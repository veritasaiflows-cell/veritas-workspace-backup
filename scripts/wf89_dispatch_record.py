#!/usr/bin/env python3
"""WF89 contract v0.3: write a Main dispatch record before a CLI agent run.

`openclaw agent --agent X` runs land in task_runs as runtime='cli' with no
subagent_runs row and no label, so the credit reader cannot bind them. Main
writes this record *before* dispatch; wf89_credit_reader.py then
binds it to exactly one cli task row (same agent + session key, created at or
after the record, identical normalized task-text hash).

This script only writes one new JSON file under state/wf89-dispatch-records/.
It never starts an agent, never overwrites a record, and grants no credit,
approval or authority. It prints the exact dispatch command for Main to run.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wf89_credit_reader import DISPATCH_DIR, DISPATCH_SCHEMA, normalized_text_hash  # noqa: E402


def full_session_key(agent_id: str, key: str) -> str:
    """Match the CLI: --session-key accepts agent:<id>:<key> or a key scoped to --agent."""
    if key.startswith("agent:"):
        if not key.startswith(f"agent:{agent_id}:"):
            raise ValueError(f"session key {key!r} is not scoped to agent {agent_id!r}")
        return key
    return f"agent:{agent_id}:{key}"


def write_record(agent_id: str, session_key: str, label: str, message_file: Path,
                 dispatch_dir: Path = DISPATCH_DIR, now_ms: int | None = None) -> dict:
    text = message_file.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("message file is empty")
    if not label.strip():
        raise ValueError("label is required (unlabeled runs are never creditable)")
    rec = {
        "schema": DISPATCH_SCHEMA,
        "contract": "v0.3",
        "dispatch_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "session_key": full_session_key(agent_id, session_key),
        "label": label.strip(),
        "task_text_sha256": normalized_text_hash(text),
        "message_file": str(message_file),
        "created_at_ms": now_ms if now_ms is not None else int(time.time() * 1000),
        "dispatcher": "main",
        "posture": "attribution evidence only; grants no credit, approval or authority",
    }
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    out = dispatch_dir / f"{rec['dispatch_id']}.json"
    with out.open("x", encoding="utf-8") as fh:  # "x": never overwrite
        json.dump(rec, fh, indent=2)
    rec["_written"] = str(out)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--agent", required=True)
    ap.add_argument("--session-key", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--message-file", required=True)
    ap.add_argument("--dispatch-dir", default=str(DISPATCH_DIR))
    args = ap.parse_args(argv)
    rec = write_record(args.agent, args.session_key, args.label, Path(args.message_file),
                       Path(args.dispatch_dir))
    rec["dispatch_command"] = (f"openclaw agent --agent {rec['agent_id']} --session-key "
                               f"{rec['session_key']} --message-file {args.message_file}")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
