#!/usr/bin/env python3
"""Compare Python and Go source-truth parity validator outputs.

This is a report-only migration gate. It does not promote SQL to source of
truth, mutate SQL or Markdown, change consumers, infer approval, or grant
portfolio/customer/execution authority.
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
DEFAULT_JSON = TMP / "python-go-source-truth-parity-validator-parity.json"
PYTHON_REPORT = TMP / "sql-source-truth-parity-validation.json"
GO_REPORT = TMP / "go-source-truth-parity-validation.json"
SCHEMA = "veritas.python_go_source_truth_parity_validator_parity.v1"

FALSE_FLAGS = {
    "source_of_truth_promotion_allowed_by_this_artifact",
    "sql_first_consumer_migration_allowed",
    "sql_writes_allowed",
    "markdown_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "recommendation_or_deployment_authority_allowed",
    "paper_or_live_execution_allowed",
    "customer_or_external_delivery_allowed",
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def false_flags(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in sorted(FALSE_FLAGS)}


def ticker_set(payload: dict[str, Any], key: str) -> list[str]:
    return sorted(str(value) for value in as_list(payload.get(key)))


def mismatches(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(row.get("ticker")): row.get("mismatches") for row in as_list(payload.get("mismatches")) if isinstance(row, dict)}


def comparison_checks(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        str(row.get("ticker")): as_dict(row.get("checks"))
        for row in as_list(payload.get("comparisons"))
        if isinstance(row, dict) and row.get("ticker")
    }


def source_hash(payload: dict[str, Any]) -> Any:
    return as_dict(payload.get("source_note")).get("sha256")


def compare(python_report: dict[str, Any], go_report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    py_summary = as_dict(python_report.get("summary"))
    go_summary = as_dict(go_report.get("summary"))
    add("status_equivalent", python_report.get("status") == go_report.get("status"), "critical", {"python": python_report.get("status"), "go": go_report.get("status")})
    add("summary_match", py_summary == go_summary, "critical", {"python": py_summary, "go": go_summary})
    add("source_note_hash_match", source_hash(python_report) == source_hash(go_report), "critical", {"python": source_hash(python_report), "go": source_hash(go_report)})
    add("false_authority_flags_match", false_flags(python_report) == false_flags(go_report), "critical", {"python": false_flags(python_report), "go": false_flags(go_report)})
    add("all_authority_flags_false", all(value is False for value in false_flags(go_report).values()), "critical", false_flags(go_report))
    for key in ("missing_finance_tickers", "missing_canon_tickers", "finance_extra_tickers", "canon_extra_tickers"):
        add(f"{key}_match", ticker_set(python_report, key) == ticker_set(go_report, key), "critical", {"python": ticker_set(python_report, key), "go": ticker_set(go_report, key)})
    add("mismatches_match", mismatches(python_report) == mismatches(go_report), "critical", {"python": mismatches(python_report), "go": mismatches(go_report)})
    add("comparison_checks_match", comparison_checks(python_report) == comparison_checks(go_report), "critical", {"python_count": len(comparison_checks(python_report)), "go_count": len(comparison_checks(go_report))})
    add("blocked_observation_count_match", len(as_list(python_report.get("blocked_field_observations"))) == len(as_list(go_report.get("blocked_field_observations"))), "warning", {"python": len(as_list(python_report.get("blocked_field_observations"))), "go": len(as_list(go_report.get("blocked_field_observations")))})
    return findings


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    python_report = load(args.python_report)
    go_report = load(args.go_report)
    missing = []
    if not python_report:
        missing.append(rel(args.python_report))
    if not go_report:
        missing.append(rel(args.go_report))
    findings = compare(python_report, go_report) if not missing else []
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if missing or critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "python_report": {"path": rel(args.python_report), "status": python_report.get("status"), "schema": python_report.get("schema_version")},
            "go_report": {"path": rel(args.go_report), "status": go_report.get("status"), "schema": go_report.get("schema_version")},
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "missing_artifacts": missing,
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "sql_write_or_import_allowed": False,
            "source_of_truth_promotion_allowed": False,
            "consumer_migration_allowed": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution_authority": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
        "validation": {
            "status": "ok" if not missing and not critical else "error",
            "errors": missing + [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Python and Go source-truth parity validator reports.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--python-report", type=Path, default=PYTHON_REPORT)
    parser.add_argument("--go-report", type=Path, default=GO_REPORT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve(args.json_out)
    args.python_report = resolve(args.python_report)
    args.go_report = resolve(args.go_report)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
