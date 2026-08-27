#!/usr/bin/env python3
"""Build and validate the canonical post-compaction resume checkpoint.

This module is a local continuity/proof surface. It projects only current
active lanes, records an explicit task cursor, and fail-closes stale or
ambiguous pickup state. It never executes the recorded command, infers owner
approval, or grants config/runtime/finance authority.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import msvcrt
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
CURRENT_RESUME = TMP / "current-resume.json"
CURRENT_ACTIVE_LANES = TMP / "current-active-lanes.json"
EXECUTION_LEDGER = TMP / "session-resume-execution-ledger.json"

SCHEMA = "veritas.session_resume_checkpoint.v1"
ACTIVE_LANES_SCHEMA = "veritas.current_active_lanes.v1"
EXECUTION_LEDGER_SCHEMA = "veritas.session_resume_execution_ledger.v1"
LANE_REGISTER_SCHEMA = "veritas.concurrent_lane_register.v1"
ACTIVE_STATUSES = {"leased", "running"}
DEFAULT_FRESHNESS_HOURS = 12.0
RESUMABLE_CHECKPOINT_STATUSES = {"in_progress", "running", "validating", "ready"}
TERMINAL_EXECUTION_RECEIPT_STATUSES = {"succeeded", "failed"}

AUTHORITY_BOUNDARY = {
    "continuity_projection_only": True,
    "executes_recorded_command": False,
    "owner_approval_inferred": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
}

PRECEDENCE = [
    "active_leased_lane_checkpoint",
    "exact_workflow_checkpoint",
    "named_workflow_continuity_note",
    "pm_queue",
    "general_status",
]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def ensure_utc(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return ensure_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ensure_utc(parsed)


def stable_hash(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def exact_command_hash(command: Any) -> str | None:
    text = str(command or "").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None


def listed_as_completed(checkpoint: dict[str, Any]) -> bool:
    """Treat the do-not-repeat list as an exact denylist, not a fuzzy prose match."""
    command = str(checkpoint.get("exact_next_command") or "").strip()
    action = str(checkpoint.get("exact_next_action") or "").strip()
    normalized = {
        str(item).strip()
        for item in as_list(checkpoint.get("already_completed_do_not_repeat"))
        if str(item).strip()
    }
    protected = {
        command,
        action,
        f"command:{command}" if command else "",
        f"action:{action}" if action else "",
    }
    return bool((normalized & protected) - {""})


def execution_receipt_content(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": receipt.get("status"),
        "checkpoint_id": receipt.get("checkpoint_id"),
        "exact_command_sha256": receipt.get("exact_command_sha256"),
        "executed_by": receipt.get("executed_by"),
        "executed_at_utc": receipt.get("executed_at_utc"),
        "proof_artifacts_and_hashes": receipt.get("proof_artifacts_and_hashes"),
    }


def checkpoint_state_content(checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Bind mutable acknowledgement/receipt state to the immutable cursor."""
    content = {
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "checkpoint_sequence": checkpoint.get("checkpoint_sequence"),
        "checkpoint_content_hash": checkpoint.get("checkpoint_content_hash"),
        "freshness_expiry": checkpoint.get("freshness_expiry"),
        "selection": checkpoint.get("selection"),
        "projection_gate": checkpoint.get("projection_gate"),
        "active_lease": checkpoint.get("active_lease"),
        "resume_acknowledgement": checkpoint.get("resume_acknowledgement"),
        "execution_receipt": checkpoint.get("execution_receipt"),
    }
    if "source_binding_sha256" in checkpoint:
        content["source"] = checkpoint.get("source")
        content["source_binding_sha256"] = checkpoint.get("source_binding_sha256")
    return content


def refresh_checkpoint_state_hash(checkpoint: dict[str, Any]) -> dict[str, Any]:
    payload = dict(checkpoint)
    payload["checkpoint_state_hash"] = stable_hash(checkpoint_state_content(payload))
    return payload


def execution_ledger_path(root: Path) -> Path:
    return root / "tmp" / EXECUTION_LEDGER.name


def execution_ledger_lock_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.lock")


@contextmanager
def execution_ledger_lock(path: Path, timeout_seconds: float = 10.0):
    """Serialize the ledger read-modify-write across Windows processes."""
    lock_path = execution_ledger_lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out acquiring execution ledger lock: {lock_path}") from exc
                time.sleep(0.05)
        try:
            yield lock_path
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def empty_execution_ledger(now: datetime | None = None) -> dict[str, Any]:
    return {
        "schema": EXECUTION_LEDGER_SCHEMA,
        "generated_at_utc": iso_utc(ensure_utc(now)),
        "records": [],
        "head_record_hash": None,
    }


def load_execution_ledger(root: Path = ROOT, path: Path | None = None) -> dict[str, Any]:
    target = path or execution_ledger_path(root)
    if not target.is_file():
        return empty_execution_ledger()
    payload = as_dict(load_json_artifact(target))
    return payload if payload else {"schema": None, "records": [], "head_record_hash": None}


def execution_ledger_record_content(record: dict[str, Any]) -> dict[str, Any]:
    content = {
        "sequence": record.get("sequence"),
        "previous_record_hash": record.get("previous_record_hash"),
        "checkpoint_id": record.get("checkpoint_id"),
        "exact_command_sha256": record.get("exact_command_sha256"),
        "receipt_content_hash": record.get("receipt_content_hash"),
        "recorded_at_utc": record.get("recorded_at_utc"),
        "proof_artifacts_and_hashes": record.get("proof_artifacts_and_hashes"),
    }
    for field in ("outcome_status", "executed_by", "executed_at_utc"):
        if field in record:
            content[field] = record.get(field)
    return content


def validate_execution_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if ledger.get("schema") != EXECUTION_LEDGER_SCHEMA:
        findings.append(active_lane_finding("session resume execution ledger schema is invalid"))
    records = ledger.get("records")
    if not isinstance(records, list):
        findings.append(active_lane_finding("session resume execution ledger records must be a list"))
        records = []
    previous_hash: str | None = None
    seen_checkpoint_ids: set[str] = set()
    for index, raw in enumerate(records, start=1):
        record = as_dict(raw)
        checkpoint_id = str(record.get("checkpoint_id") or "")
        command_hash = str(record.get("exact_command_sha256") or "")
        if record.get("sequence") != index:
            findings.append(active_lane_finding("session resume execution ledger sequence is invalid"))
        if record.get("previous_record_hash") != previous_hash:
            findings.append(active_lane_finding("session resume execution ledger chain predecessor mismatch"))
        expected_hash = stable_hash(execution_ledger_record_content(record))
        if record.get("record_hash") != expected_hash:
            findings.append(active_lane_finding("session resume execution ledger record hash mismatch"))
        if not checkpoint_id or not command_hash or checkpoint_id in seen_checkpoint_ids:
            findings.append(active_lane_finding("session resume execution ledger has a missing or duplicate receipt identity"))
        seen_checkpoint_ids.add(checkpoint_id)
        if "outcome_status" not in record:
            findings.append(active_lane_finding(
                "legacy session resume execution ledger record lacks a bound terminal outcome",
                severity="warning",
            ))
        elif record.get("outcome_status") not in TERMINAL_EXECUTION_RECEIPT_STATUSES:
            findings.append(active_lane_finding("session resume execution ledger terminal outcome is invalid"))
        previous_hash = record.get("record_hash")
    if ledger.get("head_record_hash") != previous_hash:
        findings.append(active_lane_finding("session resume execution ledger head hash mismatch"))
    return validation_result(findings)


