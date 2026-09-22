#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "main_session_escalation_consumer.py"


def load_module():
    spec = importlib.util.spec_from_file_location("main_session_escalation_consumer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def configure_paths(module, root: Path) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "main-session-escalation-consumer.json"
    module.LEDGER = root / "state" / "main-session-escalation-action-ledger.jsonl"
    module.PRIORITY_OUT = module.TMP / "main-session-priority-handoff.json"
    module.HEARTBEAT_OUT = module.TMP / "heartbeat-main-session-escalation-consumer.json"
    module.HEARTBEAT_PRIORITY_OUT = module.TMP / "heartbeat-main-session-priority-handoff.json"
    module.PRIORITY_DISPOSITION_LEDGER = root / "state" / "main-session-priority-disposition-ledger.jsonl"
    module.CRON_CONTROL = module.TMP / "cron-control-packet.json"
    module.CURRENT_WINDOW_ARTIFACTS = module.TMP / "current-window-artifacts.json"


def args(module, *, context: str = "main_session", execute_safe: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        write=False,
        validate=True,
        refresh_frontdoors=False,
        execute_safe=execute_safe,
        append_ledger=False,
        context=context,
        max_actions=8,
        repeat_threshold=2,
        out=module.OUT,
        ledger=module.LEDGER,
        priority_out=module.PRIORITY_OUT,
        priority_disposition_ledger=module.PRIORITY_DISPOSITION_LEDGER,
        max_priority_items=25,
        priority_id=None,
        priority_disposition=None,
        priority_note=None,
        priority_proof=None,
        priority_observation_source=None,
    )


def cron_packet(*signals: dict) -> dict:
    return {
        "status": "ok",
        "summary": {
            "should_wake_main_session": bool(signals),
            "escalation_signal_count": len(signals),
        },
        "escalation": {
            "should_wake_main_session": bool(signals),
            "escalation_signal_count": len(signals),
            "escalation_signals": list(signals),
        },
    }


def active_chain_signal(window: str = "morning") -> dict:
    return {
        "source": f"cron_job:Finance - {window} Alerts and Recommendations Refresh",
        "signal_class": "BLOCKED",
        "status": "blocked",
        "reason": "artifact_blocked_or_authority_widened",
        "artifact": f"tmp/alerts-recommendations-chain-{window}.json",
    }


def generic_runtime_signal() -> dict:
    return {
        "source": "cron_job:Runtime - Proof Refresh",
        "signal_class": "BLOCKED",
        "status": "scheduler_error",
        "reason": "enabled_job_repeated_scheduler_failures",
        "artifact": "tmp/runtime-proof.json",
    }


def test_alert_chain_blocker_maps_to_safe_refresh() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        signal = active_chain_signal()
        write_json(module.CRON_CONTROL, cron_packet(signal))
        write_json(module.ROOT / signal["artifact"], {"status": "critical", "authority": {"review_only": True}})
        report = module.build_report(args(module))
        action = report["actions"][0]
        assert report["validation"]["status"] == "ok"
        assert action["handler_id"] == "alerts_chain_morning_refresh"
        assert action["classification"] == "auto_repair"
        assert "alerts_chain_morning" in action["commands"]


def test_tmp_cleanup_signal_maps_to_protected_dry_run_refresh() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        signal = {
            "source": "cron_job:Runtime - Sunday Generated Artifact Cleanup Dry Run",
            "signal_class": "BLOCKED",
            "status": "blocked",
            "reason": "artifact_blocked_or_authority_widened",
            "artifact": "tmp/tmp-cleanup-report.json",
        }
        write_json(module.CRON_CONTROL, cron_packet(signal))
        write_json(module.ROOT / signal["artifact"], {"status": "ok", "authority": {"review_only": True}})
        report = module.build_report(args(module))
        action = report["actions"][0]
        assert action["handler_id"] == "tmp_cleanup_dry_run_refresh"
        assert action["classification"] == "auto_refresh"
        assert action["commands"][0] == "tmp_cleanup_dry_run"
        command, _timeout = module.COMMANDS["tmp_cleanup_dry_run"]
        assert "--dry-run" in command
        assert "--apply" not in command
        assert module.command_is_allowed(command)


def test_retired_routes_have_no_affirmative_command_handler_or_signal_surface() -> None:
    module = load_module()
    rendered_commands = json.dumps({key: value[0] for key, value in module.COMMANDS.items()}).lower()
    rendered_handlers = json.dumps(module.HANDLERS).lower()
    retired = (
        "weekday_morning_review_cron_runner.py",
        "post_close_review_cron_runner.py",
        "run_finance_refresh_chain.py",
        "wf76",
        "wf86",
        "shadow_reconciliation",
    )
    assert not any(token in rendered_commands for token in retired)
    assert not any(token in rendered_handlers for token in retired)
    assert all(module.command_is_allowed(list(spec[0])) for spec in module.COMMANDS.values())

    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        retired_signal = {
            "source": "cron_job:WF86 shadow reconciliation",
            "signal_class": "BLOCKED",
            "status": "blocked",
            "reason": "wf86_shadow_reconciliation_blocked",
            "artifact": "tmp/paper-autotrader/wf86-shadow-reconciliation.json",
        }
        write_json(module.CRON_CONTROL, cron_packet(retired_signal))
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {
                "current_usable": False,
                "critical_or_unreadable_roles": ["capital_deployment_recommendation_validation"],
            },
        })
        report = module.build_report(args(module))
        assert report["actions"] == []
        assert report["summary"]["retired_signal_suppressed_count"] == 1
        assert report["summary"]["retired_priority_source_suppressed"] is True
        assert report["main_session_priority_handoff"]["selected_item"] == {}
        assert "wf86" not in json.dumps(report).lower()


