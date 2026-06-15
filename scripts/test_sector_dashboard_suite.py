#!/usr/bin/env python3
"""Targeted tests for the WF53 sector dashboard suite renderer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sector_dashboard_suite as sds


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sample_board() -> dict:
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-10T22:00:00Z",
        "window": "post-close",
        "status": "degraded",
        "consumer_posture": "review_only",
        "status_question": "Where is sector leadership improving, where are we underexposed, and which names deserve promotion review?",
        "authority": {field: False for field in sds.AUTHORITY_FALSE_FIELDS},
        "market_data_as_of": "2026-05-08",
        "summary": {
            "improving_leadership_sectors": ["Technology"],
            "underexposed_sectors": ["Health Care"],
            "promotion_review_candidates": ["LLY", "NVDA"],
            "concentration_warnings": ["Direct Technology is at cap."],
        },
        "warnings": ["source trust review required"],
        "sectors": [
            {
                "ticker": "XLK",
                "sector": "Technology",
                "leadership_status": "improving_leadership",
                "above_50dma": True,
                "close": 180.0,
                "short_term_moving_averages": {
                    "sma_5": 178.0,
                    "sma_20": 170.0,
                    "price_vs_5dma_pct": 1.12,
                    "price_vs_20dma_pct": 5.88,
                    "sma_5_vs_20_pct": 4.71,
                    "signal": "short_term_confirmed",
                    "warning": "Short-term tape confirms; still subordinate to band and stop checks.",
                },
                "relative_strength_vs_spy": {"1d": 2.1, "5d": 4.2, "20d": 10.5},
                "sector_returns_pct": {"20d": 19.0},
                "portfolio_exposure": {"draft_weight_pct": 25, "status": "at_cap", "tickers": ["NVDA"]},
                "underexposed": False,
                "tracked_universe_candidates": [{"ticker": "NVDA"}],
                "promotion_review_status": [{"candidate": "NVDA", "owner_approval_granted": False, "watchlist_promotion_allowed": False}],
                "warnings": ["AI-power sleeve warning"],
                "owner_gated_next_review_action": "Review concentration first.",
            },
            {
                "ticker": "XLV",
                "sector": "Health Care",
                "leadership_status": "deteriorating",
                "above_50dma": False,
                "close": 90.0,
                "short_term_moving_averages": {
                    "sma_5": 92.0,
                    "sma_20": 95.0,
                    "price_vs_5dma_pct": -2.17,
                    "price_vs_20dma_pct": -5.26,
                    "sma_5_vs_20_pct": -3.16,
                    "signal": "short_term_repair_needed",
                    "warning": "5DMA is below 20DMA; short-term trend needs repair.",
                },
                "relative_strength_vs_spy": {"1d": -1.1, "5d": -3.2, "20d": -9.5},
                "sector_returns_pct": {"20d": -2.0},
                "portfolio_exposure": {"draft_weight_pct": 0, "status": "unrepresented", "tickers": []},
                "underexposed": True,
                "tracked_universe_candidates": [{"ticker": "LLY"}],
                "promotion_review_status": [{"candidate": "LLY", "owner_approval_granted": False, "watchlist_promotion_allowed": False}],
                "warnings": [],
                "owner_gated_next_review_action": "Prepare owner-gated review only.",
            },
        ],
    }


def test_build_tables(errors: list[str]) -> None:
    tables = sds.build_tables(sample_board())
    expect(len(tables["sectors"]) == 2, "sector table should include sample sectors", errors)
    expect("5/20 Signal" in tables["sectors"].columns, "sector table should include 5/20 signal column", errors)
    expect("5/20 Warning" in tables["exposure_pivot"].columns, "exposure pivot should carry 5/20 warning", errors)
    expect("Leadership" in tables["leadership_pivot"].columns, "leadership pivot should include Leadership column", errors)
    expect(set(tables["promotions"]["Candidate"]) == {"LLY", "NVDA"}, "promotion table should include both candidates", errors)


def test_write_outputs(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous_workspace = sds.WORKSPACE
        try:
            sds.WORKSPACE = root
            output = root / "tmp" / "sector-dashboard-suite.html"
            paths = sds.write_outputs(sample_board(), output, root / "tmp")
            html = output.read_text(encoding="utf-8")
            expect("WF53 Sector Dashboard Suite" in html, "HTML title should be present", errors)
            expect("Where is sector leadership improving" in html, "status question should be present", errors)
            expect("review_only" in html, "review-only authority badge should be present", errors)
            for key, rel_path in paths.items():
                expect((root / rel_path).exists(), f"output should exist for {key}", errors)
        finally:
            sds.WORKSPACE = previous_workspace


def main() -> int:
    errors: list[str] = []
    test_build_tables(errors)
    test_write_outputs(errors)
    if errors:
        print("sector_dashboard_suite_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("sector_dashboard_suite_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
