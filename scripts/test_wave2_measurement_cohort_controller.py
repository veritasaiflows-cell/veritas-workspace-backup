#!/usr/bin/env python3
"""Focused adversarial tests for the strict Wave 2 cohort controller."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import concurrent_lane_manager as lanes
import implementation_builder_worktree_manager as worktrees
import isolated_agent_usage_metadata as usage_metadata
import measurement_cohort_transport_binding as bindings
import wave2_measurement_cohort_controller as controller


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_prefixed_hash(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + sha256_bytes(raw)


def write_json(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_bytes(path.read_bytes())


def git(root: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=text,
        check=True,
    )


class ControllerFixture:
    def __init__(self, base: Path) -> None:
        self.root = base / "workspace"
        self.root.mkdir(parents=True)
        self.controller_root = (
            self.root
            / "tmp"
            / "implementation-builder-scoped-worktree"
            / "wave2-cohort-controller-v1"
        )
        self.manifest_path = self.root / controller.MANIFEST_REFERENCE
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / controller.MANIFEST_REFERENCE).read_bytes()
        self.manifest_path.write_bytes(raw)
        self.manifest = json.loads(raw.decode("utf-8"))
        self.register_path = self.root / "tmp" / "concurrent-lane-register.json"
        self.owner_session_root = base / "owner-sessions"
        self.owner_session_root.mkdir(parents=True)
        self.owner_session_id = "11111111-1111-4111-8111-111111111111"
        self.owner_message_id = "22222222-2222-4222-8222-222222222222"
        self.owner_issued_at = "2026-08-26T05:00:00Z"
        self.owner_expires_at = "2099-08-26T06:00:00Z"
        self.owner_approval_content = "\n".join(
            (
                bindings.OWNER_APPROVAL_HEADER,
                "approval_id=wave2-cohort-10-job-dispatch-20260826",
                "scope_sha256=ae3d50483e4f9f722b4460d1bfb9d985d59ed352809a76e6c0465a64c3b863d8",
                f"expires_at_utc={self.owner_expires_at}",
            )
        )
        owner_header = json.dumps(
            {"type": "session", "id": self.owner_session_id},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        owner_event = json.dumps(
            {
                "type": "message",
                "id": self.owner_message_id,
                "timestamp": self.owner_issued_at,
                "message": {
                    "role": "user",
                    "sourceChannel": "webchat",
                    "content": self.owner_approval_content,
                    "__openclaw": {"senderIsOwner": True},
                    "provenance": {"kind": "external"},
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.owner_event_sha256 = sha256_bytes(owner_event)
        (self.owner_session_root / f"{self.owner_session_id}.jsonl").write_bytes(
            owner_header + b"\n" + owner_event + b"\n"
        )

    def copy_job_files(self, number: int) -> None:
        job = self.manifest["jobs"][number - 1]
        for row in job["write_files"]:
            target = self.root / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = git(
                ROOT,
                "show",
                f"HEAD:{row['path']}",
                text=False,
            ).stdout
            if not isinstance(payload, bytes) or sha256_bytes(payload) != row["sha256"]:
                raise AssertionError(f"frozen Git preimage mismatch: {row['path']}")
            target.write_bytes(payload)

    def init_git(self) -> None:
        git(self.root, "init")
        git(self.root, "add", "--all")
        git(
            self.root,
            "-c",
            "user.name=Wave2 Test",
            "-c",
            "user.email=wave2@example.invalid",
            "commit",
            "-m",
            "frozen",
        )

    def admission_lane(
        self, *, number: int = 1, attempt_number: int = 1
    ) -> dict[str, object]:
        job = self.manifest["jobs"][number - 1]
        lane: dict[str, object] = {
            "lane_id": (
                f"WAVE2::cohort-job-{number:02d}-fixture-a{attempt_number}"
            ),
            "workflow_id": "WAVE2",
            "workstream_id": (
                f"cohort-job-{number:02d}-fixture-a{attempt_number}"
            ),
            "status": "leased",
            "owner": controller.AGENT_ID,
            "created_at_utc": (
                "2026-08-26T06:00:00Z"
                if attempt_number == 1
                else "2026-08-26T06:10:00Z"
            ),
            "allowed_writes": sorted(row["path"] for row in job["write_files"]),
            "runtime": {
                "agent_id": controller.AGENT_ID,
                "agent_role": "implementation_builder",
                "parent_job_id": job["job_id"],
                "phase": "implementation",
                "model_path": controller.MODEL_PATH,
                "thinking": controller.THINKING,
                "expected_model_path": controller.MODEL_PATH,
                "expected_thinking": controller.THINKING,
                "expected_execution_backend": controller.BACKEND,
                "max_elapsed_seconds": controller.JOB_MAX_ELAPSED_SECONDS,
                "max_tool_calls": controller.JOB_MAX_TOOL_CALLS,
                "attempt_number": attempt_number,
                "attempt_id": (
                    f"wave2-job-{number:02d}-attempt-{attempt_number}"
                ),
                "retry_count": attempt_number - 1,
                "is_first_attempt": attempt_number == 1,
                "incident_code": "",
                "incident_count": 0,
            },
            "outcome_events": [],
        }
        runtime = lane["runtime"]
        assert isinstance(runtime, dict)
        correlation = lanes.expected_attempt_correlation(lane, runtime)
        runtime["attempt_correlation"] = correlation
        return lane

    def write_register(self, *job_lanes: dict[str, object]) -> None:
        register = lanes.empty_register()
        register["lanes"] = list(job_lanes)
        write_json(self.register_path, register)

    def write_restart_packet(self) -> str:
        instrument: dict[str, str] = {}
        for reference in controller.FROZEN_INSTRUMENT_REFERENCES:
            target = self.root / reference
            if reference != controller.MANIFEST_REFERENCE:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / reference).read_bytes())
            instrument[reference] = sha256_bytes(target.read_bytes())
        qualification = {
            "schema": controller.QUALIFICATION_SCHEMA,
            "status": "ok",
            "cohort_id": controller.COHORT_ID,
            "qualified_job_numbers": list(range(2, 11)),
            "credit_awarded": False,
            "provider_dispatch_performed": False,
            "wave2_resumed": False,
        }
        qualification_path = self.root / controller.QUALIFICATION_REFERENCE
        qualification_sha256 = write_json(qualification_path, qualification)
        packet = {
            "schema": controller.RESTART_PACKET_SCHEMA,
            "status": "frozen_pending_explicit_owner_resume",
            "generated_at_utc": "2026-08-26T05:30:00Z",
            "cohort_id": controller.COHORT_ID,
            "existing_qualifying_credit_count": 1,
            "restart_job_numbers": list(range(2, 11)),
            "expected_attempt_number_by_job": {
                str(number): attempt
                for number, attempt in sorted(
                    controller.RESTART_EXPECTED_ATTEMPTS.items()
                )
            },
            "frozen_instrument_sha256": instrument,
            "qualification": {
                "reference": controller.QUALIFICATION_REFERENCE,
                "sha256": qualification_sha256,
            },
            "stop_rules": {
                "max_elapsed_seconds": controller.JOB_MAX_ELAPSED_SECONDS,
                "checkpoint_seconds": controller.JOB_CHECKPOINT_SECONDS,
                "max_tool_calls": controller.JOB_MAX_TOOL_CALLS,
                "attempts_per_restart_pass": 1,
                "same_pass_repairs": 0,
                "independent_qa_lanes": 0,
                "max_active_cohort_jobs": 1,
                "stop_on_first_failure": True,
            },
            "authority_boundary": {
                "explicit_owner_resume_required": True,
                "resume_authorized": False,
                "provider_dispatch_authorized": False,
                "cohort_credit_granted": False,
            },
        }
        return write_json(self.root / controller.RESTART_PACKET_REFERENCE, packet)

    def incident_lane(
        self,
        *,
        number: int = 1,
        attempt_number: int = 1,
        prior_lanes: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        lane = self.admission_lane(number=number, attempt_number=attempt_number)
        runtime = lane["runtime"]
        assert isinstance(runtime, dict)
        run_id = "4c91958d-fa38-4615-bb80-47ed93944d84"
        session_key = (
            "agent:implementation-builder:subagent:"
            "5563d8a3-3742-4e80-bce6-eb5f68ee39ec"
        )
        session_id = "d84b33c9-3a05-473e-a6fd-e35d67645d4f"
        if number == 1 and attempt_number == 1:
            lane["lane_id"] = (
                "WAVE2::cohort-job-01-compact-exec-cwd-20260826-a1"
            )
            lane["workstream_id"] = (
                "cohort-job-01-compact-exec-cwd-20260826-a1"
            )
            runtime["attempt_id"] = "wave2-cohort-job-01-a1"
        elif number == 1 and attempt_number == 2:
            lane["lane_id"] = (
                "WAVE2::cohort-job-01-compact-exec-cwd-20260826-a2"
            )
            lane["workstream_id"] = (
                "cohort-job-01-compact-exec-cwd-20260826-a2"
            )
            runtime["attempt_id"] = "wave2-cohort-job-01-a2"
            run_id = "f9294b8e-e8ac-41c4-85b1-253c4fd0a145"
            session_key = (
                "agent:implementation-builder:subagent:"
                "dd77521f-678c-4591-b038-6b6bf8f84301"
            )
            session_id = "56e9ce23-c7a4-4b1b-9693-252e50c94861"
        runtime["attempt_correlation"] = lanes.expected_attempt_correlation(
            lane, runtime
        )
        base_time = datetime(2026, 8, 26, 6, 0, tzinfo=timezone.utc) + timedelta(
            minutes=10 * (attempt_number - 1)
        )

        def fixture_time(offset_minutes: int) -> str:
            return (base_time + timedelta(minutes=offset_minutes)).isoformat().replace(
                "+00:00", "Z"
            )

        lane["status"] = "blocked"
        lane["started_at_utc"] = fixture_time(2)
        lane["ended_at_utc"] = fixture_time(5)
        runtime.update(
            {
                "actual_execution_backend": controller.BACKEND,
                "incident_code": "packaging_path_error",
                "incident_count": 1,
                "validator_result": "not_run",
                "outcome_status": "blocked_before_source_preflight",
                "closure_durability": "verified",
                "main_acceptance_status": "rejected",
                "main_acceptance_evidence": (
                    "tmp/implementation-builder-scoped-worktree/"
                    "wave2-cohort-controller-v1/"
                    f"job-{number:02d}/attempt-{attempt_number:02d}-incident.json"
                ),
                "outcome_event_kind": "incident",
                "outcome_event_sequence": 1,
                "outcome_recorded_at_utc": fixture_time(5),
                "session_key_hash": sha256_bytes(session_key.encode("utf-8"))[:24],
                "session_id_hash": sha256_bytes(session_id.encode("utf-8"))[:24],
                "dispatch_binding": {
                    "registry_run_id_hash": sha256_bytes(run_id.encode("utf-8"))
                },
            }
        )
        lane["outcome_events"] = [
            {
                "event_kind": "incident",
                "event_sequence": 1,
                "recorded_at_utc": fixture_time(5),
            }
        ]
        incident_path = (
            self.controller_root
            / f"job-{number:02d}"
            / f"attempt-{attempt_number:02d}-incident.json"
        )
        incident_reference = controller._artifact_reference(
            incident_path, root=self.root
        )
        lane["proof_artifacts"] = [incident_reference]
        binding_reference = self.write_binding()
        binding_path = self.root / binding_reference
        admission_path = controller._admission_path(
            self.controller_root, number, attempt_number
        )
        job = self.manifest["jobs"][number - 1]
        write_json(
            admission_path,
            {
                "schema": controller.ADMISSION_SCHEMA,
                "status": "ok",
                "generated_at_utc": fixture_time(1),
                "expires_at_utc": "2099-08-26T06:00:00Z",
                "cohort": {
                    "cohort_id": controller.COHORT_ID,
                    "manifest_reference": controller.MANIFEST_REFERENCE,
                    "manifest_sha256": controller.MANIFEST_SHA256,
                },
                "job": {
                    "job_number": number,
                    "job_id": job["job_id"],
                    "source_file_hashes": copy.deepcopy(job["write_files"]),
                    "focused_test": job.get("focused_test"),
                    "compile_test": job.get("compile_test"),
                },
                "sequence": {
                    "previous_credited_count": number - 1,
                    "expected_job_number": number,
                    "contiguous": True,
                    "other_active_cohort_job": False,
                },
                "binding": {
                    "reference": binding_reference,
                    "sha256": sha256_bytes(binding_path.read_bytes()),
                    "schema": "veritas.measurement_cohort_transport_binding.v2",
                    "calibration_proof_reference": (
                        "tmp/implementation-builder-scoped-worktree/"
                        "fixture-calibration.json"
                    ),
                    "calibration_job_id": job["job_id"] + "-calibration",
                    "calibration_allowed_write_paths": sorted(
                        row["path"] for row in job["write_files"]
                    ),
                },
                "lane": {
                    "lane_id": lane["lane_id"],
                    "workflow_id": lane["workflow_id"],
                    "workstream_id": lane["workstream_id"],
                    "created_at_utc": lane["created_at_utc"],
                    "allowed_write_paths": sorted(lane["allowed_writes"]),
                },
                "route": {
                    **controller.EXPECTED_ROUTE,
                    "fallback_allowed": False,
                    "cwd_override_allowed": False,
                },
                "attempt": controller._attempt_projection(lane),
                "attempt_history": controller._attempt_history_projection(
                    prior_lanes or [],
                    job=job,
                    root=self.root,
                    controller_root=self.controller_root,
                ),
                "authority_boundary": {
                    **controller.AUTHORITY_BOUNDARY,
                    "measurement_admission_ready": True,
                    "cohort_credit_granted": False,
                },
                "errors": [],
            },
        )
        write_json(
            incident_path,
            {
                "schema": "veritas.wave2_measurement_job_incident.v1",
                "generated_at_utc": fixture_time(4),
                "cohort_id": controller.COHORT_ID,
                "job_id": self.manifest["jobs"][number - 1]["job_id"],
                "job_number": number,
                "attempt": {
                    "attempt_id": runtime["attempt_id"],
                    "attempt_number": attempt_number,
                    "retry_count": attempt_number - 1,
                    "first_pass": attempt_number == 1,
                    "task_name": usage_metadata.task_name_for_attempt(
                        attempt_correlation_hash=runtime["attempt_correlation"][
                            "key_hash"
                        ]
                    ),
                    "run_id": run_id,
                    "session_key": session_key,
                    "session_id": session_id,
                },
                "route": {
                    "expected_execution_backend": controller.BACKEND,
                    "expected_agent_id": controller.AGENT_ID,
                    "expected_model": controller.MODEL_PATH,
                    "expected_thinking": controller.THINKING,
                    "launch_status": "accepted",
                    "resolved_provider": "openai",
                    "resolved_model": controller.MODEL_PATH,
                    "model_applied": True,
                    "fallback_observed": False,
                },
                "incident": {
                    "code": "packaging_path_error",
                    "status": "terminal_attempt_failure",
                    "stage": "scoped_worktree_preflight",
                    "summary": "Fixture stopped before source preflight.",
                    "provider_connection_failed": False,
                    "subprocess_started": False,
                    "source_write_performed": False,
                    "out_of_scope_write_performed": False,
                    "required_tests_run": False,
                    "required_compile_run": False,
                    "retry_performed": False,
                },
                "measurement_disposition": {
                    "main_accepted": False,
                    "cohort_credit_granted": False,
                    "first_pass_success_credit": False,
                    "usage_credit_pending_exact_import": True,
                    "wave3_effect": "none",
                },
                "next_safe_action": "Create one separately identified retry.",
                "authority_boundary": {
                    "wave3_authorized": False,
                    "finance_canon_portfolio_or_execution_authority": False,
                    "config_auth_runtime_mutation_authorized": False,
                    "external_action_authorized": False,
                },
            },
        )
        return lane

    def write_binding(self, number: int = 1) -> str:
        reference = (
            "tmp/implementation-builder-scoped-worktree/fixture-job-binding.json"
        )
        job = self.manifest["jobs"][0]
        selected_job = self.manifest["jobs"][number - 1]
        paths = sorted(row["path"] for row in job["write_files"])
        source_rows = sorted(
            copy.deepcopy(job["write_files"]), key=lambda row: row["path"]
        )
        selected_paths = sorted(
            row["path"] for row in selected_job["write_files"]
        )
        selected_source_rows = sorted(
            copy.deepcopy(selected_job["write_files"]),
            key=lambda row: row["path"],
        )
        handoff_reference = job["activation_handoff"]
        calibration_reference = (
            "tmp/implementation-builder-scoped-worktree/fixture-calibration.json"
        )
        handoff_files = [
            {
                "path": row["path"],
                "size_bytes": row["bytes"],
                "sha256": row["sha256"],
                "attachment_id": f"source-{index:02d}",
                "attachment_format": "raw_utf8_per_source_file.v1",
                "utf8": True,
                "compressed_or_bundle": False,
                "max_physical_line_bytes": 256,
            }
            for index, row in enumerate(source_rows, start=1)
        ]
        immutable_handoff = {
            "contract_version": 3,
            "base_path": ".",
            "budget": {
                "max_files": 2,
                "max_total_bytes": 120000,
                "max_context_tokens": 30000,
                "token_estimator": "utf8_bytes_div4_ceiling_v1",
            },
            "files": handoff_files,
            "transport": {
                "delivery_mode": controller.LANE_MODE,
                "attachment_format": "raw_utf8_per_source_file.v1",
                "one_source_file_per_attachment": True,
                "max_attachment_bytes": 40000,
                "max_physical_line_bytes": 40000,
                "compression_or_aggregate_bundle_allowed": False,
                "receiver_readback_required": True,
                "shared_workspace_writeback_verified": False,
            },
        }
        frozen_snapshot_id = canonical_prefixed_hash(immutable_handoff)
        contract_sha256 = canonical_prefixed_hash(
            {**immutable_handoff, "frozen_snapshot_id": frozen_snapshot_id}
        )
        observed = {
            "file_count": 2,
            "total_bytes": sum(row["bytes"] for row in source_rows),
            "estimated_context_tokens": (
                sum(row["bytes"] for row in source_rows) + 3
            )
            // 4,
        }
        preflight = {
            "status": "ok",
            "checks": [
                {"name": "explicit_base_path", "ok": True},
                {"name": "context_files_resolve_inside_base", "ok": True},
                {"name": "context_file_budget", "ok": True},
                {"name": "context_byte_budget", "ok": True},
                {"name": "context_token_budget", "ok": True},
                {"name": "raw_utf8_source_attachments", "ok": True},
                {
                    "name": "compressed_or_aggregate_attachments_rejected",
                    "ok": True,
                },
                {"name": "attachment_reader_limits", "ok": True},
                {"name": "receiver_readback_required", "ok": True},
            ],
            "errors": [],
        }
        preflight["fingerprint"] = canonical_prefixed_hash(preflight)
        frozen_handoff = {
            **immutable_handoff,
            "observed": observed,
            "frozen_snapshot_id": frozen_snapshot_id,
            "contract_sha256": contract_sha256,
            "preflight": preflight,
        }
        handoff_authority = {
            "review_only": True,
            "helper_final_authority": False,
            "main_session_final_integrator": True,
            "cron_or_heartbeat_may_spawn": False,
            "config_auth_channel_runtime_mutation_allowed": False,
            "cleanup_move_delete_archive_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "sql_or_ticker_import_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        }
        handoff_sha256 = write_json(
            self.root / handoff_reference,
            {
                "schema": "veritas.helper_lane_manifest.v3",
                "generated_at_utc": "2026-08-26T05:30:00Z",
                "swarm_id": "WAVE2-FIXTURE",
                "status": "ok",
                "activation_job_contract": {
                    "schema": "veritas.wave2_job_activation_contract.v1",
                    "bound_at_utc": "2026-08-26T05:31:00Z",
                    "job_id": job["job_id"],
                    "source_root": str(self.root),
                    "source_base_label": "fixture frozen baseline",
                    "allowed_files": paths,
                    "allowed_outputs": [],
                    "transient_test_output_contract": "none",
                    "old_rejected_source_hold_path": str(self.root / "old-hold"),
                    "fresh_worktree_rollback_hold_path": str(
                        self.root / "rollback-hold"
                    ),
                    "sibling_sentinel_rollback_hold_path": str(
                        self.root / "sentinel-hold.json"
                    ),
                    "objective": job["objective"],
                    "acceptance_commands": [
                        job["focused_test"],
                        job["compile_test"],
                    ],
                    "stop_lines": ["fixture stop line"],
                },
                "expected_lanes": [
                    {
                        "lane_id": "WAVE2::FIXTURE::JOB-01",
                        "status": "pending",
                        "packet_id": "WAVE2-FIXTURE-JOB-01",
                        "session_id": "",
                        "session_label": "",
                        "owner_workflow": "WAVE2",
                        "started_at_utc": "2026-08-26T05:30:00Z",
                        "updated_at_utc": "2026-08-26T05:30:00Z",
                        "verdict": "awaiting_fixture_dispatch",
                        "required_artifacts": [
                            {"path": path, "kind": "file"} for path in paths
                        ],
                        "allow_partial": False,
                        "handoff": frozen_handoff,
                        "attempt": {},
                        "incident": {},
                        "authority_boundary": handoff_authority,
                    }
                ],
                "authority_boundary": handoff_authority,
                "use_rule": "fixture",
                "validation": {"status": "ok", "errors": [], "warnings": []},
            },
        )
        calibration_runtime = {
            "execution_backend": controller.BACKEND,
            "provider": "openai",
            "model": controller.MODEL_PATH,
            "thinking": controller.THINKING,
            "openclaw_version": "fixture",
            "config_sha256": "c" * 64,
        }
        calibration_worktree = {
            "job_id": job["job_id"] + "-calibration",
            "baseline_commit": "1" * 40,
            "manifest_reference": "retained_completed_worktree/fixture/handoff-manifest.json",
            "manifest_sha256": "2" * 64,
            "changed_paths": paths,
            "git_path_inventory_sha256": "3" * 64,
        }
        calibration_sha256 = write_json(
            self.root / calibration_reference,
            {
                "schema": "veritas.persistent_transport_proof.v3",
                "status": "ok",
                "observed_at_utc": "2026-08-26T05:00:00Z",
                "expires_at_utc": "2099-08-26T06:00:00Z",
                "agent_id": controller.AGENT_ID,
                "runtime": calibration_runtime,
                "capabilities": {
                    "attachment_context_transport": True,
                    "scoped_worktree_implementation": True,
                    "shared_main_workspace_access": False,
                },
                "evidence": {
                    "attachment": {},
                    "worktree": calibration_worktree,
                    "negative_controls": {},
                },
            },
        )
        write_json(
            self.root / reference,
            {
                "schema": "veritas.measurement_cohort_transport_binding.v2",
                "status": "ok",
                "generated_at_utc": "2026-08-26T06:00:00Z",
                "expires_at_utc": "2099-08-26T06:00:00Z",
                "cohort": {
                    "cohort_id": controller.COHORT_ID,
                    "manifest_reference": controller.MANIFEST_REFERENCE,
                    "manifest_sha256": controller.MANIFEST_SHA256,
                },
                "handoff": {
                    "reference": handoff_reference,
                    "sha256": handoff_sha256,
                    "frozen_snapshot_id": frozen_snapshot_id,
                    "contract_sha256": contract_sha256,
                },
                "job": {
                    "job_number": number,
                    "job_id": selected_job["job_id"],
                    "allowed_write_paths": selected_paths,
                    "source_file_hashes": selected_source_rows,
                },
                "calibration": {
                    "reference": calibration_reference,
                    "sha256": calibration_sha256,
                    "job_id": job["job_id"] + "-calibration",
                    "changed_paths": paths,
                    "strict_projection": {
                        "proof_schema": "veritas.persistent_transport_proof.v3",
                        "runtime": calibration_runtime,
                        "worktree": calibration_worktree,
                    },
                },
                "authorization": {
                    "schema": "veritas.wave2_cohort_dispatch_authorization.v3",
                    "approval_id": "wave2-cohort-10-job-dispatch-20260826",
                    "scope_sha256": "ae3d50483e4f9f722b4460d1bfb9d985d59ed352809a76e6c0465a64c3b863d8",
                    "expires_at_utc": self.owner_expires_at,
                    "issued_at_utc": self.owner_issued_at,
                    "reference": (
                        "openclaw-owner-approval/"
                        f"{self.owner_session_id}/{self.owner_message_id}"
                    ),
                    "source_event_sha256": self.owner_event_sha256,
                    "source_message_id": self.owner_message_id,
                    "source_session_id": self.owner_session_id,
                },
                "active_worktree": {
                    "job_id": selected_job["job_id"],
                    "baseline_commit": "4" * 40,
                    "manifest_sha256": "5" * 64,
                    "allowed_write_paths": selected_paths,
                    "source_file_hashes": selected_source_rows,
                },
                "route": {
                    "execution_backend": controller.BACKEND,
                    "model_path": controller.MODEL_PATH,
                    "thinking": controller.THINKING,
                    "agent_id": controller.AGENT_ID,
                    "persistent_lane_mode": controller.LANE_MODE,
                },
                "authority_boundary": {
                    "measurement_only": True,
                    "protected_dispatch_binding_created": False,
                    "usage_receipt_created": False,
                    "cohort_credit_granted": False,
                    "config_auth_runtime_mutation_allowed": False,
                    "finance_canon_portfolio_or_execution_authority": False,
                    "external_delivery_allowed": False,
                    "owner_approval_inferred": False,
                },
            },
        )
        return reference

    def binding_check(self, number: int = 1) -> dict[str, object]:
        job = self.manifest["jobs"][number - 1]
        return {
            "status": "ok",
            "code": "ok",
            "cohort_id": controller.COHORT_ID,
            "job_number": number,
            "job_id": job["job_id"],
            "allowed_write_paths": sorted(row["path"] for row in job["write_files"]),
            "calibration_proof_reference": (
                "tmp/implementation-builder-scoped-worktree/fixture-calibration.json"
            ),
            "calibration_job_id": "wave2-cohort-job-01-compact-exec-cwd-calibration",
            "calibration_allowed_write_paths": [
                "scripts/compact_exec.py",
                "scripts/test_compact_exec.py",
            ],
            "route": dict(controller.EXPECTED_ROUTE),
            "expires_at_utc": "2099-08-26T06:00:00Z",
        }


class Wave2ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.fixture = ControllerFixture(self.base)
        self.original_owner_session_root = bindings.OWNER_SESSION_ROOT
        bindings.OWNER_SESSION_ROOT = self.fixture.owner_session_root

    def tearDown(self) -> None:
        bindings.OWNER_SESSION_ROOT = self.original_owner_session_root
        self.temporary.cleanup()

    def load_manifest(self) -> dict[str, object]:
        return controller.load_frozen_manifest(root=self.fixture.root)

    def test_exact_manifest_and_zero_credit_status(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.init_git()
        status = controller.derive_status(
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["qualifying_jobs"], 0)
        self.assertEqual(status["next_job"]["job_number"], 1)
        self.assertFalse(status["wave3_review"]["wave3_review_gate_met"])

    def test_restart_packet_freezes_the_complete_measuring_instrument(self) -> None:
        packet_sha256 = self.fixture.write_restart_packet()
        packet, observed_sha256 = controller.load_frozen_restart_packet(
            root=self.fixture.root
        )
        self.assertEqual(observed_sha256, packet_sha256)
        self.assertEqual(packet["restart_job_numbers"], list(range(2, 11)))
        self.assertFalse(packet["authority_boundary"]["resume_authorized"])

        controller_copy = (
            self.fixture.root / "scripts/wave2_measurement_cohort_controller.py"
        )
        controller_copy.write_bytes(controller_copy.read_bytes() + b"\n")
        with self.assertRaisesRegex(
            controller.CohortError,
            "restart_instrument_drift:scripts/wave2_measurement_cohort_controller.py",
        ):
            controller.load_frozen_restart_packet(root=self.fixture.root)

    def test_restart_lane_budgets_are_executable_and_fail_closed(self) -> None:
        job = self.fixture.manifest["jobs"][1]
        lane = self.fixture.admission_lane(number=2, attempt_number=2)
        self.assertNotIn(
            "lane_max_elapsed_seconds_mismatch",
            controller._lane_contract_errors(
                lane, job, terminal=False, attempt_number=2
            ),
        )
        lane["runtime"]["max_elapsed_seconds"] = 901
        self.assertIn(
            "lane_max_elapsed_seconds_mismatch",
            controller._lane_contract_errors(
                lane, job, terminal=False, attempt_number=2
            ),
        )

        terminal, _source = self._terminal_lane_and_source(
            number=2, attempt_number=2
        )
        receipt_sidecar = controller._receipt_sidecar_reference(
            self.fixture.register_path, root=self.fixture.root
        )
        terminal["allowed_writes"] = sorted(
            [*terminal["allowed_writes"], receipt_sidecar]
        )
        terminal["runtime"]["observed_tool_calls"] = 17
        errors = controller._lane_contract_errors(
            terminal,
            job,
            terminal=True,
            receipt_sidecar=receipt_sidecar,
            attempt_number=2,
        )
        self.assertIn("lane_tool_budget_exceeded_or_unavailable", errors)

    def test_restart_forbids_lane_multiplication_and_enforces_checkpoint(self) -> None:
        self.fixture.write_restart_packet()
        packet, _packet_sha256 = controller.load_frozen_restart_packet(
            root=self.fixture.root
        )
        manifest = self.load_manifest()
        job3 = self.fixture.manifest["jobs"][2]
        current = self.fixture.admission_lane(number=3)
        qa_lane = copy.deepcopy(current)
        qa_lane["lane_id"] = "WAVE2::job03-forbidden-qa"
        qa_lane["workstream_id"] = "job03-forbidden-qa"
        qa_lane["status"] = "blocked"
        qa_lane["runtime"]["phase"] = "qa"
        register = lanes.empty_register()
        register["lanes"] = [current, qa_lane]
        self.assertIn(
            "nested_repair_or_qa_lane_forbidden",
            controller._restart_topology_errors(
                register, current, manifest, packet
            ),
        )

        other_active = self.fixture.admission_lane(number=4)
        register["lanes"] = [current, other_active]
        self.assertIn(
            "only_one_active_cohort_job_required",
            controller._restart_topology_errors(
                register, current, manifest, packet
            ),
        )
        self.assertIn(
            "same_pass_repair_or_retry_forbidden",
            controller._restart_attempt_errors(
                job3,
                [current, self.fixture.admission_lane(number=3, attempt_number=2)],
            ),
        )

        terminal, _source = self._terminal_lane_and_source(number=3)
        terminal["completed_at_utc"] = "2026-08-26T06:06:00Z"
        terminal["runtime"]["outcome_recorded_at_utc"] = "2026-08-26T06:06:00Z"
        terminal["outcome_events"][0]["recorded_at_utc"] = "2026-08-26T06:06:00Z"
        self.assertEqual(
            controller._checkpoint_errors(
                terminal,
                job3,
                controller_root=self.fixture.controller_root,
                attempt_number=1,
            ),
            ["five_minute_checkpoint_missing_or_invalid"],
        )
        checkpoint = {
            "schema": controller.CHECKPOINT_SCHEMA,
            "status": "ok",
            "generated_at_utc": "2026-08-26T06:05:00Z",
            "cohort_id": controller.COHORT_ID,
            "job_id": job3["job_id"],
            "lane_id": terminal["lane_id"],
            "attempt_number": 1,
            "max_elapsed_seconds": controller.JOB_MAX_ELAPSED_SECONDS,
            "max_tool_calls": controller.JOB_MAX_TOOL_CALLS,
            "checkpoint_seconds": controller.JOB_CHECKPOINT_SECONDS,
            "observed_tool_calls": 8,
            "stop_required": False,
            "authority_boundary": {
                "checkpoint_only": True,
                "cohort_credit_granted": False,
                "provider_dispatch_authorized": False,
                "owner_approval_inferred": False,
            },
        }
        write_json(
            controller._checkpoint_path(self.fixture.controller_root, 3, 1),
            checkpoint,
        )
        self.assertEqual(
            controller._checkpoint_errors(
                terminal,
                job3,
                controller_root=self.fixture.controller_root,
                attempt_number=1,
            ),
            [],
        )

    def test_complete_job1_to_job10_restart_transition_and_job2_worktree(self) -> None:
        self.fixture.write_restart_packet()
        job1_credit, _paths = self._write_bound_job1_credit()
        write_json(
            controller._credit_path(self.fixture.controller_root, 1),
            job1_credit,
        )
        self.fixture.copy_job_files(2)
        prior = self.fixture.incident_lane(number=2, attempt_number=1)
        current = self.fixture.admission_lane(number=2, attempt_number=2)
        self.fixture.write_register(prior, current)
        binding_reference = self.fixture.write_binding(number=2)
        retained_history = [{"attempt_number": 1, "cohort_credit_granted": False}]
        with (
            patch.object(
                controller, "load_credit_chain", return_value=([job1_credit], [])
            ),
            patch.object(controller, "_preimage_errors", return_value=[]),
            patch.object(
                controller, "_prior_attempt_history_errors", return_value=[]
            ),
            patch.object(
                controller,
                "_attempt_history_projection",
                return_value=retained_history,
            ),
            patch.object(
                controller, "_utc_now", return_value="2026-08-26T06:11:00Z"
            ),
        ):
            job2_admission = controller.build_admission(
                binding_reference=binding_reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(2),
            )
        self.assertEqual(job2_admission["job"]["job_number"], 2)
        self.assertEqual(job2_admission["attempt"]["attempt_number"], 2)
        self.assertEqual(job2_admission["attempt_history"], retained_history)

        job2 = self.fixture.manifest["jobs"][1]
        handoff = self.base / "transition-handoff"
        target = handoff / "scoped-worktree"
        prepared = worktrees.prepare_worktree(
            job_id=job2["job_id"],
            source_root=self.fixture.root,
            source_base_label="fixture-job2",
            relative_paths=[row["path"] for row in job2["write_files"]],
            target=target,
            handoff_root=handoff,
        )
        self.assertEqual(prepared["file_count"], 2)
        self.assertTrue(
            worktrees.verify_worktree(target=target, handoff_root=handoff)["clean"]
        )
        changed_relative = job2["write_files"][1]["path"]
        changed_path = target.joinpath(*changed_relative.split("/"))
        changed_path.write_text(
            changed_path.read_text(encoding="utf-8")
            + "\n# model-free transition qualification\n",
            encoding="utf-8",
        )
        closed = worktrees.close_worktree(
            patch_path=self.base / "job2-transition.patch",
            target=target,
            handoff_root=handoff,
        )
        self.assertEqual(closed["changed_file_count"], 1)
        self.assertEqual(
            closed["changed_files"][0]["relative_path"], changed_relative
        )

        for number in range(3, 11):
            with self.subTest(job_number=number):
                lane = self.fixture.admission_lane(number=number)
                self.fixture.write_register(lane)
                reference = self.fixture.write_binding(number=number)
                prior_credits = [
                    {"generated_at_utc": "2026-08-26T05:59:00Z"}
                    for _index in range(number - 1)
                ]
                with (
                    patch.object(
                        controller,
                        "load_credit_chain",
                        return_value=(prior_credits, []),
                    ),
                    patch.object(controller, "_preimage_errors", return_value=[]),
                    patch.object(
                        controller,
                        "_utc_now",
                        return_value="2026-08-26T06:01:00Z",
                    ),
                ):
                    admission = controller.build_admission(
                        binding_reference=reference,
                        root=self.fixture.root,
                        controller_root=self.fixture.controller_root,
                        register_path=self.fixture.register_path,
                        binding_inspector=lambda _reference, n=number: (
                            self.fixture.binding_check(n)
                        ),
                    )
                self.assertEqual(admission["job"]["job_number"], number)
                self.assertEqual(admission["attempt"]["attempt_number"], 1)

    def test_manifest_hash_reorder_duplicate_and_three_file_job_fail(self) -> None:
        self.fixture.manifest_path.write_bytes(b"{}\n")
        with self.assertRaisesRegex(controller.CohortError, "manifest_hash_mismatch"):
            self.load_manifest()

        for mutator in (
            lambda payload: payload["jobs"].reverse(),
            lambda payload: payload["jobs"].__setitem__(
                1, {**payload["jobs"][1], "job_id": payload["jobs"][0]["job_id"]}
            ),
            lambda payload: payload["jobs"][0]["write_files"].append(
                copy.deepcopy(payload["jobs"][0]["write_files"][0])
            ),
        ):
            payload = copy.deepcopy(self.fixture.manifest)
            mutator(payload)
            digest = write_json(self.fixture.manifest_path, payload)
            with self.assertRaises(controller.CohortError):
                controller.load_frozen_manifest(
                    root=self.fixture.root, expected_sha256=digest
                )

    def test_admission_selects_only_next_job_and_emits_protected_task_name(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.init_git()
        lane = self.fixture.admission_lane()
        self.fixture.write_register(lane)
        reference = self.fixture.write_binding()
        payload = controller.build_admission(
            binding_reference=reference,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            register_path=self.fixture.register_path,
            binding_inspector=lambda _reference: self.fixture.binding_check(1),
        )
        self.assertEqual(payload["job"]["job_number"], 1)
        self.assertTrue(payload["attempt"]["dispatch_task_name"].startswith("vt1_"))
        self.assertEqual(len(payload["attempt"]["binding_token_hash"]), 64)
        self.assertFalse(payload["authority_boundary"]["cohort_credit_granted"])

        with self.assertRaisesRegex(controller.CohortError, "binding_projection_mismatch"):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(2),
            )

    def test_admission_rejects_route_attempt_and_collision_drift(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.init_git()
        reference = self.fixture.write_binding()
        lane = self.fixture.admission_lane()
        runtime = lane["runtime"]
        assert isinstance(runtime, dict)
        runtime["retry_count"] = 1
        self.fixture.write_register(lane)
        with self.assertRaisesRegex(controller.CohortError, "lane_attempt_sequence_mismatch"):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )
        lane = self.fixture.admission_lane()
        lane["runtime"]["retry_count"] = False
        self.fixture.write_register(lane)
        with self.assertRaisesRegex(controller.CohortError, "lane_attempt_sequence_mismatch"):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

    def test_admission_allows_only_contiguous_truthful_retry_history(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.init_git()
        reference = self.fixture.write_binding()
        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        self.fixture.write_register(prior, retry)
        payload = controller.build_admission(
            binding_reference=reference,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            register_path=self.fixture.register_path,
            binding_inspector=lambda _reference: self.fixture.binding_check(1),
        )
        self.assertEqual(payload["attempt"]["attempt_number"], 2)
        self.assertEqual(payload["attempt"]["retry_count"], 1)
        self.assertFalse(payload["attempt"]["incident_allowed"])
        self.assertEqual(len(payload["attempt_history"]), 1)
        self.assertFalse(payload["attempt_history"][0]["cohort_credit_granted"])
        for field in (
            "config_auth_runtime_mutation_allowed",
            "finance_canon_portfolio_or_execution_authority",
            "external_delivery_allowed",
            "wave3_authorized",
        ):
            self.assertFalse(payload["authority_boundary"][field])
        self.assertEqual(
            controller._admission_snapshot_errors(
                payload,
                self.fixture.manifest["jobs"][0],
                retry,
                [prior],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
            [],
        )
        for field, value in (
            ("attempt_number", True),
            ("retry_count", 0.0),
            ("incident_count", 1.0),
            ("cohort_credit_granted", 0),
        ):
            with self.subTest(history_field=field, value=value):
                history_alias = copy.deepcopy(payload)
                history_alias["attempt_history"][0][field] = value
                self.assertIn(
                    "admission_snapshot_contract_invalid",
                    controller._admission_snapshot_errors(
                        history_alias,
                        self.fixture.manifest["jobs"][0],
                        retry,
                        [prior],
                        root=self.fixture.root,
                        controller_root=self.fixture.controller_root,
                    ),
                )
        tampered_admission = copy.deepcopy(payload)
        tampered_admission["authority_boundary"][
            "config_auth_runtime_mutation_allowed"
        ] = True
        self.assertIn(
            "admission_snapshot_contract_invalid",
            controller._admission_snapshot_errors(
                tampered_admission,
                self.fixture.manifest["jobs"][0],
                retry,
                [prior],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )
        binding_payload = json.loads(
            (self.fixture.root / reference).read_text(encoding="utf-8")
        )
        self.assertEqual(
            controller._binding_snapshot_errors(
                binding_payload,
                self.fixture.manifest["jobs"][0],
                root=self.fixture.root,
            ),
            [],
        )
        for field, value in (
            ("route", {}),
            (
                "authority_boundary",
                {
                    **binding_payload["authority_boundary"],
                    "finance_canon_portfolio_or_execution_authority": True,
                },
            ),
            ("generated_at_utc", "not-a-time"),
        ):
            tampered_binding = copy.deepcopy(binding_payload)
            tampered_binding[field] = value
            self.assertTrue(
                controller._binding_snapshot_errors(
                    tampered_binding,
                    self.fixture.manifest["jobs"][0],
                    root=self.fixture.root,
                )
            )
        for field, value in (
            ("source_event_sha256", "not-hex"),
            ("source_message_id", "   "),
            ("source_session_id", ""),
        ):
            tampered_binding = copy.deepcopy(binding_payload)
            tampered_binding["authorization"][field] = value
            self.assertIn(
                "binding_snapshot_authorization_invalid",
                controller._binding_snapshot_errors(
                    tampered_binding,
                    self.fixture.manifest["jobs"][0],
                    root=self.fixture.root,
                ),
            )
        for field, value in (
            ("source_event_sha256", "d" * 64),
            ("source_message_id", "33333333-3333-4333-8333-333333333333"),
            ("source_session_id", "44444444-4444-4444-8444-444444444444"),
            ("issued_at_utc", "2026-08-26T05:00:01Z"),
            ("expires_at_utc", "2099-08-26T06:00:01Z"),
        ):
            tampered_binding = copy.deepcopy(binding_payload)
            tampered_binding["authorization"][field] = value
            self.assertIn(
                "binding_snapshot_authorization_source_invalid",
                controller._binding_snapshot_errors(
                    tampered_binding,
                    self.fixture.manifest["jobs"][0],
                    root=self.fixture.root,
                ),
            )
        missing_source = copy.deepcopy(binding_payload)
        missing_source["authorization"]["reference"] = (
            "openclaw-owner-approval/55555555-5555-4555-8555-555555555555/"
            "66666666-6666-4666-8666-666666666666"
        )
        self.assertIn(
            "binding_snapshot_authorization_source_unavailable",
            controller._binding_snapshot_errors(
                missing_source,
                self.fixture.manifest["jobs"][0],
                root=self.fixture.root,
            ),
        )
        transcript = (
            self.fixture.owner_session_root
            / f"{self.fixture.owner_session_id}.jsonl"
        )
        original_transcript = transcript.read_bytes()
        for mutation in ("content", "non_owner", "inter_session"):
            rows = original_transcript.splitlines()
            event = json.loads(rows[1].decode("utf-8"))
            if mutation == "content":
                event["message"]["content"] += "\nextra=true"
            elif mutation == "non_owner":
                event["message"]["__openclaw"]["senderIsOwner"] = False
            else:
                event["message"]["provenance"]["kind"] = "inter_session"
            rows[1] = json.dumps(
                event, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            transcript.write_bytes(b"\n".join(rows) + b"\n")
            try:
                self.assertIn(
                    "binding_snapshot_authorization_source_invalid",
                    controller._binding_snapshot_errors(
                        binding_payload,
                        self.fixture.manifest["jobs"][0],
                        root=self.fixture.root,
                    ),
                )
            finally:
                transcript.write_bytes(original_transcript)
        transcript.unlink()
        try:
            self.assertIn(
                "binding_snapshot_authorization_source_unavailable",
                controller._binding_snapshot_errors(
                    binding_payload,
                    self.fixture.manifest["jobs"][0],
                    root=self.fixture.root,
                ),
            )
        finally:
            transcript.write_bytes(original_transcript)

        for section, mutation, expected in (
            ("lane", lambda row: row.__setitem__("extra", True), "contract"),
            ("lane", lambda row: row.pop("workflow_id"), "contract"),
            (
                "lane",
                lambda row: row.__setitem__("workflow_id", "FORGED"),
                "contract",
            ),
            ("binding", lambda row: row.__setitem__("extra", True), "contract"),
            (
                "binding",
                lambda row: row.pop("calibration_job_id"),
                "contract",
            ),
            (
                "binding",
                lambda row: row.__setitem__(
                    "calibration_proof_reference", "tmp/forged.json"
                ),
                "binding_projection",
            ),
            (
                "binding",
                lambda row: row.__setitem__("calibration_job_id", "forged"),
                "binding_projection",
            ),
            (
                "binding",
                lambda row: row.__setitem__(
                    "calibration_allowed_write_paths", list(reversed(_job_paths))
                ),
                "binding_projection",
            ),
        ):
            nested = copy.deepcopy(payload)
            _job_paths = nested["binding"]["calibration_allowed_write_paths"]
            mutation(nested[section])
            self.assertTrue(
                any(
                    expected in error
                    for error in controller._admission_snapshot_errors(
                        nested,
                        self.fixture.manifest["jobs"][0],
                        retry,
                        [prior],
                        root=self.fixture.root,
                        controller_root=self.fixture.controller_root,
                    )
                )
            )
        tampered_expiry = copy.deepcopy(payload)
        tampered_expiry["expires_at_utc"] = "2099-08-26T06:00:01Z"
        self.assertIn(
            "admission_snapshot_binding_time_invalid",
            controller._admission_snapshot_errors(
                tampered_expiry,
                self.fixture.manifest["jobs"][0],
                retry,
                [prior],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )
        extra_field = copy.deepcopy(payload)
        extra_field["config_auth_runtime_mutation_allowed"] = True
        self.assertIn(
            "admission_snapshot_field_inventory_invalid",
            controller._admission_snapshot_errors(
                extra_field,
                self.fixture.manifest["jobs"][0],
                retry,
                [prior],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )
        self.assertEqual(
            len(payload["attempt_history"][0]["incident_evidence_sha256"]), 64
        )
        self.assertEqual(
            controller._admission_path(self.fixture.controller_root, 1).name,
            "admission.json",
        )
        self.assertEqual(
            controller._admission_path(self.fixture.controller_root, 1, 2).name,
            "attempt-02-admission.json",
        )

        for mutate, expected_error in (
            (
                lambda old, current: current["runtime"].__setitem__(
                    "attempt_number", 1
                ),
                "job_attempt_sequence_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "incident_code", ""
                ),
                "prior_attempt_1:incident_code_not_retryable",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "main_acceptance_status", "accepted"
                ),
                "prior_attempt_1:main_acceptance_not_rejected",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "model_path", "openai/gpt-5.5"
                ),
                "prior_attempt_1:runtime_model_path_mismatch",
            ),
            (
                lambda old, current: current.__setitem__(
                    "lane_id", old["lane_id"]
                ),
                "job_lane_id_reused",
            ),
            (
                lambda old, current: current.__setitem__(
                    "workstream_id", old["workstream_id"]
                ),
                "job_workstream_id_reused",
            ),
            (
                lambda old, current: current["runtime"].__setitem__(
                    "attempt_id", old["runtime"]["attempt_id"]
                ),
                "job_attempt_id_reused",
            ),
            (
                lambda old, current: current["runtime"].__setitem__(
                    "attempt_correlation",
                    copy.deepcopy(old["runtime"]["attempt_correlation"]),
                ),
                "job_attempt_correlation_reused",
            ),
            (
                lambda old, current: current.__setitem__(
                    "created_at_utc", "2026-08-26T06:04:59Z"
                ),
                "job_attempt_chronology_invalid",
            ),
            (
                lambda old, current: current.__setitem__(
                    "created_at_utc", "2026-08-26T06:05:00Z"
                ),
                "job_attempt_chronology_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "incident_count", 2
                ),
                "prior_attempt_1:incident_count_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "incident_count", True
                ),
                "prior_attempt_1:incident_count_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "attempt_number", True
                ),
                "job_attempt_number_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "retry_count", False
                ),
                "prior_attempt_1:attempt_sequence_mismatch",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "outcome_event_sequence", 2
                ),
                "prior_attempt_1:terminal_event_sequence_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "outcome_event_sequence", True
                ),
                "prior_attempt_1:terminal_event_sequence_invalid",
            ),
            (
                lambda old, current: old.pop("outcome_events"),
                "prior_attempt_1:outcome_events_inventory_invalid",
            ),
            (
                lambda old, current: old["outcome_events"].append(
                    copy.deepcopy(old["outcome_events"][0])
                ),
                "prior_attempt_1:outcome_events_inventory_invalid",
            ),
            (
                lambda old, current: old["outcome_events"][0].__setitem__(
                    "extra", True
                ),
                "prior_attempt_1:outcome_events_inventory_invalid",
            ),
            (
                lambda old, current: old["outcome_events"][0].__setitem__(
                    "event_sequence", True
                ),
                "prior_attempt_1:outcome_events_invalid",
            ),
            (
                lambda old, current: old["outcome_events"][0].__setitem__(
                    "recorded_at_utc", "2026-08-26T06:04:59Z"
                ),
                "prior_attempt_1:outcome_events_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "validator_result", "pass"
                ),
                "prior_attempt_1:validator_disposition_invalid",
            ),
            (
                lambda old, current: old["runtime"].__setitem__(
                    "outcome_status", "blocked"
                ),
                "prior_attempt_1:outcome_disposition_invalid",
            ),
        ):
            old = self.fixture.incident_lane()
            current = self.fixture.admission_lane(attempt_number=2)
            mutate(old, current)
            self.fixture.write_register(old, current)
            with self.assertRaisesRegex(controller.CohortError, expected_error):
                controller.build_admission(
                    binding_reference=reference,
                    root=self.fixture.root,
                    controller_root=self.fixture.controller_root,
                    register_path=self.fixture.register_path,
                    binding_inspector=lambda _reference: self.fixture.binding_check(1),
                )

        prior = self.fixture.incident_lane()
        retry = self.fixture.incident_lane(
            attempt_number=2,
            prior_lanes=[prior],
        )
        third = self.fixture.admission_lane(attempt_number=3)
        third["created_at_utc"] = "2026-08-26T06:20:00Z"
        repair_lane = self.fixture.admission_lane()
        repair_lane["lane_id"] = "WAVE2::job-01-control-repair"
        repair_lane["workstream_id"] = "job-01-control-repair"
        repair_lane["owner"] = "main-session"
        repair_lane["created_at_utc"] = "2026-08-26T06:15:00Z"
        repair_lane["allowed_writes"] = [
            "scripts/wave2_measurement_cohort_controller.py"
        ]
        repair_runtime = repair_lane["runtime"]
        assert isinstance(repair_runtime, dict)
        repair_runtime["agent_id"] = "main-session"
        repair_runtime["phase"] = "repair"
        repair_runtime["attempt_id"] = "wave2-job-01-control-repair-a1"
        repair_runtime["attempt_correlation"] = lanes.expected_attempt_correlation(
            repair_lane, repair_runtime
        )
        self.fixture.write_register(prior, retry, repair_lane, third)
        with self.assertRaisesRegex(
            controller.CohortError, "job_retry_limit_exceeded"
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        mislabeled_repair = copy.deepcopy(repair_lane)
        mislabeled_runtime = mislabeled_repair["runtime"]
        assert isinstance(mislabeled_runtime, dict)
        mislabeled_runtime["phase"] = "implementation"
        mislabeled_runtime["attempt_correlation"] = (
            lanes.expected_attempt_correlation(
                mislabeled_repair, mislabeled_runtime
            )
        )
        self.fixture.write_register(prior, retry, mislabeled_repair, third)
        with self.assertRaisesRegex(
            controller.CohortError, "job_retry_limit_exceeded"
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        fourth = self.fixture.admission_lane(attempt_number=4)
        fourth["created_at_utc"] = "2026-08-26T06:30:00Z"
        self.fixture.write_register(prior, retry, repair_lane, third, fourth)
        with self.assertRaisesRegex(
            controller.CohortError, "job_retry_limit_exceeded"
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        unmapped_job = self.fixture.manifest["jobs"][1]
        unmapped_register = lanes.empty_register()
        unmapped_register["lanes"] = [
            self.fixture.admission_lane(number=2, attempt_number=1),
            self.fixture.admission_lane(number=2, attempt_number=2),
            self.fixture.admission_lane(number=2, attempt_number=3),
        ]
        with self.assertRaisesRegex(
            controller.CohortError, "job_retry_limit_exceeded"
        ):
            controller._find_job_lanes(unmapped_register, unmapped_job)

        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        incident_path = self.fixture.controller_root / "job-01" / "attempt-01-incident.json"
        write_json(incident_path, {"schema": "tampered"})
        self.fixture.write_register(prior, retry)
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_attempt_1:incident_evidence_contract_invalid",
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        incident_path.unlink()
        self.fixture.write_register(prior, retry)
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_attempt_1:incident_evidence_unavailable",
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        payload = json.loads(incident_path.read_text(encoding="utf-8"))
        payload["attempt"]["attempt_id"] = "wrong-attempt-id"
        write_json(incident_path, payload)
        self.fixture.write_register(prior, retry)
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_attempt_1:incident_evidence_contract_invalid",
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        for section, field, value in (
            ("route", "resolved_provider", "forged"),
            ("incident", "required_compile_run", True),
            ("measurement_disposition", "wave3_effect", "authorized"),
            ("authority_boundary", "external_action_authorized", True),
            ("attempt", "run_id", "forged-run"),
            ("attempt", "session_key", "forged-session-key"),
            ("attempt", "session_id", "forged-session-id"),
        ):
            prior = self.fixture.incident_lane()
            retry = self.fixture.admission_lane(attempt_number=2)
            incident_payload = json.loads(
                incident_path.read_text(encoding="utf-8")
            )
            incident_payload[section][field] = value
            write_json(incident_path, incident_payload)
            self.fixture.write_register(prior, retry)
            with self.assertRaisesRegex(
                controller.CohortError,
                "prior_attempt_1:incident_evidence_",
            ):
                controller.build_admission(
                    binding_reference=reference,
                    root=self.fixture.root,
                    controller_root=self.fixture.controller_root,
                    register_path=self.fixture.register_path,
                    binding_inspector=lambda _reference: self.fixture.binding_check(1),
                )

        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        prior_admission_path = controller._admission_path(
            self.fixture.controller_root, 1
        )
        prior_admission = json.loads(
            prior_admission_path.read_text(encoding="utf-8")
        )
        prior_admission["binding"]["reference"] = (
            "tmp/implementation-builder-scoped-worktree/"
            "missing-prior-binding.json"
        )
        write_json(prior_admission_path, prior_admission)
        self.fixture.write_register(prior, retry)
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_attempt_1:prior_admission_binding_unavailable|prior_attempt_1:admission_snapshot_binding_unavailable",
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        prior_admission_path = controller._admission_path(
            self.fixture.controller_root, 1
        )
        prior_admission_path.unlink()
        self.fixture.write_register(prior, retry)
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_attempt_1:prior_admission_unavailable",
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        write_json(prior_admission_path, {"schema": "tampered"})
        self.fixture.write_register(prior, retry)
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_attempt_1:admission_snapshot_",
        ):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

        lane = self.fixture.admission_lane()
        other = {
            "lane_id": "WAVE2::collision",
            "status": "running",
            "allowed_writes": list(lane["allowed_writes"]),
            "runtime": {},
        }
        register = lanes.empty_register()
        register["lanes"] = [lane, other]
        write_json(self.fixture.register_path, register)
        with self.assertRaisesRegex(controller.CohortError, "active_write_collision"):
            controller.build_admission(
                binding_reference=reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )

    def _credit(self, number: int, previous: str | None) -> dict[str, object]:
        job = self.fixture.manifest["jobs"][number - 1]
        return {
            "schema": controller.CREDIT_SCHEMA,
            "status": "credited",
            "generated_at_utc": f"2026-08-26T{number:02d}:00:00Z",
            "cohort_id": controller.COHORT_ID,
            "manifest_reference": controller.MANIFEST_REFERENCE,
            "manifest_sha256": controller.MANIFEST_SHA256,
            "credit_number": number,
            "job_id": job["job_id"],
            "previous_credit_sha256": previous,
            "admission_reference": (
                "tmp/implementation-builder-scoped-worktree/"
                f"wave2-cohort-controller-v1/job-{number:02d}/admission.json"
            ),
            "admission_sha256": "a" * 64,
            "technical_proof_reference": (
                "tmp/implementation-builder-scoped-worktree/"
                f"wave2-cohort-controller-v1/job-{number:02d}/technical-proof.json"
            ),
            "technical_proof_sha256": "b" * 64,
            "main_acceptance_reference": (
                "tmp/implementation-builder-scoped-worktree/"
                f"wave2-cohort-controller-v1/job-{number:02d}/main-acceptance.json"
            ),
            "main_acceptance_sha256": "c" * 64,
            "lane_id": f"WAVE2::cohort-job-{number:02d}-fixture-a1",
            "attempt_number": 1,
            "retry_count": 0,
            "prior_zero_credit_incident_attempts": 0,
            "usage_source_receipt_id": f"receipt-{number:02d}",
            "source_binding_id": f"binding-{number:02d}",
            "source_snapshot_fingerprint": str(number) * 64,
            "accepted_post_apply_files": [
                {
                    "path": row["path"],
                    "bytes": row["bytes"] + 1,
                    "sha256": str(number) * 64,
                }
                for row in sorted(job["write_files"], key=lambda item: item["path"])
            ],
            "main_acceptance_status": "accepted",
            "wave3_review_gate_contribution": 1,
            "wave3_authorized": False,
            "automatic_route_promotion_allowed": False,
            "authority_boundary": dict(controller.AUTHORITY_BOUNDARY),
        }

    def _write_bound_job1_credit(self) -> tuple[dict[str, object], dict[str, Path]]:
        job = self.fixture.manifest["jobs"][0]
        post = self._credit(1, None)["accepted_post_apply_files"]
        admission_path = controller._admission_path(self.fixture.controller_root, 1)
        proof_path = controller._proof_path(self.fixture.controller_root, 1)
        acceptance_path = controller._acceptance_path(self.fixture.controller_root, 1)
        binding_reference = self.fixture.write_binding()
        binding_path = self.fixture.root / binding_reference
        lane = self.fixture.admission_lane()
        admission = {
            "schema": controller.ADMISSION_SCHEMA,
            "status": "ok",
            "generated_at_utc": "2026-08-26T06:01:00Z",
            "expires_at_utc": "2099-08-26T06:00:00Z",
            "cohort": {
                "cohort_id": controller.COHORT_ID,
                "manifest_reference": controller.MANIFEST_REFERENCE,
                "manifest_sha256": controller.MANIFEST_SHA256,
            },
            "job": {
                "job_number": 1,
                "job_id": job["job_id"],
                "source_file_hashes": copy.deepcopy(job["write_files"]),
                "focused_test": job["focused_test"],
                "compile_test": job["compile_test"],
            },
            "sequence": {
                "previous_credited_count": 0,
                "expected_job_number": 1,
                "contiguous": True,
                "other_active_cohort_job": False,
            },
            "binding": {
                "reference": binding_reference,
                "sha256": sha256_bytes(binding_path.read_bytes()),
                "schema": "veritas.measurement_cohort_transport_binding.v2",
                "calibration_proof_reference": (
                    "tmp/implementation-builder-scoped-worktree/"
                    "fixture-calibration.json"
                ),
                "calibration_job_id": job["job_id"] + "-calibration",
                "calibration_allowed_write_paths": sorted(
                    row["path"] for row in job["write_files"]
                ),
            },
            "lane": {
                "lane_id": lane["lane_id"],
                "workflow_id": lane["workflow_id"],
                "workstream_id": lane["workstream_id"],
                "created_at_utc": lane["created_at_utc"],
                "allowed_write_paths": sorted(lane["allowed_writes"]),
            },
            "route": {
                **controller.EXPECTED_ROUTE,
                "fallback_allowed": False,
                "cwd_override_allowed": False,
            },
            "attempt": controller._attempt_projection(lane),
            "attempt_history": [],
            "authority_boundary": {
                **controller.AUTHORITY_BOUNDARY,
                "measurement_admission_ready": True,
                "cohort_credit_granted": False,
            },
            "errors": [],
        }
        admission_sha256 = write_json(admission_path, admission)
        commands = [
            {
                "command": command,
                "exit_code": 0,
                "stdout_sha256": "0" * 64,
                "stderr_sha256": "0" * 64,
                "stdout_artifact": None,
                "stderr_artifact": None,
            }
            for command in (job["focused_test"], job["compile_test"])
        ]
        proof = {
            "schema": controller.PROOF_SCHEMA,
            "status": "ok",
            "generated_at_utc": "2026-08-26T06:05:00Z",
            "cohort": {
                "cohort_id": controller.COHORT_ID,
                "manifest_reference": controller.MANIFEST_REFERENCE,
                "manifest_sha256": controller.MANIFEST_SHA256,
            },
            "job": {
                "job_number": 1,
                "job_id": job["job_id"],
                "allowed_write_paths": sorted(
                    row["path"] for row in job["write_files"]
                ),
            },
            "admission": {
                "reference": controller._artifact_reference(
                    admission_path, root=self.fixture.root
                ),
                "sha256": admission_sha256,
                "binding_reference": binding_reference,
                "binding_sha256": sha256_bytes(binding_path.read_bytes()),
            },
            "lane_terminal": {
                "lane_id": lane["lane_id"],
                "workstream_id": lane["workstream_id"],
                "completed_at_utc": "2026-08-26T06:05:00Z",
                "validator_result": "pass",
                "closure_durability": "verified",
                "attempt_number": 1,
                "retry_count": 0,
                "incident_code": "",
                "incident_count": 0,
                "outcome_events": [
                    {
                        "event_kind": "terminal_closeout",
                        "event_sequence": 1,
                        "recorded_at_utc": "2026-08-26T06:05:00Z",
                    }
                ],
                "outcome_event_kind": "terminal_closeout",
                "outcome_event_sequence": 1,
                "outcome_recorded_at_utc": "2026-08-26T06:05:00Z",
            },
            "attempt_history": [],
            "usage": {
                "usage_source_receipt_id": "receipt-01",
                "source_binding_id": "binding-01",
                "source_snapshot_fingerprint": "f" * 64,
            },
            "worktree": {"post_apply_files": post},
            "validation": {
                "commands": commands,
                "validated_post_apply_files": post,
            },
            "authority_boundary": dict(controller.PROOF_AUTHORITY_BOUNDARY),
            "errors": [],
        }
        proof_sha256 = write_json(proof_path, proof)
        acceptance = {
            "schema": controller.ACCEPTANCE_SCHEMA,
            "status": "accepted",
            "cohort_id": controller.COHORT_ID,
            "job_id": job["job_id"],
            "manifest_sha256": controller.MANIFEST_SHA256,
            "admission_sha256": admission_sha256,
            "job_proof_sha256": proof_sha256,
            "accepted_post_apply_files": post,
            "accepted_validation_commands": commands,
            "main_verified": True,
            "acceptance_scope": "wave2_measurement_credit_only",
            "wave3_authorized": False,
            "automatic_route_promotion_allowed": False,
        }
        acceptance_sha256 = write_json(acceptance_path, acceptance)
        credit = self._credit(1, None)
        credit.update(
            {
                "admission_reference": controller._artifact_reference(
                    admission_path, root=self.fixture.root
                ),
                "admission_sha256": admission_sha256,
                "technical_proof_reference": controller._artifact_reference(
                    proof_path, root=self.fixture.root
                ),
                "technical_proof_sha256": proof_sha256,
                "main_acceptance_reference": controller._artifact_reference(
                    acceptance_path, root=self.fixture.root
                ),
                "main_acceptance_sha256": acceptance_sha256,
                "source_snapshot_fingerprint": "f" * 64,
                "main_acceptance_status": "accepted",
                "wave3_review_gate_contribution": 1,
                "authority_boundary": dict(controller.AUTHORITY_BOUNDARY),
            }
        )
        return credit, {
            "admission": admission_path,
            "proof": proof_path,
            "acceptance": acceptance_path,
        }

    def test_credit_gap_and_source_reuse_fail_closed(self) -> None:
        manifest = self.load_manifest()
        write_json(
            controller._credit_path(self.fixture.controller_root, 2),
            self._credit(2, None),
        )
        _, errors = controller.load_credit_chain(
            manifest,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            current_verifier=lambda _credit, _job: [],
        )
        self.assertTrue(any("credit_gap" in error for error in errors))

        self.fixture.controller_root.mkdir(parents=True, exist_ok=True)
        for path in self.fixture.controller_root.rglob("credit-receipt.json"):
            path.unlink()
        first_path = controller._credit_path(self.fixture.controller_root, 1)
        first_hash = write_json(first_path, self._credit(1, None))
        second = self._credit(2, first_hash)
        second["usage_source_receipt_id"] = "receipt-01"
        write_json(controller._credit_path(self.fixture.controller_root, 2), second)
        _, errors = controller.load_credit_chain(
            manifest,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            current_verifier=lambda _credit, _job: [],
        )
        self.assertIn("credit_usage_receipt_reused_or_missing", errors)

    def test_nine_never_ready_ten_only_opens_review_gate(self) -> None:
        previous: str | None = None
        for number in range(1, 10):
            path = controller._credit_path(self.fixture.controller_root, number)
            previous = write_json(path, self._credit(number, previous))
        with patch.object(controller, "_preimage_errors", return_value=[]):
            partial = controller.derive_status(
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                current_verifier=lambda _credit, _job: [],
                credit_artifact_verifier=lambda _credit, _job: [],
            )
        self.assertEqual(partial["qualifying_jobs"], 9)
        self.assertFalse(partial["wave3_review"]["wave3_review_gate_met"])

        path = controller._credit_path(self.fixture.controller_root, 10)
        write_json(path, self._credit(10, previous))
        ready = controller.derive_status(
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            current_verifier=lambda _credit, _job: [],
            credit_artifact_verifier=lambda _credit, _job: [],
        )
        self.assertEqual(ready["qualifying_jobs"], 10)
        self.assertTrue(ready["wave3_review"]["wave3_review_gate_met"])
        self.assertFalse(ready["wave3_review"]["wave3_authorized"])
        self.assertFalse(ready["wave3_review"]["automatic_route_promotion_allowed"])

    def test_synthetic_credit_cannot_open_review_status(self) -> None:
        write_json(
            controller._credit_path(self.fixture.controller_root, 1),
            self._credit(1, None),
        )
        status = controller.derive_status(
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            current_verifier=lambda _credit, _job: [],
        )
        self.assertEqual(status["status"], "error")
        self.assertTrue(
            any("bound_artifact" in error for error in status["errors"])
        )

    def test_bound_credit_rejects_proof_acceptance_and_receipt_tampering(self) -> None:
        job = self.fixture.manifest["jobs"][0]
        credit, paths = self._write_bound_job1_credit()
        self.assertEqual(
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
            [],
        )

        def rewritten_proof_errors(mutate) -> list[str]:
            mutated_credit, mutated_paths = self._write_bound_job1_credit()
            mutated_proof = json.loads(
                mutated_paths["proof"].read_text(encoding="utf-8")
            )
            mutate(mutated_proof)
            mutated_proof_sha256 = write_json(
                mutated_paths["proof"], mutated_proof
            )
            mutated_acceptance = json.loads(
                mutated_paths["acceptance"].read_text(encoding="utf-8")
            )
            mutated_acceptance["job_proof_sha256"] = mutated_proof_sha256
            mutated_credit["technical_proof_sha256"] = mutated_proof_sha256
            mutated_credit["main_acceptance_sha256"] = write_json(
                mutated_paths["acceptance"], mutated_acceptance
            )
            return controller._bound_credit_artifact_errors(
                mutated_credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            )

        for proof_time in (
            "2026-08-26T06:00:59Z",
            "2099-08-26T06:00:00Z",
            "2099-08-26T06:00:01Z",
        ):
            self.assertIn(
                "technical_proof_time_binding_invalid",
                rewritten_proof_errors(
                    lambda proof, value=proof_time: proof.__setitem__(
                        "generated_at_utc", value
                    )
                ),
            )
        self.assertIn(
            "technical_proof_attempt_fields_missing",
            rewritten_proof_errors(
                lambda proof: proof["lane_terminal"].pop("retry_count")
            ),
        )
        for field in (
            "config_auth_runtime_mutation_allowed",
            "finance_canon_portfolio_or_execution_authority",
            "external_delivery_allowed",
            "wave3_authorized",
        ):
            self.assertIn(
                "technical_proof_contract_invalid",
                rewritten_proof_errors(
                    lambda proof, key=field: proof["authority_boundary"].__setitem__(
                        key, True
                    )
                ),
            )
        for field in ("lane_id", "workstream_id"):
            self.assertIn(
                "technical_proof_terminal_identity_binding_invalid",
                rewritten_proof_errors(
                    lambda proof, key=field: proof["lane_terminal"].__setitem__(
                        key, "forged"
                    )
                ),
            )

        proof = json.loads(paths["proof"].read_text(encoding="utf-8"))
        proof["status"] = "forged"
        write_json(paths["proof"], proof)
        self.assertTrue(
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            )
        )

        credit, paths = self._write_bound_job1_credit()
        acceptance = json.loads(paths["acceptance"].read_text(encoding="utf-8"))
        acceptance["wave3_authorized"] = True
        credit["main_acceptance_sha256"] = write_json(
            paths["acceptance"], acceptance
        )
        errors = controller._bound_credit_artifact_errors(
            credit,
            job,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertIn("main_acceptance_contract_invalid", errors)

        credit, paths = self._write_bound_job1_credit()
        acceptance = json.loads(paths["acceptance"].read_text(encoding="utf-8"))
        acceptance["config_auth_runtime_mutation_allowed"] = True
        credit["main_acceptance_sha256"] = write_json(
            paths["acceptance"], acceptance
        )
        self.assertIn(
            "main_acceptance_contract_invalid",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

        credit, paths = self._write_bound_job1_credit()
        proof = json.loads(paths["proof"].read_text(encoding="utf-8"))
        proof["admission"]["binding_reference"] = (
            "tmp/implementation-builder-scoped-worktree/forged-binding.json"
        )
        proof_sha256 = write_json(paths["proof"], proof)
        acceptance = json.loads(paths["acceptance"].read_text(encoding="utf-8"))
        acceptance["job_proof_sha256"] = proof_sha256
        credit["technical_proof_sha256"] = proof_sha256
        credit["main_acceptance_sha256"] = write_json(
            paths["acceptance"], acceptance
        )
        self.assertIn(
            "technical_proof_admission_binding_invalid",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

        credit, paths = self._write_bound_job1_credit()
        proof = json.loads(paths["proof"].read_text(encoding="utf-8"))
        proof["authority_boundary"]["finance_canon_portfolio_or_execution_authority"] = True
        proof_sha256 = write_json(paths["proof"], proof)
        acceptance = json.loads(paths["acceptance"].read_text(encoding="utf-8"))
        acceptance["job_proof_sha256"] = proof_sha256
        credit["technical_proof_sha256"] = proof_sha256
        credit["main_acceptance_sha256"] = write_json(
            paths["acceptance"], acceptance
        )
        self.assertIn(
            "technical_proof_contract_invalid",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

        credit, _paths = self._write_bound_job1_credit()
        credit["attempt_number"] = 2
        credit["retry_count"] = 0
        self.assertIn(
            "credit_retry_count_mismatch",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )
        credit, _paths = self._write_bound_job1_credit()
        credit.pop("attempt_number")
        self.assertIn(
            "credit_attempt_fields_missing",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )
        credit, _paths = self._write_bound_job1_credit()
        credit.pop("retry_count")
        self.assertIn(
            "credit_attempt_fields_missing",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )
        credit, _paths = self._write_bound_job1_credit()
        credit["prior_zero_credit_incident_attempts"] = False
        self.assertIn(
            "credit_prior_incident_count_invalid",
            controller._basic_credit_errors(
                credit, job, previous_credit_sha256=None
            ),
        )
        credit, _paths = self._write_bound_job1_credit()
        credit["external_action_authorized"] = True
        self.assertIn(
            "credit_field_inventory_invalid",
            controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

        credit, paths = self._write_bound_job1_credit()
        proof = json.loads(paths["proof"].read_text(encoding="utf-8"))
        proof["usage"]["usage_source_receipt_id"] = "receipt-tampered"
        proof_sha256 = write_json(paths["proof"], proof)
        acceptance = json.loads(paths["acceptance"].read_text(encoding="utf-8"))
        acceptance["job_proof_sha256"] = proof_sha256
        credit["technical_proof_sha256"] = proof_sha256
        credit["main_acceptance_sha256"] = write_json(
            paths["acceptance"], acceptance
        )
        errors = controller._bound_credit_artifact_errors(
            credit,
            job,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertIn("credit_summary_binding_invalid", errors)

    def test_coherent_local_quartet_without_protected_sources_is_not_credit(self) -> None:
        credit, _paths = self._write_bound_job1_credit()
        write_json(
            controller._credit_path(self.fixture.controller_root, 1), credit
        )
        credits, errors = controller.load_credit_chain(
            self.load_manifest(),
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            register_path=self.fixture.register_path,
            completed_root=self.base / "completed",
            agent_state_root=self.base / "agent-state",
            state_db_path=self.base / "state.db",
            current_verifier=lambda _credit, _job: [],
        )
        self.assertEqual(len(credits), 1)
        self.assertTrue(
            any("historical_control_source_invalid" in error for error in errors)
        )

    def test_historical_binding_expiry_and_owner_source_remain_fail_closed(self) -> None:
        job = self.fixture.manifest["jobs"][0]

        def rewrite_chain(credit, paths, mutate_binding, mutate_admission=None):
            admission = json.loads(paths["admission"].read_text(encoding="utf-8"))
            binding_path = self.fixture.root / admission["binding"]["reference"]
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            mutate_binding(binding)
            admission["binding"]["sha256"] = write_json(binding_path, binding)
            if mutate_admission is not None:
                mutate_admission(admission)
            admission_sha256 = write_json(paths["admission"], admission)
            proof = json.loads(paths["proof"].read_text(encoding="utf-8"))
            proof["admission"]["sha256"] = admission_sha256
            proof["admission"]["binding_sha256"] = admission["binding"]["sha256"]
            proof_sha256 = write_json(paths["proof"], proof)
            acceptance = json.loads(paths["acceptance"].read_text(encoding="utf-8"))
            acceptance["admission_sha256"] = admission_sha256
            acceptance["job_proof_sha256"] = proof_sha256
            credit["admission_sha256"] = admission_sha256
            credit["technical_proof_sha256"] = proof_sha256
            credit["main_acceptance_sha256"] = write_json(
                paths["acceptance"], acceptance
            )
            return controller._bound_credit_artifact_errors(
                credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            )

        credit, paths = self._write_bound_job1_credit()
        self.assertEqual(
            rewrite_chain(
                credit,
                paths,
                lambda binding: binding.__setitem__(
                    "expires_at_utc", "2026-08-26T06:10:00Z"
                ),
                lambda admission: admission.__setitem__(
                    "expires_at_utc", "2026-08-26T06:10:00Z"
                ),
            ),
            [],
        )
        expired_admission = json.loads(
            paths["admission"].read_text(encoding="utf-8")
        )
        self.assertEqual(
            controller._admission_snapshot_errors(
                expired_admission,
                job,
                self.fixture.admission_lane(),
                [],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
            [],
        )

        credit, paths = self._write_bound_job1_credit()
        rewrite_chain(
            credit,
            paths,
            lambda binding: binding["authorization"].__setitem__(
                "source_event_sha256", "d" * 64
            ),
        )
        tampered_admission = json.loads(
            paths["admission"].read_text(encoding="utf-8")
        )
        self.assertIn(
            "binding_snapshot_authorization_source_invalid",
            controller._admission_snapshot_errors(
                tampered_admission,
                job,
                self.fixture.admission_lane(),
                [],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

    def _terminal_lane_and_source(
        self, *, number: int = 1, attempt_number: int = 1
    ) -> tuple[dict[str, object], dict[str, object]]:
        lane = self.fixture.admission_lane(
            number=number, attempt_number=attempt_number
        )
        lane["status"] = "complete"
        terminal_stamp = (
            "2026-08-26T06:05:00Z"
            if attempt_number == 1
            else "2026-08-26T06:15:00Z"
        )
        lane["completed_at_utc"] = terminal_stamp
        runtime = lane["runtime"]
        assert isinstance(runtime, dict)
        runtime.update(
            {
                "actual_execution_backend": controller.BACKEND,
                "incident_code": "",
                "incident_count": 0,
                "outcome_status": "completed_without_incident",
                "validator_result": "pass",
                "closure_durability": "verified",
                "outcome_event_kind": "terminal_closeout",
                "main_acceptance_status": "pending",
                "outcome_event_sequence": 1,
                "outcome_recorded_at_utc": terminal_stamp,
                "usage_source_receipt_id": "receipt-01",
                "usage_source_receipt_schema": "veritas.model_usage_source_receipt.v1",
                "source_binding_id": "source-binding-01",
                "source_snapshot_fingerprint": "a" * 24,
                "token_attribution_source": "openclaw_isolated_session_store_v2",
                "observed_elapsed_seconds": 300,
                "observed_tool_calls": 8,
            }
        )
        lane["outcome_events"] = [
            {
                "event_kind": "terminal_closeout",
                "event_sequence": 1,
                "recorded_at_utc": terminal_stamp,
            }
        ]
        correlation = lanes.expected_attempt_correlation(lane, runtime)
        assert correlation is not None
        token = usage_metadata.dispatch_binding_token_hash_for_attempt(
            attempt_correlation_hash=correlation["key_hash"]
        )
        source: dict[str, object] = {
            "schema": "veritas.isolated_agent_usage_metadata.v1",
            "agent_id": controller.AGENT_ID,
            "agent_role": "implementation_builder",
            "token_attribution_source": "openclaw_isolated_session_store_v2",
            "model_path": controller.MODEL_PATH,
            "model_provider": "openai",
            "actual_thinking": "low",
            "source_context_prompt_semantics": "context_prompt_snapshot_not_run_usage_total",
            "input_token_semantics": "exclusive_cached",
            "source_total_tokens_fresh": True,
            "source_snapshot_fingerprint": "a" * 24,
            "dispatch_binding": {"binding_token_hash": token},
            "run_id": "run-01",
            "duration_ms": 1234,
            "input_tokens": 100,
            "cached_input_tokens": 200,
            "cache_write_tokens": 0,
            "output_tokens": 50,
            "source_input_total_tokens": 300,
            "source_context_prompt_tokens": 17,
            "total_tokens": 350,
        }
        return lane, source

    def test_protected_usage_reopens_source_and_preserves_context_semantics(self) -> None:
        lane, source = self._terminal_lane_and_source()
        assessment_kwargs: dict[str, object] = {}

        def receipt_verifier(*_args, **_kwargs):
            return []

        def loader(**_kwargs):
            return dict(source), []

        receipt_store = lanes.empty_usage_receipt_store()
        receipt_store["receipts"] = [
            {
                "receipt_id": "receipt-01",
                "source_binding_id": "source-binding-01",
                "source_type": "openclaw_isolated_session_store_v2",
                "source_snapshot_fingerprint": source[
                    "source_snapshot_fingerprint"
                ],
                "source_run_id": source["run_id"],
                "dispatch_binding": source["dispatch_binding"],
            }
        ]
        write_json(
            lanes.usage_receipt_store_path(self.fixture.register_path),
            receipt_store,
        )

        def assessor(*_args, **kwargs):
            assessment_kwargs.update(kwargs)
            return {"usage_creditable": True, "reasons": []}

        proof = controller._usage_proof(
            lane,
            register_path=self.fixture.register_path,
            agent_state_root=self.base,
            state_db_path=self.base / "state.db",
            receipt_verifier=receipt_verifier,
            usage_loader=loader,
            credit_assessor=assessor,
        )
        self.assertEqual(proof["source_context_prompt_tokens"], 17)
        self.assertEqual(proof["total_tokens"], 350)
        self.assertTrue(proof["source_reverified"])
        self.assertTrue(assessment_kwargs["require_reverification"])
        self.assertTrue(assessment_kwargs["source_reverified_this_action"])

        source["actual_thinking"] = "medium"
        with self.assertRaisesRegex(controller.CohortError, "actual_thinking"):
            controller._usage_proof(
                lane,
                register_path=self.fixture.register_path,
                agent_state_root=self.base,
                state_db_path=self.base / "state.db",
                receipt_verifier=receipt_verifier,
                usage_loader=lambda **_kwargs: (dict(source), []),
                credit_assessor=lambda *_args, **_kwargs: {
                    "usage_creditable": True,
                    "reasons": [],
                },
            )

    def test_terminal_event_lifecycle_requires_exact_acceptance_update(self) -> None:
        lane, _source = self._terminal_lane_and_source()
        job = self.fixture.manifest["jobs"][0]
        receipt_sidecar = "tmp/concurrent-lane-register.usage-receipts.json"
        lane["allowed_writes"] = sorted(
            list(lane["allowed_writes"]) + [receipt_sidecar]
        )
        self.assertEqual(
            controller._lane_contract_errors(
                lane,
                job,
                terminal=True,
                accepted=False,
                receipt_sidecar=receipt_sidecar,
            ),
            [],
        )
        boolean_count = copy.deepcopy(lane)
        boolean_count["runtime"]["incident_count"] = True
        self.assertIn(
            "lane_incident_count_not_exact_zero",
            controller._lane_contract_errors(
                boolean_count,
                job,
                terminal=True,
                accepted=False,
                receipt_sidecar=receipt_sidecar,
            ),
        )
        for target in ("runtime", "event"):
            boolean_sequence = copy.deepcopy(lane)
            if target == "runtime":
                boolean_sequence["runtime"]["outcome_event_sequence"] = True
            else:
                boolean_sequence["outcome_events"][0]["event_sequence"] = True
            self.assertTrue(
                any(
                    "sequence_invalid" in error or "runtime_drift" in error
                    for error in controller._lane_contract_errors(
                        boolean_sequence,
                        job,
                        terminal=True,
                        accepted=False,
                        receipt_sidecar=receipt_sidecar,
                    )
                )
            )
        completion_drift = copy.deepcopy(lane)
        completion_drift["outcome_events"][0]["recorded_at_utc"] = (
            "2026-08-26T06:05:01Z"
        )
        completion_drift["runtime"]["outcome_recorded_at_utc"] = (
            "2026-08-26T06:05:01Z"
        )
        self.assertIn(
            "lane_terminal_time_binding_invalid",
            controller._lane_contract_errors(
                completion_drift,
                job,
                terminal=True,
                accepted=False,
                receipt_sidecar=receipt_sidecar,
            ),
        )
        missing_count = copy.deepcopy(lane)
        missing_count["runtime"].pop("incident_count")
        self.assertIn(
            "lane_incident_count_not_exact_zero",
            controller._lane_contract_errors(
                missing_count,
                job,
                terminal=True,
                accepted=False,
                receipt_sidecar=receipt_sidecar,
            ),
        )
        missing_events = copy.deepcopy(lane)
        missing_events.pop("outcome_events")
        self.assertIn(
            "lane_outcome_events_shape_invalid",
            controller._lane_contract_errors(
                missing_events,
                job,
                terminal=True,
                accepted=False,
                receipt_sidecar=receipt_sidecar,
            ),
        )
        runtime = lane["runtime"]
        assert isinstance(runtime, dict)
        runtime.pop("outcome_status")
        self.assertIn(
            "lane_incident_free_outcome_not_explicit",
            controller._lane_contract_errors(
                lane,
                job,
                terminal=True,
                accepted=False,
                receipt_sidecar=receipt_sidecar,
            ),
        )
        runtime["outcome_status"] = "completed_without_incident"
        runtime.update(
            {
                "main_acceptance_status": "accepted",
                "outcome_event_kind": "main_acceptance_update",
                "outcome_event_sequence": 2,
                "outcome_recorded_at_utc": "2026-08-26T06:06:00Z",
            }
        )
        lane["outcome_events"].append(
            {
                "event_kind": "main_acceptance_update",
                "event_sequence": 2,
                "recorded_at_utc": "2026-08-26T06:06:00Z",
            }
        )
        self.assertEqual(
            controller._lane_contract_errors(
                lane,
                job,
                terminal=True,
                accepted=True,
                receipt_sidecar=receipt_sidecar,
            ),
            [],
        )
        for bad_time in ("2026-08-26T06:05:00Z", "2026-08-26T06:04:59Z"):
            non_monotonic = copy.deepcopy(lane)
            non_monotonic["outcome_events"][1]["recorded_at_utc"] = bad_time
            non_monotonic["runtime"]["outcome_recorded_at_utc"] = bad_time
            self.assertIn(
                "lane_outcome_events_chronology_invalid",
                controller._lane_contract_errors(
                    non_monotonic,
                    job,
                    terminal=True,
                    accepted=True,
                    receipt_sidecar=receipt_sidecar,
                ),
            )
        runtime["outcome_event_sequence"] = 1
        self.assertIn(
            "lane_terminal_event_sequence_invalid",
            controller._lane_contract_errors(
                lane,
                job,
                terminal=True,
                accepted=True,
                receipt_sidecar=receipt_sidecar,
            ),
        )

    def test_retry_credit_counts_once_and_reopens_prior_history(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.init_git()
        binding_reference = self.fixture.write_binding()
        prior = self.fixture.incident_lane()
        retry = self.fixture.admission_lane(attempt_number=2)
        self.fixture.write_register(prior, retry)
        with patch.object(
            controller, "_utc_now", return_value="2026-08-26T06:11:00Z"
        ):
            admission = controller.build_admission(
                binding_reference=binding_reference,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                binding_inspector=lambda _reference: self.fixture.binding_check(1),
            )
        admission_path = controller._admission_path(
            self.fixture.controller_root, 1, 2
        )
        admission_sha256 = write_json(admission_path, admission)

        current, source = self._terminal_lane_and_source(attempt_number=2)
        receipt_sidecar = controller._receipt_sidecar_reference(
            self.fixture.register_path, root=self.fixture.root
        )
        current["allowed_writes"] = sorted(
            [*current["allowed_writes"], receipt_sidecar]
        )
        receipt_store = lanes.empty_usage_receipt_store()
        receipt_store["receipts"] = [
            {
                "receipt_id": "receipt-01",
                "source_binding_id": "source-binding-01",
                "source_type": "openclaw_isolated_session_store_v2",
                "source_snapshot_fingerprint": source[
                    "source_snapshot_fingerprint"
                ],
                "source_run_id": source["run_id"],
                "dispatch_binding": source["dispatch_binding"],
            }
        ]
        write_json(
            lanes.usage_receipt_store_path(self.fixture.register_path),
            receipt_store,
        )

        def receipt_verifier(*_args, **_kwargs):
            return []

        def usage_loader(**_kwargs):
            return dict(source), []

        def credit_assessor(*_args, **_kwargs):
            return {"usage_creditable": True, "reasons": []}

        usage = controller._usage_proof(
            current,
            register_path=self.fixture.register_path,
            agent_state_root=self.base,
            state_db_path=self.base / "state.db",
            receipt_verifier=receipt_verifier,
            usage_loader=usage_loader,
            credit_assessor=credit_assessor,
        )
        job = self.fixture.manifest["jobs"][0]
        post_files: list[dict[str, object]] = []
        for row in sorted(job["write_files"], key=lambda item: item["path"]):
            raw = (self.fixture.root / row["path"]).read_bytes()
            post_files.append(
                {
                    "path": row["path"],
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                }
            )
        commands = [
            {
                "command": command,
                "exit_code": 0,
                "stdout_sha256": "0" * 64,
                "stderr_sha256": "0" * 64,
                "stdout_artifact": None,
                "stderr_artifact": None,
            }
            for command in (job["focused_test"], job["compile_test"])
        ]
        proof_path = controller._proof_path(self.fixture.controller_root, 1)
        proof = {
            "schema": controller.PROOF_SCHEMA,
            "status": "ok",
            "generated_at_utc": "2026-08-26T06:15:00Z",
            "cohort": {
                "cohort_id": controller.COHORT_ID,
                "manifest_reference": controller.MANIFEST_REFERENCE,
                "manifest_sha256": controller.MANIFEST_SHA256,
            },
            "job": {
                "job_number": 1,
                "job_id": job["job_id"],
                "allowed_write_paths": sorted(
                    row["path"] for row in job["write_files"]
                ),
            },
            "admission": {
                "reference": controller._artifact_reference(
                    admission_path, root=self.fixture.root
                ),
                "sha256": admission_sha256,
                "binding_reference": admission["binding"]["reference"],
                "binding_sha256": admission["binding"]["sha256"],
            },
            "lane_terminal": {
                "lane_id": current["lane_id"],
                "workstream_id": current["workstream_id"],
                "completed_at_utc": current["completed_at_utc"],
                "validator_result": "pass",
                "closure_durability": "verified",
                "attempt_number": 2,
                "retry_count": 1,
                "incident_code": "",
                "incident_count": 0,
                "outcome_events": copy.deepcopy(current["outcome_events"]),
                "outcome_event_kind": "terminal_closeout",
                "outcome_event_sequence": 1,
                "outcome_recorded_at_utc": "2026-08-26T06:15:00Z",
            },
            "attempt_history": admission["attempt_history"],
            "usage": usage,
            "worktree": {"post_apply_files": post_files},
            "validation": {
                "commands": commands,
                "validated_post_apply_files": post_files,
            },
            "authority_boundary": dict(controller.PROOF_AUTHORITY_BOUNDARY),
            "errors": [],
        }
        proof_sha256 = write_json(proof_path, proof)
        acceptance_path = controller._acceptance_path(
            self.fixture.controller_root, 1
        )
        acceptance = {
            "schema": controller.ACCEPTANCE_SCHEMA,
            "status": "accepted",
            "cohort_id": controller.COHORT_ID,
            "job_id": job["job_id"],
            "manifest_sha256": controller.MANIFEST_SHA256,
            "admission_sha256": admission_sha256,
            "job_proof_sha256": proof_sha256,
            "accepted_post_apply_files": post_files,
            "accepted_validation_commands": commands,
            "main_verified": True,
            "acceptance_scope": "wave2_measurement_credit_only",
            "wave3_authorized": False,
            "automatic_route_promotion_allowed": False,
        }
        write_json(acceptance_path, acceptance)
        runtime = current["runtime"]
        assert isinstance(runtime, dict)
        runtime.update(
            {
                "main_acceptance_status": "accepted",
                "main_acceptance_evidence": controller._artifact_reference(
                    acceptance_path, root=self.fixture.root
                ),
                "outcome_event_kind": "main_acceptance_update",
                "outcome_event_sequence": 2,
                "outcome_recorded_at_utc": "2026-08-26T06:16:00Z",
            }
        )
        current["outcome_events"].append(
            {
                "event_kind": "main_acceptance_update",
                "event_sequence": 2,
                "recorded_at_utc": "2026-08-26T06:16:00Z",
            }
        )
        self.fixture.write_register(prior, current)
        credit = controller.build_credit(
            job_id=job["job_id"],
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            register_path=self.fixture.register_path,
            agent_state_root=self.base,
            state_db_path=self.base / "state.db",
            receipt_verifier=receipt_verifier,
            usage_loader=usage_loader,
            credit_assessor=credit_assessor,
            credit_evidence_verifier=lambda _credit, _job: [],
        )
        self.assertEqual(credit["attempt_number"], 2)
        self.assertEqual(credit["retry_count"], 1)
        self.assertEqual(credit["prior_zero_credit_incident_attempts"], 1)
        self.assertEqual(credit["wave3_review_gate_contribution"], 1)
        self.assertFalse(credit["wave3_authorized"])
        for field in (
            "config_auth_runtime_mutation_allowed",
            "finance_canon_portfolio_or_execution_authority",
            "external_delivery_allowed",
            "wave3_authorized",
        ):
            self.assertFalse(credit["authority_boundary"][field])
        for field in (
            "config_auth_runtime_mutation_allowed",
            "finance_canon_portfolio_or_execution_authority",
        ):
            tampered_credit = copy.deepcopy(credit)
            tampered_credit["authority_boundary"][field] = True
            self.assertIn(
                "credit_summary_binding_invalid",
                controller._bound_credit_artifact_errors(
                    tampered_credit,
                    job,
                    root=self.fixture.root,
                    controller_root=self.fixture.controller_root,
                ),
            )
        baseline_proof = copy.deepcopy(proof)
        baseline_acceptance = copy.deepcopy(acceptance)
        for mutation, expected in (
            (
                lambda row: row["lane_terminal"].__setitem__(
                    "lane_id", "WAVE2::forged"
                ),
                "technical_proof_terminal_identity_binding_invalid",
            ),
            (
                lambda row: row["lane_terminal"].__setitem__(
                    "workstream_id", "forged"
                ),
                "technical_proof_terminal_identity_binding_invalid",
            ),
            (
                lambda row: (
                    row.__setitem__("generated_at_utc", "2026-08-26T06:15:30Z"),
                    row["lane_terminal"].__setitem__(
                        "completed_at_utc", "2026-08-26T06:15:30Z"
                    ),
                    row["lane_terminal"].__setitem__(
                        "outcome_recorded_at_utc", "2026-08-26T06:15:30Z"
                    ),
                    row["lane_terminal"]["outcome_events"][0].__setitem__(
                        "recorded_at_utc", "2026-08-26T06:15:30Z"
                    ),
                ),
                "technical_proof_terminal_time_binding_invalid|technical_proof_terminal_prefix_binding_invalid",
            ),
        ):
            mutated_proof = copy.deepcopy(baseline_proof)
            mutation(mutated_proof)
            mutated_proof_sha256 = write_json(proof_path, mutated_proof)
            mutated_acceptance = copy.deepcopy(baseline_acceptance)
            mutated_acceptance["job_proof_sha256"] = mutated_proof_sha256
            write_json(acceptance_path, mutated_acceptance)
            with self.assertRaisesRegex(controller.CohortError, expected):
                controller.build_credit(
                    job_id=job["job_id"],
                    root=self.fixture.root,
                    controller_root=self.fixture.controller_root,
                    register_path=self.fixture.register_path,
                    agent_state_root=self.base,
                    state_db_path=self.base / "state.db",
                    receipt_verifier=receipt_verifier,
                    usage_loader=usage_loader,
                    credit_assessor=credit_assessor,
                    credit_evidence_verifier=lambda _credit, _job: [],
                )
        proof_sha256 = write_json(proof_path, baseline_proof)
        baseline_acceptance["job_proof_sha256"] = proof_sha256
        write_json(acceptance_path, baseline_acceptance)
        with self.assertRaisesRegex(
            controller.CohortError,
            "credit_precommit_reverification_failed:forced_tamper",
        ):
            controller.build_credit(
                job_id=job["job_id"],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
                agent_state_root=self.base,
                state_db_path=self.base / "state.db",
                receipt_verifier=receipt_verifier,
                usage_loader=usage_loader,
                credit_assessor=credit_assessor,
                credit_evidence_verifier=lambda _credit, _job: [
                    "forced_tamper"
                ],
            )

        self.fixture.write_register(current)
        with self.assertRaisesRegex(
            controller.CohortError, "job_attempt_sequence_invalid"
        ):
            controller.build_credit(
                job_id=job["job_id"],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
            )

        self.fixture.write_register(prior, current)
        (
            self.fixture.controller_root
            / "job-01"
            / "attempt-01-incident.json"
        ).unlink()
        with self.assertRaisesRegex(
            controller.CohortError,
            "prior_incident_evidence_invalid|incident_evidence_unavailable",
        ):
            controller.build_credit(
                job_id=job["job_id"],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                register_path=self.fixture.register_path,
            )

    def test_exact_worktree_patch_inventory_and_main_apply_validate(self) -> None:
        job_id = "wave2-cohort-fixture-worktree"
        paths = ["scripts/a.py", "scripts/test_a.py"]
        preimages: list[dict[str, object]] = []
        for index, relative in enumerate(paths, start=1):
            raw = f"before-{index}\n".encode()
            path = self.fixture.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            preimages.append(
                {"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)}
            )
        self.fixture.init_git()
        for index, relative in enumerate(paths, start=1):
            (self.fixture.root / relative).write_text(
                f"after-{index}\n", encoding="utf-8"
            )
        patch_raw = git(
            self.fixture.root,
            "diff",
            "--binary",
            "--no-ext-diff",
            "HEAD",
            "--",
            *paths,
            text=False,
        ).stdout
        patch_path = (
            self.fixture.root
            / "tmp"
            / "implementation-builder-scoped-worktree"
            / "fixture.patch"
        )
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_bytes(patch_raw)
        git(self.fixture.root, "add", "--", str(patch_path.relative_to(self.fixture.root)))
        git(
            self.fixture.root,
            "-c",
            "user.name=Wave2 Test",
            "-c",
            "user.email=wave2@example.invalid",
            "commit",
            "-m",
            "fixture patch control",
            "--",
            str(patch_path.relative_to(self.fixture.root)),
        )
        inventory = worktrees.capture_git_path_inventory(self.fixture.root)
        checkpoints = {
            "before_binding_recheck": inventory,
            "after_binding_recheck": copy.deepcopy(inventory),
        }
        inventory_hash = worktrees.git_inventory_checkpoints_sha256(
            checkpoints, paths
        )
        changed = []
        for relative in paths:
            raw = (self.fixture.root / relative).read_bytes()
            changed.append(
                {
                    "relative_path": relative,
                    "exists": True,
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                }
            )
        close_reference = (
            "tmp/implementation-builder-scoped-worktree/fixture-close.json"
        )
        write_json(
            self.fixture.root / close_reference,
            {
                "action": "close",
                "schema": "veritas.implementation_builder_worktree_proof.v1",
                "status": "ok",
                "job_id": job_id,
                "baseline_commit": git(
                    self.fixture.root, "rev-parse", "HEAD"
                ).stdout.strip(),
                "manifest_sha256": "f" * 64,
                "allowed_write_paths": paths,
                "changed_file_count": 2,
                "changed_files": changed,
                "unexpected_changed_paths": [],
                "patch_includes_declared_new_files": True,
                "patch_path": str(patch_path),
                "patch_sha256": sha256_bytes(patch_raw),
                "tracked_diff_sha256": sha256_bytes(patch_raw),
                "git_path_inventory_checkpoints": checkpoints,
                "git_path_inventory_sha256": inventory_hash,
            },
        )
        completed_root = self.base / "completed"
        retained_hash = write_json(
            completed_root / job_id / "handoff-manifest.json",
            {
                "schema": "veritas.implementation_builder_worktree_manifest.v1",
                "job_id": job_id,
                "allowed_write_paths": paths,
                "files": [
                    {
                        "relative_path": row["path"],
                        "bytes": row["bytes"],
                        "sha256": row["sha256"],
                    }
                    for row in preimages
                ],
            },
        )
        close = json.loads((self.fixture.root / close_reference).read_text())
        close["manifest_sha256"] = retained_hash
        write_json(self.fixture.root / close_reference, close)
        job = {
            "job_number": 1,
            "job_id": job_id,
            "write_files": preimages,
        }
        proof, post = controller._worktree_proof(
            job,
            close_reference,
            root=self.fixture.root,
            completed_root=completed_root,
        )
        self.assertTrue(proof["main_applied_patch_verified"])
        self.assertEqual([row["path"] for row in post], paths)

        close = json.loads((self.fixture.root / close_reference).read_text())
        close["unexpected_changed_paths"] = ["tmp/escape.txt"]
        write_json(self.fixture.root / close_reference, close)
        with self.assertRaisesRegex(controller.CohortError, "worktree_close_contract_invalid"):
            controller._worktree_proof(
                job,
                close_reference,
                root=self.fixture.root,
                completed_root=completed_root,
            )

    def test_job_proof_rechecks_binding_expiry_after_validation(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.init_git()
        binding_reference = self.fixture.write_binding()
        active = self.fixture.admission_lane()
        self.fixture.write_register(active)
        admission = controller.build_admission(
            binding_reference=binding_reference,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
            register_path=self.fixture.register_path,
            binding_inspector=lambda _reference: self.fixture.binding_check(1),
        )
        write_json(
            controller._admission_path(self.fixture.controller_root, 1), admission
        )
        terminal, _source = self._terminal_lane_and_source()
        receipt_sidecar = controller._receipt_sidecar_reference(
            self.fixture.register_path, root=self.fixture.root
        )
        terminal["allowed_writes"] = sorted(
            [*terminal["allowed_writes"], receipt_sidecar]
        )
        self.fixture.write_register(terminal)
        command_result = {
            "label": "fixture",
            "command": "fixture",
            "exit_code": 0,
            "stdout_sha256": "0" * 64,
            "stderr_sha256": "0" * 64,
            "stdout_artifact": None,
            "stderr_artifact": None,
        }
        with (
            patch.object(controller, "_usage_proof", return_value={}),
            patch.object(
                controller,
                "_worktree_proof",
                return_value=({"post_apply_files": []}, []),
            ),
            patch.object(
                controller, "_run_validation_command", return_value=command_result
            ),
            patch.object(controller, "_current_post_file_errors", return_value=[]),
            patch.object(
                controller, "_utc_now", return_value=admission["expires_at_utc"]
            ),
        ):
            with self.assertRaisesRegex(
                controller.CohortError, "admission_binding_expired"
            ):
                controller.build_job_proof(
                    job_id=self.fixture.manifest["jobs"][0]["job_id"],
                    close_proof_reference="tmp/unused-close-proof.json",
                    root=self.fixture.root,
                    controller_root=self.fixture.controller_root,
                    register_path=self.fixture.register_path,
                    completed_root=self.base / "completed",
                    agent_state_root=self.base,
                    state_db_path=self.base / "state.db",
                )

    def test_main_acceptance_requires_exact_proof_and_never_authorizes_wave3(self) -> None:
        post = [
            {"path": "scripts/a.py", "bytes": 2, "sha256": "a" * 64},
            {"path": "scripts/test_a.py", "bytes": 2, "sha256": "b" * 64},
        ]
        commands = [{"command": "python test.py", "exit_code": 0}]
        proof = {
            "job": {"job_id": "job-01"},
            "worktree": {"post_apply_files": post},
            "validation": {"commands": commands},
        }
        acceptance = {
            "schema": controller.ACCEPTANCE_SCHEMA,
            "status": "accepted",
            "cohort_id": controller.COHORT_ID,
            "job_id": "job-01",
            "manifest_sha256": controller.MANIFEST_SHA256,
            "admission_sha256": "c" * 64,
            "job_proof_sha256": "d" * 64,
            "accepted_post_apply_files": post,
            "accepted_validation_commands": commands,
            "main_verified": True,
            "acceptance_scope": "wave2_measurement_credit_only",
            "wave3_authorized": False,
            "automatic_route_promotion_allowed": False,
        }
        self.assertEqual(
            controller._validate_acceptance(
                acceptance,
                proof,
                admission_sha256="c" * 64,
                proof_sha256="d" * 64,
            ),
            [],
        )
        for field, value in (
            ("main_verified", 1),
            ("wave3_authorized", 0),
            ("automatic_route_promotion_allowed", 0),
        ):
            integer_alias = copy.deepcopy(acceptance)
            integer_alias[field] = value
            self.assertIn(
                "main_acceptance_contract_invalid",
                controller._validate_acceptance(
                    integer_alias,
                    proof,
                    admission_sha256="c" * 64,
                    proof_sha256="d" * 64,
                ),
            )
        acceptance["wave3_authorized"] = True
        self.assertIn(
            "main_acceptance_contract_invalid",
            controller._validate_acceptance(
                acceptance,
                proof,
                admission_sha256="c" * 64,
                proof_sha256="d" * 64,
            ),
        )

    def test_atomic_json_parse_and_digest_share_one_byte_read(self) -> None:
        path = self.fixture.root / "atomic.json"
        path.write_bytes(b"{}\n")
        first = b'{"value":1}\n'
        replacement = b'{"value":2}\n'
        with patch.object(
            type(path), "read_bytes", side_effect=[first, replacement]
        ) as reader:
            payload, digest = controller._read_json_path_with_sha256(path)
        self.assertEqual(payload, {"value": 1})
        self.assertEqual(digest, sha256_bytes(first))
        self.assertEqual(reader.call_count, 1)

        credit_one = self._credit(1, None)
        credit_two = self._credit(2, "d" * 64)
        for number in (1, 2):
            credit_path = controller._credit_path(self.fixture.controller_root, number)
            credit_path.parent.mkdir(parents=True, exist_ok=True)
            credit_path.write_bytes(b"{}\n")
        with (
            patch.object(
                controller,
                "_read_json_path_with_sha256",
                side_effect=[
                    (credit_one, "d" * 64),
                    (credit_two, "e" * 64),
                ],
            ) as atomic_reader,
            patch.object(
                controller,
                "_sha256_file",
                side_effect=AssertionError("credit chain must not rehash parsed JSON"),
            ),
        ):
            credits, errors = controller.load_credit_chain(
                self.fixture.manifest,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
                current_verifier=lambda _credit, _job: [],
                artifact_verifier=lambda _credit, _job: [],
            )
        self.assertEqual(errors, [])
        self.assertEqual(len(credits), 2)
        self.assertEqual(atomic_reader.call_count, 2)

    def test_binding_reopening_rejects_unrelated_and_projection_drift(self) -> None:
        job = self.fixture.manifest["jobs"][0]
        reference = self.fixture.write_binding()
        binding_path = self.fixture.root / reference
        baseline = json.loads(binding_path.read_text(encoding="utf-8"))
        self.assertEqual(
            controller._binding_snapshot_errors(
                baseline, job, root=self.fixture.root
            ),
            [],
        )
        integer_authority = copy.deepcopy(baseline)
        integer_authority["authority_boundary"]["measurement_only"] = 1
        self.assertIn(
            "binding_snapshot_route_or_authority_invalid",
            controller._binding_snapshot_errors(
                integer_authority, job, root=self.fixture.root
            ),
        )

        handoff_path = self.fixture.root / baseline["handoff"]["reference"]
        unrelated_reference = (
            "tmp/implementation-builder-scoped-worktree/unrelated-handoff.json"
        )
        unrelated_sha256 = write_json(
            self.fixture.root / unrelated_reference,
            json.loads(handoff_path.read_text(encoding="utf-8")),
        )
        substituted = copy.deepcopy(baseline)
        substituted["handoff"]["reference"] = unrelated_reference
        substituted["handoff"]["sha256"] = unrelated_sha256
        self.assertIn(
            "binding_snapshot_handoff_invalid",
            controller._binding_snapshot_errors(
                substituted, job, root=self.fixture.root
            ),
        )

        inventory_mutations = (
            ("cohort", lambda row: row.__setitem__("extra", True)),
            ("job", lambda row: row.pop("source_file_hashes")),
            ("active_worktree", lambda row: row.__setitem__("extra", True)),
            ("handoff", lambda row: row.__setitem__("extra", True)),
            ("calibration", lambda row: row.pop("job_id")),
        )
        for section, mutate in inventory_mutations:
            with self.subTest(inventory_section=section):
                candidate = copy.deepcopy(baseline)
                mutate(candidate[section])
                self.assertTrue(
                    controller._binding_snapshot_errors(
                        candidate, job, root=self.fixture.root
                    )
                )
        for section in (
            "cohort",
            "job",
            "active_worktree",
            "handoff",
            "calibration",
        ):
            with self.subTest(malformed_section=section):
                candidate = copy.deepcopy(baseline)
                candidate[section] = []
                self.assertTrue(
                    controller._binding_snapshot_errors(
                        candidate, job, root=self.fixture.root
                    )
                )

        reference = self.fixture.write_binding()
        projected = json.loads(
            (self.fixture.root / reference).read_text(encoding="utf-8")
        )
        handoff_path = self.fixture.root / projected["handoff"]["reference"]
        handoff_payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff_payload["activation_job_contract"]["allowed_files"].reverse()
        projected["handoff"]["sha256"] = write_json(
            handoff_path, handoff_payload
        )
        self.assertIn(
            "binding_snapshot_handoff_invalid",
            controller._binding_snapshot_errors(
                projected, job, root=self.fixture.root
            ),
        )

        reference = self.fixture.write_binding()
        projected = json.loads(
            (self.fixture.root / reference).read_text(encoding="utf-8")
        )
        calibration_path = self.fixture.root / projected["calibration"]["reference"]
        calibration_payload = json.loads(
            calibration_path.read_text(encoding="utf-8")
        )
        calibration_payload["runtime"]["provider"] = "alternate"
        projected["calibration"]["strict_projection"]["runtime"][
            "provider"
        ] = "alternate"
        projected["calibration"]["sha256"] = write_json(
            calibration_path, calibration_payload
        )
        self.assertIn(
            "binding_snapshot_calibration_invalid",
            controller._binding_snapshot_errors(
                projected, job, root=self.fixture.root
            ),
        )

    def test_later_job_binding_reuses_frozen_bootstrap_evidence(self) -> None:
        self.fixture.copy_job_files(1)
        self.fixture.copy_job_files(2)
        bootstrap_job = self.fixture.manifest["jobs"][0]
        selected_job = self.fixture.manifest["jobs"][1]
        reference = self.fixture.write_binding(number=2)
        binding = json.loads(
            (self.fixture.root / reference).read_text(encoding="utf-8")
        )

        self.assertEqual(
            controller._binding_snapshot_errors(
                binding, selected_job, root=self.fixture.root
            ),
            [],
        )
        self.assertEqual(
            binding["handoff"]["reference"],
            bootstrap_job["activation_handoff"],
        )
        self.assertEqual(
            binding["calibration"]["job_id"],
            bootstrap_job["job_id"] + "-calibration",
        )
        self.assertEqual(
            binding["calibration"]["changed_paths"],
            sorted(row["path"] for row in bootstrap_job["write_files"]),
        )

        selected_scope_drift = copy.deepcopy(binding)
        selected_scope_drift["job"]["allowed_write_paths"] = sorted(
            row["path"] for row in bootstrap_job["write_files"]
        )
        self.assertIn(
            "binding_snapshot_job_contract_invalid",
            controller._binding_snapshot_errors(
                selected_scope_drift, selected_job, root=self.fixture.root
            ),
        )

        calibration_drift = copy.deepcopy(binding)
        calibration_drift["calibration"]["job_id"] = (
            selected_job["job_id"] + "-calibration"
        )
        self.assertIn(
            "binding_snapshot_calibration_invalid",
            controller._binding_snapshot_errors(
                calibration_drift, selected_job, root=self.fixture.root
            ),
        )

    def test_exact_json_types_inventories_and_active_lane_shape(self) -> None:
        job = self.fixture.manifest["jobs"][0]
        active = self.fixture.admission_lane()
        self.assertEqual(
            controller._lane_contract_errors(
                active, job, terminal=False, attempt_number=1
            ),
            [],
        )
        active_mutations = (
            ("owner", "alternate", "lane_owner_mismatch"),
            ("incident_count", False, "lane_incident_count_nonzero"),
            ("incident_code", None, "lane_active_incident_shape_invalid"),
            ("created_at_utc", "not-a-time", "lane_created_at_invalid"),
        )
        for target, value, expected in active_mutations:
            with self.subTest(active_target=target):
                candidate = copy.deepcopy(active)
                if target in {"incident_count", "incident_code"}:
                    candidate["runtime"][target] = value
                else:
                    candidate[target] = value
                self.assertIn(
                    expected,
                    controller._lane_contract_errors(
                        candidate, job, terminal=False, attempt_number=1
                    ),
                )
        terminal, _source = self._terminal_lane_and_source()
        terminal["owner"] = "alternate"
        receipt_sidecar = "tmp/concurrent-lane-register.usage-receipts.json"
        terminal["allowed_writes"] = sorted(
            [*terminal["allowed_writes"], receipt_sidecar]
        )
        self.assertIn(
            "lane_owner_mismatch",
            controller._lane_contract_errors(
                terminal,
                job,
                terminal=True,
                receipt_sidecar=receipt_sidecar,
                attempt_number=1,
            ),
        )

        prior = self.fixture.incident_lane()
        admission_path = controller._admission_path(
            self.fixture.controller_root, 1, 1
        )
        admission = json.loads(admission_path.read_text(encoding="utf-8"))
        self.assertEqual(
            controller._admission_snapshot_errors(
                admission,
                job,
                prior,
                [],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
            [],
        )
        inventory_mutations = (
            ("cohort", lambda row: row.__setitem__("extra", True)),
            ("job", lambda row: row.pop("compile_test")),
            ("lane", lambda row: row.__setitem__("extra", True)),
            ("binding", lambda row: row.pop("calibration_job_id")),
        )
        for section, mutate in inventory_mutations:
            with self.subTest(admission_inventory=section):
                candidate = copy.deepcopy(admission)
                mutate(candidate[section])
                self.assertTrue(
                    controller._admission_snapshot_errors(
                        candidate,
                        job,
                        prior,
                        [],
                        root=self.fixture.root,
                        controller_root=self.fixture.controller_root,
                    )
                )
        numeric_mutations = (
            ("job", "job_number", True),
            ("job", "job_number", 1.0),
            ("sequence", "previous_credited_count", False),
            ("sequence", "expected_job_number", True),
            ("sequence", "expected_job_number", 1.0),
            ("attempt", "attempt_number", True),
            ("attempt", "retry_count", 0.0),
        )
        for section, field, value in numeric_mutations:
            with self.subTest(section=section, field=field, value=value):
                candidate = copy.deepcopy(admission)
                candidate[section][field] = value
                self.assertIn(
                    "admission_snapshot_contract_invalid",
                    controller._admission_snapshot_errors(
                        candidate,
                        job,
                        prior,
                        [],
                        root=self.fixture.root,
                        controller_root=self.fixture.controller_root,
                    ),
                )
        for field, value in (
            ("cohort_credit_only", 1),
            ("wave3_authorized", 0),
        ):
            candidate = copy.deepcopy(admission)
            candidate["authority_boundary"][field] = value
            self.assertIn(
                "admission_snapshot_contract_invalid",
                controller._admission_snapshot_errors(
                    candidate,
                    job,
                    prior,
                    [],
                    root=self.fixture.root,
                    controller_root=self.fixture.controller_root,
                ),
            )
        coherent_bad_time = copy.deepcopy(admission)
        coherent_bad_lane = copy.deepcopy(prior)
        coherent_bad_time["lane"]["created_at_utc"] = "not-a-time"
        coherent_bad_lane["created_at_utc"] = "not-a-time"
        self.assertIn(
            "admission_snapshot_time_invalid",
            controller._admission_snapshot_errors(
                coherent_bad_time,
                job,
                coherent_bad_lane,
                [],
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

    def test_validation_credit_and_authority_numeric_aliases_fail(self) -> None:
        job = self.fixture.manifest["jobs"][0]
        for field, value, expected in (
            ("credit_number", True, "credit_sequence_identity_invalid"),
            ("credit_number", 1.0, "credit_sequence_identity_invalid"),
            ("wave3_review_gate_contribution", True, "credit_authority_invalid"),
            ("wave3_review_gate_contribution", 1.0, "credit_authority_invalid"),
            ("attempt_number", True, "credit_attempt_fields_invalid"),
            ("retry_count", 0.0, "credit_attempt_fields_invalid"),
        ):
            with self.subTest(credit_field=field, value=value):
                credit = self._credit(1, None)
                credit[field] = value
                self.assertIn(
                    expected,
                    controller._basic_credit_errors(
                        credit, job, previous_credit_sha256=None
                    ),
                )
        for field, value in (
            ("wave3_authorized", 0),
            ("cohort_credit_only", 1),
        ):
            credit = self._credit(1, None)
            if field in credit:
                credit[field] = value
            else:
                credit["authority_boundary"][field] = value
            self.assertIn(
                "credit_authority_invalid",
                controller._basic_credit_errors(
                    credit, job, previous_credit_sha256=None
                ),
            )

        _credit, paths = self._write_bound_job1_credit()
        proof = json.loads(paths["proof"].read_text(encoding="utf-8"))
        for value in (True, 0.0):
            candidate = copy.deepcopy(proof)
            candidate["validation"]["commands"][0]["exit_code"] = value
            self.assertIn(
                "credit_validation_command_invalid",
                controller._validation_contract_errors(candidate, job),
            )
        candidate = copy.deepcopy(proof)
        candidate["validation"]["commands"][0]["extra"] = True
        self.assertIn(
            "credit_validation_command_inventory_invalid",
            controller._validation_contract_errors(candidate, job),
        )
        candidate = copy.deepcopy(proof)
        candidate["validation"]["extra"] = True
        self.assertIn(
            "credit_validation_inventory_invalid",
            controller._validation_contract_errors(candidate, job),
        )
        for malformed in ([], {"commands": [[], None]}):
            candidate = copy.deepcopy(proof)
            candidate["validation"] = malformed
            self.assertTrue(controller._validation_contract_errors(candidate, job))
        admission, admission_sha256 = controller._read_json_path_with_sha256(
            paths["admission"]
        )
        admission_reference = controller._artifact_reference(
            paths["admission"], root=self.fixture.root
        )
        for target, value in (
            ("authority", 0),
            ("job_number", 1.0),
            ("attempt_number", 1.0),
        ):
            with self.subTest(proof_numeric_target=target):
                candidate = copy.deepcopy(proof)
                if target == "authority":
                    candidate["authority_boundary"]["wave3_authorized"] = value
                elif target == "job_number":
                    candidate["job"]["job_number"] = value
                else:
                    candidate["lane_terminal"]["attempt_number"] = value
                self.assertTrue(
                    controller._technical_proof_contract_errors(
                        candidate,
                        job,
                        admission_reference=admission_reference,
                        admission_sha256=admission_sha256,
                        admission=admission,
                    )
                )
        malformed_admission = copy.deepcopy(admission)
        malformed_admission["cohort"] = []
        write_json(paths["admission"], malformed_admission)
        self.assertIn(
            "credit_admission_contract_invalid",
            controller._bound_credit_artifact_errors(
                _credit,
                job,
                root=self.fixture.root,
                controller_root=self.fixture.controller_root,
            ),
        )

    def test_prior_incident_identity_is_immutably_anchored(self) -> None:
        job = self.fixture.manifest["jobs"][0]
        prior = self.fixture.incident_lane()
        _reference, digest, errors = controller._prior_incident_evidence(
            prior,
            job,
            attempt_number=1,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertIsNotNone(digest)
        self.assertEqual(errors, [])

        incident_path = (
            self.fixture.controller_root / "job-01" / "attempt-01-incident.json"
        )
        payload = json.loads(incident_path.read_text(encoding="utf-8"))
        alternate_session_key = (
            "agent:implementation-builder:subagent:"
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        )
        alternate_session_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        alternate_run_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        payload["attempt"]["session_key"] = alternate_session_key
        payload["attempt"]["session_id"] = alternate_session_id
        payload["attempt"]["run_id"] = alternate_run_id
        write_json(incident_path, payload)
        prior["runtime"]["session_key_hash"] = sha256_bytes(
            alternate_session_key.encode("utf-8")
        )[:24]
        prior["runtime"]["session_id_hash"] = sha256_bytes(
            alternate_session_id.encode("utf-8")
        )[:24]
        prior["runtime"]["dispatch_binding"][
            "registry_run_id_hash"
        ] = sha256_bytes(alternate_run_id.encode("utf-8"))
        _reference, _digest, errors = controller._prior_incident_evidence(
            prior,
            job,
            attempt_number=1,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertNotIn("incident_evidence_runtime_identity_invalid", errors)
        self.assertIn("incident_evidence_retained_identity_invalid", errors)

    def test_job2_attempt1_incident_identity_is_immutably_anchored(self) -> None:
        job = self.fixture.manifest["jobs"][1]
        prior = self.fixture.incident_lane(number=2)
        prior["lane_id"] = (
            "WAVE2::cohort-job-02-lane-dirty-porcelain-parser-20260826-a1"
        )
        prior["workstream_id"] = (
            "cohort-job-02-lane-dirty-porcelain-parser-20260826-a1"
        )
        runtime = prior["runtime"]
        self.assertIsInstance(runtime, dict)
        runtime["attempt_id"] = "wave2-cohort-job-02-a1"
        runtime["attempt_correlation"] = lanes.expected_attempt_correlation(
            prior, runtime
        )
        self.assertEqual(
            runtime["attempt_correlation"]["key_hash"],
            "c7f867ec5129d32d8e41cf7f708588cb8c774d765358bd6347d452dfc8bc45bf",
        )
        run_id = "bb17346a-4fe4-4e8f-9175-4bc3f6f6ef06"
        session_key = (
            "agent:implementation-builder:subagent:"
            "d5e85b85-6ac7-4042-bb03-8853745cf96f"
        )
        session_id = "b8284638-742a-4e0c-b89c-b5e865336372"
        runtime["session_key_hash"] = sha256_bytes(session_key.encode("utf-8"))[:24]
        runtime["session_id_hash"] = sha256_bytes(session_id.encode("utf-8"))[:24]
        runtime["dispatch_binding"] = {
            "registry_run_id_hash": sha256_bytes(run_id.encode("utf-8"))
        }
        incident_path = (
            self.fixture.controller_root / "job-02" / "attempt-01-incident.json"
        )
        payload = json.loads(incident_path.read_text(encoding="utf-8"))
        payload["attempt"].update(
            {
                "attempt_id": runtime["attempt_id"],
                "task_name": usage_metadata.task_name_for_attempt(
                    attempt_correlation_hash=runtime["attempt_correlation"][
                        "key_hash"
                    ]
                ),
                "run_id": run_id,
                "session_key": session_key,
                "session_id": session_id,
            }
        )
        write_json(incident_path, payload)

        retained = controller.RETAINED_INCIDENT_IDENTITIES[(job["job_id"], 1)]
        self.assertEqual(
            retained,
            {
                "attempt_id": "wave2-cohort-job-02-a1",
                "task_name": "vt1_y74gp3crfhjs3dsbz57xbbmizoghotlwknml2y2h2rjn7sf4iw7q",
                "run_id_sha256": sha256_bytes(run_id.encode("utf-8")),
                "session_key_sha256": sha256_bytes(session_key.encode("utf-8")),
                "session_id_sha256": sha256_bytes(session_id.encode("utf-8")),
            },
        )
        _reference, digest, errors = controller._prior_incident_evidence(
            prior,
            job,
            attempt_number=1,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertIsNotNone(digest)
        self.assertEqual(errors, [])

        alternate_session_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        payload["attempt"]["session_id"] = alternate_session_id
        write_json(incident_path, payload)
        runtime["session_id_hash"] = sha256_bytes(
            alternate_session_id.encode("utf-8")
        )[:24]
        _reference, _digest, errors = controller._prior_incident_evidence(
            prior,
            job,
            attempt_number=1,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertNotIn("incident_evidence_runtime_identity_invalid", errors)
        self.assertIn("incident_evidence_retained_identity_invalid", errors)

    def test_two_retained_incident_attempts_form_valid_retry_history(self) -> None:
        job = self.fixture.manifest["jobs"][0]
        first = self.fixture.incident_lane(attempt_number=1)
        second = self.fixture.incident_lane(
            attempt_number=2,
            prior_lanes=[first],
        )

        _reference, digest, errors = controller._prior_incident_evidence(
            second,
            job,
            attempt_number=2,
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertIsNotNone(digest)
        self.assertEqual(errors, [])

        errors = controller._prior_attempt_history_errors(
            [first, second],
            job,
            receipt_sidecar=controller._receipt_sidecar_reference(
                self.fixture.register_path, root=self.fixture.root
            ),
            root=self.fixture.root,
            controller_root=self.fixture.controller_root,
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
