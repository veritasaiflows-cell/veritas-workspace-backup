#!/usr/bin/env python3
from __future__ import annotations

import pm_post_repair_quiescence_refresh as refresh


def test_clean_quiescence_is_ok() -> None:
    validation = refresh.validate_quiescence(
        [{"name": "cron_control_packet", "ok": True}],
        {
            "cron_freshness_status": "ok",
            "cron_control_status": "ok",
            "cron_blocked_count": 0,
            "cron_escalation_signal_count": 0,
            "cron_should_wake_main_session": False,
            "wf74_router_status": "ok",
            "wf74_cron_signal_classification": "green_no_repair_required",
            "pm_queue_status": "ok",
            "pm_ready_job_count": 0,
            "pm_blocked_job_count": 0,
            "pm_control_status": "ok",
            "otel_learning_loop_status": "ok",
            "status_card_validation_status": "ok",
        },
    )
    assert validation["status"] == "ok", validation


def test_ready_jobs_after_refresh_are_warning_not_blocker() -> None:
    validation = refresh.validate_quiescence(
        [{"name": "cron_control_packet", "ok": True}],
        {
            "cron_freshness_status": "ok",
            "cron_control_status": "ok",
            "cron_blocked_count": 0,
            "cron_escalation_signal_count": 0,
            "cron_should_wake_main_session": False,
            "wf74_router_status": "ok",
            "wf74_cron_signal_classification": "green_no_repair_required",
            "pm_queue_status": "ok",
            "pm_ready_job_count": 1,
            "pm_blocked_job_count": 0,
            "pm_control_status": "ok",
            "otel_learning_loop_status": "ok",
            "status_card_validation_status": "ok",
        },
    )
    assert validation["status"] == "warning", validation
    assert "pm_queue_has_ready_or_blocked_jobs_after_refresh" in validation["warnings"], validation


def test_cron_blocker_after_refresh_is_blocked() -> None:
    validation = refresh.validate_quiescence(
        [{"name": "cron_control_packet", "ok": True}],
        {
            "cron_freshness_status": "ok",
            "cron_control_status": "ok",
            "cron_blocked_count": 1,
            "cron_escalation_signal_count": 0,
            "cron_should_wake_main_session": False,
            "wf74_router_status": "ok",
            "wf74_cron_signal_classification": "active_repair_plan_required",
            "pm_queue_status": "ok",
            "pm_ready_job_count": 0,
            "pm_blocked_job_count": 0,
            "pm_control_status": "ok",
            "otel_learning_loop_status": "ok",
            "status_card_validation_status": "ok",
        },
    )
    assert validation["status"] == "blocked", validation
    assert "cron_not_quiescent" in validation["errors"], validation


def main() -> int:
    test_clean_quiescence_is_ok()
    test_ready_jobs_after_refresh_are_warning_not_blocker()
    test_cron_blocker_after_refresh_is_blocked()
    print("pm_post_repair_quiescence_refresh_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
