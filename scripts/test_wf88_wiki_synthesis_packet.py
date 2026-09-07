from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_wiki_synthesis_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_wiki_synthesis_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module, *, auto_apply_count: int = 0, unrouted_count: int = 0) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.WIKI = root / "wiki"
    module.OUT = module.TMP / "wf88-wiki-synthesis-packet.json"
    module.MD_OUT = module.TMP / "wf88-wiki-synthesis-packet.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    generated = module.utc_now()
    payloads = {
        "wf88_os2_control": {
            "status": "control_packet_ready_no_apply_authority",
            "generated_at_utc": generated,
            "summary": {
                "canonical_action_count": 8,
                "blocked_or_followup_action_count": 3,
                "recommendation_tracked_row_count": 9,
                "recommendation_later_outcome_graded_rows": 0,
                "recommendation_later_outcome_metric_scope": "durable_recommendation_outcome_ledger_max_of_preview_durable_and_grade_history",
                "recommendation_current_preview_later_outcome_graded_rows": 0,
                "recommendation_durable_later_outcome_graded_rows": 0,
                "recommendation_grade_history_graded_ledger_event_count": 0,
                "scoreable_decision_count": 22,
                "model_performance_claim_allowed_now": False,
            },
            "validation": {"status": "ok"},
        },
        "otel_ops_control": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"event_count": 153},
        },
        "otel_ops_window_summary": {
            "status": "ok",
            "generated_at_utc": generated,
            "validation": {"status": "ok"},
        },
        "model_learning_metadata_ledger": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"row_count": 994},
        },
        "wf74_improvement_opportunity_queue": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"opportunity_count": 3},
        },
        "wf74_reflection_to_proposal_autopilot": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"proposal_count": 3},
        },
        "wf74_auto_patch_proposer": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "plan_count": 3,
                "patch_plan_count": 1,
                "skill_workshop_request_count": 0,
                "owner_gated_plan_count": 3,
                "auto_apply_candidate_count": 0,
                "auto_apply_count": auto_apply_count,
            },
        },
        "wf74_autonomy_work_router": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "open_unrouted_recommendation_count": unrouted_count,
                "routed_to_pm_recommendation_count": 3,
                "recommendation_to_route_conversion_rate": 1.0,
                "route_to_pm_job_conversion_rate": 1.0,
            },
        },
        "wf74_wf88_loop_trace": {
            "status": "loop_trace_warning_no_apply_authority",
            "generated_at_utc": generated,
            "summary": {
                "trace_row_count": 3,
                "missing_destination_count": 0,
                "high_priority_unrouted_count": 0,
                "pm_job_link_count": 2,
                "lane_link_count": 1,
                "lane_link_missing_count": 1,
                "completed_lane_missing_closeout_count": 0,
                "completed_lane_missing_memory_ref_count": 0,
                "duplicate_pm_job_id_count": 0,
                "downstream_stale_after_router_count": 0,
            },
            "source_spine": {
                "otel_event_count": 153,
                "model_learning_row_count": 994,
            },
            "validation": {"status": "warning", "errors": [], "warnings": ["lane_link_missing_count:1"]},
        },
        "long_work_job_status": {
            "schema": "veritas.long_work_job_status_packet.v1",
            "status": "long_work_jobs_ready",
            "generated_at_utc": generated,
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
        },
        "wf74_decision_docket": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "row_count": 24,
                "active_action_count": 1,
                "fix_now_count": 0,
                "owner_decision_count": 1,
                "hard_stop_count": 0,
                "next_safe_action": "Prepare owner decision card.",
            },
        },
        "wf74_learning_loop_eval_harness": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "case_count": 6,
                "passed_count": 6,
                "failed_count": 0,
                "rsi_status": "proof_worker_ready",
                "legacy_rsi_first_hop_truth": False,
            },
            "rsi_maturity": {
                "status": "proof_worker_ready",
                "maturity_stage": "proof_worker_ready",
                "readiness_ladder": [
                    {"stage": "pilot_ready"},
                    {"stage": "proof_worker_ready"},
                    {"stage": "cron_candidate"},
                    {"stage": "cron_enabled"},
                ],
                "current_allowed_automation": {
                    "main_session_supervised_proof_worker": True,
                    "cron_proof_worker": False,
                    "direct_apply": False,
                    "code_patch_without_owner_review": False,
                    "skill_apply_without_owner_approval": False,
                    "sql_import_or_promotion": False,
                    "finance_canon_or_portfolio_mutation": False,
                },
                "legacy_artifact_required_for_first_hop_truth": False,
                "rubric_dimensions": [
                    {"dimension": "truthfulness"},
                    {"dimension": "freshness_discipline"},
                    {"dimension": "boundary_safety"},
                    {"dimension": "continuity_routing"},
                    {"dimension": "actionability"},
                    {"dimension": "regression_proof"},
                    {"dimension": "surface_compression"},
                ],
            },
            "eval_surface_contract": {
                "single_primary_required": True,
                "primary_surface": {
                    "artifact": "tmp/wf74-learning-loop-eval-harness.json",
                    "surface_class": "primary",
                    "first_hop_truth": True,
                },
                "secondary_surfaces": [
                    {
                        "artifact": "tmp/wf74-outcome-eval-suite-v2.json",
                        "surface_class": "secondary",
                        "first_hop_truth": False,
                    }
                ],
                "deprecated_surfaces": [
                    {
                        "artifact": "tmp/wf74-rsi-evaluation-harness.json",
                        "surface_class": "deprecated_compatibility",
                        "first_hop_truth": False,
                    }
                ],
            },
        },
        "wf74_outcome_eval_suite_v2": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"categories": 17, "fixtures": 34, "failed_classifications": 0},
        },
        "model_quality_scorecard": {
            "status": "scaffold_active",
            "generated_at_utc": generated,
            "summary": {"findings": []},
        },
        "veritas_harness_scorecard": {
            "status": "ok",
            "generated_at_utc": generated,
        },
        "retrieval_quality_scorecard": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "fixtures": 42,
                "passed": 42,
                "failed": 0,
                "average_score": 1.0,
                "classes": [f"class_{index}" for index in range(10)],
                "conflict_fixture_count": 13,
                "freshness_proof": {
                    "assessment_mode_counts": {
                        "fixture_timestamp_age": 9,
                        "source_timestamp_age": 1,
                        "synthetic_ordering_semantics": 24,
                    },
                    "live_source_timestamp_age_assessment_count": 1,
                    "live_source_status_counts": {"fresh": 1},
                },
            },
            "measurement_contract": {
                "freshness": {
                    "label_only_cases_are_live_source_proof": False,
                    "declared_labels_are_authoritative": False,
                    "source_timestamp_age_is_live_source_proof": True,
                },
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "frontier_capability_eval_spine": {
            "status": "ready_to_collect",
            "generated_at_utc": generated,
            "fixture_integrity": {
                "case_count": 100,
                "digest_match": True,
                "privacy": {"raw_capture": False},
            },
            "study_design": {
                "assignment_count": 300,
                "model_execution_performed": False,
            },
            "result_collection": {
                "row_count": 0,
                "proof_verification": {
                    "fully_verified_result_count": 0,
                    "model_execution_state": "not_observed",
                    "all_assignment_execution_proven": False,
                    "proof_index_chain_verified": False,
                },
            },
            "comparison_readiness": {
                "all_comparison_gates_passed": False,
                "trusted_execution_attestation_verified": False,
                "trusted_output_artifact_attestation_verified": False,
                "trusted_grader_attestation_verified": False,
                "cross_model_ranking_allowed": False,
                "promotion_action_allowed": False,
            },
            "baseline_attribution_context": {
                "recent_model_attribution": {"coverage": 0.9211},
                "usage_attribution": {"provider_run_join_ready": False},
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "wf88_decision_compiler": {
            "status": "decision_objects_warning_review_only",
            "generated_at_utc": generated,
            "runtime_dependency_contract": {
                "wiki_or_os2_inputs_forbidden": [
                    "tmp/wf88-os2-control-packet.json",
                    "tmp/wf88-wiki-synthesis-packet.json",
                ],
            },
            "summary": {
                "decision_object_count": 9,
                "state_counts": {"monitor_only": 7, "repair_ready_review_only": 2},
                "conflict_count": 0,
                "uncertain_count": 3,
                "owner_review_required_count": 0,
                "blocked_count": 0,
            },
            "leak_guard": {"pass": True},
            "validation": {"status": "warning", "errors": [], "warnings": ["source_validation_warning:wf74_wf88_loop_trace"]},
        },
        "rsi_outcome_scorecard": {
            "status": "warning",
            "generated_at_utc": generated,
            "summary": {
                "maturity_status": "warning_insufficient_real_outcome_evidence",
                "live_trace_row_count": 5,
                "live_trace_raw_row_count": 5,
                "live_trace_unique_correlation_id_count": 5,
                "live_trace_duplicate_correlation_id_count": 0,
                "live_trace_missing_correlation_id_count": 0,
                "live_trace_noncanonical_correlation_id_count": 0,
                "live_complete_stable_count": 0,
                "live_closed_unverified_durability_count": 3,
                "missing_link_debt_item_count": 25,
                "live_authority_violation_count": 0,
            },
            "maturity_gate": {"mature": False, "correlation_integrity_gate_met": True},
            "validation": {"status": "warning", "errors": [], "warnings": ["live_rsi_outcome_maturity_not_met"]},
        },
        "advanced_capability_pilot_packet": {
            "status": "fixture_ready_no_execution_authority",
            "generated_at_utc": generated,
            "summary": {
                "pilot_count": 6,
                "executed_pilot_count": 0,
                "promotion_ready_count": 0,
                "external_api_calls_performed": False,
                "raw_content_stored": False,
            },
            "authority_boundary": {
                "raw_prompt_capture": False,
                "raw_response_capture": False,
                "runtime_or_config_mutation": False,
                "model_route_mutation": False,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
        "route_efficiency_scorecard": {
            "status": "ok",
            "generated_at_utc": generated,
        },
        "token_usage_ledger": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "token_event_count": 10,
                "total_tokens": 1000,
                "api_equivalent_cost_usd": 1.25,
                "api_equivalent_estimate_status": "complete",
                "api_equivalent_cost_rows": 10,
                "api_equivalent_cost_event_coverage_percent": 100.0,
                "estimated_cost_total": 1.25,
                "estimated_chatgpt_credits": 42.5,
                "chatgpt_credit_estimate_status": "complete",
                "estimated_chatgpt_credit_rows": 10,
                "chatgpt_credit_event_coverage_percent": 100.0,
                "actual_billed_cost_usd": None,
                "cron_token_event_count": 8,
                "implementation_token_event_count": 2,
                "implementation_token_gap_count": 0,
            },
            "billing_semantics": {
                "billing_mode": "oauth_subscription",
                "api_equivalent_is_not_invoice": True,
                "credit_estimate_is_not_observed_debit": True,
            },
            "oauth_capacity_control": {
                "state": "normal",
                "remaining_percent": 62.0,
                "days_to_reset": 6.25,
                "automatic_action_allowed": False,
            },
            "usage_pace": {
                "rolling_5h": {"total_tokens": 100},
                "rolling_7d_observed": {"total_tokens": 1000},
                "usage_timestamp_coverage_percent": 80.0,
                "provider_quota_inferred_from_tokens": False,
            },
            "validation": {"status": "ok"},
        },
        "token_budget_status": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"api_equivalent_cost_usd": 1.25},
            "validation": {"status": "ok"},
        },
        "token_efficiency_scorecard": {
            "status": "warning",
            "generated_at_utc": generated,
            "summary": {
                "api_call_reduction_candidate_count": 1,
                "prompt_compression_candidate_count": 1,
                "failure_cost_candidate_count": 0,
                "top_candidate": "Example",
            },
            "validation": {"status": "warning"},
        },
        "implementation_token_attribution_bridge": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {
                "implementation_token_event_count": 2,
                "implementation_token_gap_count": 0,
                "provider_run_join_ready": True,
            },
            "validation": {"status": "ok"},
        },
        "pm_control_packet": {
            "status": "ok",
            "generated_at_utc": generated,
        },
        "recommendation_outcome_ledger": {
            "status": "ok",
            "generated_at_utc": generated,
            "summary": {"preview_row_count": 23},
        },
        "improvement_ledger": {
            "status": "warning",
            "generated_at_utc": generated,
            "summary": {
                "latest_open_count": 21,
                "followup_required_open_count": 13,
                "pending_skill_proposal_count": 0,
                "high_priority_overdue_open_count": 7,
            },
        },
        "actionable_improvement_queue": {
            "status": "actionable_queue_warning_no_apply_authority",
            "generated_at_utc": generated,
            "summary": {
                "open_input_count": 21,
                "action_item_count": 21,
                "orphan_count": 0,
                "missing_contract_count": 0,
                "owner_decision_count": 1,
                "hard_stop_count": 0,
                "monitor_only_count": 4,
                "top_action_title": "Route blocked cron signals into a migration-ready repair plan",
                "top_action_destination": "wf88_followup_debt_triage",
                "top_next_action": "Resolve current cron escalation.",
            },
            "validation": {"status": "warning", "errors": [], "warnings": ["monitor_review_visible:4"]},
        },
        "no_orphan_validator": {
            "status": "no_orphan_validation_warning",
            "generated_at_utc": generated,
            "summary": {
                "validation_passed": True,
                "orphan_count": 0,
                "high_priority_orphan_count": 0,
                "overdue_orphan_count": 0,
                "missing_contract_count": 0,
                "owner_decision_count": 1,
                "monitor_only_count": 4,
            },
            "validation": {"status": "warning", "errors": [], "warnings": ["monitor_rows_visible:4"]},
        },
    }
    for name, payload in payloads.items():
        write_json(root / module.SOURCES[name]["path"], payload)


