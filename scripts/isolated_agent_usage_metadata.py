#!/usr/bin/env python3
"""Read allowlisted OpenClaw isolated-agent session usage metadata safely.

Only ``sessions/sessions.json`` is opened.  Session transcripts, ``sessionFile``
targets, prompts, responses, tool payloads, auth-profile values, and delivery
identities are deliberately ignored.  Returned records contain a strict
allowlist of usage/provenance fields and hashed session references.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import shutil
import subprocess
from base64 import b32encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CONFIGURED_ISOLATED_AGENT_ROLES: dict[str, str] = {
    "docs-continuity-editor": "continuity_editor",
    "finance-redteam": "finance_redteam",
    "finance-source-scout": "finance_source_scout",
    "implementation-builder": "implementation_builder",
    "qa-redteam": "qa_redteam",
    "research-scout": "research_scout",
}
CONFIGURED_ISOLATED_AGENT_IDS = tuple(sorted(CONFIGURED_ISOLATED_AGENT_ROLES))
DEFAULT_AGENT_STATE_ROOT = Path.home() / ".openclaw" / "agents"
DEFAULT_OPENCLAW_STATE_DB = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"
TERMINAL_SESSION_STATUSES = {"done"}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SAFE_CORRELATION_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
SCHEMA = "veritas.isolated_agent_usage_metadata.v1"
ATTEMPT_CORRELATION_KEY_VERSION = "veritas.isolated_attempt_correlation.v1"
DISPATCH_BINDING_SCHEMA = "veritas.isolated_dispatch_binding.v1"
DISPATCH_BINDING_TASK_NAME_PREFIX = "vt1_"
DISPATCH_BINDING_TASK_NAME_RE = re.compile(r"^vt1_[a-z2-7]{52}$")
SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
TOKEN_FIELDS = ("inputTokens", "cacheRead", "cacheWrite", "outputTokens", "totalTokens")
VALID_THINKING_LEVELS = frozenset({"low", "medium", "high"})
GATEWAY_USAGE_FIELDS = (
    "date",
    "input",
    "output",
    "cacheRead",
    "cacheWrite",
    "totalTokens",
    "totalCost",
    "missingCostEntries",
)
# ``fresh`` is the current Gateway usage-cost clean-cache value.  ``ok`` is
# retained for compatibility with earlier additive Gateway responses.
CLEAN_GATEWAY_CACHE_STATUSES = frozenset({"fresh", "ok"})


def hash_reference(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def full_hash_reference(value: Any) -> str | None:
    """Return the full SHA-256 digest used by the protected core ledger."""
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task_name_for_attempt(*, attempt_correlation_hash: str) -> str:
    """Encode one full attempt digest as an opaque valid OpenClaw task name."""
    if not isinstance(attempt_correlation_hash, str) or not SHA256_HEX_RE.fullmatch(attempt_correlation_hash):
        raise ValueError("attempt correlation hash must be a 64-character lowercase SHA-256 hex value")
    encoded = b32encode(bytes.fromhex(attempt_correlation_hash)).decode("ascii").lower().rstrip("=")
    task_name = f"{DISPATCH_BINDING_TASK_NAME_PREFIX}{encoded}"
    if not DISPATCH_BINDING_TASK_NAME_RE.fullmatch(task_name):
        raise ValueError("dispatch binding task name did not meet the bounded opaque format")
    return task_name


def dispatch_binding_token_hash_for_attempt(*, attempt_correlation_hash: str) -> str:
    """Return the one-way core-ledger key for a lane's deterministic attempt."""
    task_name = task_name_for_attempt(attempt_correlation_hash=attempt_correlation_hash)
    return hashlib.sha256(task_name.encode("ascii")).hexdigest()


