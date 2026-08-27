#!/usr/bin/env python3
"""Regression checks for WF74 autonomy work routing."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import wf74_autonomy_work_router as router
from market_data_utils import atomic_write_json, load_json_artifact


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        opportunity_queue = root / "wf74-improvement-opportunity-queue.json"
        improvement_ledger = root / "improvement-ledger-current.json"
        workflow_followups = root / "workflow-blocker-followups.json"
        cron_control = root / "cron-control-packet.json"
        pm_control = root / "pm-control-packet.json"
        coding_outcome = root / "coding-outcome-ledger-current.json"
        out = root / "wf74-autonomy-work-router.json"
        cron_repair_plan = root / "cron-migration-repair-plan.json"
        followup_ledger = root / "workflow-implementation-followup-ledger.json"
        followup_history = root / "workflow-implementation-followup-ledger.jsonl"

        atomic_write_json(opportunity_queue, {
            "status": "ok",
            "generated_at_utc": "2026-06-20T00:00:00Z",
            "validation": {"status": "ok"},
            "opportunities": [
                {
                    "opportunity_id": "cron_migration-test",
                    "category": "cron_migration",
                    "title": "Route blocked cron signals into a migration-ready repair plan",
                    "priority": 92,
                    "proposal_gate": "cron_migration_plan_only",
                    "recommended_action": "Build a dry-run cron migration repair plan.",
                },
                {
                    "opportunity_id": "workflow_maturity-test",
                    "category": "workflow_maturity",
                    "title": "Convert workflow advancement blockers into implementation follow-ups",
                    "priority": 89,
                    "proposal_gate": "main_review_required",
                    "recommended_action": "Route repeated workflow blockers into scoped followups.",
                },
                {
                    "opportunity_id": "planning_quality-test",
                    "category": "planning_quality",
                    "title": "Measure and close planning follow-through gaps",
                    "priority": 80,
                    "proposal_gate": "main_review_required",
                    "recommended_action": "Convert repeated planning gaps into scoped implementation followups.",
                },
                {
                    "opportunity_id": "code_mutation-blocked-step-test",
                    "origin_opportunity_id": "code_mutation-blocked-step-test",
                    "lifecycle_id": "lifecycle-code-mutation-test",
                    "category": "code_mutation",
                    "title": "Repair blocked WF74 collection step",
                    "priority": 96,
                    "signal": "wf74_collection_step_blocked",
                    "proposal_gate": "main_review_required",
                    "recommended_action": "Open a narrow implementation lane for the blocked WF74 collection step.",
                    "review_event_ref": {
                        "schema": router.REVIEW_EVENT_REF_SCHEMA,
                        "metadata_only": True,
                        "link_status": "linked_exact",
                        "event_kind": "coding_outcome_event",
                        "lifecycle_id": "lifecycle-code-mutation-test",
                        "source_path": "data/state-history/coding-outcome-ledger.jsonl",
                        "record_id": "coding-test-event",
                        "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
                    },
                },
                {
                    "opportunity_id": "code_mutation-validator-drag-test",
                    "category": "code_mutation",
                    "title": "Reduce validator drag for normal implementation passes",
                    "priority": 72,
                    "signal": "validator_elapsed_exceeds_target",
                    "proposal_gate": "main_review_required",
                    "recommended_action": "Review validator routing and repeated proof commands.",
                },
                {
                    "opportunity_id": "finance_source_open-test",
                    "category": "finance_mutation",
                    "title": "Clear finance response quality source-open blockers so WF74 scorecard can pass",
                    "priority": 96,
                    "proposal_gate": "finance_repair_proposal_only",
                    "signal": "wf74_scorecard_blocked_by_finance_source_open",
                    "recommended_action": "Route source-open repair through WF78/WF85 proof.",
                    "validation_command": "python scripts\\finance_response_quality_slice.py --write --write-md --validate",
                    "evidence": {
                        "source_open_blocked_count": 42,
                        "blocker_chain": [
                            "wf74_model_quality_collection_cron_runner",
                            "model_quality_scorecard",
                            "finance_response_quality_slice",
                            "source_open_blocked_count",
                        ],
                    },
                },
                {
                    "opportunity_id": "skill_application-test",
                    "category": "skill_application",
                    "title": "Convert repeated coding friction into a Skill Workshop proposal",
                    "priority": 82,
                    "proposal_gate": "skill_workshop_proposal_only",
                    "recommended_action": "Draft a Skill Workshop proposal only if the same friction pattern repeats.",
                    "validation_command": "openclaw skills check",
                },
            ],
        })
        atomic_write_json(improvement_ledger, {
            "status": "ok",
            "summary": {
                "high_priority_overdue_open_count": 2,
                "top_improvement_age_hours": 84.95,
            },
            "validation": {"status": "ok"},
        })
        atomic_write_json(workflow_followups, {
            "status": "ok",
            "validation": {"status": "ok"},
            "followups": [
                {
                    "followup_id": "wf87-maturity-accrual",
                    "workflow_id": "WF87",
                    "route": "maturity_accrual",
                    "followup_type": "maturity_accrual",
                    "blocker_class": "runtime_maturity_or_guard",
                    "source_artifacts": ["tmp/wf87-autonomy-command-center.json"],
                    "owner": "WF87 maturity lane",
                    "next_action": "Continue maturity accrual.",
                    "acceptance_validators": [
                        "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
                        "python scripts\\workflow_advancement_scorecard.py --write --validate",
                    ],
                    "stop_lines": ["No autonomous paper execution."],
                },
                {
                    "followup_id": "wf55-measurement-only",
                    "workflow_id": "WF55",
                    "route": "measurement_only",
                    "followup_type": "maturity_accrual",
                    "blocker_class": "outcome_measurement",
                    "source_artifacts": ["tmp/wf55-autonomy-outcome-ledger.json"],
                    "owner": "WF55 outcome measurement lane",
                    "next_action": "Continue neutral outcome measurement.",
                    "acceptance_validators": [
                        "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                    ],
                },
            ],
        })
        atomic_write_json(cron_control, {
            "status": "ok",
            "summary": {
                "blocked_count": 0,
                "escalation_signal_count": 0,
                "should_wake_main_session": False,
                "requires_attention_count": 0,
            },
            "validation": {"status": "ok"},
        })
        atomic_write_json(pm_control, {"status": "ok", "summary": {"pm_implementation_queue_summary": {}}})
        atomic_write_json(coding_outcome, {
            "status": "ok",
            "ledger_summary": {
                "planning_quality_signal": {
                    "plan_followthrough_clean_rate": 0.5,
                    "plan_followthrough_gap_count": 10,
                }
            },
            "validation": {"status": "ok"},
        })

        args = SimpleNamespace(
            opportunity_queue=str(opportunity_queue),
            improvement_ledger=str(improvement_ledger),
            workflow_followups=str(workflow_followups),
            cron_control=str(cron_control),
            pm_control=str(pm_control),
            coding_outcome=str(coding_outcome),
            out=str(out),
            cron_repair_plan=str(cron_repair_plan),
            followup_ledger=str(followup_ledger),
            followup_history=str(followup_history),
        )
        merged = router.merge_pm_job_candidates([
            {
                "job_id": "pm-wf74-duplicate-test",
                "source": "wf74_autonomy_work_router",
                "source_key": "signal-a",
                "source_category": "code_mutation",
                "title": "Signal A",
                "objective": "Repair A",
                "target_files": ["tmp/a.json"],
                "proof_commands": ["python scripts\\a.py --write --validate"],
                "acceptance_criteria": ["A passes"],
                "dependencies": ["dep-a"],
                "stop_lines": ["stop-a"],
            },
            {
                "job_id": "pm-wf74-duplicate-test",
                "source": "wf74_autonomy_work_router",
                "source_key": "signal-b",
                "source_category": "code_mutation",
                "title": "Signal B",
                "objective": "Repair B",
                "target_files": ["tmp/b.json"],
                "proof_commands": ["python scripts\\b.py --write --validate"],
                "acceptance_criteria": ["B passes"],
                "dependencies": ["dep-b"],
                "stop_lines": ["stop-b"],
            },
        ])
        assert len(merged) == 1, merged
        assert merged[0]["merged_duplicate_count"] == 1, merged
        assert set(merged[0]["merged_source_keys"]) == {"signal-a", "signal-b"}, merged
        assert set(merged[0]["target_files"]) == {"tmp/a.json", "tmp/b.json"}, merged
        payload = router.build_payload(args)
        assert payload["status"] == "ok", payload["validation"]
        assert payload["summary"]["recommendation_to_route_conversion_rate"] == 1.0, payload["summary"]
        assert payload["summary"]["route_to_pm_job_conversion_rate"] == 1.0, payload["summary"]
        assert payload["summary"]["pm_job_candidate_count"] == 7, payload["summary"]
        assert payload["summary"]["code_mutation_repair_job_count"] == 2, payload["summary"]
        assert payload["summary"]["finance_source_open_repair_job_count"] == 1, payload["summary"]
        assert payload["summary"]["recommendation_action_ledger_count"] == 9, payload["summary"]
        assert payload["summary"]["recommendation_action_opportunity_row_count"] == 7, payload["summary"]
        assert payload["summary"]["recommendation_action_workflow_followup_row_count"] == 2, payload["summary"]
        assert payload["summary"]["open_unrouted_recommendation_count"] == 0, payload["summary"]
        job_id_list = [row["job_id"] for row in payload["pm_job_candidates"]]
        assert len(job_id_list) == len(set(job_id_list)), job_id_list
        job_ids = set(job_id_list)
        assert "pm-wf74-finance-source-open-quality-repair" in job_ids, job_ids
        assert "pm-wf74-cron-migration-repair-plan" not in job_ids, job_ids
        assert "pm-wf74-workflow-blocker-followup-routing" in job_ids, job_ids
        assert "pm-wf74-planning-followthrough-gap-reduction" in job_ids, job_ids
        assert "pm-wf74-code-mutation-repair-blocked-collection-step" in job_ids, job_ids
        assert len([jid for jid in job_ids if jid.startswith("pm-wf74-code-mutation-")]) == 2, job_ids
        linked_route = next(row for row in payload["opportunity_routes"] if row["source_key"] == "code_mutation-blocked-step-test")
        linked_candidate = next(row for row in payload["pm_job_candidates"] if row["job_id"] == "pm-wf74-code-mutation-repair-blocked-collection-step")
        linked_action = next(row for row in payload["recommendation_action_ledger"] if row["recommendation_id"] == "code_mutation-blocked-step-test")
        for row in (linked_route, linked_candidate, linked_action):
            assert row["origin_opportunity_id"] == "code_mutation-blocked-step-test", row
            assert row["lifecycle_id"] == "lifecycle-code-mutation-test", row
            assert row["review_event_ref"]["metadata_only"] is True, row
            assert row["review_event_ref"]["record_id"] == "coding-test-event", row
        unsafe_ref_route = router.opportunity_route({
            "opportunity_id": "unsafe-ref",
            "category": "code_mutation",
            "title": "Unsafe ref",
            "review_event_ref": {
                "schema": router.REVIEW_EVENT_REF_SCHEMA,
                "metadata_only": True,
                "link_status": "linked_exact",
                "event_kind": "coding_outcome_event",
                "lifecycle_id": "lifecycle-unsafe-ref",
                "source_path": "wiki/Decision Compiler.md",
                "record_id": "not-an-event",
            },
        }, {"classification": "active_repair_plan_required"})
        assert "review_event_ref" not in unsafe_ref_route, unsafe_ref_route
        valid_ref = {
            "schema": router.REVIEW_EVENT_REF_SCHEMA,
            "metadata_only": True,
            "link_status": "linked_exact",
            "event_kind": "coding_outcome_event",
            "lifecycle_id": "lifecycle-code-mutation-test",
            "source_path": "data/state-history/coding-outcome-ledger.jsonl",
            "record_id": "coding-test-event",
            "source_freshness": {"status": "fresh"},
            "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
        }
        compacted_ref = router.metadata_only_review_event_ref(
            valid_ref,
            lifecycle_id="lifecycle-code-mutation-test",
            recommendation_id="code_mutation-blocked-step-test",
        )
        assert compacted_ref is not None, compacted_ref
        assert compacted_ref["source_freshness"] == {"status": "fresh"}
        for prohibited_key, prohibited_value in {
            "raw_prompt": "must-not-propagate",
            "tool_payload": {"secret": "must-not-propagate"},
            "review_note": "free-form prose is not metadata",
            "auto_apply_allowed": False,
        }.items():
            invalid_ref = dict(valid_ref)
            invalid_ref[prohibited_key] = prohibited_value
            assert router.metadata_only_review_event_ref(
                invalid_ref,
                lifecycle_id="lifecycle-code-mutation-test",
                recommendation_id="code_mutation-blocked-step-test",
            ) is None, prohibited_key
        invalid_boundary_ref = dict(valid_ref)
        invalid_boundary_ref["authority_boundary"] = {
            "review_only": True,
            "owner_approval_inferred": False,
            "auto_apply_allowed": False,
        }
        assert router.metadata_only_review_event_ref(
            invalid_boundary_ref,
            lifecycle_id="lifecycle-code-mutation-test",
            recommendation_id="code_mutation-blocked-step-test",
        ) is None
        invalid_freshness_ref = dict(valid_ref)
        invalid_freshness_ref["source_freshness"] = {
            "status": "fresh",
            "raw_prompt": "must-not-propagate",
        }
        assert router.metadata_only_review_event_ref(
            invalid_freshness_ref,
            lifecycle_id="lifecycle-code-mutation-test",
            recommendation_id="code_mutation-blocked-step-test",
        ) is None
        for invalid_path in (
            "tmp/wf74-autonomy-work-router.json",
            "tmp/wf74-wf88-loop-trace.json",
            "tmp/rsi-outcome-scorecard.json",
            "wiki/Decision Compiler.md",
            "data/state-history/recommendation-outcome-grades.jsonl",
        ):
            invalid_ref = dict(valid_ref)
            invalid_ref["source_path"] = invalid_path
            assert router.metadata_only_review_event_ref(
                invalid_ref,
                lifecycle_id="lifecycle-code-mutation-test",
                recommendation_id="code_mutation-blocked-step-test",
            ) is None, invalid_path
        legacy_route = router.opportunity_route({
            "opportunity_id": "legacy-lifecycle-fallback",
            "category": "code_mutation",
            "title": "Legacy lifecycle fallback",
        }, {"classification": "active_repair_plan_required"})
        assert legacy_route["lifecycle_id"] == router.lifecycle_id_for_origin("legacy-lifecycle-fallback"), legacy_route
        for candidate in payload["pm_job_candidates"]:
            assert candidate["department"], candidate
            assert candidate["department_owner"], candidate
            assert candidate["accountable_integrator"] == "main_session_veritas", candidate
            assert candidate["allowed_execution_mode"], candidate
        finance_candidates = [
            row for row in payload["pm_job_candidates"]
            if row["job_id"] == "pm-wf74-finance-source-open-quality-repair"
        ]
        assert finance_candidates[0]["department"] == "finance_wf78_wf84_wf85", finance_candidates
        assert finance_candidates[0]["owner_workflow"] == "WF78/WF84/WF85", finance_candidates
        cron_rows = [
            row for row in payload["recommendation_action_ledger"]
            if row["recommendation_id"] == "cron_migration-test"
        ]
        assert cron_rows[0]["status"] == "monitor_or_owner_gated", cron_rows
        assert cron_rows[0]["route"] == "cron_green_residue_monitor", cron_rows
        finance_rows = [
            row for row in payload["recommendation_action_ledger"]
            if row["recommendation_id"] == "finance_source_open-test"
        ]
        assert finance_rows[0]["status"] == "routed_to_pm", finance_rows
        assert finance_rows[0]["action_taken"] == "pm_job_candidate_created", finance_rows
        skill_rows = [
            row for row in payload["recommendation_action_ledger"]
            if row["recommendation_id"] == "skill_application-test"
        ]
        assert skill_rows[0]["status"] == "monitor_or_owner_gated", skill_rows
        assert skill_rows[0]["proof_commands"] == [], skill_rows
        assert skill_rows[0]["owner_gated_or_unsafe_commands"] == ["openclaw skills check"], skill_rows
        assert payload["cron_migration_repair_plan"]["classification"] == "green_no_repair_required"
        assert payload["cron_migration_repair_plan"]["status"] == "monitor_only"

        atomic_write_json(cron_control, {
            "status": "ok",
            "summary": {
                "blocked_count": 1,
                "escalation_signal_count": 1,
                "should_wake_main_session": True,
                "requires_attention_count": 2,
                "live_scheduler_last_run_exception_count": 1,
            },
            "escalation": {
                "escalation_signals": [
                    {
                        "source": "cron_job:Runtime - WF88 Wiki Synthesis Refresh",
                        "signal_class": "BLOCKED",
                        "status": "blocked",
                        "reason": "artifact_blocked_or_authority_widened",
                        "artifact": "data/state-history/recommendation-outcome-grades.jsonl",
                        "age_hours": 3.97,
                        "next_action": "Inspect the blocked artifact and stop before further consolidation.",
                    }
                ],
            },
            "freshness": {
                "live_scheduler_last_run_exceptions": [
                    {
                        "id": "cron-test-id",
                        "name": "Finance - Morning Paper Deployment Recommendation Cards",
                        "last_status": "error",
                        "consecutive_errors": 1,
                        "artifact_status": "needs_review",
                        "signal_class": "MAIN_SESSION_REQUIRED",
                    }
                ],
            },
            "validation": {"status": "ok"},
        })
        active_payload = router.build_payload(args)
        active_job_ids = {row["job_id"] for row in active_payload["pm_job_candidates"]}
        assert "pm-wf74-cron-migration-repair-plan" in active_job_ids, active_job_ids
        assert active_payload["summary"]["cron_repair_plan_count"] == 1, active_payload["summary"]
        assert active_payload["cron_migration_repair_plan"]["classification"] == "active_repair_plan_required"
        assert active_payload["cron_migration_repair_plan"]["status"] == "ready_for_main_session"
        assert active_payload["cron_migration_repair_plan"]["escalation_signals"][0]["artifact"] == (
            "data/state-history/recommendation-outcome-grades.jsonl"
        )
        assert active_payload["cron_migration_repair_plan"]["blocked_artifacts"][0]["artifact"] == (
            "data/state-history/recommendation-outcome-grades.jsonl"
        )
        assert active_payload["cron_migration_repair_plan"]["live_scheduler_last_run_exceptions"][0]["name"] == (
            "Finance - Morning Paper Deployment Recommendation Cards"
        )
        active_steps = {row["step"] for row in active_payload["cron_migration_repair_plan"]["repair_steps"]}
        assert "inspect_blocked_artifacts" in active_steps, active_steps
        assert "inspect_live_scheduler_exceptions" in active_steps, active_steps

        atomic_write_json(opportunity_queue, {
            "status": "ok",
            "generated_at_utc": "2026-06-20T00:00:00Z",
            "validation": {"status": "ok"},
            "opportunities": [
                {
                    "opportunity_id": "workflow_maturity-test",
                    "category": "workflow_maturity",
                    "title": "Convert workflow advancement blockers into implementation follow-ups",
                    "priority": 89,
                    "proposal_gate": "main_review_required",
                    "recommended_action": "Route repeated workflow blockers into scoped followups.",
                },
            ],
        })
        atomic_write_json(workflow_followups, {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {"followup_count": 1, "route_counts": {"cron_migration": 1}},
            "followups": [
                {
                    "followup_id": "cron-cron-migration",
                    "workflow_id": "CRON",
                    "route": "cron_migration",
                    "followup_type": "implementation_followup",
                    "blocker_class": "cron_attention_or_blocked",
                    "source_artifacts": ["tmp/cron-freshness-spine.json"],
                    "owner": "Veritas main session / cron migration lane",
                    "next_action": "Keep scheduled proof running; escalate only on stale/blocked/authority drift.",
                    "acceptance_validators": [
                        "python scripts\\cron_control_packet.py --write --validate",
                        "python scripts\\cron_reduction_inventory.py --write --validate",
                    ],
                    "stop_lines": ["No live cron add/edit/disable/delete without explicit owner approval and rollback proof."],
                },
            ],
        })
        followup_only_payload = router.build_payload(args)
        assert followup_only_payload["summary"]["cron_repair_plan_count"] == 1, followup_only_payload["summary"]
        assert followup_only_payload["cron_migration_repair_plan"]["active_repair_required"] is True
        assert followup_only_payload["cron_migration_repair_plan"]["status"] == "ready_for_main_session"
        assert followup_only_payload["cron_migration_repair_plan"]["source_opportunity_id"] == "cron-cron-migration"

        atomic_write_json(cron_control, {
            "status": "ok",
            "summary": {
                "blocked_count": 0,
                "escalation_signal_count": 0,
                "should_wake_main_session": False,
                "requires_attention_count": 0,
            },
            "validation": {"status": "ok"},
        })

        first_write = router.write_outputs(payload, args)
        second_write = router.write_outputs(payload, args)
        assert first_write["appended_history_event_count"] == 7, first_write
        assert second_write["appended_history_event_count"] == 0, second_write
        current_followups = load_json_artifact(followup_ledger)
        assert current_followups["summary"]["followup_count"] == 2, current_followups

    print("wf74_autonomy_work_router: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
