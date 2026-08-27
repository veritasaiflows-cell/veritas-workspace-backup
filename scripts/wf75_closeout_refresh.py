#!/usr/bin/env python3
"""Refresh WF75 handoff/control surfaces after meaningful WF75 work.

This wrapper turns the manual closeout discipline into one repeatable command.
It regenerates WF75 service/PM/operator proof and the consolidated PM control
packet. It is still review-only: no
customer data, launch, external delivery, SQL import, canon/portfolio mutation,
archive/delete, paper/live/account action, or owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf75-closeout-refresh.json"
DEFAULT_SCENARIO_ID = "anon-risk-freshness-edge-cases-v1"

SCHEMA = "veritas.wf75_closeout_refresh.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
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


def command_plan(scenario_id: str, mode: str, validation_budget: str) -> list[list[str]]:
    full = [
        ["python", "scripts\\generic_intelligence_saas_pivot.py", "--write", "--write-db", "--validate"],
        ["python", "scripts\\wf77_supplemental_price_evidence.py", "--write", "--validate"],
        ["python", "scripts\\wf77_price_freshness_bridge.py", "--write", "--validate"],
        ["python", "scripts\\macro_event_calendar.py", "--write", "--validate"],
        ["python", "scripts\\wf75_scenario_template_library.py", "--write", "--validate"],
        ["python", "scripts\\wf75_renderer_export_regression.py", "--write", "--validate"],
        ["python", "scripts\\wf75_service_state.py", "--scenario-id", scenario_id, "--write", "--validate"],
        ["python", "scripts\\wf75_service_state_sqlite.py", "--write", "--validate"],
        ["python", "scripts\\wf75_operator_console.py", "--write", "--validate"],
        ["python", "scripts\\veritas_pm_department_validate.py", "--write"],
        ["python", "scripts\\operator_packet.py", "--workflow", "all", "--write", "--validate"],
        ["python", "scripts\\wf75_artifact_only_pm_handoff.py", "--write", "--validate"],
        ["python", "scripts\\wf75_pm_weekly_update.py", "--write", "--validate"],
        ["python", "scripts\\wf75_pm_readiness_pdf.py", "--write", "--validate"],
        ["python", "scripts\\wf75_operator_console.py", "--write", "--validate"],
    ]
    handoff_only = [
        ["python", "scripts\\generic_intelligence_saas_pivot.py", "--write", "--write-db", "--validate"],
        ["python", "scripts\\wf75_operator_console.py", "--write", "--validate"],
        ["python", "scripts\\veritas_pm_department_validate.py", "--write"],
        ["python", "scripts\\operator_packet.py", "--workflow", "all", "--write", "--validate"],
        ["python", "scripts\\wf75_artifact_only_pm_handoff.py", "--write", "--validate"],
        ["python", "scripts\\wf75_pm_weekly_update.py", "--write", "--validate"],
        ["python", "scripts\\wf75_pm_readiness_pdf.py", "--write", "--validate"],
        ["python", "scripts\\wf75_operator_console.py", "--write", "--validate"],
    ]
    tail = [
        ["python", "scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"],
    ]
    if validation_budget in {"shared", "major"}:
        tail.extend([
            ["python", "scripts\\workspace_boundary_check.py", "--write", "--validate"],
            ["python", "scripts\\artifact_index.py", "incremental"],
            ["python", "scripts\\artifact_index.py", "validate"],
        ])
    if validation_budget == "major":
        tail.insert(1, ["python", "scripts\\db_lifecycle_manifest.py", "--write", "--validate"])
    if mode == "handoff-only":
        return handoff_only + tail
    return full + tail


def run_command(cmd: list[str], timeout: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = utc_now()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        status = "ok" if proc.returncode == 0 else "error"
        if proc.returncode == 1 and "workspace_boundary_check.py" in cmd[1]:
            try:
                boundary_report = json.loads(proc.stdout)
                if boundary_report.get("status") == "warning":
                    status = "warning"
            except json.JSONDecodeError:
                pass
        return {
            "command": " ".join(cmd),
            "status": status,
            "returncode": proc.returncode,
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(cmd),
            "status": "timeout",
            "returncode": None,
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def build_summary(results: list[dict[str, Any]], scenario_id: str, mode: str, validation_budget: str) -> dict[str, Any]:
    failures = [item for item in results if item.get("status") not in {"ok", "warning"}]
    warnings = [item for item in results if item.get("status") == "warning"]
    generated_at = utc_now()
    status = "blocked" if failures else ("attention" if warnings else "ok")
    outputs = [
        item for item in [
            "tmp/wf75-service-state-current.json",
            "tmp/wf75-service-state-sqlite.json",
            "tmp/wf75-operator-console.json",
            "tmp/wf75-pm-weekly-update.json",
            "tmp/wf75-artifact-only-pm-handoff.json",
            "tmp/wf75-pm-readiness-brief.json",
            "tmp/generic-service-run-contract.json",
            "tmp/wf75-smb-workflow-scenario-library.json",
            "tmp/wf75-smb-pivot-pm-decision-packet.json",
            "tmp/wf75-smb-customer-preview.json",
            "tmp/wf75-smb-customer-preview-validation.json",
            "tmp/wf75-smb-pilot-decision-packet.json",
            "tmp/wf75-smb-lead-rescue-service-packet.json",
            "tmp/wf75-smb-lead-rescue-service-packet-validation.json",
            "tmp/wf75-smb-automation-blueprints.json",
            "tmp/wf75-smb-automation-blueprints-validation.json",
            "tmp/wf75-smb-service-state-current.json",
            "tmp/wf75-smb-service-state-validation.json",
            "tmp/wf79-smb-offer-icp-packet.json",
            "tmp/wf79-smb-demo-packets.json",
            "tmp/wf79-smb-demo-packets-validation.json",
            "tmp/wf79-smb-marketing-ops-blueprints.json",
            "tmp/wf79-smb-marketing-ops-blueprints-validation.json",
            "tmp/wf79-smb-cockpit-panel.json",
            "tmp/wf79-smb-sales-practice-packet.json",
            "tmp/wf79-smb-phase-closeout.json",
            "tmp/generic-service-state.sqlite",
            "tmp/operator-packets/retail-saas-wf75.json",
            "tmp/pm-control-packet.json",
            "tmp/pm-control-packet.sqlite",
            "tmp/workspace-boundary-check.json" if validation_budget in {"shared", "major"} else None,
            "tmp/db-lifecycle-manifest.json" if validation_budget == "major" else None,
        ]
        if item
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": status,
        "mode": mode,
        "validation_budget": validation_budget,
        "scenario_id": scenario_id,
        "command_count": len(results),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failed_commands": [item.get("command") for item in failures],
        "warning_commands": [item.get("command") for item in warnings],
        "outputs": outputs,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "results": results,
        "validation": {
            "status": "error" if failures else ("warning" if warnings else "ok"),
            "errors": [f"command_failed:{item.get('command')}" for item in failures],
            "warnings": [f"command_warning:{item.get('command')}" for item in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh WF75 closeout/handoff proof surfaces.")
    parser.add_argument("--write", action="store_true", help="Write closeout report JSON.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero when any command fails.")
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--mode", choices=["full", "handoff-only"], default="full")
    parser.add_argument("--validation-budget", choices=["micro", "narrow", "shared", "major"], default="narrow")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    results: list[dict[str, Any]] = []
    for cmd in command_plan(args.scenario_id, args.mode, args.validation_budget):
        result = run_command(cmd, args.timeout_seconds)
        results.append(result)
        if result["status"] != "ok":
            break
    summary = build_summary(results, args.scenario_id, args.mode, args.validation_budget)
    if args.write:
        atomic_write_json(out, summary)
    print(json.dumps({
        "status": summary["status"],
        "mode": summary["mode"],
        "command_count": summary["command_count"],
        "failure_count": summary["failure_count"],
        "failed_commands": summary["failed_commands"],
        "out": rel(out),
    }, indent=2, sort_keys=True))
    if args.validate and summary["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
