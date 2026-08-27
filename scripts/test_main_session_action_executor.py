#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "main_session_action_executor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("main_session_action_executor", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def configure_paths(module, root: Path) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "main-session-action-executor.json"
    module.HEARTBEAT_OUT = module.TMP / "heartbeat-main-session-action-executor.json"
    module.LEDGER = root / "state" / "main-session-action-executor-ledger.jsonl"
    module.CRON_CONTROL = module.TMP / "cron-control-packet.json"
    module.ESCALATION_CONSUMER = module.TMP / "main-session-escalation-consumer.json"
    module.GREENKEEPER = module.TMP / "main-session-greenkeeper-controller.json"
    module.PM_CONTROL = module.TMP / "pm-control-packet.json"
    module.PARALLEL_RECOMMENDATION = module.TMP / "parallel-lane-recommendation.json"
    module.PM_EXECUTION_LOOP = module.TMP / "pm-execution-loop.json"
    module.LANE_REGISTER = module.TMP / "concurrent-lane-register.json"
    module.HANDOFF_FIRST_PROOF = module.TMP / "main-session-handoff-first-proof.json"
    module.PRIORITY_HANDOFF = module.TMP / "main-session-priority-handoff.json"


def base_job() -> dict:
    return {
        "job_id": "pm-01-trade-grade-decision-os-execute-safe-next-step",
        "rank": 1,
        "status": "ready_for_main_or_helper",
        "title": "Advance WF85 Personal Trade-Grade Decision OS",
        "implementation_class": "trade_grade_decision_os",
        "collision_group": "trade_grade_decision_os",
        "readiness_score": 90,
        "target_files": ["scripts/trade_grade_decision_os_contract.py"],
        "proof_commands": ["python scripts\\trade_grade_decision_os_contract.py --write --validate"],
        "validation_budget": {"budget": "narrow"},
        "closeout_mode": "pm_state",
        "helper_packet": {"packet_id": "pm-01-helper"},
        "automation_capabilities": {
            "proof_only": True,
            "artifact_refresh": True,
            "bounded_patch_allowed": False,
            "helper_lane_allowed": True,
            "owner_gate_required": False,
            "auto_main_may_execute": True,
            "auto_cron_may_execute": True,
            "auto_heartbeat_may_execute": False,
            "auto_lane_prepare_allowed": True,
            "auto_helper_spawn_allowed": False,
            "unsafe_proof_commands": [],
        },
    }


def priority_item(module, priority_id: str, priority: str, urgency_rank: int = 0) -> dict:
    return {
        "priority_id": priority_id,
        "priority": priority,
        "urgency_rank": urgency_rank,
        "category": "test_priority",
        "owner": "main_session_test_owner",
        "due_window": "immediate" if priority == "P0" else "next_main_session",
        "next_action": f"Review {priority_id} before generic PM work.",
        "acceptance_proof": {"artifact": "tmp/test-priority-proof.json", "required_state": "clean"},
        "authority_boundary": module.PRIORITY_AUTHORITY_BOUNDARY,
        "disposition": {"status": "pending"},
    }


def write_priority_handoff(module, selected: dict, items: list[dict] | None = None, *, boundary: dict | None = None) -> None:
    write_json(module.PRIORITY_HANDOFF, {
        "status": "needs_main_review",
        "receipt": "NEW_PRIORITY",
        "validation": {"status": "ok"},
        "authority_boundary": boundary if boundary is not None else module.PRIORITY_AUTHORITY_BOUNDARY,
        "selected_item": selected,
        "items": items if items is not None else [selected],
    })


def write_surfaces(module, root: Path, job: dict | None = None) -> None:
    job = job or base_job()
    write_json(module.CRON_CONTROL, {"status": "ok", "summary": {"blocked_count": 0}})
    write_json(module.ESCALATION_CONSUMER, {
        "status": "ok",
        "summary": {
            "executed_safe_action_count": 0,
            "unresolved_count": 0,
            "next_safe_action": "No cron escalation signals to consume.",
        },
    })
    write_json(module.GREENKEEPER, {"status": "ok", "summary": {"action_counts": {}}})
    write_json(module.PM_CONTROL, {
        "status": "ok",
        "sections": {
            "pm_implementation_job_queue": {
                "status": "ok",
                "jobs": [job],
                "summary": {"job_count": 1},
            }
        },
    })
    write_json(module.PARALLEL_RECOMMENDATION, {
        "status": "ok",
        "summary": {"eligible_candidate_count": 0},
        "candidates": [],
    })
    write_json(module.LANE_REGISTER, {
        "status": "ok",
        "summary": {"active_lane_count": 0},
        "lanes": [],
        "validation": {"status": "ok"},
    })
    write_json(module.PM_EXECUTION_LOOP, {"status": "ok", "summary": {}})
    write_json(module.HANDOFF_FIRST_PROOF, {
        "status": "ok",
        "summary": {"needs_repair_count": 0},
        "repair_lane_packet": {"target_lanes": []},
    })
    write_json(module.PRIORITY_HANDOFF, {
        "status": "no_priority",
        "validation": {"status": "ok"},
    })


