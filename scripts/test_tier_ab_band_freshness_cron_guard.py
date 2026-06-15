#!/usr/bin/env python3
"""Regression checks for Tier A/B band freshness cron guard."""
from __future__ import annotations

from tier_ab_band_freshness_cron_guard import decision_grade_band_missing, tier_band_rows


def card(
    ticker: str,
    tier: str = "Tier B",
    market_date: str | None = "2026-06-10",
    band_status: str | None = "IN_BAND",
    low: float | None = 10.0,
    high: float | None = 12.0,
    stop: float | None = 9.0,
    quote_status: str = "post_close_final_quote_available_for_non_executing_review",
) -> dict:
    return {
        "ticker": ticker,
        "auto_tier": tier,
        "current_price": {
            "latest_known_price": 11.0 if market_date else None,
            "market_date": market_date,
            "quote_freshness_status": quote_status,
        },
        "entry_band": {
            "low": low,
            "high": high,
            "band_status": band_status,
            "source_timestamp": "2026-06-10" if low is not None else None,
        },
        "stop_or_invalidation": {
            "level": stop,
            "source_timestamp": "2026-06-10" if stop is not None else None,
        },
    }


def main() -> int:
    assert decision_grade_band_missing(card("OK")) is False
    assert decision_grade_band_missing(card("NOLOW", low=None)) is True
    assert decision_grade_band_missing(card("NOSTOP", stop=None)) is True
    assert decision_grade_band_missing(card("UNKNOWN", band_status="UNKNOWN")) is True

    rows = tier_band_rows([
        card("AOK", tier="Tier A", market_date="2026-06-10"),
        card("BSTALE", market_date="2026-06-09"),
        card("BMISSING", market_date=None, low=None, high=None, stop=None, band_status="UNKNOWN"),
        card("CTIER", tier="Tier C", market_date="2026-06-10"),
    ], expected_market_date="2026-06-10")
    by_ticker = {row["ticker"]: row for row in rows}
    assert by_ticker["AOK"]["state"] == "complete_and_current", by_ticker
    assert by_ticker["BSTALE"]["state"] == "stale_complete_band_context", by_ticker
    assert by_ticker["BMISSING"]["state"] == "missing_decision_grade_band", by_ticker
    assert "CTIER" not in by_ticker, by_ticker

    rows = tier_band_rows(
        [card("BRIDGE", market_date=None)],
        expected_market_date="2026-06-10",
        bridge_rows={
            "BRIDGE": {
                "price_state": {
                    "status": "ok",
                    "latest_close": 11.0,
                    "data_date": "2026-06-10",
                    "source": "tmp/wf77-price-freshness-bridge.json",
                    "source_family": "supplemental_public_price_evidence",
                    "source_label": "wf77_supplemental_price_evidence",
                }
            }
        },
    )
    assert rows[0]["state"] == "complete_and_current", rows
    assert rows[0]["current_price_context_source"] == "wf77_price_freshness_bridge", rows
    print("tier_ab_band_freshness_cron_guard: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
