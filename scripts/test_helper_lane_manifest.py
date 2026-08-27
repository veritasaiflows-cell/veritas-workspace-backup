#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import subprocess
import sys

import helper_lane_manifest as manifest


class HelperLaneManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "handoff"
        self.base.mkdir()
        (self.base / "a.txt").write_text("alpha", encoding="utf-8")
        (self.base / "b.txt").write_text("beta", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, files: list[str] | None = None, **limits: int) -> dict[str, object]:
        return manifest.build_handoff(
            "handoff",
            files or ["a.txt", "b.txt"],
            limits.get("max_files", 6),
            limits.get("max_total_bytes", 120_000),
            limits.get("max_context_tokens", 30_000),
            self.root,
        )

    def test_input_order_does_not_change_frozen_snapshot(self) -> None:
        first = self.build(["a.txt", "b.txt"])
        second = self.build(["b.txt", "a.txt"])
        self.assertEqual(first["files"], second["files"])
        self.assertEqual(first["frozen_snapshot_id"], second["frozen_snapshot_id"])
        self.assertEqual(first["contract_sha256"], second["contract_sha256"])

    def test_mutation_is_detected_by_closeout_revalidation(self) -> None:
        handoff = self.build(["a.txt"])
        lane = {
            "lane_id": "lane",
            "status": "completed",
            "handoff": handoff,
            "attempt": manifest.build_attempt(
                "lane", str(handoff["frozen_snapshot_id"]), 1, "2026-08-11T21:00:00Z", "", "", ""
            ),
            "incident": {"required": False, "sla_status": "not_applicable"},
        }
        self.assertEqual(manifest.revalidate_lane_handoff(lane, self.root)["status"], "ok")
        (self.base / "a.txt").write_text("changed", encoding="utf-8")
        result = manifest.revalidate_lane_handoff(lane, self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("handoff_files_mismatch", result["errors"])

    def test_file_byte_and_token_budgets_fail_closed(self) -> None:
        exact = self.build(["a.txt"], max_files=1, max_total_bytes=5, max_context_tokens=2)
        self.assertEqual(exact["preflight"]["status"], "ok")

        file_over = self.build(max_files=1)
        self.assertIn("context_file_budget_exceeded", file_over["preflight"]["errors"])
        byte_over = self.build(["a.txt"], max_total_bytes=4)
        self.assertIn("context_byte_budget_exceeded", byte_over["preflight"]["errors"])
        token_over = self.build(["a.txt"], max_context_tokens=1)
        self.assertIn("context_token_budget_exceeded", token_over["preflight"]["errors"])
        with self.assertRaisesRegex(ValueError, "max_files_exceeds_hard_ceiling"):
            self.build(max_files=7)
        with self.assertRaisesRegex(ValueError, "max_total_bytes_exceeds_hard_ceiling"):
            self.build(max_total_bytes=manifest.DEFAULT_MAX_TOTAL_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "max_context_tokens_exceeds_hard_ceiling"):
            self.build(max_context_tokens=manifest.DEFAULT_MAX_CONTEXT_TOKENS + 1)

    def test_absolute_parent_escape_and_case_duplicate_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "context_path_not_base_relative"):
            self.build([str((self.base / "a.txt").resolve())])
        with self.assertRaisesRegex(ValueError, "context_path_not_base_relative"):
            self.build(["../outside.txt"])
        with self.assertRaisesRegex(ValueError, "context_path_duplicate"):
            self.build(["a.txt", "A.TXT"])

    def test_attempt_identity_and_retry_requirements(self) -> None:
        snapshot = str(self.build(["a.txt"])["frozen_snapshot_id"])
        first = manifest.build_attempt("lane", snapshot, 1, "2026-08-11T21:00:00Z", "", "", "")
        retry = manifest.build_attempt(
            "lane",
            snapshot,
            2,
            "2026-08-11T21:05:00Z",
            str(first["attempt_id"]),
            "context_overflow",
            "split_review_packet",
        )
        self.assertEqual(first["retry_count"], 0)
        self.assertEqual(retry["retry_count"], 1)
        self.assertNotEqual(first["attempt_id"], retry["attempt_id"])
        tampered = dict(retry)
        tampered["retry_reason"] = "different_reason"
        lane = {
            "lane_id": "lane",
            "status": "completed",
            "handoff": self.build(["a.txt"]),
            "attempt": tampered,
            "incident": manifest.build_incident(
                True, "2026-08-11T21:00:00Z", "2026-08-11T21:01:00Z", "2026-08-11T21:01:00Z"
            ),
        }
        self.assertIn("attempt_attempt_id_mismatch", manifest.revalidate_attempt_and_incident(lane, snapshot))
        with self.assertRaisesRegex(ValueError, "retry_previous_attempt_id_missing"):
            manifest.build_attempt("lane", snapshot, 2, "2026-08-11T21:05:00Z", "", "overflow", "split")

    def test_incident_sla_boundaries(self) -> None:
        trigger = "2026-08-11T21:00:00Z"
        for seconds, expected in ((89, "met"), (90, "met"), (91, "breached")):
            update = f"2026-08-11T21:01:{seconds - 60:02d}Z"
            result = manifest.build_incident(True, trigger, update, update)
            self.assertEqual(result["sla_status"], expected)
            self.assertEqual(result["latency_seconds"], seconds)

        fractional = manifest.build_incident(
            True,
            "2026-08-11T21:00:00.000000Z",
            "2026-08-11T21:01:30.900000Z",
            "2026-08-11T21:01:30.900000Z",
        )
        self.assertEqual(fractional["latency_seconds"], 90.9)
        self.assertEqual(fractional["sla_status"], "breached")

    def test_v3_attachment_contract_rejects_compression_and_reader_limit_before_dispatch(self) -> None:
        (self.base / "compressed.gz").write_bytes(b"\x1f\x8bnot-a-real-stream")
        compressed = self.build(["compressed.gz"])
        self.assertEqual(compressed["preflight"]["status"], "blocked")
        self.assertIn("attachment_decode_unsupported:compressed.gz", compressed["preflight"]["errors"])

        (self.base / "long-line.txt").write_text("x" * (manifest.DEFAULT_MAX_ATTACHMENT_LINE_BYTES + 1), encoding="utf-8")
        oversized = self.build(["long-line.txt"])
        self.assertEqual(oversized["preflight"]["status"], "blocked")
        self.assertIn("attachment_reader_limit:long-line.txt:file_bytes", oversized["preflight"]["errors"])
        self.assertIn("attachment_reader_limit:long-line.txt:physical_line_bytes", oversized["preflight"]["errors"])

    def test_v3_receiver_readback_requires_each_actual_attachment_hash_and_snapshot(self) -> None:
        handoff = self.build(["a.txt", "b.txt"])
        proof = {
            "schema": manifest.RECEIVER_READBACK_SCHEMA,
            "status": "ok",
            "frozen_snapshot_id": handoff["frozen_snapshot_id"],
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
                for row in handoff["files"]
            ],
        }
        self.assertEqual(manifest.validate_receiver_readback(handoff, proof)["status"], "ok")
        proof["attachments"][0]["sha256"] = "0" * 64
        result = manifest.validate_receiver_readback(handoff, proof)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("attachment_source_readback_failed:source-01:sha256_mismatch", result["errors"])

    def test_completed_v3_payload_requires_receiver_main_and_actual_qa_proofs(self) -> None:
        handoff = self.build(["a.txt"])
        lane = {
            "lane_id": "lane",
            "status": "completed",
            "verdict": "PASS",
            "allow_partial": False,
            "required_artifacts": [],
            "handoff": handoff,
            "attempt": manifest.build_attempt(
                "lane", str(handoff["frozen_snapshot_id"]), 1, "2026-08-11T21:00:00Z", "", "", ""
            ),
            "incident": {"required": False, "sla_status": "not_applicable"},
        }
        payload = {
            "schema": manifest.SCHEMA,
            "expected_lanes": [lane],
            "authority_boundary": dict(manifest.AUTHORITY_BOUNDARY),
        }
        result = manifest.validate_payload(payload, self.root)
        self.assertEqual(result["status"], "error")
        self.assertIn("lane:attachment_source_readback_failed:proof_missing", result["errors"])
        self.assertIn("lane:main_applied_after_draft:proof_schema_invalid", result["errors"])
        self.assertIn("lane:qa_applied_diff:qa_result_artifact_path_missing", result["errors"])

    def test_preflight_fingerprint_tamper_and_invalid_cli_exit_are_fail_closed(self) -> None:
        handoff = self.build(["a.txt"])
        lane = {
            "lane_id": "lane",
            "status": "completed",
            "handoff": handoff,
            "attempt": manifest.build_attempt(
                "lane", str(handoff["frozen_snapshot_id"]), 1, "2026-08-11T21:00:00Z", "", "", ""
            ),
            "incident": {"required": False, "sla_status": "not_applicable"},
        }
        lane["handoff"]["preflight"]["fingerprint"] = "sha256:" + "0" * 64
        self.assertIn("handoff_preflight_mismatch", manifest.revalidate_lane_handoff(lane, self.root)["errors"])

        command = [
            sys.executable,
            str(Path(manifest.__file__).resolve()),
            "--lane-id",
            "budget-probe",
            "--status",
            "running",
            "--base-path",
            ".",
            "--context-file",
            "scripts/helper_lane_manifest.py",
            "--context-file",
            "scripts/helper_spawn_packets.py",
            "--max-files",
            "1",
        ]
        completed = subprocess.run(command, cwd=manifest.ROOT, capture_output=True, text=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('"status": "error"', completed.stdout)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
