#!/usr/bin/env python3
"""Build an operator-facing token budget status packet from metadata ledgers."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
TOKEN_USAGE = TMP / "token-usage-ledger-current.json"
OUT = TMP / "token-budget-status.json"
SCHEMA = "veritas.token_budget_status.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "cost_estimate_only": True,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "external_export_allowed": False,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "platform_billing_api_call_allowed": False,
    "automatic_quota_action_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def normalize_billing_semantics(source: dict[str, Any]) -> dict[str, Any]:
    semantics = dict(as_dict(source.get("billing_semantics")))
    not_invoice = as_optional_bool(first_defined(
        semantics,
        "api_equivalent_is_not_invoice",
        "api_equivalent_cost_is_not_invoice",
        "api_equivalent_cost_usd_is_not_invoice",
    ))
    semantics["billing_mode"] = semantics.get("billing_mode") or "unavailable"
    # The consumer always labels the benchmark truthfully. An explicit unsafe
    # upstream value remains visible and is blocked by validate().
    semantics["api_equivalent_is_not_invoice"] = True if not_invoice is None else not_invoice
    semantics.setdefault("actual_billed_cost_is_inferred", False)
    semantics.setdefault("platform_billing_api_queried", False)
    return semantics


def normalize_oauth_capacity_control(source: dict[str, Any]) -> dict[str, Any]:
    control = dict(as_dict(source.get("oauth_capacity_control")))
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
    return control


def normalize_cost_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    api_equivalent = first_defined(row, "api_equivalent_cost_usd", "estimated_cost")
    normalized["api_equivalent_cost_usd"] = api_equivalent
    normalized["estimated_cost"] = api_equivalent
    normalized["estimated_cost_deprecated_alias_for"] = "api_equivalent_cost_usd"
    normalized["estimated_chatgpt_credits"] = row.get("estimated_chatgpt_credits")
    api_rows = int(first_defined(row, "api_equivalent_cost_rows", "estimated_cost_rows") or 0)
    credit_rows = int(row.get("estimated_chatgpt_credit_rows") or 0)
    run_count = int(row.get("count") or 0)
    normalized["api_equivalent_cost_rows"] = api_rows
    normalized["estimated_cost_rows"] = api_rows
    normalized["api_equivalent_estimate_status"] = row.get("api_equivalent_estimate_status") or (
        "unavailable" if not api_rows else "complete" if api_rows == run_count else "partial_unknown_input_semantics_or_missing_rate"
    )
    normalized["chatgpt_credit_estimate_status"] = row.get("chatgpt_credit_estimate_status") or (
        "unavailable" if not credit_rows else "complete" if credit_rows == run_count else "partial_separate_no_public_rate_or_missing_rate"
    )
    return normalized


def percent(numerator: Any, denominator: Any) -> float | None:
    try:
        denominator_value = float(denominator or 0)
        if denominator_value <= 0:
            return None
        return round((float(numerator or 0) / denominator_value) * 100.0, 4)
    except (TypeError, ValueError):
        return None


def safe_gateway_totals(value: Any) -> dict[str, Any]:
    row = as_dict(value)
    return {
        key: row.get(key)
        for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens", "totalCost", "missingCostEntries")
    }


def safe_fleet_window(value: Any, *, observed: bool = False) -> dict[str, Any]:
    row = as_dict(value)
    if observed:
        return {
            key: row.get(key)
            for key in (
                "status", "source", "coverage", "event_count", "total_tokens",
                "input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens",
            )
        }
    return {
        "status": row.get("status") or "unavailable",
        "source": row.get("source"),
        "date_labels": [str(item) for item in as_list(row.get("date_labels")) if isinstance(item, str)],
        "closed_day_count": row.get("closed_day_count"),
        "totals": safe_gateway_totals(row.get("totals")),
        "cost_semantics": row.get("cost_semantics"),
    }


def sum_window(agents: list[dict[str, Any]], name: str) -> dict[str, Any]:
    windows = [as_dict(as_dict(agent.get("usage_windows")).get(name)) for agent in agents]
    if name == "rolling_5h_observed":
        observed = [row for row in windows if row.get("status") == "observed"]
        return {
            "status": "partial_observed" if observed else "no_observed_session_events",
            "coverage": "partial_latest_session_snapshots_not_provider_history",
            "ready_agent_count": len(observed),
            "configured_agent_count": len(agents),
            "event_count": sum(int(row.get("event_count") or 0) for row in observed) if observed else None,
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in observed) if observed else None,
        }
    ready = [row for row in windows if row.get("status") == "ok"]
    total_cost_values = [as_dict(row.get("totals")).get("totalCost") for row in ready]
    all_costs_present = bool(ready) and all(value is not None for value in total_cost_values)
    return {
        "status": "ok" if len(ready) == len(agents) and agents else ("partial" if ready else "unavailable"),
        "ready_agent_count": len(ready),
        "configured_agent_count": len(agents),
        "total_tokens": sum(int(as_dict(row.get("totals")).get("totalTokens") or 0) for row in ready) if ready else None,
        "api_equivalent_cost_usd": round(sum(float(value or 0) for value in total_cost_values), 6) if all_costs_present else None,
        "api_equivalent_is_not_invoice": True,
        "actual_billed_cost_usd": None,
        "date_labels": sorted({
            str(item)
            for row in ready
            for item in as_list(row.get("date_labels"))
            if isinstance(item, str)
        }),
    }


def normalize_fleet_reporting(source: dict[str, Any], capacity: dict[str, Any]) -> dict[str, Any]:
    raw = as_dict(source.get("fleet_reporting"))
    source_summary = as_dict(source.get("summary"))
    outcome_contract = as_dict(raw.get("outcome_credit_contract"))
    required_outcome_fields = (
        "outcome_creditable_completed_lane_count",
        "outcome_uncreditable_completed_lane_count",
        "outcome_eligible_completed_lane_count",
        "historical_or_untracked_completed_lane_count",
        "qa_review_completed_count",
    )
    source_validation = as_dict(source.get("validation"))
    source_event_validation = as_dict(source.get("isolated_agent_event_validation"))
    source_contract_trusted = bool(
        source.get("schema") == "veritas.token_usage_ledger_current.v1"
        and str(source.get("status") or "").lower() in {"ok", "warning"}
        and str(source_validation.get("status") or "").lower() in {"ok", "warning"}
        and not as_list(source_validation.get("errors"))
        and source_event_validation.get("status") == "ok"
    )
    utilization_by_agent = {
        str(row.get("agent_id")): as_dict(row)
        for row in as_list(source.get("per_agent_usage"))
        if isinstance(row, dict) and row.get("agent_id")
    }
    agents: list[dict[str, Any]] = []
    for raw_agent in as_list(raw.get("agents")):
        if not isinstance(raw_agent, dict):
            continue
        agent_id = str(raw_agent.get("agent_id") or "")
        outcomes = as_dict(raw_agent.get("outcomes"))
        windows = as_dict(raw_agent.get("usage_windows"))
        utilization = as_dict(utilization_by_agent.get(agent_id))
        agents.append({
            "agent_id": agent_id,
            "agent_role": raw_agent.get("agent_role"),
            "utilization": {
                key: utilization.get(key)
                for key in (
                    "reporting_source", "gateway_status", "reporting_window_days",
                    "reporting_total_tokens", "reporting_total_cost", "session_event_count",
                    "session_total_tokens", "session_attribution_grade_event_count",
                    "session_pricing_grade_event_count", "implementation_attributed_event_count",
                    "utilized", "gateway_attribution_grade", "gateway_pricing_grade",
                    "utilization_share_percent",
                )
            },
            "usage_windows": {
                "rolling_5h_observed": safe_fleet_window(windows.get("rolling_5h_observed"), observed=True),
                "rolling_24h_gateway": safe_fleet_window(windows.get("rolling_24h_gateway")),
                "closed_7d_gateway": safe_fleet_window(windows.get("closed_7d_gateway")),
            },
            "outcomes": {
                key: outcomes.get(key)
                for key in (
                    "lane_count", "completed_lane_count",
                    "outcome_creditable_completed_lane_count", "outcome_uncreditable_completed_lane_count",
                    "parent_job_count",
                    "outcome_tracking_start_utc", "outcome_eligible_completed_lane_count",
                    "historical_or_untracked_completed_lane_count",
                    "parent_job_completed_count", "main_accepted_count",
                    "main_acceptance_pending_count", "qa_review_completed_count",
                    "qa_pass_count", "qa_yield_percent",
                    "rework_count", "attribution_gap_count",
                )
            },
        })

    outcome_telemetry_verified = bool(
        raw
        and source_contract_trusted
        and outcome_contract.get("version") == "veritas.fleet_outcome_credit.v1"
        and outcome_contract.get("status") == "verified"
        and outcome_contract.get("post_cutover_source_reverification_required") is True
        and all(
            all(field in as_dict(row.get("outcomes")) for field in required_outcome_fields)
            for row in agents
        )
    )
    outcomes_available = bool(agents) and outcome_telemetry_verified
    completed = sum(int(as_dict(row.get("outcomes")).get("completed_lane_count") or 0) for row in agents) if outcomes_available else None
    outcome_eligible_completed = sum(
        int(as_dict(row.get("outcomes")).get("outcome_eligible_completed_lane_count") or 0)
        for row in agents
    ) if outcomes_available else None
    historical_or_untracked_completed = sum(
        int(as_dict(row.get("outcomes")).get("historical_or_untracked_completed_lane_count") or 0)
        for row in agents
    ) if outcomes_available else None
    parent_jobs = sum(int(as_dict(row.get("outcomes")).get("parent_job_count") or 0) for row in agents) if outcomes_available else None
    parent_completed = sum(int(as_dict(row.get("outcomes")).get("parent_job_completed_count") or 0) for row in agents) if outcomes_available else None
    main_accepted = sum(int(as_dict(row.get("outcomes")).get("main_accepted_count") or 0) for row in agents) if outcomes_available else None
    qa_pass = sum(int(as_dict(row.get("outcomes")).get("qa_pass_count") or 0) for row in agents) if outcomes_available else None
    qa_review_completed = sum(
        int(as_dict(row.get("outcomes")).get("qa_review_completed_count") or 0)
        for row in agents
    ) if outcomes_available else None
    rework = sum(int(as_dict(row.get("outcomes")).get("rework_count") or 0) for row in agents) if outcomes_available else None
    attribution_gaps = sum(int(as_dict(row.get("outcomes")).get("attribution_gap_count") or 0) for row in agents) if outcomes_available else None
    outcome_tracking_start_utc = next(
        (
            as_dict(row.get("outcomes")).get("outcome_tracking_start_utc")
            for row in agents
            if as_dict(row.get("outcomes")).get("outcome_tracking_start_utc")
        ),
        None,
    )
    session_events = int(source_summary.get("isolated_agent_session_event_count") or 0)
    attribution_grade_events = int(source_summary.get("isolated_agent_attribution_grade_event_count") or 0)
    pricing_grade_events = int(source_summary.get("isolated_agent_pricing_grade_event_count") or 0)
    source_cost_semantics = as_dict(raw.get("window_contract")).get("gateway_cost_semantics")
    return {
        "schema": "veritas.isolated_agent_fleet_budget_view.v1",
        "present": bool(raw),
        "status": (
            "unavailable" if not raw
            else "ok" if (
                int(as_dict(raw.get("summary")).get("gateway_closed_7d_ready_agent_count") or 0) == len(agents)
                and agents and outcome_telemetry_verified
            )
            else "partial"
        ),
        "generated_at_utc": raw.get("generated_at_utc"),
        "source_schema": raw.get("schema"),
        "outcome_telemetry_status": "verified" if outcome_telemetry_verified else ("unavailable" if raw else "not_present"),
        "outcome_telemetry_reason": (
            None if outcome_telemetry_verified
            else (
                "token_usage_ledger_validation_or_provenance_not_trusted"
                if raw and not source_contract_trusted
                else "receipt_revalidated_outcome_contract_required"
            )
        ),
        "window_contract": {
            key: as_dict(raw.get("window_contract")).get(key)
            for key in (
                "rolling_5h_observed_source", "rolling_24h_source", "closed_7d_source",
                "gateway_cache_must_be_clean", "gateway_cost_semantics", "actual_billed_cost_inferred",
            )
        },
        "usage_windows": {
            "rolling_5h_observed": sum_window(agents, "rolling_5h_observed"),
            "rolling_24h_gateway": sum_window(agents, "rolling_24h_gateway"),
            "closed_7d_gateway": sum_window(agents, "closed_7d_gateway"),
        },
        "summary": {
            "configured_agent_count": len(agents) or source_summary.get("configured_isolated_agent_count"),
            "observed_agent_count": source_summary.get("observed_isolated_agent_count"),
            "utilized_agent_count": source_summary.get("utilized_isolated_agent_count"),
            "session_event_count": session_events,
            "attribution_grade_event_count": attribution_grade_events,
            "attribution_grade_coverage_percent": percent(attribution_grade_events, session_events),
            "pricing_grade_event_count": pricing_grade_events,
            "pricing_grade_attribution_coverage_percent": percent(pricing_grade_events, session_events),
            "parent_job_count": parent_jobs,
            "parent_job_completed_count": parent_completed,
            "parent_job_completion_percent": percent(parent_completed, parent_jobs),
            "completed_lane_count": completed,
            "outcome_tracking_start_utc": outcome_tracking_start_utc,
            "outcome_eligible_completed_lane_count": outcome_eligible_completed,
            "historical_or_untracked_completed_lane_count": historical_or_untracked_completed,
            "main_accepted_count": main_accepted,
            "main_acceptance_percent": percent(main_accepted, outcome_eligible_completed),
            "main_acceptance_pending_count": max(outcome_eligible_completed - main_accepted, 0) if outcome_eligible_completed is not None and main_accepted is not None else None,
            "qa_review_completed_count": qa_review_completed,
            "qa_pass_count": qa_pass,
            "qa_yield_percent": percent(qa_pass, qa_review_completed),
            "rework_count": rework,
            "rework_percent": percent(rework, outcome_eligible_completed),
            "attribution_gap_count": attribution_gaps,
            "source_gateway_24h_ready_agent_count": as_dict(raw.get("summary")).get("gateway_24h_ready_agent_count"),
            "source_gateway_closed_7d_ready_agent_count": as_dict(raw.get("summary")).get("gateway_closed_7d_ready_agent_count"),
        },
        "agents": agents,
        "billing_semantics": {
            "label": "API-equivalent benchmark",
            "source_cost_semantics": source_cost_semantics,
            "api_equivalent_is_not_invoice": source_cost_semantics in {None, "api_equivalent_not_invoice"},
            "actual_billed_cost_usd": None,
        },
        "oauth_capacity_advisory": {
            "status": capacity.get("status"),
            "tier": capacity.get("tier"),
            "remaining_percent": first_defined(capacity, "remaining_percent", "remaining_capacity_percent"),
            "reset_at_utc": first_defined(capacity, "reset_at_utc", "reset_utc"),
            "automatic_action_allowed": False,
        },
        "privacy_contract": {
            "metadata_only": True,
            "raw_prompt_stored": False,
            "raw_response_stored": False,
            "tool_payload_stored": False,
        },
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


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    existing = as_dict(payload.get("validation"))
    errors = [str(value) for value in as_list(existing.get("errors"))]
    warnings = [str(value) for value in as_list(existing.get("warnings"))]
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")

    summary = as_dict(payload.get("summary"))
    semantics = as_dict(payload.get("billing_semantics"))
    capacity = as_dict(payload.get("oauth_capacity_control"))
    fleet = as_dict(payload.get("fleet_usage"))
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
        actual_billed = summary.get("actual_billed_cost_usd")
        if actual_billed is not None and not actual_cost_is_owner_entered(summary, semantics):
            errors.append("oauth_actual_billed_cost_lacks_owner_entered_provenance")

    if capacity.get("automatic_action_allowed") is not False:
        errors.append("oauth_capacity_automatic_action_enabled")
    if fleet:
        fleet_billing = as_dict(fleet.get("billing_semantics"))
        fleet_capacity = as_dict(fleet.get("oauth_capacity_advisory"))
        privacy = as_dict(fleet.get("privacy_contract"))
        if fleet_billing.get("api_equivalent_is_not_invoice") is not True:
            errors.append("fleet_api_equivalent_presented_as_invoice")
        if fleet_billing.get("actual_billed_cost_usd") is not None:
            errors.append("fleet_actual_billed_cost_must_remain_unallocated")
        if fleet_capacity.get("automatic_action_allowed") is not False:
            errors.append("fleet_oauth_capacity_automatic_action_enabled")
        for key in ("metadata_only",):
            if privacy.get(key) is not True:
                errors.append(f"fleet_privacy_contract_invalid:{key}")
        for key in ("raw_prompt_stored", "raw_response_stored", "tool_payload_stored"):
            if privacy.get(key) is not False:
                errors.append(f"fleet_privacy_contract_invalid:{key}")
    quota_status = str(capacity.get("status") or "unavailable").strip().lower()
    quota_tier = str(capacity.get("tier") or "unavailable").strip().lower()
    if quota_status in {"", "missing", "stale", "unknown", "unavailable"} or quota_tier in {
        "", "missing", "stale", "unknown", "unavailable"
    }:
        warnings.append("oauth_capacity_snapshot_missing_or_stale")

    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def build_payload(path: Path = TOKEN_USAGE, top_limit: int = 5) -> dict[str, Any]:
    source = load(path)
    summary = as_dict(source.get("summary"))
    top_jobs = [normalize_cost_row(as_dict(row)) for row in as_list(source.get("top_cron_jobs_by_tokens"))[:top_limit]]
    total_tokens = int(summary.get("total_tokens") or 0)
    api_equivalent_cost = first_defined(summary, "api_equivalent_cost_usd", "estimated_cost_total")
    estimated_chatgpt_credits = summary.get("estimated_chatgpt_credits")
    actual_billed_cost = summary.get("actual_billed_cost_usd")
    billing_semantics = normalize_billing_semantics(source)
    oauth_capacity_control = normalize_oauth_capacity_control(source)
    fleet_reporting = normalize_fleet_reporting(source, oauth_capacity_control)
    usage_pace = as_dict(source.get("usage_pace"))
    warnings: list[str] = []
    if not source:
        warnings.append("token_usage_source_missing_or_unparseable")
    if int(summary.get("implementation_token_gap_count") or 0):
        warnings.append("implementation_token_attribution_gap_present")
    if str(summary.get("api_equivalent_estimate_status") or "unavailable") != "complete":
        warnings.append("api_equivalent_estimate_coverage_incomplete")
    if str(summary.get("chatgpt_credit_estimate_status") or "unavailable") != "complete":
        warnings.append("chatgpt_credit_estimate_coverage_incomplete")
    if int(summary.get("configured_isolated_agent_count") or 0) and fleet_reporting.get("present") is not True:
        warnings.append("isolated_agent_fleet_reporting_unavailable")
    if fleet_reporting.get("present") is True and fleet_reporting.get("outcome_telemetry_status") != "verified":
        warnings.append("isolated_agent_fleet_outcome_telemetry_unavailable")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning" if warnings else "ok",
        "purpose": "Operator-facing token budget envelope derived from metadata-only token usage ledger.",
        "source_artifacts": {"token_usage_ledger": rel(path)},
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "billing_semantics": billing_semantics,
        "oauth_capacity_control": oauth_capacity_control,
        "fleet_usage": fleet_reporting,
        "usage_pace": usage_pace,
        "compatibility": {
            "schema_version_preserved": SCHEMA,
            "deprecated_aliases": {
                "summary.estimated_cost_total": "summary.api_equivalent_cost_usd",
                "tokens_envelope.estimated_cost_total": "tokens_envelope.api_equivalent_cost_usd",
                "top_token_heavy_cron_jobs[].estimated_cost": "top_token_heavy_cron_jobs[].api_equivalent_cost_usd",
            },
        },
        "summary": {
            "total_tokens": total_tokens,
            "api_equivalent_cost_usd": api_equivalent_cost,
            "api_equivalent_estimate_status": summary.get("api_equivalent_estimate_status"),
            "api_equivalent_cost_rows": summary.get("api_equivalent_cost_rows"),
            "api_equivalent_cost_event_coverage_percent": summary.get("api_equivalent_cost_event_coverage_percent"),
            "api_equivalent_priced_tokens": summary.get("api_equivalent_priced_tokens"),
            "estimated_cost_total": api_equivalent_cost,
            "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
            "estimated_chatgpt_credits": estimated_chatgpt_credits,
            "chatgpt_credit_estimate_status": summary.get("chatgpt_credit_estimate_status"),
            "estimated_chatgpt_credit_rows": summary.get("estimated_chatgpt_credit_rows"),
            "chatgpt_credit_event_coverage_percent": summary.get("chatgpt_credit_event_coverage_percent"),
            "chatgpt_credit_priced_tokens": summary.get("chatgpt_credit_priced_tokens"),
            "actual_billed_cost_usd": actual_billed_cost,
            "unknown_or_invalid_input_token_semantics_event_count": summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            "pricing_status": summary.get("pricing_status"),
            "token_event_count": summary.get("token_event_count"),
            "cron_token_event_count": summary.get("cron_token_event_count"),
            "implementation_token_event_count": summary.get("implementation_token_event_count"),
            "implementation_token_gap_count": summary.get("implementation_token_gap_count"),
            "unique_cron_job_count": summary.get("unique_cron_job_count"),
            "unique_model_count": summary.get("unique_model_count"),
            "last_24h_burn_status": "not_available_from_current_summary_packet",
            "last_24h_total_tokens": None,
            "rolling_5h_total_tokens": as_dict(usage_pace.get("rolling_5h")).get("total_tokens"),
            "rolling_7d_observed_total_tokens": as_dict(usage_pace.get("rolling_7d_observed")).get("total_tokens"),
            "usage_timestamp_coverage_percent": usage_pace.get("usage_timestamp_coverage_percent"),
            "fleet_reporting_status": fleet_reporting.get("status"),
            "fleet_outcome_telemetry_status": fleet_reporting.get("outcome_telemetry_status"),
            "fleet_configured_agent_count": as_dict(fleet_reporting.get("summary")).get("configured_agent_count"),
            "fleet_utilized_agent_count": as_dict(fleet_reporting.get("summary")).get("utilized_agent_count"),
            "fleet_pricing_grade_attribution_coverage_percent": as_dict(fleet_reporting.get("summary")).get("pricing_grade_attribution_coverage_percent"),
            "fleet_parent_job_completed_count": as_dict(fleet_reporting.get("summary")).get("parent_job_completed_count"),
            "fleet_outcome_eligible_completed_lane_count": as_dict(fleet_reporting.get("summary")).get("outcome_eligible_completed_lane_count"),
            "fleet_historical_or_untracked_completed_lane_count": as_dict(fleet_reporting.get("summary")).get("historical_or_untracked_completed_lane_count"),
            "fleet_main_accepted_count": as_dict(fleet_reporting.get("summary")).get("main_accepted_count"),
            "fleet_qa_review_completed_count": as_dict(fleet_reporting.get("summary")).get("qa_review_completed_count"),
            "fleet_qa_pass_count": as_dict(fleet_reporting.get("summary")).get("qa_pass_count"),
            "fleet_qa_yield_percent": as_dict(fleet_reporting.get("summary")).get("qa_yield_percent"),
            "fleet_rework_count": as_dict(fleet_reporting.get("summary")).get("rework_count"),
            "fleet_attribution_gap_count": as_dict(fleet_reporting.get("summary")).get("attribution_gap_count"),
            "top_cron_job_count": len(top_jobs),
            "next_safe_action": "Use top_token_heavy_cron_jobs to target prompt/cron efficiency; do not infer content capture or finance quality.",
        },
        "tokens_envelope": {
            "workspace_total_tokens": total_tokens,
            "api_equivalent_cost_usd": api_equivalent_cost,
            "api_equivalent_estimate_status": summary.get("api_equivalent_estimate_status"),
            "api_equivalent_cost_rows": summary.get("api_equivalent_cost_rows"),
            "api_equivalent_cost_event_coverage_percent": summary.get("api_equivalent_cost_event_coverage_percent"),
            "estimated_cost_total": api_equivalent_cost,
            "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
            "estimated_chatgpt_credits": estimated_chatgpt_credits,
            "chatgpt_credit_estimate_status": summary.get("chatgpt_credit_estimate_status"),
            "estimated_chatgpt_credit_rows": summary.get("estimated_chatgpt_credit_rows"),
            "chatgpt_credit_event_coverage_percent": summary.get("chatgpt_credit_event_coverage_percent"),
            "actual_billed_cost_usd": actual_billed_cost,
            "pricing_status": summary.get("pricing_status"),
            "last_24h_burn_status": "not_available_from_current_summary_packet",
            "session_tokens_status": "unavailable_to_workspace_script",
            "isolated_agent_fleet": fleet_reporting,
        },
        "top_token_heavy_cron_jobs": top_jobs,
        "blocked_actions": [
            "no Platform billing API call or inferred invoice",
            "no automatic quota throttling, schedule change, or model-route mutation",
            "no runtime, config, or auth mutation",
            "no raw prompt, response, transcript, or tool payload capture",
        ],
        "validation": {"status": "ok", "errors": [], "warnings": warnings},
    }
    payload["validation"] = validate(payload)
    payload["status"] = payload["validation"]["status"]
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--source", type=Path, default=TOKEN_USAGE)
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source if args.source.is_absolute() else ROOT / args.source
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(source)
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({"status": payload["status"], "summary": payload["summary"], "out": rel(out) if args.write else None}, indent=2))
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
