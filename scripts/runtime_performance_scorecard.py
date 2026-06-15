#!/usr/bin/env python3
"""Build a unified runtime performance scorecard for local validators.

This is a report-only control-plane helper. It times representative SQL,
Go, Python, and TypeScript/Node validation paths, writes proof artifacts, and
keeps a compact append-only history for regression review. It does not mutate
finance canon, portfolio state, customer state, runtime config, or execution
authority.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from go_sql_helper_route_registry import GO_BIN_DIR, SELECTED_INPROCESS_BINARY_HELPERS, binary_default_command, build_command
from lib.pm_control_reader import pm_program_state
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GO_SCRIPT_BIN = ROOT / "scripts" / "go" / "bin"
HISTORY = ROOT / "data" / "state-history" / "runtime-performance-scorecard.jsonl"
DEFAULT_JSON = TMP / "runtime-performance-scorecard.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "runtime.performance_scorecard.v1"


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


def tail(text: str, limit: int = 2200) -> str:
    return text[-limit:] if len(text) > limit else text


def run_command(name: str, command: list[str], *, cwd: Path = ROOT, timeout: int = 240) -> dict[str, Any]:
    started = time.perf_counter()
    executable = shutil.which(command[0])
    if executable is None and not Path(command[0]).exists():
        return {
            "name": name,
            "runtime": classify_runtime(command),
            "status": "blocked",
            "returncode": None,
            "duration_ms": 0,
            "cwd": rel(cwd),
            "command": command,
            "notes": f"binary not found: {command[0]}",
        }
    resolved = [executable or command[0], *command[1:]]
    try:
        completed = subprocess.run(
            resolved,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "runtime": classify_runtime(command),
            "status": "blocked",
            "returncode": None,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "cwd": rel(cwd),
            "command": command,
            "notes": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout or ""),
            "stderr_tail": tail(exc.stderr or ""),
        }
    return {
        "name": name,
        "runtime": classify_runtime(command),
        "status": "ok" if completed.returncode == 0 else "blocked",
        "returncode": completed.returncode,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "cwd": rel(cwd),
        "command": command,
        "notes": "ok" if completed.returncode == 0 else "command failed",
        "stdout_tail": tail(completed.stdout or ""),
        "stderr_tail": tail(completed.stderr or ""),
    }


def classify_runtime(command: list[str]) -> str:
    head = Path(command[0]).name.lower()
    if head.startswith("python") or head == Path(sys.executable).name.lower():
        return "python"
    if head == "go":
        return "go"
    if head in {"npm", "npm.cmd", "node", "node.exe"}:
        return "node_typescript"
    if "sqlite" in head:
        return "sqlite"
    if head.startswith("go-") and head.endswith(".exe"):
        return "go_binary"
    return "other"


def go_script_bin_command(name: str, *args: str) -> list[str]:
    return [str(GO_SCRIPT_BIN / f"{name}.exe"), *args]


def command_plan(args: argparse.Namespace) -> list[tuple[str, list[str], Path, int]]:
    sql_iterations = str(max(1, int(args.sql_iterations)))
    selected_builds = [
        (f"build_{helper['key']}_binary", build_command(helper), ROOT / "scripts" / "go", 300)
        for helper in SELECTED_INPROCESS_BINARY_HELPERS
    ]
    selected_binary_routes = [
        (helper["key"], binary_default_command(helper), ROOT, 240)
        for helper in SELECTED_INPROCESS_BINARY_HELPERS
    ]
    plan: list[tuple[str, list[str], Path, int]] = [
        ("python_compile_runtime_scorecard", [sys.executable, "-m", "py_compile", "scripts\\runtime_performance_scorecard.py"], ROOT, 60),
        ("sql_latency_benchmark", [sys.executable, "scripts\\sql_latency_benchmark.py", "--iterations", sql_iterations, "--json-out", "tmp\\sql-latency-benchmark-current.json", "--validate"], ROOT, 240),
        ("go_test_all", ["go", "test", ".\\..."], ROOT / "scripts" / "go", 240),
        *selected_builds,
        *selected_binary_routes,
        ("python_go_sql_parity_check", [sys.executable, "scripts\\python_go_sql_parity_check.py", "--write", "--validate"], ROOT, 240),
        ("go_wf75_smb_boundary_lint", ["go", "run", ".\\cmd\\wf75-smb-boundary-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\wf75-smb-boundary-lint.json"], ROOT / "scripts" / "go", 240),
        ("go_finance_sql_boundary_lint", ["go", "run", ".\\cmd\\finance-sql-boundary-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\finance-sql-boundary-lint.json"], ROOT / "scripts" / "go", 240),
        ("go_python_sql_contract_lint", ["go", "run", ".\\cmd\\python-sql-contract-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\python-sql-contract-lint.json"], ROOT / "scripts" / "go", 240),
        ("python_go_sql_migration_candidates", [sys.executable, "scripts\\python_go_sql_migration_candidates.py", "--write", "--validate"], ROOT, 240),
        ("python_sql_source_truth_manifest", [sys.executable, "scripts\\sql_source_truth_authority_manifest.py", "--write", "--validate"], ROOT, 240),
        (
            "go_sql_source_truth_manifest",
            [
                "go",
                "run",
                ".\\cmd\\go-sql-source-truth-manifest",
                "--root",
                "..\\..",
                "--driver",
                "inprocess",
                "--out",
                "..\\..\\tmp\\go-sql-source-truth-authority-manifest.json",
            ],
            ROOT / "scripts" / "go",
            240,
        ),
        ("python_go_source_truth_manifest_parity", [sys.executable, "scripts\\python_go_source_truth_manifest_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_sql_source_truth_parity_validator", [sys.executable, "scripts\\sql_source_truth_parity_validator.py", "--write", "--validate"], ROOT, 240),
        ("go_source_truth_parity_validator", ["go", "run", ".\\cmd\\go-source-truth-parity-validator", "--root", "..\\..", "--out", "..\\..\\tmp\\go-source-truth-parity-validation.json"], ROOT / "scripts" / "go", 240),
        ("python_go_source_truth_parity_validator_parity", [sys.executable, "scripts\\python_go_source_truth_parity_validator_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_sql_500_expansion_gate", [sys.executable, "scripts\\sql_500_ticker_expansion_design_gate.py", "--write", "--validate"], ROOT, 240),
        (
            "go_sql_500_expansion_gate",
            go_script_bin_command(
                "go-sql-500-expansion-design-gate",
                "--root",
                str(ROOT),
                "--driver",
                "inprocess",
                "--out",
                str(TMP / "go-sql-500-ticker-expansion-design-gate.json"),
            ),
            ROOT,
            240,
        ),
        ("python_go_sql_500_expansion_gate_parity", [sys.executable, "scripts\\python_go_sql_500_expansion_gate_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_finance_data_coverage", [sys.executable, "scripts\\finance_data_coverage.py", "--write-contract", "--validate"], ROOT, 240),
        ("go_finance_data_coverage_probe", ["go", "run", ".\\cmd\\go-finance-data-coverage-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\go-finance-data-coverage-probe.json"], ROOT / "scripts" / "go", 240),
        ("python_go_finance_data_coverage_probe_parity", [sys.executable, "scripts\\python_go_finance_data_coverage_probe_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_finance_human_notes_thinning_candidates", [sys.executable, "scripts\\finance_human_notes_thinning_candidates.py", "--write", "--validate"], ROOT, 240),
        ("python_go_finance_human_notes_sql_check_parity", [sys.executable, "scripts\\python_go_finance_human_notes_sql_check_parity.py", "--write", "--validate"], ROOT, 240),
        (
            "go_sql_inprocess_driver_pilot_gate_artifact_validate",
            [
                sys.executable,
                "scripts\\go_sql_inprocess_driver_pilot_gate.py",
                "--write",
                "--write-md",
                "--validate",
                "--parent-runtime-scorecard",
                "--parent-harness-scorecard",
                "--quiet",
            ],
            ROOT,
            60,
        ),
        ("python_finance_universe_validator", [sys.executable, "scripts\\finance_universe_validator.py", "--validate"], ROOT, 240),
        ("go_finance_universe_validation_probe", ["go", "run", ".\\cmd\\go-finance-universe-validation-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\go-finance-universe-validation-probe.json"], ROOT / "scripts" / "go", 240),
        ("python_go_finance_universe_validation_parity", [sys.executable, "scripts\\python_go_finance_universe_validation_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_wf78_sql_phase2_readiness", [sys.executable, "scripts\\wf78_sql_phase2_readiness.py"], ROOT, 240),
        ("go_wf78_sql_phase2_readiness_probe", ["go", "run", ".\\cmd\\go-wf78-sql-phase2-readiness-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\go-wf78-sql-phase2-readiness-probe.json"], ROOT / "scripts" / "go", 240),
        ("python_go_wf78_sql_phase2_readiness_parity", [sys.executable, "scripts\\python_go_wf78_sql_phase2_readiness_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_go_durable_output_parity_repeated_gate", [sys.executable, "scripts\\python_go_durable_output_parity_repeated_gate.py", "--write", "--validate", "--cycles", "3"], ROOT, 240),
        ("go_sql_consumer_authority_guard", ["go", "run", ".\\cmd\\go-sql-consumer-authority-guard", "--root", "..\\..", "--out", "..\\..\\tmp\\go-sql-consumer-authority-guard.json"], ROOT / "scripts" / "go", 240),
        ("python_go_sql_consumer_authority_guard_parity", [sys.executable, "scripts\\python_go_sql_consumer_authority_guard_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_consumer_authority_guard_fixture_parity", [sys.executable, "scripts\\python_go_sql_consumer_authority_guard_fixture_parity.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_consumer_authority_dashboard_ab", [sys.executable, "scripts\\python_go_sql_consumer_authority_dashboard_ab.py", "--write", "--validate", "--cycles", "3"], ROOT, 240),
        ("python_go_sql_consumer_authority_demotion_dry_run", [sys.executable, "scripts\\python_go_sql_consumer_authority_demotion_dry_run.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_consumer_authority_controlled_router", [sys.executable, "scripts\\python_go_sql_consumer_authority_controlled_router.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_helper_demotion_readiness_gate", [sys.executable, "scripts\\python_go_sql_helper_demotion_readiness_gate.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_helper_demotion_queue", [sys.executable, "scripts\\python_go_sql_helper_demotion_queue.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_helper_contract_gate", [sys.executable, "scripts\\python_go_sql_helper_contract_gate.py", "--write", "--validate", "--allow-runtime-self-cycle"], ROOT, 240),
        ("python_go_sql_helper_controlled_router_batch", [sys.executable, "scripts\\python_go_sql_helper_controlled_router_batch.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_helper_go_primary_history_gate", [sys.executable, "scripts\\python_go_sql_helper_go_primary_history_gate.py", "--write", "--validate", "--cycles", "3"], ROOT, 240),
        ("python_go_sql_helper_default_route_promotion", [sys.executable, "scripts\\python_go_sql_helper_default_route_promotion.py", "--write", "--validate"], ROOT, 240),
        ("python_go_sql_helper_default_route_history_gate", [sys.executable, "scripts\\python_go_sql_helper_default_route_history_gate.py", "--write", "--write-history", "--validate", "--cycles", "5"], ROOT, 240),
        ("python_go_sql_helper_fallback_removal_readiness_gate", [sys.executable, "scripts\\python_go_sql_helper_fallback_removal_readiness_gate.py", "--write", "--validate", "--parent-runtime-scorecard"], ROOT, 240),
        ("python_go_sql_helper_retirement_gate", [sys.executable, "scripts\\python_go_sql_helper_retirement_gate.py", "--write", "--validate", "--parent-runtime-scorecard"], ROOT, 240),
        ("go_sql_schema_drift_lint", ["go", "run", ".\\cmd\\sql-schema-drift-lint", "--root", "..\\..", "--out", "..\\..\\tmp\\sql-schema-drift-lint.json"], ROOT / "scripts" / "go", 240),
        ("go_sql_proof_probe", ["go", "run", ".\\cmd\\sql-proof-probe", "--root", "..\\..", "--out", "..\\..\\tmp\\sql-proof-probe.json"], ROOT / "scripts" / "go", 240),
        ("python_pm_program_state", [sys.executable, "scripts\\pm_program_state.py", "--write", "--write-db", "--validate"], ROOT, 240),
        ("python_artifact_index_incremental", [sys.executable, "scripts\\artifact_index.py", "incremental"], ROOT, 240),
        ("python_artifact_index_validate", [sys.executable, "scripts\\artifact_index.py", "validate"], ROOT, 240),
        ("python_sql_coverage_guard", [sys.executable, "scripts\\sql_coverage_guard.py", "--write", "--validate"], ROOT, 240),
        ("python_capital_deployment_band_integrity_validator", [sys.executable, "scripts\\capital_deployment_band_integrity_validator.py", "--write", "--write-md", "--validate"], ROOT, 120),
    ]
    if not args.quick:
        plan.append(("node_pm_cockpit_validate", ["npm", "run", "validate"], ROOT / "apps" / "pm-control-cockpit", 240))
    return plan


def runtime_summary(commands: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in commands:
        runtime = str(row.get("runtime") or "other")
        bucket = buckets.setdefault(runtime, {"checks": 0, "blocked": 0, "total_duration_ms": 0.0, "max_duration_ms": 0.0})
        bucket["checks"] += 1
        if row.get("status") != "ok":
            bucket["blocked"] += 1
        duration = float(row.get("duration_ms") or 0)
        bucket["total_duration_ms"] = round(float(bucket["total_duration_ms"]) + duration, 3)
        bucket["max_duration_ms"] = max(float(bucket["max_duration_ms"]), duration)
    return buckets


def latest_history(path: Path) -> dict[str, Any]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError:
        return {}
    if not lines:
        return {}
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {}


def regression_check(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"has_previous": False, "warnings": []}
    warnings: list[str] = []
    cur_total = float(as_dict(current.get("summary")).get("total_duration_ms") or 0)
    prev_total = float(as_dict(previous.get("summary")).get("total_duration_ms") or 0)
    if prev_total > 0 and cur_total > 5000 and cur_total > prev_total * 1.75:
        warnings.append(f"total_runtime_regression previous_ms={prev_total:.3f} current_ms={cur_total:.3f}")
    cur_sql = float(as_dict(as_dict(current.get("artifacts")).get("sql_latency")).get("max_p95_ms") or 0)
    prev_sql = float(as_dict(as_dict(previous.get("artifacts")).get("sql_latency")).get("max_p95_ms") or 0)
    if prev_sql > 0 and cur_sql > 5 and cur_sql > prev_sql * 2:
        warnings.append(f"sql_p95_regression previous_ms={prev_sql:.3f} current_ms={cur_sql:.3f}")
    return {"has_previous": True, "warnings": warnings}


def artifact_snapshot() -> dict[str, Any]:
    sql_latency = as_dict(load_json_artifact(TMP / "sql-latency-benchmark-current.json"))
    go_sql_latency = as_dict(load_json_artifact(TMP / "go-sql-latency-probe.json"))
    go_sql_inventory = as_dict(load_json_artifact(TMP / "go-sql-inventory-helper.json"))
    python_go_parity = as_dict(load_json_artifact(TMP / "python-go-sql-parity-check.json"))
    finance_lint = as_dict(load_json_artifact(TMP / "finance-sql-boundary-lint.json"))
    python_sql_lint = as_dict(load_json_artifact(TMP / "python-sql-contract-lint.json"))
    python_go_candidates = as_dict(load_json_artifact(TMP / "python-go-sql-migration-candidates.json"))
    go_source_truth_manifest = as_dict(load_json_artifact(TMP / "go-sql-source-truth-authority-manifest.json"))
    source_truth_manifest_parity = as_dict(load_json_artifact(TMP / "python-go-source-truth-manifest-parity.json"))
    go_source_truth_parity = as_dict(load_json_artifact(TMP / "go-source-truth-parity-validation.json"))
    source_truth_parity_gate = as_dict(load_json_artifact(TMP / "python-go-source-truth-parity-validator-parity.json"))
    go_500_expansion_gate = as_dict(load_json_artifact(TMP / "go-sql-500-ticker-expansion-design-gate.json"))
    expansion_gate_parity = as_dict(load_json_artifact(TMP / "python-go-sql-500-expansion-gate-parity.json"))
    go_finance_data_coverage = as_dict(load_json_artifact(TMP / "go-finance-data-coverage-probe.json"))
    finance_data_coverage_parity = as_dict(load_json_artifact(TMP / "python-go-finance-data-coverage-probe-parity.json"))
    go_finance_human_notes = as_dict(load_json_artifact(TMP / "go-finance-human-notes-sql-check.json"))
    finance_human_notes_parity = as_dict(load_json_artifact(TMP / "python-go-finance-human-notes-sql-check-parity.json"))
    go_sql_inprocess_driver_pilot = as_dict(load_json_artifact(TMP / "go-sql-inprocess-driver-pilot-gate.json"))
    go_finance_universe_validation = as_dict(load_json_artifact(TMP / "go-finance-universe-validation-probe.json"))
    finance_universe_validation_parity = as_dict(load_json_artifact(TMP / "python-go-finance-universe-validation-parity.json"))
    go_wf78_phase2_readiness = as_dict(load_json_artifact(TMP / "go-wf78-sql-phase2-readiness-probe.json"))
    wf78_phase2_readiness_parity = as_dict(load_json_artifact(TMP / "python-go-wf78-sql-phase2-readiness-parity.json"))
    durable_output_repeated_gate = as_dict(load_json_artifact(TMP / "python-go-durable-output-parity-repeated-gate.json"))
    go_sql_consumer_authority = as_dict(load_json_artifact(TMP / "go-sql-consumer-authority-guard.json"))
    sql_consumer_authority_parity = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-guard-parity.json"))
    sql_consumer_authority_fixture_parity = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-guard-fixture-parity.json"))
    sql_consumer_authority_dashboard_ab = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-dashboard-ab.json"))
    sql_consumer_authority_demotion_dry_run = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-demotion-dry-run.json"))
    sql_consumer_authority_controlled_router = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-controlled-router.json"))
    sql_helper_demotion_readiness_gate = as_dict(load_json_artifact(TMP / "python-go-sql-helper-demotion-readiness-gate.json"))
    sql_helper_demotion_queue = as_dict(load_json_artifact(TMP / "python-go-sql-helper-demotion-queue.json"))
    sql_helper_contract_gate = as_dict(load_json_artifact(TMP / "python-go-sql-helper-contract-gate.json"))
    sql_helper_controlled_router_batch = as_dict(load_json_artifact(TMP / "python-go-sql-helper-controlled-router-batch.json"))
    sql_helper_go_primary_history_gate = as_dict(load_json_artifact(TMP / "python-go-sql-helper-go-primary-history-gate.json"))
    sql_helper_default_route_promotion = as_dict(load_json_artifact(TMP / "python-go-sql-helper-default-route-promotion.json"))
    sql_helper_default_route_history_gate = as_dict(load_json_artifact(TMP / "python-go-sql-helper-default-route-history-gate.json"))
    sql_helper_fallback_removal_readiness_gate = as_dict(load_json_artifact(TMP / "python-go-sql-helper-fallback-removal-readiness-gate.json"))
    sql_helper_retirement_gate = as_dict(load_json_artifact(TMP / "python-go-sql-helper-retirement-gate.json"))
    schema_lint = as_dict(load_json_artifact(TMP / "sql-schema-drift-lint.json"))
    sql_proof_probe = as_dict(load_json_artifact(TMP / "sql-proof-probe.json"))
    smb_lint = as_dict(load_json_artifact(TMP / "wf75-smb-boundary-lint.json"))
    capital_band_integrity = as_dict(load_json_artifact(TMP / "capital-deployment-band-integrity-validator.json"))
    pm_state = pm_program_state()
    return {
        "sql_latency": {
            "path": "tmp/sql-latency-benchmark-current.json",
            "status": sql_latency.get("status"),
            "max_p95_ms": as_dict(sql_latency.get("summary")).get("max_p95_ms"),
            "benchmarks": as_dict(sql_latency.get("summary")).get("benchmarks"),
        },
        "go_sql_latency_probe": {
            "path": "tmp/go-sql-latency-probe.json",
            "status": go_sql_latency.get("status"),
            "sqlite_driver": go_sql_latency.get("sqlite_driver"),
            "max_p95_ms": as_dict(go_sql_latency.get("summary")).get("max_p95_ms"),
            "benchmarks": as_dict(go_sql_latency.get("summary")).get("benchmarks"),
            "successful": as_dict(go_sql_latency.get("summary")).get("successful"),
        },
        "go_sql_inventory_helper": {
            "path": "tmp/go-sql-inventory-helper.json",
            "status": go_sql_inventory.get("status"),
            "sqlite_driver": go_sql_inventory.get("sqlite_driver"),
            "databases": as_dict(go_sql_inventory.get("summary")).get("databases"),
            "present": as_dict(go_sql_inventory.get("summary")).get("present"),
            "tables": as_dict(go_sql_inventory.get("summary")).get("tables"),
            "views": as_dict(go_sql_inventory.get("summary")).get("views"),
            "total_rows": as_dict(go_sql_inventory.get("summary")).get("total_rows"),
            "missing_tables": as_dict(go_sql_inventory.get("summary")).get("missing_tables"),
        },
        "python_go_sql_parity_check": {
            "path": "tmp/python-go-sql-parity-check.json",
            "status": python_go_parity.get("status"),
            "checks": as_dict(python_go_parity.get("summary")).get("checks"),
            "critical": as_dict(python_go_parity.get("summary")).get("critical"),
            "warnings": as_dict(python_go_parity.get("summary")).get("warnings"),
            "latency_pairs": as_dict(python_go_parity.get("summary")).get("latency_pairs"),
            "row_count_mismatches": as_dict(python_go_parity.get("summary")).get("row_count_mismatches"),
        },
        "finance_sql_boundary_lint": {
            "path": "tmp/finance-sql-boundary-lint.json",
            "status": finance_lint.get("status"),
            "checks": as_dict(finance_lint.get("summary")).get("checks"),
            "critical": as_dict(finance_lint.get("summary")).get("critical"),
            "warnings": as_dict(finance_lint.get("summary")).get("warnings"),
        },
        "smb_go_boundary_lint": {
            "path": "tmp/wf75-smb-boundary-lint.json",
            "status": smb_lint.get("status"),
            "checks": as_dict(smb_lint.get("summary")).get("checks"),
            "critical": as_dict(smb_lint.get("summary")).get("critical"),
        },
        "python_sql_contract_lint": {
            "path": "tmp/python-sql-contract-lint.json",
            "status": python_sql_lint.get("status"),
            "checks": as_dict(python_sql_lint.get("summary")).get("checks"),
            "critical": as_dict(python_sql_lint.get("summary")).get("critical"),
            "warnings": as_dict(python_sql_lint.get("summary")).get("warnings"),
        },
        "python_go_sql_migration_candidates": {
            "path": "tmp/python-go-sql-migration-candidates.json",
            "status": python_go_candidates.get("status"),
            "candidates_total": as_dict(python_go_candidates.get("summary")).get("candidates_total"),
            "ready_for_go_spike": as_dict(python_go_candidates.get("summary")).get("ready_for_go_spike"),
            "keep_python_governed": as_dict(python_go_candidates.get("summary")).get("keep_python_governed"),
        },
        "capital_deployment_band_integrity": {
            "path": "tmp/capital-deployment-band-integrity-validator.json",
            "status": capital_band_integrity.get("status"),
            "domain_status": as_dict(capital_band_integrity.get("validation")).get("domain_status"),
            "ticker_count": as_dict(capital_band_integrity.get("summary")).get("ticker_count"),
            "critical_count": as_dict(capital_band_integrity.get("summary")).get("critical_count"),
            "warning_count": as_dict(capital_band_integrity.get("summary")).get("warning_count"),
            "mismatch_tickers": as_dict(capital_band_integrity.get("summary")).get("mismatch_tickers"),
        },
        "go_sql_source_truth_manifest": {
            "path": "tmp/go-sql-source-truth-authority-manifest.json",
            "status": go_source_truth_manifest.get("status"),
            "database_surfaces": as_dict(go_source_truth_manifest.get("summary")).get("database_surfaces"),
            "canonical_owner_notes": as_dict(go_source_truth_manifest.get("summary")).get("canonical_owner_notes"),
            "errors": len(as_list(as_dict(go_source_truth_manifest.get("summary")).get("errors"))),
        },
        "python_go_source_truth_manifest_parity": {
            "path": "tmp/python-go-source-truth-manifest-parity.json",
            "status": source_truth_manifest_parity.get("status"),
            "checks": as_dict(source_truth_manifest_parity.get("summary")).get("checks"),
            "critical": as_dict(source_truth_manifest_parity.get("summary")).get("critical"),
            "warnings": as_dict(source_truth_manifest_parity.get("summary")).get("warnings"),
        },
        "go_source_truth_parity_validator": {
            "path": "tmp/go-source-truth-parity-validation.json",
            "status": go_source_truth_parity.get("status"),
            "markdown_rows": as_dict(go_source_truth_parity.get("summary")).get("markdown_rows"),
            "ready_rows": as_dict(go_source_truth_parity.get("summary")).get("ready_rows"),
            "mismatch_rows": as_dict(go_source_truth_parity.get("summary")).get("mismatch_rows"),
        },
        "python_go_source_truth_parity_validator_parity": {
            "path": "tmp/python-go-source-truth-parity-validator-parity.json",
            "status": source_truth_parity_gate.get("status"),
            "checks": as_dict(source_truth_parity_gate.get("summary")).get("checks"),
            "critical": as_dict(source_truth_parity_gate.get("summary")).get("critical"),
            "warnings": as_dict(source_truth_parity_gate.get("summary")).get("warnings"),
        },
        "go_sql_500_expansion_gate": {
            "path": "tmp/go-sql-500-ticker-expansion-design-gate.json",
            "status": go_500_expansion_gate.get("status"),
            "validation_status": as_dict(go_500_expansion_gate.get("validation")).get("status"),
            "production_current_cards": as_dict(go_500_expansion_gate.get("current_state")).get("production_current_cards"),
            "live_pilot_candidates": as_dict(go_500_expansion_gate.get("current_state")).get("live_pilot_candidates"),
        },
        "python_go_sql_500_expansion_gate_parity": {
            "path": "tmp/python-go-sql-500-expansion-gate-parity.json",
            "status": expansion_gate_parity.get("status"),
            "checks": as_dict(expansion_gate_parity.get("summary")).get("checks"),
            "critical": as_dict(expansion_gate_parity.get("summary")).get("critical"),
            "warnings": as_dict(expansion_gate_parity.get("summary")).get("warnings"),
        },
        "go_finance_data_coverage_probe": {
            "path": "tmp/go-finance-data-coverage-probe.json",
            "status": go_finance_data_coverage.get("status"),
            "source_status": go_finance_data_coverage.get("source_status"),
            "data_family_count": as_dict(go_finance_data_coverage.get("summary")).get("data_family_count"),
            "ticker_count_indexed": as_dict(go_finance_data_coverage.get("summary")).get("ticker_count_indexed"),
            "source_artifact_count": as_dict(go_finance_data_coverage.get("summary")).get("source_artifact_count"),
        },
        "python_go_finance_data_coverage_probe_parity": {
            "path": "tmp/python-go-finance-data-coverage-probe-parity.json",
            "status": finance_data_coverage_parity.get("status"),
            "checks": as_dict(finance_data_coverage_parity.get("summary")).get("checks"),
            "critical": as_dict(finance_data_coverage_parity.get("summary")).get("critical"),
            "warnings": as_dict(finance_data_coverage_parity.get("summary")).get("warnings"),
        },
        "go_finance_human_notes_sql_check": {
            "path": "tmp/go-finance-human-notes-sql-check.json",
            "status": go_finance_human_notes.get("status"),
            "sql_canon_check": as_dict(go_finance_human_notes.get("sql_canon_check")).get("status"),
            "sqlite_driver": as_dict(go_finance_human_notes.get("sql_canon_check")).get("sqlite_driver"),
            "active_ticker_count": as_dict(go_finance_human_notes.get("sql_canon_check")).get("active_ticker_count"),
            "legacy_answer_path_count": as_dict(go_finance_human_notes.get("sql_canon_check")).get("legacy_answer_path_count"),
            "review_monitor_count": as_dict(go_finance_human_notes.get("sql_canon_check")).get("review_monitor_count"),
        },
        "python_go_finance_human_notes_sql_check_parity": {
            "path": "tmp/python-go-finance-human-notes-sql-check-parity.json",
            "status": finance_human_notes_parity.get("status"),
            "checks": as_dict(finance_human_notes_parity.get("summary")).get("checks"),
            "critical": as_dict(finance_human_notes_parity.get("summary")).get("critical"),
            "warnings": as_dict(finance_human_notes_parity.get("summary")).get("warnings"),
        },
        "go_finance_universe_validation_probe": {
            "path": "tmp/go-finance-universe-validation-probe.json",
            "status": go_finance_universe_validation.get("status"),
            "active_ticker_count": as_dict(go_finance_universe_validation.get("semantic_summary")).get("active_ticker_count"),
            "production_active_ticker_count": as_dict(go_finance_universe_validation.get("semantic_summary")).get("production_active_ticker_count"),
            "review_100_monitor_count": as_dict(go_finance_universe_validation.get("semantic_summary")).get("review_100_monitor_count"),
            "validation_failed": as_dict(go_finance_universe_validation.get("semantic_summary")).get("validation_failed"),
        },
        "python_go_finance_universe_validation_parity": {
            "path": "tmp/python-go-finance-universe-validation-parity.json",
            "status": finance_universe_validation_parity.get("status"),
            "checks": as_dict(finance_universe_validation_parity.get("summary")).get("checks"),
            "critical": as_dict(finance_universe_validation_parity.get("summary")).get("critical"),
            "warnings": as_dict(finance_universe_validation_parity.get("summary")).get("warnings"),
        },
        "go_wf78_sql_phase2_readiness_probe": {
            "path": "tmp/go-wf78-sql-phase2-readiness-probe.json",
            "status": go_wf78_phase2_readiness.get("status"),
            "workflow": as_dict(go_wf78_phase2_readiness.get("semantic_summary")).get("workflow"),
            "phase": as_dict(go_wf78_phase2_readiness.get("semantic_summary")).get("phase"),
            "surface_count": as_dict(go_wf78_phase2_readiness.get("semantic_summary")).get("surface_count"),
            "blocked_surface_count": as_dict(go_wf78_phase2_readiness.get("semantic_summary")).get("blocked_surface_count"),
        },
        "python_go_wf78_sql_phase2_readiness_parity": {
            "path": "tmp/python-go-wf78-sql-phase2-readiness-parity.json",
            "status": wf78_phase2_readiness_parity.get("status"),
            "checks": as_dict(wf78_phase2_readiness_parity.get("summary")).get("checks"),
            "critical": as_dict(wf78_phase2_readiness_parity.get("summary")).get("critical"),
            "warnings": as_dict(wf78_phase2_readiness_parity.get("summary")).get("warnings"),
        },
        "python_go_durable_output_parity_repeated_gate": {
            "path": "tmp/python-go-durable-output-parity-repeated-gate.json",
            "status": durable_output_repeated_gate.get("status"),
            "checks": as_dict(durable_output_repeated_gate.get("summary")).get("checks"),
            "critical": as_dict(durable_output_repeated_gate.get("summary")).get("critical"),
            "warnings": as_dict(durable_output_repeated_gate.get("summary")).get("warnings"),
            "cycles": as_dict(durable_output_repeated_gate.get("summary")).get("cycles"),
            "cases": as_dict(durable_output_repeated_gate.get("summary")).get("cases"),
            "stable_case_fingerprints": as_dict(durable_output_repeated_gate.get("summary")).get("stable_case_fingerprints"),
            "durable_output_signal": as_dict(durable_output_repeated_gate.get("summary")).get("durable_output_signal"),
        },
        "go_sql_consumer_authority_guard": {
            "path": "tmp/go-sql-consumer-authority-guard.json",
            "status": go_sql_consumer_authority.get("status"),
            "sql_read_allowed": go_sql_consumer_authority.get("sql_read_allowed"),
            "checks": as_dict(go_sql_consumer_authority.get("summary")).get("checks"),
            "failed": as_dict(go_sql_consumer_authority.get("summary")).get("failed"),
            "fallback_missing_keys": as_dict(go_sql_consumer_authority.get("summary")).get("fallback_missing_keys"),
            "extra_keys": as_dict(go_sql_consumer_authority.get("summary")).get("extra_keys"),
            "cache_stale_or_unsafe_rows": as_dict(go_sql_consumer_authority.get("summary")).get("cache_stale_or_unsafe_rows"),
        },
        "python_go_sql_consumer_authority_guard_parity": {
            "path": "tmp/python-go-sql-consumer-authority-guard-parity.json",
            "status": sql_consumer_authority_parity.get("status"),
            "checks": as_dict(sql_consumer_authority_parity.get("summary")).get("checks"),
            "critical": as_dict(sql_consumer_authority_parity.get("summary")).get("critical"),
            "warnings": as_dict(sql_consumer_authority_parity.get("summary")).get("warnings"),
        },
        "python_go_sql_consumer_authority_guard_fixture_parity": {
            "path": "tmp/python-go-sql-consumer-authority-guard-fixture-parity.json",
            "status": sql_consumer_authority_fixture_parity.get("status"),
            "checks": as_dict(sql_consumer_authority_fixture_parity.get("summary")).get("checks"),
            "critical": as_dict(sql_consumer_authority_fixture_parity.get("summary")).get("critical"),
            "warnings": as_dict(sql_consumer_authority_fixture_parity.get("summary")).get("warnings"),
            "demotion_readiness_signal": as_dict(sql_consumer_authority_fixture_parity.get("summary")).get("demotion_readiness_signal"),
        },
        "python_go_sql_consumer_authority_dashboard_ab": {
            "path": "tmp/python-go-sql-consumer-authority-dashboard-ab.json",
            "status": sql_consumer_authority_dashboard_ab.get("status"),
            "checks": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("checks"),
            "critical": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("critical"),
            "warnings": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("warnings"),
            "cycles": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("cycles"),
            "cases_per_cycle": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("cases_per_cycle"),
            "case_fingerprints_stable": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("case_fingerprints_stable"),
            "demotion_readiness_signal": as_dict(sql_consumer_authority_dashboard_ab.get("summary")).get("demotion_readiness_signal"),
        },
        "python_go_sql_consumer_authority_demotion_dry_run": {
            "path": "tmp/python-go-sql-consumer-authority-demotion-dry-run.json",
            "status": sql_consumer_authority_demotion_dry_run.get("status"),
            "checks": as_dict(sql_consumer_authority_demotion_dry_run.get("summary")).get("checks"),
            "critical": as_dict(sql_consumer_authority_demotion_dry_run.get("summary")).get("critical"),
            "warnings": as_dict(sql_consumer_authority_demotion_dry_run.get("summary")).get("warnings"),
            "go_primary_allowed_cases": as_dict(sql_consumer_authority_demotion_dry_run.get("summary")).get("go_primary_allowed_cases"),
            "python_fallback_cases": as_dict(sql_consumer_authority_demotion_dry_run.get("summary")).get("python_fallback_cases"),
            "dry_run_signal": as_dict(sql_consumer_authority_demotion_dry_run.get("summary")).get("dry_run_signal"),
        },
        "python_go_sql_consumer_authority_controlled_router": {
            "path": "tmp/python-go-sql-consumer-authority-controlled-router.json",
            "status": sql_consumer_authority_controlled_router.get("status"),
            "checks": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("checks"),
            "critical": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("critical"),
            "warnings": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("warnings"),
            "go_primary_allowed_cases": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("go_primary_allowed_cases"),
            "python_fallback_cases": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("python_fallback_cases"),
            "default_mode": as_dict(sql_consumer_authority_controlled_router.get("route_contract")).get("default_mode"),
            "cycles": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("cycles"),
            "route_fingerprints_stable": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("route_fingerprints_stable"),
            "controlled_router_signal": as_dict(sql_consumer_authority_controlled_router.get("summary")).get("controlled_router_signal"),
        },
        "python_go_sql_helper_demotion_readiness_gate": {
            "path": "tmp/python-go-sql-helper-demotion-readiness-gate.json",
            "status": sql_helper_demotion_readiness_gate.get("status"),
            "checks": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("warnings"),
            "ready_for_go_spike_contracts": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("ready_for_go_spike_contracts"),
            "durable_output_candidates": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("durable_output_candidates"),
            "retire_python_now": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("retire_python_now"),
            "demotion_gate_signal": as_dict(sql_helper_demotion_readiness_gate.get("summary")).get("demotion_gate_signal"),
        },
        "python_go_sql_helper_demotion_queue": {
            "path": "tmp/python-go-sql-helper-demotion-queue.json",
            "status": sql_helper_demotion_queue.get("status"),
            "checks": as_dict(sql_helper_demotion_queue.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_demotion_queue.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_demotion_queue.get("summary")).get("warnings"),
            "controlled_demoted_helpers": as_dict(sql_helper_demotion_queue.get("summary")).get("controlled_demoted_helpers"),
            "next_queue_candidates": as_dict(sql_helper_demotion_queue.get("summary")).get("next_queue_candidates"),
            "retire_python_now": as_dict(sql_helper_demotion_queue.get("summary")).get("retire_python_now"),
            "queue_signal": as_dict(sql_helper_demotion_queue.get("summary")).get("queue_signal"),
        },
        "python_go_sql_helper_contract_gate": {
            "path": "tmp/python-go-sql-helper-contract-gate.json",
            "status": sql_helper_contract_gate.get("status"),
            "checks": as_dict(sql_helper_contract_gate.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_contract_gate.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_contract_gate.get("summary")).get("warnings"),
            "contracts_total": as_dict(sql_helper_contract_gate.get("summary")).get("contracts_total"),
            "fixture_contracts_captured": as_dict(sql_helper_contract_gate.get("summary")).get("fixture_contracts_captured"),
            "semantic_shape_parity_green": as_dict(sql_helper_contract_gate.get("summary")).get("semantic_shape_parity_green"),
            "durable_output_parity_pending": as_dict(sql_helper_contract_gate.get("summary")).get("durable_output_parity_pending"),
            "controlled_router_design_eligible": as_dict(sql_helper_contract_gate.get("summary")).get("controlled_router_design_eligible"),
            "retire_python_now": as_dict(sql_helper_contract_gate.get("summary")).get("retire_python_now"),
            "contract_gate_signal": as_dict(sql_helper_contract_gate.get("summary")).get("contract_gate_signal"),
        },
        "python_go_sql_helper_controlled_router_batch": {
            "path": "tmp/python-go-sql-helper-controlled-router-batch.json",
            "status": sql_helper_controlled_router_batch.get("status"),
            "checks": as_dict(sql_helper_controlled_router_batch.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_controlled_router_batch.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_controlled_router_batch.get("summary")).get("warnings"),
            "batch_controlled_demoted_helpers": as_dict(sql_helper_controlled_router_batch.get("summary")).get("batch_controlled_demoted_helpers"),
            "total_controlled_demoted_helpers_including_first": as_dict(sql_helper_controlled_router_batch.get("summary")).get("total_controlled_demoted_helpers_including_first"),
            "retire_python_now": as_dict(sql_helper_controlled_router_batch.get("summary")).get("retire_python_now"),
            "batch_signal": as_dict(sql_helper_controlled_router_batch.get("summary")).get("batch_signal"),
        },
        "python_go_sql_helper_go_primary_history_gate": {
            "path": "tmp/python-go-sql-helper-go-primary-history-gate.json",
            "status": sql_helper_go_primary_history_gate.get("status"),
            "checks": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("warnings"),
            "cycles": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("cycles"),
            "routes_per_cycle": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("routes_per_cycle"),
            "stable_route_fingerprints": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("stable_route_fingerprints"),
            "retire_python_now": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("retire_python_now"),
            "go_primary_history_signal": as_dict(sql_helper_go_primary_history_gate.get("summary")).get("go_primary_history_signal"),
        },
        "python_go_sql_helper_default_route_promotion": {
            "path": "tmp/python-go-sql-helper-default-route-promotion.json",
            "status": sql_helper_default_route_promotion.get("status"),
            "checks": as_dict(sql_helper_default_route_promotion.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_default_route_promotion.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_default_route_promotion.get("summary")).get("warnings"),
            "default_route_promoted_helpers": as_dict(sql_helper_default_route_promotion.get("summary")).get("default_route_promoted_helpers"),
            "default_route": as_dict(sql_helper_default_route_promotion.get("summary")).get("default_route"),
            "retire_python_now": as_dict(sql_helper_default_route_promotion.get("summary")).get("retire_python_now"),
            "default_route_promotion_signal": as_dict(sql_helper_default_route_promotion.get("summary")).get("default_route_promotion_signal"),
        },
        "python_go_sql_helper_default_route_history_gate": {
            "path": "tmp/python-go-sql-helper-default-route-history-gate.json",
            "status": sql_helper_default_route_history_gate.get("status"),
            "checks": as_dict(sql_helper_default_route_history_gate.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_default_route_history_gate.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_default_route_history_gate.get("summary")).get("warnings"),
            "cycles": as_dict(sql_helper_default_route_history_gate.get("summary")).get("cycles"),
            "routes_per_cycle": as_dict(sql_helper_default_route_history_gate.get("summary")).get("routes_per_cycle"),
            "stable_route_fingerprints": as_dict(sql_helper_default_route_history_gate.get("summary")).get("stable_route_fingerprints"),
            "retire_python_now": as_dict(sql_helper_default_route_history_gate.get("summary")).get("retire_python_now"),
            "default_route_history_signal": as_dict(sql_helper_default_route_history_gate.get("summary")).get("default_route_history_signal"),
        },
        "python_go_sql_helper_fallback_removal_readiness_gate": {
            "path": "tmp/python-go-sql-helper-fallback-removal-readiness-gate.json",
            "status": sql_helper_fallback_removal_readiness_gate.get("status"),
            "checks": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("warnings"),
            "promoted_helpers": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("promoted_helpers"),
            "fallback_removal_proposal_ready": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("fallback_removal_proposal_ready"),
            "fallback_removal_allowed": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("fallback_removal_allowed"),
            "retire_python_now": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("retire_python_now"),
            "readiness_signal": as_dict(sql_helper_fallback_removal_readiness_gate.get("summary")).get("readiness_signal"),
        },
        "python_go_sql_helper_retirement_gate": {
            "path": "tmp/python-go-sql-helper-retirement-gate.json",
            "status": sql_helper_retirement_gate.get("status"),
            "checks": as_dict(sql_helper_retirement_gate.get("summary")).get("checks"),
            "critical": as_dict(sql_helper_retirement_gate.get("summary")).get("critical"),
            "warnings": as_dict(sql_helper_retirement_gate.get("summary")).get("warnings"),
            "controlled_demoted_helpers": as_dict(sql_helper_retirement_gate.get("summary")).get("controlled_demoted_helpers"),
            "retirement_ready": as_dict(sql_helper_retirement_gate.get("summary")).get("retirement_ready"),
            "retire_python_now": as_dict(sql_helper_retirement_gate.get("summary")).get("retire_python_now"),
            "python_file_delete_allowed": as_dict(sql_helper_retirement_gate.get("summary")).get("python_file_delete_allowed"),
            "retirement_gate_signal": as_dict(sql_helper_retirement_gate.get("summary")).get("retirement_gate_signal"),
        },
        "go_sql_inprocess_driver_pilot_gate": {
            "path": "tmp/go-sql-inprocess-driver-pilot-gate.json",
            "status": go_sql_inprocess_driver_pilot.get("status"),
            "helpers_compared": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("helpers_compared"),
            "helpers_ok": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("helpers_ok"),
            "read_only_probe_status": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("read_only_probe_status"),
            "compiled_binary_ready": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("compiled_binary_ready"),
            "routing_changed_by_this_gate": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("routing_changed_by_this_gate"),
            "python_owner_default": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("python_owner_default"),
            "go_validator_only": as_dict(go_sql_inprocess_driver_pilot.get("summary")).get("go_validator_only"),
        },
        "sql_schema_drift_lint": {
            "path": "tmp/sql-schema-drift-lint.json",
            "status": schema_lint.get("status"),
            "checks": as_dict(schema_lint.get("summary")).get("checks"),
            "critical": as_dict(schema_lint.get("summary")).get("critical"),
            "warnings": as_dict(schema_lint.get("summary")).get("warnings"),
        },
        "sql_proof_probe": {
            "path": "tmp/sql-proof-probe.json",
            "status": sql_proof_probe.get("status"),
            "checks": as_dict(sql_proof_probe.get("summary")).get("checks"),
            "critical": as_dict(sql_proof_probe.get("summary")).get("critical"),
            "warnings": as_dict(sql_proof_probe.get("summary")).get("warnings"),
            "dbs": as_dict(sql_proof_probe.get("summary")).get("dbs"),
        },
        "pm_program_state": {
            "path": "tmp/pm-control-packet.json#sections.pm_program_state",
            "status": pm_state.get("status"),
            "lanes": len(as_list(pm_state.get("lanes"))),
        },
    }


def build_scorecard(args: argparse.Namespace) -> dict[str, Any]:
    if args.artifact_only:
        artifacts = artifact_snapshot()
        summary = {
            "checks_total": len(artifacts),
            "ok_count": len(artifacts),
            "blocked_count": 0,
            "total_duration_ms": 0,
            "max_command_duration_ms": 0,
            "quick_mode": bool(args.quick),
            "artifact_only": True,
        }
        scorecard = {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "ok",
            "workspace_root": str(ROOT),
            "summary": summary,
            "runtime_summary": {},
            "commands": [],
            "artifacts": artifacts,
            "authority_boundary": {
                "report_only": True,
                "db_mutation": False,
                "canon_or_portfolio_mutation": False,
                "customer_or_external_delivery": False,
                "paper_or_live_execution_authority": False,
                "owner_approval_inferred": False,
                "config_auth_runtime_mutation": False,
            },
            "notes": "Artifact-only refresh. Uses already regenerated validator artifacts as source-trust proof; it is not a fresh runtime timing benchmark.",
        }
        scorecard["regression_check"] = {"has_previous": bool(latest_history(args.history_out)), "warnings": ["artifact_only_no_runtime_timing"]}
        scorecard["validation"] = validate(scorecard)
        if scorecard["validation"]["status"] != "ok":
            scorecard["status"] = "blocked"
        return scorecard

    started = time.perf_counter()
    commands = [run_command(name, command, cwd=cwd, timeout=timeout) for name, command, cwd, timeout in command_plan(args)]
    blocked = [row for row in commands if row.get("status") != "ok"]
    summary = {
        "checks_total": len(commands),
        "ok_count": len(commands) - len(blocked),
        "blocked_count": len(blocked),
        "total_duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "max_command_duration_ms": max((float(row.get("duration_ms") or 0) for row in commands), default=0.0),
        "quick_mode": bool(args.quick),
    }
    scorecard = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if blocked else "ok",
        "workspace_root": str(ROOT),
        "summary": summary,
        "runtime_summary": runtime_summary(commands),
        "commands": commands,
        "artifacts": artifact_snapshot(),
        "authority_boundary": {
            "report_only": True,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution_authority": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
    }
    regression = regression_check(scorecard, latest_history(args.history_out))
    scorecard["regression_check"] = regression
    if scorecard["status"] == "ok" and regression.get("warnings"):
        scorecard["status"] = "warning"
    scorecard["validation"] = validate(scorecard)
    if scorecard["validation"]["status"] != "ok":
        scorecard["status"] = "blocked"
    return scorecard


def validate(scorecard: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if scorecard.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = as_dict(scorecard.get("authority_boundary"))
    for key, expected in {
        "report_only": True,
        "db_mutation": False,
        "canon_or_portfolio_mutation": False,
        "customer_or_external_delivery": False,
        "paper_or_live_execution_authority": False,
        "owner_approval_inferred": False,
        "config_auth_runtime_mutation": False,
    }.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    if int(as_dict(scorecard.get("summary")).get("blocked_count") or 0) > 0:
        warnings.append("one_or_more_runtime_checks_blocked")
    artifacts = as_dict(scorecard.get("artifacts"))
    for key in (
        "go_sql_latency_probe",
        "go_sql_inventory_helper",
        "go_finance_human_notes_sql_check",
    ):
        driver = as_dict(artifacts.get(key)).get("sqlite_driver")
        if driver != "inprocess":
            errors.append(f"{key} default artifact must use inprocess sqlite driver, observed={driver!r}")
    pilot = as_dict(artifacts.get("go_sql_inprocess_driver_pilot_gate"))
    python_owner_default = pilot.get("python_owner_default") is True or as_dict(pilot).get("default_route") == "python_owner_only"
    if pilot.get("status") != "ok":
        errors.append("go_sql_inprocess_driver_pilot_gate must be ok as a validator/proof gate")
    if python_owner_default and pilot.get("routing_changed_by_this_gate") is True:
        errors.append("go_sql_inprocess_driver_pilot_gate must not activate compiled-binary default routing while Python is owner/default")
    if not python_owner_default and pilot.get("routing_changed_by_this_gate") is not True:
        errors.append("go_sql_inprocess_driver_pilot_gate must be ok with compiled binary default route active when Python-owner rollback is not active")
    warnings.extend(as_list(as_dict(scorecard.get("regression_check")).get("warnings")))
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(scorecard: dict[str, Any]) -> str:
    summary = as_dict(scorecard.get("summary"))
    lines = [
        "# Runtime Performance Scorecard",
        "",
        f"- Generated: `{scorecard.get('generated_at_utc')}`",
        f"- Status: `{scorecard.get('status')}`",
        f"- Checks: `{summary.get('ok_count')}` ok / `{summary.get('blocked_count')}` blocked",
        f"- Total runtime: `{summary.get('total_duration_ms')}` ms",
        f"- Max command runtime: `{summary.get('max_command_duration_ms')}` ms",
        "",
        "## Runtime Buckets",
        "",
    ]
    for runtime, row in as_dict(scorecard.get("runtime_summary")).items():
        lines.append(f"- `{runtime}`: `{row.get('checks')}` checks, `{row.get('blocked')}` blocked, `{row.get('total_duration_ms')}` ms total")
    lines.extend(["", "## Commands", ""])
    for row in as_list(scorecard.get("commands")):
        if not isinstance(row, dict):
            continue
        lines.append(f"- `{row.get('status')}` {row.get('name')}: `{row.get('duration_ms')}` ms ({row.get('notes')})")
    warnings = as_list(as_dict(scorecard.get("regression_check")).get("warnings"))
    if warnings:
        lines.extend(["", "## Regression Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Report-only local proof. No canon/portfolio mutation, customer/external delivery, paper/live action, config/auth/runtime mutation, or owner approval inference.",
            "",
        ]
    )
    return "\n".join(lines)


def render_summary(scorecard: dict[str, Any]) -> str:
    summary = as_dict(scorecard.get("summary"))
    validation = as_dict(scorecard.get("validation"))
    return (
        "runtime_performance_scorecard "
        f"status={scorecard.get('status')} "
        f"checks={summary.get('ok_count')}/{summary.get('checks_total')} "
        f"blocked={summary.get('blocked_count')} "
        f"artifact_only={summary.get('artifact_only', False)} "
        f"quick={summary.get('quick_mode')} "
        f"total_ms={summary.get('total_duration_ms')} "
        f"validation={validation.get('status')} "
        f"path={rel(DEFAULT_JSON)}"
    )


def append_history(path: Path, scorecard: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    row = {
        "generated_at_utc": scorecard.get("generated_at_utc"),
        "status": scorecard.get("status"),
        "summary": scorecard.get("summary"),
        "runtime_summary": scorecard.get("runtime_summary"),
        "artifacts": scorecard.get("artifacts"),
    }
    atomic_write_text(path, existing + json.dumps(row, sort_keys=True) + "\n")


def write_bootstrap_placeholder(path: Path) -> None:
    placeholder = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "bootstrap",
        "summary": {
            "checks_total": 0,
            "ok_count": 0,
            "blocked_count": 0,
            "total_duration_ms": 0,
            "max_command_duration_ms": 0,
            "quick_mode": None,
        },
        "runtime_summary": {},
        "commands": [],
        "artifacts": {},
        "authority_boundary": {
            "report_only": True,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution_authority": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
        "notes": "Bootstrap placeholder written so source-readiness validators can see the required scorecard path during the first full run.",
    }
    atomic_write_json(path, placeholder)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the unified runtime performance scorecard.")
    parser.add_argument("--write", action="store_true", help="Write JSON scorecard.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown sidecar.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero if hard runtime checks are blocked.")
    parser.add_argument("--quick", action="store_true", help="Fast artifact-only refresh; does not rerun long command timings.")
    parser.add_argument("--artifact-only", action="store_true", help="Refresh the scorecard from current proof artifacts without rerunning long command timings.")
    parser.add_argument("--timed-quick", action="store_true", help="Run timed command checks while skipping slower Node/TypeScript cockpit validation.")
    parser.add_argument("--sql-iterations", type=int, default=20, help="Warm iterations for SQL latency benchmark.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--history-out", type=Path, default=HISTORY)
    parser.add_argument("--print-json", action="store_true", help="Print the full JSON scorecard to stdout. Default output is a compact summary.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout unless validation fails through the process exit code.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.json_out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
    args.md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    args.history_out = args.history_out if args.history_out.is_absolute() else ROOT / args.history_out
    if args.quick:
        args.artifact_only = True
    if args.timed_quick:
        args.quick = True
        args.artifact_only = False
    if args.write:
        write_bootstrap_placeholder(args.json_out)
    scorecard = build_scorecard(args)
    if args.write:
        atomic_write_json(args.json_out, scorecard)
        append_history(args.history_out, scorecard)
    if args.write_md:
        atomic_write_text(args.md_out, render_markdown(scorecard))
    if args.print_json:
        print(json.dumps(scorecard, indent=2, sort_keys=True))
    elif not args.quiet:
        print(render_summary(scorecard))
    if args.validate and scorecard.get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
