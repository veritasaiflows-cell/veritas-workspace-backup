#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

from pm_main_session_handoff import build_handoff_from_payloads


def safe_action(action_id: str, lane_id: str, rank: int) -> dict:
    return {
        "action_id": action_id,
        "lane_id": lane_id,
        "rank": rank,
        "action_type": "refresh_artifact",
        "authority": "review_only",
        "inline_execution_allowed": False,
        "heartbeat_may_execute": False,
        "helper_lane_allowed_from_main_session": True,
        "stop_lines": ["no owner approval inference"],
    }


def test_handoff_prefers_ready_queue_job_over_ledger_completed_top_action() -> None:
    actions = {
        "next_actions": [
            safe_action("wf78_scaleout-refresh_artifact", "wf78_scaleout", 1),
            safe_action("tier_promotion_review-refresh_artifact", "tier_promotion_review", 2),
        ]
    }
    queue = {
        "summary": {"ready_job_count": 1},
        "jobs": [
            {
                "job_id": "pm-wf78-scaleout-refresh-artifact",
                "source_action_id": "wf78_scaleout-refresh_artifact",
                "status": "completed_by_ledger",
            },
            {
                "job_id": "pm-tier-promotion-review-refresh-artifact",
                "source_action_id": "tier_promotion_review-refresh_artifact",
                "status": "ready_for_main_or_helper",
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        handoff = build_handoff_from_payloads(actions, {}, {}, queue, Path(tmp) / "pm-dispatch-ledger.json", cooldown_hours=0)

    assert handoff["status"] == "ready_for_main_session"
    assert handoff["selected_action"]["action_id"] == "tier_promotion_review-refresh_artifact"
    assert handoff["selected_implementation_job"]["job_id"] == "pm-tier-promotion-review-refresh-artifact"
    assert handoff["signal_classification"]["class"] == "MAIN_SESSION_REQUIRED"


def test_handoff_returns_no_action_when_all_queue_jobs_are_ledger_completed() -> None:
    actions = {
        "next_actions": [
            safe_action("wf78_scaleout-refresh_artifact", "wf78_scaleout", 1),
            safe_action("tier_promotion_review-refresh_artifact", "tier_promotion_review", 2),
        ]
    }
    queue = {
        "summary": {"ready_job_count": 0},
        "jobs": [
            {
                "job_id": "pm-wf78-scaleout-refresh-artifact",
                "source_action_id": "wf78_scaleout-refresh_artifact",
                "status": "completed_by_ledger",
            },
            {
                "job_id": "pm-tier-promotion-review-refresh-artifact",
                "source_action_id": "tier_promotion_review-refresh_artifact",
                "status": "completed_by_ledger",
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        handoff = build_handoff_from_payloads(actions, {}, {}, queue, Path(tmp) / "pm-dispatch-ledger.json", cooldown_hours=0)

    assert handoff["status"] == "no_action"
    assert handoff["selected_action"] == {}
    assert handoff["signal_classification"]["class"] == "NO_REPLY"
    assert handoff["validation"]["warnings"] == ["no_pm_next_action_available"]


if __name__ == "__main__":
    test_handoff_prefers_ready_queue_job_over_ledger_completed_top_action()
    test_handoff_returns_no_action_when_all_queue_jobs_are_ledger_completed()
    print("pm_main_session_handoff_tests_passed")
