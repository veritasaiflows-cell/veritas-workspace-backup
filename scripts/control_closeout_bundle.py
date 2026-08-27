#!/usr/bin/env python3
"""One control-closeout command for the Finance Decision Factory operating loop.

This is a thin bundle over capabilities that already exist. It runs the
repeatable-work closeout chain (route index, action scorer, event rerouting,
truth-surface inventory, fast-path QA, artifact index, PM control), then
refreshes the consolidated PM control packet, refreshes the small set of
cockpit-required live proofs that are not owned by the closeout chain, validates
the PM cockpit source registry, and reports concurrent-lane-register health.

It is validation/proof only: no canon/portfolio mutation, no SQL import, no
archive/delete, no config/auth/runtime mutation, no customer/external delivery,
no capital deployment, no trade/paper/live/account action, no money movement,
and no owner approval inference.
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

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "control-closeout-bundle.json"
COCKPIT_DIR = ROOT / "apps" / "pm-control-cockpit"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
PM_CONTROL = TMP / "pm-control-packet.json"
CLOSEOUT = TMP / "repeatable-work-closeout.json"
GREENKEEPER = TMP / "main-session-greenkeeper-controller.json"
ESCALATION_CONSUMER = TMP / "main-session-escalation-consumer.json"
ACTION_EXECUTOR = TMP / "main-session-action-executor.json"
RELEASE_CONTRACT = TMP / "implementation-release-contract.json"
SCHEMA = "veritas.control_closeout_bundle.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "closeout_handoff_and_allowlisted_pm_proof_only": True,
    "executes_code_patches": False,
    "spawns_helpers": False,
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


def run_step(name: str, command: list[str], timeout: int, cwd: Path = ROOT) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
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
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def skipped_step(name: str, reason: str) -> dict[str, Any]:
    return {"name": name, "ok": True, "skipped": True, "reason": reason}


def failed_step(name: str, reason: str) -> dict[str, Any]:
    return {"name": name, "ok": False, "skipped": True, "reason": reason}


def lane_register_health() -> dict[str, Any]:
    data = load_json_artifact(LANE_REGISTER)
    if not isinstance(data, dict):
        return {"present": False, "detail": f"missing {rel(LANE_REGISTER)}"}
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    return {
        "present": True,
        "validation_status": validation.get("status"),
        "lane_count": summary.get("lane_count"),
        "active_lane_count": summary.get("active_lane_count"),
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
    }


def artifact_status(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        return {"present": False}
    validation = data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}
    return {
        "present": True,
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    steps.append(run_step(
        "implementation_release_contract_pre_closeout",
        py_cmd("scripts\\implementation_release_contract.py", "--phase", "advisory", "--write", "--validate"),
        180,
    ))

    steps.append(run_step(
        "response_recommendation_contract_lint_self_test",
        py_cmd("scripts\\response_recommendation_contract_lint.py", "--self-test", "--write", "--validate"),
        120,
    ))

    steps.append(run_step(
        "cockpit_live_required_source_refresh",
        py_cmd("scripts\\wf78_tier_capacity_policy_gate.py", "--write", "--write-db", "--validate"),
        240,
    ))

    closeout_cmd = py_cmd("scripts\\repeatable_work_closeout.py", "--validation-budget", args.validation_budget, "--write", "--validate")
    if args.continue_on_failure:
        closeout_cmd.append("--continue-on-failure")
    steps.append(run_step("repeatable_work_closeout", closeout_cmd, 900))

    steps.append(run_step(
        "pm_control_packet",
        py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"),
        240,
    ))

    steps.append(run_step(
        "main_session_escalation_consumer",
        py_cmd(
            "scripts\\main_session_escalation_consumer.py",
            "--context",
            "closeout",
            "--refresh-frontdoors",
            "--execute-safe",
            "--write",
            "--validate",
            "--append-ledger",
        ),
        1200,
    ))

    steps.append(run_step(
        "pm_control_packet_after_escalation_consumer",
        py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"),
        240,
    ))

    steps.append(run_step(
        "main_session_greenkeeper_controller",
        py_cmd(
            "scripts\\main_session_greenkeeper_controller.py",
            "--refresh-frontdoors",
            "--execute-safe",
            "--write",
            "--validate",
            "--append-ledger",
        ),
        600,
    ))

    steps.append(run_step(
        "pm_control_packet_after_greenkeeper",
        py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"),
        240,
    ))

    steps.append(run_step(
        "main_session_action_executor",
        py_cmd(
            "scripts\\main_session_action_executor.py",
            "--context",
            "closeout",
            "--execute-safe",
            "--write",
            "--validate",
            "--append-ledger",
        ),
        1500,
    ))

    steps.append(run_step(
        "pm_control_packet_after_action_executor",
        py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"),
        240,
    ))

    steps.append(run_step(
        "implementation_release_contract_post_producers",
        py_cmd("scripts\\implementation_release_contract.py", "--phase", "advisory", "--write", "--validate"),
        180,
    ))

    steps.append(run_step(
        "concurrent_lane_register_status",
        py_cmd("scripts\\concurrent_lane_manager.py", "--status", "--validate"),
        120,
    ))

    if not args.skip_cockpit_validate:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if npm and COCKPIT_DIR.exists():
            steps.append(run_step("pm_cockpit_validate", [npm, "run", "validate"], 240, cwd=COCKPIT_DIR))
        else:
            steps.append(failed_step("pm_cockpit_validate", "requested but npm not found on PATH or cockpit dir missing"))
    else:
        steps.append(skipped_step("pm_cockpit_validate", "skipped by --skip-cockpit-validate"))

    failed = [s["name"] for s in steps if not s.get("ok")]
    status = "ok" if not failed else "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Single control-closeout bundle: live cockpit-source refresh + closeout chain + cron escalation consumer + greenkeeper + one allowlisted PM proof pickup + workflow handoff + lane-register health + cockpit validate.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "steps_run": len(steps),
            "failed_steps": failed,
            "lane_register": lane_register_health(),
            "closeout_artifact": artifact_status(CLOSEOUT),
            "pm_control_artifact": artifact_status(PM_CONTROL),
            "escalation_consumer_artifact": artifact_status(ESCALATION_CONSUMER),
            "greenkeeper_artifact": artifact_status(GREENKEEPER),
            "action_executor_artifact": artifact_status(ACTION_EXECUTOR),
            "implementation_release_contract": artifact_status(RELEASE_CONTRACT),
            "next_safe_action": (
                "Use fast-path QA + PM control packet as pickup proof; pick the next safe PM job."
                if status == "ok"
                else "Inspect the first failed step; do not advance the operating loop until closeout is clean."
            ),
        },
        "steps": steps,
        "validation": {
            "status": status,
            "errors": failed,
            "warnings": [],
        },
        "stop_lines": [
            "Validation/proof only; may consume allowlisted cron escalation repairs and run one allowlisted PM proof job through main_session_action_executor.",
            "No canon/portfolio/SQL mutation, archive/delete, config/auth/runtime change, or customer delivery.",
            "No capital deployment, trade/paper/live/account action, money movement, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Finance Decision Factory control-closeout bundle.")
    parser.add_argument("--write", action="store_true", help="Write the bundle artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero when status is blocked.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Pass through to the closeout chain.")
    parser.add_argument("--cockpit-validate", action="store_true", help="Deprecated no-op: cockpit validation now runs by default.")
    parser.add_argument("--skip-cockpit-validate", action="store_true", help="Skip PM cockpit source-registry validation.")
    parser.add_argument("--record-completion", action="store_true", help="Append this successful closeout to the implementation completion ledger.")
    parser.add_argument("--completion-job-id", default=None, help="Job id to use when --record-completion is set.")
    parser.add_argument("--completion-title", default=None, help="Job title to use when --record-completion is set.")
    parser.add_argument("--completion-summary", default=None, help="Job summary to use when --record-completion is set.")
    parser.add_argument("--validation-budget", choices=["micro", "narrow", "shared", "major"], default="shared")
    parser.add_argument("--out", type=Path, default=OUT, help="Output artifact path.")
    args = parser.parse_args()

    if args.record_completion and not args.completion_job_id:
        print("--record-completion requires --completion-job-id", file=sys.stderr)
        return 2

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        if report["status"] == "ok" and args.record_completion:
            ledger_cmd = py_cmd(
                "scripts\\implementation_completion_ledger.py",
                "--source",
                rel(args.out),
                "--job-id",
                str(args.completion_job_id),
                "--record",
                "--write",
                "--validate",
            )
            if args.completion_title:
                ledger_cmd.extend(["--title", str(args.completion_title)])
            if args.completion_summary:
                ledger_cmd.extend(["--summary", str(args.completion_summary)])
            ledger_result = run_step("implementation_completion_ledger", ledger_cmd, 120)
            if not ledger_result["ok"]:
                report["status"] = "blocked"
                report["completion_ledger_result"] = ledger_result
                report["validation"]["status"] = "blocked"
                report["validation"]["errors"] = [*report["validation"]["errors"], "implementation_completion_ledger"]
                atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} steps={report['summary']['steps_run']} failed={report['summary']['failed_steps']}")
    else:
        print(json.dumps(report["summary"], indent=2, default=str))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
