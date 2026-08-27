#!/usr/bin/env python3
"""Focused regressions for WF84 repair-state coverage semantics."""
from __future__ import annotations

from canonical_finance_data_plane import (
    DURABLE_REGISTRY_SOURCE_PATHS,
    FINANCE_STATE_DB,
    NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS,
    stale_required_sources,
    price_row_with_tier_c_monitor_context,
    review_price_context_from_price_row,
    section_presence_score,
    source_meta,
    technical_posture_from_price_row,
    validate_tables,
)
import canonical_finance_data_plane as cfdp


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_validate_tables_accepts_active_internal_non_production_wait_state(errors: list[str]) -> None:
    old_sections = cfdp.FULL_ANSWER_SECTION_SOURCES
    old_feeder = cfdp.feeder_authority_violations
    cfdp.FULL_ANSWER_SECTION_SOURCES = [("identity", None, "universe_metadata")]
    cfdp.feeder_authority_violations = lambda: []
    try:
        tables = {name: [] for name in cfdp.TABLE_ORDER}
        tables["source_artifact"] = [{"artifact_id": "src_router", "required_for_mvp": False, "exists_on_disk": True, "path": "tmp/test.json", "schema": "test"}]
        tables["security_master"] = [{"ticker": "AAA"}, {"ticker": "BBB"}]
        tables["universe_membership"] = [
            {
                "ticker": "AAA",
                "universe_scope": "review_100_monitor",
                "production_answer_path_member": False,
                "thin_monitor_row": True,
                "decision_grade_eligible": False,
                "source_open_required": True,
            },
            {
                "ticker": "BBB",
                "universe_scope": "active_internal_universe",
                "production_answer_path_member": False,
                "thin_monitor_row": False,
                "decision_grade_eligible": False,
                "source_open_required": True,
            },
        ]
        tables["routing_state_current"] = [
            {
                "ticker": "AAA",
                "auto_tier": "Tier C",
                "auto_state": "C-MONITOR",
                "critical_data_conflict_count": 0,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "source_artifact_id": "src_router",
            },
            {
                "ticker": "BBB",
                "auto_tier": "Tier A",
                "auto_state": "A-WATCH",
                "critical_data_conflict_count": 0,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "source_artifact_id": "src_router",
            },
        ]
        tables["full_answer_section_context"] = [
            {"ticker": "AAA", "section_id": "identity", "source_open_required": True},
            {"ticker": "BBB", "section_id": "identity", "source_open_required": True},
        ]
        tables["price_technical_current"] = [
            {"ticker": "AAA", "source_artifact_id": "src_router"},
            {"ticker": "BBB", "source_artifact_id": "src_router"},
        ]
        tables["decision_queue_state"] = [
            {
                "ticker": "AAA",
                "actionability": "review_only",
                "paper_or_live_execution_allowed": False,
                "owner_action_required": False,
            },
            {
                "ticker": "BBB",
                "actionability": "review_only",
                "paper_or_live_execution_allowed": False,
                "owner_action_required": False,
            },
        ]
        validation = validate_tables(
            tables,
            {"capital_deployment_approved_count": 0, "trade_or_execution_approved_count": 0},
            {
                "generated_at_utc": "2026-06-24T00:00:00Z",
                "router_tickers": ["AAA", "BBB"],
                "finance_universe_tickers": ["AAA"],
                "tier_weighted_tickers": ["AAA", "BBB"],
                "decision_spine_tickers": ["AAA", "BBB"],
            },
        )
    finally:
        cfdp.FULL_ANSWER_SECTION_SOURCES = old_sections
        cfdp.feeder_authority_violations = old_feeder
    check = next(item for item in validation["checks"] if item["check_name"] == "router_ticker_set_matches_finance_state_universe")
    expect(check["status"] == "ok", "active_internal_universe non-production rows should not block strict finance-state wait state", errors)


