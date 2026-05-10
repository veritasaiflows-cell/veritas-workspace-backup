"""earnings_calendar_enrichment.py

Pulls next confirmed earnings dates from yfinance for all Coverage Universe
equity names. Compares against the standing timing-sensitive Event Calendar
watchlist and flags newly confirmable entries or date changes.

Usage:
    python scripts/earnings_calendar_enrichment.py

Requirements:
    pip install yfinance

Output:
    tmp/earnings-calendar.json   -- full structured output
    Terminal summary             -- upcoming dates, watchlist flags, alerts
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

WORKSPACE = Path(__file__).resolve().parents[1]
OUT_PATH = WORKSPACE / "tmp" / "earnings-calendar.json"
CONFIG_PATH = WORKSPACE / "tmp" / "portfolio-config.json"
STALE_AFTER_DAYS = 7
EXPECTED_UPDATE_WINDOW = "Refresh weekly, before event-calendar maintenance, and when major earnings windows approach or resolve."

COVERAGE: dict[str, str] = {
    "XOM": "XOM",
    "LNG": "LNG",
    "CVX": "CVX",
    "COP": "COP",
    "EOG": "EOG",
    "ET": "ET",
    "WMB": "WMB",
    "MPLX": "MPLX",
    "LMT": "LMT",
    "RTX": "RTX",
    "NOC": "NOC",
    "GD": "GD",
    "KTOS": "KTOS",
    "LDOS": "LDOS",
    "BAH": "BAH",
    "SAIC": "SAIC",
    "MSFT": "MSFT",
    "GOOG": "GOOG",
    "NVDA": "NVDA",
    "ETN": "ETN",
    "AMD": "AMD",
    "VRT": "VRT",
    "PLTR": "PLTR",
    "SMCI": "SMCI",
    "EQIX": "EQIX",
    "ASML": "ASML",
    "AMAT": "AMAT",
    "LRCX": "LRCX",
    "JPM": "JPM",
    "GS": "GS",
    "BRK.B": "BRK-B",
    "AMZN": "AMZN",
    "CAT": "CAT",
    "LLY": "LLY"
}

# Keep this focused on live timing-sensitive names where date drift can still
# change near-term operator behavior. Broad quarter-ahead comparisons belong in
# the note layer, not as a standing machine-warning source.
#
# Dates here are operating comparison dates, not a claim of primary-source
# confirmation. A note-layer item can still remain explicitly unconfirmed even
# when this watchlist carries the current working estimate to avoid stale-noise
# churn in every chain run.
WATCHLIST: dict[str, str | None] = {
    "BRK.B": "2026-05-02",
    "ETN": "2026-05-05",
    "NVDA": "2026-05-20",
    "PLTR": "2026-05-04",
    "AMD": "2026-05-05",
    "SMCI": "2026-05-05",
}

# Explicit post-earnings holds are allowed only when a just-reported name is
# still carrying the elapsed print as its next upcoming date. This avoids
# lying about a fresh upcoming catalyst without fabricating an unconfirmed
# next-quarter date.
POST_EARNINGS_MANUAL_HOLDS: dict[str, dict[str, str]] = {
    "BRK.B": {
        "stale_date": "2026-05-02",
        "reason": "reported 2026-05-02; next-quarter date not yet primary-confirmed",
    },
    "CAT": {
        "stale_date": "2026-04-30",
        "reason": "reported 2026-04-30; next-quarter date not yet primary-confirmed",
    },
}

UPCOMING_WINDOW_DAYS = 30
TIMING_SENSITIVE_ALERT_WINDOW_DAYS = 14


def fetch_earnings_date(display_ticker: str, yf_ticker: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ticker": display_ticker,
        "next_earnings_date": None,
        "source": "yfinance",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }
    try:
        t = yf.Ticker(yf_ticker)
        cal = t.calendar

        earnings_dt: date | None = None

        if cal is None:
            record["error"] = "calendar returned None"
            return record

        if isinstance(cal, dict):
            # yfinance 1.3.x returns datetime.date objects (not datetime.datetime).
            # datetime.date has no .date() method -- must handle both types explicitly.
            raw = cal.get("Earnings Date") or cal.get("Earnings date")
            if raw:
                if isinstance(raw, list):
                    raw = raw[0]
                if isinstance(raw, datetime):
                    # datetime.datetime -- call .date() to strip time component
                    earnings_dt = raw.date()
                elif isinstance(raw, date):
                    # datetime.date -- already a date, use directly
                    earnings_dt = raw
                elif isinstance(raw, str):
                    earnings_dt = date.fromisoformat(str(raw)[:10])
        elif hasattr(cal, "to_dict"):
            d = cal.to_dict()
            raw = d.get("Earnings Date") or d.get("Earnings date")
            if raw:
                first = list(raw.values())[0] if isinstance(raw, dict) else raw[0]
                if isinstance(first, datetime):
                    earnings_dt = first.date()
                elif isinstance(first, date):
                    earnings_dt = first
                elif isinstance(first, str):
                    earnings_dt = date.fromisoformat(str(first)[:10])

        if earnings_dt is None:
            record["error"] = "no earnings date in calendar response"
        else:
            record["next_earnings_date"] = earnings_dt.isoformat()

    except Exception as exc:
        record["error"] = str(exc)

    return record


def apply_post_earnings_manual_hold(record: dict[str, Any]) -> dict[str, Any]:
    hold = POST_EARNINGS_MANUAL_HOLDS.get(str(record.get("ticker") or ""))
    if not hold:
        return record

    stale_date = hold.get("stale_date")
    if record.get("next_earnings_date") != stale_date:
        return record

    record["next_earnings_date"] = None
    record["source"] = "manual_post_earnings_hold"
    record["manual_hold"] = {
        "held_prior_date": stale_date,
        "reason": hold.get("reason") or "manual post-earnings hold",
    }
    return record


def days_until(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str)
        return (d - date.today()).days
    except Exception:
        return None


def compare_to_watchlist(record: dict[str, Any], watchlist_date: str | None) -> str:
    fetched_date = record.get("next_earnings_date")
    manual_hold = record.get("manual_hold")
    if manual_hold:
        return "confirmed manual hold -- recently reported; next date pending confirmation"
    if fetched_date is None:
        return "no date from yfinance"
    if watchlist_date is None:
        return "NEW -- not in vault watchlist: " + fetched_date
    if fetched_date == watchlist_date:
        return "confirmed -- matches vault"
    ticker = str(record.get("ticker") or "unknown")
    return "DATE CHANGED -- vault has " + watchlist_date + ", yfinance shows " + fetched_date


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    sep = "=" * 74
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("")
    print(sep)
    print("  EARNINGS CALENDAR ENRICHMENT  --  " + now)
    print(sep)
    print("  Fetching earnings dates for " + str(len(COVERAGE)) + " names...")
    print("")

    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for display_ticker, yf_ticker in COVERAGE.items():
        print("  " + display_ticker + "...", end=" ", flush=True)
        rec = fetch_earnings_date(display_ticker, yf_ticker)
        rec = apply_post_earnings_manual_hold(rec)
        records.append(rec)
        if rec["error"]:
            print("no date (" + rec["error"] + ")")
            errors.append(display_ticker)
        else:
            manual_hold = rec.get("manual_hold")
            if manual_hold:
                print("manual hold (" + str(manual_hold.get("reason") or "recently reported") + ")")
            else:
                print(rec["next_earnings_date"])

    print("")
    print("  WATCHLIST COMPARISON")
    print("  " + "-" * 60)

    alerts: list[str] = []
    timing_sensitive_alerts: list[str] = []
    for rec in records:
        ticker = rec["ticker"]
        if ticker not in WATCHLIST:
            continue
        watchlisted = WATCHLIST[ticker]
        flag = compare_to_watchlist(rec, watchlisted)
        status_char = "OK" if flag.startswith("confirmed") else "!!"
        print("  [" + status_char + "] " + "{:<8}".format(ticker) + "  " + flag)
        if not flag.startswith("confirmed"):
            alert_text = ticker + ": " + flag
            alerts.append(alert_text)
            timing_days = days_until(rec["next_earnings_date"])
            if timing_days is not None and 0 <= timing_days <= TIMING_SENSITIVE_ALERT_WINDOW_DAYS:
                timing_sensitive_alerts.append(alert_text)

    upcoming = []
    for rec in records:
        d = rec["next_earnings_date"]
        if not d:
            continue
        days = days_until(d)
        if days is not None and 0 <= days <= UPCOMING_WINDOW_DAYS:
            upcoming.append((days, rec["ticker"], d))
    upcoming.sort()

    print("")
    print("  UPCOMING EARNINGS (next " + str(UPCOMING_WINDOW_DAYS) + " days)")
    print("  " + "-" * 60)
    if upcoming:
        for days, ticker, dt in upcoming:
            day_label = "today" if days == 0 else ("tomorrow" if days == 1 else "in " + str(days) + " days")
            print("  " + "{:<8}".format(ticker) + "  " + dt + "  (" + day_label + ")")
    else:
        print("  none in the next " + str(UPCOMING_WINDOW_DAYS) + " days")

    if alerts:
        print("")
        print("  ALERTS -- REVIEW")
        print("  " + "-" * 60)
        for a in alerts:
            print("  !! " + a)

    if timing_sensitive_alerts:
        print("")
        print("  TIMING-SENSITIVE ALERTS -- ACTION REQUIRED")
        print("  " + "-" * 60)
        for a in timing_sensitive_alerts:
            print("  !! " + a)

    warnings: list[str] = []
    if errors:
        warnings.append("One or more coverage names failed to return a next earnings date.")
    if timing_sensitive_alerts:
        warnings.append("Timing-sensitive watchlist/date mismatches detected. Review before updating critical catalyst notes.")
    elif alerts:
        warnings.append("Non-blocking watchlist/date mismatches remain outside the active timing window.")

    print("")
    print("  Fetch errors (" + str(len(errors)) + "): " + (", ".join(errors) if errors else "none"))

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of_date": today.isoformat(),
        "status": "ok" if not errors else ("partial" if len(errors) < len(COVERAGE) else "error"),
        "stale_after_days": STALE_AFTER_DAYS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": None,
        "warnings": warnings,
        "upcoming_window_days": UPCOMING_WINDOW_DAYS,
        "records": records,
        "watchlist_alerts": alerts,
        "timing_sensitive_alerts": timing_sensitive_alerts,
        "timing_sensitive_alert_window_days": TIMING_SENSITIVE_ALERT_WINDOW_DAYS,
        "fetch_errors": errors,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if warnings:
        print("  Warnings:")
        for warning in warnings:
            print("  - " + warning)

    print("  Output written to tmp/earnings-calendar.json")
    print(sep)
    print("")


if __name__ == "__main__":
    main()
