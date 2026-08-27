#!/usr/bin/env python3
"""Focused tests for cron_predispatch_efficiency_plan.py."""

from __future__ import annotations

import cron_predispatch_efficiency_plan as plan


def test_agent_turn_requires_payload_diff() -> None:
    scorecard = {
        "status": "warning",
        "token_event_count": 10,
        "api_equivalent_cost_usd": 1.23,
        "api_equivalent_estimate_status": "partial_unknown_input_semantics_or_missing_rate",
        "api_equivalent_cost_rows": 2,
        "api_equivalent_cost_event_coverage_percent": 20.0,
        "estimated_cost_total": 1.23,
        "estimated_chatgpt_credits": 12.5,
        "chatgpt_credit_estimate_status": "partial_separate_no_public_rate_or_missing_rate",
        "estimated_chatgpt_credit_rows": 2,
        "chatgpt_credit_event_coverage_percent": 20.0,
        "actual_billed_cost_usd": None,
        "billing_semantics": {
            "billing_mode": "oauth_subscription",
            "api_equivalent_is_not_invoice": True,
        },
        "oauth_capacity_control": {
            "state": "normal",
            "remaining_percent": 62.0,
            "automatic_action_allowed": False,
        },
        "implementation_token_gap_count": 3,
        "cron_candidates": [{"cron_name": "Agent Job", "total_tokens": 1000}],
    }
    cron_export = {"jobs": [{"name": "Agent Job", "enabled": True, "payload": {"kind": "agentTurn", "model": "m"}}]}
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["status"] == "warning"
    assert payload["summary"]["agent_turn_candidate_count"] == 1
    assert payload["summary"]["api_equivalent_cost_usd"] == 1.23
    assert payload["summary"]["api_equivalent_estimate_status"].startswith("partial_")
    assert payload["summary"]["api_equivalent_cost_rows"] == 2
    assert payload["summary"]["estimated_chatgpt_credits"] == 12.5
    assert payload["summary"]["chatgpt_credit_estimate_status"].startswith("partial_")
    assert payload["summary"]["actual_billed_cost_usd"] is None
    assert payload["summary"]["oauth_quota_state"] == "normal"
    assert payload["billing_semantics"]["api_equivalent_is_not_invoice"] is True
    assert payload["oauth_capacity_control"]["automatic_action_allowed"] is False
    assert payload["candidates"][0]["implementation_route"] == "cron_payload_diff_required"
    assert payload["candidates"][0]["script_level_prefilter_saves_model_tokens"] is False


def test_command_payload_is_wrapper_candidate() -> None:
    scorecard = {"cron_candidates": [{"job_name": "Command Job", "tokens": 100}]}
    cron_export = {"jobs": [{"name": "Command Job", "enabled": True, "payload": {"kind": "command"}}]}
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["summary"]["command_wrapper_candidate_count"] == 0
    assert payload["candidates"][0]["implementation_route"] == "command_prefilter_runtime_efficiency_candidate"
    assert payload["candidates"][0]["script_level_prefilter_saves_model_tokens"] is False
    assert payload["candidates"][0]["script_level_prefilter_saves_runtime_work"] is True


def test_command_payload_with_model_path_can_save_model_tokens() -> None:
    scorecard = {"cron_candidates": [{"job_name": "Command Model Job", "tokens": 100}]}
    cron_export = {
        "jobs": [
            {
                "name": "Command Model Job",
                "enabled": True,
                "payload": {"kind": "command", "model": "provider/model"},
            }
        ]
    }
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["summary"]["command_wrapper_candidate_count"] == 1
    assert payload["candidates"][0]["implementation_route"] == "script_prefilter_wrapper_candidate"
    assert payload["candidates"][0]["script_level_prefilter_saves_model_tokens"] is True


def test_existing_changed_only_command_gate_is_detected() -> None:
    scorecard = {"cron_candidates": [{"job_name": "Changed Only Job", "tokens": 100}]}
    cron_export = {
        "jobs": [
            {
                "name": "Changed Only Job",
                "enabled": True,
                "payload": {"kind": "command", "argv": ["python", "runner.py", "--changed-only"]},
            }
        ]
    }
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["summary"]["existing_changed_only_command_gate_count"] == 1
    assert payload["summary"]["existing_changed_input_command_gate_count"] == 1
    assert payload["candidates"][0]["implementation_route"] == "existing_changed_input_command_gate_present"
    assert payload["candidates"][0]["existing_changed_only_gate"] is True


def test_skip_if_unchanged_command_gate_is_detected() -> None:
    scorecard = {"cron_candidates": [{"job_name": "Skip Job", "tokens": 100}]}
    cron_export = {
        "jobs": [
            {
                "name": "Skip Job",
                "enabled": True,
                "payload": {"kind": "command", "argv": ["python", "runner.py", "--skip-if-unchanged"]},
            }
        ]
    }
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["summary"]["existing_changed_input_command_gate_count"] == 1
    assert payload["candidates"][0]["implementation_route"] == "existing_changed_input_command_gate_present"


def test_description_changed_input_skip_command_gate_is_detected() -> None:
    scorecard = {"cron_candidates": [{"job_name": "Digest Job", "tokens": 100}]}
    cron_export = {
        "jobs": [
            {
                "name": "Digest Job",
                "enabled": True,
                "description": "Command-backed digest with changed-input skip.",
                "payload": {"kind": "command", "argv": ["python", "runner.py"]},
            }
        ]
    }
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["summary"]["existing_changed_input_command_gate_count"] == 1
    assert payload["candidates"][0]["existing_changed_only_gate"] is True


def test_known_default_skip_wrapper_is_detected() -> None:
    scorecard = {"cron_candidates": [{"job_name": "Security Job", "tokens": 100}]}
    cron_export = {
        "jobs": [
            {
                "name": "Security Job",
                "enabled": True,
                "payload": {"kind": "command", "argv": ["python", "scripts\\cyber_security_daily_audit_cron_runner.py"]},
            }
        ]
    }
    payload = plan.build_plan(scorecard, cron_export, limit=10)
    assert payload["summary"]["existing_changed_input_command_gate_count"] == 1
    assert payload["candidates"][0]["implementation_route"] == "existing_changed_input_command_gate_present"


def main() -> int:
    test_agent_turn_requires_payload_diff()
    test_command_payload_is_wrapper_candidate()
    test_command_payload_with_model_path_can_save_model_tokens()
    test_existing_changed_only_command_gate_is_detected()
    test_skip_if_unchanged_command_gate_is_detected()
    test_description_changed_input_skip_command_gate_is_detected()
    test_known_default_skip_wrapper_is_detected()
    print("cron_predispatch_efficiency_plan_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
