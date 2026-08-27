#!/usr/bin/env python3
"""Phase 2 additive SQL-canon backfill.

This extends the existing ``state/finance/finance-canon.sqlite`` store with
the missing migration-state tables needed before consumer cutover. It does not
archive files, import new tickers, mutate portfolio Markdown, or grant capital,
paper/live execution, account, customer, or external-delivery authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, backup_sqlite_database


ROOT = Path(__file__).resolve().parents[1]
STATE_FINANCE = ROOT / "state" / "finance"
TMP = ROOT / "tmp"
BACKUPS = ROOT / "backups" / "finance-sql-canon-migration"
DB_PATH = STATE_FINANCE / "finance-canon.sqlite"

PHASE2_OUT = TMP / "sql-canon-phase2-backfill.json"
VALIDATION_OUT = TMP / "sql-canon-phase2-backfill-validation.json"

ROUTING_PATH = TMP / "wf78-auto-tier-routing.json"
FRESHNESS_PATH = TMP / "wf78-tier-weighted-freshness-resolution.json"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"
BACKLOG_PATH = TMP / "sql-canon-consumer-migration-backlog.json"
MASTER_PLAN_PATH = TMP / "sql-canon-migration-master-plan.json"
SCHEMA_PACKET_PATH = TMP / "sql-canon-schema-authority-packet.json"

APPROVAL_REFERENCE = {
    "source": "telegram",
    "message_id": "3336",
    "timestamp_mst": "2026-06-16 11:24:44",
    "summary": "Approved local SQL-canon finance-state migration and consumer migration.",
}

FALSE_AUTHORITY_FLAGS = {
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "real_customer_data_or_external_delivery_allowed": False,
    "portfolio_or_canon_markdown_mutation_allowed": False,
    "legacy_archive_move_performed": False,
    "ticker_import_performed": False,
    "owner_approval_inferred_for_capital_or_execution": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def source_state(path: Path) -> dict[str, Any]:
    payload = load_json(path, {}) or {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256(path),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "validation_status": (payload.get("validation") or {}).get("status")
        if isinstance(payload.get("validation"), dict)
        else None,
    }


def connect(write: bool = False) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(DB_PATH)
    else:
        uri = DB_PATH.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    if write:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def backup_db(run_id: str) -> dict[str, Any]:
    backup_dir = BACKUPS / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_sqlite_database(DB_PATH, backup_dir / "finance-canon.sqlite")
    copied: list[dict[str, Any]] = [
        {
            "path": rel(DB_PATH),
            "backup_path": rel(backup_path),
            "sha256": sha256(backup_path),
            "rollback": f"Restore {rel(backup_path)} over {rel(DB_PATH)} after closing SQL consumers.",
        }
    ]
    manifest = {
        "schema_version": "sql_canon_phase2_backup_manifest.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": {
            "backup_only": True,
            "delete_allowed": False,
            "archive_move_allowed": False,
            "capital_or_execution_authority": False,
        },
        "items": copied,
    }
    write_json(backup_dir / "manifest.json", manifest)
    return {"backup_dir": rel(backup_dir), "manifest": rel(backup_dir / "manifest.json"), "items": copied}


def create_phase2_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS current_sql_canon_routing;

        CREATE TABLE IF NOT EXISTS finance_state_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tier_routing_state (
            ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
            auto_tier TEXT,
            auto_state TEXT,
            route_reason TEXT,
            route_priority INTEGER,
            data_confidence_rating TEXT,
            fundamentals_confidence TEXT,
            tier_a_confidence_status TEXT,
            critical_data_conflict_count INTEGER,
            tier_c_attention_score REAL,
            tier_c_attention_next_action TEXT,
            capital_deployment_approved INTEGER NOT NULL CHECK(capital_deployment_approved IN (0, 1)),
            trade_or_execution_approved INTEGER NOT NULL CHECK(trade_or_execution_approved IN (0, 1)),
            requires_separate_capital_or_execution_approval INTEGER NOT NULL CHECK(requires_separate_capital_or_execution_approval IN (0, 1)),
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reference_levels (
            ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
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

        CREATE TABLE IF NOT EXISTS evidence_freshness (
            ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
            has_production_card INTEGER NOT NULL CHECK(has_production_card IN (0, 1)),
            card_path TEXT,
            provider_status TEXT,
            resolution_state TEXT,
            required_depth TEXT,
            card_generated_at_utc TEXT,
            card_missing_or_stale_count INTEGER,
            stale_families_json TEXT NOT NULL,
            source_confidence_class TEXT NOT NULL,
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            source_generated_at_utc TEXT,
            authority_class TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_lineage (
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

        CREATE TABLE IF NOT EXISTS consumer_migration_registry (
            consumer_path TEXT PRIMARY KEY,
            consumer_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            migration_lane TEXT NOT NULL,
            cutover_state TEXT NOT NULL,
            fallback_required INTEGER NOT NULL CHECK(fallback_required IN (0, 1)),
            parity_required INTEGER NOT NULL CHECK(parity_required IN (0, 1)),
            raw_sql_needs_review INTEGER NOT NULL CHECK(raw_sql_needs_review IN (0, 1)),
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            registered_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS authority_events (
            event_id TEXT PRIMARY KEY,
            event_time_utc TEXT NOT NULL,
            event_type TEXT NOT NULL,
            approval_source TEXT,
            approval_message_id TEXT,
            authority_boundary_json TEXT NOT NULL,
            detail_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS migration_validation_runs (
            run_id TEXT PRIMARY KEY,
            run_time_utc TEXT NOT NULL,
            validator_name TEXT NOT NULL,
            status TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            detail_json TEXT NOT NULL
        );

        CREATE VIEW IF NOT EXISTS current_sql_canon_routing AS
        SELECT s.ticker, s.name, s.instrument_type, s.sector, s.industry,
               u.universe_scope, u.tier AS legacy_tier,
               u.production_scope_member, u.production_scope_source,
               u.sql_tier, u.sql_tier_state, u.tier_decision_scope,
               t.auto_tier, t.auto_state, t.route_priority,
               e.has_production_card, e.provider_status,
               a.answer_scope, a.production_card_generation_allowed,
               r.reference_price_low, r.reference_price_high, r.reference_invalidation_level,
               r.reference_band_status, r.reference_confidence
        FROM securities s
        JOIN universe_membership u USING (ticker)
        LEFT JOIN tier_routing_state t USING (ticker)
        LEFT JOIN evidence_status e USING (ticker)
        LEFT JOIN evidence_freshness f USING (ticker)
        LEFT JOIN answer_path_scope a USING (ticker)
        LEFT JOIN reference_levels r USING (ticker)
        WHERE s.active = 1;
        """
    )


