"""post_earnings_note_targets.py

Read-only selective note-update workflow for post-earnings maintenance.

This script reads tmp/post-earnings-prep.json and translates each earnings packet
into candidate note updates and update intents. It does not edit notes. Its job
is to tell the agent which files are likely affected and why, so note updates can
stay selective instead of broad and noisy.

Usage:
    python scripts/post_earnings_note_targets.py

Inputs:
    tmp/post-earnings-prep.json

Outputs:
    tmp/post-earnings-note-targets.json
    terminal summary
"""

from __future__ import annotations

from board_state_contract import legacy_state
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
PREP_PATH = TMP / "post-earnings-prep.json"
OUT_PATH = TMP / "post-earnings-note-targets.json"
STALE_HOURS = 24

TARGET_RULES: dict[str, dict[str, Any]] = {
    "05. Intelligence/Event Calendar.md": {
        "when": "always for material tracked earnings",
        "intent": "mark reported status, preserve concise what happened / what it means / what we do now line, and clear or roll the catalyst forward",
    },
    "05. Intelligence/Weekly Intelligence Brief.md": {
        "when": "when the report changes company thesis, sector read-through, or near-term positioning",
        "intent": "update earnings radar and recommended-actions sections with decision-grade interpretation",
    },
    "03. Portfolio/Execution Board.md": {
        "when": "when price structure, blocker status, invalidation logic, action state, or trigger logic changed materially after the report",
        "intent": "rebuild entry zone, stop, and stance only when the earnings reaction materially changed the setup; promote, demote, unblock, or keep blocked with explicit why",
    },
    "03. Portfolio/Portfolio Snapshot.md": {
        "when": "when the report changes whether a draft holding remains justified, suspended, or under review",
        "intent": "update posture, status line, and review action rather than churning the whole snapshot",
    },
    "04. Research/Coverage and Watchlist.md": {
        "when": "when conviction, ranking, status label, durable thesis language, key risk, or act-when conditions changed",
        "intent": "promote, demote, reframe watch status, or update permanent research framing; do not churn short-term noise",
    },
}

RETIRED_PORTFOLIO_TARGET_PREFIX = "03. Portfolio/"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"ERROR: required file not found: {path}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def build_candidate_updates(packet: dict[str, Any]) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    ticker = packet.get("ticker")
    priority = packet.get("priority")
    stage = packet.get("stage")
    trigger_state = legacy_state(packet.get("trigger_context", {}), "action_state")
    deployment_state = legacy_state(packet.get("deployment_context", {}), "action_state")

    seen_targets: set[str] = set()
    for target in packet.get("note_targets", []):
        # Earnings review may inform research, but it must not route a result
        # into retired portfolio-state surfaces or imply a portfolio action.
        if str(target).startswith(RETIRED_PORTFOLIO_TARGET_PREFIX):
            continue
        if target in seen_targets:
            continue
        seen_targets.add(target)
        rule = TARGET_RULES.get(target, {})
        urgency = "normal"
        if priority == "critical":
            urgency = "high"
        if stage in ("reports today", "imminent", "just reported or elapsed") and priority in ("critical", "high"):
            urgency = "high"
        if target == "04. Research/Coverage and Watchlist.md":
            urgency = "low"
        if target == "03. Portfolio/Execution Board.md" and trigger_state in ("DO NOT TOUCH", "BLOCKED") and deployment_state in ("BELOW STOP", "BLOCKED", "BENCH"):
            rationale = f"{ticker}: only update if the earnings reaction materially changes the current blocked or broken setup"
        elif target == "03. Portfolio/Portfolio Snapshot.md":
            rationale = f"{ticker}: update only if the report changes whether the draft slot remains justified, suspended, or under review"
        elif target == "04. Research/Coverage and Watchlist.md":
            rationale = f"{ticker}: durable thesis file, so update only on true thesis, key-risk, or act-when change"
        else:
            rationale = f"{ticker}: candidate target because the post-earnings interpretation may change status, read-through, or decision posture"

        updates.append({
            "path": target,
            "urgency": urgency,
            "when_rule": rule.get("when"),
            "intent": rule.get("intent"),
            "rationale": rationale,
        })
    return updates


