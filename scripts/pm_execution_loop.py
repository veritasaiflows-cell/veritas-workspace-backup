#!/usr/bin/env python3
"""PM execution loop: use the PM control packet as the operating system.

Picks the top safe job(s) from ``pm-control-packet.json``, enforces
one-writer-per-collision-group, optionally runs the job's review-only proof
commands, then runs the standard closeout enforcer.

Dry-run by default: it shows what *would* run. Pass ``--execute`` to actually
run the guarded proof + closeout commands.

Hard guard: only review-only proof/validation commands are auto-executed. Any
job whose proof commands contain mutation/execution/import/config tokens is
marked ``needs_main_review`` and is never auto-run here. No capital deployment,
trade/paper/live/account action, money movement, canon/portfolio mutation, SQL
import, config/auth/runtime change, or owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.command_guard import command_is_review_only_safe, parse_command
from lib.proof_budget import closeout_commands
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CONTROL_PACKET = TMP / "pm-control-packet.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
OUT = TMP / "pm-execution-loop.json"
SCHEMA = "veritas.pm_execution_loop.v1"

READY_STATUS = "ready_for_main_or_helper"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runs_review_only_proof_commands": True,
    "executes_implementation_jobs": False,
    "spawns_helpers": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
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


def proof_commands_safe(job: dict[str, Any]) -> tuple[bool, list[str]]:
    unsafe: list[str] = []
    for cmd in as_list(job.get("proof_commands")):
        if not command_is_review_only_safe(str(cmd)):
            unsafe.append(str(cmd))
    return (not unsafe, unsafe)


def command_parts_and_cwd(command: str) -> tuple[list[str], Path]:
    """Support the PM queue's narrow ``cd dir; command`` proof-command shape."""
    cwd = ROOT
    stripped = command.strip()
    if stripped.lower().startswith("cd ") and ";" in stripped:
        cd_part, command_part = stripped.split(";", 1)
        cd_target = cd_part[3:].strip().strip('"').strip("'")
        candidate = (ROOT / cd_target).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            return [], ROOT
        cwd = candidate
        stripped = command_part.strip()
    parts = parse_command(stripped)
    if parts and parts[0].lower() in ("python", "python3", "py"):
        parts = [sys.executable, *parts[1:]]
    elif parts and sys.platform == "win32":
        shim = shutil.which(f"{parts[0]}.cmd") or shutil.which(f"{parts[0]}.exe") or shutil.which(parts[0])
        if shim:
            parts = [shim, *parts[1:]]
    return parts, cwd


def run_command_string(name: str, command: str, timeout: int) -> dict[str, Any]:
    parts, cwd = command_parts_and_cwd(command)
    started = utc_now()
    if not parts:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "stdout_preview": "",
            "stderr_preview": "unable to parse review-only proof command",
        }
    try:
        proc = subprocess.run(parts, cwd=cwd, text=True, capture_output=True, timeout=timeout)
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
    except FileNotFoundError as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "stdout_preview": "",
            "stderr_preview": f"{type(exc).__name__}: {exc}",
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


