from __future__ import annotations

import json
import tempfile
from pathlib import Path

import coding_outcome_ledger as ledger


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def lane(lane_id: str = "WF87::slice") -> dict:
    return {
        "lane_id": lane_id,
        "workflow_id": "WF87",
        "workstream_id": "slice",
        "owner": "test",
        "status": "complete",
        "created_at_utc": "2026-06-12T05:00:00Z",
        "started_at_utc": "2026-06-12T05:01:00Z",
        "completed_at_utc": "2026-06-12T05:06:00Z",
        "allowed_writes": ["scripts/example.py", "tmp/example.json"],
        "acceptance_commands": ["python scripts\\test_example.py"],
        "proof_artifacts": ["tmp/example.json"],
        "runtime": {
            "session_label": "webchat-main",
            "task_name": "wf87-slice",
            "model_path": "openai/gpt-5.5",
            "run_id": "run-wf87-slice",
            "input_tokens": 100,
            "cached_input_tokens": 25,
            "output_tokens": 40,
            "total_tokens": 165,
            "token_attribution_source": "provider_usage",
            "retry_count": 0,
        },
    }


def test_build_record_classifies_script_lane() -> None:
    record = ledger.build_record(lane(), {"status": "ok", "summary": {"recommended_budget": "micro"}})
    assert record["lane_kind"] == "script_or_validator_implementation"
    assert record["duration_minutes"] == 5.0
    assert record["run_reference"].startswith("run_sha256:")
    assert record["session_reference"].startswith("session_sha256:")
    assert record["task_reference"].startswith("task_sha256:")
    assert record["model_path"] == "openai/gpt-5.5"
    assert record["attribution"]["session_present"] is True
    assert record["attribution"]["model_present"] is True
    assert record["attribution"]["token_present"] is True
    assert record["attribution"]["token_source_present"] is True
    assert record["token_usage"]["total_tokens"] == 165
    assert record["token_usage"]["input_tokens_inclusive_cache"] == 100
    assert record["token_usage"]["uncached_input_tokens"] == 75
    assert record["token_usage"]["gross_tokens"] == 140
    assert "inclusive_of_cached_input" in record["token_usage"]["cache_semantics"]
    assert record["token_usage"]["token_attribution_source"] == "provider_usage"
    assert record["coding_outcome"]["proof_attached"] is True
    assert record["coding_outcome"]["validator_proxy_passed"] is True
    assert record["coding_outcome"]["edit_churn"]["script_write_count"] == 1
    assert record["coding_outcome"]["retry_count"] == 0
    assert record["attempt_correlation"] is None
    assert record["authority_boundary"]["trade_execution_allowed"] is False


def test_attempt_correlation_preserves_explicit_safe_metadata() -> None:
    attributed = lane()
    attributed["runtime"].update({
        "parent_job_id": "PM::wf87-parent",
        "phase": " Independent-QA ",
        "attempt_id": "sha256:attempt-2",
        "retry_count": 1,
    })
    record = ledger.build_record(attributed, {"status": "ok", "summary": {}})
    expected = ledger.build_attempt_correlation_key(
        parent_job_id="PM::wf87-parent",
        lane_id="WF87::slice",
        phase="independent_qa",
        attempt_id="sha256:attempt-2",
        retry_count=1,
    )
    assert record["parent_job_id"] == "PM::wf87-parent"
    assert record["phase"] == "independent_qa"
    assert record["attempt_id"] == "sha256:attempt-2"
    assert record["coding_outcome"]["retry_count"] == 1
    assert record["attempt_correlation"] == expected
    assert record["attribution"]["attempt_correlation_present"] is True


def test_retry_correlation_is_nullable_strict_and_backward_compatible() -> None:
    retry_lane = lane()
    retry_lane["runtime"].update({
        "parent_job_id": "PM::wf87-parent",
        "phase": "implementation",
        "retry_count": 2,
    })
    retry_record = ledger.build_record(retry_lane, {"status": "ok", "summary": {}})
    assert retry_record["attempt_id"] is None
    assert retry_record["coding_outcome"]["retry_count"] == 2
    assert retry_record["attempt_correlation"]["attempt_source"] == "retry_count"

    malformed = lane()
    malformed["runtime"].update({
        "parent_job_id": "PM::wf87-parent",
        "phase": "implementation",
        "retry_count": "0",
    })
    malformed_record = ledger.build_record(malformed, {"status": "ok", "summary": {}})
    assert malformed_record["coding_outcome"]["retry_count"] is None
    assert malformed_record["attempt_correlation"] is None

    legacy = lane()
    legacy["runtime"].pop("retry_count")
    legacy_record = ledger.build_record(legacy, {"status": "ok", "summary": {}})
    assert legacy_record["coding_outcome"]["retry_count"] is None
    assert legacy_record["attempt_correlation"] is None
    summary = ledger.summarize_rows([legacy_record])
    assert summary["total_retry_count"] == 0
    assert summary["retry_attributed_count"] == 0
    assert summary["retry_unavailable_count"] == 1
    assert summary["first_pass_clean_count"] == 0
    assert summary["planning_quality_signal"]["gap_reasons"]["retry_count_unavailable"] == 1


