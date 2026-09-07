#!/usr/bin/env python3
"""Offline Phase 3C compatibility proof for dynamic Tier A+B entitlement.

The test deliberately uses only in-memory ``UniverseMembershipRecord``
snapshots.  It does not create a database, call a provider, invoke a
subprocess or scheduler, or create a Tier writer.  Actual effective-tier
transactions remain a separately gated Phase 4 concern.
"""

from __future__ import annotations

from dataclasses import replace
from unittest import mock

import pytest

import finance_sql_canon_access as sql_canon
from finance_sql_canon_access import (
    DYNAMIC_ENTITLEMENT_WITNESSES,
    DynamicEntitlementScope,
    DynamicEntitlementScopeError,
    FinanceSqlCanonAccess,
    UniverseMembershipRecord,
    verify_dynamic_entitlement_payload,
)


def membership(
    ticker: str,
    tier: str,
    *,
    active: bool = True,
    yfinance_symbol: str | None = None,
    decision_grade_eligible: bool = True,
) -> UniverseMembershipRecord:
    """Build one hand-authored guarded-SQL-shaped record for this test only."""

    sql_tier, coverage_obligation_tier = DYNAMIC_ENTITLEMENT_WITNESSES[tier]
    return UniverseMembershipRecord(
        ticker=ticker,
        name=f"{ticker} test issuer",
        instrument_type="equity",
        sector=None,
        industry=None,
        yfinance_symbol=yfinance_symbol or ticker,
        sec_cik=None,
        company_ir=None,
        active=active,
        universe_scope="phase3c_in_memory",
        tier=tier,
        coverage_obligation_tier=coverage_obligation_tier,
        monitoring_role="review_only",
        production_scope_member=False,
        production_scope_source=None,
        sql_tier=sql_tier,
        sql_tier_state="effective",
        tier_decision_scope="phase3c_compatibility_only",
        review_100_monitor=False,
        decision_grade_eligible=decision_grade_eligible,
        source_open_required=False,
        promotion_required_before_action=True,
        raw_json={"ticker": ticker, "tier": tier},
    )


def retier(row: UniverseMembershipRecord, tier: str) -> UniverseMembershipRecord:
    """Return a simulated effective tier with its two witnesses synchronized."""

    sql_tier, coverage_obligation_tier = DYNAMIC_ENTITLEMENT_WITNESSES[tier]
    return replace(
        row,
        tier=tier,
        sql_tier=sql_tier,
        coverage_obligation_tier=coverage_obligation_tier,
    )


def baseline_snapshot() -> dict[str, UniverseMembershipRecord]:
    return {
        "ALPHA": membership("ALPHA", "A", yfinance_symbol="ALPHA"),
        "BRAVO": membership("BRAVO", "B", yfinance_symbol="BRAVO-ALT"),
        "CHARLIE": membership("CHARLIE", "C", yfinance_symbol="CHARLIE-ALT"),
    }


def expected_memberships(
    snapshot: dict[str, UniverseMembershipRecord],
) -> set[str]:
    return {
        ticker
        for ticker, row in snapshot.items()
        if row.active and row.tier in {"A", "B"}
    }


def resolve_snapshot(
    snapshot: dict[str, UniverseMembershipRecord],
    *,
    envelope_count: int | None = None,
) -> DynamicEntitlementScope:
    """Resolve a snapshot while making any attempted SQLite path fail loudly."""

    client = FinanceSqlCanonAccess()
    with (
        mock.patch.object(
            client,
            "universe_memberships",
            return_value=dict(sorted(snapshot.items())),
        ) as membership_read,
        mock.patch.object(
            sql_canon,
            "connect_readonly",
            side_effect=AssertionError("Phase 3C must not open SQLite"),
        ),
    ):
        scope = client.dynamic_entitlement_scope(
            envelope_name="phase3c_in_memory",
            envelope_count=envelope_count,
        )
    assert membership_read.call_count == 1
    return scope


