#!/usr/bin/env python3
"""Focused regressions for WF78 ticker freshness ledger precedence."""
from __future__ import annotations

import wf78_ticker_freshness_ledger as ledger


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def overall_for(families: list[str], tier: str, repair_disposition: str | None = None) -> str:
    states = {ledger.family_state(fam, tier, repair_disposition) for fam in families}
    return next((state for state in ledger.STATE_SEVERITY if state in states), "stale_review_required")


def main() -> int:
    errors: list[str] = []

    expect(
        overall_for(["stale:technical_posture", "stale:price_band_stop"], "Tier B") == "stale_source_open",
        "a refreshable family must not outvote a source-open family on Tier B",
        errors,
    )
    expect(
        overall_for(["stale:technical_posture", "stale:price_band_stop"], "Tier C") == "blocked_structural",
        "Tier C thin-monitor rows must route to structural hold, not card refresh",
        errors,
    )
    expect(
        overall_for(["stale:technical_posture"], "Tier B") == "stale_refreshable",
        "a genuinely refreshable-only row must still route to the refresh gate",
        errors,
    )
    expect(
        overall_for(["stale:technical_posture", "stale:catalyst_earnings_state"], "Tier B") == "stale_review_required",
        "an unclassified family must outrank a refreshable family",
        errors,
    )
    expect(
        overall_for(
            ["stale:technical_posture", "stale:price_band_stop"],
            "Tier B",
            "repaired_from_owner_source",
        )
        == "source_open_repaired_rerun_needed",
        "a repaired source-open row must route to rerun rather than refresh",
        errors,
    )
    expect(
        overall_for(
            ["stale:price_band_stop", "stale:deployment_readiness"],
            "Tier B",
            "repaired_from_owner_source",
        )
        == "source_open_repaired_rerun_needed",
        "rerun state applies when every source-open family is repaired",
        errors,
    )

    expect(
        ledger.STATE_SEVERITY.index("stale_source_open") < ledger.STATE_SEVERITY.index("stale_refreshable"),
        "severity order must rank source-open work above refreshable work",
        errors,
    )

    for message in errors:
        print(f"FAIL {message}")
    if errors:
        return 1
    print("ok wf78 ticker freshness ledger precedence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
