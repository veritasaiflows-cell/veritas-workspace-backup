#!/usr/bin/env python3
"""Compare Python and Go SQL consumer authority guard outputs.

Report-only migration proof. It does not mutate SQL, canon, portfolio,
dashboard behavior, customer state, runtime config, paper/live/account state,
or owner approval state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from sql_consumer_authority_guard import build_phase4a_sql_consumer_authority_guard

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-consumer-authority-guard-parity.json"
GO_REPORT = TMP / "go-sql-consumer-authority-guard.json"
DEFAULT_FALLBACK = TMP / "wf72-a2-consumer-authority-fallback-values.json"
SCHEMA = "veritas.python_go_sql_consumer_authority_guard_parity.v1"


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


def fallback_values(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def check_map(report: dict[str, Any]) -> dict[str, bool]:
    return {str(row.get("name")): bool(row.get("ok")) for row in as_list(report.get("checks")) if isinstance(row, dict)}


def _expected_go_status(python_status: Any) -> str:
    return "ok" if python_status == "ok" else "fail_closed"


def compare(python_report: dict[str, Any], go_report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    py_summary = {
        "approved_keys": len(as_list(python_report.get("approved_keys"))),
        "active_entry_stop_reference_keys": len(as_list(python_report.get("active_entry_stop_reference_keys"))),
        "cache_rows": len(as_list(python_report.get("cache_rows"))),
        "extra_keys": len(set(f"{row.get('scope')}:{row.get('field_name')}" for row in as_list(python_report.get("cache_rows"))) - set(as_list(python_report.get("approved_keys")))),
        "missing_keys": len(set(as_list(python_report.get("approved_keys"))) - set(f"{row.get('scope')}:{row.get('field_name')}" for row in as_list(python_report.get("cache_rows")))),
        "fallback_missing_keys": len(as_list(python_report.get("fallback_missing_keys"))),
        "forbidden_true_rows": len(as_list(python_report.get("forbidden_true_rows"))),
        "cache_forbidden_rows": len(as_list(python_report.get("cache_forbidden_rows"))),
        "cache_stale_or_unsafe_rows": len(as_list(python_report.get("cache_stale_or_unsafe_rows"))),
        "canon_stage_apply_allowed_true_count": python_report.get("canon_stage_apply_allowed_true_count"),
        "canon_stage_incomplete_review_only_rows": python_report.get("canon_stage_incomplete_review_only_rows"),
    }
    go_summary = as_dict(go_report.get("summary"))
    python_status = python_report.get("status")
    python_read_allowed = python_report.get("sql_read_allowed")
    expected_read_allowed = python_status == "ok"
    expected_go_status = _expected_go_status(python_status)
    add(
        "python_expected_fallback_posture",
        python_status in {"ok", "blocked"} and python_read_allowed is expected_read_allowed,
        "critical",
        {"status": python_status, "sql_read_allowed": python_read_allowed, "expected_read_allowed": expected_read_allowed},
    )
    add(
        "go_expected_fallback_posture",
        go_report.get("status") == expected_go_status and go_report.get("sql_read_allowed") is expected_read_allowed,
        "critical",
        {"status": go_report.get("status"), "sql_read_allowed": go_report.get("sql_read_allowed"), "expected": expected_go_status, "expected_read_allowed": expected_read_allowed},
    )
    if expected_read_allowed is False and go_report.get("status") == "fail_closed" and go_report.get("sql_read_allowed") is False:
        add(
            "live_a2_expected_fail_closed_posture",
            False,
            "warning",
            {
                "python_status": python_status,
                "go_status": go_report.get("status"),
                "sql_read_allowed": False,
                "cache_stale_or_unsafe_rows": go_summary.get("cache_stale_or_unsafe_rows"),
                "meaning": "live A2 SQL consumer guard refused an unsafe read; this is readiness debt, not authority widening",
            },
        )
    for key in (
        "approved_keys",
        "active_entry_stop_reference_keys",
        "cache_rows",
        "extra_keys",
        "missing_keys",
        "fallback_missing_keys",
        "forbidden_true_rows",
        "cache_forbidden_rows",
        "cache_stale_or_unsafe_rows",
        "canon_stage_apply_allowed_true_count",
        "canon_stage_incomplete_review_only_rows",
    ):
        add(f"summary_{key}_match", py_summary.get(key) == go_summary.get(key), "critical", {"python": py_summary.get(key), "go": go_summary.get(key)})
    py_checks = check_map(python_report)
    go_checks = check_map(go_report)
    for name in (
        "forbidden_authority_flags_false",
        "canon_stage_apply_not_allowed",
        "higher_risk_family_gates_no_activation",
        "canon_cache_integrity_ok",
        "sql_canon_boundary_active",
        "sql_canon_authority_true",
        "consumer_scope_dashboard_proof_metadata_only",
        "fallback_required_meta_true",
        "exact_approved_keys_only",
        "row_boundaries_and_field_families_allowed",
        "fallback_values_present",
        "cache_source_freshness_safe",
    ):
        add(f"check_{name}_match", py_checks.get(name) == go_checks.get(name), "critical", {"python": py_checks.get(name), "go": go_checks.get(name)})
    boundary = as_dict(go_report.get("authority_boundary"))
    for key in (
        "sql_write_or_import_allowed",
        "db_mutation",
        "canon_or_portfolio_mutation",
        "customer_or_external_delivery",
        "paper_or_live_execution",
        "owner_approval_inferred",
        "config_auth_runtime_mutation",
        "trade_or_account_action_allowed",
        "money_movement_allowed",
        "dashboard_behavior_change_allowed",
        "canonical_note_mutation_allowed",
    ):
        add(f"go_boundary_false_{key}", boundary.get(key) is False, "critical", {key: boundary.get(key)})
    add("go_boundary_report_read_only", boundary.get("report_only") is True and boundary.get("read_only") is True, "critical", boundary)
    return findings


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    fallback = fallback_values(args.fallback_json)
    python_report = build_phase4a_sql_consumer_authority_guard(fallback_values_by_key=fallback)
    go_report = load(args.go_report)
    missing = [] if go_report else [rel(args.go_report)]
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
            "python_report": {"status": python_report.get("status"), "sql_read_allowed": python_report.get("sql_read_allowed")},
            "go_report": {"path": rel(args.go_report), "status": go_report.get("status"), "sql_read_allowed": go_report.get("sql_read_allowed")},
            "fallback_json": {"path": rel(args.fallback_json), "exists": bool(fallback), "key_count": len(fallback)},
        },
        "summary": {"checks": len(findings), "critical": len(critical), "warnings": len(warnings), "missing_artifacts": missing},
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "sql_write_or_import_allowed": False,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution": False,
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
    parser = argparse.ArgumentParser(description="Compare Python and Go SQL consumer authority guard reports.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--go-report", type=Path, default=GO_REPORT)
    parser.add_argument("--fallback-json", type=Path, default=DEFAULT_FALLBACK)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve(args.json_out)
    args.go_report = resolve(args.go_report)
    args.fallback_json = resolve(args.fallback_json)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
