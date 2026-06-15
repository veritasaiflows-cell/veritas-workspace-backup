#!/usr/bin/env python3
"""Cron wrapper for the WF74 learning-loop Telegram digest."""
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
OUT = TMP / "wf74-learning-loop-telegram-cron-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "telegram_delivery_allowed": True,
    "cron_wrapper_only": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def py(*args: str) -> list[str]:
    return [sys.executable, *args]


def run_step(name: str, command: list[str], timeout: int, required: bool = True) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        ok = proc.returncode == 0
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": ok,
            "required": required,
            "stdout_tail": proc.stdout[-2500:],
            "stderr_tail": proc.stderr[-1500:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "required": required,
            "timeout_seconds": timeout,
            "stdout_tail": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def build_runner(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    steps.append(run_step("wf74_model_quality_collection_cron_runner", py("scripts\\wf74_model_quality_collection_cron_runner.py", "--write", "--write-md", "--validate"), 180))
    digest_command = [
        "scripts\\wf74_learning_loop_telegram_digest.py",
        "--write",
        "--validate",
        "--after-6pm-only",
    ]
    if args.send:
        digest_command.append("--send")
    if args.force:
        digest_command.append("--force")
    steps.append(run_step("wf74_learning_loop_telegram_digest", py(*digest_command), 90))
    steps.append(run_step("cron_freshness_spine", py("scripts\\cron_freshness_spine.py", "--write", "--validate"), 120))
    steps.append(run_step("cron_control_packet", py("scripts\\cron_control_packet.py", "--write", "--validate"), 120))

    failed = [step for step in steps if step["required"] and not step["ok"]]
    digest = load_dict(TMP / "wf74-learning-loop-telegram-digest.json")
    runner = load_dict(TMP / "wf74-model-quality-collection-cron-runner.json")
    status = "ok" if not failed else "blocked"
    errors: list[str] = []
    if failed:
        errors.extend(f"required_step_failed:{step['name']}" for step in failed)
    if digest.get("validation", {}).get("status") not in {None, "ok"}:
        errors.append("telegram_digest_validation_not_ok")
    if digest.get("status") == "blocked":
        errors.append("telegram_digest_blocked")

    return {
        "schema": "veritas.wf74_learning_loop_telegram_cron_runner.v1",
        "generated_at_utc": utc_now(),
        "status": status if not errors else "blocked",
        "mode": "send" if args.send else "dry_run",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "step_count": len(steps),
            "failed_step_count": len(failed),
            "wf74_runner_status": runner.get("status"),
            "wf74_runner_validation": runner.get("validation", {}).get("status"),
            "digest_status": digest.get("status"),
            "digest_operator_action": digest.get("operator_action"),
            "digest_trigger_reason": digest.get("trigger_reason"),
            "digest_sent_count": digest.get("sent_count"),
            "opportunity_count": digest.get("summary", {}).get("opportunity_count"),
            "high_priority_count": digest.get("summary", {}).get("high_priority_count"),
            "proposal_count": digest.get("summary", {}).get("proposal_count"),
            "owner_decision_required_count": digest.get("summary", {}).get("owner_decision_required_count"),
            "auto_apply_count": digest.get("summary", {}).get("auto_apply_count"),
        },
        "steps": steps,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": [
                "telegram_delivery_only",
                "wf74_digest_may_surface_owner_gates_but_never_applies_changes",
            ],
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WF74 learning-loop Telegram digest cron chain.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_runner(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        atomic_write_json(output, packet)
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        print(json.dumps({"status": "blocked", "errors": packet["validation"]["errors"], "output": rel(output)}, indent=2))
        return 1
    print(json.dumps({
        "status": packet["status"],
        "mode": packet["mode"],
        "summary": packet["summary"],
        "output": rel(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
