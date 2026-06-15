from __future__ import annotations

import wf74_improvement_opportunity_queue as queue


def sample_inputs() -> dict:
    return {
        "wf74_runner": {"summary": {"steps_blocked": 0}},
        "coding_outcome": {
            "ledger_summary": {
                "ledger_row_count": 10,
                "model_attributed_count": 0,
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
    }


def test_queue_has_required_cadences_and_gates() -> None:
    payload = queue.build_payload(sample_inputs())
    assert payload["validation"]["status"] == "ok"
    assert payload["authority_boundary"]["code_mutation_allowed"] is False
    assert payload["authority_boundary"]["collector_config_mutation_allowed"] is False
    assert payload["authority_boundary"]["paper_or_live_execution_allowed"] is False
    for required in ("code_mutation", "skill_application", "collector_config", "finance_mutation", "execution"):
        assert required in payload["review_cadence"]
    gates = {row["proposal_gate"] for row in payload["opportunities"]}
    assert "main_review_required" in gates
    assert "owner_decision_required" in gates
    assert "standing_guardrail_no_execution" in gates
    assert "auto_apply" not in gates
    assert "auto_execute" not in gates


if __name__ == "__main__":
    test_queue_has_required_cadences_and_gates()
    print("wf74_improvement_opportunity_queue_tests_passed")