def ledger_record_for_checkpoint(ledger: dict[str, Any], checkpoint: dict[str, Any]) -> dict[str, Any]:
    checkpoint_id = checkpoint.get("checkpoint_id")
    command_hash = exact_command_hash(checkpoint.get("exact_next_command"))
    return next(
        (
            as_dict(item)
            for item in as_list(ledger.get("records"))
            if as_dict(item).get("checkpoint_id") == checkpoint_id
            and as_dict(item).get("exact_command_sha256") == command_hash
        ),
        {},
    )


def projection_selection_gate(
    projection: dict[str, Any],
    source_kind: str | None,
    lane_id: str | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    projection_validation = as_dict(projection.get("validation"))
    critical_details = [
        str(as_dict(item).get("detail") or "")
        for item in as_list(projection_validation.get("findings"))
        if as_dict(item).get("severity") == "critical"
    ]
    explicit_ambiguity_only = bool(
        projection.get("resolution") == "blocked_ambiguous"
        and source_kind == "explicit_checkpoint"
        and critical_details
        and all(detail.startswith("multiple active lanes require an explicit lane-bound checkpoint") for detail in critical_details)
    )
    if projection_validation.get("status") == "critical" and not explicit_ambiguity_only:
        reasons.append("active_lane_projection_invalid")
    lanes = [as_dict(item) for item in as_list(projection.get("active_lanes"))]
    active_count = int(projection.get("active_lane_count") or 0)
    if active_count != len(lanes):
        reasons.append("active_lane_count_mismatch")
    identities = [str(item.get("lane_id") or "") for item in lanes]
    if any(not identity for identity in identities):
        reasons.append("active_lane_identity_missing")
    if len(set(identities)) != len(identities):
        reasons.append("active_lane_identity_duplicate")
    for lane in lanes:
        if not lane.get("workflow_id"):
            reasons.append("active_lane_workflow_missing")
        if not lane.get("owner"):
            reasons.append("active_lane_owner_missing")
        if lane.get("lease_current") is not True:
            reasons.append("active_lane_lease_stale_or_missing")
    matches = [item for item in lanes if item.get("lane_id") == lane_id]
    if active_count:
        if not lane_id or len(matches) != 1:
            reasons.append("exact_lane_selection_not_unique")
        if active_count > 1 and source_kind != "explicit_checkpoint":
            reasons.append("multiple_lanes_require_explicit_checkpoint")
    return {
        "status": "critical" if reasons else "ok",
        "reasons": sorted(set(reasons)),
        "active_lane_count": active_count,
        "projected_lane_count": len(lanes),
        "source_kind": source_kind,
        "selected_lane_id": lane_id,
    }


def validation_result(findings: list[dict[str, Any]]) -> dict[str, Any]:
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warnings = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "status": "critical" if critical else ("warning" if warnings else "ok"),
        "critical": critical,
        "warnings": warnings,
        "findings": findings,
    }


def active_lane_finding(detail: str, *, severity: str = "critical") -> dict[str, Any]:
    return {
        "severity": severity,
        "category": "current_task_blocker" if severity == "critical" else "current_task_warning",
        "detail": detail,
    }


def normalize_active_lane(raw: dict[str, Any], full: dict[str, Any], now: datetime) -> dict[str, Any]:
    merged = {**full, **raw}
    runtime = as_dict(full.get("runtime"))
    lane_id = str(merged.get("lane_id") or "").strip() or None
    workflow_id = str(merged.get("workflow_id") or full.get("workflow_id") or "").strip() or None
    workstream = str(
        merged.get("workstream_id")
        or merged.get("workstream")
        or full.get("workstream_id")
        or ""
    ).strip() or None
    expiry_text = merged.get("lease_expires_at_utc") or full.get("lease_expires_at_utc")
    expiry = parse_utc(expiry_text)
    lease_current = bool(expiry and expiry > now)
    status = str(merged.get("status") or full.get("status") or "").strip() or None
    return {
        "lane_id": lane_id,
        "workflow_id": workflow_id,
        "workstream": workstream,
        "owner": merged.get("owner") or full.get("owner"),
        "status": status,
        "phase": merged.get("phase") or runtime.get("phase"),
        "parent_job_id": merged.get("parent_job_id") or runtime.get("parent_job_id"),
        "objective": merged.get("objective") or runtime.get("objective"),
        "next_action": merged.get("next_action") or runtime.get("deliverable"),
        "exact_next_command": merged.get("exact_next_command") or runtime.get("exact_next_command"),
        "blocker": merged.get("blocker"),
        "lease_expires_at_utc": iso_utc(expiry) if expiry else None,
        "lease_current": lease_current,
        "sla_status": "lease_current" if lease_current else "lease_stale_or_missing",
        "allowed_writes": sorted(str(item) for item in as_list(full.get("allowed_writes")) if str(item).strip()),
        "proof_artifacts": sorted(str(item) for item in as_list(full.get("proof_artifacts")) if str(item).strip()),
        "stop_lines": [str(item) for item in as_list(full.get("stop_lines")) if str(item).strip()],
        "authority_boundary": full.get("authority_boundary"),
        "attempt_retry_identity": {
            "attempt_id": runtime.get("attempt_id"),
            "attempt_number": runtime.get("attempt_number"),
            "retry_count": runtime.get("retry_count"),
        },
        "updated_at_utc": merged.get("updated_at_utc") or full.get("updated_at_utc"),
    }


