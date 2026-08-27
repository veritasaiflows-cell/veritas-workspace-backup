#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "heartbeat_continuation_candidates.py"


def load_module():
    spec = importlib.util.spec_from_file_location("heartbeat_continuation_candidates", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def minimal_payload(module) -> dict:
    return {
        "heartbeat_authority": {
            "may_directly_advance_workflow_queue": False,
            "may_run_major_phase_work": False,
            "may_mutate_canon_or_portfolio": False,
            "may_import_sql_or_tickers": False,
            "may_change_config_auth_channel_runtime": False,
            "may_move_delete_archive": False,
            "may_take_paper_live_or_account_action": False,
            "may_infer_owner_approval": False,
            "may_queue_bounded_main_session_handoff": True,
        },
        "candidates": [
            {
                "workflow_id": "WF75",
                "status": "handoff_ready",
                "inline_execution_allowed": False,
                "may_spawn_helper_from_heartbeat": False,
                "authority_violations": [],
                "goal_alignment": ["Retail Investor Finance Intelligence SaaS P0 continuity"],
            }
        ],
    }


def test_heartbeat_action_bridge_never_requests_execute_safe() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        out = root / "tmp" / "heartbeat-main-session-action-executor.json"

        def fake_run(command, cwd, text, capture_output, timeout):
            write_json(
                out,
                {
                    "status": "warning",
                    "mode": "dry_run",
                    "context": "heartbeat",
                    "validation": {"status": "ok", "warnings": ["main_handoff_action_present"]},
                    "summary": {
                        "action_type": "prepare_helper_lane",
                        "classification": "main_handoff",
                        "selected_pm_job": {"job_id": "pm-10-wf78-source-artifact-capture"},
                        "executed": False,
                        "next_safe_action": "Main session may spawn the helper using helper_packet.",
                    },
                    "action": {"classification": "main_handoff"},
                    "execution_results": [],
                },
            )

            class Proc:
                returncode = 0
                stdout = "wrote tmp/heartbeat-main-session-action-executor.json"
                stderr = ""

            assert "--execute-safe" not in command
            return Proc()

        module.subprocess.run = fake_run
        bridge = module.run_heartbeat_main_session_action_bridge(out)
        assert bridge["ok"] is True
        assert bridge["context"] == "heartbeat"
        assert bridge["mode"] == "dry_run"
        assert bridge["classification"] == "main_handoff"
        assert bridge["executed"] is False
        assert bridge["execution_results_count"] == 0
        assert "--execute-safe" not in " ".join(str(part) for part in bridge["command"])
        assert "--out tmp/heartbeat-main-session-action-executor.json" in " ".join(str(part) for part in bridge["command"])


def test_validate_rejects_heartbeat_action_bridge_execution() -> None:
    module = load_module()
    payload = minimal_payload(module)
    payload["main_session_action_bridge"] = {
        "ok": True,
        "command": ["python", "scripts\\main_session_action_executor.py", "--context", "heartbeat", "--execute-safe"],
        "context": "heartbeat",
        "mode": "execute_safe",
        "classification": "auto_execute",
        "executed": True,
        "execution_results_count": 1,
        "heartbeat_boundary": {
            "may_wake_main_session": True,
            "may_execute_inline": True,
            "may_pass_execute_safe": True,
        },
    }
    validation = module.validate_payload(payload)
    assert validation["status"] == "error"
    assert "main_session_action_bridge_requested_execute_safe" in validation["errors"]
    assert "main_session_action_bridge_auto_execute_forbidden" in validation["errors"]
    assert "main_session_action_bridge_executed" in validation["errors"]


def test_load_pm_context_prefers_control_packet_sections() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        control = root / "tmp" / "pm-control-packet.json"
        write_json(
            control,
            {
                "schema": "veritas.pm_control_packet.v1",
                "sections": {
                    "pm_program_state": {
                        "schema": "veritas.pm_program_state.v1",
                        "status": "ok",
                        "generated_at_utc": "2026-06-21T03:25:00Z",
                        "readiness": {"stale_lanes": 0},
                        "next_actions": [{"action_id": "fresh-action"}],
                    },
                    "pm_implementation_job_queue": {
                        "schema": "veritas.pm_implementation_job_queue.v1",
                        "summary": {"ready_job_count": 1},
                    },
                },
            },
        )

        context = module.load_pm_context(control)
        assert context["pm_state"]["readiness"]["stale_lanes"] == 0
        assert context["actions_payload"]["next_actions"][0]["action_id"] == "fresh-action"
        assert context["implementation_queue"]["summary"]["ready_job_count"] == 1
        assert context["source_label"].endswith("tmp/pm-control-packet.json#sections.pm_program_state")
