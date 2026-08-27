from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rsi_outcome_scorecard.py"
FIXTURES = ROOT / "data" / "evals" / "rsi-outcome-scorecard-fixtures.json"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("rsi_outcome_scorecard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_document() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def fixture_case(case_id: str) -> dict:
    for case in fixture_document()["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"fixture not found: {case_id}")


def score_fixture(module, case_id: str) -> dict:
    case = fixture_case(case_id)
    return module.score_lineage(
        row_id=case["case_id"],
        title=case["title"],
        source_class="synthetic_metadata_fixture",
        lineage=case["lineage"],
        source_refs=["data/evals/rsi-outcome-scorecard-fixtures.json"],
    )


def safe_trace_boundary() -> dict:
    return {
        "review_only": True,
        "trace_packet_only": True,
        "derived_routing_proof_only": True,
        "auto_apply_allowed": False,
        "cron_schedule_mutation_allowed": False,
        "config_auth_runtime_mutation_allowed": False,
        "sql_or_source_mutation_allowed": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "cash_sizing_risk_mutation_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "customer_or_external_output_allowed": False,
        "model_training_claim_allowed": False,
        "raw_prompt_or_response_capture_allowed": False,
        "raw_tool_payload_capture_allowed": False,
        "owner_approval_inferred": False,
    }


def live_trace(*, owner_gated: bool = False) -> dict:
    if owner_gated:
        route_status = "monitor_or_owner_gated"
        decision_state = "monitor_only"
        pm_job_id = None
        pm_job_status = None
    else:
        route_status = "pm_job_candidate"
        decision_state = "fix_now"
        pm_job_id = "pm-test-rsi"
        pm_job_status = "completed_by_ledger"
    return {
        "schema": "veritas.wf74_wf88_loop_trace_packet.v1",
        "status": "loop_trace_warning_no_apply_authority",
        "authority_boundary": safe_trace_boundary(),
        "source_spine": {"implementation_token_gap_count": 1, "token_event_count": 2},
        "trace_rows": [
            {
                "trace_id": "trace-test-owner" if owner_gated else "trace-test",
                "opportunity_id": "opportunity-test-owner" if owner_gated else "opportunity-test",
                "title": "Owner-gated proof" if owner_gated else "Close a routed regression",
                "signal": "synthetic_live_metadata_signal",
                "completion_status": "open",
                "decision_docket_id": "docket-test",
                "decision_action_state": decision_state,
                "route_status": route_status,
                "route": "owner_packet" if owner_gated else "implementation_lane",
                "pm_job_id": pm_job_id,
                "pm_job_status": pm_job_status,
                "pm_job_lane_id": "owner_packet" if owner_gated else "implementation_lane",
                "lane_id": None,
                "lane_status": None,
                "lane_completed_at_utc": None,
                "memory_refs": [{"path": "memory/2026-07-01.md", "line": 1}],
                "missing_links": [],
                "authority_boundary": {
                    "review_only": True,
                    "trace_row_only": True,
                    "auto_apply_allowed": False,
                    "owner_approval_inferred": False,
                },
            }
        ],
    }


def exact_ref(*, event_kind: str, lifecycle_id: str, record_id: str, recommendation_id: str | None = None, ledger_event_id: str | None = None) -> dict:
    ref = {
        "schema": "veritas.wf74_rsi_review_event_ref.v1",
        "metadata_only": True,
        "link_status": "linked_exact",
        "event_kind": event_kind,
        "lifecycle_id": lifecycle_id,
        "source_path": (
            "data/state-history/coding-outcome-ledger.jsonl"
            if event_kind == "coding_outcome_event"
            else "data/state-history/recommendation-outcome-grades.jsonl"
        ),
        "record_id": record_id,
        "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
    }
    if recommendation_id:
        ref["recommendation_id"] = recommendation_id
    if ledger_event_id:
        ref["ledger_event_id"] = ledger_event_id
    return ref


def test_required_metadata_fixtures_classify_as_expected() -> None:
    module = load_module()
    fixtures = fixture_document()
    report, rows = module.build_fixture_evaluation(fixtures)

    assert fixtures["schema"] == module.FIXTURE_SCHEMA
    assert fixtures["metadata_only"] is True
    assert report["status"] == "ok"
    assert report["fixture_count"] == 7
    assert report["passed_count"] == 7
    assert report["failed_count"] == 0
    assert report["excluded_from_live_maturity"] is True
    assert set(report["fixture_ids"]) == module.REQUIRED_FIXTURE_IDS
    assert len(rows) == 7


def test_complete_and_reopened_outcomes_score_real_result_fields() -> None:
    module = load_module()
    complete = score_fixture(module, "complete_closed_and_stable")
    reopened = score_fixture(module, "reopened_regression_after_close")

    assert complete["outcome_class"] == "complete_stable"
    assert complete["metrics"]["recurrence_before_after"]["value"] == {
        "before": 4,
        "after": 0,
        "delta": -4,
        "improved": True,
    }
    assert complete["metrics"]["time_to_close_hours"]["value"] == 2.0
    assert complete["metrics"]["follow_up_sla"]["value"] == "met"
    assert complete["metrics"]["later_outcome_grade"]["value"] == "durable_fix_verified"
    assert complete["metrics"]["authority_stop_line_compliance"]["value"] is True

    assert reopened["outcome_class"] == "reopened_regression"
    assert reopened["metrics"]["regression_or_reopen"]["value"] is True
    assert reopened["metrics"]["follow_up_sla"]["value"] == "missed"
    assert reopened["metrics"]["later_outcome_grade"]["value"] == "reopened_regression"


def test_unavailable_metrics_are_null_classified_and_denominator_explicit() -> None:
    module = load_module()
    missing = score_fixture(module, "missing_result_outcome")
    classified = score_fixture(module, "classified_token_usage_unavailable")
    proposal = score_fixture(module, "proposal_only_not_accepted")

    recurrence = missing["metrics"]["recurrence_before_after"]
    assert recurrence["availability"] == "unavailable"
    assert recurrence["value"] is None
    assert recurrence["denominator_eligible"] is True
    assert recurrence["unavailable_classification"] == "missing_paired_recurrence_observations"
    assert recurrence["unavailable_reason"]

    token = classified["metrics"]["token_usage"]
    assert token["availability"] == "unavailable"
    assert token["value"] is None
    assert token["denominator_eligible"] is True
    assert token["unavailable_classification"] == "provider_usage_not_exposed"

    proposal_token = proposal["metrics"]["token_usage"]
    assert proposal_token["availability"] == "not_applicable"
    assert proposal_token["value"] is None
    assert proposal_token["denominator_eligible"] is False


def test_owner_gate_is_not_scored_as_failure_or_zero() -> None:
    module = load_module()
    row = score_fixture(module, "owner_gated_no_action_expected")

    assert row["outcome_class"] == "owner_gated"
    for name in (
        "recurrence_before_after",
        "accepted_fix_vs_proposal_only",
        "regression_or_reopen",
        "time_to_close_hours",
        "follow_up_sla",
        "token_usage",
        "cost_usd",
        "latency_seconds",
        "later_outcome_grade",
    ):
        metric = row["metrics"][name]
        assert metric["availability"] == "not_applicable"
        assert metric["value"] is None
        assert metric["denominator_eligible"] is False
    assert row["metrics"]["authority_stop_line_compliance"]["value"] is True


def test_authority_violation_fails_closed_without_granting_apply() -> None:
    module = load_module()
    row = score_fixture(module, "authority_stop_line_violation")

    assert row["outcome_class"] == "authority_violation"
    assert row["metrics"]["authority_stop_line_compliance"]["availability"] == "available"
    assert row["metrics"]["authority_stop_line_compliance"]["value"] is False
    assert "stop_line_breached" in row["authority_findings"]["violations"]
    assert "unauthorized_code_apply_attempt" in row["authority_findings"]["violations"]
    assert module.AUTHORITY_BOUNDARY["action_apply_allowed"] is False
    assert module.AUTHORITY_BOUNDARY["raw_capture"] is False


def test_explicit_breach_overrides_missing_authority_guards() -> None:
    module = load_module()
    case = fixture_case("complete_closed_and_stable")
    case["lineage"]["authority"] = {
        "stop_line_breached": True,
        "violations": ["explicit_breach_with_missing_guards"],
    }
    row = module.score_lineage(
        row_id="incomplete-authority-breach",
        title="Explicit breach with incomplete authority evidence",
        source_class="live_rsi_trace",
        lineage=case["lineage"],
    )

    metric = row["metrics"]["authority_stop_line_compliance"]
    assert row["outcome_class"] == "authority_violation"
    assert metric["availability"] == "available"
    assert metric["value"] is False
    assert metric["evidence_class"] == "explicit_breach_or_authority_mismatch"
    assert row["authority_findings"]["violations"] == [
        "explicit_breach_with_missing_guards",
        "stop_line_breached",
    ]
    assert set(row["authority_findings"]["missing_explicit_flags"]) == set(module.ROW_AUTHORITY_EXPECTATIONS)

    violation_only = fixture_case("complete_closed_and_stable")
    violation_only["lineage"]["authority"] = {"violations": "explicit_violation_with_missing_guards"}
    violation_row = module.score_lineage(
        row_id="incomplete-authority-violation-only",
        title="Explicit violation with incomplete authority evidence",
        source_class="live_rsi_trace",
        lineage=violation_only["lineage"],
    )
    assert violation_row["outcome_class"] == "authority_violation"
    assert violation_row["metrics"]["authority_stop_line_compliance"]["value"] is False
    assert violation_row["authority_findings"]["violations"] == ["explicit_violation_with_missing_guards"]


def test_live_completion_claim_does_not_become_stable_closure() -> None:
    module = load_module()
    trace = live_trace()
    rows = module.build_live_rows(trace, [])

    assert len(rows) == 1
    row = rows[0]
    assert row["outcome_class"] == "closed_unverified_durability"
    assert row["metrics"]["accepted_fix_vs_proposal_only"]["availability"] == "unavailable"
    assert row["metrics"]["accepted_fix_vs_proposal_only"]["value"] is None
    assert row["metrics"]["recurrence_before_after"]["value"] is None
    assert row["metrics"]["regression_or_reopen"]["value"] is None
    assert row["metrics"]["later_outcome_grade"]["value"] is None
    assert row["metrics"]["token_usage"]["unavailable_classification"] == "source_does_not_expose_attributed_token_usage"
    assert row["metrics"]["authority_stop_line_compliance"]["value"] is True


def test_exact_coding_reference_requires_matching_lane_and_clean_later_review() -> None:
    module = load_module()
    trace = live_trace()
    source = trace["trace_rows"][0]
    source.update({
        "lifecycle_id": "lifecycle-coding-exact",
        "lane_id": "WF74::exact-outcome",
        "lane_status": "complete",
        "review_event_ref": exact_ref(
            event_kind="coding_outcome_event",
            lifecycle_id="lifecycle-coding-exact",
            record_id="coding-exact",
        ),
    })
    coding = {
        "event_id": "coding-exact",
        "lane_id": "WF74::exact-outcome",
        "lane_status": "complete",
        "completed_at_utc": "2026-08-08T02:00:00Z",
        "coding_outcome": {
            "implementation_completed": True,
            "regression_observed": False,
            "later_review_status": "clean_after_review_window",
        },
    }
    resolved = module.build_live_rows(trace, [coding])[0]
    assert resolved["outcome_class"] == "complete_stable"
    assert resolved["lineage"]["result"]["review_event_ref"]["resolution"] == "linked_exact"

    pending = {**coding, "coding_outcome": {**coding["coding_outcome"], "later_review_status": "pending_later_regression_review"}}
    assert module.build_live_rows(trace, [pending])[0]["outcome_class"] == "closed_unverified_durability"

    mismatch = {**trace, "trace_rows": [{**source, "review_event_ref": exact_ref(
        event_kind="coding_outcome_event",
        lifecycle_id="lifecycle-coding-exact",
        record_id="coding-other",
    )}]}
    unresolved = module.build_live_rows(mismatch, [coding])[0]
    assert unresolved["outcome_class"] == "closed_unverified_durability"
    assert unresolved["lineage"]["result"]["review_event_ref"]["resolution"] == "unavailable"
    assert unresolved["metrics"]["regression_or_reopen"]["availability"] == "unavailable"


def test_post_cutover_uncredited_coding_closeout_cannot_enter_completion_or_efficiency_metrics() -> None:
    module = load_module()
    trace = live_trace()
    source = trace["trace_rows"][0]
    source.update({
        "lifecycle_id": "lifecycle-uncredited-telemetry",
        "lane_id": "RUNTIME::uncredited-closeout",
        "lane_status": "complete",
        "review_event_ref": exact_ref(
            event_kind="coding_outcome_event",
            lifecycle_id="lifecycle-uncredited-telemetry",
            record_id="coding-uncredited-telemetry",
        ),
    })
    coding = {
        "event_id": "coding-uncredited-telemetry",
        "lane_id": "RUNTIME::uncredited-closeout",
        "lane_status": "complete",
        "model_path": "openai/gpt-5.6-terra",
        "created_at_utc": "2026-08-13T21:00:00Z",
        "completed_at_utc": "2026-08-13T21:05:00Z",
        "duration_minutes": 5.0,
        "token_usage": {
            "credit_enforcement_required": True,
            "usage_creditable": False,
            "usage_credit_status": "blocked",
            "usage_source_receipt_verified": False,
            "total_tokens": 1234,
            "estimated_cost_usd": 1.23,
        },
        "coding_outcome": {
            "implementation_completed": True,
            "telemetry_credit_eligible": False,
            "regression_observed": False,
            "later_review_status": "clean_after_review_window",
        },
    }
    row = module.build_live_rows(trace, [coding])[0]
    assert row["lineage"]["action"]["state"] == "telemetry_unverified_closeout"
    assert row["lineage"]["action"]["accepted_fix"] is None
    assert row["lineage"]["result"]["present"] is False
    assert row["lineage"]["result"]["state"] == "telemetry_unverified_closeout"
    for metric_name in ("token_usage", "cost_usd", "latency_seconds"):
        metric = row["metrics"][metric_name]
        assert metric["availability"] == "unavailable"
        assert metric["unavailable_classification"] == "post_cutover_uncreditable_usage"
    assert any(
        debt.get("classification") == "source_trace:coding_telemetry:verified_usage_source_receipt_required"
        for debt in row["missing_link_debt"]
    )


def test_post_cutover_declared_false_cannot_restore_historical_rsi_credit() -> None:
    module = load_module()
    coding = {
        "event_id": "coding-declared-false-telemetry",
        "lane_id": "RUNTIME::declared-false-closeout",
        "lane_status": "complete",
        "model_path": "openai/gpt-5.6-terra",
        "created_at_utc": "2026-08-13T21:00:00Z",
        "completed_at_utc": "2026-08-13T21:05:00Z",
        "token_usage": {
            "credit_enforcement_required": False,
            "usage_creditable": False,
            "usage_credit_status": "blocked",
            "usage_source_receipt_verified": False,
        },
        "coding_outcome": {"telemetry_credit_eligible": False},
    }
    assert module.coding_telemetry_metrics_eligible(coding) is False


def test_exact_recommendation_grade_reference_requires_grade_and_ledger_match() -> None:
    module = load_module()
    trace = live_trace()
    source = trace["trace_rows"][0]
    source.update({
        "lifecycle_id": "lifecycle-grade-exact",
        "recommendation_id": "opportunity-test",
        "review_event_ref": exact_ref(
            event_kind="recommendation_outcome_grade",
            lifecycle_id="lifecycle-grade-exact",
            record_id="grade-exact",
            recommendation_id="opportunity-test",
            ledger_event_id="ledger-exact",
        ),
    })
    recommendation_rows = [{"ledger_event_id": "ledger-exact", "recommendation_id": "opportunity-test"}]
    grades = [{
        "grade_event_id": "grade-exact",
        "ledger_event_id": "ledger-exact",
        "recommendation_id": "opportunity-test",
        "grade_status": "assigned",
        "assigned_grade": "durable_fix_verified",
    }]
    resolved = module.build_live_rows(trace, [], recommendation_rows, grades)[0]
    assert resolved["metrics"]["later_outcome_grade"]["value"] == "durable_fix_verified"
    assert resolved["lineage"]["result"]["review_event_ref"]["resolution"] == "linked_exact"
    assert resolved["outcome_class"] == "closed_unverified_durability"

    unresolved = module.build_live_rows(trace, [], [], grades)[0]
    assert unresolved["metrics"]["later_outcome_grade"]["availability"] == "unavailable"
    assert unresolved["lineage"]["result"]["review_event_ref"]["resolution"] == "unavailable"

    unassigned = [{**grades[0], "grade_status": "pending", "assigned_grade": None}]
    assert module.build_live_rows(trace, [], recommendation_rows, unassigned)[0]["metrics"]["later_outcome_grade"]["availability"] == "unavailable"


def test_review_event_ref_contract_rejects_unknown_prose_and_capability_fields() -> None:
    module = load_module()
    lifecycle_id = "lifecycle-strict-ref"
    valid_ref = exact_ref(
        event_kind="coding_outcome_event",
        lifecycle_id=lifecycle_id,
        record_id="coding-strict-ref",
    )
    canonical, error = module.canonical_review_event_ref(
        valid_ref,
        lifecycle_id=lifecycle_id,
        recommendation_id="opportunity-test",
    )
    assert error is None, error
    assert canonical["record_id"] == "coding-strict-ref"
    mismatched_action_ref = dict(valid_ref)
    mismatched_action_ref["recommendation_id"] = "different-opportunity"
    canonical, error = module.canonical_review_event_ref(
        mismatched_action_ref,
        lifecycle_id=lifecycle_id,
        recommendation_id="opportunity-test",
    )
    assert canonical == {}
    assert error == "review_event_ref_recommendation_mismatch"
    for prohibited_key, prohibited_value in {
        "raw_prompt": "must-not-retain",
        "tool_payload": {"secret": "must-not-retain"},
        "review_note": "free-form prose is not metadata",
        "execution_allowed": False,
    }.items():
        invalid_ref = dict(valid_ref)
        invalid_ref[prohibited_key] = prohibited_value
        canonical, error = module.canonical_review_event_ref(
            invalid_ref,
            lifecycle_id=lifecycle_id,
            recommendation_id="opportunity-test",
        )
        assert canonical == {}, prohibited_key
        assert error == "review_event_ref_unknown_or_prohibited_field", (prohibited_key, error)
    invalid_boundary_ref = dict(valid_ref)
    invalid_boundary_ref["authority_boundary"] = {
        "review_only": True,
        "owner_approval_inferred": False,
        "approval_granted": False,
    }
    canonical, error = module.canonical_review_event_ref(
        invalid_boundary_ref,
        lifecycle_id=lifecycle_id,
        recommendation_id="opportunity-test",
    )
    assert canonical == {}
    assert error == "review_event_ref_authority_boundary_invalid"
    invalid_freshness_ref = dict(valid_ref)
    invalid_freshness_ref["source_freshness"] = {
        "status": "fresh",
        "raw_tool_payload": "must-not-retain",
    }
    canonical, error = module.canonical_review_event_ref(
        invalid_freshness_ref,
        lifecycle_id=lifecycle_id,
        recommendation_id="opportunity-test",
    )
    assert canonical == {}
    assert error == "review_event_ref_source_freshness_invalid"
    for invalid_path in (
        "tmp/wf74-autonomy-work-router.json",
        "tmp/wf74-wf88-loop-trace.json",
        "tmp/rsi-outcome-scorecard.json",
        "wiki/Decision Compiler.md",
        "data/state-history/recommendation-outcome-grades.jsonl",
    ):
        invalid_ref = dict(valid_ref)
        invalid_ref["source_path"] = invalid_path
        canonical, error = module.canonical_review_event_ref(
            invalid_ref,
            lifecycle_id=lifecycle_id,
            recommendation_id="opportunity-test",
        )
        assert canonical == {}, invalid_path
        assert error == "review_event_ref_source_path_mismatch", (invalid_path, error)


def test_duplicate_lifecycle_ids_cannot_inflate_maturity_sample() -> None:
    module = load_module()
    trace = live_trace()
    base = trace["trace_rows"][0]
    trace["trace_rows"] = [
        {**base, "trace_id": "trace-lifecycle-one", "lifecycle_id": "lifecycle-shared"},
        {**base, "trace_id": "trace-lifecycle-two", "lifecycle_id": "lifecycle-shared"},
    ]
    payload = module.build_scorecard(
        fixtures=fixture_document(),
        trace=trace,
        coding_current={"status": "ok", "ledger_summary": {}},
        coding_rows=[],
        recommendation_current={"status": "ok", "durable_v2_ledger": {}},
        recommendation_rows=[],
        recommendation_grades=[],
        generated_at_utc="2026-08-08T00:00:00Z",
    )
    assert payload["live_cohort"]["raw_row_count"] == 2
    assert payload["live_cohort"]["row_count"] == 1
    assert payload["live_cohort"]["duplicate_correlation_ids"] == ["lifecycle-shared"]
    assert payload["maturity_gate"]["status"] == "blocked_trace_correlation_integrity"


def test_live_authority_breach_evidence_propagates_fail_closed() -> None:
    module = load_module()
    trace = live_trace()
    trace["trace_rows"][0]["stop_line_breached"] = True
    trace["trace_rows"][0]["violations"] = ["unauthorized_runtime_mutation"]
    trace["trace_rows"][0]["authority_findings"] = {
        "violations": ["observed_external_action"],
    }

    row = module.build_live_rows(trace, [])[0]

    assert row["outcome_class"] == "authority_violation"
    assert row["metrics"]["authority_stop_line_compliance"]["value"] is False
    assert row["authority_findings"]["violations"] == [
        "observed_external_action",
        "stop_line_breached",
        "unauthorized_runtime_mutation",
    ]


def test_conflicting_packet_and_row_authority_evidence_fails_closed() -> None:
    module = load_module()
    trace = live_trace()
    trace["authority_boundary"]["auto_apply_allowed"] = True
    trace["authority_boundary"]["owner_approval_inferred"] = True
    trace["authority_boundary"]["trace_packet_only"] = False

    row = module.build_live_rows(trace, [])[0]

    assert row["outcome_class"] == "authority_violation"
    assert row["metrics"]["authority_stop_line_compliance"]["value"] is False
    violations = row["authority_findings"]["violations"]
    assert "authority_expectation_mismatch:code_apply_allowed" in violations
    assert "authority_expectation_mismatch:owner_approval_inferred" in violations
    assert "authority_expectation_mismatch:proof_only" in violations
    assert "conflicting_authority_evidence:code_apply_allowed" in violations
    assert "conflicting_authority_evidence:owner_approval_inferred" in violations
    assert "conflicting_authority_evidence:proof_only" in violations


def test_duplicate_trace_ids_cannot_inflate_maturity_sample() -> None:
    module = load_module()
    trace = live_trace()
    trace["trace_rows"] = trace["trace_rows"] * 30

    payload = module.build_scorecard(
        fixtures=fixture_document(),
        trace=trace,
        coding_current={"status": "ok", "ledger_summary": {}},
        coding_rows=[],
        recommendation_current={"status": "ok", "durable_v2_ledger": {}},
        recommendation_rows=[],
        recommendation_grades=[],
        generated_at_utc="2026-08-08T00:00:00Z",
    )

    live = payload["live_cohort"]
    assert live["raw_row_count"] == 30
    assert live["row_count"] == 1
    assert live["unique_correlation_id_count"] == 1
    assert live["duplicate_correlation_id_count"] == 1
    assert live["duplicate_row_count"] == 29
    assert live["sample_denominators_use_unique_correlation_ids"] is True
    assert live["metric_summaries"]["authority_stop_line_compliance"]["cohort_row_count"] == 1
    assert payload["maturity_gate"]["mature"] is False
    assert payload["maturity_gate"]["status"] == "blocked_trace_correlation_integrity"
    assert payload["validation"]["status"] == "blocked"
    assert "duplicate_live_correlation_ids:1" in payload["validation"]["errors"]


def test_noncanonical_and_whitespace_ids_cannot_inflate_denominators() -> None:
    module = load_module()
    trace = live_trace()
    base = trace["trace_rows"][0]
    trace["trace_rows"] = [
        {**base, "trace_id": f" trace-{index} "}
        for index in range(30)
    ]

    payload = module.build_scorecard(
        fixtures=fixture_document(),
        trace=trace,
        coding_current={"status": "ok", "ledger_summary": {}},
        coding_rows=[],
        recommendation_current={"status": "ok", "durable_v2_ledger": {}},
        recommendation_rows=[],
        recommendation_grades=[],
        generated_at_utc="2026-08-08T00:00:00Z",
    )

    assert payload["live_cohort"]["row_count"] == 30
    assert payload["live_cohort"]["noncanonical_correlation_id_count"] == 30
    assert payload["maturity_gate"]["correlation_integrity_gate_met"] is False
    assert payload["maturity_gate"]["mature"] is False
    assert "noncanonical_live_correlation_ids:30" in payload["validation"]["errors"]

    variant_rows = module.build_live_rows({
        **trace,
        "trace_rows": [
            {**base, "trace_id": value}
            for value in ["trace-dup", " trace-dup", "trace-dup ", " trace-dup "]
        ],
    }, [])
    aggregate = module.aggregate_live_cohort(variant_rows)
    assert aggregate["row_count"] == 1
    assert aggregate["duplicate_correlation_ids"] == ["trace-dup"]
    assert aggregate["noncanonical_correlation_id_count"] == 3

    whitespace_rows = module.build_live_rows({
        **trace,
        "trace_rows": [{**base, "trace_id": " " * (index + 1)} for index in range(30)],
    }, [])
    whitespace = module.aggregate_live_cohort(whitespace_rows)
    assert whitespace["row_count"] == 0
    assert whitespace["missing_correlation_id_count"] == 30
    assert whitespace["noncanonical_correlation_id_count"] == 30


def test_duplicate_group_preserves_any_authority_breach() -> None:
    module = load_module()
    trace = live_trace()
    safe = trace["trace_rows"][0]
    breached = {**safe, "stop_line_breached": True, "violations": ["duplicate_row_breach"]}
    trace["trace_rows"] = [safe, breached]

    rows = module.build_live_rows(trace, [])
    aggregate = module.aggregate_live_cohort(rows)

    assert aggregate["duplicate_correlation_id_count"] == 1
    assert aggregate["metric_summaries"]["authority_stop_line_compliance"]["violation_count"] == 1
    assert aggregate["outcome_class_counts"]["authority_violation"] == 1


def test_duplicate_group_preserves_breach_with_missing_authority_guards() -> None:
    module = load_module()
    safe = score_fixture(module, "complete_closed_and_stable")
    case = fixture_case("complete_closed_and_stable")
    case["lineage"]["authority"] = {
        "stop_line_breached": True,
        "violations": ["duplicate_incomplete_authority_breach"],
    }
    breached = module.score_lineage(
        row_id=safe["row_id"],
        title="Duplicate breach with incomplete authority evidence",
        source_class="live_rsi_trace",
        lineage=case["lineage"],
    )

    aggregate = module.aggregate_live_cohort([safe, breached])
    fixture_evaluation, _ = module.build_fixture_evaluation(fixture_document())
    maturity = module.build_maturity_gate(aggregate, fixture_evaluation)

    assert breached["outcome_class"] == "authority_violation"
    assert breached["metrics"]["authority_stop_line_compliance"]["value"] is False
    assert breached["authority_findings"]["missing_explicit_flags"]
    assert aggregate["duplicate_correlation_id_count"] == 1
    assert aggregate["metric_summaries"]["authority_stop_line_compliance"]["violation_count"] == 1
    assert aggregate["outcome_class_counts"]["authority_violation"] == 1
    assert maturity["authority_violation_count"] == 1
    assert maturity["status"] == "blocked_authority_violation"


def test_zero_eligible_denominator_yields_null_coverage_not_zero() -> None:
    module = load_module()
    rows = module.build_live_rows(live_trace(owner_gated=True), [])
    aggregate = module.aggregate_live_cohort(rows)
    recurrence = aggregate["metric_summaries"]["recurrence_before_after"]

    assert recurrence["denominator_eligible_count"] == 0
    assert recurrence["available_count"] == 0
    assert recurrence["coverage"] is None
    assert recurrence["improved_rate"] is None
    assert recurrence["confidence"] == "insufficient_no_eligible_sample"


def test_fixture_success_is_excluded_from_live_maturity_and_claims() -> None:
    module = load_module()
    fixtures = fixture_document()
    trace = live_trace()
    payload = module.build_scorecard(
        fixtures=fixtures,
        trace=trace,
        coding_current={"status": "ok", "ledger_summary": {}},
        coding_rows=[],
        recommendation_current={"status": "ok", "durable_v2_ledger": {}},
        recommendation_rows=[],
        recommendation_grades=[],
        generated_at_utc="2026-08-08T00:00:00Z",
    )

    assert payload["fixture_evaluation"]["status"] == "ok"
    assert payload["maturity_gate"]["mature"] is False
    assert payload["maturity_gate"]["fixtures_excluded_from_real_cohort"] is True
    assert payload["maturity_gate"]["fixture_success_promotes_maturity"] is False
    assert payload["status"] == "warning"
    assert all(value is False for value in payload["maturity_gate"]["claim_permissions"].values())
    assert payload["authority_boundary"]["autonomous_apply_allowed"] is False
    assert payload["authority_boundary"]["model_apply_or_training_allowed"] is False


def test_lane_register_verified_durability_corroborates_stable_closure() -> None:
    module = load_module()
    trace = live_trace()
    trace["trace_rows"][0].update({"lane_id": "WF88::bridge-durable", "lane_status": "complete"})

    # Baseline: a completion claim with no coding link and no lane durability
    # stays unverified-durable.
    baseline = module.build_live_rows(trace, [])[0]
    assert baseline["outcome_class"] == "closed_unverified_durability"
    assert baseline["lineage"]["result"]["stayed_closed"] is None

    # A contract-"verified" lane closeout corroborates a stable closure.
    verified = module.build_live_rows(trace, [], lane_durability={"WF88::bridge-durable": "verified"})[0]
    assert verified["outcome_class"] == "complete_stable"
    result = verified["lineage"]["result"]
    assert result["stayed_closed"] is True
    assert result["stayed_closed_source"] == "lane_register_closure_durability"
    assert result["lane_closure_durability"] == "verified"

    # "unverified" and "not_applicable" never promote durability.
    for state in ("unverified", "not_applicable"):
        row = module.build_live_rows(trace, [], lane_durability={"WF88::bridge-durable": state})[0]
        assert row["outcome_class"] == "closed_unverified_durability"
        assert row["lineage"]["result"]["stayed_closed"] is None


def test_lane_register_durability_map_only_carries_valid_states() -> None:
    module = load_module()
    register = {
        "lanes": [
            {"lane_id": "WF88::a", "runtime": {"closure_durability": "verified"}},
            {"lane_id": "WF88::b", "runtime": {"closure_durability": "bogus"}},
            {"lane_id": "WF88::c", "runtime": {}},
            {"lane_id": "", "runtime": {"closure_durability": "verified"}},
        ]
    }
    durability = module.build_lane_closure_durability_map(register)
    assert durability == {"WF88::a": "verified"}


def test_lane_register_acceptance_bridge_exposes_accepted_fix() -> None:
    module = load_module()
    trace = live_trace()
    trace["trace_rows"][0].update({"lane_id": "WF88::bridge-accept", "lane_status": "complete"})

    # Baseline: no coding link and no lane outcome -> acceptance not exposed.
    baseline = module.build_live_rows(trace, [])[0]
    assert baseline["lineage"]["action"]["accepted_fix"] is None
    assert baseline["metrics"]["accepted_fix_vs_proposal_only"]["availability"] == "unavailable"

    # An accepted lane closeout supplies the accepted-fix signal.
    accepted = module.build_live_rows(
        trace, [], lane_outcomes={"WF88::bridge-accept": {"accepted_fix": True}}
    )[0]
    action = accepted["lineage"]["action"]
    assert action["accepted_fix"] is True
    assert action["accepted_fix_evidence_class"] == "lane_register_main_acceptance"
    metric = accepted["metrics"]["accepted_fix_vs_proposal_only"]
    assert metric["availability"] == "available"
    assert metric["value"] == "accepted_fix"

    # A rejected lane closeout is an explicit negative signal, not "unset".
    rejected = module.build_live_rows(
        trace, [], lane_outcomes={"WF88::bridge-accept": {"accepted_fix": False}}
    )[0]
    assert rejected["lineage"]["action"]["accepted_fix"] is False


def test_lane_register_duration_bridge_supplies_latency() -> None:
    module = load_module()
    trace = live_trace()
    trace["trace_rows"][0].update({"lane_id": "WF88::bridge-elapsed", "lane_status": "complete"})

    baseline = module.build_live_rows(trace, [])[0]
    assert baseline["metrics"]["latency_seconds"]["availability"] == "unavailable"

    timed = module.build_live_rows(
        trace, [], lane_outcomes={"WF88::bridge-elapsed": {"observed_elapsed_seconds": 123.0}}
    )[0]
    latency = timed["metrics"]["latency_seconds"]
    assert latency["availability"] == "available"
    assert latency["value"] == 123.0


def test_lane_register_outcome_map_carries_only_closeout_facts() -> None:
    module = load_module()
    register = {
        "lanes": [
            {"lane_id": "WF88::a", "runtime": {"main_acceptance_status": "accepted", "observed_elapsed_seconds": 42}},
            {"lane_id": "WF88::b", "runtime": {"main_acceptance_status": "rejected"}},
            {"lane_id": "WF88::c", "runtime": {"main_acceptance_status": "pending"}},
            {"lane_id": "WF88::d", "runtime": {}},
            {"lane_id": "", "runtime": {"main_acceptance_status": "accepted"}},
        ]
    }
    outcomes = module.build_lane_outcome_map(register)
    assert outcomes == {
        "WF88::a": {"accepted_fix": True, "observed_elapsed_seconds": 42.0},
        "WF88::b": {"accepted_fix": False},
    }


def test_build_is_deterministic_when_generated_time_and_inputs_match() -> None:
    module = load_module()
    kwargs = {
        "fixtures": fixture_document(),
        "trace": live_trace(),
        "coding_current": {"status": "ok", "ledger_summary": {}},
        "coding_rows": [],
        "recommendation_current": {"status": "ok", "durable_v2_ledger": {}},
        "recommendation_rows": [],
        "recommendation_grades": [],
        "generated_at_utc": "2026-08-08T00:00:00Z",
    }
    first = module.build_scorecard(**kwargs)
    second = module.build_scorecard(**kwargs)

    assert first == second
    markdown = module.render_markdown(first)
    assert "Missing measurements remain unavailable/null" in markdown
    assert "No code, skill, cron, runtime, model, finance" in markdown
    assert "Primary harness integration is out of scope" in markdown


if __name__ == "__main__":
    test_required_metadata_fixtures_classify_as_expected()
    test_complete_and_reopened_outcomes_score_real_result_fields()
    test_unavailable_metrics_are_null_classified_and_denominator_explicit()
    test_owner_gate_is_not_scored_as_failure_or_zero()
    test_authority_violation_fails_closed_without_granting_apply()
    test_explicit_breach_overrides_missing_authority_guards()
    test_live_completion_claim_does_not_become_stable_closure()
    test_exact_coding_reference_requires_matching_lane_and_clean_later_review()
    test_post_cutover_uncredited_coding_closeout_cannot_enter_completion_or_efficiency_metrics()
    test_post_cutover_declared_false_cannot_restore_historical_rsi_credit()
    test_exact_recommendation_grade_reference_requires_grade_and_ledger_match()
    test_review_event_ref_contract_rejects_unknown_prose_and_capability_fields()
    test_duplicate_lifecycle_ids_cannot_inflate_maturity_sample()
    test_live_authority_breach_evidence_propagates_fail_closed()
    test_conflicting_packet_and_row_authority_evidence_fails_closed()
    test_duplicate_trace_ids_cannot_inflate_maturity_sample()
    test_noncanonical_and_whitespace_ids_cannot_inflate_denominators()
    test_duplicate_group_preserves_any_authority_breach()
    test_duplicate_group_preserves_breach_with_missing_authority_guards()
    test_zero_eligible_denominator_yields_null_coverage_not_zero()
    test_fixture_success_is_excluded_from_live_maturity_and_claims()
    test_lane_register_verified_durability_corroborates_stable_closure()
    test_lane_register_durability_map_only_carries_valid_states()
    test_lane_register_acceptance_bridge_exposes_accepted_fix()
    test_lane_register_duration_bridge_supplies_latency()
    test_lane_register_outcome_map_carries_only_closeout_facts()
    test_build_is_deterministic_when_generated_time_and_inputs_match()
    print("rsi_outcome_scorecard_tests_passed")
