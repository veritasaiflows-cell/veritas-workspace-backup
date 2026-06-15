#!/usr/bin/env python3
"""Deliberate Go-primary promotion readiness gate for human-notes SQL check.

This gate is report-only. It proves whether the narrow read-only
`go_finance_human_notes_sql_check` helper is ready for a future controlled
Go-primary/Python-fallback route. It does not flip routing, retire Python,
delete files, write/import SQL, mutate canon/portfolio state, or grant
paper/live/account authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from go_sql_helper_route_registry import (
    SELECTED_INPROCESS_BINARY_HELPERS,
    binary_default_command,
    validate_registry,
)
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-finance-human-notes-sql-check-promotion-gate.json"
HISTORY_JSONL = ROOT / "data" / "state-history" / "python-go-finance-human-notes-sql-check-promotion-gate.jsonl"
PARITY_JSON = TMP / "python-go-finance-human-notes-sql-check-parity.json"
PYTHON_REPORT = TMP / "finance-human-notes-thinning-candidates.json"
GO_REPORT = TMP / "go-finance-human-notes-sql-check.json"
FRESHNESS_JSON = TMP / "go-binary-freshness-guard.json"
RUNTIME_JSON = TMP / "runtime-performance-scorecard.json"
HARNESS_JSON = TMP / "veritas-harness-scorecard.json"
PILOT_GATE_JSON = TMP / "go-sql-inprocess-driver-pilot-gate.json"
HELPER_KEY = "go_finance_human_notes_sql_check"
SCHEMA = "veritas.python_go_finance_human_notes_sql_check_promotion_gate.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_command(name: str, command: list[str], cwd: Path = ROOT, timeout: int = 240) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "name": name,
        "command": command,
        "cwd": rel(cwd),
        "status": "ok" if proc.returncode == 0 else "blocked",
        "returncode": proc.returncode,
        "duration_ms": duration_ms,
        "stdout_preview": (proc.stdout or "")[-1000:],
        "stderr_preview": (proc.stderr or "")[-1000:],
    }


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def helper_metadata() -> dict[str, Any]:
    for helper in SELECTED_INPROCESS_BINARY_HELPERS:
        if helper.get("key") == HELPER_KEY:
            return helper
    return {}


def normalized_cycle_payload(parity: dict[str, Any], python_report: dict[str, Any], go_report: dict[str, Any]) -> dict[str, Any]:
    py_check = as_dict(python_report.get("sql_canon_check"))
    go_check = as_dict(go_report.get("sql_canon_check"))
    go_boundary = as_dict(go_report.get("authority_boundary"))
    parity_summary = as_dict(parity.get("summary"))
    return {
        "python_status": python_report.get("status"),
        "go_status": go_report.get("status"),
        "parity_status": parity.get("status"),
        "parity_checks": parity_summary.get("checks"),
        "parity_critical": parity_summary.get("critical"),
        "parity_warnings": parity_summary.get("warnings"),
        "python_sql_canon_check": {
            "status": py_check.get("status"),
            "path": py_check.get("path"),
            "integrity": py_check.get("integrity"),
            "active_ticker_count": py_check.get("active_ticker_count"),
            "legacy_answer_path_count": py_check.get("legacy_answer_path_count"),
            "review_monitor_count": py_check.get("review_monitor_count"),
        },
        "go_sql_canon_check": {
            "status": go_check.get("status"),
            "path": go_check.get("path"),
            "integrity": go_check.get("integrity"),
            "active_ticker_count": go_check.get("active_ticker_count"),
            "legacy_answer_path_count": go_check.get("legacy_answer_path_count"),
            "review_monitor_count": go_check.get("review_monitor_count"),
        },
        "go_boundary": {
            "report_only": go_boundary.get("report_only"),
            "read_only": go_boundary.get("read_only"),
            "canonical_note_mutation_allowed": go_boundary.get("canonical_note_mutation_allowed"),
            "portfolio_mutation_allowed": go_boundary.get("portfolio_mutation_allowed"),
            "human_note_archive_applied": go_boundary.get("human_note_archive_applied"),
            "delete_allowed": go_boundary.get("delete_allowed"),
            "paper_or_live_execution_allowed": go_boundary.get("paper_or_live_execution_allowed"),
            "trade_or_account_action_allowed": go_boundary.get("trade_or_account_action_allowed"),
            "owner_approval_inferred": go_boundary.get("owner_approval_inferred"),
        },
    }


def artifact_checks(findings: list[dict[str, Any]], cycle: int, parity: dict[str, Any], python_report: dict[str, Any], go_report: dict[str, Any]) -> None:
    parity_summary = as_dict(parity.get("summary"))
    go_boundary = as_dict(go_report.get("authority_boundary"))
    add(findings, f"cycle_{cycle}:python_report_ready", python_report.get("status") == "ready_for_owner_review_no_archive_applied", "critical", python_report.get("status"))
    add(findings, f"cycle_{cycle}:go_report_ok", go_report.get("status") == "ok", "critical", go_report.get("status"))
    add(findings, f"cycle_{cycle}:parity_ok", parity.get("status") == "ok", "critical", parity.get("status"))
    add(findings, f"cycle_{cycle}:parity_critical_zero", int(parity_summary.get("critical") or 0) == 0, "critical", parity_summary)
    add(findings, f"cycle_{cycle}:parity_warnings_zero", int(parity_summary.get("warnings") or 0) == 0, "critical", parity_summary)
    add(findings, f"cycle_{cycle}:go_boundary_read_only", go_boundary.get("read_only") is True and go_boundary.get("report_only") is True, "critical", go_boundary)
    for key in (
        "human_note_archive_applied",
        "delete_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "trade_or_account_action_allowed",
        "money_movement_allowed",
        "owner_approval_inferred",
        "config_auth_runtime_mutation",
    ):
        add(findings, f"cycle_{cycle}:go_boundary_false_{key}", go_boundary.get(key) in {False, None}, "critical", {key: go_boundary.get(key)})


def build_report(cycles: int) -> dict[str, Any]:
    cycle_count = max(1, int(cycles))
    findings: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    helper = helper_metadata()

    registry = validate_registry()
    add(findings, "registry_ok", registry.get("status") == "ok", "critical", registry.get("status"))
    add(findings, "helper_selected", bool(helper), "critical", HELPER_KEY)
    if helper:
        default_command = binary_default_command(helper, GO_REPORT)
        add(findings, "helper_default_command_uses_inprocess", "--driver" in default_command and "inprocess" in default_command, "critical", default_command)
        add(findings, "helper_binary_exists", Path(default_command[0]).exists(), "critical", default_command[0])
    else:
        default_command = []

    freshness_cmd = [sys.executable, "scripts\\go_binary_freshness_guard.py", "--write", "--validate"]
    freshness_result = run_command("go_binary_freshness_guard", freshness_cmd)
    commands.append(freshness_result)
    freshness = load(FRESHNESS_JSON)
    add(findings, "go_binary_freshness_ok", freshness_result.get("returncode") == 0 and freshness.get("status") == "ok", "critical", {"command": freshness_result, "artifact": freshness})

    runtime = load(RUNTIME_JSON)
    runtime_summary = as_dict(runtime.get("summary"))
    add(findings, "runtime_scorecard_ok", runtime.get("status") == "ok" and int(runtime_summary.get("blocked_count") or 0) == 0, "critical", runtime_summary)
    harness = load(HARNESS_JSON)
    harness_summary = as_dict(harness.get("summary"))
    add(findings, "harness_scorecard_ok", harness.get("status") == "ok" and int(harness_summary.get("failure_count") or 0) == 0, "critical", harness_summary)
    pilot = load(PILOT_GATE_JSON)
    pilot_summary = as_dict(pilot.get("summary"))
    add(findings, "pilot_gate_ok", pilot.get("status") == "ok" and int(pilot_summary.get("critical") or 0) == 0, "critical", pilot_summary)

    cycle_rows: list[dict[str, Any]] = []
    for index in range(cycle_count):
        cycle = index + 1
        cycle_commands: list[dict[str, Any]] = []
        for name, command, cwd in (
            (
                "python_finance_human_notes_thinning_candidates",
                [sys.executable, "scripts\\finance_human_notes_thinning_candidates.py", "--write", "--validate"],
                ROOT,
            ),
            (HELPER_KEY, default_command, ROOT),
            (
                "python_go_finance_human_notes_sql_check_parity",
                [sys.executable, "scripts\\python_go_finance_human_notes_sql_check_parity.py", "--write", "--validate"],
                ROOT,
            ),
        ):
            if not command:
                result = {"name": name, "status": "blocked", "returncode": 2, "duration_ms": 0, "stderr_preview": "missing command"}
            else:
                result = run_command(f"cycle_{cycle}:{name}", command, cwd)
            cycle_commands.append(result)
            commands.append(result)
            add(findings, f"cycle_{cycle}:{name}:command_ok", result.get("returncode") == 0, "critical", result)

        parity = load(PARITY_JSON)
        python_report = load(PYTHON_REPORT)
        go_report = load(GO_REPORT)
        artifact_checks(findings, cycle, parity, python_report, go_report)
        normalized = normalized_cycle_payload(parity, python_report, go_report)
        cycle_rows.append(
            {
                "cycle": cycle,
                "fingerprint": fingerprint(normalized),
                "normalized": normalized,
                "commands": cycle_commands,
            }
        )

    fingerprints = {str(row.get("fingerprint")) for row in cycle_rows}
    add(findings, "cycle_fingerprints_stable", len(fingerprints) == 1 and len(cycle_rows) == cycle_count, "critical", sorted(fingerprints))

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    command_failures = [row for row in commands if row.get("returncode") != 0]
    status = "blocked" if critical or command_failures else "warning" if warnings else "ok"
    signal = "ready_for_controlled_go_primary_route_with_python_fallback" if status == "ok" else "not_ready"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "helper": HELPER_KEY,
        "source_artifacts": {
            "registry": "scripts/go_sql_helper_route_registry.py",
            "freshness_guard": rel(FRESHNESS_JSON),
            "runtime_scorecard": rel(RUNTIME_JSON),
            "harness_scorecard": rel(HARNESS_JSON),
            "pilot_gate": rel(PILOT_GATE_JSON),
            "parity": rel(PARITY_JSON),
            "python_report": rel(PYTHON_REPORT),
            "go_report": rel(GO_REPORT),
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cycles": cycle_count,
            "cycle_fingerprints_stable": len(fingerprints) == 1 and len(cycle_rows) == cycle_count,
            "command_failures": len(command_failures),
            "default_route_changed": False,
            "production_routing_changed": False,
            "recommended_controlled_route": "go_primary_with_python_fallback",
            "python_fallback_retained": True,
            "retire_python_now": 0,
            "python_file_delete_allowed": False,
            "sql_write_or_import_allowed": False,
            "promotion_gate_signal": signal,
        },
        "controlled_route_candidate": {
            "helper": HELPER_KEY,
            "current_default_route": "python_owner_only",
            "recommended_next_route": "controlled_go_primary_with_python_fallback",
            "production_routing_changed_by_this_gate": False,
            "rollback": "Keep or restore Python owner/default route and rerun this promotion gate plus runtime scorecard.",
        },
        "cycles": cycle_rows,
        "commands": commands,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "default_route_changed": False,
            "production_routing_changed": False,
            "python_fallback_retained": True,
            "retire_python_now": False,
            "python_file_delete_allowed": False,
            "sql_write_or_import_allowed": False,
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
            "status": "ok" if status == "ok" else "error",
            "errors": [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run human-notes Go promotion readiness gate.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-history", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--history-out", type=Path, default=HISTORY_JSONL)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def append_history(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": SCHEMA,
        "generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "helper": report.get("helper"),
        "summary": report.get("summary"),
        "authority_boundary": report.get("authority_boundary"),
    }
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
        fh.write("\n")


def main() -> int:
    args = parse_args()
    report = build_report(args.cycles)
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    if args.write_history:
        append_history(resolve(args.history_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
