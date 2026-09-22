#!/usr/bin/env python3
"""Route WF74 improvement signals into durable repair plans and PM jobs.

This is the bridge between "WF74 noticed a problem" and "main/cron has a
review-only work object to advance." It does not apply fixes, mutate schedules,
spawn helpers, or widen finance/execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.command_guard import command_is_review_only_safe
from market_data_utils import atomic_write_json, load_json_artifact
from wf74_improvement_opportunity_queue import select_actionable_planning_gap


def project_planning_signal(planning_signal: dict[str, Any]) -> dict[str, Any]:
    """Project raw planning history separately from trusted actionable debt.

    Raw history (raw163-scale totals) is preserved verbatim; the partition is
    trusted only when the signal schema is exact, counts are strict non-bool
    ints, and reconciliation is exact, otherwise fail closed to raw with a
    warning. Single source of selector meaning: wf74_improvement_opportunity_queue.
    """
    # Schema-exact trust: only veritas.planning_quality_signal.v1 may project a verified partition.
    # Single source of meaning for the fail-closed selector: wf74_improvement_opportunity_queue.
    selection = select_actionable_planning_gap(planning_signal)
    if planning_signal.get("schema") != "veritas.planning_quality_signal.v1":
        raw_gap = int(selection["raw_gap_count"])
        warning = str(selection.get("warning") or "partition_fields_unavailable")
        selection = {
            "selected_gap_count": raw_gap,
            "raw_gap_count": raw_gap,
            "source": "raw_gap_fallback",
            "warning": "planning_signal_schema_not_exact; " + warning,
            "actionable_gap_count": planning_signal.get("plan_followthrough_actionable_gap_count"),
            "terminal_unavailable_count": planning_signal.get("plan_followthrough_terminal_unavailable_count"),
            "repaired_accepted_count": planning_signal.get("plan_followthrough_repaired_accepted_count"),
            "partitioned_gap_row_count": planning_signal.get("partitioned_gap_row_count"),
            "partition_reconciliation_ok": planning_signal.get("partition_reconciliation_ok"),
        }
    if selection["source"] == "actionable_partition_verified":
        operational_status: Any = planning_signal.get("actionable_status") or (
            "attention" if int(selection["selected_gap_count"]) else "ok"
        )
    else:
        operational_status = "unverified_fallback"
    return {
        "planning_followthrough_gap_count": int(selection["raw_gap_count"]),
        "planning_followthrough_gap_count_selected": int(selection["selected_gap_count"]),
        "planning_followthrough_gap_source": selection["source"],
        "planning_followthrough_actionable_gap_count": selection.get("actionable_gap_count"),
        "planning_followthrough_terminal_unavailable_count": selection.get("terminal_unavailable_count"),
        "planning_followthrough_repaired_accepted_count": selection.get("repaired_accepted_count"),
        "planning_partitioned_gap_row_count": selection.get("partitioned_gap_row_count"),
        "planning_partition_reconciliation_ok": selection.get("partition_reconciliation_ok"),
        "planning_actionable_status": operational_status,
        "planning_signal_schema": planning_signal.get("schema"),
        "planning_gap_selection_warning": selection.get("warning"),
    }

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"

DEFAULT_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
DEFAULT_IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
DEFAULT_WORKFLOW_FOLLOWUPS = TMP / "workflow-blocker-followups.json"
DEFAULT_CRON_CONTROL = TMP / "cron-control-packet.json"
DEFAULT_PM_CONTROL = TMP / "pm-control-packet.json"
DEFAULT_CODING_OUTCOME = TMP / "coding-outcome-ledger-current.json"
DEFAULT_OUT = TMP / "wf74-autonomy-work-router.json"
DEFAULT_CRON_REPAIR_PLAN = TMP / "cron-migration-repair-plan.json"
DEFAULT_FOLLOWUP_LEDGER = TMP / "workflow-implementation-followup-ledger.json"
DEFAULT_FOLLOWUP_HISTORY = STATE / "workflow-implementation-followup-ledger.jsonl"

SCHEMA = "veritas.wf74_autonomy_work_router.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "router_only": True,
    "append_only_followup_history": True,
    "auto_fix_allowed": False,
    "auto_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "external_delivery_allowed": False,
    "helper_spawn_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

# This is deliberately a reference contract, not a review-event store. The
# router only carries a compact upstream reference when it is already supplied
# by an owner surface; it never creates, grades, or updates an event.
REVIEW_EVENT_REF_SCHEMA = "veritas.wf74_rsi_review_event_ref.v1"
REVIEW_EVENT_KINDS = {"coding_outcome_event", "recommendation_outcome_grade"}
REVIEW_EVENT_LINK_STATUSES = {"linked_exact", "unlinked", "unresolved"}
REVIEW_EVENT_SOURCE_BY_KIND = {
    "coding_outcome_event": "data/state-history/coding-outcome-ledger.jsonl",
    "recommendation_outcome_grade": "data/state-history/recommendation-outcome-grades.jsonl",
}
REVIEW_EVENT_REF_FIELDS = {
    "schema",
    "metadata_only",
    "link_status",
    "event_kind",
    "lifecycle_id",
    "source_path",
    "record_id",
    "record_hash",
    "ledger_event_id",
    "recommendation_id",
    "linked_at_utc",
    "source_freshness",
    "authority_boundary",
}
REVIEW_EVENT_FRESHNESS_FIELDS = {
    "generated_at_utc",
    "observed_at_utc",
    "age_hours",
    "status",
    "fresh",
    "max_age_hours",
}
REVIEW_EVENT_FRESHNESS_STATUSES = {"ok", "warning", "fresh", "stale", "blocked", "missing", "error", "unknown"}
REVIEW_EVENT_AUTHORITY_FIELDS = {"review_only", "owner_approval_inferred"}

GLOBAL_STOP_LINES = [
    "no owner approval inference",
    "no auto-apply from WF74 recommendations",
    "no cron schedule mutation without exact owner-approved diff, rollback, and post-change proof",
    "no config/auth/channel/service/runtime mutation",
    "no archive/move/delete without exact owner approval",
    "no canon/portfolio/sizing/cash/risk-rule mutation",
    "no paper/live/brokerage/account action",
]

DEPARTMENT_OWNER_BY_DEPARTMENT = {
    "cron": "cron-automation-manager",
    "runtime_ops": "automation-hardening-manager",
    "pm": "veritas-pm-department",
    "finance_wf78_wf84_wf85": "main-session-veritas-finance",
    "product_wf75_wf79": "smb-workflow-automation-operator",
    "qa": "workspace-qa-pass",
    "skills_procedure": "workspace-governor",
    "memory_continuity": "memory-continuity-manager",
    "main_session_veritas": "main-session-veritas",
}


DEPARTMENT_WORKFLOW_BY_DEPARTMENT = {
    "cron": "CRON/WF73/WF76",
    "runtime_ops": "Runtime Ops/WF74",
    "pm": "PM/WF74",
    "finance_wf78_wf84_wf85": "WF78/WF84/WF85",
    "product_wf75_wf79": "WF75/WF79",
    "qa": "QA/WF73",
    "skills_procedure": "Skills/Procedures/WF74",
    "memory_continuity": "Memory/Continuity",
    "main_session_veritas": "Main Session Veritas",
}


def department_for_route(category: str, implementation_class: str, owner_surface: str, lane_id: str) -> str:
    text = " ".join([category, implementation_class, owner_surface, lane_id]).casefold()
    if "cron" in text:
        return "cron"
    if any(token in text for token in ("finance", "wf78", "wf84", "wf85", "trade_grade", "ticker")):
        return "finance_wf78_wf84_wf85"
    if any(token in text for token in ("wf75", "wf79", "retail", "smb", "product", "service_state")):
        return "product_wf75_wf79"
    if any(token in text for token in ("qa", "validator", "measurement")):
        return "qa"
    if any(token in text for token in ("skill", "procedure", "playbook")):
        return "skills_procedure"
    if any(token in text for token in ("memory", "continuity")):
        return "memory_continuity"
    if any(token in text for token in ("workflow", "followup", "planning", "wf74", "code_mutation")):
        return "runtime_ops"
    if "pm" in text:
        return "pm"
    return "main_session_veritas"


def department_contract(category: str, implementation_class: str, owner_surface: str, lane_id: str, status: str) -> dict[str, str]:
    department = department_for_route(category, implementation_class, owner_surface, lane_id)
    execution_mode = "owner_gated_review" if status == "owner_decision_required" else "main_or_helper_plan_only"
    if department == "cron":
        execution_mode = "cron_review_only_proof_refresh"
    return {
        "department": department,
        "department_owner": DEPARTMENT_OWNER_BY_DEPARTMENT[department],
        "owner_workflow": DEPARTMENT_WORKFLOW_BY_DEPARTMENT[department],
        "accountable_integrator": "main_session_veritas",
        "allowed_execution_mode": execution_mode,
    }

ROUTED_CATEGORIES = {
    "code_mutation",
    "cron_migration",
    "finance_mutation",
    "workflow_maturity",
    "planning_quality",
}

CODE_MUTATION_REPAIR_PROOF = [
    "python scripts\\model_run_ledger.py --write --write-md --validate",
    "python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate",
    "python scripts\\cron_control_packet.py --write --validate",
    "python scripts\\wf74_autonomy_work_router.py --write --validate",
    "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
]

CRON_REPAIR_PROOF = [
    "python scripts\\cron_control_packet.py --write --validate",
    "python scripts\\workflow_advancement_scorecard.py --write --validate",
    "python scripts\\wf74_autonomy_work_router.py --write --validate",
]

WORKFLOW_ROUTING_PROOF = [
    "python scripts\\workflow_advancement_scorecard.py --write --validate",
    "python scripts\\wf74_autonomy_work_router.py --write --validate",
    "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
]

PLANNING_QUALITY_PROOF = [
    "python scripts\\coding_outcome_ledger.py --write --validate",
    "python scripts\\concurrent_lane_manager.py --status --write --validate",
    "python scripts\\wf74_autonomy_work_router.py --write --validate",
]

FINANCE_SOURCE_OPEN_REPAIR_PROOF = [
    "python scripts\\wf78_source_open_repair_executor.py --tier all --write --validate",
    "python scripts\\wf78_source_open_work_packet.py --write --validate",
    "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
    "python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate",
    "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
]


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


def compact_identifier(value: Any) -> str:
    text = str(value or "")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
    return text if text and len(text) <= 256 and set(text) <= allowed else ""


def metadata_only_review_event_ref(
    value: Any,
    *,
    lifecycle_id: str,
    recommendation_id: str,
) -> dict[str, Any] | None:
    """Accept only a narrow, upstream-produced outcome reference.

    The reference carries identifiers and provenance, never the event body.
    A malformed, authoritative, Wiki/Markdown, or lifecycle-mismatched value
    is omitted so routing cannot fail open from prose or a mutable Wiki page.
    """
    ref = as_dict(value)
    if not ref:
        return None
    if set(ref) - REVIEW_EVENT_REF_FIELDS:
        return None
    if ref.get("schema") != REVIEW_EVENT_REF_SCHEMA or ref.get("metadata_only") is not True:
        return None
    link_status = str(ref.get("link_status") or "")
    event_kind = str(ref.get("event_kind") or "")
    if link_status not in REVIEW_EVENT_LINK_STATUSES or event_kind not in REVIEW_EVENT_KINDS:
        return None
    ref_lifecycle_id = compact_identifier(ref.get("lifecycle_id"))
    if ref.get("lifecycle_id") is not None and not ref_lifecycle_id:
        return None
    if ref_lifecycle_id and lifecycle_id and ref_lifecycle_id != lifecycle_id:
        return None
    source_path = str(ref.get("source_path") or "").replace("\\", "/")
    if source_path and source_path != REVIEW_EVENT_SOURCE_BY_KIND[event_kind]:
        return None
    boundary = as_dict(ref.get("authority_boundary"))
    if ref.get("authority_boundary") is not None and (
        set(boundary) != REVIEW_EVENT_AUTHORITY_FIELDS
        or boundary.get("review_only") is not True
        or boundary.get("owner_approval_inferred") is not False
    ):
        return None
    record_id = compact_identifier(ref.get("record_id"))
    if ref.get("record_id") is not None and not record_id:
        return None
    if link_status == "linked_exact" and (not source_path or not record_id or not ref_lifecycle_id):
        return None
    record_hash = str(ref.get("record_hash") or "")
    if record_hash and (len(record_hash) != 64 or set(record_hash.casefold()) - set("0123456789abcdef")):
        return None
    ref_recommendation_id = compact_identifier(ref.get("recommendation_id"))
    if ref.get("recommendation_id") is not None and not ref_recommendation_id:
        return None
    if ref_recommendation_id and recommendation_id and ref_recommendation_id != recommendation_id:
        return None
    for key in ("ledger_event_id",):
        if ref.get(key) is not None and not compact_identifier(ref.get(key)):
            return None
    linked_at_utc = str(ref.get("linked_at_utc") or "")
    if ref.get("linked_at_utc") is not None and (not linked_at_utc or len(linked_at_utc) > 64):
        return None
    freshness = as_dict(ref.get("source_freshness"))
    if ref.get("source_freshness") is not None:
        if not isinstance(ref.get("source_freshness"), dict) or set(freshness) - REVIEW_EVENT_FRESHNESS_FIELDS:
            return None
        if any(
            key in freshness and not isinstance(freshness[key], (str, int, float, bool))
            for key in freshness
        ):
            return None
        if "status" in freshness and str(freshness["status"]) not in REVIEW_EVENT_FRESHNESS_STATUSES:
            return None
        if "fresh" in freshness and type(freshness["fresh"]) is not bool:
            return None
        if any(
            key in freshness and (type(freshness[key]) is bool or not isinstance(freshness[key], (int, float)))
            for key in ("age_hours", "max_age_hours")
        ):
            return None
        if any(
            key in freshness and (not isinstance(freshness[key], str) or len(freshness[key]) > 64)
            for key in ("generated_at_utc", "observed_at_utc")
        ):
            return None
    result: dict[str, Any] = {
        "schema": REVIEW_EVENT_REF_SCHEMA,
        "metadata_only": True,
        "link_status": link_status,
        "event_kind": event_kind,
        "lifecycle_id": lifecycle_id or ref_lifecycle_id,
    }
    result["source_path"] = source_path if source_path else None
    if record_id:
        result["record_id"] = record_id
    if record_hash:
        result["record_hash"] = record_hash
    for key in ("ledger_event_id", "recommendation_id"):
        item = compact_identifier(ref.get(key))
        if item:
            result[key] = item
    if linked_at_utc:
        result["linked_at_utc"] = linked_at_utc
    if freshness:
        result["source_freshness"] = freshness
    if boundary:
        result["authority_boundary"] = {
            "review_only": True,
            "owner_approval_inferred": False,
        }
    return result


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "-".join(str(part or "").strip() for part in parts if str(part or "").strip())
    chars = [ch.lower() if ch.isalnum() else "-" for ch in raw]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{prefix}-{slug.strip('-') or 'unknown'}"


def fingerprint(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def lifecycle_id_for_origin(origin_opportunity_id: Any) -> str:
    """Match the legacy WF74 lifecycle derivation used by queue and trace."""
    raw = f"wf74|{str(origin_opportunity_id or '')}"
    return f"lifecycle-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def source_status(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def priority_band(priority: Any, default: str = "P2") -> str:
    try:
        value = int(priority)
    except (TypeError, ValueError):
        return default
    if value >= 80:
        return "P1"
    if value >= 60:
        return "P2"
    return "P3"


def compact_cron_signal(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "source",
            "signal_class",
            "status",
            "reason",
            "artifact",
            "age_hours",
            "next_action",
        )
        if row.get(key) is not None
    }


def compact_scheduler_exception(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "id",
            "name",
            "last_status",
            "consecutive_errors",
            "artifact_status",
            "signal_class",
            "reconciliation",
        )
        if row.get(key) is not None
    }


def cron_current_state(cron_control: dict[str, Any]) -> dict[str, Any]:
    if not cron_control or not isinstance(cron_control.get("summary"), dict):
        return {
            "schema": "veritas.wf74_cron_signal_state.v1",
            "classification": "unknown_blocked",
            "safe_repair_available": False,
            "blocked_count": None,
            "escalation_signal_count": None,
            "blocked_artifact_count": None,
            "should_wake_main_session": None,
            "requires_attention_count": None,
            "live_scheduler_last_run_exception_count": None,
            "escalation_signals": [],
            "blocked_artifacts": [],
            "live_scheduler_last_run_exceptions": [],
            "next_action": (
                "Refresh cron_control_packet before classifying WF74 cron residue; missing cron truth must not be treated as green."
            ),
            "proof": "tmp/cron-control-packet.json",
        }
    summary = as_dict(cron_control.get("summary"))
    escalation = as_dict(cron_control.get("escalation"))
    freshness = as_dict(cron_control.get("freshness"))
    escalation_signals = [
        compact_cron_signal(row)
        for row in as_list(escalation.get("escalation_signals"))
        if isinstance(row, dict)
    ]
    blocked_artifacts = [
        {
            "artifact": row.get("artifact"),
            "source": row.get("source"),
            "reason": row.get("reason"),
            "age_hours": row.get("age_hours"),
            "next_action": row.get("next_action"),
        }
        for row in escalation_signals
        if row.get("artifact")
    ]
    live_scheduler_exceptions = [
        compact_scheduler_exception(row)
        for row in as_list(freshness.get("live_scheduler_last_run_exceptions"))
        if isinstance(row, dict)
    ]
    blocked_count = int(summary.get("blocked_count") or 0)
    escalation_count = int(summary.get("escalation_signal_count") or 0)
    should_wake = bool(summary.get("should_wake_main_session"))
    attention_count = int(summary.get("requires_attention_count") or 0)
    live_exception_count = int(
        summary.get("live_scheduler_last_run_exception_count")
        or len(live_scheduler_exceptions)
    )
    if blocked_count or escalation_count or should_wake:
        classification = "active_repair_plan_required"
        safe_repair_available = False
        next_action = (
            "Build or refresh a dry-run repair plan that names the active cron signals and blocked artifacts; "
            "do not mutate schedules unless a scoped diff and rollback proof are owner-approved."
        )
    else:
        classification = "green_no_repair_required"
        safe_repair_available = False
        next_action = (
            "Keep warning-grade cron attention visible as monitor-only residue; do not create a PM repair job unless "
            "blocked, escalated, or wake-main-session signals recur."
        )
    return {
        "schema": "veritas.wf74_cron_signal_state.v1",
        "classification": classification,
        "safe_repair_available": safe_repair_available,
        "blocked_count": blocked_count,
        "escalation_signal_count": escalation_count,
        "blocked_artifact_count": len(blocked_artifacts),
        "should_wake_main_session": should_wake,
        "requires_attention_count": attention_count,
        "live_scheduler_last_run_exception_count": live_exception_count,
        "escalation_signals": escalation_signals,
        "blocked_artifacts": blocked_artifacts,
        "live_scheduler_last_run_exceptions": live_scheduler_exceptions,
        "next_action": next_action,
        "proof": "tmp/cron-control-packet.json",
    }


def opportunity_route(opportunity: dict[str, Any], cron_state: dict[str, Any]) -> dict[str, Any]:
    category = str(opportunity.get("category") or "unknown")
    title = str(opportunity.get("title") or category)
    priority = opportunity.get("priority")
    source_key = str(opportunity.get("opportunity_id") or stable_id("opportunity", category, title))
    origin_opportunity_id = str(opportunity.get("origin_opportunity_id") or source_key)
    lifecycle_id = str(opportunity.get("lifecycle_id") or lifecycle_id_for_origin(origin_opportunity_id))
    review_event_ref = metadata_only_review_event_ref(
        opportunity.get("review_event_ref"),
        lifecycle_id=lifecycle_id,
        recommendation_id=source_key,
    )
    base = {
        "schema": "veritas.wf74_autonomy_route.v1",
        "source_type": "wf74_improvement_opportunity",
        "source_key": source_key,
        "recommendation_id": source_key,
        "origin_opportunity_id": origin_opportunity_id,
        "lifecycle_id": lifecycle_id,
        "category": category,
        "title": title,
        "priority": priority,
        "proposal_gate": opportunity.get("proposal_gate"),
        "recommended_action": opportunity.get("recommended_action"),
        "completion_status": opportunity.get("completion_status"),
        "prior_completion": opportunity.get("prior_completion"),
        "route_status": "not_routed",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if review_event_ref is not None:
        base["review_event_ref"] = review_event_ref
    if category == "cron_migration":
        if cron_state.get("classification") != "active_repair_plan_required":
            base.update(
                {
                    "route_status": "monitor_or_owner_gated",
                    "route": "cron_green_residue_monitor",
                    "blocked_reason": (
                        "current cron control has no blocked, escalated, or wake-main-session signal; "
                        "warning-grade attention remains monitor-only"
                    ),
                    "proof_commands": [
                        "python scripts\\cron_control_packet.py --write --validate",
                        "python scripts\\wf74_autonomy_work_router.py --write --validate",
                    ],
                    "current_signal_state": cron_state,
                    "acceptance_criteria": [
                        "current cron control stays blocked=0 and escalation=0",
                        "warning-grade attention is visible without creating a PM repair job",
                        "schedule/config mutation remains owner-gated",
                    ],
                }
            )
            return base
        cron_job_id = (
            "pm-wf74-cron-migration-regression-repair"
            if opportunity.get("completion_status") == "current_regression_after_completion"
            else "pm-wf74-cron-migration-repair-plan"
        )
        base.update(
            {
                "route_status": "pm_job_candidate",
                "route": "cron_repair_plan",
                "pm_job_id": cron_job_id,
                "implementation_class": "wf74_cron_migration_repair_plan",
                "owner_surface": "WF74 improvement ledger + cron control packet",
                "proof_commands": CRON_REPAIR_PROOF,
                "current_signal_state": cron_state,
                "acceptance_criteria": [
                    "current cron blocker state is classified from live cron_control_packet",
                    "active blockers have a dry-run repair plan or green residue is closed by proof",
                    "schedule/config mutation remains owner-gated",
                ],
            }
        )
    elif category == "code_mutation":
        signal = str(opportunity.get("signal") or "")
        is_blocked_collection_step = (
            signal == "wf74_collection_step_blocked"
            or "blocked wf74 collection step" in title.casefold()
        )
        route_name = (
            "blocked_collection_step_repair"
            if is_blocked_collection_step
            else f"code_mutation_followup_{source_key}"
        )
        job_id = (
            "pm-wf74-code-mutation-repair-blocked-collection-step"
            if is_blocked_collection_step
            else stable_id("pm-wf74-code-mutation", source_key)
        )
        implementation_class = (
            "wf74_blocked_collection_step_repair"
            if is_blocked_collection_step
            else "wf74_code_mutation_followup"
        )
        owner_surface = (
            "WF74 improvement opportunity queue + model quality collection runner"
            if is_blocked_collection_step
            else "WF74 improvement opportunity queue + validator routing proof"
        )
        acceptance_criteria = [
            "blocked WF74 collection step is repaired, downgraded to domain attention, or routed with exact blocker proof",
            "wf74_model_quality_collection_cron_runner.py completes without technical blocked steps",
            "cron_control_packet no longer escalates Ops - OTEL Local Digest for a technical runner failure",
            "finance/customer/execution/canon authority remains review-only and owner-gated",
        ] if is_blocked_collection_step else [
            "code-mutation opportunity receives a distinct PM job identity tied to its source opportunity",
            "validator routing or proof-drag change is proposed only after targeted timing/proof evidence",
            "normal implementation validation remains quality-preserving and review-only",
            "finance/customer/execution/canon authority remains review-only and owner-gated",
        ]
        base.update(
            {
                "route_status": "pm_job_candidate",
                "route": route_name,
                "pm_job_id": job_id,
                "implementation_class": implementation_class,
                "owner_surface": owner_surface,
                "proof_commands": CODE_MUTATION_REPAIR_PROOF,
                "current_signal_state": {
                    "classification": "implementation_lane_required",
                    "source": "tmp/wf74-improvement-opportunity-queue.json",
                    "validation_command": opportunity.get("validation_command"),
                },
                "acceptance_criteria": acceptance_criteria,
            }
        )
    elif category == "finance_mutation" and (
        "source-open blockers" in title or opportunity.get("signal") == "wf74_scorecard_blocked_by_finance_source_open"
    ):
        evidence = as_dict(opportunity.get("evidence"))
        base.update(
            {
                "route_status": "pm_job_candidate",
                "route": "finance_source_open_quality_repair",
                "pm_job_id": "pm-wf74-finance-source-open-quality-repair",
                "implementation_class": "finance_response_quality_source_open_repair",
                "owner_surface": "Finance response quality slice + WF78/WF85 source-open repair conveyor",
                "proof_commands": FINANCE_SOURCE_OPEN_REPAIR_PROOF,
                "current_signal_state": {
                    "classification": "finance_domain_repair_required",
                    "source": "tmp/finance-response-quality-slice.json",
                    "validation_command": opportunity.get("validation_command"),
                    "source_open_blocked_count": evidence.get("source_open_blocked_count"),
                    "blocker_chain": evidence.get("blocker_chain"),
                    "recommended_department": "finance_wf78_wf84_wf85",
                },
                "acceptance_criteria": [
                    "source-open blocked finance response quality rows are repaired or reduced with explicit source-open proof",
                    "finance_response_quality_slice.py reruns cleanly or reports only exact remaining finance-domain blockers",
                    "wf74_model_quality_collection_cron_runner.py no longer presents this as a runtime/code repair job",
                    "PM job department is finance_wf78_wf84_wf85 with main_session_veritas integration",
                    "finance/customer/execution/canon authority remains review-only and owner-gated",
                ],
            }
        )
    elif category == "workflow_maturity":
        workflow_job_id = (
            "pm-wf74-workflow-blocker-followup-routing"
            if int(priority or 0) >= 80
            else stable_id("pm-wf74-workflow-maturity", source_key)
        )
        base.update(
            {
                "route_status": "pm_job_candidate",
                "route": "workflow_blocker_followup_routing",
                "pm_job_id": workflow_job_id,
                "implementation_class": "wf74_workflow_followup_routing",
                "owner_surface": "WF74 improvement ledger + workflow advancement scorecard",
                "proof_commands": WORKFLOW_ROUTING_PROOF,
                "acceptance_criteria": [
                    "workflow-blocker-followups.json rows are mirrored into durable followup ledger",
                    "valid followups become PM jobs or carry explicit measurement/owner-gated stop reason",
                    "parallel implementation queue can pick proof-only work without widening authority",
                ],
            }
        )
    elif category == "planning_quality":
        planning_job_id = (
            "pm-wf74-planning-followthrough-gap-regression"
            if opportunity.get("completion_status") == "current_regression_after_completion"
            else "pm-wf74-planning-followthrough-gap-reduction"
        )
        base.update(
            {
                "route_status": "pm_job_candidate",
                "route": "planning_followthrough_job",
                "pm_job_id": planning_job_id,
                "implementation_class": "wf74_planning_followthrough",
                "owner_surface": "WF74 coding outcome ledger + lane register",
                "proof_commands": PLANNING_QUALITY_PROOF,
                "acceptance_criteria": [
                    "stale active/leased lanes are closed or blocked with proof",
                    "completed lanes carry proof and acceptance commands",
                    "planning follow-through clean rate improves across WF74 runs",
                ],
            }
        )
    elif category in {"outcome_measurement", "finance_mutation", "collector_config", "execution", "skill_application"}:
        base.update(
            {
                "route_status": "monitor_or_owner_gated",
                "route": f"{category}_guarded_review",
                "blocked_reason": "category is intentionally review/measurement/owner-gated unless a current validator regresses",
                "proof_commands": [str(opportunity.get("validation_command") or "")],
            }
        )
    return base


def route_to_pm_candidate(route: dict[str, Any], rank: int) -> dict[str, Any]:
    job_id = str(route.get("pm_job_id") or stable_id("pm-wf74", route.get("source_key")))
    category = str(route.get("category") or "wf74")
    collision_seed = str(route.get("route") or category)
    if category == "workflow_maturity" and int(route.get("priority") or 0) < 80:
        collision_seed = f"{collision_seed}_{route.get('source_key')}"
    proof_commands = [cmd for cmd in as_list(route.get("proof_commands")) if cmd]
    target_files = [
        "tmp/wf74-autonomy-work-router.json",
        "tmp/improvement-ledger-current.json",
        "tmp/workflow-implementation-followup-ledger.json",
    ]
    if category == "cron_migration":
        target_files.extend(["tmp/cron-control-packet.json", "tmp/cron-migration-repair-plan.json"])
    elif category == "code_mutation":
        target_files.extend([
            "scripts/model_run_ledger.py",
            "scripts/wf74_model_quality_collection_cron_runner.py",
            "scripts/wf74_autonomy_work_router.py",
            "scripts/pm_implementation_job_queue.py",
            "tmp/model-run-ledger-current.json",
            "tmp/wf74-model-quality-collection-cron-runner.json",
            "tmp/cron-control-packet.json",
            "tmp/pm-implementation-job-queue.json",
        ])
    elif category == "finance_mutation":
        target_files.extend([
            "scripts/wf78_source_open_repair_executor.py",
            "scripts/wf78_source_open_work_packet.py",
            "scripts/finance_response_quality_slice.py",
            "scripts/wf74_model_quality_collection_cron_runner.py",
            "tmp/finance-response-quality-slice.json",
            "tmp/wf78-source-open-repair-executor.json",
            "tmp/wf78-source-open-work-packet.json",
            "tmp/wf74-model-quality-collection-cron-runner.json",
            "tmp/pm-implementation-job-queue.json",
        ])
    elif category == "planning_quality":
        target_files.extend(["tmp/coding-outcome-ledger-current.json", "tmp/concurrent-lane-status.json"])
    else:
        target_files.extend(["tmp/workflow-blocker-followups.json", "state/workflow-implementation-followup-ledger.jsonl"])
    implementation_class = str(route.get("implementation_class") or "wf74_autonomy_routing")
    owner_surface = str(route.get("owner_surface") or "WF74 improvement ledger")
    lane_id = str(route.get("route") or category)
    status = "ready_for_main_or_helper"
    candidate = {
        "schema": "veritas.wf74_pm_job_candidate.v1",
        "job_id": job_id,
        "rank": rank,
        "priority": priority_band(route.get("priority")),
        "status": status,
        "source": "wf74_autonomy_work_router",
        "source_key": route.get("source_key"),
        "source_category": category,
        "completion_status": route.get("completion_status"),
        "prior_completion": route.get("prior_completion"),
        "lane_id": lane_id,
        "lane_status": "ready",
        "title": str(route.get("title") or job_id),
        "objective": str(route.get("recommended_action") or route.get("title") or job_id),
        "implementation_class": implementation_class,
        "owner_surface": owner_surface,
        **department_contract(category, implementation_class, owner_surface, lane_id, status),
        "target_files": sorted(dict.fromkeys(target_files)),
        "collision_group": f"wf74_{collision_seed}",
        "dependencies": [
            "WF74 improvement ledger must be current enough to route recommendations",
            "main session remains final integrator",
            "cron may run proof-only jobs only when PM automation capabilities allow it",
        ],
        "proof_commands": proof_commands,
        "acceptance_criteria": as_list(route.get("acceptance_criteria")),
        "helper_role": f"WF74 {category} follow-through helper",
        "stop_lines": GLOBAL_STOP_LINES,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    for key in ("recommendation_id", "origin_opportunity_id", "lifecycle_id"):
        value = route.get(key)
        if value is not None and str(value).strip():
            candidate[key] = value
    review_event_ref = metadata_only_review_event_ref(
        route.get("review_event_ref"),
        lifecycle_id=str(route.get("lifecycle_id") or ""),
        recommendation_id=str(route.get("recommendation_id") or route.get("source_key") or ""),
    )
    if review_event_ref is not None:
        candidate["review_event_ref"] = review_event_ref
    return candidate


def recommendation_action_ledger(
    opportunities: list[dict[str, Any]],
    opportunity_routes: list[dict[str, Any]],
    pm_candidates: list[dict[str, Any]],
    workflow_followups: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    routes_by_key = {str(row.get("source_key")): row for row in opportunity_routes}
    jobs_by_source: dict[str, dict[str, Any]] = {}
    for row in pm_candidates:
        if row.get("source") != "wf74_autonomy_work_router":
            continue
        for source_key in unique_strings([row.get("source_key")] + as_list(row.get("merged_source_keys"))):
            jobs_by_source[source_key] = row
    rows: list[dict[str, Any]] = []
    for opportunity in opportunities:
        source_key = str(opportunity.get("opportunity_id") or stable_id("opportunity", opportunity.get("category"), opportunity.get("title")))
        route = as_dict(routes_by_key.get(source_key))
        job = as_dict(jobs_by_source.get(source_key))
        route_status = str(route.get("route_status") or "not_routed")
        if route_status == "pm_job_candidate":
            status = "routed_to_pm"
            action_taken = "pm_job_candidate_created"
            next_action = "PM dispatcher or main session should run the listed proof commands and close or update the job with validator evidence."
        elif route_status == "monitor_or_owner_gated":
            status = "monitor_or_owner_gated"
            action_taken = "kept_review_only"
            next_action = str(route.get("blocked_reason") or "Continue monitoring until a validator regression or owner decision makes it actionable.")
        else:
            status = "open_unrouted"
            action_taken = "none"
            next_action = str(opportunity.get("recommended_action") or "Classify and route this recommendation.")
        raw_proof_commands = [
            cmd for cmd in as_list(job.get("proof_commands") or route.get("proof_commands") or [opportunity.get("validation_command")])
            if cmd
        ]
        if route_status == "monitor_or_owner_gated":
            safe_proof_commands = []
            blocked_proof_commands = raw_proof_commands
        else:
            safe_proof_commands = [cmd for cmd in raw_proof_commands if command_is_wf74_proof_safe(str(cmd))]
            blocked_proof_commands = [cmd for cmd in raw_proof_commands if not command_is_wf74_proof_safe(str(cmd))]
        lifecycle_id = str(
            route.get("lifecycle_id")
            or opportunity.get("lifecycle_id")
            or lifecycle_id_for_origin(opportunity.get("origin_opportunity_id") or source_key)
        )
        origin_opportunity_id = str(route.get("origin_opportunity_id") or opportunity.get("origin_opportunity_id") or source_key)
        action_row = {
            "schema": "veritas.wf74_recommendation_action_ledger.row.v1",
            "recommendation_id": source_key,
            "opportunity_id": source_key,
            "origin_opportunity_id": origin_opportunity_id,
            "lifecycle_id": lifecycle_id,
            "priority": opportunity.get("priority"),
            "priority_band": priority_band(opportunity.get("priority")),
            "category": opportunity.get("category"),
            "title": opportunity.get("title"),
            "recommendation": opportunity.get("recommended_action"),
            "details": opportunity.get("details"),
            "proposal_gate": opportunity.get("proposal_gate"),
            "validation_command": opportunity.get("validation_command"),
            "route_status": route_status,
            "route": route.get("route"),
            "status": status,
            "action_taken": action_taken,
            "pm_job_id": job.get("job_id") or route.get("pm_job_id"),
            "implementation_class": job.get("implementation_class") or route.get("implementation_class"),
            "department": job.get("department"),
            "department_owner": job.get("department_owner"),
            "owner_workflow": job.get("owner_workflow"),
            "accountable_integrator": job.get("accountable_integrator"),
            "allowed_execution_mode": job.get("allowed_execution_mode"),
            "proof_commands": safe_proof_commands,
            "owner_gated_or_unsafe_commands": blocked_proof_commands,
            "next_action": next_action,
            "source_artifacts": [
                "tmp/wf74-improvement-opportunity-queue.json",
                "tmp/wf74-autonomy-work-router.json",
            ],
            "owner": "main_session" if route_status == "pm_job_candidate" else "review_or_owner_gate",
            "last_updated_at_utc": utc_now(),
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        review_event_ref = metadata_only_review_event_ref(
            route.get("review_event_ref") or opportunity.get("review_event_ref"),
            lifecycle_id=lifecycle_id,
            recommendation_id=source_key,
        )
        if review_event_ref is not None:
            action_row["review_event_ref"] = review_event_ref
        rows.append(action_row)
    for followup in workflow_followups or []:
        proof_commands = [
            cmd for cmd in as_list(followup.get("proof_commands"))
            if cmd and command_is_wf74_proof_safe(str(cmd))
        ]
        blocked_proof_commands = [
            cmd for cmd in as_list(followup.get("proof_commands"))
            if cmd and not command_is_wf74_proof_safe(str(cmd))
        ]
        rows.append({
            "schema": "veritas.wf74_recommendation_action_ledger.row.v1",
            "recommendation_id": str(followup.get("followup_id") or followup.get("source_key")),
            "opportunity_id": None,
            "priority": followup.get("priority"),
            "priority_band": str(followup.get("priority") or "P2"),
            "category": "workflow_blocker_followup",
            "title": followup.get("title"),
            "recommendation": followup.get("objective"),
            "details": followup.get("source_followup"),
            "proposal_gate": "main_review_required" if followup.get("status") != "ready_for_review" else "measurement_only",
            "validation_command": None,
            "route_status": "pm_job_candidate",
            "route": followup.get("route"),
            "status": "routed_to_pm",
            "action_taken": "workflow_followup_pm_job_candidate_created",
            "pm_job_id": followup.get("pm_job_id"),
            "implementation_class": followup.get("implementation_class"),
            "department": followup.get("department"),
            "department_owner": followup.get("department_owner"),
            "owner_workflow": followup.get("owner_workflow"),
            "accountable_integrator": followup.get("accountable_integrator"),
            "allowed_execution_mode": followup.get("allowed_execution_mode"),
            "proof_commands": proof_commands,
            "owner_gated_or_unsafe_commands": blocked_proof_commands,
            "next_action": "PM dispatcher or main session should run the listed proof commands and close or update the workflow followup with validator evidence.",
            "source_artifacts": [
                "tmp/workflow-blocker-followups.json",
                "tmp/workflow-implementation-followup-ledger.json",
                "tmp/wf74-autonomy-work-router.json",
            ],
            "owner": "main_session",
            "last_updated_at_utc": utc_now(),
            "authority_boundary": AUTHORITY_BOUNDARY,
        })
    return rows


def followup_route(followup: dict[str, Any], rank: int) -> dict[str, Any]:
    followup_id = str(followup.get("followup_id") or stable_id("followup", followup.get("workflow_id"), rank))
    route = str(followup.get("route") or "workflow_followup")
    validators = [cmd for cmd in as_list(followup.get("acceptance_validators")) if cmd]
    proof_commands = validators[:]
    router_command = "python scripts\\wf74_autonomy_work_router.py --write --validate"
    if router_command not in proof_commands:
        proof_commands.append(router_command)
    status = "ready_for_review" if route == "measurement_only" else "ready_for_main_or_helper"
    implementation_class = {
        "maturity_accrual": "wf74_workflow_maturity_followup",
        "measurement_only": "wf74_workflow_measurement_followup",
        "dependency_rollup": "wf74_dependency_rollup",
    }.get(route, "wf74_workflow_followup")
    owner_surface = str(followup.get("owner") or "workflow advancement scorecard")
    return {
        "schema": "veritas.workflow_implementation_followup.v1",
        "followup_id": followup_id,
        "source_type": "workflow_blocker_followup",
        "source_key": followup_id,
        "workflow_id": followup.get("workflow_id"),
        "route": route,
        "followup_type": followup.get("followup_type"),
        "blocker_class": followup.get("blocker_class"),
        "title": f"{followup.get('workflow_id') or 'Workflow'} followup: {followup.get('next_action') or route}",
        "owner": followup.get("owner"),
        "pm_job_id": stable_id("pm-wf74-followup", followup_id),
        "priority": "P2" if route != "dependency_rollup" else "P1",
        "status": status,
        "implementation_class": implementation_class,
        "owner_surface": owner_surface,
        **department_contract("workflow_blocker_followup", implementation_class, owner_surface, route, status),
        "target_files": sorted(dict.fromkeys([str(item) for item in as_list(followup.get("source_artifacts"))] + [
            "tmp/workflow-blocker-followups.json",
            "tmp/workflow-implementation-followup-ledger.json",
        ])),
        "collision_group": f"workflow_followup_{followup.get('workflow_id') or followup_id}".lower(),
        "objective": str(followup.get("next_action") or "Advance workflow followup with proof-only validators."),
        "proof_commands": proof_commands,
        "acceptance_criteria": [
            "listed acceptance validators pass or the followup carries an exact blocker",
            "workflow advancement scorecard updates the blocker state",
            "no execution/capital/runtime authority expands from measurement proof",
        ],
        "stop_lines": sorted(set(GLOBAL_STOP_LINES + [str(item) for item in as_list(followup.get("stop_lines"))])),
        "source_followup": followup,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def followup_to_pm_candidate(followup: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "schema": "veritas.wf74_pm_job_candidate.v1",
        "job_id": followup["pm_job_id"],
        "rank": rank,
        "priority": followup["priority"],
        "status": followup["status"],
        "source": "wf74_autonomy_work_router",
        "source_key": followup["source_key"],
        "source_category": "workflow_blocker_followup",
        "lane_id": str(followup.get("route") or "workflow_followup"),
        "lane_status": "ready",
        "title": followup["title"],
        "objective": followup["objective"],
        "implementation_class": followup["implementation_class"],
        "owner_surface": followup["owner_surface"],
        "department": followup["department"],
        "department_owner": followup["department_owner"],
        "owner_workflow": followup["owner_workflow"],
        "accountable_integrator": followup["accountable_integrator"],
        "allowed_execution_mode": followup["allowed_execution_mode"],
        "target_files": followup["target_files"],
        "collision_group": followup["collision_group"],
        "dependencies": [
            "workflow-blocker-followups.json must remain validator-clean",
            "main session remains final integrator",
            "measurement-only followups must not become execution readiness claims",
        ],
        "proof_commands": followup["proof_commands"],
        "acceptance_criteria": followup["acceptance_criteria"],
        "helper_role": f"Workflow followup helper for {followup.get('workflow_id') or followup.get('route')}",
        "stop_lines": followup["stop_lines"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def merge_pm_job_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold repeated WF74 signals into one PM job without losing source context."""
    merged_by_id: dict[str, dict[str, Any]] = {}
    merged: list[dict[str, Any]] = []
    for candidate in candidates:
        job_id = str(candidate.get("job_id") or "").strip()
        if not job_id:
            merged.append(candidate)
            continue
        if job_id not in merged_by_id:
            row = dict(candidate)
            row["merged_source_keys"] = unique_strings([row.get("source_key")])
            row["merged_source_categories"] = unique_strings([row.get("source_category")])
            row["merged_duplicate_count"] = 0
            merged_by_id[job_id] = row
            merged.append(row)
            continue
        existing = merged_by_id[job_id]
        existing["merged_duplicate_count"] = int(existing.get("merged_duplicate_count") or 0) + 1
        existing["merged_source_keys"] = unique_strings(
            as_list(existing.get("merged_source_keys")) + [candidate.get("source_key")]
        )
        existing["merged_source_categories"] = unique_strings(
            as_list(existing.get("merged_source_categories")) + [candidate.get("source_category")]
        )
        for key in ("target_files", "dependencies", "proof_commands", "acceptance_criteria", "stop_lines"):
            existing[key] = unique_strings(as_list(existing.get(key)) + as_list(candidate.get(key)))
        existing["merged_titles"] = unique_strings(
            as_list(existing.get("merged_titles")) + [existing.get("title"), candidate.get("title")]
        )
        existing["merged_objectives"] = unique_strings(
            as_list(existing.get("merged_objectives")) + [existing.get("objective"), candidate.get("objective")]
        )
    return merged


