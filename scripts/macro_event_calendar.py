#!/usr/bin/env python3
"""Build the Veritas macro-event calendar.

This is a review-only macro schedule surface for high-impact U.S. releases.
It tracks event timing and follow-up expectations, but does not make forecast,
probability, portfolio, paper-trading, or execution claims.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "macro-event-calendar.json"
DEFAULT_MD = TMP / "macro-event-calendar.md"
MARKET_STATE = TMP / "market-state.json"
MACRO_REGIME = TMP / "macro-regime.json"

SCHEMA = "veritas.macro_event_calendar.v1"
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "forecast_or_probability_claim_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def event(
    *,
    event_id: str,
    date_text: str,
    time_et: str,
    agency: str,
    metric: str,
    period: str,
    source_url: str,
    market_sensitivity: str,
    follow_up: str,
    official_confirmed: bool = True,
) -> dict[str, Any]:
    hour, minute = [int(part) for part in time_et.split(":")]
    local_dt = datetime.fromisoformat(date_text).replace(hour=hour, minute=minute, tzinfo=EASTERN)
    return {
        "event_id": event_id,
        "event_at_utc": iso_utc(local_dt),
        "date": date_text,
        "time_et": time_et,
        "timezone": "America/New_York",
        "agency": agency,
        "metric": metric,
        "period": period,
        "importance": "high",
        "source_url": source_url,
        "source_type": "official_release_calendar",
        "official_confirmed": official_confirmed,
        "market_sensitivity": market_sensitivity,
        "macro_channels": ["rates", "inflation", "growth", "equities", "credit"],
        "expected_followup": follow_up,
    }


def seeded_events() -> list[dict[str, Any]]:
    return [
        event(
            event_id="2026-06-05-bls-employment-situation-may-2026",
            date_text="2026-06-05",
            time_et="08:30",
            agency="BLS",
            metric="Employment Situation",
            period="May 2026",
            source_url="https://www.bls.gov/cps/home.htm",
            market_sensitivity="Labor strength, unemployment, wages, and Fed-cut timing.",
            follow_up="Refresh labor read-through, rates reaction, risk appetite, and candidate sizing discipline after release.",
        ),
        event(
            event_id="2026-06-10-bls-cpi-may-2026",
            date_text="2026-06-10",
            time_et="08:30",
            agency="BLS",
            metric="Consumer Price Index",
            period="May 2026",
            source_url="https://www.bls.gov/cpi/",
            market_sensitivity="Inflation path, real yields, Fed-cut probability, duration, and no-chase discipline.",
            follow_up="Refresh inflation posture, policy expectations, market-state, macro regime, and deployment stop lines after release.",
        ),
        event(
            event_id="2026-06-11-bls-ppi-may-2026",
            date_text="2026-06-11",
            time_et="08:30",
            agency="BLS",
            metric="Producer Price Index",
            period="May 2026",
            source_url="https://www.bls.gov/ppi/",
            market_sensitivity="Pipeline inflation, margin pressure, rates, and sector rotation.",
            follow_up="Refresh inflation read-through and watch for margin-sensitive sector impacts after release.",
        ),
        event(
            event_id="2026-06-17-fomc-policy-decision",
            date_text="2026-06-17",
            time_et="14:00",
            agency="Federal Reserve",
            metric="FOMC Policy Decision",
            period="June 2026",
            source_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            market_sensitivity="Policy rate path, dot-plot/readout if applicable, rates, dollar, and risk assets.",
            follow_up="Refresh policy expectations, macro regime, portfolio posture, and stop-line state after statement/press conference.",
        ),
        event(
            event_id="2026-06-25-bea-pce-personal-income-outlays-may-2026",
            date_text="2026-06-25",
            time_et="08:30",
            agency="BEA",
            metric="Personal Income and Outlays / PCE",
            period="May 2026",
            source_url="https://www.bea.gov/news/schedule",
            market_sensitivity="Fed-preferred inflation, consumption, income, and growth quality.",
            follow_up="Refresh Fed-preferred inflation posture and consumer/growth thesis after release.",
        ),
    ]


def annotate_events(events: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in events:
        event_dt = datetime.fromisoformat(str(item["event_at_utc"]).replace("Z", "+00:00"))
        days_until = (event_dt.date() - now.date()).days
        status = "elapsed" if event_dt < now else "today" if event_dt.date() == now.date() else "upcoming"
        row = dict(item)
        row["status"] = status
        row["days_until"] = days_until
        row["requires_day_of_followup"] = status in {"today", "upcoming"} and days_until <= 1
        rows.append(row)
    return sorted(rows, key=lambda row: row["event_at_utc"])


def build_calendar(as_of: date | None = None) -> dict[str, Any]:
    now = utc_now()
    if as_of is not None:
        now = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)

    market_state = as_dict(load_json_artifact(MARKET_STATE))
    macro_regime = as_dict(load_json_artifact(MACRO_REGIME))
    events = annotate_events(seeded_events(), now)
    upcoming = [row for row in events if row["status"] in {"today", "upcoming"}]
    next_7 = [row for row in upcoming if int(row["days_until"]) <= 7]
    next_14 = [row for row in upcoming if int(row["days_until"]) <= 14]
    next_30 = [row for row in upcoming if int(row["days_until"]) <= 30]
    next_event = upcoming[0] if upcoming else None

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": iso_utc(now),
        "status": "ok",
        "source_posture": "official_calendar_seeded_review_only",
        "source_artifacts": [
            {"path": rel(MARKET_STATE), "exists": MARKET_STATE.exists(), "status": market_state.get("status")},
            {"path": rel(MACRO_REGIME), "exists": MACRO_REGIME.exists(), "status": macro_regime.get("status")},
        ],
        "current_macro_state": {
            "macro_regime": macro_regime.get("macro_regime") or macro_regime.get("regime"),
            "macro_verdict": macro_regime.get("verdict") or macro_regime.get("summary"),
            "fed_target_range": as_dict(as_dict(market_state.get("macro")).get("fed")).get("target_range"),
        },
        "events": events,
        "summary": {
            "event_count": len(events),
            "upcoming_event_count": len(upcoming),
            "next_7_day_count": len(next_7),
            "next_14_day_count": len(next_14),
            "next_30_day_count": len(next_30),
            "next_event_id": as_dict(next_event).get("event_id"),
            "next_event_metric": as_dict(next_event).get("metric"),
            "next_event_date": as_dict(next_event).get("date"),
            "high_impact_next_14_days": [
                {"date": row["date"], "metric": row["metric"], "agency": row["agency"], "period": row["period"]}
                for row in next_14
            ],
        },
        "operator_followup_contract": {
            "before_event": "Flag event risk in daily/weekly intelligence and avoid overstating deployment certainty ahead of high-impact releases.",
            "after_event": "Refresh market-state, macro-regime, daily review objects, deployment readiness, and capital-deployment recommendation validators.",
            "owner_decision_required": "Any resulting capital deployment, paper order, or canon/portfolio mutation still requires the normal gated approval path.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    events = payload.get("events")
    if not isinstance(events, list) or len(events) < 5:
        errors.append("expected at least five macro events")
    metrics = {str(row.get("metric")) for row in events if isinstance(row, dict)}
    for metric in ("Employment Situation", "Consumer Price Index", "Producer Price Index", "FOMC Policy Decision", "Personal Income and Outlays / PCE"):
        if metric not in metrics:
            errors.append(f"missing required macro metric: {metric}")
    upcoming = [row for row in events if isinstance(row, dict) and row.get("status") in {"today", "upcoming"}]
    if not upcoming:
        warnings.append("no upcoming macro events remain in seeded window")
    for row in events if isinstance(events, list) else []:
        if not isinstance(row, dict):
            errors.append("event row must be object")
            continue
        for field in ("event_id", "event_at_utc", "date", "time_et", "agency", "metric", "period", "source_url"):
            if not row.get(field):
                errors.append(f"event missing {field}: {row.get('event_id')}")
        if row.get("source_type") != "official_release_calendar":
            errors.append(f"event source_type must be official_release_calendar: {row.get('event_id')}")
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Macro Event Calendar",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{as_dict(payload.get('validation')).get('status')}`",
        f"- Next event: `{summary.get('next_event_date')}` `{summary.get('next_event_metric')}`",
        "",
        "## Upcoming High-Impact Events",
        "",
    ]
    for row in payload.get("events") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{row.get('date')}` `{row.get('time_et')} ET` - {row.get('agency')} {row.get('metric')} ({row.get('period')}) "
            f"- `{row.get('status')}` / days_until `{row.get('days_until')}`"
        )
    contract = as_dict(payload.get("operator_followup_contract"))
    lines.extend(
        [
            "",
            "## Operator Contract",
            "",
            f"- Before event: {contract.get('before_event')}",
            f"- After event: {contract.get('after_event')}",
            f"- Owner decision required: {contract.get('owner_decision_required')}",
            "",
            "## Boundary",
            "",
            "Review-only macro calendar. No forecast/probability claim, portfolio/canon mutation, paper/live execution, or owner approval inference.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a review-only macro event calendar.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown outputs.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_calendar()
    if args.write:
        atomic_write_json(Path(args.json_out), payload)
        atomic_write_text(Path(args.md_out), render_markdown(payload))
    if args.validate and payload["validation"]["status"] != "ok":
        print("\n".join(payload["validation"]["errors"]))
        return 1
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
