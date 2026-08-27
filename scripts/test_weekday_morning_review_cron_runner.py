from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import weekday_morning_review_cron_runner as runner


def _clean_recovered_payload() -> dict:
    return {
        "authority_boundary": dict(runner.AUTHORITY_BOUNDARY),
        "steps": [],
        "summary": {
            "run_chain_status": "completed_with_recovery",
            "run_summary_status": "ok",
            "run_summary_stop_line": False,
            "run_summary_blockers_count": 0,
            "run_summary_operator_action_required_count": 0,
            "auto_band_status": "ok",
            "reference_band_sync_status": "ok",
            "position_sizing_semantic_sync_status": "ok_no_changes",
            "post_apply_failed_steps": 0,
            "dashboard_critical": 0,
            "dashboard_warning": 0,
            "capital_validator_status": "ok",
            "capital_validator_critical": 0,
            "sql_canon_health": {
                "status": "ok",
                "authority_boundary": {
                    "db_mutation_allowed": False,
                    "sql_canon_cutover_allowed": False,
                    "capital_deployment_allowed": False,
                    "paper_or_live_execution_allowed": False,
                    "brokerage_or_account_action_allowed": False,
                    "customer_or_external_delivery_allowed": False,
                    "owner_approval_inferred": False,
                },
            },
        },
    }


