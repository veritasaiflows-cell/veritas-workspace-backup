#!/usr/bin/env python3
"""Validate SQL-canon Phase 2 shadow backfill completeness and authority flags."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-shadow-backfill-validator.json"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_PLAN = ROOT / "tmp" / "sql-canon-migration-master-plan.json"
DEFAULT_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"


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


def count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def build(db: Path, master_plan: Path, backlog: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    plan = load_json(master_plan)
    backlog_payload = load_json(backlog)
    backlog_count = len(backlog_payload.get("items") or [])

    if not db.exists():
        add("db_exists", False, rel(db))
        return payload(checks, db, master_plan, backlog, {}, plan)

    with connect_ro(db) as conn:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"securities", "tier_routing_state", "reference_levels", "evidence_freshness", "source_lineage", "consumer_migration_registry"}
        missing = sorted(required - tables)
        add("required_backfill_tables_present", not missing, missing)
        if missing:
            return payload(checks, db, master_plan, backlog, {}, plan)
        counts = {
            table: count(conn, f'SELECT COUNT(*) FROM "{table}"')
            for table in sorted(required | {"authority_events", "migration_validation_runs", "archive_candidates"})
            if table in tables
        }
        forbidden = {
            "tier_routing_execution_flags": count(
                conn,
                """
                SELECT COUNT(*) FROM tier_routing_state
                WHERE capital_deployment_approved != 0 OR trade_or_execution_approved != 0
                """,
            ),
            "evidence_execution_customer_flags": count(
                conn,
                """
                SELECT COUNT(*) FROM evidence_status
                WHERE customer_output_allowed != 0 OR paper_or_live_execution_allowed != 0
                """,
            ),
            "archive_apply_enabled": count(conn, "SELECT COUNT(*) FROM archive_candidates WHERE archive_apply_allowed_now != 0"),
        }
        lineage_nulls = count(conn, "SELECT COUNT(*) FROM source_lineage WHERE source_artifact_sha256 IS NULL OR source_artifact_path=''")
        lineage_families = {
            str(row["field_family"]): int(row["count"])
            for row in conn.execute("SELECT field_family, COUNT(*) AS count FROM source_lineage GROUP BY field_family")
        }
        production_reference_nulls = count(
            conn,
            """
            SELECT COUNT(*)
            FROM current_sql_canon_routing AS routing
            JOIN reference_levels AS refs ON refs.ticker = routing.ticker
            WHERE routing.legacy_production_42 = 1
              AND routing.production_card_generation_allowed = 1
              AND (
                refs.reference_price_low IS NULL
                OR refs.reference_price_high IS NULL
                OR refs.reference_invalidation_level IS NULL
              )
            """,
        )
        registry_p0 = count(conn, "SELECT COUNT(*) FROM consumer_migration_registry WHERE priority='P0'")
        registry_p0_answer_path = count(conn, "SELECT COUNT(*) FROM consumer_migration_registry WHERE priority='P0' AND migration_lane='answer_path_parity_lane'")
        registry_answer_path_non_p0 = count(conn, "SELECT COUNT(*) FROM consumer_migration_registry WHERE priority!='P0' AND migration_lane='answer_path_parity_lane'")
        registry_p1 = count(conn, "SELECT COUNT(*) FROM consumer_migration_registry WHERE priority='P1'")

    add("master_plan_ok", plan.get("status") == "phase0_1_ready", plan.get("status"))
    add("backlog_loaded", counts.get("consumer_migration_registry") == backlog_count and backlog_count >= 400, {"db": counts.get("consumer_migration_registry"), "backlog": backlog_count})
    add("core_row_counts_match_200", all(counts.get(table) == 200 for table in ["securities", "tier_routing_state", "reference_levels", "evidence_freshness"]), counts)
    add("source_lineage_complete_enough", counts.get("source_lineage", 0) >= 3000 and lineage_nulls == 0, {"count": counts.get("source_lineage"), "nulls": lineage_nulls, "families": lineage_families})
    add("production_reference_levels_complete", production_reference_nulls == 0, {"null_production_references": production_reference_nulls})
    add(
        "consumer_registry_priorities_present",
        registry_p0 > 0 and registry_p0_answer_path == registry_p0 and registry_answer_path_non_p0 == 0 and registry_p1 >= 300,
        {"P0": registry_p0, "P0_answer_path": registry_p0_answer_path, "answer_path_non_P0": registry_answer_path_non_p0, "P1": registry_p1},
    )
    add("authority_false_flags_clean", all(value == 0 for value in forbidden.values()), forbidden)
    add("authority_event_and_validation_recorded", counts.get("authority_events", 0) >= 1 and counts.get("migration_validation_runs", 0) >= 1, counts)
    return payload(checks, db, master_plan, backlog, counts, plan)


def payload(
    checks: list[dict[str, Any]],
    db: Path,
    master_plan: Path,
    backlog: Path,
    counts: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"]]
    return {
        "schema_version": "sql_canon_shadow_backfill_validator.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "db": rel(db),
        "master_plan": rel(master_plan),
        "backlog": rel(backlog),
        "master_plan_status": plan.get("status"),
        "counts": counts,
        "checks": checks,
        "errors": errors,
        "authority_boundary": {
            "read_only_validator": True,
            "db_mutation_allowed": False,
            "consumer_cutover_allowed_by_this_validator": False,
            "capital_or_execution_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--master-plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    master = args.master_plan if args.master_plan.is_absolute() else ROOT / args.master_plan
    backlog = args.backlog if args.backlog.is_absolute() else ROOT / args.backlog
    result = build(db, master, backlog)
    if args.write:
        atomic_write_json(OUT, result)
    print(json.dumps({"status": result["status"], "errors": len(result["errors"]), "written": [rel(OUT)] if args.write else []}, indent=2))
    return 1 if args.validate and result["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
