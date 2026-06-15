#!/usr/bin/env python3
"""Build the WF87 approval and freshness TTL proof surface.

This validator is intentionally fail-closed. It checks owner approvals, quotes,
band/stop proof, WF67 guard proof, kill-switch proof, and reconciliation proof.
It never grants approval or execution authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf87-approval-freshness-ttl.json"
DEFAULT_APPROVAL = TMP / "paper-autotrader" / "autonomous-pilot-approval.json"
DEFAULT_QUOTE_LEDGER = TMP / "post-close-final-quote-ledger.json"
DEFAULT_BAND_GUARD = TMP / "tier-ab-band-freshness-cron-guard.json"
DEFAULT_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
DEFAULT_KILL_SWITCH = TMP / "alpaca-paper-readiness" / "kill-switch.json"
DEFAULT_RECONCILIATION = TMP / "alpaca-paper-readiness" / "paper-order-reconciliation.vrt-wf86-assisted-approved.json"

SCHEMA = "veritas.wf87_approval_freshness_ttl.v1"
PHOENIX = ZoneInfo("America/Phoenix")
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "wake_recommendation_only": True,
    "ttl_validator_only": True,
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
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError:
            return None
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_now(value: str | None) -> datetime:
    parsed = parse_dt(value) if value else None
    return parsed or datetime.now(timezone.utc).replace(microsecond=0)


def age_minutes(now: datetime, stamp: datetime | None) -> float | None:
    if stamp is None:
        return None
    return max((now - stamp).total_seconds() / 60.0, 0.0)


def market_session_date(now: datetime) -> str:
    local = now.astimezone(EASTERN)
    return local.date().isoformat()


def check_boundary_false(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = as_dict(report.get("authority_boundary"))
    for key in (
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "paper_submit_allowed",
        "paper_cancel_allowed",
        "paper_sell_allowed",
        "live_trade_allowed",
        "live_endpoint_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "portfolio_or_canon_mutation_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_not_false:{key}")
    return errors


def approval_checks(paths: list[Path], now: datetime, ttl_minutes: int) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not paths:
        blockers.append("missing_approval_artifact")
    for path in paths:
        payload = load_dict(path)
        stamp = parse_dt(payload.get("created_at_utc") or payload.get("generated_at_utc"))
        valid_statuses = {"approved_scoped_pilot", "approved_exact_order", "approved_final_submit"}
        status = payload.get("status") or payload.get("approval_status")
        approved_by = payload.get("approved_by")
        age = age_minutes(now, stamp)
        row_blockers: list[str] = []
        if not payload:
            row_blockers.append("missing")
        if approved_by != "Randall":
            row_blockers.append("not_randall_approval")
        if status not in valid_statuses:
            row_blockers.append(f"invalid_approval_status:{status}")
        if age is None:
            row_blockers.append("missing_approval_timestamp")
        elif age > ttl_minutes:
            row_blockers.append("approval_expired")
        boundary = as_dict(payload.get("authority_boundary"))
        if boundary.get("owner_approval_inferred") is not False:
            row_blockers.append("approval_boundary_owner_inference_not_false")
        rows.append({
            "path": rel(path),
            "present": bool(payload),
            "status": status,
            "approved_by": approved_by,
            "timestamp_utc": stamp.isoformat().replace("+00:00", "Z") if stamp else None,
            "age_minutes": round(age, 2) if age is not None else None,
            "ttl_minutes": ttl_minutes,
            "fresh": not row_blockers,
            "blockers": row_blockers,
        })
        blockers.extend(f"approval:{path.name}:{item}" for item in row_blockers)
    return rows, blockers


def quote_checks(quote_ledger: dict[str, Any], now: datetime, ttl_minutes: int) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    rows = [as_dict(row) for row in as_list(quote_ledger.get("rows"))]
    generated = parse_dt(quote_ledger.get("generated_at_utc"))
    stale_rows: list[dict[str, Any]] = []
    if not quote_ledger:
        blockers.append("missing_quote_ledger")
    if quote_ledger.get("status") != "ok":
        blockers.append(f"quote_ledger_status_not_ok:{quote_ledger.get('status')}")
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        stamp = parse_dt(row.get("retrieved_at_utc") or quote_ledger.get("generated_at_utc"))
        row_age = age_minutes(now, stamp)
        if row.get("status") != "ok" or row.get("close") is None:
            stale_rows.append({"ticker": ticker, "reason": "quote_missing_or_not_ok"})
        elif row_age is None or row_age > ttl_minutes:
            stale_rows.append({"ticker": ticker, "reason": "quote_expired", "age_minutes": round(row_age or 0, 2)})
    if not rows:
        blockers.append("no_quote_rows")
    if stale_rows:
        blockers.append("expired_or_missing_quote_rows")
    ledger_age = age_minutes(now, generated)
    return {
        "status": quote_ledger.get("status"),
        "path_rows": len(rows),
        "generated_at_utc": quote_ledger.get("generated_at_utc"),
        "age_minutes": round(ledger_age, 2) if ledger_age is not None else None,
        "ttl_minutes": ttl_minutes,
        "stale_or_missing_rows": stale_rows,
        "fresh": bool(rows) and not stale_rows and quote_ledger.get("status") == "ok",
    }, blockers


def band_stop_checks(band_guard: dict[str, Any], now: datetime, ttl_hours: int) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    rows = [as_dict(row) for row in as_list(band_guard.get("rows"))]
    session = market_session_date(now)
    stale_rows: list[dict[str, Any]] = []
    missing_stop_rows: list[str] = []
    missing_band_rows: list[str] = []
    absent_same_session_stops: list[str] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        band_stamp = parse_dt(row.get("band_source_timestamp") or row.get("market_date"))
        stop_stamp = parse_dt(row.get("stop_source_timestamp") or row.get("market_date"))
        band_age_hours = None if band_stamp is None else age_minutes(now, band_stamp) / 60.0
        stop_age_hours = None if stop_stamp is None else age_minutes(now, stop_stamp) / 60.0
        if row.get("entry_band_low_present") is not True or row.get("entry_band_high_present") is not True:
            missing_band_rows.append(ticker)
        if row.get("stop_or_invalidation_present") is not True:
            missing_stop_rows.append(ticker)
        if band_age_hours is None or stop_age_hours is None or band_age_hours > ttl_hours or stop_age_hours > ttl_hours:
            stale_rows.append({
                "ticker": ticker,
                "band_age_hours": round(band_age_hours, 2) if band_age_hours is not None else None,
                "stop_age_hours": round(stop_age_hours, 2) if stop_age_hours is not None else None,
            })
        if str(row.get("stop_source_timestamp") or row.get("market_date") or "")[:10] != session:
            absent_same_session_stops.append(ticker)
    if not band_guard:
        blockers.append("missing_band_stop_guard")
    if band_guard.get("status") != "ok":
        blockers.append(f"band_stop_guard_status_not_ok:{band_guard.get('status')}")
    if not rows:
        blockers.append("no_band_stop_rows")
    if missing_band_rows:
        blockers.append("missing_band_rows")
    if missing_stop_rows:
        blockers.append("missing_stop_rows")
    if stale_rows:
        blockers.append("stale_band_or_stop_rows")
    if absent_same_session_stops:
        blockers.append("same_session_stop_absent")
    return {
        "status": band_guard.get("status"),
        "row_count": len(rows),
        "ttl_hours": ttl_hours,
        "required_same_session_market_date": session,
        "missing_band_tickers": missing_band_rows,
        "missing_stop_tickers": missing_stop_rows,
        "stale_rows": stale_rows,
        "same_session_stop_absent_tickers": absent_same_session_stops,
        "fresh": bool(rows) and not missing_band_rows and not missing_stop_rows and not stale_rows and not absent_same_session_stops and band_guard.get("status") == "ok",
    }, blockers


def proof_check(name: str, payload: dict[str, Any], now: datetime, ttl_minutes: int, *, ok_fields: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    stamp = parse_dt(payload.get("generated_at_utc") or as_dict(payload.get("freshness")).get("generated_at_utc"))
    age = age_minutes(now, stamp)
    row_blockers: list[str] = []
    if not payload:
        row_blockers.append(f"missing_{name}_proof")
    if payload.get("status") not in {"ok", "submitted"}:
        row_blockers.append(f"{name}_status_not_ok:{payload.get('status')}")
    if age is None:
        row_blockers.append(f"missing_{name}_timestamp")
    elif age > ttl_minutes:
        row_blockers.append(f"{name}_expired")
    for field, expected in (ok_fields or {}).items():
        if payload.get(field) is not expected:
            row_blockers.append(f"{name}_{field}_not_{expected}")
    blockers.extend(row_blockers)
    return {
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "age_minutes": round(age, 2) if age is not None else None,
        "ttl_minutes": ttl_minutes,
        "fresh": not row_blockers,
        "blockers": row_blockers,
    }, blockers


def kill_switch_check(payload: dict[str, Any], now: datetime) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    expires = parse_dt(payload.get("expires_at_utc"))
    generated = parse_dt(payload.get("generated_at_utc"))
    expired = expires is None or now > expires
    if not payload:
        blockers.append("missing_kill_switch")
    if payload.get("paper_only") is not True:
        blockers.append("kill_switch_not_paper_only")
    if payload.get("live_endpoint_forbidden") is not True:
        blockers.append("kill_switch_live_endpoint_not_forbidden")
    if expired:
        blockers.append("kill_switch_expired")
    if payload.get("no_inferred_approval") is not True:
        blockers.append("kill_switch_no_inferred_approval_not_true")
    return {
        "generated_at_utc": payload.get("generated_at_utc"),
        "expires_at_utc": payload.get("expires_at_utc"),
        "age_minutes": round(age_minutes(now, generated) or 0, 2) if generated else None,
        "fresh": not blockers,
        "blockers": blockers,
    }, blockers


def build_report(
    *,
    now: datetime | None = None,
    approval_paths: list[Path] | None = None,
    quote_ledger_path: Path = DEFAULT_QUOTE_LEDGER,
    band_guard_path: Path = DEFAULT_BAND_GUARD,
    guard_path: Path = DEFAULT_GUARD,
    kill_switch_path: Path = DEFAULT_KILL_SWITCH,
    reconciliation_path: Path = DEFAULT_RECONCILIATION,
    approval_ttl_minutes: int = 390,
    quote_ttl_minutes: int = 60,
    band_stop_ttl_hours: int = 36,
    guard_ttl_minutes: int = 90,
    reconciliation_ttl_minutes: int = 480,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    approval_paths = approval_paths if approval_paths is not None else [DEFAULT_APPROVAL]
    approvals, approval_blockers = approval_checks([resolve(path) for path in approval_paths], now, approval_ttl_minutes)
    quotes, quote_blockers = quote_checks(load_dict(resolve(quote_ledger_path)), now, quote_ttl_minutes)
    bands, band_blockers = band_stop_checks(load_dict(resolve(band_guard_path)), now, band_stop_ttl_hours)
    guard, guard_blockers = proof_check(
        "guard",
        load_dict(resolve(guard_path)),
        now,
        guard_ttl_minutes,
        ok_fields={"ready_for_paper_submit_cancel": True, "live_trading_allowed": False, "money_movement_allowed": False},
    )
    kill_switch, kill_blockers = kill_switch_check(load_dict(resolve(kill_switch_path)), now)
    reconciliation, reconciliation_blockers = proof_check(
        "reconciliation",
        load_dict(resolve(reconciliation_path)),
        now,
        reconciliation_ttl_minutes,
        ok_fields={"trade_or_account_action_allowed": False, "paper_submit_allowed": False, "paper_cancel_allowed": False},
    )
    blockers = approval_blockers + quote_blockers + band_blockers + guard_blockers + kill_blockers + reconciliation_blockers
    validation_errors = check_boundary_false({"authority_boundary": AUTHORITY_BOUNDARY})
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "workflow_id": "WF87",
        "status": "ok" if not blockers else "blocked",
        "purpose": "Fail-closed approval/freshness TTL proof for WF87/WF86 paper-autotrader readiness.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "thresholds": {
            "approval_ttl_minutes": approval_ttl_minutes,
            "quote_ttl_minutes": quote_ttl_minutes,
            "band_stop_ttl_hours": band_stop_ttl_hours,
            "guard_ttl_minutes": guard_ttl_minutes,
            "reconciliation_ttl_minutes": reconciliation_ttl_minutes,
        },
        "checks": {
            "approvals": approvals,
            "quotes": quotes,
            "bands_and_stops": bands,
            "guard": guard,
            "kill_switch": kill_switch,
            "reconciliation": reconciliation,
        },
        "blockers": blockers,
        "validation": {
            "status": "ok" if not validation_errors else "error",
            "errors": validation_errors,
            "warnings": blockers,
        },
        "next_safe_action": "Blocked proof requires fresh source refresh and main-session review; this artifact cannot execute or infer approval.",
        "stop_lines": [
            "Expired or missing approval, quote, band, stop, guard, kill-switch, or reconciliation proof blocks automatically.",
            "No paper/live execution authority is granted by this TTL validator.",
            "No owner approval inference.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", action="append", type=Path, dest="approvals")
    parser.add_argument("--quote-ledger", type=Path, default=DEFAULT_QUOTE_LEDGER)
    parser.add_argument("--band-guard", type=Path, default=DEFAULT_BAND_GUARD)
    parser.add_argument("--guard", type=Path, default=DEFAULT_GUARD)
    parser.add_argument("--kill-switch", type=Path, default=DEFAULT_KILL_SWITCH)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--now-utc")
    parser.add_argument("--approval-ttl-minutes", type=int, default=390)
    parser.add_argument("--quote-ttl-minutes", type=int, default=60)
    parser.add_argument("--band-stop-ttl-hours", type=int, default=36)
    parser.add_argument("--guard-ttl-minutes", type=int, default=90)
    parser.add_argument("--reconciliation-ttl-minutes", type=int, default=480)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    report = build_report(
        now=parse_now(args.now_utc),
        approval_paths=args.approvals,
        quote_ledger_path=args.quote_ledger,
        band_guard_path=args.band_guard,
        guard_path=args.guard,
        kill_switch_path=args.kill_switch,
        reconciliation_path=args.reconciliation,
        approval_ttl_minutes=args.approval_ttl_minutes,
        quote_ttl_minutes=args.quote_ttl_minutes,
        band_stop_ttl_hours=args.band_stop_ttl_hours,
        guard_ttl_minutes=args.guard_ttl_minutes,
        reconciliation_ttl_minutes=args.reconciliation_ttl_minutes,
    )
    out = resolve(args.out)
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "blockers": report["blockers"],
        "validation": report["validation"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
