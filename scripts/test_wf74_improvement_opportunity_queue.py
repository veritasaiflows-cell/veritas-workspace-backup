from __future__ import annotations

from copy import deepcopy

import wf74_improvement_opportunity_queue as queue

from unittest.mock import patch as _test_isolation_patch

_TEST_NEUTRAL_WF87_PROOF = {
    "retired": False,
    "reason": "test_isolation_neutral_no_live_capsule",
    "capsule_path": "state/workflows/WF87.json",
}

# Hermetic baseline: neutralize the live WF87 capsule for every test in this
# module, so counts and categories never depend on real workspace capsule
# state. The explicit positive/negative WF87 tests below nest their own
# patch.object context over this default. Active under both the direct script
# and pytest. Production gate untouched.
_test_wf87_neutral = _test_isolation_patch.object(
    queue, "load_wf87_retired_architecture_proof", return_value=_TEST_NEUTRAL_WF87_PROOF
)
_test_wf87_neutral.start()


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


def test_green_cron_with_ledger_escalation_echo_closes_not_regresses() -> None:
    # 2026-09-12 regression fixture: a green scorecard (blocked_count=0) whose
    # control packet is ok must not re-open the completed cron-regression row
    # just because an improvement-ledger overdue echo raises escalation count
    # and should_wake_main_session.
    inputs = deepcopy(sample_inputs())
    inputs["cron_signal"] = {
        "status": "ok",
        "validation": {"status": "ok"},
        "scorecard": {"blocked_count": 0, "requires_attention_count": 0, "enabled_job_count": 44},
        "signals": [],
    }
    inputs["cron_control"] = {
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {
            "blocked_count": 0,
            "escalation_signal_count": 1,
            "should_wake_main_session": True,
            "requires_attention_count": 1,
        },
        "scorecard": {
            "scorecard": {
                "blocked_count": 0,
                "requires_attention_count": 1,
                "enabled_job_count": 44,
            },
            "signals": [
                {
                    "source": "operating_spine:improvement_ledger",
                    "signal_class": "OWNER_DECISION",
                    "attention": "requires_main_attention",
                    "status": "warning",
                    "reason": "high_priority_overdue",
                    "next_action": "",
                }
            ],
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
    regressed = [
        row for row in payload["opportunities"]
        if row.get("signal") == "cron_scorecard_regressed_after_completed_repair_plan"
    ]
    assert not regressed
    assert payload["summary"]["regressed_after_completion_count"] == 0
    resolved = [
        row for row in payload["completed_or_resolved_opportunities"]
        if row.get("completion_status") == "completed_by_ledger_current_cron_green"
    ]
    assert resolved
    assert resolved[0]["current_cron_signal"]["scorecard"]["blocked_count"] == 0


def test_control_packet_validation_failure_still_regresses_without_blockers() -> None:
    # blocked_count=0 with an echo present, but cron control validation is not
    # ok: the completed row must still re-open.
    inputs = deepcopy(sample_inputs())
    inputs["cron_control"] = {
        "status": "ok",
        "validation": {"status": "blocked"},
        "summary": {
            "blocked_count": 0,
            "escalation_signal_count": 1,
            "should_wake_main_session": True,
            "requires_attention_count": 1,
        },
        "scorecard": {
            "scorecard": {
                "blocked_count": 0,
                "requires_attention_count": 1,
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
    regressed = [
        row for row in payload["opportunities"]
        if row.get("signal") == "cron_scorecard_regressed_after_completed_repair_plan"
    ]
    assert regressed
    assert regressed[0]["completion_status"] == "current_regression_after_completion"
    assert payload["summary"]["regressed_after_completion_count"] == 1


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


def test_wf55_ledger_warning_is_measurement_only_not_implementation() -> None:
    row = {
        "workflow_id": "WF55",
        "status": "ok",
        "signal": "blocked",
        "blockers": ["ledger_validation=warning"],
    }
    assert queue.workflow_blocker_requires_implementation(row) is False


def test_residual_followup_evidence_reflects_post_classification_counts() -> None:
    original = queue.opportunity(
        category="workflow_maturity",
        title="Convert workflow advancement blockers into implementation follow-ups",
        priority=89,
        signal="workflow_advancement_blockers_present",
        evidence={
            "blocked_count": 4,
            "owner_needed_count": 0,
            "blocked_workflows": [
                {
                    "workflow_id": "CRON",
                    "status": "blocked",
                    "blockers": ["cron_status=blocked", "blocked_count=4"],
                },
                {
                    "workflow_id": "WF87",
                    "status": "runtime_blocked",
                    "blockers": ["wf87_runtime_blocked"],
                },
                {
                    "workflow_id": "WF55",
                    "status": "ok",
                    "blockers": ["ledger_validation=warning"],
                },
                {
                    "workflow_id": "AUTONOMY-SPINE",
                    "status": "ok",
                    "blockers": ["wf87_runtime_gates_not_clean"],
                },
            ],
            "implementation_blocker_count": 2,
            "visibility_operationalized": False,
        },
        recommended_action="Route blockers into follow-up rows.",
        proposal_gate="main_review_required",
        validation_command="python scripts\\workflow_advancement_scorecard.py --write --validate",
    )
    completion = {"matched_job_ids": ["pm-wf74-workflow-blocker-followup-routing"]}
    residual = queue.residual_workflow_followup(original, completion)
    assert residual["evidence"]["implementation_blocker_count"] == 1
    assert residual["evidence"]["visibility_operationalized"] is True
    assert residual["evidence"]["blocked_count"] == 4


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


def test_wf87_retired_architecture_proof_exact_holds() -> None:
    retired = {
        "lifecycle": "paused",
        "readiness": "paused",
        "primary_route_artifact": None,
        "effective_status_override": "on_hold",
        "current_state": "**Retired 2026-08-29** with WF86.",
    }
    proof = queue.wf87_retired_architecture_proof(retired)
    assert proof["retired"] is True
    assert queue.wf87_retired_architecture_proof(None)["retired"] is False
    assert queue.wf87_retired_architecture_proof({})["retired"] is False
    not_retired = dict(retired)
    not_retired["lifecycle"] = "active"
    assert queue.wf87_retired_architecture_proof(not_retired)["retired"] is False
    with_primary = dict(retired)
    with_primary["primary_route_artifact"] = "tmp/something.json"
    assert queue.wf87_retired_architecture_proof(with_primary)["retired"] is False
    missing_key = dict(retired)
    del missing_key["primary_route_artifact"]
    missing_proof = queue.wf87_retired_architecture_proof(missing_key)
    assert missing_proof["retired"] is False
    assert "missing_required_keys" in missing_proof["reason"]
    negated = dict(retired)
    negated["current_state"] = "WF87 is not retired; still active."
    negated_proof = queue.wf87_retired_architecture_proof(negated)
    assert negated_proof["retired"] is False
    assert negated_proof["reason"] == "current_state_negates_retired"
    no_override = {k: v for k, v in retired.items() if k != "effective_status_override"}
    no_override_proof = queue.wf87_retired_architecture_proof(no_override)
    assert no_override_proof["retired"] is False
    assert no_override_proof["reason"] == "effective_status_override_key_missing"


def test_wf87_retired_opportunity_resolves_when_capsule_retired() -> None:
    from unittest.mock import patch as _patch
    inputs = deepcopy(sample_inputs())
    wf87_proof = {
        "retired": True,
        "reason": "retired_architecture_proof_holds",
        "capsule_path": "state/workflows/WF87.json",
    }
    with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=wf87_proof):
        payload = queue.build_payload(inputs)
    titles = [row["title"] for row in payload["opportunities"]]
    assert queue.WF87_RETIRED_OPPORTUNITY_TITLE not in titles
    done = [row for row in payload["completed_or_resolved_opportunities"] if row.get("completion_status") == "completed_retired_architecture_no_routing"]
    assert done
    assert done[0]["retired_architecture_proof"] == wf87_proof


def test_wf87_retired_opportunity_stays_open_when_proof_missing() -> None:
    from unittest.mock import patch as _patch
    inputs = deepcopy(sample_inputs())
    wf87_proof = {"retired": False, "reason": "capsule_missing_or_malformed", "capsule_path": "state/workflows/WF87.json"}
    with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=wf87_proof):
        payload = queue.build_payload(inputs)
    rows = [row for row in payload["opportunities"] if row["title"] == queue.WF87_RETIRED_OPPORTUNITY_TITLE]
    assert rows
    assert rows[0]["completion_status"] == "open"


_WF87_RETIRED_CAPSULE_PROOF = {
    "retired": True,
    "reason": "retired_architecture_proof_holds",
    "capsule_path": "state/workflows/WF87.json",
}

_EXACT_RETIRED_CAPSULE = {
    "lifecycle": "paused",
    "readiness": "paused",
    "primary_route_artifact": None,
    "effective_status_override": "on_hold",
    "current_state": "**Retired 2026-08-29** with WF86.",
}


def _wf87_shadow_titles(payload):
    return [row["title"] for row in payload["opportunities"]]


def test_wf87_shadow_row_resolves_as_retired_history_when_proof_holds() -> None:
    from unittest.mock import patch as _patch
    inputs = deepcopy(sample_inputs())
    with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=dict(_WF87_RETIRED_CAPSULE_PROOF)):
        payload = queue.build_payload(inputs)
    assert queue.WF87_SHADOW_OPPORTUNITY_TITLE not in _wf87_shadow_titles(payload)
    assert queue.WF87_RETIRED_OPPORTUNITY_TITLE not in _wf87_shadow_titles(payload)
    retired = [
        row for row in payload["completed_or_resolved_opportunities"]
        if row.get("completion_status") == "completed_retired_architecture_no_routing"
    ]
    retired_titles = {row["title"] for row in retired}
    assert queue.WF87_SHADOW_OPPORTUNITY_TITLE in retired_titles
    assert queue.WF87_RETIRED_OPPORTUNITY_TITLE in retired_titles
    shadow = [row for row in retired if row["title"] == queue.WF87_SHADOW_OPPORTUNITY_TITLE][0]
    assert shadow["retired_architecture_proof"] == _WF87_RETIRED_CAPSULE_PROOF
    assert shadow["opportunity_id"] and shadow["origin_opportunity_id"] and shadow["lifecycle_id"]
    assert shadow["lifecycle_id"].startswith("lifecycle-")
    assert shadow["signal"] == queue.WF87_SHADOW_OPPORTUNITY_SIGNAL
    assert "pending_regular_session_followup_count" in shadow["evidence"]


def test_wf87_shadow_row_stays_open_across_adversarial_capsules() -> None:
    from unittest.mock import patch as _patch
    base = dict(_EXACT_RETIRED_CAPSULE)
    missing_primary = dict(base)
    del missing_primary["primary_route_artifact"]
    missing_state = dict(base)
    del missing_state["current_state"]
    no_override = {k: v for k, v in base.items() if k != "effective_status_override"}
    adversarial = [
        ("missing_capsule", None),
        ("malformed_capsule", {}),
        ("non_dict_capsule", ["paused"]),
        ("active_lifecycle", {**base, "lifecycle": "active"}),
        ("active_readiness", {**base, "readiness": "active"}),
        ("non_null_primary", {**base, "primary_route_artifact": "tmp/something.json"}),
        ("missing_primary_key", missing_primary),
        ("missing_current_state_key", missing_state),
        ("missing_override_key", no_override),
        ("override_not_on_hold", {**base, "effective_status_override": "active"}),
        ("negated_not_retired", {**base, "current_state": "WF87 is not retired; still active."}),
        ("negated_non_retired", {**base, "current_state": "WF87 non-retired pilot continues."}),
        ("current_state_not_retired", {**base, "current_state": "WF87 pilot still active."}),
    ]
    for name, capsule in adversarial:
        proof = queue.wf87_retired_architecture_proof(capsule)
        assert proof["retired"] is False, name
        inputs = deepcopy(sample_inputs())
        with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=proof):
            payload = queue.build_payload(inputs)
        rows = [row for row in payload["opportunities"] if row["title"] == queue.WF87_SHADOW_OPPORTUNITY_TITLE]
        assert rows, name
        assert rows[0]["completion_status"] == "open", name


def test_wf87_shadow_input_shapes_resolve_only_with_strict_proof() -> None:
    from unittest.mock import patch as _patch
    stale = deepcopy(sample_inputs())
    stale["wf87_shadow_outcome"] = {
        "summary": {
            "decision_count": 20,
            "scoreable_decision_count": 9,
            "pending_regular_session_followup_count": 6,
            "stale_pending_followup_count": 3,
            "decision_quality_claim_allowed_now": False,
            "model_performance_claim_allowed_now": False,
        }
    }
    missing = deepcopy(sample_inputs())
    del missing["wf87_shadow_outcome"]
    empty = deepcopy(sample_inputs())
    empty["wf87_shadow_outcome"] = {}
    failed_proof = {"retired": False, "reason": "capsule_missing_or_malformed", "capsule_path": "state/workflows/WF87.json"}
    for label, inputs in (("existing_backlog", deepcopy(sample_inputs())), ("stale_backlog", stale), ("missing_input", missing), ("empty_input", empty)):
        with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=dict(failed_proof)):
            payload = queue.build_payload(inputs)
        rows = [row for row in payload["opportunities"] if row["title"] == queue.WF87_SHADOW_OPPORTUNITY_TITLE]
        assert rows, label
        assert rows[0]["completion_status"] == "open", label
        with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=dict(_WF87_RETIRED_CAPSULE_PROOF)):
            retired_payload = queue.build_payload(inputs)
        assert queue.WF87_SHADOW_OPPORTUNITY_TITLE not in _wf87_shadow_titles(retired_payload), label
        done = [
            row for row in retired_payload["completed_or_resolved_opportunities"]
            if row.get("title") == queue.WF87_SHADOW_OPPORTUNITY_TITLE
            and row.get("completion_status") == "completed_retired_architecture_no_routing"
        ]
        assert done, label


