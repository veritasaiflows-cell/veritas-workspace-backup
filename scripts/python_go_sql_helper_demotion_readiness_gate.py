#!/usr/bin/env python3
"""Gate Python SQL helper demotion behind proof and fixture contracts.

This report-only gate turns the migration candidate registry into hard stop
lines for demotion:

- durable-output helpers require semantic/shape parity before replacement
- contract-first helpers require a fixture contract before Go ports
- existing Go-covered helpers still keep Python unless repeated A/B/fallback
  history exists

It does not execute candidate helpers, mutate SQL/canon/portfolio/customer/
runtime state, retire Python, or infer approval.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-demotion-readiness-gate.json"
CANDIDATES_JSON = TMP / "python-go-sql-migration-candidates.json"
SCHEMA = "veritas.python_go_sql_helper_demotion_readiness_gate.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def proof_exists(path_value: Any) -> bool:
    if not path_value:
        return False
    path = ROOT / str(path_value).replace("/", "\\")
    return path.exists()


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def contract_requirements(row: dict[str, Any]) -> list[str]:
    requirements = [
        "fixture_input_contract",
        "expected_json_shape_contract",
        "authority_boundary_contract",
        "python_go_semantic_parity_gate",
    ]
    if row.get("durable_output"):
        requirements.extend(["durable_output_shape_parity", "no_durable_write_replacement_without_owner_gate"])
    if row.get("orchestrates_commands"):
        requirements.extend(["command_orchestration_keeps_python_owner", "go_probe_only_for_isolated_read_checks"])
    if row.get("semantic_authority_surface"):
        requirements.extend(["forbidden_authority_fixture_cases", "fallback_or_fail_closed_cases"])
    return sorted(set(requirements))


def build_report() -> dict[str, Any]:
    candidates = as_dict(load_json_artifact(CANDIDATES_JSON))
    demotion_dry_run = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-demotion-dry-run.json"))
    dashboard_ab_gate = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-dashboard-ab.json"))
    controlled_router = as_dict(load_json_artifact(TMP / "python-go-sql-consumer-authority-controlled-router.json"))
    rows = [row for row in as_list(candidates.get("all_candidates")) if isinstance(row, dict)]
    findings: list[dict[str, Any]] = []
    add(findings, "candidate_registry_ok", candidates.get("status") in {"ok", "warning"}, "critical", candidates.get("status"))
    add(findings, "candidate_registry_has_rows", len(rows) > 0, "critical", len(rows))
    add(findings, "demotion_dry_run_ok", demotion_dry_run.get("status") == "ok", "critical", demotion_dry_run.get("status"))
    add(findings, "dashboard_ab_gate_ok", dashboard_ab_gate.get("status") == "ok", "critical", dashboard_ab_gate.get("status"))
    add(findings, "controlled_router_ok", controlled_router.get("status") == "ok", "critical", controlled_router.get("status"))
    add(
        findings,
        "controlled_router_keeps_python_default",
        as_dict(controlled_router.get("route_contract")).get("default_mode") == "python_owner_only"
        and as_dict(controlled_router.get("route_contract")).get("production_routing_changed") is False
        and as_dict(controlled_router.get("route_contract")).get("retire_python_now") is False,
        "critical",
        controlled_router.get("route_contract"),
    )

    existing_go = []
    durable_output = []
    contract_first = []
    blocked_retire = []
    for row in rows:
        go_coverage = as_dict(row.get("go_coverage"))
        if row.get("candidate_kind") == "existing_go_covered":
            existing_go.append(row)
            add(findings, f"covered_proof_exists:{row.get('path')}", proof_exists(go_coverage.get("proof_artifact")), "critical", go_coverage)
        if row.get("durable_output"):
            durable_output.append(row)
            add(findings, f"durable_output_not_retired:{row.get('path')}", row.get("retire_python_now") is False, "critical", row.get("retire_python_now"))
        if row.get("migration_batch") == "batch_2_contract_first" or row.get("candidate_kind") in {"artifact_report_generator", "durable_output_generator", "orchestrating_report_generator", "orchestrating_gate", "durable_registry_generator"}:
            contract_first.append(row)
            add(findings, f"contract_first_not_retired:{row.get('path')}", row.get("retire_python_now") is False, "critical", row.get("retire_python_now"))
        if row.get("retire_python_now") is True:
            blocked_retire.append(row)

    add(findings, "no_helper_marked_retire_now", not blocked_retire, "critical", [row.get("path") for row in blocked_retire])
    add(findings, "ready_spike_count_visible", int(as_dict(candidates.get("summary")).get("ready_for_go_spike") or 0) == 12, "info", as_dict(candidates.get("summary")).get("ready_for_go_spike"))

    contract_queue = []
    for row in rows:
        if row.get("bucket") == "ready_for_go_spike":
            contract_queue.append(
                {
                    "path": row.get("path"),
                    "candidate_kind": row.get("candidate_kind"),
                    "migration_batch": row.get("migration_batch"),
                    "durable_output": bool(row.get("durable_output")),
                    "orchestrates_commands": bool(row.get("orchestrates_commands")),
                    "go_coverage": as_dict(row.get("go_coverage")) or None,
                    "requirements_before_go_replacement": contract_requirements(row),
                    "allowed_next_action": "fixture_contract_or_go_probe_spike_only",
                    "retire_python_now": False,
                }
            )

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
            "demotion_dry_run": "tmp/python-go-sql-consumer-authority-demotion-dry-run.json",
            "dashboard_ab_gate": "tmp/python-go-sql-consumer-authority-dashboard-ab.json",
            "controlled_router": "tmp/python-go-sql-consumer-authority-controlled-router.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "candidate_rows": len(rows),
            "existing_go_covered": len(existing_go),
            "durable_output_candidates": len(durable_output),
            "contract_first_candidates": len(contract_first),
            "ready_for_go_spike_contracts": len(contract_queue),
            "retire_python_now": len(blocked_retire),
            "demotion_gate_signal": "ready_for_controlled_router_ab_only_no_python_retirement" if not critical else "not_ready",
        },
        "contract_first_queue": contract_queue,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "demotes_python": False,
            "executes_candidate_helpers": False,
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
    parser = argparse.ArgumentParser(description="Gate Python SQL helper demotion behind proof contracts.")
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
