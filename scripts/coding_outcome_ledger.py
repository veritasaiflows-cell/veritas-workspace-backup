#!/usr/bin/env python3
"""Build a durable coding outcome ledger from the lane register.

This is the coding analogue to the finance outcome ledger: it records
completed implementation lanes, their proof artifacts, validation proxy state,
and later-review placeholders. It is review-only and never grants execution,
config, finance, portfolio, account, or cleanup authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from isolated_agent_usage_metadata import (
    build_attempt_correlation_key,
    canonical_correlation_identifier,
    normalize_correlation_phase,
    strict_nonnegative_int,
)
from concurrent_lane_manager import verify_usage_source_receipt
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "tmp" / "concurrent-lane-register.json"
CHANGED_ROUTER = ROOT / "tmp" / "changed-file-validator-router.json"
LEDGER = ROOT / "data" / "state-history" / "coding-outcome-ledger.jsonl"
CURRENT = ROOT / "tmp" / "coding-outcome-ledger-current.json"

SCHEMA = "veritas.coding_outcome_ledger.v1"
CURRENT_SCHEMA = "veritas.coding_outcome_ledger_current.v1"
USAGE_SOURCE_RECEIPTS_SCHEMA = "veritas.model_usage_source_receipts.v1"
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"
TRUSTED_TOKEN_ATTRIBUTION_SOURCES = {
    "codex_native_rollout_jsonl",
    "openclaw_isolated_session_store_v1",
}
EX_POST_REVIEW_MIN_AGE_HOURS = 24.0
MIN_GRADED_ROWS_FOR_MODEL_PERFORMANCE_CLAIM = 30
MIN_GRADED_ROWS_PER_MODEL_FOR_MODEL_COMPARISON = 10
MIN_ACCEPTED_ROWS_FOR_COMPARABLE_COHORT = 10
EXECUTION_BACKENDS = {"model_free_command", "persistent_isolated_agent", "codex_native_subagent", "main"}
THINKING_LEVELS = {"none", "low", "medium", "high"}
MAIN_ACCEPTED_STATUSES = {"accepted", "accepted-with-documented-limits"}
TERMINAL_LANE_STATUSES = {"complete", "blocked", "cancelled", "failed", "error", "rejected"}

# Historical lanes where the closeout carried acceptance commands but omitted
# proof_artifacts before the ledger started enforcing that field. Keep this
# narrow and visible instead of rewriting the append-only ledger.
LEGACY_PROOF_REMEDIATIONS = {
    "WF78::tier-label-preview-audit-flag": {
        "reason": "historical_closeout_omitted_proof_artifacts",
        "proof_artifacts": [
            "legacy remediation: acceptance command set was declared; original lane omitted proof_artifacts"
        ],
    },
    "WF78::tier-semantics-cron-wiring": {
        "reason": "historical_closeout_omitted_proof_artifacts",
        "proof_artifacts": [
            "legacy remediation: acceptance command set was declared; original lane omitted proof_artifacts"
        ],
    },
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "coding_outcome_tracking_only": True,
    "append_only": True,
    "spawns_helpers": False,
    "scheduler_allowed": False,
    "autonomous_execution_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
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


def nonnegative_int(value: Any) -> int | None:
    parsed = as_int(value)
    return parsed if parsed is not None and parsed >= 0 else None


def privacy_safe_fingerprint(value: Any, prefix: str) -> str | None:
    """Return a deterministic metadata reference without serializing source text."""
    if not isinstance(value, str) or not value.strip():
        return None
    return f"{prefix}_sha256:{hashlib.sha256(value.strip().encode('utf-8')).hexdigest()[:16]}"


def inventory_fingerprint(values: list[str], prefix: str) -> str | None:
    if not values:
        return None
    # Sorting makes an inventory reference deterministic without retaining its
    # raw command, artifact, or path contents.
    joined = "\n".join(sorted(values))
    return f"{prefix}_sha256:{hashlib.sha256(joined.encode('utf-8')).hexdigest()[:16]}"


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main_acceptance(runtime: dict[str, Any], lane: dict[str, Any]) -> tuple[str | None, bool | None]:
    """Prefer the controlled status, retaining the legacy boolean only if absent."""
    value = runtime.get("main_acceptance_status")
    if value is None:
        value = lane.get("main_acceptance_status")
    if isinstance(value, str) and value.strip():
        status = value.strip().lower()
        return status, status in MAIN_ACCEPTED_STATUSES
    legacy = runtime.get("main_accepted") if runtime.get("main_accepted") is not None else lane.get("main_accepted")
    return None, legacy if isinstance(legacy, bool) else None


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": str(exc), "_line_number": line_number})
            continue
        rows.append(value if isinstance(value, dict) else {"_parse_error": "row is not an object", "_line_number": line_number})
    return rows


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def model_lane_requires_creditable_usage(lane: dict[str, Any], runtime: dict[str, Any]) -> bool:
    """Apply the strict source-receipt contract to new terminal model lanes.

    Older append-only outcome rows remain visible as historical process
    evidence.  They must not be retroactively relabelled as provider-backed
    usage, but the cutover prevents a new model lane from entering any
    efficiency or acceptance denominator without a receipt.
    """
    if not (runtime.get("model_path") or lane.get("model_path")):
        return False
    cutoff = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    observed = parse_utc(lane.get("created_at_utc")) or parse_utc(
        lane.get("completed_at_utc") or lane.get("ended_at_utc")
    )
    if observed is None:
        return str(lane.get("status") or "") in TERMINAL_LANE_STATUSES
    return cutoff is not None and observed >= cutoff


def load_usage_source_receipts(register_path: Path) -> list[dict[str, Any]]:
    """Load the manager-owned sidecar; it is evidence, never an authority."""
    payload = as_dict(load_json(register_path.with_suffix(".usage-receipts.json")))
    if payload.get("schema") != USAGE_SOURCE_RECEIPTS_SCHEMA:
        return []
    return [row for row in as_list(payload.get("receipts")) if isinstance(row, dict)]


def source_receipt_matches_lane(
    lane: dict[str, Any],
    receipts: list[dict[str, Any]],
    *,
    register_path: Path = REGISTER,
) -> bool:
    """Use the manager's shared source re-opener, not a mutable SHA sidecar."""
    del receipts  # The register-adjacent sidecar is consulted by the verifier.
    runtime = as_dict(lane.get("runtime"))
    return not verify_usage_source_receipt(
        lane,
        runtime,
        register_path.with_suffix(".usage-receipts.json"),
    )


