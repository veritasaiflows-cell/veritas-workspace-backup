#!/usr/bin/env python3
"""Focused tests for finance decision sync spine state classification."""
from __future__ import annotations

import unittest

import finance_decision_sync_spine as spine


class FinanceDecisionSyncSpineTests(unittest.TestCase):
    def test_in_band_review_hold_is_not_promotion_vetoed(self) -> None:
        self.assertEqual(
            spine.state_for_promotion_gate_verdict("in_band_review_hold"),
            "in_band_not_clean",
        )

    def test_wait_verdict_remains_promotion_vetoed(self) -> None:
        self.assertEqual(
            spine.state_for_promotion_gate_verdict("watch_for_reclaim_or_pullback"),
            "promotion_vetoed",
        )

    def test_promote_verdict_does_not_add_blocking_state(self) -> None:
        self.assertIsNone(
            spine.state_for_promotion_gate_verdict("promote_for_owner_review")
        )

    def test_current_band_status_used_when_suggested_band_not_applyable(self) -> None:
        context = spine.band_proposal_current_context({
            "ticker": "BRK.B",
            "canonical_apply_eligible": False,
            "current_band_low": 489.78,
            "current_band_high": 498.19,
            "current_stop": 483.05,
            "suggested_band_low": 478.96,
            "suggested_band_high": 491.62,
            "suggested_stop": 469.93,
            "close": 497.04,
            "band_status": "NEAR_BAND",
        })
        self.assertEqual(context["band_status"], "IN_BAND")
        self.assertEqual(context["entry_band_low"], 489.78)
        self.assertEqual(context["entry_band_high"], 498.19)

    def test_suggested_band_status_recomputed_when_applyable(self) -> None:
        context = spine.band_proposal_current_context({
            "ticker": "VRT",
            "canonical_apply_eligible": True,
            "suggested_band_low": 301.50,
            "suggested_band_high": 323.90,
            "suggested_stop": 285.00,
            "close": 334.82,
            "band_status": "NEAR_BAND",
        })
        self.assertEqual(context["band_status"], "ABOVE_BAND_WAIT")
        self.assertEqual(context["entry_band_low"], 301.50)
        self.assertEqual(context["entry_band_high"], 323.90)

    def test_above_band_rewrites_stale_in_band_gate(self) -> None:
        fields = spine.normalized_promotion_gate_fields(
            "in_band_review_hold",
            [],
            "ABOVE_BAND_WAIT",
        )
        self.assertEqual(fields["gate_verdict"], "defer_until_veto_clears")
        self.assertEqual(fields["gate_vetoes"], ["above band / no-chase"])
        self.assertIn("promotion_gate_fields_aligned_to_current_band_status", fields["warnings"])

    def test_in_band_removes_stale_above_band_veto(self) -> None:
        fields = spine.normalized_promotion_gate_fields(
            "defer_until_veto_clears",
            ["above band / no-chase"],
            "IN_BAND",
        )
        self.assertEqual(fields["gate_verdict"], "in_band_review_hold")
        self.assertEqual(fields["gate_vetoes"], [])
        self.assertIn("promotion_gate_fields_aligned_to_current_band_status", fields["warnings"])

    def test_in_band_preserves_non_band_vetoes(self) -> None:
        fields = spine.normalized_promotion_gate_fields(
            "defer_until_veto_clears",
            ["above band / no-chase", "current opportunity digest blocked/deferred"],
            "IN_BAND",
        )
        self.assertEqual(fields["gate_verdict"], "defer_until_veto_clears")
        self.assertEqual(fields["gate_vetoes"], ["current opportunity digest blocked/deferred"])


if __name__ == "__main__":
    unittest.main()