def test_append_new_records_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "coding.jsonl"
        record = ledger.build_record(lane(), {"status": "ok", "summary": {}})
        first = ledger.append_new_records([record], path)
        second = ledger.append_new_records([record], path)
        rows = ledger.load_jsonl(path)
        assert first["appended_count"] == 1
        assert second["appended_count"] == 0
        assert len(rows) == 1


def test_new_rows_are_privacy_safe_and_append_without_rewriting_history() -> None:
    marker = "qa-secret-token"
    private = lane("WF87::privacy")
    private["runtime"]["task_name"] = marker
    private["runtime"]["run_id"] = marker
    private["acceptance_commands"] = [f"python {marker}.py"]
    private["proof_artifacts"] = [f"tmp/{marker}.json"]
    private["allowed_writes"] = [f"scripts/{marker}.py"]
    record = ledger.build_record(private, {"status": "ok", "summary": {}})
    serialized = json.dumps(record, sort_keys=True)
    assert marker not in serialized
    assert "task_name" not in record
    assert "acceptance_commands" not in record
    assert "proof_artifacts" not in record
    assert "run_id" not in record["token_usage"]
    assert record["acceptance_command_count"] == 1
    assert record["proof_artifact_count"] == 1
    assert record["acceptance_command_inventory_fingerprint"].startswith("acceptance_commands_sha256:")
    assert record["proof_artifact_inventory_fingerprint"].startswith("proof_artifacts_sha256:")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "coding.jsonl"
        historical = '{"historical":"raw bytes stay untouched"}\n'
        path.write_text(historical, encoding="utf-8")
        ledger.append_new_records([record], path)
        contents = path.read_text(encoding="utf-8")
        assert contents.startswith(historical)
        assert marker not in contents


def test_fresh_path_tokens_preserve_later_retouch_privately() -> None:
    first_lane = lane("WF87::fresh-a")
    first_lane["allowed_writes"] = ["scripts/shared_private.py"]
    first = ledger.build_record(first_lane, {"status": "ok", "summary": {}})
    second_lane = lane("WF87::fresh-b")
    second_lane["allowed_writes"] = ["scripts/shared_private.py"]
    second_lane["started_at_utc"] = "2026-06-13T05:01:00Z"
    second_lane["completed_at_utc"] = "2026-06-13T05:06:00Z"
    second_lane["proof_artifacts"] = []
    second = ledger.build_record(second_lane, {"status": "ok", "summary": {}})
    assert first["reviewable_path_tokens"] == second["reviewable_path_tokens"]
    assert "shared_private.py" not in json.dumps(first)
    reviewed = ledger.apply_ex_post_reviews([first, second])
    assert reviewed[0]["coding_outcome"]["rework_required"] is True
    assert reviewed[0]["coding_outcome"]["later_review_status"] == "undocumented_later_retouch"


def test_ex_post_review_marks_later_retouch_and_first_pass_rate() -> None:
    first = ledger.build_record(lane("WF87::slice-a"), {"status": "ok", "summary": {}})
    first["allowed_writes"] = ["scripts/example.py"]  # historical-row fixture
    second_lane = lane("WF87::slice-b")
    second_lane["started_at_utc"] = "2026-06-13T05:01:00Z"
    second_lane["completed_at_utc"] = "2026-06-13T05:06:00Z"
    second = ledger.build_record(second_lane, {"status": "ok", "summary": {}})
    second["allowed_writes"] = ["scripts/example.py"]  # historical-row fixture

    reviewed = ledger.apply_ex_post_reviews([first, second])
    assert reviewed[0]["coding_outcome"]["rework_required"] is False
    assert reviewed[0]["coding_outcome"]["regression_observed"] is False
    assert reviewed[0]["coding_outcome"]["later_review_status"] == "documented_later_followup"
    assert reviewed[1]["coding_outcome"]["rework_required"] is False
    assert reviewed[1]["coding_outcome"]["later_review_status"] == "clean_after_review_window"

    summary = ledger.summarize_rows([first, second])
    assert summary["ex_post_graded_count"] == 2
    assert summary["rework_required_count"] == 0
    assert summary["first_pass_clean_count"] == 2
    assert summary["first_pass_clean_rate"] == 1.0
    planning = summary["planning_quality_signal"]
    assert planning["schema"] == "veritas.planning_quality_signal.v1"
    assert planning["plan_followthrough_gap_count"] == 0
    assert planning["documented_later_followup_count"] == 1
    claim_gate = summary["model_performance_claim_gate"]
    assert claim_gate["model_performance_claim_allowed"] is False
    assert claim_gate["review_only_process_metric_available"] is True
    assert claim_gate["graded_count"] == 2
    assert claim_gate["sample_gate_met"] is False


def test_undocumented_later_retouch_stays_a_gap() -> None:
    first = ledger.build_record(lane("WF87::slice-a"), {"status": "ok", "summary": {}})
    first["allowed_writes"] = ["scripts/example.py"]  # historical-row fixture
    second_lane = lane("WF87::slice-b")
    second_lane["started_at_utc"] = "2026-06-13T05:01:00Z"
    second_lane["completed_at_utc"] = "2026-06-13T05:06:00Z"
    second_lane["proof_artifacts"] = []
    second = ledger.build_record(second_lane, {"status": "ok", "summary": {}})
    second["allowed_writes"] = ["scripts/example.py"]  # historical-row fixture

    reviewed = ledger.apply_ex_post_reviews([first, second])
    assert reviewed[0]["coding_outcome"]["rework_required"] is True
    assert reviewed[0]["coding_outcome"]["later_review_status"] == "undocumented_later_retouch"

    summary = ledger.summarize_rows([first, second])
    planning = summary["planning_quality_signal"]
    assert planning["plan_followthrough_gap_count"] == 2
    assert planning["gap_reasons"]["later_rework"] == 1
    assert planning["gap_reasons"]["missing_proof"] == 1
    assert summary["model_performance_claim_gate"]["model_performance_claim_allowed"] is False


