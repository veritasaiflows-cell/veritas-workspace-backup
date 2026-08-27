#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import helper_lane_manifest as handoff_manifest
import swarm_completion_handshake as handshake


class SwarmCompletionHandshakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_workspace = handshake.WORKSPACE
        handshake.WORKSPACE = self.root
        self.base = self.root / "handoff"
        self.base.mkdir()
        (self.base / "context.txt").write_text("frozen context", encoding="utf-8")
        (self.base / "result.json").write_text('{"status":"ok"}', encoding="utf-8")

    def tearDown(self) -> None:
        handshake.WORKSPACE = self.old_workspace
        self.temp.cleanup()

    def lane(self) -> dict[str, object]:
        frozen = handoff_manifest.build_handoff("handoff", ["context.txt"], root=self.root)
        frozen_file = frozen["files"][0]
        post_apply_bytes = b"applied context"
        (self.base / "context.txt").write_bytes(post_apply_bytes)
        post_apply_sha256 = hashlib.sha256(post_apply_bytes).hexdigest()
        attempt = handoff_manifest.build_attempt(
            "qa-1", str(frozen["frozen_snapshot_id"]), 1, "2026-08-11T21:00:00Z", "", "", ""
        )
        diff_bytes = b"diff --git a/context.txt b/context.txt\n--- a/context.txt\n+++ b/context.txt\n@@ -1 +1 @@\n-frozen context\n+applied context\n"
        (self.root / "applied.diff").write_bytes(diff_bytes)
        applied_diff_sha256 = "sha256:" + hashlib.sha256(diff_bytes).hexdigest()
        qa_output = b"test_target: PASS\n"
        (self.root / "qa-output.txt").write_bytes(qa_output)
        qa_command = {
            "command": "python test_target.py",
            "exit_code": 0,
            "output_artifact": "qa-output.txt",
            "output_sha256": "sha256:" + hashlib.sha256(qa_output).hexdigest(),
            "validated_paths": ["context.txt"],
            "validated_after_sha256": {"context.txt": post_apply_sha256},
        }
        qa_result = {
            "schema": "veritas.qa_applied_diff_result.v1",
            "status": "ok",
            "qa_target": "actual_main_applied_diff",
            "frozen_snapshot_id": frozen["frozen_snapshot_id"],
            "applied_diff_sha256": applied_diff_sha256,
            "tested_paths": ["context.txt"],
            "tested_files": [{
                "path": "context.txt",
                "after_sha256": post_apply_sha256,
                "after_size_bytes": len(post_apply_bytes),
            }],
            "commands": [qa_command],
        }
        qa_bytes = json.dumps(qa_result, sort_keys=True, separators=(",", ":")).encode("utf-8")
        (self.root / "qa-result.json").write_bytes(qa_bytes)
        return {
            "lane_id": "qa-1",
            "status": "completed",
            "verdict": "PASS",
            "allow_partial": False,
            "required_artifacts": [{"path": "result.json", "kind": "json"}],
            "handoff": frozen,
            "attempt": attempt,
            "incident": {"required": False, "sla_status": "not_applicable"},
            "receiver_readback": {
                "schema": handoff_manifest.RECEIVER_READBACK_SCHEMA,
                "status": "ok",
                "frozen_snapshot_id": frozen["frozen_snapshot_id"],
                "receiver_session_ref_sha256": "sha256:" + "a" * 64,
                "receiver_run_ref_sha256": "sha256:" + "b" * 64,
                "attachments": [
                    {
                        "attachment_id": row["attachment_id"],
                        "path": row["path"],
                        "size_bytes": row["size_bytes"],
                        "sha256": row["sha256"],
                        "max_physical_line_bytes": row["max_physical_line_bytes"],
                        "readback_status": "ok",
                    }
                    for row in frozen["files"]
                ],
            },
            "main_application": {
                "schema": "veritas.main_applied_diff.v1",
                "status": "ok",
                "main_application_result": "applied",
                "frozen_snapshot_id": frozen["frozen_snapshot_id"],
                "delivery_mode": "patch_draft",
                "applied_diff_sha256": applied_diff_sha256,
                "applied_diff_artifact": "applied.diff",
                "allowed_paths": ["context.txt"],
                "changed_paths": ["context.txt"],
                "changed_files": [{
                    "path": "context.txt",
                    "before_sha256": frozen_file["sha256"],
                    "before_size_bytes": frozen_file["size_bytes"],
                    "after_sha256": post_apply_sha256,
                    "after_size_bytes": len(post_apply_bytes),
                }],
                "main_verified": True,
            },
            "qa_applied_diff": {
                "schema": "veritas.qa_applied_diff.v1",
                "status": "ok",
                "qa_target": "actual_main_applied_diff",
                "frozen_snapshot_id": frozen["frozen_snapshot_id"],
                "applied_diff_sha256": applied_diff_sha256,
                "qa_result_artifact": "qa-result.json",
                "qa_result_sha256": "sha256:" + hashlib.sha256(qa_bytes).hexdigest(),
                "commands": qa_result["commands"],
            },
        }

    def write_manifest(self, lane: dict[str, object], schema: str = handoff_manifest.SCHEMA) -> Path:
        path = self.root / "manifest.json"
        path.write_text(json.dumps({"schema": schema, "swarm_id": "test", "expected_lanes": [lane]}), encoding="utf-8")
        return path

    def test_clean_v3_manifest_allows_synthesis_and_reports_manifest_hash(self) -> None:
        path = self.write_manifest(self.lane())
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["synthesis_allowed"])
        self.assertEqual(len(result["observed_manifest_file_sha256"]), 64)
        self.assertEqual(result["lanes"][0]["handoff_revalidation"]["status"], "ok")
        self.assertEqual(result["lanes"][0]["receiver_readback"]["status"], "ok")

    def test_v3_missing_receiver_readback_or_applied_qa_blocks_synthesis(self) -> None:
        lane = self.lane()
        del lane["receiver_readback"]
        result = handshake.build_result(json.loads(self.write_manifest(lane).read_text(encoding="utf-8")), self.root / "manifest.json")
        issues = result["blocking_lanes"][0]["issues"]
        self.assertIn("attachment_source_readback_failed:proof_missing", issues)

        lane = self.lane()
        lane["qa_applied_diff"]["qa_target"] = "proposed_diff"  # type: ignore[index]
        result = handshake.build_result(json.loads(self.write_manifest(lane).read_text(encoding="utf-8")), self.root / "manifest.json")
        self.assertIn("qa_applied_diff:target_or_status_invalid", result["blocking_lanes"][0]["issues"])

    def test_missing_or_failed_preflight_blocks(self) -> None:
        lane = self.lane()
        lane["handoff"]["preflight"]["status"] = "blocked"  # type: ignore[index]
        path = self.write_manifest(lane)
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertFalse(result["synthesis_allowed"])
        self.assertIn("handoff_preflight_not_ok", result["blocking_lanes"][0]["issues"])

    def test_file_or_contract_hash_drift_blocks(self) -> None:
        lane = self.lane()
        (self.base / "context.txt").write_text("mutated", encoding="utf-8")
        path = self.write_manifest(lane)
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertIn("main_applied_after_draft:changed_file_post_apply_mismatch:context.txt", result["blocking_lanes"][0]["issues"])

        lane = self.lane()
        lane["handoff"]["contract_sha256"] = "sha256:" + "0" * 64  # type: ignore[index]
        path = self.write_manifest(lane)
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertIn("handoff_contract_sha256_mismatch", result["blocking_lanes"][0]["issues"])

    def test_incident_sla_breach_blocks_closeout(self) -> None:
        lane = self.lane()
        frozen = lane["handoff"]
        first_attempt = lane["attempt"]
        lane["attempt"] = handoff_manifest.build_attempt(
            "qa-1",
            str(frozen["frozen_snapshot_id"]),  # type: ignore[index]
            2,
            "2026-08-11T21:02:00Z",
            str(first_attempt["attempt_id"]),  # type: ignore[index]
            "context_overflow",
            "split_packet",
        )
        lane["incident"] = handoff_manifest.build_incident(
            True,
            "2026-08-11T21:00:00Z",
            "2026-08-11T21:01:31Z",
            "2026-08-11T21:01:31Z",
        )
        path = self.write_manifest(lane)
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertIn("incident_sla_breached", result["blocking_lanes"][0]["issues"])

    def test_legacy_manifest_keeps_workspace_relative_behavior_with_warning(self) -> None:
        legacy = copy.deepcopy(self.lane())
        legacy.pop("handoff")
        legacy.pop("attempt")
        legacy.pop("incident")
        legacy["required_artifacts"] = [{"path": "handoff/result.json", "kind": "json"}]
        path = self.write_manifest(legacy, handoff_manifest.LEGACY_SCHEMA)
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertEqual(result["status"], "ok")
        self.assertIn("legacy_manifest_without_frozen_handoff_revalidation", result["warnings"])

    def test_v2_manifest_remains_compatible_with_explicit_warning(self) -> None:
        lane = self.lane()
        frozen = handoff_manifest.build_handoff("handoff", ["context.txt"], root=self.root, contract_version=2)
        lane["handoff"] = frozen
        lane["attempt"] = handoff_manifest.build_attempt(
            "qa-1", str(frozen["frozen_snapshot_id"]), 1, "2026-08-11T21:00:00Z", "", "", ""
        )
        path = self.write_manifest(lane, handoff_manifest.PREVIOUS_SCHEMA)
        result = handshake.build_result(json.loads(path.read_text(encoding="utf-8")), path)
        self.assertEqual(result["status"], "ok")
        self.assertIn("v2_manifest_compatibility_mode", result["warnings"])

    def test_schema_contract_mismatch_cannot_downgrade_v3_closeout(self) -> None:
        v3_lane = self.lane()
        downgraded = handshake.build_result(
            json.loads(self.write_manifest(v3_lane, handoff_manifest.PREVIOUS_SCHEMA).read_text(encoding="utf-8")),
            self.root / "manifest.json",
        )
        self.assertEqual(downgraded["status"], "blocked")
        self.assertIn("manifest_handoff_contract_version_mismatch", downgraded["blocking_lanes"][0]["issues"])

        v2_lane = self.lane()
        v2_handoff = handoff_manifest.build_handoff("handoff", ["context.txt"], root=self.root, contract_version=2)
        v2_lane["handoff"] = v2_handoff
        v2_lane["attempt"] = handoff_manifest.build_attempt(
            "qa-1", str(v2_handoff["frozen_snapshot_id"]), 1, "2026-08-11T21:00:00Z", "", "", ""
        )
        upgraded = handshake.build_result(
            json.loads(self.write_manifest(v2_lane, handoff_manifest.SCHEMA).read_text(encoding="utf-8")),
            self.root / "manifest.json",
        )
        self.assertEqual(upgraded["status"], "blocked")
        self.assertIn("manifest_handoff_contract_version_mismatch", upgraded["blocking_lanes"][0]["issues"])

    def test_v3_rejects_escaping_scope_or_structurally_fake_applied_proof(self) -> None:
        lane = self.lane()
        lane["main_application"]["allowed_paths"] = ["../../outside"]  # type: ignore[index]
        result = handshake.build_result(json.loads(self.write_manifest(lane).read_text(encoding="utf-8")), self.root / "manifest.json")
        issues = result["blocking_lanes"][0]["issues"]
        self.assertIn("main_applied_after_draft:allowed_paths_path_not_workspace_relative", issues)

        lane = self.lane()
        lane["main_application"]["applied_diff_sha256"] = "sha256:" + "f" * 64  # type: ignore[index]
        lane["qa_applied_diff"]["applied_diff_sha256"] = "sha256:" + "f" * 64  # type: ignore[index]
        result = handshake.build_result(json.loads(self.write_manifest(lane).read_text(encoding="utf-8")), self.root / "manifest.json")
        self.assertIn("main_applied_after_draft:applied_diff_hash_not_artifact", result["blocking_lanes"][0]["issues"])

        lane = self.lane()
        bad_commands = [{
            "command": "python unrelated.py",
            "exit_code": 0,
            "output_artifact": "qa-output.txt",
            "output_sha256": "sha256:" + hashlib.sha256((self.root / "qa-output.txt").read_bytes()).hexdigest(),
            "validated_paths": ["unrelated.py"],
            "validated_after_sha256": {"unrelated.py": "f" * 64},
        }]
        qa_result_path = self.root / "qa-result.json"
        qa_result = json.loads(qa_result_path.read_text(encoding="utf-8"))
        qa_result["commands"] = bad_commands
        qa_bytes = json.dumps(qa_result, sort_keys=True, separators=(",", ":")).encode("utf-8")
        qa_result_path.write_bytes(qa_bytes)
        lane["qa_applied_diff"]["commands"] = bad_commands  # type: ignore[index]
        lane["qa_applied_diff"]["qa_result_sha256"] = "sha256:" + hashlib.sha256(qa_bytes).hexdigest()  # type: ignore[index]
        result = handshake.build_result(json.loads(self.write_manifest(lane).read_text(encoding="utf-8")), self.root / "manifest.json")
        self.assertIn("qa_applied_diff:qa_result_command_validated_paths_mismatch", result["blocking_lanes"][0]["issues"])

    def test_v3_rejects_a_noop_or_wrong_post_apply_workspace_state(self) -> None:
        lane = self.lane()
        (self.base / "context.txt").write_text("frozen context", encoding="utf-8")
        result = handshake.build_result(json.loads(self.write_manifest(lane).read_text(encoding="utf-8")), self.root / "manifest.json")
        self.assertIn(
            "main_applied_after_draft:changed_file_post_apply_mismatch:context.txt",
            result["blocking_lanes"][0]["issues"],
        )


if __name__ == "__main__":
    raise SystemExit(unittest.main())
