#!/usr/bin/env python3
"""MVP concurrent lane lease manager.

This is a small anti-collision register for parallel workflow/helper lanes. It
does not spawn helpers, schedule work, mutate canon/portfolio state, infer owner
approval, or grant execution authority. It records planned/leased/running/
complete lanes and validates that active lanes do not write the same surfaces.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from lib.terminal_outcome import (
    CLOSURE_DURABILITY_STATES,
    VALIDATOR_RESULTS,
)
from isolated_agent_usage_metadata import (
    CONFIGURED_ISOLATED_AGENT_IDS,
    DEFAULT_AGENT_STATE_ROOT,
    DEFAULT_OPENCLAW_STATE_DB,
    build_attempt_correlation_key,
    dispatch_binding_token_hash_for_attempt,
    find_session_usage_record,
    hash_reference,
    load_allowlisted_session_usage,
    load_verified_isolated_session_usage_for_binding,
    task_name_for_attempt,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTER = TMP / "concurrent-lane-register.json"
WORKFLOW_INDEX = TMP / "workflow-routing-index.json"
SHADOW_PILOT_ERROR = TMP / "wf73-postgres-shadow-pilot-metrics.json"
SCHEMA = "veritas.concurrent_lane_register.v1"
ACTIVE_LEASE_ADMISSION_SCHEMA = "veritas.concurrent_lane_active_lease_admission.v1"
USAGE_SOURCE_RECEIPTS_SCHEMA = "veritas.model_usage_source_receipts.v1"
USAGE_SOURCE_REVERIFICATION_CONTRACT_VERSION = "veritas.model_usage_source_reverification.v1"
USAGE_SOURCE_BINDING_CONTRACT_VERSION = "veritas.usage_source_binding.v2"
DISPATCH_TASK_NAME_SCHEMA = "veritas.isolated_dispatch_task_name.v1"

ACTIVE_STATUSES = {"planned", "leased", "running"}
VALID_STATUSES = ACTIVE_STATUSES | {"complete", "blocked", "cancelled"}
TERMINAL_STATUSES = {"complete", "blocked", "cancelled"}
DEFAULT_LEASE_HOURS = 6
TOKEN_STAMPING_ENFORCEMENT_START_UTC = "2026-06-27T00:00:00Z"
TOKEN_CLOSEOUT_GUARD_START_UTC = "2026-07-03T19:30:00Z"
TOKEN_CLOSEOUT_HARD_ENFORCEMENT_START_UTC = "2026-07-07T00:00:00Z"
ATTRIBUTION_GRADE_ALL_LANES_ENFORCEMENT_START_UTC = "2026-08-09T00:00:00Z"
EFFICIENCY_ENFORCEMENT_START_UTC = "2026-08-12T05:46:00Z"
IDENTITY_METADATA_HARD_ENFORCEMENT_START_UTC = "2026-08-22T15:42:23Z"
# The terminal ledger contains valid bounded outcome summaries from before the
# append-only ``outcome_events`` list was durably materialized.  The last such
# retained closeout is 2026-08-26T13:57:13Z.  Keep those rows visible without
# inventing history; every event at or after this boundary must carry the list.
OUTCOME_EVENT_HISTORY_HARD_ENFORCEMENT_START_UTC = "2026-08-26T13:57:14Z"
# Proof files were not governed by an immutable-retention contract before the
# Wave 1 identity cutover.  Missing older paths remain explicit audit debt;
# newer completed lanes continue to fail closed.
PROOF_ARTIFACT_EXISTENCE_HARD_ENFORCEMENT_START_UTC = IDENTITY_METADATA_HARD_ENFORCEMENT_START_UTC
# New model work must have a deterministic source-to-lane join.  Older rows
# remain visible for audit but are never silently upgraded into a savings
# cohort by this change.
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"
MODEL_USAGE_CREDIT_CONTRACT_VERSION = "veritas.model_usage_credit.v2"
TRUSTED_TOKEN_ATTRIBUTION_SOURCES = {
    "codex_native_rollout_jsonl",
    "openclaw_isolated_session_store_v1",
    "openclaw_isolated_session_store_v2",
}
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")
COMPLETE_TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "output_tokens",
    "total_tokens",
)
IMPLEMENTATION_PHASES = {"implementation", "build", "integration", "repair", "refactor"}
# 2026-09-18 Phase 2 (owner-directed): shared definition lives in
# scripts/token_usage_classifications.py. This consumer is the STRICT closeout
# gate: no lane may close on manual or self-declared totals.
from token_usage_classifications import CLOSEOUT_GATE_MISSING_USAGE_CLASSIFICATIONS
ACCEPTED_MISSING_USAGE_CLASSIFICATIONS = set(CLOSEOUT_GATE_MISSING_USAGE_CLASSIFICATIONS)
NEW_ISOLATED_MISSING_USAGE_CLASSIFICATIONS = {"provider_usage_unavailable"}
USAGE_UNAVAILABLE_REASONS = {
    "current_main_session_counters_not_job_scoped",
    "fork_baseline_unavailable",
    "isolated_session_record_unavailable",
    "provider_counters_not_exposed",
    "rollout_schema_unsupported",
    "session_not_terminal",
}
FORK_POLICIES = {"none", "recent", "all", "unknown"}
DEFAULT_RESOURCE_BUDGETS = {
    "audit": {"gross_tokens": 750_000, "cached_replay_tokens": 600_000, "tool_calls": 24, "elapsed_seconds": 1_800},
    "qa": {"gross_tokens": 1_000_000, "cached_replay_tokens": 800_000, "tool_calls": 32, "elapsed_seconds": 2_400},
    "implementation": {"gross_tokens": 1_500_000, "cached_replay_tokens": 1_200_000, "tool_calls": 48, "elapsed_seconds": 3_600},
    "default": {"gross_tokens": 1_000_000, "cached_replay_tokens": 800_000, "tool_calls": 32, "elapsed_seconds": 2_400},
}
HARD_RESOURCE_CEILINGS = {
    "gross_tokens": 4_000_000,
    "cached_replay_tokens": 3_500_000,
    "tool_calls": 80,
    "elapsed_seconds": 7_200,
}
OUTCOME_EVENT_KINDS = {"incident", "terminal_closeout", "main_acceptance_update"}
OUTCOME_UTC_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
)
INCIDENT_CODES = {
    "blocked_dependency",
    "cancelled_by_owner",
    "context_budget_exceeded",
    "context_overflow",
    "handoff_integrity_failed",
    "handoff_preflight_failed",
    "packaging_path_error",
    "provider_error",
    "qa_reject",
    "sla_breach",
    "timeout",
    "token_budget_exceeded",
    "cached_replay_budget_exceeded",
    "tool_loop_budget_exceeded",
    "elapsed_budget_exceeded",
    "rework_cap_exceeded",
    "unknown",
    "validation_failure",
    "telemetry_attribution_unavailable",
}
OUTCOME_REFRESH_SLA_SECONDS = 90
# Parser/import compatibility default only.  It is never eligible to establish
# credit: re-verification below anchors to the physical runtime adjacent to
# this installed workspace, not a HOME/USERPROFILE-derived location.
DEFAULT_CODEX_SESSIONS_ROOT = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "codex-home" / "sessions"
CODEX_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
V2_CANONICAL_SOURCE_FIELDS = (
    "run_id",
    "agent_role",
    "model_provider",
    "usage_at_utc",
    "usage_time_source",
)
ROUTE_MODEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}")
ROUTE_THINKING_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
ROUTE_PROVIDER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
ROOT_LINEAGE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
SLICE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
TECHNICAL_ACCEPTANCE_STATUSES = {"pending", "accepted", "rejected"}
ACCOUNTING_STATUSES = {"pending", "credited", "blocked", "unavailable"}
ADMIN_CLOSURE_STATUSES = {"open", "blocked", "closed"}
ACTIVATION_STATUSES = {"blocked", "ready"}
FOUR_STATE_DEFAULTS = {
    "technical_acceptance_status": "pending",
    "accounting_status": "pending",
    "administrative_closure_status": "open",
    "activation_status": "blocked",
}


def normalize_lineage_id(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise SystemExit(f"{field} must be a non-empty identifier")
    if not ROOT_LINEAGE_ID_PATTERN.fullmatch(text):
        raise SystemExit(f"invalid {field}")
    return text


def normalize_slice_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise SystemExit("objective_slice_id must be a non-empty identifier")
    if not SLICE_ID_PATTERN.fullmatch(text):
        raise SystemExit("invalid objective_slice_id")
    return text


def normalize_four_state(value: object, allowed: set[str], field: str, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if text not in allowed:
        raise SystemExit(f"invalid {field}")
    return text


def normalize_root_lineage_fields(runtime: dict[str, Any]) -> None:
    has_root = str(runtime.get("root_objective_id") or "").strip() != ""
    has_slice = str(runtime.get("objective_slice_id") or "").strip() != ""
    has_pred = str(runtime.get("predecessor_lane_id") or "").strip() != ""
    has_cum = runtime.get("cumulative_attempt_number") not in (None, "") or runtime.get("cumulative_retry_count") not in (None, "")
    has_accepted = str(runtime.get("accepted_slice_id") or "").strip() != ""
    if has_root:
        runtime["root_objective_id"] = normalize_lineage_id(runtime.get("root_objective_id"), "root_objective_id")
    if has_slice:
        runtime["objective_slice_id"] = normalize_slice_id(runtime.get("objective_slice_id"))
    if has_root != has_slice:
        raise SystemExit("root_objective_id and objective_slice_id must be supplied together")
    if has_pred and not has_root:
        raise SystemExit("predecessor_lane_id requires root_objective_id and objective_slice_id")
    if has_cum and not has_root:
        raise SystemExit("cumulative counters require root_objective_id and objective_slice_id")
    if has_root and has_pred:
        runtime["predecessor_lane_id"] = normalize_lineage_id(runtime.get("predecessor_lane_id"), "predecessor_lane_id")
    for field, allowed in (
        ("technical_acceptance_status", TECHNICAL_ACCEPTANCE_STATUSES),
        ("accounting_status", ACCOUNTING_STATUSES),
        ("administrative_closure_status", ADMIN_CLOSURE_STATUSES),
        ("activation_status", ACTIVATION_STATUSES),
    ):
        runtime[field] = normalize_four_state(runtime.get(field), allowed, field, FOUR_STATE_DEFAULTS[field])
    for field, minimum in (("cumulative_attempt_number", 1), ("cumulative_retry_count", 0)):
        if runtime.get(field) not in (None, ""):
            parsed = strict_attempt_int(runtime.get(field), minimum=minimum)
            if parsed is None:
                raise SystemExit(f"{field} must be an integer greater than or equal to {minimum}")
            runtime[field] = parsed
    if has_accepted:
        runtime["accepted_slice_id"] = normalize_slice_id(runtime.get("accepted_slice_id"))
        if runtime.get("technical_acceptance_status") != "accepted":
            raise SystemExit("accepted_slice_id is present only when technical_acceptance_status is accepted")
    if runtime.get("cumulative_attempt_number") not in (None, "") and runtime.get("cumulative_retry_count") not in (None, ""):
        if int(runtime["cumulative_attempt_number"]) != int(runtime["cumulative_retry_count"]) + 1:
            raise SystemExit("cumulative_attempt_number must equal cumulative_retry_count + 1")


def root_slice_key(runtime: dict[str, Any]) -> tuple[str, str] | None:
    root = str(runtime.get("root_objective_id") or "").strip()
    sl = str(runtime.get("objective_slice_id") or "").strip()
    if root and sl:
        return (root, sl)
    return None


def rework_group_key(runtime: dict[str, Any]) -> tuple[str, str]:
    key = root_slice_key(runtime)
    if key is not None:
        return (f"root:{key[0]}", f"slice:{key[1]}")
    return ("parent", str(runtime.get("parent_job_id") or ""))


def find_lane_by_id(register: dict[str, Any], lane_id: str) -> dict[str, Any] | None:
    for item in as_list(register.get("lanes")):
        if isinstance(item, dict) and str(item.get("lane_id") or "") == lane_id:
            return item
    return None


def validate_root_lineage(register: dict[str, Any], lane: dict[str, Any]) -> None:
    runtime = as_dict(lane.get("runtime"))
    root = str(runtime.get("root_objective_id") or "").strip()
    sl = str(runtime.get("objective_slice_id") or "").strip()
    if not root and not sl:
        return
    if bool(root) != bool(sl):
        raise SystemExit("root_objective_id and objective_slice_id must be supplied together")
    lane_id = str(lane.get("lane_id") or "")
    predecessor = str(runtime.get("predecessor_lane_id") or "").strip()
    group = [
        item for item in as_list(register.get("lanes"))
        if isinstance(item, dict)
        and str(item.get("lane_id") or "") != lane_id
        and str(as_dict(item.get("runtime")).get("root_objective_id") or "").strip() == root
        and str(as_dict(item.get("runtime")).get("objective_slice_id") or "").strip() == sl
    ]
    if predecessor:
        pred = find_lane_by_id(register, predecessor)
        if pred is None:
            raise SystemExit("predecessor_lane_id not found in register")
        pred_rt = as_dict(pred.get("runtime"))
        if str(pred_rt.get("root_objective_id") or "").strip() != root or str(pred_rt.get("objective_slice_id") or "").strip() != sl:
            raise SystemExit("cross-root predecessor rejected")
        pred_attempt = pred_rt.get("cumulative_attempt_number")
        pred_retry = pred_rt.get("cumulative_retry_count")
        try:
            base_attempt = int(pred_attempt) if pred_attempt not in (None, "") else 1
            base_retry = int(pred_retry) if pred_retry not in (None, "") else 0
        except (TypeError, ValueError):
            raise SystemExit("predecessor cumulative counters are not integers")
        expected_attempt = base_attempt + 1
        expected_retry = base_retry + 1
        if runtime.get("cumulative_attempt_number") in (None, ""):
            runtime["cumulative_attempt_number"] = expected_attempt
        elif int(runtime["cumulative_attempt_number"]) != expected_attempt:
            raise SystemExit("non-monotonic cumulative_attempt_number")
        if runtime.get("cumulative_retry_count") in (None, ""):
            runtime["cumulative_retry_count"] = expected_retry
        elif int(runtime["cumulative_retry_count"]) != expected_retry:
            raise SystemExit("non-monotonic cumulative_retry_count")
        lane["runtime"] = runtime
        return
    if group and not any(
        str(as_dict(item.get("runtime")).get("predecessor_lane_id") or "").strip() == lane_id
        for item in group
    ):
        raise SystemExit("missing predecessor_lane_id for successor slice attempt")
    if runtime.get("cumulative_attempt_number") in (None, ""):
        runtime["cumulative_attempt_number"] = 1
    elif int(runtime["cumulative_attempt_number"]) != 1:
        raise SystemExit("attempted cumulative reset rejected")
    if runtime.get("cumulative_retry_count") in (None, ""):
        runtime["cumulative_retry_count"] = 0
    elif int(runtime["cumulative_retry_count"]) != 0:
        raise SystemExit("attempted cumulative reset rejected")
    lane["runtime"] = runtime


def is_release_blocked(runtime: dict[str, Any]) -> bool:
    return not (
        str(runtime.get("technical_acceptance_status") or "pending") == "accepted"
        and str(runtime.get("accounting_status") or "pending") == "credited"
        and str(runtime.get("administrative_closure_status") or "open") == "closed"
        and str(runtime.get("activation_status") or "blocked") == "ready"
    )


def configured_openclaw_runtime_root() -> Path:
    """Return the physical OpenClaw runtime rooted beside this workspace.

    This deliberately does not use ``Path.home()``, ``HOME``, ``USERPROFILE``,
    or parser arguments.  Those values can be redirected by the process that
    is trying to claim credit, while the script's resolved installation path is
    the production trust anchor.
    """
    runtime_root = ROOT.parent.resolve()
    if runtime_root.name.lower() != ".openclaw":
        raise RuntimeError("workspace is not located under a physical .openclaw runtime root")
    return runtime_root


def configured_isolated_agent_state_root() -> Path:
    """Return the fixed production isolated-agent root eligible for credit."""
    return configured_openclaw_runtime_root() / "agents"


def configured_openclaw_state_db() -> Path:
    """Return the fixed core state database eligible to prove a dispatch bind."""
    return configured_openclaw_runtime_root() / "state" / "openclaw.sqlite"


def configured_codex_sessions_root() -> Path:
    """Return the one production Codex source root eligible for revalidation."""
    return configured_openclaw_runtime_root() / "agents" / "main" / "agent" / "codex-home" / "sessions"
CODEX_SUBAGENT_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
CODEX_TASK_PATH_PATTERN = re.compile(r"/root(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,127})+")
EXECUTION_BACKENDS = {"model_free_command", "persistent_isolated_agent", "codex_native_subagent", "main"}
COHORT_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "coordination_register_only": True,
    "spawns_helpers": False,
    "scheduler_allowed": False,
    "autonomous_execution_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "capital_deployment_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "coordination_register_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

FORBIDDEN_WRITE_PATTERNS = [
    r"^\.openclaw[\\/]",
    r"^~?[\\/]?\.openclaw[\\/]",
    r"(^|[\\/])openclaw\.json$",
    r"(^|[\\/])\.env($|[\\/])",
    r"(^|[\\/])credentials?($|[\\/])",
    r"(^|[\\/])secrets?($|[\\/])",
    r"(^|[\\/])09\. Archive[\\/]",
    r"(^|[\\/])backups[\\/]",
    r"^03\. Portfolio[\\/]",
    r"^04\. Research[\\/]Coverage and Watchlist\.md$",
    r"^data[\\/]finance[\\/]universe-v1\.json$",
    r"^state[\\/]finance[\\/]",
]

SQL_CANON_GATED_WRITE_EXCEPTIONS = {
    "state/finance/finance-canon.sqlite",
    "state/finance/finance-canon.sqlite-shm",
    "state/finance/finance-canon.sqlite-wal",
}
SQL_CANON_GATED_WRITE_PREFIX_EXCEPTIONS = (
    "backups/finance-sql-canon-migration/",
    "backups/finance-sql-source-lineage/",
    "backups/finance-production-scope-schema-retirement/",
    "backups/reference-levels-derived-refresh/",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_outcome_utc(value: Any) -> datetime | None:
    """Parse an outcome timestamp only when its UTC relationship is explicit."""
    if not isinstance(value, str) or OUTCOME_UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def next_outcome_recorded_at(previous: Any) -> str:
    candidate = parse_outcome_utc(utc_now()) or datetime.now(timezone.utc)
    prior = parse_outcome_utc(previous)
    if prior is not None and candidate <= prior:
        candidate = prior + timedelta(microseconds=1)
    return candidate.isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def usage_receipt_store_path(register_path: Path) -> Path:
    """Keep receipt state adjacent to the lane register, never in transcripts."""
    return register_path.with_suffix(".usage-receipts.json")


def declare_usage_receipt_write(lane: dict[str, Any], register_path: Path, imported_this_action: bool) -> None:
    """Expose the manager-owned receipt sidecar in the lane's write contract."""
    if not imported_this_action:
        return
    receipt_ref = normalize_path(rel(usage_receipt_store_path(register_path)))
    lane["allowed_writes"] = sorted({
        *[normalize_path(str(item)) for item in as_list(lane.get("allowed_writes")) if str(item).strip()],
        receipt_ref,
    })


def empty_usage_receipt_store() -> dict[str, Any]:
    return {
        "schema": USAGE_SOURCE_RECEIPTS_SCHEMA,
        "metadata_only": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "receipts": [],
    }


def load_usage_receipt_store(path: Path) -> dict[str, Any]:
    payload = load_dict(path)
    if not payload:
        return empty_usage_receipt_store()
    if payload.get("schema") != USAGE_SOURCE_RECEIPTS_SCHEMA:
        return empty_usage_receipt_store()
    payload.setdefault("metadata_only", True)
    payload.setdefault("authority_boundary", dict(AUTHORITY_BOUNDARY))
    payload.setdefault("receipts", [])
    return payload


def source_type_for_runtime(runtime: dict[str, Any]) -> str | None:
    source = str(runtime.get("token_attribution_source") or "")
    if source == "codex_native_rollout_jsonl":
        return "codex_native_rollout_jsonl"
    if source == "openclaw_isolated_session_store_v1":
        return "openclaw_isolated_session_store_v1"
    if source == "openclaw_isolated_session_store_v2":
        return "openclaw_isolated_session_store_v2"
    return None


def bounded_usage_receipt(lane: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any] | None:
    """Build an opaque source-to-lane receipt without session IDs or content.

    The receipt is written only after one of the two importer paths has opened
    and reconciled the actual allowlisted source.  It binds that source to one
    parent/lane/attempt and prevents a copied token bundle from closing another
    lane.
    """
    source_type = source_type_for_runtime(runtime)
    correlation = as_dict(runtime.get("attempt_correlation"))
    source_run_id = str(runtime.get("run_id") or "")
    source_snapshot = str(runtime.get("source_snapshot_fingerprint") or "")
    session_ref = str(runtime.get("session_ref_hash") or "")
    parent_job_id = str(runtime.get("parent_job_id") or "")
    phase = str(runtime.get("phase") or "")
    lane_key = str(lane.get("lane_id") or "")
    attempt_hash = str(correlation.get("key_hash") or "")
    model_path = str(runtime.get("model_path") or "")
    required = (source_type, source_run_id, source_snapshot, session_ref, parent_job_id, phase, lane_key, attempt_hash, model_path)
    if not all(required):
        return None
    token_fields = {
        key: strict_runtime_int(runtime.get(key))
        for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens")
    }
    if any(value is None for value in token_fields.values()):
        return None
    body = {
        "source_type": source_type,
        "source_run_id": source_run_id,
        "source_snapshot_fingerprint": source_snapshot,
        "session_ref_hash": session_ref,
        "lane_id": lane_key,
        "parent_job_id": parent_job_id,
        "phase": phase,
        "attempt_correlation_hash": attempt_hash,
        "model_path": model_path,
        "token_attribution_source": runtime.get("token_attribution_source"),
        "input_token_semantics": runtime.get("input_token_semantics"),
        "source_input_total_tokens": strict_runtime_int(runtime.get("source_input_total_tokens")),
        "source_total_tokens_fresh": runtime.get("source_total_tokens_fresh") is True,
        "tokens": token_fields,
    }
    if body["source_input_total_tokens"] is None:
        return None
    dispatch_binding = as_dict(runtime.get("dispatch_binding"))
    if dispatch_binding:
        binding_fields = (
            "schema",
            "binding_token_hash",
            "child_session_key_hash",
            "dispatch_nonce_hash",
            "target_agent_id_hash",
            "registry_run_id_hash",
            "reserved_at_ms",
            "accepted_at_ms",
            "terminal_at_ms",
            "terminal_status",
        )
        protected_binding = {key: dispatch_binding.get(key) for key in binding_fields}
        hash_fields = (
            "binding_token_hash",
            "child_session_key_hash",
            "dispatch_nonce_hash",
            "target_agent_id_hash",
            "registry_run_id_hash",
        )
        timestamp_fields = ("reserved_at_ms", "accepted_at_ms", "terminal_at_ms")
        if (
            protected_binding["schema"] != "veritas.isolated_dispatch_binding.v1"
            or protected_binding["terminal_status"] != "ok"
            or not all(
                isinstance(protected_binding[key], str)
                and re.fullmatch(r"[a-f0-9]{64}", str(protected_binding[key]))
                for key in hash_fields
            )
            or not all(
                (value := strict_runtime_int(protected_binding[key])) is not None and value > 0
                for key in timestamp_fields
            )
        ):
            return None
        if not (
            int(protected_binding["reserved_at_ms"])
            <= int(protected_binding["accepted_at_ms"])
            <= int(protected_binding["terminal_at_ms"])
        ):
            return None
        body["dispatch_binding"] = protected_binding
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "veritas.model_usage_source_receipt.v1",
        "receipt_id": sha256_text(encoded),
        # A source run is consumable exactly once.  The snapshot is retained
        # in the receipt body for revalidation, but must not be part of the
        # uniqueness key; otherwise the same run can be replayed under a new
        # snapshot fingerprint and credited to a second lane.
        "source_binding_contract_version": USAGE_SOURCE_BINDING_CONTRACT_VERSION,
        "source_binding_id": sha256_text("|".join((source_type, source_run_id))),
        "verified_at_utc": utc_now(),
        **body,
    }