def test_authority_widening_becomes_owner_decision() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        signal = {
            "source": "cron_job:Runtime - Bad Proof",
            "signal_class": "BLOCKED",
            "status": "blocked",
            "reason": "authority_widened",
            "artifact": "tmp/bad.json",
        }
        write_json(module.CRON_CONTROL, cron_packet(signal))
        write_json(module.ROOT / signal["artifact"], {"authority": {"paper_submit_allowed": True}})
        report = module.build_report(args(module))
        action = report["actions"][0]
        assert action["classification"] == "owner_decision"
        assert action["commands"] == []
        assert action["owner_gate_required"] is True


def test_heartbeat_never_executes_and_rejects_execute_safe() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        signal = active_chain_signal("post-close")
        write_json(module.CRON_CONTROL, cron_packet(signal))
        write_json(module.ROOT / signal["artifact"], {"status": "critical", "authority": {"review_only": True}})
        report = module.build_report(args(module, context="heartbeat", execute_safe=True))
        assert report["validation"]["status"] == "blocked"
        assert "heartbeat_execute_safe_requested" in report["validation"]["errors"]
        assert report["execution_results"] == []


def test_repeated_signal_is_marked_for_residue() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        signal = active_chain_signal()
        fp = module.fingerprint(signal)
        module.LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.LEDGER.write_text(json.dumps({"actions": [{"fingerprint": fp}]}) + "\n", encoding="utf-8")
        write_json(module.CRON_CONTROL, cron_packet(signal))
        write_json(module.ROOT / signal["artifact"], {"status": "critical", "authority": {"review_only": True}})
        report = module.build_report(args(module))
        assert report["actions"][0]["repeat_count"] == 2
        assert report["actions"][0]["repeated_blocker"] is True
        assert "repeated_blocker_present" in report["validation"]["warnings"]


def test_priority_handoff_ranks_current_window_before_generic_cron_repair() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_json(module.CRON_CONTROL, cron_packet(generic_runtime_signal()))
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {"current_usable": False, "window_completion_state": "missed_after_deadline"},
        })
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_observation_source = "heartbeat"
        first = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        assert first["receipt"] == "NEW_PRIORITY"
        assert first["selected_item"]["priority"] == "P0"
        assert first["selected_item"]["category"] == "current_window_unusable"
        assert first["summary"]["priority_counts"] == {"P0": 1, "P1": 1, "P2": 0}
        write_json(module.PRIORITY_OUT, first)
        second = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        assert second["receipt"] == "NO_DELTA"
        assert second["selected_item"]["repeat_count"] == 2


