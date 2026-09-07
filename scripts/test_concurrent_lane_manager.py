#!/usr/bin/env python3
from __future__ import annotations

import argparse

import concurrent_lane_manager as lanes


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def warning_names(result: dict) -> set[str]:
    return {str(item.get("name")) for item in result.get("warnings", [])}


def error_names(result: dict) -> set[str]:
    return {str(item.get("name")) for item in result.get("errors", [])}


def check_detail(result: dict, name: str):
    for item in result.get("checks", []):
        if item.get("name") == name:
            return item.get("detail")
    raise AssertionError(f"missing validation check: {name}")


def completed_model_lane(
    token_source: str | None = None,
    total_tokens: int | None = None,
    completed_at_utc: str = "2026-07-03T20:00:00Z",
) -> dict:
    runtime = {
        "session_key": "unit-test-session",
        "model_path": "openai/gpt-5.5",
        "model_provider": "openai",
    }
    if token_source:
        runtime["token_attribution_source"] = token_source
    if total_tokens is not None:
        runtime["total_tokens"] = total_tokens
        runtime["token_attribution_source"] = "unit-test"
    return {
        "lane_id": "WF88::unit-token-closeout",
        "workflow_id": "WF88",
        "workstream_id": "unit-token-closeout",
        "owner": "unit-test",
        "status": "complete",
        "created_at_utc": completed_at_utc,
        "completed_at_utc": completed_at_utc,
        "ended_at_utc": completed_at_utc,
        "allowed_writes": ["tmp/unit-token-closeout.json"],
        "proof_artifacts": ["unit test proof"],
        "runtime": runtime,
    }


def test_completed_model_lane_warns_without_token_closeout() -> None:
    register = lanes.empty_register()
    register["lanes"] = [completed_model_lane()]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "token closeout classification gap should be warning-grade")
    expect(
        "historical_completed_model_lanes_have_token_closeout_visibility" in warning_names(result),
        "missing token closeout classification should be visible",
    )


def test_historical_pre_guard_lane_does_not_warn() -> None:
    register = lanes.empty_register()
    register["lanes"] = [completed_model_lane(completed_at_utc="2026-07-03T19:00:00Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "historical pre-guard lane should be warning-clean")
    expect(
        "historical_completed_model_lanes_have_token_closeout_visibility" not in warning_names(result),
        "pre-guard lane should not require retroactive token closeout classification",
    )


def test_completed_model_lane_accepts_missing_usage_classification() -> None:
    register = lanes.empty_register()
    register["lanes"] = [completed_model_lane(token_source="current_chat_runtime_unavailable")]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "accepted unavailable classification should validate")
    expect(
        "historical_completed_model_lanes_have_token_closeout_visibility" not in warning_names(result),
        "accepted unavailable classification should clear token closeout warning",
    )


def test_completed_model_lane_accepts_token_totals() -> None:
    register = lanes.empty_register()
    register["lanes"] = [completed_model_lane(total_tokens=42)]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "token totals should validate")
    expect(
        "historical_completed_model_lanes_have_token_closeout_visibility" not in warning_names(result),
        "token totals should clear token closeout warning",
    )


def test_terminal_outcome_fields_persist_when_valid() -> None:
    lane = {"runtime": {}}
    args = argparse.Namespace(
        validator_result="pass",
        closure_durability="verified",
        register="tmp/unit-terminal-outcome-register.json",
    )
    lanes.apply_runtime_metadata(lane, args)
    runtime = lane["runtime"]
    expect(runtime.get("validator_result") == "pass", "valid validator_result should persist")
    expect(runtime.get("closure_durability") == "verified", "valid closure_durability should persist")


def test_invalid_validator_result_is_rejected() -> None:
    lane = {"runtime": {}}
    args = argparse.Namespace(validator_result="bogus", closure_durability="")
    try:
        lanes.apply_runtime_metadata(lane, args)
    except SystemExit as exc:
        expect("invalid validator result" in str(exc), "invalid validator_result should fail closed")
        return
    raise AssertionError("invalid validator_result should raise SystemExit")