def persist_usage_source_receipt(lane: dict[str, Any], runtime: dict[str, Any], store_path: Path) -> str:
    receipt = bounded_usage_receipt(lane, runtime)
    if receipt is None:
        raise SystemExit("trusted source import did not produce a complete source receipt")
    store = load_usage_receipt_store(store_path)
    receipts = [row for row in as_list(store.get("receipts")) if isinstance(row, dict)]
    binding_id = receipt["source_binding_id"]
    for existing in receipts:
        if existing.get("source_binding_id") != binding_id:
            continue
        same_receipt = existing.get("receipt_id") == receipt["receipt_id"]
        if not same_receipt:
            raise SystemExit("source run is already bound to a different lane or attempt")
    if not any(existing.get("receipt_id") == receipt["receipt_id"] for existing in receipts):
        receipts.append(receipt)
    store["schema"] = USAGE_SOURCE_RECEIPTS_SCHEMA
    store["metadata_only"] = True
    store["authority_boundary"] = dict(AUTHORITY_BOUNDARY)
    store["updated_at_utc"] = utc_now()
    store["receipts"] = sorted(receipts, key=lambda row: (str(row.get("verified_at_utc") or ""), str(row.get("receipt_id") or "")))
    atomic_write_json(store_path, store)
    runtime["usage_source_receipt_id"] = receipt["receipt_id"]
    runtime["usage_source_receipt_schema"] = receipt["schema"]
    return receipt["receipt_id"]


def _source_record_matches_runtime(record: dict[str, Any], runtime: dict[str, Any]) -> bool:
    """Compare the fixed, privacy-safe fields emitted by an isolated source.

    A lane register and its adjacent receipt cache are mutable workspace
    metadata.  They can route a source observation, but they cannot by
    themselves prove that the source was reopened.  This comparison is shared
    by every credit consumer through ``verify_usage_source_receipt``.
    """
    for key in (
        "run_id",
        "agent_role",
        "session_ref_hash",
        "source_snapshot_fingerprint",
        "model_path",
        "model_provider",
        "usage_at_utc",
        "usage_time_source",
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "total_tokens",
        "source_input_total_tokens",
        "duration_ms",
    ):
        if record.get(key) != runtime.get(key):
            return False
    if record.get("source_total_tokens_fresh") is not True or runtime.get("source_total_tokens_fresh") is not True:
        return False
    expected_binding = as_dict(runtime.get("dispatch_binding"))
    if expected_binding:
        observed_binding = as_dict(record.get("dispatch_binding"))
        return bool(observed_binding) and observed_binding == expected_binding
    expected_attempt = as_dict(record.get("attempt_correlation")).get("key_hash")
    observed_attempt = as_dict(runtime.get("attempt_correlation")).get("key_hash")
    return bool(expected_attempt and observed_attempt and expected_attempt == observed_attempt)


def _reverify_isolated_usage_source(
    runtime: dict[str, Any],
    *,
    agent_state_root: Path,
    state_db_path: Path,
    expected_binding_token_hash: str | None = None,
) -> list[str]:
    """Re-open the fixed allowlisted isolated-agent source before crediting it."""
    agent_id = str(runtime.get("agent_id") or "")
    if agent_id not in CONFIGURED_ISOLATED_AGENT_IDS:
        return ["isolated_source_agent_not_allowlisted"]
    if expected_binding_token_hash:
        record, errors = load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=expected_binding_token_hash,
            agent_state_root=agent_state_root,
            state_db_path=state_db_path,
        )
        if record is None:
            return errors or ["isolated_dispatch_binding_reopen_failed"]
        return [] if _source_record_matches_runtime(record, runtime) else ["isolated_source_reverification_mismatch"]
    try:
        payload = load_allowlisted_session_usage([agent_id], agent_state_root)
    except (OSError, ValueError):
        return ["isolated_source_reopen_failed"]
    matches = [
        record for record in as_list(payload.get("records"))
        if isinstance(record, dict)
        and record.get("agent_id") == agent_id
        and _source_record_matches_runtime(record, runtime)
    ]
    if len(matches) != 1:
        return ["isolated_source_reverification_mismatch"]
    return []


