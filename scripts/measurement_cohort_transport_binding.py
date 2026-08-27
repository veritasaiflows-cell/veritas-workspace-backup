#!/usr/bin/env python3
"""Bind a fresh low-effort calibration to one frozen Wave 2 cohort job.

This module deliberately does not dispatch a provider job, create usage
receipts, or grant cohort credit.  It creates a short-lived admission binding
only after independent evidence already exists: a current low-effort scoped
worktree calibration, an exact cohort-wide owner authorization record, the
frozen cohort manifest/bootstrap handoff, and a clean active job worktree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PREFIX = "tmp/implementation-builder-scoped-worktree/"
EVIDENCE_ROOT = ROOT / "tmp" / "implementation-builder-scoped-worktree"
OWNER_APPROVAL_REFERENCE_PREFIX = "openclaw-owner-approval/"
OWNER_SESSION_ROOT = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
ACTIVE_WORKTREE_ROOT = (
    Path.home()
    / ".openclaw"
    / "workspaces"
    / "implementation-builder"
    / "handoff"
    / "scoped-worktree"
)
SCHEMA = "veritas.measurement_cohort_transport_binding.v2"
AUTHORIZATION_SCHEMA = "veritas.wave2_cohort_dispatch_authorization.v3"
CALIBRATION_PROOF_SCHEMA = "veritas.persistent_transport_proof.v3"
COHORT_MANIFEST_SCHEMA = "veritas.wave2_measurement_cohort_manifest.v1"
HANDOFF_SCHEMA = "veritas.helper_lane_manifest.v3"
# `cohort_id` is the immutable manifest identity.  The handoff's `swarm_id`
# deliberately uses a separate legacy/control-plane spelling, so bind both
# rather than conflating them.
COHORT_ID = "wave2-implementation-builder-10-job-measurement-v1"
HANDOFF_SWARM_ID = "WAVE2-10-JOB-MEASUREMENT-COHORT"
COHORT_MANIFEST_REFERENCE = (
    "tmp/implementation-builder-scoped-worktree/wave2-10-job-cohort-manifest-v1.json"
)
COHORT_MANIFEST_SHA256 = "9c721b1978c6cf214fe93cddc3056e152a471e9fe9fb49c5f2b6531b207dd8e7"
HANDOFF_REFERENCE = (
    "tmp/implementation-builder-scoped-worktree/wave2-job1-frozen-handoff-v1.json"
)
HANDOFF_SHA256 = "556043ad4ce746c17586d479cc0727d857617e8242e27991f5a7e6c4cebce82b"
TERRA_MODEL = "openai/gpt-5.6-terra"
AGENT_ID = "implementation-builder"
LANE_MODE = "scoped_worktree_implementation"
JOB_ID = "wave2-cohort-job-01-compact-exec-cwd"
LANE_ID = "WAVE2::COHORT::JOB-01::COMPACT-EXEC-CWD"
CALIBRATION_JOB_ID = f"{JOB_ID}-calibration"
CALIBRATION_ALLOWED_WRITE_PATHS = [
    "scripts/compact_exec.py",
    "scripts/test_compact_exec.py",
]
MAX_TTL = timedelta(hours=2)
DEFAULT_TTL = timedelta(hours=1)
MAX_CALIBRATION_AGE = timedelta(hours=24)
MAX_OWNER_APPROVAL_TTL = timedelta(hours=24)
# Direct-owner sessions can legitimately grow during a long governed cohort.
# Keep the verifier bounded, but above the observed Main transcript size so a
# later exact approval remains readable throughout the sequential run.
MAX_OWNER_TRANSCRIPT_BYTES = 32_000_000
OWNER_APPROVAL_HEADER = "WAVE2-COHORT-10-JOB-LOW-ROUTE-APPROVAL-V2"
OWNER_REVOCATION_HEADER = "WAVE2-COHORT-10-JOB-LOW-ROUTE-REVOKE-V2"


def _result(code: str, **detail: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "code": code}
    if detail:
        payload["detail"] = detail
    return payload


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_lower_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _normal_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        return None
    if value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return value


def _normal_reference_path(value: Any) -> str | None:
    """Canonicalize a CLI filesystem reference without weakening path guards."""
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    if any(ord(char) < 32 for char in value):
        return None
    return _normal_path(value.replace("\\", "/"))


def _evidence_path(reference: Any, *, root: Path) -> Path | None:
    normalized = _normal_reference_path(reference)
    if normalized is None or not normalized.startswith(EVIDENCE_PREFIX):
        return None
    try:
        candidate = (root / normalized).resolve()
        relative = candidate.relative_to(root.resolve()).as_posix()
        candidate.relative_to((root / "tmp" / "implementation-builder-scoped-worktree").resolve())
    except (OSError, ValueError):
        return None
    return candidate if relative == normalized else None


def _read_json_reference(reference: Any, *, root: Path, max_bytes: int = 200_000) -> tuple[dict[str, Any] | None, str | None, str | None]:
    path = _evidence_path(reference, root=root)
    if path is None:
        return None, None, "measurement_cohort_binding_reference_invalid"
    try:
        raw = path.read_bytes()
    except OSError:
        return None, None, "measurement_cohort_binding_source_unreadable"
    if not raw or len(raw) > max_bytes:
        return None, None, "measurement_cohort_binding_source_unreadable"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None, "measurement_cohort_binding_source_malformed"
    if not isinstance(payload, dict):
        return None, None, "measurement_cohort_binding_source_malformed"
    return payload, hashlib.sha256(raw).hexdigest(), None


def _read_frozen_source(
    reference: Any,
    *,
    expected_reference: str,
    expected_sha256: str,
    root: Path,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if reference != expected_reference:
        return None, None, "measurement_cohort_binding_frozen_reference_invalid"
    payload, digest, error = _read_json_reference(reference, root=root)
    if error or digest != expected_sha256:
        return None, None, error or "measurement_cohort_binding_frozen_hash_mismatch"
    return payload, digest, None


def _path_hashes(value: Any, *, bytes_key: str) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    rows: list[dict[str, Any]] = []
    for item in value:
        record = _as_dict(item)
        path = _normal_path(record.get("path") or record.get("relative_path"))
        size = record.get(bytes_key)
        digest = record.get("sha256")
        if path is None or not isinstance(size, int) or isinstance(size, bool) or size <= 0 or not _is_lower_hex(digest, 64):
            return None
        rows.append({"path": path, "bytes": size, "sha256": digest})
    if len({row["path"] for row in rows}) != 2:
        return None
    return sorted(rows, key=lambda row: row["path"])


def _source_contract(
    manifest: dict[str, Any],
    handoff: dict[str, Any],
    *,
    selected_job_id: str = JOB_ID,
    handoff_reference: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    fixed_route = _as_dict(manifest.get("fixed_route_contract"))
    required_route = {
        "agent_id": AGENT_ID,
        "execution_backend": "persistent_isolated_agent",
        "model_path": TERRA_MODEL,
        "thinking": "low",
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
    if (
        manifest.get("schema") != COHORT_MANIFEST_SCHEMA
        or manifest.get("status") != "frozen_pending_hot_activation_and_sequential_dispatch"
        or manifest.get("cohort_id") != COHORT_ID
        or fixed_route != required_route
    ):
        return None, "measurement_cohort_binding_manifest_contract_invalid"
    manifest_boundary = _as_dict(manifest.get("authority_boundary"))
    if (
        manifest_boundary.get("preparation_only") is not True
        or manifest_boundary.get("provider_job_dispatch_authorized") is not False
        or any(manifest_boundary.get(name) is not False for name in (
        "config_or_runtime_changed",
        "automatic_route_promotion_allowed",
        "wave3_authorized",
        "finance_canon_portfolio_or_execution_authority",
        "owner_approval_inferred",
        ))
    ):
        return None, "measurement_cohort_binding_manifest_authority_invalid"
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 10:
        return None, "measurement_cohort_binding_manifest_contract_invalid"
    roster: list[dict[str, Any]] = []
    for row in jobs:
        candidate = _as_dict(row)
        number = candidate.get("job_number")
        candidate_id = candidate.get("job_id")
        files = _path_hashes(candidate.get("write_files"), bytes_key="bytes")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or number not in range(1, 11)
            or not isinstance(candidate_id, str)
            or not candidate_id
            or files is None
        ):
            return None, "measurement_cohort_binding_manifest_roster_invalid"
        roster.append(
            {
                "job_number": number,
                "job_id": candidate_id,
                "write_files": files,
            }
        )
    if (
        sorted(row["job_number"] for row in roster) != list(range(1, 11))
        or len({row["job_id"] for row in roster}) != 10
        or len(
            {
                file["path"]
                for row in roster
                for file in row["write_files"]
            }
        )
        != 20
    ):
        return None, "measurement_cohort_binding_manifest_roster_invalid"
    cohort_job_ids = [
        row["job_id"] for row in sorted(roster, key=lambda item: item["job_number"])
    ]
    activation = _as_dict(handoff.get("activation_job_contract"))
    activation_job_id = activation.get("job_id")
    if activation_job_id != JOB_ID:
        return None, "measurement_cohort_binding_handoff_contract_invalid"
    activation_jobs = [row for row in jobs if _as_dict(row).get("job_id") == activation_job_id]
    if len(activation_jobs) != 1:
        return None, "measurement_cohort_binding_job_missing"
    activation_job = _as_dict(activation_jobs[0])
    activation_files = _path_hashes(activation_job.get("write_files"), bytes_key="bytes")
    if (
        activation_job.get("job_number") != 1
        or activation_files is None
        or [row["path"] for row in activation_files] != CALIBRATION_ALLOWED_WRITE_PATHS
    ):
        return None, "measurement_cohort_binding_job_paths_invalid"
    if (
        handoff.get("schema") != HANDOFF_SCHEMA
        or handoff.get("status") != "ok"
        or handoff.get("swarm_id") != HANDOFF_SWARM_ID
        or handoff.get("provider_job_dispatch_authorized") is not None
        or handoff.get("execution_authorization") is not None
        or (
            handoff_reference is not None
            and activation_job.get("activation_handoff") != handoff_reference
        )
    ):
        return None, "measurement_cohort_binding_handoff_contract_invalid"
    if activation.get("schema") != "veritas.wave2_job_activation_contract.v1":
        return None, "measurement_cohort_binding_handoff_contract_invalid"
    if sorted(activation.get("allowed_files") or []) != [row["path"] for row in activation_files]:
        return None, "measurement_cohort_binding_handoff_paths_invalid"
    lanes = handoff.get("expected_lanes")
    if not isinstance(lanes, list) or len(lanes) != 1:
        return None, "measurement_cohort_binding_handoff_contract_invalid"
    lane = _as_dict(lanes[0])
    lane_handoff = _as_dict(lane.get("handoff"))
    lane_files = _path_hashes(lane_handoff.get("files"), bytes_key="size_bytes")
    if (
        lane.get("lane_id") != LANE_ID
        or lane.get("owner_workflow") != "WAVE2"
        or lane.get("status") != "pending"
        or lane.get("verdict") != "awaiting_owner_activation_and_dispatch"
        or lane.get("allow_partial") is not False
        or str(lane.get("session_id") or "")
        or str(lane.get("session_label") or "")
        or _as_dict(lane.get("attempt")).get("attempt_number") != 1
        or _as_dict(lane.get("attempt")).get("retry_count") != 0
        or _as_dict(lane.get("attempt")).get("is_first_attempt") is not True
        or lane_handoff.get("contract_version") != 3
        or lane_handoff.get("base_path") != "."
        or lane_files != activation_files
        or not isinstance(lane_handoff.get("frozen_snapshot_id"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", lane_handoff["frozen_snapshot_id"])
        or not isinstance(lane_handoff.get("contract_sha256"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", lane_handoff["contract_sha256"])
    ):
        return None, "measurement_cohort_binding_handoff_contract_invalid"
    handoff_boundary = _as_dict(handoff.get("authority_boundary"))
    if any(handoff_boundary.get(name) is not False for name in (
        "config_auth_channel_runtime_mutation_allowed",
        "customer_or_external_delivery_allowed",
        "sql_or_ticker_import_allowed",
        "canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    )):
        return None, "measurement_cohort_binding_handoff_authority_invalid"
    matching_jobs = [row for row in jobs if _as_dict(row).get("job_id") == selected_job_id]
    if len(matching_jobs) != 1:
        return None, "measurement_cohort_binding_job_missing"
    selected_job = _as_dict(matching_jobs[0])
    selected_files = _path_hashes(selected_job.get("write_files"), bytes_key="bytes")
    selected_number = selected_job.get("job_number")
    if (
        not isinstance(selected_number, int)
        or isinstance(selected_number, bool)
        or selected_number not in range(1, 11)
        or selected_files is None
        or (selected_number == 1 and selected_job_id != JOB_ID)
        or (selected_number != 1 and selected_job.get("activation_handoff") is not None)
    ):
        return None, "measurement_cohort_binding_job_paths_invalid"
    return {
        "cohort_id": COHORT_ID,
        "job_number": selected_number,
        "job_id": selected_job_id,
        "allowed_write_paths": [row["path"] for row in selected_files],
        "source_file_hashes": selected_files,
        "calibration_job_id": CALIBRATION_JOB_ID,
        "calibration_allowed_write_paths": list(CALIBRATION_ALLOWED_WRITE_PATHS),
        "cohort_job_ids": cohort_job_ids,
        "frozen_snapshot_id": lane_handoff["frozen_snapshot_id"],
        "contract_sha256": lane_handoff["contract_sha256"],
    }, None


def _current_source_hashes(contract: dict[str, Any], *, root: Path) -> list[dict[str, Any]] | None:
    rows: list[dict[str, Any]] = []
    for expected in contract["source_file_hashes"]:
        path = root / expected["path"]
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        actual = {"path": expected["path"], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if actual != expected:
            return None
        rows.append(actual)
    return rows


def _stable_expected_file_hashes(
    base: Path, expected_files: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Hash exact active-worktree files without trusting manifest claims."""
    resolved_base = base.resolve()
    rows: list[dict[str, Any]] = []
    try:
        for expected in expected_files:
            path = (resolved_base / expected["path"]).resolve()
            path.relative_to(resolved_base)
            before = path.stat()
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected["bytes"]:
                return None
            data = path.read_bytes()
            after = path.stat()
            stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
            if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
                return None
            actual = {
                "path": expected["path"],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            if actual != expected:
                return None
            rows.append(actual)
    except (KeyError, OSError, ValueError):
        return None
    return rows


def collect_active_worktree_state(*, active_root: Path = ACTIVE_WORKTREE_ROOT) -> dict[str, Any] | None:
    manifest_path = active_root / "handoff-manifest.json"
    try:
        manifest_raw = manifest_path.read_bytes()
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    git = shutil.which("git") or shutil.which("git.exe")
    if not git:
        return None
    try:
        head = subprocess.run([git, "-C", str(active_root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        status = subprocess.run([git, "-C", str(active_root), "status", "--porcelain=v1", "--untracked-files=all", "--no-renames"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    commit = (head.stdout or "").strip().lower()
    if head.returncode != 0 or status.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", commit) is None or (status.stdout or "").strip():
        return None
    paths = _path_hashes(manifest.get("files"), bytes_key="bytes")
    if (
        manifest.get("schema") != "veritas.implementation_builder_worktree_manifest.v1"
        or manifest.get("job_id") is None
        or paths is None
        or manifest.get("allowed_write_paths") != [row["path"] for row in paths]
    ):
        return None
    actual_paths = _stable_expected_file_hashes(active_root, paths)
    if actual_paths != paths:
        return None
    try:
        head_after = subprocess.run([git, "-C", str(active_root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        status_after = subprocess.run([git, "-C", str(active_root), "status", "--porcelain=v1", "--untracked-files=all", "--no-renames"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if (
        head_after.returncode != 0
        or status_after.returncode != 0
        or (head_after.stdout or "").strip().lower() != commit
        or (status_after.stdout or "").strip()
    ):
        return None
    return {
        "job_id": manifest["job_id"],
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "baseline_commit": commit,
        "allowed_write_paths": [row["path"] for row in paths],
        "source_file_hashes": actual_paths,
    }


def _validate_calibration(
    payload: dict[str, Any],
    contract: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str | None:
    runtime = _as_dict(payload.get("runtime"))
    evidence = _as_dict(payload.get("evidence"))
    worktree = _as_dict(evidence.get("worktree"))
    expected_job = contract["calibration_job_id"]
    expected_manifest_reference = (
        f"retained_completed_worktree/{expected_job}/handoff-manifest.json"
    )
    if (
        payload.get("schema") != CALIBRATION_PROOF_SCHEMA
        or payload.get("status") != "ok"
        or payload.get("agent_id") != AGENT_ID
        or set(runtime) != {
            "execution_backend",
            "provider",
            "model",
            "thinking",
            "openclaw_version",
            "config_sha256",
        }
        or runtime.get("execution_backend") != "persistent_isolated_agent"
        or runtime.get("provider") != "openai"
        or runtime.get("model") != TERRA_MODEL
        or runtime.get("thinking") != "low"
        or not isinstance(runtime.get("openclaw_version"), str)
        or not runtime["openclaw_version"].strip()
        or not _is_lower_hex(runtime.get("config_sha256"), 64)
        or worktree.get("job_id") != expected_job
        or worktree.get("manifest_reference") != expected_manifest_reference
        or sorted(worktree.get("changed_paths") or [])
        != contract["calibration_allowed_write_paths"]
    ):
        return "measurement_cohort_binding_calibration_invalid"
    try:
        observed = _parse_time(payload.get("observed_at_utc"))
        expires = _parse_time(payload.get("expires_at_utc"))
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        current = current.astimezone(timezone.utc)
        if (
            observed > current
            or current - observed > MAX_CALIBRATION_AGE
            or expires <= observed
            or expires - observed > MAX_CALIBRATION_AGE
            or expires <= current
        ):
            raise ValueError("stale calibration")
    except (TypeError, ValueError):
        return "measurement_cohort_binding_calibration_expired"
    return None


def _required_authorization_scope(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wave2_cohort_dispatch_scope.v1",
        "cohort_id": COHORT_ID,
        "cohort_manifest_reference": COHORT_MANIFEST_REFERENCE,
        "cohort_manifest_sha256": COHORT_MANIFEST_SHA256,
        "cohort_job_ids": list(contract["cohort_job_ids"]),
        "job1_anchor_handoff_reference": HANDOFF_REFERENCE,
        "job1_anchor_handoff_sha256": HANDOFF_SHA256,
        "calibration_proof_reference": contract["calibration_proof_reference"],
        "calibration_proof_sha256": contract["calibration_proof_sha256"],
        "calibration_job_id": CALIBRATION_JOB_ID,
        "calibration_capability_only": True,
        "agent_id": AGENT_ID,
        "execution_backend": "persistent_isolated_agent",
        "model_path": TERRA_MODEL,
        "thinking": "low",
        "persistent_lane_mode": LANE_MODE,
        "dispatch_order": "strictly_sequential",
        "cohort_dispatch_authorized": True,
        "supersedes_preparation_only_for_exact_frozen_cohort": True,
    }


def _owner_approval_reference(reference: Any) -> tuple[str, str] | None:
    normalized = _normal_path(reference)
    if normalized is None or not normalized.startswith(OWNER_APPROVAL_REFERENCE_PREFIX):
        return None
    parts = normalized.split("/")
    if len(parts) != 3 or parts[0] != OWNER_APPROVAL_REFERENCE_PREFIX.rstrip("/"):
        return None
    try:
        session_id = str(uuid.UUID(parts[1]))
        message_id = str(uuid.UUID(parts[2]))
    except (AttributeError, ValueError):
        return None
    if parts[1] != session_id or parts[2] != message_id:
        return None
    return session_id, message_id


def _owner_approval_statement(
    approval_id: str,
    scope_sha256: str,
    expires_at_utc: str,
) -> str:
    return "\n".join(
        (
            OWNER_APPROVAL_HEADER,
            f"approval_id={approval_id}",
            f"scope_sha256={scope_sha256}",
            f"expires_at_utc={expires_at_utc}",
        )
    )


def _owner_revocation_statement(approval_id: str) -> str:
    return "\n".join((OWNER_REVOCATION_HEADER, f"approval_id={approval_id}"))


def _direct_owner_message(message: dict[str, Any]) -> bool:
    metadata = _as_dict(message.get("__openclaw"))
    provenance = _as_dict(message.get("provenance"))
    return bool(
        message.get("role") == "user"
        and message.get("sourceChannel") in {"webchat", "telegram"}
        and metadata.get("senderIsOwner") is True
        and provenance.get("kind") != "inter_session"
    )


def _read_owner_approval(
    reference: Any,
    *,
    session_root: Path = OWNER_SESSION_ROOT,
) -> tuple[dict[str, Any] | None, str | None]:
    identity = _owner_approval_reference(reference)
    if identity is None:
        return None, "measurement_cohort_binding_authorization_reference_invalid"
    session_id, message_id = identity
    try:
        resolved_root = session_root.resolve(strict=True)
        transcript = (resolved_root / f"{session_id}.jsonl").resolve(strict=True)
        transcript.relative_to(resolved_root)
        if transcript.parent != resolved_root or transcript.is_symlink():
            raise ValueError("session path escaped controlled root")
        if transcript.stat().st_size > MAX_OWNER_TRANSCRIPT_BYTES:
            raise ValueError("transcript too large")
        raw = transcript.read_bytes()
    except (OSError, ValueError):
        return None, "measurement_cohort_binding_authorization_verifier_unavailable"
    if not raw or len(raw) > MAX_OWNER_TRANSCRIPT_BYTES:
        return None, "measurement_cohort_binding_authorization_verifier_unavailable"
    rows = raw.splitlines()
    if not rows:
        return None, "measurement_cohort_binding_authorization_verifier_unavailable"
    try:
        header = json.loads(rows[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "measurement_cohort_binding_authorization_verifier_unavailable"
    if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != session_id:
        return None, "measurement_cohort_binding_authorization_verifier_unavailable"
    matches: list[dict[str, Any]] = []
    for raw_row in rows[1:]:
        try:
            row = json.loads(raw_row.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "measurement_cohort_binding_authorization_verifier_unavailable"
        if not isinstance(row, dict) or row.get("type") != "message" or row.get("id") != message_id:
            continue
        message = _as_dict(row.get("message"))
        if not _direct_owner_message(message) or not isinstance(message.get("content"), str):
            return None, "measurement_cohort_binding_authorization_source_invalid"
        try:
            observed_at = _parse_time(row.get("timestamp"))
        except (TypeError, ValueError):
            return None, "measurement_cohort_binding_authorization_source_invalid"
        matches.append(
            {
                "session_id": session_id,
                "message_id": message_id,
                "observed_at": observed_at,
                "content": message["content"],
                "source_event_sha256": hashlib.sha256(raw_row).hexdigest(),
            }
        )
    if len(matches) != 1:
        return None, "measurement_cohort_binding_authorization_source_invalid"
    return matches[0], None


def _authorization_revoked(
    approval: dict[str, Any],
    *,
    session_root: Path,
) -> bool | None:
    """Check later owner messages in the same controlled session for revocation."""
    try:
        session_id = str(approval["session_id"])
        resolved_root = session_root.resolve(strict=True)
        transcript = (resolved_root / f"{session_id}.jsonl").resolve(strict=True)
        transcript.relative_to(resolved_root)
        if transcript.parent != resolved_root or transcript.is_symlink():
            raise ValueError("session path escaped controlled root")
        if transcript.stat().st_size > MAX_OWNER_TRANSCRIPT_BYTES:
            raise ValueError("transcript too large")
        raw = transcript.read_bytes()
        if len(raw) > MAX_OWNER_TRANSCRIPT_BYTES:
            raise ValueError("transcript too large")
    except (OSError, ValueError):
        return None
    revocation = _owner_revocation_statement(str(approval["approval_id"]))
    source_still_present = False
    for raw_row in raw.splitlines()[1:]:
        try:
            row = json.loads(raw_row.decode("utf-8"))
            message = _as_dict(row.get("message"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if row.get("id") == approval.get("message_id"):
            if hashlib.sha256(raw_row).hexdigest() != approval.get("source_event_sha256"):
                return None
            source_still_present = True
        if (
            source_still_present
            and _direct_owner_message(message)
            and message.get("content") == revocation
        ):
            return True
    return False if source_still_present else None


def _resolve_authorization(
    reference: Any,
    contract: dict[str, Any],
    *,
    now: datetime | None = None,
    session_root: Path = OWNER_SESSION_ROOT,
) -> tuple[dict[str, Any] | None, str | None]:
    approval, error = _read_owner_approval(reference, session_root=session_root)
    if error:
        return None, error
    raw_lines = str((approval or {}).get("content", "")).splitlines()
    approval_id = raw_lines[1].removeprefix("approval_id=") if len(raw_lines) >= 2 else ""
    scope_sha256 = _canonical_sha256(_required_authorization_scope(contract))
    if not approval or not isinstance(approval_id, str) or re.fullmatch(r"wave2-cohort-10-job-[a-z0-9-]{8,128}", approval_id) is None:
        return None, "measurement_cohort_binding_authorization_invalid"
    if len(raw_lines) != 4 or raw_lines[0] != OWNER_APPROVAL_HEADER:
        return None, "measurement_cohort_binding_authorization_invalid"
    fields = {}
    for line in raw_lines[1:]:
        key, separator, value = line.partition("=")
        if not separator or key in fields:
            return None, "measurement_cohort_binding_authorization_invalid"
        fields[key] = value
    if set(fields) != {"approval_id", "scope_sha256", "expires_at_utc"}:
        return None, "measurement_cohort_binding_authorization_invalid"
    try:
        expires_at = _parse_time(fields["expires_at_utc"])
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        current = current.astimezone(timezone.utc)
        observed_at = approval["observed_at"]
        if not isinstance(observed_at, datetime):
            raise ValueError("source timestamp missing")
        if (
            fields["approval_id"] != approval_id
            or fields["scope_sha256"] != scope_sha256
            or expires_at <= observed_at
            or expires_at - observed_at > MAX_OWNER_APPROVAL_TTL
            or expires_at <= current
        ):
            raise ValueError("approval scope or expiration invalid")
    except (TypeError, ValueError):
        return None, "measurement_cohort_binding_authorization_invalid"
    approval["approval_id"] = approval_id
    revoked = _authorization_revoked(approval, session_root=session_root)
    if revoked is None:
        return None, "measurement_cohort_binding_authorization_verifier_unavailable"
    if revoked:
        return None, "measurement_cohort_binding_authorization_revoked"
    return {
        "schema": AUTHORIZATION_SCHEMA,
        "reference": reference,
        "approval_id": approval_id,
        "scope_sha256": scope_sha256,
        "issued_at_utc": _utc_text(observed_at),
        "expires_at_utc": _utc_text(expires_at),
        "source_session_id": approval["session_id"],
        "source_message_id": approval["message_id"],
        "source_event_sha256": approval["source_event_sha256"],
    }, None


def _calibration_projection(check: dict[str, Any]) -> dict[str, Any] | None:
    """Persist only the strict proof facts that admission must recheck."""
    runtime = _as_dict(check.get("runtime"))
    worktree = _as_dict(_as_dict(check.get("evidence")).get("worktree"))
    if (
        check.get("status") != "ok"
        or check.get("proof_schema") != CALIBRATION_PROOF_SCHEMA
    ):
        return None
    return {
        "proof_schema": check["proof_schema"],
        "runtime": {
            name: runtime.get(name)
            for name in (
                "execution_backend",
                "provider",
                "model",
                "thinking",
                "openclaw_version",
                "config_sha256",
            )
        },
        "worktree": {
            name: worktree.get(name)
            for name in (
                "job_id",
                "manifest_reference",
                "manifest_sha256",
                "baseline_commit",
                "changed_paths",
                "git_path_inventory_sha256",
            )
        },
    }


def _strict_calibration_projection_valid(
    projection: dict[str, Any] | None,
    contract: dict[str, Any],
) -> bool:
    if projection is None:
        return False
    runtime = _as_dict(projection.get("runtime"))
    worktree = _as_dict(projection.get("worktree"))
    return bool(
        projection.get("proof_schema") == CALIBRATION_PROOF_SCHEMA
        and runtime.get("execution_backend") == "persistent_isolated_agent"
        and runtime.get("provider") == "openai"
        and runtime.get("model") == TERRA_MODEL
        and runtime.get("thinking") == "low"
        and worktree.get("job_id") == contract["calibration_job_id"]
        and worktree.get("manifest_reference")
        == f"retained_completed_worktree/{contract['calibration_job_id']}/handoff-manifest.json"
        and sorted(worktree.get("changed_paths") or [])
        == contract["calibration_allowed_write_paths"]
    )


def _strict_calibration_check(
    reference: str,
    *,
    root: Path,
    injected_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Use the router's full v3 verifier rather than trusting a proof JSON."""
    if injected_check is not None:
        return injected_check
    if root.resolve() != ROOT.resolve():
        return _result("measurement_cohort_binding_strict_calibration_root_invalid")
    try:
        # Import lazily: the router imports this module, but is fully loaded
        # before it ever calls the binding inspector.
        import project_implementation_router as router
    except ImportError:
        return _result("measurement_cohort_binding_strict_calibration_unavailable")
    return router.inspect_persistent_transport_proof(
        reference,
        AGENT_ID,
        LANE_MODE,
        "low",
    )


def build_binding(
    *,
    cohort_manifest_reference: str,
    handoff_reference: str,
    calibration_proof_reference: str,
    authorization_reference: str,
    job_id: str = JOB_ID,
    root: Path = ROOT,
    active_state: dict[str, Any] | None = None,
    now: datetime | None = None,
    ttl: timedelta = DEFAULT_TTL,
    strict_calibration_check: dict[str, Any] | None = None,
    owner_session_root: Path = OWNER_SESSION_ROOT,
) -> dict[str, Any]:
    if ttl <= timedelta() or ttl > MAX_TTL:
        return _result("measurement_cohort_binding_ttl_invalid")
    canonical_manifest_reference = _normal_reference_path(cohort_manifest_reference)
    canonical_handoff_reference = _normal_reference_path(handoff_reference)
    canonical_calibration_reference = _normal_reference_path(calibration_proof_reference)
    if canonical_manifest_reference is None or canonical_handoff_reference is None:
        return _result("measurement_cohort_binding_frozen_reference_invalid")
    if canonical_calibration_reference is None:
        return _result("measurement_cohort_binding_reference_invalid")
    manifest, manifest_hash, error = _read_frozen_source(
        canonical_manifest_reference,
        expected_reference=COHORT_MANIFEST_REFERENCE,
        expected_sha256=COHORT_MANIFEST_SHA256,
        root=root,
    )
    if error:
        return _result(error)
    handoff, handoff_hash, error = _read_frozen_source(
        canonical_handoff_reference,
        expected_reference=HANDOFF_REFERENCE,
        expected_sha256=HANDOFF_SHA256,
        root=root,
    )
    if error:
        return _result(error)
    contract, error = _source_contract(
        manifest or {},
        handoff or {},
        selected_job_id=job_id,
        handoff_reference=canonical_handoff_reference,
    )
    if error:
        return _result(error)
    calibration, calibration_hash, error = _read_json_reference(canonical_calibration_reference, root=root)
    if error:
        return _result(error)
    error = _validate_calibration(calibration or {}, contract or {}, now=now)
    if error:
        return _result(error)
    strict_check = _strict_calibration_check(
        canonical_calibration_reference,
        root=root,
        injected_check=strict_calibration_check,
    )
    strict_projection = _calibration_projection(strict_check)
    if not _strict_calibration_projection_valid(strict_projection, contract or {}):
        return _result(
            "measurement_cohort_binding_calibration_strict_invalid",
            cause=str(strict_check.get("code") or "unavailable"),
        )
    authorization_contract = {
        **(contract or {}),
        "calibration_proof_reference": canonical_calibration_reference,
        "calibration_proof_sha256": calibration_hash,
    }
    authorization, error = _resolve_authorization(
        authorization_reference,
        authorization_contract,
        now=now,
        session_root=owner_session_root,
    )
    if error:
        return _result(error)
    source_hashes = _current_source_hashes(contract or {}, root=root)
    state = active_state if active_state is not None else collect_active_worktree_state()
    if source_hashes is None or state is None:
        return _result("measurement_cohort_binding_active_worktree_invalid")
    if (
        state.get("job_id") != contract["job_id"]
        or state.get("allowed_write_paths") != contract["allowed_write_paths"]
        or state.get("source_file_hashes") != contract["source_file_hashes"]
    ):
        return _result("measurement_cohort_binding_active_worktree_drift")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        return _result("measurement_cohort_binding_expiry_invalid")
    current = current.astimezone(timezone.utc)
    try:
        calibration_expires = _parse_time((calibration or {}).get("expires_at_utc"))
        authorization_expires = _parse_time((authorization or {}).get("expires_at_utc"))
    except (TypeError, ValueError):
        return _result("measurement_cohort_binding_expiry_invalid")
    if current + ttl > calibration_expires:
        return _result("measurement_cohort_binding_calibration_expiry_insufficient")
    if current + ttl > authorization_expires:
        return _result("measurement_cohort_binding_authorization_expiry_insufficient")
    return {
        "schema": SCHEMA,
        "status": "ok",
        "generated_at_utc": _utc_text(current),
        "expires_at_utc": _utc_text(current + ttl),
        "cohort": {"cohort_id": COHORT_ID, "manifest_reference": canonical_manifest_reference, "manifest_sha256": manifest_hash},
        "handoff": {"reference": canonical_handoff_reference, "sha256": handoff_hash, "frozen_snapshot_id": contract["frozen_snapshot_id"], "contract_sha256": contract["contract_sha256"]},
        "job": {"job_number": contract["job_number"], "job_id": contract["job_id"], "allowed_write_paths": contract["allowed_write_paths"], "source_file_hashes": source_hashes},
        "calibration": {
            "reference": canonical_calibration_reference,
            "sha256": calibration_hash,
            "job_id": contract["calibration_job_id"],
            "changed_paths": contract["calibration_allowed_write_paths"],
            "strict_projection": strict_projection,
        },
        "authorization": {
            **authorization,
        },
        "active_worktree": state,
        "route": {"execution_backend": "persistent_isolated_agent", "model_path": TERRA_MODEL, "thinking": "low", "agent_id": AGENT_ID, "persistent_lane_mode": LANE_MODE},
        "authority_boundary": {"measurement_only": True, "protected_dispatch_binding_created": False, "usage_receipt_created": False, "cohort_credit_granted": False, "config_auth_runtime_mutation_allowed": False, "finance_canon_portfolio_or_execution_authority": False, "external_delivery_allowed": False, "owner_approval_inferred": False},
    }


def validate_binding_payload(
    payload: Any,
    *,
    root: Path = ROOT,
    active_state: dict[str, Any] | None = None,
    now: datetime | None = None,
    strict_calibration_check: dict[str, Any] | None = None,
    owner_session_root: Path = OWNER_SESSION_ROOT,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _result("measurement_cohort_binding_schema_invalid")
    required = {"schema", "status", "generated_at_utc", "expires_at_utc", "cohort", "handoff", "job", "calibration", "authorization", "active_worktree", "route", "authority_boundary"}
    if set(payload) != required or payload.get("schema") != SCHEMA or payload.get("status") != "ok":
        return _result("measurement_cohort_binding_schema_invalid")
    try:
        generated = _parse_time(payload["generated_at_utc"])
        expires = _parse_time(payload["expires_at_utc"])
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        current = current.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return _result("measurement_cohort_binding_expiry_invalid")
    if generated > current or expires <= generated or expires - generated > MAX_TTL or expires <= current:
        return _result("measurement_cohort_binding_expired")
    cohort = _as_dict(payload.get("cohort"))
    handoff = _as_dict(payload.get("handoff"))
    job = _as_dict(payload.get("job"))
    calibration = _as_dict(payload.get("calibration"))
    authorization = _as_dict(payload.get("authorization"))
    route = _as_dict(payload.get("route"))
    boundary = _as_dict(payload.get("authority_boundary"))
    expected_route = {"execution_backend": "persistent_isolated_agent", "model_path": TERRA_MODEL, "thinking": "low", "agent_id": AGENT_ID, "persistent_lane_mode": LANE_MODE}
    expected_boundary = {"measurement_only": True, "protected_dispatch_binding_created": False, "usage_receipt_created": False, "cohort_credit_granted": False, "config_auth_runtime_mutation_allowed": False, "finance_canon_portfolio_or_execution_authority": False, "external_delivery_allowed": False, "owner_approval_inferred": False}
    if route != expected_route or boundary != expected_boundary:
        return _result("measurement_cohort_binding_route_or_authority_invalid")
    manifest, manifest_hash, error = _read_frozen_source(
        cohort.get("manifest_reference"),
        expected_reference=COHORT_MANIFEST_REFERENCE,
        expected_sha256=COHORT_MANIFEST_SHA256,
        root=root,
    )
    if error or cohort.get("cohort_id") != COHORT_ID or cohort.get("manifest_sha256") != manifest_hash:
        return _result(error or "measurement_cohort_binding_manifest_hash_mismatch")
    handoff_source, handoff_hash, error = _read_frozen_source(
        handoff.get("reference"),
        expected_reference=HANDOFF_REFERENCE,
        expected_sha256=HANDOFF_SHA256,
        root=root,
    )
    if error or handoff.get("sha256") != handoff_hash:
        return _result(error or "measurement_cohort_binding_handoff_hash_mismatch")
    selected_job_id = job.get("job_id") if isinstance(job.get("job_id"), str) else ""
    contract, error = _source_contract(
        manifest or {},
        handoff_source or {},
        selected_job_id=selected_job_id,
        handoff_reference=handoff.get("reference") if isinstance(handoff.get("reference"), str) else None,
    )
    if error:
        return _result(error)
    if (
        handoff.get("frozen_snapshot_id") != contract["frozen_snapshot_id"]
        or handoff.get("contract_sha256") != contract["contract_sha256"]
        or job.get("job_number") != contract["job_number"]
        or job.get("job_id") != contract["job_id"]
        or job.get("allowed_write_paths") != contract["allowed_write_paths"]
        or job.get("source_file_hashes") != contract["source_file_hashes"]
    ):
        return _result("measurement_cohort_binding_frozen_contract_mismatch")
    if _current_source_hashes(contract, root=root) != contract["source_file_hashes"]:
        return _result("measurement_cohort_binding_source_hash_mismatch")
    calibration_source, calibration_hash, error = _read_json_reference(calibration.get("reference"), root=root)
    if (
        error
        or calibration.get("sha256") != calibration_hash
        or calibration.get("job_id") != contract["calibration_job_id"]
        or calibration.get("changed_paths")
        != contract["calibration_allowed_write_paths"]
    ):
        return _result(error or "measurement_cohort_binding_calibration_hash_mismatch")
    error = _validate_calibration(calibration_source or {}, contract, now=now)
    if error:
        return _result(error)
    strict_check = _strict_calibration_check(
        calibration["reference"],
        root=root,
        injected_check=strict_calibration_check,
    )
    strict_projection = _calibration_projection(strict_check)
    if (
        not _strict_calibration_projection_valid(strict_projection, contract)
        or calibration.get("strict_projection") != strict_projection
    ):
        return _result("measurement_cohort_binding_calibration_strict_invalid")
    try:
        if expires > _parse_time((calibration_source or {}).get("expires_at_utc")):
            return _result("measurement_cohort_binding_calibration_expiry_insufficient")
    except (TypeError, ValueError):
        return _result("measurement_cohort_binding_calibration_strict_invalid")
    authorization_contract = {
        **contract,
        "calibration_proof_reference": calibration.get("reference"),
        "calibration_proof_sha256": calibration_hash,
    }
    current_authorization, error = _resolve_authorization(
        authorization.get("reference"),
        authorization_contract,
        now=now,
        session_root=owner_session_root,
    )
    if error:
        return _result(error)
    if authorization != current_authorization:
        return _result("measurement_cohort_binding_authorization_source_drift")
    try:
        if expires > _parse_time(current_authorization["expires_at_utc"]):
            return _result("measurement_cohort_binding_authorization_expiry_insufficient")
    except (TypeError, ValueError):
        return _result("measurement_cohort_binding_authorization_source_drift")
    state = active_state if active_state is not None else collect_active_worktree_state()
    if state is None:
        return _result("measurement_cohort_binding_active_worktree_invalid")
    if (
        state.get("job_id") != contract["job_id"]
        or state.get("allowed_write_paths") != contract["allowed_write_paths"]
        or state.get("source_file_hashes") != contract["source_file_hashes"]
    ):
        return _result("measurement_cohort_binding_active_worktree_drift")
    if state != payload.get("active_worktree"):
        return _result("measurement_cohort_binding_active_worktree_drift")
    return {
        "status": "ok",
        "code": "ok",
        "cohort_id": COHORT_ID,
        "job_id": contract["job_id"],
        "job_number": contract["job_number"],
        "allowed_write_paths": list(contract["allowed_write_paths"]),
        "calibration_proof_reference": calibration["reference"],
        "calibration_job_id": calibration["job_id"],
        "calibration_allowed_write_paths": list(calibration["changed_paths"]),
        "route": dict(route),
        "expires_at_utc": payload["expires_at_utc"],
    }


def inspect_binding_reference(
    reference: Any,
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    owner_session_root: Path = OWNER_SESSION_ROOT,
) -> dict[str, Any]:
    payload, _, error = _read_json_reference(reference, root=root)
    if error:
        return _result(error)
    return validate_binding_payload(payload, root=root, now=now, owner_session_root=owner_session_root)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-manifest", required=True)
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--calibration-proof", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--job-id", default=JOB_ID)
    parser.add_argument("--out")
    parser.add_argument("--ttl-minutes", type=int, default=60)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    ttl = timedelta(minutes=args.ttl_minutes)
    binding = build_binding(
        cohort_manifest_reference=args.cohort_manifest,
        handoff_reference=args.handoff,
        calibration_proof_reference=args.calibration_proof,
        authorization_reference=args.authorization,
        job_id=args.job_id,
        ttl=ttl,
    )
    if binding.get("status") == "ok" and args.write:
        out_path = _evidence_path(args.out, root=ROOT)
        if out_path is None:
            binding = _result("measurement_cohort_binding_output_path_invalid")
        else:
            _write_json(out_path, binding)
    if binding.get("status") == "ok" and args.validate:
        binding["validation"] = validate_binding_payload(binding)
        if binding["validation"].get("status") != "ok":
            binding["status"] = "error"
            binding["code"] = binding["validation"].get("code")
    print(json.dumps(binding, indent=2, sort_keys=True))
    return 0 if binding.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
