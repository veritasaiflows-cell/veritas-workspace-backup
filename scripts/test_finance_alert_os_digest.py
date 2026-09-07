from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import finance_alert_os_digest as digest
from finance_alert_os_digest import build_message, controller_semantic_errors


class FinanceAlertOsDigestTests(unittest.TestCase):
    def test_message_is_alert_and_recommendation_only(self) -> None:
        levels = {
            "generated_at_utc": "2026-08-30T00:00:00Z",
            "summary": {
                "alert_state_counts": {"monitor_only": 1},
                "band_entry_signal_tickers": [],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": ["ETN"],
                "freshness_review_tickers": [],
                "quote_session_dates": ["2026-08-28"],
                "quote_as_of_utc_values": ["2026-08-28T19:59:44Z"],
            },
        }
        message = build_message("morning", levels)
        self.assertIn("Band-entry alerts: none", message)
        self.assertIn("Monitor-only: ETN", message)
        self.assertIn("Quote session date: 2026-08-28", message)
        self.assertIn("Quote evidence as of: 2026-08-28T19:59:44Z", message)
        self.assertIn("alert firing is suppressed", message)
        self.assertIn("no capital", message.lower())

    def test_alerts_without_intraday_eligibility_fail_closed(self) -> None:
        levels = {
            "summary": {
                "band_entry_signal_tickers": ["ETN"],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "fresh_intraday_signal_eligible_tickers": [],
            }
        }
        self.assertIn(
            "controller emits alerts without fresh-intraday eligibility proof",
            controller_semantic_errors(levels),
        )

    def test_intraday_eligible_alerts_are_allowed(self) -> None:
        levels = {
            "summary": {
                "band_entry_signal_tickers": ["ETN"],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "fresh_intraday_signal_eligible_tickers": ["ETN"],
            }
        }
        self.assertEqual(controller_semantic_errors(levels), [])


class ControllerStalenessTests(unittest.TestCase):
    def _levels(self, age_hours: float) -> dict:
        stamp = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        return {
            "generated_at_utc": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "alert_state_counts": {"monitor_only": 1},
                "band_entry_signal_tickers": [],
                "invalidation_signal_tickers": [],
                "no_chase_signal_tickers": [],
                "monitor_only_tickers": ["ETN"],
                "freshness_review_tickers": [],
                "quote_session_dates": ["2026-09-04"],
                "quote_as_of_utc_values": ["2026-09-04T19:59:44Z"],
            },
        }

    def _payload(self, levels: dict, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert-level-freshness-controller.json"
            path.write_text(json.dumps(levels), encoding="utf-8")
            with mock.patch.object(digest, "LEVELS", path):
                return digest.build_payload("morning", **kwargs)

    def test_fresh_controller_is_delivered(self) -> None:
        payload = self._payload(self._levels(0.5))

        self.assertEqual(payload["status"], "ok")
        self.assertIsNotNone(payload["message_preview"])

    def test_stale_controller_blocks_delivery(self) -> None:
        payload = self._payload(self._levels(20))

        self.assertEqual(payload["status"], "blocked")
        self.assertIsNone(payload["message_preview"])
        self.assertTrue(
            any("is stale" in error for error in payload["validation"]["errors"]),
            payload["validation"]["errors"],
        )

    def test_age_limit_is_configurable(self) -> None:
        payload = self._payload(self._levels(20), max_controller_age_hours=24.0)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source_artifacts"]["alert_levels"]["max_age_hours"], 24.0)

    def test_missing_stamp_fails_closed(self) -> None:
        levels = self._levels(0.5)
        levels.pop("generated_at_utc")
        payload = self._payload(levels)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn(
            "alert-level freshness proof has no usable generated_at_utc stamp",
            payload["validation"]["errors"],
        )

    def test_future_stamp_fails_closed(self) -> None:
        payload = self._payload(self._levels(-5))

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(
            any("in the future" in error for error in payload["validation"]["errors"]),
            payload["validation"]["errors"],
        )

    def test_small_negative_skew_is_tolerated(self) -> None:
        self.assertEqual(self._payload(self._levels(-0.05))["status"], "ok")

    def test_unparseable_stamp_fails_closed(self) -> None:
        levels = self._levels(0.5)
        levels["generated_at_utc"] = "not-a-timestamp"

        self.assertEqual(self._payload(levels)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
