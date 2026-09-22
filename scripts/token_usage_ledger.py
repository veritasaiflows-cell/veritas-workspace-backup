#!/usr/bin/env python3
"""Build a metadata-only token usage ledger for cron and implementation work.

Token counts come from the existing model-run ledger, which already reads
OpenClaw cron run usage metadata. Implementation lanes are joined by run_id
when possible; otherwise the ledger records the attribution gap honestly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from isolated_agent_usage_metadata import (
    CONFIGURED_ISOLATED_AGENT_IDS,
    CONFIGURED_ISOLATED_AGENT_ROLES,
    DEFAULT_AGENT_STATE_ROOT,
    dispatch_binding_token_hash_for_attempt,
    hash_reference,
    load_allowlisted_session_usage,
    load_gateway_usage_cost,
    load_verified_isolated_session_usage_for_binding,
)
from concurrent_lane_manager import (
    configured_isolated_agent_state_root,
    configured_openclaw_state_db,
    telemetry_enforcement_applies,
    verify_usage_source_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"
DEFAULT_LEDGER = STATE_HISTORY / "token-usage-ledger.jsonl"
DEFAULT_JSON = TMP / "token-usage-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
CODING_OUTCOME = TMP / "coding-outcome-ledger-current.json"
CODING_OUTCOME_HISTORY = STATE_HISTORY / "coding-outcome-ledger.jsonl"
PRICING = ROOT / "state" / "model-token-pricing.json"
OAUTH_POLICY = ROOT / "state" / "openai-oauth-budget-policy.json"
OAUTH_CAPACITY_CURRENT = ROOT / "state" / "openai-oauth-capacity-current.json"
OAUTH_CAPACITY_HISTORY = STATE_HISTORY / "openai-oauth-capacity.jsonl"
# Legacy parser/testing surface only. Credit-time candidate ingestion below
# uses the physical runtime root selected by concurrent_lane_manager instead.
ISOLATED_AGENT_STATE_ROOT = DEFAULT_AGENT_STATE_ROOT

SCHEMA = "veritas.token_usage_ledger_current.v1"
EVENT_SCHEMA = "veritas.token_usage_ledger_event.v1"
USAGE_SOURCE_RECEIPTS_SCHEMA = "veritas.model_usage_source_receipts.v1"
FLEET_OUTCOME_CREDIT_CONTRACT_VERSION = "veritas.fleet_outcome_credit.v1"
OAUTH_CAPACITY_SCHEMA = "veritas.openai_oauth_capacity_snapshot.v1"
OAUTH_CAPACITY_EVENT_SCHEMA = "veritas.openai_oauth_capacity_event.v1"
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
TOKEN_TOTAL_TOLERANCE_TOKENS = 2
FLEET_OUTCOME_TRACKING_START_UTC = "2026-08-09T00:00:00Z"
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"
TRUSTED_LANE_TOKEN_SOURCES = {
    "codex_native_rollout_jsonl",
    "openclaw_isolated_session_store_v1",
    "openclaw_isolated_session_store_v2",
}
CREDITABLE_ISOLATED_JOIN_STATUSES = {
    "joined_by_run_id",
    "joined_by_attempt_correlation",
}
LANE_RUNTIME_EVENT_PRODUCER = "concurrent_lane_runtime_metadata"
LANE_RUNTIME_EVENT_RUN_KIND = "implementation_lane"
EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS = 10
MAIN_ACCEPTED_OUTCOME_STATES = {
    "accepted",
    "accepted_with_documented_limits",
    "approved",
    "merged",
    "complete",
    "passed",
}

UNSUPPORTED_MODEL_ROUTES = {
    "claude-cli/claude-fable-5": {
        "status": "unsupported_legacy",
        "active_route_countable": False,
        "reason": "Fable is no longer a supported model route; retain historical rows for audit only.",
        "replacement_guidance": "Use openai/gpt-5.6-sol for main/high-stakes synthesis or an approved bounded helper route.",
    },
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "append_only": True,
    "local_only": True,
    "metadata_only": True,
    "cost_estimate_only": True,
    "pricing_required_for_cost": True,
    "actual_billed_cost_inference_allowed": False,
    "automatic_quota_action_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "model_route_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TEXT = (
    "Authorization:",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "raw prompt",
    "raw_prompt",
    "prompt body",
    "user prompt",
    "raw response",
    "raw_response",
    "response body",
    "assistant response",
    "tool payload",
    "tool_payload",
)

FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?i)\bacct_[A-Za-z0-9_-]{6,}\b"),
)

FORBIDDEN_KEY_MARKERS = (
    "prompt",
    "response",
    "tool_input",
    "tool_output",
    "tool_payload",
    "system_prompt",
    "authorization",
    "access_token",
    "refresh_token",
    "oauth_token",
    "secret",
    "credential",
    "header",
    "account_id",
    "account_identity",
    "email",
)

SAFE_EXCLUDED_CONTENT_DECLARATION = {
    "account identity",
    "credentials",
    "raw status text",
    "prompts",
    "responses",
    "tool payloads",
}


def _input_fingerprint(
    ledger_path: Path,
    policy_path: Path = OAUTH_POLICY,
    capacity_path: Path = OAUTH_CAPACITY_CURRENT,
) -> dict[str, Any]:
    """Return a deterministic fingerprint of all inputs that affect the ledger payload.

    Used to decide whether the previous output can be reused unchanged.
    """

    def _file_signature(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        stat = path.stat()
        content = path.read_bytes()
        return {
            "path": rel(path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    inputs: dict[str, Any] = {
        # The builder itself is an input: without this, a code change that alters
        # payload shape is masked by the fast path until a data input happens to change.
        "builder_source": _file_signature(Path(__file__).resolve()),
        "ledger_jsonl": _file_signature(ledger_path),
        "model_run_ledger": _file_signature(MODEL_RUN_LEDGER),
        "lane_register": _file_signature(LANE_REGISTER),
        "coding_outcome": _file_signature(CODING_OUTCOME),
        "coding_outcome_history": _file_signature(CODING_OUTCOME_HISTORY),
        "pricing": _file_signature(PRICING),
        "oauth_policy": _file_signature(policy_path),
        "oauth_capacity": _file_signature(capacity_path),
    }
    # Include isolated agent session store mtimes without reading full content.
    try:
        root = configured_isolated_session_candidate_root()
        if root.exists():
            isolated_stores: list[dict[str, Any]] = []
            for agent_id in CONFIGURED_ISOLATED_AGENT_IDS:
                idx = root / agent_id / "index.json"
                if idx.exists():
                    stat = idx.stat()
                    isolated_stores.append({
                        "agent_id": agent_id,
                        "mtime_ns": stat.st_mtime_ns,
                        "size": stat.st_size,
                    })
            inputs["isolated_agent_indices"] = sorted(isolated_stores, key=lambda x: x["agent_id"])
    except (OSError, RuntimeError, ValueError):
        inputs["isolated_agent_indices"] = []
    return inputs


def _try_fast_path(
    json_out: Path,
    ledger_path: Path,
    policy_path: Path = OAUTH_POLICY,
    capacity_path: Path = OAUTH_CAPACITY_CURRENT,
) -> dict[str, Any] | None:
    """Reuse the previous payload if no inputs have changed.

    This is the primary incremental optimization: when no source artifacts
    changed, the ledger is append-only and pricing/attribution are
    deterministic, so the previous output remains valid. We only refresh the
    generated timestamp and fast-path metadata.
    """
    if not json_out.exists():
        return None
    previous_text = json_out.read_text(encoding="utf-8")
    try:
        previous = json.loads(previous_text)
    except json.JSONDecodeError:
        return None
    if previous.get("schema") != SCHEMA:
        return None
    previous_fingerprint = as_dict(previous.get("_input_fingerprint"))
    if not previous_fingerprint:
        return None
    current_fingerprint = _input_fingerprint(ledger_path, policy_path, capacity_path)
    if current_fingerprint != previous_fingerprint:
        return None
    # Inputs unchanged: reuse payload, bump timestamp, zero append counters.
    payload = dict(previous)
    payload["generated_at_utc"] = utc_now()
    payload["_fast_path"] = {
        "reused": True,
        "reason": "input_fingerprint_unchanged",
        "previous_generated_at_utc": previous.get("generated_at_utc"),
    }
    summary = as_dict(payload.get("summary"))
    summary["appended_event_count"] = 0
    summary["candidate_event_count"] = summary.get("token_event_count", 0)
    payload["summary"] = summary
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def first_int(*values: Any) -> int | None:
    for value in values:
        parsed = as_int(value)
        if parsed is not None:
            return parsed
    return None


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def usage_window_summary(
    events: list[dict[str, Any]],
    now: datetime,
    hours: float,
) -> dict[str, Any]:
    """Summarize only events with a reliable usage timestamp.

    ``recorded_at_utc`` is intentionally never used as a fallback because it
    is ledger-ingestion time, not evidence of when provider usage occurred.
    """
    end = now.astimezone(timezone.utc)
    start = end - timedelta(hours=hours)
    timestamped: list[tuple[dict[str, Any], datetime]] = []
    untrusted_timestamp_count = 0
    for event in events:
        observed = parse_utc(event.get("usage_at_utc"))
        if observed is None:
            continue
        source = str(event.get("usage_time_source") or "").strip().lower()
        trusted_source = source.startswith("entry.ts_") or source in {"provider_timestamp", "lane_completed_at"}
        if trusted_source:
            timestamped.append((event, observed))
        else:
            untrusted_timestamp_count += 1
    selected = [event for event, observed in timestamped if start <= observed <= end]
    api_rows = [event for event in selected if event.get("api_equivalent_cost_usd") is not None]
    credit_rows = [event for event in selected if event.get("estimated_chatgpt_credits") is not None]
    return {
        "status": "current" if timestamped else "unavailable",
        "window_hours": hours,
        "window_start_utc": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "window_end_utc": end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "event_count": len(selected),
        "total_tokens": sum(int(event.get("total_tokens") or 0) for event in selected),
        "api_equivalent_cost_usd": round(
            sum(float(event.get("api_equivalent_cost_usd") or 0) for event in api_rows), 6
        ) if api_rows else None,
        "api_equivalent_cost_rows": len(api_rows),
        "api_equivalent_estimate_status": (
            "unavailable" if not selected or not api_rows
            else "complete" if len(api_rows) == len(selected)
            else "partial_unknown_input_semantics_or_missing_rate"
        ),
        "estimated_chatgpt_credits": round(
            sum(float(event.get("estimated_chatgpt_credits") or 0) for event in credit_rows), 6
        ) if credit_rows else None,
        "estimated_chatgpt_credit_rows": len(credit_rows),
        "chatgpt_credit_estimate_status": (
            "unavailable" if not selected or not credit_rows
            else "complete" if len(credit_rows) == len(selected)
            else "partial_separate_no_public_rate_or_missing_rate"
        ),
        "reliable_usage_timestamp_event_count": len(timestamped),
        "excluded_missing_usage_timestamp_event_count": len(events) - len(timestamped) - untrusted_timestamp_count,
        "excluded_untrusted_usage_timestamp_event_count": untrusted_timestamp_count,
        "trusted_usage_time_sources": ["entry.ts_*", "provider_timestamp", "lane_completed_at"],
        "ingestion_timestamp_used_as_usage_time": False,
    }


def first_ingestion_times(persisted_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Earliest persisted ``recorded_at_utc`` per event id.

    The in-memory view re-derives candidate events every build and
    ``latest_by_event_id`` keeps the newest ``recorded_at_utc``, so an event's
    live field is re-derivation time, not when the ledger first saw it. Only the
    append-only file preserves true first ingestion.
    """
    first: dict[str, str] = {}
    for row in persisted_rows:
        event_id = str(row.get("event_id") or "")
        recorded = row.get("recorded_at_utc")
        if not event_id or not isinstance(recorded, str) or parse_utc(recorded) is None:
            continue
        seen = first.get(event_id)
        if seen is None or recorded < seen:
            first[event_id] = recorded
    return first


def ingestion_window_summary(
    events: list[dict[str, Any]],
    now: datetime,
    hours: float,
    first_ingested_at: dict[str, str],
) -> dict[str, Any]:
    """Summarize events by first ledger-ingestion time as an explicitly weaker tier.

    This is a visibility floor, not a usage measurement. Ingestion time is when
    the ledger first observed a row, so it cannot support provider pace, quota,
    or billing claims. It exists so that recent spend is not reported as zero
    while provider timestamp coverage stays low.
    """
    end = now.astimezone(timezone.utc)
    start = end - timedelta(hours=hours)
    selected: list[dict[str, Any]] = []
    unpersisted = 0
    for event in events:
        event_id = str(event.get("event_id") or "")
        recorded = first_ingested_at.get(event_id)
        if recorded is None:
            unpersisted += 1
            continue
        observed = parse_utc(recorded)
        if observed is not None and start <= observed <= end:
            selected.append(event)
    return {
        "status": "ingestion_time_observed" if selected else "no_rows_in_window",
        "time_basis": "first_persisted_ledger_recorded_at_utc",
        "window_hours": hours,
        "window_start_utc": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "window_end_utc": end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "event_count": len(selected),
        "total_tokens": sum(int(event.get("total_tokens") or 0) for event in selected),
        "excluded_not_yet_persisted_event_count": unpersisted,
        "ingestion_timestamp_used_as_usage_time": True,
        "provider_pace_claim_allowed": False,
        "quota_or_billing_claim_allowed": False,
        "meaning": (
            "Rows the ledger first recorded inside this window. Ingestion time may "
            "lag or batch actual provider usage, so treat this as a lower bound on "
            "recent observation and never as provider pace, quota, or billed cost."
        ),
    }


def safe_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    sensitive_markers = ("bearer", "authorization", "secret", "credential", "prompt", "response", "tool_payload", "account_identity")
    if any(marker in stripped.lower() for marker in sensitive_markers):
        return None
    return stripped if SAFE_LABEL.fullmatch(stripped) else None


def normalize_access_mode(mode: Any, source: Any) -> tuple[str, str]:
    normalized_mode = str(mode or "").strip().lower()
    normalized_source = str(source or "").strip().lower()
    if normalized_mode in {"chatgpt", "apikey"} and normalized_source == "sanitized_producer_metadata":
        return normalized_mode, "sanitized_producer_metadata"
    return "unknown", "unknown"


def normalize_speed_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"standard", "fast"} else "unknown"


def resolve_input_token_semantics(
    input_tokens: Any,
    cached_input_tokens: Any,
    declared_semantics: Any,
) -> dict[str, Any]:
    input_count = as_int(input_tokens)
    cached_count = as_int(cached_input_tokens)
    declared = str(declared_semantics).strip().lower() if declared_semantics is not None else ""
    valid = {"inclusive_cached", "exclusive_cached", "no_cache"}
    if declared == "unknown":
        return {
            "input_token_semantics": "unknown",
            "input_token_semantics_source": "declared_unknown",
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "producer marked input token semantics unknown",
        }
    if declared == "invalid":
        return {
            "input_token_semantics": "invalid",
            "input_token_semantics_source": "declared_invalid",
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "producer marked input token semantics invalid",
        }
    if declared and declared not in valid:
        return {
            "input_token_semantics": "invalid",
            "input_token_semantics_source": "declared_invalid",
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "unsupported declared input_token_semantics value",
        }
    if not declared:
        if cached_count == 0:
            declared = "no_cache"
            source = "derived_from_explicit_zero_cached_tokens"
        else:
            return {
                "input_token_semantics": "unknown",
                "input_token_semantics_source": "legacy_missing",
                "input_token_semantics_valid": False,
                "uncached_input_tokens": None,
                "pricing_cached_input_tokens": None,
                "reason": "legacy row lacks input_token_semantics and does not prove zero cached tokens",
            }
    else:
        source = "declared"
    if input_count is not None and input_count < 0:
        return {
            "input_token_semantics": "invalid",
            "input_token_semantics_source": source,
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "input token count is negative",
        }
    if cached_count is not None and cached_count < 0:
        return {
            "input_token_semantics": "invalid",
            "input_token_semantics_source": source,
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "cached input token count is negative",
        }
    if declared == "no_cache":
        if cached_count not in (None, 0):
            return {
                "input_token_semantics": "invalid",
                "input_token_semantics_source": source,
                "input_token_semantics_valid": False,
                "uncached_input_tokens": None,
                "pricing_cached_input_tokens": None,
                "reason": "no_cache conflicts with non-zero cached input tokens",
            }
        if input_count is None:
            return {
                "input_token_semantics": "invalid",
                "input_token_semantics_source": source,
                "input_token_semantics_valid": False,
                "uncached_input_tokens": None,
                "pricing_cached_input_tokens": None,
                "reason": "no_cache semantics require input_tokens",
            }
        return {
            "input_token_semantics": "no_cache",
            "input_token_semantics_source": source,
            "input_token_semantics_valid": True,
            "uncached_input_tokens": input_count,
            "pricing_cached_input_tokens": 0,
            "reason": "input tokens are entirely uncached",
        }
    if input_count is None:
        return {
            "input_token_semantics": "invalid",
            "input_token_semantics_source": source,
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "declared cached-input semantics require input_tokens",
        }
    if cached_count is None:
        return {
            "input_token_semantics": "invalid",
            "input_token_semantics_source": source,
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "declared cached-input semantics require cached_input_tokens; use no_cache for a zero-cache row",
        }
    if declared == "inclusive_cached":
        if cached_count > input_count:
            return {
                "input_token_semantics": "invalid",
                "input_token_semantics_source": source,
                "input_token_semantics_valid": False,
                "uncached_input_tokens": None,
                "pricing_cached_input_tokens": None,
                "reason": "inclusive cached input exceeds input_tokens",
            }
        return {
            "input_token_semantics": "inclusive_cached",
            "input_token_semantics_source": source,
            "input_token_semantics_valid": True,
            "uncached_input_tokens": max(input_count - (cached_count or 0), 0),
            "pricing_cached_input_tokens": cached_count or 0,
            "reason": "input_tokens includes cached input; uncached input is input minus cached",
        }
    return {
        "input_token_semantics": "exclusive_cached",
        "input_token_semantics_source": source,
        "input_token_semantics_valid": True,
        "uncached_input_tokens": input_count,
        "pricing_cached_input_tokens": cached_count or 0,
        "reason": "input_tokens excludes cached input",
    }


def reconcile_token_total(
    total_tokens: Any,
    output_tokens: Any,
    token_breakdown: dict[str, Any],
    cache_write_tokens: Any = 0,
) -> dict[str, Any]:
    """Reconcile declared totals against normalized token components.

    The fixed two-token tolerance matches ``model_run_ledger.py`` and only
    accommodates small provider counter-finalization differences. Larger
    mismatches fail closed for both API-equivalent and credit estimates.
    """
    total_count = as_int(total_tokens)
    output_count = as_int(output_tokens)
    cache_write_count = as_int(cache_write_tokens)
    reasons: list[str] = []
    if total_count is not None and total_count < 0:
        reasons.append("total_tokens is negative")
    if output_count is None:
        reasons.append("output_tokens missing or invalid")
    elif output_count < 0:
        reasons.append("output_tokens is negative")
    if cache_write_count is None:
        reasons.append("cache_write_tokens missing or invalid")
    elif cache_write_count < 0:
        reasons.append("cache_write_tokens is negative")
    if token_breakdown.get("input_token_semantics_valid") is not True:
        reasons.append(str(token_breakdown.get("reason") or "input token semantics are not valid"))

    expected_total: int | None = None
    if not reasons:
        expected_total = int(token_breakdown.get("uncached_input_tokens") or 0) + int(
            token_breakdown.get("pricing_cached_input_tokens") or 0
        ) + int(cache_write_count or 0) + int(output_count or 0)
        if total_count is None:
            total_count = expected_total

    delta = total_count - expected_total if total_count is not None and expected_total is not None else None
    if delta is not None and abs(delta) > TOKEN_TOTAL_TOLERANCE_TOKENS:
        reasons.append(f"total_tokens differs from semantic total by {delta} tokens")

    return {
        "total_tokens": total_count,
        "token_total_expected": expected_total,
        "token_total_delta": delta,
        "token_total_tolerance_tokens": TOKEN_TOTAL_TOLERANCE_TOKENS,
        "token_semantics_status": "invalid" if reasons else "valid",
        "token_semantics_reasons": reasons,
    }


