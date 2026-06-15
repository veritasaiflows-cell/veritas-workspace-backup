#!/usr/bin/env python3
"""Run the standard repeatable-work closeout chain.

This wrapper removes manual command choreography from WF72/WF73/WF78 closeout.
It refreshes route/scorer/rerouting/inventory/QA/index/PM control proof in the
validated order. It does not execute trades, mutate canon/portfolio state,
infer approval, or perform archive/delete/config/runtime changes.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "repeatable-work-closeout.json"
SCHEMA = "veritas.repeatable_work_closeout.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "closeout_validation_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
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


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


FULL_CHAIN: list[tuple[str, list[str], int]] = [
    ("workflow_routing_index", py_cmd("scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"), 180),
    ("artifact_intelligence_action_scorer", py_cmd("scripts\\artifact_intelligence_action_scorer.py", "--write", "--validate"), 180),
    ("wf78_event_triggered_rerouting", py_cmd("scripts\\wf78_event_triggered_rerouting.py", "--write", "--write-db", "--validate"), 180),
    ("truth_surface_inventory", py_cmd("scripts\\truth_surface_inventory.py", "--write", "--validate"), 180),
    ("pm_sidecar_retirement_guard", py_cmd("scripts\\pm_sidecar_retirement_guard.py", "--write", "--validate"), 180),
    ("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180),
    ("otel_ops_control", py_cmd("scripts\\otel_ops_control.py", "--write", "--write-db", "--validate"), 120),
    ("changed_file_validator_router", py_cmd("scripts\\changed_file_validator_router.py", "--write", "--validate"), 120),
    ("fast_path_qa", py_cmd("scripts\\fast_path_qa.py", "--write", "--validate"), 180),
    ("artifact_index_incremental", py_cmd("scripts\\artifact_index.py", "incremental"), 240),
    ("artifact_index_validate", py_cmd("scripts\\artifact_index.py", "validate"), 240),
    ("pm_control_packet", py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 240),
]


def chain_for_budget(validation_budget: str) -> list[tuple[str, list[str], int]]:
    if validation_budget in {"micro", "narrow"}:
        return [
            ("workflow_routing_index", py_cmd("scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"), 180),
            ("pm_sidecar_retirement_guard", py_cmd("scripts\\pm_sidecar_retirement_guard.py", "--write", "--validate"), 180),
            ("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180),
            ("otel_ops_control", py_cmd("scripts\\otel_ops_control.py", "--write", "--write-db", "--validate"), 120),
            ("changed_file_validator_router", py_cmd("scripts\\changed_file_validator_router.py", "--write", "--validate"), 120),
            ("fast_path_qa", py_cmd("scripts\\fast_path_qa.py", "--write", "--validate", "--no-probes"), 180),
            ("pm_control_packet", py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 240),
        ]
    if validation_budget == "shared":
        return [
            step for step in FULL_CHAIN
            if step[0] not in {"artifact_index_incremental", "artifact_index_validate"}
        ]
    return FULL_CHAIN


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
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
            "stdout_preview": proc.stdout.strip()[-4000:],
            "stderr_preview": proc.stderr.strip()[-3000:],
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
            "stdout_preview": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else "",
        }


def build_report(stop_on_failure: bool, validation_budget: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    chain = chain_for_budget(validation_budget)
    for name, command, timeout in chain:
        step = run_step(name, command, timeout)
        steps.append(step)
        if stop_on_failure and not step["ok"]:
            break
    failed = [step["name"] for step in steps if not step["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not failed else "blocked",
        "validation_budget": validation_budget,
        "purpose": "Standard closeout chain for repeatable parallel work.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "steps_expected": len(chain),
            "steps_run": len(steps),
            "failed_steps": failed,
            "next_safe_action": "If ok, use fast-path QA and PM state as pickup proof; if blocked, inspect the first failed step only.",
        },
        "steps": steps,
        "validation": {
            "status": "ok" if not failed else "blocked",
            "errors": failed,
            "warnings": [],
        },
        "stop_lines": [
            "Closeout is validation/proof only; no archive/delete, config/auth/runtime mutation, canon/portfolio mutation, customer output, paper/live/account action, money movement, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeatable-work closeout chain.")
    parser.add_argument("--write", action="store_true", help="Write closeout artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on blocked closeout.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Run all steps even if one fails.")
    parser.add_argument("--skip-post-write-pm-refresh", action="store_true", help="Do not refresh PM control packet after the closeout artifact is written.")
    parser.add_argument("--validation-budget", choices=["micro", "narrow", "shared", "major"], default="shared")
    args = parser.parse_args()

    report = build_report(stop_on_failure=not args.continue_on_failure, validation_budget=args.validation_budget)
    if args.write:
        atomic_write_json(OUT, report)
        if report["status"] == "ok" and not args.skip_post_write_pm_refresh:
            post_step = run_step(
                "post_write_pm_control_packet",
                py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"),
                240,
            )
            report["steps"].append(post_step)
            report["summary"]["steps_run"] = len(report["steps"])
            if not post_step["ok"]:
                report["status"] = "blocked"
                report["summary"]["failed_steps"] = [*report["summary"]["failed_steps"], post_step["name"]]
                report["validation"]["status"] = "blocked"
                report["validation"]["errors"] = [*report["validation"]["errors"], post_step["name"]]
            atomic_write_json(OUT, report)
        print(f"wrote {rel(OUT)} status={report['status']} steps={report['summary']['steps_run']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
