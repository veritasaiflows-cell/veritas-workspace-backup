from __future__ import annotations

from copy import deepcopy

import wf74_improvement_opportunity_queue as queue


def sample_inputs() -> dict:
    return {
        "wf74_runner": {"summary": {"steps_blocked": 0}},
        "coding_outcome": {
            "ledger_summary": {
                "ledger_row_count": 10,
                "model_attributed_count": 0,
                "planning_quality_signal": {
                    "schema": "veritas.planning_quality_signal.v1",
                    "tracked_lane_count": 10,
                    "plan_contract_present_count": 8,
                    "plan_followthrough_clean_count": 6,
                    "plan_followthrough_gap_count": 4,
                    "plan_followthrough_clean_rate": 0.6,
                    "gap_reasons": {"missing_proof": 2, "later_rework": 2},
                    "status": "attention",
                },
            }
        },
        "coding_runtime": {
            "kpis": {
                "validator_elapsed_seconds": 14,
                "validator_target_seconds": 10,
                "recommended_budget": "shared",
                "recommended_validator_count": 12,
                "rework_required": False,
                "failure_bucket_counts": {},
            }
        },
        "otel_ops": {
            "drift": {
                "status": "review",
                "daily_warning_or_error_count": 0,
                "daily_vs_weekly_event_rate_ratio": 3.1,
                "drift_reasons": ["daily_event_rate_deviates_from_weekly_baseline"],
            }
        },
        "model_run": {"summary": {"lane_register_rows": 12}},
        "model_learning": {},
        "finance_response": {
            "summary": {
                "sector_timing_warning_available": True,
                "source_freshness_blocked_count": 4,
                "remediation_tracks_needing_repair": 1,
                "average_quality_score": 1.0,
            }
        },
        "pm_control": {},
        "field_depth_packet": {
            "status": "owner_decision_required",
            "current_collector_posture": {"has_file_exporter": False},
        },
        "cron_signal": {
            "scorecard": {
                "blocked_count": 2,
                "requires_attention_count": 3,
                "enabled_job_count": 51,
            },
            "signals": [
                {
                    "source": "cron_job:Runtime - Weekly OS Improvement Radar",
                    "artifact": "tmp/artifact-staleness-explainer.json",
                    "signal_class": "BLOCKED",
                    "attention": "requires_main_attention",
                    "status": "blocked",
                    "reason": "artifact_blocked_or_authority_widened",
                    "next_action": "Inspect blocked artifact.",
                }
            ],
        },
        "cron_control": {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "blocked_count": 2,
                "escalation_signal_count": 0,
                "should_wake_main_session": False,
                "requires_attention_count": 3,
            },
            "scorecard": {
                "scorecard": {
                    "blocked_count": 2,
                    "requires_attention_count": 3,
                    "enabled_job_count": 51,
                },
                "signals": [
                    {
                        "source": "cron_job:Runtime - Weekly OS Improvement Radar",
                        "artifact": "tmp/artifact-staleness-explainer.json",
                        "signal_class": "BLOCKED",
                        "attention": "requires_main_attention",
                        "status": "blocked",
                        "reason": "artifact_blocked_or_authority_widened",
                        "next_action": "Inspect blocked artifact.",
                    }
                ],
            },
        },
        "workflow_advancement": {
            "summary": {
                "blocked_count": 2,
                "owner_needed_count": 0,
                "cron_update_recommended": False,
            },
            "validation": {"status": "ok"},
            "signals": [
                {
                    "workflow_id": "WF87",
                    "signal": "blocked",
                    "status": "runtime_blocked",
                    "blockers": ["shadow_threshold_not_met"],
                    "next_action": "Continue maturity accrual.",
                }
            ],
        },
        "wf87_shadow_outcome": {
            "summary": {
                "decision_count": 15,
                "scoreable_decision_count": 2,
                "pending_regular_session_followup_count": 8,
                "stale_pending_followup_count": 0,
                "decision_quality_claim_allowed_now": False,
                "model_performance_claim_allowed_now": False,
            }
        },
        "wf87_readiness_rollup": {
            "phase_readiness": {
                "phase_a_runtime_gates_clean": False,
                "phase_b_assisted_round_trip_ready": False,
                "phase_c_autonomous_paper_buy_ready": False,
            },
            "blocker_taxonomy": {
                "binding_blockers": ["shadow_threshold_not_met"],
                "counts": {"binding_blocker_count": 1},
            },
        },
        "pm_implementation_queue": {},
        "implementation_completion_ledger": [],
    }


