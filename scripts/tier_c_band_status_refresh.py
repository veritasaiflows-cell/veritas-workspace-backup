#!/usr/bin/env python3
"""Build a monitor-grade Tier C band-status surface.

This is a review-only Tier C triage artifact. It computes coarse reference
bands/stops and status buckets so WF78 can rank thin-monitor names without
promoting them into decision-grade deployment, sizing, or execution posture.

It does not mutate ticker cards, portfolio config, canon, SQL canon/cache,
deployment surfaces, sizing, paper/live orders, accounts, or owner notes.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

try:
    import yfinance as yf
except Exception:  # pragma: no cover - exercised only when provider package is missing.
    yf = None  # type: ignore[assignment]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "tier-c-band-status.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
SCHEMA = "veritas.tier_c_band_status.v1"
ENGINE_VERSION = "tier-c-monitor-keltner-v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "tier_c_monitor_band_status_only": True,
    "automated_non_capital_routing_allowed": True,
    "monitor_grade_only": True,
    "decision_grade_entry_stop_allowed": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_config_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "position_sizing_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_AUTHORITY = {
    "review_only",
    "tier_c_monitor_band_status_only",
    "automated_non_capital_routing_allowed",
    "monitor_grade_only",
}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def yf_symbol(symbol: str) -> str:
    # yfinance uses hyphenated share-class symbols.
    return symbol.replace(".", "-")


def finite_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def round_price(value: Any) -> float | None:
    f = finite_float(value)
    return round(f, 2) if f is not None else None


def load_routes() -> list[dict[str, Any]]:
    payload = load_json_artifact(AUTO_ROUTER)
    rows = as_list(as_dict(payload).get("rows"))
    return [as_dict(row) for row in rows if ticker(as_dict(row).get("ticker"))]


def tier_c_routes() -> list[dict[str, Any]]:
    return [row for row in load_routes() if row.get("auto_tier") == "Tier C"]


def sqlite_fallback_rows() -> dict[str, dict[str, Any]]:
    if not STATE_DB.exists():
        return {}
    con = sqlite3.connect(STATE_DB)
    con.row_factory = sqlite3.Row
    try:
        query = """
        select
            u.ticker,
            l.latest_known_price,
            l.band_status,
            l.raw_json as latest_raw_json,
            e.entry_band_low,
            e.entry_band_high,
            e.stop_or_invalidation,
            e.source_timestamp
        from universe u
        left join latest_price_technical l on l.ticker = u.ticker
        left join entry_stop_reference e on e.ticker = u.ticker
        where u.tier = 'C'
        """
        rows = {}
        for row in con.execute(query):
            item = dict(row)
            rows[ticker(item.get("ticker"))] = item
        return rows
    finally:
        con.close()


def download_prices(symbols: list[str], *, period: str, interval: str) -> tuple[dict[str, Any], list[str]]:
    if yf is None:
        return {}, ["yfinance unavailable; provider refresh skipped"]
    if not symbols:
        return {}, []
    provider_symbols = [yf_symbol(symbol) for symbol in symbols]
    try:
        data = yf.download(
            " ".join(provider_symbols),
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        return {}, [f"yfinance batch download failed: {exc}"]
    return {symbol: data.get(yf_symbol(symbol)) for symbol in symbols if hasattr(data, "get")}, []


def series_last(series: Any) -> float | None:
    try:
        clean = series.dropna()
        if clean.empty:
            return None
        return finite_float(clean.iloc[-1])
    except Exception:
        return None


def series_date(series: Any) -> str | None:
    try:
        clean = series.dropna()
        if clean.empty:
            return None
        idx = clean.index[-1]
        if hasattr(idx, "date"):
            return idx.date().isoformat()
        return str(idx)[:10]
    except Exception:
        return None


def build_technical(symbol: str, frame: Any) -> dict[str, Any]:
    if frame is None or getattr(frame, "empty", True):
        return {"ticker": symbol, "status": "missing_provider_frame"}
    try:
        close = frame["Close"].dropna()
        high = frame["High"].dropna()
        low = frame["Low"].dropna()
    except Exception:
        return {"ticker": symbol, "status": "missing_provider_columns"}
    if len(close) < 50:
        return {"ticker": symbol, "status": "insufficient_history", "history_count": len(close)}

    prev_close = close.shift(1)
    tr = (high - low).combine(abs(high - prev_close), max).combine(abs(low - prev_close), max)
    latest_close = series_last(close)
    atr20 = series_last(tr.rolling(20).mean())
    ema20 = series_last(close.ewm(span=20, adjust=False).mean())
    ema50 = series_last(close.ewm(span=50, adjust=False).mean())
    sma200 = series_last(close.rolling(200).mean()) if len(close) >= 200 else None
    return {
        "ticker": symbol,
        "status": "ok",
        "history_count": len(close),
        "data_date": series_date(close),
        "close": round_price(latest_close),
        "ema20": round_price(ema20),
        "ema50": round_price(ema50),
        "sma200": round_price(sma200),
        "atr20": round_price(atr20),
        "atrp20": round(atr20 / latest_close, 4) if atr20 and latest_close else None,
    }


def classify_trend(close: float | None, ema20: float | None, ema50: float | None, sma200: float | None) -> str:
    if close is None or ema20 is None or ema50 is None:
        return "UNKNOWN"
    if sma200 is not None and close < sma200 and close < ema20 and close < ema50:
        return "BELOW_ALL_MAS"
    if sma200 is not None and close < sma200:
        return "BELOW_200"
    if sma200 is not None and close > ema20 > ema50 > sma200:
        return "BULLISH_20_50_200"
    if sma200 is not None and close > ema20 and close > ema50 and close > sma200:
        return "ABOVE_ALL_MAS"
    return "MIXED"


def atr_multiplier(atrp20: float | None) -> float:
    if atrp20 is None:
        return 2.0
    if atrp20 < 0.015:
        return 1.5
    if atrp20 <= 0.035:
        return 2.0
    return 2.5


def classify_band(close: float | None, low: float | None, high: float | None, stop: float | None, trend: str) -> tuple[str, float | None]:
    if close is None:
        return "UNKNOWN", None
    if stop is not None and close < stop:
        return "BELOW_STOP", None
    if trend in {"BELOW_200", "BELOW_ALL_MAS"}:
        return "RECLAIM_ONLY", None
    if low is None or high is None:
        return "UNKNOWN", None
    if low <= close <= high:
        return "IN_BAND", round((close - high) / high * 100, 2)
    if close < low:
        return "BELOW_BAND", round((close - low) / low * 100, 2)
    dist = round((close - high) / high * 100, 2)
    return ("NEAR_BAND" if dist <= 5.0 else "ABOVE_BAND", dist)


def monitor_band(tech: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    close = finite_float(tech.get("close")) or finite_float(fallback.get("latest_known_price"))
    ema20 = finite_float(tech.get("ema20"))
    ema50 = finite_float(tech.get("ema50"))
    sma200 = finite_float(tech.get("sma200"))
    atr20 = finite_float(tech.get("atr20"))
    atrp20 = finite_float(tech.get("atrp20"))
    trend = classify_trend(close, ema20, ema50, sma200)

    source = "provider_calculated_monitor_band"
    low: float | None = None
    high: float | None = None
    stop: float | None = None
    confidence = 0
    warnings: list[str] = []

    if close is not None and ema20 is not None and ema50 is not None and atr20 is not None:
        mult = atr_multiplier(atrp20)
        low = max(ema20 - mult * atr20, ema50 - 0.5 * atr20)
        high = ema20 + 0.25 * atr20
        if trend in {"BELOW_200", "BELOW_ALL_MAS"} and sma200 is not None:
            low = max(ema50, sma200)
            high = low + 1.25 * atr20
        if low >= high:
            high = low + max(0.5 * atr20, close * 0.005)
        stop = low - 1.25 * atr20
        confidence = 2 if trend in {"UNKNOWN", "MIXED"} else 3
    else:
        low = finite_float(fallback.get("entry_band_low"))
        high = finite_float(fallback.get("entry_band_high"))
        stop = finite_float(fallback.get("stop_or_invalidation"))
        source = "existing_sql_reference_fallback" if low and high else "insufficient_monitor_inputs"
        confidence = 1 if low and high and close is not None else 0
        if confidence == 0:
            warnings.append("missing provider inputs and existing SQL band reference")

    low = round_price(low)
    high = round_price(high)
    stop = round_price(stop)
    status, distance = classify_band(round_price(close), low, high, stop, trend)
    if status == "UNKNOWN" and fallback.get("band_status") not in {None, "", "missing_required_refresh"}:
        status = str(fallback.get("band_status")).upper()
    return {
        "latest_price": round_price(close),
        "reference_band_low": low,
        "reference_band_high": high,
        "coarse_reference_stop": stop,
        "band_status": status,
        "distance_to_band_pct": distance,
        "trend_stack": trend,
        "confidence": confidence,
        "reference_source": source,
        "warnings": warnings,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    routes = tier_c_routes()
    if args.limit:
        routes = routes[: args.limit]
    symbols = [ticker(row.get("ticker")) for row in routes]
    fallback = sqlite_fallback_rows()
    provider_frames: dict[str, Any] = {}
    provider_warnings: list[str] = []
    if not args.skip_provider_refresh:
        provider_frames, provider_warnings = download_prices(symbols, period=args.period, interval=args.interval)

    rows: list[dict[str, Any]] = []
    for route in routes:
        symbol = ticker(route.get("ticker"))
        fb = fallback.get(symbol, {})
        tech = build_technical(symbol, provider_frames.get(symbol)) if provider_frames else {"ticker": symbol, "status": "provider_refresh_skipped"}
        band = monitor_band(tech, fb)
        rows.append({
            "ticker": symbol,
            "name": route.get("name"),
            "auto_tier": route.get("auto_tier"),
            "auto_state": route.get("auto_state"),
            "sector": route.get("sector"),
            "instrument_type": route.get("instrument_type"),
            "monitor_grade": True,
            "decision_grade": False,
            "data_date": tech.get("data_date") or fb.get("source_timestamp"),
            "technical_input_status": tech.get("status"),
            "latest_price": band["latest_price"],
            "reference_band_low": band["reference_band_low"],
            "reference_band_high": band["reference_band_high"],
            "coarse_reference_stop": band["coarse_reference_stop"],
            "band_status": band["band_status"],
            "distance_to_band_pct": band["distance_to_band_pct"],
            "trend_stack": band["trend_stack"],
            "confidence": band["confidence"],
            "reference_source": band["reference_source"],
            "warnings": band["warnings"],
            "authority": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        })

    status_counts = Counter(row["band_status"] for row in rows)
    input_counts = Counter(row["technical_input_status"] for row in rows)
    confidence_counts = Counter(str(row["confidence"]) for row in rows)
    errors: list[str] = []
    warnings = list(provider_warnings)
    if not rows:
        errors.append("no Tier C rows found in WF78 auto-tier routing")
    if not args.limit and len(rows) not in {157, 168}:
        warnings.append(f"Tier C row count is {len(rows)}; expected current router/SQL range 157-168")
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if any(
        row["authority"]["capital_deployment_approved"]
        or row["authority"]["trade_or_execution_approved"]
        or row["authority"]["paper_or_live_execution_allowed"]
        or row["authority"]["owner_approval_inferred"]
        for row in rows
    ):
        errors.append("row authority boundary widened")

    known = sum(1 for row in rows if row["band_status"] not in {"UNKNOWN", "STALE"})
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Monitor-grade Tier C band-status and coarse stop surface for WF78 triage.",
        "engine_version": ENGINE_VERSION,
        "parameters": {
            "skip_provider_refresh": bool(args.skip_provider_refresh),
            "period": args.period,
            "interval": args.interval,
            "limit": args.limit,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(AUTO_ROUTER), rel(STATE_DB)],
        "summary": {
            "tier_c_count": len(rows),
            "known_band_status_count": known,
            "unknown_or_stale_count": len(rows) - known,
            "status_counts": dict(status_counts.most_common()),
            "technical_input_status_counts": dict(input_counts.most_common()),
            "confidence_counts": dict(confidence_counts.most_common()),
            "monitor_grade_only": True,
            "decision_grade_entry_stop_allowed": False,
            "next_safe_action": "Use as Tier C triage only; promote selected names before decision-grade band/stop/sizing repair.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Monitor-grade reference bands/stops are not deployable written entry bands.",
            "No canon, portfolio, deployment, sizing, cash, trade, paper/live, brokerage, account, or owner-approval authority.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build monitor-grade Tier C band-status artifact.")
    parser.add_argument("--skip-provider-refresh", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--period", default="260d")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"tier_c={report['summary']['tier_c_count']} known={report['summary']['known_band_status_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
