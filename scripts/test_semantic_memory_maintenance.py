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
        # Exit reflects primary-cache health; the detection-only overlay stays
        # visible as payload attention for review routing.
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "attention")
        self.assertEqual(payload["runtime_patch"]["reason"], "approved_runtime_patch_missing_or_replaced")

    def test_runtime_patch_discovery_uses_behavior_marker_not_chunk_hash(self) -> None:
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "ok")
        self.assertEqual(Path(state["path"]), self.runtime_tools_source)
        self.assertTrue(state["non_session_fast_path_guard_before_visibility"])

    def test_fast_path_guard_shape_verifies_without_legacy_label(self) -> None:
        # Behavior over marker strings: the legacy SKIP label is absent but the
        # guard still precedes visibility setup, so the behavior verifies.
        self.runtime_tools_source.write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { "
            "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS memory corpus unavailable in corpus=all "
            'if (!params.hits.some((hit) => hit.source === "sessions")) return params.hits; '
            "const visibility = resolveEffectiveSessionToolsVisibility({}); "
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["behavior_proof"]["non_session_fast_path_guard"], "upstream_native")

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

    def write_upstream_native_layout(self, *, guard_before_visibility: bool = True) -> Path:
        """Stage a 2026.9.2-style split-chunk runtime: upstream markers in the
        tools chunk, non-session fast-path guard in the visibility chunk."""
        tools_source = maintenance.RUNTIME_DIST_DIR / "tools-upstream-hash.js"
        tools_source.write_text(
            'import { t as filterMemorySearchHitsBySessionVisibility } from "./session-search-visibility-upstream-hash.js"; '
            "const controller = new AbortController(); "
            "composeMemoryCorpusMetadata mergeMemorySearchCorpusResults attemptMemoryCorpus "
            "runMemoryCorpusDeadline runMemorySearchWithDeadline "
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        self.runtime_loader.write_text(
            'const loadMemoryToolsModule = createLazyRuntimeModule(() => import("../../tools-upstream-hash.js"));',
            encoding="utf-8",
        )
        visibility_source = maintenance.RUNTIME_DIST_DIR / "session-search-visibility-upstream-hash.js"
        guard = (
            'if (!params.hits.some((hit) => hit.source === "sessions"))'
            ' return params.conversationRecall?.corpus === "sessions" ? [] : params.hits; '
        )
        visibility_setup = "const visibility = resolveEffectiveSessionToolsVisibility({}); "
        body = guard + visibility_setup if guard_before_visibility else visibility_setup + guard
        visibility_source.write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { " + body
            + "function unused() {}",
            encoding="utf-8",
        )
        return tools_source

    def test_upstream_native_chunk_layout_is_ok(self) -> None:
        tools_source = self.write_upstream_native_layout()
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "ok")
        self.assertEqual(Path(state["path"]), tools_source)
        self.assertEqual(
            state["behavior_proof"],
            {
                "corpus_all_partial_result_tolerance": "upstream_native",
                "abort_deadline_enforcement": "upstream_native",
                "non_session_fast_path_guard": "upstream_native",
            },
        )
        self.assertTrue(state["non_session_fast_path_guard_before_visibility"])
        self.assertEqual(
            Path(state["visibility_chunk"]),
            maintenance.RUNTIME_DIST_DIR / "session-search-visibility-upstream-hash.js",
        )

    def test_upstream_native_guard_must_precede_visibility_setup(self) -> None:
        self.write_upstream_native_layout(guard_before_visibility=False)
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "attention")
        self.assertFalse(state["non_session_fast_path_guard_before_visibility"])
        self.assertEqual(state["missing_markers"], ["MEMORY_SEARCH_NON_SESSION_FAST_PATH_GUARD"])

    def test_partial_upstream_tolerance_is_attention(self) -> None:
        tools_source = maintenance.RUNTIME_DIST_DIR / "tools-partial-hash.js"
        tools_source.write_text(
            'import { t as filterMemorySearchHitsBySessionVisibility } from "./session-search-visibility-partial-hash.js"; '
            "const controller = new AbortController(); "
            "composeMemoryCorpusMetadata runMemoryCorpusDeadline "
            "function createMemorySearchTool() {}",
            encoding="utf-8",
        )
        self.runtime_loader.write_text(
            'const loadMemoryToolsModule = createLazyRuntimeModule(() => import("../../tools-partial-hash.js"));',
            encoding="utf-8",
        )
        (maintenance.RUNTIME_DIST_DIR / "session-search-visibility-partial-hash.js").write_text(
            "async function filterMemorySearchHitsBySessionVisibility(params) { "
            'if (!params.hits.some((hit) => hit.source === "sessions")) return params.hits; '
            "const visibility = resolveEffectiveSessionToolsVisibility({}); ",
            encoding="utf-8",
        )
        state = maintenance.runtime_patch_state()
        self.assertEqual(state["status"], "attention")
        self.assertEqual(state["missing_markers"], ["CORPUS_ALL_PARTIAL_RESULT_TOLERANCE"])
        self.assertEqual(state["behavior_proof"]["abort_deadline_enforcement"], "upstream_native")

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