def build_reconciliation_tasks(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Surface post-print work without mutating notes, alerts, or canon."""
    if packet.get("phase") != "post_earnings":
        return []
    reconciliation = packet.get("reconciliation") if isinstance(packet.get("reconciliation"), dict) else {}
    task_specs = (
        ("scorecard", "scorecard_required", "Create or update a source-backed scorecard; preserve unresolved evidence as unresolved."),
        ("thesis", "thesis_reassessment_required", "Reassess thesis, base/bull/bear, risks, and confidence from official evidence."),
        ("catalyst", "catalyst_reconciliation_required", "Resolve or roll the catalyst forward only after post-print interpretation is complete."),
        ("alert", "alert_reconciliation_required", "Reassess the review-only alert state against the current alert controller; never mutate alert canon automatically."),
    )
    return [
        {
            "ticker": packet.get("ticker"),
            "task": name,
            "required": True,
            "intent": intent,
            "review_only": True,
            "automatic_mutation_allowed": False,
        }
        for name, requirement, intent in task_specs
        if reconciliation.get(requirement) is True
    ]


def main() -> None:
    prep = load_json(PREP_PATH)
    packets = prep.get("packets", []) or []
    earnings_lifecycle = prep.get("earnings_lifecycle") if isinstance(prep.get("earnings_lifecycle"), dict) else {}

    workflows: list[dict[str, Any]] = []
    impacted_notes: dict[str, list[str]] = {}
    reconciliation_queue: list[dict[str, Any]] = []

    for packet in packets:
        ticker = packet.get("ticker")
        candidate_updates = build_candidate_updates(packet)
        reconciliation_tasks = build_reconciliation_tasks(packet)
        workflows.append({
            "ticker": ticker,
            "priority": packet.get("priority"),
            "stage": packet.get("stage"),
            "next_earnings_date": packet.get("next_earnings_date"),
            "action_state": legacy_state(packet.get("trigger_context", {}), "action_state"),
            "candidate_updates": candidate_updates,
            "reconciliation_tasks": reconciliation_tasks,
        })
        reconciliation_queue.extend(reconciliation_tasks)
        for update in candidate_updates:
            impacted_notes.setdefault(update["path"], []).append(ticker)

    prep_age = None
    try:
        prep_age = round((datetime.now(timezone.utc) - datetime.fromisoformat(prep.get("generated_at_utc"))).total_seconds() / 3600, 2) if prep.get("generated_at_utc") else None
    except Exception:
        prep_age = None
    prep_stale = prep_age is not None and prep_age > prep.get("stale_after_hours", STALE_HOURS)
    status = "ok" if prep.get("status") == "ok" and not prep_stale else "partial"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stale_after_hours": STALE_HOURS,
        "expected_update_window": "Run after post_earnings_prep.py and before any post-earnings note edits.",
        "last_trading_day": prep.get("last_trading_day"),
        "source_last_trading_day": prep.get("source_last_trading_day"),
        "source": {
            "prep_file": str(PREP_PATH),
            "generated_at_utc": prep.get("generated_at_utc"),
            "age_hours": prep_age,
            "is_stale": prep_stale,
            "status": prep.get("status"),
        },
        "warnings": prep.get("warnings", []),
        "earnings_lifecycle": earnings_lifecycle,
        "impacted_notes": impacted_notes,
        "workflows": workflows,
        "reconciliation_queue": reconciliation_queue,
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "alert_canon_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    sep = "=" * 88
    print("\n" + sep)
    print("  POST-EARNINGS NOTE TARGETS  --  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(sep)
    print("\n  {:<8}  {:<10}  {:<18}  {:<24}".format("Ticker", "Priority", "Stage", "Action state"))
    print("  " + "-" * 84)
    for workflow in workflows:
        print("  {:<8}  {:<10}  {:<18}  {:<24}".format(
            workflow.get("ticker") or "--",
            workflow.get("priority") or "--",
            workflow.get("stage") or "--",
            legacy_state(workflow, "action_state") or "--",
        ))

    print("\n  IMPACTED NOTES")
    print("  " + "-" * 40)
    for path, tickers in sorted(impacted_notes.items()):
        print("  " + path)
        print("    -> " + ", ".join(sorted(tickers)))

    warnings = payload.get("warnings") or []
    if warnings:
        print("\n  WARNINGS")
        print("  " + "-" * 40)
        for warning in warnings:
            print("  - " + warning)

    print("\nOutput written to " + str(OUT_PATH))
    print("")


if __name__ == "__main__":
    main()
