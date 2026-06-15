#!/usr/bin/env python3
"""Targeted tests for WF85 paper-deployment notification digest."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import wf85_paper_deployment_notification_digest as digest


def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def base_manager(target: str | None = None) -> dict:
    return {
        "status": "ok",
        "generated_at_utc": stamp(),
        "target_session_date": target or datetime.now(timezone.utc).date().isoformat(),
        "candidate_card_reviews": [
            {
                "ticker": "XLB",
                "status": "conditional_ready_after_fresh_monday_quote",
                "packet_rank": 1,
                "rank": 2,
                "band_status": "IN_BAND",
                "order": {
                    "symbol": "XLB",
                    "side": "buy",
                    "type": "limit",
                    "time_in_force": "day",
                    "limit_price": 51.68,
                    "notional": 250.0,
                },
                "owner_approval_status": "pending_exact_randall_approval",
                "card_path": "tmp/card.json",
                "request_path": "tmp/request.json",
                "blockers": [],
                "required_before_execution": ["exact Randall approval"],
            }
        ],
    }


def test_manager_rows_fresh_vs_stale() -> None:
    ready, near = digest.build_manager_rows(base_manager(), 36)
    assert [row["ticker"] for row in ready] == ["XLB"]
    assert not near
    assert ready[0]["paper_execution_ready"] is False

    stale = base_manager("2026-06-01")
    ready, near = digest.build_manager_rows(stale, 36)
    assert not ready
    assert [row["ticker"] for row in near] == ["XLB"]
    assert any("target_session_not_today" in item for item in near[0]["blockers"])


def test_digest_blocks_authority_drift() -> None:
    authority = deepcopy(digest.AUTHORITY_BOUNDARY)
    authority["paper_order_submit_allowed"] = True
    violations = digest.authority_violations(authority)
    assert "paper_order_submit_allowed" in violations


def test_message_preview_never_activates_approve() -> None:
    packet = {
        "status": "ok",
        "operator_action": "TELEGRAM_NOTIFY",
        "summary": {
            "deployment_ready_count": 0,
            "execution_ready_count": 0,
            "near_deployment_count": 1,
            "watch_count": 1,
            "blocked_or_repair_count": 0,
        },
        "categories": {
            "deployment_ready": [],
            "near_deployment": [{"ticker": "VRT", "readiness_kind": "near_deployment", "blockers": ["fresh_quote_required"]}],
            "watch": [{"ticker": "GOOG", "decision_state": "monitor_only", "band_status": "IN_BAND"}],
            "blocked_or_repair": [],
        },
    }
    msg = digest.build_message_preview(packet, 5)
    assert "APPROVE is not active" in msg
    assert "Execution-ready now: 0" in msg
    assert "VRT" in msg
    assert "Paper Deployment Radar" in msg
    assert "fresh quote needed" in msg
    assert "near_deployment" not in msg


def main() -> int:
    test_manager_rows_fresh_vs_stale()
    test_digest_blocks_authority_drift()
    test_message_preview_never_activates_approve()
    print("wf85_paper_deployment_notification_digest targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
