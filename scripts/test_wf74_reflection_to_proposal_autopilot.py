from __future__ import annotations

import wf74_improvement_opportunity_queue as queue
import wf74_reflection_to_proposal_autopilot as autopilot


def test_autopilot_generates_proposals_without_apply_authority() -> None:
    queue_payload = queue.build_payload({
        "wf74_runner": {"summary": {"steps_blocked": 0}},
        "coding_outcome": {"ledger_summary": {"ledger_row_count": 5, "model_attributed_count": 0}},
        "coding_runtime": {"kpis": {"validator_elapsed_seconds": 8, "validator_target_seconds": 10}},
        "otel_ops": {"drift": {"status": "ok"}},
        "model_run": {"summary": {"lane_register_rows": 5}},
        "model_learning": {},
        "finance_response": {"summary": {}},
        "pm_control": {},
        "field_depth_packet": {"status": "owner_decision_required", "current_collector_posture": {}},
    })
    payload = autopilot.build_payload(queue_payload, limit=4)
    assert payload["validation"]["status"] == "ok"
    assert payload["authority_boundary"]["auto_apply_allowed"] is False
    assert payload["authority_boundary"]["skill_application_allowed"] is False
    assert payload["authority_boundary"]["collector_config_mutation_allowed"] is False
    assert payload["summary"]["proposal_count"] >= 2
    statuses = {row["proposal_status"] for row in payload["proposals"]}
    assert "main_review_required" in statuses
    assert "owner_decision_required" in statuses
    assert "exact_owner_approval_required" in statuses
    assert "auto_apply" not in statuses
    assert "auto_execute" not in statuses


if __name__ == "__main__":
    test_autopilot_generates_proposals_without_apply_authority()
    print("wf74_reflection_to_proposal_autopilot_tests_passed")
