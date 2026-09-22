#!/usr/bin/env python3
"""Narrow owner: Main configured + effective (session-bound) model selection.

Single integration point for the Main route. The router (build + validate)
and the long-work packet linter resolve through this module instead of any
static fleet constant. This module authors nothing, executes nothing, and
grants no authority: it returns structured selections with provenance.

Two layers:
  configured -- exact model from OpenClaw configuration for agent "main".
  effective  -- configured model, or a SELECTED user session pin read from
                the fixed runtime database. Auto-selected sessions are never
                treated as user permission and stay blocked.

Fail-closed throughout: unreadable config, malformed entries, missing roster
members, aliases, reference keys, unknown session sources, forged envelopes,
and partial pins all resolve to model None with a named error. A present
envelope is strictly validated and never downgraded to the legacy path; the
legacy path applies only when the envelope key is absent. There is no
fallback model of any kind.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = "veritas.main_model_selection.v1"
AGENT_ID = "main"
SESSION_SCHEMA_VERSION = 19

DEFAULT_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"

MODULE_ROOT = Path(__file__).resolve().parents[1]


def _derive_session_db_path() -> Path | None:
    """Production anchor: module installation ROOT.parent, and only when that
    directory is named '.openclaw'. No caller-supplied paths, no HOME
    redirection, no CLI database option. Tests monkeypatch SESSION_DB_PATH."""
    parent = MODULE_ROOT.parent
    if parent.name != ".openclaw":
        return None
    return parent / "agents" / "main" / "agent" / "openclaw-agent.sqlite"


SESSION_DB_PATH = _derive_session_db_path()

PACKET_MAX_AGE = timedelta(minutes=15)
FUTURE_SKEW = timedelta(seconds=120)

SESSION_KEY_RE = re.compile(r"agent:main:[A-Za-z0-9][A-Za-z0-9_.:+\-]*")
SESSION_ID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# Unsupported selection-reference keys. Checked at the payload, agents,
# defaults, main-entry, and model-dict levels. Every other metadata key
# (bindings, ownership, models, heartbeat, ...) is ignored, never rejected.
REFERENCE_KEYS = frozenset({"$include", "includes", "include", "extends", "$ref"})

_ALLOWED_MODEL_KEYS = {"primary", "fallbacks"}
_MISSING = object()

HEX64_RE = re.compile(r"[0-9a-f]{64}")

ENVELOPE_KEYS = frozenset({"schema", "agent_id", "configured", "effective"})
CONFIGURED_KEYS = frozenset({"agent_id", "model", "source", "config_sha256", "error"})
EFFECTIVE_KEYS = frozenset({"model", "basis", "provider", "source",
                            "session_key_sha256", "session_id_sha256",
                            "resolved_at_utc", "error"})
RAW_IDENTIFIER_KEYS = frozenset({"session_key", "session_id", "current_session_id",
                                 "session_pin", "main_session_key", "main_session_id"})
VALID_BASES = frozenset({"configured", "configured-unpinned", "user-pin-selected", "blocked"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_z(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_moment(value: Any) -> datetime | None:
    """Accept aware datetimes (and naive as UTC); anything else is None."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_utc_z(value: Any) -> datetime | None:
    """Parse proof timestamps. Invalid, naive-treated-as-UTC, or wrong-type
    values return None (callers emit findings, never raise)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if not isinstance(parsed, datetime):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _has_reference_key(mapping: dict[str, Any]) -> str | None:
    for key in mapping:
        if key in REFERENCE_KEYS:
            return str(key)
    return None


def _is_exact_token(value: Any) -> bool:
    """Exact provider or bare-name token: no whitespace, control chars,
    auth-profile suffixes, query/fragment markers, or path aliases."""
    if not isinstance(value, str) or not value:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    if value[0] in (".", "~", "/", "\\"):
        return False
    if any(bad in value for bad in ("/", "\\", "@", "?", "#", " ")):
        return False
    if ".." in value:
        return False
    return True


def _is_exact_model(value: Any) -> bool:
    """Exact provider/model ref: `provider/model` with two exact tokens."""
    if not isinstance(value, str) or not value:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    if value != value.strip():
        return False
    head, sep, tail = value.partition("/")
    if not sep or "/" in tail:
        return False
    return _is_exact_token(head) and _is_exact_token(tail)


def _primary_of(value: Any) -> tuple[str | None, str]:
    """Return (model, kind). Kinds: 'string', 'object', 'inherit', 'malformed'.

    'inherit' means the key is absent but the entry is otherwise valid, so a
    present defaults primary may apply. An explicit null, a non-empty
    fallbacks array with anything but exact model refs, or any invented key
    is 'malformed' and never inherits. A well-formed non-empty fallbacks
    array is accepted as metadata only: selection still uses primary and no
    fallback is ever chosen here.
    """
    if value is _MISSING:
        return None, "inherit"
    if value is None:
        return None, "malformed"
    if isinstance(value, str):
        if not _is_exact_model(value):
            return None, "malformed"
        return value, "string"
    if isinstance(value, dict):
        if any(key not in _ALLOWED_MODEL_KEYS for key in value):
            return None, "malformed"
        fallbacks = value.get("fallbacks", [])
        if "fallbacks" in value:
            if not isinstance(fallbacks, list) or not fallbacks:
                if fallbacks != []:
                    return None, "malformed"
            elif not all(_is_exact_model(item) for item in fallbacks):
                return None, "malformed"
        primary = value.get("primary", _MISSING)
        if primary is _MISSING:
            return None, "inherit"
        if not _is_exact_model(primary):
            return None, "malformed"
        return primary, "object"
    return None, "malformed"


def _read_config_bytes(config_path: str | Path) -> bytes | None:
    try:
        return Path(config_path).read_bytes()
    except OSError:
        return None


def resolve_configured(config_path: str | Path) -> dict[str, Any]:
    """Structured CONFIGURED Main selection. Reads the file bytes once;
    the hash and the parse bind to those same bytes. Never raises."""
    raw = _read_config_bytes(config_path)
    if raw is None:
        return {"agent_id": AGENT_ID, "model": None, "source": "unreadable",
                "config_sha256": None, "error": "config_unreadable"}
    file_hash = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"agent_id": AGENT_ID, "model": None, "source": "unreadable",
                "config_sha256": file_hash, "error": "config_unreadable"}

    def refused(code: str) -> dict[str, Any]:
        return {"agent_id": AGENT_ID, "model": None, "source": "fail-closed",
                "config_sha256": file_hash, "error": code}

    if not isinstance(payload, dict):
        return refused("config_not_object")
    ref_key = _has_reference_key(payload)
    if ref_key is not None:
        return refused("selection_reference_unsupported")
    agents = _as_dict(payload.get("agents"))
    if agents is None:
        return refused("agents_not_object")
    ref_key = _has_reference_key(agents)
    if ref_key is not None:
        return refused("selection_reference_unsupported")

    def inherited_default() -> dict[str, Any]:
        defaults = _as_dict(agents.get("defaults"))
        if defaults is None:
            return refused("main_model_unresolved")
        ref_key = _has_reference_key(defaults)
        if ref_key is not None:
            return refused("selection_reference_unsupported")
        model, kind = _primary_of(defaults.get("model", _MISSING))
        if model is None:
            return refused("main_model_unresolved")
        return {"agent_id": AGENT_ID, "model": model,
                "source": "inherited-defaults",
                "config_sha256": file_hash, "error": None}

    if "entries" in agents:
        entries = agents.get("entries")
        if not isinstance(entries, dict):
            return refused("entries_not_object")
        if AGENT_ID not in entries:
            # A missing roster member never inherits under local governance.
            return refused("main_entry_missing")
        entry = entries.get(AGENT_ID)
        if not isinstance(entry, dict):
            return refused("main_entry_not_object")
        ref_key = _has_reference_key(entry)
        if ref_key is not None:
            return refused("selection_reference_unsupported")
        raw_model = entry.get("model", _MISSING)
        if isinstance(raw_model, dict):
            ref_key = _has_reference_key(raw_model)
            if ref_key is not None:
                return refused("selection_reference_unsupported")
        model, kind = _primary_of(raw_model)
        if kind == "malformed":
            return refused("main_model_malformed")
        if kind == "inherit":
            return inherited_default()
        return {"agent_id": AGENT_ID, "model": model,
                "source": "explicit-string" if kind == "string" else "explicit-object",
                "config_sha256": file_hash, "error": None}
    # No entries key: legacy Main defaults apply only when the unsupported
    # legacy list is also absent.
    if "list" in agents:
        return refused("legacy_list_unsupported")
    legacy = inherited_default()
    if legacy["model"] is not None:
        legacy["source"] = "legacy-defaults"
    return legacy


def _open_session_db() -> sqlite3.Connection:
    if SESSION_DB_PATH is None:
        raise FileNotFoundError("no fixed session anchor")
    db = sqlite3.connect(f"{SESSION_DB_PATH.as_uri()}?mode=ro", uri=True, timeout=5)
    db.execute("PRAGMA query_only=ON")
    return db


def _check_schema_owner(db: sqlite3.Connection) -> str | None:
    """None when ownership+known version hold, else a failure code."""
    try:
        rows = db.execute(
            "SELECT role, schema_version, agent_id FROM schema_meta WHERE meta_key='primary'"
        ).fetchall()
    except sqlite3.Error:
        return "session_db_unavailable"
    if len(rows) != 1:
        return "session_schema_unexpected"
    role, version, agent_id = rows[0]
    if role != "agent" or agent_id != AGENT_ID or not isinstance(version, int):
        return "session_schema_unexpected"
    if version != SESSION_SCHEMA_VERSION:
        return "session_schema_unsupported"
    return None


_PIN_COLUMNS = (
    "session_key,current_session_id,"
    "json_extract(entry_json,'$.providerOverride'),"
    "json_extract(entry_json,'$.modelOverride'),"
    "json_extract(entry_json,'$.modelOverrideSource'),"
    "entry_valid"
)


def _read_pin_row(db: sqlite3.Connection, session_key: str,
                  session_id: str) -> tuple | None | dict[str, Any]:
    try:
        rows = db.execute(
            f"SELECT {_PIN_COLUMNS} FROM session_nodes "
            "WHERE session_key=? AND current_session_id=?",
            (session_key, session_id),
        ).fetchall()
    except sqlite3.Error:
        return {"db_error": True}
    if len(rows) != 1:
        return None
    return rows[0]


def _blocked(key_hash: str | None, id_hash: str | None, code: str) -> dict[str, Any]:
    return {"model": None, "basis": "blocked", "provider": None, "source": None,
            "session_key_sha256": key_hash, "session_id_sha256": id_hash,
            "resolved_at_utc": _utc_z(utc_now()), "error": code}


def resolve_session(session_key: str, session_id: str) -> dict[str, Any]:
    """EFFECTIVE session layer for one validated Main session. Read-only.

    A window counts as genuinely unpinned only when provider, model, AND
    source overrides are all JSON null. Any non-null override field forces
    the pin path: partial, contradictory, or unknown-source overrides block.
    """
    if not isinstance(session_key, str) or SESSION_KEY_RE.fullmatch(session_key) is None:
        return _blocked(None, None, "session_key_malformed")
    if not isinstance(session_id, str) or SESSION_ID_RE.fullmatch(session_id) is None:
        return _blocked(None, None, "session_id_malformed")
    key_hash = _sha256_text(session_key)
    id_hash = _sha256_text(session_id)
    try:
        db = _open_session_db()
    except (OSError, FileNotFoundError, sqlite3.Error):
        return _blocked(key_hash, id_hash, "session_db_unavailable")
    try:
        schema_failure = _check_schema_owner(db)
        if schema_failure is not None:
            return _blocked(key_hash, id_hash, schema_failure)
        row = _read_pin_row(db, session_key, session_id)
    finally:
        db.close()
    if row is None:
        return _blocked(key_hash, id_hash, "session_unknown_or_replaced")
    if isinstance(row, dict) or row[5] != 1:
        return _blocked(key_hash, id_hash, "session_entry_invalid")
    _live_key, _live_id, raw_provider, raw_model, raw_source = row[0], row[1], row[2], row[3], row[4]
    if raw_provider is None and raw_model is None:
        if raw_source is None:
            return {"model": None, "basis": "configured-unpinned", "provider": None, "source": None,
                    "session_key_sha256": key_hash, "session_id_sha256": id_hash,
                    "resolved_at_utc": _utc_z(utc_now()), "error": None}
        code = "session_source_auto_blocked" if raw_source == "auto" else "session_source_unknown"
        return _blocked(key_hash, id_hash, code)
    provider = raw_provider if _is_exact_token(raw_provider) else None
    model = raw_model if isinstance(raw_model, str) and _is_exact_model(raw_model) \
        else (raw_model if isinstance(raw_model, str) and "/" not in raw_model
              and _is_exact_token(raw_model) else None)
    source = raw_source if isinstance(raw_source, str) and raw_source.strip() else None
    if provider is None or model is None:
        return _blocked(key_hash, id_hash, "session_pin_partial")
    if source != "user":
        code = "session_source_auto_blocked" if source == "auto" else "session_source_unknown"
        return _blocked(key_hash, id_hash, code)
    if "/" in model:
        if model.partition("/")[0] != provider:
            return _blocked(key_hash, id_hash, "session_provider_model_mismatch")
        combined = model
    else:
        combined = f"{provider}/{model}"
    return {"model": combined,
            "basis": "user-pin-selected", "provider": provider, "source": "user",
            "session_key_sha256": key_hash, "session_id_sha256": id_hash,
            "resolved_at_utc": _utc_z(utc_now()), "error": None}


def resolve_effective(config_path: str | Path, *, session_key: str | None = None,
                      session_id: str | None = None) -> dict[str, Any]:
    """Full selection envelope for the Main route. No caller model input exists:
    a bare --model flag cannot reach this function, so it can never authorize
    a pin. The envelope carries only allowlisted fields and key/id hashes."""
    configured = resolve_configured(config_path)
    if (session_key is None) != (session_id is None):
        envelope_effective = _blocked(None, None, "session_pair_required")
        return {"schema": SCHEMA, "agent_id": AGENT_ID, "configured": configured,
                "effective": envelope_effective}
    if session_key is None:
        return {"schema": SCHEMA, "agent_id": AGENT_ID, "configured": configured,
                "effective": {"model": configured["model"], "basis": "configured",
                              "provider": None, "source": None, "session_key_sha256": None,
                              "session_id_sha256": None,
                              "resolved_at_utc": _utc_z(utc_now()),
                              "error": configured["error"]}}
    if configured["model"] is None:
        envelope_effective = dict(_blocked(None, None, configured["error"] or "main_model_unresolved"))
        return {"schema": SCHEMA, "agent_id": AGENT_ID, "configured": configured,
                "effective": envelope_effective}
    session = resolve_session(session_key, session_id)
    if session["basis"] == "configured-unpinned":
        effective = dict(session)
        effective["model"] = configured["model"]
    else:
        effective = session
    return {"schema": SCHEMA, "agent_id": AGENT_ID, "configured": configured,
            "effective": effective}


def _finding(severity: str, code: str, message: str, **detail: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if detail:
        row["detail"] = detail
    return row


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and HEX64_RE.fullmatch(value) is not None


def _strict_envelope(model_route: dict[str, Any]) -> list[dict[str, Any]]:
    """Structural validation of a PRESENT envelope. Any deviation is a
    critical finding; a present envelope is never downgraded to legacy."""
    findings: list[dict[str, Any]] = []
    envelope = model_route.get("model_selection")
    if not isinstance(envelope, dict):
        findings.append(_finding("critical", "model_selection_envelope_invalid",
                                 "A present model_selection envelope must be an object."))
        return findings
    for raw_key in list(envelope.keys()):
        if raw_key in RAW_IDENTIFIER_KEYS:
            findings.append(_finding("critical", "session_raw_identifier_exposed",
                                     "Raw session identifiers must never enter the trusted envelope.",
                                     field=str(raw_key)))
        elif raw_key not in ENVELOPE_KEYS:
            findings.append(_finding("critical", "model_selection_envelope_unknown_field",
                                     "Unknown envelope field.", field=str(raw_key)))
    if envelope.get("schema") != SCHEMA:
        findings.append(_finding("critical", "model_selection_schema_invalid",
                                 "Envelope schema is not this selection owner version."))
    if envelope.get("agent_id") != AGENT_ID:
        findings.append(_finding("critical", "model_selection_agent_invalid",
                                 "Envelope agent is not the Main agent."))
    configured = envelope.get("configured")
    if not isinstance(configured, dict):
        findings.append(_finding("critical", "model_selection_configured_invalid",
                                 "Envelope configured selection must be an object."))
    else:
        for raw_key in list(configured.keys()):
            if raw_key not in CONFIGURED_KEYS:
                findings.append(_finding("critical", "model_selection_envelope_unknown_field",
                                         "Unknown configured field.", field=str(raw_key)))
        if configured.get("agent_id") != AGENT_ID:
            findings.append(_finding("critical", "model_selection_agent_invalid",
                                     "Configured agent is not the Main agent."))
        if configured.get("model") is not None and not _is_exact_model(configured.get("model")):
            findings.append(_finding("critical", "model_selection_model_invalid",
                                     "Configured model is not an exact provider/model ref."))
        if configured.get("config_sha256") is not None and not _valid_hash(configured.get("config_sha256")):
            findings.append(_finding("critical", "model_selection_hash_invalid",
                                     "Config hash is malformed."))
        if configured.get("source") is not None and not isinstance(configured.get("source"), str):
            findings.append(_finding("critical", "model_selection_configured_invalid",
                                     "Configured source has the wrong type."))
        if configured.get("error") is not None and not isinstance(configured.get("error"), str):
            findings.append(_finding("critical", "model_selection_configured_invalid",
                                     "Configured error has the wrong type."))
    effective = envelope.get("effective")
    if not isinstance(effective, dict):
        findings.append(_finding("critical", "model_selection_effective_invalid",
                                 "Envelope effective selection must be an object."))
    else:
        for raw_key in list(effective.keys()):
            if raw_key in RAW_IDENTIFIER_KEYS:
                findings.append(_finding("critical", "session_raw_identifier_exposed",
                                         "Raw session identifiers must never enter the trusted envelope.",
                                         field=str(raw_key)))
            elif raw_key not in EFFECTIVE_KEYS:
                findings.append(_finding("critical", "model_selection_envelope_unknown_field",
                                         "Unknown effective field.", field=str(raw_key)))
        if effective.get("model") is not None and not _is_exact_model(effective.get("model")):
            findings.append(_finding("critical", "model_selection_model_invalid",
                                     "Effective model is not an exact provider/model ref."))
        if effective.get("basis") not in VALID_BASES:
            findings.append(_finding("critical", "model_selection_basis_invalid",
                                     "Effective basis is unknown."))
        for field in ("provider", "source", "error"):
            if effective.get(field) is not None and not isinstance(effective.get(field), str):
                findings.append(_finding("critical", "model_selection_effective_invalid",
                                         f"Effective {field} has the wrong type."))
        for field in ("session_key_sha256", "session_id_sha256"):
            if effective.get(field) is not None and not _valid_hash(effective.get(field)):
                findings.append(_finding("critical", "model_selection_hash_invalid",
                                         f"Effective {field} is malformed."))
        resolved = effective.get("resolved_at_utc")
        if resolved is not None and _parse_utc_z(resolved) is None:
            findings.append(_finding("critical", "session_packet_unreadable",
                                     "The session proof timestamp could not be parsed."))
    return findings


def _revalidate_session_binding(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    """Hashed-identity re-read on the fixed DB. Trusts no packet booleans and
    accepts only valid Main key shapes on the matched row."""
    findings: list[dict[str, Any]] = []
    effective = envelope.get("effective")
    if not isinstance(effective, dict):
        findings.append(_finding("critical", "model_selection_effective_invalid",
                                 "Envelope effective selection must be an object."))
        return findings
    key_hash = effective.get("session_key_sha256")
    id_hash = effective.get("session_id_sha256")
    basis = effective.get("basis")
    if not _valid_hash(key_hash) or not _valid_hash(id_hash):
        findings.append(_finding("critical", "model_selection_hash_invalid",
                                 "Session binding hashes are malformed."))
        return findings
    try:
        db = _open_session_db()
    except (OSError, FileNotFoundError, sqlite3.Error):
        findings.append(_finding("critical", "session_db_unavailable",
                                 "The fixed session database could not be read read-only."))
        return findings
    try:
        db.create_function("sha256", 1,
                           lambda value: hashlib.sha256(str(value).encode("utf-8")).hexdigest())
        schema_failure = _check_schema_owner(db)
        if schema_failure is not None:
            code = "session_schema_unsupported" if schema_failure == "session_schema_unsupported" \
                else "session_schema_unexpected"
            findings.append(_finding("critical", code,
                                     "Session database ownership or schema did not match the Main agent."))
            return findings
        try:
            rows = db.execute(
                f"SELECT {_PIN_COLUMNS} FROM session_nodes "
                "WHERE sha256(session_key)=? AND sha256(current_session_id)=? "
                "AND session_key GLOB 'agent:main:*' "
                "AND current_session_id GLOB '????????-????-????-????-????????????'",
                (key_hash, id_hash),
            ).fetchall()
        except sqlite3.Error:
            findings.append(_finding("critical", "session_entry_invalid",
                                     "The session entry could not be read."))
            return findings
    finally:
        db.close()
    if len(rows) != 1:
        findings.append(_finding("critical", "session_unknown_or_replaced",
                                 "The bound session is unknown, mismatched, reset, or replaced."))
        return findings
    _live_key, _live_id, raw_provider, raw_model, raw_source, entry_valid = rows[0]
    if entry_valid != 1:
        findings.append(_finding("critical", "session_entry_invalid",
                                 "The bound session entry is not valid."))
        return findings
    pinned = not (raw_provider is None and raw_model is None and raw_source is None)
    if basis == "configured-unpinned":
        if pinned:
            findings.append(_finding("critical", "session_pin_changed",
                                     "The bound window is now pinned; the unpinned proof no longer holds."))
        return findings
    if basis == "user-pin-selected":
        if not pinned:
            findings.append(_finding("critical", "session_pin_changed",
                                     "The pinned window was reset to unpinned."))
            return findings
        provider = raw_provider if _is_exact_token(raw_provider) else None
        model = raw_model if isinstance(raw_model, str) else None
        source = raw_source if isinstance(raw_source, str) else None
        if provider is None or model is None or source != "user":
            findings.append(_finding("critical", "session_pin_tampered",
                                     "The live session pin is partial or not user-authorized."))
            return findings
        expected_model = model if "/" in model and model.partition("/")[0] == provider \
            else (f"{provider}/{model}" if "/" not in model else None)
        if expected_model is None or not _is_exact_model(expected_model):
            findings.append(_finding("critical", "session_pin_tampered",
                                     "The live session pin is not an exact provider/model ref."))
            return findings
        if (provider != effective.get("provider") or expected_model != effective.get("model")
                or source != effective.get("source")):
            findings.append(_finding("critical", "session_pin_tampered",
                                     "The live session pin no longer matches the packet envelope."))
        return findings
    findings.append(_finding("critical", "model_selection_basis_invalid",
                             "Effective basis is unknown."))
    return findings


def validate_main_route(model_route: dict[str, Any], config_path: str | Path,
                        *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Shared validator for router + linter. Returns finding dicts with
    severity/code/message/detail. Empty means the Main route is accepted."""
    moment = _coerce_moment(now) or utc_now()
    findings: list[dict[str, Any]] = []
    route = model_route if isinstance(model_route, dict) else {}
    expected = route.get("expected_model_path")
    alias = route.get("model")
    if alias is not None and expected is not None and alias != expected:
        findings.append(_finding("critical", "model_alias_mismatch",
                                 "The model alias must equal the expected model path.",
                                 model=alias, expected_model_path=expected))
    configured = resolve_configured(config_path)
    if configured["model"] is None:
        findings.append(_finding("critical", "main_selection_unreadable",
                                 "The configured Main model could not be read; no fallback applies.",
                                 error=configured["error"]))
        return findings
    if "model_selection" not in route:
        # Legacy handmade/model-only packet: conservatively accept only the
        # currently configured model (expected_model_path or, when absent,
        # the model alias), and never a session pin without a trusted envelope.
        candidate = expected if expected is not None else alias
        if candidate != configured["model"]:
            findings.append(_finding("critical", "main_model_invalid",
                                     "Main routes must use the configured Main model.",
                                     expected_model_path=candidate,
                                     configured_model=configured["model"]))
            findings.append(_finding("critical", "main_live_model_mismatch",
                                     "The routed Main model must equal the live configured Main model.",
                                     expected_model_path=candidate,
                                     live_model_path=configured["model"]))
        for stray in ("session_pin", "main_session_key", "main_session_id",
                      "session_key", "current_session_id"):
            if route.get(stray) is not None:
                findings.append(_finding("critical", "session_pin_without_envelope",
                                         "A session pin requires a trusted model_selection envelope.",
                                         field=stray))
                break
        return findings
    findings.extend(_strict_envelope(route))
    envelope = route.get("model_selection")
    if not isinstance(envelope, dict):
        return findings
    if any(item["severity"] == "critical" for item in findings):
        # Structurally untrusted envelope: report shape defects only, never
        # treat its claims as evidence.
        return findings
    env_configured = envelope.get("configured", {})
    if env_configured.get("config_sha256") != configured["config_sha256"] \
            or env_configured.get("model") != configured["model"]:
        findings.append(_finding("critical", "main_selection_config_drift",
                                 "Configuration drifted between route creation and validation.",
                                 created_model=env_configured.get("model"),
                                 current_model=configured["model"]))
    effective = envelope.get("effective", {})
    basis = effective.get("basis")
    if expected != effective.get("model"):
        findings.append(_finding("critical", "main_model_invalid",
                                 "The routed Main model must equal the resolved effective selection.",
                                 expected_model_path=expected,
                                 effective_model=effective.get("model")))
    if basis == "configured":
        if effective.get("model") != configured["model"]:
            findings.append(_finding("critical", "main_model_invalid",
                                     "The routed Main model must equal the configured Main model.",
                                     expected_model_path=effective.get("model"),
                                     configured_model=configured["model"]))
        for field in ("provider", "source", "session_key_sha256", "session_id_sha256"):
            if effective.get(field) is not None:
                findings.append(_finding("critical", "model_selection_effective_invalid",
                                         "A configured selection carries no session identifiers.",
                                         field=field))
        if effective.get("error") != configured["error"]:
            findings.append(_finding("critical", "main_selection_config_drift",
                                     "Configured error state changed between creation and validation."))
    elif basis in ("configured-unpinned", "user-pin-selected"):
        resolved_at = _parse_utc_z(effective.get("resolved_at_utc"))
        if resolved_at is None:
            findings.append(_finding("critical", "session_packet_unreadable",
                                     "The session proof timestamp could not be parsed."))
        else:
            if resolved_at - moment > FUTURE_SKEW:
                findings.append(_finding("critical", "session_packet_future",
                                         "The session proof timestamp is in the future."))
            elif moment - resolved_at > PACKET_MAX_AGE:
                findings.append(_finding("critical", "session_packet_stale",
                                         "The session proof is older than 15 minutes; rebuild the packet."))
        findings.extend(_revalidate_session_binding(envelope))
    else:
        findings.append(_finding("critical", "main_selection_blocked",
                                 "The Main selection is blocked and must not route.",
                                 error=effective.get("error") if isinstance(effective, dict) else None))
    return findings
