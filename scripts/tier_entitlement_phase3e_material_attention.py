#!/usr/bin/env python3
"""Build a non-authoritative Tier C material-attention candidate ledger.

Phase 3E is intentionally not a queue, recommendation surface, tier writer, or
provider gate.  It projects explicitly supplied material events onto active
Tier C identities from one guarded SQL read, carries every unresolved item
forward, and emits changed-only notifications.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from finance_sql_canon_access import (
    DynamicEntitlementScopeError,
    FinanceSqlCanonAccess,
)


INPUT_SCHEMA = "veritas.tier_entitlement.phase3e.material_attention_input.v1"
OUTPUT_SCHEMA = (
    "veritas.tier_entitlement.phase3e.material_attention_candidate_ledger.v1"
)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PHASE3E_OUTPUT_ROOT = WORKSPACE_ROOT / "tmp" / "phase3e-material-attention"

ADMITTED_EVENT_KINDS = frozenset(
    {"invalidation_alert", "thesis_change", "catalyst_alert", "evidence_conflict"}
)
UNDEFINED_POLICY_KINDS = frozenset({"freshness_decay", "price_reference_change"})
CAUSE_SCOPES = frozenset({"ticker_specific", "broad_macro"})
UPDATE_KINDS = frozenset({"reviewed", "deferred", "resolved"})
FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "priority",
        "rank",
        "score",
        "p0",
        "p3",
        "queue_owner",
        "effective_tier_override",
        "recommendation",
        "approval",
        "action",
        "provider_request",
    }
)
HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$")

TOP_LEVEL_KEYS = frozenset(
    {"schema", "run_id", "market_day", "events", "status_updates"}
)
MARKET_DAY_KEYS = frozenset({"id", "ordinal", "calendar_owner", "calendar_version"})
EVENT_KEYS = frozenset(
    {
        "symbol",
        "event_kind",
        "event_state",
        "cause",
        "source_owner",
        "source_version",
        "source_event_id",
        "materiality",
        "cause_scope",
        "ticker_consequence_ref",
        "source_policy_ref",
        "evidence_refs",
    }
)
STATUS_UPDATE_KEYS = frozenset(
    {
        "event_dedupe_key",
        "update_kind",
        "recorded_by_owner",
        "market_day_id",
        "market_day_ordinal",
        "displaced_by_work_ref",
        "resolution_source_event_id",
    }
)
PRIOR_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "status",
        "run_id",
        "market_day",
        "authority",
        "scope_binding",
        "unresolved_candidates",
        "notifications",
        "status_transitions",
        "out_of_lane",
        "identity_and_tier_conflicts",
        "grouped_macro_events",
        "degraded_mode_digest",
        "inherited_blockers",
        "blocking_errors",
    }
)
AUTHORITY_KEYS = frozenset(
    {
        "artifact_class",
        "projection_only",
        "gate_input",
        "queue_owner",
        "queue_priority_authority",
        "tier_write_authority",
        "recommendation_authority",
        "provider_or_external_authority",
        "side_effects",
    }
)
SCOPE_BINDING_KEYS = frozenset(
    {
        "source",
        "resolver_invocation_count",
        "tier_c_scope_fingerprint",
        "sort_semantics",
    }
)


class MaterialAttentionError(ValueError):
    """Fail-closed Phase 3E input or prior-ledger error."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MaterialAttentionError(f"{label}_must_be_object")
    return value


def _require_exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        detail = {"missing": missing, "unknown": unknown}
        raise MaterialAttentionError(f"{label}_keys:{canonical_json_bytes(detail).decode()}")


def _require_string(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
    maximum: int = 512,
) -> str:
    if not isinstance(value, str):
        raise MaterialAttentionError(f"{label}_must_be_string")
    text = value.strip()
    if not allow_empty and not text:
        raise MaterialAttentionError(f"{label}_empty")
    if len(text) > maximum or "\x00" in text or "\r" in text or "\n" in text:
        raise MaterialAttentionError(f"{label}_invalid")
    return text


def _require_identifier(value: object, label: str) -> str:
    text = _require_string(value, label, maximum=256)
    if not IDENTIFIER_RE.fullmatch(text):
        raise MaterialAttentionError(f"{label}_invalid")
    return text


def _require_canonical_string(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
    maximum: int = 512,
) -> str:
    text = _require_string(value, label, allow_empty=allow_empty, maximum=maximum)
    if text != value:
        raise MaterialAttentionError(f"{label}_not_canonical")
    return text


def _require_canonical_identifier(
    value: object, label: str, *, maximum: int = 256
) -> str:
    text = _require_canonical_string(value, label, maximum=maximum)
    if not IDENTIFIER_RE.fullmatch(text):
        raise MaterialAttentionError(f"{label}_invalid")
    return text