def check_validate_tables_uses_lane_qualified_caps_when_available(errors: list[str]) -> None:
    old_sections = cfdp.FULL_ANSWER_SECTION_SOURCES
    old_feeder = cfdp.feeder_authority_violations
    cfdp.FULL_ANSWER_SECTION_SOURCES = [("identity", None, "universe_metadata")]
    cfdp.feeder_authority_violations = lambda: []
    try:
        tickers = [f"T{i:03d}" for i in range(100)]
        tables = {name: [] for name in cfdp.TABLE_ORDER}
        tables["source_artifact"] = [
            {
                "artifact_id": "src_router",
                "path": "tmp/wf78-auto-tier-routing.json",
                "schema": "veritas.wf78_auto_tier_router.v1",
                "required_for_mvp": False,
                "exists_on_disk": True,
            }
        ]
        tables["security_master"] = [{"ticker": ticker} for ticker in tickers]
        tables["universe_membership"] = [
            {
                "ticker": ticker,
                "universe_scope": "active_internal_universe",
                "production_answer_path_member": False,
                "thin_monitor_row": False,
                "decision_grade_eligible": False,
                "source_open_required": True,
            }
            for ticker in tickers
        ]
        tables["routing_state_current"] = [
            {
                "ticker": tickers[0],
                "auto_tier": "Tier A",
                "auto_state": "A-WATCH",
                "critical_data_conflict_count": 0,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "source_artifact_id": "src_router",
            },
            *[
                {
                    "ticker": ticker,
                    "auto_tier": "Tier B",
                    "auto_state": "B-CANDIDATE",
                    "critical_data_conflict_count": 0,
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "source_artifact_id": "src_router",
                }
                for ticker in tickers[1:59]
            ],
            *[
                {
                    "ticker": ticker,
                    "auto_tier": "Tier C",
                    "auto_state": "C-MONITOR",
                    "critical_data_conflict_count": 0,
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                    "source_artifact_id": "src_router",
                }
                for ticker in tickers[59:]
            ],
        ]
        tables["full_answer_section_context"] = [
            {"ticker": ticker, "section_id": "identity", "source_open_required": True}
            for ticker in tickers
        ]
        tables["price_technical_current"] = [
            {"ticker": ticker, "source_artifact_id": "src_router"}
            for ticker in tickers
        ]
        tables["decision_queue_state"] = [
            {
                "ticker": ticker,
                "actionability": "review_only",
                "paper_or_live_execution_allowed": False,
                "owner_action_required": False,
            }
            for ticker in tickers
        ]
        validation = validate_tables(
            tables,
            {
                "capital_deployment_approved_count": 0,
                "trade_or_execution_approved_count": 0,
                "flat_auto_tier_compatibility_retained": True,
                "lane_tier_counts": {
                    "Tier A Equity": 14,
                    "Tier A Sleeve": 1,
                    "Tier B Equity": 43,
                    "Tier B Sleeve": 1,
                },
            },
            {
                "generated_at_utc": "2026-06-24T00:00:00Z",
                "router_tickers": tickers,
                "finance_universe_tickers": tickers,
                "tier_weighted_tickers": tickers,
                "decision_spine_tickers": tickers,
            },
        )
    finally:
        cfdp.FULL_ANSWER_SECTION_SOURCES = old_sections
        cfdp.feeder_authority_violations = old_feeder

    expect("tier_b_cap" not in validation["errors"], "flat Tier B compatibility count should not block lane-qualified WF84 caps", errors)
    expect(
        any(item["check_name"] == "flat_auto_tier_b_cap_compatibility_classified" for item in validation["checks"]),
        "flat Tier B compatibility over-cap should remain classified",
        errors,
    )


