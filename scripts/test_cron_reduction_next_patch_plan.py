#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import cron_reduction_next_patch_plan as plan


def old_timestamp() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=72)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sample_contracts() -> dict:
    return {
        "contracts": [
            {"id": "phase1_delivery_daily", "status": "source_jobs_absent", "source_jobs": ["daily builder", "daily handoff"]},
            {"id": "phase1_delivery_weekly", "status": "source_jobs_absent", "source_jobs": ["weekly builder", "weekly handoff"]},
            {"id": "phase1_delivery_monthly", "status": "source_jobs_absent", "source_jobs": ["monthly builder", "monthly handoff"]},
            {"id": "phase2_postclose_paper_reconciliation", "source_jobs": ["paper refresh", "shadow recon"]},
            {"id": "phase2_wf68_alert_digest", "source_jobs": ["alert producer", "alert digest"]},
            {"id": "phase2_morning_market_paper", "source_jobs": ["morning one"]},
            {"id": "phase2_midday_market_paper", "source_jobs": ["midday one"]},
            {"id": "phase1_runtime_future_session", "source_jobs": ["future session"]},
            {"id": "phase1_runtime_otel", "source_jobs": ["otel"]},
            {"id": "phase1_runtime_wf74_send", "source_jobs": ["wf74"]},
            {"id": "phase3_runtime_weekly_improvement_proof", "source_jobs": ["weekly proof"]},
        ]
    }


def sample_payload() -> dict:
    return plan.build_payload(
        control={
            "summary": {
                "enabled_job_count": 47,
                "blocked_count": 0,
                "requires_attention_count": 1,
                "should_wake_main_session": False,
                "escalation_signal_count": 0,
            }
        },
        inventory={"summary": {"total_jobs": 81, "enabled_jobs": 47, "disabled_jobs": 34}},
        contracts_payload=sample_contracts(),
        phase1={
            "status": "ok",
            "components": [
                {"name": "runtime_future_session", "status": "ok", "generated_at_utc": old_timestamp()},
                {"name": "runtime_otel", "status": "ok", "generated_at_utc": old_timestamp()},
                {"name": "runtime_wf74_send", "status": "ok", "generated_at_utc": old_timestamp()},
            ],
        },
        phase2={
            "status": "blocked",
            "components": [
                {"name": "postclose_paper_reconciliation", "status": "ok", "generated_at_utc": old_timestamp()},
                {"name": "wf68_alert_digest", "status": "ok", "generated_at_utc": old_timestamp()},
                {"name": "morning_market_paper", "status": "blocked", "generated_at_utc": old_timestamp()},
                {"name": "midday_market_paper", "status": "blocked", "generated_at_utc": old_timestamp()},
            ],
        },
        phase3={"status": "blocked", "validation": {"status": "blocked"}},
        contract_validator={
            "summary": {
                "drift_count": 0,
                "missing_live_job_count": 0,
                "prompt_bloat_count": 0,
                "multiline_truncation_risk_count": 0,
            }
        },
    )


def batch_by_id(payload: dict, batch_id: str) -> dict:
    for item in payload.get("candidate_batches", []):
        if item.get("id") == batch_id:
            return item
    raise AssertionError(f"missing batch {batch_id}")


def test_plan_is_review_only_and_valid() -> None:
    payload = sample_payload()

    assert payload["status"] == "ok"
    assert payload["current_state"]["enabled_jobs"] == 47
    assert payload["current_state"]["gap_to_27"] == 20
    assert payload["authority_boundary"]["cron_schedule_mutation_allowed"] is False
    assert payload["authority_boundary"]["job_add_disable_delete_allowed"] is False
    assert "enabled_job_count_above_post_optimization_cap" in payload["validation"]["warnings"]


def test_delivery_series_is_not_counted_as_next_savings() -> None:
    payload = sample_payload()
    delivery = batch_by_id(payload, "finance_delivery_series")

    assert delivery["status"] == "already_absent_from_live_fleet"
    assert delivery["expected_enabled_savings"] == 0


def test_old_phase2_successes_need_fresh_rerun_before_patch() -> None:
    payload = sample_payload()

    assert batch_by_id(payload, "phase2_postclose_paper_reconciliation")["status"] == "needs_fresh_rerun_before_patch"
    assert batch_by_id(payload, "phase2_wf68_alert_digest")["status"] == "needs_fresh_rerun_before_patch"
    assert batch_by_id(payload, "phase2_morning_market_paper")["status"] == "blocked_pending_market_window_shadow"


if __name__ == "__main__":
    test_plan_is_review_only_and_valid()
    test_delivery_series_is_not_counted_as_next_savings()
    test_old_phase2_successes_need_fresh_rerun_before_patch()
    print("ok")
