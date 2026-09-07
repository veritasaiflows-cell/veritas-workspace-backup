from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import analyst_consensus_refresh as analyst
import phase3g_dynamic_execution as phase3g_adapter
from finance_sql_canon_access import DynamicEntitlementScopeError, dynamic_entitlement_payload_fingerprint


class FakeDynamicScope:
    source = "guarded_sql:universe_membership.tier"
    tickers = ("AAA", "BBB")
    aliases = {"AAA": "AAA", "BBB": "BBB", "BB-B": "BBB", "BB.B": "BBB"}

    def __init__(self) -> None:
        self.fingerprint = dynamic_entitlement_payload_fingerprint({
            "members": [
                {"ticker": "AAA", "tier": "A", "decision_grade_eligible": True},
                {"ticker": "BBB", "tier": "B", "decision_grade_eligible": True},
            ],
        })
        self.memberships = ["AAA", "BBB"]
        self.overflow_tickers: list[str] = []
        self.integrity_breaches: list[object] = []

    def payload(self) -> dict:
        return {
            "source": "guarded_sql:universe_membership.tier",
            "members": [
                {"ticker": "AAA", "tier": "A", "decision_grade_eligible": True},
                {"ticker": "BBB", "tier": "B", "decision_grade_eligible": True},
            ],
            "fingerprint": self.fingerprint,
            "count": 2,
            "tier_breakdown": {"A": 1, "B": 1},
            "integrity_breaches": [],
            "envelope_name": "test",
            "envelope_count": 2,
            "overflow_tickers": [],
            "overflow_count": 0,
        }


class FakeDynamicClient:
    def __init__(self) -> None:
        self.scope = FakeDynamicScope()
        self.calls = 0

    def dynamic_entitlement_scope(self, *args: object, **kwargs: object) -> FakeDynamicScope:
        self.calls += 1
        return self.scope


class AnalystDynamicEntitlementScopeTests(unittest.TestCase):
    def test_full_dynamic_scope_exact_reordered_aliased_and_superset_fail_closed(self) -> None:
        for tickers in (
            ["AAA", "BBB"],
            ["BBB", "AAA"],
            ["AAA", "BB-B"],
            ["AAA", "BBB", "OTHER"],
        ):
            with self.subTest(tickers=tickers):
                with self.assertRaisesRegex(DynamicEntitlementScopeError, "dynamic_entitlement_scope_requires_gate"):
                    analyst.enforce_explicit_ticker_boundary(tickers, FakeDynamicClient())

    def test_one_ticker_ad_hoc_request_remains_compatible(self) -> None:
        self.assertEqual(analyst.enforce_explicit_ticker_boundary(["BB-B"], FakeDynamicClient()), ["BBB"])

    def test_preview_and_gate_denial_never_fetch_or_write(self) -> None:
        # Valid preview-only is inert: exactly one adapter scope read, exit 0,
        # and positively zero fetch/build/write work.
        client = FakeDynamicClient()
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=client),
            mock.patch.object(analyst, "build_artifact") as build_artifact,
            mock.patch.object(analyst, "fetch_ticker") as fetch_ticker,
            mock.patch.object(Path, "write_text") as write_text,
            mock.patch.object(sys, "argv", ["analyst", "--dynamic-entitlement-preview"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(analyst.main(), 0)
            self.assertEqual(client.calls, 1)
            build_artifact.assert_not_called()
            fetch_ticker.assert_not_called()
            write_text.assert_not_called()
        planned = json.loads(stdout.getvalue())
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(planned["provider_calls"], 0)
        self.assertEqual(planned["output_writes"], 0)
        # Contradictory preview+write is rejected early: exit 1 with zero
        # scope/SQL reads and zero fetch/build/write work.
        client = FakeDynamicClient()
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=client),
            mock.patch.object(analyst, "build_artifact") as build_artifact,
            mock.patch.object(analyst, "fetch_ticker") as fetch_ticker,
            mock.patch.object(Path, "write_text") as write_text,
            mock.patch.object(sys, "argv", ["analyst", "--dynamic-entitlement-preview", "--write"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(analyst.main(), 1)
            self.assertEqual(client.calls, 0)
            build_artifact.assert_not_called()
            fetch_ticker.assert_not_called()
            write_text.assert_not_called()
        denied = json.loads(stdout.getvalue())
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"], "dynamic_incompatible_cli_options")
        # Scope+write with a non-policy origin is rejected before any
        # scope/SQL read and performs zero fetch/build/write work.
        client = FakeDynamicClient()
        stdout = io.StringIO()
        with (
            mock.patch.object(phase3g_adapter, "FinanceSqlCanonAccess", return_value=client),
            mock.patch.object(analyst, "build_artifact") as build_artifact,
            mock.patch.object(analyst, "fetch_ticker") as fetch_ticker,
            mock.patch.object(Path, "write_text") as write_text,
            mock.patch.object(sys, "argv", ["analyst", "--dynamic-entitlement-scope", "--write"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(analyst.main(), 1)
            self.assertEqual(client.calls, 0)
            build_artifact.assert_not_called()
            fetch_ticker.assert_not_called()
            write_text.assert_not_called()
        denied = json.loads(stdout.getvalue())
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"], "dynamic_execution_requires_write_and_policy_origin")

    def test_full_scope_argument_is_stopped_before_fetch_but_one_ticker_stays_ad_hoc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "analyst.json"
            client = FakeDynamicClient()
            with (
                mock.patch.object(analyst, "FinanceSqlCanonAccess", return_value=client),
                mock.patch.object(analyst, "build_artifact") as build_artifact,
                mock.patch.object(sys, "argv", ["analyst", "--output", str(output), "--tickers", "AAA", "BBB"]),
            ):
                self.assertEqual(analyst.main(), 1)
                build_artifact.assert_not_called()
            client = FakeDynamicClient()
            artifact = {"status": "ok", "consumer_posture": "quarantined", "tickers": {}}
            with (
                mock.patch.object(analyst, "FinanceSqlCanonAccess", return_value=client),
                mock.patch.object(analyst, "build_artifact", return_value=artifact) as build_artifact,
                mock.patch.object(sys, "argv", ["analyst", "--output", str(output), "--tickers", "AAA"]),
            ):
                self.assertEqual(analyst.main(), 0)
                build_artifact.assert_called_once_with(["AAA"])


if __name__ == "__main__":
    unittest.main()
