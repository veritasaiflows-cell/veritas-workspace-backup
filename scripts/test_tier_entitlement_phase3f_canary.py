#!/usr/bin/env python3
"""Fail-closed, ordering, receipt, child, and boundary tests for the Phase 3F policy gate.

The per-run signed approval record was retired on 2026-09-02 by owner direction.
Authority now comes from the standing owner-approved provider policy, so these
tests assert policy admission, daily-budget accounting, sealed capability
handoff, one-shot consumption, child confinement, and authority boundaries.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import alert_level_freshness_controller as alert
import analyst_consensus_refresh as analyst
import dynamic_entitlement_provider_policy as policy_module
import phase3f_external_canary_approval as approval
import run_alerts_recommendations_chain as chain
from dynamic_entitlement_provider_policy import (
    ProviderPolicyError,
    budget_day_key,
    load_provider_policy,
    reserve_provider_calls,
    settle_provider_calls,
)
from finance_sql_canon_access import (
    DynamicEntitlementExternalGateError,
    DynamicEntitlementScope,
    dynamic_entitlement_payload_fingerprint,
    require_dynamic_entitlement_external_gate,
)


NOW = datetime(2026, 9, 2, 5, 30, 0, tzinfo=timezone.utc)
RUN_ROOT = "tmp/phase3f-policy-runs"
POLICY_RELPATH = "state/dynamic-entitlement-provider-policy.json"
LEDGER_RELPATH = "state/dynamic-entitlement-provider-call-ledger.json"
WORKSPACE = Path(__file__).resolve().parent.parent


def canonical(value: object) -> bytes:
    return approval.canonical_json_bytes(value)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_scope(
    count: int = 2,
    *,
    overflow: bool = False,
    envelope_count: int = 128,
    envelope_name: str = "standing_provider_policy",
    source: str = "guarded_sql:universe_membership.tier",
    breaches: tuple[str, ...] = (),
) -> DynamicEntitlementScope:
    if count == 2:
        tickers = ["AAA", "BBB"]
        tiers = {"AAA": "A", "BBB": "B"}
    else:
        tickers = [f"T{index:03d}" for index in range(count)]
        tiers = {
            ticker: ("A" if index < count // 2 else "B")
            for index, ticker in enumerate(tickers)
        }
    rows = {
        ticker: SimpleNamespace(
            ticker=ticker,
            tier=tiers[ticker],
            decision_grade_eligible=True,
        )
        for ticker in tickers
    }
    members = [
        {
            "ticker": ticker,
            "tier": tiers[ticker],
            "decision_grade_eligible": True,
        }
        for ticker in tickers
    ]
    fingerprint = dynamic_entitlement_payload_fingerprint({"members": members})
    breakdown = {
        "A": sum(1 for tier in tiers.values() if tier == "A"),
        "B": sum(1 for tier in tiers.values() if tier == "B"),
    }
    return DynamicEntitlementScope(
        source=source,
        memberships=rows,
        identities=dict(rows),
        aliases={ticker: ticker for ticker in tickers},
        fingerprint=fingerprint,
        tier_breakdown=breakdown,
        integrity_breaches=breaches,
        envelope_name=envelope_name,
        envelope_count=envelope_count,
        overflow_tickers=tuple(tickers[envelope_count:]) if overflow else (),
    )


def policy_document(**overrides: object) -> dict[str, object]:
    document = {
        "schema": policy_module.POLICY_SCHEMA,
        "effective_at_utc": "2026-09-02T22:20:00Z",
        "approved_by": "Randall",
        "approved_at_local": "2026-09-02 15:17 America/Phoenix",
        "enabled": True,
        "purpose": "test fixture",
        "allowed_components": ["analyst_consensus", "alert_level_freshness"],
        "allowed_providers": ["yfinance", "alpaca_market_data"],
        "envelope": {
            "max_scope_count": 128,
            "max_attempts_per_scope_member": 2,
            "max_run_duration_seconds": 900,
            "max_retries_per_component": 0,
        },
        "daily_budget": {
            "max_daily_provider_calls": 400,
            "timezone": "America/Phoenix",
            "ledger_path": LEDGER_RELPATH,
            "exhausted_behavior": "fail_closed_zero_provider_calls",
        },
        "scope_source": {
            "authority": "guarded_sql_dynamic_entitlement_scope",
            "truncation_allowed": False,
            "overflow_behavior": "fail_closed_zero_provider_calls_with_member_enumerating_debt_artifact",
        },
        "authority_boundary": {
            "provider_reads_allowed": True,
            "guarded_sql_tier_or_membership_writes_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "recommendation_generation_or_publication_allowed": False,
            "cron_schedule_mutation_allowed": False,
            "config_auth_runtime_mutation_allowed": False,
            "dependency_install_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "capital_deployment_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
        "review": {
            "review_by_utc": "2026-12-02T00:00:00Z",
            "review_trigger": "scheduled",
            "expiry_behavior": "advisory_warning_not_hard_stop",
        },
    }
    document.update(overrides)
    return document


def write_policy(root: Path, document: dict[str, object] | None = None) -> Path:
    path = root / POLICY_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = policy_document() if document is None else document
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_policy(root: Path, document: dict[str, object] | None = None):
    write_policy(root, document)
    return load_provider_policy(root)


def mint(
    root: Path,
    *,
    scope: DynamicEntitlementScope | None = None,
    components: tuple[str, ...] = ("alert_level_freshness", "analyst_consensus"),
    run_id: str = "policy-test-run",
    document: dict[str, object] | None = None,
    input_hashes: dict[str, str] | None = None,
    now_utc: datetime = NOW,
    environment: str = approval.PRODUCTION_ENVIRONMENT,
) -> approval.Phase3FCanaryAuthorization:
    resolved = load_policy(root, document)
    return approval.authorize_from_policy(
        resolved,
        scope or make_scope(),
        components=components,
        run_id=run_id,
        run_root=RUN_ROOT,
        workspace_root=root,
        input_hashes=input_hashes,
        now_utc=now_utc,
        environment=environment,
    )


class FakeScopeClient:
    """Records the envelope the caller asks for and returns a fixed scope."""

    def __init__(self, scope: DynamicEntitlementScope) -> None:
        self.scope = scope
        self.calls: list[tuple[str, int]] = []

    def dynamic_entitlement_scope(
        self, *, envelope_name: str, envelope_count: int
    ) -> DynamicEntitlementScope:
        self.calls.append((envelope_name, envelope_count))
        return self.scope


def quote_documents(tickers: tuple[str, ...], *, generated: str) -> tuple[bytes, bytes]:
    snapshot = {
        "generated_at_utc": generated,
        "quotes": [
            {
                "ticker": ticker,
                "price": 100.0,
                "as_of_utc": generated,
                "source": "test",
            }
            for ticker in tickers
        ],
    }
    validation = {
        "generated_at_utc": generated,
        "status": "clean",
        "conflicts": [],
        "rows": [{"ticker": ticker, "status": "clean"} for ticker in tickers],
    }
    return canonical(snapshot), canonical(validation)


def clean_lineage(ticker: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "authority_class": "owner_approved",
        "source_status": "clean",
        "evidence_sha256": sha_bytes(ticker.encode("utf-8")),
    }


def reference_evidence_document(tickers: tuple[str, ...], *, generated: str) -> bytes:
    return canonical(
        {
            "generated_at_utc": generated,
            "levels": [
                {
                    "ticker": ticker,
                    "reference_price_low": 90.0,
                    "reference_price_high": 110.0,
                    "reference_invalidation_level": 80.0,
                    "reference_confidence": 3,
                    "reference_band_status": "active",
                    "authority_class": "owner_approved",
                }
                for ticker in tickers
            ],
            "lineage": [clean_lineage(ticker) for ticker in tickers],
        }
    )


def fake_provider_module() -> types.ModuleType:
    module = types.ModuleType("fake_yfinance")
    module.__phase3f_test_fixture__ = True

    class Ticker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def get_info(self) -> dict[str, object]:
            return {}

    module.Ticker = Ticker
    return module


# ---------------------------------------------------------------------------
# Policy document validation
# ---------------------------------------------------------------------------


class ProviderPolicyDocumentTests(unittest.TestCase):
    def test_live_policy_matches_the_owner_approved_values(self) -> None:
        live = load_provider_policy(WORKSPACE)
        self.assertEqual(live.allowed_components, ("analyst_consensus", "alert_level_freshness"))
        self.assertEqual(live.allowed_providers, ("yfinance", "alpaca_market_data"))
        self.assertEqual(live.max_scope_count, 128)
        self.assertEqual(live.max_attempts_per_scope_member, 2)
        self.assertEqual(live.max_run_duration_seconds, 900)
        self.assertEqual(live.max_daily_provider_calls, 400)
        self.assertEqual(live.max_retries_per_component, 0)
        self.assertEqual(live.ledger_path, (WORKSPACE / LEDGER_RELPATH).resolve())

    def test_missing_policy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProviderPolicyError) as caught:
                load_provider_policy(Path(directory))
        self.assertEqual(str(caught.exception), "provider_policy_missing")

    def test_disabled_policy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProviderPolicyError) as caught:
                load_policy(Path(directory), policy_document(enabled=False))
        self.assertEqual(str(caught.exception), "provider_policy_disabled")

    def test_unknown_field_at_every_nesting_level_fails_closed(self) -> None:
        cases = [
            ((), "unexpected", "provider_policy_unknown_field"),
            (("envelope",), "max_scope_counts", "provider_policy_envelope_invalid"),
            (("daily_budget",), "max_daily_calls", "provider_policy_daily_budget_invalid"),
            (("scope_source",), "truncation", "provider_policy_scope_source_invalid"),
            (
                ("authority_boundary",),
                "extra_grant",
                "provider_policy_authority_boundary_invalid",
            ),
            (("review",), "review_by", "provider_policy_review_invalid"),
        ]
        for path, key, code in cases:
            with self.subTest(path=path, key=key), tempfile.TemporaryDirectory() as directory:
                document = policy_document()
                target = document
                for part in path:
                    target = target[part]
                target[key] = False
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), document)
                self.assertEqual(str(caught.exception), code)

    def test_every_required_false_boundary_must_be_literal_false(self) -> None:
        for key in policy_module._REQUIRED_FALSE_BOUNDARIES:
            for value in (True, "false", 0, None):
                with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                    document = policy_document()
                    document["authority_boundary"][key] = value
                    with self.assertRaises(ProviderPolicyError) as caught:
                        load_policy(Path(directory), document)
                    self.assertEqual(
                        str(caught.exception), "provider_policy_authority_boundary_invalid"
                    )

    def test_provider_reads_must_be_explicitly_true(self) -> None:
        for value in (False, "true", 1, None):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                document = policy_document()
                document["authority_boundary"]["provider_reads_allowed"] = value
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), document)
                self.assertEqual(
                    str(caught.exception), "provider_policy_provider_reads_not_allowed"
                )

    def test_envelope_bounds_reject_both_directions_and_non_integers(self) -> None:
        cases = [
            ("max_scope_count", 0),
            ("max_scope_count", policy_module.ABSOLUTE_MAX_SCOPE_COUNT + 1),
            ("max_scope_count", True),
            ("max_scope_count", 32.0),
            ("max_attempts_per_scope_member", 0),
            (
                "max_attempts_per_scope_member",
                policy_module.ABSOLUTE_MAX_ATTEMPTS_PER_MEMBER + 1,
            ),
            ("max_run_duration_seconds", 0),
            (
                "max_run_duration_seconds",
                policy_module.ABSOLUTE_MAX_RUN_DURATION_SECONDS + 1,
            ),
            ("max_retries_per_component", -1),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                document = policy_document()
                document["envelope"][key] = value
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), document)
                self.assertEqual(str(caught.exception), "provider_policy_envelope_invalid")

    def test_absolute_ceiling_sits_above_the_owner_knob(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = policy_document()
            document["envelope"]["max_scope_count"] = policy_module.ABSOLUTE_MAX_SCOPE_COUNT
            resolved = load_policy(Path(directory), document)
        self.assertEqual(resolved.max_scope_count, policy_module.ABSOLUTE_MAX_SCOPE_COUNT)
        self.assertGreater(policy_module.ABSOLUTE_MAX_SCOPE_COUNT, 128)

    def test_daily_budget_bounds_and_exhausted_behavior(self) -> None:
        cases = [
            ("max_daily_provider_calls", 0),
            (
                "max_daily_provider_calls",
                policy_module.ABSOLUTE_MAX_DAILY_PROVIDER_CALLS + 1,
            ),
            ("max_daily_provider_calls", "400"),
            ("exhausted_behavior", "warn_and_continue"),
            ("exhausted_behavior", None),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                document = policy_document()
                document["daily_budget"][key] = value
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), document)
                self.assertEqual(str(caught.exception), "provider_policy_daily_budget_invalid")

    def test_ledger_path_cannot_escape_the_workspace(self) -> None:
        for candidate in ("../outside.json", "C:/Windows/temp.json", "/etc/passwd", "", 7):
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as directory:
                document = policy_document()
                document["daily_budget"]["ledger_path"] = candidate
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), document)
                self.assertEqual(str(caught.exception), "provider_policy_daily_budget_invalid")

    def test_scope_source_must_be_guarded_sql_without_truncation(self) -> None:
        cases = [
            ("authority", "analyst_local_tier_sets"),
            ("truncation_allowed", True),
            ("truncation_allowed", "false"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                document = policy_document()
                document["scope_source"][key] = value
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), document)
                self.assertEqual(str(caught.exception), "provider_policy_scope_source_invalid")

    def test_component_and_provider_lists_are_closed_and_deduplicated(self) -> None:
        cases = [
            ("allowed_components", [], "provider_policy_components_invalid"),
            ("allowed_components", ["portfolio_rebalance"], "provider_policy_components_invalid"),
            (
                "allowed_components",
                ["analyst_consensus", "analyst_consensus"],
                "provider_policy_components_invalid",
            ),
            ("allowed_components", "analyst_consensus", "provider_policy_components_invalid"),
            ("allowed_providers", ["alpaca"], "provider_policy_providers_invalid"),
            ("allowed_providers", [], "provider_policy_providers_invalid"),
        ]
        for key, value, code in cases:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ProviderPolicyError) as caught:
                    load_policy(Path(directory), policy_document(**{key: value}))
                self.assertEqual(str(caught.exception), code)

    def test_malformed_or_oversized_policy_bytes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / POLICY_RELPATH
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            with self.assertRaises(ProviderPolicyError) as caught:
                load_provider_policy(root)
            self.assertEqual(str(caught.exception), "provider_policy_bytes_invalid")

            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ProviderPolicyError) as caught:
                load_provider_policy(root)
            self.assertEqual(str(caught.exception), "provider_policy_json_invalid")

            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ProviderPolicyError) as caught:
                load_provider_policy(root)
            self.assertEqual(str(caught.exception), "provider_policy_unknown_field")

            path.write_bytes(b"{" + b" " * (policy_module.MAX_POLICY_BYTES + 8) + b"}")
            with self.assertRaises(ProviderPolicyError) as caught:
                load_provider_policy(root)
            self.assertEqual(str(caught.exception), "provider_policy_bytes_invalid")

    def test_policy_path_outside_the_workspace_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            foreign = Path(outside) / "policy.json"
            foreign.write_text(json.dumps(policy_document()), encoding="utf-8")
            with self.assertRaises(ProviderPolicyError) as caught:
                load_provider_policy(Path(directory), policy_path=foreign)
        self.assertEqual(str(caught.exception), "provider_policy_path_invalid")

    def test_schema_must_match_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProviderPolicyError) as caught:
                load_policy(Path(directory), policy_document(schema="veritas.other.v1"))
        self.assertEqual(str(caught.exception), "provider_policy_schema_invalid")

    def test_admission_helpers_enforce_component_provider_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_policy(Path(directory))
        resolved.require_component("analyst_consensus")
        resolved.require_provider("yfinance")
        resolved.require_scope_within_envelope(128)
        self.assertEqual(resolved.attempt_budget(32), 64)
        with self.assertRaises(ProviderPolicyError) as caught:
            resolved.require_component("portfolio_rebalance")
        self.assertEqual(str(caught.exception), "provider_policy_component_not_allowed")
        with self.assertRaises(ProviderPolicyError) as caught:
            resolved.require_provider("alpaca")
        self.assertEqual(str(caught.exception), "provider_policy_provider_not_allowed")
        with self.assertRaises(ProviderPolicyError) as caught:
            resolved.require_scope_within_envelope(129)
        self.assertEqual(str(caught.exception), "provider_policy_scope_overflow")
        for bad in (0, -1, True, 3.0, "32"):
            with self.subTest(bad=bad), self.assertRaises(ProviderPolicyError) as caught:
                resolved.require_scope_within_envelope(bad)
            self.assertEqual(str(caught.exception), "provider_policy_scope_count_invalid")


# ---------------------------------------------------------------------------
# Daily budget ledger
# ---------------------------------------------------------------------------


class SettledCallCountTests(unittest.TestCase):
    def test_honest_metrics_are_summed(self) -> None:
        metrics = {
            "analyst_consensus": {"provider_method_attempts": 9},
            "alert_level_freshness": {"provider_method_attempts": 4},
        }
        self.assertEqual(chain.settled_call_count(metrics, 64), 13)

    def test_missing_key_consumes_the_whole_reservation(self) -> None:
        metrics = {
            "analyst_consensus": {"status": "completed"},
            "alert_level_freshness": {"provider_method_attempts": 0},
        }
        self.assertEqual(chain.settled_call_count(metrics, 64), 64)

    def test_malformed_counts_consume_the_whole_reservation(self) -> None:
        for value in (None, -1, True, "12", 12.0, [12]):
            with self.subTest(value=value):
                metrics = {"analyst_consensus": {"provider_method_attempts": value}}
                self.assertEqual(chain.settled_call_count(metrics, 64), 64)

    def test_non_dict_row_consumes_the_whole_reservation(self) -> None:
        self.assertEqual(chain.settled_call_count({"analyst_consensus": None}, 64), 64)

    def test_silent_components_cannot_refund_real_spend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document()
            document["daily_budget"]["max_daily_provider_calls"] = 100
            resolved = load_policy(root, document)
            reserve_provider_calls(resolved, 100, run_id="silent-run")
            settled = settle_provider_calls(
                resolved,
                chain.settled_call_count({"analyst_consensus": {}}, 100),
                run_id="silent-run",
            )
            self.assertEqual(settled["remaining_today"], 0)


class DailyBudgetLedgerTests(unittest.TestCase):
    def test_reservations_accumulate_and_then_exhaust(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document()
            document["daily_budget"]["max_daily_provider_calls"] = 100
            resolved = load_policy(root, document)
            first = reserve_provider_calls(resolved, 64, now_utc=NOW, run_id="run-a")
            self.assertEqual(first["reserved_this_run"], 64)
            self.assertEqual(first["reserved_today"], 64)
            self.assertEqual(first["remaining_today"], 36)
            second = reserve_provider_calls(resolved, 36, now_utc=NOW, run_id="run-b")
            self.assertEqual(second["reserved_today"], 100)
            self.assertEqual(second["remaining_today"], 0)
            with self.assertRaises(ProviderPolicyError) as caught:
                reserve_provider_calls(resolved, 1, now_utc=NOW, run_id="run-c")
            self.assertEqual(str(caught.exception), "provider_daily_budget_exhausted")
            ledger = json.loads(resolved.ledger_path.read_text(encoding="utf-8"))
            day = budget_day_key(NOW)
            self.assertEqual(ledger["days"][day]["runs"], 2)
            self.assertEqual(ledger["days"][day]["run_ids"], ["run-a", "run-b"])

    def test_day_key_uses_phoenix_not_utc(self) -> None:
        # 05:30Z on Sep 2 is 22:30 on Sep 1 in Phoenix.  A UTC day key would
        # silently grant a second full budget in the middle of one local day.
        self.assertEqual(budget_day_key(NOW), "2026-09-01")
        self.assertEqual(
            budget_day_key(datetime(2026, 9, 2, 7, 30, tzinfo=timezone.utc)), "2026-09-02"
        )
        with self.assertRaises(ProviderPolicyError) as caught:
            budget_day_key(datetime(2026, 9, 2, 5, 30))
        self.assertEqual(str(caught.exception), "provider_policy_clock_invalid")

    def test_separate_local_days_get_separate_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document()
            document["daily_budget"]["max_daily_provider_calls"] = 64
            resolved = load_policy(root, document)
            reserve_provider_calls(resolved, 64, now_utc=NOW, run_id="run-a")
            later = reserve_provider_calls(
                resolved,
                64,
                now_utc=NOW + timedelta(days=1),
                run_id="run-b",
            )
        self.assertEqual(later["day"], "2026-09-02")
        self.assertEqual(later["reserved_today"], 64)

    def test_corrupt_ledger_fails_closed_instead_of_resetting_the_budget(self) -> None:
        cases = [
            (b"{not json", "provider_call_ledger_json_invalid"),
            (b"[]", "provider_call_ledger_json_invalid"),
            (b'{"schema": "other", "days": {}}', "provider_call_ledger_schema_invalid"),
            (
                json.dumps({"schema": policy_module.LEDGER_SCHEMA, "days": []}).encode(),
                "provider_call_ledger_json_invalid",
            ),
        ]
        for raw, code in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                resolved = load_policy(root)
                resolved.ledger_path.parent.mkdir(parents=True, exist_ok=True)
                resolved.ledger_path.write_bytes(raw)
                with self.assertRaises(ProviderPolicyError) as caught:
                    reserve_provider_calls(resolved, 1, now_utc=NOW, run_id="run-a")
                self.assertEqual(str(caught.exception), code)

    def test_reservation_arguments_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_policy(Path(directory))
            for count in (0, -1, True, 2.5, "64"):
                with self.subTest(count=count), self.assertRaises(ProviderPolicyError) as caught:
                    reserve_provider_calls(resolved, count, now_utc=NOW, run_id="run-a")
                self.assertEqual(str(caught.exception), "provider_call_reservation_invalid")
            for run_id in ("", None, 7):
                with self.subTest(run_id=run_id), self.assertRaises(ProviderPolicyError) as caught:
                    reserve_provider_calls(resolved, 1, now_utc=NOW, run_id=run_id)
                self.assertEqual(str(caught.exception), "provider_call_reservation_invalid")

    def test_settlement_returns_only_the_unused_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document()
            document["daily_budget"]["max_daily_provider_calls"] = 100
            resolved = load_policy(root, document)
            reserve_provider_calls(resolved, 64, now_utc=NOW, run_id="run-a")
            settled = settle_provider_calls(resolved, 9, now_utc=NOW, run_id="run-a")
            self.assertEqual(settled["refunded_calls"], 55)
            self.assertEqual(settled["actual_calls"], 9)
            self.assertEqual(settled["reserved_today"], 9)
            self.assertEqual(settled["remaining_today"], 91)
            self.assertEqual(settled["overrun_attempts"], 0)

    def test_settlement_never_grants_budget_beyond_the_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-a")
            settled = settle_provider_calls(resolved, 40, now_utc=NOW, run_id="run-a")
            self.assertEqual(settled["refunded_calls"], 0)
            self.assertEqual(settled["overrun_attempts"], 30)
            self.assertEqual(settled["reserved_today"], 10)
            ledger = json.loads(resolved.ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["days"][budget_day_key(NOW)]["overrun_attempts"], 30)

    def test_settlement_cannot_be_replayed_to_refund_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            reserve_provider_calls(resolved, 64, now_utc=NOW, run_id="run-a")
            settle_provider_calls(resolved, 0, now_utc=NOW, run_id="run-a")
            for run_id in ("run-a", "never-reserved"):
                with self.subTest(run_id=run_id):
                    with self.assertRaises(ProviderPolicyError) as caught:
                        settle_provider_calls(resolved, 0, now_utc=NOW, run_id=run_id)
                    self.assertEqual(
                        str(caught.exception), "provider_call_settlement_unknown_run"
                    )

    def test_reservation_run_ids_cannot_collide_within_a_day(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            reserve_provider_calls(resolved, 8, now_utc=NOW, run_id="run-a")
            with self.assertRaises(ProviderPolicyError) as caught:
                reserve_provider_calls(resolved, 8, now_utc=NOW, run_id="run-a")
            self.assertEqual(
                str(caught.exception), "provider_call_reservation_duplicate_run_id"
            )

    def test_settlement_arguments_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_policy(Path(directory))
            reserve_provider_calls(resolved, 8, now_utc=NOW, run_id="run-a")
            for actual in (-1, True, 2.5, "8"):
                with self.subTest(actual=actual), self.assertRaises(ProviderPolicyError) as caught:
                    settle_provider_calls(resolved, actual, now_utc=NOW, run_id="run-a")
                self.assertEqual(str(caught.exception), "provider_call_settlement_invalid")

    def test_unsettled_reservation_still_bounds_the_day(self) -> None:
        # A crash between reserve and settle must not hand budget back.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document()
            document["daily_budget"]["max_daily_provider_calls"] = 64
            resolved = load_policy(root, document)
            reserve_provider_calls(resolved, 64, now_utc=NOW, run_id="crashed")
            with self.assertRaises(ProviderPolicyError) as caught:
                reserve_provider_calls(resolved, 1, now_utc=NOW, run_id="run-b")
            self.assertEqual(str(caught.exception), "provider_daily_budget_exhausted")

    def test_ledger_write_leaves_no_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            reserve_provider_calls(resolved, 8, now_utc=NOW, run_id="run-a")
            leftovers = sorted(p.name for p in resolved.ledger_path.parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])


# ---------------------------------------------------------------------------
# External gate admission
# ---------------------------------------------------------------------------


class ExternalGateAdmissionTests(unittest.TestCase):
    def _gate(self, root: Path, scope: DynamicEntitlementScope, **kwargs):
        resolved = kwargs.pop("policy", None) or load_policy(root, kwargs.pop("document", None))
        return require_dynamic_entitlement_external_gate(
            scope,
            scope_origin=kwargs.pop("scope_origin", "phase3f_dynamic_entitlement"),
            workspace_root=root,
            policy=resolved,
        )

    def test_foreign_scope_origin_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                self._gate(root, make_scope(), scope_origin="wf78_tier_mirror")
        self.assertEqual(
            str(caught.exception), "dynamic_entitlement_scope_origin_not_allowed"
        )

    def test_non_guarded_sql_scope_source_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                self._gate(root, make_scope(source="analyst_local:tier_sets"))
        self.assertEqual(
            str(caught.exception), "dynamic_entitlement_scope_source_not_guarded_sql"
        )

    def test_integrity_breaches_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                self._gate(root, make_scope(breaches=("alias_collision",)))
        self.assertEqual(str(caught.exception), "dynamic_entitlement_scope_integrity_breach")

    def test_scope_within_the_policy_envelope_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = self._gate(root, make_scope(64))
        self.assertEqual(resolved.max_scope_count, 128)

    def test_scope_beyond_the_policy_envelope_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document()
            document["envelope"]["max_scope_count"] = 32
            with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                self._gate(root, make_scope(33), document=document)
        self.assertEqual(str(caught.exception), "provider_policy_scope_overflow")

    def test_owner_may_declare_a_narrower_or_wider_envelope(self) -> None:
        # This is the defect the phase removed: a static 32 pin voided the run
        # on the 33rd Tier A/B admission.  The ceiling is now an owner knob.
        for ceiling, count, admitted in ((32, 32, True), (32, 33, False), (256, 200, True)):
            with self.subTest(ceiling=ceiling, count=count), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                document = policy_document()
                document["envelope"]["max_scope_count"] = ceiling
                scope = make_scope(count, envelope_count=ceiling)
                if admitted:
                    self.assertIsNotNone(self._gate(root, scope, document=document))
                else:
                    with self.assertRaises(DynamicEntitlementExternalGateError):
                        self._gate(root, scope, document=document)

    def test_missing_or_disabled_policy_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                require_dynamic_entitlement_external_gate(
                    make_scope(),
                    scope_origin="phase3f_dynamic_entitlement",
                    workspace_root=root,
                )
            self.assertEqual(str(caught.exception), "provider_policy_missing")
            write_policy(root, policy_document(enabled=False))
            with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                require_dynamic_entitlement_external_gate(
                    make_scope(),
                    scope_origin="phase3f_dynamic_entitlement",
                    workspace_root=root,
                )
            self.assertEqual(str(caught.exception), "provider_policy_disabled")

    def test_overflow_debt_enumerates_members_with_zero_provider_calls(self) -> None:
        scope = make_scope(40, envelope_count=32)
        document = policy_document()
        document["envelope"]["max_scope_count"] = 32
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_policy(root, document)
            resolved = load_provider_policy(root)
            debt_path = root / "tmp" / "dynamic-entitlement-scope-overflow-debt.json"
            client = FakeScopeClient(scope)
            with mock.patch.object(chain, "ROOT", root), mock.patch.object(
                chain, "TMP", root / "tmp"
            ), mock.patch.object(chain, "load_provider_policy", lambda *a, **k: resolved):
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    chain.prepare_policy_canary(
                        components=("analyst_consensus",),
                        run_id="policy-overflow",
                        client=client,
                        now_utc=NOW,
                    )
            self.assertEqual(str(caught.exception), "provider_policy_scope_overflow")
            debt = json.loads(debt_path.read_text(encoding="utf-8"))
            self.assertEqual(debt["provider_calls"], 0)
            self.assertEqual(debt["observed_scope_count"], 40)
            self.assertEqual(debt["policy_max_scope_count"], 32)
            self.assertEqual(len(debt["members"]), 40)
            self.assertFalse((root / RUN_ROOT).exists())

    def test_membership_growth_reads_as_growth_not_binding_mismatch(self) -> None:
        scope = make_scope(33)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_policy(root)
            resolved = load_provider_policy(root)
            client = FakeScopeClient(scope)
            with mock.patch.object(chain, "ROOT", root), mock.patch.object(
                chain, "TMP", root / "tmp"
            ), mock.patch.object(chain, "load_provider_policy", lambda *a, **k: resolved):
                _, authorization, reservation = chain.prepare_policy_canary(
                    components=("analyst_consensus",),
                    run_id="policy-growth",
                    client=client,
                    now_utc=NOW,
                )
            self.assertEqual(client.calls, [("standing_provider_policy", 128)])
            self.assertEqual(authorization.scope.count, 33)
            self.assertEqual(reservation["reserved_this_run"], 66)

    def test_provider_allowlist_is_enforced_on_the_real_path(self) -> None:
        # The loader already pins allowed_providers to a code constant, so a
        # denied provider has to be injected past it to prove the dispatch-time
        # check is live rather than decorative.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_policy(root)
            resolved = dataclasses.replace(
                load_provider_policy(root), allowed_providers=("alpaca",)
            )
            client = FakeScopeClient(make_scope())
            with mock.patch.object(chain, "ROOT", root), mock.patch.object(
                chain, "TMP", root / "tmp"
            ), mock.patch.object(chain, "load_provider_policy", lambda *a, **k: resolved):
                with self.assertRaises(ProviderPolicyError) as caught:
                    chain.prepare_policy_canary(
                        components=("analyst_consensus",),
                        run_id="policy-provider-denied",
                        client=client,
                        now_utc=NOW,
                    )
            self.assertEqual(
                str(caught.exception), "provider_policy_provider_not_allowed"
            )
            self.assertFalse((root / RUN_ROOT).exists())

    def test_every_allowed_component_maps_to_a_known_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_policy(Path(directory))
        for component_id in resolved.allowed_components:
            self.assertIn(component_id, chain.COMPONENT_PROVIDERS)

    def test_non_integer_scope_counts_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_policy(Path(directory))
        for bad in (None, "32", 32.0):
            with self.subTest(bad=bad), self.assertRaises(ProviderPolicyError):
                resolved.require_scope_within_envelope(bad)


# ---------------------------------------------------------------------------
# Authorization minting
# ---------------------------------------------------------------------------


class AuthorizationMintingTests(unittest.TestCase):
    def test_envelope_exposes_policy_derived_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory), scope=make_scope(32))
        envelope = authorization.approval.envelope
        self.assertEqual(envelope.name, "standing_provider_policy")
        self.assertEqual(envelope.maximum_scope_count, 128)
        self.assertEqual(envelope.max_duration_seconds, 900)
        self.assertEqual(envelope.method_attempt_limit("analyst_consensus"), 64)
        self.assertEqual(envelope.method_attempt_limit("alert_level_freshness"), 0)
        self.assertEqual(envelope.retry_limit("analyst_consensus"), 0)

    def test_unapproved_and_unknown_components_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = policy_document(allowed_components=["alert_level_freshness"])
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(root, components=("analyst_consensus",), document=document)
            self.assertEqual(str(caught.exception), "phase3f_component_not_approved")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(Path(directory), components=("portfolio_rebalance",))
            self.assertEqual(str(caught.exception), "phase3f_component_unknown")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(Path(directory), components=())
            self.assertEqual(str(caught.exception), "phase3f_component_not_approved")

    def test_integrity_breach_blocks_before_any_receipt_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(root, scope=make_scope(breaches=("tier_witness_conflict",)))
            self.assertEqual(str(caught.exception), "guarded_sql_scope_integrity_breach")
            self.assertFalse((root / RUN_ROOT).exists())

    def test_validity_window_comes_from_the_policy_duration_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
        self.assertEqual(authorization.approval.not_before_utc, NOW)
        self.assertEqual(authorization.approval.expires_at_utc, NOW + timedelta(seconds=900))
        approval.recheck_phase3f_expiry(authorization.approval, now_utc=NOW)
        with self.assertRaises(approval.Phase3FApprovalError) as caught:
            approval.recheck_phase3f_expiry(
                authorization.approval, now_utc=NOW + timedelta(seconds=900)
            )
        self.assertEqual(str(caught.exception), "phase3f_approval_not_current")

    def test_naive_or_offset_clocks_are_refused_on_recheck(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
        for bad in (
            datetime(2026, 9, 2, 5, 31),
            datetime(2026, 9, 1, 22, 31, tzinfo=timezone(timedelta(hours=-7))),
        ):
            with self.subTest(bad=bad), self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.recheck_phase3f_expiry(authorization.approval, now_utc=bad)
            self.assertEqual(str(caught.exception), "phase3f_clock_invalid")

    def test_environment_defaults_to_production_and_rejects_unknown_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
        self.assertEqual(authorization.approval.environment, approval.PRODUCTION_ENVIRONMENT)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(Path(directory), environment="staging")
        self.assertEqual(str(caught.exception), "phase3f_environment_invalid")

    def test_run_identifier_bounds_are_enforced(self) -> None:
        for run_id in ("", "-leading", "has space", "a" * 129, "bad/slash"):
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    mint(Path(directory), run_id=run_id)
                self.assertEqual(str(caught.exception), "phase3f_run_id_invalid")

    def test_canary_root_cannot_escape_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.authorize_from_policy(
                    resolved,
                    make_scope(),
                    components=("analyst_consensus",),
                    run_id="policy-escape",
                    run_root="../outside",
                    workspace_root=root,
                    now_utc=NOW,
                )
        self.assertEqual(str(caught.exception), "phase3f_approved_canary_root_invalid")

    def test_all_output_paths_stay_inside_the_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authorization = mint(root)
            run_directory = (root / RUN_ROOT).resolve()
            names = tuple(name for name, _ in authorization.approval.output_paths)
            self.assertEqual(names, approval.POLICY_RUN_OUTPUT_NAMES)
            for _, path in authorization.approval.output_paths:
                self.assertEqual(path.parent, run_directory)
            self.assertEqual(authorization.receipt_path.parent, run_directory)
        with self.assertRaises(approval.Phase3FApprovalError) as caught:
            authorization.approval.output_path("model_portfolio")
        self.assertEqual(str(caught.exception), "phase3f_output_not_approved")

    def test_policy_provenance_is_recorded_without_becoming_a_source_hash_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authorization = mint(root)
            policy_path = root / POLICY_RELPATH
            self.assertEqual(
                authorization.approval.decision_packet_id,
                f"standing-policy:{policy_path.name}",
            )
            self.assertEqual(
                authorization.approval.decision_packet_sha256,
                sha_bytes(policy_path.read_bytes()),
            )
        self.assertEqual(authorization.approval.source_hashes, ())
        self.assertIsNone(authorization.approval.record_path)


# ---------------------------------------------------------------------------
# One-shot receipts and component claims
# ---------------------------------------------------------------------------


class ReceiptAndClaimOneShotTests(unittest.TestCase):
    def test_receipt_hash_binds_the_written_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            raw = authorization.receipt_path.read_bytes()
        self.assertEqual(sha_bytes(raw), authorization.receipt_sha256)
        receipt = json.loads(raw.decode("utf-8"))
        self.assertEqual(receipt["schema"], approval.RECEIPT_SCHEMA)
        self.assertEqual(receipt["provider_method_attempts"], 0)
        self.assertEqual(receipt["scope_payload_sha256"], authorization.scope.payload_sha256)

    def test_reusing_a_run_identifier_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mint(root, run_id="policy-once")
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(root, run_id="policy-once")
        self.assertEqual(str(caught.exception), "phase3f_one_shot_already_consumed")

    def test_a_zero_byte_receipt_slot_still_counts_as_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            slot = root / RUN_ROOT / "policy-partial.receipt.json"
            slot.parent.mkdir(parents=True, exist_ok=True)
            slot.write_bytes(b"")
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(root, run_id="policy-partial")
        self.assertEqual(str(caught.exception), "phase3f_one_shot_already_consumed")

    def test_concurrent_minting_produces_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            scope = make_scope()
            results: list[object] = []
            lock = threading.Lock()
            barrier = threading.Barrier(6)

            def attempt() -> None:
                barrier.wait()
                try:
                    outcome: object = approval.authorize_from_policy(
                        resolved,
                        scope,
                        components=("analyst_consensus",),
                        run_id="policy-race",
                        run_root=RUN_ROOT,
                        workspace_root=root,
                        now_utc=NOW,
                    )
                except approval.Phase3FApprovalError as exc:
                    outcome = exc
                with lock:
                    results.append(outcome)

            threads = [threading.Thread(target=attempt) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        winners = [r for r in results if isinstance(r, approval.Phase3FCanaryAuthorization)]
        losers = [r for r in results if isinstance(r, approval.Phase3FApprovalError)]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 5)
        self.assertTrue(
            all(str(exc) == "phase3f_one_shot_already_consumed" for exc in losers), losers
        )

    def test_directory_sync_failure_leaves_the_slot_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = load_policy(root)
            with mock.patch.object(
                approval,
                "_fsync_directory_entry",
                side_effect=approval.Phase3FApprovalError("phase3f_directory_sync_failed"),
            ):
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    approval.authorize_from_policy(
                        resolved,
                        make_scope(),
                        components=("analyst_consensus",),
                        run_id="policy-fsync",
                        run_root=RUN_ROOT,
                        workspace_root=root,
                        now_utc=NOW,
                    )
            self.assertEqual(str(caught.exception), "phase3f_directory_sync_failed")
            self.assertTrue((root / RUN_ROOT / "policy-fsync.receipt.json").is_file())
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                mint(root, run_id="policy-fsync")
            self.assertEqual(str(caught.exception), "phase3f_one_shot_already_consumed")

    def test_component_claim_is_one_shot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            claim_path, claim_sha = approval.create_phase3f_component_claim(
                authorization, component_id="analyst_consensus", now_utc=NOW
            )
            self.assertEqual(sha_bytes(claim_path.read_bytes()), claim_sha)
            claim = json.loads(claim_path.read_text(encoding="utf-8"))
            self.assertEqual(claim["schema"], approval.COMPONENT_CLAIM_SCHEMA)
            self.assertEqual(claim["component_id"], "analyst_consensus")
            self.assertEqual(claim["receipt_sha256"], authorization.receipt_sha256)
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.create_phase3f_component_claim(
                    authorization, component_id="analyst_consensus", now_utc=NOW
                )
            self.assertEqual(str(caught.exception), "phase3f_component_already_consumed")
            # A different component still has its own slot.
            approval.create_phase3f_component_claim(
                authorization, component_id="alert_level_freshness", now_utc=NOW
            )

    def test_concurrent_component_claims_produce_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            results: list[object] = []
            lock = threading.Lock()
            barrier = threading.Barrier(6)

            def attempt() -> None:
                barrier.wait()
                try:
                    outcome: object = approval.create_phase3f_component_claim(
                        authorization, component_id="analyst_consensus", now_utc=NOW
                    )
                except approval.Phase3FApprovalError as exc:
                    outcome = exc
                with lock:
                    results.append(outcome)

            threads = [threading.Thread(target=attempt) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        winners = [r for r in results if isinstance(r, tuple)]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(results) - len(winners), 5)

    def test_receipt_drift_or_deletion_makes_the_state_ambiguous(self) -> None:
        for mutate in ("delete", "tamper", "rebind"):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                authorization = mint(Path(directory))
                if mutate == "delete":
                    authorization.receipt_path.unlink()
                elif mutate == "tamper":
                    authorization.receipt_path.write_bytes(b'{"schema": "x"}\n')
                else:
                    receipt = json.loads(authorization.receipt_path.read_text(encoding="utf-8"))
                    receipt["record_id"] = "other-run"
                    authorization.receipt_path.write_bytes(canonical(receipt) + b"\n")
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    approval.require_phase3f_authorization(
                        authorization, component_id="analyst_consensus", now_utc=NOW
                    )
                self.assertEqual(str(caught.exception), "phase3f_receipt_state_ambiguous")


# ---------------------------------------------------------------------------
# Sealed capability objects
# ---------------------------------------------------------------------------


class SealedCapabilityTests(unittest.TestCase):
    def test_forged_authorization_shapes_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
        forgeries = [
            {"approval": authorization.approval, "scope": authorization.scope},
            SimpleNamespace(
                approval=authorization.approval,
                scope=authorization.scope,
                receipt_path=authorization.receipt_path,
                receipt_sha256=authorization.receipt_sha256,
                _authorization_seal=object(),
            ),
            None,
            "authorized",
        ]
        for forged in forgeries:
            with self.subTest(kind=type(forged).__name__):
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    approval.require_phase3f_authorization(
                        forged, component_id="analyst_consensus", now_utc=NOW
                    )
                self.assertEqual(str(caught.exception), "phase3f_parent_authorization_required")

    def test_a_broken_inner_seal_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            broken_approval = copy.replace(
                authorization.approval, _verification_seal=object()
            ) if hasattr(copy, "replace") else None
            if broken_approval is None:
                import dataclasses

                broken_approval = dataclasses.replace(
                    authorization.approval, _verification_seal=object()
                )
            forged = approval.Phase3FCanaryAuthorization(
                approval=broken_approval,
                scope=authorization.scope,
                receipt_path=authorization.receipt_path,
                receipt_sha256=authorization.receipt_sha256,
                _authorization_seal=approval._AUTHORIZATION_SEAL,
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_authorization(
                    forged, component_id="analyst_consensus", now_utc=NOW
                )
        self.assertEqual(str(caught.exception), "phase3f_parent_authorization_required")

    def test_a_component_outside_the_minted_envelope_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory), components=("analyst_consensus",))
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_authorization(
                    authorization, component_id="alert_level_freshness", now_utc=NOW
                )
        self.assertEqual(str(caught.exception), "phase3f_component_not_approved")

    def test_freezing_requires_a_sealed_verified_approval(self) -> None:
        for forged in (None, {"expected_scope": None}, SimpleNamespace(expected_scope=None)):
            with self.subTest(kind=type(forged).__name__):
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    approval.compare_and_freeze_phase3f_scope(forged, make_scope())
                self.assertEqual(str(caught.exception), "phase3f_verified_approval_required")


# ---------------------------------------------------------------------------
# Frozen scope
# ---------------------------------------------------------------------------


class FrozenScopeTests(unittest.TestCase):
    def test_scope_drift_after_minting_is_a_binding_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.compare_and_freeze_phase3f_scope(
                    authorization.approval, make_scope(4)
                )
        self.assertEqual(str(caught.exception), "phase3f_scope_binding_mismatch")

    def test_overflow_is_refused_before_freezing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            overflowing = make_scope(4, overflow=True, envelope_count=2)
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.compare_and_freeze_phase3f_scope(authorization.approval, overflowing)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_overflow")

    def test_tier_breakdown_drift_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            drifted = make_scope()
            object.__setattr__(drifted, "tier_breakdown", {"A": 2, "B": 0})
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.compare_and_freeze_phase3f_scope(authorization.approval, drifted)
        self.assertEqual(str(caught.exception), "phase3f_scope_binding_mismatch")

    def test_verified_tickers_are_exactly_the_frozen_membership(self) -> None:
        for count in (2, 8, 33):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                scope = make_scope(count)
                authorization = mint(Path(directory), scope=scope)
                tickers = approval.verified_scope_tickers(
                    authorization, component_id="analyst_consensus", now_utc=NOW
                )
                self.assertEqual(tickers, tuple(sorted(scope.memberships)))

    def test_tampered_frozen_bytes_fail_the_fingerprint_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            object.__setattr__(
                authorization.scope, "canonical_bytes", b'{"members": [], "count": 0}'
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.verified_scope_tickers(
                    authorization, component_id="analyst_consensus", now_utc=NOW
                )
        self.assertEqual(
            str(caught.exception), "guarded_sql_scope_payload_fingerprint_mismatch"
        )

    def test_children_never_reopen_sql_to_resolve_membership(self) -> None:
        class ForbiddenClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise AssertionError("child opened guarded SQL")

        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            with mock.patch.object(alert, "FinanceSqlCanonAccess", ForbiddenClient), \
                    mock.patch.object(analyst, "FinanceSqlCanonAccess", ForbiddenClient):
                tickers = approval.verified_scope_tickers(
                    authorization, component_id="alert_level_freshness", now_utc=NOW
                )
        self.assertEqual(tickers, ("AAA", "BBB"))


# ---------------------------------------------------------------------------
# Component boundaries
# ---------------------------------------------------------------------------


class ComponentBoundaryTests(unittest.TestCase):
    def test_attempt_and_retry_budgets_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory), scope=make_scope(32))
            approval.require_phase3f_component_budget(
                authorization,
                component_id="analyst_consensus",
                provider_method_attempts=64,
                now_utc=NOW,
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_component_budget(
                    authorization,
                    component_id="analyst_consensus",
                    provider_method_attempts=65,
                    now_utc=NOW,
                )
            self.assertEqual(
                str(caught.exception), "phase3f_component_method_attempt_budget_exceeded"
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_component_budget(
                    authorization,
                    component_id="analyst_consensus",
                    provider_method_attempts=0,
                    retries=1,
                    now_utc=NOW,
                )
            self.assertEqual(str(caught.exception), "phase3f_component_retry_budget_exceeded")

    def test_provider_free_components_get_a_zero_attempt_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory), scope=make_scope(32))
            approval.require_phase3f_component_budget(
                authorization,
                component_id="alert_level_freshness",
                provider_method_attempts=0,
                now_utc=NOW,
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_component_budget(
                    authorization,
                    component_id="alert_level_freshness",
                    provider_method_attempts=1,
                    now_utc=NOW,
                )
        self.assertEqual(
            str(caught.exception), "phase3f_component_method_attempt_budget_exceeded"
        )

    def test_non_integer_attempt_counts_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            for bad in (-1, 1.5, True, "2", None):
                with self.subTest(bad=bad), self.assertRaises(approval.Phase3FApprovalError):
                    approval.require_phase3f_component_budget(
                        authorization,
                        component_id="analyst_consensus",
                        provider_method_attempts=bad,
                        now_utc=NOW,
                    )

    def test_duration_cap_and_non_finite_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            approval.require_phase3f_component_duration(
                authorization,
                component_id="analyst_consensus",
                duration_seconds=899.5,
                now_utc=NOW,
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_component_duration(
                    authorization,
                    component_id="analyst_consensus",
                    duration_seconds=900.5,
                    now_utc=NOW,
                )
            self.assertEqual(str(caught.exception), "phase3f_component_duration_exceeded")
            for bad in (float("nan"), float("inf"), -1.0, True, "12"):
                with self.subTest(bad=bad), self.assertRaises(
                    approval.Phase3FApprovalError
                ) as caught:
                    approval.require_phase3f_component_duration(
                        authorization,
                        component_id="analyst_consensus",
                        duration_seconds=bad,
                        now_utc=NOW,
                    )
                self.assertEqual(str(caught.exception), "phase3f_component_duration_invalid")

    def test_input_bytes_are_bound_to_the_minted_hashes(self) -> None:
        payload = b'{"evidence": true}'
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(
                Path(directory),
                input_hashes={"alert_reference_evidence": sha_bytes(payload)},
            )
            self.assertEqual(
                approval.require_phase3f_input_bytes(
                    authorization.approval, name="alert_reference_evidence", raw=payload
                ),
                sha_bytes(payload),
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_input_bytes(
                    authorization.approval,
                    name="alert_reference_evidence",
                    raw=payload + b" ",
                )
            self.assertEqual(str(caught.exception), "phase3f_input_hash_mismatch")
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                approval.require_phase3f_input_bytes(
                    authorization.approval, name="unbound", raw=payload
                )
        self.assertEqual(str(caught.exception), "phase3f_input_not_approved")

    def test_skipped_component_metrics_declare_no_provider_work(self) -> None:
        metrics = approval.skipped_phase3f_component_metrics("analyst_consensus")
        self.assertEqual(metrics["status"], "skipped_not_approved")
        self.assertEqual(metrics["provider_method_attempts"], 0)
        self.assertFalse(metrics["raw_provider_payload_retained"])
        self.assertFalse(metrics["credentials_or_tokens_retained"])
        self.assertFalse(metrics["stderr_or_exception_text_retained"])
        with self.assertRaises(approval.Phase3FApprovalError) as caught:
            approval.skipped_phase3f_component_metrics("portfolio_rebalance")
        self.assertEqual(str(caught.exception), "phase3f_component_unknown")

    def test_production_authorization_refuses_a_substituted_provider_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory), components=("analyst_consensus",))
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                analyst._build_phase3f_analyst_component_with_authorization(
                    authorization=authorization,
                    now=NOW,
                    _test_provider_module=fake_provider_module(),
                )
        self.assertEqual(str(caught.exception), "phase3f_test_provider_forbidden_in_production")

    def test_test_authorization_requires_a_marked_provider_fixture(self) -> None:
        unmarked = types.ModuleType("unmarked")
        for candidate in (None, unmarked):
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as directory:
                authorization = mint(
                    Path(directory),
                    components=("analyst_consensus",),
                    environment=approval.TEST_ENVIRONMENT,
                )
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    analyst._build_phase3f_analyst_component_with_authorization(
                        authorization=authorization,
                        now=NOW,
                        _test_provider_module=candidate,
                    )
                self.assertEqual(
                    str(caught.exception),
                    "phase3f_test_authorization_provider_import_forbidden",
                )

    def test_provider_constructor_failures_never_leak_secrets(self) -> None:
        module = types.ModuleType("leaky_yfinance")
        module.__phase3f_test_fixture__ = True

        class Ticker:
            def __init__(self, symbol: str) -> None:
                raise RuntimeError("auth failed for token secret-token-abc123")

        module.Ticker = Ticker
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(
                Path(directory),
                components=("analyst_consensus",),
                environment=approval.TEST_ENVIRONMENT,
            )
            component = analyst._build_phase3f_analyst_component_with_authorization(
                authorization=authorization,
                now=NOW,
                _test_provider_module=module,
            )
        blob = json.dumps(component, default=str)
        self.assertNotIn("secret-token-abc123", blob)
        self.assertNotIn("auth failed", blob)
        self.assertFalse(component["metrics"]["credentials_or_tokens_retained"])
        self.assertFalse(component["metrics"]["stderr_or_exception_text_retained"])

    def test_the_component_claim_burns_before_provider_work_begins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authorization = mint(
                root,
                components=("analyst_consensus",),
                environment=approval.TEST_ENVIRONMENT,
            )
            approval.create_phase3f_component_claim(
                authorization, component_id="analyst_consensus", now_utc=NOW
            )
            with self.assertRaises(approval.Phase3FApprovalError) as caught:
                analyst._build_phase3f_analyst_component_with_authorization(
                    authorization=authorization,
                    now=NOW,
                    _test_provider_module=fake_provider_module(),
                )
        self.assertEqual(str(caught.exception), "phase3f_component_already_consumed")


# ---------------------------------------------------------------------------
# Strict evidence parsing
# ---------------------------------------------------------------------------


class StrictEvidenceParsingTests(unittest.TestCase):
    def test_hostile_evidence_documents_are_refused(self) -> None:
        cases = [
            b'{"a": 1, "a": 2}',
            b"\xef\xbb\xbf{}",
            b'{"a": NaN}',
            b'{"a": Infinity}',
            b"[]",
            b"",
            b'{"a": 1',
            b'{"a": 1} trailing',
        ]
        for raw in cases:
            with self.subTest(raw=raw[:24]):
                with self.assertRaises(approval.Phase3FApprovalError):
                    approval.strict_canonical_evidence_json_object(raw, maximum_bytes=4096)

    def test_oversized_evidence_is_refused(self) -> None:
        raw = canonical({"padding": "x" * 512})
        with self.assertRaises(approval.Phase3FApprovalError):
            approval.strict_canonical_evidence_json_object(raw, maximum_bytes=64)

    def test_well_formed_evidence_round_trips(self) -> None:
        document = {"alpha": 1, "beta": [1, 2, {"gamma": True}]}
        parsed = approval.strict_canonical_evidence_json_object(
            canonical(document), maximum_bytes=4096
        )
        self.assertEqual(parsed, document)


# ---------------------------------------------------------------------------
# Authority boundaries
# ---------------------------------------------------------------------------


class AuthorityBoundaryRegressionTests(unittest.TestCase):
    MODULES = (
        "scripts/phase3f_external_canary_approval.py",
        "scripts/dynamic_entitlement_provider_policy.py",
        "scripts/run_alerts_recommendations_chain.py",
    )

    def test_no_cryptography_dependency_survives_the_retirement(self) -> None:
        tokens = (
            "cryptography",
            "ed25519",
            "Ed25519",
            "nacl",
            "PRODUCTION_PHASE3F_TRUST",
            "verify_signature",
            "public_key",
        )
        for relpath in self.MODULES:
            source = (WORKSPACE / relpath).read_text(encoding="utf-8")
            for token in tokens:
                with self.subTest(relpath=relpath, token=token):
                    self.assertNotIn(token, source)

    def test_the_live_policy_grants_provider_reads_and_nothing_else(self) -> None:
        document = json.loads((WORKSPACE / POLICY_RELPATH).read_text(encoding="utf-8"))
        boundary = document["authority_boundary"]
        self.assertIs(boundary["provider_reads_allowed"], True)
        for key in policy_module._REQUIRED_FALSE_BOUNDARIES:
            with self.subTest(key=key):
                self.assertIs(boundary[key], False)
        self.assertEqual(document["allowed_providers"], ["yfinance", "alpaca_market_data"])
        self.assertIs(document["scope_source"]["truncation_allowed"], False)

    def test_receipt_and_claim_payloads_declare_zero_provider_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            claim_path, _ = approval.create_phase3f_component_claim(
                authorization, component_id="analyst_consensus", now_utc=NOW
            )
            receipt = json.loads(authorization.receipt_path.read_text(encoding="utf-8"))
            claim = json.loads(claim_path.read_text(encoding="utf-8"))
        for payload in (receipt, claim):
            self.assertEqual(payload["provider_method_attempts"], 0)
            self.assertEqual(payload["inherited_blockers"], ["external_baseline_blocked"])

    def test_children_expose_no_positive_command_line_execution(self) -> None:
        for module in (analyst, alert):
            with self.subTest(module=module.__name__):
                source = (WORKSPACE / "scripts" / f"{module.__name__}.py").read_text(
                    encoding="utf-8"
                )
                self.assertIn("dynamic_entitlement_preview", source)
                self.assertNotIn("--run-phase3f", source)

    def test_the_immutable_scope_artifact_is_evidence_not_a_trust_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization = mint(Path(directory))
            scope_path = authorization.approval.output_path("immutable_scope")
            self.assertTrue(scope_path.is_file())
            scope_path.write_bytes(b'{"members": [], "count": 0, "fingerprint": "x"}\n')
            # Children read the sealed in-memory bytes, so on-disk tampering
            # cannot widen or narrow what a child may touch.
            tickers = approval.verified_scope_tickers(
                authorization, component_id="analyst_consensus", now_utc=NOW
            )
        self.assertEqual(tickers, ("AAA", "BBB"))

    def test_chain_declares_the_policy_authorization_source_in_proof(self) -> None:
        source = (WORKSPACE / "scripts/run_alerts_recommendations_chain.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("standing_provider_policy", source)
        self.assertIn("veritas.tier_entitlement.phase3f.canary_proof.v2", source)

    def test_policy_run_output_names_cover_every_written_artifact(self) -> None:
        self.assertEqual(
            set(approval.POLICY_RUN_OUTPUT_NAMES),
            {
                "alert_level_freshness",
                "analyst_consensus",
                "canary_proof",
                "immutable_scope",
                "overflow_debt",
                "alert_quote_snapshot",
                "alert_quote_validation",
                "alert_reference_evidence",
            },
        )


SCRIPTS = Path(approval.__file__).resolve().parent


def _budget_policy(root: Path, cap: int):
    document = policy_document()
    document["daily_budget"]["max_daily_provider_calls"] = cap
    return load_policy(root, document)


def _run_concurrently(calls) -> list[object]:
    results: list[object] = []
    guard = threading.Lock()
    barrier = threading.Barrier(len(calls))

    def invoke(fn) -> None:
        barrier.wait()
        try:
            outcome: object = fn()
        except Exception as exc:  # noqa: BLE001 - the outcome is the assertion
            outcome = exc
        with guard:
            results.append(outcome)

    threads = [threading.Thread(target=invoke, args=(fn,)) for fn in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# Held by a separate interpreter so the lock is proven across processes, not
# merely across threads of one process.
_HOLDER_SOURCE = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import dynamic_entitlement_provider_policy as policy_module

ledger = Path(sys.argv[2])
marker = Path(sys.argv[3])
with policy_module._ledger_lock(ledger, timeout_seconds=5.0):
    marker.write_text("held", encoding="utf-8")
    time.sleep(float(sys.argv[4]))
"""


