#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "token_budget_status.py"


def load_module():
    spec = importlib.util.spec_from_file_location("token_budget_status", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_token_budget_exposes_operator_envelope_without_content_capture() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        source.write_text(json.dumps({
            "status": "ok",
            "summary": {
                "total_tokens": 1234,
                "estimated_cost_total": 1.23,
                "pricing_status": "loaded",
                "implementation_token_gap_count": 2,
                "token_event_count": 4,
                "cron_token_event_count": 3,
                "unique_cron_job_count": 2,
                "unique_model_count": 1,
            },
            "top_cron_jobs_by_tokens": [
                {"cron_job_name": "A", "total_tokens": 900},
                {"cron_job_name": "B", "total_tokens": 300},
            ],
        }), encoding="utf-8")

        payload = module.build_payload(source)

        assert payload["tokens_envelope"]["workspace_total_tokens"] == 1234
        assert payload["summary"]["api_equivalent_cost_usd"] == 1.23
        assert payload["summary"]["estimated_cost_total"] == 1.23
        assert payload["summary"]["estimated_cost_total_deprecated_alias_for"] == "api_equivalent_cost_usd"
        assert payload["tokens_envelope"]["last_24h_burn_status"] == "not_available_from_current_summary_packet"
        assert payload["authority_boundary"]["raw_prompt_capture_allowed"] is False
        assert payload["authority_boundary"]["tool_payload_capture_allowed"] is False
        assert payload["authority_boundary"]["platform_billing_api_call_allowed"] is False
        assert payload["authority_boundary"]["automatic_quota_action_allowed"] is False
        assert payload["top_token_heavy_cron_jobs"][0]["cron_job_name"] == "A"
        assert payload["top_token_heavy_cron_jobs"][0]["api_equivalent_cost_usd"] is None
        assert "implementation_token_attribution_gap_present" in payload["validation"]["warnings"]
        assert "oauth_capacity_snapshot_missing_or_stale" in payload["validation"]["warnings"]


def test_token_budget_propagates_oauth_cost_credit_and_capacity_contract() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        source.write_text(json.dumps({
            "status": "ok",
            "summary": {
                "total_tokens": 5000,
                "api_equivalent_cost_usd": 4.25,
                "estimated_cost_total": 4.25,
                "estimated_chatgpt_credits": 42.5,
                "actual_billed_cost_usd": None,
                "pricing_status": "loaded",
                "implementation_token_gap_count": 0,
                "token_event_count": 1,
                "api_equivalent_estimate_status": "complete",
                "api_equivalent_cost_rows": 1,
                "api_equivalent_cost_event_coverage_percent": 100.0,
                "chatgpt_credit_estimate_status": "complete",
                "estimated_chatgpt_credit_rows": 1,
                "chatgpt_credit_event_coverage_percent": 100.0,
            },
            "billing_semantics": {
                "billing_mode": "oauth_subscription",
                "api_equivalent_is_not_invoice": True,
                "actual_billed_cost_is_inferred": False,
            },
            "oauth_capacity_control": {
                "status": "current",
                "tier": "reduce_routine",
                "remaining_percent": 37.5,
                "reset_at_utc": "2026-08-15T00:00:00Z",
                "days_until_reset": 6,
                "reserve_percent": 20,
                "daily_burn_guidance": "preserve reserve",
                "automatic_action_allowed": False,
            },
            "top_cron_jobs_by_tokens": [{
                "cron_job_name": "A",
                "count": 1,
                "total_tokens": 5000,
                "api_equivalent_cost_usd": 4.25,
                "api_equivalent_cost_rows": 1,
                "api_equivalent_estimate_status": "complete",
                "estimated_cost": 4.25,
                "estimated_chatgpt_credits": 42.5,
                "estimated_chatgpt_credit_rows": 1,
                "chatgpt_credit_estimate_status": "complete",
            }],
        }), encoding="utf-8")

        payload = module.build_payload(source)

        assert payload["validation"]["status"] == "ok"
        assert payload["billing_semantics"]["billing_mode"] == "oauth_subscription"
        assert payload["billing_semantics"]["api_equivalent_is_not_invoice"] is True
        assert payload["oauth_capacity_control"]["tier"] == "reduce_routine"
        assert payload["oauth_capacity_control"]["remaining_percent"] == 37.5
        assert payload["oauth_capacity_control"]["automatic_action_allowed"] is False
        assert payload["summary"]["api_equivalent_cost_usd"] == 4.25
        assert payload["summary"]["estimated_cost_total"] == 4.25
        assert payload["summary"]["estimated_chatgpt_credits"] == 42.5
        assert payload["summary"]["api_equivalent_estimate_status"] == "complete"
        assert payload["summary"]["api_equivalent_cost_event_coverage_percent"] == 100.0
        assert payload["summary"]["chatgpt_credit_estimate_status"] == "complete"
        assert payload["summary"]["actual_billed_cost_usd"] is None
        assert payload["top_token_heavy_cron_jobs"][0]["api_equivalent_cost_usd"] == 4.25
        assert payload["top_token_heavy_cron_jobs"][0]["estimated_cost"] == 4.25
        assert "no Platform billing API call or inferred invoice" in payload["blocked_actions"]


def test_token_budget_blocks_unsafe_oauth_billing_or_automatic_action() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        source.write_text(json.dumps({
            "status": "ok",
            "summary": {
                "api_equivalent_cost_usd": 7.0,
                "estimated_cost_total": 7.0,
                "actual_billed_cost_usd": 7.0,
            },
            "billing_semantics": {
                "billing_mode": "oauth_subscription",
                "api_equivalent_is_not_invoice": False,
            },
            "oauth_capacity_control": {
                "status": "current",
                "tier": "normal",
                "automatic_action_allowed": True,
            },
        }), encoding="utf-8")

        payload = module.build_payload(source)

        assert payload["status"] == "blocked"
        assert "oauth_api_equivalent_presented_as_actual_bill" in payload["validation"]["errors"]
        assert "oauth_actual_billed_cost_lacks_owner_entered_provenance" in payload["validation"]["errors"]
        assert "oauth_capacity_automatic_action_enabled" in payload["validation"]["errors"]


def test_token_budget_treats_stale_quota_as_warning_not_blocked() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        source.write_text(json.dumps({
            "summary": {"api_equivalent_cost_usd": 1.0},
            "billing_semantics": {
                "billing_mode": "oauth_subscription",
                "api_equivalent_is_not_invoice": True,
            },
            "oauth_capacity_control": {
                "status": "stale",
                "tier": "normal",
                "automatic_action_allowed": False,
            },
        }), encoding="utf-8")

        payload = module.build_payload(source)

        assert payload["status"] == "warning"
        assert payload["validation"]["status"] == "warning"
        assert payload["validation"]["errors"] == []
        assert "oauth_capacity_snapshot_missing_or_stale" in payload["validation"]["warnings"]


def test_token_budget_normalizes_core_capacity_field_names() -> None:
    module = load_module()
    normalized = module.normalize_oauth_capacity_control({
        "oauth_capacity_control": {
            "state": "normal",
            "quota_tier": "normal",
            "snapshot_status": "fresh",
            "capacity_known": True,
            "remaining_percent": 62.0,
            "days_to_reset": 6.25,
            "automatic_action_allowed": False,
        }
    })
    assert normalized["status"] == "current"
    assert normalized["tier"] == "normal"
    assert normalized["snapshot_available"] is True


def test_token_budget_integrates_sanitized_fleet_windows_and_outcomes() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        agent = {
            "agent_id": "implementation-builder",
            "agent_role": "implementation_builder",
            "prompt": "must-not-leak",
            "usage_windows": {
                "rolling_5h_observed": {
                    "status": "observed", "event_count": 1, "total_tokens": 100,
                    "input_tokens": 80, "cached_input_tokens": 10, "cache_write_tokens": 0,
                    "output_tokens": 10, "raw_response": "must-not-leak",
                },
                "rolling_24h_gateway": {
                    "status": "ok", "date_labels": ["2026-08-09"],
                    "totals": {"totalTokens": 200, "totalCost": 0.2, "input": 150, "output": 50},
                    "cost_semantics": "api_equivalent_not_invoice",
                },
                "closed_7d_gateway": {
                    "status": "ok", "closed_day_count": 7,
                    "date_labels": ["2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-08"],
                    "totals": {"totalTokens": 700, "totalCost": 0.7},
                    "cost_semantics": "api_equivalent_not_invoice",
                },
            },
            "outcomes": {
                "lane_count": 3, "completed_lane_count": 3,
                "outcome_creditable_completed_lane_count": 2,
                "outcome_uncreditable_completed_lane_count": 1,
                "outcome_tracking_start_utc": "2026-08-09T00:00:00Z",
                "outcome_eligible_completed_lane_count": 2,
                "historical_or_untracked_completed_lane_count": 1,
                "parent_job_count": 1,
                "parent_job_completed_count": 1, "main_accepted_count": 1,
                "main_acceptance_pending_count": 1, "qa_review_completed_count": 1,
                "qa_pass_count": 1, "qa_yield_percent": 100.0,
                "rework_count": 1, "attribution_gap_count": 1,
            },
        }
        source.write_text(json.dumps({
            "schema": "veritas.token_usage_ledger_current.v1",
            "status": "ok",
            "validation": {"status": "ok", "errors": [], "warnings": []},
            "isolated_agent_event_validation": {"status": "ok", "finding_count": 0, "findings": []},
            "summary": {
                "total_tokens": 1000,
                "token_event_count": 2,
                "configured_isolated_agent_count": 1,
                "observed_isolated_agent_count": 1,
                "utilized_isolated_agent_count": 1,
                "isolated_agent_session_event_count": 2,
                "isolated_agent_attribution_grade_event_count": 2,
                "isolated_agent_pricing_grade_event_count": 1,
                "api_equivalent_estimate_status": "complete",
                "chatgpt_credit_estimate_status": "complete",
            },
            "billing_semantics": {"billing_mode": "oauth_subscription", "api_equivalent_is_not_invoice": True},
            "oauth_capacity_control": {"status": "current", "tier": "normal", "automatic_action_allowed": False},
            "per_agent_usage": [{
                "agent_id": "implementation-builder", "reporting_source": "gateway_usage_cost",
                "reporting_total_tokens": 700, "utilized": True, "utilization_share_percent": 100.0,
                "session_event_count": 2, "session_attribution_grade_event_count": 2,
                "session_pricing_grade_event_count": 1,
            }],
            "fleet_reporting": {
                "schema": "veritas.isolated_agent_fleet_reporting.v1",
                "generated_at_utc": "2026-08-09T18:00:00Z",
                "outcome_credit_contract": {
                    "version": "veritas.fleet_outcome_credit.v1",
                    "status": "verified",
                    "post_cutover_source_reverification_required": True,
                },
                "window_contract": {
                    "gateway_cost_semantics": "api_equivalent_not_invoice",
                    "gateway_cache_must_be_clean": True,
                    "actual_billed_cost_inferred": False,
                },
                "summary": {"gateway_24h_ready_agent_count": 1, "gateway_closed_7d_ready_agent_count": 1},
                "agents": [agent],
            },
        }), encoding="utf-8")

        payload = module.build_payload(source)
        fleet = payload["fleet_usage"]
        serialized = json.dumps(fleet, sort_keys=True)

        assert fleet["status"] == "ok"
        assert fleet["usage_windows"]["rolling_5h_observed"]["total_tokens"] == 100
        assert fleet["usage_windows"]["rolling_24h_gateway"]["total_tokens"] == 200
        assert fleet["usage_windows"]["closed_7d_gateway"]["total_tokens"] == 700
        assert fleet["summary"]["pricing_grade_attribution_coverage_percent"] == 50.0
        assert fleet["outcome_telemetry_status"] == "verified"
        assert fleet["summary"]["parent_job_completed_count"] == 1
        assert fleet["summary"]["main_accepted_count"] == 1
        assert fleet["summary"]["outcome_eligible_completed_lane_count"] == 2
        assert fleet["summary"]["historical_or_untracked_completed_lane_count"] == 1
        assert fleet["summary"]["main_acceptance_percent"] == 50.0
        assert fleet["summary"]["qa_review_completed_count"] == 1
        assert fleet["summary"]["qa_yield_percent"] == 100.0
        assert fleet["summary"]["rework_count"] == 1
        assert fleet["summary"]["attribution_gap_count"] == 1
        assert fleet["billing_semantics"]["api_equivalent_is_not_invoice"] is True
        assert fleet["billing_semantics"]["actual_billed_cost_usd"] is None
        assert fleet["oauth_capacity_advisory"]["automatic_action_allowed"] is False
        assert "must-not-leak" not in serialized
        assert '"prompt"' not in serialized
        assert '"raw_response"' not in serialized


def test_token_budget_does_not_fallback_to_raw_completed_lanes_for_legacy_fleet_outcomes() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        source.write_text(json.dumps({
            "schema": "veritas.token_usage_ledger_current.v1",
            "status": "blocked",
            "validation": {"status": "error", "errors": ["receipt_missing"], "warnings": []},
            "isolated_agent_event_validation": {"status": "blocked", "finding_count": 1},
            "summary": {
                "configured_isolated_agent_count": 1,
                "isolated_agent_session_event_count": 1,
                "isolated_agent_attribution_grade_event_count": 1,
                "isolated_agent_pricing_grade_event_count": 1,
            },
            "oauth_capacity_control": {"status": "current", "tier": "normal", "automatic_action_allowed": False},
            "fleet_reporting": {
                "schema": "veritas.isolated_agent_fleet_reporting.v1",
                "outcome_credit_contract": {
                    "version": "veritas.fleet_outcome_credit.v1",
                    "status": "verified",
                    "post_cutover_source_reverification_required": True,
                },
                "summary": {"gateway_closed_7d_ready_agent_count": 1},
                "agents": [{
                    "agent_id": "implementation-builder",
                    "outcomes": {
                        "completed_lane_count": 1,
                        "outcome_creditable_completed_lane_count": 1,
                        "outcome_uncreditable_completed_lane_count": 0,
                        "outcome_eligible_completed_lane_count": 1,
                        "historical_or_untracked_completed_lane_count": 0,
                        "main_accepted_count": 1,
                        "qa_review_completed_count": 1,
                        "qa_pass_count": 1,
                    },
                }],
            },
        }), encoding="utf-8")
        payload = module.build_payload(source)
        fleet = payload["fleet_usage"]
        assert fleet["outcome_telemetry_status"] == "unavailable"
        assert fleet["outcome_telemetry_reason"] == "token_usage_ledger_validation_or_provenance_not_trusted"
        assert fleet["summary"]["completed_lane_count"] is None
        assert fleet["summary"]["outcome_eligible_completed_lane_count"] is None
        assert fleet["summary"]["main_accepted_count"] is None
        assert fleet["summary"]["qa_review_completed_count"] is None
        assert fleet["summary"]["qa_yield_percent"] is None
        assert "isolated_agent_fleet_outcome_telemetry_unavailable" in payload["validation"]["warnings"]


def test_token_budget_missing_fleet_reporting_is_warning_not_false_zero() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "token-usage-ledger-current.json"
        source.write_text(json.dumps({
            "summary": {"configured_isolated_agent_count": 6},
            "oauth_capacity_control": {"status": "current", "tier": "normal", "automatic_action_allowed": False},
        }), encoding="utf-8")
        payload = module.build_payload(source)
        assert payload["status"] == "warning"
        assert payload["fleet_usage"]["status"] == "unavailable"
        assert payload["fleet_usage"]["agents"] == []
        assert payload["fleet_usage"]["usage_windows"]["rolling_5h_observed"]["total_tokens"] is None
        assert payload["fleet_usage"]["usage_windows"]["rolling_24h_gateway"]["total_tokens"] is None
        assert payload["fleet_usage"]["usage_windows"]["closed_7d_gateway"]["total_tokens"] is None
        assert payload["fleet_usage"]["summary"]["parent_job_completed_count"] is None
        assert payload["fleet_usage"]["summary"]["main_accepted_count"] is None
        assert payload["fleet_usage"]["summary"]["qa_yield_percent"] is None
        assert payload["fleet_usage"]["summary"]["rework_count"] is None
        assert payload["fleet_usage"]["summary"]["attribution_gap_count"] is None
        assert "isolated_agent_fleet_reporting_unavailable" in payload["validation"]["warnings"]


if __name__ == "__main__":
    test_token_budget_exposes_operator_envelope_without_content_capture()
    test_token_budget_propagates_oauth_cost_credit_and_capacity_contract()
    test_token_budget_blocks_unsafe_oauth_billing_or_automatic_action()
    test_token_budget_treats_stale_quota_as_warning_not_blocked()
    test_token_budget_normalizes_core_capacity_field_names()
    test_token_budget_integrates_sanitized_fleet_windows_and_outcomes()
    test_token_budget_does_not_fallback_to_raw_completed_lanes_for_legacy_fleet_outcomes()
    test_token_budget_missing_fleet_reporting_is_warning_not_false_zero()
    print("token budget status tests passed")