def test_priority_disposition_requires_main_and_clean_closure_proof() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {"current_usable": False, "window_completion_state": "missed_after_deadline"},
        })
        handoff = module.build_report(args(module))["main_session_priority_handoff"]
        priority_id = handoff["selected_item"]["priority_id"]
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_id = priority_id
        heartbeat_args.priority_disposition = "accepted"
        assert module.record_priority_disposition(heartbeat_args, handoff)["error"] == "priority_disposition_requires_main_context"

        main_args = args(module)
        main_args.priority_id = priority_id
        main_args.priority_disposition = "closed"
        main_args.priority_proof = str(module.CURRENT_WINDOW_ARTIFACTS.relative_to(module.ROOT))
        assert module.record_priority_disposition(main_args, handoff)["error"] == "current_window_not_usable"
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "ok",
            "summary": {"current_usable": True, "window_completion_state": "completed"},
            "validation": {"status": "ok"},
        })
        assert module.record_priority_disposition(main_args, handoff)["status"] == "ok"


def test_priority_lifecycle_deduplicates_and_reescalates() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        signal = generic_runtime_signal()
        write_json(module.CRON_CONTROL, cron_packet(signal, dict(signal)))
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_observation_source = "heartbeat"
        first = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        assert first["summary"]["duplicate_candidate_count"] == 1
        assert first["selected_item"]["priority"] == "P1"
        selected_id = first["selected_item"]["priority_id"]
        first["items"][0]["repeat_count"] = 7
        first["state_index"][selected_id]["repeat_count"] = 7
        write_json(module.PRIORITY_OUT, first)
        aged = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        assert aged["selected_item"]["repeat_count"] == 8
        assert aged["receipt"] == "ESCALATED_PRIORITY"


def test_main_session_pickup_does_not_age_heartbeat_repeat_counter() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        write_json(module.CURRENT_WINDOW_ARTIFACTS, {
            "status": "warning",
            "summary": {"current_usable": False, "window_completion_state": "missed_after_deadline"},
        })
        heartbeat_args = args(module, context="heartbeat")
        heartbeat_args.priority_observation_source = "heartbeat"
        first = module.build_report(heartbeat_args)["main_session_priority_handoff"]
        selected_id = first["selected_item"]["priority_id"]
        first["items"][0]["repeat_count"] = 4
        first["state_index"][selected_id]["repeat_count"] = 4
        write_json(module.PRIORITY_OUT, first)
        pickup_args = args(module, context="main_session")
        pickup_args.priority_observation_source = "main_session"
        pickup = module.build_report(pickup_args)["main_session_priority_handoff"]
        assert pickup["state_index"][selected_id]["repeat_count"] == 4
        assert pickup["observation"]["priority_repeat_age_advanced"] is False


def test_forbidden_heartbeat_arguments_fail_before_writes() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_paths(module, Path(tmpdir))
        old_argv = sys.argv
        try:
            sys.argv = [
                str(SCRIPT), "--context", "heartbeat", "--write", "--append-ledger",
                "--out", str(module.OUT), "--ledger", str(module.LEDGER),
            ]
            assert module.main() == 2
            assert not module.OUT.exists()
            assert not module.LEDGER.exists()

            sys.argv = [
                str(SCRIPT), "--context", "heartbeat", "--write", "--validate",
                "--out", str(module.HEARTBEAT_OUT),
                "--priority-out", str(module.HEARTBEAT_PRIORITY_OUT),
                "--priority-observation-source", "heartbeat",
            ]
            assert module.main() == 0
            assert module.HEARTBEAT_OUT.exists()
            assert module.HEARTBEAT_PRIORITY_OUT.exists()
        finally:
            sys.argv = old_argv


def main() -> int:
    test_alert_chain_blocker_maps_to_safe_refresh()
    test_retired_routes_have_no_affirmative_command_handler_or_signal_surface()
    test_authority_widening_becomes_owner_decision()
    test_heartbeat_never_executes_and_rejects_execute_safe()
    test_repeated_signal_is_marked_for_residue()
    test_priority_handoff_ranks_current_window_before_generic_cron_repair()
    test_priority_disposition_requires_main_and_clean_closure_proof()
    test_priority_lifecycle_deduplicates_and_reescalates()
    test_main_session_pickup_does_not_age_heartbeat_repeat_counter()
    test_forbidden_heartbeat_arguments_fail_before_writes()
    print("main_session_escalation_consumer tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
