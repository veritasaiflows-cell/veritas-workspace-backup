#!/usr/bin/env python3
"""Regression tests for SQL-first band display in WF85 paper alerts."""

from __future__ import annotations

import morning_paper_deployment_recommendation_builder as morning
import wf85_paper_deployment_notification_digest as digest


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def ref(low: float, high: float, stop: float, status: str | None = None) -> dict:
    return {
        "reference_price_low": low,
        "reference_price_high": high,
        "reference_invalidation_level": stop,
        "reference_band_status": status,
        "source_artifact_path": "tmp/band-proposals.json",
        "source_generated_at_utc": "2026-06-23T14:30:00Z",
        "fallback_rule": "fallback_to_band_proposals_or_owner_notes",
        "authority_class": "reference_metadata_review_only_no_deployment_authority",
    }


def test_morning_effective_band_fields(errors: list[str]) -> None:
    item = {
        "ticker": "NVDA",
        "current_band_status": "IN_BAND",
        "entry_band_low": 202.81,
        "entry_band_high": 212.23,
        "stop_or_invalidation": 192.95,
    }
    canonical = {
        "band_status": "IN_BAND",
        "entry_band_low": 190.79,
        "entry_band_high": 212.04,
        "stop_or_invalidation": 181.12,
    }
    fields = morning.effective_band_fields(item, canonical, 200.46)
    expect(fields["band_status"] == "IN_BAND", f"NVDA should be inside SQL band: {fields}", errors)
    expect(fields["entry_band_low"] == 190.79, f"SQL low should win: {fields}", errors)
    expect(fields["prior_reclaim_not_met"] is True, f"prior reclaim filter should remain visible: {fields}", errors)
    expect(fields["band_display_conflict"] is False, f"final displayed SQL band should not conflict: {fields}", errors)


def test_digest_sql_overlay_and_conflict_guard(errors: list[str]) -> None:
    references = {"NVDA": ref(190.79, 212.04, 181.12, "IN_BAND")}
    row = {
        "ticker": "NVDA",
        "current_price": 200.46,
        "band_status": "IN_BAND",
        "entry_band_low": 202.81,
        "entry_band_high": 212.23,
        "stop_or_invalidation": 192.95,
        "blockers": [],
    }
    overlaid = digest.apply_sql_reference(row, references)
    expect(overlaid["entry_band_low"] == 190.79, f"digest should display SQL low: {overlaid}", errors)
    expect(overlaid["band_status"] == "IN_BAND", f"digest should recompute from SQL band: {overlaid}", errors)
    expect(overlaid["prior_reclaim_not_met"] is True, f"digest should keep prior reclaim filter: {overlaid}", errors)
    expect(overlaid["band_display_conflict"] is False, f"SQL overlay should resolve final display conflict: {overlaid}", errors)

    no_sql = digest.apply_sql_reference(row, {})
    expect(no_sql["band_display_conflict"] is True, f"without SQL overlay stale display must conflict: {no_sql}", errors)
    expect(no_sql["band_status"] == "BELOW_BAND", f"conflict row should be recomputed below old display band: {no_sql}", errors)


def test_morning_rows_route_prior_reclaim_to_watch(errors: list[str]) -> None:
    morning_packet = {
        "cards": [
            {
                "ticker": "NVDA",
                "clean_for_randall_approval_review": False,
                "status": "blocked_or_not_clean_for_approval",
                "current_price": 200.46,
                "band_status": "IN_BAND",
                "entry_band_low": 202.81,
                "entry_band_high": 212.23,
                "stop_or_invalidation": 192.95,
                "blockers": ["promotion_gate_vetoes_present"],
            }
        ]
    }
    rows = digest.build_morning_rows(morning_packet, {"NVDA": ref(190.79, 212.04, 181.12, "IN_BAND")})
    expect(len(rows) == 1, f"expected one morning row: {rows}", errors)
    if rows:
        row = rows[0]
        expect(row.get("digest_category") == "watch", f"below-prior-reclaim row should not be near-deployment: {row}", errors)
        expect("prior_reclaim_band_not_reclaimed" in row.get("blockers", []), f"prior reclaim blocker missing: {row}", errors)


def test_tier_a_mismatch_rows_display_sql(errors: list[str]) -> None:
    references = {
        "GOOG": ref(342.43, 368.17, 328.13),
        "GS": ref(978.37, 1054.44, 936.11),
        "JPM": ref(301.50, 307.78, 293.93),
    }
    stale_rows = {
        "GOOG": (354.25, 369.69, 341.07, 348.78),
        "GS": (971.53, 1048.14, 928.97, 1000.00),
        "JPM": (304.96, 315.95, 296.21, 304.00),
    }
    for ticker, (old_low, old_high, old_stop, price) in stale_rows.items():
        overlaid = digest.apply_sql_reference(
            {
                "ticker": ticker,
                "latest_known_price": price,
                "band_status": "IN_BAND",
                "entry_band_low": old_low,
                "entry_band_high": old_high,
                "stop_or_invalidation": old_stop,
            },
            references,
        )
        expected = references[ticker]
        expect(overlaid["entry_band_low"] == expected["reference_price_low"], f"{ticker} low did not use SQL: {overlaid}", errors)
        expect(overlaid["entry_band_high"] == expected["reference_price_high"], f"{ticker} high did not use SQL: {overlaid}", errors)
        expect(overlaid["stop_or_invalidation"] == expected["reference_invalidation_level"], f"{ticker} stop did not use SQL: {overlaid}", errors)


def main() -> int:
    errors: list[str] = []
    test_morning_effective_band_fields(errors)
    test_digest_sql_overlay_and_conflict_guard(errors)
    test_morning_rows_route_prior_reclaim_to_watch(errors)
    test_tier_a_mismatch_rows_display_sql(errors)
    if errors:
        print("sql_first_band_alert_integrity_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("sql_first_band_alert_integrity_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