def test_legacy_validator_unknown_is_attention_not_hard_gap() -> None:
    record = ledger.build_record(lane(), {"status": "ok", "summary": {}})
    record["coding_outcome"]["validator_proxy_passed"] = None

    summary = ledger.summarize_rows([record])
    planning = summary["planning_quality_signal"]
    assert summary["validator_unknown_legacy_count"] == 1
    assert planning["legacy_validator_unknown_count"] == 1
    assert planning["plan_followthrough_gap_count"] == 0
    assert planning["plan_followthrough_clean_rate"] == 1.0


def test_legacy_proof_remediation_closes_known_historical_missing_proof() -> None:
    historical = ledger.build_record(
        lane("WF78::tier-label-preview-audit-flag"),
        {"status": "ok", "summary": {}},
    )
    historical["lane_id"] = "WF78::tier-label-preview-audit-flag"  # historical-row fixture
    historical["proof_artifacts"] = []
    historical["proof_artifact_count"] = 0
    historical["coding_outcome"]["proof_attached"] = False

    reviewed = ledger.apply_ex_post_reviews([historical])
    assert reviewed[0]["coding_outcome"]["proof_attached"] is True
    assert reviewed[0]["coding_outcome"]["proof_remediated"] is True

    summary = ledger.summarize_rows([historical])
    assert summary["proof_remediated_count"] == 1
    assert summary["planning_quality_signal"]["plan_followthrough_gap_count"] == 0


def routed_lane(lane_id: str, *, thinking: str = "medium", backend: str = "persistent_isolated_agent") -> dict:
    attributed = lane(lane_id)
    attributed["allowed_writes"] = [f"scripts/{lane_id.lower().replace(':', '_')}.py"]
    attributed["runtime"].update({
        "expected_model_path": "openai/gpt-5.6-terra",
        "expected_thinking": thinking,
        "expected_execution_backend": backend,
        "actual_model_path": "openai/gpt-5.6-terra",
        "actual_thinking": thinking,
        "actual_execution_backend": backend,
        "task_shape": "implementation",
        "authority_class": "owner_gated",
        "write_scope": "single_surface",
        "main_accepted": True,
    })
    return attributed


def post_cutover_uncredited_lane(lane_id: str = "RUNTIME::uncredited") -> dict:
    """A realistic forged/unavailable closeout must never earn metrics."""
    attributed = routed_lane(lane_id, backend="codex_native_subagent")
    attributed.update({
        "created_at_utc": "2026-08-13T21:00:00Z",
        "started_at_utc": "2026-08-13T21:01:00Z",
        "completed_at_utc": "2026-08-13T21:06:00Z",
    })
    attributed["runtime"].update({
        "parent_job_id": "RUNTIME::uncredited-parent",
        "phase": "implementation",
        "attempt_id": "uncredited-attempt",
        "main_acceptance_status": "accepted",
        "token_attribution_source": "provider_usage_unavailable",
        "usage_creditable": False,
        "usage_credit_status": "blocked",
    })
    return attributed


def test_post_cutover_missing_or_forged_receipt_cannot_enter_efficiency_metrics() -> None:
    uncredited = ledger.build_record(post_cutover_uncredited_lane(), {"status": "ok", "summary": {}})
    assert uncredited["token_usage"]["usage_creditable"] is False
    assert uncredited["token_usage"]["usage_credit_status"] == "blocked"
    assert uncredited["token_usage"]["usage_source_receipt_verified"] is False
    assert uncredited["token_usage"]["total_tokens"] is None
    assert uncredited["coding_outcome"]["telemetry_credit_eligible"] is False
    assert ledger.route_accepted(uncredited) is False
    assert ledger.first_pass_accepted(uncredited) is False
    assert uncredited["comparable_cohort_key"] is None
    summary = ledger.summarize_rows([uncredited])
    assert summary["quality_row_count"] == 0
    assert summary["telemetry_uncreditable_row_count"] == 1
    parent = summary["parent_jobs"]["RUNTIME::uncredited-parent"]
    assert parent["telemetry"] == {"creditable_row_count": 0, "uncreditable_row_count": 1}
    assert parent["completion"] == {"denominator": 0, "completed_count": 0}
    assert parent["main_acceptance"] == {"denominator": 0, "accepted_count": 0}


def test_post_cutover_declared_false_cannot_restore_historical_efficiency_credit() -> None:
    forged = ledger.build_record(post_cutover_uncredited_lane("RUNTIME::declared-false"), {"status": "ok", "summary": {}})
    forged["token_usage"].update({
        "credit_enforcement_required": False,
        "usage_creditable": False,
        "usage_credit_status": "blocked",
        "usage_source_receipt_verified": False,
    })
    forged["coding_outcome"].update({"telemetry_credit_eligible": False, "regression_observed": False})
    assert ledger.row_requires_creditable_usage(forged) is True
    assert ledger.telemetry_metrics_eligible(forged) is False
    assert ledger.route_accepted(forged) is False
    assert forged["comparable_cohort_key"] is None


