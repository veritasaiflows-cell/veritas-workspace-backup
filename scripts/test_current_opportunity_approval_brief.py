#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import current_opportunity_approval_brief as brief


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class CurrentOpportunityApprovalBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        tmp = self.root / "tmp"
        _write(tmp / "cron-control-packet.json", {
            "status": "ok", "generated_at_utc": "2026-08-30T00:00:00Z",
            "validation": {"status": "ok"},
            "summary": {"blocked_count": 0, "stale_count": 0, "live_scheduler_last_run_exception_count": 0},
        })
        _write(tmp / "finance-sql-canon-access-validation.json", {
            "status": "ok", "generated_at_utc": "2026-08-30T00:00:00Z", "validation": {"status": "ok"},
        })
        _write(tmp / "intraday-alerts" / "quote-snapshot-proof.json", {
            "status": "ok", "generated_at_utc": "2026-08-30T00:00:00Z", "validation": {"status": "ok"},
        })
        _write(tmp / "alert-level-freshness-controller.json", {
            "status": "ok", "generated_at_utc": "2026-08-30T00:00:00Z", "validation": {"status": "ok"},
            "rows": [{
                "ticker": "ETN", "alert_state": "band_entry", "freshness_status": "current",
                "confidence": "medium", "latest_price": 402.56, "reference_low": 385.98,
                "reference_high": 434.4, "invalidation_threshold": 363.96,
            }],
        })
        _write(tmp / "finance-alert-os-digest.json", {
            "status": "ok", "generated_at_utc": "2026-08-30T00:00:00Z", "validation": {"status": "ok"},
            "summary": {
                "ticker_count": 1, "alert_state_counts": {"band_entry": 1},
                "band_entry_signal_tickers": ["ETN"], "no_chase_signal_tickers": [],
                "freshness_review_tickers": [], "invalidation_signal_tickers": [],
            },
        })
        _write(tmp / "owner-gated-action-review-queue.json", {
            "status": "ok", "generated_at_utc": "2026-08-30T00:00:00Z", "validation": {"status": "ok"},
            "review_items": [{
                "gate": "alert_canon_policy_mutation", "title": "Review alert repair",
                "priority": 66, "decision_state": "owner_decision_required",
                "required_owner_decision": "approve_reject_defer_or_request_deeper_review",
                "required_before_apply": ["exact diff"], "source": "tmp/proof.json",
            }],
        })

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_builds_alerts_only_brief(self) -> None:
        packet = brief.build_brief(self.root)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["summary"]["finance_ticker_count"], 1)
        self.assertEqual(packet["summary"]["owner_review_required_count"], 1)
        self.assertEqual(packet["current_opportunities"]["alert_rows"][0]["ticker"], "ETN")

    def test_refresh_contract_has_no_retired_finance_routes(self) -> None:
        joined = "\n".join(" ".join(command).lower() for command in brief.REFRESH_COMMANDS)
        self.assertIn("run_alerts_recommendations_chain.py", joined)
        for forbidden in ("trade_grade", "wf67", "wf78", "paper", "deployment", "position_sizing"):
            self.assertNotIn(forbidden, joined)

    def test_authority_is_fail_closed(self) -> None:
        boundary = brief.build_brief(self.root)["authority_boundary"]
        self.assertTrue(boundary["review_only"])
        self.assertFalse(boundary["maintains_portfolio_state"])
        self.assertFalse(boundary["maintains_simulated_account_state"])
        self.assertFalse(boundary["capital_or_order_authority"])
        self.assertFalse(boundary["paper_or_live_execution_allowed"])
        self.assertFalse(boundary["owner_approval_inferred"])

    def test_missing_required_source_blocks(self) -> None:
        (self.root / "tmp" / "finance-alert-os-digest.json").unlink()
        packet = brief.build_brief(self.root)
        self.assertEqual(packet["status"], "blocked")
        self.assertIn("missing_source:recommendation_digest", packet["validation"]["errors"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
