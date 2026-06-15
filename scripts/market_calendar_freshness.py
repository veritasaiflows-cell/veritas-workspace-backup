#!/usr/bin/env python3
"""Shared market-calendar freshness vocabulary for finance quote proof.

The contract is intentionally narrow: classify quote timestamps against the
latest completed US equity market session so weekend/holiday/off-hours quote
age does not masquerade as a live provider failure. It grants no capital,
execution, account, or portfolio authority.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

AZ = ZoneInfo("America/Phoenix")
MARKET_OPEN = time(6, 30)
OPEN_SETTLED = time(6, 42)
MARKET_CLOSE = time(13, 0)
EARLY_CLOSE = time(11, 0)
FRESH_SECONDS = 15 * 60
CURRENT_SECONDS = 24 * 60 * 60

NYSE_FULL_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}

NYSE_EARLY_CLOSES_2026 = {
    date(2026, 11, 27),
    date(2026, 12, 24),
}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def is_market_day(day: date) -> bool:
    return day.weekday() < 5 and day not in NYSE_FULL_HOLIDAYS_2026


def market_close_for_date(day: date) -> time:
    return EARLY_CLOSE if day in NYSE_EARLY_CLOSES_2026 else MARKET_CLOSE


def latest_market_date(now_local: datetime) -> date:
    cursor = now_local.date()
    while not is_market_day(cursor):
        cursor = date.fromordinal(cursor.toordinal() - 1)
    return cursor


def last_completed_market_date(now_local: datetime) -> date:
    cursor = latest_market_date(now_local)
    if cursor == now_local.date() and now_local.time() < market_close_for_date(cursor):
        cursor = date.fromordinal(cursor.toordinal() - 1)
        while not is_market_day(cursor):
            cursor = date.fromordinal(cursor.toordinal() - 1)
    return cursor


def market_session(now_utc: datetime | None = None) -> dict[str, Any]:
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_local = now_utc.astimezone(AZ)
    today = now_local.date()
    latest = latest_market_date(now_local)
    completed = last_completed_market_date(now_local)
    close_time = market_close_for_date(today)

    if not is_market_day(today):
        window = "market_closed_weekend_or_holiday"
    elif now_local.time() < MARKET_OPEN:
        window = "pre_open"
    elif now_local.time() < OPEN_SETTLED:
        window = "open_settling"
    elif now_local.time() <= close_time:
        window = "market_hours_fresh"
    else:
        window = "post_close"

    return {
        "timezone": "America/Phoenix",
        "now_local": now_local.isoformat(),
        "market_session_window": window,
        "market_open_time_az": MARKET_OPEN.isoformat(timespec="minutes"),
        "market_close_time_az": close_time.isoformat(timespec="minutes"),
        "latest_market_date": latest.isoformat(),
        "last_completed_market_date": completed.isoformat(),
        "market_day_today": is_market_day(today),
        "market_holiday_today": today in NYSE_FULL_HOLIDAYS_2026,
        "early_close_today": today in NYSE_EARLY_CLOSES_2026,
        "fresh_intraday_expected": window == "market_hours_fresh",
        "fresh_intraday_allowed": window == "market_hours_fresh",
        "closed_market_expected_stale_allowed": window
        in {"market_closed_weekend_or_holiday", "pre_open", "post_close"},
        "policy": (
            "Regular session requires fresh intraday quotes. Closed-market, "
            "pre-open, weekend, and holiday windows accept last-completed-session "
            "quotes for review-only monitoring but never for execution freshness."
        ),
    }


def legacy_freshness_status(source_dt: datetime | None, received_at: datetime, fresh_seconds: int, current_seconds: int) -> tuple[str, int | None]:
    if source_dt is None:
        return "missing_source_timestamp", None
    age = max(0, int((received_at - source_dt).total_seconds()))
    if age <= fresh_seconds:
        return "fresh", age
    if age <= current_seconds:
        return "current_but_not_intraday_fresh", age
    return "stale", age


def classify_quote_freshness(
    source_ts: str | None,
    received_at: datetime,
    *,
    fresh_seconds: int = FRESH_SECONDS,
    current_seconds: int = CURRENT_SECONDS,
) -> dict[str, Any]:
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    received_at = received_at.astimezone(timezone.utc)
    session = market_session(received_at)
    source_dt = parse_utc(source_ts)
    legacy_status, age_seconds = legacy_freshness_status(source_dt, received_at, fresh_seconds, current_seconds)

    if source_dt is None:
        calendar_status = "provider_missing"
        source_market_date = None
    else:
        source_market_date = source_dt.astimezone(AZ).date().isoformat()
        if age_seconds is not None and age_seconds <= fresh_seconds:
            calendar_status = "fresh_intraday"
        elif source_market_date == session["last_completed_market_date"]:
            calendar_status = "current_last_completed_session"
        elif session["closed_market_expected_stale_allowed"] and source_market_date == session["latest_market_date"]:
            calendar_status = "market_closed_expected_stale"
        else:
            calendar_status = "stale_unexpected"

    return {
        "freshness_status": legacy_status,
        "calendar_freshness_status": calendar_status,
        "age_seconds": age_seconds,
        "source_market_date": source_market_date,
        "market_session_window": session["market_session_window"],
        "latest_market_date": session["latest_market_date"],
        "last_completed_market_date": session["last_completed_market_date"],
        "fresh_intraday_expected": session["fresh_intraday_expected"],
        "fresh_intraday_allowed": session["fresh_intraday_allowed"],
        "closed_market_expected_stale_allowed": session["closed_market_expected_stale_allowed"],
        "policy": session["policy"],
    }