def test_route_mismatch_fails_closed_and_legacy_is_unavailable() -> None:
    matching = ledger.build_record(routed_lane("WF87::route-match"), {"status": "ok", "summary": {}})
    assert matching["route_attribution"]["route_conformance"] == "conformant"
    assert matching["coding_outcome"]["route_mismatch_fail_closed"] is False
    assert matching["comparable_cohort_key"]

    mismatch_lane = routed_lane("WF87::route-mismatch")
    mismatch_lane["runtime"]["actual_thinking"] = "high"
    mismatch = ledger.build_record(mismatch_lane, {"status": "ok", "summary": {}})
    assert mismatch["route_attribution"]["route_conformance"] == "mismatch"
    assert mismatch["coding_outcome"]["route_mismatch_fail_closed"] is True
    assert mismatch["comparable_cohort_key"] is None

    legacy = ledger.build_record(lane("WF87::legacy-route"), {"status": "ok", "summary": {}})
    assert legacy["route_attribution"]["route_conformance"] == "unavailable_legacy"
    assert legacy["comparable_cohort_key"] is None


def test_lane_manager_thinking_field_is_observed_route_effort() -> None:
    live_shape = routed_lane("WF87::live-thinking-shape")
    live_shape["runtime"]["thinking"] = live_shape["runtime"].pop("actual_thinking")
    record = ledger.build_record(live_shape, {"status": "ok", "summary": {}})
    assert record["route_attribution"]["actual_thinking"] == "medium"
    assert record["route_attribution"]["route_conformance"] == "conformant"
    assert record["comparable_cohort_key"]


def test_comparable_cohorts_keep_route_shapes_separate_and_gate_samples() -> None:
    rows = []
    for index in range(10):
        routed = routed_lane(f"WF87::cohort-{index}")
        routed["started_at_utc"] = f"2026-06-{index + 1:02d}T05:01:00Z"
        routed["completed_at_utc"] = f"2026-06-{index + 1:02d}T05:06:00Z"
        record = ledger.build_record(routed, {"status": "ok", "summary": {}})
        record["coding_outcome"].update({"rework_required": False, "regression_observed": False})
        rows.append(record)
    separated = ledger.build_record(
        routed_lane("WF87::cohort-high", thinking="high"),
        {"status": "ok", "summary": {}},
    )
    rows.append(separated)
    summary = ledger.summarize_rows(rows)
    cohorts = summary["comparable_cohorts"]
    assert len(cohorts) == 2
    medium = next(item for key, item in cohorts.items() if key.endswith("|medium"))
    high = next(item for key, item in cohorts.items() if key.endswith("|high"))
    assert medium["accepted_count"] == 10
    assert medium["first_pass_accepted_count"] == 10
    assert medium["gross_input_tokens"] == 1000
    assert medium["uncached_input_tokens"] == 750
    assert medium["output_tokens"] == 400
    assert medium["elapsed_minutes"] == 50.0
    assert medium["retry_tax"]["total_retry_count"] == 0
    assert medium["sample_gate_met"] is True
    assert medium["route_ranking_or_promotion_allowed"] is False
    assert high["accepted_count"] == 1
    assert high["sample_gate_met"] is False
    assert summary["comparable_cohort_sample_gate"]["required_accepted_count"] == 10
    assert summary["model_performance_claim_gate"]["model_performance_claim_allowed"] is False


def test_controlled_main_acceptance_status_overrides_legacy_boolean() -> None:
    accepted = routed_lane("WF87::status-accepted")
    accepted["runtime"].update({"main_acceptance_status": "accepted-with-documented-limits", "main_accepted": False})
    accepted_record = ledger.build_record(accepted, {"status": "ok", "summary": {}})
    assert accepted_record["route_attribution"]["main_accepted"] is True
    assert accepted_record["route_attribution"]["main_acceptance_status"] == "accepted-with-documented-limits"
    for status in ("pending", "rework-requested", "rejected", "not-applicable"):
        rejected = routed_lane(f"WF87::status-{status}")
        rejected["runtime"].update({"main_acceptance_status": status, "main_accepted": True})
        assert ledger.build_record(rejected, {"status": "ok", "summary": {}})["route_attribution"]["main_accepted"] is False
    legacy = ledger.build_record(routed_lane("WF87::status-legacy"), {"status": "ok", "summary": {}})
    assert legacy["route_attribution"]["main_acceptance_status"] is None
    assert legacy["route_attribution"]["main_accepted"] is True


