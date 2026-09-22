from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import alert_level_freshness_controller as controller
import phase3g_dynamic_execution as phase3g_adapter
from finance_sql_canon_access import dynamic_entitlement_payload_fingerprint
from alert_level_freshness_controller import (
    QUOTE_PROOF_REQUIRED_FALSE_AUTHORITY,
    age_hours,
    classify_signal,
    confidence_label,
    quote_evaluation_policy,
    quote_proof_is_clean,
    quote_rows_by_ticker,
)


class _FakeDynamicScope:
    source = "guarded_sql:universe_membership.tier"

    def __init__(self) -> None:
        self.fingerprint = dynamic_entitlement_payload_fingerprint({
            "members": [{"ticker": "AAA", "tier": "A", "decision_grade_eligible": True}],
        })
        self.memberships = ["AAA"]
        self.overflow_tickers: list[str] = []
        self.aliases = {"AAA": "AAA"}
        self.integrity_breaches: list[object] = []

    def payload(self) -> dict:
        return {
            "source": "guarded_sql:universe_membership.tier",
            "members": [{"ticker": "AAA", "tier": "A", "decision_grade_eligible": True}],
            "fingerprint": self.fingerprint,
            "count": 1,
            "tier_breakdown": {"A": 1, "B": 0},
            "integrity_breaches": [],
            "envelope_name": "test",
            "envelope_count": 1,
            "overflow_tickers": [],
            "overflow_count": 0,
        }


class _FakeDynamicClient:
    def __init__(self) -> None:
        self.calls = 0
        self.scope = _FakeDynamicScope()

    def dynamic_entitlement_scope(self, *args: object, **kwargs: object) -> _FakeDynamicScope:
        self.calls += 1
        return self.scope


def clean_quote_fixture(*, closed_session: bool = False) -> tuple[dict, dict, dict]:
    if closed_session:
        row = {
            "symbol": "ETN",
            "calendar_freshness_status": "current_last_completed_session",
            "freshness_status": "stale",
            "market_session_window": "market_closed_weekend_or_holiday",
            "fresh_intraday_allowed": False,
            "closed_market_expected_stale_allowed": True,
        }
    else:
        row = {
            "symbol": "ETN",
            "calendar_freshness_status": "fresh_intraday",
            "freshness_status": "fresh",
            "market_session_window": "market_hours_fresh",
            "fresh_intraday_allowed": True,
            "closed_market_expected_stale_allowed": False,
        }
    proof = {
        "status": "ok",
        "authority": {key: False for key in QUOTE_PROOF_REQUIRED_FALSE_AUTHORITY},
        "credential_source": {"ambiguous_or_live_names_detected": False},
        "symbols_requested": ["ETN"],
        "symbols_observed": ["ETN"],
        "symbols_missing": [],
        "snapshots": [copy.deepcopy(row)],
        "market_session": {
            "market_session_window": row["market_session_window"],
            "fresh_intraday_allowed": row["fresh_intraday_allowed"],
            "closed_market_expected_stale_allowed": row["closed_market_expected_stale_allowed"],
        },
    }
    validation = {
        "status": "ok",
        "critical_count": 0,
        "findings": [],
        "validated_artifact": "tmp/intraday-alerts/quote-snapshot-proof.json",
    }
    return row, proof, validation


def boundary_quote_fixture(market_session_window: str) -> tuple[dict, dict, dict]:
    """Fresh intraday quote landing exactly at a session-boundary window.

    Mirrors clean_quote_fixture shape: row, proof with a matching
    market_session block, and validation. Producer contract pins
    fresh_intraday_allowed=False for all boundary windows and the
    per-window closed_market_expected_stale_allowed flag.
    """
    boundary_closed_flag = {"pre_open": True, "open_settling": False, "post_close": True}
    row = {
        "symbol": "ETN",
        "calendar_freshness_status": "fresh_intraday",
        "freshness_status": "fresh",
        "market_session_window": market_session_window,
        "fresh_intraday_allowed": False,
        "closed_market_expected_stale_allowed": boundary_closed_flag[market_session_window],
    }
    proof = {
        "status": "ok",
        "authority": {key: False for key in QUOTE_PROOF_REQUIRED_FALSE_AUTHORITY},
        "credential_source": {"ambiguous_or_live_names_detected": False},
        "symbols_requested": ["ETN"],
        "symbols_observed": ["ETN"],
        "symbols_missing": [],
        "snapshots": [copy.deepcopy(row)],
        "market_session": {
            "market_session_window": row["market_session_window"],
            "fresh_intraday_allowed": row["fresh_intraday_allowed"],
            "closed_market_expected_stale_allowed": row["closed_market_expected_stale_allowed"],
        },
    }
    validation = {
        "status": "ok",
        "critical_count": 0,
        "findings": [],
        "validated_artifact": "tmp/intraday-alerts/quote-snapshot-proof.json",
    }
    return row, proof, validation


