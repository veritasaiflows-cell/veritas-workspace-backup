#!/usr/bin/env python3
"""Stable cron runner for the sector allocation decision matrix.

This keeps the cron prompt to one deterministic command and records step-level
proof for the report-only sector allocation matrix.
"""
from __future__ import annotations

import argparse
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
DEFAULT_OUT = TMP / "sector-allocation-decision-matrix-cron-runner.json"
SCHEMA = "veritas.sector_allocation_decision_matrix_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "sector_matrix_report_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "sizing_or_allocation_change_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_FLAGS = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_order_execution_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "probability_or_modeling_authority",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def tail(text: str | bytes | None, limit: int = 1600) -> str:
    if isinstance(text, bytes):
        value = text.decode("utf-8", errors="replace")
    else:
        value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started_at = utc_now()
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
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout),
            "stderr_tail": tail(exc.stderr),
        }
    return {
        "name": name,
        "command": command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def command_plan() -> list[tuple[str, list[str], int]]:
    return [
        ("sector_allocation_decision_matrix", [sys.executable, "scripts\\sector_allocation_decision_matrix.py", "--write", "--validate"], 180),
        ("sector_allocation_decision_matrix_tests", [sys.executable, "scripts\\test_sector_allocation_decision_matrix.py"], 120),
        ("artifact_index_incremental", [sys.executable, "scripts\\artifact_index.py", "incremental"], 240),
        ("artifact_index_validate", [sys.executable, "scripts\\artifact_index.py", "validate"], 240),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 180),
    ]


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(full)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status"),
        "operator_action": payload.get("operator_action"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc") or payload.get("generated_at"),
    }


def build_summary() -> dict[str, Any]:
    matrix = load(TMP / "sector-allocation-decision-matrix.json")
    validation = as_dict(matrix.get("validation"))
    findings = as_list(validation.get("findings"))
    critical = sum(1 for item in findings if as_dict(item).get("severity") == "critical")
    warning = sum(1 for item in findings if as_dict(item).get("severity") == "warning")
    return {
        "sector_matrix_status": matrix.get("status"),
        "sector_matrix_validation": validation.get("status"),
        "sector_matrix_critical_count": validation.get("critical", critical),
        "sector_matrix_warning_count": validation.get("warning", warning),
        "probability_readiness": as_dict(matrix.get("trust_state")).get("probability_readiness"),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed)}")
    matrix_path = TMP / "sector-allocation-decision-matrix.json"
    if not matrix_path.exists():
        errors.append("sector_matrix_artifact_missing")
    matrix = load(matrix_path)
    if matrix.get("status") != "ok":
        errors.append(f"sector_matrix_status_not_ok:{matrix.get('status')}")
    matrix_validation = as_dict(matrix.get("validation"))
    if matrix_validation.get("status") != "ok":
        errors.append(f"sector_matrix_validation_not_ok:{matrix_validation.get('status')}")
    if int(matrix_validation.get("critical") or 0):
        errors.append("sector_matrix_critical_nonzero")
    authority = as_dict(matrix.get("authority"))
    for key in sorted(FORBIDDEN_TRUE_FLAGS):
        if authority.get(key) is True:
            errors.append(f"sector_matrix_{key}_true")
    if int(matrix_validation.get("warning") or 0):
        warnings.append("sector_matrix_warning_accepted")
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
            artifact("tmp/sector-allocation-decision-matrix.json"),
            artifact("tmp/sector-allocation-decision-matrix.md"),
            artifact("tmp/cron-operator-ledger.json"),
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    payload["operator_action"] = "BLOCKED" if validation["errors"] else "NO_REPLY"
    payload["summary"]["failed_step_count"] = len([step for step in steps if not step.get("ok")])
    payload["summary"]["accepted_warning_count"] = len(validation["warnings"])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the sector allocation decision matrix cron proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    steps: list[dict[str, Any]] = []
    for name, command, timeout in command_plan():
        step = run_step(name, command, timeout)
        steps.append(step)
        if not step.get("ok"):
            break
    payload = build_payload(steps)
    if args.write:
        atomic_write_json(args.json_out, payload)
    else:
        print(payload)
    return 1 if args.validate and payload["validation"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
