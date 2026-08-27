#!/usr/bin/env python3
from __future__ import annotations

import pm_autonomy_verifier as verifier
from pm_autonomy_policy import DEFAULT_POLICY, validate_policy


def test_policy_still_blocks_code_and_execution_authority() -> None:
    validation = validate_policy(DEFAULT_POLICY)
    assert validation["status"] == "ok", validation
    boundary = DEFAULT_POLICY["automation_boundary"]
    assert boundary["code_patch_without_prompt"] is False
    assert boundary["cron_schedule_mutation_allowed"] is False
    assert boundary["config_auth_runtime_mutation_allowed"] is False
    assert boundary["canon_or_portfolio_mutation_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def test_verifier_authority_boundary_blocks_mutation() -> None:
    boundary = verifier.AUTHORITY_BOUNDARY
    assert boundary["patches_code"] is False
    assert boundary["spawns_helpers"] is False
    assert boundary["cron_schedule_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False


def test_future_session_refresh_runs_before_startup_status_when_included() -> None:
    calls: list[str] = []
    original = verifier.run_step

    def fake_run_step(name, command, timeout):
        calls.append(name)
        return {"name": name, "command": command, "timeout": timeout, "ok": True}

    try:
        verifier.run_step = fake_run_step
        steps = verifier.refresh_status_packets(include_future_session=True)
    finally:
        verifier.run_step = original

    assert [step["name"] for step in steps] == [
        "pm_control_packet",
        "future_session_enhancement_packet",
        "startup_brief_packet",
        "status_card_packet",
    ]
    assert calls == [step["name"] for step in steps]


def test_no_action_health_check_is_clean_not_warning() -> None:
    report = {
        "status": "quiet_success",
        "summary": {"action_type": "no_action"},
        "validation": {"status": "ok", "errors": [], "warnings": [], "info": ["no_action_verified"]},
    }
    health = verifier.health_check(report)
    assert health["status"] == "clean"
    assert health["verifier_status"] == "quiet_success"


def test_no_action_startup_status_refresh_failures_are_warning_residue() -> None:
    errors, warnings = verifier.classify_refresh_failures(
        "no_action",
        [
            {"name": "pm_control_packet", "ok": True},
            {"name": "startup_brief_packet", "ok": False},
            {"name": "status_card_packet", "ok": False},
        ],
    )

    assert errors == []
    assert warnings == ["status_packet_refresh_validation_residue"]


def test_verification_state_reports_resolved_and_refreshed() -> None:
    state = verifier.verification_state(
        action_type="run_proof_refresh",
        dispatcher_selected_job="pm-test",
        worker_selected_job="pm-test",
        worker_summary={},
        worker={"worker_state": {"job_resolved_or_completed": True}},
        pm_execution={"worker_state": {"closeout_ledgered": True}},
        refresh_results=[{"ok": True, "name": "pm_control_packet"}],
    )
    assert state["candidate_selected"] is True
    assert state["closeout_ledgered"] is True
    assert state["frontdoors_refreshed"] is True
    assert state["terminal_state"] == "resolved_and_refreshed"


def main() -> int:
    test_policy_still_blocks_code_and_execution_authority()
    test_verifier_authority_boundary_blocks_mutation()
    test_future_session_refresh_runs_before_startup_status_when_included()
    test_no_action_health_check_is_clean_not_warning()
    test_no_action_startup_status_refresh_failures_are_warning_residue()
    test_verification_state_reports_resolved_and_refreshed()
    print("pm_autonomy_verifier_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
