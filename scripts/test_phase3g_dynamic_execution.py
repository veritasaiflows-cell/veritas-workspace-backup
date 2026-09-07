"""Offline real-producer Phase 3G CLI coverage; no live SQL or providers."""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import socket
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import alert_level_freshness_controller as alert
import analyst_consensus_refresh as analyst
import phase3g_dynamic_execution as dynamic
import run_alerts_recommendations_chain as chain
from finance_sql_canon_access import (
    DynamicEntitlementScopeError, dynamic_entitlement_payload_fingerprint,
    FinanceSqlCanonAccess, DYNAMIC_ENTITLEMENT_WITNESSES,
)
from phase3f_external_canary_approval import canonical_json_bytes
from test_tier_entitlement_phase3f_canary import FakeScopeClient, make_scope, write_policy, policy_document
from test_alert_level_freshness_controller import clean_quote_fixture


class DynamicExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_policy(self.root)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(chain, "ROOT", self.root))
        self.stack.enter_context(mock.patch.object(chain, "TMP", self.root / "tmp"))
        self.network = self.stack.enter_context(mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")))
        self.subprocess = self.stack.enter_context(mock.patch.object(chain.subprocess, "run", side_effect=AssertionError("subprocess forbidden")))
        self.provider_calls = []
        self.symbols = []
        outer = self

        class Ticker:
            def __init__(self, symbol):
                outer.symbols.append(symbol)

            def get_analyst_price_targets(self):
                outer.provider_calls.append("targets")
                return {"mean": 110, "current": 100}

            def get_recommendations(self):
                outer.provider_calls.append("recommendations")
                return None

        self.stack.enter_context(mock.patch.dict(sys.modules, {"yfinance": types.SimpleNamespace(Ticker=Ticker)}))

    def inputs(self, scope, *, quote=None, validation=None, full=False):
        now = datetime.now(timezone.utc).isoformat()
        ref = {
            "schema": "veritas.phase3f.alert_reference_evidence.v1", "status": "ok",
            "database_path": "state/finance/finance-canon.sqlite", "database_sha256": "a" * 64,
            "scope_fingerprint": scope.fingerprint,
            "scope_payload_sha256": hashlib.sha256(canonical_json_bytes(scope.payload())).hexdigest(),
            "tickers": list(scope.tickers), "reference_levels": {}, "evidence_freshness": {},
            "lineage": {}, "errors": [],
        }
        if full:
            for ticker in scope.tickers:
                ref["reference_levels"][ticker] = {
                    "ticker": ticker, "reference_price_low": 90., "reference_price_high": 110.,
                    "reference_invalidation_level": 80., "reference_confidence": 4,
                    "reference_band_status": "current", "authority_class": "test",
                    "fallback_rule": None,
                }
                ref["evidence_freshness"][ticker] = {
                    "ticker": ticker, "resolution_state": "ok", "required_depth": "test",
                    "card_generated_at_utc": now, "card_missing_or_stale_count": 0,
                    "stale_families": [], "source_confidence_class": "test", "authority_class": "test",
                }
                ref["lineage"][ticker] = {
                    "fields": [], "artifact_checks": [], "level_as_of_utc": now,
                    "source_paths": [], "lineage_validation_ok": True,
                }
        flags = []
        for flag, value in (("--alert-reference-evidence", ref), ("--alert-quote-snapshot", quote or {}),
                            ("--alert-quote-validation", validation or {})):
            path = self.root / (flag[2:] + ".json")
            path.write_bytes(canonical_json_bytes(value))
            flags += [flag, path.name]
        return flags

    def invoke(self, module, scope, extra=(), *, client=None):
        prefix = ["test", "morning"] if module is chain else ["test"]
        client = client or FakeScopeClient(scope)
        output = io.StringIO()
        with mock.patch.object(dynamic, "FinanceSqlCanonAccess", return_value=client), \
             mock.patch.object(sys, "argv", prefix + list(extra)), contextlib.redirect_stdout(output):
            code = module.main()
        return code, json.loads(output.getvalue()), client

    def execute(self, module, scope, extra=()):
        return self.invoke(module, scope, ["--dynamic-entitlement-scope", "--scope-origin",
                                         "phase3f_dynamic_entitlement", "--write", *extra])

    def test_real_chain_growth_missing_rows_remain_enrolled(self):
        for count in (33, 64, 128):
            with self.subTest(count=count):
                scope = make_scope(count)
                # Cumulative real reservation is tested separately below.
                ledger = self.root / "state/dynamic-entitlement-provider-call-ledger.json"
                if ledger.exists():
                    # Local fixture reset, never a production ledger.
                    ledger.unlink()
                before = len(self.provider_calls)
                code, result, client = self.execute(chain, scope, self.inputs(scope))
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "completed_with_visible_debt")
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(len(self.provider_calls) - before, count * 2)
                components = result["component_results"]
                self.assertEqual(set(components["analyst_consensus"]["tickers"]), set(scope.tickers))
                rows = components["alert_level_freshness"]["rows"]
                self.assertEqual({r["ticker"] for r in rows}, set(scope.tickers))
                self.assertTrue(all(r["alert_state"] == "freshness_decay" for r in rows))
                self.assertFalse((self.root / "tmp/alert-level-freshness-controller.json").exists())
                self.assertTrue(list((self.root / chain.PHASE3F_POLICY_RUN_ROOT).glob("*.canary_proof.json")))
        self.network.assert_not_called()
        self.subprocess.assert_not_called()

    def test_standalone_consumers_really_execute(self):
        scope = make_scope()
        for module in (analyst, alert):
            code, result, client = self.execute(module, scope, self.inputs(scope) if module is alert else [])
            self.assertEqual(code, 1)  # missing evidence is explicitly not green
            self.assertEqual(len(client.calls), 1)
            self.assertTrue(result["component_results"])
            self.assertEqual(result["guarded_sql_scope_reads"], 1)
        self.assertEqual(len(self.provider_calls), 4)

    def test_overflow_retains_all_members_without_calls(self):
        scope = make_scope(129, overflow=True)
        code, result, client = self.execute(analyst, scope)
        self.assertEqual(code, 1)
        self.assertEqual(result["scope"]["count"], 129)
        files = list((self.root / chain.PHASE3F_POLICY_RUN_ROOT).glob("overflow-*.json"))
        self.assertEqual(len(json.loads(files[0].read_text())["members"]), 129)
        self.assertEqual(self.provider_calls, [])
        self.assertEqual(len(client.calls), 1)

    def test_preview_and_dry_run_inert(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        for module in (chain, analyst, alert):
            for flags in (["--dynamic-entitlement-preview"], ["--dynamic-entitlement-scope", "--dry-run"]):
                code, result, client = self.invoke(module, make_scope(64), flags)
                self.assertEqual(code, 0)
                self.assertEqual(result["scope"]["count"], 64)
                self.assertEqual(len(client.calls), 1)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertFalse(self.provider_calls)

    def test_contradictions_do_no_work(self):
        for module, extra in ((chain, ["--send"]), (alert, ["--out", "state/evil.json"]),
                              (analyst, ["--tickers", "AAA"]), (analyst, ["--output", "state/evil.json"]),
                              (analyst, ["--merge-existing"]), (chain, ["--timeout-seconds", "999"]),
                              (chain, ["--dynamic-entitlement-preview"]), (analyst, ["--dry-run"])):
            code, result, client = self.execute(module, make_scope(), extra)
            self.assertEqual(code, 1)
            self.assertEqual(client.calls, [])
        self.assertFalse(self.provider_calls)

    def test_policy_malformed_and_future_do_no_work(self):
        for mutation in (lambda d: d.update(enabled=False),
                         lambda d: d.update(effective_at_utc="2099-01-01T00:00:00Z"),
                         lambda d: d.update(allowed_providers=[])):
            doc = policy_document()
            mutation(doc)
            write_policy(self.root, doc)
            code, _, client = self.execute(analyst, make_scope())
            self.assertEqual(code, 1)
            self.assertEqual(client.calls, [])
        self.assertFalse(self.provider_calls)

    def test_sql_tier_conflict_and_fingerprint_fail_closed(self):
        for error in ("guarded_sql_scope_tier_conflict", "guarded_sql_scope_alias_conflict", "SQL failed"):
            client = mock.Mock()
            client.dynamic_entitlement_scope.side_effect = DynamicEntitlementScopeError(error)
            code, result, _ = self.invoke(analyst, make_scope(), ["--dynamic-entitlement-scope",
                "--scope-origin", "phase3f_dynamic_entitlement", "--write"], client=client)
            self.assertEqual(code, 1)
        scope = dataclasses.replace(make_scope(), fingerprint="0" * 64)
        self.assertEqual(self.execute(analyst, scope)[0], 1)
        self.assertFalse(self.provider_calls)

    def test_mixed_eligibility_scope_reaches_evidence_with_claim_debt(self):
        rows = {}
        for ticker, tier, eligible in (("AAA", "A", True), ("BBB", "B", False)):
            sql_tier, coverage = DYNAMIC_ENTITLEMENT_WITNESSES[tier]
            rows[ticker] = types.SimpleNamespace(ticker=ticker, active=True, tier=tier,
                sql_tier=sql_tier, coverage_obligation_tier=coverage, yfinance_symbol=ticker,
                decision_grade_eligible=eligible)
        real_client = FinanceSqlCanonAccess()
        with mock.patch.object(real_client, "universe_memberships", return_value=rows):
            scope = real_client.dynamic_entitlement_scope(
                envelope_name="standing_provider_policy", envelope_count=128)
        self.assertEqual(scope.integrity_breaches, ())
        self.assertEqual(scope.eligibility_debt, ("BBB",))
        _, quote, validation = clean_quote_fixture()
        now = datetime.now(timezone.utc).isoformat()
        quote["symbols_requested"] = ["AAA", "BBB"]
        quote["symbols_observed"] = ["AAA", "BBB"]
        first = dict(quote["snapshots"][0])
        first.update(symbol="AAA", price=100, source_timestamp_utc=now)
        second = dict(quote["snapshots"][0])
        second.update(symbol="BBB", price=100, source_timestamp_utc=now)
        quote["snapshots"] = [first, second]
        flags = ["--dynamic-entitlement-scope", "--scope-origin",
                 "phase3f_dynamic_entitlement", "--write",
                 *self.inputs(scope, quote=quote, validation=validation, full=True)]
        with mock.patch.object(real_client, "universe_memberships", return_value=rows) as read:
            code, result, _ = self.invoke(chain, scope, flags, client=real_client)
            self.assertEqual(read.call_count, 1)
        self.assertEqual(result["guarded_sql_scope_reads"], 1)
        self.assertEqual(result["dynamic_scope"]["eligibility_debt"], ["BBB"])
        self.assertEqual(result["dynamic_scope"]["integrity_breaches"], [])
        # Every member reaches evidence work: analyst provider calls for both.
        self.assertEqual(len(self.provider_calls), 4)
        analyst_result = result["component_results"]["analyst_consensus"]
        self.assertEqual(set(analyst_result["tickers"]), {"AAA", "BBB"})
        self.assertEqual(
            analyst_result["dynamic_entitlement"]["decision_grade_debt"], ["BBB"])
        # False eligibility stays decision/band-claim blocked with claim debt.
        alert_rows = {row["ticker"]: row
                      for row in result["component_results"]["alert_level_freshness"]["rows"]}
        self.assertEqual(set(alert_rows), {"AAA", "BBB"})
        self.assertTrue(alert_rows["AAA"]["alert_fire_eligible"])
        self.assertFalse(alert_rows["BBB"]["alert_fire_eligible"])
        self.assertEqual(alert_rows["BBB"]["alert_state"], "freshness_decay")
        self.assertEqual(
            result["component_results"]["alert_level_freshness"]["dynamic_entitlement"]["decision_grade_debt"],
            ["BBB"],
        )
        self.assertEqual(code, 1)
        self.assertIn(result["status"], ("completed_with_visible_debt",))
        self.network.assert_not_called()
        self.subprocess.assert_not_called()

    def test_budget_exhaustion_has_no_extra_calls(self):
        scope = make_scope(128)
        self.execute(analyst, scope)
        self.assertEqual(len(self.provider_calls), 256)
        code, result, _ = self.execute(analyst, scope)
        self.assertEqual(code, 1)
        self.assertIn("budget", result["error"])
        self.assertEqual(len(self.provider_calls), 256)

    def test_real_attempt_and_duration_guards_persist(self):
        doc = policy_document()
        doc["envelope"]["max_attempts_per_scope_member"] = 1
        write_policy(self.root, doc)
        code, result, _ = self.execute(analyst, make_scope())
        self.assertEqual(code, 1)
        self.assertEqual(len(self.provider_calls), 2)
        self.assertIn("budget", result["error"])
        original = analyst.Phase3FAnalystProviderObserver.before_construction

        def expired(observer):
            observer.started_monotonic -= 901
            original(observer)

        with mock.patch.object(analyst.Phase3FAnalystProviderObserver, "before_construction", expired):
            code, result, _ = self.execute(analyst, make_scope())
        self.assertEqual(code, 1)
        self.assertIn("duration", result["error"])
        self.assertEqual(len(self.provider_calls), 2)

    def test_real_sql_resolver_single_read_and_tier_conflict(self):
        scope = make_scope(33)
        rows = {}
        for ticker, member in scope.memberships.items():
            sql_tier, coverage = DYNAMIC_ENTITLEMENT_WITNESSES[member.tier]
            rows[ticker] = types.SimpleNamespace(ticker=ticker, active=True, tier=member.tier,
                sql_tier=sql_tier, coverage_obligation_tier=coverage, yfinance_symbol=ticker,
                decision_grade_eligible=True)
        client = FinanceSqlCanonAccess()
        with mock.patch.object(client, "universe_memberships", return_value=rows) as read:
            code, result, _ = self.invoke(analyst, scope, ["--dynamic-entitlement-scope",
                "--scope-origin", "phase3f_dynamic_entitlement", "--write"], client=client)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(result["dynamic_scope"]["count"], 33)
            rows[scope.tickers[0]].sql_tier = "WRONG"
            before = len(self.provider_calls)
            code, result, _ = self.invoke(analyst, scope, ["--dynamic-entitlement-scope",
                "--scope-origin", "phase3f_dynamic_entitlement", "--write"], client=client)
            self.assertEqual(code, 1)
            self.assertIn("tier_conflict", result["error"])
            self.assertEqual(len(self.provider_calls), before)

    def test_stale_and_future_quotes_never_green_real_alert_producer(self):
        scope = make_scope()
        for hours in (-1, 100):
            _, quote, validation = clean_quote_fixture()
            quote["symbols_requested"] = ["AAA"]
            quote["symbols_observed"] = ["AAA"]
            quote["snapshots"][0].update(symbol="AAA", price=100,
                source_timestamp_utc=(datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat())
            code, result, _ = self.execute(alert, scope, self.inputs(scope, quote=quote, validation=validation, full=True))
            self.assertEqual(code, 1)
            rows = result["component_results"]["alert_level_freshness"]["rows"]
            self.assertTrue(all(r["alert_state"] == "freshness_decay" for r in rows))
            self.assertTrue(all(not r["alert_fire_eligible"] for r in rows))

    def test_run_id_path_escape_rejected(self):
        code, result, _ = self.execute(analyst, make_scope(), ["--dynamic-run-id", "../../state/evil"])
        self.assertEqual(code, 1)
        self.assertFalse(self.provider_calls)
        self.assertFalse((self.root / "state/evil").exists())

    def test_aliases_preserved_by_real_producers(self):
        scope = make_scope()
        row = scope.memberships.pop("AAA")
        row.ticker = "BRK.B"
        members = dict(sorted({**scope.memberships, "BRK.B": row}.items()))
        scope = dataclasses.replace(scope, memberships=members, identities=members,
                                    aliases={"BBB": "BBB", "BRK.B": "BRK.B", "BRK-B": "BRK.B"})
        scope = dataclasses.replace(scope, fingerprint=dynamic_entitlement_payload_fingerprint(scope.payload()))
        _, quote, validation = clean_quote_fixture()
        quote["symbols_requested"] = ["BRK-B"]
        quote["symbols_observed"] = ["BRK-B"]
        quote["snapshots"][0].update(symbol="BRK-B", price=100,
            source_timestamp_utc=datetime.now(timezone.utc).isoformat())
        code, result, _ = self.execute(chain, scope, self.inputs(scope, quote=quote, validation=validation, full=True))
        self.assertIn("BRK-B", self.symbols)
        self.assertEqual(result["aliases"]["BRK-B"], "BRK.B")
        rows = {r["ticker"]: r for r in result["component_results"]["alert_level_freshness"]["rows"]}
        self.assertEqual(rows["BRK.B"]["alert_state"], "band_entry")
        self.assertFalse(rows["BBB"]["alert_fire_eligible"])

    def test_missing_reference_with_fresh_quote_cannot_fire(self):
        scope = make_scope()
        _, quote, validation = clean_quote_fixture()
        quote["symbols_requested"] = ["AAA"]
        quote["symbols_observed"] = ["AAA"]
        quote["snapshots"][0].update(symbol="AAA", price=100,
            source_timestamp_utc=datetime.now(timezone.utc).isoformat())
        _, result, _ = self.execute(alert, scope, self.inputs(scope, quote=quote, validation=validation))
        self.assertTrue(all(not row["alert_fire_eligible"] for row in result["component_results"]["alert_level_freshness"]["rows"]))

    def test_reference_fingerprint_tamper_prevents_provider_work(self):
        scope = make_scope()
        flags = self.inputs(scope)
        path = self.root / "alert-reference-evidence.json"
        payload = json.loads(path.read_bytes())
        payload["scope_fingerprint"] = "0" * 64
        path.write_bytes(canonical_json_bytes(payload))
        code, result, _ = self.execute(chain, scope, flags)
        self.assertEqual(code, 1)
        self.assertFalse(self.provider_calls)

    def test_input_escape_rejected_before_sql(self):
        scope = make_scope()
        flags = self.inputs(scope)
        flags[1] = "../outside.json"
        code, result, client = self.execute(alert, scope, flags)
        self.assertEqual(code, 1)
        self.assertEqual(client.calls, [])
        self.assertFalse(self.provider_calls)

    def test_no_flag_legacy_alert_path_unchanged(self):
        payload = {"status": "ok", "summary": {"ticker_count": 18, "alert_state_counts": {}}}
        with mock.patch.object(alert, "build_payload", return_value=payload) as build:
            code, _, client = self.invoke(alert, make_scope())
        self.assertEqual(code, 0)
        self.assertEqual(client.calls, [])
        self.assertEqual(tuple(build.call_args.kwargs["tickers"]), alert.TRACKED_TICKERS)


if __name__ == "__main__":
    unittest.main()