def test_queue_has_required_cadences_and_gates() -> None:
    payload = queue.build_payload(sample_inputs())
    assert payload["validation"]["status"] == "ok"
    assert payload["authority_boundary"]["code_mutation_allowed"] is False
    assert payload["authority_boundary"]["collector_config_mutation_allowed"] is False
    assert payload["authority_boundary"]["paper_or_live_execution_allowed"] is False
    for required in (
        "code_mutation",
        "skill_application",
        "collector_config",
        "finance_mutation",
        "execution",
        "cron_migration",
        "workflow_maturity",
        "outcome_measurement",
        "planning_quality",
    ):
        assert required in payload["review_cadence"]
    gates = {row["proposal_gate"] for row in payload["opportunities"]}
    assert "main_review_required" in gates
    assert "owner_decision_required" in gates
    assert "standing_guardrail_no_execution" in gates
    assert "cron_migration_plan_only" in gates
    assert "measurement_only_no_execution" in gates
    assert "auto_apply" not in gates
    assert "auto_execute" not in gates
    categories = {row["category"] for row in payload["opportunities"]}
    assert "cron_migration" in categories
    assert "workflow_maturity" in categories
    assert "outcome_measurement" in categories
    assert "planning_quality" in categories
    collector_rows = [row for row in payload["opportunities"] if row["category"] == "collector_config"]
    volume_review = [row for row in collector_rows if row["title"] == "Review OTEL event-rate drift against the weekly baseline"]
    assert volume_review
    assert volume_review[0]["priority"] == 64
    assert volume_review[0]["signal"] == "otel_operational_volume_review"
    assert volume_review[0]["evidence"]["operational_volume_only"] is True
    assert payload["summary"]["outcome_measurement_followup_count"] >= 1
    assert payload["summary"]["planning_quality_followup_count"] >= 1


def test_completed_workflow_routing_with_only_maturity_residue_is_resolved() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["implementation_completion_ledger"] = [
        {
            "completed_at_utc": "2026-06-20T14:20:33Z",
            "job": {
                "job_id": "pm-wf74-workflow-blocker-followup-routing",
                "title": "Convert workflow advancement blockers into implementation follow-ups",
                "implementation_class": "wf74_workflow_followup_routing",
            },
        }
    ]
    payload = queue.build_payload(inputs)
    titles = [row["title"] for row in payload["opportunities"]]
    assert "Convert workflow advancement blockers into implementation follow-ups" not in titles
    residual = [row for row in payload["opportunities"] if row["title"] == "Close remaining workflow-maturity follow-ups"]
    assert not residual
    assert payload["summary"]["completed_or_resolved_opportunity_count"] == 1


def test_completed_workflow_routing_reopens_when_non_maturity_blocker_remains() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["workflow_advancement"]["signals"].append({
        "workflow_id": "PM",
        "signal": "blocked",
        "status": "blocked",
        "blockers": ["pm_queue_authority_gap"],
        "next_action": "Open a PM authority cleanup lane.",
    })
    inputs["implementation_completion_ledger"] = [
        {
            "completed_at_utc": "2026-06-20T14:20:33Z",
            "job": {
                "job_id": "pm-wf74-workflow-blocker-followup-routing",
                "title": "Convert workflow advancement blockers into implementation follow-ups",
                "implementation_class": "wf74_workflow_followup_routing",
            },
        }
    ]
    payload = queue.build_payload(inputs)
    residual = [row for row in payload["opportunities"] if row["title"] == "Convert workflow advancement blockers into implementation follow-ups"]
    assert residual
    assert residual[0]["priority"] == 89


def test_completed_cron_plan_with_current_blocker_is_regression() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["implementation_completion_ledger"] = [
        {
            "completed_at_utc": "2026-06-20T17:17:01Z",
            "job": {
                "job_id": "pm-wf74-cron-migration-repair-plan",
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "implementation_class": "wf74_cron_migration_repair_plan",
            },
        }
    ]
    payload = queue.build_payload(inputs)
    cron_rows = [row for row in payload["opportunities"] if row["category"] == "cron_migration"]
    assert cron_rows
    assert cron_rows[0]["title"] == "Repair regressed cron signals after completed migration plan"
    assert cron_rows[0]["completion_status"] == "current_regression_after_completion"
    assert payload["summary"]["regressed_after_completion_count"] == 1


