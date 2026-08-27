#!/usr/bin/env python3
"""Focused tests for the finance SQL-canon typed access layer."""

from __future__ import annotations

from finance_sql_canon_access import FinanceSqlCanonAccess, p0_registry_lane_status


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    client = FinanceSqlCanonAccess()
    validation = client.validate()
    assert_true(validation["status"] == "ok", f"validation blocked: {validation['errors']}")

    tickers = client.production_answer_tickers()
    assert_true(len(tickers) == 0, f"expected 0 proof-joined production-grade tickers, got {len(tickers)}")

    legacy_tickers = client.legacy_production_answer_tickers()
    assert_true(len(legacy_tickers) == 0, f"expected retired legacy answer path to be empty, got {len(legacy_tickers)}")
    label_only_tickers = client.legacy_tier_a_ready_compatibility_tickers()
    assert_true(label_only_tickers == ["GOOG", "NVDA", "VRT"], f"unexpected label-only Tier A/A-READY tickers: {label_only_tickers}")

    nvda = client.ticker_state("NVDA")
    assert_true(nvda is not None, "NVDA state missing")
    assert_true(nvda.ticker == "NVDA", f"unexpected ticker {nvda}")
    assert_true(nvda.legacy_production_42 is False, "NVDA must not expose the retired production 42 scope")
    assert_true(nvda.production_scope_member is False, "NVDA must not be strict production-scope without proof-joined gates")
    assert_true(nvda.compatibility_reason is None, f"unexpected compatibility reason: {nvda.compatibility_reason}")
    assert_true(nvda.sql_tier == "Tier A", f"NVDA should expose SQL-first tier: {nvda.sql_tier}")
    assert_true(nvda.tier_decision_scope == "tier_a_sql_first_review_scope", f"unexpected tier scope: {nvda.tier_decision_scope}")
    assert_true(nvda.production_card_generation_allowed is False, "NVDA card generation scope should be fail-closed")

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
    assert_true("no_deployment_authority" in ref.authority_class, ref.authority_class)

    vrt_ref = client.reference_level("VRT")
    assert_true(vrt_ref is not None, "VRT reference level missing")
    assert_true(vrt_ref.reference_price_low is not None, "VRT low reference should be populated")
    assert_true(vrt_ref.reference_price_high is not None, "VRT high reference should be populated")
    assert_true(vrt_ref.reference_invalidation_level is not None, "VRT invalidation reference should be populated")

    fresh = client.evidence_freshness("NVDA")
    assert_true(fresh is not None, "NVDA freshness missing")
    assert_true("no_capital_authority" in fresh.authority_class, fresh.authority_class)

    registry = client.migration_registry_summary()
    assert_true(p0_registry_lane_status(registry)["ok"], registry)
    assert_true(sum(registry["cutover_state_counts"].values()) >= 400, registry)
    assert_true(registry["cutover_state_counts"].get("sql_primary_guarded", 0) >= 21, registry)
    assert_true(registry["cutover_state_counts"].get("source_producer", 0) >= 300, registry)

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

    print("finance_sql_canon_access tests OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