def assert_complete_scope(
    scope: DynamicEntitlementScope,
    snapshot: dict[str, UniverseMembershipRecord],
) -> None:
    expected = expected_memberships(snapshot)
    assert set(scope.memberships) == expected
    assert scope.tickers == tuple(sorted(expected))
    assert list(scope.memberships) == sorted(expected)
    assert all(row.tier in {"A", "B"} for row in scope.memberships.values())


def test_b_to_a_reclassification_preserves_complete_scope_and_changes_witnessed_tier() -> None:
    before_snapshot = baseline_snapshot()
    before = resolve_snapshot(before_snapshot)
    assert_complete_scope(before, before_snapshot)

    after_snapshot = dict(before_snapshot)
    after_snapshot["BRAVO"] = retier(after_snapshot["BRAVO"], "A")
    after = resolve_snapshot(after_snapshot)

    assert_complete_scope(after, after_snapshot)
    assert "BRAVO" in before.memberships and "BRAVO" in after.memberships
    assert before.memberships["BRAVO"].tier == "B"
    assert after.memberships["BRAVO"].tier == "A"
    assert after.tier_breakdown == {"A": 2, "B": 0}
    assert after.fingerprint != before.fingerprint


def test_c_to_b_joins_scope_only_after_effective_tier_snapshot_transition() -> None:
    before_snapshot = baseline_snapshot()
    before = resolve_snapshot(before_snapshot)
    assert_complete_scope(before, before_snapshot)
    assert before.aliases["CHARLIE-ALT"] == "CHARLIE"
    assert "CHARLIE" in before.identities
    assert "CHARLIE" not in before.memberships

    after_snapshot = dict(before_snapshot)
    after_snapshot["CHARLIE"] = retier(after_snapshot["CHARLIE"], "B")
    after = resolve_snapshot(after_snapshot)

    assert_complete_scope(after, after_snapshot)
    assert after.aliases["CHARLIE-ALT"] == "CHARLIE"
    assert "CHARLIE" in after.memberships


def test_paired_displacement_and_demotion_has_no_static_capacity_rule() -> None:
    snapshot = baseline_snapshot()
    snapshot["CHARLIE"] = retier(snapshot["CHARLIE"], "B")
    snapshot["BRAVO"] = retier(snapshot["BRAVO"], "C")
    snapshot["ALPHA"] = retier(snapshot["ALPHA"], "B")

    scope = resolve_snapshot(snapshot)

    assert_complete_scope(scope, snapshot)
    assert set(scope.tickers) == {"ALPHA", "CHARLIE"}
    assert "BRAVO" not in scope.memberships
    assert scope.tier_breakdown == {"A": 0, "B": 2}


def test_alias_identity_never_bypasses_membership_predicate() -> None:
    snapshot = baseline_snapshot()
    scope = resolve_snapshot(snapshot)

    assert_complete_scope(scope, snapshot)
    assert scope.aliases["BRAVO-ALT"] == "BRAVO"
    assert "BRAVO" in scope.memberships
    assert scope.aliases["CHARLIE-ALT"] == "CHARLIE"
    assert "CHARLIE" in scope.identities
    assert "CHARLIE" not in scope.memberships


def test_scope_growth_is_complete_beyond_derived_baseline_and_payload_tampering_fails_closed() -> None:
    base_snapshot = baseline_snapshot()
    base_scope = resolve_snapshot(base_snapshot)
    assert_complete_scope(base_scope, base_snapshot)

    expanded_snapshot = dict(base_snapshot)
    expanded_snapshot["ECHO"] = membership("ECHO", "B", yfinance_symbol="ECHO")
    expanded = resolve_snapshot(
        expanded_snapshot,
        envelope_count=len(base_scope.tickers),
    )

    assert_complete_scope(expanded, expanded_snapshot)
    assert len(expanded.tickers) == len(base_scope.tickers) + 1
    assert expanded.overflow_tickers
    assert set(expanded.overflow_tickers) == set(expanded.tickers[len(base_scope.tickers):])

    payload = expanded.payload()
    assert verify_dynamic_entitlement_payload(payload, expanded.fingerprint) == expanded.fingerprint
    payload["members"][0]["tier"] = "B" if payload["members"][0]["tier"] == "A" else "A"
    with pytest.raises(
        DynamicEntitlementScopeError,
        match="guarded_sql_scope_payload_fingerprint_mismatch",
    ):
        verify_dynamic_entitlement_payload(payload, expanded.fingerprint)


