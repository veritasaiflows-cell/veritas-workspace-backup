#!/usr/bin/env python3
"""Regression checks for the WF74 V2 decision docket."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import wf74_decision_docket as docket
from market_data_utils import atomic_write_json


def write_inputs(root: Path) -> SimpleNamespace:
    opportunity_queue = root / "wf74-improvement-opportunity-queue.json"
    router = root / "wf74-autonomy-work-router.json"
    auto_patch = root / "wf74-auto-patch-proposer.json"
    improvement_ledger = root / "improvement-ledger-current.json"
    cron_control = root / "cron-control-packet.json"
    otel_control = root / "otel-ops-control.json"
    workflow_advancement = root / "workflow-advancement-scorecard.json"
    wf87_readiness = root / "wf87-v2-readiness-rollup.json"
    autonomy_spine = root / "autonomy-spine-readiness-rollup.json"
    out = root / "wf74-decision-docket.json"

    atomic_write_json(opportunity_queue, {
        "status": "ok",
        "opportunities": [
            {
                "opportunity_id": "cron-regression",
                "category": "cron_migration",
                "title": "Repair regressed cron signals after completed migration plan",
                "priority": 92,
                "recommended_action": "Repair the missing cron contract and rerun cron control.",
            },
            {
                "opportunity_id": "wf87-threshold",
                "category": "outcome_measurement",
                "title": "Track WF87 shadow outcomes until regular-session follow-up thresholds are met",
                "priority": 68,
                "recommended_action": "Collect regular-session evidence.",
            },
            {
                "opportunity_id": "execution-guardrail",
                "category": "execution",
                "title": "Maintain execution as proposal-only and exact-owner-gated",
                "priority": 35,
                "proposal_gate": "standing_guardrail_no_execution",
            },
            {
                "opportunity_id": "raw-prompt-capture",
                "category": "otel_learning_loop",
                "title": "Capture raw prompt and tool payload data",
                "priority": 99,
            },
            {
                "opportunity_id": "response-recommendation-gap",
                "category": "response_quality",
                "title": "Responses state facts and repairs but miss top recommendations",
                "priority": 86,
                "recommended_action": "Add response recommendation contract linting and rerun response-quality proof.",
            },
        ],
    })
    atomic_write_json(router, {
        "status": "ok",
        "workflow_implementation_followups": [
            {
                "followup_id": "autonomy-spine-dependency-rollup",
                "workflow_id": "AUTONOMY-SPINE",
                "route": "dependency_rollup",
                "title": "AUTONOMY-SPINE followup",
                "next_action": "Continue scheduled accrual and daylight/reconciliation proof.",
            }
        ],
        "pm_job_candidates": [],
    })
    atomic_write_json(auto_patch, {
        "status": "ok",
        "patch_plans": [
            {
                "plan_id": "wf74-v2-docket",
                "title": "Add WF74 V2 decision docket",
                "risk_class": "main_review_patch_required",
                "next_action": "Implement the docket and tests.",
            }
        ],
        "skill_workshop_requests": [
            {
                "plan_id": "skill-v2",
                "title": "Update disciplined implementation skill",
                "next_action": "Create Skill Workshop proposal.",
            }
        ],
        "owner_gated_reviews": [
            {
                "plan_id": "owner-v2",
                "title": "Owner-gated execution review",
                "next_action": "Ask Randall before execution.",
            },
            {
                "plan_id": "finance-review",
                "route": "finance_repair_review",
                "category": "finance_mutation",
                "title": "Route finance response-quality gaps into repair proposals",
                "next_action": "Keep as repair proposal-only; do not infer owner approval or mutate finance canon.",
            },
            {
                "plan_id": "execution-review",
                "route": "execution_guardrail_review",
                "category": "execution",
                "title": "Maintain execution as proposal-only and exact-owner-gated",
                "next_action": "Keep as standing visibility only; do not execute.",
            }
        ],
    })
    atomic_write_json(improvement_ledger, {"status": "ok", "latest_open_improvements": []})
    atomic_write_json(cron_control, {
        "status": "ok",
        "summary": {
            "blocked_count": 1,
            "escalation_signal_count": 1,
            "stale_count": 0,
            "should_wake_main_session": True,
        },
    })
    atomic_write_json(otel_control, {
        "status": "ok",
        "collector_health": {"status": "ok", "listening": True},
        "drift": {"status": "ok"},
        "volume_normalization_recommendation": {"status": "hold_config"},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    atomic_write_json(workflow_advancement, {"status": "ok", "summary": {"blocked_count": 3}})
    atomic_write_json(wf87_readiness, {"status": "phase_a_hardening_implemented_runtime_blocked"})
    atomic_write_json(autonomy_spine, {"status": "ok", "summary": {"final_state": "continue_accrual"}})
    return SimpleNamespace(
        opportunity_queue=str(opportunity_queue),
        router=str(router),
        auto_patch=str(auto_patch),
        improvement_ledger=str(improvement_ledger),
        cron_control=str(cron_control),
        otel_control=str(otel_control),
        workflow_advancement=str(workflow_advancement),
        wf87_readiness=str(wf87_readiness),
        autonomy_spine=str(autonomy_spine),
        out=str(out),
        write_md="",
        write=False,
        validate=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        args = write_inputs(Path(td))
        payload = docket.build_payload(args)
        assert payload["status"] == "ok", payload["validation"]
        states_by_source = {
            row["source_id"]: row["action_state"]
            for row in payload["rows"]
        }
        assert states_by_source["cron-regression"] == "fix_now", states_by_source
        assert states_by_source["wf87-threshold"] == "market_session_accrual", states_by_source
        assert states_by_source["execution-guardrail"] == "monitor_only", states_by_source
        assert states_by_source["raw-prompt-capture"] == "hard_stop", states_by_source
        assert states_by_source["response-recommendation-gap"] == "fix_now", states_by_source
        assert states_by_source["autonomy-spine-dependency-rollup"] == "market_session_accrual", states_by_source
        assert states_by_source["wf74-v2-docket"] == "fix_now", states_by_source
        assert states_by_source["skill-v2"] == "skill_proposal", states_by_source
        assert states_by_source["owner-v2"] == "owner_decision", states_by_source
        assert states_by_source["finance-review"] == "monitor_only", states_by_source
        assert states_by_source["execution-review"] == "monitor_only", states_by_source
        assert payload["summary"]["fix_now_count"] == 3, payload["summary"]
        assert payload["summary"]["hard_stop_count"] == 1, payload["summary"]
        for row in payload["rows"]:
            assert row["next_action"], row
            assert row["stop_lines"], row
            assert row["authority_boundary"]["review_only"] is True, row
    with tempfile.TemporaryDirectory() as td:
        args = write_inputs(Path(td))
        improvement_ledger = Path(args.improvement_ledger)
        data = {
            "status": "ok",
            "latest_open_improvements": [
                {
                    "improvement_id": "collector_config-monitor",
                    "source_key": "collector_config-monitor",
                    "category": "collector_config",
                    "title": "Review OTEL event-rate drift against the weekly baseline",
                    "priority": 88,
                    "recommended_action": "Review OTEL event ingestion/volume as local operations only; do not mutate collector/runtime config without exact owner-approved change proof.",
                    "next_action": "Review OTEL event ingestion/volume as local operations only; do not mutate collector/runtime config without exact owner-approved change proof.",
                    "follow_up": {
                        "detail": "OTEL event-rate drift is operational monitor-only; closure requires a non-blocked current OTEL packet.",
                    },
                },
                {
                    "improvement_id": "collector_config-mutation",
                    "source_key": "collector_config-mutation",
                    "category": "collector_config",
                    "title": "Change collector config for telemetry capture",
                    "priority": 90,
                    "recommended_action": "Mutate collector config after owner approval.",
                },
            ],
        }
        atomic_write_json(improvement_ledger, data)
        payload = docket.build_payload(args)
        states_by_source = {
            row["source_id"]: row["action_state"]
            for row in payload["rows"]
        }
        reasons_by_source = {
            row["source_id"]: row["classification_reason"]
            for row in payload["rows"]
        }
        assert states_by_source["collector_config-monitor"] == "monitor_only", states_by_source
        assert reasons_by_source["collector_config-monitor"] == "otel_ops_current_monitor_only", reasons_by_source
        assert states_by_source["collector_config-mutation"] == "hard_stop", states_by_source
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
