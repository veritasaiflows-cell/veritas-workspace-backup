#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pm_priority_pickup_predispatch_prefilter as module


NOW = datetime(2026, 8, 30, 17, 0, 0, tzinfo=timezone.utc)
OK_STEPS = [{"ok": True, "error_code": None}, {"ok": True, "error_code": None}]


def quiet_handoff(**overrides) -> dict:
    base = {
        "status": "no_priority",
        "receipt": "NO_DELTA",
        "input_signature": {"sha256": "a" * 64},
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "summary": {
            "priority_counts": {"P0": 0, "P1": 0, "P2": 0},
            "selected_priority_id": None,
            "selected_priority": None,
            "re_escalation_interval_checks": {"P0": 4, "P1": 8},
        },
        "items": [],
    }
    base.update(overrides)
    return base


def active_handoff(level: str = "P1") -> dict:
    return quiet_handoff(
        status="needs_main_review",
        receipt="NEW_PRIORITY",
        input_signature={"sha256": "b" * 64},
        summary={
            "priority_counts": {"P0": 0, "P1": 1, "P2": 0},
            "selected_priority_id": "PRI-2026-08-30-001",
            "selected_priority": level,
            "re_escalation_interval_checks": {"P0": 4, "P1": 8},
        },
    )


OK_EXECUTOR = {"status": "ok", "validation": {"status": "ok"}}


def decide(handoff, executor=None, steps=None, previous=None, now=NOW):
    return module.decide_wake(
        handoff, executor if executor is not None else OK_EXECUTOR,
        steps if steps is not None else OK_STEPS,
        previous or {}, now,
    )


def test_quiet_state_does_not_wake_main():
    decision = decide(quiet_handoff())
    assert decision["wake_required"] is False
    assert decision["wake_reasons"] == []


def test_new_priority_wakes_main():
    decision = decide(active_handoff())
    assert decision["wake_required"] is True
    assert "handoff_receipt:NEW_PRIORITY" in decision["wake_reasons"]
    assert "selected_priority_pending_main_disposition" in decision["wake_reasons"]
    assert decision["suppressed"] is False


def test_gate_fails_open_on_every_unclear_state():
    # A missing handoff must never be read as "nothing to do".
    assert decide({})["wake_required"] is True
    assert "handoff_missing_or_unreadable" in decide({})["wake_reasons"]

    bad_validation = quiet_handoff(validation={"status": "blocked", "errors": ["x"]})
    assert "handoff_validation_not_ok" in decide(bad_validation)["wake_reasons"]

    blocked = quiet_handoff(status="blocked", receipt="BLOCKED")
    assert decide(blocked)["wake_required"] is True

    failed_steps = [{"ok": True, "error_code": None}, {"ok": False, "error_code": "step_timeout"}]
    reasons = decide(quiet_handoff(), steps=failed_steps)["wake_reasons"]
    assert "deterministic_step_failed:step_timeout" in reasons

    assert "action_executor_output_missing" in decide(quiet_handoff(), executor={})["wake_reasons"]
    blocked_exec = {"status": "blocked", "validation": {"status": "blocked"}}
    reasons = decide(quiet_handoff(), executor=blocked_exec)["wake_reasons"]
    assert "action_executor_blocked" in reasons
    assert "action_executor_validation_not_ok" in reasons


def test_unchanged_priority_is_suppressed_inside_the_reescalation_window():
    handoff = active_handoff("P1")
    first = decide(handoff)
    previous = {
        "decision": first,
        "wake": {"dispatched": True, "dispatched_at_utc": "2026-08-30T15:00:00Z"},
    }
    # 2h elapsed against an 8h P1 window.
    decision = decide(handoff, previous=previous)
    assert decision["wake_required"] is True
    assert decision["suppressed"] is True
    assert decision["suppression_reason"] == "unchanged_priority_inside_reescalation_window"
    assert decision["reescalation_hours"] == 8.0


def test_suppression_expires_and_p0_uses_the_shorter_window():
    handoff = active_handoff("P0")
    previous = {
        "decision": decide(handoff),
        "wake": {"dispatched": True, "dispatched_at_utc": "2026-08-30T12:30:00Z"},
    }
    # 4.5h elapsed against a 4h P0 window.
    decision = decide(handoff, previous=previous)
    assert decision["reescalation_hours"] == 4.0
    assert decision["suppressed"] is False


def test_a_changed_priority_breaks_suppression_immediately():
    previous = {
        "decision": decide(active_handoff("P1")),
        "wake": {"dispatched": True, "dispatched_at_utc": "2026-08-30T16:55:00Z"},
    }
    escalated = active_handoff("P0")
    escalated["receipt"] = "ESCALATED_PRIORITY"
    escalated["input_signature"] = {"sha256": "c" * 64}
    decision = decide(escalated, previous=previous)
    assert decision["suppressed"] is False