def clear_phase2_tables(conn: sqlite3.Connection) -> None:
    for table in [
        "tier_routing_state",
        "reference_levels",
        "evidence_freshness",
        "source_lineage",
    ]:
        conn.execute(f"DELETE FROM {table}")


def insert_lineage(
    conn: sqlite3.Connection,
    *,
    scope: str,
    scope_key: str,
    family: str,
    field: str,
    source: dict[str, Any],
    authority_class: str,
    fallback_rule: str,
    inserted_at: str,
) -> None:
    lineage_id = "|".join([scope, scope_key, family, field])
    conn.execute(
        """
        INSERT OR REPLACE INTO source_lineage(
            lineage_id, scope, scope_key, field_family, field_name, source_artifact_path,
            source_artifact_sha256, source_generated_at_utc, source_status, validator_status,
            authority_class, fallback_rule, inserted_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lineage_id,
            scope,
            scope_key,
            family,
            field,
            source["path"],
            source.get("sha256"),
            source.get("generated_at_utc"),
            source.get("status"),
            source.get("validation_status"),
            authority_class,
            fallback_rule,
            inserted_at,
        ),
    )


def backfill_routing(conn: sqlite3.Connection, inserted_at: str) -> int:
    payload = load_json(ROUTING_PATH, {}) or {}
    rows = as_rows(payload)
    source = source_state(ROUTING_PATH)
    count = 0
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO tier_routing_state(
                ticker, auto_tier, auto_state, route_reason, route_priority,
                data_confidence_rating, fundamentals_confidence, tier_a_confidence_status,
                critical_data_conflict_count, tier_c_attention_score, tier_c_attention_next_action,
                capital_deployment_approved, trade_or_execution_approved,
                requires_separate_capital_or_execution_approval, source_artifact_path,
                source_artifact_sha256, source_generated_at_utc, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                row.get("auto_tier"),
                row.get("auto_state"),
                row.get("route_reason"),
                row.get("route_priority"),
                row.get("data_confidence_rating"),
                row.get("fundamentals_confidence"),
                row.get("tier_a_confidence_status"),
                row.get("critical_data_conflict_count"),
                row.get("tier_c_attention_score"),
                row.get("tier_c_attention_next_action"),
                int(bool(row.get("capital_deployment_approved"))),
                int(bool(row.get("trade_or_execution_approved"))),
                int(row.get("requires_separate_capital_or_execution_approval") is not False),
                source["path"],
                source.get("sha256"),
                source.get("generated_at_utc"),
                json.dumps(row, sort_keys=True),
            ),
        )
        for field in ["auto_tier", "auto_state", "route_priority", "data_confidence_rating"]:
            insert_lineage(
                conn,
                scope="ticker",
                scope_key=ticker,
                family="tier_routing_state",
                field=field,
                source=source,
                authority_class="derived_non_capital_routing",
                fallback_rule="fallback_to_wf78_auto_tier_routing_json",
                inserted_at=inserted_at,
            )
        count += 1
    return count


def backfill_reference_levels(conn: sqlite3.Connection, inserted_at: str) -> int:
    payload = load_json(FRESHNESS_PATH, {}) or {}
    rows = as_rows(payload)
    source = source_state(FRESHNESS_PATH)
    count = 0
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        low = row.get("tier_c_monitor_reference_band_low")
        high = row.get("tier_c_monitor_reference_band_high")
        stop = row.get("tier_c_monitor_reference_stop")
        confidence = row.get("tier_c_monitor_confidence")
        band_status = row.get("tier_c_monitor_band_status")
        conn.execute(
            """
            INSERT OR REPLACE INTO reference_levels(
                ticker, reference_price_low, reference_price_high, reference_invalidation_level,
                reference_confidence, reference_band_status, source_artifact_path,
                source_artifact_sha256, source_generated_at_utc, fallback_rule,
                authority_class, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                low,
                high,
                stop,
                confidence,
                band_status,
                source["path"],
                source.get("sha256"),
                source.get("generated_at_utc"),
                "fallback_to_wf78_tier_weighted_freshness_resolution_json_or_owner_notes",
                "reference_metadata_review_only_no_deployment_authority",
                json.dumps(row, sort_keys=True),
            ),
        )
        for field in [
            "reference_price_low",
            "reference_price_high",
            "reference_invalidation_level",
            "reference_confidence",
            "reference_band_status",
        ]:
            insert_lineage(
                conn,
                scope="ticker",
                scope_key=ticker,
                family="reference_levels",
                field=field,
                source=source,
                authority_class="reference_metadata_review_only_no_deployment_authority",
                fallback_rule="fallback_to_wf78_tier_weighted_freshness_resolution_json_or_owner_notes",
                inserted_at=inserted_at,
            )
        count += 1
    if FINANCE_STATE_DB.exists():
        uri = FINANCE_STATE_DB.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as state_conn:
            state_conn.row_factory = sqlite3.Row
            state_conn.execute("PRAGMA busy_timeout=5000")
            state_conn.execute("PRAGMA foreign_keys=ON")
            state_rows = state_conn.execute(
                """
                SELECT *
                FROM entry_stop_reference
                WHERE entry_band_low IS NOT NULL
                   OR entry_band_high IS NOT NULL
                   OR stop_or_invalidation IS NOT NULL
                ORDER BY ticker
                """
            ).fetchall()
        for state_row in state_rows:
            row = dict(state_row)
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue
            state_source = {
                "path": row.get("source_artifact_path") or rel(FINANCE_STATE_DB),
                "exists": True,
                "sha256": row.get("source_artifact_hash") or sha256(FINANCE_STATE_DB),
                "status": row.get("validation_status"),
                "generated_at_utc": row.get("source_timestamp"),
                "validation_status": row.get("validation_status"),
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO reference_levels(
                    ticker, reference_price_low, reference_price_high, reference_invalidation_level,
                    reference_confidence, reference_band_status, source_artifact_path,
                    source_artifact_sha256, source_generated_at_utc, fallback_rule,
                    authority_class, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    row.get("entry_band_low"),
                    row.get("entry_band_high"),
                    row.get("stop_or_invalidation"),
                    None,
                    None,
                    state_source["path"],
                    state_source.get("sha256"),
                    state_source.get("generated_at_utc"),
                    "fallback_to_finance_intelligence_state_entry_stop_reference_or_owner_notes",
                    "reference_metadata_review_only_no_deployment_authority",
                    json.dumps({"finance_intelligence_state_entry_stop_reference": row}, sort_keys=True),
                ),
            )
            for field in [
                "reference_price_low",
                "reference_price_high",
                "reference_invalidation_level",
            ]:
                insert_lineage(
                    conn,
                    scope="ticker",
                    scope_key=ticker,
                    family="reference_levels",
                    field=field,
                    source=state_source,
                    authority_class="reference_metadata_review_only_no_deployment_authority",
                    fallback_rule="fallback_to_finance_intelligence_state_entry_stop_reference_or_owner_notes",
                    inserted_at=inserted_at,
                )
    return count


