#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

import wf87_market_hours_gate_probe as probe


def test_market_session_context_detects_regular_hours() -> None:
    context = probe.market_session_context(datetime(2026, 6, 11, 15, 0, tzinfo=timezone.utc))
    assert context["regular_market_hours"] is True
    assert context["session_state"] == "regular_market_hours"


def test_market_session_context_detects_after_hours() -> None:
    context = probe.market_session_context(datetime(2026, 6, 12, 5, 0, tzinfo=timezone.utc))
    assert context["regular_market_hours"] is False
    assert context["session_state"] == "outside_regular_market_hours"


def test_authority_boundary_blocks_execution_and_kill_switch_lifecycle() -> None:
    boundary = probe.AUTHORITY_BOUNDARY
    assert boundary["review_only"] is True
    assert boundary["market_hours_probe_only"] is True
    for key in probe.REQUIRED_FALSE_AUTHORITY:
        assert boundary[key] is False


def test_command_plan_refreshes_shadow_threshold_sources_before_gate_artifacts() -> None:
    names = [name for name, _command, _timeout in probe.command_plan()]
    assert names[:2] == ["wf86_shadow_eligibility", "wf86_shadow_decision_ledger"]
    assert names.index("wf86_shadow_decision_ledger") < names.index("shadow_outcome_scorecard")
    assert names.index("wf86_shadow_decision_ledger") < names.index("v2_readiness_rollup")


def test_command_plan_can_skip_shadow_threshold_sources_outside_regular_hours() -> None:
    names = [name for name, _command, _timeout in probe.command_plan(include_shadow_threshold_refresh=False)]
    assert "wf86_shadow_eligibility" not in names
    assert "wf86_shadow_decision_ledger" not in names
    assert "v2_readiness_rollup" in names


def test_expected_artifacts_include_shadow_threshold_sources() -> None:
    assert "shadow_eligibility" in probe.EXPECTED_ARTIFACTS
    assert "shadow_decision_ledger" in probe.EXPECTED_ARTIFACTS


def test_outside_hours_payload_is_sample_only() -> None:
    payload = probe.build_payload([], datetime(2026, 6, 12, 5, 0, tzinfo=timezone.utc))
    assert payload["status"] == "outside_market_hours_sample_only"
    assert payload["summary"]["daylight_sample"] is False
    assert payload["validation"]["status"] == "warning"
    assert "outside_regular_market_hours_sample" in payload["validation"]["warnings"]


if __name__ == "__main__":
    test_market_session_context_detects_regular_hours()
    test_market_session_context_detects_after_hours()
    test_authority_boundary_blocks_execution_and_kill_switch_lifecycle()
    test_command_plan_refreshes_shadow_threshold_sources_before_gate_artifacts()
    test_command_plan_can_skip_shadow_threshold_sources_outside_regular_hours()
    test_expected_artifacts_include_shadow_threshold_sources()
    test_outside_hours_payload_is_sample_only()
    print("wf87_market_hours_gate_probe_tests_passed")