def test_invalid_closure_durability_is_rejected() -> None:
    lane = {"runtime": {}}
    args = argparse.Namespace(validator_result="", closure_durability="maybe")
    try:
        lanes.apply_runtime_metadata(lane, args)
    except SystemExit as exc:
        expect("invalid closure durability" in str(exc), "invalid closure_durability should fail closed")
        return
    raise AssertionError("invalid closure_durability should raise SystemExit")


def active_implementation_attempt_lane() -> dict:
    lane = lanes.build_lane_template(
        "WAVE2",
        "unit-active-outcome-baseline",
        "unit-test",
    )
    lane["status"] = "leased"
    lane["lease_expires_at_utc"] = "2099-01-01T00:00:00Z"
    lane["allowed_writes"] = ["tmp/unit-active-outcome-baseline.json"]
    lane["runtime"] = {
        "parent_job_id": "unit-wave2-job",
        "phase": "implementation",
        "model_path": "openai/gpt-5.6-terra",
        "model_provider": "openai",
        "retry_count": 2,
        "attempt_number": 3,
        "attempt_id": "unit-wave2-job-a3",
    }
    lanes.apply_runtime_metadata(
        lane,
        argparse.Namespace(register="tmp/unit-active-outcome-register.json"),
    )
    return lane


def test_active_model_attempt_materializes_clean_outcome_baseline() -> None:
    lane = active_implementation_attempt_lane()
    runtime = lane["runtime"]
    expect(runtime.get("incident_code") == "", "active attempt needs clean incident code")
    expect(runtime.get("incident_count") == 0, "active attempt needs zero incident count")
    expect(lane.get("outcome_events") == [], "active attempt needs empty outcome history")


def test_active_incident_history_fails_closed_without_terminal_rewrite() -> None:
    lane = active_implementation_attempt_lane()
    runtime = lane["runtime"]
    recorded_at = "2026-08-26T19:00:00Z"
    runtime.update({
        "incident_code": "packaging_path_error",
        "incident_count": 1,
        "outcome_event_kind": "incident",
        "outcome_event_sequence": 1,
        "outcome_recorded_at_utc": recorded_at,
    })
    lane["outcome_events"] = [{
        "event_kind": "incident",
        "event_sequence": 1,
        "recorded_at_utc": recorded_at,
    }]
    lanes.apply_runtime_metadata(
        lane,
        argparse.Namespace(register="tmp/unit-active-outcome-register.json"),
    )
    expect(runtime.get("incident_code") == "packaging_path_error", "active refresh must not erase incident code")
    expect(runtime.get("incident_count") == 1, "active refresh must not erase incident count")
    expect(len(lane["outcome_events"]) == 1, "active refresh must not erase event history")

    register = lanes.empty_register()
    register["lanes"] = [lane]
    active = lanes.validate_active_lease_admission(register)
    expect(active["status"] == "error", "reactivated incident history must fail active admission")
    detail = check_detail(active, "outcome_event_metadata_is_bounded_and_complete")
    baseline_errors = set(detail[0]["errors"])
    expect(
        {
            "active_incident_code_not_clean",
            "active_incident_count_not_zero",
            "active_outcome_events_not_empty",
        }.issubset(baseline_errors),
        "active admission must report every dirty baseline field",
    )

    lane["status"] = "blocked"
    lane["lease_expires_at_utc"] = None
    lane["ended_at_utc"] = recorded_at
    terminal = lanes.validate_register(register)
    terminal_detail = check_detail(
        terminal,
        "outcome_event_metadata_is_bounded_and_complete",
    )
    expect(
        not any(row.get("lane_id") == lane["lane_id"] for row in terminal_detail),
        "valid terminal incident history must remain accepted",
    )


