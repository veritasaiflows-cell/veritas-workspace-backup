from __future__ import annotations

import unittest
from unittest.mock import patch

import cron_operator_ledger as ledger


class CronOperatorLedgerTests(unittest.TestCase):
    def test_live_gateway_state_beats_legacy_file_snapshot(self) -> None:
        live_jobs = [{"id": "live", "name": "Live Scheduler Job", "enabled": True}]
        gateway_meta = {"available": True, "returncode": 0, "total": 1}

        with (
            patch.object(ledger, "cron_jobs_from_gateway", return_value=(live_jobs, gateway_meta)),
            patch.object(ledger, "cron_jobs_from_store", return_value=[{"id": "legacy"}]),
        ):
            jobs, source = ledger.cron_jobs()

        self.assertEqual(jobs, live_jobs)
        self.assertEqual(source["source"], "gateway_cli")
        self.assertFalse(source["gateway_fallback_used"])
        self.assertEqual(source["gateway"], gateway_meta)

    def test_legacy_file_is_used_only_when_live_gateway_is_unavailable(self) -> None:
        legacy_jobs = [{"id": "legacy", "name": "Legacy Snapshot", "enabled": True}]
        gateway_meta = {"available": True, "returncode": 1, "error": "openclaw_cron_list_failed"}

        with (
            patch.object(ledger, "cron_jobs_from_gateway", return_value=([], gateway_meta)),
            patch.object(ledger, "cron_jobs_from_store", return_value=legacy_jobs),
        ):
            jobs, source = ledger.cron_jobs()

        self.assertEqual(jobs, legacy_jobs)
        self.assertEqual(source["source"], "legacy_file_store_fallback")
        self.assertTrue(source["gateway_fallback_used"])
        self.assertEqual(source["gateway"], gateway_meta)

    def test_success_diagnostic_is_not_reported_as_last_error(self) -> None:
        jobs = ledger.summarize_jobs(
            [
                {
                    "id": "clean",
                    "name": "Clean proof job",
                    "enabled": True,
                    "state": {
                        "lastStatus": "ok",
                        "consecutiveErrors": 0,
                        "lastDiagnosticSummary": "validated warning-grade proof",
                    },
                }
            ]
        )

        self.assertEqual(jobs[0]["last_status"], "ok")
        self.assertEqual(jobs[0]["last_error"], "")
        self.assertEqual(jobs[0]["last_diagnostic_summary"], "validated warning-grade proof")


if __name__ == "__main__":
    unittest.main()
