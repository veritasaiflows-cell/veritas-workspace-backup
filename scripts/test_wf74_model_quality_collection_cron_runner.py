from pathlib import Path
import json
import sys
import tempfile

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
    assert learning_environment["quality_gate_status"] in {"ok", "claim_gated"}
    assert learning_environment["decision_quality_status"] in {"active", "active_measurement_only", "not_blocked_by_wf55"}
    if "wf55_outcome_grades" in learning_environment.get("claim_gated_quality_gates", []):
        assert learning_environment["decision_quality_status"] == "active_measurement_only"
        assert learning_environment["semantic_outcome_claim_status"] == "maturity_gated"
        assert "wf55_outcome_grades" not in learning_environment.get("blocked_quality_gates", [])
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


def test_finance_quality_failure_is_domain_attention_not_cron_block() -> None:
    step = runner.run_step(
        "finance_response_quality_slice",
        [sys.executable, "-c", "import sys; sys.exit(1)"],
        5,
        12,
    )

    payload = runner.build_payload([step])
    details = [finding["detail"] for finding in runner.validate(payload)["findings"]]

    assert step["status"] == "attention"
    assert step["blocking"] is False
    assert step["attention_class"] == "domain_quality"
    assert step["failure_kind"] == "nonzero_returncode"
    assert step["step_index"] == 12
    assert payload["status"] == "ok"
    assert payload["summary"]["steps_blocked"] == 0
    assert payload["summary"]["steps_attention"] == 1
    assert payload["summary"]["domain_attention_steps"] == ["finance_response_quality_slice"]
    assert "one or more collection steps blocked" not in details


def test_source_open_blocker_chain_points_to_finance_repair_route() -> None:
    original_tmp = runner.TMP
    with tempfile.TemporaryDirectory() as td:
        runner.TMP = Path(td)
        (runner.TMP / "finance-response-quality-slice.json").write_text(
            '{"status":"blocked","summary":{"source_open_blocked_count":42}}',
            encoding="utf-8",
        )
        step = {
            "name": "model_quality_scorecard",
            "status": "blocked",
            "blocking": True,
            "returncode": 1,
        }

        payload = runner.build_payload([step])
        summary = payload["summary"]

        assert payload["status"] == "blocked"
        assert runner.is_classified_domain_blocker(payload) is True
        assert summary["finance_response_quality_source_open_blocked_count"] == 42
        assert summary["finance_response_quality_recommended_department"] == "finance_wf78_wf84_wf85"
        assert summary["finance_response_quality_recommended_repair_route"] == "wf78_wf85_source_open_repair"
        assert summary["finance_response_quality_blocker_chain"] == [
            "wf74_model_quality_collection_cron_runner",
            "model_quality_scorecard",
            "finance_response_quality_slice",
            "source_freshness_blocked_count=0",
            "source_open_blocked_count=42",
            "primary_state_blocked_count=0",
            "below_stop_blocked_count=0",
            "tier_c_thin_monitor_non_blocking_count=0",
            "scoped_thin_monitor_not_required_non_blocking_count=0",
        ]
        validation = {
            "status": "critical",
            "findings": [
                {"severity": "critical", "detail": "one or more collection steps blocked"},
                {"severity": "critical", "detail": "learning environment runner status is blocked"},
                {"severity": "critical", "detail": "finance response quality slice has source/technical or unclassified blockers that still block WF74 collection."},
                {"severity": "warning", "detail": "finance response quality slice is not ok"},
            ],
        }
        decision = runner.scheduler_exit_decision(payload, validation, allow_domain_blocked_exit_zero=True)
        assert decision["status"] == "domain_blocked_nonfatal"
        assert decision["returncode"] == 0
        assert decision["reason"] == "classified_finance_response_source_open_repair"
        strict_decision = runner.scheduler_exit_decision(payload, validation, allow_domain_blocked_exit_zero=False)
        assert strict_decision["status"] == "critical"
        assert strict_decision["returncode"] == 1
    runner.TMP = original_tmp


