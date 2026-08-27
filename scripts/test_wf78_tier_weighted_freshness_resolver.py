#!/usr/bin/env python3
"""Focused regressions for WF78 tier-weighted freshness resolution."""
from __future__ import annotations

import wf78_tier_weighted_freshness_resolver as resolver


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    original_card = resolver.card
    original_load_dict = resolver.load_dict
    original_is_current_card = resolver.is_current_card
    try:
        resolver.card = lambda symbol: {  # type: ignore[assignment]
            "technical_posture": {"data_date": "2026-06-10", "latest_close": 123.45},
            "price_band_stop": {"latest_known_price": 123.45},
        }
        state, _, blockers = resolver.classify_tier_ab(
            "TEST",
            "Tier A",
            {"stale_families": ["fresh_price_quote"], "overall_freshness_state": "stale_refreshable"},
            {"repair_disposition": "needs_deployment_readiness_surface"},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
        )
        expect(
            state == "resolved_to_current_technical_review",
            "fresh_price_quote-only rows should resolve from current technical review context before deployment packaging repair",
            errors,
        )
        expect(blockers == [], "current technical review context should clear fresh_price_quote blocker", errors)

        mixed_state, _, mixed_blockers = resolver.classify_tier_ab(
            "MIXED",
            "Tier A",
            {
                "stale_families": ["deployment_readiness_surface", "fresh_price_quote"],
                "overall_freshness_state": "stale_refreshable",
            },
            {"repair_disposition": "needs_deployment_readiness_surface"},
            {},
            {},
            {},
            {},
            {},
            {},
            {},
        )
        expect(
            mixed_state == "blocked_deployment_readiness_surface_required",
            "mixed deployment-readiness debt should remain a context blocker",
            errors,
        )
        expect(
            mixed_blockers == ["deployment_readiness_surface"],
            "mixed deployment-readiness blocker should stay explicit",
            errors,
        )

        def fake_load_dict(path):  # type: ignore[no-untyped-def]
            if path == resolver.LEDGER:
                return {
                    "summary": {"ticker_count": 3},
                    "rows": [
                        {"ticker": "AAA", "overall_freshness_state": "fresh"},
                        {"ticker": "BBB", "overall_freshness_state": "fresh"},
                        {"ticker": "CCC", "overall_freshness_state": "fresh"},
                    ],
                }
            if path == resolver.AUTO_ROUTER:
                return {
                    "summary": {"active_ticker_count": 3},
                    "rows": [
                        {"ticker": "AAA", "auto_tier": "Tier C", "auto_state": "C-MONITOR"},
                        {"ticker": "BBB", "auto_tier": "Tier C", "auto_state": "C-MONITOR"},
                        {"ticker": "CCC", "auto_tier": "Tier C", "auto_state": "C-MONITOR"},
                    ],
                }
            if path == resolver.TIER_C_BAND_STATUS:
                return {"summary": {"tier_c_count": 3}, "rows": []}
            if path == resolver.REFRESH_GATE:
                return {"status": "ok", "validation": {"warnings": []}}
            return {"rows": []}

        resolver.load_dict = fake_load_dict  # type: ignore[assignment]
        resolver.is_current_card = lambda symbol, ledger_row: True  # type: ignore[assignment]
        dynamic_report = resolver.build()
        expect(dynamic_report["status"] == "ok", "dynamic active-scope report should validate", errors)
        expect(dynamic_report["summary"]["ticker_count"] == 3, "dynamic active-scope ticker count should be accepted", errors)
        expect(
            dynamic_report["summary"]["expected_active_scope_count"] == 3,
            "expected active scope should come from WF78 router summary",
            errors,
        )
    finally:
        resolver.card = original_card
        resolver.load_dict = original_load_dict  # type: ignore[assignment]
        resolver.is_current_card = original_is_current_card  # type: ignore[assignment]

    if errors:
        print("wf78_tier_weighted_freshness_resolver_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf78_tier_weighted_freshness_resolver_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