def run_command_parts(name: str, parts: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(parts, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": parts,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-2000:],
            "stderr_preview": proc.stderr.strip()[-1200:],
        }
    except FileNotFoundError as exc:
        return {
            "name": name,
            "command": parts,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "stdout_preview": "",
            "stderr_preview": f"{type(exc).__name__}: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": parts,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def active_register_groups() -> set[str]:
    data = as_dict(load_json_artifact(LANE_REGISTER))
    groups: set[str] = set()
    for lane in as_list(data.get("lanes")):
        lane = as_dict(lane)
        if lane.get("status") in ("leased", "running"):
            group = lane.get("collision_group") or lane.get("workstream")
            if group:
                groups.add(str(group))
    return groups


def select_jobs(jobs: list[dict[str, Any]], limit: int, only_job: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    busy_groups = active_register_groups()
    used_groups: set[str] = set()
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    ranked = sorted(
        [as_dict(j) for j in jobs],
        key=lambda j: (int(j.get("rank") or 9999), -float(j.get("readiness_score") or 0)),
    )

    for job in ranked:
        job_id = job.get("job_id")
        if only_job and job_id != only_job:
            continue
        group = str(job.get("collision_group") or job_id)
        if job.get("status") != READY_STATUS:
            skipped.append({"job_id": job_id, "reason": f"status={job.get('status')}"})
            continue
        if group in busy_groups:
            skipped.append({"job_id": job_id, "reason": f"collision group '{group}' is leased/running in lane register"})
            continue
        if group in used_groups:
            skipped.append({"job_id": job_id, "reason": f"collision group '{group}' already selected this run"})
            continue
        safe, unsafe = proof_commands_safe(job)
        if not safe:
            skipped.append({"job_id": job_id, "reason": "proof commands need main review", "unsafe_commands": unsafe})
            continue
        used_groups.add(group)
        selected.append(job)
        if len(selected) >= limit:
            break

    return selected, skipped


def job_view(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "rank": job.get("rank"),
        "priority": job.get("priority"),
        "title": job.get("title"),
        "implementation_class": job.get("implementation_class"),
        "owner_surface": job.get("owner_surface"),
        "collision_group": job.get("collision_group"),
        "validation_budget": job.get("validation_budget"),
        "closeout_mode": job.get("closeout_mode"),
        "target_files": job.get("target_files"),
        "proof_commands": job.get("proof_commands"),
        "acceptance_criteria": job.get("acceptance_criteria"),
        "closeout_required": job.get("closeout_required"),
    }


def job_closeout_commands(job: dict[str, Any]) -> list[str]:
    listed = [str(command) for command in as_list(job.get("closeout_required"))]
    if listed:
        return listed
    return closeout_commands(str(job.get("closeout_mode") or "integration"))


def load_queue() -> tuple[dict[str, Any], str]:
    control = as_dict(load_json_artifact(CONTROL_PACKET))
    queue = as_dict(as_dict(control.get("sections")).get("pm_implementation_job_queue"))
    if queue:
        return queue, rel(CONTROL_PACKET)
    return {}, rel(CONTROL_PACKET)


def worker_state(
    selected: list[dict[str, Any]],
    proof_results: list[dict[str, Any]],
    closeout_results: list[dict[str, Any]],
    *,
    executed: bool,
    completion_ledger_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proof_ok = bool(proof_results) and all(row.get("ok") for row in proof_results)
    closeout_ok = bool(closeout_results) and all(row.get("ok") for row in closeout_results)
    ledgered = as_dict(completion_ledger_result).get("ok") is True
    frontdoors_refreshed = any(
        "pm_control_packet.py" in " ".join(str(part) for part in as_list(row.get("command")))
        or "pm_control_packet.py" in str(row.get("command") or "")
        for row in closeout_results
        if row.get("ok")
    )
    resolved = bool(executed and selected and proof_ok and closeout_ok and ledgered)
    return {
        "candidate_selected": bool(selected),
        "selected_job_ids": [job.get("job_id") for job in selected],
        "lane_prepared": False,
        "proof_executed": bool(executed and proof_results),
        "proof_ok": proof_ok,
        "closeout_executed": bool(executed and closeout_results),
        "closeout_ok": closeout_ok,
        "closeout_ledgered": ledgered,
        "frontdoors_refreshed": frontdoors_refreshed,
        "job_resolved_or_completed": resolved,
        "terminal_state": (
            "resolved"
            if resolved
            else "blocked"
            if any(not row.get("ok") for row in proof_results + closeout_results) or (completion_ledger_result and not ledgered)
            else "executed_waiting_for_ledger"
            if executed and selected
            else "dry_run_selected"
            if selected
            else "no_candidate_selected"
        ),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    queue, queue_source = load_queue()
    errors: list[str] = []
    if not queue:
        errors.append(f"missing PM job queue; run pm_control_packet.py --write --write-db --validate first")

    jobs = as_list(queue.get("jobs"))
    selected, skipped = select_jobs(jobs, max(1, args.limit), args.job)

    proof_results: list[dict[str, Any]] = []
    closeout_results: list[dict[str, Any]] = []
    executed = bool(args.execute and selected)

    if executed:
        proof_cache: dict[str, dict[str, Any]] = {}
        for job in selected:
            job_id = str(job.get("job_id"))
            for idx, cmd in enumerate(as_list(job.get("proof_commands"))):
                command = str(cmd)
                if args.reuse_proof_cache and command in proof_cache and proof_cache[command].get("ok"):
                    proof_results.append({
                        "name": f"{job_id}:proof[{idx}]",
                        "command": command,
                        "started_at_utc": utc_now(),
                        "completed_at_utc": utc_now(),
                        "returncode": 0,
                        "ok": True,
                        "reused": True,
                        "reused_from": proof_cache[command].get("name"),
                        "stdout_preview": "",
                        "stderr_preview": "",
                    })
                    continue
                result = run_command_string(f"{job_id}:proof[{idx}]", command, 600)
                proof_results.append(result)
                if result.get("ok"):
                    proof_cache[command] = result
        closeout_seen: set[str] = set()
        for job in selected:
            job_id = str(job.get("job_id"))
            for idx, command in enumerate(job_closeout_commands(job)):
                if command in closeout_seen:
                    continue
                closeout_seen.add(command)
                if args.reuse_proof_cache and command in proof_cache and proof_cache[command].get("ok"):
                    closeout_results.append({
                        "name": f"{job_id}:closeout[{idx}]",
                        "command": command,
                        "started_at_utc": utc_now(),
                        "completed_at_utc": utc_now(),
                        "returncode": 0,
                        "ok": True,
                        "reused": True,
                        "reused_from": proof_cache[command].get("name"),
                        "stdout_preview": "",
                        "stderr_preview": "",
                    })
                    continue
                closeout_results.append(run_command_string(f"{job_id}:closeout[{idx}]", command, 600))

    failed = [r["name"] for r in (proof_results + closeout_results) if not r["ok"]]
    if failed:
        errors.extend(failed)
    status = "ok" if not errors else "blocked"

    state = worker_state(selected, proof_results, closeout_results, executed=executed)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "execute" if executed else "dry_run",
        "queue_source": queue_source,
        "purpose": "Pick top safe PM job(s), enforce one-writer-per-collision-group, run review-only proof + closeout.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [queue_source, rel(LANE_REGISTER)],
        "parameters": {
            "execute": bool(args.execute),
            "limit": max(1, args.limit),
            "job": args.job,
        },
        "summary": {
            "queue_job_count": len(jobs),
            "selected_count": len(selected),
            "selected_jobs": [j.get("job_id") for j in selected],
            "skipped_count": len(skipped),
            "executed": executed,
            "proof_failed": [r["name"] for r in proof_results if not r["ok"]],
            "closeout_failed": [r["name"] for r in closeout_results if not r["ok"]],
            "proof_reused_count": len([r for r in proof_results if r.get("reused")]),
            "closeout_reused_count": len([r for r in closeout_results if r.get("reused")]),
            "proof_cache_enabled": bool(args.reuse_proof_cache),
            "worker_state": state,
            "recommended_execution_rule": queue.get("recommended_execution_rule"),
            "selected_validation_budgets": [
                {
                    "job_id": job.get("job_id"),
                    "budget": as_dict(job.get("validation_budget")).get("budget"),
                    "closeout_mode": job.get("closeout_mode"),
                    "closeout_command_count": len(job_closeout_commands(job)),
                }
                for job in selected
            ],
            "next_safe_action": (
                "Review job output, then re-run with --execute to run the next collision-distinct job."
                if not executed
                else "Verify proof + closeout output; update daily/continuity if implementation state changed."
            ),
        },
        "selected": [job_view(j) for j in selected],
        "worker_state": state,
        "skipped": skipped,
        "proof_results": proof_results,
        "closeout_results": closeout_results,
        "validation": {
            "status": status,
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "Dry-run by default; --execute runs only review-only proof plus each job's budgeted closeout commands.",
            "One writer per collision group; jobs leased/running in the lane register are skipped.",
            "Jobs with mutation/execution/import/config proof commands are flagged needs_main_review and never auto-run.",
            "No capital deployment, trade/paper/live/account action, money movement, canon/portfolio/SQL mutation, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PM execution loop over the implementation job queue.")
    parser.add_argument("--write", action="store_true", help="Write the execution-loop artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero when status is blocked.")
    parser.add_argument("--execute", action="store_true", help="Run guarded proof + closeout commands (default is dry-run).")
    parser.add_argument("--skip-completion-ledger", action="store_true", help="Do not append successful executed jobs to the implementation completion ledger.")
    parser.add_argument("--reuse-proof-cache", action=argparse.BooleanOptionalAction, default=True, help="Reuse identical successful proof commands within one execution batch and closeout.")
    parser.add_argument("--limit", type=int, default=1, help="Max jobs to select across distinct collision groups (default 1).")
    parser.add_argument("--job", default=None, help="Select a specific job_id only.")
    parser.add_argument("--out", type=Path, default=OUT, help="Output artifact path.")
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        if report["status"] == "ok" and report["mode"] == "execute" and not args.skip_completion_ledger:
            ledger_result = run_command_parts(
                "implementation_completion_ledger",
                [
                    sys.executable,
                    "scripts\\implementation_completion_ledger.py",
                    "--source",
                    rel(args.out),
                    "--record",
                    "--write",
                    "--validate",
                ],
                120,
            )
            report["completion_ledger_result"] = ledger_result
            report["worker_state"] = worker_state(
                as_list(report.get("selected")),
                as_list(report.get("proof_results")),
                as_list(report.get("closeout_results")),
                executed=True,
                completion_ledger_result=ledger_result,
            )
            report["summary"]["worker_state"] = report["worker_state"]
            if not ledger_result["ok"]:
                report["status"] = "blocked"
                report["validation"]["status"] = "blocked"
                report["validation"]["errors"] = [*report["validation"]["errors"], "implementation_completion_ledger"]
            atomic_write_json(args.out, report)
        s = report["summary"]
        print(
            f"wrote {rel(args.out)} status={report['status']} mode={report['mode']} "
            f"selected={s['selected_count']} skipped={s['skipped_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2, default=str))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
