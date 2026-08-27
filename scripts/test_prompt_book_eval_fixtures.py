#!/usr/bin/env python3
from __future__ import annotations

import unittest

import prompt_book_eval_fixtures as fixtures
import prompt_book_registry as registry


class PromptBookEvalFixtureTests(unittest.TestCase):
    def test_fixture_packet_covers_all_p0_targets(self) -> None:
        packet = fixtures.build_fixture_packet()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["validation"]["status"], "ok")
        covered = set(packet["summary"]["covered_prompt_ids"])
        self.assertTrue(set(fixtures.P0_FIXTURE_PROMPT_IDS).issubset(covered))
        self.assertTrue(set(fixtures.FIXTURE_PROMPT_IDS).issubset(covered))
        self.assertIn("current-opportunity-approval-brief-v1", covered)
        self.assertIn("question-route-catalog-v1", covered)
        self.assertEqual(packet["summary"]["fixture_target_count"], len(fixtures.FIXTURE_PROMPT_IDS))
        self.assertFalse(packet["summary"]["prompt_text_stored"])
        self.assertTrue(packet["summary"]["raw_capture_blocked"])

    def test_fixtures_preserve_review_only_boundary(self) -> None:
        packet = fixtures.build_fixture_packet()
        for fixture in packet["fixtures"]:
            boundary = fixture["authority_assertions"]
            self.assertTrue(boundary["review_only"])
            self.assertTrue(boundary["metadata_only"])
            self.assertFalse(boundary["skill_auto_apply"])
            self.assertFalse(boundary["cron_schedule_mutation"])
            self.assertFalse(boundary["finance_canon_portfolio_mutation"])
            self.assertFalse(boundary["capital_deployment"])
            self.assertFalse(boundary["paper_live_account_action"])
            source_packet = fixture["synthetic_source_packet"]
            self.assertFalse(source_packet["contains_user_request_body"])
            self.assertFalse(source_packet["contains_model_response_body"])
            self.assertFalse(source_packet["contains_tool_io_body"])
            self.assertFalse(source_packet["contains_sensitive_material"])

    def test_registry_marks_p0_entries_covered_by_fixture_test(self) -> None:
        packet = registry.build_registry()
        entries = {entry["prompt_id"]: entry for entry in packet["entries"]}
        for prompt_id in fixtures.FIXTURE_PROMPT_IDS:
            eval_contract = entries[prompt_id]["eval_contract"]
            self.assertEqual(eval_contract["status"], "covered")
            self.assertIn("python scripts\\test_prompt_book_eval_fixtures.py", eval_contract["commands"])
            self.assertEqual(eval_contract["fixture_id"], f"fixture-{prompt_id}")

    def test_validation_blocks_missing_fixture_coverage(self) -> None:
        packet = fixtures.build_fixture_packet()
        packet["fixtures"] = packet["fixtures"][1:]
        result = fixtures.validate_fixture_packet(packet)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("missing_p0_fixture_coverage" in error for error in result["errors"]))
        self.assertTrue(any("missing_fixture_coverage" in error for error in result["errors"]))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
