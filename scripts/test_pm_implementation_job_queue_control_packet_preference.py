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
        wf74_router = root / "wf74-autonomy-work-router.json"
        completion_ledger = root / "state" / "implementation-completion-ledger.jsonl"
        completion_ledger.parent.mkdir(parents=True, exist_ok=True)
        completion_ledger.write_text("", encoding="utf-8")

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
        atomic_write_json(wf74_router, {"status": "ok", "validation": {"status": "ok"}, "pm_job_candidates": []})

        original = {
            "DEFAULT_CONTROL_PACKET": queue.DEFAULT_CONTROL_PACKET,
            "DEFAULT_PM_STATE": queue.DEFAULT_PM_STATE,
            "DEFAULT_PM_ACTIONS": queue.DEFAULT_PM_ACTIONS,
            "DEFAULT_CRON_CANDIDATES": queue.DEFAULT_CRON_CANDIDATES,
            "DEFAULT_HELPER_PACKETS": queue.DEFAULT_HELPER_PACKETS,
            "DEFAULT_WF74_ROUTER": queue.DEFAULT_WF74_ROUTER,
            "DEFAULT_COMPLETION_LEDGER": queue.DEFAULT_COMPLETION_LEDGER,
        }
        try:
            queue.DEFAULT_CONTROL_PACKET = control
            queue.DEFAULT_PM_STATE = pm_state
            queue.DEFAULT_PM_ACTIONS = pm_actions
            queue.DEFAULT_CRON_CANDIDATES = cron_candidates
            queue.DEFAULT_HELPER_PACKETS = helper_packets
            queue.DEFAULT_WF74_ROUTER = wf74_router
            queue.DEFAULT_COMPLETION_LEDGER = completion_ledger
            args = type("Args", (), {
                "pm_state": str(pm_state),
                "pm_actions": str(pm_actions),
                "cron_candidates": str(cron_candidates),
                "helper_packets": str(helper_packets),
                "wf74_router": str(wf74_router),
                "max_pm_jobs": 10,
                "max_cron_jobs": 4,
                "max_wf74_jobs": 8,
            })()
            payload = queue.build_payload(args)

            atomic_write_json(control, {
                "schema": "test.pm_control_packet",
                "status": "ok",
                "sections": {"pm_program_state": {"status": "ok", "next_actions": []}},
            })
            atomic_write_json(wf74_router, {
                "status": "ok",
                "validation": {"status": "ok"},
                "kpis": {
                    "recommendation_to_route_conversion_rate": 1.0,
                    "route_to_pm_job_conversion_rate": 1.0,
                    "high_priority_overdue_count": 2,
                    "planning_followthrough_clean_rate": 0.5,
                },
                "pm_job_candidates": [
                    {
                        "job_id": "pm-wf74-cron-migration-repair-plan",
                        "priority": "P1",
                        "status": "ready_for_main_or_helper",
                        "source_key": "cron_migration-test",
                        "source_category": "cron_migration",
                        "lane_id": "cron_repair_plan",
                        "title": "Route blocked cron signals into a migration-ready repair plan",
                        "objective": "Build a dry-run cron migration repair plan.",
                        "implementation_class": "wf74_cron_migration_repair_plan",
                        "owner_surface": "WF74 improvement ledger + cron control packet",
                        "target_files": ["tmp/wf74-autonomy-work-router.json"],
                        "collision_group": "wf74_cron_repair_plan",
                        "proof_commands": [
                            "python scripts\\cron_control_packet.py --write --validate",
                            "python scripts\\wf74_autonomy_work_router.py --write --validate",
                        ],
                        "acceptance_criteria": ["route is visible in PM queue"],
                        "helper_role": "WF74 cron follow-through helper",
                        "stop_lines": ["no cron schedule mutation"],
                    }
                ],
            })
            router_payload = queue.build_payload(type("Args", (), {
                "pm_state": str(pm_state),
                "pm_actions": str(pm_actions),
                "cron_candidates": str(cron_candidates),
                "helper_packets": str(helper_packets),
                "wf74_router": str(wf74_router),
                "max_pm_jobs": 0,
                "max_cron_jobs": 0,
                "max_wf74_jobs": 8,
            })())
        finally:
            for key, value in original.items():
                setattr(queue, key, value)

        assert payload["status"] == "ok", payload
        assert payload["summary"]["blocked_job_count"] == 0, payload["summary"]
        assert payload["summary"]["top_job_id"] == "pm-trade-grade-decision-os-execute-safe-next-step", payload["summary"]
        assert payload["source_status"]["pm_next_actions_effective_source"].endswith(
            "#sections.pm_program_state.next_actions"
        ), payload["source_status"]
        assert router_payload["status"] == "ok", router_payload
        assert router_payload["summary"]["wf74_router_job_count"] == 1, router_payload["summary"]
        assert router_payload["summary"]["top_job_id"] == "pm-wf74-cron-migration-repair-plan", router_payload["summary"]
        assert router_payload["jobs"][0]["source"] == "wf74_autonomy_work_router", router_payload["jobs"][0]

    print("pm_implementation_job_queue control-packet preference: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
