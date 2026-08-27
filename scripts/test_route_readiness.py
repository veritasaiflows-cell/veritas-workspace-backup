from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import route_readiness as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_wf84_review_ready_in_band_owner_gated(errors: list[str]) -> None:
    row = {
        "auto_tier": "Tier A",
        "auto_state": "A-WATCH",
        "band_status": "IN_BAND",
        "quote_freshness_status": "fresh",
        "capital_deployment_approved": 0,
        "trade_or_execution_approved": 0,
        "paper_or_live_execution_allowed": 0,
        "owner_approval_inferred": 0,
    }
    readiness = mod.route_readiness_from_wf84_row(row, "review_ready")
    expect(readiness["timing_state"] == "in_band_fresh_review", "fresh in-band timing", errors)
    expect(readiness["trade_readiness_state"] == "approval_card_candidate_owner_gated", "review-ready remains owner-gated", errors)
    expect(readiness["authority_state"] == "review_only_no_capital_or_execution_authority", "authority remains review-only", errors)
    expect(readiness["paper_or_live_execution_allowed"] is False, "paper/live flag false", errors)


def test_missing_band_refresh_is_explicit(errors: list[str]) -> None:
    readiness = mod.build_route_readiness(
        routing_tier="Tier C",
        routing_state="C-MONITOR",
        decision_state="monitor_only",
        band_status="missing_required_refresh",
        quote_freshness_status="fresh",
        authority={},
    )
    expect(readiness["timing_state"] == "band_status_missing_required_refresh", "missing-band timing must be visible", errors)
    expect("Refresh band/stop context" in readiness["next_route_action"], "missing-band next action should route refresh", errors)
    expect(readiness["trade_readiness_state"] == "not_trade_ready_monitor_only", "missing-band monitor is not trade ready", errors)


def test_route_context_uses_card_fallback(errors: list[str]) -> None:
    readiness = mod.route_readiness_from_route_context(
        {"auto_tier": "Tier A", "auto_state": "A-WATCH"},
        {"decision_state": "monitor_only", "authority_boundary": {}},
        {
            "price_band_stop": {
                "band_status": "IN_BAND",
                "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review",
            }
        },
    )
    expect(readiness["timing_state"] == "in_band_review_only_quote", "card fallback should preserve review-only quote timing", errors)
    expect(readiness["trade_readiness_state"] == "not_trade_ready_in_band_monitor_only", "in-band monitor remains not trade ready", errors)


def test_monitor_grade_in_band_is_not_trade_ready(errors: list[str]) -> None:
    readiness = mod.build_route_readiness(
        routing_tier="Tier C",
        routing_state="C-MONITOR",
        decision_state="monitor_only",
        band_status="IN_BAND",
        quote_freshness_status="tier_c_monitor_grade_reference",
        authority={},
    )
    expect(readiness["timing_state"] == "in_band_monitor_grade", "Tier C monitor overlay must be labeled monitor-grade", errors)
    expect(readiness["trade_readiness_state"] == "not_trade_ready_monitor_grade", "monitor-grade in-band must not become trade ready", errors)
    expect("triage only" in readiness["next_route_action"], "monitor-grade action should stay triage-only", errors)


def test_authority_conflict_blocks_trade_readiness(errors: list[str]) -> None:
    readiness = mod.build_route_readiness(
        routing_tier="Tier A",
        routing_state="A-READY",
        decision_state="review_ready",
        band_status="IN_BAND",
        quote_freshness_status="fresh",
        authority={"capital_deployment_approved": True},
    )
    expect(readiness["authority_state"] == "blocked_authority_flag_true", "authority conflict should be explicit", errors)
    expect(readiness["trade_readiness_state"] == "blocked_authority_conflict", "authority conflict must block trade readiness", errors)


def main() -> int:
    errors: list[str] = []
    test_wf84_review_ready_in_band_owner_gated(errors)
    test_missing_band_refresh_is_explicit(errors)
    test_route_context_uses_card_fallback(errors)
    test_monitor_grade_in_band_is_not_trade_ready(errors)
    test_authority_conflict_blocks_trade_readiness(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("route_readiness tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
