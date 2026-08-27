#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

import sql_canon_consumer_registry_sync as sync


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def init_db(path: Path, backlog_path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE consumer_migration_registry(
                consumer_path TEXT PRIMARY KEY,
                consumer_type TEXT,
                priority TEXT,
                migration_lane TEXT,
                cutover_state TEXT,
                fallback_required INTEGER,
                parity_required INTEGER,
                raw_sql_needs_review INTEGER,
                source_artifact_path TEXT,
                source_artifact_sha256 TEXT,
                registered_at_utc TEXT
            );
            CREATE TABLE migration_validation_runs(
                run_id TEXT PRIMARY KEY,
                run_time_utc TEXT,
                validator_name TEXT,
                status TEXT,
                artifact_path TEXT,
                detail_json TEXT
            );
            """
        )
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
                "scripts/example_consumer.py",
                "test_or_parity_consumer",
                "P2",
                "test_parity_lane",
                "sql_primary_guarded",
                1,
                0,
                0,
                sync.rel(backlog_path),
                "stale-hash",
                "2026-06-01T00:00:00Z",
            ),
        )
        conn.commit()


def write_backlog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "ready",
                "items": [
                    {
                        "path": "scripts/example_consumer.py",
                        "consumer_type": "test_or_parity_consumer",
                        "priority": "P2",
                        "fallback_required": True,
                        "requires_parity_before_cutover": False,
                        "raw_sql_needs_review": False,
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "finance-canon.sqlite"
        backlog_path = root / "sql-canon-consumer-migration-backlog.json"
        write_backlog(backlog_path)
        init_db(db_path, backlog_path)
        current_hash = sync.sha256_file(backlog_path)

        dry_run = sync.build_payload(db_path, backlog_path, apply=False, refresh_metadata=True)
        expect(dry_run["status"] == "ok", f"dry run failed: {dry_run['validation']}")
        expect(dry_run["metadata_update_before_count"] == 1, "stale source hash should be a metadata update")
        changed_fields = set(dry_run["metadata_updates"][0]["changed_fields"])
        expect("source_artifact_sha256" in changed_fields, f"missing source hash change: {changed_fields}")

        applied = sync.build_payload(db_path, backlog_path, apply=True, refresh_metadata=True)
        expect(applied["status"] == "ok", f"apply failed: {applied['validation']}")
        expect(applied["updated_count"] == 1, f"expected one updated row: {applied['updated_count']}")
        with closing(sqlite3.connect(db_path)) as conn:
            stored = conn.execute(
                "SELECT source_artifact_sha256 FROM consumer_migration_registry WHERE consumer_path=?",
                ("scripts/example_consumer.py",),
            ).fetchone()[0]
        expect(stored == current_hash, f"stored hash {stored} != {current_hash}")

    print("sql_canon_consumer_registry_sync_tests_passed")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
