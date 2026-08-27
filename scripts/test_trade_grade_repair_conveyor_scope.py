#!/usr/bin/env python3
"""Regression checks for WF85 repair-conveyor blocker scope."""
from __future__ import annotations

from trade_grade_repair_conveyor import (
    ATOMIC_FIVE_FAMILIES,
    ATOMIC_REPAIR_FALSE_AUTHORITY,
    atomic_five_family_repair_errors,
    atomic_five_family_repair_queue,
    finance_domain_blocker,
    implementation_blocker_for_row,
    pilot_contract_errors,
    repair_scope,
    scope_summary,
)


def main() -> int:
    lanes = [
        "monitor_only",
        "invalidation_or_below_stop_review_only",
        "wf78_band_stop_context_repair",
        "tier_c_thin_monitor_deferred",
    ]
    rows = [
        {
            "ticker": f"T{i}",
            "repair_lane": lane,
            "repair_scope": repair_scope(lane),
            "finance_domain_blocker": finance_domain_blocker(lane),
            "implementation_blocker": implementation_blocker_for_row(lane),
        }
        for i, lane in enumerate(lanes, start=1)
    ]
    summary = scope_summary(rows, [])
    assert summary["pm_blocker_scope"] == "finance_domain_only", summary
    assert summary["implementation_queue_posture"] == "not_an_implementation_blocker", summary
    assert summary["implementation_blocker_count"] == 0, summary
    assert summary["control_plane_blocker_count"] == 0, summary
    assert summary["finance_domain_repair_item_count"] == len(rows), summary
    assert summary["total_repair_conveyor_row_count"] == len(rows), summary
    assert summary["owner_finance_gate_count"] == 0, summary
    assert summary["normal_finance_repair_rows_create_pm_implementation_jobs"] is False, summary
    assert summary["only_validation_errors_create_implementation_blockers"] is True, summary

    owner_gate_rows = rows + [
        {
            "ticker": "OWNER",
            "repair_lane": "review_ready_waiting_approval_gate",
            "repair_scope": repair_scope("review_ready_waiting_approval_gate"),
            "finance_domain_blocker": finance_domain_blocker("review_ready_waiting_approval_gate"),
            "implementation_blocker": implementation_blocker_for_row("review_ready_waiting_approval_gate"),
        }
    ]
    owner_summary = scope_summary(owner_gate_rows, [])
    assert owner_summary["total_repair_conveyor_row_count"] == len(owner_gate_rows), owner_summary
    assert owner_summary["finance_domain_repair_item_count"] == len(rows), owner_summary
    assert owner_summary["finance_or_owner_gate_repair_item_count"] == len(owner_gate_rows), owner_summary
    assert owner_summary["owner_finance_gate_count"] == 1, owner_summary
    assert owner_summary["finance_domain_blocker_count"] == len(rows), owner_summary

    failed = scope_summary(rows, ["approval_card_drafts_present_before_conveyor_repair"])
    assert failed["pm_blocker_scope"] == "control_plane_validation_failed", failed
    assert failed["implementation_queue_posture"] == "implementation_attention_required", failed
    assert failed["implementation_blocker_count"] == 1, failed
    assert failed["control_plane_blocker_count"] == 1, failed

    safe_pilot = {
        "ticker": "AVGO",
        "auto_tier": "Tier B",
        "decision_state": "monitor_only",
        "source_open_status": "verified",
        "band_status": "IN_BAND",
        "stop_or_invalidation_present": True,
    }
    assert pilot_contract_errors([safe_pilot]) == [], safe_pilot

    blocked_state = dict(safe_pilot, ticker="BAD", decision_state="no_chase")
    assert pilot_contract_errors([blocked_state]) == ["BAD"], blocked_state

    missing_source = dict(safe_pilot, ticker="SRC", source_open_status="blocked")
    assert pilot_contract_errors([missing_source]) == ["SRC"], missing_source

    stale_all = [f"stale:{family}" for family in ATOMIC_FIVE_FAMILIES]
    atomic = atomic_five_family_repair_queue(
        [
            {"ticker": "AOS", "auto_tier": "Tier A", "required_depth": "decision_repair", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": stale_all},
            {"ticker": "ALLE", "auto_tier": "Tier A", "required_depth": "decision_repair", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": stale_all},
            {"ticker": "AAPL", "auto_tier": "Tier B", "required_depth": "promotion_repair", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": ["stale:catalyst_earnings_state"]},
            {"ticker": "AVGO", "auto_tier": "Tier B", "required_depth": "promotion_repair", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": stale_all},
            {"ticker": "TSM", "auto_tier": "Tier B", "required_depth": "promotion_repair", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": stale_all},
            {"ticker": "DASH", "auto_tier": "Tier B", "required_depth": "promotion_repair", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": stale_all},
            {"ticker": "IGNORED", "auto_tier": "Tier C", "required_depth": "thin_monitor", "resolution_state": "blocked_unresolved_tier_ab_debt", "stale_families": stale_all},
        ],
        "2026-08-11T04:00:00Z",
    )
    assert [row["ticker"] for row in atomic] == ["ALLE", "AOS", "DASH", "TSM", "AVGO", "AAPL"]
    assert atomic_five_family_repair_errors(atomic) == []
    for row in atomic:
        assert len(row["family_dispositions"]) == 5
        assert {item["family"] for item in row["family_dispositions"]} == set(ATOMIC_FIVE_FAMILIES)
        assert row["first_family"] == "catalyst_earnings_state"
        assert row["source_open_manual_only"] is True
        for key in ATOMIC_REPAIR_FALSE_AUTHORITY:
            assert row["authority_boundary"][key] is False
    aapl = next(row for row in atomic if row["ticker"] == "AAPL")
    aapl_status = {item["family"]: item["status"] for item in aapl["family_dispositions"]}
    assert aapl_status["catalyst_earnings_state"] == "refresh_required"
    assert aapl_status["technical_posture"] == "retained_current"
    dependencies = {
        item["family"]: item["depends_on"]
        for item in next(row for row in atomic if row["ticker"] == "DASH")["family_dispositions"]
    }
    assert dependencies["recommendation_support"] == list(ATOMIC_FIVE_FAMILIES[:3])
    assert dependencies["deployment_readiness"] == list(ATOMIC_FIVE_FAMILIES[:4])
    assert atomic_five_family_repair_errors(atomic + [dict(atomic[0])]) == ["atomic_repair_queue_duplicate_ticker"]

    print("trade_grade_repair_conveyor_scope: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
