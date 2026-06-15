#!/usr/bin/env python3
"""Build the WF87 intraday monitor proof surface.

The monitor is market-hours review/wake infrastructure only. It can detect stop
breaches, fill drift, stale/anomalous proof, and recommend a main-session wake;
it cannot submit, cancel, sell, or approve orders.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf87-intraday-monitor.json"
DEFAULT_TTL = TMP / "wf87-approval-freshness-ttl.json"
DEFAULT_QUOTES = TMP / "post-close-final-quote-ledger.json"
DEFAULT_BANDS = TMP / "tier-ab-band-freshness-cron-guard.json"
DEFAULT_RECONCILIATION = TMP / "alpaca-paper-readiness" / "paper-order-reconciliation.vrt-wf86-assisted-approved.json"

SCHEMA = "veritas.wf87_intraday_monitor.v1"
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "wake_recommendation_only": True,
    "market_hours_monitor_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_now(value: str | None) -> datetime:
    parsed = parse_dt(value) if value else None
    return parsed or datetime.now(timezone.utc).replace(microsecond=0)


def market_hours_state(now: datetime) -> dict[str, Any]:
    local = now.astimezone(EASTERN)
    open_time = time(9, 30)
    close_time = time(16, 0)
    is_weekday = local.weekday() < 5
    in_regular = is_weekday and open_time <= local.time() <= close_time
    return {
        "timezone": "America/New_York",
        "local_time": local.replace(microsecond=0).isoformat(),
        "market_date": local.date().isoformat(),
        "regular_session": in_regular,
        "reason": "regular_market_hours" if in_regular else "outside_regular_market_hours",
        "window": "09:30-16:00 ET weekdays",
    }


def fnum(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def latest_quote_map(payload: dict[str, Any]) -> dict[str, float]:
    quotes: dict[str, float] = {}
    for row in as_list(payload.get("rows")):
        row_dict = as_dict(row)
        ticker = str(row_dict.get("ticker") or "").upper()
        close = fnum(row_dict.get("close") or row_dict.get("current_price") or row_dict.get("latest_price"))
        if ticker and close is not None and row_dict.get("status") in {None, "ok"}:
            quotes[ticker] = close
    return quotes


def stop_map(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    rows: dict[str, dict[str, Any]] = {}
    absent_same_session: list[str] = []
    market_date = as_dict(payload.get("summary")).get("expected_market_date")
    for row in as_list(payload.get("rows")):
        row_dict = as_dict(row)
        ticker = str(row_dict.get("ticker") or "").upper()
        if not ticker:
            continue
        rows[ticker] = row_dict
        if str(row_dict.get("stop_source_timestamp") or row_dict.get("market_date") or "")[:10] != str(market_date or "")[:10]:
            absent_same_session.append(ticker)
    return rows, absent_same_session


def stop_breaches(quotes: dict[str, float], bands: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    breaches: list[dict[str, Any]] = []
    for ticker, row in bands.items():
        price = quotes.get(ticker)
        stop = fnum(row.get("stop_or_invalidation") or row.get("stop") or row.get("current_stop"))
        if price is not None and stop is not None and price <= stop:
            breaches.append({
                "ticker": ticker,
                "price": price,
                "stop_or_invalidation": stop,
                "breach_pct": round((price - stop) / stop, 4) if stop else None,
                "action": "wake_main_session_for_review_only_stop_breach",
            })
    return breaches


def fill_drift(reconciliation: dict[str, Any], bands: dict[str, dict[str, Any]], threshold_pct: float) -> list[dict[str, Any]]:
    drift: list[dict[str, Any]] = []
    for row in as_list(reconciliation.get("positions")):
        pos = as_dict(row)
        ticker = str(pos.get("symbol") or "").upper()
        price = fnum(pos.get("current_price"))
        entry = fnum(pos.get("avg_entry_price"))
        stop = fnum(as_dict(bands.get(ticker)).get("stop_or_invalidation"))
        if not ticker or price is None:
            continue
        if entry and abs(price - entry) / entry >= threshold_pct:
            drift.append({
                "ticker": ticker,
                "kind": "entry_price_drift",
                "current_price": price,
                "avg_entry_price": entry,
                "drift_pct": round((price - entry) / entry, 4),
                "threshold_pct": threshold_pct,
            })
        if stop and price <= stop:
            drift.append({
                "ticker": ticker,
                "kind": "held_position_stop_breach",
                "current_price": price,
                "stop_or_invalidation": stop,
                "threshold_pct": threshold_pct,
            })
    return drift


def anomaly_halts(ttl: dict[str, Any], reconciliation: dict[str, Any], absent_same_session_stops: list[str]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    if ttl and ttl.get("status") != "ok":
        anomalies.append({
            "kind": "ttl_blocked",
            "blockers": as_list(ttl.get("blockers")),
            "action": "halt_review_queue_and_wake_main_session",
        })
    if absent_same_session_stops:
        anomalies.append({
            "kind": "same_session_stop_absent",
            "tickers": absent_same_session_stops,
            "action": "block_sell_gate_until_refreshed_stop_proof_exists",
        })
    freshness = as_dict(reconciliation.get("freshness"))
    if reconciliation.get("status") not in {"ok", None} or freshness.get("status") not in {"fresh", None}:
        anomalies.append({
            "kind": "reconciliation_not_fresh",
            "status": reconciliation.get("status"),
            "freshness_status": freshness.get("status"),
            "action": "wake_main_session_for_get_only_reconciliation_review",
        })
    return anomalies


def build_report(
    *,
    now: datetime | None = None,
    ttl_path: Path = DEFAULT_TTL,
    quotes_path: Path = DEFAULT_QUOTES,
    bands_path: Path = DEFAULT_BANDS,
    reconciliation_path: Path = DEFAULT_RECONCILIATION,
    fill_drift_threshold_pct: float = 0.05,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    hours = market_hours_state(now)
    ttl = load_dict(resolve(ttl_path))
    quotes_payload = load_dict(resolve(quotes_path))
    bands_payload = load_dict(resolve(bands_path))
    reconciliation = load_dict(resolve(reconciliation_path))
    quotes = latest_quote_map(quotes_payload)
    bands, absent_same_session = stop_map(bands_payload)
    breaches = stop_breaches(quotes, bands) if hours["regular_session"] else []
    drift = fill_drift(reconciliation, bands, fill_drift_threshold_pct) if hours["regular_session"] else []
    anomalies = anomaly_halts(ttl, reconciliation, absent_same_session)
    wake_reasons = []
    if hours["regular_session"] and breaches:
        wake_reasons.append("stop_breach_detected")
    if hours["regular_session"] and drift:
        wake_reasons.append("fill_drift_detected")
    if anomalies:
        wake_reasons.append("anomaly_halt")
    if not hours["regular_session"]:
        wake_reasons = ["outside_market_hours_review_only"] if anomalies else []
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "workflow_id": "WF87",
        "status": "wake_recommended" if wake_reasons else ("monitoring" if hours["regular_session"] else "market_closed"),
        "purpose": "Intraday review/wake monitor for stop breaches, fill drift, anomaly halt, and main-session attention.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "market_hours": hours,
        "signals": {
            "stop_breaches": breaches,
            "fill_drift": drift,
            "anomaly_halts": anomalies,
        },
        "main_session_wake": {
            "recommended": bool(wake_reasons),
            "reasons": wake_reasons,
            "message": "Wake main session for review only; do not execute from this monitor." if wake_reasons else "No wake needed from this proof surface.",
        },
        "same_session_stop_wiring": {
            "source": rel(resolve(bands_path)),
            "absent_tickers": absent_same_session,
            "blocked": bool(absent_same_session),
        },
        "source_artifacts": [
            rel(resolve(ttl_path)),
            rel(resolve(quotes_path)),
            rel(resolve(bands_path)),
            rel(resolve(reconciliation_path)),
        ],
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
        },
        "stop_lines": [
            "Monitor is review/wake only.",
            "No submit, cancel, sell, account action, money movement, live endpoint, or owner approval inference.",
            "Same-session stop absence blocks sell-gate review until refreshed proof exists.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttl", type=Path, default=DEFAULT_TTL)
    parser.add_argument("--quotes", type=Path, default=DEFAULT_QUOTES)
    parser.add_argument("--bands", type=Path, default=DEFAULT_BANDS)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--now-utc")
    parser.add_argument("--fill-drift-threshold-pct", type=float, default=0.05)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    report = build_report(
        now=parse_now(args.now_utc),
        ttl_path=args.ttl,
        quotes_path=args.quotes,
        bands_path=args.bands,
        reconciliation_path=args.reconciliation,
        fill_drift_threshold_pct=args.fill_drift_threshold_pct,
    )
    out = resolve(args.out)
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "main_session_wake": report["main_session_wake"],
        "market_hours": report["market_hours"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
