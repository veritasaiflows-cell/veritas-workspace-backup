#!/usr/bin/env python3
"""Write the WF86 shadow decision ledger without execution authority.

This script records what the paper autotrader would do from the current
shadow-eligibility packet. It does not submit, cancel, sell, create a kill
switch, call brokerage endpoints, or infer owner approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_ELIGIBILITY = TMP / "paper-autotrader" / "shadow-eligibility.json"
DEFAULT_OUT = TMP / "paper-autotrader" / "shadow-decisions.json"
SCHEMA = "veritas.wf86_shadow_decision_ledger.v1"
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "shadow_mode_only": True,
    "paper_only_design": True,
    "autonomous_paper_execution_allowed_now": False,
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_utc(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def market_session(generated_at_utc: str) -> dict[str, Any]:
    dt = parse_utc(generated_at_utc).astimezone(EASTERN)
    open_dt = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    close_dt = dt.replace(hour=16, minute=0, second=0, microsecond=0)
    regular = dt.weekday() < 5 and open_dt <= dt < close_dt
    return {
        "market_date": dt.date().isoformat(),
        "regular_market_hours": regular,
        "session_state": "regular_market_hours" if regular else "outside_regular_market_hours",
    }


def session_key(generated_at_utc: str) -> str:
    session = market_session(generated_at_utc)
    suffix = "main-session-shadow" if session["regular_market_hours"] else "outside-regular-market-hours-shadow"
    return f"{session['market_date']}:{suffix}"


def decision_id(session: str, ticker: str, action: str) -> str:
    slug = action.replace("_", "-")
    return f"wf86-shadow-{session}-{ticker.lower()}-{slug}"


def build_decision(session: str, row: dict[str, Any], eligibility_path: Path, source_generated_at: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    action = str(row.get("shadow_decision") or "unknown")
    generated_at = utc_now()
    market = market_session(source_generated_at)
    threshold_accrual = session.endswith(":main-session-shadow") and market["regular_market_hours"]
    return {
        "decision_id": decision_id(session, ticker, action),
        "session_key": session,
        "generated_at_utc": generated_at,
        "source_generated_at_utc": source_generated_at,
        "market_session": market,
        "threshold_accrual_eligible": threshold_accrual,
        "ticker": ticker,
        "shadow_decision": action,
        "shadow_eligible": bool(row.get("shadow_eligible")),
        "execution_ready": False,
        "assisted_review_ready": bool(row.get("assisted_review_ready")),
        "max_shadow_notional_usd": row.get("max_shadow_notional_usd"),
        "current_price": row.get("current_price"),
        "current_band_status": row.get("current_band_status"),
        "written_band": row.get("written_band"),
        "factory_disposition": row.get("factory_disposition"),
        "wf67_request_generation_status": row.get("wf67_request_generation_status"),
        "shadow_blockers": as_list(row.get("shadow_blockers")),
        "root_cause_blockers": as_list(row.get("root_cause_blockers")),
        "plain_english_blockers": as_list(row.get("plain_english_blockers")),
        "assisted_review_blockers": as_list(row.get("assisted_review_blockers")),
        "execution_blockers": as_list(row.get("execution_blockers")),
        "source_artifact": rel(eligibility_path),
        "outcome": {
            "tracked": False,
            "status": "pending_future_session",
            "fill_or_order_id": None,
            "paper_position_after": None,
            "notes": "Shadow ledger only. No order submitted.",
        },
        "authority": {
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def merge_existing(existing: dict[str, Any], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    legacy_by_decision_id: dict[str, str] = {}
    for row in as_list(existing.get("decisions")):
        row_dict = as_dict(row)
        key = decision_merge_key(row_dict)
        if key:
            merged[key] = row_dict
            legacy_id = str(row_dict.get("decision_id") or "")
            if legacy_id:
                legacy_by_decision_id[legacy_id] = key
    for row in new_rows:
        key = decision_merge_key(row)
        legacy_key = legacy_by_decision_id.get(str(row.get("decision_id") or ""))
        merged[legacy_key or key] = row
    return list(merged.values())


def decision_merge_key(row: dict[str, Any]) -> str:
    """Return the durable threshold-count key: one ticker per session."""
    session = str(row.get("session_key") or "").strip()
    symbol = str(row.get("ticker") or "").strip().upper()
    if session and symbol:
        return f"{session}:{symbol}"
    return str(row.get("decision_id") or "")


def threshold_accrual_eligible(row: dict[str, Any]) -> bool:
    if row.get("threshold_accrual_eligible") is False:
        return False
    if row.get("threshold_accrual_eligible") is True:
        return True
    session = str(row.get("session_key") or "")
    if not session.endswith(":main-session-shadow"):
        return False
    generated_at = str(row.get("source_generated_at_utc") or "")
    if not generated_at:
        return True
    return bool(market_session(generated_at).get("regular_market_hours"))


def build_report(eligibility_path: Path, out_path: Path) -> dict[str, Any]:
    eligibility = load_dict(eligibility_path)
    existing = load_dict(out_path) if out_path.exists() else {}
    generated_at = str(eligibility.get("generated_at_utc") or utc_now())
    session = session_key(generated_at)
    current_rows = [
        build_decision(session, as_dict(row), eligibility_path, generated_at)
        for row in as_list(eligibility.get("decisions"))
        if as_dict(row).get("ticker")
    ]
    decisions = merge_existing(existing, current_rows)
    clean_decisions_all = [
        row for row in decisions
        if row.get("shadow_eligible") is True
        and row.get("shadow_decision") in {"would_buy_shadow", "would_sell_shadow", "no_action_wait_for_band", "repair_only_shadow", "repair_only_below_stop"}
        and row.get("execution_ready") is False
        and as_dict(row.get("authority")).get("owner_approval_inferred") is False
    ]
    clean_decisions = [row for row in clean_decisions_all if threshold_accrual_eligible(row)]
    non_accrual_clean_decisions = [row for row in clean_decisions_all if not threshold_accrual_eligible(row)]
    unique_sessions = sorted({str(row.get("session_key")) for row in clean_decisions if row.get("session_key")})
    would_buy = [row for row in decisions if row.get("shadow_decision") == "would_buy_shadow"]

    errors: list[str] = []
    warnings: list[str] = []
    if eligibility.get("status") not in {"ok", "warning"}:
        errors.append(f"eligibility_status_not_ok:{eligibility.get('status')}")
    if not current_rows:
        warnings.append("no_current_shadow_decisions")
    if any(row.get("execution_ready") for row in decisions):
        errors.append("ledger_execution_ready_must_remain_false")
    for key, expected in AUTHORITY_BOUNDARY.items():
        if AUTHORITY_BOUNDARY[key] is not expected:
            errors.append(f"authority_boundary_invalid:{key}")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow_id": "WF86",
        "purpose": "Append-only proof surface for shadow paper-autotrader decisions before assisted or autonomous paper execution.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "decision_count": len(decisions),
            "current_session_decision_count": len(current_rows),
            "clean_shadow_decision_count": len(clean_decisions),
            "non_accrual_clean_shadow_decision_count": len(non_accrual_clean_decisions),
            "unique_clean_market_sessions": len(unique_sessions),
            "required_clean_market_sessions": 5,
            "required_clean_decisions": 20,
            "would_buy_shadow_count": len(would_buy),
            "would_buy_shadow_tickers": [row.get("ticker") for row in would_buy],
            "shadow_threshold_met": len(unique_sessions) >= 5 and len(clean_decisions) >= 20,
            "execution_ready_count": 0,
            "next_safe_action": "Continue shadow logging and build assisted-mode request proof; do not execute orders.",
        },
        "decisions": decisions,
        "source_artifacts": [
            rel(eligibility_path),
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "Shadow decision ledger is not approval.",
            "No paper submit/cancel/sell from this script.",
            "No live endpoint, account action, money movement, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eligibility", type=Path, default=DEFAULT_ELIGIBILITY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    eligibility = resolve(args.eligibility)
    out = resolve(args.out)
    report = build_report(eligibility, out)
    if args.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "summary": report["summary"],
        "validation": report["validation"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
