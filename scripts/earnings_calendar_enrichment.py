"""earnings_calendar_enrichment.py

Pulls next confirmed earnings dates from yfinance for all Coverage and Watchlist
equity names. Compares against the standing timing-sensitive Event Calendar
watchlist and flags newly confirmable entries or date changes.

Usage:
    python scripts/earnings_calendar_enrichment.py
    python scripts/earnings_calendar_enrichment.py --tickers AJG AXON --merge-existing

Requirements:
    pip install yfinance

Output:
    tmp/earnings-calendar.json   -- full structured output
    Terminal summary             -- upcoming dates, watchlist flags, alerts
"""

from __future__ import annotations

import argparse
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
    "BKNG": "BKNG",
    "CAT": "CAT",
    "LLY": "LLY",
    # 2026-05-15 sector-expansion machine-tracked equities. ETFs/funds do
    # not belong here because this artifact is an earnings-catalyst surface,
    # not a distribution/ex-dividend calendar.
    "LIN": "LIN",
    "ECL": "ECL",
    "VMC": "VMC",
    "META": "META",
    "NFLX": "NFLX",
    "TMUS": "TMUS",
    "PH": "PH",
    "GE": "GE",
    "CME": "CME",
}

# Keep comparison baselines out of code. The script can fetch fresh provider
# dates for the full coverage list, but only operator-selected timing-sensitive
# baselines should produce DATE CHANGED alerts. Configure those under
# tmp/portfolio-config.json -> earnings_date_watchlist.
WATCHLIST_CONFIG_FIELD = "earnings_date_watchlist"
WATCHLIST_CLOSEOUT_BACKUP_DIR = WORKSPACE / "tmp" / "portfolio-config-backups"

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
        "date_source_class": "provider_estimate",
        "primary_confirmed": False,
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


def load_portfolio_config() -> dict[str, Any]:
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_earnings_date_watchlist(config: dict[str, Any]) -> dict[str, str | None]:
    """Return configured timing-sensitive comparison baselines.

    Shape accepted:
      "earnings_date_watchlist": {
        "NVDA": {"date": "2026-05-20", ...},
        "TICKER": "2026-05-20"
      }

    This field is deliberately narrow: it is for live dates whose drift would
    change near-term operator behavior, not for every quarter-ahead yfinance
    estimate or already-reported event.
    """
    raw = config.get(WATCHLIST_CONFIG_FIELD)
    if not isinstance(raw, dict):
        return {}

    out: dict[str, str | None] = {}
    for ticker, value in raw.items():
        if not isinstance(ticker, str) or not ticker.strip():
            continue
        clean_ticker = ticker.strip().upper()
        if value is None or isinstance(value, str):
            out[clean_ticker] = value
        elif isinstance(value, dict):
            if str(value.get("status") or "active").lower() in {"closed", "inactive", "resolved"}:
                continue
            date_value = value.get("date")
            out[clean_ticker] = date_value if isinstance(date_value, str) else None
    return out


def parse_iso_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(str(date_str)[:10])
    except Exception:
        return None


def _is_on_or_after(left: str | None, right: str | None) -> bool:
    left_dt = parse_iso_date(left)
    right_dt = parse_iso_date(right)
    return bool(left_dt and right_dt and left_dt >= right_dt)


