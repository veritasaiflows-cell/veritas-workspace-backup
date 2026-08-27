#!/usr/bin/env python3
"""Fail-closed controller for the fixed ten-job Wave 2 measurement cohort."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REFERENCE = (
    "tmp/implementation-builder-scoped-worktree/wave2-10-job-cohort-manifest-v1.json"
)
MANIFEST_SHA256 = "9c721b1978c6cf214fe93cddc3056e152a471e9fe9fb49c5f2b6531b207dd8e7"
COHORT_ID = "wave2-implementation-builder-10-job-measurement-v1"
CONTROLLER_REFERENCE = (
    "tmp/implementation-builder-scoped-worktree/wave2-cohort-controller-v1"
)
CONTROLLER_ROOT = ROOT / CONTROLLER_REFERENCE
REGISTER_PATH = ROOT / "tmp" / "concurrent-lane-register.json"
COMPLETED_WORKTREE_ROOT = (
    Path.home()
    / ".openclaw"
    / "workspaces"
    / "implementation-builder"
    / "handoff"
    / "completed"
)
AGENT_STATE_ROOT = Path.home() / ".openclaw" / "agents"
STATE_DB_PATH = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"
AGENT_ID = "implementation-builder"
MODEL_PATH = "openai/gpt-5.6-terra"
THINKING = "low"
BACKEND = "persistent_isolated_agent"
LANE_MODE = "scoped_worktree_implementation"
MAX_JSON_BYTES = 1_000_000
MAX_PATCH_BYTES = 2_000_000
MAX_ATTEMPTS_PER_JOB = 2
JOB_MAX_ELAPSED_SECONDS = 900
JOB_CHECKPOINT_SECONDS = 300
JOB_MAX_TOOL_CALLS = 16
RESTART_PACKET_REFERENCE = (
    "tmp/implementation-builder-scoped-worktree/cohort-run-20260826/"
    "wave2-nine-job-restart-packet-v2.json"
)
QUALIFICATION_REFERENCE = (
    "tmp/implementation-builder-scoped-worktree/cohort-run-20260826/"
    "wave2-nine-job-pre-resume-qualification-v2.json"
)
RESTART_PACKET_SCHEMA = "veritas.wave2_nine_job_restart_packet.v2"
QUALIFICATION_SCHEMA = "veritas.wave2_nine_job_pre_resume_qualification.v2"
RESTART_EXPECTED_ATTEMPTS = {2: 2, **{number: 1 for number in range(3, 11)}}
FROZEN_INSTRUMENT_REFERENCES = (
    MANIFEST_REFERENCE,
    "scripts/wave2_measurement_cohort_controller.py",
    "scripts/test_wave2_measurement_cohort_controller.py",
    "scripts/implementation_builder_worktree_manager.py",
    "scripts/test_implementation_builder_worktree_manager.py",
    "scripts/measurement_cohort_transport_binding.py",
)
ACTIVE_LANE_STATUSES = {"leased", "running"}
TERMINAL_LANE_STATUS = "complete"
ADMISSION_SCHEMA = "veritas.wave2_measurement_job_admission.v1"
PROOF_SCHEMA = "veritas.wave2_measurement_job_proof.v1"
CREDIT_SCHEMA = "veritas.wave2_measurement_job_credit.v1"
ACCEPTANCE_SCHEMA = "veritas.wave2_measurement_main_acceptance.v1"
STATUS_SCHEMA = "veritas.wave2_measurement_cohort_status.v1"
CHECKPOINT_SCHEMA = "veritas.wave2_measurement_job_checkpoint.v1"
EXPECTED_ROUTE = {
    "execution_backend": BACKEND,
    "model_path": MODEL_PATH,
    "thinking": THINKING,
    "agent_id": AGENT_ID,
    "persistent_lane_mode": LANE_MODE,
}
EXPECTED_MANIFEST_ROUTE = {
    "agent_id": AGENT_ID,
    "execution_backend": BACKEND,
    "model_path": MODEL_PATH,
    "thinking": THINKING,
    "delivery_mode": LANE_MODE,
    "sandbox": "require",
    "cwd_override_allowed": False,
    "fallback_route_allowed": False,
    "mixed_route_parent_jobs_allowed": False,
    "dispatch_order": "strictly_sequential",
    "task_class": "narrow_non_finance_workspace_local_python_guard_hardening",
    "write_file_count_per_job": 2,
    "validation_budget": "narrow",
    "main_final_acceptance_required": True,
}
AUTHORITY_BOUNDARY = {
    "cohort_credit_only": True,
    "controller_dispatched_provider_job": False,
    "wave3_authorized": False,
    "automatic_route_promotion_allowed": False,
    "route_policy_change_authorized": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_portfolio_or_execution_authority": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}
ADMISSION_FIELDS = frozenset(
    "schema status generated_at_utc expires_at_utc cohort job sequence binding lane route attempt attempt_history authority_boundary errors".split()
)
PROOF_FIELDS = frozenset(
    "schema status generated_at_utc cohort job admission lane_terminal attempt_history usage worktree validation authority_boundary errors".split()
)
ACCEPTANCE_FIELDS = frozenset(
    "schema status cohort_id job_id manifest_sha256 admission_sha256 job_proof_sha256 accepted_post_apply_files accepted_validation_commands main_verified acceptance_scope wave3_authorized automatic_route_promotion_allowed".split()
)
CREDIT_FIELDS = frozenset(
    "schema status generated_at_utc cohort_id manifest_reference manifest_sha256 credit_number job_id previous_credit_sha256 admission_reference admission_sha256 technical_proof_reference technical_proof_sha256 main_acceptance_reference main_acceptance_sha256 lane_id attempt_number retry_count prior_zero_credit_incident_attempts usage_source_receipt_id source_binding_id source_snapshot_fingerprint accepted_post_apply_files main_acceptance_status wave3_review_gate_contribution wave3_authorized automatic_route_promotion_allowed authority_boundary".split()
)
COHORT_PROJECTION_FIELDS = frozenset(
    "cohort_id manifest_reference manifest_sha256".split()
)
JOB_PROJECTION_FIELDS = frozenset(
    "job_number job_id allowed_write_paths source_file_hashes".split()
)
ACTIVE_WORKTREE_FIELDS = frozenset(
    "job_id baseline_commit manifest_sha256 allowed_write_paths source_file_hashes".split()
)
BINDING_HANDOFF_FIELDS = frozenset(
    "reference sha256 frozen_snapshot_id contract_sha256".split()
)
BINDING_CALIBRATION_FIELDS = frozenset(
    "reference sha256 job_id changed_paths strict_projection".split()
)
ADMISSION_JOB_FIELDS = frozenset(
    "job_number job_id source_file_hashes focused_test compile_test".split()
)
ADMISSION_LANE_FIELDS = frozenset(
    "lane_id workflow_id workstream_id created_at_utc allowed_write_paths".split()
)
ADMISSION_BINDING_FIELDS = frozenset(
    "reference sha256 schema calibration_proof_reference calibration_job_id calibration_allowed_write_paths".split()
)
VALIDATION_FIELDS = frozenset("commands validated_post_apply_files".split())
VALIDATION_COMMAND_FIELDS = frozenset(
    "command exit_code stdout_sha256 stderr_sha256 stdout_artifact stderr_artifact".split()
)
RETAINED_INCIDENT_IDENTITIES = {
    ("wave2-cohort-job-01-compact-exec-cwd", 1): {
        "attempt_id": "wave2-cohort-job-01-a1",
        "task_name": "vt1_tomqds62y4demc7h7fynmkwkaquikmadbgdoq7crymju4gtkuema",
        "run_id_sha256": "88a532b24ac8229cd2381637bdbd88425e9968992d573885c565392abe124275",
        "session_key_sha256": "d18903c3d78e400014c6be65be59175ed88be3cb9443514111a348bf68e5d12a",
        "session_id_sha256": "b84485f5696871fb3c253f586acb81295477f92ada5312b29a9aaa285f12d637",
    },
    ("wave2-cohort-job-01-compact-exec-cwd", 2): {
        "attempt_id": "wave2-cohort-job-01-a2",
        "task_name": "vt1_qbjsrenzcuieebkarqglhcb6gy6rionzlnyybrd5vszylwi4awga",
        "run_id_sha256": "d09c99899778060b2d5c3d76d67bef5eaa313571354ee0e85551341b5d114470",
        "session_key_sha256": "6e4620cdc7de19271f9d920e5e84d070665f3df4a343b10a8fe5b3a3c548fa0c",
        "session_id_sha256": "a4468d0e019766daa39b1de41b30b2224c040d784141c33c2143a1bb5cce9db9",
    },
    ("wave2-cohort-job-02-lane-dirty-porcelain-parser", 1): {
        "attempt_id": "wave2-cohort-job-02-a1",
        "task_name": "vt1_y74gp3crfhjs3dsbz57xbbmizoghotlwknml2y2h2rjn7sf4iw7q",
        "run_id_sha256": "dfb22f53fc2759f9116b4b1f408c2465b6704a09f4f96f5ee0cef1021d3baa4d",
        "session_key_sha256": "1a97b761fbfe1329b4de4961ec99013301d8f4a5c9906ddcd1604419137b5e7c",
        "session_id_sha256": "347df513f81392a0047f1181a4cc658c9a168d43b896dcf7b7aad07829983787",
    },
}
HANDOFF_MANIFEST_FIELDS = frozenset(
    "schema generated_at_utc swarm_id status activation_job_contract expected_lanes authority_boundary use_rule validation".split()
)
HANDOFF_ACTIVATION_FIELDS = frozenset(
    "schema bound_at_utc job_id source_root source_base_label allowed_files allowed_outputs transient_test_output_contract old_rejected_source_hold_path fresh_worktree_rollback_hold_path sibling_sentinel_rollback_hold_path objective acceptance_commands stop_lines".split()
)
HANDOFF_LANE_FIELDS = frozenset(
    "lane_id status packet_id session_id session_label owner_workflow started_at_utc updated_at_utc verdict required_artifacts allow_partial handoff attempt incident authority_boundary".split()
)
FROZEN_HANDOFF_FIELDS = frozenset(
    "contract_version base_path budget files transport observed frozen_snapshot_id contract_sha256 preflight".split()
)
FROZEN_HANDOFF_BUDGET_FIELDS = frozenset(
    "max_files max_total_bytes max_context_tokens token_estimator".split()
)
FROZEN_HANDOFF_TRANSPORT_FIELDS = frozenset(
    "delivery_mode attachment_format one_source_file_per_attachment max_attachment_bytes max_physical_line_bytes compression_or_aggregate_bundle_allowed receiver_readback_required shared_workspace_writeback_verified".split()
)
FROZEN_HANDOFF_OBSERVED_FIELDS = frozenset(
    "file_count total_bytes estimated_context_tokens".split()
)
FROZEN_HANDOFF_PREFLIGHT_FIELDS = frozenset(
    "status checks errors fingerprint".split()
)
FROZEN_HANDOFF_CHECK_FIELDS = frozenset("name ok".split())
FROZEN_HANDOFF_FILE_FIELDS = frozenset(
    "path size_bytes sha256 attachment_id attachment_format utf8 compressed_or_bundle max_physical_line_bytes".split()
)
HANDOFF_REQUIRED_ARTIFACT_FIELDS = frozenset("path kind".split())
HANDOFF_VALIDATION_FIELDS = frozenset("status errors warnings".split())
HANDOFF_AUTHORITY_BOUNDARY = {
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
CALIBRATION_PAYLOAD_FIELDS = frozenset(
    "schema status observed_at_utc expires_at_utc agent_id runtime capabilities evidence".split()
)
CALIBRATION_RUNTIME_FIELDS = frozenset(
    "execution_backend provider model thinking openclaw_version config_sha256".split()
)
CALIBRATION_STRICT_FIELDS = frozenset("proof_schema runtime worktree".split())
CALIBRATION_WORKTREE_PROJECTION_FIELDS = frozenset(
    "job_id baseline_commit manifest_reference manifest_sha256 changed_paths git_path_inventory_sha256".split()
)
PROOF_AUTHORITY_BOUNDARY = {
    **AUTHORITY_BOUNDARY,
    "main_acceptance_pending": True,
    "cohort_credit_granted": False,
}


class CohortError(RuntimeError):
    """A deterministic cohort gate failure."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise CohortError("timestamp_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CohortError("timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CohortError("timestamp_timezone_required")
    return parsed.astimezone(timezone.utc)


def _exact_int(value: Any, *, minimum: int = 0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _exact_bool(value: Any, expected: bool) -> bool:
    return isinstance(value, bool) and value is expected


def _exact_projection(value: Any, expected: Any) -> bool:
    """Compare JSON-shaped values without bool/int/float equality aliases."""
    if isinstance(expected, dict):
        return (
            isinstance(value, dict)
            and set(value) == set(expected)
            and all(_exact_projection(value[key], item) for key, item in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(value, list)
            and len(value) == len(expected)
            and all(
                _exact_projection(observed, item)
                for observed, item in zip(value, expected)
            )
        )
    return type(value) is type(expected) and value == expected


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CohortError("artifact_not_canonicalizable") from exc


def _normal_relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        return None
    if value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        return None
    parts = PurePosixPath(value).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return PurePosixPath(*parts).as_posix()


def _workspace_reference_path(reference: Any, *, root: Path = ROOT) -> Path:
    normalized = _normal_relative_path(reference)
    if normalized is None or not normalized.startswith(
        "tmp/implementation-builder-scoped-worktree/"
    ):
        raise CohortError("artifact_reference_invalid")
    try:
        resolved_root = root.resolve()
        path = (resolved_root / normalized).resolve(strict=True)
        path.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise CohortError("artifact_reference_unreadable") from exc
    if not path.is_file() or path.is_symlink():
        raise CohortError("artifact_reference_not_regular")
    return path


def _workspace_path_from_value(value: Any, *, root: Path = ROOT) -> Path:
    if not isinstance(value, str) or not value:
        raise CohortError("workspace_path_invalid")
    raw = Path(value).expanduser()
    try:
        resolved_root = root.resolve()
        path = (raw if raw.is_absolute() else resolved_root / raw).resolve(strict=True)
        path.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise CohortError("workspace_path_escape_or_missing") from exc
    if not path.is_file() or path.is_symlink():
        raise CohortError("workspace_path_not_regular")
    return path


def _read_json_bytes(raw: bytes, *, max_bytes: int = MAX_JSON_BYTES) -> dict[str, Any]:
    if not raw or len(raw) > max_bytes:
        raise CohortError("json_size_invalid")
    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CohortError("json_malformed") from exc
    if not isinstance(payload, dict):
        raise CohortError("json_object_required")
    return payload


def _read_json_path_with_sha256(
    path: Path, *, max_bytes: int = MAX_JSON_BYTES
) -> tuple[dict[str, Any], str]:
    """Parse and hash one immutable byte observation of a JSON artifact."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CohortError("json_unreadable") from exc
    return _read_json_bytes(raw, max_bytes=max_bytes), _sha256_bytes(raw)


def _read_json_path(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> dict[str, Any]:
    return _read_json_path_with_sha256(path, max_bytes=max_bytes)[0]


def _read_json_reference(reference: Any, *, root: Path = ROOT) -> tuple[dict[str, Any], Path, str]:
    path = _workspace_reference_path(reference, root=root)
    payload, digest = _read_json_path_with_sha256(path)
    return payload, path, digest


def _artifact_reference(path: Path, *, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise CohortError("artifact_path_outside_workspace") from exc


def _write_once(path: Path, payload: dict[str, Any]) -> str:
    raw = _canonical_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise CohortError("immutable_artifact_conflict")
        return _sha256_bytes(raw)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return _sha256_bytes(raw)


def _write_bytes_once(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise CohortError("immutable_output_conflict")
        return _sha256_bytes(raw)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return _sha256_bytes(raw)


def _job_files(job: dict[str, Any]) -> list[dict[str, Any]]:
    raw_files = job.get("write_files")
    if not isinstance(raw_files, list) or len(raw_files) != 2:
        raise CohortError("manifest_job_file_count_invalid")
    rows: list[dict[str, Any]] = []
    for raw in raw_files:
        row = raw if isinstance(raw, dict) else {}
        path = _normal_relative_path(row.get("path"))
        size = row.get("bytes")
        digest = row.get("sha256")
        if (
            path is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 1
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise CohortError("manifest_job_file_invalid")
        rows.append({"path": path, "bytes": size, "sha256": digest})
    if len({row["path"] for row in rows}) != 2:
        raise CohortError("manifest_job_file_duplicate")
    return sorted(rows, key=lambda row: row["path"])


def load_frozen_manifest(
    *,
    root: Path = ROOT,
    manifest_reference: str = MANIFEST_REFERENCE,
    expected_sha256: str = MANIFEST_SHA256,
) -> dict[str, Any]:
    path = (root / manifest_reference).resolve(strict=True)
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CohortError("manifest_path_escape") from exc
    manifest, observed_sha256 = _read_json_path_with_sha256(path)
    if observed_sha256 != expected_sha256:
        raise CohortError("manifest_hash_mismatch")
    if (
        manifest.get("schema") != "veritas.wave2_measurement_cohort_manifest.v1"
        or manifest.get("status") != "frozen_pending_hot_activation_and_sequential_dispatch"
        or manifest.get("cohort_id") != COHORT_ID
        or not _exact_projection(
            manifest.get("fixed_route_contract"), EXPECTED_MANIFEST_ROUTE
        )
    ):
        raise CohortError("manifest_contract_invalid")
    boundary = manifest.get("authority_boundary")
    if not isinstance(boundary, dict) or boundary.get("preparation_only") is not True:
        raise CohortError("manifest_authority_invalid")
    for key in (
        "provider_job_dispatch_authorized",
        "automatic_route_promotion_allowed",
        "wave3_authorized",
        "finance_canon_portfolio_or_execution_authority",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            raise CohortError("manifest_authority_invalid")
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 10:
        raise CohortError("manifest_roster_size_invalid")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    normalized_jobs: list[dict[str, Any]] = []
    for expected_number, raw_job in enumerate(jobs, start=1):
        job = raw_job if isinstance(raw_job, dict) else {}
        job_id = job.get("job_id")
        if (
            not _exact_int(job.get("job_number"), minimum=1)
            or job.get("job_number") != expected_number
            or not isinstance(job_id, str)
            or not job_id
            or job_id in seen_ids
        ):
            raise CohortError("manifest_roster_identity_invalid")
        files = _job_files(job)
        if any(row["path"] in seen_paths for row in files):
            raise CohortError("manifest_roster_path_reused")
        seen_ids.add(job_id)
        seen_paths.update(row["path"] for row in files)
        normalized = dict(job)
        normalized["write_files"] = files
        normalized_jobs.append(normalized)
    manifest = dict(manifest)
    manifest["jobs"] = normalized_jobs
    return manifest


def load_frozen_restart_packet(
    *,
    root: Path = ROOT,
    packet_reference: str = RESTART_PACKET_REFERENCE,
) -> tuple[dict[str, Any], str]:
    """Verify the zero-credit qualification and every frozen instrument byte."""
    packet_path = _workspace_reference_path(packet_reference, root=root)
    if not packet_path.is_file():
        raise CohortError("restart_packet_missing")
    packet, packet_sha256 = _read_json_path_with_sha256(packet_path)
    expected_attempts = {
        str(number): attempt
        for number, attempt in sorted(RESTART_EXPECTED_ATTEMPTS.items())
    }
    instrument = packet.get("frozen_instrument_sha256")
    qualification = packet.get("qualification")
    authority = packet.get("authority_boundary")
    stop_rules = packet.get("stop_rules")
    if (
        packet.get("schema") != RESTART_PACKET_SCHEMA
        or packet.get("status") != "frozen_pending_explicit_owner_resume"
        or packet.get("cohort_id") != COHORT_ID
        or packet.get("existing_qualifying_credit_count") != 1
        or packet.get("restart_job_numbers") != list(range(2, 11))
        or packet.get("expected_attempt_number_by_job") != expected_attempts
        or not isinstance(instrument, dict)
        or set(instrument) != set(FROZEN_INSTRUMENT_REFERENCES)
        or not isinstance(qualification, dict)
        or not isinstance(authority, dict)
        or not isinstance(stop_rules, dict)
    ):
        raise CohortError("restart_packet_contract_invalid")
    for reference in FROZEN_INSTRUMENT_REFERENCES:
        path = _workspace_path_from_value(reference, root=root)
        expected = instrument.get(reference)
        if (
            not path.is_file()
            or re.fullmatch(r"[0-9a-f]{64}", str(expected or "")) is None
            or _sha256_file(path) != expected
        ):
            raise CohortError("restart_instrument_drift:" + reference)
    qualification_reference = qualification.get("reference")
    qualification_sha256 = qualification.get("sha256")
    if (
        qualification_reference != QUALIFICATION_REFERENCE
        or re.fullmatch(r"[0-9a-f]{64}", str(qualification_sha256 or "")) is None
    ):
        raise CohortError("restart_qualification_binding_invalid")
    qualification_payload, _path, observed_qualification_sha256 = (
        _read_json_reference(qualification_reference, root=root)
    )
    if (
        observed_qualification_sha256 != qualification_sha256
        or qualification_payload.get("schema") != QUALIFICATION_SCHEMA
        or qualification_payload.get("status") != "ok"
        or qualification_payload.get("cohort_id") != COHORT_ID
        or qualification_payload.get("qualified_job_numbers") != list(range(2, 11))
        or qualification_payload.get("credit_awarded") is not False
        or qualification_payload.get("provider_dispatch_performed") is not False
        or qualification_payload.get("wave2_resumed") is not False
    ):
        raise CohortError("restart_qualification_binding_invalid")
    expected_stop_rules = {
        "max_elapsed_seconds": JOB_MAX_ELAPSED_SECONDS,
        "checkpoint_seconds": JOB_CHECKPOINT_SECONDS,
        "max_tool_calls": JOB_MAX_TOOL_CALLS,
        "attempts_per_restart_pass": 1,
        "same_pass_repairs": 0,
        "independent_qa_lanes": 0,
        "max_active_cohort_jobs": 1,
        "stop_on_first_failure": True,
    }
    if stop_rules != expected_stop_rules:
        raise CohortError("restart_stop_rules_invalid")
    if (
        authority.get("explicit_owner_resume_required") is not True
        or authority.get("resume_authorized") is not False
        or authority.get("provider_dispatch_authorized") is not False
        or authority.get("cohort_credit_granted") is not False
    ):
        raise CohortError("restart_packet_authority_invalid")
    return packet, packet_sha256


def _job_paths(job: dict[str, Any]) -> list[str]:
    return [row["path"] for row in _job_files(job)]


def _job_by_number(manifest: dict[str, Any], number: int) -> dict[str, Any]:
    jobs = manifest["jobs"]
    if number < 1 or number > len(jobs):
        raise CohortError("job_number_out_of_range")
    return jobs[number - 1]


def _job_by_id(manifest: dict[str, Any], job_id: str) -> dict[str, Any]:
    matches = [job for job in manifest["jobs"] if job.get("job_id") == job_id]
    if len(matches) != 1:
        raise CohortError("job_id_not_in_primary_roster")
    return matches[0]


def _job_dir(controller_root: Path, number: int) -> Path:
    return controller_root / f"job-{number:02d}"


def _admission_path(
    controller_root: Path, number: int, attempt_number: int = 1
) -> Path:
    if (
        isinstance(attempt_number, bool)
        or not isinstance(attempt_number, int)
        or attempt_number < 1
    ):
        raise CohortError("admission_attempt_number_invalid")
    name = "admission.json" if attempt_number == 1 else f"attempt-{attempt_number:02d}-admission.json"
    return _job_dir(controller_root, number) / name


def _proof_path(controller_root: Path, number: int) -> Path:
    return _job_dir(controller_root, number) / "technical-proof.json"


def _credit_path(controller_root: Path, number: int) -> Path:
    return _job_dir(controller_root, number) / "credit-receipt.json"


def _acceptance_path(controller_root: Path, number: int) -> Path:
    return _job_dir(controller_root, number) / "main-acceptance.json"


def _checkpoint_path(
    controller_root: Path, number: int, attempt_number: int
) -> Path:
    return (
        _job_dir(controller_root, number)
        / f"attempt-{attempt_number:02d}-five-minute-checkpoint.json"
    )


def _attempt_counter_errors(payload: Any, *, prefix: str) -> list[str]:
    row = payload if isinstance(payload, dict) else {}
    if "attempt_number" not in row or "retry_count" not in row:
        return [f"{prefix}_attempt_fields_missing"]
    attempt_number = row.get("attempt_number")
    retry_count = row.get("retry_count")
    if not _exact_int(attempt_number, minimum=1) or not _exact_int(retry_count):
        return [f"{prefix}_attempt_fields_invalid"]
    if retry_count != attempt_number - 1:
        return [f"{prefix}_retry_count_mismatch"]
    return []


def _admission_binding_time_errors(
    admission: dict[str, Any],
    binding: dict[str, Any],
    *,
    unexpired_at: datetime | None = None,
) -> list[str]:
    try:
        admission_generated = _parse_utc(admission.get("generated_at_utc"))
        admission_expires = _parse_utc(admission.get("expires_at_utc"))
        binding_generated = _parse_utc(binding.get("generated_at_utc"))
        binding_expires = _parse_utc(binding.get("expires_at_utc"))
    except CohortError:
        return ["admission_snapshot_binding_time_invalid"]
    errors: list[str] = []
    if (
        binding_generated > admission_generated
        or admission_generated >= admission_expires
        or admission_expires != binding_expires
    ):
        errors.append("admission_snapshot_binding_time_invalid")
    if unexpired_at is not None and admission_expires <= unexpired_at:
        errors.append("admission_binding_expired")
    return errors


def _successful_lane_outcome_errors(
    lane: dict[str, Any], *, accepted: bool
) -> list[str]:
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    errors: list[str] = []
    if runtime.get("incident_code") not in (None, ""):
        errors.append("lane_incident_present")
    if not _exact_int(runtime.get("incident_count")) or runtime.get(
        "incident_count"
    ) != 0:
        errors.append("lane_incident_count_not_exact_zero")
    expected_kinds = ["terminal_closeout"]
    if accepted:
        expected_kinds.append("main_acceptance_update")
    events = lane.get("outcome_events")
    if not isinstance(events, list) or len(events) != len(expected_kinds):
        return errors + ["lane_outcome_events_shape_invalid"]
    expected_rows: list[dict[str, Any]] = []
    event_times: list[datetime] = []
    for sequence, (raw, kind) in enumerate(zip(events, expected_kinds), start=1):
        row = raw if isinstance(raw, dict) else {}
        if set(row) != {"event_kind", "event_sequence", "recorded_at_utc"}:
            errors.append("lane_outcome_events_shape_invalid")
            continue
        if (
            row.get("event_kind") != kind
            or not _exact_int(row.get("event_sequence"), minimum=1)
            or row.get("event_sequence") != sequence
        ):
            errors.append("lane_outcome_events_sequence_invalid")
        try:
            event_times.append(_parse_utc(row.get("recorded_at_utc")))
        except CohortError:
            errors.append("lane_outcome_events_sequence_invalid")
        expected_rows.append(row)
    try:
        terminal_time = _parse_utc(
            lane.get("completed_at_utc") or lane.get("ended_at_utc")
        )
        if not event_times or event_times[0] != terminal_time:
            errors.append("lane_terminal_time_binding_invalid")
        if accepted and len(event_times) == 2 and event_times[0] >= event_times[1]:
            errors.append("lane_outcome_events_chronology_invalid")
    except CohortError:
        errors.append("lane_terminal_time_binding_invalid")
    if expected_rows:
        final = expected_rows[-1]
        if (
            runtime.get("outcome_event_kind") != final.get("event_kind")
            or not _exact_int(runtime.get("outcome_event_sequence"), minimum=1)
            or runtime.get("outcome_event_sequence") != final.get("event_sequence")
            or runtime.get("outcome_recorded_at_utc")
            != final.get("recorded_at_utc")
        ):
            errors.append("lane_outcome_event_runtime_drift")
    return errors


def _validation_contract_errors(
    proof: dict[str, Any], job: dict[str, Any]
) -> list[str]:
    validation = (
        proof.get("validation")
        if isinstance(proof.get("validation"), dict)
        else {}
    )
    commands = validation.get("commands")
    errors: list[str] = []
    if set(validation) != VALIDATION_FIELDS:
        errors.append("credit_validation_inventory_invalid")
    if not isinstance(commands, list) or len(commands) != 2:
        return errors + ["credit_validation_command_count_invalid"]
    for index, expected_command in enumerate(
        (job.get("focused_test"), job.get("compile_test"))
    ):
        row = commands[index] if isinstance(commands[index], dict) else {}
        if set(row) != VALIDATION_COMMAND_FIELDS:
            errors.append("credit_validation_command_inventory_invalid")
        exit_code = row.get("exit_code")
        if (
            row.get("command") != expected_command
            or not _exact_int(exit_code)
            or exit_code != 0
        ):
            errors.append("credit_validation_command_invalid")
    worktree = proof.get("worktree") if isinstance(proof.get("worktree"), dict) else {}
    if not _exact_projection(
        validation.get("validated_post_apply_files"), worktree.get("post_apply_files")
    ):
        errors.append("credit_validation_post_files_invalid")
    return sorted(set(errors))


def _technical_proof_contract_errors(
    proof: dict[str, Any],
    job: dict[str, Any],
    *,
    admission_reference: str,
    admission_sha256: str,
    admission: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if set(proof) != PROOF_FIELDS:
        errors.append("technical_proof_field_inventory_invalid")
    if (
        proof.get("schema") != PROOF_SCHEMA
        or proof.get("status") != "ok"
        or not _exact_projection(
            proof.get("cohort"),
            {
            "cohort_id": COHORT_ID,
            "manifest_reference": MANIFEST_REFERENCE,
            "manifest_sha256": MANIFEST_SHA256,
            },
        )
        or not _exact_projection(
            proof.get("job"),
            {
            "job_number": job["job_number"],
            "job_id": job["job_id"],
            "allowed_write_paths": _job_paths(job),
            },
        )
        or not _exact_projection(
            proof.get("authority_boundary"), PROOF_AUTHORITY_BOUNDARY
        )
        or proof.get("errors") != []
        or not isinstance(proof.get("attempt_history"), list)
    ):
        errors.append("technical_proof_contract_invalid")
    try:
        _parse_utc(proof.get("generated_at_utc"))
    except CohortError:
        errors.append("technical_proof_generated_at_invalid")
    binding = admission.get("binding") if isinstance(admission.get("binding"), dict) else {}
    expected_admission = {
        "reference": admission_reference,
        "sha256": admission_sha256,
        "binding_reference": binding.get("reference"),
        "binding_sha256": binding.get("sha256"),
    }
    if proof.get("admission") != expected_admission:
        errors.append("technical_proof_admission_binding_invalid")
    terminal = (
        proof.get("lane_terminal")
        if isinstance(proof.get("lane_terminal"), dict)
        else {}
    )
    expected_terminal_fields = {
        "lane_id",
        "workstream_id",
        "completed_at_utc",
        "validator_result",
        "closure_durability",
        "attempt_number",
        "retry_count",
        "incident_code",
        "incident_count",
        "outcome_events",
        "outcome_event_kind",
        "outcome_event_sequence",
        "outcome_recorded_at_utc",
    }
    if set(terminal) != expected_terminal_fields:
        errors.append("technical_proof_terminal_inventory_invalid")
    errors.extend(_attempt_counter_errors(terminal, prefix="technical_proof"))
    if terminal.get("incident_code") not in (None, "") or (
        terminal.get("incident_count") != 0
        or isinstance(terminal.get("incident_count"), bool)
    ):
        errors.append("technical_proof_incident_contract_invalid")
    expected_event = {
        "event_kind": "terminal_closeout",
        "event_sequence": 1,
        "recorded_at_utc": terminal.get("outcome_recorded_at_utc"),
    }
    terminal_events = (
        terminal.get("outcome_events")
        if isinstance(terminal.get("outcome_events"), list)
        else []
    )
    first_terminal_event = (
        terminal_events[0]
        if terminal_events and isinstance(terminal_events[0], dict)
        else {}
    )
    if (
        not _exact_projection(terminal_events, [expected_event])
        or terminal.get("outcome_event_kind") != "terminal_closeout"
        or not _exact_int(terminal.get("outcome_event_sequence"), minimum=1)
        or not _exact_int(first_terminal_event.get("event_sequence"), minimum=1)
        or terminal.get("outcome_event_sequence") != 1
    ):
        errors.append("technical_proof_outcome_events_invalid")
    for field in ("completed_at_utc", "outcome_recorded_at_utc"):
        try:
            _parse_utc(terminal.get(field))
        except CohortError:
            errors.append("technical_proof_terminal_time_invalid")
    try:
        completed = _parse_utc(terminal.get("completed_at_utc"))
        outcome = _parse_utc(terminal.get("outcome_recorded_at_utc"))
        generated = _parse_utc(proof.get("generated_at_utc"))
        admission_generated = _parse_utc(admission.get("generated_at_utc"))
        admission_expires = _parse_utc(admission.get("expires_at_utc"))
        if not (
            completed == outcome
            and admission_generated <= completed <= generated < admission_expires
        ):
            errors.append("technical_proof_time_binding_invalid")
    except CohortError:
        errors.append("technical_proof_time_binding_invalid")
    if terminal.get("validator_result") != "pass" or terminal.get(
        "closure_durability"
    ) != "verified":
        errors.append("technical_proof_terminal_disposition_invalid")
    errors.extend(_validation_contract_errors(proof, job))
    return sorted(set(errors))


def _proof_lane_binding_errors(
    proof: dict[str, Any], admission: dict[str, Any], lane: dict[str, Any] | None = None
) -> list[str]:
    terminal = proof.get("lane_terminal") if isinstance(proof.get("lane_terminal"), dict) else {}
    admitted = admission.get("lane") if isinstance(admission.get("lane"), dict) else {}
    errors: list[str] = []
    if any(terminal.get(key) != admitted.get(key) for key in ("lane_id", "workstream_id")):
        errors.append("technical_proof_terminal_identity_binding_invalid")
    if lane is not None:
        events = lane.get("outcome_events") if isinstance(lane.get("outcome_events"), list) else []
        first = events[0] if events and isinstance(events[0], dict) else {}
        if (
            terminal.get("lane_id") != lane.get("lane_id")
            or terminal.get("workstream_id") != lane.get("workstream_id")
        ):
            errors.append("technical_proof_terminal_identity_binding_invalid")
        if terminal.get("completed_at_utc") != (
            lane.get("completed_at_utc") or lane.get("ended_at_utc")
        ):
            errors.append("technical_proof_terminal_time_binding_invalid")
        if (
            terminal.get("outcome_events") != [first]
            or terminal.get("outcome_event_kind") != first.get("event_kind")
            or terminal.get("outcome_event_sequence") != first.get("event_sequence")
            or terminal.get("outcome_recorded_at_utc") != first.get("recorded_at_utc")
        ):
            errors.append("technical_proof_terminal_prefix_binding_invalid")
    return errors


def _basic_credit_errors(
    credit: dict[str, Any],
    job: dict[str, Any],
    *,
    previous_credit_sha256: str | None,
) -> list[str]:
    errors: list[str] = []
    if set(credit) != CREDIT_FIELDS:
        errors.append("credit_field_inventory_invalid")
    if credit.get("schema") != CREDIT_SCHEMA or credit.get("status") != "credited":
        errors.append("credit_schema_or_status_invalid")
    if (
        credit.get("cohort_id") != COHORT_ID
        or credit.get("manifest_reference") != MANIFEST_REFERENCE
        or credit.get("manifest_sha256") != MANIFEST_SHA256
    ):
        errors.append("credit_cohort_invalid")
    if (
        not _exact_int(credit.get("credit_number"), minimum=1)
        or credit.get("credit_number") != job["job_number"]
        or credit.get("job_id") != job["job_id"]
    ):
        errors.append("credit_sequence_identity_invalid")
    if credit.get("previous_credit_sha256") != previous_credit_sha256:
        errors.append("credit_chain_hash_invalid")
    if (
        credit.get("wave3_authorized") is not False
        or credit.get("automatic_route_promotion_allowed") is not False
        or not _exact_projection(credit.get("authority_boundary"), AUTHORITY_BOUNDARY)
        or credit.get("main_acceptance_status") != "accepted"
        or not _exact_int(
            credit.get("wave3_review_gate_contribution"), minimum=1
        )
        or credit.get("wave3_review_gate_contribution") != 1
    ):
        errors.append("credit_authority_invalid")
    errors.extend(_attempt_counter_errors(credit, prefix="credit"))
    if (
        not _exact_int(credit.get("prior_zero_credit_incident_attempts"))
        or credit.get("prior_zero_credit_incident_attempts")
        != credit.get("retry_count")
    ):
        errors.append("credit_prior_incident_count_invalid")
    post_files = credit.get("accepted_post_apply_files")
    if not isinstance(post_files, list) or len(post_files) != 2:
        errors.append("credit_post_files_invalid")
    else:
        paths = [row.get("path") for row in post_files if isinstance(row, dict)]
        if sorted(paths) != _job_paths(job):
            errors.append("credit_post_paths_invalid")
    return errors


def _current_post_file_errors(
    rows: Any,
    *,
    root: Path,
) -> list[str]:
    if not isinstance(rows, list):
        return ["post_files_missing"]
    errors: list[str] = []
    for raw in rows:
        row = raw if isinstance(raw, dict) else {}
        path = _normal_relative_path(row.get("path"))
        digest = row.get("sha256")
        size = row.get("bytes")
        if path is None or not isinstance(digest, str) or not _exact_int(size, minimum=0):
            errors.append("post_file_row_invalid")
            continue
        try:
            data = (root / path).read_bytes()
        except OSError:
            errors.append(f"post_file_missing:{path}")
            continue
        if len(data) != size or _sha256_bytes(data) != digest:
            errors.append(f"post_file_drift:{path}")
    return errors


def _bound_credit_artifact_errors(
    credit: dict[str, Any],
    job: dict[str, Any],
    *,
    root: Path,
    controller_root: Path,
) -> list[str]:
    """Reopen every artifact a credit claims instead of trusting its summary."""
    number = int(job["job_number"])
    errors: list[str] = []
    if set(credit) != CREDIT_FIELDS:
        errors.append("credit_field_inventory_invalid")
    errors.extend(_attempt_counter_errors(credit, prefix="credit"))
    if errors:
        return sorted(set(errors))
    attempt_number = credit["attempt_number"]
    admission_path = _admission_path(controller_root, number, attempt_number)
    proof_path = _proof_path(controller_root, number)
    acceptance_path = _acceptance_path(controller_root, number)
    expected_references = {
        "admission_reference": _artifact_reference(admission_path, root=root),
        "technical_proof_reference": _artifact_reference(proof_path, root=root),
        "main_acceptance_reference": _artifact_reference(acceptance_path, root=root),
    }
    for field, expected in expected_references.items():
        if credit.get(field) != expected:
            errors.append(f"credit_{field}_invalid")
    try:
        admission, admission_sha256 = _read_json_path_with_sha256(admission_path)
        proof, proof_sha256 = _read_json_path_with_sha256(proof_path)
        acceptance, acceptance_sha256 = _read_json_path_with_sha256(
            acceptance_path
        )
    except (CohortError, OSError):
        return errors + ["credit_bound_artifact_missing_or_invalid"]
    if (
        credit.get("admission_sha256") != admission_sha256
        or credit.get("technical_proof_sha256") != proof_sha256
        or credit.get("main_acceptance_sha256") != acceptance_sha256
    ):
        errors.append("credit_bound_artifact_hash_invalid")
    admission_cohort = (
        admission.get("cohort")
        if isinstance(admission.get("cohort"), dict)
        else {}
    )
    admission_job = (
        admission.get("job") if isinstance(admission.get("job"), dict) else {}
    )
    if (
        set(admission) != ADMISSION_FIELDS
        or admission.get("schema") != ADMISSION_SCHEMA
        or admission.get("status") != "ok"
        or set(admission_cohort) != COHORT_PROJECTION_FIELDS
        or admission_cohort.get("cohort_id") != COHORT_ID
        or admission_cohort.get("manifest_reference") != MANIFEST_REFERENCE
        or admission_cohort.get("manifest_sha256") != MANIFEST_SHA256
        or set(admission_job) != ADMISSION_JOB_FIELDS
        or admission_job.get("job_id") != job["job_id"]
    ):
        errors.append("credit_admission_contract_invalid")
    proof_errors = _technical_proof_contract_errors(
        proof,
        job,
        admission_reference=expected_references["admission_reference"],
        admission_sha256=admission_sha256,
        admission=admission,
    )
    proof_errors.extend(_proof_lane_binding_errors(proof, admission))
    if proof_errors:
        errors.append("credit_technical_proof_contract_invalid")
        errors.extend(proof_errors)
    errors.extend(
        _validate_acceptance(
            acceptance,
            proof,
            admission_sha256=admission_sha256,
            proof_sha256=proof_sha256,
        )
    )
    proof_usage = proof.get("usage") if isinstance(proof.get("usage"), dict) else {}
    proof_worktree = (
        proof.get("worktree") if isinstance(proof.get("worktree"), dict) else {}
    )
    proof_terminal = (
        proof.get("lane_terminal")
        if isinstance(proof.get("lane_terminal"), dict)
        else {}
    )
    proof_history = proof.get("attempt_history")
    if (
        not _exact_projection(
            credit.get("accepted_post_apply_files"),
            proof_worktree.get("post_apply_files"),
        )
        or credit.get("usage_source_receipt_id")
        != proof_usage.get("usage_source_receipt_id")
        or credit.get("source_binding_id") != proof_usage.get("source_binding_id")
        or credit.get("source_snapshot_fingerprint")
        != proof_usage.get("source_snapshot_fingerprint")
        or credit.get("main_acceptance_status") != "accepted"
        or not _exact_int(
            credit.get("wave3_review_gate_contribution"), minimum=1
        )
        or credit.get("wave3_review_gate_contribution") != 1
        or not _exact_projection(credit.get("authority_boundary"), AUTHORITY_BOUNDARY)
        or not _exact_int(credit.get("attempt_number"), minimum=1)
        or not _exact_int(credit.get("retry_count"))
        or not _exact_int(credit.get("prior_zero_credit_incident_attempts"))
        or credit.get("attempt_number")
        != proof_terminal.get("attempt_number")
        or credit.get("retry_count")
        != proof_terminal.get("retry_count")
        or credit.get("retry_count") != credit.get("attempt_number") - 1
        or credit.get("prior_zero_credit_incident_attempts")
        != credit.get("retry_count")
        or credit.get("prior_zero_credit_incident_attempts")
        != (len(proof_history) if isinstance(proof_history, list) else -1)
    ):
        errors.append("credit_summary_binding_invalid")
    try:
        _parse_utc(credit.get("generated_at_utc"))
    except CohortError:
        errors.append("credit_generated_at_invalid")
    return sorted(set(errors))


def _validation_artifact_errors(
    proof: dict[str, Any],
    job: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    validation = (
        proof.get("validation")
        if isinstance(proof.get("validation"), dict)
        else {}
    )
    commands = validation.get("commands")
    expected_commands = [job.get("focused_test"), job.get("compile_test")]
    errors = _validation_contract_errors(proof, job)
    if not isinstance(commands, list) or len(commands) != 2:
        return sorted(set(errors))
    for index, expected_command in enumerate(expected_commands):
        row = commands[index] if isinstance(commands[index], dict) else {}
        for stream in ("stdout", "stderr"):
            digest = row.get(f"{stream}_sha256")
            reference = row.get(f"{stream}_artifact")
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                errors.append("credit_validation_output_digest_invalid")
                continue
            try:
                artifact = _workspace_reference_path(reference, root=root)
            except CohortError:
                errors.append("credit_validation_output_artifact_invalid")
                continue
            if _sha256_file(artifact) != digest:
                errors.append("credit_validation_output_hash_invalid")
    return sorted(set(errors))


def _historical_credit_evidence_errors(
    credit: dict[str, Any],
    job: dict[str, Any],
    *,
    root: Path,
    controller_root: Path,
    register_path: Path,
    completed_root: Path,
    agent_state_root: Path,
    state_db_path: Path,
) -> list[str]:
    """Reverify the protected authority chain behind one historical credit."""
    errors = _bound_credit_artifact_errors(
        credit, job, root=root, controller_root=controller_root
    )
    if errors:
        return errors
    number = int(job["job_number"])
    try:
        attempt_number = credit["attempt_number"]
        admission_path = _admission_path(controller_root, number, attempt_number)
        admission = _read_json_path(admission_path)
        proof = _read_json_path(_proof_path(controller_root, number))
        acceptance_path = _acceptance_path(controller_root, number)
        register = _load_register(register_path)
        attempt_lanes = _find_job_lanes(
            register,
            job,
            immutable_credited_attempt_number=credit.get("attempt_number"),
        )
        lane = attempt_lanes[-1]
        import concurrent_lane_manager as lanes
    except (CohortError, ImportError, OSError) as exc:
        return ["credit_historical_control_source_invalid:" + str(exc)]
    receipt_sidecar = _artifact_reference(
        lanes.usage_receipt_store_path(register_path), root=root
    )
    errors.extend(
        _admission_snapshot_errors(
            admission,
            job,
            lane,
            attempt_lanes[:-1],
            root=root,
            controller_root=controller_root,
        )
    )
    errors.extend(
        _lane_contract_errors(
            lane,
            job,
            terminal=True,
            accepted=True,
            receipt_sidecar=receipt_sidecar,
            attempt_number=attempt_number,
        )
    )
    errors.extend(_proof_lane_binding_errors(proof, admission, lane))
    errors.extend(
        _prior_attempt_history_errors(
            attempt_lanes[:-1],
            job,
            receipt_sidecar=receipt_sidecar,
            root=root,
            controller_root=controller_root,
        )
    )
    expected_route = {
        **EXPECTED_ROUTE,
        "fallback_allowed": False,
        "cwd_override_allowed": False,
    }
    expected_sequence = {
        "previous_credited_count": number - 1,
        "expected_job_number": number,
        "contiguous": True,
        "other_active_cohort_job": False,
    }
    if (
        not _exact_projection(admission.get("route"), expected_route)
        or not _exact_projection(admission.get("sequence"), expected_sequence)
        or not _exact_projection(
            admission.get("job", {}).get("source_file_hashes"), _job_files(job)
        )
        or admission.get("job", {}).get("focused_test") != job.get("focused_test")
        or admission.get("job", {}).get("compile_test") != job.get("compile_test")
        or admission.get("lane", {}).get("lane_id") != lane.get("lane_id")
        or sorted(admission.get("lane", {}).get("allowed_write_paths") or [])
        != _job_paths(job)
        or credit.get("lane_id") != lane.get("lane_id")
        or attempt_number != len(attempt_lanes)
        or not _exact_projection(
            admission.get("attempt_history"),
            _attempt_history_projection(
                attempt_lanes[:-1],
                job=job,
                root=root,
                controller_root=controller_root,
            ),
        )
        or not _exact_projection(
            proof.get("attempt_history"),
            _attempt_history_projection(
                attempt_lanes[:-1],
                job=job,
                root=root,
                controller_root=controller_root,
            ),
        )
    ):
        errors.append("credit_admission_lane_route_binding_invalid")
    try:
        expected_attempt = _attempt_projection(lane)
    except CohortError as exc:
        errors.append("credit_attempt_projection_invalid:" + str(exc))
    else:
        if not _exact_projection(admission.get("attempt"), expected_attempt):
            errors.append("credit_admission_attempt_binding_invalid")
    expected_acceptance_reference = _artifact_reference(acceptance_path, root=root)
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    if runtime.get("main_acceptance_evidence") != expected_acceptance_reference:
        errors.append("credit_lane_acceptance_evidence_invalid")
    if errors:
        return sorted(set(errors))
    try:
        usage = _usage_proof(
            lane,
            register_path=register_path,
            agent_state_root=agent_state_root,
            state_db_path=state_db_path,
        )
    except (CohortError, OSError) as exc:
        errors.append("credit_protected_usage_invalid:" + str(exc))
    else:
        if usage != proof.get("usage"):
            errors.append("credit_protected_usage_drift")
    close_reference = proof.get("worktree", {}).get("close_proof_reference")
    try:
        worktree, post_files = _worktree_proof(
            job,
            close_reference,
            root=root,
            completed_root=completed_root,
        )
    except (CohortError, OSError, subprocess.SubprocessError) as exc:
        errors.append("credit_worktree_proof_invalid:" + str(exc))
    else:
        if not _exact_projection(worktree, proof.get("worktree")):
            errors.append("credit_worktree_proof_drift")
        if not _exact_projection(post_files, credit.get("accepted_post_apply_files")):
            errors.append("credit_worktree_post_files_drift")
    errors.extend(_validation_artifact_errors(proof, job, root=root))
    return sorted(set(errors))


def load_credit_chain(
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    controller_root: Path = CONTROLLER_ROOT,
    current_verifier: Callable[[dict[str, Any], dict[str, Any]], list[str]] | None = None,
    artifact_verifier: Callable[[dict[str, Any], dict[str, Any]], list[str]] | None = None,
    register_path: Path = REGISTER_PATH,
    completed_root: Path = COMPLETED_WORKTREE_ROOT,
    agent_state_root: Path = AGENT_STATE_ROOT,
    state_db_path: Path = STATE_DB_PATH,
) -> tuple[list[dict[str, Any]], list[str]]:
    credits: list[dict[str, Any]] = []
    errors: list[str] = []
    previous_hash: str | None = None
    gap_seen = False
    for job in manifest["jobs"]:
        number = int(job["job_number"])
        path = _credit_path(controller_root, number)
        if not path.exists():
            gap_seen = True
            continue
        if gap_seen:
            errors.append(f"credit_gap_before_job_{number:02d}")
            continue
        try:
            credit, credit_sha256 = _read_json_path_with_sha256(path)
        except CohortError as exc:
            errors.append(f"credit_{number:02d}_{exc}")
            continue
        errors.extend(
            f"credit_{number:02d}_{item}"
            for item in _basic_credit_errors(
                credit, job, previous_credit_sha256=previous_hash
            )
        )
        bound_verifier = artifact_verifier or (
            lambda row, selected_job: _historical_credit_evidence_errors(
                row,
                selected_job,
                root=root,
                controller_root=controller_root,
                register_path=register_path,
                completed_root=completed_root,
                agent_state_root=agent_state_root,
                state_db_path=state_db_path,
            )
        )
        errors.extend(
            f"credit_{number:02d}_{item}"
            for item in bound_verifier(credit, job)
        )
        verifier = current_verifier or (
            lambda row, _job: _current_post_file_errors(
                row.get("accepted_post_apply_files"), root=root
            )
        )
        errors.extend(f"credit_{number:02d}_{item}" for item in verifier(credit, job))
        credits.append(credit)
        previous_hash = credit_sha256
    credited_count = len(credits)
    for number in range(credited_count + 2, 11):
        artifacts = [
            _admission_path(controller_root, number),
            _proof_path(controller_root, number),
            _acceptance_path(controller_root, number),
        ]
        artifacts.extend(
            sorted(_job_dir(controller_root, number).glob("attempt-*-admission.json"))
        )
        for artifact in artifacts:
            if artifact.exists():
                errors.append(f"later_artifact_across_gap:{artifact.name}:job-{number:02d}")
    receipt_ids = [str(row.get("usage_source_receipt_id") or "") for row in credits]
    binding_ids = [str(row.get("source_binding_id") or "") for row in credits]
    if any(not value for value in receipt_ids) or len(set(receipt_ids)) != len(receipt_ids):
        errors.append("credit_usage_receipt_reused_or_missing")
    if any(not value for value in binding_ids) or len(set(binding_ids)) != len(binding_ids):
        errors.append("credit_source_binding_reused_or_missing")
    return credits, sorted(set(errors))


def _preimage_errors(job: dict[str, Any], *, root: Path) -> list[str]:
    errors: list[str] = []
    paths = _job_paths(job)
    for expected in _job_files(job):
        try:
            raw = (root / expected["path"]).read_bytes()
        except OSError:
            errors.append(f"source_missing:{expected['path']}")
            continue
        if len(raw) != expected["bytes"] or _sha256_bytes(raw) != expected["sha256"]:
            errors.append(f"source_preimage_drift:{expected['path']}")
    try:
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--", *paths],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        errors.append("git_status_unavailable")
    else:
        if status.returncode != 0 or status.stdout.strip():
            errors.append("source_paths_not_git_clean")
    return errors


def _load_register(register_path: Path) -> dict[str, Any]:
    try:
        import concurrent_lane_manager as lanes
    except ImportError as exc:
        raise CohortError("lane_manager_unavailable") from exc
    return lanes.load_register(register_path)


def _receipt_sidecar_reference(register_path: Path, *, root: Path) -> str:
    try:
        import concurrent_lane_manager as lanes
    except ImportError as exc:
        raise CohortError("lane_manager_unavailable") from exc
    return _artifact_reference(lanes.usage_receipt_store_path(register_path), root=root)


def _find_job_lanes(
    register: dict[str, Any],
    job: dict[str, Any],
    *,
    immutable_credited_attempt_number: int | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for raw in register.get("lanes", []):
        lane = raw if isinstance(raw, dict) else {}
        runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
        if (
            runtime.get("parent_job_id") == job["job_id"]
            and runtime.get("phase") == "implementation"
        ):
            matches.append(lane)
    if not matches:
        raise CohortError("job_lane_missing")
    indexed: list[tuple[int, dict[str, Any]]] = []
    identity_values: dict[str, set[str]] = {
        "lane_id": set(),
        "workstream_id": set(),
        "attempt_id": set(),
        "attempt_correlation": set(),
    }
    for lane in matches:
        runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
        attempt_number = runtime.get("attempt_number")
        if (
            isinstance(attempt_number, bool)
            or not isinstance(attempt_number, int)
            or attempt_number < 1
        ):
            raise CohortError("job_attempt_number_invalid")
        try:
            created = _parse_utc(lane.get("created_at_utc"))
            started = (
                _parse_utc(lane.get("started_at_utc"))
                if lane.get("started_at_utc") is not None
                else None
            )
            ended_value = lane.get("ended_at_utc") or lane.get("completed_at_utc")
            ended = _parse_utc(ended_value) if ended_value is not None else None
        except CohortError as exc:
            raise CohortError("job_attempt_chronology_invalid") from exc
        if (
            (started is not None and created > started)
            or (ended is not None and created > ended)
            or (started is not None and ended is not None and started > ended)
        ):
            raise CohortError("job_attempt_chronology_invalid")
        identities = {
            "lane_id": lane.get("lane_id"),
            "workstream_id": lane.get("workstream_id"),
            "attempt_id": runtime.get("attempt_id"),
            "attempt_correlation": (
                runtime.get("attempt_correlation", {}).get("key_hash")
                if isinstance(runtime.get("attempt_correlation"), dict)
                else None
            ),
        }
        for field, raw_value in identities.items():
            if not isinstance(raw_value, str) or not raw_value:
                raise CohortError(f"job_{field}_invalid")
            if raw_value in identity_values[field]:
                raise CohortError(f"job_{field}_reused")
            identity_values[field].add(raw_value)
        indexed.append((attempt_number, lane))
    indexed.sort(key=lambda item: item[0])
    max_attempts = (
        immutable_credited_attempt_number
        if immutable_credited_attempt_number is not None
        else MAX_ATTEMPTS_PER_JOB
    )
    if not _exact_int(max_attempts, minimum=1) or len(indexed) > max_attempts:
        raise CohortError("job_retry_limit_exceeded")
    observed = [item[0] for item in indexed]
    if observed != list(range(1, len(indexed) + 1)):
        raise CohortError("job_attempt_sequence_invalid")
    for (_previous_number, previous), (_current_number, current) in zip(
        indexed, indexed[1:]
    ):
        previous_end = previous.get("ended_at_utc") or previous.get(
            "completed_at_utc"
        )
        current_created = current.get("created_at_utc")
        try:
            if _parse_utc(previous_end) >= _parse_utc(current_created):
                raise CohortError("job_attempt_chronology_invalid")
        except CohortError as exc:
            if str(exc) == "job_attempt_chronology_invalid":
                raise
            raise CohortError("job_attempt_chronology_invalid") from exc
    return [item[1] for item in indexed]


def _lane_contract_errors(
    lane: dict[str, Any],
    job: dict[str, Any],
    *,
    terminal: bool,
    accepted: bool = False,
    receipt_sidecar: str | None = None,
    attempt_number: int = 1,
) -> list[str]:
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    errors: list[str] = []
    expected_status = TERMINAL_LANE_STATUS if terminal else {"leased", "running"}
    if lane.get("owner") != AGENT_ID:
        errors.append("lane_owner_mismatch")
    if terminal:
        if lane.get("status") != expected_status:
            errors.append("lane_not_complete")
    elif lane.get("status") not in expected_status:
        errors.append("lane_not_admissible")
    observed_writes = sorted(lane.get("allowed_writes") or [])
    expected_writes = list(_job_paths(job))
    if terminal and receipt_sidecar:
        expected_writes.append(receipt_sidecar)
    if observed_writes != sorted(expected_writes):
        errors.append("lane_write_scope_mismatch")
    expected_runtime = {
        "agent_id": AGENT_ID,
        "parent_job_id": job["job_id"],
        "phase": "implementation",
        "model_path": MODEL_PATH,
        "thinking": THINKING,
        "expected_model_path": MODEL_PATH,
        "expected_thinking": THINKING,
        "expected_execution_backend": BACKEND,
    }
    for key, value in expected_runtime.items():
        if runtime.get(key) != value:
            errors.append(f"lane_runtime_{key}_mismatch")
    if int(job.get("job_number") or 0) >= 2:
        if runtime.get("max_elapsed_seconds") != JOB_MAX_ELAPSED_SECONDS:
            errors.append("lane_max_elapsed_seconds_mismatch")
        if runtime.get("max_tool_calls") != JOB_MAX_TOOL_CALLS:
            errors.append("lane_max_tool_calls_mismatch")
    actual_backend = runtime.get("actual_execution_backend")
    if terminal and actual_backend != BACKEND:
        errors.append("lane_actual_backend_mismatch")
    if (
        not _exact_int(runtime.get("attempt_number"), minimum=1)
        or runtime.get("attempt_number") != attempt_number
        or not _exact_int(runtime.get("retry_count"))
        or runtime.get("retry_count") != attempt_number - 1
        or runtime.get("is_first_attempt") is not (attempt_number == 1)
    ):
        errors.append("lane_attempt_sequence_mismatch")
    correlation = runtime.get("attempt_correlation")
    if (
        terminal
        and (
            not isinstance(runtime.get("attempt_id"), str)
            or not runtime.get("attempt_id")
            or not isinstance(correlation, dict)
            or correlation.get("attempt_source") != "attempt_id"
        )
    ):
        errors.append("lane_attempt_identity_not_protected")
    if runtime.get("incident_code") not in (None, ""):
        errors.append("lane_incident_present")
    incident_count = runtime.get("incident_count")
    if not _exact_int(incident_count) or incident_count != 0:
        errors.append("lane_incident_count_nonzero")
    events = lane.get("outcome_events")
    if isinstance(events, list) and any(
        isinstance(row, dict) and row.get("event_kind") == "incident" for row in events
    ):
        errors.append("lane_incident_event_present")
    try:
        created_at = _parse_utc(lane.get("created_at_utc"))
        started_at = (
            _parse_utc(lane.get("started_at_utc"))
            if lane.get("started_at_utc") is not None
            else None
        )
        terminal_at = (
            _parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
            if terminal
            else None
        )
        if (
            (started_at is not None and created_at > started_at)
            or (terminal_at is not None and created_at > terminal_at)
            or (
                terminal_at is not None
                and started_at is not None
                and started_at > terminal_at
            )
        ):
            errors.append("lane_time_chronology_invalid")
    except CohortError:
        errors.append("lane_created_at_invalid")
    if not terminal and (
        not _exact_projection(runtime.get("incident_code"), "")
        or not _exact_int(incident_count)
        or incident_count != 0
        or events != []
    ):
        errors.append("lane_active_incident_shape_invalid")
    if terminal:
        if int(job.get("job_number") or 0) >= 2:
            observed_elapsed = runtime.get("observed_elapsed_seconds")
            observed_tools = runtime.get("observed_tool_calls")
            if (
                not _exact_int(observed_elapsed)
                or observed_elapsed > JOB_MAX_ELAPSED_SECONDS
            ):
                errors.append("lane_elapsed_budget_exceeded_or_unavailable")
            if (
                not _exact_int(observed_tools)
                or observed_tools > JOB_MAX_TOOL_CALLS
            ):
                errors.append("lane_tool_budget_exceeded_or_unavailable")
        errors.extend(_successful_lane_outcome_errors(lane, accepted=accepted))
        if runtime.get("agent_role") != "implementation_builder":
            errors.append("lane_agent_role_mismatch")
        if runtime.get("validator_result") != "pass":
            errors.append("lane_validator_not_pass")
        if runtime.get("closure_durability") != "verified":
            errors.append("lane_closure_not_verified")
        if runtime.get("outcome_status") != "completed_without_incident":
            errors.append("lane_incident_free_outcome_not_explicit")
        expected_event_kind = (
            "main_acceptance_update" if accepted else "terminal_closeout"
        )
        expected_event_sequence = 2 if accepted else 1
        if runtime.get("outcome_event_kind") != expected_event_kind:
            errors.append("lane_terminal_event_missing")
        if runtime.get("outcome_event_sequence") != expected_event_sequence:
            errors.append("lane_terminal_event_sequence_invalid")
        if not isinstance(runtime.get("outcome_recorded_at_utc"), str):
            errors.append("lane_terminal_recorded_at_missing")
        if accepted:
            if runtime.get("main_acceptance_status") != "accepted":
                errors.append("lane_main_acceptance_not_exact")
        elif runtime.get("main_acceptance_status") not in (
            None,
            "",
            "pending",
            "accepted",
        ):
            errors.append("lane_main_acceptance_rejected")
    return sorted(set(errors))


def _authorization_provenance_errors(
    authorization: dict[str, Any],
) -> list[str]:
    """Reopen immutable owner evidence without applying present-time expiry rules."""
    try:
        import measurement_cohort_transport_binding as bindings
    except ImportError:
        return ["binding_snapshot_authorization_source_unavailable"]
    try:
        approval, read_error = bindings._read_owner_approval(
            authorization.get("reference"),
            session_root=bindings.OWNER_SESSION_ROOT,
        )
    except (OSError, TypeError, ValueError):
        return ["binding_snapshot_authorization_source_unavailable"]
    if read_error:
        suffix = (
            "unavailable"
            if read_error.endswith("_verifier_unavailable")
            else "invalid"
        )
        return [f"binding_snapshot_authorization_source_{suffix}"]
    if not isinstance(approval, dict):
        return ["binding_snapshot_authorization_source_invalid"]
    raw_lines = str(approval.get("content") or "").splitlines()
    if len(raw_lines) != 4 or raw_lines[0] != bindings.OWNER_APPROVAL_HEADER:
        return ["binding_snapshot_authorization_source_invalid"]
    fields: dict[str, str] = {}
    for line in raw_lines[1:]:
        key, separator, value = line.partition("=")
        if not separator or not key or key in fields:
            return ["binding_snapshot_authorization_source_invalid"]
        fields[key] = value
    if set(fields) != {"approval_id", "scope_sha256", "expires_at_utc"}:
        return ["binding_snapshot_authorization_source_invalid"]
    try:
        observed_at = approval.get("observed_at")
        if not isinstance(observed_at, datetime):
            raise CohortError("owner approval timestamp missing")
        if (
            approval.get("session_id") != authorization.get("source_session_id")
            or approval.get("message_id") != authorization.get("source_message_id")
            or approval.get("source_event_sha256")
            != authorization.get("source_event_sha256")
            or _parse_utc(authorization.get("issued_at_utc")) != observed_at
            or fields.get("approval_id") != authorization.get("approval_id")
            or fields.get("scope_sha256") != authorization.get("scope_sha256")
            or _parse_utc(fields.get("expires_at_utc"))
            != _parse_utc(authorization.get("expires_at_utc"))
        ):
            raise CohortError("owner approval projection mismatch")
    except CohortError:
        return ["binding_snapshot_authorization_source_invalid"]
    return []


def _frozen_handoff_errors(
    binding: dict[str, Any],
    payload: dict[str, Any],
    job: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    errors: list[str] = []
    expected_reference = job.get("activation_handoff")
    if (
        set(binding) != BINDING_HANDOFF_FIELDS
        or not isinstance(expected_reference, str)
        or binding.get("reference") != expected_reference
        or set(payload) != HANDOFF_MANIFEST_FIELDS
        or payload.get("schema") != "veritas.helper_lane_manifest.v3"
        or payload.get("status") != "ok"
        or not _exact_projection(
            payload.get("authority_boundary"), HANDOFF_AUTHORITY_BOUNDARY
        )
    ):
        errors.append("binding_snapshot_handoff_invalid")
    activation = (
        payload.get("activation_job_contract")
        if isinstance(payload.get("activation_job_contract"), dict)
        else {}
    )
    try:
        _parse_utc(payload.get("generated_at_utc"))
        _parse_utc(activation.get("bound_at_utc"))
    except CohortError:
        errors.append("binding_snapshot_handoff_invalid")
    expected_commands = [job.get("focused_test"), job.get("compile_test")]
    if (
        set(activation) != HANDOFF_ACTIVATION_FIELDS
        or activation.get("schema") != "veritas.wave2_job_activation_contract.v1"
        or activation.get("job_id") != job["job_id"]
        or not _exact_projection(activation.get("allowed_files"), _job_paths(job))
        or not _exact_projection(activation.get("allowed_outputs"), [])
        or not _exact_projection(
            activation.get("acceptance_commands"), expected_commands
        )
    ):
        errors.append("binding_snapshot_handoff_invalid")
    lanes = payload.get("expected_lanes")
    lane = (
        lanes[0]
        if isinstance(lanes, list)
        and len(lanes) == 1
        and isinstance(lanes[0], dict)
        else {}
    )
    required_artifacts = lane.get("required_artifacts")
    expected_artifacts = [
        {"path": path, "kind": "file"} for path in _job_paths(job)
    ]
    artifacts_well_shaped = (
        isinstance(required_artifacts, list)
        and all(
            isinstance(row, dict)
            and set(row) == HANDOFF_REQUIRED_ARTIFACT_FIELDS
            for row in required_artifacts
        )
    )
    frozen = lane.get("handoff") if isinstance(lane.get("handoff"), dict) else {}
    budget = frozen.get("budget") if isinstance(frozen.get("budget"), dict) else {}
    transport = (
        frozen.get("transport")
        if isinstance(frozen.get("transport"), dict)
        else {}
    )
    observed = (
        frozen.get("observed")
        if isinstance(frozen.get("observed"), dict)
        else {}
    )
    preflight = (
        frozen.get("preflight")
        if isinstance(frozen.get("preflight"), dict)
        else {}
    )
    checks = preflight.get("checks")
    files = frozen.get("files")
    file_rows = files if isinstance(files, list) else []
    files_well_shaped = len(file_rows) == len(_job_files(job)) and all(
        isinstance(row, dict) and set(row) == FROZEN_HANDOFF_FILE_FIELDS
        for row in file_rows
    )
    file_projection = [
        {
            "path": row.get("path"),
            "bytes": row.get("size_bytes"),
            "sha256": row.get("sha256"),
        }
        for row in file_rows
        if isinstance(row, dict)
    ]
    validation = (
        payload.get("validation")
        if isinstance(payload.get("validation"), dict)
        else {}
    )
    total_bytes = sum(row["bytes"] for row in _job_files(job))
    expected_budget = {
        "max_files": 2,
        "max_total_bytes": 120000,
        "max_context_tokens": 30000,
        "token_estimator": "utf8_bytes_div4_ceiling_v1",
    }
    expected_transport = {
        "delivery_mode": LANE_MODE,
        "attachment_format": "raw_utf8_per_source_file.v1",
        "one_source_file_per_attachment": True,
        "max_attachment_bytes": 40000,
        "max_physical_line_bytes": 40000,
        "compression_or_aggregate_bundle_allowed": False,
        "receiver_readback_required": True,
        "shared_workspace_writeback_verified": False,
    }
    expected_observed = {
        "file_count": 2,
        "total_bytes": total_bytes,
        "estimated_context_tokens": (total_bytes + 3) // 4,
    }
    expected_check_names = [
        "explicit_base_path",
        "context_files_resolve_inside_base",
        "context_file_budget",
        "context_byte_budget",
        "context_token_budget",
        "raw_utf8_source_attachments",
        "compressed_or_aggregate_attachments_rejected",
        "attachment_reader_limits",
        "receiver_readback_required",
    ]
    checks_well_shaped = (
        isinstance(checks, list)
        and all(
            isinstance(row, dict)
            and set(row) == FROZEN_HANDOFF_CHECK_FIELDS
            and _exact_bool(row.get("ok"), True)
            for row in checks
        )
        and [row.get("name") for row in checks] == expected_check_names
    )
    if (
        set(lane) != HANDOFF_LANE_FIELDS
        or not _exact_bool(lane.get("allow_partial"), False)
        or not _exact_projection(
            lane.get("authority_boundary"), HANDOFF_AUTHORITY_BOUNDARY
        )
        or not artifacts_well_shaped
        or not _exact_projection(required_artifacts, expected_artifacts)
        or set(frozen) != FROZEN_HANDOFF_FIELDS
        or not _exact_int(frozen.get("contract_version"), minimum=3)
        or frozen.get("contract_version") != 3
        or frozen.get("base_path") != "."
        or set(budget) != FROZEN_HANDOFF_BUDGET_FIELDS
        or not _exact_projection(budget, expected_budget)
        or set(transport) != FROZEN_HANDOFF_TRANSPORT_FIELDS
        or not _exact_projection(transport, expected_transport)
        or set(observed) != FROZEN_HANDOFF_OBSERVED_FIELDS
        or not _exact_projection(observed, expected_observed)
        or set(preflight) != FROZEN_HANDOFF_PREFLIGHT_FIELDS
        or preflight.get("status") != "ok"
        or preflight.get("errors") != []
        or not checks_well_shaped
        or not files_well_shaped
        or not _exact_projection(file_projection, _job_files(job))
        or binding.get("frozen_snapshot_id") != frozen.get("frozen_snapshot_id")
        or binding.get("contract_sha256") != frozen.get("contract_sha256")
        or set(validation) != HANDOFF_VALIDATION_FIELDS
        or validation.get("status") != "ok"
        or validation.get("errors") != []
        or validation.get("warnings") != []
    ):
        errors.append("binding_snapshot_handoff_invalid")
    try:
        import helper_lane_manifest as handoffs
    except ImportError:
        errors.append("binding_snapshot_handoff_invalid")
    else:
        try:
            metadata_errors = handoffs.validate_frozen_handoff_metadata(frozen, root)
        except (OSError, TypeError, ValueError):
            metadata_errors = ["handoff_metadata_unavailable"]
        if metadata_errors:
            errors.append("binding_snapshot_handoff_invalid")
    return sorted(set(errors))


def _calibration_binding_errors(
    binding: dict[str, Any],
    payload: dict[str, Any],
    bootstrap_job: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    evidence = (
        payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    )
    worktree = (
        evidence.get("worktree")
        if isinstance(evidence.get("worktree"), dict)
        else {}
    )
    strict = (
        binding.get("strict_projection")
        if isinstance(binding.get("strict_projection"), dict)
        else {}
    )
    strict_runtime = (
        strict.get("runtime") if isinstance(strict.get("runtime"), dict) else {}
    )
    strict_worktree = (
        strict.get("worktree") if isinstance(strict.get("worktree"), dict) else {}
    )
    selected_worktree = {
        key: worktree.get(key) for key in CALIBRATION_WORKTREE_PROJECTION_FIELDS
    }
    expected_job_id = bootstrap_job["job_id"] + "-calibration"
    expected_capabilities = {
        "attachment_context_transport": True,
        "scoped_worktree_implementation": True,
        "shared_main_workspace_access": False,
    }
    if (
        set(binding) != BINDING_CALIBRATION_FIELDS
        or set(payload) != CALIBRATION_PAYLOAD_FIELDS
        or payload.get("schema") != "veritas.persistent_transport_proof.v3"
        or payload.get("status") != "ok"
        or payload.get("agent_id") != AGENT_ID
        or not _exact_projection(
            payload.get("capabilities"), expected_capabilities
        )
        or set(runtime) != CALIBRATION_RUNTIME_FIELDS
        or runtime.get("execution_backend") != BACKEND
        or runtime.get("provider") != "openai"
        or runtime.get("model") != MODEL_PATH
        or runtime.get("thinking") != THINKING
        or set(evidence) != {"attachment", "worktree", "negative_controls"}
        or set(strict) != CALIBRATION_STRICT_FIELDS
        or strict.get("proof_schema") != payload.get("schema")
        or set(strict_runtime) != CALIBRATION_RUNTIME_FIELDS
        or not _exact_projection(strict_runtime, runtime)
        or set(strict_worktree) != CALIBRATION_WORKTREE_PROJECTION_FIELDS
        or not _exact_projection(strict_worktree, selected_worktree)
        or binding.get("job_id") != expected_job_id
        or worktree.get("job_id") != expected_job_id
        or not _exact_projection(
            binding.get("changed_paths"), _job_paths(bootstrap_job)
        )
        or not _exact_projection(
            worktree.get("changed_paths"), _job_paths(bootstrap_job)
        )
    ):
        errors.append("binding_snapshot_calibration_invalid")
    for field in ("baseline_commit", "manifest_sha256", "git_path_inventory_sha256"):
        if not isinstance(selected_worktree.get(field), str) or not selected_worktree.get(
            field
        ):
            errors.append("binding_snapshot_calibration_invalid")
    try:
        observed = _parse_utc(payload.get("observed_at_utc"))
        expires = _parse_utc(payload.get("expires_at_utc"))
        if observed >= expires:
            errors.append("binding_snapshot_calibration_invalid")
    except CohortError:
        errors.append("binding_snapshot_calibration_invalid")
    return sorted(set(errors))


def _binding_snapshot_errors(
    payload: dict[str, Any],
    job: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    errors: list[str] = []
    required = {
        "schema",
        "status",
        "generated_at_utc",
        "expires_at_utc",
        "cohort",
        "handoff",
        "job",
        "calibration",
        "authorization",
        "active_worktree",
        "route",
        "authority_boundary",
    }
    if (
        set(payload) != required
        or payload.get("schema") != "veritas.measurement_cohort_transport_binding.v2"
        or payload.get("status") != "ok"
    ):
        return ["binding_snapshot_schema_invalid"]
    try:
        generated = _parse_utc(payload.get("generated_at_utc"))
        expires = _parse_utc(payload.get("expires_at_utc"))
        if generated >= expires:
            errors.append("binding_snapshot_time_invalid")
    except CohortError:
        errors.append("binding_snapshot_time_invalid")
        generated = None
        expires = None
    cohort = payload.get("cohort") if isinstance(payload.get("cohort"), dict) else {}
    handoff = payload.get("handoff") if isinstance(payload.get("handoff"), dict) else {}
    selected_job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    calibration = (
        payload.get("calibration")
        if isinstance(payload.get("calibration"), dict)
        else {}
    )
    authorization = (
        payload.get("authorization")
        if isinstance(payload.get("authorization"), dict)
        else {}
    )
    active = (
        payload.get("active_worktree")
        if isinstance(payload.get("active_worktree"), dict)
        else {}
    )
    expected_route = {
        "execution_backend": BACKEND,
        "model_path": MODEL_PATH,
        "thinking": THINKING,
        "agent_id": AGENT_ID,
        "persistent_lane_mode": LANE_MODE,
    }
    expected_boundary = {
        "measurement_only": True,
        "protected_dispatch_binding_created": False,
        "usage_receipt_created": False,
        "cohort_credit_granted": False,
        "config_auth_runtime_mutation_allowed": False,
        "finance_canon_portfolio_or_execution_authority": False,
        "external_delivery_allowed": False,
        "owner_approval_inferred": False,
    }
    if not _exact_projection(
        payload.get("route"), expected_route
    ) or not _exact_projection(payload.get("authority_boundary"), expected_boundary):
        errors.append("binding_snapshot_route_or_authority_invalid")
    expected_cohort = {
        "cohort_id": COHORT_ID,
        "manifest_reference": MANIFEST_REFERENCE,
        "manifest_sha256": MANIFEST_SHA256,
    }
    expected_job = {
        "job_number": job["job_number"],
        "job_id": job["job_id"],
        "allowed_write_paths": _job_paths(job),
        "source_file_hashes": _job_files(job),
    }
    if (
        set(cohort) != COHORT_PROJECTION_FIELDS
        or not _exact_projection(cohort, expected_cohort)
        or set(selected_job) != JOB_PROJECTION_FIELDS
        or not _exact_projection(selected_job, expected_job)
        or set(active) != ACTIVE_WORKTREE_FIELDS
        or active.get("job_id") != job["job_id"]
        or not _exact_projection(active.get("allowed_write_paths"), _job_paths(job))
        or not _exact_projection(active.get("source_file_hashes"), _job_files(job))
        or re.fullmatch(r"[0-9a-f]{40}", str(active.get("baseline_commit") or ""))
        is None
        or re.fullmatch(r"[0-9a-f]{64}", str(active.get("manifest_sha256") or ""))
        is None
    ):
        errors.append("binding_snapshot_job_contract_invalid")
    manifest_payload: dict[str, Any] | None = None
    try:
        manifest_payload, _manifest_path, manifest_sha256 = _read_json_reference(
            cohort.get("manifest_reference"), root=root
        )
    except (CohortError, OSError):
        errors.append("binding_snapshot_manifest_unavailable")
    else:
        if manifest_sha256 != MANIFEST_SHA256:
            errors.append("binding_snapshot_manifest_invalid")
    bootstrap_job: dict[str, Any] | None = None
    if manifest_payload is not None:
        jobs = manifest_payload.get("jobs")
        candidates = [
            row
            for row in jobs
            if isinstance(jobs, list)
            and isinstance(row, dict)
            and isinstance(row.get("activation_handoff"), str)
            and row.get("activation_handoff")
        ] if isinstance(jobs, list) else []
        if (
            len(candidates) == 1
            and candidates[0].get("job_number") == 1
        ):
            bootstrap_job = candidates[0]
    if bootstrap_job is None:
        errors.extend(
            (
                "binding_snapshot_handoff_invalid",
                "binding_snapshot_calibration_invalid",
            )
        )
    try:
        handoff_payload, _handoff_path, handoff_sha256 = _read_json_reference(
            handoff.get("reference"), root=root
        )
    except (CohortError, OSError):
        errors.append("binding_snapshot_handoff_unavailable")
    else:
        if handoff.get("sha256") != handoff_sha256:
            errors.append("binding_snapshot_handoff_invalid")
        if bootstrap_job is not None:
            errors.extend(
                _frozen_handoff_errors(
                    handoff, handoff_payload, bootstrap_job, root=root
                )
            )
    try:
        calibration_payload, _calibration_path, calibration_sha256 = (
            _read_json_reference(calibration.get("reference"), root=root)
        )
    except (CohortError, OSError):
        errors.append("binding_snapshot_calibration_unavailable")
    else:
        if calibration.get("sha256") != calibration_sha256:
            errors.append("binding_snapshot_calibration_invalid")
        if bootstrap_job is not None:
            errors.extend(
                _calibration_binding_errors(
                    calibration, calibration_payload, bootstrap_job
                )
            )
        try:
            calibration_expires = _parse_utc(
                calibration_payload.get("expires_at_utc")
            )
            if expires is not None and calibration_expires < expires:
                errors.append("binding_snapshot_calibration_expiry_invalid")
        except CohortError:
            errors.append("binding_snapshot_calibration_expiry_invalid")
    if (
        set(authorization)
        != {
            "schema",
            "approval_id",
            "scope_sha256",
            "expires_at_utc",
            "issued_at_utc",
            "reference",
            "source_event_sha256",
            "source_message_id",
            "source_session_id",
        }
        or authorization.get("schema")
        != "veritas.wave2_cohort_dispatch_authorization.v3"
        or authorization.get("approval_id")
        != "wave2-cohort-10-job-dispatch-20260826"
        or authorization.get("scope_sha256")
        != "ae3d50483e4f9f722b4460d1bfb9d985d59ed352809a76e6c0465a64c3b863d8"
        or not str(authorization.get("reference") or "").startswith(
            "openclaw-owner-approval/"
        )
        or not isinstance(authorization.get("source_event_sha256"), str)
        or re.fullmatch(
            r"[0-9A-Fa-f]{64}", str(authorization.get("source_event_sha256") or "")
        )
        is None
        or not isinstance(authorization.get("source_message_id"), str)
        or not authorization.get("source_message_id", "").strip()
        or not isinstance(authorization.get("source_session_id"), str)
        or not authorization.get("source_session_id", "").strip()
    ):
        errors.append("binding_snapshot_authorization_invalid")
    try:
        authorization_issued = _parse_utc(authorization.get("issued_at_utc"))
        authorization_expires = _parse_utc(authorization.get("expires_at_utc"))
        if (
            generated is None
            or expires is None
            or authorization_issued > generated
            or authorization_expires < expires
        ):
            errors.append("binding_snapshot_authorization_time_invalid")
    except CohortError:
        errors.append("binding_snapshot_authorization_time_invalid")
    errors.extend(_authorization_provenance_errors(authorization))
    return sorted(set(errors))


def _admission_snapshot_errors(
    admission: dict[str, Any],
    job: dict[str, Any],
    lane: dict[str, Any],
    prior_lanes: list[dict[str, Any]],
    *,
    root: Path,
    controller_root: Path,
    allow_legacy_first_incident: bool = False,
) -> list[str]:
    errors: list[str] = []
    allowed_inventories = {ADMISSION_FIELDS}
    if allow_legacy_first_incident:
        allowed_inventories.add(ADMISSION_FIELDS - {"attempt_history"})
    if frozenset(admission) not in allowed_inventories:
        errors.append("admission_snapshot_field_inventory_invalid")
    expected_route = {
        **EXPECTED_ROUTE,
        "fallback_allowed": False,
        "cwd_override_allowed": False,
    }
    expected_sequence = {
        "previous_credited_count": int(job["job_number"]) - 1,
        "expected_job_number": int(job["job_number"]),
        "contiguous": True,
        "other_active_cohort_job": False,
    }
    expected_authority = {
        **AUTHORITY_BOUNDARY,
        "measurement_admission_ready": True,
        "cohort_credit_granted": False,
    }
    try:
        expected_attempt = _attempt_projection(lane)
        expected_history = _attempt_history_projection(
            prior_lanes,
            job=job,
            root=root,
            controller_root=controller_root,
        )
    except CohortError as exc:
        return ["admission_snapshot_projection_invalid:" + str(exc)]
    observed_history = admission.get("attempt_history")
    if not prior_lanes and observed_history is None:
        observed_history = []
    admission_lane = (
        admission.get("lane") if isinstance(admission.get("lane"), dict) else {}
    )
    admission_binding = (
        admission.get("binding")
        if isinstance(admission.get("binding"), dict)
        else {}
    )
    admission_cohort = (
        admission.get("cohort")
        if isinstance(admission.get("cohort"), dict)
        else {}
    )
    admission_job = (
        admission.get("job") if isinstance(admission.get("job"), dict) else {}
    )
    expected_cohort = {
        "cohort_id": COHORT_ID,
        "manifest_reference": MANIFEST_REFERENCE,
        "manifest_sha256": MANIFEST_SHA256,
    }
    expected_job = {
        "job_number": job["job_number"],
        "job_id": job["job_id"],
        "source_file_hashes": _job_files(job),
        "focused_test": job.get("focused_test"),
        "compile_test": job.get("compile_test"),
    }
    if (
        admission.get("schema") != ADMISSION_SCHEMA
        or admission.get("status") != "ok"
        or set(admission_cohort) != COHORT_PROJECTION_FIELDS
        or not _exact_projection(admission_cohort, expected_cohort)
        or set(admission_job) != ADMISSION_JOB_FIELDS
        or not _exact_projection(admission_job, expected_job)
        or not _exact_projection(admission.get("sequence"), expected_sequence)
        or not _exact_projection(admission.get("route"), expected_route)
        or set(admission_lane) != ADMISSION_LANE_FIELDS
        or set(admission_binding) != ADMISSION_BINDING_FIELDS
        or admission_lane.get("lane_id") != lane.get("lane_id")
        or admission_lane.get("workflow_id") != lane.get("workflow_id")
        or admission_lane.get("workstream_id") != lane.get("workstream_id")
        or admission_lane.get("created_at_utc") != lane.get("created_at_utc")
        or not _exact_projection(
            admission_lane.get("allowed_write_paths"), _job_paths(job)
        )
        or not _exact_projection(admission.get("attempt"), expected_attempt)
        or not _exact_projection(observed_history, expected_history)
        or not _exact_projection(
            admission.get("authority_boundary"), expected_authority
        )
        or admission.get("errors") != []
    ):
        errors.append("admission_snapshot_contract_invalid")
    try:
        generated = _parse_utc(admission.get("generated_at_utc"))
        expires = _parse_utc(admission.get("expires_at_utc"))
        lane_created = _parse_utc(admission_lane.get("created_at_utc"))
        authoritative_created = _parse_utc(lane.get("created_at_utc"))
        if (
            generated >= expires
            or lane_created != authoritative_created
            or lane_created > generated
        ):
            errors.append("admission_snapshot_time_invalid")
    except CohortError:
        errors.append("admission_snapshot_time_invalid")
    binding = admission_binding
    try:
        binding_payload, binding_path, binding_sha256 = _read_json_reference(
            binding.get("reference"), root=root
        )
    except (CohortError, OSError):
        errors.append("admission_snapshot_binding_unavailable")
    else:
        if binding_sha256 != binding.get("sha256"):
            errors.append("admission_snapshot_binding_hash_invalid")
        calibration = (
            binding_payload.get("calibration")
            if isinstance(binding_payload.get("calibration"), dict)
            else {}
        )
        expected_binding = {
            "reference": _artifact_reference(binding_path, root=root),
            "sha256": binding_sha256,
            "schema": binding_payload.get("schema"),
            "calibration_proof_reference": calibration.get("reference"),
            "calibration_job_id": calibration.get("job_id"),
            "calibration_allowed_write_paths": calibration.get("changed_paths"),
        }
        if binding != expected_binding:
            errors.append("admission_snapshot_binding_projection_invalid")
        errors.extend(_binding_snapshot_errors(binding_payload, job, root=root))
        errors.extend(_admission_binding_time_errors(admission, binding_payload))
    return sorted(set(errors))


def _prior_admission_evidence(
    lane: dict[str, Any],
    job: dict[str, Any],
    *,
    prior_lanes: list[dict[str, Any]],
    attempt_number: int,
    root: Path,
    controller_root: Path,
) -> tuple[str, str | None, list[str]]:
    admission_path = _admission_path(
        controller_root, int(job["job_number"]), attempt_number
    )
    reference = _artifact_reference(admission_path, root=root)
    try:
        admission, digest = _read_json_path_with_sha256(admission_path)
    except (CohortError, OSError):
        return reference, None, ["prior_admission_unavailable"]
    errors = _admission_snapshot_errors(
        admission,
        job,
        lane,
        prior_lanes,
        root=root,
        controller_root=controller_root,
        allow_legacy_first_incident=True,
    )
    return reference, digest, sorted(set(errors))


def _prior_incident_evidence(
    lane: dict[str, Any],
    job: dict[str, Any],
    *,
    attempt_number: int,
    root: Path,
    controller_root: Path,
) -> tuple[str, str | None, list[str]]:
    expected_path = (
        _job_dir(controller_root, int(job["job_number"]))
        / f"attempt-{attempt_number:02d}-incident.json"
    )
    reference = _artifact_reference(expected_path, root=root)
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    errors: list[str] = []
    if lane.get("proof_artifacts") != [reference]:
        errors.append("incident_evidence_inventory_invalid")
    if runtime.get("main_acceptance_evidence") != reference:
        errors.append("incident_evidence_runtime_binding_invalid")
    try:
        payload, digest = _read_json_path_with_sha256(expected_path)
    except (CohortError, OSError):
        return reference, None, errors + ["incident_evidence_unavailable"]
    attempt = payload.get("attempt") if isinstance(payload.get("attempt"), dict) else {}
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else {}
    disposition = (
        payload.get("measurement_disposition")
        if isinstance(payload.get("measurement_disposition"), dict)
        else {}
    )
    authority = (
        payload.get("authority_boundary")
        if isinstance(payload.get("authority_boundary"), dict)
        else {}
    )
    try:
        expected_task_name = _attempt_projection(lane)["dispatch_task_name"]
    except CohortError:
        expected_task_name = None
        errors.append("incident_evidence_attempt_binding_invalid")
    expected_route = {
        "expected_execution_backend": BACKEND,
        "expected_agent_id": AGENT_ID,
        "expected_model": MODEL_PATH,
        "expected_thinking": THINKING,
        "launch_status": "accepted",
        "resolved_provider": "openai",
        "resolved_model": MODEL_PATH,
        "model_applied": True,
        "fallback_observed": False,
    }
    expected_authority = {
        "wave3_authorized": False,
        "finance_canon_portfolio_or_execution_authority": False,
        "config_auth_runtime_mutation_authorized": False,
        "external_action_authorized": False,
    }
    if set(payload) != {
        "schema",
        "generated_at_utc",
        "cohort_id",
        "job_id",
        "job_number",
        "attempt",
        "route",
        "incident",
        "measurement_disposition",
        "next_safe_action",
        "authority_boundary",
    }:
        errors.append("incident_evidence_shape_invalid")
    if (
        set(attempt)
        != {
            "attempt_id",
            "attempt_number",
            "retry_count",
            "first_pass",
            "task_name",
            "run_id",
            "session_key",
            "session_id",
        }
        or not _exact_projection(route, expected_route)
        or set(incident)
        != {
            "code",
            "status",
            "stage",
            "summary",
            "provider_connection_failed",
            "subprocess_started",
            "source_write_performed",
            "out_of_scope_write_performed",
            "required_tests_run",
            "required_compile_run",
            "retry_performed",
        }
        or set(disposition)
        != {
            "main_accepted",
            "cohort_credit_granted",
            "first_pass_success_credit",
            "usage_credit_pending_exact_import",
            "wave3_effect",
        }
        or not _exact_projection(authority, expected_authority)
    ):
        errors.append("incident_evidence_nested_shape_invalid")
    if (
        payload.get("schema") != "veritas.wave2_measurement_job_incident.v1"
        or payload.get("cohort_id") != COHORT_ID
        or payload.get("job_id") != job["job_id"]
        or not _exact_int(payload.get("job_number"), minimum=1)
        or payload.get("job_number") != job["job_number"]
        or not _exact_int(attempt.get("attempt_number"), minimum=1)
        or attempt.get("attempt_number") != attempt_number
        or attempt.get("attempt_id") != runtime.get("attempt_id")
        or not _exact_int(attempt.get("retry_count"))
        or attempt.get("retry_count") != attempt_number - 1
        or attempt.get("first_pass") is not (attempt_number == 1)
        or attempt.get("task_name") != expected_task_name
        or incident.get("code") != "packaging_path_error"
        or incident.get("status") != "terminal_attempt_failure"
        or incident.get("stage") != "scoped_worktree_preflight"
        or not isinstance(incident.get("summary"), str)
        or not incident.get("summary")
        or incident.get("provider_connection_failed") is not False
        or incident.get("subprocess_started") is not False
        or incident.get("source_write_performed") is not False
        or incident.get("out_of_scope_write_performed") is not False
        or incident.get("required_tests_run") is not False
        or incident.get("required_compile_run") is not False
        or incident.get("retry_performed") is not False
        or disposition.get("main_accepted") is not False
        or disposition.get("cohort_credit_granted") is not False
        or disposition.get("first_pass_success_credit") is not False
        or disposition.get("usage_credit_pending_exact_import") is not True
        or disposition.get("wave3_effect") != "none"
        or not isinstance(payload.get("next_safe_action"), str)
        or not payload.get("next_safe_action")
    ):
        errors.append("incident_evidence_contract_invalid")
    session_key = attempt.get("session_key")
    session_id = attempt.get("session_id")
    run_id = attempt.get("run_id")
    dispatch = (
        runtime.get("dispatch_binding")
        if isinstance(runtime.get("dispatch_binding"), dict)
        else {}
    )
    if (
        not isinstance(session_key, str)
        or _sha256_bytes(session_key.encode("utf-8"))[:24]
        != runtime.get("session_key_hash")
        or not isinstance(session_id, str)
        or _sha256_bytes(session_id.encode("utf-8"))[:24]
        != runtime.get("session_id_hash")
        or not isinstance(run_id, str)
        or _sha256_bytes(run_id.encode("utf-8"))
        != dispatch.get("registry_run_id_hash")
    ):
        errors.append("incident_evidence_runtime_identity_invalid")
    retained_identity = RETAINED_INCIDENT_IDENTITIES.get(
        (str(job.get("job_id") or ""), attempt_number)
    )
    observed_identity = {
        "attempt_id": attempt.get("attempt_id"),
        "task_name": attempt.get("task_name"),
        "run_id_sha256": (
            _sha256_bytes(run_id.encode("utf-8")) if isinstance(run_id, str) else None
        ),
        "session_key_sha256": (
            _sha256_bytes(session_key.encode("utf-8"))
            if isinstance(session_key, str)
            else None
        ),
        "session_id_sha256": (
            _sha256_bytes(session_id.encode("utf-8"))
            if isinstance(session_id, str)
            else None
        ),
    }
    if retained_identity is None or not _exact_projection(
        observed_identity, retained_identity
    ):
        errors.append("incident_evidence_retained_identity_invalid")
    try:
        generated = _parse_utc(payload.get("generated_at_utc"))
        started = _parse_utc(lane.get("started_at_utc"))
        ended = _parse_utc(lane.get("ended_at_utc"))
        recorded = _parse_utc(runtime.get("outcome_recorded_at_utc"))
        if not (started <= generated <= recorded == ended):
            errors.append("incident_evidence_time_binding_invalid")
    except CohortError:
        errors.append("incident_evidence_time_binding_invalid")
    return reference, digest, sorted(set(errors))


def _prior_attempt_history_errors(
    prior_lanes: list[dict[str, Any]],
    job: dict[str, Any],
    *,
    receipt_sidecar: str,
    root: Path,
    controller_root: Path,
) -> list[str]:
    """Validate retained zero-credit incident attempts before a current retry."""
    errors: list[str] = []
    expected_runtime = {
        "agent_id": AGENT_ID,
        "parent_job_id": job["job_id"],
        "phase": "implementation",
        "model_path": MODEL_PATH,
        "thinking": THINKING,
        "expected_model_path": MODEL_PATH,
        "expected_thinking": THINKING,
        "expected_execution_backend": BACKEND,
    }
    expected_writes = sorted(_job_paths(job))
    expected_writes_with_receipt = sorted([*expected_writes, receipt_sidecar])
    for expected_attempt, lane in enumerate(prior_lanes, start=1):
        runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
        prefix = f"prior_attempt_{expected_attempt}:"
        if lane.get("status") != "blocked":
            errors.append(prefix + "not_blocked")
        if lane.get("owner") != AGENT_ID:
            errors.append(prefix + "owner_mismatch")
        observed_writes = sorted(lane.get("allowed_writes") or [])
        if observed_writes not in (expected_writes, expected_writes_with_receipt):
            errors.append(prefix + "write_scope_mismatch")
        for key, value in expected_runtime.items():
            if runtime.get(key) != value:
                errors.append(prefix + f"runtime_{key}_mismatch")
        if runtime.get("actual_execution_backend") != BACKEND:
            errors.append(prefix + "actual_backend_mismatch")
        if runtime.get("agent_role") != "implementation_builder":
            errors.append(prefix + "agent_role_mismatch")
        if (
            not _exact_int(runtime.get("attempt_number"), minimum=1)
            or runtime.get("attempt_number") != expected_attempt
            or not _exact_int(runtime.get("retry_count"))
            or runtime.get("retry_count") != expected_attempt - 1
            or runtime.get("is_first_attempt") is not (expected_attempt == 1)
        ):
            errors.append(prefix + "attempt_sequence_mismatch")
        incident_code = runtime.get("incident_code")
        if incident_code != "packaging_path_error":
            errors.append(prefix + "incident_code_not_retryable")
        incident_count = runtime.get("incident_count")
        if not _exact_int(incident_count) or incident_count != 1:
            errors.append(prefix + "incident_count_invalid")
        if runtime.get("outcome_event_kind") != "incident":
            errors.append(prefix + "terminal_event_invalid")
        event_sequence = runtime.get("outcome_event_sequence")
        if not _exact_int(event_sequence, minimum=1) or event_sequence != 1:
            errors.append(prefix + "terminal_event_sequence_invalid")
        if not isinstance(runtime.get("outcome_recorded_at_utc"), str):
            errors.append(prefix + "terminal_recorded_at_missing")
        events = lane.get("outcome_events")
        expected_event = {
            "event_kind": "incident",
            "event_sequence": 1,
            "recorded_at_utc": runtime.get("outcome_recorded_at_utc"),
        }
        if (
            not isinstance(events, list)
            or len(events) != 1
            or not isinstance(events[0], dict)
            or set(events[0])
            != {"event_kind", "event_sequence", "recorded_at_utc"}
        ):
            errors.append(prefix + "outcome_events_inventory_invalid")
        elif (
            events != [expected_event]
            or not _exact_int(events[0].get("event_sequence"), minimum=1)
        ):
            errors.append(prefix + "outcome_events_invalid")
        if runtime.get("closure_durability") != "verified":
            errors.append(prefix + "closure_not_verified")
        if runtime.get("main_acceptance_status") != "rejected":
            errors.append(prefix + "main_acceptance_not_rejected")
        if runtime.get("validator_result") != "not_run":
            errors.append(prefix + "validator_disposition_invalid")
        if runtime.get("outcome_status") != "blocked_before_source_preflight":
            errors.append(prefix + "outcome_disposition_invalid")
        _reference, _digest, evidence_errors = _prior_incident_evidence(
            lane,
            job,
            attempt_number=expected_attempt,
            root=root,
            controller_root=controller_root,
        )
        errors.extend(prefix + item for item in evidence_errors)
        _reference, _digest, admission_errors = _prior_admission_evidence(
            lane,
            job,
            prior_lanes=prior_lanes[: expected_attempt - 1],
            attempt_number=expected_attempt,
            root=root,
            controller_root=controller_root,
        )
        errors.extend(prefix + item for item in admission_errors)
        try:
            projection = _attempt_projection(lane)
        except CohortError as exc:
            errors.append(prefix + str(exc))
        else:
            if (
                projection["attempt_number"] != expected_attempt
                or projection["retry_count"] != expected_attempt - 1
            ):
                errors.append(prefix + "attempt_projection_mismatch")
    return sorted(set(errors))


def _attempt_history_projection(
    prior_lanes: list[dict[str, Any]],
    *,
    job: dict[str, Any],
    root: Path,
    controller_root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for expected_attempt, lane in enumerate(prior_lanes, start=1):
        runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
        reference, digest, errors = _prior_incident_evidence(
            lane,
            job,
            attempt_number=expected_attempt,
            root=root,
            controller_root=controller_root,
        )
        if errors or digest is None:
            raise CohortError("prior_incident_evidence_invalid")
        admission_reference, admission_digest, admission_errors = (
            _prior_admission_evidence(
                lane,
                job,
                prior_lanes=prior_lanes[: expected_attempt - 1],
                attempt_number=expected_attempt,
                root=root,
                controller_root=controller_root,
            )
        )
        if admission_errors or admission_digest is None:
            raise CohortError("prior_admission_evidence_invalid")
        rows.append(
            {
                "lane_id": lane.get("lane_id"),
                "attempt_number": runtime.get("attempt_number"),
                "retry_count": runtime.get("retry_count"),
                "status": lane.get("status"),
                "incident_code": runtime.get("incident_code"),
                "incident_count": runtime.get("incident_count"),
                "main_acceptance_status": runtime.get("main_acceptance_status"),
                "outcome_recorded_at_utc": runtime.get("outcome_recorded_at_utc"),
                "incident_evidence_reference": reference,
                "incident_evidence_sha256": digest,
                "admission_reference": admission_reference,
                "admission_sha256": admission_digest,
                "cohort_credit_granted": False,
            }
        )
    return rows


def _active_collision_errors(
    register: dict[str, Any], lane: dict[str, Any], job: dict[str, Any]
) -> list[str]:
    target = set(_job_paths(job))
    errors: list[str] = []
    for raw in register.get("lanes", []):
        other = raw if isinstance(raw, dict) else {}
        if other.get("lane_id") == lane.get("lane_id"):
            continue
        if other.get("status") not in ACTIVE_LANE_STATUSES:
            continue
        overlap = target.intersection(other.get("allowed_writes") or [])
        if overlap:
            errors.append("active_write_collision:" + ",".join(sorted(overlap)))
    return errors


def _restart_attempt_errors(
    job: dict[str, Any], attempt_lanes: list[dict[str, Any]]
) -> list[str]:
    number = int(job.get("job_number") or 0)
    expected_attempt = RESTART_EXPECTED_ATTEMPTS.get(number)
    if expected_attempt is None:
        return ["job_not_in_nine_job_restart"]
    errors: list[str] = []
    if len(attempt_lanes) != expected_attempt:
        errors.append("restart_attempt_number_mismatch")
    if number == 2:
        if len(attempt_lanes) < 2:
            errors.append("job2_attempt1_history_missing")
        elif (
            job.get("job_id"), 1
        ) not in RETAINED_INCIDENT_IDENTITIES:
            errors.append("job2_attempt1_identity_not_retained")
    elif len(attempt_lanes) != 1:
        errors.append("same_pass_repair_or_retry_forbidden")
    return sorted(set(errors))


def _restart_topology_errors(
    register: dict[str, Any],
    lane: dict[str, Any],
    manifest: dict[str, Any],
    restart_packet: dict[str, Any],
) -> list[str]:
    """Forbid cohort lane multiplication after the frozen restart epoch."""
    restart_job_ids = {
        row["job_id"]
        for row in manifest["jobs"]
        if int(row["job_number"]) in RESTART_EXPECTED_ATTEMPTS
    }
    restart_at = _parse_utc(restart_packet.get("generated_at_utc"))
    errors: list[str] = []
    active_job_lane_ids: list[str] = []
    for raw in register.get("lanes", []):
        other = raw if isinstance(raw, dict) else {}
        runtime = (
            other.get("runtime") if isinstance(other.get("runtime"), dict) else {}
        )
        parent = runtime.get("parent_job_id")
        if parent not in restart_job_ids and parent != COHORT_ID:
            continue
        try:
            created = _parse_utc(other.get("created_at_utc"))
        except CohortError:
            errors.append("restart_lane_created_at_invalid")
            continue
        if created < restart_at:
            continue
        if runtime.get("phase") != "implementation":
            errors.append("nested_repair_or_qa_lane_forbidden")
        if other.get("status") in ACTIVE_LANE_STATUSES:
            active_job_lane_ids.append(str(other.get("lane_id") or ""))
    if sorted(active_job_lane_ids) != [str(lane.get("lane_id") or "")]:
        errors.append("only_one_active_cohort_job_required")
    return sorted(set(errors))


def _checkpoint_errors(
    lane: dict[str, Any],
    job: dict[str, Any],
    *,
    controller_root: Path,
    attempt_number: int,
) -> list[str]:
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    try:
        created = _parse_utc(lane.get("created_at_utc"))
        terminal = _parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    except CohortError:
        return ["checkpoint_lane_time_invalid"]
    elapsed = int((terminal - created).total_seconds())
    if elapsed <= JOB_CHECKPOINT_SECONDS:
        return []
    path = _checkpoint_path(controller_root, int(job["job_number"]), attempt_number)
    try:
        checkpoint = _read_json_path(path)
        generated = _parse_utc(checkpoint.get("generated_at_utc"))
    except (CohortError, OSError):
        return ["five_minute_checkpoint_missing_or_invalid"]
    expected = {
        "schema": CHECKPOINT_SCHEMA,
        "status": "ok",
        "generated_at_utc": checkpoint.get("generated_at_utc"),
        "cohort_id": COHORT_ID,
        "job_id": job["job_id"],
        "lane_id": lane.get("lane_id"),
        "attempt_number": attempt_number,
        "max_elapsed_seconds": JOB_MAX_ELAPSED_SECONDS,
        "max_tool_calls": JOB_MAX_TOOL_CALLS,
        "checkpoint_seconds": JOB_CHECKPOINT_SECONDS,
        "observed_tool_calls": checkpoint.get("observed_tool_calls"),
        "stop_required": False,
        "authority_boundary": {
            "checkpoint_only": True,
            "cohort_credit_granted": False,
            "provider_dispatch_authorized": False,
            "owner_approval_inferred": False,
        },
    }
    errors: list[str] = []
    if checkpoint != expected:
        errors.append("five_minute_checkpoint_contract_invalid")
    if generated < created or (generated - created).total_seconds() > JOB_CHECKPOINT_SECONDS:
        errors.append("five_minute_checkpoint_late")
    observed = checkpoint.get("observed_tool_calls")
    if observed is not None and (
        not _exact_int(observed) or observed > JOB_MAX_TOOL_CALLS
    ):
        errors.append("five_minute_checkpoint_tool_budget_invalid")
    if runtime.get("max_elapsed_seconds") != JOB_MAX_ELAPSED_SECONDS:
        errors.append("five_minute_checkpoint_elapsed_budget_drift")
    return sorted(set(errors))


def _attempt_projection(lane: dict[str, Any]) -> dict[str, Any]:
    try:
        import concurrent_lane_manager as lanes
        import isolated_agent_usage_metadata as usage
    except ImportError as exc:
        raise CohortError("attempt_helpers_unavailable") from exc
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    correlation = lanes.expected_attempt_correlation(lane, runtime)
    if not isinstance(correlation, dict) or re.fullmatch(
        r"[0-9a-f]{64}", str(correlation.get("key_hash") or "")
    ) is None:
        raise CohortError("attempt_correlation_invalid")
    observed = runtime.get("attempt_correlation")
    if not isinstance(observed, dict) or observed.get("key_hash") != correlation["key_hash"]:
        raise CohortError("attempt_correlation_drift")
    attempt_number = runtime.get("attempt_number")
    retry_count = runtime.get("retry_count")
    if (
        not _exact_int(attempt_number, minimum=1)
        or not _exact_int(retry_count)
        or retry_count != attempt_number - 1
        or runtime.get("is_first_attempt") is not (attempt_number == 1)
    ):
        raise CohortError("attempt_sequence_invalid")
    return {
        "attempt_number": attempt_number,
        "retry_count": retry_count,
        "incident_allowed": False,
        "attempt_correlation_hash": correlation["key_hash"],
        "dispatch_task_name": usage.task_name_for_attempt(
            attempt_correlation_hash=correlation["key_hash"]
        ),
        "binding_token_hash": usage.dispatch_binding_token_hash_for_attempt(
            attempt_correlation_hash=correlation["key_hash"]
        ),
    }


def derive_status(
    *,
    root: Path = ROOT,
    controller_root: Path = CONTROLLER_ROOT,
    current_verifier: Callable[[dict[str, Any], dict[str, Any]], list[str]] | None = None,
    credit_artifact_verifier: Callable[[dict[str, Any], dict[str, Any]], list[str]] | None = None,
) -> dict[str, Any]:
    try:
        manifest = load_frozen_manifest(root=root)
        credits, errors = load_credit_chain(
            manifest,
            root=root,
            controller_root=controller_root,
            current_verifier=current_verifier,
            artifact_verifier=credit_artifact_verifier,
        )
        if errors:
            raise CohortError(";".join(errors))
        count = len(credits)
        next_job = _job_by_number(manifest, count + 1) if count < 10 else None
        if next_job is not None:
            preimage_errors = _preimage_errors(next_job, root=root)
            if preimage_errors:
                raise CohortError(";".join(preimage_errors))
        ready = count == 10
        return {
            "schema": STATUS_SCHEMA,
            "status": "ok",
            "generated_at_utc": _utc_now(),
            "cohort_id": COHORT_ID,
            "manifest_reference": MANIFEST_REFERENCE,
            "manifest_sha256": MANIFEST_SHA256,
            "qualifying_jobs": count,
            "required_jobs": 10,
            "credited_job_ids": [row["job_id"] for row in credits],
            "next_job": (
                {
                    "job_number": next_job["job_number"],
                    "job_id": next_job["job_id"],
                    "allowed_write_paths": _job_paths(next_job),
                }
                if next_job is not None
                else None
            ),
            "wave3_review": {
                "status": "ready_for_owner_review" if ready else "cohort_incomplete",
                "qualifying_jobs": count,
                "required_jobs": 10,
                "wave3_review_gate_met": ready,
                "wave3_authorized": False,
                "authorization_granted": False,
                "automatic_route_promotion_allowed": False,
                "route_policy_change_authorized": False,
                "next_action": (
                    "explicit_owner_review_required" if ready else "complete_next_frozen_job"
                ),
            },
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
            "errors": [],
        }
    except (CohortError, OSError, subprocess.SubprocessError) as exc:
        return {
            "schema": STATUS_SCHEMA,
            "status": "error",
            "generated_at_utc": _utc_now(),
            "cohort_id": COHORT_ID,
            "qualifying_jobs": 0,
            "required_jobs": 10,
            "wave3_review": {
                "status": "blocked",
                "wave3_review_gate_met": False,
                "wave3_authorized": False,
                "automatic_route_promotion_allowed": False,
            },
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
            "errors": [str(exc)],
        }


def build_admission(
    *,
    binding_reference: str,
    root: Path = ROOT,
    controller_root: Path = CONTROLLER_ROOT,
    register_path: Path = REGISTER_PATH,
    binding_inspector: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = load_frozen_manifest(root=root)
    credits, credit_errors = load_credit_chain(
        manifest, root=root, controller_root=controller_root
    )
    if credit_errors:
        raise CohortError(";".join(credit_errors))
    if len(credits) >= 10:
        raise CohortError("cohort_already_complete")
    job = _job_by_number(manifest, len(credits) + 1)
    restart_packet: dict[str, Any] | None = None
    if int(job["job_number"]) >= 2:
        restart_packet, _restart_packet_sha256 = load_frozen_restart_packet(root=root)
    elif (root / RESTART_PACKET_REFERENCE).is_file():
        raise CohortError("job1_already_credited_no_further_admission")
    preimage_errors = _preimage_errors(job, root=root)
    if preimage_errors:
        raise CohortError(";".join(preimage_errors))
    binding_payload, binding_path, binding_sha256 = _read_json_reference(
        binding_reference, root=root
    )
    if binding_inspector is None:
        try:
            import measurement_cohort_transport_binding as bindings
        except ImportError as exc:
            raise CohortError("binding_inspector_unavailable") from exc
        binding_check = bindings.inspect_binding_reference(binding_reference, root=root)
    else:
        binding_check = binding_inspector(binding_reference)
    binding_snapshot_errors = _binding_snapshot_errors(
        binding_payload, job, root=root
    )
    if binding_snapshot_errors:
        raise CohortError(";".join(binding_snapshot_errors))
    if binding_check.get("status") != "ok":
        raise CohortError(
            "binding_invalid:" + str(binding_check.get("code") or "unknown")
        )
    if binding_check.get("expires_at_utc") != binding_payload.get("expires_at_utc"):
        raise CohortError("binding_expiry_projection_mismatch")
    binding_calibration = (
        binding_payload.get("calibration")
        if isinstance(binding_payload.get("calibration"), dict)
        else {}
    )
    if (
        binding_check.get("cohort_id") != COHORT_ID
        or not _exact_int(binding_check.get("job_number"), minimum=1)
        or binding_check.get("job_number") != job["job_number"]
        or binding_check.get("job_id") != job["job_id"]
        or not _exact_projection(
            binding_check.get("allowed_write_paths"), _job_paths(job)
        )
        or not _exact_projection(binding_check.get("route"), EXPECTED_ROUTE)
        or binding_check.get("calibration_proof_reference")
        != binding_calibration.get("reference")
        or binding_check.get("calibration_job_id")
        != binding_calibration.get("job_id")
        or not _exact_projection(
            binding_check.get("calibration_allowed_write_paths"),
            binding_calibration.get("changed_paths"),
        )
    ):
        raise CohortError("binding_projection_mismatch")
    register = _load_register(register_path)
    attempt_lanes = _find_job_lanes(register, job)
    lane = attempt_lanes[-1]
    attempt_number = len(attempt_lanes)
    receipt_sidecar = _receipt_sidecar_reference(register_path, root=root)
    lane_errors = _prior_attempt_history_errors(
        attempt_lanes[:-1],
        job,
        receipt_sidecar=receipt_sidecar,
        root=root,
        controller_root=controller_root,
    )
    lane_errors.extend(
        _lane_contract_errors(
            lane,
            job,
            terminal=False,
            attempt_number=attempt_number,
        )
    )
    lane_errors.extend(_active_collision_errors(register, lane, job))
    if restart_packet is not None:
        lane_errors.extend(_restart_attempt_errors(job, attempt_lanes))
        lane_errors.extend(
            _restart_topology_errors(register, lane, manifest, restart_packet)
        )
    if credits:
        previous_generated = _parse_utc(credits[-1].get("generated_at_utc"))
        lane_created = _parse_utc(lane.get("created_at_utc"))
        if lane_created <= previous_generated:
            lane_errors.append("lane_created_before_previous_credit")
    if lane_errors:
        raise CohortError(";".join(sorted(set(lane_errors))))
    attempt = _attempt_projection(lane)
    generated_at_utc = _utc_now()
    admission = {
        "schema": ADMISSION_SCHEMA,
        "status": "ok",
        "generated_at_utc": generated_at_utc,
        "expires_at_utc": binding_payload.get("expires_at_utc"),
        "cohort": {
            "cohort_id": COHORT_ID,
            "manifest_reference": MANIFEST_REFERENCE,
            "manifest_sha256": MANIFEST_SHA256,
        },
        "job": {
            "job_number": job["job_number"],
            "job_id": job["job_id"],
            "source_file_hashes": _job_files(job),
            "focused_test": job.get("focused_test"),
            "compile_test": job.get("compile_test"),
        },
        "sequence": {
            "previous_credited_count": len(credits),
            "expected_job_number": len(credits) + 1,
            "contiguous": True,
            "other_active_cohort_job": False,
        },
        "binding": {
            "reference": _artifact_reference(binding_path, root=root),
            "sha256": binding_sha256,
            "schema": binding_payload.get("schema"),
            "calibration_proof_reference": binding_calibration.get("reference"),
            "calibration_job_id": binding_calibration.get("job_id"),
            "calibration_allowed_write_paths": binding_calibration.get(
                "changed_paths"
            ),
        },
        "lane": {
            "lane_id": lane.get("lane_id"),
            "workflow_id": lane.get("workflow_id"),
            "workstream_id": lane.get("workstream_id"),
            "created_at_utc": lane.get("created_at_utc"),
            "allowed_write_paths": _job_paths(job),
        },
        "route": {
            **EXPECTED_ROUTE,
            "fallback_allowed": False,
            "cwd_override_allowed": False,
        },
        "attempt": attempt,
        "attempt_history": _attempt_history_projection(
            attempt_lanes[:-1],
            job=job,
            root=root,
            controller_root=controller_root,
        ),
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "measurement_admission_ready": True,
            "cohort_credit_granted": False,
        },
        "errors": [],
    }
    time_errors = _admission_binding_time_errors(
        admission,
        binding_payload,
        unexpired_at=_parse_utc(generated_at_utc),
    )
    if time_errors:
        raise CohortError(";".join(time_errors))
    return admission


def build_checkpoint(
    *,
    job_id: str,
    root: Path = ROOT,
    controller_root: Path = CONTROLLER_ROOT,
    register_path: Path = REGISTER_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create the one bounded five-minute checkpoint for an active restart job."""
    manifest = load_frozen_manifest(root=root)
    restart_packet, _restart_packet_sha256 = load_frozen_restart_packet(root=root)
    credits, credit_errors = load_credit_chain(
        manifest, root=root, controller_root=controller_root
    )
    if credit_errors:
        raise CohortError(";".join(credit_errors))
    job = _job_by_id(manifest, job_id)
    if job["job_number"] != len(credits) + 1 or int(job["job_number"]) < 2:
        raise CohortError("checkpoint_job_not_next_restart_job")
    register = _load_register(register_path)
    attempt_lanes = _find_job_lanes(register, job)
    lane = attempt_lanes[-1]
    attempt_number = len(attempt_lanes)
    errors = _restart_attempt_errors(job, attempt_lanes)
    errors.extend(
        _lane_contract_errors(
            lane,
            job,
            terminal=False,
            attempt_number=attempt_number,
        )
    )
    errors.extend(_restart_topology_errors(register, lane, manifest, restart_packet))
    checkpoint_at = now or datetime.now(timezone.utc)
    try:
        created = _parse_utc(lane.get("created_at_utc"))
    except CohortError:
        errors.append("checkpoint_lane_time_invalid")
    else:
        elapsed = (checkpoint_at - created).total_seconds()
        if elapsed < 0 or elapsed > JOB_CHECKPOINT_SECONDS:
            errors.append("five_minute_checkpoint_outside_window")
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    observed_tools = runtime.get("observed_tool_calls")
    if observed_tools is not None and (
        not _exact_int(observed_tools) or observed_tools > JOB_MAX_TOOL_CALLS
    ):
        errors.append("five_minute_checkpoint_tool_budget_invalid")
    if errors:
        raise CohortError(";".join(sorted(set(errors))))
    return {
        "schema": CHECKPOINT_SCHEMA,
        "status": "ok",
        "generated_at_utc": checkpoint_at.isoformat().replace("+00:00", "Z"),
        "cohort_id": COHORT_ID,
        "job_id": job_id,
        "lane_id": lane.get("lane_id"),
        "attempt_number": attempt_number,
        "max_elapsed_seconds": JOB_MAX_ELAPSED_SECONDS,
        "max_tool_calls": JOB_MAX_TOOL_CALLS,
        "checkpoint_seconds": JOB_CHECKPOINT_SECONDS,
        "observed_tool_calls": observed_tools,
        "stop_required": False,
        "authority_boundary": {
            "checkpoint_only": True,
            "cohort_credit_granted": False,
            "provider_dispatch_authorized": False,
            "owner_approval_inferred": False,
        },
    }


def _retained_manifest_errors(
    job: dict[str, Any], *, completed_root: Path
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", str(job.get("job_id") or "")):
        return None, None, ["retained_job_id_invalid"]
    try:
        root = completed_root.resolve(strict=True)
        manifest_path = (root / str(job["job_id"]) / "handoff-manifest.json").resolve(
            strict=True
        )
        manifest_path.relative_to(root)
    except (OSError, ValueError):
        return None, None, ["retained_manifest_unavailable"]
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return None, None, ["retained_manifest_not_regular"]
    try:
        manifest, manifest_sha256 = _read_json_path_with_sha256(manifest_path)
    except CohortError as exc:
        return None, None, [f"retained_manifest_{exc}"]
    files = manifest.get("files")
    normalized: list[dict[str, Any]] = []
    if isinstance(files, list):
        for raw in files:
            row = raw if isinstance(raw, dict) else {}
            normalized.append(
                {
                    "path": row.get("relative_path"),
                    "bytes": row.get("bytes"),
                    "sha256": row.get("sha256"),
                }
            )
    errors: list[str] = []
    if (
        manifest.get("schema")
        != "veritas.implementation_builder_worktree_manifest.v1"
        or manifest.get("job_id") != job["job_id"]
        or sorted(manifest.get("allowed_write_paths") or []) != _job_paths(job)
        or not _exact_projection(
            sorted(normalized, key=lambda row: str(row["path"])), _job_files(job)
        )
    ):
        errors.append("retained_manifest_preimage_mismatch")
    return manifest, manifest_sha256, errors


def _git_blob_hash(root: Path, path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{path}"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return _sha256_bytes(result.stdout) if result.returncode == 0 else None


def _git_exact_patch(root: Path, paths: list[str]) -> bytes | None:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--binary",
                "--no-ext-diff",
                "HEAD",
                "--",
                *paths,
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def _worktree_proof(
    job: dict[str, Any],
    close_proof_reference: str,
    *,
    root: Path,
    completed_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        import helper_lane_manifest as handoffs
        import implementation_builder_worktree_manager as worktrees
    except ImportError as exc:
        raise CohortError("worktree_verifier_unavailable") from exc
    close, close_path, close_sha256 = _read_json_reference(
        close_proof_reference, root=root
    )
    paths = _job_paths(job)
    if (
        close.get("action") != "close"
        or close.get("schema")
        != "veritas.implementation_builder_worktree_proof.v1"
        or close.get("status") != "ok"
        or close.get("job_id") != job["job_id"]
        or sorted(close.get("allowed_write_paths") or []) != paths
        or not _exact_int(close.get("changed_file_count"), minimum=2)
        or close.get("changed_file_count") != 2
        or close.get("unexpected_changed_paths") != []
        or close.get("patch_includes_declared_new_files") is not True
        or not isinstance(close.get("baseline_commit"), str)
        or re.fullmatch(r"[0-9a-f]{40}", close.get("baseline_commit") or "")
        is None
        or not isinstance(close.get("manifest_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", close.get("manifest_sha256") or "")
        is None
    ):
        raise CohortError("worktree_close_contract_invalid")
    changed = close.get("changed_files")
    if not isinstance(changed, list) or len(changed) != 2:
        raise CohortError("worktree_changed_files_invalid")
    changed_rows: list[dict[str, Any]] = []
    preimages = {row["path"]: row for row in _job_files(job)}
    for raw in changed:
        row = raw if isinstance(raw, dict) else {}
        path = _normal_relative_path(row.get("relative_path"))
        size = row.get("bytes")
        digest = row.get("sha256")
        if (
            path not in preimages
            or row.get("exists") is not True
            or not isinstance(size, int)
            or size < 1
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or digest == preimages[path]["sha256"]
        ):
            raise CohortError("worktree_changed_file_invalid_or_noop")
        changed_rows.append({"path": path, "bytes": size, "sha256": digest})
    changed_rows.sort(key=lambda row: row["path"])
    if [row["path"] for row in changed_rows] != paths:
        raise CohortError("worktree_changed_paths_mismatch")
    patch_path = _workspace_path_from_value(close.get("patch_path"), root=root)
    if patch_path.stat().st_size > MAX_PATCH_BYTES:
        raise CohortError("patch_too_large")
    patch_raw = patch_path.read_bytes()
    patch_sha256 = _sha256_bytes(patch_raw)
    if (
        patch_sha256 != close.get("patch_sha256")
        or patch_sha256 != close.get("tracked_diff_sha256")
    ):
        raise CohortError("patch_hash_mismatch")
    patch_paths, patch_errors = handoffs.unified_diff_changed_paths(patch_raw)
    if patch_errors or patch_paths != paths:
        raise CohortError("patch_path_inventory_invalid:" + ",".join(patch_errors))
    try:
        inventory_sha256 = worktrees.git_inventory_checkpoints_sha256(
            close.get("git_path_inventory_checkpoints"), paths
        )
    except Exception as exc:  # verifier owns the exact exception vocabulary
        raise CohortError("git_inventory_checkpoints_invalid") from exc
    if inventory_sha256 != close.get("git_path_inventory_sha256"):
        raise CohortError("git_inventory_hash_mismatch")
    retained, retained_sha256, retained_errors = _retained_manifest_errors(
        job, completed_root=completed_root
    )
    if retained_errors:
        raise CohortError(";".join(retained_errors))
    if close.get("manifest_sha256") != retained_sha256:
        raise CohortError("close_retained_manifest_hash_mismatch")
    for expected in _job_files(job):
        if _git_blob_hash(root, expected["path"]) != expected["sha256"]:
            raise CohortError("main_head_preimage_mismatch:" + expected["path"])
    if _git_exact_patch(root, paths) != patch_raw:
        raise CohortError("main_applied_diff_mismatch")
    current_errors = _current_post_file_errors(changed_rows, root=root)
    if current_errors:
        raise CohortError(";".join(current_errors))
    return {
        "close_proof_reference": _artifact_reference(close_path, root=root),
        "close_proof_sha256": close_sha256,
        "patch_reference": _artifact_reference(patch_path, root=root),
        "patch_sha256": patch_sha256,
        "git_path_inventory_sha256": inventory_sha256,
        "retained_manifest_sha256": retained_sha256,
        "retained_manifest_job_id": retained.get("job_id") if retained else None,
        "changed_paths": paths,
        "post_apply_files": changed_rows,
        "main_head_preimages_verified": True,
        "main_applied_patch_verified": True,
    }, changed_rows


def _usage_proof(
    lane: dict[str, Any],
    *,
    register_path: Path,
    agent_state_root: Path,
    state_db_path: Path,
    receipt_verifier: Callable[..., list[str]] | None = None,
    usage_loader: Callable[..., tuple[dict[str, Any] | None, list[str]]] | None = None,
    credit_assessor: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        import concurrent_lane_manager as lanes
        import isolated_agent_usage_metadata as usage
    except ImportError as exc:
        raise CohortError("usage_verifier_unavailable") from exc
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    store_path = lanes.usage_receipt_store_path(register_path)
    assessor = credit_assessor or lanes.usage_credit_assessment
    assessment = assessor(
        lane,
        runtime,
        receipt_store_path=store_path,
        require_reverification=True,
        source_reverified_this_action=True,
        isolated_agent_state_root=agent_state_root,
    )
    if assessment.get("usage_creditable") is not True:
        raw_reasons = assessment.get("reasons")
        detail = (
            ",".join(str(item) for item in raw_reasons)
            if isinstance(raw_reasons, list)
            else "unknown"
        )
        raise CohortError("usage_not_creditable:" + detail)
    verifier = receipt_verifier or lanes.verify_usage_source_receipt
    reasons = verifier(
        lane,
        runtime,
        store_path,
        isolated_agent_state_root=agent_state_root,
    )
    if reasons:
        raise CohortError("usage_receipt_invalid:" + ",".join(reasons))
    correlation = lanes.expected_attempt_correlation(lane, runtime)
    if not isinstance(correlation, dict):
        raise CohortError("usage_attempt_correlation_missing")
    expected_token = usage.dispatch_binding_token_hash_for_attempt(
        attempt_correlation_hash=correlation["key_hash"]
    )
    loader = usage_loader or usage.load_verified_isolated_session_usage_for_binding
    source, source_errors = loader(
        agent_id=AGENT_ID,
        expected_binding_token_hash=expected_token,
        agent_state_root=agent_state_root,
        state_db_path=state_db_path,
    )
    if source is None or source_errors:
        raise CohortError("usage_source_invalid:" + ",".join(source_errors))
    required = {
        "schema": "veritas.isolated_agent_usage_metadata.v1",
        "agent_id": AGENT_ID,
        "agent_role": "implementation_builder",
        "token_attribution_source": "openclaw_isolated_session_store_v2",
        "model_path": MODEL_PATH,
        "model_provider": "openai",
        "actual_thinking": THINKING,
        "source_context_prompt_semantics": "context_prompt_snapshot_not_run_usage_total",
        "input_token_semantics": "exclusive_cached",
        "source_total_tokens_fresh": True,
    }
    for key, value in required.items():
        if source.get(key) != value:
            raise CohortError("usage_source_field_mismatch:" + key)
    if runtime.get("source_snapshot_fingerprint") != source.get(
        "source_snapshot_fingerprint"
    ):
        raise CohortError("usage_snapshot_fingerprint_mismatch")
    if runtime.get("token_attribution_source") != "openclaw_isolated_session_store_v2":
        raise CohortError("runtime_usage_source_type_invalid")
    if (
        runtime.get("usage_source_receipt_schema")
        != "veritas.model_usage_source_receipt.v1"
    ):
        raise CohortError("runtime_usage_receipt_schema_invalid")
    dispatch = source.get("dispatch_binding")
    if not isinstance(dispatch, dict) or dispatch.get("binding_token_hash") != expected_token:
        raise CohortError("usage_dispatch_binding_mismatch")
    duration = source.get("duration_ms")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
        raise CohortError("usage_duration_missing")
    numeric_fields = (
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "source_input_total_tokens",
        "source_context_prompt_tokens",
        "total_tokens",
    )
    for key in numeric_fields:
        value = source.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CohortError("usage_token_field_invalid:" + key)
    if source["total_tokens"] != (
        source["input_tokens"]
        + source["cached_input_tokens"]
        + source["cache_write_tokens"]
        + source["output_tokens"]
    ):
        raise CohortError("usage_gross_total_reconciliation_failed")
    receipt_id = runtime.get("usage_source_receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id:
        raise CohortError("usage_receipt_id_missing")
    store = lanes.load_usage_receipt_store(store_path)
    receipt_matches = [
        row
        for row in store.get("receipts", [])
        if isinstance(row, dict) and row.get("receipt_id") == receipt_id
    ]
    if len(receipt_matches) != 1:
        raise CohortError("usage_receipt_missing_or_ambiguous")
    receipt = receipt_matches[0]
    binding_id = receipt.get("source_binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        raise CohortError("usage_source_binding_id_missing")
    if (
        receipt.get("source_type") != "openclaw_isolated_session_store_v2"
        or receipt.get("source_snapshot_fingerprint")
        != source.get("source_snapshot_fingerprint")
        or receipt.get("source_run_id") != source.get("run_id")
        or receipt.get("dispatch_binding") != source.get("dispatch_binding")
    ):
        raise CohortError("usage_receipt_direct_source_mismatch")
    return {
        "token_attribution_source": source["token_attribution_source"],
        "usage_source_receipt_id": receipt_id,
        "source_binding_id": binding_id,
        "source_snapshot_fingerprint": source["source_snapshot_fingerprint"],
        "run_id": source.get("run_id"),
        "actual_model_path": source["model_path"],
        "actual_thinking": source["actual_thinking"],
        "source_context_prompt_tokens": source["source_context_prompt_tokens"],
        "source_context_prompt_semantics": source[
            "source_context_prompt_semantics"
        ],
        "input_tokens": source["input_tokens"],
        "cached_input_tokens": source["cached_input_tokens"],
        "cache_write_tokens": source["cache_write_tokens"],
        "output_tokens": source["output_tokens"],
        "total_tokens": source["total_tokens"],
        "duration_ms": duration,
        "source_reverified": True,
    }


def _command_args(command: Any) -> list[str]:
    if not isinstance(command, str) or not command.startswith("python "):
        raise CohortError("validation_command_invalid")
    if any(token in command for token in ("&&", "||", ";", "|", "`", "$(")):
        raise CohortError("validation_command_control_operator_forbidden")
    args = shlex.split(command, posix=False)
    if not args or args[0].casefold() not in {"python", "python.exe"}:
        raise CohortError("validation_command_executable_invalid")
    return args


def _run_validation_command(
    command: str,
    *,
    root: Path,
    output_root: Path,
    label: str,
    write: bool,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            _command_args(command),
            cwd=root,
            capture_output=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CohortError("validation_command_unavailable:" + label) from exc
    stdout_path = output_root / f"{label}.stdout"
    stderr_path = output_root / f"{label}.stderr"
    stdout_hash = _sha256_bytes(result.stdout)
    stderr_hash = _sha256_bytes(result.stderr)
    if write:
        _write_bytes_once(stdout_path, result.stdout)
        _write_bytes_once(stderr_path, result.stderr)
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout_sha256": stdout_hash,
        "stderr_sha256": stderr_hash,
        "stdout_artifact": (
            _artifact_reference(stdout_path, root=root) if write else None
        ),
        "stderr_artifact": (
            _artifact_reference(stderr_path, root=root) if write else None
        ),
    }


def build_job_proof(
    *,
    job_id: str,
    close_proof_reference: str,
    root: Path = ROOT,
    controller_root: Path = CONTROLLER_ROOT,
    register_path: Path = REGISTER_PATH,
    completed_root: Path = COMPLETED_WORKTREE_ROOT,
    agent_state_root: Path = AGENT_STATE_ROOT,
    state_db_path: Path = STATE_DB_PATH,
    write_outputs: bool = False,
    receipt_verifier: Callable[..., list[str]] | None = None,
    usage_loader: Callable[..., tuple[dict[str, Any] | None, list[str]]] | None = None,
    credit_assessor: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = load_frozen_manifest(root=root)
    job = _job_by_id(manifest, job_id)
    number = int(job["job_number"])
    restart_packet = (
        load_frozen_restart_packet(root=root)[0] if number >= 2 else None
    )
    register = _load_register(register_path)
    attempt_lanes = _find_job_lanes(register, job)
    lane = attempt_lanes[-1]
    attempt_number = len(attempt_lanes)
    admission_path = _admission_path(controller_root, number, attempt_number)
    if not admission_path.exists():
        raise CohortError("admission_missing")
    admission, admission_sha256 = _read_json_path_with_sha256(admission_path)
    proof_now = datetime.now(timezone.utc)
    if (
        admission.get("schema") != ADMISSION_SCHEMA
        or admission.get("status") != "ok"
        or admission.get("cohort", {}).get("manifest_sha256") != MANIFEST_SHA256
        or admission.get("job", {}).get("job_id") != job_id
    ):
        raise CohortError("admission_invalid")
    if _parse_utc(admission.get("expires_at_utc")) <= proof_now:
        raise CohortError("admission_expired")
    binding = admission.get("binding") if isinstance(admission.get("binding"), dict) else {}
    binding_payload, binding_path, binding_sha256 = _read_json_reference(
        binding.get("reference"), root=root
    )
    if binding_sha256 != binding.get("sha256") or binding_payload.get("status") != "ok":
        raise CohortError("admission_binding_drift")
    admission_errors = _admission_snapshot_errors(
        admission,
        job,
        lane,
        attempt_lanes[:-1],
        root=root,
        controller_root=controller_root,
    )
    if admission_errors:
        raise CohortError(";".join(admission_errors))
    binding_time_errors = _admission_binding_time_errors(
        admission, binding_payload, unexpired_at=proof_now
    )
    if binding_time_errors:
        raise CohortError(";".join(binding_time_errors))
    if lane.get("lane_id") != admission.get("lane", {}).get("lane_id"):
        raise CohortError("admission_lane_drift")
    try:
        import concurrent_lane_manager as lanes
    except ImportError as exc:
        raise CohortError("lane_manager_unavailable") from exc
    receipt_sidecar = _artifact_reference(
        lanes.usage_receipt_store_path(register_path), root=root
    )
    lane_errors = _lane_contract_errors(
        lane,
        job,
        terminal=True,
        accepted=False,
        receipt_sidecar=receipt_sidecar,
        attempt_number=attempt_number,
    )
    lane_errors.extend(
        _prior_attempt_history_errors(
            attempt_lanes[:-1],
            job,
            receipt_sidecar=receipt_sidecar,
            root=root,
            controller_root=controller_root,
        )
    )
    if restart_packet is not None:
        lane_errors.extend(_restart_attempt_errors(job, attempt_lanes))
        lane_errors.extend(
            _restart_topology_errors(register, lane, manifest, restart_packet)
        )
        lane_errors.extend(
            _checkpoint_errors(
                lane,
                job,
                controller_root=controller_root,
                attempt_number=attempt_number,
            )
        )
    if lane_errors:
        raise CohortError(";".join(lane_errors))
    if admission.get("attempt") != _attempt_projection(lane):
        raise CohortError("admission_attempt_binding_drift")
    attempt_history = _attempt_history_projection(
        attempt_lanes[:-1],
        job=job,
        root=root,
        controller_root=controller_root,
    )
    if admission.get("attempt_history") != attempt_history:
        raise CohortError("admission_attempt_history_drift")
    usage = _usage_proof(
        lane,
        register_path=register_path,
        agent_state_root=agent_state_root,
        state_db_path=state_db_path,
        receipt_verifier=receipt_verifier,
        usage_loader=usage_loader,
        credit_assessor=credit_assessor,
    )
    worktree, post_files = _worktree_proof(
        job,
        close_proof_reference,
        root=root,
        completed_root=completed_root,
    )
    output_root = _job_dir(controller_root, number) / "validation"
    commands = [
        _run_validation_command(
            str(job.get("focused_test") or ""),
            root=root,
            output_root=output_root,
            label="focused-test",
            write=write_outputs,
        ),
        _run_validation_command(
            str(job.get("compile_test") or ""),
            root=root,
            output_root=output_root,
            label="compile-test",
            write=write_outputs,
        ),
    ]
    if any(
        not _exact_int(row.get("exit_code")) or row.get("exit_code") != 0
        for row in commands
    ):
        raise CohortError("validation_command_failed")
    if _current_post_file_errors(post_files, root=root):
        raise CohortError("post_apply_hash_changed_during_validation")
    try:
        final_binding_payload, final_binding_path, final_binding_sha256 = (
            _read_json_reference(binding.get("reference"), root=root)
        )
    except (CohortError, OSError) as exc:
        raise CohortError("admission_binding_drift") from exc
    if (
        final_binding_path != binding_path
        or final_binding_sha256 != binding_sha256
        or final_binding_payload != binding_payload
    ):
        raise CohortError("admission_binding_drift")
    proof_generated_at_utc = _utc_now()
    binding_time_errors = _admission_binding_time_errors(
        admission,
        final_binding_payload,
        unexpired_at=_parse_utc(proof_generated_at_utc),
    )
    if binding_time_errors:
        raise CohortError(";".join(binding_time_errors))
    runtime = lane.get("runtime") if isinstance(lane.get("runtime"), dict) else {}
    proof = {
        "schema": PROOF_SCHEMA,
        "status": "ok",
        "generated_at_utc": proof_generated_at_utc,
        "cohort": {
            "cohort_id": COHORT_ID,
            "manifest_reference": MANIFEST_REFERENCE,
            "manifest_sha256": MANIFEST_SHA256,
        },
        "job": {
            "job_number": number,
            "job_id": job_id,
            "allowed_write_paths": _job_paths(job),
        },
        "admission": {
            "reference": _artifact_reference(admission_path, root=root),
            "sha256": admission_sha256,
            "binding_reference": _artifact_reference(binding_path, root=root),
            "binding_sha256": binding_sha256,
        },
        "lane_terminal": {
            "lane_id": lane.get("lane_id"),
            "workstream_id": lane.get("workstream_id"),
            "completed_at_utc": lane.get("completed_at_utc")
            or lane.get("ended_at_utc"),
            "validator_result": runtime.get("validator_result"),
            "closure_durability": runtime.get("closure_durability"),
            "attempt_number": attempt_number,
            "retry_count": attempt_number - 1,
            "incident_code": runtime.get("incident_code"),
            "incident_count": runtime.get("incident_count"),
            "outcome_events": list(lane.get("outcome_events") or []),
            "outcome_event_kind": runtime.get("outcome_event_kind"),
            "outcome_event_sequence": runtime.get("outcome_event_sequence"),
            "outcome_recorded_at_utc": runtime.get("outcome_recorded_at_utc"),
        },
        "attempt_history": attempt_history,
        "usage": usage,
        "worktree": worktree,
        "validation": {
            "commands": commands,
            "validated_post_apply_files": post_files,
        },
        "authority_boundary": dict(PROOF_AUTHORITY_BOUNDARY),
        "errors": [],
    }
    proof_errors = _technical_proof_contract_errors(
        proof,
        job,
        admission_reference=_artifact_reference(admission_path, root=root),
        admission_sha256=admission_sha256,
        admission=admission,
    )
    proof_errors.extend(_proof_lane_binding_errors(proof, admission, lane))
    if proof_errors:
        raise CohortError(";".join(proof_errors))
    return proof


def _validate_acceptance(
    acceptance: dict[str, Any],
    proof: dict[str, Any],
    *,
    admission_sha256: str,
    proof_sha256: str,
) -> list[str]:
    errors: list[str] = []
    job = proof.get("job") if isinstance(proof.get("job"), dict) else {}
    worktree = proof.get("worktree") if isinstance(proof.get("worktree"), dict) else {}
    post_files = worktree.get("post_apply_files")
    if (
        set(acceptance) != ACCEPTANCE_FIELDS
        or acceptance.get("schema") != ACCEPTANCE_SCHEMA
        or acceptance.get("status") != "accepted"
        or acceptance.get("cohort_id") != COHORT_ID
        or acceptance.get("job_id") != job.get("job_id")
        or acceptance.get("manifest_sha256") != MANIFEST_SHA256
        or acceptance.get("admission_sha256") != admission_sha256
        or acceptance.get("job_proof_sha256") != proof_sha256
        or not _exact_projection(
            acceptance.get("accepted_post_apply_files"), post_files
        )
        or acceptance.get("main_verified") is not True
        or acceptance.get("acceptance_scope") != "wave2_measurement_credit_only"
        or acceptance.get("wave3_authorized") is not False
        or acceptance.get("automatic_route_promotion_allowed") is not False
    ):
        errors.append("main_acceptance_contract_invalid")
    validation = proof.get("validation") if isinstance(proof.get("validation"), dict) else {}
    if not _exact_projection(
        acceptance.get("accepted_validation_commands"), validation.get("commands")
    ):
        errors.append("main_acceptance_validation_binding_invalid")
    return errors


def build_credit(
    *,
    job_id: str,
    root: Path = ROOT,
    controller_root: Path = CONTROLLER_ROOT,
    register_path: Path = REGISTER_PATH,
    agent_state_root: Path = AGENT_STATE_ROOT,
    state_db_path: Path = STATE_DB_PATH,
    completed_root: Path = COMPLETED_WORKTREE_ROOT,
    receipt_verifier: Callable[..., list[str]] | None = None,
    usage_loader: Callable[..., tuple[dict[str, Any] | None, list[str]]] | None = None,
    credit_assessor: Callable[..., dict[str, Any]] | None = None,
    credit_evidence_verifier: (
        Callable[[dict[str, Any], dict[str, Any]], list[str]] | None
    ) = None,
) -> dict[str, Any]:
    manifest = load_frozen_manifest(root=root)
    credits, credit_errors = load_credit_chain(
        manifest, root=root, controller_root=controller_root
    )
    if credit_errors:
        raise CohortError(";".join(credit_errors))
    expected_number = len(credits) + 1
    job = _job_by_id(manifest, job_id)
    if job["job_number"] != expected_number:
        raise CohortError("credit_not_next_contiguous_job")
    restart_packet = (
        load_frozen_restart_packet(root=root)[0]
        if int(job["job_number"]) >= 2
        else None
    )
    register = _load_register(register_path)
    attempt_lanes = _find_job_lanes(register, job)
    lane = attempt_lanes[-1]
    attempt_number = len(attempt_lanes)
    proof_path = _proof_path(controller_root, expected_number)
    acceptance_path = _acceptance_path(controller_root, expected_number)
    admission_path = _admission_path(
        controller_root, expected_number, attempt_number
    )
    if not proof_path.exists() or not acceptance_path.exists() or not admission_path.exists():
        raise CohortError("credit_source_artifact_missing")
    admission, admission_sha256 = _read_json_path_with_sha256(admission_path)
    proof, proof_sha256 = _read_json_path_with_sha256(proof_path)
    acceptance, acceptance_sha256 = _read_json_path_with_sha256(acceptance_path)
    lane_terminal = (
        proof.get("lane_terminal")
        if isinstance(proof.get("lane_terminal"), dict)
        else {}
    )
    proof_errors = _technical_proof_contract_errors(
        proof,
        job,
        admission_reference=_artifact_reference(admission_path, root=root),
        admission_sha256=admission_sha256,
        admission=admission,
    )
    proof_errors.extend(_proof_lane_binding_errors(proof, admission, lane))
    if proof_errors:
        raise CohortError("technical_proof_invalid:" + ";".join(proof_errors))
    acceptance_errors = _validate_acceptance(
        acceptance,
        proof,
        admission_sha256=admission_sha256,
        proof_sha256=proof_sha256,
    )
    if acceptance_errors:
        raise CohortError(";".join(acceptance_errors))
    try:
        import concurrent_lane_manager as lanes
    except ImportError as exc:
        raise CohortError("lane_manager_unavailable") from exc
    receipt_sidecar = _artifact_reference(
        lanes.usage_receipt_store_path(register_path), root=root
    )
    lane_errors = _lane_contract_errors(
        lane,
        job,
        terminal=True,
        accepted=True,
        receipt_sidecar=receipt_sidecar,
        attempt_number=attempt_number,
    )
    lane_errors.extend(
        _prior_attempt_history_errors(
            attempt_lanes[:-1],
            job,
            receipt_sidecar=receipt_sidecar,
            root=root,
            controller_root=controller_root,
        )
    )
    if restart_packet is not None:
        lane_errors.extend(_restart_attempt_errors(job, attempt_lanes))
        lane_errors.extend(
            _restart_topology_errors(register, lane, manifest, restart_packet)
        )
        lane_errors.extend(
            _checkpoint_errors(
                lane,
                job,
                controller_root=controller_root,
                attempt_number=attempt_number,
            )
        )
    if (
        lane_terminal.get("attempt_number") != attempt_number
        or lane_terminal.get("retry_count") != attempt_number - 1
        or proof.get("attempt_history")
        != _attempt_history_projection(
            attempt_lanes[:-1],
            job=job,
            root=root,
            controller_root=controller_root,
        )
    ):
        lane_errors.append("technical_proof_attempt_history_drift")
    evidence = lane.get("runtime", {}).get("main_acceptance_evidence")
    if evidence != _artifact_reference(acceptance_path, root=root):
        lane_errors.append("lane_main_acceptance_evidence_mismatch")
    if lane_errors:
        raise CohortError(";".join(sorted(set(lane_errors))))
    reverified_usage = _usage_proof(
        lane,
        register_path=register_path,
        agent_state_root=agent_state_root,
        state_db_path=state_db_path,
        receipt_verifier=receipt_verifier,
        usage_loader=usage_loader,
        credit_assessor=credit_assessor,
    )
    if reverified_usage != proof.get("usage"):
        raise CohortError("technical_proof_usage_drift")
    post_files = proof.get("worktree", {}).get("post_apply_files")
    post_errors = _current_post_file_errors(post_files, root=root)
    if post_errors:
        raise CohortError(";".join(post_errors))
    used_receipts = {row.get("usage_source_receipt_id") for row in credits}
    used_bindings = {row.get("source_binding_id") for row in credits}
    if (
        reverified_usage["usage_source_receipt_id"] in used_receipts
        or reverified_usage["source_binding_id"] in used_bindings
    ):
        raise CohortError("usage_source_reused")
    previous_hash = None
    if expected_number > 1:
        previous_payload, previous_hash = _read_json_path_with_sha256(
            _credit_path(controller_root, expected_number - 1)
        )
        if previous_payload != credits[-1]:
            raise CohortError("previous_credit_changed_during_credit_build")
    candidate = {
        "schema": CREDIT_SCHEMA,
        "status": "credited",
        "generated_at_utc": _utc_now(),
        "cohort_id": COHORT_ID,
        "manifest_reference": MANIFEST_REFERENCE,
        "manifest_sha256": MANIFEST_SHA256,
        "credit_number": expected_number,
        "job_id": job_id,
        "previous_credit_sha256": previous_hash,
        "admission_reference": _artifact_reference(admission_path, root=root),
        "admission_sha256": admission_sha256,
        "technical_proof_reference": _artifact_reference(proof_path, root=root),
        "technical_proof_sha256": proof_sha256,
        "main_acceptance_reference": _artifact_reference(acceptance_path, root=root),
        "main_acceptance_sha256": acceptance_sha256,
        "lane_id": lane.get("lane_id"),
        "attempt_number": attempt_number,
        "retry_count": attempt_number - 1,
        "prior_zero_credit_incident_attempts": len(attempt_lanes) - 1,
        "usage_source_receipt_id": reverified_usage["usage_source_receipt_id"],
        "source_binding_id": reverified_usage["source_binding_id"],
        "source_snapshot_fingerprint": reverified_usage[
            "source_snapshot_fingerprint"
        ],
        "accepted_post_apply_files": post_files,
        "main_acceptance_status": "accepted",
        "wave3_review_gate_contribution": 1,
        "wave3_authorized": False,
        "automatic_route_promotion_allowed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    if credit_evidence_verifier is None:
        evidence_errors = _historical_credit_evidence_errors(
            candidate,
            job,
            root=root,
            controller_root=controller_root,
            register_path=register_path,
            completed_root=completed_root,
            agent_state_root=agent_state_root,
            state_db_path=state_db_path,
        )
    else:
        evidence_errors = credit_evidence_verifier(candidate, job)
    if evidence_errors:
        raise CohortError("credit_precommit_reverification_failed:" + ";".join(evidence_errors))
    return candidate


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--write", action="store_true")
    status_parser.add_argument("--validate", action="store_true")
    admit_parser = subparsers.add_parser("admit-next")
    admit_parser.add_argument("--binding", required=True)
    admit_parser.add_argument("--write", action="store_true")
    admit_parser.add_argument("--validate", action="store_true")
    checkpoint_parser = subparsers.add_parser("checkpoint-job")
    checkpoint_parser.add_argument("--job-id", required=True)
    checkpoint_parser.add_argument("--write", action="store_true")
    checkpoint_parser.add_argument("--validate", action="store_true")
    prove_parser = subparsers.add_parser("prove-job")
    prove_parser.add_argument("--job-id", required=True)
    prove_parser.add_argument("--worktree-close-proof", required=True)
    prove_parser.add_argument("--write", action="store_true")
    prove_parser.add_argument("--validate", action="store_true")
    credit_parser = subparsers.add_parser("credit-job")
    credit_parser.add_argument("--job-id", required=True)
    credit_parser.add_argument("--write", action="store_true")
    credit_parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "status":
            payload = derive_status()
            if args.write:
                _write_once(CONTROLLER_ROOT / "cohort-status.json", payload)
        elif args.command == "admit-next":
            payload = build_admission(binding_reference=args.binding)
            if args.write:
                number = int(payload["job"]["job_number"])
                attempt_number = int(payload["attempt"]["attempt_number"])
                _write_once(
                    _admission_path(CONTROLLER_ROOT, number, attempt_number),
                    payload,
                )
        elif args.command == "checkpoint-job":
            payload = build_checkpoint(job_id=args.job_id)
            if args.write:
                job = _job_by_id(load_frozen_manifest(), args.job_id)
                _write_once(
                    _checkpoint_path(
                        CONTROLLER_ROOT,
                        int(job["job_number"]),
                        int(payload["attempt_number"]),
                    ),
                    payload,
                )
        elif args.command == "prove-job":
            payload = build_job_proof(
                job_id=args.job_id,
                close_proof_reference=args.worktree_close_proof,
                write_outputs=args.write,
            )
            if args.write:
                number = int(payload["job"]["job_number"])
                _write_once(_proof_path(CONTROLLER_ROOT, number), payload)
        else:
            payload = build_credit(job_id=args.job_id)
            if args.write:
                _write_once(
                    _credit_path(CONTROLLER_ROOT, int(payload["credit_number"])),
                    payload,
                )
        _emit(payload)
        return 0 if payload.get("status") in {"ok", "credited"} else 1
    except (CohortError, OSError, subprocess.SubprocessError) as exc:
        payload = {
            "status": "error",
            "code": str(exc),
            "generated_at_utc": _utc_now(),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        _emit(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
