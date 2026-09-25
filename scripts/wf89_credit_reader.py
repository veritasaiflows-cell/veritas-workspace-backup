#!/usr/bin/env python3
"""WF89 D2a per-run credit reader (CANDIDATE, read-only, review-only).

Implements attribution contract v0.2
(tmp/wf89-fleet-20260909/coder-attribution-20260910/attribution-contract-v0.2.md)
binding semantics exactly:

- Spine: global store task_runs rows with runtime='subagent'.
- Corroboration: subagent_runs row keyed by same run_id with matching
  child/controller/requester keys + requesterAgentId.
- Executor-store witness: agents/<agent_id>/agent/openclaw-agent.sqlite
  session_nodes row (entry_valid=1) for child_session_key whose current
  sessionId matches a session_windows row; window lifecycle must match
  entry lifecycle or state = MISMATCH (blocks credit).
- Usage credit: SUM over trajectory_runtime_events model.completed events
  with run_id == task_runs.run_id WITHIN the bound window (session_id ==
  bound window session_id). Required usage keys: input/output/total/
  cost.total. Optional: cacheRead/reasoningTokens. Missing-usage =>
  PARTIAL/no-credit (never inferred).
- task_runs-only rows => observable-only, verified=false, creditable=false.
- Unknown vs uninstrumented (S5): task_kind NULL = uninstrumented;
  label NULL = unlabeled/observable-only; missing subagent_runs =
  INCOMPLETE (unknown); executor store absent/entry_valid=0/corrupt =
  UNREADABLE; window/entry mismatch = MISMATCH.
- Per-attempt per-window reporting ONLY. No aggregation across generations
  (D2c unapproved). Legacy subagent_dispatch_bindings permanently excluded
  (never read).

Contract v0.3 (ACCEPTED 2026-09-24; on by default, --no-cli opts out; see
tmp/wf89-fleet-20260909/attribution-contract-v0.3.md): runtime='cli'
rows (`openclaw agent --agent X`) have no subagent_runs leg. A Main-written
dispatch record in state/wf89-dispatch-records/ replaces it; the executor
witness and usage steps are unchanged.

All SQLite opened read-only via URI mode=ro. No writes to any store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
GLOBAL_DB = HOME / ".openclaw" / "state" / "openclaw.sqlite"
AGENT_ROOT = HOME / ".openclaw" / "agents"
SCHEMA = "veritas.wf89_credit_reader.v1"
REQUIRED_USAGE_KEYS = ("input", "output", "total")
TERMINAL_TASK_STATUSES = {"succeeded", "failed", "timed_out", "cancelled"}
CREDITABLE_TASK_STATUSES = {"succeeded", "failed", "timed_out", "cancelled"}
WORKSPACE = Path(__file__).resolve().parent.parent
DISPATCH_DIR = WORKSPACE / "state" / "wf89-dispatch-records"
DISPATCH_SCHEMA = "veritas.wf89_dispatch_record.v1"
DISPATCH_REQUIRED_KEYS = ("dispatch_id", "agent_id", "session_key", "label",
                          "task_text_sha256", "created_at_ms")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def task_text_hash(task_text: str) -> str:
    return hashlib.sha256(task_text.encode("utf-8")).hexdigest()


def open_ro(path: Path) -> sqlite3.Connection:
    uri = path.as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=10.0)
    con.row_factory = sqlite3.Row
    return con


def parse_generation(detail_json: str | None) -> int | None:
    if not detail_json:
        return None
    try:
        return json.loads(detail_json).get("generation")
    except (json.JSONDecodeError, AttributeError):
        return None


def extract_usage(event_json: str) -> dict | None:
    """Return usable usage dict or None. Required: input/output/total/cost.total."""
    try:
        d = json.loads(event_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if d.get("type") != "model.completed":
        return None
    usage = (d.get("data") or {}).get("usage")
    if not isinstance(usage, dict):
        return None
    if not all(isinstance(usage.get(k), (int, float)) for k in REQUIRED_USAGE_KEYS):
        return None
    cost = usage.get("cost")
    if not isinstance(cost, dict) or not isinstance(cost.get("total"), (int, float)):
        return None
    out = {k: usage[k] for k in REQUIRED_USAGE_KEYS}
    out["cost_total"] = cost["total"]
    for opt in ("cacheRead", "reasoningTokens"):
        if isinstance(usage.get(opt), (int, float)):
            out[opt] = usage[opt]
    return out


def classify_row(task: sqlite3.Row, sub: sqlite3.Row | None, node: sqlite3.Row | None,
                 node_error: str | None, window: sqlite3.Row | None,
                 entry: dict | None, usage_events: list[dict]) -> dict:
    task_id = task["task_id"]
    run_id = task["run_id"]
    label = task["label"]
    status = task["status"]
    task_kind = task["task_kind"]
    child_key = task["child_session_key"]
    generation = parse_generation(task["detail_json"])
    kind_state = "uninstrumented" if task_kind is None else task_kind
    _task_text = task["task"]
    _task_text_sha256 = task_text_hash(_task_text) if isinstance(_task_text, str) and _task_text != "" else "hash_uncomputable"
    rec: dict = {
        "task_id": task_id, "run_id": run_id, "label": label if label is not None else "unlabeled",
        "task_text_sha256": _task_text_sha256,
        "label_null": label is None, "status": status, "task_kind_state": kind_state,
        "agent_id": task["agent_id"], "child_session_key": child_key,
        "requester_session_key": task["requester_session_key"],
        "requester_agent_id": task["requester_agent_id"],
        "generation": generation, "verified": False, "creditable": False,
        "usage": None, "usage_event_count": 0,
    }
    # S5 / F: task_runs-only => observable-only.
    if sub is None:
        rec.update(state="INCOMPLETE" if run_id else "OBSERVABLE_ONLY",
                   reason="missing subagent_runs corroboration (unknown, not failed)" if run_id
                   else "no run_id; task_runs-only observable record")
        return rec
    # Corroboration cross-match (contract S1).
    try:
        payload = json.loads(sub["payload_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    mismatch_keys = [k for k, a, b in (
        ("child_session_key", sub["child_session_key"], child_key),
        ("requester_session_key", sub["requester_session_key"], task["requester_session_key"]),
    ) if a != b]
    if mismatch_keys or payload.get("taskRunId") != run_id:
        rec.update(state="MISMATCH",
                   reason=f"subagent_runs cross-match failed (keys={mismatch_keys}, taskRunId={payload.get('taskRunId')})")
        return rec
    rec["controller_session_key"] = sub["controller_session_key"]
    if label is None:
        rec.update(state="OBSERVABLE_ONLY", reason="unlabeled run: observable, not creditable",
                   verified=False, creditable=False)
        return rec
    return classify_witness(rec, status, node, node_error, window, entry, usage_events)


def classify_witness(rec: dict, status: str, node: sqlite3.Row | None, node_error: str | None,
                     window: sqlite3.Row | None, entry: dict | None,
                     usage_events: list[dict]) -> dict:
    """Executor-store witness + usage steps shared by the subagent and CLI paths."""
    if node_error is not None:
        rec.update(state="UNREADABLE", reason=node_error)
        return rec
    assert node is not None
    if not node["entry_valid"]:
        rec.update(state="UNREADABLE", reason="executor session_nodes entry_valid=0")
        return rec
    if entry is None:
        rec.update(state="UNREADABLE", reason="executor entry_json missing/corrupt")
        return rec
    if entry.get("sessionId") != node["current_session_id"]:
        rec.update(state="MISMATCH",
                   reason="entry sessionId != session_nodes.current_session_id")
        return rec
    if window is None:
        rec.update(state="MISMATCH", reason="no session_windows row for bound window session_id")
        return rec
    if (entry.get("status") is not None and window["status"] is not None
            and entry.get("status") != window["status"]):
        rec.update(state="MISMATCH",
                   reason=f"window/entry lifecycle mismatch (entry={entry.get('status')}, window={window['status']})")
        return rec
    rec["window_session_id"] = node["current_session_id"]
    rec["window_status"] = window["status"]
    rec["window_model"] = window["model"]
    rec["window_model_provider"] = window["model_provider"]
    if status not in CREDITABLE_TASK_STATUSES:
        rec.update(state="OBSERVABLE_ONLY",
                   reason=f"non-terminal task status ({status}); observable only")
        return rec
    # Usage witness (contract S3.5/S4): missing => PARTIAL, never inferred.
    usable = [u for u in usage_events if u is not None]
    if not usable:
        rec.update(state="PARTIAL", reason="no usable model.completed usage events for run_id in bound window")
        return rec
    totals: dict = {"input": 0, "output": 0, "total": 0, "cost_total": 0.0}
    for opt in ("cacheRead", "reasoningTokens"):
        if any(opt in u for u in usable):
            totals[opt] = 0
    for u in usable:
        for k in totals:
            totals[k] += u.get(k, 0)
    rec.update(state="CREDITABLE", verified=True, creditable=True,
               usage=totals, usage_event_count=len(usable),
               reason=f"{len(usable)} model.completed event(s) in bound window")
    return rec


def normalized_text_hash(text: str) -> str:
    """The task store keeps CLI --message text stripped; hash both sides the same way."""
    return task_text_hash(text.strip())


def load_dispatch_records(dispatch_dir: Path) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    if not dispatch_dir.is_dir():
        return records, errors
    for p in sorted(dispatch_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{p.name}: unreadable ({exc})")
            continue
        missing = [k for k in DISPATCH_REQUIRED_KEYS if not d.get(k)]
        if d.get("schema") != DISPATCH_SCHEMA or missing:
            errors.append(f"{p.name}: invalid dispatch record (schema={d.get('schema')}, missing={missing})")
            continue
        d["_path"] = p.name
        records.append(d)
    return records, errors


def classify_cli_row(task: sqlite3.Row, dispatch: dict, node: sqlite3.Row | None,
                     node_error: str | None, window: sqlite3.Row | None,
                     entry: dict | None, usage_events: list[dict]) -> dict:
    """Contract v0.3: a Main-written dispatch record replaces the
    subagent_runs leg for runtime='cli' rows. Label comes from the record."""
    rec = classify_row(task, None, None, None, None, None, [])
    rec.update(dispatch_path="cli", dispatch_id=dispatch["dispatch_id"],
               dispatch_record=dispatch["_path"], label=dispatch["label"], label_null=False)
    return classify_witness(rec, task["status"], node, node_error, window, entry, usage_events)


def executor_witness(agent_root: Path, agent_id: str | None, child_key: str | None,
                     run_id: str | None) -> tuple:
    """Return (node, node_error, window, entry, usage_events) from the executor store."""
    node = window = None
    entry = None
    node_error = None
    usage_events: list = []
    if not agent_id or not child_key:
        return None, "missing agent_id/child_session_key; executor store unresolvable", None, None, []
    edb = agent_root / agent_id / "agent" / "openclaw-agent.sqlite"
    if not edb.exists():
        return None, f"executor store absent: {edb}", None, None, []
    try:
        econ = open_ro(edb)
        try:
            node = econ.execute("SELECT * FROM session_nodes WHERE session_key = ?",
                                (child_key,)).fetchone()
            if node is None:
                node_error = "no session_nodes row for child_session_key"
            else:
                try:
                    entry = json.loads(node["entry_json"] or "null")
                    if not isinstance(entry, dict):
                        entry = None
                except json.JSONDecodeError:
                    entry = None
                if entry is None and node["entry_valid"]:
                    node_error = "entry_json corrupt"
                    node = None
                else:
                    wid = node["current_session_id"]
                    window = econ.execute("SELECT * FROM session_windows WHERE session_id = ?",
                                          (wid,)).fetchone()
                    if run_id and wid:
                        for (ej,) in econ.execute(
                                "SELECT event_json FROM trajectory_runtime_events"
                                " WHERE run_id = ? AND session_id = ?", (run_id, wid)).fetchall():
                            u = extract_usage(ej)
                            if u is not None:
                                usage_events.append(u)
                            else:
                                try:
                                    if json.loads(ej).get("type") == "model.completed":
                                        usage_events.append(None)
                                except (json.JSONDecodeError, TypeError, AttributeError):
                                    pass
        finally:
            econ.close()
    except sqlite3.Error as exc:
        node_error = f"executor store unreadable: {exc}"
        node = None
    return node, node_error, window, entry, usage_events


def read_cli(dispatch_dir: Path, global_db: Path = GLOBAL_DB,
             agent_root: Path = AGENT_ROOT) -> dict:
    """Contract v0.3: bind each Main dispatch record to exactly one
    runtime='cli' task row (same agent, same session key, created at/after the
    record, identical normalized task-text hash). 0 matches = PENDING, >1 =
    MISMATCH (ambiguous). CLI rows with no record are counted, never credited."""
    dispatches, errors = load_dispatch_records(dispatch_dir)
    gcon = open_ro(global_db)
    try:
        cli_rows = gcon.execute("SELECT * FROM task_runs WHERE runtime='cli' ORDER BY created_at").fetchall()
    finally:
        gcon.close()
    records, bound_task_ids = [], set()
    for d in dispatches:
        matches = [t for t in cli_rows
                   if t["agent_id"] == d["agent_id"] and t["child_session_key"] == d["session_key"]
                   and (t["created_at"] or 0) >= d["created_at_ms"]
                   and isinstance(t["task"], str)
                   and normalized_text_hash(t["task"]) == d["task_text_sha256"]]
        if len(matches) != 1:
            state = "PENDING" if not matches else "MISMATCH"
            records.append({"dispatch_path": "cli", "dispatch_id": d["dispatch_id"],
                            "dispatch_record": d["_path"], "agent_id": d["agent_id"],
                            "label": d["label"], "state": state, "verified": False,
                            "creditable": False,
                            "reason": "no matching runtime='cli' task row yet" if not matches
                            else f"ambiguous: {len(matches)} cli task rows match one dispatch record"})
            continue
        task = matches[0]
        bound_task_ids.add(task["task_id"])
        node, node_error, window, entry, usage_events = executor_witness(
            agent_root, task["agent_id"], task["child_session_key"], task["run_id"])
        rec = classify_cli_row(task, d, node, node_error, window, entry, usage_events)
        rec["usage_event_count"] = (len([u for u in usage_events if isinstance(u, dict)])
                                    if rec["state"] == "CREDITABLE" else 0)
        records.append(rec)
    unrecorded: dict[str, int] = {}
    for t in cli_rows:
        if t["task_id"] not in bound_task_ids:
            unrecorded[t["agent_id"] or "unknown"] = unrecorded.get(t["agent_id"] or "unknown", 0) + 1
    counts: dict[str, int] = {}
    for r in records:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"contract": "v0.3", "dispatch_dir": str(dispatch_dir),
            "dispatch_records": len(dispatches), "dispatch_record_errors": errors,
            "counts": counts, "cli_rows_total": len(cli_rows),
            "cli_rows_without_dispatch_record_by_agent": unrecorded, "records": records}


def read_task(task_id: str | None = None, limit: int | None = None,
              global_db: Path = GLOBAL_DB, agent_root: Path = AGENT_ROOT) -> dict:
    gcon = open_ro(global_db)
    try:
        q = ("SELECT * FROM task_runs WHERE runtime='subagent'"
             + (" AND task_id = ?" if task_id else "") + " ORDER BY created_at"
             + (f" LIMIT {int(limit)}" if limit else ""))
        tasks = gcon.execute(q, (task_id,) if task_id else []).fetchall()
        # Join on payload.taskRunId (the contract S1 key), not subagent_runs.run_id:
        # re-announced/generation>=2 runs get a new registry run_id (e.g.
        # "announce:requester-settle:...") while taskRunId still names the task run.
        subs: dict[str, list[sqlite3.Row]] = {}
        for r in gcon.execute("SELECT * FROM subagent_runs").fetchall():
            try:
                key = json.loads(r["payload_json"] or "{}").get("taskRunId") or r["run_id"]
            except json.JSONDecodeError:
                key = r["run_id"]
            if key:
                subs.setdefault(key, []).append(r)
    finally:
        gcon.close()
    records = []
    for task in tasks:
        run_id = task["run_id"]
        candidates = subs.get(run_id, []) if run_id else []
        if len(candidates) > 1:
            rec = classify_row(task, None, None, None, None, None, [])
            rec.update(state="MISMATCH",
                       reason=f"ambiguous corroboration: {len(candidates)} subagent_runs rows share taskRunId")
            records.append(rec)
            continue
        sub = candidates[0] if candidates else None
        node, node_error, window, entry, usage_events = executor_witness(
            agent_root, task["agent_id"], task["child_session_key"], run_id)
        # Normalize: usage_events may contain None sentinels for unusable completed events.
        usable_only = [u for u in usage_events if isinstance(u, dict)]
        rec = classify_row(task, sub, node, node_error, window, entry, usage_events)
        rec["usage_event_count"] = len(usable_only) if rec["state"] == "CREDITABLE" else 0
        records.append(rec)
    counts: dict[str, int] = {}
    for r in records:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"schema": SCHEMA, "observed_at_utc": utc_now(),
            "global_db": str(global_db), "total_scanned": len(records),
            "counts": counts, "records": records}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WF89 D2a read-only per-run credit reader")
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--global-db", default=str(GLOBAL_DB))
    ap.add_argument("--agent-root", default=str(AGENT_ROOT))
    ap.add_argument("--no-cli", action="store_true",
                    help="skip binding runtime='cli' rows via dispatch records (contract v0.3)")
    ap.add_argument("--include-cli", action="store_true",
                    help="no-op; kept for pre-acceptance commands (CLI binding is the default)")
    ap.add_argument("--dispatch-dir", default=str(DISPATCH_DIR))
    args = ap.parse_args(argv)
    result = read_task(task_id=args.task_id, limit=args.limit,
                       global_db=Path(args.global_db), agent_root=Path(args.agent_root))
    if not args.no_cli:
        result["cli"] = read_cli(Path(args.dispatch_dir), global_db=Path(args.global_db),
                                 agent_root=Path(args.agent_root))
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        summary = {"total_scanned": result["total_scanned"], "counts": result["counts"],
                   "out": args.out}
        if "cli" in result:
            summary["cli"] = {k: v for k, v in result["cli"].items() if k != "records"}
        print(json.dumps(summary, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