def build_watchlist_lifecycle_closeouts(
    *,
    config: dict[str, Any],
    records: list[dict[str, Any]],
    today: date,
) -> list[dict[str, Any]]:
    """Return safe active-watchlist closeouts for already-reviewed prints.

    The active watchlist is for timing-sensitive upcoming/just-arrived dates.
    Once the event date is past and tracked_universe records a post-earnings
    review at/after that event, the watch item should stop feeding dashboard
    past-date warnings. This is machine-config maintenance only; it does not
    imply portfolio/canon/trade/account authority.
    """
    raw_watchlist = config.get(WATCHLIST_CONFIG_FIELD) if isinstance(config.get(WATCHLIST_CONFIG_FIELD), dict) else {}
    tracked = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}
    records_by_ticker = {str(rec.get("ticker") or "").upper(): rec for rec in records}
    closeouts: list[dict[str, Any]] = []

    for ticker, entry in raw_watchlist.items():
        clean_ticker = str(ticker or "").strip().upper()
        if not clean_ticker:
            continue
        if isinstance(entry, dict) and str(entry.get("status") or "active").lower() in {"closed", "inactive", "resolved"}:
            continue
        watch_date = entry if isinstance(entry, str) else entry.get("date") if isinstance(entry, dict) else None
        watch_dt = parse_iso_date(watch_date)
        if not watch_dt or watch_dt >= today:
            continue

        meta = tracked.get(clean_ticker) if isinstance(tracked.get(clean_ticker), dict) else {}
        post_review_confirmed = bool(meta.get("post_earnings_review_confirmed"))
        last_earnings_ok = _is_on_or_after(meta.get("last_earnings_date"), str(watch_date))
        review_date_ok = _is_on_or_after(meta.get("post_earnings_review_date"), str(watch_date))
        if not (post_review_confirmed and last_earnings_ok and review_date_ok):
            continue

        rec = records_by_ticker.get(clean_ticker, {})
        closeouts.append({
            "ticker": clean_ticker,
            "watchlist_date": watch_date,
            "provider_date_before_closeout": rec.get("next_earnings_date"),
            "status": "watchlist_cleanup_eligible",
            "reason": "event date elapsed and tracked_universe confirms post-earnings review at/after the event",
            "evidence": {
                "last_earnings_date": meta.get("last_earnings_date"),
                "post_earnings_review_date": meta.get("post_earnings_review_date"),
                "post_earnings_review_confirmed": post_review_confirmed,
            },
            "authority": {
                "review_only": True,
                "portfolio_mutation_allowed": False,
                "canonical_note_mutation_allowed": False,
                "trade_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return closeouts


def build_existing_watchlist_lifecycle_holds(
    *,
    config: dict[str, Any],
    records: list[dict[str, Any]],
    today: date,
) -> list[dict[str, Any]]:
    """Return already-closed watchlist entries that should still suppress stale provider dates."""
    raw_watchlist = config.get(WATCHLIST_CONFIG_FIELD) if isinstance(config.get(WATCHLIST_CONFIG_FIELD), dict) else {}
    tracked = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}
    records_by_ticker = {str(rec.get("ticker") or "").upper(): rec for rec in records}
    holds: list[dict[str, Any]] = []

    for ticker, entry in raw_watchlist.items():
        clean_ticker = str(ticker or "").strip().upper()
        if not clean_ticker or not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "active").lower() not in {"closed", "inactive", "resolved"}:
            continue
        watch_date = entry.get("date")
        watch_dt = parse_iso_date(watch_date)
        if not watch_dt or watch_dt >= today:
            continue
        meta = tracked.get(clean_ticker) if isinstance(tracked.get(clean_ticker), dict) else {}
        if not (
            bool(meta.get("post_earnings_review_confirmed"))
            and _is_on_or_after(meta.get("last_earnings_date"), str(watch_date))
            and _is_on_or_after(meta.get("post_earnings_review_date"), str(watch_date))
        ):
            continue
        rec = records_by_ticker.get(clean_ticker, {})
        holds.append({
            "ticker": clean_ticker,
            "watchlist_date": watch_date,
            "provider_date_before_closeout": rec.get("next_earnings_date"),
            "status": "watchlist_already_closed",
            "reason": entry.get("closeout_reason") or "event watchlist entry already closed after confirmed post-earnings review",
            "evidence": {
                "last_earnings_date": meta.get("last_earnings_date"),
                "post_earnings_review_date": meta.get("post_earnings_review_date"),
                "post_earnings_review_confirmed": bool(meta.get("post_earnings_review_confirmed")),
                "closed_at_utc": entry.get("closed_at_utc"),
            },
            "authority": {
                "review_only": True,
                "portfolio_mutation_allowed": False,
                "canonical_note_mutation_allowed": False,
                "trade_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return holds


def apply_watchlist_lifecycle_closeouts(config: dict[str, Any], closeouts: list[dict[str, Any]]) -> dict[str, Any]:
    if not closeouts:
        return {"applied": False, "count": 0, "tickers": []}
    raw_watchlist = config.get(WATCHLIST_CONFIG_FIELD)
    if not isinstance(raw_watchlist, dict):
        return {"applied": False, "count": 0, "tickers": [], "error": "watchlist field missing or not object"}

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    WATCHLIST_CLOSEOUT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = WATCHLIST_CLOSEOUT_BACKUP_DIR / ("portfolio-config-before-earnings-closeout-" + timestamp.replace(":", "") + ".json")
    backup_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    applied: list[str] = []
    by_ticker = {item["ticker"]: item for item in closeouts}
    for ticker, closeout in by_ticker.items():
        current = raw_watchlist.get(ticker)
        if current is None:
            continue
        if isinstance(current, dict):
            updated = dict(current)
        else:
            updated = {"date": current}
        updated.update({
            "status": "closed",
            "closed_at_utc": timestamp,
            "closed_by": "scripts/earnings_calendar_enrichment.py",
            "closeout_reason": closeout["reason"],
            "next_watch_status": "inactive_until_next_confirmed_or_timing_sensitive_catalyst",
        })
        raw_watchlist[ticker] = updated
        applied.append(ticker)

    if applied:
        config["generated_at_utc"] = timestamp
        config["last_updated_by"] = "scripts/earnings_calendar_enrichment.py earnings watchlist lifecycle closeout"
        CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"applied": bool(applied), "count": len(applied), "tickers": sorted(applied), "backup_path": str(backup_path.relative_to(WORKSPACE))}


def apply_closeout_hold_to_records(records: list[dict[str, Any]], closeouts: list[dict[str, Any]]) -> None:
    closeout_by_ticker = {item["ticker"]: item for item in closeouts}
    for rec in records:
        ticker = str(rec.get("ticker") or "").upper()
        closeout = closeout_by_ticker.get(ticker)
        if not closeout:
            continue
        rec["next_earnings_date"] = None
        rec["source"] = "post_earnings_lifecycle_closeout"
        rec["date_source_class"] = "post_earnings_lifecycle_closeout"
        rec["primary_confirmed"] = False
        rec["lifecycle"] = {
            "status": "post_event_review_confirmed_next_date_pending",
            "closed_watchlist_date": closeout.get("watchlist_date"),
            "provider_date_before_closeout": closeout.get("provider_date_before_closeout"),
            "reason": closeout.get("reason"),
            "evidence": closeout.get("evidence"),
        }


def apply_post_earnings_manual_hold(record: dict[str, Any]) -> dict[str, Any]:
    hold = POST_EARNINGS_MANUAL_HOLDS.get(str(record.get("ticker") or ""))
    if not hold:
        return record

    stale_date = hold.get("stale_date")
    if record.get("next_earnings_date") != stale_date:
        return record

    record["next_earnings_date"] = None
    record["source"] = "manual_post_earnings_hold"
    record["date_source_class"] = "manual_post_earnings_hold"
    record["primary_confirmed"] = False
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
        return "NEW -- no configured baseline: " + fetched_date
    if fetched_date == watchlist_date:
        return "confirmed -- matches configured baseline"
    ticker = str(record.get("ticker") or "unknown")
    return "DATE CHANGED -- baseline has " + watchlist_date + ", yfinance shows " + fetched_date


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the review-only earnings calendar artifact.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Explicit ticker shard to refresh, including symbols outside static coverage.",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Preserve unrefreshed records from the existing output artifact.",
    )
    parser.add_argument(
        "--apply-watchlist-closeouts",
        action="store_true",
        help="Apply eligible watchlist closeouts to portfolio-config.json; requires explicit owner authorization.",
    )
    args = parser.parse_args(argv)
    if args.merge_existing and not args.tickers:
        parser.error("--merge-existing requires --tickers")
    return args


def normalize_tickers(raw_tickers: list[str]) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for raw in raw_tickers:
        ticker = str(raw).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def provider_ticker(display_ticker: str) -> str:
    return COVERAGE.get(display_ticker, display_ticker.replace(".", "-"))


def load_existing_payload() -> dict[str, Any]:
    try:
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def merge_refreshed_records(
    existing_records: list[dict[str, Any]],
    refreshed_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refreshed_by_ticker = {
        str(record.get("ticker") or "").upper(): record
        for record in refreshed_records
        if str(record.get("ticker") or "").strip()
    }
    merged: list[dict[str, Any]] = []
    replaced: set[str] = set()
    for record in existing_records:
        ticker = str(record.get("ticker") or "").upper()
        if ticker in refreshed_by_ticker:
            if ticker not in replaced:
                merged.append(refreshed_by_ticker[ticker])
                replaced.add(ticker)
            continue
        merged.append(record)
    for record in refreshed_records:
        ticker = str(record.get("ticker") or "").upper()
        if ticker not in replaced:
            merged.append(record)
            replaced.add(ticker)
    return merged


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    shard_tickers = normalize_tickers(args.tickers or [])
    shard_mode = bool(args.tickers)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = load_portfolio_config()

    today = date.today()
    sep = "=" * 74
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("")
    print(sep)
    print("  EARNINGS CALENDAR ENRICHMENT  --  " + now)
    print(sep)
    selected_tickers = shard_tickers if shard_mode else list(COVERAGE)
    print("  Fetching earnings dates for " + str(len(selected_tickers)) + " names...")
    print("")

    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for display_ticker in selected_tickers:
        yf_ticker = provider_ticker(display_ticker)
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

    if shard_mode:
        lifecycle_closeouts: list[dict[str, Any]] = []
        lifecycle_holds: list[dict[str, Any]] = []
        lifecycle_apply = {
            "applied": False,
            "count": 0,
            "tickers": [],
            "reason": "disabled_in_ticker_shard_mode",
        }
    else:
        lifecycle_closeouts = build_watchlist_lifecycle_closeouts(config=config, records=records, today=today)
        lifecycle_holds = lifecycle_closeouts + build_existing_watchlist_lifecycle_holds(config=config, records=records, today=today)
        apply_closeout_hold_to_records(records, lifecycle_holds)
        # Collection is review-only by default. An earnings refresh may not
        # silently mutate the legacy watchlist/configuration surface.
        lifecycle_apply = (
            apply_watchlist_lifecycle_closeouts(config, lifecycle_closeouts)
            if args.apply_watchlist_closeouts
            else {
                "applied": False,
                "count": 0,
                "tickers": [],
                "reason": "owner_authorization_not_requested",
            }
        )

    existing_payload = load_existing_payload() if shard_mode and args.merge_existing else {}
    existing_records = existing_payload.get("records") if isinstance(existing_payload.get("records"), list) else []
    if existing_records:
        records = merge_refreshed_records(existing_records, records)
    watchlist = load_earnings_date_watchlist(config)

    if lifecycle_holds:
        print("")
        print("  EARNINGS LIFECYCLE CLOSEOUTS")
        print("  " + "-" * 60)
        for closeout in lifecycle_holds:
            label = "CLOSED" if closeout.get("status") == "watchlist_cleanup_eligible" else "HELD"
            print("  [" + label + "] " + closeout["ticker"] + " " + str(closeout.get("watchlist_date")) + " -- " + closeout["reason"])

    print("")
    print("  CONFIG WATCHLIST COMPARISON")
    print("  " + "-" * 60)
    if not watchlist:
        print("  none configured")

    alerts: list[str] = []
    timing_sensitive_alerts: list[str] = []
    for rec in records:
        ticker = rec["ticker"]
        if ticker not in watchlist:
            continue
        watchlisted = watchlist[ticker]
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

    scope_size = len(selected_tickers)
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of_date": today.isoformat(),
        "status": "ok" if not errors else ("partial" if len(errors) < scope_size else "error"),
        "stale_after_days": STALE_AFTER_DAYS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": None,
        "warnings": warnings,
        "upcoming_window_days": UPCOMING_WINDOW_DAYS,
        "records": records,
        "watchlist_alerts": alerts,
        "watchlist_source": str(CONFIG_PATH.relative_to(WORKSPACE)) + ":" + WATCHLIST_CONFIG_FIELD,
        "watchlist_tickers": sorted(watchlist.keys()),
        "earnings_lifecycle": {
            "schema_version": 1,
            "closeouts": lifecycle_closeouts,
            "active_holds": lifecycle_holds,
            "config_apply": lifecycle_apply,
            "authority": {
                "review_only": True,
                "portfolio_mutation_allowed": False,
                "canonical_note_mutation_allowed": False,
                "trade_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        "timing_sensitive_alerts": timing_sensitive_alerts,
        "timing_sensitive_alert_window_days": TIMING_SENSITIVE_ALERT_WINDOW_DAYS,
        "fetch_errors": errors,
    }
    if shard_mode:
        payload["refresh_scope"] = {
            "mode": "ticker_shard",
            "tickers": selected_tickers,
            "merge_existing": bool(args.merge_existing),
            "review_only": True,
            "portfolio_config_mutation_allowed": False,
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
