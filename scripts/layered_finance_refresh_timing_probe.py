from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import layered_finance_refresh_chain as layered
from chain_manifest import window_names
from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKSPACE / "scripts"
OUT = WORKSPACE / "tmp" / "layered-finance-refresh-timing-probe.json"
SCHEMA_VERSION = "layered-finance-refresh-timing-probe-v1"

AUTHORITY_BOUNDARY = {
    "review_only_timing_probe": True,
    "dry_run_only": True,
    "runs_finance_chain_steps": False,
    "cron_enabled": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_execution_allowed": False,
    "live_execution_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}


@dataclass(frozen=True)
class TimedResult:
    command: tuple[str, ...]
    duration_ms: float
    returncode: int
    stdout_tail: str
    stderr_tail: str

    def to_json(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "duration_ms": round(self.duration_ms, 3),
            "returncode": self.returncode,
            "stdout_tail": self.stdout_tail[-2000:],
            "stderr_tail": self.stderr_tail[-2000:],
        }


Runner = Callable[[tuple[str, ...], int], TimedResult]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_timed_command(command: tuple[str, ...], timeout_seconds: int) -> TimedResult:
    started = time.perf_counter()
    proc = subprocess.run(
        list(command),
        cwd=str(WORKSPACE),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    return TimedResult(
        command=command,
        duration_ms=duration_ms,
        returncode=int(proc.returncode),
        stdout_tail=proc.stdout[-2000:],
        stderr_tail=proc.stderr[-2000:],
    )


def serial_command(window: str) -> tuple[str, ...]:
    return (sys.executable, str(SCRIPTS_DIR / "run_finance_refresh_chain.py"), window, "--dry-run")


def layered_command(window: str, max_workers: int) -> tuple[str, ...]:
    return (
        sys.executable,
        str(SCRIPTS_DIR / "layered_finance_refresh_chain.py"),
        window,
        "--dry-run",
        "--skip-mutating",
        "--max-workers",
        str(max_workers),
        "--write",
        "--validate",
    )


def build_window_probe(window: str, *, max_workers: int, timeout_seconds: int, runner: Runner) -> dict[str, Any]:
    serial = runner(serial_command(window), timeout_seconds)
    layered_result = runner(layered_command(window, max_workers), timeout_seconds)
    layered_plan = layered.build_payload(window, max_workers=max_workers, skip_mutating=True)
    serial_step_count = layered_plan["summary"]["original_step_count"]
    layered_step_count = layered_plan["summary"]["step_count"]
    return {
        "window": window,
        "serial_dry_run": serial.to_json(),
        "layered_read_only_dry_run": layered_result.to_json(),
        "layered_read_only_summary": layered_plan["summary"],
        "layered_read_only_validation": layered_plan["validation"],
        "speed_ratio_serial_over_layered": (
            round(serial.duration_ms / layered_result.duration_ms, 4) if layered_result.duration_ms else None
        ),
        "step_delta": serial_step_count - layered_step_count,
        "status": "ok" if serial.returncode == 0 and layered_result.returncode == 0 else "error",
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = payload.get("authority_boundary") or {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for window in payload.get("windows", []):
        if window.get("status") != "ok":
            errors.append(f"window_probe_failed:{window.get('window')}")
        summary = window.get("layered_read_only_summary") or {}
        if summary.get("mutating_step_count") != 0:
            errors.append(f"read_only_profile_has_mutating_steps:{window.get('window')}")
        if summary.get("skipped_mutating_step_count", 0) <= 0:
            warnings.append(f"no_mutating_steps_skipped:{window.get('window')}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(windows: list[str], *, max_workers: int, timeout_seconds: int, runner: Runner = run_timed_command) -> dict[str, Any]:
    results = [
        build_window_probe(window, max_workers=max_workers, timeout_seconds=timeout_seconds, runner=runner)
        for window in windows
    ]
    payload = {
        "schema": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "status": "draft",
        "windows_requested": windows,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "window_count": len(results),
            "ok_window_count": sum(1 for row in results if row.get("status") == "ok"),
            "max_workers": max_workers,
            "dry_run_only": True,
            "cron_update_recommended": False,
        },
        "windows": results,
        "stop_lines": [
            "Timing probe runs dry-runs only; it does not execute finance chain steps.",
            "Layered execution remains opt-in and not wired to cron by this proof.",
            "No canon/portfolio mutation, paper/live/account action, capital approval, or owner approval inference.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare serial dry-run planning with layered read-only dry-run planning.")
    parser.add_argument("--window", action="append", choices=window_names(), dest="windows")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    windows = args.windows or ["morning", "post-close"]
    payload = build_payload(windows, max_workers=args.max_workers, timeout_seconds=args.timeout_seconds)
    out = args.out if args.out.is_absolute() else WORKSPACE / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({"status": payload["status"], "summary": payload["summary"], "validation": payload["validation"]}, indent=2))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
