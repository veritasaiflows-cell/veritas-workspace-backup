#!/usr/bin/env python3
"""Report-only dashboard A/B gate for Go SQL consumer authority demotion.

This gate compares the dashboard's Python-owned SQL consumer path with the Go
authority guard in two cases:

- live workspace, no fallback values: both must stay fail-closed/read-blocked
- synthetic clean fixture with approved fallback values: both may allow the
  bounded proof-metadata read

It does not change dashboard behavior, demote Python, mutate SQL/canon/
portfolio/customer/runtime state, or infer approval.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import dashboard_payload
from market_data_utils import atomic_write_json, load_json_artifact
from python_go_sql_consumer_authority_guard_fixture_parity import build_fixture, run_go_fixture
from sql_consumer_authority_guard import active_sql_canon_approved_keys, build_phase4a_sql_consumer_authority_guard

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-consumer-authority-dashboard-ab.json"
LIVE_GO_REPORT = TMP / "go-sql-consumer-authority-guard.json"
LIVE_A2_FALLBACK_VALUES = TMP / "wf72-a2-consumer-authority-fallback-values.json"
SCHEMA = "veritas.python_go_sql_consumer_authority_dashboard_ab.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def boundary_false(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is False


def add_finding(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def write_fallback(path: Path, values: dict[str, Any]) -> None:
    path.write_text(json.dumps(values, indent=2, sort_keys=True), encoding="utf-8")


def approved_key_count() -> int:
    return len(active_sql_canon_approved_keys())


def mutate_stale_cache_row(cache_db: Path) -> None:
    conn = sqlite3.connect(cache_db)
    try:
        conn.execute(
            """
            UPDATE canon_cache_fields
            SET freshness_status = 'stale'
            WHERE scope = 'deployment'
              AND field_name = 'source_freshness_classification'
            """
        )
        conn.commit()
    finally:
        conn.close()


def dashboard_fixture_case(case_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="veritas-dashboard-go-ab-", ignore_cleanup_errors=True) as temp_name:
        fixture_root = Path(temp_name)
        artifact_db, cache_db, fallback_path, fallback = build_fixture(fixture_root)
        if case_name == "missing_fallback":
            fallback.pop("deployment:source_freshness_classification", None)
            write_fallback(fallback_path, fallback)
        elif case_name == "stale_unsafe_source":
            mutate_stale_cache_row(cache_db)
        original_guard: Callable[..., dict[str, Any]] = dashboard_payload.build_phase4a_sql_consumer_authority_guard

        def fixture_guard(fallback_values_by_key: dict[str, Any] | None = None) -> dict[str, Any]:
            return build_phase4a_sql_consumer_authority_guard(
                workspace=fixture_root,
                artifact_index_db=artifact_db,
                canon_cache_db=cache_db,
                fallback_values_by_key=fallback_values_by_key if fallback_values_by_key is not None else fallback,
            )

        dashboard_payload.build_phase4a_sql_consumer_authority_guard = fixture_guard
        try:
            dashboard_report = dashboard_payload._load_phase4a_sql_canon_metadata(fallback)
        finally:
            dashboard_payload.build_phase4a_sql_consumer_authority_guard = original_guard
        go_report = run_go_fixture(fixture_root, fallback_path)
    return dashboard_report, go_report


def live_case() -> tuple[dict[str, Any], dict[str, Any]]:
    fallback = load_json_artifact(LIVE_A2_FALLBACK_VALUES)
    fallback = fallback if isinstance(fallback, dict) else {}
    dashboard_report = dashboard_payload._load_phase4a_sql_canon_metadata(fallback)
    go_report = load_json_artifact(LIVE_GO_REPORT)
    return dashboard_report, go_report if isinstance(go_report, dict) else {"status": "missing_live_go_report"}


def compare_clean_fixture(dashboard_report: dict[str, Any], go_report: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    go_summary = as_dict(go_report.get("summary"))
    rows = as_dict(dashboard_report.get("rows"))
    guard = as_dict(dashboard_report.get("authorityGuard"))
    add_finding(findings, "clean_dashboard_status_ok", dashboard_report.get("status") == "ok", "critical", dashboard_report.get("status"))
    add_finding(findings, "clean_dashboard_sql_read_allowed", dashboard_report.get("sqlReadAllowed") is True, "critical", dashboard_report.get("sqlReadAllowed"))
    add_finding(findings, "clean_dashboard_proof_metadata_only", dashboard_report.get("proofMetadataAuthority") is True and dashboard_report.get("sqlIsCanon") is False, "critical", {"proofMetadataAuthority": dashboard_report.get("proofMetadataAuthority"), "sqlIsCanon": dashboard_report.get("sqlIsCanon")})
    add_finding(findings, "clean_go_status_ok", go_report.get("status") == "ok", "critical", go_report.get("status"))
    add_finding(findings, "clean_go_sql_read_allowed", go_report.get("sql_read_allowed") is True, "critical", go_report.get("sql_read_allowed"))
    approved_keys = approved_key_count()
    add_finding(findings, "clean_dashboard_go_row_count_match", len(rows) == go_summary.get("cache_rows") == approved_keys, "critical", {"dashboard_rows": len(rows), "go_cache_rows": go_summary.get("cache_rows"), "approved_keys": approved_keys})
    add_finding(findings, "clean_dashboard_guard_aligned", guard.get("status") == "ok" and guard.get("sql_read_allowed") is True, "critical", {"status": guard.get("status"), "sql_read_allowed": guard.get("sql_read_allowed")})
    for key in (
        "canonicalNoteMutationAllowed",
        "portfolioMutationAllowed",
        "ownerApprovalInferred",
        "tradeOrAccountActionAllowed",
        "paperTradeAuthorityAllowed",
        "liveTradeAuthorityAllowed",
        "dashboardBehaviorChangeAllowed",
    ):
        add_finding(findings, f"clean_dashboard_boundary_false_{key}", boundary_false(dashboard_report, key), "critical", {key: dashboard_report.get(key)})
    go_boundary = as_dict(go_report.get("authority_boundary"))
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
    ):
        add_finding(findings, f"clean_go_boundary_false_{key}", go_boundary.get(key) is False, "critical", {key: go_boundary.get(key)})


def compare_blocked_fixture(case_name: str, dashboard_report: dict[str, Any], go_report: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    guard = as_dict(dashboard_report.get("authorityGuard"))
    add_finding(findings, f"{case_name}_dashboard_degraded", dashboard_report.get("status") == "degraded_fallback_required", "critical", dashboard_report.get("status"))
    add_finding(findings, f"{case_name}_dashboard_sql_read_blocked", dashboard_report.get("sqlReadAllowed") is False, "critical", dashboard_report.get("sqlReadAllowed"))
    add_finding(findings, f"{case_name}_dashboard_guard_blocked", guard.get("status") == "blocked" and guard.get("sql_read_allowed") is False, "critical", {"status": guard.get("status"), "sql_read_allowed": guard.get("sql_read_allowed")})
    add_finding(findings, f"{case_name}_go_fail_closed", go_report.get("status") == "fail_closed", "critical", go_report.get("status"))
    add_finding(findings, f"{case_name}_go_sql_read_blocked", go_report.get("sql_read_allowed") is False, "critical", go_report.get("sql_read_allowed"))
    add_finding(findings, f"{case_name}_dashboard_rows_empty", len(as_dict(dashboard_report.get("rows"))) == 0, "critical", len(as_dict(dashboard_report.get("rows"))))
    for key in (
        "canonicalNoteMutationAllowed",
        "portfolioMutationAllowed",
        "ownerApprovalInferred",
        "tradeOrAccountActionAllowed",
        "paperTradeAuthorityAllowed",
        "liveTradeAuthorityAllowed",
        "dashboardBehaviorChangeAllowed",
    ):
        add_finding(findings, f"{case_name}_dashboard_boundary_false_{key}", boundary_false(dashboard_report, key), "critical", {key: dashboard_report.get(key)})
    go_boundary = as_dict(go_report.get("authority_boundary"))
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
    ):
        add_finding(findings, f"{case_name}_go_boundary_false_{key}", go_boundary.get(key) is False, "critical", {key: go_boundary.get(key)})


def compare_live(dashboard_report: dict[str, Any], go_report: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    approved_keys = approved_key_count()
    add_finding(findings, "live_dashboard_status_ok_with_a2_fallback", dashboard_report.get("status") == "ok", "critical", dashboard_report.get("status"))
    add_finding(findings, "live_dashboard_sql_read_allowed_with_a2_fallback", dashboard_report.get("sqlReadAllowed") is True, "critical", dashboard_report.get("sqlReadAllowed"))
    add_finding(findings, "live_go_status_ok_with_a2_fallback", go_report.get("status") == "ok", "critical", go_report.get("status"))
    add_finding(findings, "live_go_sql_read_allowed_with_a2_fallback", go_report.get("sql_read_allowed") is True, "critical", go_report.get("sql_read_allowed"))
    add_finding(findings, "live_dashboard_go_row_count_match", len(as_dict(dashboard_report.get("rows"))) == as_dict(go_report.get("summary")).get("cache_rows") == approved_keys, "critical", {"dashboard_rows": len(as_dict(dashboard_report.get("rows"))), "go_cache_rows": as_dict(go_report.get("summary")).get("cache_rows"), "approved_keys": approved_keys})
    add_finding(findings, "live_both_keep_sql_non_canon", dashboard_report.get("sqlIsCanon") is False, "critical", dashboard_report.get("sqlIsCanon"))
    for key in (
        "canonicalNoteMutationAllowed",
        "portfolioMutationAllowed",
        "ownerApprovalInferred",
        "tradeOrAccountActionAllowed",
        "paperTradeAuthorityAllowed",
        "liveTradeAuthorityAllowed",
        "dashboardBehaviorChangeAllowed",
    ):
        add_finding(findings, f"live_dashboard_boundary_false_{key}", boundary_false(dashboard_report, key), "critical", {key: dashboard_report.get(key)})


def case_summary(dashboard_report: dict[str, Any], go_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "dashboard_status": dashboard_report.get("status"),
        "dashboard_sql_read_allowed": dashboard_report.get("sqlReadAllowed"),
        "dashboard_rows": len(as_dict(dashboard_report.get("rows"))),
        "go_status": go_report.get("status"),
        "go_sql_read_allowed": go_report.get("sql_read_allowed"),
        "go_cache_rows": as_dict(go_report.get("summary")).get("cache_rows"),
    }


def build_cycle(cycle: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    clean_dashboard, clean_go = dashboard_fixture_case("clean_fixture")
    missing_dashboard, missing_go = dashboard_fixture_case("missing_fallback")
    stale_dashboard, stale_go = dashboard_fixture_case("stale_unsafe_source")
    live_dashboard, live_go = live_case()
    compare_clean_fixture(clean_dashboard, clean_go, findings)
    compare_blocked_fixture("missing_fallback", missing_dashboard, missing_go, findings)
    compare_blocked_fixture("stale_unsafe_source", stale_dashboard, stale_go, findings)
    compare_live(live_dashboard, live_go, findings)
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    return {
        "cycle": cycle,
        "status": "blocked" if critical else "warning" if warnings else "ok",
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
        },
        "cases": {
            "clean_fixture": case_summary(clean_dashboard, clean_go),
            "missing_fallback": case_summary(missing_dashboard, missing_go),
            "stale_unsafe_source": case_summary(stale_dashboard, stale_go),
            "live_no_fallback": case_summary(live_dashboard, live_go),
        },
        "findings": findings,
    }


def stable_case_fingerprints(cycles: list[dict[str, Any]]) -> bool:
    if not cycles:
        return False
    first = cycles[0].get("cases")
    return all(cycle.get("cases") == first for cycle in cycles)


def build_report(cycles_requested: int) -> dict[str, Any]:
    if shutil.which("go") is None:
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "summary": {"checks": 0, "critical": 1, "warnings": 0, "missing_tools": ["go"]},
            "findings": [],
            "validation": {"status": "error", "errors": ["missing_tool:go"], "warnings": []},
        }
    cycles_requested = max(1, cycles_requested)
    cycles = [build_cycle(cycle) for cycle in range(1, cycles_requested + 1)]
    findings = []
    for cycle in cycles:
        for finding in as_list(cycle.get("findings")):
            if isinstance(finding, dict):
                findings.append({"cycle": cycle.get("cycle"), **finding})
    stable = stable_case_fingerprints(cycles)
    add_finding(findings, "repeated_ab_case_fingerprints_stable", stable, "critical", {"cycles": cycles_requested})
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "dashboard_consumer": "scripts/dashboard_payload.py",
            "python_owner": "scripts/sql_consumer_authority_guard.py",
            "go_companion": "scripts/go/cmd/go-sql-consumer-authority-guard",
            "live_go_report": "tmp/go-sql-consumer-authority-guard.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "approved_keys": approved_key_count(),
            "cycles": cycles_requested,
            "case_fingerprints_stable": stable,
            "cases_per_cycle": 4,
            "demotion_readiness_signal": "dashboard_ab_repeat_clean" if not critical else "not_ready",
        },
        "cases": cycles[0].get("cases"),
        "cycles": [{"cycle": cycle.get("cycle"), "status": cycle.get("status"), "summary": cycle.get("summary"), "cases": cycle.get("cases")} for cycle in cycles],
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "synthetic_fixture_only_for_allow_case": True,
            "live_case_fail_closed_only": True,
            "demotes_python": False,
            "dashboard_behavior_change_allowed": False,
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
    parser = argparse.ArgumentParser(description="Run dashboard A/B proof for Go SQL consumer authority demotion readiness.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--cycles", type=int, default=3, help="Number of repeated A/B cycles to run.")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    out = resolve(args.json_out)
    report = build_report(args.cycles)
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
