"""entry_band_fetch.py

Generalized entry-band data fetcher. Pulls OHLC for any ticker from
yfinance, tags each bar with a workspace-defined macro regime, optionally
overlays the vault's preferred band from tmp/portfolio-config.json, and
writes a JSON bundle that scripts/entry_band_viewer.jsx renders.

Pair:
    scripts/entry_band_fetch.py    -- this file (data + HTML generation)
    scripts/entry_band_viewer.jsx  -- generalized React viewer component

Embed pattern note:
    `entry_band_viewer.jsx` is not a standalone build-tooled React app.
    This script reads that JSX source as a checked-in inline viewer bundle and
    injects it directly into the generated per-ticker HTML files under
    `tmp/entry-band-reports/`. Treat it as a governed render asset for this
    exporter, not as a separate frontend project that needs its own npm/build
    pipeline.

Usage:
    python scripts/entry_band_fetch.py NVDA                       # JSON only, monthly, 10y
    python scripts/entry_band_fetch.py NVDA --html                # + self-contained HTML
    python scripts/entry_band_fetch.py JPM --interval 1d --years 5 --html
    python scripts/entry_band_fetch.py ETN --html --open          # also open in browser

Outputs:
    tmp/entry-band-data/{TICKER}.json
    tmp/entry-band-reports/{TICKER}_entry_band.html   (with --html)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import webbrowser
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import universe

try:
    import yfinance as yf
except ImportError:
    print("yfinance is required. Install with: pip install yfinance", file=sys.stderr)
    sys.exit(2)


WORKSPACE = Path(__file__).resolve().parents[1]
TMP_DATA_DIR = WORKSPACE / "tmp" / "entry-band-data"
HTML_DIR = WORKSPACE / "tmp" / "entry-band-reports"
BATCH_MANIFEST_PATH = TMP_DATA_DIR / "_batch-manifest.json"
JSX_PATH = WORKSPACE / "scripts" / "entry_band_viewer.jsx"
PORTFOLIO_CONFIG_PATH = WORKSPACE / "tmp" / "portfolio-config.json"
TECH_REFRESH_PATH = WORKSPACE / "tmp" / "technical-refresh.json"
BAND_PROPOSALS_PATH = WORKSPACE / "tmp" / "band-proposals.json"


# Macro regime catalogue. Edit when the regime read changes.
# Periods are inclusive YYYY-MM:YYYY-MM ranges; bars are tagged by YYYY-MM
# prefix, so daily-interval bundles still match correctly.
MACRO_REGIMES: dict[str, dict[str, Any]] = {
    "low_rate_low_vol": {"label": "Low Rate / Low Vol", "color": "#3b82f6",
                          "periods": ["2015-01:2015-07", "2017-01:2017-12"]},
    "tightening": {"label": "Tightening Cycle", "color": "#f59e0b",
                    "periods": ["2016-11:2016-12", "2018-01:2018-09",
                                "2022-01:2022-12", "2025-01:2025-12",
                                "2026-01:2026-12"]},
    "vol_spike_crisis": {"label": "Vol Spike / Crisis", "color": "#ef4444",
                          "periods": ["2015-08:2015-10", "2018-10:2018-12",
                                      "2020-02:2020-04"]},
    "easing_recovery": {"label": "Easing / Recovery", "color": "#10b981",
                         "periods": ["2016-01:2016-10", "2019-01:2019-12",
                                     "2020-05:2021-06"]},
    "peak_hold": {"label": "Peak Rate Hold", "color": "#8b5cf6",
                   "periods": ["2023-01:2024-03"]},
    "stimulus_boom": {"label": "Stimulus / Capex Boom", "color": "#ec4899",
                       "periods": ["2021-07:2021-12", "2024-04:2024-12"]},
}


def _round(v: Any, ndigits: int = 2) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, ndigits)


def _years_ago(n: int) -> date:
    today = date.today()
    try:
        return today.replace(year=today.year - n)
    except ValueError:
        return today.replace(year=today.year - n, day=28)


def fetch_ohlc(ticker: str, years: int, interval: str, start: str | None):
    """Fetch OHLC from yfinance. Returns (bars, meta)."""
    start_date = start or _years_ago(years).isoformat()
    asof_date = date.today()
    # yfinance treats `end` as exclusive. Use tomorrow as the fetch boundary so
    # same-day/post-close refreshes do not silently drop the latest trading day
    # while still labeling the bundle with today's as-of date.
    fetch_end_date = (asof_date + timedelta(days=1)).isoformat()
    yf_ticker = yf.Ticker(ticker.replace(".", "-"))
    hist = yf_ticker.history(start=start_date, end=fetch_end_date, interval=interval, auto_adjust=False)
    if hist is None or hist.empty:
        raise RuntimeError(f"yfinance returned no history for {ticker} ({interval}, since {start_date})")

    info: dict[str, Any] = {}
    try:
        info = yf_ticker.info or {}
    except Exception:
        info = {}
    name = info.get("longName") or info.get("shortName") or ticker
    currency = info.get("currency", "USD")

    bars: list[dict[str, Any]] = []
    monthly = interval in {"1mo", "3mo"}
    for ts, row in hist.iterrows():
        d_str = ts.strftime("%Y-%m" if monthly else "%Y-%m-%d")
        try:
            bars.append({
                "d": d_str,
                "o": _round(row["Open"]),
                "h": _round(row["High"]),
                "l": _round(row["Low"]),
                "c": _round(row["Close"]),
                "v": _round((row.get("Volume", 0) or 0) / 1_000_000, 2),
            })
        except (ValueError, TypeError, KeyError):
            continue
    bars = [b for b in bars if b["c"] is not None]

    meta = {
        "name": name,
        "currency": currency,
        "interval": interval,
        "asof": asof_date.isoformat(),
        "period": {"start": bars[0]["d"] if bars else "", "end": bars[-1]["d"] if bars else ""},
    }
    return bars, meta


def load_preferred_band(ticker: str) -> dict[str, Any] | None:
    """Look up vault's preferred entry band for `ticker`.

    Canonical schema (apply_band_update.py):
        cfg["entry_bands"][TICKER] = {low, high, stop, label, stop_label, band_last_set}
    Tolerates a couple of legacy/variant shapes too. None if no usable band.
    """
    if not PORTFOLIO_CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(PORTFOLIO_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cfg, dict):
        return None

    sym = ticker.upper()
    candidate: dict[str, Any] | None = None

    eb = cfg.get("entry_bands")
    if isinstance(eb, dict):
        candidate = eb.get(sym) or eb.get(ticker)

    if candidate is None:
        tickers_d = cfg.get("tickers")
        if isinstance(tickers_d, dict):
            candidate = tickers_d.get(sym) or tickers_d.get(ticker)
    if candidate is None and (sym in cfg or ticker in cfg):
        maybe = cfg.get(sym) or cfg.get(ticker)
        if isinstance(maybe, dict) and any(k in maybe for k in ("low", "high", "stop", "band_low", "band_high")):
            candidate = maybe
    if candidate is None and isinstance(cfg.get("positions"), list):
        for pos in cfg["positions"]:
            if isinstance(pos, dict) and (pos.get("ticker") or "").upper() == sym:
                candidate = pos
                break

    if not candidate:
        return None

    low = candidate.get("low") if "low" in candidate else (candidate.get("band_low") or candidate.get("entry_low"))
    high = candidate.get("high") if "high" in candidate else (candidate.get("band_high") or candidate.get("entry_high"))
    stop = candidate.get("stop") if "stop" in candidate else candidate.get("explicit_stop")
    set_date = candidate.get("band_last_set") or candidate.get("last_set") or candidate.get("set")
    label = candidate.get("label")

    if low is None and high is None and stop is None:
        return None
    return {
        "low": _round(low) if low is not None else None,
        "high": _round(high) if high is not None else None,
        "stop": _round(stop) if stop is not None else None,
        "set": set_date,
        "label": label,
    }


def load_current_quote(ticker: str) -> dict[str, Any] | None:
    """Pull the most recent close + MA snapshot from technical-refresh.json."""
    if not TECH_REFRESH_PATH.exists():
        return None
    try:
        data = json.loads(TECH_REFRESH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for rec in (data.get("records") or []):
        if rec.get("ticker", "").upper() == ticker.upper():
            close = rec.get("close")
            if close is None:
                return None
            return {
                "close": close,
                "ma20": rec.get("ma20"),
                "ma50": rec.get("ma50"),
                "ma200": rec.get("ma200"),
                "data_date": rec.get("data_date"),
            }
    return None


def load_latest_band_proposal(ticker: str) -> dict[str, Any] | None:
    """Return the latest review-only band-engine proposal for a ticker."""
    if not BAND_PROPOSALS_PATH.exists():
        return None
    try:
        data = json.loads(BAND_PROPOSALS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for rec in (data.get("proposals") or []):
        if rec.get("ticker", "").upper() == ticker.upper():
            return {
                "engine_version": rec.get("engine_version"),
                "method": rec.get("entry_band_method"),
                "type": rec.get("entry_band_type"),
                "status": rec.get("band_status"),
                "trend_stack": rec.get("trend_stack"),
                "suggested_low": rec.get("suggested_band_low"),
                "suggested_high": rec.get("suggested_band_high"),
                "suggested_stop": rec.get("suggested_stop"),
                "sma_envelope_low": rec.get("sma_envelope_low"),
                "sma_envelope_high": rec.get("sma_envelope_high"),
                "earnings_state": rec.get("earnings_state"),
                "earnings_date_source_class": rec.get("earnings_date_source_class"),
                "earnings_primary_confirmed": rec.get("earnings_primary_confirmed"),
                "band_confidence": rec.get("band_confidence"),
                "needs_review": rec.get("needs_review"),
                "canonical_apply_eligible": rec.get("canonical_apply_eligible"),
            }
    return None


def build_bundle(ticker: str, years: int, interval: str, start: str | None) -> dict[str, Any]:
    bars, meta = fetch_ohlc(ticker, years, interval, start)
    bundle: dict[str, Any] = {
        "ticker": ticker.upper(),
        "name": meta["name"],
        "asof": meta["asof"],
        "currency": meta["currency"],
        "interval": meta["interval"],
        "period": meta["period"],
        "data": bars,
        "macro_regimes": MACRO_REGIMES,
        "preferred_band": load_preferred_band(ticker.upper()),
        "current_quote": load_current_quote(ticker.upper()),
        "band_engine_proposal": load_latest_band_proposal(ticker.upper()),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if interval == "1wk":
        bundle["fwd_periods"] = [4, 13, 26]
        bundle["fwd_label"] = "Weeks"
    return bundle


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{TICKER} -- Entry Band Analysis</title>
  <style>
    html, body {{ margin: 0; padding: 0; background: #0c0f14; color: #e8eaed;
                  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    #root {{ min-height: 100vh; }}
    .__loading {{ padding: 60px 24px; color: #6b7280; text-align: center; font-size: 14px; }}
  </style>
  <script type="importmap">
  {{
    "imports": {{
      "react":             "https://esm.sh/react@18.2.0",
      "react/jsx-runtime": "https://esm.sh/react@18.2.0/jsx-runtime",
      "react-dom":         "https://esm.sh/react-dom@18.2.0",
      "react-dom/client":  "https://esm.sh/react-dom@18.2.0/client",
      "recharts":          "https://esm.sh/recharts@2.12.7?external=react,react-dom"
    }}
  }}
  </script>
  <script src="https://unpkg.com/@babel/standalone@7.24.0/babel.min.js"></script>
</head>
<body>
  <div id="root">
    <div class="__loading">Loading {TICKER} entry-band analysis...</div>
  </div>
  <script>window.__ENTRY_BAND_DATA__ = {DATA_JSON};</script>
  <script type="text/babel" data-type="module" data-presets="react">
{JSX_CODE}

import React from "react";
import {{ createRoot }} from "react-dom/client";
const __root = createRoot(document.getElementById("root"));
__root.render(React.createElement(EntryBandViewer));
  </script>
</body>
</html>
"""


