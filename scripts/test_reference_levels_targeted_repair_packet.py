from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import reference_levels_targeted_repair_packet as packet


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
            scope_key TEXT,
            field_family TEXT,
            field_name TEXT,
            source_artifact_path TEXT,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            source_status TEXT,
            validator_status TEXT,
            fallback_rule TEXT,
            authority_class TEXT
        );
        INSERT INTO securities VALUES ('ACN', 1), ('GS', 1), ('NVDA', 1);
        INSERT INTO reference_levels VALUES (
            'ACN', NULL, NULL, NULL, NULL, NULL,
            'tmp/wf78-tier-weighted-freshness-resolution.json', 'wf78hash',
            '2026-06-20T00:00:00Z', 'fallback', 'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'GS', 971.53, 1048.14, 928.97, NULL, 'NEAR_BAND',
            'tmp/band-proposals.json', 'BAND_HASH_PLACEHOLDER',
            '2026-06-20T00:00:00Z', 'fallback_to_band_proposals_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'NVDA', 202.81, 212.23, 192.95, NULL, 'inside_band',
            'tmp/execution-board-canon-anchor-pilot.json', 'stale_anchor_hash',
            '2026-06-18', 'fallback_to_execution_board_anchor_preview_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        """
    )
    for ticker in ("ACN", "GS", "NVDA"):
        for field in packet.PRICE_FIELDS:
            source_path = (
                "tmp/wf78-tier-weighted-freshness-resolution.json"
                if ticker == "ACN"
                else "03. Portfolio/Execution Board.md"
            )
            conn.execute(
                """
                INSERT INTO source_lineage VALUES (
                    ?, 'reference_levels', ?, ?,
                    'boardhash', '2026-06-16', 'ok', 'ok',
                    'fallback_to_finance_intelligence_state_entry_stop_reference_or_owner_notes',
                    'reference_metadata_review_only_no_deployment_authority'
                )
                """,
                (ticker, field, source_path),
            )
    conn.commit()
    conn.close()


def update_gs_hash(db: Path, band_hash: str) -> None:
    conn = sqlite3.connect(db)
    conn.execute("UPDATE reference_levels SET source_artifact_sha256=? WHERE ticker='GS'", (band_hash,))
    conn.commit()
    conn.close()


def build(tmp_path: Path, *, missing_band_complete: bool = False) -> dict:
    db = tmp_path / "finance-canon.sqlite"
    wf78 = tmp_path / "wf78.json"
    finance_db = tmp_path / "finance-state.sqlite"
    band = tmp_path / "band-proposals.json"
    auto = tmp_path / "auto-band-apply.json"
    anchor = tmp_path / "anchor.json"
    missing_band = tmp_path / "missing-band.json"
    make_db(db)
    write_json(
        wf78,
        {
            "rows": [
                {
                    "ticker": "ACN",
                    "resolution_state": "resolved_to_owner_lineage_proposal_review",
                    "tier_c_monitor_reference_band_low": None,
                    "tier_c_monitor_reference_band_high": None,
                    "tier_c_monitor_reference_stop": None,
                }
            ]
        },
    )
    conn = sqlite3.connect(finance_db)
    conn.executescript(
        """
        CREATE TABLE entry_stop_reference (
            ticker TEXT,
            entry_band_low REAL,
            entry_band_high REAL,
            stop_or_invalidation REAL,
            freshness_status TEXT,
            validation_status TEXT,
            source_artifact_path TEXT,
            source_timestamp TEXT,
            owner_note_path TEXT
        );
        INSERT INTO entry_stop_reference VALUES (
            'ACN', NULL, NULL, NULL, 'missing_required_refresh',
            'thin_monitor_missing_required_evidence', NULL, NULL, 'owner.md'
        );
        """
    )
    conn.close()
    write_json(
        band,
        {
            "proposals": [
                {
                    "ticker": "GS",
                    "suggested_band_low": 971.53,
                    "suggested_band_high": 1048.14,
                    "suggested_stop": 928.97,
                }
            ]
        },
    )
    update_gs_hash(db, packet.sha256_file(band) or "")
    write_json(auto, {"applied": [{"ticker": "GS"}]})
    write_json(anchor, {"anchors": []})
    write_json(
        missing_band,
        {
            "rows": [
                {
                    "ticker": "ACN",
                    "repair_status": "ready_for_decision_grade_band_context",
                    "band": {
                        "entry_band_low": 100.0 if missing_band_complete else None,
                        "entry_band_high": 110.0 if missing_band_complete else None,
                        "stop_or_invalidation": 95.0 if missing_band_complete else None,
                    },
                }
            ]
        },
    )
    return packet.build_packet(
        db_path=db,
        wf78_path=wf78,
        finance_state_db=finance_db,
        band_proposals_path=band,
        auto_band_apply_path=auto,
        anchor_pilot_path=anchor,
        missing_band_context_path=missing_band,
    )


