#!/usr/bin/env python3
"""Focused regressions for WF85 decision-card source-open classification."""
from __future__ import annotations

import trade_grade_decision_cards as cards


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_structural_hold_decision_states_remain_non_actionable(errors: list[str]) -> None:
    source_gate = {"source_open_status": "verified", "missing_or_stale_families": []}
    freshness = {"status": "fresh", "blockers": []}
    membership = {
        "production_answer_path_member": False,
        "thin_monitor_row": False,
        # Preserve the current legacy flag and prove downstream decision gates
        # still prevent structural Tier C holds from becoming actionable.
        "decision_grade_eligible": True,
    }
    cases = [
        ("RTX", "blocked_missing_freshness", "ABOVE_BAND", "defer_until_veto_clears", "no_chase"),
        ("SMCI", "blocked_missing_freshness", "ABOVE_BAND", "in_band_review_hold", "no_chase"),
        ("TMUS", "below_stop_or_invalidation", "BELOW_STOP", "reject_currently", "below_stop_or_invalidation"),
        ("VMC", "blocked_missing_freshness", "BELOW_BAND", "monitor_only", "monitor_only"),
        ("WMB", "blocked_missing_freshness", "BELOW_BAND", "monitor_only", "monitor_only"),
    ]
    structural_cards: list[dict[str, object]] = []
    for ticker, primary_state, band_status, gate_verdict, expected_state in cases:
        current = {
            "ticker": ticker,
            "auto_tier": "Tier C",
            "auto_state": "C-CANDIDATE-HOLD",
            "primary_state": primary_state,
            "band_status": band_status,
            "entry_band_low": 10,
            "entry_band_high": 12,
            "stop_or_invalidation": 9,
            "gate_verdict": gate_verdict,
        }
        decision_state, blockers = cards.classify_decision_state(
            current,
            source_gate,
            freshness,
            membership,
        )
        expect(
            decision_state == expected_state,
            f"{ticker} structural hold should remain {expected_state}, observed {decision_state}",
            errors,
        )
        structural_cards.append({
            **current,
            "decision_state": decision_state,
            "decision_state_reason": blockers,
            "entry_band": {"band_status": band_status},
            "source_freshness": {"quote_freshness_status": "intraday_fresh"},
        })

    approval_gate = cards.build_approval_gate(
        structural_cards,
        {},
        {
            "generated_at_utc": cards.utc_now(),
            "status": "ok",
            "ready_for_paper_submit_cancel": True,
        },
    )
    expect(
        approval_gate["summary"]["review_ready_count"] == 0,
        "structural Tier C holds must not become review-ready",
        errors,
    )
    expect(
        approval_gate["summary"]["approval_card_draft_count"] == 0,
        "structural Tier C holds must not produce approval-card drafts",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    test_structural_hold_decision_states_remain_non_actionable(errors)
    original_load_json = cards.load_json
    try:
        verified = cards.source_status_for(
            "TEST",
            [
                {
                    "source_use": "entry_stop_reference",
                    "path": "tmp/band-proposals.json",
                    "status": "current",
                    "validation_status": "ok",
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            verified["source_open_status"] == "verified",
            "SQL-first current/ok source rows should verify source-open instead of blocking",
            errors,
        )

        current_but_invalid = cards.source_status_for(
            "TEST",
            [
                {
                    "source_use": "entry_stop_reference",
                    "path": "tmp/band-proposals.json",
                    "status": "current",
                    "validation_status": "blocked",
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            current_but_invalid["source_open_status"] == "blocked",
            "current source rows with blocked validation must stay blocked",
            errors,
        )

        promoted_state, promoted_blockers = cards.classify_decision_state(
            {
                "ticker": "TEST",
                "primary_state": "blocked_missing_freshness",
                "band_status": "IN_BAND",
                "entry_band_low": 10,
                "entry_band_high": 12,
                "stop_or_invalidation": 9,
                "gate_verdict": "promote_for_owner_review",
            },
            {"source_open_status": "verified", "missing_or_stale_families": []},
            {"status": "fresh", "blockers": []},
            {"thin_monitor_row": False},
        )
        expect(
            promoted_state == "review_ready" and not promoted_blockers,
            "promote_for_owner_review should become review_ready after source, freshness, and band gates clear",
            errors,
        )

        promoted_no_chase_state, promoted_no_chase_blockers = cards.classify_decision_state(
            {
                "ticker": "TEST",
                "primary_state": "blocked_missing_freshness",
                "band_status": "ABOVE_BAND",
                "entry_band_low": 10,
                "entry_band_high": 12,
                "stop_or_invalidation": 9,
                "gate_verdict": "promote_for_owner_review",
            },
            {"source_open_status": "verified", "missing_or_stale_families": []},
            {"status": "fresh", "blockers": []},
            {"thin_monitor_row": False},
        )
        expect(
            promoted_no_chase_state == "no_chase"
            and "band_status=ABOVE_BAND" in promoted_no_chase_blockers,
            "promote_for_owner_review must not override no-chase band status",
            errors,
        )

        cards.load_json = lambda path: {  # type: ignore[assignment]
            "status": "warning",
            "summary": {
                "target_count": 2,
                "ok_count": 2,
                "error_count": 0,
                "cached_overlay_count": 2,
            },
            "validation": {"status": "ok"},
        }
        accepted = cards.source_status_for(
            "TEST",
            [
                {
                    "source_use": "price_technical_current",
                    "path": "tmp/post-close-final-quote-ledger.json",
                    "status": "warning",
                    "validation_status": "ok",
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            accepted["source_open_status"] == "verified",
            "safe post-close cached-overlay warning should be source-open verified for non-executing review",
            errors,
        )
        expect(
            accepted["accepted_warning_sources"]
            and accepted["accepted_warning_sources"][0]["acceptance"] == "warning_accepted_for_non_executing_review_cached_overlay",
            "accepted warning source should be explicitly visible",
            errors,
        )
        expect(
            "execution freshness" in accepted["approval_execution_freshness_guard"],
            "accepted warning source must keep execution-freshness boundary visible",
            errors,
        )

        cards.load_json = lambda path: {  # type: ignore[assignment]
            "status": "warning",
            "summary": {
                "target_count": 2,
                "ok_count": 2,
                "error_count": 0,
                "cached_overlay_count": 1,
                "ok_tickers": ["BRK.B", "VRT"],
            },
            "validation": {"status": "ok"},
        }
        accepted_ticker_ok = cards.source_status_for(
            "BRK.B",
            [
                {
                    "source_use": "price_technical_current",
                    "path": "tmp/post-close-final-quote-ledger.json",
                    "status": "warning",
                    "validation_status": "ok",
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            accepted_ticker_ok["source_open_status"] == "verified",
            "warning quote source with clean validation and ticker in ok_tickers should verify review-only source-open",
            errors,
        )
        expect(
            accepted_ticker_ok["accepted_warning_sources"]
            and accepted_ticker_ok["accepted_warning_sources"][0]["acceptance"] == "warning_accepted_for_non_executing_review_ticker_ok",
            "ticker-level accepted warning source should be explicitly visible",
            errors,
        )

        cards.load_json = lambda path: {  # type: ignore[assignment]
            "status": "warning",
            "summary": {
                "target_count": 2,
                "ok_count": 1,
                "error_count": 1,
                "cached_overlay_count": 1,
            },
            "validation": {"status": "ok"},
        }
        blocked = cards.source_status_for(
            "TEST",
            [
                {
                    "source_use": "price_technical_current",
                    "path": "tmp/post-close-final-quote-ledger.json",
                    "status": "warning",
                    "validation_status": "ok",
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            blocked["source_open_status"] == "blocked",
            "warning quote source with errors or incomplete cached overlay must stay blocked",
            errors,
        )

        cards.load_json = lambda path: {  # type: ignore[assignment]
            "status": "ok",
            "records": [
                {"ticker": "VRT", "close": 329.77, "data_date": "2026-06-30"},
                {"ticker": "XLB", "close": 50.94, "data_date": "2026-06-30"},
            ],
        }
        technical_refresh_accepted = cards.source_status_for(
            "VRT",
            [
                {
                    "source_use": "price_technical_current",
                    "path": "tmp/technical-refresh.json",
                    "status": "ok",
                    "validation_status": None,
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            technical_refresh_accepted["source_open_status"] == "verified",
            "technical-refresh artifact status ok with a ticker row should verify review-only source-open",
            errors,
        )
        expect(
            technical_refresh_accepted["accepted_status_only_sources"]
            and technical_refresh_accepted["accepted_status_only_sources"][0]["acceptance"]
            == "artifact_status_ok_accepted_for_non_executing_review_ticker_row",
            "accepted technical-refresh status-only source should be explicitly visible",
            errors,
        )

        cards.load_json = lambda path: {  # type: ignore[assignment]
            "status": "ok",
            "records": [
                {"ticker": "XLB", "close": 50.94, "data_date": "2026-06-30"},
            ],
        }
        technical_refresh_missing_ticker = cards.source_status_for(
            "VRT",
            [
                {
                    "source_use": "price_technical_current",
                    "path": "tmp/technical-refresh.json",
                    "status": "ok",
                    "validation_status": None,
                }
            ],
            [],
            {"thin_monitor_row": False},
        )
        expect(
            technical_refresh_missing_ticker["source_open_status"] == "blocked",
            "technical-refresh artifact must stay blocked when the ticker row is absent",
            errors,
        )
    finally:
        cards.load_json = original_load_json

    if errors:
        print("trade_grade_decision_cards_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("trade_grade_decision_cards_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