def test_wiki_synthesis_routes_recommendations_without_apply_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "warning"
        assert packet["recommendation_leak_guard"]["pass"] is True
        assert packet["summary"]["auto_apply_count"] == 0
        assert packet["summary"]["open_unrouted_recommendation_count"] == 0
        assert packet["summary"]["loop_trace_row_count"] == 3
        assert packet["summary"]["loop_trace_lane_link_missing_count"] == 1
        assert packet["summary"]["long_work_job_count"] == 2
        assert packet["summary"]["long_work_resumable_job_count"] == 0
        assert "maintain-long-work-job-status" in {row["id"] for row in packet["action_items"]}
        assert "maintain-wf74-wf88-loop-trace" in {row["id"] for row in packet["action_items"]}
        assert packet["summary"]["recommendation_later_outcome_metric_scope"] == "durable_recommendation_outcome_ledger_max_of_preview_durable_and_grade_history"
        assert "wf74_rsi_evaluation_harness" not in packet["inputs"]


def test_startup_efficiency_semantics_are_generated_and_gated() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        write_json(root / module.SOURCES["coding_outcome_ledger"]["path"], {
            "status": "ok",
            "generated_at_utc": module.utc_now(),
            "ledger_summary": {
                "route_conformant_count": 2,
                "route_mismatch_count": 1,
                "incident_row_count": 1,
                "invalid_token_integrity_row_count": 1,
                "total_retry_count": 3,
                "comparable_cohorts": {},
                "comparable_cohort_sample_gate": {
                    "required_accepted_count": 999,
                    "eligible_cohort_count": 0,
                    "route_ranking_or_promotion_before_gate": False,
                },
            },
            "validation": {"status": "ok"},
        })
        packet = module.build_packet()
        pages = module.wiki_pages(packet)
        cold = pages["wiki/syntheses/Cold Session Operating Routes.md"]
        token = pages["wiki/scorecards-and-evals/Token Efficiency Map.md"]
        for marker in ["model_free_command", "persistent_isolated_agent", "codex_native_subagent", "actual backend/model/thinking", "What proof is required before dispatching a persistent isolated agent?"]:
            assert marker in cold
        for marker in ["uncached input tokens per Main-accepted job", "retry tax", "owner-directed on-demand evidence review", "no fixed cohort pilot is required", "automatic route ranking and promotion remain disabled", "How should a new session measure token efficiency?"]:
            assert marker in token
        assert packet["startup_efficiency_semantic_contract"]["schema"] == module.STARTUP_EFFICIENCY_SEMANTIC_SCHEMA
        assert packet["execution_efficiency_policy"]["schema"] == module.implementation_router.EFFICIENCY_POLICY_SCHEMA
        assert "coding_outcome_premature_route_ranking_or_promotion" not in packet["validation"]["errors"]
        assert "coding_outcome_comparable_cohort_gate_invalid" not in packet["validation"]["errors"]

        tampered = json.loads(json.dumps(packet))
        tampered["startup_efficiency_semantic_contract"]["required_anchors"]["wiki/syntheses/Cold Session Operating Routes.md"].append("missing-semantic-anchor")
        validation = module.validate_packet(tampered, pages)
        assert any("startup_efficiency_semantic_anchor_missing" in error for error in validation["errors"])
        assert packet["summary"]["rsi_status"] == "proof_worker_ready"
        assert packet["summary"]["wf74_eval_primary_surface"] == "tmp/wf74-learning-loop-eval-harness.json"
        assert packet["summary"]["wf74_legacy_rsi_first_hop_truth"] is False
        assert packet["summary"]["retrieval_live_source_timestamp_age_assessment_count"] == 1
        assert packet["summary"]["retrieval_label_only_cases_are_live_source_proof"] is False
        assert packet["summary"]["retrieval_declared_labels_are_authoritative"] is False
        assert packet["summary"]["rsi_live_trace_unique_correlation_id_count"] == 5
        assert packet["summary"]["rsi_live_trace_duplicate_correlation_id_count"] == 0
        assert packet["summary"]["rsi_live_trace_noncanonical_correlation_id_count"] == 0
        assert packet["summary"]["rsi_correlation_integrity_gate_met"] is True
        assert packet["summary"]["api_equivalent_token_cost_usd"] == 1.25
        assert packet["summary"]["api_equivalent_estimate_status"] == "complete"
        assert packet["summary"]["api_equivalent_cost_rows"] == 10
        assert packet["summary"]["estimated_chatgpt_credits"] == 42.5
        assert packet["summary"]["chatgpt_credit_estimate_status"] == "complete"
        assert packet["summary"]["estimated_chatgpt_credit_rows"] == 10
        assert packet["summary"]["rolling_5h_total_tokens"] == 100
        assert packet["summary"]["actual_billed_cost_usd"] is None
        assert packet["summary"]["token_api_equivalent_is_not_invoice"] is True
        assert packet["summary"]["token_credit_estimate_is_not_observed_debit"] is True
        assert packet["summary"]["oauth_quota_state"] == "normal"
        assert packet["summary"]["oauth_automatic_action_allowed"] is False
        states = {row["id"]: row["state"] for row in packet["action_items"]}
        assert states["grade-recommendation-outcomes"] == "followup_required"
        assert "recommendation_current_preview_later_outcome_graded_rows_zero" in packet["validation"]["warnings"]
        assert states["maintain-wf88-retrieval-regression-corpus"] == "clean"
        assert states["collect-frontier-capability-eval-results"] == "evidence_collection_required"
        assert states["compile-wf88-decision-objects"] == "warning_review_only"
        assert states["close-rsi-outcome-linkage-debt"] == "evidence_linkage_required"
        assert states["run-isolated-advanced-capability-pilots"] == "fixture_ready_execution_gated"
        assert packet["authority_boundary"]["creates_canon"] is False
        assert packet["authority_boundary"]["paper_or_live_execution_allowed"] is False
        assert packet["summary"]["wiki_page_count"] == len(module.EXPECTED_WIKI_PAGES)

        pages = module.wiki_pages(packet)
        assert set(pages) == set(module.EXPECTED_WIKI_PAGES)
        for content in pages.values():
            assert "Status: synthesis only" in content
            assert "Owner workflow: WF88" in content
            assert "Authority boundary:" in content
            assert "Promotion path:" in content
            assert "## Source artifacts" in content


