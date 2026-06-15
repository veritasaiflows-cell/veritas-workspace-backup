#!/usr/bin/env python3
"""Record controlled Go-first/Python-fallback demotion for eligible helpers.

This consumes the contract gate and promotes only parity-green, non-orchestration
helpers into controlled-router design state. It is still report-only: default
routing remains unchanged, Python fallback remains retained, and no helper is
retired or deleted.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-controlled-router-batch.json"
CONTRACT_JSON = TMP / "python-go-sql-helper-contract-gate.json"
FIRST_ROUTER_JSON = TMP / "python-go-sql-consumer-authority-controlled-router.json"
DEFAULT_PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
SCHEMA = "veritas.python_go_sql_helper_controlled_router_batch.v1"


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


def build_route(contract: dict[str, Any]) -> dict[str, Any]:
    parity = as_dict(contract.get("semantic_shape_parity"))
    stability = as_dict(contract.get("consumer_stability"))
    runtime = as_dict(stability.get("runtime_scorecard"))
    harness = as_dict(stability.get("harness"))
    pm_state = as_dict(stability.get("pm_state"))
    fixture = as_dict(contract.get("fixture_contract"))
    return {
        "path": contract.get("path"),
        "demotion_stage": "controlled_go_first_python_fallback",
        "default_route": "python_owner_only",
        "controlled_route": "go_first_with_python_fallback",
        "production_routing_changed": False,
        "python_fallback_retained": True,
        "retire_python_now": False,
        "durable_output": bool(contract.get("durable_output")),
        "candidate_kind": contract.get("candidate_kind"),
        "parity_artifact": parity.get("parity_artifact"),
        "parity_status": parity.get("status"),
        "parity_checks": parity.get("checks"),
        "expected_output_artifact": fixture.get("expected_output_artifact"),
        "consumer_stability": {
            "runtime_ok": runtime.get("ok") is True,
            "runtime_checks_total": runtime.get("checks_total"),
            "harness_ok": harness.get("ok") is True,
            "harness_failure_count": harness.get("failure_count"),
            "pm_state_ok": pm_state.get("ok") is True,
            "pm_state_status": pm_state.get("status"),
        },
        "next_promotion_gate": "collect repeated Go-primary history before any default routing change; keep Python fallback until longer history is clean.",
    }


def build_report() -> dict[str, Any]:
    default_promotion = load(DEFAULT_PROMOTION_JSON)
    if (
        default_promotion.get("status") == "ok"
        and as_dict(default_promotion.get("summary")).get("default_route") == "python_owner_only"
    ):
        python_default_helpers = [
            str(row.get("path"))
            for row in as_list(default_promotion.get("promoted_routes"))
            if isinstance(row, dict) and row.get("path")
        ]
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "ok",
            "workspace_root": str(ROOT),
            "source_artifacts": {
                "default_route_promotion": "tmp/python-go-sql-helper-default-route-promotion.json",
            },
            "summary": {
                "checks": len(python_default_helpers) + 1,
                "critical": 0,
                "warnings": 0,
                "batch_controlled_demoted_helpers": 0,
                "total_controlled_demoted_helpers_including_first": 0,
                "durable_output_helpers_in_batch": 0,
                "production_routing_changed": False,
                "python_fallback_retained": True,
                "retire_python_now": 0,
                "default_route": "python_owner_only",
                "python_default_helpers": len(python_default_helpers),
                "go_validator_only_helpers": len(python_default_helpers),
                "batch_signal": "dormant_python_owner_default_go_validator_only",
            },
            "controlled_router_batch": [],
            "excluded_candidates": {
                "python_default_helpers": python_default_helpers,
                "reason": "Controlled Go-first batch is dormant while Python is owner/default.",
            },
            "findings": [
                {
                    "check": "python_owner_default_route_active",
                    "ok": True,
                    "severity": "info",
                    "detail": "Controlled-router batch is dormant; Go remains validator-only.",
                }
            ],
            "authority_boundary": {
                "report_only": True,
                "read_only": True,
                "controlled_demotion_not_retirement": False,
                "production_routing_changed": False,
                "python_owner_default": True,
                "go_validator_only": True,
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
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }
    contract_gate = load(CONTRACT_JSON)
    first_router = load(FIRST_ROUTER_JSON)
    findings: list[dict[str, Any]] = []

    add(findings, "contract_gate_ok", contract_gate.get("status") == "ok", "critical", contract_gate.get("status"))
    add(findings, "first_controlled_router_ok", first_router.get("status") == "ok", "critical", first_router.get("status"))
    add(
        findings,
        "durable_output_parity_pending_zero",
        int(as_dict(contract_gate.get("summary")).get("durable_output_parity_pending") or 0) == 0,
        "critical",
        contract_gate.get("summary"),
    )
    add(
        findings,
        "retire_python_now_zero",
        int(as_dict(contract_gate.get("summary")).get("retire_python_now") or 0) == 0,
        "critical",
        contract_gate.get("summary"),
    )

    eligible_paths = set(str(path) for path in as_list(contract_gate.get("eligible_next_controlled_router_candidates")))
    contracts = [row for row in as_list(contract_gate.get("contracts")) if isinstance(row, dict)]
    routes = [build_route(row) for row in contracts if str(row.get("path")) in eligible_paths]

    for route in routes:
        add(findings, f"{route['path']}:parity_green", route.get("parity_status") == "green", "critical", route)
        add(findings, f"{route['path']}:runtime_stable", as_dict(route.get("consumer_stability")).get("runtime_ok") is True, "critical", route)
        add(findings, f"{route['path']}:harness_stable", as_dict(route.get("consumer_stability")).get("harness_ok") is True, "critical", route)
        add(findings, f"{route['path']}:pm_state_stable", as_dict(route.get("consumer_stability")).get("pm_state_ok") is True, "critical", route)
        add(findings, f"{route['path']}:fallback_retained", route.get("python_fallback_retained") is True, "critical", route)
        add(findings, f"{route['path']}:production_routing_unchanged", route.get("production_routing_changed") is False, "critical", route)
        add(findings, f"{route['path']}:not_retired", route.get("retire_python_now") is False, "critical", route)

    add(findings, "eligible_routes_match_contract_gate", len(routes) == len(eligible_paths), "critical", {"routes": len(routes), "eligible": len(eligible_paths)})

    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "contract_gate": "tmp/python-go-sql-helper-contract-gate.json",
            "first_controlled_router": "tmp/python-go-sql-consumer-authority-controlled-router.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "batch_controlled_demoted_helpers": len(routes) if not critical else 0,
            "total_controlled_demoted_helpers_including_first": (len(routes) + 1) if not critical else 0,
            "durable_output_helpers_in_batch": sum(1 for row in routes if row.get("durable_output")),
            "production_routing_changed": False,
            "python_fallback_retained": True,
            "retire_python_now": 0,
            "batch_signal": "eligible_helpers_controlled_go_first_python_fallback_recorded" if not critical else "not_ready",
        },
        "controlled_router_batch": routes,
        "excluded_candidates": {
            "orchestration_python_owner_retained": contract_gate.get("orchestration_python_owner_retained", []),
            "durable_output_parity_pending": contract_gate.get("durable_output_parity_pending", []),
        },
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
    parser = argparse.ArgumentParser(description="Record controlled router batch for eligible Python-Go SQL helpers.")
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
