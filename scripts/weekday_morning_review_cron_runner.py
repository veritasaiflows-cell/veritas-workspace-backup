#!/usr/bin/env python3
"""Compatibility runner for the weekday morning alerts-and-recommendations chain.

The enabled cron contract invokes the bounded chain directly. This entrypoint
remains as a fail-closed compatibility wrapper for manual or legacy callers;
it does not own schedules, ticker tiers, finance canon, or portfolio state.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_sql_canon_access import access as finance_sql_canon_access


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "weekday-morning-review-cron-runner.json"
DEFAULT_OBSERVER_OUT = TMP / "weekday-morning-review-cron-observer.json"
DEFAULT_LAUNCH_OUT = TMP / "weekday-morning-review-cron-launcher.json"
SCHEMA = "veritas.weekday_morning_review_cron_runner.v1"
LAUNCH_SCHEMA = "veritas.weekday_morning_review_cron_launcher.v1"
PROCESS_QUERY_TIMEOUT_SECONDS = 10

AUTHORITY_BOUNDARY = {
    "review_only_runner": True,
    "alerts_and_non_executing_recommendations_only": True,
    "finance_canon_mutation_allowed": False,
    "portfolio_state_mutation_allowed": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_launch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_morning")


def resolve_output_path(requested: Path | None, skip_chain: bool) -> Path:
    if skip_chain:
        return DEFAULT_OBSERVER_OUT
    path = requested or DEFAULT_OUT
    path = path if path.is_absolute() else ROOT / path
    return path


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive fail-closed runner guard
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def tail(text: str | None, limit: int = 1600) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def active_morning_processes() -> list[dict[str, Any]]:
    current_pid = os.getpid()
    script = """
$currentPid = %d
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
  Where-Object {
    $_.ProcessId -ne $currentPid -and (
      ($_.CommandLine -like '*weekday_morning_review_cron_runner.py*' -and $_.CommandLine -notlike '*--launch-background*') -or
      ($_.CommandLine -like '*run_alerts_recommendations_chain.py*' -and $_.CommandLine -like '*morning*')
    )
  } |
  Select-Object ProcessId,ParentProcessId,CommandLine,CreationDate |
  ConvertTo-Json -Compress -Depth 3