def strict_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def safe_nonnegative_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def epoch_ms_to_utc(value: Any) -> str | None:
    epoch_ms = strict_nonnegative_int(value)
    if epoch_ms is None:
        return None
    try:
        parsed = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    if parsed.year < 2000 or parsed.year > 2100:
        return None
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_model_path(provider: Any, model: Any) -> str | None:
    if not isinstance(provider, str) or not isinstance(model, str):
        return None
    provider = provider.strip()
    model = model.strip()
    if not SAFE_COMPONENT.fullmatch(provider) or not SAFE_COMPONENT.fullmatch(model):
        return None
    return model if model.startswith(f"{provider}/") else f"{provider}/{model}"


def session_reference_hash(session_key: Any, session_id: Any) -> str | None:
    key_hash = hash_reference(session_key)
    session_id_hash = hash_reference(session_id)
    preferred = session_id_hash or key_hash
    return preferred


def isolated_session_run_id(agent_id: str, session_ref_hash: str, started_at_ms: int) -> str:
    seed = f"isolated-agent-run|{agent_id}|{session_ref_hash}|{started_at_ms}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def canonical_correlation_identifier(value: Any) -> str | None:
    """Return one bounded identifier suitable for correlation-key input."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not SAFE_CORRELATION_IDENTIFIER.fullmatch(normalized):
        return None
    return normalized


def normalize_correlation_phase(value: Any) -> str | None:
    """Normalize a bounded phase name without retaining caller formatting."""
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not normalized or len(normalized) > 64:
        return None
    return normalized


def build_attempt_correlation_key(
    *,
    parent_job_id: Any,
    lane_id: Any,
    phase: Any,
    attempt_id: Any = None,
    retry_count: Any = None,
) -> dict[str, str] | None:
    """Hash an explicit attempt identity without returning any raw identifiers.

    An explicit attempt ID is authoritative.  The retry-count variant is used
    only when the attempt ID is absent, and only for a real nonnegative integer;
    missing or malformed values never become an invented first attempt.
    """
    parent = canonical_correlation_identifier(parent_job_id)
    lane = canonical_correlation_identifier(lane_id)
    normalized_phase = normalize_correlation_phase(phase)
    if parent is None or lane is None or normalized_phase is None:
        return None

    source: str
    discriminator: str | int
    if attempt_id is not None:
        canonical_attempt = canonical_correlation_identifier(attempt_id)
        if canonical_attempt is None:
            return None
        source = "attempt_id"
        discriminator = canonical_attempt
    else:
        explicit_retry = strict_nonnegative_int(retry_count)
        if explicit_retry is None:
            return None
        source = "retry_count"
        discriminator = explicit_retry

    canonical = {
        "key_version": ATTEMPT_CORRELATION_KEY_VERSION,
        "parent_job_id": parent,
        "lane_id": lane,
        "phase": normalized_phase,
        "attempt_source": source,
        "attempt_value": discriminator,
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return {
        "key_version": ATTEMPT_CORRELATION_KEY_VERSION,
        "key_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "attempt_source": source,
    }


def _snapshot_fingerprint(record: dict[str, Any]) -> str:
    selected = {
        key: record.get(key)
        for key in (
            "agent_id",
            "session_ref_hash",
            "started_at_epoch_ms",
            "ended_at_epoch_ms",
            "model_path",
            "actual_thinking",
            "input_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "output_tokens",
            "source_input_total_tokens",
            "source_context_prompt_tokens",
            "source_context_prompt_semantics",
            "total_tokens",
            "source_total_tokens_fresh",
        )
    }
    if isinstance(record.get("attempt_correlation"), dict):
        selected["attempt_correlation"] = record["attempt_correlation"]
    if isinstance(record.get("dispatch_binding"), dict):
        selected["dispatch_binding"] = record["dispatch_binding"]
    raw = json.dumps(selected, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def extract_session_usage(
    agent_id: str,
    session_key: Any,
    entry: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return one sanitized usage record plus metadata-only validation errors."""
    errors: list[str] = []
    if agent_id not in CONFIGURED_ISOLATED_AGENT_ROLES:
        return None, ["agent_not_allowlisted"]
    if not isinstance(entry, dict):
        return None, ["session_entry_not_object"]

    status = entry.get("status")
    if status not in TERMINAL_SESSION_STATUSES:
        errors.append("session_not_terminal")
    if entry.get("totalTokensFresh") is not True:
        errors.append("total_tokens_not_fresh")

    counts: dict[str, int] = {}
    for source_key in TOKEN_FIELDS:
        parsed = strict_nonnegative_int(entry.get(source_key))
        if parsed is None:
            errors.append(f"invalid_{source_key}")
        else:
            counts[source_key] = parsed

    started_at_ms = strict_nonnegative_int(entry.get("startedAt"))
    ended_at_ms = strict_nonnegative_int(entry.get("endedAt"))
    started_at_utc = epoch_ms_to_utc(started_at_ms)
    ended_at_utc = epoch_ms_to_utc(ended_at_ms)
    if started_at_ms is None or started_at_utc is None:
        errors.append("invalid_startedAt")
    if ended_at_ms is None or ended_at_utc is None:
        errors.append("invalid_endedAt")
    if started_at_ms is not None and ended_at_ms is not None and ended_at_ms < started_at_ms:
        errors.append("ended_before_started")

    session_id = entry.get("sessionId")
    session_key_hash = hash_reference(session_key)
    session_id_hash = hash_reference(session_id)
    session_ref_hash = session_reference_hash(session_key, session_id)
    if session_ref_hash is None:
        errors.append("missing_session_reference")

    model_path = canonical_model_path(entry.get("modelProvider"), entry.get("model"))
    if model_path is None:
        errors.append("invalid_model_path")

    runtime_ms = strict_nonnegative_int(entry.get("runtimeMs"))
    if entry.get("runtimeMs") is not None and runtime_ms is None:
        errors.append("invalid_runtimeMs")
    source_estimated_cost = safe_nonnegative_float(entry.get("estimatedCostUsd"))
    if entry.get("estimatedCostUsd") is not None and source_estimated_cost is None:
        errors.append("invalid_estimatedCostUsd")
    if errors:
        return None, sorted(set(errors))

    assert started_at_ms is not None and ended_at_ms is not None
    assert started_at_utc is not None and ended_at_utc is not None
    assert session_ref_hash is not None and model_path is not None
    cache_write_tokens = counts["cacheWrite"]
    source_input_total_tokens = counts["inputTokens"] + counts["cacheRead"] + cache_write_tokens
    raw_thinking = str(entry.get("thinkingLevel") or "").strip().lower()
    actual_thinking = raw_thinking if raw_thinking in VALID_THINKING_LEVELS else None
    attempt_correlation = build_attempt_correlation_key(
        parent_job_id=entry.get("parent_job_id"),
        lane_id=entry.get("lane_id"),
        phase=entry.get("phase"),
        attempt_id=entry.get("attempt_id"),
        retry_count=entry.get("retry_count"),
    )
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "agent_id": agent_id,
        "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
        "session_ref_hash": session_ref_hash,
        "session_key_hash": session_key_hash,
        "session_id_hash": session_id_hash,
        "run_id": isolated_session_run_id(agent_id, session_ref_hash, started_at_ms),
        "status": "done",
        "model_path": model_path,
        "model_provider": str(entry.get("modelProvider")),
        "actual_thinking": actual_thinking,
        "started_at_epoch_ms": started_at_ms,
        "ended_at_epoch_ms": ended_at_ms,
        "started_at_utc": started_at_utc,
        "usage_at_utc": ended_at_utc,
        "usage_time_source": "isolated_session.endedAt_epoch_ms",
        "duration_ms": runtime_ms,
        "input_tokens": counts["inputTokens"],
        "cached_input_tokens": counts["cacheRead"],
        "cache_write_tokens": cache_write_tokens,
        "output_tokens": counts["outputTokens"],
        "source_input_total_tokens": source_input_total_tokens,
        "source_context_prompt_tokens": counts["totalTokens"],
        "source_context_prompt_semantics": "context_prompt_snapshot_not_run_usage_total",
        "total_tokens": source_input_total_tokens + counts["outputTokens"],
        "input_token_semantics": "exclusive_cached",
        "token_semantics_status": "valid",
        "source_total_tokens_fresh": True,
        "source_estimated_cost_usd": source_estimated_cost,
        "source_estimated_cost_semantics": "openclaw_source_estimate_not_invoice",
        "token_attribution_source": "openclaw_isolated_session_store_v1",
        "metadata_only": True,
        "pricing_grade_eligible": cache_write_tokens == 0,
        "pricing_unavailable_reason": (
            None if cache_write_tokens == 0 else "cache_write_pricing_unavailable"
        ),
        "source_artifact": f"openclaw-agent-session-index:{agent_id}",
    }
    if attempt_correlation is not None:
        record["attempt_correlation"] = attempt_correlation
    record["source_snapshot_fingerprint"] = _snapshot_fingerprint(record)
    return record, []


