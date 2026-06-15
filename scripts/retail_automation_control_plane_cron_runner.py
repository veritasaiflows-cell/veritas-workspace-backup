#!/usr/bin/env python3
"""Stable runner for the P0 Retail Automation Control Plane Guard cron.

The retail lane is currently review-only and paused as a product priority, but
the guard still keeps its proof surfaces honest. This runner reduces isolated
cron failures from incidental command handling by producing one classified proof
artifact.
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

from lib.pm_control_reader import pm_program_state
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "retail-automation-control-plane-cron-runner.json"
SCHEMA = "veritas.retail_automation_control_plane_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "customer_or_external_delivery_allowed": False,
    "customer_data_import_allowed": False,
    "sql_write_or_import_allowed": False,
    "sql_first_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def command_plan() -> list[tuple[str, list[str], int]]:
    return [
        ("retail_truth_routing_contract", [sys.executable, "scripts\\retail_truth_routing_contract.py", "--write", "--validate"], 180),
        ("retail_answer_harness", [sys.executable, "scripts\\retail_answer_harness.py", "--write", "--validate"], 180),
        ("retail_saas_fixture_demo_seeded_bad", [sys.executable, "scripts\\retail_saas_fixture_demo.py", "--write-seeded-bad"], 180),
        ("wf78_phase_runner_all_safe", [sys.executable, "scripts\\wf78_phase_runner.py", "--phase", "all-safe", "--write", "--validate"], 420),
        ("intraday_quote_snapshot_proof", [sys.executable, "scripts\\intraday_quote_snapshot_proof.py"], 180),
        ("market_execution_readiness_cron_hardening", [sys.executable, "scripts\\market_execution_readiness_cron_hardening.py", "--write", "--validate"], 180),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 180),
        ("operating_leverage_spine", [sys.executable, "scripts\\operating_leverage_spine.py", "--write", "--validate"], 180),
        ("cron_freshness_spine", [sys.executable, "scripts\\cron_freshness_spine.py", "--write", "--validate"], 180),
        ("automation_stack_hardening_pass", [sys.executable, "scripts\\automation_stack_hardening_pass.py", "--write"], 240),
        ("retail_automation_control_plane", [sys.executable, "scripts\\retail_automation_control_plane.py", "--write", "--validate"], 240),
        ("pm_program_state", [sys.executable, "scripts\\pm_program_state.py", "--write", "--write-db", "--validate"], 240),
        ("pm_cockpit_validate", ["node", "--experimental-strip-types", "apps\\pm-control-cockpit\\src\\server.ts", "--validate"], 240),
    ]


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(full)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "summary": payload.get("summary") or payload.get("scorecard"),
    }


def build_summary() -> dict[str, Any]:
    contract = load(TMP / "retail-truth-routing-contract.json")
    harness = load(TMP / "retail-answer-harness.json")
    control = load(TMP / "retail-automation-control-plane.json")
    hardening = load(TMP / "automation-stack-hardening-pass.json")
    phase = load(TMP / "wf78-phase-runner-current.json")
    queue = load(TMP / "wf78-capital-review-queue.json")
    rerouting = load(TMP / "wf78-event-triggered-rerouting.json")
    market = load(TMP / "market-execution-readiness-cron-hardening.json")
    pm = pm_program_state()
    return {
        "retail_contract_status": contract.get("status"),
        "retail_contract_validation": as_dict(contract.get("validation")).get("status"),
        "answer_harness_status": harness.get("status"),
        "answer_harness_validation": as_dict(harness.get("validation")).get("status"),
        "answer_harness_seeded_bad_cases": as_dict(harness.get("summary")).get("seeded_bad_cases"),
        "retail_control_status": control.get("status"),
        "retail_control_validation": as_dict(control.get("validation")).get("status"),
        "quiet_cron_mode": as_dict(control.get("quiet_cron_summary")).get("mode"),
        "automation_hardening_status": hardening.get("status"),
        "automation_hardening_validation": as_dict(hardening.get("validation")).get("status"),
        "automation_hardening_critical": int_or_zero(as_dict(hardening.get("summary")).get("critical")),
        "wf78_phase_runner_status": phase.get("status"),
        "wf78_phase_runner_failed_steps": as_dict(phase.get("summary")).get("failed_steps"),
        "capital_review_queue_status": queue.get("status"),
        "capital_review_approved_count": as_dict(queue.get("summary")).get("capital_deployment_approved_count"),
        "trade_execution_approved_count": as_dict(queue.get("summary")).get("trade_or_execution_approved_count"),
        "event_rerouting_status": rerouting.get("status"),
        "event_rerouting_actions": as_dict(rerouting.get("summary")).get("action_count"),
        "market_readiness_status": market.get("status"),
        "market_readiness_validation": as_dict(market.get("validation")).get("status"),
        "market_readiness_critical": int_or_zero(as_dict(market.get("summary")).get("critical_count")),
        "pm_program_status": pm.get("status"),
        "pm_program_validation": as_dict(pm.get("validation")).get("status"),
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
    for key in (
        "retail_contract_validation",
        "answer_harness_validation",
        "retail_control_validation",
        "automation_hardening_validation",
        "market_readiness_validation",
        "pm_program_validation",
    ):
        if summary.get(key) != "ok":
            errors.append(f"{key}_not_ok:{summary.get(key)}")
    if int_or_zero(summary.get("automation_hardening_critical")) != 0:
        errors.append("automation_hardening_critical_nonzero")
    if int_or_zero(summary.get("market_readiness_critical")) != 0:
        errors.append("market_readiness_critical_nonzero")
    if int_or_zero(summary.get("capital_review_approved_count")) != 0:
        errors.append("capital_review_queue_capital_approved_nonzero")
    if int_or_zero(summary.get("trade_execution_approved_count")) != 0:
        errors.append("capital_review_queue_trade_execution_approved_nonzero")
    if summary.get("quiet_cron_mode") not in {"NO_REPLY", None}:
        warnings.append(f"retail_control_quiet_cron_mode:{summary.get('quiet_cron_mode')}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(steps: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": build_summary(),
        "steps": steps,
        "artifacts": [
            artifact("tmp/retail-truth-routing-contract.json"),
            artifact("tmp/retail-answer-harness.json"),
            artifact("tmp/retail-automation-control-plane.json"),
            artifact("tmp/automation-stack-hardening-pass.json"),
            artifact("tmp/wf78-phase-runner-current.json"),
            artifact("tmp/wf78-capital-review-queue.json"),
            artifact("tmp/wf78-event-triggered-rerouting.json"),
            artifact("tmp/market-execution-readiness-cron-hardening.json"),
            artifact("tmp/pm-control-packet.json"),
        ],
        "stop_lines": [
            "Review-only retail/control proof. Retail/customer launch remains paused/gated.",
            "No customer output, SQL import/promotion, canon/portfolio mutation, capital deployment, paper/live/account action, or owner approval inference.",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    payload["operator_action"] = "BLOCKED" if validation["errors"] else "MAIN_HANDOFF_REQUIRED" if validation["warnings"] else "NO_REPLY"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P0 retail automation control plane cron proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = [run_step(name, command, timeout) for name, command, timeout in command_plan()]
    payload = build_payload(steps)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"operator_action={payload['operator_action']} retail={summary.get('retail_control_status')} "
        f"hardening={summary.get('automation_hardening_status')} market={summary.get('market_readiness_status')}"
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
