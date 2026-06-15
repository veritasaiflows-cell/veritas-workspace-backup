#!/usr/bin/env python3
"""Focused regressions for WF84/WF85 answer parity semantics."""
from __future__ import annotations

from full_intelligence_answer_parity import semantic_band_status
from trade_grade_full_answer_assembler import CANONICAL_DB, portfolio_fit_with_current_route, present, section_summary, technical_setup_data, wf84_context


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    aliases = {
        "ABOVE_BAND_WAIT": "ABOVE_BAND",
        "above band no chase": "ABOVE_BAND",
        "BELOW-BAND-REPAIR": "BELOW_BAND",
        "IN_BAND_REVIEW": "IN_BAND",
        "in band wait": "IN_BAND",
    }
    for raw, expected in aliases.items():
        expect(
            semantic_band_status(raw) == expected,
            f"band status alias {raw!r} should normalize to {expected!r}",
            errors,
        )
    expect(
        semantic_band_status("BELOW_STOP") == "BELOW_STOP",
        "unknown/non-aliased material states should remain explicit",
        errors,
    )
    expect(
        not present({"status": "source_open_required"}),
        "source_open_required placeholder should not count as substantive full-answer content",
        errors,
    )
    technical = technical_setup_data(
        {"technical_posture": {"latest_close": None, "ma20": None}},
        {"sections": {"technical_posture": {"raw_json": "{\"status\":\"missing_required_refresh\",\"repair_required\":true,\"source_path\":\"tmp/finance-data-coverage-current.json\"}"}}},
    )
    expect(technical.get("status") == "missing_required_refresh", "technical setup should fall back to WF84 repair state", errors)
    expect(technical.get("repair_required") is True, "technical setup repair state should stay explicit", errors)
    if CANONICAL_DB.exists():
        context = wf84_context("A")
        expect(context.get("status") in {"ok", "missing"}, "WF84 context lookup should not fail on drillback ordering", errors)
        if context.get("status") == "ok":
            expect(bool(context.get("sections")), "WF84 context should expose section rows when ticker exists", errors)
    fit = portfolio_fit_with_current_route(
        {
            "portfolio_fit_concentration": {
                "sector": "Infrastructure",
                "wf78_auto_tier": "Tier C",
                "wf78_auto_state": "C-MONITOR",
            }
        },
        {
            "auto_tier": "Tier A",
            "auto_state": "A-CHALLENGED",
            "decision_state": "blocked_missing_freshness",
        },
    )
    expect(fit.get("wf78_auto_tier") == "Tier A", "portfolio fit should expose current route tier", errors)
    expect(fit.get("current_route_tier") == "Tier A", "portfolio fit should label current route tier", errors)
    expect(fit.get("prior_card_wf78_auto_tier") == "Tier C", "portfolio fit should preserve prior card tier", errors)
    expect(fit.get("wf85_decision_state") == "blocked_missing_freshness", "portfolio fit should carry WF85 decision state", errors)
    fit_summary = section_summary({"raw": fit})
    expect("current route: Tier A" in fit_summary, "human portfolio-fit summary should surface current route tier", errors)
    expect("prior card: Tier C" in fit_summary, "human portfolio-fit summary should surface prior card tier", errors)
    if errors:
        print("full_intelligence_answer_parity_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("full_intelligence_answer_parity_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
