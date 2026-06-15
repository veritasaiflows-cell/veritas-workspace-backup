#!/usr/bin/env python3
"""Focused tests for WF67 paper-position readiness classification."""
from __future__ import annotations

import alpaca_paper_position_sql_refresh as refresh
import wf67_paper_position_refresh_cron_check as cron_check


def blocked_packet_with_last_known() -> dict:
    return {
        "status": "blocked",
        "freshness": {
            "status": "blocked",
            "latest_successful_snapshot_at_utc": "2026-06-11T21:51:54Z",
            "last_known_positions_status": "stale_but_known",
        },
        "latest_refresh": {
            "status": "blocked",
            "validation_findings": [{"severity": "critical", "code": "kill_switch_invalid:not_expired"}],
        },
        "account_summary": {"open_orders_count": 0},
        "positions": [{"symbol": "ETN", "quantity": 1}],
        "authority_boundary": {"trade_or_account_action_allowed": False},
    }


def test_stale_known_positions_support_review_but_not_execution() -> None:
    packet = blocked_packet_with_last_known()
    classification = refresh.classify_readiness(packet)

    assert classification["paper_position_visibility_state"] == "stale_but_known"
    assert classification["planning_state"] == "usable_with_stale_disclosure"
    assert classification["refresh_blocker_scope"] == "read_only_refresh_only"
    assert classification["blocks_research_shadow_or_planning"] is False
    assert classification["blocks_paper_execution"] is True
    assert classification["paper_or_live_execution_allowed"] is False
    assert classification["owner_approval_inferred"] is False


def test_missing_last_known_positions_remains_blocking() -> None:
    packet = blocked_packet_with_last_known()
    packet["positions"] = []
    packet["freshness"]["latest_successful_snapshot_at_utc"] = None

    classification = refresh.classify_readiness(packet)

    assert classification["paper_position_visibility_state"] == "blocked_unavailable"
    assert classification["planning_state"] == "blocked_no_current_position_visibility"
    assert classification["blocks_research_shadow_or_planning"] is True
    assert classification["blocks_paper_execution"] is True


def test_cron_check_downgrades_stale_known_packet_to_warning() -> None:
    packet = blocked_packet_with_last_known()
    packet["readiness_classification"] = refresh.classify_readiness(packet)
    findings: list[dict] = []

    cron_check.classify_packet_status(packet, findings)

    assert findings == [
        {
            "severity": "warning",
            "code": "paper_positions_refresh_blocked_last_known_stale",
            "planning_state": "usable_with_stale_disclosure",
            "refresh_blocker_scope": "read_only_refresh_only",
            "refresh_blocker_codes": ["kill_switch_invalid:not_expired"],
            "paper_execution_state": "blocked_until_fresh_positions_exact_owner_approval_clean_wf67_guard_and_execution_kill_switch",
        }
    ]


if __name__ == "__main__":
    test_stale_known_positions_support_review_but_not_execution()
    test_missing_last_known_positions_remains_blocking()
    test_cron_check_downgrades_stale_known_packet_to_warning()
    print("wf67_paper_position_readiness_classifier_tests_passed")
