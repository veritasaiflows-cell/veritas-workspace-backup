#!/usr/bin/env python3
"""WF89 daily fleet scorecard (model-free, read-only against OpenClaw stores).

OpenClaw keeps task_runs rows for 7 days, so per-lane cost and speed evidence
disappears unless it is captured. Each run:

1. Reads the live window through wf89_credit_reader (attribution contract v0.3).
2. Appends every CREDITABLE run not already captured to the durable,
   append-only history data/state-history/wf89-credited-runs.jsonl, with usage
   and timing (started/ended from task_runs).
3. Writes tmp/wf89-fleet-scorecard.json: per-lane medians over the history
   (fresh tokens = input + output, total tokens, duration), the live window's
   delegation mix, and the command-line runs that cannot be credited because
   they have no dispatch record.

Benchmark runs are separated by label heuristic (BENCHMARK_LABEL); they are
model comparisons, not delegated work. Credited is not accepted: acceptance is
Main's judgment and is not in the stores. Opens every OpenClaw store read-only
and writes only the history file and the scorecard. No config, cron, agent, or
authority change.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

import wf89_credit_reader as reader

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "state-history" / "wf89-credited-runs.jsonl"
OUT = ROOT / "tmp" / "wf89-fleet-scorecard.json"
SCHEMA = "veritas.wf89_fleet_scorecard.v1"
HISTORY_SCHEMA = "veritas.wf89_credited_run.v1"
# Label families of model-comparison runs seen 2026-09-12..24: "Sol T3 case",
# "Arena A T2 rep1", "DS chain B T4a", "Arena D mission-2", "GLM multi-turn TTL
# pilot", and harness case ids containing "::" ("glm::code-debug-offbyone").
# A bare "arena" is not a marker: builder/QA jobs that built the arena harness
# ("Harden arena transport and grading") are real work.
BENCHMARK_LABEL = re.compile(
    r"\bT\d+\b|\bcase\b|\bchain [a-z]\b|\br\d+\b|\bmission-\d|::|\bmulti-turn\b|\bbench\b",
    re.IGNORECASE,
)
MIN_RUNS_FOR_MEDIAN = 3


def utc_iso(ms: Any) -> str | None:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_benchmark(label: str | None) -> bool:
    return bool(label) and bool(BENCHMARK_LABEL.search(label))


def task_timing(global_db: Path, task_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not task_ids:
        return {}
    con = reader.open_ro(global_db)
    try:
        timing: dict[str, dict[str, Any]] = {}
        for start in range(0, len(task_ids), 500):
            chunk = task_ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            for row in con.execute(
                f"SELECT task_id, started_at, ended_at, tool_use_count, terminal_outcome FROM task_runs WHERE task_id IN ({marks})",
                chunk,
            ):
                started, ended = row["started_at"], row["ended_at"]
                timing[row["task_id"]] = {
                    "started_at_utc": utc_iso(started),
                    "ended_at_utc": utc_iso(ended),
                    "duration_seconds": round((ended - started) / 1000, 1) if started and ended and ended >= started else None,
                    "tool_use_count": row["tool_use_count"],
                    "terminal_outcome": row["terminal_outcome"],
                }
        return timing
    finally:
        con.close()


def history_row(rec: dict[str, Any], timing: dict[str, Any], captured_at: str) -> dict[str, Any]:
    usage = rec.get("usage") or {}
    fresh = None
    if isinstance(usage.get("input"), int) and isinstance(usage.get("output"), int):
        fresh = usage["input"] + usage["output"]
    return {
        "schema": HISTORY_SCHEMA,
        "run_id": rec.get("run_id"),
        "task_id": rec.get("task_id"),
        "agent_id": rec.get("agent_id"),
        "label": rec.get("label"),
        "benchmark": is_benchmark(rec.get("label")),
        "dispatch_path": rec.get("dispatch_path") or "sessions_spawn",
        "status": rec.get("status"),
        "usage": {
            "input": usage.get("input"),
            "output": usage.get("output"),
            "cache_read": usage.get("cacheRead"),
            "total": usage.get("total"),
            "fresh": fresh,
        },
        **timing,
        "captured_at_utc": captured_at,
    }


def load_history(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad = 0
    if not path.exists():
        return rows, bad
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(row, dict) and row.get("run_id"):
                rows.append(row)
            else:
                bad += 1
    return rows, bad


def lane_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def med(values: list[float]) -> float | None:
        return round(median(values), 1) if len(values) >= MIN_RUNS_FOR_MEDIAN else None

    fresh = [r["usage"]["fresh"] for r in rows if isinstance(r.get("usage", {}).get("fresh"), int)]
    total = [r["usage"]["total"] for r in rows if isinstance(r.get("usage", {}).get("total"), int)]
    duration = [r["duration_seconds"] for r in rows if isinstance(r.get("duration_seconds"), (int, float))]
    return {
        "credited_runs": len(rows),
        "median_fresh_tokens": med(fresh),
        "median_total_tokens": med(total),
        "median_duration_seconds": med(duration),
        "max_duration_seconds": max(duration) if duration else None,
        "median_withheld_below_runs": MIN_RUNS_FOR_MEDIAN,
    }


def build(global_db: Path, agent_root: Path, dispatch_dir: Path, history_path: Path, *, write: bool) -> dict[str, Any]:
    captured_at = reader.utc_now()
    window = reader.read_task(global_db=global_db, agent_root=agent_root)
    cli = reader.read_cli(dispatch_dir, global_db=global_db, agent_root=agent_root)
    live = list(window["records"]) + list(cli.get("records") or [])
    creditable = [r for r in live if r.get("state") == "CREDITABLE" and r.get("run_id")]

    history, bad_rows = load_history(history_path)
    seen = {r["run_id"] for r in history}
    new = [r for r in creditable if r["run_id"] not in seen]
    timing = task_timing(global_db, [r["task_id"] for r in new if r.get("task_id")])
    new_rows = [history_row(r, timing.get(r.get("task_id"), {}), captured_at) for r in new]
    if write and new_rows:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as handle:
            for row in new_rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    all_rows = history + new_rows

    now = datetime.now(timezone.utc)
    recent_cutoff = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    lanes: dict[str, Any] = {}
    for agent in sorted({r.get("agent_id") or "unknown" for r in all_rows}):
        mine = [r for r in all_rows if (r.get("agent_id") or "unknown") == agent]
        work = [r for r in mine if not r.get("benchmark")]
        lanes[agent] = {
            "work": lane_stats(work),
            "work_last_30d": lane_stats([r for r in work if (r.get("ended_at_utc") or r.get("captured_at_utc") or "") >= recent_cutoff]),
            "benchmark_runs": sum(1 for r in mine if r.get("benchmark")),
        }

    window_by_agent: dict[str, dict[str, int]] = {}
    for rec in live:
        agent = rec.get("agent_id") or "unknown"
        kind = "benchmark" if is_benchmark(rec.get("label")) else "work"
        slot = window_by_agent.setdefault(agent, {"work": 0, "benchmark": 0})
        slot[kind] += 1
    window_work = sum(v["work"] for v in window_by_agent.values())
    main_work = window_by_agent.get("main", {}).get("work", 0)

    # Observations are standing measurement facts for the WF89 plan, not daily
    # review items; only a corrupt history (evidence loss) is an error.
    errors: list[str] = []
    observations: list[str] = []
    if bad_rows:
        errors.append(f"history_unparseable_rows:{bad_rows}")
    uncreditable_cli = cli.get("cli_rows_without_dispatch_record_by_agent") or {}
    if uncreditable_cli:
        observations.append("cli_runs_without_dispatch_record_are_uncreditable")
    if not any(v["work"]["median_fresh_tokens"] is not None for v in lanes.values()):
        observations.append("no_lane_has_enough_credited_work_runs_for_medians")

    return {
        "schema": SCHEMA,
        "generated_at_utc": captured_at,
        "status": "error" if errors else "ok",
        "observations": observations,
        "history": {
            "path": history_path.as_posix(),
            "rows_before": len(history),
            "rows_appended": len(new_rows) if write else 0,
            "rows_pending_append": 0 if write else len(new_rows),
            "rows_total": len(all_rows) if write else len(history),
        },
        "window": {
            "note": "task_runs rows expire 7 days after they end; the window is not history",
            "subagent_state_counts": window["counts"],
            "cli_state_counts": cli.get("counts", {}),
            "delegated_runs_by_agent": window_by_agent,
            "main_share_of_work_runs": round(main_work / window_work, 3) if window_work else None,
            "cli_rows_without_dispatch_record_by_agent": uncreditable_cli,
        },
        "lanes": lanes,
        "limits": [
            "Credited means usage was proven for a run, not that Main accepted its output.",
            "Benchmark separation is a label heuristic; unlabeled runs count as work.",
            "Lanes do different tasks; medians are not like-for-like comparisons.",
            "cost.total is unpriced (0) on ollama-cloud and meta; compare on tokens.",
        ],
        "authority_boundary": {
            "read_only_openclaw_stores": True,
            "writes": ["append-only credited-run history", "scorecard json"],
            "config_or_agent_mutation_allowed": False,
            "cron_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "error" if errors else "ok", "errors": errors, "warnings": []},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WF89 model-free fleet scorecard")
    ap.add_argument("--global-db", type=Path, default=reader.GLOBAL_DB)
    ap.add_argument("--agent-root", type=Path, default=reader.AGENT_ROOT)
    ap.add_argument("--dispatch-dir", type=Path, default=reader.DISPATCH_DIR)
    ap.add_argument("--history", type=Path, default=HISTORY)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args(argv)
    payload = build(args.global_db, args.agent_root, args.dispatch_dir, args.history, write=args.write)
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    hist = payload["history"]
    print(
        f"status={payload['status']} appended={hist['rows_appended']} pending={hist['rows_pending_append']} "
        f"history={hist['rows_total']} main_work_share={payload['window']['main_share_of_work_runs']}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
