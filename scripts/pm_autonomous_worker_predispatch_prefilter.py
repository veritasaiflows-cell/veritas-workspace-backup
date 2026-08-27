#!/usr/bin/env python3
"""Predispatch changed-input gate for the PM autonomous implementation worker.

This wrapper is designed to run before any model-backed cron agent turn. It
reuses the PM worker's existing input signature and quiet/no-action reuse rule,
then writes a small proof packet when the worker can be skipped safely.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pm_job_worker_runner as worker

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.pm_autonomous_worker_predispatch_prefilter.v1"
JOB_NAME = "PM - Autonomous Implementation Proof Worker"
OUT = TMP / "pm-autonomous-worker-predispatch-prefilter.json"
PROPOSAL_OUT = TMP / "pm-autonomous-worker-predispatch-prefilter-proposal.json"
LIVE_CRON = TMP / "cron-list-live-current.json"
WORKER_OUT = TMP / "pm-job-worker-runner.json"

EXISTING_WORKER_COMMAND = (
    "python scripts\\pm_job_worker_runner.py "
    "--refresh-frontdoors --execute --verify --write --validate"
)
PROPOSED_COMMAND = (
    "python scripts\\pm_autonomous_worker_predispatch_prefilter.py "
    "--execute --write --validate"
)
PROPOSED_SINGLE_LINE_MESSAGE = (
    "Work in C:\\Users\\Veritas\\.openclaw\\workspace. "
    "Objective: advance PM implementation work autonomously within phase-1 safety boundaries "
    "by running the PM autonomy worker once. "
    f"Execute exactly this single command: {PROPOSED_COMMAND}. "
    "Do not run any other commands; do not inspect unrelated files manually; do not patch code; "
    "do not spawn helpers; do not mutate cron schedule/config/runtime, finance canon/portfolio, "
    "SQL imports, customer/external surfaces, paper/live/account/brokerage state, capital deployment, "
    "money movement, or approval state. "
    "Response contract: reply exactly NO_REPLY if the command exits 0; if blocked, report only worker "
    "status, selected job, validation errors, and proof paths tmp\\pm-job-worker-runner.json, "
    "tmp\\pm-autonomy-dispatcher.json, tmp\\pm-autonomy-verifier.json, "
    "tmp\\pm-main-session-action-inbox.json."
)

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "prefilter_proof_only": True,
    "may_execute_existing_worker_when_changed": True,
    "patches_code": False,
    "spawns_helpers": False,
    "cron_schedule_mutation_allowed": False,
    "cron_payload_mutation_allowed": False,
    "model_route_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def find_live_cron_job(payload: Any, job_name: str = JOB_NAME) -> dict[str, Any]:
    if isinstance(payload, dict):
        if payload.get("name") == job_name:
            return payload
        for value in payload.values():
            found = find_live_cron_job(value, job_name)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_live_cron_job(value, job_name)
            if found:
                return found
    return {}


def current_cron_message(job: dict[str, Any]) -> str:
    return str(as_dict(job.get("payload")).get("message") or "")


def proposed_single_line_message() -> str:
    return " ".join(PROPOSED_SINGLE_LINE_MESSAGE.split())


def build_promotion_proposal(
    *,
    live_cron_path: Path = LIVE_CRON,
    job_name: str = JOB_NAME,
) -> dict[str, Any]:
    live = load_json(live_cron_path, {})
    job = find_live_cron_job(live, job_name)
    payload = as_dict(job.get("payload"))
    message = current_cron_message(job)
    current_command_found = EXISTING_WORKER_COMMAND in message
    proposed_command_found = PROPOSED_COMMAND in message
    proposed_message = proposed_single_line_message() if job else ""
    proposed_payload = dict(payload)
    if proposed_message:
        proposed_payload["message"] = proposed_message
    if job and proposed_command_found:
        status = "already_promoted"
    elif job and current_command_found:
        status = "proposal_ready"
    else:
        status = "proposal_warning"
    return {
        "schema": f"{SCHEMA}.proposal",
        "generated_at_utc": utc_now(),
        "status": status,
        "job_name": job_name,
        "job_id": job.get("id"),
        "source_artifact": rel(live_cron_path),
        "live_job_present": bool(job),
        "current_payload_kind": payload.get("kind"),
        "current_model": payload.get("model"),
        "current_thinking": payload.get("thinking"),
        "current_timeout_seconds": payload.get("timeoutSeconds"),
        "current_command_found": current_command_found,
        "proposed_command_found": proposed_command_found,
        "current_command": EXISTING_WORKER_COMMAND,
        "proposed_command": PROPOSED_COMMAND,
        "proposed_payload": proposed_payload if proposed_message else {},
        "proposal_shape": {
            "single_line_payload": "\n" not in proposed_message and "\r" not in proposed_message,
            "multiline_payload_avoided": True,
            "proposed_message_length": len(proposed_message),
        },
        "promotion_effect": {
            "message_level_wrapper": True,
            "skips_worker_when_inputs_unchanged": True,
            "eliminates_scheduled_agent_turn": False,
            "agent_turn_to_command_migration_required_for_full_api_savings": True,
            "note": "This safe proposal swaps the worker command inside the existing agentTurn payload. It reduces repeated PM worker/proof work but does not remove the scheduled model turn by itself.",
        },
        "apply_status": "not_applied",
        "required_next_gate": "explicit cron payload promotion approval plus cron patch manager/contract validation",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "This proposal does not edit cron.",
            "No cron schedule, model route, runtime config, finance/canon, portfolio, paper/live/account, or external action is authorized by this packet.",
        ],
    }


def execute_worker(timeout_seconds: int) -> dict[str, Any]:
    started = utc_now()
    command = [
        sys.executable,
        "scripts\\pm_job_worker_runner.py",
        "--refresh-frontdoors",
        "--execute",
        "--verify",
        "--write",
        "--validate",
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        return {
            "name": "pm_job_worker_runner",
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
            "name": "pm_job_worker_runner",
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout_seconds,
            "stdout_preview": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    input_signature = worker.build_input_signature("cron")
    worker_prefilter = worker.prefilter_decision(WORKER_OUT, input_signature)
    proposal = build_promotion_proposal()
    can_skip = bool(worker_prefilter.get("can_reuse_existing_packet"))
    worker_step: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if can_skip:
        status = "skipped_unchanged"
        action = "skip_worker"
        info.append("existing_worker_packet_reused")
    elif args.prefilter_only or not args.execute:
        status = "run_required"
        action = "run_worker_when_promoted"
        info.append("changed_or_unproven_inputs_require_worker")
    else:
        worker_step = execute_worker(args.timeout_seconds)
        if worker_step.get("ok"):
            status = "worker_executed"
            action = "worker_executed"
        else:
            status = "blocked"
            action = "worker_failed"
            errors.append("pm_job_worker_runner_failed")

    if proposal.get("status") != "proposal_ready":
        if proposal.get("status") == "already_promoted":
            info.append("promotion_proposal_already_live")
        else:
            warnings.append("promotion_proposal_not_ready")

    validation_status = "blocked" if errors else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "prefilter_only" if args.prefilter_only else "execute" if args.execute else "dry_run",
        "job_name": JOB_NAME,
        "purpose": "Skip the PM autonomous implementation worker before model-backed cron dispatch when inputs are unchanged and prior quiet proof is fresh.",
        "action": action,
        "would_spawn_model_or_agent_turn": False if can_skip else None,
        "would_run_existing_worker": False if can_skip else True,
        "input_signature": input_signature,
        "worker_prefilter": worker_prefilter,
        "worker_step": worker_step,
        "promotion_proposal_path": rel(PROPOSAL_OUT),
        "source_artifacts": {
            "worker_packet": rel(WORKER_OUT),
            "live_cron_inventory": rel(LIVE_CRON),
            "promotion_proposal": rel(PROPOSAL_OUT),
        },
        "validation": {
            "status": validation_status,
            "errors": errors,
            "warnings": warnings,
            "info": info,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "This wrapper does not mutate the live cron schedule or payload.",
            "Promotion into the live cron payload requires explicit cron-payload approval and cron patch validation.",
            "No finance/canon, portfolio, paper/live/account, external, runtime config, model-route, or owner-approval mutation is authorized.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run the existing PM worker when changed inputs require it.")
    parser.add_argument("--prefilter-only", action="store_true", help="Only decide skip/run-required; never run the PM worker.")
    parser.add_argument("--write", action="store_true", help="Write proof and promotion proposal JSON.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero only for blocked validation.")
    parser.add_argument("--pretty", action="store_true", help="Print full JSON report.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--proposal-out", type=Path, default=PROPOSAL_OUT)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global PROPOSAL_OUT
    PROPOSAL_OUT = args.proposal_out

    report = build_report(args)
    proposal = build_promotion_proposal()
    if args.write:
        atomic_write_json(args.out, report)
        atomic_write_json(args.proposal_out, proposal)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"action={report['action']} validation={report['validation']['status']}"
        )
    if args.pretty or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
