from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reference_levels_band_proposals_source_migration import build_packet


def init_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
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
        """
    )
    for ticker, low, high, stop, source in [
        ("GOOG", 354.25, 369.69, 341.07, "tmp/execution-board-canon-anchor-pilot.json"),
        ("GS", 971.53, 1048.14, 928.97, "tmp/band-proposals.json"),
        ("NVDA", 202.81, 212.23, 192.95, "tmp/execution-board-canon-anchor-pilot.json"),
        ("VRT", 300.02, 319.13, 276.97, "tmp/band-proposals.json"),
    ]:
        conn.execute(
            """
            INSERT INTO reference_levels VALUES (
                ?, ?, ?, ?, NULL, 'IN_BAND', ?, 'oldsha', '2026-06-18',
                'fallback', 'reference_metadata_review_only_no_deployment_authority', '{}'
            )
            """,
            (ticker, low, high, stop, source),
        )
    conn.commit()
    conn.close()


def write_band_proposals(path: Path, *, drift: bool = False) -> None:
    proposals = [
        {"ticker": "GOOG", "current_band_low": 354.26 if drift else 354.25, "current_band_high": 369.69, "current_stop": 341.07, "band_status": "IN_BAND", "band_confidence": 4},
        {"ticker": "GS", "current_band_low": 971.53, "current_band_high": 1048.14, "current_stop": 928.97, "band_status": "NEAR_BAND", "band_confidence": 4},
        {"ticker": "NVDA", "current_band_low": 202.81, "current_band_high": 212.23, "current_stop": 192.95, "band_status": "IN_BAND", "band_confidence": 4},
        {"ticker": "VRT", "current_band_low": 300.02, "current_band_high": 319.13, "current_stop": 276.97, "band_status": "NEAR_BAND", "band_confidence": 4},
    ]
    path.write_text(
        json.dumps(
            {
                "status": "ok",
                "generated_at_utc": "2026-06-20T05:20:20.318272+00:00",
                "proposals": proposals,
            }
        ),
        encoding="utf-8",
    )


def test_builds_ready_packet_for_matching_band_proposals(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    source = tmp_path / "band-proposals.json"
    init_db(db)
    write_band_proposals(source)

    packet = build_packet(db, source)

    assert packet["status"] == "ready_for_apply"
    assert packet["summary"]["reference_metadata_update_count"] == 2
    assert packet["summary"]["source_lineage_rows_proposed"] == 12
    assert packet["summary"]["numeric_rewrite_count"] == 0
    assert {row["ticker"] for row in packet["proposed_reference_level_updates"]} == {"GOOG", "GS", "NVDA", "VRT"}
    assert {row["source_artifact_path"] for row in packet["proposed_source_lineage_rows"]} == {"tmp/band-proposals.json"}


def test_blocks_when_band_proposals_value_does_not_match_sql(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    source = tmp_path / "band-proposals.json"
    init_db(db)
    write_band_proposals(source, drift=True)

    packet = build_packet(db, source)

    assert packet["status"] == "blocked"
    assert "GOOG:band_proposals_values_do_not_match_sql_reference" in packet["validation"]["errors"]
