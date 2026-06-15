#!/usr/bin/env python3
"""Go-first/Python-fallback dry-run for SQL consumer authority guard.

This is a controlled routing simulation only. It proves the first demotion
candidate can be evaluated Go-first while Python remains available as fallback.
It does not change dashboard routing, retire Python, mutate SQL/canon/
portfolio/customer/runtime state, or infer approval.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json
from python_go_sql_consumer_authority_dashboard_ab import dashboard_fixture_case, live_case
from sql_consumer_authority_guard import active_sql_canon_approved_keys

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-consumer-authority-demotion-dry-run.json"
SCHEMA = "veritas.python_go_sql_consumer_authority_demotion_dry_run.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def approved_key_count() -> int:
    return len(active_sql_canon_approved_keys())


def route_case(case_name: str, dashboard_report: dict[str, Any], go_report: dict[str, Any]) -> dict[str, Any]:
    python_guard = as_dict(dashboard_report.get("authorityGuard"))
    go_allows = go_report.get("status") == "ok" and go_report.get("sql_read_allowed") is True
    python_allows = python_guard.get("status") == "ok" and python_guard.get("sql_read_allowed") is True
    dashboard_allows = dashboard_report.get("status") == "ok" and dashboard_report.get("sqlReadAllowed") is True
    if go_allows:
        selected = "go_primary_read_allowed"
        fallback = False
    else:
        selected = "python_fallback_blocked" if not python_allows else "python_fallback_read_allowed"
        fallback = True
    return {
        "case": case_name,
        "selected_route": selected,
        "fallback_exercised": fallback,
        "go_status": go_report.get("status"),
        "go_sql_read_allowed": go_report.get("sql_read_allowed"),
        "python_status": python_guard.get("status"),
        "python_sql_read_allowed": python_guard.get("sql_read_allowed"),
        "dashboard_status": dashboard_report.get("status"),
        "dashboard_sql_read_allowed": dashboard_report.get("sqlReadAllowed"),
        "dashboard_rows": len(as_dict(dashboard_report.get("rows"))),
        "route_consistent": go_allows == python_allows == dashboard_allows,
    }


def build_report() -> dict[str, Any]:
    if shutil.which("go") is None:
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "summary": {"checks": 0, "critical": 1, "warnings": 0, "missing_tools": ["go"]},
            "validation": {"status": "error", "errors": ["missing_tool:go"], "warnings": []},
        }
    cases = {
        "clean_fixture": dashboard_fixture_case("clean_fixture"),
        "missing_fallback": dashboard_fixture_case("missing_fallback"),
        "stale_unsafe_source": dashboard_fixture_case("stale_unsafe_source"),
        "live_a2_fallback": live_case(),
    }
    route_decisions = [route_case(name, dashboard, go) for name, (dashboard, go) in cases.items()]
    findings: list[dict[str, Any]] = []
    expected_clean_rows = approved_key_count()
    clean = next(row for row in route_decisions if row["case"] == "clean_fixture")
    add(findings, "clean_fixture_go_primary_selected", clean["selected_route"] == "go_primary_read_allowed", "critical", clean)
    add(findings, "clean_fixture_no_fallback_needed", clean["fallback_exercised"] is False, "critical", clean)
    for row in route_decisions:
        add(findings, f"{row['case']}_route_consistent", row["route_consistent"] is True, "critical", row)
        expected_rows = expected_clean_rows if row["case"] in {"clean_fixture", "live_a2_fallback"} else 0
        add(findings, f"{row['case']}_dashboard_rows_expected", row["dashboard_rows"] == expected_rows, "critical", row)
    live = next(row for row in route_decisions if row["case"] == "live_a2_fallback")
    add(findings, "live_a2_fallback_go_primary_selected", live["selected_route"] == "go_primary_read_allowed", "critical", live)
    add(findings, "live_a2_fallback_no_fallback_needed", live["fallback_exercised"] is False, "critical", live)
    for blocked_case in ("missing_fallback", "stale_unsafe_source"):
        row = next(item for item in route_decisions if item["case"] == blocked_case)
        add(findings, f"{blocked_case}_python_fallback_exercised", row["fallback_exercised"] is True, "critical", row)
        add(findings, f"{blocked_case}_fallback_remains_blocked", row["selected_route"] == "python_fallback_blocked", "critical", row)
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "dashboard_ab_gate": "scripts/python_go_sql_consumer_authority_dashboard_ab.py",
            "python_owner": "scripts/sql_consumer_authority_guard.py",
            "go_companion": "scripts/go/cmd/go-sql-consumer-authority-guard",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cases": len(route_decisions),
            "go_primary_allowed_cases": sum(1 for row in route_decisions if row["selected_route"] == "go_primary_read_allowed"),
            "python_fallback_cases": sum(1 for row in route_decisions if row["fallback_exercised"]),
            "dry_run_signal": "go_first_python_fallback_ready_for_controlled_ab" if not critical else "not_ready",
        },
        "route_decisions": route_decisions,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "dry_run_only": True,
            "production_routing_changed": False,
            "demotes_python": False,
            "python_fallback_retained": True,
            "live_sql_write_or_import_allowed": False,
            "db_mutation": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Go-first/Python-fallback dry-run for SQL consumer authority guard.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