def test_unrelated_outcome_measurement_row_unaffected_by_retired_proof() -> None:
    from unittest.mock import patch as _patch
    unrelated = queue.opportunity(
        category="outcome_measurement",
        title="Track cron follow-up calibration until thresholds are met",
        priority=68,
        signal="cron_followup_calibration_backlog",
        evidence={"pending_followup_count": 3},
        recommended_action="Keep calibrating cron follow-ups.",
        proposal_gate="measurement_only_no_execution",
        validation_command="python scripts\\cron_control_packet.py --write --validate",
    )
    lookalike = queue.opportunity(
        category="outcome_measurement",
        title="WF87 shadow outcomes review (team sync)",
        priority=68,
        signal="wf87_shadow_review_sync",
        evidence={"pending_followup_count": 1},
        recommended_action="Weekly sync review.",
        proposal_gate="measurement_only_no_execution",
        validation_command="python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
    )
    inputs = {"implementation_completion_ledger": [], "pm_implementation_queue": {}}
    with _patch.object(queue, "load_wf87_retired_architecture_proof", return_value=dict(_WF87_RETIRED_CAPSULE_PROOF)):
        current, done, regressed = queue.apply_completion_overlay([unrelated, lookalike], inputs)
    assert len(current) == 2
    assert not done
    for row in current:
        assert row["completion_status"] == "open"
    assert {row["title"] for row in current} == {unrelated["title"], lookalike["title"]}


