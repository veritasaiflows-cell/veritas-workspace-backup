#!/usr/bin/env python3
"""Build the WF88 OS 2.0 control packet.

WF88 is the measured learning, cleanup, and route-contraction layer. This
packet consumes WF87's narrow runtime-governor output instead of duplicating
paper-autonomy authority. It is a thin control surface, not a new canonical
owner or cleanup apply tool.
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

WF87_GOVERNOR = TMP / "wf87-paper-autonomy-runtime-governor.json"
WF67_MANAGER = TMP / "alpaca-paper-readiness" / "wf67-autonomous-paper-manager-current.json"
WF88_CLEANUP_PLAN = TMP / "wf88-retired-surface-cleanup-plan.json"
WF88_ROUTE_CONTRACTION = TMP / "wf88-route-contraction-packet.json"
WF88_SOURCE_OPEN_CLASSIFIER = TMP / "wf88-source-open-residue-classifier.json"
WF88_DELETE_READINESS = TMP / "wf88-delete-readiness-packet.json"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
WF55_LEDGER = TMP / "wf55-autonomy-outcome-ledger.json"
FINANCE_DIGEST = TMP / "finance-decision-performance-digest.json"
WF85_PACKET = TMP / "wf85-decision-os-review-packet.json"
WF74_DOCKET = TMP / "wf74-decision-docket.json"
WF74_WF88_LOOP_TRACE = TMP / "wf74-wf88-loop-trace.json"
LONG_WORK_JOB_STATUS = TMP / "long-work-job-status-packet.json"
IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
PM_CONTROL = TMP / "pm-control-packet.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
OTEL_CONTROL = TMP / "otel-ops-control.json"
WF88_WIKI_SYNTHESIS = TMP / "wf88-wiki-synthesis-packet.json"
SKILL_WORKSHOP_BODY_GUARD = TMP / "skill-workshop-body-guard.json"
WF88_FINANCE_QUERY_FRICTION_GUARD = TMP / "wf88-finance-query-friction-guard.json"
FINANCE_CACHE_FRONTDOOR = TMP / "finance-cache-frontdoor.json"
WF78_ROUTE_READINESS_P3 = TMP / "wf78-route-readiness-p3-market-ranking.json"
OUT = TMP / "wf88-os2-control-packet.json"
MD_OUT = TMP / "wf88-os2-control-packet.md"

SCHEMA = "veritas.wf88_os2_control_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "control_packet_only": True,
    "learning_signal_only": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_output_allowed": False,
    "model_training_claim_allowed": False,
    "raw_prompt_or_tool_capture_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def source_descriptor(path: Path, required: bool = True, max_age_hours: float | None = None) -> dict[str, Any]:
    payload = load_optional_json(path)
    generated_at = payload.get("generated_at_utc")
    generated_dt = parse_utc(generated_at)
    age_hours = None
    freshness_status = "missing" if not path.exists() else "unknown_generated_at"
    warning = path.exists() is not True and required
    blocking = path.exists() is not True and required
    if generated_dt is not None:
        age_hours = round((datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600.0, 2)
        if max_age_hours is None:
            freshness_status = "present_unbounded"
        else:
            freshness_status = "fresh" if age_hours <= max_age_hours else "stale"
            warning = age_hours > max_age_hours
    elif path.exists():
        warning = required
    return {
        "path": rel(path),
        "present": path.exists(),
        "required": required,
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "freshness_status": freshness_status,
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "warning": warning,
        "blocking": blocking,
    }


def summarize_wf87(governor: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(governor.get("summary"))
    return {
        "source_status": governor.get("status"),
        "runtime_status": summary.get("runtime_status"),
        "shadow_threshold_met": summary.get("shadow_threshold_met"),
        "reconciliation_maturity_met": summary.get("reconciliation_maturity_met"),
        "shadow_scoreable_decision_count": summary.get("shadow_scoreable_decision_count"),
        "assisted_filled_round_trips_all_time": summary.get("assisted_filled_round_trips_all_time"),
        "required_assisted_filled_round_trips_for_phase_c_proposal": summary.get("required_assisted_filled_round_trips_for_phase_c_proposal"),
        "phase_c_owner_review_eligible_now": summary.get("phase_c_owner_review_eligible_now"),
        "phase_c_autonomous_paper_buy_ready": summary.get("phase_c_autonomous_paper_buy_ready"),
        "execution_allowed": summary.get("execution_allowed"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_wf67(manager: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(manager.get("summary"))
    validation = as_dict(manager.get("validation"))
    authority = as_dict(manager.get("authority"))
    return {
        "source_status": manager.get("status"),
        "validation_status": validation.get("status"),
        "candidate_card_count": summary.get("candidate_card_count"),
        "blocked_candidate_count": summary.get("blocked_candidate_count"),
        "conditional_ready_after_fresh_monday_quote_count": summary.get("conditional_ready_after_fresh_monday_quote_count"),
        "ready_tickers": summary.get("ready_tickers"),
        "blocked_tickers": summary.get("blocked_tickers"),
        "repair_review_tickers": summary.get("repair_review_tickers"),
        "paper_order_execution_allowed": authority.get("paper_order_execution_allowed"),
        "live_trade_or_account_action_allowed": authority.get("live_trade_or_account_action_allowed"),
        "owner_approval_inferred": authority.get("owner_approval_inferred"),
        "operator_next_action": manager.get("operator_next_action"),
    }


def summarize_cleanup(cleanup: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(cleanup.get("summary"))
    return {
        "source_status": cleanup.get("status"),
        "delete_allowed_now_count": summary.get("delete_allowed_now_count"),
        "archive_allowed_now_count": summary.get("archive_allowed_now_count"),
        "tmp_cleanup_preview_eligible_count": summary.get("tmp_cleanup_preview_eligible_count"),
        "first_tmp_microbatch_candidate_count": summary.get("first_tmp_microbatch_candidate_count"),
        "script_route_contraction_candidate_count": summary.get("script_route_contraction_candidate_count"),
        "script_route_contraction_exact_file_count": summary.get("script_route_contraction_exact_file_count"),
        "db_archive_candidate_count": summary.get("db_archive_candidate_count"),
        "cron_packet_status": summary.get("cron_packet_status"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_route_contraction(route_packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(route_packet.get("summary"))
    return {
        "source_status": route_packet.get("status"),
        "validation_status": as_dict(route_packet.get("validation")).get("status"),
        "exact_route_contraction_file_count": summary.get("exact_route_contraction_file_count"),
        "contracted_or_already_narrowed_count": summary.get("contracted_or_already_narrowed_count"),
        "needs_route_contraction_count": summary.get("needs_route_contraction_count"),
        "script_deletion_ready_now_count": summary.get("script_deletion_ready_now_count"),
        "delete_allowed_now_count": summary.get("delete_allowed_now_count"),
        "archive_allowed_now_count": summary.get("archive_allowed_now_count"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_source_open_classifier(classifier: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(classifier.get("summary"))
    return {
        "source_status": classifier.get("status"),
        "validation_status": as_dict(classifier.get("validation")).get("status"),
        "source_open_blocked_count": summary.get("source_open_blocked_count"),
        "default_runtime_blocker_count": summary.get("default_runtime_blocker_count"),
        "implementation_blocker_count": summary.get("implementation_blocker_count"),
        "active_sql_json_tier_repair_count": summary.get("active_sql_json_tier_repair_count"),
        "below_stop_or_invalidation_review_only_count": summary.get("below_stop_or_invalidation_review_only_count"),
        "monitor_only_context_count": summary.get("monitor_only_context_count"),
        "legacy_42_deprecated_residue_count": summary.get("legacy_42_deprecated_residue_count"),
        "unknown_needs_source_open_count": summary.get("unknown_needs_source_open_count"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_delete_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(readiness.get("summary"))
    return {
        "source_status": readiness.get("status"),
        "validation_status": as_dict(readiness.get("validation")).get("status"),
        "tmp_delete_candidate_count": summary.get("tmp_delete_candidate_count"),
        "tmp_delete_ready_after_owner_approval_count": summary.get("tmp_delete_ready_after_owner_approval_count"),
        "tmp_delete_already_applied_count": summary.get("tmp_delete_already_applied_count"),
        "tmp_delete_missing_unapplied_count": summary.get("tmp_delete_missing_unapplied_count"),
        "tmp_delete_bytes": summary.get("tmp_delete_bytes"),
        "db_archive_candidate_count": summary.get("db_archive_candidate_count"),
        "db_archive_ready_after_owner_approval_count": summary.get("db_archive_ready_after_owner_approval_count"),
        "script_deletion_ready_now_count": summary.get("script_deletion_ready_now_count"),
        "cron_mutation_ready_now_count": summary.get("cron_mutation_ready_now_count"),
        "delete_or_archive_performed": summary.get("delete_or_archive_performed"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_recommendation_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(ledger.get("recommendation_tracking_summary"))
    durable = as_dict(ledger.get("durable_v2_ledger"))
    grade_history = as_dict(durable.get("grade_history") or ledger.get("grade_history"))
    rows = as_list(ledger.get("tracked_rows"))
    subtype_counts: dict[str, int] = {}
    current_preview_later_outcome_graded = 0
    for row in rows:
        row_dict = as_dict(row)
        subtype = str(row_dict.get("event_subtype") or "unknown")
        subtype_counts[subtype] = subtype_counts.get(subtype, 0) + 1
        payload = as_dict(row_dict.get("payload"))
        marker = " ".join([
            subtype,
            str(payload.get("outcome_grade") or ""),
            str(payload.get("forward_scorecard_status") or ""),
            str(payload.get("later_outcome_status") or ""),
        ]).lower()
        if "graded" in marker or "later_outcome" in marker and "pending" not in marker:
            current_preview_later_outcome_graded += 1
    durable_later_outcome_graded = durable.get("later_outcome_graded_rows")
    history_later_outcome_graded = grade_history.get("graded_ledger_event_count")
    later_outcome_graded = current_preview_later_outcome_graded
    if isinstance(durable_later_outcome_graded, int):
        later_outcome_graded = max(later_outcome_graded, durable_later_outcome_graded)
    if isinstance(history_later_outcome_graded, int):
        later_outcome_graded = max(later_outcome_graded, history_later_outcome_graded)
    return {
        "source_status": ledger.get("status"),
        "validation_status": as_dict(ledger.get("validation")).get("status"),
        "tracked_row_count": summary.get("tracking_row_count", len(rows)),
        "pending_owner_decision_rows": summary.get("pending_owner_decision_rows"),
        "pending_paper_card_rows": summary.get("pending_paper_card_rows"),
        "later_outcome_graded_rows": later_outcome_graded,
        "later_outcome_metric_scope": "durable_recommendation_outcome_ledger_max_of_preview_durable_and_grade_history",
        "current_preview_later_outcome_graded_rows": current_preview_later_outcome_graded,
        "durable_later_outcome_graded_rows": durable_later_outcome_graded,
        "grade_history_graded_ledger_event_count": history_later_outcome_graded,
        "grade_history_event_count": grade_history.get("assigned_grade_event_count"),
        "grade_history_path": grade_history.get("path"),
        "tracked_tickers": summary.get("tracked_tickers"),
        "event_subtype_counts": subtype_counts,
        "predictive_or_model_claims_allowed": summary.get("predictive_or_model_claims_allowed") is True,
        "paper_or_live_execution_allowed": summary.get("paper_or_live_execution_allowed") is True,
    }


def summarize_learning(wf55: dict[str, Any], finance_digest: dict[str, Any]) -> dict[str, Any]:
    wf55_summary = as_dict(wf55.get("summary"))
    performance_claim = as_dict(finance_digest.get("performance_claim_status"))
    decision_quality_claim = (
        performance_claim.get("decision_quality_claim_allowed_now")
        if "decision_quality_claim_allowed_now" in performance_claim
        else wf55_summary.get("decision_quality_claim_allowed_now")
    )
    model_performance_claim = (
        performance_claim.get("model_performance_claim_allowed_now")
        if "model_performance_claim_allowed_now" in performance_claim
        else performance_claim.get("predictive_skill_claim_allowed_now")
    )
    return {
        "wf55_status": wf55.get("status"),
        "finance_digest_status": finance_digest.get("status"),
        "decision_event_count": wf55_summary.get("decision_event_count"),
        "measurement_grade_count": wf55_summary.get("measurement_grade_count"),
        "clean_shadow_decision_count": wf55_summary.get("clean_shadow_decision_count"),
        "shadow_threshold_met": wf55_summary.get("shadow_threshold_met"),
        "scoreable_decision_count": wf55_summary.get("scoreable_decision_count"),
        "pending_regular_session_followup_count": wf55_summary.get("pending_regular_session_followup_count"),
        "decision_quality_claim_allowed_now": decision_quality_claim is True,
        "model_performance_claim_allowed_now": model_performance_claim is True,
        "claim_state": wf55_summary.get("claim_state"),
    }


def summarize_decision_os(wf85: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(wf85.get("summary"))
    return {
        "source_status": wf85.get("status"),
        "card_count": summary.get("card_count"),
        "approval_card_draft_count": summary.get("approval_card_draft_count"),
        "approval_gate_review_ready_count": summary.get("approval_gate_review_ready_count"),
        "capital_review_ready_count": summary.get("capital_review_ready_count"),
        "implementation_blocker_count": summary.get("implementation_blocker_count"),
        "source_open_status_counts": summary.get("source_open_status_counts"),
        "trade_grade_data_readiness_status": summary.get("trade_grade_data_readiness_status"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_ops(pm: dict[str, Any], cron: dict[str, Any], otel: dict[str, Any], improvement: dict[str, Any], wf74: dict[str, Any]) -> dict[str, Any]:
    pm_summary = as_dict(pm.get("summary"))
    cron_summary = as_dict(cron.get("summary"))
    otel_summary = as_dict(otel.get("summary"))
    improvement_summary = as_dict(improvement.get("summary"))
    wf74_summary = as_dict(wf74.get("summary"))
    pm_readiness = as_dict(pm_summary.get("pm_readiness"))
    return {
        "pm_status": pm.get("status"),
        "pm_readiness_band": pm_readiness.get("readiness_band"),
        "pm_blocked_lanes": pm_readiness.get("blocked_lanes"),
        "cron_status": cron.get("status"),
        "cron_escalation_signal_count": cron_summary.get("escalation_signal_count"),
        "cron_blocked_count": cron_summary.get("blocked_count"),
        "otel_status": otel.get("status"),
        "otel_event_count_24h": otel_summary.get("event_count"),
        "improvement_status": improvement.get("status"),
        "improvement_open_count": improvement_summary.get("latest_open_count"),
        "improvement_high_priority_overdue_count": improvement_summary.get("high_priority_overdue_open_count"),
        "wf74_status": wf74.get("status"),
        "wf74_active_action_count": wf74_summary.get("active_action_count"),
        "wf74_fix_now_count": wf74_summary.get("fix_now_count"),
        "wf74_hard_stop_count": wf74_summary.get("hard_stop_count"),
    }


def summarize_wiki_synthesis(wiki: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(wiki.get("summary"))
    leak_guard = as_dict(wiki.get("recommendation_leak_guard"))
    validation = as_dict(wiki.get("validation"))
    return {
        "source_status": wiki.get("status"),
        "validation_status": validation.get("status"),
        "wiki_page_count": summary.get("wiki_page_count"),
        "self_prompt_count": summary.get("self_prompt_count"),
        "action_item_count": len(as_list(wiki.get("action_items"))),
        "recommendation_leak_guard_pass": leak_guard.get("pass"),
        "open_unrouted_recommendation_count": leak_guard.get("open_unrouted_recommendation_count"),
        "auto_apply_count": leak_guard.get("auto_apply_count"),
        "rsi_status": summary.get("rsi_status"),
        "followup_required_open_count": summary.get("followup_required_open_count"),
        "recommendation_later_outcome_graded_rows": summary.get("recommendation_later_outcome_graded_rows"),
        "retrieval_quality_status": summary.get("retrieval_quality_status"),
        "retrieval_quality_validation_status": summary.get("retrieval_quality_validation_status"),
        "retrieval_fixture_count": summary.get("retrieval_fixture_count"),
        "retrieval_passed_count": summary.get("retrieval_passed_count"),
        "retrieval_failed_count": summary.get("retrieval_failed_count"),
        "retrieval_class_count": summary.get("retrieval_class_count"),
        "retrieval_average_score": summary.get("retrieval_average_score"),
        "retrieval_live_source_timestamp_age_assessment_count": summary.get("retrieval_live_source_timestamp_age_assessment_count"),
        "retrieval_label_only_cases_are_live_source_proof": summary.get("retrieval_label_only_cases_are_live_source_proof"),
        "retrieval_declared_labels_are_authoritative": summary.get("retrieval_declared_labels_are_authoritative"),
        "retrieval_source_timestamp_age_is_live_source_proof": summary.get("retrieval_source_timestamp_age_is_live_source_proof"),
        "frontier_eval_status": summary.get("frontier_eval_status"),
        "frontier_eval_validation_status": summary.get("frontier_eval_validation_status"),
        "frontier_fixture_count": summary.get("frontier_fixture_count"),
        "frontier_result_row_count": summary.get("frontier_result_row_count"),
        "frontier_fully_verified_result_count": summary.get("frontier_fully_verified_result_count"),
        "frontier_model_execution_state": summary.get("frontier_model_execution_state"),
        "frontier_all_assignment_execution_proven": summary.get("frontier_all_assignment_execution_proven"),
        "frontier_proof_index_chain_verified": summary.get("frontier_proof_index_chain_verified"),
        "frontier_all_comparison_gates_passed": summary.get("frontier_all_comparison_gates_passed"),
        "frontier_trusted_execution_attestation_verified": summary.get("frontier_trusted_execution_attestation_verified"),
        "frontier_trusted_output_artifact_attestation_verified": summary.get("frontier_trusted_output_artifact_attestation_verified"),
        "frontier_trusted_grader_attestation_verified": summary.get("frontier_trusted_grader_attestation_verified"),
        "frontier_cross_model_ranking_allowed": summary.get("frontier_cross_model_ranking_allowed"),
        "decision_compiler_status": summary.get("decision_compiler_status"),
        "decision_compiler_validation_status": summary.get("decision_compiler_validation_status"),
        "decision_object_count": summary.get("decision_object_count"),
        "decision_conflict_count": summary.get("decision_conflict_count"),
        "decision_blocked_count": summary.get("decision_blocked_count"),
        "decision_compiler_leak_guard_pass": summary.get("decision_compiler_leak_guard_pass"),
        "rsi_outcome_status": summary.get("rsi_outcome_status"),
        "rsi_outcome_validation_status": summary.get("rsi_outcome_validation_status"),
        "rsi_outcome_mature": summary.get("rsi_outcome_mature"),
        "rsi_outcome_maturity_status": summary.get("rsi_outcome_maturity_status"),
        "rsi_live_complete_stable_count": summary.get("rsi_live_complete_stable_count"),
        "rsi_missing_link_debt_item_count": summary.get("rsi_missing_link_debt_item_count"),
        "rsi_live_authority_violation_count": summary.get("rsi_live_authority_violation_count"),
        "rsi_live_trace_unique_correlation_id_count": summary.get("rsi_live_trace_unique_correlation_id_count"),
        "rsi_live_trace_duplicate_correlation_id_count": summary.get("rsi_live_trace_duplicate_correlation_id_count"),
        "rsi_live_trace_missing_correlation_id_count": summary.get("rsi_live_trace_missing_correlation_id_count"),
        "rsi_live_trace_noncanonical_correlation_id_count": summary.get("rsi_live_trace_noncanonical_correlation_id_count"),
        "rsi_correlation_integrity_gate_met": summary.get("rsi_correlation_integrity_gate_met"),
        "advanced_pilot_status": summary.get("advanced_pilot_status"),
        "advanced_pilot_validation_status": summary.get("advanced_pilot_validation_status"),
        "advanced_pilot_count": summary.get("advanced_pilot_count"),
        "advanced_pilot_executed_count": summary.get("advanced_pilot_executed_count"),
        "advanced_pilot_promotion_ready_count": summary.get("advanced_pilot_promotion_ready_count"),
        "advanced_pilot_external_api_calls_performed": summary.get("advanced_pilot_external_api_calls_performed"),
        "advanced_pilot_raw_content_stored": summary.get("advanced_pilot_raw_content_stored"),
        "advanced_pilot_fixture_contract_safe": summary.get("advanced_pilot_fixture_contract_safe"),
        "next_safe_action": "Refresh wiki synthesis after WF88/WF74/PM/OTEL producers and keep warnings visible until routed or resolved.",
    }


def summarize_loop_trace(trace: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(trace.get("summary"))
    source_spine = as_dict(trace.get("source_spine"))
    validation = as_dict(trace.get("validation"))
    return {
        "source_status": trace.get("status"),
        "validation_status": validation.get("status"),
        "trace_row_count": summary.get("trace_row_count"),
        "missing_destination_count": summary.get("missing_destination_count"),
        "high_priority_unrouted_count": summary.get("high_priority_unrouted_count"),
        "pm_job_link_count": summary.get("pm_job_link_count"),
        "lane_link_count": summary.get("lane_link_count"),
        "lane_link_missing_count": summary.get("lane_link_missing_count"),
        "completed_lane_missing_closeout_count": summary.get("completed_lane_missing_closeout_count"),
        "completed_lane_missing_memory_ref_count": summary.get("completed_lane_missing_memory_ref_count"),
        "duplicate_pm_job_id_count": summary.get("duplicate_pm_job_id_count"),
        "downstream_stale_after_router_count": summary.get("downstream_stale_after_router_count"),
        "otel_event_count": source_spine.get("otel_event_count"),
        "model_learning_row_count": source_spine.get("model_learning_row_count"),
        "implementation_token_gap_count": source_spine.get("implementation_token_gap_count") or summary.get("implementation_token_gap_count"),
        "next_safe_action": summary.get("next_safe_action") or "Refresh the loop trace after WF74 router, PM queue, or lane register changes.",
    }


def summarize_long_work_jobs(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    return {
        "source_status": packet.get("status"),
        "validation_status": validation.get("status"),
        "job_count": summary.get("job_count"),
        "active_job_count": summary.get("active_job_count"),
        "terminal_job_count": summary.get("terminal_job_count"),
        "resumable_job_count": summary.get("resumable_job_count"),
        "blocked_job_count": summary.get("blocked_job_count"),
        "stale_active_job_count": summary.get("stale_active_job_count"),
        "status_counts": summary.get("status_counts"),
        "resumable_job_ids": summary.get("resumable_job_ids"),
        "blocked_job_ids": summary.get("blocked_job_ids"),
        "stale_active_job_ids": summary.get("stale_active_job_ids"),
        "next_safe_action": summary.get("next_safe_action") or "Refresh the long-work status packet before resuming provider-backed or full-source local jobs.",
    }


def summarize_skill_workshop_guard(guard: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(guard.get("summary"))
    return {
        "source_status": guard.get("status"),
        "validation_status": as_dict(guard.get("validation")).get("status"),
        "critical_count": summary.get("critical_count"),
        "live_error_count": summary.get("live_error_count"),
        "live_warning_count": summary.get("live_warning_count"),
        "pair_status": summary.get("pair_status"),
        "next_safe_action": "Run the existing body guard before and after Skill Workshop apply; do not create duplicate guards for this failure mode.",
    }


def summarize_finance_query_friction_guard(guard: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(guard.get("summary"))
    return {
        "source_status": guard.get("status"),
        "validation_status": as_dict(guard.get("validation")).get("status"),
        "validation_warning_count": summary.get("validation_warning_count"),
        "live_routing_tier_a_count": summary.get("live_routing_tier_a_count"),
        "live_routing_tier_b_count": summary.get("live_routing_tier_b_count"),
        "live_routing_tier_c_count": summary.get("live_routing_tier_c_count"),
        "membership_scope_tier_a_count": summary.get("membership_scope_tier_a_count"),
        "membership_scope_tier_b_count": summary.get("membership_scope_tier_b_count"),
        "membership_scope_tier_c_count": summary.get("membership_scope_tier_c_count"),
        "tier_b_delta_live_minus_membership": summary.get("tier_b_delta_live_minus_membership"),
        "promotion_candidate_count": summary.get("promotion_candidate_count"),
        "promotion_tier_c_attention_count": summary.get("promotion_tier_c_attention_count"),
        "promotion_c_to_b_evidence_complete_count": summary.get("promotion_c_to_b_evidence_complete_count"),
        "promotion_evidence_repair_count": summary.get("promotion_evidence_repair_count"),
        "jsonl_valid_event_count": summary.get("jsonl_valid_event_count"),
        "latest_source_day": summary.get("latest_source_day"),
        "latest_source_day_event_count": summary.get("latest_source_day_event_count"),
        "latest_source_day_single_sweep": summary.get("latest_source_day_single_sweep"),
        "tier_a_b_band_numeric_collision_risk": summary.get("tier_a_b_band_numeric_collision_risk"),
        "recommended_query_mode": summary.get("recommended_query_mode"),
        "next_safe_action": summary.get("next_safe_action") or "Run the guard before WF78/WF88 tier-routing answers.",
    }


def summarize_finance_cache_frontdoor(frontdoor: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(frontdoor.get("summary"))
    boundary = as_dict(frontdoor.get("authority_boundary"))
    return {
        "source_status": frontdoor.get("status"),
        "validation_status": as_dict(frontdoor.get("validation")).get("status"),
        "ticker_count": summary.get("ticker_count"),
        "safe_cached_review_answer_count": summary.get("safe_cached_review_answer_count"),
        "safe_material_claim_from_cache_count": summary.get("safe_material_claim_from_cache_count"),
        "material_claim_source_open_required_count": summary.get("material_claim_source_open_required_count"),
        "refresh_or_source_open_needed_count": summary.get("refresh_or_source_open_needed_count"),
        "source_open_status_counts": summary.get("source_open_status_counts"),
        "decision_state_counts": summary.get("decision_state_counts"),
        "timing_state_counts": summary.get("timing_state_counts"),
        "trade_readiness_state_counts": summary.get("trade_readiness_state_counts"),
        "authority_state_counts": summary.get("authority_state_counts"),
        "sql_first_truth_production_retained": boundary.get("sql_first_truth_production_retained"),
        "cache_first_chat_consumption": boundary.get("cache_first_chat_consumption"),
        "source_open_required_for_material_claims": boundary.get("source_open_required_for_material_claims"),
        "next_safe_action": summary.get("next_safe_action") or "Use finance-cache-frontdoor for lightweight chat answers before deeper WF84/WF85 drills.",
    }


def summarize_route_readiness_p3(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    return {
        "source_status": packet.get("status"),
        "validation_status": validation.get("status"),
        "market_window_state": summary.get("market_window_state"),
        "market_holiday": summary.get("market_holiday"),
        "market_window_refresh_required_count": summary.get("market_window_refresh_required_count"),
        "category_counts": summary.get("category_counts"),
        "top_review_queue_tickers": summary.get("top_review_queue_tickers"),
        "approval_card_candidate_owner_gated_tickers": summary.get("approval_card_candidate_owner_gated_tickers"),
        "in_band_review_monitor_tickers": summary.get("in_band_review_monitor_tickers"),
        "next_safe_action": summary.get("next_safe_action") or "Use P3 ranking for review-only route triage; market-window refresh and owner gates remain required.",
    }


def _blocked_component_status(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return not normalized or normalized == "error" or "blocked" in normalized


def _frontier_component_state(wiki: dict[str, Any]) -> str:
    if wiki.get("frontier_eval_validation_status") != "ok" or _blocked_component_status(wiki.get("frontier_eval_status")):
        return "blocked"
    ready = (
        int(wiki.get("frontier_result_row_count") or 0) > 0
        and "warning" not in str(wiki.get("frontier_eval_status") or "").lower()
        and wiki.get("frontier_all_assignment_execution_proven") is True
        and wiki.get("frontier_proof_index_chain_verified") is True
        and wiki.get("frontier_all_comparison_gates_passed") is True
        and wiki.get("frontier_trusted_execution_attestation_verified") is True
        and wiki.get("frontier_trusted_output_artifact_attestation_verified") is True
        and wiki.get("frontier_trusted_grader_attestation_verified") is True
        and wiki.get("frontier_cross_model_ranking_allowed") is True
    )
    return "review_ready" if ready else "followup_required"


def _compiler_retrieval_component_state(wiki: dict[str, Any]) -> str:
    compiler_validation = wiki.get("decision_compiler_validation_status")
    retrieval_blocked = (
        wiki.get("retrieval_quality_status") != "ok"
        or wiki.get("retrieval_quality_validation_status") in {None, "blocked", "error"}
    )
    retrieval_ready = (
        wiki.get("retrieval_quality_status") == "ok"
        and wiki.get("retrieval_quality_validation_status") == "ok"
        and int(wiki.get("retrieval_fixture_count") or 0) >= 30
        and int(wiki.get("retrieval_failed_count") or 0) == 0
        and int(wiki.get("retrieval_passed_count") or 0) == int(wiki.get("retrieval_fixture_count") or 0)
        and int(wiki.get("retrieval_live_source_timestamp_age_assessment_count") or 0) >= 1
        and wiki.get("retrieval_label_only_cases_are_live_source_proof") is False
        and wiki.get("retrieval_declared_labels_are_authoritative") is False
        and wiki.get("retrieval_source_timestamp_age_is_live_source_proof") is True
    )
    compiler_blocked = (
        compiler_validation in {None, "blocked", "error"}
        or _blocked_component_status(wiki.get("decision_compiler_status"))
        or wiki.get("decision_compiler_leak_guard_pass") is not True
        or int(wiki.get("decision_blocked_count") or 0) > 0
        or int(wiki.get("decision_conflict_count") or 0) > 0
    )
    if compiler_blocked or retrieval_blocked:
        return "blocked"
    if not retrieval_ready:
        return "repair_queue"
    if compiler_validation == "warning" or "warning" in str(wiki.get("decision_compiler_status") or "").lower():
        return "warning_review_only"
    return "review_ready" if compiler_validation == "ok" and int(wiki.get("decision_object_count") or 0) > 0 else "repair_queue"


def _rsi_component_state(wiki: dict[str, Any]) -> str:
    integrity_blocked = (
        wiki.get("rsi_outcome_validation_status") in {None, "blocked", "error"}
        or _blocked_component_status(wiki.get("rsi_outcome_status"))
        or int(wiki.get("rsi_live_authority_violation_count") or 0) > 0
        or int(wiki.get("rsi_live_trace_duplicate_correlation_id_count") or 0) > 0
        or int(wiki.get("rsi_live_trace_missing_correlation_id_count") or 0) > 0
        or int(wiki.get("rsi_live_trace_noncanonical_correlation_id_count") or 0) > 0
        or wiki.get("rsi_correlation_integrity_gate_met") is not True
    )
    if integrity_blocked:
        return "blocked"
    mature = (
        wiki.get("rsi_outcome_validation_status") == "ok"
        and "warning" not in str(wiki.get("rsi_outcome_status") or "").lower()
        and wiki.get("rsi_outcome_mature") is True
        and int(wiki.get("rsi_live_complete_stable_count") or 0) > 0
        and int(wiki.get("rsi_missing_link_debt_item_count") or 0) == 0
    )
    return "review_ready" if mature else "followup_required"


def _advanced_pilot_component_state(wiki: dict[str, Any]) -> str:
    fixture_safe = (
        wiki.get("advanced_pilot_fixture_contract_safe") is True
        and wiki.get("advanced_pilot_status") == "fixture_ready_no_execution_authority"
        and wiki.get("advanced_pilot_validation_status") == "ok"
        and int(wiki.get("advanced_pilot_count") or 0) >= 6
        and int(wiki.get("advanced_pilot_executed_count") or 0) == 0
        and int(wiki.get("advanced_pilot_promotion_ready_count") or 0) == 0
        and wiki.get("advanced_pilot_external_api_calls_performed") is False
        and wiki.get("advanced_pilot_raw_content_stored") is False
    )
    return "fixture_ready_execution_gated" if fixture_safe else "blocked"


def canonical_action_state(packet: dict[str, Any]) -> list[dict[str, Any]]:
    wf87 = as_dict(packet.get("wf87_runtime_governor"))
    wf67 = as_dict(packet.get("wf67_paper_guardrail"))
    cleanup = as_dict(packet.get("retired_surface_cleanup"))
    contraction = as_dict(packet.get("route_contraction"))
    classifier = as_dict(packet.get("source_open_residue_classifier"))
    readiness = as_dict(packet.get("delete_readiness"))
    recommendation_ledger = as_dict(packet.get("recommendation_outcome_ledger"))
    learning = as_dict(packet.get("finance_learning_loop"))
    decision_os = as_dict(packet.get("wf85_decision_os"))
    ops = as_dict(packet.get("ops_control"))
    wiki = as_dict(packet.get("wiki_synthesis"))
    loop_trace = as_dict(packet.get("wf74_wf88_loop_trace"))
    long_work = as_dict(packet.get("long_work_job_status"))
    skill_guard = as_dict(packet.get("skill_workshop_body_guard"))
    finance_query_guard = as_dict(packet.get("finance_query_friction_guard"))
    finance_cache = as_dict(packet.get("finance_cache_frontdoor"))
    route_readiness_p3 = as_dict(packet.get("wf78_route_readiness_p3"))
    tmp_ready = int(readiness.get("tmp_delete_ready_after_owner_approval_count") or 0)
    tmp_applied = int(readiness.get("tmp_delete_already_applied_count") or 0)
    delete_state = "approved_tmp_microbatch_applied" if tmp_ready == 0 and tmp_applied else "owner_ready_no_apply"
    delete_summary = (
        f"Approved tmp delete microbatch already applied: {tmp_applied}; pending tmp delete candidates ready after owner approval: {tmp_ready}; "
        f"DB archive candidates ready after owner approval: {readiness.get('db_archive_ready_after_owner_approval_count')}."
        if tmp_applied
        else f"Tmp delete candidates ready after owner approval: {tmp_ready}; DB archive candidates ready after owner approval: {readiness.get('db_archive_ready_after_owner_approval_count')}."
    )
    rows = [
        {
            "id": "wf87-runtime-governor-fail-closed",
            "owner_workflow": "WF87",
            "state": "blocked_owner_gated",
            "summary": "WF87 maturity improved but execution-time proof is fail-closed and Phase B round trips are not mature.",
            "next_action": wf87.get("next_safe_action"),
            "authority": "review_only_no_execution",
        },
        {
            "id": "wf67-paper-guardrail-blocked-cards",
            "owner_workflow": "WF67",
            "state": "blocked_owner_gated" if int(wf67.get("blocked_candidate_count") or 0) else "guardrail_visible",
            "summary": (
                f"WF67 manager cards: {wf67.get('candidate_card_count')}; "
                f"blocked candidates: {wf67.get('blocked_candidate_count')}; "
                f"ready tickers: {wf67.get('ready_tickers') or []}."
            ),
            "next_action": wf67.get("operator_next_action") or "Refresh WF67 guard proof only when an exact paper action is being prepared.",
            "authority": "paper_guardrail_only_exact_owner_approval_required",
        },
        {
            "id": "wf88-cleanup-route-contraction",
            "owner_workflow": "WF88",
            "state": "proposal_ready_no_apply_authority",
            "summary": f"{cleanup.get('script_route_contraction_exact_file_count')} exact route-contraction files identified; {contraction.get('contracted_or_already_narrowed_count')} are contracted or already narrowed; script deletion ready now is {contraction.get('script_deletion_ready_now_count')}.",
            "next_action": contraction.get("next_safe_action") or "Lease exact route-contraction files; keep deletion/archive/apply behind separate owner approval.",
            "authority": "review_only_no_delete_archive_apply",
        },
        {
            "id": "wf88-source-open-residue-classification",
            "owner_workflow": "WF88",
            "state": "default_runtime_drag_removed",
            "summary": f"Source-open blocked rows: {classifier.get('source_open_blocked_count')}; default runtime blockers: {classifier.get('default_runtime_blocker_count')}; active SQL/JSON repair rows: {classifier.get('active_sql_json_tier_repair_count')}.",
            "next_action": classifier.get("next_safe_action"),
            "authority": "review_only_finance_domain_classification_no_delete",
        },
        {
            "id": "wf88-delete-readiness-owner-packets",
            "owner_workflow": "WF88",
            "state": delete_state,
            "summary": delete_summary,
            "next_action": readiness.get("next_safe_action"),
            "authority": "owner_approval_required_no_delete_archive_performed",
        },
        {
            "id": "wf88-learning-loop-measurement",
            "owner_workflow": "WF88",
            "state": "measure_not_claim",
            "summary": f"{learning.get('scoreable_decision_count')} scoreable decisions; model/performance claims remain disabled unless explicit packet allows them.",
            "next_action": "Keep grading outcomes and connect finance-call intake before making quality claims.",
            "authority": "learning_signal_only",
        },
        {
            "id": "wf88-wiki-synthesis-layer",
            "owner_workflow": "WF88",
            "state": "blocked" if wiki.get("validation_status") == "blocked" else "synthesis_active_with_visible_warnings",
            "summary": f"Wiki pages: {wiki.get('wiki_page_count')}; self-prompts: {wiki.get('self_prompt_count')}; leak guard pass: {wiki.get('recommendation_leak_guard_pass')}; decision objects: {wiki.get('decision_object_count')}; RSI outcome maturity: {wiki.get('rsi_outcome_maturity_status')}.",
            "next_action": wiki.get("next_safe_action"),
            "authority": "review_only_synthesis_no_canon_or_apply",
        },
        {
            "id": "wf88-frontier-capability-eval-spine",
            "owner_workflow": "WF88",
            "state": _frontier_component_state(wiki),
            "summary": f"Frozen frontier cases: {wiki.get('frontier_fixture_count')}; collected/fully verified result rows: {wiki.get('frontier_result_row_count')}/{wiki.get('frontier_fully_verified_result_count')}; execution: {wiki.get('frontier_model_execution_state')}; ranking allowed: {wiki.get('frontier_cross_model_ranking_allowed')}.",
            "next_action": "Collect blinded source-identical metadata results through the scorer surface; do not rank an empty scaffold.",
            "authority": "review_only_eval_no_route_or_model_promotion",
        },
        {
            "id": "wf88-decision-compiler-and-retrieval",
            "owner_workflow": "WF88",
            "state": _compiler_retrieval_component_state(wiki),
            "summary": f"Decision objects: {wiki.get('decision_object_count')}; conflicts: {wiki.get('decision_conflict_count')}; retrieval pass: {wiki.get('retrieval_passed_count')}/{wiki.get('retrieval_fixture_count')} across {wiki.get('retrieval_class_count')} classes; live timestamp-age proofs: {wiki.get('retrieval_live_source_timestamp_age_assessment_count')}.",
            "next_action": "Use the deterministic compiler as first-hop decision truth and keep wiki/OS2 out of its runtime inputs.",
            "authority": "review_only_decision_compilation_no_apply_or_execution",
        },
        {
            "id": "wf88-rsi-later-outcome-scorecard",
            "owner_workflow": "WF74-WF88",
            "state": _rsi_component_state(wiki),
            "summary": f"Stable linked closures: {wiki.get('rsi_live_complete_stable_count')}; missing linkage/metric debt: {wiki.get('rsi_missing_link_debt_item_count')}; unique/duplicate/missing/noncanonical correlations: {wiki.get('rsi_live_trace_unique_correlation_id_count')}/{wiki.get('rsi_live_trace_duplicate_correlation_id_count')}/{wiki.get('rsi_live_trace_missing_correlation_id_count')}/{wiki.get('rsi_live_trace_noncanonical_correlation_id_count')}; maturity: {wiki.get('rsi_outcome_maturity_status')}.",
            "next_action": "Add exact RSI correlation and stayed-closed, recurrence, SLA, efficiency, and later-grade observations at owner sources.",
            "authority": "review_only_outcome_scoring_no_self_modification_or_apply",
        },
        {
            "id": "wf88-advanced-capability-pilot-contracts",
            "owner_workflow": "WF88",
            "state": _advanced_pilot_component_state(wiki),
            "summary": f"Fixture-ready pilots: {wiki.get('advanced_pilot_count')}; executed: {wiki.get('advanced_pilot_executed_count')}; promotion-ready: {wiki.get('advanced_pilot_promotion_ready_count')}.",
            "next_action": "Keep pilots isolated until a separately gated runner provides matched, privacy-safe execution evidence.",
            "authority": "fixture_only_no_api_execution_route_runtime_or_promotion_authority",
        },
        {
            "id": "wf74-wf88-loop-trace-spine",
            "owner_workflow": "WF74-WF88",
            "state": (
                "blocked"
                if loop_trace.get("validation_status") == "blocked"
                or int(loop_trace.get("high_priority_unrouted_count") or 0)
                or int(loop_trace.get("duplicate_pm_job_id_count") or 0)
                else "warning"
                if loop_trace.get("validation_status") == "warning"
                or int(loop_trace.get("downstream_stale_after_router_count") or 0)
                or int(loop_trace.get("lane_link_missing_count") or 0)
                else "clean"
            ),
            "summary": (
                f"Trace rows: {loop_trace.get('trace_row_count')}; "
                f"PM/lane links: {loop_trace.get('pm_job_link_count')}/{loop_trace.get('lane_link_count')}; "
                f"missing destinations: {loop_trace.get('missing_destination_count')}; "
                f"stale consumers: {loop_trace.get('downstream_stale_after_router_count')}."
            ),
            "next_action": loop_trace.get("next_safe_action"),
            "authority": "review_only_trace_no_apply_or_execution",
        },
        {
            "id": "runtime-long-work-job-status-spine",
            "owner_workflow": "RUNTIME",
            "state": (
                "blocked"
                if long_work.get("validation_status") == "blocked"
                or int(long_work.get("blocked_job_count") or 0)
                else "resumable"
                if int(long_work.get("resumable_job_count") or 0)
                else "warning"
                if long_work.get("validation_status") == "warning"
                or int(long_work.get("stale_active_job_count") or 0)
                or int(long_work.get("active_job_count") or 0)
                else "clean"
            ),
            "summary": (
                f"Long-work jobs: {long_work.get('job_count')}; active/resumable/blocked/stale: "
                f"{long_work.get('active_job_count')}/{long_work.get('resumable_job_count')}/"
                f"{long_work.get('blocked_job_count')}/{long_work.get('stale_active_job_count')}."
            ),
            "next_action": long_work.get("next_safe_action"),
            "authority": "review_only_runtime_status_resume_no_cron_or_config_mutation",
        },
        {
            "id": "wf88-skill-workshop-body-guard-enforcement",
            "owner_workflow": "WF88",
            "state": "guard_clean" if skill_guard.get("critical_count") in (0, None) and skill_guard.get("live_error_count") in (0, None) else "blocked",
            "summary": f"Existing Skill Workshop body guard criticals: {skill_guard.get('critical_count')}; live errors: {skill_guard.get('live_error_count')}; pair status: {skill_guard.get('pair_status')}.",
            "next_action": skill_guard.get("next_safe_action"),
            "authority": "review_only_guard_route_no_duplicate_script",
        },
        {
            "id": "wf88-finance-query-friction-guard",
            "owner_workflow": "WF88",
            "state": "guard_active_review_only" if finance_query_guard.get("validation_status") == "ok" else "blocked",
            "summary": (
                f"Live routing B count: {finance_query_guard.get('live_routing_tier_b_count')}; "
                f"membership-scope B count: {finance_query_guard.get('membership_scope_tier_b_count')}; "
                f"valid JSONL events: {finance_query_guard.get('jsonl_valid_event_count')}; "
                f"latest source-day single sweep: {finance_query_guard.get('latest_source_day_single_sweep')}."
            ),
            "next_action": finance_query_guard.get("next_safe_action"),
            "authority": "review_only_query_guard_no_sql_or_routing_mutation",
        },
        {
            "id": "finance-cache-frontdoor-chat-route",
            "owner_workflow": "WF88",
            "state": "cache_first_chat_ready" if finance_cache.get("validation_status") == "ok" else "blocked",
            "summary": (
                f"Cache front door tickers: {finance_cache.get('ticker_count')}; "
                f"safe cached review answers: {finance_cache.get('safe_cached_review_answer_count')}; "
                f"safe material-claim cache rows: {finance_cache.get('safe_material_claim_from_cache_count')}; "
                f"material source-open required: {finance_cache.get('material_claim_source_open_required_count')}."
            ),
            "next_action": finance_cache.get("next_safe_action"),
            "authority": "review_only_chat_facade_sql_first_truth_source_open_material_claims",
        },
        {
            "id": "recommendation-outcome-backlog",
            "owner_workflow": "WF88",
            "state": "ungraded_backlog",
            "summary": f"Recommendation tracked rows: {recommendation_ledger.get('tracked_row_count')}; pending owner decisions: {recommendation_ledger.get('pending_owner_decision_rows')}; later-outcome graded rows: {recommendation_ledger.get('later_outcome_graded_rows')}.",
            "next_action": "Refresh and grade outcomes before making performance claims.",
            "authority": "review_only_measurement_no_model_claim",
        },
        {
            "id": "wf85-source-open-repair-queue",
            "owner_workflow": "WF85",
            "state": "repair_queue",
            "summary": f"WF85 source-open blocked rows: {classifier.get('source_open_blocked_count')}; default runtime blockers: {classifier.get('default_runtime_blocker_count')}; active SQL/JSON repair rows: {classifier.get('active_sql_json_tier_repair_count')}; Decision OS status is {decision_os.get('source_status')}.",
            "next_action": decision_os.get("next_safe_action"),
            "authority": "review_only_decision_packet",
        },
        {
            "id": "improvement-ledger-open-followups",
            "owner_workflow": "WF88",
            "state": "followup_required",
            "summary": f"{ops.get('improvement_open_count')} open improvements; {ops.get('improvement_high_priority_overdue_count')} high-priority overdue.",
            "next_action": "Route exact high-priority improvements through lane register instead of broad cleanup.",
            "authority": "review_only_route_control",
        },
    ]
    return rows


def build_packet() -> dict[str, Any]:
    governor = load_optional_json(WF87_GOVERNOR)
    wf67_manager = load_optional_json(WF67_MANAGER)
    cleanup = load_optional_json(WF88_CLEANUP_PLAN)
    route_contraction = load_optional_json(WF88_ROUTE_CONTRACTION)
    source_open_classifier = load_optional_json(WF88_SOURCE_OPEN_CLASSIFIER)
    delete_readiness = load_optional_json(WF88_DELETE_READINESS)
    recommendation_ledger = load_optional_json(RECOMMENDATION_LEDGER)
    wf55 = load_optional_json(WF55_LEDGER)
    finance_digest = load_optional_json(FINANCE_DIGEST)
    wf85 = load_optional_json(WF85_PACKET)
    wf74 = load_optional_json(WF74_DOCKET)
    loop_trace = load_optional_json(WF74_WF88_LOOP_TRACE)
    long_work = load_optional_json(LONG_WORK_JOB_STATUS)
    improvement = load_optional_json(IMPROVEMENT_LEDGER)
    pm = load_optional_json(PM_CONTROL)
    cron = load_optional_json(CRON_CONTROL)
    otel = load_optional_json(OTEL_CONTROL)
    wiki_synthesis = load_optional_json(WF88_WIKI_SYNTHESIS)
    skill_workshop_guard = load_optional_json(SKILL_WORKSHOP_BODY_GUARD)
    finance_query_guard = load_optional_json(WF88_FINANCE_QUERY_FRICTION_GUARD)
    finance_cache_frontdoor = load_optional_json(FINANCE_CACHE_FRONTDOOR)
    route_readiness_p3 = load_optional_json(WF78_ROUTE_READINESS_P3)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "control_packet_ready_no_apply_authority",
        "purpose": "Thin WF88 into the measured OS 2.0 routing, learning, cleanup-planning, and action-state control layer.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf87_runtime_governor": source_descriptor(WF87_GOVERNOR, max_age_hours=24),
            "wf67_paper_guardrail_manager": source_descriptor(WF67_MANAGER, max_age_hours=24),
            "wf88_retired_surface_cleanup_plan": source_descriptor(WF88_CLEANUP_PLAN, max_age_hours=24),
            "wf88_route_contraction_packet": source_descriptor(WF88_ROUTE_CONTRACTION, required=False, max_age_hours=24),
            "wf88_source_open_residue_classifier": source_descriptor(WF88_SOURCE_OPEN_CLASSIFIER, max_age_hours=24),
            "wf88_delete_readiness_packet": source_descriptor(WF88_DELETE_READINESS, max_age_hours=24),
            "recommendation_outcome_ledger_current": source_descriptor(RECOMMENDATION_LEDGER, max_age_hours=168),
            "wf55_autonomy_outcome_ledger": source_descriptor(WF55_LEDGER, max_age_hours=72),
            "finance_decision_performance_digest": source_descriptor(FINANCE_DIGEST, max_age_hours=72),
            "wf85_decision_os_review_packet": source_descriptor(WF85_PACKET, max_age_hours=24),
            "wf74_decision_docket": source_descriptor(WF74_DOCKET, max_age_hours=24),
            "wf74_wf88_loop_trace": source_descriptor(WF74_WF88_LOOP_TRACE, max_age_hours=24),
            "long_work_job_status": source_descriptor(LONG_WORK_JOB_STATUS, max_age_hours=24),
            "improvement_ledger_current": source_descriptor(IMPROVEMENT_LEDGER, max_age_hours=24),
            "pm_control_packet": source_descriptor(PM_CONTROL, max_age_hours=4),
            "cron_control_packet": source_descriptor(CRON_CONTROL, max_age_hours=4),
            "otel_ops_control": source_descriptor(OTEL_CONTROL, max_age_hours=4),
            "wf88_wiki_synthesis_packet": source_descriptor(WF88_WIKI_SYNTHESIS, max_age_hours=24),
            "skill_workshop_body_guard": source_descriptor(SKILL_WORKSHOP_BODY_GUARD, max_age_hours=24),
            "wf88_finance_query_friction_guard": source_descriptor(WF88_FINANCE_QUERY_FRICTION_GUARD, max_age_hours=24),
            "finance_cache_frontdoor": source_descriptor(FINANCE_CACHE_FRONTDOOR, max_age_hours=12),
            "wf78_route_readiness_p3_market_ranking": source_descriptor(WF78_ROUTE_READINESS_P3, max_age_hours=12),
        },
        "unified_routing_contract": {
            "wf67_to_wf87": "WF67 remains the paper-only execution guardrail; WF87 may consume its readiness only as fail-closed runtime proof, not as approval.",
            "wf85_to_wf87": "WF85 emits review-only decision candidates; WF87 may consume them only for paper-autonomy runtime eligibility proof.",
            "wf87_to_wf88": "WF87 exports runtime eligibility, blockers, and outcome signals; WF88 owns grading, experiments, cleanup, and OS-wide action state.",
            "wf74_to_wf88": "WF74 turns repeated failures and measured lessons into proposal-only improvement work; WF88 summarizes those actions and keeps them routed through PM or owner-gated packets.",
            "wf74_wf88_loop_trace": "The loop trace stitches each current WF74 opportunity through router, docket, PM job, lane, closeout proof, memory refs, and WF88 consumer freshness.",
            "long_work_job_status": "Long-running local jobs must publish checkpoint/status rows with bounded resume commands so future sessions can resume or close them without waiting on one foreground tool call.",
            "wf88_to_wf67": "WF88 may surface WF67-ready or blocked card state, but it must never approve, submit, cancel, sell, refresh a kill switch, or infer paper execution authority.",
            "wf88_to_work_queue": "WF88 produces canonical action-state rows and route-contraction proposals; apply/delete/archive/cron mutation require separate approval packets.",
            "wf88_to_wiki": "WF88 wiki synthesis turns control/eval/proposal state into durable source-linked pages for new sessions, without canon or apply authority.",
            "do_not_duplicate": [
                "WF87 must not own OS-wide learning, cleanup, coding outcomes, behavior portability, or dashboards.",
                "WF67 must remain the only paper execution guardrail; WF88 and WF87 may only consume WF67 status as review-only proof.",
                "WF88 must not approve or execute paper/live brokerage actions.",
                "WF74 must not create self-modification authority; WF88 may route WF74 lessons only as proposal, validator, PM, Skill Workshop, owner-packet, or monitor-only rows.",
                "Long-work status packets may recommend bounded resume commands; they must not mutate cron schedules, runtime config, finance canon, portfolio state, execution surfaces, or owner approvals.",
                "The wiki layer must not become a second canon, approval, portfolio, execution, or model-training source.",
                "Skill Workshop body-replacement prevention must use scripts/skill_workshop_body_guard.py, not a duplicate guard or parallel procedure.",
                "WF88 finance-query guard must label live routing, membership scope, band completeness, and scheduled-sweep event counts instead of collapsing them into one number.",
                "Finance cache front door is a chat facade only: SQL-first for truth production, cache-first for chat consumption, source-open for material claims.",
            ],
        },
        "wf87_runtime_governor": summarize_wf87(governor),
        "wf67_paper_guardrail": summarize_wf67(wf67_manager),
        "retired_surface_cleanup": summarize_cleanup(cleanup),
        "route_contraction": summarize_route_contraction(route_contraction),
        "source_open_residue_classifier": summarize_source_open_classifier(source_open_classifier),
        "delete_readiness": summarize_delete_readiness(delete_readiness),
        "recommendation_outcome_ledger": summarize_recommendation_ledger(recommendation_ledger),
        "finance_learning_loop": summarize_learning(wf55, finance_digest),
        "wf85_decision_os": summarize_decision_os(wf85),
        "ops_control": summarize_ops(pm, cron, otel, improvement, wf74),
        "wiki_synthesis": summarize_wiki_synthesis(wiki_synthesis),
        "wf74_wf88_loop_trace": summarize_loop_trace(loop_trace),
        "long_work_job_status": summarize_long_work_jobs(long_work),
        "skill_workshop_body_guard": summarize_skill_workshop_guard(skill_workshop_guard),
        "finance_query_friction_guard": summarize_finance_query_friction_guard(finance_query_guard),
        "finance_cache_frontdoor": summarize_finance_cache_frontdoor(finance_cache_frontdoor),
        "wf78_route_readiness_p3": summarize_route_readiness_p3(route_readiness_p3),
        "route_contraction_policy": {
            "default": "reduce default runtime surfaces before deleting files",
            "first_targets": [
                "Keep scripts/ticker_answer_packet.py compatibility-only.",
                "Move old human-note parity checks out of default runtime scoring.",
                "Mode-gate legacy table/header checks.",
                "Relabel human notes as context, policy, and narrative rather than structured owners.",
            ],
            "delete_allowed_now": False,
            "archive_allowed_now": False,
            "cron_mutation_allowed_now": False,
        },
        "stop_lines": [
            "No delete, archive, move, apply, cron mutation, config/runtime/auth mutation, or external/customer action.",
            "No portfolio/canon/cash/sizing/risk mutation and no paper/live/brokerage/account action.",
            "No model-training claim, raw prompt/tool capture, or inferred owner approval.",
            "Generated control packets route work; they do not become canon or execution authority.",
        ],
    }
    packet["canonical_action_state"] = canonical_action_state(packet)
    packet["summary"] = summarize_packet(packet)
    if int(packet["summary"].get("stale_input_count") or 0) > 0:
        packet["status"] = "control_packet_warning_no_apply_authority"
        packet["summary"]["status"] = packet["status"]
    packet["validation"] = validate_packet(packet)
    return packet


def summarize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    wf87 = as_dict(packet.get("wf87_runtime_governor"))
    wf67 = as_dict(packet.get("wf67_paper_guardrail"))
    cleanup = as_dict(packet.get("retired_surface_cleanup"))
    contraction = as_dict(packet.get("route_contraction"))
    classifier = as_dict(packet.get("source_open_residue_classifier"))
    readiness = as_dict(packet.get("delete_readiness"))
    recommendation = as_dict(packet.get("recommendation_outcome_ledger"))
    learning = as_dict(packet.get("finance_learning_loop"))
    ops = as_dict(packet.get("ops_control"))
    wiki = as_dict(packet.get("wiki_synthesis"))
    loop_trace = as_dict(packet.get("wf74_wf88_loop_trace"))
    long_work = as_dict(packet.get("long_work_job_status"))
    skill_guard = as_dict(packet.get("skill_workshop_body_guard"))
    finance_query_guard = as_dict(packet.get("finance_query_friction_guard"))
    finance_cache = as_dict(packet.get("finance_cache_frontdoor"))
    route_readiness_p3 = as_dict(packet.get("wf78_route_readiness_p3"))
    actions = as_list(packet.get("canonical_action_state"))
    blocked = [row for row in actions if as_dict(row).get("state") in {"blocked", "blocked_owner_gated", "followup_required", "repair_queue"}]
    input_rows = as_dict(packet.get("inputs"))
    stale_inputs = [name for name, row in input_rows.items() if as_dict(row).get("freshness_status") == "stale"]
    missing_required = [name for name, row in input_rows.items() if as_dict(row).get("required") and not as_dict(row).get("present")]
    return {
        "status": packet.get("status"),
        "canonical_action_count": len(actions),
        "blocked_or_followup_action_count": len(blocked),
        "stale_input_count": len(stale_inputs),
        "stale_inputs": stale_inputs,
        "missing_required_input_count": len(missing_required),
        "wf87_runtime_status": wf87.get("runtime_status"),
        "wf87_phase_c_owner_review_eligible_now": wf87.get("phase_c_owner_review_eligible_now"),
        "wf87_execution_allowed": wf87.get("execution_allowed"),
        "wf67_manager_status": wf67.get("source_status"),
        "wf67_manager_validation_status": wf67.get("validation_status"),
        "wf67_candidate_card_count": wf67.get("candidate_card_count"),
        "wf67_blocked_candidate_count": wf67.get("blocked_candidate_count"),
        "wf67_ready_tickers": wf67.get("ready_tickers"),
        "cleanup_first_tmp_microbatch_candidate_count": cleanup.get("first_tmp_microbatch_candidate_count"),
        "cleanup_route_contraction_exact_file_count": cleanup.get("script_route_contraction_exact_file_count"),
        "route_contraction_validation_status": contraction.get("validation_status"),
        "route_contraction_contracted_or_narrowed_count": contraction.get("contracted_or_already_narrowed_count"),
        "route_contraction_needs_contraction_count": contraction.get("needs_route_contraction_count"),
        "script_deletion_ready_now_count": contraction.get("script_deletion_ready_now_count"),
        "source_open_blocked_count": classifier.get("source_open_blocked_count"),
        "source_open_default_runtime_blocker_count": classifier.get("default_runtime_blocker_count"),
        "active_sql_json_tier_repair_count": classifier.get("active_sql_json_tier_repair_count"),
        "tmp_delete_ready_after_owner_approval_count": readiness.get("tmp_delete_ready_after_owner_approval_count"),
        "tmp_delete_already_applied_count": readiness.get("tmp_delete_already_applied_count"),
        "db_archive_ready_after_owner_approval_count": readiness.get("db_archive_ready_after_owner_approval_count"),
        "recommendation_tracked_row_count": recommendation.get("tracked_row_count"),
        "recommendation_pending_owner_decision_rows": recommendation.get("pending_owner_decision_rows"),
        "recommendation_later_outcome_graded_rows": recommendation.get("later_outcome_graded_rows"),
        "recommendation_later_outcome_metric_scope": recommendation.get("later_outcome_metric_scope"),
        "recommendation_current_preview_later_outcome_graded_rows": recommendation.get("current_preview_later_outcome_graded_rows"),
        "recommendation_durable_later_outcome_graded_rows": recommendation.get("durable_later_outcome_graded_rows"),
        "recommendation_grade_history_graded_ledger_event_count": recommendation.get("grade_history_graded_ledger_event_count"),
        "scoreable_decision_count": learning.get("scoreable_decision_count"),
        "model_performance_claim_allowed_now": learning.get("model_performance_claim_allowed_now"),
        "pm_status": ops.get("pm_status"),
        "cron_status": ops.get("cron_status"),
        "improvement_open_count": ops.get("improvement_open_count"),
        "wiki_synthesis_status": wiki.get("source_status"),
        "wiki_synthesis_validation_status": wiki.get("validation_status"),
        "wiki_page_count": wiki.get("wiki_page_count"),
        "wiki_self_prompt_count": wiki.get("self_prompt_count"),
        "wiki_recommendation_leak_guard_pass": wiki.get("recommendation_leak_guard_pass"),
        "wiki_action_item_count": wiki.get("action_item_count"),
        "wiki_rsi_status": wiki.get("rsi_status"),
        "wiki_followup_required_open_count": wiki.get("followup_required_open_count"),
        "wiki_retrieval_quality_status": wiki.get("retrieval_quality_status"),
        "wiki_retrieval_quality_validation_status": wiki.get("retrieval_quality_validation_status"),
        "wiki_retrieval_fixture_count": wiki.get("retrieval_fixture_count"),
        "wiki_retrieval_passed_count": wiki.get("retrieval_passed_count"),
        "wiki_retrieval_failed_count": wiki.get("retrieval_failed_count"),
        "wiki_retrieval_class_count": wiki.get("retrieval_class_count"),
        "wiki_retrieval_average_score": wiki.get("retrieval_average_score"),
        "wiki_retrieval_live_source_timestamp_age_assessment_count": wiki.get("retrieval_live_source_timestamp_age_assessment_count"),
        "wiki_retrieval_label_only_cases_are_live_source_proof": wiki.get("retrieval_label_only_cases_are_live_source_proof"),
        "wiki_retrieval_declared_labels_are_authoritative": wiki.get("retrieval_declared_labels_are_authoritative"),
        "wiki_retrieval_source_timestamp_age_is_live_source_proof": wiki.get("retrieval_source_timestamp_age_is_live_source_proof"),
        "wiki_frontier_eval_status": wiki.get("frontier_eval_status"),
        "wiki_frontier_eval_validation_status": wiki.get("frontier_eval_validation_status"),
        "wiki_frontier_fixture_count": wiki.get("frontier_fixture_count"),
        "wiki_frontier_result_row_count": wiki.get("frontier_result_row_count"),
        "wiki_frontier_fully_verified_result_count": wiki.get("frontier_fully_verified_result_count"),
        "wiki_frontier_model_execution_state": wiki.get("frontier_model_execution_state"),
        "wiki_frontier_all_assignment_execution_proven": wiki.get("frontier_all_assignment_execution_proven"),
        "wiki_frontier_proof_index_chain_verified": wiki.get("frontier_proof_index_chain_verified"),
        "wiki_frontier_all_comparison_gates_passed": wiki.get("frontier_all_comparison_gates_passed"),
        "wiki_frontier_trusted_execution_attestation_verified": wiki.get("frontier_trusted_execution_attestation_verified"),
        "wiki_frontier_trusted_output_artifact_attestation_verified": wiki.get("frontier_trusted_output_artifact_attestation_verified"),
        "wiki_frontier_trusted_grader_attestation_verified": wiki.get("frontier_trusted_grader_attestation_verified"),
        "wiki_frontier_cross_model_ranking_allowed": wiki.get("frontier_cross_model_ranking_allowed"),
        "wiki_decision_compiler_status": wiki.get("decision_compiler_status"),
        "wiki_decision_compiler_validation_status": wiki.get("decision_compiler_validation_status"),
        "wiki_decision_object_count": wiki.get("decision_object_count"),
        "wiki_decision_conflict_count": wiki.get("decision_conflict_count"),
        "wiki_decision_blocked_count": wiki.get("decision_blocked_count"),
        "wiki_decision_compiler_leak_guard_pass": wiki.get("decision_compiler_leak_guard_pass"),
        "wiki_rsi_outcome_status": wiki.get("rsi_outcome_status"),
        "wiki_rsi_outcome_validation_status": wiki.get("rsi_outcome_validation_status"),
        "wiki_rsi_outcome_mature": wiki.get("rsi_outcome_mature"),
        "wiki_rsi_outcome_maturity_status": wiki.get("rsi_outcome_maturity_status"),
        "wiki_rsi_live_complete_stable_count": wiki.get("rsi_live_complete_stable_count"),
        "wiki_rsi_missing_link_debt_item_count": wiki.get("rsi_missing_link_debt_item_count"),
        "wiki_rsi_live_authority_violation_count": wiki.get("rsi_live_authority_violation_count"),
        "wiki_rsi_live_trace_unique_correlation_id_count": wiki.get("rsi_live_trace_unique_correlation_id_count"),
        "wiki_rsi_live_trace_duplicate_correlation_id_count": wiki.get("rsi_live_trace_duplicate_correlation_id_count"),
        "wiki_rsi_live_trace_missing_correlation_id_count": wiki.get("rsi_live_trace_missing_correlation_id_count"),
        "wiki_rsi_live_trace_noncanonical_correlation_id_count": wiki.get("rsi_live_trace_noncanonical_correlation_id_count"),
        "wiki_rsi_correlation_integrity_gate_met": wiki.get("rsi_correlation_integrity_gate_met"),
        "wiki_advanced_pilot_status": wiki.get("advanced_pilot_status"),
        "wiki_advanced_pilot_validation_status": wiki.get("advanced_pilot_validation_status"),
        "wiki_advanced_pilot_count": wiki.get("advanced_pilot_count"),
        "wiki_advanced_pilot_executed_count": wiki.get("advanced_pilot_executed_count"),
        "wiki_advanced_pilot_promotion_ready_count": wiki.get("advanced_pilot_promotion_ready_count"),
        "wiki_advanced_pilot_external_api_calls_performed": wiki.get("advanced_pilot_external_api_calls_performed"),
        "wiki_advanced_pilot_raw_content_stored": wiki.get("advanced_pilot_raw_content_stored"),
        "wiki_advanced_pilot_fixture_contract_safe": wiki.get("advanced_pilot_fixture_contract_safe"),
        "loop_trace_status": loop_trace.get("source_status"),
        "loop_trace_validation_status": loop_trace.get("validation_status"),
        "loop_trace_row_count": loop_trace.get("trace_row_count"),
        "loop_trace_missing_destination_count": loop_trace.get("missing_destination_count"),
        "loop_trace_high_priority_unrouted_count": loop_trace.get("high_priority_unrouted_count"),
        "loop_trace_pm_job_link_count": loop_trace.get("pm_job_link_count"),
        "loop_trace_lane_link_count": loop_trace.get("lane_link_count"),
        "loop_trace_lane_link_missing_count": loop_trace.get("lane_link_missing_count"),
        "loop_trace_completed_lane_missing_closeout_count": loop_trace.get("completed_lane_missing_closeout_count"),
        "loop_trace_completed_lane_missing_memory_ref_count": loop_trace.get("completed_lane_missing_memory_ref_count"),
        "loop_trace_duplicate_pm_job_id_count": loop_trace.get("duplicate_pm_job_id_count"),
        "loop_trace_downstream_stale_after_router_count": loop_trace.get("downstream_stale_after_router_count"),
        "loop_trace_otel_event_count": loop_trace.get("otel_event_count"),
        "loop_trace_model_learning_row_count": loop_trace.get("model_learning_row_count"),
        "loop_trace_implementation_token_gap_count": loop_trace.get("implementation_token_gap_count"),
        "long_work_job_status": long_work.get("source_status"),
        "long_work_validation_status": long_work.get("validation_status"),
        "long_work_job_count": long_work.get("job_count"),
        "long_work_active_job_count": long_work.get("active_job_count"),
        "long_work_resumable_job_count": long_work.get("resumable_job_count"),
        "long_work_blocked_job_count": long_work.get("blocked_job_count"),
        "long_work_stale_active_job_count": long_work.get("stale_active_job_count"),
        "long_work_status_counts": long_work.get("status_counts"),
        "long_work_resumable_job_ids": long_work.get("resumable_job_ids"),
        "long_work_blocked_job_ids": long_work.get("blocked_job_ids"),
        "long_work_stale_active_job_ids": long_work.get("stale_active_job_ids"),
        "long_work_next_safe_action": long_work.get("next_safe_action"),
        "skill_workshop_body_guard_status": skill_guard.get("source_status"),
        "skill_workshop_body_guard_validation_status": skill_guard.get("validation_status"),
        "skill_workshop_body_guard_critical_count": skill_guard.get("critical_count"),
        "skill_workshop_body_guard_live_error_count": skill_guard.get("live_error_count"),
        "finance_query_guard_status": finance_query_guard.get("source_status"),
        "finance_query_guard_validation_status": finance_query_guard.get("validation_status"),
        "finance_query_guard_live_tier_b_count": finance_query_guard.get("live_routing_tier_b_count"),
        "finance_query_guard_membership_tier_b_count": finance_query_guard.get("membership_scope_tier_b_count"),
        "finance_query_guard_tier_b_delta_live_minus_membership": finance_query_guard.get("tier_b_delta_live_minus_membership"),
        "finance_query_guard_valid_event_count": finance_query_guard.get("jsonl_valid_event_count"),
        "finance_query_guard_latest_source_day_single_sweep": finance_query_guard.get("latest_source_day_single_sweep"),
        "finance_query_guard_band_collision_risk": finance_query_guard.get("tier_a_b_band_numeric_collision_risk"),
        "finance_cache_frontdoor_status": finance_cache.get("source_status"),
        "finance_cache_frontdoor_validation_status": finance_cache.get("validation_status"),
        "finance_cache_frontdoor_ticker_count": finance_cache.get("ticker_count"),
        "finance_cache_frontdoor_safe_cached_review_answer_count": finance_cache.get("safe_cached_review_answer_count"),
        "finance_cache_frontdoor_safe_material_claim_from_cache_count": finance_cache.get("safe_material_claim_from_cache_count"),
        "finance_cache_frontdoor_material_source_open_required_count": finance_cache.get("material_claim_source_open_required_count"),
        "finance_cache_frontdoor_refresh_or_source_open_needed_count": finance_cache.get("refresh_or_source_open_needed_count"),
        "finance_cache_frontdoor_timing_state_counts": finance_cache.get("timing_state_counts"),
        "finance_cache_frontdoor_trade_readiness_state_counts": finance_cache.get("trade_readiness_state_counts"),
        "finance_cache_frontdoor_authority_state_counts": finance_cache.get("authority_state_counts"),
        "wf78_route_readiness_p3_status": route_readiness_p3.get("source_status"),
        "wf78_route_readiness_p3_validation_status": route_readiness_p3.get("validation_status"),
        "wf78_route_readiness_p3_market_window": route_readiness_p3.get("market_window_state"),
        "wf78_route_readiness_p3_market_holiday": route_readiness_p3.get("market_holiday"),
        "wf78_route_readiness_p3_market_refresh_required_count": route_readiness_p3.get("market_window_refresh_required_count"),
        "wf78_route_readiness_p3_category_counts": route_readiness_p3.get("category_counts"),
        "wf78_route_readiness_p3_top_review_queue_tickers": route_readiness_p3.get("top_review_queue_tickers"),
        "wf78_route_readiness_p3_approval_card_candidate_owner_gated_tickers": route_readiness_p3.get("approval_card_candidate_owner_gated_tickers"),
        "wf78_route_readiness_p3_in_band_review_monitor_tickers": route_readiness_p3.get("in_band_review_monitor_tickers"),
        "finance_cache_frontdoor_sql_first_retained": finance_cache.get("sql_first_truth_production_retained"),
        "finance_cache_frontdoor_cache_first_chat": finance_cache.get("cache_first_chat_consumption"),
        "finance_cache_frontdoor_source_open_material_claims": finance_cache.get("source_open_required_for_material_claims"),
        "next_safe_action": "Use WF87's runtime packet for paper-autonomy proof and WF88's cleanup/action rows for route contraction. No delete/archive/apply/execution.",
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key in (
        "delete_allowed",
        "archive_allowed",
        "move_allowed",
        "apply_allowed",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "sql_mutation_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "paper_or_live_execution_allowed",
        "autonomous_paper_submit_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "customer_or_external_output_allowed",
        "model_training_claim_allowed",
        "raw_prompt_or_tool_capture_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")
    for name, descriptor in as_dict(packet.get("inputs")).items():
        desc = as_dict(descriptor)
        if desc.get("required") and desc.get("present") is not True:
            errors.append(f"missing_required_input:{name}:{desc.get('path')}")
        if desc.get("freshness_status") == "stale":
            warnings.append(f"stale_input:{name}:age_hours={desc.get('age_hours')}:max_age_hours={desc.get('max_age_hours')}")
        if desc.get("freshness_status") == "unknown_generated_at" and desc.get("required"):
            warnings.append(f"unknown_generated_at:{name}")
    if as_dict(packet.get("wf87_runtime_governor")).get("execution_allowed") is not False:
        errors.append("wf87_execution_allowed_must_be_false")
    wf67 = as_dict(packet.get("wf67_paper_guardrail"))
    if wf67:
        if wf67.get("paper_order_execution_allowed") is not False:
            errors.append("wf67_paper_order_execution_allowed_must_be_false")
        if wf67.get("live_trade_or_account_action_allowed") is not False:
            errors.append("wf67_live_trade_or_account_action_allowed_must_be_false")
        if wf67.get("owner_approval_inferred") is not False:
            errors.append("wf67_owner_approval_inferred_must_be_false")
    cleanup = as_dict(packet.get("retired_surface_cleanup"))
    contraction = as_dict(packet.get("route_contraction"))
    if cleanup.get("delete_allowed_now_count") not in (0, None):
        errors.append("cleanup_delete_allowed_now_count_must_be_zero")
    if cleanup.get("archive_allowed_now_count") not in (0, None):
        errors.append("cleanup_archive_allowed_now_count_must_be_zero")
    if len(as_list(packet.get("canonical_action_state"))) == 0:
        errors.append("canonical_action_state_empty")
    if as_dict(packet.get("finance_learning_loop")).get("model_performance_claim_allowed_now") is True:
        warnings.append("model_performance_claim_allowed_now_true_review_required")
    if cleanup.get("script_route_contraction_exact_file_count") in (None, 0):
        warnings.append("no_route_contraction_files_available")
    if contraction and contraction.get("delete_allowed_now_count") not in (0, None):
        errors.append("route_contraction_delete_allowed_now_count_must_be_zero")
    if contraction and contraction.get("archive_allowed_now_count") not in (0, None):
        errors.append("route_contraction_archive_allowed_now_count_must_be_zero")
    if contraction and contraction.get("script_deletion_ready_now_count") not in (0, None):
        errors.append("route_contraction_script_deletion_ready_now_count_must_be_zero")
    classifier = as_dict(packet.get("source_open_residue_classifier"))
    if classifier and classifier.get("default_runtime_blocker_count") not in (0, None):
        errors.append("source_open_default_runtime_blocker_count_must_be_zero")
    readiness = as_dict(packet.get("delete_readiness"))
    if readiness and readiness.get("delete_or_archive_performed") is True:
        errors.append("delete_readiness_must_not_perform_delete_or_archive")
    recommendation = as_dict(packet.get("recommendation_outcome_ledger"))
    if recommendation and recommendation.get("later_outcome_graded_rows") == 0:
        warnings.append("recommendation_later_outcome_graded_rows_zero")
    wiki = as_dict(packet.get("wiki_synthesis"))
    if wiki:
        if wiki.get("validation_status") == "blocked":
            errors.append("wiki_synthesis_validation_blocked")
        elif wiki.get("validation_status") == "warning":
            warnings.append("wiki_synthesis_validation_warning")
        if wiki.get("recommendation_leak_guard_pass") is not True:
            errors.append("wiki_synthesis_recommendation_leak_guard_must_pass")
        if int(wiki.get("auto_apply_count") or 0):
            errors.append("wiki_synthesis_auto_apply_count_must_be_zero")
    loop_trace = as_dict(packet.get("wf74_wf88_loop_trace"))
    if loop_trace:
        if loop_trace.get("validation_status") == "blocked":
            errors.append("wf74_wf88_loop_trace_validation_blocked")
        elif loop_trace.get("validation_status") == "warning":
            warnings.append("wf74_wf88_loop_trace_validation_warning")
        if int(loop_trace.get("duplicate_pm_job_id_count") or 0):
            errors.append(f"wf74_wf88_loop_trace_duplicate_pm_job_id_count:{loop_trace.get('duplicate_pm_job_id_count')}")
        if int(loop_trace.get("high_priority_unrouted_count") or 0):
            errors.append(f"wf74_wf88_loop_trace_high_priority_unrouted_count:{loop_trace.get('high_priority_unrouted_count')}")
        if int(loop_trace.get("lane_link_missing_count") or 0):
            warnings.append(f"wf74_wf88_loop_trace_lane_link_missing_count:{loop_trace.get('lane_link_missing_count')}")
        if int(loop_trace.get("downstream_stale_after_router_count") or 0):
            warnings.append(f"wf74_wf88_loop_trace_downstream_stale_after_router_count:{loop_trace.get('downstream_stale_after_router_count')}")
    long_work = as_dict(packet.get("long_work_job_status"))
    if long_work:
        if long_work.get("validation_status") == "blocked":
            errors.append("long_work_job_status_validation_blocked")
        elif long_work.get("validation_status") == "warning":
            warnings.append("long_work_job_status_validation_warning")
        if int(long_work.get("blocked_job_count") or 0):
            errors.append(f"long_work_blocked_job_count:{long_work.get('blocked_job_count')}")
        if int(long_work.get("stale_active_job_count") or 0):
            warnings.append(f"long_work_stale_active_job_count:{long_work.get('stale_active_job_count')}")
        if int(long_work.get("resumable_job_count") or 0):
            warnings.append(f"long_work_resumable_job_count:{long_work.get('resumable_job_count')}")
    skill_guard = as_dict(packet.get("skill_workshop_body_guard"))
    if skill_guard:
        if int(skill_guard.get("critical_count") or 0):
            errors.append("skill_workshop_body_guard_critical_count_must_be_zero")
        if int(skill_guard.get("live_error_count") or 0):
            errors.append("skill_workshop_body_guard_live_error_count_must_be_zero")
    finance_query_guard = as_dict(packet.get("finance_query_friction_guard"))
    if finance_query_guard:
        if finance_query_guard.get("validation_status") != "ok":
            errors.append("finance_query_friction_guard_validation_must_be_ok")
    finance_cache = as_dict(packet.get("finance_cache_frontdoor"))
    if finance_cache:
        if finance_cache.get("validation_status") != "ok":
            errors.append("finance_cache_frontdoor_validation_must_be_ok")
        if finance_cache.get("sql_first_truth_production_retained") is not True:
            errors.append("finance_cache_frontdoor_sql_first_truth_must_be_retained")
        if finance_cache.get("cache_first_chat_consumption") is not True:
            errors.append("finance_cache_frontdoor_cache_first_chat_must_be_true")
        if finance_cache.get("source_open_required_for_material_claims") is not True:
            errors.append("finance_cache_frontdoor_source_open_material_claims_must_be_true")
    route_readiness_p3 = as_dict(packet.get("wf78_route_readiness_p3"))
    if route_readiness_p3:
        if route_readiness_p3.get("source_status") != "ok":
            errors.append("wf78_route_readiness_p3_status_must_be_ok")
        if route_readiness_p3.get("validation_status") == "error":
            errors.append("wf78_route_readiness_p3_validation_error")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    wf87 = as_dict(packet.get("wf87_runtime_governor"))
    wf67 = as_dict(packet.get("wf67_paper_guardrail"))
    cleanup = as_dict(packet.get("retired_surface_cleanup"))
    contraction = as_dict(packet.get("route_contraction"))
    finance_query_guard = as_dict(packet.get("finance_query_friction_guard"))
    finance_cache = as_dict(packet.get("finance_cache_frontdoor"))
    route_readiness_p3 = as_dict(packet.get("wf78_route_readiness_p3"))
    long_work = as_dict(packet.get("long_work_job_status"))
    lines = [
        "# WF88 OS 2.0 Control Packet",
        "",
        "## Verdict",
        "",
        "WF88 is the broad learning, cleanup-planning, and action-state layer. WF87 is now a narrower paper-autonomy runtime governor underneath it.",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Canonical action rows: `{summary.get('canonical_action_count')}`",
        f"- Blocked/follow-up rows: `{summary.get('blocked_or_followup_action_count')}`",
        f"- WF87 runtime status: `{summary.get('wf87_runtime_status')}`",
        f"- WF87 Phase C owner-review eligible now: `{summary.get('wf87_phase_c_owner_review_eligible_now')}`",
        f"- WF87 execution allowed: `{summary.get('wf87_execution_allowed')}`",
        f"- WF67 manager status: `{summary.get('wf67_manager_status')}`",
        f"- WF67 candidate/blocked cards: `{summary.get('wf67_candidate_card_count')}/{summary.get('wf67_blocked_candidate_count')}`",
        f"- Route-contraction exact files: `{summary.get('cleanup_route_contraction_exact_file_count')}`",
        f"- Route-contraction validation: `{summary.get('route_contraction_validation_status')}`",
        f"- Contracted/already narrowed files: `{summary.get('route_contraction_contracted_or_narrowed_count')}`",
        f"- Script deletion ready now: `{summary.get('script_deletion_ready_now_count')}`",
        f"- First tmp proposal candidates: `{summary.get('cleanup_first_tmp_microbatch_candidate_count')}`",
        f"- Tmp delete ready after owner approval: `{summary.get('tmp_delete_ready_after_owner_approval_count')}`",
        f"- DB archive ready after owner approval: `{summary.get('db_archive_ready_after_owner_approval_count')}`",
        f"- Source-open blocked rows: `{summary.get('source_open_blocked_count')}`",
        f"- Source-open default runtime blockers: `{summary.get('source_open_default_runtime_blocker_count')}`",
        f"- Active SQL/JSON repair rows: `{summary.get('active_sql_json_tier_repair_count')}`",
        f"- Recommendation tracked rows: `{summary.get('recommendation_tracked_row_count')}`",
        f"- Recommendation later-outcome graded rows: `{summary.get('recommendation_later_outcome_graded_rows')}`",
        f"- Recommendation later-outcome metric scope: `{summary.get('recommendation_later_outcome_metric_scope')}`",
        f"- Recommendation preview/durable/grade-history graded rows: `{summary.get('recommendation_current_preview_later_outcome_graded_rows')}` / `{summary.get('recommendation_durable_later_outcome_graded_rows')}` / `{summary.get('recommendation_grade_history_graded_ledger_event_count')}`",
        f"- Stale inputs: `{summary.get('stale_input_count')}`",
        f"- Scoreable decisions: `{summary.get('scoreable_decision_count')}`",
        f"- Model performance claim allowed now: `{summary.get('model_performance_claim_allowed_now')}`",
        f"- Wiki synthesis status: `{summary.get('wiki_synthesis_status')}`",
        f"- Wiki synthesis validation: `{summary.get('wiki_synthesis_validation_status')}`",
        f"- Wiki pages: `{summary.get('wiki_page_count')}`",
        f"- Wiki self-prompts: `{summary.get('wiki_self_prompt_count')}`",
        f"- Wiki recommendation leak guard pass: `{summary.get('wiki_recommendation_leak_guard_pass')}`",
        f"- Wiki RSI status: `{summary.get('wiki_rsi_status')}`",
        f"- Loop trace status: `{summary.get('loop_trace_status')}`",
        f"- Loop trace rows: `{summary.get('loop_trace_row_count')}`",
        f"- Loop trace PM/lane links: `{summary.get('loop_trace_pm_job_link_count')}` / `{summary.get('loop_trace_lane_link_count')}`",
        f"- Loop trace missing lane links: `{summary.get('loop_trace_lane_link_missing_count')}`",
        f"- Loop trace stale consumers: `{summary.get('loop_trace_downstream_stale_after_router_count')}`",
        f"- Long-work jobs: `{summary.get('long_work_job_count')}` / active `{summary.get('long_work_active_job_count')}` / resumable `{summary.get('long_work_resumable_job_count')}` / blocked `{summary.get('long_work_blocked_job_count')}`",
        f"- Skill Workshop body guard: `{summary.get('skill_workshop_body_guard_status')}` / critical `{summary.get('skill_workshop_body_guard_critical_count')}` / live errors `{summary.get('skill_workshop_body_guard_live_error_count')}`",
        f"- Finance query guard validation: `{summary.get('finance_query_guard_validation_status')}`",
        f"- Finance query guard live/member Tier B: `{summary.get('finance_query_guard_live_tier_b_count')}/{summary.get('finance_query_guard_membership_tier_b_count')}`",
        f"- Finance query guard latest-day single sweep: `{summary.get('finance_query_guard_latest_source_day_single_sweep')}`",
        f"- Finance cache front door: `{summary.get('finance_cache_frontdoor_validation_status')}` / tickers `{summary.get('finance_cache_frontdoor_ticker_count')}` / safe review `{summary.get('finance_cache_frontdoor_safe_cached_review_answer_count')}` / safe material `{summary.get('finance_cache_frontdoor_safe_material_claim_from_cache_count')}`",
        f"- Finance cache route readiness: timing `{summary.get('finance_cache_frontdoor_timing_state_counts')}` / trade `{summary.get('finance_cache_frontdoor_trade_readiness_state_counts')}` / authority `{summary.get('finance_cache_frontdoor_authority_state_counts')}`",
        f"- WF78 P3 market/ranking queue: `{route_readiness_p3.get('validation_status')}` / window `{route_readiness_p3.get('market_window_state')}` / refresh-required `{route_readiness_p3.get('market_window_refresh_required_count')}` / top review `{route_readiness_p3.get('top_review_queue_tickers')}`",
        "",
        "## Unified Routing",
        "",
        "- WF85 -> WF87: review-only candidates become runtime eligibility proof.",
        "- WF87 -> WF88: runtime blockers and outcomes feed learning/control.",
        "- WF88 -> queue: one canonical action-state row per real next move.",
        "- WF88 -> wiki: durable source-linked synthesis pages for new sessions.",
        "- Long-work -> WF88: resumable local jobs publish checkpoint/status rows so sessions resume bounded slices instead of waiting on one foreground tool call.",
        "",
        "## WF87 Runtime",
        "",
        f"- Runtime status: `{wf87.get('runtime_status')}`",
        f"- Assisted filled round trips: `{wf87.get('assisted_filled_round_trips_all_time')}/{wf87.get('required_assisted_filled_round_trips_for_phase_c_proposal')}`",
        f"- Phase C owner-review eligible: `{wf87.get('phase_c_owner_review_eligible_now')}`",
        "",
        "## WF67 Guardrail",
        "",
        f"- Manager status: `{wf67.get('source_status')}`",
        f"- Validation: `{wf67.get('validation_status')}`",
        f"- Candidate cards: `{wf67.get('candidate_card_count')}`",
        f"- Blocked candidates: `{wf67.get('blocked_candidate_count')}`",
        f"- Ready tickers: `{wf67.get('ready_tickers')}`",
        "",
        "## Cleanup",
        "",
        f"- Tmp preview eligible: `{cleanup.get('tmp_cleanup_preview_eligible_count')}`",
        f"- First tmp proposal batch: `{cleanup.get('first_tmp_microbatch_candidate_count')}`",
        f"- Route-contraction candidates: `{cleanup.get('script_route_contraction_candidate_count')}`",
        f"- Route-contraction dry-run status: `{contraction.get('source_status')}`",
        "- Delete/archive/apply allowed now: `False`",
        "",
        "## Finance Query Guard",
        "",
        f"- Validation: `{finance_query_guard.get('validation_status')}`",
        f"- Live routing Tier B: `{finance_query_guard.get('live_routing_tier_b_count')}`",
        f"- Membership-scope Tier B: `{finance_query_guard.get('membership_scope_tier_b_count')}`",
        f"- Valid JSONL events: `{finance_query_guard.get('jsonl_valid_event_count')}`",
        f"- Latest source-day single sweep: `{finance_query_guard.get('latest_source_day_single_sweep')}`",
        f"- Band-completeness numeric collision risk: `{finance_query_guard.get('tier_a_b_band_numeric_collision_risk')}`",
        "",
        "## Finance Cache Front Door",
        "",
        f"- Validation: `{finance_cache.get('validation_status')}`",
        f"- Tickers: `{finance_cache.get('ticker_count')}`",
        f"- Safe cached review answers: `{finance_cache.get('safe_cached_review_answer_count')}`",
        f"- Safe material-claim cache rows: `{finance_cache.get('safe_material_claim_from_cache_count')}`",
        f"- Material source-open required: `{finance_cache.get('material_claim_source_open_required_count')}`",
        f"- SQL-first truth retained: `{finance_cache.get('sql_first_truth_production_retained')}`",
        f"- Cache-first chat consumption: `{finance_cache.get('cache_first_chat_consumption')}`",
        f"- Source-open required for material claims: `{finance_cache.get('source_open_required_for_material_claims')}`",
        "",
        "## Long Work Runtime",
        "",
        f"- Status: `{long_work.get('source_status')}`",
        f"- Validation: `{long_work.get('validation_status')}`",
        f"- Jobs: `{long_work.get('job_count')}`",
        f"- Active/resumable/blocked/stale: `{long_work.get('active_job_count')}` / `{long_work.get('resumable_job_count')}` / `{long_work.get('blocked_job_count')}` / `{long_work.get('stale_active_job_count')}`",
        f"- Resumable job IDs: `{long_work.get('resumable_job_ids')}`",
        f"- Next safe action: {long_work.get('next_safe_action')}",
        "",
        "## Canonical Action State",
        "",
    ]
    for row in as_list(packet.get("canonical_action_state")):
        row_dict = as_dict(row)
        lines.append(f"- `{row_dict.get('id')}`: `{row_dict.get('state')}` - {row_dict.get('summary')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- No delete/archive/apply, cron mutation, config/runtime/auth mutation, external/customer output, paper/live execution, or owner approval inference.",
        "- This packet routes work and reduces duplicate surfaces; it does not become canon or execution authority.",
    ])
    return "\n".join(lines) + "\n"


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
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
