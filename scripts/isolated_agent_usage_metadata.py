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
import os
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


_CANONICAL_DB_SUBPATH = ("agent", "openclaw-agent.sqlite")
_CANONICAL_NODE_TABLE = "session_nodes"
_CANONICAL_WINDOW_TABLE = "session_windows"
_SQLITE_SCAN_BOUND = 512
_SQLITE_EXACT_LIMIT = 4
_SQLITE_BUSY_TIMEOUT_MS = 5000
_MAX_SCALAR_LEN = 512
# Only fields already consumed by extract_session_usage (usage scalars,
# provenance identity, correlation inputs). Never raw content, prompts,
# auth, delivery, labels, sessionFile, transcript or account identifiers.
_ALLOWLISTED_JSON_FIELDS = (
    "status",
    "totalTokensFresh",
    "sessionId",
    "modelProvider",
    "model",
    "thinkingLevel",
    "startedAt",
    "endedAt",
    "runtimeMs",
    "inputTokens",
    "cacheRead",
    "cacheWrite",
    "outputTokens",
    "totalTokens",
    "estimatedCostUsd",
    "parent_job_id",
    "lane_id",
    "phase",
    "attempt_id",
    "retry_count",
)
_ALLOWLISTED_JSON_PATHS = tuple(f"$.{name}" for name in _ALLOWLISTED_JSON_FIELDS)
_REQUIRED_NODE_COLUMNS = {
    "session_key": "TEXT",
    "current_session_id": "TEXT",
    "entry_json": "TEXT",
    "entry_valid": "INTEGER",
}
_REQUIRED_WINDOW_COLUMNS = {
    "session_id": "TEXT",
    "session_key": "TEXT",
    "started_at": "INTEGER",
    "ended_at": "INTEGER",
    "status": "TEXT",
}


class _CanonicalAbsent(Exception):
    pass


class _CanonicalUnreadable(Exception):
    pass


class _CanonicalIncompatible(Exception):
    pass


def _realpath_str(path: Path) -> str:
    return os.path.realpath(os.fspath(path))


def _resolve_owned_paths(
    root: Path, agent_id: str
) -> tuple[str, str, str, str] | None:
    """Resolve agent root, canonical DB and legacy JSON inside one owning root.

    Returns (root_real, agent_real, db_real, legacy_real) or None when any
    reparse/symlink/junction redirects outside the exact owning agent root,
    including sibling-agent redirection. Fleet-root containment alone is
    never sufficient.
    """
    root_real = _realpath_str(root)
    agent_real = _realpath_str(root / agent_id)
    if os.path.basename(agent_real) != agent_id:
        return None
    if os.path.dirname(agent_real) != root_real:
        return None
    db_real = _realpath_str(root / agent_id / _CANONICAL_DB_SUBPATH[0] / _CANONICAL_DB_SUBPATH[1])
    legacy_real = _realpath_str(root / agent_id / "sessions" / "sessions.json")
    expected_db = os.path.join(agent_real, _CANONICAL_DB_SUBPATH[0], _CANONICAL_DB_SUBPATH[1])
    expected_legacy = os.path.join(agent_real, "sessions", "sessions.json")
    if db_real != expected_db or legacy_real != expected_legacy:
        return None
    return (root_real, agent_real, db_real, legacy_real)


