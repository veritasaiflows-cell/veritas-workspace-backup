#!/usr/bin/env python3
"""Check Python-vs-Go SQL helper parity from existing proof artifacts.

This is a report-only migration gate. It compares correctness surfaces between
the Python SQL latency benchmark and the Go SQL latency/inventory helpers before
any Python SQL helper is retired, demoted, or replaced.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-parity-check.json"
SCHEMA = "veritas.python_go_sql_parity_check.v1"


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


def finding(severity: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    row.update(extra)
    return row


def benchmark_key(row: dict[str, Any]) -> str:
    return f"{row.get('database')}::{row.get('label')}"


def load_artifact(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def check_boundary(name: str, payload: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    boundary = as_dict(payload.get("authority_boundary"))
    if not boundary:
        findings.append(finding("critical", "missing_authority_boundary", f"{name} has no authority_boundary object"))
        return
    required_false_keys = {
        "db_mutation",
        "sql_write_or_import_allowed",
        "canon_or_portfolio_mutation",
        "canon_or_portfolio_mutation_allowed",
        "customer_or_external_delivery",
        "paper_or_live_execution_authority",
        "paper_or_live_execution_allowed",
        "brokerage_or_execution_authority",
        "owner_approval_inferred",
        "config_auth_runtime_mutation",
    }
    if boundary.get("read_only") is False or boundary.get("report_only") is False:
        findings.append(finding("critical", "not_report_or_read_only", f"{name} boundary is not read-only/report-only"))
    for key in sorted(required_false_keys):
        if key in boundary and boundary.get(key) not in (False, 0, None):
            findings.append(finding("critical", "authority_widened", f"{name} authority boundary widened: {key}", key=key, value=boundary.get(key)))


def compare_latency(python_latency: dict[str, Any], go_latency: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    py_results = [row for row in as_list(python_latency.get("results")) if isinstance(row, dict)]
    go_results = [row for row in as_list(go_latency.get("results")) if isinstance(row, dict)]
    py_by_key = {benchmark_key(row): row for row in py_results}
    go_by_key = {benchmark_key(row): row for row in go_results}

    missing_in_go = sorted(set(py_by_key) - set(go_by_key))
    extra_in_go = sorted(set(go_by_key) - set(py_by_key))
    for key in missing_in_go:
        findings.append(finding("critical", "go_missing_python_benchmark", "Go latency probe is missing a Python benchmark", benchmark=key))
    for key in extra_in_go:
        findings.append(finding("warning", "go_extra_benchmark", "Go latency probe has a benchmark not present in Python", benchmark=key))

    status_mismatches = 0
    row_mismatches = 0
    checked_pairs = 0
    for key in sorted(set(py_by_key) & set(go_by_key)):
        py_row = py_by_key[key]
        go_row = go_by_key[key]
        checked_pairs += 1
        py_status = str(py_row.get("status") or "")
        go_status = str(go_row.get("status") or "")
        if py_status == "ok" and go_status != "ok":
            status_mismatches += 1
            findings.append(
                finding(
                    "critical",
                    "go_failed_python_ok_benchmark",
                    "Python benchmark succeeded but Go benchmark did not",
                    benchmark=key,
                    python_status=py_status,
                    go_status=go_status,
                    go_error=go_row.get("error"),
                )
            )
        if py_row.get("rows") != go_row.get("rows"):
            row_mismatches += 1
            findings.append(
                finding(
                    "critical",
                    "row_count_mismatch",
                    "Python and Go benchmark row counts differ",
                    benchmark=key,
                    python_rows=py_row.get("rows"),
                    go_rows=go_row.get("rows"),
                )
            )

    summary = {
        "python_benchmarks": len(py_results),
        "go_benchmarks": len(go_results),
        "checked_pairs": checked_pairs,
        "missing_in_go": len(missing_in_go),
        "extra_in_go": len(extra_in_go),
        "status_mismatches": status_mismatches,
        "row_count_mismatches": row_mismatches,
        "timing_compared_for_status": False,
        "timing_note": "Timing values are informational only because the current Go probe shells out to sqlite3 and includes process startup overhead.",
    }
    return summary, findings


def check_inventory(go_inventory: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    summary = as_dict(go_inventory.get("summary"))
    blocked = int(summary.get("blocked_dbs") or 0)
    warnings = int(summary.get("warning_dbs") or 0)
    missing_tables = int(summary.get("missing_tables") or 0)
    row_count_errors = int(summary.get("row_count_errors") or 0)
    if go_inventory.get("status") != "ok":
        findings.append(finding("critical", "go_inventory_not_ok", "Go SQL inventory helper is not ok", status=go_inventory.get("status")))
    for code, count in {
        "go_inventory_blocked_dbs": blocked,
        "go_inventory_warning_dbs": warnings,
        "go_inventory_missing_tables": missing_tables,
        "go_inventory_row_count_errors": row_count_errors,
    }.items():
        if count:
            findings.append(finding("critical", code, f"Go inventory helper reported {count}", count=count))
    return {
        "status": go_inventory.get("status"),
        "databases": summary.get("databases"),
        "present": summary.get("present"),
        "tables": summary.get("tables"),
        "views": summary.get("views"),
        "total_rows": summary.get("total_rows"),
        "blocked_dbs": blocked,
        "warning_dbs": warnings,
        "missing_tables": missing_tables,
        "row_count_errors": row_count_errors,
    }, findings


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    python_latency = load_artifact(args.python_latency)
    go_latency = load_artifact(args.go_latency)
    go_inventory = load_artifact(args.go_inventory)
    findings: list[dict[str, Any]] = []

    sources = {
        "python_latency": {"path": rel(args.python_latency), "exists": args.python_latency.exists(), "status": python_latency.get("status")},
        "go_latency": {"path": rel(args.go_latency), "exists": args.go_latency.exists(), "status": go_latency.get("status")},
        "go_inventory": {"path": rel(args.go_inventory), "exists": args.go_inventory.exists(), "status": go_inventory.get("status")},
    }
    for name, row in sources.items():
        if not row["exists"]:
            findings.append(finding("critical", "missing_source_artifact", f"{name} source artifact is missing", path=row["path"]))

    if python_latency:
        check_boundary("python_latency", python_latency, findings)
    if go_latency:
        check_boundary("go_latency", go_latency, findings)
    if go_inventory:
        check_boundary("go_inventory", go_inventory, findings)

    latency_summary, latency_findings = compare_latency(python_latency, go_latency)
    inventory_summary, inventory_findings = check_inventory(go_inventory)
    findings.extend(latency_findings)
    findings.extend(inventory_findings)

    critical = sum(1 for row in findings if row.get("severity") == "critical")
    warnings = sum(1 for row in findings if row.get("severity") == "warning")
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "summary": {
            "checks": 3,
            "critical": critical,
            "warnings": warnings,
            "latency_pairs": latency_summary.get("checked_pairs"),
            "row_count_mismatches": latency_summary.get("row_count_mismatches"),
            "status_mismatches": latency_summary.get("status_mismatches"),
            "inventory_blocked_dbs": inventory_summary.get("blocked_dbs"),
        },
        "source_artifacts": sources,
        "latency_parity": latency_summary,
        "inventory_parity": inventory_summary,
        "findings": findings,
        "migration_posture": {
            "selected_python_sql_helpers_may_be_demoted_after_repeated_clean_parity": status == "ok",
            "python_remains_workflow_generator": True,
            "go_remains_read_only_sql_proof_edge": True,
            "timing_values_are_not_replacement_proof": True,
        },
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "db_mutation": False,
            "sql_write_or_import_allowed": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution_authority": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Python-vs-Go SQL helper parity.")
    parser.add_argument("--write", action="store_true", help="Write JSON report.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero when parity is blocked.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--python-latency", type=Path, default=TMP / "sql-latency-benchmark-current.json")
    parser.add_argument("--go-latency", type=Path, default=TMP / "go-sql-latency-probe.json")
    parser.add_argument("--go-inventory", type=Path, default=TMP / "go-sql-inventory-helper.json")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve_path(args.json_out)
    args.python_latency = resolve_path(args.python_latency)
    args.go_latency = resolve_path(args.go_latency)
    args.go_inventory = resolve_path(args.go_inventory)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report.get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
