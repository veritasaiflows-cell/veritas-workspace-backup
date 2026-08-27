#!/usr/bin/env python3
"""Apply gated entry-band maintenance rows to SQL reference_levels.

This is the SQL-first successor to Markdown Execution Board table updates for
routine entry-band maintenance. It is intentionally narrow: it updates only the
requested ticker rows in ``reference_levels`` from an auto-band apply request,
backs up SQLite first, writes rollback proof, and preserves review-only
authority flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, backup_sqlite_database


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_CHANGES = TMP / "auto-band-apply.json"
DEFAULT_SOURCE = TMP / "band-proposals.json"
DEFAULT_OUT = TMP / "reference-levels-derived-refresh-apply-result.json"
DEFAULT_ROLLBACK = TMP / "reference-levels-derived-refresh-rollback.json"
DEFAULT_ROLLBACK_DRILL = TMP / "reference-levels-derived-refresh-rollback-drill.json"
BACKUP_ROOT = ROOT / "backups" / "reference-levels-derived-refresh"

SCHEMA = "veritas.reference_levels_derived_refresh_apply.v1"
ROLLBACK_SCHEMA = "veritas.reference_levels_derived_refresh_rollback.v1"
AUTHORITY_CLASS = "reference_metadata_review_only_no_deployment_authority"
FALLBACK_RULE = "fallback_to_band_proposals_or_owner_notes"

REFERENCE_COLUMNS = [
    "ticker",
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_confidence",
    "reference_band_status",
    "source_artifact_path",
    "source_artifact_sha256",
    "source_generated_at_utc",
    "fallback_rule",
    "authority_class",
    "raw_json",
]

AUTHORITY = {
    "review_only": True,
    "sql_reference_levels_apply_path": True,
    "routine_entry_band_maintenance_only": True,
    "schema_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_config_mutation_allowed": False,
    "portfolio_or_canon_note_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

UNSAFE_TRUE_KEYS = {
    "schema_mutation_allowed",
    "markdown_mutation_allowed",
    "portfolio_config_mutation_allowed",
    "portfolio_or_canon_note_mutation_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "customer_or_external_delivery_allowed",
    "owner_approval_inferred",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_hash(row: dict[str, Any] | None) -> str:
    payload = json.dumps(row or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_true_authority(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in UNSAFE_TRUE_KEYS and child is True:
                findings.append(dotted)
            findings.extend(collect_true_authority(child, dotted))
    elif isinstance(value, list):
        for idx, child in enumerate(value[:300]):
            findings.extend(collect_true_authority(child, f"{prefix}[{idx}]"))
    return findings


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def normalize_number(value: Any) -> float:
    return round(float(value), 4)


def source_generated_at(source_payload: dict[str, Any], applied_date: str) -> str:
    generated = source_payload.get("generated_at_utc")
    if isinstance(generated, str) and generated:
        return generated
    return f"{applied_date}T00:00:00Z"


def proposed_raw_json(change: dict[str, Any], source_hash: str | None, source_generated: str) -> str:
    payload = {
        "ticker": change.get("ticker"),
        "source_policy": "auto_band_apply_sql_first_reference_levels",
        "band_maintenance": {
            "old_low": change.get("old_low"),
            "old_high": change.get("old_high"),
            "old_stop": change.get("old_stop"),
            "new_low": change.get("new_low"),
            "new_high": change.get("new_high"),
            "new_stop": change.get("new_stop"),
            "method": change.get("method"),
            "band_status": change.get("band_status"),
            "close": change.get("close"),
            "data_date": change.get("data_date"),
            "coverage_lane": change.get("coverage_lane"),
            "workflow_state": change.get("workflow_state"),
            "reasons": change.get("reasons") or [],
        },
        "source": {
            "source_artifact_path": "tmp/band-proposals.json",
            "source_artifact_sha256": source_hash,
            "source_generated_at_utc": source_generated,
        },
        "authority": AUTHORITY,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def proposed_row(change: dict[str, Any], source_hash: str | None, source_generated: str) -> dict[str, Any]:
    ticker = str(change.get("ticker") or "").upper()
    return {
        "ticker": ticker,
        "reference_price_low": normalize_number(change.get("new_low")),
        "reference_price_high": normalize_number(change.get("new_high")),
        "reference_invalidation_level": normalize_number(change.get("new_stop")),
        "reference_confidence": None,
        "reference_band_status": change.get("band_status"),
        "source_artifact_path": "tmp/band-proposals.json",
        "source_artifact_sha256": source_hash,
        "source_generated_at_utc": source_generated,
        "fallback_rule": FALLBACK_RULE,
        "authority_class": AUTHORITY_CLASS,
        "raw_json": proposed_raw_json(change, source_hash, source_generated),
    }


def normalize_reference_row(row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column) for column in REFERENCE_COLUMNS}


def load_repair_packet(packet_path: Path, expect_count: int | None) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    payload = load_json(packet_path)
    errors: list[str] = []
    if not payload:
        return {}, [], [f"repair_packet_missing_or_unreadable:{rel(packet_path)}"]
    errors.extend(f"unsafe_repair_packet_authority:{item}" for item in collect_true_authority(payload))
    if payload.get("status") not in {"ready_for_owner_review", "ready_for_apply"}:
        errors.append(f"repair_packet_status_not_ready:{payload.get('status')}")
    validation = as_dict(payload.get("validation"))
    if validation and validation.get("status") not in {"ok", "ready"}:
        errors.append(f"repair_packet_validation_not_ok:{validation.get('status')}")

    proposed: dict[str, dict[str, Any]] = {}
    lineage_rows: list[dict[str, Any]] = []
    for item in as_list(payload.get("proposed_reference_level_updates")):
        row = as_dict(item)
        ticker = str(row.get("ticker") or "").upper()
        proposed_row_payload = as_dict(row.get("proposed"))
        if not ticker or not proposed_row_payload:
            errors.append("repair_packet_update_missing_ticker_or_proposed_row")
            continue
        proposed_row_payload = normalize_reference_row({**proposed_row_payload, "ticker": ticker})
        missing_columns = [column for column in REFERENCE_COLUMNS if column not in proposed_row_payload]
        if missing_columns:
            errors.append(f"{ticker}:repair_packet_proposed_row_missing_columns:{','.join(missing_columns)}")
        proposed[ticker] = proposed_row_payload
        for lineage in as_list(row.get("source_lineage_rows")):
            lineage_row = as_dict(lineage)
            if lineage_row:
                lineage_rows.append(lineage_row)
    for lineage in as_list(payload.get("proposed_source_lineage_rows")):
        lineage_row = as_dict(lineage)
        lineage_id = str(lineage_row.get("lineage_id") or "")
        if lineage_row and lineage_id not in {str(row.get("lineage_id") or "") for row in lineage_rows}:
            lineage_rows.append(lineage_row)
    if expect_count is not None and len(proposed) != expect_count:
        errors.append(f"repair_packet_expected_count_{expect_count}_got_{len(proposed)}")
    for ticker, row in proposed.items():
        for field in ("reference_price_low", "reference_price_high", "reference_invalidation_level"):
            if row.get(field) is None:
                errors.append(f"{ticker}:repair_packet_missing_{field}")
        if row.get("authority_class") != AUTHORITY_CLASS:
            errors.append(f"{ticker}:unexpected_authority_class:{row.get('authority_class')}")
    return proposed, lineage_rows, errors


def load_changes(changes_path: Path) -> tuple[str, list[dict[str, Any]], list[str]]:
    payload = load_json(changes_path)
    errors: list[str] = []
    if not payload:
        return "", [], [f"changes artifact missing_or_unreadable:{rel(changes_path)}"]
    errors.extend(f"unsafe_changes_authority:{item}" for item in collect_true_authority(payload))
    applied_date = str(payload.get("applied_date") or "")[:10]
    changes = [item for item in as_list(payload.get("applied")) if isinstance(item, dict)]
    if not changes:
        return applied_date, [], errors
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for item in changes:
        ticker = str(item.get("ticker") or "").upper()
        if not ticker:
            errors.append("change_missing_ticker")
            continue
        if ticker in seen:
            errors.append(f"duplicate_ticker:{ticker}")
            continue
        seen.add(ticker)
        for field in ("new_low", "new_high", "new_stop"):
            if item.get(field) is None:
                errors.append(f"{ticker}_missing_{field}")
        clean.append({**item, "ticker": ticker})
    if not applied_date:
        dates = sorted({str(item.get("data_date") or "")[:10] for item in clean if item.get("data_date")})
        applied_date = dates[-1] if dates else datetime.now(timezone.utc).date().isoformat()
    return applied_date, clean, errors


def select_rows(conn: sqlite3.Connection, tickers: list[str]) -> dict[str, dict[str, Any]]:
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT {', '.join(REFERENCE_COLUMNS)} FROM reference_levels WHERE ticker IN ({placeholders})",
        tuple(tickers),
    ).fetchall()
    return {str(row["ticker"]).upper(): dict(row) for row in rows}


def select_lineage_rows(conn: sqlite3.Connection, lineage_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not lineage_ids:
        return {}
    placeholders = ",".join("?" for _ in lineage_ids)
    rows = conn.execute(
        f"SELECT * FROM source_lineage WHERE lineage_id IN ({placeholders})",
        tuple(lineage_ids),
    ).fetchall()
    return {str(row["lineage_id"]): dict(row) for row in rows}


def backup_db(db_path: Path, backup_root: Path, run_id: str) -> Path:
    return backup_sqlite_database(db_path, backup_root / run_id / "finance-canon.sqlite")


def write_rollback(
    *,
    rollback_path: Path,
    run_id: str,
    db_path: Path,
    backup_path: Path | None,
    before_rows: dict[str, dict[str, Any]],
    proposed_rows: dict[str, dict[str, Any]],
    before_lineage_rows: dict[str, dict[str, Any]] | None = None,
    proposed_lineage_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rollback = {
        "schema": ROLLBACK_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ready_for_explicit_rollback_if_needed",
        "run_id": run_id,
        "db_path": rel(db_path),
        "backup_path": rel(backup_path) if backup_path else "",
        "backup_sha256": sha256_file(backup_path) if backup_path else None,
        "affected_tickers": sorted(proposed_rows),
        "before_rows": before_rows,
        "proposed_rows": proposed_rows,
        "before_lineage_rows": before_lineage_rows or {},
        "proposed_lineage_rows": proposed_lineage_rows or [],
        "restore_method": "Restore affected rows from before_rows or restore the backup DB only after explicit rollback instruction.",
        "authority": AUTHORITY,
    }
    atomic_write_json(rollback_path, rollback)
    return rollback


def validate_schema(conn: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "reference_levels" not in tables:
        return ["missing_reference_levels_table"]
    if "source_lineage" not in tables:
        return ["missing_source_lineage_table"]
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(reference_levels)")}
    missing = sorted(set(REFERENCE_COLUMNS) - columns)
    if missing:
        errors.append(f"reference_levels_missing_columns:{','.join(missing)}")
    lineage_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(source_lineage)")}
    required_lineage = {
        "lineage_id",
        "scope",
        "scope_key",
        "field_family",
        "field_name",
        "source_artifact_path",
        "source_artifact_sha256",
        "source_generated_at_utc",
        "source_status",
        "validator_status",
        "authority_class",
        "fallback_rule",
        "inserted_at_utc",
    }
    missing_lineage = sorted(required_lineage - lineage_columns)
    if missing_lineage:
        errors.append(f"source_lineage_missing_columns:{','.join(missing_lineage)}")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        errors.append(f"sqlite_integrity:{integrity}")
    return errors


def apply_rows(
    conn: sqlite3.Connection,
    proposed_rows: dict[str, dict[str, Any]],
    proposed_lineage_rows: list[dict[str, Any]] | None = None,
) -> None:
    update_columns = [column for column in REFERENCE_COLUMNS if column != "ticker"]
    set_clause = ", ".join(f"{column}=?" for column in update_columns)
    lineage_columns = [
        "lineage_id",
        "scope",
        "scope_key",
        "field_family",
        "field_name",
        "source_artifact_path",
        "source_artifact_sha256",
        "source_generated_at_utc",
        "source_status",
        "validator_status",
        "authority_class",
        "fallback_rule",
        "inserted_at_utc",
    ]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for ticker, row in proposed_rows.items():
            params = [row.get(column) for column in update_columns] + [ticker]
            conn.execute(f"UPDATE reference_levels SET {set_clause} WHERE ticker=?", params)
        for row in proposed_lineage_rows or []:
            clean = dict(row)
            if clean.get("inserted_at_utc") == "<apply_time_utc>":
                clean["inserted_at_utc"] = utc_now()
            placeholders = ", ".join("?" for _ in lineage_columns)
            conn.execute(
                f"INSERT OR REPLACE INTO source_lineage({', '.join(lineage_columns)}) VALUES ({placeholders})",
                [clean.get(column) for column in lineage_columns],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def rollback_drill(
    *,
    db_path: Path,
    rollback: dict[str, Any],
    drill_path: Path,
) -> dict[str, Any]:
    if not rollback.get("backup_path"):
        drill = {
            "schema": "veritas.reference_levels_derived_refresh_rollback_drill.v1",
            "generated_at_utc": utc_now(),
            "status": "not_run_no_apply",
            "authority": AUTHORITY,
        }
        atomic_write_json(drill_path, drill)
        return drill
    drill_db = TMP / f"reference-levels-derived-refresh-rollback-drill-{stamp()}.sqlite"
    shutil.copy2(db_path, drill_db)
    before_rows = as_dict(rollback.get("before_rows"))
    before_lineage_rows = as_dict(rollback.get("before_lineage_rows"))
    proposed_lineage_rows = [as_dict(row) for row in as_list(rollback.get("proposed_lineage_rows"))]
    with connect(drill_db) as conn:
        errors = validate_schema(conn)
        if not errors:
            update_columns = [column for column in REFERENCE_COLUMNS if column != "ticker"]
            set_clause = ", ".join(f"{column}=?" for column in update_columns)
            conn.execute("BEGIN IMMEDIATE")
            try:
                for ticker, row in before_rows.items():
                    params = [row.get(column) for column in update_columns] + [ticker]
                    conn.execute(f"UPDATE reference_levels SET {set_clause} WHERE ticker=?", params)
                for row in proposed_lineage_rows:
                    lineage_id = str(row.get("lineage_id") or "")
                    if not lineage_id:
                        continue
                    before_lineage = as_dict(before_lineage_rows.get(lineage_id))
                    if before_lineage:
                        columns = list(before_lineage)
                        update_columns_lineage = [column for column in columns if column != "lineage_id"]
                        set_clause_lineage = ", ".join(f"{column}=?" for column in update_columns_lineage)
                        params = [before_lineage.get(column) for column in update_columns_lineage] + [lineage_id]
                        conn.execute(f"UPDATE source_lineage SET {set_clause_lineage} WHERE lineage_id=?", params)
                    else:
                        conn.execute("DELETE FROM source_lineage WHERE lineage_id=?", (lineage_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            restored = select_rows(conn, sorted(before_rows))
            restored_lineage = select_lineage_rows(conn, sorted(before_lineage_rows))
        else:
            restored = {}
            restored_lineage = {}
    restored_ok = {ticker: row_hash(restored.get(ticker)) == row_hash(row) for ticker, row in before_rows.items()}
    restored_lineage_ok = {
        lineage_id: row_hash(restored_lineage.get(lineage_id)) == row_hash(row)
        for lineage_id, row in before_lineage_rows.items()
    }
    drill = {
        "schema": "veritas.reference_levels_derived_refresh_rollback_drill.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if all(restored_ok.values()) and not errors else "blocked",
        "drill_db_path": rel(drill_db),
        "affected_tickers": sorted(before_rows),
        "restored_hash_ok": restored_ok,
        "restored_lineage_hash_ok": restored_lineage_ok,
        "errors": errors,
        "real_db_mutated_by_drill": False,
        "authority": AUTHORITY,
    }
    atomic_write_json(drill_path, drill)
    return drill


def build_payload(
    *,
    db_path: Path,
    changes_path: Path,
    source_path: Path,
    out_path: Path,
    rollback_path: Path,
    rollback_drill_path: Path,
    backup_root: Path,
    apply: bool,
    repair_packet_path: Path | None = None,
    expect_repair_count: int | None = None,
) -> dict[str, Any]:
    run_id = f"reference-levels-derived-refresh-{stamp()}"
    source_payload = load_json(source_path)
    source_hash = sha256_file(source_path)
    applied_date = ""
    changes: list[dict[str, Any]] = []
    proposed_lineage_rows: list[dict[str, Any]] = []
    if repair_packet_path:
        proposed, proposed_lineage_rows, errors = load_repair_packet(repair_packet_path, expect_repair_count)
        source_generated = source_generated_at(source_payload, datetime.now(timezone.utc).date().isoformat())
    else:
        applied_date, changes, errors = load_changes(changes_path)
        source_generated = source_generated_at(source_payload, applied_date or datetime.now(timezone.utc).date().isoformat())
        proposed = {
            change["ticker"]: proposed_row(change, source_hash, source_generated)
            for change in changes
            if not errors
        }
    before_rows: dict[str, dict[str, Any]] = {}
    before_lineage_rows: dict[str, dict[str, Any]] = {}
    after_rows: dict[str, dict[str, Any]] = {}
    after_lineage_rows: dict[str, dict[str, Any]] = {}
    backup_path: Path | None = None
    drill: dict[str, Any] = {}

    requested_count = len(proposed)
    if not errors and requested_count:
        if not db_path.exists():
            errors.append(f"db_missing:{rel(db_path)}")
        else:
            with connect(db_path) as conn:
                errors.extend(validate_schema(conn))
                before_rows = select_rows(conn, sorted(proposed))
                missing = sorted(set(proposed) - set(before_rows))
                if missing:
                    errors.append(f"reference_level_rows_missing:{','.join(missing)}")
                lineage_ids = [str(row.get("lineage_id") or "") for row in proposed_lineage_rows if row.get("lineage_id")]
                before_lineage_rows = select_lineage_rows(conn, sorted(lineage_ids))
            unsafe_rows = collect_true_authority(proposed)
            errors.extend(f"unsafe_proposed_row_authority:{item}" for item in unsafe_rows)
            unsafe_lineage = collect_true_authority(proposed_lineage_rows)
            errors.extend(f"unsafe_proposed_lineage_authority:{item}" for item in unsafe_lineage)

    status = "ok_no_changes" if not requested_count and not errors else "ready_for_apply"
    apply_executed = False
    if apply and not errors and requested_count:
        backup_path = backup_db(db_path, backup_root, run_id)
        with connect(db_path) as conn:
            apply_rows(conn, proposed, proposed_lineage_rows)
            after_rows = select_rows(conn, sorted(proposed))
            lineage_ids = [str(row.get("lineage_id") or "") for row in proposed_lineage_rows if row.get("lineage_id")]
            after_lineage_rows = select_lineage_rows(conn, sorted(lineage_ids))
        apply_executed = True
        status = "ok" if all(row_hash(after_rows.get(ticker)) == row_hash(row) for ticker, row in proposed.items()) else "blocked"
        if proposed_lineage_rows and len(after_lineage_rows) != len({str(row.get("lineage_id")) for row in proposed_lineage_rows}):
            status = "blocked"
            errors.append("source_lineage_after_count_mismatch")
    elif errors:
        status = "blocked"
    elif apply and not requested_count:
        status = "ok_no_changes"

    rollback = write_rollback(
        rollback_path=rollback_path,
        run_id=run_id,
        db_path=db_path,
        backup_path=backup_path,
        before_rows=before_rows,
        proposed_rows=proposed,
        before_lineage_rows=before_lineage_rows,
        proposed_lineage_rows=proposed_lineage_rows,
    )
    if apply_executed:
        drill = rollback_drill(db_path=db_path, rollback=rollback, drill_path=rollback_drill_path)
        if drill.get("status") != "ok":
            status = "blocked"
            errors.append("rollback_drill_blocked")
    else:
        drill = rollback_drill(db_path=db_path, rollback=rollback, drill_path=rollback_drill_path)

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "status": status,
        "apply_requested": apply,
        "apply_executed": apply_executed,
        "db_path": rel(db_path),
        "changes_path": rel(changes_path),
        "source_path": rel(source_path),
        "repair_packet_path": rel(repair_packet_path) if repair_packet_path else "",
        "source_sha256": source_hash,
        "source_generated_at_utc": source_generated,
        "affected_tickers": sorted(proposed),
        "affected_count": len(proposed),
        "source_lineage_affected_count": len(proposed_lineage_rows),
        "before_row_hashes": {ticker: row_hash(row) for ticker, row in before_rows.items()},
        "proposed_row_hashes": {ticker: row_hash(row) for ticker, row in proposed.items()},
        "after_row_hashes": {ticker: row_hash(row) for ticker, row in after_rows.items()},
        "before_lineage_hashes": {lineage_id: row_hash(row) for lineage_id, row in before_lineage_rows.items()},
        "after_lineage_hashes": {lineage_id: row_hash(row) for lineage_id, row in after_lineage_rows.items()},
        "backup": {
            "path": rel(backup_path) if backup_path else "",
            "sha256": sha256_file(backup_path) if backup_path else None,
        },
        "rollback_path": rel(rollback_path),
        "rollback_drill_path": rel(rollback_drill_path),
        "rollback_drill_status": drill.get("status"),
        "rows": [
            {
                "ticker": ticker,
                "before": before_rows.get(ticker),
                "proposed": proposed.get(ticker),
                "after": after_rows.get(ticker),
                "operation": "update",
            }
            for ticker in sorted(proposed)
        ],
        "authority": AUTHORITY,
        "validation": {
            "status": "ok" if not errors and status in {"ready_for_apply", "ok", "ok_no_changes"} else "blocked",
            "errors": errors,
            "warnings": [] if apply else ["dry_run_no_sql_write_performed"],
        },
        "post_apply_validators": [
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
            "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
            "python scripts\\full_intelligence_answer_parity.py --write --validate",
        ],
        "stop_lines": [
            "No schema mutation.",
            "No Markdown or portfolio-config mutation.",
            "No capital, trade, paper/live, brokerage, account, money movement, customer, or approval authority.",
        ],
    }
    atomic_write_json(out_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--changes", type=Path, default=DEFAULT_CHANGES)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--rollback", type=Path, default=DEFAULT_ROLLBACK)
    parser.add_argument("--rollback-drill", type=Path, default=DEFAULT_ROLLBACK_DRILL)
    parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    parser.add_argument("--repair-packet", type=Path, default=None)
    parser.add_argument("--expect-repair-count", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true", help="Accepted for contract symmetry; output is always written.")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    payload = build_payload(
        db_path=resolve(args.db),
        changes_path=resolve(args.changes),
        source_path=resolve(args.source),
        out_path=resolve(args.out),
        rollback_path=resolve(args.rollback),
        rollback_drill_path=resolve(args.rollback_drill),
        backup_root=resolve(args.backup_root),
        apply=args.apply,
        repair_packet_path=resolve(args.repair_packet) if args.repair_packet else None,
        expect_repair_count=args.expect_repair_count,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "apply_executed": payload["apply_executed"],
                "affected_count": payload["affected_count"],
                "out": rel(resolve(args.out)),
            },
            indent=2,
        )
    )
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
