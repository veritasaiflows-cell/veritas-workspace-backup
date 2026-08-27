#!/usr/bin/env python3
"""Guard the SQL-canon consumer migration registry against backlog drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, backup_sqlite_database


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-consumer-registry-guard.json"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"
BACKUP_ROOT = ROOT / "backups" / "sql-canon-consumer-registry-sync"

ALLOWED_CUTOVER_STATES = {
    "not_cut_over",
    "sql_shadow",
    "sql_shadow_validated",
    "sql_primary",
    "sql_primary_guarded",
    "blocked",
    "source_producer",
    "archived",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect_rw(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backup_db(db: Path, backup_root: Path, run_id: str) -> dict[str, Any]:
    backup_path = backup_sqlite_database(db, backup_root / run_id / "finance-canon.sqlite")
    return {
        "path": rel(backup_path),
        "sha256": sha256_file(backup_path),
        "rollback": f"Restore {rel(backup_path)} over {rel(db)} only after closing SQL consumers and receiving explicit rollback instruction.",
    }


def migration_lane_for(item: dict[str, Any]) -> str:
    consumer_type = str(item.get("consumer_type") or "")
    if consumer_type == "production_or_answer_path_consumer":
        return "answer_path_parity_lane"
    if consumer_type == "finance_routing_or_freshness_consumer":
        return "wf78_wf77_routing_lane"
    if consumer_type == "cron_or_governance_consumer":
        return "cron_pm_governance_lane"
    if consumer_type == "pm_cockpit_consumer":
        return "pm_cockpit_lane"
    if consumer_type == "WF75_internal_product_consumer":
        return "wf75_product_lane"
    if consumer_type == "test_or_parity_consumer":
        return "test_parity_lane"
    if consumer_type == "source_producer_or_loader":
        return "source_loader_lane"
    return "typed_access_guard_lane"


def advisory_missing_registry_item(item: dict[str, Any]) -> bool:
    """Test-only parity consumers should not force a DB write during closeout."""
    return (
        item.get("consumer_type") == "test_or_parity_consumer"
        and str(item.get("priority") or "") not in {"P0", "P1"}
        and not bool(item.get("raw_sql_needs_review"))
        and not bool(item.get("requires_parity_before_cutover"))
    )


def sync_registry(db: Path, backlog: Path, backup_root: Path) -> dict[str, Any]:
    run_id = f"consumer-registry-sync-{stamp()}"
    payload = load_json(backlog)
    items = [item for item in payload.get("items", []) if isinstance(item, dict) and item.get("path")]
    if payload.get("status") != "ready":
        return {"status": "blocked", "errors": [f"backlog_not_ready:{payload.get('status')}"], "applied": False}
    if not db.exists():
        return {"status": "blocked", "errors": [f"db_missing:{rel(db)}"], "applied": False}

    backup = backup_db(db, backup_root, run_id)
    inserted_at = utc_now()
    backlog_hash = sha256_file(backlog)
    inserted = 0
    updated = 0
    with connect_rw(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for item in items:
                consumer_path = str(item.get("path") or "")
                existing = conn.execute(
                    "SELECT cutover_state, raw_sql_needs_review FROM consumer_migration_registry WHERE consumer_path=?",
                    (consumer_path,),
                ).fetchone()
                cutover_state = str(existing["cutover_state"]) if existing else "not_cut_over"
                raw_sql_needs_review = (
                    int(existing["raw_sql_needs_review"])
                    if existing
                    else int(bool(item.get("raw_sql_needs_review")))
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO consumer_migration_registry(
                        consumer_path, consumer_type, priority, migration_lane, cutover_state,
                        fallback_required, parity_required, raw_sql_needs_review,
                        source_artifact_path, source_artifact_sha256, registered_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        consumer_path,
                        str(item.get("consumer_type") or "unknown"),
                        str(item.get("priority") or "P3"),
                        migration_lane_for(item),
                        cutover_state,
                        int(item.get("fallback_required") is not False),
                        int(bool(item.get("requires_parity_before_cutover"))),
                        raw_sql_needs_review,
                        rel(backlog),
                        backlog_hash,
                        inserted_at,
                    ),
                )
                if existing:
                    updated += 1
                else:
                    inserted += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA optimize")

    return {
        "status": "ok",
        "applied": True,
        "run_id": run_id,
        "backup": backup,
        "backlog_sha256": backlog_hash,
        "inserted_count": inserted,
        "updated_count": updated,
        "total_backlog_items": len(items),
    }


def build(db: Path, backlog: Path, sync_result: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    backlog_payload = load_json(backlog)
    items = [item for item in backlog_payload.get("items", []) if isinstance(item, dict)]
    item_by_path = {str(item.get("path")): item for item in items if item.get("path")}
    if not db.exists():
        add("db_exists", False, rel(db))
        return payload(checks, db, backlog, {}, {}, [], warnings=warnings)

    with connect_ro(db) as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM consumer_migration_registry ORDER BY consumer_path")]

    row_by_path = {str(row["consumer_path"]): row for row in rows}
    missing = sorted(set(item_by_path) - set(row_by_path))
    advisory_missing = sorted(path for path in missing if advisory_missing_registry_item(item_by_path[path]))
    blocking_missing = sorted(path for path in missing if path not in set(advisory_missing))
    extra = sorted(set(row_by_path) - set(item_by_path))
    mismatch: list[dict[str, Any]] = []
    for path, item in item_by_path.items():
        row = row_by_path.get(path)
        if not row:
            continue
        for field in ["priority", "consumer_type"]:
            if str(row.get(field)) != str(item.get(field)):
                mismatch.append({"path": path, "field": field, "db": row.get(field), "backlog": item.get(field)})
        if row.get("migration_lane") == "":
            mismatch.append({"path": path, "field": "migration_lane", "db": row.get("migration_lane"), "backlog": "nonempty"})

    state_counts = Counter(str(row.get("cutover_state")) for row in rows)
    priority_counts = Counter(str(row.get("priority")) for row in rows)
    lane_counts = Counter(str(row.get("migration_lane")) for row in rows)
    invalid_states = sorted(state for state in state_counts if state not in ALLOWED_CUTOVER_STATES)
    expected_p0_count = sum(1 for item in items if item.get("priority") == "P0")
    p0_not_tracked = [
        row["consumer_path"]
        for row in rows
        if row.get("priority") == "P0" and row.get("migration_lane") != "answer_path_parity_lane"
    ]
    missing_fallback = [row["consumer_path"] for row in rows if int(row.get("fallback_required") or 0) != 1]

    add("backlog_present", backlog_payload.get("status") == "ready", backlog_payload.get("status"))
    if advisory_missing:
        warnings.append(
            "advisory_missing_test_or_parity_registry_rows:"
            + ",".join(advisory_missing[:20])
        )
    historical_notes: list[str] = []
    if extra:
        historical_notes.append(
            "historical_extra_registry_rows_retained:"
            + ",".join(extra[:20])
        )
    add(
        "all_blocking_backlog_items_registered",
        not blocking_missing,
        {
            "missing": blocking_missing[:20],
            "advisory_missing": advisory_missing[:20],
            "extra": extra[:20],
            "missing_count": len(blocking_missing),
            "advisory_missing_count": len(advisory_missing),
            "extra_count": len(extra),
        },
    )
    add("registry_fields_match_backlog", not mismatch, mismatch[:20])
    add("cutover_states_valid", not invalid_states, invalid_states)
    add(
        "p0_answer_path_lane_exact",
        priority_counts.get("P0", 0) == expected_p0_count and not p0_not_tracked,
        {"P0": priority_counts.get("P0"), "expected_P0": expected_p0_count, "bad": p0_not_tracked},
    )
    add("fallback_required_for_all", not missing_fallback, missing_fallback[:20])
    add("lane_split_present", {"answer_path_parity_lane", "source_loader_lane", "test_parity_lane"}.issubset(set(lane_counts)), dict(lane_counts))

    return payload(checks, db, backlog, dict(priority_counts), dict(lane_counts), rows, sync_result or {}, warnings=warnings, review_notes=historical_notes)


def payload(
    checks: list[dict[str, Any]],
    db: Path,
    backlog: Path,
    priority_counts: dict[str, int],
    lane_counts: dict[str, int],
    rows: list[dict[str, Any]],
    sync_result: dict[str, Any],
    warnings: list[str] | None = None,
    review_notes: list[str] | None = None,
) -> dict[str, Any]:
    warnings = warnings or []
    review_notes = review_notes or []
    errors = [check for check in checks if not check["ok"]]
    status = "ok" if not errors else "blocked"
    return {
        "schema_version": "sql_canon_consumer_registry_guard.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "db": rel(db),
        "backlog": rel(backlog),
        "registry_count": len(rows),
        "priority_counts": priority_counts,
        "lane_counts": lane_counts,
        "cutover_state_counts": dict(Counter(str(row.get("cutover_state")) for row in rows)),
        "checks": checks,
        "errors": errors,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
        "review_notes": review_notes,
        "sync_result": sync_result,
        "authority_boundary": {
            "read_only_validator": not bool(sync_result.get("applied")),
            "consumer_registry_sync_path": True,
            "consumer_registry_mutation_performed": bool(sync_result.get("applied")),
            "consumer_file_mutation_allowed": False,
            "archive_delete_allowed": False,
            "capital_or_execution_authority": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    parser.add_argument("--sync-db", action="store_true", help="Apply a narrow consumer_migration_registry sync from the backlog.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    backlog = args.backlog if args.backlog.is_absolute() else ROOT / args.backlog
    backup_root = args.backup_root if args.backup_root.is_absolute() else ROOT / args.backup_root
    sync_result = sync_registry(db, backlog, backup_root) if args.sync_db else {}
    result = build(db, backlog, sync_result)
    if args.write:
        atomic_write_json(OUT, result)
    print(json.dumps({
        "status": result["status"],
        "errors": len(result["errors"]),
        "sync_applied": bool(sync_result.get("applied")),
        "written": [rel(OUT)] if args.write else [],
    }, indent=2))
    return 1 if args.validate and (result["status"] != "ok" or sync_result.get("status") == "blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
