#!/usr/bin/env python3
"""Build the WF87 assisted paper cadence proof.

This packet records Randall's approved assisted-paper cadence as policy only.
It does not approve any specific order and does not grant submit/cancel/sell
authority. Each assisted paper order still needs an exact WF67-gated approval
card at execution time.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf87-assisted-paper-cadence.json"

SCHEMA = "veritas.wf87_assisted_paper_cadence.v1"
EASTERN = ZoneInfo("America/New_York")

ORDER_HISTORY = TMP / "alpaca-paper-readiness" / "paper-order-history-classifier.json"
ASSISTED_CARDS = TMP / "paper-autotrader" / "assisted-order-cards.json"
WF67_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "paper_only_design": True,
    "assisted_cadence_policy_approved": True,
    "exact_order_approval_required_per_order": True,
    "cadence_approval_is_order_approval": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "paper_replace_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
    "paper_to_live_promotion_allowed": False,
}

FORBIDDEN_TRUE_KEYS = (
    "cadence_approval_is_order_approval",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_replace_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "owner_approval_inferred",
    "cron_direct_execution_allowed",
    "paper_to_live_promotion_allowed",
)

TERMINAL_CLASSIFICATIONS = {"filled", "expired", "canceled", "cancelled", "rejected"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def market_context(now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    et = current.astimezone(EASTERN)
    open_dt = datetime.combine(et.date(), time(9, 30), tzinfo=EASTERN)
    close_dt = datetime.combine(et.date(), time(16, 0), tzinfo=EASTERN)
    is_weekday = et.weekday() < 5
    is_regular = is_weekday and open_dt <= et < close_dt
    return {
        "now_utc": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "market_timezone": "America/New_York",
        "market_date": et.date().isoformat(),
        "regular_market_hours": is_regular,
        "session_state": "regular_market_hours" if is_regular else "outside_regular_market_hours",
    }


def monday_for(dt: datetime) -> str:
    et = dt.astimezone(EASTERN)
    monday = et.date()
    monday = monday.fromordinal(monday.toordinal() - et.weekday())
    return monday.isoformat()


def is_wf86_assisted(row: dict[str, Any]) -> bool:
    request = as_dict(row.get("request"))
    haystack = " ".join(
        str(item or "").lower()
        for item in (
            row.get("source_path"),
            request.get("path"),
            request.get("request_id"),
        )
    )
    return "wf86-assisted" in haystack


def assisted_reps(order_history: dict[str, Any], now: datetime) -> dict[str, Any]:
    rows = [row for row in as_list(order_history.get("classifications")) if isinstance(row, dict)]
    assisted = [row for row in rows if is_wf86_assisted(row)]
    current_week = monday_for(now)
    week_rows: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    for row in assisted:
        submitted_at = parse_utc(row.get("submitted_at_utc") or row.get("generated_at_utc"))
        classification = str(row.get("classification") or "").lower()
        request = as_dict(row.get("request"))
        normalized_row = {
            "symbol": row.get("symbol"),
            "side": row.get("side"),
            "classification": classification or None,
            "submitted_at_utc": submitted_at.replace(microsecond=0).isoformat().replace("+00:00", "Z") if submitted_at else None,
            "source_path": row.get("source_path"),
            "request_path": request.get("path"),
            "request_id": request.get("request_id"),
            "counts_as_assisted_attempt": True,
            "counts_as_terminal_attempt": classification in TERMINAL_CLASSIFICATIONS,
            "counts_as_filled_order": classification == "filled",
            "counts_as_assisted_maturity_rep": False,
            "counts_as_filled_round_trip": False,
        }
        normalized.append(normalized_row)
        if submitted_at and monday_for(submitted_at) == current_week:
            week_rows.append(normalized_row)
    terminal = [row for row in normalized if row["counts_as_terminal_attempt"]]
    filled_orders = [row for row in normalized if row["counts_as_filled_order"]]
    maturity_reps = [row for row in normalized if row["counts_as_assisted_maturity_rep"]]
    current_week_terminal = [row for row in week_rows if row["counts_as_terminal_attempt"]]
    current_week_filled_orders = [row for row in week_rows if row["counts_as_filled_order"]]
    current_week_maturity_reps = [row for row in week_rows if row["counts_as_assisted_maturity_rep"]]
    return {
        "all_time_wf86_assisted_attempt_count": len(normalized),
        "all_time_assisted_terminal_attempt_count": len(terminal),
        "all_time_assisted_filled_order_count": len(filled_orders),
        "all_time_assisted_maturity_rep_count": len(maturity_reps),
        "all_time_assisted_filled_round_trip_count": 0,
        "current_week_start_et": current_week,
        "current_week_wf86_assisted_attempt_count": len(week_rows),
        "current_week_assisted_terminal_attempt_count": len(current_week_terminal),
        "current_week_assisted_filled_order_count": len(current_week_filled_orders),
        "current_week_assisted_maturity_rep_count": len(current_week_maturity_reps),
        "current_week_assisted_filled_round_trip_count": 0,
        "current_week_rows": week_rows,
        "all_time_rows": normalized,
        "counting_note": (
            "WF86-assisted attempts and terminal attempts are telemetry only. "
            "Maturity credit requires filled round-trip proof and remains zero until proven."
        ),
    }


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    authority_paths = authority_true_paths(payload)
    if authority_paths:
        errors.append("authority_drift_detected")
    policy = as_dict(payload.get("cadence_policy"))
    if int(policy.get("target_assisted_attempts_per_week_min") or 0) < 1:
        errors.append("cadence_attempt_min_less_than_one")
    if int(policy.get("target_assisted_attempts_per_week_max") or 0) > 2:
        errors.append("cadence_attempt_max_above_owner_approved_range")
    if as_dict(payload.get("source_statuses")).get("order_history_status") != "ok":
        warnings.append("order_history_not_clean")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": authority_paths,
    }


def build_payload(paths: dict[str, Path], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    order_history = load_dict(paths["order_history"])
    assisted_cards = load_dict(paths["assisted_cards"])
    guard = load_dict(paths["wf67_guard"])
    market = market_context(current)
    reps = assisted_reps(order_history, current)

    min_attempts = 1
    max_attempts = 2
    current_attempts = int(reps["current_week_wf86_assisted_attempt_count"])
    current_maturity_reps = int(reps["current_week_assisted_maturity_rep_count"])
    if market["regular_market_hours"] and current_attempts < min_attempts:
        status = "candidate_review_window_open"
        next_action = "Build exact assisted-paper order card only if fresh WF67 gates and market evidence are clean."
    elif current_attempts >= min_attempts and current_maturity_reps == 0:
        status = "attempted_cadence_satisfied_maturity_blocked"
        next_action = "Analyze unfilled assisted attempts before preparing another exact owner-approved paper request."
    elif current_maturity_reps >= min_attempts:
        status = "filled_round_trip_maturity_present"
        next_action = "No automatic order action; next assisted rep still requires exact owner approval."
    else:
        status = "outside_fresh_gate_window"
        next_action = "Wait for a fresh regular-session gate window before preparing any assisted paper request."

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": status,
        "purpose": "Review-only cadence proof for Phase B assisted paper maturity reps.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "owner_policy_approval": {
            "approved": True,
            "source": "Randall WebChat approval, 2026-06-11 22:01 America/Phoenix",
            "scope": "1-2 small assisted paper maturity reps per week during fresh-gate windows.",
            "does_not_approve_any_specific_order": True,
            "exact_wf67_order_approval_required_each_time": True,
        },
        "cadence_policy": {
            "target_assisted_attempts_per_week_min": min_attempts,
            "target_assisted_attempts_per_week_max": max_attempts,
            "target_filled_round_trip_maturity_reps_per_week_min": 1,
            "expired_or_unfilled_attempts_count_as_maturity": False,
            "fresh_gate_window": "regular US market hours only after fresh WF67/TTL/band/stop/quote proof",
            "sizing_rule": "small assisted paper rep; exact notional/qty comes only from the approved card",
            "existing_wf86_pilot_cap_reference": "Tier A, 5000 USD max per approved card, 3/day remains a ceiling not a mandate",
        },
        "market_session": market,
        "assisted_maturity_reps": reps,
        "source_statuses": {
            "order_history_status": order_history.get("status"),
            "order_history_validation_status": as_dict(order_history.get("validation")).get("status"),
            "assisted_cards_status": assisted_cards.get("status"),
            "wf67_guard_status": guard.get("status"),
            "wf67_guard_validation_status": as_dict(guard.get("validation")).get("status"),
        },
        "next_safe_action": next_action,
        "stop_lines": [
            "Cadence approval is not order approval.",
            "Each assisted paper order still requires a fresh exact card, WF67 guard proof, kill switch, and Randall exact approval.",
            "No paper submit/cancel/sell, live endpoint, account action, money movement, or owner approval inference.",
        ],
        "source_artifacts": {key: rel(path) for key, path in paths.items()},
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order-history", type=Path, default=ORDER_HISTORY)
    parser.add_argument("--assisted-cards", type=Path, default=ASSISTED_CARDS)
    parser.add_argument("--wf67-guard", type=Path, default=WF67_GUARD)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "order_history": args.order_history if args.order_history.is_absolute() else ROOT / args.order_history,
        "assisted_cards": args.assisted_cards if args.assisted_cards.is_absolute() else ROOT / args.assisted_cards,
        "wf67_guard": args.wf67_guard if args.wf67_guard.is_absolute() else ROOT / args.wf67_guard,
    }
    payload = build_payload(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} current_week_reps={reps} out={out}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            reps=payload["assisted_maturity_reps"]["current_week_assisted_maturity_rep_count"],
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
