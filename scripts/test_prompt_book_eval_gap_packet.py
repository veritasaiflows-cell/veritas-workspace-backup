#!/usr/bin/env python3
from __future__ import annotations

import unittest

import prompt_book_eval_gap_packet as eval_gap


class PromptBookEvalGapPacketTests(unittest.TestCase):
    def test_eval_gap_packet_is_review_only(self) -> None:
        packet = eval_gap.build_eval_gap_packet()
        self.assertIn(packet["status"], {"ok", "warning"})
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertTrue(packet["authority_boundary"]["review_only"])
        self.assertFalse(packet["authority_boundary"]["capital_deployment"])
        self.assertGreaterEqual(packet["summary"]["covered_count"], 1)
        self.assertEqual(packet["summary"]["eval_gap_count"], len(packet["eval_gaps"]))

    def test_gap_rows_include_minimum_fixture_contract(self) -> None:
        packet = eval_gap.build_eval_gap_packet()
        if packet["eval_gaps"]:
            row = packet["eval_gaps"][0]
            self.assertIn("minimum_fixture", row)
            self.assertIn("expected_checks", row["minimum_fixture"])

    def test_fully_covered_registry_has_no_eval_gaps(self) -> None:
        packet = eval_gap.build_eval_gap_packet()
        self.assertEqual(packet["summary"]["eval_gap_count"], 0)
        self.assertEqual(packet["summary"]["high_priority_gap_count"], 0)
        self.assertEqual(packet["eval_gaps"], [])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