def test_historical_outcome_grades_do_not_satisfy_current_preview_evidence() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        source = root / module.SOURCES["wf88_os2_control"]["path"]
        source_payload = json.loads(source.read_text(encoding="utf-8"))
        source_payload["summary"]["recommendation_later_outcome_graded_rows"] = 89
        source_payload["summary"]["recommendation_durable_later_outcome_graded_rows"] = 89
        source_payload["summary"]["recommendation_grade_history_graded_ledger_event_count"] = 89
        source_payload["summary"]["recommendation_current_preview_later_outcome_graded_rows"] = 0
        source_payload["summary"]["model_performance_claim_allowed_now"] = False
        write_json(source, source_payload)

        packet = module.build_packet()
        states = {row["id"]: row["state"] for row in packet["action_items"]}
        assert packet["summary"]["recommendation_later_outcome_graded_rows"] == 89
        assert packet["summary"]["recommendation_current_preview_later_outcome_graded_rows"] == 0
        assert states["grade-recommendation-outcomes"] == "followup_required"
        assert "recommendation_current_preview_later_outcome_graded_rows_zero" in packet["validation"]["warnings"]


def test_wiki_synthesis_blocks_leaked_recommendations_and_auto_apply() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module, auto_apply_count=1, unrouted_count=2)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert "auto_apply_count_must_be_zero" in packet["validation"]["errors"]
        assert "open_unrouted_recommendations_must_be_zero" in packet["validation"]["errors"]
        assert packet["recommendation_leak_guard"]["pass"] is False


