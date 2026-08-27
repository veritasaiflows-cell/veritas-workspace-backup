#!/usr/bin/env python3
"""Close out OTEL audit recommendations with a migration-safe plan.

This packet reconciles the 2026-06-15 OTEL learning-loop recommendations
against current proof artifacts. It is review-only: it may plan cron migration,
hygiene, and follow-up measurement, but it does not mutate cron, config, runtime,
or delete/archive files.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "otel-recommendation-closeout.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.otel_recommendation_closeout.v1"

OTEL_LEARNING = TMP / "otel-learning-loop.json"
WF74_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
OTEL_OPS = TMP / "otel-ops-control.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
FUTURE_PACKET = TMP / "future-session-enhancement-packet.json"
OTEL_LOG_RETENTION = TMP / "otel-log-retention.json"
MODEL_LEARNING = TMP / "model-learning-metadata-ledger.json"
MODEL_RUN = TMP / "model-run-ledger-current.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "planning_only": True,
    "cron_schedule_mutation_allowed": False,
    "cron_payload_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "collector_config_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "archive_or_delete_allowed": False,
    "external_export_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

RECOMMENDATION_DEFINITIONS = {
    "R1": "OTEL log rotation / retention",
    "R2": "Audit live runtime-metadata collector config, not stale/basic config",
    "R3": "Schedule and staleness-guard future-session carryover packet",
    "R4": "Token/cost metadata-depth patch",
    "R5": "Archive orphaned scorecards",
    "R6": "Broaden learning-loop inputs beyond model_quality_scorecard",
    "R7": "Automate outcome/follow-up measurement",
    "R8": "Dead collector hygiene",
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


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def stale_scorecard_candidates(max_count: int = 20) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for path in TMP.glob("*scorecard*.json"):
        payload = as_dict(load_json_artifact(path))
        generated = payload.get("generated_at_utc")
        parsed: datetime | None = None
        if generated:
            try:
                parsed = datetime.fromisoformat(str(generated).replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                parsed = None
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        basis = parsed or mtime
        age_days = (now - basis).total_seconds() / 86400
        if age_days >= 7:
            candidates.append({
                "path": rel(path),
                "status": payload.get("status"),
                "generated_at_utc": generated,
                "mtime_utc": mtime.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "age_days": round(age_days, 2),
                "proposed_action": "archive_candidate_owner_approval_required",
            })
    return sorted(candidates, key=lambda row: row["age_days"], reverse=True)[:max_count]


def dead_collector_candidates() -> list[dict[str, Any]]:
    paths = [
        ROOT / "scripts" / "local_otel_collector.py",
        ROOT / "scripts" / "start_local_otel_collector.cmd",
    ]
    candidates: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            candidates.append({
                "path": rel(path),
                "exists": True,
                "proposed_action": "hygiene_review_owner_approval_required",
                "reason": "legacy Python/cmd collector surface; live collector proof is from tools/otelcol/otelcol.exe and runtime-metadata config",
            })
    return candidates


def recommendation_statuses() -> dict[str, dict[str, Any]]:
    otel = as_dict(load_json_artifact(OTEL_OPS))
    cron = as_dict(load_json_artifact(CRON_CONTROL))
    future = as_dict(load_json_artifact(FUTURE_PACKET))
    log_retention = as_dict(load_json_artifact(OTEL_LOG_RETENTION))
    learning = as_dict(load_json_artifact(OTEL_LEARNING))
    queue = as_dict(load_json_artifact(WF74_QUEUE))
    model_learning = as_dict(load_json_artifact(MODEL_LEARNING))
    model_run = as_dict(load_json_artifact(MODEL_RUN))

    collector_config = as_dict(otel.get("collector_config"))
    learning_summaries = as_dict(learning.get("learning_summaries"))
    friction = as_dict(learning_summaries.get("operational_friction"))
    queue_summary = as_dict(queue.get("summary"))
    token_cost = as_dict(learning_summaries.get("token_cost"))

    return {
        "R1": {
            "title": RECOMMENDATION_DEFINITIONS["R1"],
            "status": "implemented",
            "proof": [rel(OTEL_LOG_RETENTION)],
            "evidence": {
                "retention_status": log_retention.get("status"),
                "validation_status": as_dict(log_retention.get("validation")).get("status"),
            },
        },
        "R2": {
            "title": RECOMMENDATION_DEFINITIONS["R2"],
            "status": "implemented" if collector_config.get("path") and "runtime-metadata" in str(collector_config.get("path")) else "needs_review",
            "proof": [rel(OTEL_OPS)],
            "evidence": {"collector_config_path": collector_config.get("path")},
        },
        "R3": {
            "title": RECOMMENDATION_DEFINITIONS["R3"],
            "status": "implemented_with_warning" if future.get("status") == "warning" else "implemented" if future.get("status") == "ok" else "needs_repair",
            "proof": [rel(FUTURE_PACKET), rel(CRON_CONTROL)],
            "evidence": {
                "future_packet_status": future.get("status"),
                "future_packet_validation": as_dict(future.get("validation")).get("status"),
                "cron_status": cron.get("status"),
                "cron_validation": as_dict(cron.get("validation")).get("status"),
            },
        },
        "R4": {
            "title": RECOMMENDATION_DEFINITIONS["R4"],
            "status": "partially_implemented_owner_config_decision_remaining",
            "proof": [rel(MODEL_LEARNING), rel(MODEL_RUN), rel(OTEL_LEARNING)],
            "evidence": {
                "model_learning_status": model_learning.get("status"),
                "model_run_status": model_run.get("status"),
                "token_coverage_ratio": token_cost.get("token_coverage_ratio"),
                "cost_coverage_ratio": token_cost.get("cost_coverage_ratio"),
            },
        },
        "R5": {
            "title": RECOMMENDATION_DEFINITIONS["R5"],
            "status": "dry_run_plan_ready_owner_approval_required",
            "proof": [rel(DEFAULT_JSON)],
            "evidence": {"candidate_count": len(stale_scorecard_candidates())},
        },
        "R6": {
            "title": RECOMMENDATION_DEFINITIONS["R6"],
            "status": "implemented",
            "proof": [rel(WF74_QUEUE), rel(OTEL_LEARNING)],
            "evidence": {
                "queue_categories": queue_summary.get("by_category"),
                "cron_blocked_count": as_dict(friction.get("cron")).get("blocked_count"),
                "workflow_blocked_count": as_dict(friction.get("workflow_advancement")).get("blocked_count"),
            },
        },
        "R7": {
            "title": RECOMMENDATION_DEFINITIONS["R7"],
            "status": "implemented_measurement_backlog",
            "proof": [rel(WF74_QUEUE), rel(OTEL_LEARNING)],
            "evidence": {
                "outcome_measurement_followup_count": queue_summary.get("outcome_measurement_followup_count"),
                "wf87_pending_followups": as_dict(friction.get("wf87_shadow_outcomes")).get("pending_regular_session_followup_count"),
            },
        },
        "R8": {
            "title": RECOMMENDATION_DEFINITIONS["R8"],
            "status": "dry_run_plan_ready_owner_approval_required",
            "proof": [rel(DEFAULT_JSON)],
            "evidence": {"candidate_count": len(dead_collector_candidates())},
        },
    }


def cron_migration_next_steps() -> list[dict[str, Any]]:
    return [
        {
            "step": 1,
            "name": "Inventory and group cron surfaces",
            "action": "Use cron_control_packet, cron_contract_validator, and cron_signal_scorecard to group jobs by owner workflow, artifact outputs, blocked signals, and schedule collision risk.",
            "command": "python scripts\\cron_control_packet.py --write --validate",
            "mutation_allowed": False,
        },
        {
            "step": 2,
            "name": "Normalize contracts before live migration",
            "action": "Patch state/cron-contracts only when a contract is missing or stale; validate drift before touching live Gateway cron.",
            "command": "python scripts\\cron_contract_validator.py --write --validate",
            "mutation_allowed": "contract_file_only_after_lane_lease",
        },
        {
            "step": 3,
            "name": "Build dry-run migration batches",
            "action": "Separate low-risk proof refreshers from owner-facing delivery jobs and finance market-window jobs. Start with proof refreshers.",
            "command": "python scripts\\cron_patch_manager.py --dry-run --write --validate",
            "mutation_allowed": False,
        },
        {
            "step": 4,
            "name": "Canary one low-risk job",
            "action": "Use a bounded canary with preserved stop lines, schedule, target, and rollback. Spark canaries require xhigh thinking.",
            "command": "python scripts\\cron_spark_canary_monitor.py --write --validate",
            "mutation_allowed": "owner_approved_canary_only",
        },
        {
            "step": 5,
            "name": "Apply approved cron patch with rollback",
            "action": "Apply only exact approved changes, capture before/after contracts, and keep auth/runtime/channel boundaries unchanged.",
            "command": "python scripts\\cron_patch_manager.py --apply --write --validate",
            "mutation_allowed": "explicit_owner_approval_required",
        },
        {
            "step": 6,
            "name": "Post-change proof and carryover",
            "action": "Refresh cron freshness, OTEL ops, future-session packet, and the recommendation closeout; block if escalation returns.",
            "command": "python scripts\\cron_control_packet.py --write --validate; python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            "mutation_allowed": False,
        },
    ]


def build_payload() -> dict[str, Any]:
    stale_candidates = stale_scorecard_candidates()
    collector_candidates = dead_collector_candidates()
    statuses = recommendation_statuses()
    unresolved = [
        key for key, row in statuses.items()
        if str(row.get("status")) not in {"implemented", "implemented_measurement_backlog"}
    ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Reconcile OTEL audit recommendations, dry-run hygiene targets, and cron migration next steps.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_status": [
            source_status(OTEL_LEARNING),
            source_status(WF74_QUEUE),
            source_status(OTEL_OPS),
            source_status(CRON_CONTROL),
            source_status(FUTURE_PACKET),
            source_status(OTEL_LOG_RETENTION),
            source_status(MODEL_LEARNING),
            source_status(MODEL_RUN),
        ],
        "recommendations": statuses,
        "summary": {
            "recommendation_count": len(statuses),
            "implemented_count": sum(1 for row in statuses.values() if str(row.get("status")).startswith("implemented")),
            "owner_approval_required_count": sum(1 for row in statuses.values() if "owner" in str(row.get("status"))),
            "unresolved_recommendations": unresolved,
            "stale_scorecard_candidate_count": len(stale_candidates),
            "dead_collector_candidate_count": len(collector_candidates),
            "next_safe_action": "Use the cron migration dry-run sequence; request approval only for exact cron/config/archive/delete changes.",
        },
        "r5_stale_scorecard_dry_run": {
            "destructive_action_taken": False,
            "candidates": stale_candidates,
        },
        "r8_dead_collector_hygiene_dry_run": {
            "destructive_action_taken": False,
            "candidates": collector_candidates,
        },
        "cron_migration_next_steps": cron_migration_next_steps(),
        "blocked_actions": [
            "no live cron mutation from this packet",
            "no collector/runtime config mutation from this packet",
            "no archive/delete/move from this packet",
            "no external delivery",
            "no finance canon/portfolio mutation",
            "no paper/live/account action",
            "no owner approval inference",
        ],
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if as_dict(payload.get("r5_stale_scorecard_dry_run")).get("destructive_action_taken") is not False:
        errors.append("r5_destructive_action_taken")
    if as_dict(payload.get("r8_dead_collector_hygiene_dry_run")).get("destructive_action_taken") is not False:
        errors.append("r8_destructive_action_taken")
    if as_dict(payload.get("summary")).get("owner_approval_required_count"):
        warnings.append("owner_approval_required_for_remaining_runtime_or_hygiene_changes")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# OTEL Recommendation Closeout",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Implemented: {summary.get('implemented_count')} / {summary.get('recommendation_count')}",
        f"- Owner approval required: {summary.get('owner_approval_required_count')}",
        f"- Unresolved: {', '.join(summary.get('unresolved_recommendations') or [])}",
        "",
        "## Cron Migration Next Steps",
    ]
    for step in as_list(payload.get("cron_migration_next_steps")):
        lines.append(f"- {step.get('step')}. {step.get('name')}: {step.get('action')}")
    lines.extend(["", "## Blocked Actions"])
    for action in as_list(payload.get("blocked_actions")):
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        atomic_write_json(args.json_out, payload)
        if args.write_md:
            atomic_write_text(args.md_out, render_md(payload))
    else:
        print(json.dumps(payload, indent=2))
    print(
        "status={status} validation={validation} implemented={implemented}/{total} owner_required={owner_required}".format(
            status=payload.get("status"),
            validation=as_dict(payload.get("validation")).get("status"),
            implemented=as_dict(payload.get("summary")).get("implemented_count"),
            total=as_dict(payload.get("summary")).get("recommendation_count"),
            owner_required=as_dict(payload.get("summary")).get("owner_approval_required_count"),
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
