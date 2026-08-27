#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone

import wf78_auto_tier_router as router


def test_classify_operating_company_equity() -> None:
    row = {"ticker": "NVDA", "instrument_type": "operating_company", "sector": "Tech"}
    lane = router.classify_instrument(row)
    assert lane["review_lane"] == "equity_depth"
    assert lane["instrument_class"] == "operating_company"
    assert router.lane_tier("Tier A", lane["review_lane"]) == "Tier A Equity"


def test_classify_etf_sleeve_and_existing_special_proxies() -> None:
    sleeve = router.classify_instrument({"ticker": "XLF", "instrument_type": "etf", "sector": "Financials"})
    commodity = router.classify_instrument({"ticker": "SLV", "instrument_type": "commodity_proxy", "sector": "Commodities"})
    rates = router.classify_instrument({"ticker": "TLT", "instrument_type": "bond_or_rate_proxy", "sector": "Fixed Income"})
    crypto = router.classify_instrument({"ticker": "IBIT", "instrument_type": "", "sector": ""})
    assert sleeve["review_lane"] == "sleeve_proxy"
    assert router.lane_tier("Tier A", sleeve["review_lane"]) == "Tier A Sleeve"
    assert commodity["review_lane"] == "commodity_proxy"
    assert router.lane_tier("Tier A", commodity["review_lane"]) == "Tier A Commodity"
    assert rates["review_lane"] == "rates_income_proxy"
    assert router.lane_tier("Tier B", rates["review_lane"]) == "Tier B Rates/Income"
    assert crypto["review_lane"] == "crypto_proxy"


def test_lane_family_count_uses_lane_qualified_tiers() -> None:
    counts = {
        "Tier A Equity": 14,
        "Tier A Sleeve": 1,
        "Tier B Equity": 43,
        "Tier B Sleeve": 1,
        "Tier C Equity": 241,
    }

    assert router.lane_family_count(counts, "Tier A") == 15
    assert router.lane_family_count(counts, "Tier B") == 44


def test_sync_lane_tier_fields_recomputes_demoted_rows() -> None:
    row = {
        "ticker": "VRT",
        "auto_tier": "Tier B",
        "opportunity_tier": "Tier A",
        "review_lane": "equity_depth",
        "lane_tier": "Tier A Equity",
        "lane_tier_label": "Tier A Equity",
    }
    synced = router.sync_lane_tier_fields(row)
    assert synced["opportunity_tier"] == "Tier B"
    assert synced["lane_tier"] == "Tier B Equity"
    assert synced["lane_tier_label"] == "Tier B Equity"


def test_phase2_evidence_complete_validates_existing_tier_b() -> None:
    row = router.route_entry(
        {
            "ticker": "ACN",
            "name": "Accenture",
            "tier": "B",
            "instrument_type": "operating_company",
            "sector": "Information Technology",
        },
        {},
        None,
        {},
        set(),
        {"ACN"},
        set(),
        {},
        {},
        {},
        datetime.now(timezone.utc),
    )

    assert row["auto_tier"] == "Tier B"
    assert row["auto_state"] == "B-VALIDATED"
    assert row["phase2_validated_tier_b"] is True
    assert row["route_reason"] == "phase2_research_packet_evidence_complete_validated_existing_tier_b_non_capital"
    assert row["capital_deployment_approved"] is False
    assert row["trade_or_execution_approved"] is False


def test_phase2_evidence_complete_does_not_create_new_tier_b_admission() -> None:
    row = router.route_entry(
        {
            "ticker": "NEWC",
            "name": "New Candidate",
            "tier": "C",
            "instrument_type": "operating_company",
            "sector": "Information Technology",
        },
        {},
        None,
        {},
        set(),
        set(),
        {"NEWC"},
        {},
        {},
        {},
        datetime.now(timezone.utc),
    )

    assert row["auto_tier"] == "Tier C"
    assert row["auto_state"] == "C-CANDIDATE-HOLD"
    assert row["phase2_validated_tier_b"] is False
    assert row["route_reason"] == "phase2_eligible_but_auto_router_holds_for_quality_capacity_or_caution_burden"


def test_tier_b_cap_moves_low_priority_overflow_to_candidate_hold() -> None:
    rows = [
        {
            "ticker": f"B{index:02d}",
            "auto_tier": "Tier B",
            "auto_state": "B-CANDIDATE",
            "route_priority": 20,
            "route_reason": "existing_research_bench",
            "review_lane": "equity_depth",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
        for index in range(router.TIER_B_CAP)
    ]
    rows.append({
        "ticker": "OVERFLOW",
        "auto_tier": "Tier B",
        "auto_state": "B-CHALLENGED",
        "route_priority": 25,
        "route_reason": "confidence_demotion",
        "review_lane": "equity_depth",
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
    })

    capped, held = router.enforce_tier_b_row_cap(rows)
    overflow = next(row for row in capped if row["ticker"] == "OVERFLOW")

    assert held == ["OVERFLOW"]
    assert sum(row["auto_tier"] == "Tier B" for row in capped) == router.TIER_B_CAP
    assert overflow["auto_tier"] == "Tier C"
    assert overflow["auto_state"] == "C-CANDIDATE-HOLD"
    assert overflow["lane_tier"] == "Tier C Equity"
    assert overflow["capital_deployment_approved"] is False
    assert overflow["trade_or_execution_approved"] is False
    assert "auto_demoted_to_c_hold_by_tier_b_capacity_cap" in overflow["route_reason"]


if __name__ == "__main__":
    test_classify_operating_company_equity()
    test_classify_etf_sleeve_and_existing_special_proxies()
    test_lane_family_count_uses_lane_qualified_tiers()
    test_sync_lane_tier_fields_recomputes_demoted_rows()
    test_phase2_evidence_complete_validates_existing_tier_b()
    test_phase2_evidence_complete_does_not_create_new_tier_b_admission()
    test_tier_b_cap_moves_low_priority_overflow_to_candidate_hold()
    print("wf78_auto_tier_router tests passed")