def test_wiki_synthesis_blocks_legacy_rsi_as_required_source() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        module.SOURCES["wf74_rsi_evaluation_harness"] = {
            "path": "tmp/wf74-rsi-evaluation-harness.json",
            "required": True,
            "max_age_hours": 240,
        }
        try:
            packet = module.build_packet()
        finally:
            module.SOURCES.pop("wf74_rsi_evaluation_harness", None)

        assert packet["validation"]["status"] == "blocked"
        assert "legacy_rsi_harness_must_not_be_required_source" in packet["validation"]["errors"]


def test_write_wiki_pages_creates_expected_durable_markdown() -> None:
    module = load_module()
    assert module.retrieval_mirror_path("wiki/index.md").endswith("/Wiki Index.md")
    assert not module.retrieval_mirror_path("wiki/index.md").endswith("/canonical/index.md")
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        packet = module.build_packet()
        first_write = module.write_wiki_pages(packet)

        for rel_path in module.EXPECTED_WIKI_PAGES:
            path = root / rel_path
            assert path.exists()
            text = path.read_text(encoding="utf-8")
            assert "Status: synthesis only" in text
            assert "## Source artifacts" in text
        retrieval_path = root / module.RETRIEVAL_SOURCE_REL
        assert retrieval_path.exists()
        retrieval_text = retrieval_path.read_text(encoding="utf-8")
        assert "# WF88 Wiki Retrieval Index" in retrieval_text
        assert "cron failure triage" in retrieval_text
        retrieval_contract = packet["wiki_retrieval_contract"]
        assert retrieval_contract["page_granular"] is True
        assert retrieval_contract["page_count"] == len(module.EXPECTED_WIKI_PAGES)
        for rel_path in module.EXPECTED_WIKI_PAGES:
            mirror_path = root / module.retrieval_mirror_path(rel_path)
            assert mirror_path.exists()
            mirror_text = mirror_path.read_text(encoding="utf-8")
            assert f"# {module.canonical_page_title(rel_path, module.wiki_pages(packet)[rel_path])}" in mirror_text
            assert f"Canonical page: `{rel_path}`" in mirror_text
            assert "## Query aliases" in mirror_text
            assert "## Canonical content" in mirror_text
            for alias in module.retrieval_page_aliases(rel_path):
                assert f"- {alias}" in mirror_text
        assert packet["wiki_retrieval_contract"]["canonical_page_count"] == len(module.EXPECTED_WIKI_PAGES)
        assert packet["wiki_retrieval_contract"]["rendered_sha256"] == module.rendered_content_sha256(retrieval_text)
        assert first_write["status"] == "changed"
        assert first_write["changed_count"] == (2 * len(module.EXPECTED_WIKI_PAGES)) + 1
        assert first_write["unchanged_count"] == 0

        mtimes = {
            row["path"]: (root / row["path"]).stat().st_mtime_ns
            for row in first_write["artifacts"]
        }
        second_write = module.write_wiki_pages(packet)
        assert second_write["status"] == "unchanged"
        assert second_write["changed_count"] == 0
        assert second_write["unchanged_count"] == (2 * len(module.EXPECTED_WIKI_PAGES)) + 1
        assert second_write["source_snapshot_sha256"] == first_write["source_snapshot_sha256"]
        assert second_write["render_contract_sha256"] == first_write["render_contract_sha256"]
        assert {
            row["path"]: (root / row["path"]).stat().st_mtime_ns
            for row in second_write["artifacts"]
        } == mtimes


