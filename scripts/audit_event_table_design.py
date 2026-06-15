#!/usr/bin/env python3
"""Build the audit-event table design for future service-state storage.

This is schema design only. It does not create or migrate a database. The
schema is SQLite-first and PostgreSQL-compatible in spirit so future service
state can record proof, approvals, and authority rows without storing customer
secrets or implying execution/canon authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from authority_matrix import DEFAULT_MATRIX, build_matrix, validate_matrix
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "audit-event-table-design.json"
DEFAULT_VALIDATION = TMP / "audit-event-table-design-validation.json"

SCHEMA = "veritas.audit_event_table_design.v1"

BOOLEAN_FALSE_DEFAULTS = [
    "contains_secret",
    "contains_customer_data",
    "external_delivery",
    "portfolio_or_canon_mutation",
    "paper_or_live_account_action",
    "owner_approval_inferred",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def column(name: str, sqlite_type: str, *, nullable: bool, description: str, default: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "sqlite_type": sqlite_type,
        "postgres_compatible_type": {
            "TEXT": "text",
            "INTEGER": "integer",
        }.get(sqlite_type, sqlite_type.lower()),
        "nullable": nullable,
        "description": description,
    }
    if default is not None:
        payload["default"] = default
    return payload


def build_design() -> dict[str, Any]:
    matrix = as_dict(load_json_artifact(DEFAULT_MATRIX)) or build_matrix()
    matrix_validation = validate_matrix(matrix)
    columns = [
        column("event_id", "TEXT", nullable=False, description="Stable UUID/ULID-style event identifier."),
        column("event_time_utc", "TEXT", nullable=False, description="ISO-8601 UTC timestamp when the event was recorded."),
        column("actor_type", "TEXT", nullable=False, description="main_session, heartbeat, cron, subagent, script, or owner."),
        column("actor_id", "TEXT", nullable=True, description="Opaque actor/session/script label; never a secret."),
        column("authority_row_id", "TEXT", nullable=False, description="Authority Matrix row controlling this event."),
        column("workflow_id", "TEXT", nullable=True, description="Workflow label such as WF75, WF77, WF78, WF72, WF64/WF56."),
        column("action_type", "TEXT", nullable=False, description="validate, prepare_packet, dry_run, staged_write, exact_apply, render, export, etc."),
        column("action_status", "TEXT", nullable=False, description="ok, warning, blocked, error, cancelled, or superseded."),
        column("artifact_path", "TEXT", nullable=True, description="Relative path to the proof artifact."),
        column("artifact_sha256", "TEXT", nullable=True, description="SHA-256 of the proof artifact when available."),
        column("approval_source", "TEXT", nullable=True, description="Relative path or message reference for scoped approval; never inferred."),
        column("approval_expires_at_utc", "TEXT", nullable=True, description="Optional expiration timestamp for scoped approval."),
        column("rollback_artifact_path", "TEXT", nullable=True, description="Relative path to rollback/backup proof."),
        column("redaction_class", "TEXT", nullable=False, description="public, internal, restricted, secret_reference_only, or blocked_secret."),
        column("contains_secret", "INTEGER", nullable=False, description="0/1 boolean; must default to 0 and be validated false for normal proof logs.", default=0),
        column("contains_customer_data", "INTEGER", nullable=False, description="0/1 boolean; must default to 0 until customer gates exist.", default=0),
        column("external_delivery", "INTEGER", nullable=False, description="0/1 boolean; must default to 0 until launch/delivery gates exist.", default=0),
        column("portfolio_or_canon_mutation", "INTEGER", nullable=False, description="0/1 boolean; true only for exact gated workspace mutation events.", default=0),
        column("paper_or_live_account_action", "INTEGER", nullable=False, description="0/1 boolean; must remain 0 for this product/authority spine.", default=0),
        column("owner_approval_inferred", "INTEGER", nullable=False, description="0/1 boolean; must always be 0.", default=0),
        column("metadata_json", "TEXT", nullable=True, description="Small JSON object for non-secret event metadata."),
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "design_ready",
        "authority_matrix_status": matrix_validation["status"],
        "database_posture": {
            "current_action": "schema_design_only",
            "sqlite_db_create_allowed": False,
            "postgres_migration_allowed": False,
            "customer_data_allowed": False,
            "credential_secret_storage_allowed": False,
            "external_delivery_allowed": False,
            "canon_or_portfolio_apply_allowed_by_this_design": False,
            "paper_or_live_account_action_allowed": False,
        },
        "table": {
            "name": "audit_event",
            "strict_sqlite_recommended": True,
            "columns": columns,
            "primary_key": ["event_id"],
            "foreign_keys_future": [
                {"column": "authority_row_id", "references": "authority_matrix.row_id", "status": "future_service_db_only"},
            ],
            "indexes": [
                {"name": "idx_audit_event_time", "columns": ["event_time_utc"]},
                {"name": "idx_audit_event_authority", "columns": ["authority_row_id"]},
                {"name": "idx_audit_event_workflow", "columns": ["workflow_id"]},
                {"name": "idx_audit_event_status", "columns": ["action_status"]},
                {"name": "idx_audit_event_artifact", "columns": ["artifact_path"]},
            ],
            "check_constraints": [
                "contains_secret IN (0,1)",
                "contains_customer_data IN (0,1)",
                "external_delivery IN (0,1)",
                "portfolio_or_canon_mutation IN (0,1)",
                "paper_or_live_account_action IN (0,1)",
                "owner_approval_inferred = 0",
                "redaction_class IN ('public','internal','restricted','secret_reference_only','blocked_secret')",
            ],
        },
        "sqlite_create_table_sql": [
            "CREATE TABLE audit_event (",
            "  event_id TEXT PRIMARY KEY,",
            "  event_time_utc TEXT NOT NULL,",
            "  actor_type TEXT NOT NULL,",
            "  actor_id TEXT,",
            "  authority_row_id TEXT NOT NULL,",
            "  workflow_id TEXT,",
            "  action_type TEXT NOT NULL,",
            "  action_status TEXT NOT NULL,",
            "  artifact_path TEXT,",
            "  artifact_sha256 TEXT,",
            "  approval_source TEXT,",
            "  approval_expires_at_utc TEXT,",
            "  rollback_artifact_path TEXT,",
            "  redaction_class TEXT NOT NULL CHECK (redaction_class IN ('public','internal','restricted','secret_reference_only','blocked_secret')),",
            "  contains_secret INTEGER NOT NULL DEFAULT 0 CHECK (contains_secret IN (0,1)),",
            "  contains_customer_data INTEGER NOT NULL DEFAULT 0 CHECK (contains_customer_data IN (0,1)),",
            "  external_delivery INTEGER NOT NULL DEFAULT 0 CHECK (external_delivery IN (0,1)),",
            "  portfolio_or_canon_mutation INTEGER NOT NULL DEFAULT 0 CHECK (portfolio_or_canon_mutation IN (0,1)),",
            "  paper_or_live_account_action INTEGER NOT NULL DEFAULT 0 CHECK (paper_or_live_account_action IN (0,1)),",
            "  owner_approval_inferred INTEGER NOT NULL DEFAULT 0 CHECK (owner_approval_inferred = 0),",
            "  metadata_json TEXT",
            ") STRICT;",
        ],
        "sqlite_pragmas_for_future_db": [
            "PRAGMA journal_mode=WAL;",
            "PRAGMA busy_timeout=5000;",
            "PRAGMA foreign_keys=ON;",
            "PRAGMA synchronous=NORMAL;",
        ],
        "stop_lines": [
            "This design does not create a DB.",
            "Audit events must never store secret values.",
            "Customer data, credential storage, external delivery, and account actions remain future-gated.",
        ],
    }


def validate_design(design: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if design.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    posture = as_dict(design.get("database_posture"))
    for key in (
        "sqlite_db_create_allowed",
        "postgres_migration_allowed",
        "customer_data_allowed",
        "credential_secret_storage_allowed",
        "external_delivery_allowed",
        "canon_or_portfolio_apply_allowed_by_this_design",
        "paper_or_live_account_action_allowed",
    ):
        if posture.get(key) is not False:
            errors.append(f"database_posture {key} must be false")
    table = as_dict(design.get("table"))
    columns = table.get("columns") if isinstance(table.get("columns"), list) else []
    column_index = {item.get("name"): item for item in columns if isinstance(item, dict)}
    for name in BOOLEAN_FALSE_DEFAULTS:
        col = as_dict(column_index.get(name))
        if col.get("default") != 0:
            errors.append(f"{name} must default to 0")
    constraints = " ".join(table.get("check_constraints") or [])
    if "owner_approval_inferred = 0" not in constraints:
        errors.append("owner_approval_inferred check constraint missing")
    if not any("STRICT" in line for line in design.get("sqlite_create_table_sql", [])):
        warnings.append("SQLite STRICT table marker not found")
    return {
        "schema": "veritas.audit_event_table_design.validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": "schema design validator only; no DB create/migration, no customer data, no secrets, no external delivery, no account/execution authority",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build audit event table design.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validation-out", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    design = build_design() if args.write or not args.validate else as_dict(load_json_artifact(args.out))
    validation = validate_design(design)
    if args.write:
        atomic_write_json(args.out, design)
        atomic_write_json(args.validation_out, validation)
    else:
        print(json.dumps({"design": design, "validation": validation}, indent=2, sort_keys=True))
    if args.validate and validation["status"] != "ok":
        return 1
    if args.validate:
        print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
