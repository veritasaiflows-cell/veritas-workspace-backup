#!/usr/bin/env python3
"""Changed-input gate for the deterministic OS audit companion refresh.

This command is the model-free cron entrypoint. It reuses the proven status-card
prefilter mechanics, but binds them to the six-step OS audit runner and its
review-only input manifest. Unchanged inputs may reuse a successful runner
output for at most 25 hours; changed, missing required, stale, or invalid proof
always runs the existing deterministic runner.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import status_card_freshness_predispatch_prefilter as common

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "os-audit-companion-refresh-predispatch-prefilter.json"
RUNNER_OUT = ROOT / "tmp" / "os-audit-companion-refresh-proof.json"
SCHEMA = "veritas.os_audit_companion_refresh_predispatch_prefilter.v1"
RUNNER_SCHEMA = "veritas.os_audit_companion_refresh_runner.v1"
MAX_REUSE_MINUTES = 1500
STEP_COUNT = 6

# Outputs written by this runner must never feed its own next input signature.
# Keeping one of these paths in the manifest creates a feedback loop where every
# successful refresh makes the following invocation look changed again.
RUNNER_OUTPUT_SOURCES = frozenset(
    {
        "tmp/tmp-lifecycle-guard.json",
        "tmp/tmp-artifact-spire.json",
        "tmp/token-budget-status.json",
        "tmp/security-warning-ledger.json",
        "tmp/wf78-promotion-visibility-top10.json",
        "tmp/pm-autonomy-verifier-health.json",
        "tmp/veritas-status-card.json",
        "tmp/veritas-status-card-frontdoor.json",
    }
)

# Reuse the already-reviewed status-card manifest and add the five OS companion
# producers that precede status-card generation. Exclude every artifact written
# by this six-step runner; true upstream sources (for example the token ledger,
# workflow state, doctrine, and producer code) remain hashed. This deliberately
# replaces the old whole-tmp/state/memory mtime walk, which was too noisy to
# support a real unchanged-input decision. The 25-hour reuse ceiling still
# forces a bounded refresh even when upstream hashes remain unchanged.
STATIC_INPUT_SOURCES = list(
    dict.fromkeys(
        [
            "scripts/os_audit_companion_refresh_runner.py",
            "scripts/os_audit_companion_refresh_predispatch_prefilter.py",
            "scripts/tmp_lifecycle_guard.py",
            "scripts/token_budget_status.py",
            "scripts/security_warning_ledger.py",
            "scripts/wf78_promotion_visibility_top10.py",
            "scripts/pm_autonomy_verifier.py",
            # WF84 is an active P0 guarded alert evidence capsule. Pin it here so
            # this gate's watched-source contract does not silently shrink when
            # the status card's input list is tuned for its own consumers.
            "state/workflows/WF84.json",
            *(
                source
                for source in common.STATIC_INPUT_SOURCES
                if str(source).replace("\\", "/") not in RUNNER_OUTPUT_SOURCES
            ),
        ]
    )
)
REQUIRED_INPUT_SOURCES = frozenset(
    {
        "scripts/os_audit_companion_refresh_runner.py",
        "scripts/os_audit_companion_refresh_predispatch_prefilter.py",
        "scripts/tmp_lifecycle_guard.py",
        "scripts/token_budget_status.py",
        "scripts/security_warning_ledger.py",
        "scripts/wf78_promotion_visibility_top10.py",
        "scripts/pm_autonomy_verifier.py",
        *(
            source
            for source in common.REQUIRED_INPUT_SOURCES
            if str(source).replace("\\", "/") not in RUNNER_OUTPUT_SOURCES
        ),
    }
)

AUTHORITY_BOUNDARY = {
    **common.AUTHORITY_BOUNDARY,
    "may_run_existing_status_card_runner": False,
    "may_run_existing_os_audit_companion_runner": True,
}
STOP_LINES = [
    "This wrapper does not edit cron, schedule, delivery, config, auth, credentials, or runtime settings.",
    "Execute mode may write only the existing six review-packet outputs through the existing runner.",
    "Do not treat skipped_unchanged as approval, finance judgment, cleanup authority, or indefinite freshness.",
    "The live cron payload is applied and rollback-protected through the separate owner-approved cron gate.",
]


def configure_common() -> None:
    common.OUT = OUT
    common.RUNNER_OUT = RUNNER_OUT
    common.SCHEMA = SCHEMA
    common.RUNNER_SCHEMA = RUNNER_SCHEMA
    common.MAX_REUSE_MINUTES = MAX_REUSE_MINUTES
    common.STATIC_INPUT_SOURCES = STATIC_INPUT_SOURCES
    common.REQUIRED_INPUT_SOURCES = REQUIRED_INPUT_SOURCES
    common.AUTHORITY_BOUNDARY = AUTHORITY_BOUNDARY
    common.STOP_LINES = STOP_LINES
    common.input_source_paths = input_source_paths
    common.runner_success = runner_success
    common.runner_output_summary = runner_output_summary


def input_source_paths(
    now: datetime,
    source_paths: Iterable[str | Path] | None = None,
) -> list[str | Path]:
    """Return stable named sources without the status gate's date rollover.

    Daily-memory freshness remains owned by the separate 30-minute Status Card
    job. Adding changing today/yesterday path names here would force this daily
    OS job to run on every natural trigger even when every named source hash was
    unchanged.
    """
    del now
    paths: list[str | Path] = list(STATIC_INPUT_SOURCES if source_paths is None else source_paths)
    seen: set[str] = set()
    unique: list[str | Path] = []
    for path in paths:
        key = str(path).replace("\\", "/")
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def runner_success(payload: dict[str, Any]) -> bool:
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != STEP_COUNT:
        return False
    if payload.get("schema") != RUNNER_SCHEMA or payload.get("status") != "ok":
        return False
    if payload.get("failed_at_step") is not None:
        return False
    for expected_index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            return False
        if type(result.get("index")) is not int or result.get("index") != expected_index:
            return False
        if type(result.get("exit_code")) is not int or result.get("exit_code") != 0:
            return False
    return True


def runner_output_summary(payload: dict[str, Any], now: datetime, max_reuse_minutes: int) -> dict[str, Any]:
    completed = common.parse_timestamp(payload.get("completed_at_utc") or payload.get("generated_at_utc"))
    age_seconds = (now.astimezone(timezone.utc) - completed).total_seconds() if completed else None
    fresh_enough = bool(completed and 0 <= age_seconds <= max_reuse_minutes * 60)
    success = runner_success(payload)
    return {
        "present": bool(payload),
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "steps_passed": STEP_COUNT if success else sum(
            1
            for result in payload.get("results", [])
            if isinstance(result, dict) and type(result.get("exit_code")) is int and result.get("exit_code") == 0
        ),
        "step_count": STEP_COUNT,
        "steps_failed": 0 if success else payload.get("failed_at_step"),
        "completed_at_utc": payload.get("completed_at_utc") or payload.get("generated_at_utc"),
        "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "success": success,
        "fresh_enough_for_reuse": fresh_enough,
        "reuse_window_minutes": max_reuse_minutes,
    }


def build_prefilter_report(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    proof_path: Path = OUT,
    runner_path: Path = RUNNER_OUT,
    max_reuse_minutes: int = MAX_REUSE_MINUTES,
    source_paths: Iterable[str | Path] | None = None,
    required_source_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    configure_common()
    report = common.build_prefilter_report(
        root=root,
        now=now,
        proof_path=proof_path,
        runner_path=runner_path,
        max_reuse_minutes=max_reuse_minutes,
        source_paths=source_paths,
        required_source_paths=required_source_paths,
    )
    report.update(
        {
            "job_name": "Runtime - OS Audit Companion Packets Refresh",
            "purpose": "Skip duplicate deterministic OS audit companion work only when explicit inputs are unchanged and the six-step runner proof remains fresh.",
            "authority_boundary": AUTHORITY_BOUNDARY,
            "stop_lines": STOP_LINES,
        }
    )
    report["source_artifacts"] = {
        "prefilter_proof": common.rel(common.resolve_path(proof_path, root), root),
        "runner_output": common.rel(common.resolve_path(runner_path, root), root),
        "existing_runner": "scripts/os_audit_companion_refresh_runner.py",
    }
    report["promotion_effect"] = {
        "existing_runner_path_unchanged": True,
        "scheduled_payload_kind": "command",
        "eliminates_scheduled_agent_turn": True,
        "model_or_agent_turn_on_changed_inputs": False,
        "model_or_agent_turn_on_unchanged_inputs": False,
    }
    report["execution_semantics"] = {
        "prefilter_writes_its_own_review_proof": True,
        "execute_mode_writes_existing_review_packets": True,
        "control_or_authority_state_mutation": False,
        "scheduled_agent_turn_occurs": False,
    }
    return report


def run_existing_runner(
    timeout_seconds: int = 720,
    root: Path = ROOT,
    runner_out: Path = RUNNER_OUT,
) -> dict[str, Any]:
    try:
        resolved_runner_out = common.ensure_workspace_path(runner_out, root)
    except ValueError:
        return {
            "command": None,
            "started_at_utc": common.utc_now(),
            "completed_at_utc": common.utc_now(),
            "duration_ms": 0,
            "returncode": None,
            "ok": False,
            "error_code": "runner_output_path_outside_workspace",
            "stdout_tail": "",
            "stderr_tail": "runner output must remain inside the workspace",
        }
    resolved_runner_out.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(common.resolve_path("scripts/os_audit_companion_refresh_runner.py", root)),
        "--write",
        "--validate",
    ]
    started = time.monotonic()
    started_at = common.utc_now()
    try:
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout_seconds)
        return {
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": common.utc_now(),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": completed.returncode,
            "ok": completed.returncode == 0 and resolved_runner_out.is_file(),
            "stdout_tail": (completed.stdout or "")[-2000:],
            "stderr_tail": (completed.stderr or "")[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": common.utc_now(),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }
    except (OSError, ValueError) as exc:
        return {
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": common.utc_now(),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": None,
            "ok": False,
            "error_code": "runner_launch_failed",
            "error_type": type(exc).__name__,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }


def finalize_runner_execution(
    report: dict[str, Any],
    execution: dict[str, Any],
    *,
    root: Path = ROOT,
    runner_path: Path = RUNNER_OUT,
    max_reuse_minutes: int = MAX_REUSE_MINUTES,
    now: datetime | None = None,
    source_paths: Iterable[str | Path] | None = None,
    required_source_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    configure_common()
    report = common.finalize_runner_execution(
        report,
        execution,
        root=root,
        runner_path=runner_path,
        max_reuse_minutes=max_reuse_minutes,
        now=now,
        source_paths=source_paths,
        required_source_paths=required_source_paths,
    )
    replacements = {
        "status_card_freshness_runner_output_not_reusable": "os_audit_companion_runner_output_not_reusable",
        "status_card_freshness_runner_output_invalid": "os_audit_companion_runner_output_invalid",
        "status_card_freshness_runner_failed": "os_audit_companion_runner_failed",
    }
    report["validation"]["errors"] = [replacements.get(error, error) for error in report["validation"].get("errors", [])]
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--prefilter-only", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--runner-out", type=Path, default=RUNNER_OUT)
    parser.add_argument("--max-reuse-minutes", type=int, default=MAX_REUSE_MINUTES)
    parser.add_argument("--timeout-seconds", type=int, default=720)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute and args.prefilter_only:
        raise SystemExit("--execute and --prefilter-only are mutually exclusive")
    if args.max_reuse_minutes <= 0 or args.timeout_seconds <= 0:
        raise SystemExit("reuse and timeout values must be positive")
    try:
        args.out = common.ensure_workspace_path(args.out, ROOT)
        args.runner_out = common.ensure_workspace_path(args.runner_out, ROOT)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    report = build_prefilter_report(
        proof_path=args.out,
        runner_path=args.runner_out,
        max_reuse_minutes=args.max_reuse_minutes,
    )
    if report["status"] == "run_required" and args.execute and not args.prefilter_only:
        report = finalize_runner_execution(
            report,
            run_existing_runner(args.timeout_seconds, root=ROOT, runner_out=args.runner_out),
            root=ROOT,
            runner_path=args.runner_out,
            max_reuse_minutes=args.max_reuse_minutes,
        )
    if args.write:
        common.atomic_write_json(args.out, report)
    if args.print_json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"status={report['status']} action={report['action']} "
            f"source_unchanged={report['source_unchanged']} "
            f"runner_success={report['runner_output']['success']}"
        )
    return 1 if args.validate and report["status"] == "blocked" else 0


configure_common()

if __name__ == "__main__":
    raise SystemExit(main())