def identity_gap_lane(*, created_at_utc: str, status: str = "cancelled") -> dict:
    lane = completed_model_lane(completed_at_utc="2026-08-22T15:00:01Z")
    lane["lane_id"] = f"WF73::identity-gap-{status}"
    lane["workstream_id"] = f"identity-gap-{status}"
    lane["status"] = status
    lane["created_at_utc"] = created_at_utc
    lane["runtime"].update({
        "phase": "implementation",
        "usage_unavailable_reason": "current_main_session_counters_not_job_scoped",
        "token_attribution_source": "provider_usage_unavailable",
        "max_gross_tokens": 1000,
        "max_cached_replay_tokens": 800,
        "max_tool_calls": 8,
        "max_elapsed_seconds": 60,
        "resource_budget_guard": {
            "status": "partial",
            "limits": {
                "gross_tokens": 1000,
                "cached_replay_tokens": 800,
                "tool_calls": 8,
                "elapsed_seconds": 60,
            },
            "observed": {
                "gross_tokens": None,
                "cached_replay_tokens": None,
                "tool_calls": None,
                "elapsed_seconds": None,
            },
            "breaches": [],
            "early_stop_required": False,
        },
    })
    lane["runtime"].pop("parent_job_id", None)
    lane["runtime"].pop("attempt_number", None)
    lane["runtime"].pop("retry_count", None)
    return lane