def test_parent_aggregation_preserves_handoff_and_excludes_incidents_from_denominators() -> None:
    first = routed_lane("WF87::parent-first")
    first["runtime"].update({
        "parent_job_id": "PM::bounded-parent", "phase": "implementation", "attempt_id": "attempt-1",
        "handoff_file_count": 2, "handoff_total_bytes": 80, "handoff_context_tokens": 20,
    })
    first_record = ledger.build_record(first, {"status": "ok", "summary": {}})
    first_record["coding_outcome"].update({"rework_required": False, "regression_observed": False})
    incident = routed_lane("WF87::parent-incident")
    # The real incident signal is controlled runtime metadata, not a lane
    # status that concurrent_lane_manager never emits.  A contradictory
    # complete status must still fail closed for quality denominators.
    incident["runtime"].update({"parent_job_id": "PM::bounded-parent", "phase": "qa", "attempt_id": "attempt-2", "retry_count": 1, "outcome_event_kind": "incident", "incident_code": "test-incident"})
    incident_record = ledger.build_record(incident, {"status": "ok", "summary": {}})
    parent = ledger.summarize_rows([first_record, incident_record])["parent_jobs"]["PM::bounded-parent"]
    assert parent["phase_count"] == 2
    assert parent["attempt_count"] == 2
    assert parent["retry_tax"]["total_retry_count"] == 1
    assert parent["completion"] == {"denominator": 1, "completed_count": 1}
    assert parent["qa"] == {"denominator": 0, "passed_count": 0, "failed_count": 0}
    assert parent["main_acceptance"] == {"denominator": 1, "accepted_count": 1}
    assert parent["handoff"]["file_count"] is None
    assert parent["handoff"]["coverage"]["handoff_file_count"] == {"value": None, "observed_partial_sum": 2, "available_count": 1, "missing_count": 1, "total_row_count": 2, "status": "partial"}
    assert parent["incident_row_count"] == 1
    assert incident_record["coding_outcome"]["outcome_event_kind"] == "incident"
    assert incident_record["coding_outcome"]["incident_code"] == "test-incident"
    missing = ledger.build_record(routed_lane("WF87::handoff-missing"), {"status": "ok", "summary": {}})
    assert missing["route_attribution"]["handoff_file_count"] is None
    assert missing["route_attribution"]["handoff_total_bytes"] is None
    assert missing["route_attribution"]["handoff_context_tokens"] is None


def actionable_routed_lane(lane_id: str) -> dict:
    attributed = routed_lane(lane_id)
    attributed["runtime"].update({
        "parent_job_id": "PM::history-partition",
        "phase": "implementation",
        "attempt_id": f"attempt-{lane_id}",
        "main_acceptance_status": "accepted",
    })
    return attributed


def test_recent_unresolved_gap_stays_actionable() -> None:
    unresolved = ledger.build_record(actionable_routed_lane("WF87::history-recent"), {"status": "ok", "summary": {}})
    unresolved["coding_outcome"]["proof_attached"] = False
    unresolved["proof_artifact_count"] = 0
    summary = ledger.summarize_rows([unresolved])
    planning = summary["planning_quality_signal"]
    assert planning["plan_followthrough_gap_count"] == 1
    assert planning["plan_followthrough_actionable_gap_count"] == 1
    assert planning["plan_followthrough_terminal_unavailable_count"] == 0
    assert planning["plan_followthrough_repaired_accepted_count"] == 0
    assert planning["gap_partitions"]["actionable_unresolved"]["row_count"] == 1
    assert planning["partition_reconciliation_ok"] is True


def test_historical_terminal_unavailable_partitions_out_of_actionable() -> None:
    legacy_input = lane("WF87::history-legacy")
    legacy_input["runtime"].pop("retry_count")
    historical = ledger.build_record(legacy_input, {"status": "ok", "summary": {}})
    assert historical["route_attribution"]["route_conformance"] == "unavailable_legacy"
    assert historical["coding_outcome"]["retry_count"] is None
    summary = ledger.summarize_rows([historical])
    planning = summary["planning_quality_signal"]
    # Raw totals preserved: the unavailable-retry event still counts raw.
    assert planning["plan_followthrough_gap_count"] == 1
    assert planning["gap_reasons"].get("retry_count_unavailable") == 1
    assert planning["plan_followthrough_terminal_unavailable_count"] == 1
    assert planning["plan_followthrough_actionable_gap_count"] == 0
    assert planning["gap_partitions"]["terminal_known_unavailable"]["row_count"] == 1
    assert planning["partition_reconciliation_ok"] is True


def test_accepted_after_retry_partitions_as_repaired_with_raw_totals_retained() -> None:
    record = ledger.build_record(actionable_routed_lane("WF87::history-repaired"), {"status": "ok", "summary": {}})
    record["coding_outcome"]["retry_count"] = 2
    assert record["coding_outcome"]["proof_attached"] is True
    assert record["route_attribution"]["main_accepted"] is True
    assert ledger.explicit_main_acceptance(record) is True
    summary = ledger.summarize_rows([record])
    planning = summary["planning_quality_signal"]
    assert planning["plan_followthrough_gap_count"] == 1
    assert planning["gap_reasons"].get("retry_required") == 1
    assert summary["total_retry_count"] == 2
    assert planning["plan_followthrough_repaired_accepted_count"] == 1
    assert planning["plan_followthrough_actionable_gap_count"] == 0
    assert planning["gap_partitions"]["repaired_accepted_retry"]["row_count"] == 1
    assert planning["partition_reconciliation_ok"] is True


