#!/usr/bin/env python3
"""Verify PM autonomy worker output and refresh user-facing status surfaces."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from pm_autonomy_policy import DEFAULT_POLICY_PATH, load_policy, validate_policy

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DISPATCHER = TMP / "pm-autonomy-dispatcher.json"
WORKER = TMP / "pm-job-worker-runner.json"
PM_EXECUTION = TMP / "pm-execution-loop.json"
OUT = TMP / "pm-autonomy-verifier.json"

SCHEMA = "veritas.pm_autonomy_verifier.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "verifies_worker_output": True,
    "refreshes_status_packets": True,
    "patches_code": False,
    "spawns_helpers": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return as_dict(load_json_artifact(path))


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-1800:],
            "stderr_preview": proc.stderr.strip()[-1000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-1800:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1000:] if isinstance(exc.stderr, str) else "",
        }


def refresh_status_packets(*, include_future_session: bool = False) -> list[dict[str, Any]]:
    steps = [
        ("pm_control_packet", [sys.executable, "scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 300),
    ]
    if include_future_session:
        steps.append((
            "future_session_enhancement_packet",
            [sys.executable, "scripts\\future_session_enhancement_packet.py", "--write", "--validate"],
            180,
        ))
    steps.extend([
        ("startup_brief_packet", [sys.executable, "scripts\\startup_brief_packet.py", "--write", "--validate"], 120),
        ("status_card_packet", [sys.executable, "scripts\\status_card_packet.py", "--write", "--validate"], 120),
    ])
    return [run_step(name, command, timeout) for name, command, timeout in steps]


def verification_state(
    *,
    action_type: str,
    dispatcher_selected_job: Any,
    worker_selected_job: Any,
    worker_summary: dict[str, Any],
    worker: dict[str, Any],
    pm_execution: dict[str, Any],
    refresh_results: list[dict[str, Any]],
) -> dict[str, Any]:
    worker_state = as_dict(worker.get("worker_state") or worker_summary.get("worker_state"))
    execution_state = as_dict(pm_execution.get("worker_state"))
    selected_job_id = dispatcher_selected_job or worker_selected_job
    refresh_ok = bool(refresh_results) and all(row.get("ok") for row in refresh_results)
    return {
        "candidate_selected": bool(selected_job_id),
        "selected_job_id": selected_job_id,
        "lane_prepared": worker_state.get("lane_prepared") is True,
        "proof_executed": worker_state.get("proof_executed") is True or execution_state.get("proof_executed") is True,
        "closeout_executed": worker_state.get("closeout_executed") is True or execution_state.get("closeout_executed") is True,
        "closeout_ledgered": worker_state.get("closeout_ledgered") is True or execution_state.get("closeout_ledgered") is True,
        "frontdoors_refreshed": refresh_ok,
        "job_resolved_or_completed": worker_state.get("job_resolved_or_completed") is True or execution_state.get("job_resolved_or_completed") is True,
        "terminal_state": (
            "resolved_and_refreshed"
            if (worker_state.get("job_resolved_or_completed") is True or execution_state.get("job_resolved_or_completed") is True) and refresh_ok
            else "plan_waiting_for_main"
            if action_type == "prepare_implementation_plan"
            else "no_unattended_safe_job"
            if action_type == "no_action"
            else "proof_verified_refresh_pending"
            if worker_state.get("proof_executed") is True or execution_state.get("proof_executed") is True
            else "verification_pending"
        ),
    }


def classify_refresh_failures(action_type: str, refresh_results: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    failures = [str(step.get("name")) for step in refresh_results if not step.get("ok")]
    if (
        str(action_type or "") == "no_action"
        and failures
        and set(failures).issubset({"startup_brief_packet", "status_card_packet"})
    ):
        return [], ["status_packet_refresh_validation_residue"]
    return [f"refresh_failed:{name}" for name in failures], []


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    dispatcher = load(args.dispatcher)
    worker = load(args.worker)
    pm_execution = load(PM_EXECUTION)
    worker_summary = as_dict(worker.get("summary"))
    dispatcher_summary = as_dict(dispatcher.get("summary"))
    executed = bool(worker_summary.get("executed"))
    policy = load_policy(args.policy)
    policy_validation = validate_policy(policy)
    include_future_session = bool(args.refresh_future_session or (args.refresh_status and executed))
    refresh_results = refresh_status_packets(include_future_session=include_future_session) if args.refresh_status else []
    action_type = dispatcher_summary.get("selected_action_type") or as_dict(worker.get("dispatch")).get("action_type")
    dispatcher_selected_job = dispatcher_summary.get("selected_job_id")
    worker_selected_job = worker_summary.get("selected_job_id")

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    if policy_validation["status"] != "ok":
        errors.extend([f"policy:{item}" for item in policy_validation["errors"]])
    if worker.get("authority_boundary") != AUTHORITY_BOUNDARY and as_dict(worker.get("authority_boundary")).get("patches_code") is not False:
        errors.append("worker_authority_boundary")
    if worker.get("status") == "blocked":
        errors.append("worker_blocked")
    if executed and pm_execution.get("status") != "ok":
        errors.append("pm_execution_loop_not_ok")
    if action_type == "no_action":
        info.append("no_action_verified")
    if action_type == "prepare_implementation_plan":
        warnings.append("implementation_plan_waiting_for_main_or_helper")
    refresh_errors, refresh_warnings = classify_refresh_failures(str(action_type or ""), refresh_results)
    errors.extend(refresh_errors)
    warnings.extend(refresh_warnings)
    if executed and dispatcher_selected_job and worker_selected_job and dispatcher_selected_job != worker_selected_job:
        warnings.append("dispatcher_worker_selection_mismatch_next_job_pending")
    state = verification_state(
        action_type=str(action_type or ""),
        dispatcher_selected_job=dispatcher_selected_job,
        worker_selected_job=worker_selected_job,
        worker_summary=worker_summary,
        worker=worker,
        pm_execution=pm_execution,
        refresh_results=refresh_results,
    )

    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "warning" if warnings else "quiet_success" if action_type == "no_action" else "ok",
        "purpose": "Verify scheduled PM autonomy output and refresh PM/startup/status surfaces.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "policy": rel(args.policy),
            "dispatcher": rel(args.dispatcher),
            "worker": rel(args.worker),
            "pm_execution_loop": rel(PM_EXECUTION),
        },
        "summary": {
            "dispatcher_status": dispatcher.get("status"),
            "worker_status": worker.get("status"),
            "action_type": action_type,
            "selected_job_id": dispatcher_selected_job or worker_selected_job,
            "worker_selected_job_id": worker_selected_job,
            "executed": executed,
            "pm_execution_loop_status": pm_execution.get("status"),
            "refresh_status_packets_ran": bool(refresh_results),
            "future_session_refresh_ran": any(step.get("name") == "future_session_enhancement_packet" for step in refresh_results),
            "refresh_failures": [step.get("name") for step in refresh_results if not step.get("ok")],
            "verification_state": state,
            "next_action": (
                "Review blocked verifier errors."
                if errors
                else "Main/helper implementation is needed; unattended worker only prepared the plan."
                if action_type == "prepare_implementation_plan"
                else "No unattended-safe PM job was available."
                if action_type == "no_action"
                else "Autonomous proof refresh verified and status packets refreshed."
            ),
        },
        "verification_state": state,
        "refresh_results": refresh_results,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings, "info": info},
        "stop_lines": [
            "Verifier refreshes proof/status only. No code patch, helper spawn, cron mutation, config/runtime change, finance/canon/customer/external/account/trading action, or owner approval inference.",
        ],
    }
    return report


def health_check(report: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(report.get("validation"))
    errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
    warnings = validation.get("warnings") if isinstance(validation.get("warnings"), list) else []
    return {
        "schema": "pm_autonomy_verifier_health_check_v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "degraded" if warnings else "clean",
        "verifier_status": report.get("status"),
        "action_type": as_dict(report.get("summary")).get("action_type"),
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify scheduled PM autonomy output.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--refresh-status", action="store_true")
    parser.add_argument("--refresh-future-session", action="store_true", help="Refresh the future-session pickup packet before startup/status. Automatically enabled after executed work when --refresh-status is used.")
    parser.add_argument("--health-check", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--dispatcher", type=Path, default=DISPATCHER)
    parser.add_argument("--worker", type=Path, default=WORKER)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report(args)
    if args.health_check:
        health = health_check(report)
        print(json.dumps(health, indent=2, sort_keys=True))
        return 1 if args.validate and health["status"] == "blocked" else 0
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"action={report['summary']['action_type']} selected={report['summary']['selected_job_id']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