def api_pricing_rates(
    pricing: dict[str, Any],
    model: dict[str, Any],
    token_breakdown: dict[str, Any],
) -> dict[str, Any]:
    """Select standard versus long-context API rates from explicit pricing metadata."""
    context_input_tokens = int(token_breakdown.get("uncached_input_tokens") or 0) + int(
        token_breakdown.get("pricing_cached_input_tokens") or 0
    )
    limit = as_int(as_dict(pricing.get("pricing_basis")).get("short_context_input_limit_tokens"))
    long_context_rates_available = (
        model.get("long_context_input_per_million") is not None
        and model.get("long_context_output_per_million") is not None
    )
    use_long_context = (
        limit is not None
        and context_input_tokens > limit
        and long_context_rates_available
    )
    prefix = "long_context_" if use_long_context else ""
    return {
        "input_per_million": model.get(f"{prefix}input_per_million"),
        "cached_input_per_million": model.get(f"{prefix}cached_input_per_million"),
        "output_per_million": model.get(f"{prefix}output_per_million"),
        "pricing_context_class": "long_context" if use_long_context else "standard_context",
        "pricing_context_input_tokens": context_input_tokens,
        "pricing_context_limit_tokens": limit,
        "long_context_rates_available": long_context_rates_available,
    }


def model_support(model_path: Any) -> dict[str, Any]:
    if not model_path:
        return {
            "status": "unattributed",
            "active_route_countable": False,
            "reason": "No model_path was stamped by the producer.",
        }
    path = str(model_path)
    unsupported = UNSUPPORTED_MODEL_ROUTES.get(path)
    if unsupported:
        return {"model_path": path, **unsupported}
    return {
        "model_path": path,
        "status": "supported_or_unclassified",
        "active_route_countable": True,
        "reason": "Model is not in the unsupported-route blocklist.",
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.touch(exist_ok=True)
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered == "excluded_content":
                declared = set(child) if isinstance(child, list) and all(isinstance(item, str) for item in child) else set()
                if declared == SAFE_EXCLUDED_CONTENT_DECLARATION:
                    continue
                findings.append(f"invalid_excluded_content_declaration:{path}.{key}")
                continue
            if any(marker in lowered for marker in FORBIDDEN_KEY_MARKERS):
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(marker.lower() in value.lower() for marker in FORBIDDEN_TEXT) or any(
            pattern.search(value) for pattern in FORBIDDEN_VALUE_PATTERNS
        ):
            findings.append(f"forbidden_value:{path}")
    return findings


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def load_pricing(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return payload if payload.get("schema") else {}


def load_policy(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return payload if payload.get("schema") else {}


def resolve_pricing_model(model_path: str | None, pricing: dict[str, Any]) -> tuple[str | None, dict[str, Any], str]:
    if not model_path:
        return None, {}, "missing_model_path"
    models = as_dict(pricing.get("models"))
    if model_path in models:
        return model_path, as_dict(models.get(model_path)), "exact"
    aliases = {**as_dict(pricing.get("aliases")), **as_dict(pricing.get("model_aliases"))}
    candidate = model_path
    visited: set[str] = set()
    while candidate in aliases and candidate not in visited:
        visited.add(candidate)
        candidate = str(aliases[candidate])
        if candidate in models:
            return candidate, as_dict(models.get(candidate)), "alias"
    return candidate, {}, "missing_model_price"


def estimate_cost(
    model_path: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    pricing: dict[str, Any],
    cached_input_tokens: int | None = None,
    input_token_semantics: Any = None,
    token_semantics_status: Any = None,
    cache_write_tokens: Any = 0,
) -> dict[str, Any]:
    """Estimate an API-equivalent benchmark; ``estimated_cost`` is a deprecated alias."""
    token_breakdown = resolve_input_token_semantics(input_tokens, cached_input_tokens, input_token_semantics)
    if token_semantics_status is not None and str(token_semantics_status) != "valid":
        token_breakdown = {
            **token_breakdown,
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "upstream token_semantics_status is not valid",
        }
    if token_breakdown.get("input_token_semantics_valid") is not True:
        semantics_status = "invalid" if token_semantics_status is not None and str(token_semantics_status) != "valid" else str(token_breakdown.get("input_token_semantics") or "unknown")
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": f"{semantics_status}_input_token_semantics",
            "pricing_model_path": None,
            "pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    output_count = as_int(output_tokens)
    if output_count is None or output_count < 0:
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": "missing_output_tokens" if output_count is None else "invalid_output_tokens",
            "pricing_model_path": None,
            "pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    cache_write_count = as_int(cache_write_tokens)
    if cache_write_count is None or cache_write_count < 0:
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": "invalid_cache_write_tokens",
            "pricing_model_path": None,
            "pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    if cache_write_count > 0:
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": "cache_write_pricing_unavailable",
            "pricing_model_path": None,
            "pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    if not model_path or not pricing:
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": "missing_pricing_table",
            "pricing_model_path": None,
            "pricing_resolution": "missing_pricing_table",
            "input_token_breakdown": token_breakdown,
        }
    pricing_model_path, model, resolution = resolve_pricing_model(model_path, pricing)
    if not model:
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": "missing_model_price",
            "pricing_model_path": pricing_model_path,
            "pricing_resolution": resolution,
            "input_token_breakdown": token_breakdown,
        }
    rate_set = api_pricing_rates(pricing, model, token_breakdown)
    input_per_m = rate_set.get("input_per_million")
    cached_input_per_m = rate_set.get("cached_input_per_million")
    output_per_m = rate_set.get("output_per_million")
    try:
        cached_rate = float(cached_input_per_m) if cached_input_per_m is not None else float(input_per_m)
        cost = (
            ((token_breakdown.get("uncached_input_tokens") or 0) / 1_000_000.0) * float(input_per_m)
            + ((token_breakdown.get("pricing_cached_input_tokens") or 0) / 1_000_000.0) * cached_rate
            + (output_count / 1_000_000.0) * float(output_per_m)
        )
    except (TypeError, ValueError):
        return {
            "api_equivalent_cost_usd": None,
            "estimated_cost": None,
            "pricing_status": "invalid_model_price",
            "pricing_model_path": pricing_model_path,
            "pricing_resolution": resolution,
            "input_token_breakdown": token_breakdown,
            **{key: rate_set.get(key) for key in (
                "pricing_context_class",
                "pricing_context_input_tokens",
                "pricing_context_limit_tokens",
            )},
        }
    model_status = str(model.get("status") or "estimated")
    pricing_status = "estimated_proxy" if model_status.startswith("proxy") else "estimated"
    amount = round(cost, 6)
    return {
        "api_equivalent_cost_usd": amount,
        "estimated_cost": amount,
        "pricing_status": pricing_status,
        "pricing_model_path": pricing_model_path,
        "pricing_resolution": resolution,
        "input_token_breakdown": token_breakdown,
        **{key: rate_set.get(key) for key in (
            "pricing_context_class",
            "pricing_context_input_tokens",
            "pricing_context_limit_tokens",
        )},
    }


def estimate_chatgpt_credits(
    model_path: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None,
    pricing: dict[str, Any],
    input_token_semantics: Any = None,
    token_semantics_status: Any = None,
    speed_mode: Any = None,
    access_mode: Any = None,
    cache_write_tokens: Any = 0,
) -> dict[str, Any]:
    token_breakdown = resolve_input_token_semantics(input_tokens, cached_input_tokens, input_token_semantics)
    if token_semantics_status is not None and str(token_semantics_status) != "valid":
        token_breakdown = {
            **token_breakdown,
            "input_token_semantics_valid": False,
            "uncached_input_tokens": None,
            "pricing_cached_input_tokens": None,
            "reason": "upstream token_semantics_status is not valid",
        }
    if token_breakdown.get("input_token_semantics_valid") is not True:
        semantics_status = "invalid" if token_semantics_status is not None and str(token_semantics_status) != "valid" else str(token_breakdown.get("input_token_semantics") or "unknown")
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": f"{semantics_status}_input_token_semantics",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": None,
            "credit_pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    output_count = as_int(output_tokens)
    if output_count is None or output_count < 0:
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "missing_output_tokens" if output_count is None else "invalid_output_tokens",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": None,
            "credit_pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    cache_write_count = as_int(cache_write_tokens)
    if cache_write_count is None or cache_write_count < 0:
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "invalid_cache_write_tokens",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": None,
            "credit_pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    if cache_write_count > 0:
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "cache_write_pricing_unavailable",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": None,
            "credit_pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    normalized_speed_mode = normalize_speed_mode(speed_mode)
    normalized_access_mode = str(access_mode or "unknown").strip().lower()
    if normalized_access_mode not in {"chatgpt", "apikey", "unknown"}:
        normalized_access_mode = "unknown"
    if normalized_access_mode == "apikey":
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "not_applicable_api_key_access",
            "chatgpt_credit_rate_classification": "not_applicable",
            "chatgpt_credit_access_mode": "apikey",
            "chatgpt_credit_access_assumption": "none_fail_closed",
            "credit_pricing_model_path": None,
            "credit_pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    if normalized_speed_mode == "fast":
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "fast_speed_rate_unavailable",
            "chatgpt_credit_rate_classification": "unknown",
            "chatgpt_credit_speed_mode": "fast",
            "chatgpt_credit_speed_assumption": "none_fail_closed",
            "chatgpt_credit_access_mode": normalized_access_mode,
            "chatgpt_credit_access_assumption": (
                "observed_chatgpt" if normalized_access_mode == "chatgpt"
                else "packet_oauth_mode_assumed"
            ),
            "credit_pricing_model_path": None,
            "credit_pricing_resolution": "not_attempted",
            "input_token_breakdown": token_breakdown,
        }
    if not model_path or not pricing:
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "missing_pricing_table",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": None,
            "input_token_breakdown": token_breakdown,
        }
    pricing_model_path, model, resolution = resolve_pricing_model(model_path, pricing)
    if not model:
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "missing_model_credit_rate",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": pricing_model_path,
            "credit_pricing_resolution": resolution,
            "input_token_breakdown": token_breakdown,
        }
    rates = model.get("chatgpt_credits_per_million")
    rate_status = str(model.get("chatgpt_credit_pricing_status") or "missing_model_credit_rate")
    if not isinstance(rates, dict):
        classification = "separate/no-public-rate" if rate_status == "separate_no_public_rate" else "unknown"
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": rate_status,
            "chatgpt_credit_rate_classification": classification,
            "credit_pricing_model_path": pricing_model_path,
            "credit_pricing_resolution": resolution,
            "input_token_breakdown": token_breakdown,
        }
    try:
        credits = (
            ((token_breakdown.get("uncached_input_tokens") or 0) / 1_000_000.0) * float(rates.get("input"))
            + ((token_breakdown.get("pricing_cached_input_tokens") or 0) / 1_000_000.0) * float(rates.get("cached_input"))
            + (output_count / 1_000_000.0) * float(rates.get("output"))
        )
    except (TypeError, ValueError):
        return {
            "estimated_chatgpt_credits": None,
            "chatgpt_credit_pricing_status": "invalid_model_credit_rate",
            "chatgpt_credit_rate_classification": "unknown",
            "credit_pricing_model_path": pricing_model_path,
            "credit_pricing_resolution": resolution,
            "input_token_breakdown": token_breakdown,
        }
    return {
        "estimated_chatgpt_credits": round(credits, 6),
        "chatgpt_credit_pricing_status": (
            "official_rate" if normalized_speed_mode == "standard"
            else "official_rate_standard_speed_assumed"
        ),
        "chatgpt_credit_rate_classification": "official_chatgpt_credit_rate",
        "chatgpt_credit_speed_mode": normalized_speed_mode,
        "chatgpt_credit_speed_assumption": (
            "observed_standard" if normalized_speed_mode == "standard"
            else "standard_speed_assumed"
        ),
        "chatgpt_credit_access_mode": normalized_access_mode,
        "chatgpt_credit_access_assumption": (
            "observed_chatgpt" if normalized_access_mode == "chatgpt"
            else "packet_oauth_mode_assumed"
        ),
        "credit_pricing_model_path": pricing_model_path,
        "credit_pricing_resolution": resolution,
        "input_token_breakdown": token_breakdown,
    }


