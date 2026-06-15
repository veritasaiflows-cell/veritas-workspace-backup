#!/usr/bin/env python3
"""Targeted tests for market-hours quote readiness hardening."""
from __future__ import annotations

from datetime import datetime

import market_execution_readiness_cron_hardening as hardening


def proof(calendar_status: str = "fresh_intraday", freshness_status: str = "fresh") -> dict:
    return {
        "status": "ok",
        "generated_at_utc": "2026-06-15T19:00:00Z",
        "snapshots": [
            {
                "symbol": "ITA",
                "source_timestamp_utc": "2026-06-15T18:59:00Z",
                "calendar_freshness_status": calendar_status,
                "freshness_status": freshness_status,
            }
        ],
    }


def test_quote_snapshot_retry_reasons_are_market_hours_only() -> None:
    market_open = datetime(2026, 6, 15, 12, 0, tzinfo=hardening.LOCAL_TZ)
    after_close = datetime(2026, 6, 15, 13, 30, tzinfo=hardening.LOCAL_TZ)
    stale = proof("stale_unexpected", "current_but_not_intraday_fresh")
    validation = {"status": "ok"}

    reasons = hardening.quote_snapshot_retry_reasons(stale, validation, market_open)
    assert "ITA:calendar_freshness:stale_unexpected" in reasons, reasons
    assert "ITA:freshness:current_but_not_intraday_fresh" in reasons, reasons
    assert hardening.quote_snapshot_retry_reasons(stale, validation, after_close) == []


def test_quote_snapshot_validation_gap_triggers_retry() -> None:
    market_open = datetime(2026, 6, 15, 12, 0, tzinfo=hardening.LOCAL_TZ)
    reasons = hardening.quote_snapshot_retry_reasons(proof(), {"status": "error"}, market_open)
    assert "quote_snapshot_validation:error" in reasons, reasons


def test_retry_quote_snapshot_if_needed_clears_after_refresh() -> None:
    market_open = datetime(2026, 6, 15, 12, 0, tzinfo=hardening.LOCAL_TZ)
    state = {
        "proof": proof("stale_unexpected", "current_but_not_intraday_fresh"),
        "validation": {"status": "ok"},
    }
    original_load = hardening.load

    def fake_load(path):
        if path == hardening.QUOTE_PROOF:
            return state["proof"]
        if path == hardening.QUOTE_VALIDATION:
            return state["validation"]
        return {}

    def fake_runner():
        state["proof"] = proof()
        return {"ok": True, "returncode": 0}

    hardening.load = fake_load
    try:
        result = hardening.retry_quote_snapshot_if_needed(
            state["proof"],
            state["validation"],
            market_open,
            max_attempts=2,
            backoff_seconds=0,
            runner=fake_runner,
        )
    finally:
        hardening.load = original_load

    assert result["attempted"] is True, result
    assert result["attempt_count"] == 1, result
    assert result["cleared"] is True, result
    assert result["final_reasons"] == [], result


def main() -> int:
    test_quote_snapshot_retry_reasons_are_market_hours_only()
    test_quote_snapshot_validation_gap_triggers_retry()
    test_retry_quote_snapshot_if_needed_clears_after_refresh()
    print("market_execution_readiness_cron_hardening targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
