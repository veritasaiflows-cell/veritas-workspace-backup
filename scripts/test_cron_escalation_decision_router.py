#!/usr/bin/env python3
"""Focused checks for cron_escalation_decision_router."""
from __future__ import annotations

from cron_escalation_decision_router import action_bucket, build_wf85_packet


def test_internal_send_contract_action_routes_to_decision_packet() -> None:
    bucket, disposition, next_action = action_bucket(
        {
            "id": "enabled_contract_internal_send_with_delivery_none",
            "contract": "state/cron-contracts/finance-wf85-paper-deployment-telegram-radar.json",
            "classification": "owner_decision",
        }
    )
    assert bucket == "owner_decision_delivery_semantics"
    assert disposition == "decision_packet_prepared"
    assert "WF85 Telegram radar decision packet" in next_action


def test_silent_contract_mentions_send_is_noise() -> None:
    bucket, disposition, next_action = action_bucket(
        {
            "id": "contract_text_mentions_send_but_executable_is_silent",
            "classification": "auto_refresh",
        }
    )
    assert bucket == "scanner_false_positive_or_noise"
    assert disposition == "no_cron_change_recommended"
    assert "scanner" in next_action


def test_wf85_packet_recognizes_self_describing_internal_delivery() -> None:
    rows = [
        {
            "exists": True,
            "delivery_mode": "none",
            "payload_mentions_send": True,
            "internal_delivery_mode": "telegram_via_runner",
            "cron_delivery_mode_remains_none": True,
            "delivery_only_review_notification": True,
            "owner_telegram_delivery_allowed": True,
            "customer_or_public_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }
    ]
    packet = build_wf85_packet("2026-06-18T00:00:00Z", rows)
    assert packet["validation"]["status"] == "ok"
    assert "self-describing" in packet["current_read"]
    assert packet["options"][0]["recommended"] is True


if __name__ == "__main__":
    test_internal_send_contract_action_routes_to_decision_packet()
    test_silent_contract_mentions_send_is_noise()
    test_wf85_packet_recognizes_self_describing_internal_delivery()
    print("cron_escalation_decision_router tests ok")
