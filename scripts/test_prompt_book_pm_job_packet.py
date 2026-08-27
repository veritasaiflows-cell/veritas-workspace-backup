#!/usr/bin/env python3
from __future__ import annotations

import unittest

import prompt_book_pm_job_packet as pm_jobs


class PromptBookPmJobPacketTests(unittest.TestCase):
    def test_pm_jobs_are_review_only(self) -> None:
        packet = pm_jobs.build_pm_job_packet()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertGreaterEqual(packet["summary"]["job_count"], 4)
        for job in packet["jobs"]:
            self.assertEqual(job["status"], "candidate_review_only")
            self.assertFalse(job["authority_boundary"]["skill_auto_apply"])
            self.assertFalse(job["authority_boundary"]["capital_deployment"])
            self.assertFalse(job["authority_boundary"]["paper_live_account_action"])

    def test_contains_eval_gap_job(self) -> None:
        packet = pm_jobs.build_pm_job_packet()
        ids = {job["job_id"] for job in packet["jobs"]}
        self.assertIn("pm-prompt-book-eval-gap-v0", ids)

    def test_eval_gap_job_becomes_maintenance_when_no_gaps(self) -> None:
        packet = pm_jobs.build_pm_job_packet()
        jobs = {job["job_id"]: job for job in packet["jobs"]}
        eval_job = jobs["pm-prompt-book-eval-gap-v0"]
        self.assertEqual(packet["summary"]["high_priority_gap_count"], 0)
        self.assertEqual(eval_job["priority"], "low")
        self.assertEqual(eval_job["title"], "Maintain prompt-book eval fixture coverage")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
