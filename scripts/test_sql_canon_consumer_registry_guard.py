from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import sql_canon_consumer_registry_guard as guard


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE consumer_migration_registry (
            consumer_path TEXT PRIMARY KEY,
            consumer_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            migration_lane TEXT NOT NULL,
            cutover_state TEXT NOT NULL,
            fallback_required INTEGER NOT NULL,
            parity_required INTEGER NOT NULL,
            raw_sql_needs_review INTEGER NOT NULL,
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            registered_at_utc TEXT NOT NULL
        );
        INSERT INTO consumer_migration_registry VALUES (
            'scripts/sql_canon_answer_path_ab_harness.py',
            'source_producer_or_loader',
            'P1',
            'source_loader_lane',
            'sql_primary_guarded',
            1,
            0,
            1,
            'old-backlog.json',
            'oldhash',
            '2026-06-20T00:00:00Z'
        );
        """
    )
    conn.commit()
    conn.close()


def write_backlog(path: Path) -> None:
    payload = {
        "status": "ready",
        "items": [
            {
                "path": "scripts/sql_canon_answer_path_ab_harness.py",
                "consumer_type": "production_or_answer_path_consumer",
                "priority": "P0",
                "requires_parity_before_cutover": True,
                "fallback_required": True,
                "raw_sql_needs_review": False,
            },
            {
                "path": "scripts/new_consumer.py",
                "consumer_type": "test_or_parity_consumer",
                "priority": "P2",
                "requires_parity_before_cutover": False,
                "fallback_required": True,
                "raw_sql_needs_review": False,
            },
            {
                "path": "scripts/source_loader.py",
                "consumer_type": "source_producer_or_loader",
                "priority": "P1",
                "requires_parity_before_cutover": False,
                "fallback_required": True,
                "raw_sql_needs_review": False,
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_sync_registry_adds_missing_and_repairs_fields_while_preserving_cutover(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    backlog = tmp_path / "backlog.json"
    make_db(db)
    write_backlog(backlog)

    before = guard.build(db, backlog)
    sync = guard.sync_registry(db, backlog, tmp_path / "backups")
    after = guard.build(db, backlog, sync)

    assert before["status"] == "blocked"
    assert sync["status"] == "ok"
    assert sync["inserted_count"] == 2
    assert sync["updated_count"] == 1
    assert after["status"] == "ok"
    assert after["sync_result"]["applied"] is True

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = dict(
        conn.execute(
            "SELECT * FROM consumer_migration_registry WHERE consumer_path=?",
            ("scripts/sql_canon_answer_path_ab_harness.py",),
        ).fetchone()
    )
    conn.close()

    assert row["priority"] == "P0"
    assert row["consumer_type"] == "production_or_answer_path_consumer"
    assert row["migration_lane"] == "answer_path_parity_lane"
    assert row["cutover_state"] == "sql_primary_guarded"
    assert row["raw_sql_needs_review"] == 1


def test_sync_registry_blocks_when_backlog_not_ready(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    backlog = tmp_path / "backlog.json"
    make_db(db)
    backlog.write_text(json.dumps({"status": "blocked", "items": []}), encoding="utf-8")

    sync = guard.sync_registry(db, backlog, tmp_path / "backups")

    assert sync["status"] == "blocked"
    assert sync["applied"] is False


def test_build_warns_for_advisory_missing_test_consumer(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    backlog = tmp_path / "backlog.json"
    make_db(db)
    backlog.write_text(
        json.dumps(
            {
                "status": "ready",
                "items": [
                    {
                        "path": "scripts/sql_canon_answer_path_ab_harness.py",
                        "consumer_type": "source_producer_or_loader",
                        "priority": "P1",
                        "requires_parity_before_cutover": False,
                        "fallback_required": True,
                        "raw_sql_needs_review": True,
                    },
                    {
                        "path": "scripts/test_new_parity_guard.py",
                        "consumer_type": "test_or_parity_consumer",
                        "priority": "P2",
                        "requires_parity_before_cutover": False,
                        "fallback_required": True,
                        "raw_sql_needs_review": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = guard.build(db, backlog)

    assert result["status"] == "ok"
    assert result["validation"]["status"] == "ok"
    assert result["validation"]["warnings"] == [
        "advisory_missing_test_or_parity_registry_rows:scripts/test_new_parity_guard.py"
    ]
    registration = next(
        check
        for check in result["checks"]
        if check["name"] == "all_blocking_backlog_items_registered"
    )
    assert registration["ok"] is True
    assert registration["detail"]["missing_count"] == 0
    assert registration["detail"]["advisory_missing_count"] == 1


def test_build_records_historical_extra_registry_rows_as_review_notes(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    backlog = tmp_path / "backlog.json"
    make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO consumer_migration_registry VALUES (
            'scripts/retired_legacy_packet.py',
            'source_producer_or_loader',
            'P1',
            'source_loader_lane',
            'source_producer',
            1,
            0,
            0,
            'old-backlog.json',
            'oldhash',
            '2026-06-20T00:00:00Z'
        )
        """
    )
    conn.commit()
    conn.close()
    write_backlog(backlog)

    sync = guard.sync_registry(db, backlog, tmp_path / "backups")
    result = guard.build(db, backlog, sync)

    assert result["status"] == "ok"
    assert result["validation"]["status"] == "ok"
    assert result["validation"]["warnings"] == []
    assert any(
        note.startswith("historical_extra_registry_rows_retained:")
        for note in result["review_notes"]
    )
    registration = next(
        check
        for check in result["checks"]
        if check["name"] == "all_blocking_backlog_items_registered"
    )
    assert registration["ok"] is True
    assert registration["detail"]["missing_count"] == 0
    assert registration["detail"]["extra_count"] == 1
