from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import reference_levels_derived_refresh_apply as apply_ref


def make_db(path: Path) -> None:
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
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            fallback_rule TEXT NOT NULL,
            authority_class TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE TABLE source_lineage (
            lineage_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            field_family TEXT NOT NULL,
            field_name TEXT NOT NULL,
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            source_status TEXT,
            validator_status TEXT,
            authority_class TEXT NOT NULL,
            fallback_rule TEXT NOT NULL,
            inserted_at_utc TEXT NOT NULL
        );
        INSERT INTO reference_levels VALUES (
            'VRT', 80.0, 90.0, 70.0, NULL, 'OLD',
            'old.json', 'oldhash', '2026-06-17T00:00:00Z',
            'old_fallback', 'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        INSERT INTO reference_levels VALUES (
            'GS', 500.0, 520.0, 480.0, NULL, 'OLD',
            'old.json', 'oldhash', '2026-06-17T00:00:00Z',
            'old_fallback', 'reference_metadata_review_only_no_deployment_authority', '{}'
        );
        """
    )
    conn.commit()
    conn.close()


def write_changes(path: Path, *, unsafe: bool = False) -> None:
    payload = {
        "applied_date": "2026-06-18",
        "authority": {
            "capital_action_allowed": False,
            "owner_approval_inferred": unsafe,
        },
        "applied": [
            {
                "ticker": "VRT",
                "old_low": 80.0,
                "old_high": 90.0,
                "old_stop": 70.0,
                "new_low": 95.0,
                "new_high": 105.0,
                "new_stop": 88.0,
                "method": "KELTNER_PRIMARY",
                "band_status": "NEAR_BAND",
                "close": 94.5,
                "data_date": "2026-06-18",
                "coverage_lane": "test",
                "workflow_state": "test",
                "reasons": ["unit test"],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_source(path: Path) -> None:
    path.write_text(json.dumps({"generated_at_utc": "2026-06-18T21:00:00Z"}), encoding="utf-8")


def read_row(db_path: Path, ticker: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM reference_levels WHERE ticker=?", (ticker,)).fetchone())
    conn.close()
    return row


def run_payload(tmp_path: Path, *, apply: bool, unsafe: bool = False) -> dict:
    db = tmp_path / "finance-canon.sqlite"
    changes = tmp_path / "auto-band-apply.json"
    source = tmp_path / "band-proposals.json"
    make_db(db)
    write_changes(changes, unsafe=unsafe)
    write_source(source)
    return apply_ref.build_payload(
        db_path=db,
        changes_path=changes,
        source_path=source,
        out_path=tmp_path / "result.json",
        rollback_path=tmp_path / "rollback.json",
        rollback_drill_path=tmp_path / "rollback-drill.json",
        backup_root=tmp_path / "backups",
        apply=apply,
    )


def test_dry_run_does_not_mutate_sqlite(tmp_path: Path) -> None:
    payload = run_payload(tmp_path, apply=False)
    db = tmp_path / "finance-canon.sqlite"
    row = read_row(db, "VRT")

    assert payload["status"] == "ready_for_apply"
    assert payload["apply_executed"] is False
    assert row["reference_price_low"] == 80.0
    assert payload["validation"]["status"] == "ok"
    assert "dry_run_no_sql_write_performed" in payload["validation"]["warnings"]


def test_apply_updates_only_requested_ticker_and_writes_rollback(tmp_path: Path) -> None:
    payload = run_payload(tmp_path, apply=True)
    db = tmp_path / "finance-canon.sqlite"
    vrt = read_row(db, "VRT")
    gs = read_row(db, "GS")

    assert payload["status"] == "ok"
    assert payload["apply_executed"] is True
    assert payload["backup"]["path"]
    assert payload["rollback_drill_status"] == "ok"
    assert vrt["reference_price_low"] == 95.0
    assert vrt["reference_price_high"] == 105.0
    assert vrt["reference_invalidation_level"] == 88.0
    assert vrt["source_artifact_path"] == "tmp/band-proposals.json"
    assert gs["reference_price_low"] == 500.0
    assert payload["authority"]["capital_deployment_allowed"] is False
    assert payload["authority"]["owner_approval_inferred"] is False


def test_repair_packet_apply_updates_reference_and_source_lineage(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    source = tmp_path / "wf78-missing-band-context-repair.json"
    repair = tmp_path / "repair.json"
    make_db(db)
    source.write_text(json.dumps({"generated_at_utc": "2026-06-20T22:40:08Z"}), encoding="utf-8")
    repair.write_text(
        json.dumps(
            {
                "status": "ready_for_owner_review",
                "validation": {"status": "ok"},
                "proposed_reference_level_updates": [
                    {
                        "ticker": "VRT",
                        "proposed": {
                            "ticker": "VRT",
                            "reference_price_low": 95.0,
                            "reference_price_high": 105.0,
                            "reference_invalidation_level": 88.0,
                            "reference_confidence": 4,
                            "reference_band_status": "NEAR_BAND",
                            "source_artifact_path": "tmp/wf78-missing-band-context-repair.json",
                            "source_artifact_sha256": "hash",
                            "source_generated_at_utc": "2026-06-20T22:40:08Z",
                            "fallback_rule": "legacy_wf78_band_context_migration_exception_audit_fallback_only",
                            "authority_class": "reference_metadata_review_only_no_deployment_authority",
                            "raw_json": "{}",
                        },
                        "source_lineage_rows": [
                            {
                                "lineage_id": "reference_levels:VRT:reference_price_low:test",
                                "scope": "ticker",
                                "scope_key": "VRT",
                                "field_family": "reference_levels",
                                "field_name": "reference_price_low",
                                "source_artifact_path": "tmp/wf78-missing-band-context-repair.json",
                                "source_artifact_sha256": "hash",
                                "source_generated_at_utc": "2026-06-20T22:40:08Z",
                                "source_status": "ok_review_only_migration_exception",
                                "validator_status": "ok",
                                "authority_class": "reference_metadata_review_only_no_deployment_authority",
                                "fallback_rule": "legacy_wf78_band_context_migration_exception_audit_fallback_only",
                                "inserted_at_utc": "<apply_time_utc>",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = apply_ref.build_payload(
        db_path=db,
        changes_path=tmp_path / "unused-auto-band-apply.json",
        source_path=source,
        out_path=tmp_path / "result.json",
        rollback_path=tmp_path / "rollback.json",
        rollback_drill_path=tmp_path / "rollback-drill.json",
        backup_root=tmp_path / "backups",
        apply=True,
        repair_packet_path=repair,
        expect_repair_count=1,
    )
    row = read_row(db, "VRT")
    conn = sqlite3.connect(db)
    lineage_count = conn.execute("SELECT COUNT(*) FROM source_lineage").fetchone()[0]
    conn.close()

    assert payload["status"] == "ok"
    assert payload["apply_executed"] is True
    assert payload["source_lineage_affected_count"] == 1
    assert payload["rollback_drill_status"] == "ok"
    assert row["reference_price_low"] == 95.0
    assert lineage_count == 1


def test_unsafe_request_authority_blocks(tmp_path: Path) -> None:
    payload = run_payload(tmp_path, apply=True, unsafe=True)
    row = read_row(tmp_path / "finance-canon.sqlite", "VRT")

    assert payload["status"] == "blocked"
    assert payload["apply_executed"] is False
    assert any("unsafe_changes_authority" in item for item in payload["validation"]["errors"])
    assert row["reference_price_low"] == 80.0
