#!/usr/bin/env python3
"""Compare Python finance-universe validation and Go durable-output probe.

Report-only migration proof. Python remains the durable universe generator until
semantic/shape parity, repeated history, and downstream consumers stay green.
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
DEFAULT_JSON = TMP / "python-go-finance-universe-validation-parity.json"
PYTHON_REPORT = TMP / "wf78-finance-universe-validation.json"
GO_REPORT = TMP / "go-finance-universe-validation-probe.json"
SCHEMA = "veritas.python_go_finance_universe_validation_parity.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def compare(python_report: dict[str, Any], go_report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    py_summary = as_dict(python_report.get("summary"))
    go_semantic = as_dict(go_report.get("semantic_summary"))
    go_shape = as_dict(go_report.get("source_shape"))
    for key in (
        "checks",
        "failed",
        "active_ticker_count",
        "production_active_ticker_count",
        "pilot_fixture_count",
        "review_100_monitor_count",
    ):
        go_key = f"validation_{key}" if key in {"checks", "failed"} else key
        add(f"summary_{key}_match", py_summary.get(key) == go_semantic.get(go_key), "critical", {"python": py_summary.get(key), "go": go_semantic.get(go_key)})
    add("go_probe_ok", go_report.get("status") == "ok", "critical", go_report.get("validation"))
    add("source_status_ok", python_report.get("status") == "ok" and go_shape.get("status") == "ok", "critical", {"python": python_report.get("status"), "go_shape": go_shape.get("status")})
    add("top_level_keys_match", sorted(python_report.keys()) == go_shape.get("top_level_keys"), "critical", {"python": sorted(python_report.keys()), "go": go_shape.get("top_level_keys")})
    add("summary_keys_match", sorted(py_summary.keys()) == go_shape.get("summary_keys"), "critical", {"python": sorted(py_summary.keys()), "go": go_shape.get("summary_keys")})
    add("authority_keys_match", sorted(as_dict(python_report.get("authority_boundary")).keys()) == go_shape.get("authority_keys"), "critical", {"python": sorted(as_dict(python_report.get("authority_boundary")).keys()), "go": go_shape.get("authority_keys")})
    add("semantic_counts_match_universe_state", go_semantic.get("active_ticker_count") == go_semantic.get("universe_active_ticker_count") and go_semantic.get("production_active_ticker_count") == go_semantic.get("universe_production_count") and go_semantic.get("review_100_monitor_count") == go_semantic.get("universe_review_100_count"), "critical", go_semantic)
    add("source_open_all_entries", go_semantic.get("source_open_missing") == 0, "critical", go_semantic.get("source_open_missing"))
    add("no_forbidden_authority_true_values", not go_semantic.get("forbidden_authority_true_values"), "critical", go_semantic.get("forbidden_authority_true_values"))
    boundary = as_dict(go_report.get("authority_boundary"))
    for key in (
        "sql_write_or_import_allowed",
        "db_mutation",
        "canon_or_portfolio_mutation",
        "customer_or_external_delivery",
        "paper_or_live_execution",
        "owner_approval_inferred",
        "config_auth_runtime_mutation",
    ):
        add(f"go_boundary_false_{key}", boundary.get(key) is False, "critical", {key: boundary.get(key)})
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
            "python_report": {"path": rel(args.python_report), "status": python_report.get("status")},
            "go_report": {"path": rel(args.go_report), "status": go_report.get("status")},
        },
        "summary": {"checks": len(findings), "critical": len(critical), "warnings": len(warnings), "missing_artifacts": missing},
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "canon_or_portfolio_mutation": False,
            "paper_or_live_execution_authority": False,
            "brokerage_or_account_action": False,
            "owner_approval_inferred": False,
            "customer_or_external_delivery": False,
            "config_auth_runtime_mutation": False,
            "durable_python_generator_retired": False,
        },
        "validation": {
            "status": "ok" if not missing and not critical else "error",
            "errors": missing + [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Python finance universe validation and Go probe reports.")
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
