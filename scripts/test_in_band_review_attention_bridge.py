#!/usr/bin/env python3
"""Focused regression tests for the review-only intraday attention bridge."""
from __future__ import annotations

import in_band_review_attention_bridge as bridge


QUOTE_TIME = "2026-08-13T14:00:00Z"
REFRESH_TIME = "2026-08-13T14:01:00Z"


def quote(symbol: str, price: float, *, fresh: bool = True) -> dict:
    return {
        "symbol": symbol,
        "price": price,
        "freshness_status": "fresh" if fresh else "stale",
        "calendar_freshness_status": "fresh_intraday" if fresh else "stale_unexpected",
        "age_seconds": 30 if fresh else 3600,
        "source_timestamp_utc": QUOTE_TIME,
    }


def sync_row(symbol: str, *, candidate: bool, conflict: bool = False) -> dict:
    review = {
        "candidate": candidate,
        "recommended_entry_policy_action": "main_review_required" if candidate else "monitor_until_setup_valid",
        "surface_conflicts": ["technical_refresh_not_in_band_but_band_proposals_in_band"] if conflict else [],
    }
    return {
        "ticker": symbol,
        "primary_state": "monitor_only",
        "entry_band_low": 90.0,
        "entry_band_high": 110.0,
        "stop_or_invalidation": 80.0,
        "entry_policy_review": review,
        "blockers": ["promotion_gate_verdict=in_band_review_hold"],
        "warnings": ["entry_policy_review_candidate_non_authorizing"] if candidate else [],
        "promotion_gate_verdict": "in_band_review_hold",
    }


def inputs() -> dict:
    return {
        "quote_proof": {
            "status": "ok",
            "generated_at_utc": QUOTE_TIME,
            "snapshots": [quote("CAT", 100.0), quote("GOOG", 100.0), quote("ECL", 100.0), quote("TIER_C", 100.0)],
        },
        "hygiene": {
            "status": "ok",
            "generated_at_utc": REFRESH_TIME,
            "rows": [
                {"ticker": "CAT", "band": {"current_band_low": 90.0, "current_band_high": 110.0, "current_stop": 80.0}},
                {"ticker": "GOOG", "band": {"current_band_low": 90.0, "current_band_high": 110.0, "current_stop": 80.0}},
                {"ticker": "ECL", "band": {"current_band_low": 90.0, "current_band_high": 110.0, "current_stop": 80.0}},
            ],
        },
        "sync": {
            "status": "ok",
            "generated_at_utc": REFRESH_TIME,
            "rows": [sync_row("CAT", candidate=True), sync_row("ECL", candidate=True), sync_row("GOOG", candidate=False, conflict=True), sync_row("TIER_C", candidate=True)],
        },
        "router": {
            "status": "ok",
            "generated_at_utc": "2026-08-13T13:00:00Z",
            "rows": [
                {"ticker": "CAT", "auto_tier": "Tier B", "auto_state": "B-CANDIDATE"},
                {"ticker": "ECL", "auto_tier": "Tier B", "auto_state": "B-CANDIDATE"},
                {"ticker": "GOOG", "auto_tier": "Tier A", "auto_state": "A-CHALLENGED"},
                {"ticker": "TIER_C", "auto_tier": "Tier C", "auto_state": "C-MONITOR"},
            ],
        },
    }


def test_fresh_review_and_repair_attention_are_visible_without_authority() -> None:
    packet = bridge.build_payload(**inputs(), generated_at_utc="2026-08-13T14:02:00Z")
    assert packet["status"] == "ok", packet
    assert packet["summary"]["review_attention_tickers"] == ["CAT", "ECL"], packet
    assert packet["summary"]["repair_attention_tickers"] == ["GOOG"], packet
    assert packet["operator_alert"]["action"] == "REVIEW_ATTENTION", packet
    assert packet["operator_alert"]["external_delivery_allowed"] is False, packet
    assert packet["authority_boundary"]["capital_deployment_approved"] is False, packet
    for row in packet["review_attention"] + packet["repair_attention"]:
        assert row["derived_band_status"] == "IN_BAND", row
        assert row["capital_deployment_approved"] is False, row
        assert row["trade_or_execution_approved"] is False, row
    assert packet["repair_attention"][0]["recommended_action"] == "technical_surface_reconciliation_required", packet


def test_stale_hygiene_or_sync_fails_closed() -> None:
    payload = inputs()
    payload["hygiene"]["generated_at_utc"] = "2026-08-13T13:59:00Z"
    packet = bridge.build_payload(**payload)
    assert packet["status"] == "blocked", packet
    assert "band_hygiene_older_than_quote_proof" in packet["validation"]["errors"], packet
    assert packet["review_attention"] == [], packet


def test_stale_tier_router_fails_closed() -> None:
    payload = inputs()
    payload["router"]["generated_at_utc"] = "2026-08-12T13:00:00Z"
    packet = bridge.build_payload(**payload)
    assert packet["status"] == "blocked", packet
    assert "tier_router_not_current_for_quote_proof" in packet["validation"]["errors"], packet
    assert packet["review_attention"] == [], packet


def test_stale_and_lower_tier_rows_are_suppressed() -> None:
    payload = inputs()
    payload["quote_proof"]["snapshots"] = [quote("CAT", 100.0, fresh=False), quote("TIER_C", 100.0)]
    packet = bridge.build_payload(**payload)
    assert packet["status"] == "ok", packet
    assert packet["summary"]["review_attention_count"] == 0, packet
    assert packet["summary"]["repair_attention_count"] == 0, packet
    assert packet["operator_alert"]["action"] == "NO_REPLY", packet


def main() -> int:
    test_fresh_review_and_repair_attention_are_visible_without_authority()
    test_stale_hygiene_or_sync_fails_closed()
    test_stale_tier_router_fails_closed()
    test_stale_and_lower_tier_rows_are_suppressed()
    print("in_band_review_attention_bridge targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
