"""market_state_refresh.py

Live market state refresh using yfinance plus optional FRED-backed macro fields.

Coverage via yfinance (no API key required):
  ^GSPC  S&P 500 level
  ^VIX   VIX
  ^TNX   10Y Treasury yield (already in %, e.g. 4.31)
  ^IRX   3M T-bill yield (short-rate proxy)
  DX-Y.NYB  U.S. Dollar Index (DXY)
  BZ=F   Brent crude
  CL=F   WTI crude
  ES=F   S&P 500 futures snapshot
  NQ=F   Nasdaq 100 futures snapshot
  XLI/XLF/XLK/XLE  sector posture snapshot
  ETN/JPM/NVDA  top actionable-name snapshot

Optional better macro source via FRED API:
  DGS2   2Y Treasury yield

Also wired:
  FedWatch cut prob    -- CME 30-day Fed Funds Futures primary, ZQ yfinance fallback
  Fed target range     -- still maintained manually after FOMC (update constants at top of file)

Usage:
    python scripts/market_state_refresh.py

Requirements:
    pip install yfinance

Optional better macro source:
    set FRED_API_KEY=...
"""

from __future__ import annotations

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yfinance as yf

from market_data_utils import fetch_fedwatch_probability, fetch_fred_latest

WORKSPACE = Path(__file__).resolve().parents[1]
OUT_PATH = WORKSPACE / "tmp" / "market-state.json"
STALE_AFTER_HOURS = 24
EXPECTED_UPDATE_WINDOW = "Refresh before weekly intelligence, weekday executive briefs, deployment review, trigger-sheet generation, and any macro-sensitive portfolio review."
EASTERN = ZoneInfo("America/New_York")
PREMARKET_CUTOFF = time(9, 30)

FED_TARGET_LOW = 3.50
FED_TARGET_HIGH = 3.75
FED_TARGET_DATE = "2026-04-19"
NEXT_FOMC_DATE = "2026-04-29"   # next scheduled FOMC decision date -- update after each meeting
NEXT_FOMC_ZQ_TICKER = "ZQK26"  # 30-day Fed Funds futures contract covering next FOMC (May 2026)
FIELDS = [
    ("spx", "^GSPC", "S&P 500"),
    ("vix", "^VIX", "VIX"),
    ("y10", "^TNX", "10Y Treasury"),
    ("y3m", "^IRX", "3M T-bill"),
    ("dxy", "DX-Y.NYB", "DXY"),
    ("brent", "BZ=F", "Brent"),
    ("wti", "CL=F", "WTI"),
]

FUTURES_FIELDS = [
    ("spx_futures", "ES=F", "S&P 500 futures"),
    ("nasdaq_futures", "NQ=F", "Nasdaq 100 futures"),
]

SECTOR_FIELDS = [
    ("xli", "XLI", "Industrials"),
    ("xlf", "XLF", "Financials"),
    ("xlk", "XLK", "Technology"),
    ("xle", "XLE", "Energy"),
]