def _safe_invalid_record(agent_id: str, session_key: Any, entry: Any, errors: list[str]) -> dict[str, Any]:
    entry_dict = entry if isinstance(entry, dict) else {}
    return {
        "agent_id": agent_id,
        "session_ref_hash": session_reference_hash(session_key, entry_dict.get("sessionId")),
        "errors": sorted(set(errors)),
    }


def load_allowlisted_session_usage(
    agent_ids: Iterable[str] = CONFIGURED_ISOLATED_AGENT_IDS,
    agent_state_root: Path = DEFAULT_AGENT_STATE_ROOT,
) -> dict[str, Any]:
    requested = tuple(dict.fromkeys(str(item) for item in agent_ids))
    unknown = sorted(set(requested) - set(CONFIGURED_ISOLATED_AGENT_IDS))
    if unknown:
        raise ValueError(f"agent ids are not allowlisted: {', '.join(unknown)}")

    root = Path(agent_state_root).resolve()
    records_by_run: dict[str, dict[str, Any]] = {}
    invalid_records: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []
    for agent_id in requested:
        store = (root / agent_id / "sessions" / "sessions.json").resolve()
        try:
            store.relative_to(root)
        except ValueError as exc:
            raise ValueError("session store escaped configured agent state root") from exc
        status: dict[str, Any] = {
            "agent_id": agent_id,
            "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
            "source_artifact": f"openclaw-agent-session-index:{agent_id}",
            "present": store.is_file(),
            "valid_record_count": 0,
            "invalid_record_count": 0,
        }
        if not store.is_file():
            status["status"] = "missing"
            source_status.append(status)
            continue
        try:
            raw = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            status["status"] = "invalid_json"
            status["invalid_record_count"] = 1
            invalid_records.append({"agent_id": agent_id, "session_ref_hash": None, "errors": ["session_index_unreadable"]})
            source_status.append(status)
            continue
        if not isinstance(raw, dict):
            status["status"] = "invalid_root"
            status["invalid_record_count"] = 1
            invalid_records.append({"agent_id": agent_id, "session_ref_hash": None, "errors": ["session_index_root_not_object"]})
            source_status.append(status)
            continue
        for session_key, entry in raw.items():
            record, errors = extract_session_usage(agent_id, session_key, entry)
            if record is None:
                invalid_records.append(_safe_invalid_record(agent_id, session_key, entry, errors))
                status["invalid_record_count"] += 1
                continue
            run_id = str(record["run_id"])
            previous = records_by_run.get(run_id)
            if previous is None or int(record["ended_at_epoch_ms"]) >= int(previous["ended_at_epoch_ms"]):
                records_by_run[run_id] = record
            status["valid_record_count"] += 1
        status["status"] = "ok" if status["invalid_record_count"] == 0 else "warning"
        source_status.append(status)

    records = sorted(records_by_run.values(), key=lambda row: (str(row["agent_id"]), str(row["run_id"])))
    return {
        "schema": SCHEMA,
        "metadata_only": True,
        "configured_agent_ids": list(requested),
        "records": records,
        "invalid_records": invalid_records,
        "source_status": source_status,
        "summary": {
            "configured_agent_count": len(requested),
            "observed_agent_count": len({row["agent_id"] for row in records}),
            "valid_record_count": len(records),
            "invalid_record_count": len(invalid_records),
        },
    }