def _require_ordinal(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise MaterialAttentionError(f"{label}_must_be_nonnegative_integer")
    return value


def _reject_authority_fields(value: object, path: str = "input") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.casefold() in FORBIDDEN_AUTHORITY_FIELDS:
                raise MaterialAttentionError(f"authority_shaped_field_rejected:{path}.{key}")
            _reject_authority_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_authority_fields(child, f"{path}[{index}]")


def _validate_market_day(value: object) -> dict[str, Any]:
    row = _require_object(value, "market_day")
    _require_exact_keys(row, MARKET_DAY_KEYS, "market_day")
    return {
        "id": _require_identifier(row["id"], "market_day.id"),
        "ordinal": _require_ordinal(row["ordinal"], "market_day.ordinal"),
        "calendar_owner": _require_identifier(
            row["calendar_owner"], "market_day.calendar_owner"
        ),
        "calendar_version": _require_identifier(
            row["calendar_version"], "market_day.calendar_version"
        ),
    }


def _validate_prior_market_day(value: object) -> dict[str, Any]:
    row = _require_object(value, "prior.market_day")
    _require_exact_keys(row, MARKET_DAY_KEYS, "prior.market_day")
    return {
        "id": _require_canonical_identifier(row["id"], "prior.market_day.id"),
        "ordinal": _require_ordinal(row["ordinal"], "prior.market_day.ordinal"),
        "calendar_owner": _require_canonical_identifier(
            row["calendar_owner"], "prior.market_day.calendar_owner"
        ),
        "calendar_version": _require_canonical_identifier(
            row["calendar_version"], "prior.market_day.calendar_version"
        ),
    }


def _validate_event(value: object, index: int) -> dict[str, Any]:
    label = f"events[{index}]"
    row = _require_object(value, label)
    _require_exact_keys(row, EVENT_KEYS, label)
    evidence = row["evidence_refs"]
    if not isinstance(evidence, list) or len(evidence) > 128:
        raise MaterialAttentionError(f"{label}.evidence_refs_invalid")
    evidence_refs = sorted(
        {
            _require_string(item, f"{label}.evidence_refs", maximum=512)
            for item in evidence
        }
    )
    event = {
        "symbol": _require_string(row["symbol"], f"{label}.symbol", maximum=32).upper(),
        "event_kind": _require_identifier(row["event_kind"], f"{label}.event_kind"),
        "event_state": _require_identifier(row["event_state"], f"{label}.event_state"),
        "cause": _require_identifier(row["cause"], f"{label}.cause"),
        "source_owner": _require_identifier(
            row["source_owner"], f"{label}.source_owner"
        ),
        "source_version": _require_identifier(
            row["source_version"], f"{label}.source_version"
        ),
        "source_event_id": _require_identifier(
            row["source_event_id"], f"{label}.source_event_id"
        ),
        "materiality": _require_identifier(
            row["materiality"], f"{label}.materiality"
        ),
        "cause_scope": _require_identifier(
            row["cause_scope"], f"{label}.cause_scope"
        ),
        "ticker_consequence_ref": _require_string(
            row["ticker_consequence_ref"],
            f"{label}.ticker_consequence_ref",
            allow_empty=True,
            maximum=512,
        ),
        "source_policy_ref": _require_string(
            row["source_policy_ref"],
            f"{label}.source_policy_ref",
            allow_empty=True,
            maximum=512,
        ),
        "evidence_refs": evidence_refs,
    }
    return event


def _validate_status_update(value: object, index: int) -> dict[str, Any]:
    label = f"status_updates[{index}]"
    row = _require_object(value, label)
    _require_exact_keys(row, STATUS_UPDATE_KEYS, label)
    key = _require_string(row["event_dedupe_key"], f"{label}.event_dedupe_key")
    if not HEX_64_RE.fullmatch(key):
        raise MaterialAttentionError(f"{label}.event_dedupe_key_invalid")
    kind = _require_identifier(row["update_kind"], f"{label}.update_kind")
    if kind not in UPDATE_KINDS:
        raise MaterialAttentionError(f"{label}.update_kind_invalid")
    return {
        "event_dedupe_key": key,
        "update_kind": kind,
        "recorded_by_owner": _require_identifier(
            row["recorded_by_owner"], f"{label}.recorded_by_owner"
        ),
        "market_day_id": _require_identifier(
            row["market_day_id"], f"{label}.market_day_id"
        ),
        "market_day_ordinal": _require_ordinal(
            row["market_day_ordinal"], f"{label}.market_day_ordinal"
        ),
        "displaced_by_work_ref": _require_string(
            row["displaced_by_work_ref"],
            f"{label}.displaced_by_work_ref",
            allow_empty=True,
            maximum=512,
        ),
        "resolution_source_event_id": _require_string(
            row["resolution_source_event_id"],
            f"{label}.resolution_source_event_id",
            allow_empty=True,
            maximum=512,
        ),
    }


def validate_input_document(value: object) -> dict[str, Any]:
    row = _require_object(value, "input")
    _reject_authority_fields(row)
    _require_exact_keys(row, TOP_LEVEL_KEYS, "input")
    if row.get("schema") != INPUT_SCHEMA:
        raise MaterialAttentionError("input_schema_mismatch")
    events = row["events"]
    updates = row["status_updates"]
    if not isinstance(events, list) or len(events) > 10_000:
        raise MaterialAttentionError("events_invalid")
    if not isinstance(updates, list) or len(updates) > 10_000:
        raise MaterialAttentionError("status_updates_invalid")
    return {
        "schema": INPUT_SCHEMA,
        "run_id": _require_identifier(row["run_id"], "run_id"),
        "market_day": _validate_market_day(row["market_day"]),
        "events": [_validate_event(item, index) for index, item in enumerate(events)],
        "status_updates": [
            _validate_status_update(item, index) for index, item in enumerate(updates)
        ],
    }


def _candidate_dedupe_key(canonical_ticker: str, event: Mapping[str, Any]) -> str:
    return _sha256(
        [
            canonical_ticker,
            event["event_state"],
            event["cause"],
            event["source_version"],
        ]
    )


def _material_content_hash(canonical_ticker: str, event: Mapping[str, Any]) -> str:
    return _sha256(
        [
            canonical_ticker,
            event["event_kind"],
            event["event_state"],
            event["cause"],
            event["source_owner"],
            event["source_version"],
            event["materiality"],
            event["cause_scope"],
            event["ticker_consequence_ref"],
            event["source_policy_ref"],
            sorted(set(event["evidence_refs"])),
        ]
    )


def _new_candidate(
    canonical_ticker: str,
    event: Mapping[str, Any],
    market_day: Mapping[str, Any],
) -> dict[str, Any]:
    key = _candidate_dedupe_key(canonical_ticker, event)
    return {
        "event_dedupe_key": key,
        "canonical_ticker": canonical_ticker,
        "guarded_sql_tier": "C",
        "event_kind": event["event_kind"],
        "event_state": event["event_state"],
        "cause": event["cause"],
        "source_owner": event["source_owner"],
        "source_version": event["source_version"],
        "latest_source_event_id": event["source_event_id"],
        "materiality": "material",
        "cause_scope": event["cause_scope"],
        "ticker_consequence_ref": event["ticker_consequence_ref"],
        "source_policy_ref": event["source_policy_ref"],
        "evidence_refs": list(event["evidence_refs"]),
        "material_content_hash": _material_content_hash(canonical_ticker, event),
        "first_seen": {
            "market_day_id": market_day["id"],
            "market_day_ordinal": market_day["ordinal"],
        },
        "last_status_refresh": {
            "market_day_id": market_day["id"],
            "market_day_ordinal": market_day["ordinal"],
            "kind": "new",
        },
        "age_market_days": 0,
        "status_refresh_age_market_days": 0,
        "latest_deferral": None,
        "review_owner": None,
        "debts": ["owner_unassigned", "queue_owner_absent"],
    }


def _validate_candidate(candidate: object, index: int) -> dict[str, Any]:
    label = f"prior.unresolved_candidates[{index}]"
    row = _require_object(candidate, label)
    required = {
        "event_dedupe_key",
        "canonical_ticker",
        "guarded_sql_tier",
        "event_kind",
        "event_state",
        "cause",
        "source_owner",
        "source_version",
        "latest_source_event_id",
        "materiality",
        "cause_scope",
        "ticker_consequence_ref",
        "source_policy_ref",
        "evidence_refs",
        "material_content_hash",
        "first_seen",
        "last_status_refresh",
        "age_market_days",
        "status_refresh_age_market_days",
        "latest_deferral",
        "review_owner",
        "debts",
    }
    _require_exact_keys(row, frozenset(required), label)
    key = _require_canonical_string(
        row["event_dedupe_key"], f"{label}.event_dedupe_key"
    )
    content_hash = _require_canonical_string(
        row["material_content_hash"], f"{label}.material_content_hash"
    )
    if not HEX_64_RE.fullmatch(key) or not HEX_64_RE.fullmatch(content_hash):
        raise MaterialAttentionError(f"{label}_hash_invalid")
    if row.get("guarded_sql_tier") != "C" or row.get("materiality") != "material":
        raise MaterialAttentionError(f"{label}_authority_or_materiality_invalid")
    canonical_ticker = _require_canonical_identifier(
        row["canonical_ticker"], f"{label}.canonical_ticker", maximum=32
    )
    if canonical_ticker != canonical_ticker.upper():
        raise MaterialAttentionError(f"{label}.canonical_ticker_not_canonical")
    for field in (
        "event_kind",
        "event_state",
        "cause",
        "source_owner",
        "source_version",
        "latest_source_event_id",
        "cause_scope",
    ):
        _require_canonical_identifier(row[field], f"{label}.{field}")
    if row["event_kind"] not in ADMITTED_EVENT_KINDS:
        raise MaterialAttentionError(f"{label}.event_kind_invalid")
    if row["cause_scope"] not in CAUSE_SCOPES:
        raise MaterialAttentionError(f"{label}.cause_scope_invalid")
    for field in ("ticker_consequence_ref", "source_policy_ref"):
        _require_canonical_string(
            row[field], f"{label}.{field}", allow_empty=True, maximum=512
        )
    semantic_error = _candidate_admissibility_error(row)
    if semantic_error:
        raise MaterialAttentionError(f"{label}_{semantic_error}")
    first_seen = _require_object(row["first_seen"], f"{label}.first_seen")
    refresh = _require_object(row["last_status_refresh"], f"{label}.last_status_refresh")
    for timing, timing_label in ((first_seen, "first_seen"), (refresh, "last_status_refresh")):
        required_timing = {"market_day_id", "market_day_ordinal"}
        if timing_label == "last_status_refresh":
            required_timing.add("kind")
        _require_exact_keys(timing, frozenset(required_timing), f"{label}.{timing_label}")
        _require_canonical_identifier(
            timing["market_day_id"], f"{label}.{timing_label}.market_day_id"
        )
        _require_ordinal(
            timing["market_day_ordinal"], f"{label}.{timing_label}.market_day_ordinal"
        )
    if refresh["market_day_ordinal"] < first_seen["market_day_ordinal"]:
        raise MaterialAttentionError(f"{label}_refresh_before_first_seen")
    if refresh["kind"] not in {"new", "reviewed", "deferred"}:
        raise MaterialAttentionError(f"{label}.last_status_refresh.kind_invalid")
    evidence = row["evidence_refs"]
    debts = row["debts"]
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise MaterialAttentionError(f"{label}.evidence_refs_invalid")
    if not isinstance(debts, list) or not all(isinstance(item, str) for item in debts):
        raise MaterialAttentionError(f"{label}.debts_invalid")
    for item in evidence:
        _require_canonical_string(item, f"{label}.evidence_refs", maximum=512)
    for item in debts:
        _require_canonical_string(item, f"{label}.debts", maximum=512)
    if evidence != sorted(set(evidence)) or debts != sorted(set(debts)):
        raise MaterialAttentionError(f"{label}_noncanonical_lists")
    for field in ("age_market_days", "status_refresh_age_market_days"):
        _require_ordinal(row[field], f"{label}.{field}")
    review_owner = row["review_owner"]
    if review_owner is not None:
        _require_canonical_identifier(review_owner, f"{label}.review_owner")
    latest_deferral = row["latest_deferral"]
    if latest_deferral is not None:
        latest_deferral = _require_object(
            latest_deferral, f"{label}.latest_deferral"
        )
        _require_exact_keys(
            latest_deferral,
            frozenset(
                {
                    "market_day_id",
                    "market_day_ordinal",
                    "recorded_by_owner",
                    "displaced_by_work_ref",
                }
            ),
            f"{label}.latest_deferral",
        )
        _require_canonical_identifier(
            latest_deferral["market_day_id"],
            f"{label}.latest_deferral.market_day_id",
        )
        _require_ordinal(
            latest_deferral["market_day_ordinal"],
            f"{label}.latest_deferral.market_day_ordinal",
        )
        _require_canonical_identifier(
            latest_deferral["recorded_by_owner"],
            f"{label}.latest_deferral.recorded_by_owner",
        )
        _require_canonical_string(
            latest_deferral["displaced_by_work_ref"],
            f"{label}.latest_deferral.displaced_by_work_ref",
            maximum=512,
        )
    expected_key = _sha256(
        [
            str(row["canonical_ticker"]),
            str(row["event_state"]),
            str(row["cause"]),
            str(row["source_version"]),
        ]
    )
    if key != expected_key:
        raise MaterialAttentionError(f"{label}_dedupe_key_mismatch")
    expected_content_hash = _material_content_hash(canonical_ticker, row)
    if content_hash != expected_content_hash:
        raise MaterialAttentionError(f"{label}_material_content_hash_mismatch")
    return copy.deepcopy(row)


def _validate_prior(prior: object | None) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    if prior is None:
        return None, {}
    row = _require_object(prior, "prior")
    _require_exact_keys(row, PRIOR_TOP_LEVEL_KEYS, "prior")
    if row.get("schema") != OUTPUT_SCHEMA:
        raise MaterialAttentionError("prior_schema_mismatch")
    if row.get("status") not in {"review_only_candidates", "blocked"}:
        raise MaterialAttentionError("prior_status_invalid")
    market_day = _validate_prior_market_day(row.get("market_day"))
    authority = _require_object(row.get("authority"), "prior.authority")
    _require_exact_keys(authority, AUTHORITY_KEYS, "prior.authority")
    required_false = (
        "queue_owner",
        "queue_priority_authority",
        "tier_write_authority",
        "recommendation_authority",
        "provider_or_external_authority",
    )
    if any(authority.get(key) is not False for key in required_false):
        raise MaterialAttentionError("prior_authority_clamp_invalid")
    if (
        authority.get("artifact_class")
        != "non_authoritative_attention_candidate_ledger"
        or authority.get("projection_only") is not True
        or authority.get("gate_input") is not False
        or authority.get("side_effects")
        != "optional_named_workspace_local_json_only"
    ):
        raise MaterialAttentionError("prior_authority_identity_invalid")
    scope_binding = _require_object(row.get("scope_binding"), "prior.scope_binding")
    _require_exact_keys(scope_binding, SCOPE_BINDING_KEYS, "prior.scope_binding")
    if scope_binding.get("tier_c_scope_fingerprint") is not None:
        raise MaterialAttentionError("prior_tier_c_fingerprint_forbidden")
    if (
        scope_binding.get("source")
        != "shared_guarded_sql_dynamic_entitlement_scope"
        or scope_binding.get("resolver_invocation_count") != 1
        or scope_binding.get("sort_semantics") != "deterministic_only_not_priority"
    ):
        raise MaterialAttentionError("prior_scope_binding_invalid")
    if row.get("inherited_blockers") != ["external_baseline_blocked"]:
        raise MaterialAttentionError("prior_inherited_blocker_missing")
    candidates = row.get("unresolved_candidates")
    if not isinstance(candidates, list):
        raise MaterialAttentionError("prior_unresolved_candidates_invalid")
    open_items: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(candidates):
        candidate = _validate_candidate(item, index)
        key = candidate["event_dedupe_key"]
        if key in open_items:
            raise MaterialAttentionError("prior_duplicate_event_dedupe_key")
        expected_age = market_day["ordinal"] - candidate["first_seen"]["market_day_ordinal"]
        expected_refresh_age = (
            market_day["ordinal"]
            - candidate["last_status_refresh"]["market_day_ordinal"]
        )
        if expected_age < 0 or expected_refresh_age < 0:
            raise MaterialAttentionError("prior_candidate_market_day_regression")
        if (
            candidate["age_market_days"] != expected_age
            or candidate["status_refresh_age_market_days"] != expected_refresh_age
        ):
            raise MaterialAttentionError("prior_candidate_age_mismatch")
        open_items[key] = candidate
    return market_day, open_items


def _validate_market_day_progression(
    current: Mapping[str, Any], prior: Mapping[str, Any] | None
) -> None:
    if prior is None:
        return
    if (
        current["calendar_owner"] != prior["calendar_owner"]
        or current["calendar_version"] != prior["calendar_version"]
    ):
        raise MaterialAttentionError("market_day_calendar_binding_changed")
    if current["ordinal"] < prior["ordinal"]:
        raise MaterialAttentionError("market_day_ordinal_regression")
    if current["ordinal"] == prior["ordinal"] and current["id"] != prior["id"]:
        raise MaterialAttentionError("market_day_id_conflict")


def _enumerated_scope_error(exc: Exception) -> str:
    code = str(exc).strip()
    allowed = {
        "guarded_sql_scope_tier_conflict",
        "guarded_sql_scope_alias_conflict",
        "guarded_sql_scope_empty",
        "guarded_sql_scope_invalid_envelope",
    }
    return code if code in allowed else "guarded_sql_scope_unavailable"


def _event_issue(event: Mapping[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    result = {
        "source_event_id": event["source_event_id"],
        "symbol": event["symbol"],
        "event_kind": event["event_kind"],
        "source_owner": event["source_owner"],
        "source_version": event["source_version"],
        "reason": reason,
    }
    result.update(extra)
    return result


def _admissibility_error(event: Mapping[str, Any]) -> str | None:
    kind = event["event_kind"]
    if kind in UNDEFINED_POLICY_KINDS:
        return "undefined_phase3e_policy_kind"
    if kind not in ADMITTED_EVENT_KINDS:
        return "unsupported_event_kind"
    if event["materiality"] != "material":
        return "upstream_materiality_not_material"
    if event["cause_scope"] not in CAUSE_SCOPES:
        return "invalid_cause_scope"
    if kind == "catalyst_alert" and not event["ticker_consequence_ref"]:
        return "catalyst_missing_distinct_ticker_consequence"
    if event["cause"] == "serious_freshness_conflict":
        if kind != "evidence_conflict" or not event["source_policy_ref"]:
            return "serious_freshness_conflict_missing_upstream_policy"
    return None


def _candidate_admissibility_error(candidate: Mapping[str, Any]) -> str | None:
    """Reapply admission policy to persisted unresolved candidates."""
    semantic_error = _admissibility_error(candidate)
    if semantic_error:
        return semantic_error
    if (
        candidate["cause_scope"] == "broad_macro"
        and not candidate["ticker_consequence_ref"]
    ):
        return "broad_macro_without_distinct_ticker_consequence"
    return None


def _resolve_alias(scope: object, symbol: str) -> str | None:
    aliases = getattr(scope, "aliases", {})
    identities = getattr(scope, "identities", {})
    normalized = symbol.strip().upper()
    variants = (normalized, normalized.replace(".", "-"), normalized.replace("-", "."))
    resolved = {aliases.get(variant) for variant in variants if aliases.get(variant)}
    if len(resolved) > 1:
        return None
    canonical = next(iter(resolved), None)
    if canonical is None and normalized in identities:
        canonical = normalized
    return canonical


def _refresh_candidate_ages(
    open_items: Mapping[str, dict[str, Any]], market_day: Mapping[str, Any]
) -> None:
    current = market_day["ordinal"]
    for item in open_items.values():
        age = current - item["first_seen"]["market_day_ordinal"]
        refresh_age = current - item["last_status_refresh"]["market_day_ordinal"]
        if age < 0 or refresh_age < 0:
            raise MaterialAttentionError("candidate_market_day_regression")
        item["age_market_days"] = age
        item["status_refresh_age_market_days"] = refresh_age
        debts = {
            debt
            for debt in item.get("debts", [])
            if debt
            not in {"review_or_deferral_overdue", "five_market_day_status_breach"}
        }
        debts.add("queue_owner_absent")
        if item.get("review_owner"):
            debts.discard("owner_unassigned")
        else:
            debts.add("owner_unassigned")
        if refresh_age > 1:
            debts.add("review_or_deferral_overdue")
        if refresh_age > 5:
            debts.add("five_market_day_status_breach")
        item["debts"] = sorted(debts)


def _digest(
    open_items: Mapping[str, Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    reviewed = sum(1 for row in transitions if row["update_kind"] == "reviewed")
    deferred = sum(1 for row in transitions if row["update_kind"] == "deferred")
    oldest = max((row["age_market_days"] for row in open_items.values()), default=0)
    overdue = sum(
        1
        for row in open_items.values()
        if "review_or_deferral_overdue" in row.get("debts", [])
    )
    return {
        "status": "candidate_side_only",
        "total_unresolved_candidates": len(open_items),
        "reviewed_this_run": reviewed,
        "deferred_this_run": deferred,
        "oldest_age_market_days": oldest,
        "overdue_without_review_or_deferral": overdue,
        "total_queued": None,
        "queue_metrics_status": "unavailable_no_owner_surface",
    }


def _base_output(
    request: Mapping[str, Any],
    open_items: Mapping[str, dict[str, Any]],
    *,
    status: str,
    resolver_invocations: int,
    notifications: Sequence[Mapping[str, Any]] = (),
    transitions: Sequence[Mapping[str, Any]] = (),
    out_of_lane: Sequence[Mapping[str, Any]] = (),
    conflicts: Sequence[Mapping[str, Any]] = (),
    macro_groups: Sequence[Mapping[str, Any]] = (),
    blocking_errors: Sequence[str] = (),
) -> dict[str, Any]:
    ordered_items = sorted(
        open_items.values(),
        key=lambda item: (item["first_seen"]["market_day_ordinal"], item["canonical_ticker"], item["event_dedupe_key"]),
    )
    return {
        "schema": OUTPUT_SCHEMA,
        "status": status,
        "run_id": request["run_id"],
        "market_day": copy.deepcopy(request["market_day"]),
        "authority": {
            "artifact_class": "non_authoritative_attention_candidate_ledger",
            "projection_only": True,
            "gate_input": False,
            "queue_owner": False,
            "queue_priority_authority": False,
            "tier_write_authority": False,
            "recommendation_authority": False,
            "provider_or_external_authority": False,
            "side_effects": "optional_named_workspace_local_json_only",
        },
        "scope_binding": {
            "source": "shared_guarded_sql_dynamic_entitlement_scope",
            "resolver_invocation_count": resolver_invocations,
            "tier_c_scope_fingerprint": None,
            "sort_semantics": "deterministic_only_not_priority",
        },
        "unresolved_candidates": ordered_items,
        "notifications": list(notifications),
        "status_transitions": list(transitions),
        "out_of_lane": list(out_of_lane),
        "identity_and_tier_conflicts": list(conflicts),
        "grouped_macro_events": list(macro_groups),
        "degraded_mode_digest": _digest(open_items, transitions),
        "inherited_blockers": ["external_baseline_blocked"],
        "blocking_errors": list(blocking_errors),
    }


def build_material_attention_ledger(
    input_doc: object,
    prior: object | None = None,
    client: FinanceSqlCanonAccess | None = None,
) -> dict[str, Any]:
    """Build one candidate-ledger projection with exactly one guarded read."""

    request = validate_input_document(input_doc)
    prior_day, open_items = _validate_prior(prior)
    _validate_market_day_progression(request["market_day"], prior_day)
    open_items = copy.deepcopy(open_items)

    access = client or FinanceSqlCanonAccess()
    try:
        scope = access.dynamic_entitlement_scope(
            envelope_name=None,
            envelope_count=None,
        )
    except (DynamicEntitlementScopeError, OSError, RuntimeError, sqlite3.Error) as exc:
        _refresh_candidate_ages(open_items, request["market_day"])
        return _base_output(
            request,
            open_items,
            status="blocked",
            resolver_invocations=1,
            blocking_errors=[_enumerated_scope_error(exc)],
        )

    identities = getattr(scope, "identities", None)
    aliases = getattr(scope, "aliases", None)
    if not isinstance(identities, dict) or not isinstance(aliases, dict):
        _refresh_candidate_ages(open_items, request["market_day"])
        return _base_output(
            request,
            open_items,
            status="blocked",
            resolver_invocations=1,
            blocking_errors=["guarded_sql_scope_unavailable"],
        )

    notifications: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    out_of_lane: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    macro_groups: dict[str, dict[str, Any]] = {}
    admitted_batch: dict[str, list[tuple[dict[str, Any], str, str]]] = {}

    for event in request["events"]:
        semantic_error = _admissibility_error(event)
        if semantic_error:
            conflicts.append(_event_issue(event, semantic_error))
            continue
        canonical = _resolve_alias(scope, event["symbol"])
        if canonical is None:
            conflicts.append(_event_issue(event, "unknown_or_conflicting_alias"))
            continue
        membership = identities.get(canonical)
        if membership is None:
            conflicts.append(
                _event_issue(
                    event,
                    "identity_missing_for_resolved_alias",
                    canonical_ticker=canonical,
                )
            )
            continue
        tier = str(getattr(membership, "tier", "")).upper() if membership else ""
        if tier != "C":
            out_of_lane.append(
                _event_issue(
                    event,
                    "effective_tier_not_c",
                    canonical_ticker=canonical,
                    guarded_sql_tier=tier or "unknown",
                    required_truth_class="evidence_join_and_recommendation_queue",
                    owner_surface="no_owner_surface",
                )
            )
            continue
        if event["cause_scope"] == "broad_macro" and not event["ticker_consequence_ref"]:
            group_key = _sha256(
                [
                    event["event_kind"],
                    event["event_state"],
                    event["cause"],
                    event["source_owner"],
                    event["source_version"],
                ]
            )
            group = macro_groups.setdefault(
                group_key,
                {
                    "macro_group_key": group_key,
                    "event_kind": event["event_kind"],
                    "event_state": event["event_state"],
                    "cause": event["cause"],
                    "source_owner": event["source_owner"],
                    "source_version": event["source_version"],
                    "reason": "broad_macro_without_distinct_ticker_consequence",
                    "canonical_tickers": [],
                    "source_event_ids": [],
                },
            )
            group["canonical_tickers"].append(canonical)
            group["source_event_ids"].append(event["source_event_id"])
            continue

        key = _candidate_dedupe_key(canonical, event)
        content_hash = _material_content_hash(canonical, event)
        admitted_batch.setdefault(key, []).append((event, canonical, content_hash))

    for key, rows in admitted_batch.items():
        distinct_hashes = {row[2] for row in rows}
        if len(distinct_hashes) != 1:
            conflicts.append(
                {
                    "event_dedupe_key": key,
                    "source_event_ids": sorted(row[0]["source_event_id"] for row in rows),
                    "reason": "event_dedupe_collision",
                }
            )
            continue
        event, canonical, content_hash = min(
            rows, key=lambda row: canonical_json_bytes(row[0])
        )
        existing = open_items.get(key)
        if existing is None:
            open_items[key] = _new_candidate(canonical, event, request["market_day"])
            notifications.append({"event_dedupe_key": key, "reason": "new"})
        elif existing["material_content_hash"] != content_hash:
            existing.update(
                {
                    "event_kind": event["event_kind"],
                    "latest_source_event_id": event["source_event_id"],
                    "source_owner": event["source_owner"],
                    "materiality": "material",
                    "cause_scope": event["cause_scope"],
                    "ticker_consequence_ref": event["ticker_consequence_ref"],
                    "source_policy_ref": event["source_policy_ref"],
                    "evidence_refs": list(event["evidence_refs"]),
                    "material_content_hash": content_hash,
                }
            )
            notifications.append(
                {"event_dedupe_key": key, "reason": "materially_changed"}
            )

    update_counts: dict[str, int] = {}
    for update in request["status_updates"]:
        key = update["event_dedupe_key"]
        update_counts[key] = update_counts.get(key, 0) + 1
    duplicate_update_keys: set[str] = set()
    for update in request["status_updates"]:
        key = update["event_dedupe_key"]
        if update_counts[key] > 1:
            if key in duplicate_update_keys:
                continue
            duplicate_update_keys.add(key)
            conflicts.append(
                {"event_dedupe_key": key, "reason": "duplicate_status_update"}
            )
            continue
        candidate = open_items.get(key)
        if candidate is None:
            conflicts.append(
                {"event_dedupe_key": key, "reason": "status_update_target_not_unresolved"}
            )
            continue
        if (
            update["market_day_id"] != request["market_day"]["id"]
            or update["market_day_ordinal"] != request["market_day"]["ordinal"]
        ):
            conflicts.append(
                {"event_dedupe_key": key, "reason": "status_update_market_day_mismatch"}
            )
            continue
        kind = update["update_kind"]
        if kind == "deferred" and not update["displaced_by_work_ref"]:
            conflicts.append(
                {"event_dedupe_key": key, "reason": "deferral_missing_displaced_work"}
            )
            continue
        if kind == "resolved":
            if (
                update["recorded_by_owner"] != candidate["source_owner"]
                or not update["resolution_source_event_id"]
            ):
                conflicts.append(
                    {"event_dedupe_key": key, "reason": "resolution_not_source_owner_bound"}
                )
                continue
            del open_items[key]
        else:
            candidate["last_status_refresh"] = {
                "market_day_id": request["market_day"]["id"],
                "market_day_ordinal": request["market_day"]["ordinal"],
                "kind": kind,
            }
            candidate["review_owner"] = update["recorded_by_owner"]
            if kind == "deferred":
                candidate["latest_deferral"] = {
                    "market_day_id": update["market_day_id"],
                    "market_day_ordinal": update["market_day_ordinal"],
                    "recorded_by_owner": update["recorded_by_owner"],
                    "displaced_by_work_ref": update["displaced_by_work_ref"],
                }
        transitions.append(
            {
                "event_dedupe_key": key,
                "canonical_ticker": candidate["canonical_ticker"],
                "update_kind": kind,
                "recorded_by_owner": update["recorded_by_owner"],
                "market_day_id": update["market_day_id"],
                "market_day_ordinal": update["market_day_ordinal"],
                "displaced_by_work_ref": update["displaced_by_work_ref"] or None,
                "resolution_source_event_id": update["resolution_source_event_id"] or None,
            }
        )

    for group in macro_groups.values():
        group["canonical_tickers"] = sorted(set(group["canonical_tickers"]))
        group["source_event_ids"] = sorted(set(group["source_event_ids"]))

    _refresh_candidate_ages(open_items, request["market_day"])
    return _base_output(
        request,
        open_items,
        status="review_only_candidates",
        resolver_invocations=1,
        notifications=sorted(notifications, key=lambda row: row["event_dedupe_key"]),
        transitions=sorted(transitions, key=lambda row: row["event_dedupe_key"]),
        out_of_lane=sorted(
            out_of_lane, key=lambda row: (row.get("canonical_ticker", ""), row["source_event_id"])
        ),
        conflicts=sorted(conflicts, key=lambda row: canonical_json_bytes(row)),
        macro_groups=sorted(macro_groups.values(), key=lambda row: row["macro_group_key"]),
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MaterialAttentionError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_reject_duplicate_json_keys)


def _contained_output_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(PHASE3E_OUTPUT_ROOT)
    except ValueError as exc:
        raise MaterialAttentionError("output_path_outside_phase3e_artifact_root") from exc
    if resolved.suffix.casefold() != ".json":
        raise MaterialAttentionError("output_path_must_be_json")
    return resolved


def _write_json_exclusive_temp(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.phase3e.tmp")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = os.open(temporary, flags, 0o600)
    try:
        payload = canonical_json_bytes(value) + b"\n"
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--out")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = _load_json(args.input)
        prior = _load_json(args.prior) if args.prior else None
        result = build_material_attention_ledger(request, prior=prior)
        if args.validate:
            _validate_prior(result)
        if args.write:
            if not args.out:
                raise MaterialAttentionError("write_requires_out")
            output_path = _contained_output_path(args.out)
            _write_json_exclusive_temp(output_path, result)
        elif args.out:
            raise MaterialAttentionError("out_requires_write")
        print(canonical_json_bytes(result).decode("utf-8"))
        return 0 if result["status"] == "review_only_candidates" else 2
    except (MaterialAttentionError, json.JSONDecodeError, OSError) as exc:
        print(
            canonical_json_bytes(
                {
                    "schema": OUTPUT_SCHEMA,
                    "status": "blocked",
                    "error": str(exc),
                }
            ).decode("utf-8"),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
