from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_os2_control_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_os2_control_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.WF87_GOVERNOR = module.TMP / "wf87-paper-autonomy-runtime-governor.json"
    module.WF88_CLEANUP_PLAN = module.TMP / "wf88-retired-surface-cleanup-plan.json"
    module.WF88_ROUTE_CONTRACTION = module.TMP / "wf88-route-contraction-packet.json"
    module.WF88_SOURCE_OPEN_CLASSIFIER = module.TMP / "wf88-source-open-residue-classifier.json"
    module.WF88_DELETE_READINESS = module.TMP / "wf88-delete-readiness-packet.json"
    module.RECOMMENDATION_LEDGER = module.TMP / "recommendation-outcome-ledger-current.json"
    module.WF55_LEDGER = module.TMP / "wf55-autonomy-outcome-ledger.json"
    module.FINANCE_DIGEST = module.TMP / "finance-decision-performance-digest.json"
    module.WF85_PACKET = module.TMP / "wf85-decision-os-review-packet.json"
    module.WF74_DOCKET = module.TMP / "wf74-decision-docket.json"
    module.WF74_WF88_LOOP_TRACE = module.TMP / "wf74-wf88-loop-trace.json"
    module.LONG_WORK_JOB_STATUS = module.TMP / "long-work-job-status-packet.json"
    module.IMPROVEMENT_LEDGER = module.TMP / "improvement-ledger-current.json"
    module.PM_CONTROL = module.TMP / "pm-control-packet.json"
    module.CRON_CONTROL = module.TMP / "cron-control-packet.json"
    module.OTEL_CONTROL = module.TMP / "otel-ops-control.json"
    module.WF88_WIKI_SYNTHESIS = module.TMP / "wf88-wiki-synthesis-packet.json"
    module.SKILL_WORKSHOP_BODY_GUARD = module.TMP / "skill-workshop-body-guard.json"
    module.WF88_FINANCE_QUERY_FRICTION_GUARD = module.TMP / "wf88-finance-query-friction-guard.json"
    module.FINANCE_CACHE_FRONTDOOR = module.TMP / "finance-cache-frontdoor.json"
    module.WF78_ROUTE_READINESS_P3 = module.TMP / "wf78-route-readiness-p3-market-ranking.json"
    module.OUT = module.TMP / "wf88-os2-control-packet.json"
    module.MD_OUT = module.TMP / "wf88-os2-control-packet.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    write_json(module.WF87_GOVERNOR, {
        "status": "runtime_fail_closed_maturity_improved",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "runtime_status": "blocked",
            "shadow_threshold_met": True,
            "reconciliation_maturity_met": True,
            "shadow_scoreable_decision_count": 22,
            "assisted_filled_round_trips_all_time": 0,
            "required_assisted_filled_round_trips_for_phase_c_proposal": 5,
            "phase_c_owner_review_eligible_now": False,
            "phase_c_autonomous_paper_buy_ready": False,
            "execution_allowed": False,
            "next_safe_action": "refresh runtime proof",
        },
    })
    write_json(module.WF88_CLEANUP_PLAN, {
        "status": "proposal_ready_no_apply_authority",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "delete_allowed_now_count": 0,
            "archive_allowed_now_count": 0,
            "tmp_cleanup_preview_eligible_count": 3083,
            "first_tmp_microbatch_candidate_count": 9,
            "script_route_contraction_candidate_count": 12,
            "script_route_contraction_exact_file_count": 10,
            "db_archive_candidate_count": 1,
            "cron_packet_status": "packet_needed_no_cron_mutation",
            "next_safe_action": "review plan",
        },
    })
    write_json(module.WF88_ROUTE_CONTRACTION, {
        "status": "route_contraction_dry_run_ready_no_delete_authority",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "exact_route_contraction_file_count": 10,
            "contracted_or_already_narrowed_count": 10,
            "needs_route_contraction_count": 0,
            "script_deletion_ready_now_count": 0,
            "delete_allowed_now_count": 0,
            "archive_allowed_now_count": 0,
            "next_safe_action": "prepare owner packets only after approval",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.WF88_SOURCE_OPEN_CLASSIFIER, {
        "status": "classified_no_default_runtime_drag",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "source_open_blocked_count": 42,
            "default_runtime_blocker_count": 0,
            "implementation_blocker_count": 0,
            "active_sql_json_tier_repair_count": 19,
            "below_stop_or_invalidation_review_only_count": 17,
            "monitor_only_context_count": 6,
            "legacy_42_deprecated_residue_count": 0,
            "unknown_needs_source_open_count": 0,
            "next_safe_action": "remove default drag",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.WF88_DELETE_READINESS, {
        "status": "owner_ready_microbatches_no_apply",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "tmp_delete_candidate_count": 9,
            "tmp_delete_ready_after_owner_approval_count": 9,
            "tmp_delete_bytes": 82384,
            "db_archive_candidate_count": 1,
            "db_archive_ready_after_owner_approval_count": 1,
            "script_deletion_ready_now_count": 0,
            "cron_mutation_ready_now_count": 0,
            "delete_or_archive_performed": False,
            "next_safe_action": "ask exact approval",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.RECOMMENDATION_LEDGER, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "durable_v2_ledger": {
            "later_outcome_graded_rows": 0,
            "grade_history": {
                "assigned_grade_event_count": 0,
                "graded_ledger_event_count": 0,
                "path": "data/state-history/recommendation-outcome-grades.jsonl",
            },
        },
        "recommendation_tracking_summary": {
            "tracking_row_count": 15,
            "pending_owner_decision_rows": 15,
            "pending_paper_card_rows": 5,
            "tracked_tickers": ["NVDA"],
            "predictive_or_model_claims_allowed": False,
            "paper_or_live_execution_allowed": False,
        },
        "tracked_rows": [{"event_subtype": "owner_decision_pending", "payload": {"decision_status": "pending_owner_review"}}],
        "validation": {"status": "ok"},
    })
    write_json(module.WF55_LEDGER, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "decision_event_count": 25,
            "measurement_grade_count": 12,
            "clean_shadow_decision_count": 21,
            "shadow_threshold_met": True,
            "scoreable_decision_count": 22,
            "pending_regular_session_followup_count": 0,
            "claim_state": "measure_not_claim",
        },
    })
    write_json(module.FINANCE_DIGEST, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "performance_claim_status": {
            "decision_quality_claim_allowed_now": False,
            "model_performance_claim_allowed_now": False,
        },
    })
    write_json(module.WF85_PACKET, {
        "status": "warning",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "card_count": 300,
            "approval_card_draft_count": 0,
            "approval_gate_review_ready_count": 0,
            "capital_review_ready_count": 0,
            "implementation_blocker_count": 42,
            "source_open_status_counts": {"blocked": 42},
            "trade_grade_data_readiness_status": "warning",
            "next_safe_action": "repair source-open blockers",
        },
    })
    write_json(module.WF74_DOCKET, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "active_action_count": 4,
            "fix_now_count": 1,
            "hard_stop_count": 0,
        },
    })
    write_json(module.WF74_WF88_LOOP_TRACE, {
        "status": "loop_trace_warning_no_apply_authority",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "trace_row_count": 5,
            "missing_destination_count": 0,
            "high_priority_unrouted_count": 0,
            "pm_job_link_count": 3,
            "lane_link_count": 1,
            "lane_link_missing_count": 2,
            "completed_lane_missing_closeout_count": 0,
            "completed_lane_missing_memory_ref_count": 0,
            "duplicate_pm_job_id_count": 0,
            "downstream_stale_after_router_count": 0,
        },
        "source_spine": {
            "otel_event_count": 100,
            "model_learning_row_count": 20,
            "implementation_token_gap_count": 2,
        },
        "validation": {"status": "warning", "errors": [], "warnings": ["lane_link_missing_count:2"]},
    })
    write_json(module.LONG_WORK_JOB_STATUS, {
        "schema": "veritas.long_work_job_status_packet.v1",
        "status": "long_work_jobs_ready",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "job_count": 2,
            "active_job_count": 0,
            "terminal_job_count": 2,
            "resumable_job_count": 0,
            "blocked_job_count": 0,
            "stale_active_job_count": 0,
            "status_counts": {"complete": 2},
            "resumable_job_ids": [],
            "blocked_job_ids": [],
            "stale_active_job_ids": [],
            "next_safe_action": "No resumable long jobs are waiting.",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.IMPROVEMENT_LEDGER, {
        "status": "warning",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "latest_open_count": 21,
            "high_priority_overdue_open_count": 7,
        },
    })
    write_json(module.PM_CONTROL, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "pm_readiness": {
                "readiness_band": "green",
                "blocked_lanes": 0,
            },
        },
    })
    write_json(module.CRON_CONTROL, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "escalation_signal_count": 0,
            "blocked_count": 0,
        },
    })
    write_json(module.OTEL_CONTROL, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "event_count": 100,
        },
    })
    write_json(module.WF88_WIKI_SYNTHESIS, {
        "status": "wiki_synthesis_warning_no_apply_authority",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "wiki_page_count": 12,
            "self_prompt_count": 6,
            "rsi_status": "pilot_ready",
            "followup_required_open_count": 13,
            "recommendation_later_outcome_graded_rows": 0,
            "retrieval_quality_status": "ok",
            "retrieval_quality_validation_status": "ok",
            "retrieval_fixture_count": 42,
            "retrieval_passed_count": 42,
            "retrieval_failed_count": 0,
            "retrieval_class_count": 10,
            "retrieval_average_score": 1.0,
            "retrieval_live_source_timestamp_age_assessment_count": 1,
            "retrieval_label_only_cases_are_live_source_proof": False,
            "retrieval_declared_labels_are_authoritative": False,
            "retrieval_source_timestamp_age_is_live_source_proof": True,
            "frontier_eval_status": "ready_to_collect",
            "frontier_eval_validation_status": "ok",
            "frontier_fixture_count": 100,
            "frontier_result_row_count": 0,
            "frontier_fully_verified_result_count": 0,
            "frontier_model_execution_state": "not_observed",
            "frontier_all_assignment_execution_proven": False,
            "frontier_proof_index_chain_verified": False,
            "frontier_all_comparison_gates_passed": False,
            "frontier_trusted_execution_attestation_verified": False,
            "frontier_trusted_output_artifact_attestation_verified": False,
            "frontier_trusted_grader_attestation_verified": False,
            "frontier_cross_model_ranking_allowed": False,
            "decision_compiler_status": "decision_compiler_warning_review_only",
            "decision_compiler_validation_status": "warning",
            "decision_object_count": 9,
            "decision_conflict_count": 0,
            "decision_blocked_count": 0,
            "decision_compiler_leak_guard_pass": True,
            "rsi_outcome_status": "warning",
            "rsi_outcome_validation_status": "warning",
            "rsi_outcome_mature": False,
            "rsi_outcome_maturity_status": "insufficient_live_outcome_proof",
            "rsi_live_complete_stable_count": 0,
            "rsi_missing_link_debt_item_count": 25,
            "rsi_live_authority_violation_count": 0,
            "rsi_live_trace_unique_correlation_id_count": 5,
            "rsi_live_trace_duplicate_correlation_id_count": 0,
            "rsi_live_trace_missing_correlation_id_count": 0,
            "rsi_live_trace_noncanonical_correlation_id_count": 0,
            "rsi_correlation_integrity_gate_met": True,
            "advanced_pilot_status": "fixture_ready_no_execution_authority",
            "advanced_pilot_validation_status": "ok",
            "advanced_pilot_count": 6,
            "advanced_pilot_executed_count": 0,
            "advanced_pilot_promotion_ready_count": 0,
            "advanced_pilot_external_api_calls_performed": False,
            "advanced_pilot_raw_content_stored": False,
            "advanced_pilot_fixture_contract_safe": True,
        },
        "recommendation_leak_guard": {
            "pass": True,
            "open_unrouted_recommendation_count": 0,
            "auto_apply_count": 0,
        },
        "action_items": [{"id": "refresh-wf88-wiki-synthesis"}],
        "validation": {"status": "warning", "errors": [], "warnings": ["rsi_harness_pilot_ready_not_mature"]},
    })
    write_json(module.SKILL_WORKSHOP_BODY_GUARD, {
        "status": "warning",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "critical_count": 0,
            "live_error_count": 0,
            "live_warning_count": 1,
            "pair_status": None,
        },
        "validation": {"status": "warning", "errors": [], "warnings": ["sqlite_skill_missing_h1"]},
    })
    write_json(module.WF88_FINANCE_QUERY_FRICTION_GUARD, {
        "status": "guard_warning_review_only",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "validation_status": "ok",
            "validation_warning_count": 3,
            "live_routing_tier_a_count": 15,
            "live_routing_tier_b_count": 44,
            "live_routing_tier_c_count": 241,
            "membership_scope_tier_a_count": 15,
            "membership_scope_tier_b_count": 17,
            "membership_scope_tier_c_count": 268,
            "tier_b_delta_live_minus_membership": 27,
            "promotion_candidate_count": 86,
            "promotion_tier_c_attention_count": 48,
            "promotion_c_to_b_evidence_complete_count": 15,
            "promotion_evidence_repair_count": 23,
            "jsonl_valid_event_count": 394,
            "latest_source_day": "2026-06-27",
            "latest_source_day_event_count": 23,
            "latest_source_day_single_sweep": True,
            "tier_a_b_band_numeric_collision_risk": True,
            "recommended_query_mode": "file_based_python_script_or_single_quoted_powershell_here_string",
            "next_safe_action": "Use this guard before WF78/WF88 tier-routing answers; no mutation or execution authority is granted.",
        },
        "validation": {"status": "ok", "errors": [], "warnings": ["tier_b_count_split_live_routing_44_membership_scope_17"]},
    })
    write_json(module.FINANCE_CACHE_FRONTDOOR, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "ticker_count": 300,
            "safe_cached_review_answer_count": 251,
            "safe_material_claim_from_cache_count": 209,
            "material_claim_source_open_required_count": 42,
            "refresh_or_source_open_needed_count": 49,
            "next_safe_action": "Use ticker rows for lightweight chat answers; source-open before material claims.",
        },
        "authority_boundary": {
            "review_only": True,
            "chat_cache_facade_only": True,
            "sql_first_truth_production_retained": True,
            "cache_first_chat_consumption": True,
            "source_open_required_for_material_claims": True,
            "capital_deployment_allowed": False,
            "trade_or_execution_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.WF78_ROUTE_READINESS_P3, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "market_window_state": "closed",
            "market_holiday": False,
            "market_window_refresh_required_count": 0,
            "category_counts": {"monitor": 2},
            "top_review_queue_tickers": ["NVDA"],
            "approval_card_candidate_owner_gated_tickers": [],
            "in_band_review_monitor_tickers": ["NVDA"],
            "next_safe_action": "Use P3 ranking for review-only route triage.",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })


def test_control_packet_unifies_wf87_under_wf88_without_apply_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "warning"
        assert packet["summary"]["wf87_runtime_status"] == "blocked"
        assert packet["summary"]["wf87_execution_allowed"] is False
        assert packet["summary"]["cleanup_route_contraction_exact_file_count"] == 10
        assert packet["summary"]["route_contraction_validation_status"] == "ok"
        assert packet["summary"]["script_deletion_ready_now_count"] == 0
        assert packet["summary"]["source_open_blocked_count"] == 42
        assert packet["summary"]["source_open_default_runtime_blocker_count"] == 0
        assert packet["summary"]["tmp_delete_ready_after_owner_approval_count"] == 9
        assert packet["summary"]["tmp_delete_already_applied_count"] is None
        assert packet["summary"]["recommendation_later_outcome_graded_rows"] == 0
        assert packet["summary"]["recommendation_later_outcome_metric_scope"] == "durable_recommendation_outcome_ledger_max_of_preview_durable_and_grade_history"
        assert packet["summary"]["recommendation_current_preview_later_outcome_graded_rows"] == 0
        assert packet["summary"]["recommendation_durable_later_outcome_graded_rows"] == 0
        assert packet["summary"]["wiki_page_count"] == 12
        assert packet["summary"]["wiki_recommendation_leak_guard_pass"] is True
        assert packet["summary"]["wiki_retrieval_passed_count"] == 42
        assert packet["summary"]["wiki_retrieval_live_source_timestamp_age_assessment_count"] == 1
        assert packet["summary"]["wiki_retrieval_label_only_cases_are_live_source_proof"] is False
        assert packet["summary"]["wiki_frontier_fixture_count"] == 100
        assert packet["summary"]["wiki_frontier_result_row_count"] == 0
        assert packet["summary"]["wiki_frontier_fully_verified_result_count"] == 0
        assert packet["summary"]["wiki_frontier_model_execution_state"] == "not_observed"
        assert packet["summary"]["wiki_frontier_cross_model_ranking_allowed"] is False
        assert packet["summary"]["wiki_frontier_trusted_execution_attestation_verified"] is False
        assert packet["summary"]["wiki_frontier_trusted_output_artifact_attestation_verified"] is False
        assert packet["summary"]["wiki_frontier_trusted_grader_attestation_verified"] is False
        assert packet["summary"]["wiki_decision_object_count"] == 9
        assert packet["summary"]["wiki_decision_compiler_leak_guard_pass"] is True
        assert packet["summary"]["wiki_rsi_live_complete_stable_count"] == 0
        assert packet["summary"]["wiki_rsi_missing_link_debt_item_count"] == 25
        assert packet["summary"]["wiki_rsi_live_trace_unique_correlation_id_count"] == 5
        assert packet["summary"]["wiki_rsi_live_trace_duplicate_correlation_id_count"] == 0
        assert packet["summary"]["wiki_rsi_live_trace_noncanonical_correlation_id_count"] == 0
        assert packet["summary"]["wiki_rsi_correlation_integrity_gate_met"] is True
        assert packet["summary"]["wiki_advanced_pilot_count"] == 6
        assert packet["summary"]["wiki_advanced_pilot_executed_count"] == 0
        assert packet["summary"]["wiki_advanced_pilot_fixture_contract_safe"] is True
        assert packet["summary"]["loop_trace_row_count"] == 5
        assert packet["summary"]["loop_trace_pm_job_link_count"] == 3
        assert packet["summary"]["loop_trace_lane_link_missing_count"] == 2
        assert packet["summary"]["long_work_job_count"] == 2
        assert packet["summary"]["long_work_resumable_job_count"] == 0
        assert packet["summary"]["long_work_blocked_job_count"] == 0
        assert packet["summary"]["skill_workshop_body_guard_critical_count"] == 0
        assert packet["summary"]["skill_workshop_body_guard_live_error_count"] == 0
        assert packet["summary"]["finance_query_guard_validation_status"] == "ok"
        assert packet["summary"]["finance_query_guard_live_tier_b_count"] == 44
        assert packet["summary"]["finance_query_guard_membership_tier_b_count"] == 17
        assert packet["summary"]["finance_query_guard_latest_source_day_single_sweep"] is True
        assert packet["summary"]["finance_cache_frontdoor_validation_status"] == "ok"
        assert packet["summary"]["finance_cache_frontdoor_ticker_count"] == 300
        assert packet["summary"]["finance_cache_frontdoor_safe_cached_review_answer_count"] == 251
        assert packet["summary"]["finance_cache_frontdoor_safe_material_claim_from_cache_count"] == 209
        assert packet["summary"]["finance_cache_frontdoor_sql_first_retained"] is True
        assert packet["summary"]["finance_cache_frontdoor_cache_first_chat"] is True
        assert packet["summary"]["finance_cache_frontdoor_source_open_material_claims"] is True
        assert packet["authority_boundary"]["delete_allowed"] is False
        assert packet["authority_boundary"]["paper_or_live_execution_allowed"] is False
        assert packet["unified_routing_contract"]["wf87_to_wf88"].startswith("WF87 exports runtime eligibility")
        assert packet["unified_routing_contract"]["wf74_wf88_loop_trace"].startswith("The loop trace stitches")
        assert packet["unified_routing_contract"]["wf88_to_wiki"].startswith("WF88 wiki synthesis")
        assert any("skill_workshop_body_guard.py" in item for item in packet["unified_routing_contract"]["do_not_duplicate"])