def _find_codex_rollout_by_session_hash(session_hash: str, sessions_root: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve exactly one native rollout from the fixed Codex sessions root.

    We retain only a session hash in workspace metadata.  The resolver scans
    fixed ``session_meta`` identifiers and never projects prompt, response, or
    tool content.  It is intentionally used only for source re-verification.
    """
    if not session_hash:
        return None, "codex_source_session_hash_required"
    try:
        root = sessions_root.expanduser().resolve(strict=True)
    except OSError:
        return None, "codex_source_root_unavailable"
    if not root.is_dir():
        return None, "codex_source_root_unavailable"
    session_ids: set[str] = set()
    try:
        candidates = list(root.rglob("*.jsonl"))
    except OSError:
        return None, "codex_source_scan_failed"
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
            with resolved.open("r", encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    if not isinstance(row, dict) or row.get("type") != "session_meta":
                        continue
                    session_id = as_dict(row.get("payload")).get("id")
                    if isinstance(session_id, str) and CODEX_SESSION_ID_PATTERN.fullmatch(session_id) and hash_reference(session_id) == session_hash:
                        session_ids.add(session_id)
                    break
        except (OSError, UnicodeError, json.JSONDecodeError):
            # A malformed unrelated rollout is not a reason to trust a
            # candidate.  The exact candidate must still resolve uniquely.
            continue
    if len(session_ids) != 1:
        return None, "codex_source_not_unique_or_missing"
    try:
        return load_codex_native_rollout(next(iter(session_ids)), root), None
    except SystemExit:
        return None, "codex_source_reopen_failed"


def _reverify_codex_native_usage_source(
    runtime: dict[str, Any],
    *,
    sessions_root: Path,
) -> list[str]:
    """Re-open native source evidence, then require a protected dispatch bind.

    Codex rollout JSONL proves source usage/model, but it does not include the
    parent job, lane, phase, or attempt.  Until a protected dispatcher binding
    exists outside the lane-writer boundary, source evidence may not receive
    per-job credit.  This is deliberately fail-closed rather than pretending a
    self-hashed workspace receipt closes that authorization gap.
    """
    source_hash = str(runtime.get("source_run_id_hash") or "")
    record, error = _find_codex_rollout_by_session_hash(source_hash, sessions_root)
    if error:
        return [error]
    assert record is not None
    usage = as_dict(record.get("usage"))
    expected = {
        "source_snapshot_fingerprint": record.get("source_snapshot_fingerprint"),
        "model_path": record.get("model"),
        "source_cumulative_input_tokens": usage.get("input_tokens"),
        "source_cumulative_cached_input_tokens": usage.get("cached_input_tokens"),
        "source_cumulative_output_tokens": usage.get("output_tokens"),
    }
    if any(runtime.get(key) != value for key, value in expected.items()):
        return ["codex_source_reverification_mismatch"]
    input_tokens = strict_runtime_int(runtime.get("input_tokens"))
    cached_tokens = strict_runtime_int(runtime.get("cached_input_tokens"))
    output_tokens = strict_runtime_int(runtime.get("output_tokens"))
    baseline_input = strict_runtime_int(runtime.get("fork_baseline_input_tokens"))
    baseline_cached = strict_runtime_int(runtime.get("fork_baseline_cached_input_tokens"))
    baseline_output = strict_runtime_int(runtime.get("fork_baseline_output_tokens"))
    if any(value is None for value in (input_tokens, cached_tokens, output_tokens, baseline_input, baseline_cached, baseline_output)):
        return ["codex_source_token_binding_missing"]
    if (
        input_tokens != int(usage["input_tokens"]) - int(baseline_input)
        or cached_tokens != int(usage["cached_input_tokens"]) - int(baseline_cached)
        or output_tokens != int(usage["output_tokens"]) - int(baseline_output)
    ):
        return ["codex_source_token_reverification_mismatch"]
    return ["codex_dispatch_binding_required"]


def source_reverification_reasons(
    lane: dict[str, Any],
    runtime: dict[str, Any],
    *,
    isolated_agent_state_root: Path | None = None,
    codex_sessions_root: Path | None = None,
) -> list[str]:
    """Return proof failures after reopening the actual fixed source.

    The receipt sidecar is a cache and routing aid only.  All per-job cost,
    savings, and outcome credit must survive this independent source check.
    """
    # These optional parameters remain for source-parser fixture compatibility,
    # but deliberately have no authority at credit time.  A process that can
    # choose a root could pair a coherent writable receipt with a synthetic
    # sessions store.  Credit re-opens only the configured production roots.
    del isolated_agent_state_root, codex_sessions_root
    source_type = source_type_for_runtime(runtime)
    if source_type == "openclaw_isolated_session_store_v1":
        # A v1 session index is useful observation telemetry but cannot prove
        # which caller/attempt dispatched it.  Preserve it for audit and fail
        # closed for credit until it arrives through the protected v2 bind.
        return ["isolated_dispatch_binding_required"]
    if source_type == "openclaw_isolated_session_store_v2":
        expected = expected_attempt_correlation(lane, runtime)
        if expected is None:
            return ["attempt_correlation_required"]
        expected_binding_token_hash = dispatch_binding_token_hash_for_attempt(
            attempt_correlation_hash=expected["key_hash"]
        )
        observed_binding = as_dict(runtime.get("dispatch_binding"))
        if observed_binding.get("binding_token_hash") != expected_binding_token_hash:
            return ["dispatch_binding_attempt_mismatch"]
        timeline_reasons = dispatch_binding_lane_lifecycle_reasons(lane, observed_binding)
        if timeline_reasons:
            return timeline_reasons
        try:
            return _reverify_isolated_usage_source(
                runtime,
                agent_state_root=configured_isolated_agent_state_root(),
                state_db_path=configured_openclaw_state_db(),
                expected_binding_token_hash=expected_binding_token_hash,
            )
        except (OSError, RuntimeError):
            return ["configured_openclaw_runtime_root_unavailable"]
    if source_type == "codex_native_rollout_jsonl":
        try:
            return _reverify_codex_native_usage_source(
                runtime,
                sessions_root=configured_codex_sessions_root(),
            )
        except (OSError, RuntimeError):
            return ["configured_openclaw_runtime_root_unavailable"]
    return ["trusted_source_reverification_required"]


def verify_usage_source_receipt(
    lane: dict[str, Any],
    runtime: dict[str, Any],
    store_path: Path,
    *,
    isolated_agent_state_root: Path | None = None,
    codex_sessions_root: Path | None = None,
) -> list[str]:
    if not terminal_timestamp_is_consistent(lane):
        return ["terminal_timestamp_before_created_at"]
    expected_attempt = expected_attempt_correlation(lane, runtime)
    observed_attempt = as_dict(runtime.get("attempt_correlation")).get("key_hash")
    if expected_attempt is None or observed_attempt != expected_attempt.get("key_hash"):
        return ["attempt_correlation_required"]
    expected = bounded_usage_receipt(lane, runtime)
    receipt_id = str(runtime.get("usage_source_receipt_id") or "")
    if expected is None or not receipt_id:
        return ["source_receipt_required"]
    if receipt_id != expected["receipt_id"]:
        return ["source_receipt_runtime_binding_mismatch"]
    store = load_usage_receipt_store(store_path)
    matches = [row for row in as_list(store.get("receipts")) if isinstance(row, dict) and row.get("receipt_id") == receipt_id]
    if len(matches) != 1:
        return ["source_receipt_missing_or_ambiguous"]
    receipt = matches[0]
    if receipt != expected and {key: value for key, value in receipt.items() if key != "verified_at_utc"} != {key: value for key, value in expected.items() if key != "verified_at_utc"}:
        return ["source_receipt_store_binding_mismatch"]
    binding_matches = [
        row for row in as_list(store.get("receipts"))
        if isinstance(row, dict) and row.get("source_binding_id") == expected["source_binding_id"]
    ]
    if len(binding_matches) != 1:
        return ["source_receipt_source_reused_or_ambiguous"]
    return source_reverification_reasons(
        lane,
        runtime,
        isolated_agent_state_root=isolated_agent_state_root,
        codex_sessions_root=codex_sessions_root,
    )


def nonnegative_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a nonnegative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def positive_int_arg(value: str) -> int:
    parsed = nonnegative_int_arg(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be an integer greater than or equal to 1")
    return parsed


def strict_attempt_int(value: Any, *, minimum: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= minimum:
        return value
    return None


def legacy_attempt_int(value: Any, *, minimum: int) -> int | None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value.strip()):
        return None
    parsed = int(value.strip())
    return parsed if parsed >= minimum else None


def compatible_attempt_int(value: Any, *, minimum: int) -> int | None:
    typed = strict_attempt_int(value, minimum=minimum)
    return typed if typed is not None else legacy_attempt_int(value, minimum=minimum)


def normalize_attempt_metadata(runtime: dict[str, Any]) -> None:
    """Normalize prospective attempt identity without inventing legacy history."""
    retry_supplied = runtime.get("retry_count") not in (None, "")
    attempt_supplied = runtime.get("attempt_number") not in (None, "")
    if not retry_supplied and not attempt_supplied:
        return
    retry_count = compatible_attempt_int(runtime.get("retry_count"), minimum=0) if retry_supplied else None
    attempt_number = compatible_attempt_int(runtime.get("attempt_number"), minimum=1) if attempt_supplied else None
    if retry_supplied and retry_count is None:
        raise SystemExit("retry_count must be a nonnegative integer")
    if attempt_supplied and attempt_number is None:
        raise SystemExit("attempt_number must be an integer greater than or equal to 1")
    if retry_count is None:
        retry_count = int(attempt_number or 1) - 1
    if attempt_number is None:
        attempt_number = retry_count + 1
    if attempt_number != retry_count + 1:
        raise SystemExit("attempt_number must equal retry_count + 1")
    runtime["retry_count"] = retry_count
    runtime["attempt_number"] = attempt_number
    runtime["is_first_attempt"] = attempt_number == 1


def active_implementation_attempt_outcome_baseline_applies(
    lane: dict[str, Any], runtime: dict[str, Any]
) -> bool:
    """Identify active model attempts that require an explicit clean baseline."""
    retry_count = strict_attempt_int(runtime.get("retry_count"), minimum=0)
    attempt_number = strict_attempt_int(runtime.get("attempt_number"), minimum=1)
    return bool(
        lane.get("status") in ACTIVE_STATUSES
        and runtime.get("model_path") not in (None, "")
        and str(runtime.get("phase") or "").strip().lower() == "implementation"
        and retry_count is not None
        and attempt_number == retry_count + 1
    )


def efficiency_enforcement_applies(lane: dict[str, Any]) -> bool:
    created = parse_utc(lane.get("created_at_utc"))
    start = parse_utc(EFFICIENCY_ENFORCEMENT_START_UTC)
    return bool(created and start and created >= start)


def identity_metadata_hard_enforcement_applies(lane: dict[str, Any]) -> bool:
    """Fail closed unless a terminal row is timestamped before Wave 1."""
    created = parse_utc(lane.get("created_at_utc"))
    start = parse_utc(IDENTITY_METADATA_HARD_ENFORCEMENT_START_UTC)
    if lane.get("status") in ACTIVE_STATUSES:
        return True
    if start is None:
        return True
    if created is not None:
        return created >= start
    terminal_time = parse_utc(lane.get("ended_at_utc")) or parse_utc(lane.get("completed_at_utc"))
    if terminal_time is None:
        return True
    return terminal_time >= start


def is_provably_pre_identity_enforcement_terminal(lane: dict[str, Any]) -> bool:
    """Return true only for a terminal row with a valid pre-cutoff creation time."""
    created = parse_utc(lane.get("created_at_utc"))
    start = parse_utc(IDENTITY_METADATA_HARD_ENFORCEMENT_START_UTC)
    return bool(
        lane.get("status") in TERMINAL_STATUSES
        and created is not None
        and start is not None
        and created < start
    )


def is_provably_pre_outcome_event_history_enforcement_terminal(
    lane: dict[str, Any], runtime: dict[str, Any]
) -> bool:
    """Classify only terminal rows whose retained event predates list enforcement."""
    event_time = parse_outcome_utc(runtime.get("outcome_recorded_at_utc"))
    start = parse_utc(OUTCOME_EVENT_HISTORY_HARD_ENFORCEMENT_START_UTC)
    return bool(
        lane.get("status") in TERMINAL_STATUSES
        and event_time is not None
        and start is not None
        and event_time < start
    )


HISTORICAL_TERMINAL_SESSION_INDEX_RETENTION_REASON = "dispatch_binding_session_index_unavailable"


def is_historical_terminal_session_index_retention_gap(
    lane: dict[str, Any],
    runtime: dict[str, Any],
    credit: dict[str, Any],
) -> bool:
    """Classify one aged-out terminal canary as retention debt, not new failure.

    Event-time credit is immutable historical evidence; the live session-index
    row has aged out, so current source re-verification and accounting credit
    are unavailable by design.  Release and current credit remain blocked.
    ``usage_credit_assessment()`` is never altered by this classification.

    Every near miss returns False and stays critical: post-cutoff event time,
    an extra or different current reason, receipt/binding/source mismatch,
    current accounting credited, release-ready state, missing Main acceptance,
    a non-pass validator, unverified closure, a present ``outcome_events``
    list, or a non-complete status.
    """
    if lane.get("status") != "complete":
        return False
    if not is_provably_pre_outcome_event_history_enforcement_terminal(lane, runtime):
        return False
    # Historical absence only: an empty modern list must not qualify.
    if "outcome_events" in lane:
        return False
    if runtime.get("token_attribution_source") != "openclaw_isolated_session_store_v2":
        return False
    if runtime.get("usage_credit_status") != "creditable" or runtime.get("usage_creditable") is not True:
        return False
    if runtime.get("source_reverification_status") != "verified":
        return False
    if runtime.get("main_acceptance_status") != "accepted":
        return False
    if runtime.get("outcome_status") != "accepted":
        return False
    if runtime.get("validator_result") != "pass":
        return False
    if runtime.get("closure_durability") != "verified":
        return False
    if credit.get("required") is not True:
        return False
    if credit.get("usage_creditable") is not False:
        return False
    if list(credit.get("reasons") or []) != [HISTORICAL_TERMINAL_SESSION_INDEX_RETENTION_REASON]:
        return False
    if runtime.get("accounting_status") == "credited":
        return False
    # NOTE: ``is_release_blocked`` takes the lane runtime mapping, not the lane.
    if not is_release_blocked(runtime):
        return False
    return True


def is_provably_pre_proof_artifact_enforcement_complete(lane: dict[str, Any]) -> bool:
    """Classify missing paths only for completed rows created before retention enforcement."""
    created = parse_utc(lane.get("created_at_utc"))
    start = parse_utc(PROOF_ARTIFACT_EXISTENCE_HARD_ENFORCEMENT_START_UTC)
    return bool(
        lane.get("status") == "complete"
        and created is not None
        and start is not None
        and created < start
    )


def resource_budget_defaults(runtime: dict[str, Any]) -> dict[str, int]:
    phase = str(runtime.get("phase") or runtime.get("task_shape") or "default").strip().lower()
    if phase in IMPLEMENTATION_PHASES:
        phase = "implementation"
    return dict(DEFAULT_RESOURCE_BUDGETS.get(phase, DEFAULT_RESOURCE_BUDGETS["default"]))


def normalize_resource_budgets(runtime: dict[str, Any]) -> None:
    if not runtime.get("model_path"):
        return
    defaults = resource_budget_defaults(runtime)
    field_map = {
        "max_gross_tokens": "gross_tokens",
        "max_cached_replay_tokens": "cached_replay_tokens",
        "max_tool_calls": "tool_calls",
        "max_elapsed_seconds": "elapsed_seconds",
    }
    for field, budget_key in field_map.items():
        value = runtime.get(field)
        if value in (None, ""):
            runtime[field] = defaults[budget_key]
            continue
        parsed = strict_runtime_int(value)
        if parsed is None or parsed < 1:
            raise SystemExit(f"{field} must be a positive integer")
        if parsed > HARD_RESOURCE_CEILINGS[budget_key]:
            raise SystemExit(f"{field} exceeds the hard resource ceiling")
        runtime[field] = parsed


def evaluate_resource_budget(lane: dict[str, Any]) -> list[str]:
    runtime = as_dict(lane.get("runtime"))
    if not runtime.get("model_path"):
        return []
    if strict_runtime_int(runtime.get("observed_elapsed_seconds")) is None:
        started = parse_utc(lane.get("started_at_utc"))
        ended = parse_utc(lane.get("ended_at_utc"))
        if started is not None and ended is not None and ended >= started:
            runtime["observed_elapsed_seconds"] = int(math.ceil((ended - started).total_seconds()))
    observations = {
        "gross_tokens": strict_runtime_int(runtime.get("total_tokens")),
        "cached_replay_tokens": strict_runtime_int(runtime.get("cached_input_tokens")),
        "tool_calls": strict_runtime_int(runtime.get("observed_tool_calls")),
        "elapsed_seconds": strict_runtime_int(runtime.get("observed_elapsed_seconds")),
    }
    limits = {
        "gross_tokens": strict_runtime_int(runtime.get("max_gross_tokens")),
        "cached_replay_tokens": strict_runtime_int(runtime.get("max_cached_replay_tokens")),
        "tool_calls": strict_runtime_int(runtime.get("max_tool_calls")),
        "elapsed_seconds": strict_runtime_int(runtime.get("max_elapsed_seconds")),
    }
    reason_by_metric = {
        "gross_tokens": "token_budget_exceeded",
        "cached_replay_tokens": "cached_replay_budget_exceeded",
        "tool_calls": "tool_loop_budget_exceeded",
        "elapsed_seconds": "elapsed_budget_exceeded",
    }
    breaches = [reason_by_metric[key] for key in observations if observations[key] is not None and limits[key] is not None and observations[key] > limits[key]]
    runtime["resource_budget_guard"] = {
        "status": "blocked" if breaches else ("ok" if all(value is not None for value in observations.values()) else "partial"),
        "limits": limits,
        "observed": observations,
        "breaches": breaches,
        "early_stop_required": bool(breaches),
    }
    lane["runtime"] = runtime
    return breaches


def enforce_resource_budget(lane: dict[str, Any], previous_status: str | None) -> bool:
    breaches = evaluate_resource_budget(lane)
    if not breaches:
        return False
    lane["status"] = "blocked"
    runtime = as_dict(lane.get("runtime"))
    runtime["incident_code"] = breaches[0]
    lane["runtime"] = runtime
    stamp_status_times(lane, "blocked", previous_status)
    record_outcome_transition(lane, event_kind="incident", previous_status=previous_status, state_changed=True)
    return True


def enforce_usage_creditability(
    lane: dict[str, Any],
    previous_status: str | None,
    *,
    receipt_store_path: Path,
    source_reverified_this_action: bool,
    isolated_agent_state_root: Path | None = None,
    codex_sessions_root: Path | None = None,
) -> bool:
    """Fail closed before a new model lane can report a successful closeout.

    The work itself may have happened, so raw runtime fields remain in the
    record.  The lane is blocked as a control-plane outcome until a unique
    trusted source run is imported and reconciled.
    """
    runtime = as_dict(lane.get("runtime"))
    credit = usage_credit_assessment(
        lane,
        runtime,
        receipt_store_path=receipt_store_path,
        require_reverification=True,
        source_reverified_this_action=source_reverified_this_action,
        isolated_agent_state_root=isolated_agent_state_root,
        codex_sessions_root=codex_sessions_root,
    )
    if not credit.get("required"):
        return False
    runtime["telemetry_contract_version"] = MODEL_USAGE_CREDIT_CONTRACT_VERSION
    runtime["usage_credit_status"] = credit["status"]
    runtime["usage_creditable"] = credit["usage_creditable"] is True
    runtime["usage_credit_block_reasons"] = credit.get("reasons") or []
    runtime["source_reverification_contract_version"] = USAGE_SOURCE_REVERIFICATION_CONTRACT_VERSION
    runtime["source_reverification_status"] = "verified" if credit["usage_creditable"] is True else "blocked"
    if credit.get("usage_creditable") is True:
        lane["runtime"] = runtime
        return False
    lane["status"] = "blocked"
    runtime["incident_code"] = "telemetry_attribution_unavailable"
    runtime["outcome_status"] = "telemetry_blocked"
    if str(runtime.get("technical_acceptance_status") or "").strip() not in TECHNICAL_ACCEPTANCE_STATUSES:
        runtime["technical_acceptance_status"] = "pending"
    if str(runtime.get("main_acceptance_status") or "").strip() not in ("accepted", "telemetry_blocked"):
        runtime["main_acceptance_status"] = "telemetry_blocked"
    runtime["accounting_status"] = "blocked"
    runtime.setdefault("accounting_detail", "provider_usage_unavailable")
    runtime["administrative_closure_status"] = "blocked"
    runtime["activation_status"] = "blocked"
    runtime["release_blocked"] = True
    lane["runtime"] = runtime
    stamp_status_times(lane, "blocked", previous_status)
    record_outcome_transition(lane, event_kind="incident", previous_status=previous_status, state_changed=True)
    return True


def enforce_rework_policy(register: dict[str, Any], lane: dict[str, Any]) -> None:
    runtime = as_dict(lane.get("runtime"))
    group = rework_group_key(runtime)
    parent_job_id = str(runtime.get("parent_job_id") or "")
    phase = str(runtime.get("phase") or "").strip().lower()
    if group[0] == "parent" and not parent_job_id:
        return
    if phase not in {"repair", "qa"}:
        return
    siblings = [
        item for item in as_list(register.get("lanes"))
        if isinstance(item, dict)
        and item.get("lane_id") != lane.get("lane_id")
        and rework_group_key(as_dict(item.get("runtime"))) == group
    ]
    prior_repairs = [item for item in siblings if str(as_dict(item.get("runtime")).get("phase") or "").lower() == "repair"]
    prior_qa_retries = [
        item for item in siblings
        if str(as_dict(item.get("runtime")).get("phase") or "").lower() == "qa"
        and (strict_attempt_int(as_dict(item.get("runtime")).get("retry_count"), minimum=1) is not None)
    ]
    retry_count = strict_attempt_int(runtime.get("retry_count"), minimum=0) or 0
    if phase == "repair" and (prior_repairs or retry_count > 1):
        raise SystemExit("ordinary rework cap reached: return to Main for scope reduction")
    if phase == "qa" and retry_count > 1:
        raise SystemExit("fresh QA rerun cap reached: return to Main for scope reduction")
    if phase == "qa" and retry_count >= 1 and prior_qa_retries:
        raise SystemExit("fresh QA rerun cap reached: return to Main for scope reduction")


def record_outcome_transition(
    lane: dict[str, Any],
    *,
    event_kind: str,
    previous_status: str | None,
    state_changed: bool | None = None,
) -> None:
    runtime = as_dict(lane.get("runtime"))
    if event_kind not in OUTCOME_EVENT_KINDS:
        raise SystemExit(f"unsupported outcome event kind: {event_kind}")
    events = lane.get("outcome_events")
    if events is None:
        events = []
    if not isinstance(events, list):
        raise SystemExit("lane outcome_events must be a list")
    event_times: list[datetime] = []
    for index, row in enumerate(events, start=1):
        recorded_at = parse_outcome_utc(row.get("recorded_at_utc")) if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or set(row) != {"event_kind", "event_sequence", "recorded_at_utc"}
            or row.get("event_kind") not in OUTCOME_EVENT_KINDS
            or strict_attempt_int(row.get("event_sequence"), minimum=1) != index
            or not isinstance(row.get("recorded_at_utc"), str)
            or recorded_at is None
        ):
            raise SystemExit("lane outcome_events history is invalid")
        if event_times and recorded_at <= event_times[-1]:
            raise SystemExit("lane outcome_events timestamps must be strictly increasing")
        event_times.append(recorded_at)

    raw_sequence = runtime.get("outcome_event_sequence")
    if raw_sequence is None:
        prior_sequence = 0
    else:
        prior_sequence = strict_attempt_int(raw_sequence, minimum=0)
        if prior_sequence is None:
            raise SystemExit("runtime outcome_event_sequence must be an exact integer")
    if len(events) != prior_sequence:
        raise SystemExit("lane outcome_events sequence is inconsistent")
    previous_kind = runtime.get("outcome_event_kind")
    previous_recorded_at = runtime.get("outcome_recorded_at_utc")
    if events:
        if (
            not isinstance(previous_kind, str)
            or previous_kind not in OUTCOME_EVENT_KINDS
            or not isinstance(previous_recorded_at, str)
            or parse_outcome_utc(previous_recorded_at) is None
            or events[-1] != {
                "event_kind": previous_kind,
                "event_sequence": prior_sequence,
                "recorded_at_utc": previous_recorded_at,
            }
        ):
            raise SystemExit("lane outcome_events terminal event is inconsistent")
    elif previous_kind not in (None, "") or previous_recorded_at not in (None, "") or prior_sequence != 0:
        raise SystemExit("runtime outcome event state has no matching history")

    raw_incident_count = runtime.get("incident_count")
    prior_incident_count = 0
    incident_event_count = sum(row.get("event_kind") == "incident" for row in events)
    if events and raw_incident_count is None:
        raise SystemExit("runtime incident_count must equal incident event history")
    if raw_incident_count is not None:
        parsed_incident_count = strict_attempt_int(raw_incident_count, minimum=0)
        if parsed_incident_count is None:
            raise SystemExit("runtime incident_count must be an exact integer")
        prior_incident_count = parsed_incident_count
    if prior_incident_count != incident_event_count:
        raise SystemExit("runtime incident_count must equal incident event history")
    if event_kind != "incident" and prior_incident_count != 0:
        raise SystemExit("successful outcome incident_count must be exact zero")

    same_transition = previous_kind == event_kind and previous_status == str(lane.get("status") or "")
    if state_changed is True:
        same_transition = False
    new_runtime = dict(runtime)
    new_events = list(events)
    if same_transition:
        new_sequence = prior_sequence
        new_recorded_at = previous_recorded_at
    else:
        new_sequence = prior_sequence + 1
        new_recorded_at = next_outcome_recorded_at(previous_recorded_at)
        parsed_new_time = parse_outcome_utc(new_recorded_at)
        if parsed_new_time is None or (event_times and parsed_new_time <= event_times[-1]):
            raise SystemExit("new outcome event timestamp must be later than prior event")
        new_events.append(
            {
                "event_kind": event_kind,
                "event_sequence": new_sequence,
                "recorded_at_utc": new_recorded_at,
            }
        )
    new_runtime["outcome_event_kind"] = event_kind
    new_runtime["outcome_event_sequence"] = new_sequence
    new_runtime["outcome_recorded_at_utc"] = new_recorded_at
    if event_kind == "incident":
        new_runtime.setdefault("incident_code", "unknown")
        new_runtime["incident_count"] = prior_incident_count if same_transition else prior_incident_count + 1
    else:
        new_runtime.setdefault("incident_code", "")
        new_runtime["incident_count"] = 0
    lane["outcome_events"] = new_events
    lane["runtime"] = new_runtime


def runtime_has_token_value(runtime: dict[str, Any]) -> bool:
    return any(
        runtime.get(key) not in (None, "")
        for key in (*TOKEN_KEYS, "cache_write_tokens", "source_input_total_tokens")
    )


def strict_runtime_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def runtime_token_assessment(runtime: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in COMPLETE_TOKEN_KEYS if strict_runtime_int(runtime.get(key)) is None]
    semantics = str(runtime.get("input_token_semantics") or "")
    if semantics not in {"exclusive_cached", "inclusive_cached", "no_cache"}:
        missing.append("input_token_semantics")
    if missing:
        return {
            "token_valid": False,
            "pricing_grade": False,
            "status": "attribution_incomplete",
            "missing_fields": sorted(set(missing)),
        }
    input_tokens = int(runtime["input_tokens"])
    cached = int(runtime["cached_input_tokens"])
    cache_write = int(runtime["cache_write_tokens"])
    output = int(runtime["output_tokens"])
    total = int(runtime["total_tokens"])
    reasons: list[str] = []
    if semantics == "no_cache":
        if cached or cache_write:
            reasons.append("no_cache_conflicts_with_cache_tokens")
        expected = input_tokens + output
    elif semantics == "inclusive_cached":
        if cached > input_tokens:
            reasons.append("inclusive_cached_exceeds_input_tokens")
        expected = input_tokens + cache_write + output
    else:
        expected = input_tokens + cached + cache_write + output
    if total != expected:
        reasons.append("token_total_mismatch")
    source_input_total = runtime.get("source_input_total_tokens")
    isolated_source = str(runtime.get("token_attribution_source") or "").startswith("openclaw_isolated_session_store")
    if isolated_source and source_input_total in (None, ""):
        reasons.append("source_input_total_tokens_missing")
    if source_input_total not in (None, ""):
        parsed_source_total = strict_runtime_int(source_input_total)
        expected_source_total = input_tokens + cache_write if semantics == "inclusive_cached" else input_tokens + cached + cache_write
        if parsed_source_total is None or parsed_source_total != expected_source_total:
            reasons.append("source_input_total_mismatch")
    if isolated_source and runtime.get("source_total_tokens_fresh") is not True:
        reasons.append("source_total_tokens_fresh_not_proven")
    elif runtime.get("source_total_tokens_fresh") is False:
        reasons.append("source_total_tokens_not_fresh")
    token_valid = not reasons
    pricing_grade = token_valid and cache_write == 0
    return {
        "token_valid": token_valid,
        "pricing_grade": pricing_grade,
        "status": (
            "pricing_grade"
            if pricing_grade else (
                "usage_exact_rate_unavailable"
                if token_valid and cache_write > 0 else "invalid_usage"
            )
        ),
        "missing_fields": [],
        "reasons": reasons,
        "token_total_expected": expected,
    }


def telemetry_enforcement_applies(lane: dict[str, Any], runtime: dict[str, Any]) -> bool:
    """Return true for post-cutover model work that needs a source-backed join.

    The lane creation time is the primary cutover anchor so historic records do
    not get rewritten.  A missing creation time falls back to terminal time and
    is therefore never a way to evade the new contract.
    """
    model_path = runtime.get("model_path") or lane.get("model_path")
    if not model_path:
        return False
    cutoff = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    if cutoff is None:
        return False
    observed_at = parse_utc(lane.get("created_at_utc"))
    if observed_at is None:
        observed_at = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    # A terminal model lane with no usable time cannot claim a historical
    # exception.  Treat it as in-scope so closeout fails rather than allowing a
    # missing timestamp to bypass the strict cutover.
    if observed_at is None:
        return str(lane.get("status") or "") in TERMINAL_STATUSES
    return observed_at >= cutoff


def terminal_timestamp_is_consistent(lane: dict[str, Any]) -> bool:
    """Reject a terminal timestamp that predates the lane's creation.

    ``created_at_utc`` is the primary cutover anchor. A mutable earlier end
    timestamp must not recast post-cutover work as historical or let it enter
    an outcome/efficiency cohort.
    """
    created = parse_utc(lane.get("created_at_utc"))
    terminal = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    return not (created is not None and terminal is not None and terminal < created)


def dispatch_binding_lane_lifecycle_reasons(
    lane: dict[str, Any],
    binding: dict[str, Any],
) -> list[str]:
    """Require a protected binding to fit inside the lane it claims to credit.

    A deterministic token must not backfill a completed lane. Its source-side
    reservation must occur after lane creation and a terminal receipt must not
    arrive after the terminal lane closeout. The core reader independently
    reopens the binding, so cached lane metadata cannot establish this proof.
    """
    created_at = parse_utc(lane.get("created_at_utc"))
    if created_at is None:
        return ["dispatch_binding_lane_created_at_required"]
    timestamps = {
        key: binding.get(key)
        for key in ("reserved_at_ms", "accepted_at_ms", "terminal_at_ms")
    }
    if not all(
        isinstance(value, int) and not isinstance(value, bool) and value > 0
        for value in timestamps.values()
    ):
        return ["dispatch_binding_timestamp_invalid"]
    reserved_at_ms = int(timestamps["reserved_at_ms"])
    terminal_at_ms = int(timestamps["terminal_at_ms"])
    if reserved_at_ms < int(created_at.timestamp() * 1000):
        return ["dispatch_binding_reserved_before_lane_created"]
    if str(lane.get("status") or "") in TERMINAL_STATUSES:
        lane_terminal_at = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
        if lane_terminal_at is None:
            return ["dispatch_binding_lane_terminal_at_required"]
        if terminal_at_ms > int(lane_terminal_at.timestamp() * 1000):
            return ["dispatch_binding_terminal_after_lane_completion"]
    return []


def expected_attempt_correlation(lane: dict[str, Any], runtime: dict[str, Any]) -> dict[str, str] | None:
    return build_attempt_correlation_key(
        parent_job_id=runtime.get("parent_job_id"),
        lane_id=lane.get("lane_id"),
        phase=runtime.get("phase"),
        attempt_id=runtime.get("attempt_id"),
        retry_count=runtime.get("retry_count"),
    )


def bind_attempt_correlation(lane: dict[str, Any], runtime: dict[str, Any]) -> None:
    """Persist only a privacy-safe, deterministic attempt key.

    Imported isolated-session metadata may already contain the key.  When it
    does, the lane contract must derive the identical key before it can count.
    """
    expected = expected_attempt_correlation(lane, runtime)
    observed = as_dict(runtime.get("attempt_correlation"))
    observed_hash = str(observed.get("key_hash") or "")
    if expected is not None and observed_hash and observed_hash != expected["key_hash"]:
        raise SystemExit("attempt correlation does not match the declared parent job, lane, phase, and attempt")
    if expected is not None:
        runtime["attempt_correlation"] = expected


def has_v2_dispatch_binding_provenance(runtime: dict[str, Any]) -> bool:
    """Return whether a runtime is protected by v2 dispatch-binding privacy rules."""
    return (
        str(runtime.get("token_attribution_source") or "")
        == "openclaw_isolated_session_store_v2"
        or bool(as_dict(runtime.get("dispatch_binding")))
    )


def scrub_v2_dispatch_binding_runtime_identifiers(
    runtime: dict[str, Any],
    *,
    canonical_source_fields: dict[str, Any] | None = None,
) -> None:
    """Keep v2 binding provenance free of raw caller/session identifiers.

    A v2 binding is the privacy-safe source-to-attempt join. Later status
    updates may contain convenient raw session metadata, but must never put it
    back into the lane register once that protected provenance exists.
    """
    if not has_v2_dispatch_binding_provenance(runtime):
        return
    canonical = canonical_source_fields or {}
    for key in ("session_key", "session_id", "session_label", "task_name"):
        raw = runtime.pop(key, None)
        raw_hash = hash_reference(raw)
        if raw_hash:
            runtime[f"caller_{key}_hash"] = raw_hash
    for key in V2_CANONICAL_SOURCE_FIELDS:
        raw = runtime.get(key)
        source_value = canonical.get(key)
        if source_value not in (None, ""):
            runtime[key] = source_value
            continue
        if raw not in (None, ""):
            runtime.pop(key, None)
            raw_hash = hash_reference(raw)
            if raw_hash:
                runtime[f"caller_{key}_hash"] = raw_hash


def usage_credit_assessment(
    lane: dict[str, Any],
    runtime: dict[str, Any],
    *,
    receipt_store_path: Path | None = None,
    require_reverification: bool = False,
    source_reverified_this_action: bool = False,
    isolated_agent_state_root: Path | None = None,
    codex_sessions_root: Path | None = None,
) -> dict[str, Any]:
    """Classify whether usage may count toward cost, savings, or efficiency.

    Raw observations are intentionally retained when this returns false.  They
    are audit telemetry, not evidence that a model lane consumed that usage.
    """
    required = telemetry_enforcement_applies(lane, runtime)
    assessment = runtime_token_assessment(runtime)
    source = str(runtime.get("token_attribution_source") or "")
    run_id = str(runtime.get("run_id") or "")
    session_ref = str(runtime.get("session_ref_hash") or "")
    correlation = as_dict(runtime.get("attempt_correlation"))
    reasons: list[str] = []
    if not required:
        return {
            "required": False,
            "usage_creditable": False,
            "status": "historical_observed_unverified",
            "reasons": ["pre_cutover_or_missing_timestamp"],
        }
    if assessment.get("token_valid") is not True:
        reasons.append(str(assessment.get("status") or "attribution_incomplete"))
    observed_at = parse_utc(lane.get("created_at_utc")) or parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    if observed_at is None:
        reasons.append("telemetry_timestamp_required")
    if not terminal_timestamp_is_consistent(lane):
        reasons.append("terminal_timestamp_before_created_at")
    if source not in TRUSTED_TOKEN_ATTRIBUTION_SOURCES:
        reasons.append("trusted_token_source_required")
    elif source == "codex_native_rollout_jsonl":
        if runtime.get("provenance_label") != "codex_native_rollout" or not runtime.get("source_run_id_hash"):
            reasons.append("native_rollout_provenance_required")
    elif source == "openclaw_isolated_session_store_v1":
        if runtime.get("agent_id") not in CONFIGURED_ISOLATED_AGENT_IDS or not runtime.get("source_snapshot_fingerprint"):
            reasons.append("isolated_session_snapshot_provenance_required")
        reasons.append("isolated_dispatch_binding_required")
    elif source == "openclaw_isolated_session_store_v2":
        binding = as_dict(runtime.get("dispatch_binding"))
        expected = expected_attempt_correlation(lane, runtime)
        expected_token = (
            dispatch_binding_token_hash_for_attempt(attempt_correlation_hash=expected["key_hash"])
            if expected is not None
            else None
        )
        required_binding_fields = (
            "schema",
            "binding_token_hash",
            "child_session_key_hash",
            "dispatch_nonce_hash",
            "target_agent_id_hash",
            "registry_run_id_hash",
            "reserved_at_ms",
            "accepted_at_ms",
            "terminal_at_ms",
            "terminal_status",
        )
        if (
            runtime.get("agent_id") not in CONFIGURED_ISOLATED_AGENT_IDS
            or not runtime.get("source_snapshot_fingerprint")
            or any(key not in binding for key in required_binding_fields)
            or binding.get("schema") != "veritas.isolated_dispatch_binding.v1"
            or binding.get("terminal_status") != "ok"
            or binding.get("binding_token_hash") != expected_token
        ):
            reasons.append("isolated_dispatch_binding_provenance_required")
    if not run_id:
        reasons.append("source_run_id_required")
    if not session_ref:
        reasons.append("session_reference_required")
    expected = expected_attempt_correlation(lane, runtime)
    if expected is None or correlation.get("key_hash") != expected.get("key_hash"):
        reasons.append("attempt_correlation_required")
    if source in TRUSTED_TOKEN_ATTRIBUTION_SOURCES:
        receipt_reasons = verify_usage_source_receipt(
            lane,
            runtime,
            receipt_store_path or usage_receipt_store_path(DEFAULT_REGISTER),
            isolated_agent_state_root=isolated_agent_state_root,
            codex_sessions_root=codex_sessions_root,
        )
        reasons.extend(receipt_reasons)
        if require_reverification and not source_reverified_this_action:
            reasons.append("source_receipt_reverification_required")
    return {
        "required": True,
        "usage_creditable": not reasons,
        "status": "creditable" if not reasons else "blocked",
        "reasons": sorted(set(reasons)),
        "token_assessment": assessment.get("status"),
        "token_attribution_source": source or None,
    }


def requires_attribution_grade_closeout(lane: dict[str, Any], runtime: dict[str, Any]) -> bool:
    """Compatibility name for the strict post-cutover model-lane contract."""
    return telemetry_enforcement_applies(lane, runtime)


def accepted_missing_usage_classification(runtime: dict[str, Any]) -> str | None:
    value = runtime.get("token_attribution_source")
    if value in ACCEPTED_MISSING_USAGE_CLASSIFICATIONS:
        return str(value)
    if runtime.get("usage_unavailable_reason") in USAGE_UNAVAILABLE_REASONS and value in (None, ""):
        return "provider_usage_unavailable"
    return None


def token_closeout_status(lane: dict[str, Any], runtime: dict[str, Any]) -> str | None:
    if not runtime.get("model_path"):
        return None
    if runtime_has_token_value(runtime):
        return str(runtime_token_assessment(runtime).get("status") or "attribution_incomplete")
    classification = accepted_missing_usage_classification(runtime)
    if classification:
        return classification
    status = str(lane.get("status") or "")
    if status == "complete":
        return "missing_usage_classification_required"
    if status in ACTIVE_STATUSES:
        return "pending_token_metadata"
    return None


def completed_after_token_closeout_guard(lane: dict[str, Any]) -> bool:
    completed_at = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    guard_start = parse_utc(TOKEN_CLOSEOUT_GUARD_START_UTC)
    if completed_at is None or guard_start is None:
        return False
    return completed_at >= guard_start


def completed_after_token_hard_enforcement(lane: dict[str, Any]) -> bool:
    completed_at = parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    hard_start = parse_utc(TOKEN_CLOSEOUT_HARD_ENFORCEMENT_START_UTC)
    if completed_at is None or hard_start is None:
        return False
    return completed_at >= hard_start


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def route_by_id(workflow_id: str) -> dict[str, Any]:
    index = load_dict(WORKFLOW_INDEX)
    wanted = workflow_id.upper()
    for route in as_list(index.get("routes")):
        if isinstance(route, dict) and str(route.get("workflow_id") or "").upper() == wanted:
            return route
    return {}


def empty_register() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_authority": "06. Playbooks/Active Workflows.md",
        "workflow_route_index": rel(WORKFLOW_INDEX),
        "lanes": [],
        "stop_lines": [
            "This register coordinates helper-lane leases only; it does not spawn helpers or schedule work.",
            "No two active lanes may write the same surface.",
            "Completion requires proof artifacts or acceptance commands.",
            "No canon/portfolio/config/auth/runtime/destructive/capital/trade/account/money authority.",
        ],
    }


def load_register(path: Path) -> dict[str, Any]:
    register = load_dict(path)
    if not register:
        return empty_register()
    register.setdefault("schema", SCHEMA)
    register.setdefault("authority_boundary", dict(AUTHORITY_BOUNDARY))
    register.setdefault("lanes", [])
    register.setdefault("stop_lines", empty_register()["stop_lines"])
    return register


def lane_id(workflow_id: str, workstream_id: str) -> str:
    return f"{workflow_id.upper()}::{workstream_id.strip().lower()}"


def find_lane(register: dict[str, Any], workflow_id: str, workstream_id: str) -> dict[str, Any] | None:
    target = lane_id(workflow_id, workstream_id)
    for lane in as_list(register.get("lanes")):
        if isinstance(lane, dict) and lane.get("lane_id") == target:
            return lane
    return None


def default_forbidden_writes(route: dict[str, Any]) -> list[str]:
    forbidden = [
        "SOUL.md",
        "AGENTS.md",
        "TOOLS.md",
        "MEMORY.md",
        "03. Portfolio/*",
        "state/finance/*",
        "data/finance/universe-v1.json",
        "09. Archive/*",
        "config/auth/runtime/channel/credential surfaces",
    ]
    if route.get("owner_action_required"):
        forbidden.append("owner-gated route surfaces without main-session approval")
    return forbidden


def build_lane_template(workflow_id: str, workstream_id: str, owner: str = "unassigned") -> dict[str, Any]:
    route = route_by_id(workflow_id)
    now = utc_now()
    read_first: list[str] = []
    if route.get("continuity_note"):
        read_first.append(route["continuity_note"])
    if route.get("primary_route_artifact") and not route.get("primary_pending"):
        read_first.append(route["primary_route_artifact"])
    read_first.extend(as_list(route.get("secondary_artifacts")))
    acceptance = as_list(route.get("validator_commands")) + ["python scripts\\concurrent_lane_manager.py --validate"]
    return {
        "lane_id": lane_id(workflow_id, workstream_id),
        "workflow_id": workflow_id.upper(),
        "workstream_id": workstream_id,
        "owner": owner,
        "status": "planned",
        "mode": "Spawn distinct-output" if route.get("safe_for_helper_lane", True) else "Main-session only",
        "created_at_utc": now,
        "updated_at_utc": now,
        "lease_expires_at_utc": None,
        "read_first": read_first[:6],
        "allowed_writes": [],
        "forbidden_writes": default_forbidden_writes(route),
        "acceptance_commands": acceptance,
        "proof_artifacts": [],
        "stop_lines": as_list(route.get("stop_lines")),
        "notes": [],
        "merge_required_by_main": True,
        "authority_boundary": route.get("authority_boundary") or "derived helper-lane coordination only; no approval/execution/mutation authority",
    }


def upsert_lane(register: dict[str, Any], lane: dict[str, Any]) -> None:
    lanes = as_list(register.get("lanes"))
    for index, existing in enumerate(lanes):
        if isinstance(existing, dict) and existing.get("lane_id") == lane.get("lane_id"):
            lanes[index] = lane
            register["lanes"] = lanes
            return
    lanes.append(lane)
    register["lanes"] = lanes


def cli_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise SystemExit(f"invalid boolean metadata value: {value}")


def bounded_route_value(value: Any, pattern: re.Pattern[str], field: str) -> str:
    """Return bounded route metadata without accepting arbitrary session text."""
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise SystemExit(f"invalid Codex {field} metadata")
    return value


def exact_rollout_filename_match(path: Path, session_id: str) -> bool:
    """Accept a session id only as a complete rollout filename component."""
    stem = path.stem
    return stem == session_id or stem.endswith(f"-{session_id}") or stem.startswith(f"{session_id}-")


def is_codex_subagent_source(value: Any) -> bool:
    """Validate only the bounded subagent provenance shape without retaining it."""
    source = as_dict(value)
    if set(source) != {"subagent"}:
        return False
    subagent = as_dict(source.get("subagent"))
    if set(subagent) != {"thread_spawn"}:
        return False
    spawned = as_dict(subagent.get("thread_spawn"))
    required = ("parent_thread_id", "depth", "agent_path", "agent_nickname", "agent_role")
    if set(spawned) != set(required):
        return False
    if strict_runtime_int(spawned.get("depth")) is None or int(spawned["depth"]) < 1:
        return False
    if spawned.get("agent_role") is not None and not (
        isinstance(spawned.get("agent_role"), str)
        and CODEX_SUBAGENT_IDENTIFIER_PATTERN.fullmatch(spawned["agent_role"])
    ):
        return False
    agent_path = spawned.get("agent_path")
    if not isinstance(agent_path, str) or not CODEX_TASK_PATH_PATTERN.fullmatch(agent_path):
        return False
    return all(
        isinstance(spawned[key], str) and CODEX_SUBAGENT_IDENTIFIER_PATTERN.fullmatch(spawned[key])
        for key in ("parent_thread_id", "agent_nickname")
    )


def canonical_codex_model_path(provider: Any, model: Any) -> str:
    provider_value = bounded_route_value(provider, ROUTE_PROVIDER_PATTERN, "model provider")
    model_value = bounded_route_value(model, ROUTE_MODEL_PATTERN, "model")
    return model_value if "/" in model_value else f"{provider_value}/{model_value}"


def bounded_execution_backend(value: Any, field: str) -> str:
    if not isinstance(value, str) or value not in EXECUTION_BACKENDS:
        raise SystemExit(f"invalid {field} metadata")
    return value


def has_native_rollout_provenance(runtime: dict[str, Any]) -> bool:
    return runtime.get("token_attribution_source") == "codex_native_rollout_jsonl" or runtime.get("provenance_label") == "codex_native_rollout"


def enforce_native_execution_backend(runtime: dict[str, Any], args: argparse.Namespace, *, persist: bool) -> None:
    """Keep native rollout provenance bound to its only valid execution backend."""
    if not has_native_rollout_provenance(runtime):
        return
    for key in ("expected_execution_backend", "actual_execution_backend"):
        supplied = getattr(args, key, None)
        existing = runtime.get(key)
        if supplied not in (None, "", "codex_native_subagent") or existing not in (None, "", "codex_native_subagent"):
            raise SystemExit("Codex native rollout provenance requires immutable codex_native_subagent execution backend")
        if persist:
            runtime[key] = "codex_native_subagent"


def bounded_cohort_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not COHORT_IDENTIFIER_PATTERN.fullmatch(value):
        raise SystemExit(f"invalid {field} metadata")
    return value


def load_codex_native_rollout(session_id: str, sessions_root: Path) -> dict[str, Any]:
    """Load a single finished Codex rollout using only fixed metadata fields.

    This deliberately never descends into response_item, prompt, reasoning, tool,
    authentication, or account payloads.  JSONL files are considered only by their
    session_meta identity and a small fixed event allowlist.
    """
    if not CODEX_SESSION_ID_PATTERN.fullmatch(session_id):
        raise SystemExit("Codex session id must be an exact safe session identifier")
    try:
        root = sessions_root.expanduser().resolve(strict=True)
    except OSError as exc:
        raise SystemExit("Codex sessions root is unavailable") from exc
    if not root.is_dir():
        raise SystemExit("Codex sessions root is not a directory")

    candidates = [candidate for candidate in root.rglob("*.jsonl") if exact_rollout_filename_match(candidate, session_id)]
    if len(candidates) != 1:
        raise SystemExit("Codex rollout session must resolve to exactly one filename candidate")

    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            raise SystemExit("Codex rollout path escapes the sessions root")
        session_meta_count = 0
        non_subagent_meta_count = 0
        matched_subagent_meta = False
        observed_provider: str | None = None
        observed_model: str | None = None
        observed_effort: str | None = None
        last_usage: dict[str, int] | None = None
        last_usage_index = -1
        completion_index = -1
        try:
            with resolved.open("r", encoding="utf-8") as handle:
                for index, line in enumerate(handle):
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise SystemExit("malformed Codex rollout JSONL") from exc
                    if not isinstance(row, dict):
                        raise SystemExit("malformed Codex rollout record")
                    kind = row.get("type")
                    payload = as_dict(row.get("payload"))
                    if kind == "session_meta":
                        if payload.get("id") == session_id:
                            if is_codex_subagent_source(payload.get("source")):
                                session_meta_count += 1
                                matched_subagent_meta = True
                                observed_provider = bounded_route_value(payload.get("model_provider"), ROUTE_PROVIDER_PATTERN, "model provider")
                            else:
                                non_subagent_meta_count += 1
                    elif matched_subagent_meta and kind == "turn_context":
                        model = payload.get("model")
                        effort = payload.get("effort")
                        if model is not None:
                            normalized_model = canonical_codex_model_path(observed_provider, model)
                            if observed_model is not None and observed_model != normalized_model:
                                raise SystemExit("Codex rollout has conflicting turn-context model metadata")
                            observed_model = normalized_model
                        if effort is not None:
                            normalized_effort = bounded_route_value(effort, ROUTE_THINKING_PATTERN, "effort")
                            if observed_effort is not None and observed_effort != normalized_effort:
                                raise SystemExit("Codex rollout has conflicting turn-context effort metadata")
                            observed_effort = normalized_effort
                    elif matched_subagent_meta and kind == "event_msg":
                        event_type = payload.get("type")
                        if event_type == "token_count":
                            usage = as_dict(payload.get("total_token_usage"))
                            if not usage:
                                usage = as_dict(as_dict(payload.get("info")).get("total_token_usage"))
                            required = ("input_tokens", "cached_input_tokens", "output_tokens")
                            if not usage or any(strict_runtime_int(usage.get(key)) is None for key in required):
                                raise SystemExit("Codex rollout has malformed or negative token usage")
                            last_usage = {key: int(usage[key]) for key in required}
                            if last_usage["cached_input_tokens"] > last_usage["input_tokens"]:
                                raise SystemExit("Codex rollout cached input tokens exceed input tokens")
                            if "total_tokens" in usage:
                                reported_total = strict_runtime_int(usage.get("total_tokens"))
                                if reported_total is None or reported_total != last_usage["input_tokens"] + last_usage["output_tokens"]:
                                    raise SystemExit("Codex rollout total token usage is inconsistent")
                            reasoning = usage.get("reasoning_output_tokens")
                            if reasoning is not None:
                                parsed_reasoning = strict_runtime_int(reasoning)
                                if parsed_reasoning is None:
                                    raise SystemExit("Codex rollout has malformed reasoning token metadata")
                                last_usage["reasoning_output_tokens"] = parsed_reasoning
                            last_usage_index = index
                        elif event_type == "task_complete":
                            completion_index = index
        except OSError as exc:
            raise SystemExit("Codex rollout cannot be read") from exc
        if session_meta_count:
            if session_meta_count != 1 or non_subagent_meta_count:
                raise SystemExit("Codex rollout has ambiguous matching session metadata")
            matches.append({
                "path": resolved,
                "source_snapshot_fingerprint": sha256_file(resolved),
                "provider": observed_provider,
                "model": observed_model,
                "effort": observed_effort,
                "usage": last_usage,
                "last_usage_index": last_usage_index,
                "completion_index": completion_index,
            })
    if len(matches) != 1:
        raise SystemExit("Codex rollout session must resolve to exactly one file")
    record = matches[0]
    if not record["provider"] or not record["model"] or not record["effort"]:
        raise SystemExit("Codex rollout lacks observed model or effort metadata")
    if record["usage"] is None or record["last_usage_index"] < 0:
        raise SystemExit("Codex rollout lacks total token usage")
    if record["completion_index"] <= record["last_usage_index"]:
        raise SystemExit("Codex rollout lacks completion after final token usage")
    return record


def import_codex_native_rollout_usage(runtime: dict[str, Any], args: argparse.Namespace) -> None:
    if not getattr(args, "import_codex_native_rollout", False):
        return
    session_id = str(getattr(args, "codex_session_id", "") or runtime.get("session_id") or "")
    if not session_id:
        raise SystemExit("Codex native import requires --codex-session-id")
    if runtime.get("model_path"):
        runtime.setdefault("expected_model_path", str(runtime["model_path"]))
    if runtime.get("thinking"):
        runtime.setdefault("expected_thinking", str(runtime["thinking"]))
    for key in ("expected_execution_backend", "actual_execution_backend"):
        supplied = runtime.get(key)
        if supplied not in (None, "", "codex_native_subagent"):
            raise SystemExit("Codex native rollout provenance requires codex_native_subagent execution backend")
        runtime[key] = "codex_native_subagent"
    if runtime.get("expected_model_path"):
        runtime["expected_model_path"] = bounded_route_value(runtime["expected_model_path"], ROUTE_MODEL_PATTERN, "expected model")
    if runtime.get("expected_thinking"):
        runtime["expected_thinking"] = bounded_route_value(runtime["expected_thinking"], ROUTE_THINKING_PATTERN, "expected effort")
    runtime["expected_execution_backend"] = bounded_execution_backend(runtime["expected_execution_backend"], "expected execution backend")
    runtime["actual_execution_backend"] = bounded_execution_backend(runtime["actual_execution_backend"], "actual execution backend")
    record = load_codex_native_rollout(session_id, Path(getattr(args, "codex_sessions_root", DEFAULT_CODEX_SESSIONS_ROOT)))
    usage = record["usage"]
    assert isinstance(usage, dict)
    fork_policy = str(runtime.get("fork_policy") or "")
    if fork_policy not in FORK_POLICIES:
        raise SystemExit("Codex native import requires an explicit fork policy")
    baseline_fields = {
        "input_tokens": strict_runtime_int(runtime.get("fork_baseline_input_tokens")),
        "cached_input_tokens": strict_runtime_int(runtime.get("fork_baseline_cached_input_tokens")),
        "output_tokens": strict_runtime_int(runtime.get("fork_baseline_output_tokens")),
    }
    if fork_policy == "none":
        if any(value not in (None, 0) for value in baseline_fields.values()):
            raise SystemExit("fork_turns=none cannot declare a nonzero inherited token baseline")
        baseline_fields = {key: 0 for key in baseline_fields}
    elif any(value is None for value in baseline_fields.values()):
        raise SystemExit("forked Codex native import requires explicit inherited token baselines")
    attributed: dict[str, int] = {}
    for key, baseline in baseline_fields.items():
        assert baseline is not None
        observed = int(usage[key])
        if baseline > observed:
            raise SystemExit("Codex fork baseline exceeds cumulative rollout usage")
        attributed[key] = observed - baseline
    if attributed["cached_input_tokens"] > attributed["input_tokens"]:
        raise SystemExit("attributed cached input exceeds attributed input after fork-baseline subtraction")
    input_tokens = attributed["input_tokens"]
    output_tokens = attributed["output_tokens"]
    runtime.update({
        "session_id_hash": hash_reference(session_id),
        "session_ref_hash": hash_reference(session_id),
        "actual_model_path": record["model"],
        "actual_thinking": record["effort"],
        "model_path": record["model"],
        "thinking": record["effort"],
        "input_tokens": input_tokens,
        "cached_input_tokens": attributed["cached_input_tokens"],
        "cache_write_tokens": 0,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_token_semantics": "inclusive_cached",
        "source_input_total_tokens": input_tokens,
        "source_total_tokens_fresh": True,
        "token_attribution_source": "codex_native_rollout_jsonl",
        "fork_policy": fork_policy,
        "fork_baseline_applied": True,
        # Persist the exact baseline used for the delta.  Revalidation must
        # recompute the same calculation instead of inferring a zero baseline
        # from a mutable receipt or a caller convention.
        "fork_baseline_input_tokens": baseline_fields["input_tokens"],
        "fork_baseline_cached_input_tokens": baseline_fields["cached_input_tokens"],
        "fork_baseline_output_tokens": baseline_fields["output_tokens"],
        "source_cumulative_input_tokens": usage["input_tokens"],
        "source_cumulative_cached_input_tokens": usage["cached_input_tokens"],
        "source_cumulative_output_tokens": usage["output_tokens"],
        "source_snapshot_fingerprint": record["source_snapshot_fingerprint"],
    })
    if "reasoning_output_tokens" in usage and fork_policy == "none":
        runtime["reasoning_output_tokens"] = usage["reasoning_output_tokens"]
    elif "reasoning_output_tokens" in usage:
        runtime["source_cumulative_reasoning_output_tokens"] = usage["reasoning_output_tokens"]
    for key in ("session_key", "session_id", "session_label", "task_name", "run_id", "agent_role"):
        value = runtime.pop(key, None)
        value_hash = hash_reference(value)
        if value_hash:
            runtime[f"caller_{key}_hash"] = value_hash
    # The source transcript identity is retained only as a bounded hash.  This
    # gives the ledger a deterministic source-run key without storing a raw
    # session identifier or allowing a caller-supplied fallback run ID.
    session_hash = hash_reference(session_id)
    if not session_hash:
        raise SystemExit("Codex native rollout session identity could not be hashed")
    runtime["run_id"] = f"codex:{session_hash}"
    runtime["source_run_id_hash"] = session_hash
    runtime["agent_role"] = "codex_native_subagent"
    runtime["provenance_label"] = "codex_native_rollout"


def import_isolated_session_usage(runtime: dict[str, Any], args: argparse.Namespace) -> None:
    if not getattr(args, "import_isolated_session_usage", False):
        return
    agent_id = str(runtime.get("agent_id") or "")
    if agent_id not in CONFIGURED_ISOLATED_AGENT_IDS:
        raise SystemExit("isolated session import requires an explicitly allowlisted --agent-id")
    session_id = runtime.get("session_id")
    session_key = runtime.get("session_key")
    if not session_id and not session_key:
        raise SystemExit("isolated session import requires --session-id or --session-key")
    state_root = Path(getattr(args, "isolated_agent_state_root", None) or DEFAULT_AGENT_STATE_ROOT)
    if getattr(args, "require_dispatch_binding", False):
        correlation = as_dict(runtime.get("attempt_correlation"))
        correlation_hash = str(correlation.get("key_hash") or "")
        if not re.fullmatch(r"[a-f0-9]{64}", correlation_hash):
            raise SystemExit("isolated dispatch binding import requires a deterministic attempt correlation")
        expected_binding_token_hash = dispatch_binding_token_hash_for_attempt(
            attempt_correlation_hash=correlation_hash
        )
        record, errors = load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=expected_binding_token_hash,
            agent_state_root=state_root,
            state_db_path=Path(
                getattr(args, "isolated_agent_state_db", None) or DEFAULT_OPENCLAW_STATE_DB
            ),
            session_id=session_id,
            session_key=session_key,
        )
        if record is None:
            detail = ", ".join(sorted(set(errors))) if errors else "unavailable"
            raise SystemExit(f"no verified terminal dispatch binding matched the requested isolated session: {detail}")
    else:
        payload = load_allowlisted_session_usage([agent_id], state_root)
        record = find_session_usage_record(
            payload,
            agent_id=agent_id,
            session_id=session_id,
            session_key=session_key,
        )
    if record is None:
        raise SystemExit("no unique fresh terminal usage record matched the requested isolated session")
    existing_model = runtime.get("model_path")
    if existing_model and existing_model != record.get("model_path"):
        raise SystemExit("isolated session model does not match declared lane model")
    mapped = {
        "agent_role": record.get("agent_role"),
        "session_ref_hash": record.get("session_ref_hash"),
        "session_key_hash": record.get("session_key_hash"),
        "session_id_hash": record.get("session_id_hash"),
        "run_id": record.get("run_id"),
        "model_path": record.get("model_path"),
        "model_provider": record.get("model_provider"),
        "input_tokens": record.get("input_tokens"),
        "cached_input_tokens": record.get("cached_input_tokens"),
        "cache_write_tokens": record.get("cache_write_tokens"),
        "output_tokens": record.get("output_tokens"),
        "total_tokens": record.get("total_tokens"),
        "input_token_semantics": record.get("input_token_semantics"),
        "source_input_total_tokens": record.get("source_input_total_tokens"),
        "source_total_tokens_fresh": record.get("source_total_tokens_fresh"),
        "usage_at_utc": record.get("usage_at_utc"),
        "usage_time_source": record.get("usage_time_source"),
        # Preserve source-derived duration only when the allowlisted session
        # record exposes it.  Consumers keep absent duration unknown rather
        # than inventing a zero-latency observation.
        "duration_ms": record.get("duration_ms"),
        "source_estimated_cost_usd": record.get("source_estimated_cost_usd"),
        "source_estimated_cost_semantics": record.get("source_estimated_cost_semantics"),
        "token_attribution_source": record.get("token_attribution_source"),
        "source_snapshot_fingerprint": record.get("source_snapshot_fingerprint"),
        "attempt_correlation": record.get("attempt_correlation"),
        "dispatch_binding": record.get("dispatch_binding"),
        "pricing_unavailable_reason": record.get("pricing_unavailable_reason"),
    }
    runtime.update({key: value for key, value in mapped.items() if value is not None})
    # Raw identifiers were required only for the local source join. Keep their
    # hashes for audit, never the values, task name, or session text.
    scrub_v2_dispatch_binding_runtime_identifiers(
        runtime,
        canonical_source_fields={
            key: record.get(key)
            for key in V2_CANONICAL_SOURCE_FIELDS
            if record.get(key) not in (None, "")
        },
    )
    runtime.setdefault("access_mode", "unknown")
    runtime.setdefault("speed_mode", "unknown")


def apply_runtime_metadata(
    lane: dict[str, Any],
    args: argparse.Namespace,
    *,
    persist_usage_receipt: bool = True,
) -> bool:
    runtime = as_dict(lane.get("runtime"))
    # Preserve source-derived session hashes when a later status update carries
    # raw identifiers. The update may record caller hashes, but it must not
    # replace the bound source identity before it is scrubbed.
    protected_dispatch_binding_before_metadata = has_v2_dispatch_binding_provenance(runtime)
    protected_source_fields = (
        {
            key: runtime.get(key)
            for key in V2_CANONICAL_SOURCE_FIELDS
            if runtime.get(key) not in (None, "")
        }
        if protected_dispatch_binding_before_metadata
        else {}
    )
    enforce_native_execution_backend(runtime, args, persist=False)
    caller_supplied_session_key = getattr(args, "session_key", None) not in (None, "")
    caller_supplied_session_id = getattr(args, "session_id", None) not in (None, "")
    for key in (
        "agent_id",
        "agent_role",
        "parent_job_id",
        "phase",
        "authority_class",
        "objective",
        "deliverable",
        "closeout_destination",
        "session_key",
        "session_id",
        "session_label",
        "task_name",
        "run_id",
        "model_path",
        "model_provider",
        "thinking",
        "expected_model_path",
        "expected_thinking",
        "expected_execution_backend",
        "actual_execution_backend",
        "task_shape",
        "write_scope",
        "handoff_file_count",
        "handoff_total_bytes",
        "handoff_context_tokens",
        "fork_policy",
        "usage_unavailable_reason",
        "fork_baseline_input_tokens",
        "fork_baseline_cached_input_tokens",
        "fork_baseline_output_tokens",
        "fork_baseline_tool_calls",
        "max_gross_tokens",
        "max_cached_replay_tokens",
        "max_tool_calls",
        "max_elapsed_seconds",
        "observed_tool_calls",
        "observed_elapsed_seconds",
        "retry_count",
        "attempt_number",
        "attempt_id",
        "incident_code",
        "token_attribution_source",
        "input_token_semantics",
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "output_tokens",
        "total_tokens",
        "source_input_total_tokens",
        "access_mode",
        "speed_mode",
        "usage_at_utc",
        "usage_time_source",
        "outcome_status",
        "main_acceptance_status",
        "main_acceptance_evidence",
        "root_objective_id",
        "objective_slice_id",
        "predecessor_lane_id",
        "cumulative_attempt_number",
        "cumulative_retry_count",
        "accepted_slice_id",
        "technical_acceptance_status",
        "accounting_status",
        "administrative_closure_status",
        "activation_status",
        "validator_result",
        "closure_durability",
        "estimated_cost_usd",
        "source_estimated_cost_usd",
    ):
        value = getattr(args, key, None)
        if value not in (None, ""):
            if key in V2_CANONICAL_SOURCE_FIELDS and protected_dispatch_binding_before_metadata:
                caller_hash = hash_reference(value)
                if caller_hash:
                    runtime[f"caller_{key}_hash"] = caller_hash
                continue
            runtime[key] = value
    source_fresh = cli_bool(getattr(args, "source_total_tokens_fresh", None))
    if source_fresh is not None:
        runtime["source_total_tokens_fresh"] = source_fresh
    env_defaults = {
        "session_label": "OPENCLAW_SESSION_LABEL",
        "session_id": "OPENCLAW_SESSION_ID",
        "session_key": "OPENCLAW_SESSION_KEY",
        "run_id": "OPENCLAW_RUN_ID",
        "model_path": "OPENCLAW_MODEL_PATH",
        "input_tokens": "OPENCLAW_INPUT_TOKENS",
        "cached_input_tokens": "OPENCLAW_CACHED_INPUT_TOKENS",
        "output_tokens": "OPENCLAW_OUTPUT_TOKENS",
        "total_tokens": "OPENCLAW_TOTAL_TOKENS",
        "token_attribution_source": "OPENCLAW_TOKEN_ATTRIBUTION_SOURCE",
        "estimated_cost_usd": "OPENCLAW_ESTIMATED_COST_USD",
    }
    for key, env_name in env_defaults.items():
        if key == "run_id" and protected_dispatch_binding_before_metadata:
            caller_hash = hash_reference(os.environ.get(env_name))
            if caller_hash:
                runtime["caller_run_id_hash"] = caller_hash
            continue
        if not runtime.get(key):
            value = os.environ.get(env_name)
            if value:
                runtime[key] = value
                if key == "model_path":
                    runtime.setdefault("model_attribution_source", f"env:{env_name}")
                elif key in {"input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"}:
                    runtime.setdefault("token_attribution_source", f"env:{env_name}")
                else:
                    runtime.setdefault("session_attribution_source", f"env:{env_name}")
    for key in ("expected_execution_backend", "actual_execution_backend"):
        if runtime.get(key) not in (None, ""):
            runtime[key] = bounded_execution_backend(runtime[key], key.replace("_", " "))
    for key in ("task_shape", "write_scope"):
        if runtime.get(key) not in (None, ""):
            runtime[key] = bounded_cohort_identifier(runtime[key], key.replace("_", " "))
    if runtime.get("fork_policy") not in (None, "") and runtime.get("fork_policy") not in FORK_POLICIES:
        raise SystemExit("invalid fork policy")
    if runtime.get("usage_unavailable_reason") not in (None, "") and runtime.get("usage_unavailable_reason") not in USAGE_UNAVAILABLE_REASONS:
        raise SystemExit("invalid usage unavailable reason")
    if runtime.get("validator_result") not in (None, "") and runtime.get("validator_result") not in VALIDATOR_RESULTS:
        raise SystemExit("invalid validator result")
    if runtime.get("closure_durability") not in (None, "") and runtime.get("closure_durability") not in CLOSURE_DURABILITY_STATES:
        raise SystemExit("invalid closure durability")
    if runtime.get("usage_unavailable_reason") in USAGE_UNAVAILABLE_REASONS and runtime.get("token_attribution_source") in (None, ""):
        runtime["token_attribution_source"] = "provider_usage_unavailable"
    if caller_supplied_session_key and not protected_dispatch_binding_before_metadata:
        runtime["session_key_hash"] = hash_reference(runtime.get("session_key"))
    else:
        runtime.setdefault("session_key_hash", hash_reference(runtime.get("session_key")))
    if caller_supplied_session_id and not protected_dispatch_binding_before_metadata:
        runtime["session_id_hash"] = hash_reference(runtime.get("session_id"))
    else:
        runtime.setdefault("session_id_hash", hash_reference(runtime.get("session_id")))
    if (caller_supplied_session_key or caller_supplied_session_id) and not protected_dispatch_binding_before_metadata:
        runtime["session_ref_hash"] = runtime.get("session_id_hash") or runtime.get("session_key_hash")
    elif not runtime.get("session_ref_hash"):
        runtime["session_ref_hash"] = runtime.get("session_id_hash") or runtime.get("session_key_hash")
    runtime = {key: value for key, value in runtime.items() if value is not None}
    normalize_attempt_metadata(runtime)
    normalize_root_lineage_fields(runtime)
    if active_implementation_attempt_outcome_baseline_applies(lane, runtime):
        runtime.setdefault("incident_code", "")
        runtime.setdefault("incident_count", 0)
        lane.setdefault("outcome_events", [])
    normalize_resource_budgets(runtime)
    # The protected core producer token is derived only from the declared
    # parent/lane/phase/attempt before reading any caller-provided session.
    bind_attempt_correlation(lane, runtime)
    import_isolated_session_usage(runtime, args)
    import_codex_native_rollout_usage(runtime, args)
    canonical_v2_source_fields = dict(protected_source_fields)
    if (
        not canonical_v2_source_fields
        and getattr(args, "import_isolated_session_usage", False)
        and str(runtime.get("token_attribution_source") or "")
        == "openclaw_isolated_session_store_v2"
    ):
        canonical_v2_source_fields = {
            key: runtime.get(key)
            for key in V2_CANONICAL_SOURCE_FIELDS
            if runtime.get(key) not in (None, "")
        }
    # This is deliberately after every metadata/import path so a subsequent
    # --set-status cannot re-persist raw IDs on a protected v2 lane. A direct
    # caller switch to v2 has no imported canonical run and is therefore
    # hashed/quarantined rather than retained.
    scrub_v2_dispatch_binding_runtime_identifiers(
        runtime,
        canonical_source_fields=canonical_v2_source_fields,
    )
    # A later status update may describe caller metadata, but it cannot
    # overwrite the canonical source fields imported from a protected bind.
    runtime.update(canonical_v2_source_fields)
    bind_attempt_correlation(lane, runtime)
    # Model imports and the v2 canonical binding above may populate model_path
    # after the pre-import baseline. Initialize the clean outcome baseline here,
    # idempotently, so imported active implementation attempts start clean
    # without overwriting any existing incident/history state.
    if active_implementation_attempt_outcome_baseline_applies(lane, runtime):
        runtime.setdefault("incident_code", "")
        runtime.setdefault("incident_count", 0)
        lane.setdefault("outcome_events", [])
    source_reverified_this_action = bool(
        getattr(args, "import_isolated_session_usage", False)
        or getattr(args, "import_codex_native_rollout", False)
    )
    if source_reverified_this_action and persist_usage_receipt:
        persist_usage_source_receipt(
            lane,
            runtime,
            usage_receipt_store_path(Path(args.register)),
        )
    enforce_native_execution_backend(runtime, args, persist=True)
    normalize_resource_budgets(runtime)
    has_token_value = runtime_has_token_value(runtime)
    legacy_components = ("input_tokens", "cached_input_tokens", "output_tokens")
    if runtime.get("cache_write_tokens") in (None, "") and all(runtime.get(key) not in (None, "") for key in legacy_components):
        runtime["cache_write_tokens"] = 0
        runtime.setdefault("cache_write_attribution_source", "legacy_assumed_zero")
    if runtime.get("total_tokens") in (None, ""):
        token_parts: list[int] = []
        for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens"):
            value = runtime.get(key)
            if value in (None, ""):
                token_parts = []
                break
            try:
                token_parts.append(int(value))
            except (TypeError, ValueError):
                token_parts = []
                break
        if token_parts:
            runtime["total_tokens"] = sum(token_parts)
            has_token_value = True
    if has_token_value and not runtime.get("token_attribution_source"):
        runtime["token_attribution_source"] = "cli:concurrent_lane_manager"
    if runtime.get("model_path") and not runtime.get("model_provider"):
        model_path = str(runtime.get("model_path") or "")
        if "/" in model_path:
            runtime["model_provider"] = model_path.split("/", 1)[0]
    closeout_status = token_closeout_status(lane, runtime)
    if closeout_status:
        runtime["token_closeout_status"] = closeout_status
    # Use the register-adjacent receipt store for both ordinary runtime
    # stamping and closeout.  Falling back to the global default here would
    # make a correct custom-register import look uncredited (or, worse,
    # consult an unrelated receipt store).
    credit = usage_credit_assessment(
        lane,
        runtime,
        receipt_store_path=usage_receipt_store_path(Path(args.register)),
        source_reverified_this_action=source_reverified_this_action,
    )
    if credit.get("required"):
        runtime["telemetry_contract_version"] = MODEL_USAGE_CREDIT_CONTRACT_VERSION
        runtime["usage_credit_status"] = credit["status"]
        runtime["usage_creditable"] = credit["usage_creditable"] is True
        runtime["usage_credit_block_reasons"] = credit.get("reasons") or []
    if runtime:
        lane["runtime"] = runtime
    return source_reverified_this_action


def persist_reverified_usage_receipt_after_active_admission(
    lane: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    """Persist an imported source receipt only after active-lane admission.

    A preview/actual active admission uses the exact imported metadata without
    writing its receipt.  This keeps a rejected candidate from leaving receipt
    residue while preserving the normal source-reverification credit path once
    the candidate is known to be safe to persist.
    """
    source_reverified_this_action = bool(
        getattr(args, "import_isolated_session_usage", False)
        or getattr(args, "import_codex_native_rollout", False)
    )
    if not source_reverified_this_action:
        return
    runtime = as_dict(lane.get("runtime"))
    persist_usage_source_receipt(
        lane,
        runtime,
        usage_receipt_store_path(Path(args.register)),
    )
    credit = usage_credit_assessment(
        lane,
        runtime,
        receipt_store_path=usage_receipt_store_path(Path(args.register)),
        source_reverified_this_action=True,
    )
    if credit.get("required"):
        runtime["telemetry_contract_version"] = MODEL_USAGE_CREDIT_CONTRACT_VERSION
        runtime["usage_credit_status"] = credit["status"]
        runtime["usage_creditable"] = credit["usage_creditable"] is True
        runtime["usage_credit_block_reasons"] = credit.get("reasons") or []
    lane["runtime"] = runtime


def stamp_status_times(lane: dict[str, Any], status: str, previous_status: str | None = None) -> None:
    now = utc_now()
    lane["updated_at_utc"] = now
    if status == "running" and not lane.get("started_at_utc"):
        lane["started_at_utc"] = now
    if status in TERMINAL_STATUSES:
        if previous_status != status or not lane.get("ended_at_utc"):
            lane["ended_at_utc"] = now
        lane["lease_expires_at_utc"] = None
        if status == "complete":
            if previous_status != status or not lane.get("completed_at_utc"):
                lane["completed_at_utc"] = now
    elif status in ACTIVE_STATUSES:
        lane.pop("ended_at_utc", None)
        if status != "complete":
            lane.pop("completed_at_utc", None)
        if status == "planned":
            # Planned is an intentionally lease-free coordination state.
            lane["lease_expires_at_utc"] = None


def apply_plan(register: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if find_lane(register, args.plan, args.workstream):
        raise SystemExit(f"lane already exists: {lane_id(args.plan, args.workstream)}")
    lane = build_lane_template(args.plan, args.workstream, args.owner)
    lane["notes"].append("planned_from_workflow_route_index")
    upsert_lane(register, lane)
    return lane


def apply_lease(
    register: dict[str, Any],
    args: argparse.Namespace,
    *,
    persist_usage_receipt: bool = True,
) -> dict[str, Any]:
    lane = find_lane(register, args.lease, args.workstream) or build_lane_template(args.lease, args.workstream, args.owner)
    previous_status = str(lane.get("status") or "")
    if lane.get("status") == "complete" and not args.reopen_complete:
        raise SystemExit("cannot lease a completed lane")
    if lane.get("status") == "complete" and args.reopen_complete:
        lane["proof_artifacts"] = []
        lane.pop("completed_at_utc", None)
        lane.pop("ended_at_utc", None)
    lane["status"] = args.lane_status
    lane["owner"] = args.owner
    stamp_status_times(lane, args.lane_status, previous_status)
    if args.lane_status in {"leased", "running"}:
        lane["lease_expires_at_utc"] = (
            datetime.now(timezone.utc) + timedelta(hours=float(args.lease_hours))
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    apply_runtime_metadata(lane, args, persist_usage_receipt=persist_usage_receipt)
    validate_root_lineage(register, lane)
    enforce_rework_policy(register, lane)
    enforce_resource_budget(lane, previous_status)
    if args.allowed_write:
        lane["allowed_writes"] = sorted({normalize_path(item) for item in args.allowed_write})
    declare_usage_receipt_write(lane, Path(args.register), bool(
        getattr(args, "import_isolated_session_usage", False)
        or getattr(args, "import_codex_native_rollout", False)
    ))
    if args.read_first:
        base_read_first = [] if args.replace_contract else as_list(lane.get("read_first"))
        lane["read_first"] = sorted({normalize_path(item) for item in base_read_first + args.read_first})
    if args.acceptance_command:
        base_acceptance = [] if args.replace_contract else as_list(lane.get("acceptance_commands"))
        lane["acceptance_commands"] = base_acceptance + args.acceptance_command
    if args.note:
        lane["notes"] = as_list(lane.get("notes")) + args.note
    upsert_lane(register, lane)
    return lane


def apply_complete(register: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    lane = find_lane(register, args.complete, args.workstream)
    if lane is None:
        raise SystemExit(f"lane not found: {lane_id(args.complete, args.workstream)}")
    previous_status = str(lane.get("status") or "")
    previous_runtime = as_dict(lane.get("runtime"))
    previous_acceptance = str(previous_runtime.get("main_acceptance_status") or "")
    previous_acceptance_evidence = str(previous_runtime.get("main_acceptance_evidence") or "")
    previous_event_kind = str(previous_runtime.get("outcome_event_kind") or "")
    lane["status"] = "complete"
    stamp_status_times(lane, "complete", previous_status)
    source_reverified_this_action = apply_runtime_metadata(lane, args)
    validate_root_lineage(register, lane)
    declare_usage_receipt_write(lane, Path(args.register), source_reverified_this_action)
    budget_blocked = enforce_resource_budget(lane, previous_status)
    telemetry_blocked = False if budget_blocked else enforce_usage_creditability(
        lane,
        previous_status,
        receipt_store_path=usage_receipt_store_path(Path(args.register)),
        source_reverified_this_action=source_reverified_this_action,
        isolated_agent_state_root=Path(getattr(args, "isolated_agent_state_root", DEFAULT_AGENT_STATE_ROOT)),
        codex_sessions_root=Path(getattr(args, "codex_sessions_root", DEFAULT_CODEX_SESSIONS_ROOT)),
    )
    current_acceptance = str(as_dict(lane.get("runtime")).get("main_acceptance_status") or "")
    current_acceptance_evidence = str(as_dict(lane.get("runtime")).get("main_acceptance_evidence") or "")
    acceptance_changed = bool(args.main_acceptance_status) and current_acceptance != previous_acceptance
    acceptance_evidence_changed = (
        bool(args.main_acceptance_evidence)
        and current_acceptance_evidence != previous_acceptance_evidence
    )
    acceptance_update_requested = bool(args.main_acceptance_status or args.main_acceptance_evidence)
    event_kind = (
        "main_acceptance_update"
        if previous_status == "complete"
        and acceptance_update_requested
        and (
            acceptance_changed
            or acceptance_evidence_changed
            or previous_event_kind == "main_acceptance_update"
        )
        else "terminal_closeout"
    )
    if not budget_blocked and not telemetry_blocked:
        record_outcome_transition(
            lane,
            event_kind=event_kind,
            previous_status=previous_status,
            state_changed=(acceptance_changed or acceptance_evidence_changed) if event_kind == "main_acceptance_update" else None,
        )
    if args.proof:
        lane["proof_artifacts"] = sorted({normalize_path(item) for item in as_list(lane.get("proof_artifacts")) + args.proof})
    if args.note:
        lane["notes"] = as_list(lane.get("notes")) + args.note
    upsert_lane(register, lane)
    return lane


def apply_status(
    register: dict[str, Any],
    args: argparse.Namespace,
    *,
    persist_usage_receipt: bool = True,
) -> dict[str, Any]:
    lane = find_lane(register, args.set_status, args.workstream)
    if lane is None:
        raise SystemExit(f"lane not found: {lane_id(args.set_status, args.workstream)}")
    previous_status = str(lane.get("status") or "")
    previous_runtime = as_dict(lane.get("runtime"))
    previous_acceptance = str(previous_runtime.get("main_acceptance_status") or "")
    previous_acceptance_evidence = str(previous_runtime.get("main_acceptance_evidence") or "")
    previous_incident_code = str(previous_runtime.get("incident_code") or "")
    previous_event_kind = str(previous_runtime.get("outcome_event_kind") or "")
    lane["status"] = args.lane_status
    stamp_status_times(lane, args.lane_status, previous_status)
    if args.lane_status in {"leased", "running"}:
        # A status transition that reactivates terminal work is a fresh lease,
        # not a resurrection of a null or expired terminal timestamp.
        lane["lease_expires_at_utc"] = (
            datetime.now(timezone.utc) + timedelta(hours=float(args.lease_hours))
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_reverified_this_action = apply_runtime_metadata(
        lane,
        args,
        persist_usage_receipt=persist_usage_receipt,
    )
    validate_root_lineage(register, lane)
    declare_usage_receipt_write(lane, Path(args.register), source_reverified_this_action)
    budget_blocked = enforce_resource_budget(lane, previous_status)
    telemetry_blocked = False
    if not budget_blocked and args.lane_status == "complete":
        telemetry_blocked = enforce_usage_creditability(
            lane,
            previous_status,
            receipt_store_path=usage_receipt_store_path(Path(args.register)),
            source_reverified_this_action=source_reverified_this_action,
            isolated_agent_state_root=Path(getattr(args, "isolated_agent_state_root", DEFAULT_AGENT_STATE_ROOT)),
            codex_sessions_root=Path(getattr(args, "codex_sessions_root", DEFAULT_CODEX_SESSIONS_ROOT)),
        )
    if budget_blocked:
        pass
    elif telemetry_blocked:
        pass
    elif args.lane_status in {"blocked", "cancelled"}:
        current_incident_code = str(as_dict(lane.get("runtime")).get("incident_code") or "")
        record_outcome_transition(
            lane,
            event_kind="incident",
            previous_status=previous_status,
            state_changed=bool(args.incident_code) and current_incident_code != previous_incident_code,
        )
    elif args.lane_status == "complete":
        current_acceptance = str(as_dict(lane.get("runtime")).get("main_acceptance_status") or "")
        current_acceptance_evidence = str(as_dict(lane.get("runtime")).get("main_acceptance_evidence") or "")
        acceptance_changed = bool(args.main_acceptance_status) and current_acceptance != previous_acceptance
        acceptance_evidence_changed = (
            bool(args.main_acceptance_evidence)
            and current_acceptance_evidence != previous_acceptance_evidence
        )
        acceptance_update_requested = bool(args.main_acceptance_status or args.main_acceptance_evidence)
        event_kind = (
            "main_acceptance_update"
            if previous_status == "complete"
            and acceptance_update_requested
            and (
                acceptance_changed
                or acceptance_evidence_changed
                or previous_event_kind == "main_acceptance_update"
            )
            else "terminal_closeout"
        )
        record_outcome_transition(
            lane,
            event_kind=event_kind,
            previous_status=previous_status,
            state_changed=(acceptance_changed or acceptance_evidence_changed) if event_kind == "main_acceptance_update" else None,
        )
    if args.proof:
        lane["proof_artifacts"] = sorted({normalize_path(item) for item in as_list(lane.get("proof_artifacts")) + args.proof})
    if args.note:
        lane["notes"] = as_list(lane.get("notes")) + args.note
    upsert_lane(register, lane)
    return lane


def path_forbidden(path: str) -> str | None:
    normalized = normalize_path(path)
    for pattern in FORBIDDEN_WRITE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return pattern
    return None


def lane_forbidden_write_exception(lane: dict[str, Any], path: str, pattern: str) -> bool:
    """Allow exact SQL-CANON maintenance lanes to declare their gated DB writes.

    The register remains conservative by default: finance state paths and backups
    stay forbidden for ordinary lanes. SQL-CANON repair lanes may explicitly lease
    the durable finance DB and the matching rollback backup directory when the
    write is the bounded SQL-canon metadata path.
    """
    normalized = normalize_path(path)
    workflow_id = str(lane.get("workflow_id") or "").upper()
    lid = str(lane.get("lane_id") or "")
    if (
        workflow_id == "WF88"
        and lid == "WF88::wf67-stale-paper-artifact-archive-20260628"
        and normalized.startswith("09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-06-28/")
    ):
        return True
    if (
        workflow_id == "WF88"
        and lid == "WF88::wf67-legacy-radar-archive-apply-20260706"
        and (
            normalized == "09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-07-06"
            or normalized.startswith("09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-07-06/")
        )
    ):
        return True
    if (
        workflow_id == "PORTFOLIO-GOVERNANCE"
        and lid == "PORTFOLIO-GOVERNANCE::execution-board-route-marker-cleanup-20260706"
        and normalized == "03. Portfolio/Execution Board.md"
    ):
        return True
    if workflow_id == "WF78::SQL-FIRST-RECOMMENDATION-ARCHIVE-APPLY-20260625" and normalized.startswith(
        "09. Archive/WF78 SQL-First Deprecated Recommendation Surfaces/2026-06-24/"
    ):
        return True
    if workflow_id == "SQL-CANON" or workflow_id.startswith("SQL-CANON::"):
        if normalized in SQL_CANON_GATED_WRITE_EXCEPTIONS:
            return True
        return any(
            normalized == prefix.rstrip("/") or normalized.startswith(prefix)
            for prefix in SQL_CANON_GATED_WRITE_PREFIX_EXCEPTIONS
        )
    return False


def terminal_forbidden_write_inventory(hits: list[dict[str, str]]) -> dict[str, Any]:
    """Classify terminal forbidden-write hits as historical audit inventory.

    Active forbidden write declarations remain hard failures. Terminal hits are
    preserved so old sensitive declarations stay visible without blocking or
    warning on currently clean work.
    """
    status_counts: dict[str, int] = {}
    pattern_counts: dict[str, int] = {}
    lane_ids: set[str] = set()
    for hit in hits:
        lane_id_value = str(hit.get("lane_id") or "")
        if lane_id_value:
            lane_ids.add(lane_id_value)
        status = str(hit.get("status") or "unknown")
        pattern = str(hit.get("pattern") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    return {
        "classification": "terminal_history_audit_inventory",
        "safety_note": "Active forbidden write paths remain hard failures; terminal hits are retained as audit inventory.",
        "hit_count": len(hits),
        "lane_count": len(lane_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "hits": hits,
    }


PROOF_PATH_EXTENSIONS = {
    ".csv",
    ".db",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".pdf",
    ".py",
    ".sqlite",
    ".txt",
    ".xlsx",
}

PROOF_PATH_PREFIXES = (
    "tmp/",
    "scripts/",
    "state/",
    "data/",
    "memory/",
    "06. Playbooks/",
    "03. Portfolio/",
    "04. Research/",
)

ARCHIVED_PROOF_RELOCATIONS = (
    (
        "tmp/ticker-answer-packets/",
        "09. Archive/WF85 Legacy Ticker Answer Packets/preview/",
    ),
    (
        "tmp/alpaca-paper-readiness/",
        "09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-06-28/tmp/alpaca-paper-readiness/",
    ),
    (
        "tmp/alpaca-paper-readiness/",
        "09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-07-06/tmp/alpaca-paper-readiness/",
    ),
)

ARCHIVED_PROOF_EXACT_RELOCATIONS = {
    "scripts/wf78_legacy_42_tier_migration_planner.py": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/scripts/wf78_legacy_42_tier_migration_planner.py"
    ),
    "scripts/wf78_legacy_42_archive_readiness_packet.py": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/scripts/wf78_legacy_42_archive_readiness_packet.py"
    ),
    "scripts/wf78_legacy_42_tier_state.py": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/scripts/wf78_legacy_42_tier_state.py"
    ),
    "scripts/legacy_42_lifecycle_gate_packet.py": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/scripts/legacy_42_lifecycle_gate_packet.py"
    ),
    "scripts/test_legacy_42_lifecycle_gate_packet.py": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/scripts/test_legacy_42_lifecycle_gate_packet.py"
    ),
    "tmp/wf78-legacy-42-tier-migration-planner.json": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/tmp/wf78-legacy-42-tier-migration-planner.json"
    ),
    "tmp/wf78-legacy-42-tier-state-shadow.sqlite": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/tmp/wf78-legacy-42-tier-state-shadow.sqlite"
    ),
    "tmp/wf78-legacy-42-archive-readiness-packet.json": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/tmp/wf78-legacy-42-archive-readiness-packet.json"
    ),
    "tmp/legacy-42-lifecycle-gate-packet.json": (
        "09. Archive/WF78 Legacy 42 Full Archive/2026-06-24/tmp/legacy-42-lifecycle-gate-packet.json"
    ),
    "tmp/finance-vector-retrieval-summary.json": (
        "09. Archive/Finance Runtime/2026-08-29-portfolio-paper-state-retirement/source-state/tmp/finance-vector-retrieval-summary.json"
    ),
}


def proof_path_candidates(value: str) -> list[str]:
    """Return filesystem proof paths embedded in a proof entry.

    Older lane closeouts sometimes stored short narrative proof such as
    "command -> status ok" in proof_artifacts. Keep that visible, but only
    require existence checks for entries that are actually artifact paths.
    """
    candidates: list[str] = []
    for raw_part in str(value).split(";"):
        part = normalize_path(raw_part)
        if not part:
            continue
        if re.match(r"^(python|py|pytest|node|npm|go|openclaw|cd)\b", part, re.IGNORECASE):
            continue
        suffix = Path(part).suffix.lower()
        if suffix not in PROOF_PATH_EXTENSIONS:
            continue
        if " " in part and not part.startswith(PROOF_PATH_PREFIXES) and not re.match(r"^[A-Za-z]:[\\/]", part):
            continue
        if re.search(r"\s(->|status=|status |=|ok\b|blocked\b|eligible=)", part, re.IGNORECASE):
            continue
        candidates.append(part)
    return candidates


def proof_path_exists(path: str) -> bool:
    candidate = ROOT / path
    if candidate.exists():
        return True
    normalized = normalize_path(path)
    exact_relocation = ARCHIVED_PROOF_EXACT_RELOCATIONS.get(normalized)
    if exact_relocation and (ROOT / exact_relocation).exists():
        return True
    for old_prefix, archive_prefix in ARCHIVED_PROOF_RELOCATIONS:
        if normalized.startswith(old_prefix):
            relocated = ROOT / archive_prefix / normalized.removeprefix(old_prefix)
            if relocated.exists():
                return True
    return False


def validate_register(
    register: dict[str, Any],
    receipt_store_path: Path | None = None,
    *,
    isolated_agent_state_root: Path | None = None,
    codex_sessions_root: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})

    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    active = [lane for lane in lanes if lane.get("status") in ACTIVE_STATUSES]
    now = datetime.now(timezone.utc)

    check("schema_current", register.get("schema") == SCHEMA, register.get("schema"))
    for flag in REQUIRED_TRUE_FLAGS:
        check(f"authority_{flag}_true", as_dict(register.get("authority_boundary")).get(flag) is True, as_dict(register.get("authority_boundary")).get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        check(f"authority_{flag}_false", as_dict(register.get("authority_boundary")).get(flag) is False, as_dict(register.get("authority_boundary")).get(flag))

    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    for lane in lanes:
        lid = str(lane.get("lane_id") or "")
        if lid in seen_ids:
            duplicate_ids.append(lid)
        seen_ids.add(lid)
    check("unique_lane_ids", not duplicate_ids, duplicate_ids)

    invalid_status = [lane.get("lane_id") for lane in lanes if lane.get("status") not in VALID_STATUSES]
    check("valid_status_values", not invalid_status, invalid_status)

    active_write_owners: dict[str, list[str]] = {}
    active_forbidden_hits: list[dict[str, str]] = []
    terminal_forbidden_hits: list[dict[str, str]] = []
    active_without_owner: list[str] = []
    stale_leases: list[str] = []
    active_without_writes: list[str] = []
    running_without_start: list[str] = []
    running_without_session: list[str] = []
    running_without_model: list[str] = []
    terminal_without_end: list[str] = []
    terminal_end_completed_at_fallbacks: list[dict[str, str]] = []
    completed_without_proof: list[str] = []
    completed_model_without_token_closeout: list[dict[str, str]] = []
    future_completed_model_without_token_closeout: list[dict[str, str]] = []
    attribution_grade_closeout_gaps: list[dict[str, Any]] = []
    attribution_grade_pricing_unavailable: list[dict[str, Any]] = []
    telemetry_credit_gaps: list[dict[str, Any]] = []
    historical_terminal_session_index_retention_gaps: list[dict[str, Any]] = []
    missing_proof: list[dict[str, str]] = []
    historical_missing_proof: list[dict[str, str]] = []
    invalid_attempt_metadata: list[dict[str, Any]] = []
    legacy_attempt_metadata: list[dict[str, Any]] = []
    invalid_outcome_event_metadata: list[dict[str, Any]] = []
    historical_outcome_event_history_gaps: list[dict[str, Any]] = []
    terminal_route_conformance_gaps: list[dict[str, Any]] = []
    terminal_nonaccepted_route_conformance_incidents: list[dict[str, Any]] = []
    native_backend_invariant_gaps: list[dict[str, Any]] = []
    efficiency_identity_gaps: list[dict[str, Any]] = []
    historical_efficiency_identity_gaps: list[dict[str, Any]] = []
    usage_unavailable_reason_gaps: list[dict[str, Any]] = []
    resource_budget_contract_gaps: list[dict[str, Any]] = []
    resource_budget_state_gaps: list[dict[str, Any]] = []
    native_fork_policy_gaps: list[dict[str, Any]] = []

    for lane in lanes:
        lid = str(lane.get("lane_id") or "")
        status = lane.get("status")
        lane_runtime = as_dict(lane.get("runtime"))
        if lane_runtime.get("model_path") and (
            efficiency_enforcement_applies(lane)
            or identity_metadata_hard_enforcement_applies(lane)
        ):
            identity_missing = [
                field for field in ("parent_job_id", "phase")
                if not isinstance(lane_runtime.get(field), str) or not str(lane_runtime.get(field)).strip()
            ]
            if strict_attempt_int(lane_runtime.get("attempt_number"), minimum=1) is None:
                identity_missing.append("attempt_number")
            if strict_attempt_int(lane_runtime.get("retry_count"), minimum=0) is None:
                identity_missing.append("retry_count")
            if identity_missing:
                gap = {"lane_id": lid, "missing": identity_missing}
                if status in ACTIVE_STATUSES or identity_metadata_hard_enforcement_applies(lane):
                    efficiency_identity_gaps.append(gap)
                else:
                    historical_efficiency_identity_gaps.append({
                        **gap,
                        "classification": "historical_identity_unavailable_not_backfilled",
                    })
            budget_fields = {
                "max_gross_tokens": "gross_tokens",
                "max_cached_replay_tokens": "cached_replay_tokens",
                "max_tool_calls": "tool_calls",
                "max_elapsed_seconds": "elapsed_seconds",
            }
            invalid_budgets = []
            for field, hard_key in budget_fields.items():
                value = strict_runtime_int(lane_runtime.get(field))
                if value is None or value < 1 or value > HARD_RESOURCE_CEILINGS[hard_key]:
                    invalid_budgets.append(field)
            if invalid_budgets:
                resource_budget_contract_gaps.append({"lane_id": lid, "invalid_or_missing": invalid_budgets})
            guard = as_dict(lane_runtime.get("resource_budget_guard"))
            if guard.get("status") == "blocked" and status != "blocked":
                resource_budget_state_gaps.append({"lane_id": lid, "status": status, "guard_status": "blocked"})
            missing_usage = accepted_missing_usage_classification(lane_runtime)
            if status in TERMINAL_STATUSES and missing_usage and lane_runtime.get("usage_unavailable_reason") not in USAGE_UNAVAILABLE_REASONS:
                usage_unavailable_reason_gaps.append({"lane_id": lid, "classification": missing_usage})
            if status in TERMINAL_STATUSES and has_native_rollout_provenance(lane_runtime):
                fork_errors = []
                if lane_runtime.get("fork_policy") != "none":
                    fork_errors.append("fork_policy_must_be_none")
                if lane_runtime.get("fork_baseline_applied") is not True:
                    fork_errors.append("fork_baseline_not_applied")
                if fork_errors:
                    native_fork_policy_gaps.append({"lane_id": lid, "errors": fork_errors})
        if has_native_rollout_provenance(lane_runtime):
            invalid_backends = {
                key: lane_runtime.get(key)
                for key in ("expected_execution_backend", "actual_execution_backend")
                if lane_runtime.get(key) != "codex_native_subagent"
            }
            if invalid_backends:
                native_backend_invariant_gaps.append({"lane_id": lid, "backends": invalid_backends})
        retry_present = lane_runtime.get("retry_count") not in (None, "")
        attempt_present = lane_runtime.get("attempt_number") not in (None, "")
        if retry_present or attempt_present:
            retry_count = strict_attempt_int(lane_runtime.get("retry_count"), minimum=0)
            attempt_number = strict_attempt_int(lane_runtime.get("attempt_number"), minimum=1)
            legacy_retry = legacy_attempt_int(lane_runtime.get("retry_count"), minimum=0)
            legacy_attempt = legacy_attempt_int(lane_runtime.get("attempt_number"), minimum=1)
            effective_retry = retry_count if retry_count is not None else legacy_retry
            effective_attempt = attempt_number if attempt_number is not None else legacy_attempt
            attempt_errors: list[str] = []
            if retry_present and effective_retry is None:
                attempt_errors.append("retry_count_not_nonnegative_integer")
            if attempt_present and effective_attempt is None:
                attempt_errors.append("attempt_number_not_positive_integer")
            if effective_retry is not None and effective_attempt is not None and effective_attempt != effective_retry + 1:
                attempt_errors.append("attempt_retry_conflict")
            expected_first = effective_attempt == 1 if effective_attempt is not None else None
            if expected_first is not None and retry_count is not None and attempt_number is not None and lane_runtime.get("is_first_attempt") is not expected_first:
                attempt_errors.append("is_first_attempt_not_derived")
            if attempt_errors:
                invalid_attempt_metadata.append({"lane_id": lid, "errors": attempt_errors})
            elif legacy_retry is not None or legacy_attempt is not None:
                legacy_attempt_metadata.append({"lane_id": lid, "classification": "legacy_numeric_string_not_counted_as_typed_attempt"})
        event_kind = str(lane_runtime.get("outcome_event_kind") or "")
        event_errors: list[str] = []
        if active_implementation_attempt_outcome_baseline_applies(lane, lane_runtime):
            if lane_runtime.get("incident_code") != "":
                event_errors.append("active_incident_code_not_clean")
            if strict_attempt_int(lane_runtime.get("incident_count"), minimum=0) != 0:
                event_errors.append("active_incident_count_not_zero")
            if lane.get("outcome_events") != []:
                event_errors.append("active_outcome_events_not_empty")
        if event_kind and event_kind not in OUTCOME_EVENT_KINDS:
            event_errors.append("invalid_outcome_event_kind")
        incident_code = str(lane_runtime.get("incident_code") or "")
        if incident_code and incident_code not in INCIDENT_CODES:
            event_errors.append("invalid_incident_code")
        if event_kind == "incident" and incident_code not in INCIDENT_CODES:
            event_errors.append("incident_code_required")
        if event_kind and parse_outcome_utc(lane_runtime.get("outcome_recorded_at_utc")) is None:
            event_errors.append("outcome_recorded_at_utc_required")
        if event_kind and strict_attempt_int(lane_runtime.get("outcome_event_sequence"), minimum=1) is None:
            event_errors.append("outcome_event_sequence_required")
        if lane_runtime.get("incident_count") not in (None, "") and strict_attempt_int(lane_runtime.get("incident_count"), minimum=0) is None:
            event_errors.append("incident_count_not_nonnegative_integer")
        outcome_events = lane.get("outcome_events")
        if outcome_events is not None or event_kind:
            if not isinstance(outcome_events, list):
                event_errors.append("outcome_events_list_required")
            else:
                prior_event_time: datetime | None = None
                incident_event_count = 0
                for index, row in enumerate(outcome_events, start=1):
                    row_time = parse_outcome_utc(row.get("recorded_at_utc")) if isinstance(row, dict) else None
                    if (
                        not isinstance(row, dict)
                        or set(row) != {"event_kind", "event_sequence", "recorded_at_utc"}
                        or row.get("event_kind") not in OUTCOME_EVENT_KINDS
                        or strict_attempt_int(row.get("event_sequence"), minimum=1) != index
                        or row_time is None
                    ):
                        event_errors.append("outcome_event_history_invalid")
                        continue
                    if prior_event_time is not None and row_time <= prior_event_time:
                        event_errors.append("outcome_event_history_not_strictly_increasing")
                    prior_event_time = row_time
                    if row.get("event_kind") == "incident":
                        incident_event_count += 1
                runtime_sequence = strict_attempt_int(lane_runtime.get("outcome_event_sequence"), minimum=0)
                if outcome_events:
                    if runtime_sequence != len(outcome_events):
                        event_errors.append("outcome_event_sequence_history_mismatch")
                    if outcome_events[-1] != {
                        "event_kind": lane_runtime.get("outcome_event_kind"),
                        "event_sequence": runtime_sequence,
                        "recorded_at_utc": lane_runtime.get("outcome_recorded_at_utc"),
                    }:
                        event_errors.append("outcome_event_runtime_drift")
                    persisted_incident_count = strict_attempt_int(lane_runtime.get("incident_count"), minimum=0)
                    if persisted_incident_count != incident_event_count:
                        event_errors.append("incident_count_history_mismatch")
                elif event_kind:
                    event_errors.append("outcome_event_history_required")
        if event_errors:
            normalized_event_errors = sorted(set(event_errors))
            gap = {"lane_id": lid, "errors": normalized_event_errors}
            if (
                normalized_event_errors == ["outcome_events_list_required"]
                and is_provably_pre_outcome_event_history_enforcement_terminal(lane, lane_runtime)
            ):
                historical_outcome_event_history_gaps.append({
                    **gap,
                    "classification": "historical_outcome_event_history_unavailable_not_backfilled",
                    "outcome_recorded_at_utc": lane_runtime.get("outcome_recorded_at_utc"),
                })
            else:
                invalid_outcome_event_metadata.append(gap)
        if status in TERMINAL_STATUSES and lane_runtime.get("token_attribution_source") == "codex_native_rollout_jsonl":
            expected_model = lane_runtime.get("expected_model_path")
            expected_thinking = lane_runtime.get("expected_thinking")
            actual_model = lane_runtime.get("actual_model_path")
            actual_thinking = lane_runtime.get("actual_thinking")
            expected_backend = lane_runtime.get("expected_execution_backend")
            actual_backend = lane_runtime.get("actual_execution_backend")
            route_errors: list[str] = []
            if not all(isinstance(value, str) and value for value in (expected_model, expected_thinking, actual_model, actual_thinking, expected_backend, actual_backend)):
                route_errors.append("expected_and_actual_route_metadata_required")
            else:
                if expected_model != actual_model:
                    route_errors.append("model_path_mismatch")
                if expected_thinking != actual_thinking:
                    route_errors.append("thinking_mismatch")
                if expected_backend != actual_backend:
                    route_errors.append("execution_backend_mismatch")
            if route_errors:
                gap = {"lane_id": lid, "errors": route_errors}
                if status == "complete":
                    terminal_route_conformance_gaps.append(gap)
                else:
                    terminal_nonaccepted_route_conformance_incidents.append({
                        **gap,
                        "status": status,
                        "incident_code": lane_runtime.get("incident_code"),
                        "classification": "terminal_nonaccepted_route_mismatch_incident",
                    })
        writes = [normalize_path(str(item)) for item in as_list(lane.get("allowed_writes")) if str(item).strip()]
        if status in ACTIVE_STATUSES:
            if not lane.get("owner") or lane.get("owner") == "unassigned":
                active_without_owner.append(lid)
            if status in {"leased", "running"} and not writes:
                active_without_writes.append(lid)
            expires = parse_utc(lane.get("lease_expires_at_utc"))
            if status in {"leased", "running"} and expires and expires < now:
                stale_leases.append(lid)
            if status == "running" and not parse_utc(lane.get("started_at_utc")):
                running_without_start.append(lid)
            if status == "running" and not as_dict(lane.get("runtime")).get("session_key"):
                running_without_session.append(lid)
            if status == "running" and not as_dict(lane.get("runtime")).get("model_path"):
                running_without_model.append(lid)
            for path in writes:
                active_write_owners.setdefault(path, []).append(lid)
        ended_at = parse_utc(lane.get("ended_at_utc"))
        completed_at = parse_utc(lane.get("completed_at_utc"))
        if status in TERMINAL_STATUSES and not ended_at:
            completed_at_is_valid_terminal_proof = bool(
                completed_at
                and (
                    status == "complete"
                    or is_provably_pre_identity_enforcement_terminal(lane)
                )
            )
            if completed_at_is_valid_terminal_proof:
                if status != "complete":
                    terminal_end_completed_at_fallbacks.append({
                        "lane_id": lid,
                        "completed_at_utc": str(lane.get("completed_at_utc")),
                        "classification": "historical_terminal_end_proven_by_completed_at",
                    })
            else:
                terminal_without_end.append(lid)
        for path in writes:
            pattern = path_forbidden(path)
            if pattern and lane_forbidden_write_exception(lane, path, pattern):
                continue
            if pattern:
                hit = {"lane_id": lid, "path": path, "pattern": pattern, "status": str(status or "")}
                if status in ACTIVE_STATUSES:
                    active_forbidden_hits.append(hit)
                else:
                    terminal_forbidden_hits.append(hit)
        if status == "complete":
            proofs = [normalize_path(str(item)) for item in as_list(lane.get("proof_artifacts")) if str(item).strip()]
            commands = [str(item) for item in as_list(lane.get("acceptance_commands")) if str(item).strip()]
            if not proofs and not commands:
                completed_without_proof.append(lid)
            runtime = as_dict(lane.get("runtime"))
            assessment = runtime_token_assessment(runtime)
            if requires_attribution_grade_closeout(lane, runtime):
                credit = usage_credit_assessment(
                    lane,
                    runtime,
                    receipt_store_path=receipt_store_path,
                    isolated_agent_state_root=isolated_agent_state_root,
                    codex_sessions_root=codex_sessions_root,
                )
                if credit.get("usage_creditable") is not True:
                    gap = {
                        "lane_id": lid,
                        "model_path": runtime.get("model_path") or lane.get("model_path"),
                        "status": credit.get("status"),
                        "reasons": credit.get("reasons"),
                        "token_attribution_source": runtime.get("token_attribution_source"),
                    }
                    if is_historical_terminal_session_index_retention_gap(lane, runtime, credit):
                        historical_terminal_session_index_retention_gaps.append({
                            **gap,
                            "classification": "historical_terminal_session_index_retention_gap",
                            "event_time_credit": "immutable_historical_evidence",
                            "current_source_reverification": "unavailable",
                            "current_accounting_credit": "unavailable",
                        })
                    else:
                        telemetry_credit_gaps.append(gap)
                if assessment.get("token_valid") is not True:
                    attribution_grade_closeout_gaps.append({
                        "lane_id": lid,
                        "agent_id": runtime.get("agent_id"),
                        "phase": runtime.get("phase"),
                        "model_path": runtime.get("model_path") or lane.get("model_path"),
                        "token_closeout_status": assessment.get("status"),
                        "has_partial_usage": runtime_has_token_value(runtime),
                        "missing_usage_classification": accepted_missing_usage_classification(runtime),
                        "allowed_missing_usage_classifications": [],
                        "missing_fields": assessment.get("missing_fields"),
                        "reasons": assessment.get("reasons"),
                    })
                elif assessment.get("token_valid") is True and assessment.get("pricing_grade") is not True:
                    attribution_grade_pricing_unavailable.append({
                        "lane_id": lid,
                        "agent_id": runtime.get("agent_id"),
                        "phase": runtime.get("phase"),
                        "reason": "cache_write_pricing_unavailable",
                    })
            if runtime.get("model_path") and not runtime_has_token_value(runtime) and not accepted_missing_usage_classification(runtime):
                token_gap = {
                    "lane_id": lid,
                    "model_path": str(runtime.get("model_path") or ""),
                    "token_closeout_status": str(runtime.get("token_closeout_status") or "missing"),
                }
                if completed_after_token_hard_enforcement(lane):
                    future_completed_model_without_token_closeout.append(token_gap)
                elif completed_after_token_closeout_guard(lane):
                    completed_model_without_token_closeout.append(token_gap)
            for proof in proofs:
                for proof_path in proof_path_candidates(proof):
                    if not proof_path_exists(proof_path):
                        gap = {"lane_id": lid, "proof": proof_path}
                        if is_provably_pre_proof_artifact_enforcement_complete(lane):
                            historical_missing_proof.append({
                                **gap,
                                "classification": "historical_proof_path_unavailable_not_retargeted",
                            })
                        else:
                            missing_proof.append(gap)

    collisions = {path: owners for path, owners in active_write_owners.items() if len(owners) > 1}
    check("attempt_metadata_is_typed_derived_and_consistent", not invalid_attempt_metadata, invalid_attempt_metadata)
    check("legacy_numeric_string_attempt_metadata", True, legacy_attempt_metadata, "info")
    check("outcome_event_metadata_is_bounded_and_complete", not invalid_outcome_event_metadata, invalid_outcome_event_metadata)
    check(
        "historical_terminal_outcome_event_history_gaps_are_classified_not_backfilled",
        not historical_outcome_event_history_gaps,
        {
            "hard_enforcement_start_utc": OUTCOME_EVENT_HISTORY_HARD_ENFORCEMENT_START_UTC,
            "classification": "historical_outcome_event_history_unavailable_not_backfilled",
            "gaps": historical_outcome_event_history_gaps,
        },
        "warning",
    )
    check("native_rollout_provenance_requires_codex_native_subagent_backend", not native_backend_invariant_gaps, native_backend_invariant_gaps)
    check("terminal_codex_native_route_conforms_to_expected_route", not terminal_route_conformance_gaps, terminal_route_conformance_gaps)
    check(
        "terminal_nonaccepted_route_mismatch_incidents_are_classified",
        not terminal_nonaccepted_route_conformance_incidents,
        terminal_nonaccepted_route_conformance_incidents,
        "warning",
    )
    check("new_model_lanes_have_parent_phase_attempt_identity", not efficiency_identity_gaps, efficiency_identity_gaps)
    check(
        "historical_model_lane_identity_gaps_are_classified_not_backfilled",
        not historical_efficiency_identity_gaps,
        {
            "hard_enforcement_start_utc": IDENTITY_METADATA_HARD_ENFORCEMENT_START_UTC,
            "classification": "historical_identity_unavailable_not_backfilled",
            "gaps": historical_efficiency_identity_gaps,
        },
        "warning",
    )
    check("new_unavailable_usage_has_explicit_reason", not usage_unavailable_reason_gaps, usage_unavailable_reason_gaps)
    check("new_model_lanes_have_bounded_resource_budgets", not resource_budget_contract_gaps, resource_budget_contract_gaps)
    check("resource_budget_breaches_are_terminal_incidents", not resource_budget_state_gaps, resource_budget_state_gaps)
    check("new_native_rollouts_use_no_fork_and_apply_baseline", not native_fork_policy_gaps, native_fork_policy_gaps)
    check("no_active_write_collisions", not collisions, collisions)
    check("no_active_forbidden_write_paths", not active_forbidden_hits, active_forbidden_hits)
    check("terminal_forbidden_write_paths", True, terminal_forbidden_write_inventory(terminal_forbidden_hits), "info")
    check("active_lanes_have_owner", not active_without_owner, active_without_owner)
    check("leased_running_lanes_declare_writes", not active_without_writes, active_without_writes)
    check("no_stale_active_leases", not stale_leases, stale_leases, "warning")
    check("running_lanes_have_started_at", not running_without_start, running_without_start, "warning")
    check("running_lanes_have_session_metadata", not running_without_session, running_without_session, "warning")
    check("running_lanes_have_model_metadata", not running_without_model, running_without_model, "warning")
    check("terminal_lanes_have_ended_at", not terminal_without_end, terminal_without_end, "warning")
    check(
        "historical_terminal_end_completed_at_fallbacks",
        True,
        terminal_end_completed_at_fallbacks,
        "info",
    )
    check("completed_lanes_have_proof_or_acceptance", not completed_without_proof, completed_without_proof)
    check(
        "historical_completed_model_lanes_have_token_closeout_visibility",
        not completed_model_without_token_closeout,
        {
            "token_closeout_guard_start_utc": TOKEN_CLOSEOUT_GUARD_START_UTC,
            "token_closeout_hard_enforcement_start_utc": TOKEN_CLOSEOUT_HARD_ENFORCEMENT_START_UTC,
            "gaps": completed_model_without_token_closeout,
        },
        "warning",
    )
    check(
        "future_completed_model_lanes_require_token_closeout_metadata_or_classification",
        not future_completed_model_without_token_closeout,
        {
            "token_closeout_hard_enforcement_start_utc": TOKEN_CLOSEOUT_HARD_ENFORCEMENT_START_UTC,
            "gaps": future_completed_model_without_token_closeout,
        },
    )
    check(
        "new_model_driven_lanes_require_deterministic_creditable_usage",
        not telemetry_credit_gaps,
        {
            "cutover_utc": STRICT_TELEMETRY_CUTOVER_UTC,
            "trusted_sources": sorted(TRUSTED_TOKEN_ATTRIBUTION_SOURCES),
            "gaps": telemetry_credit_gaps,
        },
    )
    check(
        "historical_terminal_session_index_retention_gaps_are_classified_not_recredited",
        not historical_terminal_session_index_retention_gaps,
        {
            "classification": "historical_terminal_session_index_retention_gap",
            "detail": (
                "Event-time credit is immutable historical evidence; current source "
                "re-verification and accounting credit are unavailable, and release "
                "and current credit remain blocked."
            ),
            "gaps": historical_terminal_session_index_retention_gaps,
        },
        "warning",
    )
    check(
        "new_model_driven_implementation_and_isolated_lanes_require_complete_reconciled_usage",
        not attribution_grade_closeout_gaps,
        {
            "enforcement_start_utc": STRICT_TELEMETRY_CUTOVER_UTC,
            "gaps": attribution_grade_closeout_gaps,
        },
    )
    isolated_implementation_gaps = [
        row for row in attribution_grade_closeout_gaps
        if row.get("agent_id") in CONFIGURED_ISOLATED_AGENT_IDS
        and str(row.get("phase") or "").strip().lower() in IMPLEMENTATION_PHASES
    ]
    check(
        "new_isolated_implementation_phases_require_complete_reconciled_usage_or_classification",
        not isolated_implementation_gaps,
        isolated_implementation_gaps,
    )
    check(
        "isolated_implementation_pricing_unavailable_visibility",
        True,
        attribution_grade_pricing_unavailable,
        "info",
    )
    check("proof_artifacts_exist", not missing_proof, missing_proof)
    check(
        "historical_missing_proof_artifacts_are_classified_not_retargeted",
        not historical_missing_proof,
        {
            "hard_enforcement_start_utc": PROOF_ARTIFACT_EXISTENCE_HARD_ENFORCEMENT_START_UTC,
            "classification": "historical_proof_path_unavailable_not_retargeted",
            "gaps": historical_missing_proof,
        },
        "warning",
    )

    errors = [item for item in checks if item["severity"] == "critical" and not item["ok"]]
    warnings = [item for item in checks if item["severity"] == "warning" and not item["ok"]]
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def validate_active_lease_admission(register: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether active-lane state is safe to persist.

    The durable ledger intentionally retains terminal-route and proof debt.
    That debt remains part of :func:`validate_register`, but it must not make a
    safe, distinct new lease impossible.  This admission projection therefore
    runs the existing validator against active rows only while preserving the
    full-register structural checks that protect the register itself.
    """
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})

    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    active_lanes = [lane for lane in lanes if lane.get("status") in ACTIVE_STATUSES]
    now = datetime.now(timezone.utc)

    check("schema_current", register.get("schema") == SCHEMA, register.get("schema"))
    authority_boundary = as_dict(register.get("authority_boundary"))
    for flag in REQUIRED_TRUE_FLAGS:
        check(f"authority_{flag}_true", authority_boundary.get(flag) is True, authority_boundary.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        check(f"authority_{flag}_false", authority_boundary.get(flag) is False, authority_boundary.get(flag))

    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    for lane in lanes:
        lid = str(lane.get("lane_id") or "")
        if lid in seen_ids:
            duplicate_ids.append(lid)
        seen_ids.add(lid)
    check("unique_lane_ids", not duplicate_ids, duplicate_ids)

    invalid_status = [lane.get("lane_id") for lane in lanes if lane.get("status") not in VALID_STATUSES]
    check("valid_status_values", not invalid_status, invalid_status)

    active_without_current_expiry: list[dict[str, str]] = []
    for lane in active_lanes:
        if lane.get("status") not in {"leased", "running"}:
            continue
        expires = parse_utc(lane.get("lease_expires_at_utc"))
        if expires is None:
            active_without_current_expiry.append({
                "lane_id": str(lane.get("lane_id") or ""),
                "reason": "lease_expiry_missing_or_invalid",
            })
        elif expires <= now:
            active_without_current_expiry.append({
                "lane_id": str(lane.get("lane_id") or ""),
                "reason": "lease_expired",
            })
    check(
        "leased_running_lanes_have_current_lease_expiry",
        not active_without_current_expiry,
        active_without_current_expiry,
    )

    # Reuse the established active-lane checks rather than creating a second,
    # subtly divergent collision or identity validator.  Terminal rows are
    # deliberately omitted from this projection; their audit debt stays in the
    # full register validation written by refresh_summary.
    active_projection = copy.deepcopy(register)
    active_projection["lanes"] = copy.deepcopy(active_lanes)
    projected_validation = validate_register(active_projection)
    active_check_names = {
        "attempt_metadata_is_typed_derived_and_consistent",
        "outcome_event_metadata_is_bounded_and_complete",
        "native_rollout_provenance_requires_codex_native_subagent_backend",
        "new_model_lanes_have_parent_phase_attempt_identity",
        "new_model_lanes_have_bounded_resource_budgets",
        "resource_budget_breaches_are_terminal_incidents",
        "no_active_write_collisions",
        "no_active_forbidden_write_paths",
        "active_lanes_have_owner",
        "leased_running_lanes_declare_writes",
        "no_stale_active_leases",
        "running_lanes_have_started_at",
        "running_lanes_have_session_metadata",
        "running_lanes_have_model_metadata",
    }
    for projected_check in as_list(projected_validation.get("checks")):
        if not isinstance(projected_check, dict) or projected_check.get("name") not in active_check_names:
            continue
        checks.append(dict(projected_check))

    errors = [item for item in checks if item["severity"] == "critical" and not item["ok"]]
    warnings = [item for item in checks if item["severity"] == "warning" and not item["ok"]]
    return {
        "schema": ACTIVE_LEASE_ADMISSION_SCHEMA,
        "scope": "active_lanes_with_full_register_structure",
        "active_lane_count": len(active_lanes),
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def open_lane_projection(lane: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Project only live work; terminal history remains append-only elsewhere."""
    now = now or datetime.now(timezone.utc)
    runtime = as_dict(lane.get("runtime"))
    status = str(lane.get("status") or "unknown")
    expires = parse_utc(lane.get("lease_expires_at_utc"))
    if status == "planned":
        sla_status = "awaiting_lease"
    elif expires is None:
        sla_status = "lease_missing"
    elif expires <= now:
        sla_status = "lease_expired"
    else:
        sla_status = "lease_current"
    incident = as_dict(runtime.get("incident"))
    blocker = (
        incident.get("incident_code")
        or runtime.get("incident_code")
        or lane.get("blocker")
        or ("lease_expired" if sla_status == "lease_expired" else None)
    )
    next_action = runtime.get("next_action") or runtime.get("deliverable")
    if not next_action:
        if sla_status == "lease_expired":
            next_action = "Main must close this stale lane or issue a fresh exact-write lease after review."
        elif status == "planned":
            next_action = "Declare exact allowed_writes and acquire a lease before starting work."
        else:
            next_action = "Complete the declared deliverable, validate it, and close the lane with proof."
    return {
        "lane_id": lane.get("lane_id"),
        "workflow_id": lane.get("workflow_id"),
        "workstream_id": lane.get("workstream_id"),
        "owner": lane.get("owner"),
        "status": status,
        "phase": runtime.get("phase") or lane.get("phase"),
        "lease_expires_at_utc": lane.get("lease_expires_at_utc"),
        "sla_status": sla_status,
        "blocker": blocker,
        "next_action": next_action,
        "proof_artifacts": list(as_list(lane.get("proof_artifacts")))[:3],
        "allowed_write_count": len(as_list(lane.get("allowed_writes"))),
        "disposition": "main_review_required" if blocker else "continue_or_close_with_proof",
    }


def refresh_summary(
    register: dict[str, Any],
    receipt_store_path: Path | None = None,
    *,
    isolated_agent_state_root: Path | None = None,
    codex_sessions_root: Path | None = None,
) -> None:
    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    counts: dict[str, int] = {}
    workflow_counts: dict[str, int] = {}
    for lane in lanes:
        status = str(lane.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        wid = str(lane.get("workflow_id") or "unknown")
        workflow_counts[wid] = workflow_counts.get(wid, 0) + 1
    open_lanes = [
        open_lane_projection(lane)
        for lane in lanes
        if str(lane.get("status") or "") in ACTIVE_STATUSES
    ]
    open_lanes.sort(key=lambda row: (row.get("sla_status") != "lease_expired", str(row.get("lane_id") or "")))
    historical_terminal_count = sum(1 for lane in lanes if lane.get("status") in TERMINAL_STATUSES)
    attention_open_count = sum(
        1 for lane in open_lanes if lane.get("sla_status") in {"lease_expired", "lease_missing"} or lane.get("blocker")
    )
    register["generated_at_utc"] = utc_now()
    register["summary"] = {
        "lane_count": len(lanes),
        "status_counts": dict(sorted(counts.items())),
        "workflow_counts": dict(sorted(workflow_counts.items())),
        # Historical rows are deliberately not part of the live-work ranking.
        "historical_terminal_lane_count": historical_terminal_count,
        "open_lane_count": len(open_lanes),
        "active_lane_count": len(open_lanes),  # compatibility alias
        "open_blocked_lane_count": sum(1 for lane in open_lanes if lane.get("blocker")),
        "attention_open_lane_count": attention_open_count,
        "open_lanes": open_lanes,
        "next_safe_action": (
            "Resolve or explicitly close open lanes with expired/missing leases first; then lease narrow distinct-output lanes only after allowed_writes are explicit."
            if attention_open_count
            else "Lease narrow distinct-output lanes only after allowed_writes are explicit; main session must merge and update continuity."
        ),
    }
    register["validation"] = validate_register(
        register,
        receipt_store_path,
        isolated_agent_state_root=isolated_agent_state_root,
        codex_sessions_root=codex_sessions_root,
    )


def print_result(
    action: str,
    register: dict[str, Any],
    lane: dict[str, Any] | None = None,
    post_write_refresh: dict[str, Any] | None = None,
    lease_admission: dict[str, Any] | None = None,
) -> None:
    print(
        json.dumps(
            {
                "action": action,
                "status": as_dict(register.get("validation")).get("status"),
                "summary": register.get("summary"),
                "lane": lane,
                "post_write_refresh": post_write_refresh or {"status": "not_requested"},
                "lease_admission": lease_admission or {"status": "not_requested"},
                "validation": {
                    "errors": len(as_list(as_dict(register.get("validation")).get("errors"))),
                    "warnings": len(as_list(as_dict(register.get("validation")).get("warnings"))),
                },
            },
            indent=2,
        )
    )


def refresh_shadow_pilot_after_write(register_path: Path) -> None:
    """Refresh passive WF73 shadow telemetry without making it lane authority."""
    try:
        from wf73_postgres_shadow_pilot import refresh_shadow_pilot

        refresh_shadow_pilot(register_path)
    except Exception as exc:  # pragma: no cover - fail-open by design
        atomic_write_json(
            SHADOW_PILOT_ERROR,
            {
                "schema": "veritas.wf73.postgres_shadow_pilot_metrics.v1",
                "generated_at_utc": utc_now(),
                "status": "warning",
                "mode": "shadow_refresh_failed_json_primary_preserved",
                "metrics": {
                    "json_primary": True,
                    "postgres_runtime_dependency": False,
                    "shadow_projection_available": False,
                },
                "validation": {
                    "status": "warning",
                    "errors": [],
                    "warnings": [f"shadow_refresh_failed:{type(exc).__name__}"],
                },
                "authority_boundary": {
                    "review_only": True,
                    "shadow_projection_only": True,
                    "json_lane_register_primary": True,
                    "lane_claim_authority_allowed": False,
                    "owner_approval_inferred": False,
                },
            },
        )


def emit_dispatch_task_name(register: dict[str, Any], args: argparse.Namespace) -> int:
    """Emit the one opaque core task token for an already-declared lane.

    This intentionally works from an in-memory runtime and returns only the
    opaque task name. The caller is responsible for passing that token to the
    protected core producer before helper dispatch; this register action never
    writes, launches, or otherwise authorizes a helper.
    """
    if args.write:
        raise SystemExit("dispatch task name emission is nonmutating and cannot be combined with --write")
    lane = find_lane(register, args.dispatch_task_name, args.workstream)
    if lane is None:
        raise SystemExit("dispatch task name requires an existing lane")
    if str(lane.get("status") or "") not in {"leased", "running"}:
        raise SystemExit("dispatch task name requires a leased or running lane")
    lease_expires_at = parse_utc(lane.get("lease_expires_at_utc"))
    if lease_expires_at is None or lease_expires_at <= datetime.now(timezone.utc):
        raise SystemExit("dispatch task name requires a current lane lease")
    runtime = dict(as_dict(lane.get("runtime")))
    bind_attempt_correlation(lane, runtime)
    correlation_hash = str(as_dict(runtime.get("attempt_correlation")).get("key_hash") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", correlation_hash):
        raise SystemExit("dispatch task name requires a complete deterministic attempt contract")
    try:
        task_name = task_name_for_attempt(attempt_correlation_hash=correlation_hash)
    except ValueError as exc:
        raise SystemExit("dispatch task name could not be derived") from exc
    print(json.dumps({
        "schema": DISPATCH_TASK_NAME_SCHEMA,
        "task_name": task_name,
    }, sort_keys=True, separators=(",", ":")))
    return 0


def should_refresh_outcome_surfaces(
    register_path: Path,
    lane: dict[str, Any] | None,
    action_name: str,
) -> bool:
    if lane is None or register_path.resolve() != DEFAULT_REGISTER.resolve():
        return False
    event_kind = str(as_dict(lane.get("runtime")).get("outcome_event_kind") or "")
    if action_name in {"complete", "set-status"} and lane.get("status") == "complete":
        return event_kind in {"terminal_closeout", "main_acceptance_update"}
    if action_name == "set-status" and lane.get("status") in {"blocked", "cancelled"}:
        return event_kind == "incident"
    return False


def refresh_lane_outcome_surfaces(
    register_path: Path,
    lane: dict[str, Any] | None,
    action_name: str,
) -> dict[str, Any]:
    """Refresh local metadata-only outcome truth after the register is durable."""
    if not should_refresh_outcome_surfaces(register_path, lane, action_name):
        return {"status": "not_triggered", "canonical_register_only": True, "commands": []}
    commands = (
        (
            "agent_message_ledger",
            [
                sys.executable,
                str(ROOT / "scripts" / "agent_message_ledger_packet.py"),
                "--register",
                str(register_path),
                "--append-ledger",
                "--write",
                "--validate",
            ],
        ),
        (
            "token_usage_ledger",
            [
                sys.executable,
                str(ROOT / "scripts" / "token_usage_ledger.py"),
                "--write",
                "--validate",
                "--skip-isolated-agent-usage-cost",
            ],
        ),
    )
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    for name, command in commands:
        remaining = OUTCOME_REFRESH_SLA_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            results.append({"name": name, "returncode": None, "status": "error", "error_class": "OutcomeRefreshSlaExpired"})
            continue
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=remaining,
            )
            results.append({"name": name, "returncode": completed.returncode, "status": "ok" if completed.returncode == 0 else "error"})
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"name": name, "returncode": None, "status": "error", "error_class": type(exc).__name__})
    failed = [row for row in results if row.get("status") != "ok"]
    elapsed_seconds = time.monotonic() - started
    latency_ms = int(math.ceil(elapsed_seconds * 1000))
    sla_status = "met" if elapsed_seconds <= OUTCOME_REFRESH_SLA_SECONDS else "breached"
    return {
        "status": "error" if failed or sla_status == "breached" else "ok",
        "canonical_register_only": True,
        "register_transition_preserved_on_failure": True,
        "provisional_sla_seconds": OUTCOME_REFRESH_SLA_SECONDS,
        "latency_ms": latency_ms,
        "sla_status": sla_status,
        "commands": results,
    }


def requested_action_name(args: argparse.Namespace) -> str:
    if args.plan:
        return "plan"
    if args.lease:
        return "lease"
    if args.complete:
        return "complete"
    if args.set_status:
        return "set-status"
    return "status"


def apply_requested_action(
    register: dict[str, Any],
    args: argparse.Namespace,
    *,
    persist_usage_receipt: bool = True,
) -> tuple[str, dict[str, Any] | None]:
    """Apply one parsed action to an in-memory register."""
    action_name = requested_action_name(args)
    if action_name == "plan":
        return action_name, apply_plan(register, args)
    if action_name == "lease":
        return action_name, apply_lease(
            register,
            args,
            persist_usage_receipt=persist_usage_receipt,
        )
    if action_name == "complete":
        return action_name, apply_complete(register, args)
    if action_name == "set-status":
        return action_name, apply_status(
            register,
            args,
            persist_usage_receipt=persist_usage_receipt,
        )
    return action_name, None


def action_requires_active_lease_admission(args: argparse.Namespace) -> bool:
    """Return whether this write needs active-lane collision validation."""
    if not args.write:
        return False
    if args.plan:
        return True
    return bool((args.lease or args.set_status) and args.lane_status in ACTIVE_STATUSES)


def active_lease_admission_lock_path(register_path: Path) -> Path:
    return register_path.with_name(f"{register_path.name}.active-lease-admission.lock")


def acquire_active_lease_admission_lock(register_path: Path) -> Path:
    """Acquire the shared register transaction lock before any read/write.

    A crash may leave this exact lock file behind.  That is intentional: the
    next writer must resolve the stale lock explicitly rather than racing a
    possibly incomplete register write. Keep the existing lock path so older
    active-admission callers and new terminal/status writers contend together.
    """
    lock_path = active_lease_admission_lock_path(register_path)
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        payload = json.dumps({"pid": os.getpid(), "created_at_utc": utc_now()}, sort_keys=True).encode("utf-8")
        os.write(descriptor, payload)
        os.fsync(descriptor)
    except Exception:
        os.close(descriptor)
        descriptor = -1
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return lock_path


def release_active_lease_admission_lock(lock_path: Path | None) -> None:
    if lock_path is None:
        return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def lock_admission_failure(lock_path: Path, error: str) -> dict[str, Any]:
    failure = {
        "name": "active_lease_admission_lock_available",
        "ok": False,
        "status": "fail",
        "severity": "critical",
        "detail": {"lock_path": str(lock_path), "error": error},
    }
    return {
        "schema": ACTIVE_LEASE_ADMISSION_SCHEMA,
        "scope": "active_lanes_with_full_register_structure",
        "active_lane_count": None,
        "status": "error",
        "errors": [failure],
        "warnings": [],
        "checks": [failure],
    }


def print_lock_admission_failure(action: str, lock_path: Path, error: str) -> None:
    print(json.dumps({
        "action": action,
        "status": "error",
        "summary": None,
        "lane": None,
        "post_write_refresh": {"status": "not_requested"},
        "lease_admission": lock_admission_failure(lock_path, error),
        "validation": {"errors": None, "warnings": None},
    }, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--plan", metavar="WORKFLOW")
    action.add_argument("--lease", metavar="WORKFLOW")
    action.add_argument("--complete", metavar="WORKFLOW")
    action.add_argument("--set-status", metavar="WORKFLOW")
    action.add_argument(
        "--dispatch-task-name",
        metavar="WORKFLOW",
        help="Emit the deterministic opaque v2 dispatch token for an existing lane without writing or spawning.",
    )
    action.add_argument("--status", dest="show_status", action="store_true")
    parser.add_argument("--workstream", default="default", help="Workstream identifier within the workflow.")
    parser.add_argument("--owner", default="unassigned")
    parser.add_argument("--lease-hours", type=float, default=DEFAULT_LEASE_HOURS)
    parser.add_argument("--allowed-write", action="append", default=[])
    parser.add_argument("--read-first", action="append", default=[])
    parser.add_argument("--acceptance-command", action="append", default=[])
    parser.add_argument("--agent-id", default="", help="Configured isolated-agent id for exact attribution.")
    parser.add_argument("--agent-role", default="", help="Role label for the isolated/helper agent.")
    parser.add_argument("--parent-job-id", default="", help="Stable parent PM/job identifier.")
    parser.add_argument("--phase", default="", help="Implementation phase, for example implementation or QA.")
    parser.add_argument("--authority-class", default="", help="Read-only/workspace-write/owner-gated authority class.")
    parser.add_argument("--objective", default="", help="Bounded lane objective metadata.")
    parser.add_argument("--deliverable", default="", help="Expected deliverable metadata.")
    parser.add_argument("--closeout-destination", default="", help="Main-session closeout destination.")
    parser.add_argument("--session-key", default="", help="OpenClaw session key for the helper lane, when known.")
    parser.add_argument("--session-id", default="", help="OpenClaw session id for the helper lane, when known.")
    parser.add_argument("--session-label", default="", help="Human-readable helper session label, when known.")
    parser.add_argument("--task-name", default="", help="Stable OpenClaw taskName/alias for the helper lane, when known.")
    parser.add_argument("--run-id", default="", help="Stable model/runtime run id, when known.")
    parser.add_argument("--model-path", default="", help="Model path for the lane, for example ollama-cloud/glm-5.3:cloud.")
    parser.add_argument("--model-provider", default="", help="Model provider, inferred from --model-path when omitted.")
    parser.add_argument("--thinking", default="", help="Model reasoning/posture level, when exposed.")
    parser.add_argument("--expected-model-path", default="", help="Expected model path; defaults from --model-path for native rollout import.")
    parser.add_argument("--expected-thinking", default="", help="Expected effort; defaults from --thinking for native rollout import.")
    parser.add_argument("--expected-execution-backend", default="", choices=("", *sorted(EXECUTION_BACKENDS)), help="Expected bounded execution backend for route conformance.")
    parser.add_argument("--actual-execution-backend", default="", choices=("", *sorted(EXECUTION_BACKENDS)), help="Observed bounded execution backend for route conformance.")
    parser.add_argument("--task-shape", default="", help="Bounded task-shape identifier for future efficiency cohorts.")
    parser.add_argument("--write-scope", default="", help="Bounded write-scope identifier for future efficiency cohorts.")
    parser.add_argument("--handoff-file-count", type=nonnegative_int_arg, default=None, help="Exact handoff file count when exposed.")
    parser.add_argument("--handoff-total-bytes", type=nonnegative_int_arg, default=None, help="Exact handoff byte total when exposed.")
    parser.add_argument("--handoff-context-tokens", type=nonnegative_int_arg, default=None, help="Exact handoff context token count when exposed.")
    parser.add_argument("--fork-policy", default="", choices=("", *sorted(FORK_POLICIES)), help="Explicit helper transcript fork policy; efficient native work requires none.")
    parser.add_argument("--usage-unavailable-reason", default="", choices=("", *sorted(USAGE_UNAVAILABLE_REASONS)), help="Controlled reason authoritative usage is unavailable.")
    parser.add_argument("--fork-baseline-input-tokens", type=nonnegative_int_arg, default=None)
    parser.add_argument("--fork-baseline-cached-input-tokens", type=nonnegative_int_arg, default=None)
    parser.add_argument("--fork-baseline-output-tokens", type=nonnegative_int_arg, default=None)
    parser.add_argument("--fork-baseline-tool-calls", type=nonnegative_int_arg, default=None)
    parser.add_argument("--max-gross-tokens", type=positive_int_arg, default=None)
    parser.add_argument("--max-cached-replay-tokens", type=positive_int_arg, default=None)
    parser.add_argument("--max-tool-calls", type=positive_int_arg, default=None)
    parser.add_argument("--max-elapsed-seconds", type=positive_int_arg, default=None)
    parser.add_argument("--observed-tool-calls", type=nonnegative_int_arg, default=None)
    parser.add_argument("--observed-elapsed-seconds", type=nonnegative_int_arg, default=None)
    parser.add_argument("--retry-count", type=nonnegative_int_arg, default=None, help="Zero-based retry count for the lane.")
    parser.add_argument("--attempt-number", type=positive_int_arg, default=None, help="One-based attempt number; must equal retry count plus one.")
    parser.add_argument("--attempt-id", default="", help="Stable metadata-only attempt identifier, when available.")
    parser.add_argument("--incident-code", default="", choices=("", *sorted(INCIDENT_CODES)), help="Bounded incident classification; narrative belongs in proof, not telemetry.")
    parser.add_argument("--token-attribution-source", default="", help="Metadata-only source label for token counts, for example provider_usage or runtime_usage.")
    parser.add_argument("--input-token-semantics", default="", choices=("", "exclusive_cached", "inclusive_cached", "no_cache"))
    parser.add_argument("--input-tokens", type=int, default=None, help="Input token count for the lane, when exposed.")
    parser.add_argument("--cached-input-tokens", type=int, default=None, help="Cached-input token count for the lane, when exposed.")
    parser.add_argument("--cache-write-tokens", type=int, default=None, help="Cache-write token count, when exposed.")
    parser.add_argument("--output-tokens", type=int, default=None, help="Output token count for the lane, when exposed.")
    parser.add_argument("--total-tokens", type=int, default=None, help="Total token count for the lane, when exposed.")
    parser.add_argument(
        "--source-input-total-tokens",
        "--source-prompt-tokens",
        dest="source_input_total_tokens",
        type=int,
        default=None,
        help="Source input total used for token reconciliation.",
    )
    parser.add_argument("--source-total-tokens-fresh", choices=("true", "false"), default=None)
    parser.add_argument("--access-mode", default="", choices=("", "chatgpt", "apikey", "unknown"))
    parser.add_argument("--speed-mode", default="", choices=("", "standard", "fast", "unknown"))
    parser.add_argument("--usage-at-utc", default="", help="Observed usage timestamp, when exposed.")
    parser.add_argument("--usage-time-source", default="", help="Metadata-only usage timestamp provenance.")
    parser.add_argument("--outcome-status", default="", help="Implementation outcome classification.")
    parser.add_argument("--main-acceptance-status", default="", help="Main-session acceptance state.")
    parser.add_argument("--main-acceptance-evidence", default="", help="Path/label for Main acceptance evidence.")
    parser.add_argument("--root-objective-id", default="", help="Persistent root objective identity for state lineage.")
    parser.add_argument("--objective-slice-id", default="", help="Stable acceptance slice under the root.")
    parser.add_argument("--predecessor-lane-id", default="", help="Exact predecessor lane id when a successor exists.")
    parser.add_argument("--cumulative-attempt-number", type=positive_int_arg, default=None, help="Cumulative attempt across successor labels; derived when omitted.")
    parser.add_argument("--cumulative-retry-count", type=nonnegative_int_arg, default=None, help="Cumulative retry across successor labels; derived when omitted.")
    parser.add_argument("--accepted-slice-id", default="", help="Accepted slice id; present only when technically accepted.")
    parser.add_argument("--technical-acceptance-status", default="", choices=("", *sorted(TECHNICAL_ACCEPTANCE_STATUSES)), help="Orthogonal technical acceptance state.")
    parser.add_argument("--accounting-status", default="", choices=("", *sorted(ACCOUNTING_STATUSES)), help="Orthogonal accounting state.")
    parser.add_argument("--administrative-closure-status", default="", choices=("", *sorted(ADMIN_CLOSURE_STATUSES)), help="Orthogonal administrative closure state.")
    parser.add_argument("--activation-status", default="", choices=("", *sorted(ACTIVATION_STATUSES)), help="Orthogonal activation state; default remains blocked.")
    parser.add_argument("--validator-result", default="", choices=("", *VALIDATOR_RESULTS), help="Terminal validator disposition for the lane's acceptance commands (metadata-only).")
    parser.add_argument("--closure-durability", default="", choices=("", *CLOSURE_DURABILITY_STATES), help="Whether the closure was verified durable (stayed closed) or not yet (metadata-only).")
    parser.add_argument("--estimated-cost-usd", type=float, default=None, help="Optional closeout cost estimate when exposed; token_usage_ledger remains the canonical local estimate.")
    parser.add_argument("--source-estimated-cost-usd", type=float, default=None, help="Source estimate only; never actual billed cost.")
    parser.add_argument("--import-isolated-session-usage", action="store_true", help="Read exact allowlisted sessions.json metadata for this lane.")
    parser.add_argument(
        "--require-dispatch-binding",
        action="store_true",
        help="Require a terminal privacy-safe core dispatch binding before importing isolated usage.",
    )
    parser.add_argument("--isolated-agent-state-root", type=Path, default=DEFAULT_AGENT_STATE_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--isolated-agent-state-db", type=Path, default=DEFAULT_OPENCLAW_STATE_DB, help=argparse.SUPPRESS)
    parser.add_argument("--import-codex-native-rollout", action="store_true", help="Import allowlisted metadata from one exact completed Codex rollout JSONL.")
    parser.add_argument("--codex-session-id", default="", help="Exact Codex-native session id to import.")
    parser.add_argument("--codex-sessions-root", type=Path, default=DEFAULT_CODEX_SESSIONS_ROOT, help="Codex sessions root; defaults to the main agent Codex sessions directory.")
    parser.add_argument(
        "--replace-contract",
        action="store_true",
        help="Replace template read_first and acceptance commands with explicitly supplied lane contract values.",
    )
    parser.add_argument(
        "--reopen-complete",
        action="store_true",
        help="Allow a completed lane to be re-leased when its proof is stale against current input artifacts.",
    )
    parser.add_argument("--proof", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--status-value", dest="lane_status", default="leased", choices=sorted(VALID_STATUSES))
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--active-lease-safety",
        action="store_true",
        help="Validate only current/prospective active-lane admission; terminal ledger debt remains visible separately.",
    )
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    register_path = args.register if args.register.is_absolute() else ROOT / args.register
    # Downstream source-receipt operations must use the exact same register
    # location as the action, not a cwd-dependent spelling of it.
    args.register = register_path
    action_name = requested_action_name(args)
    admission_required = action_requires_active_lease_admission(args)
    admission_lock: Path | None = None
    if args.write:
        try:
            admission_lock = acquire_active_lease_admission_lock(register_path)
        except FileExistsError:
            lock_path = active_lease_admission_lock_path(register_path)
            print_lock_admission_failure(action_name, lock_path, "active_lease_admission_lock_exists")
            return 1
        except OSError as exc:
            lock_path = active_lease_admission_lock_path(register_path)
            print_lock_admission_failure(action_name, lock_path, f"active_lease_admission_lock_error:{type(exc).__name__}")
            return 1

    try:
        register = load_register(register_path)
        if args.dispatch_task_name:
            return emit_dispatch_task_name(register, args)

        lane: dict[str, Any] | None = None
        lease_admission: dict[str, Any] | None = None
        if admission_required:
            # Admission must be evaluated from a copy before any candidate
            # register or imported-usage receipt becomes durable.
            preview = copy.deepcopy(register)
            _, preview_lane = apply_requested_action(
                preview,
                args,
                persist_usage_receipt=False,
            )
            preview_admission = validate_active_lease_admission(preview)
            if preview_admission.get("status") != "ok":
                receipt_store = usage_receipt_store_path(register_path)
                refresh_summary(
                    register,
                    receipt_store,
                    isolated_agent_state_root=Path(args.isolated_agent_state_root),
                    codex_sessions_root=Path(args.codex_sessions_root),
                )
                print_result(action_name, register, preview_lane, lease_admission=preview_admission)
                return 1

            # Reapply after the preview so any source import is checked against
            # the durable in-memory candidate.  Receipt persistence remains
            # deferred until this second admission check has passed.
            action_name, lane = apply_requested_action(
                register,
                args,
                persist_usage_receipt=False,
            )
            lease_admission = validate_active_lease_admission(register)
            if lease_admission.get("status") != "ok":
                receipt_store = usage_receipt_store_path(register_path)
                refresh_summary(
                    register,
                    receipt_store,
                    isolated_agent_state_root=Path(args.isolated_agent_state_root),
                    codex_sessions_root=Path(args.codex_sessions_root),
                )
                print_result(action_name, register, lane, lease_admission=lease_admission)
                return 1
            if lane is not None:
                persist_reverified_usage_receipt_after_active_admission(lane, args)
        else:
            action_name, lane = apply_requested_action(register, args)

        receipt_store = usage_receipt_store_path(register_path)
        refresh_summary(
            register,
            receipt_store,
            isolated_agent_state_root=Path(args.isolated_agent_state_root),
            codex_sessions_root=Path(args.codex_sessions_root),
        )
        if args.active_lease_safety and lease_admission is None:
            lease_admission = validate_active_lease_admission(register)

        post_write_refresh: dict[str, Any] | None = None
        if args.write:
            atomic_write_json(register_path, register)
            # The durable register transaction is finished. Downstream outcome
            # refresh can be slow; it must not monopolize the write lock.
            release_active_lease_admission_lock(admission_lock)
            admission_lock = None
            refresh_shadow_pilot_after_write(register_path)
            post_write_refresh = refresh_lane_outcome_surfaces(register_path, lane, action_name)
            if lane is not None and post_write_refresh.get("status") != "not_triggered":
                runtime = as_dict(lane.get("runtime"))
                runtime["outcome_refresh"] = {
                    "status": post_write_refresh.get("status"),
                    "provisional_sla_seconds": post_write_refresh.get("provisional_sla_seconds"),
                    "latency_ms": post_write_refresh.get("latency_ms"),
                    "sla_status": post_write_refresh.get("sla_status"),
                    "commands": [
                        {"name": row.get("name"), "status": row.get("status"), "returncode": row.get("returncode")}
                        for row in as_list(post_write_refresh.get("commands"))
                    ],
                }
                lane["runtime"] = runtime
                # Lost-update guard (LANE-RACE-20260913): the outcome-surface
                # refresh above can take up to ~90s. Reacquire the same lock
                # BEFORE loading the fresh register, then merge ONLY our own
                # outcome_refresh. A reload without this lock still races a
                # terminal/status writer and can erase an intervening lease.
                try:
                    admission_lock = acquire_active_lease_admission_lock(register_path)
                except FileExistsError:
                    print_lock_admission_failure(action_name, active_lease_admission_lock_path(register_path),
                                                 "active_lease_admission_lock_exists_after_refresh")
                    return 1
                except OSError as exc:
                    print_lock_admission_failure(action_name, active_lease_admission_lock_path(register_path),
                                                 f"active_lease_admission_lock_error_after_refresh:{type(exc).__name__}")
                    return 1
                fresh_register = load_register(register_path)
                own_lane_id = lane.get("lane_id")
                merged = False
                for existing in as_list(fresh_register.get("lanes")):
                    if isinstance(existing, dict) and existing.get("lane_id") == own_lane_id:
                        existing_runtime = as_dict(existing.get("runtime"))
                        existing_runtime["outcome_refresh"] = runtime["outcome_refresh"]
                        existing["runtime"] = existing_runtime
                        merged = True
                        break
                if not merged:
                    # Defensive only: our lane was durably written before the
                    # refresh, so it must still be present.  Re-upsert rather
                    # than drop the outcome_refresh signal; never touch any
                    # other lane.
                    upsert_lane(fresh_register, lane)
                refresh_summary(
                    fresh_register,
                    receipt_store,
                    isolated_agent_state_root=Path(args.isolated_agent_state_root),
                    codex_sessions_root=Path(args.codex_sessions_root),
                )
                atomic_write_json(register_path, fresh_register)
                # Point the printed result at the durable merged state so the
                # summary/validation shown to the caller match what is on disk.
                register = fresh_register
        print_result(action_name, register, lane, post_write_refresh, lease_admission)
        if args.active_lease_safety and lease_admission and lease_admission.get("status") != "ok":
            return 1
        if post_write_refresh and post_write_refresh.get("status") == "error":
            return 1
        if lane is not None and as_dict(as_dict(lane.get("runtime")).get("resource_budget_guard")).get("status") == "blocked":
            return 1
        if (
            lane is not None
            and lane.get("status") == "blocked"
            and as_dict(lane.get("runtime")).get("usage_credit_status") == "blocked"
        ):
            return 1
        if args.validate and as_dict(register.get("validation")).get("status") != "ok":
            return 1
        return 0
    finally:
        release_active_lease_admission_lock(admission_lock)


if __name__ == "__main__":
    raise SystemExit(main())
