"""Hermetic recovery drill tests; never restore or write the live canon."""
from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finance_sql_canon_recovery_drill as drill  # noqa: E402
from sqlite_snapshot import logical_sha256  # noqa: E402


def seed(db: Path, *, marker: bool = True) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("CREATE TABLE securities(ticker TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO securities VALUES ('NVDA')")
        conn.execute("CREATE TABLE universe_membership(ticker TEXT REFERENCES securities(ticker), tier TEXT)")
        conn.execute("INSERT INTO universe_membership VALUES ('NVDA','A')")
        conn.execute("CREATE TABLE reference_levels(ticker TEXT REFERENCES securities(ticker), low REAL)")
        conn.execute("INSERT INTO reference_levels VALUES ('NVDA',100.0)")
        conn.execute("CREATE TABLE source_lineage(ticker TEXT REFERENCES securities(ticker), source TEXT)")
        conn.execute("INSERT INTO source_lineage VALUES ('NVDA','fixture')")
        conn.execute("CREATE TABLE audit_events(event_type TEXT, detail TEXT)")
        if marker:
            conn.execute("INSERT INTO audit_events VALUES (?, 'test')", (drill.MIGRATION_MARKER,))


def test_copy_drill_captures_wal_and_recovers_after_fault(tmp_path, monkeypatch):
    source = tmp_path / "source.sqlite"
    seed(source)
    monkeypatch.setattr(drill, "DRILL_ROOT", tmp_path / "drills")
    before = logical_sha256(source)
    report = drill.run_drill(source, drill.DRILL_ROOT / "test-001")
    assert report["status"] == "ok_copy_only"
    assert report["authority"]["live_restore_allowed"] is False
    assert report["source_logical_sha256"] == before == logical_sha256(source)
    assert report["snapshot_logical_sha256"] == report["backup_logical_sha256"] == report["restored_logical_sha256"]
    assert report["fault_logical_sha256"] != before
    assert report["uncheckpointed_wal_visible"] is True
    assert report["main_file_unchanged_during_wal_fault"] is True
    assert report["wrong_hash_refused_without_change"] is True
    assert report["fault_removed_after_restore"] is True
    assert report["original_validation"] == report["restored_validation"]
    assert report["original_validation"]["table_counts"]["universe_membership"] == 1
    assert (drill.DRILL_ROOT / "test-001" / "report.json").exists()
    with pytest.raises(ValueError, match="exists"):
        drill.run_drill(source, drill.DRILL_ROOT / "test-001")


def test_drill_refuses_outside_path_or_missing_migration_marker(tmp_path, monkeypatch):
    source = tmp_path / "source.sqlite"
    seed(source, marker=False)
    monkeypatch.setattr(drill, "DRILL_ROOT", tmp_path / "drills")
    with pytest.raises(ValueError, match="unique child"):
        drill.run_drill(source, tmp_path / "outside")
    with pytest.raises(ValueError, match="migration_marker=0"):
        drill.run_drill(source, drill.DRILL_ROOT / "missing-marker")
    assert not (drill.DRILL_ROOT / "missing-marker" / "report.json").exists()


def test_readonly_source_snapshot_includes_uncheckpointed_wal(tmp_path, monkeypatch):
    source = tmp_path / "source-wal.sqlite"
    seed(source)
    monkeypatch.setattr(drill, "DRILL_ROOT", tmp_path / "drills")
    with closing(sqlite3.connect(source)) as setup:
        setup.execute("PRAGMA journal_mode=WAL")
    reader = sqlite3.connect(source)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM securities").fetchone()
        with closing(sqlite3.connect(source)) as writer:
            with writer:
                writer.execute("INSERT INTO securities VALUES ('WALONLY')")
        main_before = drill._sha256_file(source)
        report = drill.run_drill(source, drill.DRILL_ROOT / "wal-source")
        assert report["original_validation"]["table_counts"]["securities"] == 2
        assert report["restored_validation"]["table_counts"]["securities"] == 2
        assert report["source_logical_sha256"] == report["restored_logical_sha256"]
        assert drill._sha256_file(source) == main_before
    finally:
        reader.close()
