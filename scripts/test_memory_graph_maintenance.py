#!/usr/bin/env python3
"""Regression tests for maintenance delegation and shared hash health."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import memory_graph_maintenance as maintenance


VALIDATION_ROOT = Path(
    os.environ.get("GRAPH_INCREMENTAL_TEST_ROOT", tempfile.gettempdir())
).resolve()
FRESH_GRAPH = {
    "status": "ok",
    "freshness": "fresh",
    "selected_path": "scripts/graphify-out/graph.json",
    "candidates": [],
}
STALE_GRAPH = {
    "status": "ok",
    "freshness": "stale",
    "selected_path": "scripts/graphify-out/graph.json",
    "candidates": [],
}
VALID_CACHE = {
    "status": "ok",
    "errors": [],
    "warnings": [],
    "source_count": 391,
    "chunk_count": 2348,
    "embedding_provider": "ollama",
    "embedding_model": "nomic-embed-text:latest",
}
HEALTHY_VECTOR_STORES = {
    "status": "ok",
    "checked": 9,
    "degraded_agents": [],
    "stores": [],
}
READY_OWNER_PREFLIGHT = {
    "outcome": "ready",
    "launch_allowed": True,
    "target_cap": {"max_targets": 25},
    "backlog": {"target_cap_exceeded": False},
}


def _tempdir() -> tempfile.TemporaryDirectory[str]:
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=VALIDATION_ROOT)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


class MemoryGraphMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = _tempdir()
        self.root = Path(self.temp.name)
        self.old_out = maintenance.OUT
        self.old_scorecard = maintenance.SCORECARD_OUT
        maintenance.OUT = self.root / "proof" / "operational.json"
        maintenance.SCORECARD_OUT = self.root / "proof" / "scorecard.json"

    def tearDown(self) -> None:
        maintenance.OUT = self.old_out
        maintenance.SCORECARD_OUT = self.old_scorecard
        self.temp.cleanup()

    def test_real_unrelated_dependencies_are_loaded(self) -> None:
        for module in (
            maintenance.semantic_maintenance,
            maintenance.vmi,
        ):
            path = Path(module.__file__).resolve()
            self.assertIn("scripts", path.parts)
            self.assertNotIn("sol-draft", path.parts)
        router_module = sys.modules["lib.graphify_router"]
        router_path = Path(router_module.__file__).resolve()
        self.assertIn("scripts", router_path.parts)
        self.assertNotIn("sol-draft", router_path.parts)

    def test_gate_and_scorecard_contracts_remain_intact(self) -> None:
        with mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH):
            code, gate = maintenance.run_gate(write=True)
        self.assertEqual(code, 0)
        self.assertEqual(gate["status"], "ok")
        self.assertEqual(gate["action"], "no_refresh_needed")
        self.assertEqual(
            json.loads(maintenance.OUT.read_text(encoding="utf-8"))["status"],
            "ok",
        )
        with (
            mock.patch.object(
                maintenance.semantic_maintenance,
                "safe_validate",
                return_value=(VALID_CACHE, None),
            ),
            mock.patch.object(
                maintenance.semantic_maintenance,
                "vector_store_integrity_state",
                return_value=HEALTHY_VECTOR_STORES,
            ),
            mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH),
            mock.patch.object(maintenance, "embedding_dimension", return_value=768),
            mock.patch.object(
                maintenance,
                "latest_maintenance_summary",
                return_value={
                    "status": "ok",
                    "generated_at_utc": maintenance.utc_now(),
                },
            ),
        ):
            code, scorecard = maintenance.run_scorecard(write=True)
        self.assertEqual(code, 0)
        self.assertEqual(scorecard["status"], "ok")
        self.assertEqual(scorecard["vector_cache"]["embedding_dimension"], 768)

    def test_code_health_uses_shared_hash_policy_and_detects_same_mtime(self) -> None:
        source_root = self.root / "scripts"
        graph_dir = source_root / "graphify-out"
        graph_dir.mkdir(parents=True)
        graph_path = graph_dir / "graph.json"
        graph_path.write_text("{}", encoding="utf-8")
        source = source_root / "worker.py"
        source.write_text("x = 1\n", encoding="utf-8")
        old_mtime = source.stat().st_mtime
        rows = {
            "worker.py": {
                "mtime": old_mtime,
                "ast_hash": _md5(source),
                "semantic_hash": "",
            },
            "fixture.json": {"mtime": 1},
        }
        (graph_dir / "manifest.json").write_text(
            json.dumps(rows), encoding="utf-8"
        )
        fresh = maintenance.code_only_manifest_health(graph_path)
        self.assertEqual(fresh["coverage_status"], "fresh")
        self.assertEqual(fresh["changed_count"], 0)
        source.write_text("x = 2\n", encoding="utf-8")
        os.utime(source, (old_mtime, old_mtime))
        stale = maintenance.code_only_manifest_health(graph_path)
        self.assertEqual(stale["coverage_status"], "stale")
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["changed_count"], 1)
        self.assertEqual(stale["changed_sample"], ["worker.py"])
        self.assertEqual(stale["new_count"], 0)
        self.assertEqual(stale["deleted_count"], 0)
        self.assertEqual(
            stale["method"], "code_only_manifest_shared_hash_policy"
        )

    def test_code_health_shares_sensitive_and_generated_exclusions(self) -> None:
        source_root = self.root / "scripts"
        graph_dir = source_root / "graphify-out"
        graph_dir.mkdir(parents=True)
        graph_path = graph_dir / "graph.json"
        graph_path.write_text("{}", encoding="utf-8")
        (source_root / "safe.py").write_text("x = 1\n", encoding="utf-8")
        sensitive = source_root / "credentials" / "secret.py"
        sensitive.parent.mkdir()
        sensitive.write_text("do_not_read = 1\n", encoding="utf-8")
        generated = source_root / "generated" / "output.py"
        generated.parent.mkdir()
        generated.write_text("do_not_read = 2\n", encoding="utf-8")
        rows = {
            "safe.py": {
                "mtime": (source_root / "safe.py").stat().st_mtime,
                "ast_hash": _md5(source_root / "safe.py"),
            }
        }
        (graph_dir / "manifest.json").write_text(
            json.dumps(rows), encoding="utf-8"
        )
        with mock.patch.object(
            maintenance.incremental_owner,
            "hash_file",
            wraps=maintenance.incremental_owner.hash_file,
        ) as hashed:
            state = maintenance.code_only_manifest_health(graph_path)
        read_paths = {Path(call.args[0]).name for call in hashed.call_args_list}
        self.assertEqual(read_paths, {"safe.py"})
        self.assertEqual(state["coverage_status"], "fresh")

    def test_code_health_rejects_reparse_source_root(self) -> None:
        source_root = self.root / "scripts"
        graph_dir = source_root / "graphify-out"
        graph_dir.mkdir(parents=True)
        graph_path = graph_dir / "graph.json"
        graph_path.write_text("{}", encoding="utf-8")
        (graph_dir / "manifest.json").write_text("{}", encoding="utf-8")
        original_lstat = Path.lstat

        def marked_lstat(path):
            actual = original_lstat(path)
            if Path(path) == source_root:
                return mock.Mock(
                    st_mode=actual.st_mode,
                    st_file_attributes=0x400,
                )
            return actual

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=marked_lstat):
            state = maintenance.code_only_manifest_health(graph_path)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["coverage_status"], "unknown")
        self.assertIn("source_root_reparse_component", state["policy_block"])

    def test_owner_command_is_unique_stage_only_and_forwards_subset(self) -> None:
        before = {
            "selected_path": "scripts/graphify-out/graph.json",
        }
        first = maintenance.owner_stage_command(
            before, changed_paths=["memory_graph_maintenance.py"]
        )
        second = maintenance.owner_stage_command(
            before, changed_paths=["memory_graph_maintenance.py"]
        )
        self.assertIn("--mode", first)
        self.assertIn("stage", first)
        self.assertNotIn("update", first)
        self.assertIn("--changed-path", first)
        self.assertIn("memory_graph_maintenance.py", first)
        self.assertEqual(
            first[first.index("--max-targets") + 1],
            str(maintenance.incremental_owner.MAX_TARGETS),
        )
        first_stage = Path(first[first.index("--stage-dir") + 1])
        second_stage = Path(second[second.index("--stage-dir") + 1])
        self.assertNotEqual(first_stage, second_stage)
        self.assertEqual(first_stage.parent, maintenance.OWNER_STAGE_ROOT)

    def test_refresh_stages_then_publishes_one_bounded_batch(self) -> None:
        staged = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"outcome":"staged"}', stderr=""
        )
        published = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"outcome":"published_with_backlog","backlog":{"remaining_changed_count":88}}',
            stderr="",
        )
        with (
            mock.patch.object(
                maintenance, "graph_state", side_effect=[STALE_GRAPH, STALE_GRAPH]
            ),
            mock.patch.object(
                maintenance,
                "owner_stage_preflight",
                return_value=READY_OWNER_PREFLIGHT,
            ),
            mock.patch.object(
                maintenance.subprocess, "run", side_effect=[staged, published]
            ) as run,
        ):
            code, payload = maintenance.run_refresh(
                max_seconds=30,
                write=False,
                changed_paths=["memory_graph_maintenance.py"],
            )
        stage_command = run.call_args_list[0].args[0]
        publish_command = run.call_args_list[1].args[0]
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["action"], "owner_stage_then_publish_incremental_batch")
        self.assertEqual(payload["publication"], "published_bounded_batch")
        self.assertEqual(payload["backlog"]["remaining_changed_count"], 88)
        self.assertIn("--changed-path", stage_command)
        self.assertEqual(publish_command[publish_command.index("--mode") + 1], "publish")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertEqual(run.call_args.kwargs["cwd"], maintenance.GRAPH_ROOT)

    def test_refresh_keeps_full_structured_owner_refusal(self) -> None:
        reason = "target_count_26_exceeds_cap_25:" + ("x" * 5000)
        refusal = {
            "outcome": "blocked",
            "reason": reason,
            "selection": {"policy_block": reason},
        }
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout=json.dumps(refusal),
            stderr="owner refused stage",
        )
        with (
            mock.patch.object(
                maintenance, "graph_state", side_effect=[STALE_GRAPH, STALE_GRAPH]
            ),
            mock.patch.object(
                maintenance,
                "owner_stage_preflight",
                return_value=READY_OWNER_PREFLIGHT,
            ),
            mock.patch.object(
                maintenance.subprocess, "run", return_value=completed
            ),
        ):
            code, payload = maintenance.run_refresh(max_seconds=30, write=False)
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["owner_stage_result"], refusal)
        self.assertEqual(payload["owner_refusal"], refusal)
        self.assertEqual(payload["owner_refusal"]["reason"], reason)
        self.assertEqual(len(payload["stage_result"]["stdout_tail"]), 4000)

    def test_preflight_batches_26_target_backlog_without_raising_cap(self) -> None:
        source_root = self.root / "scripts"
        graph_dir = source_root / "graphify-out"
        graph_dir.mkdir(parents=True)
        graph_path = graph_dir / "graph.json"
        graph_path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
        (graph_dir / "manifest.json").write_text("{}", encoding="utf-8")
        for index in range(26):
            (source_root / f"changed_{index:02d}.py").write_text(
                "value = 1\n", encoding="utf-8"
            )
        stale_graph = {
            "status": "ok",
            "freshness": "stale",
            "selected_path": str(graph_path),
            "candidates": [],
        }
        old_graph_root = maintenance.GRAPH_ROOT
        maintenance.GRAPH_ROOT = source_root
        try:
            payload = maintenance.owner_stage_preflight(stale_graph)
        finally:
            maintenance.GRAPH_ROOT = old_graph_root
        self.assertTrue(payload["launch_allowed"])
        self.assertEqual(payload["backlog"]["max_targets"], 25)
        self.assertEqual(payload["backlog"]["selected_target_count"], 25)
        self.assertEqual(payload["backlog"]["deferred_changed_count"], 1)
        self.assertTrue(payload["backlog"]["resumable"])

    def test_latest_maintenance_summary_hashes_rebuild_completion(self) -> None:
        producer_path = self.root / "semantic-maintenance.json"
        producer_payload = {
            "status": "ok",
            "action": "rebuild_registered_sources",
            "generated_at_utc": maintenance.utc_now(),
            "rebuild_attempts": [
                {"rebuild_exit_code": 0, "post_validation": {"status": "ok"}}
            ],
        }
        raw = json.dumps(producer_payload, sort_keys=True).encode("utf-8")
        producer_path.write_bytes(raw)
        old_out = maintenance.semantic_maintenance.OUT
        maintenance.semantic_maintenance.OUT = producer_path
        try:
            summary = maintenance.latest_maintenance_summary()
        finally:
            maintenance.semantic_maintenance.OUT = old_out
        self.assertEqual(summary["producer_completion"]["state"], "rebuild_completed")
        self.assertEqual(
            summary["producer_completion"]["token"],
            hashlib.sha256(raw).hexdigest(),
        )
        self.assertEqual(summary["producer_completion"]["post_validation_status"], "ok")

    def test_scorecard_revalidates_after_producer_completion(self) -> None:
        pre_validation = {**VALID_CACHE, "snapshot": "pre"}
        post_validation = {**VALID_CACHE, "snapshot": "post"}
        before = {
            "status": "ok",
            "generated_at_utc": maintenance.utc_now(),
            "producer_completion": {"state": "rebuild_completed", "token": "before"},
        }
        after = {
            "status": "ok",
            "generated_at_utc": maintenance.utc_now(),
            "producer_completion": {"state": "rebuild_completed", "token": "after"},
        }
        with (
            mock.patch.object(
                maintenance.semantic_maintenance,
                "safe_validate",
                side_effect=[(pre_validation, None), (post_validation, None)],
            ) as validate,
            mock.patch.object(
                maintenance.semantic_maintenance,
                "vector_store_integrity_state",
                return_value=HEALTHY_VECTOR_STORES,
            ),
            mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH),
            mock.patch.object(maintenance, "embedding_dimension", return_value=768),
            mock.patch.object(
                maintenance,
                "latest_maintenance_summary",
                side_effect=[before, after, after],
            ) as summary,
        ):
            code, payload = maintenance.run_scorecard(write=False)
        self.assertEqual(code, 0)
        self.assertEqual(validate.call_count, 2)
        self.assertEqual(summary.call_count, 3)
        self.assertEqual(payload["vector_cache"]["validation"]["snapshot"], "post")
        self.assertTrue(payload["vector_cache"]["validation_current"])
        self.assertEqual(payload["vector_cache"]["freshness"], "fresh")
        self.assertEqual(
            payload["vector_cache"]["producer_completion_handoff"]["status"],
            "fresh_post_completion_validation_ok",
        )

    def test_scorecard_marks_snapshot_noncurrent_if_producer_changes_again(self) -> None:
        pre_validation = {**VALID_CACHE, "snapshot": "pre"}
        post_validation = {**VALID_CACHE, "snapshot": "post"}
        before = {
            "status": "ok",
            "generated_at_utc": maintenance.utc_now(),
            "producer_completion": {"state": "rebuild_completed", "token": "before"},
        }
        after = {
            "status": "ok",
            "generated_at_utc": maintenance.utc_now(),
            "producer_completion": {"state": "rebuild_completed", "token": "after"},
        }
        changed_again = {
            "status": "ok",
            "generated_at_utc": maintenance.utc_now(),
            "producer_completion": {"state": "rebuild_completed", "token": "again"},
        }
        with (
            mock.patch.object(
                maintenance.semantic_maintenance,
                "safe_validate",
                side_effect=[(pre_validation, None), (post_validation, None)],
            ),
            mock.patch.object(
                maintenance.semantic_maintenance,
                "vector_store_integrity_state",
                return_value=HEALTHY_VECTOR_STORES,
            ),
            mock.patch.object(maintenance, "graph_state", return_value=FRESH_GRAPH),
            mock.patch.object(maintenance, "embedding_dimension", return_value=768),
            mock.patch.object(
                maintenance,
                "latest_maintenance_summary",
                side_effect=[before, after, changed_again],
            ),
        ):
            code, payload = maintenance.run_scorecard(write=False)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "warning")
        self.assertFalse(payload["vector_cache"]["validation_current"])
        self.assertEqual(payload["vector_cache"]["freshness"], "attention")
        self.assertIn(
            "primary_vector_cache_handoff_validation_required",
            payload["warnings"],
        )
        self.assertEqual(
            payload["vector_cache"]["producer_completion_handoff"]["status"],
            "producer_changed_during_post_completion_validation",
        )

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
            "stale_sources": [{"source_path": "wiki/index.md", "reason": "sha256_mismatch"}],
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
