#!/usr/bin/env python3
"""Focused tests for production_scope_schema_retirement_plan."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from sqlite_snapshot import logical_sha256, wal_safe_restore

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "production_scope_schema_retirement_plan.py"

spec = importlib.util.spec_from_file_location("production_scope_schema_retirement_plan", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_desired_values_fail_closed_for_current_production_scope() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE universe_membership(
            ticker TEXT,
            universe_scope TEXT,
            tier TEXT,
            legacy_production_42 INTEGER,
            review_100_monitor INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO universe_membership VALUES('NVDA', 'production_current_42', 'A', 1, 0)"
    )
    row = conn.execute("SELECT * FROM universe_membership").fetchone()
    values = module.desired_values(row, set())
    assert values["production_scope_member"] == 0
    assert values["production_scope_source"] == "not_current_proof_joined_production_scope"
    assert values["tier_ab_decision_scope"] == "tier_a_review_scope"
    assert values["compatibility_reason"] == "archived_legacy_42_compatibility_alias_not_production_authority"


def test_validate_dry_run_does_not_require_columns() -> None:
    packet = {
        "apply": False,
        "authority_boundary": module.AUTHORITY_BOUNDARY,
        "schema_state": {
            "missing_columns": sorted(module.NEUTRAL_COLUMNS),
            "routing_view_missing_columns": sorted(module.NEUTRAL_COLUMNS),
        },
    }
    assert module.validate(packet) == []


def test_validate_apply_requires_neutral_columns() -> None:
    packet = {
        "apply": True,
        "authority_boundary": module.AUTHORITY_BOUNDARY,
        "schema_state": {
            "missing_columns": ["production_scope_member"],
            "routing_view_missing_columns": [],
            "integrity_check": "ok",
            "foreign_key_issue_count": 0,
        },
    }
    assert "neutral_columns_missing:['production_scope_member']" in module.validate(packet)


def test_manifest_and_restore_with_reader_pinned_wal(tmp_path, monkeypatch) -> None:
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE proof(value TEXT)")
        writer.execute("INSERT INTO proof VALUES ('before')")

    reader = sqlite3.connect(db)
    try:
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM proof").fetchone()[0] == 1
        main_sha_before = module.sha256(db)
        with sqlite3.connect(db) as writer:
            writer.execute("INSERT INTO proof VALUES ('committed-in-wal')")
        assert module.sha256(db) == main_sha_before
        assert Path(f"{db}-wal").exists()

        monkeypatch.setattr(module, "DB_PATH", db)
        monkeypatch.setattr(module, "BACKUPS", tmp_path / "backups")
        result = module.backup_db("isolated-run")
        manifest = json.loads((tmp_path / "backups" / "isolated-run" / "manifest.json").read_text())
        entry = manifest["files"][0]
        backup = tmp_path / "backups" / "isolated-run" / db.name
        assert result["files"] == manifest["files"]
        assert entry["sha256"] == main_sha_before
        assert entry["backup_sha256"] != main_sha_before
        assert entry["backup_logical_sha256"] == entry["logical_sha256_before"]
        assert logical_sha256(backup) == entry["backup_logical_sha256"]
        with sqlite3.connect(backup) as snapshot:
            assert [row[0] for row in snapshot.execute("SELECT value FROM proof ORDER BY rowid")] == [
                "before", "committed-in-wal"
            ]
        assert "owner approval" in entry["rollback"]
        assert "all readers and writers" in entry["rollback"]
        assert "wal_safe_restore" in entry["rollback"]
        assert "never a main-file replacement" in entry["rollback"]
        with pytest.raises(FileExistsError, match="backup run already exists"):
            module.backup_db("isolated-run")
        assert logical_sha256(backup) == entry["backup_logical_sha256"]
        assert json.loads((tmp_path / "backups" / "isolated-run" / "manifest.json").read_text()) == manifest
    finally:
        reader.close()

    with sqlite3.connect(db) as writer:
        writer.execute("INSERT INTO proof VALUES ('post-backup')")
    assert logical_sha256(db) != entry["backup_logical_sha256"]
    assert wal_safe_restore(backup, db, entry["backup_logical_sha256"]) == entry["backup_logical_sha256"]
    with sqlite3.connect(db) as restored:
        assert [row[0] for row in restored.execute("SELECT value FROM proof ORDER BY rowid")] == [
            "before", "committed-in-wal"
        ]


def test_mismatched_logical_backup_never_emits_manifest(tmp_path, monkeypatch) -> None:
    db = tmp_path / "source.sqlite"
    with sqlite3.connect(db) as writer:
        writer.execute("CREATE TABLE proof(value TEXT)")
        writer.execute("INSERT INTO proof VALUES ('source')")

    def wrong_backup(_source: Path, destination: Path) -> Path:
        with sqlite3.connect(destination) as other:
            other.execute("CREATE TABLE proof(value TEXT)")
            other.execute("INSERT INTO proof VALUES ('different')")
        return destination

    monkeypatch.setattr(module, "DB_PATH", db)
    monkeypatch.setattr(module, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(module, "backup_sqlite_database", wrong_backup)
    with pytest.raises(ValueError, match="logical SHA-256 mismatch"):
        module.backup_db("mismatch")
    assert not (tmp_path / "backups" / "mismatch" / "manifest.json").exists()

