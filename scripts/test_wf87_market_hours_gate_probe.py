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
    test_outside_hours_payload_is_sample_only()
    print("wf87_market_hours_gate_probe_tests_passed")