def test_telegram_runner_requests_nonblocking_exit_for_classified_domain_debt() -> None:
    source = (SCRIPTS / "wf74_learning_loop_telegram_cron_runner.py").read_text(encoding="utf-8")

    assert '"--cron-nonblocking-domain-exit"' in source


def test_decision_readiness_debt_is_classified_domain_nonfatal() -> None:
    original_tmp = runner.TMP
    with tempfile.TemporaryDirectory() as td:
        runner.TMP = Path(td)
        (runner.TMP / "finance-response-quality-slice.json").write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "summary": {
                        "source_open_blocked_count": 0,
                        "source_freshness_blocked_count": 0,
                        "primary_state_blocked_count": 48,
                        "below_stop_blocked_count": 78,
                        "technical_posture_missing_both_count": 0,
                        "remediation_tracks_needing_repair": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
        step = {
            "name": "model_quality_scorecard",
            "status": "blocked",
            "blocking": True,
            "returncode": 1,
        }

        payload = runner.build_payload([step])
        summary = payload["summary"]

        assert runner.classified_domain_blocker_reason(payload) == "classified_finance_response_decision_readiness_debt"
        assert runner.is_classified_domain_blocker(payload) is True
        assert summary["finance_response_quality_source_open_blocked_count"] == 0
        assert summary["finance_response_quality_source_freshness_blocked_count"] == 0
        assert summary["finance_response_quality_primary_state_blocked_count"] == 48
        assert summary["finance_response_quality_below_stop_blocked_count"] == 78
        validation = {
            "status": "critical",
            "findings": [
                {"severity": "critical", "detail": "one or more collection steps blocked"},
                {"severity": "critical", "detail": "learning environment runner status is blocked"},
                {"severity": "warning", "detail": "finance response quality slice is not ok"},
            ],
        }
        decision = runner.scheduler_exit_decision(payload, validation, allow_domain_blocked_exit_zero=True)
        assert decision["status"] == "domain_blocked_nonfatal"
        assert decision["returncode"] == 0
        assert decision["reason"] == "classified_finance_response_decision_readiness_debt"
        strict_decision = runner.scheduler_exit_decision(payload, validation, allow_domain_blocked_exit_zero=False)
        assert strict_decision["status"] == "critical"
        assert strict_decision["returncode"] == 1
    runner.TMP = original_tmp


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


def test_source_open_orchestrator_precedes_finance_response_quality_slice() -> None:
    plan_names = [name for name, _cmd, _timeout in runner.command_plan(include_harness=False)]

    assert "wf78_source_open_patch_orchestrator" in plan_names
    assert "finance_response_quality_slice" in plan_names
    assert plan_names.index("wf78_source_open_patch_orchestrator") < plan_names.index("finance_response_quality_slice")
    assert runner.is_non_blocking_step("wf78_source_open_patch_orchestrator") is False


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


def test_tier_a_b_finance_domain_debt_is_warning_not_runner_block() -> None:
    payload = {
        "authority_boundary": runner.AUTHORITY_BOUNDARY,
        "summary": {
            "steps_blocked": 0,
            "steps_attention": 0,
            "finance_response_quality_status": "ok",
            "finance_repair_conveyor_implementation_blocker_count": 0,
            "finance_repair_conveyor_control_plane_blocker_count": 0,
            "tier_a_b_band_cron_guard_validation": "warning",
            "tier_a_b_stale_complete_band_context_count": 2,
            "token_usage_validation": "ok",
            "token_usage_event_count": 1,
            "otel_window_count": 5,
            "otel_field_depth_packet_status": "approved_enabled",
            "coding_outcome_ledger_rows": 1,
        },
        "artifacts": [{"path": "tmp/mock.json", "exists": True}],
    }

    findings = runner.validate(payload)["findings"]
    details = [finding["detail"] for finding in findings]
    severities = {finding["detail"]: finding["severity"] for finding in findings}

    assert "Tier A/B complete band context is finance-domain repair debt" in details
    assert severities["Tier A/B complete band context is finance-domain repair debt"] == "warning"
    assert "Tier A/B complete band context is stale" not in details
