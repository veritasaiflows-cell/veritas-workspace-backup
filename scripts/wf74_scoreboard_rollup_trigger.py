#!/usr/bin/env python3
"""Read-only prefilter for the nightly WF74 scoreboard rollup gate.

Reads the WF74 improvement opportunity queue and decision docket after the
21:40 OTEL Local Digest regenerates them, selects genuinely actionable
high-priority items, and prints one compact JSON summary for the gateway
trigger.

This script never wakes Main, never writes files, and never mutates state.
Dedupe/dispatch decisions belong to the gateway trigger state; actions belong
to the woken Main turn.  Stale scoreboards (regen failure) are reported as
stale so the trigger can watchdog the nightly regen instead of trusting it.

Signature stability: docket row ids regenerate on every rebuild
(patch-plan-<hash>), so the dedupe signature is built from title, priority,
and gate -- the stable identity of an item, not its per-run id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE_REL = "tmp/wf74-improvement-opportunity-queue.json"
DOCKET_REL = "tmp/wf74-decision-docket.json"

SCHEMA = "veritas.wf74_scoreboard_rollup_trigger.v1"
HIGH_PRIORITY_MIN = 70
EXCLUDED_GATES = {"standing_guardrail_no_execution"}
MAX_AGE_HOURS = 26.0


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def age_hours(stamp: Any, now: datetime) -> float | None:
    if not isinstance(stamp, str) or not stamp.strip():
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
    return round((now - moment).total_seconds() / 3600.0, 2)


def select_actionable(queue: dict[str, Any], docket: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge docket fix_now rows and high-priority queue opportunities.

    Title collisions between the two sources are expected (the docket derives
    from the same signals); the docket row wins because it carries proof
    commands.  Dedupe is by title, not id, because ids are not stable across
    regenerations.
    """
    by_title: dict[str, dict[str, Any]] = {}

    for row in docket.get("rows") or []:
        if not isinstance(row, dict) or row.get("action_state") != "fix_now":
            continue
        item = {
            "kind": "docket_fix_now",
            "id": str(row.get("docket_id") or row.get("source_id") or ""),
            "title": str(row.get("title") or "").strip(),
            "priority": int(row.get("priority") or 0),
            "gate": str(row.get("route") or row.get("proposal_gate") or "main_review_required"),
            "proof_commands": [str(c) for c in (row.get("proof_commands") or []) if str(c).strip()],
        }
        if item["title"]:
            by_title[item["title"].lower()] = item

    for opp in queue.get("opportunities") or []:
        if not isinstance(opp, dict):
            continue
        gate = str(opp.get("proposal_gate") or "")
        if gate in EXCLUDED_GATES:
            continue
        if int(opp.get("priority") or 0) < HIGH_PRIORITY_MIN:
            continue
        item = {
            "kind": "queue_opportunity",
            "id": str(opp.get("opportunity_id") or ""),
            "title": str(opp.get("title") or "").strip(),
            "priority": int(opp.get("priority") or 0),
            "gate": gate or "main_review_required",
            "validation_command": str(opp.get("validation_command") or "").strip(),
        }
        if not item["title"]:
            continue
        key = item["title"].lower()
        if key not in by_title:  # docket row already won this title
            by_title[key] = item

    return sorted(by_title.values(), key=lambda entry: (-entry["priority"], entry["title"]))


def signature(items: list[dict[str, Any]]) -> str:
    material = "|".join(
        f"{i['title'].lower()}:{i['priority']}:{i['gate']}" for i in items
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def summarize(root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    queue = load(root / QUEUE_REL)
    docket = load(root / DOCKET_REL)

    if not queue or not docket:
        return {
            "schema": SCHEMA,
            "ok": False,
            "error": "queue_or_docket_missing_or_unreadable",
            "queue_present": bool(queue),
            "docket_present": bool(docket),
        }

    ages = [
        value
        for value in (
            age_hours(queue.get("generated_at_utc"), now),
            age_hours(docket.get("generated_at_utc"), now),
        )
        if value is not None
    ]
    if not ages:
        return {"schema": SCHEMA, "ok": False, "error": "generated_at_utc_missing"}

    newest_age = max(ages)
    stale = newest_age > MAX_AGE_HOURS
    items = select_actionable(queue, docket)
    return {
        "schema": SCHEMA,
        "ok": True,
        "stale": stale,
        "age_hours": newest_age,
        "actionable_count": len(items),
        "actionable": items,
        "signature": signature(items),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only WF74 scoreboard rollup prefilter; prints one JSON summary.")
    parser.add_argument("--root", default=str(ROOT), help="workspace root (tests inject an isolated root)")
    args = parser.parse_args(argv)
    print(json.dumps(summarize(Path(args.root).resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())