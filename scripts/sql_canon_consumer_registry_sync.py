#!/usr/bin/env python3
"""Synchronize SQL-canon consumer registry metadata from the backlog.

This is a narrow registry maintenance tool. It inserts backlog consumers that
are missing from ``consumer_migration_registry`` and, when explicitly requested,
refreshes existing registry metadata from the current backlog classification.
It does not change consumer code, retire fallbacks, change answer behavior,
mutate schema, archive files, or grant finance authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, backup_sqlite_database


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"
DEFAULT_OUT = ROOT / "tmp" / "sql-canon-consumer-registry-sync.json"
BACKUP_DIR = ROOT / "backups" / "finance-sql-canon-migration"

AUTHORITY_BOUNDARY = {
    "registry_insert_allowed": True,
    "registry_metadata_refresh_allowed": True,
    "cutover_state_refresh_allowed": False,
    "consumer_files_modified": False,
    "consumer_behavior_changed": False,
    "fallback_retirement_allowed": False,
    "source_feeder_retirement_allowed": False,
    "archive_delete_allowed": False,
    "schema_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backup_db(source: Path, timestamp: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_ts = timestamp.replace(":", "").replace("-", "").replace("Z", "Z")
    backup = BACKUP_DIR / f"finance-canon-consumer-registry-sync-{safe_ts}.sqlite"
    return backup_sqlite_database(source, backup)


def migration_lane_for(item: dict[str, Any]) -> str:
    consumer_type = item.get("consumer_type")
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


def default_state_for(item: dict[str, Any]) -> str:
    consumer_type = item.get("consumer_type")
    if consumer_type == "source_producer_or_loader":
        return "source_producer"
    if consumer_type == "test_or_parity_consumer" and not item.get("raw_sql_needs_review") and not item.get("requires_parity_before_cutover"):
        return "sql_primary_guarded"
    return "not_cut_over"


def backlog_items(backlog: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(backlog)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return {str(item.get("path")): item for item in items if isinstance(item, dict) and item.get("path")}


def read_registered(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row["consumer_path"])
        for row in conn.execute("SELECT consumer_path FROM consumer_migration_registry")
    }


def registry_state_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        str(row["cutover_state"]): int(row["count"])
        for row in conn.execute(
            "SELECT cutover_state, COUNT(*) AS count FROM consumer_migration_registry GROUP BY cutover_state"
        )
    }


def desired_metadata_for(item: dict[str, Any], backlog_path: Path, backlog_hash: str | None, timestamp: str) -> dict[str, Any]:
    return {
        "consumer_type": str(item.get("consumer_type") or "unknown"),
        "priority": str(item.get("priority") or "P3"),
        "migration_lane": migration_lane_for(item),
        "fallback_required": int(item.get("fallback_required") is not False),
        "parity_required": int(bool(item.get("requires_parity_before_cutover"))),
        "raw_sql_needs_review": int(bool(item.get("raw_sql_needs_review"))),
        "source_artifact_path": rel(backlog_path),
        "source_artifact_sha256": backlog_hash,
        "registered_at_utc": timestamp,
    }


def raw_sql_review_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute("SELECT COUNT(*) FROM consumer_migration_registry WHERE raw_sql_needs_review != 0").fetchone()[0]
    )


def build_payload(db_path: Path, backlog_path: Path, *, apply: bool, refresh_metadata: bool) -> dict[str, Any]:
    timestamp = utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    if not db_path.exists():
        errors.append(f"db_missing:{rel(db_path)}")
    items = backlog_items(backlog_path)
    if not items:
        errors.append(f"backlog_empty_or_missing:{rel(backlog_path)}")

    backup_path: Path | None = None
    missing_rows: list[dict[str, Any]] = []
    state_before: dict[str, int] = {}
    state_after: dict[str, int] = {}
    registered_after = 0
    raw_sql_review_before = 0
    raw_sql_review_after = 0
    metadata_updates: list[dict[str, Any]] = []
    backlog_hash = sha256_file(backlog_path)

    if not errors:
        with closing(connect(db_path)) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok":
                errors.append(f"integrity_check:{integrity}")
            if fk_issues:
                errors.append(f"foreign_key_issues:{len(fk_issues)}")
            registered = read_registered(conn)
            state_before = registry_state_counts(conn)
            raw_sql_review_before = raw_sql_review_count(conn)
            if refresh_metadata:
                existing_rows = {
                    str(row["consumer_path"]): dict(row)
                    for row in conn.execute(
                        """
                        SELECT consumer_path, consumer_type, priority, migration_lane,
                               fallback_required, parity_required, raw_sql_needs_review,
                               source_artifact_path, source_artifact_sha256
                        FROM consumer_migration_registry
                        """
                    )
                }
        missing_paths = sorted(set(items) - registered)
        for path in missing_paths:
            item = items[path]
            desired = desired_metadata_for(item, backlog_path, backlog_hash, timestamp)
            missing_rows.append(
                {
                    "consumer_path": path,
                    "consumer_type": desired["consumer_type"],
                    "priority": desired["priority"],
                    "migration_lane": desired["migration_lane"],
                    "cutover_state": default_state_for(item),
                    "fallback_required": desired["fallback_required"],
                    "parity_required": desired["parity_required"],
                    "raw_sql_needs_review": desired["raw_sql_needs_review"],
                }
            )
        if not missing_rows:
            warnings.append("no_missing_registry_rows")
        if refresh_metadata:
            for path in sorted(set(items) & registered):
                item = items[path]
                desired = desired_metadata_for(item, backlog_path, backlog_hash, timestamp)
                current = existing_rows.get(path) or {}
                comparable_fields = {
                    "consumer_type",
                    "priority",
                    "migration_lane",
                    "fallback_required",
                    "parity_required",
                    "raw_sql_needs_review",
                    "source_artifact_path",
                    "source_artifact_sha256",
                }
                changed_fields = [
                    key
                    for key, desired_value in desired.items()
                    if key in comparable_fields and current.get(key) != desired_value
                ]
                if changed_fields:
                    metadata_updates.append(
                        {
                            "consumer_path": path,
                            "changed_fields": changed_fields,
                            **desired,
                        }
                    )
            if not metadata_updates:
                warnings.append("no_registry_metadata_updates")

    if apply and not errors and (missing_rows or metadata_updates):
        backup_path = backup_db(db_path, timestamp)
        with closing(connect(db_path)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            for row in missing_rows:
                conn.execute(
                    """
                    INSERT INTO consumer_migration_registry(
                        consumer_path, consumer_type, priority, migration_lane, cutover_state,
                        fallback_required, parity_required, raw_sql_needs_review,
                        source_artifact_path, source_artifact_sha256, registered_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["consumer_path"],
                        row["consumer_type"],
                        row["priority"],
                        row["migration_lane"],
                        row["cutover_state"],
                        row["fallback_required"],
                        row["parity_required"],
                        row["raw_sql_needs_review"],
                        rel(backlog_path),
                        backlog_hash,
                        timestamp,
                    ),
                )
            if refresh_metadata:
                for row in metadata_updates:
                    conn.execute(
                        """
                        UPDATE consumer_migration_registry
                        SET consumer_type=?,
                            priority=?,
                            migration_lane=?,
                            fallback_required=?,
                            parity_required=?,
                            raw_sql_needs_review=?,
                            source_artifact_path=?,
                            source_artifact_sha256=?,
                            registered_at_utc=?
                        WHERE consumer_path=?
                        """,
                        (
                            row["consumer_type"],
                            row["priority"],
                            row["migration_lane"],
                            row["fallback_required"],
                            row["parity_required"],
                            row["raw_sql_needs_review"],
                            row["source_artifact_path"],
                            row["source_artifact_sha256"],
                            row["registered_at_utc"],
                            row["consumer_path"],
                        ),
                    )
            conn.execute(
                """
                INSERT OR REPLACE INTO migration_validation_runs(
                    run_id, run_time_utc, validator_name, status, artifact_path, detail_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"sql-canon-consumer-registry-sync-{timestamp}",
                    timestamp,
                    "sql_canon_consumer_registry_sync",
                    "ok",
                    rel(DEFAULT_OUT),
                    json.dumps(
                        {
                            "inserted_count": len(missing_rows),
                            "updated_count": len(metadata_updates) if refresh_metadata else 0,
                            "refresh_metadata": refresh_metadata,
                            "backup_path": rel(backup_path),
                            "authority_boundary": AUTHORITY_BOUNDARY,
                        },
                        sort_keys=True,
                    ),
                ),
            )
            conn.commit()

    if not errors:
        with closing(connect(db_path)) as conn:
            state_after = registry_state_counts(conn)
            registered_after = len(read_registered(conn))
            raw_sql_review_after = raw_sql_review_count(conn)
            missing_after = sorted(set(items) - read_registered(conn))
            if apply and missing_after:
                errors.append("missing_after_apply:" + ",".join(missing_after[:20]))
            integrity_after = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_after = conn.execute("PRAGMA foreign_key_check").fetchall()
            if integrity_after != "ok":
                errors.append(f"post_integrity_check:{integrity_after}")
            if fk_after:
                errors.append(f"post_foreign_key_issues:{len(fk_after)}")

    status = "ok" if not errors else "blocked"
    return {
        "schema": "veritas.sql_canon_consumer_registry_sync.v1",
        "generated_at_utc": timestamp,
        "status": status,
        "apply_requested": apply,
        "db": rel(db_path),
        "backlog": rel(backlog_path),
        "backup_path": rel(backup_path) if backup_path else None,
        "backlog_count": len(items),
        "registered_after_count": registered_after,
        "refresh_metadata_requested": refresh_metadata,
        "missing_before_count": len(missing_rows),
        "inserted_count": len(missing_rows) if apply and status == "ok" else 0,
        "metadata_update_before_count": len(metadata_updates),
        "updated_count": len(metadata_updates) if apply and refresh_metadata and status == "ok" else 0,
        "metadata_updates": metadata_updates,
        "missing_rows": missing_rows,
        "missing_by_type": dict(sorted(Counter(row["consumer_type"] for row in missing_rows).items())),
        "missing_by_state": dict(sorted(Counter(row["cutover_state"] for row in missing_rows).items())),
        "state_counts_before": state_before,
        "state_counts_after": state_after,
        "raw_sql_review_before_count": raw_sql_review_before,
        "raw_sql_review_after_count": raw_sql_review_after,
        "validation": {"status": status, "critical_errors": errors, "warnings": warnings},
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-metadata", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    backlog = args.backlog if args.backlog.is_absolute() else ROOT / args.backlog
    payload = build_payload(db, backlog, apply=args.apply, refresh_metadata=args.refresh_metadata)
    if args.write:
        atomic_write_json(DEFAULT_OUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "apply_requested": payload["apply_requested"],
                "refresh_metadata_requested": payload["refresh_metadata_requested"],
                "missing_before_count": payload["missing_before_count"],
                "inserted_count": payload["inserted_count"],
                "metadata_update_before_count": payload["metadata_update_before_count"],
                "updated_count": payload["updated_count"],
                "raw_sql_review_before_count": payload["raw_sql_review_before_count"],
                "raw_sql_review_after_count": payload["raw_sql_review_after_count"],
                "missing_by_type": payload["missing_by_type"],
                "missing_by_state": payload["missing_by_state"],
                "backup_path": payload["backup_path"],
                "validation": payload["validation"],
                "written": [rel(DEFAULT_OUT)] if args.write else [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
