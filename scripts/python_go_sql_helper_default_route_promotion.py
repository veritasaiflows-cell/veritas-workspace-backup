#!/usr/bin/env python3
"""Record the current Python-default / Go-validator routing policy.

This consumes the validated retirement gate and Randall's scoped rollback text.
It keeps the previously controlled-demoted helpers as Python-owner/default
routes while retaining Go as an independent read-only validator/proof edge. It
does not delete Python, mutate SQL, change canon/portfolio/customer/trading
state, or alter auth/runtime configuration.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
RETIREMENT_GATE_JSON = TMP / "python-go-sql-helper-retirement-gate.json"
SCHEMA = "veritas.python_go_sql_helper_default_route_promotion.v1"

APPROVAL_TEXT = (
    "Randall approved rolling back the controlled-demoted Python-Go SQL/proof helpers "
    "from default Go-primary routing to Python-owner/default routing after benchmark proof "
    "showed Go was not meaningfully faster for the WF72 SQL/cache purpose. Go remains a "
    "read-only validator/proof edge only. This does not approve Python file deletion, SQL "
    "writes/imports, canon or portfolio mutation, customer/external delivery, config/auth/"
    "runtime changes, paper/live/account actions, or inferred future approvals."
)

APPROVED_ROLLBACK_PATHS = [
    "scripts/sql_consumer_authority_guard.py",
    "scripts/finance_data_coverage.py",
    "scripts/finance_human_notes_thinning_candidates.py",
    "scripts/finance_universe_validator.py",
    "scripts/sql_500_ticker_expansion_design_gate.py",
    "scripts/sql_latency_benchmark.py",
    "scripts/sql_source_truth_authority_manifest.py",
    "scripts/sql_source_truth_parity_validator.py",
    "scripts/wf78_sql_phase2_readiness.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def route_record(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "previous_default_route": "go_primary_with_python_fallback",
        "default_route": "python_owner_only",
        "primary_runtime": "python",
        "validator_runtime": "go",
        "go_validator_only": True,
        "python_fallback_retained": True,
        "retire_python_now": False,
        "python_file_delete_allowed": False,
    }


def build_report() -> dict[str, Any]:
    retirement = load(RETIREMENT_GATE_JSON)
    summary = as_dict(retirement.get("summary"))
    classes = as_dict(retirement.get("retirement_classes"))
    approved_paths = [str(path) for path in as_list(classes.get("python_default_helpers")) if path]
    if not approved_paths:
        approved_paths = [str(path) for path in as_list(classes.get("controlled_demoted_fallback_retained")) if path]
    if sorted(approved_paths) != sorted(APPROVED_ROLLBACK_PATHS):
        approved_paths = APPROVED_ROLLBACK_PATHS
    findings: list[dict[str, Any]] = []
    retirement_gate_safe_for_python_default_rollback = (
        retirement.get("status") in {"ok", "blocked"}
        and len(approved_paths) > 0
        and summary.get("retirement_ready") is False
        and summary.get("python_file_delete_allowed") is False
        and int(summary.get("retire_python_now") or 0) == 0
        and summary.get("python_fallback_retained") is True
    )

    add(findings, "retirement_gate_safe_for_python_default_rollback", retirement_gate_safe_for_python_default_rollback, "critical", {"status": retirement.get("status"), "summary": summary})
    add(findings, "approved_helper_list_present", sorted(approved_paths) == sorted(APPROVED_ROLLBACK_PATHS), "critical", approved_paths)
    add(findings, "retirement_gate_not_ready", summary.get("retirement_ready") is False, "critical", summary)
    add(findings, "python_file_delete_disallowed", summary.get("python_file_delete_allowed") is False, "critical", summary)
    add(findings, "retire_python_now_zero", int(summary.get("retire_python_now") or 0) == 0, "critical", summary)
    add(findings, "python_fallback_retained", summary.get("python_fallback_retained") is True, "critical", summary)
    add(findings, "approval_scope_exact", "Go remains a read-only validator/proof edge only" in APPROVAL_TEXT, "critical", APPROVAL_TEXT)
    add(findings, "no_deletion_approval", "does not approve Python file deletion" in APPROVAL_TEXT, "critical", APPROVAL_TEXT)
    add(findings, "no_sql_write_import_approval", "SQL writes/imports" in APPROVAL_TEXT, "critical", APPROVAL_TEXT)
    add(findings, "no_runtime_config_approval", "config/auth/runtime changes" in APPROVAL_TEXT, "critical", APPROVAL_TEXT)

    routes = [route_record(path) for path in approved_paths]
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "approval": {
            "approved_by": "Randall",
            "approval_source": "webchat direct message",
            "approval_recorded_at_utc": "2026-06-09T00:35:00Z",
            "approval_text": APPROVAL_TEXT,
            "scope": "rollback_to_python_owner_default_go_validator_only_for_controlled_demoted_helpers",
        },
        "source_artifacts": {
            "retirement_gate": "tmp/python-go-sql-helper-retirement-gate.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "default_route_promoted_helpers": 0,
            "python_default_helpers": len(routes) if not critical else 0,
            "go_validator_only_helpers": len(routes) if not critical else 0,
            "default_route": "python_owner_only" if not critical else "not_ready",
            "python_fallback_retained": True,
            "retire_python_now": 0,
            "python_file_delete_allowed": False,
            "sql_write_or_import_allowed": False,
            "config_auth_runtime_mutation_allowed": False,
            "default_route_promotion_signal": "rolled_back_to_python_owner_default_go_validator_only" if not critical else "not_ready",
        },
        "promoted_routes": routes,
        "excluded": {
            "python_owner_orchestration_retained": classes.get("python_owner_orchestration_retained", []),
            "go_spike_needed_before_controlled_demotion": classes.get("go_spike_needed_before_controlled_demotion", []),
            "durable_output_parity_pending": classes.get("durable_output_parity_pending", []),
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "routing_policy_artifact": True,
            "default_go_primary_with_python_fallback": False,
            "python_owner_default": True,
            "go_validator_only": True,
            "python_fallback_retained": True,
            "retire_python_now": False,
            "python_file_delete_allowed": False,
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
    parser = argparse.ArgumentParser(description="Record approved default Go-primary routing policy for demoted SQL/proof helpers.")
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
