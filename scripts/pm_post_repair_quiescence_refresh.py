#!/usr/bin/env python3
"""Refresh front doors after PM/cron/WF74 repair work settles.

This wrapper is intentionally narrow: it reruns the proof surfaces that decide
whether repaired jobs are still visible as ready/blocked work. It does not patch
code, mutate cron schedules, change config, or widen finance authority.
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
OUT = TMP / "pm-post-repair-quiescence-refresh.json"

SCHEMA = "veritas.pm_post_repair_quiescence_refresh.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "frontdoor_refresh_only": True,
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

STEPS: list[tuple[str, list[str], int, str]] = [
    ("cron_freshness_spine", [sys.executable, "scripts\\cron_freshness_spine.py", "--write", "--validate"], 300, "tmp/cron-freshness-spine.json"),
    ("cron_control_packet", [sys.executable, "scripts\\cron_control_packet.py", "--write", "--validate"], 300, "tmp/cron-control-packet.json"),
    ("wf74_improvement_opportunity_queue", [sys.executable, "scripts\\wf74_improvement_opportunity_queue.py", "--write", "--validate"], 240, "tmp/wf74-improvement-opportunity-queue.json"),
    ("wf74_autonomy_work_router", [sys.executable, "scripts\\wf74_autonomy_work_router.py", "--write", "--validate"], 240, "tmp/wf74-autonomy-work-router.json"),
    ("pm_implementation_job_queue", [sys.executable, "scripts\\pm_implementation_job_queue.py", "--write", "--write-db", "--validate"], 300, "tmp/pm-implementation-job-queue.json"),
    ("pm_control_packet", [sys.executable, "scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 360, "tmp/pm-control-packet.json"),
    ("otel_learning_loop", [sys.executable, "scripts\\otel_learning_loop.py", "--write", "--validate"], 240, "tmp/otel-learning-loop.json"),
    ("status_card_packet", [sys.executable, "scripts\\status_card_packet.py", "--write", "--validate"], 180, "tmp/veritas-status-card.json"),
]


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


def load(path: str | Path) -> dict[str, Any]:
    candidate = path if isinstance(path, Path) else ROOT / path
    return as_dict(load_json_artifact(candidate))


def run_step(name: str, command: list[str], timeout: int, artifact: str) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "artifact": artifact,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": (proc.stdout or "").strip()[-1800:],
            "stderr_preview": (proc.stderr or "").strip()[-1000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "artifact": artifact,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-1800:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1000:] if isinstance(exc.stderr, str) else "",
        }


def summarize_quiescence(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cron_freshness = as_dict(artifacts.get("cron_freshness_spine"))
    cron_control = as_dict(artifacts.get("cron_control_packet"))
    wf74_router = as_dict(artifacts.get("wf74_autonomy_work_router"))
    pm_queue = as_dict(artifacts.get("pm_implementation_job_queue"))
    pm_control = as_dict(artifacts.get("pm_control_packet"))
    otel_loop = as_dict(artifacts.get("otel_learning_loop"))
    status_card = as_dict(artifacts.get("status_card_packet"))

    cron_summary = as_dict(cron_control.get("summary"))
    pm_summary = as_dict(pm_queue.get("summary"))
    wf74_summary = as_dict(wf74_router.get("summary"))
    pm_control_summary = as_dict(pm_control.get("summary"))
    return {
        "cron_freshness_status": cron_freshness.get("status"),
        "cron_control_status": cron_control.get("status"),
        "cron_blocked_count": int(cron_summary.get("blocked_count") or 0),
        "cron_escalation_signal_count": int(cron_summary.get("escalation_signal_count") or 0),
        "cron_should_wake_main_session": bool(cron_summary.get("should_wake_main_session")),
        "wf74_router_status": wf74_router.get("status"),
        "wf74_cron_signal_classification": wf74_summary.get("cron_signal_classification"),
        "wf74_pm_candidate_count": int(wf74_summary.get("pm_job_candidate_count") or 0),
        "pm_queue_status": pm_queue.get("status"),
        "pm_ready_job_count": int(pm_summary.get("ready_job_count") or 0),
        "pm_blocked_job_count": int(pm_summary.get("blocked_job_count") or 0),
        "pm_active_job_count": int(pm_summary.get("active_job_count") or 0),
        "pm_completed_by_ledger_job_count": int(pm_summary.get("completed_by_ledger_job_count") or 0),
        "pm_control_status": pm_control.get("status"),
        "pm_control_ready_job_count": int(as_dict(pm_control_summary.get("pm_implementation_queue_summary")).get("ready_job_count") or 0),
        "otel_learning_loop_status": otel_loop.get("status"),
        "status_card_status": status_card.get("status"),
        "status_card_validation_status": as_dict(status_card.get("validation")).get("status"),
    }


def validate_quiescence(step_results: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    failed_steps = [row.get("name") for row in step_results if not row.get("ok")]
    if failed_steps:
        errors.extend([f"step_failed:{name}" for name in failed_steps])
    if summary.get("cron_freshness_status") not in {"ok", "warning"}:
        errors.append(f"cron_freshness_not_ok:{summary.get('cron_freshness_status')}")
    if summary.get("cron_control_status") != "ok":
        errors.append(f"cron_control_not_ok:{summary.get('cron_control_status')}")
    if summary.get("cron_blocked_count") or summary.get("cron_escalation_signal_count") or summary.get("cron_should_wake_main_session"):
        errors.append("cron_not_quiescent")
    if summary.get("wf74_router_status") not in {"ok", "warning"}:
        errors.append(f"wf74_router_not_ok:{summary.get('wf74_router_status')}")
    if summary.get("wf74_cron_signal_classification") not in {"green_no_repair_required", "no_cron_signal", None}:
        warnings.append(f"wf74_cron_residue_not_green:{summary.get('wf74_cron_signal_classification')}")
    if summary.get("pm_queue_status") != "ok":
        errors.append(f"pm_queue_not_ok:{summary.get('pm_queue_status')}")
    if summary.get("pm_ready_job_count") or summary.get("pm_blocked_job_count"):
        warnings.append("pm_queue_has_ready_or_blocked_jobs_after_refresh")
    if summary.get("pm_control_status") not in {"ok", "warning"}:
        errors.append(f"pm_control_not_ok:{summary.get('pm_control_status')}")
    if summary.get("otel_learning_loop_status") not in {"ok", "warning"}:
        errors.append(f"otel_learning_loop_not_ok:{summary.get('otel_learning_loop_status')}")
    if summary.get("status_card_validation_status") not in {"ok", "warning"}:
        warnings.append(f"status_card_validation_not_clean:{summary.get('status_card_validation_status')}")
    return {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    step_results: list[dict[str, Any]] = []
    for name, command, timeout, artifact in STEPS:
        result = run_step(name, command, timeout, artifact)
        step_results.append(result)
        if not result.get("ok") and not args.continue_on_failure:
            break
    artifacts = {row["name"]: load(row["artifact"]) for row in step_results}
    summary = summarize_quiescence(artifacts)
    validation = validate_quiescence(step_results, summary)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": validation["status"],
        "purpose": "Post-repair frontdoor refresh to keep resolved cron/PM/WF74 work from remaining visible as stale ready work.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            **summary,
            "steps_run": len(step_results),
            "failed_steps": [row.get("name") for row in step_results if not row.get("ok")],
            "next_safe_action": (
                "Main should inspect validation errors before further automation."
                if validation["errors"]
                else "Main should classify warnings; no cron/PM repair blocker remains if cron and PM counts are zero."
                if validation["warnings"]
                else "Quiescent. Automatic proof-only PM worker can wait for the next eligible job."
            ),
        },
        "steps": step_results,
        "validation": validation,
        "stop_lines": [
            "Refreshes proof/frontdoor artifacts only.",
            "No cron schedule/config/auth/runtime mutation.",
            "No code patch, helper spawn, archive/delete, finance/canon/portfolio/customer/external/account/trading action, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh PM/cron/WF74 front doors after repair work settles.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(json.dumps({"status": report["status"], "out": rel(args.out), "summary": report["summary"], "validation": report["validation"]}, indent=2, sort_keys=True))
    else:
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
