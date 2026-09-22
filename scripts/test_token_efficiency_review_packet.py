from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "token_efficiency_review_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("token_efficiency_review_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TokenEfficiencyReviewPacketTests(unittest.TestCase):
    def test_review_packet_summarizes_candidates_without_apply_authority(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scorecard = root / "token-efficiency-scorecard.json"
            scorecard.write_text(json.dumps({
                "status": "warning",
                "generated_at_utc": "2026-07-05T00:00:00Z",
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
                    "api_call_reduction_candidate_count": 1,
                    "prompt_compression_candidate_count": 1,
                    "failure_cost_candidate_count": 1,
                    "implementation_token_gap_count": 2,
                    "top_candidate": "PM - Proof Worker",
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
                "api_call_reduction_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Proof Worker",
                        "total_tokens": 1000,
                        "run_count": 4,
                        "candidate_types": ["changed_only_prefilter_review", "failure_cost_repair_review"],
                        "predispatch_contract": {"mode": "changed_input_hash_before_model_spawn"},
                    }
                ],
                "prompt_compression_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Proof Worker",
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    }
                ],
                "failure_cost_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Proof Worker",
                        "candidate_types": ["failure_cost_repair_review"],
                        "failed_or_error_count": 1,
                    }
                ],
                "action_items": [{"id": "review", "state": "ready_for_review"}],
                "validation": {"status": "warning"},
            }), encoding="utf-8")

            packet = module.build_packet(scorecard)

            self.assertEqual(packet["validation"]["status"], "warning")
            self.assertEqual(packet["summary"]["promotion_ready_count"], 0)
            self.assertEqual(packet["summary"]["changed_only_prefilter_review_count"], 1)
            self.assertEqual(packet["summary"]["api_equivalent_cost_usd"], 1.25)
            self.assertEqual(packet["summary"]["api_equivalent_estimate_status"], "complete")
            self.assertEqual(packet["summary"]["api_equivalent_cost_rows"], 10)
            self.assertEqual(packet["summary"]["estimated_chatgpt_credits"], 42.5)
            self.assertEqual(packet["summary"]["chatgpt_credit_estimate_status"], "complete")
            self.assertEqual(packet["summary"]["estimated_chatgpt_credit_rows"], 10)
            self.assertIsNone(packet["summary"]["actual_billed_cost_usd"])
            self.assertEqual(packet["summary"]["oauth_quota_state"], "normal")
            self.assertTrue(packet["billing_semantics"]["api_equivalent_is_not_invoice"])
            self.assertFalse(packet["oauth_capacity_control"]["automatic_action_allowed"])
            self.assertEqual(packet["automation_queues"]["changed_only_prefilter"]["state"], "candidate_available")
            self.assertEqual(
                packet["automation_queues"]["prompt_compression"]["next_candidate"]["cron_job_name"],
                "PM - Proof Worker",
            )
            self.assertFalse(packet["authority_boundary"]["cron_schedule_mutation_allowed"])
            self.assertFalse(packet["authority_boundary"]["code_mutation_allowed"])
            self.assertEqual(packet["top_api_call_reduction_candidates"][0]["cron_job_name"], "PM - Proof Worker")

    def test_review_packet_reads_action_required_attribution_denominator(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scorecard = root / "token-efficiency-scorecard.json"

            def write_scorecard(action_required: int) -> None:
                scorecard.write_text(json.dumps({
                    "status": "warning",
                    "generated_at_utc": "2026-09-12T00:00:00Z",
                    "summary": {
                        "token_event_count": 10,
                        "total_tokens": 1000,
                        "api_equivalent_cost_usd": 1.25,
                        "api_equivalent_estimate_status": "complete",
                        "api_equivalent_cost_rows": 10,
                        "api_equivalent_cost_event_coverage_percent": 100.0,
                        "api_call_reduction_candidate_count": 0,
                        "prompt_compression_candidate_count": 0,
                        "failure_cost_candidate_count": 0,
                        "implementation_token_gap_count": 597,
                        "attribution_gap_action_required_count": action_required,
                        "attribution_gap_resolution_status": (
                            "terminal_unavailable_only" if action_required == 0 else "stamp_required"
                        ),
                    },
                    "validation": {"status": "ok"},
                }), encoding="utf-8")

            write_scorecard(0)
            classified = module.build_packet(scorecard)
            self.assertEqual(classified["summary"]["attribution_gap_action_required_count"], 0)
            self.assertEqual(classified["summary"]["attribution_gap_resolution_status"], "terminal_unavailable_only")
            self.assertNotIn("implementation_token_gap_count:597", classified["validation"]["warnings"])
            self.assertNotIn("attribution_gap_action_required_count:0", classified["validation"]["warnings"])

            write_scorecard(2)
            actionable = module.build_packet(scorecard)
            self.assertIn("attribution_gap_action_required_count:2", actionable["validation"]["warnings"])

    def test_review_packet_marks_candidate_promotion_ready_from_regression_proof(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scorecard = root / "token-efficiency-scorecard.json"
            scorecard.write_text(json.dumps({
                "status": "warning",
                "summary": {
                    "api_call_reduction_candidate_count": 1,
                    "prompt_compression_candidate_count": 2,
                    "failure_cost_candidate_count": 0,
                    "implementation_token_gap_count": 0,
                    "top_candidate": "PM - Autonomous Implementation Proof Worker",
                },
                "api_call_reduction_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
                        "total_tokens": 1000,
                        "run_count": 4,
                        "candidate_types": ["changed_only_prefilter_review"],
                        "predispatch_contract": {"mode": "changed_input_hash_before_model_spawn"},
                    }
                ],
                "prompt_compression_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
                        "tokens_per_run": 1000,
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    },
                    {
                        "rank": 2,
                        "cron_job_name": "Finance - Ticker Card Freshness Owner Runner",
                        "tokens_per_run": 900,
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    },
                ],
                "validation": {"status": "warning"},
            }), encoding="utf-8")
            (root / "pm-autonomous-worker-predispatch-prefilter.json").write_text(json.dumps({
                "status": "skipped_unchanged",
                "action": "skip_worker",
                "would_run_existing_worker": False,
                "would_spawn_model_or_agent_turn": False,
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }), encoding="utf-8")

            packet = module.build_packet(scorecard)

            self.assertEqual(packet["summary"]["promotion_ready_count"], 1)
            self.assertEqual(packet["summary"]["promotion_incomplete_count"], 0)
            self.assertEqual(packet["summary"]["next_changed_only_candidate"], "PM - Autonomous Implementation Proof Worker")
            self.assertEqual(packet["automation_queues"]["changed_only_prefilter"]["state"], "promotion_ready")
            self.assertEqual(packet["promotion_ready_candidates"][0]["promotion_status"], "promotion_ready")
            self.assertEqual(packet["promotion_ready_candidates"][0]["proof_type"], "changed_only_prefilter_regression")
            self.assertFalse(packet["authority_boundary"]["cron_schedule_mutation_allowed"])

    def test_review_packet_surfaces_incomplete_promotion_proof(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scorecard = root / "token-efficiency-scorecard.json"
            scorecard.write_text(json.dumps({
                "status": "warning",
                "summary": {
                    "api_call_reduction_candidate_count": 1,
                    "prompt_compression_candidate_count": 2,
                    "failure_cost_candidate_count": 0,
                    "implementation_token_gap_count": 0,
                    "top_candidate": "PM - Autonomous Implementation Proof Worker",
                },
                "api_call_reduction_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
                        "total_tokens": 1000,
                        "run_count": 4,
                        "candidate_types": ["changed_only_prefilter_review"],
                        "predispatch_contract": {"mode": "changed_input_hash_before_model_spawn"},
                    }
                ],
                "prompt_compression_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
                        "tokens_per_run": 1000,
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    },
                    {
                        "rank": 2,
                        "cron_job_name": "Finance - Ticker Card Freshness Owner Runner",
                        "tokens_per_run": 900,
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    },
                ],
                "validation": {"status": "warning"},
            }), encoding="utf-8")
            (root / "pm-autonomous-worker-predispatch-prefilter.json").write_text(json.dumps({
                "status": "run_required",
                "action": "run_worker_when_promoted",
                "would_run_existing_worker": True,
                "would_spawn_model_or_agent_turn": None,
                "worker_prefilter": {
                    "source_unchanged": True,
                    "reason": "previous_packet_not_quiet_no_action",
                    "previous_action_type": "prepare_implementation_plan",
                },
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }), encoding="utf-8")

            packet = module.build_packet(scorecard)

            self.assertEqual(packet["summary"]["promotion_ready_count"], 0)
            self.assertEqual(packet["summary"]["promotion_incomplete_count"], 1)
            self.assertEqual(packet["summary"]["next_prompt_compression_candidate"], "Finance - Ticker Card Freshness Owner Runner")
            self.assertEqual(packet["automation_queues"]["changed_only_prefilter"]["state"], "proof_incomplete")
            incomplete = packet["promotion_incomplete_candidates"][0]
            self.assertEqual(incomplete["promotion_status"], "proof_incomplete")
            self.assertFalse(incomplete["proof_checks"]["status"])
            self.assertFalse(incomplete["proof_checks"]["action"])
            self.assertFalse(incomplete["proof_checks"]["would_run_existing_worker"])
            self.assertFalse(incomplete["proof_checks"]["would_spawn_model_or_agent_turn"])
            self.assertEqual(incomplete["failed_proof_checks"], [
                "status",
                "action",
                "would_run_existing_worker",
                "would_spawn_model_or_agent_turn",
            ])
            self.assertEqual(incomplete["proof_blocker"]["reason"], "previous_packet_not_quiet_no_action")
            self.assertEqual(incomplete["proof_blocker"]["previous_action_type"], "prepare_implementation_plan")

    def test_finance_fallback_can_be_promotion_ready_while_pm_remains_incomplete(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scorecard = root / "token-efficiency-scorecard.json"
            scorecard.write_text(json.dumps({
                "status": "warning",
                "summary": {
                    "api_call_reduction_candidate_count": 2,
                    "prompt_compression_candidate_count": 2,
                    "failure_cost_candidate_count": 0,
                    "implementation_token_gap_count": 0,
                    "top_candidate": "PM - Autonomous Implementation Proof Worker",
                },
                "api_call_reduction_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
                        "total_tokens": 1000,
                        "run_count": 4,
                        "candidate_types": ["changed_only_prefilter_review"],
                    },
                    {
                        "rank": 2,
                        "cron_job_name": "Finance - Ticker Card Freshness Owner Runner",
                        "total_tokens": 900,
                        "run_count": 3,
                        "candidate_types": ["changed_only_prefilter_review"],
                    },
                ],
                "prompt_compression_candidates": [
                    {
                        "rank": 1,
                        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
                        "tokens_per_run": 1000,
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    },
                    {
                        "rank": 2,
                        "cron_job_name": "Finance - Ticker Card Freshness Owner Runner",
                        "tokens_per_run": 900,
                        "candidate_types": ["prompt_compression_or_summary_cache_review"],
                    },
                ],
                "validation": {"status": "warning"},
            }), encoding="utf-8")
            (root / "pm-autonomous-worker-predispatch-prefilter.json").write_text(json.dumps({
                "status": "run_required",
                "action": "run_worker_when_promoted",
                "would_run_existing_worker": True,
                "would_spawn_model_or_agent_turn": None,
                "worker_prefilter": {"reason": "source_signature_changed", "source_unchanged": False},
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }), encoding="utf-8")
            (root / "ticker-card-freshness-owner-runner-prefilter.json").write_text(json.dumps({
                "status": "skipped_unchanged",
                "action": "skip_worker",
                "would_run_existing_worker": False,
                "would_spawn_model_or_agent_turn": False,
                "worker_prefilter": {
                    "reason": "source_unchanged_and_same_day_successful_output_present",
                    "source_unchanged": True,
                },
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }), encoding="utf-8")

            packet = module.build_packet(scorecard)

            self.assertEqual(packet["summary"]["promotion_ready_count"], 1)
            self.assertEqual(packet["summary"]["promotion_incomplete_count"], 1)
            self.assertEqual(
                packet["summary"]["next_changed_only_candidate"],
                "Finance - Ticker Card Freshness Owner Runner",
            )
            self.assertEqual(
                packet["summary"]["next_prompt_compression_candidate"],
                "Finance - Ticker Card Freshness Owner Runner",
            )
            self.assertEqual(packet["automation_queues"]["changed_only_prefilter"]["state"], "promotion_ready")
            self.assertEqual(
                packet["promotion_ready_candidates"][0]["proof_type"],
                "same_day_changed_only_prefilter_regression",
            )


if __name__ == "__main__":
    unittest.main()