class HolderCleanupError(AssertionError):
    """Fail-closed cleanup failure for a PIPE-spawned test child.

    Raised when the child cannot be proven reaped within bounds, its pipe
    readers cannot be joined within bounds, or closing a pipe itself fails.
    A cannot-clean-safely outcome is an explicit test failure: it never
    returns success and never lets a returncode hide the cleanup fault.
    """


def _drain_close_reap(holder, *, drain_timeout=30.0, kill_timeout=5.0):
    """Bounded fail-closed drain/close/reap for a PIPE-spawned child (test-only).

    Drains both pipes (bounded), then closes them and reaps the child on
    every path: normal exit, early exit, assertion failure, or holder
    timeout. A hung child is killed and reaped with a bounded fallback, and
    the helper returns (returncode, stderr_bytes) so nonzero child outcomes
    stay visible.

    Fail-closed ordering (Main repair adjudication 2026-09-05): the pipes
    are closed only after the child is proven reaped and no pipe reader is
    still consuming them, because closing a BufferedReader while a reader
    thread is still active can block without a timeout. Any kill that fails
    while the child is still alive, any reap that cannot complete within
    bounds, and any pipe-close failure raises HolderCleanupError instead of
    returning success. The single tolerated case is a kill that fails
    against an already-reaped child: a benign race proven by an immediate
    poll, not assumed. Raised from a caller finally, the error chains with
    the primary assertion via exception context instead of hiding it.
    """
    import subprocess

    stderr: bytes = b""
    kill_notes: list[str] = []

    def _note_failed_kill(stage: str, exc: BaseException) -> None:
        # Tolerate only a kill that demonstrably raced an already-reaped
        # child; anything else is recorded and fails closed below whenever
        # the child is still alive.
        if holder.poll() is None:
            kill_notes.append(f"{stage} kill failed: {exc!r}")

    try:
        _, err = holder.communicate(timeout=drain_timeout)
        if err:
            stderr = err
    except subprocess.TimeoutExpired:
        try:
            holder.kill()
        except Exception as exc:  # noqa: BLE001 - recorded, then raised if live
            _note_failed_kill("first", exc)
        try:
            _, err = holder.communicate(timeout=kill_timeout)
            if err:
                stderr = err
        except subprocess.TimeoutExpired as undrained:
            # The child or its pipe readers survived termination. Re-assert
            # termination, then require a bounded reap BEFORE touching the
            # pipes; the pipes stay open until the child is proven reaped
            # and the readers joined.
            try:
                holder.kill()
            except Exception as exc:  # noqa: BLE001 - recorded, then raised if live
                _note_failed_kill("second", exc)
            try:
                holder.wait(timeout=kill_timeout)
            except Exception as exc:
                detail = "; ".join(kill_notes)
                raise HolderCleanupError(
                    "holder_cleanup_incomplete: child not reaped within "
                    "bounded wait after kill; pipes left open"
                    + (f"; {detail}" if detail else "")
                ) from undrained
            if holder.poll() is None:
                detail = "; ".join(kill_notes)
                raise HolderCleanupError(
                    "holder_cleanup_incomplete: child still alive after "
                    "bounded kill/wait; pipes left open (no success "
                    "claimed, no close attempted on a live reader)"
                    + (f"; {detail}" if detail else "")
                ) from undrained
            try:
                _, err = holder.communicate(timeout=kill_timeout)
                if err:
                    stderr = err
            except subprocess.TimeoutExpired as readers:
                raise HolderCleanupError(
                    "holder_cleanup_incomplete: pipe readers still active "
                    "after child exit; pipes left open"
                ) from readers
    if holder.poll() is None:
        # Defensive: every path above proves the reap, but never close a
        # possibly-live reader on assumption alone.
        try:
            holder.wait(timeout=kill_timeout)
        except Exception as exc:
            raise HolderCleanupError(
                "holder_cleanup_incomplete: child still alive before pipe "
                f"close; pipes left open: {exc!r}"
            ) from exc
        if holder.poll() is None:
            raise HolderCleanupError(
                "holder_cleanup_incomplete: child still alive before pipe "
                "close; pipes left open"
            )
    # The child is reaped and the readers joined, so closing is safe. A
    # close failure is a real leak signal and must not hide behind a zero
    # returncode, so it raises. Both pipes are attempted even if one fails.
    close_errors: list[str] = []
    for name in ("stdout", "stderr"):
        stream = getattr(holder, name, None)
        if stream is None:
            continue
        try:
            stream.close()
        except Exception as exc:  # noqa: BLE001 - collected, then raised
            close_errors.append(f"{name} close failed: {exc!r}")
    if close_errors:
        raise HolderCleanupError(
            "holder_cleanup_close_failed: " + "; ".join(close_errors)
        )
    try:
        holder.wait(timeout=kill_timeout)
    except Exception as exc:
        raise HolderCleanupError(
            f"holder_cleanup_incomplete: final reap failed: {exc!r}"
        ) from exc
    return holder.returncode, stderr


