#!/usr/bin/env python3
from __future__ import annotations

import unittest

import question_route_usage_ledger as ledger


class QuestionRouteUsageLedgerTests(unittest.TestCase):
    def test_baseline_ledger_is_metadata_only_and_valid(self) -> None:
        packet = ledger.build_ledger()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertEqual(packet["summary"]["route_count"], 9)
        self.assertEqual(packet["summary"]["row_count"], 9)
        self.assertEqual(packet["summary"]["over_budget_count"], 0)
        self.assertTrue(packet["summary"]["raw_capture_blocked"])
        self.assertFalse(packet["summary"]["prompt_text_stored"])
        for row in packet["rows"]:
            self.assertFalse(row["question_body_stored"])
            self.assertFalse(row["answer_body_stored"])
            self.assertFalse(row["tool_io_body_stored"])

    def test_over_budget_event_requires_pm_followup(self) -> None:
        packet = ledger.build_ledger(
            route_id="capital_deployment_recommendations",
            actual_tool_calls=9,
            stale_or_blocker_flag=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertEqual(packet["summary"]["over_budget_count"], 1)
        self.assertEqual(packet["summary"]["stale_or_blocker_count"], 1)
        row = packet["rows"][0]
        self.assertEqual(row["route_id"], "capital_deployment_recommendations")
        self.assertTrue(row["over_budget"])
        self.assertTrue(row["pm_followup_required"])
        self.assertTrue(row["stale_or_blocker_flag"])

    def test_validation_blocks_raw_storage_flags(self) -> None:
        packet = ledger.build_ledger()
        packet["rows"][0]["question_body_stored"] = True

        result = ledger.validate_ledger(packet)

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("question_body_stored_not_false" in error for error in result["errors"]))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