def _open_canonical_readonly(db_real: str) -> sqlite3.Connection:
    uri = Path(db_real).as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute(f"PRAGMA busy_timeout = {_SQLITE_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA trusted_schema = OFF")
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def _check_canonical_schema(connection: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if _CANONICAL_NODE_TABLE not in tables or _CANONICAL_WINDOW_TABLE not in tables:
        raise _CanonicalIncompatible("canonical_schema_mismatch")
    node_info = connection.execute(
        f'PRAGMA table_info("{_CANONICAL_NODE_TABLE}")'
    ).fetchall()
    window_info = connection.execute(
        f'PRAGMA table_info("{_CANONICAL_WINDOW_TABLE}")'
    ).fetchall()
    node_cols = {row[1]: row for row in node_info}
    window_cols = {row[1]: row for row in window_info}
    for name in _REQUIRED_NODE_COLUMNS:
        if name not in node_cols:
            raise _CanonicalIncompatible("canonical_schema_mismatch")
    for name in _REQUIRED_WINDOW_COLUMNS:
        if name not in window_cols:
            raise _CanonicalIncompatible("canonical_schema_mismatch")
    # Structural PK uniqueness: session_key and session_id must be the
    # single-column primary keys, not merely indexed columns.
    node_pk = sorted(row[1] for row in node_info if len(row) > 5 and row[5] > 0)
    window_pk = sorted(row[1] for row in window_info if len(row) > 5 and row[5] > 0)
    if node_pk != ["session_key"] or window_pk != ["session_id"]:
        raise _CanonicalIncompatible("canonical_schema_mismatch")


def _decode_bounded_scalar(raw: Any) -> Any:
    """Decode one ``->`` projected JSON value; reject containers/unbounded text."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("non_text_projection")
    if len(raw) > _MAX_SCALAR_LEN + 32:
        raise ValueError("scalar_too_long")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("malformed_scalar")
    if isinstance(value, (dict, list)):
        raise ValueError("non_scalar_value")
    if isinstance(value, str) and len(value) > _MAX_SCALAR_LEN:
        raise ValueError("scalar_too_long")
    return value


def _canonical_projection_select() -> str:
    parts = [
        'n.session_key AS node_key',
        'n.current_session_id AS node_current_id',
        'n.entry_valid AS node_valid',
        'w.session_id AS window_id',
        'w.session_key AS window_key',
        'w.status AS window_status',
        'w.started_at AS window_started',
        'w.ended_at AS window_ended',
    ]
    for index in range(len(_ALLOWLISTED_JSON_FIELDS)):
        # json_valid guards one malformed document from aborting the whole
        # bounded read; malformed rows project as NULL and are rejected
        # per-row in Python without raw leakage.
        parts.append(
            f'CASE WHEN json_valid(n.entry_json) THEN n.entry_json -> ? ELSE NULL END AS f{index}'
        )
    return ', '.join(parts)


def _query_canonical_rows(
    connection: sqlite3.Connection,
    *,
    session_key: str | None = None,
    session_id: str | None = None,
    scan_limit: int = _SQLITE_SCAN_BOUND + 1,
) -> list[tuple]:
    """Select the current-window join with caller filters applied pre-bound.

    The node/window join is performed inside SQLite so a target beyond 512
    rows is still found when the caller supplies its exact key/ID. The
    node and window tables are never LIMITed independently. A LEFT JOIN
    keeps nodes with missing/mismatched windows visible as invalid rows;
    an inner join must never turn them into a clean empty ok source.
    """
    select_list = _canonical_projection_select()
    clauses: list[str] = []
    params: list[Any] = list(_ALLOWLISTED_JSON_PATHS)
    if session_key is not None:
        clauses.append('n.session_key = ?')
        params.append(session_key)
    if session_id is not None:
        clauses.append('n.current_session_id = ?')
        params.append(session_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    params.append(int(scan_limit))
    rows = connection.execute(
        f"""
        SELECT {select_list}
        FROM session_nodes AS n
        LEFT JOIN session_windows AS w
          ON w.session_id = n.current_session_id
         AND w.session_key = n.session_key
        {where}
        ORDER BY n.session_key ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return rows


def _canonical_row_to_entry(
    agent_id: str, row: tuple
) -> tuple[str, Any, str | None]:
    """Return (session_key, entry_dict, failure_label) without raw leakage."""
    node_key, node_current_id, node_valid = row[0], row[1], row[2]
    window_id, window_key, window_status = row[3], row[4], row[5]
    window_started, window_ended = row[6], row[7]
    raw_fields = row[8:]
    if not isinstance(node_key, str) or not node_key or len(node_key) > _MAX_SCALAR_LEN:
        return ('', None, 'canonical_identity_invalid')
    if (
        not isinstance(node_current_id, str)
        or not node_current_id
        or len(node_current_id) > _MAX_SCALAR_LEN
    ):
        return (node_key, None, 'canonical_identity_invalid')
    # entry_valid must be exactly integer 1; booleans, strings, nulls and
    # 0 are never current, even when the joined window looks terminal.
    if type(node_valid) is not int or node_valid != 1:
        return (node_key, None, 'canonical_entry_not_current')
    # Current-window identity: LEFT JOIN keeps orphaned nodes visible, so
    # re-verify exact typed node/window key identity here. Missing, null,
    # unbounded or mismatched windows never become a clean empty source.
    if (
        not isinstance(window_id, str)
        or not window_id
        or len(window_id) > _MAX_SCALAR_LEN
        or not isinstance(window_key, str)
        or not window_key
        or len(window_key) > _MAX_SCALAR_LEN
    ):
        return (node_key, None, 'canonical_window_identity_mismatch')
    if window_id != node_current_id or window_key != node_key:
        return (node_key, None, 'canonical_window_identity_mismatch')
    if window_status not in TERMINAL_SESSION_STATUSES:
        return (node_key, None, 'canonical_window_lifecycle_invalid')
    # Window lifecycle scalars: strict nonnegative integers, ordered, and
    # exactly equal to the entry interval. No tolerance is approved: stale,
    # retired, reset, null, boolean or float windows are rejected even when
    # the entry timestamps fit the dispatch reservation/terminal bounds.
    if type(window_started) is not int or window_started < 0:
        return (node_key, None, 'canonical_window_time_mismatch')
    if type(window_ended) is not int or window_ended < 0:
        return (node_key, None, 'canonical_window_time_mismatch')
    if window_ended < window_started:
        return (node_key, None, 'canonical_window_time_mismatch')
    try:
        decoded = [_decode_bounded_scalar(raw) for raw in raw_fields]
    except ValueError:
        return (node_key, None, 'canonical_entry_malformed')
    entry = dict(zip(_ALLOWLISTED_JSON_FIELDS, decoded))
    # Token scalars must be strict numbers; JSON true/false must not pass
    # as 1/0 and arrays/objects are already rejected above.
    for token_field in TOKEN_FIELDS:
        token_value = entry.get(token_field)
        if isinstance(token_value, bool) or not isinstance(token_value, int):
            return (node_key, None, 'canonical_entry_malformed')
    freshness = entry.get('totalTokensFresh')
    if freshness is not True:
        return (node_key, None, 'canonical_entry_not_fresh')
    if entry.get('status') != 'done':
        return (node_key, None, 'canonical_entry_lifecycle_invalid')
    # Contradictory entry/current identity: the entry sessionId must be a
    # typed nonempty bounded value equal to BOTH node.current_session_id
    # AND the current window.session_id. Checked on every path even when
    # the caller omits key/ID filters.
    entry_session_id = entry.get('sessionId')
    if (
        not isinstance(entry_session_id, str)
        or not entry_session_id
        or len(entry_session_id) > _MAX_SCALAR_LEN
    ):
        return (node_key, None, 'canonical_window_identity_mismatch')
    if entry_session_id != node_current_id or entry_session_id != window_id:
        return (node_key, None, 'canonical_window_identity_mismatch')
    # Exact window/entry time consistency.
    entry_started = entry.get('startedAt')
    entry_ended = entry.get('endedAt')
    if type(entry_started) is not int or type(entry_ended) is not int:
        return (node_key, None, 'canonical_window_time_mismatch')
    if window_started != entry_started or window_ended != entry_ended:
        return (node_key, None, 'canonical_window_time_mismatch')
    return (node_key, entry, None)


def _read_canonical_store(
    *,
    agent_id: str,
    root: Path,
    session_key: str | None = None,
    session_id: str | None = None,
    bulk: bool = False,
) -> tuple[str, list[tuple[str, Any]], bool, str | None]:
    """Open the canonical SQLite store read-only; never fall back silently.

    Returns (kind, entries, partial, error_label) where kind is one of
    'absent', 'ok', 'unreadable', 'incompatible'. 'absent' is the only
    state that permits legacy JSON fallback.
    """
    resolved = _resolve_owned_paths(root, agent_id)
    if resolved is None:
        raise ValueError('session store escaped configured agent state root')
    _, _, db_real, _ = resolved
    if not os.path.lexists(db_real):
        return ('absent', [], False, None)
    if os.path.isdir(db_real) or not os.path.isfile(db_real):
        return ('incompatible', [], False, 'canonical_store_not_file')
    connection: sqlite3.Connection | None = None
    try:
        connection = _open_canonical_readonly(db_real)
        _check_canonical_schema(connection)
        if bulk:
            rows = _query_canonical_rows(connection)
            partial = len(rows) > _SQLITE_SCAN_BOUND
            rows = rows[:_SQLITE_SCAN_BOUND]
        else:
            rows = _query_canonical_rows(
                connection,
                session_key=session_key,
                session_id=session_id,
                scan_limit=_SQLITE_EXACT_LIMIT,
            )
            partial = False
    except _CanonicalIncompatible:
        return ('incompatible', [], False, 'canonical_store_incompatible')
    except (sqlite3.Error, OSError, ValueError):
        return ('unreadable', [], False, 'canonical_store_unreadable')
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                pass
    decoded: list[tuple[str, Any]] = []
    for row in rows:
        node_key, entry, _failure = _canonical_row_to_entry(agent_id, row)
        decoded.append((node_key, entry))
    return ('ok', decoded, partial, None)


def load_allowlisted_session_usage(
    agent_ids: Iterable[str] = CONFIGURED_ISOLATED_AGENT_IDS,
    agent_state_root: Path = DEFAULT_AGENT_STATE_ROOT,
) -> dict[str, Any]:
    requested = tuple(dict.fromkeys(str(item) for item in agent_ids))
    unknown = sorted(set(requested) - set(CONFIGURED_ISOLATED_AGENT_IDS))
    if unknown:
        raise ValueError(f"agent ids are not allowlisted: {', '.join(unknown)}")

    root = Path(agent_state_root).expanduser()
    root_real = _realpath_str(root)
    records_by_run: dict[str, dict[str, Any]] = {}
    invalid_records: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []
    for agent_id in requested:
        resolved = _resolve_owned_paths(root, agent_id)
        if resolved is None:
            raise ValueError("session store escaped configured agent state root")
        _, _, db_real, legacy_real = resolved
        store = Path(legacy_real)
        status: dict[str, Any] = {
            "agent_id": agent_id,
            "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
            "source_artifact": f"openclaw-agent-session-index:{agent_id}",
            "present": store.is_file(),
            "valid_record_count": 0,
            "invalid_record_count": 0,
            "partial": False,
        }
        # Bounded read-only canonical loader first. Legacy JSON is used
        # only on genuine canonical absence; a present-but-unreadable,
        # corrupt, incompatible, non-file or escaped store never
        # downgrades to a possibly stale favorable JSON file.
        kind, canonical_entries, partial, error_label = _read_canonical_store(
            agent_id=agent_id, root=root, bulk=True
        )
        if kind != 'absent':
            status["present"] = os.path.lexists(db_real)
            status["partial"] = partial
            if kind != 'ok':
                status["status"] = "canonical_unreadable" if kind == 'unreadable' else "canonical_incompatible"
                status["invalid_record_count"] = 1
                invalid_records.append({"agent_id": agent_id, "session_ref_hash": None, "errors": [error_label or "canonical_store_unreadable"]})
                source_status.append(status)
                continue
            for session_key, entry in canonical_entries:
                if entry is None:
                    invalid_records.append(_safe_invalid_record(agent_id, session_key, {}, ["canonical_entry_invalid"]))
                    status["invalid_record_count"] += 1
                    continue
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
            if partial:
                status["status"] = "partial"
            else:
                status["status"] = "ok" if status["invalid_record_count"] == 0 else "warning"
            source_status.append(status)
            continue
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
        root = Path(agent_state_root).expanduser()
        resolved = _resolve_owned_paths(root, agent_id)
        if resolved is None:
            return None, ["dispatch_binding_session_index_unavailable"]
        _, _, db_real, legacy_real = resolved
        store = Path(legacy_real)
    except OSError:
        return None, ["dispatch_binding_session_index_unavailable"]

    requested_session_id = session_id if isinstance(session_id, str) and session_id else None
    requested_session_key = session_key if isinstance(session_key, str) and session_key else None
    matches: list[dict[str, Any]] = []
    matched_binding_session = False
    invalid_binding_session = False
    unresolved_partial = False
    # Canonical SQLite path: exact caller filters are applied before the
    # bound so a target beyond 512 rows is still found via the joined
    # current-window query. Without caller identity the bounded hash scan
    # reports partial/unresolved instead of false not-found or credit.
    canonical_present = os.path.lexists(db_real)
    if canonical_present:
        kind, canonical_entries, partial, error_label = _read_canonical_store(
            agent_id=agent_id,
            root=root,
            session_key=requested_session_key,
            session_id=requested_session_id,
            bulk=(requested_session_key is None and requested_session_id is None),
        )
        if kind != 'ok':
            return None, ["dispatch_binding_session_index_unavailable"]
        # Bounded hash scan without caller identity cannot credit: a target
        # inside the first 512 and a target beyond 512 both stay unresolved.
        if partial and requested_session_key is None and requested_session_id is None:
            return None, ["dispatch_binding_session_index_unresolved"]
        candidates: list[tuple[Any, Any]] = list(canonical_entries)
    else:
        if not store.is_file():
            return None, ["dispatch_binding_session_index_unavailable"]
        try:
            raw = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None, ["dispatch_binding_session_index_unreadable"]
        if not isinstance(raw, dict):
            return None, ["dispatch_binding_session_index_invalid"]
        candidates = list(raw.items())
    for raw_session_key, entry in candidates:
        if full_hash_reference(raw_session_key) != binding["child_session_key_hash"]:
            continue
        matched_binding_session = True
        if not isinstance(entry, dict):
            invalid_binding_session = True
            continue
        if requested_session_key is not None and raw_session_key != requested_session_key:
            continue
        if requested_session_id is not None:
            entry_id = entry.get("sessionId")
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
    if len(matches) > 1:
        return None, ["dispatch_binding_session_key_not_found"]
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
