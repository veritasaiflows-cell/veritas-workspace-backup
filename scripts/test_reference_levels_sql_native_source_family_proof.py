from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reference_levels_sql_native_source_family_proof import build_proof


def init_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE securities (
            ticker TEXT PRIMARY KEY,
            active INTEGER NOT NULL
        );
        CREATE TABLE reference_levels (
            ticker TEXT PRIMARY KEY,
            reference_price_low REAL,
            reference_price_high REAL,
            reference_invalidation_level REAL,
            reference_confidence INTEGER,
            reference_band_status TEXT,
            source_artifact_path TEXT,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            fallback_rule TEXT,
            authority_class TEXT,
            raw_json TEXT
        );
        CREATE TABLE source_lineage (
            scope_key TEXT,
            field_name TEXT,
            field_family TEXT,
            source_artifact_path TEXT,
            source_generated_at_utc TEXT,
            source_status TEXT,
            validator_status TEXT,
            authority_class TEXT,
            fallback_rule TEXT
        );
        CREATE TABLE source_artifacts (
            artifact_path TEXT PRIMARY KEY,
            artifact_role TEXT,
            exists_on_disk INTEGER,
            sha256 TEXT,
            generated_at_utc TEXT,
            validator_status TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def insert_reference(conn: sqlite3.Connection, ticker: str, source: str) -> None:
    conn.execute(
        """
        INSERT INTO securities (ticker, active) VALUES (?, 1)
        """,
        (ticker,),
    )
    conn.execute(
        """
        INSERT INTO reference_levels (
            ticker, reference_price_low, reference_price_high,
            reference_invalidation_level, reference_confidence,
            reference_band_status, source_artifact_path, source_artifact_sha256,
            source_generated_at_utc, fallback_rule, authority_class, raw_json
        ) VALUES (?, 10.0, 12.0, 9.0, 3, 'IN_BAND', ?, 'hash',
                  '2026-06-21T00:00:00Z', 'fallback', 'review_only', '{}')
        """,
        (ticker, source),
    )


def insert_lineage(conn: sqlite3.Connection, ticker: str, source: str) -> None:
    for field in (
        "reference_price_low",
        "reference_price_high",
        "reference_invalidation_level",
    ):
        conn.execute(
            """
            INSERT INTO source_lineage (
                scope_key, field_name, field_family, source_artifact_path,
                source_generated_at_utc, source_status, validator_status,
                authority_class, fallback_rule
            ) VALUES (?, ?, 'reference_levels', ?, '2026-06-21T00:00:00Z',
                      'ok', 'ok', 'review_only', 'fallback')
            """,
            (ticker, field, source),
        )


def test_duplicate_old_lineage_does_not_hide_current_source(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    init_db(db)
    conn = sqlite3.connect(db)
    insert_reference(conn, "ACN", "tmp/current-source.json")
    insert_lineage(conn, "ACN", "tmp/old-source.json")
    insert_lineage(conn, "ACN", "tmp/current-source.json")
    conn.commit()
    conn.close()

    packet = build_proof(db)
    acn = next(row for row in packet["row_proofs"] if row["ticker"] == "ACN")

    assert "reference_row_source_not_in_price_lineage" not in acn["issues"]
    assert set(acn["price_lineage_sources"].values()) == {"tmp/current-source.json"}
    assert packet["status"] == "ok"
    assert packet["summary"]["sql_first_reference_provenance_clean"] is True
    assert packet["summary"]["row_issue_counts"] == {}
    assert packet["summary"]["non_blocking_readiness_gaps"] == []


def test_missing_current_source_lineage_is_metadata_residue(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    init_db(db)
    conn = sqlite3.connect(db)
    insert_reference(conn, "GOOG", "tmp/current-source.json")
    insert_lineage(conn, "GOOG", "tmp/old-source.json")
    conn.commit()
    conn.close()

    packet = build_proof(db)
    goog = next(row for row in packet["row_proofs"] if row["ticker"] == "GOOG")

    assert "reference_row_source_not_in_price_lineage" in goog["metadata_issues"]
    assert goog["issues"] == []
    assert packet["status"] == "ok"
    assert packet["summary"]["sql_first_reference_provenance_clean"] is True
    assert packet["summary"]["row_issue_counts"] == {}
    assert packet["summary"]["row_metadata_issue_counts"]["reference_row_source_not_in_price_lineage"] == 1


def test_active_tickers_without_reference_are_nonblocking_scaleout_gap(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    init_db(db)
    conn = sqlite3.connect(db)
    insert_reference(conn, "GOOG", "tmp/current-source.json")
    insert_lineage(conn, "GOOG", "tmp/current-source.json")
    conn.execute("INSERT INTO securities (ticker, active) VALUES ('NVDA', 1)")
    conn.commit()
    conn.close()

    packet = build_proof(db)

    assert packet["status"] == "ok"
    assert packet["summary"]["active_ticker_count"] == 2
    assert packet["summary"]["reference_row_count"] == 1
    assert packet["summary"]["active_without_reference_count"] == 1
    assert packet["summary"]["row_proof_count"] == 1
    assert packet["summary"]["non_blocking_readiness_gaps"] == ["active_tickers_without_reference_levels:1"]


def test_missing_price_lineage_still_blocks(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    init_db(db)
    conn = sqlite3.connect(db)
    insert_reference(conn, "GOOG", "tmp/current-source.json")
    conn.commit()
    conn.close()

    packet = build_proof(db)
    goog = next(row for row in packet["row_proofs"] if row["ticker"] == "GOOG")

    assert "missing_complete_price_field_lineage" in goog["issues"]
    assert packet["status"] == "blocked"
    assert packet["summary"]["sql_first_reference_provenance_clean"] is False
    assert packet["summary"]["row_issue_counts"]["missing_complete_price_field_lineage"] == 1