def write_parallel_candidate(module) -> None:
    write_json(module.PARALLEL_RECOMMENDATION, {
        "status": "ok",
        "lease_command": "python scripts\\concurrent_lane_manager.py --lease WF75 --workstream pm-10 --write --validate",
        "summary": {"eligible_candidate_count": 1},
        "recommendation": {
            "top_candidate": {
                "workflow_id": "WF75",
                "workstream_id": "pm-10",
                "title": "Run WF75 slice",
                "pm_job_id": "pm-10-wf75",
                "from_pm_job": True,
            }
        },
        "ranked_candidates": [],
    })


def args(context: str) -> SimpleNamespace:
    return SimpleNamespace(
        refresh_frontdoors=False,
        execute_safe=False,
        append_ledger=False,
        context=context,
        ledger=Path("unused-ledger.jsonl"),
    )


def test_main_context_selects_proof_execution() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        run_args = args("main_session")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["action"]["action_type"] == "execute_pm_proof"
        assert report["summary"]["selected_pm_job"]["job_id"] == "pm-01-trade-grade-decision-os-execute-safe-next-step"
        assert report["summary"]["executed"] is False


def test_heartbeat_context_never_executes_phase() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        run_args = args("heartbeat")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["action"]["action_type"] in {"prepare_helper_lane", "no_action"}
        assert report["summary"]["executed"] is False


def test_priority_handoff_precedes_generic_pm_work() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        p0 = priority_item(module, "current-window:test", "P0")
        p1 = priority_item(module, "ticker:test", "P1", 40)
        write_priority_handoff(module, p0, [p0, p1])
        run_args = args("main_session")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["action"]["action_type"] == "review_priority_handoff"
        assert report["summary"]["selected_priority_level"] == "P0"
        assert report["summary"]["selected_pm_job"] == {}
        assert report["summary"]["executed"] is False


def test_heartbeat_execute_safe_is_blocked_and_direct_execution_fails_closed() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        run_args = args("heartbeat")
        run_args.execute_safe = True
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "blocked"
        assert "heartbeat_execute_safe_requested" in report["validation"]["errors"]
        assert report["execution_results"] == []

        direct = {
            "action_type": "execute_pm_proof",
            "selected_pm_job": {"job_id": "must-not-run"},
        }
        assert module.execute_action(direct, run_args) == []

        writes: list[Path] = []
        original_atomic_write = module.atomic_write_json
        original_argv = sys.argv
        module.atomic_write_json = lambda path, payload: writes.append(path)
        sys.argv = [str(SCRIPT), "--context", "heartbeat", "--execute-safe", "--write"]
        try:
            assert module.main() == 2
            assert writes == []
        finally:
            module.atomic_write_json = original_atomic_write
            sys.argv = original_argv

        writes = []
        module.atomic_write_json = lambda path, payload: writes.append(path)
        sys.argv = [str(SCRIPT), "--context", "heartbeat", "--write", "--validate"]
        try:
            assert module.main() == 2
            assert writes == []
        finally:
            module.atomic_write_json = original_atomic_write
            sys.argv = original_argv

        writes = []
        module.atomic_write_json = lambda path, payload: writes.append(path)
        sys.argv = [
            str(SCRIPT), "--context", "heartbeat", "--write", "--validate",
            "--out", str(module.HEARTBEAT_OUT),
        ]
        try:
            assert module.main() == 0
            assert writes == [module.HEARTBEAT_OUT]
        finally:
            module.atomic_write_json = original_atomic_write
            sys.argv = original_argv


def test_p2_priority_is_monitor_only_and_does_not_starve_generic_pm_work() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        p2 = priority_item(module, "tier-c:test", "P2", 90)
        p2["due_window"] = "scheduled_monitoring"
        write_priority_handoff(module, p2, [p2])
        run_args = args("main_session")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["action"]["action_type"] == "execute_pm_proof"
        assert report["summary"]["selected_pm_job"]["job_id"] == "pm-01-trade-grade-decision-os-execute-safe-next-step"


def test_tampered_priority_authority_and_selection_are_blocked() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        p0 = priority_item(module, "p0", "P0")
        p1 = priority_item(module, "p1", "P1", 40)
        tampered_boundary = dict(module.PRIORITY_AUTHORITY_BOUNDARY)
        tampered_boundary["review_only"] = False
        p0["authority_boundary"] = tampered_boundary
        write_priority_handoff(module, p0, [p0, p1], boundary=tampered_boundary)
        run_args = args("main_session")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "blocked"
        assert "priority_handoff_invalid" in report["validation"]["errors"]

        p0 = priority_item(module, "p0", "P0")
        p1 = priority_item(module, "p1", "P1", 40)
        write_priority_handoff(module, p1, [p0, p1])
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "blocked"
        assert "priority_handoff_selected_item_not_highest_unresolved" in report["validation"]["errors"]


