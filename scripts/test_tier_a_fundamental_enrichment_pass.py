from __future__ import annotations

import pytest

import tier_a_fundamental_enrichment_pass as mod


def test_yfinance_is_not_official_in_authority_boundary() -> None:
    payload = mod.build_payload(["BRK.B"], fetch_sec=False)

    assert payload["authority_boundary"]["yfinance_is_official_source"] is False
    assert payload["authority_boundary"]["sec_companyfacts_is_official_api"] is True


def test_derived_book_value_uses_equity_share_count_and_price() -> None:
    row = {"total_equity": 727_181_000_000, "diluted_average_shares": 2_157_185_889}
    card = {"price_band_stop": {"latest_known_price": 489.46}}

    derived = mod.derived_book_value(row, card)

    assert derived["book_value_per_diluted_share"] == pytest.approx(337.097, abs=0.001)
    assert derived["price_to_book_derived"] == pytest.approx(1.4519, abs=0.0001)


def test_official_capture_summary_extracts_addressed_fields() -> None:
    bridge_row = {
        "status": "manual_confirmed_official_source",
        "manual_review_required": True,
        "official_earnings_bridge": {
            "source_authority_level": "manual_confirmed_official_source",
            "official_capture": {
                "captured_fields": ["segment_margins", "acquisition_debt_notes"],
                "addressed_fields": ["segment_margins", "guidance"],
            },
            "segment_margins": {"status": "partial", "value": {"segment_operating_income": 123}},
            "guidance": {"status": "not_disclosed_in_release", "value": None},
            "evidence_claims": [{"claim_type": "official_capture_segment_margins"}],
        },
    }

    summary = mod.official_capture_summary(bridge_row)

    assert summary["status"] == "manual_confirmed_official_source"
    assert summary["captured_fields"] == ["segment_margins", "acquisition_debt_notes"]
    assert summary["addressed_fields"] == ["segment_margins", "guidance"]
    assert summary["captured_values"]["segment_margins"]["value"]["segment_operating_income"] == 123


def test_validation_blocks_forbidden_authority_flags() -> None:
    payload = mod.build_payload(["BRK.B"], fetch_sec=False)
    payload["authority_boundary"]["capital_deployment_allowed"] = True

    checks = mod.validate_payload(payload)
    failed = {check["name"] for check in checks if not check["ok"]}

    assert "authority_capital_deployment_allowed_false" in failed
