#!/usr/bin/env python3
"""Targeted tests for market-hours quote readiness hardening."""
from __future__ import annotations

from datetime import datetime

import market_calendar_freshness as calendar_owner
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


def test_market_calendar_constants_use_the_active_calendar_owner() -> None:
    assert hardening.NYSE_FULL_HOLIDAYS_2026 is calendar_owner.NYSE_FULL_HOLIDAYS_2026
    assert hardening.NYSE_EARLY_CLOSES_2026 is calendar_owner.NYSE_EARLY_CLOSES_2026


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


def test_effective_probe_prefers_enabled_silent_job() -> None:
    ledger = {
        "jobs": [
            {
                "name": hardening.LEGACY_TIER_A_INTRADAY_JOB,
                "enabled": False,
                "payload": {"message": "python scripts\\finance_market_deployment_operating_loop.py --send"},
            },
            {
                "name": hardening.SILENT_TIER_A_INTRADAY_JOB,
                "enabled": True,
                "payload": {"message": "python scripts\\finance_market_deployment_operating_loop.py --write --validate"},
            },
        ]
    }

    job = hardening.effective_probe_job(
        ledger,
        hardening.SILENT_TIER_A_INTRADAY_JOB,
        hardening.LEGACY_TIER_A_INTRADAY_JOB,
    )

    assert job["name"] == hardening.SILENT_TIER_A_INTRADAY_JOB
    assert "--send" not in hardening.job_command_text(job)


def test_effective_wf68_prefers_consolidated_digest_job() -> None:
    ledger = {
        "jobs": [
            {
                "name": hardening.LEGACY_WF68_INTRADAY_JOB,
                "enabled": False,
                "schedule": {"expr": "0 7 * * 1-5"},
            },
            {
                "name": hardening.WF68_CONSOLIDATED_JOB,
                "enabled": True,
                "schedule": {"expr": "5 7 * * 1-5"},
                "payload": {"message": "python scripts\\wf68_alert_digest_consolidated_runner.py --write --validate"},
            },
        ]
    }

    job = hardening.effective_wf68_job(ledger)

    assert job["name"] == hardening.WF68_CONSOLIDATED_JOB
    assert "wf68_alert_digest_consolidated_runner.py" in hardening.job_command_text(job)


def test_deployment_intraday_symbols_are_actionable_subset() -> None:
    auto_router = {
        "rows": [
            {"ticker": "NVDA", "auto_tier": "Tier A", "auto_state": "A-READY"},
            {"ticker": "VAW", "auto_tier": "Tier A", "auto_state": "A-CHALLENGED"},
            {"ticker": "CME", "auto_tier": "Tier A", "auto_state": "A-WATCH"},
        ]
    }
    capital_queue = {"rows": [{"ticker": "GOOG"}]}

    symbols = hardening.deployment_intraday_symbols(auto_router, capital_queue)

    assert symbols == ["GOOG", "NVDA"], symbols


def test_closed_market_quote_gate_uses_actionable_subset() -> None:
    required_market_date = hardening.date(2026, 6, 23)
    snapshots = [
        {
            "symbol": "NVDA",
            "source_timestamp_utc": "2026-06-23T19:59:00Z",
            "calendar_freshness_status": "current_last_completed_session",
        },
        {
            "symbol": "GOOG",
            "source_timestamp_utc": "2026-06-23T19:59:00Z",
            "calendar_freshness_status": "current_last_completed_session",
        },
        {
            "symbol": "VAW",
            "source_timestamp_utc": "2026-06-22T19:59:00Z",
            "calendar_freshness_status": "stale_unexpected",
        },
    ]
    calendar_status_by_symbol = {
        hardening.normalize_symbol(row["symbol"]): row["calendar_freshness_status"]
        for row in snapshots
    }
    actionable_rows = [
        row for row in snapshots
        if hardening.normalize_symbol(row["symbol"]) in {"GOOG", "NVDA"}
    ]

    actionable_source_current = all(
        (parsed := hardening.parse_utc(row.get("source_timestamp_utc"))) is not None
        and parsed.astimezone(hardening.LOCAL_TZ).date() == required_market_date
        for row in actionable_rows
    )
    actionable_calendar_current = all(
        calendar_status_by_symbol.get(hardening.normalize_symbol(row.get("symbol"))) in {
            "fresh_intraday",
            "current_last_completed_session",
            "market_closed_expected_stale",
        }
        for row in actionable_rows
    )

    assert actionable_source_current is True
    assert actionable_calendar_current is True


