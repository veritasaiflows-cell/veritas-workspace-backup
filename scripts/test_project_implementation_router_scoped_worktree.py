#!/usr/bin/env python3
"""Focused unit checks for persistent scoped-worktree proof routing."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# The scoped handoff intentionally carries only the router and this focused test.
# Stub unrelated runtime helpers so pure proof/parser tests stay self-contained.
sys.modules.setdefault("long_work_packet_linter", types.ModuleType("long_work_packet_linter"))
_market_data_utils = types.ModuleType("market_data_utils")
_market_data_utils.atomic_write_json = lambda *args, **kwargs: None
_market_data_utils.load_json_artifact = lambda *args, **kwargs: {}
sys.modules.setdefault("market_data_utils", _market_data_utils)
_lib = types.ModuleType("lib")
_lib.__path__ = []
_terminal_outcome = types.ModuleType("lib.terminal_outcome")
_terminal_outcome.contract_block = lambda: {}
sys.modules.setdefault("lib", _lib)
sys.modules.setdefault("lib.terminal_outcome", _terminal_outcome)

import project_implementation_router as router

NOW = datetime(2026, 8, 23, 12, 30, tzinfo=timezone.utc)
CONFIG_SHA256 = "a" * 64
AGENT_ID = "implementation-builder"
OPENCLAW_VERSION = "2026.8.1"
JOB_ID = "router-scoped-worktree-capability-20260823-r1"
CHANGED_PATHS = [
    "scripts/project_implementation_router.py",
    "scripts/test_project_implementation_router_scoped_worktree.py",
]
ATTACHMENT_ID = "43e0a0ee-840c-4e1a-a7bc-3b823a29faec"
ATTACHMENT_NAME = "attachment-probe-40kb.txt"
ATTACHMENT_REFERENCE = f"tmp/implementation-builder-scoped-worktree/{ATTACHMENT_NAME}"
ATTACHMENT_RUNTIME_LABEL = f".openclaw/attachments/{ATTACHMENT_ID}/{ATTACHMENT_NAME}"
ATTACHMENT_SANDBOX_PATH = f"/attachments/{ATTACHMENT_ID}/{ATTACHMENT_NAME}"
RUNTIME_PROBE_REFERENCE = "tmp/implementation-builder-scoped-worktree/runtime-probe.json"
PATCH_REFERENCE = "tmp/implementation-builder-scoped-worktree/probe.patch"
CLOSE_REFERENCE = "tmp/implementation-builder-scoped-worktree/probe-close.json"
CALIBRATION_JOB_ID = f"{JOB_ID}-calibration"
CALIBRATION_MANIFEST_REFERENCE = (
    f"{router.PERSISTENT_RETAINED_MANIFEST_PREFIX}{CALIBRATION_JOB_ID}/handoff-manifest.json"
)


def run_git_checked(git_executable: str, root: Path, *args: str) -> None:
    completed = subprocess.run(
        [git_executable, "-C", str(root), *args],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))


def prepare_inspection_fixture(root: Path, git_executable: str) -> tuple[dict[str, object], Path, Path]:
    evidence_root = root / "tmp" / "implementation-builder-scoped-worktree"
    worktree_root = root / "scoped-worktree"
    evidence_root.mkdir(parents=True)
    (worktree_root / "scripts").mkdir(parents=True)

    (evidence_root / ATTACHMENT_NAME).write_text("alpha\nbeta\n", encoding="utf-8")
    (evidence_root / "runtime-probe.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    (evidence_root / "probe.patch").write_text("bounded patch\n", encoding="utf-8")
    (evidence_root / "probe-close.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    (worktree_root / "handoff-manifest.json").write_text(
        json.dumps({"allowed_write_paths": CHANGED_PATHS}), encoding="utf-8"
    )
    tracked_path = worktree_root / CHANGED_PATHS[0]
    untracked_path = worktree_root / CHANGED_PATHS[1]
    tracked_path.write_text("baseline\n", encoding="utf-8")

    run_git_checked(git_executable, worktree_root, "init", "--quiet")
    run_git_checked(git_executable, worktree_root, "config", "user.name", "Scoped Test")
    run_git_checked(git_executable, worktree_root, "config", "user.email", "scoped@example.invalid")
    run_git_checked(
        git_executable,
        worktree_root,
        "add",
        "--",
        "handoff-manifest.json",
        CHANGED_PATHS[0],
    )
    run_git_checked(git_executable, worktree_root, "commit", "--quiet", "-m", "baseline")
    tracked_path.write_text("changed tracked file\n", encoding="utf-8")
    untracked_path.write_text("new untracked file\n", encoding="utf-8")

    payload: dict[str, object] = {
        "evidence": {
            "attachment": {
                "reference": ATTACHMENT_REFERENCE,
                "runtime_probe_reference": RUNTIME_PROBE_REFERENCE,
            },
            "worktree": {
                "manifest_reference": router.PERSISTENT_SCOPED_MANIFEST_REFERENCE,
                "patch_reference": PATCH_REFERENCE,
                "close_proof_reference": CLOSE_REFERENCE,
                "changed_paths": list(CHANGED_PATHS),
            },
        }
    }
    return payload, evidence_root, worktree_root


def scoped_v2_payload() -> dict[str, object]:
    return {
        "schema": router.PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA,
        "status": "ok",
        "observed_at_utc": "2026-08-23T12:00:00Z",
        "expires_at_utc": "2026-08-23T13:00:00Z",
        "agent_id": AGENT_ID,
        "runtime": {
            "execution_backend": "persistent_isolated_agent",
            "provider": "openai",
            "model": router.NATIVE_MODEL,
            "thinking": "high",
            "openclaw_version": OPENCLAW_VERSION,
            "config_sha256": CONFIG_SHA256,
        },
        "capabilities": {
            "attachment_context_transport": True,
            "scoped_worktree_implementation": True,
            "shared_main_workspace_access": False,
        },
        "evidence": {
            "attachment": {
                "reference": ATTACHMENT_REFERENCE,
                "bytes": 123,
                "line_count": 4,
                "sha256": "b" * 64,
                "runtime_label": ATTACHMENT_RUNTIME_LABEL,
                "sandbox_path": ATTACHMENT_SANDBOX_PATH,
                "mount_mode": "read_only",
                "runtime_probe_reference": RUNTIME_PROBE_REFERENCE,
                "runtime_probe_sha256": "2" * 64,
            },
            "worktree": {
                "job_id": JOB_ID,
                "baseline_commit": "c" * 40,
                "manifest_reference": router.PERSISTENT_SCOPED_MANIFEST_REFERENCE,
                "manifest_sha256": "d" * 64,
                "patch_reference": PATCH_REFERENCE,
                "patch_sha256": "e" * 64,
                "close_proof_reference": CLOSE_REFERENCE,
                "close_proof_sha256": "f" * 64,
                "changed_paths": list(CHANGED_PATHS),
                "git_path_inventory_sha256": inventory_sha256(),
            },
            "negative_controls": {
                "main_workspace_read_blocked": True,
                "network_blocked": True,
                "protected_mount_writes_blocked": True,
                "out_of_scope_write_blocked": True,
                "unexpected_changed_paths_empty": True,
            },
        },
    }


def scoped_v3_payload() -> dict[str, object]:
    payload = copy.deepcopy(scoped_v2_payload())
    payload["schema"] = router.PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA
    payload["runtime"]["thinking"] = "low"  # type: ignore[index]
    payload["evidence"]["worktree"]["job_id"] = CALIBRATION_JOB_ID  # type: ignore[index]
    payload["evidence"]["worktree"]["manifest_reference"] = CALIBRATION_MANIFEST_REFERENCE  # type: ignore[index]
    return payload


def runtime_probe_payload() -> dict[str, object]:
    return {
        "schema": "veritas.implementation_builder_transport_probe_runtime.v1",
        "status": "ok",
        "observed_at_utc": "2026-08-23T12:00:00Z",
        "attachment": {
            "name": ATTACHMENT_NAME,
            "runtime_label": ATTACHMENT_RUNTIME_LABEL,
            "sandbox_path": ATTACHMENT_SANDBOX_PATH,
            "mount_mode": "read_only",
            "bytes": 123,
            "lines": 4,
            "sha256": "b" * 64,
            "match": True,
            "write_blocked": True,
        },
        "worktree": {
            "manifest_sha256": "d" * 64,
            "router_sha256": "1" * 64,
            "test_sha256": "3" * 64,
            "git_head": "c" * 40,
            "git_path_inventory_sha256": inventory_sha256(),
            "all_match": True,
        },
        "negative_controls": {
            "main_workspace_read_blocked": True,
            "network_blocked": True,
            "attachment_write_blocked": True,
            "role_write_blocked": True,
            "git_metadata_write_blocked": True,
            "manifest_write_blocked": True,
            "sentinel_write_blocked": True,
        },
        "backend_identity": {
            "agent_id": AGENT_ID,
            "execution_backend": "persistent_isolated_agent",
            "provider": "openai",
            "model": router.NATIVE_MODEL,
            "thinking": "high",
        },
        "writes_attempted_but_blocked": True,
        "writes_completed": False,
        "network_attempted": True,
        "error": None,
        "main_acceptance_claimed": False,
    }


def runtime_probe_v3_payload() -> dict[str, object]:
    payload = copy.deepcopy(runtime_probe_payload())
    payload["schema"] = "veritas.implementation_builder_transport_probe_runtime.v2"
    payload["backend_identity"]["thinking"] = "low"  # type: ignore[index]
    payload["worktree"] = {
        "manifest_sha256": "d" * 64,
        "git_head": "c" * 40,
        "git_path_inventory_sha256": inventory_sha256(),
        "changed_files": [
            {"relative_path": CHANGED_PATHS[0], "sha256": "1" * 64},
            {"relative_path": CHANGED_PATHS[1], "sha256": "3" * 64},
        ],
        "all_match": True,
    }
    return payload


def inventory_checkpoint(
    *,
    paths: list[str] | None = None,
    tracked_paths: list[str] | None = None,
    untracked_paths: list[str] | None = None,
) -> dict[str, object]:
    resolved_paths = sorted(paths if paths is not None else CHANGED_PATHS)
    resolved_tracked = sorted(tracked_paths if tracked_paths is not None else [CHANGED_PATHS[0]])
    resolved_untracked = sorted(untracked_paths if untracked_paths is not None else [CHANGED_PATHS[1]])
    return {
        "paths": resolved_paths,
        "status_paths": list(resolved_paths),
        "tracked_diff_paths": resolved_tracked,
        "untracked_paths": resolved_untracked,
        "status_porcelain_sha256": "4" * 64,
        "tracked_diff_output_sha256": "5" * 64,
        "untracked_output_sha256": "6" * 64,
    }


def inventory_checkpoints() -> dict[str, object]:
    return {
        "before_binding_recheck": inventory_checkpoint(),
        "after_binding_recheck": inventory_checkpoint(),
    }


def inventory_sha256() -> str:
    digest = router._git_inventory_checkpoints_sha256(
        inventory_checkpoints(), CHANGED_PATHS
    )
    if digest is None:
        raise AssertionError("test inventory fixture must be digestible")
    return digest


def verified_evidence() -> dict[str, object]:
    return {
        "status": "ok",
        "code": "ok",
        "attachment": {
            "reference": ATTACHMENT_REFERENCE,
            "bytes": 123,
            "line_count": 4,
            "sha256": "b" * 64,
            "runtime_probe_reference": RUNTIME_PROBE_REFERENCE,
            "runtime_probe_sha256": "2" * 64,
            "runtime_probe": runtime_probe_payload(),
        },
        "worktree": {
            "manifest_reference": router.PERSISTENT_SCOPED_MANIFEST_REFERENCE,
            "manifest_sha256": "d" * 64,
            "patch_reference": PATCH_REFERENCE,
            "patch_sha256": "e" * 64,
            "close_proof_reference": CLOSE_REFERENCE,
            "close_proof_sha256": "f" * 64,
            "git_path_inventory_sha256": inventory_sha256(),
            "baseline_commit": "c" * 40,
            "changed_files": [
                {
                    "relative_path": CHANGED_PATHS[0],
                    "exists": True,
                    "bytes": 321,
                    "sha256": "1" * 64,
                },
                {
                    "relative_path": CHANGED_PATHS[1],
                    "exists": True,
                    "bytes": 654,
                    "sha256": "3" * 64,
                }
            ],
            "manifest": {
                "schema": "veritas.implementation_builder_worktree_manifest.v1",
                "job_id": JOB_ID,
                "allowed_write_paths": list(CHANGED_PATHS),
                "authority": {
                    "external_delivery_allowed": False,
                    "main_acceptance_required": True,
                    "network_allowed": False,
                    "runtime_config_mutation_allowed": False,
                    "writable_root": "/worktree",
                },
            },
            "close_proof": {
                "schema": "veritas.implementation_builder_worktree_proof.v1",
                "action": "close",
                "status": "ok",
                "job_id": JOB_ID,
                "baseline_commit": "c" * 40,
                "manifest_sha256": "d" * 64,
                "patch_sha256": "e" * 64,
                "tracked_diff_sha256": "e" * 64,
                "changed_file_count": 2,
                "allowed_write_paths": list(CHANGED_PATHS),
                "unexpected_changed_paths": [],
                "patch_includes_declared_new_files": True,
                "git_path_inventory_checkpoints": inventory_checkpoints(),
                "git_path_inventory_sha256": inventory_sha256(),
                "changed_files": [
                    {
                        "relative_path": CHANGED_PATHS[0],
                        "exists": True,
                        "bytes": 321,
                        "sha256": "1" * 64,
                    },
                    {
                        "relative_path": CHANGED_PATHS[1],
                        "exists": True,
                        "bytes": 654,
                        "sha256": "3" * 64,
                    }
                ],
            },
            "git_path_inventory_checkpoints": inventory_checkpoints(),
            "git_path_inventory_sha256": inventory_sha256(),
        },
    }


def verified_v3_evidence() -> dict[str, object]:
    evidence = copy.deepcopy(verified_evidence())
    evidence["attachment"]["runtime_probe"] = runtime_probe_v3_payload()  # type: ignore[index]
    evidence["worktree"]["manifest_reference"] = CALIBRATION_MANIFEST_REFERENCE  # type: ignore[index]
    evidence["worktree"]["manifest"]["job_id"] = CALIBRATION_JOB_ID  # type: ignore[index]
    evidence["worktree"]["close_proof"]["job_id"] = CALIBRATION_JOB_ID  # type: ignore[index]
    return evidence


def validate_scoped(
    payload: dict[str, object],
    *,
    config_sha256: str = CONFIG_SHA256,
    expected_thinking: str = "high",
    openclaw_version: str = OPENCLAW_VERSION,
    evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    return router.validate_persistent_transport_proof_payload(
        payload,
        AGENT_ID,
        "scoped_worktree_implementation",
        config_sha256,
        NOW,
        expected_thinking=expected_thinking,
        current_openclaw_version=openclaw_version,
        verified_evidence=evidence if evidence is not None else verified_evidence(),
    )


def patch_draft_v1_payload() -> dict[str, object]:
    return {
        "schema": router.PERSISTENT_TRANSPORT_PROOF_SCHEMA,
        "status": "ok",
        "observed_at_utc": "2026-08-23T12:00:00Z",
        "agent_id": AGENT_ID,
        "capabilities": {
            "attachment_context_transport": True,
            "shared_main_workspace_access": False,
        },
    }


class PersistentScopedWorktreeProofTests(unittest.TestCase):
    def test_equal_inventory_with_cross_surface_digest_is_accepted(self) -> None:
        check = validate_scoped(scoped_v2_payload())
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["code"], "ok")
        self.assertEqual(check["persistent_lane_mode"], "scoped_worktree_implementation")
        self.assertEqual(check["required_capability"], "scoped_worktree_implementation")
        self.assertEqual(
            check["evidence"]["worktree"]["git_path_inventory_sha256"],
            inventory_sha256(),
        )

    def test_v3_retained_low_calibration_accepts_exact_generic_changed_files(self) -> None:
        check = validate_scoped(
            scoped_v3_payload(),
            expected_thinking="low",
            evidence=verified_v3_evidence(),
        )
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["proof_schema"], router.PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA)
        mismatch = validate_scoped(
            scoped_v3_payload(),
            expected_thinking="medium",
            evidence=verified_v3_evidence(),
        )
        self.assertEqual(mismatch["code"], "persistent_transport_thinking_mismatch")

    def test_v3_generic_probe_rejects_changed_file_tampering(self) -> None:
        evidence = verified_v3_evidence()
        evidence["attachment"]["runtime_probe"]["worktree"]["changed_files"][0]["sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(
            scoped_v3_payload(),
            expected_thinking="low",
            evidence=evidence,
        )
        self.assertEqual(check["code"], "persistent_transport_runtime_probe_worktree_mismatch")

    def test_inventory_digest_is_canonical_across_mapping_insertion_order(self) -> None:
        checkpoints = inventory_checkpoints()
        reversed_checkpoints = {
            "after_binding_recheck": dict(
                reversed(
                    list(checkpoints["after_binding_recheck"].items())  # type: ignore[union-attr]
                )
            ),
            "before_binding_recheck": dict(
                reversed(
                    list(checkpoints["before_binding_recheck"].items())  # type: ignore[union-attr]
                )
            ),
        }
        self.assertEqual(
            router._git_inventory_checkpoints_sha256(
                checkpoints, CHANGED_PATHS
            ),
            router._git_inventory_checkpoints_sha256(
                reversed_checkpoints, CHANGED_PATHS
            ),
        )

    def test_missing_or_malformed_outer_inventory_digest_is_rejected(self) -> None:
        for replacement in (None, "A" * 64, "0" * 63):
            with self.subTest(replacement=replacement):
                payload = scoped_v2_payload()
                if replacement is None:
                    payload["evidence"]["worktree"].pop(  # type: ignore[index,union-attr]
                        "git_path_inventory_sha256"
                    )
                else:
                    payload["evidence"]["worktree"][  # type: ignore[index]
                        "git_path_inventory_sha256"
                    ] = replacement
                check = validate_scoped(payload)
                self.assertEqual(
                    check["code"], "persistent_transport_proof_schema_invalid"
                )

    def test_close_runtime_and_active_inventory_digest_mismatches_are_rejected(self) -> None:
        cases = (
            ("close", "persistent_transport_close_proof_contract_mismatch"),
            ("runtime", "persistent_transport_runtime_probe_worktree_mismatch"),
            ("active", "persistent_transport_worktree_inventory_digest_mismatch"),
        )
        for surface, expected_code in cases:
            with self.subTest(surface=surface):
                evidence = verified_evidence()
                if surface == "close":
                    evidence["worktree"]["close_proof"][  # type: ignore[index]
                        "git_path_inventory_sha256"
                    ] = "0" * 64
                elif surface == "runtime":
                    evidence["attachment"]["runtime_probe"]["worktree"][  # type: ignore[index]
                        "git_path_inventory_sha256"
                    ] = "0" * 64
                else:
                    evidence["worktree"][  # type: ignore[index]
                        "git_path_inventory_sha256"
                    ] = "0" * 64
                check = validate_scoped(scoped_v2_payload(), evidence=evidence)
                self.assertEqual(check["code"], expected_code)

    def test_inventory_with_extra_path_is_rejected(self) -> None:
        evidence = verified_evidence()
        extra_path = "scripts/unexpected.py"
        for checkpoint in evidence["worktree"]["git_path_inventory_checkpoints"].values():  # type: ignore[index,union-attr]
            checkpoint.update(  # type: ignore[union-attr]
                inventory_checkpoint(
                    paths=[*CHANGED_PATHS, extra_path],
                    tracked_paths=[CHANGED_PATHS[0]],
                    untracked_paths=[CHANGED_PATHS[1], extra_path],
                )
            )
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_worktree_inventory_mismatch")

    def test_inventory_missing_declared_path_is_rejected(self) -> None:
        evidence = verified_evidence()
        for checkpoint in evidence["worktree"]["git_path_inventory_checkpoints"].values():  # type: ignore[index,union-attr]
            checkpoint.update(  # type: ignore[union-attr]
                inventory_checkpoint(
                    paths=[CHANGED_PATHS[0]],
                    tracked_paths=[CHANGED_PATHS[0]],
                    untracked_paths=[],
                )
            )
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_worktree_inventory_mismatch")

    def test_attachment_only_v1_is_rejected_for_scoped_mode(self) -> None:
        check = validate_scoped(patch_draft_v1_payload())
        self.assertEqual(check["status"], "error")
        self.assertEqual(check["code"], "persistent_transport_proof_schema_invalid")

    def test_false_negative_control_is_rejected(self) -> None:
        payload = scoped_v2_payload()
        payload["evidence"]["negative_controls"]["network_blocked"] = False  # type: ignore[index]
        check = validate_scoped(payload)
        self.assertEqual(check["code"], "persistent_transport_negative_control_failed")

    def test_config_fingerprint_mismatch_is_rejected(self) -> None:
        check = validate_scoped(scoped_v2_payload(), config_sha256="f" * 64)
        self.assertEqual(check["code"], "persistent_transport_config_mismatch")

    def test_shared_main_workspace_access_is_rejected(self) -> None:
        payload = scoped_v2_payload()
        payload["capabilities"]["shared_main_workspace_access"] = True  # type: ignore[index]
        check = validate_scoped(payload)
        self.assertEqual(check["code"], "persistent_transport_capability_missing")

    def test_scoped_mode_still_requires_attachment_transport(self) -> None:
        payload = scoped_v2_payload()
        payload["capabilities"]["attachment_context_transport"] = False  # type: ignore[index]
        check = validate_scoped(payload)
        self.assertEqual(check["code"], "persistent_transport_capability_missing")

    def test_thinking_mismatch_is_rejected(self) -> None:
        check = validate_scoped(scoped_v2_payload(), expected_thinking="medium")
        self.assertEqual(check["code"], "persistent_transport_thinking_mismatch")

    def test_runtime_version_mismatch_is_rejected(self) -> None:
        check = validate_scoped(scoped_v2_payload(), openclaw_version="2026.8.2")
        self.assertEqual(check["code"], "persistent_transport_runtime_version_mismatch")

    def test_missing_byte_verification_is_rejected(self) -> None:
        check = validate_scoped(scoped_v2_payload(), evidence={})
        self.assertEqual(check["code"], "persistent_transport_evidence_unverified")

    def test_attachment_hash_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["attachment"]["sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_attachment_hash_mismatch")

    def test_attachment_reference_outside_scoped_evidence_root_is_rejected(self) -> None:
        payload = scoped_v2_payload()
        payload["evidence"]["attachment"]["reference"] = "MEMORY.md"  # type: ignore[index]
        check = validate_scoped(payload)
        self.assertEqual(check["code"], "persistent_transport_proof_schema_invalid")

    def test_attachment_runtime_mapping_mismatch_is_rejected(self) -> None:
        payload = scoped_v2_payload()
        payload["evidence"]["attachment"]["sandbox_path"] = "/attachments/wrong/probe.txt"  # type: ignore[index]
        check = validate_scoped(payload)
        self.assertEqual(check["code"], "persistent_transport_proof_schema_invalid")

    def test_runtime_probe_hash_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["attachment"]["runtime_probe_sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_runtime_probe_hash_mismatch")

    def test_runtime_probe_contract_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["attachment"]["runtime_probe"]["negative_controls"]["network_blocked"] = False  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_runtime_probe_contract_mismatch")

    def test_runtime_probe_worktree_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["attachment"]["runtime_probe"]["worktree"]["router_sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_runtime_probe_worktree_mismatch")

    def test_manifest_hash_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["worktree"]["manifest_sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_manifest_hash_mismatch")

    def test_patch_hash_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["worktree"]["patch_sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_patch_hash_mismatch")

    def test_close_proof_contract_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["worktree"]["close_proof"]["unexpected_changed_paths"] = ["escape.txt"]  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_close_proof_contract_mismatch")

    def test_active_worktree_head_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["worktree"]["baseline_commit"] = "0" * 40  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_worktree_head_mismatch")

    def test_active_changed_file_hash_mismatch_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["worktree"]["changed_files"][0]["sha256"] = "0" * 64  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_changed_file_hash_mismatch")

    def test_manifest_with_broader_write_scope_is_rejected(self) -> None:
        evidence = verified_evidence()
        evidence["worktree"]["manifest"]["allowed_write_paths"].append("scripts/extra.py")  # type: ignore[index]
        check = validate_scoped(scoped_v2_payload(), evidence=evidence)
        self.assertEqual(check["code"], "persistent_transport_manifest_contract_mismatch")

    def test_patch_draft_v1_compatibility_is_preserved(self) -> None:
        check = router.validate_persistent_transport_proof_payload(
            patch_draft_v1_payload(), AGENT_ID, "patch_draft", None, NOW
        )
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["required_capability"], "attachment_context_transport")

    def test_inspector_captures_tracked_and_untracked_inventory_at_both_checkpoints(self) -> None:
        git_executable = shutil.which("git")
        if git_executable is None:
            self.skipTest("Git is required for scoped-worktree inventory checks")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            payload, evidence_root, worktree_root = prepare_inspection_fixture(
                temporary_root, git_executable
            )
            with (
                patch.object(router, "ROOT", temporary_root),
                patch.object(router, "PERSISTENT_SCOPED_EVIDENCE_ROOT", evidence_root),
                patch.object(router, "PERSISTENT_SCOPED_WORKTREE_ROOT", worktree_root),
            ):
                inspected = router._inspect_persistent_evidence(payload)
        self.assertEqual(inspected["status"], "ok")
        checkpoints = inspected["worktree"]["git_path_inventory_checkpoints"]  # type: ignore[index]
        before = checkpoints["before_binding_recheck"]
        after = checkpoints["after_binding_recheck"]
        self.assertEqual(before, after)
        self.assertEqual(before["paths"], CHANGED_PATHS)
        self.assertEqual(before["status_paths"], CHANGED_PATHS)
        self.assertEqual(before["tracked_diff_paths"], [CHANGED_PATHS[0]])
        self.assertEqual(before["untracked_paths"], [CHANGED_PATHS[1]])

    def test_v3_inspector_uses_retained_calibration_worktree_not_active_mount(self) -> None:
        git_executable = shutil.which("git")
        if git_executable is None:
            self.skipTest("Git is required for scoped-worktree inventory checks")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            payload, evidence_root, active_root = prepare_inspection_fixture(
                temporary_root, git_executable
            )
            retained_base = temporary_root / "completed"
            retained_root = retained_base / CALIBRATION_JOB_ID
            retained_base.mkdir()
            shutil.move(str(active_root), str(retained_root))
            payload["schema"] = router.PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA
            payload["evidence"]["worktree"]["job_id"] = CALIBRATION_JOB_ID  # type: ignore[index]
            payload["evidence"]["worktree"]["manifest_reference"] = CALIBRATION_MANIFEST_REFERENCE  # type: ignore[index]
            with (
                patch.object(router, "ROOT", temporary_root),
                patch.object(router, "PERSISTENT_SCOPED_EVIDENCE_ROOT", evidence_root),
                patch.object(router, "PERSISTENT_SCOPED_WORKTREE_ROOT", temporary_root / "active-job1"),
                patch.object(router, "PERSISTENT_RETAINED_WORKTREE_ROOT", retained_base),
            ):
                inspected = router._inspect_persistent_evidence(payload)
        self.assertEqual(inspected["status"], "ok")
        self.assertEqual(
            inspected["worktree"]["manifest_reference"],
            CALIBRATION_MANIFEST_REFERENCE,
        )

    def test_inspector_rejects_path_inventory_change_between_checkpoints(self) -> None:
        git_executable = shutil.which("git")
        if git_executable is None:
            self.skipTest("Git is required for scoped-worktree inventory checks")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            payload, evidence_root, worktree_root = prepare_inspection_fixture(
                temporary_root, git_executable
            )
            original_binding_check = router._binding_unchanged
            mutation_injected = False

            def binding_check_with_mutation(binding: dict[str, object], *, max_bytes: int) -> bool:
                nonlocal mutation_injected
                unchanged = original_binding_check(binding, max_bytes=max_bytes)
                if not mutation_injected:
                    (worktree_root / "unexpected.txt").write_text("late mutation\n", encoding="utf-8")
                    mutation_injected = True
                return unchanged

            with (
                patch.object(router, "ROOT", temporary_root),
                patch.object(router, "PERSISTENT_SCOPED_EVIDENCE_ROOT", evidence_root),
                patch.object(router, "PERSISTENT_SCOPED_WORKTREE_ROOT", worktree_root),
                patch.object(router, "_binding_unchanged", side_effect=binding_check_with_mutation),
            ):
                inspected = router._inspect_persistent_evidence(payload)
        self.assertEqual(inspected["status"], "error")
        self.assertEqual(inspected["code"], "persistent_transport_evidence_changed_during_validation")

    def test_inspector_rejects_stable_unexpected_path_inventory(self) -> None:
        git_executable = shutil.which("git")
        if git_executable is None:
            self.skipTest("Git is required for scoped-worktree inventory checks")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            payload, evidence_root, worktree_root = prepare_inspection_fixture(
                temporary_root, git_executable
            )
            (worktree_root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            with (
                patch.object(router, "ROOT", temporary_root),
                patch.object(router, "PERSISTENT_SCOPED_EVIDENCE_ROOT", evidence_root),
                patch.object(router, "PERSISTENT_SCOPED_WORKTREE_ROOT", worktree_root),
            ):
                inspected = router._inspect_persistent_evidence(payload)
        self.assertEqual(inspected["status"], "error")
        self.assertEqual(inspected["code"], "persistent_transport_worktree_inventory_mismatch")

    def test_preconsumption_revalidation_projects_fresh_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            proof_path = temporary_root / "proof.json"
            config_path = temporary_root / "openclaw.json"
            proof_path.write_text("{}\n", encoding="utf-8")
            config_path.write_text("{}\n", encoding="utf-8")
            evidence = verified_evidence()
            checked = {
                "status": "ok",
                "code": "ok",
                "evidence": {"worktree": {}},
            }
            with (
                patch.object(router, "ROOT", temporary_root),
                patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", config_path),
                patch.object(router, "_active_openclaw_version", return_value=OPENCLAW_VERSION),
                patch.object(router, "_inspect_persistent_evidence", side_effect=[evidence, copy.deepcopy(evidence)]),
                patch.object(router, "validate_persistent_transport_proof_payload", return_value=checked),
            ):
                result = router.inspect_persistent_transport_proof(
                    "proof.json", AGENT_ID, "scoped_worktree_implementation", "high"
                )
        self.assertEqual(result["status"], "ok")
        projection = result["evidence"]["worktree"]["preconsumption_revalidation"]
        self.assertEqual(projection["baseline_commit"], "c" * 40)
        self.assertEqual(projection["git_path_inventory_sha256"], inventory_sha256())
        self.assertEqual(projection["patch_sha256"], "e" * 64)
        self.assertEqual(projection["close_proof_sha256"], "f" * 64)
        self.assertEqual(projection["changed_files"], evidence["worktree"]["changed_files"])  # type: ignore[index]

    def test_preconsumption_revalidation_rejects_any_consumed_binding_change(self) -> None:
        mutations = {
            "head": ("baseline_commit", "0" * 40),
            "inventory": ("git_path_inventory_sha256", "0" * 64),
            "manifest": ("manifest_sha256", "0" * 64),
            "patch": ("patch_sha256", "0" * 64),
            "close": ("close_proof_sha256", "0" * 64),
        }
        for label, (field, replacement) in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                temporary_root = Path(temporary)
                proof_path = temporary_root / "proof.json"
                config_path = temporary_root / "openclaw.json"
                proof_path.write_text("{}\n", encoding="utf-8")
                config_path.write_text("{}\n", encoding="utf-8")
                initial = verified_evidence()
                changed = copy.deepcopy(initial)
                changed["worktree"][field] = replacement  # type: ignore[index]
                checked = {
                    "status": "ok",
                    "code": "ok",
                    "evidence": {"worktree": {}},
                }
                with (
                    patch.object(router, "ROOT", temporary_root),
                    patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", config_path),
                    patch.object(router, "_active_openclaw_version", return_value=OPENCLAW_VERSION),
                    patch.object(router, "_inspect_persistent_evidence", side_effect=[initial, changed]),
                    patch.object(router, "validate_persistent_transport_proof_payload", return_value=checked),
                ):
                    result = router.inspect_persistent_transport_proof(
                        "proof.json", AGENT_ID, "scoped_worktree_implementation", "high"
                    )
                self.assertEqual(
                    result["code"],
                    "persistent_transport_evidence_changed_during_validation",
                )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            proof_path = temporary_root / "proof.json"
            config_path = temporary_root / "openclaw.json"
            proof_path.write_text("{}\n", encoding="utf-8")
            config_path.write_text("{}\n", encoding="utf-8")
            initial = verified_evidence()
            changed = copy.deepcopy(initial)
            changed["worktree"]["changed_files"][0]["sha256"] = "0" * 64  # type: ignore[index]
            with (
                patch.object(router, "ROOT", temporary_root),
                patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", config_path),
                patch.object(router, "_active_openclaw_version", return_value=OPENCLAW_VERSION),
                patch.object(router, "_inspect_persistent_evidence", side_effect=[initial, changed]),
                patch.object(
                    router,
                    "validate_persistent_transport_proof_payload",
                    return_value={"status": "ok", "code": "ok", "evidence": {"worktree": {}}},
                ),
            ):
                result = router.inspect_persistent_transport_proof(
                    "proof.json", AGENT_ID, "scoped_worktree_implementation", "high"
                )
            self.assertEqual(
                result["code"],
                "persistent_transport_evidence_changed_during_validation",
            )

    def test_parser_defaults_and_accepts_scoped_mode(self) -> None:
        with patch.object(sys, "argv", ["router"]):
            self.assertEqual(router.parse_args().persistent_lane_mode, "patch_draft")
        with patch.object(sys, "argv", ["router", "--persistent-lane-mode", "scoped_worktree_implementation"]):
            self.assertEqual(router.parse_args().persistent_lane_mode, "scoped_worktree_implementation")
        with patch.object(sys, "argv", ["router", "--measurement-cohort-binding", "tmp/implementation-builder-scoped-worktree/job1-binding.json"]):
            self.assertEqual(
                router.parse_args().measurement_cohort_binding,
                "tmp/implementation-builder-scoped-worktree/job1-binding.json",
            )


if __name__ == "__main__":
    unittest.main()
