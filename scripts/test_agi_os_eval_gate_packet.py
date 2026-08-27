from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agi_os_eval_gate_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("agi_os_eval_gate_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgiOsEvalGatePacketTests(unittest.TestCase):
    def test_eval_gates_warn_without_later_outcomes_and_preserve_boundary(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tmp").mkdir()

            paths = {}
            for name, filename in {
                "recommendation_outcomes": "recommendation.json",
                "finance_decision_performance": "finance.json",
                "coding_outcomes": "coding.json",
                "wf55_autonomy_outcomes": "wf55.json",
                "wf87_shadow_outcomes": "wf87.json",
                "vector_memory_graph": "graph.json",
                "token_efficiency_review": "token.json",
                "implementation_token_attribution": "implementation-token.json",
                "frontier_capability_eval": "frontier.json",
                "rsi_outcome_scorecard": "rsi-outcomes.json",
                "advanced_capability_pilots": "advanced-pilots.json",
                "retrieval_quality": "retrieval.json",
                "wf88_decision_compiler": "compiler.json",
                "agent_message_ledger": "agent.json",
                "wf74_wf88_checkpoint": "wf74.json",
                "wf84_wf85_checkpoint": "wf84.json",
                "implementation_checkpoint": "impl.json",
            }.items():
                paths[name] = root / "tmp" / filename

            paths["recommendation_outcomes"].write_text(json.dumps({"summary": {"graded_count": 0}}), encoding="utf-8")
            paths["finance_decision_performance"].write_text(json.dumps({"summary": {"scoreable_count": 0}}), encoding="utf-8")
            paths["coding_outcomes"].write_text(
                json.dumps({
                    "status": "ok",
                    "ledger_summary": {
                        "model_performance_claim_gate": {
                            "model_performance_claim_allowed": False,
                            "graded_count": 2,
                        }
                    },
                }),
                encoding="utf-8",
            )
            paths["vector_memory_graph"].write_text(json.dumps({"summary": {"node_count": 3, "edge_count": 2}}), encoding="utf-8")
            paths["token_efficiency_review"].write_text(
                json.dumps({"summary": {"promotion_ready_count": 0, "top_candidate": "PM"}}),
                encoding="utf-8",
            )
            paths["implementation_token_attribution"].write_text(
                json.dumps({
                    "status": "ok",
                    "validation": {"status": "ok"},
                    "summary": {
                        "gap_resolution_status": "classified_unavailable_only",
                        "unclassified_supported_runtime_gap_count": 0,
                    },
                }),
                encoding="utf-8",
            )
            paths["frontier_capability_eval"].write_text(
                json.dumps({
                    "status": "ready_to_collect",
                    "fixture_integrity": {"case_count": 100, "digest_match": True, "privacy": {"raw_capture": False}},
                    "study_design": {"assignment_count": 300, "model_execution_performed": False},
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
                    "validation": {"status": "ok"},
                }),
                encoding="utf-8",
            )
            paths["rsi_outcome_scorecard"].write_text(
                json.dumps({
                    "status": "warning",
                    "summary": {
                        "live_trace_row_count": 5,
                        "live_trace_unique_correlation_id_count": 5,
                        "live_trace_duplicate_correlation_id_count": 0,
                        "live_trace_missing_correlation_id_count": 0,
                        "live_trace_noncanonical_correlation_id_count": 0,
                        "live_complete_stable_count": 0,
                        "live_authority_violation_count": 0,
                    },
                    "maturity_gate": {"mature": False, "all_metric_gates_met": False, "correlation_integrity_gate_met": True},
                    "validation": {"status": "warning"},
                }),
                encoding="utf-8",
            )
            paths["advanced_capability_pilots"].write_text(
                json.dumps({
                    "status": "fixture_ready_no_execution_authority",
                    "summary": {
                        "pilot_count": 6,
                        "executed_pilot_count": 0,
                        "promotion_ready_count": 0,
                        "external_api_calls_performed": False,
                        "raw_content_stored": False,
                    },
                    "authority_boundary": {
                        "external_api_calls_performed": False,
                        "raw_prompt_capture": False,
                        "raw_response_capture": False,
                        "runtime_or_config_mutation": False,
                        "model_route_mutation": False,
                    },
                    "validation": {"status": "ok"},
                }),
                encoding="utf-8",
            )
            paths["retrieval_quality"].write_text(
                json.dumps({
                    "status": "ok",
                    "summary": {
                        "fixtures": 42,
                        "passed": 42,
                        "failed": 0,
                        "classes": [f"class_{index}" for index in range(10)],
                        "average_score": 1.0,
                        "freshness_proof": {
                            "assessment_mode_counts": {"source_timestamp_age": 1},
                            "live_source_timestamp_age_assessment_count": 1,
                        },
                    },
                    "measurement_contract": {
                        "freshness": {
                            "label_only_cases_are_live_source_proof": False,
                            "declared_labels_are_authoritative": False,
                            "source_timestamp_age_is_live_source_proof": True,
                        },
                    },
                    "validation": {"status": "ok"},
                }),
                encoding="utf-8",
            )
            paths["wf88_decision_compiler"].write_text(
                json.dumps({
                    "status": "decision_objects_warning_review_only",
                    "summary": {"decision_object_count": 9, "blocked_count": 0, "conflict_count": 0},
                    "runtime_dependency_contract": {
                        "wiki_or_os2_inputs_forbidden": ["tmp/wf88-os2-control-packet.json", "tmp/wf88-wiki-synthesis-packet.json"],
                        "model_or_api_call": False,
                    },
                    "leak_guard": {"pass": True},
                    "validation": {"status": "warning", "errors": [], "warnings": ["upstream_warning"]},
                }),
                encoding="utf-8",
            )
            paths["agent_message_ledger"].write_text(json.dumps({
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "event_count": 4,
                    "verified_helper_event_count": 4,
                    "telemetry_blocked_event_count": 0,
                    "unverified_receipt_event_count": 0,
                },
            }), encoding="utf-8")
            paths["wf74_wf88_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            paths["wf84_wf85_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")

            payload = module.build_packet(root, paths)

            self.assertEqual(payload["validation"]["status"], "warning")
            self.assertIn("recommendation_later_outcome_gate", payload["validation"]["warnings"])
            self.assertIn("token_efficiency_promotion_gate", payload["validation"]["warnings"])
            self.assertIn("frontier_capability_eval_evidence_gate", payload["validation"]["warnings"])
            self.assertIn("rsi_later_outcome_maturity_gate", payload["validation"]["warnings"])
            self.assertIn("advanced_capability_pilot_execution_evidence_gate", payload["validation"]["warnings"])
            self.assertNotIn("frontier_capability_eval_contract_gate", payload["validation"]["warnings"])
            self.assertNotIn("advanced_capability_pilot_contract_gate", payload["validation"]["warnings"])
            self.assertNotIn("wf88_retrieval_regression_gate", payload["validation"]["warnings"])
            self.assertIn("wf88_decision_compiler_gate", payload["validation"]["warnings"])
            self.assertNotIn("implementation_token_attribution_gate", payload["validation"]["warnings"])
            self.assertFalse(payload["authority_boundary"]["autonomous_promotion_allowed"])
            self.assertFalse(payload["authority_boundary"]["paper_or_live_execution_allowed"])

    def test_eval_warns_when_implementation_token_attribution_has_unclassified_supported_gaps(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tmp").mkdir()
            paths = {name: root / "tmp" / f"{name}.json" for name in module.DEFAULT_INPUTS}
            for path in paths.values():
                path.write_text(json.dumps({"status": "ok", "summary": {}}), encoding="utf-8")
            paths["recommendation_outcomes"].write_text(json.dumps({"summary": {"graded_count": 1}}), encoding="utf-8")
            paths["finance_decision_performance"].write_text(json.dumps({"summary": {"scoreable_count": 1}}), encoding="utf-8")
            paths["coding_outcomes"].write_text(json.dumps({
                "status": "ok",
                "ledger_summary": {
                    "model_performance_claim_gate": {
                        "model_performance_claim_allowed": False,
                        "graded_count": 4,
                    }
                },
            }), encoding="utf-8")
            paths["vector_memory_graph"].write_text(json.dumps({"summary": {"edge_count": 2}}), encoding="utf-8")
            paths["token_efficiency_review"].write_text(json.dumps({"summary": {"promotion_ready_count": 1}}), encoding="utf-8")
            paths["agent_message_ledger"].write_text(json.dumps({
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "event_count": 1,
                    "verified_helper_event_count": 1,
                    "telemetry_blocked_event_count": 0,
                    "unverified_receipt_event_count": 0,
                },
            }), encoding="utf-8")
            paths["wf74_wf88_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            paths["wf84_wf85_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            paths["implementation_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            paths["implementation_token_attribution"].write_text(json.dumps({
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "gap_resolution_status": "stamp_required",
                    "unclassified_supported_runtime_gap_count": 2,
                }
            }), encoding="utf-8")

            payload = module.build_packet(root, paths)

            self.assertIn("implementation_token_attribution_gate", payload["validation"]["warnings"])
            self.assertNotIn("model_performance_claim_boundary_gate", payload["validation"]["warnings"])

    def test_eval_warns_when_model_performance_claim_gate_missing(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tmp").mkdir()
            paths = {name: root / "tmp" / f"{name}.json" for name in module.DEFAULT_INPUTS}
            for path in paths.values():
                path.write_text(json.dumps({"status": "ok", "summary": {}}), encoding="utf-8")
            paths["recommendation_outcomes"].write_text(json.dumps({"summary": {"graded_count": 1}}), encoding="utf-8")
            paths["finance_decision_performance"].write_text(json.dumps({"summary": {"scoreable_count": 1}}), encoding="utf-8")
            paths["vector_memory_graph"].write_text(json.dumps({"summary": {"edge_count": 2}}), encoding="utf-8")
            paths["token_efficiency_review"].write_text(json.dumps({"summary": {"promotion_ready_count": 1}}), encoding="utf-8")
            paths["implementation_token_attribution"].write_text(json.dumps({
                "summary": {
                    "gap_resolution_status": "classified_unavailable_only",
                    "unclassified_supported_runtime_gap_count": 0,
                }
            }), encoding="utf-8")
            paths["agent_message_ledger"].write_text(json.dumps({
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "event_count": 1,
                    "verified_helper_event_count": 1,
                    "telemetry_blocked_event_count": 0,
                    "unverified_receipt_event_count": 0,
                },
            }), encoding="utf-8")
            paths["wf74_wf88_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            paths["wf84_wf85_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            paths["implementation_checkpoint"].write_text(json.dumps({"status": "ok"}), encoding="utf-8")

            payload = module.build_packet(root, paths)

            self.assertIn("model_performance_claim_boundary_gate", payload["validation"]["warnings"])

    def test_unattested_frontier_and_counter_only_pilots_never_pass_evidence_gates(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tmp").mkdir()
            paths = {name: root / "tmp" / f"{name}.json" for name in module.DEFAULT_INPUTS}
            for path in paths.values():
                path.write_text(json.dumps({"status": "ok", "summary": {}}), encoding="utf-8")

            paths["frontier_capability_eval"].write_text(json.dumps({
                "status": "warning_upstream",
                "fixture_integrity": {"case_count": 100, "digest_match": True, "privacy": {"raw_capture": False}},
                "study_design": {"assignment_count": 300, "model_execution_performed": False},
                "result_collection": {
                    "row_count": 300,
                    "proof_verification": {
                        "fully_verified_result_count": 300,
                        "all_assignment_execution_proven": True,
                        "proof_index_chain_verified": True,
                    },
                },
                "comparison_readiness": {
                    "all_comparison_gates_passed": True,
                    "cross_model_ranking_allowed": True,
                    "trusted_execution_attestation_verified": True,
                    "trusted_output_artifact_attestation_verified": True,
                    "trusted_grader_attestation_verified": True,
                },
                "validation": {"status": "ok"},
            }), encoding="utf-8")
            paths["advanced_capability_pilots"].write_text(json.dumps({
                "status": "execution_evidence_ready_review_only",
                "summary": {
                    "pilot_count": 6,
                    "executed_pilot_count": 6,
                    "promotion_ready_count": 0,
                    "external_api_calls_performed": True,
                    "raw_content_stored": False,
                },
                "authority_boundary": {
                    "raw_prompt_capture": False,
                    "raw_response_capture": False,
                    "runtime_or_config_mutation": False,
                    "model_route_mutation": False,
                },
                "validation": {"status": "ok"},
            }), encoding="utf-8")
            paths["rsi_outcome_scorecard"].write_text(json.dumps({
                "status": "warning",
                "summary": {
                    "live_authority_violation_count": 0,
                    "live_trace_duplicate_correlation_id_count": 0,
                    "live_trace_missing_correlation_id_count": 0,
                    "live_trace_noncanonical_correlation_id_count": 0,
                },
                "maturity_gate": {
                    "mature": True,
                    "all_metric_gates_met": True,
                    "correlation_integrity_gate_met": True,
                },
                "validation": {"status": "ok"},
            }), encoding="utf-8")

            payload = module.build_packet(root, paths)
            gates = {row["name"]: row for row in payload["gates"]}
            self.assertEqual(gates["frontier_capability_eval_evidence_gate"]["status"], "warning")
            self.assertEqual(gates["advanced_capability_pilot_execution_evidence_gate"]["status"], "warning")
            self.assertEqual(gates["rsi_later_outcome_maturity_gate"]["status"], "warning")

    def test_telemetry_blocked_agent_events_and_blocked_sources_cannot_pass_gates(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tmp").mkdir()
            paths = {name: root / "tmp" / f"{name}.json" for name in module.DEFAULT_INPUTS}
            for path in paths.values():
                path.write_text(json.dumps({"status": "ok", "validation": {"status": "ok"}, "summary": {}}), encoding="utf-8")
            paths["coding_outcomes"].write_text(json.dumps({
                "status": "blocked",
                "validation": {"status": "blocked"},
                "ledger_summary": {"telemetry_uncreditable_row_count": 1},
            }), encoding="utf-8")
            paths["implementation_token_attribution"].write_text(json.dumps({
                "status": "blocked",
                "validation": {"status": "blocked"},
                "summary": {
                    "gap_resolution_status": "complete",
                    "unclassified_supported_runtime_gap_count": 0,
                },
            }), encoding="utf-8")
            paths["agent_message_ledger"].write_text(json.dumps({
                "status": "ok",
                "validation": {"status": "ok"},
                "summary": {
                    "event_count": 1,
                    "verified_helper_event_count": 0,
                    "telemetry_blocked_event_count": 1,
                    "unverified_receipt_event_count": 1,
                },
            }), encoding="utf-8")

            payload = module.build_packet(root, paths)
            gates = {item["name"]: item for item in payload["gates"]}

            self.assertEqual(gates["coding_followthrough_gate"]["status"], "fail")
            self.assertEqual(gates["implementation_token_attribution_gate"]["status"], "warning")
            self.assertEqual(gates["agent_message_ledger_gate"]["status"], "warning")


if __name__ == "__main__":
    unittest.main()
