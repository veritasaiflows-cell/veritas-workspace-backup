#!/usr/bin/env python3
"""Targeted tests for WF85 paper-deployment Telegram notifier."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf85_paper_deployment_telegram_notifier as notifier


def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def digest(status: str = "ok") -> dict:
    return {
        "status": status,
        "operator_action": "TELEGRAM_NOTIFY",
        "generated_at_utc": stamp(),
        "authority_boundary": {
            "paper_or_live_execution_allowed": False,
            "paper_order_submit_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "ok" if status == "ok" else "blocked", "errors": ["x"] if status != "ok" else []},
        "summary": {
            "deployment_ready_tickers": [],
            "near_deployment_tickers": ["VRT"],
            "wf67_guard_status": "blocked",
            "wf67_guard_ready_for_submit_cancel": False,
            "wf85_approval_card_draft_count": 0,
        },
        "message_preview": "WF85 PAPER DEPLOYMENT RADAR\nAPPROVE is not active in Telegram.",
    }


def watch_digest(symbol: str) -> dict:
    return {
        "status": "ok",
        "operator_action": "TELEGRAM_NOTIFY",
        "generated_at_utc": stamp(),
        "authority_boundary": {
            "paper_or_live_execution_allowed": False,
            "paper_order_submit_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "ok", "errors": []},
        "summary": {
            "deployment_ready_tickers": [],
            "near_deployment_tickers": [],
            "watch_tickers": [symbol],
            "blocked_or_repair_tickers": [],
            "wf67_guard_status": "blocked",
            "wf67_guard_ready_for_submit_cancel": False,
            "wf85_approval_card_draft_count": 0,
        },
        "categories": {
            "watch": [{"ticker": symbol, "decision_state": "monitor_only"}],
            "blocked_or_repair": [],
        },
        "message_preview": f"Paper Deployment Radar\n\nWatch\n- {symbol}: watch only\n\nAPPROVE is not active.",
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        digest_path = td / "digest.json"
        state_path = td / "state.json"
        output_path = td / "out.json"
        write(digest_path, digest())
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(state_path),
            "--output",
            str(output_path),
            "--write",
            "--validate",
        ])
        assert rc == 0
        result = json.loads(output_path.read_text(encoding="utf-8"))
        assert result["status"] == "DRY_RUN_READY", result
        assert result["authority"]["paper_or_live_order_submission_allowed"] is False
        assert "APPROVE is not active" in result["message_preview"]
        assert "\n" in result["message_preview"]
        assert result["delivery_chunk_count"] >= 1
        assert result["delivery_messages_preview"]
        assert all("\n" not in item for item in result["delivery_messages_preview"])
        assert result["delivery_messages_preview"][0].startswith("WF85 Paper Deployment Radar alert part 1/")
        assert "APPROVE is not active" in result["delivery_messages_preview"][0]

        write(state_path, {"sent_keys": {result["dedupe_key"]: {"sent_at_utc": stamp(), "message_kind": "radar"}}})
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(state_path),
            "--output",
            str(output_path),
            "--write",
            "--validate",
            "--send",
        ])
        assert rc == 0
        duplicate = json.loads(output_path.read_text(encoding="utf-8"))
        assert duplicate["status"] == "NO_REPLY", duplicate
        assert duplicate["duplicate"] is True
        assert duplicate["sent_count"] == 0

        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(state_path),
            "--output",
            str(output_path),
            "--write",
            "--validate",
            "--alert-window",
            "midday",
        ])
        assert rc == 0
        window_distinct = json.loads(output_path.read_text(encoding="utf-8"))
        assert window_distinct["status"] == "DRY_RUN_READY", window_distinct
        assert window_distinct["duplicate"] is False
        assert window_distinct["alert_window"] == "midday"
        assert window_distinct["dedupe_key"] != result["dedupe_key"]

        write(digest_path, watch_digest("GOOG"))
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(td / "watch-state.json"),
            "--output",
            str(output_path),
            "--write",
            "--validate",
            "--alert-window",
            "morning",
        ])
        assert rc == 0
        watch_one = json.loads(output_path.read_text(encoding="utf-8"))
        assert watch_one["status"] == "DRY_RUN_READY", watch_one
        assert watch_one["dedupe_key"]

        write(digest_path, watch_digest("NVDA"))
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(td / "watch-state.json"),
            "--output",
            str(output_path),
            "--write",
            "--validate",
            "--alert-window",
            "morning",
        ])
        assert rc == 0
        watch_two = json.loads(output_path.read_text(encoding="utf-8"))
        assert watch_two["status"] == "DRY_RUN_READY", watch_two
        assert watch_two["dedupe_key"] != watch_one["dedupe_key"]

        bad = digest("blocked")
        write(digest_path, bad)
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(state_path),
            "--output",
            str(output_path),
            "--write",
            "--validate",
        ])
        assert rc == 0
        blocked = json.loads(output_path.read_text(encoding="utf-8"))
        assert blocked["status"] == "DRY_RUN_READY", blocked
        assert blocked["message_kind"] == "blocker", blocked

        stale = digest()
        stale["generated_at_utc"] = "2026-06-01T00:00:00Z"
        write(digest_path, stale)
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(state_path),
            "--output",
            str(output_path),
            "--write",
            "--validate",
            "--max-age-minutes",
            "1",
        ])
        assert rc == 0
        stale_result = json.loads(output_path.read_text(encoding="utf-8"))
        assert stale_result["status"] == "BLOCKED", stale_result
        assert any(str(item).startswith("digest_stale") for item in stale_result["blockers"])

        write(digest_path, digest())
        rc = notifier.main([
            "--digest",
            str(digest_path),
            "--state",
            str(td / "outside-hours-state.json"),
            "--output",
            str(output_path),
            "--write",
            "--validate",
            "--market-hours-only",
        ])
        assert rc == 0
        market_hours_result = json.loads(output_path.read_text(encoding="utf-8"))
        if not market_hours_result["market_hours_gate"]["in_regular_session"]:
            assert market_hours_result["status"] == "NO_REPLY", market_hours_result
            assert market_hours_result["message_kind"] == "outside_market_hours", market_hours_result
            assert market_hours_result["delivery_chunk_count"] == 0, market_hours_result

    print("wf85_paper_deployment_telegram_notifier targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
