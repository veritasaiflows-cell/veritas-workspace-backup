from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import post_close_review_cron_runner as runner
import post_close_review_cron_launcher as launcher


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
        "run_chain_generated_at_utc": "2026-08-31T20:20:00Z",
        "run_chain_critical_errors": [],
        "run_chain_warnings": [],
        "run_chain_retired_stage_hits": [],
        "run_chain_authority": dict(CHAIN_AUTHORITY),
        "alert_level_status": "ok",
        "alert_level_validation_status": "ok",
        "digest_status": "ok",
        "digest_validation_status": "ok",
        "cron_control_escalation_signal_count": 0,
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


def test_terminal_contract_remains_compatible_with_launcher(monkeypatch) -> None:
    monkeypatch.setattr(runner, "build_summary", _clean_summary)
    payload = runner.build_payload([], skip_chain=False, launch_id="post-close-launch-1")
    observed_at = launcher.parse_generated_at(payload["generated_at_utc"])

    assert observed_at is not None
    assert payload["terminal_completion"]["run_summary_run_id"]
    assert launcher.recent_success_artifact(payload, observed_at, max_age_minutes=45) is True


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
    summary["run_chain_authority"]["maintains_portfolio_state"] = True

    validation = runner.validate(_payload(summary))

    assert "run_chain_authority_maintains_portfolio_state_not_false" in validation["errors"]


def test_cron_control_packet_failure_is_attention_not_failed_step(monkeypatch) -> None:
    step = {
        "name": "cron_control_packet",
        "ok": False,
        "status": runner.classify_step_status("cron_control_packet", 1),
        "blocking": not runner.is_non_blocking_step("cron_control_packet"),
        "returncode": 1,
    }
    monkeypatch.setattr(runner, "build_summary", _clean_summary)

    payload = runner.build_payload([step], skip_chain=False)

    assert step["status"] == "attention"
    assert runner.is_blocking_step_failure(step) is False
    assert payload["step_rollup"]["blocked"] == 0
    assert payload["step_rollup"]["attention"] == 1
    assert "attention_steps:cron_control_packet" in payload["validation"]["warnings"]
    assert payload["status"] == "warning"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"


def test_current_chain_step_failure_blocks(monkeypatch) -> None:
    step = {
        "name": "post_close_alerts_recommendations_chain",
        "ok": False,
        "status": runner.classify_step_status("post_close_alerts_recommendations_chain", 1),
        "blocking": not runner.is_non_blocking_step("post_close_alerts_recommendations_chain"),
        "returncode": 1,
    }
    monkeypatch.setattr(runner, "build_summary", _clean_summary)

    payload = runner.build_payload([step], skip_chain=False)

    assert step["status"] == "blocked"
    assert runner.is_blocking_step_failure(step) is True
    assert payload["step_rollup"]["blocked"] == 1
    assert "failed_steps:post_close_alerts_recommendations_chain" in payload["validation"]["errors"]


def test_build_steps_uses_current_bounded_chain() -> None:
    steps = runner.build_steps(False)

    assert steps[0] == (
        "post_close_alerts_recommendations_chain",
        [sys.executable, "scripts\\run_alerts_recommendations_chain.py", "post-close", "--write", "--validate"],
        3000,
    )
    assert runner.build_steps(True) == []


def test_skip_chain_default_output_is_observer_only() -> None:
    assert runner.resolve_output_path(None, True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(runner.DEFAULT_OUT, True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(Path("tmp/arbitrary-observer-target.json"), True) == runner.DEFAULT_OBSERVER_OUT
    assert runner.resolve_output_path(None, False) == runner.DEFAULT_OUT


def test_recent_chain_check_uses_current_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "TMP", tmp_path)
    (tmp_path / "alerts-recommendations-chain-post-close.json").write_text('{"status":"running"}', encoding="utf-8")

    assert runner.chain_recently_running() is True


def test_background_launcher_does_not_duplicate_current_chain(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "TMP", tmp_path)
    monkeypatch.setattr(
        runner,
        "active_post_close_processes",
        lambda: [{"ProcessId": 123, "CommandLine": "python scripts\\run_alerts_recommendations_chain.py post-close"}],
    )
    out = tmp_path / "post-close-review-cron-runner.json"
    launch_out = tmp_path / "post-close-review-cron-launcher.json"

    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "already_running"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert payload["child_pid"] is None
    assert payload["active_processes"]
    assert launch_out.exists()


def test_background_launcher_payload_shape_without_running_chain(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "chain_recently_running", lambda: False)
    monkeypatch.setattr(runner, "active_post_close_processes", lambda: [])
    monkeypatch.setattr(runner, "start_detached_process", lambda command, stdout_path, stderr_path: 12345)
    monkeypatch.setattr(runner, "TMP", tmp_path)
    out = tmp_path / "post-close-review-cron-runner.json"
    launch_out = tmp_path / "post-close-review-cron-launcher.json"

    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "launched"
    assert payload["operator_action"] == "NO_REPLY"
    assert payload["child_pid"] == 12345
    assert payload["stale_running_artifact"] is False
    assert payload["expected_result_artifact"].endswith("post-close-review-cron-runner.json")
    assert payload["launch_id"]
    assert "--launch-id" in payload["child_command"]
    assert launch_out.exists()


def test_background_launcher_relaunches_stale_running_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "chain_recently_running", lambda: True)
    monkeypatch.setattr(runner, "active_post_close_processes", lambda: [])
    monkeypatch.setattr(runner, "start_detached_process", lambda command, stdout_path, stderr_path: 12345)
    monkeypatch.setattr(runner, "TMP", tmp_path)
    out = tmp_path / "post-close-review-cron-runner.json"
    launch_out = tmp_path / "post-close-review-cron-launcher.json"

    payload = runner.launch_background(False, out, launch_out)

    assert payload["status"] == "launched_after_stale_running_artifact"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert payload["child_pid"] == 12345
    assert payload["stale_running_artifact"] is True
    assert launch_out.exists()
