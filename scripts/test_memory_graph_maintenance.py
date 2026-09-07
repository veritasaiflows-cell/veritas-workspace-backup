#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import memory_graph_maintenance as maintenance


FRESH_GRAPH = {"status": "ok", "freshness": "fresh", "selected_path": "scripts/graphify-out/graph.json", "candidates": []}
STALE_GRAPH = {"status": "ok", "freshness": "stale", "selected_path": "scripts/graphify-out/graph.json", "candidates": []}
VALID_CACHE = {
    "status": "ok",
    "errors": [],
    "warnings": [],
    "source_count": 391,
    "chunk_count": 2348,
    "embedding_provider": "ollama",
    "embedding_model": "nomic-embed-text:latest",
}
HEALTHY_VECTOR_STORES = {"status": "ok", "checked": 9, "degraded_agents": [], "stores": []}


class MemoryGraphMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_out, self.old_scorecard_out = maintenance.OUT, maintenance.SCORECARD_OUT
        maintenance.OUT = self.root / "tmp" / "operational-graph-maintenance.json"
        maintenance.SCORECARD_OUT = self.root / "tmp" / "memory-vector-graph-weekly-scorecard.json"

    def tearDown(self) -> None:
        maintenance.OUT, maintenance.SCORECARD_OUT = self.old_out, self.old_scorecard_out
        self.tmp.cleanup()

    def test_fresh_gate_is_ok_and_writes_proof(self) -> None:
        with mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH):
            code, payload = maintenance.run_gate(write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "no_refresh_needed")
        self.assertEqual(json.loads(maintenance.OUT.read_text(encoding="utf-8"))["status"], "ok")

    def test_stale_gate_is_a_nonfailing_refresh_signal(self) -> None:
        with mock.patch.object(maintenance, "graph_state", return_value=STALE_GRAPH):
            code, payload = maintenance.run_gate(write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["action"], "refresh_due")

    def test_refresh_updates_only_when_graph_is_stale(self) -> None:
        with mock.patch.object(maintenance, "graph_state", side_effect=[STALE_GRAPH, FRESH_GRAPH]), mock.patch.object(
            maintenance.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="updated", stderr=""),
        ) as run:
            code, payload = maintenance.run_refresh(max_seconds=30, write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "incremental_scripts_graph_refresh")
        self.assertEqual(run.call_args.args[0], ["graphify", "update", "."])
        self.assertEqual(run.call_args.kwargs["cwd"], maintenance.GRAPH_ROOT)

    def test_code_only_manifest_ignores_noncode_entries_but_detects_python_drift(self) -> None:
        source_root = self.root / "scripts"
        graph_dir = source_root / "graphify-out"
        graph_dir.mkdir(parents=True)
        graph_path = graph_dir / "graph.json"
        graph_path.write_text("{}", encoding="utf-8")
        source = source_root / "worker.py"
        source.write_text("print('ok')\n", encoding="utf-8")
        fixture = source_root / "fixture.json"
        fixture.write_text("{}\n", encoding="utf-8")
        manifest = {
            "worker.py": {"mtime": source.stat().st_mtime},
            "fixture.json": {"mtime": fixture.stat().st_mtime},
        }
        (graph_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        state = maintenance.code_only_manifest_health(graph_path)
        self.assertEqual(state["coverage_status"], "fresh")
        (source_root / "new_worker.py").write_text("print('new')\n", encoding="utf-8")
        state = maintenance.code_only_manifest_health(graph_path)
        self.assertEqual(state["coverage_status"], "stale")
        self.assertEqual(state["new_sample"], ["new_worker.py"])

    def test_scorecard_reports_stale_graph_as_warning_with_vector_baseline(self) -> None:
        with mock.patch.object(maintenance.semantic_maintenance, "safe_validate", return_value=(VALID_CACHE, None)), mock.patch.object(
            maintenance.semantic_maintenance,
            "vector_store_integrity_state",
            return_value=HEALTHY_VECTOR_STORES,
        ), mock.patch.object(maintenance, "graph_state", return_value=STALE_GRAPH), mock.patch.object(
            maintenance,
            "embedding_dimension",
            return_value=768,
        ), mock.patch.object(
            maintenance,
            "latest_maintenance_summary",
            return_value={"status": "ok", "generated_at_utc": maintenance.utc_now()},
        ):
            code, payload = maintenance.run_scorecard(write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["vector_cache"]["embedding_dimension"], 768)
        self.assertIn("scripts_graph_refresh_due", payload["warnings"])

    def test_scorecard_reports_volatile_cache_drift_as_refresh_due_warning(self) -> None:
        stale_cache = {
            **VALID_CACHE,
            "status": "error",
            "errors": ["stale_source_hashes:1"],
            "stale_sources": [{"source_path": "tmp/finance-alert-os-digest.json", "reason": "sha256_mismatch"}],
        }
        with mock.patch.object(maintenance.semantic_maintenance, "safe_validate", return_value=(stale_cache, None)), mock.patch.object(
            maintenance.semantic_maintenance,
            "vector_store_integrity_state",
            return_value=HEALTHY_VECTOR_STORES,
        ), mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH), mock.patch.object(
            maintenance,
            "embedding_dimension",
            return_value=768,
        ), mock.patch.object(
            maintenance,
            "latest_maintenance_summary",
            return_value={"status": "ok", "generated_at_utc": maintenance.utc_now()},
        ):
            code, payload = maintenance.run_scorecard(write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["vector_cache"]["freshness"], "refresh_due")
        self.assertIn("primary_vector_cache_refresh_due", payload["warnings"])

    def test_scorecard_keeps_durable_cache_drift_as_an_error(self) -> None:
        stale_cache = {
            **VALID_CACHE,
            "status": "error",
            "errors": ["stale_source_hashes:1"],
            "stale_sources": [{"source_path": "memory/2026-08-31.md", "reason": "sha256_mismatch"}],
        }
        with mock.patch.object(maintenance.semantic_maintenance, "safe_validate", return_value=(stale_cache, None)), mock.patch.object(
            maintenance.semantic_maintenance,
            "vector_store_integrity_state",
            return_value=HEALTHY_VECTOR_STORES,
        ), mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH), mock.patch.object(
            maintenance,
            "embedding_dimension",
            return_value=768,
        ), mock.patch.object(
            maintenance,
            "latest_maintenance_summary",
            return_value={"status": "ok", "generated_at_utc": maintenance.utc_now()},
        ):
            code, payload = maintenance.run_scorecard(write=True)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertIn("primary_vector_cache_validation_not_ok", payload["errors"])

    def test_scorecard_keeps_transitive_drift_as_an_error(self) -> None:
        stale_cache = {
            **VALID_CACHE,
            "status": "error",
            "errors": ["stale_source_hashes:1"],
            "stale_sources": [{"source_path": "tmp/finance-alert-os-digest.json", "reason": "sha256_mismatch"}],
            "transitive_stale_paths": ["memory/2026-08-31.md"],
        }
        with mock.patch.object(maintenance.semantic_maintenance, "safe_validate", return_value=(stale_cache, None)), mock.patch.object(
            maintenance.semantic_maintenance,
            "vector_store_integrity_state",
            return_value=HEALTHY_VECTOR_STORES,
        ), mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH), mock.patch.object(
            maintenance,
            "embedding_dimension",
            return_value=768,
        ), mock.patch.object(
            maintenance,
            "latest_maintenance_summary",
            return_value={"status": "ok", "generated_at_utc": maintenance.utc_now()},
        ):
            code, payload = maintenance.run_scorecard(write=True)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertIn("primary_vector_cache_validation_not_ok", payload["errors"])


if __name__ == "__main__":
    unittest.main()
