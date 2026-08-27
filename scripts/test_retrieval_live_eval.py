#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import retrieval_live_eval as rle  # noqa: E402
import vector_memory_index as vmi  # noqa: E402


class RetrievalLiveEvalTests(unittest.TestCase):
    def make_inputs(self, root: Path, *, reviewed: bool = True) -> tuple[Path, Path]:
        (root / "wiki").mkdir(parents=True, exist_ok=True)
        (root / "data" / "evals").mkdir(parents=True, exist_ok=True)
        alpha = root / "wiki" / "alpha.md"
        beta = root / "wiki" / "beta.md"
        alpha.write_text(
            "# Alpha route\n"
            "A copper falcon routes telemetry into the review queue.\n"
            "Only a signed review packet may promote the recommendation.\n"
            "The underlying model weights are never rewritten.\n",
            encoding="utf-8",
        )
        beta.write_text(
            "# Beta route\n"
            "A copper budget tracks routine API usage.\n"
            "Telemetry is reported but no recommendation is promoted.\n"
            "This page is a lexical distractor.\n",
            encoding="utf-8",
        )
        sources = [
            {"path": "wiki/alpha.md", "sha256": hashlib.sha256(alpha.read_bytes()).hexdigest()},
            {"path": "wiki/beta.md", "sha256": hashlib.sha256(beta.read_bytes()).hexdigest()},
        ]
        manifest = rle.manifest_hash(sources)
        registry = {
            "schema": "veritas.retrieval_live_source_registry.v1",
            "status": "frozen_draft_review_required",
            "source_manifest_sha256": manifest,
            "chunking": {"lines_per_chunk": 4, "overlap": 0, "max_chars": 2000},
            "providers": {
                "hash": {"embedding_provider": "hash", "embedding_model": "hashing-vector-v0"},
                "semantic": {"embedding_provider": "ollama", "embedding_model": "test-embed:latest"},
                "fts_only": {"source_db": "hash", "ranking": "raw SQLite FTS5 bm25 ascending"},
            },
            "sources": sources,
        }
        registry_path = root / "data" / "evals" / "registry.json"
        registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        gold = {
            "schema": "veritas.retrieval_live_gold.v1",
            "status": "draft_review_required",
            "source_registry": "data/evals/registry.json",
            "source_manifest_sha256": manifest,
            "max_k": 5,
            "measurement_contract": {
                "absent_posture": "abstention_uncalibrated",
                "promotion_thresholds_defined": False,
            },
            "human_review": {
                "status": "reviewed" if reviewed else "required_before_trusted_baseline",
                "sole_relevance_review_complete": reviewed,
            },
            "fixtures": [
                {
                    "fixture_id": "exact",
                    "fixture_class": "exact",
                    "query": "A copper falcon routes telemetry into the review queue.",
                    "relevant_passages": [{"source_path": "wiki/alpha.md", "start_line": 2, "end_line": 2}],
                    "distractor_passages": [],
                    "absence_certified": False,
                },
                {
                    "fixture_id": "paraphrase",
                    "fixture_class": "paraphrase",
                    "query": "Where is monitoring information sent into a human decision list?",
                    "relevant_passages": [{"source_path": "wiki/alpha.md", "start_line": 2, "end_line": 2}],
                    "distractor_passages": [],
                    "absence_certified": False,
                },
                {
                    "fixture_id": "distractor",
                    "fixture_class": "distractor",
                    "query": "Which page permits recommendation promotion only with a signed review packet?",
                    "relevant_passages": [{"source_path": "wiki/alpha.md", "start_line": 3, "end_line": 3}],
                    "distractor_passages": [{"source_path": "wiki/beta.md", "start_line": 3, "end_line": 3}],
                    "absence_certified": False,
                },
                {
                    "fixture_id": "absent",
                    "fixture_class": "absent",
                    "query": "What Kubernetes disruption budget is approved?",
                    "relevant_passages": [],
                    "distractor_passages": [],
                    "absence_certified": True,
                },
            ],
        }
        gold_path = root / "data" / "evals" / "gold.json"
        gold_path.write_text(json.dumps(gold, indent=2) + "\n", encoding="utf-8")
        return registry_path, gold_path

    def artifact_binding(self, registry_path: Path, gold_path: Path) -> dict[str, str]:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        return {
            "gold_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
            "source_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "source_manifest_sha256": registry["source_manifest_sha256"],
        }

    def make_label_audit(self, root: Path, registry_path: Path, gold_path: Path) -> Path:
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        artifact = {
            "schema": rle.AUDIT_SCHEMA,
            "status": "complete",
            "reviewer_type": "machine",
            **self.artifact_binding(registry_path, gold_path),
            "reviews": [
                {
                    "fixture_id": fixture["fixture_id"],
                    "query_sha256": rle.query_sha256(fixture["query"]),
                    "decision": "confirmed",
                }
                for fixture in gold["fixtures"]
            ],
        }
        path = root / "data" / "evals" / "label-audit.json"
        path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        return path

    def make_sealed_calibration(self, root: Path, registry_path: Path, gold_path: Path) -> Path:
        artifact = {
            "schema": rle.CALIBRATION_SCHEMA,
            "status": "sealed_unrun_review_only",
            "sealed": True,
            "execution_status": "unrun",
            "review_only": True,
            **self.artifact_binding(registry_path, gold_path),
            "cases": [
                {
                    "calibration_id": "cal_answer_alpha_weights",
                    "case_type": "answer",
                    "query": "Which source says the model weights remain unchanged?",
                    "relevant_passages": [{"source_path": "wiki/alpha.md", "start_line": 4, "end_line": 4}],
                },
                {
                    "calibration_id": "cal_answer_beta_budget",
                    "case_type": "answer",
                    "query": "Where is routine API usage tracked by a copper budget?",
                    "relevant_passages": [{"source_path": "wiki/beta.md", "start_line": 2, "end_line": 2}],
                },
                {
                    "calibration_id": "cal_abstain_moonbase",
                    "case_type": "abstain",
                    "query": "What lunar base staffing policy applies?",
                    "relevant_passages": [],
                    "absence_certified": True,
                },
                {
                    "calibration_id": "cal_abstain_humidity",
                    "case_type": "abstain",
                    "query": "What humidity threshold triggers a warehouse alarm?",
                    "relevant_passages": [],
                    "absence_certified": True,
                },
            ],
        }
        path = root / "data" / "evals" / "sealed-calibration.json"
        path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        return path

    def build_hash(self, root: Path, registry_path: Path, name: str = "hash") -> Path:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        db = root / "tmp" / f"{name}.sqlite"
        vmi.build_index(
            root=root,
            db_path=db,
            out_path=root / "tmp" / f"{name}.json",
            patterns=[row["path"] for row in registry["sources"]],
            provider="hash",
            model="hashing-vector-v0",
            ollama_url="http://127.0.0.1:1",
            timeout=0.1,
            batch_size=8,
            lines_per_chunk=4,
            overlap=0,
            max_chars=2000,
            source_profile="full",
        )
        return db

    def test_validate_inputs_accepts_frozen_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, gold_path = self.make_inputs(root)
            _, _, validation = rle.validate_inputs(root=root, registry_path=registry_path, gold_path=gold_path)
            self.assertEqual(validation["status"], "ok")
            self.assertEqual(validation["fixture_class_counts"], {"exact": 1, "paraphrase": 1, "distractor": 1, "absent": 1})

    def test_validate_inputs_fails_closed_on_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, gold_path = self.make_inputs(root)
            (root / "wiki" / "alpha.md").write_text("changed\n", encoding="utf-8")
            _, _, validation = rle.validate_inputs(root=root, registry_path=registry_path, gold_path=gold_path)
            self.assertEqual(validation["status"], "error")
            self.assertIn("source_hash_mismatch:wiki/alpha.md", validation["errors"])

    def test_independent_label_audit_requires_exact_hash_and_full_unique_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, gold_path = self.make_inputs(root)
            audit_path = self.make_label_audit(root, registry_path, gold_path)
            accepted = rle.validate_independent_label_audit(
                root=root,
                audit_path=audit_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(accepted["status"], "ok")
            self.assertEqual(accepted["derived_status"], "confirmed")
            self.assertTrue(accepted["coverage"]["full_unique_coverage"])
            self.assertFalse(accepted["human_review_satisfied"])

            artifact = json.loads(audit_path.read_text(encoding="utf-8"))
            artifact["gold_sha256"] = "wrong"
            audit_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            hash_mismatch = rle.validate_independent_label_audit(
                root=root,
                audit_path=audit_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(hash_mismatch["status"], "error")
            self.assertIn("label_audit_gold_sha256_mismatch", hash_mismatch["errors"])

            artifact["gold_sha256"] = self.artifact_binding(registry_path, gold_path)["gold_sha256"]
            artifact["reviews"] = artifact["reviews"][:-1]
            audit_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            coverage_mismatch = rle.validate_independent_label_audit(
                root=root,
                audit_path=audit_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(coverage_mismatch["status"], "error")
            self.assertIn("label_audit_fixture_coverage_missing:absent", coverage_mismatch["errors"])

    def test_sealed_calibration_rejects_gold_overlap_nonsealed_and_imbalance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, gold_path = self.make_inputs(root)
            calibration_path = self.make_sealed_calibration(root, registry_path, gold_path)
            accepted = rle.validate_sealed_abstention_calibration(
                root=root,
                calibration_path=calibration_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(accepted["status"], "ok")
            self.assertEqual(accepted["case_counts"], {"answer": 2, "abstain": 2})
            self.assertFalse(accepted["execution_semantics"]["included_in_provider_metrics"])

            artifact = json.loads(calibration_path.read_text(encoding="utf-8"))
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            artifact["cases"][0]["calibration_id"] = gold["fixtures"][0]["fixture_id"]
            artifact["cases"][1]["query"] = gold["fixtures"][1]["query"].upper()
            calibration_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            id_and_query_overlap = rle.validate_sealed_abstention_calibration(
                root=root,
                calibration_path=calibration_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(id_and_query_overlap["status"], "error")
            self.assertIn(
                "abstention_calibration_id_overlaps_gold_fixture:exact",
                id_and_query_overlap["errors"],
            )
            self.assertIn(
                "abstention_calibration_query_overlaps_gold:cal_answer_beta_budget",
                id_and_query_overlap["errors"],
            )

            artifact = json.loads(self.make_sealed_calibration(root, registry_path, gold_path).read_text(encoding="utf-8"))
            artifact["cases"][0]["relevant_passages"] = [
                {"source_path": "wiki/alpha.md", "start_line": 2, "end_line": 2}
            ]
            calibration_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            overlap = rle.validate_sealed_abstention_calibration(
                root=root,
                calibration_path=calibration_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(overlap["status"], "error")
            self.assertIn(
                "abstention_calibration_answer_range_overlaps_gold:cal_answer_alpha_weights:wiki/alpha.md",
                overlap["errors"],
            )

            artifact = json.loads(self.make_sealed_calibration(root, registry_path, gold_path).read_text(encoding="utf-8"))
            artifact["status"] = "draft"
            artifact["sealed"] = False
            artifact["cases"] = artifact["cases"][:-1]
            calibration_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
            invalid_state = rle.validate_sealed_abstention_calibration(
                root=root,
                calibration_path=calibration_path,
                registry_path=registry_path,
                gold_path=gold_path,
            )
            self.assertEqual(invalid_state["status"], "error")
            self.assertIn("abstention_calibration_status_not_sealed_unrun_review_only", invalid_state["errors"])
            self.assertIn("abstention_calibration_not_sealed", invalid_state["errors"])
            self.assertIn("abstention_calibration_case_balance_invalid", invalid_state["errors"])

    def test_score_fixture_computes_recall_mrr_and_distractor_error(self) -> None:
        fixture = {
            "fixture_id": "x",
            "fixture_class": "distractor",
            "relevant_passages": [{"source_path": "right.md", "start_line": 10, "end_line": 12}],
            "distractor_passages": [{"source_path": "wrong.md", "start_line": 1, "end_line": 2}],
        }
        results = [
            {"source_path": "wrong.md", "start_line": 1, "end_line": 2, "score": 0.9},
            {"source_path": "right.md", "start_line": 8, "end_line": 15, "score": 0.8},
        ]
        row = rle.score_fixture(
            fixture,
            results=results,
            diagnostics={"status": "ok"},
            max_k=5,
            ranking_mode="semantic_fts",
        )
        self.assertEqual(row["metrics"]["recall_at_1"], 0.0)
        self.assertEqual(row["metrics"]["recall_at_3"], 1.0)
        self.assertEqual(row["metrics"]["mrr"], 0.5)
        self.assertTrue(row["metrics"]["passage_overlap_hit"])
        self.assertTrue(row["metrics"]["named_distractor_error"])

    def test_absent_fixture_remains_uncalibrated(self) -> None:
        fixture = {"fixture_id": "abs", "fixture_class": "absent", "relevant_passages": []}
        row = rle.score_fixture(
            fixture,
            results=[{"source_path": "near.md", "score": 0.8}, {"source_path": "other.md", "score": 0.7}],
            diagnostics={"status": "ok", "fts_candidate_count": 2},
            max_k=5,
            ranking_mode="semantic_fts",
        )
        self.assertEqual(row["measurement_status"], "abstention_uncalibrated")
        self.assertIsNone(row["absent_diagnostics"]["calibrated_pass_fail"])
        self.assertAlmostEqual(row["absent_diagnostics"]["runner_up_margin"], 0.1)

    def test_fts_only_queries_real_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path, _ = self.make_inputs(root)
            db = self.build_hash(root, registry_path)
            results, diagnostics = rle.search_fts_only(db_path=db, query="signed review packet", max_k=5)
            self.assertEqual(diagnostics["status"], "ok")
            self.assertGreater(diagnostics["fts_candidate_count"], 0)
            self.assertEqual(results[0]["source_path"], "wiki/alpha.md")

    def test_search_hybrid_rejects_query_fallback_warning(self) -> None:
        fake = {
            "status": "ok",
            "freshness": {"status": "ok"},
            "warnings": ["ollama_query_embedding_unavailable_fell_back_to_hash"],
            "fts_candidate_count": 1,
            "results": [{"source_path": "wiki/alpha.md", "embedding_provider": "ollama"}],
        }
        with mock.patch.object(vmi, "search_index", return_value=fake):
            _, diagnostics = rle.search_hybrid(
                root=Path("."),
                db_path=Path("unused.sqlite"),
                query="query",
                max_k=5,
                expected_provider="ollama",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
            )
        self.assertEqual(diagnostics["status"], "error")
        self.assertIn("query_provider_fallback_detected", diagnostics["errors"])

    def test_provider_snapshot_detects_substitution(self) -> None:
        snapshot = {
            "meta": {"embedding_provider": "hash", "embedding_model": "hashing-vector-v0"},
            "source_manifest_sha256": "m",
            "source_count": 1,
            "chunk_count": 1,
            "fts_count": 1,
            "provider_rows": [{"embedding_provider": "hash", "embedding_model": "hashing-vector-v0"}],
        }
        errors = rle.provider_snapshot_errors(
            snapshot,
            expected_provider="ollama",
            expected_model="semantic",
            expected_manifest="m",
        )
        self.assertTrue(any(item.startswith("embedding_provider_mismatch") for item in errors))

    def test_compare_providers_reports_no_paraphrase_discrimination(self) -> None:
        summary = {
            "overall_positive": {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0},
            "by_class": {
                name: {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0}
                for name in ("exact", "paraphrase", "distractor")
            },
        }
        runs = {name: {"summary": summary} for name in ("hash_fts", "semantic_fts", "fts_only")}
        result = rle.compare_providers(runs)
        self.assertFalse(result["paraphrase_provider_discrimination_observed"])
        self.assertIn("semantic_and_hash_within_noise_on_paraphrase_fixtures", result["findings"])

    def test_history_is_append_only_and_regression_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            rle.append_history(path, {"row": 1})
            rle.append_history(path, {"row": 2})
            self.assertEqual(rle.load_history(path), [{"row": 1}, {"row": 2}])

        report = {
            "inputs": {"source_manifest_sha256": "m", "gold_sha256": "g"},
            "index_contract": {"chunk_snapshot_sha256": "c"},
            "providers": {
                "hash_fts": {
                    "embedding_model": "h",
                    "resolved_model_digest": "hd",
                    "evaluation": {"summary": {"overall_positive": {"mrr": 0.5, "recall_at_5": 0.8}}},
                },
                "semantic_fts": {
                    "embedding_model": "s",
                    "resolved_model_digest": "sd",
                    "evaluation": {"summary": {"overall_positive": {"mrr": 0.5, "recall_at_5": 0.8}}},
                },
            },
        }
        prior = {
            "compatibility_key": rle.compatibility_key(report),
            "recorded_at_utc": "earlier",
            "metrics": {
                "hash_fts": {"overall_positive": {"mrr": 0.8, "recall_at_5": 1.0}},
                "semantic_fts": {"overall_positive": {"mrr": 0.8, "recall_at_5": 1.0}},
            },
        }
        regression = rle.compatible_regression(report, [prior])
        self.assertEqual(regression["status"], "regression")
        self.assertGreaterEqual(len(regression["regressions"]), 2)

    def test_sealed_calibration_is_excluded_from_provider_metrics_compatibility_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            registry_path, gold_path = self.make_inputs(root)
            audit_path = self.make_label_audit(root, registry_path, gold_path)
            calibration_path = self.make_sealed_calibration(root, registry_path, gold_path)

            def fake_batch(texts: list[str], *, model: str, url: str, timeout: float) -> list[list[float]]:
                return [vmi.hash_embedding("semantic-prefix " + text) for text in texts]

            def fake_one(text: str, *, model: str, url: str, timeout: float) -> list[float]:
                return vmi.hash_embedding("semantic-prefix " + text)

            with (
                mock.patch.object(rle, "resolve_ollama_digest", return_value="digest-test"),
                mock.patch.object(vmi, "ollama_embed_batch", side_effect=fake_batch),
                mock.patch.object(vmi, "ollama_embed_one", side_effect=fake_one),
            ):
                report = rle.run_evaluation(
                    root=root,
                    registry_path=registry_path,
                    gold_path=gold_path,
                    hash_db=root / "tmp" / "hash.sqlite",
                    hash_index=root / "tmp" / "hash.json",
                    semantic_db=root / "tmp" / "semantic.sqlite",
                    semantic_index=root / "tmp" / "semantic.json",
                    mutation_db=root / "tmp" / "mutation.sqlite",
                    ollama_url="http://127.0.0.1:1",
                    timeout=0.1,
                    batch_size=8,
                    history=[],
                    label_audit_path=audit_path,
                    abstention_calibration_path=calibration_path,
                )
            self.assertEqual(report["validation"]["status"], "ok")
            self.assertFalse(report["authority_boundary"]["provider_promotion_allowed"])
            supplemental = report["supplemental_artifacts"]
            self.assertEqual(supplemental["independent_label_audit"]["status"], "ok")
            self.assertEqual(supplemental["sealed_abstention_calibration"]["status"], "ok")
            for provider in report["providers"].values():
                self.assertEqual(len(provider["evaluation"]["fixtures"]), 4)
            without_supplemental = json.loads(json.dumps(report))
            without_supplemental.pop("supplemental_artifacts")
            self.assertEqual(rle.compatibility_key(report), rle.compatibility_key(without_supplemental))
            history = rle.history_entry(report)
            self.assertNotIn("supplemental_artifacts", history)
            self.assertEqual(set(history["metrics"]), {"hash_fts", "semantic_fts", "fts_only"})
            self.assertIn("not human review", rle.render_markdown(report))

    def test_end_to_end_uses_isolated_identical_indexes_and_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            registry_path, gold_path = self.make_inputs(root, reviewed=False)

            def fake_batch(texts: list[str], *, model: str, url: str, timeout: float) -> list[list[float]]:
                return [vmi.hash_embedding("semantic-prefix " + text) for text in texts]

            def fake_one(text: str, *, model: str, url: str, timeout: float) -> list[float]:
                return vmi.hash_embedding("semantic-prefix " + text)

            with (
                mock.patch.object(rle, "resolve_ollama_digest", return_value="digest-test"),
                mock.patch.object(vmi, "ollama_embed_batch", side_effect=fake_batch),
                mock.patch.object(vmi, "ollama_embed_one", side_effect=fake_one),
            ):
                report = rle.run_evaluation(
                    root=root,
                    registry_path=registry_path,
                    gold_path=gold_path,
                    hash_db=root / "tmp" / "hash.sqlite",
                    hash_index=root / "tmp" / "hash.json",
                    semantic_db=root / "tmp" / "semantic.sqlite",
                    semantic_index=root / "tmp" / "semantic.json",
                    mutation_db=root / "tmp" / "mutation.sqlite",
                    ollama_url="http://127.0.0.1:1",
                    timeout=0.1,
                    batch_size=8,
                    history=[],
                )
            self.assertEqual(report["validation"]["status"], "ok")
            self.assertEqual(report["status"], "draft_review_required")
            self.assertTrue(report["index_contract"]["identical_frozen_chunks"])
            self.assertTrue(report["index_contract"]["protected_default_index_untouched"])
            self.assertEqual(report["mutation_self_test"]["status"], "ok")
            self.assertFalse(report["authority_boundary"]["provider_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
