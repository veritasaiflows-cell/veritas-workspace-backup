#!/usr/bin/env python3
"""Run a command with compact terminal output and full logs written to tmp/.

WF72 helper: reduces OpenClaw exec tool-result bloat by keeping verbose stdout/stderr
on disk and printing only status, counts, and artifact paths. It performs no
config/auth/runtime mutation by itself; it only executes the caller-supplied
local command in the current workspace context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "compact-exec-logs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_label(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in label.strip().lower())
    return cleaned.strip("-")[:80] or "compact-exec"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def workspace_cwd(cwd: Path) -> Path:
    """Return an existing directory contained by ROOT, or fail before execution."""
    try:
        resolved = cwd.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"cwd does not exist: {cwd}") from exc
    if not resolved.is_dir():
        raise ValueError(f"cwd is not a directory: {resolved}")
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"cwd is outside workspace root: {resolved}") from exc
    return resolved

def run_command(command: list[str], label: str, cwd: Path) -> dict[str, Any]:
    cwd = workspace_cwd(cwd)
    started = utc_now()
    proc = subprocess.run(command, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", capture_output=True)
    finished = utc_now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{stamp}-{safe_label(label)}"
    stdout_path = OUT_DIR / f"{stem}.stdout.txt"
    stderr_path = OUT_DIR / f"{stem}.stderr.txt"
    json_path = OUT_DIR / f"{stem}.json"
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    report = {
        "schema_version": 1,
        "generated_at_utc": finished,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "label": label,
        "command": command,
        "cwd": rel(cwd),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": {
            "path": rel(stdout_path),
            "chars": len(proc.stdout or ""),
            "sha256": sha256_text(proc.stdout or ""),
        },
        "stderr": {
            "path": rel(stderr_path),
            "chars": len(proc.stderr or ""),
            "sha256": sha256_text(proc.stderr or ""),
        },
        "authority_boundary": "Local command-output compression helper only; no extra config/auth/runtime/canon/finance/trade authority.",
    }
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = rel(json_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a command and print only compact status/counts/log paths.")
    parser.add_argument("--label", default="compact-exec", help="Short label for log filenames.")
    parser.add_argument("--cwd", type=Path, default=ROOT, help="Working directory. Defaults to workspace root.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --, e.g. -- python scripts\\test.py")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(json.dumps({"status": "error", "error": "missing command after --"}, sort_keys=True))
        return 2
    report = run_command(command, args.label, args.cwd)
    print(
        "status={status} returncode={returncode} stdout_chars={stdout_chars} stderr_chars={stderr_chars} report={report} stdout={stdout} stderr={stderr}".format(
            status="ok" if report["ok"] else "failed",
            returncode=report["returncode"],
            stdout_chars=report["stdout"]["chars"],
            stderr_chars=report["stderr"]["chars"],
            report=report["report_path"],
            stdout=report["stdout"]["path"],
            stderr=report["stderr"]["path"],
        )
    )
    return int(report["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
