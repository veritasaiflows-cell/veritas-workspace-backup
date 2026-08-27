#!/usr/bin/env python3
"""Validate the live finance-canon DB against the SQL-canon Phase 2 contract."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-phase2-schema-contract-guard.json"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_SCHEMA = ROOT / "tmp" / "sql-canon-schema-authority-packet.json"

REQUIRED_TABLES = {
    "finance_state_meta",
    "securities",
    "universe_membership",
    "tier_routing_state",
    "source_lineage",
    "reference_levels",
    "evidence_freshness",
    "consumer_migration_registry",
    "authority_events",
    "migration_validation_runs",
}
REQUIRED_VIEWS = {
    "current_active_universe",
    "current_answer_path",
    "review_monitor_universe",
    "current_sql_canon_routing",
}
REQUIRED_COLUMNS = {
    "tier_routing_state": {"ticker", "auto_tier", "auto_state", "capital_deployment_approved", "trade_or_execution_approved", "source_artifact_path"},
    "source_lineage": {"lineage_id", "scope", "scope_key", "field_family", "field_name", "source_artifact_sha256", "authority_class", "fallback_rule"},
    "reference_levels": {"ticker", "reference_price_low", "reference_price_high", "reference_invalidation_level", "authority_class"},
    "evidence_freshness": {"ticker", "resolution_state", "required_depth", "source_confidence_class", "authority_class"},
    "consumer_migration_registry": {"consumer_path", "consumer_type", "priority", "migration_lane", "cutover_state", "fallback_required", "parity_required"},
    "authority_events": {"event_id", "event_time_utc", "event_type", "approval_source", "approval_message_id"},
    "migration_validation_runs": {"run_id", "validator_name", "status", "artifact_path"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def counts(conn: sqlite3.Connection, names: set[str]) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for name in sorted(names):
        try:
            result[name] = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        except sqlite3.Error as exc:
            result[name] = f"error:{exc}"
    return result


def build(db: Path, schema_packet: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    packet = load_json(schema_packet)
    target_tables = {
        str(row.get("table"))
        for row in packet.get("target_tables", [])
        if isinstance(row, dict) and row.get("table")
    }
    expected_tables = REQUIRED_TABLES | target_tables

    if not db.exists():
        add("db_exists", False, rel(db))
        return payload(checks, db, schema_packet, {}, {}, {})

    with connect_ro(db) as conn:
        rows = conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view')").fetchall()
        tables = {str(row["name"]) for row in rows if row["type"] == "table"}
        views = {str(row["name"]) for row in rows if row["type"] == "view"}
        missing_tables = sorted(expected_tables - tables)
        missing_views = sorted(REQUIRED_VIEWS - views)
        column_missing = {
            table: sorted(required - table_columns(conn, table))
            for table, required in REQUIRED_COLUMNS.items()
            if table in tables and required - table_columns(conn, table)
        }
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        table_counts = counts(conn, expected_tables & tables)
        view_counts = counts(conn, REQUIRED_VIEWS & views)

    add("schema_packet_present", schema_packet.exists(), rel(schema_packet))
    add("integrity_check_ok", integrity == "ok", integrity)
    add("foreign_key_check_ok", len(fk_issues) == 0, len(fk_issues))
    add("required_tables_present", not missing_tables, missing_tables)
    add("required_views_present", not missing_views, missing_views)
    add("required_columns_present", not column_missing, column_missing)
    add("phase2_rows_present", table_counts.get("tier_routing_state") == 200 and table_counts.get("evidence_freshness") == 200, table_counts)

    return payload(checks, db, schema_packet, table_counts, view_counts, packet)


def payload(
    checks: list[dict[str, Any]],
    db: Path,
    schema_packet: Path,
    table_counts: dict[str, Any],
    view_counts: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"]]
    return {
        "schema_version": "sql_canon_phase2_schema_contract_guard.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "db": rel(db),
        "schema_packet": rel(schema_packet),
        "schema_packet_status": packet.get("status"),
        "table_counts": table_counts,
        "view_counts": view_counts,
        "checks": checks,
        "errors": errors,
        "authority_boundary": {
            "read_only_validator": True,
            "db_mutation_allowed": False,
            "consumer_cutover_allowed_by_this_guard": False,
            "capital_or_execution_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--schema-packet", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    schema = args.schema_packet if args.schema_packet.is_absolute() else ROOT / args.schema_packet
    result = build(db, schema)
    if args.write:
        atomic_write_json(OUT, result)
    print(json.dumps({"status": result["status"], "errors": len(result["errors"]), "written": [rel(OUT)] if args.write else []}, indent=2))
    return 1 if args.validate and result["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