def validate_actual_billed_cost_entry(entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not entry:
        return ["OAuth policy actual_billed_cost block missing"]
    allowed_keys = {"amount_usd", "billing_period_label", "source", "recorded_at_utc"}
    unexpected_keys = sorted(str(key) for key in entry if key not in allowed_keys)
    if unexpected_keys:
        errors.append(f"actual_billed_cost contains unsupported provenance fields: {', '.join(unexpected_keys)}")
    amount_raw = entry.get("amount_usd")
    source = entry.get("source")
    period = entry.get("billing_period_label")
    recorded = entry.get("recorded_at_utc")
    if amount_raw is None:
        if source != "not_recorded_do_not_infer":
            errors.append("null actual billed cost must use source=not_recorded_do_not_infer")
        if period is not None or recorded is not None:
            errors.append("null actual billed cost must not carry billing-period or timestamp provenance")
        return errors
    amount = as_float(amount_raw)
    if amount is None or amount < 0:
        errors.append("owner-entered actual billed cost must be a finite nonnegative amount")
    if source != "owner_entered":
        errors.append("non-null actual billed cost requires source=owner_entered")
    if safe_label(period) is None:
        errors.append("non-null actual billed cost requires a privacy-safe billing_period_label")
    if parse_utc(recorded) is None:
        errors.append("non-null actual billed cost requires a valid UTC recorded_at_utc timestamp")
    return errors


def actual_billed_cost_from_policy(policy: dict[str, Any]) -> dict[str, Any]:
    entry = as_dict(policy.get("actual_billed_cost"))
    errors = validate_actual_billed_cost_entry(entry)
    amount = as_float(entry.get("amount_usd"))
    if errors or entry.get("amount_usd") is None:
        return {
            "actual_billed_cost_usd": None,
            "actual_billed_cost_known": False,
            "actual_billed_cost_source": "not_recorded_do_not_infer",
            "billing_period_label": None,
            "recorded_at_utc": None,
            "validation_errors": errors,
        }
    return {
        "actual_billed_cost_usd": amount,
        "actual_billed_cost_known": True,
        "actual_billed_cost_source": "owner_entered",
        "billing_period_label": entry.get("billing_period_label"),
        "recorded_at_utc": entry.get("recorded_at_utc"),
        "validation_errors": [],
    }


def validate_oauth_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not policy:
        return ["OAuth budget policy missing"]
    if policy.get("billing_mode") != "oauth_subscription":
        errors.append("OAuth budget policy billing_mode must be oauth_subscription")
    if policy.get("action_mode") != "advisory_only":
        errors.append("OAuth budget policy action_mode must be advisory_only")
    errors.extend(validate_actual_billed_cost_entry(as_dict(policy.get("actual_billed_cost"))))
    thresholds = as_dict(policy.get("thresholds_percent"))
    reserve = as_float(thresholds.get("reserve"))
    reduce_routine = as_float(thresholds.get("reduce_routine_at_or_below"))
    pause_noncritical = as_float(thresholds.get("pause_noncritical_at_or_below"))
    urgent_only = as_float(thresholds.get("urgent_only_at_or_below"))
    if None in (reserve, reduce_routine, pause_noncritical, urgent_only):
        errors.append("OAuth budget policy thresholds must be finite numbers")
    elif not (100 >= reduce_routine > reserve > pause_noncritical > urgent_only >= 0):
        errors.append("OAuth budget policy threshold ordering must be 100 >= reduce_routine > reserve > pause_noncritical > urgent_only >= 0")
    freshness = as_float(policy.get("snapshot_freshness_max_hours"))
    if freshness is None or not (0 < freshness <= 168):
        errors.append("OAuth budget policy snapshot_freshness_max_hours must be in (0, 168]")
    purchase = as_dict(policy.get("credit_purchase_or_overage"))
    if purchase.get("requires_explicit_owner_approval") is not True:
        errors.append("OAuth credit purchase or overage must require explicit owner approval")
    if purchase.get("automatic_purchase_allowed") is not False:
        errors.append("automatic OAuth credit purchase must remain disabled")
    automatic = as_dict(policy.get("automatic_mutation"))
    for key in ("cron_allowed", "model_route_allowed", "runtime_config_allowed"):
        if automatic.get(key) is not False:
            errors.append(f"OAuth policy automatic mutation must remain false: {key}")
    return errors


def validate_capacity_snapshot(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed_keys = {
        "schema",
        "snapshot_id",
        "recorded_at_utc",
        "checked_at_utc",
        "observation_fingerprint",
        "billing_mode",
        "remaining_percent",
        "reset_hours",
        "source_label",
        "window_label",
        "authoritative",
        "metadata_only",
        "recording_mode",
        "excluded_content",
    }
    unexpected_keys = sorted(str(key) for key in snapshot if key not in allowed_keys)
    if unexpected_keys:
        errors.append(f"capacity snapshot contains non-metadata fields: {', '.join(unexpected_keys)}")
    if snapshot.get("schema") != OAUTH_CAPACITY_SCHEMA:
        errors.append("capacity snapshot schema mismatch")
    if safe_label(snapshot.get("snapshot_id")) is None:
        errors.append("capacity snapshot_id must be a privacy-safe identifier")
    if snapshot.get("billing_mode") != "oauth_subscription":
        errors.append("capacity snapshot billing_mode must be oauth_subscription")
    remaining = as_float(snapshot.get("remaining_percent"))
    if remaining is None or not (0 <= remaining <= 100):
        errors.append("remaining_percent must be in [0, 100]")
    reset_hours = as_float(snapshot.get("reset_hours"))
    if reset_hours is None or not (0 <= reset_hours <= 8760):
        errors.append("reset_hours must be in [0, 8760]")
    if safe_label(snapshot.get("source_label")) is None:
        errors.append("source_label must be a privacy-safe label of at most 64 characters")
    if safe_label(snapshot.get("window_label")) is None:
        errors.append("window_label must be a privacy-safe label of at most 64 characters")
    if parse_utc(snapshot.get("recorded_at_utc")) is None:
        errors.append("recorded_at_utc must be an aware ISO-8601 UTC timestamp")
    checked_at = snapshot.get("checked_at_utc")
    if checked_at is not None and parse_utc(checked_at) is None:
        errors.append("checked_at_utc must be an aware ISO-8601 UTC timestamp when present")
    observation_fingerprint = snapshot.get("observation_fingerprint")
    if observation_fingerprint is not None and safe_label(observation_fingerprint) is None:
        errors.append("observation_fingerprint must be a privacy-safe identifier when present")
    if snapshot.get("authoritative") is not True:
        errors.append("capacity snapshot must be explicitly authoritative")
    if snapshot.get("metadata_only") is not True:
        errors.append("capacity snapshot must remain metadata-only")
    if snapshot.get("recording_mode") != "explicit_write_only":
        errors.append("capacity snapshot must use explicit_write_only recording mode")
    errors.extend(scan_forbidden(snapshot))
    return errors


def record_capacity_snapshot(
    remaining_percent: Any,
    reset_hours: Any,
    source_label: Any,
    window_label: Any,
    current_path: Path = OAUTH_CAPACITY_CURRENT,
    history_path: Path = OAUTH_CAPACITY_HISTORY,
    recorded_at_utc: str | None = None,
) -> tuple[dict[str, Any], bool]:
    remaining = as_float(remaining_percent)
    reset = as_float(reset_hours)
    source = safe_label(source_label)
    window = safe_label(window_label)
    input_errors: list[str] = []
    if remaining is None or not (0 <= remaining <= 100):
        input_errors.append("remaining_percent must be in [0, 100]")
    if reset is None or not (0 <= reset <= 8760):
        input_errors.append("reset_hours must be in [0, 8760]")
    if source is None:
        input_errors.append("source_label must match [A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
    if window is None:
        input_errors.append("window_label must match [A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
    if input_errors:
        raise ValueError("; ".join(input_errors))

    normalized_remaining = round(remaining, 6)
    normalized_reset = round(reset, 6)
    observation_fingerprint = stable_id(
        "openai_oauth_capacity_observation",
        f"{normalized_remaining:.6f}",
        f"{normalized_reset:.6f}",
        source,
        window,
    )
    checked_at = recorded_at_utc or utc_now()
    if parse_utc(checked_at) is None:
        raise ValueError("recorded_at_utc must be an aware ISO-8601 UTC timestamp")

    existing = as_dict(load_json_artifact(current_path))
    same_observation = (
        not validate_capacity_snapshot(existing)
        and as_float(existing.get("remaining_percent")) == normalized_remaining
        and as_float(existing.get("reset_hours")) == normalized_reset
        and existing.get("source_label") == source
        and existing.get("window_label") == window
    )
    if same_observation:
        refreshed = {
            **existing,
            "checked_at_utc": checked_at,
            "observation_fingerprint": observation_fingerprint,
        }
        snapshot_errors = validate_capacity_snapshot(refreshed)
        if snapshot_errors:
            raise ValueError("; ".join(snapshot_errors))
        atomic_write_json(current_path, refreshed)
        snapshot_id = existing.get("snapshot_id")
        history_ids = {row.get("snapshot_id") for row in read_jsonl(history_path)}
        if snapshot_id and snapshot_id not in history_ids:
            history_row = {**refreshed, "schema": OAUTH_CAPACITY_EVENT_SCHEMA, "event_kind": "capacity_snapshot_recorded"}
            append_jsonl(history_path, [history_row])
            return refreshed, True
        return refreshed, False

    recorded = checked_at
    snapshot_id = stable_id("openai_oauth_capacity", recorded, remaining, reset, source, window)
    snapshot = {
        "schema": OAUTH_CAPACITY_SCHEMA,
        "snapshot_id": snapshot_id,
        "recorded_at_utc": recorded,
        "checked_at_utc": checked_at,
        "observation_fingerprint": observation_fingerprint,
        "billing_mode": "oauth_subscription",
        "remaining_percent": normalized_remaining,
        "reset_hours": normalized_reset,
        "source_label": source,
        "window_label": window,
        "authoritative": True,
        "metadata_only": True,
        "recording_mode": "explicit_write_only",
        "excluded_content": [
            "account identity",
            "credentials",
            "raw status text",
            "prompts",
            "responses",
            "tool payloads",
        ],
    }
    snapshot_errors = validate_capacity_snapshot(snapshot)
    if snapshot_errors:
        raise ValueError("; ".join(snapshot_errors))
    atomic_write_json(current_path, snapshot)
    history_ids = {row.get("snapshot_id") for row in read_jsonl(history_path)}
    appended = snapshot_id not in history_ids
    if appended:
        history_row = {**snapshot, "schema": OAUTH_CAPACITY_EVENT_SCHEMA, "event_kind": "capacity_snapshot_recorded"}
        append_jsonl(history_path, [history_row])
    return snapshot, appended


def compute_oauth_capacity_control(
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    policy_errors = validate_oauth_policy(policy)
    control: dict[str, Any] = {
        "state": "unavailable",
        "status": "unavailable",
        "quota_tier": "unavailable",
        "tier": "unavailable",
        "capacity_known": False,
        "advisory_only": True,
        "automatic_action_allowed": False,
        "throttling_authorized": False,
        "advisory_action": "no_quota_action_from_unknown_data",
        "policy": policy,
        "policy_validation": {"status": "critical" if policy_errors else "ok", "errors": policy_errors},
        "snapshot_status": "missing" if not snapshot else "unchecked",
        "snapshot": snapshot or None,
        "snapshot_checked_at_utc": None,
        "snapshot_validation": {"status": "warning" if not snapshot else "unchecked", "errors": []},
        "days_to_reset": None,
        "days_until_reset": None,
        "reset_days": None,
        "reserve_percent": None,
        "max_daily_percentage_point_burn_preserving_reserve": None,
        "daily_burn_guidance": None,
    }
    if not policy_errors:
        control["reserve_percent"] = float(as_dict(policy.get("thresholds_percent"))["reserve"])
    if policy_errors or not snapshot:
        return control

    snapshot_errors = validate_capacity_snapshot(snapshot)
    control["snapshot_validation"] = {"status": "critical" if snapshot_errors else "ok", "errors": snapshot_errors}
    if snapshot_errors:
        control["snapshot_status"] = "invalid"
        return control

    recorded = parse_utc(snapshot.get("recorded_at_utc"))
    assert recorded is not None
    checked = parse_utc(snapshot.get("checked_at_utc")) or recorded
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = (current - checked).total_seconds() / 3600.0
    reset_at_recording = float(snapshot["reset_hours"])
    reset_hours_remaining = max(reset_at_recording - max(age_hours, 0.0), 0.0)
    days_to_reset = reset_hours_remaining / 24.0
    control.update({
        "remaining_percent": float(snapshot["remaining_percent"]),
        "snapshot_checked_at_utc": checked.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "recorded_reset_hours": reset_at_recording,
        "estimated_reset_hours_remaining": round(reset_hours_remaining, 6),
        "days_to_reset": round(days_to_reset, 6),
        "days_until_reset": round(days_to_reset, 6),
        "reset_days": round(days_to_reset, 6),
        "snapshot_age_hours": round(age_hours, 6),
    })
    freshness_max = float(policy["snapshot_freshness_max_hours"])
    reset_window_elapsed = age_hours > 0 and reset_hours_remaining <= 0
    if age_hours < 0 or age_hours > freshness_max or reset_window_elapsed:
        control.update({
            "state": "stale",
            "status": "stale",
            "quota_tier": "stale",
            "tier": "stale",
            "snapshot_status": "stale",
            "stale_reason": (
                "snapshot_timestamp_is_in_the_future" if age_hours < 0
                else "recorded_reset_window_elapsed" if reset_window_elapsed
                else "snapshot_exceeds_freshness_limit"
            ),
        })
        return control

    thresholds = as_dict(policy.get("thresholds_percent"))
    remaining = float(snapshot["remaining_percent"])
    if remaining <= float(thresholds["urgent_only_at_or_below"]):
        tier = "urgent_only"
        advisory_action = "use_quota_for_urgent_work_only"
    elif remaining <= float(thresholds["pause_noncritical_at_or_below"]):
        tier = "pause_noncritical"
        advisory_action = "pause_noncritical_usage"
    elif remaining <= float(thresholds["reduce_routine_at_or_below"]):
        tier = "reduce_routine"
        advisory_action = "reduce_routine_usage"
    else:
        tier = "normal"
        advisory_action = "continue_with_reserve_guard"
    reserve = float(thresholds["reserve"])
    burn = max((remaining - reserve) / days_to_reset, 0.0) if days_to_reset > 0 else 0.0
    control.update({
        "state": tier,
        "status": "current",
        "quota_tier": tier,
        "tier": tier,
        "capacity_known": True,
        "snapshot_status": "fresh",
        "advisory_action": advisory_action,
        "max_daily_percentage_point_burn_preserving_reserve": round(burn, 6),
        "daily_burn_guidance": round(burn, 6),
    })
    return control


def build_oauth_capacity_high_burn_preflight(
    control: dict[str, Any],
    policy: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return advisory-only capacity guidance for an already-selected high-burn job.

    This is intentionally a display/control aid, not a dispatcher.  It never
    enables a model route, changes a cron, or turns stale capacity into a hard
    execution block.
    """
    _ = now  # The supplied control owns its observed timestamp and age.
    resolved_policy = policy or as_dict(control.get("policy"))
    event_refresh = as_dict(resolved_policy.get("event_refresh"))
    max_age = as_float(event_refresh.get("high_burn_preflight_max_snapshot_age_hours"))
    if max_age is None or not (0 < max_age <= 168):
        max_age = 6.0
    snapshot_status = str(control.get("snapshot_status") or "missing").strip().lower()
    quota_status = str(control.get("status") or "unavailable").strip().lower()
    quota_tier = str(control.get("tier") or control.get("quota_tier") or "unavailable").strip().lower()
    snapshot_age = as_float(control.get("snapshot_age_hours"))
    capacity_known = control.get("capacity_known") is True
    stale_or_unknown = (
        snapshot_status not in {"fresh"}
        or quota_status != "current"
        or quota_tier in {"", "stale", "unavailable", "unknown", "invalid", "missing"}
        or snapshot_age is None
        or snapshot_age > max_age
        or not capacity_known
    )
    if stale_or_unknown:
        status = "refresh_required"
        next_action = "Capture a current authoritative, sanitized capacity observation before high-burn work; no automatic throttling or dispatch change is authorized."
    elif quota_tier == "normal":
        status = "advisory_current"
        next_action = "Capacity proof is current for advisory review; preserve the configured reserve and keep dispatch owner-controlled."
    else:
        status = "review_required"
        next_action = "Capacity is current but below the normal tier; review priority and reserve before high-burn work, with no automatic dispatch change."
    snapshot = as_dict(control.get("snapshot"))
    return {
        "required": True,
        "status": status,
        "advisory_only": True,
        "quota_status": quota_status or "unavailable",
        "quota_tier": quota_tier or "unavailable",
        "snapshot_status": snapshot_status or "missing",
        "checked_at_utc": control.get("snapshot_checked_at_utc") or snapshot.get("checked_at_utc") or snapshot.get("recorded_at_utc"),
        "snapshot_age_hours": snapshot_age,
        "max_snapshot_age_hours": round(max_age, 6),
        "remaining_percent": as_float(control.get("remaining_percent")),
        "reserve_percent": as_float(control.get("reserve_percent")),
        "automatic_action_allowed": False,
        "automatic_dispatch_allowed": False,
        "next_action": next_action,
    }


def usage_receipt_store_path() -> Path:
    return LANE_REGISTER.with_suffix(".usage-receipts.json")


def load_usage_source_receipts() -> list[dict[str, Any]]:
    payload = as_dict(load_json_artifact(usage_receipt_store_path()))
    if payload.get("schema") != USAGE_SOURCE_RECEIPTS_SCHEMA:
        return []
    return [row for row in as_list(payload.get("receipts")) if isinstance(row, dict)]


def strict_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def receipt_matches_lane(lane: dict[str, Any] | None, receipts: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Require shared source re-verification before assigning lane credit."""
    if not lane:
        return False, "deterministic_lane_join_required"
    runtime = as_dict(lane.get("runtime"))
    if lane.get("status") != "complete":
        return False, "lane_not_complete"
    if runtime.get("usage_creditable") is not True or runtime.get("usage_credit_status") != "creditable":
        return False, "lane_usage_not_creditable"
    del receipts  # Shared verifier reopens the manager-owned sidecar and source.
    reasons = verify_usage_source_receipt(
        lane,
        runtime,
        usage_receipt_store_path(),
        isolated_agent_state_root=ISOLATED_AGENT_STATE_ROOT,
    )
    return (not reasons, reasons[0] if reasons else None)


def configured_isolated_session_candidate_root() -> Path:
    """Return the physical root eligible to provide ledger credit candidates.

    Session-index observation roots are configurable for parsing/tests, but a
    redirected HOME/USERPROFILE path must not feed an implementation-credit
    event. The manager owns the common physical runtime trust anchor.
    """
    return configured_isolated_agent_state_root()


def lane_index(register: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lane in as_list(register.get("lanes")):
        if not isinstance(lane, dict):
            continue
        runtime = as_dict(lane.get("runtime"))
        run_id = runtime.get("run_id") or lane.get("run_id")
        if run_id:
            candidates[str(run_id)].append(lane)
    ambiguous = {run_id for run_id, rows in candidates.items() if len(rows) != 1}
    return ({run_id: rows[0] for run_id, rows in candidates.items() if len(rows) == 1}, ambiguous)


def is_lane_runtime_event(event: Any) -> bool:
    """Recognize exact lane-runtime provenance without producer-only matching."""
    return (
        isinstance(event, dict)
        and event.get("schema") == EVENT_SCHEMA
        and event.get("producer") == LANE_RUNTIME_EVENT_PRODUCER
        and event.get("run_kind") == LANE_RUNTIME_EVENT_RUN_KIND
    )


def creditable_candidate_run_ids(
    model_candidate_events: list[dict[str, Any]],
    isolated_candidate_events: list[dict[str, Any]],
) -> set[str]:
    """Return only independently creditable non-lane candidate identities.

    Uncreditable observations remain audit evidence, but cannot suppress a
    receipt-bound lane-runtime event.  The caller deliberately passes only
    model and isolated-session candidates, never lane candidates themselves.
    """
    return {
        str(event.get("source_run_id"))
        for event in model_candidate_events + isolated_candidate_events
        if event.get("source_run_id") and event.get("usage_creditable") is True
    }


def provider_observation_run_ids(
    model_candidate_events: list[dict[str, Any]],
    isolated_candidate_events: list[dict[str, Any]],
) -> set[str]:
    """Return all non-lane candidate identities retained for audit."""
    return {
        str(event.get("source_run_id"))
        for event in model_candidate_events + isolated_candidate_events
        if event.get("source_run_id")
    }


def reconcile_derived_creditable_events(
    all_events: list[dict[str, Any]],
    current_candidate_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Hide stale creditable counterparts when current evidence exists.

    JSONL remains append-only.  This only reconciles the in-memory view when
    a current build has independently creditable evidence for a run.  The
    current event IDs supersede stale creditable counterparts from either
    source family.  Multiple current creditable IDs remain visible: resolving
    their relationship requires a separate binding rule and must not be
    changed by this future-only lane reconciliation repair.
    """
    current_ids_by_run: dict[str, set[str]] = defaultdict(set)
    for event in current_candidate_events:
        if event.get("usage_creditable") is not True:
            continue
        run_id = str(event.get("source_run_id") or "")
        event_id = str(event.get("event_id") or "")
        if run_id and event_id:
            current_ids_by_run[run_id].add(event_id)
    reconciled: list[dict[str, Any]] = []
    for row in all_events:
        if row.get("usage_creditable") is not True:
            reconciled.append(row)
            continue
        run_id = str(row.get("source_run_id") or "")
        current_ids = current_ids_by_run.get(run_id)
        if current_ids and str(row.get("event_id") or "") not in current_ids:
            continue
        reconciled.append(row)
    return reconciled


def coding_history_index(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        run_id = row.get("run_id")
        if run_id:
            candidates[str(run_id)].append(row)
    ambiguous = {run_id for run_id, values in candidates.items() if len(values) != 1}
    return ({run_id: values[0] for run_id, values in candidates.items() if len(values) == 1}, ambiguous)


def token_event(
    row: dict[str, Any],
    pricing: dict[str, Any],
    lanes_by_run: dict[str, dict[str, Any]],
    coding_by_run: dict[str, dict[str, Any]],
    ambiguous_run_ids: set[str] | None = None,
    usage_receipts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    total_tokens = as_int(row.get("tokens"))
    if total_tokens is None or total_tokens < 0:
        return None
    run_id = str(row.get("run_id") or stable_id(row.get("producer"), row.get("cron_job_name"), row.get("source_generated_at_utc")))
    input_tokens = as_int(row.get("input_tokens"))
    output_tokens = as_int(row.get("output_tokens"))
    cached_input_tokens = first_int(row.get("cached_input_tokens"), row.get("cache_read_tokens"))
    cache_write_tokens = first_int(row.get("cache_write_tokens"), row.get("cache_write"), 0)
    declared_input_semantics = row.get("input_token_semantics")
    upstream_semantics_status = row.get("token_semantics_status")
    normalized_breakdown = resolve_input_token_semantics(input_tokens, cached_input_tokens, declared_input_semantics)
    reconciliation = reconcile_token_total(total_tokens, output_tokens, normalized_breakdown, cache_write_tokens)
    effective_semantics_status = (
        str(upstream_semantics_status)
        if upstream_semantics_status is not None and str(upstream_semantics_status) != "valid"
        else str(reconciliation.get("token_semantics_status") or "invalid")
    )
    access_mode, access_mode_source = normalize_access_mode(row.get("access_mode"), row.get("access_mode_source"))
    speed_mode = normalize_speed_mode(row.get("speed_mode"))
    model_path = row.get("model_path")
    support = model_support(model_path)
    cost = estimate_cost(model_path, input_tokens, output_tokens, pricing, cached_input_tokens, declared_input_semantics, effective_semantics_status, cache_write_tokens)
    credits = estimate_chatgpt_credits(model_path, input_tokens, output_tokens, cached_input_tokens, pricing, declared_input_semantics, effective_semantics_status, speed_mode, access_mode, cache_write_tokens)
    token_breakdown = as_dict(cost.get("input_token_breakdown"))
    ambiguous = run_id in (ambiguous_run_ids or set())
    lane = None if ambiguous else lanes_by_run.get(run_id)
    coding = None if ambiguous else coding_by_run.get(run_id)
    lane_runtime = as_dict((lane or {}).get("runtime"))
    receipt_valid, receipt_reason = receipt_matches_lane(lane, usage_receipts or [])
    if receipt_valid and lane is not None:
        lane_runtime_for_receipt = as_dict(lane.get("runtime"))
        if model_path != lane_runtime_for_receipt.get("model_path"):
            receipt_valid, receipt_reason = False, "provider_row_model_mismatch"
        elif total_tokens != as_int(lane_runtime_for_receipt.get("total_tokens")):
            receipt_valid, receipt_reason = False, "provider_row_total_tokens_mismatch"
        elif input_tokens is not None and input_tokens != as_int(lane_runtime_for_receipt.get("input_tokens")):
            receipt_valid, receipt_reason = False, "provider_row_input_tokens_mismatch"
        elif output_tokens is not None and output_tokens != as_int(lane_runtime_for_receipt.get("output_tokens")):
            receipt_valid, receipt_reason = False, "provider_row_output_tokens_mismatch"
    deterministic_join = not ambiguous and lane is not None and receipt_valid
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": stable_id("token_usage", run_id, row.get("producer"), row.get("source_generated_at_utc")),
        "recorded_at_utc": utc_now(),
        "usage_at_utc": row.get("usage_at_utc"),
        "usage_time_source": row.get("usage_time_source"),
        "source_artifact": rel(MODEL_RUN_LEDGER),
        "source_run_id": run_id,
        "producer": row.get("producer"),
        "run_kind": row.get("run_kind"),
        "workflow_id": row.get("workflow_id") or (lane or {}).get("workflow_id") or (coding or {}).get("workflow_id"),
        "cron_job_name": row.get("cron_job_name"),
        "lane_id": (lane or {}).get("lane_id") or (coding or {}).get("lane_id"),
        "workstream_id": (lane or {}).get("workstream_id") or (coding or {}).get("workstream_id"),
        "task_name": (coding or {}).get("task_name") or as_dict((lane or {}).get("runtime")).get("task_name"),
        "model_path": model_path,
        "model_provider": row.get("model_provider"),
        "access_mode": access_mode,
        "access_mode_source": access_mode_source,
        "speed_mode": speed_mode,
        "model_support": support,
        "supported_model_capacity": support.get("active_route_countable") is True,
        "status": row.get("status"),
        "duration_ms": row.get("duration_ms"),
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_write_tokens": cache_write_tokens,
        "uncached_input_tokens": token_breakdown.get("uncached_input_tokens"),
        "input_token_semantics": token_breakdown.get("input_token_semantics"),
        "input_token_semantics_source": token_breakdown.get("input_token_semantics_source"),
        "input_token_semantics_valid": token_breakdown.get("input_token_semantics_valid"),
        "input_token_semantics_reason": token_breakdown.get("reason"),
        "token_semantics_status": effective_semantics_status,
        "token_semantics_reasons": [
            *[str(reason) for reason in as_list(row.get("token_semantics_reasons"))],
            *[str(reason) for reason in as_list(reconciliation.get("token_semantics_reasons"))],
        ],
        "token_total_expected": reconciliation.get("token_total_expected"),
        "token_total_delta": reconciliation.get("token_total_delta"),
        "token_total_tolerance_tokens": reconciliation.get("token_total_tolerance_tokens"),
        "output_tokens": output_tokens,
        "api_equivalent_cost_usd": cost["api_equivalent_cost_usd"],
        "estimated_cost": cost["estimated_cost"],
        "estimated_cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd",
        "actual_billed_cost_usd": None,
        "actual_billed_cost_source": "not_recorded_do_not_infer",
        "estimated_chatgpt_credits": credits["estimated_chatgpt_credits"],
        "chatgpt_credit_pricing_status": credits["chatgpt_credit_pricing_status"],
        "chatgpt_credit_rate_classification": credits["chatgpt_credit_rate_classification"],
        "chatgpt_credit_speed_mode": credits.get("chatgpt_credit_speed_mode"),
        "chatgpt_credit_speed_assumption": credits.get("chatgpt_credit_speed_assumption"),
        "chatgpt_credit_access_mode": credits.get("chatgpt_credit_access_mode"),
        "chatgpt_credit_access_assumption": credits.get("chatgpt_credit_access_assumption"),
        "credit_pricing_model_path": credits.get("credit_pricing_model_path"),
        "credit_pricing_resolution": credits.get("credit_pricing_resolution"),
        "pricing_status": cost["pricing_status"],
        "api_equivalent_pricing_status": cost["pricing_status"],
        "pricing_model_path": cost.get("pricing_model_path"),
        "pricing_resolution": cost.get("pricing_resolution"),
        "pricing_context_class": cost.get("pricing_context_class"),
        "pricing_context_input_tokens": cost.get("pricing_context_input_tokens"),
        "pricing_context_limit_tokens": cost.get("pricing_context_limit_tokens"),
        "implementation_attributed": deterministic_join and effective_semantics_status == "valid",
        "observed_implementation_candidate": bool(lane or coding),
        "usage_creditable": deterministic_join and effective_semantics_status == "valid",
        "usage_credit_block_reason": (
            "ambiguous_run_id" if ambiguous else (
                None if deterministic_join and effective_semantics_status == "valid" else (receipt_reason or "deterministic_lane_receipt_join_required")
            )
        ),
        "parent_job_id": lane_runtime.get("parent_job_id") or (coding or {}).get("parent_job_id"),
        "phase": normalized_outcome_state(lane_runtime.get("phase")) or None,
        "attempt_number": lane_attempt_metadata(lane).get("attempt_number") if lane else None,
        "retry_count": lane_attempt_metadata(lane).get("retry_count") if lane else None,
        "main_acceptance_status": normalized_outcome_state(lane_runtime.get("main_acceptance_status")) or None,
        "outcome_event_kind": normalized_outcome_state(lane_runtime.get("outcome_event_kind")) or None,
        "cron_attributed": bool(row.get("cron_job_name")),
        "tokens_per_second": round(total_tokens / (float(row.get("duration_ms") or 0) / 1000.0), 3) if row.get("duration_ms") else None,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    return event


def lane_token_event(
    lane: dict[str, Any],
    pricing: dict[str, Any],
    provider_observation_run_ids: set[str],
    usage_receipts: list[dict[str, Any]] | None = None,
    creditable_provider_run_ids: set[str] | None = None,
    ambiguous_lane_run_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    if lane.get("status") != "complete":
        return None
    runtime = as_dict(lane.get("runtime"))
    input_tokens = as_int(runtime.get("input_tokens"))
    output_tokens = as_int(runtime.get("output_tokens"))
    cached_input_tokens = as_int(runtime.get("cached_input_tokens"))
    cache_write_tokens = first_int(runtime.get("cache_write_tokens"), 0)
    declared_input_semantics = runtime.get("input_token_semantics")
    upstream_semantics_status = runtime.get("token_semantics_status")
    runtime_breakdown = resolve_input_token_semantics(input_tokens, cached_input_tokens, declared_input_semantics)
    raw_total_tokens = as_int(runtime.get("total_tokens"))
    if raw_total_tokens is not None and raw_total_tokens < 0:
        return None
    reconciliation = reconcile_token_total(raw_total_tokens, output_tokens, runtime_breakdown, cache_write_tokens)
    total_tokens = as_int(reconciliation.get("total_tokens"))
    if total_tokens is None:
        return None
    effective_semantics_status = (
        str(upstream_semantics_status)
        if upstream_semantics_status is not None and str(upstream_semantics_status) != "valid"
        else str(reconciliation.get("token_semantics_status") or "invalid")
    )
    access_mode, access_mode_source = normalize_access_mode(runtime.get("access_mode"), runtime.get("access_mode_source"))
    speed_mode = normalize_speed_mode(runtime.get("speed_mode"))
    run_id = str(runtime.get("run_id") or lane.get("run_id") or stable_id("lane", lane.get("lane_id"), lane.get("started_at_utc"), lane.get("completed_at_utc")))
    if run_id in (ambiguous_lane_run_ids or set()):
        return None
    model_path = runtime.get("model_path") or lane.get("model_path")
    support = model_support(model_path)
    cost = estimate_cost(model_path, input_tokens, output_tokens, pricing, cached_input_tokens, declared_input_semantics, effective_semantics_status, cache_write_tokens)
    credits = estimate_chatgpt_credits(model_path, input_tokens, output_tokens, cached_input_tokens, pricing, declared_input_semantics, effective_semantics_status, speed_mode, access_mode, cache_write_tokens)
    token_breakdown = as_dict(cost.get("input_token_breakdown"))
    duration_ms = None
    started = lane.get("started_at_utc")
    completed = lane.get("completed_at_utc") or lane.get("ended_at_utc")
    usage_at_utc = runtime.get("usage_at_utc")
    usage_time_source = runtime.get("usage_time_source")
    if parse_utc(usage_at_utc) is None and parse_utc(completed) is not None:
        usage_at_utc = completed
        usage_time_source = "lane_completed_at"
    source = str(runtime.get("token_attribution_source") or "lane_runtime_metadata")
    correlation = as_dict(runtime.get("attempt_correlation"))
    receipt_valid, receipt_reason = receipt_matches_lane(lane, usage_receipts or [])
    usage_creditable = (
        source in TRUSTED_LANE_TOKEN_SOURCES
        and runtime.get("usage_credit_status") == "creditable"
        and runtime.get("usage_creditable") is True
        and bool(runtime.get("run_id"))
        and bool(runtime.get("session_ref_hash"))
        and bool(correlation.get("key_hash"))
        and effective_semantics_status == "valid"
        and receipt_valid
    )
    if run_id in (creditable_provider_run_ids or set()):
        return None
    # Preserve the existing single-observation behavior when neither source is
    # independently creditable.  A valid, receipt-bound lane is the only case
    # that may coexist with an uncreditable provider observation for this run.
    if run_id in provider_observation_run_ids and not usage_creditable:
        return None
    attempts = lane_attempt_metadata(lane)
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": stable_id("token_usage", run_id, lane.get("lane_id"), "lane_runtime_tokens"),
        "recorded_at_utc": utc_now(),
        "usage_at_utc": usage_at_utc,
        "usage_time_source": usage_time_source,
        "source_artifact": rel(LANE_REGISTER),
        "source_run_id": run_id,
        "producer": LANE_RUNTIME_EVENT_PRODUCER,
        "run_kind": LANE_RUNTIME_EVENT_RUN_KIND,
        "workflow_id": lane.get("workflow_id"),
        "cron_job_name": None,
        "lane_id": lane.get("lane_id"),
        "workstream_id": lane.get("workstream_id"),
        "task_name": runtime.get("task_name") or lane.get("workstream_id"),
        "model_path": model_path,
        "model_provider": runtime.get("model_provider"),
        "access_mode": access_mode,
        "access_mode_source": access_mode_source,
        "speed_mode": speed_mode,
        "model_support": support,
        "supported_model_capacity": support.get("active_route_countable") is True,
        "status": lane.get("status"),
        "duration_ms": duration_ms,
        "started_at_utc": started,
        "completed_at_utc": completed,
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_write_tokens": cache_write_tokens,
        "uncached_input_tokens": token_breakdown.get("uncached_input_tokens"),
        "input_token_semantics": token_breakdown.get("input_token_semantics"),
        "input_token_semantics_source": token_breakdown.get("input_token_semantics_source"),
        "input_token_semantics_valid": token_breakdown.get("input_token_semantics_valid"),
        "input_token_semantics_reason": token_breakdown.get("reason"),
        "token_semantics_status": effective_semantics_status,
        "token_semantics_reasons": [
            *[str(reason) for reason in as_list(runtime.get("token_semantics_reasons"))],
            *[str(reason) for reason in as_list(reconciliation.get("token_semantics_reasons"))],
        ],
        "token_total_expected": reconciliation.get("token_total_expected"),
        "token_total_delta": reconciliation.get("token_total_delta"),
        "token_total_tolerance_tokens": reconciliation.get("token_total_tolerance_tokens"),
        "output_tokens": output_tokens,
        "api_equivalent_cost_usd": cost["api_equivalent_cost_usd"],
        "estimated_cost": cost["estimated_cost"],
        "estimated_cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd",
        "actual_billed_cost_usd": None,
        "actual_billed_cost_source": "not_recorded_do_not_infer",
        "estimated_chatgpt_credits": credits["estimated_chatgpt_credits"],
        "chatgpt_credit_pricing_status": credits["chatgpt_credit_pricing_status"],
        "chatgpt_credit_rate_classification": credits["chatgpt_credit_rate_classification"],
        "chatgpt_credit_speed_mode": credits.get("chatgpt_credit_speed_mode"),
        "chatgpt_credit_speed_assumption": credits.get("chatgpt_credit_speed_assumption"),
        "chatgpt_credit_access_mode": credits.get("chatgpt_credit_access_mode"),
        "chatgpt_credit_access_assumption": credits.get("chatgpt_credit_access_assumption"),
        "credit_pricing_model_path": credits.get("credit_pricing_model_path"),
        "credit_pricing_resolution": credits.get("credit_pricing_resolution"),
        "pricing_status": cost["pricing_status"],
        "api_equivalent_pricing_status": cost["pricing_status"],
        "pricing_model_path": cost.get("pricing_model_path"),
        "pricing_resolution": cost.get("pricing_resolution"),
        "pricing_context_class": cost.get("pricing_context_class"),
        "pricing_context_input_tokens": cost.get("pricing_context_input_tokens"),
        "pricing_context_limit_tokens": cost.get("pricing_context_limit_tokens"),
        "implementation_attributed": usage_creditable,
        "observed_implementation_candidate": True,
        "usage_creditable": usage_creditable,
        "usage_credit_block_reason": (
            None if usage_creditable else (receipt_reason or "trusted_source_and_deterministic_attempt_join_required")
        ),
        "parent_job_id": runtime.get("parent_job_id"),
        "phase": normalized_outcome_state(runtime.get("phase")) or None,
        "attempt_number": attempts.get("attempt_number"),
        "retry_count": attempts.get("retry_count"),
        "main_acceptance_status": normalized_outcome_state(runtime.get("main_acceptance_status")) or None,
        "outcome_event_kind": normalized_outcome_state(runtime.get("outcome_event_kind")) or None,
        "cron_attributed": False,
        "token_attribution_source": source,
        "tokens_per_second": None,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    return event


def lane_agent_id(lane: dict[str, Any]) -> str | None:
    runtime = as_dict(lane.get("runtime"))
    explicit = runtime.get("agent_id")
    if explicit in CONFIGURED_ISOLATED_AGENT_IDS:
        return str(explicit)
    session_key = runtime.get("session_key")
    if isinstance(session_key, str) and session_key.startswith("agent:"):
        parts = session_key.split(":", 2)
        if len(parts) >= 2 and parts[1] in CONFIGURED_ISOLATED_AGENT_IDS:
            return parts[1]
    return None


def normalized_outcome_state(value: Any) -> str:
    """Normalize explicit closeout vocabulary without inferring a disposition."""
    return re.sub(r"[\s-]+", "_", str(value or "").strip().lower()).strip("_")


def strict_attempt_int(value: Any, *, minimum: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= minimum:
        return value
    return None


def lane_attempt_metadata(lane: dict[str, Any]) -> dict[str, Any]:
    runtime = candidate_runtime(lane)
    retry_count = strict_attempt_int(runtime.get("retry_count"), minimum=0)
    attempt_number = strict_attempt_int(runtime.get("attempt_number"), minimum=1)
    if retry_count is not None and attempt_number is None:
        attempt_number = retry_count + 1
    if attempt_number is not None and retry_count is None:
        retry_count = attempt_number - 1
    if attempt_number is not None and retry_count is not None and attempt_number != retry_count + 1:
        retry_count = None
        attempt_number = None
    return {
        "retry_count": retry_count,
        "attempt_number": attempt_number,
        "is_first_attempt": attempt_number == 1 if attempt_number is not None else None,
        "is_retry": retry_count > 0 if retry_count is not None else None,
    }


def safe_metadata_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if text and len(text) <= 128 and re.fullmatch(r"[A-Za-z0-9_.:-]+", text):
        return text
    return None


def candidate_runtime(candidate: dict[str, Any]) -> dict[str, Any]:
    return as_dict(candidate.get("runtime")) or candidate


def candidate_agent_id(candidate: dict[str, Any]) -> str | None:
    direct = lane_agent_id(candidate)
    if direct:
        return direct
    runtime = candidate_runtime(candidate)
    explicit = runtime.get("agent_id") or candidate.get("agent_id") or candidate.get("owner")
    return str(explicit) if explicit in CONFIGURED_ISOLATED_AGENT_IDS else None


def candidate_identity(candidate: dict[str, Any]) -> tuple[str, str, str]:
    runtime = candidate_runtime(candidate)
    correlation = as_dict(runtime.get("attempt_correlation") or candidate.get("attempt_correlation"))
    return (
        str(candidate.get("lane_id") or ""),
        str(runtime.get("run_id") or candidate.get("run_id") or ""),
        str(correlation.get("key_hash") or ""),
    )


def candidate_consistency(candidate: dict[str, Any], record: dict[str, Any]) -> str | None:
    runtime = candidate_runtime(candidate)
    agent_id = candidate_agent_id(candidate)
    if agent_id and agent_id != record.get("agent_id"):
        return "agent_mismatch"
    model_path = runtime.get("model_path") or candidate.get("model_path")
    if model_path and model_path != record.get("model_path"):
        return "model_mismatch"
    lane_started = parse_utc(candidate.get("started_at_utc"))
    lane_ended = parse_utc(candidate.get("completed_at_utc") or candidate.get("ended_at_utc"))
    usage_started = parse_utc(record.get("started_at_utc"))
    usage_ended = parse_utc(record.get("usage_at_utc"))
    if lane_started and lane_ended and usage_started and usage_ended:
        if usage_ended < lane_started or usage_started > lane_ended:
            return "time_mismatch"
    return None


def match_isolated_usage_lane(
    record: dict[str, Any],
    register: dict[str, Any],
    coding_history: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    current = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    history = [row for row in (coding_history or []) if isinstance(row, dict)]
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for candidate in current + history:
        key = candidate_identity(candidate)
        prior = deduped.get(key)
        if prior is None or candidate in current:
            deduped[key] = candidate
    candidates = list(deduped.values())
    record_correlation = as_dict(record.get("attempt_correlation"))
    correlation_hash = record_correlation.get("key_hash")
    correlation_matches = [
        candidate for candidate in candidates
        if correlation_hash
        and as_dict(candidate_runtime(candidate).get("attempt_correlation") or candidate.get("attempt_correlation")).get("key_hash") == correlation_hash
    ]

    tiers: list[tuple[str, list[dict[str, Any]]]] = []
    run_id = record.get("run_id")
    tiers.append(("joined_by_run_id", [candidate for candidate in candidates if run_id and candidate_runtime(candidate).get("run_id") == run_id]))
    typed_fields = (
        ("session_ref_hash", "joined_by_session_ref"),
        ("session_id_hash", "joined_by_session_id"),
        ("session_key_hash", "joined_by_session_key"),
    )
    for field, status in typed_fields:
        record_hash = record.get(field)
        tier_matches: list[dict[str, Any]] = []
        if record_hash:
            for candidate in candidates:
                runtime = candidate_runtime(candidate)
                candidate_hash = runtime.get(field)
                if candidate_hash is None and field == "session_id_hash":
                    candidate_hash = hash_reference(runtime.get("session_id"))
                elif candidate_hash is None and field == "session_key_hash":
                    candidate_hash = hash_reference(runtime.get("session_key"))
                if candidate_hash == record_hash:
                    tier_matches.append(candidate)
        tiers.append((status, tier_matches))
    tiers.append(("joined_by_attempt_correlation", correlation_matches))

    selected: tuple[int, str, dict[str, Any]] | None = None
    for tier_index, (status, matches) in enumerate(tiers):
        if not matches:
            continue
        if len(matches) > 1:
            return None, "ambiguous"
        selected = (tier_index, status, matches[0])
        break
    if selected is None:
        return None, "unmatched"

    tier_index, status, candidate = selected
    selected_identity = candidate_identity(candidate)
    # A lower-priority correlation key may fill in a missing identifier; it
    # must never override an identifier that was actually supplied by both
    # sides.  Otherwise a stale/wrong run ID could borrow a creditable lane
    # merely because its attempt correlation happened to match.
    candidate_runtime_values = candidate_runtime(candidate)
    for field in ("run_id", "session_ref_hash", "session_id_hash", "session_key_hash"):
        record_value = record.get(field)
        if not record_value:
            continue
        candidate_value = candidate_runtime_values.get(field) or candidate.get(field)
        if candidate_value is None and field == "session_id_hash":
            candidate_value = hash_reference(candidate_runtime_values.get("session_id"))
        elif candidate_value is None and field == "session_key_hash":
            candidate_value = hash_reference(candidate_runtime_values.get("session_key"))
        if candidate_value and candidate_value != record_value:
            return None, "identity_conflict"
    for _, lower_matches in tiers[tier_index + 1:]:
        if any(candidate_identity(row) != selected_identity for row in lower_matches):
            return None, "identity_conflict"
    candidate_correlation_hash = as_dict(
        candidate_runtime(candidate).get("attempt_correlation") or candidate.get("attempt_correlation")
    ).get("key_hash")
    if correlation_hash and candidate_correlation_hash and candidate_correlation_hash != correlation_hash:
        return None, "identity_conflict"
    consistency = candidate_consistency(candidate, record)
    if consistency:
        return None, consistency
    return candidate, status


def isolated_candidate_matches_credit_lane(record: dict[str, Any], lane: dict[str, Any] | None) -> bool:
    """Require the emitted candidate to equal the creditable lane source.

    ``receipt_matches_lane`` independently reopens the protected source for
    the lane. This second comparison prevents a distinct candidate record from
    being joined by run/attempt identity and then inheriting that lane's credit
    with altered token or timing fields.
    """
    if lane is None:
        return False
    runtime = candidate_runtime(lane)
    for key in (
        "run_id",
        "agent_id",
        "agent_role",
        "session_ref_hash",
        "model_path",
        "model_provider",
        "usage_at_utc",
        "usage_time_source",
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "total_tokens",
        "input_token_semantics",
        "source_input_total_tokens",
        "source_total_tokens_fresh",
        "duration_ms",
        "source_snapshot_fingerprint",
    ):
        expected = runtime.get(key)
        if key == "agent_id":
            expected = runtime.get(key) or lane.get(key)
        if record.get(key) != expected:
            return False
    observed_binding = as_dict(record.get("dispatch_binding"))
    expected_binding = as_dict(runtime.get("dispatch_binding"))
    return observed_binding == expected_binding


def reverified_v2_isolated_usage_records(register: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-open one protected isolated record per eligible v2 lane.

    The generic sessions index intentionally exposes observation-only v1
    records. A v2 credit event must instead come from the hash-only core bind
    plus the physical session index, so it cannot inherit credit from a
    same-run v1 observation.
    """
    try:
        agent_root = configured_isolated_session_candidate_root()
        state_db = configured_openclaw_state_db()
    except (OSError, RuntimeError):
        return []
    records_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lane in as_list(register.get("lanes")):
        if not isinstance(lane, dict) or lane.get("status") != "complete":
            continue
        runtime = candidate_runtime(lane)
        if runtime.get("token_attribution_source") != "openclaw_isolated_session_store_v2":
            continue
        agent_id = runtime.get("agent_id")
        correlation_hash = as_dict(runtime.get("attempt_correlation")).get("key_hash")
        if not isinstance(agent_id, str) or agent_id not in CONFIGURED_ISOLATED_AGENT_IDS:
            continue
        if not isinstance(correlation_hash, str):
            continue
        try:
            binding_token_hash = dispatch_binding_token_hash_for_attempt(
                attempt_correlation_hash=correlation_hash,
            )
        except ValueError:
            continue
        record, errors = load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=binding_token_hash,
            agent_state_root=agent_root,
            state_db_path=state_db,
        )
        if record is None or errors or not isolated_candidate_matches_credit_lane(record, lane):
            continue
        run_id = record.get("run_id")
        if isinstance(run_id, str) and run_id:
            records_by_run[run_id].append(record)
    # A protected source run must resolve to one lane only. Ambiguity stays
    # visible via the v1 observation path but cannot produce credit here.
    return [rows[0] for rows in records_by_run.values() if len(rows) == 1]


def isolated_session_token_event(
    record: dict[str, Any],
    pricing: dict[str, Any],
    register: dict[str, Any],
    coding_history: list[dict[str, Any]] | None = None,
    usage_receipts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    lane, join_status = match_isolated_usage_lane(record, register, coding_history)
    run_id = str(record.get("run_id") or "")
    if not run_id:
        return None
    row = {
        "tokens": record.get("total_tokens"),
        "input_tokens": record.get("input_tokens"),
        "cached_input_tokens": record.get("cached_input_tokens"),
        "cache_write_tokens": record.get("cache_write_tokens"),
        "input_token_semantics": record.get("input_token_semantics"),
        "token_semantics_status": record.get("token_semantics_status"),
        "output_tokens": record.get("output_tokens"),
        "run_id": run_id,
        "producer": "openclaw_isolated_session_store",
        "run_kind": "isolated_agent_session",
        "usage_at_utc": record.get("usage_at_utc"),
        "usage_time_source": record.get("usage_time_source"),
        "model_path": record.get("model_path"),
        "model_provider": record.get("model_provider"),
        "status": record.get("status"),
        "duration_ms": record.get("duration_ms"),
        "access_mode": "unknown",
        "access_mode_source": "not_exposed_by_session_index",
        "speed_mode": "unknown",
    }
    event = token_event(row, pricing, {run_id: lane} if lane else {}, {})
    if event is None:
        return None
    runtime = candidate_runtime(lane) if lane else {}
    attempts = lane_attempt_metadata(lane) if lane else {
        "retry_count": None,
        "attempt_number": None,
        "is_first_attempt": None,
        "is_retry": None,
    }
    event.update({
        "event_id": stable_id("token_usage", run_id, "openclaw_isolated_session_store"),
        "source_artifact": record.get("source_artifact"),
        "agent_id": record.get("agent_id"),
        "agent_role": record.get("agent_role"),
        "session_ref_hash": record.get("session_ref_hash"),
        "session_id_hash": record.get("session_id_hash"),
        "session_key_hash": record.get("session_key_hash"),
        "source_snapshot_fingerprint": record.get("source_snapshot_fingerprint"),
        "source_input_total_tokens": record.get("source_input_total_tokens"),
        "source_total_tokens_fresh": record.get("source_total_tokens_fresh"),
        "source_estimated_cost_usd": record.get("source_estimated_cost_usd"),
        "source_estimated_cost_semantics": record.get("source_estimated_cost_semantics"),
        "cache_write_tokens": record.get("cache_write_tokens"),
        "isolated_agent_attributed": True,
        "token_attribution_source": record.get("token_attribution_source"),
        "lane_join_status": join_status,
        "implementation_attributed": False,
        "parent_job_id": runtime.get("parent_job_id") if lane else None,
        "phase": normalized_outcome_state(runtime.get("phase")) or None,
        "attempt_number": attempts.get("attempt_number"),
        "retry_count": attempts.get("retry_count"),
        "is_first_attempt": attempts.get("is_first_attempt"),
        "is_retry": attempts.get("is_retry"),
        "attempt_id": safe_metadata_id(runtime.get("attempt_id")),
        "attempt_correlation": record.get("attempt_correlation"),
        "incident_code": normalized_outcome_state(runtime.get("incident_code")) or None,
        "outcome_event_kind": normalized_outcome_state(runtime.get("outcome_event_kind")) or None,
        "outcome_status": normalized_outcome_state(runtime.get("outcome_status")) or None,
        "main_acceptance_status": normalized_outcome_state(runtime.get("main_acceptance_status")) or None,
        "pricing_unavailable_reason": record.get("pricing_unavailable_reason"),
    })
    deterministic_join = join_status in CREDITABLE_ISOLATED_JOIN_STATUSES
    candidate_matches_credit_lane = isolated_candidate_matches_credit_lane(record, lane)
    receipt_valid, receipt_reason = receipt_matches_lane(lane, usage_receipts or [])
    event["usage_creditable"] = (
        deterministic_join
        and candidate_matches_credit_lane
        and event.get("token_semantics_status") == "valid"
        and event.get("source_total_tokens_fresh") is True
        and lane is not None
        and receipt_valid
    )
    event["usage_credit_block_reason"] = (
        None if event["usage_creditable"] else (
            "deterministic_run_or_attempt_join_required"
            if not deterministic_join else (receipt_reason or "source_or_token_reconciliation_invalid")
        )
    )
    if not event["usage_creditable"] and deterministic_join and not candidate_matches_credit_lane:
        event["usage_credit_block_reason"] = "isolated_candidate_lane_mismatch"
    event["implementation_attributed"] = event["usage_creditable"] is True
    event["attribution_grade"] = (
        event["usage_creditable"] is True
        and event.get("token_semantics_status") == "valid"
        and event.get("source_total_tokens_fresh") is True
    )
    event["pricing_grade"] = (
        event["attribution_grade"] is True
        and int(event.get("cache_write_tokens") or 0) == 0
        and event.get("api_equivalent_cost_usd") is not None
    )
    return event


def validate_isolated_session_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for event in events:
        reasons: list[str] = []
        if event.get("agent_id") not in CONFIGURED_ISOLATED_AGENT_IDS:
            reasons.append("agent_not_allowlisted")
        for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens"):
            value = as_int(event.get(key))
            if value is None or value < 0:
                reasons.append(f"invalid_{key}")
        source_input_total = as_int(event.get("source_input_total_tokens"))
        expected_input_total = sum(int(event.get(key) or 0) for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens"))
        if source_input_total != expected_input_total:
            reasons.append("source_input_total_mismatch")
        if as_int(event.get("total_tokens")) != expected_input_total + int(event.get("output_tokens") or 0):
            reasons.append("ledger_total_mismatch")
        if event.get("source_total_tokens_fresh") is not True:
            reasons.append("source_total_tokens_not_fresh")
        if event.get("token_semantics_status") != "valid":
            reasons.append("token_semantics_not_valid")
        observed_at = parse_utc(event.get("usage_at_utc"))
        cutover = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
        if observed_at is not None and cutover is not None and observed_at >= cutover and event.get("usage_creditable") is not True:
            reasons.append("post_cutover_deterministic_usage_join_required")
        if int(event.get("cache_write_tokens") or 0) > 0 and (
            event.get("api_equivalent_cost_usd") is not None
            or event.get("estimated_chatgpt_credits") is not None
        ):
            reasons.append("cache_write_received_price")
        privacy = scan_forbidden(event)
        if privacy:
            reasons.append("privacy_scan_failed")
        if reasons:
            unique_reasons = sorted(set(reasons))
            severity = (
                "warning"
                if unique_reasons == ["post_cutover_deterministic_usage_join_required"]
                else "critical"
            )
            findings.append({
                "event_id": event.get("event_id"),
                "agent_id": event.get("agent_id"),
                "severity": severity,
                "credit_class": "noncreditable_observed_usage" if severity == "warning" else "blocked_integrity",
                "reasons": unique_reasons,
            })
    return findings


def per_agent_usage_rows(
    events: list[dict[str, Any]],
    gateway_usage: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    gateway_by_agent = {
        str(row.get("agent_id")): row
        for row in as_list(as_dict(gateway_usage).get("agents"))
        if isinstance(row, dict) and row.get("agent_id")
    }
    rows: list[dict[str, Any]] = []
    reporting_total = 0
    provisional: list[dict[str, Any]] = []
    for agent_id in CONFIGURED_ISOLATED_AGENT_IDS:
        agent_events = [row for row in events if row.get("agent_id") == agent_id]
        gateway = as_dict(gateway_by_agent.get(agent_id))
        gateway_totals = as_dict(gateway.get("totals")) if gateway.get("status") == "ok" else {}
        gateway_tokens = as_int(gateway_totals.get("totalTokens"))
        session_tokens = sum(int(row.get("total_tokens") or 0) for row in agent_events)
        preferred_tokens = gateway_tokens if gateway_tokens is not None else session_tokens
        reporting_total += preferred_tokens
        provisional.append({
            "agent_id": agent_id,
            "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
            "reporting_source": "gateway_usage_cost" if gateway_tokens is not None else "session_index_fallback",
            "gateway_status": gateway.get("status") or "not_requested",
            "gateway_errors": as_list(gateway.get("errors")),
            "reporting_window_days": gateway.get("days"),
            "reporting_total_tokens": preferred_tokens,
            "reporting_total_cost": gateway_totals.get("totalCost") if gateway_tokens is not None else None,
            "session_event_count": len(agent_events),
            "session_total_tokens": session_tokens,
            "session_attribution_grade_event_count": sum(1 for row in agent_events if row.get("attribution_grade") is True),
            "session_pricing_grade_event_count": sum(1 for row in agent_events if row.get("pricing_grade") is True),
            "implementation_attributed_event_count": sum(1 for row in agent_events if row.get("implementation_attributed") is True),
            "utilized": preferred_tokens > 0,
            "gateway_attribution_grade": gateway.get("attribution_grade"),
            "gateway_pricing_grade": gateway.get("pricing_grade"),
            "session_events_excluded_from_gateway_reporting_totals": gateway_tokens is not None,
        })
    for row in provisional:
        row["utilization_share_percent"] = round(
            (int(row["reporting_total_tokens"]) / reporting_total) * 100.0, 4
        ) if reporting_total else 0.0
        rows.append(row)
    return rows


def _gateway_window_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")
    result: dict[str, Any] = {key: sum(int(row.get(key) or 0) for row in rows) for key in fields}
    costs = [as_float(row.get("totalCost")) for row in rows]
    result["totalCost"] = round(sum(value or 0.0 for value in costs), 6) if rows and all(value is not None for value in costs) else None
    result["missingCostEntries"] = sum(int(row.get("missingCostEntries") or 0) for row in rows)
    return result


def build_fleet_reporting(
    events: list[dict[str, Any]],
    register: dict[str, Any],
    gateway_usage: dict[str, Any] | None,
    implementation_gaps: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    gateway_by_agent = {
        str(row.get("agent_id")): row
        for row in as_list(as_dict(gateway_usage).get("agents"))
        if isinstance(row, dict) and row.get("agent_id")
    }
    gap_lane_ids = {str(row.get("lane_id")) for row in implementation_gaps if row.get("lane_id")}
    usage_receipts = load_usage_source_receipts()

    def outcome_creditable_lane(lane: dict[str, Any]) -> bool:
        """New model-outcome metrics require the same receipt as token credit."""
        runtime = as_dict(lane.get("runtime"))
        model_path = runtime.get("model_path") or lane.get("model_path")
        if not model_path:
            return True
        if not telemetry_enforcement_applies(lane, runtime):
            return True
        valid, _reason = receipt_matches_lane(lane, usage_receipts)
        return valid
    now_utc = now.astimezone(timezone.utc)
    cutoff_5h = now_utc - timedelta(hours=5)
    today = now_utc.date().isoformat()
    agents: list[dict[str, Any]] = []
    for agent_id in CONFIGURED_ISOLATED_AGENT_IDS:
        agent_events = [row for row in events if row.get("agent_id") == agent_id]
        recent_events = [
            row for row in agent_events
            if parse_utc(row.get("usage_at_utc")) is not None
            and parse_utc(row.get("usage_at_utc")) >= cutoff_5h
        ]
        gateway = as_dict(gateway_by_agent.get(agent_id))
        gateway_ok = gateway.get("status") == "ok" and gateway.get("reporting_eligible") is True
        daily = [row for row in as_list(gateway.get("daily")) if isinstance(row, dict)] if gateway_ok else []
        daily_sorted = sorted(daily, key=lambda row: str(row.get("date") or ""))
        latest_24h_rows = [row for row in daily_sorted if row.get("date") == today]
        if not latest_24h_rows and daily_sorted:
            latest_24h_rows = daily_sorted[-1:]
        closed_rows = [row for row in daily_sorted if str(row.get("date") or "") < today][-7:]
        agent_lanes = [
            lane for lane in as_list(register.get("lanes"))
            if isinstance(lane, dict) and lane_agent_id(lane) == agent_id
        ]
        completed = [
            lane for lane in agent_lanes
            if lane.get("status") == "complete"
            and normalized_outcome_state(as_dict(lane.get("runtime")).get("outcome_event_kind")) != "incident"
        ]
        credited_completed = [lane for lane in completed if outcome_creditable_lane(lane)]
        uncredited_completed = [lane for lane in completed if lane not in credited_completed]
        outcome_tracking_start = parse_utc(FLEET_OUTCOME_TRACKING_START_UTC)
        outcome_eligible_completed = [
            lane for lane in credited_completed
            if outcome_tracking_start is not None
            and (parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc")) or datetime.min.replace(tzinfo=timezone.utc))
            >= outcome_tracking_start
        ]
        historical_or_untracked_completed = [
            lane for lane in credited_completed if lane not in outcome_eligible_completed
        ]
        parent_jobs = {
            str(as_dict(lane.get("runtime")).get("parent_job_id"))
            for lane in agent_lanes
            if as_dict(lane.get("runtime")).get("parent_job_id")
        }
        completed_parent_jobs = {
            str(as_dict(lane.get("runtime")).get("parent_job_id"))
            for lane in credited_completed
            if as_dict(lane.get("runtime")).get("parent_job_id")
        }
        accepted_states = {
            "accepted", "accepted_with_documented_limits", "approved", "merged", "complete", "passed",
        }
        rework_states = {"rework", "changes_required", "rejected", "failed"}
        accepted = [
            lane for lane in outcome_eligible_completed
            if normalized_outcome_state(as_dict(lane.get("runtime")).get("main_acceptance_status")) in accepted_states
        ]
        first_attempt_completed = [
            lane for lane in outcome_eligible_completed
            if lane_attempt_metadata(lane).get("is_first_attempt") is True
        ]
        retry_completed = [
            lane for lane in outcome_eligible_completed
            if lane_attempt_metadata(lane).get("is_retry") is True
        ]
        unknown_attempt_completed = [
            lane for lane in outcome_eligible_completed
            if lane_attempt_metadata(lane).get("attempt_number") is None
        ]
        first_attempt_accepted = [lane for lane in accepted if lane in first_attempt_completed]
        accepted_after_retry = [lane for lane in accepted if lane in retry_completed]
        rework = [
            lane for lane in outcome_eligible_completed
            if normalized_outcome_state(as_dict(lane.get("runtime")).get("outcome_status")) in rework_states
            or normalized_outcome_state(as_dict(lane.get("runtime")).get("main_acceptance_status")) in rework_states
        ]
        qa_review_completed = [
            lane for lane in outcome_eligible_completed
            if normalized_outcome_state(as_dict(lane.get("runtime")).get("phase")) == "qa"
        ]
        qa_pass = [
            lane for lane in qa_review_completed
            if normalized_outcome_state(as_dict(lane.get("runtime")).get("outcome_status"))
            in {"pass", "passed", "accepted", "qa_pass", "pass_with_warnings", "passed_with_warnings"}
        ]
        first_attempt_qa_reviews = [lane for lane in qa_review_completed if lane in first_attempt_completed]
        retry_qa_reviews = [lane for lane in qa_review_completed if lane in retry_completed]
        first_attempt_qa_pass = [lane for lane in qa_pass if lane in first_attempt_qa_reviews]
        qa_pass_after_retry = [lane for lane in qa_pass if lane in retry_qa_reviews]
        incident_count = 0
        incident_lane_count = 0
        for lane in agent_lanes:
            runtime = as_dict(lane.get("runtime"))
            persisted = strict_attempt_int(runtime.get("incident_count"), minimum=0)
            is_incident_lane = (
                lane.get("status") in {"blocked", "cancelled"}
                or normalized_outcome_state(runtime.get("outcome_event_kind")) == "incident"
            )
            if persisted is not None and persisted > 0:
                incident_count += persisted
                incident_lane_count += 1
            elif is_incident_lane:
                incident_count += 1
                incident_lane_count += 1
        attribution_gap_count = sum(
            1 for lane in completed
            if str(lane.get("lane_id")) in gap_lane_ids
            or str(as_dict(lane.get("runtime")).get("token_closeout_status") or "") in {"invalid_usage", "attribution_incomplete"}
            or lane in uncredited_completed
        )
        agents.append({
            "agent_id": agent_id,
            "agent_role": CONFIGURED_ISOLATED_AGENT_ROLES[agent_id],
            "usage_windows": {
                "rolling_5h_observed": {
                    "status": "observed" if recent_events else "no_observed_session_events",
                    "source": "allowlisted_sessions_index_terminal_run_metadata",
                    "coverage": "partial_latest_session_snapshots_not_provider_history",
                    "event_count": len(recent_events),
                    "total_tokens": sum(int(row.get("total_tokens") or 0) for row in recent_events),
                    "input_tokens": sum(int(row.get("input_tokens") or 0) for row in recent_events),
                    "cached_input_tokens": sum(int(row.get("cached_input_tokens") or 0) for row in recent_events),
                    "cache_write_tokens": sum(int(row.get("cache_write_tokens") or 0) for row in recent_events),
                    "output_tokens": sum(int(row.get("output_tokens") or 0) for row in recent_events),
                },
                "rolling_24h_gateway": {
                    "status": "ok" if gateway_ok and latest_24h_rows else ("no_daily_row" if gateway_ok else "blocked"),
                    "source": "openclaw_gateway_usage_cost_daily",
                    "date_labels": [row.get("date") for row in latest_24h_rows],
                    "totals": _gateway_window_totals(latest_24h_rows) if gateway_ok and latest_24h_rows else {},
                    "cost_semantics": "api_equivalent_not_invoice",
                },
                "closed_7d_gateway": {
                    "status": "ok" if gateway_ok and len(closed_rows) == 7 else ("partial" if gateway_ok and closed_rows else "blocked"),
                    "source": "openclaw_gateway_usage_cost_daily",
                    "closed_day_count": len(closed_rows),
                    "date_labels": [row.get("date") for row in closed_rows],
                    "totals": _gateway_window_totals(closed_rows) if gateway_ok and closed_rows else {},
                    "cost_semantics": "api_equivalent_not_invoice",
                },
            },
            "outcomes": {
                "lane_count": len(agent_lanes),
                "completed_lane_count": len(completed),
                "outcome_creditable_completed_lane_count": len(credited_completed),
                "outcome_uncreditable_completed_lane_count": len(uncredited_completed),
                "outcome_tracking_start_utc": FLEET_OUTCOME_TRACKING_START_UTC,
                "outcome_eligible_completed_lane_count": len(outcome_eligible_completed),
                "historical_or_untracked_completed_lane_count": len(historical_or_untracked_completed),
                "parent_job_count": len(parent_jobs),
                "parent_job_completed_count": len(completed_parent_jobs),
                "main_accepted_count": len(accepted),
                "main_acceptance_pending_count": max(len(outcome_eligible_completed) - len(accepted), 0),
                "first_attempt_completed_count": len(first_attempt_completed),
                "retry_completed_count": len(retry_completed),
                "unknown_attempt_completed_count": len(unknown_attempt_completed),
                "first_attempt_main_accepted_count": len(first_attempt_accepted),
                "accepted_after_retry_count": len(accepted_after_retry),
                "qa_review_completed_count": len(qa_review_completed),
                "qa_pass_count": len(qa_pass),
                "qa_yield_percent": round((len(qa_pass) / len(qa_review_completed)) * 100.0, 4) if qa_review_completed else None,
                "first_attempt_qa_review_count": len(first_attempt_qa_reviews),
                "first_attempt_qa_pass_count": len(first_attempt_qa_pass),
                "first_attempt_qa_yield_percent": round((len(first_attempt_qa_pass) / len(first_attempt_qa_reviews)) * 100.0, 4) if first_attempt_qa_reviews else None,
                "retry_qa_review_count": len(retry_qa_reviews),
                "qa_pass_after_retry_count": len(qa_pass_after_retry),
                "incident_count": incident_count,
                "incident_lane_count": incident_lane_count,
                "rework_count": len(rework),
                "attribution_gap_count": attribution_gap_count,
            },
        })
    return {
        "schema": "veritas.isolated_agent_fleet_reporting.v1",
        "generated_at_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "outcome_credit_contract": {
            "version": FLEET_OUTCOME_CREDIT_CONTRACT_VERSION,
            "status": "verified",
            "post_cutover_source_reverification_required": True,
            "source": "receipt_revalidated_lane_outcome_projection",
        },
        "window_contract": {
            "rolling_5h_observed_source": "session_index_terminal_metadata_with_partial_coverage",
            "rolling_24h_source": "Gateway usage-cost clean daily row",
            "closed_7d_source": "last seven clean Gateway daily rows before current UTC date",
            "gateway_cache_must_be_clean": True,
            "gateway_cost_semantics": "api_equivalent_not_invoice",
            "actual_billed_cost_inferred": False,
        },
        "summary": {
            "configured_agent_count": len(CONFIGURED_ISOLATED_AGENT_IDS),
            "gateway_24h_ready_agent_count": sum(1 for row in agents if as_dict(as_dict(row.get("usage_windows")).get("rolling_24h_gateway")).get("status") == "ok"),
            "gateway_closed_7d_ready_agent_count": sum(1 for row in agents if as_dict(as_dict(row.get("usage_windows")).get("closed_7d_gateway")).get("status") == "ok"),
            "completed_lane_count": sum(int(as_dict(row.get("outcomes")).get("completed_lane_count") or 0) for row in agents),
            "outcome_creditable_completed_lane_count": sum(int(as_dict(row.get("outcomes")).get("outcome_creditable_completed_lane_count") or 0) for row in agents),
            "outcome_uncreditable_completed_lane_count": sum(int(as_dict(row.get("outcomes")).get("outcome_uncreditable_completed_lane_count") or 0) for row in agents),
            "outcome_eligible_completed_lane_count": sum(int(as_dict(row.get("outcomes")).get("outcome_eligible_completed_lane_count") or 0) for row in agents),
            "historical_or_untracked_completed_lane_count": sum(int(as_dict(row.get("outcomes")).get("historical_or_untracked_completed_lane_count") or 0) for row in agents),
            "main_accepted_count": sum(int(as_dict(row.get("outcomes")).get("main_accepted_count") or 0) for row in agents),
            "first_attempt_completed_count": sum(int(as_dict(row.get("outcomes")).get("first_attempt_completed_count") or 0) for row in agents),
            "retry_completed_count": sum(int(as_dict(row.get("outcomes")).get("retry_completed_count") or 0) for row in agents),
            "unknown_attempt_completed_count": sum(int(as_dict(row.get("outcomes")).get("unknown_attempt_completed_count") or 0) for row in agents),
            "first_attempt_main_accepted_count": sum(int(as_dict(row.get("outcomes")).get("first_attempt_main_accepted_count") or 0) for row in agents),
            "accepted_after_retry_count": sum(int(as_dict(row.get("outcomes")).get("accepted_after_retry_count") or 0) for row in agents),
            "qa_review_completed_count": sum(int(as_dict(row.get("outcomes")).get("qa_review_completed_count") or 0) for row in agents),
            "qa_pass_count": sum(int(as_dict(row.get("outcomes")).get("qa_pass_count") or 0) for row in agents),
            "first_attempt_qa_review_count": sum(int(as_dict(row.get("outcomes")).get("first_attempt_qa_review_count") or 0) for row in agents),
            "first_attempt_qa_pass_count": sum(int(as_dict(row.get("outcomes")).get("first_attempt_qa_pass_count") or 0) for row in agents),
            "retry_qa_review_count": sum(int(as_dict(row.get("outcomes")).get("retry_qa_review_count") or 0) for row in agents),
            "qa_pass_after_retry_count": sum(int(as_dict(row.get("outcomes")).get("qa_pass_after_retry_count") or 0) for row in agents),
            "incident_count": sum(int(as_dict(row.get("outcomes")).get("incident_count") or 0) for row in agents),
            "incident_lane_count": sum(int(as_dict(row.get("outcomes")).get("incident_lane_count") or 0) for row in agents),
            "rework_count": sum(int(as_dict(row.get("outcomes")).get("rework_count") or 0) for row in agents),
            "attribution_gap_count": sum(int(as_dict(row.get("outcomes")).get("attribution_gap_count") or 0) for row in agents),
        },
        "agents": agents,
    }


def implementation_gap_rows(register: dict[str, Any], token_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # A self-declared or ambiguously joined token row is retained in the raw
    # ledger but cannot close an implementation attribution gap.
    token_lane_ids = {
        event.get("lane_id")
        for event in token_events
        if event.get("lane_id") and event.get("usage_creditable") is True
    }
    rows: list[dict[str, Any]] = []
    for lane in as_list(register.get("lanes")):
        if not isinstance(lane, dict) or lane.get("status") != "complete":
            continue
        runtime = as_dict(lane.get("runtime"))
        model_path = runtime.get("model_path") or lane.get("model_path")
        lane_id = lane.get("lane_id")
        if not model_path or lane_id in token_lane_ids:
            continue
        support = model_support(model_path)
        rows.append({
            "lane_id": lane_id,
            "workflow_id": lane.get("workflow_id"),
            "workstream_id": lane.get("workstream_id"),
            "task_name": runtime.get("task_name") or lane.get("workstream_id"),
            "model_path": model_path,
            "model_support": support,
            "supported_model_capacity": support.get("active_route_countable") is True,
            "status": lane.get("status"),
            "token_status": "missing_usage",
            "reason": "lane has model/runtime metadata but no matching token-bearing run_id",
        })
    return rows


def efficiency_measurement(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe the strictly attributable efficiency cohort without inventing savings.

    A dollar/token saving needs two comparable, accepted cohorts and an explicit
    baseline.  Until then this is deliberately an observation gate, not a
    percentage-saving estimate.
    """
    jobs: dict[str, dict[str, Any]] = {}
    for event in events:
        parent_job_id = str(event.get("parent_job_id") or "")
        if not parent_job_id:
            continue
        if event.get("usage_creditable") is not True or event.get("implementation_attributed") is not True:
            continue
        if normalized_outcome_state(event.get("main_acceptance_status")) not in MAIN_ACCEPTED_OUTCOME_STATES:
            continue
        if normalized_outcome_state(event.get("outcome_event_kind")) == "incident":
            continue
        if strict_attempt_int(event.get("attempt_number"), minimum=1) is None:
            continue
        cohort = {
            "model_path": str(event.get("model_path") or "unknown"),
            "phase": normalized_outcome_state(event.get("phase")) or "unknown",
        }
        entry = jobs.setdefault(parent_job_id, {"parent_job_id": parent_job_id, "cohort": cohort, "total_tokens": 0})
        if entry["cohort"] != cohort:
            # A mixed-model job is useful audit data but not a like-for-like
            # efficiency observation.
            entry["mixed_route"] = True
        entry["total_tokens"] += int(event.get("total_tokens") or 0)
    cohorts: dict[str, dict[str, Any]] = {}
    for job in jobs.values():
        if job.get("mixed_route"):
            continue
        cohort = as_dict(job.get("cohort"))
        key = f"{cohort.get('model_path')}|{cohort.get('phase')}"
        bucket = cohorts.setdefault(key, {**cohort, "main_accepted_parent_job_count": 0, "total_tokens": 0})
        bucket["main_accepted_parent_job_count"] += 1
        bucket["total_tokens"] += int(job.get("total_tokens") or 0)
    rows = []
    for row in cohorts.values():
        count = int(row["main_accepted_parent_job_count"])
        rows.append({
            **row,
            "average_gross_tokens_per_main_accepted_job": round(row["total_tokens"] / count, 4) if count else None,
            "minimum_comparable_jobs_met": count >= EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS,
        })
    rows.sort(key=lambda row: (str(row["model_path"]), str(row["phase"])))
    enough_observations = [row for row in rows if row["minimum_comparable_jobs_met"]]
    return {
        "schema": "veritas.efficiency_measurement.v1",
        "minimum_comparable_main_accepted_jobs": EFFICIENCY_MIN_COMPARABLE_MAIN_ACCEPTED_JOBS,
        "eligible_main_accepted_parent_job_count": len([job for job in jobs.values() if not job.get("mixed_route")]),
        "mixed_route_parent_job_count": sum(1 for job in jobs.values() if job.get("mixed_route")),
        "cohorts": rows,
        "baseline_configured": False,
        "savings_claim_allowed": False,
        "status": (
            "baseline_required" if enough_observations else "insufficient_attributable_comparable_cohort"
        ),
        "reason": "Savings remains blocked until an explicit like-for-like baseline is configured; raw or unjoined usage is excluded.",
    }


def aggregate(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "uncached_input_tokens": 0,
            "uncached_input_token_rows": 0,
            "output_tokens": 0,
            "failed_or_error_count": 0,
            "api_equivalent_cost_usd": 0.0,
            "api_equivalent_cost_rows": 0,
            "estimated_cost": 0.0,
            "estimated_cost_rows": 0,
            "estimated_chatgpt_credits": 0.0,
            "estimated_chatgpt_credit_rows": 0,
        }
    )
    for event in events:
        label = str(event.get(key) or "unknown")
        bucket = buckets[label]
        bucket["count"] += 1
        bucket["total_tokens"] += int(event.get("total_tokens") or 0)
        bucket["input_tokens"] += int(event.get("input_tokens") or 0)
        bucket["cached_input_tokens"] += int(event.get("cached_input_tokens") or 0)
        if event.get("uncached_input_tokens") is not None:
            bucket["uncached_input_tokens"] += int(event.get("uncached_input_tokens") or 0)
            bucket["uncached_input_token_rows"] += 1
        bucket["output_tokens"] += int(event.get("output_tokens") or 0)
        if str(event.get("status") or "").lower() not in {"ok", "complete", "success"}:
            bucket["failed_or_error_count"] += 1
        api_equivalent = event.get("api_equivalent_cost_usd")
        if api_equivalent is None:
            api_equivalent = event.get("estimated_cost")
        if api_equivalent is not None:
            bucket["api_equivalent_cost_usd"] += float(api_equivalent or 0)
            bucket["estimated_cost"] += float(api_equivalent or 0)
            bucket["api_equivalent_cost_rows"] += 1
            bucket["estimated_cost_rows"] += 1
        if event.get("estimated_chatgpt_credits") is not None:
            bucket["estimated_chatgpt_credits"] += float(event.get("estimated_chatgpt_credits") or 0)
            bucket["estimated_chatgpt_credit_rows"] += 1
    rows = []
    for label, bucket in buckets.items():
        rows.append({
            key: label,
            **bucket,
            "api_equivalent_cost_usd": round(bucket["api_equivalent_cost_usd"], 6) if bucket["api_equivalent_cost_rows"] else None,
            "api_equivalent_estimate_status": (
                "unavailable" if not bucket["api_equivalent_cost_rows"]
                else "complete" if bucket["api_equivalent_cost_rows"] == bucket["count"]
                else "partial_unknown_input_semantics_or_missing_rate"
            ),
            "estimated_cost": round(bucket["api_equivalent_cost_usd"], 6) if bucket["api_equivalent_cost_rows"] else None,
            "estimated_cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd",
            "actual_billed_cost_usd": None,
            "estimated_chatgpt_credits": round(bucket["estimated_chatgpt_credits"], 6) if bucket["estimated_chatgpt_credit_rows"] else None,
            "chatgpt_credit_estimate_status": (
                "unavailable" if not bucket["estimated_chatgpt_credit_rows"]
                else "complete" if bucket["estimated_chatgpt_credit_rows"] == bucket["count"]
                else "partial_separate_no_public_rate_or_missing_rate"
            ),
            "uncached_input_tokens": bucket["uncached_input_tokens"] if bucket["uncached_input_token_rows"] else None,
        })
    return sorted(rows, key=lambda row: int(row.get("total_tokens") or 0), reverse=True)


def latest_by_event_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        event_id = str(row.get("event_id") or "")
        if not event_id:
            continue
        existing = latest.get(event_id)
        if not existing or str(row.get("recorded_at_utc") or "") >= str(existing.get("recorded_at_utc") or ""):
            latest[event_id] = row
    return list(latest.values())


def priced_view_event(event: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    """Return an in-memory cost-enriched event without rewriting history."""
    result = dict(event)
    total_tokens = as_int(result.get("total_tokens"))
    input_tokens = as_int(result.get("input_tokens"))
    output_tokens = as_int(result.get("output_tokens"))
    cached_input_tokens = first_int(result.get("cached_input_tokens"), result.get("cache_read_tokens"))
    cache_write_tokens = first_int(result.get("cache_write_tokens"), 0)
    result["cached_input_tokens"] = cached_input_tokens
    result["cache_write_tokens"] = cache_write_tokens
    declared_input_semantics = result.get("input_token_semantics")
    upstream_semantics_status = result.get("token_semantics_status")
    access_mode, access_mode_source = normalize_access_mode(result.get("access_mode"), result.get("access_mode_source"))
    speed_mode = normalize_speed_mode(result.get("speed_mode"))
    result["access_mode"] = access_mode
    result["access_mode_source"] = access_mode_source
    result["speed_mode"] = speed_mode
    normalized_breakdown = resolve_input_token_semantics(input_tokens, cached_input_tokens, declared_input_semantics)
    reconciliation = reconcile_token_total(total_tokens, output_tokens, normalized_breakdown, cache_write_tokens)
    effective_semantics_status = (
        str(upstream_semantics_status)
        if upstream_semantics_status is not None and str(upstream_semantics_status) != "valid"
        else str(reconciliation.get("token_semantics_status") or "invalid")
    )
    cost = estimate_cost(result.get("model_path"), input_tokens, output_tokens, pricing, cached_input_tokens, declared_input_semantics, effective_semantics_status, cache_write_tokens)
    token_breakdown = as_dict(cost.get("input_token_breakdown"))
    result["uncached_input_tokens"] = token_breakdown.get("uncached_input_tokens")
    result["input_token_semantics"] = token_breakdown.get("input_token_semantics")
    result["input_token_semantics_source"] = token_breakdown.get("input_token_semantics_source")
    result["input_token_semantics_valid"] = token_breakdown.get("input_token_semantics_valid")
    result["input_token_semantics_reason"] = token_breakdown.get("reason")
    result["token_semantics_status"] = effective_semantics_status
    result["token_semantics_reasons"] = [
        *[str(reason) for reason in as_list(result.get("token_semantics_reasons"))],
        *[str(reason) for reason in as_list(reconciliation.get("token_semantics_reasons"))],
    ]
    result["token_total_expected"] = reconciliation.get("token_total_expected")
    result["token_total_delta"] = reconciliation.get("token_total_delta")
    result["token_total_tolerance_tokens"] = reconciliation.get("token_total_tolerance_tokens")
    result.setdefault("usage_at_utc", None)
    result.setdefault("usage_time_source", None)
    api_equivalent = cost.get("api_equivalent_cost_usd")
    result["api_equivalent_cost_usd"] = api_equivalent
    result["estimated_cost"] = api_equivalent
    result["estimated_cost_semantics"] = "deprecated_alias_of_api_equivalent_cost_usd"
    result.setdefault("actual_billed_cost_usd", None)
    result.setdefault("actual_billed_cost_source", "not_recorded_do_not_infer")
    result["pricing_status"] = cost.get("pricing_status")
    result["api_equivalent_pricing_status"] = cost.get("pricing_status")
    result["pricing_model_path"] = cost.get("pricing_model_path")
    result["pricing_resolution"] = cost.get("pricing_resolution")
    result["pricing_context_class"] = cost.get("pricing_context_class")
    result["pricing_context_input_tokens"] = cost.get("pricing_context_input_tokens")
    result["pricing_context_limit_tokens"] = cost.get("pricing_context_limit_tokens")
    credits = estimate_chatgpt_credits(
        result.get("model_path"),
        input_tokens,
        output_tokens,
        cached_input_tokens,
        pricing,
        declared_input_semantics,
        effective_semantics_status,
        speed_mode,
        access_mode,
        cache_write_tokens,
    )
    result["estimated_chatgpt_credits"] = credits.get("estimated_chatgpt_credits")
    result["chatgpt_credit_pricing_status"] = credits.get("chatgpt_credit_pricing_status")
    result["chatgpt_credit_rate_classification"] = credits.get("chatgpt_credit_rate_classification")
    result["chatgpt_credit_speed_mode"] = credits.get("chatgpt_credit_speed_mode")
    result["chatgpt_credit_speed_assumption"] = credits.get("chatgpt_credit_speed_assumption")
    result["chatgpt_credit_access_mode"] = credits.get("chatgpt_credit_access_mode")
    result["chatgpt_credit_access_assumption"] = credits.get("chatgpt_credit_access_assumption")
    result["credit_pricing_model_path"] = credits.get("credit_pricing_model_path")
    result["credit_pricing_resolution"] = credits.get("credit_pricing_resolution")
    support = model_support(result.get("model_path"))
    result["model_support"] = support
    result["supported_model_capacity"] = support.get("active_route_countable") is True
    return result


def build_payload(
    ledger_path: Path,
    append: bool,
    policy_path: Path = OAUTH_POLICY,
    capacity_path: Path = OAUTH_CAPACITY_CURRENT,
    now: datetime | None = None,
    isolated_gateway_usage: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model_run = as_dict(load_json_artifact(MODEL_RUN_LEDGER))
    register = as_dict(load_json_artifact(LANE_REGISTER))
    coding_current = as_dict(load_json_artifact(CODING_OUTCOME))
    pricing = load_pricing(PRICING)
    oauth_policy = load_policy(policy_path)
    capacity_snapshot = as_dict(load_json_artifact(capacity_path))
    try:
        isolated_session_usage = load_allowlisted_session_usage(
            CONFIGURED_ISOLATED_AGENT_IDS,
            configured_isolated_session_candidate_root(),
        )
    except (OSError, RuntimeError, ValueError):
        # Candidate observation is optional; an unavailable trusted root must
        # never fall back to a HOME/USERPROFILE-derived path for credit.
        isolated_session_usage = {"records": []}
    reverified_v2_records = reverified_v2_isolated_usage_records(register)
    reverified_v2_run_ids = {
        str(record.get("run_id"))
        for record in reverified_v2_records
        if record.get("run_id")
    }
    isolated_credit_candidates = [
        record
        for record in as_list(isolated_session_usage.get("records"))
        if isinstance(record, dict) and str(record.get("run_id") or "") not in reverified_v2_run_ids
    ] + reverified_v2_records
    lanes_by_run, ambiguous_lane_run_ids = lane_index(register)
    coding_history_rows = read_jsonl(CODING_OUTCOME_HISTORY)
    coding_by_run, ambiguous_coding_run_ids = coding_history_index(coding_history_rows)
    ambiguous_run_ids = ambiguous_lane_run_ids | ambiguous_coding_run_ids
    usage_receipts = load_usage_source_receipts()
    existing = read_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    model_candidate_events = [
        event for event in (
            token_event(row, pricing, lanes_by_run, coding_by_run, ambiguous_run_ids, usage_receipts)
            for row in as_list(model_run.get("rows"))
            if isinstance(row, dict)
        )
        if event is not None
    ]
    isolated_candidate_events = [
        event for event in (
            isolated_session_token_event(record, pricing, register, coding_history_rows, usage_receipts)
            for record in isolated_credit_candidates
        )
        if event is not None
    ]
    creditable_provider_run_ids = creditable_candidate_run_ids(
        model_candidate_events,
        isolated_candidate_events,
    )
    observed_provider_run_ids = provider_observation_run_ids(
        model_candidate_events,
        isolated_candidate_events,
    )
    lane_candidate_events = [
        event for event in (
            lane_token_event(
                lane,
                pricing,
                observed_provider_run_ids,
                usage_receipts,
                creditable_provider_run_ids=creditable_provider_run_ids,
                ambiguous_lane_run_ids=ambiguous_lane_run_ids,
            )
            for lane in as_list(register.get("lanes"))
            if isinstance(lane, dict)
        )
        if event is not None
    ]
    candidate_events = model_candidate_events + isolated_candidate_events + lane_candidate_events
    new_events = [event for event in candidate_events if event.get("event_id") not in existing_ids]
    if append:
        append_jsonl(ledger_path, new_events)
    first_ingested_at = first_ingestion_times(existing + (new_events if append else []))
    # Candidate events also form the current in-memory view so newly clarified
    # token semantics/timestamps can enrich old event IDs without rewriting the
    # append-only history. Only truly new IDs are appended above.
    all_events = latest_by_event_id([row for row in existing + candidate_events if row.get("schema") == EVENT_SCHEMA])
    all_events = reconcile_derived_creditable_events(all_events, candidate_events)
    all_events = [
        priced_view_event(row, pricing)
        for row in all_events
        if as_int(row.get("total_tokens")) is not None and int(row.get("total_tokens")) >= 0
    ]
    gaps = implementation_gap_rows(register, all_events)
    token_events = sorted(all_events, key=lambda row: int(row.get("total_tokens") or 0), reverse=True)
    creditable_events = [row for row in token_events if row.get("usage_creditable") is True]
    efficiency = efficiency_measurement(token_events)
    isolated_events = [row for row in token_events if row.get("isolated_agent_attributed") is True]
    isolated_event_validation_findings = validate_isolated_session_events(isolated_events)
    isolated_event_validation_errors = [
        row for row in isolated_event_validation_findings
        if row.get("severity") == "critical"
    ]
    isolated_event_validation_warnings = [
        row for row in isolated_event_validation_findings
        if row.get("severity") != "critical"
    ]
    per_agent_usage = per_agent_usage_rows(isolated_events, isolated_gateway_usage)
    pace_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    fleet_reporting = build_fleet_reporting(
        isolated_events,
        register,
        isolated_gateway_usage,
        gaps,
        pace_now,
    )
    privacy_findings = scan_forbidden({
        "events": token_events,
        "gaps": gaps,
        "capacity_snapshot": capacity_snapshot,
        "isolated_session_source_status": isolated_session_usage.get("source_status"),
        "isolated_gateway_usage": isolated_gateway_usage or {},
        "per_agent_usage": per_agent_usage,
        "fleet_reporting": fleet_reporting,
    })
    unsupported_model_events = [
        row for row in token_events
        if as_dict(row.get("model_support")).get("status") == "unsupported_legacy"
    ]
    supported_model_events = [
        row for row in token_events
        if as_dict(row.get("model_support")).get("active_route_countable") is True
    ]
    unsupported_model_gaps = [
        row for row in gaps
        if as_dict(row.get("model_support")).get("status") == "unsupported_legacy"
    ]
    supported_model_gaps = [
        row for row in gaps
        if as_dict(row.get("model_support")).get("active_route_countable") is True
    ]
    api_equivalent_rows = [row for row in token_events if row.get("api_equivalent_cost_usd") is not None]
    credit_estimate_rows = [row for row in token_events if row.get("estimated_chatgpt_credits") is not None]
    credit_standard_speed_assumed_rows = [
        row for row in credit_estimate_rows
        if row.get("chatgpt_credit_speed_assumption") == "standard_speed_assumed"
    ]
    credit_packet_oauth_assumed_rows = [
        row for row in credit_estimate_rows
        if row.get("chatgpt_credit_access_assumption") == "packet_oauth_mode_assumed"
    ]
    api_equivalent_total = round(sum(float(row.get("api_equivalent_cost_usd") or 0) for row in api_equivalent_rows), 6) if api_equivalent_rows else None
    chatgpt_credit_total = round(sum(float(row.get("estimated_chatgpt_credits") or 0) for row in credit_estimate_rows), 6) if credit_estimate_rows else None
    actual_billing = actual_billed_cost_from_policy(oauth_policy)
    rolling_5h = usage_window_summary(token_events, pace_now, 5.0)
    rolling_7d = usage_window_summary(token_events, pace_now, 168.0)
    reliable_usage_timestamp_count = int(rolling_7d.get("reliable_usage_timestamp_event_count") or 0)
    usage_pace = {
        "rolling_5h": rolling_5h,
        "rolling_7d_observed": rolling_7d,
        "reliable_usage_timestamp_event_count": reliable_usage_timestamp_count,
        "usage_timestamp_coverage_percent": round(
            (reliable_usage_timestamp_count / len(token_events)) * 100.0, 4
        ) if token_events else 0.0,
        "provider_quota_inferred_from_tokens": False,
        "ingestion_timestamp_used_as_usage_time": False,
        # Separate weaker tier: keeps the trusted windows strict while preventing
        # recent activity from reading as zero when provider timestamps are sparse.
        "ingestion_observed_fallback": {
            "rolling_5h": ingestion_window_summary(token_events, pace_now, 5.0, first_ingested_at),
            "rolling_7d": ingestion_window_summary(token_events, pace_now, 168.0, first_ingested_at),
            "reason_trusted_windows_may_read_zero": (
                "Trusted pace windows accept only provider or lane usage timestamps; "
                "rows carrying just ledger-ingestion time are excluded by design."
            ),
            "authority": "visibility_only_not_provider_pace_quota_or_billing",
        },
    }
    summary = {
        "ledger_row_count": len(read_jsonl(ledger_path)) if append else len(all_events),
        "candidate_event_count": len(candidate_events),
        "appended_event_count": len(new_events),
        "token_event_count": len(token_events),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in token_events),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in token_events),
        "cached_input_tokens": sum(int(row.get("cached_input_tokens") or 0) for row in token_events),
        "cache_write_tokens": sum(int(row.get("cache_write_tokens") or 0) for row in token_events),
        "uncached_input_tokens": sum(int(row.get("uncached_input_tokens") or 0) for row in token_events if row.get("uncached_input_tokens") is not None),
        "uncached_input_token_rows": sum(1 for row in token_events if row.get("uncached_input_tokens") is not None),
        "input_token_semantics_counts": dict(sorted(Counter(str(row.get("input_token_semantics") or "unknown") for row in token_events).items())),
        "unknown_or_invalid_input_token_semantics_event_count": sum(
            1 for row in token_events if row.get("token_semantics_status") != "valid"
        ),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in token_events),
        "api_equivalent_cost_rows": len(api_equivalent_rows),
        "api_equivalent_cost_event_coverage_percent": round(
            (len(api_equivalent_rows) / len(token_events)) * 100.0, 4
        ) if token_events else 0.0,
        "api_equivalent_priced_tokens": sum(int(row.get("total_tokens") or 0) for row in api_equivalent_rows),
        "api_equivalent_cost_usd": api_equivalent_total,
        "api_equivalent_cost_usd_total": api_equivalent_total,
        "api_equivalent_estimate_status": (
            "unavailable" if not token_events or not api_equivalent_rows
            else "complete" if len(api_equivalent_rows) == len(token_events)
            else "partial_unknown_input_semantics_or_missing_rate"
        ),
        "estimated_cost_rows": len(api_equivalent_rows),
        "estimated_cost_total": api_equivalent_total,
        "estimated_cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd_total",
        "actual_billed_cost_usd": actual_billing["actual_billed_cost_usd"],
        "actual_billed_cost_known": actual_billing["actual_billed_cost_known"],
        "actual_billed_cost_source": actual_billing["actual_billed_cost_source"],
        "actual_billed_cost_billing_period_label": actual_billing["billing_period_label"],
        "actual_billed_cost_recorded_at_utc": actual_billing["recorded_at_utc"],
        "non_null_actual_billed_cost_event_count": sum(1 for row in token_events if row.get("actual_billed_cost_usd") is not None),
        "estimated_chatgpt_credit_rows": len(credit_estimate_rows),
        "chatgpt_credit_event_coverage_percent": round(
            (len(credit_estimate_rows) / len(token_events)) * 100.0, 4
        ) if token_events else 0.0,
        "chatgpt_credit_priced_tokens": sum(int(row.get("total_tokens") or 0) for row in credit_estimate_rows),
        "chatgpt_credit_standard_speed_assumed_event_count": len(credit_standard_speed_assumed_rows),
        "chatgpt_credit_packet_oauth_assumed_event_count": len(credit_packet_oauth_assumed_rows),
        "estimated_chatgpt_credits": chatgpt_credit_total,
        "estimated_chatgpt_credits_total": chatgpt_credit_total,
        "chatgpt_credit_estimate_status": (
            "unavailable" if not token_events or not credit_estimate_rows
            else "complete_standard_speed_assumed" if len(credit_estimate_rows) == len(token_events) and credit_standard_speed_assumed_rows
            else "complete" if len(credit_estimate_rows) == len(token_events)
            else "partial_separate_no_public_rate_or_missing_rate"
        ),
        "access_mode_counts": dict(sorted(Counter(str(row.get("access_mode") or "unknown") for row in token_events).items())),
        "speed_mode_counts": dict(sorted(Counter(str(row.get("speed_mode") or "unknown") for row in token_events).items())),
        "cron_token_event_count": sum(1 for row in token_events if row.get("cron_attributed")),
        "implementation_token_event_count": sum(1 for row in token_events if row.get("implementation_attributed")),
        "usage_creditable_event_count": len(creditable_events),
        "usage_uncredited_event_count": sum(1 for row in token_events if row.get("usage_creditable") is False),
        "usage_source_receipt_count": len(usage_receipts),
        "efficiency_eligible_main_accepted_parent_job_count": efficiency["eligible_main_accepted_parent_job_count"],
        "savings_claim_allowed": efficiency["savings_claim_allowed"],
        "savings_measurement_status": efficiency["status"],
        "ambiguous_lane_run_id_count": len(ambiguous_lane_run_ids),
        "ambiguous_coding_run_id_count": len(ambiguous_coding_run_ids),
        "configured_isolated_agent_count": len(CONFIGURED_ISOLATED_AGENT_IDS),
        "observed_isolated_agent_count": len({row.get("agent_id") for row in isolated_events if row.get("agent_id")}),
        "utilized_isolated_agent_count": sum(1 for row in per_agent_usage if row.get("utilized") is True),
        "isolated_agent_session_event_count": len(isolated_events),
        "isolated_agent_attribution_grade_event_count": sum(1 for row in isolated_events if row.get("attribution_grade") is True),
        "isolated_agent_pricing_grade_event_count": sum(1 for row in isolated_events if row.get("pricing_grade") is True),
        "isolated_agent_implementation_joined_event_count": sum(1 for row in isolated_events if row.get("implementation_attributed") is True),
        "isolated_agent_unmatched_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "unmatched"),
        "isolated_agent_ambiguous_join_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "ambiguous"),
        "isolated_agent_model_mismatch_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "model_mismatch"),
        "isolated_agent_agent_mismatch_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "agent_mismatch"),
        "isolated_agent_time_mismatch_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "time_mismatch"),
        "isolated_agent_identity_conflict_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "identity_conflict"),
        "isolated_agent_run_id_joined_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "joined_by_run_id"),
        "isolated_agent_session_ref_joined_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "joined_by_session_ref"),
        "isolated_agent_session_id_joined_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "joined_by_session_id"),
        "isolated_agent_session_key_joined_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "joined_by_session_key"),
        "isolated_agent_attempt_correlation_joined_event_count": sum(1 for row in isolated_events if row.get("lane_join_status") == "joined_by_attempt_correlation"),
        "isolated_agent_invalid_source_record_count": int(as_dict(isolated_session_usage.get("summary")).get("invalid_record_count") or 0),
        "isolated_agent_full_event_validation_error_count": len(isolated_event_validation_errors),
        "isolated_agent_noncreditable_observed_usage_count": len(isolated_event_validation_warnings),
        "isolated_gateway_usage_requested": isolated_gateway_usage is not None,
        "isolated_gateway_usage_ok_agent_count": int(as_dict(as_dict(isolated_gateway_usage).get("summary")).get("ok_agent_count") or 0),
        "isolated_gateway_usage_blocked_agent_count": int(as_dict(as_dict(isolated_gateway_usage).get("summary")).get("blocked_agent_count") or 0),
        "isolated_gateway_pricing_grade_agent_count": int(as_dict(as_dict(isolated_gateway_usage).get("summary")).get("pricing_grade_agent_count") or 0),
        "implementation_token_gap_count": len(gaps),
        "supported_implementation_token_gap_count": len(supported_model_gaps),
        "unsupported_legacy_implementation_token_gap_count": len(unsupported_model_gaps),
        "supported_model_token_event_count": len(supported_model_events),
        "unsupported_legacy_model_token_event_count": len(unsupported_model_events),
        "unique_cron_job_count": len({row.get("cron_job_name") for row in token_events if row.get("cron_job_name")}),
        "unique_model_count": len({row.get("model_path") for row in token_events if row.get("model_path")}),
        "unique_supported_model_count": len({row.get("model_path") for row in supported_model_events if row.get("model_path")}),
        "unsupported_legacy_model_paths": sorted({
            str(row.get("model_path")) for row in token_events + gaps
            if as_dict(row.get("model_support")).get("status") == "unsupported_legacy" and row.get("model_path")
        }),
        "privacy_scan_status": "ok" if not privacy_findings else "blocked",
        "pricing_status": "loaded" if pricing else "missing_pricing_table",
        "reliable_usage_timestamp_event_count": reliable_usage_timestamp_count,
        "usage_timestamp_coverage_percent": usage_pace["usage_timestamp_coverage_percent"],
    }
    oauth_capacity_control = compute_oauth_capacity_control(oauth_policy, capacity_snapshot, now=now)
    billing_semantics = {
        "billing_mode": "oauth_subscription",
        "api_equivalent_cost_usd": api_equivalent_total,
        "api_equivalent_cost_label": "API-equivalent benchmark",
        "api_equivalent_is_not_invoice": True,
        "api_equivalent_cost_is_invoice": False,
        "api_equivalent_is_not_invoice": True,
        "api_equivalent_estimate_status": summary["api_equivalent_estimate_status"],
        "api_equivalent_cost_explanation": "Public API token-rate benchmark only; it is not an invoice or actual billed cost under OAuth subscription access.",
        "legacy_aliases": {
            "estimated_cost": "deprecated_alias_of_api_equivalent_cost_usd",
            "estimated_cost_total": "deprecated_alias_of_api_equivalent_cost_usd_total",
        },
        "actual_billed_cost_usd": actual_billing["actual_billed_cost_usd"],
        "actual_billed_cost_known": actual_billing["actual_billed_cost_known"],
        "actual_billed_cost_source": actual_billing["actual_billed_cost_source"],
        "actual_billed_cost_provenance": {
            "billing_period_label": actual_billing["billing_period_label"],
            "recorded_at_utc": actual_billing["recorded_at_utc"],
            "source": actual_billing["actual_billed_cost_source"],
        },
        "actual_billed_cost_inference_allowed": False,
        "actual_billed_cost_is_inferred": False,
        "platform_billing_api_queried": False,
        "estimated_chatgpt_credits": chatgpt_credit_total,
        "credit_estimate_is_not_observed_debit": True,
        "chatgpt_credit_estimate_status": summary["chatgpt_credit_estimate_status"],
        "credit_estimate_is_not_observed_debit": True,
        "chatgpt_credit_speed_mode_observed": False if credit_standard_speed_assumed_rows else True,
        "chatgpt_credit_standard_speed_assumed_event_count": len(credit_standard_speed_assumed_rows),
        "chatgpt_credit_packet_oauth_assumed_event_count": len(credit_packet_oauth_assumed_rows),
        "chatgpt_credit_estimate_explanation": "Token-based estimate from official ChatGPT credit rates where published; explicit API-key events remain null, event-level unknown access relies on the owner-declared packet OAuth mode, separate models without a public credit rate remain null, fast mode fails closed, and unknown speed is explicitly labeled as a standard-speed assumption.",
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Metadata-only token usage ledger with OAuth-aware benchmark, ChatGPT credit, and advisory capacity context.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "billing_semantics": billing_semantics,
        "oauth_capacity_control": oauth_capacity_control,
        "usage_pace": usage_pace,
        "ledger_path": rel(ledger_path),
        "source_status": [
            source_status(MODEL_RUN_LEDGER),
            source_status(LANE_REGISTER),
            source_status(CODING_OUTCOME),
            source_status(PRICING),
            source_status(policy_path),
            source_status(capacity_path),
        ],
        "isolated_agent_session_source_status": isolated_session_usage.get("source_status"),
        "isolated_agent_gateway_usage_cost": isolated_gateway_usage or {
            "status": "not_requested",
            "metadata_only": True,
        },
        "per_agent_usage": per_agent_usage,
        "fleet_reporting": fleet_reporting,
        "efficiency_measurement": efficiency,
        "isolated_agent_event_validation": {
            "status": (
                "ok"
                if not isolated_event_validation_findings
                else "warning"
                if not isolated_event_validation_errors
                else "blocked"
            ),
            "finding_count": len(isolated_event_validation_findings),
            "critical_count": len(isolated_event_validation_errors),
            "warning_count": len(isolated_event_validation_warnings),
            "findings": isolated_event_validation_findings,
        },
        "summary": summary,
        "top_cron_jobs_by_tokens": aggregate([row for row in token_events if row.get("cron_job_name")], "cron_job_name")[:15],
        "top_models_by_tokens": aggregate([row for row in token_events if row.get("model_path")], "model_path")[:15],
        "top_supported_models_by_tokens": aggregate([row for row in supported_model_events if row.get("model_path")], "model_path")[:15],
        "unsupported_legacy_model_events": unsupported_model_events[:25],
        "top_statuses_by_tokens": aggregate(token_events, "status")[:10],
        "top_token_events": token_events[:25],
        "implementation_token_gaps": gaps[:25],
        "recommendations": recommendations(summary, token_events, gaps),
        "next_safe_action": "Use top_supported_models_by_tokens for current supported-capacity views; keep top_models_by_tokens as historical/all-model audit context.",
        "blocked_actions": [
            "no raw prompt/response/tool payload capture",
            "no invoice or actual-billed-cost claim from API-equivalent benchmarks",
            "no cost claim without local pricing table",
            "no automatic quota throttling from missing or stale capacity data",
            "no credit purchase or overage without explicit owner approval",
            "no model ranking from token usage alone",
            "no cron schedule or runtime mutation from this ledger",
            "no finance/capital/execution authority",
        ],
        "privacy_scan": {
            "status": "ok" if not privacy_findings else "blocked",
            "finding_count": len(privacy_findings),
            "findings": privacy_findings,
        },
        "_input_fingerprint": _input_fingerprint(
            ledger_path, policy_path, capacity_path
        ),
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload, new_events


def recommendations(summary: dict[str, Any], events: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    if summary.get("pricing_status") != "loaded":
        recs.append({
            "id": "add_local_pricing_table",
            "severity": "info",
            "decision": "prepare_local_pricing_table",
            "next_action": "Add a local model-token-pricing table before making dollar-cost claims.",
        })
    supported_gap_count = int(summary.get("supported_implementation_token_gap_count") or 0)
    if supported_gap_count:
        recs.append({
            "id": "implementation_token_attribution_gap",
            "severity": "warning",
            "decision": "stamp_token_usage_into_implementation_lanes",
            "next_action": "Extend completed lane/coding outcome records with token usage or a matching provider run_id.",
            "gap_count": supported_gap_count,
        })
    unsupported_gap_count = int(summary.get("unsupported_legacy_implementation_token_gap_count") or 0)
    if unsupported_gap_count:
        recs.append({
            "id": "unsupported_legacy_model_gap_quarantined",
            "severity": "info",
            "decision": "keep_legacy_unsupported_rows_out_of_supported_capacity",
            "next_action": "Leave unsupported legacy model rows auditable, but do not count them as supported model capacity.",
            "gap_count": unsupported_gap_count,
        })
    if events:
        top = events[0]
        recs.append({
            "id": "review_top_token_cron_job",
            "severity": "info",
            "decision": "review_changed_only_or_cadence_candidate",
            "next_action": f"Review {top.get('cron_job_name') or top.get('source_run_id')} for changed-only mode, shorter prompt, or cadence reduction if value is low.",
            "total_tokens": top.get("total_tokens"),
        })
    return recs


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    summary = as_dict(payload.get("summary"))
    billing = as_dict(payload.get("billing_semantics"))
    efficiency = as_dict(payload.get("efficiency_measurement"))
    if efficiency:
        if efficiency.get("savings_claim_allowed") is not False or summary.get("savings_claim_allowed") is not False:
            errors.append("savings claims require an explicit comparable-baseline contract")
        if efficiency.get("baseline_configured") is not False:
            errors.append("unreviewed efficiency baseline must not be enabled")
    if billing.get("billing_mode") != "oauth_subscription":
        errors.append("billing semantics must remain oauth_subscription")
    actual_billed = billing.get("actual_billed_cost_usd")
    actual_source = billing.get("actual_billed_cost_source")
    if actual_billed is not None and actual_source != "owner_entered":
        errors.append("OAuth actual billed cost must not be inferred")
    if billing.get("actual_billed_cost_inference_allowed") is not False:
        errors.append("OAuth actual billed cost inference must remain disabled")
    if billing.get("actual_billed_cost_is_inferred") is not False:
        errors.append("OAuth actual billed cost inferred flag must remain false")
    if billing.get("platform_billing_api_queried") is not False:
        errors.append("Platform billing API queried flag must remain false")
    if billing.get("actual_billed_cost_known") != (actual_billed is not None):
        errors.append("OAuth actual billed cost known flag is inconsistent")
    if billing.get("api_equivalent_cost_is_invoice") is not False:
        errors.append("API-equivalent cost must not be classified as an invoice")
    if billing.get("api_equivalent_is_not_invoice") is not True:
        errors.append("API-equivalent non-invoice guard alias must remain true")
    if billing.get("credit_estimate_is_not_observed_debit") is not True:
        errors.append("ChatGPT credit estimate must not be classified as an observed debit")
    if summary.get("estimated_cost_total") != summary.get("api_equivalent_cost_usd_total"):
        errors.append("legacy estimated_cost_total must equal API-equivalent benchmark alias")
    if int(summary.get("non_null_actual_billed_cost_event_count") or 0) > 0:
        errors.append("token events contain a non-null OAuth actual billed cost")
    for event in as_list(payload.get("top_token_events")):
        if not isinstance(event, dict):
            continue
        if event.get("estimated_cost") != event.get("api_equivalent_cost_usd"):
            errors.append(f"legacy estimated_cost alias mismatch: {event.get('event_id')}")
        if (event.get("input_token_semantics_valid") is not True or event.get("token_semantics_status") != "valid") and (
            event.get("api_equivalent_cost_usd") is not None or event.get("estimated_chatgpt_credits") is not None
        ):
            errors.append(f"ambiguous input token semantics produced a benchmark estimate: {event.get('event_id')}")
        delta = as_int(event.get("token_total_delta"))
        tolerance = as_int(event.get("token_total_tolerance_tokens"))
        if delta is not None and tolerance is not None and abs(delta) > tolerance and (
            event.get("api_equivalent_cost_usd") is not None or event.get("estimated_chatgpt_credits") is not None
        ):
            errors.append(f"inconsistent token total produced a benchmark estimate: {event.get('event_id')}")
        if event.get("actual_billed_cost_usd") is not None:
            errors.append(f"OAuth account-level actual billed cost must not be attributed to an event: {event.get('event_id')}")
    control = as_dict(payload.get("oauth_capacity_control"))
    control_policy = as_dict(control.get("policy"))
    policy_errors = validate_oauth_policy(control_policy)
    errors.extend(policy_errors)
    policy_actual = actual_billed_cost_from_policy(control_policy)
    if billing.get("actual_billed_cost_usd") != policy_actual.get("actual_billed_cost_usd"):
        errors.append("billing actual-cost amount does not match owner-entered policy provenance")
    if billing.get("actual_billed_cost_source") != policy_actual.get("actual_billed_cost_source"):
        errors.append("billing actual-cost source does not match owner-entered policy provenance")
    if summary.get("actual_billed_cost_usd") != billing.get("actual_billed_cost_usd"):
        errors.append("summary actual billed cost does not match billing semantics")
    allowed_states = {"unavailable", "stale", "normal", "reduce_routine", "pause_noncritical", "urgent_only"}
    if control.get("state") not in allowed_states:
        errors.append("OAuth capacity control state is invalid")
    if control.get("tier") != control.get("quota_tier"):
        errors.append("OAuth capacity tier alias mismatch")
    expected_control_status = "current" if control.get("state") in {"normal", "reduce_routine", "pause_noncritical", "urgent_only"} else control.get("state")
    if control.get("status") != expected_control_status:
        errors.append("OAuth capacity status alias mismatch")
    if control.get("days_until_reset") != control.get("days_to_reset") or control.get("reset_days") != control.get("days_to_reset"):
        errors.append("OAuth reset-day alias mismatch")
    if control.get("daily_burn_guidance") != control.get("max_daily_percentage_point_burn_preserving_reserve"):
        errors.append("OAuth daily-burn alias mismatch")
    if control.get("automatic_action_allowed") is not False:
        errors.append("OAuth automatic quota action must remain disabled")
    if control.get("throttling_authorized") is not False:
        errors.append("OAuth capacity control must remain advisory and non-authorizing")
    snapshot_status = control.get("snapshot_status")
    snapshot_errors = as_list(as_dict(control.get("snapshot_validation")).get("errors"))
    if snapshot_status == "invalid" or snapshot_errors:
        errors.extend(f"capacity snapshot invalid: {item}" for item in snapshot_errors)
    elif control.get("state") in {"unavailable", "stale"}:
        warnings.append("OAuth capacity is missing or stale; quota action remains unknown and unauthorized")
        if control.get("capacity_known") is not False:
            errors.append("missing or stale OAuth capacity must not be treated as known")
    if summary.get("privacy_scan_status") != "ok":
        errors.append("privacy scan not ok")
    isolated_validation = as_dict(payload.get("isolated_agent_event_validation"))
    isolated_session_count = int(summary.get("isolated_agent_session_event_count") or 0)
    if (
        isolated_session_count > 0
        or "isolated_agent_event_validation" in payload
    ) and (
        isolated_validation.get("status") == "blocked"
        or int(summary.get("isolated_agent_full_event_validation_error_count") or 0) > 0
    ):
        errors.append("isolated agent full-event validation not ok")
    if isolated_validation.get("status") == "warning":
        warnings.append("isolated agent session usage observed but not deterministically creditable")
    if int(summary.get("isolated_agent_invalid_source_record_count") or 0) > 0:
        warnings.append("invalid/stale isolated session metadata was rejected and excluded")
    if int(summary.get("isolated_agent_ambiguous_join_event_count") or 0) > 0:
        warnings.append("some isolated session events have ambiguous lane joins")
    if int(summary.get("isolated_agent_model_mismatch_event_count") or 0) > 0:
        warnings.append("some isolated session events disagree with lane model metadata")
    if summary.get("isolated_gateway_usage_requested") is True and int(summary.get("isolated_gateway_usage_blocked_agent_count") or 0) > 0:
        warnings.append("Gateway usage-cost reporting failed closed for one or more isolated agents")
    if int(summary.get("token_event_count") or 0) <= 0:
        warnings.append("no token-bearing rows found")
    event_count = int(summary.get("token_event_count") or 0)
    api_rows = int(summary.get("api_equivalent_cost_rows") or 0)
    credit_rows = int(summary.get("estimated_chatgpt_credit_rows") or 0)
    if api_rows > event_count or credit_rows > event_count:
        errors.append("priced event coverage exceeds token event count")
    if api_rows < event_count and summary.get("api_equivalent_estimate_status") == "complete":
        errors.append("partial API-equivalent coverage is marked complete")
    if credit_rows < event_count and summary.get("chatgpt_credit_estimate_status") == "complete":
        errors.append("partial ChatGPT-credit coverage is marked complete")
    if int(summary.get("unknown_or_invalid_input_token_semantics_event_count") or 0) > 0:
        warnings.append("some legacy token rows have unknown or invalid input-token semantics; API-equivalent and credit estimates are null for those rows")
    if summary.get("pricing_status") != "loaded":
        warnings.append("pricing table missing; cost estimates disabled")
    usage_pace = as_dict(payload.get("usage_pace"))
    if usage_pace.get("provider_quota_inferred_from_tokens") is not False:
        errors.append("provider quota must not be inferred from token pace")
    if usage_pace.get("ingestion_timestamp_used_as_usage_time") is not False:
        errors.append("ingestion timestamp must not be used as usage time")
    for window_name in ("rolling_5h", "rolling_7d_observed"):
        window = as_dict(usage_pace.get(window_name))
        if window.get("ingestion_timestamp_used_as_usage_time") is not False:
            errors.append(f"{window_name} uses ingestion time as usage time")
    if any(key not in {"chatgpt", "apikey", "unknown"} for key in as_dict(summary.get("access_mode_counts"))):
        errors.append("unsupported access mode present in token events")
    if any(key not in {"standard", "fast", "unknown"} for key in as_dict(summary.get("speed_mode_counts"))):
        errors.append("unsupported speed mode present in token events")
    if int(summary.get("unsupported_legacy_model_token_event_count") or 0) > 0:
        warnings.append("unsupported legacy model has token events; treat as historical audit until active-route proof is inspected")
    return {"status": "critical" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    billing = as_dict(payload.get("billing_semantics"))
    capacity = as_dict(payload.get("oauth_capacity_control"))
    usage_pace = as_dict(payload.get("usage_pace"))
    rolling_5h = as_dict(usage_pace.get("rolling_5h"))
    rolling_7d = as_dict(usage_pace.get("rolling_7d_observed"))
    api_equivalent = as_float(billing.get("api_equivalent_cost_usd"))
    credits = as_float(billing.get("estimated_chatgpt_credits"))
    actual_billed = as_float(billing.get("actual_billed_cost_usd"))
    api_label = f"${api_equivalent:.6f}" if api_equivalent is not None else "unknown"
    credit_label = f"{credits:.6f}" if credits is not None else "unknown"
    actual_provenance = as_dict(billing.get("actual_billed_cost_provenance"))
    actual_label = (
        f"${actual_billed:.2f} (owner entered; period {actual_provenance.get('billing_period_label')})"
        if actual_billed is not None
        else "unknown (not inferred from token usage)"
    )
    lines = [
        "# Token Usage Ledger Current",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Token events: {summary.get('token_event_count')}",
        f"- Total tokens: {summary.get('total_tokens')}",
        f"- Input/output tokens: {summary.get('input_tokens')} / {summary.get('output_tokens')}",
        f"- Unknown/invalid input-token semantics events: {summary.get('unknown_or_invalid_input_token_semantics_event_count')}",
        f"- Cron token events: {summary.get('cron_token_event_count')}",
        f"- Implementation token events/gaps: {summary.get('implementation_token_event_count')} / {summary.get('implementation_token_gap_count')}",
        f"- Supported implementation token gaps: {summary.get('supported_implementation_token_gap_count')}",
        f"- Unsupported legacy implementation token gaps: {summary.get('unsupported_legacy_implementation_token_gap_count')}",
        f"- Pricing status: {summary.get('pricing_status')}",
        f"- API-equivalent benchmark: {api_label} ({billing.get('api_equivalent_estimate_status')}; {summary.get('api_equivalent_cost_rows')}/{summary.get('token_event_count')} events priced, {summary.get('api_equivalent_cost_event_coverage_percent')}%; not an invoice under OAuth)",
        f"- Actual billed cost: {actual_label}",
        f"- Estimated ChatGPT credits: {credit_label} ({billing.get('chatgpt_credit_estimate_status')}; {summary.get('estimated_chatgpt_credit_rows')}/{summary.get('token_event_count')} events priced, {summary.get('chatgpt_credit_event_coverage_percent')}%; not an observed debit)",
        f"- Credit speed caveat: standard speed assumed for {summary.get('chatgpt_credit_standard_speed_assumed_event_count')} priced events where speed was unobserved",
        f"- Credit access caveat: owner-declared packet OAuth assumed for {summary.get('chatgpt_credit_packet_oauth_assumed_event_count')} priced events where event access mode was unobserved",
        f"- Quota tier: {capacity.get('quota_tier')} (advisory only; automatic action allowed=false)",
        f"- Days to reset: {capacity.get('days_to_reset')}",
        f"- Max daily percentage-point burn preserving reserve: {capacity.get('max_daily_percentage_point_burn_preserving_reserve')}",
        f"- Rolling 5h observed tokens: {rolling_5h.get('total_tokens')} across {rolling_5h.get('event_count')} reliably timestamped events",
        f"- Rolling 7d observed tokens: {rolling_7d.get('total_tokens')} across {rolling_7d.get('event_count')} reliably timestamped events",
        f"- Reliable usage timestamp coverage: {usage_pace.get('usage_timestamp_coverage_percent')}% (ingestion time is not used)",
        "",
        "## Top Cron Jobs By Tokens",
    ]
    for row in payload.get("top_cron_jobs_by_tokens", [])[:10]:
        lines.append(f"- {row.get('cron_job_name')}: {row.get('total_tokens')} tokens across {row.get('count')} runs")
    lines.extend(["", "## Recommendations"])
    for rec in payload.get("recommendations", []):
        lines.append(f"- {rec.get('id')}: {rec.get('next_action')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build metadata-only token usage ledger.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--ledger-out", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--record-remaining-percent", type=float)
    parser.add_argument("--record-reset-hours", type=float)
    parser.add_argument("--record-source-label")
    parser.add_argument("--record-window-label")
    parser.add_argument("--capacity-current-out", type=Path, default=OAUTH_CAPACITY_CURRENT)
    parser.add_argument("--capacity-history-out", type=Path, default=OAUTH_CAPACITY_HISTORY)
    parser.add_argument("--isolated-agent-usage-days", type=int, default=8, help="Gateway usage-cost reporting window (current day plus seven closed days).")
    parser.add_argument("--skip-isolated-agent-usage-cost", action="store_true", help="Skip the read-only Gateway usage-cost reporting input.")
    args = parser.parse_args()

    recording_values = (
        args.record_remaining_percent,
        args.record_reset_hours,
        args.record_source_label,
        args.record_window_label,
    )
    recording_requested = any(value is not None for value in recording_values)
    if recording_requested and not all(value is not None for value in recording_values):
        parser.error("capacity recording requires --record-remaining-percent, --record-reset-hours, --record-source-label, and --record-window-label together")
    if recording_requested and not args.write:
        parser.error("capacity recording requires --write")
    capacity_history_appended = False
    if recording_requested:
        try:
            _, capacity_history_appended = record_capacity_snapshot(
                args.record_remaining_percent,
                args.record_reset_hours,
                args.record_source_label,
                args.record_window_label,
                current_path=args.capacity_current_out,
                history_path=args.capacity_history_out,
            )
        except ValueError as exc:
            parser.error(str(exc))

    isolated_gateway_usage = None
    if not args.skip_isolated_agent_usage_cost:
        isolated_gateway_usage = load_gateway_usage_cost(
            CONFIGURED_ISOLATED_AGENT_IDS,
            days=args.isolated_agent_usage_days,
        )

    payload: dict[str, Any] | None = None
    new_events: list[dict[str, Any]] = []
    if args.write:
        payload = _try_fast_path(
            args.json_out,
            args.ledger_out,
            policy_path=OAUTH_POLICY,
            capacity_path=args.capacity_current_out,
        )
    if payload is None:
        payload, new_events = build_payload(
            args.ledger_out,
            append=args.write,
            capacity_path=args.capacity_current_out,
            isolated_gateway_usage=isolated_gateway_usage,
        )
    if args.write:
        atomic_write_json(args.json_out, payload)
        if args.write_md:
            atomic_write_text(args.md_out, render_md(payload))
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
        f"events={summary.get('token_event_count')} total_tokens={summary.get('total_tokens')} "
        f"appended={len(new_events)} pricing={summary.get('pricing_status')} "
        f"quota={as_dict(payload.get('oauth_capacity_control')).get('quota_tier')} "
        f"capacity_history_appended={str(capacity_history_appended).lower()}"
    )
    for error in as_dict(payload.get("validation")).get("errors", []):
        print(f"  [critical] {error}")
    for warning in as_dict(payload.get("validation")).get("warnings", []):
        print(f"  [warning] {warning}")
    if args.validate and as_dict(payload.get("validation")).get("status") == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
