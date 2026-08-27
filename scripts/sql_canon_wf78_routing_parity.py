#!/usr/bin/env python3
"""Compare WF78 JSON routing state against SQL-canon tier_routing_state."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-wf78-routing-parity.json"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_SOURCE = ROOT / "tmp" / "wf78-auto-tier-routing.json"
FIELDS = ["auto_tier", "auto_state", "route_reason", "route_priority", "data_confidence_rating", "fundamentals_confidence"]


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


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def norm(value: Any) -> str:
    return "" if value is None else str(value)


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


def build(db: Path, source: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    payload = load_json(source)
    source_rows = {
        str(row.get("ticker") or "").upper(): row
        for row in payload.get("rows", [])
        if isinstance(row, dict) and row.get("ticker")
    }
    expected_count = expected_source_row_count(payload)
    duplicate_source_count = len([row for row in payload.get("rows", []) if isinstance(row, dict) and row.get("ticker")]) - len(source_rows)
    if not db.exists():
        add("db_exists", False, rel(db))
        return result(checks, db, source, [], len(source_rows), 0)

    with closing(connect_ro(db)) as conn:
        sql_rows = {
            str(row["ticker"]): dict(row)
            for row in conn.execute("SELECT * FROM tier_routing_state ORDER BY ticker")
        }
        false_flags = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM tier_routing_state
                WHERE capital_deployment_approved != 0 OR trade_or_execution_approved != 0
                """
            ).fetchone()[0]
        )

    missing = sorted(set(source_rows) - set(sql_rows))
    extra = sorted(set(sql_rows) - set(source_rows))
    diffs: list[dict[str, Any]] = []
    for ticker in sorted(set(source_rows) & set(sql_rows)):
        src = source_rows[ticker]
        row = sql_rows[ticker]
        for field in FIELDS:
            if norm(src.get(field)) != norm(row.get(field)):
                diffs.append({"ticker": ticker, "field": field, "source": src.get(field), "sql": row.get(field)})
    add("source_status_ok", payload.get("status") == "ok", payload.get("status"))
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    add("source_validation_ok", validation.get("status") == "ok", validation.get("status"))
    add("source_expected_row_count_available", expected_count is not None, expected_count)
    add(
        "source_row_count_matches_expected",
        expected_count is not None and len(source_rows) == expected_count,
        {"source": len(source_rows), "expected": expected_count},
    )
    add("source_unique_tickers", duplicate_source_count == 0, duplicate_source_count)
    add("ticker_sets_match", not missing and not extra, {"missing": missing[:20], "extra": extra[:20], "missing_count": len(missing), "extra_count": len(extra)})
    add("routing_fields_match", not diffs, diffs[:25])
    add("authority_flags_false", false_flags == 0, false_flags)
    add("source_sql_row_counts_match", len(source_rows) == len(sql_rows), {"source": len(source_rows), "sql": len(sql_rows)})
    return result(checks, db, source, diffs, len(source_rows), len(sql_rows))


def result(
    checks: list[dict[str, Any]],
    db: Path,
    source: Path,
    diffs: list[dict[str, Any]],
    source_count: int,
    sql_count: int,
) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"]]
    status = "ok" if not errors else "blocked"
    return {
        "schema_version": "sql_canon_wf78_routing_parity.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "db": rel(db),
        "source": rel(source),
        "source_count": source_count,
        "sql_count": sql_count,
        "diff_count": len(diffs),
        "diffs": diffs[:100],
        "checks": checks,
        "errors": errors,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
        },
        "authority_boundary": {
            "read_only_validator": True,
            "db_mutation_allowed": False,
            "production_answer_change_allowed": False,
            "capital_or_execution_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    source = args.source if args.source.is_absolute() else ROOT / args.source
    payload = build(db, source)
    if args.write:
        atomic_write_json(OUT, payload)
    print(json.dumps({"status": payload["status"], "diff_count": payload["diff_count"], "written": [rel(OUT)] if args.write else []}, indent=2))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
