#!/usr/bin/env python3
"""Phase3G debt-scope separation tests (hermetic, zero SQL, zero providers).

Repair attempt 2 contract: resolver ``integrity_breaches`` means ONLY
structural failure (normally empty; structural faults raise before it).
``decision_grade_eligible=false`` members stay enrolled with their false
flag in the fingerprint and membership, and debt lives solely in the
derived ``eligibility_debt`` annotation, cross-checked against the
fingerprint-bound flags.  No string-shape bypass exists anywhere.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import finance_sql_canon_access as sql_canon
from finance_sql_canon_access import (
    DynamicEntitlementExternalGateError,
    DynamicEntitlementScopeError,
    FinanceSqlCanonAccess,
    UniverseMembershipRecord,
    eligibility_debt_label,
    require_dynamic_entitlement_external_gate,
    verify_dynamic_entitlement_payload,
)


def _member(
    ticker: str,
    tier: str,
    eligible: bool,
    *,
    yfinance_symbol: str | None = None,
    active: bool = True,
) -> UniverseMembershipRecord:
    return UniverseMembershipRecord(
        ticker=ticker,
        name=f"{ticker} Inc",
        instrument_type="common_stock",
        sector="Technology",
        industry="Semiconductors",
        yfinance_symbol=yfinance_symbol or ticker,
        sec_cik=None,
        company_ir=None,
        active=active,
        universe_scope="active_internal_universe",
        tier=tier,
        coverage_obligation_tier=tier,
        monitoring_role="monitor",
        production_scope_member=False,
        production_scope_source=None,
        sql_tier=f"Tier {tier}",
        sql_tier_state="current",
        tier_decision_scope="phase3g_debt_scope_fixture",
        review_100_monitor=False,
        decision_grade_eligible=eligible,
        source_open_required=False,
        promotion_required_before_action=False,
        raw_json={},
    )


def _mixed_snapshot() -> dict[str, UniverseMembershipRecord]:
    return {
        "AAA": _member("AAA", "A", True),
        "BBB": _member("BBB", "B", True),
        "CCC": _member("CCC", "A", False),
        "DDD": _member("DDD", "B", False),
        "EEE": _member("EEE", "C", True),
    }


class _StubPolicy:
    def __init__(self) -> None:
        self.admitted_counts: list[int] = []

    def require_scope_within_envelope(self, count: int) -> None:
        self.admitted_counts.append(count)


class DebtScopeTest(unittest.TestCase):
    def resolve(self, snapshot: dict[str, UniverseMembershipRecord], **kwargs):
        client = FinanceSqlCanonAccess(Path("/nonexistent/finance-canon.sqlite"))
        with (
            mock.patch.object(client, "universe_memberships", return_value=dict(sorted(snapshot.items()))) as read,
            mock.patch.object(sql_canon, "connect_readonly", side_effect=AssertionError("debt scope must not open SQL")),
        ):
            scope = client.dynamic_entitlement_scope(**kwargs)
        self.assertEqual(read.call_count, 1)
        return scope

    def test_mixed_scope_keeps_every_ab_member(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        self.assertEqual(set(scope.memberships), {"AAA", "BBB", "CCC", "DDD"})
        self.assertEqual(scope.tickers, ("AAA", "BBB", "CCC", "DDD"))
        self.assertEqual(scope.tier_breakdown, {"A": 2, "B": 2})
        self.assertFalse(scope.memberships["CCC"].decision_grade_eligible)
        self.assertFalse(scope.memberships["DDD"].decision_grade_eligible)

    def test_integrity_breaches_structural_only(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        self.assertEqual(scope.integrity_breaches, ())
        self.assertEqual(scope.eligibility_debt, ("CCC", "DDD"))

    def test_false_eligibility_preserved_in_fingerprint(self) -> None:
        debt_scope = self.resolve(_mixed_snapshot())
        clean_snapshot = _mixed_snapshot()
        clean_snapshot["CCC"] = replace(clean_snapshot["CCC"], decision_grade_eligible=True)
        clean_snapshot["DDD"] = replace(clean_snapshot["DDD"], decision_grade_eligible=True)
        clean_scope = self.resolve(clean_snapshot)
        self.assertNotEqual(debt_scope.fingerprint, clean_scope.fingerprint)
        payload = debt_scope.payload()
        self.assertEqual(
            verify_dynamic_entitlement_payload(payload, debt_scope.fingerprint),
            debt_scope.fingerprint,
        )
        by_ticker = {row["ticker"]: row for row in payload["members"]}
        self.assertIs(by_ticker["CCC"]["decision_grade_eligible"], False)
        self.assertIs(by_ticker["DDD"]["decision_grade_eligible"], False)
        self.assertIs(by_ticker["AAA"]["decision_grade_eligible"], True)

    def test_debt_annotation_explicit_and_validated(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        payload = scope.payload()
        self.assertEqual(payload["eligibility_debt"], ["CCC", "DDD"])
        self.assertEqual(payload["eligibility_debt_count"], 2)
        self.assertIn("not_decision_or_recommendation_ready", payload["debt_label"])
        self.assertIn("CCC", payload["debt_label"])
        understated = dict(payload)
        understated["eligibility_debt"] = ["CCC"]
        with self.assertRaises(DynamicEntitlementScopeError) as caught:
            verify_dynamic_entitlement_payload(understated, scope.fingerprint)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_payload_fingerprint_mismatch")
        cleared = dict(payload)
        cleared["eligibility_debt"] = []
        with self.assertRaises(DynamicEntitlementScopeError):
            verify_dynamic_entitlement_payload(cleared, scope.fingerprint)
        legacy = {k: v for k, v in payload.items() if k != "eligibility_debt"}
        self.assertEqual(
            verify_dynamic_entitlement_payload(legacy, scope.fingerprint),
            scope.fingerprint,
        )

    def test_debt_label_never_confers_readiness(self) -> None:
        clean_snapshot = _mixed_snapshot()
        clean_snapshot["CCC"] = replace(clean_snapshot["CCC"], decision_grade_eligible=True)
        clean_snapshot["DDD"] = replace(clean_snapshot["DDD"], decision_grade_eligible=True)
        clean_scope = self.resolve(clean_snapshot)
        self.assertEqual(clean_scope.eligibility_debt, ())
        self.assertEqual(clean_scope.payload()["debt_label"], eligibility_debt_label([]))
        self.assertNotIn("ready_for_decision", clean_scope.payload()["debt_label"])
        self.assertNotIn("recommendation_ready", clean_scope.payload()["debt_label"])

    def test_gate_admits_debt_only_scope_for_evidence(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        policy = _StubPolicy()
        resolved = require_dynamic_entitlement_external_gate(
            scope, scope_origin="phase3f_dynamic_entitlement", policy=policy
        )
        self.assertIs(resolved, policy)
        self.assertEqual(policy.admitted_counts, [4])

    def test_gate_rejects_fabricated_debt_mismatch(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        forged = replace(scope, eligibility_debt=())
        with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
            require_dynamic_entitlement_external_gate(
                forged, scope_origin="phase3f_dynamic_entitlement", policy=_StubPolicy()
            )
        self.assertEqual(
            str(caught.exception), "dynamic_entitlement_scope_eligibility_debt_mismatch"
        )

    def test_gate_still_refuses_any_breach_without_shape_bypass(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        for breaches in (
            ("alias_collision",),
            ("entitlement_integrity_breach:AAA:decision_grade_eligible_false",),
        ):
            with self.subTest(breaches=breaches):
                broken = replace(scope, integrity_breaches=breaches)
                with self.assertRaises(DynamicEntitlementExternalGateError) as caught:
                    require_dynamic_entitlement_external_gate(
                        broken, scope_origin="phase3f_dynamic_entitlement", policy=_StubPolicy()
                    )
                self.assertEqual(
                    str(caught.exception), "dynamic_entitlement_scope_integrity_breach"
                )

    def test_tier_witness_conflict_fails_closed(self) -> None:
        snapshot = _mixed_snapshot()
        snapshot["AAA"] = replace(snapshot["AAA"], sql_tier="Tier B")
        with self.assertRaises(DynamicEntitlementScopeError) as caught:
            self.resolve(snapshot)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_tier_conflict")

    def test_alias_collision_fails_closed(self) -> None:
        snapshot = _mixed_snapshot()
        snapshot["BBB"] = replace(snapshot["BBB"], yfinance_symbol="AAA")
        with self.assertRaises(DynamicEntitlementScopeError) as caught:
            self.resolve(snapshot)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_alias_conflict")

    def test_malformed_envelope_fails_closed(self) -> None:
        with self.assertRaises(DynamicEntitlementScopeError) as caught:
            self.resolve(_mixed_snapshot(), envelope_count=-1)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_invalid_envelope")

    def test_empty_ab_scope_fails_closed(self) -> None:
        snapshot = {"EEE": _member("EEE", "C", True)}
        with self.assertRaises(DynamicEntitlementScopeError) as caught:
            self.resolve(snapshot)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_empty")

    def test_overflow_keeps_full_membership(self) -> None:
        scope = self.resolve(_mixed_snapshot(), envelope_name="tiny", envelope_count=1)
        self.assertEqual(set(scope.memberships), {"AAA", "BBB", "CCC", "DDD"})
        self.assertEqual(len(scope.overflow_tickers), 3)
        self.assertEqual(scope.eligibility_debt, ("CCC", "DDD"))

    def test_tampered_payload_fails_closed(self) -> None:
        scope = self.resolve(_mixed_snapshot())
        payload = scope.payload()
        payload["members"][2]["decision_grade_eligible"] = True
        with self.assertRaises(DynamicEntitlementScopeError) as caught:
            verify_dynamic_entitlement_payload(payload, scope.fingerprint)
        self.assertEqual(str(caught.exception), "guarded_sql_scope_payload_fingerprint_mismatch")


if __name__ == "__main__":
    unittest.main()