def test_partition_reconciliation_across_mixed_history() -> None:
    recent = ledger.build_record(actionable_routed_lane("WF87::history-mix-recent"), {"status": "ok", "summary": {}})
    recent["coding_outcome"]["proof_attached"] = False
    recent["proof_artifact_count"] = 0
    legacy_input = lane("WF87::history-mix-legacy")
    legacy_input["runtime"].pop("retry_count")
    legacy = ledger.build_record(legacy_input, {"status": "ok", "summary": {}})
    fixed = ledger.build_record(actionable_routed_lane("WF87::history-mix-fixed"), {"status": "ok", "summary": {}})
    fixed["coding_outcome"]["retry_count"] = 1
    summary = ledger.summarize_rows([recent, legacy, fixed])
    planning = summary["planning_quality_signal"]
    assert planning["plan_followthrough_gap_count"] == 3
    assert planning["partitioned_gap_row_count"] == 3
    assert planning["partition_reconciliation_ok"] is True
    assert planning["plan_followthrough_actionable_gap_count"] == 1
    assert planning["plan_followthrough_terminal_unavailable_count"] == 1
    assert planning["plan_followthrough_repaired_accepted_count"] == 1
    # Compatible raw fields unchanged in meaning.
    assert planning["hard_gap_count"] == 3
    assert planning["status"] == "attention"
    assert planning["actionable_status"] == "attention"


def test_malformed_unknown_history_fails_closed_as_actionable() -> None:
    # Retry required WITHOUT proof: must never partition as repaired.
    unproven = ledger.build_record(actionable_routed_lane("WF87::history-unproven"), {"status": "ok", "summary": {}})
    unproven["coding_outcome"]["retry_count"] = 3
    unproven["coding_outcome"]["proof_attached"] = False
    unproven["proof_artifact_count"] = 0
    assert ledger.planning_history_partition(unproven) == "actionable_unresolved"
    # Missing retry on a conformant current-shape row: actionable, not terminal.
    conformant_missing = ledger.build_record(actionable_routed_lane("WF87::history-conformant-missing"), {"status": "ok", "summary": {}})
    conformant_missing["coding_outcome"]["retry_count"] = None
    assert conformant_missing["route_attribution"]["route_conformance"] == "conformant"
    assert ledger.planning_history_partition(conformant_missing) == "actionable_unresolved"
    # Unknown/malformed retry value with otherwise-clean content: actionable.
    malformed = ledger.build_record(actionable_routed_lane("WF87::history-malformed"), {"status": "ok", "summary": {}})
    malformed["coding_outcome"]["retry_count"] = "1"
    assert ledger.planning_gap_reasons_for_row(malformed) == ["retry_count_unavailable"] or "retry_count_unavailable" in ledger.planning_gap_reasons_for_row(malformed)
    assert ledger.planning_history_partition(malformed) == "actionable_unresolved"
    summary = ledger.summarize_rows([unproven, conformant_missing, malformed])
    planning = summary["planning_quality_signal"]
    assert planning["plan_followthrough_gap_count"] == 3
    assert planning["plan_followthrough_actionable_gap_count"] == 3
    assert planning["plan_followthrough_terminal_unavailable_count"] == 0
    assert planning["plan_followthrough_repaired_accepted_count"] == 0
    assert planning["partition_reconciliation_ok"] is True


def test_pre_cutover_uninstrumented_missing_retry_is_terminal() -> None:
    base = lane("WF87::history-precutover")
    base["runtime"].pop("retry_count")
    row = ledger.build_record(base, {"status": "ok", "summary": {}})
    row["route_attribution"] = {}
    assert ledger.history_pre_cutover_uninstrumented(row) is True
    assert ledger.planning_history_partition(row) == "terminal_known_unavailable"
    summary = ledger.summarize_rows([row])
    planning = summary["planning_quality_signal"]
    assert planning["plan_followthrough_gap_count"] == 1
    assert planning["gap_reasons"].get("retry_count_unavailable") == 1
    assert planning["plan_followthrough_terminal_unavailable_count"] == 1
    assert planning["plan_followthrough_actionable_gap_count"] == 0
    assert planning["partition_reconciliation_ok"] is True


def test_post_cutover_missing_route_stays_actionable() -> None:
    row = {
        "created_at_utc": "2026-09-10T05:00:00Z",
        "completed_at_utc": "2026-09-10T05:06:00Z",
        "route_attribution": {},
        "coding_outcome": {
            "implementation_completed": True,
            "acceptance_commands_declared": True,
            "proof_attached": True,
            "validator_proxy_passed": True,
            "retry_count": None,
        },
    }
    assert ledger.history_pre_cutover_uninstrumented(row) is False
    assert ledger.planning_gap_reasons_for_row(row) == ["retry_count_unavailable"]
    assert ledger.planning_history_partition(row) == "actionable_unresolved"


def test_malformed_timestamp_missing_retry_stays_actionable() -> None:
    row = {
        "created_at_utc": "not-a-timestamp",
        "completed_at_utc": "also-bad",
        "route_attribution": {},
        "coding_outcome": {
            "implementation_completed": True,
            "acceptance_commands_declared": True,
            "proof_attached": True,
            "validator_proxy_passed": True,
            "retry_count": None,
        },
    }
    assert ledger.history_pre_cutover_uninstrumented(row) is False
    assert ledger.planning_gap_reasons_for_row(row) == ["retry_count_unavailable"]
    assert ledger.planning_history_partition(row) == "actionable_unresolved"


