"""event_calendar_rollforward.py

Read-only roll-forward packet for the Event Calendar note.

The script compares provider next-earnings dates from tmp/earnings-calendar.json
against dated ticker rows currently visible in 05. Intelligence/Event Calendar.md
and emits review-ready roll-forward proposals. It does not edit the vault note.

Usage:
    python scripts/event_calendar_rollforward.py [--write-md]

Inputs:
    tmp/earnings-calendar.json
    tmp/portfolio-config.json
    05. Intelligence/Event Calendar.md

Outputs:
    tmp/event-calendar-rollforward.json
    optional Markdown digest when --write-md is supplied
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
EARNINGS_PATH = TMP / "earnings-calendar.json"
CONFIG_PATH = TMP / "portfolio-config.json"
SOURCE_CONFIDENCE_PATH = TMP / "earnings-date-source-confidence.json"
EVENT_CALENDAR_PATH = WORKSPACE / "05. Intelligence" / "Event Calendar.md"
OUT_JSON = TMP / "event-calendar-rollforward.json"
OUT_MD = OUT_JSON.with_suffix(".md")
STALE_AFTER_HOURS = 24

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

ROW_RE = re.compile(
    r"^\|\s*(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})\s*\|[^|]*\|(?P<event>[^|]+)\|(?P<priority>[^|]+)\|(?P<notes>[^|]*)\|"
)
TICKER_RE = re.compile(r"\b[A-Z]{1,5}(?:\.B)?\b")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_generated_age_hours(payload: dict[str, Any]) -> float | None:
    generated = payload.get("generated_at_utc")
    if not generated:
        return None
    try:
        ts = datetime.fromisoformat(str(generated))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2)
    except Exception:
        return None


def parse_event_calendar_rows(text: str, year: int) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = ROW_RE.match(line)
        if not match:
            continue
        month = MONTHS[match.group("month")]
        day = int(match.group("day"))
        try:
            event_date = date(year, month, day)
        except ValueError:
            continue
        event = match.group("event").strip()
        notes = match.group("notes").strip()
        for ticker in TICKER_RE.findall(event):
            # Ignore common all-caps non-ticker event acronyms unless the ticker
            # is tracked by the config filter downstream.
            by_ticker.setdefault(ticker, []).append({
                "date": event_date.isoformat(),
                "line": line_no,
                "event": event,
                "notes": notes,
                "raw": line,
            })
    return by_ticker


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest.")
    args = parser.parse_args()
    today = date.today()
    earnings = load_json(EARNINGS_PATH)
    config = load_json(CONFIG_PATH)
    source_confidence = load_json(SOURCE_CONFIDENCE_PATH) if SOURCE_CONFIDENCE_PATH.exists() else {}
    calendar_text = EVENT_CALENDAR_PATH.read_text(encoding="utf-8")

    tracked = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}
    watchlist = config.get("earnings_date_watchlist") if isinstance(config.get("earnings_date_watchlist"), dict) else {}
    rows_by_ticker = parse_event_calendar_rows(calendar_text, today.year)
    earnings_records = {rec.get("ticker"): rec for rec in earnings.get("records", []) if isinstance(rec, dict) and rec.get("ticker")}
    confidence_records = {
        rec.get("ticker"): rec
        for rec in source_confidence.get("records", [])
        if isinstance(rec, dict) and rec.get("ticker")
    }

    proposals: list[dict[str, Any]] = []
    warnings: list[str] = []
    earnings_age = parse_generated_age_hours(earnings)
    if earnings.get("status") not in ("ok", "partial"):
        warnings.append("earnings-calendar artifact is not usable")
    if earnings_age is None or earnings_age > 24 * int(earnings.get("stale_after_days", 7)):
        warnings.append("earnings-calendar artifact is stale or missing generated_at_utc")

    for ticker, meta in sorted(tracked.items()):
        rec = earnings_records.get(ticker)
        provider_date = parse_iso_date(rec.get("next_earnings_date") if rec else None)
        if provider_date is None:
            continue
        current_rows = rows_by_ticker.get(ticker, [])
        if not current_rows:
            continue
        latest_row = max(current_rows, key=lambda row: row["date"])
        vault_date = parse_iso_date(latest_row.get("date"))
        if vault_date is None:
            continue

        # Roll-forward condition: the vault row is elapsed or older than the
        # provider's current next date. This is a review packet, not authority.
        if provider_date <= today or provider_date == vault_date:
            continue
        if vault_date > today and provider_date <= vault_date:
            continue

        watch_entry = watchlist.get(ticker)
        primary_confirmed = False
        if isinstance(watch_entry, dict):
            primary_confirmed = bool(watch_entry.get("primary_confirmed"))
        confidence_row = confidence_records.get(ticker)
        if isinstance(confidence_row, dict) and confidence_row.get("source_confidence") == "primary_confirmed":
            primary_confirmed = True
        confidence = "primary_confirmed" if primary_confirmed else "provider_estimate_unconfirmed"
        lane = meta.get("coverage_lane") or "unknown"
        action = "roll_forward_review"
        if ticker in watchlist and not primary_confirmed:
            action = "keep_timing_sensitive_until_primary_confirmed"

        proposals.append({
            "ticker": ticker,
            "coverage_lane": lane,
            "portfolio_role": meta.get("portfolio_role"),
            "vault_date": vault_date.isoformat(),
            "provider_next_earnings_date": provider_date.isoformat(),
            "days_until_provider_date": (provider_date - today).days,
            "confidence": confidence,
            "recommended_action": action,
            "source": rec.get("source") if rec else None,
            "fetched_at_utc": rec.get("fetched_at_utc") if rec else None,
            "event_calendar_line": latest_row.get("line"),
            "event_calendar_event": latest_row.get("event"),
            "note": "Update Event Calendar as a provider-estimated next-quarter date unless primary IR/SEC confirmation is available.",
        })

    status = "ok" if not warnings else "partial"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": "Run after earnings_calendar_enrichment.py and before Event Calendar maintenance.",
        "source": {
            "earnings_calendar": str(EARNINGS_PATH.relative_to(WORKSPACE)),
            "portfolio_config": str(CONFIG_PATH.relative_to(WORKSPACE)),
            "source_confidence": str(SOURCE_CONFIDENCE_PATH.relative_to(WORKSPACE)) if SOURCE_CONFIDENCE_PATH.exists() else None,
            "event_calendar": str(EVENT_CALENDAR_PATH.relative_to(WORKSPACE)),
            "earnings_generated_at_utc": earnings.get("generated_at_utc"),
            "earnings_age_hours": earnings_age,
        },
        "warnings": warnings,
        "proposals": proposals,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Event Calendar Roll-Forward Review",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Status: {status}",
        "",
        "This is a review-only packet. It does not authorize silent canonical note mutation.",
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend([f"- {warning}" for warning in warnings])
        lines.append("")
    lines.extend([
        "## Proposed roll-forwards",
        "",
        "| Ticker | Vault date | Provider next date | Confidence | Action |",
        "|---|---:|---:|---|---|",
    ])
    if proposals:
        for row in proposals:
            lines.append(
                f"| {row['ticker']} | {row['vault_date']} | {row['provider_next_earnings_date']} "
                f"| {row['confidence']} | {row['recommended_action']} |"
            )
    else:
        lines.append("| — | — | — | — | No roll-forward proposals |")
    lines.extend([
        "",
        "## Suggested Event Calendar wording",
        "",
        "Use wording like: `Next expected earnings: YYYY-MM-DD per yfinance/provider estimate; not primary-confirmed. Keep as timing watch only until IR/SEC confirmation or company release.`",
        "",
    ])
    if args.write_md:
        OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("event calendar roll-forward proposals:", len(proposals))
    for row in proposals:
        print(f"  {row['ticker']}: {row['vault_date']} -> {row['provider_next_earnings_date']} ({row['confidence']})")
    if warnings:
        print("warnings:")
        for warning in warnings:
            print("  -", warning)
    print("wrote", OUT_JSON)
    if args.write_md:
        print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
