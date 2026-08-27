#!/usr/bin/env python3
"""Focused tests for band proposal classification."""
from __future__ import annotations

import unittest

import band_refresh


class BandRefreshTests(unittest.TestCase):
    def test_non_applyable_wait_state_is_monitor_only_not_blocking(self) -> None:
        proposal = band_refresh.BandProposal(
            ticker="BRK.B",
            coverage_lane="execution",
            workflow_state="REPAIR",
            entry_policy="band_defined",
            current_band_low=489.78,
            current_band_high=498.19,
            current_stop=483.05,
            band_last_set="2026-05-13",
            days_old=48,
            trading_days_old=34,
            close=497.04,
            ma20=488.71,
            ma50=481.33,
            ma200=490.12,
            atr14=6.86,
            canonical_apply_eligible=False,
            needs_review=True,
            reasons=["workflow state is not decision-grade for band application"],
        )
        self.assertFalse(band_refresh.is_blocking_review(proposal))


if __name__ == "__main__":
    unittest.main()
