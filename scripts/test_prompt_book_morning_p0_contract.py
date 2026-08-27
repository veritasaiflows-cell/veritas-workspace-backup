#!/usr/bin/env python3
from __future__ import annotations

import unittest

import prompt_book_morning_p0_contract as contract


class PromptBookMorningP0ContractTests(unittest.TestCase):
    def test_contract_is_review_only_and_pickup_ready(self) -> None:
        packet = contract.build_contract()
        self.assertIn(packet["status"], {"ok", "warning"})
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertEqual(packet["summary"]["readiness_state"], "ready_for_morning_pickup")
        self.assertTrue(packet["authority_boundary"]["review_only"])
        self.assertTrue(packet["authority_boundary"]["metadata_only"])
        self.assertFalse(packet["authority_boundary"]["skill_auto_apply"])
        self.assertFalse(packet["authority_boundary"]["cron_schedule_mutation"])
        self.assertFalse(packet["authority_boundary"]["finance_canon_portfolio_mutation"])
        self.assertFalse(packet["authority_boundary"]["capital_deployment"])
        self.assertFalse(packet["authority_boundary"]["paper_live_account_action"])

    def test_includes_expected_high_priority_eval_fixtures(self) -> None:
        packet = contract.build_contract()
        target_ids = set(packet["p0_fixture_target_prompt_ids"])
        covered_ids = set(packet["p0_fixture_covered_prompt_ids"])
        self.assertTrue(set(contract.HIGH_PRIORITY_EVAL_FIXTURES).issubset(target_ids))
        self.assertTrue(set(contract.HIGH_PRIORITY_EVAL_FIXTURES).issubset(covered_ids))
        self.assertEqual(packet["summary"]["p0_remaining_high_priority_count"], 0)

    def test_skill_review_records_applied_and_superseded_proposals(self) -> None:
        packet = contract.build_contract()
        skill_review = packet["skill_proposal_review"]
        self.assertEqual(skill_review["reviewed_proposal_count"], 6)
        self.assertEqual(skill_review["pending_proposal_count"], 0)
        self.assertEqual(skill_review["applied_proposal_count"], 5)
        self.assertEqual(skill_review["rejected_proposal_count"], 1)
        self.assertEqual(skill_review["duplicate_update_skills"], [])
        self.assertNotIn("duplicate_skill_update_proposals_require_merge_before_apply", packet["validation"]["warnings"])
        agi_rows = [
            row
            for row in skill_review["proposals"]
            if row["skill_name"] == "agi-harness-readiness-operator"
        ]
        self.assertEqual(len(agi_rows), 2)
        self.assertEqual({row["review_status"] for row in agi_rows}, {"applied", "rejected_superseded"})

    def test_prompt_book_operator_was_first_applied_candidate(self) -> None:
        packet = contract.build_contract()
        ordered = [
            row
            for row in packet["skill_proposal_review"]["proposals"]
            if row.get("apply_order") is not None
        ]
        self.assertEqual(ordered[0]["skill_name"], "veritas-prompt-book-operator")
        self.assertEqual(ordered[0]["apply_order"], 1)
        self.assertEqual(ordered[0]["review_status"], "applied")
        self.assertIn("eval fixtures", ordered[0]["recommended_change"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
