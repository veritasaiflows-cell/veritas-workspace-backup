from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
TRIGGER_PATH = TMP / "trigger-sheet.json"
VALIDATION_PATH = TMP / "dashboard-validation.json"
BAND_PROPOSALS_PATH = TMP / "band-proposals.json"
OUT_PATH = TMP / "deployment-readiness-surface.json"
RUN_SUMMARY_GLOB = "run-summary-*.json"

STATE_ORDER = [
    "DEPLOYABLE NOW",
    "ALMOST DEPLOYABLE",
    "ALMOST / NEAR-EARNINGS CAUTION",
    "POST-EARNINGS REVIEW",
    "BLOCKED",
    "DO NOT TOUCH",
    "WATCH / RESEARCH NEEDED",
    "SYSTEM HOLD",
]

RAW_TO_SURFACE = {
    "DEPLOYABLE": "DEPLOYABLE NOW",
    "ALMOST": "ALMOST DEPLOYABLE",
    "BLOCKED": "BLOCKED",
    "BENCH": "DO NOT TOUCH",
    "BELOW STOP": "DO NOT TOUCH",
    "WATCH": "WATCH / RESEARCH NEEDED",
    "ERROR": "WATCH / RESEARCH NEEDED",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the bounded morning deployment-readiness review surface.")
    parser.add_argument("--window", default="post-close", help="Preferred run-summary window to read.")
    return parser.parse_args()


def load_json(path: Path, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def days_from_today(value: str | None) -> int | None:
    dt = parse_iso_date(value)
    if not dt:
        return None
    today = datetime.now(timezone.utc).date()
    return (today - dt.date()).days


def choose_run_summary(preferred_window: str) -> tuple[dict[str, Any] | None, str | None]:
    preferred = TMP / f"run-summary-{preferred_window}.json"
    if preferred.exists():
        return load_json(preferred, required=False), preferred.name
    candidates = sorted(TMP.glob(RUN_SUMMARY_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None, None
    return load_json(candidates[0], required=False), candidates[0].name


def band_stale_tickers() -> set[str]:
    payload = load_json(BAND_PROPOSALS_PATH, required=False) or {}
    summary = payload.get("summary") or {}
    tickers = set(summary.get("blocking_review_tickers") or [])
    if tickers:
        return tickers
    for proposal in payload.get("proposals", []) or []:
        if not isinstance(proposal, dict):
            continue
        if proposal.get("needs_review") and not proposal.get("skip_reason") and proposal.get("ticker"):
            tickers.add(proposal["ticker"])
    return tickers


def warning_counts(validation: dict[str, Any]) -> tuple[int, int, int]:
    summary = validation.get("summary") or {}
    return int(summary.get("critical", 0)), int(summary.get("warning", 0)), int(summary.get("info", 0))


def fmt_band_position(record: dict[str, Any]) -> str:
    close = record.get("close")
    band = record.get("entry_band") or {}
    low = band.get("low")
    high = band.get("high")
    if close is None or low is None or high is None:
        return "no band"
    if low <= close <= high:
        return "IN BAND"
    if close > high:
        pct = ((close - high) / high) * 100
        return f"{pct:.1f}% above band top"
    pct = ((low - close) / low) * 100
    return f"{pct:.1f}% below band low"


def map_macro_gate(run_summary: dict[str, Any] | None) -> str:
    freshness = (((run_summary or {}).get("validation") or {}).get("exec_freshness") or "").lower()
    return "CLEAN" if freshness == "clean" else "DEGRADED"


def should_hold_system(run_summary: dict[str, Any] | None) -> bool:
    return bool((run_summary or {}).get("stop_line"))


def surface_state_for(
    record: dict[str, Any],
    *,
    fallback_used: bool,
    stop_line: bool,
    stale_band_tickers: set[str],
) -> tuple[str, str | None, str]:
    if stop_line:
        return "SYSTEM HOLD", "RULE 0", "system stop line active"

    ticker = record.get("ticker") or "?"
    workflow_state = str(record.get("workflow_state") or "").upper()
    machine_state = str(record.get("deployment_state") or record.get("action_state") or "WATCH").upper()
    below_stop = bool(record.get("below_stop"))
    earnings_blocked = bool(record.get("earnings_blocked"))
    days_to_earnings = record.get("days_to_earnings")
    post_review_confirmed = bool(record.get("post_earnings_review_confirmed"))
    last_earnings_age_days = days_from_today(record.get("last_earnings_date"))
    earnings_date_ir_confirmed = record.get("earnings_date_ir_confirmed")
    band_stale = ticker in stale_band_tickers

    if below_stop:
        return "DO NOT TOUCH", "RULE 1", "below stop"
    if earnings_blocked and isinstance(days_to_earnings, int) and days_to_earnings > 14:
        return "POST-EARNINGS REVIEW", "RULE 2", "stale earnings block — calendar moved past the print"
    if last_earnings_age_days is not None and 0 <= last_earnings_age_days <= 10 and not post_review_confirmed:
        return "POST-EARNINGS REVIEW", "RULE 3", "recent print with no confirmed post-earnings review"
    if workflow_state == "WATCH":
        return "WATCH / RESEARCH NEEDED", "RULE 4", "workflow_state = WATCH"
    if workflow_state == "REPAIR":
        return "DO NOT TOUCH", "RULE 5", "repair mode remains active"
    if machine_state == "DEPLOYABLE" and (fallback_used or band_stale):
        reason = "trust ceiling — " + ("fallback active" if fallback_used else "band review debt still active")
        return "ALMOST DEPLOYABLE", "RULE 6", reason
    if machine_state == "DEPLOYABLE" and earnings_date_ir_confirmed is False and isinstance(days_to_earnings, int) and 0 < days_to_earnings <= 21:
        return "ALMOST DEPLOYABLE", "RULE 6B", "timing confirmation still unresolved inside the active catalyst window"
    if earnings_blocked and isinstance(days_to_earnings, int) and 0 < days_to_earnings <= 14:
        return "BLOCKED", "RULE 7", f"valid active earnings block ({days_to_earnings}d)"

    return RAW_TO_SURFACE.get(machine_state, "WATCH / RESEARCH NEEDED"), None, "pass-through"


def qualify_surface(surface_state: str, record: dict[str, Any]) -> str:
    days_to_earnings = record.get("days_to_earnings")
    if surface_state == "ALMOST DEPLOYABLE" and isinstance(days_to_earnings, int) and 1 <= days_to_earnings <= 7:
        return "ALMOST / NEAR-EARNINGS CAUTION"
    return surface_state


def state_sort_key(state: str) -> int:
    try:
        return STATE_ORDER.index(state)
    except ValueError:
        return len(STATE_ORDER)


def record_sort_key(state: str, record: dict[str, Any]) -> tuple[Any, ...]:
    if state == "POST-EARNINGS REVIEW":
        return (0 if record.get("in_entry_band") else 1, record.get("ticker") or "")
    return (record.get("ticker") or "",)


def main() -> int:
    args = parse_args()
    trigger = load_json(TRIGGER_PATH, required=True) or {}
    validation = load_json(VALIDATION_PATH, required=False) or {"summary": {"critical": 0, "warning": 0, "info": 0}, "warnings": []}
    run_summary, run_summary_name = choose_run_summary(args.window)
    stale_band_tickers = band_stale_tickers()

    stop_line = should_hold_system(run_summary)
    fallback_used = bool(((run_summary or {}).get("fallback_state") or {}).get("used"))
    macro_gate = map_macro_gate(run_summary)
    critical_count, warning_count, info_count = warning_counts(validation)
    warning_codes = [item.get("code") for item in validation.get("warnings", []) if item.get("code")]
    stale_blocks = [
        rec.get("ticker")
        for rec in trigger.get("records", []) or []
        if rec.get("earnings_blocked") and isinstance(rec.get("days_to_earnings"), int) and rec.get("days_to_earnings") > 14
    ]

    run_generated = parse_iso_ts((run_summary or {}).get("generated_at_utc"))
    trigger_generated = parse_iso_ts(trigger.get("generated_at_utc"))
    timestamp_gap_hours = None
    timestamp_gap_warning = None
    if run_generated and trigger_generated:
        timestamp_gap_hours = round(abs((trigger_generated - run_generated).total_seconds()) / 3600, 2)
        if timestamp_gap_hours > 2:
            timestamp_gap_warning = (
                f"run-summary ({run_generated.isoformat()}) predates the trigger surface ({trigger_generated.isoformat()}) by {timestamp_gap_hours}h"
            )

    grouped: dict[str, list[dict[str, Any]]] = {state: [] for state in STATE_ORDER}
    for record in trigger.get("records", []) or []:
        base_state, override_rule, override_reason = surface_state_for(
            record,
            fallback_used=fallback_used,
            stop_line=stop_line,
            stale_band_tickers=stale_band_tickers,
        )
        surface_state = qualify_surface(base_state, record)
        out = {
            "ticker": record.get("ticker"),
            "surface_state": surface_state,
            "base_surface_state": base_state,
            "workflow_state": record.get("workflow_state"),
            "machine_state": record.get("deployment_state") or record.get("action_state"),
            "close": record.get("close"),
            "band_position": fmt_band_position(record),
            "days_to_earnings": record.get("days_to_earnings"),
            "near_earnings_caution": surface_state == "ALMOST / NEAR-EARNINGS CAUTION",
            "band_stale": (record.get("ticker") in stale_band_tickers),
            "earnings_date_confirmed": "YES" if record.get("earnings_date_ir_confirmed") is True else "UNCONFIRMED",
            "earnings_date_ir_confirmed": record.get("earnings_date_ir_confirmed"),
            "earnings_date_ir_confirmed_date": record.get("earnings_date_ir_confirmed_date"),
            "last_earnings_date": record.get("last_earnings_date"),
            "post_earnings_review_date": record.get("post_earnings_review_date"),
            "post_earnings_review_confirmed": record.get("post_earnings_review_confirmed"),
            "macro_gate": macro_gate,
            "override_rule": override_rule,
            "override_reason": override_reason,
            "why": record.get("why"),
            "trigger": record.get("technical_trigger"),
            "action_state": record.get("action_state"),
            "catalyst_blocker": record.get("catalyst_blocker"),
            "next_earnings_date": record.get("next_earnings_date"),
        }
        grouped.setdefault(surface_state, []).append(out)

    for state, rows in grouped.items():
        rows.sort(key=lambda item: record_sort_key(state, item))

    summary = {state: len(grouped.get(state, [])) for state in STATE_ORDER}
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window": args.window,
        "source_run_summary": run_summary_name,
        "system": {
            "stop_line": stop_line,
            "deployable_now_suspended": fallback_used,
            "canonical_note_mutation_allowed": (((run_summary or {}).get("downstream") or {}).get("canonical_note_mutation_allowed")),
            "presentation_allowed": (((run_summary or {}).get("downstream") or {}).get("presentation_allowed")),
            "macro_gate": macro_gate,
            "warning_counts": {"critical": critical_count, "warning": warning_count, "info": info_count},
            "warning_codes": warning_codes,
            "stale_earnings_blocks": stale_blocks,
            "timestamp_gap_hours": timestamp_gap_hours,
            "timestamp_gap_warning": timestamp_gap_warning,
            "run_summary_generated_at_utc": (run_summary or {}).get("generated_at_utc"),
            "trigger_generated_at_utc": trigger.get("generated_at_utc"),
        },
        "summary": summary,
        "groups": grouped,
    }

    atomic_write_json(OUT_PATH, output)

    print(f"deployment_readiness_surface: wrote {OUT_PATH}")
    print(f"  source run summary: {run_summary_name or 'none'}")
    print(f"  macro gate: {macro_gate}")
    print(f"  warnings: {critical_count} critical / {warning_count} warning / {info_count} info")
    for state in STATE_ORDER:
        count = summary.get(state, 0)
        if count:
            print(f"  {state}: {count}")
    if timestamp_gap_warning:
        print(f"  WARNING: {timestamp_gap_warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