def find_session_usage_record(
    payload: dict[str, Any],
    *,
    agent_id: str,
    session_id: Any = None,
    session_key: Any = None,
) -> dict[str, Any] | None:
    id_hash = hash_reference(session_id)
    key_hash = hash_reference(session_key)
    if not id_hash and not key_hash:
        return None
    matches = []
    for record in payload.get("records", []):
        if not isinstance(record, dict) or record.get("agent_id") != agent_id:
            continue
        # When the caller supplies both identifiers, they must identify the
        # same terminal source record.  An OR join would let a stale or wrong
        # companion identifier borrow attribution from the other one.
        if id_hash and record.get("session_id_hash") != id_hash:
            continue
        if key_hash and record.get("session_key_hash") != key_hash:
            continue
        matches.append(record)
    unique = {str(row.get("run_id")): row for row in matches}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def _load_terminal_dispatch_binding(
    *,
    agent_id: str,
    expected_binding_token_hash: str,
    state_db_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Read exactly one completed hash-only dispatch binding from the core DB."""
    if not SHA256_HEX_RE.fullmatch(expected_binding_token_hash):
        return None, ["dispatch_binding_token_hash_invalid"]
    target_agent_id_hash = full_hash_reference(agent_id)
    if target_agent_id_hash is None:
        return None, ["dispatch_binding_agent_hash_invalid"]
    try:
        resolved_db = Path(state_db_path).expanduser().resolve(strict=True)
    except OSError:
        return None, ["dispatch_binding_state_db_unavailable"]
    if not resolved_db.is_file():
        return None, ["dispatch_binding_state_db_unavailable"]

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"{resolved_db.as_uri()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        rows = connection.execute(
            """
            SELECT
              binding.binding_token_hash,
              binding.child_session_key_hash,
              binding.dispatch_nonce_hash,
              binding.target_agent_id_hash,
              binding.reserved_at_ms,
              binding.binding_schema,
              accepted.occurred_at_ms AS accepted_at_ms,
              accepted.registry_run_id_hash AS accepted_registry_run_id_hash,
              terminal.occurred_at_ms AS terminal_at_ms,
              terminal.registry_run_id_hash AS terminal_registry_run_id_hash,
              terminal.terminal_status
            FROM subagent_dispatch_bindings AS binding
            JOIN subagent_dispatch_binding_events AS accepted
              ON accepted.binding_token_hash = binding.binding_token_hash
             AND accepted.event_seq = 1
             AND accepted.event_kind = 'accepted'
            JOIN subagent_dispatch_binding_events AS terminal
              ON terminal.binding_token_hash = binding.binding_token_hash
             AND terminal.event_seq = 2
             AND terminal.event_kind = 'terminal'
            WHERE binding.binding_token_hash = ?
              AND binding.target_agent_id_hash = ?
              AND binding.binding_schema = ?
            LIMIT 2
            """,
            (expected_binding_token_hash, target_agent_id_hash, DISPATCH_BINDING_SCHEMA),
        ).fetchall()
    except (sqlite3.Error, OSError, ValueError):
        return None, ["dispatch_binding_state_db_unavailable"]
    finally:
        if connection is not None:
            connection.close()

    if len(rows) != 1:
        return None, ["dispatch_binding_missing_or_ambiguous"]
    row = rows[0]
    (
        binding_token_hash,
        child_session_key_hash,
        dispatch_nonce_hash,
        observed_target_agent_id_hash,
        reserved_at_ms,
        binding_schema,
        accepted_at_ms,
        accepted_registry_run_id_hash,
        terminal_at_ms,
        terminal_registry_run_id_hash,
        terminal_status,
    ) = row
    hashes = (
        binding_token_hash,
        child_session_key_hash,
        dispatch_nonce_hash,
        observed_target_agent_id_hash,
        accepted_registry_run_id_hash,
        terminal_registry_run_id_hash,
    )
    if not all(isinstance(value, str) and SHA256_HEX_RE.fullmatch(value) for value in hashes):
        return None, ["dispatch_binding_hash_shape_invalid"]
    if (
        binding_token_hash != expected_binding_token_hash
        or observed_target_agent_id_hash != target_agent_id_hash
        or accepted_registry_run_id_hash != terminal_registry_run_id_hash
        or binding_schema != DISPATCH_BINDING_SCHEMA
        or terminal_status != "ok"
    ):
        return None, ["dispatch_binding_lifecycle_mismatch"]
    timestamps = (reserved_at_ms, accepted_at_ms, terminal_at_ms)
    if not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in timestamps):
        return None, ["dispatch_binding_timestamp_invalid"]
    if not (reserved_at_ms <= accepted_at_ms <= terminal_at_ms):
        return None, ["dispatch_binding_lifecycle_order_invalid"]
    return {
        "schema": binding_schema,
        "binding_token_hash": binding_token_hash,
        "child_session_key_hash": child_session_key_hash,
        "dispatch_nonce_hash": dispatch_nonce_hash,
        "target_agent_id_hash": observed_target_agent_id_hash,
        "reserved_at_ms": reserved_at_ms,
        "accepted_at_ms": accepted_at_ms,
        "registry_run_id_hash": accepted_registry_run_id_hash,
        "terminal_at_ms": terminal_at_ms,
        "terminal_status": terminal_status,
    }, []


def load_verified_isolated_session_usage_for_binding(
    *,
    agent_id: str,
    expected_binding_token_hash: str,
    agent_state_root: Path = DEFAULT_AGENT_STATE_ROOT,
    state_db_path: Path = DEFAULT_OPENCLAW_STATE_DB,
    session_id: Any = None,
    session_key: Any = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Join a terminal usage index entry to one protected dispatch binding.

    The session index and core state database are opened read-only. Raw session
    keys and IDs are retained only while the two sources are compared and are
    never emitted in the returned record or error labels.
    """
    if agent_id not in CONFIGURED_ISOLATED_AGENT_ROLES:
        return None, ["agent_not_allowlisted"]
    binding, binding_errors = _load_terminal_dispatch_binding(
        agent_id=agent_id,
        expected_binding_token_hash=expected_binding_token_hash,
        state_db_path=state_db_path,
    )
    if binding is None:
        return None, binding_errors
    try:
        root = Path(agent_state_root).expanduser().resolve()
        store = (root / agent_id / "sessions" / "sessions.json").resolve()
        store.relative_to(root)
    except (OSError, ValueError):
        return None, ["dispatch_binding_session_index_unavailable"]
    if not store.is_file():
        return None, ["dispatch_binding_session_index_unavailable"]
    try:
        raw = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, ["dispatch_binding_session_index_unreadable"]
    if not isinstance(raw, dict):
        return None, ["dispatch_binding_session_index_invalid"]

    requested_session_id = session_id if isinstance(session_id, str) and session_id else None
    requested_session_key = session_key if isinstance(session_key, str) and session_key else None
    matches: list[dict[str, Any]] = []
    matched_binding_session = False
    invalid_binding_session = False
    for raw_session_key, entry in raw.items():
        if full_hash_reference(raw_session_key) != binding["child_session_key_hash"]:
            continue
        matched_binding_session = True
        if requested_session_key is not None and raw_session_key != requested_session_key:
            continue
        if requested_session_id is not None:
            entry_id = entry.get("sessionId") if isinstance(entry, dict) else None
            if entry_id != requested_session_id:
                continue
        record, errors = extract_session_usage(agent_id, raw_session_key, entry)
        if record is None:
            invalid_binding_session = True
            continue
        started_at_ms = record.get("started_at_epoch_ms")
        ended_at_ms = record.get("ended_at_epoch_ms")
        if (
            not isinstance(started_at_ms, int)
            or isinstance(started_at_ms, bool)
            or not isinstance(ended_at_ms, int)
            or isinstance(ended_at_ms, bool)
            or not (
                # Gateway acknowledgement can occur after the child reports
                # its source start. Reservation and terminal are the session's
                # enclosing dispatch bounds.
                int(binding["reserved_at_ms"])
                <= started_at_ms
                <= ended_at_ms
                <= int(binding["terminal_at_ms"])
            )
        ):
            invalid_binding_session = True
            continue
        sanitized = dict(record)
        # The legacy index cannot prove caller-owned parent/lane metadata.
        # The protected token binding is the sole source-to-attempt join.
        sanitized.pop("attempt_correlation", None)
        sanitized["token_attribution_source"] = "openclaw_isolated_session_store_v2"
        sanitized["dispatch_binding"] = dict(binding)
        sanitized["source_snapshot_fingerprint"] = _snapshot_fingerprint(sanitized)
        matches.append(sanitized)

    if len(matches) == 1:
        return matches[0], []
    if invalid_binding_session:
        return None, ["dispatch_binding_session_lifecycle_invalid"]
    if matched_binding_session:
        return None, ["dispatch_binding_requested_session_mismatch"]
    return None, ["dispatch_binding_session_key_not_found"]


def _nonempty_count(value: Any) -> int:
    if value is None or value is False:
        return 0
    if value is True:
        return 1
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, (list, tuple, dict, set)):
        return len(value)
    return 1