if __name__ == "__main__":
    test_queue_has_required_cadences_and_gates()
    test_completed_workflow_routing_with_only_maturity_residue_is_resolved()
    test_completed_workflow_routing_reopens_when_non_maturity_blocker_remains()
    test_completed_cron_plan_with_current_blocker_is_regression()
    test_completed_cron_plan_with_current_green_cron_is_resolved_residue()
    test_green_cron_with_ledger_escalation_echo_closes_not_regresses()
    test_control_packet_validation_failure_still_regresses_without_blockers()
    test_completed_planning_pass_with_current_gap_is_regression()
    test_lifecycle_identity_survives_followup_relabeling()
    test_wf55_ledger_warning_is_measurement_only_not_implementation()
    test_residual_followup_evidence_reflects_post_classification_counts()
    test_opportunity_id_is_stable_across_priority_change()
    test_completion_matches_by_identity_when_title_rule_is_absent()
    test_current_wf74_blocked_step_stays_open_without_completion()
    test_source_open_blocked_wf74_step_routes_to_finance_repair()
    test_classified_finance_freshness_debt_is_not_a_false_code_repair()
    test_wf87_retired_architecture_proof_exact_holds()
    test_wf87_retired_opportunity_resolves_when_capsule_retired()
    test_wf87_retired_opportunity_stays_open_when_proof_missing()
    test_wf87_shadow_row_resolves_as_retired_history_when_proof_holds()
    test_wf87_shadow_row_stays_open_across_adversarial_capsules()
    test_wf87_shadow_input_shapes_resolve_only_with_strict_proof()
    test_unrelated_outcome_measurement_row_unaffected_by_retired_proof()
    print("wf74_improvement_opportunity_queue_tests_passed")