def test_parallel_candidate_handoff_is_actionable() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        job = base_job()
        job["automation_capabilities"]["auto_main_may_execute"] = False
        job["automation_capabilities"]["auto_cron_may_execute"] = False
        write_surfaces(module, root, job)
        write_parallel_candidate(module)
        run_args = args("main_session")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["action"]["action_type"] == "prepare_parallel_helper_lane"
        assert report["summary"]["parallel_helper_workstream"] == "pm-10"
        assert report["summary"]["next_safe_action"].startswith("Run the parallel lane recommender lease_command")


def test_handoff_first_proof_repair_packet_takes_next_safe_action_priority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        job = base_job()
        job["automation_capabilities"]["auto_main_may_execute"] = False
        job["automation_capabilities"]["auto_cron_may_execute"] = False
        write_surfaces(module, root, job)
        write_parallel_candidate(module)
        write_json(module.HANDOFF_FIRST_PROOF, {
            "status": "warning",
            "summary": {"needs_repair_count": 2},
            "repair_lane_packet": {"target_lanes": ["morning", "post_close"]},
        })
        run_args = args("main_session")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["action"]["action_type"] == "prepare_parallel_helper_lane"
        assert report["summary"]["handoff_first_proof_needs_repair_count"] == 2
        assert report["summary"]["next_safe_action"].startswith("Use tmp/main-session-handoff-first-proof.json")


def test_heartbeat_refresh_frontdoors_does_not_request_execute_safe() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        seen_commands: list[list[str]] = []

        def fake_run_step(name, command, timeout):
            seen_commands.append(command)
            return {"name": name, "command": command, "ok": True, "returncode": 0}

        module.run_step = fake_run_step
        run_args = args("heartbeat")
        run_args.refresh_frontdoors = True
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        flattened = [" ".join(command) for command in seen_commands]
        heartbeat_commands = [
            command for command in flattened
            if "main_session_escalation_consumer.py" in command
            or "main_session_greenkeeper_controller.py" in command
        ]
        assert heartbeat_commands
        assert all("--execute-safe" not in command for command in heartbeat_commands)


def test_refresh_frontdoors_without_execute_safe_is_dry_run() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        write_surfaces(module, root)
        seen_commands: list[list[str]] = []

        def fake_run_step(name, command, timeout):
            seen_commands.append(command)
            return {"name": name, "command": command, "ok": True, "returncode": 0}

        module.run_step = fake_run_step
        run_args = args("main_session")
        run_args.refresh_frontdoors = True
        run_args.execute_safe = False
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        flattened = [" ".join(command) for command in seen_commands]
        consumer_or_greenkeeper = [
            command for command in flattened
            if "main_session_escalation_consumer.py" in command
            or "main_session_greenkeeper_controller.py" in command
        ]
        assert consumer_or_greenkeeper
        assert all("--execute-safe" not in command for command in consumer_or_greenkeeper)


def test_closeout_uses_cron_execution_eligibility() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_paths(module, root)
        main_only = base_job()
        main_only["job_id"] = "main-only"
        main_only["rank"] = 1
        main_only["automation_capabilities"]["auto_main_may_execute"] = True
        main_only["automation_capabilities"]["auto_cron_may_execute"] = False
        cron_safe = base_job()
        cron_safe["job_id"] = "cron-safe"
        cron_safe["rank"] = 2
        cron_safe["automation_capabilities"]["auto_main_may_execute"] = True
        cron_safe["automation_capabilities"]["auto_cron_may_execute"] = True
        write_surfaces(module, root, main_only)
        pm = json.loads(module.PM_CONTROL.read_text(encoding="utf-8"))
        pm["sections"]["pm_implementation_job_queue"]["jobs"].append(cron_safe)
        write_json(module.PM_CONTROL, pm)
        run_args = args("closeout")
        run_args.ledger = module.LEDGER
        report = module.build_report(run_args)
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["selected_pm_job"]["job_id"] == "cron-safe"


def main() -> int:
    test_main_context_selects_proof_execution()
    test_heartbeat_context_never_executes_phase()
    test_priority_handoff_precedes_generic_pm_work()
    test_heartbeat_execute_safe_is_blocked_and_direct_execution_fails_closed()
    test_p2_priority_is_monitor_only_and_does_not_starve_generic_pm_work()
    test_tampered_priority_authority_and_selection_are_blocked()
    test_parallel_candidate_handoff_is_actionable()
    test_handoff_first_proof_repair_packet_takes_next_safe_action_priority()
    test_heartbeat_refresh_frontdoors_does_not_request_execute_safe()
    test_refresh_frontdoors_without_execute_safe_is_dry_run()
    test_closeout_uses_cron_execution_eligibility()
    print("main_session_action_executor tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
