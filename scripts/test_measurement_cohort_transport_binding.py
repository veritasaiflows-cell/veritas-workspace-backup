#!/usr/bin/env python3
"""Focused fail-closed checks for the Wave 2 low-effort admission binding."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import measurement_cohort_transport_binding as binding


NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
JOB_ID = binding.JOB_ID
CALIBRATION_JOB_ID = f"{JOB_ID}-calibration"
PATHS = ["scripts/compact_exec.py", "scripts/test_compact_exec.py"]
JOB2_ID = "wave2-cohort-job-02-lane-dirty-porcelain-parser"
JOB2_PATHS = ["scripts/lane_collision_preflight.py", "scripts/test_lane_collision_preflight.py"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_write(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest(path.read_bytes())


class BindingFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.source_files: list[dict[str, object]] = []
        for index, relative in enumerate(PATHS, start=1):
            raw = f"fixture-{index}\n".encode("utf-8")
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.source_files.append({"path": relative, "bytes": len(raw), "sha256": digest(raw)})
        self.source_files.sort(key=lambda row: str(row["path"]))
        self.job2_source_files: list[dict[str, object]] = []
        for index, relative in enumerate(JOB2_PATHS, start=1):
            raw = f"job2-fixture-{index}\n".encode("utf-8")
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.job2_source_files.append(
                {"path": relative, "bytes": len(raw), "sha256": digest(raw)}
            )
        self.job2_source_files.sort(key=lambda row: str(row["path"]))
        self.manifest_reference = binding.COHORT_MANIFEST_REFERENCE
        self.handoff_reference = binding.HANDOFF_REFERENCE
        self.calibration_reference = "tmp/implementation-builder-scoped-worktree/calibration-proof.json"
        self.owner_session_root = root / "openclaw-controlled" / "agents" / "main" / "sessions"
        self.owner_session_id = "11111111-1111-4111-8111-111111111111"
        self.owner_message_id = "22222222-2222-4222-8222-222222222222"
        self.authorization_reference = (
            f"{binding.OWNER_APPROVAL_REFERENCE_PREFIX}"
            f"{self.owner_session_id}/{self.owner_message_id}"
        )
        self.approval_id = "wave2-cohort-10-job-low-route-dispatch-20260825"
        self.manifest_hash = ""
        self.handoff_hash = ""
        self.write_sources()

    def write_sources(self) -> None:
        for index, relative in enumerate(PATHS, start=1):
            (self.root / relative).write_bytes(f"fixture-{index}\n".encode("utf-8"))
        for index, relative in enumerate(JOB2_PATHS, start=1):
            (self.root / relative).write_bytes(f"job2-fixture-{index}\n".encode("utf-8"))
        jobs: list[dict[str, object]] = [
            {
                "job_number": 1,
                "job_id": JOB_ID,
                "activation_handoff": self.handoff_reference,
                "write_files": copy.deepcopy(self.source_files),
            },
            {
                "job_number": 2,
                "job_id": JOB2_ID,
                "activation_handoff": None,
                "write_files": copy.deepcopy(self.job2_source_files),
            },
        ]
        for number in range(3, 11):
            rows: list[dict[str, object]] = []
            for relative in (
                f"scripts/cohort_fixture_{number:02d}.py",
                f"scripts/test_cohort_fixture_{number:02d}.py",
            ):
                raw = f"job-{number}-{relative}\n".encode("utf-8")
                rows.append(
                    {"path": relative, "bytes": len(raw), "sha256": digest(raw)}
                )
            jobs.append(
                {
                    "job_number": number,
                    "job_id": f"wave2-cohort-fixture-job-{number:02d}",
                    "activation_handoff": None,
                    "write_files": sorted(rows, key=lambda row: str(row["path"])),
                }
            )
        manifest = {
            "schema": binding.COHORT_MANIFEST_SCHEMA,
            "status": "frozen_pending_hot_activation_and_sequential_dispatch",
            "cohort_id": binding.COHORT_ID,
            "fixed_route_contract": {
                "agent_id": binding.AGENT_ID,
                "execution_backend": "persistent_isolated_agent",
                "model_path": binding.TERRA_MODEL,
                "thinking": "low",
                "delivery_mode": binding.LANE_MODE,
                "sandbox": "require",
                "cwd_override_allowed": False,
                "fallback_route_allowed": False,
                "mixed_route_parent_jobs_allowed": False,
                "dispatch_order": "strictly_sequential",
                "task_class": "narrow_non_finance_workspace_local_python_guard_hardening",
                "write_file_count_per_job": 2,
                "validation_budget": "narrow",
                "main_final_acceptance_required": True,
            },
            "authority_boundary": {
                "preparation_only": True,
                "config_or_runtime_changed": False,
                "provider_job_dispatch_authorized": False,
                "automatic_route_promotion_allowed": False,
                "wave3_authorized": False,
                "finance_canon_portfolio_or_execution_authority": False,
                "owner_approval_inferred": False,
            },
            "jobs": jobs,
        }
        handoff_files = [
            {"path": row["path"], "size_bytes": row["bytes"], "sha256": row["sha256"]}
            for row in self.source_files
        ]
        handoff = {
            "schema": binding.HANDOFF_SCHEMA,
            "status": "ok",
            "swarm_id": binding.HANDOFF_SWARM_ID,
            "activation_job_contract": {
                "schema": "veritas.wave2_job_activation_contract.v1",
                "job_id": JOB_ID,
                "allowed_files": list(PATHS),
            },
            "expected_lanes": [
                {
                    "lane_id": binding.LANE_ID,
                    "owner_workflow": "WAVE2",
                    "status": "pending",
                    "verdict": "awaiting_owner_activation_and_dispatch",
                    "allow_partial": False,
                    "session_id": "",
                    "session_label": "",
                    "attempt": {"attempt_number": 1, "retry_count": 0, "is_first_attempt": True},
                    "handoff": {
                        "contract_version": 3,
                        "base_path": ".",
                        "files": handoff_files,
                        "frozen_snapshot_id": "sha256:" + "a" * 64,
                        "contract_sha256": "sha256:" + "b" * 64,
                    },
                }
            ],
            "authority_boundary": {
                "config_auth_channel_runtime_mutation_allowed": False,
                "customer_or_external_delivery_allowed": False,
                "sql_or_ticker_import_allowed": False,
                "canon_or_portfolio_mutation_allowed": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
        }
        self.manifest_hash = json_write(self.root / self.manifest_reference, manifest)
        self.handoff_hash = json_write(self.root / self.handoff_reference, handoff)
        calibration = {
            "schema": binding.CALIBRATION_PROOF_SCHEMA,
            "status": "ok",
            "observed_at_utc": "2026-08-25T11:00:00Z",
            "expires_at_utc": "2026-08-25T13:00:00Z",
            "agent_id": binding.AGENT_ID,
            "runtime": {
                "execution_backend": "persistent_isolated_agent",
                "provider": "openai",
                "model": binding.TERRA_MODEL,
                "thinking": "low",
                "openclaw_version": "2026.7.1",
                "config_sha256": "c" * 64,
            },
            "capabilities": {},
            "evidence": {
                "worktree": {
                    "job_id": CALIBRATION_JOB_ID,
                    "manifest_reference": f"retained_completed_worktree/{CALIBRATION_JOB_ID}/handoff-manifest.json",
                    "changed_paths": list(PATHS),
                }
            },
        }
        json_write(self.root / self.calibration_reference, calibration)
        scope = {
            "schema": "veritas.wave2_cohort_dispatch_scope.v1",
            "cohort_id": binding.COHORT_ID,
            "cohort_manifest_reference": binding.COHORT_MANIFEST_REFERENCE,
            "cohort_manifest_sha256": self.manifest_hash,
            "cohort_job_ids": [str(row["job_id"]) for row in jobs],
            "job1_anchor_handoff_reference": binding.HANDOFF_REFERENCE,
            "job1_anchor_handoff_sha256": self.handoff_hash,
            "calibration_proof_reference": self.calibration_reference,
            "calibration_proof_sha256": digest(
                (self.root / self.calibration_reference).read_bytes()
            ),
            "calibration_job_id": CALIBRATION_JOB_ID,
            "calibration_capability_only": True,
            "agent_id": binding.AGENT_ID,
            "execution_backend": "persistent_isolated_agent",
            "model_path": binding.TERRA_MODEL,
            "thinking": "low",
            "persistent_lane_mode": binding.LANE_MODE,
            "dispatch_order": "strictly_sequential",
            "cohort_dispatch_authorized": True,
            "supersedes_preparation_only_for_exact_frozen_cohort": True,
        }
        self.write_owner_approval(
            binding._owner_approval_statement(
                self.approval_id,
                binding._canonical_sha256(scope),
                "2026-08-25T13:00:00Z",
            )
        )

    def write_owner_approval(self, content: str, *, sender_is_owner: bool = True) -> None:
        transcript = self.owner_session_root / f"{self.owner_session_id}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "type": "session",
            "version": 3,
            "id": self.owner_session_id,
            "timestamp": "2026-08-25T11:00:00Z",
        }
        row = {
            "type": "message",
            "id": self.owner_message_id,
            "timestamp": "2026-08-25T11:30:00Z",
            "message": {
                "role": "user",
                "sourceChannel": "webchat",
                "content": content,
                "__openclaw": {"senderIsOwner": sender_is_owner},
            },
        }
        transcript.write_text(
            "\n".join(json.dumps(item, sort_keys=True) for item in (header, row)) + "\n",
            encoding="utf-8",
        )

    def append_owner_revocation(self) -> None:
        transcript = self.owner_session_root / f"{self.owner_session_id}.jsonl"
        row = {
            "type": "message",
            "id": "33333333-3333-4333-8333-333333333333",
            "timestamp": "2026-08-25T11:45:00Z",
            "message": {
                "role": "user",
                "sourceChannel": "webchat",
                "content": binding._owner_revocation_statement(self.approval_id),
                "__openclaw": {"senderIsOwner": True},
            },
        }
        with transcript.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def active_state(self, *, job_id: str = JOB_ID) -> dict[str, object]:
        files = self.source_files if job_id == JOB_ID else self.job2_source_files
        return {
            "job_id": job_id,
            "manifest_sha256": "e" * 64,
            "baseline_commit": "f" * 40,
            "allowed_write_paths": [str(row["path"]) for row in files],
            "source_file_hashes": copy.deepcopy(files),
        }

    def strict_check(self) -> dict[str, object]:
        changed = [
            {"relative_path": row["path"], "exists": True, "bytes": row["bytes"], "sha256": row["sha256"]}
            for row in self.source_files
        ]
        return {
            "status": "ok",
            "code": "ok",
            "proof_schema": binding.CALIBRATION_PROOF_SCHEMA,
            "runtime": {
                "execution_backend": "persistent_isolated_agent",
                "provider": "openai",
                "model": binding.TERRA_MODEL,
                "thinking": "low",
                "openclaw_version": "2026.7.1",
                "config_sha256": "c" * 64,
            },
            "evidence": {
                "worktree": {
                    "job_id": CALIBRATION_JOB_ID,
                    "manifest_reference": f"retained_completed_worktree/{CALIBRATION_JOB_ID}/handoff-manifest.json",
                    "manifest_sha256": "1" * 64,
                    "baseline_commit": "2" * 40,
                    "changed_paths": list(PATHS),
                    "changed_files": changed,
                    "git_path_inventory_sha256": "3" * 64,
                }
            },
        }


class MeasurementCohortBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = BindingFixture(self.root)
        self.hash_patch = patch.multiple(
            binding,
            COHORT_MANIFEST_SHA256=self.fixture.manifest_hash,
            HANDOFF_SHA256=self.fixture.handoff_hash,
        )
        self.hash_patch.start()

    def tearDown(self) -> None:
        self.hash_patch.stop()
        self.temporary.cleanup()

    def build(
        self,
        *,
        strict: dict[str, object] | None = None,
        job_id: str = JOB_ID,
    ) -> dict[str, object]:
        return binding.build_binding(
            cohort_manifest_reference=self.fixture.manifest_reference,
            handoff_reference=self.fixture.handoff_reference,
            calibration_proof_reference=self.fixture.calibration_reference,
            authorization_reference=self.fixture.authorization_reference,
            job_id=job_id,
            root=self.root,
            active_state=self.fixture.active_state(job_id=job_id),
            now=NOW,
            ttl=timedelta(minutes=30),
            strict_calibration_check=strict or self.fixture.strict_check(),
            owner_session_root=self.fixture.owner_session_root,
        )

    def validate(
        self,
        payload: dict[str, object],
        *,
        strict: dict[str, object] | None = None,
        job_id: str = JOB_ID,
    ) -> dict[str, object]:
        return binding.validate_binding_payload(
            payload,
            root=self.root,
            active_state=self.fixture.active_state(job_id=job_id),
            now=NOW + timedelta(minutes=1),
            strict_calibration_check=strict or self.fixture.strict_check(),
            owner_session_root=self.fixture.owner_session_root,
        )

    def test_exact_frozen_binding_is_admission_only(self) -> None:
        payload = self.build()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(self.validate(payload)["status"], "ok")
        boundary = payload["authority_boundary"]
        self.assertFalse(boundary["protected_dispatch_binding_created"])
        self.assertFalse(boundary["usage_receipt_created"])
        self.assertFalse(boundary["cohort_credit_granted"])

    def test_generic_job1_calibration_admits_second_frozen_job(self) -> None:
        payload = self.build(job_id=JOB2_ID)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["job"]["job_id"], JOB2_ID)
        self.assertEqual(payload["job"]["allowed_write_paths"], JOB2_PATHS)
        self.assertEqual(payload["calibration"]["job_id"], CALIBRATION_JOB_ID)
        self.assertEqual(payload["calibration"]["changed_paths"], PATHS)
        checked = self.validate(payload, job_id=JOB2_ID)
        self.assertEqual(checked["status"], "ok")
        self.assertEqual(checked["calibration_allowed_write_paths"], PATHS)

    def test_windows_cli_references_are_canonicalized_before_binding(self) -> None:
        payload = binding.build_binding(
            cohort_manifest_reference=self.fixture.manifest_reference.replace("/", "\\"),
            handoff_reference=self.fixture.handoff_reference.replace("/", "\\"),
            calibration_proof_reference=self.fixture.calibration_reference.replace("/", "\\"),
            authorization_reference=self.fixture.authorization_reference,
            job_id=JOB2_ID,
            root=self.root,
            active_state=self.fixture.active_state(job_id=JOB2_ID),
            now=NOW,
            ttl=timedelta(minutes=30),
            strict_calibration_check=self.fixture.strict_check(),
            owner_session_root=self.fixture.owner_session_root,
        )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["cohort"]["manifest_reference"], self.fixture.manifest_reference)
        self.assertEqual(payload["handoff"]["reference"], self.fixture.handoff_reference)
        self.assertEqual(payload["calibration"]["reference"], self.fixture.calibration_reference)
        self.assertEqual(self.validate(payload, job_id=JOB2_ID)["status"], "ok")

    def test_windows_cli_reference_normalization_remains_fail_closed(self) -> None:
        for reference in (
            r"C:\\tmp\\implementation-builder-scoped-worktree\\wave2.json",
            r"\\\\server\\share\\wave2.json",
            r"tmp\\implementation-builder-scoped-worktree\\..\\wave2.json",
            "tmp\\\\implementation-builder-scoped-worktree\\wave2.json",
        ):
            with self.subTest(reference=reference):
                result = binding.build_binding(
                    cohort_manifest_reference=reference,
                    handoff_reference=self.fixture.handoff_reference,
                    calibration_proof_reference=self.fixture.calibration_reference,
                    authorization_reference=self.fixture.authorization_reference,
                    root=self.root,
                    active_state=self.fixture.active_state(),
                    now=NOW,
                    strict_calibration_check=self.fixture.strict_check(),
                    owner_session_root=self.fixture.owner_session_root,
                )
                self.assertEqual(
                    result["code"],
                    "measurement_cohort_binding_frozen_reference_invalid",
                )

    def test_live_router_projection_without_changed_files_is_valid(self) -> None:
        strict = self.fixture.strict_check()
        del strict["evidence"]["worktree"]["changed_files"]
        payload = self.build(strict=strict)
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn(
            "changed_files", payload["calibration"]["strict_projection"]["worktree"]
        )

    def test_wrong_frozen_reference_and_digest_fail_closed(self) -> None:
        result = binding.build_binding(
            cohort_manifest_reference="tmp/implementation-builder-scoped-worktree/forged.json",
            handoff_reference=self.fixture.handoff_reference,
            calibration_proof_reference=self.fixture.calibration_reference,
            authorization_reference=self.fixture.authorization_reference,
            root=self.root,
            active_state=self.fixture.active_state(),
            now=NOW,
            strict_calibration_check=self.fixture.strict_check(),
        )
        self.assertEqual(result["code"], "measurement_cohort_binding_frozen_reference_invalid")

        manifest_path = self.root / self.fixture.manifest_reference
        manifest_path.write_text("{}\n", encoding="utf-8")
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_frozen_hash_mismatch")

    def test_stale_or_shallow_calibration_never_mints_binding(self) -> None:
        calibration_path = self.root / self.fixture.calibration_reference
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        calibration["expires_at_utc"] = "2026-08-25T11:30:00Z"
        json_write(calibration_path, calibration)
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_calibration_expired")

        self.fixture.write_sources()
        strict = {"status": "error", "code": "persistent_transport_config_mismatch"}
        self.assertEqual(
            self.build(strict=strict)["code"],
            "measurement_cohort_binding_calibration_strict_invalid",
        )

    def test_self_asserted_authorization_scope_tampering_and_revocation_fail_closed(self) -> None:
        result = binding.build_binding(
            cohort_manifest_reference=self.fixture.manifest_reference,
            handoff_reference=self.fixture.handoff_reference,
            calibration_proof_reference=self.fixture.calibration_reference,
            authorization_reference="memory/owner-approvals/self-authored.json",
            root=self.root,
            active_state=self.fixture.active_state(),
            now=NOW,
            strict_calibration_check=self.fixture.strict_check(),
            owner_session_root=self.fixture.owner_session_root,
        )
        self.assertEqual(result["code"], "measurement_cohort_binding_authorization_reference_invalid")

        self.fixture.write_owner_approval(
            binding._owner_approval_statement(
                self.fixture.approval_id,
                "0" * 64,
                "2026-08-25T13:00:00Z",
            )
        )
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_authorization_invalid")

        self.fixture.write_sources()
        self.fixture.append_owner_revocation()
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_authorization_revoked")

        self.fixture.write_sources()
        expected_scope = {
            "schema": "veritas.wave2_cohort_dispatch_scope.v1",
            "cohort_id": binding.COHORT_ID,
            "cohort_manifest_reference": binding.COHORT_MANIFEST_REFERENCE,
            "cohort_manifest_sha256": self.fixture.manifest_hash,
            "cohort_job_ids": [
                JOB_ID,
                JOB2_ID,
                *[f"wave2-cohort-fixture-job-{number:02d}" for number in range(3, 11)],
            ],
            "job1_anchor_handoff_reference": binding.HANDOFF_REFERENCE,
            "job1_anchor_handoff_sha256": self.fixture.handoff_hash,
            "calibration_proof_reference": self.fixture.calibration_reference,
            "calibration_proof_sha256": digest(
                (self.root / self.fixture.calibration_reference).read_bytes()
            ),
            "calibration_job_id": CALIBRATION_JOB_ID,
            "calibration_capability_only": True,
            "agent_id": binding.AGENT_ID,
            "execution_backend": "persistent_isolated_agent",
            "model_path": binding.TERRA_MODEL,
            "thinking": "low",
            "persistent_lane_mode": binding.LANE_MODE,
            "dispatch_order": "strictly_sequential",
            "cohort_dispatch_authorized": True,
            "supersedes_preparation_only_for_exact_frozen_cohort": True,
        }
        self.fixture.write_owner_approval(
            binding._owner_approval_statement(
                self.fixture.approval_id,
                binding._canonical_sha256(expected_scope),
                "2026-08-25T13:00:00Z",
            ),
            sender_is_owner=False,
        )
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_authorization_source_invalid")

        self.fixture.write_sources()
        self.fixture.write_owner_approval(
            binding._owner_approval_statement(
                self.fixture.approval_id,
                binding._canonical_sha256(expected_scope),
                "2026-08-25T12:15:00Z",
            )
        )
        self.assertEqual(
            self.build()["code"],
            "measurement_cohort_binding_authorization_expiry_insufficient",
        )

    def test_bounded_long_owner_transcript_remains_verifiable(self) -> None:
        transcript = (
            self.fixture.owner_session_root
            / f"{self.fixture.owner_session_id}.jsonl"
        )
        padding = {"type": "padding", "content": "x" * 8_100_000}
        with transcript.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(padding, sort_keys=True) + "\n")
        self.assertGreater(transcript.stat().st_size, 8_000_000)
        self.assertLess(transcript.stat().st_size, binding.MAX_OWNER_TRANSCRIPT_BYTES)
        self.assertEqual(self.build()["status"], "ok")

    def test_source_active_worktree_and_strict_projection_drift_fail_closed(self) -> None:
        payload = self.build()
        self.assertEqual(payload["status"], "ok")
        (self.root / PATHS[0]).write_text("drift\n", encoding="utf-8")
        self.assertEqual(
            self.validate(payload)["code"],
            "measurement_cohort_binding_source_hash_mismatch",
        )

        self.fixture.write_sources()
        payload = self.build()
        payload["active_worktree"]["baseline_commit"] = "0" * 40
        self.assertEqual(
            self.validate(payload)["code"],
            "measurement_cohort_binding_active_worktree_drift",
        )

        payload = self.build()
        payload["calibration"]["strict_projection"]["runtime"]["config_sha256"] = "0" * 64
        self.assertEqual(
            self.validate(payload)["code"],
            "measurement_cohort_binding_calibration_strict_invalid",
        )

    def test_calibration_job_route_and_path_mismatch_fail_closed(self) -> None:
        calibration_path = self.root / self.fixture.calibration_reference
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        calibration["runtime"]["thinking"] = "medium"
        json_write(calibration_path, calibration)
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_calibration_invalid")

        self.fixture.write_sources()
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        calibration["evidence"]["worktree"]["job_id"] = JOB_ID
        json_write(calibration_path, calibration)
        self.assertEqual(self.build()["code"], "measurement_cohort_binding_calibration_invalid")


if __name__ == "__main__":
    unittest.main()
