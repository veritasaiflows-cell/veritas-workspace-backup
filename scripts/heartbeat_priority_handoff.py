#!/usr/bin/env python3
"""Fail-closed heartbeat-to-main priority handoff.

This is the only supported heartbeat bridge for current-window, ticker-debt,
and cron-residue priorities.  It accepts no execution, context, lane, agent,
or scheduler flags and invokes both downstream consumers in heartbeat dry-run
mode with fixed argv.  It writes a small receipt that main session can claim.
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
OUT = TMP / "heartbeat-priority-receipt.json"
CONSUMER_OUT = TMP / "heartbeat-main-session-escalation-consumer.json"
PRIORITY_OUT = TMP / "heartbeat-main-session-priority-handoff.json"
SCHEMA = "veritas.heartbeat_priority_receipt.v1"
AUTHORITY_BOUNDARY = {
    "review_only": True,
    "heartbeat_may_execute": False,
    "heartbeat_may_spawn_helper": False,
    "heartbeat_may_lease_lane": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def run_step(name: str, command: list[str], timeout: int = 300) -> dict[str, Any]:
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
            "stdout_preview": proc.stdout.strip()[-1200:],
            "stderr_preview": proc.stderr.strip()[-1200:],
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
            "stdout_preview": (exc.stdout or "")[-1200:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def fixed_steps() -> list[tuple[str, list[str]]]:
    return [
        (
            "main_session_escalation_consumer",
            [
                sys.executable,
                "scripts\\main_session_escalation_consumer.py",
                "--context",
                "heartbeat",
                "--write",
                "--validate",
                "--priority-observation-source",
                "heartbeat",
                "--out",
                rel(CONSUMER_OUT),
                "--priority-out",
                rel(PRIORITY_OUT),
            ],
        ),
    ]


def validate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if receipt.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    expected_steps = fixed_steps()
    actual_steps = [
        (str(as_dict(step).get("name") or ""), [str(part) for part in as_dict(step).get("command") or []])
        for step in receipt.get("steps") or []
    ]
    if actual_steps != expected_steps:
        errors.append("fixed_heartbeat_commands_changed")
    for step in receipt.get("steps") or []:
        if as_dict(step).get("ok") is not True:
            errors.append(f"step_failed:{as_dict(step).get('name')}")
    consumer = as_dict(receipt.get("consumer"))
    priority = as_dict(receipt.get("priority_handoff"))
    if consumer.get("context") != "heartbeat" or consumer.get("mode") != "dry_run":
        errors.append("consumer_not_heartbeat_dry_run")
    if consumer.get("execution_results"):
        errors.append("consumer_executed_actions")
    expected_sources = {
        "consumer": rel(CONSUMER_OUT),
        "priority_handoff": rel(PRIORITY_OUT),
    }
    if as_dict(receipt.get("source_artifacts")) != expected_sources:
        errors.append("heartbeat_source_artifacts_changed")
    if as_dict(priority.get("validation")).get("status") != "ok":
        errors.append("priority_handoff_invalid")
    if priority.get("receipt") not in {"NO_DELTA", "NEW_PRIORITY", "ESCALATED_PRIORITY", "BLOCKED"}:
        errors.append("priority_receipt_invalid")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []}


def build_receipt() -> dict[str, Any]:
    steps = [run_step(name, command) for name, command in fixed_steps()]
    consumer = load(CONSUMER_OUT)
    priority_handoff = load(PRIORITY_OUT)
    receipt = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Heartbeat-only priority receipt; detect and route to main session without workflow, repair, helper, lane, or execution advancement.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "steps": steps,
        "source_artifacts": {
            "consumer": rel(CONSUMER_OUT),
            "priority_handoff": rel(PRIORITY_OUT),
        },
        "consumer": {
            "status": consumer.get("status"),
            "mode": consumer.get("mode"),
            "context": consumer.get("context"),
            "execution_results": consumer.get("execution_results") or [],
            "summary": consumer.get("summary") or {},
        },
        "priority_handoff": priority_handoff,
        "receipt": priority_handoff.get("receipt") or "BLOCKED",
        "stop_lines": [
            "No --execute-safe, --execute-one, lane lease, helper spawn, cron context, or scheduler/runtime mutation is accepted by this heartbeat bridge.",
            "A priority receipt is a main-session review handoff, not repair, canon, portfolio, execution, account, or capital authority.",
        ],
    }
    receipt["validation"] = validate_receipt(receipt)
    receipt["status"] = "blocked" if receipt["validation"]["status"] != "ok" else (
        "needs_main_review" if priority_handoff.get("status") == "needs_main_review" else "ok"
    )
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fixed heartbeat priority handoff only.", allow_abbrev=False)
    parser.add_argument("--write", action="store_true", help="Write the heartbeat priority receipt.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero when the fixed dry-run bridge is invalid.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.write:
        print("--write is required; this bridge persists the reviewed heartbeat receipt", file=sys.stderr)
        return 2
    receipt = build_receipt()
    atomic_write_json(OUT, receipt, indent=2)
    print(
        f"wrote {rel(OUT)} status={receipt['status']} receipt={receipt['receipt']} "
        f"validation={receipt['validation']['status']}"
    )
    if args.validate and receipt["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
