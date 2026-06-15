#!/usr/bin/env python3
"""Targeted tests for WF68 Telegram reply bridge."""
from __future__ import annotations

import wf68_telegram_reply_bridge as bridge


def message(content: str) -> dict:
    return {
        "row_id": "row-1",
        "timestamp_utc": "2026-06-02T05:19:06Z",
        "sender_id": "8650152206",
        "sender_label": "Randall (8650152206)",
        "content": content,
    }


def main() -> int:
    ack = bridge.parse_command(message("Ack wf68 delivery test 97"))
    assert ack is not None
    assert ack["command"] == "ACK", ack
    assert ack["workflow"] == "WF68", ack
    assert ack["message_ref"] == "97", ack
    assert ack["ticker"] is None, ack
    assert ack["blocked"] is False, ack

    review = bridge.parse_command(message("REVIEW WF68 ETN MESSAGE 97"))
    assert review is not None
    assert review["command"] == "REVIEW", review
    assert review["ticker"] == "ETN", review

    prepare = bridge.parse_command(message("prepare wf68 brk.b message 101"))
    assert prepare is not None
    assert prepare["command"] == "PREPARE", prepare
    assert prepare["ticker"] == "BRK.B", prepare
    assert prepare["message_ref"] == "101", prepare

    approve = bridge.parse_command(message("APPROVE WF68 ETN MESSAGE 97"))
    assert approve is not None
    assert approve["command"] == "APPROVE", approve
    assert approve["status"] == "BLOCKED_UNSUPPORTED_APPROVE", approve
    assert approve["blocked"] is True, approve

    ignored = bridge.parse_command(message("hello"))
    assert ignored is None

    main_message = bridge.build_main_message(review, bridge.DEFAULT_OUTPUT_JSON)
    assert "WF68 TELEGRAM REPLY RECEIVED" in main_message, main_message
    assert "Ticker: ETN" in main_message, main_message
    assert "APPROVE is not active" in main_message, main_message

    blocked_message = bridge.build_main_message(approve, bridge.DEFAULT_OUTPUT_JSON)
    assert "WF68 TELEGRAM REPLY BLOCKED" in blocked_message, blocked_message
    assert "No paper/live order" in blocked_message, blocked_message

    print("wf68_telegram_reply_bridge targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
