#!/usr/bin/env python3
"""Run a declared ordered command sequence for cron jobs that need no judgment.

Several cron jobs were agentTurn jobs whose entire instruction was "run these
commands in order, then reply NO_REPLY unless something failed".  That wrapped a
model turn around deterministic work and required a very broad tool grant on an
unattended schedule.

This runner executes the declared sequence, writes an aggregated proof artifact,
and wakes Main only when a step actually fails.  It carries no authority of its
own: every command is declared here, nothing is discovered or synthesized.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"

SCHEMA = "veritas.deterministic_cron_sequence_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "declared_commands_only": True,
    "may_discover_or_synthesize_commands": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

STOP_LINES = [
    "The runner executes only the commands declared in JOB_SPECS; it never composes new ones.",
    "A failed step wakes Main for review; it never triggers a repair, retry loop, or cleanup.",
    "Proof output is evidence for review, not approval, routing, or execution authority.",
]


class JobSpec(NamedTuple):
    key: str
    job_id: str
    title: str
    out: Path
    history: Path
    commands: list[list[str]]
    step_timeout: int


JOB_SPECS: dict[str, JobSpec] = {
    "weekly_os_improvement_radar_proof": JobSpec(
        key="weekly_os_improvement_radar_proof",
        job_id="a9d1978a-7d52-4790-bfe4-ab211e49f560",
        title="Weekly OS Improvement Radar Proof Refresh",
        out=TMP / "weekly-os-improvement-radar-proof-runner.json",
        history=STATE_HISTORY / "weekly-os-improvement-radar-proof-runner.jsonl",
        commands=[
            ["scripts/cron_efficiency_review_runner.py", "--write", "--validate"],
            ["scripts/implementation_token_attribution_bridge.py", "--write", "--write-md", "--validate"],
            ["scripts/artifact_staleness_explainer.py", "--write", "--validate"],
            ["scripts/lane_collision_preflight.py", "--write", "--validate"],
            ["scripts/validator_bundle_router.py", "--max-budget", "shared", "--write", "--validate"],
            ["scripts/worktree_checkpoint_planner.py", "--write", "--validate"],
            ["scripts/cron_contract_validator.py", "--require-contracts", "--fail-on-drift", "--write", "--validate"],
            ["scripts/pm_control_packet.py", "--write", "--write-db", "--validate"],
            ["scripts/cron_control_packet.py", "--write", "--validate"],
        ],
        step_timeout=600,
    ),
    "sunday_generated_artifact_cleanup_dry_run": JobSpec(
        key="sunday_generated_artifact_cleanup_dry_run",
        job_id="f14ec666-a9a9-4dd7-ad98-ac210800c544",
        title="Sunday Generated Artifact Cleanup Dry Run",
        out=TMP / "sunday-generated-artifact-cleanup-dry-run-runner.json",
        history=STATE_HISTORY / "sunday-generated-artifact-cleanup-dry-run-runner.jsonl",
        commands=[
            ["scripts/tmp_cleanup.py", "--dry-run", "--days", "7"],
            ["scripts/cron_operator_ledger.py", "--write", "--write-md", "--validate"],
        ],
        step_timeout=600,
    ),
}


def utc_now(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def ensure_workspace_path(path: Path) -> Path:
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"path escapes workspace: {path}")
    return resolved


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    resolved = ensure_workspace_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved.with_suffix(resolved.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(resolved)


def append_history(path: Path, record: dict[str, Any]) -> None:
    resolved = ensure_workspace_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def spec_errors(spec: JobSpec) -> list[str]:
    problems: list[str] = []
    if not spec.commands:
        problems.append("spec_has_no_commands")
    for command in spec.commands:
        if not command:
            problems.append("empty_command")
            continue
        script = command[0]
        if not script.startswith("scripts/") or not script.endswith(".py"):
            problems.append(f"command_not_a_workspace_script:{script}")
            continue
        if not (ROOT / script).is_file():
            problems.append(f"command_script_missing:{script}")
    return sorted(set(problems))


def run_command(command: list[str], timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {"command": command, "started_at_utc": utc_now()}
    try:
        completed = subprocess.run(
            [sys.executable, *command],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        record.update(
            duration_ms=int((time.monotonic() - started) * 1000),
            returncode=None,
            ok=False,
            error_code="step_timeout",
            stderr_tail="",
        )
        return record
    except OSError as exc:
        record.update(
            duration_ms=int((time.monotonic() - started) * 1000),
            returncode=None,
            ok=False,
            error_code="step_launch_failed",
            stderr_tail=str(exc)[-600:],
        )
        return record
    record.update(
        duration_ms=int((time.monotonic() - started) * 1000),
        returncode=completed.returncode,
        ok=completed.returncode == 0,
        error_code=None if completed.returncode == 0 else "step_nonzero_exit",
        stderr_tail=(completed.stderr or "")[-600:],
        stdout_tail=(completed.stdout or "")[-600:],
    )
    return record


def build_wake_message(spec: JobSpec, failed: list[dict[str, Any]], out: Path) -> str:
    lines = [
        f"{spec.title}: a deterministic step failed and needs review.",
        f"Proof: {rel(out)}",
        "",
    ]
    for step in failed:
        lines.append(f"FAILED {' '.join(step['command'])}")
        lines.append(f"  code={step.get('error_code')} rc={step.get('returncode')}")
        tail = (step.get("stderr_tail") or "").strip()
        if tail:
            lines.append(f"  stderr: {tail[-400:]}")
    lines += [
        "",
        "Report only the proof path, the failed command, its validation errors, and the next repair owner.",
        "Do not implement a repair, retry the sequence, or mutate cron, config, runtime, canon, portfolio,",
        "capital, execution, brokerage, or account state. No external delivery or approval inference.",
    ]
    return "\n".join(lines)


def dispatch_wake(spec: JobSpec, message: str, *, timeout_seconds: int, dry_run: bool) -> dict[str, Any]:
    run_at_ms = int(time.time() * 1000)
    session_key = f"agent:main:cron:{spec.job_id}:run:{run_at_ms}"
    record: dict[str, Any] = {
        "dispatched": False,
        "dry_run": bool(dry_run),
        "session_key": session_key,
        "message_chars": len(message),
        "error_code": None,
    }
    if dry_run:
        record["error_code"] = "dry_run_not_dispatched"
        return record

    binary = shutil.which("openclaw")
    if not binary:
        record["error_code"] = "openclaw_cli_not_found"
        return record

    message_path = TMP / f"{spec.key}-wake-message.txt"
    try:
        ensure_workspace_path(message_path).parent.mkdir(parents=True, exist_ok=True)
        message_path.write_text(message, encoding="utf-8")
    except OSError as exc:
        record["error_code"] = "wake_message_write_failed"
        record["stderr_tail"] = str(exc)[-400:]
        return record
    record["message_path"] = rel(message_path)

    try:
        completed = subprocess.run(
            [
                binary, "agent",
                "--agent", "main",
                "--session-key", session_key,
                "--message-file", str(message_path),
                "--timeout", str(timeout_seconds),
                "--json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 60,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        record["error_code"] = "wake_dispatch_failed"
        record["error_type"] = type(exc).__name__
        return record

    record["returncode"] = completed.returncode
    record["dispatched"] = completed.returncode == 0
    record["dispatched_at_utc"] = utc_now()
    if completed.returncode != 0:
        record["error_code"] = "wake_dispatch_nonzero_exit"
        record["stderr_tail"] = (completed.stderr or "")[-400:]
    return record


def build_report(spec: JobSpec, steps: list[dict[str, Any]], structure: list[str], wake: dict[str, Any], started_at_utc: str) -> dict[str, Any]:
    failed = [step for step in steps if not step.get("ok")]
    errors = [f"spec_invalid:{problem}" for problem in structure]
    errors.extend(f"step_failed:{' '.join(step['command'])}:{step.get('error_code')}" for step in failed)
    return {
        "schema": SCHEMA,
        "job_key": spec.key,
        "job_id": spec.job_id,
        "title": spec.title,
        "started_at_utc": started_at_utc,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "operator_action": "MAIN_SESSION_REQUIRED" if errors else "NO_REPLY",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": STOP_LINES,
        "summary": {
            "declared_command_count": len(spec.commands),
            "executed_step_count": len(steps),
            "failed_step_count": len(failed),
            "failed_commands": [" ".join(step["command"]) for step in failed],
            "spec_problems": structure,
        },
        "steps": steps,
        "wake": wake,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
    }


def validate(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = list((report.get("validation") or {}).get("errors") or [])
    if report.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if report.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_mutated")
    summary = report.get("summary") or {}
    if summary.get("executed_step_count") != len(report.get("steps") or []):
        errors.append("step_count_mismatch")
    wake = report.get("wake") or {}
    if wake.get("dispatched") and not summary.get("failed_step_count"):
        errors.append("wake_dispatched_without_failure")
    return {"status": "blocked" if errors else "ok", "errors": sorted(set(errors)), "warnings": []}


def history_record(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    return {
        "generated_at_utc": report.get("generated_at_utc"),
        "job_key": report.get("job_key"),
        "status": report.get("status"),
        "failed_step_count": summary.get("failed_step_count"),
        "failed_commands": summary.get("failed_commands"),
        "wake_dispatched": (report.get("wake") or {}).get("dispatched"),
        "validation_status": (report.get("validation") or {}).get("status"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a declared deterministic cron command sequence.")
    parser.add_argument("--job", required=True, choices=sorted(JOB_SPECS))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--dry-run-wake", action="store_true", help="Decide but never wake Main.")
    parser.add_argument("--list-only", action="store_true", help="Validate the spec without executing it.")
    parser.add_argument("--wake-timeout", type=int, default=600)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spec = JOB_SPECS[args.job]
    started_at_utc = utc_now()
    structure = spec_errors(spec)

    if args.list_only:
        report = build_report(spec, [], structure, {"dispatched": False, "dry_run": True}, started_at_utc)
        report["validation"] = validate(report)
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
        return 1 if args.validate and report["validation"]["status"] != "ok" else 0

    steps = [] if structure else [run_command(command, spec.step_timeout) for command in spec.commands]
    failed = [step for step in steps if not step.get("ok")]

    if failed or structure:
        wake = dispatch_wake(
            spec,
            build_wake_message(spec, failed, spec.out),
            timeout_seconds=args.wake_timeout,
            dry_run=args.dry_run_wake,
        )
    else:
        wake = {"dispatched": False, "dry_run": False, "error_code": "wake_not_required"}

    report = build_report(spec, steps, structure, wake, started_at_utc)
    report["validation"] = validate(report)

    if args.write:
        atomic_write_json(spec.out, report)
        append_history(spec.history, history_record(report))

    print(json.dumps({
        "job_key": report["job_key"],
        "status": report["status"],
        "operator_action": report["operator_action"],
        "summary": report["summary"],
        "output": rel(spec.out),
    }, indent=2, sort_keys=True))

    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