def sanitize_gateway_usage_cost(agent_id: str, payload: Any, days: int) -> dict[str, Any]:
    errors: list[str] = []
    if agent_id not in CONFIGURED_ISOLATED_AGENT_ROLES:
        return {"agent_id": agent_id, "status": "blocked", "errors": ["agent_not_allowlisted"]}
    if not isinstance(payload, dict):
        return {"agent_id": agent_id, "status": "blocked", "errors": ["gateway_payload_not_object"]}
    cache = payload.get("cacheStatus")
    if not isinstance(cache, dict):
        cache = {}
        errors.append("cache_status_missing")
    cache_status = str(cache.get("status") or "unknown")
    pending_count = _nonempty_count(cache.get("pendingFiles"))
    stale_count = _nonempty_count(cache.get("staleFiles"))
    if cache_status not in CLEAN_GATEWAY_CACHE_STATUSES:
        errors.append("cache_status_not_ok")
    if pending_count:
        errors.append("cache_pending_files")
    if stale_count:
        errors.append("cache_stale_files")

    daily_rows: list[dict[str, Any]] = []
    raw_daily = payload.get("daily")
    if not isinstance(raw_daily, list):
        errors.append("daily_rows_missing")
        raw_daily = []
    for row in raw_daily:
        if not isinstance(row, dict):
            errors.append("daily_row_not_object")
            continue
        sanitized = {key: row.get(key) for key in GATEWAY_USAGE_FIELDS}
        sanitized["missingCostEntries"] = _nonempty_count(row.get("missingCostEntries"))
        for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens"):
            if strict_nonnegative_int(sanitized.get(key)) is None:
                errors.append(f"daily_invalid_{key}")
        if safe_nonnegative_float(sanitized.get("totalCost")) is None:
            errors.append("daily_invalid_totalCost")
        daily_rows.append(sanitized)

    if not isinstance(payload.get("totals"), dict):
        errors.append("totals_missing")
    totals_raw = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    totals = {key: totals_raw.get(key) for key in GATEWAY_USAGE_FIELDS if key != "date"}
    totals["missingCostEntries"] = _nonempty_count(totals_raw.get("missingCostEntries"))
    for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens"):
        if strict_nonnegative_int(totals.get(key)) is None:
            errors.append(f"totals_invalid_{key}")
    if safe_nonnegative_float(totals.get("totalCost")) is None:
        errors.append("totals_invalid_totalCost")
    daily_missing_cost_count = sum(_nonempty_count(row.get("missingCostEntries")) for row in daily_rows)
    missing_cost_count = max(
        daily_missing_cost_count,
        _nonempty_count(totals.get("missingCostEntries")),
    )
    if missing_cost_count:
        errors.append("missing_cost_entries")
    clean_cache = not errors
    return {
        "schema": "veritas.isolated_agent_gateway_usage_cost.v1",
        "agent_id": agent_id,
        "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
        "days": days,
        "updated_at": payload.get("updatedAt"),
        "daily": daily_rows,
        "totals": totals if clean_cache else {},
        "cache_status": {
            "status": cache_status,
            "cached_file_count": _nonempty_count(cache.get("cachedFiles")),
            "pending_file_count": pending_count,
            "stale_file_count": stale_count,
            "refreshed_at": cache.get("refreshedAt"),
        },
        "missing_cost_entry_count": missing_cost_count,
        "attribution_grade": not any(error != "missing_cost_entries" for error in errors),
        "pricing_grade": clean_cache,
        "reporting_eligible": clean_cache,
        "cost_semantics": "api_equivalent_not_invoice",
        "actual_billed_cost_usd": None,
        "daily_rows_preserved_for_24h_and_closed_7d_reporting": True,
        "status": "ok" if clean_cache else "blocked",
        "errors": sorted(set(errors)),
        "metadata_only": True,
    }


