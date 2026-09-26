#!/usr/bin/env python3
"""WF89 contract v0.3: write a Main dispatch record before a CLI agent run.

`openclaw agent --agent X` runs land in task_runs as runtime='cli' with no
subagent_runs row and no label, so the credit reader cannot bind them. A
record written *before* dispatch lets wf89_credit_reader.py bind it to
exactly one cli task row (same agent + session key, created at or after the
record, identical normalized task-text hash).

Two modes:
- record only (default): write one new JSON file under
  state/wf89-dispatch-records/ and print the exact dispatch command.
- `--run` / `launch()`: write the record and start the agent in one step, so
  the record and the launch can never drift apart. This is the only
  documented CLI dispatch route; scripts import `launch()` instead of calling
  `openclaw agent` themselves.

Records are never overwritten. A record grants no credit, approval or
authority; the reader decides credit from OpenClaw's own stores.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wf89_credit_reader import DISPATCH_DIR, DISPATCH_SCHEMA, normalized_text_hash  # noqa: E402

# The launcher owns these flags; letting a caller set them would break the
# agent/session-key/task-text binding the reader relies on.
RESERVED_ARGS = frozenset({"--agent", "--session-key", "--session-id", "--message",
                           "--message-file", "--to"})


def full_session_key(agent_id: str, key: str) -> str:
    """Match the CLI: --session-key accepts agent:<id>:<key> or a key scoped to --agent.

    OpenClaw stores session keys lowercased (task_runs.child_session_key), so the
    record uses the lowercased key too; a mixed-case key would otherwise never bind.
    """
    key = key.lower()
    agent_id = agent_id.lower()
    if key.startswith("agent:"):
        if not key.startswith(f"agent:{agent_id}:"):
            raise ValueError(f"session key {key!r} is not scoped to agent {agent_id!r}")
        return key
    return f"agent:{agent_id}:{key}"


def write_record_text(agent_id: str, session_key: str, label: str, text: str, *,
                      message_file: Path | None = None, dispatch_dir: Path = DISPATCH_DIR,
                      now_ms: int | None = None, launched_by: str | None = None) -> dict:
    if not text.strip():
        raise ValueError("task text is empty")
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
        "message_file": str(message_file) if message_file else None,
        "created_at_ms": now_ms if now_ms is not None else int(time.time() * 1000),
        "dispatcher": "main",
        "posture": "attribution evidence only; grants no credit, approval or authority",
    }
    if launched_by:
        rec["launched_by"] = launched_by
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    out = dispatch_dir / f"{rec['dispatch_id']}.json"
    with out.open("x", encoding="utf-8") as fh:  # "x": never overwrite
        json.dump(rec, fh, indent=2)
    rec["_written"] = str(out)
    return rec


def write_record(agent_id: str, session_key: str, label: str, message_file: Path,
                 dispatch_dir: Path = DISPATCH_DIR, now_ms: int | None = None) -> dict:
    text = message_file.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("message file is empty")
    return write_record_text(agent_id, session_key, label, text, message_file=message_file,
                             dispatch_dir=dispatch_dir, now_ms=now_ms)


def resolve_binary() -> str:
    return shutil.which("openclaw") or shutil.which("openclaw.cmd") or "openclaw"


def check_extra_args(extra_args: Sequence[str]) -> list[str]:
    extra = [str(a) for a in extra_args]
    bad = sorted({a.split("=", 1)[0] for a in extra} & RESERVED_ARGS)
    if bad:
        raise ValueError(f"launcher owns {bad}; pass them as launch() parameters")
    return extra


def agent_command(binary: str | Sequence[str], agent_id: str, session_key: str, *,
                  message_file: Path | None = None, message_text: str | None = None,
                  extra_args: Sequence[str] = ()) -> list[str]:
    """The exact `openclaw agent` argv the launcher runs (also usable as a dry-run preview)."""
    if (message_file is None) == (message_text is None):
        raise ValueError("pass exactly one of message_file or message_text")
    prefix = [binary] if isinstance(binary, str) else list(binary)
    message = (["--message-file", str(message_file)] if message_file is not None
               else ["--message", message_text])
    return [*prefix, "agent", "--agent", agent_id,
            "--session-key", full_session_key(agent_id, session_key),
            *message, *check_extra_args(extra_args)]


def launch(agent_id: str, session_key: str, label: str, *,
           message_file: Path | None = None, message_text: str | None = None,
           extra_args: Sequence[str] = (), binary: str | Sequence[str] | None = None,
           dispatch_dir: Path = DISPATCH_DIR, runner: Callable[..., Any] = subprocess.run,
           launched_by: str = "wf89_dispatch_record.launch",
           **run_kwargs: Any) -> tuple[dict, Any]:
    """Write the dispatch record, then run the agent. Returns (record, runner result).

    Everything is validated before the record is written, so a rejected
    launch leaves no orphan record. If the runner itself raises after the
    record exists, the record stays and the reader reports it PENDING, which
    is the honest outcome for a dispatch that never produced a run.
    """
    command = agent_command(binary if binary is not None else resolve_binary(), agent_id,
                            session_key, message_file=message_file, message_text=message_text,
                            extra_args=extra_args)
    text = message_text if message_text is not None else Path(message_file).read_text(encoding="utf-8")
    rec = write_record_text(agent_id, session_key, label, text,
                            message_file=Path(message_file) if message_file is not None else None,
                            dispatch_dir=dispatch_dir, launched_by=launched_by)
    rec["dispatch_command"] = command
    return rec, runner(command, **run_kwargs)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, extra = argv[:split], argv[split + 1:]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 epilog="With --run, arguments after `--` go to `openclaw agent` "
                                        "(e.g. -- --model X --thinking high --timeout 600 --json).")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--session-key", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--message-file", required=True)
    ap.add_argument("--dispatch-dir", default=str(DISPATCH_DIR))
    ap.add_argument("--run", action="store_true",
                    help="write the record and launch the agent in one step (recommended)")
    args = ap.parse_args(argv)
    if extra and not args.run:
        ap.error("arguments after `--` require --run")
    if args.run:
        # Record goes to stderr so the agent's stdout (e.g. --json) stays parseable.
        rec, proc = launch(args.agent, args.session_key, args.label,
                           message_file=Path(args.message_file), extra_args=extra,
                           dispatch_dir=Path(args.dispatch_dir), check=False)
        print(json.dumps(rec, indent=2), file=sys.stderr)
        return int(proc.returncode)
    rec = write_record(args.agent, args.session_key, args.label, Path(args.message_file),
                       Path(args.dispatch_dir))
    rec["dispatch_command"] = (f"openclaw agent --agent {rec['agent_id']} --session-key "
                               f"{rec['session_key']} --message-file {args.message_file}")
    rec["note"] = "record only; prefer --run so the record and launch cannot drift apart"
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
