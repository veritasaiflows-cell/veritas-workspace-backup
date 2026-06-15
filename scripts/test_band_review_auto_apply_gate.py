#!/usr/bin/env python3
"""Regression tests for morning band review auto-apply handling."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import band_hygiene_freshness_controller as hygiene
import morning_paper_deployment_recommendation_builder as morning


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def case_age_zero_quote_is_fresh() -> list[str]:
    errors: list[str] = []
    snapshot = {"freshness_status": "fresh", "price": 123.45, "age_seconds": 0}
    expect(hygiene.clean_quote(snapshot), "hygiene clean_quote rejected age_seconds=0", errors)
    expect(morning.price_fresh_clean(snapshot), "morning price_fresh_clean rejected age_seconds=0", errors)
    return errors


def case_auto_applied_band_review_is_not_left_open() -> list[str]:
    errors: list[str] = []
    proposal = {
        "needs_review": True,
        "canonical_apply_eligible": True,
        "band_status": "IN_BAND",
        "entry_policy": "band_defined",
    }
    quote = {"freshness_status": "fresh", "price": 303.42, "age_seconds": 0}
    state, blockers, owner_review_required = hygiene.row_state(
        "VRT",
        proposal,
        {},
        quote,
        {"ticker": "VRT", "new_low": 265.76, "new_high": 318.4, "new_stop": 241.83},
        {},
    )
    expect(state == "applied_auto_maintenance", f"unexpected hygiene state after auto apply: {state}", errors)
    expect("post_apply_band_review_still_open" not in blockers, "post-apply blocker remained after auto apply", errors)
    expect(owner_review_required is False, "auto-applied clean band still required owner review", errors)

    status, card_blockers, _warnings = morning.classify_candidate(
        {
            "ticker": "VRT",
            "disposition": "owner_card_and_wf67_request_ready",
            "wf67_request_generation_status": "ok",
            "wf67_request_path": "tmp/example.json",
            "owner_card_path": "tmp/example-card.json",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "quote_repair_context": {"execution_freshness_approved": False},
            "quote_freshness_status": "current_market_day_quote_available_for_non_executing_review",
        },
        quote,
        {"chief_intelligence_verdict": "promote_for_owner_review"},
        {"auto_state": "A-READY"},
        {
            "ticker": "VRT",
            "auto_state": "A-READY",
            "band_status": "IN_BAND",
            "entry_band_low": 265.76,
            "entry_band_high": 318.4,
            "stop_or_invalidation": 241.83,
            "capital_deployment_approved": 0,
            "trade_or_execution_approved": 0,
            "paper_or_live_execution_allowed": 0,
            "owner_approval_inferred": 0,
        },
        {"tier_a_confidence_status": "ready"},
        {"needs_review": True, "blocking_review": True, "entry_policy": "band_defined"},
        {"state": state, "blockers": blockers, "auto_apply": {"applied": True}},
    )
    expect(status == "approval_card_clean_ready_for_randall_review", f"unexpected morning status: {status}", errors)
    expect("band_review_required" not in card_blockers, f"band review blocker remained: {card_blockers}", errors)
    expect("post_apply_band_review_still_open" not in card_blockers, f"post-apply blocker remained: {card_blockers}", errors)
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(case_age_zero_quote_is_fresh())
    errors.extend(case_auto_applied_band_review_is_not_left_open())
    if errors:
        print("band_review_auto_apply_gate_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("band_review_auto_apply_gate_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
