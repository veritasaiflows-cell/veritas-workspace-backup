#!/usr/bin/env python3
"""Build a compact startup brief from existing route packets.

This is a fast read-only pickup surface for simple greetings and status checks.
It avoids regenerating PM/cron/control packets unless the operator explicitly
asks elsewhere; generated packets remain routing proof, not canon or approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "startup-brief-packet.json"
SCHEMA = "veritas.startup_brief_packet.v1"

FUTURE_PACKET = TMP / "future-session-enhancement-packet.json"
PM_PACKET = TMP / "pm-control-packet.json"
CRON_PACKET = TMP / "cron-control-packet.json"
IMPROVEMENT_PACKET = TMP / "improvement-ledger-current.json"
TOKEN_USAGE_PACKET = TMP / "token-usage-ledger-current.json"
OWNER_GATED_PACKET = TMP / "owner-gated-action-review-queue.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routes_existing_packets_only": True,
    "regenerates_control_packets": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def artifact_age_seconds(path: Path, now: datetime) -> float | None:
    if not path.exists():
        return None
    return max(0.0, now.timestamp() - path.stat().st_mtime)


def path_state(path: Path, now: datetime) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.exists(),
        "age_seconds": artifact_age_seconds(path, now),
    }


def first_workflow(future_packet: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    for row in future_packet.get("workflow_capsules") or []:
        if isinstance(row, dict) and row.get("workflow_id") == workflow_id:
            return row
    return {}


def build_payload(max_age_minutes: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    future = load(FUTURE_PACKET)
    pm = load(PM_PACKET)
    cron = load(CRON_PACKET)
    improvement = load(IMPROVEMENT_PACKET)
    token_usage = load(TOKEN_USAGE_PACKET)
    owner_gated = load(OWNER_GATED_PACKET)
    pm_summary = as_dict(pm.get("summary"))
    cron_summary = as_dict(cron.get("summary"))
    improvement_summary = as_dict(improvement.get("summary"))
    token_summary = as_dict(token_usage.get("summary"))
    owner_gated_summary = as_dict(owner_gated.get("summary"))
    finance_digest = as_dict(pm_summary.get("finance_domain_repair_digest"))
    implementation_queue = as_dict(pm_summary.get("implementation_queue"))
    pm_readiness = as_dict(pm_summary.get("pm_readiness"))
    wf85 = first_workflow(future, "WF85")
    wf84 = first_workflow(future, "WF84")
    artifacts = {
        "future_session_packet": path_state(FUTURE_PACKET, now),
        "pm_control_packet": path_state(PM_PACKET, now),
        "cron_control_packet": path_state(CRON_PACKET, now),
        "improvement_ledger_packet": path_state(IMPROVEMENT_PACKET, now),
        "token_usage_ledger_packet": path_state(TOKEN_USAGE_PACKET, now),
        "owner_gated_action_review_queue": path_state(OWNER_GATED_PACKET, now),
    }
    stale = [
        key
        for key, state in artifacts.items()
        if state.get("age_seconds") is None or state.get("age_seconds", 0) > max_age_minutes * 60
    ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not stale else "stale_input_warning",
        "purpose": "Fast startup/status brief from existing route packets.",
        "max_age_minutes": max_age_minutes,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "inputs": artifacts,
        "summary": {
            "identity": "Veritas, Randall's finance-first market-intelligence chief of staff and workflow/decision-support operator.",
            "primary_goal": "WF85 Personal Trade-Grade Decision OS",
            "wf85_status": wf85.get("effective_status"),
            "wf84_status": wf84.get("effective_status"),
            "pm_status": pm.get("status"),
            "pm_readiness_band": pm_readiness.get("readiness_band"),
            "pm_ready_job_count": implementation_queue.get("ready_job_count"),
            "pm_blocked_job_count": implementation_queue.get("blocked_job_count"),
            "cron_status": cron.get("status"),
            "cron_escalation_signal_count": cron_summary.get("escalation_signal_count"),
            "cron_blocked_count": cron_summary.get("blocked_count"),
            "improvement_ledger_status": improvement.get("status"),
            "improvement_open_count": improvement_summary.get("latest_open_count"),
            "improvement_high_priority_open_count": improvement_summary.get("high_priority_open_count"),
            "improvement_overdue_open_count": improvement_summary.get("overdue_open_count"),
            "improvement_due_soon_open_count": improvement_summary.get("due_soon_open_count"),
            "improvement_high_priority_overdue_open_count": improvement_summary.get("high_priority_overdue_open_count"),
            "improvement_escalation_level": improvement_summary.get("escalation_level"),
            "improvement_top_title": improvement_summary.get("top_improvement_title"),
            "improvement_top_next_action": improvement_summary.get("top_improvement_next_action"),
            "improvement_top_age_hours": improvement_summary.get("top_improvement_age_hours"),
            "improvement_top_sla_status": improvement_summary.get("top_improvement_sla_status"),
            "token_usage_status": token_usage.get("status"),
            "token_usage_event_count": token_summary.get("token_event_count"),
            "token_usage_total_tokens": token_summary.get("total_tokens"),
            "token_usage_cron_event_count": token_summary.get("cron_token_event_count"),
            "token_usage_implementation_event_count": token_summary.get("implementation_token_event_count"),
            "token_usage_implementation_gap_count": token_summary.get("implementation_token_gap_count"),
            "token_usage_pricing_status": token_summary.get("pricing_status"),
            "owner_gated_review_status": owner_gated.get("status"),
            "owner_gated_item_count": owner_gated_summary.get("item_count"),
            "owner_gated_decision_required_count": owner_gated_summary.get("owner_decision_required_count"),
            "owner_gated_top_gate": owner_gated_summary.get("top_gate"),
            "owner_gated_top_title": owner_gated_summary.get("top_title"),
            "owner_gated_next_safe_action": owner_gated_summary.get("next_safe_action"),
            "implementation_blocker_count": finance_digest.get("implementation_blocker_count"),
            "control_plane_blocker_count": finance_digest.get("control_plane_blocker_count"),
            "finance_domain_repair_item_count": finance_digest.get("finance_domain_repair_item_count"),
            "tier_a_b_missing_decision_grade_band_count": finance_digest.get("tier_a_b_missing_decision_grade_band_count"),
            "tier_a_b_missing_decision_grade_band_tickers": finance_digest.get("tier_a_b_missing_decision_grade_band_tickers"),
        },
        "recommended_next_action": (
            "If this is a simple greeting, answer from this packet. "
            "Refresh PM/cron/future-session packets only when stale inputs, a material status question, or a workflow action requires live proof."
        ),
        "stale_inputs": stale,
        "validation": validate(AUTHORITY_BOUNDARY),
    }
    if payload["validation"]["status"] != "ok":
        payload["status"] = "critical"
    return payload


def validate(boundary: dict[str, Any]) -> dict[str, Any]:
    errors = [
        key for key, expected in AUTHORITY_BOUNDARY.items()
        if boundary.get(key) is not expected
    ]
    return {"status": "critical" if errors else "ok", "errors": errors}


def render_text(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    missing = summary.get("tier_a_b_missing_decision_grade_band_tickers") or []
    return "\n".join([
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')}",
        f"primary={summary.get('primary_goal')} wf85={summary.get('wf85_status')} wf84={summary.get('wf84_status')}",
        f"pm={summary.get('pm_status')} readiness={summary.get('pm_readiness_band')} ready_jobs={summary.get('pm_ready_job_count')} blocked_jobs={summary.get('pm_blocked_job_count')}",
        f"cron={summary.get('cron_status')} escalation={summary.get('cron_escalation_signal_count')} blocked={summary.get('cron_blocked_count')}",
        f"improvements={summary.get('improvement_ledger_status')} open={summary.get('improvement_open_count')} high={summary.get('improvement_high_priority_open_count')} overdue={summary.get('improvement_overdue_open_count')} escalation={summary.get('improvement_escalation_level')} top={summary.get('improvement_top_title')}",
        f"tokens={summary.get('token_usage_status')} events={summary.get('token_usage_event_count')} total={summary.get('token_usage_total_tokens')} implementation_gaps={summary.get('token_usage_implementation_gap_count')}",
        f"owner_gated={summary.get('owner_gated_review_status')} decisions={summary.get('owner_gated_decision_required_count')} top={summary.get('owner_gated_top_gate')}:{summary.get('owner_gated_top_title')}",
        f"finance_domain_repair_items={summary.get('finance_domain_repair_item_count')} implementation_blockers={summary.get('implementation_blocker_count')} control_blockers={summary.get('control_plane_blocker_count')}",
        f"tier_a_b_missing_bands={summary.get('tier_a_b_missing_decision_grade_band_count')} tickers={','.join(missing)}",
        f"stale_inputs={','.join(payload.get('stale_inputs') or [])}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact read-only startup brief packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--max-age-minutes", type=int, default=90)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload(args.max_age_minutes)
    if args.write:
        atomic_write_json(args.out, payload)
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.validate and payload.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
