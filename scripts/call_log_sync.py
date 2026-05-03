"""call_log_sync.py

Compare the current deployment board (trigger-sheet.json) against the open
calls recorded in 04. Research/Call Log.md, and print a delta report showing
which calls have changed state.

This script is READ-ONLY with respect to the Call Log markdown. It does NOT
auto-update the file. Its output is a decision-support report: Veritas or
Claude reviews the delta and decides which entries warrant an update, then
edits the markdown with proper context and notes.

Outputs:
  Terminal delta report
  tmp/call-log-sync.json  (machine-readable version of the delta for automation)

Usage:
    python scripts/call_log_sync.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from typing import Any

WORKSPACE     = Path(__file__).resolve().parents[1]
TRIGGER_SHEET = WORKSPACE / "tmp" / "trigger-sheet.json"
CALL_LOG_MD   = WORKSPACE / "04. Research" / "Call Log.md"
OUT_JSON      = WORKSPACE / "tmp" / "call-log-sync.json"

# ---------------------------------------------------------------------------
# Map trigger-sheet action_state to simplified call status
# ---------------------------------------------------------------------------
ACTION_STATE_MAP = {
    "DEPLOYABLE":         "deployable",
    "ALMOST DEPLOYABLE":  "almost_deployable",
    "ALMOST":             "almost_deployable",
    "BLOCKED":            "blocked",
    "DO NOT TOUCH":       "do_not_touch",
    "REPAIR":             "do_not_touch",
    "WATCH":              "watch",
    "BENCH":              "bench",
}


def load_json(path: Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def describe_transition(delta: dict[str, Any]) -> str:
    previous = delta.get("intended_state") or delta.get("log_status") or "unknown"
    current = delta.get("current_state") or "unknown"
    return f"{previous} → {current}"


# ---------------------------------------------------------------------------
# Parse open calls from Call Log.md
# ---------------------------------------------------------------------------
def parse_call_log(content: str) -> list[dict[str, str]]:
    """Extract rows from the Active calls table in Call Log.md.

    Returns list of dicts: {num, date_opened, ticker, call_summary, status, notes}
    """
    calls: list[dict[str, str]] = []

    # Find the active calls table — rows that start with | followed by a number
    # Format: | # | Date Opened | Ticker | Call | Entry Band | Stop | Timeframe | Conviction | Status | Outcome | Date Closed | Notes |
    table_pattern = re.compile(
        r"^\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([A-Z0-9.]+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]*)\|",
        re.MULTILINE,
    )
    for m in table_pattern.finditer(content):
        num         = m.group(1).strip()
        date_opened = m.group(2).strip()
        ticker      = m.group(3).strip()
        call_text   = m.group(4).strip()
        entry_band  = m.group(5).strip()
        status      = m.group(9).strip()
        notes       = m.group(12).strip()

        calls.append({
            "num":         num,
            "date_opened": date_opened,
            "ticker":      ticker,
            "call_text":   call_text[:120],  # truncate for readability
            "entry_band":  entry_band,
            "status":      status,
            "notes":       notes[:120],
        })

    return calls


# ---------------------------------------------------------------------------
# Classify change severity
# ---------------------------------------------------------------------------
def classify_change(log_status: str, current_state: str) -> str:
    """Return change severity: 'no_change', 'minor', 'material', 'critical'"""
    ls = log_status.lower()
    cs = current_state.lower()

    if ls == cs:
        return "no_change"

    # Critical: thesis-impairment-level changes
    critical_pairs = {
        ("almost_deployable", "do_not_touch"),
        ("almost_deployable", "watch"),
        ("deployable",        "do_not_touch"),
        ("deployable",        "watch"),
        ("deployable",        "bench"),
        ("blocked",           "do_not_touch"),
    }
    if (ls, cs) in critical_pairs or (cs, ls) in critical_pairs:
        return "critical"

    # Material: deployment-relevant changes
    material_pairs = {
        ("almost_deployable", "deployable"),
        ("blocked",           "almost_deployable"),
        ("blocked",           "deployable"),
        ("watch",             "almost_deployable"),
        ("bench",             "almost_deployable"),
        ("do_not_touch",      "watch"),
        ("do_not_touch",      "bench"),
    }
    if (ls, cs) in material_pairs or (cs, ls) in material_pairs:
        return "material"

    return "minor"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    print("Loading artifacts...")
    trigger = load_json(TRIGGER_SHEET) or {}

    if not CALL_LOG_MD.exists():
        print(f"  ERROR: Call Log not found at {CALL_LOG_MD}")
        return

    log_content = CALL_LOG_MD.read_text(encoding="utf-8")
    trigger_records = {r["ticker"]: r for r in trigger.get("records", [])}
    last_trading_day = trigger.get("last_trading_day", "unknown")

    # Parse open calls
    log_calls = parse_call_log(log_content)
    print(f"  Call Log: {len(log_calls)} entries parsed")
    print(f"  Trigger sheet: {len(trigger_records)} records (as of {last_trading_day})")

    # -----------------------------------------------------------------------
    # Build delta
    # -----------------------------------------------------------------------
    deltas: list[dict[str, Any]] = []

    # For each logged call, check against current trigger sheet
    seen_tickers: set[str] = set()
    for call in log_calls:
        ticker = call["ticker"]
        seen_tickers.add(ticker)

        log_status_raw = call["status"].lower()
        # Normalize log status to simplified form
        if "incomplete" in log_status_raw:
            log_simplified = "open"
        elif "deployable" in log_status_raw and "almost" not in log_status_raw:
            log_simplified = "deployable"
        elif "almost" in log_status_raw:
            log_simplified = "almost_deployable"
        elif "blocked" in log_status_raw:
            log_simplified = "blocked"
        elif "do not touch" in log_status_raw or "repair" in log_status_raw:
            log_simplified = "do_not_touch"
        elif "watch" in log_status_raw:
            log_simplified = "watch"
        elif "bench" in log_status_raw:
            log_simplified = "bench"
        else:
            log_simplified = log_status_raw

        tr = trigger_records.get(ticker)
        if tr is None:
            # Name no longer in trigger sheet
            deltas.append({
                "call_num":      call["num"],
                "ticker":        ticker,
                "log_status":    log_status_raw,
                "current_state": "not_in_trigger_sheet",
                "change":        "material",
                "action":        f"#{call['num']} {ticker}: removed from trigger sheet — confirm via portfolio-config",
                "current_close":  None,
                "current_why":    None,
                "days_to_earnings": None,
            })
            continue

        current_action = (tr.get("action_state") or "").upper()
        current_simplified = ACTION_STATE_MAP.get(current_action, current_action.lower())

        # Skip if log status is "open/incomplete" — those are the live calls
        # We compare the ORIGINAL call intent (encoded in call_text) vs current state
        call_text_lower = call["call_text"].lower()
        if "almost deployable" in call_text_lower or "pullback only" in call_text_lower:
            intended = "almost_deployable"
        elif "blocked" in call_text_lower:
            intended = "blocked"
        elif "do not touch" in call_text_lower:
            intended = "do_not_touch"
        elif "watch" in call_text_lower:
            intended = "watch"
        elif "bench" in call_text_lower:
            intended = "bench"
        elif "deployable" in call_text_lower:
            intended = "deployable"
        else:
            intended = "open"

        change = classify_change(intended, current_simplified)

        deltas.append({
            "call_num":         call["num"],
            "ticker":           ticker,
            "log_status":       log_status_raw,
            "intended_state":   intended,
            "current_state":    current_simplified,
            "current_action":   current_action,
            "change":           change,
            "current_close":    tr.get("close"),
            "current_why":      tr.get("why", ""),
            "days_to_earnings": tr.get("days_to_earnings"),
            "catalyst_blocker": tr.get("catalyst_blocker", ""),
            "in_band":          tr.get("in_entry_band", False),
        })

    # Check for names in trigger sheet not in the call log
    new_names = [tk for tk in trigger_records if tk not in seen_tickers]

    # -----------------------------------------------------------------------
    # Write JSON output
    # -----------------------------------------------------------------------
    no_change  = [d for d in deltas if d["change"] == "no_change"]
    minor      = [d for d in deltas if d["change"] == "minor"]
    material   = [d for d in deltas if d["change"] == "material"]
    critical   = [d for d in deltas if d["change"] == "critical"]

    output: dict[str, Any] = {
        "generated_at_utc":  utc_now(),
        "last_trading_day":  last_trading_day,
        "calls_parsed":      len(log_calls),
        "trigger_records":   len(trigger_records),
        "summary": {
            "critical": len(critical),
            "material": len(material),
            "minor":    len(minor),
            "no_change": len(no_change),
            "new_names_not_in_log": new_names,
        },
        "deltas": deltas,
    }
    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # -----------------------------------------------------------------------
    # Terminal report
    # -----------------------------------------------------------------------
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  CALL LOG SYNC  --  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(sep)
    print(f"\n  Trigger data as of: {last_trading_day}")
    print(f"  Calls in log: {len(log_calls)}  |  Trigger records: {len(trigger_records)}")
    print(f"\n  Changes: {len(critical)} critical  {len(material)} material  {len(minor)} minor  {len(no_change)} unchanged")

    if critical:
        print(f"\n  ⚠  CRITICAL — Update Call Log now:")
        for d in critical:
            dte = f"  earnings in {d['days_to_earnings']}d" if d.get("days_to_earnings") is not None and d["days_to_earnings"] >= 0 else ""
            print(f"     #{d['call_num']} {d['ticker']}: {describe_transition(d)}{dte}")
            if d.get("current_why"):
                print(f"          Reason: {d['current_why']}")

    if material:
        print(f"\n  ► MATERIAL — Review and update Call Log:")
        for d in material:
            dte = f"  earnings in {d['days_to_earnings']}d" if d.get("days_to_earnings") is not None and d["days_to_earnings"] >= 0 else ""
            in_band_note = "  IN BAND" if d.get("in_band") else ""
            print(f"     #{d['call_num']} {d['ticker']}: {describe_transition(d)}{dte}{in_band_note}")
            if d.get("current_why"):
                print(f"          Reason: {d['current_why']}")

    if minor:
        print(f"\n  ○ Minor changes (log awareness, not urgent):")
        for d in minor:
            print(f"     #{d['call_num']} {d['ticker']}: {describe_transition(d)}")

    if new_names:
        print(f"\n  + Names in trigger sheet not yet in call log:")
        for tk in new_names:
            tr = trigger_records[tk]
            print(f"     {tk} — {tr.get('action_state', 'unknown')} | {tr.get('why', '')[:60]}")
        print("    Consider opening new call log entries for these names.")

    if not critical and not material and not minor:
        print("\n  All calls consistent with current trigger sheet. No updates required.")

    print(f"\n  Saved → tmp/call-log-sync.json")
    print(sep + "\n")


if __name__ == "__main__":
    main()
