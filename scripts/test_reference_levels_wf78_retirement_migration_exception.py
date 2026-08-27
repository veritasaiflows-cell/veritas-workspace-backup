from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import reference_levels_wf78_retirement_migration_exception as packet


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
        INSERT INTO securities VALUES ('ACN', 1), ('GOOG', 1), ('NVDA', 1), ('GS', 1);
        INSERT INTO reference_levels VALUES (
            'ACN', NULL, NULL, NULL, NULL, NULL,
            'tmp/wf78-tier-weighted-freshness-resolution.json', 'oldhash',
            '2026-06-16T00:00:00Z',
            'fallback_to_wf78_tier_weighted_freshness_resolution_json_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'GOOG', 100.0, 110.0, 95.0, NULL, 'IN_BAND',
            'tmp/execution-board-canon-anchor-pilot.json', 'stale',
            '2026-06-18T00:00:00Z',
            'fallback_to_execution_board_anchor_preview_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'NVDA', 200.0, 210.0, 190.0, NULL, 'IN_BAND',
            'tmp/execution-board-canon-anchor-pilot.json', 'stale',
            '2026-06-18T00:00:00Z',
            'fallback_to_execution_board_anchor_preview_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'GS', 970.0, 1040.0, 928.0, NULL, 'NEAR_BAND',
            'tmp/band-proposals.json', 'bandhash',
            '2026-06-20T00:00:00Z',
            'fallback_to_band_proposals_or_owner_notes',
            'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        """
    )
    conn.commit()
    conn.close()


def targeted_payload() -> dict:
    return {
        "schema": "veritas.reference_levels_targeted_repair_packet.v1",
        "rows": [
            {
                "ticker": "ACN",
                "classification": packet.TARGET_CLASSIFICATION,
                "issues": ["numeric_reference_fields_incomplete"],
                "blockers": ["missing_band_context_repair_stop_line_blocks_direct_canon_or_sql_apply"],
            },
            {
                "ticker": "GOOG",
                "classification": "blocked_source_authority_or_reproducibility_required",
                "issues": ["reference_row_source_not_in_price_lineage"],
                "blockers": ["anchor_pilot_current_file_missing_ticker"],
            },
            {
                "ticker": "NVDA",
                "classification": "blocked_source_authority_or_reproducibility_required",
                "issues": ["reference_row_source_not_in_price_lineage"],
                "blockers": ["anchor_pilot_hash_mismatch_current_file_not_reproducible"],
            },
            {
                "ticker": "GS",
                "classification": "eligible_source_lineage_repair_dry_run_only",
                "issues": ["reference_row_source_not_in_price_lineage"],
                "blockers": [],
                "dry_run_lineage_updates": [{"field_name": "reference_price_low"}],
            },
        ],
    }


def missing_band_payload(*, complete: bool = True, unsafe: bool = False) -> dict:
    stop = 95.0 if complete else None
    return {
        "schema": "veritas.wf78_missing_band_context_repair.v1",
        "generated_at_utc": "2026-06-20T22:40:08Z",
        "status": "ok",
        "authority_boundary": {
            "review_only": True,
            "sql_canon_mutation_allowed": unsafe,
            "canon_or_portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "rows": [
            {
                "ticker": "ACN",
                "tier": "Tier B",
                "repair_status": "ready_for_decision_grade_band_context",
                "current_price": 90.0,
                "price_data_date": "2026-06-18",
                "price_source": "yfinance",
                "repair_applied": False,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "owner_approval_inferred": False,
                "band": {
                    "entry_band_low": 100.0,
                    "entry_band_high": 110.0,
                    "stop_or_invalidation": stop,
                    "band_status": "BELOW_STOP",
                    "source_timestamp": "2026-06-18",
                    "band_source": "review_only_technical_band_context",
                },
                "technical_band_context": {
                    "status": "ok",
                    "engine_version": "keltner-ma-v1",
                    "band": {
                        "band_confidence": 3,
                        "band_status": "BELOW_STOP",
                        "entry_band_low": 100.0,
                        "entry_band_high": 110.0,
                        "stop_or_invalidation": stop,
                    },
                },
            }
        ],
    }


def build(tmp_path: Path, *, complete: bool = True, unsafe: bool = False) -> dict:
    db = tmp_path / "finance-canon.sqlite"
    targeted = tmp_path / "targeted.json"
    missing = tmp_path / "missing.json"
    make_db(db)
    write_json(targeted, targeted_payload())
    write_json(missing, missing_band_payload(complete=complete, unsafe=unsafe))
    return packet.build_packet(
        db_path=db,
        targeted_packet_path=targeted,
        missing_band_context_path=missing,
        require_active_count=None,
        require_target_count=None,
    )


def test_builds_one_time_exception_without_permanent_wf78_authority(tmp_path: Path) -> None:
    result = build(tmp_path)

    assert result["status"] == "ready_for_owner_review"
    assert result["policy"]["permanent_source_authority"] is False
    assert result["summary"]["migration_exception_candidate_count"] == 1
    assert result["summary"]["source_lineage_rows_proposed"] == len(packet.LINEAGE_FIELDS)
    assert result["summary"]["sql_update_count"] == 0
    assert result["summary"]["registry_writer_allowed_now"] is False

    update = result["proposed_reference_level_updates"][0]
    proposed = update["proposed"]
    assert update["ticker"] == "ACN"
    assert proposed["reference_price_low"] == 100.0
    assert proposed["reference_price_high"] == 110.0
    assert proposed["reference_invalidation_level"] == 95.0
    assert proposed["reference_confidence"] == 3
    assert proposed["source_artifact_path"] == packet.SOURCE_PATH
    assert proposed["fallback_rule"] == packet.FALLBACK_RULE


def test_goog_nvda_are_separate_source_authority_decisions(tmp_path: Path) -> None:
    result = build(tmp_path)

    assert set(result["migration_exception_tickers"]) == {"ACN"}
    decisions = {row["ticker"]: row for row in result["source_authority_decisions"]}
    assert set(decisions) == {"GOOG", "NVDA"}
    assert all(row["migration_exception_in_scope"] is False for row in decisions.values())
    assert result["lineage_only_out_of_scope"][0]["ticker"] == "GS"


def test_incomplete_missing_band_source_blocks_packet(tmp_path: Path) -> None:
    result = build(tmp_path, complete=False)

    assert result["status"] == "blocked"
    assert "ACN:source_row_incomplete_low_high_stop" in result["validation"]["errors"]
    assert result["summary"]["migration_exception_candidate_count"] == 0


def test_unsafe_source_authority_blocks_packet(tmp_path: Path) -> None:
    result = build(tmp_path, unsafe=True)

    assert result["status"] == "blocked"
    assert any(
        error.startswith("unsafe_missing_band_context_authority:authority_boundary.sql_canon_mutation_allowed")
        for error in result["validation"]["errors"]
    )
