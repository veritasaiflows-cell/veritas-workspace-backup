#!/usr/bin/env python3
"""Hermetic adversarial proof for the Phase 3G current-alerts adapter.

Every test uses synthetic scopes and injected artifacts: no live scope names,
no producer files, no provider, no SQL, no writes. The suite proves the
adapter contract from tmp/phase3fg-20260905/adjudication.md:

* quote observation requires independently valid proof plus finite freshness,
  with producer policy AND independent calendar agreeing;
* closed-market monitor-only classification stays observable;
* missing bands never erase a valid quote and never make band claims ready;
* analyst needs an explicit allowed sourcing status plus finite age;
* quarantined/unverified evidence never becomes observed or decision-grade;
* lineage/reference quality and recency stay evidence-backed;
* recommendation cards and queue ownership are never fabricated or counted.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Mapping
from unittest import mock

import pytest

from finance_sql_canon_access import REFERENCE_LEVEL_LINEAGE_FIELDS, DynamicEntitlementScope
from phase3g_alert_coverage import (
    build_current_alerts_coverage,
    safe_output_path,
)
from tier_entitlement_phase3d_observed_coverage import (
    ENROLLED_NOT_OBSERVED,
    NO_OWNER_SURFACE,
    OBSERVED,
    ArtifactSnapshot,
)

RUN_AT = "2026-09-05T14:00:00Z"  # Saturday: closed-market session context.
QUOTE_STAMP = "2026-09-04T20:00:00Z"  # Friday close: 18h old, inside 36h ceiling.
CONTROLLER_GEN = "2026-09-05T13:00:00Z"  # 1h old, inside 6h contract.
ANALYST_ASOF = "2026-09-04T20:00:00Z"  # 18h old, inside 7d review contract.
LINEAGE_STAMP = "2026-09-05T10:00:00Z"  # 4h old, inside 14d reference contract.
CONTROLLER_SCHEMA = "veritas.alert_level_freshness_controller.v1"
MONITOR_FRESH = "current_last_completed_session_monitor"


def make_scope(*names: str, tier: str = "B", eligible: bool = True) -> DynamicEntitlementScope:
    members = {
        name: SimpleNamespace(ticker=name, tier=tier, decision_grade_eligible=eligible)
        for name in names
    }
    return DynamicEntitlementScope(
        source="guarded_sql:test",
        memberships=members,
        identities=dict(members),
        aliases={name: name for name in names},
        fingerprint="synthetic-fingerprint",
        tier_breakdown={tier: len(names)},
        integrity_breaches=(),
        envelope_name="test",
        envelope_count=len(names),
        overflow_tickers=(),
    )


def snapshot(path: str, payload: Mapping[str, Any] | None, *,
             error: str | None = None, sha: str | None = "synthetic-sha") -> ArtifactSnapshot:
    return ArtifactSnapshot(path=path, sha256=sha if payload is not None else None,
                            payload=payload, error=error)


def clean_quote_row(name: str, **overrides: Any) -> dict[str, Any]:
    row = {"symbol": name, "price": 100.0, "source_timestamp_utc": QUOTE_STAMP}
    row.update(overrides)
    return row


def clean_controller_row(name: str, **overrides: Any) -> dict[str, Any]:
    row = {"ticker": name, "validation_status": "ok",
           "freshness_status": MONITOR_FRESH, "alert_state": "normal"}
    row.update(overrides)
    return row


def clean_analyst_row(**overrides: Any) -> dict[str, Any]:
    row = {"as_of": ANALYST_ASOF, "source_status": "auto_sourced_yfinance",
           "cross_check_conflict": "pass",
           "source_lineage": {"source_url": "https://example.test/q",
                              "evidence_digest_sha256": "abc123"}}
    row.update(overrides)
    return row


def clean_lineage(**overrides: Any) -> dict[str, Any]:
    lineage = {
        "level_as_of_utc": LINEAGE_STAMP,
        "fields": [{"field_name": field, "source_generated_at_utc": LINEAGE_STAMP}
                   for field in sorted(REFERENCE_LEVEL_LINEAGE_FIELDS)],
        "artifact_checks": [{"path": "p", "expected_sha256": "e",
                             "actual_sha256": "e", "hash_matches": True}],
        "lineage_validation_ok": True,
    }
    lineage.update(overrides)
    return lineage


class FakeClient:
    def __init__(self, scope: DynamicEntitlementScope, *,
                 reference: Any = "default", reference_error: Any = None) -> None:
        self.scope = scope
        self.calls = 0
        self._reference = reference
        self._reference_error = reference_error

    def dynamic_entitlement_scope(self, **_kwargs: Any) -> DynamicEntitlementScope:
        self.calls += 1
        return self.scope

    def reference_level(self, ticker: str) -> Any:
        if self._reference_error is not None:
            raise self._reference_error(ticker) if isinstance(
                self._reference_error, type) else self._reference_error
        if self._reference == "default":
            return SimpleNamespace(reference_price_low=90.0,
                                   reference_price_high=110.0,
                                   reference_invalidation_level=85.0)
        return self._reference


@contextmanager
def controlled_helpers(proof_ok: bool = True, policy_current: bool = True,
                       calendar_status: str = "current_last_completed_session"
                       ) -> Iterator[dict[str, Any]]:
    """Pin producer-owned helpers; the adapter must AND both calendar gates."""
    calls: dict[str, Any] = {}
    import phase3g_alert_coverage as adapter

    def fake_proof(proof: Any, validation: Any, **kwargs: Any) -> bool:
        calls["proof_identity"] = kwargs.get("expected_artifact_identity")
        return proof_ok

    def fake_policy(*_args: Any, **_kwargs: Any) -> dict[str, bool]:
        return {"calendar_current": policy_current, "fire_eligible": False,
                "monitor_only": True, "stale_or_missing": not policy_current}

    def fake_calendar(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"calendar_freshness_status": calendar_status}

    def fake_verify(payload: Any, fingerprint: Any) -> None:
        calls["verify"] = (payload, fingerprint)

    with (
        mock.patch("alert_level_freshness_controller.quote_proof_is_clean",
                   side_effect=fake_proof),
        mock.patch("alert_level_freshness_controller.quote_evaluation_policy",
                   side_effect=fake_policy),
        mock.patch.object(adapter, "classify_quote_freshness", side_effect=fake_calendar),
        mock.patch.object(adapter, "verify_dynamic_entitlement_payload",
                          side_effect=fake_verify),
    ):
        yield calls


def run_build(scope: DynamicEntitlementScope, *,
              quote_rows: Mapping[str, Any] | list | None = "default",
              controller_rows: list | None = "default",
              analyst_rows: Mapping[str, Any] | None = "default",
              lineage: Any = "default",
              client: FakeClient | None = None,
              proof_ok: bool = True, policy_current: bool = True,
              calendar_status: str = "current_last_completed_session",
              analyst_status: str = "ok", analyst_tier_sets: bool = False,
              run_at: str = RUN_AT) -> tuple[dict[str, Any], dict[str, Any]]:
    names = list(scope.tickers)
    quote_payload: Mapping[str, Any] | None = (
        {"generated_at_utc": CONTROLLER_GEN,
         "snapshots": ({n: clean_quote_row(n) for n in names}
                       if quote_rows == "default" else quote_rows)}
        if quote_rows is not None else None)
    controller_payload: Mapping[str, Any] | None = (
        {"generated_at_utc": CONTROLLER_GEN, "schema": CONTROLLER_SCHEMA,
         "rows": ([clean_controller_row(n) for n in names]
                  if controller_rows == "default" else controller_rows)}
        if controller_rows is not None else None)
    tickers = ({n: clean_analyst_row() for n in names}
               if analyst_rows == "default" else analyst_rows)
    analyst_payload: Mapping[str, Any] | None = (
        {"generated_at_utc": CONTROLLER_GEN, "status": analyst_status,
         "tickers": tickers} if analyst_rows is not None else None)
    if analyst_tier_sets and isinstance(analyst_payload, dict):
        analyst_payload = dict(analyst_payload, tier_sets={"A": list(names)})
    quote = (snapshot("tmp/quote-test.json", quote_payload) if quote_payload is not None
             else ArtifactSnapshot(path="tmp/quote-test.json", sha256=None,
                                   payload=None, error="artifact_missing"))
    validation = (snapshot("tmp/quote-validation-test.json",
                            {"generated_at_utc": CONTROLLER_GEN} if quote_rows is not None else None)
                  if quote_rows is not None else ArtifactSnapshot(
                      path="tmp/quote-validation-test.json", sha256=None,
                      payload=None, error="artifact_missing"))
    controller = snapshot("tmp/controller-test.json", controller_payload)
    analyst = (snapshot("tmp/analyst-test.json", analyst_payload)
               if analyst_payload is not None else ArtifactSnapshot(
                   path="tmp/analyst-test.json", sha256=None,
                   payload=None, error="artifact_missing"))
    lineage_map = clean_lineage() if lineage == "default" else lineage

    def lineage_reader(_ticker: str) -> Any:
        return lineage_map(_ticker) if callable(lineage_map) else lineage_map

    with controlled_helpers(proof_ok=proof_ok, policy_current=policy_current,
                            calendar_status=calendar_status) as calls:
        proof = build_current_alerts_coverage(
            client=client or FakeClient(scope), scope=scope,
            controller=controller, quote=quote, quote_validation=validation,
            analyst=analyst, lineage_reader=lineage_reader, run_as_of_utc=run_at)
    assert calls["verify"] == (scope.payload(), scope.fingerprint)
    return proof, calls


def cell(proof: dict[str, Any], ticker: str, evidence_class: str) -> dict[str, Any]:
    row = next(r for r in proof["rows"] if r["ticker"] == ticker)
    return row["evidence"][evidence_class]


def test_fully_clean_build_observes_evidence_without_decision_grade() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    proof, calls = run_build(scope)
    assert proof["status"] == "coverage_debt"  # card synthesis stays routed debt: never auto-cleared
    assert calls["proof_identity"] == "tmp/quote-test.json"
    for name in ("ALPHA", "BRAVO"):
        for evidence_class in ("quote_session", "lineage", "reference_level",
                               "analyst_symbol", "freshness"):
            assert cell(proof, name, evidence_class)["state"] == OBSERVED, (name, evidence_class)
        assert cell(proof, name, "recommendation_card")["state"] == NO_OWNER_SURFACE
        assert cell(proof, name, "recommendation_card")["reason"] == \
            "current_recommendation_compiler_not_verified"
        assert cell(proof, name, "queue")["state"] == ENROLLED_NOT_OBSERVED
        row = next(r for r in proof["rows"] if r["ticker"] == name)
        assert row["recommendation_complete"] is False
        assert row["band_dependent_claims_blocked"] is False
    # Only the structural card-synthesis debt routes; nothing is counted as reviewed.
    assert [(q["ticker"], q["evidence_class"]) for q in proof["repair_queue"]] == [
        ("ALPHA", "recommendation_card"), ("BRAVO", "recommendation_card")]
    summary = proof["repair_queue_summary"]
    assert summary["reviewed"] is None and summary["review_sla_proven"] is False
    assert proof["resolver_invocation_count"] == 0
    assert proof["authority"] == {"projection_only": True, "gate_input": False,
                                  "automatic_action": False}
    assert proof["capacity"]["provider_calls"] == 0


def test_missing_quote_artifact_blocks_quote_but_not_bands_or_membership() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    proof, _ = run_build(scope, quote_rows=None)
    assert {r["ticker"] for r in proof["rows"]} == {"ALPHA", "BRAVO"}
    for name in ("ALPHA", "BRAVO"):
        assert cell(proof, name, "quote_session")["reason"] == "artifact_missing"
        assert cell(proof, name, "quote_session")["state"] == ENROLLED_NOT_OBSERVED
        assert cell(proof, name, "reference_level")["state"] == OBSERVED
        assert cell(proof, name, "freshness")["state"] == ENROLLED_NOT_OBSERVED
        row = next(r for r in proof["rows"] if r["ticker"] == name)
        assert row["band_dependent_claims_blocked"] is True


def test_unbound_quote_payload_is_visible_debt() -> None:
    scope = make_scope("ALPHA")
    # Present payload without a content hash can never bind to an artifact.
    quote = ArtifactSnapshot(path="tmp/quote-test.json", sha256=None,
                             payload={"generated_at_utc": CONTROLLER_GEN,
                                      "snapshots": {"ALPHA": clean_quote_row("ALPHA")}},
                             error=None)
    validation = snapshot("tmp/quote-validation-test.json", {"generated_at_utc": CONTROLLER_GEN})
    controller = snapshot("tmp/controller-test.json",
                          {"generated_at_utc": CONTROLLER_GEN, "schema": CONTROLLER_SCHEMA,
                           "rows": [clean_controller_row("ALPHA")]})
    analyst = snapshot("tmp/analyst-test.json",
                       {"generated_at_utc": CONTROLLER_GEN, "status": "ok",
                        "tickers": {"ALPHA": clean_analyst_row()}})
    with controlled_helpers():
        rebuilt = build_current_alerts_coverage(
            client=FakeClient(scope), scope=scope, controller=controller,
            quote=quote, quote_validation=validation, analyst=analyst,
            lineage_reader=lambda _t: clean_lineage(), run_as_of_utc=RUN_AT)
    assert cell(rebuilt, "ALPHA", "quote_session")["reason"] == "source_unbound"
    assert cell(rebuilt, "ALPHA", "quote_session")["state"] == ENROLLED_NOT_OBSERVED


def test_stale_quote_artifact_and_tampered_proof_fail_closed() -> None:
    scope = make_scope("ALPHA")
    stale_quote = snapshot("tmp/quote-test.json",
                           {"generated_at_utc": "2026-08-01T00:00:00Z",
                            "snapshots": {"ALPHA": clean_quote_row("ALPHA")}})
    validation = snapshot("tmp/quote-validation-test.json", {"generated_at_utc": CONTROLLER_GEN})
    controller = snapshot("tmp/controller-test.json",
                          {"generated_at_utc": CONTROLLER_GEN, "schema": CONTROLLER_SCHEMA,
                           "rows": [clean_controller_row("ALPHA")]})
    analyst = snapshot("tmp/analyst-test.json",
                       {"generated_at_utc": CONTROLLER_GEN, "status": "ok",
                        "tickers": {"ALPHA": clean_analyst_row()}})
    with controlled_helpers():
        proof = build_current_alerts_coverage(
            client=FakeClient(scope), scope=scope, controller=controller,
            quote=stale_quote, quote_validation=validation, analyst=analyst,
            lineage_reader=lambda _t: clean_lineage(), run_as_of_utc=RUN_AT)
    assert cell(proof, "ALPHA", "quote_session")["reason"] == "stale_evidence"

    proof, _ = run_build(scope, proof_ok=False)
    assert cell(proof, "ALPHA", "quote_session")["reason"] == "quote_proof_not_clean"


def test_bad_price_missing_row_and_alias_conflict_are_per_ticker_debt() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    scope.aliases["BRK-B"] = "BRAVO"
    quote_list = [clean_quote_row("ALPHA"), clean_quote_row("BRAVO", price=-5.0),
                  {"symbol": "BRK-B", "price": 10.0, "source_timestamp_utc": QUOTE_STAMP},
                  {"symbol": "BRAVO", "price": 10.0, "source_timestamp_utc": QUOTE_STAMP},
                  {"symbol": "GHOST", "price": 10.0, "source_timestamp_utc": QUOTE_STAMP}]
    proof, _ = run_build(scope, quote_rows=quote_list)
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED
    assert cell(proof, "BRAVO", "quote_session")["reason"] == "alias_conflict"
    debt_reasons = {d["reason"] for d in proof["artifact_symbol_debt"]["quote_session"]}
    assert "unresolved_symbol" in debt_reasons  # GHOST can never join the scope
    assert [r["ticker"] for r in proof["rows"]] == ["ALPHA", "BRAVO"]

    scope2 = make_scope("ALPHA", "BRAVO", "CHARLIE")
    rows = {"ALPHA": clean_quote_row("ALPHA"),
            "BRAVO": clean_quote_row("BRAVO", price=0.0)}
    proof2, _ = run_build(scope2, quote_rows=rows)
    assert cell(proof2, "BRAVO", "quote_session")["reason"] == "quote_price_invalid"
    assert cell(proof2, "CHARLIE", "quote_session")["reason"] == "quote_source_row_missing"


def test_stale_future_and_missing_quote_stamps_fail_closed() -> None:
    scope = make_scope("ALPHA", "BRAVO", "CHARLIE")
    rows = {"ALPHA": clean_quote_row("ALPHA", source_timestamp_utc="2026-08-20T20:00:00Z"),
            "BRAVO": clean_quote_row("BRAVO", source_timestamp_utc="2026-09-05T16:00:00Z"),
            "CHARLIE": {"symbol": "CHARLIE", "price": 10.0}}
    proof, _ = run_build(scope, quote_rows=rows)
    assert cell(proof, "ALPHA", "quote_session")["reason"] == "stale_evidence"
    assert cell(proof, "BRAVO", "quote_session")["reason"] == "future_timestamp"
    assert cell(proof, "CHARLIE", "quote_session")["reason"] == "missing_timestamp"


def test_calendar_gates_are_anded_not_orred() -> None:
    scope = make_scope("ALPHA")
    proof, _ = run_build(scope, policy_current=True, calendar_status="stale_unexpected")
    assert cell(proof, "ALPHA", "quote_session")["reason"] == "quote_not_current"
    proof, _ = run_build(scope, policy_current=False,
                         calendar_status="current_last_completed_session")
    assert cell(proof, "ALPHA", "quote_session")["reason"] == "quote_not_current"
    proof, _ = run_build(scope, policy_current=True,
                         calendar_status="current_last_completed_session")
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED


def test_closed_market_monitor_only_stays_observable() -> None:
    scope = make_scope("ALPHA")
    proof, _ = run_build(scope, policy_current=True,
                         calendar_status="market_closed_expected_stale")
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED
    assert cell(proof, "ALPHA", "freshness")["state"] == OBSERVED
    assert cell(proof, "ALPHA", "freshness")["reason"] == "current_alert_evaluation"


def test_missing_bands_keep_valid_quote_observed() -> None:
    scope = make_scope("ALPHA")
    proof, _ = run_build(scope, lineage={}, client=FakeClient(scope, reference=None))
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED
    assert cell(proof, "ALPHA", "lineage")["reason"] == "lineage_record_missing"
    assert cell(proof, "ALPHA", "reference_level")["reason"] == "reference_level_missing_or_invalid"
    assert cell(proof, "ALPHA", "freshness")["state"] == ENROLLED_NOT_OBSERVED
    row = next(r for r in proof["rows"] if r["ticker"] == "ALPHA")
    assert row["band_dependent_claims_blocked"] is True
    assert row["recommendation_complete"] is False


def test_none_lineage_return_degrades_to_per_ticker_debt() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    proof, _ = run_build(scope, lineage=lambda t: None if t == "BRAVO" else clean_lineage())
    assert cell(proof, "ALPHA", "lineage")["state"] == OBSERVED
    assert cell(proof, "ALPHA", "reference_level")["state"] == OBSERVED
    assert cell(proof, "BRAVO", "lineage")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "BRAVO", "reference_level")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "BRAVO", "quote_session")["state"] == OBSERVED
    assert {r["ticker"] for r in proof["rows"]} == {"ALPHA", "BRAVO"}


def test_unexpected_reference_exception_degrades_to_per_ticker_debt() -> None:
    # Main re-adjudication: this scenario is PRESERVED but its expectation is
    # reversed. A reference-reader KeyError is a systemic programming/guard
    # failure, not per-ticker debt. The adapter must abort fail-closed with a
    # sanitized systemic error (no ordinary coverage_debt artifact, no retry
    # of remaining members, no leaked original message) rather than degrade.
    scope = make_scope("ALPHA", "BRAVO", "CHARLIE")
    client = FakeClient(scope)
    original = client.reference_level
    seen: list[str] = []

    def flaky(ticker: str) -> Any:
        seen.append(ticker)
        if ticker == "BRAVO":
            raise KeyError(ticker)
        return original(ticker)

    client.reference_level = flaky  # type: ignore[method-assign]
    with controlled_helpers():
        with pytest.raises(RuntimeError, match="coverage_reference_system_failure") as excinfo:
            run_build(scope, client=client)
    assert str(excinfo.value) == "coverage_reference_system_failure"
    assert seen == ["ALPHA", "BRAVO"]  # CHARLIE never retried after guard failure.


def test_reference_os_failure_aborts_systemic_without_retry() -> None:
    scope = make_scope("ALPHA", "BRAVO", "CHARLIE")
    client = FakeClient(scope)
    original = client.reference_level
    seen: list[str] = []

    def flaky(ticker: str) -> Any:
        seen.append(ticker)
        if ticker == "BRAVO":
            raise OSError("synthetic disk failure")
        return original(ticker)

    client.reference_level = flaky  # type: ignore[method-assign]
    with controlled_helpers():
        with pytest.raises(RuntimeError, match="coverage_reference_system_failure") as excinfo:
            run_build(scope, client=client)
    assert str(excinfo.value) == "coverage_reference_system_failure"
    assert seen == ["ALPHA", "BRAVO"]


def test_lineage_shape_keyerror_degrades_to_per_ticker_debt() -> None:
    # The same KeyError type in the LINEAGE component stays per-ticker
    # malformed-evidence debt: full membership, valid quotes, and the
    # untouched member's observed cells survive.
    scope = make_scope("ALPHA", "BRAVO")

    def reader(ticker: str) -> Any:
        if ticker == "BRAVO":
            raise KeyError(ticker)
        return clean_lineage()

    proof, _ = run_build(scope, lineage=reader)
    assert cell(proof, "ALPHA", "lineage")["state"] == OBSERVED
    assert cell(proof, "ALPHA", "reference_level")["state"] == OBSERVED
    assert cell(proof, "BRAVO", "lineage")["reason"] == "guarded_reference_read_error"
    assert cell(proof, "BRAVO", "lineage")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "BRAVO", "reference_level")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "BRAVO", "quote_session")["state"] == OBSERVED
    assert {r["ticker"] for r in proof["rows"]} == {"ALPHA", "BRAVO"}


def test_lineage_malformed_conversion_degrades_to_per_ticker_debt() -> None:
    scope = make_scope("ALPHA", "BRAVO")

    def reader(ticker: str) -> Any:
        if ticker == "BRAVO":
            return 42  # dict(42) raises TypeError: shape debt, not systemic.
        return clean_lineage()

    proof, _ = run_build(scope, lineage=reader)
    assert cell(proof, "ALPHA", "lineage")["state"] == OBSERVED
    assert cell(proof, "BRAVO", "lineage")["reason"] == "guarded_reference_read_error"
    assert cell(proof, "BRAVO", "lineage")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "BRAVO", "quote_session")["state"] == OBSERVED
    assert {r["ticker"] for r in proof["rows"]} == {"ALPHA", "BRAVO"}


@pytest.mark.parametrize("failure", [
    RuntimeError("synthetic guard failure"),
    OSError("synthetic disk failure"),
    sqlite3.Error("synthetic db failure"),
])
def test_lineage_system_failure_aborts_without_ordinary_artifact(failure: Exception) -> None:
    scope = make_scope("ALPHA", "BRAVO", "CHARLIE")
    seen: list[str] = []

    def reader(ticker: str) -> Any:
        seen.append(ticker)
        if ticker == "BRAVO":
            raise failure
        return clean_lineage()

    with controlled_helpers():
        with pytest.raises(RuntimeError, match="coverage_lineage_system_failure") as excinfo:
            run_build(scope, lineage=reader)
    assert str(excinfo.value) == "coverage_lineage_system_failure"
    assert seen == ["ALPHA", "BRAVO"]  # CHARLIE never retried after system failure.


def test_inverted_and_invalid_bands_never_read_ready() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    client = FakeClient(scope)
    client.reference_level = lambda t: (SimpleNamespace(reference_price_low=110.0,  # type: ignore[method-assign]
                                                        reference_price_high=90.0,
                                                        reference_invalidation_level=85.0)
                                        if t == "ALPHA" else None)
    proof, _ = run_build(scope, client=client)
    assert cell(proof, "ALPHA", "reference_level")["reason"] == "reference_band_inverted"
    assert cell(proof, "BRAVO", "reference_level")["reason"] == "reference_level_missing_or_invalid"
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED


def test_lineage_quality_gates_are_evidence_backed() -> None:
    scope = make_scope("ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO")
    bad_fields = dict(clean_lineage(), fields=[
        {"field_name": "reference_price_low", "source_generated_at_utc": LINEAGE_STAMP}])
    stale_field = dict(clean_lineage(), fields=[
        {"field_name": f, "source_generated_at_utc": ("2026-01-01T00:00:00Z"
                                                     if f == "reference_price_high" else LINEAGE_STAMP)}
        for f in sorted(REFERENCE_LEVEL_LINEAGE_FIELDS)])
    # The pre-fix three-field shape (no reference_confidence/band_status) is incomplete.
    legacy_three = dict(clean_lineage(), fields=[
        {"field_name": f, "source_generated_at_utc": LINEAGE_STAMP}
        for f in ("reference_price_low", "reference_price_high", "reference_invalidation_level")])
    bad_checks = dict(clean_lineage(), artifact_checks=[
        {"path": "p", "expected_sha256": "e", "actual_sha256": "X", "hash_matches": False}])
    no_validation = dict(clean_lineage(), lineage_validation_ok=False)

    def reader(ticker: str) -> Any:
        return {"ALPHA": bad_fields, "BRAVO": stale_field,
                "CHARLIE": bad_checks, "DELTA": no_validation, "ECHO": legacy_three}[ticker]

    proof, _ = run_build(scope, lineage=reader)
    assert cell(proof, "ALPHA", "lineage")["reason"] == "lineage_field_set_incomplete_or_duplicate"
    assert cell(proof, "ECHO", "lineage")["reason"] == "lineage_field_set_incomplete_or_duplicate"
    assert cell(proof, "BRAVO", "lineage")["reason"] == "stale_evidence"
    assert cell(proof, "CHARLIE", "lineage")["reason"] == "lineage_not_clean"
    assert cell(proof, "DELTA", "lineage")["reason"] == "lineage_not_clean"


def test_stale_placeholder_and_quarantined_analyst_never_observed() -> None:
    scope = make_scope("ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT")
    rows = {"ALPHA": clean_analyst_row(),
            "BRAVO": clean_analyst_row(source_status="manual_pending"),
            "CHARLIE": clean_analyst_row(cross_check_conflict="conflict"),
            "DELTA": clean_analyst_row(source_lineage={"source_url": None,
                                                       "evidence_digest_sha256": None}),
            "ECHO": clean_analyst_row(as_of="2026-08-01T00:00:00Z"),
            "FOXTROT": clean_analyst_row(as_of="2026-09-05T16:00:00Z")}
    proof, _ = run_build(scope, analyst_rows=rows)
    assert cell(proof, "ALPHA", "analyst_symbol")["state"] == OBSERVED
    assert cell(proof, "BRAVO", "analyst_symbol")["reason"] == \
        "analyst_unavailable_partial_or_not_cross_checked"
    assert cell(proof, "CHARLIE", "analyst_symbol")["reason"] == \
        "analyst_unavailable_partial_or_not_cross_checked"
    assert cell(proof, "DELTA", "analyst_symbol")["reason"] == "analyst_lineage_missing"
    assert cell(proof, "ECHO", "analyst_symbol")["reason"] == "stale_evidence"
    assert cell(proof, "FOXTROT", "analyst_symbol")["reason"] == "future_timestamp"

    proof, _ = run_build(scope, analyst_status="placeholder_manual_required")
    for name in scope.tickers:
        assert cell(proof, name, "analyst_symbol")["reason"] == \
            "analyst_placeholder_manual_required"

    proof, _ = run_build(scope, analyst_tier_sets=True)
    for name in scope.tickers:
        assert cell(proof, name, "analyst_symbol")["reason"] == "analyst_quarantined"


def test_missing_analyst_row_and_artifact_are_visible_not_fabricated() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    proof, _ = run_build(scope, analyst_rows={"ALPHA": clean_analyst_row()})
    assert cell(proof, "ALPHA", "analyst_symbol")["state"] == OBSERVED
    assert cell(proof, "BRAVO", "analyst_symbol")["reason"] == "analyst_source_row_missing"

    proof, _ = run_build(scope, analyst_rows=None)
    for name in ("ALPHA", "BRAVO"):
        assert cell(proof, name, "analyst_symbol")["reason"] == "artifact_missing"


def test_controller_mismatch_and_staleness_block_freshness_only() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    controller = snapshot("tmp/controller-test.json",
                          {"generated_at_utc": CONTROLLER_GEN, "schema": "wrong.schema",
                           "rows": [clean_controller_row("ALPHA"), clean_controller_row("BRAVO")]})
    analyst = snapshot("tmp/analyst-test.json",
                       {"generated_at_utc": CONTROLLER_GEN, "status": "ok",
                        "tickers": {"ALPHA": clean_analyst_row(), "BRAVO": clean_analyst_row()}})
    quote = snapshot("tmp/quote-test.json",
                     {"generated_at_utc": CONTROLLER_GEN,
                      "snapshots": {"ALPHA": clean_quote_row("ALPHA"),
                                    "BRAVO": clean_quote_row("BRAVO")}})
    validation = snapshot("tmp/quote-validation-test.json", {"generated_at_utc": CONTROLLER_GEN})
    with controlled_helpers():
        proof = build_current_alerts_coverage(
            client=FakeClient(scope), scope=scope, controller=controller,
            quote=quote, quote_validation=validation, analyst=analyst,
            lineage_reader=lambda _t: clean_lineage(), run_as_of_utc=RUN_AT)
    for name in ("ALPHA", "BRAVO"):
        assert cell(proof, name, "freshness")["reason"] == "controller_schema_mismatch"
        assert cell(proof, name, "quote_session")["state"] == OBSERVED

    proof, _ = run_build(
        scope, controller_rows=[clean_controller_row("ALPHA", freshness_status="stale"),
                               clean_controller_row("BRAVO")])
    assert cell(proof, "ALPHA", "freshness")["reason"] == \
        "controller_evidence_review_required"
    assert cell(proof, "BRAVO", "freshness")["state"] == OBSERVED


def test_repair_queue_prioritizes_incidents_and_never_claims_review() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    controller_rows = [clean_controller_row("ALPHA", alert_state="thesis_change"),
                       clean_controller_row("BRAVO", alert_state="normal")]
    analyst = {"ALPHA": clean_analyst_row(as_of="2026-08-01T00:00:00Z"),
               "BRAVO": clean_analyst_row()}
    quote = {"ALPHA": clean_quote_row("ALPHA"),
             "BRAVO": {"symbol": "BRAVO", "price": 10.0}}
    proof, _ = run_build(scope, quote_rows=quote, controller_rows=controller_rows,
                         analyst_rows=analyst)
    assert cell(proof, "ALPHA", "freshness")["state"] == OBSERVED
    queue = proof["repair_queue"]
    assert queue, "dirty evidence must route to the repair queue, not vanish"
    assert queue[0]["ticker"] == "ALPHA" and queue[0]["priority"] == "P0"
    bravo = [q for q in queue if q["ticker"] == "BRAVO"]
    assert bravo and bravo[0]["priority"] == "P2"
    for entry in queue:
        assert entry["state"] == "pending_review"
        assert entry["automatic_action"] is False
        assert entry["reviewed_at_utc"] is None
        assert entry["queue_age_status"] == "unavailable_no_review_ledger"
        assert entry["owner"] == "Veritas Main"
    summary = proof["repair_queue_summary"]
    assert summary["reviewed"] is None and summary["review_sla_proven"] is False
    assert summary["reason"] == "routing_projection_is_not_an_observed_review_ledger"


def test_scope_parity_violation_and_bad_clock_raise() -> None:
    member = SimpleNamespace(ticker="ALPHA", tier="B", decision_grade_eligible=True)
    ghost = SimpleNamespace(ticker="GHOST", tier="B", decision_grade_eligible=True)
    parity_scope = SimpleNamespace(tickers=("ALPHA",),
                                   memberships={"ALPHA": member, "GHOST": ghost},
                                   aliases={"ALPHA": "ALPHA"}, fingerprint="x",
                                   payload=lambda: {"fingerprint": "x"})
    quote = snapshot("tmp/quote-test.json",
                     {"generated_at_utc": CONTROLLER_GEN,
                      "snapshots": {"ALPHA": clean_quote_row("ALPHA")}})
    with controlled_helpers():
        with pytest.raises(ValueError, match="scope_membership_parity_failure"):
            build_current_alerts_coverage(
                client=FakeClient(make_scope("ALPHA")), scope=parity_scope,  # type: ignore[arg-type]
                controller=snapshot("tmp/c.json", None), quote=quote,
                quote_validation=snapshot("tmp/v.json", None),
                analyst=snapshot("tmp/a.json", None),
                lineage_reader=lambda _t: clean_lineage(), run_as_of_utc=RUN_AT)
    scope2 = make_scope("ALPHA")
    with controlled_helpers():
        with pytest.raises(ValueError, match="invalid_run_as_of_utc"):
            run_build(scope2, run_at="not-a-timestamp")


def test_build_is_hermetic_deterministic_and_side_effect_free() -> None:
    scope = make_scope("ALPHA", "BRAVO")
    with (
        mock.patch.object(Path, "read_text", side_effect=AssertionError("read attempted")),
        mock.patch.object(Path, "write_text", side_effect=AssertionError("write attempted")),
        mock.patch("subprocess.run", side_effect=AssertionError("subprocess attempted")),
    ):
        first, _ = run_build(scope)
        second, _ = run_build(scope)
    import json as _json
    assert _json.dumps(first, sort_keys=True) == _json.dumps(second, sort_keys=True)
    assert first["coverage_counts"]["queue"][ENROLLED_NOT_OBSERVED] == 2


def test_out_of_scope_symbols_stay_debt_and_never_filter_members() -> None:
    scope = make_scope("ALPHA")
    rows = {"ALPHA": clean_quote_row("ALPHA"), "ZZZ_UNKNOWN": clean_quote_row("ZZZ_UNKNOWN")}
    proof, _ = run_build(scope, quote_rows=rows)
    assert [r["ticker"] for r in proof["rows"]] == ["ALPHA"]
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED
    assert proof["artifact_symbol_debt"]["quote_session"] == [
        {"symbol": "ZZZ_UNKNOWN", "reason": "unresolved_symbol"}]


def test_safe_output_path_keeps_proofs_in_distinct_tmp_json() -> None:
    from tier_entitlement_phase3d_observed_coverage import ROOT
    good = safe_output_path(ROOT / "tmp" / "phase3g-test" / "coverage.json")
    assert good.suffix == ".json"
    with pytest.raises(ValueError, match="coverage_output_outside_workspace"):
        safe_output_path(Path("/tmp/elsewhere/coverage.json"))
    with pytest.raises(ValueError, match="coverage_output_requires_distinct_phase3g_tmp_json"):
        safe_output_path(ROOT / "tmp" / "other" / "coverage.json")
    with pytest.raises(ValueError, match="coverage_output_requires_distinct_phase3g_tmp_json"):
        safe_output_path(ROOT / "tmp" / "phase3g-test" / "coverage.txt")


def _breached_scope(breach: str) -> DynamicEntitlementScope:
    scope = make_scope("ALPHA", "BRAVO")
    return DynamicEntitlementScope(
        source=scope.source, memberships=dict(scope.memberships),
        identities=dict(scope.identities), aliases=dict(scope.aliases),
        fingerprint=scope.fingerprint, tier_breakdown=dict(scope.tier_breakdown),
        integrity_breaches=(breach,), envelope_name=scope.envelope_name,
        envelope_count=scope.envelope_count,
        overflow_tickers=tuple(scope.overflow_tickers),
    )


def _assert_breach_denied_without_work(scope: DynamicEntitlementScope) -> None:
    import phase3g_alert_coverage as adapter

    client = FakeClient(scope)
    calls: dict[str, object] = {}

    def fake_verify(payload: object, fingerprint: object) -> None:
        calls["verify"] = (payload, fingerprint)

    with (
        mock.patch.object(adapter, "verify_dynamic_entitlement_payload",
                           side_effect=fake_verify),
        mock.patch.object(adapter, "_read_artifact",
                           side_effect=AssertionError("artifact read on breach")),
        mock.patch.object(adapter, "_source_from_controller",
                           side_effect=AssertionError("source read on breach")),
        mock.patch.object(Path, "read_text",
                           side_effect=AssertionError("read on breach")),
        mock.patch.object(Path, "write_text",
                           side_effect=AssertionError("write on breach")),
        mock.patch("subprocess.run",
                    side_effect=AssertionError("subprocess on breach")),
        pytest.raises(ValueError, match="structural_scope_integrity_breach"),
    ):
        build_current_alerts_coverage(
            client=client, scope=scope,
            lineage_reader=lambda _t: (_ for _ in ()).throw(
                AssertionError("lineage read on breach")),
            run_as_of_utc=RUN_AT)
    # Passed-in scope must not trigger another resolver read on denial.
    assert client.calls == 0


def test_structural_breach_rejects_before_any_evidence_work() -> None:
    _assert_breach_denied_without_work(
        _breached_scope("guarded_sql_scope_tier_conflict"))


def test_fabricated_debt_shaped_breach_string_has_no_bypass() -> None:
    # A debt-shaped string in integrity_breaches is still structural failure:
    # the gate refuses ANY nonempty value without shape exceptions.
    _assert_breach_denied_without_work(_breached_scope(
        "entitlement_integrity_breach:BRAVO:decision_grade_eligible_false"))


def test_debt_only_scope_remains_enrolled_with_quote_observed() -> None:
    # Debt-only (decision_grade_eligible=false, breaches empty) is NOT gated:
    # the member stays enrolled, quote observation survives missing bands,
    # and no recommendation/queue readiness is fabricated.
    scope = make_scope("ALPHA", eligible=False)
    proof, _ = run_build(scope, lineage={})
    assert [r["ticker"] for r in proof["rows"]] == ["ALPHA"]
    assert cell(proof, "ALPHA", "quote_session")["state"] == OBSERVED
    assert cell(proof, "ALPHA", "lineage")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "ALPHA", "reference_level")["state"] == ENROLLED_NOT_OBSERVED
    assert cell(proof, "ALPHA", "recommendation_card")["state"] == NO_OWNER_SURFACE
    assert cell(proof, "ALPHA", "queue")["state"] == ENROLLED_NOT_OBSERVED
    row = next(r for r in proof["rows"] if r["ticker"] == "ALPHA")
    assert row["decision_grade_eligible"] is False
    assert row["band_dependent_claims_blocked"] is True
    assert row["recommendation_complete"] is False
    summary = proof["repair_queue_summary"]
    assert summary["reviewed"] is None and summary["review_sla_proven"] is False


def _controller_with_sources(sources: Mapping[str, Any]) -> ArtifactSnapshot:
    return snapshot("tmp/controller-test.json",
                    {"generated_at_utc": CONTROLLER_GEN, "schema": CONTROLLER_SCHEMA,
                     "rows": [], "source_artifacts": dict(sources)})


def test_controller_source_path_rejects_unsafe_shapes_without_content_read() -> None:
    import phase3g_alert_coverage as adapter

    unsafe = [
        "../outside.json", "tmp/../outside.json", "/etc/passwd.json",
        "C:/evil.json", "C:\\evil.json", "C:relative.json",
        "//server/share.json", "\\\\server\\share\\x.json",
        "\\\\?\\C:\\x.json", "tmp/evil.txt", "tmp/no-suffix",
        "", "   ", "tmp/ads.json:stream", "tmp/evil./x.json",
        "tmp/evil /x.json", "tmp//double.json", "tmp/./dot.json",
        "/tmp/abs.json", "tmp/ok.json\x00",
    ]
    for raw in unsafe:
        controller = _controller_with_sources({"quote_snapshot": raw})
        with mock.patch.object(adapter, "_read_artifact",
                               side_effect=AssertionError("content read on invalid path")) as reader:
            result = adapter._source_from_controller(controller, "quote_snapshot", "tmp/default.json")
        assert result.error == "source_path_invalid", raw
        assert result.path == "tmp/default.json", raw  # rejected raw path never echoed.
        assert result.payload is None and result.sha256 is None
        reader.assert_not_called()
    controller = _controller_with_sources({"quote_snapshot": 42})
    with mock.patch.object(adapter, "_read_artifact",
                           side_effect=AssertionError("content read on invalid path")) as reader:
        result = adapter._source_from_controller(controller, "quote_snapshot", "tmp/default.json")
    assert result.error == "source_path_invalid"
    assert result.path == "tmp/default.json"
    reader.assert_not_called()


def test_controller_source_path_allows_safe_missing_as_artifact_missing() -> None:
    import phase3g_alert_coverage as adapter

    missing = "tmp/intraday-alerts/phase3g-test-missing-synthetic.json"
    controller = _controller_with_sources({"quote_snapshot": missing})
    result = adapter._source_from_controller(controller, "quote_snapshot", "tmp/default.json")
    assert result.error == "artifact_missing"  # absence is not invalidity.
    assert result.payload is None


def test_controller_source_path_denies_reparse_without_content_read() -> None:
    import phase3g_alert_coverage as adapter

    controller = _controller_with_sources({"quote_snapshot": "tmp/intraday-alerts/ok.json"})
    with (
        mock.patch.object(adapter, "_path_has_reparse_component", return_value=True),
        mock.patch.object(adapter, "_read_artifact",
                          side_effect=AssertionError("content read on reparse")) as reader,
    ):
        result = adapter._source_from_controller(controller, "quote_snapshot", "tmp/default.json")
    assert result.error == "source_path_invalid"
    assert result.path == "tmp/default.json"
    reader.assert_not_called()


def test_controller_source_path_passes_safe_relative_to_reader_once() -> None:
    import phase3g_alert_coverage as adapter

    sentinel = ArtifactSnapshot(path="tmp/ok.json", sha256="x", payload={}, error=None)
    controller = _controller_with_sources({"quote_snapshot": "tmp/intraday-alerts/ok.json"})
    with (
        mock.patch.object(adapter, "_path_has_reparse_component", return_value=False),
        mock.patch.object(adapter, "_read_artifact", return_value=sentinel) as reader,
    ):
        result = adapter._source_from_controller(controller, "quote_snapshot", "tmp/default.json")
    assert result is sentinel
    reader.assert_called_once()
