#!/usr/bin/env python3
"""Focused regression tests for the finance_sql_canon.py rebuild guards (2026-09-27).

Covers the two rebuild-integrity fixes and the migrated-canon refusal, proven
first on temp copies of the live canon
(tmp/finance-sql-canon-rebuild-disposition-20260927/proof-{pre,post}.json):

1. disciplined_reference_levels rows survive a rebuild. DROP TABLE securities fires
   the table's ON DELETE CASCADE foreign key, so the row set is captured before the
   rebuild and restored after it, exactly like reference_levels/evidence_freshness.
2. A mid-rebuild failure rolls the whole rebuild back. create_schema must not use
   executescript() (which commits pending work and autocommits every DROP/CREATE);
   DDL and inserts share one explicit transaction.
3. A migrated canon is refused before report, backup, or database writes; direct
   build_db callers are refused too. Legacy candidates remain testable.

All tests run against throwaway SQLite files under pytest's tmp_path. They never
touch state/finance/finance-canon.sqlite and never mutate live artifacts.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import finance_sql_canon as fsc  # noqa: E402

# Mirrors the live migration-era DDL (verified against the live canon 2026-09-27):
# the ON DELETE CASCADE to securities is the hazard under test.
DRL_DDL = """
CREATE TABLE disciplined_reference_levels (
    ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
    disciplined_band_low REAL,
    disciplined_band_high REAL,
    disciplined_stop REAL,
    band_state TEXT NOT NULL,
    disciplined_levels_set_at TEXT,
    disciplined_level_trigger TEXT,
    disciplined_source_artifact_path TEXT NOT NULL,
    disciplined_source_sha256 TEXT,
    authority_class TEXT NOT NULL,
    prior_disciplined_json TEXT,
    inserted_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
)
"""

EXPECTED_OBJECTS = {
    "meta",
    "securities",
    "universe_membership",
    "source_artifacts",
    "evidence_status",
    "answer_path_scope",
    "validator_runs",
    "archive_candidates",
    "audit_events",
    "current_active_universe",
    "current_answer_path",
    "review_monitor_universe",
}


MIGRATION_MARKER_EVENT_TYPE = fsc.MIGRATION_MARKER_EVENT_TYPE


def _universe(*tickers_and_tiers):
    return {
        "entries": [
            {
                "ticker": ticker,
                "active": True,
                "tier": tier,
                "universe_scope": "active_internal_universe",
            }
            for ticker, tier in tickers_and_tiers
        ]
    }


def _configure(monkeypatch, db_path: Path, tmp_path: Path) -> None:
    # Point every writable surface at tmp_path. TMP is rebound so artifact reads
    # miss and resolve fail-closed, keeping the tests hermetic.
    monkeypatch.setattr(fsc, "DB_PATH", db_path)
    monkeypatch.setattr(fsc, "ARCHIVE_PLAN_PATH", tmp_path / "archive-plan.json")
    monkeypatch.setattr(fsc, "TMP", tmp_path)


def test_disciplined_reference_levels_survive_rebuild(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    universe = _universe(("NVDA", "A"), ("MSFT", "B"))
    fsc.build_db(universe, "focused-test", "seed-run")

    with sqlite3.connect(db) as conn:
        conn.execute(DRL_DDL)
        conn.execute(
            """
            INSERT INTO disciplined_reference_levels(
                ticker, band_state, disciplined_source_artifact_path,
                authority_class, inserted_at_utc, updated_at_utc
            ) VALUES ('NVDA', 'sentinel', 'test', 'sentinel', 't', 't')
            """
        )
        conn.commit()

    fsc.build_db(universe, "focused-test", "rebuild-run")

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT ticker, band_state FROM disciplined_reference_levels"
        ).fetchall()
    assert rows == [("NVDA", "sentinel")]


def test_disciplined_reference_levels_preserve_requires_ticker_column(tmp_path):
    # The preserve mechanism only restores tables with a ticker column; this pins
    # the contract the fix relies on instead of silently skipping the table.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE disciplined_reference_levels (id INTEGER PRIMARY KEY)")
    preserved = fsc.fetch_preserved_extension_rows(conn)
    assert preserved["disciplined_reference_levels"] == []


def test_mid_rebuild_failure_rolls_back_everything(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    universe = _universe(("NVDA", "A"), ("MSFT", "B"))
    fsc.build_db(universe, "focused-test", "seed-run")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) "
            "VALUES ('migration-marker', 't', ?, '{}')",
            ("legacy-audit-sentinel",),
        )
        conn.execute(DRL_DDL)
        conn.execute(
            "INSERT INTO disciplined_reference_levels("
            "ticker, band_state, disciplined_source_artifact_path, authority_class, "
            "inserted_at_utc, updated_at_utc) VALUES ('NVDA','sentinel','test','sentinel','t','t')"
        )
        conn.commit()

    def failing_insert_universe(conn, universe):
        conn.execute(
            "INSERT INTO securities(ticker, name, instrument_type, active) "
            "VALUES ('ZZZPROOF', 'Injected Failure', 'operating_company', 1)"
        )
        raise RuntimeError("injected mid-rebuild failure")

    monkeypatch.setattr(fsc, "insert_universe", failing_insert_universe)
    with pytest.raises(RuntimeError, match="injected mid-rebuild failure"):
        fsc.build_db(universe, "focused-test", "doomed-run")

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM evidence_status").fetchone()[0] == 2
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type=?", ("legacy-audit-sentinel",)
        ).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM disciplined_reference_levels").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM securities WHERE ticker='ZZZPROOF'").fetchone()[0] == 0


def test_create_schema_opens_one_transaction_and_keeps_objects(tmp_path):
    db = tmp_path / "fresh.sqlite"
    conn = sqlite3.connect(db)
    fsc.create_schema(conn)
    # DDL must sit inside one still-open transaction (no executescript autocommit).
    assert conn.in_transaction
    conn.commit()
    objects = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        )
    }
    conn.close()
    assert EXPECTED_OBJECTS <= objects


def test_create_schema_refuses_trailing_incomplete_sql(tmp_path, monkeypatch):
    # Fail closed if the schema script ever ends mid-statement instead of
    # silently building a partial canon.
    monkeypatch.setattr(fsc, "SCHEMA_SQL", "DROP VIEW IF EXISTS current_active_universe;\nCREATE TABLE meta (")
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError, match="incomplete statement"):
        fsc.create_schema(conn)


def test_migrated_report_refuses_before_any_writes(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    monkeypatch.setattr(fsc, "STATE", tmp_path)
    monkeypatch.setattr(fsc, "REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(fsc, "UNIVERSE_PATH", tmp_path / "universe.json")
    monkeypatch.setattr(fsc, "BACKUPS", tmp_path / "backups")
    universe = _universe(("NVDA", "A"))
    fsc.build_db(universe, "focused-test", "seed-run")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) "
            "VALUES ('migration-marker', 't', ?, '{}')",
            (MIGRATION_MARKER_EVENT_TYPE,),
        )
    fsc.UNIVERSE_PATH.write_text('{"sentinel":true}', encoding="utf-8")
    before = db.read_bytes()
    archive_before = fsc.ARCHIVE_PLAN_PATH.read_bytes()

    with pytest.raises(RuntimeError, match="Refusing legacy whole-canon rebuild"):
        fsc.build_report("any-reference", write=True)

    assert db.read_bytes() == before
    assert fsc.UNIVERSE_PATH.read_text(encoding="utf-8") == '{"sentinel":true}'
    assert not fsc.REPORT_PATH.exists()
    assert not fsc.BACKUPS.exists()
    assert fsc.ARCHIVE_PLAN_PATH.read_bytes() == archive_before
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT tier FROM universe_membership WHERE ticker='NVDA'").fetchone()[0] == "A"
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type=?", (MIGRATION_MARKER_EVENT_TYPE,)).fetchone()[0] == 1


def test_direct_builder_refuses_migrated_canon(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    universe = _universe(("NVDA", "A"))
    fsc.build_db(universe, "focused-test", "seed-run")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) "
            "VALUES ('migration-marker', 't', ?, '{}')",
            (MIGRATION_MARKER_EVENT_TYPE,),
        )
    before = db.read_bytes()
    with pytest.raises(RuntimeError, match="Refusing legacy whole-canon rebuild"):
        fsc.build_db(universe, "any-reference", "blocked-run")
    assert db.read_bytes() == before


def test_same_connection_recheck_refuses_after_preflight(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    universe = _universe(("NVDA", "A"))
    fsc.build_db(universe, "focused-test", "seed-run")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) "
            "VALUES ('migration-marker', 't', ?, '{}')",
            (MIGRATION_MARKER_EVENT_TYPE,),
        )
    before = db.read_bytes()
    # Simulate a marker committed after the first check: the builder's own
    # connection must still refuse before PRAGMAs or DDL.
    monkeypatch.setattr(fsc, "preflight_rebuild_target", lambda: None)
    with pytest.raises(RuntimeError, match="Refusing legacy whole-canon rebuild"):
        fsc.build_db(universe, "any-reference", "blocked-run")
    assert db.read_bytes() == before


def test_malformed_migration_ledger_refuses_rebuild(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE audit_events(event_id TEXT)")
    with pytest.raises(sqlite3.OperationalError, match="event_type"):
        fsc.build_db(_universe(("NVDA", "A")), "any-reference", "blocked-run")


def test_uncheckpointed_wal_migration_marker_refuses(tmp_path, monkeypatch):
    db = tmp_path / "canon.sqlite"
    _configure(monkeypatch, db, tmp_path)
    universe = _universe(("NVDA", "A"))
    fsc.build_db(universe, "focused-test", "seed-run")
    with sqlite3.connect(db) as setup:
        setup.execute("PRAGMA journal_mode=WAL")
    # Pin a reader so the marker remains in the WAL, not the main DB file.
    with sqlite3.connect(db) as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM audit_events").fetchone()
        with sqlite3.connect(db) as writer:
            writer.execute(
                "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) "
                "VALUES ('migration-marker', 't', ?, '{}')",
                (MIGRATION_MARKER_EVENT_TYPE,),
            )
        assert db.with_name(db.name + "-wal").exists()
        with pytest.raises(RuntimeError, match="Refusing legacy whole-canon rebuild"):
            fsc.preflight_rebuild_target()
        with pytest.raises(RuntimeError, match="Refusing legacy whole-canon rebuild"):
            fsc.build_db(universe, "any-reference", "blocked-run")
