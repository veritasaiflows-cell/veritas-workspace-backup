from __future__ import annotations

import finance_response_quality_repair_loop as repair


def base_slice() -> dict:
    return {
        "schema": "veritas.finance_response_quality_slice.v1",
        "status": "ok",
        "summary": {
            "blocked_archetype_count": 0,
            "warning_archetype_count": 0,
            "source_freshness_blocked_count": 0,
            "source_open_blocked_count": 0,
            "remediation_tracks_needing_repair": 0,
        },
        "source_state": {
            "source_freshness_status": "ok",
            "source_freshness_validation": "ok",
            "source_freshness_blocked_count": 0,
            "source_open_blocked_count": 0,
        },
        "archetypes": [
            {
                "archetype_id": "staleness_refusal_answer",
                "status": "ok",
                "quality_score": 1.0,
                "failed_required_checks": [],
            }
        ],
        "remediation_tracks": [],
        "source_artifacts": {
            "source_freshness_gate": "tmp/trade-grade-source-freshness-gate.json",
        },
        "authority_boundary": {
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def base_queue() -> dict:
    return {
        "schema": "veritas.wf74_improvement_opportunity_queue.v1",
        "status": "ok",
        "source_artifacts": {
            "finance_response": "tmp/finance-response-quality-slice.json",
            "wf74_runner": "tmp/wf74-model-quality-collection-cron-runner.json",
        },
        "opportunities": [],
        "authority_boundary": {
            "finance_canon_or_portfolio_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def test_blocked_source_freshness_generates_proposal() -> None:
    slice_payload = base_slice()
    slice_payload["summary"]["source_freshness_blocked_count"] = 2
    slice_payload["summary"]["remediation_tracks_needing_repair"] = 1
    slice_payload["source_state"]["source_freshness_blocked_count"] = 2
    slice_payload["remediation_tracks"] = [
        {
            "track_id": "source_freshness_repair",
            "status": "needs_repair",
            "owner_workflow": "WF85 source/freshness gate and WF78 source-open repair",
            "current_gap_count": 2,
            "target_next_checkpoint_count": 2,
            "next_commands": ["python scripts\\trade_grade_repair_conveyor.py --write --validate"],
        }
    ]
    queue_payload = base_queue()
    queue_payload["opportunities"] = [
        {
            "opportunity_id": "finance_mutation-test",
            "category": "finance_mutation",
            "proposal_gate": "finance_repair_proposal_only",
        }
    ]

    payload = repair.build_payload({
        "finance_response_quality_slice": slice_payload,
        "improvement_opportunity_queue": queue_payload,
    })

    assert payload["validation"]["status"] == "ok"
    assert payload["summary"]["proposal_count"] >= 2
    repair_types = {row["repair_type"] for row in payload["proposals"]}
    assert "source_freshness_repair" in repair_types
    assert "remediation_track_repair" in repair_types
    freshness = next(row for row in payload["proposals"] if row["repair_type"] == "source_freshness_repair")
    assert freshness["affected_archetype"] == "staleness_refusal_answer"
    assert freshness["affected_gap"] == "source_freshness_blocked_count"
    assert freshness["source_opportunity_ids"] == ["finance_mutation-test"]
    assert freshness["no_mutation_authority_flags"]["finance_canon_or_portfolio_mutation_allowed"] is False
    assert freshness["no_mutation_authority_flags"]["paper_or_live_execution_allowed"] is False
    assert "rollback" in freshness["rollback_or_proof_requirement"].lower()


def test_clean_slice_noop_ok() -> None:
    payload = repair.build_payload({
        "finance_response_quality_slice": base_slice(),
        "improvement_opportunity_queue": base_queue(),
    })

    assert payload["status"] == "noop_ok"
    assert payload["summary"]["proposal_count"] == 0
    assert payload["validation"]["status"] == "warning"
    assert "no_repair_proposals_generated" in payload["validation"]["warnings"]


def test_authority_drift_validation_error() -> None:
    slice_payload = base_slice()
    slice_payload["authority_boundary"]["capital_deployment_approved"] = True
    payload = repair.build_payload({
        "finance_response_quality_slice": slice_payload,
        "improvement_opportunity_queue": base_queue(),
    })

    assert payload["status"] == "blocked"
    assert payload["validation"]["status"] == "error"
    assert any("source_authority_drift_detected" in error for error in payload["validation"]["errors"])


if __name__ == "__main__":
    test_blocked_source_freshness_generates_proposal()
    test_clean_slice_noop_ok()
    test_authority_drift_validation_error()
    print("finance_response_quality_repair_loop_tests_passed")