def test_reader_failure_and_witness_conflict_each_fail_closed() -> None:
    client = FinanceSqlCanonAccess()
    with (
        mock.patch.object(
            client,
            "universe_memberships",
            side_effect=RuntimeError("synthetic_guarded_sql_read_failure"),
        ) as membership_read,
        mock.patch.object(
            sql_canon,
            "connect_readonly",
            side_effect=AssertionError("Phase 3C must not open SQLite"),
        ),
        pytest.raises(RuntimeError, match="synthetic_guarded_sql_read_failure"),
    ):
        client.dynamic_entitlement_scope()
    assert membership_read.call_count == 1

    conflict_snapshot = baseline_snapshot()
    conflict_snapshot["BRAVO"] = replace(conflict_snapshot["BRAVO"], sql_tier="Tier A")
    with pytest.raises(DynamicEntitlementScopeError, match="guarded_sql_scope_tier_conflict"):
        resolve_snapshot(conflict_snapshot)


def test_decision_grade_repair_debt_is_an_authority_clamp_not_a_promotion_rule() -> None:
    # Amended contract (Main 2026-09-05 L64/65; resolver excerpt lines 92-100,
    # 1560-1567): decision_grade_eligible=false is resolver-owned eligibility
    # debt, NEVER a structural integrity failure. integrity_breaches means
    # structural failure only; debt lives solely in eligibility_debt.
    snapshot = baseline_snapshot()
    snapshot["BRAVO"] = replace(snapshot["BRAVO"], decision_grade_eligible=False)
    snapshot["CHARLIE"] = replace(snapshot["CHARLIE"], decision_grade_eligible=False)

    scope = resolve_snapshot(snapshot)

    # CHARLIE is canonical Tier C: excluded from A+B membership even when its
    # own eligibility flag flips. BRAVO is canonical Tier B: stays enrolled.
    assert_complete_scope(scope, snapshot)
    assert "BRAVO" in scope.memberships
    assert "CHARLIE" not in scope.memberships
    assert set(scope.tickers) == {"ALPHA", "BRAVO"}
    assert scope.tier_breakdown == {"A": 1, "B": 1}

    # False-flag preservation: the member row keeps decision_grade_eligible False.
    assert scope.memberships["BRAVO"].decision_grade_eligible is False
    assert scope.memberships["ALPHA"].decision_grade_eligible is True

    # Structural/debt separation: no structural breach; exact debt tuple.
    assert scope.integrity_breaches == ()
    assert scope.eligibility_debt == ("BRAVO",)

    # Fingerprint sensitivity: flipping ONLY the included BRAVO eligibility
    # flag changes the member-triples fingerprint.
    eligible_snapshot = baseline_snapshot()
    eligible_scope = resolve_snapshot(eligible_snapshot)
    assert eligible_scope.eligibility_debt == ()
    assert eligible_scope.integrity_breaches == ()
    assert scope.fingerprint != eligible_scope.fingerprint

    # Tier C eligibility never expands A+B membership, debt, or fingerprint:
    # CHARLIE flag flips alone change nothing observable in scope.
    charlie_eligible = baseline_snapshot()
    charlie_eligible["CHARLIE"] = replace(
        charlie_eligible["CHARLIE"], decision_grade_eligible=True
    )
    charlie_ineligible = baseline_snapshot()
    charlie_ineligible["CHARLIE"] = replace(
        charlie_ineligible["CHARLIE"], decision_grade_eligible=False
    )
    scope_c_on = resolve_snapshot(charlie_eligible)
    scope_c_off = resolve_snapshot(charlie_ineligible)
    for closed_scope in (scope_c_on, scope_c_off):
        assert set(closed_scope.memberships) == {"ALPHA", "BRAVO"}
        assert closed_scope.eligibility_debt == ()
        assert closed_scope.integrity_breaches == ()
    assert scope_c_on.fingerprint == scope_c_off.fingerprint