def prepare_jsx_for_inline(jsx_path: Path) -> str:
    """Strip `export default` so EntryBandViewer is a plain identifier
    inside the HTML's text/babel module block. Imports stay (importmap)."""
    src = jsx_path.read_text(encoding="utf-8")
    src = re.sub(
        r"^\s*export\s+default\s+function\s+EntryBandViewer",
        "function EntryBandViewer",
        src,
        count=1,
        flags=re.MULTILINE,
    )
    return src


def render_html(bundle: dict[str, Any], out_path: Path) -> None:
    if not JSX_PATH.exists():
        raise FileNotFoundError(
            f"Cannot find viewer at {JSX_PATH}. The fetcher and viewer are a pair -- both must be present."
        )
    jsx_code = prepare_jsx_for_inline(JSX_PATH)
    data_json = json.dumps(bundle, ensure_ascii=False)
    html = HTML_TEMPLATE.format(TICKER=bundle["ticker"], DATA_JSON=data_json, JSX_CODE=jsx_code)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def load_tracked_tickers() -> list[str]:
    """Return all tickers entitled to technical_refresh from portfolio-config.json."""
    if not PORTFOLIO_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {PORTFOLIO_CONFIG_PATH}")
    cfg = json.loads(PORTFOLIO_CONFIG_PATH.read_text(encoding="utf-8"))
    tracked = cfg.get("tracked_universe") or {}
    return [
        ticker.upper()
        for ticker, meta in tracked.items()
        if isinstance(meta, dict) and universe.is_entitled(ticker, meta, "technical_refresh")
    ]