def test_pre_wave1_identity_gap_is_warning_not_rewritten() -> None:
    register = lanes.empty_register()
    register["lanes"] = [identity_gap_lane(created_at_utc="2026-08-22T15:00:00Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "pre-Wave-1 terminal identity gap should not remain critical")
    expect(
        "historical_model_lane_identity_gaps_are_classified_not_backfilled" in warning_names(result),
        "historical identity gap should remain visible as a warning",
    )
    expect(
        "new_model_lanes_have_parent_phase_attempt_identity" not in error_names(result),
        "historical identity gap must not be backfilled or treated as a new-lane failure",
    )


def test_post_wave1_identity_gap_remains_fail_closed() -> None:
    register = lanes.empty_register()
    register["lanes"] = [identity_gap_lane(created_at_utc="2026-08-22T15:42:24Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "error", "post-Wave-1 identity gap must fail closed")
    expect(
        "new_model_lanes_have_parent_phase_attempt_identity" in error_names(result),
        "future identity enforcement must remain critical",
    )


def test_active_identity_gap_with_unclassifiable_created_at_fails_closed() -> None:
    for created_at_utc in (None, "not-a-timestamp"):
        register = lanes.empty_register()
        lane = identity_gap_lane(created_at_utc=created_at_utc or "placeholder", status="leased")
        if created_at_utc is None:
            lane.pop("created_at_utc", None)
        else:
            lane["created_at_utc"] = created_at_utc
        lane.pop("completed_at_utc", None)
        lane.pop("ended_at_utc", None)
        lane["lease_expires_at_utc"] = "2099-01-01T00:00:00Z"
        register["lanes"] = [lane]
        result = lanes.validate_register(register)
        expect(result["status"] == "error", "unclassifiable active model identity must fail closed")
        expect(
            "new_model_lanes_have_parent_phase_attempt_identity" in error_names(result),
            "missing or invalid created_at must not bypass active model identity enforcement",
        )


def test_cancelled_lane_accepts_completed_at_as_historical_terminal_end() -> None:
    register = lanes.empty_register()
    lane = completed_model_lane(completed_at_utc="2026-08-16T06:40:00Z")
    lane["lane_id"] = "WF73::legacy-cancelled-terminal"
    lane["status"] = "cancelled"
    lane.pop("ended_at_utc", None)
    register["lanes"] = [lane]
    result = lanes.validate_register(register)
    expect(
        "terminal_lanes_have_ended_at" not in warning_names(result),
        "valid completed_at should prove a historical terminal end without inventing ended_at",
    )
    fallbacks = check_detail(result, "historical_terminal_end_completed_at_fallbacks")
    expect(len(fallbacks) == 1, "completed_at fallback should remain explicitly visible")


def test_future_cancelled_lane_requires_ended_at_despite_completed_at() -> None:
    register = lanes.empty_register()
    lane = identity_gap_lane(created_at_utc="2026-08-22T15:42:24Z")
    lane["lane_id"] = "WF73::future-cancelled-terminal"
    lane["runtime"]["parent_job_id"] = "unit-parent"
    lane["runtime"]["attempt_number"] = 1
    lane["runtime"]["retry_count"] = 0
    lane.pop("ended_at_utc", None)
    register["lanes"] = [lane]
    result = lanes.validate_register(register)
    expect(
        "terminal_lanes_have_ended_at" in warning_names(result),
        "post-cutoff cancelled lane must not use the historical completed_at fallback",
    )
    fallbacks = check_detail(result, "historical_terminal_end_completed_at_fallbacks")
    expect(not fallbacks, "future terminal row must not be mislabeled as a historical fallback")


def terminal_outcome_history_gap_lane(recorded_at_utc: str) -> dict:
    lane = active_implementation_attempt_lane()
    lane["status"] = "blocked"
    lane["lease_expires_at_utc"] = None
    lane["ended_at_utc"] = recorded_at_utc
    lane["runtime"].update({
        "incident_code": "validation_failure",
        "incident_count": 1,
        "outcome_event_kind": "incident",
        "outcome_event_sequence": 1,
        "outcome_recorded_at_utc": recorded_at_utc,
    })
    lane.pop("outcome_events", None)
    return lane


def test_historical_terminal_outcome_history_gap_is_warning_not_backfill() -> None:
    register = lanes.empty_register()
    register["lanes"] = [terminal_outcome_history_gap_lane("2026-08-26T13:57:13Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "proven historical event-history gap should be warning-grade")
    expect(
        "historical_terminal_outcome_event_history_gaps_are_classified_not_backfilled" in warning_names(result),
        "historical event-history gap must remain visible without invented events",
    )
    expect(
        "outcome_event_metadata_is_bounded_and_complete" not in error_names(result),
        "historical event-history gap must not remain a current-contract error",
    )


def test_post_cutover_terminal_outcome_history_gap_fails_closed() -> None:
    register = lanes.empty_register()
    register["lanes"] = [terminal_outcome_history_gap_lane("2026-08-26T13:57:14Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "error", "post-cutover event-history gap must fail closed")
    expect(
        "outcome_event_metadata_is_bounded_and_complete" in error_names(result),
        "future event-history enforcement must remain critical",
    )


def missing_proof_lane(created_at_utc: str) -> dict:
    lane = completed_model_lane(completed_at_utc=created_at_utc)
    lane["runtime"] = {}
    lane["proof_artifacts"] = ["tmp/unit-missing-proof-retention.json"]
    return lane


def test_historical_missing_proof_is_warning_not_retargeted() -> None:
    register = lanes.empty_register()
    register["lanes"] = [missing_proof_lane("2026-08-14T00:00:00Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "historical missing proof should be warning-grade")
    expect(
        "historical_missing_proof_artifacts_are_classified_not_retargeted" in warning_names(result),
        "historical missing proof must remain visible without basename retargeting",
    )
    expect("proof_artifacts_exist" not in error_names(result), "historical proof debt must not remain critical")


def test_post_cutover_missing_proof_fails_closed() -> None:
    register = lanes.empty_register()
    register["lanes"] = [missing_proof_lane("2026-08-22T15:42:23Z")]
    result = lanes.validate_register(register)
    expect(result["status"] == "error", "post-cutover missing proof must fail closed")
    expect("proof_artifacts_exist" in error_names(result), "future proof retention must remain critical")


def test_blocked_route_mismatch_is_warning_incident() -> None:
    register = lanes.empty_register()
    lane = completed_model_lane(completed_at_utc="2026-06-01T00:00:00Z")
    lane["lane_id"] = "WF88::blocked-route-mismatch-incident"
    lane["status"] = "blocked"
    lane["runtime"].update({
        "incident_code": "telemetry_attribution_unavailable",
        "token_attribution_source": "codex_native_rollout_jsonl",
        "expected_model_path": "openai/gpt-5.6-terra",
        "actual_model_path": "openai/gpt-5.6-sol",
        "expected_thinking": "low",
        "actual_thinking": "ultra",
        "expected_execution_backend": "codex_native_subagent",
        "actual_execution_backend": "codex_native_subagent",
    })
    register["lanes"] = [lane]
    result = lanes.validate_register(register)
    expect(result["status"] == "ok", "fail-closed blocked route mismatch should be warning-grade")
    expect(
        "terminal_nonaccepted_route_mismatch_incidents_are_classified" in warning_names(result),
        "blocked route mismatch must remain visible as an incident",
    )
    expect(
        "terminal_codex_native_route_conforms_to_expected_route" not in error_names(result),
        "a nonaccepted route incident must not invalidate the full ledger",
    )


def test_active_admission_keeps_terminal_route_and_proof_debt_visible() -> None:
    register = lanes.empty_register()
    historical = completed_model_lane(completed_at_utc="2026-06-01T00:00:00Z")
    historical["lane_id"] = "WF88::historical-route-proof-debt"
    historical["workstream_id"] = "historical-route-proof-debt"
    historical["proof_artifacts"] = ["tmp/unit-active-admission-missing-proof-20260824.json"]
    historical["runtime"].update({
        "token_attribution_source": "codex_native_rollout_jsonl",
        "expected_model_path": "openai/gpt-5.6-terra",
        "actual_model_path": "openai/gpt-5.6-luna",
        "expected_thinking": "low",
        "actual_thinking": "low",
        "expected_execution_backend": "codex_native_subagent",
        "actual_execution_backend": "codex_native_subagent",
    })
    register["lanes"] = [historical]

    full = lanes.validate_register(register)
    admission = lanes.validate_active_lease_admission(register)
    expect(full["status"] == "error", "terminal debt must remain an error in the full ledger")
    expect(
        "terminal_codex_native_route_conforms_to_expected_route" in error_names(full),
        "terminal route mismatch must remain visible",
    )
    expect(
        "historical_missing_proof_artifacts_are_classified_not_retargeted" in warning_names(full),
        "historical missing proof must remain visible without invented recovery",
    )
    expect("proof_artifacts_exist" not in error_names(full), "pre-cutover missing proof should be warning-grade")
    expect(admission["status"] == "ok", "terminal debt must not block an otherwise empty active projection")


def main() -> None:
    test_completed_model_lane_warns_without_token_closeout()
    test_historical_pre_guard_lane_does_not_warn()
    test_completed_model_lane_accepts_missing_usage_classification()
    test_completed_model_lane_accepts_token_totals()
    test_terminal_outcome_fields_persist_when_valid()
    test_invalid_validator_result_is_rejected()
    test_invalid_closure_durability_is_rejected()
    test_active_model_attempt_materializes_clean_outcome_baseline()
    test_active_incident_history_fails_closed_without_terminal_rewrite()
    test_pre_wave1_identity_gap_is_warning_not_rewritten()
    test_post_wave1_identity_gap_remains_fail_closed()
    test_active_identity_gap_with_unclassifiable_created_at_fails_closed()
    test_cancelled_lane_accepts_completed_at_as_historical_terminal_end()
    test_future_cancelled_lane_requires_ended_at_despite_completed_at()
    test_historical_terminal_outcome_history_gap_is_warning_not_backfill()
    test_post_cutover_terminal_outcome_history_gap_fails_closed()
    test_historical_missing_proof_is_warning_not_retargeted()
    test_post_cutover_missing_proof_fails_closed()
    test_blocked_route_mismatch_is_warning_incident()
    test_active_admission_keeps_terminal_route_and_proof_debt_visible()
    print("concurrent lane token closeout tests passed")


if __name__ == "__main__":
    main()