""" % current_pid
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=PROCESS_QUERY_TIMEOUT_SECONDS,
        )
    except Exception:
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    return [item for item in parsed if isinstance(item, dict)]


def chain_recently_running(max_age_seconds: int = 4 * 3600) -> bool:
    run_chain = TMP / "alerts-recommendations-chain-morning.json"
    payload = load(run_chain)
    if payload.get("status") != "running":
        return False
    try:
        age_seconds = time.time() - run_chain.stat().st_mtime
    except OSError:
        return False
    return age_seconds <= max_age_seconds


def start_detached_process(command: list[str], stdout_path: Path, stderr_path: Path) -> int:
    """Start the long runner without keeping the cron wrapper attached to it.

    The former PowerShell ``Start-Process`` hop could keep the launcher's
    process/pipe lifetime coupled to the child.  Use the native Windows
    process flags and explicit file handles instead, so the scheduler-facing
    launcher returns as soon as ``Popen`` has created the child.
    """
    creationflags = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    try:
        with stdout_path.open("ab") as stdout_handle, stderr_path.open("ab") as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                close_fds=True,
                creationflags=creationflags,
            )
    except OSError as exc:
        raise RuntimeError(f"unable to launch detached weekday morning runner: {exc}") from exc
    return process.pid


def launch_background(skip_chain: bool, out: Path, launch_out: Path) -> dict[str, Any]:
    stdout_path = TMP / "weekday-morning-review-cron-runner.background.out.txt"
    stderr_path = TMP / "weekday-morning-review-cron-runner.background.err.txt"
    active_processes = active_morning_processes()
    stale_running_artifact = chain_recently_running() and not active_processes
    if active_processes:
        previous = load(launch_out)
        payload = {
            "schema": LAUNCH_SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "already_running",
            "operator_action": "MAIN_SESSION_REQUIRED",
            "mode": {"skip_chain": skip_chain},
            "launch_id": previous.get("launch_id"),
            "child_pid": None,
            "active_processes": active_processes,
            "stale_running_artifact": False,
            "expected_result_artifact": rel(out),
            "authority_boundary": AUTHORITY_BOUNDARY,
            "stop_lines": [
                "Launcher detected a recent running weekday morning chain and did not start a duplicate.",
                "No trade/account action, paper/live execution, money movement, execution approval, or owner approval inference.",
            ],
        }
        atomic_write_json(launch_out, payload)
        return payload

    launch_id = new_launch_id()
    command = [sys.executable, str(Path(__file__).resolve()), "--write", "--validate", "--out", str(out), "--launch-id", launch_id]
    if skip_chain:
        command.append("--skip-chain")
    try:
        child_pid = start_detached_process(command, stdout_path, stderr_path)
    except RuntimeError as exc:
        payload = {
            "schema": LAUNCH_SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "launch_failed",
            "operator_action": "BLOCKED",
            "mode": {"skip_chain": skip_chain},
            "launch_id": launch_id,
            "child_pid": None,
            "child_command": command,
            "error": str(exc),
            "active_processes": [],
            "stale_running_artifact": stale_running_artifact,
            "expected_result_artifact": rel(out),
            "authority_boundary": AUTHORITY_BOUNDARY,
            "stop_lines": [
                "Launcher failed before starting the existing approved weekday morning runner.",
                "No trade/account action, paper/live execution, money movement, execution approval, or owner approval inference.",
            ],
        }
        atomic_write_json(launch_out, payload)
        return payload
    payload = {
        "schema": LAUNCH_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "launched_after_stale_running_artifact" if stale_running_artifact else "launched",
        "operator_action": "MAIN_SESSION_REQUIRED" if stale_running_artifact else "NO_REPLY",
        "mode": {"skip_chain": skip_chain},
        "launch_id": launch_id,
        "child_pid": child_pid,
        "child_command": command,
        "child_stdout": rel(stdout_path),
        "child_stderr": rel(stderr_path),
        "active_processes": [],
        "stale_running_artifact": stale_running_artifact,
        "expected_result_artifact": rel(out),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Launcher only starts the existing approved morning runner in the background.",
            "No trade/account action, paper/live execution, money movement, execution approval, or owner approval inference.",
        ],
    }
    atomic_write_json(launch_out, payload)
    return payload


def build_steps(skip_chain: bool) -> list[tuple[str, list[str], int]]:
    if skip_chain:
        return []
    return [
        (
            "morning_alerts_recommendations_chain",
            [sys.executable, "scripts\\run_alerts_recommendations_chain.py", "morning", "--write", "--validate"],
            2700,
        ),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 240),
    ]


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(full)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status") or payload.get("overall"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "summary": payload.get("summary"),
        "authority": payload.get("authority_boundary") or payload.get("authority"),
    }


def build_summary() -> dict[str, Any]:
    run_chain = load(TMP / "alerts-recommendations-chain-morning.json")
    alert_levels = load(TMP / "alert-level-freshness-controller.json")
    digest = load(TMP / "finance-alert-os-morning-digest.json")
    sql_health = sql_canon_health()
    chain_validation = as_dict(run_chain.get("validation"))
    return {
        "run_chain_status": run_chain.get("status"),
        "run_chain_validation_status": chain_validation.get("status"),
        "run_chain_generated_at_utc": run_chain.get("generated_at_utc"),
        "run_chain_critical_errors": as_list(as_dict(run_chain.get("summary")).get("critical_errors")),
        "run_chain_warnings": as_list(as_dict(run_chain.get("summary")).get("warnings")),
        "run_chain_retired_stage_hits": as_list(as_dict(run_chain.get("summary")).get("retired_stage_hits")),
        "run_chain_authority": as_dict(run_chain.get("authority")),
        "alert_level_status": alert_levels.get("status"),
        "alert_level_validation_status": as_dict(alert_levels.get("validation")).get("status"),
        "digest_status": digest.get("status"),
        "digest_validation_status": as_dict(digest.get("validation")).get("status"),
        "sql_canon_status": sql_health.get("status"),
        "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
        "sql_canon_health": sql_health,
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed_steps = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed_steps:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed_steps)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("run_chain_status") != "ok":
        errors.append(f"run_chain_status:{summary.get('run_chain_status')}")
    if summary.get("run_chain_validation_status") != "ok":
        errors.append(f"run_chain_validation_status:{summary.get('run_chain_validation_status')}")
    critical_errors = as_list(summary.get("run_chain_critical_errors"))
    if critical_errors:
        errors.append(f"run_chain_critical_errors:{','.join(str(item) for item in critical_errors)}")
    retired_hits = as_list(summary.get("run_chain_retired_stage_hits"))
    if retired_hits:
        errors.append(f"run_chain_retired_stage_hits:{','.join(str(item) for item in retired_hits)}")
    if summary.get("alert_level_status") != "ok" or summary.get("alert_level_validation_status") != "ok":
        errors.append("alert_level_freshness_not_ok")
    if summary.get("digest_status") != "ok" or summary.get("digest_validation_status") != "ok":
        errors.append("recommendation_digest_not_ok")

    chain_authority = as_dict(summary.get("run_chain_authority"))
    for key in (
        "writes_finance_canon",
        "maintains_portfolio_state",
        "maintains_simulated_account_state",
        "capital_or_order_authority",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        if chain_authority.get(key) is not False:
            errors.append(f"run_chain_authority_{key}_not_false")
    sql_health = as_dict(summary.get("sql_canon_health"))
    if sql_health.get("status") != "ok":
        errors.append(f"sql_canon_guard_blocked:{sql_health.get('status')}")
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            errors.append(f"sql_canon_authority_{key}_not_false")

    chain_warnings = as_list(summary.get("run_chain_warnings"))
    if chain_warnings:
        warnings.append(f"run_chain_warnings:{','.join(str(item) for item in chain_warnings)}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(steps: list[dict[str, Any]], skip_chain: bool, launch_id: str | None = None) -> dict[str, Any]:
    summary = build_summary()
    chain_generated_at = summary.get("run_chain_generated_at_utc")
    compatibility_run_id = f"alerts-recommendations:morning:{chain_generated_at}" if chain_generated_at else None
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "mode": {"skip_chain": skip_chain},
        "launch_id": launch_id,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "terminal_completion": {
            "window": "morning",
            "launch_id": launch_id,
            "runner_executed_chain": not skip_chain,
            "run_chain_status": summary.get("run_chain_status"),
            "run_chain_validation_status": summary.get("run_chain_validation_status"),
            "run_chain_generated_at_utc": chain_generated_at,
            "run_chain_started_at_utc": chain_generated_at,
            "run_chain_completed_at_utc": chain_generated_at,
            "run_summary_status": summary.get("run_chain_validation_status"),
            "run_summary_run_id": compatibility_run_id,
            "run_summary_generated_at_utc": chain_generated_at,
        },
        "steps": steps,
        "artifacts": [
            artifact("tmp/alerts-recommendations-chain-morning.json"),
            artifact("tmp/alert-level-freshness-controller.json"),
            artifact("tmp/finance-alert-os-morning-digest.json"),
            artifact("tmp/finance-sql-canon-access-validation.json"),
        ],
        "stop_lines": [
            "The compatibility runner may execute only the bounded morning alerts-and-recommendations chain and existing local cron ledger proof.",
            "No trade/account action, paper/live execution, money movement, execution approval, or owner approval inference.",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = (
        "blocked" if validation["errors"]
        else "warning" if validation["warnings"]
        else "ok"
    )
    payload["operator_action"] = (
        "BLOCKED" if validation["errors"]
        else "MAIN_SESSION_REQUIRED" if validation["warnings"] else "NO_REPLY"
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and classify weekday morning alerts-and-recommendations proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-chain", action="store_true", help="Do not run the morning chain; classify current artifacts only.")
    parser.add_argument("--launch-background", action="store_true", help="Launch the runner in a background process and return immediately.")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--launch-out", type=Path, default=DEFAULT_LAUNCH_OUT)
    parser.add_argument("--launch-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = resolve_output_path(args.out, args.skip_chain)
    if args.launch_background:
        launch_out = args.launch_out if args.launch_out.is_absolute() else ROOT / args.launch_out
        payload = launch_background(args.skip_chain, out, launch_out)
        print(
            f"status={payload['status']} operator_action={payload['operator_action']} "
            f"child_pid={payload['child_pid']} expected={payload['expected_result_artifact']}"
        )
        return 0
    steps = [run_step(name, command, timeout) for name, command, timeout in build_steps(args.skip_chain)]
    payload = build_payload(steps, args.skip_chain, args.launch_id)
    if args.write:
        atomic_write_json(out, payload)
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"operator_action={payload['operator_action']} run_chain={summary.get('run_chain_status')} "
        f"alert_levels={summary.get('alert_level_status')} digest={summary.get('digest_status')}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