def test_closed_market_quote_gate_allows_no_actionable_subset() -> None:
    assert hardening.actionable_quote_snapshot_gate_ok(
        market_is_open=False,
        intraday_required_symbols=[],
        intraday_required_snapshot_fresh_intraday=False,
        intraday_required_snapshot_calendar_current=False,
        intraday_required_snapshot_source_dates_current=False,
    ) is True


def test_market_date_gate_allows_stale_nonrequired_row_when_required_set_is_current() -> None:
    required_market_date = hardening.date(2026, 8, 7)

    assert hardening.quote_snapshot_market_date_gate_ok(
        market_is_open=False,
        quote_local_date=hardening.date(2026, 8, 8),
        required_market_date=required_market_date,
        required_snapshot_rows=[{"symbol": "NVDA"}],
        required_snapshot_source_dates_current=True,
        snapshot_source_date_current=False,
        required_snapshot_calendar_current=True,
        snapshot_calendar_current=False,
    ) is True


def test_market_date_gate_rejects_stale_required_set() -> None:
    required_market_date = hardening.date(2026, 8, 7)

    assert hardening.quote_snapshot_market_date_gate_ok(
        market_is_open=False,
        quote_local_date=hardening.date(2026, 8, 8),
        required_market_date=required_market_date,
        required_snapshot_rows=[{"symbol": "NVDA"}],
        required_snapshot_source_dates_current=False,
        snapshot_source_date_current=True,
        required_snapshot_calendar_current=False,
        snapshot_calendar_current=True,
    ) is False


def test_market_date_gate_without_required_rows_uses_all_snapshot_fallback() -> None:
    required_market_date = hardening.date(2026, 8, 7)
    kwargs = {
        "market_is_open": False,
        "quote_local_date": hardening.date(2026, 8, 8),
        "required_market_date": required_market_date,
        "required_snapshot_rows": [],
        "required_snapshot_source_dates_current": False,
        "required_snapshot_calendar_current": False,
    }

    assert hardening.quote_snapshot_market_date_gate_ok(
        **kwargs,
        snapshot_source_date_current=True,
        snapshot_calendar_current=True,
    ) is True
    assert hardening.quote_snapshot_market_date_gate_ok(
        **kwargs,
        snapshot_source_date_current=False,
        snapshot_calendar_current=False,
    ) is False


def test_market_date_gate_does_not_use_generated_date_alone_during_market_hours() -> None:
    required_market_date = hardening.date(2026, 8, 7)

    assert hardening.quote_snapshot_market_date_gate_ok(
        market_is_open=True,
        quote_local_date=required_market_date,
        required_market_date=required_market_date,
        required_snapshot_rows=[{"symbol": "NVDA"}],
        required_snapshot_source_dates_current=False,
        snapshot_source_date_current=False,
        required_snapshot_calendar_current=True,
        snapshot_calendar_current=True,
    ) is False


def test_market_date_gate_allows_prior_completed_session_preopen() -> None:
    assert hardening.quote_snapshot_market_date_gate_ok(
        market_is_open=False,
        quote_local_date=hardening.date(2026, 8, 10),
        required_market_date=hardening.date(2026, 8, 10),
        required_snapshot_rows=[{"symbol": "NVDA"}],
        required_snapshot_source_dates_current=False,
        snapshot_source_date_current=False,
        required_snapshot_calendar_current=True,
        snapshot_calendar_current=True,
    ) is True


def main() -> int:
    test_market_calendar_constants_use_the_active_calendar_owner()
    test_quote_snapshot_retry_reasons_are_market_hours_only()
    test_quote_snapshot_validation_gap_triggers_retry()
    test_retry_quote_snapshot_if_needed_clears_after_refresh()
    test_effective_probe_prefers_enabled_silent_job()
    test_effective_wf68_prefers_consolidated_digest_job()
    test_deployment_intraday_symbols_are_actionable_subset()
    test_closed_market_quote_gate_uses_actionable_subset()
    test_closed_market_quote_gate_allows_no_actionable_subset()
    test_market_date_gate_allows_stale_nonrequired_row_when_required_set_is_current()
    test_market_date_gate_rejects_stale_required_set()
    test_market_date_gate_without_required_rows_uses_all_snapshot_fallback()
    test_market_date_gate_does_not_use_generated_date_alone_during_market_hours()
    test_market_date_gate_allows_prior_completed_session_preopen()
    print("market_execution_readiness_cron_hardening targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
