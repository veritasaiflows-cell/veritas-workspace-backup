#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pm_autonomy_dispatcher as dispatcher
from pm_autonomy_policy import DEFAULT_POLICY


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def job(job_id: str, priority: str, source_score: int, auto_cron: bool, rank: int = 1, auto_main: bool | None = None) -> dict:
    auto_main = auto_cron if auto_main is None else auto_main
    return {
        "job_id": job_id,
        "rank": rank,
        "priority": priority,
        "source_priority_score": source_score,
        "status": "ready_for_main_or_helper",
        "title": job_id,
        "implementation_class": "wf74_workflow_followup_routing",
        "collision_group": job_id,
        "readiness_score": 80,
        "proof_commands": ["python scripts\\pm_control_packet.py --write --write-db --validate"],
        "automation_capabilities": {
            "auto_cron_may_execute": auto_cron,
            "auto_main_may_execute": auto_main,
            "auto_lane_prepare_allowed": True,
            "helper_lane_allowed": True,
            "owner_gate_required": False,
            "unsafe_proof_commands": [],
        },
    }


def test_dispatcher_prefers_proof_refresh_and_source_priority() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        policy = root / "policy.json"
        queue = root / "queue.json"
        register = root / "register.json"
        out = root / "out.json"
        inbox = root / "inbox.json"
        write_json(policy, DEFAULT_POLICY)
        write_json(register, {"lanes": []})
        write_json(queue, {
            "jobs": [
                job("lower", "P1", 80, True, rank=1),
                job("higher", "P1", 95, True, rank=2),
                job("plan-only", "P1", 99, False, rank=3),
            ]
        })
        args = argparse.Namespace(
            policy=policy,
            queue=queue,
            lane_register=register,
            out=out,
            inbox=inbox,
            dry_run=False,
            execution_context="cron",
        )
        report = dispatcher.build_report(args)
        assert report["status"] == "ok", report
        assert report["summary"]["selected_job_id"] == "higher", report["summary"]
        assert report["summary"]["selected_action_type"] == "run_proof_refresh", report["summary"]
        dispatcher.atomic_write_json(out, report)
        dispatcher.atomic_write_json(inbox, dispatcher.build_inbox(report))
        assert json.loads(inbox.read_text(encoding="utf-8"))["top_pending_job_id"] == "higher"


def test_dispatcher_blocks_active_collision_group() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        policy = root / "policy.json"
        queue = root / "queue.json"
        register = root / "register.json"
        write_json(policy, DEFAULT_POLICY)
        write_json(register, {"lanes": [{"status": "running", "workstream_id": "busy"}]})
        busy = job("busy", "P1", 99, True)
        busy["collision_group"] = "busy"
        write_json(queue, {"jobs": [busy]})
        args = argparse.Namespace(policy=policy, queue=queue, lane_register=register, out=root / "out.json", inbox=root / "inbox.json", dry_run=False, execution_context="cron")
        report = dispatcher.build_report(args)
        assert report["status"] == "quiet_success", report
        assert report["summary"]["selected_action_type"] == "no_action", report["summary"]
        assert report["validation"]["warnings"] == []
        assert "no_unattended_safe_job" in report["validation"]["info"]


def test_main_context_can_run_main_only_proof_refresh_but_cron_cannot() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        policy = root / "policy.json"
        queue = root / "queue.json"
        register = root / "register.json"
        write_json(policy, DEFAULT_POLICY)
        write_json(register, {"lanes": []})
        write_json(queue, {"jobs": [job("main-only", "P1", 90, False, auto_main=True)]})

        cron_report = dispatcher.build_report(argparse.Namespace(
            policy=policy,
            queue=queue,
            lane_register=register,
            out=root / "cron.json",
            inbox=root / "cron-inbox.json",
            dry_run=False,
            execution_context="cron",
        ))
        assert cron_report["summary"]["selected_action_type"] == "prepare_implementation_plan", cron_report["summary"]

        main_report = dispatcher.build_report(argparse.Namespace(
            policy=policy,
            queue=queue,
            lane_register=register,
            out=root / "main.json",
            inbox=root / "main-inbox.json",
            dry_run=False,
            execution_context="main",
        ))
        assert main_report["status"] == "ok", main_report
        assert main_report["summary"]["selected_action_type"] == "run_proof_refresh", main_report["summary"]
        assert main_report["action"]["execution_context"] == "main"


def main() -> int:
    test_dispatcher_prefers_proof_refresh_and_source_priority()
    test_dispatcher_blocks_active_collision_group()
    test_main_context_can_run_main_only_proof_refresh_but_cron_cannot()
    print("pm_autonomy_dispatcher_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