def build_cron_repair_plan(
    opportunity_routes: list[dict[str, Any]],
    cron_state: dict[str, Any],
    opportunity_queue: dict[str, Any],
    workflow_followups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cron_routes = [row for row in opportunity_routes if row.get("category") == "cron_migration"]
    active_routes = [row for row in cron_routes if row.get("route_status") == "pm_job_candidate"]
    cron_followups = [
        row for row in as_list(workflow_followups)
        if isinstance(row, dict) and row.get("route") == "cron_migration"
    ]
    evidence = as_dict(cron_routes[0].get("current_signal_state")) if cron_routes else cron_state
    opportunity = active_routes[0] if active_routes else (cron_routes[0] if cron_routes else {})
    escalation_signals = as_list(evidence.get("escalation_signals"))
    blocked_artifacts = as_list(evidence.get("blocked_artifacts"))
    live_scheduler_exceptions = as_list(evidence.get("live_scheduler_last_run_exceptions"))
    active_repair = evidence.get("classification") == "active_repair_plan_required" and (
        bool(active_routes)
        or bool(cron_followups)
        or bool(escalation_signals)
        or bool(blocked_artifacts)
        or int(evidence.get("blocked_artifact_count") or 0) > 0
    )
    source_opportunity_id = opportunity.get("source_key")
    if not source_opportunity_id and cron_followups:
        source_opportunity_id = cron_followups[0].get("followup_id")
    repair_steps = [
        {
            "step": "refresh_current_truth",
            "command": "python scripts\\cron_control_packet.py --write --validate",
            "done_means": "current blocked/escalation state is measured from live cron control proof",
        },
        {
            "step": "inspect_blocked_artifacts",
            "artifacts": blocked_artifacts,
            "done_means": (
                "each blocked artifact is classified as a proof bug, owner-gated residue, "
                "stale warning, or real implementation repair before any schedule/config change is considered"
            ),
        },
        {
            "step": "inspect_live_scheduler_exceptions",
            "scheduler_exceptions": live_scheduler_exceptions,
            "done_means": (
                "last-run errors are reconciled against artifact freshness so transient scheduler errors "
                "do not become hidden cron blockers"
            ),
        },
        {
            "step": "route_or_close_residue",
            "command": "python scripts\\wf74_autonomy_work_router.py --write --validate",
            "done_means": "cron residue is either converted into a PM job or classified green by current proof",
        },
        {
            "step": "handoff_to_pm",
            "command": "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
            "done_means": "main/cron dispatcher can see the repair-plan job with proof-only commands",
        },
    ] if active_repair else [
        {
            "step": "monitor_current_truth",
            "command": "python scripts\\cron_control_packet.py --write --validate",
            "done_means": "cron remains blocked=0, escalation=0, and should_wake_main_session=false",
        },
        {
            "step": "keep_residue_non_actionable",
            "command": "python scripts\\wf74_autonomy_work_router.py --write --validate",
            "done_means": "warning-grade cron residue is visible without PM repair-job creation",
        },
    ]
    return {
        "schema": "veritas.cron_migration_repair_plan.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_main_session" if active_repair else "monitor_only",
        "classification": evidence.get("classification"),
        "purpose": (
            "Review-only repair-plan handoff for active blocked/escalated cron signals surfaced by WF74."
            if active_repair
            else "Monitor-only proof that WF74 cron residue is warning-grade and not an active repair job."
        ),
        "source_opportunity_id": source_opportunity_id,
        "source_status": {
            "wf74_improvement_opportunity_queue": opportunity_queue.get("status"),
            "cron_signal_state": evidence,
            "workflow_cron_followup_count": len(cron_followups),
        },
        "safe_repair_available": evidence.get("safe_repair_available") is True,
        "active_repair_required": active_repair,
        "escalation_signal_count": evidence.get("escalation_signal_count"),
        "blocked_artifact_count": evidence.get("blocked_artifact_count"),
        "live_scheduler_last_run_exception_count": evidence.get("live_scheduler_last_run_exception_count"),
        "escalation_signals": escalation_signals,
        "blocked_artifacts": blocked_artifacts,
        "live_scheduler_last_run_exceptions": live_scheduler_exceptions,
        "repair_steps": repair_steps,
        "blocked_reason_if_not_auto_fixable": (
            "Cron schedule/config mutation needs exact owner-approved diff, rollback proof, and post-change cron validation."
        ),
        "stop_lines": GLOBAL_STOP_LINES,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def read_existing_fingerprints(path: Path) -> set[str]:
    seen: set[str] = set()
    if not path.exists():
        return seen
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("event_fingerprint"):
            seen.add(str(row["event_fingerprint"]))
    return seen


def ledger_event(row: dict[str, Any]) -> dict[str, Any]:
    event_fp = fingerprint(row.get("source_type"), row.get("source_key"), row.get("pm_job_id"), row.get("status"))
    event = dict(row)
    event.update(
        {
            "schema": "veritas.workflow_implementation_followup_event.v1",
            "recorded_at_utc": utc_now(),
            "event_fingerprint": event_fp,
            "history_action": "route_or_refresh",
        }
    )
    return event


def write_jsonl_events(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = read_existing_fingerprints(path)
    new_rows = [ledger_event(row) for row in rows]
    append_rows = [row for row in new_rows if str(row.get("event_fingerprint")) not in seen]
    if append_rows:
        with path.open("a", encoding="utf-8") as handle:
            for row in append_rows:
                handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return len(append_rows)


def safe_command_findings(commands: list[Any], context: str) -> list[str]:
    return [f"{context}:{command}" for command in commands if command and not command_is_wf74_proof_safe(str(command))]


def command_is_wf74_proof_safe(command: str) -> bool:
    normalized = " ".join(command.strip().lower().split())
    if not command_is_review_only_safe(command):
        return False
    if not (normalized.startswith("python scripts\\") or normalized.startswith("python scripts/")):
        return False
    return " --validate" in f" {normalized}"


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    cron_state = as_dict(payload.get("cron_migration_repair_plan")).get("classification")
    cron_repair_routed = int(as_dict(payload.get("summary")).get("cron_repair_plan_count") or 0) > 0
    required_sources = {
        "wf74_improvement_opportunity_queue",
        "improvement_ledger",
        "workflow_blocker_followups",
        "cron_control_packet",
        "pm_control_packet",
        "coding_outcome_ledger",
    }
    for row in as_list(payload.get("source_status")):
        name = Path(str(row.get("path") or "")).name
        source_key = {
            "wf74-improvement-opportunity-queue.json": "wf74_improvement_opportunity_queue",
            "improvement-ledger-current.json": "improvement_ledger",
            "workflow-blocker-followups.json": "workflow_blocker_followups",
            "cron-control-packet.json": "cron_control_packet",
            "pm-control-packet.json": "pm_control_packet",
            "coding-outcome-ledger-current.json": "coding_outcome_ledger",
        }.get(name)
        if source_key in required_sources:
            if row.get("exists") is not True:
                errors.append(f"required_source_missing:{source_key}")
            if row.get("status") not in {"ok", "warning"}:
                if source_key == "cron_control_packet" and cron_state == "active_repair_plan_required" and cron_repair_routed:
                    warnings.append(f"required_source_status_active_repair_routed:{source_key}:{row.get('status')}")
                else:
                    errors.append(f"required_source_status_not_ok:{source_key}:{row.get('status')}")
    if cron_state == "unknown_blocked":
        errors.append("cron_truth_missing_or_unknown")
    routed = as_list(payload.get("opportunity_routes"))
    pm_candidates = as_list(payload.get("pm_job_candidates"))
    followups = as_list(payload.get("workflow_implementation_followups"))
    action_ledger = as_list(payload.get("recommendation_action_ledger"))
    summary = as_dict(payload.get("summary"))
    cron_plan = as_dict(payload.get("cron_migration_repair_plan"))
    for row in routed:
        route = as_dict(row)
        source_key = str(route.get("source_key") or "")
        lifecycle_id = str(route.get("lifecycle_id") or "")
        origin_opportunity_id = str(route.get("origin_opportunity_id") or "")
        if not source_key or not lifecycle_id or not origin_opportunity_id:
            errors.append(f"route_missing_lifecycle_identity:{source_key or 'unknown'}")
        review_event_ref = route.get("review_event_ref")
        if review_event_ref is not None and metadata_only_review_event_ref(
            review_event_ref,
            lifecycle_id=lifecycle_id,
            recommendation_id=str(route.get("recommendation_id") or source_key),
        ) is None:
            errors.append(f"route_invalid_review_event_ref:{source_key or 'unknown'}")
    for category in ROUTED_CATEGORIES:
        if int(summary.get(f"{category}_routable_count") or 0) and not any(
            row.get("category") == category and row.get("route_status") == "pm_job_candidate" for row in routed
        ):
            errors.append(f"routable_category_not_pm_routed:{category}")
    if cron_plan.get("active_repair_required") is True:
        if int(cron_plan.get("escalation_signal_count") or 0) > 0 and not as_list(cron_plan.get("escalation_signals")):
            errors.append("active_cron_repair_missing_escalation_signal_details")
        if int(cron_plan.get("blocked_artifact_count") or 0) > 0 and not as_list(cron_plan.get("blocked_artifacts")):
            errors.append("active_cron_repair_missing_blocked_artifact_details")
        if int(cron_plan.get("live_scheduler_last_run_exception_count") or 0) > 0 and not as_list(cron_plan.get("live_scheduler_last_run_exceptions")):
            warnings.append("active_cron_repair_missing_live_scheduler_exception_details")
        step_names = {str(row.get("step")) for row in as_list(cron_plan.get("repair_steps")) if isinstance(row, dict)}
        if not {"inspect_blocked_artifacts", "inspect_live_scheduler_exceptions"}.issubset(step_names):
            errors.append("active_cron_repair_missing_inspection_steps")
    if int(summary.get("routable_opportunity_count") or 0) and summary.get("recommendation_to_route_conversion_rate") != 1.0:
        errors.append("not_all_routable_recommendations_were_routed")
    if int(summary.get("pm_job_candidate_count") or 0) < int(summary.get("routed_opportunity_count") or 0):
        errors.append("routed_opportunity_missing_pm_candidate")
    expected_action_rows = int(summary.get("opportunity_count") or 0) + int(summary.get("workflow_followup_count") or 0)
    if len(action_ledger) != expected_action_rows:
        errors.append("recommendation_action_ledger_missing_rows")
    if int(summary.get("open_unrouted_recommendation_count") or 0):
        warnings.append("recommendation_action_ledger_has_open_unrouted_rows")
    for row in action_ledger:
        if not row.get("recommendation_id") or not row.get("status") or not row.get("next_action"):
            errors.append(f"recommendation_action_ledger_row_incomplete:{row.get('recommendation_id')}")
        unsafe = safe_command_findings(as_list(row.get("proof_commands")), str(row.get("recommendation_id")))
        if unsafe:
            errors.extend([f"unsafe_recommendation_action_command:{item}" for item in unsafe])
        if row.get("category") != "workflow_blocker_followup":
            lifecycle_id = str(row.get("lifecycle_id") or "")
            if not lifecycle_id or not str(row.get("origin_opportunity_id") or ""):
                errors.append(f"recommendation_action_missing_lifecycle_identity:{row.get('recommendation_id')}")
            review_event_ref = row.get("review_event_ref")
            if review_event_ref is not None and metadata_only_review_event_ref(
                review_event_ref,
                lifecycle_id=lifecycle_id,
                recommendation_id=str(row.get("recommendation_id") or ""),
            ) is None:
                errors.append(f"recommendation_action_invalid_review_event_ref:{row.get('recommendation_id')}")
    job_ids = [str(row.get("job_id")) for row in pm_candidates]
    if len(job_ids) != len(set(job_ids)):
        errors.append("duplicate_pm_job_candidate_ids")
    for row in pm_candidates:
        if not as_list(row.get("proof_commands")):
            errors.append(f"pm_candidate_missing_proof:{row.get('job_id')}")
        if not as_list(row.get("acceptance_criteria")):
            errors.append(f"pm_candidate_missing_acceptance:{row.get('job_id')}")
        for key in ("department", "department_owner", "owner_workflow", "accountable_integrator", "allowed_execution_mode"):
            if not str(row.get(key) or "").strip():
                errors.append(f"pm_candidate_missing_department_contract:{row.get('job_id')}:{key}")
        if row.get("accountable_integrator") != "main_session_veritas":
            errors.append(f"pm_candidate_non_main_integrator:{row.get('job_id')}:{row.get('accountable_integrator')}")
        if row.get("department") not in DEPARTMENT_OWNER_BY_DEPARTMENT:
            errors.append(f"pm_candidate_unknown_department:{row.get('job_id')}:{row.get('department')}")
        unsafe = safe_command_findings(as_list(row.get("proof_commands")), str(row.get("job_id")))
        if unsafe:
            errors.extend([f"unsafe_pm_candidate_command:{item}" for item in unsafe])
        if as_dict(row.get("authority_boundary")) != AUTHORITY_BOUNDARY:
            errors.append(f"pm_candidate_authority_changed:{row.get('job_id')}")
        if row.get("source_category") != "workflow_blocker_followup":
            lifecycle_id = str(row.get("lifecycle_id") or "")
            if not lifecycle_id or not str(row.get("origin_opportunity_id") or ""):
                errors.append(f"pm_candidate_missing_lifecycle_identity:{row.get('job_id')}")
            review_event_ref = row.get("review_event_ref")
            if review_event_ref is not None and metadata_only_review_event_ref(
                review_event_ref,
                lifecycle_id=lifecycle_id,
                recommendation_id=str(row.get("recommendation_id") or row.get("source_key") or ""),
            ) is None:
                errors.append(f"pm_candidate_invalid_review_event_ref:{row.get('job_id')}")
    for row in followups:
        if not row.get("pm_job_id"):
            errors.append(f"followup_missing_pm_job_id:{row.get('followup_id')}")
        for key in ("department", "department_owner", "owner_workflow", "accountable_integrator", "allowed_execution_mode"):
            if not str(row.get(key) or "").strip():
                errors.append(f"followup_missing_department_contract:{row.get('followup_id')}:{key}")
        if not as_list(row.get("proof_commands")):
            warnings.append(f"followup_missing_proof:{row.get('followup_id')}")
    if cron_plan.get("safe_repair_available") is True:
        warnings.append("cron_repair_plan_safe_repair_available_true_verify_before_execution")
    if any(as_dict(payload.get("authority_boundary")).get(key) for key in (
        "auto_fix_allowed",
        "auto_apply_allowed",
        "cron_schedule_mutation_allowed",
        "runtime_config_mutation_allowed",
        "paper_or_live_execution_allowed",
    )):
        errors.append("forbidden_authority_enabled")
    return {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    opportunity_path = workspace_path(args.opportunity_queue, DEFAULT_OPPORTUNITY_QUEUE)
    improvement_path = workspace_path(args.improvement_ledger, DEFAULT_IMPROVEMENT_LEDGER)
    workflow_followups_path = workspace_path(args.workflow_followups, DEFAULT_WORKFLOW_FOLLOWUPS)
    cron_control_path = workspace_path(args.cron_control, DEFAULT_CRON_CONTROL)
    pm_control_path = workspace_path(args.pm_control, DEFAULT_PM_CONTROL)
    coding_outcome_path = workspace_path(args.coding_outcome, DEFAULT_CODING_OUTCOME)

    opportunity_queue = load_json(opportunity_path)
    improvement_ledger = load_json(improvement_path)
    workflow_followups_packet = load_json(workflow_followups_path)
    cron_control = load_json(cron_control_path)
    pm_control = load_json(pm_control_path)
    coding_outcome = load_json(coding_outcome_path)

    cron_state = cron_current_state(cron_control)
    opportunities = [row for row in as_list(opportunity_queue.get("opportunities")) if isinstance(row, dict)]
    opportunity_routes = [opportunity_route(row, cron_state) for row in opportunities]
    routed_opportunity_routes = [row for row in opportunity_routes if row.get("route_status") == "pm_job_candidate"]
    workflow_followups = [
        followup_route(row, index)
        for index, row in enumerate(as_list(workflow_followups_packet.get("followups")), start=1)
        if isinstance(row, dict)
    ]
    pm_candidates: list[dict[str, Any]] = []
    for index, row in enumerate(routed_opportunity_routes, start=1):
        pm_candidates.append(route_to_pm_candidate(row, index))
    base_rank = len(pm_candidates)
    for index, row in enumerate(workflow_followups, start=1):
        pm_candidates.append(followup_to_pm_candidate(row, base_rank + index))
    raw_pm_candidate_count = len(pm_candidates)
    pm_candidates = merge_pm_job_candidates(pm_candidates)
    merged_pm_candidate_duplicate_count = raw_pm_candidate_count - len(pm_candidates)
    action_ledger = recommendation_action_ledger(opportunities, opportunity_routes, pm_candidates, workflow_followups)

    routable_routes = [row for row in routed_opportunity_routes if str(row.get("category")) in ROUTED_CATEGORIES]
    routed_categories = {str(row.get("category")) for row in routed_opportunity_routes}
    cron_repair_plan = build_cron_repair_plan(opportunity_routes, cron_state, opportunity_queue, workflow_followups)
    cron_repair_plan_count = len([row for row in routed_opportunity_routes if row.get("category") == "cron_migration"])
    if cron_repair_plan.get("active_repair_required") and cron_repair_plan_count == 0:
        cron_repair_plan_count = 1
    improvement_summary = as_dict(improvement_ledger.get("summary"))
    planning_signal = as_dict(as_dict(coding_outcome.get("ledger_summary")).get("planning_quality_signal"))
    planning_projection = project_planning_signal(planning_signal)
    pm_summary = as_dict(pm_control.get("summary"))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Convert WF74 recommendations into durable repair plans, workflow followups, and PM job candidates.",
        "posture": "review_only_router",
        "sources": {
            "wf74_improvement_opportunity_queue": rel(opportunity_path),
            "improvement_ledger": rel(improvement_path),
            "workflow_blocker_followups": rel(workflow_followups_path),
            "cron_control_packet": rel(cron_control_path),
            "pm_control_packet": rel(pm_control_path),
            "coding_outcome_ledger": rel(coding_outcome_path),
        },
        "source_status": [
            source_status(opportunity_path),
            source_status(improvement_path),
            source_status(workflow_followups_path),
            source_status(cron_control_path),
            source_status(pm_control_path),
            source_status(coding_outcome_path),
        ],
        "summary": {
            "opportunity_count": len(opportunities),
            "routable_opportunity_count": len(routable_routes),
            "routed_opportunity_count": len(routed_opportunity_routes),
            "pm_job_candidate_count": len(pm_candidates),
            "raw_pm_job_candidate_count": raw_pm_candidate_count,
            "merged_pm_job_candidate_duplicate_count": merged_pm_candidate_duplicate_count,
            "workflow_followup_count": len(workflow_followups),
            "cron_repair_plan_count": cron_repair_plan_count,
            "code_mutation_repair_job_count": len([row for row in routed_opportunity_routes if row.get("category") == "code_mutation"]),
            "finance_source_open_repair_job_count": len([
                row for row in routed_opportunity_routes
                if row.get("route") == "finance_source_open_quality_repair"
            ]),
            "planning_followthrough_job_count": len([row for row in routed_opportunity_routes if row.get("category") == "planning_quality"]),
            "code_mutation_routable_count": len([row for row in routable_routes if row.get("category") == "code_mutation"]),
            "finance_mutation_routable_count": len([row for row in routable_routes if row.get("category") == "finance_mutation"]),
            "workflow_maturity_routable_count": len([row for row in routable_routes if row.get("category") == "workflow_maturity"]),
            "cron_migration_routable_count": len([row for row in routable_routes if row.get("category") == "cron_migration"]),
            "planning_quality_routable_count": len([row for row in routable_routes if row.get("category") == "planning_quality"]),
            "recommendation_action_ledger_count": len(action_ledger),
            "recommendation_action_opportunity_row_count": len([row for row in action_ledger if row.get("category") != "workflow_blocker_followup"]),
            "recommendation_action_workflow_followup_row_count": len([row for row in action_ledger if row.get("category") == "workflow_blocker_followup"]),
            "open_unrouted_recommendation_count": len([row for row in action_ledger if row.get("status") == "open_unrouted"]),
            "routed_to_pm_recommendation_count": len([row for row in action_ledger if row.get("status") == "routed_to_pm"]),
            "recommendation_to_route_conversion_rate": round(len(routed_opportunity_routes) / len(routable_routes), 4) if routable_routes else 1.0,
            "route_to_pm_job_conversion_rate": round(len(pm_candidates) / (len(routed_opportunity_routes) + len(workflow_followups)), 4)
            if (len(routed_opportunity_routes) + len(workflow_followups))
            else 1.0,
            "routed_categories": sorted(routed_categories),
            "department_counts": {
                department: len([row for row in pm_candidates if row.get("department") == department])
                for department in sorted({str(row.get("department") or "unknown") for row in pm_candidates})
            },
            "allowed_execution_mode_counts": {
                mode: len([row for row in pm_candidates if row.get("allowed_execution_mode") == mode])
                for mode in sorted({str(row.get("allowed_execution_mode") or "unknown") for row in pm_candidates})
            },
            "cron_signal_classification": cron_state.get("classification"),
            "cron_blocked_count": cron_state.get("blocked_count"),
            "cron_escalation_signal_count": cron_state.get("escalation_signal_count"),
            "cron_should_wake_main_session": cron_state.get("should_wake_main_session"),
            "high_priority_overdue_count": improvement_summary.get("high_priority_overdue_open_count"),
            "top_improvement_age_hours": improvement_summary.get("top_improvement_age_hours"),
            "planning_followthrough_clean_rate": planning_signal.get("plan_followthrough_clean_rate"),
            "planning_followthrough_gap_count": planning_projection["planning_followthrough_gap_count"],
            "planning_followthrough_gap_count_selected": planning_projection["planning_followthrough_gap_count_selected"],
            "planning_followthrough_gap_source": planning_projection["planning_followthrough_gap_source"],
            "planning_followthrough_actionable_gap_count": planning_projection["planning_followthrough_actionable_gap_count"],
            "planning_followthrough_terminal_unavailable_count": planning_projection["planning_followthrough_terminal_unavailable_count"],
            "planning_followthrough_repaired_accepted_count": planning_projection["planning_followthrough_repaired_accepted_count"],
            "planning_partitioned_gap_row_count": planning_projection["planning_partitioned_gap_row_count"],
            "planning_partition_reconciliation_ok": planning_projection["planning_partition_reconciliation_ok"],
            "planning_actionable_status": planning_projection["planning_actionable_status"],
            "planning_signal_schema": planning_projection["planning_signal_schema"],
            "planning_gap_selection_warning": planning_projection["planning_gap_selection_warning"],
            "pm_auto_main_executable_job_count_before_router": pm_summary.get("pm_implementation_queue_summary", {}).get("auto_main_executable_job_count")
            if isinstance(pm_summary.get("pm_implementation_queue_summary"), dict)
            else None,
        },
        "cron_migration_repair_plan": cron_repair_plan,
        "opportunity_routes": opportunity_routes,
        "recommendation_action_ledger": action_ledger,
        "workflow_implementation_followups": workflow_followups,
        "pm_job_candidates": pm_candidates,
        "kpis": {
            "recommendation_to_route_conversion_rate": round(len(routed_opportunity_routes) / len(routable_routes), 4) if routable_routes else 1.0,
            "route_to_pm_job_conversion_rate": round(len(pm_candidates) / (len(routed_opportunity_routes) + len(workflow_followups)), 4)
            if (len(routed_opportunity_routes) + len(workflow_followups))
            else 1.0,
            "pm_job_closure_rate_source": "pm implementation completion ledger",
            "planning_followthrough_gap_count_selected": planning_projection["planning_followthrough_gap_count_selected"],
            "planning_followthrough_gap_source": planning_projection["planning_followthrough_gap_source"],
            "planning_followthrough_actionable_gap_count": planning_projection["planning_followthrough_actionable_gap_count"],
            "planning_actionable_status": planning_projection["planning_actionable_status"],
            "planning_followthrough_clean_rate": planning_signal.get("plan_followthrough_clean_rate"),
            "high_priority_overdue_count": improvement_summary.get("high_priority_overdue_open_count"),
            "average_age_of_top_open_improvement_hours": improvement_summary.get("top_improvement_age_hours"),
            "success_target": {
                "high_priority_overdue_count": 0,
                "stale_active_lanes": 0,
                "planning_followthrough_clean_rate_minimum": 0.75,
                "unrouted_recurring_blockers": 0,
            },
        },
        "next_safe_action": (
            "Run pm_implementation_job_queue.py so main/cron sees routed WF74 jobs; "
            "then let PM dispatcher pick proof-only work by automation capabilities."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = payload["validation"]["status"]
    return payload


def write_outputs(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    out = workspace_path(args.out, DEFAULT_OUT)
    cron_plan = workspace_path(args.cron_repair_plan, DEFAULT_CRON_REPAIR_PLAN)
    followup_ledger = workspace_path(args.followup_ledger, DEFAULT_FOLLOWUP_LEDGER)
    followup_history = workspace_path(args.followup_history, DEFAULT_FOLLOWUP_HISTORY)
    atomic_write_json(out, payload)
    atomic_write_json(cron_plan, payload.get("cron_migration_repair_plan"))
    current_followups = {
        "schema": "veritas.workflow_implementation_followup_ledger.v1",
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "summary": {
            "followup_count": len(as_list(payload.get("workflow_implementation_followups"))),
            "pm_job_candidate_count": len(as_list(payload.get("pm_job_candidates"))),
            "history_path": rel(followup_history),
        },
        "workflow_implementation_followups": payload.get("workflow_implementation_followups"),
        "pm_job_candidates": [
            row for row in as_list(payload.get("pm_job_candidates"))
            if row.get("source_category") == "workflow_blocker_followup"
        ],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": payload.get("validation"),
    }
    atomic_write_json(followup_ledger, current_followups)
    appended = write_jsonl_events(
        followup_history,
        as_list(payload.get("workflow_implementation_followups")) + [
            row for row in as_list(payload.get("opportunity_routes")) if row.get("route_status") == "pm_job_candidate"
        ],
    )
    return {
        "out": rel(out),
        "cron_repair_plan": rel(cron_plan),
        "followup_ledger": rel(followup_ledger),
        "followup_history": rel(followup_history),
        "appended_history_event_count": appended,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route WF74 recommendations into PM jobs and repair plans.")
    parser.add_argument("--opportunity-queue", default=str(DEFAULT_OPPORTUNITY_QUEUE))
    parser.add_argument("--improvement-ledger", default=str(DEFAULT_IMPROVEMENT_LEDGER))
    parser.add_argument("--workflow-followups", default=str(DEFAULT_WORKFLOW_FOLLOWUPS))
    parser.add_argument("--cron-control", default=str(DEFAULT_CRON_CONTROL))
    parser.add_argument("--pm-control", default=str(DEFAULT_PM_CONTROL))
    parser.add_argument("--coding-outcome", default=str(DEFAULT_CODING_OUTCOME))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--cron-repair-plan", default=str(DEFAULT_CRON_REPAIR_PLAN))
    parser.add_argument("--followup-ledger", default=str(DEFAULT_FOLLOWUP_LEDGER))
    parser.add_argument("--followup-history", default=str(DEFAULT_FOLLOWUP_HISTORY))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    write_result = write_outputs(payload, args) if args.write else None
    result = {
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "kpis": payload.get("kpis"),
        "validation": payload.get("validation"),
        "write_result": write_result,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and payload.get("status") not in {"ok", "warning"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
