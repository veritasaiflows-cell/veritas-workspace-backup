#!/usr/bin/env python3
"""Regression tests for the deterministic retrieval-quality scorecard."""
from __future__ import annotations

import copy
import unittest
import warnings

import retrieval_quality_scorecard as rq


warnings.filterwarnings("ignore", category=ResourceWarning)


class RetrievalQualityScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        warnings.simplefilter("ignore", ResourceWarning)
        cls.corpus = rq.load_fixture_corpus()
        cls.packet = rq.build_scorecard()

    def test_fixture_corpus_has_required_depth_and_contrast(self) -> None:
        fixtures = self.corpus["fixtures"]
        self.assertGreaterEqual(len(fixtures), 30)
        self.assertEqual(rq.validate_fixture_corpus(self.corpus), [])
        classes = {row["fixture_class"] for row in fixtures}
        self.assertEqual(classes, rq.REQUIRED_CLASSES)
        polarities = {row["polarity"] for row in fixtures}
        self.assertEqual(polarities, rq.KNOWN_POLARITIES)
        self.assertEqual(len({row["fixture_id"] for row in fixtures}), len(fixtures))
        self.assertEqual(len({row["question"] for row in fixtures}), len(fixtures))

    def test_live_scorecard_passes_all_current_contract_fixtures(self) -> None:
        summary = self.packet["summary"]
        self.assertEqual(self.packet["status"], "ok")
        self.assertEqual(self.packet["validation"]["status"], "ok")
        self.assertEqual(summary["fixtures"], 42)
        self.assertEqual(summary["passed"], summary["fixtures"])
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["partial"], 0)
        self.assertEqual(summary["average_score"], 1.0)

    def test_measurement_scope_does_not_claim_live_retrieval_quality(self) -> None:
        scope = self.packet["measurement_scope"]
        self.assertFalse(scope["live_index_queried"])
        self.assertEqual(scope["candidate_source"], "fixture_supplied_candidates_and_exact_contract_sources")
        for claim in {
            "live_vector_index_querying",
            "embedding_provider_quality",
            "paraphrase_retrieval_quality",
            "recall_mrr_or_ranking_quality",
            "retrieval_abstention_calibration",
        }:
            self.assertIn(claim, scope["does_not_measure"])
        self.assertEqual(scope["live_retrieval_evaluator"], "scripts/retrieval_live_eval.py")

    def test_negative_fixtures_fail_closed_or_select_the_safe_contrast(self) -> None:
        negative_specs = {
            row["fixture_id"]: row
            for row in self.corpus["fixtures"]
            if row["polarity"] == "negative"
        }
        results = {row["fixture_id"]: row for row in self.packet["fixtures"]}
        self.assertGreaterEqual(len(negative_specs), 10)
        blocked_count = 0
        safe_selection_count = 0
        for fixture_id, spec in negative_specs.items():
            with self.subTest(fixture_id=fixture_id):
                self.assertEqual(results[fixture_id]["status"], "pass")
                self.assertEqual(
                    results[fixture_id]["retrieval_outcome"],
                    spec["expected"]["retrieval_outcome"],
                )
                if results[fixture_id]["retrieval_outcome"] == "blocked":
                    blocked_count += 1
                else:
                    safe_selection_count += 1
                    self.assertTrue(results[fixture_id]["conflict"])
        self.assertGreaterEqual(blocked_count, 8)
        self.assertGreaterEqual(safe_selection_count, 2)

    def test_owner_and_sql_sources_outrank_generated_or_legacy_paths(self) -> None:
        results = {row["fixture_id"]: row for row in self.packet["fixtures"]}
        owner = results["rq_owner_execution_policy_over_dashboard"]
        self.assertEqual(owner["selected_source_pointer"], "03. Portfolio/Execution Board.md")
        self.assertTrue(owner["conflict"])
        retired = results["rq_sql_legacy_42_remains_retired"]
        self.assertEqual(retired["retrieval_outcome"], "blocked")
        self.assertEqual(retired["evidence"]["block_reason"], "legacy_path_retired")
        stop = results["rq_sql_rtx_invalidation_level"]
        self.assertEqual(stop["evidence"]["value"], 177.91)
        self.assertIn("review_only", stop["evidence"]["authority_class"])

    def test_missing_unparseable_archive_and_stale_sources_fail_closed(self) -> None:
        results = {row["fixture_id"]: row for row in self.packet["fixtures"]}
        for fixture_id, expected_reason in {
            "rq_missing_owner_source_blocks": "missing_source",
            "rq_markdown_cannot_masquerade_as_json": "unparseable_source",
            "rq_sqlite_cannot_masquerade_as_json": "unparseable_source",
        }.items():
            with self.subTest(fixture_id=fixture_id):
                row = results[fixture_id]
                self.assertEqual(row["retrieval_outcome"], "blocked")
                self.assertEqual(row["evidence"]["block_reason"], expected_reason)
        archive = results["rq_archive_startup_index_loses_to_current"]
        self.assertEqual(archive["evidence"]["rejected_reasons"]["archived_startup_index"], "archive_not_current")
        stale = results["rq_stale_generated_proof_loses_to_fresh_proof"]
        self.assertEqual(stale["evidence"]["rejected_reasons"]["stale_dashboard_validation"], "stale_source")
        assessments = {
            row["candidate_id"]: row["freshness_assessment"]
            for row in stale["evidence"]["candidates"]
        }
        self.assertEqual(assessments["fresh_capital_validation"]["status"], "fresh")
        self.assertEqual(assessments["fresh_capital_validation"]["age_hours"], 0.5)
        self.assertEqual(assessments["stale_dashboard_validation"]["status"], "stale")
        self.assertEqual(assessments["stale_dashboard_validation"]["age_hours"], 4.0)

    def test_timestamp_age_derivation_uses_ordering_age_and_inclusive_boundary(self) -> None:
        boundary = rq.derive_timestamp_freshness(
            "2026-08-08T11:00:00Z",
            "2026-08-08T12:00:00Z",
            1,
            mode="fixture_timestamp_age",
        )
        expired = rq.derive_timestamp_freshness(
            "2026-08-08T10:59:59Z",
            "2026-08-08T12:00:00Z",
            1,
            mode="fixture_timestamp_age",
        )
        future = rq.derive_timestamp_freshness(
            "2026-08-08T12:00:01Z",
            "2026-08-08T12:00:00Z",
            1,
            mode="fixture_timestamp_age",
        )
        self.assertEqual(boundary["status"], "fresh")
        self.assertEqual(boundary["age_hours"], 1.0)
        self.assertEqual(expired["status"], "stale")
        self.assertGreater(expired["age_hours"], expired["max_age_hours"])
        self.assertEqual(future["status"], "unknown")
        self.assertEqual(future["reason"], "generated_at_is_in_future")

    def test_legacy_freshness_label_cannot_override_timestamp_age(self) -> None:
        spec = copy.deepcopy(next(
            row for row in self.corpus["fixtures"]
            if row["fixture_id"] == "rq_stale_generated_proof_loses_to_fresh_proof"
        ))
        spec["candidates"][0]["freshness"] = "stale"
        spec["candidates"][1]["freshness"] = "fresh"
        result = rq.evaluate_fixture(spec, rq.EvaluationContext())
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.evidence["selected_candidate_id"], "fresh_capital_validation")
        del spec["candidates"][0]["freshness_evidence"]
        spec["candidates"][0]["freshness"] = "fresh"
        result = rq.evaluate_fixture(spec, rq.EvaluationContext())
        self.assertEqual(result.retrieval_outcome, "blocked")
        self.assertEqual(result.evidence["rejected_reasons"]["fresh_capital_validation"], "freshness_unknown")

    def test_declared_live_source_status_cannot_override_derived_age(self) -> None:
        payload = {
            "generated_at_utc": "2026-08-08T11:30:00Z",
            "max_age_hours": 1,
            "freshness_status": "stale",
        }
        contract = {
            "mode": "source_timestamp_age",
            "generated_at_pointer": "/generated_at_utc",
            "max_age_hours_pointer": "/max_age_hours",
            "declared_status_pointer": "/freshness_status",
        }
        context = rq.EvaluationContext(evaluation_time_utc="2026-08-08T12:00:00Z")
        assessment = rq.assess_json_freshness(payload, contract, context)
        self.assertEqual(assessment["status"], "fresh")
        self.assertEqual(assessment["age_hours"], 0.5)
        self.assertFalse(assessment["declared_status_matches_derived"])
        self.assertFalse(assessment["declared_status_is_authoritative"])

    def test_freshness_contract_separates_live_source_from_fixture_and_synthetic_proof(self) -> None:
        measurement = self.packet["measurement_contract"]["freshness"]
        proof = self.packet["summary"]["freshness_proof"]
        modes = proof["assessment_mode_counts"]
        self.assertFalse(measurement["declared_labels_are_authoritative"])
        self.assertFalse(measurement["label_only_cases_are_live_source_proof"])
        self.assertFalse(measurement["fixture_timestamp_age_is_live_source_proof"])
        self.assertTrue(measurement["source_timestamp_age_is_live_source_proof"])
        self.assertGreaterEqual(modes["fixture_timestamp_age"], 9)
        self.assertGreater(modes["synthetic_ordering_semantics"], 0)
        self.assertGreaterEqual(proof["live_source_timestamp_age_assessment_count"], 1)
        live = next(
            row for row in self.packet["fixtures"]
            if row["fixture_id"] == "rq_freshness_current_descriptor_accepted"
        )["evidence"]["freshness_assessment"]
        self.assertEqual(live["mode"], "source_timestamp_age")
        self.assertTrue(live["is_live_source_proof"])
        self.assertEqual(live["status"], "fresh")
        self.assertFalse(live["declared_status_is_authoritative"])

    def test_corpus_rejects_label_only_freshness_required_candidate(self) -> None:
        corpus = copy.deepcopy(self.corpus)
        spec = next(
            row for row in corpus["fixtures"]
            if row["fixture_id"] == "rq_freshness_stale_action_blocks"
        )
        candidate = spec["candidates"][0]
        del candidate["freshness_evidence"]
        candidate["freshness"] = "stale"
        errors = rq.validate_fixture_corpus(corpus)
        self.assertTrue(any(value.startswith("freshness_required_without_derived_evidence:") for value in errors))
        self.assertTrue(any(value.startswith("freshness_required_uses_legacy_label:") for value in errors))

    def test_vector_and_index_are_supplements_not_final_authority(self) -> None:
        results = {row["fixture_id"]: row for row in self.packet["fixtures"]}
        final = results["rq_vector_supplement_cannot_be_final_authority"]
        self.assertEqual(final["retrieval_outcome"], "blocked")
        self.assertTrue(final["source_open_required"])
        route = results["rq_vector_supplement_routes_to_exact_source"]
        self.assertEqual(route["retrieval_outcome"], "selected")
        self.assertTrue(route["source_open_required"])
        self.assertEqual(route["selected_source_pointer"], "tmp/vector-memory-ollama-full-index.json")
        self.assertFalse(self.packet["kg_vector_expansion_verdict"]["additional_infrastructure_justified_now"])

    def test_validation_detects_authority_widening(self) -> None:
        mutated = copy.deepcopy(self.packet)
        mutated["authority_boundary"]["apply_allowed"] = True
        validation = rq.validate_scorecard(mutated)
        self.assertEqual(validation["status"], "blocked")
        self.assertIn("authority_boundary_mismatch:apply_allowed", validation["errors"])

    def test_markdown_renders_contract_and_fixture_ids(self) -> None:
        markdown = rq.render_markdown(self.packet)
        self.assertIn("# Retrieval Authority and Source-Selection Contract Scorecard", markdown)
        self.assertIn("rq_sql_production_answer_empty_is_valid", markdown)
        self.assertIn("does not create canon", markdown.lower())
        self.assertIn("not live-source freshness proof", markdown.lower())
        self.assertIn("does not", markdown.lower())
        self.assertIn("live vector index", markdown.lower())


if __name__ == "__main__":
    unittest.main()
