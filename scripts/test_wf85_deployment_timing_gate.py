#!/usr/bin/env python3
"""Acceptance tests for wf85_deployment_timing_gate.py."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf85_deployment_timing_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf85_deployment_timing_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    result = module.self_test()
    assert result["status"] == "ok", result

    assert module.final_timing_state(
        tier_scope="tier_a_b_decision_layer",
        decision_state="review_ready",
        price_gate="in_band",
        quote_gate="review_only_price_context",
        earnings_gate="safe_window",
        macro_gate="clear",
    ) == ("review_ready_wait_fresh_quote", ["quote_freshness_class=review_only_price_context"])

    assert module.final_timing_state(
        tier_scope="tier_a_b_decision_layer",
        decision_state="review_ready",
        price_gate="in_band",
        quote_gate="execution_fresh",
        earnings_gate="earnings_within_4_weeks",
        macro_gate="clear",
    ) == ("review_ready_suppressed", ["earnings_gate=earnings_within_4_weeks"])

    assert module.final_timing_state(
        tier_scope="tier_a_b_decision_layer",
        decision_state="below_stop_or_invalidation",
        price_gate="in_band",
        quote_gate="review_only_price_context",
        earnings_gate="earnings_within_4_weeks",
        macro_gate="clear",
    ) == (
        "blocked_below_stop_or_invalidation",
        ["decision_state=below_stop_or_invalidation", "price_band_gate=in_band"],
    )

    assert module.final_timing_state(
        tier_scope="tier_a_b_decision_layer",
        decision_state="review_ready",
        price_gate="in_band",
        quote_gate="execution_fresh",
        earnings_gate="safe_window",
        macro_gate="sector_headwind_override",
    ) == ("review_ready_suppressed", ["macro_sector_gate=sector_headwind_override"])

    gate, reasons, details = module.classify_earnings(
        "VRT",
        {},
        {"instrument_type": "operating_company"},
        date(2026, 6, 28),
        {
            "ticker": "VRT",
            "next_earnings_date": "2026-07-29",
            "source": "yfinance",
            "date_source_class": "provider_estimate",
            "primary_confirmed": False,
            "fetched_at_utc": "2026-06-28T15:02:36Z",
        },
        {"ticker": "VRT", "source_confidence": "provider_estimate"},
    )
    assert gate == "safe_window", (gate, reasons, details)
    assert details["date_source_class"] == "provider_estimate"
    assert details["gate_clear_condition"]

    gate, reasons, details = module.classify_earnings(
        "NVDA",
        {},
        {"instrument_type": "operating_company"},
        date(2026, 6, 28),
        {
            "ticker": "NVDA",
            "next_earnings_date": None,
            "source": "post_earnings_lifecycle_closeout",
            "date_source_class": "post_earnings_lifecycle_closeout",
            "primary_confirmed": False,
            "lifecycle": {"status": "post_event_review_confirmed_next_date_pending"},
        },
        {"ticker": "NVDA", "source_confidence": "primary_confirmed", "primary_confirmation_status": "configured_primary_evidence"},
    )
    assert gate == "unknown_block_or_caution", (gate, reasons, details)
    assert reasons == ["post_earnings_confirmed_next_date_pending"]
    assert details["source_confidence"] == "primary_confirmed"

    assert module.AUTHORITY_BOUNDARY["capital_deployment_approved"] is False
    assert module.AUTHORITY_BOUNDARY["paper_or_live_execution_allowed"] is False
    assert module.AUTHORITY_BOUNDARY["owner_approval_inferred"] is False
    print("ok wf85 deployment timing gate acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