def partitioned_planning_signal(actionable, terminal, repaired, raw=None, reconciled=True, rate=0.6):
    total = actionable + terminal + repaired
    return {
        "schema": "veritas.planning_quality_signal.v1",
        "tracked_lane_count": 10,
        "plan_contract_present_count": 8,
        "plan_followthrough_clean_count": 6,
        "plan_followthrough_gap_count": total if raw is None else raw,
        "plan_followthrough_clean_rate": rate,
        "gap_reasons": {"missing_proof": 1},
        "status": "attention",
        "plan_followthrough_actionable_gap_count": actionable,
        "plan_followthrough_terminal_unavailable_count": terminal,
        "plan_followthrough_repaired_accepted_count": repaired,
        "partitioned_gap_row_count": total,
        "partition_reconciliation_ok": reconciled,
        "actionable_status": "attention" if actionable else "ok",
    }


def planning_completion_job():
    return {
        "completed_at_utc": "2026-06-20T16:05:25Z",
        "job": {
            "job_id": "pm-wf74-planning-followthrough-gap-reduction",
            "title": "Measure and close planning follow-through gaps",
            "implementation_class": "wf74_planning_followthrough",
        },
    }


def planning_rows(payload):
    return [row for row in payload["opportunities"] if row["category"] == "planning_quality"]


