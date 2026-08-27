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


def fresh_quotes() -> dict[str, dict]:
    return {
        "XLB": {
            "symbol": "XLB",
            "price": 51.68,
            "freshness_status": "fresh",
            "age_seconds": 30,
        }
    }


def test_manager_rows_fresh_vs_stale() -> None:
    ready, near, legacy = digest.build_manager_rows(base_manager(), 36, fresh_quotes())
    assert [row["ticker"] for row in ready] == ["XLB"]
    assert not near
    assert not legacy
    assert ready[0]["paper_execution_ready"] is False

    stale = base_manager("2026-06-01")
    ready, near, legacy = digest.build_manager_rows(stale, 36, fresh_quotes())
    assert not ready
    assert not near
    assert [row["ticker"] for row in legacy] == ["XLB"]
    assert legacy[0]["readiness_kind"] == "wf67_manager_legacy_audit_only"
    assert legacy[0]["legacy_audit_only"] is True
    assert legacy[0]["current_surface_eligible"] is False
    assert any("target_session_not_today" in item for item in legacy[0]["blockers"])
    assert legacy[0]["card_path"] is None
    assert legacy[0]["request_path"] is None
    assert legacy[0]["wf67_manager_card_reference_suppressed"] is True


def test_digest_blocks_authority_drift() -> None:
    authority = deepcopy(digest.AUTHORITY_BOUNDARY)
    authority["paper_order_submit_allowed"] = True
    violations = digest.authority_violations(authority)
    assert "paper_order_submit_allowed" in violations


def test_source_stale_reason_flags_missing_and_old_source() -> None:
    assert digest.source_stale_reason("morning_paper_cards", {}, 1) == "morning_paper_cards_generated_at_missing"
    old = {"age_hours": 2.5}
    assert digest.source_stale_reason("morning_paper_cards", old, 1) == "morning_paper_cards_stale:2.5h_gt_1h"
    fresh = {"age_hours": 0.25}
    assert digest.source_stale_reason("morning_paper_cards", fresh, 1) is None


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


def test_watch_only_digest_is_telegram_visible_but_not_preparable() -> None:
    packet = {
        "status": "ok",
        "operator_action": "TELEGRAM_NOTIFY",
        "summary": {
            "deployment_ready_count": 0,
            "execution_ready_count": 0,
            "near_deployment_count": 0,
            "watch_count": 1,
            "blocked_or_repair_count": 0,
        },
        "categories": {
            "deployment_ready": [],
            "near_deployment": [],
            "legacy_wf67_manager_audit": [{"ticker": "VRT", "readiness_kind": "wf67_manager_legacy_audit_only"}],
            "watch": [{"ticker": "GOOG", "decision_state": "monitor_only", "band_status": "IN_BAND"}],
            "blocked_or_repair": [],
        },
    }
    msg = digest.build_message_preview(packet, 5)
    assert "Near Deployment" not in msg
    assert "Watch" in msg
    assert "PREPARE is disabled until a name reaches near-deployment" in msg
    assert "APPROVE is not active" in msg


def test_stale_quote_suppresses_price_band_and_stop_in_message() -> None:
    stale_row = digest.apply_quote_display_dependency(
        {
            "ticker": "GOOG",
            "decision_state": "monitor_only",
            "latest_known_price": 313.33,
            "band_status": "IN_BAND",
            "entry_band_low": 286.37,
            "entry_band_high": 300.76,
            "stop_or_invalidation": 277.63,
        },
        {"symbol": "GOOG", "price": 313.33, "freshness_status": "stale", "age_seconds": 7200},
    )
    packet = {
        "summary": {
            "deployment_ready_count": 0,
            "execution_ready_count": 0,
            "near_deployment_count": 0,
            "watch_count": 1,
            "blocked_or_repair_count": 0,
        },
        "categories": {"deployment_ready": [], "near_deployment": [], "watch": [stale_row], "blocked_or_repair": []},
        "validation": {},
    }

    message = digest.build_message_preview(packet, 5)

    assert "fresh quote required; price/band/stop display suppressed" in message
    assert "$313.33" not in message
    assert "$286.37" not in message
    assert "$277.63" not in message


def test_current_quote_allows_numeric_display_dependency() -> None:
    context = digest.quote_display_context({"price": 100.0, "freshness_status": "fresh", "age_seconds": 900})
    assert context["price_display_allowed"] is True


def main() -> int:
    test_manager_rows_fresh_vs_stale()
    test_digest_blocks_authority_drift()
    test_source_stale_reason_flags_missing_and_old_source()
    test_message_preview_never_activates_approve()
    test_watch_only_digest_is_telegram_visible_but_not_preparable()
    test_stale_quote_suppresses_price_band_and_stop_in_message()
    test_current_quote_allows_numeric_display_dependency()
    print("wf85_paper_deployment_notification_digest targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
