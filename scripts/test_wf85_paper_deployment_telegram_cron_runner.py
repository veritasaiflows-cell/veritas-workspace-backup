#!/usr/bin/env python3
"""Targeted tests for the WF85 paper-deployment Telegram cron wrapper."""
from __future__ import annotations

import wf85_paper_deployment_telegram_cron_runner as runner


def step(name: str, ok: bool) -> dict:
    return {"name": name, "ok": ok, "required": True}


def blocked_digest() -> dict:
    return {
        "status": "blocked",
        "validation": {"status": "blocked", "errors": ["wf85_runner_not_ok:blocked"]},
    }


def test_blocked_digest_sent_to_telegram_is_validation_ok() -> None:
    status, operator_action, errors, warnings, confirmation = runner.classify_validation(
        [step("wf85_paper_deployment_notification_digest", False)],
        blocked_digest(),
        {"status": "SENT", "sent_count": 1, "blockers": []},
        send=True,
    )

    assert status == "blocked"
    assert operator_action == "TELEGRAM_BLOCKER_SENT"
    assert errors == []
    assert "digest_blocked_surfaced_by_telegram" in warnings
    assert "digest_validation_blocked_surfaced_by_telegram" in warnings
    assert confirmation["blocker_surfaced_by_telegram"] is True


def test_blocked_morning_builder_sent_to_telegram_is_validation_ok() -> None:
    status, operator_action, errors, warnings, confirmation = runner.classify_validation(
        [step("morning_paper_deployment_recommendation_builder", False)],
        blocked_digest(),
        {"status": "SENT", "sent_count": 1, "blockers": []},
        send=True,
    )

    assert status == "blocked"
    assert operator_action == "TELEGRAM_BLOCKER_SENT"
    assert errors == []
    assert "digest_blocked_surfaced_by_telegram" in warnings
    assert confirmation["blocker_surfaced_by_telegram"] is True


def test_blocked_digest_without_send_fails_closed() -> None:
    status, operator_action, errors, _warnings, confirmation = runner.classify_validation(
        [step("wf85_paper_deployment_notification_digest", False)],
        blocked_digest(),
        {"status": "NO_REPLY", "sent_count": 0, "blockers": []},
        send=True,
    )

    assert status == "blocked"
    assert operator_action == "BLOCKED"
    assert "required_step_failed:wf85_paper_deployment_notification_digest" in errors
    assert "digest_validation_not_ok" in errors
    assert "blocked_digest_not_delivered" in errors
    assert confirmation["blocker_surfaced_by_telegram"] is False


def test_send_failure_fails_closed() -> None:
    status, operator_action, errors, _warnings, confirmation = runner.classify_validation(
        [step("wf85_paper_deployment_telegram_notifier", False)],
        {"status": "ok", "validation": {"status": "ok"}},
        {"status": "SEND_FAILED", "sent_count": 0, "blockers": ["openclaw_message_send_failed"]},
        send=True,
    )

    assert status == "blocked"
    assert operator_action == "BLOCKED"
    assert "required_step_failed:wf85_paper_deployment_telegram_notifier" in errors
    assert "telegram_send_failed" in errors
    assert confirmation["notifier_status"] == "SEND_FAILED"


def test_default_morning_builder_command_is_ledger_only() -> None:
    command = runner.morning_builder_command()
    assert "--ledger-only" in command
    assert "--write" in command
    assert "--validate" in command


def test_full_morning_builder_command_is_opt_in() -> None:
    command = runner.morning_builder_command(full_refresh=True)
    assert "--ledger-only" not in command
    assert "--write" in command
    assert "--validate" in command


def test_quote_proof_refresh_precedes_digest() -> None:
    command = runner.pre_digest_quote_refresh_command()
    assert command[-1] == "scripts\\intraday_quote_snapshot_proof.py"


def main() -> int:
    test_blocked_digest_sent_to_telegram_is_validation_ok()
    test_blocked_morning_builder_sent_to_telegram_is_validation_ok()
    test_blocked_digest_without_send_fails_closed()
    test_send_failure_fails_closed()
    test_default_morning_builder_command_is_ledger_only()
    test_full_morning_builder_command_is_opt_in()
    test_quote_proof_refresh_precedes_digest()
    print("wf85_paper_deployment_telegram_cron_runner targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
