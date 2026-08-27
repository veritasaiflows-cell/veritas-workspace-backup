#!/usr/bin/env python3
"""Fast scheduler launcher for the long post-close finance runner.

The full post-close chain can run longer than the isolated-agent shell envelope.
This launcher gives cron a quick, deterministic command while the existing
runner still owns the actual proof artifact.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "post-close-review-cron-launcher.json"
DEFAULT_RESULT = TMP / "post-close-review-cron-runner.json"
SCHEMA = "veritas.post_close_review_cron_launcher.v1"
DEFAULT_RECENT_SUCCESS_MINUTES = 45

AUTHORITY_BOUNDARY = {
    "review_only_launcher": True,
    "may_launch_existing_post_close_runner": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed_by_launcher": False,
    "capital_deployment_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now() -> str:
    return utc_now_dt().isoformat().replace("+00:00", "Z")


def new_launch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_post-close")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def recent_success_artifact(payload: dict[str, Any], now: datetime, max_age_minutes: int) -> bool:
    generated = parse_generated_at(payload.get("generated_at_utc"))
    if generated is None:
        return False
    age_seconds = (now - generated).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_minutes * 60:
        return False
    errors = as_dict(payload.get("validation")).get("errors")
    mode = as_dict(payload.get("mode"))
    terminal = as_dict(payload.get("terminal_completion"))
    status = payload.get("status")
    accepted_status_pair = (
        status == "ok"
        and terminal.get("run_chain_status") == "ok"
        and terminal.get("run_summary_status") == "ok"
    ) or (
        status == "completed_with_ticker_repairs"
        and terminal.get("run_chain_status") == "completed_with_ticker_repairs"
        and terminal.get("run_summary_status") == "warning"
    )
    return bool(
        errors in ([], None)
        and mode.get("skip_chain") is False
        and terminal.get("runner_executed_chain") is True
        and terminal.get("launch_id")
        and terminal.get("launch_id") == payload.get("launch_id")
        and terminal.get("run_summary_run_id")
        and accepted_status_pair
    )


def active_post_close_processes() -> list[dict[str, Any]]:
    ps = (
        "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*post_close_review_cron_runner.py*' "
        "-or $_.CommandLine -like '*run_finance_refresh_chain.py post-close*' } | "
        "Select-Object ProcessId,ParentProcessId,CommandLine,CreationDate | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    rows = parsed if isinstance(parsed, list) else [parsed]
    return [row for row in rows if isinstance(row, dict)]


def tail(text: str | None, limit: int = 1000) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def detached_creation_flags() -> int:
    flags = 0
    for name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
        flags |= int(getattr(subprocess, name, 0))
    return flags


def start_detached_process(command: list[str], stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            close_fds=True,
            creationflags=detached_creation_flags(),
        )
    return int(proc.pid)


def launch_runner(result_path: Path, launch_id: str | None = None) -> dict[str, Any]:
    launch_id = launch_id or new_launch_id()
    stdout_path = TMP / "post-close-review-cron-runner.launch.stdout.log"
    stderr_path = TMP / "post-close-review-cron-runner.launch.stderr.log"
    command = [
        sys.executable,
        str(SCRIPTS / "post_close_review_cron_runner.py"),
        "--write",
        "--validate",
        "--out",
        str(result_path),
        "--launch-id",
        launch_id,
    ]
    child_pid = start_detached_process(command, stdout_path, stderr_path)
    return {
        "pid": child_pid,
        "launch_id": launch_id,
        "command": command,
        "stdout": stdout_path.as_posix(),
        "stderr": stderr_path.as_posix(),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_mismatch")
    status = payload.get("status")
    if status not in {"already_running", "recent_success", "launched"}:
        errors.append(f"unexpected_status:{status}")
    if status == "launched" and not as_dict(payload.get("launch")).get("pid"):
        errors.append("launched_without_pid")
    if status == "already_running" and not payload.get("active_processes"):
        errors.append("already_running_without_process_rows")
    if status == "recent_success" and not as_dict(payload.get("result_artifact")).get("exists"):
        errors.append("recent_success_without_result_artifact")
    if status in {"already_running", "recent_success"}:
        warnings.append(status)
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(max_age_minutes: int, result_path: Path, previous_launcher: dict[str, Any] | None = None) -> dict[str, Any]:
    now = utc_now_dt()
    result = as_dict(load_json_artifact(result_path))
    result_generated = parse_generated_at(result.get("generated_at_utc"))
    active = active_post_close_processes()
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "launch_id": None,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "recent_success_window_minutes": max_age_minutes,
        "active_processes": active,
        "result_artifact": {
            "path": result_path.as_posix(),
            "exists": result_path.exists(),
            "status": result.get("status"),
            "validation_status": as_dict(result.get("validation")).get("status"),
            "generated_at_utc": result.get("generated_at_utc"),
            "launch_id": result.get("launch_id"),
            "skip_chain": as_dict(result.get("mode")).get("skip_chain"),
            "age_seconds": None if result_generated is None else round((now - result_generated).total_seconds(), 3),
        },
        "launch": None,
        "expected_result_artifact": result_path.as_posix(),
        "stop_lines": [
            "Launcher may only start the existing post_close_review_cron_runner.py.",
            "No schedule/config/auth/channel/canon/portfolio/trade/account mutation is performed by this launcher.",
        ],
    }
    if active:
        payload["status"] = "already_running"
        payload["launch_id"] = as_dict(previous_launcher).get("launch_id") or result.get("launch_id")
    elif recent_success_artifact(result, now, max_age_minutes):
        payload["status"] = "recent_success"
        payload["launch_id"] = result.get("launch_id")
    else:
        payload["launch_id"] = new_launch_id()
        payload["launch"] = launch_runner(result_path, payload["launch_id"])
        payload["status"] = "launched"
    payload["validation"] = validate(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch or deduplicate post-close finance runner for cron.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--recent-success-minutes", type=int, default=DEFAULT_RECENT_SUCCESS_MINUTES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    result = args.result if args.result.is_absolute() else ROOT / args.result
    previous = as_dict(load_json_artifact(out))
    payload = build_payload(args.recent_success_minutes, result, previous)
    if args.write:
        atomic_write_json(out, payload)
    print(
        f"launcher_status={payload['status']} validation={payload['validation']['status']} "
        f"child_pid={as_dict(payload.get('launch')).get('pid')}"
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
