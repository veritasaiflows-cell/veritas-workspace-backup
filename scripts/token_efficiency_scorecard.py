#!/usr/bin/env python3
"""Build a metadata-only token efficiency scorecard for WF88.

This packet ranks cron/API optimization candidates from existing token ledger
metadata. It recommends changed-only, cadence-review, prompt-compression, and
failure-cost reviews, but it does not change cron schedules or model routing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
import token_budget_status as budget_status
import token_usage_ledger


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
TOKEN_USAGE = TMP / "token-usage-ledger-current.json"
TOKEN_BUDGET = TMP / "token-budget-status.json"
ATTRIBUTION_BRIDGE = TMP / "implementation-token-attribution-bridge.json"
CRON_CONTRACTS = ROOT / "state" / "cron-contracts"
OUT = TMP / "token-efficiency-scorecard.json"
MD_OUT = OUT.with_suffix(".md")
SCHEMA = "veritas.token_efficiency_scorecard.v1"

# Payload kinds that run a deterministic subprocess and cannot spawn a model or
# agent turn. Ledger spend for these jobs predates their conversion.
DETERMINISTIC_PAYLOAD_KINDS = {"command"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "cost_estimate_only": True,
    "api_call_reduction_recommendation_only": True,
    "external_export_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "platform_billing_api_call_allowed": False,
    "automatic_quota_action_allowed": False,
    "model_install_or_training_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def first_defined(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return None


def as_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def normalize_billing_semantics(raw: dict[str, Any]) -> dict[str, Any]:
    semantics = dict(raw)
    not_invoice = as_optional_bool(first_defined(
        semantics,
        "api_equivalent_is_not_invoice",
        "api_equivalent_cost_is_not_invoice",
        "api_equivalent_cost_usd_is_not_invoice",
    ))
    semantics["billing_mode"] = semantics.get("billing_mode") or "unavailable"
    semantics["api_equivalent_is_not_invoice"] = True if not_invoice is None else not_invoice
    semantics.setdefault("actual_billed_cost_is_inferred", False)
    semantics.setdefault("platform_billing_api_queried", False)
    return semantics


def normalize_oauth_capacity_control(raw: dict[str, Any]) -> dict[str, Any]:
    control = dict(raw)
    source_present = bool(control)
    state = str(control.get("state") or "").strip().lower()
    snapshot_status = str(control.get("snapshot_status") or "").strip().lower()
    control["status"] = control.get("status") or (
        "current" if snapshot_status == "fresh" and state not in {"", "unavailable", "stale"} else state or "unavailable"
    )
    control["tier"] = control.get("tier") or control.get("quota_tier") or state or "unavailable"
    automatic_action = as_optional_bool(control.get("automatic_action_allowed"))
    control["automatic_action_allowed"] = False if automatic_action is None else automatic_action
    control.setdefault("snapshot_available", control.get("capacity_known") is True or source_present)
    if control.get("reserve_percent") is None:
        control["reserve_percent"] = as_dict(as_dict(control.get("policy")).get("thresholds_percent")).get("reserve")
    if control.get("days_until_reset") is None:
        control["days_until_reset"] = control.get("days_to_reset")
    if control.get("daily_burn_guidance") is None:
        control["daily_burn_guidance"] = control.get("max_daily_percentage_point_burn_preserving_reserve")
    return control


def oauth_capacity_preflight_for_candidate(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> dict[str, Any]:
    """Return advisory OAuth capacity metadata for an existing scorecard candidate."""
    if "repeated_high_burn_job" not in as_list(candidate.get("reasons")):
        return {
            "required": False,
            "state": "not_applicable",
            "advisory_only": True,
            "automatic_action_allowed": False,
            "automatic_dispatch_allowed": False,
        }

    policy = as_dict(control.get("policy")) or None
    preflight = as_dict(token_usage_ledger.build_oauth_capacity_high_burn_preflight(
        control,
        policy=policy,
    ))
    state = str(preflight.get("status") or preflight.get("state") or "").strip().lower()
    if state not in {"advisory_current", "review_required", "refresh_required"}:
        state = "refresh_required"
    return {
        "required": True,
        "state": state,
        "advisory_only": True,
        "quota_tier": preflight.get("quota_tier"),
        "snapshot_status": preflight.get("snapshot_status"),
        "checked_at_utc": preflight.get("checked_at_utc"),
        "snapshot_age_hours": preflight.get("snapshot_age_hours"),
        "max_snapshot_age_hours": preflight.get("max_snapshot_age_hours"),
        "remaining_percent": preflight.get("remaining_percent"),
        "reserve_percent": preflight.get("reserve_percent"),
        "next_action": preflight.get("next_action"),
        "automatic_action_allowed": False,
        "automatic_dispatch_allowed": False,
    }


def actual_cost_is_owner_entered(summary: dict[str, Any], semantics: dict[str, Any]) -> bool:
    for container in (summary, semantics):
        for key in (
            "actual_billed_cost_owner_entered",
            "actual_billed_cost_is_owner_entered",
            "owner_entered_actual_billed_cost",
        ):
            if as_optional_bool(container.get(key)) is True:
                return True
        source = str(container.get("actual_billed_cost_source") or "").strip().lower()
        if source in {"owner_entered", "owner-provided", "owner_provided", "manual_owner_entry"}:
            return True
    return False


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def ratio(numerator: Any, denominator: Any) -> float | None:
    try:
        denom = float(denominator or 0)
        if denom <= 0:
            return None
        return round(float(numerator or 0) / denom, 4)
    except (TypeError, ValueError):
        return None


def per_run(value: Any, count: Any) -> float | None:
    try:
        count_value = float(count or 0)
        if count_value <= 0:
            return None
        return round(float(value or 0) / count_value, 2)
    except (TypeError, ValueError):
        return None


def fleet_efficiency_view(fleet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(fleet.get("summary"))
    windows = as_dict(fleet.get("usage_windows"))
    outcome_telemetry_verified = fleet.get("outcome_telemetry_status") == "verified"
    outcome_keys = (
        "parent_job_count", "parent_job_completed_count", "parent_job_completion_percent",
        "completed_lane_count", "main_accepted_count", "main_acceptance_percent",
        "outcome_tracking_start_utc", "outcome_eligible_completed_lane_count",
        "historical_or_untracked_completed_lane_count", "main_acceptance_pending_count",
        "qa_review_completed_count", "qa_pass_count", "qa_yield_percent",
        "rework_count", "rework_percent", "attribution_gap_count",
    )
    safe_windows = {
        name: {
            key: as_dict(windows.get(name)).get(key)
            for key in (
                "status", "coverage", "ready_agent_count", "configured_agent_count",
                "event_count", "total_tokens", "api_equivalent_cost_usd",
                "api_equivalent_is_not_invoice", "actual_billed_cost_usd", "date_labels",
            )
        }
        for name in ("rolling_5h_observed", "rolling_24h_gateway", "closed_7d_gateway")
    }
    agents: list[dict[str, Any]] = []
    for raw in as_list(fleet.get("agents")):
        if not isinstance(raw, dict):
            continue
        utilization = as_dict(raw.get("utilization"))
        outcomes = as_dict(raw.get("outcomes"))
        safe_outcomes = {
            key: (outcomes.get(key) if outcome_telemetry_verified else None)
            for key in (
                "lane_count", "completed_lane_count", "parent_job_count",
                "outcome_tracking_start_utc", "outcome_eligible_completed_lane_count",
                "historical_or_untracked_completed_lane_count",
                "parent_job_completed_count", "main_accepted_count",
                "main_acceptance_pending_count", "qa_review_completed_count",
                "qa_pass_count", "qa_yield_percent",
                "rework_count", "attribution_gap_count",
            )
        }
        gaps = int(safe_outcomes.get("attribution_gap_count") or 0)
        rework = int(safe_outcomes.get("rework_count") or 0)
        agents.append({
            "agent_id": raw.get("agent_id"),
            "agent_role": raw.get("agent_role"),
            "reporting_source": utilization.get("reporting_source"),
            "reporting_total_tokens": utilization.get("reporting_total_tokens"),
            "utilization_share_percent": utilization.get("utilization_share_percent"),
            "utilized": utilization.get("utilized"),
            "session_event_count": utilization.get("session_event_count"),
            "session_attribution_grade_event_count": utilization.get("session_attribution_grade_event_count"),
            "session_pricing_grade_event_count": utilization.get("session_pricing_grade_event_count"),
            "outcomes": safe_outcomes,
            "review_state": (
                "attribution_repair_required" if gaps
                else "rework_review" if rework
                else "outcome_telemetry_unavailable" if not outcome_telemetry_verified
                else "measured_no_outcome_yet" if not int(safe_outcomes.get("completed_lane_count") or 0)
                else "measured"
            ),
        })
    return {
        "schema": "veritas.isolated_agent_fleet_efficiency_view.v1",
        "present": fleet.get("present") is True,
        "status": (
            "outcome_telemetry_unavailable"
            if fleet.get("present") is True and not outcome_telemetry_verified
            else (fleet.get("status") or "unavailable")
        ),
        "generated_at_utc": fleet.get("generated_at_utc"),
        "outcome_telemetry_status": "verified" if outcome_telemetry_verified else "unavailable",
        "outcome_telemetry_reason": fleet.get("outcome_telemetry_reason") or (
            None if outcome_telemetry_verified else "receipt_revalidated_outcome_contract_required"
        ),
        "usage_windows": safe_windows,
        "summary": {
            key: summary.get(key)
            for key in (
                "configured_agent_count", "observed_agent_count", "utilized_agent_count",
                "session_event_count", "attribution_grade_event_count",
                "attribution_grade_coverage_percent", "pricing_grade_event_count",
                "pricing_grade_attribution_coverage_percent", *outcome_keys,
            )
        } if outcome_telemetry_verified else {
            key: (summary.get(key) if key not in outcome_keys else None)
            for key in (
                "configured_agent_count", "observed_agent_count", "utilized_agent_count",
                "session_event_count", "attribution_grade_event_count",
                "attribution_grade_coverage_percent", "pricing_grade_event_count",
                "pricing_grade_attribution_coverage_percent", *outcome_keys,
            )
        },
        "agents": agents,
        "billing_semantics": {
            "label": "API-equivalent benchmark",
            "api_equivalent_is_not_invoice": as_dict(fleet.get("billing_semantics")).get("api_equivalent_is_not_invoice") is True,
            "actual_billed_cost_usd": None,
        },
        "oauth_capacity_advisory": {
            key: as_dict(fleet.get("oauth_capacity_advisory")).get(key)
            for key in ("status", "tier", "remaining_percent", "reset_at_utc", "automatic_action_allowed")
        },
        "interpretation": {
            "token_usage_is_model_quality_proof": False,
            "main_acceptance_is_inferred": False,
            "outcome_telemetry_creditable": outcome_telemetry_verified,
            "automatic_action_allowed": False,
        },
    }


def source_status(path: Path) -> dict[str, Any]:
    payload = load(path)
    return {
        "path": rel(path),
        "present": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def enabled_contract_payload_kinds(contract_dir: Path) -> dict[str, str]:
    """Map enabled contract-backed cron names to their current live payload kind."""
    kinds: dict[str, str] = {}
    if not contract_dir.is_dir():
        return kinds
    for path in contract_dir.glob("*.json"):
        payload = load(path)
        name = payload.get("name")
        if isinstance(name, str) and name.strip() and payload.get("enabled") is not False:
            kinds[name.strip()] = str(as_dict(payload.get("payload")).get("kind") or "unknown")
    return kinds


def active_contract_names(contract_dir: Path) -> set[str]:
    """Enabled cron names whose live payload can still spend model tokens.

    A contract whose live payload is a deterministic command cannot spawn a model
    or agent turn, so its ledger spend is an already-captured conversion rather
    than a live efficiency candidate. Ranking those rows as candidates presents
    completed work as outstanding debt.
    """
    return {
        name
        for name, kind in enabled_contract_payload_kinds(contract_dir).items()
        if kind not in DETERMINISTIC_PAYLOAD_KINDS
    }


def classify_job(row: dict[str, Any], rank: int) -> dict[str, Any]:
    total = int(row.get("total_tokens") or 0)
    count = int(row.get("count") or 0)
    output = int(row.get("output_tokens") or 0)
    cached = int(row.get("cached_input_tokens") or 0)
    failures = int(row.get("failed_or_error_count") or 0)
    output_ratio = ratio(output, total)
    cache_ratio = ratio(cached, total)
    tokens_per_run = per_run(total, count)
    api_equivalent_cost = first_defined(row, "api_equivalent_cost_usd", "estimated_cost")
    api_equivalent_cost_rows = int(first_defined(row, "api_equivalent_cost_rows", "estimated_cost_rows") or 0)
    api_equivalent_estimate_status = row.get("api_equivalent_estimate_status") or (
        "unavailable" if not api_equivalent_cost_rows
        else "complete" if api_equivalent_cost_rows == count
        else "partial_unknown_input_semantics_or_missing_rate"
    )
    api_equivalent_cost_per_run = per_run(api_equivalent_cost, count) if api_equivalent_estimate_status == "complete" else None
    api_equivalent_cost_per_priced_run = per_run(api_equivalent_cost, api_equivalent_cost_rows)
    estimated_chatgpt_credits = row.get("estimated_chatgpt_credits")
    estimated_chatgpt_credit_rows = int(row.get("estimated_chatgpt_credit_rows") or 0)
    chatgpt_credit_estimate_status = row.get("chatgpt_credit_estimate_status") or (
        "unavailable" if not estimated_chatgpt_credit_rows
        else "complete" if estimated_chatgpt_credit_rows == count
        else "partial_separate_no_public_rate_or_missing_rate"
    )
    estimated_chatgpt_credits_per_run = per_run(estimated_chatgpt_credits, count) if chatgpt_credit_estimate_status == "complete" else None
    estimated_chatgpt_credits_per_priced_run = per_run(estimated_chatgpt_credits, estimated_chatgpt_credit_rows)
    reasons: list[str] = []
    candidate_types: list[str] = []
    if rank <= 5:
        reasons.append("top_5_token_consumer")
        candidate_types.append("changed_only_prefilter_review")
    if count >= 10 and total >= 500_000:
        reasons.append("repeated_high_burn_job")
        candidate_types.append("cadence_or_skip_when_unchanged_review")
    if output_ratio is not None and output_ratio < 0.01 and total >= 250_000:
        reasons.append("very_low_output_ratio")
        candidate_types.append("prompt_compression_or_summary_cache_review")
    if failures > 0:
        reasons.append("token_burn_with_failures")
        candidate_types.append("failure_cost_repair_review")
    if cache_ratio is not None and cache_ratio > 0.85:
        reasons.append("high_cache_reuse")
        candidate_types.append("cache_preservation_candidate")
    if not reasons:
        reasons.append("monitor_only")
        candidate_types.append("monitor_only")
    predispatch = predispatch_contract(sorted(set(candidate_types)))
    return {
        "rank": rank,
        "cron_job_name": row.get("cron_job_name"),
        "run_count": count,
        "total_tokens": total,
        "tokens_per_run": tokens_per_run,
        "api_equivalent_cost_usd": api_equivalent_cost,
        "api_equivalent_cost_rows": api_equivalent_cost_rows,
        "api_equivalent_estimate_status": api_equivalent_estimate_status,
        "api_equivalent_cost_per_run_usd": api_equivalent_cost_per_run,
        "api_equivalent_cost_per_priced_run_usd": api_equivalent_cost_per_priced_run,
        "estimated_cost": api_equivalent_cost,
        "estimated_cost_per_run": api_equivalent_cost_per_run,
        "estimated_cost_deprecated_alias_for": "api_equivalent_cost_usd",
        "estimated_cost_per_run_deprecated_alias_for": "api_equivalent_cost_per_run_usd",
        "estimated_chatgpt_credits": estimated_chatgpt_credits,
        "estimated_chatgpt_credit_rows": estimated_chatgpt_credit_rows,
        "chatgpt_credit_estimate_status": chatgpt_credit_estimate_status,
        "estimated_chatgpt_credits_per_run": estimated_chatgpt_credits_per_run,
        "estimated_chatgpt_credits_per_priced_run": estimated_chatgpt_credits_per_priced_run,
        "input_tokens": row.get("input_tokens"),
        "cached_input_tokens": cached,
        "output_tokens": output,
        "output_ratio": output_ratio,
        "cache_ratio": cache_ratio,
        "failed_or_error_count": failures,
        "candidate_types": sorted(set(candidate_types)),
        "reasons": reasons,
        "predispatch_contract": predispatch,
        "next_review": next_review(candidate_types),
    }


def predispatch_contract(candidate_types: list[str]) -> dict[str, Any]:
    skip_candidate = any(
        candidate in candidate_types
        for candidate in ("changed_only_prefilter_review", "cadence_or_skip_when_unchanged_review")
    )
    if not skip_candidate:
        return {
            "recommended": False,
            "mode": "monitor_or_cache_preservation",
            "acceptance": "No pre-dispatch skip needed from current metadata.",
        }
    return {
        "recommended": True,
        "mode": "changed_input_hash_before_model_spawn",
        "acceptance": "Unchanged source hash writes skipped_unchanged proof and does not spawn an agent/model turn; changed source hash runs the existing job path.",
        "required_proof": [
            "input_signature hash",
            "previous successful hash",
            "skip artifact path",
            "existing expected artifacts remain fresh or are explicitly marked reused",
        ],
        "stop_line": "No cron schedule or model-route mutation from this scorecard; wire through a separate validated cron patch.",
    }


def next_review(candidate_types: list[str]) -> str:
    if "failure_cost_repair_review" in candidate_types:
        return "Repair failing run path first; failed token burn is the highest-signal waste."
    if "changed_only_prefilter_review" in candidate_types:
        return "Add or verify a deterministic changed-input prefilter before spawning a model call."
    if "cadence_or_skip_when_unchanged_review" in candidate_types:
        return "Review whether cadence can be kept while model calls only run after source hash or freshness changes."
    if "prompt_compression_or_summary_cache_review" in candidate_types:
        return "Replace broad context with a compact source summary and regression-test output equivalence."
    if "cache_preservation_candidate" in candidate_types:
        return "Preserve stable prompt prefix and avoid churn that breaks cache reuse."
    return "Monitor only."


def select_next_candidate(
    api_call_reduction: list[dict[str, Any]],
    prompt_compression: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for row in api_call_reduction:
        if as_dict(row.get("predispatch_contract")).get("recommended") is True:
            return {
                "selection_reason": "top_changed_only_or_cadence_prefilter_candidate",
                "candidate_type": "changed_only_prefilter",
                "cron_job_name": row.get("cron_job_name"),
                "rank": row.get("rank"),
                "tokens_per_run": row.get("tokens_per_run"),
                "total_tokens": row.get("total_tokens"),
                "run_count": row.get("run_count"),
                "next_review": row.get("next_review"),
                "acceptance": as_dict(row.get("predispatch_contract")).get("acceptance"),
                "stop_line": as_dict(row.get("predispatch_contract")).get("stop_line"),
            }
    if prompt_compression:
        row = prompt_compression[0]
        return {
            "selection_reason": "top_prompt_compression_candidate",
            "candidate_type": "prompt_compression",
            "cron_job_name": row.get("cron_job_name"),
            "rank": row.get("rank"),
            "tokens_per_run": row.get("tokens_per_run"),
            "total_tokens": row.get("total_tokens"),
            "run_count": row.get("run_count"),
            "next_review": row.get("next_review"),
            "acceptance": "Compressed prompt preserves validator status, routed action count, and authority-boundary markers.",
            "stop_line": "No prompt shrink is accepted without regression proof.",
        }
    return None


def build_payload(
    token_usage_path: Path = TOKEN_USAGE,
    token_budget_path: Path = TOKEN_BUDGET,
    cron_contract_dir: Path = CRON_CONTRACTS,
    attribution_bridge_path: Path | None = None,
) -> dict[str, Any]:
    token_usage = load(token_usage_path)
    token_budget = load(token_budget_path)
    summary = as_dict(token_usage.get("summary"))
    budget_summary = as_dict(token_budget.get("summary"))
    # Resolve lazily so patched-module TMP (tests) stays hermetic.
    attribution_bridge_path = attribution_bridge_path or (TMP / "implementation-token-attribution-bridge.json")
    attribution_bridge_summary = as_dict(load(attribution_bridge_path).get("summary")) if attribution_bridge_path.exists() else {}
    raw_attribution_action_required = attribution_bridge_summary.get("action_required_supported_runtime_gap_count")
    attribution_action_required = (
        int(raw_attribution_action_required)
        if isinstance(raw_attribution_action_required, (int, float)) and not isinstance(raw_attribution_action_required, bool)
        else None
    )
    attribution_gap_resolution_status = str(attribution_bridge_summary.get("gap_resolution_status") or "") or None
    billing_source = as_dict(token_usage.get("billing_semantics")) or as_dict(token_budget.get("billing_semantics"))
    capacity_source = as_dict(token_usage.get("oauth_capacity_control")) or as_dict(token_budget.get("oauth_capacity_control"))
    usage_pace = as_dict(token_usage.get("usage_pace")) or as_dict(token_budget.get("usage_pace"))
    billing_semantics = normalize_billing_semantics(billing_source)
    oauth_capacity_control = normalize_oauth_capacity_control(capacity_source)
    fleet_usage = as_dict(token_budget.get("fleet_usage"))
    if as_dict(token_usage.get("fleet_reporting")):
        # The budget packet is a derived display surface.  Rebuild outcome
        # eligibility from the current token-usage ledger whenever it exists;
        # never let a nested budget summary self-certify accepted/QA metrics.
        fleet_usage = budget_status.normalize_fleet_reporting(token_usage, oauth_capacity_control)
    elif fleet_usage:
        # A fleet block without the source ledger can remain an audit/display
        # hint, but its outcome fields are not independently revalidated.
        fleet_usage = {
            **fleet_usage,
            "outcome_telemetry_status": "unavailable",
            "outcome_telemetry_reason": "token_usage_ledger_source_required",
        }
    fleet_efficiency = fleet_efficiency_view(fleet_usage)
    api_equivalent_cost = first_defined(summary, "api_equivalent_cost_usd", "estimated_cost_total")
    if api_equivalent_cost is None:
        api_equivalent_cost = first_defined(budget_summary, "api_equivalent_cost_usd", "estimated_cost_total")
    estimated_chatgpt_credits = summary.get("estimated_chatgpt_credits")
    if estimated_chatgpt_credits is None:
        estimated_chatgpt_credits = budget_summary.get("estimated_chatgpt_credits")
    actual_billed_cost = summary.get("actual_billed_cost_usd")
    if actual_billed_cost is None:
        actual_billed_cost = budget_summary.get("actual_billed_cost_usd")

    def summary_value(*keys: str) -> Any:
        value = first_defined(summary, *keys)
        return value if value is not None else first_defined(budget_summary, *keys)

    ledger_rows = [as_dict(row) for row in as_list(token_usage.get("top_cron_jobs_by_tokens"))]
    enabled_payload_kinds = enabled_contract_payload_kinds(cron_contract_dir)
    active_names = active_contract_names(cron_contract_dir)
    active_rows = [row for row in ledger_rows if row.get("cron_job_name") in active_names]
    jobs = [classify_job(row, index + 1) for index, row in enumerate(active_rows)]
    historical_jobs = []
    for index, row in enumerate(
        [row for row in ledger_rows if row.get("cron_job_name") not in active_names]
    ):
        name = row.get("cron_job_name")
        converted = name in enabled_payload_kinds
        historical_jobs.append({
            **classify_job(row, index + 1),
            "activity_status": (
                "converted_to_deterministic_payload" if converted else "historical_or_unverified"
            ),
            "live_payload_kind": enabled_payload_kinds.get(name),
            "spend_classification": (
                "already_captured_conversion" if converted else "retired_or_unverified_job"
            ),
        })
    converted_jobs = [
        row for row in historical_jobs
        if row.get("activity_status") == "converted_to_deterministic_payload"
    ]
    for row in [*jobs, *historical_jobs]:
        row["oauth_capacity_preflight"] = oauth_capacity_preflight_for_candidate(
            row,
            oauth_capacity_control,
        )
    for row in jobs:
        row["activity_status"] = "active_contract_backed"
    actionable = [
        row for row in jobs
        if "monitor_only" not in as_list(row.get("candidate_types"))
    ]
    api_call_reduction = [
        row for row in actionable
        if any(candidate in as_list(row.get("candidate_types")) for candidate in ("changed_only_prefilter_review", "cadence_or_skip_when_unchanged_review"))
    ]
    prompt_compression = [
        row for row in actionable
        if "prompt_compression_or_summary_cache_review" in as_list(row.get("candidate_types"))
    ]
    failure_cost = [
        row for row in actionable
        if "failure_cost_repair_review" in as_list(row.get("candidate_types"))
    ]
    selected_next_candidate = select_next_candidate(api_call_reduction, prompt_compression)
    # Live attribution debt is the bridge's action-required denominator; the raw
    # ledger gap count includes classified historical/terminal-unavailable rows
    # that are audit context, not open work. Without a bridge artifact, fall
    # back to the raw count (previous behavior, fail-closed).
    bridge_needed = (
        attribution_action_required > 0
        if attribution_action_required is not None
        else int(summary.get("implementation_token_gap_count") or 0) > 0
    )
    packet_summary = {
        "token_usage_status": token_usage.get("status"),
        "token_budget_status": token_budget.get("status"),
        "token_event_count": int(summary.get("token_event_count") or 0),
        "total_tokens": int(summary.get("total_tokens") or 0),
        "api_equivalent_cost_usd": api_equivalent_cost,
        "api_equivalent_estimate_status": summary_value("api_equivalent_estimate_status"),
        "api_equivalent_cost_rows": summary_value("api_equivalent_cost_rows"),
        "api_equivalent_cost_event_coverage_percent": summary_value("api_equivalent_cost_event_coverage_percent"),
        "api_equivalent_priced_tokens": summary_value("api_equivalent_priced_tokens"),
        "estimated_cost_total": api_equivalent_cost,
        "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
        "estimated_chatgpt_credits": estimated_chatgpt_credits,
        "chatgpt_credit_estimate_status": summary_value("chatgpt_credit_estimate_status"),
        "estimated_chatgpt_credit_rows": summary_value("estimated_chatgpt_credit_rows"),
        "chatgpt_credit_event_coverage_percent": summary_value("chatgpt_credit_event_coverage_percent"),
        "chatgpt_credit_priced_tokens": summary_value("chatgpt_credit_priced_tokens"),
        "unknown_or_invalid_input_token_semantics_event_count": summary_value(
            "unknown_or_invalid_input_token_semantics_event_count"
        ),
        "rolling_5h_total_tokens": as_dict(usage_pace.get("rolling_5h")).get("total_tokens"),
        "rolling_7d_observed_total_tokens": as_dict(usage_pace.get("rolling_7d_observed")).get("total_tokens"),
        "usage_timestamp_coverage_percent": usage_pace.get("usage_timestamp_coverage_percent"),
        "actual_billed_cost_usd": actual_billed_cost,
        "actual_billed_cost_source": first_defined(summary, "actual_billed_cost_source")
        or first_defined(budget_summary, "actual_billed_cost_source")
        or billing_semantics.get("actual_billed_cost_source"),
        "oauth_quota_status": oauth_capacity_control.get("status"),
        "oauth_quota_tier": oauth_capacity_control.get("tier"),
        "oauth_remaining_percent": first_defined(
            oauth_capacity_control, "remaining_percent", "remaining_capacity_percent"
        ),
        "oauth_reset_at_utc": first_defined(oauth_capacity_control, "reset_at_utc", "reset_utc"),
        "oauth_days_until_reset": first_defined(oauth_capacity_control, "days_until_reset", "days_to_reset", "reset_days"),
        "oauth_reserve_percent": first_defined(oauth_capacity_control, "reserve_percent", "reserve_target_percent"),
        "oauth_daily_burn_guidance": oauth_capacity_control.get("daily_burn_guidance"),
        "cron_token_event_count": int(summary.get("cron_token_event_count") or 0),
        "implementation_token_event_count": int(summary.get("implementation_token_event_count") or 0),
        "implementation_token_gap_count": int(summary.get("implementation_token_gap_count") or 0),
        "attribution_gap_action_required_count": attribution_action_required,
        "attribution_gap_resolution_status": attribution_gap_resolution_status,
        "fleet_reporting_status": fleet_efficiency.get("status"),
        "fleet_outcome_telemetry_status": fleet_efficiency.get("outcome_telemetry_status"),
        "fleet_configured_agent_count": as_dict(fleet_efficiency.get("summary")).get("configured_agent_count"),
        "fleet_utilized_agent_count": as_dict(fleet_efficiency.get("summary")).get("utilized_agent_count"),
        "fleet_pricing_grade_attribution_coverage_percent": as_dict(fleet_efficiency.get("summary")).get("pricing_grade_attribution_coverage_percent"),
        "fleet_parent_job_completed_count": as_dict(fleet_efficiency.get("summary")).get("parent_job_completed_count"),
        "fleet_outcome_eligible_completed_lane_count": as_dict(fleet_efficiency.get("summary")).get("outcome_eligible_completed_lane_count"),
        "fleet_historical_or_untracked_completed_lane_count": as_dict(fleet_efficiency.get("summary")).get("historical_or_untracked_completed_lane_count"),
        "fleet_main_accepted_count": as_dict(fleet_efficiency.get("summary")).get("main_accepted_count"),
        "fleet_qa_review_completed_count": as_dict(fleet_efficiency.get("summary")).get("qa_review_completed_count"),
        "fleet_qa_pass_count": as_dict(fleet_efficiency.get("summary")).get("qa_pass_count"),
        "fleet_qa_yield_percent": as_dict(fleet_efficiency.get("summary")).get("qa_yield_percent"),
        "fleet_rework_count": as_dict(fleet_efficiency.get("summary")).get("rework_count"),
        "fleet_attribution_gap_count": as_dict(fleet_efficiency.get("summary")).get("attribution_gap_count"),
        "active_contract_name_count": len(active_names),
        "active_ledger_job_count": len(jobs),
        "historical_or_unverified_ledger_job_count": len(historical_jobs),
        "converted_to_deterministic_payload_job_count": len(converted_jobs),
        "converted_to_deterministic_payload_tokens": sum(
            int(row.get("total_tokens") or 0) for row in converted_jobs
        ),
        "model_capable_enabled_contract_count": len(active_names),
        "deterministic_enabled_contract_count": sum(
            1 for kind in enabled_payload_kinds.values() if kind in DETERMINISTIC_PAYLOAD_KINDS
        ),
        "cron_candidate_count": len(actionable),
        "api_call_reduction_candidate_count": len(api_call_reduction),
        "prompt_compression_candidate_count": len(prompt_compression),
        "failure_cost_candidate_count": len(failure_cost),
        "top_candidate": actionable[0].get("cron_job_name") if actionable else None,
        "selected_next_candidate": as_dict(selected_next_candidate).get("cron_job_name"),
        "selected_next_candidate_type": as_dict(selected_next_candidate).get("candidate_type"),
        "bridge_needed": bridge_needed,
        "predispatch_skip_candidate_count": sum(
            1 for row in actionable if as_dict(row.get("predispatch_contract")).get("recommended") is True
        ),
        "next_safe_action": "Review top candidates for deterministic prefilters or prompt compression; do not change cadence/model routing without a separate validated patch.",
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning" if bridge_needed or failure_cost else "ok",
        "purpose": "Metadata-only scorecard for choosing cron/API token optimization work without raw content capture.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "billing_semantics": billing_semantics,
        "oauth_capacity_control": oauth_capacity_control,
        "fleet_efficiency": fleet_efficiency,
        "usage_pace": usage_pace,
        "compatibility": {
            "schema_version_preserved": SCHEMA,
            "deprecated_aliases": {
                "summary.estimated_cost_total": "summary.api_equivalent_cost_usd",
                "candidate.estimated_cost": "candidate.api_equivalent_cost_usd",
                "candidate.estimated_cost_per_run": "candidate.api_equivalent_cost_per_run_usd",
            },
        },
        "source_artifacts": {
            "token_usage_ledger": rel(token_usage_path),
            "token_budget_status": rel(token_budget_path),
            "cron_contract_directory": rel(cron_contract_dir),
        },
        "source_status": [
            source_status(token_usage_path),
            source_status(token_budget_path),
        ],
        "summary": packet_summary,
        "top_cron_efficiency_candidates": actionable[:15],
        "historical_or_unverified_cron_spend": historical_jobs[:15],
        "selected_next_candidate": selected_next_candidate,
        "cron_predispatch_recommendations": [
            {
                "rank": row.get("rank"),
                "cron_job_name": row.get("cron_job_name"),
                "tokens_per_run": row.get("tokens_per_run"),
                "cache_ratio": row.get("cache_ratio"),
                "output_ratio": row.get("output_ratio"),
                "predispatch_contract": row.get("predispatch_contract"),
            }
            for row in actionable
            if as_dict(row.get("predispatch_contract")).get("recommended") is True
        ][:15],
        "api_call_reduction_candidates": api_call_reduction[:15],
        "prompt_compression_candidates": prompt_compression[:15],
        "failure_cost_candidates": failure_cost[:15],
        "action_items": action_items(packet_summary, oauth_capacity_control, fleet_efficiency),
        "blocked_actions": [
            "no cron schedule mutation from this scorecard",
            "no Platform billing API call or inferred invoice",
            "no automatic quota throttling or model-route mutation",
            "no model install, training, or self-modifying-weight claim",
            "no raw prompt/response/tool payload capture",
            "no finance/capital/paper/live/brokerage/account authority",
        ],
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] == "blocked":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning" and payload["status"] == "ok":
        payload["status"] = "warning"
    return payload


def quota_action_item(control: dict[str, Any]) -> dict[str, Any]:
    quota_status = str(control.get("status") or "unavailable").strip().lower()
    tier = str(control.get("tier") or "unavailable").strip().lower()
    unavailable = quota_status in {"", "missing", "stale", "unknown", "unavailable"} or tier in {
        "", "missing", "stale", "unknown", "unavailable"
    }
    if unavailable:
        state = "refresh_required"
        next_action = "Refresh the OAuth quota snapshot; do not throttle automatically."
    elif tier == "normal":
        state = "advisory"
        next_action = "Preserve the OAuth reserve and current routing policy."
    elif tier == "reduce_routine":
        state = "advisory"
        next_action = "Recommend Terra/Luna for routine work and Sol only for high-value integration."
    elif tier == "pause_noncritical":
        state = "review_required"
        next_action = "Recommend review or pause of noncritical model-driven work, with no schedule change."
    elif tier == "urgent_only":
        state = "review_required"
        next_action = "Recommend urgent or high-value model-driven work only."
    else:
        state = "refresh_required"
        next_action = "Refresh the OAuth quota snapshot; do not throttle automatically."
    return {
        "id": "oauth-quota-capacity-guidance",
        "state": state,
        "quota_status": quota_status or "unavailable",
        "quota_tier": tier or "unavailable",
        "automatic_action_allowed": False,
        "next_action": next_action,
        "acceptance": "Quota advice remains review-only and preserves the configured reserve.",
        "stop_line": "Advisory only; no automatic throttling, schedule, runtime, config, auth, or model-route mutation.",
    }


def action_items(
    summary: dict[str, Any],
    capacity_control: dict[str, Any] | None = None,
    fleet_efficiency: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = [
        {
            "id": "review-top-token-cron-prefilters",
            "state": "ready_for_review" if int(summary.get("api_call_reduction_candidate_count") or 0) else "monitor",
            "next_action": "For each top candidate, add a deterministic changed-input/source-hash gate before any model call in a separate scoped patch.",
            "acceptance": "Equivalent output on changed inputs and skipped model call on unchanged inputs.",
            "stop_line": "Separate patch required before schedule/model routing changes.",
        },
        {
            "id": "run-prompt-compression-regression-harness",
            "state": "ready_for_review" if int(summary.get("prompt_compression_candidate_count") or 0) else "monitor",
            "next_action": "Build fixture-based before/after checks for compressed prompts before adopting shorter prompts.",
            "acceptance": "Compressed prompt preserves validator status, routed action count, and authority-boundary markers.",
            "stop_line": "No prompt shrink is accepted without regression proof.",
        },
        quota_action_item(as_dict(capacity_control)),
    ]
    attribution_action_required_count = summary.get("attribution_gap_action_required_count")
    gap_live_debt = (
        attribution_action_required_count > 0
        if isinstance(attribution_action_required_count, (int, float)) and not isinstance(attribution_action_required_count, bool)
        else int(summary.get("implementation_token_gap_count") or 0)
    )
    if gap_live_debt:
        rows.append({
            "id": "close-implementation-token-attribution-gap",
            "state": "repair_required",
            "next_action": "Use concurrent_lane_manager closeout fields plus implementation-token-attribution-bridge to stamp provider run ids and token totals into implementation lane metadata.",
            "acceptance": "new implementation lanes with exposed usage produce implementation token events and do not create new missing_usage gaps; privacy scan stays ok.",
            "stop_line": "Metadata only; no raw prompt, response, or tool payload capture.",
        })
    fleet = as_dict(fleet_efficiency)
    fleet_summary = as_dict(fleet.get("summary"))
    if fleet.get("present") is not True:
        rows.append({
            "id": "refresh-isolated-agent-fleet-reporting",
            "state": "refresh_required",
            "next_action": "Run the ordered metadata-only fleet usage producer before interpreting utilization or outcomes.",
            "acceptance": "The canonical fleet_reporting block has valid 5h/24h/closed-7d source labels and no raw content.",
            "stop_line": "Do not treat unavailable fleet metrics as zero and do not parse transcripts.",
        })
    elif fleet.get("outcome_telemetry_status") != "verified":
        rows.append({
            "id": "repair-isolated-agent-outcome-telemetry",
            "state": "repair_required",
            "next_action": "Regenerate fleet reporting from receipt-revalidated lane outcomes; do not substitute raw completed-lane totals.",
            "acceptance": "Fleet outcome telemetry reports verified and exposes explicit eligible, QA-review, and attribution-gap denominators.",
            "stop_line": "Unverified fleet events remain audit-only and cannot support efficiency, reliability, latency, cost, or savings claims.",
        })
    if int(fleet_summary.get("attribution_gap_count") or 0):
        rows.append({
            "id": "repair-isolated-agent-attribution-gaps",
            "state": "repair_required",
            "next_action": "Repair parent/lane/session linkage for the named gaps before calculating complete fleet economics.",
            "acceptance": "New parent jobs close with pricing-grade or explicitly unavailable attribution and no unclassified gap.",
            "stop_line": "Metadata only; no raw prompt, response, transcript, or tool payload capture.",
        })
    if int(fleet_summary.get("rework_count") or 0):
        rows.append({
            "id": "review-isolated-agent-rework",
            "state": "review_required",
            "next_action": "Review linked rework jobs for routing, packet, validator, or acceptance friction; do not infer model quality from tokens.",
            "acceptance": "Each recommendation cites linked outcome metadata and distinguishes routing friction from model quality.",
            "stop_line": "No model ranking, route mutation, or automatic agent promotion from this scorecard.",
        })
    return rows


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    summary = as_dict(payload.get("summary"))
    semantics = as_dict(payload.get("billing_semantics"))
    capacity = as_dict(payload.get("oauth_capacity_control"))
    fleet = as_dict(payload.get("fleet_efficiency"))
    billing_mode = str(semantics.get("billing_mode") or "").strip().lower()
    if billing_mode == "oauth_subscription":
        if semantics.get("api_equivalent_is_not_invoice") is not True:
            errors.append("oauth_api_equivalent_presented_as_actual_bill")
        unsafe_bill_markers = (
            semantics.get("api_equivalent_is_actual_billed_cost"),
            semantics.get("api_equivalent_is_invoice"),
            semantics.get("api_equivalent_is_bill"),
        )
        if any(as_optional_bool(value) is True for value in unsafe_bill_markers):
            errors.append("oauth_api_equivalent_presented_as_actual_bill")
        if summary.get("actual_billed_cost_usd") is not None and not actual_cost_is_owner_entered(summary, semantics):
            errors.append("oauth_actual_billed_cost_lacks_owner_entered_provenance")
    if capacity.get("automatic_action_allowed") is not False:
        errors.append("oauth_capacity_automatic_action_enabled")
    if fleet.get("present") is True:
        fleet_billing = as_dict(fleet.get("billing_semantics"))
        fleet_capacity = as_dict(fleet.get("oauth_capacity_advisory"))
        interpretation = as_dict(fleet.get("interpretation"))
        if fleet_billing.get("api_equivalent_is_not_invoice") is not True:
            errors.append("fleet_api_equivalent_presented_as_invoice")
        if fleet_billing.get("actual_billed_cost_usd") is not None:
            errors.append("fleet_actual_billed_cost_must_remain_unallocated")
        if fleet_capacity.get("automatic_action_allowed") is not False:
            errors.append("fleet_oauth_capacity_automatic_action_enabled")
        for key in ("token_usage_is_model_quality_proof", "main_acceptance_is_inferred", "automatic_action_allowed"):
            if interpretation.get(key) is not False:
                errors.append(f"fleet_interpretation_guard_invalid:{key}")
        if interpretation.get("outcome_telemetry_creditable") is not (fleet.get("outcome_telemetry_status") == "verified"):
            errors.append("fleet_outcome_telemetry_interpretation_mismatch")
        fleet_summary = as_dict(fleet.get("summary"))
        if int(fleet_summary.get("attribution_gap_count") or 0):
            warnings.append(f"fleet_attribution_gap_count:{fleet_summary.get('attribution_gap_count')}")
        if int(fleet_summary.get("rework_count") or 0):
            warnings.append(f"fleet_rework_count:{fleet_summary.get('rework_count')}")
        if fleet.get("outcome_telemetry_status") != "verified":
            warnings.append("fleet_outcome_telemetry_unavailable")
    elif int(summary.get("fleet_configured_agent_count") or 0):
        warnings.append("isolated_agent_fleet_reporting_unavailable")
    quota_status = str(capacity.get("status") or "unavailable").strip().lower()
    quota_tier = str(capacity.get("tier") or "unavailable").strip().lower()
    if quota_status in {"", "missing", "stale", "unknown", "unavailable"} or quota_tier in {
        "", "missing", "stale", "unknown", "unavailable"
    }:
        warnings.append("oauth_capacity_snapshot_missing_or_stale")
    quota_actions = [
        as_dict(row) for row in as_list(payload.get("action_items"))
        if as_dict(row).get("id") == "oauth-quota-capacity-guidance"
    ]
    if not quota_actions:
        errors.append("oauth_quota_action_item_missing")
    elif quota_actions[0].get("automatic_action_allowed") is not False:
        errors.append("oauth_quota_action_enables_automatic_action")
    for candidate in [
        *as_list(payload.get("top_cron_efficiency_candidates")),
        *as_list(payload.get("historical_or_unverified_cron_spend")),
    ]:
        candidate_data = as_dict(candidate)
        preflight = as_dict(candidate_data.get("oauth_capacity_preflight"))
        repeated_high_burn = "repeated_high_burn_job" in as_list(candidate_data.get("reasons"))
        if repeated_high_burn:
            if preflight.get("required") is not True:
                errors.append("repeated_high_burn_oauth_capacity_preflight_missing")
            if preflight.get("state") not in {
                "advisory_current",
                "review_required",
                "refresh_required",
            }:
                errors.append("repeated_high_burn_oauth_capacity_preflight_state_invalid")
        elif preflight.get("state") != "not_applicable":
            errors.append("non_high_burn_oauth_capacity_preflight_invalid")
        if preflight.get("automatic_action_allowed") is not False:
            errors.append("oauth_capacity_preflight_automatic_action_enabled")
        if preflight.get("automatic_dispatch_allowed") is not False:
            errors.append("oauth_capacity_preflight_automatic_dispatch_enabled")
    if int(summary.get("token_event_count") or 0) == 0:
        warnings.append("no_token_events_available")
    attribution_action_required_count = summary.get("attribution_gap_action_required_count")
    if isinstance(attribution_action_required_count, (int, float)) and not isinstance(attribution_action_required_count, bool):
        if attribution_action_required_count > 0:
            warnings.append(f"attribution_gap_action_required_count:{int(attribution_action_required_count)}")
    elif int(summary.get("implementation_token_gap_count") or 0):
        warnings.append(f"implementation_token_gap_count:{summary.get('implementation_token_gap_count')}")
    if str(summary.get("api_equivalent_estimate_status") or "unavailable") != "complete":
        warnings.append("api_equivalent_estimate_coverage_incomplete")
    if str(summary.get("chatgpt_credit_estimate_status") or "unavailable") != "complete":
        warnings.append("chatgpt_credit_estimate_coverage_incomplete")
    if int(summary.get("failure_cost_candidate_count") or 0):
        warnings.append(f"failure_cost_candidate_count:{summary.get('failure_cost_candidate_count')}")
    if int(summary.get("api_call_reduction_candidate_count") or 0) or int(summary.get("prompt_compression_candidate_count") or 0):
        if not as_dict(summary.get("selected_next_candidate")) and not summary.get("selected_next_candidate"):
            errors.append("selected_next_candidate_missing")
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Token Efficiency Scorecard",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Token events: {summary.get('token_event_count')}",
        f"- Total tokens: {summary.get('total_tokens')}",
        f"- API-equivalent benchmark: {summary.get('api_equivalent_cost_usd')} ({summary.get('api_equivalent_estimate_status')}; {summary.get('api_equivalent_cost_rows')}/{summary.get('token_event_count')} events priced; not an invoice)",
        f"- Actual billed cost: {summary.get('actual_billed_cost_usd')}",
        f"- Estimated ChatGPT credits: {summary.get('estimated_chatgpt_credits')} ({summary.get('chatgpt_credit_estimate_status')}; {summary.get('estimated_chatgpt_credit_rows')}/{summary.get('token_event_count')} events priced; not an observed debit)",
        f"- OAuth quota tier: {summary.get('oauth_quota_tier')}",
        f"- Cron/API reduction candidates: {summary.get('api_call_reduction_candidate_count')}",
        f"- Prompt compression candidates: {summary.get('prompt_compression_candidate_count')}",
        f"- Selected next candidate: {summary.get('selected_next_candidate')} ({summary.get('selected_next_candidate_type')})",
        f"- Implementation attribution gaps: raw {summary.get('implementation_token_gap_count')}; action-required {summary.get('attribution_gap_action_required_count')} (resolution: {summary.get('attribution_gap_resolution_status')})",
        f"- Isolated-agent fleet: {summary.get('fleet_reporting_status')} / utilized {summary.get('fleet_utilized_agent_count')}/{summary.get('fleet_configured_agent_count')}",
        f"- Fleet pricing-grade attribution: {summary.get('fleet_pricing_grade_attribution_coverage_percent')}%",
        f"- Fleet outcomes: parent jobs completed {summary.get('fleet_parent_job_completed_count')}; Main accepted {summary.get('fleet_main_accepted_count')}/{summary.get('fleet_outcome_eligible_completed_lane_count')} tracked; QA passed {summary.get('fleet_qa_pass_count')}/{summary.get('fleet_qa_review_completed_count')} ({summary.get('fleet_qa_yield_percent')}%); historical/untracked {summary.get('fleet_historical_or_untracked_completed_lane_count')}; rework {summary.get('fleet_rework_count')}; gaps {summary.get('fleet_attribution_gap_count')}",
        "",
        "## Top Candidates",
        "",
    ]
    for row in as_list(payload.get("top_cron_efficiency_candidates"))[:10]:
        item = as_dict(row)
        lines.append(
            f"- {item.get('cron_job_name')}: {item.get('total_tokens')} tokens, "
            f"{item.get('run_count')} runs, candidates {', '.join(as_list(item.get('candidate_types')))}"
        )
    lines.extend(["", "## Actions", ""])
    for row in as_list(payload.get("action_items")):
        item = as_dict(row)
        lines.append(f"- `{item.get('id')}`: `{item.get('state')}` - {item.get('next_action')}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--token-usage", type=Path, default=TOKEN_USAGE)
    parser.add_argument("--token-budget", type=Path, default=TOKEN_BUDGET)
    parser.add_argument("--cron-contract-dir", type=Path, default=CRON_CONTRACTS)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token_usage = args.token_usage if args.token_usage.is_absolute() else ROOT / args.token_usage
    token_budget = args.token_budget if args.token_budget.is_absolute() else ROOT / args.token_budget
    cron_contract_dir = args.cron_contract_dir if args.cron_contract_dir.is_absolute() else ROOT / args.cron_contract_dir
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    payload = build_payload(token_usage, token_budget, cron_contract_dir)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = as_dict(payload.get("summary"))
        print(
            f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
            f"total_tokens={summary.get('total_tokens')} api_candidates={summary.get('api_call_reduction_candidate_count')} "
            f"prompt_candidates={summary.get('prompt_compression_candidate_count')}"
        )
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
