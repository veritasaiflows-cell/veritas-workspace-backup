#!/usr/bin/env python3
"""Classify WF88/WF74 follow-up debt into durable ledger outcomes.

This packet is deliberately review-only. It decides whether each
``follow_up_required_before_closure`` ledger row has enough current proof to be
closed, must stay open as an active successor/follow-up, or is owner/config
gated. The improvement ledger consumes this packet to append durable closure
events; this script does not mutate cron, config, finance, portfolio, paper, or
live execution state.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf74_improvement_opportunity_queue import select_actionable_planning_gap


def planning_trust_from_router(router_summary: dict[str, Any]) -> dict[str, Any]:
    """Re-verify router-projected partition with the single-source selector.

    Rebuilds the raw signal shape from projected router keys so trust reuses
    wf74_improvement_opportunity_queue.select_actionable_planning_gap instead
    of duplicating its meaning. Schema-exactness is required; the schema is
    carried by the router projection, never invented here.
    """
    projected = {
        "schema": router_summary.get("planning_signal_schema"),
        "plan_followthrough_gap_count": router_summary.get("planning_followthrough_gap_count"),
        "plan_followthrough_actionable_gap_count": router_summary.get("planning_followthrough_actionable_gap_count"),
        "plan_followthrough_terminal_unavailable_count": router_summary.get("planning_followthrough_terminal_unavailable_count"),
        "plan_followthrough_repaired_accepted_count": router_summary.get("planning_followthrough_repaired_accepted_count"),
        "partitioned_gap_row_count": router_summary.get("planning_partitioned_gap_row_count"),
        "partition_reconciliation_ok": router_summary.get("planning_partition_reconciliation_ok"),
    }
    return select_actionable_planning_gap(projected)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf88-followup-debt-triage-packet.json"
MD_OUT = TMP / "wf88-followup-debt-triage-packet.md"
SCHEMA = "veritas.wf88_followup_debt_triage_packet.v1"

IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
WF74_ROUTER = TMP / "wf74-autonomy-work-router.json"
WF74_DOCKET = TMP / "wf74-decision-docket.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
OTEL_OPS = TMP / "otel-ops-control.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
FINANCE_RESPONSE_QUALITY_SLICE = TMP / "finance-response-quality-slice.json"
FINANCE_RESPONSE_QUALITY_REPAIR_LOOP = TMP / "finance-response-quality-repair-loop.json"
WORKFLOW_FOLLOWUPS = TMP / "workflow-blocker-followups.json"
WF87_ROLLUP = TMP / "wf87-v2-readiness-rollup.json"
AUTONOMY_SPINE = TMP / "autonomy-spine-readiness-rollup.json"
VALIDATOR_TIMING = TMP / "validator-timing-ledger.json"
WF88_OS2_CONTROL = TMP / "wf88-os2-control-packet.json"
IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE = TMP / "implementation-token-attribution-bridge.json"

IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE_SCHEMA = "veritas.implementation_token_attribution_bridge.v1"
IMPLEMENTATION_TOKEN_BRIDGE_MAX_AGE_SECONDS = 24.0 * 3600.0
IMPLEMENTATION_TOKEN_BRIDGE_OK_STATUSES = {"ok", "warning"}
IMPLEMENTATION_TOKEN_BRIDGE_OK_VALIDATIONS = {"ok", "warning"}
IMPLEMENTATION_TOKEN_BRIDGE_TERMINAL_RESOLUTIONS = {"terminal_unavailable_only", "historical_or_classified_unavailable_only"}

ALLOWED_CLOSURE_STATUSES = {
    "verified_fix",
    "pending_skill_proposal",
    "applied_skill_proposal",
    "superseded_by_open_improvement",
    "owner_packet_ready_not_applied",
    "monitor_only_drift_currently_absent",
    "historical_terminal_unavailable_claim_limit",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "classification_only": True,
    "ledger_closure_proof_only": True,
    "auto_apply_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def source_record(path: Path) -> dict[str, Any]:
    payload = load(path)
    return {
        "path": rel(path),
        "present": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def source_key(row: dict[str, Any]) -> str:
    return str(row.get("source_key") or "")


def norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def base_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf88_followup_debt_triage_item.v1",
        "source_type": row.get("source_type"),
        "source_key": row.get("source_key"),
        "title": row.get("title"),
        "category": row.get("category"),
        "priority": row.get("priority"),
        "sla_status": row.get("sla_status"),
        "opened_at_utc": row.get("opened_at_utc"),
        "age_hours": row.get("age_hours"),
        "input_decision": row.get("decision"),
        "closure_allowed": False,
        "closure_status": None,
        "action_state": "followup_required",
        "recommended_next_action": row.get("next_action"),
        "proof_artifacts": [],
        "successor_id": None,
        "successor_artifact": None,
        "closure_reason": None,
        "stop_lines": [
            "No auto-apply from this triage packet.",
            "No cron schedule/config/runtime mutation.",
            "No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, or account mutation.",
            "No owner approval inference.",
        ],
    }


def wf88_successor(successor_id: str) -> dict[str, str]:
    return {
        "successor_id": successor_id,
        "successor_artifact": rel(WF88_OS2_CONTROL),
        "successor_artifact_kind": "wf88_canonical_action_state",
    }


def classify_cron(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    cron = ctx["cron_control"]
    summary = as_dict(cron.get("summary"))
    followups = ctx["workflow_followups"]
    has_cron_followup = any(
        as_dict(followup).get("route") == "cron_migration"
        for followup in as_list(followups.get("followups"))
    )
    blocked_count = int_value(summary.get("blocked_count"))
    escalation_count = int_value(summary.get("escalation_signal_count"))
    should_wake = bool(summary.get("should_wake_main_session"))
    cron_green = not blocked_count and not escalation_count and not should_wake
    item.update({
        "action_state": "monitor_only" if cron_green else "active_successor_followup",
        "successor_id": "cron-cron-migration" if has_cron_followup else None,
        "successor_title": "CRON followup: keep scheduled proof running and escalate only on stale/blocked/authority drift.",
        "closure_reason": (
            "Current cron proof still has blocked/escalation state; keep the cron migration follow-up open."
            if not cron_green
            else "Cron control is green; keep the old cron-migration row as monitor-only successor visibility."
        ),
        "recommended_next_action": (
            "Resolve or explicitly route the current cron-control escalation; rerun cron_control_packet and WF74 router after proof changes."
            if not cron_green
            else "Monitor only; cron control is green and escalation is zero. Reopen a repair lane only if cron blocked/escalation state returns."
        ),
        "proof_artifacts": [rel(CRON_CONTROL), rel(WORKFLOW_FOLLOWUPS)],
        "context": {
            "cron_blocked_count": blocked_count,
            "cron_escalation_signal_count": escalation_count,
            "cron_should_wake_main_session": should_wake,
            "workflow_followup_present": has_cron_followup,
        },
    })
    return item


def classify_collector(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    otel = ctx["otel_ops"]
    drift = as_dict(otel.get("drift"))
    summary = as_dict(otel.get("summary"))
    validation_status = as_dict(otel.get("validation")).get("status")
    blocked = otel.get("status") == "blocked" or validation_status == "blocked"
    event_count = int_value(summary.get("event_count"))
    otel_green = (
        not blocked
        and otel.get("status") == "ok"
        and validation_status == "ok"
        and str(drift.get("status") or "") == "ok"
        and int_value(drift.get("daily_warning_or_error_count")) == 0
        and event_count > 0
    )
    item.update({
        "action_state": "monitor_only" if otel_green else "active_operational_drift_review",
        "closure_reason": (
            "Current OTEL ops proof is blocked/review because the recent indexed event window is empty relative to baseline."
            if blocked
            else "OTEL ops is current and drift is clean; keep the old collector-config row as monitor-only operational visibility."
            if otel_green
            else "OTEL event-rate drift is operational monitor-only; closure requires a non-blocked current OTEL packet."
        ),
        "recommended_next_action": (
            "Review OTEL event ingestion/volume as local operations only; do not mutate collector/runtime config without exact owner-approved change proof."
            if not otel_green
            else "Monitor only; OTEL ops is current, validation is clean, and drift is ok. Reopen config review only if current OTEL proof regresses."
        ),
        "proof_artifacts": [rel(OTEL_OPS), rel(CRON_CONTROL)],
        "context": {
            "otel_status": otel.get("status"),
            "otel_validation_status": validation_status,
            "daily_warning_or_error_count": int_value(drift.get("daily_warning_or_error_count")),
            "daily_vs_weekly_event_rate_ratio": drift.get("daily_vs_weekly_event_rate_ratio"),
            "event_count_24h": event_count,
        },
    })
    return item


def classify_outcome(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    wf87 = ctx["wf87_rollup"]
    threshold = as_dict(wf87.get("shadow_threshold"))
    calibration = as_dict(wf87.get("shadow_outcome_calibration"))
    threshold_met = bool(threshold.get("threshold_met"))
    pending_followup = int_value(calibration.get("pending_regular_session_followup_count"))
    if threshold_met and pending_followup == 0:
        item.update({
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "action_state": "close_with_threshold_proof",
            **wf88_successor("wf88-learning-loop-measurement"),
            "closure_reason": "WF87 shadow outcome threshold proof is met and no regular-session follow-up rows are pending.",
            "recommended_next_action": "Close the old threshold-follow-up rows; keep separate WF87 runtime/autonomy blockers visible until their own gates clear.",
            "proof_artifacts": [rel(WF87_ROLLUP), rel(AUTONOMY_SPINE)],
            "context": {
                "threshold_met": threshold_met,
                "pending_regular_session_followup_count": pending_followup,
                "decision_quality_claim_allowed_now": calibration.get("decision_quality_claim_allowed_now"),
                "model_performance_claim_allowed_now": calibration.get("model_performance_claim_allowed_now"),
                "wf87_status": wf87.get("status"),
            },
        })
    else:
        item.update({
            "action_state": "market_session_accrual",
            "closure_reason": "Regular-session threshold proof is not complete in the current WF87 packet.",
            "recommended_next_action": "Continue WF87 shadow outcome scorecard accrual; do not claim decision/model performance.",
            "proof_artifacts": [rel(WF87_ROLLUP), rel(AUTONOMY_SPINE)],
            "context": {
                "threshold_met": threshold_met,
                "pending_regular_session_followup_count": pending_followup,
            },
        })
    return item


def classify_planning(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    router_summary = as_dict(ctx["wf74_router"].get("summary"))
    runner_summary = as_dict(ctx["wf74_runner"].get("summary"))
    gap_count = int_value(router_summary.get("planning_followthrough_gap_count"))
    clean_rate = float_value(router_summary.get("planning_followthrough_clean_rate"))
    history_context = {
        "planning_followthrough_gap_count": gap_count,
        "planning_followthrough_clean_rate": clean_rate,
        "runner_planning_followthrough_gap_count": runner_summary.get("planning_quality_followthrough_gap_count"),
        "planning_followthrough_gap_count_selected": router_summary.get("planning_followthrough_gap_count_selected"),
        "planning_followthrough_gap_source": router_summary.get("planning_followthrough_gap_source"),
        "planning_followthrough_actionable_gap_count": router_summary.get("planning_followthrough_actionable_gap_count"),
        "planning_followthrough_terminal_unavailable_count": router_summary.get("planning_followthrough_terminal_unavailable_count"),
        "planning_followthrough_repaired_accepted_count": router_summary.get("planning_followthrough_repaired_accepted_count"),
        "planning_partitioned_gap_row_count": router_summary.get("planning_partitioned_gap_row_count"),
        "planning_partition_reconciliation_ok": router_summary.get("planning_partition_reconciliation_ok"),
        "planning_actionable_status": router_summary.get("planning_actionable_status"),
        "planning_gap_selection_warning": router_summary.get("planning_gap_selection_warning"),
    }
    partition_keys = (
        "planning_followthrough_gap_count_selected",
        "planning_followthrough_gap_source",
        "planning_followthrough_actionable_gap_count",
        "planning_actionable_status",
    )
    if not any(router_summary.get(key) is not None for key in partition_keys):
        # Legacy pre-partition producer: raw rule preserved verbatim.
        if gap_count == 0 and clean_rate >= 1.0:
            item.update({
                "closure_allowed": True,
                "closure_status": "verified_fix",
                "action_state": "close_with_clean_followthrough_proof",
                **wf88_successor("improvement-ledger-open-followups"),
                "closure_reason": "Planning follow-through proof is clean: gap count is zero and clean rate is 1.0.",
                "recommended_next_action": "Close the stale planning follow-through rows and continue normal WF74/PM monitoring.",
                "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_RUNNER)],
                "context": history_context,
            })
        else:
            item.update({
                "action_state": "planning_followthrough_gap_open",
                "closure_reason": "Planning follow-through proof is not clean.",
                "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_RUNNER)],
                "context": history_context,
            })
        return item
    trust = planning_trust_from_router(router_summary)
    if (
        trust["source"] == "actionable_partition_verified"
        and int(trust["selected_gap_count"]) == 0
        and router_summary.get("planning_actionable_status") == "ok"
    ):
        item.update({
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "action_state": "close_with_verified_zero_actionable_debt",
            **wf88_successor("improvement-ledger-open-followups"),
            "closure_reason": (
                "No actionable planning debt: trusted actionable count is 0 with actionable status ok; "
                "terminal/repaired history is retained and the raw gap is preserved, not rewritten as clean."
            ),
            "recommended_next_action": "Close the stale planning follow-through rows and continue normal WF74/PM monitoring.",
            "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_RUNNER)],
            "context": history_context,
        })
    else:
        item.update({
            "action_state": "planning_followthrough_gap_open",
            "closure_reason": (
                "Planning follow-through partition is untrusted (missing, malformed, or mismatched): "
                "fail closed and keep open; raw gap and history context are preserved."
            ),
            "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_RUNNER)],
            "context": history_context,
        })
    return item


def classify_validator(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    runner_summary = as_dict(ctx["wf74_runner"].get("summary"))
    timing = ctx["validator_timing"]
    elapsed = runner_summary.get("coding_runtime_validator_elapsed_seconds")
    timing_status = timing.get("status")
    timing_validation = as_dict(timing.get("validation")).get("status")
    clean = timing_status == "ok" and timing_validation == "ok" and float_value(elapsed) <= 30.0
    if clean:
        item.update({
            "closure_allowed": True,
            "closure_status": "monitor_only_drift_currently_absent",
            "action_state": "close_as_currently_absent_drag",
            **wf88_successor("improvement-ledger-open-followups"),
            "closure_reason": "Current normal validator timing proof is clean and below the normal-pass drag threshold.",
            "recommended_next_action": "Close as monitor-only; reopen if validator timing or release closeout drag regresses.",
            "proof_artifacts": [rel(WF74_RUNNER), rel(VALIDATOR_TIMING)],
            "context": {
                "validator_elapsed_seconds": elapsed,
                "validator_timing_status": timing_status,
                "validator_timing_validation_status": timing_validation,
            },
        })
    else:
        item.update({
            "action_state": "validator_drag_monitor_open",
            "closure_reason": "Validator timing proof is missing, stale, blocked, or above threshold.",
            "proof_artifacts": [rel(WF74_RUNNER), rel(VALIDATOR_TIMING)],
            "context": {
                "validator_elapsed_seconds": elapsed,
                "validator_timing_status": timing_status,
                "validator_timing_validation_status": timing_validation,
            },
        })
    return item


def classify_wf74_queue(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    router_summary = as_dict(ctx["wf74_router"].get("summary"))
    open_unrouted = int_value(router_summary.get("open_unrouted_recommendation_count"))
    route_rate = float_value(router_summary.get("recommendation_to_route_conversion_rate"))
    pm_candidates = int_value(router_summary.get("pm_job_candidate_count"))
    if open_unrouted == 0 and route_rate >= 1.0:
        item.update({
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "action_state": "close_with_routing_proof",
            **wf88_successor("improvement-ledger-open-followups"),
            "closure_reason": "WF74 router has zero open unrouted recommendations and full recommendation-to-route conversion.",
            "recommended_next_action": "Close the old WF74 queue follow-up row; keep PM/WF74 routed jobs visible through their own packets.",
            "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_DOCKET)],
            "context": {
                "open_unrouted_recommendation_count": open_unrouted,
                "recommendation_to_route_conversion_rate": route_rate,
                "pm_job_candidate_count": pm_candidates,
            },
        })
    else:
        item.update({
            "action_state": "wf74_queue_followup_open",
            "closure_reason": "WF74 router still has unrouted recommendations or incomplete route conversion.",
            "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_DOCKET)],
            "context": {
                "open_unrouted_recommendation_count": open_unrouted,
                "recommendation_to_route_conversion_rate": route_rate,
                "pm_job_candidate_count": pm_candidates,
            },
        })
    return item


def is_finance_response_quality_row(row: dict[str, Any]) -> bool:
    if row.get("category") != "finance_mutation":
        return False
    text = " ".join(
        str(row.get(key) or "")
        for key in ("source_key", "title", "input_decision", "signal", "recommended_next_action")
    ).casefold()
    markers = (
        "finance response quality",
        "finance response-quality",
        "source-open blocker",
        "source_open_blocked",
        "blocked_by_finance_source_open",
    )
    return any(marker in text for marker in markers)


FINANCE_RESPONSE_QUALITY_SLICE_SCHEMA = "veritas.finance_response_quality_slice.v1"
FINANCE_RESPONSE_QUALITY_REPAIR_LOOP_SCHEMA = "veritas.finance_response_quality_repair_loop.v1"

# Review-only evidence must be fresh and fully formed to authorize closure. A
# days-old packet must never read as clean. Missing, malformed, future, stale,
# wrong-schema, or failed-validation evidence fails closed and keeps the
# follow-up open. Missing decisive counters never coerce to clean zero.
FINANCE_EVIDENCE_MAX_AGE_SECONDS = 72.0 * 3600.0
FINANCE_EVIDENCE_OK_VALIDATION_STATUSES = {"ok", "warning"}


def parse_evidence_generated_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evidence_validation_informational(validation: Any) -> bool:
    """Require an explicit validation object with a known-good status.

    Only ``ok`` passes outright; ``warning`` passes only with informational
    warning detail present. Any error entries, blank/unknown/missing status,
    or a missing/non-object validation fails closed.
    """
    if not isinstance(validation, dict):
        return False
    if validation.get("status") not in FINANCE_EVIDENCE_OK_VALIDATION_STATUSES:
        return False
    errors = validation.get("errors")
    if not isinstance(errors, list) or len(errors) != 0:
        return False
    warnings = validation.get("warnings")
    if not isinstance(warnings, list):
        return False
    if validation.get("status") == "warning" and len(warnings) == 0:
        return False
    return True


def required_count(summary: dict[str, Any], key: str) -> tuple[bool, int]:
    """Read a decisive counter without coercing absence to clean zero.

    Returns (False, 0) when the key is missing, boolean, or non-numeric, so a
    missing counter can never satisfy a ``== 0`` cleanliness check.
    """
    if not isinstance(summary, dict) or key not in summary:
        return (False, 0)
    value = summary[key]
    if isinstance(value, bool):
        return (False, 0)
    if isinstance(value, float) and not value.is_integer():
        return (False, 0)
    try:
        return (True, int(value))
    except (TypeError, ValueError):
        return (False, 0)


def finance_evidence_usable(
    artifact: dict[str, Any],
    *,
    expected_schema: str,
    allowed_statuses: set[str],
) -> bool:
    """Fail-closed gate for review-only finance evidence.

    Returns False (keep the follow-up open) when the artifact is missing, has
    an unexpected status, a missing or mismatched schema, a missing or
    non-informational validation object, or a missing, malformed, future, or
    stale generation timestamp. There is no future-timestamp grace.
    """
    if not isinstance(artifact, dict) or not artifact:
        return False
    if artifact.get("status") not in allowed_statuses:
        return False
    if artifact.get("schema") != expected_schema:
        return False
    if not evidence_validation_informational(artifact.get("validation")):
        return False
    generated_at = parse_evidence_generated_at(artifact.get("generated_at_utc"))
    if generated_at is None:
        return False
    now = datetime.now(timezone.utc)
    if generated_at > now:
        return False
    if (now - generated_at).total_seconds() > FINANCE_EVIDENCE_MAX_AGE_SECONDS:
        return False
    return True


def finance_response_quality_proof_clean(ctx: dict[str, dict[str, Any]]) -> bool:
    runner = ctx["wf74_runner"]
    runner_summary = as_dict(runner.get("summary"))
    slice_artifact = ctx["finance_response_quality_slice"]
    repair_artifact = ctx["finance_response_quality_repair_loop"]
    slice_summary = as_dict(slice_artifact.get("summary"))
    repair_summary = as_dict(repair_artifact.get("summary"))
    # The WF74 runner is a generic technical health signal only. The retired
    # pre-pivot keys (finance_response_quality_status and the
    # finance_response_quality_*_count keys) no longer exist in the producer;
    # they are intentionally not read here, and absent keys never default to
    # clean. The retired WF85 reconciliation packet is likewise not read:
    # WF85 old surfaces were retired from the alerts OS, so a blocked WF85
    # packet is structurally obsolete evidence, not a source-quality failure.
    # Finance cleanliness is keyed on the review-only slice and repair-loop
    # packets instead.
    checks: list[bool] = [
        runner.get("status") == "ok",
        required_count(runner_summary, "steps_blocked") == (True, 0),
        finance_evidence_usable(
            slice_artifact,
            expected_schema=FINANCE_RESPONSE_QUALITY_SLICE_SCHEMA,
            allowed_statuses={"ok"},
        ),
    ]
    for key in (
        "blocked_archetype_count",
        "source_open_blocked_count",
        "source_freshness_blocked_count",
        "remediation_tracks_needing_repair",
    ):
        checks.append(required_count(slice_summary, key) == (True, 0))
    checks.append(finance_evidence_usable(
        repair_artifact,
        expected_schema=FINANCE_RESPONSE_QUALITY_REPAIR_LOOP_SCHEMA,
        allowed_statuses={"ok", "noop_ok"},
    ))
    for key in (
        "proposal_count",
        "high_priority_count",
        "source_open_blocked_count",
        "source_freshness_blocked_count",
        "remediation_tracks_needing_repair",
    ):
        checks.append(required_count(repair_summary, key) == (True, 0))
    return all(checks)


def classify_finance_response_quality(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    proof_artifacts = [
        rel(WF74_RUNNER),
        rel(FINANCE_RESPONSE_QUALITY_SLICE),
        rel(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP),
    ]
    if finance_response_quality_proof_clean(ctx):
        item.update({
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "action_state": "close_with_finance_response_quality_clean_proof",
            **wf88_successor("wf85-source-open-repair-queue"),
            "closure_reason": "Fresh review-only slice and repair-loop proof shows zero finance response-quality source-open blockers and zero repair proposals; WF74 runner technical health is ok with zero blocked steps.",
            "recommended_next_action": "Close the stale finance response-quality follow-up row; reopen only if source-open blockers, repair proposals, or stale/failed evidence reappear.",
            "proof_artifacts": proof_artifacts,
            "context": {
                "wf74_steps_blocked": int_value(as_dict(ctx["wf74_runner"].get("summary")).get("steps_blocked")),
                "source_open_blocked_count": int_value(as_dict(ctx["finance_response_quality_slice"].get("summary")).get("source_open_blocked_count")),
                "repair_proposal_count": int_value(as_dict(ctx["finance_response_quality_repair_loop"].get("summary")).get("proposal_count")),
            },
        })
    else:
        item.update({
            "action_state": "finance_response_quality_followup_open",
            "closure_reason": "Finance response-quality proof is not clean enough to close this follow-up row; missing, stale, future, malformed, unvalidated, or failed evidence fails closed.",
            "recommended_next_action": "Keep open until WF74 runner health, finance response-quality slice, and repair loop are all clean, fully validated, and freshly generated.",
            "proof_artifacts": proof_artifacts,
        })
    return item


def strict_nonbool_int(value: Any) -> tuple[bool, int]:
    """Strict non-bool int read: missing/bool/non-int never coerces to clean zero."""
    if isinstance(value, bool) or not isinstance(value, int):
        return (False, 0)
    return (True, value)


def implementation_token_bridge_usable(bridge: dict[str, Any]) -> tuple[bool, str]:
    """Fail-closed gate for the implementation-token-attribution bridge.

    Requires exact schema, fresh<=24h/nonfuture generation, status ok|warning,
    validation ok|warning with errors empty, strict non-bool zero for the three
    action-required counters, and terminal-only resolution status.
    """
    if not isinstance(bridge, dict) or not bridge:
        return (False, "bridge_missing_or_malformed")
    if bridge.get("schema") != IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE_SCHEMA:
        return (False, "bridge_schema_mismatch")
    if bridge.get("status") not in IMPLEMENTATION_TOKEN_BRIDGE_OK_STATUSES:
        return (False, "bridge_status_not_ok")
    validation = bridge.get("validation")
    if not isinstance(validation, dict):
        return (False, "bridge_validation_missing")
    if validation.get("status") not in IMPLEMENTATION_TOKEN_BRIDGE_OK_VALIDATIONS:
        return (False, "bridge_validation_not_ok")
    errors = validation.get("errors")
    if not isinstance(errors, list) or len(errors) != 0:
        return (False, "bridge_validation_errors_not_empty")
    generated_at = parse_evidence_generated_at(bridge.get("generated_at_utc"))
    if generated_at is None:
        return (False, "bridge_generated_at_malformed")
    now = datetime.now(timezone.utc)
    if generated_at > now:
        return (False, "bridge_generated_at_future")
    if (now - generated_at).total_seconds() > IMPLEMENTATION_TOKEN_BRIDGE_MAX_AGE_SECONDS:
        return (False, "bridge_stale")
    summary = as_dict(bridge.get("summary"))
    for key in (
        "action_required_supported_runtime_gap_count",
        "post_cutoff_supported_unresolved_gap_count",
        "unknown_completion_supported_unresolved_gap_count",
    ):
        present, number = strict_nonbool_int(summary.get(key))
        if not present or number != 0:
            return (False, f"bridge_unresolved_or_missing:{key}")
    if summary.get("gap_resolution_status") not in IMPLEMENTATION_TOKEN_BRIDGE_TERMINAL_RESOLUTIONS:
        return (False, "bridge_resolution_not_terminal_only")
    return (True, "bridge_terminal_unavailable_only")


def is_usage_source_reverification_row(row: dict[str, Any]) -> bool:
    return (
        str(row.get("source_key") or "") == "usage_source_reverification_required"
        or str(row.get("title") or "") == "usage_source_reverification_required"
    )


def classify_usage_source_reverification(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    bridge = ctx.get("implementation_token_bridge", {})
    usable, detail = implementation_token_bridge_usable(bridge)
    proof_artifacts = [rel(IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE)]
    summary = as_dict(bridge.get("summary")) if isinstance(bridge, dict) else {}
    context = {
        "bridge_status": bridge.get("status") if isinstance(bridge, dict) else None,
        "bridge_validation_status": as_dict(bridge.get("validation")).get("status") if isinstance(bridge, dict) else None,
        "bridge_generated_at_utc": bridge.get("generated_at_utc") if isinstance(bridge, dict) else None,
        "action_required_supported_runtime_gap_count": summary.get("action_required_supported_runtime_gap_count"),
        "post_cutoff_supported_unresolved_gap_count": summary.get("post_cutoff_supported_unresolved_gap_count"),
        "unknown_completion_supported_unresolved_gap_count": summary.get("unknown_completion_supported_unresolved_gap_count"),
        "gap_resolution_status": summary.get("gap_resolution_status"),
        "bridge_gate": detail,
    }
    if usable:
        item.update({
            "closure_allowed": True,
            "closure_status": "historical_terminal_unavailable_claim_limit",
            "action_state": "monitor_only",
            "successor_id": None,
            "successor_artifact": rel(IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE),
            "successor_artifact_kind": "implementation_token_attribution_bridge",
            "closure_reason": (
                "Fresh bridge proof shows zero action-required supported-runtime gaps with terminal-only "
                "resolution; this closes the reverification follow-up as a historical claim limit, explicitly "
                "NOT a verified success or performance claim."
            ),
            "recommended_next_action": (
                "Monitor only; keep historical economics and model-performance limits visible and do not use "
                "these lanes for performance, cost, latency, reliability, or savings comparisons."
            ),
            "proof_artifacts": proof_artifacts,
            "context": context,
        })
    else:
        item.update({
            "action_state": "usage_source_reverification_open",
            "closure_reason": (
                f"Bridge proof is not terminal-clean ({detail}); missing, malformed, stale, future, unvalidated, "
                "or currently-unresolved evidence fails closed and keeps reverification open."
            ),
            "recommended_next_action": (
                "Keep open until a fresh schema-exact bridge with zero action-required supported-runtime gaps "
                "and terminal-only resolution is available; do not claim model economics or performance."
            ),
            "proof_artifacts": proof_artifacts,
            "context": context,
        })
    return item


def classify_item(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    category = str(row.get("category") or "")
    title = str(row.get("title") or "")
    key = source_key(row)
    if category == "cron_migration":
        return classify_cron(row, ctx)
    if category == "collector_config":
        return classify_collector(row, ctx)
    if category == "outcome_measurement" or title.startswith("Track WF87 shadow outcomes"):
        return classify_outcome(row, ctx)
    if category == "planning_quality":
        return classify_planning(row, ctx)
    if category == "code_mutation" or key == "validator_latency_optimization" or title == "validator_latency_optimization":
        return classify_validator(row, ctx)
    if key == "wf74_queue_followup" or title == "wf74_queue_followup":
        return classify_wf74_queue(row, ctx)
    if is_finance_response_quality_row(row):
        return classify_finance_response_quality(row, ctx)
    if is_usage_source_reverification_row(row):
        return classify_usage_source_reverification(row, ctx)
    item = base_item(row)
    item.update({
        "action_state": "manual_review_required",
        "closure_reason": "No deterministic triage rule matched this follow-up row.",
        "recommended_next_action": "Keep open until a durable proof artifact or owner packet is identified.",
        "proof_artifacts": [rel(IMPROVEMENT_LEDGER)],
    })
    return item


def duplicate_subject_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Group recurring follow-up rows that represent the same unresolved subject."""
    return (
        str(item.get("source_type") or ""),
        norm_text(item.get("category")),
        norm_text(item.get("title")),
        str(item.get("action_state") or ""),
        norm_text(item.get("recommended_next_action")),
    )