def project_active_lanes(lane_register: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Project a compact, validated active-lane view from the real register shape."""
    current_time = ensure_utc(now)
    findings: list[dict[str, Any]] = []
    register_valid = bool(lane_register) and lane_register.get("schema") == LANE_REGISTER_SCHEMA
    if not lane_register:
        findings.append(active_lane_finding("concurrent lane register is missing or unreadable"))
    elif lane_register.get("schema") != LANE_REGISTER_SCHEMA:
        findings.append(active_lane_finding("concurrent lane register schema is invalid"))
    upstream_validation = as_dict(lane_register.get("validation"))
    if lane_register and upstream_validation.get("status") not in {None, "ok"}:
        findings.append(active_lane_finding(
            f"concurrent lane register upstream validation is {upstream_validation.get('status')}",
            severity="warning",
        ))
    summary = as_dict(lane_register.get("summary"))
    full_rows = [as_dict(item) for item in as_list(lane_register.get("lanes"))]
    full_by_id = {
        str(row.get("lane_id")): row
        for row in full_rows
        if str(row.get("lane_id") or "").strip()
    }
    summary_rows = [as_dict(item) for item in as_list(summary.get("open_lanes"))]
    if summary_rows:
        source_rows = summary_rows
        source_shape = "summary.open_lanes"
    else:
        source_rows = [row for row in full_rows if str(row.get("status") or "") in ACTIVE_STATUSES]
        source_shape = "lanes.active_status_filter"

    declared_raw = summary.get("active_lane_count")
    try:
        declared_count = int(declared_raw) if declared_raw is not None else len(source_rows)
    except (TypeError, ValueError):
        declared_count = len(source_rows)
        findings.append(active_lane_finding("lane register active_lane_count is not an integer"))

    active_lanes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in source_rows:
        lane_id = str(raw.get("lane_id") or "").strip()
        full = full_by_id.get(lane_id, {})
        lane = normalize_active_lane(raw, full, current_time)
        if lane.get("status") not in ACTIVE_STATUSES:
            continue
        if not lane.get("lane_id"):
            findings.append(active_lane_finding("active lane row is missing lane_id"))
        elif lane_id in seen:
            findings.append(active_lane_finding(f"duplicate active lane identity: {lane_id}"))
        else:
            seen.add(lane_id)
        if not lane.get("workflow_id"):
            findings.append(active_lane_finding(f"active lane is missing workflow_id: {lane.get('lane_id')}"))
        if not lane.get("owner"):
            findings.append(active_lane_finding(f"active lane is missing owner: {lane.get('lane_id')}"))
        if not lane.get("lease_current"):
            findings.append(active_lane_finding(f"active lane lease is stale or missing: {lane.get('lane_id')}"))
        active_lanes.append(lane)

    active_lanes.sort(key=lambda item: str(item.get("lane_id") or ""))
    if declared_count != len(active_lanes):
        findings.append(active_lane_finding(
            f"active lane count mismatch: declared={declared_count} projected={len(active_lanes)}"
        ))

    effective_count = max(declared_count, len(active_lanes))
    current_lane: dict[str, Any] | None = None
    if not register_valid:
        resolution = "blocked_missing_register"
        blocking_reasons = ["lane_register_missing_or_invalid"]
    elif effective_count == 0:
        resolution = "none"
        blocking_reasons: list[str] = []
    elif effective_count > 1:
        resolution = "blocked_ambiguous"
        blocking_reasons = ["multiple_active_lanes_require_explicit_checkpoint"]
        findings.append(active_lane_finding(
            f"multiple active lanes require an explicit lane-bound checkpoint: count={effective_count}"
        ))
    elif len(active_lanes) != 1 or not active_lanes[0].get("lane_id"):
        resolution = "blocked_missing_identity"
        blocking_reasons = ["active_lane_identity_missing"]
        findings.append(active_lane_finding("active lane count is nonzero but no current lane identity is available"))
    elif not active_lanes[0].get("lease_current"):
        current_lane = active_lanes[0]
        resolution = "blocked_stale_lease"
        blocking_reasons = ["active_lane_lease_stale_or_missing"]
    else:
        current_lane = active_lanes[0]
        resolution = "single"
        blocking_reasons = []

    validation = validation_result(findings)
    return {
        "schema": ACTIVE_LANES_SCHEMA,
        "generated_at_utc": iso_utc(current_time),
        "source": "tmp/concurrent-lane-register.json",
        "source_shape": source_shape,
        "status": "blocked" if validation["status"] == "critical" else "ok",
        "active_lane_count": effective_count,
        "projected_lane_count": len(active_lanes),
        "resolution": resolution,
        "blocking_reasons": blocking_reasons,
        "current_lane": current_lane,
        "active_lanes": active_lanes,
        "precedence": PRECEDENCE,
        "validation": validation,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def workspace_path(root: Path, value: str) -> tuple[str, Path]:
    raw = Path(str(value).strip())
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    root_resolved = root.resolve()
    try:
        relative = resolved.relative_to(root_resolved).as_posix()
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root: {value}") from exc
    return relative, resolved


def hash_paths(root: Path, paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in sorted({str(item).strip() for item in paths if str(item).strip()}):
        relative, path = workspace_path(root, value)
        exists = path.is_file()
        rows.append({
            "path": relative,
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists else None,
        })
    return rows


def hash_row_findings(
    rows: Any,
    label: str,
    *,
    root: Path,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return [active_lane_finding(f"resume {label} must be a list")]
    for raw_row in rows:
        row = as_dict(raw_row)
        path_text = str(row.get("path") or "").strip()
        if not row.get("exists") or not path_text:
            findings.append(active_lane_finding(f"resume {label} path is missing: {path_text or None}"))
            continue
        try:
            _, live_path = workspace_path(root, path_text)
        except ValueError as exc:
            findings.append(active_lane_finding(str(exc)))
            continue
        if not live_path.is_file():
            findings.append(active_lane_finding(f"resume {label} live path is missing: {path_text}"))
            continue
        live_hash = hashlib.sha256(live_path.read_bytes()).hexdigest()
        if live_hash != row.get("sha256"):
            findings.append(active_lane_finding(f"resume {label} live path drifted: {path_text}"))
    return findings


def checkpoint_content(checkpoint: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "parent_job_id",
        "workflow_id",
        "lane_id",
        "workstream",
        "objective",
        "status",
        "last_completed_step",
        "in_progress_step",
        "exact_next_action",
        "exact_next_command",
        "already_completed_do_not_repeat",
        "changed_files_and_hashes",
        "proof_artifacts_and_hashes",
        "attempt_retry_identity",
        "blocker",
        "approval_boundary",
        "stop_lines",
        "continuity_home",
        "safe_to_execute_automatically",
    ]
    content = {field: checkpoint.get(field) for field in fields}
    if "source_binding_sha256" in checkpoint:
        content["source_binding_sha256"] = checkpoint.get("source_binding_sha256")
    return content


def checkpoint_validation(
    checkpoint: dict[str, Any],
    now: datetime | None = None,
    *,
    root: Path = ROOT,
    execution_ledger: dict[str, Any] | None = None,
    verify_changed_files: bool = True,
) -> dict[str, Any]:
    current_time = ensure_utc(now)
    findings: list[dict[str, Any]] = []
    selection = as_dict(checkpoint.get("selection"))
    resolution = selection.get("resolution")
    if resolution == "none" and not checkpoint.get("checkpoint_id"):
        return validation_result(findings)
    if checkpoint.get("schema") != SCHEMA:
        findings.append(active_lane_finding("resume checkpoint schema is not current"))
    projection_gate = as_dict(checkpoint.get("projection_gate"))
    if projection_gate.get("status") != "ok":
        reasons = ",".join(str(item) for item in as_list(projection_gate.get("reasons"))) or "missing"
        findings.append(active_lane_finding(f"resume live projection gate is critical: {reasons}"))
    if resolution in {"blocked_ambiguous", "blocked_missing_identity", "blocked_stale_lease", "blocked_missing_register"}:
        findings.append(active_lane_finding(f"resume selection is blocked: {resolution}"))
    source_binding = checkpoint.get("source_binding_sha256")
    if source_binding is None:
        findings.append(active_lane_finding(
            "legacy resume checkpoint lacks source-kind integrity binding; emit a successor after consumption",
            severity="warning",
        ))
    elif source_binding != stable_hash(checkpoint.get("source")):
        findings.append(active_lane_finding("resume checkpoint source-kind integrity binding mismatch"))
    if not checkpoint.get("checkpoint_id"):
        findings.append(active_lane_finding("resume checkpoint_id is missing"))
    if not checkpoint.get("workflow_id"):
        findings.append(active_lane_finding("resume workflow_id is missing"))
    if not checkpoint.get("objective"):
        findings.append(active_lane_finding("resume objective is missing"))
    if not checkpoint.get("last_completed_step"):
        findings.append(active_lane_finding("resume last_completed_step is missing"))
    if not checkpoint.get("in_progress_step"):
        findings.append(active_lane_finding("resume in_progress_step is missing"))
    if not isinstance(checkpoint.get("exact_next_action"), str) or not checkpoint.get("exact_next_action").strip():
        findings.append(active_lane_finding("resume exact_next_action is missing"))
    if not isinstance(checkpoint.get("exact_next_command"), str) or not checkpoint.get("exact_next_command").strip():
        findings.append(active_lane_finding("resume exact_next_command is missing"))
    if not isinstance(checkpoint.get("already_completed_do_not_repeat"), list):
        findings.append(active_lane_finding("resume already_completed_do_not_repeat must be a list"))
    for field in ("changed_files_and_hashes", "proof_artifacts_and_hashes"):
        if not isinstance(checkpoint.get(field), list):
            findings.append(active_lane_finding(f"resume {field} must be a list"))
            continue
        for raw_row in as_list(checkpoint.get(field)):
            row = as_dict(raw_row)
            path_text = str(row.get("path") or "").strip()
            if not row.get("exists") or not path_text:
                findings.append(active_lane_finding(f"resume hash-bound path is missing: {path_text or None}"))
                continue
            try:
                _, live_path = workspace_path(root, path_text)
            except ValueError as exc:
                findings.append(active_lane_finding(str(exc)))
                continue
            if not live_path.is_file():
                findings.append(active_lane_finding(f"resume hash-bound live path is missing: {path_text}"))
                continue
            live_hash = hashlib.sha256(live_path.read_bytes()).hexdigest()
            should_verify_live_hash = field != "changed_files_and_hashes" or verify_changed_files
            if should_verify_live_hash and live_hash != row.get("sha256"):
                findings.append(active_lane_finding(f"resume hash-bound live path drifted: {path_text}"))
    expected_hash = stable_hash(checkpoint_content(checkpoint))
    if checkpoint.get("checkpoint_content_hash") != expected_hash:
        findings.append(active_lane_finding("resume checkpoint content hash mismatch"))
    sequence = checkpoint.get("checkpoint_sequence")
    expected_id = (
        f"resume-{sequence:04d}-{expected_hash[:16]}"
        if isinstance(sequence, int) and sequence > 0
        else None
    )
    if checkpoint.get("checkpoint_id") != expected_id:
        findings.append(active_lane_finding("resume checkpoint_id is not bound to sequence and content hash"))
    if checkpoint.get("checkpoint_state_hash") != stable_hash(checkpoint_state_content(checkpoint)):
        findings.append(active_lane_finding("resume checkpoint mutable state hash mismatch"))
    expiry = parse_utc(checkpoint.get("freshness_expiry"))
    if not expiry or expiry <= current_time:
        findings.append(active_lane_finding("resume checkpoint is stale or lacks freshness_expiry"))
    active_lane_count = int(selection.get("active_lane_count") or 0)
    if active_lane_count and not checkpoint.get("lane_id"):
        findings.append(active_lane_finding("resume checkpoint with active lanes must name one exact lane_id"))
    if checkpoint.get("lane_id"):
        active_lease = as_dict(checkpoint.get("active_lease"))
        if active_lease.get("lease_current") is not True:
            findings.append(active_lane_finding("resume checkpoint is not bound to a current active lease"))
        if active_lease.get("lane_id") != checkpoint.get("lane_id"):
            findings.append(active_lane_finding("resume checkpoint active lease lane_id mismatch"))
        lease_expiry = parse_utc(active_lease.get("lease_expires_at_utc"))
        if not lease_expiry or lease_expiry <= current_time:
            findings.append(active_lane_finding("resume checkpoint active lease is stale or lacks expiry"))
    receipt = as_dict(checkpoint.get("execution_receipt"))
    receipt_status = receipt.get("status")
    if receipt_status not in {"pending", "succeeded", "failed", "not_applicable"}:
        findings.append(active_lane_finding("resume execution receipt status is invalid"))
    if receipt_status in TERMINAL_EXECUTION_RECEIPT_STATUSES:
        if receipt.get("checkpoint_id") != checkpoint.get("checkpoint_id"):
            findings.append(active_lane_finding("resume execution receipt checkpoint_id mismatch"))
        if receipt.get("exact_command_sha256") != exact_command_hash(checkpoint.get("exact_next_command")):
            findings.append(active_lane_finding("resume execution receipt exact command hash mismatch"))
        if receipt.get("receipt_content_hash") != stable_hash(execution_receipt_content(receipt)):
            findings.append(active_lane_finding("resume execution receipt content hash mismatch"))
        findings.extend(hash_row_findings(
            receipt.get("proof_artifacts_and_hashes"),
            "execution receipt proof",
            root=root,
        ))
    ledger = execution_ledger if execution_ledger is not None else load_execution_ledger(root)
    ledger_validation = validate_execution_ledger(ledger)
    if ledger_validation.get("status") == "critical":
        findings.extend(as_list(ledger_validation.get("findings")))
    ledger_record = ledger_record_for_checkpoint(ledger, checkpoint)
    if receipt_status in TERMINAL_EXECUTION_RECEIPT_STATUSES and not ledger_record:
        findings.append(active_lane_finding("resume terminal execution receipt is missing from the monotonic ledger"))
    if receipt_status not in TERMINAL_EXECUTION_RECEIPT_STATUSES and ledger_record:
        findings.append(active_lane_finding("resume execution ledger shows this command was already consumed"))
    if ledger_record:
        if receipt_status in TERMINAL_EXECUTION_RECEIPT_STATUSES:
            if ledger_record.get("receipt_content_hash") != receipt.get("receipt_content_hash"):
                findings.append(active_lane_finding("resume execution receipt and ledger content hashes do not match"))
            if ledger_record.get("proof_artifacts_and_hashes") != receipt.get("proof_artifacts_and_hashes"):
                findings.append(active_lane_finding("resume execution receipt and ledger proof rows do not match"))
            ledger_outcome = ledger_record.get("outcome_status")
            if ledger_outcome is not None and ledger_outcome != receipt_status:
                findings.append(active_lane_finding("resume execution receipt and ledger terminal outcomes do not match"))
        findings.extend(hash_row_findings(
            ledger_record.get("proof_artifacts_and_hashes"),
            "execution ledger proof",
            root=root,
        ))
    return validation_result(findings)


def apply_evaluation(
    checkpoint: dict[str, Any],
    now: datetime | None = None,
    *,
    root: Path = ROOT,
    execution_ledger: dict[str, Any] | None = None,
    verify_changed_files: bool = True,
) -> dict[str, Any]:
    payload = dict(checkpoint)
    ledger = execution_ledger if execution_ledger is not None else load_execution_ledger(root)
    validation = checkpoint_validation(
        payload,
        now,
        root=root,
        execution_ledger=ledger,
        verify_changed_files=verify_changed_files,
    )
    no_target = as_dict(payload.get("selection")).get("resolution") == "none" and not payload.get("checkpoint_id")
    payload["validation"] = validation
    payload["resume_status"] = "no_resume_target" if no_target else (
        "blocked" if validation["status"] == "critical" else "ready"
    )
    acknowledgement = as_dict(payload.get("resume_acknowledgement"))
    acknowledged = (
        acknowledgement.get("status") == "acknowledged"
        and acknowledgement.get("checkpoint_id") == payload.get("checkpoint_id")
    )
    command_present = bool(
        isinstance(payload.get("exact_next_command"), str)
        and payload.get("exact_next_command").strip()
    )
    safe = payload.get("safe_to_execute_automatically") is True
    checkpoint_status_allows_execution = payload.get("status") in RESUMABLE_CHECKPOINT_STATUSES
    receipt = as_dict(payload.get("execution_receipt"))
    receipt_consumed = bool(
        receipt.get("status") in TERMINAL_EXECUTION_RECEIPT_STATUSES
        and receipt.get("checkpoint_id") == payload.get("checkpoint_id")
        and receipt.get("exact_command_sha256") == exact_command_hash(payload.get("exact_next_command"))
        and receipt.get("receipt_content_hash") == stable_hash(execution_receipt_content(receipt))
    )
    ledger_consumed = bool(ledger_record_for_checkpoint(ledger, payload))
    denylisted_complete = listed_as_completed(payload)
    replay_blocked = receipt_consumed or ledger_consumed or denylisted_complete
    blocker_present = bool(str(payload.get("blocker") or "").strip())
    if payload.get("resume_status") == "ready" and not checkpoint_status_allows_execution:
        payload["resume_status"] = "blocked"
    if payload.get("resume_status") == "ready" and blocker_present:
        payload["resume_status"] = "blocked"
    if payload.get("resume_status") == "ready" and receipt_consumed:
        payload["resume_status"] = "awaiting_successor"
    authorized = bool(
        payload.get("resume_status") == "ready"
        and command_present
        and safe
        and acknowledged
        and not replay_blocked
    )
    payload["execution_gate"] = {
        "status": "authorized" if authorized else (
            "not_applicable" if no_target else ("consumed" if receipt_consumed else "blocked")
        ),
        "checkpoint_valid": validation["status"] != "critical",
        "exact_command_present": command_present,
        "resume_acknowledged": acknowledged,
        "safe_to_execute_automatically": safe,
        "checkpoint_status_allows_execution": checkpoint_status_allows_execution,
        "blocker_present": blocker_present,
        "already_completed_denylist_match": denylisted_complete,
        "execution_receipt_consumed": receipt_consumed,
        "execution_ledger_consumed": ledger_consumed,
        "replay_blocked": replay_blocked,
        "command_authorized": authorized,
        "execution_performed_by_this_script": False,
    }
    return payload


def active_lease_for_lane(projection: dict[str, Any], lane_id: str | None) -> dict[str, Any]:
    if not lane_id:
        return {}
    matches = [
        as_dict(row)
        for row in as_list(projection.get("active_lanes"))
        if as_dict(row).get("lane_id") == lane_id
    ]
    if len(matches) != 1:
        return {
            "lane_id": lane_id,
            "lease_current": False,
            "selection_unique": False,
        }
    lane = matches[0]
    return {
        "lane_id": lane_id,
        "status": lane.get("status"),
        "owner": lane.get("owner"),
        "lease_expires_at_utc": lane.get("lease_expires_at_utc"),
        "lease_current": lane.get("lease_current") is True,
        "selection_unique": True,
    }


def expiration_for(now: datetime, hours: float, active_lease: dict[str, Any]) -> str:
    expiry = now + timedelta(hours=max(float(hours), 0.01))
    lease_expiry = parse_utc(active_lease.get("lease_expires_at_utc"))
    if lease_expiry and lease_expiry < expiry:
        expiry = lease_expiry
    return iso_utc(expiry)


def assemble_checkpoint(
    record: dict[str, Any],
    projection: dict[str, Any],
    existing: dict[str, Any],
    root: Path,
    now: datetime,
    freshness_hours: float,
    *,
    source_kind: str,
) -> dict[str, Any]:
    lane_id = str(record.get("lane_id") or "").strip() or None
    lane = next(
        (as_dict(row) for row in as_list(projection.get("active_lanes")) if as_dict(row).get("lane_id") == lane_id),
        {},
    )
    active_lease = active_lease_for_lane(projection, lane_id)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": iso_utc(now),
        "source": {
            "kind": source_kind,
            "precedence": PRECEDENCE,
            "lane_projection_schema": projection.get("schema"),
            "selection_context": {
                "active_lane_count": projection.get("active_lane_count"),
                "selected_lane_id": lane_id,
                "lease_expires_at_utc": active_lease.get("lease_expires_at_utc"),
            },
        },
        "selection": {
            "resolution": "explicit" if source_kind == "explicit_checkpoint" else projection.get("resolution"),
            "active_lane_count": projection.get("active_lane_count"),
            "selected_source": source_kind,
        },
        "projection_gate": projection_selection_gate(projection, source_kind, lane_id),
        "parent_job_id": record.get("parent_job_id") or lane.get("parent_job_id"),
        "workflow_id": record.get("workflow_id") or lane.get("workflow_id"),
        "lane_id": lane_id,
        "workstream": record.get("workstream") or lane.get("workstream"),
        "objective": record.get("objective") or lane.get("objective"),
        "status": record.get("status") or "in_progress",
        "last_completed_step": record.get("last_completed_step"),
        "in_progress_step": record.get("in_progress_step"),
        "exact_next_action": record.get("exact_next_action") or lane.get("next_action"),
        "exact_next_command": record.get("exact_next_command") or lane.get("exact_next_command"),
        "already_completed_do_not_repeat": [
            str(item) for item in as_list(record.get("already_completed_do_not_repeat")) if str(item).strip()
        ],
        "changed_files_and_hashes": hash_paths(root, [str(item) for item in as_list(record.get("changed_files"))]),
        "proof_artifacts_and_hashes": hash_paths(root, [str(item) for item in as_list(record.get("proof_artifacts"))]),
        "attempt_retry_identity": record.get("attempt_retry_identity") or lane.get("attempt_retry_identity") or {},
        "active_lease": active_lease,
        "blocker": record.get("blocker") or lane.get("blocker"),
        "approval_boundary": record.get("approval_boundary") or lane.get("authority_boundary"),
        "stop_lines": [str(item) for item in as_list(record.get("stop_lines") or lane.get("stop_lines")) if str(item).strip()],
        "continuity_home": record.get("continuity_home"),
        "safe_to_execute_automatically": record.get("safe_to_execute_automatically") is True,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["source_binding_sha256"] = stable_hash(payload["source"])
    content_hash = stable_hash(checkpoint_content(payload))
    same_content = (
        existing.get("schema") == SCHEMA
        and existing.get("checkpoint_content_hash") == content_hash
        and as_dict(existing.get("source")).get("kind") == source_kind
    )
    if same_content:
        sequence = int(existing.get("checkpoint_sequence") or 1)
        checkpoint_id = existing.get("checkpoint_id")
        created_at = existing.get("created_at_utc") or iso_utc(now)
        freshness_expiry = existing.get("freshness_expiry") or expiration_for(now, freshness_hours, active_lease)
        acknowledgement = existing.get("resume_acknowledgement")
        execution_receipt = existing.get("execution_receipt")
        existing_state_valid = (
            existing.get("checkpoint_state_hash") == stable_hash(checkpoint_state_content(existing))
        )
    else:
        previous_sequence = int(existing.get("checkpoint_sequence") or 0) if existing.get("schema") == SCHEMA else 0
        sequence = previous_sequence + 1
        checkpoint_id = f"resume-{sequence:04d}-{content_hash[:16]}"
        created_at = iso_utc(now)
        freshness_expiry = expiration_for(now, freshness_hours, active_lease)
        acknowledgement = {"status": "pending", "checkpoint_id": checkpoint_id}
        execution_receipt = {"status": "pending", "checkpoint_id": checkpoint_id}
    payload.update({
        "checkpoint_id": checkpoint_id,
        "checkpoint_sequence": sequence,
        "checkpoint_content_hash": content_hash,
        "created_at_utc": created_at,
        "freshness_expiry": freshness_expiry,
        "resume_acknowledgement": acknowledgement,
        "execution_receipt": execution_receipt,
    })
    if same_content and not existing_state_valid:
        payload["checkpoint_state_hash"] = existing.get("checkpoint_state_hash")
    else:
        payload = refresh_checkpoint_state_hash(payload)
    return apply_evaluation(payload, now, root=root)


def empty_pointer(projection: dict[str, Any], now: datetime, *, root: Path = ROOT) -> dict[str, Any]:
    resolution = projection.get("resolution")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": iso_utc(now),
        "source": {"kind": "active_lane_projection", "precedence": PRECEDENCE},
        "selection": {
            "resolution": resolution,
            "active_lane_count": projection.get("active_lane_count"),
            "selected_source": None,
            "blocking_reasons": projection.get("blocking_reasons"),
        },
        "projection_gate": projection_selection_gate(projection, "active_lane_projection", None),
        "checkpoint_id": None,
        "checkpoint_sequence": 0,
        "checkpoint_content_hash": None,
        "parent_job_id": None,
        "workflow_id": None,
        "lane_id": None,
        "workstream": None,
        "objective": None,
        "status": "blocked" if resolution != "none" else "idle",
        "last_completed_step": None,
        "in_progress_step": None,
        "exact_next_action": None,
        "exact_next_command": None,
        "already_completed_do_not_repeat": [],
        "changed_files_and_hashes": [],
        "proof_artifacts_and_hashes": [],
        "attempt_retry_identity": {},
        "active_lease": {},
        "blocker": ",".join(str(item) for item in as_list(projection.get("blocking_reasons"))) or None,
        "approval_boundary": None,
        "stop_lines": [],
        "continuity_home": None,
        "freshness_expiry": None,
        "safe_to_execute_automatically": False,
        "resume_acknowledgement": {"status": "not_applicable", "checkpoint_id": None},
        "execution_receipt": {"status": "not_applicable", "checkpoint_id": None},
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["source_binding_sha256"] = stable_hash(payload["source"])
    return apply_evaluation(payload, now, root=root)


def existing_explicit_is_reusable(existing: dict[str, Any], projection: dict[str, Any], now: datetime) -> bool:
    if existing.get("schema") != SCHEMA or as_dict(existing.get("source")).get("kind") != "explicit_checkpoint":
        return False
    if existing.get("checkpoint_content_hash") != stable_hash(checkpoint_content(existing)):
        return True  # Preserve the tampered checkpoint so validation exposes it.
    if as_dict(projection.get("validation")).get("status") == "critical":
        return True  # Preserve explicit state and fail closed rather than erase it.
    expiry = parse_utc(existing.get("freshness_expiry"))
    if not expiry or expiry <= now:
        return True  # Preserve stale explicit state and fail closed.
    lane_id = existing.get("lane_id")
    if not lane_id:
        return bool(existing.get("workflow_id"))
    return any(
        as_dict(row).get("lane_id") == lane_id and as_dict(row).get("lease_current") is True
        for row in as_list(projection.get("active_lanes"))
    )


def rebind_live_lease(
    checkpoint: dict[str, Any],
    projection: dict[str, Any],
    now: datetime,
    *,
    root: Path = ROOT,
    verify_changed_files: bool = True,
) -> dict[str, Any]:
    """Validate stored state before applying a trusted live-lease projection."""
    initial = apply_evaluation(checkpoint, now, root=root, verify_changed_files=verify_changed_files)
    if as_dict(initial.get("validation")).get("status") == "critical":
        return initial
    if not initial.get("lane_id"):
        return initial
    rebound = dict(initial)
    source = as_dict(rebound.get("source"))
    source_binding_valid = bool(
        rebound.get("source_binding_sha256")
        and rebound.get("source_binding_sha256") == stable_hash(source)
    )
    source_kind = source.get("kind") if source_binding_valid else None
    rebound["selection"] = {
        **as_dict(rebound.get("selection")),
        "resolution": "explicit" if source_kind == "explicit_checkpoint" else projection.get("resolution"),
        "active_lane_count": projection.get("active_lane_count"),
    }
    rebound["projection_gate"] = projection_selection_gate(
        projection,
        source_kind,
        str(initial.get("lane_id")),
    )
    rebound["active_lease"] = active_lease_for_lane(projection, str(initial.get("lane_id")))
    rebound = refresh_checkpoint_state_hash(rebound)
    return apply_evaluation(rebound, now, root=root, verify_changed_files=verify_changed_files)


def refresh_existing(
    existing: dict[str, Any],
    projection: dict[str, Any],
    now: datetime,
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    payload = dict(existing)
    payload["generated_at_utc"] = iso_utc(now)
    payload["selection"] = {
        "resolution": "explicit",
        "active_lane_count": projection.get("active_lane_count"),
        "selected_source": "explicit_checkpoint",
    }
    return rebind_live_lease(payload, projection, now, root=root)


def refresh_outputs(
    *,
    root: Path = ROOT,
    tmp: Path = TMP,
    now: datetime | None = None,
    record: dict[str, Any] | None = None,
    freshness_hours: float = DEFAULT_FRESHNESS_HOURS,
    write: bool = False,
    resume_out: Path | None = None,
    active_out: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_time = ensure_utc(now)
    lane_register = as_dict(load_json_artifact(tmp / "concurrent-lane-register.json"))
    projection = project_active_lanes(lane_register, current_time)
    resume_path = resume_out or (tmp / "current-resume.json")
    active_path = active_out or (tmp / "current-active-lanes.json")
    existing = as_dict(load_json_artifact(resume_path))

    if record is not None:
        checkpoint = assemble_checkpoint(
            record,
            projection,
            existing,
            root,
            current_time,
            freshness_hours,
            source_kind="explicit_checkpoint",
        )
    elif existing_explicit_is_reusable(existing, projection, current_time):
        checkpoint = refresh_existing(existing, projection, current_time, root=root)
    elif projection.get("resolution") == "single":
        lane = as_dict(projection.get("current_lane"))
        checkpoint = assemble_checkpoint(
            {
                "lane_id": lane.get("lane_id"),
                "workflow_id": lane.get("workflow_id"),
                "workstream": lane.get("workstream"),
                "objective": lane.get("objective"),
                "status": lane.get("status"),
                "exact_next_action": lane.get("next_action"),
                "exact_next_command": lane.get("exact_next_command"),
                "attempt_retry_identity": lane.get("attempt_retry_identity"),
                "approval_boundary": lane.get("authority_boundary"),
                "stop_lines": lane.get("stop_lines"),
            },
            projection,
            existing,
            root,
            current_time,
            freshness_hours,
            source_kind="active_lane_projection",
        )
    else:
        checkpoint = empty_pointer(projection, current_time, root=root)

    if write:
        atomic_write_json(active_path, projection)
        atomic_write_json(resume_path, checkpoint)
    return checkpoint, projection


def acknowledge_checkpoint(
    checkpoint: dict[str, Any],
    checkpoint_id: str,
    actor: str,
    now: datetime | None = None,
    *,
    root: Path = ROOT,
    active_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_time = ensure_utc(now)
    if checkpoint.get("checkpoint_id") != checkpoint_id:
        raise ValueError(
            f"resume acknowledgement checkpoint mismatch: expected={checkpoint.get('checkpoint_id')} received={checkpoint_id}"
        )
    if checkpoint.get("lane_id") and active_projection is None:
        raise ValueError("cannot acknowledge a lane-bound checkpoint without a live active-lane projection")
    candidate = dict(checkpoint)
    evaluated = (
        rebind_live_lease(candidate, active_projection, current_time, root=root)
        if active_projection is not None
        else apply_evaluation(candidate, current_time, root=root)
    )
    if as_dict(evaluated.get("validation")).get("status") == "critical":
        raise ValueError("cannot acknowledge an invalid or stale resume checkpoint")
    existing = as_dict(evaluated.get("resume_acknowledgement"))
    if existing.get("status") == "acknowledged" and existing.get("checkpoint_id") == checkpoint_id:
        return evaluated
    evaluated["resume_acknowledgement"] = {
        "status": "acknowledged",
        "checkpoint_id": checkpoint_id,
        "acknowledged_by": actor,
        "acknowledged_at_utc": iso_utc(current_time),
    }
    evaluated = refresh_checkpoint_state_hash(evaluated)
    return apply_evaluation(evaluated, current_time, root=root)


def append_execution_ledger_record(
    ledger: dict[str, Any],
    receipt: dict[str, Any],
    now: datetime,
    *,
    root: Path,
) -> dict[str, Any]:
    validation = validate_execution_ledger(ledger)
    if validation.get("status") == "critical":
        raise ValueError("cannot append to an invalid session resume execution ledger")
    proof_findings = hash_row_findings(
        receipt.get("proof_artifacts_and_hashes"),
        "execution receipt proof",
        root=root,
    )
    if proof_findings:
        raise ValueError("cannot record execution with missing or drifted proof artifacts")
    checkpoint_id = str(receipt.get("checkpoint_id") or "")
    command_hash = str(receipt.get("exact_command_sha256") or "")
    records = [as_dict(item) for item in as_list(ledger.get("records"))]
    for record in records:
        if record.get("checkpoint_id") == checkpoint_id:
            if record.get("exact_command_sha256") == command_hash:
                if (
                    record.get("receipt_content_hash") == receipt.get("receipt_content_hash")
                    and record.get("proof_artifacts_and_hashes") == receipt.get("proof_artifacts_and_hashes")
                    and record.get("outcome_status") in {None, receipt.get("status")}
                ):
                    return ledger
                raise ValueError("execution ledger checkpoint receipt conflicts with its existing record")
            raise ValueError("execution ledger checkpoint_id is already bound to a different command")
    record = {
        "sequence": len(records) + 1,
        "previous_record_hash": ledger.get("head_record_hash"),
        "checkpoint_id": checkpoint_id,
        "exact_command_sha256": command_hash,
        "receipt_content_hash": receipt.get("receipt_content_hash"),
        "outcome_status": receipt.get("status"),
        "executed_by": receipt.get("executed_by"),
        "executed_at_utc": receipt.get("executed_at_utc"),
        "recorded_at_utc": iso_utc(now),
        "proof_artifacts_and_hashes": receipt.get("proof_artifacts_and_hashes"),
    }
    record["record_hash"] = stable_hash(execution_ledger_record_content(record))
    return {
        "schema": EXECUTION_LEDGER_SCHEMA,
        "generated_at_utc": iso_utc(now),
        "records": [*records, record],
        "head_record_hash": record["record_hash"],
    }


def record_execution_receipt(
    checkpoint: dict[str, Any],
    checkpoint_id: str,
    actor: str,
    now: datetime | None = None,
    *,
    root: Path = ROOT,
    active_projection: dict[str, Any] | None = None,
    proof_artifacts: list[str] | None = None,
    execution_ledger_file: Path | None = None,
    persist_ledger: bool = False,
    outcome_status: str | None = None,
) -> dict[str, Any]:
    """Consume one acknowledged command after its caller reports a terminal result.

    This function records proof only. It never executes the command.
    """
    current_time = ensure_utc(now)
    if outcome_status not in TERMINAL_EXECUTION_RECEIPT_STATUSES:
        raise ValueError(f"unsupported terminal execution outcome: {outcome_status}")
    if checkpoint.get("checkpoint_id") != checkpoint_id:
        raise ValueError(
            f"execution receipt checkpoint mismatch: expected={checkpoint.get('checkpoint_id')} received={checkpoint_id}"
        )
    if checkpoint.get("lane_id") and active_projection is None:
        raise ValueError("cannot record execution for a lane-bound checkpoint without a live active-lane projection")
    ledger_path = execution_ledger_file or execution_ledger_path(root)
    lock_context = execution_ledger_lock(ledger_path) if persist_ledger else nullcontext()
    with lock_context:
        ledger = load_execution_ledger(root, ledger_path)
        candidate = dict(checkpoint)
        candidate = (
            rebind_live_lease(
                candidate,
                active_projection,
                current_time,
                root=root,
                verify_changed_files=False,
            )
            if active_projection is not None
            else apply_evaluation(
                candidate,
                current_time,
                root=root,
                execution_ledger=ledger,
                verify_changed_files=False,
            )
        )
        existing = as_dict(candidate.get("execution_receipt"))
        expected_command_hash = exact_command_hash(candidate.get("exact_next_command"))
        if existing.get("status") in TERMINAL_EXECUTION_RECEIPT_STATUSES:
            if not (
                existing.get("status") == outcome_status
                and existing.get("checkpoint_id") == checkpoint_id
                and existing.get("exact_command_sha256") == expected_command_hash
                and existing.get("receipt_content_hash") == stable_hash(execution_receipt_content(existing))
            ):
                raise ValueError("terminal execution receipt already exists with a different outcome or identity")
            if ledger_record_for_checkpoint(ledger, candidate):
                return apply_evaluation(
                    candidate,
                    current_time,
                    root=root,
                    execution_ledger=ledger,
                    verify_changed_files=False,
                )
            raise ValueError("terminal execution receipt is missing from the monotonic ledger")
        evaluated = apply_evaluation(
            candidate,
            current_time,
            root=root,
            execution_ledger=ledger,
            verify_changed_files=False,
        )
        if as_dict(evaluated.get("validation")).get("status") == "critical":
            raise ValueError("cannot record execution for an invalid or stale resume checkpoint")
        if as_dict(evaluated.get("execution_gate")).get("command_authorized") is not True:
            raise ValueError("cannot record execution unless the exact command is currently authorized")
        if not proof_artifacts:
            raise ValueError("terminal execution receipt requires at least one proof artifact")
        receipt = {
            "status": outcome_status,
            "checkpoint_id": checkpoint_id,
            "exact_command_sha256": expected_command_hash,
            "executed_by": actor,
            "executed_at_utc": iso_utc(current_time),
            "proof_artifacts_and_hashes": hash_paths(root, proof_artifacts),
        }
        receipt["receipt_content_hash"] = stable_hash(execution_receipt_content(receipt))
        ledger = append_execution_ledger_record(ledger, receipt, current_time, root=root)
        if persist_ledger:
            atomic_write_json(ledger_path, ledger)
        evaluated["execution_receipt"] = receipt
        evaluated = refresh_checkpoint_state_hash(evaluated)
        return apply_evaluation(
            evaluated,
            current_time,
            root=root,
            execution_ledger=ledger,
            verify_changed_files=False,
        )


def cli_record(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "parent_job_id": args.parent_job_id,
        "workflow_id": args.workflow_id,
        "lane_id": args.lane_id,
        "workstream": args.workstream,
        "objective": args.objective,
        "status": args.checkpoint_status,
        "last_completed_step": args.last_completed_step,
        "in_progress_step": args.in_progress_step,
        "exact_next_action": args.exact_next_action,
        "exact_next_command": args.exact_next_command,
        "already_completed_do_not_repeat": args.already_completed,
        "changed_files": args.changed_file,
        "proof_artifacts": args.proof_artifact,
        "attempt_retry_identity": {
            "attempt_id": args.attempt_id,
            "attempt_number": args.attempt_number,
            "retry_count": args.retry_count,
        },
        "blocker": args.blocker,
        "approval_boundary": args.approval_boundary,
        "stop_lines": args.stop_line,
        "continuity_home": args.continuity_home,
        "safe_to_execute_automatically": args.safe_to_execute_automatically,
    }


def resolve_exact_next_command(raw: str | None, encoded: str | None) -> str | None:
    """Decode an argument-safe command transport without changing command text."""
    if raw and encoded:
        raise ValueError("--exact-next-command and --exact-next-command-base64 are mutually exclusive")
    if not encoded:
        return raw
    try:
        return base64.b64decode(encoded.encode("ascii"), validate=True).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("--exact-next-command-base64 is not valid UTF-8 Base64") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Build, acknowledge, or consume the canonical session resume checkpoint.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--record", action="store_true", help="Record an explicit task cursor rather than derive one from lane state.")
    parser.add_argument("--acknowledge", metavar="CHECKPOINT_ID")
    parser.add_argument("--acknowledged-by", default="main-session")
    parser.add_argument("--record-execution", metavar="CHECKPOINT_ID")
    parser.add_argument("--executed-by", default="main-session")
    parser.add_argument(
        "--execution-status",
        choices=sorted(TERMINAL_EXECUTION_RECEIPT_STATUSES),
        default=None,
        help="Terminal result reported by the caller; both outcomes consume replay authorization.",
    )
    parser.add_argument("--execution-proof-artifact", action="append", default=[])
    parser.add_argument("--execution-ledger", type=Path, default=EXECUTION_LEDGER)
    parser.add_argument("--parent-job-id")
    parser.add_argument("--workflow-id")
    parser.add_argument("--lane-id")
    parser.add_argument("--workstream")
    parser.add_argument("--objective")
    parser.add_argument("--status-value", dest="checkpoint_status", default="in_progress")
    parser.add_argument("--last-completed-step")
    parser.add_argument("--in-progress-step")
    parser.add_argument("--exact-next-action")
    parser.add_argument("--exact-next-command")
    parser.add_argument(
        "--exact-next-command-base64",
        help="Argument-safe UTF-8 Base64 transport for an exact command containing Windows quotes or spaces.",
    )
    parser.add_argument("--already-completed", action="append", default=[])
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--proof-artifact", action="append", default=[])
    parser.add_argument("--attempt-id")
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--retry-count", type=int)
    parser.add_argument("--blocker")
    parser.add_argument("--approval-boundary")
    parser.add_argument("--stop-line", action="append", default=[])
    parser.add_argument("--continuity-home")
    parser.add_argument("--safe-to-execute-automatically", action="store_true")
    parser.add_argument("--freshness-hours", type=float, default=DEFAULT_FRESHNESS_HOURS)
    parser.add_argument("--lane-register", type=Path, default=LANE_REGISTER)
    parser.add_argument("--out", type=Path, default=CURRENT_RESUME)
    parser.add_argument("--active-out", type=Path, default=CURRENT_ACTIVE_LANES)
    args = parser.parse_args()

    try:
        args.exact_next_command = resolve_exact_next_command(
            args.exact_next_command,
            args.exact_next_command_base64,
        )
    except ValueError as exc:
        parser.error(str(exc))

    now = ensure_utc()
    if args.acknowledge and args.record_execution:
        parser.error("--acknowledge and --record-execution are mutually exclusive")
    if args.record_execution and args.execution_status is None:
        parser.error("--execution-status is required with --record-execution; success is never inferred")
    if args.execution_status is not None and not args.record_execution:
        parser.error("--execution-status is valid only with --record-execution")
    if args.acknowledge:
        checkpoint = as_dict(load_json_artifact(args.out))
        live_lane_register = as_dict(load_json_artifact(args.lane_register))
        projection = project_active_lanes(live_lane_register, now)
        try:
            checkpoint = acknowledge_checkpoint(
                checkpoint,
                args.acknowledge,
                args.acknowledged_by,
                now,
                root=ROOT,
                active_projection=projection,
            )
        except ValueError as exc:
            print(f"status=blocked acknowledgement=failed detail={exc}")
            return 1
        if args.write:
            atomic_write_json(args.out, checkpoint)
    elif args.record_execution:
        checkpoint = as_dict(load_json_artifact(args.out))
        live_lane_register = as_dict(load_json_artifact(args.lane_register))
        projection = project_active_lanes(live_lane_register, now)
        try:
            checkpoint = record_execution_receipt(
                checkpoint,
                args.record_execution,
                args.executed_by,
                now,
                root=ROOT,
                active_projection=projection,
                proof_artifacts=args.execution_proof_artifact,
                execution_ledger_file=args.execution_ledger,
                persist_ledger=args.write,
                outcome_status=args.execution_status,
            )
        except ValueError as exc:
            print(f"status=blocked execution_receipt=failed detail={exc}")
            return 1
        if args.write:
            atomic_write_json(args.out, checkpoint)
    else:
        record = cli_record(args) if args.record else None
        checkpoint, projection = refresh_outputs(
            root=ROOT,
            tmp=args.lane_register.parent,
            now=now,
            record=record,
            freshness_hours=args.freshness_hours,
            write=args.write,
            resume_out=args.out,
            active_out=args.active_out,
        )

    validation = as_dict(checkpoint.get("validation"))
    print(json.dumps({
        "status": checkpoint.get("resume_status"),
        "validation_status": validation.get("status"),
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "lane_id": checkpoint.get("lane_id"),
        "resolution": as_dict(checkpoint.get("selection")).get("resolution"),
        "active_lane_count": projection.get("active_lane_count"),
        "command_authorized": as_dict(checkpoint.get("execution_gate")).get("command_authorized"),
        "written": [str(args.out), str(args.active_out)] if args.write and not (args.acknowledge or args.record_execution) else (
            ([str(args.out), str(args.execution_ledger)] if args.record_execution else [str(args.out)])
            if args.write else []
        ),
    }, indent=2))
    if args.validate and validation.get("status") == "critical":
        for finding in as_list(validation.get("findings")):
            print(f"  [{as_dict(finding).get('severity')}] {as_dict(finding).get('detail')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