def test_control_packet_has_canonical_action_rows() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        ids = {row["id"] for row in packet["canonical_action_state"]}
        assert "wf87-runtime-governor-fail-closed" in ids
        assert "wf88-cleanup-route-contraction" in ids
        assert "wf88-source-open-residue-classification" in ids
        assert "wf88-delete-readiness-owner-packets" in ids
        assert "recommendation-outcome-backlog" in ids
        assert "wf88-learning-loop-measurement" in ids
        assert "wf88-wiki-synthesis-layer" in ids
        assert "wf88-frontier-capability-eval-spine" in ids
        assert "wf88-decision-compiler-and-retrieval" in ids
        assert "wf88-rsi-later-outcome-scorecard" in ids
        assert "wf88-advanced-capability-pilot-contracts" in ids
        assert "wf74-wf88-loop-trace-spine" in ids
        assert "runtime-long-work-job-status-spine" in ids
        assert "wf88-skill-workshop-body-guard-enforcement" in ids
        assert "wf88-finance-query-friction-guard" in ids
        assert "finance-cache-frontdoor-chat-route" in ids
        assert "wf67-paper-guardrail-blocked-cards" in ids
        assert "wf85-source-open-repair-queue" in ids
        assert "improvement-ledger-open-followups" in ids
        assert packet["summary"]["canonical_action_count"] == 19
        frontier_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf88-frontier-capability-eval-spine")
        assert frontier_row["state"] == "followup_required"
        compiler_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf88-decision-compiler-and-retrieval")
        assert compiler_row["state"] == "warning_review_only"
        rsi_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf88-rsi-later-outcome-scorecard")
        assert rsi_row["state"] == "followup_required"
        pilot_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf88-advanced-capability-pilot-contracts")
        assert pilot_row["state"] == "fixture_ready_execution_gated"
        loop_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf74-wf88-loop-trace-spine")
        assert loop_row["state"] == "warning"
        assert loop_row["authority"] == "review_only_trace_no_apply_or_execution"
        long_work_row = next(row for row in packet["canonical_action_state"] if row["id"] == "runtime-long-work-job-status-spine")
        assert long_work_row["state"] == "clean"
        assert long_work_row["authority"] == "review_only_runtime_status_resume_no_cron_or_config_mutation"
        guard_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf88-finance-query-friction-guard")
        assert guard_row["authority"] == "review_only_query_guard_no_sql_or_routing_mutation"
        cache_row = next(row for row in packet["canonical_action_state"] if row["id"] == "finance-cache-frontdoor-chat-route")
        assert cache_row["authority"] == "review_only_chat_facade_sql_first_truth_source_open_material_claims"
        assert cache_row["state"] == "cache_first_chat_ready"
        assert packet["summary"]["model_performance_claim_allowed_now"] is False
        wf85_row = next(row for row in packet["canonical_action_state"] if row["id"] == "wf85-source-open-repair-queue")
        assert "WF85 source-open blocked rows: 42" in wf85_row["summary"]
        assert "default runtime blockers: 0" in wf85_row["summary"]


