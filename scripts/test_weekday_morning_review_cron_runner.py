from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import weekday_morning_review_cron_runner as runner


CHAIN_AUTHORITY = {
    "writes_finance_canon": False,
    "maintains_portfolio_state": False,
    "maintains_simulated_account_state": False,
    "capital_or_order_authority": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def _clean_summary() -> dict:
    return {
        "run_chain_status": "ok",
        "run_chain_validation_status": "ok",
        "run_chain_generated_at_utc": "2026-08-31T13:05:04Z",
        "run_chain_critical_errors": [],
        "run_chain_warnings": [],
        "run_chain_retired_stage_hits": [],
        "run_chain_authority": dict(CHAIN_AUTHORITY),
        "alert_level_status": "ok",
        "alert_level_validation_status": "ok",
        "digest_status": "ok",
        "digest_validation_status": "ok",
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
    }


def _payload(summary: dict | None = None, steps: list[dict] | None = None) -> dict:
    return {
        "authority_boundary": dict(runner.AUTHORITY_BOUNDARY),
        "steps": steps or [],
        "summary": summary or _clean_summary(),
    }


def test_clean_current_chain_is_ok() -> None:
    assert runner.validate(_payload()) == {"status": "ok", "errors": [], "warnings": []}


def test_terminal_compatibility_aliases_are_derived(monkeypatch) -> None:
    monkeypatch.setattr(runner, "build_summary", _clean_summary)

    payload = runner.build_payload([], skip_chain=False, launch_id="morning-launch-1")
    terminal = payload["terminal_completion"]

    assert terminal["run_summary_status"] == "ok"
    assert terminal["run_summary_run_id"] == "alerts-recommendations:morning:2026-08-31T13:05:04Z"
    assert terminal["run_summary_generated_at_utc"] == terminal["run_chain_generated_at_utc"]


def test_alert_freshness_error_is_not_masked(monkeypatch) -> None:
    summary = _clean_summary()
    summary.update({
        "run_chain_status": "error",
        "run_chain_validation_status": "error",
        "run_chain_critical_errors": ["alert_level_freshness"],
        "alert_level_status": "error",
        "alert_level_validation_status": "error",
    })
    validation = runner.validate(_payload(summary))
    monkeypatch.setattr(runner, "build_summary", lambda: summary)
    result = runner.build_payload([], skip_chain=True)

    assert validation["status"] == "error"
    assert "run_chain_status:error" in validation["errors"]
    assert "run_chain_critical_errors:alert_level_freshness" in validation["errors"]
    assert "alert_level_freshness_not_ok" in validation["errors"]
    assert result["status"] == "blocked"
    assert result["operator_action"] == "BLOCKED"


def test_retired_stage_hit_blocks_fail_closed() -> None:
    summary = _clean_summary()
    summary["run_chain_retired_stage_hits"] = ["retired-stage.py"]

    validation = runner.validate(_payload(summary))

    assert "run_chain_retired_stage_hits:retired-stage.py" in validation["errors"]


def test_chain_authority_widening_blocks() -> None:
    summary = _clean_summary()
    summary["run_chain_authority"]["capital_or_order_authority"] = True

    validation = runner.validate(_payload(summary))

    assert "run_chain_authority_capital_or_order_authority_not_false" in validation["errors"]


def test_build_steps_uses_current_bounded_chain() -> None:
    steps = runner.build_steps(False)

    assert steps[0] == (
        "morning_alerts_recommendations_chain",
        [sys.executable, "scripts\\run_alerts_recommendations_chain.py", "morning", "--write", "--validate"],
        2700,
    )
    assert runner.build_steps(True) == []


def test_skip_chain_default_output_is_observer_only() -> None:
    assert runner.resolve_output_path(None, True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(runner.DEFAULT_OUT, True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(Path("tmp/arbitrary-observer-target.json"), True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(None, False) == runner.DEFAULT_OUT


def test_recent_chain_check_uses_current_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "TMP", tmp_path)
    (tmp_path / "alerts-recommendations-chain-morning.json").write_text('{"status":"running"}', encoding="utf-8")

    assert runner.chain_recently_running() is True


def test_background_launcher_does_not_duplicate_current_chain(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "TMP", tmp_path)
    monkeypatch.setattr(
        runner,
        "active_morning_processes",
        lambda: [{"ProcessId": 123, "CommandLine": "python scripts\\run_alerts_recommendations_chain.py morning"}],
    )
    out = tmp_path / "weekday-morning-review-cron-runner.json"
    launch_out = tmp_path / "weekday-morning-review-cron-launcher.json"

    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "already_running"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert payload["child_pid"] is None
    assert payload["active_processes"]
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
    assert launch_out.exists()
