#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import semantic_memory_maintenance as maintenance


def stale_alert_validation() -> dict:
    return {
        "status": "error",
        "errors": ["stale_source_hashes:1"],
        "stale_sources": [
            {
                "source_path": "tmp/finance-alert-os-digest.json",
                "reason": "sha256_mismatch",
            }
        ],
        "transitive_stale_paths": [],
        "warnings": [],
    }


class SemanticMemoryMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_root, self.old_db, self.old_out, self.old_runtime_dist = (
            maintenance.ROOT,
            maintenance.DB,
            maintenance.OUT,
            maintenance.RUNTIME_DIST_DIR,
        )
        maintenance.ROOT = self.root
        maintenance.DB = self.root / "tmp" / "vector-memory.sqlite"
        maintenance.OUT = self.root / "tmp" / "semantic-memory-maintenance.json"
        maintenance.RUNTIME_DIST_DIR = self.root / "dist"
        maintenance.RUNTIME_DIST_DIR.mkdir()
        self.runtime_tools_source = maintenance.RUNTIME_DIST_DIR / "tools-test-hash.js"
        self.runtime_tools_source.write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { "
            "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS memory corpus unavailable in corpus=all "
            "MEMORY_SEARCH_SKIP_SESSION_VISIBILITY_FOR_NON_SESSION_HITS "
            'if (!params.hits.some((hit) => hit.source === "sessions")) return params.hits; '
            "const visibility = resolveEffectiveSessionToolsVisibility({}); "
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        self.runtime_loader = maintenance.RUNTIME_DIST_DIR / "extensions" / "memory-core" / "index.js"
        self.runtime_loader.parent.mkdir(parents=True)
        self.runtime_loader.write_text(
            'const loadMemoryToolsModule = createLazyRuntimeModule(() => import("../../tools-test-hash.js"));',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        maintenance.ROOT, maintenance.DB, maintenance.OUT, maintenance.RUNTIME_DIST_DIR = (
            self.old_root,
            self.old_db,
            self.old_out,
            self.old_runtime_dist,
        )
        self.tmp.cleanup()

    def test_alert_proof_staleness_rebuilds_without_exception(self) -> None:
        with mock.patch.object(
            maintenance,
            "safe_validate",
            side_effect=[(stale_alert_validation(), None), ({"status": "ok", "errors": [], "warnings": []}, None)],
        ), mock.patch.object(
            maintenance.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0),
        ) as run:
            code, payload = maintenance.run_maintenance(max_seconds=30, batch_size=8, write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "rebuild_registered_sources")
        run.assert_called_once()
        self.assertEqual(json.loads(maintenance.OUT.read_text(encoding="utf-8"))["status"], "ok")

    def test_unexpected_drift_rebuilds_and_returns_ok(self) -> None:
        stale = {"status": "error", "errors": ["stale_source_hashes:1"], "stale_sources": [{"source_path": "memory/2026-08-20.md"}], "warnings": []}
        with mock.patch.object(maintenance, "safe_validate", side_effect=[(stale, None), ({"status": "ok", "errors": [], "warnings": []}, None)]), mock.patch.object(
            maintenance.subprocess, "run", return_value=subprocess.CompletedProcess(args=[], returncode=0)
        ) as run:
            code, payload = maintenance.run_maintenance(max_seconds=30, batch_size=8, write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "rebuild_registered_sources")
        self.assertIn("scripts\\vector_memory_index.py", run.call_args.args[0])

    def test_direct_finance_summary_hash_drift_rebuilds(self) -> None:
        stale = {
            "status": "error",
            "errors": ["stale_source_hashes:1"],
            "stale_sources": [
                {
                    "source_path": "tmp/finance-vector-retrieval-summary.json",
                    "reason": "sha256_mismatch",
                }
            ],
            "transitive_stale_paths": [],
            "warnings": [],
        }
        with mock.patch.object(
            maintenance,
            "safe_validate",
            side_effect=[(stale, None), ({"status": "ok", "errors": [], "warnings": []}, None)],
        ), mock.patch.object(
            maintenance.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0),
        ) as run:
            code, payload = maintenance.run_maintenance(max_seconds=30, batch_size=8, write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "rebuild_registered_sources")
        run.assert_called_once()

    def test_volatile_source_drift_gets_one_bounded_retry(self) -> None:
        with mock.patch.object(
            maintenance,
            "safe_validate",
            side_effect=[
                (stale_alert_validation(), None),
                (stale_alert_validation(), None),
                ({"status": "ok", "errors": [], "warnings": []}, None),
            ],
        ), mock.patch.object(
            maintenance.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0),
        ) as run:
            code, payload = maintenance.run_maintenance(max_seconds=30, batch_size=8, write=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(len(payload["rebuild_attempts"]), 2)
        self.assertEqual(payload["rebuild_attempts"][0]["post_validation"]["status"], "error")
        self.assertIn("post_rebuild_volatile_source_drift_retrying", payload["notes"])

    def test_timeout_is_an_error_and_is_written(self) -> None:
        stale = {"status": "error", "errors": ["missing_db"], "stale_sources": [], "warnings": []}
        with mock.patch.object(maintenance, "safe_validate", return_value=(stale, None)), mock.patch.object(
            maintenance.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="index", timeout=30)
        ):
            code, payload = maintenance.run_maintenance(max_seconds=30, batch_size=8, write=True)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertIn("rebuild_timeout", payload["validation"]["errors"])

    def test_missing_runtime_patch_is_attention(self) -> None:
        self.runtime_tools_source.write_text(
            "function createMemorySearchTool() {} unpatched runtime",
            encoding="utf-8",
        )
        with mock.patch.object(maintenance, "safe_validate", return_value=({"status": "ok", "errors": [], "warnings": []}, None)):
            code, payload = maintenance.run_maintenance(max_seconds=30, batch_size=8, write=True)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "attention")
        self.assertEqual(payload["runtime_patch"]["reason"], "approved_runtime_patch_missing_or_replaced")

    def test_runtime_patch_discovery_uses_behavior_marker_not_chunk_hash(self) -> None:
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "ok")
        self.assertEqual(Path(state["path"]), self.runtime_tools_source)
        self.assertTrue(state["non_session_fast_path_guard_before_visibility"])

    def test_missing_non_session_fast_path_marker_is_attention(self) -> None:
        self.runtime_tools_source.write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { "
            "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS memory corpus unavailable in corpus=all "
            'if (!params.hits.some((hit) => hit.source === "sessions")) return params.hits; '
            "const visibility = resolveEffectiveSessionToolsVisibility({}); "
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "attention")
        self.assertEqual(
            state["missing_markers"],
            ["MEMORY_SEARCH_SKIP_SESSION_VISIBILITY_FOR_NON_SESSION_HITS"],
        )

    def test_non_session_fast_path_guard_must_precede_visibility_setup(self) -> None:
        self.runtime_tools_source.write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { "
            "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS memory corpus unavailable in corpus=all "
            "MEMORY_SEARCH_SKIP_SESSION_VISIBILITY_FOR_NON_SESSION_HITS "
            "const visibility = resolveEffectiveSessionToolsVisibility({}); "
            'if (!params.hits.some((hit) => hit.source === "sessions")) return params.hits; '
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "attention")
        self.assertFalse(state["non_session_fast_path_guard_before_visibility"])
        self.assertEqual(state["missing_markers"], ["MEMORY_SEARCH_NON_SESSION_FAST_PATH_GUARD"])

    def test_stale_patched_chunk_does_not_mask_active_unpatched_chunk(self) -> None:
        active_source = maintenance.RUNTIME_DIST_DIR / "tools-active-hash.js"
        active_source.write_text(
            "function createMemorySearchTool() {} unpatched active runtime",
            encoding="utf-8",
        )
        self.runtime_loader.write_text(
            'const loadMemoryToolsModule = createLazyRuntimeModule(() => import("../../tools-active-hash.js"));',
            encoding="utf-8",
        )
        (maintenance.RUNTIME_DIST_DIR / "tools-stale-patched-hash.js").write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { "
            "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS memory corpus unavailable in corpus=all "
            "MEMORY_SEARCH_SKIP_SESSION_VISIBILITY_FOR_NON_SESSION_HITS "
            'if (!params.hits.some((hit) => hit.source === "sessions")) return params.hits; '
            "const visibility = resolveEffectiveSessionToolsVisibility({}); "
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "attention")
        self.assertEqual(state["reason"], "approved_runtime_patch_missing_or_replaced")
        self.assertEqual(Path(state["path"]), active_source)

    def test_missing_runtime_memory_tools_source_is_attention(self) -> None:
        self.runtime_tools_source.unlink()
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "attention")
        self.assertEqual(state["reason"], "runtime_tools_source_missing_or_unreadable")


if __name__ == "__main__":
    unittest.main()