# Observed session-log scans take ~33s per agent; the CLI default of 10s
# times out every query and reports all agents as command_failed.
GATEWAY_USAGE_COST_TIMEOUT_MS = 60000


def load_gateway_usage_cost(
    agent_ids: Iterable[str] = CONFIGURED_ISOLATED_AGENT_IDS,
    *,
    days: int = 8,
    runner: Any = subprocess.run,
    executable: str | None = None,
) -> dict[str, Any]:
    if isinstance(days, bool) or not isinstance(days, int) or days <= 0 or days > 366:
        raise ValueError("days must be an integer from 1 through 366")
    requested = tuple(dict.fromkeys(str(item) for item in agent_ids))
    unknown = sorted(set(requested) - set(CONFIGURED_ISOLATED_AGENT_IDS))
    if unknown:
        raise ValueError(f"agent ids are not allowlisted: {', '.join(unknown)}")
    command = executable or shutil.which("openclaw") or shutil.which("openclaw.cmd") or "openclaw"
    rows: list[dict[str, Any]] = []
    for agent_id in requested:
        try:
            completed = runner(
                [
                    command, "gateway", "usage-cost",
                    "--agent", agent_id,
                    "--days", str(days),
                    "--timeout", str(GATEWAY_USAGE_COST_TIMEOUT_MS),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            rows.append({
                "agent_id": agent_id,
                "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
                "status": "blocked",
                "errors": ["gateway_usage_cost_command_failed"],
                "metadata_only": True,
            })
            continue
        if getattr(completed, "returncode", 1) != 0:
            rows.append({
                "agent_id": agent_id,
                "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
                "status": "blocked",
                "errors": ["gateway_usage_cost_command_failed"],
                "metadata_only": True,
            })
            continue
        try:
            payload = json.loads(getattr(completed, "stdout", ""))
        except json.JSONDecodeError:
            rows.append({
                "agent_id": agent_id,
                "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
                "status": "blocked",
                "errors": ["gateway_usage_cost_invalid_json"],
                "metadata_only": True,
            })
            continue
        rows.append(sanitize_gateway_usage_cost(agent_id, payload, days))
    return {
        "schema": "veritas.isolated_agent_gateway_usage_cost_collection.v1",
        "metadata_only": True,
        "days": days,
        "agents": rows,
        "summary": {
            "configured_agent_count": len(requested),
            "ok_agent_count": sum(1 for row in rows if row.get("status") == "ok"),
            "blocked_agent_count": sum(1 for row in rows if row.get("status") != "ok"),
            "pricing_grade_agent_count": sum(1 for row in rows if row.get("pricing_grade") is True),
            "attribution_grade_agent_count": sum(1 for row in rows if row.get("attribution_grade") is True),
        },
    }