def test_suppressed_runs_do_not_restart_the_window():
    handoff = active_handoff("P1")
    first = decide(handoff)
    dispatched_at = "2026-08-30T15:00:00Z"
    previous = {"decision": first, "wake": {"dispatched": True, "dispatched_at_utc": dispatched_at}}

    # Simulate the carry-forward main() performs on a suppressed run.
    suppressed = decide(handoff, previous=previous)
    assert suppressed["suppressed"] is True
    carried = {
        "decision": suppressed,
        "wake": {"dispatched": False, "dispatched_at_utc": dispatched_at},
    }
    # 8.5h after the original wake, the window must have expired, not reset.
    later = decide(handoff, previous=carried, now=NOW + timedelta(hours=6, minutes=30))
    assert later["suppressed"] is False


def test_wake_message_carries_boundaries_and_no_rerun_instruction():
    handoff = active_handoff("P0")
    message = module.build_wake_message(handoff, decide(handoff))
    assert "do not re-run them" in message
    assert "PRI-2026-08-30-001" in message
    for boundary in ("capital deployment", "config/auth/runtime mutation", "owner approval inference"):
        assert boundary in message
    assert "NO_REPLY" in message
    # The gate must not hand Main a broader mandate than the systemEvent had.
    assert "--execute-safe" in message and "helper spawn" in message


def test_dispatch_is_inert_in_dry_run():
    record = module.dispatch_wake("body", job_id=module.PICKUP_JOB_ID, timeout_seconds=10, dry_run=True)
    assert record["dispatched"] is False
    assert record["dry_run"] is True
    assert record["error_code"] == "dry_run_not_dispatched"
    assert record["session_key"].startswith(f"agent:main:cron:{module.PICKUP_JOB_ID}:run:")


def test_wake_session_key_is_attributable_by_the_usage_extractor():
    import cron_main_session_usage_metadata as usage

    record = module.dispatch_wake("body", job_id=module.PICKUP_JOB_ID, timeout_seconds=10, dry_run=True)
    parsed = usage.parse_cron_run_session_key(record["session_key"])
    assert parsed is not None
    assert parsed[0] == module.PICKUP_JOB_ID


def test_validate_rejects_an_ungrounded_or_mutated_report():
    handoff = quiet_handoff()
    decision = decide(handoff)
    wake = {"dispatched": False, "dry_run": False, "error_code": "wake_not_required"}
    report = module.build_report(OK_STEPS, handoff, OK_EXECUTOR, decision, wake, now=NOW, job_id=module.PICKUP_JOB_ID)
    assert module.validate(report)["status"] == "ok"

    tampered = module.build_report(OK_STEPS, handoff, OK_EXECUTOR, decision, dict(wake, dispatched=True), now=NOW, job_id=module.PICKUP_JOB_ID)
    assert "wake_dispatched_without_decision" in module.validate(tampered)["errors"]

    widened = module.build_report(OK_STEPS, handoff, OK_EXECUTOR, decision, wake, now=NOW, job_id=module.PICKUP_JOB_ID)
    widened["authority_boundary"] = dict(module.AUTHORITY_BOUNDARY, capital_deployment_allowed=True)
    assert "authority_boundary_mutated" in module.validate(widened)["errors"]

    no_reason = module.build_report(OK_STEPS, handoff, OK_EXECUTOR, dict(decision, wake_required=True, wake_reasons=[]), wake, now=NOW, job_id=module.PICKUP_JOB_ID)
    assert "wake_required_without_reason" in module.validate(no_reason)["errors"]


def test_failed_step_is_a_warning_not_a_silent_pass():
    steps = [{"ok": False, "error_code": "step_nonzero_exit"}, {"ok": True, "error_code": None}]
    handoff = quiet_handoff()
    decision = decide(handoff, steps=steps)
    wake = {"dispatched": False, "dry_run": True, "error_code": "dry_run_not_dispatched"}
    report = module.build_report(steps, handoff, OK_EXECUTOR, decision, wake, now=NOW, job_id=module.PICKUP_JOB_ID)
    result = module.validate(report)
    assert result["status"] == "warning"
    assert "deterministic_step_failed:step_nonzero_exit" in result["warnings"]


def main() -> int:
    test_quiet_state_does_not_wake_main()
    test_new_priority_wakes_main()
    test_gate_fails_open_on_every_unclear_state()
    test_unchanged_priority_is_suppressed_inside_the_reescalation_window()
    test_suppression_expires_and_p0_uses_the_shorter_window()
    test_a_changed_priority_breaks_suppression_immediately()
    test_suppressed_runs_do_not_restart_the_window()
    test_wake_message_carries_boundaries_and_no_rerun_instruction()
    test_dispatch_is_inert_in_dry_run()
    test_wake_session_key_is_attributable_by_the_usage_extractor()
    test_validate_rejects_an_ungrounded_or_mutated_report()
    test_failed_step_is_a_warning_not_a_silent_pass()
    print("pm priority pickup predispatch prefilter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
