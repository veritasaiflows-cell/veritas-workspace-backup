#!/usr/bin/env python3
"""Focused regression tests for the WF88 Frontier Capability Evaluation Spine."""
from __future__ import annotations

import copy
import unittest

import frontier_capability_eval_spine as spine


FIXED_TIME = "2026-08-08T12:00:00Z"
COLLECTION_ID = "synthetic-test-collection"
PROOF_INDEX_REF = "memory://independent-frontier-proof-index"
RUN_OBSERVED_AT = "2026-08-08T12:00:00Z"
OUTPUT_OBSERVED_AT = "2026-08-08T12:01:00Z"
GRADER_OBSERVED_AT = "2026-08-08T12:02:00Z"
RUBRIC_ID = spine.EXPECTED_RUBRIC_ID
RUBRIC_SHA256 = spine.EXPECTED_RUBRIC_DIGEST
RUN_PRODUCER_ID = spine.PINNED_PRODUCER_ID_BY_ROLE["run_harness"]
OUTPUT_PRODUCER_ID = spine.PINNED_PRODUCER_ID_BY_ROLE["output_harness"]
GRADER_PRODUCER_ID = spine.PINNED_PRODUCER_ID_BY_ROLE["independent_grader"]


def fixture_packet() -> dict:
    return spine.load_json(spine.FIXTURE_PATH)


def result_rows(fixtures: dict) -> list[dict]:
    assignments, _ = spine.build_assignments(fixtures)
    candidate_scores = {
        "blind-amber-41": 0.91,
        "blind-cobalt-73": 0.83,
        "blind-slate-29": 0.74,
    }
    rows: list[dict] = []
    for index, assignment in enumerate(assignments, start=1):
        recovery_required = assignment["task_class"] == "multi_tool_recovery"
        score = candidate_scores[assignment["blind_candidate_id"]]
        rows.append({
            "schema": spine.RESULT_ROW_SCHEMA,
            "result_id": f"result-{index:04d}",
            "collection_id": COLLECTION_ID,
            "assignment_id": assignment["assignment_id"],
            "case_id": assignment["case_id"],
            "task_class": assignment["task_class"],
            "workload_fingerprint": assignment["workload_fingerprint"],
            "blind_candidate_id": assignment["blind_candidate_id"],
            "model_path": assignment["model_path"],
            "model_identity_verified": True,
            "attribution_source": "evaluation_harness_metadata",
            "attribution_eligible": True,
            "classification_eligible": True,
            "execution_state": "completed",
            "graded": True,
            "task_completion": True,
            "validator_pass": True,
            "first_pass_clean": True,
            "rework_count": 0,
            "latency_ms": 1000 + index,
            "usage_status": "exposed",
            "input_tokens": 1000,
            "cached_input_tokens": 250,
            "output_tokens": 400,
            "total_tokens": 1400,
            "missing_usage_classification": None,
            "authority_violation_count": 0,
            "authority_violation_codes": [],
            "refusal_observed": False,
            "refusal_appropriate": None,
            "tool_recovery_required": recovery_required,
            "tool_recovery_status": "recovered" if recovery_required else "not_required",
            "tool_recovery_attempts": 1 if recovery_required else 0,
            "grader_scores": {
                "overall": score,
                "task_quality": score,
                "recovery_quality": score,
                "boundary_quality": score,
            },
            "confidence_interval_eligible": True,
            "validator_regression": False,
            "run_proof_id": f"run-proof-{index:04d}",
            "run_proof_sha256": "0" * 64,
            "output_artifact_id": f"output-artifact-{index:04d}",
            "output_artifact_sha256": spine.digest({
                "assignment_id": assignment["assignment_id"],
                "synthetic_output_number": index,
            }),
            "output_proof_id": f"output-proof-{index:04d}",
            "output_proof_sha256": "0" * 64,
            "grader_id": GRADER_PRODUCER_ID,
            "rubric_id": RUBRIC_ID,
            "rubric_sha256": RUBRIC_SHA256,
            "grader_proof_id": f"grader-proof-{index:04d}",
            "grader_proof_sha256": "0" * 64,
        })
    return rows


