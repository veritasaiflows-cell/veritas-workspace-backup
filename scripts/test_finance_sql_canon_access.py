#!/usr/bin/env python3
"""Focused tests for the finance SQL-canon typed access layer."""

from __future__ import annotations

import hashlib
import tempfile
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from unittest import mock

from finance_sql_canon_access import (
    CURRENT_LINEAGE_SOURCE_STATUSES,
    DynamicEntitlementScopeError,
    DynamicEntitlementExternalGateError,
    REFERENCE_LEVEL_LINEAGE_FIELDS,
    FinanceSqlCanonAccess,
    eligibility_debt_label,
    require_dynamic_entitlement_external_gate,
    verify_dynamic_entitlement_payload,
    p0_registry_lane_status,
)


ROOT = Path(__file__).resolve().parents[1]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    client = FinanceSqlCanonAccess()
    validation = client.validate()
    assert_true(validation["status"] == "ok", f"validation blocked: {validation['errors']}")
    assert_true(validation["warnings"] == [], f"unexpected validation warnings: {validation['warnings']}")
    checks = {row["name"]: row for row in validation["checks"]}
    for name in [
        "immutable_alert_reference_baseline_exact",
        "current_lineage_artifacts_exist_and_hash_match",
        "legacy_tier_routing_and_consumers_retired",
        "current_sql_raw_json_alerts_only",
        "audited_consumer_retirement_manifest_exact",
        "legacy_production_route_retired",
        "alert_lineage_complete",
    ]:
        assert_true(checks.get(name, {}).get("ok") is True, f"{name} failed: {checks.get(name)}")
    lineage_check = checks["current_lineage_artifacts_exist_and_hash_match"]
    lineage_detail = lineage_check.get("detail") or {}
    assert_true(
        tuple(lineage_detail.get("current_source_statuses") or ()) == CURRENT_LINEAGE_SOURCE_STATUSES,
        f"current lineage statuses drifted: {lineage_detail.get('current_source_statuses')}",
    )
    assert_true(
        int(lineage_detail.get("excluded_retired_history_rows") or 0) >= 1,
        f"retired_history rows should be excluded from current hash-match: {lineage_detail}",
    )
    mismatch_paths = {
        str(row.get("path") or "")
        for row in (lineage_detail.get("mismatches") or [])
        if isinstance(row, dict)
    }
    assert_true(
        "03. Alerts and Recommendations/Alert Bands and Invalidation Register.md" not in mismatch_paths,
        f"retired markdown register must not block current lineage hash-match: {mismatch_paths}",
    )

    tickers = client.production_answer_tickers()
    assert_true(len(tickers) == 0, f"expected 0 proof-joined production-grade tickers, got {len(tickers)}")

    legacy_tickers = client.legacy_production_answer_tickers()
    assert_true(len(legacy_tickers) == 0, f"expected retired legacy answer path to be empty, got {len(legacy_tickers)}")
    label_only_tickers = client.legacy_tier_a_ready_compatibility_tickers()
    assert_true(label_only_tickers == [], f"retired tier-routing labels remain: {label_only_tickers}")

    nvda = client.ticker_state("NVDA")
    assert_true(nvda is not None, "NVDA state missing")
    assert_true(nvda.ticker == "NVDA", f"unexpected ticker {nvda}")
    assert_true(nvda.legacy_production_42 is False, "NVDA must not expose the retired production 42 scope")
    assert_true(nvda.production_scope_member is False, "NVDA must not be strict production-scope without proof-joined gates")
    assert_true(nvda.compatibility_reason is None, f"unexpected compatibility reason: {nvda.compatibility_reason}")
    assert_true(nvda.sql_tier == "Tier A", f"NVDA should expose SQL-first tier: {nvda.sql_tier}")
    assert_true(nvda.tier_decision_scope == "tier_a_sql_first_review_scope", f"unexpected tier scope: {nvda.tier_decision_scope}")
    assert_true(nvda.production_card_generation_allowed is False, "NVDA card generation scope should be fail-closed")
    assert_true(nvda.auto_tier is None and nvda.auto_state is None, "retired WF78 routing fields must be empty")

    states = client.ticker_states(["NVDA", "VRT", "not-a-real-ticker"])
    assert_true(sorted(states) == ["NVDA", "VRT"], f"unexpected bulk ticker states: {sorted(states)}")
    assert_true(states["VRT"].legacy_production_42 is False, "VRT must not expose the retired production 42 scope")
    assert_true(states["VRT"].production_scope_member is False, "VRT should fail closed for strict production scope")

    grade_states = client.production_grade_states()
    assert_true(sorted(grade_states) == [], f"unexpected production-grade states: {sorted(grade_states)}")
    assert_true(all(row.auto_tier == "Tier A" and row.auto_state == "A-READY" for row in grade_states.values()), "production-grade states must be Tier A/A-READY")

    ref = client.reference_level("NVDA")
    assert_true(ref is not None, "NVDA reference level missing")
    assert_true(ref.reference_price_low is not None, "NVDA low reference should be populated")
    assert_true(ref.reference_price_high is not None, "NVDA high reference should be populated")
    assert_true(ref.reference_invalidation_level is not None, "NVDA invalidation reference should be populated")
    assert_true("alert_reference_metadata_review_only" in ref.authority_class, ref.authority_class)
    assert_true(
        set(asdict(ref)) == {
            "ticker",
            "reference_price_low",
            "reference_price_high",
            "reference_invalidation_level",
            "reference_confidence",
            "reference_band_status",
            "authority_class",
            "fallback_rule",
        },
        f"ReferenceLevel schema changed: {asdict(ref)}",
    )

    vrt_ref = client.reference_level("VRT")
    assert_true(vrt_ref is not None, "VRT reference level missing")
    assert_true(vrt_ref.reference_price_low is not None, "VRT low reference should be populated")
    assert_true(vrt_ref.reference_price_high is not None, "VRT high reference should be populated")
    assert_true(vrt_ref.reference_invalidation_level is not None, "VRT invalidation reference should be populated")

    fresh = client.evidence_freshness("NVDA")
    assert_true(fresh is not None, "NVDA freshness missing")
    assert_true("alert_evidence_metadata_review_only" in fresh.authority_class, fresh.authority_class)

    registry = client.migration_registry_summary()
    assert_true(p0_registry_lane_status(registry)["ok"], registry)
    assert_true(sum(registry["cutover_state_counts"].values()) >= 400, registry)
    assert_true(registry["cutover_state_counts"].get("sql_primary_guarded", 0) >= 21, registry)
    assert_true(registry["cutover_state_counts"].get("retired_alerts_os_pivot", 0) >= 192, registry)

    summary = client.field_family_summary()
    families = summary["field_families"]
    assert_true("ticker_state" in families, summary)
    assert_true("universe_membership" in families, summary)
    for family in [
        "ticker_state",
        "reference_levels",
        "source_lineage",
        "evidence_freshness",
        "tier_routing_state",
        "answer_path_scope",
        "universe_membership",
    ]:
        assert_true(family in families, f"{family} missing from field summary")
    assert_true(
        families["universe_membership"]["production_scope_rows"] == 0,
        f"strict production scope should be empty: {families['universe_membership']}",
    )
    assert_true(families["tier_routing_state"]["sql_primary_current_state"] is False, families["tier_routing_state"])
    assert_true(families["tier_routing_state"]["row_count"] == 0, families["tier_routing_state"])
    assert_true(families["tier_routing_state"]["canon_owner"] is False, families["tier_routing_state"])

    memberships = client.universe_memberships()
    assert_true(len(memberships) == 300, f"expected 300 SQL memberships, got {len(memberships)}")
    assert_true(list(memberships) == sorted(memberships), "memberships must be canonical-ticker ordered")
    assert_true(
        Counter(row.universe_scope for row in memberships.values())
        == {"active_internal_universe": 42, "review_100_monitor": 258},
        "unexpected guarded SQL scope distribution",
    )
    assert_true(
        Counter(row.tier for row in memberships.values()) == {"A": 15, "B": 17, "C": 268},
        "unexpected guarded SQL tier distribution",
    )
    scope_client = FinanceSqlCanonAccess()
    with mock.patch.object(scope_client, "universe_memberships", return_value=memberships) as scope_read:
        dynamic_scope = scope_client.dynamic_entitlement_scope()
    assert_true(scope_read.call_count == 1, "dynamic scope must read memberships exactly once")
    expected_dynamic = {
        ticker for ticker, row in memberships.items()
        if row.active and row.tier in {"A", "B"}
    }
    assert_true(set(dynamic_scope.tickers) == expected_dynamic, "dynamic scope omitted or added a membership")
    assert_true(
        all(row.decision_grade_eligible for row in dynamic_scope.memberships.values()),
        "current SQL fixture unexpectedly has decision-grade repair debt",
    )
    assert_true(dynamic_scope.overflow_tickers == (), "initial measured envelope should not overflow")
    with mock.patch.object(scope_client, "universe_memberships", return_value=memberships):
        overflow_scope = scope_client.dynamic_entitlement_scope(
            envelope_name="synthetic_small_envelope",
            envelope_count=1,
        )
    assert_true(
        overflow_scope.tickers == dynamic_scope.tickers and len(overflow_scope.overflow_tickers) == len(dynamic_scope.tickers) - 1,
        "over-envelope scope must remain complete and expose every overflow member",
    )
    payload = dynamic_scope.payload()
    assert_true(
        verify_dynamic_entitlement_payload(payload, dynamic_scope.fingerprint) == dynamic_scope.fingerprint,
        "dynamic payload fingerprint did not round-trip",
    )
    payload["members"][0]["tier"] = "C"
    try:
        verify_dynamic_entitlement_payload(payload, dynamic_scope.fingerprint)
    except DynamicEntitlementScopeError as exc:
        assert_true(str(exc) == "guarded_sql_scope_payload_fingerprint_mismatch", str(exc))
    else:
        raise AssertionError("changed child payload must fail closed")
    debt_memberships = dict(memberships)
    debt_memberships["NVDA"] = replace(debt_memberships["NVDA"], decision_grade_eligible=False)
    with mock.patch.object(scope_client, "universe_memberships", return_value=debt_memberships):
        debt_scope = scope_client.dynamic_entitlement_scope()
    assert_true("NVDA" in debt_scope.memberships, "decision-grade false membership was silently omitted")
    assert_true(
        debt_scope.integrity_breaches == (),
        f"eligibility debt must not be a structural breach: {debt_scope.integrity_breaches}",
    )
    assert_true(
        debt_scope.eligibility_debt == ("NVDA",),
        f"eligibility debt must name the ineligible member: {debt_scope.eligibility_debt}",
    )
    debt_payload = debt_scope.payload()
    assert_true(
        debt_payload["eligibility_debt"] == ["NVDA"] and debt_payload["eligibility_debt_count"] == 1,
        f"payload must expose eligibility debt: {debt_payload.get('eligibility_debt')}",
    )
    assert_true(
        "not_decision_or_recommendation_ready" in debt_payload["debt_label"],
        f"debt label must deny readiness: {debt_payload.get('debt_label')}",
    )
    assert_true(
        verify_dynamic_entitlement_payload(debt_payload, debt_scope.fingerprint) == debt_scope.fingerprint,
        "debt payload fingerprint did not round-trip (false encoding must be preserved)",
    )
    nvda_member = [m for m in debt_payload["members"] if m["ticker"] == "NVDA"][0]
    assert_true(
        nvda_member["decision_grade_eligible"] is False,
        "false eligibility flag must be preserved in fingerprint and membership",
    )
    understated = dict(debt_payload)
    understated["eligibility_debt"] = []
    try:
        verify_dynamic_entitlement_payload(understated, debt_scope.fingerprint)
    except DynamicEntitlementScopeError as exc:
        assert_true(str(exc) == "guarded_sql_scope_payload_fingerprint_mismatch", str(exc))
    else:
        raise AssertionError("understated debt annotation must fail closed")
    legacy_payload = {key: value for key, value in debt_payload.items() if key != "eligibility_debt"}
    assert_true(
        verify_dynamic_entitlement_payload(legacy_payload, debt_scope.fingerprint) == debt_scope.fingerprint,
        "legacy payload without annotation must remain compatible (debt derived from flags)",
    )
    admitted = require_dynamic_entitlement_external_gate(
        debt_scope,
        scope_origin="phase3f_dynamic_entitlement",
        policy=mock.Mock(),
    )
    assert_true(admitted is not None, "debt-only scope must reach evidence intake")
    conflict_memberships = dict(memberships)
    conflict_memberships["NVDA"] = replace(conflict_memberships["NVDA"], sql_tier="Tier B")
    with mock.patch.object(scope_client, "universe_memberships", return_value=conflict_memberships):
        try:
            scope_client.dynamic_entitlement_scope()
        except DynamicEntitlementScopeError as exc:
            assert_true(str(exc) == "guarded_sql_scope_tier_conflict", str(exc))
        else:
            raise AssertionError("tier witness conflict must fail the full dynamic scope")
    conflicting_raw_rows = [
        row
        for row in memberships.values()
        if row.raw_json.get("universe_scope") != row.universe_scope
        or row.raw_json.get("tier") != row.tier
    ]
    assert_true(bool(conflicting_raw_rows), "expected a legacy raw_json scope/tier conflict fixture")
    assert_true(
        all(row.universe_scope in {"active_internal_universe", "review_100_monitor"} for row in conflicting_raw_rows),
        "typed SQL scope did not override legacy raw_json",
    )

    alias_rows = [
        row
        for row in memberships.values()
        if row.yfinance_symbol.upper() != row.ticker.upper()
    ]
    assert_true(bool(alias_rows), "expected a nontrivial provider identity alias")
    alias_row = alias_rows[0]
    assert_true(
        client.resolve_tickers([alias_row.yfinance_symbol]) == {
            alias_row.yfinance_symbol.upper(): alias_row.ticker
        },
        "provider alias did not resolve to canonical identity",
    )
    invalid_alias = alias_row.yfinance_symbol + "_INVALID"
    try:
        client.resolve_tickers([invalid_alias])
    except ValueError:
        pass
    else:
        raise AssertionError("dynamically constructed invalid identity must fail closed")

    reference_records = client.reference_level_records()
    verified_records = [row for row in reference_records.values() if row is not None]
    unavailable_records = [ticker for ticker, row in reference_records.items() if row is None]
    assert_true(len(reference_records) == 300, f"unexpected reference identity count: {len(reference_records)}")
    assert_true(len(verified_records) == 42, f"expected 42 fully verified reference records, got {len(verified_records)}")
    assert_true(len(unavailable_records) == 258, f"expected 258 missing/provenance-blocked records, got {len(unavailable_records)}")
    assert_true(
        client.reference_level_record(unavailable_records[0]) is None,
        "known identity without fully verified reference provenance must return None",
    )
    nvda_record = client.reference_level_record("NVDA")
    assert_true(nvda_record is not None, "NVDA verified reference record missing")
    assert_true(set(nvda_record.lineage_field_names) == REFERENCE_LEVEL_LINEAGE_FIELDS, nvda_record.lineage_field_names)
    assert_true(nvda_record.source_status == "ok" and nvda_record.validator_status == "ok", asdict(nvda_record))
    source_path = ROOT / nvda_record.source_artifact_path
    assert_true(source_path.exists(), f"NVDA source artifact missing: {source_path}")
    assert_true(
        hashlib.sha256(source_path.read_bytes()).hexdigest() == nvda_record.source_artifact_sha256,
        "NVDA durable source artifact hash mismatch",
    )
    assert_true(bool(nvda_record.source_generated_at_utc), "NVDA source timestamp missing")

    with tempfile.TemporaryDirectory() as tmp_dir:
        missing_db = Path(tmp_dir) / "missing-finance-canon.sqlite"
        missing_client = FinanceSqlCanonAccess(missing_db)
        try:
            missing_client.universe_memberships()
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing finance-canon DB must fail closed")
        assert_true(not missing_db.exists(), "read-only guard created a fallback database")

    print("finance_sql_canon_access tests OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
