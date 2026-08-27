from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import post_close_review_cron_runner as runner


def _clean_data_quality_payload(classification: str, ticker_count: int) -> dict:
    is_ticker_scoped = classification == "ticker_scoped_repair"
    return {
        "authority_boundary": dict(runner.AUTHORITY_BOUNDARY),
        "steps": [],
        "summary": {
            "run_chain_status": "completed_with_ticker_repairs" if is_ticker_scoped else "completed_with_systemic_data_quality",
            "run_summary_status": "warning" if is_ticker_scoped else "blocked",
            "run_summary_stop_line": not is_ticker_scoped,
            "run_summary_blockers_count": 0 if is_ticker_scoped else 1,
            "run_summary_data_quality_classification": classification,
            "run_summary_data_quality_only": True,
            "run_summary_data_quality_ticker_count": ticker_count,
            "run_summary_data_quality_tickers": ["JPM"] if is_ticker_scoped else ["GS", "JPM"],
            "auto_band_status": "ok",
            "reference_band_sync_status": "ok",
            "position_sizing_semantic_sync_status": "ok_no_changes",
            "post_apply_failed_steps": 0,
            "dashboard_critical": 0,
            "dashboard_warning": 0,
            "capital_validator_status": "ok",
            "capital_validator_critical": 0,
            "capital_bundle_status": "ok",
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
        },
    }


def _safe_artifact(path: str) -> dict:
    authorities = {
        "tmp/auto-band-apply.json": {"capital_action_allowed": False, "owner_approval_inferred": False},
        "tmp/reference-band-note-sync.json": {"capital_action_allowed": False, "owner_approval_inferred": False},
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


def test_no_candidate_capital_validator_warning_is_review_only_ok() -> None:
    summary = {
        "capital_validator_status": "warning",
        "capital_validator_critical": 0,
        "capital_bundle_status": "no_candidates",
    }

    assert runner.capital_validator_review_only_ok(summary) is True


def test_capital_validator_warning_with_critical_still_blocks() -> None:
    summary = {
        "capital_validator_status": "warning",
        "capital_validator_critical": 1,
        "capital_bundle_status": "no_candidates",
    }

    assert runner.capital_validator_review_only_ok(summary) is False


def test_cron_control_packet_failure_is_attention_not_failed_step(monkeypatch) -> None:
    step = {
        "name": "cron_control_packet",
        "ok": False,
        "status": runner.classify_step_status("cron_control_packet", 1),
        "blocking": not runner.is_non_blocking_step("cron_control_packet"),
        "returncode": 1,
    }

    clean_summary = _clean_data_quality_payload("ticker_scoped_repair", 1)["summary"]
    clean_summary.update({
        "run_chain_status": "ok",
        "run_summary_status": "ok",
        "run_summary_stop_line": False,
        "run_summary_blockers_count": 0,
        "run_summary_data_quality_classification": None,
        "run_summary_data_quality_only": False,
        "run_summary_data_quality_ticker_count": 0,
        "run_summary_data_quality_tickers": [],
    })
    monkeypatch.setattr(runner, "build_summary", lambda: clean_summary)
    monkeypatch.setattr(runner, "artifact", _safe_artifact)
    payload = runner.build_payload([step], skip_chain=False)
    validation = runner.validate(payload)

    assert step["status"] == "attention"
    assert runner.is_blocking_step_failure(step) is False
    assert payload["step_rollup"]["blocked"] == 0
    assert payload["step_rollup"]["attention"] == 1
    assert not any(item.startswith("failed_steps:") for item in validation["errors"])
    assert "attention_steps:cron_control_packet" in validation["warnings"]
    assert payload["status"] == "warning"
    assert payload["operator_action"] == "MAIN_SESSION_REQUIRED"


def test_normal_failed_step_still_blocks_validation() -> None:
    step = {
        "name": "post_close_finance_refresh_chain",
        "ok": False,
        "status": runner.classify_step_status("post_close_finance_refresh_chain", 1),
        "blocking": not runner.is_non_blocking_step("post_close_finance_refresh_chain"),
        "returncode": 1,
    }

    payload = runner.build_payload([step], skip_chain=False)
    validation = runner.validate(payload)

    assert step["status"] == "blocked"
    assert runner.is_blocking_step_failure(step) is True
    assert payload["step_rollup"]["blocked"] == 1
    assert payload["step_rollup"]["attention"] == 0
    assert "failed_steps:post_close_finance_refresh_chain" in validation["errors"]


def test_ticker_scoped_data_quality_chain_is_completed_with_visible_repair(monkeypatch) -> None:
    monkeypatch.setattr(runner, "artifact", _safe_artifact)
    payload = _clean_data_quality_payload("ticker_scoped_repair", 1)
    validation = runner.validate(payload)
    monkeypatch.setattr(runner, "build_summary", lambda: payload["summary"])
    result = runner.build_payload([], skip_chain=False, launch_id="post-close-launch-1")

    assert validation["errors"] == []
    assert "ticker_scoped_data_quality_repair_present_for_main_visibility" in validation["warnings"]
    assert result["status"] == "completed_with_ticker_repairs"
    assert result["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert result["terminal_completion"]["runner_executed_chain"] is True
    assert result["terminal_completion"]["launch_id"] == "post-close-launch-1"


def test_systemic_data_quality_chain_is_completed_but_decision_degraded(monkeypatch) -> None:
    monkeypatch.setattr(runner, "artifact", _safe_artifact)
    payload = _clean_data_quality_payload("systemic_data_quality", 2)
    validation = runner.validate(payload)
    monkeypatch.setattr(runner, "build_summary", lambda: payload["summary"])
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
        "active_post_close_processes",
        lambda: [{"ProcessId": 123, "CommandLine": "python scripts\\run_finance_refresh_chain.py post-close"}],
    )
    runner_file = tmp_path / "run-chain-post-close.json"
    runner_file.write_text('{"status":"running"}', encoding="utf-8")
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
    assert payload["operator_action"] == "NO_REPLY"
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
    assert payload["expected_result_artifact"].endswith("post-close-review-cron-runner.json")
    assert launch_out.exists()