def backfill_evidence_freshness(conn: sqlite3.Connection, inserted_at: str) -> int:
    payload = load_json(FRESHNESS_PATH, {}) or {}
    rows = as_rows(payload)
    source = source_state(FRESHNESS_PATH)
    count = 0
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        existing = conn.execute(
            "SELECT has_production_card, card_path, provider_status FROM evidence_status WHERE ticker=?",
            (ticker,),
        ).fetchone()
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_freshness(
                ticker, has_production_card, card_path, provider_status, resolution_state,
                required_depth, card_generated_at_utc, card_missing_or_stale_count,
                stale_families_json, source_confidence_class, source_artifact_path,
                source_artifact_sha256, source_generated_at_utc, authority_class, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                int(existing["has_production_card"]) if existing else 0,
                existing["card_path"] if existing else None,
                existing["provider_status"] if existing else None,
                row.get("resolution_state"),
                row.get("required_depth"),
                row.get("card_generated_at_utc"),
                row.get("card_missing_or_stale_count"),
                json.dumps(row.get("stale_families") or [], sort_keys=True),
                "decision_or_monitor_freshness_metadata",
                source["path"],
                source.get("sha256"),
                source.get("generated_at_utc"),
                "machine_control_state_no_capital_authority",
                json.dumps(row, sort_keys=True),
            ),
        )
        for field in ["resolution_state", "required_depth", "card_generated_at_utc", "stale_families"]:
            insert_lineage(
                conn,
                scope="ticker",
                scope_key=ticker,
                family="evidence_freshness",
                field=field,
                source=source,
                authority_class="machine_control_state_no_capital_authority",
                fallback_rule="fallback_to_wf78_tier_weighted_freshness_resolution_json",
                inserted_at=inserted_at,
            )
        count += 1
    return count


