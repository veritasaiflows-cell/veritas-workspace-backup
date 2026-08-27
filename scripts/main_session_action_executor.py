#!/usr/bin/env python3
"""Main-session action executor for bounded cron/heartbeat pickup.

This is the thin action layer above cron control, greenkeeper, PM control, and
the parallel lane recommender. It chooses one safe action per run and can
execute only allowlisted proof/refresh work. It does not patch code, spawn
helpers, mutate finance canon/portfolio state, change cron/config/runtime, or
infer owner approval.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "main-session-action-executor.json"
LEDGER = ROOT / "state" / "main-session-action-executor-ledger.jsonl"
HEARTBEAT_OUT = TMP / "heartbeat-main-session-action-executor.json"

CRON_CONTROL = TMP / "cron-control-packet.json"
GREENKEEPER = TMP / "main-session-greenkeeper-controller.json"
ESCALATION_CONSUMER = TMP / "main-session-escalation-consumer.json"
PM_CONTROL = TMP / "pm-control-packet.json"
PARALLEL_RECOMMENDATION = TMP / "parallel-lane-recommendation.json"
PM_EXECUTION_LOOP = TMP / "pm-execution-loop.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
HANDOFF_FIRST_PROOF = TMP / "main-session-handoff-first-proof.json"
PRIORITY_HANDOFF = TMP / "main-session-priority-handoff.json"

SCHEMA = "veritas.main_session_action_executor.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runs_allowlisted_proof_commands": True,
    "executes_code_patches": False,
    "spawns_helpers": False,
    "helper_final_authority": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

PM_EXECUTION_CONTEXTS = {"main_session", "cron", "closeout", "manual"}
SOFT_FRONTDOOR_FAILURES = {"main_session_greenkeeper_controller", "parallel_lane_recommender"}

# This is deliberately narrower than the executor's generic proof-only
# boundary. Priority packets are handoffs, never execution instructions.
PRIORITY_AUTHORITY_BOUNDARY = {
    "review_only": True,
    "main_session_review_required": True,
    "heartbeat_may_execute": False,
    "heartbeat_may_spawn_helper": False,
    "heartbeat_may_lease_lane": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}
PRIORITY_DUE_WINDOWS = {"immediate", "next_main_session", "scheduled_monitoring"}


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


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


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
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
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
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def maybe_refresh_frontdoors(args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.refresh_frontdoors:
        return []
    escalation_consumer_cmd = [
        "scripts\\main_session_escalation_consumer.py",
        "--context",
        args.context,
        "--write",
        "--validate",
    ]
    if args.execute_safe and args.context != "heartbeat":
        escalation_consumer_cmd.insert(3, "--execute-safe")
        escalation_consumer_cmd.append("--append-ledger")
    greenkeeper_cmd = [
        "scripts\\main_session_greenkeeper_controller.py",
        "--refresh-frontdoors",
        "--write",
        "--validate",
    ]
    if args.execute_safe and args.context != "heartbeat":
        greenkeeper_cmd.insert(2, "--execute-safe")
        greenkeeper_cmd.append("--append-ledger")
    return [
        run_step("handoff_first_proof_gate", py_cmd("scripts\\handoff_first_proof_gate.py", "--write", "--validate"), 240),
        run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 240),
        run_step(
            "main_session_escalation_consumer",
            py_cmd(*escalation_consumer_cmd),
            1200,
        ),
        run_step(
            "main_session_greenkeeper_controller",
            py_cmd(*greenkeeper_cmd),
            900,
        ),
        run_step("pm_control_packet", py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 300),
        run_step("parallel_lane_recommender", py_cmd("scripts\\parallel_lane_recommender.py", "--write", "--validate"), 240),
    ]


def active_collision_groups(register: dict[str, Any]) -> set[str]:
    groups: set[str] = set()
    for lane in as_list(register.get("lanes")):
        row = as_dict(lane)
        if row.get("status") not in {"planned", "leased", "running"}:
            continue
        workstream = str(row.get("workstream_id") or "")
        workflow = str(row.get("workflow_id") or "")
        if workstream:
            groups.add(workstream)
        if workflow and workstream:
            groups.add(f"{workflow}::{workstream}")
    return groups


def queue_jobs(pm_control: dict[str, Any]) -> list[dict[str, Any]]:
    sections = as_dict(pm_control.get("sections"))
    queue = as_dict(sections.get("pm_implementation_job_queue"))
    return [as_dict(job) for job in as_list(queue.get("jobs"))]


def job_allowed_for_context(job: dict[str, Any], context: str) -> bool:
    caps = as_dict(job.get("automation_capabilities"))
    if context == "heartbeat":
        return caps.get("auto_heartbeat_may_execute") is True
    if context in {"cron", "closeout"}:
        return caps.get("auto_cron_may_execute") is True
    return caps.get("auto_main_may_execute") is True


def select_pm_job(jobs: list[dict[str, Any]], context: str, busy_groups: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    skipped: list[dict[str, Any]] = []
    ranked = sorted(jobs, key=lambda row: (int(row.get("rank") or 9999), -float(row.get("readiness_score") or 0)))
    for job in ranked:
        job_id = str(job.get("job_id") or "")
        group = str(job.get("collision_group") or "")
        caps = as_dict(job.get("automation_capabilities"))
        if job.get("status") != "ready_for_main_or_helper":
            skipped.append({"job_id": job_id, "reason": f"status={job.get('status')}"})
            continue
        if group and group in busy_groups:
            skipped.append({"job_id": job_id, "reason": f"collision_group_active:{group}"})
            continue
        if caps.get("owner_gate_required"):
            skipped.append({"job_id": job_id, "reason": "owner_gate_required"})
            continue
        if caps.get("unsafe_proof_commands"):
            skipped.append({"job_id": job_id, "reason": "unsafe_proof_commands", "commands": caps.get("unsafe_proof_commands")})
            continue
        if not job_allowed_for_context(job, context):
            skipped.append({"job_id": job_id, "reason": f"not_auto_executable_in_context:{context}"})
            continue
        return job, skipped
    return {}, skipped


def top_helper_candidate(parallel: dict[str, Any]) -> dict[str, Any]:
    recommendation = as_dict(parallel.get("recommendation"))
    top_candidate = as_dict(recommendation.get("top_candidate"))
    if top_candidate and as_dict(parallel.get("summary")).get("eligible_candidate_count"):
        return top_candidate
    if recommendation.get("eligible") is True:
        return recommendation
    for candidate in as_list(parallel.get("ranked_candidates")):
        row = as_dict(candidate)
        if row.get("eligible") is True:
            return row
    for candidate in as_list(parallel.get("candidates")):
        row = as_dict(candidate)
        if row.get("eligible") is True:
            return row
    return {}


def repeated_handoff_state(ledger_path: Path, selected_job_id: str | None) -> dict[str, Any]:
    if not selected_job_id or not ledger_path.exists():
        return {"selected_job_id": selected_job_id, "recent_same_job_count": 0}
    count = 0
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()[-12:]
    except OSError:
        lines = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        previous = as_dict(as_dict(row.get("summary")).get("selected_pm_job")).get("job_id")
        if previous == selected_job_id:
            count += 1
        else:
            break
    return {"selected_job_id": selected_job_id, "recent_same_job_count": count}


def build_helper_lane_packet(job: dict[str, Any], parallel: dict[str, Any]) -> dict[str, Any]:
    caps = as_dict(job.get("automation_capabilities"))
    helper_packet = as_dict(job.get("helper_packet"))
    candidate = top_helper_candidate(parallel)
    return {
        "status": "ready" if caps.get("helper_lane_allowed") else "not_allowed",
        "source": "pm_implementation_job_queue",
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "collision_group": job.get("collision_group"),
        "validation_budget": job.get("validation_budget"),
        "closeout_mode": job.get("closeout_mode"),
        "target_files": as_list(job.get("target_files")),
        "proof_commands": as_list(job.get("proof_commands")),
        "helper_packet": helper_packet,
        "parallel_candidate_available": bool(candidate),
        "parallel_candidate": candidate,
        "next_safe_action": (
            "Main session may spawn the helper using helper_packet, then verify proof and complete the lane."
            if caps.get("helper_lane_allowed")
            else "Main review required; helper lane not allowed by PM capability contract."
        ),
    }


def select_priority_handoff(priority_handoff: dict[str, Any]) -> dict[str, Any]:
    """Convert a review-only priority packet into a main-session handoff."""
    if not priority_handoff:
        return {}
    validation = as_dict(priority_handoff.get("validation"))
    selected = as_dict(priority_handoff.get("selected_item"))
    if priority_handoff.get("status") == "no_priority" and not selected:
        return {}
    boundary_invalid = (
        priority_handoff.get("authority_boundary") != PRIORITY_AUTHORITY_BOUNDARY
        or selected.get("authority_boundary") != PRIORITY_AUTHORITY_BOUNDARY
    )
    structure_invalid = (
        not str(selected.get("next_action") or "").strip()
        or not as_dict(selected.get("acceptance_proof")).get("artifact")
        or not str(selected.get("owner") or "").strip()
        or selected.get("due_window") not in PRIORITY_DUE_WINDOWS
    )
    if validation.get("status") != "ok" or boundary_invalid or structure_invalid:
        return {
            "action_type": "review_priority_handoff",
            "classification": "main_handoff",
            "reason": "Priority handoff validation is not clean; inspect its proof before generic PM work.",
            "selected_priority_item": {},
            "priority_handoff_invalid": True,
        }
    if priority_handoff.get("status") != "needs_main_review" or not selected:
        return {}
    # P2 is intentionally monitor-only.  It remains visible on the priority
    # handoff, but must not preempt a ready generic PM action or force a Main
    # disposition unless its source escalates it to P0/P1.
    if selected.get("priority") == "P2":
        return {}
    if selected.get("priority") not in {"P0", "P1"}:
        return {
            "action_type": "review_priority_handoff",
            "classification": "main_handoff",
            "reason": "Priority handoff has an invalid selected priority; inspect its proof before generic PM work.",
            "selected_priority_item": selected,
            "priority_handoff_invalid": True,
        }
    disposition = as_dict(selected.get("disposition"))
    if disposition.get("status") in {"closed", "deferred"}:
        return {}
    return {
        "action_type": "review_priority_handoff",
        "classification": "main_handoff",
        "reason": (
            f"{selected.get('priority')} priority {selected.get('priority_id')} must be reviewed before generic PM work."
        ),
        "selected_priority_item": selected,
        "priority_receipt": priority_handoff.get("receipt"),
        "priority_handoff_invalid": False,
    }


def selected_priority_matches_handoff(priority_handoff: dict[str, Any], selected: dict[str, Any]) -> bool:
    """Reject a tampered selected item when a higher unresolved item is present."""
    active = [
        as_dict(item)
        for item in as_list(priority_handoff.get("items"))
        if as_dict(as_dict(item).get("disposition")).get("status") not in {"closed", "deferred"}
    ]
    if not active:
        return True
    rank = {"P0": 0, "P1": 1, "P2": 2}
    expected = min(
        active,
        key=lambda item: (
            rank.get(str(item.get("priority") or ""), 9),
            int(item.get("urgency_rank")) if item.get("urgency_rank") is not None else 999,
            str(item.get("priority_id") or ""),
        ),
    )
    return str(expected.get("priority_id") or "") == str(selected.get("priority_id") or "")


def choose_action(args: argparse.Namespace, artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    priority_action = select_priority_handoff(artifacts["priority_handoff"])
    if priority_action:
        return priority_action
    pm_control = artifacts["pm_control"]
    parallel = artifacts["parallel"]
    register = artifacts["lane_register"]
    jobs = queue_jobs(pm_control)
    selected_job, skipped = select_pm_job(jobs, args.context, active_collision_groups(register))
    helper_packet = build_helper_lane_packet(selected_job, parallel) if selected_job else {}
    handoff_state = repeated_handoff_state(args.ledger, selected_job.get("job_id") if selected_job else None)
    if selected_job:
        action_type = "execute_pm_proof" if job_allowed_for_context(selected_job, args.context) else "prepare_helper_lane"
        if args.context == "heartbeat":
            action_type = "prepare_helper_lane"
        return {
            "action_type": action_type,
            "classification": "auto_execute" if action_type == "execute_pm_proof" else "main_handoff",
            "reason": (
                f"PM job {selected_job.get('job_id')} is proof-safe and executable in {args.context} context."
                if action_type == "execute_pm_proof"
                else f"PM job {selected_job.get('job_id')} is ready for main/helper pickup; heartbeat does not execute phases."
            ),
            "selected_pm_job": {
                "job_id": selected_job.get("job_id"),
                "title": selected_job.get("title"),
                "rank": selected_job.get("rank"),
                "implementation_class": selected_job.get("implementation_class"),
                "collision_group": selected_job.get("collision_group"),
                "automation_capabilities": selected_job.get("automation_capabilities"),
            },
            "helper_lane_packet": helper_packet,
            "handoff_state": handoff_state,
            "skipped_jobs": skipped,
        }
    candidate = top_helper_candidate(parallel)
    if candidate:
        return {
            "action_type": "prepare_parallel_helper_lane",
            "classification": "main_handoff",
            "reason": "No PM job was auto-executable, but a parallel helper candidate is eligible.",
            "parallel_candidate": candidate,
            "parallel_lease_command": parallel.get("lease_command"),
            "skipped_jobs": skipped,
        }
    return {
        "action_type": "no_action",
        "classification": "no_reply",
        "reason": "No auto-executable PM job and no eligible parallel helper lane.",
        "skipped_jobs": skipped,
    }


def execute_action(action: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.execute_safe:
        return []
    if args.context == "heartbeat":
        return []
    if action.get("action_type") != "execute_pm_proof":
        return []
    job_id = as_dict(action.get("selected_pm_job")).get("job_id")
    if not job_id:
        return []
    return [
        run_step(
            "pm_execution_loop_execute_selected_job",
            py_cmd(
                "scripts\\pm_execution_loop.py",
                "--execute",
                "--job",
                str(job_id),
                "--write",
                "--validate",
            ),
            1200,
        )
    ]


def append_ledger(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema": "veritas.main_session_action_executor_ledger.entry.v1",
        "recorded_at_utc": utc_now(),
        "report_generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "mode": report.get("mode"),
        "context": report.get("context"),
        "summary": report.get("summary"),
        "action": report.get("action"),
        "validation": report.get("validation"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if report.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    action = as_dict(report.get("action"))
    if action.get("classification") == "auto_execute":
        caps = as_dict(as_dict(action.get("selected_pm_job")).get("automation_capabilities"))
        if caps.get("owner_gate_required"):
            errors.append("auto_execute_owner_gate_required")
        if caps.get("unsafe_proof_commands"):
            errors.append("auto_execute_unsafe_proof_commands")
        if report.get("context") == "heartbeat":
            errors.append("heartbeat_auto_execute_forbidden")
    if report.get("context") == "heartbeat" and report.get("mode") == "execute_safe":
        errors.append("heartbeat_execute_safe_requested")
    if action.get("action_type") == "review_priority_handoff":
        priority = as_dict(action.get("selected_priority_item"))
        if action.get("priority_handoff_invalid"):
            errors.append("priority_handoff_invalid")
        elif priority.get("priority") not in {"P0", "P1"}:
            errors.append("priority_handoff_selected_priority_invalid")
        elif priority.get("authority_boundary") != PRIORITY_AUTHORITY_BOUNDARY:
            errors.append("priority_handoff_authority_boundary_changed")
        elif (
            not str(priority.get("next_action") or "").strip()
            or not as_dict(priority.get("acceptance_proof")).get("artifact")
            or not str(priority.get("owner") or "").strip()
            or priority.get("due_window") not in PRIORITY_DUE_WINDOWS
        ):
            errors.append("priority_handoff_selected_item_incomplete")
        elif report.get("priority_handoff_selected_item_matches_highest_unresolved") is not True:
            errors.append("priority_handoff_selected_item_not_highest_unresolved")
    for result in as_list(report.get("frontdoor_refresh_results")):
        if result.get("ok"):
            continue
        name = str(result.get("name") or "")
        if name in SOFT_FRONTDOOR_FAILURES:
            warnings.append(f"frontdoor_reported_residue:{name}")
        else:
            errors.append("frontdoor_refresh_failed")
    if any(not result.get("ok") for result in as_list(report.get("execution_results"))):
        errors.append("execution_failed")
    if action.get("classification") == "main_handoff":
        warnings.append("main_handoff_action_present")
    if action.get("action_type") == "no_action":
        warnings.append("no_action_available")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    refresh_results = maybe_refresh_frontdoors(args)
    artifacts = {
        "cron_control": load(CRON_CONTROL),
        "greenkeeper": load(GREENKEEPER),
        "escalation_consumer": load(ESCALATION_CONSUMER),
        "pm_control": load(PM_CONTROL),
        "parallel": load(PARALLEL_RECOMMENDATION),
        "lane_register": load(LANE_REGISTER),
        "handoff_first_proof": load(HANDOFF_FIRST_PROOF),
        "priority_handoff": load(PRIORITY_HANDOFF),
    }
    action = choose_action(args, artifacts)
    execution_results = execute_action(action, args)
    pm_execution = load(PM_EXECUTION_LOOP)
    selected_pm_job = as_dict(action.get("selected_pm_job"))
    parallel_candidate = as_dict(action.get("parallel_candidate"))
    selected_priority_item = as_dict(action.get("selected_priority_item"))
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": "execute_safe" if args.execute_safe else "dry_run",
        "context": args.context,
        "purpose": "Main-session pickup layer for cron/greenkeeper/PM/parallel handoffs.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "cron_control": rel(CRON_CONTROL),
            "escalation_consumer": rel(ESCALATION_CONSUMER),
            "greenkeeper": rel(GREENKEEPER),
            "pm_control": rel(PM_CONTROL),
            "parallel_lane_recommendation": rel(PARALLEL_RECOMMENDATION),
            "lane_register": rel(LANE_REGISTER),
            "pm_execution_loop": rel(PM_EXECUTION_LOOP),
            "handoff_first_proof": rel(HANDOFF_FIRST_PROOF),
            "main_session_priority_handoff": rel(PRIORITY_HANDOFF),
        },
        "priority_handoff_selected_item_matches_highest_unresolved": (
            selected_priority_matches_handoff(artifacts["priority_handoff"], selected_priority_item)
            if action.get("action_type") == "review_priority_handoff" and not action.get("priority_handoff_invalid")
            else None
        ),
        "summary": {
            "action_type": action.get("action_type"),
            "classification": action.get("classification"),
            "selected_pm_job": selected_pm_job,
            "parallel_helper_workstream": parallel_candidate.get("workstream_id"),
            "parallel_helper_title": parallel_candidate.get("title"),
            "parallel_helper_pm_job_id": parallel_candidate.get("pm_job_id"),
            "parallel_lease_command": action.get("parallel_lease_command"),
            "frontdoor_refresh_ran": bool(refresh_results),
            "frontdoor_refresh_failed": [result.get("name") for result in refresh_results if not result.get("ok")],
            "executed": bool(execution_results),
            "execution_failed": [result.get("name") for result in execution_results if not result.get("ok")],
            "pm_execution_loop_status": pm_execution.get("status"),
            "pm_execution_loop_mode": pm_execution.get("mode"),
            "pm_execution_loop_selected_jobs": as_dict(pm_execution.get("summary")).get("selected_jobs"),
            "parallel_eligible_candidate_count": as_dict(as_dict(artifacts["parallel"].get("summary"))).get("eligible_candidate_count"),
            "greenkeeper_action_counts": as_dict(as_dict(artifacts["greenkeeper"].get("summary")).get("action_counts")),
            "escalation_consumer_status": artifacts["escalation_consumer"].get("status"),
            "escalation_consumer_executed_safe_action_count": as_dict(artifacts["escalation_consumer"].get("summary")).get("executed_safe_action_count"),
            "escalation_consumer_unresolved_count": as_dict(artifacts["escalation_consumer"].get("summary")).get("unresolved_count"),
            "escalation_consumer_next_safe_action": as_dict(artifacts["escalation_consumer"].get("summary")).get("next_safe_action"),
            "handoff_first_proof_status": artifacts["handoff_first_proof"].get("status"),
            "handoff_first_proof_needs_repair_count": as_dict(artifacts["handoff_first_proof"].get("summary")).get("needs_repair_count"),
            "handoff_first_proof_target_lanes": as_dict(artifacts["handoff_first_proof"].get("repair_lane_packet")).get("target_lanes"),
            "priority_handoff_status": artifacts["priority_handoff"].get("status"),
            "priority_handoff_receipt": artifacts["priority_handoff"].get("receipt"),
            "selected_priority_item": selected_priority_item,
            "selected_priority_level": selected_priority_item.get("priority"),
            "next_safe_action": (
                "Review execution_results and PM execution loop output."
                if execution_results
                else (
                    selected_priority_item.get("next_action")
                    if action.get("action_type") == "review_priority_handoff" and selected_priority_item
                    else (
                        "Use tmp/main-session-handoff-first-proof.json repair_lane_packet to repair blocked/missing handoff lanes."
                        if as_dict(artifacts["handoff_first_proof"].get("summary")).get("needs_repair_count")
                        else (
                            "Run with --execute-safe from main/cron/closeout context to execute the selected proof-safe PM job."
                            if action.get("action_type") == "execute_pm_proof"
                            else (
                                as_dict(action.get("helper_lane_packet")).get("next_safe_action")
                                or (
                                    "Run the parallel lane recommender lease_command, spawn the helper with the matching packet, "
                                    "then verify proof and complete the lane."
                                    if action.get("action_type") == "prepare_parallel_helper_lane"
                                    else ""
                                )
                                or "No action available."
                            )
                        )
                    )
                )
            ),
        },
        "action": action,
        "frontdoor_refresh_results": refresh_results,
        "execution_results": execution_results,
        "stop_lines": [
            "Dry-run by default.",
            "--execute-safe runs only one proof-safe PM job via pm_execution_loop with completion-ledger skip.",
            "Heartbeat context may prepare/surface handoff only; it must not execute PM phases.",
            "No code patching, helper spawning, cron schedule mutation, config/auth/runtime change, canon/portfolio mutation, SQL/ticker import, capital deployment, paper/live/account action, money movement, or owner approval inference.",
        ],
    }
    report["validation"] = validate_report(report)
    report["status"] = (
        "blocked" if report["validation"]["status"] == "blocked"
        else "warning" if report["validation"]["warnings"]
        else "ok"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded main-session action executor.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--refresh-frontdoors", action="store_true")
    parser.add_argument("--execute-safe", action="store_true")
    parser.add_argument("--append-ledger", action="store_true")
    parser.add_argument("--context", choices=["main_session", "cron", "heartbeat", "closeout", "manual"], default="main_session")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args()

    # Context is not authority.  When a caller declares heartbeat context, it
    # gets exactly the fixed dry-run surface used by heartbeat_priority_handoff:
    # no frontdoor chain, execution, ledger append, or alternate write target.
    # Reject before build_report() so an invalid heartbeat invocation cannot
    # overwrite an action-executor artifact and then merely fail validation.
    heartbeat_forbidden: list[str] = []
    if args.context == "heartbeat":
        if args.execute_safe:
            heartbeat_forbidden.append("--execute-safe")
        if args.append_ledger:
            heartbeat_forbidden.append("--append-ledger")
        if args.refresh_frontdoors:
            heartbeat_forbidden.append("--refresh-frontdoors")
        out = args.out if args.out.is_absolute() else ROOT / args.out
        ledger = args.ledger if args.ledger.is_absolute() else ROOT / args.ledger
        if args.write and out.resolve() != HEARTBEAT_OUT.resolve():
            heartbeat_forbidden.append("--out")
        if ledger.resolve() != LEDGER.resolve():
            heartbeat_forbidden.append("--ledger")
    if heartbeat_forbidden:
        print(f"blocked heartbeat arguments: {', '.join(heartbeat_forbidden)}", file=sys.stderr)
        return 2

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        if args.append_ledger:
            append_ledger(args.ledger, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} mode={report['mode']} "
            f"context={report['context']} action={report['summary']['action_type']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
