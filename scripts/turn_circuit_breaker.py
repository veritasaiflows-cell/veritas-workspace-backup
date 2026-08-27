#!/usr/bin/env python3
"""Fail-closed per-turn budget guard with durable checkpoint and resume.

This is a workspace-local cooperative enforcement primitive. A runtime or orchestrator calls
``start`` once, reports absolute per-turn observations with ``observe``, and
calls ``preflight`` before dispatching another tool. Reaching either hard limit
atomically writes a checkpoint and blocks further dispatch until ``resume`` is
called with a different turn id.

The guard does not intercept native Codex/OpenClaw calls by itself. It is built
for direct use by workspace runners now and for a separately approved runtime
hook later. It stores counters, hashes, and bounded operator-supplied summaries.
It has no dedicated raw-prompt or raw-tool-payload fields, but it cannot
semantically classify caller-supplied summary text.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable

try:
    from long_work_job_runtime import atomic_write_json, load_json, normalize_job_id, utc_now
except ModuleNotFoundError:  # Supports ``python -m unittest scripts.test_...`` from workspace root.
    from scripts.long_work_job_runtime import atomic_write_json, load_json, normalize_job_id, utc_now


ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = ROOT / "state" / "turn-circuit-breaker"

SCHEMA = "veritas.turn_circuit_breaker.v1"
CHECKPOINT_SCHEMA = "veritas.turn_circuit_breaker_checkpoint.v1"
POLICY_SCHEMA = "veritas.turn_circuit_breaker_policy.v1"

HARD_MAX_TOOL_CALLS = 30
HARD_MAX_CONTEXT_TOKENS = 60_000
WARNING_TOOL_CALLS = 24
WARNING_CONTEXT_TOKENS = 48_000

RUNNING = "running"
CHECKPOINTED = "checkpointed"
COMPLETE = "complete"
VALID_STATUSES = {RUNNING, CHECKPOINTED, COMPLETE}
VALID_VALIDATION_STATES = {"not_run", "ok", "warning", "blocked", "error"}

POLICY = {
    "schema": POLICY_SCHEMA,
    "owner": "scripts/turn_circuit_breaker.py",
    "hard_limits": {
        "tool_calls": HARD_MAX_TOOL_CALLS,
        "context_tokens": HARD_MAX_CONTEXT_TOKENS,
    },
    "warning_thresholds": {
        "tool_calls": WARNING_TOOL_CALLS,
        "context_tokens": WARNING_CONTEXT_TOKENS,
    },
    "semantics": {
        "hard_limit_comparison": "observed_greater_than_or_equal_to_limit",
        "tool_limit_meaning": "calls_1_through_30_allowed; call_31_blocked",
        "context_limit_meaning": "current_turn_context_estimate_not_cumulative_gross_tokens",
        "counter_updates": "absolute_monotonic_per_attempt",
        "checkpoint_before_block_state": True,
        "fresh_turn_id_required_to_resume": True,
        "single_writer_required": True,
        "single_writer_enforced_by_job_lock": True,
        "stale_writer_rejected_by_revision": True,
        "runtime_interceptor_included": False,
        "observation_trust": "caller_supplied_unverified_without_runtime_hook",
        "fresh_turn_trust": "caller_supplied_unverified_without_runtime_hook",
    },
    "authority_boundary": {
        "workspace_local_state_only": True,
        "raw_prompt_or_tool_payload_capture_allowed": False,
        "runtime_or_plugin_mutation_allowed": False,
        "external_action_allowed": False,
        "owner_approval_inferred": False,
    },
}


class GuardError(ValueError):
    """Raised when a circuit-breaker transition is invalid."""


def normalize_turn_id(value: str) -> str:
    cleaned = normalize_job_id(value)
    if len(cleaned) > 120:
        raise GuardError("turn_id exceeds 120 characters after normalization")
    return cleaned


def state_dir(job_id: str) -> Path:
    return STATE_ROOT / normalize_job_id(job_id)


def state_path(job_id: str) -> Path:
    return state_dir(job_id) / "state.json"


def checkpoint_path(job_id: str) -> Path:
    return state_dir(job_id) / "checkpoint.json"


def event_path(job_id: str) -> Path:
    return state_dir(job_id) / "events.jsonl"


def lock_path(job_id: str) -> Path:
    return state_dir(job_id) / "state.lock"


@contextmanager
def job_lock(job_id: str, timeout_seconds: float = 5.0):
    """Hold a one-byte cross-platform advisory lock for one job transition."""
    path = lock_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    deadline = time.monotonic() + timeout_seconds
    locked = False
    try:
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise GuardError("timed out acquiring the per-job circuit-breaker lock") from exc
                time.sleep(0.025)
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bounded_text(value: Any, field: str, *, required: bool = False, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise GuardError(f"{field} is required")
    if len(text) > max_length:
        raise GuardError(f"{field} exceeds {max_length} characters")
    if "\n" in text or "\r" in text:
        raise GuardError(f"{field} must be a one-line operator summary")
    return text


def nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise GuardError(f"{field} must be a nonnegative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise GuardError(f"{field} must be a nonnegative integer") from exc
    if parsed < 0:
        raise GuardError(f"{field} must be a nonnegative integer")
    return parsed


def dedupe_text(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = bounded_text(value, "completed_step", max_length=500)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def resolve_artifact(reference: str) -> dict[str, Any]:
    raw = bounded_text(reference, "artifact", required=True, max_length=500)
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            display = resolved.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            display = resolved.as_posix()
    else:
        resolved = (ROOT / candidate).resolve()
        try:
            display = resolved.relative_to(ROOT.resolve()).as_posix()
        except ValueError as exc:
            raise GuardError(f"artifact path escapes workspace: {raw}") from exc
    if not resolved.exists() or not resolved.is_file():
        return {"path": display, "exists": False, "sha256": None, "bytes": None}
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {"path": display, "exists": True, "sha256": digest, "bytes": resolved.stat().st_size}


def capture_artifacts(references: Iterable[str]) -> list[dict[str, Any]]:
    rows = [resolve_artifact(item) for item in references]
    return sorted({row["path"]: row for row in rows}.values(), key=lambda row: row["path"])


def write_event(job_id: str, event: str, state: dict[str, Any], detail: dict[str, Any] | None = None) -> None:
    path = event_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at_utc": utc_now(),
        "job_id": normalize_job_id(job_id),
        "attempt_number": state.get("attempt_number"),
        "turn_id": state.get("turn_id"),
        "event": event,
        "status": state.get("status"),
        "detail": detail or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def load_state(job_id: str) -> dict[str, Any]:
    state = load_json(state_path(job_id))
    if not state:
        raise GuardError(f"turn circuit-breaker state is missing for {normalize_job_id(job_id)}")
    integrity_errors = state_integrity_errors(state)
    if integrity_errors:
        raise GuardError("state integrity failed: " + ",".join(integrity_errors))
    return state


def state_integrity_hash(state: dict[str, Any]) -> str:
    payload = dict(state)
    payload.pop("state_hash", None)
    return canonical_hash(payload)


def state_integrity_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    revision = state.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        errors.append("state_revision_invalid")
    if state.get("state_hash") != state_integrity_hash(state):
        errors.append("state_hash_mismatch")
    return errors


def limits_for(*, max_tool_calls: int, max_context_tokens: int) -> dict[str, int]:
    tools = nonnegative_int(max_tool_calls, "max_tool_calls")
    tokens = nonnegative_int(max_context_tokens, "max_context_tokens")
    if tools < 1 or tools > HARD_MAX_TOOL_CALLS:
        raise GuardError(f"max_tool_calls must be between 1 and {HARD_MAX_TOOL_CALLS}")
    if tokens < 1 or tokens > HARD_MAX_CONTEXT_TOKENS:
        raise GuardError(f"max_context_tokens must be between 1 and {HARD_MAX_CONTEXT_TOKENS}")
    return {"tool_calls": tools, "context_tokens": tokens}


def evaluate(observed: dict[str, int], limits: dict[str, int]) -> dict[str, Any]:
    breaches = [key for key in ("tool_calls", "context_tokens") if observed[key] >= limits[key]]
    warnings = [
        key
        for key, threshold in (("tool_calls", min(WARNING_TOOL_CALLS, limits["tool_calls"])), ("context_tokens", min(WARNING_CONTEXT_TOKENS, limits["context_tokens"])))
        if observed[key] >= threshold and key not in breaches
    ]
    return {
        "status": "tripped" if breaches else ("warning" if warnings else "ok"),
        "breaches": breaches,
        "warnings": warnings,
        "tool_dispatch_allowed": not breaches,
        "resume_required": bool(breaches),
    }


def resume_command(job_id: str) -> str:
    return f"python scripts\\turn_circuit_breaker.py --pretty resume --job-id {normalize_job_id(job_id)} --turn-id <fresh-turn-id>"


def new_state(
    *,
    job_id: str,
    turn_id: str,
    objective: str,
    next_action: str,
    owner_workflow: str,
    max_tool_calls: int = HARD_MAX_TOOL_CALLS,
    max_context_tokens: int = HARD_MAX_CONTEXT_TOKENS,
    completed_steps: Iterable[str] = (),
    artifacts: Iterable[str] = (),
) -> dict[str, Any]:
    now = utc_now()
    normalized_job = normalize_job_id(job_id)
    state = {
        "schema": SCHEMA,
        "policy_schema": POLICY_SCHEMA,
        "job_id": normalized_job,
        "owner_workflow": bounded_text(owner_workflow, "owner_workflow", required=True, max_length=120),
        "objective": bounded_text(objective, "objective", required=True),
        "status": RUNNING,
        "revision": 0,
        "state_hash": None,
        "attempt_number": 1,
        "turn_id": normalize_turn_id(turn_id),
        "created_at_utc": now,
        "updated_at_utc": now,
        "started_at_utc": now,
        "completed_at_utc": None,
        "limits": limits_for(max_tool_calls=max_tool_calls, max_context_tokens=max_context_tokens),
        "observed": {"tool_calls": 0, "context_tokens": 0},
        "guard": {},
        "completed_steps": dedupe_text(completed_steps),
        "artifacts": capture_artifacts(artifacts),
        "last_successful_tool": None,
        "next_action": bounded_text(next_action, "next_action", required=True),
        "validation_status": "not_run",
        "resume_command": resume_command(normalized_job),
        "resume_required": False,
        "tool_dispatch_allowed": True,
        "checkpoint": None,
        "resumed_from_checkpoint": None,
        "attempt_history": [],
        "authority_boundary": dict(POLICY["authority_boundary"]),
        "observation_trust": "caller_supplied_unverified_without_runtime_hook",
        "fresh_turn_trust": "caller_supplied_unverified_without_runtime_hook",
        "enforcement_level": "cooperative_workspace_guard",
    }
    state["guard"] = evaluate(state["observed"], state["limits"])
    return state


def persist_state(
    state: dict[str, Any],
    event: str,
    detail: dict[str, Any] | None = None,
    *,
    adjacent_json: Iterable[tuple[Path, dict[str, Any]]] = (),
) -> dict[str, Any]:
    state = dict(state)
    job_id = str(state["job_id"])
    path = state_path(job_id)
    with job_lock(job_id):
        current = load_json(path)
        incoming_revision = state.get("revision")
        if current:
            integrity_errors = state_integrity_errors(current)
            if integrity_errors:
                raise GuardError("persisted state integrity failed: " + ",".join(integrity_errors))
            if incoming_revision != current.get("revision"):
                raise GuardError("stale state transition rejected by revision check")
        elif incoming_revision != 0:
            raise GuardError("new state must begin at revision 0")
        state["revision"] = int(incoming_revision) + 1
        state["updated_at_utc"] = utc_now()
        state["state_hash"] = state_integrity_hash(state)
        atomic_write_json(path, state)
        for adjacent_path, adjacent_payload in adjacent_json:
            atomic_write_json(adjacent_path, adjacent_payload)
        write_event(job_id, event, state, detail)
    return state


def checkpoint_payload(state: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "job_id": state["job_id"],
        "owner_workflow": state["owner_workflow"],
        "attempt_number": state["attempt_number"],
        "turn_id": state["turn_id"],
        "captured_at_utc": utc_now(),
        "reasons": reasons,
        "limits": state["limits"],
        "observed": state["observed"],
        "objective": state["objective"],
        "completed_steps": state["completed_steps"],
        "artifacts": state["artifacts"],
        "last_successful_tool": state.get("last_successful_tool"),
        "next_action": state["next_action"],
        "validation_status": state["validation_status"],
        "resume_command": state["resume_command"],
        "raw_prompt_or_tool_payload_fields_in_schema": False,
        "caller_summary_text_semantically_inspected": False,
    }
    payload["checkpoint_id"] = canonical_hash(payload)
    return payload


def checkpoint_state(state: dict[str, Any], reasons: list[str], *, event: str) -> dict[str, Any]:
    checkpoint = checkpoint_payload(state, reasons)
    path = checkpoint_path(str(state["job_id"]))
    state = dict(state)
    state["status"] = CHECKPOINTED
    state["resume_required"] = True
    state["tool_dispatch_allowed"] = False
    state["guard"] = {**evaluate(state["observed"], state["limits"]), "status": "tripped" if reasons != ["manual_checkpoint"] else "checkpointed", "resume_required": True, "tool_dispatch_allowed": False}
    state["checkpoint"] = {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix() if path.resolve().is_relative_to(ROOT.resolve()) else path.as_posix(),
        "checkpoint_id": checkpoint["checkpoint_id"],
        "captured_at_utc": checkpoint["captured_at_utc"],
        "reasons": reasons,
        "payload": checkpoint,
    }
    # One atomic state write contains both the fail-closed transition and the
    # full checkpoint. The adjacent checkpoint file is a convenient mirror;
    # losing power between the two writes still leaves a resumable blocked
    # state rather than a running state with no checkpoint.
    return persist_state(
        state,
        event,
        {"checkpoint_id": checkpoint["checkpoint_id"], "reasons": reasons},
        adjacent_json=[(path, checkpoint)],
    )


def require_active_turn(state: dict[str, Any], turn_id: str) -> None:
    if state.get("status") != RUNNING:
        raise GuardError("tool dispatch is blocked; resume from the durable checkpoint in a fresh turn")
    if normalize_turn_id(turn_id) != state.get("turn_id"):
        raise GuardError("turn_id does not match the active attempt")


def update_progress(
    state: dict[str, Any],
    *,
    turn_id: str,
    tool_calls: int,
    context_tokens: int,
    completed_steps: Iterable[str] = (),
    artifacts: Iterable[str] = (),
    last_successful_tool: str = "",
    next_action: str = "",
    validation_status: str = "",
) -> dict[str, Any]:
    require_active_turn(state, turn_id)
    observed = {
        "tool_calls": nonnegative_int(tool_calls, "tool_calls"),
        "context_tokens": nonnegative_int(context_tokens, "context_tokens"),
    }
    previous = state["observed"]
    for key in observed:
        if observed[key] < int(previous[key]):
            raise GuardError(f"{key} cannot decrease within an attempt")
    state = dict(state)
    state["observed"] = observed
    state["completed_steps"] = dedupe_text([*state.get("completed_steps", []), *completed_steps])
    if artifacts:
        by_path = {row["path"]: row for row in state.get("artifacts", [])}
        by_path.update({row["path"]: row for row in capture_artifacts(artifacts)})
        state["artifacts"] = sorted(by_path.values(), key=lambda row: row["path"])
    if last_successful_tool:
        state["last_successful_tool"] = bounded_text(last_successful_tool, "last_successful_tool", max_length=500)
    if next_action:
        state["next_action"] = bounded_text(next_action, "next_action", required=True)
    if validation_status:
        if validation_status not in VALID_VALIDATION_STATES:
            raise GuardError("validation_status is invalid")
        state["validation_status"] = validation_status
    state["guard"] = evaluate(observed, state["limits"])
    state["tool_dispatch_allowed"] = state["guard"]["tool_dispatch_allowed"]
    state["resume_required"] = state["guard"]["resume_required"]
    if state["guard"]["breaches"]:
        reasons = [f"{key}_limit_reached" for key in state["guard"]["breaches"]]
        return checkpoint_state(state, reasons, event="hard_limit_checkpointed")
    return persist_state(state, "observation_recorded", {"guard_status": state["guard"]["status"]})


def preflight(state: dict[str, Any], *, turn_id: str, tool_calls: int, context_tokens: int) -> dict[str, Any]:
    state = update_progress(state, turn_id=turn_id, tool_calls=tool_calls, context_tokens=context_tokens)
    return {
        "status": "allowed" if state["tool_dispatch_allowed"] else "blocked",
        "job_id": state["job_id"],
        "turn_id": state["turn_id"],
        "attempt_number": state["attempt_number"],
        "limits": state["limits"],
        "observed": state["observed"],
        "guard": state["guard"],
        "next_action": state["next_action"],
        "checkpoint": state.get("checkpoint"),
    }


def resume_state(state: dict[str, Any], *, fresh_turn_id: str) -> dict[str, Any]:
    if state.get("status") != CHECKPOINTED or state.get("resume_required") is not True:
        raise GuardError("resume requires a checkpointed attempt")
    new_turn = normalize_turn_id(fresh_turn_id)
    if new_turn == state.get("turn_id"):
        raise GuardError("resume requires a different fresh turn_id")
    validation = validate_state(state)
    if validation["errors"]:
        raise GuardError("checkpointed state failed validation: " + ",".join(validation["errors"]))
    authoritative_checkpoint = dict((state.get("checkpoint") or {}).get("payload") or {})
    previous_attempt = {
        "attempt_number": state["attempt_number"],
        "turn_id": state["turn_id"],
        "observed": state["observed"],
        "checkpoint": state["checkpoint"],
        "ended_at_utc": utc_now(),
    }
    state = dict(state)
    state["attempt_history"] = [*state.get("attempt_history", []), previous_attempt]
    state["attempt_number"] = int(state["attempt_number"]) + 1
    state["turn_id"] = new_turn
    state["status"] = RUNNING
    state["started_at_utc"] = utc_now()
    state["completed_at_utc"] = None
    state["observed"] = {"tool_calls": 0, "context_tokens": 0}
    state["guard"] = evaluate(state["observed"], state["limits"])
    state["resume_required"] = False
    state["tool_dispatch_allowed"] = True
    state["resumed_from_checkpoint"] = previous_attempt["checkpoint"]
    state["checkpoint"] = None
    return persist_state(
        state,
        "resumed_in_fresh_turn",
        {"previous_turn_id": previous_attempt["turn_id"]},
        adjacent_json=[(checkpoint_path(str(state["job_id"])), authoritative_checkpoint)],
    )


def complete_state(state: dict[str, Any], *, turn_id: str, validation_status: str) -> dict[str, Any]:
    require_active_turn(state, turn_id)
    if validation_status not in {"ok", "warning"}:
        raise GuardError("completion requires validation_status ok or warning")
    state = dict(state)
    state["status"] = COMPLETE
    state["validation_status"] = validation_status
    state["completed_at_utc"] = utc_now()
    state["tool_dispatch_allowed"] = False
    state["resume_required"] = False
    return persist_state(state, "completed")


def validate_checkpoint(job_id: str, reference: dict[str, Any]) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    embedded = reference.get("payload") if isinstance(reference.get("payload"), dict) else {}
    if not embedded:
        return {"errors": ["embedded_checkpoint_missing"], "warnings": []}
    payload = dict(embedded)
    if payload.get("schema") != CHECKPOINT_SCHEMA:
        errors.append("checkpoint_schema_mismatch")
    checkpoint_id = payload.pop("checkpoint_id", None)
    if checkpoint_id != canonical_hash(payload):
        errors.append("checkpoint_hash_mismatch")
    if checkpoint_id != reference.get("checkpoint_id"):
        errors.append("checkpoint_reference_mismatch")
    for field in ("job_id", "turn_id", "objective", "next_action", "resume_command", "captured_at_utc"):
        if not payload.get(field):
            errors.append(f"checkpoint_missing:{field}")
    if payload.get("raw_prompt_or_tool_payload_fields_in_schema") is not False:
        errors.append("checkpoint_raw_field_boundary_failed")
    if payload.get("caller_summary_text_semantically_inspected") is not False:
        errors.append("checkpoint_summary_inspection_claim_invalid")
    mirror = load_json(checkpoint_path(job_id))
    if not mirror:
        warnings.append("checkpoint_mirror_missing_embedded_checkpoint_authoritative")
    else:
        mirror_payload = dict(mirror)
        mirror_id = mirror_payload.pop("checkpoint_id", None)
        if mirror_id != canonical_hash(mirror_payload) or mirror_id != checkpoint_id:
            warnings.append("checkpoint_mirror_stale_or_mismatched_embedded_checkpoint_authoritative")
    return {"errors": errors, "warnings": warnings}


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(state_integrity_errors(state))
    if state.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    for field in ("job_id", "owner_workflow", "objective", "status", "turn_id", "limits", "observed", "next_action", "resume_command"):
        if state.get(field) in (None, "", {}):
            errors.append(f"missing_required_field:{field}")
    if state.get("status") not in VALID_STATUSES:
        errors.append("invalid_status")
    try:
        limits = limits_for(
            max_tool_calls=state.get("limits", {}).get("tool_calls"),
            max_context_tokens=state.get("limits", {}).get("context_tokens"),
        )
        observed = {
            "tool_calls": nonnegative_int(state.get("observed", {}).get("tool_calls"), "tool_calls"),
            "context_tokens": nonnegative_int(state.get("observed", {}).get("context_tokens"), "context_tokens"),
        }
    except GuardError as exc:
        errors.append(str(exc))
        limits = {"tool_calls": HARD_MAX_TOOL_CALLS, "context_tokens": HARD_MAX_CONTEXT_TOKENS}
        observed = {"tool_calls": 0, "context_tokens": 0}
    expected = evaluate(observed, limits)
    status = state.get("status")
    if expected["breaches"] and status != CHECKPOINTED:
        errors.append("hard_limit_not_checkpointed")
    if status == CHECKPOINTED:
        if state.get("resume_required") is not True or state.get("tool_dispatch_allowed") is not False:
            errors.append("checkpointed_state_not_fail_closed")
        checkpoint_validation = validate_checkpoint(str(state.get("job_id") or ""), state.get("checkpoint") or {})
        errors.extend(checkpoint_validation["errors"])
        warnings.extend(checkpoint_validation["warnings"])
    elif status == RUNNING:
        if state.get("resume_required") is not False or state.get("tool_dispatch_allowed") is not True:
            errors.append("running_state_dispatch_contract_invalid")
        if expected["breaches"]:
            errors.append("running_state_over_limit")
    elif status == COMPLETE and state.get("tool_dispatch_allowed") is not False:
        errors.append("complete_state_dispatch_still_allowed")
    if state.get("validation_status") not in VALID_VALIDATION_STATES:
        errors.append("invalid_validation_status")
    if state.get("enforcement_level") != "cooperative_workspace_guard":
        errors.append("enforcement_level_misclassified")
    if state.get("observation_trust") != "caller_supplied_unverified_without_runtime_hook":
        errors.append("observation_trust_misclassified")
    if state.get("fresh_turn_trust") != "caller_supplied_unverified_without_runtime_hook":
        errors.append("fresh_turn_trust_misclassified")
    boundary = state.get("authority_boundary") or {}
    for key in ("raw_prompt_or_tool_payload_capture_allowed", "runtime_or_plugin_mutation_allowed", "external_action_allowed", "owner_approval_inferred"):
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_failed:{key}")
    if expected["warnings"] and status == RUNNING:
        warnings.append("warning_threshold_reached")
    return {"status": "error" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=None, help="Override state root for isolated testing.")
    parser.add_argument("--pretty", action="store_true")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("policy")

    start = sub.add_parser("start")
    start.add_argument("--job-id", required=True)
    start.add_argument("--turn-id", required=True)
    start.add_argument("--owner-workflow", default="WF88")
    start.add_argument("--objective", required=True)
    start.add_argument("--next-action", required=True)
    start.add_argument("--max-tool-calls", type=int, default=HARD_MAX_TOOL_CALLS)
    start.add_argument("--max-context-tokens", type=int, default=HARD_MAX_CONTEXT_TOKENS)
    start.add_argument("--completed-step", action="append", default=[])
    start.add_argument("--artifact", action="append", default=[])

    for action in ("observe", "preflight"):
        command = sub.add_parser(action)
        command.add_argument("--job-id", required=True)
        command.add_argument("--turn-id", required=True)
        command.add_argument("--tool-calls", type=int, required=True)
        command.add_argument("--context-tokens", type=int, required=True)
        if action == "observe":
            command.add_argument("--completed-step", action="append", default=[])
            command.add_argument("--artifact", action="append", default=[])
            command.add_argument("--last-successful-tool", default="")
            command.add_argument("--next-action", default="")
            command.add_argument("--validation-status", choices=sorted(VALID_VALIDATION_STATES), default="")

    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--job-id", required=True)
    checkpoint.add_argument("--turn-id", required=True)

    resume = sub.add_parser("resume")
    resume.add_argument("--job-id", required=True)
    resume.add_argument("--turn-id", required=True, help="Fresh turn id; must differ from the checkpointed turn.")

    complete = sub.add_parser("complete")
    complete.add_argument("--job-id", required=True)
    complete.add_argument("--turn-id", required=True)
    complete.add_argument("--validation-status", choices=("ok", "warning"), required=True)

    for action in ("status", "validate"):
        command = sub.add_parser(action)
        command.add_argument("--job-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    global STATE_ROOT
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.state_root is not None:
        STATE_ROOT = args.state_root.resolve()
    try:
        if args.action == "policy":
            payload: dict[str, Any] = POLICY
        elif args.action == "start":
            path = state_path(args.job_id)
            if path.exists():
                raise GuardError("state already exists; use status, checkpoint, resume, or a new job_id")
            payload = persist_state(
                new_state(
                    job_id=args.job_id,
                    turn_id=args.turn_id,
                    objective=args.objective,
                    next_action=args.next_action,
                    owner_workflow=args.owner_workflow,
                    max_tool_calls=args.max_tool_calls,
                    max_context_tokens=args.max_context_tokens,
                    completed_steps=args.completed_step,
                    artifacts=args.artifact,
                ),
                "started",
            )
        elif args.action == "observe":
            payload = update_progress(
                load_state(args.job_id),
                turn_id=args.turn_id,
                tool_calls=args.tool_calls,
                context_tokens=args.context_tokens,
                completed_steps=args.completed_step,
                artifacts=args.artifact,
                last_successful_tool=args.last_successful_tool,
                next_action=args.next_action,
                validation_status=args.validation_status,
            )
        elif args.action == "preflight":
            payload = preflight(
                load_state(args.job_id),
                turn_id=args.turn_id,
                tool_calls=args.tool_calls,
                context_tokens=args.context_tokens,
            )
        elif args.action == "checkpoint":
            state = load_state(args.job_id)
            require_active_turn(state, args.turn_id)
            payload = checkpoint_state(state, ["manual_checkpoint"], event="manual_checkpointed")
        elif args.action == "resume":
            payload = resume_state(load_state(args.job_id), fresh_turn_id=args.turn_id)
        elif args.action == "complete":
            payload = complete_state(load_state(args.job_id), turn_id=args.turn_id, validation_status=args.validation_status)
        elif args.action == "status":
            payload = load_state(args.job_id)
        else:
            state = load_state(args.job_id)
            payload = {"job_id": state["job_id"], "validation": validate_state(state), "state": state}
    except GuardError as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
        return 1

    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    if args.action == "validate":
        return 0 if payload["validation"]["status"] in {"ok", "warning"} else 1
    status = payload.get("status")
    guard = payload.get("guard") or {}
    if status == CHECKPOINTED or guard.get("tool_dispatch_allowed") is False or status == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