def event_id_for_lane(lane: dict[str, Any]) -> str:
    lane_id = str(lane.get("lane_id") or "")
    completed = str(lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc") or "")
    digest = hashlib.sha256(f"{lane_id}|{completed}".encode("utf-8")).hexdigest()[:16]
    return f"coding_{digest}"


def duration_minutes(lane: dict[str, Any]) -> float | None:
    start = parse_utc(lane.get("started_at_utc") or lane.get("created_at_utc"))
    end = parse_utc(lane.get("ended_at_utc") or lane.get("completed_at_utc") or lane.get("updated_at_utc"))
    if not start or not end or end < start:
        return None
    return round((end - start).total_seconds() / 60.0, 2)


def lane_kind(lane: dict[str, Any]) -> str:
    writes = [str(item).replace("\\", "/") for item in as_list(lane.get("allowed_writes"))]
    if any(path.startswith("scripts/") for path in writes):
        return "script_or_validator_implementation"
    if any(path.startswith("state/workflows/") or "Project Continuity/" in path for path in writes):
        return "workflow_control_implementation"
    if any(path.startswith("tmp/") for path in writes):
        return "proof_artifact_lane"
    return "coordination_or_note_lane"


def validation_proxy(changed_router: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(changed_router.get("summary"))
    validation = as_dict(changed_router.get("validation"))
    return {
        "source": rel(CHANGED_ROUTER),
        "status": changed_router.get("status"),
        "validation_status": validation.get("status"),
        "recommended_budget": summary.get("recommended_budget"),
        "changed_path_count": summary.get("changed_path_count"),
        "recommendation_count": summary.get("recommendation_count"),
        "validator_passed": changed_router.get("status") == "ok" and validation.get("status") in {None, "ok"},
    }


def runtime_stamp(
    lane: dict[str, Any],
    source_receipts: list[dict[str, Any]] | None = None,
    *,
    register_path: Path = REGISTER,
) -> dict[str, Any]:
    runtime = as_dict(lane.get("runtime"))
    classification = as_dict(lane.get("classification"))
    lane_id = str(lane.get("lane_id") or "")
    correlation_lane_id = canonical_correlation_identifier(lane.get("lane_id"))
    started = str(lane.get("started_at_utc") or lane.get("created_at_utc") or "")
    completed = str(lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc") or "")
    model_path = runtime.get("model_path") or lane.get("model_path")
    provider = None
    if isinstance(model_path, str) and "/" in model_path:
        provider = model_path.split("/", 1)[0]
    input_tokens = nonnegative_int(runtime.get("input_tokens"))
    cached_input_tokens = nonnegative_int(runtime.get("cached_input_tokens"))
    output_tokens = nonnegative_int(runtime.get("output_tokens"))
    total_tokens = nonnegative_int(runtime.get("total_tokens"))
    estimated_cost_usd = as_float(runtime.get("estimated_cost_usd"))
    cache_relationship_valid = (
        input_tokens is None or cached_input_tokens is None or cached_input_tokens <= input_tokens
    )
    token_integrity_status = "invalid_cache_relationship" if not cache_relationship_valid else "ok"
    token_integrity_reason = "cached_input_tokens_exceeds_input_tokens" if not cache_relationship_valid else None
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        # Provider input is inclusive of its cached subset.  Cache is a
        # discount/attribution dimension, not another input token bucket.
        total_tokens = input_tokens + output_tokens
    uncached_input_tokens = (
        input_tokens - cached_input_tokens
        if input_tokens is not None and cached_input_tokens is not None and cache_relationship_valid else None
    )
    gross_tokens = input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
    observed_components = {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
    }
    if not cache_relationship_valid:
        # Observations stay explicitly non-authoritative; no invalid token
        # component may enter efficiency sums.
        input_tokens = cached_input_tokens = output_tokens = total_tokens = gross_tokens = uncached_input_tokens = None
    credit_enforcement_required = model_lane_requires_creditable_usage(lane, runtime)
    source_receipt_verified = source_receipt_matches_lane(lane, source_receipts or [], register_path=register_path)
    usage_creditable = (
        not credit_enforcement_required
        or (
            runtime.get("usage_creditable") is True
            and runtime.get("usage_credit_status") == "creditable"
            and source_receipt_verified
        )
    )
    usage_credit_status = (
        "creditable" if usage_creditable and credit_enforcement_required
        else ("legacy_unverified" if not credit_enforcement_required else "blocked")
    )
    uncredited_observed_components = None
    if credit_enforcement_required and not usage_creditable:
        uncredited_observed_components = {
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }
        # Preserve the raw observation only as audit evidence.  It may not
        # enter token, cost, acceptance, or efficiency aggregates.
        input_tokens = cached_input_tokens = output_tokens = total_tokens = gross_tokens = uncached_input_tokens = None
        estimated_cost_usd = None
    token_usage = {
        "input_tokens": input_tokens,
        "input_tokens_inclusive_cache": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "gross_tokens": gross_tokens,
        "integrity_status": token_integrity_status,
        "integrity_reason": token_integrity_reason,
        "non_authoritative_observed_components": observed_components if not cache_relationship_valid else None,
        "cache_semantics": "input_tokens_inclusive_of_cached_input; uncached_input_tokens=input_tokens-cached_input_tokens; gross_tokens=input_tokens+output_tokens",
        "estimated_cost_usd": estimated_cost_usd,
        "token_attribution_source": runtime.get("token_attribution_source"),
        "token_attributed": total_tokens is not None and usage_creditable,
        "credit_enforcement_required": credit_enforcement_required,
        "usage_creditable": usage_creditable,
        "usage_credit_status": usage_credit_status,
        "usage_source_receipt_verified": source_receipt_verified,
        "uncredited_observed_components": uncredited_observed_components,
    }
    parent_job_id = canonical_correlation_identifier(
        runtime.get("parent_job_id") if runtime.get("parent_job_id") is not None else lane.get("parent_job_id")
    )
    phase = normalize_correlation_phase(
        runtime.get("phase") if runtime.get("phase") is not None else lane.get("phase")
    )
    attempt_id_source = runtime.get("attempt_id") if runtime.get("attempt_id") is not None else lane.get("attempt_id")
    attempt_id = canonical_correlation_identifier(attempt_id_source)
    explicit_retry = runtime.get("retry_count") if runtime.get("retry_count") is not None else lane.get("retry_count")
    parsed_retry_count = strict_nonnegative_int(explicit_retry)
    attempt_correlation = build_attempt_correlation_key(
        parent_job_id=parent_job_id,
        lane_id=correlation_lane_id,
        phase=phase,
        attempt_id=attempt_id_source,
        retry_count=explicit_retry,
    )
    expected_model_path = runtime.get("expected_model_path") or lane.get("expected_model_path")
    expected_thinking = runtime.get("expected_thinking") or lane.get("expected_thinking")
    expected_backend = runtime.get("expected_execution_backend") or lane.get("expected_execution_backend")
    actual_model_path = runtime.get("actual_model_path") or model_path
    # The lane manager's observed effort field is `thinking`.  Preserve the
    # explicit `actual_thinking` compatibility field, but do not discard live
    # route evidence when the canonical runtime shape is used.
    actual_thinking = runtime.get("actual_thinking") or runtime.get("thinking") or lane.get("actual_thinking") or lane.get("thinking")
    actual_backend = runtime.get("actual_execution_backend") or lane.get("actual_execution_backend")
    expected_complete = bool(
        isinstance(expected_model_path, str) and expected_model_path.strip()
        and expected_thinking in THINKING_LEVELS
        and expected_backend in EXECUTION_BACKENDS
    )
    actual_complete = bool(
        isinstance(actual_model_path, str) and actual_model_path.strip()
        and actual_thinking in THINKING_LEVELS
        and actual_backend in EXECUTION_BACKENDS
    )
    if not expected_complete:
        route_conformance = "unavailable_legacy"
        mismatches: list[str] = []
    elif not actual_complete:
        route_conformance = "unavailable_actual_route"
        mismatches = []
    else:
        pairs = {
            "model_path": (expected_model_path, actual_model_path),
            "thinking": (expected_thinking, actual_thinking),
            "execution_backend": (expected_backend, actual_backend),
        }
        mismatches = [key for key, (expected, actual) in pairs.items() if expected != actual]
        route_conformance = "conformant" if not mismatches else "mismatch"
    main_acceptance_status, main_accepted = main_acceptance(runtime, lane)
    task_shape = runtime.get("task_shape") or lane.get("task_shape") or classification.get("task_shape")
    authority_class = runtime.get("authority_class") or lane.get("authority_class") or classification.get("authority_class")
    write_scope = runtime.get("write_scope") or lane.get("write_scope") or classification.get("write_scope")
    handoff_file_count = strict_nonnegative_int(runtime.get("handoff_file_count"))
    handoff_total_bytes = strict_nonnegative_int(runtime.get("handoff_total_bytes"))
    handoff_context_tokens = strict_nonnegative_int(runtime.get("handoff_context_tokens"))
    return {
        "run_reference": privacy_safe_fingerprint(runtime.get("run_id") or stable_run_id(lane_id, started, completed), "run"),
        "session_reference": privacy_safe_fingerprint(
            runtime.get("session_id") or runtime.get("session_key") or runtime.get("session_label") or lane.get("session_id"), "session"
        ),
        "task_reference": privacy_safe_fingerprint(runtime.get("task_name") or lane.get("workstream_id"), "task"),
        "model_path": model_path,
        "model_provider": runtime.get("model_provider") or provider,
        "model_attributed": bool(model_path),
        "session_attributed": bool(runtime.get("session_id") or runtime.get("session_key") or runtime.get("session_label")),
        "token_usage": token_usage,
        "parent_job_id": parent_job_id,
        "phase": phase,
        "attempt_id": attempt_id,
        "retry_count": parsed_retry_count,
        "attempt_correlation": attempt_correlation,
        "route_attribution": {
            "expected_model_path": expected_model_path,
            "expected_thinking": expected_thinking,
            "expected_execution_backend": expected_backend,
            "actual_model_path": actual_model_path,
            "actual_thinking": actual_thinking,
            "actual_execution_backend": actual_backend,
            "route_conformance": route_conformance,
            "mismatch_fields": mismatches,
            "main_accepted": main_accepted,
            "main_acceptance_status": main_acceptance_status,
            "task_shape": task_shape,
            "authority_class": authority_class,
            "write_scope": write_scope,
            "handoff_file_count": handoff_file_count,
            "handoff_total_bytes": handoff_total_bytes,
            "handoff_context_tokens": handoff_context_tokens,
        },
    }


def stable_run_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return f"run_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def edit_churn(writes: list[str]) -> dict[str, Any]:
    normalized = [item.replace("\\", "/") for item in writes]
    return {
        "allowed_write_count": len(normalized),
        "script_write_count": sum(1 for item in normalized if item.startswith("scripts/")),
        "test_write_count": sum(1 for item in normalized if item.startswith("scripts/test_")),
        "tmp_artifact_write_count": sum(1 for item in normalized if item.startswith("tmp/")),
        "memory_write_count": sum(1 for item in normalized if item.startswith("memory/")),
        "state_or_data_write_count": sum(1 for item in normalized if item.startswith("state/") or item.startswith("data/")),
    }


def reviewable_code_paths(row: dict[str, Any]) -> set[str]:
    tokens = {
        str(token) for token in as_list(row.get("reviewable_path_tokens"))
        if isinstance(token, str) and token.startswith("path_sha256:")
    }
    if tokens:
        return tokens
    # Append-only legacy fallback only: new records emit tokens, never paths.
    paths: set[str] = set()
    for item in as_list(row.get("allowed_writes")):
        normalized = str(item).replace("\\", "/").strip().lstrip("./")
        if not normalized or normalized in {"scripts", "scripts/"}:
            continue
        if normalized.startswith("scripts/"):
            paths.add(f"path_sha256:{hashlib.sha256(normalized.lower().encode('utf-8')).hexdigest()[:16]}")
    return paths


def row_end_time(row: dict[str, Any]) -> datetime | None:
    return (
        parse_utc(row.get("completed_at_utc"))
        or parse_utc(row.get("ended_at_utc"))
        or parse_utc(row.get("recorded_at_utc"))
    )


def validator_failed(row: dict[str, Any]) -> bool:
    proxy = as_dict(row.get("validation_proxy"))
    validation_status = proxy.get("validation_status")
    status = proxy.get("status")
    if proxy.get("validator_passed") is False:
        return True
    if validation_status in {"error", "critical"}:
        return True
    return status not in {None, "ok"}


def validator_state(row: dict[str, Any]) -> str:
    outcome = as_dict(row.get("coding_outcome"))
    if outcome.get("validator_proxy_passed") is True:
        return "passed"
    if validator_failed(row):
        return "failed"
    if outcome.get("validator_proxy_passed") is None:
        return "legacy_unknown"
    return "unknown"


def apply_legacy_proof_remediations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remediated = json.loads(json.dumps(rows))
    for row in remediated:
        if row.get("_parse_error"):
            continue
        lane_id = str(row.get("lane_id") or "")
        remediation = LEGACY_PROOF_REMEDIATIONS.get(lane_id)
        if not remediation:
            continue
        outcome = as_dict(row.get("coding_outcome"))
        row["coding_outcome"] = outcome
        if outcome.get("proof_attached") is True:
            continue
        artifacts = [str(item) for item in as_list(remediation.get("proof_artifacts")) if str(item).strip()]
        row["proof_artifacts"] = artifacts
        row["proof_artifact_count"] = len(artifacts)
        outcome["proof_attached"] = bool(artifacts)
        outcome["proof_remediated"] = True
        outcome["proof_remediation_reason"] = remediation.get("reason")
        outcome["proof_remediation_source"] = "LEGACY_PROOF_REMEDIATIONS"
    return remediated


def followup_documented(row: dict[str, Any]) -> bool:
    outcome = as_dict(row.get("coding_outcome"))
    return (
        outcome.get("implementation_completed") is True
        and outcome.get("acceptance_commands_declared") is True
        and outcome.get("proof_attached") is True
        and validator_state(row) != "failed"
    )


def model_performance_claim_gate(graded_count: int, by_model: dict[str, dict[str, Any]]) -> dict[str, Any]:
    eligible_models = [
        model
        for model, stats in by_model.items()
        if int(as_dict(stats).get("graded_count") or 0) >= MIN_GRADED_ROWS_PER_MODEL_FOR_MODEL_COMPARISON
        and model not in {"", "UNKNOWN"}
    ]
    sample_gate_met = graded_count >= MIN_GRADED_ROWS_FOR_MODEL_PERFORMANCE_CLAIM
    comparison_gate_met = len(eligible_models) >= 2
    return {
        "schema": "veritas.coding_model_performance_claim_gate.v1",
        "model_performance_claim_allowed": False,
        "review_only_process_metric_available": graded_count > 0,
        "graded_count": graded_count,
        "required_graded_count": MIN_GRADED_ROWS_FOR_MODEL_PERFORMANCE_CLAIM,
        "sample_gate_met": sample_gate_met,
        "model_comparison_allowed": False,
        "model_comparison_sample_gate_met": comparison_gate_met,
        "required_graded_rows_per_model_for_comparison": MIN_GRADED_ROWS_PER_MODEL_FOR_MODEL_COMPARISON,
        "eligible_model_count_for_comparison": len(eligible_models),
        "eligible_models_for_comparison": sorted(eligible_models),
        "reason": (
            "Coding outcome rows are later-review process telemetry. They can guide workflow repair, "
            "but they do not authorize model-performance claims or model ranking."
        ),
    }


def apply_ex_post_reviews(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive later-review grades without mutating the append-only ledger."""
    reviewed = apply_legacy_proof_remediations(rows)
    clean_rows = [row for row in reviewed if not row.get("_parse_error")]
    now = datetime.now(timezone.utc)
    for index, row in enumerate(clean_rows):
        outcome = as_dict(row.get("coding_outcome"))
        row["coding_outcome"] = outcome
        paths = reviewable_code_paths(row)
        if not outcome.get("implementation_completed"):
            outcome["later_review_status"] = outcome.get("later_review_status") or "not_completed"
            continue
        if not paths:
            outcome["later_review_status"] = outcome.get("later_review_status") or "not_reviewable_no_code_paths"
            continue
        completed = row_end_time(row)
        if not completed:
            outcome["later_review_status"] = outcome.get("later_review_status") or "pending_later_regression_review"
            continue
        age_hours = (now - completed).total_seconds() / 3600
        later_rows = []
        for candidate in clean_rows[index + 1:]:
            candidate_time = row_end_time(candidate)
            if not candidate_time or candidate_time <= completed:
                continue
            overlap = paths & reviewable_code_paths(candidate)
            if overlap:
                later_rows.append((candidate, sorted(overlap)))
        if later_rows:
            regression_rows = [candidate for candidate, _ in later_rows if validator_failed(candidate)]
            undocumented_rows = [candidate for candidate, _ in later_rows if not followup_documented(candidate)]
            outcome["rework_required"] = bool(regression_rows or undocumented_rows)
            outcome["regression_observed"] = bool(regression_rows)
            if regression_rows:
                outcome["later_review_status"] = "later_validator_failure_on_touched_path"
            elif undocumented_rows:
                outcome["later_review_status"] = "undocumented_later_retouch"
            else:
                outcome["later_review_status"] = "documented_later_followup"
            outcome["later_retouch_count"] = len(later_rows)
            outcome["later_retouch_lane_ids"] = [candidate.get("lane_id") for candidate, _ in later_rows[:5]]
            outcome["undocumented_later_retouch_count"] = len(undocumented_rows)
            outcome["documented_later_followup"] = not undocumented_rows
            outcome["reviewed_at_utc"] = utc_now()
            continue
        if age_hours >= EX_POST_REVIEW_MIN_AGE_HOURS:
            outcome["rework_required"] = False
            outcome["regression_observed"] = False
            outcome["later_review_status"] = "clean_after_review_window"
            outcome["reviewed_at_utc"] = utc_now()
            outcome["review_window_hours"] = EX_POST_REVIEW_MIN_AGE_HOURS
        else:
            outcome["later_review_status"] = outcome.get("later_review_status") or "pending_later_regression_review"
    return reviewed


def retry_count(lane: dict[str, Any]) -> int | None:
    runtime = as_dict(lane.get("runtime"))
    explicit = runtime.get("retry_count") if runtime.get("retry_count") is not None else lane.get("retry_count")
    return strict_nonnegative_int(explicit)


def row_requires_creditable_usage(row: dict[str, Any]) -> bool:
    """Derive the cutover rule even for old append-only record shapes."""
    usage = as_dict(row.get("token_usage"))
    declared = usage.get("credit_enforcement_required")
    model_path = row.get("model_path") or as_dict(row.get("route_attribution")).get("actual_model_path")
    observed = parse_utc(row.get("created_at_utc")) or parse_utc(row.get("completed_at_utc"))
    cutoff = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    # A mutable historical row must not be able to opt itself out of the
    # post-cutover receipt requirement.  A positive declaration is additive;
    # a negative declaration is only descriptive.  The time/model rule is the
    # authority for the historical exception.
    derived_required = bool(model_path) and (
        observed is None
        or cutoff is None
        or observed >= cutoff
    )
    return declared is True or derived_required


def telemetry_metrics_eligible(row: dict[str, Any]) -> bool:
    """Fail closed: post-cutover model metrics need a verified receipt."""
    if not row_requires_creditable_usage(row):
        return True
    usage = as_dict(row.get("token_usage"))
    return bool(
        usage.get("usage_creditable") is True
        and usage.get("usage_credit_status") == "creditable"
        and usage.get("usage_source_receipt_verified") is True
    )


def comparable_cohort_key(row: dict[str, Any]) -> str | None:
    """Return a strict comparable-cohort key, or None for legacy/incomplete rows."""
    route = as_dict(row.get("route_attribution"))
    if (
        incident_row(row)
        or as_dict(row.get("token_usage")).get("integrity_status", "ok") != "ok"
        or not telemetry_metrics_eligible(row)
        or route.get("route_conformance") != "conformant"
        or route.get("main_accepted") is not True
    ):
        return None
    parts = (
        route.get("task_shape"),
        route.get("authority_class"),
        route.get("write_scope"),
        route.get("actual_execution_backend"),
        route.get("actual_model_path"),
        route.get("actual_thinking"),
    )
    if not all(isinstance(item, str) and item.strip() for item in parts):
        return None
    return "|".join(str(item).strip() for item in parts)


def route_accepted(row: dict[str, Any]) -> bool:
    route = as_dict(row.get("route_attribution"))
    token_usage = as_dict(row.get("token_usage"))
    return bool(
        not incident_row(row)
        and token_usage.get("integrity_status", "ok") == "ok"
        and telemetry_metrics_eligible(row)
        and route.get("route_conformance") == "conformant"
        and route.get("main_accepted") is True
        and as_dict(row.get("coding_outcome")).get("implementation_completed") is True
    )


def first_pass_accepted(row: dict[str, Any]) -> bool:
    outcome = as_dict(row.get("coding_outcome"))
    return bool(
        route_accepted(row)
        and outcome.get("validator_proxy_passed") is True
        and strict_nonnegative_int(outcome.get("retry_count")) == 0
        and outcome.get("rework_required") is False
        and outcome.get("regression_observed") is False
    )


def metric_coverage(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    """Expose partial telemetry without presenting it as a complete aggregate."""
    values = [
        as_dict(row.get("token_usage")).get(field)
        if as_dict(row.get("token_usage")).get(field) is not None
        else as_dict(row.get("route_attribution")).get(field)
        for row in rows
    ]
    numbers = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    total_row_count = len(rows)
    available_count = len(numbers)
    missing_count = total_row_count - available_count
    return {
        "value": sum(numbers) if total_row_count and missing_count == 0 else None,
        "observed_partial_sum": sum(numbers) if numbers else None,
        "available_count": available_count,
        "missing_count": missing_count,
        "total_row_count": total_row_count,
        "status": "complete" if total_row_count and missing_count == 0 else ("partial" if numbers else "unavailable"),
    }


def sum_available(rows: list[dict[str, Any]], field: str) -> int | float | None:
    """Legacy helper: authoritative value only, never a partial total."""
    return metric_coverage(rows, field)["value"]


def summarize_comparable_cohorts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cohorts: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = comparable_cohort_key(row)
        if key and route_accepted(row):
            cohorts.setdefault(key, []).append(row)
    summary: dict[str, dict[str, Any]] = {}
    for key, cohort_rows in sorted(cohorts.items()):
        token_coverage = {
            "gross_input_tokens": metric_coverage(cohort_rows, "input_tokens_inclusive_cache"),
            "uncached_input_tokens": metric_coverage(cohort_rows, "uncached_input_tokens"),
            "output_tokens": metric_coverage(cohort_rows, "output_tokens"),
            "gross_tokens": metric_coverage(cohort_rows, "gross_tokens"),
        }
        retry_counts = [
            strict_nonnegative_int(as_dict(row.get("coding_outcome")).get("retry_count"))
            for row in cohort_rows
        ]
        known_retries = [value for value in retry_counts if value is not None]
        elapsed = [row.get("duration_minutes") for row in cohort_rows]
        elapsed_numbers = [value for value in elapsed if isinstance(value, (int, float)) and not isinstance(value, bool)]
        accepted_count = len(cohort_rows)
        sample_gate_met = accepted_count >= MIN_ACCEPTED_ROWS_FOR_COMPARABLE_COHORT
        summary[key] = {
            "accepted_count": accepted_count,
            "first_pass_accepted_count": sum(1 for row in cohort_rows if first_pass_accepted(row)),
            "gross_input_tokens": token_coverage["gross_input_tokens"]["value"],
            "uncached_input_tokens": token_coverage["uncached_input_tokens"]["value"],
            "output_tokens": token_coverage["output_tokens"]["value"],
            "gross_tokens": token_coverage["gross_tokens"]["value"],
            "token_coverage": token_coverage,
            "elapsed_minutes": round(sum(elapsed_numbers), 2) if elapsed_numbers else None,
            "retry_tax": {
                "known_retry_row_count": len(known_retries),
                "total_retry_count": sum(known_retries) if known_retries else None,
                "rows_with_retry_count": sum(1 for value in known_retries if value > 0),
            },
            "sample_gate_met": sample_gate_met,
            "required_accepted_count": MIN_ACCEPTED_ROWS_FOR_COMPARABLE_COHORT,
            "route_ranking_or_promotion_allowed": False,
            "note": "The ten-job gate only makes the cohort comparable; this review-only ledger never ranks or promotes models automatically.",
        }
    return summary


def build_record(
    lane: dict[str, Any],
    changed_router: dict[str, Any],
    source_receipts: list[dict[str, Any]] | None = None,
    *,
    register_path: Path = REGISTER,
) -> dict[str, Any]:
    proofs = [str(item) for item in as_list(lane.get("proof_artifacts")) if str(item).strip()]
    acceptance = [str(item) for item in as_list(lane.get("acceptance_commands")) if str(item).strip()]
    writes = [str(item) for item in as_list(lane.get("allowed_writes")) if str(item).strip()]
    reviewable_path_tokens = sorted({
        f"path_sha256:{hashlib.sha256(item.replace('\\', '/').strip().lstrip('./').lower().encode('utf-8')).hexdigest()[:16]}"
        for item in writes
        if item.replace("\\", "/").strip().lstrip("./").lower().startswith("scripts/")
    })
    stamp = runtime_stamp(lane, source_receipts, register_path=register_path)
    runtime = as_dict(lane.get("runtime"))
    proxy = validation_proxy(changed_router)
    route = as_dict(stamp.get("route_attribution"))
    record = {
        "schema": SCHEMA,
        "event_id": event_id_for_lane(lane),
        "recorded_at_utc": utc_now(),
        "run_reference": stamp["run_reference"],
        "session_reference": stamp["session_reference"],
        "task_reference": stamp["task_reference"],
        "model_path": stamp["model_path"],
        "model_provider": stamp["model_provider"],
        "expected_model_path": route.get("expected_model_path"),
        "expected_thinking": route.get("expected_thinking"),
        "expected_execution_backend": route.get("expected_execution_backend"),
        "actual_model_path": route.get("actual_model_path"),
        "actual_thinking": route.get("actual_thinking"),
        "actual_execution_backend": route.get("actual_execution_backend"),
        "parent_job_id": stamp["parent_job_id"],
        "phase": stamp["phase"],
        "attempt_id": stamp["attempt_id"],
        "attempt_correlation": stamp["attempt_correlation"],
        "workflow_id": lane.get("workflow_id"),
        "lane_status": lane.get("status"),
        "lane_kind": lane_kind(lane),
        "created_at_utc": lane.get("created_at_utc"),
        "started_at_utc": lane.get("started_at_utc"),
        "completed_at_utc": lane.get("completed_at_utc") or lane.get("ended_at_utc"),
        "duration_minutes": duration_minutes(lane),
        "allowed_write_count": len(writes),
        "write_inventory_fingerprint": inventory_fingerprint(writes, "writes"),
        "reviewable_path_tokens": reviewable_path_tokens,
        "acceptance_command_count": len(acceptance),
        "acceptance_command_inventory_fingerprint": inventory_fingerprint(acceptance, "acceptance_commands"),
        "proof_artifact_count": len(proofs),
        "proof_artifact_inventory_fingerprint": inventory_fingerprint(proofs, "proof_artifacts"),
        "token_usage": stamp["token_usage"],
        "route_attribution": route,
        "comparable_cohort_key": None,
        "coding_outcome": {
            "implementation_completed": lane.get("status") == "complete",
            "telemetry_credit_eligible": telemetry_metrics_eligible({
                "model_path": stamp["model_path"],
                "created_at_utc": lane.get("created_at_utc"),
                "completed_at_utc": lane.get("completed_at_utc") or lane.get("ended_at_utc"),
                "lane_status": lane.get("status"),
                "token_usage": stamp["token_usage"],
            }),
            "proof_attached": bool(proofs),
            "acceptance_commands_declared": bool(acceptance),
            "validator_proxy_passed": proxy.get("validator_passed"),
            "retry_count": stamp["retry_count"],
            "main_accepted": route.get("main_accepted"),
            # Runtime outcome fields are controlled closeout metadata.  Keep
            # them as evidence so an incident remains an incident even when a
            # contradictory lane status says complete.
            "outcome_event_kind": runtime.get("outcome_event_kind") if runtime.get("outcome_event_kind") is not None else lane.get("outcome_event_kind"),
            "incident_code": runtime.get("incident_code") if runtime.get("incident_code") is not None else lane.get("incident_code"),
            "route_conformance": route.get("route_conformance"),
            "route_mismatch_fail_closed": route.get("route_conformance") == "mismatch",
            "edit_churn": edit_churn(writes),
            "rework_required": None,
            "regression_observed": None,
            "later_review_status": "pending_later_regression_review",
        },
        "attribution": {
            "run_id_present": bool(stamp["run_reference"]),
            "session_present": bool(stamp["session_attributed"]),
            "model_present": bool(stamp["model_attributed"]),
            "token_present": bool(as_dict(stamp.get("token_usage")).get("token_attributed")),
            "token_source_present": bool(as_dict(stamp.get("token_usage")).get("token_attribution_source")),
            "usage_creditable": as_dict(stamp.get("token_usage")).get("usage_creditable") is True,
            "usage_source_receipt_verified": as_dict(stamp.get("token_usage")).get("usage_source_receipt_verified") is True,
            "attempt_correlation_present": bool(stamp.get("attempt_correlation")),
            "producer_present": True,
        },
        "validation_proxy": proxy,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Coding ledger rows are tracking evidence only.",
            "No helper spawn, scheduler, config/runtime mutation, destructive cleanup, finance canon mutation, capital action, or trade authority.",
        ],
    }
    record["comparable_cohort_key"] = comparable_cohort_key(record)
    return record


def completed_lanes(register: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        lane for lane in as_list(register.get("lanes"))
        if isinstance(lane, dict) and lane.get("status") == "complete" and lane.get("lane_id")
    ]


def append_new_records(records: list[dict[str, Any]], ledger_path: Path) -> dict[str, Any]:
    existing = load_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    appended: list[str] = []
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        for record in records:
            event_id = str(record.get("event_id") or "")
            if not event_id or event_id in existing_ids:
                continue
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            appended.append(event_id)
            existing_ids.add(event_id)
    return {
        "status": "ok",
        "ledger": rel(ledger_path),
        "candidate_count": len(records),
        "appended_count": len(appended),
        "skipped_existing_count": len(records) - len(appended),
        "appended_event_ids": appended,
    }


def incident_row(row: dict[str, Any]) -> bool:
    """Incidents are retained as evidence, but are not completed-job denominators."""
    outcome = as_dict(row.get("coding_outcome"))
    event_kind = outcome.get("outcome_event_kind")
    return bool(
        isinstance(event_kind, str) and event_kind.strip().lower() == "incident"
        or row.get("lane_status") == "incident"
        or row.get("incident") is True
        or outcome.get("incident") is True
    )


def terminal_non_incident(row: dict[str, Any]) -> bool:
    return not incident_row(row) and row.get("lane_status") in TERMINAL_LANE_STATUSES


def implementation_row(row: dict[str, Any]) -> bool:
    """Identify implementation phases, with a narrow legacy phase fallback."""
    phase = row.get("phase")
    if phase == "implementation":
        return True
    # Older rows did not always carry phase.  Their lane kind is the only
    # retained implementation signal; do not infer it for proof/QA rows.
    return phase is None and row.get("lane_kind") in {
        "script_or_validator_implementation",
        "workflow_control_implementation",
    }


def explicit_main_acceptance(row: dict[str, Any]) -> bool:
    route = as_dict(row.get("route_attribution"))
    return route.get("main_acceptance_status") is not None or isinstance(route.get("main_accepted"), bool)


HISTORY_TERMINAL_UNAVAILABLE_ROUTE_STATES = frozenset({"unavailable_legacy", "unavailable_actual_route"})
HISTORY_ACTIONABLE_CONTENT_GAPS = frozenset({
    "not_completed",
    "missing_acceptance_commands",
    "missing_proof",
    "validator_not_clean",
    "later_rework",
    "later_regression",
})


def planning_gap_reasons_for_row(row: dict[str, Any]) -> list[str]:
    """Single-source planning-gap reasons for history partitioning.

    Mirrors the raw gap rules in summarize_rows without replacing them:
    the two loops inside summarize_rows remain the raw-total authority.
    Any content gap keeps the row actionable; only exact known terminal
    metadata shapes may partition elsewhere, fail-closed otherwise.
    """
    outcome = as_dict(row.get("coding_outcome"))
    reasons: list[str] = []
    if outcome.get("implementation_completed") is not True:
        reasons.append("not_completed")
    if outcome.get("acceptance_commands_declared") is not True:
        reasons.append("missing_acceptance_commands")
    if outcome.get("proof_attached") is not True:
        reasons.append("missing_proof")
    if validator_state(row) == "failed":
        reasons.append("validator_not_clean")
    observed_retry_count = strict_nonnegative_int(outcome.get("retry_count"))
    if observed_retry_count is None:
        reasons.append("retry_count_unavailable")
    elif observed_retry_count > 0:
        reasons.append("retry_required")
    if outcome.get("rework_required") is True:
        reasons.append("later_rework")
    if outcome.get("regression_observed") is True:
        reasons.append("later_regression")
    return reasons


def planning_history_partition(row: dict[str, Any], reasons: list[str] | None = None) -> str:
    """Partition a quality row into actionable / terminal / repaired history.

    - actionable_unresolved: any content gap, or anything malformed/unknown
      (fail closed: unknown or missing receipts are never success).
    - terminal_known_unavailable: the ONLY gap is retry_count_unavailable
      AND the row carries an exact known historical route shape
      (unavailable_legacy / unavailable_actual_route). No age filter.
    - repaired_accepted_retry: the ONLY gap is retry_required AND strict
      proof-present + Main-accepted terminal state holds (proof attached,
      explicit Main acceptance true, validator not failed, no later
      regression/rework). Raw retry_required totals are preserved; this
      only partitions the row out of actionable debt.
    """
    gap = list(reasons) if reasons is not None else planning_gap_reasons_for_row(row)
    if not gap:
        return "clean"
    if any(reason in HISTORY_ACTIONABLE_CONTENT_GAPS for reason in gap):
        return "actionable_unresolved"
    outcome = as_dict(row.get("coding_outcome"))
    route = as_dict(row.get("route_attribution"))
    if set(gap) == {"retry_required"}:
        repaired = (
            strict_nonnegative_int(outcome.get("retry_count")) not in (None, 0)
            and outcome.get("proof_attached") is True
            and route.get("main_accepted") is True
            and explicit_main_acceptance(row) is True
            and validator_state(row) != "failed"
            and outcome.get("regression_observed") is not True
            and outcome.get("rework_required") is not True
        )
        if repaired:
            return "repaired_accepted_retry"
        return "actionable_unresolved"
    if set(gap) == {"retry_count_unavailable"}:
        if route.get("route_conformance") in HISTORY_TERMINAL_UNAVAILABLE_ROUTE_STATES:
            return "terminal_known_unavailable"
        if history_pre_cutover_uninstrumented(row):
            return "terminal_known_unavailable"
        return "actionable_unresolved"
    # Multiple residual metadata gaps or anything unrecognized: fail closed.
    return "actionable_unresolved"


def history_pre_cutover_uninstrumented(row: dict[str, Any]) -> bool:
    """Schema-cutover terminal test for missing retry metadata.

    Uses the existing parse_utc contract and STRICT_TELEMETRY_CUTOVER_UTC:
    a schema cutover, not an arbitrary age filter. The row must be provably
    pre-cutover with no route/attempt instrumentation, while all other
    content and proof requirements are already clean (only-gap premise at
    the call site). Malformed or missing timestamps fail closed to
    actionable; post-cutover rows with missing route stay actionable.
    Terminal means the metadata predates the schema and can never be
    repaired; it never implies success or Main acceptance.
    """
    cutoff = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    observed = parse_utc(row.get("created_at_utc")) or parse_utc(row.get("completed_at_utc"))
    if cutoff is None or observed is None or observed >= cutoff:
        return False
    route = as_dict(row.get("route_attribution"))
    if route.get("route_conformance") is not None:
        return False
    if row.get("attempt_correlation") is not None:
        return False
    if row.get("parent_job_id") or row.get("attempt_id"):
        return False
    return True


def categorical_summary(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for row in rows:
        value = as_dict(row.get("route_attribution")).get(field)
        if isinstance(value, str) and value.strip():
            values[value.strip()] = values.get(value.strip(), 0) + 1
    return dict(sorted(values.items()))


def summarize_parent_jobs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate only explicitly safe parent identifiers; keep unavailable data null."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        parent_job_id = canonical_correlation_identifier(row.get("parent_job_id"))
        if parent_job_id:
            groups.setdefault(parent_job_id, []).append(row)
    result: dict[str, dict[str, Any]] = {}
    for parent_job_id, job_rows in sorted(groups.items()):
        non_incident = [row for row in job_rows if not incident_row(row)]
        credited_rows = [row for row in job_rows if telemetry_metrics_eligible(row)]
        implementation_rows = [
            row for row in credited_rows
            if terminal_non_incident(row) and implementation_row(row)
        ]
        qa_rows = [
            row for row in credited_rows
            if terminal_non_incident(row) and row.get("phase") == "qa"
        ]
        acceptance_rows = [
            row for row in credited_rows
            if not incident_row(row)
            and as_dict(row.get("token_usage")).get("integrity_status", "ok") == "ok"
            and explicit_main_acceptance(row)
        ]
        implementation_outcomes = [as_dict(row.get("coding_outcome")) for row in implementation_rows]
        qa_outcomes = [as_dict(row.get("coding_outcome")) for row in qa_rows]
        retries = [strict_nonnegative_int(as_dict(row.get("coding_outcome")).get("retry_count")) for row in job_rows]
        known_retries = [value for value in retries if value is not None]
        durations = [row.get("duration_minutes") for row in credited_rows]
        duration_numbers = [value for value in durations if isinstance(value, (int, float)) and not isinstance(value, bool)]
        phases = sorted({str(row.get("phase")) for row in job_rows if row.get("phase")})
        attempts = sorted({str(row.get("attempt_id")) for row in job_rows if row.get("attempt_id")})
        token_coverage = {
            field: metric_coverage(credited_rows, field)
            for field in ("gross_tokens", "cached_input_tokens", "uncached_input_tokens", "output_tokens")
        }
        handoff_coverage = {
            field: metric_coverage(job_rows, field)
            for field in ("handoff_file_count", "handoff_total_bytes", "handoff_context_tokens")
        }
        result[parent_job_id] = {
            "row_count": len(job_rows),
            "incident_row_count": len(job_rows) - len(non_incident),
            "telemetry": {
                "creditable_row_count": len(credited_rows),
                "uncreditable_row_count": len(job_rows) - len(credited_rows),
            },
            "phase_count": len(phases), "phases": phases,
            "attempt_count": len(attempts), "attempt_ids": attempts,
            "retry_tax": {"known_retry_row_count": len(known_retries), "total_retry_count": sum(known_retries) if known_retries else None, "rows_with_retry_count": sum(1 for value in known_retries if value > 0)},
            "first_pass_accepted_count": sum(1 for row in implementation_rows if first_pass_accepted(row)),
            "expected_route": {"backend": categorical_summary(job_rows, "expected_execution_backend"), "model": categorical_summary(job_rows, "expected_model_path"), "effort": categorical_summary(job_rows, "expected_thinking")},
            "actual_route": {"backend": categorical_summary(job_rows, "actual_execution_backend"), "model": categorical_summary(job_rows, "actual_model_path"), "effort": categorical_summary(job_rows, "actual_thinking")},
            "token_usage": {**{field: coverage["value"] for field, coverage in token_coverage.items()}, "coverage": token_coverage},
            "duration_minutes": round(sum(duration_numbers), 2) if duration_numbers else None,
            "completion": {"denominator": len(implementation_rows), "completed_count": sum(1 for outcome in implementation_outcomes if outcome.get("implementation_completed") is True)},
            "qa": {"denominator": len(qa_rows), "passed_count": sum(1 for outcome in qa_outcomes if outcome.get("validator_proxy_passed") is True), "failed_count": sum(1 for outcome in qa_outcomes if outcome.get("validator_proxy_passed") is False)},
            "outcome": {"denominator": len(non_incident), "proof_attached_count": sum(1 for row in non_incident if as_dict(row.get("coding_outcome")).get("proof_attached") is True), "acceptance_declared_count": sum(1 for row in non_incident if as_dict(row.get("coding_outcome")).get("acceptance_commands_declared") is True)},
            "main_acceptance": {"denominator": len(acceptance_rows), "accepted_count": sum(1 for row in acceptance_rows if as_dict(row.get("route_attribution")).get("main_accepted") is True)},
            "handoff": {"file_count": handoff_coverage["handoff_file_count"]["value"], "total_bytes": handoff_coverage["handoff_total_bytes"]["value"], "context_tokens": handoff_coverage["handoff_context_tokens"]["value"], "coverage": handoff_coverage},
        }
    return result


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = apply_ex_post_reviews(rows)
    clean = [row for row in reviewed if not row.get("_parse_error")]
    # Incidents remain ledger evidence and parent efficiency cost, but never
    # participate in global quality, yield, or promotion-facing measures.
    operational_rows = [row for row in clean if not incident_row(row)]
    quality_rows = [
        row for row in operational_rows
        if as_dict(row.get("token_usage")).get("integrity_status", "ok") == "ok"
        and telemetry_metrics_eligible(row)
    ]
    by_workflow: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_task: dict[str, dict[str, Any]] = {}
    planning_gap_reasons: dict[str, int] = {}
    for row in clean:
        workflow = str(row.get("workflow_id") or "UNKNOWN")
        kind = str(row.get("lane_kind") or "unknown")
        by_workflow[workflow] = by_workflow.get(workflow, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
    reviewable = [row for row in quality_rows if reviewable_code_paths(row)]
    graded = [
        row for row in reviewable
        if as_dict(row.get("coding_outcome")).get("rework_required") is not None
        and as_dict(row.get("coding_outcome")).get("regression_observed") is not None
    ]
    first_pass_clean = [
        row for row in graded
        if as_dict(row.get("coding_outcome")).get("implementation_completed") is True
        and as_dict(row.get("coding_outcome")).get("validator_proxy_passed") is True
        and strict_nonnegative_int(as_dict(row.get("coding_outcome")).get("retry_count")) == 0
        and as_dict(row.get("coding_outcome")).get("rework_required") is False
        and as_dict(row.get("coding_outcome")).get("regression_observed") is False
    ]
    first_pass_ids = {id(row) for row in first_pass_clean}
    for row in graded:
        outcome = as_dict(row.get("coding_outcome"))
        for bucket, key in ((by_model, str(row.get("model_path") or "UNKNOWN")), (by_task, str(row.get("task_reference") or as_dict(row.get("route_attribution")).get("task_shape") or "UNAVAILABLE"))):
            item = bucket.setdefault(key, {
                "graded_count": 0,
                "first_pass_clean_count": 0,
                "rework_required_count": 0,
                "regression_observed_count": 0,
            })
            item["graded_count"] += 1
            if id(row) in first_pass_ids:
                item["first_pass_clean_count"] += 1
            if outcome.get("rework_required") is True:
                item["rework_required_count"] += 1
            if outcome.get("regression_observed") is True:
                item["regression_observed_count"] += 1
    for bucket in (by_model, by_task):
        for item in bucket.values():
            item["first_pass_clean_rate"] = round(item["first_pass_clean_count"] / item["graded_count"], 4) if item["graded_count"] else None
    for row in quality_rows:
        outcome = as_dict(row.get("coding_outcome"))
        reasons: list[str] = []
        if outcome.get("implementation_completed") is not True:
            reasons.append("not_completed")
        if outcome.get("acceptance_commands_declared") is not True:
            reasons.append("missing_acceptance_commands")
        if outcome.get("proof_attached") is not True:
            reasons.append("missing_proof")
        state = validator_state(row)
        if state == "failed":
            reasons.append("validator_not_clean")
        elif state == "legacy_unknown":
            planning_gap_reasons["validator_unknown_legacy"] = planning_gap_reasons.get("validator_unknown_legacy", 0) + 1
        observed_retry_count = strict_nonnegative_int(outcome.get("retry_count"))
        if observed_retry_count is None:
            reasons.append("retry_count_unavailable")
        elif observed_retry_count > 0:
            reasons.append("retry_required")
        if outcome.get("rework_required") is True:
            reasons.append("later_rework")
        if outcome.get("regression_observed") is True:
            reasons.append("later_regression")
        if outcome.get("later_review_status") == "documented_later_followup":
            planning_gap_reasons["documented_later_followup"] = planning_gap_reasons.get("documented_later_followup", 0) + 1
        for reason in reasons:
            planning_gap_reasons[reason] = planning_gap_reasons.get(reason, 0) + 1
    planning_clean = []
    for row in quality_rows:
        outcome = as_dict(row.get("coding_outcome"))
        reasons = []
        if outcome.get("implementation_completed") is not True:
            reasons.append("not_completed")
        if outcome.get("acceptance_commands_declared") is not True:
            reasons.append("missing_acceptance_commands")
        if outcome.get("proof_attached") is not True:
            reasons.append("missing_proof")
        if validator_state(row) == "failed":
            reasons.append("validator_not_clean")
        observed_retry_count = strict_nonnegative_int(outcome.get("retry_count"))
        if observed_retry_count is None:
            reasons.append("retry_count_unavailable")
        elif observed_retry_count > 0:
            reasons.append("retry_required")
        if outcome.get("rework_required") is True:
            reasons.append("later_rework")
        if outcome.get("regression_observed") is True:
            reasons.append("later_regression")
        if not reasons:
            planning_clean.append(row)
    planning_gap_count = len(quality_rows) - len(planning_clean)
    # History partition: raw gap count above is retained verbatim for
    # wf74 queue/router/triage compatibility. The partitions below only
    # separate actionable current debt from terminal historical metadata
    # and already-accepted repaired retry history.
    partition_buckets: dict[str, list[dict[str, Any]]] = {
        "actionable_unresolved": [],
        "terminal_known_unavailable": [],
        "repaired_accepted_retry": [],
    }
    for row in quality_rows:
        gap = planning_gap_reasons_for_row(row)
        if not gap:
            continue
        partition_buckets[planning_history_partition(row, gap)].append(row)
    def _partition_reason_counts(bucket: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in bucket:
            for reason in planning_gap_reasons_for_row(row):
                counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items()))
    planning_partitions = {
        name: {"row_count": len(bucket), "reasons": _partition_reason_counts(bucket)}
        for name, bucket in partition_buckets.items()
    }
    partitioned_gap_row_count = sum(item["row_count"] for item in planning_partitions.values())
    planning_actionable_count = planning_partitions["actionable_unresolved"]["row_count"]
    planning_terminal_count = planning_partitions["terminal_known_unavailable"]["row_count"]
    planning_repaired_count = planning_partitions["repaired_accepted_retry"]["row_count"]
    planning_signal = {
        "schema": "veritas.planning_quality_signal.v1",
        "tracked_lane_count": len(quality_rows),
        "plan_contract_present_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("acceptance_commands_declared") is True),
        "plan_followthrough_clean_count": len(planning_clean),
        "plan_followthrough_gap_count": planning_gap_count,
        "plan_followthrough_clean_rate": round(len(planning_clean) / len(quality_rows), 4) if quality_rows else None,
        "gap_reasons": dict(sorted(planning_gap_reasons.items())),
        "hard_gap_count": planning_gap_count,
        "plan_followthrough_actionable_gap_count": planning_actionable_count,
        "plan_followthrough_terminal_unavailable_count": planning_terminal_count,
        "plan_followthrough_repaired_accepted_count": planning_repaired_count,
        "gap_partitions": planning_partitions,
        "partitioned_gap_row_count": partitioned_gap_row_count,
        "partition_reconciliation_ok": partitioned_gap_row_count == planning_gap_count,
        "actionable_status": "attention" if planning_actionable_count else "ok",
        "partition_notes": [
            "Raw plan_followthrough_gap_count / gap_reasons / hard_gap_count are retained verbatim for wf74 queue/router/triage compatibility.",
            "Partitions separate actionable current debt from terminal known-unavailable historical metadata and already-accepted repaired retry history.",
            "Strict proof-present + explicit Main-accepted terminal state is the only retry-resolution path; unknown/missing receipts stay actionable, never success.",
            "Terminal_known_unavailable never implies success or Main acceptance; validator-unknown and claim-gate limits are preserved verbatim.",
        ],
        "legacy_validator_unknown_count": planning_gap_reasons.get("validator_unknown_legacy", 0),
        "documented_later_followup_count": planning_gap_reasons.get("documented_later_followup", 0),
        "status": "attention" if planning_gap_count else "ok",
    }
    claim_gate = model_performance_claim_gate(len(graded), by_model)
    comparable_cohorts = summarize_comparable_cohorts(reviewed)
    parent_jobs = summarize_parent_jobs(reviewed)
    return {
        "ledger_row_count": len(clean),
        "parse_error_count": len(rows) - len(clean),
        "workflow_counts": dict(sorted(by_workflow.items())),
        "lane_kind_counts": dict(sorted(by_kind.items())),
        "run_attributed_count": sum(1 for row in clean if row.get("run_reference")),
        "session_attributed_count": sum(1 for row in clean if as_dict(row.get("attribution")).get("session_present") is True),
        "model_attributed_count": sum(1 for row in clean if as_dict(row.get("attribution")).get("model_present") is True),
        "telemetry_uncreditable_row_count": sum(
            1 for row in operational_rows if not telemetry_metrics_eligible(row)
        ),
        "quality_row_count": len(quality_rows),
        "incident_row_count": sum(1 for row in clean if incident_row(row)),
        "invalid_token_integrity_row_count": sum(
            1 for row in operational_rows
            if as_dict(row.get("token_usage")).get("integrity_status", "ok") != "ok"
        ),
        "route_conformant_count": sum(1 for row in quality_rows if as_dict(row.get("route_attribution")).get("route_conformance") == "conformant"),
        "route_mismatch_count": sum(1 for row in quality_rows if as_dict(row.get("route_attribution")).get("route_conformance") == "mismatch"),
        "route_unavailable_legacy_count": sum(1 for row in quality_rows if as_dict(row.get("route_attribution")).get("route_conformance") == "unavailable_legacy"),
        "main_accepted_count": sum(1 for row in quality_rows if as_dict(row.get("route_attribution")).get("main_accepted") is True),
        "proof_attached_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("proof_attached") is True),
        "proof_remediated_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("proof_remediated") is True),
        "acceptance_declared_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("acceptance_commands_declared") is True),
        "validator_proxy_passed_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("validator_proxy_passed") is True),
        "validator_failed_count": sum(1 for row in quality_rows if validator_state(row) == "failed"),
        "validator_unknown_legacy_count": sum(1 for row in quality_rows if validator_state(row) == "legacy_unknown"),
        "retry_attributed_count": sum(
            1 for row in quality_rows
            if strict_nonnegative_int(as_dict(row.get("coding_outcome")).get("retry_count")) is not None
        ),
        "retry_unavailable_count": sum(
            1 for row in quality_rows
            if strict_nonnegative_int(as_dict(row.get("coding_outcome")).get("retry_count")) is None
        ),
        "total_retry_count": sum(
            strict_nonnegative_int(as_dict(row.get("coding_outcome")).get("retry_count")) or 0
            for row in quality_rows
        ),
        "rework_required_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("rework_required") is True),
        "regression_observed_count": sum(1 for row in quality_rows if as_dict(row.get("coding_outcome")).get("regression_observed") is True),
        "reviewable_code_row_count": len(reviewable),
        "ex_post_graded_count": len(graded),
        "later_review_pending_count": sum(1 for row in reviewable if as_dict(row.get("coding_outcome")).get("later_review_status") == "pending_later_regression_review"),
        "later_retouch_detected_count": sum(1 for row in reviewable if as_dict(row.get("coding_outcome")).get("later_retouch_count")),
        "documented_later_followup_count": sum(1 for row in reviewable if as_dict(row.get("coding_outcome")).get("later_review_status") == "documented_later_followup"),
        "undocumented_later_retouch_count": sum(1 for row in reviewable if as_dict(row.get("coding_outcome")).get("later_review_status") == "undocumented_later_retouch"),
        "clean_after_review_count": sum(1 for row in reviewable if as_dict(row.get("coding_outcome")).get("later_review_status") == "clean_after_review_window"),
        "first_pass_clean_count": len(first_pass_clean),
        "first_pass_clean_rate": round(len(first_pass_clean) / len(graded), 4) if graded else None,
        "first_pass_clean_by_model": dict(sorted(by_model.items())),
        "first_pass_clean_by_task": dict(sorted(by_task.items())[:10]),
        "planning_quality_signal": planning_signal,
        "model_performance_claim_gate": claim_gate,
        "comparable_cohorts": comparable_cohorts,
        "parent_jobs": parent_jobs,
        "comparable_cohort_sample_gate": {
            "required_accepted_count": MIN_ACCEPTED_ROWS_FOR_COMPARABLE_COHORT,
            "eligible_cohort_count": sum(1 for item in comparable_cohorts.values() if item["sample_gate_met"]),
            "route_ranking_or_promotion_before_gate": False,
            "note": "No route ranking or promotion is available until a cohort has at least ten comparable Main-accepted jobs.",
        },
    }


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def validate_current(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if authority_true_paths(payload):
        errors.append("authority_drift_detected")
    register_validation = as_dict(as_dict(payload.get("source_statuses")).get("lane_register_validation"))
    if register_validation.get("errors"):
        warnings.append("source_lane_register_has_validation_errors")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_current(register_path: Path, changed_router_path: Path, ledger_path: Path, append_report: dict[str, Any] | None = None) -> dict[str, Any]:
    register = as_dict(load_json(register_path))
    changed_router = as_dict(load_json(changed_router_path))
    source_receipts = load_usage_source_receipts(register_path)
    records = [build_record(lane, changed_router, source_receipts, register_path=register_path) for lane in completed_lanes(register)]
    ledger_rows = apply_ex_post_reviews(load_jsonl(ledger_path))
    payload = {
        "schema": CURRENT_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only coding outcome scoreboard from completed implementation lanes.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "lane_register": rel(register_path),
            "changed_file_validator_router": rel(changed_router_path),
            "durable_ledger": rel(ledger_path),
            "usage_source_receipts": rel(register_path.with_suffix(".usage-receipts.json")),
        },
        "source_statuses": {
            "lane_register_status": register.get("status"),
            "lane_register_validation": register.get("validation"),
            "changed_file_validator_router_status": changed_router.get("status"),
            "usage_source_receipt_count": len(source_receipts),
        },
        "current_register_summary": register.get("summary"),
        "candidate_completed_lane_count": len(records),
        "last_append_report": append_report,
        "ledger_summary": summarize_rows(ledger_rows),
        "recent_records": ledger_rows[-10:],
        "next_safe_action": "Use this ledger to review coding rework/regression and planning follow-through over time; do not treat a clean validator as proof of long-term correctness.",
        "stop_lines": [
            "Review-only coding metrics.",
            "No config/runtime mutation, destructive cleanup, finance canon mutation, trading, account, or approval authority.",
        ],
    }
    payload["validation"] = validate_current(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=REGISTER)
    parser.add_argument("--changed-router", type=Path, default=CHANGED_ROUTER)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--current", type=Path, default=CURRENT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    register_path = abs_path(args.register)
    changed_router_path = abs_path(args.changed_router)
    ledger_path = abs_path(args.ledger)
    current_path = abs_path(args.current)

    register = as_dict(load_json(register_path))
    changed_router = as_dict(load_json(changed_router_path))
    source_receipts = load_usage_source_receipts(register_path)
    records = [build_record(lane, changed_router, source_receipts, register_path=register_path) for lane in completed_lanes(register)]
    append_report = append_new_records(records, ledger_path) if args.write else None
    current = build_current(register_path, changed_router_path, ledger_path, append_report)
    if args.write:
        atomic_write_json(current_path, current)
    print(
        "status={status} validation={validation} ledger_rows={rows} appended={appended} out={out}".format(
            status=current["status"],
            validation=current["validation"]["status"],
            rows=current["ledger_summary"]["ledger_row_count"],
            appended=(append_report or {}).get("appended_count"),
            out=rel(current_path) if args.write else None,
        )
    )
    if args.validate and current["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