def test_parent_aggregation_uses_phase_status_aware_denominators() -> None:
    implementation = routed_lane("WF87::multi-implementation")
    implementation["runtime"].update({"parent_job_id": "PM::multi-phase", "phase": "implementation", "attempt_id": "impl", "main_acceptance_status": "accepted"})
    implementation_record = ledger.build_record(implementation, {"status": "ok", "summary": {}})
    implementation_record["coding_outcome"].update({"rework_required": False, "regression_observed": False})

    qa = routed_lane("WF87::multi-qa")
    qa["runtime"].update({"parent_job_id": "PM::multi-phase", "phase": "qa", "attempt_id": "qa", "main_acceptance_status": "pending"})
    qa_record = ledger.build_record(qa, {"status": "ok", "summary": {}})

    proof = routed_lane("WF87::multi-proof")
    proof["runtime"].update({"parent_job_id": "PM::multi-phase", "phase": "handoff", "attempt_id": "handoff"})
    proof["runtime"].pop("main_accepted")
    proof_record = ledger.build_record(proof, {"status": "ok", "summary": {}})

    pending_implementation = routed_lane("WF87::multi-pending")
    pending_implementation.update({"status": "running"})
    pending_implementation["runtime"].update({"parent_job_id": "PM::multi-phase", "phase": "implementation", "attempt_id": "pending"})
    pending_implementation["runtime"].pop("main_accepted")
    pending_record = ledger.build_record(pending_implementation, {"status": "ok", "summary": {}})

    parent = ledger.summarize_rows([implementation_record, qa_record, proof_record, pending_record])["parent_jobs"]["PM::multi-phase"]
    assert parent["completion"] == {"denominator": 1, "completed_count": 1}
    assert parent["qa"] == {"denominator": 1, "passed_count": 1, "failed_count": 0}
    assert parent["main_acceptance"] == {"denominator": 2, "accepted_count": 1}
    assert parent["first_pass_accepted_count"] == 1


def test_incidents_are_excluded_from_global_quality_and_cohort_yield() -> None:
    incident = routed_lane("WF87::global-incident")
    incident["runtime"].update({"outcome_event_kind": "incident", "main_acceptance_status": "accepted"})
    record = ledger.build_record(incident, {"status": "ok", "summary": {}})
    record["coding_outcome"].update({"rework_required": False, "regression_observed": False})
    summary = ledger.summarize_rows([record])
    assert record["lane_status"] == "complete"
    assert ledger.route_accepted(record) is False
    assert ledger.first_pass_accepted(record) is False
    assert record["comparable_cohort_key"] is None
    assert summary["first_pass_clean_count"] == 0
    assert summary["ex_post_graded_count"] == 0
    assert summary["incident_row_count"] == 1
    assert summary["comparable_cohorts"] == {}


