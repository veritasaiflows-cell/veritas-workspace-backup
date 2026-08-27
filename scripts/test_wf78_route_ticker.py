#!/usr/bin/env python3
"""Focused regressions for WF78 single-ticker route-readiness packets."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf78_route_ticker.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf78_route_ticker", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.AUTO_ROUTER = module.TMP / "wf78-auto-tier-routing.json"
    module.STALE_TICKERS = module.TMP / "finance-intelligence-state-stale-tickers.json"
    module.TICKER_CARD_SUMMARY = module.TMP / "ticker-card-refresh-gate-card-build-summary.json"
    module.WF85_CARDS = module.TMP / "trade-grade-decision-cards.json"
    module.TIER_A_PACKET = module.TMP / "wf78-tier-a-final-promotion-packet.json"
    module.TIER_B_REPAIR = module.TMP / "wf78-tier-b-evidence-repair.json"

    write_json(
        module.AUTO_ROUTER,
        {
            "validation": {"status": "ok"},
            "rows": [
                {
                    "ticker": "ANET",
                    "name": "Arista Networks",
                    "sector": "Technology",
                    "auto_tier": "Tier A",
                    "auto_state": "A-WATCH",
                    "lane_tier": "Tier A",
                    "review_lane": "equity_depth",
                    "route_priority": 91,
                }
            ],
        },
    )
    write_json(module.STALE_TICKERS, {"stale_ticker_cards": []})
    write_json(module.TICKER_CARD_SUMMARY, {"cards": [{"ticker": "ANET", "missing_or_stale_count": 0}]})
    write_json(
        module.WF85_CARDS,
        {
            "cards": [
                {
                    "ticker": "ANET",
                    "decision_state": "monitor_only",
                    "entry_band": {"band_status": "IN_BAND", "entry_band_low": 151.34, "entry_band_high": 162.87},
                    "current_price": {
                        "latest_known_price": 159.99,
                        "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review",
                    },
                    "authority_boundary": {
                        "capital_deployment_approved": False,
                        "trade_or_execution_approved": False,
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "money_movement_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ]
        },
    )
    write_json(module.TIER_A_PACKET, {"deprecation_status": {"deprecated_for_authority": True}})
    write_json(module.TIER_B_REPAIR, {"rows": []})
    write_json(
        module.ticker_card_path("ANET"),
        {
            "ticker": "ANET",
            "universe_metadata": {"name": "Arista Networks", "sector": "Technology"},
            "recommendation_support": {"posture": "monitor_only"},
            "latest_known_price": 159.99,
            "price_band_stop": {
                "band_status": "IN_BAND",
                "entry_band_low": 151.34,
                "entry_band_high": 162.87,
                "stop_or_invalidation": 141.10,
                "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review",
            },
            "missing_or_stale_evidence": [],
        },
    )


def test_route_readiness_separates_in_band_from_trade_readiness() -> None:
    module = load_module()
    readiness = module.route_readiness(
        {"auto_tier": "Tier A", "auto_state": "A-WATCH"},
        {
            "decision_state": "monitor_only",
            "entry_band": {"band_status": "IN_BAND"},
            "current_price": {"quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"},
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "money_movement_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        {},
    )

    assert readiness["routing_tier"] == "Tier A"
    assert readiness["routing_state"] == "A-WATCH"
    assert readiness["timing_state"] == "in_band_review_only_quote"
    assert readiness["decision_state"] == "monitor_only"
    assert readiness["trade_readiness_state"] == "not_trade_ready_in_band_monitor_only"
    assert readiness["authority_state"] == "review_only_no_capital_or_execution_authority"
    assert readiness["paper_or_live_execution_allowed"] is False
    assert "in-band review monitor" in readiness["next_route_action"]


def test_review_ready_still_requires_owner_gate() -> None:
    module = load_module()
    readiness = module.route_readiness(
        {"auto_tier": "Tier A", "auto_state": "A-READY"},
        {
            "decision_state": "review_ready",
            "entry_band": {"band_status": "IN_BAND"},
            "current_price": {"quote_freshness_status": "fresh"},
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "money_movement_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        {},
    )

    assert readiness["timing_state"] == "in_band_fresh_review"
    assert readiness["trade_readiness_state"] == "approval_card_candidate_owner_gated"
    assert readiness["requires_exact_owner_approval_before_capital_or_execution"] is True
    assert readiness["capital_deployment_approved"] is False


def test_authority_flag_blocks_trade_readiness() -> None:
    module = load_module()
    readiness = module.route_readiness(
        {"auto_tier": "Tier A", "auto_state": "A-READY"},
        {
            "decision_state": "review_ready",
            "entry_band": {"band_status": "IN_BAND"},
            "current_price": {"quote_freshness_status": "fresh"},
            "authority_boundary": {
                "capital_deployment_approved": True,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "money_movement_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        {},
    )

    assert readiness["authority_state"] == "blocked_authority_flag_true"
    assert readiness["trade_readiness_state"] == "blocked_authority_conflict"


def test_build_packet_contains_route_readiness_surface() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet("ANET")
        readiness = packet["route_readiness"]

        assert packet["status"] == "ok"
        assert packet["source_artifacts"]["wf85_decision_cards"] == "tmp/trade-grade-decision-cards.json"
        assert readiness["routing_tier"] == "Tier A"
        assert readiness["routing_state"] == "A-WATCH"
        assert readiness["timing_state"] == "in_band_review_only_quote"
        assert readiness["decision_state"] == "monitor_only"
        assert readiness["trade_readiness_state"] == "not_trade_ready_in_band_monitor_only"
        assert readiness["authority_state"] == "review_only_no_capital_or_execution_authority"
        assert packet["decision"]["next_safe_action"] == readiness["next_route_action"]
        assert packet["decision"]["paper_or_live_execution_allowed"] is False


if __name__ == "__main__":
    test_route_readiness_separates_in_band_from_trade_readiness()
    test_review_ready_still_requires_owner_gate()
    test_authority_flag_blocks_trade_readiness()
    test_build_packet_contains_route_readiness_surface()
    print("wf78_route_ticker tests passed")