def test_control_packet_surfaces_stale_required_inputs_as_warnings() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        write_json(module.RECOMMENDATION_LEDGER, {
            "status": "ok",
            "generated_at_utc": "2026-01-01T00:00:00Z",
            "recommendation_tracking_summary": {"tracking_row_count": 1, "pending_owner_decision_rows": 1},
            "tracked_rows": [{"event_subtype": "owner_decision_pending"}],
            "validation": {"status": "ok"},
        })
        packet = module.build_packet()

        assert packet["status"] == "control_packet_warning_no_apply_authority"
        assert packet["validation"]["status"] == "warning"
        assert packet["summary"]["stale_input_count"] >= 1
        assert "recommendation_outcome_ledger_current" in packet["summary"]["stale_inputs"]
        assert any("stale_input:recommendation_outcome_ledger_current" in warning for warning in packet["validation"]["warnings"])


def test_control_packet_surfaces_already_applied_tmp_microbatch() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.WF88_DELETE_READINESS.read_text(encoding="utf-8"))
        payload["summary"]["tmp_delete_ready_after_owner_approval_count"] = 0
        payload["summary"]["tmp_delete_already_applied_count"] = 9
        payload["summary"]["next_safe_action"] = "The approved tmp microbatch has already been applied."
        write_json(module.WF88_DELETE_READINESS, payload)

        packet = module.build_packet()

        assert packet["summary"]["tmp_delete_ready_after_owner_approval_count"] == 0
        assert packet["summary"]["tmp_delete_already_applied_count"] == 9
        row = next(item for item in packet["canonical_action_state"] if item["id"] == "wf88-delete-readiness-owner-packets")
        assert row["state"] == "approved_tmp_microbatch_applied"
        assert "already applied: 9" in row["summary"]


