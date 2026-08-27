#!/usr/bin/env python3
"""P1: create + backfill the SQL-canon disciplined (written) entry-band layer.

Companion table ``disciplined_reference_levels`` stores the *disciplined* buy
zone separately from ``reference_levels`` (which holds the daily Keltner/MA
*tracking* band). This resolves the canon mislabel where the tracking/reclaim
band was surfaced as if it were the written buy zone.

Design (see ``06. Playbooks/Disciplined Entry Band Engine Spec.md`` and the P1
implementation proposal):
- Companion table, not ALTER TABLE, so the tightly-validated ``reference_levels``
  contract and its parity/field-family validators are untouched.
- The daily refresh writer (``reference_levels_derived_refresh_apply.py``) only
  knows ``reference_levels``; it is therefore structurally incapable of moving
  disciplined levels. Enforcement is by construction, proven by static check.
- Backfill sources the disciplined band from the last owner-set written values in
  ``tmp/entry-band-data/<TICKER>.json -> preferred_band``. No owner band -> row is
  marked ``NEEDS_OWNER_BAND`` (never silently guessed).
- Review-only. No capital/trade/paper/account authority. SQL mutation runs only
  under --apply with a full backup + rollback packet + post-apply validation.
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
TMP = ROOT / "tmp"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
ENTRY_BAND_DIR = TMP / "entry-band-data"
DEFAULT_OUT = TMP / "disciplined-reference-levels-migration-result.json"
DEFAULT_ROLLBACK = TMP / "disciplined-reference-levels-migration-rollback.json"
BACKUP_ROOT = ROOT / "backups" / "disciplined-reference-levels-migration"

SCHEMA = "veritas.disciplined_reference_levels_migration.v1"
ROLLBACK_SCHEMA = "veritas.disciplined_reference_levels_migration_rollback.v1"
TABLE = "disciplined_reference_levels"
AUTHORITY_CLASS = "canonical_written_band_review_only_no_deployment_authority"
BACKFILL_TRIGGER = "owner_set_written_band_backfill_2026-08-18"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
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

TABLE_COLUMNS = [
    "ticker",
    "disciplined_band_low",
    "disciplined_band_high",
    "disciplined_stop",
    "band_state",
    "disciplined_levels_set_at",
    "disciplined_level_trigger",
    "disciplined_source_artifact_path",
    "disciplined_source_sha256",
    "authority_class",
    "prior_disciplined_json",
    "inserted_at_utc",
    "updated_at_utc",
]

AUTHORITY = {
    "review_only": True,
    "disciplined_written_band_canon_layer": True,
    "schema_mutation_allowed": True,
    "schema_mutation_scope": "create_companion_table_disciplined_reference_levels_only",
    "reference_levels_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_or_canon_note_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def normalize_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def backup_db(db_path: Path, run_id: str) -> Path:
    return backup_sqlite_database(db_path, BACKUP_ROOT / run_id / "finance-canon.sqlite")


def load_preferred_band(ticker: str) -> tuple[dict[str, Any] | None, Path]:
    path = ENTRY_BAND_DIR / f"{ticker}.json"
    if not path.exists():
        return None, path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, path
    pb = data.get("preferred_band")
    if not isinstance(pb, dict):
        return None, path
    if pb.get("low") is None or pb.get("high") is None:
        return None, path
    return pb, path


def build_proposed_rows(tickers: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    now = utc_now()
    rows: list[dict[str, Any]] = []
    counts = {"backfilled": 0, "needs_owner_band": 0}
    for ticker in tickers:
        pb, path = load_preferred_band(ticker)
        source_path = rel(path)
        if pb is not None:
            rows.append({
                "ticker": ticker,
                "disciplined_band_low": normalize_number(pb.get("low")),
                "disciplined_band_high": normalize_number(pb.get("high")),
                "disciplined_stop": normalize_number(pb.get("stop")),
                "band_state": "BACKFILLED",
                "disciplined_levels_set_at": str(pb.get("set")) if pb.get("set") else None,
                "disciplined_level_trigger": BACKFILL_TRIGGER,
                "disciplined_source_artifact_path": source_path,
                "disciplined_source_sha256": sha256_file(path),
                "authority_class": AUTHORITY_CLASS,
                "prior_disciplined_json": None,
                "inserted_at_utc": now,
                "updated_at_utc": now,
            })
            counts["backfilled"] += 1
        else:
            rows.append({
                "ticker": ticker,
                "disciplined_band_low": None,
                "disciplined_band_high": None,
                "disciplined_stop": None,
                "band_state": "NEEDS_OWNER_BAND",
                "disciplined_levels_set_at": None,
                "disciplined_level_trigger": BACKFILL_TRIGGER,
                "disciplined_source_artifact_path": source_path,
                "disciplined_source_sha256": None,
                "authority_class": AUTHORITY_CLASS,
                "prior_disciplined_json": None,
                "inserted_at_utc": now,
                "updated_at_utc": now,
            })
            counts["needs_owner_band"] += 1
    return rows, counts


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def post_apply_validation(conn: sqlite3.Connection, expected_count: int) -> list[str]:
    errors: list[str] = []
    if not table_exists(conn, TABLE):
        return [f"missing_table:{TABLE}"]
    count = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    if count != expected_count:
        errors.append(f"row_count_mismatch:expected_{expected_count}_got_{count}")
    # Spot-proof the AMD written band round-trips exactly.
    amd = conn.execute(
        f"SELECT disciplined_band_low, disciplined_band_high, disciplined_stop, band_state "
        f"FROM {TABLE} WHERE ticker='AMD'"
    ).fetchone()
    if amd is not None:
        expected = (295.33, 342.53, 271.73, "BACKFILLED")
        got = (amd["disciplined_band_low"], amd["disciplined_band_high"], amd["disciplined_stop"], amd["band_state"])
        if got != expected:
            errors.append(f"amd_disciplined_band_mismatch:expected_{expected}_got_{got}")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        errors.append(f"sqlite_integrity:{integrity}")
    return errors


def apply_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute(CREATE_TABLE_SQL)
    placeholders = ", ".join("?" for _ in TABLE_COLUMNS)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in rows:
            conn.execute(
                f"INSERT OR REPLACE INTO {TABLE}({', '.join(TABLE_COLUMNS)}) VALUES ({placeholders})",
                [row.get(col) for col in TABLE_COLUMNS],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def write_rollback(rollback_path: Path, run_id: str, db_path: Path, backup_path: Path | None, table_preexisted: bool) -> None:
    restore = (
        f"DROP TABLE IF EXISTS {TABLE};"
        if not table_preexisted
        else "Table pre-existed; restore rows from the backup DB after explicit rollback instruction."
    )
    rollback = {
        "schema": ROLLBACK_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ready_for_explicit_rollback_if_needed",
        "run_id": run_id,
        "db_path": rel(db_path),
        "table": TABLE,
        "table_preexisted": table_preexisted,
        "backup_path": rel(backup_path) if backup_path else "",
        "backup_sha256": sha256_file(backup_path) if backup_path else None,
        "restore_method": restore,
        "authority": AUTHORITY,
    }
    atomic_write_json(rollback_path, rollback)


def build_payload(*, db_path: Path, out_path: Path, rollback_path: Path, apply: bool) -> dict[str, Any]:
    run_id = f"disciplined-reference-levels-migration-{stamp()}"
    errors: list[str] = []
    if not db_path.exists():
        errors.append(f"db_missing:{rel(db_path)}")
        payload = _blocked_payload(run_id, db_path, errors)
        atomic_write_json(out_path, payload)
        return payload

    with connect(db_path) as conn:
        tickers = [str(r[0]).upper() for r in conn.execute("SELECT ticker FROM reference_levels ORDER BY ticker")]
        table_preexisted = table_exists(conn, TABLE)
    rows, counts = build_proposed_rows(tickers)
    expected_count = len(rows)

    backup_path: Path | None = None
    apply_executed = False
    validation_errors: list[str] = []
    if apply and not errors:
        backup_path = backup_db(db_path, run_id)
        with connect(db_path) as conn:
            apply_rows(conn, rows)
            validation_errors = post_apply_validation(conn, expected_count)
        apply_executed = True

    write_rollback(rollback_path, run_id, db_path, backup_path, table_preexisted)

    all_errors = errors + validation_errors
    if apply_executed:
        status = "ok" if not all_errors else "blocked"
    else:
        status = "ready_for_apply" if not all_errors else "blocked"

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "status": status,
        "apply_requested": apply,
        "apply_executed": apply_executed,
        "db_path": rel(db_path),
        "table": TABLE,
        "table_preexisted": table_preexisted,
        "reference_levels_ticker_count": len(tickers),
        "proposed_row_count": expected_count,
        "backfill_counts": counts,
        "backfill_source_dir": rel(ENTRY_BAND_DIR),
        "sample_rows": {
            t: next((r for r in rows if r["ticker"] == t), None)
            for t in ("AMD", "MSFT", "VRT") if any(r["ticker"] == t for r in rows)
        },
        "backup": {
            "path": rel(backup_path) if backup_path else "",
            "sha256": sha256_file(backup_path) if backup_path else None,
        },
        "rollback_path": rel(rollback_path),
        "daily_writer_enforcement": {
            "writer": "scripts/reference_levels_derived_refresh_apply.py",
            "guarantee": f"Writer targets reference_levels only and has no reference to {TABLE}; it is structurally incapable of moving disciplined levels.",
            "proof_command": f'grep -c "{TABLE}" scripts/reference_levels_derived_refresh_apply.py  (expect 0)',
        },
        "authority": AUTHORITY,
        "validation": {
            "status": "ok" if not all_errors and status in {"ready_for_apply", "ok"} else "blocked",
            "errors": all_errors,
            "warnings": [] if apply else ["dry_run_no_sql_write_performed"],
        },
        "post_apply_validators": [
            "python scripts\\finance_sql_canon_access.py --write --validate",
        ],
        "stop_lines": [
            "Schema mutation is limited to creating the disciplined_reference_levels companion table.",
            "No reference_levels, Markdown, or portfolio-config mutation.",
            "No capital, trade, paper/live, brokerage, account, money movement, customer, or approval authority.",
        ],
    }
    atomic_write_json(out_path, payload)
    return payload


def _blocked_payload(run_id: str, db_path: Path, errors: list[str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "status": "blocked",
        "db_path": rel(db_path),
        "authority": AUTHORITY,
        "validation": {"status": "blocked", "errors": errors, "warnings": []},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--rollback", type=Path, default=DEFAULT_ROLLBACK)
    parser.add_argument("--apply", action="store_true", help="Perform SQL mutation. Omit for dry-run.")
    parser.add_argument("--write", action="store_true", help="Accepted for contract symmetry; output is always written.")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    payload = build_payload(
        db_path=resolve(args.db),
        out_path=resolve(args.out),
        rollback_path=resolve(args.rollback),
        apply=args.apply,
    )
    print(json.dumps({
        "status": payload["status"],
        "apply_executed": payload.get("apply_executed"),
        "proposed_row_count": payload.get("proposed_row_count"),
        "backfill_counts": payload.get("backfill_counts"),
        "out": rel(resolve(args.out)),
    }, indent=2))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