def collect_errors() -> list[str]:
    errors: list[str] = []
    check_validate_tables_accepts_active_internal_non_production_wait_state(errors)
    check_validate_tables_uses_lane_qualified_caps_when_available(errors)
    expect(
        section_presence_score({"status": "source_open_required"}) == 0.0,
        "source_open_required placeholders should not count as substantive section coverage",
        errors,
    )
    expect(
        "data/finance/universe-v1.json" in DURABLE_REGISTRY_SOURCE_PATHS,
        "universe registry should be classified as a durable registry source",
        errors,
    )
    expect(
        "state/finance/finance-canon.sqlite" in DURABLE_REGISTRY_SOURCE_PATHS,
        "guarded SQL canon should be classified as a durable registry source",
        errors,
    )
    stale = stale_required_sources(
        [
            {
                "path": "data/finance/universe-v1.json",
                "required_for_mvp": True,
                "exists_on_disk": True,
                "generated_at_utc": "2026-01-01T00:00:00Z",
                "mtime_utc": "2026-01-01T00:00:00Z",
            },
            {
                "path": "state/finance/finance-canon.sqlite",
                "required_for_mvp": True,
                "exists_on_disk": True,
                "generated_at_utc": None,
                "mtime_utc": "2026-01-01T00:00:00Z",
            },
        ],
        "2026-06-11T00:00:00Z",
    )
    expect(not stale, "durable registry age alone should not block WF84 freshness", errors)
    repair = technical_posture_from_price_row({
        "technical_status": "missing_required_refresh",
        "technical_summary": "thin monitor: price/technical refresh required",
        "source_path": "tmp/finance-data-coverage-current.json",
        "raw_json": "{\"technical_posture\":{\"latest_close\":null,\"ma20\":null}}",
    })
    expect(repair.get("status") == "missing_required_refresh", "technical repair status should be explicit", errors)
    expect(repair.get("repair_required") is True, "technical repair state should keep repair_required=true", errors)
    expect(repair.get("source_path") == "tmp/finance-data-coverage-current.json", "technical repair state should retain source path", errors)
    expect(
        repair.get("source_open_required_before_material_claims") is True,
        "technical repair state should keep material-claim source-open boundary",
        errors,
    )
    stale_low_confidence_reference_band = cfdp.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    )
    expect(
        stale_low_confidence_reference_band is True,
        "Tier A low-confidence fallback without current technicals must suppress a hard below-stop claim",
        errors,
    )
    complete_current_technical = {
        "close": 178.49,
        "ma20": 185.0,
        "ma50": 190.0,
        "ma200": 200.0,
        "data_date": "2026-08-14",
    }
    expect(
        cfdp.technical_record_is_complete_and_current(complete_current_technical, "2026-08-14") is True,
        "fixture must represent a complete, current technical record",
        errors,
    )
    expect(
        cfdp.low_confidence_reference_band_requires_refresh(
            {"auto_tier": "Tier A"},
            {"reference_confidence": 2},
            "BELOW_STOP",
        ) is True,
        "Current technicals must not rehabilitate a low-confidence legacy reference band",
        errors,
    )
    expect(
        cfdp.low_confidence_reference_band_requires_refresh(
            {"auto_tier": "Tier A"},
            {"reference_confidence": 3},
            "BELOW_STOP",
        ) is False,
        "A refreshed/high-confidence Tier A reference band may expose its computed stop state",
        errors,
    )
    expect(
        cfdp.low_confidence_reference_band_requires_refresh(
            {"auto_tier": "Tier B"},
            {"reference_confidence": 2},
            "BELOW_STOP",
        ) is False,
        "Tier B/C must not be pulled into the Tier A suppression rule",
        errors,
    )
    price_context = review_price_context_from_price_row({
        "latest_known_price": 123.45,
        "price_source": "tmp/ticker-intelligence-cards/TEST.current.json",
        "raw_json": "{\"price_band_stop\":{\"latest_known_price\":123.45},\"technical_posture\":{\"data_date\":\"2026-06-10\",\"latest_close\":123.45}}",
    })
    expect(
        price_context.get("quote_freshness_status") == NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS,
        "current technical price should be explicit non-execution review freshness",
        errors,
    )
    expect(price_context.get("market_date") == "2026-06-10", "technical data_date should become market_date", errors)
    tier_c_context = price_row_with_tier_c_monitor_context(
        {"raw_json": "{}"},
        {
            "technical_input_status": "ok",
            "latest_price": 59.19,
            "data_date": "2026-06-10",
            "band_status": "BELOW_STOP",
            "trend_stack": "BELOW_ALL_MAS",
            "confidence": 3,
            "reference_source": "provider_calculated_monitor_band",
        },
    )
    tier_c_price = review_price_context_from_price_row(tier_c_context)
    expect(tier_c_context.get("technical_status") == "monitor_grade_current", "Tier C fallback should mark monitor-grade technical status", errors)
    expect(
        tier_c_price.get("quote_freshness_status") == NON_EXECUTION_TECHNICAL_PRICE_FRESHNESS,
        "Tier C fallback should provide non-execution review freshness",
        errors,
    )
    if FINANCE_STATE_DB.exists():
        sqlite_source = source_meta(FINANCE_STATE_DB, role="test sqlite feeder", source_type="sqlite", required=True, rank=1)
        expect(sqlite_source.get("status") == "ok", "existing SQLite feeder should expose ok source status", errors)
        expect(sqlite_source.get("validation_status") == "ok", "existing SQLite feeder should expose ok validation status", errors)
    return errors


def test_repair_semantics() -> None:
    assert collect_errors() == []


def main() -> int:
    errors = collect_errors()
    if errors:
        print("canonical_finance_data_plane_repair_semantics_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("canonical_finance_data_plane_repair_semantics_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
