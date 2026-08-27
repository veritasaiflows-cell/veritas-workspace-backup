#!/usr/bin/env python3
"""Regression checks for Tier A/B band freshness cron guard."""
from __future__ import annotations

import tempfile
from pathlib import Path

import tier_ab_band_freshness_cron_guard as guard


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
    assert guard.decision_grade_band_missing(card("OK")) is False
    assert guard.decision_grade_band_missing(card("NOLOW", low=None)) is True
    assert guard.decision_grade_band_missing(card("NOSTOP", stop=None)) is True
    assert guard.decision_grade_band_missing(card("UNKNOWN", band_status="UNKNOWN")) is True

    rows = guard.tier_band_rows([
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

    rows = guard.tier_band_rows(
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

    rows = guard.tier_band_rows(
        [card("STALEBRIDGE", market_date="2026-06-09")],
        expected_market_date="2026-06-10",
        bridge_rows={
            "STALEBRIDGE": {
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
    assert rows[0]["market_date"] == "2026-06-10", rows
    assert rows[0]["current_price_context_source"] == "wf77_price_freshness_bridge", rows

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cards_path = tmp / "cards.json"
        repair_path = tmp / "repair.json"
        conveyor_path = tmp / "conveyor.json"
        bridge_path = tmp / "bridge.json"
        ledger_path = tmp / "ledger.json"
        cards_path.write_text(
            '{"cards": ['
            '{"ticker": "AOK", "auto_tier": "Tier A", "current_price": {"latest_known_price": 11.0, "market_date": "2026-06-10", "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"}, "entry_band": {"low": 10.0, "high": 12.0, "band_status": "IN_BAND", "source_timestamp": "2026-06-10T00:00:00+00:00"}, "stop_or_invalidation": {"level": 9.0, "source_timestamp": "2026-06-10T00:00:00+00:00"}},'
            '{"ticker": "BSTALE", "auto_tier": "Tier B", "current_price": {"latest_known_price": 11.0, "market_date": "2026-06-09", "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"}, "entry_band": {"low": 10.0, "high": 12.0, "band_status": "IN_BAND", "source_timestamp": "2026-06-10T00:00:00+00:00"}, "stop_or_invalidation": {"level": 9.0, "source_timestamp": "2026-06-10T00:00:00+00:00"}},'
            '{"ticker": "BNOPROV", "auto_tier": "Tier B", "current_price": {"latest_known_price": 11.0, "market_date": "2026-06-10", "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"}, "entry_band": {"low": 10.0, "high": 12.0, "band_status": "IN_BAND"}, "stop_or_invalidation": {"level": 9.0}},'
            '{"ticker": "BLEDGER", "auto_tier": "Tier B", "current_price": {"latest_known_price": 11.0, "market_date": "2026-06-10", "quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"}, "entry_band": {"low": 10.0, "high": 12.0, "band_status": "IN_BAND", "source_timestamp": "2026-06-10T00:00:00+00:00"}, "stop_or_invalidation": {"level": 9.0, "source_timestamp": "2026-06-10T00:00:00+00:00"}}'
            ']}',
            encoding="utf-8",
        )
        repair_path.write_text('{"status":"ok","summary":{"target_tickers":[]}}', encoding="utf-8")
        conveyor_path.write_text(
            '{"status":"ok","summary":{"tier_a_b_missing_decision_grade_band_count":0,"implementation_blocker_count":0,"control_plane_blocker_count":0}}',
            encoding="utf-8",
        )
        bridge_path.write_text('{"rows":[]}', encoding="utf-8")
        ledger_path.write_text(
            '{"rows":['
            '{"ticker":"AOK","stale_families":[]},'
            '{"ticker":"BSTALE","stale_families":[]},'
            '{"ticker":"BNOPROV","stale_families":[]},'
            '{"ticker":"BLEDGER","stale_families":["stale:price_band_stop"]}'
            ']}',
            encoding="utf-8",
        )
        originals = (
            guard.CARDS,
            guard.MISSING_BAND_REPAIR,
            guard.REPAIR_CONVEYOR,
            guard.WF77_PRICE_BRIDGE,
            guard.TICKER_FRESHNESS_LEDGER,
        )
        try:
            guard.CARDS = cards_path
            guard.MISSING_BAND_REPAIR = repair_path
            guard.REPAIR_CONVEYOR = conveyor_path
            guard.WF77_PRICE_BRIDGE = bridge_path
            guard.TICKER_FRESHNESS_LEDGER = ledger_path
            payload = guard.build_payload()
            missing_ledger_payload = None
            guard.TICKER_FRESHNESS_LEDGER = tmp / "absent-ledger.json"
            missing_ledger_payload = guard.build_payload()
        finally:
            (
                guard.CARDS,
                guard.MISSING_BAND_REPAIR,
                guard.REPAIR_CONVEYOR,
                guard.WF77_PRICE_BRIDGE,
                guard.TICKER_FRESHNESS_LEDGER,
            ) = originals
        rows = {row["ticker"]: row for row in payload["rows"]}
        assert payload["status"] == "warning", payload
        assert payload["validation"]["status"] == "warning", payload
        assert payload["validation"]["errors"] == [], payload
        assert "tier_a_b_complete_band_context_finance_domain_debt" in payload["validation"]["warnings"], payload

        # Provenanced, ledger-clean, current price context.
        assert rows["AOK"]["state"] == "complete_and_current", rows
        # Band evidence fine, price context behind: cheap refresh gate.
        assert rows["BSTALE"]["state"] == "stale_complete_band_context", rows
        # A band without source_timestamp can never be reported current.
        assert rows["BNOPROV"]["state"] == "stale_band_evidence", rows
        assert rows["BNOPROV"]["band_provenance_present"] is False, rows
        # Ledger-flagged band evidence outranks a current price context.
        assert rows["BLEDGER"]["state"] == "stale_band_evidence", rows
        assert rows["BLEDGER"]["ledger_band_evidence_stale"] is True, rows
        assert payload["summary"]["band_evidence_ledger_available"] is True, payload
        assert payload["summary"]["stale_band_evidence_count"] == 2, payload
        assert payload["summary"]["band_source_timestamp_missing_count"] == 1, payload

        # An unavailable ledger must fail loudly, never report an unverified all-clear.
        assert "band_evidence_ledger_unavailable" in missing_ledger_payload["validation"]["errors"], missing_ledger_payload
        assert missing_ledger_payload["status"] == "blocked", missing_ledger_payload
        assert missing_ledger_payload["summary"]["band_evidence_ledger_available"] is False, missing_ledger_payload

    print("tier_ab_band_freshness_cron_guard: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
