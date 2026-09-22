#!/usr/bin/env python3
"""Local-only OTEL collector watchdog: detect death, and recover only on explicit --restart.

Bounded supervision for tools/otelcol/otelcol.exe. Detection is always safe and
non-mutating. Recovery runs only when --restart is passed, so an unwired copy of
this script cannot change runtime state by accident.

Authority boundary: local-only; loopback-only bind preserved; no collector-config
mutation; no gateway/config/service/scheduled-task mutation; no external export;
no secrets/headers/prompt/response/tool-content capture; no finance/canon/
portfolio/capital/paper/live/account authority; no approval inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OTEL_DIR = ROOT / "tmp" / "otel-collector"
DEFAULT_EXE = ROOT / "tools" / "otelcol" / "otelcol.exe"
DEFAULT_CONFIG = ROOT / "tools" / "otelcol" / "openclaw-local-otel-runtime-metadata.yaml"
DEFAULT_STDOUT_LOG = OTEL_DIR / "collector.out.log"
DEFAULT_STDERR_LOG = OTEL_DIR / "collector.err.log"
DEFAULT_PID_FILE = OTEL_DIR / "collector.pid"
DEFAULT_LOCK = ROOT / "tmp" / "otel-collector-watchdog.lock"
DEFAULT_OUT = ROOT / "tmp" / "otel-collector-watchdog.json"
DEFAULT_DATA_FILES = (
    OTEL_DIR / "metrics.jsonl",
    OTEL_DIR / "traces.jsonl",
    OTEL_DIR / "logs.jsonl",
)
SCHEMA = "veritas.otel_collector_watchdog.v1"

HOST = "127.0.0.1"
PORT = 4318
LOCK_STALE_SECONDS = 300.0

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "loopback_bind_preserved": True,
    "external_export_allowed": False,
    "collector_config_mutation_allowed": False,
    "gateway_or_runtime_config_mutation_allowed": False,
    "scheduled_task_or_service_mutation_allowed": False,
    "capture_depth_expansion_allowed": False,
    "secrets_or_headers_collection_allowed": False,
    "finance_canon_portfolio_mutation_allowed": False,
    "capital_or_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def port_listening(host: str = HOST, port: int = PORT, timeout: float = 1.0) -> bool:
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


def _tasklist_csv(image: str | None = None, pid: int | None = None) -> str:
    if pid is not None:
        args = ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"]
    else:
        args = ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"]
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout or ""


def _parse_pids(stdout: str) -> list[int]:
    pids: list[int] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith('"'):
            continue
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == "otelcol.exe":
            try:
                pids.append(int(parts[1]))
            except ValueError:
                continue
    return pids


def otel_pids() -> list[int]:
    return _parse_pids(_tasklist_csv(image="otelcol.exe"))


def pid_alive(pid: int) -> bool:
    return bool(_parse_pids(_tasklist_csv(pid=pid)))


def read_pid_file(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def data_freshness(paths: tuple[Path, ...]) -> dict[str, Any]:
    """Newest non-empty file-exporter write, so 'listening but receiving nothing' is detectable."""
    newest: float | None = None
    newest_path: str | None = None
    sizes: dict[str, int] = {}
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        sizes[rel(path)] = stat.st_size
        if stat.st_size <= 0:
            continue
        if newest is None or stat.st_mtime > newest:
            newest = stat.st_mtime
            newest_path = rel(path)
    silent_hours: float | None = None
    if newest is not None:
        silent_hours = round((time.time() - newest) / 3600.0, 2)
    newest_utc = (
        datetime.fromtimestamp(newest, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if newest is not None
        else None
    )
    return {
        "watched": [rel(path) for path in paths],
        "sizes_bytes": sizes,
        "newest_data_path": newest_path,
        "newest_data_utc": newest_utc,
        "silent_hours": silent_hours,
    }


def config_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def acquire_lock(lock: Path, *, enabled: bool) -> dict[str, Any]:
    """Single-flight guard so overlapping runs cannot double-start the collector."""
    if not enabled:
        return {"acquired": True, "reason": "lock_disabled"}
    if lock.exists():
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        age = time.time() - float(data.get("started_epoch") or 0)
        holder = data.get("pid")
        if age < LOCK_STALE_SECONDS and isinstance(holder, int) and pid_alive(holder):
            return {"acquired": False, "reason": "concurrent_run", "holder_pid": holder, "age_seconds": round(age, 1)}
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        json.dumps({"pid": os.getpid(), "started_epoch": time.time(), "started_utc": utc_now()}),
        encoding="utf-8",
    )
    return {"acquired": True, "reason": "lock_acquired"}


def release_lock(lock: Path) -> None:
    try:
        lock.unlink()
    except OSError:
        pass


def planned_start_command(exe: Path, config: Path) -> dict[str, Any]:
    return {
        "argv": [rel(exe), f"--config=file:{rel(config)}"],
        "cwd": rel(ROOT),
        "stdout": rel(DEFAULT_STDOUT_LOG),
        "stderr": rel(DEFAULT_STDERR_LOG),
        "creationflags": ["DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"],
        "note": "Detached so the collector survives the parent watchdog process; loopback-only config is passed unchanged.",
    }


def start_collector(exe: Path, config: Path, stdout_log: Path, stderr_log: Path) -> dict[str, Any]:
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    with stdout_log.open("ab") as out_handle, stderr_log.open("ab") as err_handle:
        proc = subprocess.Popen(
            [str(exe), f"--config=file:{rel(config)}"],
            cwd=ROOT,
            stdout=out_handle,
            stderr=err_handle,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    return {"pid": proc.pid, "command": [rel(exe), f"--config=file:{rel(config)}"]}


def previous_consecutive_failures(out: Path) -> int:
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    try:
        return int(data.get("consecutive_unhealthy_runs") or 0)
    except (TypeError, ValueError):
        return 0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    exe = args.collector_exe if args.collector_exe.is_absolute() else ROOT / args.collector_exe
    config = args.collector_config if args.collector_config.is_absolute() else ROOT / args.collector_config
    pid_file = args.pid_file if args.pid_file.is_absolute() else ROOT / args.pid_file
    out = args.out if args.out.is_absolute() else ROOT / args.out
    lock = DEFAULT_LOCK

    lock_state = acquire_lock(lock, enabled=not args.no_lock)
    errors: list[str] = []
    warnings: list[str] = []
    action = "none"

    try:
        pids_before = otel_pids()
        listening_before = port_listening()
        healthy_before = listening_before

        if not lock_state.get("acquired"):
            return {
                "schema": SCHEMA,
                "generated_at_utc": utc_now(),
                "status": "ok",
                "action": "skipped_concurrent_run",
                "healthy": listening_before,
                "lock": lock_state,
                "authority_boundary": AUTHORITY_BOUNDARY,
                "errors": [],
                "warnings": ["another watchdog run holds the lock"],
                "consecutive_unhealthy_runs": previous_consecutive_failures(out),
            }

        start_result: dict[str, Any] | None = None
        if healthy_before:
            action = "none"
        elif args.dry_run:
            action = "would_restart"
        elif not args.restart:
            action = "detected_down_no_restart"
            warnings.append("collector is down; --restart not supplied so no recovery was attempted")
        else:
            if not exe.exists():
                errors.append("collector_executable_missing")
                action = "restart_failed"
            elif not config.exists():
                errors.append("collector_config_missing")
                action = "restart_failed"
            else:
                action = "restarted"
                start_result = start_collector(exe, config, DEFAULT_STDOUT_LOG, DEFAULT_STDERR_LOG)
                if not wait_for_port(True, args.start_timeout_seconds):
                    errors.append("collector_endpoint_not_listening_after_restart")
                    action = "restart_failed"

        listening_after = port_listening()
        pids_after = otel_pids()
        if action == "restarted" and not pids_after:
            errors.append("collector_process_not_running_after_restart")
            action = "restart_failed"

        if action == "restart_failed":
            warnings.append("recovery did not restore the collector endpoint")

        if pids_after:
            pid_file.parent.mkdir(parents=True, exist_ok=True)
            pid_file.write_text(str(pids_after[0]), encoding="utf-8")

        freshness = data_freshness(DEFAULT_DATA_FILES)
        starvation_enabled = bool(args.starvation_hours and args.starvation_hours > 0)
        silence = freshness.get("silent_hours")
        starving = bool(
            starvation_enabled
            and listening_after
            and (silence is None or float(silence) > float(args.starvation_hours))
        )
        if starving:
            # Process is up but no telemetry is landing: this is the case that silently
            # invalidates evidence, so it alerts without triggering a restart.
            errors.append("collector_listening_but_no_recent_data")

        healthy = bool(listening_after) and not starving
        consecutive = 0 if healthy else previous_consecutive_failures(out) + 1

        if args.validate:
            if not listening_after:
                errors.append("collector_not_listening")
            if action == "restarted" and not listening_after:
                errors.append("restart_validation_failed")

        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "ok" if (healthy and not errors) else "blocked",
            "action": action,
            "healthy": healthy,
            "endpoint": {"host": HOST, "port": PORT, "listening_before": listening_before, "listening_after": listening_after},
            "pids_before": pids_before,
            "pids_after": pids_after,
            "pid_file": rel(pid_file),
            "collector_executable": {"path": rel(exe), "exists": exe.exists()},
            "collector_config": {
                "path": rel(config),
                "exists": config.exists(),
                "sha256": config_sha256(config),
                "mutated_by_this_script": False,
            },
            "data_freshness": freshness,
            "starvation": {
                "enabled": starvation_enabled,
                "threshold_hours": float(args.starvation_hours),
                "starving": starving,
                "note": "Alert-only: a listening collector is never restarted for starvation.",
            },
            "start_result": start_result,
            "planned_start_command": planned_start_command(exe, config),
            "restart_allowed_with_flag": True,
            "restart_performed": action == "restarted",
            "lock": lock_state,
            "consecutive_unhealthy_runs": consecutive,
            "errors": errors,
            "warnings": warnings,
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
        return payload
    finally:
        release_lock(lock)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local-only OTEL collector watchdog (detect, and recover only with --restart).")
    parser.add_argument("--collector-exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--collector-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--pid-file", type=Path, default=DEFAULT_PID_FILE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--restart", action="store_true", help="Start the collector when it is not listening.")
    parser.add_argument("--dry-run", action="store_true", help="Report the action that --restart would take without starting anything.")
    parser.add_argument("--print-plan", action="store_true", help="Print the exact start command and exit without touching runtime state.")
    parser.add_argument("--no-lock", action="store_true", help="Skip the single-flight lock (not recommended for scheduled runs).")
    parser.add_argument("--start-timeout-seconds", type=float, default=15.0)
    parser.add_argument(
        "--starvation-hours",
        type=float,
        default=2.0,
        help="Flag the collector when it listens but no file-exporter data has arrived for this many hours (0 disables).",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_plan:
        exe = args.collector_exe if args.collector_exe.is_absolute() else ROOT / args.collector_exe
        config = args.collector_config if args.collector_config.is_absolute() else ROOT / args.collector_config
        print(json.dumps(planned_start_command(exe, config), indent=2))
        return 0

    payload = build_payload(args)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, out)

    summary = (
        f"status={payload['status']} action={payload['action']} healthy={payload['healthy']} "
        f"listening={payload['endpoint']['listening_after']} pids={payload['pids_after']} "
        f"silent_hours={payload['data_freshness'].get('silent_hours')} starving={payload['starvation']['starving']}"
    )
    if payload.get("errors"):
        summary += " errors=" + ",".join(str(item) for item in payload["errors"])
    print(summary)
    if args.validate and payload["status"] != "ok":
        return 1
    if payload["action"] == "restart_failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
