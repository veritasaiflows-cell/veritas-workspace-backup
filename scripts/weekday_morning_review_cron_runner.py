#!/usr/bin/env python3
"""Stable runner for the weekday morning finance refresh cron.

The scheduled job should run one deterministic command and let this runner
classify the proof artifacts. The underlying morning chain still owns the
approved scoped band/reference/sizing note sync steps.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "weekday-morning-review-cron-runner.json"
DEFAULT_LAUNCH_OUT = TMP / "weekday-morning-review-cron-launcher.json"
SCHEMA = "veritas.weekday_morning_review_cron_runner.v1"
LAUNCH_SCHEMA = "veritas.weekday_morning_review_cron_launcher.v1"

AUTHORITY_BOUNDARY = {
    "review_only_runner": True,
    "approved_scoped_entry_band_maintenance_may_run": True,
    "approved_reference_band_visibility_sync_may_run": True,
    "approved_position_sizing_semantic_sync_may_run": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "unscoped_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def tail(text: str | None, limit: int = 1600) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def launch_background(skip_chain: bool, out: Path, launch_out: Path) -> dict[str, Any]:
    stdout_path = TMP / "weekday-morning-review-cron-runner.background.out.txt"
    stderr_path = TMP / "weekday-morning-review-cron-runner.background.err.txt"
    command = [sys.executable, str(Path(__file__).resolve()), "--write", "--validate", "--out", str(out)]
    if skip_chain:
        command.append("--skip-chain")
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    finally:
        stdout.close()
        stderr.close()
    payload = {
        "schema": LAUNCH_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "launched",
        "operator_action": "NO_REPLY",
        "mode": {"skip_chain": skip_chain},
        "child_pid": proc.pid,
        "child_command": command,
        "child_stdout": rel(stdout_path),
        "child_stderr": rel(stderr_path),
        "expected_result_artifact": rel(out),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Launcher only starts the existing approved morning runner in the background.",
            "No trade/account action, paper/live execution, money movement, execution approval, or owner approval inference.",
        ],
    }
    atomic_write_json(launch_out, payload)
    return payload


def build_steps(skip_chain: bool) -> list[tuple[str, list[str], int]]:
    if skip_chain:
        return []
    return [
        ("morning_finance_refresh_chain", [sys.executable, "scripts\\run_finance_refresh_chain.py", "morning"], 2700),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 240),
    ]


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(full)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status") or payload.get("overall"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "summary": payload.get("summary"),
        "authority": payload.get("authority_boundary") or payload.get("authority"),
    }


def build_summary() -> dict[str, Any]:
    run_chain = load(TMP / "run-chain-morning.json")
    run_summary = load(TMP / "run-summary-morning.json")
    auto_band = load(TMP / "auto-band-apply.json")
    ref_sync = load(TMP / "reference-band-note-sync.json")
    sizing_sync = load(TMP / "auto-position-sizing-semantic-sync.json")
    dashboard = load(TMP / "dashboard-validation.json")
    capital_validator = load(TMP / "capital-deployment-recommendation-validation.json")
    capital_bundle = load(TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json")
    post_apply = load(TMP / "post-apply-validation-chain.json")
    return {
        "run_chain_status": run_chain.get("status"),
        "run_chain_exit_code": run_chain.get("exit_code"),
        "run_summary_status": run_summary.get("status"),
        "auto_band_status": auto_band.get("status"),
        "auto_band_applied_count": len(as_list(auto_band.get("applied"))),
        "reference_band_sync_status": ref_sync.get("status"),
        "position_sizing_semantic_sync_status": sizing_sync.get("status"),
        "position_sizing_semantic_sync_writes": as_dict(sizing_sync.get("summary")).get("writes_performed"),
        "post_apply_validation_status": post_apply.get("status"),
        "post_apply_failed_steps": as_dict(post_apply.get("summary")).get("failed"),
        "dashboard_critical": int_or_zero(as_dict(dashboard.get("summary")).get("critical")),
        "dashboard_warning": int_or_zero(as_dict(dashboard.get("summary")).get("warning")),
        "capital_validator_status": capital_validator.get("status"),
        "capital_validator_critical": int_or_zero(as_dict(capital_validator.get("summary")).get("critical")),
        "capital_bundle_status": capital_bundle.get("status"),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed_steps = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed_steps:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed_steps)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("run_chain_status") != "ok":
        errors.append(f"run_chain_status:{summary.get('run_chain_status')}")
    if summary.get("auto_band_status") not in {"ok", "ok_no_changes", None}:
        errors.append(f"auto_band_status:{summary.get('auto_band_status')}")
    if summary.get("reference_band_sync_status") not in {"ok", "ok_no_changes", None}:
        errors.append(f"reference_band_sync_status:{summary.get('reference_band_sync_status')}")
    if summary.get("position_sizing_semantic_sync_status") not in {"ok", "ok_no_changes", None}:
        errors.append(f"position_sizing_semantic_sync_status:{summary.get('position_sizing_semantic_sync_status')}")
    if int_or_zero(summary.get("post_apply_failed_steps")) != 0:
        errors.append("post_apply_validation_failed_steps_nonzero")
    if int_or_zero(summary.get("dashboard_critical")) != 0:
        errors.append("dashboard_validation_has_critical")
    if summary.get("capital_validator_status") != "ok" or int_or_zero(summary.get("capital_validator_critical")) != 0:
        errors.append("capital_deployment_recommendation_validator_not_ok")

    auto_band_auth = as_dict(artifact("tmp/auto-band-apply.json").get("authority"))
    if auto_band_auth.get("capital_action_allowed") is not False or auto_band_auth.get("owner_approval_inferred") is not False:
        errors.append("auto_band_authority_widened")
    ref_auth = as_dict(artifact("tmp/reference-band-note-sync.json").get("authority"))
    if ref_auth.get("capital_action_allowed") is not False or ref_auth.get("owner_approval_inferred") is not False:
        errors.append("reference_band_sync_authority_widened")
    sizing_auth = as_dict(artifact("tmp/auto-position-sizing-semantic-sync.json").get("authority"))
    if (
        sizing_auth.get("portfolio_config_weight_mutation_allowed") is not False
        or sizing_auth.get("cash_risk_rule_sleeve_execution_mutation_allowed") is not False
        or sizing_auth.get("trade_or_account_action_allowed") is not False
        or sizing_auth.get("owner_approval_inferred") is not False
    ):
        errors.append("position_sizing_semantic_sync_authority_widened")
    capital_auth = as_dict(artifact("tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json").get("authority"))
    if (
        capital_auth.get("proposal_apply_allowed") is not False
        or capital_auth.get("per_packet_owner_approval_inferred") is not False
        or capital_auth.get("trade_or_account_action_allowed") is not False
        or capital_auth.get("trade_execution_allowed") is not False
    ):
        errors.append("capital_recommendation_authority_widened")
    if int_or_zero(summary.get("dashboard_warning")):
        warnings.append("dashboard_validation_warnings_present_for_main_visibility")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(steps: list[dict[str, Any]], skip_chain: bool) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "mode": {"skip_chain": skip_chain},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": build_summary(),
        "steps": steps,
        "artifacts": [
            artifact("tmp/run-chain-morning.json"),
            artifact("tmp/run-summary-morning.json"),
            artifact("tmp/auto-band-apply.json"),
            artifact("tmp/reference-band-note-sync.json"),
            artifact("tmp/auto-position-sizing-semantic-sync.json"),
            artifact("tmp/post-apply-validation-chain.json"),
            artifact("tmp/dashboard-validation.json"),
            artifact("tmp/capital-deployment-recommendation-validation.json"),
        ],
        "stop_lines": [
            "The runner may execute only the existing approved morning chain.",
            "No trade/account action, paper/live execution, money movement, execution approval, or owner approval inference.",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    payload["operator_action"] = "BLOCKED" if validation["errors"] else "NO_REPLY"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and classify weekday morning finance refresh cron proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-chain", action="store_true", help="Do not run the morning chain; classify current artifacts only.")
    parser.add_argument("--launch-background", action="store_true", help="Launch the runner in a background process and return immediately.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--launch-out", type=Path, default=DEFAULT_LAUNCH_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.launch_background:
        launch_out = args.launch_out if args.launch_out.is_absolute() else ROOT / args.launch_out
        payload = launch_background(args.skip_chain, out, launch_out)
        print(
            f"status={payload['status']} operator_action={payload['operator_action']} "
            f"child_pid={payload['child_pid']} expected={payload['expected_result_artifact']}"
        )
        return 0
    steps = [run_step(name, command, timeout) for name, command, timeout in build_steps(args.skip_chain)]
    payload = build_payload(steps, args.skip_chain)
    if args.write:
        atomic_write_json(out, payload)
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"operator_action={payload['operator_action']} run_chain={summary.get('run_chain_status')} "
        f"dashboard_critical={summary.get('dashboard_critical')} dashboard_warning={summary.get('dashboard_warning')}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
