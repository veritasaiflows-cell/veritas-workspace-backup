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
    finally:
        resolver.card = original_card

    if errors:
        print("wf78_tier_weighted_freshness_resolver_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf78_tier_weighted_freshness_resolver_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