def test_token_availability_and_partial_aggregate_coverage() -> None:
    cached_only = routed_lane("WF87::cached-only")
    cached_only["runtime"].pop("input_tokens")
    cached_only["runtime"].pop("output_tokens")
    cached_only["runtime"].pop("total_tokens")
    cached_only["runtime"].update({"cached_input_tokens": 25})
    cached_record = ledger.build_record(cached_only, {"status": "ok", "summary": {}})
    usage = cached_record["token_usage"]
    assert usage["total_tokens"] is None
    assert usage["gross_tokens"] is None
    assert usage["uncached_input_tokens"] is None

    impossible = routed_lane("WF87::impossible-cache")
    impossible["runtime"].update({"input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 3})
    impossible_record = ledger.build_record(impossible, {"status": "ok", "summary": {}})
    assert impossible_record["token_usage"]["uncached_input_tokens"] is None
    assert impossible_record["token_usage"]["gross_tokens"] is None
    assert impossible_record["token_usage"]["integrity_status"] == "invalid_cache_relationship"
    assert impossible_record["token_usage"]["integrity_reason"] == "cached_input_tokens_exceeds_input_tokens"
    assert impossible_record["token_usage"]["non_authoritative_observed_components"] == {"input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 3}

    invalid_parent = routed_lane("WF87::invalid-cache-parent")
    invalid_parent["runtime"].update({"parent_job_id": "PM::invalid-cache", "phase": "implementation", "input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 3})
    invalid_summary = ledger.summarize_rows([ledger.build_record(invalid_parent, {"status": "ok", "summary": {}})])
    invalid_token = invalid_summary["parent_jobs"]["PM::invalid-cache"]["token_usage"]
    assert invalid_token["gross_tokens"] is None
    assert invalid_token["coverage"]["gross_tokens"]["status"] == "unavailable"

    complete = routed_lane("WF87::coverage-complete")
    complete["runtime"].update({"parent_job_id": "PM::coverage", "phase": "implementation", "handoff_file_count": 1, "handoff_total_bytes": 10, "handoff_context_tokens": 2})
    missing = routed_lane("WF87::coverage-missing")
    missing["runtime"].update({"parent_job_id": "PM::coverage", "phase": "qa"})
    missing["runtime"].pop("input_tokens")
    missing["runtime"].pop("cached_input_tokens")
    missing["runtime"].pop("output_tokens")
    complete_record = ledger.build_record(complete, {"status": "ok", "summary": {}})
    missing_record = ledger.build_record(missing, {"status": "ok", "summary": {}})
    coverage_summary = ledger.summarize_rows([complete_record, missing_record])
    parent = coverage_summary["parent_jobs"]["PM::coverage"]
    gross = parent["token_usage"]["coverage"]["gross_tokens"]
    handoff = parent["handoff"]["coverage"]["handoff_file_count"]
    assert parent["token_usage"]["gross_tokens"] is None
    assert gross == {"value": None, "observed_partial_sum": 140, "available_count": 1, "missing_count": 1, "total_row_count": 2, "status": "partial"}
    assert parent["handoff"]["file_count"] is None
    assert handoff == {"value": None, "observed_partial_sum": 1, "available_count": 1, "missing_count": 1, "total_row_count": 2, "status": "partial"}
    assert parent["handoff"]["coverage"]["handoff_total_bytes"]["status"] == "partial"
    assert parent["handoff"]["coverage"]["handoff_context_tokens"]["status"] == "partial"
    cohort = next(iter(coverage_summary["comparable_cohorts"].values()))
    assert cohort["gross_tokens"] is None
    assert cohort["token_coverage"]["gross_tokens"] == gross

    unavailable = ledger.metric_coverage([missing], "handoff_file_count")
    assert unavailable == {"value": None, "observed_partial_sum": None, "available_count": 0, "missing_count": 1, "total_row_count": 1, "status": "unavailable"}


def test_invalid_cache_rows_cannot_receive_efficiency_credit() -> None:
    rows = []
    for index in range(10):
        invalid = routed_lane(f"WF87::invalid-{index}")
        invalid["runtime"].update({
            "parent_job_id": "PM::invalid-cohort", "phase": "implementation",
            "input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 3,
            "main_acceptance_status": "accepted",
        })
        record = ledger.build_record(invalid, {"status": "ok", "summary": {}})
        record["coding_outcome"].update({"rework_required": False, "regression_observed": False})
        assert ledger.route_accepted(record) is False
        assert ledger.first_pass_accepted(record) is False
        assert record["comparable_cohort_key"] is None
        rows.append(record)
    summary = ledger.summarize_rows(rows)
    assert summary["invalid_token_integrity_row_count"] == 10
    assert summary["main_accepted_count"] == 0
    assert summary["first_pass_clean_count"] == 0
    assert summary["comparable_cohorts"] == {}
    parent = summary["parent_jobs"]["PM::invalid-cohort"]
    assert parent["first_pass_accepted_count"] == 0
    assert parent["main_acceptance"] == {"denominator": 0, "accepted_count": 0}


def test_build_current_warns_on_source_register_validation_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        register = write_json(
            base / "register.json",
            {
                "status": "error",
                "lanes": [lane()],
                "summary": {"active_lane_count": 0},
                "validation": {"errors": 1, "warnings": 0},
            },
        )
        router = write_json(base / "router.json", {"status": "ok", "summary": {"changed_path_count": 1}})
        durable = base / "coding.jsonl"
        record = ledger.build_record(lane(), {"status": "ok", "summary": {}})
        ledger.append_new_records([record], durable)
        current = ledger.build_current(register, router, durable)
        assert current["status"] == "warning"
        assert "source_lane_register_has_validation_errors" in current["validation"]["warnings"]


if __name__ == "__main__":
    test_build_record_classifies_script_lane()
    test_attempt_correlation_preserves_explicit_safe_metadata()
    test_retry_correlation_is_nullable_strict_and_backward_compatible()
    test_append_new_records_is_idempotent()
    test_new_rows_are_privacy_safe_and_append_without_rewriting_history()
    test_fresh_path_tokens_preserve_later_retouch_privately()
    test_ex_post_review_marks_later_retouch_and_first_pass_rate()
    test_undocumented_later_retouch_stays_a_gap()
    test_legacy_validator_unknown_is_attention_not_hard_gap()
    test_legacy_proof_remediation_closes_known_historical_missing_proof()
    test_recent_unresolved_gap_stays_actionable()
    test_historical_terminal_unavailable_partitions_out_of_actionable()
    test_accepted_after_retry_partitions_as_repaired_with_raw_totals_retained()
    test_partition_reconciliation_across_mixed_history()
    test_malformed_unknown_history_fails_closed_as_actionable()
    test_pre_cutover_uninstrumented_missing_retry_is_terminal()
    test_post_cutover_missing_route_stays_actionable()
    test_malformed_timestamp_missing_retry_stays_actionable()
    test_post_cutover_missing_or_forged_receipt_cannot_enter_efficiency_metrics()
    test_post_cutover_declared_false_cannot_restore_historical_efficiency_credit()
    test_route_mismatch_fails_closed_and_legacy_is_unavailable()
    test_comparable_cohorts_keep_route_shapes_separate_and_gate_samples()
    test_controlled_main_acceptance_status_overrides_legacy_boolean()
    test_parent_aggregation_preserves_handoff_and_excludes_incidents_from_denominators()
    test_parent_aggregation_uses_phase_status_aware_denominators()
    test_incidents_are_excluded_from_global_quality_and_cohort_yield()
    test_token_availability_and_partial_aggregate_coverage()
    test_invalid_cache_rows_cannot_receive_efficiency_credit()
    test_build_current_warns_on_source_register_validation_error()
    print("coding_outcome_ledger_tests_passed")
