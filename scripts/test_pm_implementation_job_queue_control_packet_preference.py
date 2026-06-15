#!/usr/bin/env python3
"""Regression checks for PM implementation queue control-packet preference."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pm_implementation_job_queue as queue
from market_data_utils import atomic_write_json


def action(lane_id: str, lane_status: str) -> dict:
    return {
        "action_id": f"{lane_id}-execute_safe_next_step",
        "action_type": "execute_safe_next_step",
        "authority": "review_only",
        "description": f"Test action for {lane_id}",
        "heartbeat_may_execute": False,
        "helper_lane_allowed_from_main_session": True,
        "inline_execution_allowed": False,
        "lane_id": lane_id,
        "lane_status": lane_status,
        "rank": 1,
        "readiness_score": 90,
        "stop_lines": ["review-only"],
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        control = root / "pm-control-packet.json"
        pm_state = root / "pm-program-state.json"
        pm_actions = root / "pm-next-actions.json"
        cron_candidates = root / "cron-retire-merge-candidates.json"
        helper_packets = root / "helper-spawn-packets.json"

        fresh_program = {
            "schema": "test.pm_program_state",
            "generated_at_utc": "2026-06-10T00:00:00Z",
            "status": "ok",
            "next_actions": [action("trade_grade_decision_os", "ready")],
        }
        stale_actions = {
            "schema": "test.pm_next_actions",
            "generated_at_utc": "2026-06-09T00:00:00Z",
            "status": "ok",
            "next_actions": [action("wf78_scaleout", "blocked")],
        }
        atomic_write_json(control, {
            "schema": "test.pm_control_packet",
            "status": "ok",
            "sections": {"pm_program_state": fresh_program},
        })
        atomic_write_json(pm_state, {"status": "ok", "next_actions": []})
        atomic_write_json(pm_actions, stale_actions)
        atomic_write_json(cron_candidates, {"status": "ok", "candidates": []})
        atomic_write_json(helper_packets, {"status": "ok"})

        original = {
            "DEFAULT_CONTROL_PACKET": queue.DEFAULT_CONTROL_PACKET,
            "DEFAULT_PM_STATE": queue.DEFAULT_PM_STATE,
            "DEFAULT_PM_ACTIONS": queue.DEFAULT_PM_ACTIONS,
            "DEFAULT_CRON_CANDIDATES": queue.DEFAULT_CRON_CANDIDATES,
            "DEFAULT_HELPER_PACKETS": queue.DEFAULT_HELPER_PACKETS,
        }
        try:
            queue.DEFAULT_CONTROL_PACKET = control
            queue.DEFAULT_PM_STATE = pm_state
            queue.DEFAULT_PM_ACTIONS = pm_actions
            queue.DEFAULT_CRON_CANDIDATES = cron_candidates
            queue.DEFAULT_HELPER_PACKETS = helper_packets
            args = type("Args", (), {
                "pm_state": str(pm_state),
                "pm_actions": str(pm_actions),
                "cron_candidates": str(cron_candidates),
                "helper_packets": str(helper_packets),
                "max_pm_jobs": 10,
                "max_cron_jobs": 4,
            })()
            payload = queue.build_payload(args)
        finally:
            for key, value in original.items():
                setattr(queue, key, value)

        assert payload["status"] == "ok", payload
        assert payload["summary"]["blocked_job_count"] == 0, payload["summary"]
        assert payload["summary"]["top_job_id"] == "pm-01-trade-grade-decision-os-execute-safe-next-step", payload["summary"]
        assert payload["source_status"]["pm_next_actions_effective_source"].endswith(
            "#sections.pm_program_state.next_actions"
        ), payload["source_status"]

    print("pm_implementation_job_queue control-packet preference: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