def test_write_wiki_pages_changes_only_modified_render() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        packet = module.build_packet()
        page_map = module.wiki_pages(packet)
        module.write_wiki_pages(packet, page_map)

        modified_path = "wiki/README.md"
        changed_map = dict(page_map)
        changed_map[modified_path] = changed_map[modified_path] + "\nChanged-only proof.\n"
        delta = module.write_wiki_pages(packet, changed_map)

        changed = [row["path"] for row in delta["artifacts"] if row["changed"]]
        assert changed == [
            modified_path,
            module.retrieval_mirror_path(modified_path),
            module.RETRIEVAL_SOURCE_REL,
        ]
        assert delta["changed_count"] == 3
        assert delta["unchanged_count"] == (2 * len(module.EXPECTED_WIKI_PAGES)) - 2


def test_rendered_wiki_disk_proof_detects_tampering_but_tolerates_absent_fixture_pages() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        absent = module.build_packet(verify_rendered_files=True)
        assert absent["rendered_wiki_verification"]["status"] == "not_present_tolerated"
        assert absent["validation"]["status"] == "warning"

        packet = module.build_packet(verify_rendered_files=False, planned_write_wiki=True)
        page_map = module.wiki_pages(packet)
        module.write_wiki_pages(packet, page_map)
        module.finalize_rendered_wiki_verification(packet, page_map)
        assert packet["rendered_wiki_verification"]["status"] == "verified"
        assert packet["validation"]["status"] == "warning"
        for page in packet["wiki_pages"]:
            path = root / page["path"]
            assert page["physical_state"] == "match"
            assert page["observed_sha256"] == page["rendered_sha256"]
            assert module.rendered_content_sha256(path.read_text(encoding="utf-8")) == page["rendered_sha256"]

        tampered_path = root / "wiki" / "README.md"
        tampered_path.write_text(tampered_path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")
        tampered = module.build_packet(verify_rendered_files=True)
        assert tampered["rendered_wiki_verification"]["status"] == "mismatch"
        assert tampered["validation"]["status"] == "blocked"
        assert "wiki_rendered_page_sha256_mismatch:wiki/README.md" in tampered["validation"]["errors"]
        assert module.main(["--validate"]) == 1

        tampered_path.unlink()
        partial = module.build_packet(verify_rendered_files=True)
        assert partial["validation"]["status"] == "blocked"
        assert any(error.startswith("wiki_rendered_page_set_incomplete:") for error in partial["validation"]["errors"])
        assert "wiki_rendered_page_missing:wiki/README.md" in partial["validation"]["errors"]


def test_rendered_wiki_disk_proof_blocks_uncontracted_markdown() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        packet = module.build_packet(verify_rendered_files=False, planned_write_wiki=True)
        page_map = module.wiki_pages(packet)
        module.write_wiki_pages(packet, page_map)
        orphan = root / "wiki" / "orphan.md"
        orphan.write_text("# Uncontracted\n", encoding="utf-8")

        observed = module.build_packet(verify_rendered_files=True)
        verification = observed["rendered_wiki_verification"]
        assert verification["filesystem_page_count"] == len(module.EXPECTED_WIKI_PAGES) + 1
        assert verification["present_page_count"] == len(module.EXPECTED_WIKI_PAGES)
        assert verification["uncontracted_page_paths"] == ["wiki/orphan.md"]
        assert verification["status"] == "mismatch"
        assert observed["validation"]["status"] == "blocked"
        assert "wiki_rendered_uncontracted_page:wiki/orphan.md" in observed["validation"]["errors"]


def test_source_snapshot_and_main_write_stay_coherent_across_source_drift() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        source_path = root / module.SOURCES["wf88_os2_control"]["path"]
        original_source = json.loads(source_path.read_text(encoding="utf-8"))
        drifted_source = json.loads(json.dumps(original_source))
        drifted_source["summary"]["canonical_action_count"] = 999

        original_snapshots = module.source_snapshots

        def snapshots_then_drift():
            payloads, descriptors = original_snapshots()
            write_json(source_path, drifted_source)
            return payloads, descriptors

        module.source_snapshots = snapshots_then_drift
        try:
            snapshot_packet = module.build_packet(verify_rendered_files=False)
        finally:
            module.source_snapshots = original_snapshots
        assert snapshot_packet["summary"]["wf88_canonical_action_count"] == 8
        assert snapshot_packet["inputs"]["wf88_os2_control"]["sha256"] != module.sha256_file(source_path)

        write_json(source_path, original_source)
        original_build_packet = module.build_packet
        build_count = 0

        def build_once_then_drift(*args, **kwargs):
            nonlocal build_count
            packet = original_build_packet(*args, **kwargs)
            build_count += 1
            if build_count == 1:
                write_json(source_path, drifted_source)
            return packet

        module.build_packet = build_once_then_drift
        try:
            assert module.main(["--write", "--write-md", "--write-wiki", "--validate"]) == 0
        finally:
            module.build_packet = original_build_packet
        assert build_count == 1
        persisted = json.loads(module.OUT.read_text(encoding="utf-8"))
        assert persisted["summary"]["wf88_canonical_action_count"] == 8
        expected_pages = module.wiki_pages(persisted)
        for page in persisted["wiki_pages"]:
            path = root / page["path"]
            assert path.read_text(encoding="utf-8") == expected_pages[page["path"]]
            assert page["rendered_sha256"] == module.rendered_content_sha256(expected_pages[page["path"]])
            assert page["physical_state"] == "match"


def test_persisted_render_contract_prevents_delta_false_mismatch_and_blocks_real_drift() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)

        # A fixture with neither rendered pages nor a persisted packet remains
        # safe: there is no prior physical contract to compare against.
        with contextlib.redirect_stdout(io.StringIO()):
            assert module.main(["--pretty", "--validate"]) == 0

        with contextlib.redirect_stdout(io.StringIO()):
            assert module.main(["--write", "--write-md", "--write-wiki", "--validate"]) == 0
            # The prospective delta is intentionally new, but physical page
            # proof must use the just-persisted packet and still pass.
            assert module.main(["--pretty", "--validate"]) == 0

        persisted = json.loads(module.OUT.read_text(encoding="utf-8"))
        change_path = root / "wiki" / "changes" / "What Changed Since Last Refresh.md"

        # A persisted render contract changes the all-absent behavior: the
        # first-run fixture tolerance must not mask deletion of every page.
        for page_path in module.EXPECTED_WIKI_PAGES:
            (root / page_path).unlink()
        all_missing = module.build_packet(previous_packet=persisted, verify_rendered_files=False)
        module.finalize_persisted_rendered_wiki_validation(all_missing, persisted)
        assert all_missing["rendered_wiki_verification"]["status"] == "mismatch"
        assert (
            f"wiki_rendered_persisted_page_set_missing_all:present=0:expected={len(module.EXPECTED_WIKI_PAGES)}"
            in all_missing["validation"]["errors"]
        )
        assert next(
            row for row in all_missing["rendered_wiki_verification"]["page_results"]
            if row["path"] == "wiki/changes/What Changed Since Last Refresh.md"
        )["status"] == "absent"
        with contextlib.redirect_stdout(io.StringIO()):
            assert module.main(["--pretty", "--validate"]) == 1
        module.write_wiki_pages(persisted, module.wiki_pages(persisted))

        baseline_change_page = change_path.read_text(encoding="utf-8")
        change_path.write_text(baseline_change_page + "\nTAMPERED\n", encoding="utf-8")

        tampered = module.build_packet(previous_packet=persisted, verify_rendered_files=False)
        module.finalize_persisted_rendered_wiki_validation(tampered, persisted)
        assert tampered["rendered_wiki_verification"]["contract_source"] == "persisted_packet"
        assert tampered["validation"]["status"] == "blocked"
        assert (
            "wiki_rendered_page_sha256_mismatch:wiki/changes/What Changed Since Last Refresh.md"
            in tampered["validation"]["errors"]
        )
        with contextlib.redirect_stdout(io.StringIO()):
            assert module.main(["--pretty", "--validate"]) == 1

        change_path.write_text(baseline_change_page, encoding="utf-8")
        source_path = root / module.SOURCES["wf88_os2_control"]["path"]
        source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        source_payload["summary"]["canonical_action_count"] += 1
        write_json(source_path, source_payload)

        drifted = module.build_packet(previous_packet=persisted, verify_rendered_files=False)
        module.finalize_persisted_rendered_wiki_validation(drifted, persisted)
        assert drifted["rendered_wiki_verification"]["status"] == "verified"
        assert drifted["rendered_wiki_source_drift"]["status"] == "drifted_or_invalid"
        assert drifted["validation"]["status"] == "blocked"
        assert "wiki_rendered_source_snapshot_drift:wf88_os2_control:sha256" in drifted["validation"]["errors"]
        assert any(
            error.startswith("wiki_rendered_claim_source_ref_drift:")
            and ":wf88_os2_control:sha256" in error
            for error in drifted["validation"]["errors"]
        )
        with contextlib.redirect_stdout(io.StringIO()):
            assert module.main(["--pretty", "--validate"]) == 1