def build_clean(tmp_path: Path) -> dict:
    db = tmp_path / "finance-canon.sqlite"
    wf78 = tmp_path / "wf78.json"
    finance_db = tmp_path / "finance-state.sqlite"
    band = tmp_path / "band-proposals.json"
    auto = tmp_path / "auto-band-apply.json"
    anchor = tmp_path / "anchor.json"
    missing_band = tmp_path / "missing-band.json"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE securities (ticker TEXT PRIMARY KEY, active INTEGER NOT NULL);
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
            field_family TEXT,
            field_name TEXT,
            source_artifact_path TEXT,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            source_status TEXT,
            validator_status TEXT,
            fallback_rule TEXT,
            authority_class TEXT
        );
        INSERT INTO securities VALUES ('GS', 1);
        INSERT INTO reference_levels VALUES (
            'GS', 971.53, 1048.14, 928.97, NULL, 'NEAR_BAND',
            'tmp/band-proposals.json', 'bandhash', '2026-06-20T00:00:00Z',
            'fallback_to_band_proposals_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        """
    )
    for field in packet.PRICE_FIELDS:
        conn.execute(
            """
            INSERT INTO source_lineage VALUES (
                'GS', 'reference_levels', ?, 'tmp/band-proposals.json',
                'bandhash', '2026-06-20T00:00:00Z', 'ok', 'ok',
                'fallback_to_band_proposals_or_owner_notes',
                'reference_metadata_review_only_no_deployment_authority'
            )
            """,
            (field,),
        )
    conn.commit()
    conn.close()
    conn = sqlite3.connect(finance_db)
    conn.execute(
        """
        CREATE TABLE entry_stop_reference (
            ticker TEXT,
            entry_band_low REAL,
            entry_band_high REAL,
            stop_or_invalidation REAL,
            freshness_status TEXT,
            validation_status TEXT,
            source_artifact_path TEXT,
            source_timestamp TEXT,
            owner_note_path TEXT
        )
        """
    )
    conn.close()
    for path, payload in (
        (wf78, {"rows": []}),
        (band, {"proposals": []}),
        (auto, {"applied": []}),
        (anchor, {"anchors": []}),
        (missing_band, {"rows": []}),
    ):
        write_json(path, payload)
    return packet.build_packet(
        db_path=db,
        wf78_path=wf78,
        finance_state_db=finance_db,
        band_proposals_path=band,
        auto_band_apply_path=auto,
        anchor_pilot_path=anchor,
        missing_band_context_path=missing_band,
    )


def test_numeric_gap_blocks_without_complete_source(tmp_path: Path) -> None:
    result = build(tmp_path)
    acn = next(row for row in result["rows"] if row["ticker"] == "ACN")

    assert result["status"] == "blocked"
    assert acn["classification"] == "blocked_missing_numeric_source_evidence"
    assert "no_current_source_has_complete_low_high_stop" in acn["blockers"]
    assert result["summary"]["registry_writer_allowed_now"] is False


def test_clean_rows_allow_source_family_proof_to_pass(tmp_path: Path) -> None:
    result = build_clean(tmp_path)

    assert result["status"] == "ok"
    assert result["rows"] == []
    assert result["summary"]["sql_first_reference_provenance_clean"] is True
    assert result["summary"]["reference_source_family_proof_can_pass_now"] is True
    assert result["summary"]["registry_writer_allowed_now"] is False


def test_review_only_missing_band_context_still_blocks_apply_authority(tmp_path: Path) -> None:
    result = build(tmp_path, missing_band_complete=True)
    acn = next(row for row in result["rows"] if row["ticker"] == "ACN")

    assert acn["classification"] == "blocked_numeric_source_available_but_apply_authority_missing"
    assert "missing_band_context_repair_stop_line_blocks_direct_canon_or_sql_apply" in acn["blockers"]
    assert result["summary"]["dry_run_reference_update_count"] == 0


def test_band_proposal_mismatch_is_lineage_repair_candidate(tmp_path: Path) -> None:
    result = build(tmp_path)
    gs = next(row for row in result["rows"] if row["ticker"] == "GS")

    assert gs["classification"] == "eligible_source_lineage_repair_dry_run_only"
    assert len(gs["dry_run_lineage_updates"]) == 3
    assert result["summary"]["dry_run_source_lineage_update_count"] == 3


def test_stale_anchor_pilot_blocks_as_not_reproducible(tmp_path: Path) -> None:
    result = build(tmp_path)
    nvda = next(row for row in result["rows"] if row["ticker"] == "NVDA")

    assert nvda["classification"] == "blocked_source_authority_or_reproducibility_required"
    assert "anchor_pilot_current_file_missing_ticker" in nvda["blockers"]
    assert "anchor_pilot_hash_mismatch_current_file_not_reproducible" in nvda["blockers"]