class HolderPipeCleanupRegressionTests(unittest.TestCase):
    """Focused cleanup coverage for _drain_close_reap (real subprocesses)."""

    def test_normal_exit_drains_closes_and_reaps_without_resource_warnings(
        self,
    ) -> None:
        import gc
        import subprocess
        import warnings

        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always", ResourceWarning)
            proc = subprocess.Popen(
                [sys.executable, "-c", "print('hello-cleanup')"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            returncode, _ = _drain_close_reap(
                proc, drain_timeout=10.0, kill_timeout=5.0
            )
            self.assertEqual(returncode, 0)
            self.assertIsNotNone(proc.poll())
            self.assertTrue(proc.stdout.closed)
            self.assertTrue(proc.stderr.closed)
            del proc
            gc.collect()
        leaks = [w for w in seen if issubclass(w.category, ResourceWarning)]
        self.assertEqual(leaks, [])

    def test_timeout_path_kills_closes_and_reaps_without_resource_warnings(
        self,
    ) -> None:
        import gc
        import subprocess
        import warnings

        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always", ResourceWarning)
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            returncode, _ = _drain_close_reap(
                proc, drain_timeout=0.5, kill_timeout=5.0
            )
            self.assertIsNotNone(proc.poll())
            self.assertIsNotNone(returncode)
            self.assertNotEqual(returncode, 0)
            self.assertTrue(proc.stdout.closed)
            self.assertTrue(proc.stderr.closed)
            del proc
            gc.collect()
        leaks = [w for w in seen if issubclass(w.category, ResourceWarning)]
        self.assertEqual(leaks, [])


class _FakePipeStream:
    """Hermetic stand-in for a Popen pipe whose close can fail on demand."""

    def __init__(self, *, fail_close: bool = False) -> None:
        self.closed = False
        self.close_calls = 0
        self._fail_close = fail_close

    def close(self) -> None:
        self.close_calls += 1
        if self._fail_close:
            raise OSError("fake pipe close boom")
        self.closed = True


class _FakePipeChild:
    """Hermetic Popen stand-in exposing only the surface _drain_close_reap
    touches (communicate/kill/poll/wait/returncode/stdout/stderr). Outcomes
    are scripted per call; unscripted calls report a reaped rc-0 child."""

    def __init__(
        self,
        *,
        communicate_script,
        kill_script=(),
        poll_script=(),
        wait_script=(),
        returncode=0,
        fail_stdout_close=False,
        fail_stderr_close=False,
    ) -> None:
        self._communicate = list(communicate_script)
        self._kills = list(kill_script)
        self._polls = list(poll_script)
        self._waits = list(wait_script)
        self.returncode = returncode
        self.stdout = _FakePipeStream(fail_close=fail_stdout_close)
        self.stderr = _FakePipeStream(fail_close=fail_stderr_close)
        self.kill_calls = 0

    def communicate(self, timeout=None):
        if not self._communicate:
            return (b"", b"")
        outcome = self._communicate.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def kill(self) -> None:
        self.kill_calls += 1
        if self._kills:
            exc = self._kills.pop(0)
            if exc is not None:
                raise exc

    def poll(self):
        if self._polls:
            return self._polls.pop(0)
        return self.returncode

    def wait(self, timeout=None):
        if self._waits:
            outcome = self._waits.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return self.returncode


class HolderPipeCleanupFailureTests(unittest.TestCase):
    """Fail-closed adversarial coverage for _drain_close_reap.

    Hermetic fakes cover only the cleanup-fault branches; the real
    subprocess success/hang tests above and the original OS ledger-lock
    exclusion test below are retained unchanged.
    """

    def test_kill_failure_with_live_child_raises_and_leaves_pipes_open(
        self,
    ) -> None:
        import subprocess

        child = _FakePipeChild(
            communicate_script=[
                subprocess.TimeoutExpired("fake", 0.5),
                subprocess.TimeoutExpired("fake", 5.0),
            ],
            kill_script=[OSError("fake kill denied"), OSError("fake kill denied")],
            poll_script=[None, None],
            wait_script=[subprocess.TimeoutExpired("fake", 5.0)],
            returncode=None,
        )
        with self.assertRaises(HolderCleanupError) as caught:
            _drain_close_reap(child, drain_timeout=0.5, kill_timeout=5.0)
        message = str(caught.exception)
        self.assertIn("holder_cleanup_incomplete", message)
        self.assertIn("kill failed", message)
        self.assertEqual(child.kill_calls, 2)
        self.assertFalse(child.stdout.closed)
        self.assertFalse(child.stderr.closed)

    def test_close_failure_after_clean_exit_raises_instead_of_returning_zero(
        self,
    ) -> None:
        child = _FakePipeChild(
            communicate_script=[(b"", b"")],
            returncode=0,
            fail_stdout_close=True,
        )
        with self.assertRaises(HolderCleanupError) as caught:
            _drain_close_reap(child, drain_timeout=10.0, kill_timeout=5.0)
        self.assertIn("holder_cleanup_close_failed", str(caught.exception))
        # Both pipes are attempted even when the first close fails.
        self.assertTrue(child.stderr.closed)

    def test_reap_timeout_with_live_child_raises_and_leaves_pipes_open(
        self,
    ) -> None:
        import subprocess

        child = _FakePipeChild(
            communicate_script=[
                subprocess.TimeoutExpired("fake", 0.5),
                subprocess.TimeoutExpired("fake", 5.0),
            ],
            wait_script=[subprocess.TimeoutExpired("fake", 5.0)],
            returncode=None,
        )
        with self.assertRaises(HolderCleanupError) as caught:
            _drain_close_reap(child, drain_timeout=0.5, kill_timeout=5.0)
        self.assertIn("holder_cleanup_incomplete", str(caught.exception))
        self.assertEqual(child.kill_calls, 2)
        self.assertFalse(child.stdout.closed)
        self.assertFalse(child.stderr.closed)

    def test_kill_race_against_an_already_reaped_child_still_drains(
        self,
    ) -> None:
        import subprocess

        child = _FakePipeChild(
            communicate_script=[
                subprocess.TimeoutExpired("fake", 30.0),
                (b"late-output", b""),
            ],
            kill_script=[ProcessLookupError("fake reap race")],
            poll_script=[0],
            returncode=0,
        )
        returncode, _ = _drain_close_reap(
            child, drain_timeout=30.0, kill_timeout=5.0
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(child.kill_calls, 1)
        self.assertTrue(child.stdout.closed)
        self.assertTrue(child.stderr.closed)


class LedgerConcurrencyTests(unittest.TestCase):
    def test_concurrent_reservations_never_lose_a_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = _budget_policy(root, 50)
            calls = [
                (lambda index=index: reserve_provider_calls(
                    resolved, 10, now_utc=NOW, run_id=f"run-{index}"
                ))
                for index in range(8)
            ]
            results = _run_concurrently(calls)
            granted = [r for r in results if isinstance(r, dict)]
            refused = [r for r in results if isinstance(r, ProviderPolicyError)]
            ledger = json.loads(resolved.ledger_path.read_text(encoding="utf-8"))
            entry = ledger["days"][budget_day_key(NOW)]
        # A lost update would let a 9th ten-call reservation through, or leave
        # the recorded total below the number actually granted.
        self.assertEqual(len(granted), 5)
        self.assertEqual(len(refused), 3)
        self.assertTrue(
            all(str(exc) == "provider_daily_budget_exhausted" for exc in refused), refused
        )
        self.assertEqual(entry["reserved_calls"], 50)
        self.assertEqual(sum(entry["open_reservations"].values()), 50)
        self.assertEqual(len(entry["open_reservations"]), 5)

    def test_concurrent_settlements_do_not_double_refund(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = _budget_policy(root, 100)
            for index in range(5):
                reserve_provider_calls(resolved, 10, now_utc=NOW, run_id=f"run-{index}")
            calls = [
                (lambda index=index: settle_provider_calls(
                    resolved, 0, now_utc=NOW, run_id=f"run-{index}"
                ))
                for index in range(5)
            ]
            results = _run_concurrently(calls)
            ledger = json.loads(resolved.ledger_path.read_text(encoding="utf-8"))
            entry = ledger["days"][budget_day_key(NOW)]
        self.assertTrue(all(isinstance(r, dict) for r in results), results)
        self.assertEqual(entry["reserved_calls"], 0)
        self.assertEqual(entry["open_reservations"], {})
        self.assertEqual(entry["settled_calls"], 0)

    def test_reserve_racing_settle_preserves_the_day_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = _budget_policy(root, 100)
            reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-x")
            results = _run_concurrently([
                lambda: reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-y"),
                lambda: settle_provider_calls(resolved, 0, now_utc=NOW, run_id="run-x"),
            ])
            ledger = json.loads(resolved.ledger_path.read_text(encoding="utf-8"))
            entry = ledger["days"][budget_day_key(NOW)]
        self.assertTrue(all(isinstance(r, dict) for r in results), results)
        # run-x refunds its whole reservation, run-y adds one; either order ends
        # at ten.  A lost update lands on zero or twenty.
        self.assertEqual(entry["reserved_calls"], 10)
        self.assertEqual(entry["open_reservations"], {"run-y": 10})

    def test_lock_timeout_fails_closed_and_leaves_the_ledger_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = _budget_policy(root, 100)
            reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-a")
            before = resolved.ledger_path.read_bytes()
            with mock.patch.object(policy_module, "LEDGER_LOCK_TIMEOUT_SECONDS", 0.2):
                with policy_module._ledger_lock(resolved.ledger_path):
                    with self.assertRaises(ProviderPolicyError) as caught:
                        reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-b")
            after = resolved.ledger_path.read_bytes()
        self.assertEqual(str(caught.exception), "provider_call_ledger_lock_timeout")
        self.assertEqual(before, after)

    def test_the_lock_excludes_a_second_operating_system_process(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "state" / "ledger.json"
            ledger.parent.mkdir(parents=True, exist_ok=True)
            marker = root / "held.marker"
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _HOLDER_SOURCE,
                    str(SCRIPTS),
                    str(ledger),
                    str(marker),
                    "3.0",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            holder_stderr: bytes = b""
            try:
                deadline = time.monotonic() + 20.0
                while not marker.exists() and time.monotonic() < deadline:
                    if holder.poll() is not None:
                        _, early_err = holder.communicate(timeout=10)
                        holder_stderr = early_err or b""
                        self.fail(f"holder exited early: {holder_stderr!r}")
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "holder never acquired the lock")
                with self.assertRaises(ProviderPolicyError) as caught:
                    with policy_module._ledger_lock(ledger, timeout_seconds=0.3):
                        pass
            finally:
                # Bounded drain of both pipes, close, and reap on every path:
                # success, early exit, assertion failure, or holder timeout.
                _, drained_err = _drain_close_reap(
                    holder, drain_timeout=30.0, kill_timeout=5.0
                )
                if drained_err:
                    holder_stderr = drained_err
            self.assertEqual(
                holder.returncode, 0, f"holder failed: {holder_stderr!r}"
            )
            # The kernel released the holder's lock at exit, so we get it now.
            with policy_module._ledger_lock(ledger, timeout_seconds=5.0):
                pass
        self.assertEqual(str(caught.exception), "provider_call_ledger_lock_timeout")

    def test_a_divergent_ledger_spelling_is_refused_rather_than_locking_a_second_sidecar(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            ledger = root / "state" / "ledger.json"
            ledger.parent.mkdir(parents=True, exist_ok=True)
            direct = policy_module._ledger_lock_path(ledger)
            indirect = policy_module._ledger_lock_path(
                root / "state" / "." / "ledger.json"
            )
            self.assertEqual(direct, indirect)
            with self.assertRaises(ProviderPolicyError) as caught:
                policy_module._ledger_lock_path(root / "state" / ".." / "state" / "ledger.json")
        self.assertEqual(str(caught.exception), "provider_call_ledger_path_invalid")

    def test_the_sidecar_is_never_unlinked_or_replaced_by_a_ledger_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = _budget_policy(root, 100)
            reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-a")
            lock_path = policy_module._ledger_lock_path(resolved.ledger_path)
            first_identity = lock_path.stat().st_ino, lock_path.stat().st_dev
            settle_provider_calls(resolved, 4, now_utc=NOW, run_id="run-a")
            reserve_provider_calls(resolved, 10, now_utc=NOW, run_id="run-b")
            second_identity = lock_path.stat().st_ino, lock_path.stat().st_dev
        # os.replace swaps the ledger, never the sidecar; if the sidecar were
        # replaced, two processes could hold locks on two different inodes.
        self.assertEqual(first_identity, second_identity)


class LexicalContainmentTests(unittest.TestCase):
    def test_escapes_are_rejected_without_touching_the_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outside = Path(tempfile.gettempdir()).resolve() / "phase3f-outside.json"
            self.assertFalse(approval._is_lexically_contained(outside, root))
            self.assertFalse(
                approval._is_lexically_contained(root / ".." / "escape.json", root)
            )
            self.assertFalse(approval._is_lexically_contained(Path("relative.json"), root))
            # ':' would address an alternate data stream, whose CREATE_NEW can
            # succeed against an already-consumed receipt slot.
            self.assertFalse(
                approval._is_lexically_contained(root / "a" / "receipt.json:alt", root)
            )
            # Windows strips trailing dots and spaces, aliasing two names to one
            # file and defeating one-shot mint semantics.
            self.assertFalse(
                approval._is_lexically_contained(root / "a" / "receipt.json.", root)
            )
            self.assertTrue(approval._is_lexically_contained(root / "a" / "b.json", root))

    def test_an_extended_length_spelling_of_the_same_path_is_contained(self) -> None:
        # Path.resolve() intermittently returns the \\?\ spelling when its
        # prefix-strip re-verification loses a race with concurrent creation.
        # Treating that as an escape was the sole cause of the mint flake.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "tmp" / "receipt.json"
            prefixed = Path("\\\\?\\" + str(target)) if os.name == "nt" else target
            self.assertTrue(approval._is_lexically_contained(prefixed, root))
            prefixed_root = Path("\\\\?\\" + str(root)) if os.name == "nt" else root
            self.assertTrue(approval._is_lexically_contained(target, prefixed_root))

    def test_containment_is_decided_before_any_directory_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            escape = root.parent / "phase3f-should-not-exist" / "receipt.json"
            with mock.patch.object(
                Path, "mkdir", side_effect=AssertionError("mkdir attempted")
            ):
                with self.assertRaises(approval.Phase3FApprovalError) as caught:
                    approval._exclusive_durable_json_write(
                        escape, {"a": 1}, workspace_root=root
                    )
            self.assertFalse(escape.parent.exists())
        self.assertEqual(str(caught.exception), "phase3f_durable_write_path_invalid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
