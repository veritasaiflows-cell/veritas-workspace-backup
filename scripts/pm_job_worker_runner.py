#!/usr/bin/env python3
"""Scheduled PM autonomy worker.

Phase 1 runs only unattended-safe proof refreshes and planning handoffs. It uses
the dispatcher for selection and the verifier for closeout/status refresh.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DISPATCHER = TMP / "pm-autonomy-dispatcher.json"
OUT = TMP / "pm-job-worker-runner.json"
PM_QUEUE = TMP / "pm-implementation-job-queue.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
PM_POLICY = ROOT / "state" / "pm-autonomy-policy.json"
PREFILTER_MAX_AGE_HOURS = 8.0

SCHEMA = "veritas.pm_job_worker_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runs_proof_refresh": True,
    "prepares_implementation_plan": True,
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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_file_state(label: str, path: Path) -> dict[str, Any]:
    return {
        "label": label,
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
    }


def active_collision_groups(register: dict[str, Any]) -> list[str]:
    groups: set[str] = set()
    for lane in as_list(register.get("lanes")):
        row = as_dict(lane)
        if row.get("status") not in {"planned", "leased", "running"}:
            continue
        for key in ("collision_group", "workstream_id", "workflow_id"):
            value = row.get(key)
            if value:
                groups.add(str(value))
    return sorted(groups)


def lane_register_collision_state(path: Path = LANE_REGISTER) -> dict[str, Any]:
    register = load(path)
    groups = active_collision_groups(register)
    body = json.dumps(groups, sort_keys=True, separators=(",", ":"))
    return {
        "label": "lane_register_active_collision_groups",
        "path": rel(path),
        "exists": path.exists(),
        "group_count": len(groups),
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "groups": groups,
    }


def build_input_signature(execution_context: str = "cron") -> dict[str, Any]:
    sources = [
        {
            "label": "execution_context",
            "exists": True,
            "sha256": hashlib.sha256(execution_context.encode("utf-8")).hexdigest(),
            "context": execution_context,
        },
        source_file_state("pm_queue", PM_QUEUE),
        lane_register_collision_state(LANE_REGISTER),
        source_file_state("pm_autonomy_policy", PM_POLICY),
        source_file_state("producer:pm_job_worker_runner", Path(__file__).resolve()),
        source_file_state("producer:pm_autonomy_dispatcher", ROOT / "scripts" / "pm_autonomy_dispatcher.py"),
    ]
    body = json.dumps(sources, sort_keys=True, separators=(",", ":"))
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "source_count": len(sources),
        "sources": sources,
    }


def generated_age_hours(value: Any, now: datetime | None = None) -> float | None:
    if not value:
        return None
    now = now or datetime.now(timezone.utc)
    try:
        generated = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (now - generated).total_seconds() / 3600


def prefilter_decision(out: Path, current_signature: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    previous = as_dict(load_json_artifact(out))
    previous_signature = as_dict(previous.get("input_signature"))
    previous_validation = as_dict(previous.get("validation"))
    previous_summary = as_dict(previous.get("summary"))
    previous_age = generated_age_hours(previous.get("generated_at_utc"), now)
    source_unchanged = bool(
        previous_signature.get("hash")
        and previous_signature.get("hash") == current_signature.get("hash")
    )
    previous_fresh = previous_age is not None and previous_age <= PREFILTER_MAX_AGE_HOURS
    previous_no_action = (
        previous.get("status") == "quiet_success"
        and previous_summary.get("action_type") == "no_action"
        and previous_validation.get("status") == "ok"
    )
    can_reuse = source_unchanged and previous_fresh and previous_no_action
    if not previous:
        reason = "missing_previous_packet"
    elif not previous_signature.get("hash"):
        reason = "missing_previous_input_signature"
    elif not source_unchanged:
        reason = "source_signature_changed"
    elif not previous_fresh:
        reason = "previous_packet_not_fresh"
    elif not previous_no_action:
        reason = "previous_packet_not_quiet_no_action"
    else:
        reason = "unchanged_inputs_and_fresh_no_action"
    return {
        "status": "reuse_existing_packet" if can_reuse else "refresh_required",
        "can_reuse_existing_packet": can_reuse,
        "reason": reason,
        "source_unchanged": source_unchanged,
        "previous_packet_exists": bool(previous),
        "previous_generated_at_utc": previous.get("generated_at_utc"),
        "previous_age_hours": round(previous_age, 3) if previous_age is not None else None,
        "max_age_hours": PREFILTER_MAX_AGE_HOURS,
        "previous_status": previous.get("status"),
        "previous_validation_status": previous_validation.get("status"),
        "previous_action_type": previous_summary.get("action_type"),
        "previous_input_hash": previous_signature.get("hash"),
        "current_input_hash": current_signature.get("hash"),
        "meaning": "Reuse is allowed only when PM inputs are unchanged, the previous worker packet is fresh, and the prior action was quiet no-action.",
    }


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
            "stdout_preview": proc.stdout.strip()[-2000:],
            "stderr_preview": proc.stderr.strip()[-1200:],
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
            "stdout_preview": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def refresh_frontdoors() -> list[dict[str, Any]]:
    return [
        run_step("pm_control_packet", [sys.executable, "scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 300),
        run_step("pm_implementation_job_queue", [sys.executable, "scripts\\pm_implementation_job_queue.py", "--write", "--write-db", "--validate"], 240),
    ]


def run_dispatcher(execution_context: str) -> dict[str, Any]:
    return run_step(
        "pm_autonomy_dispatcher",
        [
            sys.executable,
            "scripts\\pm_autonomy_dispatcher.py",
            "--write",
            "--validate",
            "--execution-context",
            execution_context,
        ],
        120,
    )


def run_pm_execution(job_id: str) -> dict[str, Any]:
    return run_step(
        "pm_execution_loop",
        [sys.executable, "scripts\\pm_execution_loop.py", "--execute", "--job", job_id, "--write", "--validate"],
        1200,
    )


def run_verifier() -> dict[str, Any]:
    return run_step(
        "pm_autonomy_verifier",
        [sys.executable, "scripts\\pm_autonomy_verifier.py", "--write", "--refresh-status", "--validate"],
        420,
    )


def implementation_plan_payload(selected_job: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.pm_implementation_plan_handoff.v1",
        "job_id": selected_job.get("job_id"),
        "title": selected_job.get("title"),
        "automation_class": selected_job.get("automation_class"),
        "recommended_executor": "main_or_main_spawned_helper",
        "target_files": selected_job.get("target_files") or [],
        "proof_commands": selected_job.get("proof_commands") or [],
        "next_action": "Main session should inspect this job, lease exact write surfaces if edits are needed, and spawn/execute a bounded helper. Cron does not patch code.",
        "stop_lines": [
            "No unattended code patch.",
            "No helper spawn from cron.",
            "No config/auth/runtime/canon/portfolio/external/account/trading action.",
        ],
    }


def worker_state(
    *,
    selected_job_id: str,
    action_type: str,
    executed: bool,
    implementation_plan: dict[str, Any],
    execution_results: list[dict[str, Any]],
    verifier_step: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pm_execution_payload = load(TMP / "pm-execution-loop.json")
    execution_state = as_dict(pm_execution_payload.get("worker_state"))
    execution_ok = bool(execution_results) and all(row.get("ok") for row in execution_results)
    verifier_ok = as_dict(verifier_step).get("ok") is True if verifier_step else False
    return {
        "candidate_selected": bool(selected_job_id),
        "selected_job_id": selected_job_id or None,
        "selected_action_type": action_type,
        "lane_prepared": bool(implementation_plan),
        "proof_executed": bool(executed and execution_results),
        "proof_ok": execution_ok and as_dict(execution_state).get("proof_ok") is not False,
        "closeout_executed": as_dict(execution_state).get("closeout_executed") is True,
        "closeout_ledgered": as_dict(execution_state).get("closeout_ledgered") is True,
        "frontdoors_refreshed": verifier_ok or as_dict(execution_state).get("frontdoors_refreshed") is True,
        "job_resolved_or_completed": as_dict(execution_state).get("job_resolved_or_completed") is True,
        "terminal_state": (
            "resolved"
            if as_dict(execution_state).get("job_resolved_or_completed") is True
            else "plan_prepared_for_main"
            if implementation_plan
            else "proof_execution_failed"
            if executed and not execution_ok
            else "proof_executed_waiting_for_verification"
            if executed
            else "no_unattended_safe_job"
            if action_type == "no_action"
            else "selected_not_executed"
        ),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    frontdoor_results = refresh_frontdoors() if args.refresh_frontdoors else []
    dispatcher_step = run_dispatcher(args.execution_context)
    dispatcher = load(DISPATCHER)
    action = as_dict(dispatcher.get("action"))
    selected = as_dict(action.get("selected_job"))
    action_type = str(action.get("action_type") or "no_action")
    selected_job_id = str(selected.get("job_id") or "")
    execution_results: list[dict[str, Any]] = []
    implementation_plan = {}
    executed = False

    if args.execute and action_type == "run_proof_refresh" and selected_job_id:
        execution_results.append(run_pm_execution(selected_job_id))
        executed = True
    elif action_type == "prepare_implementation_plan" and selected:
        implementation_plan = implementation_plan_payload(selected)

    worker_errors: list[str] = []
    worker_warnings: list[str] = []
    worker_info: list[str] = []
    if any(not step.get("ok") for step in frontdoor_results):
        worker_errors.extend([f"frontdoor_failed:{step.get('name')}" for step in frontdoor_results if not step.get("ok")])
    if not dispatcher_step.get("ok"):
        worker_errors.append("dispatcher_failed")
    if any(not step.get("ok") for step in execution_results):
        worker_errors.extend([f"execution_failed:{step.get('name')}" for step in execution_results if not step.get("ok")])
    if action_type == "no_action":
        worker_info.append("no_unattended_safe_job")
    if action_type == "prepare_implementation_plan":
        worker_warnings.append("implementation_plan_prepared_no_code_patch")
    if args.execution_context == "cron" and action_type == "run_proof_refresh":
        caps = as_dict(selected.get("automation_capabilities"))
        if caps.get("auto_cron_may_execute") is not True:
            worker_errors.append("cron_context_selected_non_cron_job")

    state = worker_state(
        selected_job_id=selected_job_id,
        action_type=action_type,
        executed=executed,
        implementation_plan=implementation_plan,
        execution_results=execution_results,
    )

    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if worker_errors else "warning" if worker_warnings else "quiet_success" if action_type == "no_action" else "ok",
        "mode": "execute" if args.execute else "dry_run",
        "purpose": "Scheduled PM worker for proof-refresh and implementation-plan autonomy.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "execution_context": args.execution_context,
        "source_artifacts": {
            "dispatcher": rel(DISPATCHER),
            "pm_execution_loop": "tmp/pm-execution-loop.json",
            "verifier": "tmp/pm-autonomy-verifier.json",
        },
        "summary": {
            "action_type": action_type,
            "automation_class": action.get("automation_class"),
            "selected_job_id": selected_job_id or None,
            "selected_title": selected.get("title"),
            "execution_context": args.execution_context,
            "executed": executed,
            "frontdoor_refresh_ran": bool(frontdoor_results),
            "frontdoor_failures": [step.get("name") for step in frontdoor_results if not step.get("ok")],
            "execution_failures": [step.get("name") for step in execution_results if not step.get("ok")],
            "implementation_plan_prepared": bool(implementation_plan),
            "worker_state": state,
            "next_action": (
                "Verifier should refresh PM/startup/status packets."
                if executed
                else "Main/helper implementation handoff is ready; unattended worker will not patch code."
                if implementation_plan
                else "No unattended-safe PM job was available."
            ),
        },
        "dispatch": action,
        "frontdoor_results": frontdoor_results,
        "dispatcher_step": dispatcher_step,
        "execution_results": execution_results,
        "implementation_plan": implementation_plan,
        "worker_state": state,
        "validation": {"status": "ok" if not worker_errors else "blocked", "errors": worker_errors, "warnings": worker_warnings, "info": worker_info},
        "stop_lines": [
            "Runs proof refresh or writes a plan only.",
            "No unattended code patch, helper spawn, cron mutation, config/runtime change, finance/canon/customer/external/account/trading action, or owner approval inference.",
        ],
    }
    if args.verify:
        atomic_write_json(args.out, report)
        verifier_step = run_verifier()
        report["verifier_step"] = verifier_step
        report["worker_state"] = worker_state(
            selected_job_id=selected_job_id,
            action_type=action_type,
            executed=executed,
            implementation_plan=implementation_plan,
            execution_results=execution_results,
            verifier_step=verifier_step,
        )
        report["summary"]["worker_state"] = report["worker_state"]
        if not verifier_step.get("ok"):
            report["status"] = "blocked"
            report["validation"]["status"] = "blocked"
            report["validation"]["errors"] = [*report["validation"]["errors"], "verifier_failed"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scheduled PM autonomy worker.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--refresh-frontdoors", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--prefilter-only", action="store_true", help="Check whether the existing quiet no-action packet can be reused.")
    parser.add_argument("--skip-if-unchanged", action="store_true", help="Compatibility flag; unchanged-input skip is now the default unless --force-refresh is used.")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass the changed-input prefilter and run the PM worker.")
    parser.add_argument("--execution-context", choices=("cron", "main"), default="cron")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    input_signature = build_input_signature(args.execution_context)
    prefilter = prefilter_decision(args.out, input_signature)
    if args.prefilter_only:
        print(
            f"status={prefilter['status']} can_reuse={prefilter['can_reuse_existing_packet']} "
            f"reason={prefilter['reason']} input_hash={prefilter['current_input_hash']}"
        )
        return 0
    if not args.force_refresh and prefilter.get("can_reuse_existing_packet"):
        print(
            f"status=unchanged_skip validation=ok reason={prefilter['reason']} "
            f"input_hash={prefilter['current_input_hash']}"
        )
        return 0

    report = build_report(args)
    report["input_signature"] = build_input_signature(args.execution_context)
    report["prefilter"] = prefilter
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} mode={report['mode']} "
            f"action={report['summary']['action_type']} selected={report['summary']['selected_job_id']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
