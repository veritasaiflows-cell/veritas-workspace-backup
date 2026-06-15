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

    assert module.AUTHORITY_BOUNDARY["paper_or_live_execution_allowed"] is False
    assert module.AUTHORITY_BOUNDARY["owner_approval_inferred"] is False
    print("ok trade grade os readiness rollup acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
