#!/usr/bin/env python3
"""Compare Python and Go SQL source-truth authority manifest outputs.

This is a report-only migration gate. It does not promote SQL to source of
truth, mutate SQL or Markdown, change consumers, infer approval, or grant
portfolio/customer/execution authority.
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
DEFAULT_JSON = TMP / "python-go-source-truth-manifest-parity.json"
PYTHON_MANIFEST = TMP / "sql-source-truth-authority-manifest.json"
GO_MANIFEST = TMP / "go-sql-source-truth-authority-manifest.json"
SCHEMA = "veritas.python_go_source_truth_manifest_parity.v1"

FALSE_FLAGS = {
    "source_of_truth_promotion_allowed_by_this_artifact",
    "sql_first_consumer_migration_allowed",
    "sql_canon_expansion_allowed",
    "ticker_import_allowed",
    "production_answer_path_change_allowed",
    "canonical_markdown_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "customer_or_external_delivery_allowed",
    "destructive_cleanup_allowed",
    "config_auth_channel_runtime_mutation_allowed",
}


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


def python_false_flags(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in sorted(FALSE_FLAGS)}


def go_false_flags(payload: dict[str, Any]) -> dict[str, Any]:
    flags = as_dict(payload.get("authority_flags"))
    return {key: flags.get(key) for key in sorted(FALSE_FLAGS)}


def object_names(surface: dict[str, Any]) -> list[str]:
    return sorted(str(row.get("name")) for row in as_list(surface.get("objects")) if isinstance(row, dict) and row.get("name"))


def table_counts(surface: dict[str, Any]) -> dict[str, Any]:
    return as_dict(surface.get("table_counts"))


def note_hashes(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(row.get("path")): row.get("sha256") for row in as_list(payload.get("canonical_owner_notes")) if isinstance(row, dict)}


def compare(python_manifest: dict[str, Any], go_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(check: str, ok: bool, severity: str, detail: Any) -> None:
        findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})

    py_summary = as_dict(python_manifest.get("summary"))
    go_summary = as_dict(go_manifest.get("summary"))
    add("status_equivalent", python_manifest.get("status") == go_manifest.get("status"), "critical", {"python": python_manifest.get("status"), "go": go_manifest.get("status")})
    add("database_surface_count_match", py_summary.get("database_surfaces") == go_summary.get("database_surfaces"), "critical", {"python": py_summary.get("database_surfaces"), "go": go_summary.get("database_surfaces")})
    add("canonical_note_count_match", py_summary.get("canonical_owner_notes") == go_summary.get("canonical_owner_notes"), "critical", {"python": py_summary.get("canonical_owner_notes"), "go": go_summary.get("canonical_owner_notes")})
    add("source_truth_posture_match", py_summary.get("source_of_truth_today") == go_summary.get("source_of_truth_today"), "critical", {"python": py_summary.get("source_of_truth_today"), "go": go_summary.get("source_of_truth_today")})
    add("sql_today_posture_match", py_summary.get("sql_today") == go_summary.get("sql_today"), "critical", {"python": py_summary.get("sql_today"), "go": go_summary.get("sql_today")})
    add("false_authority_flags_match", python_false_flags(python_manifest) == go_false_flags(go_manifest), "critical", {"python": python_false_flags(python_manifest), "go": go_false_flags(go_manifest)})
    add("all_authority_flags_false", all(value is False for value in go_false_flags(go_manifest).values()), "critical", go_false_flags(go_manifest))

    py_dbs = as_dict(python_manifest.get("database_surfaces"))
    go_dbs = as_dict(go_manifest.get("database_surfaces"))
    add("database_surface_names_match", sorted(py_dbs) == sorted(go_dbs), "critical", {"python": sorted(py_dbs), "go": sorted(go_dbs)})
    for name in sorted(set(py_dbs) & set(go_dbs)):
        py_surface = as_dict(py_dbs.get(name))
        go_surface = as_dict(go_dbs.get(name))
        add(f"{name}:exists_match", py_surface.get("exists") == go_surface.get("exists"), "critical", {"python": py_surface.get("exists"), "go": go_surface.get("exists")})
        add(f"{name}:integrity_match", py_surface.get("integrity_check") == go_surface.get("integrity_check"), "critical", {"python": py_surface.get("integrity_check"), "go": go_surface.get("integrity_check")})
        add(f"{name}:object_names_match", object_names(py_surface) == object_names(go_surface), "warning", {"python": object_names(py_surface), "go": object_names(go_surface)})
        add(f"{name}:table_counts_match", table_counts(py_surface) == table_counts(go_surface), "warning", {"python": table_counts(py_surface), "go": table_counts(go_surface)})

    add("canonical_note_hashes_match", note_hashes(python_manifest) == note_hashes(go_manifest), "critical", {"python": note_hashes(python_manifest), "go": note_hashes(go_manifest)})
    return findings


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    python_manifest = load(args.python_manifest)
    go_manifest = load(args.go_manifest)
    findings = compare(python_manifest, go_manifest) if python_manifest and go_manifest else []
    missing = []
    if not python_manifest:
        missing.append(rel(args.python_manifest))
    if not go_manifest:
        missing.append(rel(args.go_manifest))
    critical = [row for row in findings if row.get("ok") is not True and row.get("severity") == "critical"]
    warnings = [row for row in findings if row.get("ok") is not True and row.get("severity") == "warning"]
    status = "blocked" if missing or critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "source_artifacts": {
            "python_manifest": {"path": rel(args.python_manifest), "status": python_manifest.get("status"), "schema": python_manifest.get("schema_version")},
            "go_manifest": {"path": rel(args.go_manifest), "status": go_manifest.get("status"), "schema": go_manifest.get("schema_version")},
        },
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "missing_artifacts": missing,
        },
        "findings": findings,
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "sql_write_or_import_allowed": False,
            "source_of_truth_promotion_allowed": False,
            "consumer_migration_allowed": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution_authority": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
        "validation": {
            "status": "ok" if not missing and not critical else "error",
            "errors": missing + [str(row.get("check")) for row in critical],
            "warnings": [str(row.get("check")) for row in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Python and Go source-truth authority manifests.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--python-manifest", type=Path, default=PYTHON_MANIFEST)
    parser.add_argument("--go-manifest", type=Path, default=GO_MANIFEST)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve(args.json_out)
    args.python_manifest = resolve(args.python_manifest)
    args.go_manifest = resolve(args.go_manifest)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
