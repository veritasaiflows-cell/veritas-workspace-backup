#!/usr/bin/env python3
"""Build the Python SQL helper demotion queue.

This report-only surface records the first controlled demotion and prepares the
remaining candidates. Demotion here means "Go-first eligible with Python
fallback retained"; it does not mean Python deletion, production-only Go
routing, SQL mutation, canon/portfolio mutation, or execution authority.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-demotion-queue.json"
CANDIDATES_JSON = TMP / "python-go-sql-migration-candidates.json"
READINESS_JSON = TMP / "python-go-sql-helper-demotion-readiness-gate.json"
ROUTER_JSON = TMP / "python-go-sql-consumer-authority-controlled-router.json"
SCHEMA = "veritas.python_go_sql_helper_demotion_queue.v1"
FIRST_DEMOTION_PATH = "scripts/sql_consumer_authority_guard.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def candidate_by_path(rows: list[dict[str, Any]], path: str) -> dict[str, Any]:
    for row in rows:
        if row.get("path") == path:
            return row
    return {}


def demotion_requirements(row: dict[str, Any]) -> list[str]:
    requirements = [
        "fixture_input_contract",
        "expected_json_shape_contract",
        "authority_boundary_contract",
        "python_go_semantic_parity_gate",
        "fallback_or_fail_closed_cases",
        "downstream_consumer_ab_history",
    ]
    if row.get("durable_output"):
        requirements.extend(["durable_output_shape_parity", "no_durable_write_replacement_without_owner_gate"])
    if row.get("orchestrates_commands"):
        requirements.extend(["keep_python_orchestration_owner", "extract_go_probe_only"])
    if row.get("candidate_kind") == "existing_go_covered":
        requirements.append("controlled_router_or_consumer_gate_history")
    return sorted(set(requirements))


def build_next_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in rows:
        path = row.get("path")
        if path == FIRST_DEMOTION_PATH:
            continue
        if row.get("bucket") != "ready_for_go_spike":
            continue
        queue.append(
            {
                "path": path,
                "candidate_kind": row.get("candidate_kind"),
                "migration_batch": row.get("migration_batch"),
                "durable_output": bool(row.get("durable_output")),
                "orchestrates_commands": bool(row.get("orchestrates_commands")),
                "go_coverage": as_dict(row.get("go_coverage")) or None,
                "demotion_stage": "not_demoted",
                "allowed_next_action": "build_fixture_contract_or_consumer_ab_gate",
                "requirements_before_controlled_demotion": demotion_requirements(row),
                "retire_python_now": False,
            }
        )
    return queue


def build_report() -> dict[str, Any]:
    candidates = as_dict(load_json_artifact(CANDIDATES_JSON))
    readiness = as_dict(load_json_artifact(READINESS_JSON))
    router = as_dict(load_json_artifact(ROUTER_JSON))
    rows = [row for row in as_list(candidates.get("all_candidates")) if isinstance(row, dict)]
    first = candidate_by_path(rows, FIRST_DEMOTION_PATH)
    router_summary = as_dict(router.get("summary"))
    router_contract = as_dict(router.get("route_contract"))
    findings: list[dict[str, Any]] = []

    add(findings, "candidate_registry_ok", candidates.get("status") in {"ok", "warning"}, "critical", candidates.get("status"))
    readiness_summary = as_dict(readiness.get("summary"))
    readiness_clean = (
        readiness.get("status") in {"ok", "warning"}
        and as_dict(readiness.get("validation")).get("status") == "ok"
        and int(readiness_summary.get("critical") or 0) == 0
    )
    add(findings, "readiness_gate_ok", readiness_clean, "critical", {"status": readiness.get("status"), "summary": readiness_summary})
    add(findings, "controlled_router_ok", router.get("status") == "ok", "critical", router.get("status"))
    add(findings, "first_candidate_present", bool(first), "critical", FIRST_DEMOTION_PATH)
    add(
        findings,
        "first_candidate_has_controlled_stage",
        as_dict(first.get("go_coverage")).get("controlled_demotion_stage") == "go_first_python_fallback_controlled_demoted_not_retired",
        "critical",
        as_dict(first.get("go_coverage")),
    )
    add(
        findings,
        "router_default_remains_python_owned",
        router_contract.get("default_mode") == "python_owner_only"
        and router_contract.get("production_routing_changed") is False
        and router_contract.get("retire_python_now") is False,
        "critical",
        router_contract,
    )
    add(
        findings,
        "router_history_stable",
        router_summary.get("cycles") == 3
        and router_summary.get("route_fingerprints_stable") is True
        and int(router_summary.get("critical") or 0) == 0,
        "critical",
        router_summary,
    )
    add(
        findings,
        "readiness_gate_blocks_retirement",
        as_dict(readiness.get("summary")).get("retire_python_now") == 0,
        "critical",
        readiness.get("summary"),
    )

    next_queue = build_next_queue(rows)
    first_demotion = {
        "path": FIRST_DEMOTION_PATH,
        "demotion_stage": "controlled_go_first_python_fallback",
        "retirement_stage": "not_retired",
        "default_route": "python_owner_only",
        "controlled_route": "go_first_with_python_fallback",
        "production_routing_changed": False,
        "python_fallback_retained": True,
        "retire_python_now": False,
        "go_coverage": as_dict(first.get("go_coverage")) or None,
        "proof_artifacts": {
            "dashboard_ab": "tmp/python-go-sql-consumer-authority-dashboard-ab.json",
            "demotion_dry_run": "tmp/python-go-sql-consumer-authority-demotion-dry-run.json",
            "controlled_router": "tmp/python-go-sql-consumer-authority-controlled-router.json",
            "readiness_gate": "tmp/python-go-sql-helper-demotion-readiness-gate.json",
        },
        "next_promotion_gate": "controlled route may become default only after longer clean history and downstream PM/dashboard/runtime stability; Python still remains fallback.",
    }

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "candidate_registry": "tmp/python-go-sql-migration-candidates.json",
            "readiness_gate": "tmp/python-go-sql-helper-demotion-readiness-gate.json",
            "controlled_router": "tmp/python-go-sql-consumer-authority-controlled-router.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "controlled_demoted_helpers": 1 if not critical else 0,
            "next_queue_candidates": len(next_queue),
            "durable_output_candidates": sum(1 for row in next_queue if row["durable_output"]),
            "existing_go_covered_remaining": sum(1 for row in next_queue if row["candidate_kind"] == "existing_go_covered"),
            "retire_python_now": 0,
            "queue_signal": "first_controlled_demotion_recorded_rest_ready_for_contract_gates" if not critical else "not_ready",
        },
        "first_controlled_demotion": first_demotion,
        "next_demotion_queue": next_queue,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "controlled_demotion_not_retirement": True,
            "production_routing_changed": False,
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
    parser = argparse.ArgumentParser(description="Build Python-Go SQL helper demotion queue.")
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
