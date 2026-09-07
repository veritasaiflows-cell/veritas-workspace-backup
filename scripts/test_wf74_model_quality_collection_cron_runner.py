from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf74_model_quality_collection_cron_runner as runner


def test_cron_control_packet_failure_is_attention_not_blocking() -> None:
    step = {
        "name": "cron_control_packet",
        "status": runner.classify_step_status("cron_control_packet", 1),
        "blocking": not runner.is_non_blocking_step("cron_control_packet"),
        "returncode": 1,
    }

    payload = runner.build_payload([step])
    details = [finding["detail"] for finding in runner.validate(payload)["findings"]]

    assert step["status"] == "attention"
    assert runner.is_blocking_step_failure(step) is False
    assert payload["status"] == "ok"
    assert payload["summary"]["steps_ok"] == 0
    assert payload["summary"]["steps_blocked"] == 0
    assert payload["summary"]["steps_attention"] == 1
    learning_environment = payload["summary"]["learning_environment_status"]
    assert learning_environment["schema"] == "wf74.learning_environment_status.v1"
    assert learning_environment["runner_status"] == "attention"
    # This regression owns cron-control classification only. Quality-gate fields
    # are sourced from live proof artifacts and may truthfully be blocked while
    # an unrelated workspace migration is in progress.
    assert "quality_gate_status" in learning_environment
    assert "decision_quality_status" in learning_environment
    assert "anti_theater_status" in learning_environment
    assert "planning_quality_status" in learning_environment
    assert "coding_ex_post_status" in learning_environment
    assert "planning_quality_signal_status" in payload["summary"]
    assert "one or more collection steps blocked" not in details
    assert "one or more non-blocking diagnostic steps need attention" in details


def test_normal_step_failure_still_blocks_runner() -> None:
    step = {
        "name": "model_run_ledger",
        "status": runner.classify_step_status("model_run_ledger", 1),
        "blocking": not runner.is_non_blocking_step("model_run_ledger"),
        "returncode": 1,
    }

    payload = runner.build_payload([step])
    details = [finding["detail"] for finding in runner.validate(payload)["findings"]]

    assert step["status"] == "blocked"
    assert runner.is_blocking_step_failure(step) is True
    assert payload["status"] == "blocked"
    assert payload["summary"]["steps_ok"] == 0
    assert payload["summary"]["steps_blocked"] == 1
    assert payload["summary"]["steps_attention"] == 0
    assert payload["summary"]["learning_environment_status"]["runner_status"] == "blocked"
    assert "one or more collection steps blocked" in details


def test_harness_failure_is_quality_attention_not_runner_block() -> None:
    step = {
        "name": "veritas_harness_scorecard_fast",
        "status": runner.classify_step_status("veritas_harness_scorecard_fast", 2),
        "blocking": not runner.is_non_blocking_step("veritas_harness_scorecard_fast"),
        "returncode": 2,
    }

    payload = runner.build_payload([step])
    details = [finding["detail"] for finding in runner.validate(payload)["findings"]]

    assert step["status"] == "attention"
    assert runner.is_blocking_step_failure(step) is False
    assert payload["status"] == "ok"
    assert payload["summary"]["steps_blocked"] == 0
    assert payload["summary"]["steps_attention"] == 1
    assert payload["summary"]["learning_environment_status"]["runner_status"] == "attention"
    assert "one or more collection steps blocked" not in details


def test_otel_ops_failure_is_diagnostic_attention_not_runner_block() -> None:
    step = {
        "name": "otel_ops_control",
        "status": runner.classify_step_status("otel_ops_control", 1),
        "blocking": not runner.is_non_blocking_step("otel_ops_control"),
        "returncode": 1,
    }

    payload = runner.build_payload([step])
    details = [finding["detail"] for finding in runner.validate(payload)["findings"]]

    assert step["status"] == "attention"
    assert step["blocking"] is False
    assert payload["status"] == "ok"
    assert payload["summary"]["steps_blocked"] == 0
    assert payload["summary"]["steps_attention"] == 1
    assert "one or more collection steps blocked" not in details


def test_telegram_runner_requests_nonblocking_exit_for_classified_domain_debt() -> None:
    source = (SCRIPTS / "wf74_learning_loop_telegram_cron_runner.py").read_text(encoding="utf-8")

    assert '"--cron-nonblocking-domain-exit"' in source


def test_unclassified_blocking_step_still_fails_scheduler_exit() -> None:
    step = {
        "name": "model_run_ledger",
        "status": "blocked",
        "blocking": True,
        "returncode": 1,
    }
    payload = runner.build_payload([step])
    validation = runner.validate(payload)
    decision = runner.scheduler_exit_decision(payload, validation, allow_domain_blocked_exit_zero=True)

    assert runner.is_classified_domain_blocker(payload) is False
    assert decision["status"] == "critical"
    assert decision["returncode"] == 1
    assert decision["domain_blocked_nonfatal"] is False


def test_model_run_ledger_command_is_bounded_inside_runner_plan() -> None:
    command = {
        name: cmd
        for name, cmd, _timeout in runner.command_plan(include_harness=False)
    }["model_run_ledger"]

    assert "--cron-job-limit" in command
    assert command[command.index("--cron-job-limit") + 1] == "8"
    assert "--cron-runs-timeout" in command
    assert command[command.index("--cron-runs-timeout") + 1] == "8"


def test_alerts_os_boundary_and_recommendation_digest_replace_retired_finance_steps() -> None:
    plan_names = [name for name, _cmd, _timeout in runner.command_plan(include_harness=False)]

    assert "alerts_os_pivot_validator" in plan_names
    assert "recommendation_performance_digest" in plan_names
    assert plan_names.index("recommendation_performance_digest") < plan_names.index("alerts_os_pivot_validator")
    assert runner.is_non_blocking_step("alerts_os_pivot_validator") is False


def test_phase1_self_prompt_steps_are_daily_nonblocking_review_steps() -> None:
    plan_names = [name for name, _cmd, _timeout in runner.command_plan(include_harness=False)]

    assert "wf74_telemetry_critique_engine" in plan_names
    assert "wf74_self_prompt_generator" in plan_names
    assert plan_names.index("wf74_telemetry_critique_engine") < plan_names.index("wf74_self_prompt_generator")
    assert runner.is_non_blocking_step("wf74_telemetry_critique_engine") is True
    assert runner.is_non_blocking_step("wf74_self_prompt_generator") is True


def test_phase2_feedback_steps_follow_self_prompt_and_stay_nonblocking() -> None:
    plan_names = [name for name, _cmd, _timeout in runner.command_plan(include_harness=False)]

    assert "wf74_self_prompt_generator" in plan_names
    assert "wf74_prompt_variant_ledger" in plan_names
    assert "wf74_outcome_feedback_ingestor" in plan_names
    assert plan_names.index("wf74_self_prompt_generator") < plan_names.index("wf74_prompt_variant_ledger")
    assert plan_names.index("wf74_prompt_variant_ledger") < plan_names.index("wf74_outcome_feedback_ingestor")
    assert runner.is_non_blocking_step("wf74_prompt_variant_ledger") is True
    assert runner.is_non_blocking_step("wf74_outcome_feedback_ingestor") is True


def test_runner_does_not_consume_retired_trade_grade_repair_artifact() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8").lower()
    assert "trade-grade-repair-conveyor" not in source
    payload = runner.build_payload([])
    assert not any(key.startswith("finance_repair_conveyor_") for key in payload["summary"])