def test_completed_cron_plan_with_current_green_cron_is_resolved_residue() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["cron_control"] = {
        "status": "ok",
        "validation": {"status": "warning"},
        "summary": {
            "blocked_count": 0,
            "escalation_signal_count": 0,
            "should_wake_main_session": False,
            "requires_attention_count": 3,
        },
        "scorecard": {
            "scorecard": {
                "blocked_count": 0,
                "requires_attention_count": 3,
                "enabled_job_count": 44,
            },
            "signals": [],
        },
    }
    inputs["implementation_completion_ledger"] = [
        {
            "completed_at_utc": "2026-06-20T17:17:01Z",
            "job": {
                "job_id": "pm-wf74-cron-migration-repair-plan",
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "implementation_class": "wf74_cron_migration_repair_plan",
            },
        }
    ]
    payload = queue.build_payload(inputs)
    cron_rows = [row for row in payload["opportunities"] if row["category"] == "cron_migration"]
    assert not cron_rows
    assert payload["summary"]["regressed_after_completion_count"] == 0


def test_completed_planning_pass_with_current_gap_is_regression() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["implementation_completion_ledger"] = [
        {
            "completed_at_utc": "2026-06-20T16:05:25Z",
            "job": {
                "job_id": "pm-wf74-planning-followthrough-gap-reduction",
                "title": "Measure and close planning follow-through gaps",
                "implementation_class": "wf74_planning_followthrough",
            },
        }
    ]
    payload = queue.build_payload(inputs)
    planning_rows = [row for row in payload["opportunities"] if row["category"] == "planning_quality"]
    assert planning_rows
    assert planning_rows[0]["title"] == "Continue planning follow-through gap reduction after completed pass"
    assert planning_rows[0]["completion_status"] == "current_regression_after_completion"
    assert payload["summary"]["regressed_after_completion_count"] == 1


def test_lifecycle_identity_survives_followup_relabeling() -> None:
    original = queue.opportunity(
        category="cron_migration",
        title="Route blocked cron signals into a migration-ready repair plan",
        priority=92,
        signal="cron_blocked",
        evidence={},
        recommended_action="Build a dry-run repair plan.",
        proposal_gate="cron_migration_plan_only",
        validation_command="python scripts\\cron_control_packet.py --write --validate",
    )
    completion = {"matched_job_ids": ["pm-wf74-cron-migration-repair-plan"]}
    followup = queue.regressed_cron_followup(original, completion)
    residual = queue.residual_workflow_followup(original, completion)
    planning = queue.regressed_planning_followup(original, completion)

    assert followup["opportunity_id"] != original["opportunity_id"]
    for row in (followup, residual, planning):
        assert row["origin_opportunity_id"] == original["origin_opportunity_id"]
        assert row["lifecycle_id"] == original["lifecycle_id"]
    assert "pm-wf74" not in followup["lifecycle_id"]


def test_opportunity_id_is_stable_across_priority_change() -> None:
    kwargs = {
        "category": "code_mutation",
        "title": "Repair blocked WF74 collection step",
        "signal": "wf74_steps_blocked",
        "evidence": {},
        "recommended_action": "Repair the blocked step.",
        "proposal_gate": "code_mutation_proposal_only",
        "validation_command": "python scripts\\wf74_learning_runtime.py --write --validate",
    }
    low = queue.opportunity(priority=72, **kwargs)
    high = queue.opportunity(priority=96, **kwargs)

    assert low["opportunity_id"] == high["opportunity_id"]
    assert low["lifecycle_id"] == high["lifecycle_id"]
    legacy_low = f"code_mutation-{queue.stable_id(kwargs['title'], kwargs['signal'], 72)}"
    legacy_high = f"code_mutation-{queue.stable_id(kwargs['title'], kwargs['signal'], 96)}"
    assert legacy_low in low["legacy_opportunity_ids"]
    assert legacy_high in high["legacy_opportunity_ids"]
    assert legacy_low != legacy_high


