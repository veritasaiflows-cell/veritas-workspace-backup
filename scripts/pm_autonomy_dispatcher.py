#!/usr/bin/env python3
"""Select the next unattended-safe PM action.

The dispatcher is a selector, not an implementer. It writes a durable action
inbox for the worker/status surfaces and never patches code or mutates protected
state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from pm_autonomy_policy import DEFAULT_POLICY_PATH, load_policy, validate_policy

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

PM_QUEUE = TMP / "pm-implementation-job-queue.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
OUT = TMP / "pm-autonomy-dispatcher.json"
INBOX = TMP / "pm-main-session-action-inbox.json"

SCHEMA = "veritas.pm_autonomy_dispatcher.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "selects_jobs": True,
    "executes_jobs": False,
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


def priority_band_rank(priority: Any) -> int:
    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4,
        "P5": 5,
    }.get(str(priority or "P9").upper(), 9)


def numeric(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return default


def active_collision_groups(register: dict[str, Any]) -> set[str]:
    groups: set[str] = set()
    for lane in as_list(register.get("lanes")):
        row = as_dict(lane)
        if row.get("status") not in {"planned", "leased", "running"}:
            continue
        for key in ("collision_group", "workstream_id", "workflow_id"):
            value = row.get(key)
            if value:
                groups.add(str(value))
    return groups


def action_class_for_job(job: dict[str, Any], policy: dict[str, Any], execution_context: str = "cron") -> tuple[str, str]:
    classes = as_dict(policy.get("allowed_action_classes"))
    caps = as_dict(job.get("automation_capabilities"))
    status = str(job.get("status") or "")
    if status == "completed_by_ledger" or job.get("completed_by_ledger") is True:
        return "completed", "completed_by_ledger"
    if status == "owner_decision_required" or caps.get("owner_gate_required") is True:
        return "owner_gated", "owner_gate_required"
    if status not in {"ready_for_main_or_helper", "ready_for_review"}:
        return "not_ready", f"status={status}"
    if caps.get("unsafe_proof_commands"):
        return "blocked", "unsafe_proof_commands"
    if caps.get("auto_cron_may_execute") is True and classes.get("proof_refresh") is True:
        return "proof_refresh", "cron_proof_allowed"
    if (
        execution_context == "main"
        and caps.get("auto_main_may_execute") is True
        and classes.get("main_proof_refresh") is True
    ):
        return "proof_refresh", "main_proof_allowed"
    if (caps.get("auto_lane_prepare_allowed") is True or caps.get("helper_lane_allowed") is True) and classes.get("implementation_plan") is True:
        return "implementation_plan", "planning_allowed"
    return "main_review", "not_unattended_eligible"


def job_sort_tuple(job: dict[str, Any], action_class: str) -> tuple[Any, ...]:
    action_rank = {
        "proof_refresh": 0,
        "implementation_plan": 1,
        "main_review": 2,
        "owner_gated": 3,
        "blocked": 4,
        "not_ready": 5,
        "completed": 6,
    }.get(action_class, 9)
    return (
        action_rank,
        priority_band_rank(job.get("priority")),
        -numeric(job.get("source_priority_score"), 0.0),
        -numeric(job.get("readiness_score"), 0.0),
        int(job.get("rank") or 9999),
        str(job.get("job_id") or ""),
    )


def job_view(job: dict[str, Any]) -> dict[str, Any]:
    caps = as_dict(job.get("automation_capabilities"))
    return {
        "job_id": job.get("job_id"),
        "rank": job.get("rank"),
        "priority": job.get("priority"),
        "source_priority_score": job.get("source_priority_score"),
        "status": job.get("status"),
        "title": job.get("title"),
        "implementation_class": job.get("implementation_class"),
        "collision_group": job.get("collision_group"),
        "readiness_score": job.get("readiness_score"),
        "proof_commands": as_list(job.get("proof_commands")),
        "automation_capabilities": {
            "auto_cron_may_execute": caps.get("auto_cron_may_execute"),
            "auto_main_may_execute": caps.get("auto_main_may_execute"),
            "main_proof_refresh_candidate": caps.get("main_proof_refresh_candidate"),
            "cron_proof_refresh_candidate": caps.get("cron_proof_refresh_candidate"),
            "cron_graduation_required": caps.get("cron_graduation_required"),
            "cron_graduation_satisfied": caps.get("cron_graduation_satisfied"),
            "auto_lane_prepare_allowed": caps.get("auto_lane_prepare_allowed"),
            "helper_lane_allowed": caps.get("helper_lane_allowed"),
            "owner_gate_required": caps.get("owner_gate_required"),
            "unsafe_proof_commands": caps.get("unsafe_proof_commands"),
        },
    }


def build_inbox(report: dict[str, Any]) -> dict[str, Any]:
    action = as_dict(report.get("action"))
    selected = as_dict(action.get("selected_job"))
    return {
        "schema": "veritas.pm_main_session_action_inbox.v1",
        "generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "dispatcher_status": report.get("status"),
        "action_type": action.get("action_type"),
        "automation_class": action.get("automation_class"),
        "top_pending_job_id": selected.get("job_id"),
        "priority": selected.get("priority"),
        "priority_score": selected.get("source_priority_score"),
        "recommended_executor": action.get("recommended_executor"),
        "execution_context": action.get("execution_context"),
        "cron_proof_allowed": action.get("execution_context") == "cron" and action.get("automation_class") == "proof_refresh",
        "main_proof_allowed": action.get("execution_context") == "main" and action.get("automation_class") == "proof_refresh",
        "main_next_action": action.get("next_action"),
        "verification_required": True,
        "blocked_by": action.get("blocked_by"),
        "selected_job": selected,
        "source_artifacts": report.get("source_artifacts"),
        "authority_boundary": report.get("authority_boundary"),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    policy = load_policy(args.policy)
    policy_validation = validate_policy(policy)
    queue = load(args.queue)
    register = load(args.lane_register)
    jobs = [as_dict(job) for job in as_list(queue.get("jobs"))]
    busy = active_collision_groups(register)
    execution_context = str(getattr(args, "execution_context", "cron") or "cron")

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for job in jobs:
        action_class, reason = action_class_for_job(job, policy, execution_context)
        view = job_view(job)
        view["automation_class"] = action_class
        view["reason"] = reason
        group = str(job.get("collision_group") or "")
        if group and group in busy and action_class in {"proof_refresh", "implementation_plan"}:
            view["automation_class"] = "blocked"
            view["reason"] = f"collision_group_active:{group}"
            skipped.append(view)
            continue
        if action_class in {"proof_refresh", "implementation_plan"}:
            candidates.append(view)
        else:
            skipped.append(view)

    candidates.sort(key=lambda row: job_sort_tuple(row, str(row.get("automation_class"))))
    selected = candidates[0] if candidates else {}
    action_type = "no_action"
    next_action = "No unattended-safe PM job is currently ready."
    recommended_executor = "none"
    blocked_by = None
    if selected:
        if selected.get("automation_class") == "proof_refresh":
            action_type = "run_proof_refresh"
            recommended_executor = "pm_job_worker_runner"
            next_action = f"Run proof commands for {selected.get('job_id')} through pm_execution_loop, then verify and refresh status."
        elif selected.get("automation_class") == "implementation_plan":
            action_type = "prepare_implementation_plan"
            recommended_executor = "main_or_helper_after_review"
            next_action = f"Prepare implementation plan/handoff for {selected.get('job_id')}; do not patch code unattended."
    elif policy_validation["status"] != "ok":
        blocked_by = "policy_validation"
        next_action = "Repair PM autonomy policy before unattended dispatch."

    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": "dry_run" if args.dry_run else "dispatch",
        "purpose": "Select one unattended-safe PM action for scheduled proof/planning autonomy.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "execution_context": execution_context,
        "source_artifacts": {
            "policy": rel(args.policy),
            "pm_queue": rel(args.queue),
            "lane_register": rel(args.lane_register),
        },
        "summary": {
            "job_count": len(jobs),
            "candidate_count": len(candidates),
            "skipped_count": len(skipped),
            "selected_job_id": selected.get("job_id"),
            "selected_action_type": action_type,
            "selected_automation_class": selected.get("automation_class"),
            "selected_priority_score": selected.get("source_priority_score"),
            "policy_status": policy_validation["status"],
            "execution_context": execution_context,
            "busy_collision_group_count": len(busy),
            "next_action": next_action,
        },
        "action": {
            "action_type": action_type,
            "automation_class": selected.get("automation_class"),
            "execution_context": execution_context,
            "recommended_executor": recommended_executor,
            "selected_job": selected,
            "next_action": next_action,
            "blocked_by": blocked_by,
        },
        "candidates": candidates[:10],
        "skipped": skipped[:25],
        "policy": {
            "enabled": policy.get("enabled"),
            "cadence": policy.get("cadence"),
            "default_model": policy.get("default_model"),
            "allowed_action_classes": policy.get("allowed_action_classes"),
        },
        "validation": {
            "status": "pending",
            "errors": [],
            "warnings": [],
        },
        "stop_lines": [
            "Selector only; no code patching, helper spawning, cron mutation, config/runtime change, finance/canon/customer/external/account/trading action, or owner approval inference.",
        ],
    }
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    if report["authority_boundary"] != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    if policy_validation["status"] != "ok":
        errors.extend([f"policy:{item}" for item in policy_validation["errors"]])
    if execution_context not in {"cron", "main"}:
        errors.append(f"invalid_execution_context:{execution_context}")
    if execution_context == "cron" and action_type == "run_proof_refresh":
        caps = as_dict(selected.get("automation_capabilities"))
        if caps.get("auto_cron_may_execute") is not True:
            errors.append("cron_context_selected_non_cron_job")
    if action_type == "no_action":
        info.append("no_unattended_safe_job")
    report["validation"] = {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings, "info": info}
    report["status"] = "blocked" if errors else "warning" if warnings else "quiet_success" if action_type == "no_action" else "ok"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next unattended-safe PM action.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--queue", type=Path, default=PM_QUEUE)
    parser.add_argument("--lane-register", type=Path, default=LANE_REGISTER)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--inbox", type=Path, default=INBOX)
    parser.add_argument("--execution-context", choices=("cron", "main"), default="cron")
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        atomic_write_json(args.inbox, build_inbox(report))
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"action={report['summary']['selected_action_type']} selected={report['summary']['selected_job_id']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
