"""Regression coverage for weekend-only freshness-debt tolerance.

Owner-approved 2026-09-20: pure weekend staleness (every row freshness_decay
under market_closed_weekend_or_holiday with a quote that is still the current
last-completed session) is warning-grade. Every other shape stays error-grade.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import run_alerts_recommendations_chain as chain


def _row(alert_state="freshness_decay",
         window="market_closed_weekend_or_holiday",
         calendar="current_last_completed_session",
         ticker="AAA"):
    return {"ticker": ticker, "alert_state": alert_state,
            "market_session_window": window,
            "quote_calendar_status": calendar}


def _write(payload):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      encoding="utf-8")
    json.dump(payload, tmp)
    tmp.close()
    return tmp.name


def _controller(rows, validation="ok"):
    return {"validation": {"status": validation, "errors": [], "warnings": []},
            "rows": rows}


class WeekendOnlyDebtTest(unittest.TestCase):
    def test_pure_weekend_decay_is_eligible(self):
        path = _write(_controller([_row(ticker="AAA"), _row(ticker="BBB")]))
        try:
            result = chain.weekend_only_freshness_debt(Path(path))
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["ticker_count"], 2)

    def test_mixed_state_stays_error(self):
        path = _write(_controller([_row(), _row(alert_state="band_entry")]))
        try:
            result = chain.weekend_only_freshness_debt(Path(path))
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertFalse(result["eligible"])
        self.assertIn("non_decay_state", result["reason"])

    def test_non_weekend_window_stays_error(self):
        path = _write(_controller([_row(window="market_hours_fresh")]))
        try:
            result = chain.weekend_only_freshness_debt(Path(path))
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertFalse(result["eligible"])
        self.assertIn("non_weekend_window", result["reason"])

    def test_quote_older_than_last_session_stays_error(self):
        # A genuinely broken feed (Friday intake missed; quotes predate the
        # last completed session) must never be downgraded to a warning.
        path = _write(_controller([_row(calendar="stale_or_missing")]))
        try:
            result = chain.weekend_only_freshness_debt(Path(path))
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertFalse(result["eligible"])
        self.assertIn("quote_not_last_session", result["reason"])

    def test_invalid_controller_stays_error(self):
        path = _write(_controller([_row()], validation="error"))
        try:
            result = chain.weekend_only_freshness_debt(Path(path))
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertFalse(result["eligible"])

    def test_unreadable_controller_stays_error(self):
        result = chain.weekend_only_freshness_debt(
            Path(tempfile.gettempdir()) / "definitely-not-here-12345.json")
        self.assertFalse(result["eligible"])


if __name__ == "__main__":
    unittest.main()