def migration_lane_for(item: dict[str, Any]) -> str:
    consumer_type = item.get("consumer_type")
    if consumer_type == "production_or_answer_path_consumer":
        return "answer_path_parity_lane"
    if consumer_type == "finance_routing_or_freshness_consumer":
        return "wf78_wf77_routing_lane"
    if consumer_type == "cron_or_governance_consumer":
        return "cron_pm_governance_lane"
    if consumer_type == "pm_cockpit_consumer":
        return "pm_cockpit_lane"
    if consumer_type == "WF75_internal_product_consumer":
        return "wf75_product_lane"
    if consumer_type == "test_or_parity_consumer":
        return "test_parity_lane"
    if consumer_type == "source_producer_or_loader":
        return "source_loader_lane"
    return "typed_access_guard_lane"


def backfill_consumer_registry(conn: sqlite3.Connection, inserted_at: str) -> int:
    payload = load_json(BACKLOG_PATH, {}) or {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    source = source_state(BACKLOG_PATH)
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        consumer_path = str(item.get("path") or "")
        if not consumer_path:
            continue
        existing = conn.execute(
            "SELECT cutover_state, raw_sql_needs_review FROM consumer_migration_registry WHERE consumer_path=?",
            (consumer_path,),
        ).fetchone()
        cutover_state = str(existing["cutover_state"]) if existing else "not_cut_over"
        raw_sql_needs_review = int(existing["raw_sql_needs_review"]) if existing else int(bool(item.get("raw_sql_needs_review")))
        conn.execute(
            """
            INSERT OR REPLACE INTO consumer_migration_registry(
                consumer_path, consumer_type, priority, migration_lane, cutover_state,
                fallback_required, parity_required, raw_sql_needs_review,
                source_artifact_path, source_artifact_sha256, registered_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consumer_path,
                str(item.get("consumer_type") or "unknown"),
                str(item.get("priority") or "P3"),
                migration_lane_for(item),
                cutover_state,
                int(item.get("fallback_required") is not False),
                int(bool(item.get("requires_parity_before_cutover"))),
                raw_sql_needs_review,
                source["path"],
                source.get("sha256"),
                inserted_at,
            ),
        )
        insert_lineage(
            conn,
            scope="consumer",
            scope_key=consumer_path,
            family="consumer_migration_registry",
            field="cutover_state",
            source=source,
            authority_class="migration_control_state",
            fallback_rule="fallback_to_sql_canon_consumer_migration_backlog_json",
            inserted_at=inserted_at,
        )
        count += 1
    return count


def insert_authority_event(conn: sqlite3.Connection, inserted_at: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO authority_events(
            event_id, event_time_utc, event_type, approval_source, approval_message_id,
            authority_boundary_json, detail_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "telegram-3336-sql-canon-migration-approval",
            inserted_at,
            "owner_approved_local_sql_canon_migration",
            APPROVAL_REFERENCE["source"],
            APPROVAL_REFERENCE["message_id"],
            json.dumps(FALSE_AUTHORITY_FLAGS, sort_keys=True),
            json.dumps(APPROVAL_REFERENCE, sort_keys=True),
        ),
    )


def insert_validation_run(conn: sqlite3.Connection, inserted_at: str, status: str, detail: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO migration_validation_runs(
            run_id, run_time_utc, validator_name, status, artifact_path, detail_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            f"sql-canon-phase2-backfill-{inserted_at}",
            inserted_at,
            "sql_canon_phase2_backfill",
            status,
            rel(VALIDATION_OUT),
            json.dumps(detail, sort_keys=True),
        ),
    )


def set_meta(conn: sqlite3.Connection, key: str, value: Any, updated_at: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc) VALUES (?, ?, ?)",
        (key, json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value), updated_at),
    )


def db_counts() -> dict[str, int]:
    if not DB_PATH.exists():
        return {}
    with connect(write=False) as conn:
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if not str(row[0]).startswith("sqlite_")
        ]
        counts: dict[str, int] = {}
        for table in tables:
            counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        return counts


def validate_db() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if not DB_PATH.exists():
        add("db_exists", False, rel(DB_PATH))
        return {"status": "blocked", "checks": checks, "errors": ["db_missing"], "warnings": []}

    errors: list[str] = []
    warnings: list[str] = []
    with connect(write=False) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required_tables = {
            "finance_state_meta",
            "tier_routing_state",
            "reference_levels",
            "evidence_freshness",
            "source_lineage",
            "consumer_migration_registry",
            "authority_events",
            "migration_validation_runs",
        }
        missing_tables = sorted(required_tables - tables)
        add("required_phase2_tables_present", not missing_tables, missing_tables)
        if missing_tables:
            errors.append("missing_phase2_tables")
            return {"status": "blocked", "checks": checks, "errors": errors, "warnings": warnings}
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        securities = int(conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0])
        routing = int(conn.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0])
        references = int(conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
        freshness = int(conn.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0])
        backlog = int(conn.execute("SELECT COUNT(*) FROM consumer_migration_registry").fetchone()[0])
        p0 = int(conn.execute("SELECT COUNT(*) FROM consumer_migration_registry WHERE priority='P0'").fetchone()[0])
        false_flags = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM tier_routing_state
                WHERE capital_deployment_approved != 0
                   OR trade_or_execution_approved != 0
                """
            ).fetchone()[0]
        )
        authority_events = int(conn.execute("SELECT COUNT(*) FROM authority_events").fetchone()[0])
        validation_runs = int(conn.execute("SELECT COUNT(*) FROM migration_validation_runs").fetchone()[0])
        lineage = int(conn.execute("SELECT COUNT(*) FROM source_lineage").fetchone()[0])
        null_lineage_hashes = int(
            conn.execute("SELECT COUNT(*) FROM source_lineage WHERE source_artifact_sha256 IS NULL").fetchone()[0]
        )
        add("integrity_check_ok", integrity == "ok", integrity)
        add("foreign_key_check_ok", len(fk_rows) == 0, len(fk_rows))
        add("tier_routing_rows_match_securities", routing == securities == 200, {"routing": routing, "securities": securities})
        add("reference_level_rows_loaded", references == securities == 200, {"references": references, "securities": securities})
        add("evidence_freshness_rows_loaded", freshness == securities == 200, {"freshness": freshness, "securities": securities})
        p0_answer_path = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM consumer_migration_registry
                WHERE priority='P0' AND migration_lane='answer_path_parity_lane'
                """
            ).fetchone()[0]
        )
        answer_path_non_p0 = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM consumer_migration_registry
                WHERE priority!='P0' AND migration_lane='answer_path_parity_lane'
                """
            ).fetchone()[0]
        )
        add(
            "consumer_registry_backlog_loaded",
            backlog >= 400 and p0 > 0 and p0_answer_path == p0 and answer_path_non_p0 == 0,
            {"backlog": backlog, "p0": p0, "p0_answer_path": p0_answer_path, "answer_path_non_p0": answer_path_non_p0},
        )
        add("routing_execution_authority_false", false_flags == 0, false_flags)
        add("source_lineage_loaded", lineage >= routing + references, lineage)
        add("source_lineage_hashes_present", null_lineage_hashes == 0, null_lineage_hashes)
        add("authority_event_recorded", authority_events >= 1, authority_events)
        add("validation_run_recorded", validation_runs >= 1, validation_runs)
    for check in checks:
        if not check["ok"]:
            errors.append(check["name"])
    return {"status": "ok" if not errors else "blocked", "checks": checks, "errors": errors, "warnings": warnings}


