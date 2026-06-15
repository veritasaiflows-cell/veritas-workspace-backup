#!/usr/bin/env python3
"""Run repeated durable-output Python/Go parity cycles.

This is the durable-output equivalent of the dashboard A/B history gate. It
re-runs the Go probes and parity scripts for durable JSON/state helpers and
checks for clean, stable fingerprints across cycles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GO_ROOT = ROOT / "scripts" / "go"
DEFAULT_JSON = TMP / "python-go-durable-output-parity-repeated-gate.json"
SCHEMA = "veritas.python_go_durable_output_parity_repeated_gate.v1"

CASES = [
    {
        "name": "finance_universe_validation",
        "go_command": ["go", "run", ".\\cmd\\go-finance-universe-validation-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\go-finance-universe-validation-probe.json"],
        "parity_command": [sys.executable, "scripts\\python_go_finance_universe_validation_parity.py", "--write", "--validate"],
        "parity_path": TMP / "python-go-finance-universe-validation-parity.json",
        "go_path": TMP / "go-finance-universe-validation-probe.json",
    },
    {
        "name": "wf78_sql_phase2_readiness",
        "go_command": ["go", "run", ".\\cmd\\go-wf78-sql-phase2-readiness-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\go-wf78-sql-phase2-readiness-probe.json"],
        "parity_command": [sys.executable, "scripts\\python_go_wf78_sql_phase2_readiness_parity.py", "--write", "--validate"],
        "parity_path": TMP / "python-go-wf78-sql-phase2-readiness-parity.json",
        "go_path": TMP / "go-wf78-sql-phase2-readiness-probe.json",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=240)
    return {
        "command": command,
        "cwd": cwd.relative_to(ROOT).as_posix() if cwd != ROOT else ".",
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def stable_payload(parity: dict[str, Any], go_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "parity_status": parity.get("status"),
        "parity_summary": parity.get("summary"),
        "go_status": go_report.get("status"),
        "go_mode": go_report.get("mode"),
        "go_source_shape": go_report.get("source_shape"),
        "go_semantic_summary": go_report.get("semantic_summary"),
    }


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_report(cycles: int) -> dict[str, Any]:
    cycle_rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    fingerprints_by_case: dict[str, list[str]] = {case["name"]: [] for case in CASES}

    def add(case: str, cycle: int, check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"case": case, "cycle": cycle, "check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    for cycle in range(1, cycles + 1):
        for case in CASES:
            name = str(case["name"])
            go_result = run_command(list(case["go_command"]), GO_ROOT)
            parity_result = run_command(list(case["parity_command"]), ROOT)
            parity = load(case["parity_path"])
            go_report = load(case["go_path"])
            stable = stable_payload(parity, go_report)
            fp = fingerprint(stable)
            fingerprints_by_case[name].append(fp)
            row = {
                "cycle": cycle,
                "case": name,
                "go_returncode": go_result["returncode"],
                "parity_returncode": parity_result["returncode"],
                "parity_status": parity.get("status"),
                "parity_summary": parity.get("summary"),
                "fingerprint": fp,
            }
            cycle_rows.append(row)
            add(name, cycle, "go_probe_command_ok", go_result["ok"], "critical", go_result)
            add(name, cycle, "parity_command_ok", parity_result["ok"], "critical", parity_result)
            add(name, cycle, "parity_status_ok", parity.get("status") == "ok", "critical", parity.get("summary"))
            add(name, cycle, "go_probe_status_ok", go_report.get("status") == "ok", "critical", as_dict(go_report.get("validation")))

    for case_name, fps in fingerprints_by_case.items():
        add(case_name, 0, "fingerprints_stable", len(set(fps)) == 1, "critical", fps)

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if critical else "warning" if warnings else "ok",
        "workspace_root": str(ROOT),
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cycles": cycles,
            "cases": len(CASES),
            "stable_case_fingerprints": sum(1 for fps in fingerprints_by_case.values() if len(set(fps)) == 1),
            "retire_python_now": 0,
            "durable_output_signal": "durable_output_repeated_parity_clean" if not critical else "blocked",
        },
        "cycle_rows": cycle_rows,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "executes_parity_probes_only": True,
            "production_routing_changed": False,
            "retire_python_now": False,
            "live_sql_write_or_import_allowed": False,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
            "trade_or_account_action_allowed": False,
            "money_movement_allowed": False,
        },
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [f"{row.get('case')}:{row.get('cycle')}:{row.get('check')}" for row in critical],
            "warnings": [f"{row.get('case')}:{row.get('cycle')}:{row.get('check')}" for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated durable-output Python/Go parity cycles.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    report = build_report(max(1, args.cycles))
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