def test_completion_matches_by_identity_when_title_rule_is_absent() -> None:
    row = queue.opportunity(
        category="code_mutation",
        title="A title that no completion rule knows about",
        priority=72,
        signal="wf74_steps_blocked",
        evidence={},
        recommended_action="Repair the blocked step.",
        proposal_gate="code_mutation_proposal_only",
        validation_command="python scripts\\wf74_learning_runtime.py --write --validate",
    )
    assert row["title"] not in queue.OPPORTUNITY_COMPLETION_RULES
    legacy_hash = row["legacy_opportunity_ids"][0].rsplit("-", 1)[-1]
    inputs = {
        "implementation_completion_ledger": [
            {
                "completed_at_utc": "2026-07-05T06:51:36Z",
                "job": {
                    "job_id": f"pm-wf74-code-mutation-code-mutation-{legacy_hash}",
                    "title": "Repair blocked WF74 collection step",
                    "implementation_class": "wf74_code_mutation_followup",
                    "collision_group": f"wf74_code_mutation_followup_code_mutation-{legacy_hash}",
                },
            },
            {
                "completed_at_utc": "2026-07-05T06:51:36Z",
                "job": {"job_id": "pm-unrelated-job", "collision_group": "unrelated_group"},
            },
        ],
        "pm_implementation_queue": {},
    }
    completion = queue.matched_completion(row, queue.completed_job_index(inputs))

    assert completion["matched_by_title_rule"] == []
    assert completion["matched_job_ids"] == [f"pm-wf74-code-mutation-code-mutation-{legacy_hash}"]
    assert completion["latest_completed_at_utc"] == "2026-07-05T06:51:36Z"


def test_current_wf74_blocked_step_stays_open_without_completion() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["wf74_runner"]["summary"]["steps_blocked"] = 1
    payload = queue.build_payload(inputs)
    repair_rows = [row for row in payload["opportunities"] if row["title"] == "Repair blocked WF74 collection step"]
    assert repair_rows
    assert repair_rows[0]["completion_status"] == "open"
    assert repair_rows[0]["priority"] == 96


def test_source_open_blocked_wf74_step_routes_to_finance_repair() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["wf74_runner"]["summary"]["steps_blocked"] = 1
    inputs["wf74_runner"]["summary"]["blocking_step_names"] = ["model_quality_scorecard"]
    inputs["finance_response"]["summary"]["source_open_blocked_count"] = 42
    inputs["finance_response"]["summary"]["source_freshness_blocked_count"] = 0
    inputs["finance_response"]["summary"]["remediation_tracks_needing_repair"] = 0

    payload = queue.build_payload(inputs)
    finance_rows = [
        row for row in payload["opportunities"]
        if row["title"] == queue.SOURCE_OPEN_REPAIR_TITLE
    ]
    old_runtime_rows = [
        row for row in payload["opportunities"]
        if row["title"] == "Repair blocked WF74 collection step"
    ]

    assert finance_rows
    assert not old_runtime_rows
    assert finance_rows[0]["category"] == "finance_mutation"
    assert finance_rows[0]["priority"] == 96
    assert finance_rows[0]["evidence"]["source_open_blocked_count"] == 42
    assert finance_rows[0]["evidence"]["recommended_department"] == "finance_wf78_wf84_wf85"


def test_classified_finance_freshness_debt_is_not_a_false_code_repair() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["wf74_runner"]["summary"] = {
        "steps_blocked": 1,
        "blocking_step_names": ["model_quality_scorecard"],
        "scheduler_exit_domain_blocked_nonfatal": True,
    }

    payload = queue.build_payload(inputs)
    titles = [row["title"] for row in payload["opportunities"]]

    assert "Repair blocked WF74 collection step" not in titles
    assert "Route finance response-quality gaps into repair proposals" in titles


if __name__ == "__main__":
    test_queue_has_required_cadences_and_gates()
    test_completed_workflow_routing_with_only_maturity_residue_is_resolved()
    test_completed_workflow_routing_reopens_when_non_maturity_blocker_remains()
    test_completed_cron_plan_with_current_blocker_is_regression()
    test_completed_cron_plan_with_current_green_cron_is_resolved_residue()
    test_completed_planning_pass_with_current_gap_is_regression()
    test_lifecycle_identity_survives_followup_relabeling()
    test_opportunity_id_is_stable_across_priority_change()
    test_completion_matches_by_identity_when_title_rule_is_absent()
    test_current_wf74_blocked_step_stays_open_without_completion()
    test_source_open_blocked_wf74_step_routes_to_finance_repair()
    test_classified_finance_freshness_debt_is_not_a_false_code_repair()
    print("wf74_improvement_opportunity_queue_tests_passed")