def apply_backfill() -> dict[str, Any]:
    inserted_at = utc_now()
    run_id = "phase2-" + inserted_at.replace(":", "").replace("-", "").replace("T", "-").replace("Z", "Z")
    backup = backup_db(run_id)
    with connect(write=True) as conn:
        with conn:
            create_phase2_schema(conn)
            clear_phase2_tables(conn)
            routing_count = backfill_routing(conn, inserted_at)
            reference_count = backfill_reference_levels(conn, inserted_at)
            freshness_count = backfill_evidence_freshness(conn, inserted_at)
            registry_count = backfill_consumer_registry(conn, inserted_at)
            insert_authority_event(conn, inserted_at)
            set_meta(conn, "phase2_backfill_generated_at_utc", inserted_at, inserted_at)
            set_meta(conn, "phase2_backfill_approval_reference", APPROVAL_REFERENCE, inserted_at)
            set_meta(conn, "phase2_false_authority_flags", FALSE_AUTHORITY_FLAGS, inserted_at)
            interim = {
                "routing_count": routing_count,
                "reference_count": reference_count,
                "evidence_freshness_count": freshness_count,
                "consumer_registry_count": registry_count,
            }
            insert_validation_run(conn, inserted_at, "pending_post_commit_validation", interim)
        conn.execute("PRAGMA optimize")
    validation = validate_db()
    with connect(write=True) as conn:
        with conn:
            insert_validation_run(conn, inserted_at, validation["status"], validation)
    return {
        "applied": True,
        "backup": backup,
        "validation": validate_db(),
        "counts": db_counts(),
    }


