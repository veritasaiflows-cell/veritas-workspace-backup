#!/usr/bin/env python3
"""Build the SQL-canon owner decision packet.

This packet is intentionally non-destructive. It reads the live SQL-canon
phase proof in memory and writes a review-only decision surface for Randall.
It does not edit consumers, write SQL, retire fallbacks, archive/delete files,
change cron schedules, mutate portfolio/canon notes, or authorize execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json  # noqa: E402
import sql_canon_migration_phase_executor as phase_executor  # noqa: E402


SCHEMA = "veritas.sql_canon_owner_decision_packet.v1"
DEFAULT_OUT = ROOT / "tmp" / "sql-canon-owner-decision-packet.json"
FRONT_DOOR_READINESS_PACKET = ROOT / "tmp" / "sql-canon-front-door-readiness-packet.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "decision_packet_only": True,
    "classification_only": True,
    "consumer_file_mutation_allowed": False,
    "sql_write_allowed": False,
    "source_feeder_retirement_allowed": False,
    "python_fallback_retirement_allowed": False,
    "answer_path_sql_first_promotion_allowed": False,
    "schema_mutation_allowed": False,
    "archive_delete_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

HARD_GATE_DECISION_IDS = {
    "source_feeder_retirement",
    "python_fallback_retirement",
    "sql_first_front_door_promotion",
    "duplicate_surface_schema_cleanup",
    "cron_schedule_change",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def phase_args() -> Namespace:
    return Namespace(
        db=phase_executor.DEFAULT_DB,
        inventory=phase_executor.DEFAULT_INVENTORY,
        backlog=phase_executor.DEFAULT_BACKLOG,
        burndown=phase_executor.DEFAULT_BURNDOWN,
        retirement=phase_executor.DEFAULT_RETIREMENT,
        trade_grade_assembler=phase_executor.DEFAULT_TRADE_GRADE_ASSEMBLER,
        answer_path_ab_harness=phase_executor.DEFAULT_ANSWER_PATH_AB,
        python_retirement=phase_executor.DEFAULT_PYTHON_RETIREMENT,
        cron_control=phase_executor.DEFAULT_CRON_CONTROL,
        db_lifecycle=phase_executor.DEFAULT_DB_LIFECYCLE,
    )


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return as_dict(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return {}


def decision(
    *,
    decision_id: str,
    label: str,
    recommended_decision: str,
    status: str,
    eligible_count: int | None,
    reason: str,
    required_before_yes: list[str],
    action_allowed_now: bool = False,
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "label": label,
        "status": status,
        "recommended_decision": recommended_decision,
        "action_allowed_now": action_allowed_now,
        "approval_required_before_action": True,
        "eligible_count": eligible_count,
        "reason": reason,
        "required_before_yes": required_before_yes,
    }


def build_packet() -> dict[str, Any]:
    phase = phase_executor.build(phase_args())
    source_partition = as_dict(phase.get("source_producer_partition"))
    front_door = as_dict(phase.get("sql_first_front_door_readiness"))
    rich_front_door = read_json(FRONT_DOOR_READINESS_PACKET)
    rich_front_door_validation = as_dict(rich_front_door.get("validation"))
    rich_front_door_proof = as_dict(rich_front_door.get("proof_summary"))
    fallback = as_dict(phase.get("python_fallback_retirement_audit"))
    duplicate = as_dict(phase.get("duplicate_surface_schema_cleanup_plan"))
    cron = as_dict(phase.get("cron_impact_review"))
    registry = as_dict(phase.get("registry_summary"))
    raw_sql = as_dict(phase.get("raw_sql_classification"))
    phase_validation = as_dict(phase.get("validation"))

    raw_sql_review = int(raw_sql.get("raw_sql_review_count") or 0)
    source_ready = int(source_partition.get("source_feeder_retirement_ready_count") or 0)
    duplicate_ready = int(duplicate.get("duplicate_surface_retirement_ready_count") or 0)
    archive_ready = int(duplicate.get("archive_ready_count") or 0)
    delete_ready = int(duplicate.get("delete_ready_count") or 0)
    fallback_retire_count = int(fallback.get("retire_python_now_count") or 0)
    sql_first_allowed = False
    cron_schedule_allowed = bool(cron.get("cron_schedule_mutation_allowed"))
    rich_front_door_status = str(rich_front_door.get("status") or "missing")
    rich_front_door_valid = rich_front_door_validation.get("status") == "ok"
    rich_front_door_green = rich_front_door_status == "readiness_green_promotion_still_owner_gated" and rich_front_door_valid
    rich_front_door_source_guarded = rich_front_door_status == "readiness_waiting_source_open_guard_retained" and rich_front_door_valid
    if rich_front_door_green:
        sql_first_status = "front_door_rich_proof_ready_owner_gated"
        sql_first_reason = (
            "Rich front-door A/B and fallback contract are green, but promotion/apply still requires "
            "an exact SQL-first promotion packet, patch/diff, rollback proof, and Randall approval."
        )
        sql_first_required = [
            "separate SQL-first promotion approval packet",
            "consumer patch/diff and rollback proof",
            "post-promotion validation proof",
            "fallback/source-open retention contract remains active",
        ]
    elif rich_front_door_source_guarded:
        sql_first_status = "front_door_rich_proof_blocked_by_source_open_guard"
        guarded_count = rich_front_door_proof.get("front_door_source_open_guard_count")
        wf85_default_count = rich_front_door_proof.get("front_door_wf85_default_count")
        evaluated_count = rich_front_door_proof.get("front_door_evaluated_count")
        sql_first_reason = (
            f"Rich parity is clean and fallback is retained, but front-door default routing is {wf85_default_count}/{evaluated_count}; "
            f"{guarded_count} tickers remain source-open guarded before SQL-first promotion."
        )
        sql_first_required = [
            "repair or explicitly retain source-open guarded front-door tickers",
            "rerun sql_canon_front_door_readiness_packet",
            "separate SQL-first promotion approval packet",
            "consumer patch/diff and rollback proof",
        ]
    else:
        sql_first_status = "review_ready_not_promotable"
        sql_first_reason = "; ".join(front_door.get("blockers") or ["promotion blockers remain"])
        sql_first_required = [
            "rich-answer A/B parity beyond structural legacy-42 scope",
            "fallback/source-open contract",
            "source-feeder and duplicate-surface retirement gates, or explicit retention contract",
            "separate SQL-first promotion approval packet",
        ]

    decisions = [
        {
            "decision_id": "continue_proof_only_planning",
            "label": "Continue proof-only planning",
            "status": "safe_to_continue",
            "recommended_decision": "continue",
            "action_allowed_now": True,
            "approval_required_before_action": False,
            "eligible_count": None,
            "reason": "Classification, parity checks, and readiness packets do not cross hard apply gates.",
            "allowed_actions": [
                "refresh route/capsule/control packets",
                "run validators",
                "build narrower readiness packets",
            ],
        },
        decision(
            decision_id="source_feeder_retirement",
            label="Retire source feeders",
            recommended_decision="hold",
            status="not_eligible",
            eligible_count=source_ready,
            reason="No source feeder is retirement-ready; 346 source/proof/write surfaces remain retained.",
            required_before_yes=[
                "source_feeder_retirement_ready_count > 0 from retirement readiness proof",
                "active-reference review for each candidate",
                "backup/rollback plan",
                "exact Randall approval for named surfaces",
            ],
        ),
        decision(
            decision_id="python_fallback_retirement",
            label="Retire Python fallback",
            recommended_decision="hold",
            status="not_eligible",
            eligible_count=fallback_retire_count,
            reason="Python fallback remains retained and the retirement gate does not allow file deletion.",
            required_before_yes=[
                "python fallback removal readiness clean",
                "no live references to candidate helpers",
                "rollback instructions for every file",
                "exact Randall approval for named helper files",
            ],
        ),
        decision(
            decision_id="sql_first_front_door_promotion",
            label="Promote SQL-first finance front door",
            recommended_decision="hold",
            status=sql_first_status,
            eligible_count=0,
            reason=sql_first_reason,
            required_before_yes=sql_first_required,
            action_allowed_now=sql_first_allowed,
        ),
        decision(
            decision_id="duplicate_surface_schema_cleanup",
            label="Clean up duplicate surfaces/schema",
            recommended_decision="hold",
            status="not_eligible",
            eligible_count=duplicate_ready,
            reason="No duplicate surface, archive, delete, or schema cleanup action is ready.",
            required_before_yes=[
                "archive_ready/delete_ready candidate from DB lifecycle manifest",
                "active-reference review",
                "backup/rollback proof",
                "exact Randall archive/delete/schema approval",
            ],
        ),
        decision(
            decision_id="cron_schedule_change",
            label="Change cron schedules for SQL migration",
            recommended_decision="no_change",
            status="not_needed",
            eligible_count=0,
            reason=str(cron.get("recommendation") or "No cron schedule mutation is justified by this packet."),
            required_before_yes=[
                "cron impact packet with a specific schedule diff",
                "cron contract validator clean",
                "explicit approval for schedule mutation",
            ],
            action_allowed_now=cron_schedule_allowed,
        ),
    ]

    hard_gate_actions_allowed = [
        row["decision_id"]
        for row in decisions
        if row["decision_id"] in HARD_GATE_DECISION_IDS and row.get("action_allowed_now") is True
    ]

    status = "ready_for_owner_review"
    if phase.get("status") != "ok" or phase_validation.get("critical_errors"):
        status = "blocked_pending_phase_proof"
    elif hard_gate_actions_allowed:
        status = "blocked_authority_drift"

    return {
        "schema": SCHEMA,
        "generated_at_utc": phase.get("generated_at_utc"),
        "status": status,
        "workflow": "SQL-CANON",
        "purpose": "Owner-facing decision packet for the next SQL-canon gates after the safe migration phase.",
        "recommendation": "continue proof_only_readiness; hold every hard-gated apply/retirement/promotion action",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "evidence_summary": {
            "registry": registry,
            "raw_sql": {
                "raw_sql_present_count": raw_sql.get("raw_sql_present_count"),
                "raw_sql_review_count": raw_sql_review,
                "actionable_typed_replacement_review_count": raw_sql.get("actionable_typed_replacement_review_count"),
            },
            "source_producers": {
                "source_producer_count": source_partition.get("source_producer_count"),
                "partition_counts": source_partition.get("partition_counts"),
                "source_feeder_retirement_ready_count": source_ready,
                "retirement_candidate_count": source_partition.get("retirement_candidate_count"),
                "retirement_recommendation": source_partition.get("retirement_recommendation"),
            },
            "sql_first_front_door": front_door,
            "sql_first_front_door_rich_ab_fallback": {
                "artifact": rel(FRONT_DOOR_READINESS_PACKET),
                "status": rich_front_door_status,
                "validation_status": rich_front_door_validation.get("status"),
                "front_door_evaluated_count": rich_front_door_proof.get("front_door_evaluated_count"),
                "front_door_wf85_default_count": rich_front_door_proof.get("front_door_wf85_default_count"),
                "front_door_source_open_guard_count": rich_front_door_proof.get("front_door_source_open_guard_count"),
                "front_door_hard_blocked_count": rich_front_door_proof.get("front_door_hard_blocked_count"),
                "rich_answer_section_count": rich_front_door_proof.get("rich_answer_section_count"),
                "rich_answer_section_ok_count": rich_front_door_proof.get("rich_answer_section_ok_count"),
                "promotion_blockers_remaining": rich_front_door.get("promotion_blockers_remaining"),
            },
            "python_fallback": fallback,
            "duplicate_surface_schema_cleanup": {
                **duplicate,
                "archive_ready_count": archive_ready,
                "delete_ready_count": delete_ready,
            },
            "cron_impact": cron,
        },
        "owner_decisions": decisions,
        "hard_gate_actions_allowed": hard_gate_actions_allowed,
        "blocked_without_exact_owner_approval": [
            "source-feeder retirement",
            "Python fallback retirement or helper-file deletion",
            "SQL-first/front-door promotion",
            "duplicate-surface archive/delete/schema cleanup apply",
            "cron schedule mutation",
            "portfolio/canon/cash/sizing/risk mutation",
            "capital deployment",
            "paper/live/account/brokerage action",
            "money movement",
        ],
        "approved_to_continue_without_new_owner_decision": [
            "proof-only classification refresh",
            "readiness packet generation",
            "validator execution",
            "route/capsule/control-packet refresh",
        ],
        "next_recommended_packet": {
            "packet": (
                "sql_first_front_door_promotion_decision_packet"
                if rich_front_door_green
                else "source_open_guard_repair_or_explicit_retention_packet"
            ),
            "why": (
                "Rich front-door readiness is green; the next step would be a separate exact promotion decision packet."
                if rich_front_door_green
                else "The rich front-door proof found source-open guarded tickers; repair or explicitly retain that guard before promotion."
            ),
            "must_remain_false": [
                "sql_first_promotion_allowed",
                "fallback_retirement_allowed",
                "source_feeder_retirement_allowed",
                "archive_delete_apply_allowed",
            ],
        },
        "source_phase_executor": {
            "in_memory_schema": phase.get("schema"),
            "status": phase.get("status"),
            "phase_readiness": phase.get("phase_readiness"),
            "validation": phase_validation,
            "proof_artifacts": phase.get("proof_artifacts"),
        },
        "validation": {
            "status": "ok" if status == "ready_for_owner_review" else "error",
            "errors": [],
            "warnings": [],
        },
        "stop_lines": [
            "This packet does not approve or perform a hard-gated action.",
            "This packet does not retire source feeders or Python fallbacks.",
            "This packet does not promote SQL-first finance front doors.",
            "This packet does not archive, delete, or mutate schema.",
            "This packet does not mutate portfolio/canon/cash/sizing/risk state.",
            "This packet does not authorize capital deployment, paper/live execution, brokerage/account actions, or money movement.",
        ],
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    if packet.get("hard_gate_actions_allowed"):
        errors.append("hard_gate_action_allowed")
    decisions = {row.get("decision_id"): row for row in packet.get("owner_decisions", [])}
    missing = HARD_GATE_DECISION_IDS - set(decisions)
    if missing:
        errors.append("missing_hard_gate_decisions:" + ",".join(sorted(missing)))
    for decision_id in HARD_GATE_DECISION_IDS:
        row = decisions.get(decision_id, {})
        if row.get("action_allowed_now") is True:
            errors.append(f"hard_gate_decision_action_allowed:{decision_id}")
    evidence = as_dict(packet.get("evidence_summary"))
    if int(as_dict(evidence.get("raw_sql")).get("raw_sql_review_count") or 0) != 0:
        errors.append("raw_sql_review_count_not_zero")
    cleanup = as_dict(evidence.get("duplicate_surface_schema_cleanup"))
    if int(cleanup.get("archive_ready_count") or 0) != 0:
        errors.append("archive_ready_count_not_zero")
    if int(cleanup.get("delete_ready_count") or 0) != 0:
        errors.append("delete_ready_count_not_zero")
    source = as_dict(evidence.get("source_producers"))
    if int(source.get("source_feeder_retirement_ready_count") or 0) != 0:
        errors.append("source_feeder_retirement_ready_count_not_zero")
    rich_front = as_dict(evidence.get("sql_first_front_door_rich_ab_fallback"))
    if rich_front.get("validation_status") not in {None, "ok"}:
        errors.append("front_door_rich_ab_validation_not_ok")
    if int(rich_front.get("front_door_hard_blocked_count") or 0) != 0:
        errors.append("front_door_hard_blocked_count_not_zero")
    if packet.get("status") != "ready_for_owner_review":
        errors.append(f"packet_status_not_ready:{packet.get('status')}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet()
    errors = validate_packet(packet) if args.validate else []
    packet["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": [],
    }
    if errors and packet["status"] == "ready_for_owner_review":
        packet["status"] = "blocked_validation_error"
    if args.write:
        atomic_write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out) if args.write else None,
                "recommendation": packet["recommendation"],
                "hard_gate_actions_allowed": packet["hard_gate_actions_allowed"],
                "decision_count": len(packet["owner_decisions"]),
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