def _fake_artifact(path: str) -> dict:
    authorities = {
        "tmp/auto-band-apply.json": {
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "tmp/reference-band-note-sync.json": {
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "tmp/auto-position-sizing-semantic-sync.json": {
            "portfolio_config_weight_mutation_allowed": False,
            "cash_risk_rule_sleeve_execution_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json": {
            "proposal_apply_allowed": False,
            "per_packet_owner_approval_inferred": False,
            "trade_or_account_action_allowed": False,
            "trade_execution_allowed": False,
        },
    }
    return {"authority": authorities.get(path, {})}


def test_recovered_morning_chain_is_ok_when_downstream_proof_is_clean(monkeypatch) -> None:
    monkeypatch.setattr(runner, "artifact", _fake_artifact)

    validation = runner.validate(_clean_recovered_payload())

    assert validation == {"status": "ok", "errors": [], "warnings": []}


def test_recovered_morning_chain_still_blocks_on_stop_line(monkeypatch) -> None:
    monkeypatch.setattr(runner, "artifact", _fake_artifact)
    payload = _clean_recovered_payload()
    payload["summary"]["run_summary_stop_line"] = True

    validation = runner.validate(payload)

    assert validation["status"] == "error"
    assert validation["errors"] == ["run_chain_status:completed_with_recovery"]


def test_ticker_scoped_data_quality_chain_is_completed_with_visible_repair(monkeypatch) -> None:
    monkeypatch.setattr(runner, "artifact", _fake_artifact)
    payload = _clean_recovered_payload()
    summary = payload["summary"]
    summary.update({
        "run_chain_status": "completed_with_ticker_repairs",
        "run_summary_status": "warning",
        "run_summary_stop_line": False,
        "run_summary_blockers_count": 0,
        "run_summary_operator_action_required_count": 1,
        "run_summary_data_quality_classification": "ticker_scoped_repair",
        "run_summary_data_quality_only": True,
        "run_summary_data_quality_ticker_count": 1,
        "run_summary_data_quality_tickers": ["JPM"],
    })
    validation = runner.validate(payload)
    monkeypatch.setattr(runner, "build_summary", lambda: summary)
    result = runner.build_payload([], skip_chain=False, launch_id="morning-launch-1")

    assert validation["errors"] == []
    assert "ticker_scoped_data_quality_repair_present_for_main_visibility" in validation["warnings"]
    assert result["status"] == "completed_with_ticker_repairs"
    assert result["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert result["terminal_completion"]["runner_executed_chain"] is True
    assert result["terminal_completion"]["launch_id"] == "morning-launch-1"


def test_systemic_data_quality_chain_is_completed_but_decision_degraded(monkeypatch) -> None:
    monkeypatch.setattr(runner, "artifact", _fake_artifact)
    payload = _clean_recovered_payload()
    summary = payload["summary"]
    summary.update({
        "run_chain_status": "completed_with_systemic_data_quality",
        "run_summary_status": "blocked",
        "run_summary_stop_line": True,
        "run_summary_blockers_count": 1,
        "run_summary_operator_action_required_count": 1,
        "run_summary_data_quality_classification": "systemic_data_quality",
        "run_summary_data_quality_only": True,
        "run_summary_data_quality_ticker_count": 2,
        "run_summary_data_quality_tickers": ["GS", "JPM"],
    })
    validation = runner.validate(payload)
    monkeypatch.setattr(runner, "build_summary", lambda: summary)
    result = runner.build_payload([], skip_chain=False)

    assert validation["errors"] == []
    assert "systemic_data_quality_repair_present_for_main_visibility" in validation["warnings"]
    assert result["status"] == "completed_with_systemic_data_quality"
    assert result["operator_action"] == "MAIN_SESSION_REQUIRED"


def test_skip_chain_default_output_is_observer_only() -> None:
    assert runner.resolve_output_path(None, True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(runner.DEFAULT_OUT, True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(Path("tmp/arbitrary-observer-target.json"), True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(None, False) == runner.DEFAULT_OUT


def test_background_launcher_does_not_duplicate_recent_running_chain(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "TMP", tmp_path)
    monkeypatch.setattr(
        runner,
        "active_morning_processes",
        lambda: [{"ProcessId": 123, "CommandLine": "python scripts\\run_finance_refresh_chain.py morning"}],
    )
    (tmp_path / "run-chain-morning.json").write_text('{"status":"running"}', encoding="utf-8")

    out = tmp_path / "weekday-morning-review-cron-runner.json"
    launch_out = tmp_path / "weekday-morning-review-cron-launcher.json"
    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "already_running"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert payload["child_pid"] is None
    assert payload["active_processes"]
    assert payload["stale_running_artifact"] is False
    assert launch_out.exists()


def test_background_launcher_payload_shape_without_running_chain(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "chain_recently_running", lambda: False)
    monkeypatch.setattr(runner, "active_morning_processes", lambda: [])
    monkeypatch.setattr(runner, "start_detached_process", lambda command, stdout_path, stderr_path: 12345)
    monkeypatch.setattr(runner, "TMP", tmp_path)

    out = tmp_path / "weekday-morning-review-cron-runner.json"
    launch_out = tmp_path / "weekday-morning-review-cron-launcher.json"
    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "launched"
    assert payload["operator_action"] == "NO_REPLY"
    assert payload["child_pid"] == 12345
    assert payload["stale_running_artifact"] is False
    assert payload["expected_result_artifact"].endswith("weekday-morning-review-cron-runner.json")
    assert payload["launch_id"]
    assert "--launch-id" in payload["child_command"]
    assert launch_out.exists()


def test_start_detached_process_uses_native_detached_popen(tmp_path, monkeypatch) -> None:
    captured: dict = {}

    class FakeProcess:
        pid = 45678

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.subprocess, "DETACHED_PROCESS", 0x00000008, raising=False)
    monkeypatch.setattr(runner.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False)

    stdout_path = tmp_path / "background.out.txt"
    stderr_path = tmp_path / "background.err.txt"
    pid = runner.start_detached_process(["python.exe", "runner.py", "--write"], stdout_path, stderr_path)

    assert pid == 45678
    assert captured["command"] == ["python.exe", "runner.py", "--write"]
    assert captured["cwd"] == runner.ROOT
    assert captured["stdin"] == runner.subprocess.DEVNULL
    assert captured["close_fds"] is True
    assert captured["creationflags"] == 0x00000008 | 0x00000200
    assert captured["stdout"].name == str(stdout_path)
    assert captured["stderr"].name == str(stderr_path)
    assert captured["stdout"].closed is True
    assert captured["stderr"].closed is True


def test_background_launcher_relaunches_stale_running_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "chain_recently_running", lambda: True)
    monkeypatch.setattr(runner, "active_morning_processes", lambda: [])
    monkeypatch.setattr(runner, "start_detached_process", lambda command, stdout_path, stderr_path: 12345)
    monkeypatch.setattr(runner, "TMP", tmp_path)

    out = tmp_path / "weekday-morning-review-cron-runner.json"
    launch_out = tmp_path / "weekday-morning-review-cron-launcher.json"
    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "launched_after_stale_running_artifact"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert payload["child_pid"] == 12345
    assert payload["stale_running_artifact"] is True
    assert payload["expected_result_artifact"].endswith("weekday-morning-review-cron-runner.json")
    assert launch_out.exists()
