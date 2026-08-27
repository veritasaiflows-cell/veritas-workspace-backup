#!/usr/bin/env python3
"""Focused tests for band hygiene classification."""
from __future__ import annotations

import unittest

import band_hygiene_freshness_controller as hygiene


class BandHygieneFreshnessControllerTests(unittest.TestCase):
    def test_monitor_only_band_review_does_not_become_exception(self) -> None:
        state, blockers, owner_review = hygiene.row_state(
            "BRK.B",
            {
                "ticker": "BRK.B",
                "needs_review": True,
                "canonical_apply_eligible": False,
                "blocking_review": False,
                "entry_policy": "band_defined",
            },
            {"below_stop": False},
            {"freshness_status": "fresh", "price": 496.91, "age_seconds": 1},
            {},
            {"reason": "canonical_apply_eligible is not true"},
        )
        self.assertEqual(state, "monitor_only_review")
        self.assertIn("monitor_only_band_review", blockers)
        self.assertFalse(owner_review)

    def test_legacy_repair_workflow_does_not_force_reclaim_when_monitor_only(self) -> None:
        review = hygiene.entry_policy_review_candidate(
            "BRK.B",
            {
                "ticker": "BRK.B",
                "entry_policy": "band_defined",
                "coverage_lane": "execution",
                "workflow_state": "REPAIR",
                "band_status": "NEAR_BAND",
                "current_band_low": 489.78,
                "current_band_high": 498.19,
                "current_stop": 483.05,
                "reasons": ["workflow state is not decision-grade for band application"],
            },
            {"in_entry_band": True, "below_stop": False, "ma_posture": "above all MAs"},
            "monitor_only_review",
            ["monitor_only_band_review"],
        )
        self.assertEqual(review["hard_blockers"], [])
        self.assertEqual(review["recommended_entry_policy_action"], "main_review_required")


if __name__ == "__main__":
    unittest.main()
