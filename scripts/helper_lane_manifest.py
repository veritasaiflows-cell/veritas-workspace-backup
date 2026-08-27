#!/usr/bin/env python3
"""Build and revalidate frozen helper-lane handoff manifests.

Version 3 adds a transport-safe attachment contract: raw UTF-8 source files,
per-file and physical-line limits, receiver readback, and an explicit
patch-draft/Main-application closeout distinction.  The manifest routes
proof; it does not spawn helpers or grant mutation, approval, or execution
authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "helper-lane-active-manifest.json"

SCHEMA = "veritas.helper_lane_manifest.v3"
PREVIOUS_SCHEMA = "veritas.helper_lane_manifest.v2"
LEGACY_SCHEMA = "veritas.helper_lane_manifest.v1"
CONTRACT_VERSION = 3
TOKEN_ESTIMATOR = "utf8_bytes_div4_ceiling_v1"
DEFAULT_MAX_FILES = 6
DEFAULT_MAX_TOTAL_BYTES = 120_000
DEFAULT_MAX_CONTEXT_TOKENS = 30_000
DEFAULT_INCIDENT_SLA_SECONDS = 90
DEFAULT_MAX_ATTACHMENT_BYTES = 40_000
DEFAULT_MAX_ATTACHMENT_LINE_BYTES = 40_000
RAW_UTF8_ATTACHMENT_FORMAT = "raw_utf8_per_source_file.v1"
RECEIVER_READBACK_SCHEMA = "veritas.helper_lane_receiver_readback.v1"
DELIVERY_MODE_PATCH_DRAFT = "patch_draft"
DELIVERY_MODE_SCOPED_WORKTREE_IMPLEMENTATION = "scoped_worktree_implementation"
SUPPORTED_DELIVERY_MODES = {
    DELIVERY_MODE_PATCH_DRAFT,
    DELIVERY_MODE_SCOPED_WORKTREE_IMPLEMENTATION,
}
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
FILE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_APPLIED_DIFF_ARTIFACT_BYTES = 1_000_000
QA_VALIDATION_EXECUTABLES = {
    "python", "python.exe", "pytest", "go", "npm", "node", "dotnet", "cargo", "ruff", "mypy", "openclaw",
}

TERMINAL_STATUSES = {"completed", "abandoned", "canceled", "timed_out", "failed"}
NON_TERMINAL_STATUSES = {"pending", "running"}
ALLOWED_STATUSES = TERMINAL_STATUSES | NON_TERMINAL_STATUSES
INCIDENT_STATUSES = {"timed_out", "failed"}

AUTHORITY_BOUNDARY = {
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    timespec = "microseconds" if normalized.microsecond else "seconds"
    return normalized.isoformat(timespec=timespec).replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(value: str | None, default: Path | None = None) -> Path:
    if not value:
        if default is None:
            raise SystemExit("path value missing")
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def estimated_tokens(size_bytes: int) -> int:
    return (size_bytes + 3) // 4


def normalize_base_path(value: str, root: Path = ROOT) -> tuple[str, Path]:
    original = str(value or "").strip()
    raw = original.replace("\\", "/")
    if not raw:
        raise ValueError("base_path_missing")
    posix = PurePosixPath(raw)
    if Path(original).is_absolute() or posix.is_absolute() or posix.drive or (posix.parts and posix.parts[0].endswith(":")) or ".." in posix.parts:
        raise ValueError("base_path_must_be_workspace_relative")
    candidate = (root / Path(*posix.parts)).resolve(strict=True)
    root_resolved = root.resolve(strict=True)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("base_path_escapes_workspace") from exc
    if not candidate.is_dir():
        raise ValueError("base_path_not_directory")
    return candidate.relative_to(root_resolved).as_posix() or ".", candidate


def normalize_context_path(value: str, base: Path, root: Path = ROOT) -> tuple[str, Path]:
    original = str(value or "").strip()
    raw = original.replace("\\", "/")
    if not raw:
        raise ValueError("context_path_missing")
    posix = PurePosixPath(raw)
    if Path(original).is_absolute() or posix.is_absolute() or posix.drive or (posix.parts and posix.parts[0].endswith(":")) or ".." in posix.parts:
        raise ValueError(f"context_path_not_base_relative:{raw}")
    candidate = (base / Path(*posix.parts)).resolve(strict=True)
    try:
        candidate.relative_to(base.resolve(strict=True))
        candidate.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"context_path_escapes_base:{raw}") from exc
    if not candidate.is_file():
        raise ValueError(f"context_path_not_file:{raw}")
    return candidate.relative_to(base.resolve(strict=True)).as_posix(), candidate


def parse_artifact(value: str) -> dict[str, Any]:
    raw_path, separator, suffix = value.rpartition(":")
    if separator and suffix.strip().lower() in {"file", "json"}:
        path_value = raw_path.strip()
        kind = suffix.strip().lower()
    else:
        path_value = value.strip()
        kind = "file"
    if not path_value:
        raise SystemExit("artifact path missing")
    return {"path": path_value.replace("\\", "/"), "kind": kind}


def transport_attachment_observation(path: Path, relative: str) -> tuple[dict[str, Any], list[str]]:
    """Inspect a v3 source attachment before it reaches an isolated reader.

    The original retry sequence showed that a successful tiny nonce is not a
    payload capability proof.  This intentionally rejects compressed/bundled
    source shapes and any file or physical line above the conservative reader
    cap before a model attempt is dispatched.
    """
    raw = path.read_bytes()
    errors: list[str] = []
    suffix = path.suffix.casefold()
    compressed = suffix in {".gz", ".gzip", ".zip", ".bz2", ".xz"} or raw.startswith(
        (b"\x1f\x8b", b"PK\x03\x04", b"BZh", b"\xfd7zXZ")
    )
    if compressed:
        errors.append(f"attachment_decode_unsupported:{relative}")
    if len(raw) > DEFAULT_MAX_ATTACHMENT_BYTES:
        errors.append(f"attachment_reader_limit:{relative}:file_bytes")
    try:
        decoded = raw.decode("utf-8", errors="strict")
        line_lengths = [len(line.encode("utf-8")) for line in decoded.splitlines()]
        max_line_bytes = max(line_lengths, default=0)
        utf8 = True
    except UnicodeDecodeError:
        max_line_bytes = None
        utf8 = False
        errors.append(f"attachment_source_readback_failed:{relative}:utf8_required")
    if max_line_bytes is not None and max_line_bytes > DEFAULT_MAX_ATTACHMENT_LINE_BYTES:
        errors.append(f"attachment_reader_limit:{relative}:physical_line_bytes")
    return {
        "attachment_format": RAW_UTF8_ATTACHMENT_FORMAT,
        "utf8": utf8,
        "compressed_or_bundle": compressed,
        "max_physical_line_bytes": max_line_bytes,
    }, errors


def v3_transport_contract(delivery_mode: str) -> dict[str, Any]:
    if delivery_mode not in SUPPORTED_DELIVERY_MODES:
        raise ValueError("delivery_mode_invalid")
    return {
        "delivery_mode": delivery_mode,
        "attachment_format": RAW_UTF8_ATTACHMENT_FORMAT,
        "one_source_file_per_attachment": True,
        "max_attachment_bytes": DEFAULT_MAX_ATTACHMENT_BYTES,
        "max_physical_line_bytes": DEFAULT_MAX_ATTACHMENT_LINE_BYTES,
        "compression_or_aggregate_bundle_allowed": False,
        "receiver_readback_required": True,
        "shared_workspace_writeback_verified": False,
    }


def build_handoff(
    base_path: str,
    context_files: list[str],
    max_files: int = DEFAULT_MAX_FILES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    root: Path = ROOT,
    contract_version: int = CONTRACT_VERSION,
    delivery_mode: str = DELIVERY_MODE_PATCH_DRAFT,
) -> dict[str, Any]:
    if contract_version not in {2, CONTRACT_VERSION}:
        raise ValueError("contract_version_unsupported")
    normalized_base, base = normalize_base_path(base_path, root)
    if not context_files:
        raise ValueError("context_files_missing")
    if min(max_files, max_total_bytes, max_context_tokens) < 1:
        raise ValueError("context_budget_must_be_positive")
    if max_files > DEFAULT_MAX_FILES:
        raise ValueError("max_files_exceeds_hard_ceiling")
    if max_total_bytes > DEFAULT_MAX_TOTAL_BYTES:
        raise ValueError("max_total_bytes_exceeds_hard_ceiling")
    if max_context_tokens > DEFAULT_MAX_CONTEXT_TOKENS:
        raise ValueError("max_context_tokens_exceeds_hard_ceiling")

    records: list[dict[str, Any]] = []
    transport_errors: list[str] = []
    seen: set[str] = set()
    for raw in context_files:
        relative, path = normalize_context_path(raw, base, root)
        folded = relative.casefold()
        if folded in seen:
            raise ValueError(f"context_path_duplicate:{relative}")
        seen.add(folded)
        size = path.stat().st_size
        records.append({"path": relative, "size_bytes": size, "sha256": file_hash(path), "_path": path})
    records.sort(key=lambda row: str(row["path"]).casefold())
    if contract_version == CONTRACT_VERSION:
        for index, record in enumerate(records, start=1):
            observation, errors = transport_attachment_observation(record["_path"], str(record["path"]))
            transport_errors.extend(errors)
            record.update({"attachment_id": f"source-{index:02d}", **observation})
    for record in records:
        record.pop("_path", None)

    total_bytes = sum(int(row["size_bytes"]) for row in records)
    observed = {
        "file_count": len(records),
        "total_bytes": total_bytes,
        "estimated_context_tokens": estimated_tokens(total_bytes),
    }
    budget = {
        "max_files": max_files,
        "max_total_bytes": max_total_bytes,
        "max_context_tokens": max_context_tokens,
        "token_estimator": TOKEN_ESTIMATOR,
    }
    errors: list[str] = list(transport_errors)
    if observed["file_count"] > max_files:
        errors.append("context_file_budget_exceeded")
    if observed["total_bytes"] > max_total_bytes:
        errors.append("context_byte_budget_exceeded")
    if observed["estimated_context_tokens"] > max_context_tokens:
        errors.append("context_token_budget_exceeded")

    immutable: dict[str, Any] = {
        "contract_version": contract_version,
        "base_path": normalized_base,
        "budget": budget,
        "files": records,
    }
    if contract_version == CONTRACT_VERSION:
        immutable["transport"] = v3_transport_contract(delivery_mode)
    frozen_snapshot_id = canonical_hash(immutable)
    contract_sha256 = canonical_hash({**immutable, "frozen_snapshot_id": frozen_snapshot_id})
    checks = [
        {"name": "explicit_base_path", "ok": True},
        {"name": "context_files_resolve_inside_base", "ok": True},
        {"name": "context_file_budget", "ok": observed["file_count"] <= max_files},
        {"name": "context_byte_budget", "ok": observed["total_bytes"] <= max_total_bytes},
        {"name": "context_token_budget", "ok": observed["estimated_context_tokens"] <= max_context_tokens},
    ]
    if contract_version == CONTRACT_VERSION:
        checks.extend([
            {"name": "raw_utf8_source_attachments", "ok": not any("utf8_required" in item for item in transport_errors)},
            {"name": "compressed_or_aggregate_attachments_rejected", "ok": not any("attachment_decode_unsupported" in item for item in transport_errors)},
            {"name": "attachment_reader_limits", "ok": not any("attachment_reader_limit" in item for item in transport_errors)},
            {"name": "receiver_readback_required", "ok": True},
        ])
    preflight = {
        "status": "ok" if not errors else "blocked",
        "checks": checks,
        "errors": errors,
    }
    preflight["fingerprint"] = canonical_hash(preflight)
    return {
        **immutable,
        "observed": observed,
        "frozen_snapshot_id": frozen_snapshot_id,
        "contract_sha256": contract_sha256,
        "preflight": preflight,
    }


def build_attempt(
    lane_id: str,
    snapshot_id: str,
    attempt_number: int,
    started_at_utc: str,
    previous_attempt_id: str,
    failure_class: str,
    retry_reason: str,
) -> dict[str, Any]:
    if attempt_number < 1:
        raise ValueError("attempt_number_must_be_positive")
    if attempt_number > 1:
        if not previous_attempt_id.strip():
            raise ValueError("retry_previous_attempt_id_missing")
        if not failure_class.strip():
            raise ValueError("retry_failure_class_missing")
        if not retry_reason.strip():
            raise ValueError("retry_reason_missing")
    identity = {
        "lane_id": lane_id,
        "frozen_snapshot_id": snapshot_id,
        "attempt_number": attempt_number,
        "previous_attempt_id": previous_attempt_id.strip() or None,
        "attempt_started_at_utc": started_at_utc,
        "failure_class": failure_class.strip() or None,
        "retry_reason": retry_reason.strip() or None,
    }
    return {
        "attempt_number": attempt_number,
        "retry_count": attempt_number - 1,
        "is_first_attempt": attempt_number == 1,
        "attempt_id": canonical_hash(identity),
        "previous_attempt_id": previous_attempt_id.strip() or None,
        "attempt_started_at_utc": started_at_utc,
        "failure_class": failure_class.strip() or None,
        "retry_reason": retry_reason.strip() or None,
    }


def validate_receiver_readback(handoff: dict[str, Any], proof: Any) -> dict[str, Any]:
    """Validate a receiver's readback of the actual frozen v3 attachments.

    This is deliberately a proof of the sent source files, not merely a nonce
    or a claim that transport exists.  Session/run references are hashed so the
    manifest can remain privacy-safe while still tying proof to one attempt.
    """
    errors: list[str] = []
    if int(handoff.get("contract_version") or 0) != CONTRACT_VERSION:
        return {"status": "not_applicable", "errors": [], "warnings": ["receiver_readback_not_required_for_compatibility_contract"]}
    if not isinstance(proof, dict):
        return {"status": "blocked", "errors": ["attachment_source_readback_failed:proof_missing"], "warnings": []}
    if proof.get("schema") != RECEIVER_READBACK_SCHEMA:
        errors.append("attachment_source_readback_failed:proof_schema_invalid")
    if proof.get("status") != "ok":
        errors.append("attachment_source_readback_failed:proof_status_not_ok")
    if proof.get("frozen_snapshot_id") != handoff.get("frozen_snapshot_id"):
        errors.append("attachment_source_readback_failed:frozen_snapshot_mismatch")
    for field in ("receiver_session_ref_sha256", "receiver_run_ref_sha256"):
        if not SHA256_REF_RE.fullmatch(str(proof.get(field) or "")):
            errors.append(f"attachment_source_readback_failed:{field}_invalid")
    expected = {
        str(row.get("attachment_id") or ""): row
        for row in handoff.get("files", [])
        if isinstance(row, dict)
    }
    observed_rows = proof.get("attachments")
    if not isinstance(observed_rows, list):
        errors.append("attachment_source_readback_failed:attachments_missing")
        observed_rows = []
    observed: dict[str, dict[str, Any]] = {}
    for row in observed_rows:
        if not isinstance(row, dict):
            errors.append("attachment_source_readback_failed:attachment_row_invalid")
            continue
        attachment_id = str(row.get("attachment_id") or "")
        if not attachment_id or attachment_id in observed:
            errors.append("attachment_source_readback_failed:attachment_id_invalid_or_duplicate")
            continue
        observed[attachment_id] = row
    if set(observed) != set(expected):
        errors.append("attachment_source_readback_failed:attachment_inventory_mismatch")
    for attachment_id, expected_row in expected.items():
        actual = observed.get(attachment_id, {})
        for field in ("path", "size_bytes", "sha256", "max_physical_line_bytes"):
            if actual.get(field) != expected_row.get(field):
                errors.append(f"attachment_source_readback_failed:{attachment_id}:{field}_mismatch")
        if actual.get("readback_status") != "ok":
            errors.append(f"attachment_source_readback_failed:{attachment_id}:status_not_ok")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []}


def normalize_proof_relative_path(value: Any) -> tuple[str | None, str | None]:
    """Normalize a logical proof path without allowing an escape sequence."""
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None, "path_missing"
    parsed = PurePosixPath(raw)
    if Path(raw).is_absolute() or parsed.is_absolute() or parsed.drive or (parsed.parts and parsed.parts[0].endswith(":")) or ".." in parsed.parts:
        return None, "path_not_workspace_relative"
    parts = [part for part in parsed.parts if part not in {"", "."}]
    if not parts:
        return None, "path_missing"
    return "/".join(parts), None


def proof_artifact_path(value: Any, root: Path = ROOT) -> tuple[Path | None, str | None]:
    """Resolve a proof artifact inside the workspace and require a real file."""
    relative, error = normalize_proof_relative_path(value)
    if error:
        return None, error
    try:
        candidate = (root / Path(*PurePosixPath(str(relative)).parts)).resolve(strict=True)
        candidate.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None, "artifact_escapes_or_missing"
    if not candidate.is_file():
        return None, "artifact_not_file"
    return candidate, None


def _normalized_path_list(value: Any, prefix: str) -> tuple[list[str], list[str]]:
    if not isinstance(value, list) or not value:
        return [], [f"{prefix}_missing"]
    values: list[str] = []
    errors: list[str] = []
    for item in value:
        normalized, error = normalize_proof_relative_path(item)
        if error:
            errors.append(f"{prefix}_{error}")
            continue
        if normalized in values:
            errors.append(f"{prefix}_duplicate")
            continue
        values.append(str(normalized))
    return values, errors


def unified_diff_changed_paths(raw: bytes) -> tuple[list[str], list[str]]:
    """Read only standard `diff --git a/path b/path` headers, fail closed otherwise."""
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return [], ["diff_artifact_utf8_required"]
    paths: list[str] = []
    errors: list[str] = []
    for line in text.splitlines():
        if not line.startswith("diff --git "):
            continue
        fields = line.split()
        if len(fields) != 4:
            errors.append("diff_artifact_header_invalid")
            continue
        for raw_path in fields[2:]:
            if raw_path == "/dev/null":
                continue
            if not raw_path.startswith(("a/", "b/")):
                errors.append("diff_artifact_header_path_invalid")
                continue
            normalized, error = normalize_proof_relative_path(raw_path[2:])
            if error:
                errors.append(f"diff_artifact_{error}")
                continue
            if normalized not in paths:
                paths.append(str(normalized))
    if not paths:
        errors.append("diff_artifact_changed_paths_missing")
    return sorted(paths), errors


def validate_frozen_handoff_metadata(handoff: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Validate the immutable handoff record without rereading post-apply files."""
    errors: list[str] = []
    try:
        contract_version = int(handoff.get("contract_version") or 0)
    except (TypeError, ValueError):
        contract_version = 0
    if contract_version not in {2, CONTRACT_VERSION}:
        return ["handoff_contract_version_invalid"]
    try:
        normalized_base, _ = normalize_base_path(str(handoff.get("base_path") or ""), root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    if handoff.get("base_path") != normalized_base:
        errors.append("handoff_base_path_not_normalized")
    budget = handoff.get("budget") if isinstance(handoff.get("budget"), dict) else {}
    try:
        max_files = int(budget.get("max_files", 0))
        max_total_bytes = int(budget.get("max_total_bytes", 0))
        max_context_tokens = int(budget.get("max_context_tokens", 0))
        if min(max_files, max_total_bytes, max_context_tokens) < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("handoff_budget_invalid")
        max_files = max_total_bytes = max_context_tokens = 0
    files = handoff.get("files")
    if not isinstance(files, list) or not files:
        return errors + ["handoff_files_missing"]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in files:
        if not isinstance(row, dict):
            errors.append("handoff_file_row_invalid")
            continue
        path, path_error = normalize_proof_relative_path(row.get("path"))
        if path_error or path != row.get("path"):
            errors.append("handoff_file_path_invalid")
            continue
        if path.casefold() in seen:
            errors.append("handoff_file_path_duplicate")
            continue
        seen.add(path.casefold())
        size = row.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append("handoff_file_size_invalid")
        if not FILE_SHA256_RE.fullmatch(str(row.get("sha256") or "")):
            errors.append("handoff_file_sha256_invalid")
        rows.append(row)
    if rows != sorted(rows, key=lambda item: str(item.get("path") or "").casefold()):
        errors.append("handoff_files_not_sorted")
    total_bytes = sum(int(row.get("size_bytes", 0)) for row in rows if isinstance(row.get("size_bytes"), int))
    observed = {
        "file_count": len(rows),
        "total_bytes": total_bytes,
        "estimated_context_tokens": estimated_tokens(total_bytes),
    }
    if handoff.get("observed") != observed:
        errors.append("handoff_observed_mismatch")
    immutable: dict[str, Any] = {
        "contract_version": contract_version,
        "base_path": normalized_base,
        "budget": budget,
        "files": files,
    }
    if contract_version == CONTRACT_VERSION:
        transport = handoff.get("transport") if isinstance(handoff.get("transport"), dict) else {}
        delivery_mode = str(transport.get("delivery_mode") or "")
        try:
            expected_transport = v3_transport_contract(delivery_mode)
        except ValueError:
            errors.append("handoff_transport_invalid")
        else:
            if transport != expected_transport:
                errors.append("handoff_transport_mismatch")
            immutable["transport"] = transport
    expected_snapshot = canonical_hash(immutable)
    expected_contract = canonical_hash({**immutable, "frozen_snapshot_id": expected_snapshot})
    if handoff.get("frozen_snapshot_id") != expected_snapshot:
        errors.append("handoff_frozen_snapshot_id_mismatch")
    if handoff.get("contract_sha256") != expected_contract:
        errors.append("handoff_contract_sha256_mismatch")
    preflight = handoff.get("preflight") if isinstance(handoff.get("preflight"), dict) else {}
    preflight_without_fingerprint = {key: value for key, value in preflight.items() if key != "fingerprint"}
    if preflight.get("fingerprint") != canonical_hash(preflight_without_fingerprint):
        errors.append("handoff_preflight_mismatch")
    if preflight.get("status") != "ok":
        errors.append("handoff_preflight_not_ok")
    return errors


def validate_post_apply_file_state(lane: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Bind a completed patch draft to the actual post-apply workspace files."""
    issues: list[str] = []
    handoff = lane.get("handoff") if isinstance(lane.get("handoff"), dict) else {}
    main_application = lane.get("main_application") if isinstance(lane.get("main_application"), dict) else {}
    try:
        _, base = normalize_base_path(str(handoff.get("base_path") or ""), root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    frozen_rows = {
        str(row.get("path") or ""): row
        for row in handoff.get("files", [])
        if isinstance(row, dict)
    }
    changed_paths, path_errors = _normalized_path_list(main_application.get("changed_paths"), "main_applied_after_draft:changed_paths")
    issues.extend(path_errors)
    changed_rows = main_application.get("changed_files")
    if not isinstance(changed_rows, list) or not changed_rows:
        return issues + ["main_applied_after_draft:changed_files_missing"]
    actual_rows: dict[str, dict[str, Any]] = {}
    for row in changed_rows:
        if not isinstance(row, dict):
            issues.append("main_applied_after_draft:changed_file_row_invalid")
            continue
        path, error = normalize_proof_relative_path(row.get("path"))
        if error:
            issues.append(f"main_applied_after_draft:changed_file_{error}")
            continue
        if path in actual_rows:
            issues.append("main_applied_after_draft:changed_file_duplicate")
            continue
        actual_rows[str(path)] = row
    if set(actual_rows) != set(changed_paths):
        issues.append("main_applied_after_draft:changed_files_paths_mismatch")
    for path, row in actual_rows.items():
        frozen = frozen_rows.get(path)
        if frozen is None:
            issues.append(f"main_applied_after_draft:changed_file_outside_frozen_scope:{path}")
            continue
        if row.get("before_sha256") != frozen.get("sha256") or row.get("before_size_bytes") != frozen.get("size_bytes"):
            issues.append(f"main_applied_after_draft:changed_file_before_mismatch:{path}")
        after_hash = str(row.get("after_sha256") or "")
        after_size = row.get("after_size_bytes")
        if not FILE_SHA256_RE.fullmatch(after_hash) or not isinstance(after_size, int) or isinstance(after_size, bool) or after_size < 0:
            issues.append(f"main_applied_after_draft:changed_file_after_invalid:{path}")
            continue
        try:
            actual_path = (base / Path(*PurePosixPath(path).parts)).resolve(strict=True)
            actual_path.relative_to(base.resolve(strict=True))
        except (OSError, ValueError):
            issues.append(f"main_applied_after_draft:changed_file_missing_or_escaping:{path}")
            continue
        if actual_path.stat().st_size != after_size or file_hash(actual_path) != after_hash:
            issues.append(f"main_applied_after_draft:changed_file_post_apply_mismatch:{path}")
        if after_hash == str(frozen.get("sha256") or "") and after_size == frozen.get("size_bytes"):
            issues.append(f"main_applied_after_draft:changed_file_noop:{path}")
    for path, frozen in frozen_rows.items():
        if path in actual_rows:
            continue
        try:
            actual_path = (base / Path(*PurePosixPath(path).parts)).resolve(strict=True)
            actual_path.relative_to(base.resolve(strict=True))
        except (OSError, ValueError):
            issues.append(f"main_applied_after_draft:unchanged_file_missing_or_escaping:{path}")
            continue
        if actual_path.stat().st_size != frozen.get("size_bytes") or file_hash(actual_path) != frozen.get("sha256"):
            issues.append(f"main_applied_after_draft:unchanged_file_mutated:{path}")
    return issues


def v3_completion_proof_issues(lane: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Validate evidence that Main applied, and QA tested, an actual draft diff.

    This is intentionally stricter than a self-attested status flag.  The
    applied diff must be a concrete, hash-matched workspace artifact, every
    changed path must stay inside the frozen input scope, and a separately
    hash-matched QA result must attest to that exact diff and path set.
    """
    issues: list[str] = []
    handoff = lane.get("handoff") if isinstance(lane.get("handoff"), dict) else {}
    if int(handoff.get("contract_version") or 0) != CONTRACT_VERSION:
        return ["v3_closeout:handoff_contract_invalid"]
    transport = handoff.get("transport") if isinstance(handoff.get("transport"), dict) else {}
    if transport.get("delivery_mode") != DELIVERY_MODE_PATCH_DRAFT:
        return ["scoped_writeback_unproven"]
    snapshot = handoff.get("frozen_snapshot_id")
    frozen_paths, frozen_errors = _normalized_path_list(
        [row.get("path") for row in handoff.get("files", []) if isinstance(row, dict)],
        "frozen_source_paths",
    )
    issues.extend(frozen_errors)
    frozen_set = set(frozen_paths)

    main_application = lane.get("main_application") if isinstance(lane.get("main_application"), dict) else {}
    qa = lane.get("qa_applied_diff") if isinstance(lane.get("qa_applied_diff"), dict) else {}
    if main_application.get("schema") != "veritas.main_applied_diff.v1":
        issues.append("main_applied_after_draft:proof_schema_invalid")
    if main_application.get("status") != "ok" or main_application.get("main_application_result") != "applied":
        issues.append("main_applied_after_draft:status_not_applied")
    if main_application.get("frozen_snapshot_id") != snapshot:
        issues.append("main_applied_after_draft:frozen_snapshot_mismatch")
    if main_application.get("delivery_mode") != DELIVERY_MODE_PATCH_DRAFT:
        issues.append("main_applied_after_draft:delivery_mode_invalid")
    if main_application.get("main_verified") is not True:
        issues.append("main_applied_after_draft:main_verification_missing")

    allowed_paths, allowed_errors = _normalized_path_list(main_application.get("allowed_paths"), "main_applied_after_draft:allowed_paths")
    issues.extend(allowed_errors)
    for path in allowed_paths:
        if path not in frozen_set:
            issues.append(f"main_applied_after_draft:allowed_path_outside_frozen_scope:{path}")

    diff_hash = str(main_application.get("applied_diff_sha256") or "")
    if not SHA256_REF_RE.fullmatch(diff_hash):
        issues.append("main_applied_after_draft:applied_diff_sha256_invalid")
    diff_path, diff_error = proof_artifact_path(main_application.get("applied_diff_artifact"), root)
    changed_paths: list[str] = []
    if diff_error:
        issues.append(f"main_applied_after_draft:diff_artifact_{diff_error}")
    elif diff_path is not None:
        diff_bytes = diff_path.read_bytes()
        if len(diff_bytes) > MAX_APPLIED_DIFF_ARTIFACT_BYTES:
            issues.append("main_applied_after_draft:diff_artifact_too_large")
        actual_hash = "sha256:" + hashlib.sha256(diff_bytes).hexdigest()
        if actual_hash != diff_hash:
            issues.append("main_applied_after_draft:applied_diff_hash_not_artifact")
        changed_paths, diff_errors = unified_diff_changed_paths(diff_bytes)
        issues.extend(f"main_applied_after_draft:{item}" for item in diff_errors)
        for path in changed_paths:
            if path not in set(allowed_paths):
                issues.append(f"main_applied_after_draft:diff_path_outside_allowed_scope:{path}")
    asserted_paths, asserted_errors = _normalized_path_list(main_application.get("changed_paths"), "main_applied_after_draft:changed_paths")
    issues.extend(asserted_errors)
    if changed_paths and asserted_paths and set(asserted_paths) != set(changed_paths):
        issues.append("main_applied_after_draft:changed_paths_mismatch")
    issues.extend(validate_post_apply_file_state(lane, root))

    expected_tested_files: dict[str, dict[str, Any]] = {}
    for row in main_application.get("changed_files", []):
        if isinstance(row, dict):
            path, error = normalize_proof_relative_path(row.get("path"))
            if not error and path:
                expected_tested_files[str(path)] = {
                    "after_sha256": row.get("after_sha256"),
                    "after_size_bytes": row.get("after_size_bytes"),
                }

    if qa.get("schema") != "veritas.qa_applied_diff.v1":
        issues.append("qa_applied_diff:proof_schema_invalid")
    if qa.get("status") != "ok" or qa.get("qa_target") != "actual_main_applied_diff":
        issues.append("qa_applied_diff:target_or_status_invalid")
    if qa.get("frozen_snapshot_id") != snapshot:
        issues.append("qa_applied_diff:frozen_snapshot_mismatch")
    if qa.get("applied_diff_sha256") != diff_hash:
        issues.append("qa_applied_diff:applied_diff_hash_mismatch")
    qa_path, qa_path_error = proof_artifact_path(qa.get("qa_result_artifact"), root)
    qa_result_hash = str(qa.get("qa_result_sha256") or "")
    if not SHA256_REF_RE.fullmatch(qa_result_hash):
        issues.append("qa_applied_diff:qa_result_sha256_invalid")
    qa_result: dict[str, Any] = {}
    if qa_path_error:
        issues.append(f"qa_applied_diff:qa_result_artifact_{qa_path_error}")
    elif qa_path is not None:
        raw_result = qa_path.read_bytes()
        if "sha256:" + hashlib.sha256(raw_result).hexdigest() != qa_result_hash:
            issues.append("qa_applied_diff:qa_result_hash_not_artifact")
        try:
            parsed_result = json.loads(raw_result.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            issues.append("qa_applied_diff:qa_result_artifact_json_invalid")
        else:
            if not isinstance(parsed_result, dict):
                issues.append("qa_applied_diff:qa_result_artifact_not_object")
            else:
                qa_result = parsed_result
    if qa_result:
        if qa_result.get("schema") != "veritas.qa_applied_diff_result.v1":
            issues.append("qa_applied_diff:qa_result_schema_invalid")
        if qa_result.get("status") != "ok" or qa_result.get("qa_target") != "actual_main_applied_diff":
            issues.append("qa_applied_diff:qa_result_target_or_status_invalid")
        if qa_result.get("frozen_snapshot_id") != snapshot:
            issues.append("qa_applied_diff:qa_result_frozen_snapshot_mismatch")
        if qa_result.get("applied_diff_sha256") != diff_hash:
            issues.append("qa_applied_diff:qa_result_diff_hash_mismatch")
        tested_paths, tested_errors = _normalized_path_list(qa_result.get("tested_paths"), "qa_applied_diff:qa_result_tested_paths")
        issues.extend(tested_errors)
        if changed_paths and tested_paths and set(tested_paths) != set(changed_paths):
            issues.append("qa_applied_diff:qa_result_tested_paths_mismatch")
        tested_files = qa_result.get("tested_files")
        observed_tested_files: dict[str, dict[str, Any]] = {}
        if not isinstance(tested_files, list) or not tested_files:
            issues.append("qa_applied_diff:qa_result_tested_files_missing")
        else:
            for row in tested_files:
                if not isinstance(row, dict):
                    issues.append("qa_applied_diff:qa_result_tested_file_invalid")
                    continue
                path, error = normalize_proof_relative_path(row.get("path"))
                if error or not path or path in observed_tested_files:
                    issues.append("qa_applied_diff:qa_result_tested_file_path_invalid_or_duplicate")
                    continue
                observed_tested_files[str(path)] = {
                    "after_sha256": row.get("after_sha256"),
                    "after_size_bytes": row.get("after_size_bytes"),
                }
            if observed_tested_files != expected_tested_files:
                issues.append("qa_applied_diff:qa_result_tested_files_mismatch")
        commands = qa_result.get("commands")
        if not isinstance(commands, list) or not commands:
            issues.append("qa_applied_diff:qa_result_commands_missing")
        else:
            for command in commands:
                if not isinstance(command, dict) or not str(command.get("command") or "").strip() or command.get("exit_code") != 0:
                    issues.append("qa_applied_diff:qa_result_command_invalid")
                    break
                command_text = str(command.get("command") or "").strip()
                executable = command_text.split(maxsplit=1)[0].strip("\"'").casefold()
                if executable not in QA_VALIDATION_EXECUTABLES:
                    issues.append("qa_applied_diff:qa_result_command_not_validation_runner")
                    break
                output_hash = str(command.get("output_sha256") or "")
                if not SHA256_REF_RE.fullmatch(output_hash):
                    issues.append("qa_applied_diff:qa_result_command_output_sha256_invalid")
                    break
                output_path, output_error = proof_artifact_path(command.get("output_artifact"), root)
                if output_error:
                    issues.append(f"qa_applied_diff:qa_result_command_output_artifact_{output_error}")
                    break
                if output_path is not None:
                    output_bytes = output_path.read_bytes()
                    if "sha256:" + hashlib.sha256(output_bytes).hexdigest() != output_hash:
                        issues.append("qa_applied_diff:qa_result_command_output_hash_not_artifact")
                        break
                validated_paths, validated_path_errors = _normalized_path_list(
                    command.get("validated_paths"), "qa_applied_diff:qa_result_command_validated_paths"
                )
                if validated_path_errors or set(validated_paths) != set(changed_paths):
                    issues.append("qa_applied_diff:qa_result_command_validated_paths_mismatch")
                    break
                if command.get("validated_after_sha256") != {
                    path: row["after_sha256"] for path, row in expected_tested_files.items()
                }:
                    issues.append("qa_applied_diff:qa_result_command_after_hashes_mismatch")
                    break
            if qa.get("commands") != commands:
                issues.append("qa_applied_diff:commands_artifact_mismatch")
    return issues


def build_incident(
    required: bool,
    triggered_at_utc: str,
    update_at_utc: str,
    as_of_utc: str,
    sla_seconds: int = DEFAULT_INCIDENT_SLA_SECONDS,
) -> dict[str, Any]:
    if sla_seconds != DEFAULT_INCIDENT_SLA_SECONDS:
        raise ValueError("incident_sla_must_be_90_seconds")
    if not required and not triggered_at_utc:
        return {
            "required": False,
            "triggered_at_utc": None,
            "provisional_due_at_utc": None,
            "provisional_update_at_utc": None,
            "provisional_sla_seconds": sla_seconds,
            "latency_seconds": None,
            "sla_status": "not_applicable",
        }
    if not triggered_at_utc:
        raise ValueError("incident_triggered_at_utc_missing")
    triggered = parse_utc(triggered_at_utc, "incident_triggered_at_utc")
    due = triggered + timedelta(seconds=sla_seconds)
    update = parse_utc(update_at_utc, "incident_update_at_utc") if update_at_utc else None
    as_of = parse_utc(as_of_utc, "as_of_utc")
    if update and update < triggered:
        raise ValueError("incident_update_precedes_trigger")
    latency = (update - triggered).total_seconds() if update else None
    if update:
        status = "met" if update <= due else "breached"
    else:
        status = "pending" if as_of <= due else "breached"
    return {
        "required": required,
        "triggered_at_utc": iso_utc(triggered),
        "provisional_due_at_utc": iso_utc(due),
        "provisional_update_at_utc": iso_utc(update) if update else None,
        "provisional_sla_seconds": sla_seconds,
        "latency_seconds": latency,
        "sla_status": status,
    }


def revalidate_lane_handoff(lane: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    handoff = lane.get("handoff")
    if not isinstance(handoff, dict):
        return {"status": "blocked", "errors": ["handoff_missing"], "checks": []}
    contract_version = int(handoff.get("contract_version") or 0)
    transport = handoff.get("transport") if isinstance(handoff.get("transport"), dict) else {}
    delivery_mode = str(transport.get("delivery_mode") or DELIVERY_MODE_PATCH_DRAFT)
    main_application = lane.get("main_application") if isinstance(lane.get("main_application"), dict) else {}
    post_apply_completion = (
        contract_version == CONTRACT_VERSION
        and str(lane.get("status") or "").strip().lower() == "completed"
        and delivery_mode == DELIVERY_MODE_PATCH_DRAFT
        and main_application.get("main_application_result") == "applied"
    )
    if post_apply_completion:
        errors.extend(validate_frozen_handoff_metadata(handoff, root))
        errors.extend(validate_post_apply_file_state(lane, root))
        errors.extend(revalidate_attempt_and_incident(lane, str(handoff.get("frozen_snapshot_id") or "")))
        return {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "checks": handoff.get("preflight", {}).get("checks", []),
            "observed": handoff.get("observed"),
            "frozen_snapshot_id": handoff.get("frozen_snapshot_id"),
            "contract_sha256": handoff.get("contract_sha256"),
        }
    try:
        rebuilt = build_handoff(
            str(handoff.get("base_path") or ""),
            [str(row.get("path") or "") for row in handoff.get("files", []) if isinstance(row, dict)],
            int(handoff.get("budget", {}).get("max_files", 0)),
            int(handoff.get("budget", {}).get("max_total_bytes", 0)),
            int(handoff.get("budget", {}).get("max_context_tokens", 0)),
            root,
            contract_version,
            delivery_mode,
        )
    except (OSError, TypeError, ValueError) as exc:
        return {"status": "blocked", "errors": [str(exc)], "checks": []}
    for field in ("contract_version", "files", "observed", "frozen_snapshot_id", "contract_sha256"):
        if handoff.get(field) != rebuilt.get(field):
            errors.append(f"handoff_{field}_mismatch")
    if int(handoff.get("contract_version") or 0) == CONTRACT_VERSION and handoff.get("transport") != rebuilt.get("transport"):
        errors.append("handoff_transport_mismatch")
    if handoff.get("preflight", {}).get("status") != "ok":
        errors.append("handoff_preflight_not_ok")
    if handoff.get("preflight") != rebuilt.get("preflight"):
        errors.append("handoff_preflight_mismatch")
    if rebuilt.get("preflight", {}).get("status") != "ok":
        errors.extend(rebuilt.get("preflight", {}).get("errors", []))
    errors.extend(revalidate_attempt_and_incident(lane, str(handoff.get("frozen_snapshot_id") or "")))
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "checks": rebuilt.get("preflight", {}).get("checks", []),
        "observed": rebuilt.get("observed"),
        "frozen_snapshot_id": rebuilt.get("frozen_snapshot_id"),
        "contract_sha256": rebuilt.get("contract_sha256"),
    }


def revalidate_attempt_and_incident(lane: dict[str, Any], snapshot_id: str) -> list[str]:
    errors: list[str] = []
    attempt = lane.get("attempt") if isinstance(lane.get("attempt"), dict) else {}
    number = attempt.get("attempt_number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        return ["attempt_number_invalid"]
    started = str(attempt.get("attempt_started_at_utc") or "")
    try:
        parse_utc(started, "attempt_started_at_utc")
        expected_attempt = build_attempt(
            str(lane.get("lane_id") or ""),
            snapshot_id,
            number,
            started,
            str(attempt.get("previous_attempt_id") or ""),
            str(attempt.get("failure_class") or ""),
            str(attempt.get("retry_reason") or ""),
        )
    except ValueError as exc:
        return [str(exc)]
    for field in (
        "attempt_number",
        "retry_count",
        "is_first_attempt",
        "attempt_id",
        "previous_attempt_id",
        "attempt_started_at_utc",
        "failure_class",
        "retry_reason",
    ):
        if attempt.get(field) != expected_attempt.get(field):
            errors.append(f"attempt_{field}_mismatch")

    lane_status = str(lane.get("status") or "").strip().lower()
    incident_required = number > 1 or lane_status in INCIDENT_STATUSES
    if lane_status in INCIDENT_STATUSES and not str(attempt.get("failure_class") or "").strip():
        errors.append("attempt_failure_class_missing")
    incident = lane.get("incident") if isinstance(lane.get("incident"), dict) else {}
    if incident.get("required") is not incident_required:
        errors.append("incident_required_mismatch")
    if incident_required:
        update_at = str(incident.get("provisional_update_at_utc") or "")
        if not update_at:
            errors.append("incident_provisional_update_missing")
        else:
            try:
                rebuilt = build_incident(
                    True,
                    str(incident.get("triggered_at_utc") or ""),
                    update_at,
                    update_at,
                    int(incident.get("provisional_sla_seconds", 0)),
                )
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))
            else:
                for field in (
                    "triggered_at_utc",
                    "provisional_due_at_utc",
                    "provisional_update_at_utc",
                    "provisional_sla_seconds",
                    "latency_seconds",
                    "sla_status",
                ):
                    if incident.get(field) != rebuilt.get(field):
                        errors.append(f"incident_{field}_mismatch")
                if rebuilt.get("sla_status") != "met":
                    errors.append(f"incident_sla_{rebuilt.get('sla_status')}")
    elif incident.get("sla_status") != "not_applicable":
        errors.append("incident_unexpected_for_first_active_or_successful_attempt")
    return errors


def validate_payload(payload: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("manifest_schema_invalid_for_v3_builder")
    lanes = payload.get("expected_lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("expected_lanes_missing")
    for lane in lanes if isinstance(lanes, list) else []:
        if not isinstance(lane, dict):
            errors.append("lane_not_object")
            continue
        lane_id = str(lane.get("lane_id") or "").strip()
        status = str(lane.get("status") or "").strip().lower()
        if not lane_id:
            errors.append("lane_id_missing")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{lane_id or '<missing>'}:invalid_status:{status or '<missing>'}")
        if status == "completed" and not str(lane.get("verdict") or "").strip():
            errors.append(f"{lane_id}:completed_without_verdict")
        if lane.get("allow_partial") is True and status not in TERMINAL_STATUSES:
            errors.append(f"{lane_id}:partial_allowed_before_terminal_status")
        if not isinstance(lane.get("required_artifacts"), list):
            errors.append(f"{lane_id}:required_artifacts_not_array")
        attempt = lane.get("attempt") if isinstance(lane.get("attempt"), dict) else {}
        number = attempt.get("attempt_number")
        if not isinstance(number, int) or number < 1:
            errors.append(f"{lane_id}:attempt_number_invalid")
        elif attempt.get("retry_count") != number - 1 or attempt.get("is_first_attempt") is not (number == 1):
            errors.append(f"{lane_id}:attempt_derived_fields_mismatch")
        if isinstance(number, int) and number > 1:
            for field in ("previous_attempt_id", "failure_class", "retry_reason"):
                if not str(attempt.get(field) or "").strip():
                    errors.append(f"{lane_id}:retry_{field}_missing")
        recheck = revalidate_lane_handoff(lane, root)
        errors.extend(f"{lane_id}:{item}" for item in recheck["errors"])
        handoff = lane.get("handoff") if isinstance(lane.get("handoff"), dict) else {}
        if int(handoff.get("contract_version") or 0) != CONTRACT_VERSION:
            errors.append(f"{lane_id}:manifest_handoff_contract_version_mismatch")
        if status == "completed" and int(handoff.get("contract_version") or 0) == CONTRACT_VERSION:
            readback = validate_receiver_readback(handoff, lane.get("receiver_readback"))
            errors.extend(f"{lane_id}:{item}" for item in readback["errors"])
            errors.extend(f"{lane_id}:{item}" for item in v3_completion_proof_issues(lane, root))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if payload.get("authority_boundary", {}).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    status = str(args.status).strip().lower()
    if status in INCIDENT_STATUSES and not str(args.failure_class or "").strip():
        raise ValueError("failed_or_timed_out_attempt_failure_class_missing")
    handoff = build_handoff(
        args.base_path,
        list(args.context_file),
        args.max_files,
        args.max_total_bytes,
        args.max_context_tokens,
        delivery_mode=args.delivery_mode,
    )
    attempt = build_attempt(
        args.lane_id,
        handoff["frozen_snapshot_id"],
        args.attempt_number,
        args.started_at_utc,
        args.previous_attempt_id,
        args.failure_class,
        args.retry_reason,
    )
    incident_required = args.attempt_number > 1 or status in INCIDENT_STATUSES
    incident = build_incident(
        incident_required,
        args.incident_triggered_at_utc,
        args.incident_update_at_utc,
        args.as_of_utc,
        args.incident_sla_seconds,
    )
    lane = {
        "lane_id": args.lane_id,
        "status": status,
        "packet_id": args.packet_id,
        "session_id": args.session_id,
        "session_label": args.session_label,
        "owner_workflow": args.owner_workflow,
        "started_at_utc": args.started_at_utc,
        "updated_at_utc": utc_now(),
        "verdict": args.verdict or "",
        "required_artifacts": [parse_artifact(item) for item in args.required_artifact],
        "allow_partial": bool(args.allow_partial),
        "handoff": handoff,
        "attempt": attempt,
        "incident": incident,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "swarm_id": args.swarm_id,
        "status": "ok",
        "expected_lanes": [lane],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "use_rule": "Main blocks dispatch and synthesis unless deterministic handoff preflight and closeout revalidation pass.",
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a frozen helper-lane handoff and completion manifest.")
    parser.add_argument("--swarm-id", default="operating-leverage-helper-lanes")
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--packet-id", default="independent-qa-helper")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--session-label", default="")
    parser.add_argument("--owner-workflow", default="operating_leverage")
    parser.add_argument("--started-at-utc", default=utc_now())
    parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), required=True)
    parser.add_argument("--verdict", default="")
    parser.add_argument("--base-path", required=True, help="Workspace-relative handoff root.")
    parser.add_argument("--context-file", action="append", required=True, help="File relative to --base-path; repeat up to the budget.")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--max-context-tokens", type=int, default=DEFAULT_MAX_CONTEXT_TOKENS)
    parser.add_argument("--delivery-mode", choices=sorted(SUPPORTED_DELIVERY_MODES), default=DELIVERY_MODE_PATCH_DRAFT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--previous-attempt-id", default="")
    parser.add_argument("--failure-class", default="")
    parser.add_argument("--retry-reason", default="")
    parser.add_argument("--incident-triggered-at-utc", default="")
    parser.add_argument("--incident-update-at-utc", default="")
    parser.add_argument("--incident-sla-seconds", type=int, default=DEFAULT_INCIDENT_SLA_SECONDS)
    parser.add_argument("--as-of-utc", default=utc_now())
    parser.add_argument("--required-artifact", action="append", default=[])
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out, DEFAULT_OUT)
    try:
        payload = build_payload(args)
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "error", "errors": [str(exc)], "out": rel(out)}, indent=2, sort_keys=True))
        return 1
    if args.write:
        atomic_write_json(out, payload)
    lane = payload["expected_lanes"][0]
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "swarm_id": payload.get("swarm_id"),
        "lane_count": len(payload.get("expected_lanes", [])),
        "synthesis_status": "blocked" if args.status in NON_TERMINAL_STATUSES else "ready_for_handshake_check",
        "frozen_snapshot_id": lane["handoff"]["frozen_snapshot_id"],
        "attempt_id": lane["attempt"]["attempt_id"],
        "incident_sla_status": lane["incident"]["sla_status"],
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
