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
WF85_SOURCE_OPEN_RECONCILIATION = TMP / "wf85-source-open-reconciliation-contract.json"
WORKFLOW_FOLLOWUPS = TMP / "workflow-blocker-followups.json"
WF87_ROLLUP = TMP / "wf87-v2-readiness-rollup.json"
AUTONOMY_SPINE = TMP / "autonomy-spine-readiness-rollup.json"
VALIDATOR_TIMING = TMP / "validator-timing-ledger.json"
WF88_OS2_CONTROL = TMP / "wf88-os2-control-packet.json"

ALLOWED_CLOSURE_STATUSES = {
    "verified_fix",
    "pending_skill_proposal",
    "applied_skill_proposal",
    "superseded_by_open_improvement",
    "owner_packet_ready_not_applied",
    "monitor_only_drift_currently_absent",
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
    if gap_count == 0 and clean_rate >= 1.0:
        item.update({
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "action_state": "close_with_clean_followthrough_proof",
            **wf88_successor("improvement-ledger-open-followups"),
            "closure_reason": "Planning follow-through proof is clean: gap count is zero and clean rate is 1.0.",
            "recommended_next_action": "Close the stale planning follow-through rows and continue normal WF74/PM monitoring.",
            "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_RUNNER)],
            "context": {
                "planning_followthrough_gap_count": gap_count,
                "planning_followthrough_clean_rate": clean_rate,
                "runner_planning_followthrough_gap_count": runner_summary.get("planning_quality_followthrough_gap_count"),
            },
        })
    else:
        item.update({
            "action_state": "planning_followthrough_gap_open",
            "closure_reason": "Planning follow-through proof is not clean.",
            "proof_artifacts": [rel(WF74_ROUTER), rel(WF74_RUNNER)],
            "context": {
                "planning_followthrough_gap_count": gap_count,
                "planning_followthrough_clean_rate": clean_rate,
            },
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


def finance_response_quality_proof_clean(ctx: dict[str, dict[str, Any]]) -> bool:
    runner_summary = as_dict(ctx["wf74_runner"].get("summary"))
    slice_summary = as_dict(ctx["finance_response_quality_slice"].get("summary"))
    repair_summary = as_dict(ctx["finance_response_quality_repair_loop"].get("summary"))
    wf85_summary = as_dict(ctx["wf85_source_open_reconciliation"].get("summary"))
    return all((
        ctx["wf74_runner"].get("status") == "ok",
        int_value(runner_summary.get("steps_blocked")) == 0,
        runner_summary.get("finance_response_quality_status") == "ok",
        int_value(runner_summary.get("finance_response_quality_source_open_blocked_count")) == 0,
        int_value(runner_summary.get("finance_response_quality_source_freshness_blocked_count")) == 0,
        int_value(runner_summary.get("finance_response_quality_remediation_tracks_needing_repair")) == 0,
        ctx["finance_response_quality_slice"].get("status") == "ok",
        int_value(slice_summary.get("blocked_archetype_count")) == 0,
        int_value(slice_summary.get("source_open_blocked_count")) == 0,
        int_value(slice_summary.get("source_freshness_blocked_count")) == 0,
        int_value(slice_summary.get("remediation_tracks_needing_repair")) == 0,
        ctx["finance_response_quality_repair_loop"].get("status") in {"ok", "noop_ok"},
        int_value(repair_summary.get("proposal_count")) == 0,
        int_value(repair_summary.get("high_priority_count")) == 0,
        int_value(repair_summary.get("source_open_blocked_count")) == 0,
        int_value(repair_summary.get("source_freshness_blocked_count")) == 0,
        int_value(repair_summary.get("remediation_tracks_needing_repair")) == 0,
        ctx["wf85_source_open_reconciliation"].get("status") == "ok",
        int_value(wf85_summary.get("fresh_verified_source_count")) > 0,
        int_value(wf85_summary.get("unnecessary_source_open_blocker_count")) == 0,
        int_value(wf85_summary.get("wrong_source_open_blocker_reason_count")) == 0,
        int_value(wf85_summary.get("mismatch_error_count")) == 0,
        int_value(wf85_summary.get("producer_order_error_count")) == 0,
    ))


def classify_finance_response_quality(row: dict[str, Any], ctx: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = base_item(row)
    proof_artifacts = [
        rel(WF74_RUNNER),
        rel(FINANCE_RESPONSE_QUALITY_SLICE),
        rel(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP),
        rel(WF85_SOURCE_OPEN_RECONCILIATION),
    ]
    if finance_response_quality_proof_clean(ctx):
        item.update({
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "action_state": "close_with_finance_response_quality_clean_proof",
            **wf88_successor("wf85-source-open-repair-queue"),
            "closure_reason": "Current WF74/WF85 proof shows zero finance response-quality source-open blockers, zero repair proposals, and zero WF85 source-open reconciliation mismatches.",
            "recommended_next_action": "Close the stale finance response-quality follow-up row; reopen only if source-open blockers, repair proposals, or WF85 reconciliation mismatches reappear.",
            "proof_artifacts": proof_artifacts,
            "context": {
                "wf74_steps_blocked": int_value(as_dict(ctx["wf74_runner"].get("summary")).get("steps_blocked")),
                "source_open_blocked_count": int_value(as_dict(ctx["finance_response_quality_slice"].get("summary")).get("source_open_blocked_count")),
                "repair_proposal_count": int_value(as_dict(ctx["finance_response_quality_repair_loop"].get("summary")).get("proposal_count")),
                "wf85_unnecessary_source_open_blocker_count": int_value(as_dict(ctx["wf85_source_open_reconciliation"].get("summary")).get("unnecessary_source_open_blocker_count")),
                "wf85_mismatch_error_count": int_value(as_dict(ctx["wf85_source_open_reconciliation"].get("summary")).get("mismatch_error_count")),
            },
        })
    else:
        item.update({
            "action_state": "finance_response_quality_followup_open",
            "closure_reason": "Finance response-quality proof is not clean enough to close this follow-up row.",
            "recommended_next_action": "Keep open until WF74 runner, finance response-quality slice, repair loop, and WF85 source-open reconciliation are all clean.",
            "proof_artifacts": proof_artifacts,
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
        "wf85_source_open_reconciliation": load(WF85_SOURCE_OPEN_RECONCILIATION),
        "workflow_followups": load(WORKFLOW_FOLLOWUPS),
        "wf87_rollup": load(WF87_ROLLUP),
        "autonomy_spine": load(AUTONOMY_SPINE),
        "validator_timing": load(VALIDATOR_TIMING),
        "wf88_os2_control": load(WF88_OS2_CONTROL),
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
            "wf85_source_open_reconciliation": source_record(WF85_SOURCE_OPEN_RECONCILIATION),
            "workflow_followups": source_record(WORKFLOW_FOLLOWUPS),
            "wf87_rollup": source_record(WF87_ROLLUP),
            "autonomy_spine": source_record(AUTONOMY_SPINE),
            "validator_timing": source_record(VALIDATOR_TIMING),
            "wf88_os2_control": source_record(WF88_OS2_CONTROL),
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