def test_valid_actionable_partition_raises_with_selected_proof() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["coding_outcome"]["ledger_summary"]["planning_quality_signal"] = partitioned_planning_signal(2, 1, 1)
    payload = queue.build_payload(inputs)
    rows = planning_rows(payload)
    assert rows
    evidence = rows[0]["evidence"]
    assert evidence["plan_followthrough_gap_count"] == 4
    assert evidence["plan_followthrough_gap_count_selected"] == 2
    assert evidence["plan_followthrough_gap_source"] == "actionable_partition_verified"
    assert evidence["plan_followthrough_terminal_unavailable_count"] == 1
    assert evidence["plan_followthrough_repaired_accepted_count"] == 1
    assert evidence["planning_gap_selection_warning"] is None


def test_historical_only_terminal_repaired_raises_no_false_improvement() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["coding_outcome"]["ledger_summary"]["planning_quality_signal"] = partitioned_planning_signal(0, 3, 1)
    payload = queue.build_payload(inputs)
    assert planning_rows(payload) == []
    assert payload["summary"]["planning_quality_followup_count"] == 0


def test_verified_zero_history_closes_honestly_after_completed_pass() -> None:
    inputs = deepcopy(sample_inputs())
    signal = partitioned_planning_signal(0, 3, 1)
    signal["plan_followthrough_clean_rate"] = None
    inputs["coding_outcome"]["ledger_summary"]["planning_quality_signal"] = signal
    rows = queue.build_opportunities(inputs)
    planning = [row for row in rows if row.get("title") == "Measure and close planning follow-through gaps"]
    assert planning
    inputs["implementation_completion_ledger"] = [planning_completion_job()]
    current, done, regressed = queue.apply_completion_overlay(rows, inputs)
    assert [row for row in current if row["category"] == "planning_quality"] == []
    assert len(done) == 1
    assert done[0]["completion_status"] == "completed_no_actionable_planning_debt_history_only"
    assert done[0]["completion_status"] != "current_regression_after_completion"
    assert regressed == []
    assert done[0]["evidence"]["plan_followthrough_gap_count"] == 4


def test_malformed_partition_falls_back_to_raw_gap() -> None:
    inputs = deepcopy(sample_inputs())
    payload = queue.build_payload(inputs)
    rows = planning_rows(payload)
    assert rows
    evidence = rows[0]["evidence"]
    assert evidence["plan_followthrough_gap_count"] == 4
    assert evidence["plan_followthrough_gap_count_selected"] == 4
    assert evidence["plan_followthrough_gap_source"] == "raw_gap_fallback"
    assert evidence["planning_gap_selection_warning"]
    signal = partitioned_planning_signal(2, 1, 1)
    signal["plan_followthrough_actionable_gap_count"] = True
    inputs["coding_outcome"]["ledger_summary"]["planning_quality_signal"] = signal
    payload = queue.build_payload(inputs)
    rows = planning_rows(payload)
    assert rows
    assert rows[0]["evidence"]["plan_followthrough_gap_count_selected"] == 4
    assert rows[0]["evidence"]["plan_followthrough_gap_source"] == "raw_gap_fallback"


def test_reconciliation_mismatch_falls_back_to_raw_gap() -> None:
    inputs = deepcopy(sample_inputs())
    signal = partitioned_planning_signal(1, 1, 1)
    signal["plan_followthrough_gap_count"] = 5
    inputs["coding_outcome"]["ledger_summary"]["planning_quality_signal"] = signal
    payload = queue.build_payload(inputs)
    rows = planning_rows(payload)
    assert rows
    evidence = rows[0]["evidence"]
    assert evidence["plan_followthrough_gap_count"] == 5
    assert evidence["plan_followthrough_gap_count_selected"] == 5
    assert evidence["plan_followthrough_gap_source"] == "raw_gap_fallback"
    assert "reconcile" in str(evidence["planning_gap_selection_warning"])


def test_current_fixture_with_actionable_debt_stays_raised() -> None:
    inputs = deepcopy(sample_inputs())
    inputs["coding_outcome"]["ledger_summary"]["planning_quality_signal"] = partitioned_planning_signal(3, 1, 0)
    inputs["implementation_completion_ledger"] = [planning_completion_job()]
    payload = queue.build_payload(inputs)
    rows = planning_rows(payload)
    assert rows
    assert rows[0]["completion_status"] == "current_regression_after_completion"
    assert payload["summary"]["regressed_after_completion_count"] == 1
