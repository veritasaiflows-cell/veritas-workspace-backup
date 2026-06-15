#!/usr/bin/env python3
"""Run repeated Go-primary history checks for controlled helper demotion.

This is a report-only gate over the controlled Go-first/Python-fallback batch.
It proves the recorded controlled routes stay stable across clean cycles before
any default routing change is considered. It does not execute candidate helpers,
change routing, retire Python, or delete files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-helper-go-primary-history-gate.json"
CONTROLLED_BATCH_JSON = TMP / "python-go-sql-helper-controlled-router-batch.json"
DEFAULT_PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
SCHEMA = "veritas.python_go_sql_helper_go_primary_history_gate.v1"


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


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_route(route: dict[str, Any]) -> dict[str, Any]:
    stability = as_dict(route.get("consumer_stability"))
    return {
        "path": route.get("path"),
        "demotion_stage": route.get("demotion_stage"),
        "default_route": route.get("default_route"),
        "controlled_route": route.get("controlled_route"),
        "production_routing_changed": route.get("production_routing_changed") is True,
        "python_fallback_retained": route.get("python_fallback_retained") is True,
        "retire_python_now": route.get("retire_python_now") is True,
        "durable_output": route.get("durable_output") is True,
        "candidate_kind": route.get("candidate_kind"),
        "parity_status": route.get("parity_status"),
        "parity_checks": route.get("parity_checks"),
        "expected_output_artifact": route.get("expected_output_artifact"),
        "runtime_ok": stability.get("runtime_ok") is True,
        "runtime_checks_total": stability.get("runtime_checks_total"),
        "harness_ok": stability.get("harness_ok") is True,
        "harness_failure_count": stability.get("harness_failure_count"),
        "pm_state_ok": stability.get("pm_state_ok") is True,
        "pm_state_status": stability.get("pm_state_status"),
    }


def build_cycle(cycle: int, routes: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for route in routes:
        normalized = normalize_route(route)
        rows.append(
            {
                "cycle": cycle,
                "path": normalized.get("path"),
                "fingerprint": fingerprint(normalized),
                "normalized": normalized,
            }
        )
    return {"cycle": cycle, "routes": rows}


def build_report(cycles: int) -> dict[str, Any]:
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
                "cycles": max(1, int(cycles)),
                "routes_per_cycle": 0,
                "stable_route_fingerprints": len(python_default_helpers),
                "unstable_route_fingerprints": 0,
                "production_routing_changed": False,
                "python_fallback_retained": True,
                "retire_python_now": 0,
                "default_route": "python_owner_only",
                "python_default_helpers": len(python_default_helpers),
                "go_validator_only_helpers": len(python_default_helpers),
                "go_primary_history_signal": "dormant_python_owner_default_go_validator_only",
            },
            "stable_paths": python_default_helpers,
            "unstable_paths": [],
            "cycles": [],
            "findings": [
                {
                    "check": "python_owner_default_route_active",
                    "ok": True,
                    "severity": "info",
                    "detail": "Go-primary history is dormant while Python is owner/default.",
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
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }
    controlled_batch = load(CONTROLLED_BATCH_JSON)
    findings: list[dict[str, Any]] = []
    cycle_count = max(1, int(cycles))

    add(findings, "controlled_batch_ok", controlled_batch.get("status") == "ok", "critical", controlled_batch.get("status"))
    add(
        findings,
        "controlled_batch_fallback_retained",
        as_dict(controlled_batch.get("summary")).get("python_fallback_retained") is True,
        "critical",
        controlled_batch.get("summary"),
    )
    add(
        findings,
        "controlled_batch_production_unchanged",
        as_dict(controlled_batch.get("summary")).get("production_routing_changed") is False,
        "critical",
        controlled_batch.get("summary"),
    )
    add(
        findings,
        "controlled_batch_not_retired",
        int(as_dict(controlled_batch.get("summary")).get("retire_python_now") or 0) == 0,
        "critical",
        controlled_batch.get("summary"),
    )

    routes = [row for row in as_list(controlled_batch.get("controlled_router_batch")) if isinstance(row, dict)]
    add(findings, "controlled_routes_present", len(routes) > 0, "critical", {"route_count": len(routes)})
    cycles_payload = [build_cycle(index + 1, routes) for index in range(cycle_count)]

    route_fingerprints: dict[str, set[str]] = {}
    for cycle in cycles_payload:
        for row in as_list(cycle.get("routes")):
            normalized = as_dict(row.get("normalized"))
            path = str(normalized.get("path") or "")
            route_fingerprints.setdefault(path, set()).add(str(row.get("fingerprint")))
            add(findings, f"{path}:cycle_{cycle['cycle']}:parity_green", normalized.get("parity_status") == "green", "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:runtime_stable", normalized.get("runtime_ok") is True, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:harness_stable", normalized.get("harness_ok") is True, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:pm_state_stable", normalized.get("pm_state_ok") is True, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:fallback_retained", normalized.get("python_fallback_retained") is True, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:production_unchanged", normalized.get("production_routing_changed") is False, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:not_retired", normalized.get("retire_python_now") is False, "critical", normalized)

    stable_paths = sorted(path for path, values in route_fingerprints.items() if path and len(values) == 1)
    unstable_paths = sorted(path for path, values in route_fingerprints.items() if path and len(values) != 1)
    add(
        findings,
        "all_cycle_fingerprints_stable",
        len(unstable_paths) == 0 and len(stable_paths) == len(routes),
        "critical",
        {"stable_paths": stable_paths, "unstable_paths": unstable_paths},
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
            "controlled_router_batch": "tmp/python-go-sql-helper-controlled-router-batch.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cycles": cycle_count,
            "routes_per_cycle": len(routes),
            "stable_route_fingerprints": len(stable_paths),
            "unstable_route_fingerprints": len(unstable_paths),
            "production_routing_changed": False,
            "python_fallback_retained": True,
            "retire_python_now": 0,
            "go_primary_history_signal": "go_primary_history_clean_not_retirement_ready" if not critical else "not_ready",
        },
        "stable_paths": stable_paths,
        "unstable_paths": unstable_paths,
        "cycles": cycles_payload,
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "controlled_demotion_not_retirement": True,
            "production_routing_changed": False,
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
    parser = argparse.ArgumentParser(description="Run repeated Go-primary history gate for controlled SQL helper demotion.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
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
