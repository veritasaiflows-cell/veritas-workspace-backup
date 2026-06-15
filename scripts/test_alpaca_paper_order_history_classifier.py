#!/usr/bin/env python3
"""Acceptance tests for alpaca_paper_order_history_classifier.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "alpaca_paper_order_history_classifier.py"
spec = importlib.util.spec_from_file_location("alpaca_paper_order_history_classifier", SCRIPT)
assert spec and spec.loader
classifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classifier)


def test_authority_boundary_get_only() -> None:
    boundary = classifier.authority_boundary()
    assert boundary["review_only"] is True
    assert boundary["paper_only"] is True
    assert boundary["allowed_methods"] == ["GET"]
    for key in (
        "paper_submit_allowed",
        "paper_cancel_allowed",
        "paper_sell_allowed",
        "paper_replace_allowed",
        "close_position_or_liquidation_allowed",
        "live_endpoint_allowed",
        "live_trade_or_account_action_allowed",
        "money_movement_allowed",
        "owner_approval_inferred",
        "portfolio_or_canon_mutation_allowed",
    ):
        assert boundary[key] is False


def test_exact_order_history_match_classifies_fill() -> None:
    source = {
        "source_path": "tmp/alpaca-paper-readiness/paper-execution-result.test.json",
        "generated_at_utc": "2026-06-11T18:17:32Z",
        "symbol": "VRT",
        "side": "buy",
        "paper_order_id_hash": None,
        "request": {
            "order": {
                "symbol": "VRT",
                "side": "buy",
                "type": "limit",
                "time_in_force": "day",
                "limit_price": 288.03,
                "notional": 5000.0,
            }
        },
    }
    orders = [
        {
            "id": "broker-id-redacted-in-output",
            "symbol": "VRT",
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": "288.03",
            "notional": "5000",
            "status": "filled",
            "submitted_at": "2026-06-11T18:17:35Z",
            "filled_qty": "17.36",
            "filled_avg_price": "288.02",
        }
    ]
    result = classifier.classify_source(source, orders, [])
    assert result["classification"] == "filled"
    assert result["match_status"] == "matched"
    assert result["order_history"]["broker_order_id_hash"]
    assert "id" not in result["order_history"]


def test_unmatched_buy_with_position_is_position_observed() -> None:
    source = {
        "source_path": "tmp/alpaca-paper-readiness/paper-execution-result.goog.json",
        "generated_at_utc": "2026-06-09T18:15:01Z",
        "symbol": "GOOG",
        "side": "buy",
        "request": {},
    }
    result = classifier.classify_source(source, [], [{"symbol": "GOOG", "qty": "2", "avg_entry_price": "359.94"}])
    assert result["classification"] == "filled_position_observed_unmatched_order_history"
    assert result["position_cross_check"]["position_observed"] is True


def test_payload_warning_for_unresolved_but_not_error() -> None:
    payload = classifier.build_payload(
        [
            {
                "source_path": "tmp/alpaca-paper-readiness/paper-execution-result.vrt.json",
                "generated_at_utc": "2026-06-11T18:17:32Z",
                "symbol": "VRT",
                "side": "buy",
            }
        ],
        [],
        [],
    )
    assert payload["status"] == "warning"
    assert payload["validation"]["status"] == "warning"
    assert "unresolved_submitted_paper_orders_present" in payload["validation"]["warnings"]


if __name__ == "__main__":
    test_authority_boundary_get_only()
    test_exact_order_history_match_classifies_fill()
    test_unmatched_buy_with_position_is_position_observed()
    test_payload_warning_for_unresolved_but_not_error()
    print("alpaca_paper_order_history_classifier_tests_passed")
