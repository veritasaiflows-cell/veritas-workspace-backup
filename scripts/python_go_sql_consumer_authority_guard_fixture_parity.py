#!/usr/bin/env python3
"""Fixture parity for Python/Go SQL consumer authority guard demotion readiness.

This report-only gate builds a temporary clean fixture root with exactly the
approved SQL-canon consumer keys, matching fallback values, verified source
hashes, and no authority widening. It proves the Go companion can reach the
same read-allowed posture as the Python owner under the narrow safe contract.

It does not mutate live SQL, canon, portfolio, customer, runtime config,
paper/live/account state, or owner approval state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from sql_consumer_authority_guard import (
    ENTRY_STOP_REFERENCE_METADATA_FIELDS,
    LOW_RISK_APPROVED_KEYS,
    LOW_RISK_SQL_CANON_BOUNDARY,
    WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
    active_sql_canon_approved_keys,
    build_phase4a_sql_consumer_authority_guard,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-consumer-authority-guard-fixture-parity.json"
SCHEMA = "veritas.python_go_sql_consumer_authority_guard_fixture_parity.v1"


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fallback_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in active_sql_canon_approved_keys():
        _scope, field = key.split(":", 1)
        if field.endswith("source_freshness_classification"):
            values[key] = "fresh"
        elif field.endswith("confirmed"):
            values[key] = "true"
        elif field.endswith("date"):
            values[key] = "2026-05-31"
        else:
            values[key] = "fixture_ok"
    return values


def authority_boundary_for_field(field: str) -> str:
    if field in ENTRY_STOP_REFERENCE_METADATA_FIELDS:
        return WF72_ENTRY_STOP_SQL_CANON_BOUNDARY
    return LOW_RISK_SQL_CANON_BOUNDARY


def build_fixture(root: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    fixture_tmp = root / "tmp"
    fixture_tmp.mkdir(parents=True)
    source = fixture_tmp / "consumer-authority-fixture-source.json"
    source.write_text(json.dumps({"fixture": "consumer_authority", "generated_at_utc": utc_now()}, sort_keys=True), encoding="utf-8")
    source_hash = sha256(source)
    fallback = fallback_values()
    active_keys = [key for key in active_sql_canon_approved_keys() if key not in LOW_RISK_APPROVED_KEYS]
    activation_state_path = fixture_tmp / "wf72-entry-stop-sql-activation-state.json"
    activation_state_path.write_text(
        json.dumps(
            {
                "schema_version": "wf72_entry_stop_sql_activation_state.v1",
                "status": "activation_ready",
                "active_entry_stop_reference_keys": active_keys,
                "authority_boundary": WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
                "proposal_apply_allowed": False,
                "portfolio_mutation_allowed": False,
                "trade_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    fallback_path = fixture_tmp / "consumer-authority-fallback-values.json"
    fallback_path.write_text(json.dumps(fallback, indent=2, sort_keys=True), encoding="utf-8")

    artifact_db = fixture_tmp / "veritas-artifact-index.sqlite"
    conn = sqlite3.connect(artifact_db)
    try:
        conn.executescript(
            """
            CREATE TABLE authority_flags (
              artifact_run_id TEXT,
              flag_name TEXT,
              flag_value INTEGER,
              surface TEXT,
              raw_value TEXT,
              source_file TEXT
            );
            CREATE TABLE canon_proposal_staging (
              proposal_apply_allowed INTEGER NOT NULL DEFAULT 0,
              applied INTEGER NOT NULL DEFAULT 0,
              requires_owner_approval INTEGER NOT NULL DEFAULT 1,
              source_lineage_status TEXT NOT NULL DEFAULT 'verified',
              evidence_status TEXT NOT NULL DEFAULT 'staged',
              validator_status TEXT NOT NULL DEFAULT 'ok',
              status TEXT NOT NULL DEFAULT 'review_only'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    cache_db = fixture_tmp / "veritas-canon-cache.sqlite"
    conn = sqlite3.connect(cache_db)
    try:
        conn.executescript(
            """
            CREATE TABLE canon_cache_meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE canon_cache_fields (
              scope TEXT NOT NULL,
              field_name TEXT NOT NULL,
              field_value TEXT NOT NULL,
              validator_status TEXT NOT NULL,
              reconciliation_status TEXT NOT NULL,
              freshness_status TEXT NOT NULL,
              source_artifact_path TEXT NOT NULL,
              source_artifact_hash TEXT NOT NULL,
              authority_boundary TEXT NOT NULL
            );
            """
        )
        meta = {
            "authority_boundary": WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
            "sql_canon_authority": "true",
            "consumer_authority_scope": "dashboard_proof_metadata_only",
            "fallback_required": "true",
        }
        conn.executemany("INSERT INTO canon_cache_meta (key, value) VALUES (?, ?)", sorted(meta.items()))
        rows = []
        source_rel = "tmp/consumer-authority-fixture-source.json"
        for key, value in fallback.items():
            scope, field = key.split(":", 1)
            rows.append((scope, field, value, "ok", "match", "fresh", source_rel, source_hash, authority_boundary_for_field(field)))
        conn.executemany(
            """
            INSERT INTO canon_cache_fields
            (scope, field_name, field_value, validator_status, reconciliation_status, freshness_status, source_artifact_path, source_artifact_hash, authority_boundary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return artifact_db, cache_db, fallback_path, fallback


def check_map(report: dict[str, Any]) -> dict[str, bool]:
    return {str(row.get("name")): bool(row.get("ok")) for row in as_list(report.get("checks")) if isinstance(row, dict)}


def compare(python_report: dict[str, Any], go_report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    go_summary = as_dict(go_report.get("summary"))
    py_keys = set(as_list(python_report.get("approved_keys")))
    py_cache_keys = {f"{row.get('scope')}:{row.get('field_name')}" for row in as_list(python_report.get("cache_rows"))}
    py_summary = {
        "approved_keys": len(py_keys),
        "cache_rows": len(as_list(python_report.get("cache_rows"))),
        "extra_keys": len(py_cache_keys - py_keys),
        "missing_keys": len(py_keys - py_cache_keys),
        "fallback_missing_keys": len(as_list(python_report.get("fallback_missing_keys"))),
        "forbidden_true_rows": len(as_list(python_report.get("forbidden_true_rows"))),
        "cache_forbidden_rows": len(as_list(python_report.get("cache_forbidden_rows"))),
        "cache_stale_or_unsafe_rows": len(as_list(python_report.get("cache_stale_or_unsafe_rows"))),
        "canon_stage_apply_allowed_true_count": python_report.get("canon_stage_apply_allowed_true_count"),
        "canon_stage_incomplete_review_only_rows": python_report.get("canon_stage_incomplete_review_only_rows"),
    }
    add("python_allows_clean_fixture", python_report.get("status") == "ok" and python_report.get("sql_read_allowed") is True, "critical", {"status": python_report.get("status"), "sql_read_allowed": python_report.get("sql_read_allowed")})
    add("go_allows_clean_fixture", go_report.get("status") == "ok" and go_report.get("sql_read_allowed") is True, "critical", {"status": go_report.get("status"), "sql_read_allowed": go_report.get("sql_read_allowed")})
    for key, value in py_summary.items():
        add(f"summary_{key}_match", value == go_summary.get(key), "critical", {"python": value, "go": go_summary.get(key)})
    py_checks = check_map(python_report)
    go_checks = check_map(go_report)
    for name in (
        "forbidden_authority_flags_false",
        "canon_stage_apply_not_allowed",
        "canon_cache_integrity_ok",
        "sql_canon_boundary_active",
        "sql_canon_authority_true",
        "consumer_scope_dashboard_proof_metadata_only",
        "fallback_required_meta_true",
        "exact_approved_keys_only",
        "row_boundaries_and_field_families_allowed",
        "fallback_values_present",
        "cache_source_freshness_safe",
    ):
        add(f"check_{name}_match", py_checks.get(name) == go_checks.get(name) == True, "critical", {"python": py_checks.get(name), "go": go_checks.get(name)})
    boundary = as_dict(go_report.get("authority_boundary"))
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
        add(f"go_boundary_false_{key}", boundary.get(key) is False, "critical", {key: boundary.get(key)})
    return findings


def run_go_fixture(fixture_root: Path, fallback_path: Path) -> dict[str, Any]:
    out = fixture_root / "tmp" / "go-consumer-authority-fixture-report.json"
    command = [
        "go",
        "run",
        ".\\cmd\\go-sql-consumer-authority-guard",
        "--root",
        str(fixture_root),
        "--fallback-json",
        str(fallback_path),
        "--out",
        str(out),
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT / "scripts" / "go"),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=240,
    )
    if completed.returncode != 0:
        return {
            "status": "command_failed",
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": (completed.stdout or "")[-3000:],
            "stderr_tail": (completed.stderr or "")[-3000:],
        }
    payload = load_json_artifact(out)
    return payload if isinstance(payload, dict) else {"status": "missing_go_fixture_output", "path": str(out)}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    missing_tools = []
    if shutil.which("go") is None:
        missing_tools.append("go")
    if missing_tools:
        return {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "summary": {"checks": 0, "critical": len(missing_tools), "warnings": 0, "missing_tools": missing_tools},
            "findings": [],
            "validation": {"status": "error", "errors": [f"missing_tool:{tool}" for tool in missing_tools], "warnings": []},
        }
    with tempfile.TemporaryDirectory(prefix="veritas-go-consumer-authority-", ignore_cleanup_errors=True) as temp_name:
        fixture_root = Path(temp_name)
        artifact_db, cache_db, fallback_path, fallback = build_fixture(fixture_root)
        python_report = build_phase4a_sql_consumer_authority_guard(
            workspace=fixture_root,
            artifact_index_db=artifact_db,
            canon_cache_db=cache_db,
            fallback_values_by_key=fallback,
        )
        go_report = run_go_fixture(fixture_root, fallback_path)
        findings = compare(python_report, go_report)
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "python_owner": "scripts/sql_consumer_authority_guard.py",
            "go_companion": "scripts/go/cmd/go-sql-consumer-authority-guard",
            "fixture_type": "synthetic_clean_approved_key_fallback_present",
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "approved_keys": len(active_sql_canon_approved_keys()),
            "demotion_readiness_signal": "fixture_parity_clean" if not critical else "not_ready",
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "synthetic_fixture_only": True,
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
    parser = argparse.ArgumentParser(description="Run clean fixture parity for SQL consumer authority guard.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve(args.json_out)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
