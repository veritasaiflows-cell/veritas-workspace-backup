#!/usr/bin/env python3
"""Collect repeated Python-default route history for SQL/proof helpers.

This gate validates the current routing-policy artifact across clean cycles.
Python remains the owner/default route; Go remains a validator/proof edge only.
It keeps Python fallback retained and denies Python retirement/deletion.
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
DEFAULT_JSON = TMP / "python-go-sql-helper-default-route-history-gate.json"
PROMOTION_JSON = TMP / "python-go-sql-helper-default-route-promotion.json"
HISTORY_JSONL = ROOT / "data" / "state-history" / "python-go-sql-helper-default-route-history-gate.jsonl"
SCHEMA = "veritas.python_go_sql_helper_default_route_history_gate.v1"


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
    return {
        "path": route.get("path"),
        "default_route": route.get("default_route"),
        "primary_runtime": route.get("primary_runtime"),
            "fallback_runtime": route.get("fallback_runtime"),
            "validator_runtime": route.get("validator_runtime"),
            "go_validator_only": route.get("go_validator_only") is True,
        "python_fallback_retained": route.get("python_fallback_retained") is True,
        "retire_python_now": route.get("retire_python_now") is True,
        "python_file_delete_allowed": route.get("python_file_delete_allowed") is True,
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
    promotion = load(PROMOTION_JSON)
    summary = as_dict(promotion.get("summary"))
    routes = [row for row in as_list(promotion.get("promoted_routes")) if isinstance(row, dict)]
    findings: list[dict[str, Any]] = []
    cycle_count = max(1, int(cycles))

    add(findings, "promotion_gate_ok", promotion.get("status") == "ok", "critical", promotion.get("status"))
    add(findings, "promoted_routes_present", len(routes) > 0, "critical", {"route_count": len(routes)})
    add(findings, "fallback_retained", summary.get("python_fallback_retained") is True, "critical", summary)
    add(findings, "retire_python_now_zero", int(summary.get("retire_python_now") or 0) == 0, "critical", summary)
    add(findings, "python_file_delete_disallowed", summary.get("python_file_delete_allowed") is False, "critical", summary)
    add(findings, "sql_write_import_disallowed", summary.get("sql_write_or_import_allowed") is False, "critical", summary)

    cycles_payload = [build_cycle(index + 1, routes) for index in range(cycle_count)]
    route_fingerprints: dict[str, set[str]] = {}
    for cycle in cycles_payload:
        for row in as_list(cycle.get("routes")):
            normalized = as_dict(row.get("normalized"))
            path = str(normalized.get("path") or "")
            route_fingerprints.setdefault(path, set()).add(str(row.get("fingerprint")))
            add(findings, f"{path}:cycle_{cycle['cycle']}:python_owner_default", normalized.get("default_route") == "python_owner_only", "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:go_validator_only", normalized.get("go_validator_only") is True and normalized.get("validator_runtime") == "go", "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:fallback_retained", normalized.get("python_fallback_retained") is True, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:not_retired", normalized.get("retire_python_now") is False, "critical", normalized)
            add(findings, f"{path}:cycle_{cycle['cycle']}:delete_disallowed", normalized.get("python_file_delete_allowed") is False, "critical", normalized)

    stable_paths = sorted(path for path, values in route_fingerprints.items() if path and len(values) == 1)
    unstable_paths = sorted(path for path, values in route_fingerprints.items() if path and len(values) != 1)
    add(
        findings,
        "all_default_route_fingerprints_stable",
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
            "default_route_promotion": "tmp/python-go-sql-helper-default-route-promotion.json",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cycles": cycle_count,
            "routes_per_cycle": len(routes),
            "stable_route_fingerprints": len(stable_paths),
            "unstable_route_fingerprints": len(unstable_paths),
            "default_route": "python_owner_only",
            "python_fallback_retained": True,
            "retire_python_now": 0,
            "python_file_delete_allowed": False,
            "default_route_history_signal": "python_owner_default_history_clean_go_validator_only" if not critical else "not_ready",
        },
        "stable_paths": stable_paths,
        "unstable_paths": unstable_paths,
        "cycles": cycles_payload,
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
    parser = argparse.ArgumentParser(description="Collect repeated default Go-primary route history for promoted helpers.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-history", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--history-out", type=Path, default=HISTORY_JSONL)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def append_history(path: Path, report: dict[str, Any]) -> None:
    """Append compact route-history proof without creating another truth owner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": SCHEMA,
        "generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "summary": report.get("summary"),
        "stable_paths": report.get("stable_paths"),
        "unstable_paths": report.get("unstable_paths"),
        "authority_boundary": report.get("authority_boundary"),
    }
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
        fh.write("\n")


def main() -> int:
    args = parse_args()
    report = build_report(args.cycles)
    if args.write:
        atomic_write_json(resolve(args.json_out), report)
    if args.write_history:
        append_history(resolve(args.history_out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