def run_all_tracked(args: argparse.Namespace) -> int:
    """Batch-fetch and optionally render HTML for every tracked ticker."""
    try:
        tickers = load_tracked_tickers()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[entry_band_fetch] Cannot load tracked tickers: {exc}", file=sys.stderr)
        return 1

    if not tickers:
        print("[entry_band_fetch] No tracked tickers found in portfolio-config.json", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[entry_band_fetch] Batch mode: {len(tickers)} tickers — {', '.join(tickers)}", flush=True)

    failed: list[str] = []
    succeeded: list[str] = []
    for ticker in tickers:
        if not args.quiet:
            print(f"\n[entry_band_fetch] --- {ticker} ---", flush=True)
        try:
            bundle = build_bundle(ticker, args.years, args.interval, args.start)
        except RuntimeError as exc:
            print(f"[entry_band_fetch] {ticker}: fetch failed — {exc}", file=sys.stderr)
            failed.append(ticker)
            continue

        n = len(bundle["data"])
        if n < 12:
            print(f"[entry_band_fetch] {ticker}: WARNING only {n} bars — band methods need more history", file=sys.stderr)

        TMP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        json_path = TMP_DATA_DIR / f"{ticker}.json"
        json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"[entry_band_fetch] {ticker}: wrote JSON ({n} bars)", flush=True)
            pb = bundle.get("preferred_band")
            if pb:
                print(f"[entry_band_fetch] {ticker}: vault band low={pb.get('low')} high={pb.get('high')} stop={pb.get('stop')}", flush=True)
            cq = bundle.get("current_quote")
            if cq:
                print(f"[entry_band_fetch] {ticker}: live quote close={cq.get('close')} ma20={cq.get('ma20')} ma50={cq.get('ma50')} ma200={cq.get('ma200')}", flush=True)

        if args.html:
            try:
                html_path = HTML_DIR / f"{ticker}_entry_band.html"
                render_html(bundle, html_path)
                if not args.quiet:
                    print(f"[entry_band_fetch] {ticker}: wrote HTML", flush=True)
            except Exception as exc:
                print(f"[entry_band_fetch] {ticker}: HTML render failed — {exc}", file=sys.stderr)
                failed.append(ticker)

        if ticker not in failed:
            succeeded.append(ticker)

    manifest = {
        "schema": "entry_band_fetch_batch_manifest.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "error" if failed else "ok",
        "html_enabled": bool(args.html),
        "interval": args.interval,
        "years": args.years,
        "start": args.start,
        "ticker_count": len(tickers),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "succeeded_tickers": succeeded,
        "failed_tickers": failed,
        "data_dir": str(TMP_DATA_DIR.relative_to(WORKSPACE)),
        "html_dir": str(HTML_DIR.relative_to(WORKSPACE)),
    }
    BATCH_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCH_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[entry_band_fetch] Batch complete: {len(tickers) - len(failed)}/{len(tickers)} succeeded.", flush=True)
    if failed:
        print(f"[entry_band_fetch] Failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Fetch OHLC for any ticker and produce an entry-band data bundle (and optional HTML report).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("ticker", nargs="?", default=None,
                   help="Ticker symbol, e.g., NVDA, JPM, ETN, BRK-B, ^GSPC (omit with --all-tracked)")
    p.add_argument("--all-tracked", action="store_true", dest="all_tracked",
                   help="Batch-fetch all tickers entitled to technical_refresh from portfolio-config.json")
    p.add_argument("--years", type=int, default=10, help="History window in years (ignored if --start given)")
    p.add_argument("--start", default=None, help="Explicit start date YYYY-MM-DD (overrides --years)")
    p.add_argument("--interval", default="1mo", choices=["1d", "1wk", "1mo"], help="Bar interval")
    p.add_argument("--html", action="store_true", help="Also emit the self-contained HTML viewer")
    p.add_argument("--open", action="store_true", dest="open_browser", help="Open the HTML in the default browser when done")
    p.add_argument("--quiet", action="store_true", help="Suppress progress logs")
    args = p.parse_args(argv)

    if args.all_tracked:
        return run_all_tracked(args)

    if not args.ticker:
        p.error("ticker is required unless --all-tracked is specified")

    ticker = args.ticker.upper().strip()
    if not re.match(r"^[A-Z\^][A-Z0-9.\-=^]*$", ticker):
        print(f"Refusing suspicious ticker symbol: {args.ticker!r}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"[entry_band_fetch] {ticker} | interval={args.interval} | window={args.years}y", flush=True)

    try:
        bundle = build_bundle(ticker, args.years, args.interval, args.start)
    except RuntimeError as exc:
        print(f"[entry_band_fetch] {exc}", file=sys.stderr)
        return 1

    n = len(bundle["data"])
    if n < 12:
        print(f"[entry_band_fetch] WARNING: only {n} bars returned -- band methods need more history", file=sys.stderr)

    TMP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_path = TMP_DATA_DIR / f"{ticker}.json"
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print(f"[entry_band_fetch] wrote {json_path.relative_to(WORKSPACE)} ({n} bars)", flush=True)
        pb = bundle.get("preferred_band")
        if pb:
            print(f"[entry_band_fetch] vault preferred band: low={pb.get('low')} high={pb.get('high')} stop={pb.get('stop')} set={pb.get('set')}", flush=True)
        cq = bundle.get("current_quote")
        if cq:
            print(f"[entry_band_fetch] live quote: close={cq.get('close')} ma20={cq.get('ma20')} ma50={cq.get('ma50')} ma200={cq.get('ma200')}", flush=True)

    if args.html:
        html_path = HTML_DIR / f"{ticker}_entry_band.html"
        render_html(bundle, html_path)
        if not args.quiet:
            print(f"[entry_band_fetch] wrote {html_path.relative_to(WORKSPACE)}", flush=True)
        if args.open_browser:
            webbrowser.open(html_path.resolve().as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