ACTIONABLE_FIELDS = [
    ("ETN", "ETN", "ETN"),
    ("JPM", "JPM", "JPM"),
    ("NVDA", "NVDA", "NVDA"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_last_close(yf_ticker: str) -> tuple[float | None, str | None]:
    try:
        t = yf.Ticker(yf_ticker)
        raw = t.history(period="5d")
        if raw.empty:
            return None, None
        closes = raw["Close"].dropna()
        if closes.empty:
            return None, None
        value = round(float(closes.iloc[-1]), 4)
        data_date = closes.index[-1].strftime("%Y-%m-%d")
        return value, data_date
    except Exception:
        return None, None


def fetch_best_effort_pre_market(t: Any) -> tuple[float | None, float | None, str | None, str | None]:
    try:
        intraday = t.history(period="2d", interval="1m", prepost=True)
        if intraday.empty:
            return None, None, None, None

        closes = intraday.get("Close")
        if closes is None:
            return None, None, None, None

        closes = closes.dropna()
        if closes.empty:
            return None, None, None, None

        latest_ts = closes.index[-1]
        try:
            latest_ts_et = latest_ts.tz_convert(EASTERN)
        except Exception:
            latest_ts_et = latest_ts.tz_localize(EASTERN) if getattr(latest_ts, "tzinfo", None) is None else latest_ts

        if latest_ts_et.time() >= PREMARKET_CUTOFF:
            return None, None, None, None

        pre_market_price = round(float(closes.iloc[-1]), 4)
        previous_close = None
        try:
            info = t.info
            previous_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        except Exception:
            previous_close = None

        pre_market_change_pct = None
        if previous_close not in (None, 0):
            pre_market_change_pct = round(((pre_market_price - float(previous_close)) / float(previous_close)) * 100, 4)

        return pre_market_price, pre_market_change_pct, latest_ts_et.isoformat(), "yfinance intraday history prepost fallback"
    except Exception:
        return None, None, None, None


def fetch_snapshot(yf_ticker: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "last_price": None,
        "previous_close": None,
        "regular_market_previous_close": None,
        "change": None,
        "change_pct": None,
        "open": None,
        "day_high": None,
        "day_low": None,
        "volume": None,
        "pre_market_price": None,
        "pre_market_change_pct": None,
        "pre_market_as_of": None,
        "market_phase": None,
        "source": "yfinance fast_info/info",
        "available": False,
        "note": None,
    }
    try:
        t = yf.Ticker(yf_ticker)
        fi = t.fast_info
        info = t.info

        last_price = fi.get("lastPrice")
        previous_close = fi.get("previousClose")
        regular_market_previous_close = info.get("regularMarketPreviousClose") or previous_close
        open_price = fi.get("open")
        day_high = fi.get("dayHigh")
        day_low = fi.get("dayLow")
        volume = fi.get("lastVolume")
        pre_market_price = info.get("preMarketPrice")
        pre_market_change_pct = info.get("preMarketChangePercent")
        pre_market_as_of = None

        if last_price is not None:
            last_price = round(float(last_price), 4)
        if previous_close is not None:
            previous_close = round(float(previous_close), 4)
        if regular_market_previous_close is not None:
            regular_market_previous_close = round(float(regular_market_previous_close), 4)
        if open_price is not None:
            open_price = round(float(open_price), 4)
        if day_high is not None:
            day_high = round(float(day_high), 4)
        if day_low is not None:
            day_low = round(float(day_low), 4)
        if volume is not None:
            volume = int(volume)
        if pre_market_price is not None:
            pre_market_price = round(float(pre_market_price), 4)
        if pre_market_change_pct is not None:
            pre_market_change_pct = round(float(pre_market_change_pct), 4)

        if pre_market_price is None and "=" not in yf_ticker and not yf_ticker.startswith("^"):
            fallback_price, fallback_change_pct, fallback_as_of, fallback_source = fetch_best_effort_pre_market(t)
            if fallback_price is not None:
                pre_market_price = fallback_price
                pre_market_change_pct = fallback_change_pct
                pre_market_as_of = fallback_as_of
                snapshot["source"] = f"yfinance fast_info/info + {fallback_source}"

        change_base = regular_market_previous_close if regular_market_previous_close is not None else previous_close
        change = None
        change_pct = None
        if last_price is not None and change_base not in (None, 0):
            change = round(last_price - float(change_base), 4)
            change_pct = round((change / float(change_base)) * 100, 4)

        if pre_market_price is not None:
            market_phase = "pre-market"
        elif open_price is not None and day_high is not None:
            market_phase = "regular"
        else:
            market_phase = "unknown"

        snapshot.update(
            {
                "last_price": last_price,
                "previous_close": previous_close,
                "regular_market_previous_close": regular_market_previous_close,
                "change": change,
                "change_pct": change_pct,
                "open": open_price,
                "day_high": day_high,
                "day_low": day_low,
                "volume": volume,
                "pre_market_price": pre_market_price,
                "pre_market_change_pct": pre_market_change_pct,
                "pre_market_as_of": pre_market_as_of,
                "market_phase": market_phase,
                "available": last_price is not None,
                "note": "pre-market fields unavailable from current yfinance response" if pre_market_price is None else ("best-effort pre-market fallback from intraday history" if pre_market_as_of else None),
            }
        )
        return snapshot
    except Exception as exc:
        snapshot["note"] = f"snapshot fetch error: {exc}"
        return snapshot


def fmt(value: float | None, decimals: int = 2, prefix: str = "", suffix: str = "") -> str:
    if value is None:
        return "FAILED"
    return prefix + f"{value:,.{decimals}f}" + suffix


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Fetching market state data...")
    results: dict[str, tuple[float | None, str | None]] = {}
    for key, ticker, label in FIELDS:
        print(f"  {label} ({ticker})...", end=" ", flush=True)
        val, date = fetch_last_close(ticker)
        results[key] = (val, date)
        print("ok" if val is not None else "FAILED")

    print("  2Y Treasury (FRED DGS2)...", end=" ", flush=True)
    y2, y2_date, y2_error = fetch_fred_latest("DGS2")
    print("ok" if y2 is not None else "FAILED")

    print(f"  FedWatch cut probability ({NEXT_FOMC_ZQ_TICKER})...", end=" ", flush=True)
    cut_prob, cut_prob_source, cut_prob_note = fetch_fedwatch_probability(FED_TARGET_LOW, FED_TARGET_HIGH, NEXT_FOMC_ZQ_TICKER)
    print(f"ok ({cut_prob:.1f}%)" if cut_prob is not None else "FAILED")

    futures: dict[str, dict[str, Any]] = {}
    print("  Futures snapshots...")
    for key, ticker, label in FUTURES_FIELDS:
        print(f"    {label} ({ticker})...", end=" ", flush=True)
        snapshot = fetch_snapshot(ticker)
        futures[key] = {"ticker": ticker, "label": label, **snapshot}
        print("ok" if snapshot.get("available") else "FAILED")

    sectors: dict[str, dict[str, Any]] = {}
    print("  Sector snapshots...")
    for key, ticker, label in SECTOR_FIELDS:
        print(f"    {label} ({ticker})...", end=" ", flush=True)
        snapshot = fetch_snapshot(ticker)
        sectors[key] = {"ticker": ticker, "label": label, **snapshot}
        print("ok" if snapshot.get("available") else "FAILED")

    actionable: dict[str, dict[str, Any]] = {}
    print("  Actionable-name snapshots...")
    for key, ticker, label in ACTIONABLE_FIELDS:
        print(f"    {label} ({ticker})...", end=" ", flush=True)
        snapshot = fetch_snapshot(ticker)
        actionable[key] = {"ticker": ticker, "label": label, **snapshot}
        print("ok" if snapshot.get("available") else "FAILED")

    spx, spx_date = results["spx"]
    vix, vix_date = results["vix"]
    y10, y10_date = results["y10"]
    y3m, y3m_date = results["y3m"]
    dxy, dxy_date = results["dxy"]
    brent, brent_date = results["brent"]
    wti, wti_date = results["wti"]

    curve_3m10y_bps: float | None = None
    curve_2s10s_bps: float | None = None
    if y3m is not None and y10 is not None:
        curve_3m10y_bps = round((y10 - y3m) * 100, 1)
    if y2 is not None and y10 is not None:
        curve_2s10s_bps = round((y10 - y2) * 100, 1)

    populated = sum(v is not None for v, _ in results.values())
    total = len(FIELDS)
    if y2 is not None:
        populated += 1
    total += 1

    if populated == 0:
        status = "error"
    elif populated < total:
        status = "partial"
    else:
        status = "ok"

    last_trading_day_candidates = [d for _, d in results.values() if d]
    if y2_date:
        last_trading_day_candidates.append(y2_date)
    last_trading_day = max(last_trading_day_candidates) if last_trading_day_candidates else None

    warnings: list[str] = []
    freshness_notes: list[str] = []
    if y2 is None:
        warnings.append(
            "2Y Treasury: not populated. Set FRED_API_KEY to use FRED series DGS2 for precision 2s10s spread."
            + (f" ({y2_error})" if y2_error else "")
        )
    if y2 is not None and y10 is None:
        warnings.append("2Y populated but 10Y failed, so 2s10s spread could not be derived.")
    warnings.append(
        f"Fed target range: hardcoded {FED_TARGET_LOW}%-{FED_TARGET_HIGH}% as of {FED_TARGET_DATE}. Manual workflow: update FED_TARGET_LOW, FED_TARGET_HIGH, and FED_TARGET_DATE in scripts/market_state_refresh.py after each FOMC decision."
    )
    if cut_prob is None:
        warnings.append(
            f"FedWatch cut probability fetch failed for {NEXT_FOMC_ZQ_TICKER}. "
            f"Check cut_prob_note in output JSON for details. "
            "Manual fallback: verify CME FedWatch directly and write probability into the note layer."
        )
    if populated < total:
        warnings.append(f"Only {populated}/{total} live fields populated.")
    if last_trading_day is None:
        warnings.append("No valid trading day found in market-state output.")
    if all(not item.get("pre_market_price") for item in futures.values()) and all(not item.get("pre_market_price") for item in actionable.values()):
        warnings.append("True pre-market pricing was not available from current yfinance responses. Use futures and latest cash snapshots as context, not as full pre-market tape.")
    if last_trading_day is not None:
        source_dates = {
            "spx": spx_date,
            "vix": vix_date,
            "10y": y10_date,
            "3m": y3m_date,
            "dxy": dxy_date,
            "brent": brent_date,
            "wti": wti_date,
            "2y": y2_date,
        }
        mismatched_sources = sorted(k for k, v in source_dates.items() if v and v != last_trading_day)

        # FRED DGS2 publishes on a 1-business-day lag by design. If "2y" is the only
        # mismatch and its date is exactly 1 calendar day before last_trading_day,
        # reclassify as an expected informational note — not a warning.
        _2y_expected_lag = False
        if mismatched_sources == ["2y"] and y2_date is not None:
            try:
                _lag_days = (
                    datetime.strptime(last_trading_day, "%Y-%m-%d").date()
                    - datetime.strptime(y2_date, "%Y-%m-%d").date()
                ).days
                if _lag_days == 1:
                    _2y_expected_lag = True
                    freshness_notes.append("fred_dgs2_1day_lag_expected")
                    mismatched_sources = []  # clear so warning block is not entered
            except Exception:
                pass  # date parse failure: fall through to normal warning

        if mismatched_sources:
            warnings.append(
                "Market-state sources are not aligned on one trading day: " + ", ".join(mismatched_sources)
            )
            freshness_notes.append("mixed_source_dates")

    for sector in sectors.values():
        if sector.get("change_pct") is None or spx in (None, 0):
            sector["relative_vs_spx_pct"] = None
            sector["relative_label"] = None
            continue
        spx_change_pct = None
        if results["spx"][0] is not None:
            spx_prev_proxy = None
            spx_snapshot = fetch_snapshot("SPY")
            spx_prev_proxy = spx_snapshot.get("regular_market_previous_close")
            spx_last_proxy = spx_snapshot.get("last_price")
            if spx_prev_proxy not in (None, 0) and spx_last_proxy is not None:
                spx_change_pct = round(((spx_last_proxy - spx_prev_proxy) / spx_prev_proxy) * 100, 4)
        if spx_change_pct is None:
            sector["relative_vs_spx_pct"] = None
            sector["relative_label"] = None
            continue
        rel = round(float(sector["change_pct"]) - spx_change_pct, 4)
        sector["relative_vs_spx_pct"] = rel
        if rel >= 0.35:
            sector["relative_label"] = "strong vs SPY"
        elif rel <= -0.35:
            sector["relative_label"] = "weak vs SPY"
        else:
            sector["relative_label"] = "roughly in line with SPY"

    state: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "source_last_trading_day": {
            "spx": spx_date,
            "vix": vix_date,
            "10y": y10_date,
            "3m": y3m_date,
            "2y": y2_date,
            "dxy": dxy_date,
            "brent": brent_date,
            "wti": wti_date,
        },
        "freshness_notes": freshness_notes,
        "warnings": warnings,
        "data": {
            "fed": {
                "target_low": FED_TARGET_LOW,
                "target_high": FED_TARGET_HIGH,
                "target_source": "hardcoded constants in scripts/market_state_refresh.py",
                "target_confirmed": FED_TARGET_DATE,
                "manual_update_required": True,
                "manual_update_workflow": "After each FOMC decision, update FED_TARGET_LOW, FED_TARGET_HIGH, and FED_TARGET_DATE in scripts/market_state_refresh.py, then rerun this script.",
                "cut_probability_next_meeting": cut_prob,
                "cut_prob_source": cut_prob_source,
                "cut_prob_note": cut_prob_note,
                "next_fomc_date": NEXT_FOMC_DATE,
                "next_fomc_zq_ticker": NEXT_FOMC_ZQ_TICKER,
            },
            "treasuries": {
                "2y": y2,
                "2y_as_of": y2_date,
                "2y_source": "FRED DGS2" if y2 is not None else None,
                "2y_note": y2_error if y2 is None else None,
                "10y": y10,
                "10y_as_of": y10_date,
                "10y_source": "yfinance ^TNX" if y10 is not None else None,
                "3m_tbill": y3m,
                "3m_as_of": y3m_date,
                "3m_source": "yfinance ^IRX" if y3m is not None else None,
                "curve_2s10s_bps": curve_2s10s_bps,
                "curve_2s10s_note": "Derived from FRED DGS2 and yfinance ^TNX" if curve_2s10s_bps is not None else "2s10s unavailable without both 2Y and 10Y",
                "curve_3m10y_bps": curve_3m10y_bps,
                "curve_3m10y_note": "Derived from yfinance ^IRX and ^TNX" if curve_3m10y_bps is not None else "3M-10Y unavailable without both 3M and 10Y",
            },
            "volatility": {
                "vix": vix,
                "as_of": vix_date,
                "source": "yfinance ^VIX" if vix is not None else None,
            },
            "equities": {
                "spx": spx,
                "as_of": spx_date,
                "source": "yfinance ^GSPC" if spx is not None else None,
            },
            "fx": {
                "dxy": dxy,
                "as_of": dxy_date,
                "source": "yfinance DX-Y.NYB" if dxy is not None else None,
            },
            "energy": {
                "brent": brent,
                "brent_as_of": brent_date,
                "brent_source": "yfinance BZ=F" if brent is not None else None,
                "wti": wti,
                "wti_as_of": wti_date,
                "wti_source": "yfinance CL=F" if wti is not None else None,
            },
            "futures": futures,
            "sectors": sectors,
            "actionable": actionable,
        },
    }

    OUT_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    sep = "=" * 60
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{sep}")
    print(f"  MARKET STATE REFRESH  --  {now}")
    print(sep)

    if last_trading_day:
        print(f"\n  Last trading day covered: {last_trading_day}")

    print("\n  FED")
    print(f"    Target range : {FED_TARGET_LOW:.2f}% - {FED_TARGET_HIGH:.2f}%  (hardcoded, confirmed {FED_TARGET_DATE})")
    if cut_prob is not None:
        print(f"    Cut prob     : {cut_prob:.1f}%  (next FOMC {NEXT_FOMC_DATE}, via {cut_prob_source})")
    else:
        print(f"    Cut prob     : FAILED  ({cut_prob_note or 'unknown error'})")

    print("\n  RATES")
    print("    2Y Treasury  : " + (fmt(y2, 3, suffix="%") + f"  (as of {y2_date}, FRED DGS2)" if y2 is not None else f"FAILED ({y2_error or 'not wired'})"))
    print("    10Y Treasury : " + (fmt(y10, 3, suffix="%") + f"  (as of {y10_date})" if y10 is not None else "FAILED"))
    print("    3M T-bill    : " + (fmt(y3m, 3, suffix="%") + f"  (as of {y3m_date})" if y3m is not None else "FAILED"))
    if curve_2s10s_bps is not None:
        sign = "+" if curve_2s10s_bps >= 0 else ""
        print(f"    2s10s spread : {sign}{curve_2s10s_bps:.1f} bps")
    else:
        print("    2s10s spread : --")
    if curve_3m10y_bps is not None:
        sign = "+" if curve_3m10y_bps >= 0 else ""
        print(f"    3M-10Y spread: {sign}{curve_3m10y_bps:.1f} bps")
    else:
        print("    3M-10Y spread: --")

    print("\n  VOLATILITY / EQUITIES / FX / ENERGY")
    print("    VIX          : " + (fmt(vix, 2) + f"  (as of {vix_date})" if vix is not None else "FAILED"))
    print("    S&P 500      : " + (fmt(spx, 2) + f"  (as of {spx_date})" if spx is not None else "FAILED"))
    print("    DXY          : " + (fmt(dxy, 2) + f"  (as of {dxy_date})" if dxy is not None else "FAILED"))
    print("    Brent        : " + (fmt(brent, 2, suffix=" $/bbl") + f"  (as of {brent_date})" if brent is not None else "FAILED"))
    print("    WTI          : " + (fmt(wti, 2, suffix=" $/bbl") + f"  (as of {wti_date})" if wti is not None else "FAILED"))

    print("\n  PRE-MARKET / LIVE SNAPSHOTS")
    for bucket_name, bucket in (("Futures", futures), ("Sectors", sectors), ("Actionable", actionable)):
        print(f"    {bucket_name}:")
        for item in bucket.values():
            lp = item.get("last_price")
            cp = item.get("change_pct")
            pm = item.get("pre_market_price")
            rel = item.get("relative_label")
            line = f"      {item['label']:<14} "
            if lp is None:
                line += "FAILED"
            else:
                line += f"last {lp:,.2f}"
                if cp is not None:
                    sign = "+" if cp >= 0 else ""
                    line += f" ({sign}{cp:.2f}%)"
                if pm is not None:
                    line += f", pre {pm:,.2f}"
            if rel:
                line += f"  [{rel}]"
            print(line)

    if warnings:
        print("\n  WARNINGS")
        for w in warnings:
            print(f"    ⚠  {w}")

    print(f"\n  Saved → {OUT_PATH.relative_to(WORKSPACE)}")
    print(sep + "\n")


if __name__ == "__main__":
    main()
