#!/usr/bin/env python3
from __future__ import annotations

import wf78_source_open_repair_executor as executor


def test_ledger_stale_prefix_is_normalized() -> None:
    row = {"stale_families": ["stale:price_band_stop", "stale:technical_posture"]}
    assert executor.stale_families(row) == ["price_band_stop", "technical_posture"]
    assert executor.matched_families(row) == {"price_band_stop"}


def test_bare_card_gap_families_still_match() -> None:
    row = {"stale_families": ["deployment_readiness_surface"]}
    assert executor.matched_families(row) == {"deployment_readiness_surface"}


def test_non_target_families_do_not_match_after_normalization() -> None:
    row = {"stale_families": ["stale:deployment_readiness", "stale:recommendation_support"]}
    assert executor.matched_families(row) == set()


if __name__ == "__main__":
    test_ledger_stale_prefix_is_normalized()
    test_bare_card_gap_families_still_match()
    test_non_target_families_do_not_match_after_normalization()
    print("ok wf78 source-open repair executor family normalization")
