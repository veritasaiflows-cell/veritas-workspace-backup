#!/usr/bin/env python3
"""Compare Python and Go finance human-notes SQL-canon check outputs.

Report-only migration proof. It does not archive, delete, mutate canonical
notes, change portfolio state, infer approval, or grant paper/live/account
authority.
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
DEFAULT_JSON = TMP / "python-go-finance-human-notes-sql-check-parity.json"
PYTHON_REPORT = TMP / "finance-human-notes-thinning-candidates.json"
GO_REPORT = TMP / "go-finance-human-notes-sql-check.json"
SCHEMA = "veritas.python_go_finance_human_notes_sql_check_parity.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def compare(python_report: dict[str, Any], go_report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    py_check = as_dict(python_report.get("sql_canon_check"))
    go_check = as_dict(go_report.get("sql_canon_check"))
    for key in ("status", "path", "integrity", "active_ticker_count", "legacy_answer_path_count", "review_monitor_count"):
        add(f"sql_canon_{key}_match", py_check.get(key) == go_check.get(key), "critical", {"python": py_check.get(key), "go": go_check.get(key)})
    add("go_validation_ok", as_dict(go_report.get("validation")).get("status") == "ok", "critical", as_dict(go_report.get("validation")))
    boundary = as_dict(go_report.get("authority_boundary"))
    add("go_boundary_report_only_read_only", boundary.get("report_only") is True and boundary.get("read_only") is True, "critical", boundary)
    for key in (
        "human_note_archive_applied",
        "delete_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "customer_or_external_delivery_allowed",
        "paper_or_live_execution_allowed",
        "trade_or_account_action_allowed",
        "money_movement_allowed",
        "owner_approval_inferred",
        "config_auth_runtime_mutation",
    ):
        add(f"go_boundary_false_{key}", boundary.get(key) in {False, None}, "critical", {key: boundary.get(key)})
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
            "python_report": {"path": rel(args.python_report), "status": python_report.get("status"), "sql_canon_check": as_dict(python_report.get("sql_canon_check")).get("status")},
            "go_report": {"path": rel(args.go_report), "status": go_report.get("status"), "sql_canon_check": as_dict(go_report.get("sql_canon_check")).get("status")},
        },
        "summary": {"checks": len(findings), "critical": len(critical), "warnings": len(warnings), "missing_artifacts": missing},
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "human_note_archive_applied": False,
            "delete_allowed": False,
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
    parser = argparse.ArgumentParser(description="Compare Python and Go finance human-notes SQL check reports.")
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