def build_payload(apply_db: bool) -> dict[str, Any]:
    sources = {
        "routing": source_state(ROUTING_PATH),
        "freshness": source_state(FRESHNESS_PATH),
        "backlog": source_state(BACKLOG_PATH),
        "master_plan": source_state(MASTER_PLAN_PATH),
        "schema_packet": source_state(SCHEMA_PACKET_PATH),
    }
    source_errors = [
        name
        for name, state in sources.items()
        if not state["exists"] or state.get("status") in {"blocked", "error"}
    ]
    before_counts = db_counts()
    apply_result = apply_backfill() if apply_db and not source_errors else {"applied": False}
    validation = apply_result.get("validation") if apply_result.get("applied") else validate_db()
    status = "ok" if apply_result.get("applied") and validation.get("status") == "ok" else (
        "ready_for_db_apply" if not source_errors else "blocked"
    )
    return {
        "schema_version": "sql_canon_phase2_backfill.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "approval_reference": APPROVAL_REFERENCE,
        "authority_boundary": {
            "phase2_additive_sql_backfill": True,
            "db_apply_performed": bool(apply_result.get("applied")),
            **FALSE_AUTHORITY_FLAGS,
        },
        "target_database": rel(DB_PATH),
        "sources": sources,
        "source_errors": source_errors,
        "before_counts": before_counts,
        "after_counts": db_counts(),
        "apply_result": apply_result,
        "validation": validation,
        "next_action": (
            "Run Phase 3 parity/no-drift harness, then migrate typed-access consumers lane by lane."
            if status == "ok"
            else "Run again with --apply-db after source errors are clear."
        ),
        "stop_lines": [
            "No archive/delete operations in Phase 2.",
            "No production-answer behavior change from this backfill alone.",
            "No capital, paper/live execution, account, money, customer, external, credential, or channel authority.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write phase report artifacts.")
    parser.add_argument("--apply-db", action="store_true", help="Apply additive Phase 2 tables/backfill to the finance SQL DB.")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build_payload(apply_db=args.apply_db)
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {"status": "unknown"}
    validation_payload = {
        "schema_version": "sql_canon_phase2_backfill_validation.v1",
        "generated_at_utc": payload["generated_at_utc"],
        "status": validation.get("status"),
        "phase_status": payload["status"],
        "checks": validation.get("checks", []),
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "authority_boundary": payload["authority_boundary"],
    }
    if args.write:
        write_json(PHASE2_OUT, payload)
        write_json(VALIDATION_OUT, validation_payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "db_apply_performed": payload["authority_boundary"]["db_apply_performed"],
                "validation": validation_payload["status"],
                "errors": validation_payload["errors"],
                "after_counts": payload["after_counts"],
                "written": [rel(PHASE2_OUT), rel(VALIDATION_OUT)] if args.write else [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and payload["status"] not in {"ok", "ready_for_db_apply"}:
        return 1
    if args.validate and args.apply_db and validation_payload["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