class AlertLevelFreshnessControllerTests(unittest.TestCase):
    def test_dynamic_preview_and_gate_denial_do_not_build_or_write(self) -> None:
        client = _FakeDynamicClient()
        scope, preview = controller.dynamic_entitlement_preview(client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(scope.fingerprint, preview["scope"]["fingerprint"])
        self.assertEqual(preview["provider_calls"], 0)
        self.assertEqual(preview["output_writes"], 0)
        # Valid preview-only CLI is inert: exactly one adapter scope read,
        # exit 0, and positively zero build/write work.
        client = _FakeDynamicClient()
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=client),
            mock.patch.object(controller, "build_payload") as build_payload,
            mock.patch.object(controller, "write_json") as write_json,
            mock.patch.object(sys, "argv", ["controller", "--dynamic-entitlement-preview"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(controller.main(), 0)
            self.assertEqual(client.calls, 1)
            build_payload.assert_not_called()
            write_json.assert_not_called()
        planned = json.loads(stdout.getvalue())
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(planned["provider_calls"], 0)
        self.assertEqual(planned["output_writes"], 0)
        # Contradictory preview+write is rejected early: exit 1 with zero
        # scope/SQL reads and zero build/write work.
        client = _FakeDynamicClient()
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=client),
            mock.patch.object(controller, "build_payload") as build_payload,
            mock.patch.object(controller, "write_json") as write_json,
            mock.patch.object(sys, "argv", ["controller", "--dynamic-entitlement-preview", "--write"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(controller.main(), 1)
            self.assertEqual(client.calls, 0)
            build_payload.assert_not_called()
            write_json.assert_not_called()
        denied = json.loads(stdout.getvalue())
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"], "dynamic_incompatible_cli_options")
        # Scope+write with a non-policy origin is rejected before any
        # scope/SQL read and performs zero build/write work.
        client = _FakeDynamicClient()
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=client),
            mock.patch.object(controller, "build_payload") as build_payload,
            mock.patch.object(controller, "write_json") as write_json,
            mock.patch.object(sys, "argv", ["controller", "--dynamic-entitlement-scope", "--write"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(controller.main(), 1)
            self.assertEqual(client.calls, 0)
            build_payload.assert_not_called()
            write_json.assert_not_called()
        denied = json.loads(stdout.getvalue())
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"], "dynamic_execution_requires_write_and_policy_origin")

    def test_signal_classification(self) -> None:
        self.assertEqual(classify_signal(95.0, 90.0, 100.0, 80.0), "band_entry")
        self.assertEqual(classify_signal(75.0, 90.0, 100.0, 80.0), "invalidation_alert")
        self.assertEqual(classify_signal(103.0, 90.0, 100.0, 80.0), "no_chase")
        self.assertEqual(classify_signal(88.0, 90.0, 100.0, 80.0), "near_band")
        self.assertEqual(classify_signal(None, 90.0, 100.0, 80.0), "freshness_decay")

    def test_stale_or_conflicted_confidence_fails_low(self) -> None:
        self.assertEqual(confidence_label(5, True, False), "low")
        self.assertEqual(confidence_label(5, False, True), "low")
        self.assertEqual(confidence_label(5, False, False), "high")

    def test_quote_rows_use_symbol_as_ticker(self) -> None:
        rows = quote_rows_by_ticker({"snapshots": [{"symbol": "etn", "price": 1.0}]})
        self.assertEqual(rows["ETN"]["price"], 1.0)

    def test_future_timestamp_produces_negative_age(self) -> None:
        now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
        future = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        self.assertEqual(age_hours(future, now), -1.0)

    def test_last_completed_session_is_monitor_only_not_fire_eligible(self) -> None:
        row, proof, validation = clean_quote_fixture(closed_session=True)
        policy = quote_evaluation_policy(
            row,
            30.0,
            36.0,
            quote_proof=proof,
            quote_validation=validation,
        )
        self.assertTrue(policy["calendar_current"])
        self.assertTrue(policy["monitor_only"])
        self.assertFalse(policy["fire_eligible"])
        self.assertFalse(policy["stale_or_missing"])

    def test_current_clean_intraday_quote_can_fire(self) -> None:
        row, proof, validation = clean_quote_fixture()
        self.assertTrue(quote_proof_is_clean(proof, validation, row))
        policy = quote_evaluation_policy(
            row,
            0.1,
            36.0,
            quote_proof=proof,
            quote_validation=validation,
        )
        self.assertTrue(policy["fire_eligible"])
        self.assertFalse(policy["monitor_only"])
        self.assertFalse(policy["stale_or_missing"])

    def test_self_asserted_fresh_row_without_clean_proof_cannot_fire(self) -> None:
        row, _, _ = clean_quote_fixture()
        policy = quote_evaluation_policy(row, 0.1, 36.0)
        self.assertFalse(policy["fire_eligible"])
        self.assertTrue(policy["stale_or_missing"])

    def test_missing_stale_future_and_nonfinite_ages_fail_closed(self) -> None:
        row, proof, validation = clean_quote_fixture()
        for age in (None, 1000.0, -0.01, math.nan, math.inf, -math.inf, True):
            with self.subTest(age=age):
                policy = quote_evaluation_policy(
                    row,
                    age,
                    36.0,
                    quote_proof=proof,
                    quote_validation=validation,
                )
                self.assertFalse(policy["fire_eligible"])
                self.assertTrue(policy["stale_or_missing"])

    def test_inexact_calendar_session_or_boolean_metadata_fails_closed(self) -> None:
        for field, value in (
            ("calendar_freshness_status", "current_last_completed_session"),
            ("market_session_window", "post_close"),
            ("fresh_intraday_allowed", "true"),
            ("closed_market_expected_stale_allowed", True),
        ):
            with self.subTest(field=field):
                row, proof, validation = clean_quote_fixture()
                row[field] = value
                policy = quote_evaluation_policy(
                    row,
                    0.1,
                    36.0,
                    quote_proof=proof,
                    quote_validation=validation,
                )
                self.assertFalse(policy["fire_eligible"])
                self.assertTrue(policy["stale_or_missing"])

    def test_bad_status_validation_authority_and_conflicts_fail_clean_proof(self) -> None:
        mutations = (
            lambda proof, validation: proof.update(status="blocked"),
            lambda proof, validation: validation.update(status="error"),
            lambda proof, validation: validation.update(critical_count=1),
            lambda proof, validation: proof["authority"].update(paper_trade_allowed=True),
            lambda proof, validation: proof["authority"].pop("paper_trade_allowed"),
            lambda proof, validation: proof.update(conflict_count=1),
            lambda proof, validation: proof.update(symbols_missing=["ETN"]),
            lambda proof, validation: validation["findings"].append(
                {"severity": "warning", "code": "metadata_conflict"}
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                row, proof, validation = clean_quote_fixture()
                mutate(proof, validation)
                self.assertFalse(quote_proof_is_clean(proof, validation, row))
                policy = quote_evaluation_policy(
                    row,
                    0.1,
                    36.0,
                    quote_proof=proof,
                    quote_validation=validation,
                )
                self.assertFalse(policy["fire_eligible"])
                self.assertTrue(policy["stale_or_missing"])

    def test_row_and_top_level_market_session_mismatch_fails_closed(self) -> None:
        row, proof, validation = clean_quote_fixture()
        proof["market_session"]["market_session_window"] = "post_close"
        self.assertFalse(quote_proof_is_clean(proof, validation, row))
        policy = quote_evaluation_policy(
            row,
            0.1,
            36.0,
            quote_proof=proof,
            quote_validation=validation,
        )
        self.assertFalse(policy["fire_eligible"])
        self.assertTrue(policy["stale_or_missing"])

    def test_fresh_quote_at_session_boundary_is_calendar_current_review_only(self) -> None:
        """Green direction: fresh boundary quotes must not decay.

        Reproduces the 2026-09-11 false freshness_decay cycles at the open
        (open_settling), close (post_close), and pre-open boundaries with
        the exact producer-contract field combinations.
        """
        for window, closed_flag in (
            ("open_settling", False),
            ("post_close", True),
            ("pre_open", True),
        ):
            with self.subTest(window=window):
                row, proof, validation = boundary_quote_fixture(window)
                self.assertIs(row["fresh_intraday_allowed"], False)
                self.assertIs(row["closed_market_expected_stale_allowed"], closed_flag)
                self.assertTrue(quote_proof_is_clean(proof, validation, row))
                policy = quote_evaluation_policy(
                    row,
                    0.1,
                    36.0,
                    quote_proof=proof,
                    quote_validation=validation,
                )
                self.assertTrue(policy["calendar_current"])
                self.assertFalse(policy["stale_or_missing"])
                self.assertFalse(policy["fire_eligible"])
                self.assertTrue(policy["monitor_only"])
                self.assertEqual(policy["classification"], "session_boundary_current")

    def test_session_boundary_adversarial_metadata_fails_closed(self) -> None:
        """Red/fail-closed direction: tampered boundary metadata stays decay."""
        cases = (
            ("stale_freshness_status", {"freshness_status": "stale"}),
            ("last_completed_calendar_status", {"calendar_freshness_status": "current_last_completed_session"}),
            ("tampered_fresh_intraday_allowed", {"fresh_intraday_allowed": True}),
            ("wrong_closed_flag_open_settling", None),
            ("market_closed_weekend_or_holiday", None),
            ("market_hours_withheld_fire", None),
        )
        for name, row_override in cases:
            with self.subTest(case=name):
                if name == "wrong_closed_flag_open_settling":
                    row, proof, validation = boundary_quote_fixture("open_settling")
                    row["closed_market_expected_stale_allowed"] = True
                    proof["snapshots"][0]["closed_market_expected_stale_allowed"] = True
                    proof["market_session"]["closed_market_expected_stale_allowed"] = True
                elif name == "market_closed_weekend_or_holiday":
                    row, proof, validation = clean_quote_fixture()
                    row.update(
                        calendar_freshness_status="fresh_intraday",
                        market_session_window="market_closed_weekend_or_holiday",
                        fresh_intraday_allowed=False,
                        closed_market_expected_stale_allowed=True,
                    )
                    proof["snapshots"][0] = copy.deepcopy(row)
                    proof["market_session"] = {
                        "market_session_window": row["market_session_window"],
                        "fresh_intraday_allowed": row["fresh_intraday_allowed"],
                        "closed_market_expected_stale_allowed": row["closed_market_expected_stale_allowed"],
                    }
                elif name == "market_hours_withheld_fire":
                    row, proof, validation = clean_quote_fixture()
                    row["fresh_intraday_allowed"] = False
                    proof["snapshots"][0]["fresh_intraday_allowed"] = False
                    proof["market_session"]["fresh_intraday_allowed"] = False
                else:
                    row, proof, validation = boundary_quote_fixture("post_close")
                    row.update(row_override)
                    proof["snapshots"][0].update(row_override)
                    if name == "tampered_fresh_intraday_allowed":
                        proof["market_session"]["fresh_intraday_allowed"] = row["fresh_intraday_allowed"]
                        self.assertTrue(quote_proof_is_clean(proof, validation, row))
                policy = quote_evaluation_policy(
                    row,
                    0.1,
                    36.0,
                    quote_proof=proof,
                    quote_validation=validation,
                )
                self.assertFalse(policy["fire_eligible"])
                self.assertTrue(policy["stale_or_missing"])
                self.assertEqual(policy["classification"], "stale_or_missing")


if __name__ == "__main__":
    unittest.main()