def test_claim_catalog_page_types_and_optional_review_references_are_governed() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        baseline = module.build_packet()

        claim_index = baseline["claim_index"]
        assert claim_index["schema"] == module.CLAIM_INDEX_SCHEMA
        assert claim_index["authority"] == "review_only"
        assert claim_index["claim_count"] == len(claim_index["claims"])
        assert {
            "promotion-leak-guard-health",
            "recommendation-outcome-closure",
            "followup-no-orphan-health",
        }.issubset({claim["claim_id"] for claim in claim_index["claims"]})
        action_claims = [claim for claim in claim_index["claims"] if claim["claim_kind"] == "rendered_action_state"]
        assert len(action_claims) == len(baseline["action_items"])
        for claim in claim_index["claims"]:
            assert claim["authority"] == "review_only"
            assert claim["source_refs"]
            for ref in claim["source_refs"]:
                assert ref["source_key"] in module.SOURCES
                assert ref["path"].startswith("tmp/")
                assert ref["json_pointer"].startswith("/")
                assert len(ref["sha256"]) == 64

        assert set(module.WIKI_PAGE_TYPES) == set(module.EXPECTED_WIKI_PAGES)
        pages = module.wiki_pages(baseline)
        for page_path, page_type in module.WIKI_PAGE_TYPES.items():
            assert f"Generated page type: {page_type}" in pages[page_path]
            assert page_type in module.VALID_PAGE_TYPES
        assert baseline["review_event_intake"]["status"] == "not_present_optional"
        assert baseline["validation"]["status"] == "warning"

        target_claim = next(claim for claim in claim_index["claims"] if claim["claim_id"] == "recommendation-outcome-closure")
        review_payload = {
            "schema": module.REVIEW_EVENT_SCHEMA,
            "generated_at_utc": module.utc_now(),
            "events": [
                {
                    "event_id": "review-20260809-001",
                    "event_at_utc": module.utc_now(),
                    "claim_id": target_claim["claim_id"],
                    "disposition": "needs_evidence",
                    "reason_code": "evidence_missing",
                    "source_ref": target_claim["source_refs"][0],
                    "followup_ref": {
                        "route": "WF74",
                        "source_ref": module.source_ref(
                            baseline["inputs"], "wf74_decision_docket", "/summary/row_count",
                        ),
                    },
                }
            ],
        }
        write_json(module.review_event_path(), review_payload)
        reviewed = module.build_packet()

        assert reviewed["validation"]["status"] == "warning"
        assert not any(error.startswith("review_event") for error in reviewed["validation"]["errors"])
        assert reviewed["summary"] == baseline["summary"]
        assert reviewed["action_items"] == baseline["action_items"]
        assert reviewed["review_event_intake"]["event_count"] == 1
        assert "review-20260809-001" in module.wiki_pages(reviewed)["wiki/changes/What Changed Since Last Refresh.md"]

        review_payload["events"][0]["disposition"] = "approve"
        write_json(module.review_event_path(), review_payload)
        invalid = module.build_packet()
        assert invalid["validation"]["status"] == "blocked"
        assert "review_event_intake:review_event:0:authoritative_disposition" in invalid["validation"]["errors"]

        unknown_claim_payload = json.loads(json.dumps(review_payload))
        unknown_claim_payload["events"][0]["disposition"] = "needs_evidence"
        unknown_claim_payload["events"][0]["claim_id"] = "unknown-claim-id"
        write_json(module.review_event_path(), unknown_claim_payload)
        unknown_claim = module.build_packet()
        assert unknown_claim["validation"]["status"] == "blocked"
        assert "review_event_intake:review_event:0:unknown_claim_id" in unknown_claim["validation"]["errors"]

        markdown_ref_payload = json.loads(json.dumps(review_payload))
        markdown_ref_payload["events"][0]["disposition"] = "needs_evidence"
        markdown_ref_payload["events"][0]["source_ref"]["path"] = "wiki/attempted-override.md"
        write_json(module.review_event_path(), markdown_ref_payload)
        markdown_ref = module.build_packet()
        assert markdown_ref["validation"]["status"] == "blocked"
        assert "review_event_intake:review_event:0:source_ref_prohibited_path" in markdown_ref["validation"]["errors"]


