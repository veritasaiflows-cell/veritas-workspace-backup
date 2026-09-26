#!/usr/bin/env python3
"""WF89: record Main's judgment of a delegated run (append-only).

The credit reader proves what a run cost; only Main knows whether its output
was used. After reviewing a delegated job, record one line:

  python scripts\\wf89_run_outcome.py --run-id <run_id> --outcome accepted \\
      --main-review-minutes 6 --note "patch applied, tests pass"

Outcomes: accepted (used as delivered or with trivial fixes), rework (Main had
to redo a material part), rejected (not used). The latest line per run_id wins,
so a correction is a new line. wf89_fleet_scorecard.py joins this ledger to the
credited-run history to report fresh tokens per accepted task per lane.

Writes only data/state-history/wf89-run-outcomes.jsonl. It grants nothing:
an outcome is evidence of Main's review, not approval or authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import wf89_fleet_scorecard as sc
from wf89_credit_reader import utc_now

SCHEMA = "veritas.wf89_run_outcome.v1"


def build_row(run_id: str, outcome: str, minutes: float | None, note: str | None,
              history: list[dict]) -> dict:
    if outcome not in sc.OUTCOME_VALUES:
        raise ValueError(f"outcome must be one of {', '.join(sc.OUTCOME_VALUES)}")
    if minutes is not None and minutes < 0:
        raise ValueError("--main-review-minutes cannot be negative")
    match = next((r for r in history if r.get("run_id") == run_id), None)
    if match is None:
        raise ValueError(f"run_id {run_id} is not in the credited-run history; run the scorecard with --write first")
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "agent_id": match.get("agent_id"),
        "label": match.get("label"),
        "outcome": outcome,
        "main_review_minutes": minutes,
        "note": note,
        "recorded_at_utc": utc_now(),
        "recorded_by": "main",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record Main's outcome for a credited delegated run")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--outcome", required=True, choices=sc.OUTCOME_VALUES)
    ap.add_argument("--main-review-minutes", type=float, default=None)
    ap.add_argument("--note", default=None)
    ap.add_argument("--history", type=Path, default=sc.HISTORY)
    ap.add_argument("--outcomes", type=Path, default=sc.OUTCOMES)
    args = ap.parse_args(argv)
    history, _ = sc.load_history(args.history)
    try:
        row = build_row(args.run_id, args.outcome, args.main_review_minutes, args.note, history)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.outcomes.parent.mkdir(parents=True, exist_ok=True)
    with args.outcomes.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
