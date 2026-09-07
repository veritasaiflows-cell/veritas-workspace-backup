#!/usr/bin/env python3
"""Focused regressions for the shared WF84/WF85 decision-state compiler."""
from __future__ import annotations

import unittest
from pathlib import Path

import finance_decision_state_compiler as compiler


class FinanceDecisionStateCompilerTests(unittest.TestCase):
    def clean_source(self) -> dict[str, object]:
        return {"source_open_status": "verified", "missing_or_stale_families": []}

    def fresh_quote(self) -> dict[str, object]:
        return {"status": "fresh", "blockers": []}

    def current_row(self, **overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "ticker": "TEST",
            "primary_state": "in_band_not_clean",
            "band_status": "IN_BAND",
            "entry_band_low": 10,
            "entry_band_high": 12,
            "stop_or_invalidation": 9,
            "gate_verdict": "in_band_review_hold",
        }
        row.update(overrides)
        return row

    def test_gate_verdict_mapping_is_centralized(self) -> None:
        self.assertEqual(
            compiler.state_for_promotion_gate_verdict("in_band_review_hold"),
            "in_band_not_clean",
        )
        self.assertEqual(
            compiler.state_for_promotion_gate_verdict("watch_for_reclaim_or_pullback"),
            "promotion_vetoed",
        )
        self.assertIsNone(
            compiler.state_for_promotion_gate_verdict("promote_for_owner_review")
        )

    def test_current_compiler_owns_its_immutable_blocker_sets(self) -> None:
        self.assertEqual(
            compiler.BLOCKING_PRIMARY_STATES,
            {
                "blocked_missing_freshness",
                "blocked_missing_source_open",
                "blocked_missing_band_or_stop",
                "blocked_wf67_guard_context",
                "below_stop_or_invalidation",
                "evidence_repair",
            },
        )
        self.assertEqual(
            compiler.INVALIDATION_PRIMARY_STATES,
            {"below_stop_or_invalidation", "invalidation_review"},
        )
        source = Path(compiler.__file__).read_text(encoding="utf-8")
        self.assertNotIn("trade_grade_decision_os_contract", source)

    def test_above_band_rewrites_stale_in_band_gate(self) -> None:
        fields = compiler.normalized_promotion_gate_fields(
            "in_band_review_hold",
            [],
            "ABOVE_BAND_WAIT",
        )
        self.assertEqual(fields["gate_verdict"], "defer_until_veto_clears")
        self.assertEqual(fields["gate_vetoes"], ["above band / no-chase"])
        self.assertIn("promotion_gate_fields_aligned_to_current_band_status", fields["warnings"])

    def test_in_band_removes_stale_above_band_veto(self) -> None:
        fields = compiler.normalized_promotion_gate_fields(
            "defer_until_veto_clears",
            ["above band / no-chase"],
            "IN_BAND",
        )
        self.assertEqual(fields["gate_verdict"], "in_band_review_hold")
        self.assertEqual(fields["gate_vetoes"], [])

    def test_review_ready_requires_current_promote_and_in_band(self) -> None:
        state, blockers = compiler.classify_decision_state(
            self.current_row(
                primary_state="blocked_missing_freshness",
                gate_verdict="promote_for_owner_review",
            ),
            self.clean_source(),
            self.fresh_quote(),
            {"thin_monitor_row": False},
        )
        self.assertEqual(state, "review_ready")
        self.assertEqual(blockers, [])

    def test_above_band_overrides_current_promote(self) -> None:
        state, blockers = compiler.classify_decision_state(
            self.current_row(
                primary_state="blocked_missing_freshness",
                band_status="ABOVE_BAND",
                gate_verdict="promote_for_owner_review",
            ),
            self.clean_source(),
            self.fresh_quote(),
            {"thin_monitor_row": False},
        )
        self.assertEqual(state, "no_chase")
        self.assertEqual(blockers, ["band_status=ABOVE_BAND"])

    def test_in_band_hold_stays_monitor_only(self) -> None:
        state, blockers = compiler.classify_decision_state(
            self.current_row(),
            self.clean_source(),
            self.fresh_quote(),
            {"thin_monitor_row": False},
        )
        self.assertEqual(state, "monitor_only")
        self.assertEqual(blockers, ["not_owner_review_candidate"])

    def test_current_source_and_freshness_clear_stale_blocker(self) -> None:
        state, blockers = compiler.classify_decision_state(
            self.current_row(
                primary_state="blocked_missing_freshness",
                band_status="ABOVE_BAND_WAIT",
            ),
            self.clean_source(),
            self.fresh_quote(),
            {"thin_monitor_row": False},
        )
        self.assertEqual(state, "no_chase")
        self.assertEqual(blockers, ["band_status=ABOVE_BAND_WAIT"])

    def test_missing_source_blocks_after_band_complete(self) -> None:
        state, blockers = compiler.classify_decision_state(
            self.current_row(gate_verdict="promote_for_owner_review"),
            {"source_open_status": "blocked"},
            self.fresh_quote(),
            {"thin_monitor_row": False},
        )
        self.assertEqual(state, "blocked_missing_source_open")
        self.assertEqual(blockers, ["source_open_not_verified"])

    def test_thin_monitor_does_not_become_band_blocker(self) -> None:
        state, blockers = compiler.classify_decision_state(
            {
                "ticker": "THIN",
                "primary_state": "evidence_repair",
                "band_status": "UNKNOWN",
                "entry_band_low": None,
                "entry_band_high": None,
                "stop_or_invalidation": None,
            },
            {"source_open_status": "scoped_thin_monitor_not_required"},
            {"status": "scoped_thin_monitor_not_required"},
            {"thin_monitor_row": 1, "production_answer_path_member": 0, "decision_grade_eligible": 0},
        )
        self.assertEqual(state, "monitor_only")
        self.assertEqual(blockers, ["thin_monitor_not_decision_grade"])


if __name__ == "__main__":
    unittest.main()