def test_claim_catalog_delta_is_comparison_only_and_main_snapshots_prior_packet() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        first = module.build_packet()
        unchanged = module.build_packet(previous_packet=first)

        assert unchanged["refresh_delta"]["status"] == "available"
        assert unchanged["refresh_delta"]["added_claim_ids"] == []
        assert unchanged["refresh_delta"]["removed_claim_ids"] == []
        assert unchanged["refresh_delta"]["changed_claim_ids"] == []
        assert unchanged["refresh_delta"]["source_ref_changed_claim_ids"] == []
        assert unchanged["summary"] == first["summary"]
        assert unchanged["action_items"] == first["action_items"]

        source = root / module.SOURCES["wf88_os2_control"]["path"]
        source_payload = json.loads(source.read_text(encoding="utf-8"))
        source_payload["summary"]["recommendation_later_outcome_graded_rows"] = 1
        source_payload["summary"]["recommendation_current_preview_later_outcome_graded_rows"] = 1
        write_json(source, source_payload)
        changed = module.build_packet(previous_packet=first)
        assert "recommendation-outcome-closure" in changed["refresh_delta"]["changed_claim_ids"]
        assert "recommendation-outcome-closure" in changed["refresh_delta"]["source_ref_changed_claim_ids"]
        assert "action-state:grade-recommendation-outcomes" in changed["refresh_delta"]["changed_claim_ids"]
        assert changed["summary"]["recommendation_later_outcome_graded_rows"] == 1
        assert changed["summary"]["recommendation_current_preview_later_outcome_graded_rows"] == 1

        incompatible = module.build_packet(previous_packet={"claim_index": {"schema": "incompatible", "claims": []}})
        assert incompatible["refresh_delta"]["status"] == "unavailable"
        assert incompatible["refresh_delta"]["reason"] == "prior_claim_catalog_missing_or_incompatible"

        previous = json.loads(json.dumps(first))
        previous["claim_index"]["claims"][0]["normalized_value"] = {"state": "tampered-prior-baseline"}
        write_json(module.OUT, previous)
        assert module.main(["--write", "--write-wiki", "--validate"]) == 0
        persisted = json.loads(module.OUT.read_text(encoding="utf-8"))
        assert persisted["refresh_delta"]["status"] == "available"
        assert persisted["claim_index"]["claims"][0]["claim_id"] in persisted["refresh_delta"]["changed_claim_ids"]


