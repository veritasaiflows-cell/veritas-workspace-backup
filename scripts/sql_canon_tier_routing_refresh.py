#!/usr/bin/env python3
"""Retired WF78 SQL-canon tier_routing_state DB writer \u2014 deny-only tombstone.

The WF78 auto-tier-routing SQLite refresh path is retired and disabled.
This module keeps import compatibility and the pure validation helpers so
read-only inspection keeps working, but every database-apply and file-write
path fails closed: no invocation opens the database for writing, reads the
legacy source artifact as part of execution, creates a database backup,
writes the legacy output artifact, or reports readiness or success.

Use the current guarded SQL-canon routes instead of this retired writer.
This module performs no data-plane mutation of any kind.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RETIRED_STATUS = "retired"
RETIRED_ERROR = "retired_wf78_tier_routing_writer_disabled"
RETIRED_ERRORS = [RETIRED_ERROR]
RETIRED_REASON = (
    "retired: the WF78 sql_canon_tier_routing_refresh database writer is "
    "disabled and performs no database, backup, or output-artifact mutation; "
    "use the current guarded SQL-canon routes instead."
)


try:
    from market_data_utils import atomic_write_json, backup_sqlite_database
except Exception:  # dependency-absent fallback still fails closed
    def atomic_write_json(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(RETIRED_REASON)

    def backup_sqlite_database(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(RETIRED_REASON)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_FINANCE = ROOT / "state" / "finance"
BACKUPS = ROOT / "backups" / "finance-sql-canon-migration"
DB_PATH = STATE_FINANCE / "finance-canon.sqlite"
SOURCE = TMP / "wf78-auto-tier-routing.json"
OUT = TMP / "sql-canon-tier-routing-refresh.json"

FIELDS = ["auto_tier", "auto_state", "route_reason", "route_priority", "data_confidence_rating", "fundamentals_confidence"]
LINEAGE_FIELDS = ["auto_tier", "auto_state", "route_priority", "data_confidence_rating"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = load_json(SOURCE)
    rows = [
        row for row in payload.get("rows", [])
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    ]
    return payload, rows


def table_digest(conn: sqlite3.Connection, table: str) -> str:
    rows = [dict(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expected_source_row_count(payload: dict[str, Any]) -> int | None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    expected = summary.get("active_ticker_count")
    if isinstance(expected, int) and expected > 0:
        return expected
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    checks = validation.get("checks") if isinstance(validation.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("name") == "active_universe_rows_present":
            detail = check.get("detail")
            if isinstance(detail, int) and detail > 0:
                return detail
    return None


def validate_source(payload: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if payload.get("status") != "ok":
        errors.append("source_status_not_ok")
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    if validation.get("status") != "ok":
        errors.append("source_validation_not_ok")
    expected_row_count = expected_source_row_count(payload)
    if expected_row_count is None:
        errors.append("source_expected_row_count_unavailable")
    elif len(rows) != expected_row_count:
        errors.append("source_row_count_mismatch")
    tickers = [str(row.get("ticker") or "").upper() for row in rows]
    if len(tickers) != len(set(tickers)):
        errors.append("source_duplicate_tickers")
    bad_authority = [
        str(row.get("ticker") or "").upper()
        for row in rows
        if row.get("capital_deployment_approved") is not False
        or row.get("trade_or_execution_approved") is not False
    ]
    if bad_authority:
        errors.append("source_has_capital_or_execution_flags")
    return errors


def current_diffs(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sql_rows = {
        str(row["ticker"]): dict(row)
        for row in conn.execute("SELECT * FROM tier_routing_state ORDER BY ticker")
    }
    diffs: list[dict[str, Any]] = []
    for source in rows:
        ticker = str(source.get("ticker") or "").upper()
        sql = sql_rows.get(ticker, {})
        for field in FIELDS:
            if str(source.get(field) if source.get(field) is not None else "") != str(sql.get(field) if sql.get(field) is not None else ""):
                diffs.append({"ticker": ticker, "field": field, "source": source.get(field), "sql": sql.get(field)})
    return diffs


def _deny_apply_result() -> dict[str, Any]:
    return {
        "applied": False,
        "status": RETIRED_STATUS,
        "retired": True,
        "reason": RETIRED_REASON,
        "db_apply_performed": False,
        "errors": list(RETIRED_ERRORS),
    }


def connect(write: bool = False) -> sqlite3.Connection:
    if write:
        raise RuntimeError(RETIRED_REASON)
    conn = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backup_db(run_id: str) -> dict[str, Any]:
    raise RuntimeError(RETIRED_REASON)


def apply_refresh() -> dict[str, Any]:
    return _deny_apply_result()


def build(apply_db: bool = False) -> dict[str, Any]:
    return {
        "schema_version": "sql_canon_tier_routing_refresh.v1",
        "generated_at_utc": utc_now(),
        "status": RETIRED_STATUS,
        "retired": True,
        "reason": RETIRED_REASON,
        "target_database": rel(DB_PATH),
        "source": {
            "path": rel(SOURCE),
            "status": RETIRED_STATUS,
            "note": "the retired writer does not read the source artifact",
        },
        "pre_apply_diff_count": 0,
        "pre_apply_reference_levels_digest": None,
        "apply_result": _deny_apply_result(),
        "db_apply_performed": False,
        "written": [],
        "validation": {
            "status": "error",
            "errors": list(RETIRED_ERRORS),
            "checks": {
                "retired_writer_disabled": True,
                "source_accepted": False,
                "db_apply_performed": False,
            },
        },
        "authority_boundary": {
            "derived_non_capital_routing_sql_refresh": False,
            "tier_routing_state_only": False,
            "reference_levels_mutation_allowed": False,
            "schema_mutation_allowed": False,
            "portfolio_or_canon_markdown_mutation_allowed": False,
            "production_answer_path_change_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--apply-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)

    payload = build(apply_db=args.apply_db)
    tombstone = {
        "status": payload["status"],
        "retired": True,
        "reason": RETIRED_REASON,
        "db_apply_performed": False,
        "written": [],
        "errors": list(payload["validation"]["errors"]),
    }
    print(json.dumps(tombstone, indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
