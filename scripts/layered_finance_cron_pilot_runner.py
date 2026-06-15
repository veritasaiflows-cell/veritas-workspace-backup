from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chain_manifest import window_names
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "tmp" / "layered-finance-cron-pilot-runner.json"
SCHEMA_VERSION = "layered-finance-cron-pilot-runner-v1"

AUTHORITY_BOUNDARY = {
    "review_only_cron_pilot": True,
    "dry_run_only": True,
    "runs_finance_chain_steps": False,
    "mutating_steps_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_execution_allowed": False,
    "live_execution_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def run_command(command: list[str], timeout_seconds: int) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return {
        "command": command,
        "returncode": int(proc.returncode),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def layered_plan_path(window: str) -> Path:
    return ROOT / "tmp" / f"layered-finance-refresh-chain-plan-{window}.json"


def run_window(window: str, *, max_workers: int, timeout_seconds: int) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SCRIPTS / "layered_finance_refresh_chain.py"),
        window,
        "--dry-run",
        "--skip-mutating",
        "--max-workers",
        str(max_workers),
        "--write",
        "--validate",
    ]
    result = run_command(command, timeout_seconds)
    plan = load_json(layered_plan_path(window))
    summary = as_dict(plan.get("summary"))
    validation = as_dict(plan.get("validation"))
    blockers: list[str] = []
    if result["returncode"] != 0:
        blockers.append(f"command_returncode={result['returncode']}")
    if validation.get("status") != "ok":
        blockers.append(f"plan_validation={validation.get('status')}")
    if int(summary.get("mutating_step_count") or 0):
        blockers.append("read_only_profile_contains_mutating_steps")
    return {
        "window": window,
        "status": "ok" if not blockers else "blocked",
        "command_result": result,
        "plan_path": rel(layered_plan_path(window)),
        "plan_summary": summary,
        "plan_validation": validation,
        "blockers": blockers,
    }


def build_payload(windows: list[str], *, max_workers: int, timeout_seconds: int) -> dict[str, Any]:
    window_results = [run_window(window, max_workers=max_workers, timeout_seconds=timeout_seconds) for window in windows]
    payload = {
        "schema": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "status": "draft",
        "windows": window_results,
        "scorecard_refresh": None,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "window_count": len(window_results),
            "ok_window_count": sum(1 for item in window_results if item["status"] == "ok"),
            "max_workers": max_workers,
            "dry_run_only": True,
            "mutating_step_count": sum(int(as_dict(item.get("plan_summary")).get("mutating_step_count") or 0) for item in window_results),
            "cron_update_recommended": False,
            "scorecard_refreshed": False,
        },
        "stop_lines": [
            "Cron pilot runs layered dry-runs only; it does not execute finance chain steps.",
            "Mutating/apply steps and their downstream dependents stay skipped.",
            "No canon/portfolio mutation, paper/live/account action, capital approval, or owner approval inference.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for window in payload.get("windows") or []:
        if window.get("status") != "ok":
            errors.append(f"window_blocked:{window.get('window')}")
    summary = as_dict(payload.get("summary"))
    if int(summary.get("mutating_step_count") or 0):
        errors.append("mutating_steps_present_in_cron_pilot")
    scorecard = payload.get("scorecard_refresh")
    if scorecard and scorecard.get("returncode") != 0:
        warnings.append("scorecard_refresh_failed")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run layered finance refresh dry-run pilot for cron advancement proof.")
    parser.add_argument("--window", action="append", choices=window_names(), dest="windows")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--skip-scorecard", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    windows = args.windows or ["morning", "post-close"]
    payload = build_payload(
        windows,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if not args.skip_scorecard:
        payload["scorecard_refresh"] = run_command(
            [
                sys.executable,
                str(SCRIPTS / "workflow_advancement_scorecard.py"),
                "--write",
                "--validate",
            ],
            args.timeout_seconds,
        )
        payload["summary"]["scorecard_refreshed"] = payload["scorecard_refresh"].get("returncode") == 0
        payload["validation"] = validate(payload)
        payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
        if args.write:
            atomic_write_json(out, payload)
    print(json.dumps({"status": payload["status"], "summary": payload["summary"], "validation": payload["validation"]}, indent=2))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