def test_component_actions_fail_closed_on_upstream_validation_or_unattested_counters() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)

        retrieval_path = root / module.SOURCES["retrieval_quality_scorecard"]["path"]
        retrieval = json.loads(retrieval_path.read_text(encoding="utf-8"))
        retrieval["validation"]["status"] = "blocked"
        write_json(retrieval_path, retrieval)

        frontier_path = root / module.SOURCES["frontier_capability_eval_spine"]["path"]
        frontier = json.loads(frontier_path.read_text(encoding="utf-8"))
        frontier["status"] = "warning_upstream"
        frontier["result_collection"]["row_count"] = 300
        frontier["result_collection"]["proof_verification"]["all_assignment_execution_proven"] = True
        frontier["result_collection"]["proof_verification"]["proof_index_chain_verified"] = True
        frontier["comparison_readiness"]["all_comparison_gates_passed"] = True
        frontier["comparison_readiness"]["cross_model_ranking_allowed"] = True
        frontier["comparison_readiness"]["trusted_execution_attestation_verified"] = True
        frontier["comparison_readiness"]["trusted_output_artifact_attestation_verified"] = True
        frontier["comparison_readiness"]["trusted_grader_attestation_verified"] = True
        write_json(frontier_path, frontier)

        compiler_path = root / module.SOURCES["wf88_decision_compiler"]["path"]
        compiler = json.loads(compiler_path.read_text(encoding="utf-8"))
        compiler["validation"]["status"] = "blocked"
        write_json(compiler_path, compiler)

        rsi_path = root / module.SOURCES["rsi_outcome_scorecard"]["path"]
        rsi = json.loads(rsi_path.read_text(encoding="utf-8"))
        rsi["status"] = "warning_upstream"
        rsi["validation"]["status"] = "ok"
        rsi["maturity_gate"]["mature"] = True
        rsi["summary"]["live_complete_stable_count"] = 30
        rsi["summary"]["missing_link_debt_item_count"] = 0
        write_json(rsi_path, rsi)

        advanced_path = root / module.SOURCES["advanced_capability_pilot_packet"]["path"]
        advanced = json.loads(advanced_path.read_text(encoding="utf-8"))
        advanced["status"] = "execution_evidence_ready_review_only"
        advanced["summary"]["executed_pilot_count"] = 6
        advanced["summary"]["external_api_calls_performed"] = True
        write_json(advanced_path, advanced)

        token_scorecard_path = root / module.SOURCES["token_efficiency_scorecard"]["path"]
        token_scorecard = json.loads(token_scorecard_path.read_text(encoding="utf-8"))
        token_scorecard["status"] = "blocked"
        token_scorecard["validation"]["status"] = "error"
        write_json(token_scorecard_path, token_scorecard)

        token_bridge_path = root / module.SOURCES["implementation_token_attribution_bridge"]["path"]
        token_bridge = json.loads(token_bridge_path.read_text(encoding="utf-8"))
        token_bridge["status"] = "blocked"
        token_bridge["validation"]["status"] = "blocked"
        token_bridge["summary"]["unclassified_supported_runtime_gap_count"] = 1
        token_bridge["summary"]["closeout_enforcement_required"] = True
        write_json(token_bridge_path, token_bridge)

        packet = module.build_packet()
        states = {row["id"]: row["state"] for row in packet["action_items"]}
        assert packet["validation"]["status"] == "blocked"
        assert states["maintain-wf88-retrieval-regression-corpus"] == "blocked"
        assert states["collect-frontier-capability-eval-results"] == "evidence_collection_required"
        assert states["compile-wf88-decision-objects"] == "blocked"
        assert states["close-rsi-outcome-linkage-debt"] == "evidence_linkage_required"
        assert states["run-isolated-advanced-capability-pilots"] == "blocked"
        assert states["optimize-token-heavy-cron-api-calls"] == "repair_required"

        frontier["status"] = "ready_to_collect"
        frontier["comparison_readiness"]["trusted_execution_attestation_verified"] = False
        frontier["comparison_readiness"]["trusted_output_artifact_attestation_verified"] = False
        frontier["comparison_readiness"]["trusted_grader_attestation_verified"] = False
        write_json(frontier_path, frontier)
        unattested_packet = module.build_packet()
        unattested_states = {row["id"]: row["state"] for row in unattested_packet["action_items"]}
        assert unattested_states["collect-frontier-capability-eval-results"] == "evidence_collection_required"
        assert "frontier_ranking_without_complete_trusted_attestation" in unattested_packet["validation"]["errors"]


def test_blocked_token_bridge_blocks_efficiency_claims_not_wiki_content() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)

        token_bridge_path = root / module.SOURCES["implementation_token_attribution_bridge"]["path"]
        token_bridge = json.loads(token_bridge_path.read_text(encoding="utf-8"))
        token_bridge["status"] = "blocked"
        token_bridge["validation"]["status"] = "blocked"
        token_bridge["summary"]["unclassified_supported_runtime_gap_count"] = 1
        token_bridge["summary"]["closeout_enforcement_required"] = True
        write_json(token_bridge_path, token_bridge)

        packet = module.build_packet()
        states = {row["id"]: row["state"] for row in packet["action_items"]}
        assert packet["validation"]["status"] != "blocked"
        assert "implementation_token_attribution_bridge_blocked" not in packet["validation"]["errors"]
        assert (
            "implementation_token_attribution_bridge_blocked_efficiency_claims_only"
            in packet["validation"]["warnings"]
        )
        assert states["optimize-token-heavy-cron-api-calls"] == "repair_required"


if __name__ == "__main__":
    test_wiki_synthesis_routes_recommendations_without_apply_authority()
    test_startup_efficiency_semantics_are_generated_and_gated()
    test_wiki_synthesis_blocks_leaked_recommendations_and_auto_apply()
    test_wiki_synthesis_blocks_legacy_rsi_as_required_source()
    test_write_wiki_pages_creates_expected_durable_markdown()
    test_rendered_wiki_disk_proof_detects_tampering_but_tolerates_absent_fixture_pages()
    test_rendered_wiki_disk_proof_blocks_uncontracted_markdown()
    test_source_snapshot_and_main_write_stay_coherent_across_source_drift()
    test_persisted_render_contract_prevents_delta_false_mismatch_and_blocks_real_drift()
    test_claim_catalog_page_types_and_optional_review_references_are_governed()
    test_claim_catalog_delta_is_comparison_only_and_main_snapshots_prior_packet()
    test_component_actions_fail_closed_on_upstream_validation_or_unattested_counters()
    test_blocked_token_bridge_blocks_efficiency_claims_not_wiki_content()
    print("wf88 wiki synthesis packet tests passed")
