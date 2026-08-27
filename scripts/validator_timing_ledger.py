#!/usr/bin/env python3
"""Run budgeted validators and record timing.

The normal profile is intentionally small: it proves the current control-plane
fast path without paying DB lifecycle or WF75 major closeout costs. Shared and
major profiles are explicit opt-ins.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "validator-timing-ledger.json"

SCHEMA = "veritas.validator_timing_ledger.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "validation_timing_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def scoped_router_cmd(paths: list[str]) -> list[str]:
    command = py_cmd("scripts\\changed_file_validator_router.py")
    for path in paths:
        command.extend(["--path", path])
    command.extend(["--write", "--validate"])
    return command


COMMANDS: dict[str, tuple[list[str], int, str]] = {
    "py_compile_control_plane": (
        py_cmd(
            "-m",
            "py_compile",
            "scripts\\pm_control_packet.py",
            "scripts\\cron_control_packet.py",
            "scripts\\otel_ops_control.py",
            "scripts\\changed_file_validator_router.py",
            "scripts\\validator_timing_ledger.py",
            "scripts\\fast_path_qa.py",
            "scripts\\repeatable_work_closeout.py",
            "scripts\\control_closeout_bundle.py",
        ),
        45,
        "micro",
    ),
    "pm_control_packet": (py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 120, "narrow"),
    "cron_control_packet": (py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 120, "narrow"),
    "otel_ops_control": (py_cmd("scripts\\otel_ops_control.py", "--write", "--write-db", "--validate"), 120, "shared"),
    "changed_file_validator_router": (py_cmd("scripts\\changed_file_validator_router.py", "--write", "--validate"), 45, "narrow"),
    "fast_path_qa_no_probes": (py_cmd("scripts\\fast_path_qa.py", "--write", "--validate", "--no-probes"), 120, "narrow"),
    "repeatable_work_closeout_narrow": (
        py_cmd("scripts\\repeatable_work_closeout.py", "--validation-budget", "narrow", "--write", "--validate"),
        300,
        "shared",
    ),
    "control_closeout_bundle_shared": (
        py_cmd("scripts\\control_closeout_bundle.py", "--validation-budget", "shared", "--write", "--validate"),
        900,
        "shared",
    ),
    "db_lifecycle_manifest": (py_cmd("scripts\\db_lifecycle_manifest.py", "--write", "--validate"), 900, "major"),
    "wf75_closeout_refresh_major": (
        py_cmd("scripts\\wf75_closeout_refresh.py", "--mode", "handoff-only", "--validation-budget", "major", "--write", "--validate"),
        900,
        "major",
    ),
}

PROFILES: dict[str, list[str]] = {
    "normal": [
        "py_compile_control_plane",
        "pm_control_packet",
        "cron_control_packet",
        "changed_file_validator_router",
        "fast_path_qa_no_probes",
    ],
    "shared": [
        "py_compile_control_plane",
        "pm_control_packet",
        "cron_control_packet",
        "otel_ops_control",
        "changed_file_validator_router",
        "fast_path_qa_no_probes",
        "repeatable_work_closeout_narrow",
        "control_closeout_bundle_shared",
    ],
    "major": [
        "py_compile_control_plane",
        "pm_control_packet",
        "cron_control_packet",
        "otel_ops_control",
        "changed_file_validator_router",
        "fast_path_qa_no_probes",
        "repeatable_work_closeout_narrow",
        "control_closeout_bundle_shared",
        "db_lifecycle_manifest",
        "wf75_closeout_refresh_major",
    ],
}

TARGET_SECONDS = {
    "normal": 10.0,
    "shared": 40.0,
    "major": 120.0,
}

STRICT_COMMANDS = {
    "py_compile_control_plane",
}


def run_command(name: str, command: list[str], timeout: int, dry_run: bool, samples: int = 1) -> dict[str, Any]:
    if dry_run:
        return {
            "name": name,
            "command": command,
            "ok": True,
            "skipped": True,
            "elapsed_seconds": 0.0,
            "returncode": 0,
        }
    attempts = [measure_once(name, command, timeout) for _ in range(max(1, samples))]
    failed = [item for item in attempts if not item.get("ok")]
    result = failed[0] if failed else attempts[0]
    timings = [float(item.get("elapsed_seconds") or 0.0) for item in attempts]
    result["elapsed_seconds"] = round(statistics.median(timings), 3)
    result["sample_count"] = len(attempts)
    result["elapsed_samples"] = timings
    if len(attempts) > 1:
        result["elapsed_min_seconds"] = round(min(timings), 3)
        result["elapsed_max_seconds"] = round(max(timings), 3)
    return result


def measure_once(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    start = time.perf_counter()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        elapsed = round(time.perf_counter() - start, 3)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "elapsed_seconds": elapsed,
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "failure_kind": None if proc.returncode == 0 else "nonzero_returncode",
            "stdout_preview": proc.stdout.strip()[-1200:],
            "stderr_preview": proc.stderr.strip()[-1200:],
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - start, 3)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "elapsed_seconds": elapsed,
            "returncode": None,
            "ok": False,
            "failure_kind": "timeout",
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-1200:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def build_payload(
    profile: str,
    dry_run: bool,
    strict_command_status: bool = False,
    scoped_paths: list[str] | None = None,
    samples: int = 1,
) -> dict[str, Any]:
    selected = PROFILES[profile]
    scoped_paths = scoped_paths or []
    samples = max(1, samples)
    results = []
    for name in selected:
        command, timeout, budget = COMMANDS[name]
        if name == "changed_file_validator_router" and scoped_paths:
            command = scoped_router_cmd(scoped_paths)
        result = run_command(name, command, timeout, dry_run, samples=samples)
        result["budget"] = budget
        results.append(result)
    failed = [item["name"] for item in results if not item.get("ok")]
    timing_collection_failures = [
        item["name"]
        for item in results
        if not item.get("ok") and (strict_command_status or item.get("failure_kind") == "timeout" or item.get("name") in STRICT_COMMANDS)
    ]
    measured_validator_failures = [
        item["name"]
        for item in results
        if not item.get("ok") and item["name"] not in timing_collection_failures
    ]
    total = round(sum(float(item.get("elapsed_seconds") or 0.0) for item in results), 3)
    slow = total > TARGET_SECONDS[profile]
    # A single wall-clock sample cannot separate a real regression from host noise,
    # so downstream WF74 routing must not treat it as a confirmed drag finding.
    measurement_confidence = "median_of_samples" if samples > 1 else "single_sample_variance_unbounded"
    warnings = []
    if slow and not timing_collection_failures:
        warnings.append(f"profile_elapsed_over_target:{total}>{TARGET_SECONDS[profile]}")
        if samples <= 1:
            warnings.append("profile_elapsed_over_target_single_sample_unconfirmed")
    warnings.extend(f"measured_validator_failed:{name}" for name in measured_validator_failures)
    status = "blocked" if timing_collection_failures else "warning" if warnings else "ok"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "profile": profile,
        "target_seconds": TARGET_SECONDS[profile],
        "dry_run": dry_run,
        "strict_command_status": strict_command_status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "commands_run": len(results),
            "elapsed_seconds": total,
            "target_seconds": TARGET_SECONDS[profile],
            "sample_count": samples,
            "measurement_confidence": measurement_confidence,
            "over_target_confirmed": bool(slow and samples > 1),
            "scoped_path_count": len(scoped_paths),
            "scoped_paths": scoped_paths,
            "failed_commands": failed,
            "measured_validator_failures": measured_validator_failures,
            "timing_collection_failures": timing_collection_failures,
            "slow": slow,
            "reserved_for_major": [
                "db_lifecycle_manifest.py --write --validate",
                "wf75_closeout_refresh.py --mode handoff-only --validation-budget major --write --validate",
            ],
            "next_safe_action": (
                "Use scoped paths for narrow patch-plan timing; run shared or major only when changed-file routing recommends it."
                if scoped_paths
                else "Use normal profile for low/narrow control-plane edits; run shared or major only when changed-file routing recommends it."
            ),
        },
        "commands": results,
        "validation": {
            "status": status,
            "errors": timing_collection_failures,
            "warnings": warnings,
        },
        "stop_lines": [
            "Timing ledger runs local validators only. It does not mutate canon/portfolio state, runtime config, cron schedules, accounts, archives, customer surfaces, or execution surfaces.",
        ],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a budgeted validator timing profile.")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="normal")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Report selected commands without running them.")
    parser.add_argument("--path", action="append", dest="path_args", help="Explicit path for scoped changed-file routing; may be repeated.")
    parser.add_argument("--paths", nargs="*", dest="paths_args", help="Explicit paths for scoped changed-file routing.")
    parser.add_argument(
        "--strict-command-status",
        action="store_true",
        help="Treat any measured validator nonzero return code as a timing-ledger validation error.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=1,
        help="Run each validator N times and record the median; N>1 is required to confirm an over-target finding.",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    scoped_paths = [*(args.path_args or []), *(args.paths_args or [])]
    payload = build_payload(
        args.profile,
        dry_run=args.dry_run,
        strict_command_status=args.strict_command_status,
        scoped_paths=scoped_paths,
        samples=args.samples,
    )
    if args.write:
        atomic_write_json(args.out, payload)
        print(f"wrote {rel(args.out)} status={payload['status']} elapsed={payload['summary']['elapsed_seconds']}s profile={args.profile}")
    else:
        print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] not in {"ok", "warning"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
