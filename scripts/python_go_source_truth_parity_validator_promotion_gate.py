#!/usr/bin/env python3
"""Deliberate Go-primary promotion gate for source-truth parity validation.

This gate is report-only. It proves whether the narrow read-only
`go_source_truth_parity_validator` helper is ready for a future controlled
Go-primary/Python-fallback route. It does not promote SQL to source truth,
mutate SQL or Markdown, change consumers, retire Python, or grant portfolio,
customer, paper/live, account, config, or owner-approval authority.
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
DEFAULT_JSON = TMP / "python-go-source-truth-parity-validator-promotion-gate.json"
HISTORY_JSONL = ROOT / "data" / "state-history" / "python-go-source-truth-parity-validator-promotion-gate.jsonl"
PYTHON_REPORT = TMP / "sql-source-truth-parity-validation.json"
GO_REPORT = TMP / "go-source-truth-parity-validation.json"
PARITY_JSON = TMP / "python-go-source-truth-parity-validator-parity.json"
FRESHNESS_JSON = TMP / "go-binary-freshness-guard.json"
RUNTIME_JSON = TMP / "runtime-performance-scorecard.json"
HARNESS_JSON = TMP / "veritas-harness-scorecard.json"
HELPER_KEY = "go_source_truth_parity_validator"
SCHEMA = "veritas.python_go_source_truth_parity_validator_promotion_gate.v1"

FALSE_AUTHORITY_FLAGS = (
    "source_of_truth_promotion_allowed_by_this_artifact",
    "sql_first_consumer_migration_allowed",
    "sql_writes_allowed",
    "markdown_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "recommendation_or_deployment_authority_allowed",
    "paper_or_live_execution_allowed",
    "customer_or_external_delivery_allowed",
)


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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


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


def false_flags(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in FALSE_AUTHORITY_FLAGS}


def source_hash(payload: dict[str, Any]) -> Any:
    return as_dict(payload.get("source_note")).get("sha256")


def normalized_cycle_payload(parity: dict[str, Any], python_report: dict[str, Any], go_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "python_status": python_report.get("status"),
        "go_status": go_report.get("status"),
        "parity_status": parity.get("status"),
        "python_summary": as_dict(python_report.get("summary")),
        "go_summary": as_dict(go_report.get("summary")),
        "source_note_hash": source_hash(go_report),
        "false_authority_flags": false_flags(go_report),
        "missing_finance_tickers": sorted(str(value) for value in as_list(go_report.get("missing_finance_tickers"))),
        "missing_canon_tickers": sorted(str(value) for value in as_list(go_report.get("missing_canon_tickers"))),
        "finance_extra_tickers": sorted(str(value) for value in as_list(go_report.get("finance_extra_tickers"))),
        "canon_extra_tickers": sorted(str(value) for value in as_list(go_report.get("canon_extra_tickers"))),
        "mismatch_count": len(as_list(go_report.get("mismatches"))),
        "comparison_count": len(as_list(go_report.get("comparisons"))),
        "parity_summary": as_dict(parity.get("summary")),
    }


def artifact_checks(findings: list[dict[str, Any]], cycle: int, parity: dict[str, Any], python_report: dict[str, Any], go_report: dict[str, Any]) -> None:
    py_summary = as_dict(python_report.get("summary"))
    go_summary = as_dict(go_report.get("summary"))
    parity_summary = as_dict(parity.get("summary"))

    add(findings, f"cycle_{cycle}:python_report_green", python_report.get("status") == "phase2_parity_green_for_entry_stop_reference_metadata", "critical", python_report.get("status"))
    add(findings, f"cycle_{cycle}:go_report_green", go_report.get("status") == "phase2_parity_green_for_entry_stop_reference_metadata", "critical", go_report.get("status"))
    add(findings, f"cycle_{cycle}:python_go_summary_match", py_summary == go_summary, "critical", {"python": py_summary, "go": go_summary})
    add(findings, f"cycle_{cycle}:ready_rows_match", py_summary.get("ready_rows") == go_summary.get("ready_rows"), "critical", {"python": py_summary, "go": go_summary})
    add(findings, f"cycle_{cycle}:mismatch_rows_zero", int(go_summary.get("mismatch_rows") or 0) == 0, "critical", go_summary)
    add(findings, f"cycle_{cycle}:source_hash_match", source_hash(python_report) == source_hash(go_report), "critical", {"python": source_hash(python_report), "go": source_hash(go_report)})
    add(findings, f"cycle_{cycle}:parity_ok", parity.get("status") == "ok", "critical", parity.get("status"))
    add(findings, f"cycle_{cycle}:parity_critical_zero", int(parity_summary.get("critical") or 0) == 0, "critical", parity_summary)
    add(findings, f"cycle_{cycle}:parity_warnings_zero", int(parity_summary.get("warnings") or 0) == 0, "critical", parity_summary)
    add(findings, f"cycle_{cycle}:false_authority_flags_match", false_flags(python_report) == false_flags(go_report), "critical", {"python": false_flags(python_report), "go": false_flags(go_report)})
    add(findings, f"cycle_{cycle}:all_go_authority_flags_false", all(value is False for value in false_flags(go_report).values()), "critical", false_flags(go_report))


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

    freshness_result = run_command("go_binary_freshness_guard", [sys.executable, "scripts\\go_binary_freshness_guard.py", "--write", "--validate"])
    commands.append(freshness_result)
    freshness = load(FRESHNESS_JSON)
    add(findings, "go_binary_freshness_ok", freshness_result.get("returncode") == 0 and freshness.get("status") == "ok", "critical", {"command": freshness_result, "artifact_status": freshness.get("status")})

    runtime = load(RUNTIME_JSON)
    runtime_summary = as_dict(runtime.get("summary"))
    add(findings, "runtime_scorecard_clean_when_available", runtime.get("status") == "ok" and int(runtime_summary.get("blocked_count") or 0) == 0, "warning", runtime_summary)
    harness = load(HARNESS_JSON)
    harness_summary = as_dict(harness.get("summary"))
    add(findings, "harness_scorecard_clean_when_available", harness.get("status") == "ok" and int(harness_summary.get("failure_count") or 0) == 0, "warning", harness_summary)

    cycle_rows: list[dict[str, Any]] = []
    for index in range(cycle_count):
        cycle = index + 1
        cycle_commands: list[dict[str, Any]] = []
        for name, command in (
            (
                "python_sql_source_truth_parity_validator",
                [sys.executable, "scripts\\sql_source_truth_parity_validator.py", "--write", "--validate"],
            ),
            (HELPER_KEY, default_command),
            (
                "python_go_source_truth_parity_validator_parity",
                [sys.executable, "scripts\\python_go_source_truth_parity_validator_parity.py", "--write", "--validate"],
            ),
        ):
            if not command:
                result = {"name": name, "status": "blocked", "returncode": 2, "duration_ms": 0, "stderr_preview": "missing command"}
            else:
                result = run_command(f"cycle_{cycle}:{name}", command)
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
    signal = "ready_for_controlled_go_primary_route_with_python_fallback" if not critical and not command_failures else "not_ready"
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
            "python_report": rel(PYTHON_REPORT),
            "go_report": rel(GO_REPORT),
            "parity": rel(PARITY_JSON),
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
            "source_of_truth_changed": False,
            "recommended_controlled_route": "go_primary_with_python_fallback",
            "python_fallback_retained": True,
            "retire_python_now": 0,
            "python_file_delete_allowed": False,
            "sql_write_or_import_allowed": False,
            "promotion_gate_signal": signal,
        },
        "controlled_route_candidate": {
            "helper": HELPER_KEY,
            "current_default_route": "selected_compiled_validator_only",
            "recommended_next_route": "controlled_go_primary_with_python_fallback_for_parity_validation_only",
            "production_routing_changed_by_this_gate": False,
            "source_truth_promotion_allowed_by_this_gate": False,
            "rollback": "Keep or restore Python owner/default route for source-truth parity validation and rerun this gate plus runtime scorecard.",
        },
        "cycles": cycle_rows,
        "commands": commands,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "default_route_changed": False,
            "production_routing_changed": False,
            "source_truth_promotion_allowed": False,
            "consumer_migration_allowed": False,
            "python_fallback_retained": True,
            "retire_python_now": False,
            "python_file_delete_allowed": False,
            "sql_write_or_import_allowed": False,
            "db_mutation": False,
            "markdown_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
            "trade_or_account_action_allowed": False,
            "money_movement_allowed": False,
        },
        "validation": {
            "status": "ok" if not critical and not command_failures else "error",
            "errors": [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run source-truth parity Go promotion readiness gate.")
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
