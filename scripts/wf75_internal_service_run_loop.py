#!/usr/bin/env python3
"""Run the WF75 internal service-led prototype loop end to end.

This loop refreshes internal proof artifacts only. It does not deliver
externally, use real customer data, approve public launch, claim legal or
source-licensing readiness, give personalized advice, mutate portfolio/canon
state, or authorize paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.wf75.internal_service_run_loop.v1"
DEFAULT_OUT = TMP / "wf75-internal-service-run-loop.json"
DEFAULT_MD = TMP / "wf75-internal-service-run-loop.md"
DEFAULT_SCENARIO_ID = "anon-risk-freshness-edge-cases-v1"

COMMANDS = [
    {
        "id": "service_state",
        "command": ["python", "scripts\\wf75_service_state.py", "--scenario-id", DEFAULT_SCENARIO_ID, "--write", "--validate"],
        "timeout_seconds": 120,
    },
    {
        "id": "customer_safe_pdf",
        "command": ["python", "scripts\\wf75_customer_safe_pdf_renderer.py", "--write", "--validate"],
        "timeout_seconds": 180,
    },
    {
        "id": "customer_safe_excel",
        "command": ["python", "scripts\\wf75_customer_safe_excel_exporter.py", "--write", "--validate"],
        "timeout_seconds": 120,
    },
    {
        "id": "finance_delivery_manual_gate",
        "command": ["python", "scripts\\finance_delivery_series_orchestrator.py", "--mode", "all", "--write", "--validate"],
        "timeout_seconds": 180,
    },
    {
        "id": "deliverable_packager_pre_gate",
        "command": ["python", "scripts\\wf75_deliverable_packager.py", "--write", "--validate"],
        "timeout_seconds": 120,
    },
    {
        "id": "operator_delivery_gate",
        "command": ["python", "scripts\\wf75_operator_delivery_gate.py", "--write", "--validate"],
        "timeout_seconds": 120,
    },
    {
        "id": "deliverable_packager_final",
        "command": ["python", "scripts\\wf75_deliverable_packager.py", "--write", "--validate"],
        "timeout_seconds": 120,
    },
]

REQUIRED_ARTIFACTS = {
    "service_state": TMP / "wf75-service-state-current.json",
    "customer_safe_pdf_renderer": TMP / "wf75-customer-safe-pdf-renderer.json",
    "customer_safe_excel_exporter": TMP / "wf75-customer-safe-excel-exporter.json",
    "finance_delivery_series": TMP / "finance-delivery-series.json",
    "deliverable_packager": TMP / "wf75-deliverable-packager.json",
    "operator_delivery_gate": TMP / "wf75-operator-delivery-gate.json",
}

AUTHORITY_BOUNDARY = {
    "review_only_internal_service_led": True,
    "customer_external_delivery_allowed": False,
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "legal_compliance_source_licensing_ready": False,
    "source_licensing_assumed": False,
    "personalized_advice_allowed": False,
    "advice_execution_brokerage_account_allowed": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cron_restart_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_AUTHORITY = [
    key for key, value in AUTHORITY_BOUNDARY.items() if value is False
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def validation_status(payload: dict[str, Any]) -> str | None:
    return as_dict(payload.get("validation")).get("status") or payload.get("validation_status")


def run_command(spec: dict[str, Any]) -> dict[str, Any]:
    command = [str(part) for part in spec["command"]]
    started = utc_now()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=int(spec.get("timeout_seconds") or 120),
        )
        status = "ok" if proc.returncode == 0 else "error"
        return {
            "id": spec["id"],
            "status": status,
            "command": " ".join(command),
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-1200:],
            "stderr_tail": (proc.stderr or "")[-1200:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "id": spec["id"],
            "status": "timeout",
            "command": " ".join(command),
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "returncode": None,
            "stdout_tail": (exc.stdout or "")[-1200:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def command_plan() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "command": " ".join(str(part) for part in spec["command"]),
            "timeout_seconds": spec.get("timeout_seconds"),
        }
        for spec in COMMANDS
    ]


def artifact_probe(key: str, path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    payload = payload if isinstance(payload, dict) else {}
    return {
        "key": key,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status") or as_dict(payload.get("summary")).get("status") or "missing",
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def build_payload(*, execute: bool, scenario_id: str = DEFAULT_SCENARIO_ID) -> dict[str, Any]:
    commands = [run_command(spec) for spec in COMMANDS] if execute else [
        {
            "id": spec["id"],
            "status": "not_run",
            "command": " ".join(str(part) for part in spec["command"]),
            "returncode": None,
        }
        for spec in COMMANDS
    ]
    artifacts = {
        key: artifact_probe(key, path)
        for key, path in REQUIRED_ARTIFACTS.items()
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "scenario_id": scenario_id,
        "status": "ok",
        "execution_mode": "executed" if execute else "inspection_only",
        "command_plan": command_plan(),
        "commands": commands,
        "artifact_status": artifacts,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_safe_action": (
            "Use this run loop to refresh the internal WF75 service-led prototype proof chain. "
            "External/customer delivery remains blocked."
        ),
    }
    payload["validation"] = validate_payload(payload, require_commands=execute)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def validate_payload(payload: dict[str, Any], *, require_commands: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    command_ids = {row.get("id") for row in payload.get("command_plan", []) if isinstance(row, dict)}
    for required in {spec["id"] for spec in COMMANDS}:
        if required not in command_ids:
            errors.append(f"missing_command:{required}")
    if require_commands:
        for row in payload.get("commands", []):
            if isinstance(row, dict) and row.get("status") != "ok":
                errors.append(f"command_failed:{row.get('id')}:{row.get('status')}")
    artifacts = as_dict(payload.get("artifact_status"))
    for key in REQUIRED_ARTIFACTS:
        item = as_dict(artifacts.get(key))
        if not item.get("exists"):
            errors.append(f"missing_artifact:{key}")
        if not item.get("parseable_json"):
            errors.append(f"unparseable_artifact:{key}")
    gate = as_dict(load_json_artifact(REQUIRED_ARTIFACTS["operator_delivery_gate"]))
    if gate and gate.get("external_delivery_status") != "blocked_policy_source_legal_owner_gates":
        errors.append("operator_gate_external_delivery_not_blocked")
    finance = as_dict(load_json_artifact(REQUIRED_ARTIFACTS["finance_delivery_series"]))
    finance_gate = as_dict(as_dict(finance.get("delivery_program")).get("saas_deliverable_gate"))
    if finance_gate and finance_gate.get("cron_generation_allowed") is not False:
        errors.append("finance_delivery_cron_not_paused")
    boundary = as_dict(payload.get("authority_boundary"))
    if boundary.get("review_only_internal_service_led") is not True:
        errors.append("review_only_internal_service_led_not_true")
    for key in REQUIRED_FALSE_AUTHORITY:
        if boundary.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    return {"status": "ok" if not errors else "error", "errors": errors}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WF75 Internal Service Run Loop",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Scenario: `{payload.get('scenario_id')}`",
        "",
        "## Commands",
        "",
        "| ID | Status | Return Code |",
        "|---|---|---:|",
    ]
    for row in payload.get("commands", []):
        if isinstance(row, dict):
            lines.append(f"| {row.get('id')} | {row.get('status')} | {row.get('returncode')} |")
    lines.extend(["", "## Artifacts", "", "| Key | Status | Validation | Path |", "|---|---|---|---|"])
    for row in as_dict(payload.get("artifact_status")).values():
        if isinstance(row, dict):
            lines.append(f"| {row.get('key')} | {row.get('status')} | {row.get('validation_status')} | {row.get('path')} |")
    lines.extend(["", "## Authority Boundary", ""])
    for key, value in as_dict(payload.get("authority_boundary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Action", "", str(payload.get("next_safe_action") or ""), ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the WF75 internal service-led prototype loop.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--inspect-only", action="store_true")
    return parser.parse_args()


def absolutize(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    execute = not args.inspect_only
    payload = build_payload(execute=execute, scenario_id=args.scenario_id)
    out = absolutize(args.out)
    md_out = absolutize(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
        atomic_write_text(md_out, render_markdown(payload))
    errors = payload["validation"]["errors"]
    print(
        "status={status} mode={mode} commands={commands} errors={errors}".format(
            status=payload.get("status"),
            mode=payload.get("execution_mode"),
            commands=len(payload.get("commands", [])),
            errors=len(errors),
        )
    )
    return 0 if (not args.validate or not errors) else 2


if __name__ == "__main__":
    raise SystemExit(main())
