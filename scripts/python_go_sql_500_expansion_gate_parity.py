#!/usr/bin/env python3
"""Compare Python and Go SQL 500-ticker expansion design gate outputs.

Report-only migration proof. It does not import tickers, expand SQL-canon,
change production answer paths, mutate canon/portfolio state, infer approval,
or grant paper/live/account authority.
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
DEFAULT_JSON = TMP / "python-go-sql-500-expansion-gate-parity.json"
PYTHON_REPORT = TMP / "sql-500-ticker-expansion-design-gate.json"
GO_REPORT = TMP / "go-sql-500-ticker-expansion-design-gate.json"
SCHEMA = "veritas.python_go_sql_500_expansion_gate_parity.v1"


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


def validation_checks(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(row.get("name")): {"ok": row.get("ok"), "detail": row.get("detail")} for row in as_list(as_dict(payload.get("validation")).get("checks")) if isinstance(row, dict)}


def compare(python_report: dict[str, Any], go_report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    py_state = as_dict(python_report.get("current_state"))
    go_state = as_dict(go_report.get("current_state"))
    add("status_match", python_report.get("status") == go_report.get("status"), "critical", {"python": python_report.get("status"), "go": go_report.get("status")})
    add("validation_status_match", as_dict(python_report.get("validation")).get("status") == as_dict(go_report.get("validation")).get("status"), "critical", {"python": as_dict(python_report.get("validation")).get("status"), "go": as_dict(go_report.get("validation")).get("status")})
    for key in (
        "exists",
        "integrity_check",
        "universe_rows",
        "all_ticker_sql_rows",
        "production_current_cards",
        "production_answer_path_rows",
        "review_monitor_thin_rows",
        "fundamental_snapshot_rows",
        "analyst_snapshot_rows",
        "ticker_family_status_rows",
        "card_registry_rows",
        "missing_card_rows",
        "authority_forbidden_rows",
        "pilot_fixtures",
        "live_pilot_candidates",
        "pilot_production_overlap",
    ):
        add(f"current_state_{key}_match", py_state.get(key) == go_state.get(key), "critical", {"python": py_state.get(key), "go": go_state.get(key)})
    add("validation_checks_match", validation_checks(python_report) == validation_checks(go_report), "critical", {"python": validation_checks(python_report), "go": validation_checks(go_report)})
    add("shard_target_match", as_dict(python_report.get("shard_design")).get("target_total") == as_dict(go_report.get("shard_design")).get("target_total"), "critical", {"python": as_dict(python_report.get("shard_design")).get("target_total"), "go": as_dict(go_report.get("shard_design")).get("target_total")})
    add("enrichment_batch_match", as_dict(python_report.get("enrichment_pilot")).get("tickers") == as_dict(go_report.get("enrichment_pilot")).get("tickers"), "critical", {"python": as_dict(python_report.get("enrichment_pilot")).get("tickers"), "go": as_dict(go_report.get("enrichment_pilot")).get("tickers")})
    add("authority_false_flags_match", as_dict(python_report.get("authority_boundary")) == as_dict(go_report.get("authority_boundary")), "critical", {"python": as_dict(python_report.get("authority_boundary")), "go": as_dict(go_report.get("authority_boundary"))})
    add("staging_gate_count_match", len(as_list(python_report.get("staging_gates"))) == len(as_list(go_report.get("staging_gates"))), "warning", {"python": len(as_list(python_report.get("staging_gates"))), "go": len(as_list(go_report.get("staging_gates")))})
    return findings


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    python_report = load(args.python_report)
    go_report = load(args.go_report)
    missing = []
    if not python_report:
        missing.append(rel(args.python_report))
    if not go_report:
        missing.append(rel(args.go_report))
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
            "python_report": {"path": rel(args.python_report), "status": python_report.get("status"), "schema": python_report.get("schema_version")},
            "go_report": {"path": rel(args.go_report), "status": go_report.get("status"), "schema": go_report.get("schema_version")},
        },
        "summary": {"checks": len(findings), "critical": len(critical), "warnings": len(warnings), "missing_artifacts": missing},
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "broad_ticker_import_allowed": False,
            "production_answer_path_overwrite_allowed": False,
            "sql_canon_expansion_allowed": False,
            "canon_or_portfolio_mutation": False,
            "paper_or_live_execution_authority": False,
            "brokerage_or_account_action": False,
            "owner_approval_inferred": False,
            "money_movement": False,
        },
        "validation": {
            "status": "ok" if not missing and not critical else "error",
            "errors": missing + [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Python and Go SQL 500 expansion design gate reports.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--python-report", type=Path, default=PYTHON_REPORT)
    parser.add_argument("--go-report", type=Path, default=GO_REPORT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve(args.json_out)
    args.python_report = resolve(args.python_report)
    args.go_report = resolve(args.go_report)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