def build_proof_index(fixtures: dict, rows: list[dict]) -> dict:
    assignments, _ = spine.build_assignments(fixtures)
    records: list[dict] = []
    for row in rows:
        record_specs = [
            ("run", row["run_proof_id"], RUN_PRODUCER_ID, RUN_OBSERVED_AT, "run_proof_sha256"),
            ("output", row["output_proof_id"], OUTPUT_PRODUCER_ID, OUTPUT_OBSERVED_AT, "output_proof_sha256"),
            ("grader", row["grader_proof_id"], row["grader_id"], GRADER_OBSERVED_AT, "grader_proof_sha256"),
        ]
        for proof_type, proof_id, producer_id, observed_at, row_hash_field in record_specs:
            record = {
                "schema": spine.PROOF_RECORD_SCHEMA,
                "proof_id": proof_id,
                "proof_type": proof_type,
                "collection_id": COLLECTION_ID,
                "assignment_id": row["assignment_id"],
                "case_id": row["case_id"],
                "blind_candidate_id": row["blind_candidate_id"],
                "producer_id": producer_id,
                "observed_at_utc": observed_at,
                "metadata_only": True,
                "raw_capture": False,
                "subject_sha256": spine.proof_subject_digest(row, proof_type),
                "record_sha256": "",
            }
            record["record_sha256"] = spine.proof_record_digest(record)
            row[row_hash_field] = record["record_sha256"]
            records.append(record)
    return {
        "schema": spine.PROOF_INDEX_SCHEMA,
        "fixture_set_id": fixtures["fixture_set_id"],
        "fixture_sha256": spine.fixture_digest(fixtures),
        "assignment_manifest_sha256": spine.digest(assignments),
        "collection_id": COLLECTION_ID,
        "metadata_only": True,
        "raw_capture": False,
        "producer_registry": [
            {
                "producer_id": RUN_PRODUCER_ID,
                "producer_role": "run_harness",
                "trust_domain": "candidate_execution",
                "metadata_only": True,
                "raw_capture": False,
            },
            {
                "producer_id": OUTPUT_PRODUCER_ID,
                "producer_role": "output_harness",
                "trust_domain": "candidate_execution",
                "metadata_only": True,
                "raw_capture": False,
            },
            {
                "producer_id": GRADER_PRODUCER_ID,
                "producer_role": "independent_grader",
                "trust_domain": "independent_scoring",
                "metadata_only": True,
                "raw_capture": False,
            },
        ],
        "records": records,
    }


def result_packet(fixtures: dict, rows: list[dict], proof_index: dict | None = None) -> dict:
    return {
        "schema": spine.RESULT_PACKET_SCHEMA,
        "fixture_set_id": fixtures["fixture_set_id"],
        "collection_id": COLLECTION_ID,
        "proof_index_ref": PROOF_INDEX_REF if rows else None,
        "proof_index_sha256": spine.digest(proof_index) if proof_index is not None else ("0" * 64 if rows else None),
        "raw_capture": False,
        "rows": rows,
    }


def build_verified_spine(fixtures: dict, rows: list[dict]) -> tuple[dict, dict]:
    proof_index = build_proof_index(fixtures, rows)
    packet = spine.build_spine(
        fixtures,
        result_packet(fixtures, rows, proof_index),
        proof_index=proof_index,
        proof_source_ref=PROOF_INDEX_REF,
        baseline_inputs={},
        generated_at_utc=FIXED_TIME,
    )
    return packet, proof_index


class FrontierCapabilityEvalSpineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = fixture_packet()

    def test_frozen_fixture_has_required_coverage_and_digest(self) -> None:
        validation = spine.validate_fixtures(self.fixtures)
        self.assertEqual(validation["status"], "ok", validation["errors"])
        self.assertEqual(validation["fixture_digest"], spine.EXPECTED_FIXTURE_DIGEST)
        self.assertEqual(validation["case_count"], 100)
        self.assertEqual(
            validation["case_counts_by_task_class"],
            {task_class: 20 for task_class in spine.REQUIRED_TASK_CLASSES},
        )

    def test_assignments_are_source_identical_and_scorer_blind(self) -> None:
        coordinator, scorer = spine.build_assignments(self.fixtures)
        validation = spine.validate_assignments(self.fixtures, coordinator, scorer)
        self.assertEqual(validation["status"], "ok", validation["errors"])
        self.assertEqual(len(coordinator), 300)
        self.assertEqual(len(scorer), 300)
        grouped: dict[str, list[dict]] = {}
        for row in coordinator:
            grouped.setdefault(row["case_id"], []).append(row)
        self.assertEqual(len(grouped), 100)
        for rows in grouped.values():
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({row["workload_fingerprint"] for row in rows}), 1)
            self.assertEqual({row["model_path"] for row in rows}, set(spine.REQUIRED_MODEL_PATHS))
        for row in scorer:
            self.assertFalse(set(row) & set(spine.SCORER_FORBIDDEN_IDENTITY_FIELDS))
            self.assertTrue(row["blind_candidate_id"])

    def test_candidate_set_is_sol_terra_luna_and_rejects_retired_gpt55_control(self) -> None:
        self.assertEqual(
            spine.REQUIRED_MODEL_PATHS,
            (
                "openai/gpt-5.6-sol",
                "openai/gpt-5.6-terra",
                "openai/gpt-5.6-luna",
            ),
        )
        observed = tuple(
            row["model_path"] for row in self.fixtures["candidate_routes"]
        )
        self.assertEqual(observed, spine.REQUIRED_MODEL_PATHS)
        self.assertNotIn("openai/gpt-5.5", observed)

    def test_empty_collection_is_honest_ready_to_collect_scaffold(self) -> None:
        packet = spine.build_spine(
            self.fixtures,
            spine.empty_result_packet(self.fixtures["fixture_set_id"]),
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        repeated = spine.build_spine(
            self.fixtures,
            spine.empty_result_packet(self.fixtures["fixture_set_id"]),
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet, repeated)
        self.assertEqual(packet["status"], "ready_to_collect")
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertEqual(packet["result_collection"]["row_count"], 0)
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])
        self.assertFalse(packet["comparison_readiness"]["promotion_review_eligible"])
        self.assertFalse(packet["comparison_readiness"]["promotion_action_allowed"])
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertEqual(
            packet["study_design"]["model_execution_state"],
            "verifier_ready_no_result_claims",
        )
        self.assertFalse(packet["comparison_readiness"]["trusted_execution_attestation_verified"])
        self.assertFalse(packet["comparison_readiness"]["trusted_output_artifact_attestation_verified"])
        self.assertFalse(packet["comparison_readiness"]["trusted_grader_attestation_verified"])
        self.assertFalse(packet["study_design"]["route_change_performed"])
        self.assertFalse(packet["authority_boundary"]["raw_capture"])

    def test_result_contract_covers_required_metadata_and_blocks_raw_capture(self) -> None:
        contract = spine.result_ingestion_contract()
        required = set(contract["row_required_fields"])
        expected = {
            "collection_id",
            "workload_fingerprint",
            "execution_state",
            "task_completion",
            "validator_pass",
            "first_pass_clean",
            "rework_count",
            "latency_ms",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
            "attribution_source",
            "authority_violation_count",
            "refusal_observed",
            "tool_recovery_status",
            "grader_scores",
            "confidence_interval_eligible",
            "classification_eligible",
            "run_proof_id",
            "run_proof_sha256",
            "output_artifact_id",
            "output_artifact_sha256",
            "output_proof_id",
            "output_proof_sha256",
            "grader_id",
            "rubric_id",
            "rubric_sha256",
            "grader_proof_id",
            "grader_proof_sha256",
        }
        self.assertTrue(expected <= required)
        self.assertIn("proof_index_ref", contract["packet_required_fields"])
        self.assertIn("proof_index_sha256", contract["packet_required_fields"])
        self.assertEqual(
            contract["proof_index_contract"]["pinned_rubric"],
            {"rubric_id": RUBRIC_ID, "rubric_sha256": RUBRIC_SHA256},
        )
        self.assertEqual(
            contract["proof_index_contract"]["pinned_producer_id_by_role"],
            spine.PINNED_PRODUCER_ID_BY_ROLE,
        )
        self.assertEqual(contract["proof_index_contract"]["proof_tier"], "local_unkeyed_integrity_only")
        self.assertFalse(contract["proof_index_contract"]["execution_proof_claimed"])
        self.assertTrue(contract["independent_attestation_contract"]["verifier_implemented"])
        self.assertFalse(
            contract["independent_attestation_contract"][
                "self_asserted_row_or_index_attestation_accepted"
            ]
        )
        self.assertFalse(contract["raw_capture"])
        self.assertFalse(contract["unknown_fields_allowed"])
        self.assertIn("historical", contract["historical_missing_usage_rule"].lower())
        self.assertIn("never inferred", contract["historical_missing_usage_rule"].lower())

    def test_forged_complete_local_hash_chain_stays_pre_attestation_and_cannot_compare(self) -> None:
        rows = result_rows(self.fixtures)
        packet, proof_index = build_verified_spine(self.fixtures, rows)
        readiness = packet["comparison_readiness"]
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertEqual(len(rows), 300)
        self.assertEqual(len(proof_index["records"]), 900)
        self.assertEqual(packet["status"], "pre_attestation_collection_complete")
        self.assertTrue(readiness["collection_pre_attestation_gates_passed"])
        self.assertFalse(readiness["all_comparison_gates_passed"])
        self.assertFalse(readiness["cross_model_ranking_allowed"])
        self.assertFalse(readiness["promotion_review_eligible"])
        self.assertFalse(readiness["promotion_action_allowed"])
        self.assertEqual(
            readiness["matched_case_counts_by_task_class"],
            {task_class: 20 for task_class in spine.REQUIRED_TASK_CLASSES},
        )
        self.assertEqual(set(readiness["eligible_graded_output_counts_by_candidate"].values()), {100})
        self.assertEqual(readiness["review_only_blind_ranking_rows"], [])
        self.assertEqual(readiness["blind_candidate_statistics"], [])
        self.assertEqual(readiness["coordinator_candidate_statistics"], [])
        self.assertFalse(readiness["comparison_statistics_released"])
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertFalse(packet["study_design"]["spine_executed_models"])
        self.assertFalse(packet["study_design"]["all_assignment_execution_proven"])
        self.assertTrue(packet["study_design"]["all_assignment_local_integrity_valid"])
        self.assertEqual(
            packet["study_design"]["model_execution_state"],
            "verifier_available_signed_bundle_not_supplied",
        )
        self.assertEqual(
            packet["assignment_manifest"]["status"],
            "frozen_with_pre_attestation_collection_complete",
        )
        self.assertFalse(readiness["trusted_execution_attestation_verified"])
        self.assertFalse(readiness["trusted_output_artifact_attestation_verified"])
        self.assertFalse(readiness["trusted_grader_attestation_verified"])
        attestation = packet["result_collection"]["independent_attestation"]
        self.assertTrue(attestation["verifier_implemented"])
        self.assertEqual(
            attestation["attestation_tier"],
            "allowlisted_local_hmac_tamper_evidence_not_provider_origin_proof",
        )
        self.assertFalse(attestation["comparison_attestation_satisfied"])

    def test_self_asserted_rows_without_separate_proof_cannot_unlock(self) -> None:
        rows = result_rows(self.fixtures)
        packet = spine.build_spine(
            self.fixtures,
            result_packet(self.fixtures, rows),
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        local_integrity = packet["result_collection"]["local_integrity_validation"]
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])
        self.assertEqual(local_integrity["locally_consistent_run_claim_count"], 0)
        self.assertEqual(local_integrity["locally_consistent_result_count"], 0)
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertEqual(
            packet["study_design"]["model_execution_state"],
            "verifier_available_signed_bundle_not_supplied",
        )

    def test_missing_one_matched_result_fails_closed(self) -> None:
        rows = result_rows(self.fixtures)
        missing_assignment = rows.pop(0)
        packet, _ = build_verified_spine(self.fixtures, rows)
        readiness = packet["comparison_readiness"]
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertEqual(readiness["matched_case_counts_by_task_class"][missing_assignment["task_class"]], 19)
        self.assertFalse(readiness["cross_model_ranking_allowed"])
        self.assertEqual(readiness["review_only_blind_ranking_rows"], [])
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertFalse(packet["study_design"]["all_assignment_execution_proven"])
        self.assertFalse(packet["study_design"]["all_assignment_local_integrity_valid"])
        self.assertEqual(
            packet["result_collection"]["local_integrity_validation"]["local_integrity_state"],
            "collected_rows_local_integrity_complete",
        )
        self.assertEqual(
            packet["assignment_manifest"]["status"],
            "frozen_with_partial_or_invalid_pre_attestation_collection",
        )

    def test_one_locally_consistent_result_never_labels_manifest_attested_or_complete(self) -> None:
        rows = [result_rows(self.fixtures)[0]]
        packet, _ = build_verified_spine(self.fixtures, rows)
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertTrue(packet["study_design"]["all_result_rows_local_integrity_valid"])
        self.assertFalse(packet["study_design"]["all_assignment_execution_proven"])
        self.assertFalse(packet["study_design"]["all_assignment_local_integrity_valid"])
        self.assertEqual(
            packet["result_collection"]["local_integrity_validation"]["local_integrity_state"],
            "collected_rows_local_integrity_complete",
        )
        self.assertEqual(
            packet["assignment_manifest"]["status"],
            "frozen_with_partial_or_invalid_pre_attestation_collection",
        )
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_self_asserted_attestation_booleans_are_not_accepted_as_input(self) -> None:
        rows = [result_rows(self.fixtures)[0]]
        proof_index = build_proof_index(self.fixtures, rows)
        packet_input = result_packet(self.fixtures, rows, proof_index)
        packet_input.update({
            "trusted_execution_attestation_verified": True,
            "trusted_output_artifact_attestation_verified": True,
            "trusted_grader_attestation_verified": True,
        })
        packet = spine.build_spine(
            self.fixtures,
            packet_input,
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertTrue(
            any("result_packet_unknown_fields" in error for error in packet["validation"]["errors"])
        )
        readiness = packet["comparison_readiness"]
        self.assertFalse(readiness["trusted_execution_attestation_verified"])
        self.assertFalse(readiness["trusted_output_artifact_attestation_verified"])
        self.assertFalse(readiness["trusted_grader_attestation_verified"])
        self.assertFalse(readiness["cross_model_ranking_allowed"])

    def test_authority_violation_and_validator_regression_block_comparison(self) -> None:
        rows = result_rows(self.fixtures)
        rows[0]["authority_violation_count"] = 1
        rows[0]["authority_violation_codes"] = ["route_mutation"]
        rows[1]["validator_regression"] = True
        packet, _ = build_verified_spine(self.fixtures, rows)
        readiness = packet["comparison_readiness"]
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertEqual(readiness["authority_violation_count"], 1)
        self.assertEqual(readiness["validator_regression_count"], 1)
        self.assertFalse(readiness["cross_model_ranking_allowed"])

    def test_historical_missing_usage_stays_unavailable_and_never_invented(self) -> None:
        row = result_rows(self.fixtures)[0]
        row.update({
            "usage_status": "unavailable",
            "input_tokens": None,
            "cached_input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "missing_usage_classification": "historical_pre_token_stamping_unavailable",
        })
        coordinator, _ = spine.build_assignments(self.fixtures)
        proof_index = build_proof_index(self.fixtures, [row])
        packet = result_packet(self.fixtures, [row], proof_index)
        good = spine.validate_result_packet(
            packet,
            coordinator,
            self.fixtures["fixture_set_id"],
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            fixture_sha256=spine.fixture_digest(self.fixtures),
        )
        self.assertEqual(good["status"], "ok", good["errors"])

        row["input_tokens"] = 10
        bad = spine.validate_result_packet(
            packet,
            coordinator,
            self.fixtures["fixture_set_id"],
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            fixture_sha256=spine.fixture_digest(self.fixtures),
        )
        self.assertEqual(bad["status"], "blocked")
        self.assertTrue(any("historical_missing_usage_was_invented" in error for error in bad["errors"]))

    def test_raw_result_field_is_rejected(self) -> None:
        row = result_rows(self.fixtures)[0]
        proof_index = build_proof_index(self.fixtures, [row])
        row["response"] = "synthetic raw body that must never be stored"
        coordinator, _ = spine.build_assignments(self.fixtures)
        validation = spine.validate_result_packet(
            result_packet(self.fixtures, [row], proof_index),
            coordinator,
            self.fixtures["fixture_set_id"],
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            fixture_sha256=spine.fixture_digest(self.fixtures),
        )
        self.assertEqual(validation["status"], "blocked")
        self.assertTrue(any("forbidden_raw_field" in error for error in validation["errors"]))

    def test_scorer_result_claims_are_withheld_until_independent_attestation(self) -> None:
        rows = result_rows(self.fixtures)
        packet, _ = build_verified_spine(self.fixtures, rows)
        scorer_rows = packet["scorer_surface"]["result_rows"]
        self.assertEqual(scorer_rows, [])
        self.assertEqual(packet["scorer_surface"]["withheld_result_count"], 300)
        self.assertEqual(
            packet["scorer_surface"]["result_release_state"],
            "withheld_pending_independent_attestation",
        )
        self.assertFalse(packet["comparison_readiness"]["comparison_statistics_released"])

    def test_unverified_attribution_is_valid_collection_but_blocks_gate(self) -> None:
        rows = result_rows(self.fixtures)
        rows[0].update({
            "model_path": None,
            "model_identity_verified": False,
            "attribution_source": None,
            "attribution_eligible": False,
            "confidence_interval_eligible": False,
        })
        packet, _ = build_verified_spine(self.fixtures, rows)
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertLess(packet["comparison_readiness"]["attribution_classification_coverage"], 1.0)
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_self_asserted_confidence_eligibility_false_keeps_rows_out_of_statistics(self) -> None:
        rows = result_rows(self.fixtures)
        for row in rows:
            row["confidence_interval_eligible"] = False
        packet, _ = build_verified_spine(self.fixtures, rows)
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertEqual(
            set(packet["comparison_readiness"]["eligible_graded_output_counts_by_candidate"].values()),
            {0},
        )
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_result_tamper_after_proof_breaks_subject_and_blocks(self) -> None:
        rows = result_rows(self.fixtures)
        proof_index = build_proof_index(self.fixtures, rows)
        packet_input = result_packet(self.fixtures, rows, proof_index)
        rows[0]["grader_scores"]["overall"] = 0.01
        packet = spine.build_spine(
            self.fixtures,
            packet_input,
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertTrue(
            any("grader_proof_subject_mismatch" in error for error in packet["validation"]["errors"])
        )
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_unfrozen_rubric_cannot_unlock_even_with_consistent_proof(self) -> None:
        rows = result_rows(self.fixtures)
        rows[0]["rubric_id"] = "self-declared-rubric"
        rows[0]["rubric_sha256"] = spine.digest({"self_declared": True})
        packet, _ = build_verified_spine(self.fixtures, rows)
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertTrue(any("rubric_id_not_frozen" in error for error in packet["validation"]["errors"]))
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_self_declared_grader_trust_domain_invalidates_entire_proof_chain(self) -> None:
        rows = result_rows(self.fixtures)
        proof_index = build_proof_index(self.fixtures, rows)
        proof_index["producer_registry"][2]["trust_domain"] = "candidate_execution"
        packet = spine.build_spine(
            self.fixtures,
            result_packet(self.fixtures, rows, proof_index),
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertTrue(
            any("trust_domain_not_pinned_for_role" in error for error in packet["validation"]["errors"])
        )

    def test_unpinned_producer_identity_invalidates_entire_proof_chain(self) -> None:
        rows = result_rows(self.fixtures)
        proof_index = build_proof_index(self.fixtures, rows)
        proof_index["producer_registry"][0]["producer_id"] = "self-declared-run-harness"
        packet = spine.build_spine(
            self.fixtures,
            result_packet(self.fixtures, rows, proof_index),
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertTrue(
            any("producer_id_not_pinned_for_role" in error for error in packet["validation"]["errors"])
        )

    def test_orphan_proof_record_is_rejected_even_with_canonical_index_digest(self) -> None:
        all_rows = result_rows(self.fixtures)
        rows = [all_rows[0]]
        proof_index = build_proof_index(self.fixtures, rows)
        orphan = copy.deepcopy(proof_index["records"][0])
        orphan_assignment = all_rows[1]
        orphan.update({
            "proof_id": "orphan-run-proof",
            "assignment_id": orphan_assignment["assignment_id"],
            "case_id": orphan_assignment["case_id"],
            "blind_candidate_id": orphan_assignment["blind_candidate_id"],
            "subject_sha256": spine.proof_subject_digest(orphan_assignment, "run"),
        })
        orphan["record_sha256"] = spine.proof_record_digest(orphan)
        proof_index["records"].append(orphan)
        packet = spine.build_spine(
            self.fixtures,
            result_packet(self.fixtures, rows, proof_index),
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertTrue(
            any("proof_index_orphan_records" in error for error in packet["validation"]["errors"])
        )
        self.assertFalse(packet["study_design"]["model_execution_performed"])
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_grader_proof_preceding_output_is_rejected(self) -> None:
        rows = result_rows(self.fixtures)
        proof_index = build_proof_index(self.fixtures, rows)
        grader_record = next(record for record in proof_index["records"] if record["proof_type"] == "grader")
        grader_record["observed_at_utc"] = "2026-08-08T11:59:00Z"
        grader_record["record_sha256"] = spine.proof_record_digest(grader_record)
        rows[0]["grader_proof_sha256"] = grader_record["record_sha256"]
        packet = spine.build_spine(
            self.fixtures,
            result_packet(self.fixtures, rows, proof_index),
            proof_index=proof_index,
            proof_source_ref=PROOF_INDEX_REF,
            baseline_inputs={},
            generated_at_utc=FIXED_TIME,
        )
        self.assertEqual(packet["validation"]["status"], "blocked")
        self.assertTrue(
            any("grader_proof_precedes_output_proof" in error for error in packet["validation"]["errors"])
        )
        self.assertFalse(packet["comparison_readiness"]["cross_model_ranking_allowed"])

    def test_tampered_fixture_digest_blocks(self) -> None:
        tampered = copy.deepcopy(self.fixtures)
        tampered["task_classes"][0]["cases"][0]["difficulty"] = "easy"
        validation = spine.validate_fixtures(tampered)
        self.assertEqual(validation["status"], "blocked")
        self.assertIn("fixture_digest_mismatch", validation["errors"])

    def test_baseline_history_is_context_not_ranking_or_restamping_gate(self) -> None:
        baseline = {
            "model_quality_scorecard": {
                "status": "scaffold_active",
                "model_attribution": {
                    "instrumentation_working": True,
                    "recent_attribution_coverage": 0.9211,
                    "recent_attribution_window": {
                        "window_days": 30,
                        "applicable_rows": 76,
                        "attributed_rows": 70,
                    },
                    "attribution_applicable_rows": 1070,
                    "model_attributed_rows": 561,
                    "attribution_applicable_coverage": 0.5243,
                },
            },
            "token_attribution_bridge": {
                "status": "warning",
                "summary": {
                    "gap_resolution_status": "classified_unavailable_only",
                    "classified_runtime_gap_count": 497,
                    "unclassified_supported_runtime_gap_count": 0,
                    "implementation_token_event_count": 4,
                    "implementation_token_gap_count": 493,
                    "provider_run_join_ready": False,
                },
            },
        }
        context = spine.baseline_attribution_context(baseline)
        self.assertFalse(context["ranking_gate_input"])
        self.assertFalse(
            context["all_time_model_attribution"]["pre_instrumentation_debt_is_producer_stamping_blocker"]
        )
        self.assertTrue(context["usage_attribution"]["historical_gaps_classified_unavailable"])
        self.assertFalse(context["usage_attribution"]["provider_run_join_ready"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