def opened_sort_value(item: dict[str, Any]) -> str:
    return str(item.get("opened_at_utc") or "9999-12-31T23:59:59Z")


def collapse_duplicate_active_followups(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Close duplicate source-key rows while preserving one visible active row.

    The append-only ledger may contain old follow-up-required rows for the same
    title/category after a recurring producer changes priority or signal. This
    classifies the extra source keys as superseded instead of leaving each one
    to surface as separate unfinished work forever.
    """
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for item in items:
        if item.get("closure_allowed"):
            continue
        key = duplicate_subject_key(item)
        if not all(key[:4]):
            continue
        groups.setdefault(key, []).append(item)

    duplicate_keys = {
        key for key, group in groups.items()
        if len({source_key(row) for row in group}) > 1
    }
    if not duplicate_keys:
        return items, []

    superseded: list[dict[str, Any]] = []
    keepers: set[str] = set()
    duplicate_source_keys: set[str] = set()
    for key in duplicate_keys:
        group = sorted(
            groups[key],
            key=lambda row: (-int_value(row.get("priority")), opened_sort_value(row), source_key(row)),
        )
        keeper = group[0]
        keeper_key = source_key(keeper)
        keepers.add(keeper_key)
        for duplicate in group[1:]:
            duplicate_key = source_key(duplicate)
            duplicate_source_keys.add(duplicate_key)
            proof_artifacts = sorted({
                *[str(item) for item in as_list(duplicate.get("proof_artifacts"))],
                rel(IMPROVEMENT_LEDGER),
            })
            closed = dict(duplicate)
            closed.update({
                "closure_allowed": True,
                "closure_status": "superseded_by_open_improvement",
                "action_state": "close_duplicate_followup_source",
                "closure_reason": (
                    f"Duplicate follow-up source row is represented by open source_key {keeper_key}; "
                    "keep one canonical row visible and close this stale duplicate source key."
                ),
                "recommended_next_action": (
                    f"Close duplicate source_key {duplicate_key}; continue monitoring canonical source_key {keeper_key}."
                ),
                "successor_source_key": keeper_key,
                "successor_id": keeper_key,
                "successor_artifact": rel(IMPROVEMENT_LEDGER),
                "successor_artifact_kind": "canonical_open_improvement_row",
                "successor_title": keeper.get("title"),
                "duplicate_of_source_key": keeper_key,
                "proof_artifacts": proof_artifacts,
            })
            superseded.append(closed)

    collapsed = [
        item for item in items
        if source_key(item) not in duplicate_source_keys or source_key(item) in keepers
    ]
    return collapsed, superseded


def prior_triage_closures(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(ledger.get("latest_closed_improvements")):
        closed = as_dict(row)
        if closed.get("resolution_reason") != "wf88_followup_debt_triage":
            continue
        follow_up = as_dict(closed.get("follow_up"))
        rows.append({
            "source_type": closed.get("source_type"),
            "source_key": closed.get("source_key"),
            "title": closed.get("title"),
            "category": closed.get("category"),
            "priority": closed.get("priority"),
            "closure_status": follow_up.get("status"),
            "closure_reason": follow_up.get("detail"),
            "proof_artifacts": closed.get("proof_artifacts") or follow_up.get("proof"),
            "successor_id": closed.get("successor_id") or follow_up.get("successor_id"),
            "successor_artifact": closed.get("successor_artifact") or follow_up.get("successor_artifact"),
            "successor_artifact_kind": closed.get("successor_artifact_kind") or follow_up.get("successor_artifact_kind"),
            "closed_at_utc": closed.get("recorded_at_utc"),
            "triage_action_state": closed.get("triage_action_state"),
        })
    return rows


def build_packet() -> dict[str, Any]:
    ctx = {
        "improvement_ledger": load(IMPROVEMENT_LEDGER),
        "wf74_router": load(WF74_ROUTER),
        "wf74_docket": load(WF74_DOCKET),
        "cron_control": load(CRON_CONTROL),
        "otel_ops": load(OTEL_OPS),
        "wf74_runner": load(WF74_RUNNER),
        "finance_response_quality_slice": load(FINANCE_RESPONSE_QUALITY_SLICE),
        "finance_response_quality_repair_loop": load(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP),
        "workflow_followups": load(WORKFLOW_FOLLOWUPS),
        "wf87_rollup": load(WF87_ROLLUP),
        "autonomy_spine": load(AUTONOMY_SPINE),
        "validator_timing": load(VALIDATOR_TIMING),
        "wf88_os2_control": load(WF88_OS2_CONTROL),
        "implementation_token_bridge": load(IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE),
    }
    followups = [as_dict(row) for row in as_list(ctx["improvement_ledger"].get("followup_required_improvements"))]
    classified_items = [classify_item(row, ctx) for row in followups]
    items, duplicate_closures = collapse_duplicate_active_followups(classified_items)
    items.extend(duplicate_closures)
    closure_history = prior_triage_closures(ctx["improvement_ledger"])
    closure_allowed = [item for item in items if item.get("closure_allowed")]
    kept_open = [item for item in items if not item.get("closure_allowed")]
    closure_counts = Counter(str(item.get("closure_status") or "kept_open") for item in items)
    action_counts = Counter(str(item.get("action_state") or "unknown") for item in items)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "triage_ready",
        "purpose": "Classify open follow-up-required improvement rows into durable closure or active follow-up states.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_status": {
            "improvement_ledger": source_record(IMPROVEMENT_LEDGER),
            "wf74_router": source_record(WF74_ROUTER),
            "wf74_docket": source_record(WF74_DOCKET),
            "cron_control": source_record(CRON_CONTROL),
            "otel_ops": source_record(OTEL_OPS),
            "wf74_runner": source_record(WF74_RUNNER),
            "finance_response_quality_slice": source_record(FINANCE_RESPONSE_QUALITY_SLICE),
            "finance_response_quality_repair_loop": source_record(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP),
            "workflow_followups": source_record(WORKFLOW_FOLLOWUPS),
            "wf87_rollup": source_record(WF87_ROLLUP),
            "autonomy_spine": source_record(AUTONOMY_SPINE),
            "validator_timing": source_record(VALIDATOR_TIMING),
            "wf88_os2_control": source_record(WF88_OS2_CONTROL),
            "implementation_token_bridge": source_record(IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE),
        },
        "summary": {
            "followup_input_count": len(followups),
            "closure_allowed_count": len(closure_allowed),
            "kept_open_count": len(kept_open),
            "duplicate_followup_closed_count": len(duplicate_closures),
            "prior_triage_closure_count": len(closure_history),
            "by_closure_status": dict(sorted(closure_counts.items())),
            "by_action_state": dict(sorted(action_counts.items())),
            "cron_rows_kept_open_count": sum(1 for item in kept_open if item.get("category") == "cron_migration"),
            "collector_rows_kept_open_count": sum(1 for item in kept_open if item.get("category") == "collector_config"),
            "next_safe_action": "Run improvement_ledger.py so closure-allowed rows append durable closure events; keep active follow-up rows open.",
        },
        "triage_items": items,
        "closure_items": closure_allowed,
        "triage_closure_history": closure_history,
        "active_followup_items": kept_open,
        "ledger_contract": {
            "consumer": "scripts/improvement_ledger.py",
            "allowed_closure_statuses": sorted(ALLOWED_CLOSURE_STATUSES),
            "closure_event_resolution_reason": "wf88_followup_debt_triage",
            "closure_requires": [
                "closure_allowed true",
                "closure_status in allowed_closure_statuses",
                "non-empty proof_artifacts",
                "non-empty successor_artifact pointing to WF88 control packet or canonical successor row",
                "source_type and source_key match an open follow-up-required ledger row",
            ],
        },
        "blocked_actions": [
            "no auto-apply",
            "no cron schedule/config/runtime mutation",
            "no collector/runtime config mutation",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no paper/live/brokerage/account action",
            "no owner approval inference",
        ],
    }
    packet["validation"] = validate(packet)
    if packet["validation"]["status"] != "ok":
        packet["status"] = "triage_warning"
    return packet


def validate(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    for name, source in as_dict(packet.get("source_status")).items():
        record = as_dict(source)
        if not record.get("present"):
            # WF87 and the autonomy spine were retired by the 2026-08-29 alerts-OS pivot;
            # their rollups are no longer produced, so absence is expected, not an error.
            if name in {"wf87_rollup", "autonomy_spine"}:
                warnings.append(f"retired_source_absent:{name}")
                continue
            errors.append(f"missing_source:{name}:{record.get('path')}")
    items = [as_dict(row) for row in as_list(packet.get("triage_items"))]
    if not items:
        warnings.append("no_followup_required_rows_to_triage")
    for item in items:
        if item.get("closure_allowed"):
            status = str(item.get("closure_status") or "")
            if status not in ALLOWED_CLOSURE_STATUSES:
                errors.append(f"invalid_closure_status:{item.get('source_key')}:{status}")
            if not as_list(item.get("proof_artifacts")):
                errors.append(f"closure_without_proof:{item.get('source_key')}")
            if not item.get("successor_artifact"):
                errors.append(f"closure_without_successor_artifact:{item.get('source_key')}")
        if (
            item.get("category") in {"cron_migration", "collector_config"}
            and item.get("closure_allowed")
            and item.get("closure_status") != "superseded_by_open_improvement"
        ):
            errors.append(f"unsafe_live_operational_closure:{item.get('source_key')}")
    summary = as_dict(packet.get("summary"))
    if int_value(summary.get("kept_open_count")) > 0:
        warnings.append(f"active_followup_rows_kept_open:{summary.get('kept_open_count')}")
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF88 Follow-Up Debt Triage Packet",
        "",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Status: `{packet.get('status')}` / validation `{as_dict(packet.get('validation')).get('status')}`",
        f"- Follow-up rows triaged: `{summary.get('followup_input_count')}`",
        f"- Closure allowed: `{summary.get('closure_allowed_count')}`",
        f"- Kept open: `{summary.get('kept_open_count')}`",
        f"- Prior triage closures still proved here: `{summary.get('prior_triage_closure_count')}`",
        f"- Next safe action: {summary.get('next_safe_action')}",
        "",
        "## Closure Items",
        "",
    ]
    for item in as_list(packet.get("closure_items")):
        row = as_dict(item)
        lines.append(f"- `{row.get('source_key')}`: `{row.get('closure_status')}` - {row.get('closure_reason')}")
    lines.extend(["", "## Prior Triage Closures", ""])
    for item in as_list(packet.get("triage_closure_history")):
        row = as_dict(item)
        lines.append(f"- `{row.get('source_key')}`: `{row.get('closure_status')}` - {row.get('closure_reason')}")
    lines.extend(["", "## Kept Open", ""])
    for item in as_list(packet.get("active_followup_items")):
        row = as_dict(item)
        lines.append(f"- `{row.get('source_key')}`: `{row.get('action_state')}` - {row.get('closure_reason')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Review-only classification and ledger proof.",
        "- No cron/config/runtime/finance/execution mutation and no owner approval inference.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    if args.pretty:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_markdown(packet))
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
