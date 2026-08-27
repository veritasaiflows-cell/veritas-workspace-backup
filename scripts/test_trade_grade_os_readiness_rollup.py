#!/usr/bin/env python3
"""Acceptance tests for trade_grade_os_readiness_rollup.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trade_grade_os_readiness_rollup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("trade_grade_os_readiness_rollup", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    cards_payload = {
        "cards": [
            {"ticker": "AAA", "decision_state": "monitor_only"},
            {"ticker": "BBB", "decision_state": "review_ready"},
            {"ticker": "CCC", "decision_state": "blocked_missing_freshness"},
        ]
    }
    approval_gate = {
        "summary": {
            "review_ready_count": 1,
            "approval_card_draft_count": 0,
            "approval_draft_blocked_count": 3,
        }
    }
    full_answer = {"summary": {"full_answer_built_count": 200}}
    semantic = module.wf85_semantic_rollup(cards_payload, approval_gate, full_answer)
    assert semantic["answer_ready_count"] == 200
    assert semantic["review_only_decision_ready_count"] == 1
    assert semantic["approval_card_eligible_count"] == 0
    assert semantic["approval_card_blocked_valid_reason_count"] == 3
    assert semantic["blocked_count_semantics"] == "approval_draft_blocked_count_not_system_failure"

    bridge = module.wf86_bridge_rollup(
        {
            "decisions": [
                {"ticker": "AAA", "shadow_eligible": True, "assisted_review_ready": False},
                {"ticker": "BBB", "shadow_eligible": True, "assisted_review_ready": True},
            ],
            "summary": {"shadow_threshold_met": False},
        },
        {
            "cards": [
                {"ticker": "BBB", "owner_approval_status": "pending", "wf67_guard_status": "ok", "wf67_ready_for_paper_submit_cancel": True}
            ]
        },
        {"status": "submitted", "request_summary": {"symbol": "BBB"}},
        {"summary": {"open_orders_count": 1}, "positions": []},
    )
    assert bridge["shadow_only_count"] == 1
    assert bridge["assisted_paper_eligible_count"] == 1
    assert bridge["exact_approval_required_count"] == 1
    assert bridge["guard_ready_but_not_approved_count"] == 1
    assert bridge["submitted_open_count"] == 1
    assert bridge["fill_reconciled_count"] == 0
    assert bridge["unresolved_after_reconciliation_count"] == 0

    unresolved_bridge = module.wf86_bridge_rollup(
        {"decisions": [], "summary": {"shadow_threshold_met": False}},
        {"cards": []},
        {"status": "submitted", "request_summary": {"symbol": "BBB"}},
        {"summary": {"open_orders_count": 0}, "positions": []},
    )
    assert unresolved_bridge["submitted_open_count"] == 0
    assert unresolved_bridge["fill_reconciled_count"] == 0
    assert unresolved_bridge["unresolved_after_reconciliation_count"] == 1

    classified_bridge = module.wf86_bridge_rollup(
        {"decisions": [], "summary": {"shadow_threshold_met": False}},
        {"cards": []},
        {"status": "submitted", "request_summary": {"symbol": "VRT"}},
        {"summary": {"open_orders_count": 0}, "positions": []},
        {
            "status": "warning",
            "validation": {"status": "warning"},
            "summary": {"submitted_order_count": 2, "filled_count": 1, "terminal_non_fill_count": 1},
            "classifications": [
                {"symbol": "GOOG", "classification": "filled", "source_path": "tmp/goog.json", "evidence": "alpaca_order_history_match"},
                {"symbol": "VRT", "classification": "expired", "source_path": "tmp/vrt.json", "evidence": "alpaca_order_history_match"},
            ],
        },
    )
    assert classified_bridge["fill_reconciled_count"] == 1
    assert classified_bridge["terminal_non_fill_count"] == 1
    assert classified_bridge["unresolved_after_reconciliation_count"] == 0
    assert classified_bridge["order_history_classifier_status"] == "warning"

    tier_errors, tier_warnings = module.tier_a_b_guard_findings(
        {
            "validation_status": "warning",
            "stale_complete_band_context_count": 2,
        }
    )
    assert tier_errors == []
    assert tier_warnings == ["tier_a_b_stale_complete_band_context_finance_domain_debt_present"]

    decision_depth = module.decision_depth_rollup(
        {
            "cards": [
                {"ticker": "OWN", "auto_tier": "A", "decision_state": "review_ready"},
                {"ticker": "REV", "auto_tier": "B", "decision_state": "review_ready"},
                {"ticker": "FRH", "auto_tier": "A", "decision_state": "monitor_only"},
                {"ticker": "THN", "auto_tier": "C", "decision_state": "monitor_only"},
                {"ticker": "COV", "auto_tier": "B", "decision_state": "monitor_only"},
            ]
        },
        {"results": [{"ticker": "COV"}], "summary": {"full_answer_built_count": 300}},
        {
            "rows": [
                {"ticker": "OWN", "auto_tier": "A", "resolution_state": "fresh", "stale_families": []},
                {"ticker": "REV", "auto_tier": "B", "resolution_state": "fresh", "stale_families": []},
                {"ticker": "FRH", "auto_tier": "A", "resolution_state": "fresh", "stale_families": []},
                {"ticker": "THN", "auto_tier": "C", "resolution_state": "resolved_thin_monitor_current", "stale_families": []},
                {"ticker": "COV", "auto_tier": "B", "resolution_state": "stale", "stale_families": ["finance"]},
            ]
        },
        {
            "rows": [
                {"ticker": "OWN", "repair_lane": "fresh_quote_review_ready_pilot_candidate", "source_open_status": "verified", "freshness_status": "fresh"},
                {"ticker": "REV", "repair_lane": "fresh_quote_review_ready_pilot_candidate", "source_open_status": "verified", "freshness_status": "fresh"},
                {"ticker": "FRH", "repair_lane": "none", "source_open_status": "verified", "freshness_status": "fresh"},
                {"ticker": "THN", "repair_lane": "none", "source_open_status": "verified", "freshness_status": "fresh"},
                {"ticker": "COV", "repair_lane": "repair_required", "source_open_status": "unverified", "freshness_status": "stale"},
            ]
        },
        {
            "approval_card_drafts": [{"ticker": "OWN"}],
            "authority_boundary": {
                "review_only": True,
                "decision_support_only": True,
                "approval_card_draft_allowed": True,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "money_movement_allowed": False,
                "customer_or_external_delivery_allowed": False,
                "canon_or_portfolio_mutation_allowed": False,
                "cash_sizing_or_risk_rule_mutation_allowed": False,
                "customer_account_pii_or_suitability_data_allowed": False,
                "owner_approval_inferred": False,
            },
        },
    )
    depth_by_ticker = {row["ticker"]: row for row in decision_depth["rows"]}
    assert depth_by_ticker["OWN"]["depth_state"] == "approval_card_draft_candidate"
    assert depth_by_ticker["OWN"]["approval_card_draft_candidate"] is True
    assert depth_by_ticker["OWN"]["owner_card_candidate"] is False
    assert depth_by_ticker["REV"]["depth_state"] == "review_card_candidate"
    assert depth_by_ticker["FRH"]["depth_state"] == "fresh_decision_context"
    assert depth_by_ticker["THN"]["depth_state"] == "thin_monitor"
    assert depth_by_ticker["COV"]["depth_state"] == "coverage_floor"
    depth_summary = decision_depth["summary"]
    assert depth_summary["ticker_count"] == 5
    assert depth_summary["coverage_floor_count"] == 5
    assert depth_summary["coverage_only_count"] == 1
    assert depth_summary["approval_card_draft_candidate_count"] == 1
    assert depth_summary["owner_card_candidate_count"] == 0
    assert depth_summary["review_card_candidate_count"] == 1
    assert depth_summary["fresh_decision_context_count"] == 1
    assert depth_summary["thin_monitor_count"] == 1
    assert depth_summary["review_pipeline_candidate_count"] == 2
    assert depth_summary["production_or_decision_grade_count"] == 1
    assert depth_summary["headline_state"] == "decision_grade_depth_ready"
    incomplete_authority = module.decision_depth_rollup(
        {"cards": [{"ticker": "OWN", "auto_tier": "A", "decision_state": "review_ready"}]},
        {"results": [{"ticker": "OWN"}]},
        {"rows": [{"ticker": "OWN", "auto_tier": "A", "resolution_state": "fresh", "stale_families": []}]},
        {"rows": [{
            "ticker": "OWN",
            "repair_lane": "fresh_quote_review_ready_pilot_candidate",
            "source_open_status": "verified",
            "freshness_status": "fresh",
        }]},
        {
            "approval_card_drafts": [{"ticker": "OWN"}],
            "authority_boundary": {"owner_approval_inferred": False},
        },
    )
    incomplete_row = incomplete_authority["rows"][0]
    assert incomplete_row["approval_card_draft_candidate"] is False
    assert incomplete_row["owner_card_candidate"] is False
    unsafe_authority = {
        "review_only": True,
        "decision_support_only": True,
        "approval_card_draft_allowed": True,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": True,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "customer_or_external_delivery_allowed": False,
        "canon_or_portfolio_mutation_allowed": False,
        "cash_sizing_or_risk_rule_mutation_allowed": False,
        "customer_account_pii_or_suitability_data_allowed": False,
        "owner_approval_inferred": False,
    }
    unsafe = module.decision_depth_rollup(
        {"cards": [{"ticker": "OWN", "auto_tier": "A", "decision_state": "review_ready"}]},
        {"results": [{"ticker": "OWN"}]},
        {"rows": [{"ticker": "OWN", "auto_tier": "A", "resolution_state": "fresh", "stale_families": []}]},
        {"rows": [{"ticker": "OWN", "repair_lane": "fresh_quote_review_ready_pilot_candidate", "source_open_status": "verified", "freshness_status": "fresh"}]},
        {"approval_card_drafts": [{"ticker": "OWN"}], "authority_boundary": unsafe_authority},
    )
    assert unsafe["rows"][0]["approval_card_draft_candidate"] is False
    for key in (
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "customer_or_external_delivery_allowed",
        "canon_or_portfolio_mutation_allowed",
        "owner_approval_inferred",
    ):
        assert decision_depth["authority_boundary"][key] is False

    ledger = {
        "summary": {
            "ticker_count": 300,
            "freshness_state_counts": {"fresh": 21, "stale_refreshable": 258},
            "top_stale_families": [{"family": "stale:technical_posture", "count": 258}],
        }
    }
    tier_weighted_rows = (
        [{"ticker": f"A{i}", "auto_tier": "Tier A", "tier_weighted_resolved": True} for i in range(12)]
        + [{"ticker": f"B{i}", "auto_tier": "Tier B", "tier_weighted_resolved": True} for i in range(16)]
        + [{"ticker": f"D{i}", "auto_tier": "Tier B", "tier_weighted_resolved": False} for i in range(33)]
        + [{"ticker": f"C{i}", "auto_tier": "Tier C", "tier_weighted_resolved": True} for i in range(239)]
    )
    readiness = module.trade_grade_data_readiness_rollup(
        ledger, {"status": "ok", "rows": tier_weighted_rows}
    )
    # Tier C monitor-grade rows must never enter the decision denominator.
    assert readiness["decision_slice_ticker_count"] == 61
    assert readiness["decision_slice_resolved_count"] == 28
    assert readiness["decision_slice_threshold"] == 48
    assert readiness["decision_slice_unresolved_count"] == 33
    assert readiness["ready_for_trade_grade_decisions"] is False
    assert readiness["status"] == "data_not_ready"
    assert readiness["reason"] == "tier_a_b_resolved_count_below_threshold"
    assert readiness["readiness_basis"] == "tier_a_b_decision_slice"
    assert readiness["universe_reference"]["ticker_count"] == 300
    assert readiness["universe_reference"]["raw_true_fresh_ticker_count"] == 21

    ready_rows = [
        {"ticker": f"A{i}", "auto_tier": "Tier A", "tier_weighted_resolved": True} for i in range(50)
    ] + [{"ticker": f"D{i}", "auto_tier": "Tier B", "tier_weighted_resolved": False} for i in range(10)]
    ready = module.trade_grade_data_readiness_rollup(ledger, {"status": "ok", "rows": ready_rows})
    assert ready["ready_for_trade_grade_decisions"] is True
    assert ready["status"] == "data_ready"
    assert ready["reason"] == "tier_a_b_resolved_count_meets_threshold"

    # Fail-closed: a missing or non-ok tier-weighted artifact must never read ready.
    for degraded in ({}, {"status": "blocked", "rows": ready_rows}, {"status": "ok", "rows": []}):
        blocked = module.trade_grade_data_readiness_rollup(ledger, degraded)
        assert blocked["ready_for_trade_grade_decisions"] is False
        assert blocked["status"] == "data_not_ready"
    assert module.trade_grade_data_readiness_rollup(ledger, {"status": "ok", "rows": []})["reason"] == "decision_slice_empty"
    assert module.trade_grade_data_readiness_rollup(ledger, {})["reason"] == "tier_weighted_resolution_not_ok"

    assert module.AUTHORITY_BOUNDARY["paper_or_live_execution_allowed"] is False
    assert module.AUTHORITY_BOUNDARY["owner_approval_inferred"] is False
    print("ok trade grade os readiness rollup acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
