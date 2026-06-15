#!/usr/bin/env python3
"""Targeted tests for WF78 deployment-readiness human review grouping."""
from __future__ import annotations

import wf78_deployment_readiness_human_review as human_review


def test_classify_band_context_groups() -> None:
    assert human_review.classify_band_context({"band_status": "IN_BAND"}) == "IN_BAND"
    assert human_review.classify_band_context({"band_status": "BELOW_BAND"}) == "BELOW_BAND"
    assert human_review.classify_band_context({"band_status": "BELOW_STOP"}) == "BELOW_STOP"
    assert human_review.classify_band_context({"band_status": "ABOVE_BAND"}) == "ABOVE_BAND_NO_CHASE"
    assert human_review.classify_band_context({"current_band_context": {"band_status": "ABOVE_BAND_WAIT"}}) == "ABOVE_BAND_NO_CHASE"
    assert human_review.classify_band_context({"band_status": ""}) == "UNKNOWN_BLOCKED"


def test_normalized_row_marks_above_band_no_chase_and_preserves_authority() -> None:
    row = human_review.normalized_review_row(
        {
            "ticker": "JPM",
            "band_status": "ABOVE_BAND",
            "latest_known_price": 320.72,
            "entry_band_low": 301.50,
            "entry_band_high": 307.78,
            "stop_or_invalidation": 293.93,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        {},
    )
    assert row["band_context_group"] == "ABOVE_BAND_NO_CHASE"
    assert row["no_chase"] is True
    assert row["review_only"] is True
    assert row["capital_deployment_approved"] is False
    assert row["trade_or_execution_approved"] is False
    assert row["paper_or_live_execution_allowed"] is False
    assert row["owner_approval_inferred"] is False
    assert human_review.authority_clean(row)


def test_build_report_groups_all_packet_rows_and_keeps_below_stop_separate() -> None:
    report = human_review.build_report()
    assert report["validation"]["status"] == "ok"
    assert report["summary"]["row_count"] == 24
    groups = report["groups"]
    assert [row["ticker"] for row in groups["IN_BAND"]] == ["BKNG", "CVX", "PH", "RTX", "XLE"]
    assert [row["ticker"] for row in groups["BELOW_BAND"]] == ["ECL", "VMC", "WMB"]
    assert [row["ticker"] for row in groups["BELOW_STOP"]] == ["AMZN", "CME", "LNG", "META", "NFLX", "PLTR", "TMUS"]
    assert [row["ticker"] for row in groups["ABOVE_BAND_NO_CHASE"]] == [
        "AMD",
        "CAT",
        "GE",
        "ITA",
        "LLY",
        "PAVE",
        "VAW",
        "XLB",
        "XLI",
    ]
    assert groups["UNKNOWN_BLOCKED"] == []
    assert all(row["paper_or_live_execution_allowed"] is False for row in report["rows"])
    assert human_review.authority_clean(report)


def test_authority_validation_blocks_widened_flags() -> None:
    bad = dict(human_review.AUTHORITY_FLAGS)
    bad["trade_or_execution_approved"] = True
    assert not human_review.authority_clean(bad)
    report = {
        "authority_flags": dict(human_review.AUTHORITY_FLAGS),
        "rows": [{"ticker": "BAD", "band_context_group": "IN_BAND", **bad}],
        "groups": {"IN_BAND": [{"ticker": "BAD"}], "BELOW_BAND": [], "BELOW_STOP": [], "ABOVE_BAND_NO_CHASE": [], "UNKNOWN_BLOCKED": []},
    }
    errors = human_review.validate_report(report)
    assert any("row authority widened" in error for error in errors)


def test_markdown_contains_required_sections_and_guardrail() -> None:
    report = human_review.build_report()
    md = human_review.render_markdown(report)
    assert "### In Band (5)" in md
    assert "### Below Band (3)" in md
    assert "### Below Stop (7)" in md
    assert "### Above Band / No Chase (9)" in md
    assert "No capital deployment" in md
    assert "owner approval inference" in md


def main() -> int:
    test_classify_band_context_groups()
    test_normalized_row_marks_above_band_no_chase_and_preserves_authority()
    test_build_report_groups_all_packet_rows_and_keeps_below_stop_separate()
    test_authority_validation_blocks_widened_flags()
    test_markdown_contains_required_sections_and_guardrail()
    print("wf78_deployment_readiness_human_review targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
