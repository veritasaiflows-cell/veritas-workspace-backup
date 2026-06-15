#!/usr/bin/env python3
"""Controlled router proof for SQL consumer authority guard demotion.

This is the first explicit route switch for the Go-covered consumer authority
helper. The default mode remains Python-owned. The Go-first mode is available
only inside this report-only proof surface and always retains Python fallback.

No production dashboard routing is changed, no Python helper is retired, and no
SQL/canon/portfolio/customer/runtime/paper/live/account authority is widened.
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
DEFAULT_JSON = TMP / "python-go-sql-consumer-authority-controlled-router.json"
SCHEMA = "veritas.python_go_sql_consumer_authority_controlled_router.v1"

PYTHON_OWNER_ONLY = "python_owner_only"
GO_FIRST_WITH_PYTHON_FALLBACK = "go_first_with_python_fallback"
ROUTE_MODES = (PYTHON_OWNER_ONLY, GO_FIRST_WITH_PYTHON_FALLBACK)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def approved_key_count() -> int:
    return len(active_sql_canon_approved_keys())


def case_inputs() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    return {
        "clean_fixture": dashboard_fixture_case("clean_fixture"),
        "missing_fallback": dashboard_fixture_case("missing_fallback"),
        "stale_unsafe_source": dashboard_fixture_case("stale_unsafe_source"),
        "live_a2_fallback": live_case(),
    }


def route_decision(mode: str, case_name: str, dashboard_report: dict[str, Any], go_report: dict[str, Any]) -> dict[str, Any]:
    python_guard = as_dict(dashboard_report.get("authorityGuard"))
    go_allows = go_report.get("status") == "ok" and go_report.get("sql_read_allowed") is True
    python_allows = python_guard.get("status") == "ok" and python_guard.get("sql_read_allowed") is True
    dashboard_allows = dashboard_report.get("status") == "ok" and dashboard_report.get("sqlReadAllowed") is True

    if mode == PYTHON_OWNER_ONLY:
        selected_route = "python_owner_read_allowed" if python_allows else "python_owner_blocked"
        fallback_exercised = False
        primary_runtime = "python"
    elif mode == GO_FIRST_WITH_PYTHON_FALLBACK:
        if go_allows:
            selected_route = "go_primary_read_allowed"
            fallback_exercised = False
            primary_runtime = "go"
        else:
            selected_route = "python_fallback_read_allowed" if python_allows else "python_fallback_blocked"
            fallback_exercised = True
            primary_runtime = "python"
    else:
        raise ValueError(f"unsupported route mode: {mode}")

    return {
        "mode": mode,
        "case": case_name,
        "selected_route": selected_route,
        "primary_runtime": primary_runtime,
        "fallback_exercised": fallback_exercised,
        "go_status": go_report.get("status"),
        "go_sql_read_allowed": go_report.get("sql_read_allowed"),
        "python_status": python_guard.get("status"),
        "python_sql_read_allowed": python_guard.get("sql_read_allowed"),
        "dashboard_status": dashboard_report.get("status"),
        "dashboard_sql_read_allowed": dashboard_report.get("sqlReadAllowed"),
        "dashboard_rows": len(as_dict(dashboard_report.get("rows"))),
        "route_consistent": go_allows == python_allows == dashboard_allows,
    }


def cycle_decisions(cycle: int) -> list[dict[str, Any]]:
    inputs = case_inputs()
    return [
        {"cycle": cycle, **route_decision(mode, case_name, dashboard_report, go_report)}
        for mode in ROUTE_MODES
        for case_name, (dashboard_report, go_report) in inputs.items()
    ]


def stable_route_fingerprints(cycles: list[list[dict[str, Any]]]) -> bool:
    if not cycles:
        return False

    def normalized(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{key: value for key, value in row.items() if key != "cycle"} for row in rows]

    first = normalized(cycles[0])
    return all(normalized(cycle) == first for cycle in cycles)


def build_report(cycles_requested: int) -> dict[str, Any]:
    if shutil.which("go") is None:
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "summary": {"checks": 0, "critical": 1, "warnings": 0, "missing_tools": ["go"]},
            "validation": {"status": "error", "errors": ["missing_tool:go"], "warnings": []},
        }

    cycles_requested = max(1, cycles_requested)
    cycle_rows = [cycle_decisions(cycle) for cycle in range(1, cycles_requested + 1)]
    decisions = [row for rows in cycle_rows for row in rows]
    by_key = {(row["mode"], row["case"]): row for row in decisions}
    findings: list[dict[str, Any]] = []

    clean_default = by_key[(PYTHON_OWNER_ONLY, "clean_fixture")]
    clean_controlled = by_key[(GO_FIRST_WITH_PYTHON_FALLBACK, "clean_fixture")]
    add(findings, "default_mode_remains_python_owned", clean_default["selected_route"] == "python_owner_read_allowed", "critical", clean_default)
    add(findings, "controlled_mode_selects_go_for_clean_fixture", clean_controlled["selected_route"] == "go_primary_read_allowed", "critical", clean_controlled)
    add(findings, "controlled_mode_clean_fixture_no_fallback", clean_controlled["fallback_exercised"] is False, "critical", clean_controlled)

    live_default = by_key[(PYTHON_OWNER_ONLY, "live_a2_fallback")]
    live_controlled = by_key[(GO_FIRST_WITH_PYTHON_FALLBACK, "live_a2_fallback")]
    add(findings, "default_mode_live_a2_fallback_python_owned", live_default["selected_route"] == "python_owner_read_allowed", "critical", live_default)
    add(findings, "controlled_mode_live_a2_fallback_selects_go", live_controlled["selected_route"] == "go_primary_read_allowed", "critical", live_controlled)
    add(findings, "controlled_mode_live_a2_fallback_no_fallback", live_controlled["fallback_exercised"] is False, "critical", live_controlled)

    blocked_cases = ("missing_fallback", "stale_unsafe_source")
    for case_name in blocked_cases:
        default_row = by_key[(PYTHON_OWNER_ONLY, case_name)]
        controlled_row = by_key[(GO_FIRST_WITH_PYTHON_FALLBACK, case_name)]
        add(findings, f"default_mode_{case_name}_blocked", default_row["selected_route"] == "python_owner_blocked", "critical", default_row)
        add(findings, f"controlled_mode_{case_name}_uses_python_fallback", controlled_row["fallback_exercised"] is True, "critical", controlled_row)
        add(findings, f"controlled_mode_{case_name}_fallback_blocked", controlled_row["selected_route"] == "python_fallback_blocked", "critical", controlled_row)

    expected_clean_rows = approved_key_count()
    for row in decisions:
        expected_rows = expected_clean_rows if row["case"] in {"clean_fixture", "live_a2_fallback"} else 0
        add(findings, f"cycle_{row['cycle']}:{row['mode']}:{row['case']}:route_consistent", row["route_consistent"] is True, "critical", row)
        add(findings, f"cycle_{row['cycle']}:{row['mode']}:{row['case']}:dashboard_rows_expected", row["dashboard_rows"] == expected_rows, "critical", row)
    stable = stable_route_fingerprints(cycle_rows)
    add(findings, "controlled_router_route_fingerprints_stable", stable, "critical", {"cycles": cycles_requested})

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
        "route_contract": {
            "default_mode": PYTHON_OWNER_ONLY,
            "available_controlled_mode": GO_FIRST_WITH_PYTHON_FALLBACK,
            "production_routing_changed": False,
            "python_fallback_retained": True,
            "retire_python_now": False,
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cases_per_cycle": 4,
            "route_modes": len(ROUTE_MODES),
            "cycles": cycles_requested,
            "route_fingerprints_stable": stable,
            "go_primary_allowed_cases": sum(1 for row in decisions if row["selected_route"] == "go_primary_read_allowed"),
            "python_fallback_cases": sum(1 for row in decisions if row["fallback_exercised"]),
            "default_python_owned_cases": sum(1 for row in decisions if row["mode"] == PYTHON_OWNER_ONLY),
            "controlled_router_signal": "go_first_switch_ready_for_controlled_ab_only" if not critical else "not_ready",
        },
        "route_decisions": decisions,
        "cycles": [
            {
                "cycle": index + 1,
                "route_decisions": rows,
            }
            for index, rows in enumerate(cycle_rows)
        ],
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "dry_run_only": True,
            "production_routing_changed": False,
            "demotes_python": False,
            "python_fallback_retained": True,
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
            "errors": [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prove controlled Go-first/Python-fallback router behavior.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--cycles", type=int, default=3, help="Number of repeated controlled-router cycles to run.")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    report = build_report(args.cycles)
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
