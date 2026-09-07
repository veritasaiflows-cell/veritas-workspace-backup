#!/usr/bin/env python3
"""Phase 6: review-only escalation trigger over the cron signal scorecard.

This reads the cron signal scorecard and decides whether a fresh urgent signal
(BLOCKED or OWNER_DECISION that has not decayed to stale) warrants waking the
main session. It emits a decision artifact only. It never sends messages, never
mutates cron/runtime/canon/portfolio/accounts, and never infers owner approval.
Message delivery is the responsibility of the cron agentTurn that reads this
artifact, not of this script.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import access as finance_sql_canon_access
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_SCORECARD = TMP / "cron-signal-scorecard.json"
DEFAULT_OUT = TMP / "escalation-trigger.json"

SCHEMA = "veritas.escalation_trigger.v1"
ESCALATION_CLASSES = {"BLOCKED", "OWNER_DECISION"}
AGGREGATE_OWNER_DECISION_SOURCES = {
    "operating_spine:heartbeat_continuation_candidates",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "sends_messages": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


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


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sql_canon_health() -> dict[str, Any]:
    try:
        validation = finance_sql_canon_access().validate()
    except Exception as exc:  # pragma: no cover - defensive escalation surface
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
        }
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def select_urgent(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    """Fresh urgent signals only: BLOCKED/OWNER_DECISION that still require
    attention. Phase 4 staleness decay already moves stale signals out of the
    requires_main_attention set, so this naturally ignores stale blockers'
    softer cousins while still surfacing genuine stop-line states."""
    urgent: list[dict[str, Any]] = []
    for signal in as_list(scorecard.get("signals")):
        if not isinstance(signal, dict):
            continue
        if signal.get("signal_class") not in ESCALATION_CLASSES:
            continue
        if signal.get("attention") != "requires_main_attention":
            continue
        if (
            signal.get("signal_class") == "OWNER_DECISION"
            and signal.get("source") in AGGREGATE_OWNER_DECISION_SOURCES
            and signal.get("reason") == "one_or_more_candidates_need_human_gate"
        ):
            continue
        urgent.append({
            "source": signal.get("source"),
            "signal_class": signal.get("signal_class"),
            "status": signal.get("status"),
            "reason": signal.get("reason"),
            "artifact": signal.get("artifact"),
            "age_hours": signal.get("age_hours"),
            "next_action": signal.get("next_action") or "",
            "last_error": signal.get("live_scheduler_last_error"),
        })
    return urgent


def compose_message(urgent: list[dict[str, Any]]) -> str:
    if not urgent:
        return ""
    lines = [f"Veritas escalation: {len(urgent)} fresh signal(s) need a decision."]
    for item in urgent:
        cls = item.get("signal_class")
        src = item.get("source")
        reason = item.get("reason") or item.get("status") or ""
        nxt = item.get("next_action")
        line = f"- [{cls}] {src}: {reason}".rstrip(": ")
        err = item.get("last_error")
        if err:
            line += f" | error: {err}"
        if nxt:
            line += f" -> {nxt}"
        lines.append(line)
    return "\n".join(lines)


def build_payload(scorecard_path: Path) -> dict[str, Any]:
    scorecard = load_json(scorecard_path)
    scorecard_present = bool(scorecard)
    urgent = select_urgent(scorecard)
    sql_health = sql_canon_health()
    if sql_health.get("status") != "ok" and not any(item.get("source") == "sql_canon:finance_sql_canon_access" for item in urgent):
        urgent.append({
            "source": "sql_canon:finance_sql_canon_access",
            "signal_class": "BLOCKED",
            "status": sql_health.get("status"),
            "reason": "finance_sql_canon_guard_blocked",
            "artifact": "scripts/finance_sql_canon_access.py",
            "age_hours": 0,
            "next_action": "Run python scripts\\finance_sql_canon_access.py --write --validate and repair the SQL-canon guard before treating cron/PM readiness as clean.",
        })
    should_wake = bool(urgent)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {
            "cron_signal_scorecard": rel(scorecard_path),
            "cron_freshness_spine": as_dict(scorecard.get("sources")).get("cron_freshness_spine"),
            "finance_sql_canon_access": "scripts/finance_sql_canon_access.py",
            "scorecard_source_mode": as_dict(scorecard.get("sources")).get("source_mode"),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_health": sql_health,
        "scorecard_present": scorecard_present,
        "scorecard_generated_at_utc": scorecard.get("generated_at_utc"),
        "should_wake_main_session": should_wake,
        "escalation_signal_count": len(urgent),
        "escalation_signals": urgent,
        "suppression_rule": (
            "Generic aggregate heartbeat OWNER_DECISION signals are kept in the scorecard for on-route review "
            "but do not wake main by themselves; concrete BLOCKED signals and specific OWNER_DECISION sources still escalate."
        ),
        "escalation_message": compose_message(urgent),
        "delivery_rule": (
            "The cron agentTurn that reads this artifact should message Randall only when "
            "should_wake_main_session is true; otherwise reply NO_REPLY. This script sends nothing."
        ),
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if not payload.get("scorecard_present"):
        warnings.append("scorecard_missing_or_unparseable")
    should_wake = payload.get("should_wake_main_session")
    count = payload.get("escalation_signal_count")
    if bool(should_wake) != bool(count):
        errors.append("should_wake_inconsistent_with_signal_count")
    for item in as_list(payload.get("escalation_signals")):
        if as_dict(item).get("signal_class") not in ESCALATION_CLASSES:
            errors.append(f"non_escalation_class_in_list:{as_dict(item).get('source')}")
    sql_health = as_dict(payload.get("sql_canon_health"))
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            errors.append(f"sql_canon_authority_{key}_not_false")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review-only escalation trigger over cron signal scorecard.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--scorecard", default=str(DEFAULT_SCORECARD))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(workspace_path(args.scorecard))
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "should_wake_main_session": payload.get("should_wake_main_session"),
        "escalation_signal_count": payload.get("escalation_signal_count"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
