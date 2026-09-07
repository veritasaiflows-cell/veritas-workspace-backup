#!/usr/bin/env python3
"""Validate cron timing for daily Tier 1 quote readiness.

This is a review-only hardening pass. It proves that market-data cron windows,
WF68 quote proof, and WF78 Tier A/capital-review coverage line up before any
owner-facing execution-readiness language is allowed downstream.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time as time_module
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact
from market_calendar_freshness import NYSE_EARLY_CLOSES_2026, NYSE_FULL_HOLIDAYS_2026
from market_calendar_freshness import classify_quote_freshness, market_session as calendar_market_session


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "market-execution-readiness-cron-hardening.json"

CRON_LEDGER = TMP / "cron-operator-ledger.json"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
QUOTE_VALIDATION = TMP / "intraday-alerts" / "quote-snapshot-proof-validation.json"
WF78_AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
WF78_CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
WF78_EVENT_REROUTING = TMP / "wf78-event-triggered-rerouting.json"

SCHEMA = "veritas.market_execution_readiness_cron_hardening.v1"
LOCAL_TZ = ZoneInfo("America/Phoenix")
MARKET_OPEN = time(6, 30)
MARKET_CLOSE = time(13, 0)
EARLY_CLOSE = time(11, 0)
REQUIRED_OPPORTUNITY_PROBE_TIMES = [time(6, 42), time(7, 14), time(12, 7)]
SILENT_TIER_A_INTRADAY_JOB = "Finance - Silent Tier A Intraday Market Readiness Probe"
SILENT_TIER_A_CONFIRMATION_JOB = "Finance - Silent Tier A Confirmation Market Readiness Probe"
SILENT_TIER_A_LATE_SESSION_JOB = "Finance - Silent Tier A Late-Session Market Readiness Probe"
LEGACY_TIER_A_INTRADAY_JOB = "Finance - Tier A Intraday Opportunity Probe"
LEGACY_TIER_A_CONFIRMATION_JOB = "Finance - Tier A Confirmation Opportunity Probe"
LEGACY_TIER_A_LATE_SESSION_JOB = "Finance - Tier A Late-Session Opportunity Probe"
WF68_CONSOLIDATED_JOB = "Finance - WF68 Alert Producer and Digest"
LEGACY_WF68_INTRADAY_JOB = "Finance - WF68 Intraday Alert Producer"
QUOTE_RETRY_MAX_ATTEMPTS = 2
QUOTE_RETRY_BACKOFF_SECONDS = 3.0
QUOTE_RETRY_STATUSES = {"stale_unexpected", "provider_missing", "unknown"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_time_hardening": True,
    "market_data_readiness_proof": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_market_date(now_local: datetime) -> date:
    cursor = now_local.date()
    while cursor.weekday() >= 5 or cursor in NYSE_FULL_HOLIDAYS_2026:
        cursor = date.fromordinal(cursor.toordinal() - 1)
    return cursor


def market_close_for_date(day: date) -> time:
    return EARLY_CLOSE if day in NYSE_EARLY_CLOSES_2026 else MARKET_CLOSE


def market_is_open_local(now_local: datetime) -> bool:
    market_close = market_close_for_date(now_local.date())
    return (
        MARKET_OPEN <= now_local.time() <= market_close
        and now_local.weekday() < 5
        and now_local.date() not in NYSE_FULL_HOLIDAYS_2026
    )


def normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def append_unique(symbols: list[str], additions: list[Any]) -> list[str]:
    result = list(symbols)
    for symbol in additions:
        normalized = normalize_symbol(symbol)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def wf78_tier_one_symbols(auto_router: dict[str, Any], capital_queue: dict[str, Any]) -> list[str]:
    summary = as_dict(auto_router.get("summary"))
    symbols = []
    symbols = append_unique(symbols, as_list(summary.get("auto_tier_a_tickers")))
    if not symbols:
        symbols = append_unique(
            symbols,
            [
                as_dict(row).get("ticker")
                for row in as_list(auto_router.get("rows"))
                if as_dict(row).get("auto_tier") == "Tier A"
            ],
        )
    symbols = append_unique(symbols, [as_dict(row).get("ticker") for row in as_list(capital_queue.get("rows"))])
    return symbols


def deployment_intraday_symbols(auto_router: dict[str, Any], capital_queue: dict[str, Any]) -> list[str]:
    """Symbols that need intraday-fresh quotes before owner-card/execution-readiness language."""
    symbols = [
        as_dict(row).get("ticker")
        for row in as_list(capital_queue.get("rows"))
        if as_dict(row).get("ticker")
    ]
    symbols = append_unique(
        symbols,
        [
            as_dict(row).get("ticker")
            for row in as_list(auto_router.get("rows"))
            if as_dict(row).get("auto_tier") == "Tier A"
            and as_dict(row).get("auto_state") == "A-READY"
        ],
    )
    return symbols


def cron_expr(job: dict[str, Any]) -> str:
    schedule = job.get("schedule")
    if isinstance(schedule, str):
        try:
            schedule = json.loads(schedule)
        except json.JSONDecodeError:
            return ""
    return str(as_dict(schedule).get("expr") or "")


def expand_cron_part(part: str, low: int, high: int) -> set[int]:
    values: set[int] = set()
    for piece in part.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece == "*":
            values.update(range(low, high + 1))
        elif "-" in piece:
            start, end = piece.split("-", 1)
            values.update(range(int(start), int(end) + 1))
        else:
            values.add(int(piece))
    return {value for value in values if low <= value <= high}


def cron_times(expr: str) -> list[time]:
    parts = expr.split()
    if len(parts) < 5:
        return []
    minutes = expand_cron_part(parts[0], 0, 59)
    hours = expand_cron_part(parts[1], 0, 23)
    return sorted(time(hour, minute) for hour in hours for minute in minutes)


def job_by_name(ledger: dict[str, Any], name: str) -> dict[str, Any]:
    for job in as_list(ledger.get("jobs")):
        row = as_dict(job)
        if row.get("name") == name:
            return row
    return {}


def job_command_text(job: dict[str, Any]) -> str:
    return json.dumps(as_dict(job.get("payload")), ensure_ascii=False).lower()


def effective_probe_job(ledger: dict[str, Any], silent_name: str, legacy_name: str) -> dict[str, Any]:
    """Prefer silent post-consolidation producer jobs over retired send-capable probes."""
    silent = job_by_name(ledger, silent_name)
    if silent.get("enabled") is True:
        return silent
    return job_by_name(ledger, legacy_name)


def effective_wf68_job(ledger: dict[str, Any]) -> dict[str, Any]:
    """Prefer the consolidated WF68 digest job over the retired intraday-only producer."""
    consolidated = job_by_name(ledger, WF68_CONSOLIDATED_JOB)
    if consolidated.get("enabled") is True:
        return consolidated
    return job_by_name(ledger, LEGACY_WF68_INTRADAY_JOB)


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def actionable_quote_snapshot_gate_ok(
    *,
    market_is_open: bool,
    intraday_required_symbols: list[str] | set[str],
    intraday_required_snapshot_fresh_intraday: bool,
    intraday_required_snapshot_calendar_current: bool,
    intraday_required_snapshot_source_dates_current: bool,
) -> bool:
    if not intraday_required_symbols:
        return True
    if market_is_open:
        return bool(intraday_required_snapshot_fresh_intraday)
    return bool(intraday_required_snapshot_calendar_current and intraday_required_snapshot_source_dates_current)


def quote_snapshot_market_date_gate_ok(
    *,
    market_is_open: bool,
    quote_local_date: date | None,
    required_market_date: date,
    required_snapshot_rows: list[dict[str, Any]],
    required_snapshot_source_dates_current: bool,
    snapshot_source_date_current: bool,
    required_snapshot_calendar_current: bool,
    snapshot_calendar_current: bool,
) -> bool:
    if market_is_open:
        source_dates_current = (
            required_snapshot_source_dates_current
            if required_snapshot_rows
            else snapshot_source_date_current
        )
        return bool(quote_local_date == required_market_date and source_dates_current)
    return bool(
        required_snapshot_calendar_current
        if required_snapshot_rows
        else snapshot_calendar_current
    )


def quote_snapshot_retry_reasons(
    quote_proof: dict[str, Any],
    quote_validation: dict[str, Any],
    now_local: datetime,
) -> list[str]:
    """Return market-hours quote-proof conditions worth one bounded retry."""
    if not market_is_open_local(now_local):
        return []
    reasons: list[str] = []
    if quote_proof.get("status") != "ok":
        reasons.append(f"quote_snapshot_status:{quote_proof.get('status') or 'missing'}")
    if quote_validation.get("status") != "ok":
        reasons.append(f"quote_snapshot_validation:{quote_validation.get('status') or 'missing'}")
    quote_generated_dt = parse_utc(quote_proof.get("generated_at_utc")) or datetime.now(timezone.utc)
    snapshots = [as_dict(row) for row in as_list(quote_proof.get("snapshots"))]
    if not snapshots:
        reasons.append("quote_snapshots_missing")
    for row in snapshots:
        symbol = normalize_symbol(row.get("symbol")) or "UNKNOWN"
        status = row.get("calendar_freshness_status")
        if not isinstance(status, str) or not status:
            classified = classify_quote_freshness(row.get("source_timestamp_utc"), quote_generated_dt)
            status = str(classified.get("calendar_freshness_status") or "unknown")
        if status in QUOTE_RETRY_STATUSES:
            reasons.append(f"{symbol}:calendar_freshness:{status}")
        if row.get("freshness_status") != "fresh":
            reasons.append(f"{symbol}:freshness:{row.get('freshness_status') or 'missing'}")
    return sorted(dict.fromkeys(reasons))


def run_quote_snapshot_refresh() -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(
        [sys.executable, "scripts\\intraday_quote_snapshot_proof.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    return {
        "command": "python scripts\\intraday_quote_snapshot_proof.py",
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def retry_quote_snapshot_if_needed(
    quote_proof: dict[str, Any],
    quote_validation: dict[str, Any],
    now_local: datetime,
    *,
    max_attempts: int = QUOTE_RETRY_MAX_ATTEMPTS,
    backoff_seconds: float = QUOTE_RETRY_BACKOFF_SECONDS,
    runner=run_quote_snapshot_refresh,
) -> dict[str, Any]:
    initial_reasons = quote_snapshot_retry_reasons(quote_proof, quote_validation, now_local)
    result: dict[str, Any] = {
        "attempted": False,
        "attempt_count": 0,
        "max_attempts": max_attempts,
        "initial_reasons": initial_reasons,
        "final_reasons": initial_reasons,
        "cleared": not initial_reasons,
        "attempts": [],
    }
    if not initial_reasons:
        return result
    current_proof = quote_proof
    current_validation = quote_validation
    for attempt_index in range(max(0, max_attempts)):
        result["attempted"] = True
        run = runner()
        result["attempts"].append(run)
        result["attempt_count"] = len(result["attempts"])
        current_proof = as_dict(load(QUOTE_PROOF))
        current_validation = as_dict(load(QUOTE_VALIDATION))
        final_reasons = quote_snapshot_retry_reasons(current_proof, current_validation, now_local)
        result["final_reasons"] = final_reasons
        result["cleared"] = not final_reasons
        if not final_reasons:
            break
        if attempt_index < max_attempts - 1 and backoff_seconds > 0:
            time_module.sleep(backoff_seconds)
    return result


def build_report() -> dict[str, Any]:
    generated_at = utc_now()
    now_local = datetime.now(timezone.utc).astimezone(LOCAL_TZ)
    session = calendar_market_session(datetime.now(timezone.utc))
    required_market_date = latest_market_date(now_local)

    ledger = as_dict(load(CRON_LEDGER))
    quote_proof = as_dict(load(QUOTE_PROOF))
    quote_validation = as_dict(load(QUOTE_VALIDATION))
    auto_router = as_dict(load(WF78_AUTO_ROUTER))
    capital_queue = as_dict(load(WF78_CAPITAL_QUEUE))
    event_rerouting = as_dict(load(WF78_EVENT_REROUTING))
    quote_retry = retry_quote_snapshot_if_needed(quote_proof, quote_validation, now_local)
    if quote_retry.get("attempted"):
        quote_proof = as_dict(load(QUOTE_PROOF))
        quote_validation = as_dict(load(QUOTE_VALIDATION))

    wf68_job = effective_wf68_job(ledger)
    legacy_wf68_job = job_by_name(ledger, LEGACY_WF68_INTRADAY_JOB)
    p0_job = job_by_name(ledger, "P0 Retail Automation Control Plane Guard")
    tier_a_job = effective_probe_job(ledger, SILENT_TIER_A_INTRADAY_JOB, LEGACY_TIER_A_INTRADAY_JOB)
    confirmation_tier_a_job = effective_probe_job(ledger, SILENT_TIER_A_CONFIRMATION_JOB, LEGACY_TIER_A_CONFIRMATION_JOB)
    late_tier_a_job = effective_probe_job(ledger, SILENT_TIER_A_LATE_SESSION_JOB, LEGACY_TIER_A_LATE_SESSION_JOB)
    legacy_tier_a_job = job_by_name(ledger, LEGACY_TIER_A_INTRADAY_JOB)
    legacy_confirmation_tier_a_job = job_by_name(ledger, LEGACY_TIER_A_CONFIRMATION_JOB)
    legacy_late_tier_a_job = job_by_name(ledger, LEGACY_TIER_A_LATE_SESSION_JOB)
    wf68_times = cron_times(cron_expr(wf68_job))
    p0_times = cron_times(cron_expr(p0_job))
    tier_a_times = (
        cron_times(cron_expr(tier_a_job))
        + cron_times(cron_expr(confirmation_tier_a_job))
        + cron_times(cron_expr(late_tier_a_job))
    )
    quote_refresh_times = sorted({*wf68_times, *tier_a_times})

    required_symbols = wf78_tier_one_symbols(auto_router, capital_queue)
    intraday_required_symbols = deployment_intraday_symbols(auto_router, capital_queue)
    observed_symbols = [normalize_symbol(symbol) for symbol in as_list(quote_proof.get("symbols_observed"))]
    requested_symbols = [normalize_symbol(symbol) for symbol in as_list(quote_proof.get("symbols_requested"))]
    missing_required = sorted(symbol for symbol in required_symbols if symbol not in observed_symbols)
    not_requested_required = sorted(symbol for symbol in required_symbols if symbol not in requested_symbols)
    missing_intraday_required = sorted(symbol for symbol in intraday_required_symbols if symbol not in observed_symbols)

    quote_generated_dt = parse_utc(quote_proof.get("generated_at_utc"))
    quote_local_date = quote_generated_dt.astimezone(LOCAL_TZ).date() if quote_generated_dt else None
    snapshots = [as_dict(row) for row in as_list(quote_proof.get("snapshots"))]
    calendar_status_by_symbol: dict[str, str] = {}
    calendar_freshness_counts: dict[str, int] = {}
    for row in snapshots:
        status = row.get("calendar_freshness_status")
        if not isinstance(status, str) or not status:
            classified = classify_quote_freshness(row.get("source_timestamp_utc"), quote_generated_dt or datetime.now(timezone.utc))
            status = str(classified.get("calendar_freshness_status") or "unknown")
        calendar_status_by_symbol[normalize_symbol(row.get("symbol"))] = status
        calendar_freshness_counts[status] = calendar_freshness_counts.get(status, 0) + 1
    snapshot_source_dates = sorted({
        parsed.astimezone(LOCAL_TZ).date()
        for row in snapshots
        for parsed in [parse_utc(row.get("source_timestamp_utc"))]
        if parsed
    })
    snapshot_source_date_current = bool(snapshot_source_dates) and all(item == required_market_date for item in snapshot_source_dates)
    market_close = market_close_for_date(now_local.date())
    market_is_open = market_is_open_local(now_local)
    stale_or_missing_snapshots = [row for row in snapshots if row.get("freshness_status") in {"stale", "missing_source_timestamp"}]
    non_intraday_fresh_snapshots = [row for row in snapshots if row.get("freshness_status") != "fresh"]
    stale_unexpected_snapshots = [
        row for row in snapshots
        if calendar_status_by_symbol.get(normalize_symbol(row.get("symbol"))) in {"stale_unexpected", "provider_missing"}
    ]
    required_symbol_set = set(required_symbols)
    intraday_required_symbol_set = set(intraday_required_symbols)
    required_snapshot_rows = [row for row in snapshots if normalize_symbol(row.get("symbol")) in required_symbol_set]
    intraday_required_snapshot_rows = [row for row in snapshots if normalize_symbol(row.get("symbol")) in intraday_required_symbol_set]
    required_snapshot_source_dates_current = bool(required_snapshot_rows) and all(
        (parsed := parse_utc(row.get("source_timestamp_utc"))) is not None
        and parsed.astimezone(LOCAL_TZ).date() == required_market_date
        for row in required_snapshot_rows
    )
    required_snapshot_calendar_current = bool(required_snapshot_rows) and all(
        calendar_status_by_symbol.get(normalize_symbol(row.get("symbol"))) in {
            "fresh_intraday",
            "current_last_completed_session",
            "market_closed_expected_stale",
        }
        for row in required_snapshot_rows
    )
    snapshot_calendar_current = bool(snapshots) and all(
        calendar_status_by_symbol.get(normalize_symbol(row.get("symbol"))) in {
            "fresh_intraday",
            "current_last_completed_session",
            "market_closed_expected_stale",
        }
        for row in snapshots
    )
    required_snapshot_fresh_intraday = bool(required_snapshot_rows) and all(
        calendar_status_by_symbol.get(normalize_symbol(row.get("symbol"))) == "fresh_intraday"
        for row in required_snapshot_rows
    )
    intraday_required_snapshot_source_dates_current = bool(intraday_required_snapshot_rows) and all(
        (parsed := parse_utc(row.get("source_timestamp_utc"))) is not None
        and parsed.astimezone(LOCAL_TZ).date() == required_market_date
        for row in intraday_required_snapshot_rows
    )
    intraday_required_snapshot_calendar_current = bool(intraday_required_snapshot_rows) and all(
        calendar_status_by_symbol.get(normalize_symbol(row.get("symbol"))) in {
            "fresh_intraday",
            "current_last_completed_session",
            "market_closed_expected_stale",
        }
        for row in intraday_required_snapshot_rows
    )
    intraday_required_snapshot_fresh_intraday = bool(intraday_required_snapshot_rows) and all(
        calendar_status_by_symbol.get(normalize_symbol(row.get("symbol"))) == "fresh_intraday"
        for row in intraday_required_snapshot_rows
    )
    actionable_snapshot_gate_ok = actionable_quote_snapshot_gate_ok(
        market_is_open=market_is_open,
        intraday_required_symbols=intraday_required_symbol_set,
        intraday_required_snapshot_fresh_intraday=intraday_required_snapshot_fresh_intraday,
        intraday_required_snapshot_calendar_current=intraday_required_snapshot_calendar_current,
        intraday_required_snapshot_source_dates_current=intraday_required_snapshot_source_dates_current,
    )
    market_date_gate_ok = quote_snapshot_market_date_gate_ok(
        market_is_open=market_is_open,
        quote_local_date=quote_local_date,
        required_market_date=required_market_date,
        required_snapshot_rows=required_snapshot_rows,
        required_snapshot_source_dates_current=required_snapshot_source_dates_current,
        snapshot_source_date_current=snapshot_source_date_current,
        required_snapshot_calendar_current=required_snapshot_calendar_current,
        snapshot_calendar_current=snapshot_calendar_current,
    )
    non_intraday_fresh_required_nonactionable = [
        row for row in required_snapshot_rows
        if normalize_symbol(row.get("symbol")) not in intraday_required_symbol_set
        and row.get("freshness_status") != "fresh"
    ]
    max_age_seconds = max((int(row.get("age_seconds") or 0) for row in snapshots if row.get("age_seconds") is not None), default=None)

    wf68_payload = json.dumps(wf68_job, ensure_ascii=False).lower()

    checks: list[dict[str, Any]] = []
    add_check(checks, "cron_ledger_exists", CRON_LEDGER.exists(), rel(CRON_LEDGER))
    add_check(checks, "wf68_intraday_producer_enabled", wf68_job.get("enabled") is True, wf68_job)
    add_check(
        checks,
        "legacy_wf68_intraday_replaced_by_consolidated_digest",
        wf68_job.get("name") == WF68_CONSOLIDATED_JOB or legacy_wf68_job.get("enabled") is True,
        {
            "effective_job": wf68_job.get("name"),
            "consolidated_job": WF68_CONSOLIDATED_JOB,
            "legacy_job": LEGACY_WF68_INTRADAY_JOB,
            "legacy_enabled": legacy_wf68_job.get("enabled"),
        },
        "warning",
    )
    add_check(checks, "wf68_timezone_phoenix", "America/Phoenix" in str(wf68_job.get("timezone") or wf68_job.get("schedule")), wf68_job.get("schedule"))
    add_check(checks, "wf68_weekday_schedule_present", "1-5" in cron_expr(wf68_job), cron_expr(wf68_job))
    add_check(checks, "tier_a_composite_probe_enabled", tier_a_job.get("enabled") is True, tier_a_job)
    add_check(checks, "tier_a_confirmation_probe_enabled", confirmation_tier_a_job.get("enabled") is True, confirmation_tier_a_job)
    add_check(checks, "tier_a_late_session_probe_enabled", late_tier_a_job.get("enabled") is True, late_tier_a_job)
    add_check(checks, "tier_a_composite_probe_silent", "--send" not in job_command_text(tier_a_job), tier_a_job)
    add_check(checks, "tier_a_confirmation_probe_silent", "--send" not in job_command_text(confirmation_tier_a_job), confirmation_tier_a_job)
    add_check(checks, "tier_a_late_session_probe_silent", "--send" not in job_command_text(late_tier_a_job), late_tier_a_job)
    add_check(
        checks,
        "legacy_tier_a_send_probes_retired",
        all(job.get("enabled") is not True for job in [legacy_tier_a_job, legacy_confirmation_tier_a_job, legacy_late_tier_a_job]),
        {
            "legacy_intraday_enabled": legacy_tier_a_job.get("enabled"),
            "legacy_confirmation_enabled": legacy_confirmation_tier_a_job.get("enabled"),
            "legacy_late_session_enabled": legacy_late_tier_a_job.get("enabled"),
        },
        "warning",
    )
    add_check(
        checks,
        "tier_a_probe_has_settled_open_window",
        time(6, 42) in tier_a_times,
        [item.isoformat(timespec="minutes") for item in tier_a_times],
    )
    add_check(
        checks,
        "tier_a_probe_has_confirmation_window",
        time(7, 14) in tier_a_times,
        [item.isoformat(timespec="minutes") for item in tier_a_times],
    )
    add_check(
        checks,
        "tier_a_probe_has_late_session_window",
        time(12, 7) in tier_a_times,
        [item.isoformat(timespec="minutes") for item in tier_a_times],
    )
    add_check(
        checks,
        "tier_a_opportunity_probe_count_capped_at_three",
        sorted(tier_a_times) == REQUIRED_OPPORTUNITY_PROBE_TIMES,
        {
            "actual": [item.isoformat(timespec="minutes") for item in sorted(tier_a_times)],
            "required": [item.isoformat(timespec="minutes") for item in REQUIRED_OPPORTUNITY_PROBE_TIMES],
        },
    )
    add_check(
        checks,
        "composite_quote_refresh_has_regular_session_windows",
        len([item for item in quote_refresh_times if MARKET_OPEN <= item <= MARKET_CLOSE]) >= 2,
        {
            "wf68_times": [item.isoformat(timespec="minutes") for item in wf68_times],
            "tier_a_times": [item.isoformat(timespec="minutes") for item in tier_a_times],
        },
    )
    add_check(checks, "wf68_payload_no_redundant_ledger_refresh", "cron_operator_ledger.py" not in wf68_payload, "WF68 producer should not run ledger refresh from isolated job.")
    add_check(checks, "p0_control_guard_disabled_or_enabled_cleanly", p0_job.get("enabled") in {True, False, None}, p0_job, "warning")
    add_check(checks, "p0_market_open_guard_window_if_enabled", (p0_job.get("enabled") is not True) or any(MARKET_OPEN <= item <= time(7, 30) for item in p0_times), [item.isoformat(timespec="minutes") for item in p0_times], "warning")
    add_check(checks, "quote_snapshot_proof_exists", QUOTE_PROOF.exists(), rel(QUOTE_PROOF))
    add_check(checks, "quote_snapshot_status_ok", quote_proof.get("status") == "ok", quote_proof.get("status"))
    add_check(checks, "quote_snapshot_validation_ok", quote_validation.get("status") == "ok", quote_validation)
    add_check(
        checks,
        "quote_snapshot_market_date_current",
        market_date_gate_ok,
        {
            "quote_local_date": str(quote_local_date),
            "snapshot_source_dates": [str(item) for item in snapshot_source_dates],
            "required_market_date": str(required_market_date),
            "now_local": now_local.isoformat(),
            "market_is_open": market_is_open,
            "required_snapshot_row_count": len(required_snapshot_rows),
            "required_snapshot_source_dates_current": required_snapshot_source_dates_current,
            "all_snapshot_source_dates_current": snapshot_source_date_current,
            "required_snapshot_calendar_current": required_snapshot_calendar_current,
            "all_snapshot_calendar_current": snapshot_calendar_current,
            "policy": "Closed and pre-open proof uses calendar-current required rows when that set exists, otherwise all rows. Market-hours proof also requires same-day generated and source dates.",
        },
    )
    add_check(checks, "tier_one_required_symbols_present", not missing_required, {"missing": missing_required, "required": required_symbols, "observed": observed_symbols})
    add_check(checks, "tier_one_required_symbols_requested", not not_requested_required, {"not_requested": not_requested_required, "required": required_symbols, "requested": requested_symbols})
    add_check(
        checks,
        "deployment_intraday_required_symbols_present",
        not missing_intraday_required,
        {"missing": missing_intraday_required, "required": intraday_required_symbols, "observed": observed_symbols},
    )
    add_check(
        checks,
        "quote_snapshots_current_for_market_window",
        actionable_snapshot_gate_ok,
        {
            "market_is_open": market_is_open,
            "market_session_window": session.get("market_session_window"),
            "stale_or_missing": stale_or_missing_snapshots[:10],
            "non_intraday_fresh": non_intraday_fresh_snapshots[:10],
            "stale_unexpected": stale_unexpected_snapshots[:10],
            "calendar_freshness_counts": calendar_freshness_counts,
            "required_snapshot_source_dates_current": required_snapshot_source_dates_current,
            "required_snapshot_calendar_current": required_snapshot_calendar_current,
            "required_snapshot_fresh_intraday": required_snapshot_fresh_intraday,
            "intraday_required_symbols": intraday_required_symbols,
            "intraday_required_snapshot_source_dates_current": intraday_required_snapshot_source_dates_current,
            "intraday_required_snapshot_calendar_current": intraday_required_snapshot_calendar_current,
            "intraday_required_snapshot_fresh_intraday": intraday_required_snapshot_fresh_intraday,
            "actionable_snapshot_gate_ok": actionable_snapshot_gate_ok,
            "no_intraday_required_symbols": not intraday_required_symbol_set,
            "max_age_seconds": max_age_seconds,
            "policy": "Regular session requires intraday-fresh quotes for A-READY/capital-review symbols. Closed-market readiness requires current latest-session proof for that actionable subset; non-actionable Tier A coverage remains a warning if provider-limited.",
        },
    )
    add_check(
        checks,
        "nonactionable_tier_a_quote_freshness_warning",
        not non_intraday_fresh_required_nonactionable,
        {
            "non_intraday_fresh_required_nonactionable": non_intraday_fresh_required_nonactionable[:10],
            "policy": "Provider-limited A-CHALLENGED/watch-only symbols cannot feed execution-readiness language until fresh.",
        },
        "warning",
    )
    add_check(checks, "wf78_event_queue_keeps_fresh_quote_first", as_dict(as_dict(event_rerouting.get("summary")).get("top_action")).get("trigger") == "capital_candidate_fresh_quote_band_stop_required", as_dict(event_rerouting.get("summary")).get("top_action"), "warning")
    add_check(checks, "authority_no_execution_or_approval", all(value is False for key, value in AUTHORITY_BOUNDARY.items() if key not in {"review_only", "cron_time_hardening", "market_data_readiness_proof"}), AUTHORITY_BOUNDARY)

    critical = [check for check in checks if check["ok"] is not True and check["severity"] == "critical"]
    warnings = [check for check in checks if check["ok"] is not True and check["severity"] == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": status,
        "workflow": "Market execution-readiness cron timing hardening",
        "purpose": "Ensure daily Tier 1 quote proof is fresh and aligned to WF78/WF68 market-use windows without granting execution authority.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "cron_ledger": rel(CRON_LEDGER),
            "quote_snapshot_proof": rel(QUOTE_PROOF),
            "quote_snapshot_validation": rel(QUOTE_VALIDATION),
            "wf78_auto_router": rel(WF78_AUTO_ROUTER),
            "wf78_capital_review_queue": rel(WF78_CAPITAL_QUEUE),
            "wf78_event_triggered_rerouting": rel(WF78_EVENT_REROUTING),
        },
        "summary": {
            "required_market_date": str(required_market_date),
            "quote_local_date": str(quote_local_date) if quote_local_date else None,
            "market_session_window": session.get("market_session_window"),
            "last_completed_market_date": session.get("last_completed_market_date"),
            "market_holiday_today": now_local.date() in NYSE_FULL_HOLIDAYS_2026,
            "market_close_time_az": market_close.isoformat(timespec="minutes"),
            "required_tier_one_symbol_count": len(required_symbols),
            "deployment_intraday_required_symbol_count": len(intraday_required_symbols),
            "quote_observed_symbol_count": len(observed_symbols),
            "missing_required_symbols": missing_required,
            "missing_intraday_required_symbols": missing_intraday_required,
            "not_requested_required_symbols": not_requested_required,
            "nonfresh_snapshot_count": len(non_intraday_fresh_snapshots),
            "stale_or_missing_snapshot_count": len(stale_or_missing_snapshots),
            "stale_unexpected_snapshot_count": len(stale_unexpected_snapshots),
            "calendar_freshness_counts": calendar_freshness_counts,
            "max_quote_age_seconds": max_age_seconds,
            "quote_retry_attempted": quote_retry.get("attempted"),
            "quote_retry_attempt_count": quote_retry.get("attempt_count"),
            "quote_retry_cleared": quote_retry.get("cleared"),
            "quote_retry_final_reasons": quote_retry.get("final_reasons"),
            "wf68_times_local": [item.isoformat(timespec="minutes") for item in wf68_times],
            "tier_a_probe_times_local": [item.isoformat(timespec="minutes") for item in tier_a_times],
            "composite_quote_refresh_times_local": [item.isoformat(timespec="minutes") for item in quote_refresh_times],
            "p0_guard_times_local": [item.isoformat(timespec="minutes") for item in p0_times],
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "next_safe_action": "If blocked, refresh WF68 quote snapshot and P0 hardening proof; if ok, use WF78 queue for review-only owner-card preparation only.",
        },
        "checks": checks,
        "quote_retry": quote_retry,
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [check["name"] for check in critical],
            "warnings": [check["name"] for check in warnings],
        },
        "warning_owner_policy": {
            "wf78_event_queue_keeps_fresh_quote_first": {
                "owner_workflow": "WF78",
                "owner": "finance_event_rerouting",
                "expires_after_utc": "2026-06-17T23:59:59Z",
                "close_condition": "WF78 event rerouting top action is capital_candidate_fresh_quote_band_stop_required or warning is removed with replacement proof.",
                "permanent_noise_allowed": False,
            }
        },
        "stop_lines": [
            "Fresh quote proof does not authorize capital deployment or execution.",
            "Cron may refresh proof only; it may not place paper/live orders or mutate account/portfolio/canon state.",
            "Owner approval is still required for any capital or execution action.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cron timing for Tier 1 quote readiness.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_report()
    out = Path(args.out)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
