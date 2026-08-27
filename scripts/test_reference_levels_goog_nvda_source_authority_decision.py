from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import reference_levels_goog_nvda_source_authority_decision as packet


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def make_db(path: Path) -> None:
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
            lineage_id TEXT PRIMARY KEY,
            scope TEXT,
            scope_key TEXT,
            field_family TEXT,
            field_name TEXT,
            source_artifact_path TEXT,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            source_status TEXT,
            validator_status TEXT,
            authority_class TEXT,
            fallback_rule TEXT,
            inserted_at_utc TEXT
        );
        INSERT INTO securities VALUES ('GOOG', 1), ('NVDA', 1);
        INSERT INTO reference_levels VALUES (
            'GOOG', 354.25, 369.69, 341.07, NULL, 'inside_band',
            'tmp/execution-board-canon-anchor-pilot.json', 'stale_hash',
            '2026-06-18',
            'fallback_to_execution_board_anchor_preview_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'NVDA', 202.81, 212.23, 192.95, NULL, 'inside_band',
            'tmp/execution-board-canon-anchor-pilot.json', 'stale_hash',
            '2026-06-18',
            'fallback_to_execution_board_anchor_preview_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        """
    )
    for ticker in packet.TICKERS:
        for field in packet.PRICE_FIELDS:
            conn.execute(
                """
                INSERT INTO source_lineage VALUES (
                    ?, 'ticker', ?, 'reference_levels', ?,
                    '03. Portfolio/Execution Board.md', 'old_board_hash', '2026-06-16',
                    'ok', 'ok', 'reference_metadata_review_only_no_deployment_authority',
                    'fallback_to_finance_intelligence_state_entry_stop_reference_or_owner_notes',
                    '2026-06-16T00:00:00Z'
                )
                """,
                (f"ticker|{ticker}|reference_levels|{field}", ticker, field),
            )
    conn.commit()
    conn.close()


def targeted_payload() -> dict:
    return {
        "schema": "veritas.reference_levels_targeted_repair_packet.v1",
        "rows": [
            {"ticker": "GOOG", "classification": "blocked_source_authority_or_reproducibility_required"},
            {"ticker": "NVDA", "classification": "blocked_source_authority_or_reproducibility_required"},
        ],
    }


def band_payload(*, goog_matches: bool = True) -> dict:
    goog_low = 354.25 if goog_matches else 354.20
    return {
        "schema": "band-proposals",
        "generated_at_utc": "2026-06-20T05:20:20Z",
        "proposals": [
            {
                "ticker": "GOOG",
                "current_band_low": goog_low,
                "current_band_high": 369.69,
                "current_stop": 341.07,
                "suggested_band_low": 354.24,
                "suggested_band_high": 369.69,
                "suggested_stop": 341.03,
                "band_status": "IN_BAND",
                "band_confidence": 4,
                "canonical_apply_eligible": True,
                "needs_review": False,
                "workflow_state": "ALMOST",
                "data_date": "2026-06-18",
            },
            {
                "ticker": "NVDA",
                "current_band_low": 202.81,
                "current_band_high": 212.23,
                "current_stop": 192.95,
                "suggested_band_low": 202.81,
                "suggested_band_high": 212.23,
                "suggested_stop": 192.95,
                "band_status": "IN_BAND",
                "band_confidence": 4,
                "canonical_apply_eligible": True,
                "needs_review": False,
                "workflow_state": "ALMOST",
                "data_date": "2026-06-18",
            },
        ],
    }


def build(tmp_path: Path, *, goog_matches: bool = True) -> dict:
    db = tmp_path / "finance-canon.sqlite"
    targeted = tmp_path / "targeted.json"
    band = tmp_path / "band.json"
    anchor = tmp_path / "anchor.json"
    make_db(db)
    write_json(targeted, targeted_payload())
    write_json(band, band_payload(goog_matches=goog_matches))
    write_json(anchor, {"anchors": []})
    return packet.build_packet(
        db_path=db,
        targeted_packet_path=targeted,
        band_proposals_path=band,
        anchor_pilot_path=anchor,
        require_active_count=None,
    )


def test_recommends_band_proposals_current_values_for_both_tickers(tmp_path: Path) -> None:
    result = build(tmp_path)

    assert result["status"] == "ready_for_owner_review"
    assert result["summary"]["recommended_source_artifact_path"] == packet.SOURCE_PATH
    assert result["summary"]["reference_metadata_update_count"] == 2
    assert result["summary"]["source_lineage_rows_proposed"] == 6
    assert result["summary"]["numeric_rewrite_count"] == 0
    assert result["summary"]["sql_update_count"] == 0
    assert all(row["recommended_source"]["current_values_match_sql_reference"] for row in result["decisions"])


def test_rejects_stale_anchor_for_both_tickers(tmp_path: Path) -> None:
    result = build(tmp_path)

    for row in result["decisions"]:
        rejection = row["stale_anchor_rejection"]
        assert rejection["status"] == "rejected_current_anchor_packet_not_reproducible"
        assert "current_anchor_packet_missing_ticker" in rejection["reasons"]
        assert "current_anchor_hash_differs_from_sql_row_source_hash" in rejection["reasons"]


def test_blocks_when_current_band_values_do_not_match_sql_reference(tmp_path: Path) -> None:
    result = build(tmp_path, goog_matches=False)

    assert result["status"] == "blocked"
    assert "GOOG:band_proposals_current_values_do_not_match_sql_reference" in result["validation"]["errors"]


def test_proposed_update_changes_metadata_only_not_numeric_values(tmp_path: Path) -> None:
    result = build(tmp_path)
    goog = next(row for row in result["decisions"] if row["ticker"] == "GOOG")
    before = goog["proposed_reference_metadata_update"]["before"]
    proposed = goog["proposed_reference_metadata_update"]["proposed"]

    for field in packet.PRICE_FIELDS:
        assert proposed[field] == before[field]
    assert proposed["source_artifact_path"] == packet.SOURCE_PATH
    assert proposed["fallback_rule"] == packet.FALLBACK_RULE
