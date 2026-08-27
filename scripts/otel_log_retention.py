#!/usr/bin/env python3
"""Rotate the local OTEL collector stderr log with restart-safe handling.

The collector writes to stderr through a Windows file handle. Truncating that
file while the collector is alive can leave the writer positioned past EOF, so
live rotation stops the collector, moves the log, then starts the same local
collector config again.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
OTEL_DIR = ROOT / "tmp" / "otel-collector"
DEFAULT_LOG = OTEL_DIR / "collector.err.log"
DEFAULT_STDOUT_LOG = OTEL_DIR / "collector.out.log"
DEFAULT_ARCHIVE_DIR = OTEL_DIR / "archive"
DEFAULT_EXE = ROOT / "tools" / "otelcol" / "otelcol.exe"
DEFAULT_CONFIG = ROOT / "tools" / "otelcol" / "openclaw-local-otel-runtime-metadata.yaml"
DEFAULT_OUT = ROOT / "tmp" / "otel-log-retention.json"
SCHEMA = "veritas.otel_log_retention.v1"
CREATE_NO_WINDOW = 0x08000000

AUTHORITY_BOUNDARY = {
    "review_only": False,
    "local_only": True,
    "collector_restart_allowed_with_flag": True,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secrets_or_headers_collection_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False, "size_bytes": 0}
    stat = path.stat()
    return {
        "path": rel(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def sha256_file(path: Path, max_bytes: int = 1_000_000) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        remaining = max_bytes
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def otel_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq otelcol.exe", "/FO", "CSV", "/NH"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if result.returncode != 0:
        return []
    rows: list[int] = []
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) >= 2 and row[0].strip('"').lower() == "otelcol.exe":
            try:
                rows.append(int(row[1].strip('"')))
            except ValueError:
                pass
    return rows


def port_listening(host: str = "127.0.0.1", port: int = 4318, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(expected: bool, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if port_listening() is expected:
            return True
        time.sleep(0.25)
    return port_listening() is expected


def stop_collectors(pids: list[int]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for pid in pids:
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        results.append({
            "pid": pid,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": (completed.stdout or "")[-1000:],
            "stderr_tail": (completed.stderr or "")[-1000:],
        })
    return results


def start_collector(exe: Path, config: Path, stdout_log: Path, stderr_log: Path) -> dict[str, Any]:
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_log.open("ab")
    stderr_handle = stderr_log.open("ab")
    try:
        proc = subprocess.Popen(
            [str(exe), f"--config=file:{rel(config)}"],
            cwd=ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return {"pid": proc.pid, "command": [rel(exe), f"--config=file:{rel(config)}"]}


def rotate_log(log: Path, archive_dir: Path, keep: int) -> dict[str, Any]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = archive_dir / f"{log.stem}.{stamp}{log.suffix}"
    counter = 1
    while archive.exists():
        archive = archive_dir / f"{log.stem}.{stamp}.{counter}{log.suffix}"
        counter += 1
    source_state = file_state(log)
    source_hash_prefix = sha256_file(log)
    if log.exists():
        shutil.move(str(log), str(archive))
    archive_state = file_state(archive)
    archives = sorted(archive_dir.glob(f"{log.stem}.*{log.suffix}"), key=lambda item: item.stat().st_mtime, reverse=True)
    removed: list[dict[str, Any]] = []
    if keep >= 0:
        for old in archives[keep:]:
            state = file_state(old)
            old.unlink()
            removed.append(state)
    return {
        "archive": rel(archive),
        "source_before": source_state,
        "source_sha256_first_mb": source_hash_prefix,
        "archive_state": archive_state,
        "removed_archives": removed,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    log = args.log if args.log.is_absolute() else ROOT / args.log
    stdout_log = args.stdout_log if args.stdout_log.is_absolute() else ROOT / args.stdout_log
    archive_dir = args.archive_dir if args.archive_dir.is_absolute() else ROOT / args.archive_dir
    exe = args.collector_exe if args.collector_exe.is_absolute() else ROOT / args.collector_exe
    config = args.collector_config if args.collector_config.is_absolute() else ROOT / args.collector_config
    max_bytes = int(args.max_mb * 1024 * 1024)
    before = file_state(log)
    pids_before = otel_pids()
    needs_rotation = bool(before.get("exists")) and int(before.get("size_bytes") or 0) > max_bytes
    stop_results: list[dict[str, Any]] = []
    start_result: dict[str, Any] | None = None
    rotate_result: dict[str, Any] | None = None
    errors: list[str] = []
    warnings: list[str] = []
    action = "none"

    if needs_rotation:
        if args.dry_run:
            action = "would_rotate"
        elif pids_before and not args.restart:
            action = "blocked"
            errors.append("collector_running_restart_flag_required")
        else:
            action = "rotated"
            if pids_before:
                stop_results = stop_collectors(pids_before)
                if not all(item.get("ok") for item in stop_results):
                    errors.append("collector_stop_failed")
                if not wait_for_port(False, args.stop_timeout_seconds):
                    warnings.append("collector_port_still_listening_after_stop_timeout")
            if not errors:
                rotate_result = rotate_log(log, archive_dir, args.keep)
                if args.restart:
                    start_result = start_collector(exe, config, stdout_log, log)
                    if not wait_for_port(True, args.start_timeout_seconds):
                        errors.append("collector_port_not_listening_after_restart")
    elif not before.get("exists"):
        warnings.append("collector_log_missing")

    after = file_state(log)
    pids_after = otel_pids()
    if args.validate and args.restart and needs_rotation and not pids_after:
        errors.append("collector_process_not_running_after_restart")
    if args.validate and args.restart and needs_rotation and not port_listening():
        errors.append("collector_endpoint_not_listening_after_restart")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "action": action,
        "threshold": {"max_mb": args.max_mb, "max_bytes": max_bytes, "keep_archives": args.keep},
        "paths": {
            "log": rel(log),
            "stdout_log": rel(stdout_log),
            "archive_dir": rel(archive_dir),
            "collector_exe": rel(exe),
            "collector_config": rel(config),
        },
        "before": before,
        "after": after,
        "needs_rotation": needs_rotation,
        "collector_pids_before": pids_before,
        "collector_pids_after": pids_after,
        "stop_results": stop_results,
        "rotate_result": rotate_result,
        "start_result": start_result,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "validation": {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotate local OTEL collector logs when they exceed a size threshold.")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--stdout-log", type=Path, default=DEFAULT_STDOUT_LOG)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--collector-exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--collector-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-mb", type=float, default=256.0)
    parser.add_argument("--keep", type=int, default=5)
    parser.add_argument("--restart", action="store_true", help="Stop/restart otelcol.exe if the live log needs rotation.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--start-timeout-seconds", type=float, default=15.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload, indent=2)
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"action={payload['action']} before={payload['before'].get('size_bytes')} after={payload['after'].get('size_bytes')} out={rel(out)}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
