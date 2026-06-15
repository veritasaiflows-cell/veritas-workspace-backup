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
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
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
    stale = stale_required_sources(
        [{
            "path": "data/finance/universe-v1.json",
            "required_for_mvp": True,
            "exists_on_disk": True,
            "generated_at_utc": "2026-01-01T00:00:00Z",
            "mtime_utc": "2026-01-01T00:00:00Z",
        }],
        "2026-06-11T00:00:00Z",
    )
    expect(not stale, "durable universe registry age alone should not block WF84 freshness", errors)
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
    if errors:
        print("canonical_finance_data_plane_repair_semantics_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("canonical_finance_data_plane_repair_semantics_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