def test_control_packet_counts_grade_history_from_recommendation_ledger() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.RECOMMENDATION_LEDGER.read_text(encoding="utf-8"))
        payload["durable_v2_ledger"]["later_outcome_graded_rows"] = 3
        payload["durable_v2_ledger"]["grade_history"]["assigned_grade_event_count"] = 4
        payload["durable_v2_ledger"]["grade_history"]["graded_ledger_event_count"] = 3
        write_json(module.RECOMMENDATION_LEDGER, payload)

        packet = module.build_packet()

        assert packet["summary"]["recommendation_later_outcome_graded_rows"] == 3
        assert packet["summary"]["recommendation_durable_later_outcome_graded_rows"] == 3
        assert packet["summary"]["recommendation_grade_history_graded_ledger_event_count"] == 3
        assert "recommendation_later_outcome_graded_rows_zero" not in packet["validation"]["warnings"]


def test_component_rows_fail_closed_on_blocked_or_unattested_wiki_inputs() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        wiki = json.loads(module.WF88_WIKI_SYNTHESIS.read_text(encoding="utf-8"))
        summary = wiki["summary"]
        summary["retrieval_quality_validation_status"] = "blocked"
        summary["frontier_eval_status"] = "warning_upstream"
        summary["frontier_result_row_count"] = 300
        summary["frontier_all_assignment_execution_proven"] = True
        summary["frontier_proof_index_chain_verified"] = True
        summary["frontier_all_comparison_gates_passed"] = True
        summary["frontier_cross_model_ranking_allowed"] = True
        summary["frontier_trusted_execution_attestation_verified"] = True
        summary["frontier_trusted_output_artifact_attestation_verified"] = True
        summary["frontier_trusted_grader_attestation_verified"] = True
        summary["decision_compiler_validation_status"] = "blocked"
        summary["rsi_outcome_status"] = "warning_upstream"
        summary["rsi_outcome_validation_status"] = "ok"
        summary["rsi_outcome_mature"] = True
        summary["rsi_live_complete_stable_count"] = 30
        summary["rsi_missing_link_debt_item_count"] = 0
        summary["advanced_pilot_status"] = "execution_evidence_ready_review_only"
        summary["advanced_pilot_executed_count"] = 6
        summary["advanced_pilot_external_api_calls_performed"] = True
        summary["advanced_pilot_fixture_contract_safe"] = False
        write_json(module.WF88_WIKI_SYNTHESIS, wiki)

        packet = module.build_packet()
        states = {row["id"]: row["state"] for row in packet["canonical_action_state"]}
        assert states["wf88-frontier-capability-eval-spine"] == "followup_required"
        assert states["wf88-decision-compiler-and-retrieval"] == "blocked"
        assert states["wf88-rsi-later-outcome-scorecard"] == "followup_required"
        assert states["wf88-advanced-capability-pilot-contracts"] == "blocked"
        assert states["wf88-frontier-capability-eval-spine"] != "review_ready"


if __name__ == "__main__":
    test_control_packet_unifies_wf87_under_wf88_without_apply_authority()
    test_control_packet_has_canonical_action_rows()
    test_control_packet_surfaces_stale_required_inputs_as_warnings()
    test_control_packet_surfaces_already_applied_tmp_microbatch()
    test_control_packet_counts_grade_history_from_recommendation_ledger()
    test_component_rows_fail_closed_on_blocked_or_unattested_wiki_inputs()
    print("wf88 os2 control packet tests passed")
