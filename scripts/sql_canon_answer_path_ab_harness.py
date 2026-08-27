#!/usr/bin/env python3
"""Structural A/B harness for current answer path versus SQL-canon scope."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-answer-path-ab-harness.json"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def build(db: Path, scope: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    normalized_scope = "production-scope" if scope == "production-42" else scope

    if normalized_scope not in {"production-scope", "all-200", "p0_not_cut_over"}:
        add("scope_supported", False, scope)
        return payload(checks, db, scope, [], [], [])
    if not db.exists():
        add("db_exists", False, rel(db))
        return payload(checks, db, scope, [], [], [])

    with connect_ro(db) as conn:
        if scope == "p0_not_cut_over":
            current = [
                str(row["consumer_path"])
                for row in conn.execute(
                    """
                    SELECT consumer_path
                    FROM consumer_migration_registry
                    WHERE priority='P0'
                      AND migration_lane='answer_path_parity_lane'
                      AND cutover_state='not_cut_over'
                    ORDER BY consumer_path
                    """
                )
            ]
            registry_flags = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT consumer_path, fallback_required, parity_required, raw_sql_needs_review
                    FROM consumer_migration_registry
                    WHERE priority='P0'
                      AND migration_lane='answer_path_parity_lane'
                      AND cutover_state='not_cut_over'
                    ORDER BY consumer_path
                    """
                )
            ]
            sql = p0_not_cut_over_backlog_paths()
            expected_count = 3
        elif normalized_scope == "production-scope":
            current = [str(row["ticker"]) for row in conn.execute("SELECT ticker FROM current_answer_path ORDER BY ticker")]
            sql = [
                str(row["ticker"])
                for row in conn.execute(
                    """
                    SELECT ticker
                    FROM current_sql_canon_routing
                    WHERE production_scope_member=1 AND production_card_generation_allowed=1
                    ORDER BY ticker
                    """
                )
            ]
            expected_count = len(current)
        else:
            current = [str(row["ticker"]) for row in conn.execute("SELECT ticker FROM current_active_universe ORDER BY ticker")]
            sql = [str(row["ticker"]) for row in conn.execute("SELECT ticker FROM current_sql_canon_routing ORDER BY ticker")]
            expected_count = 200
        forbidden = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM evidence_status
                WHERE customer_output_allowed != 0 OR paper_or_live_execution_allowed != 0
                """
            ).fetchone()[0]
        )
        widened = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM answer_path_scope a
                JOIN universe_membership u USING (ticker)
                WHERE a.production_card_generation_allowed = 1
                  AND u.production_scope_member != 1
                """
            ).fetchone()[0]
        )

    missing = sorted(set(current) - set(sql))
    extra = sorted(set(sql) - set(current))
    add("scope_count_expected", len(current) == len(sql) == expected_count, {"current": len(current), "sql": len(sql), "expected": expected_count})
    add("ticker_sets_match", not missing and not extra, {"missing": missing, "extra": extra})
    if scope == "p0_not_cut_over":
        add("all_targets_keep_fallback", all(int(row["fallback_required"]) == 1 for row in registry_flags), registry_flags)
        add("all_targets_require_parity", all(int(row["parity_required"]) == 1 for row in registry_flags), registry_flags)
        add("no_raw_sql_review_needed", all(int(row["raw_sql_needs_review"]) == 0 for row in registry_flags), registry_flags)
    add("no_customer_or_execution_flags", forbidden == 0, forbidden)
    add("production_scope_not_widened", widened == 0, widened)
    add("structural_only_no_rich_claim_cutover", True, "This harness validates scope parity only; rich answer text remains WF84/WF85 governed.")
    result = payload(checks, db, normalized_scope, current, sql, [{"missing": missing, "extra": extra}] if missing or extra else [])
    if scope != normalized_scope:
        result["requested_scope"] = scope
        result["compatibility_note"] = "production-42 is accepted as a deprecated alias for production-scope."
    return result


def p0_not_cut_over_backlog_paths() -> list[str]:
    if not BACKLOG.exists():
        return []
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    paths: set[str] = set()
    for lane in backlog.get("recommended_parallel_lanes", []):
        if lane.get("lane") != "answer_path_parity_lane":
            continue
        paths.update(str(path) for path in lane.get("paths", []))
    target_paths = {
        "scripts/status_card_packet.py",
        "scripts/ticker_answer_packet_archive_apply.py",
        "scripts/ticker_answer_packet_versioned_archive_packet.py",
    }
    return sorted(paths & target_paths)


def payload(
    checks: list[dict[str, Any]],
    db: Path,
    scope: str,
    current: list[str],
    sql: list[str],
    diffs: list[dict[str, Any]],
) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"]]
    status = "ok" if not errors else "blocked"
    return {
        "schema_version": "sql_canon_answer_path_ab_harness.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "scope": scope,
        "db": rel(db),
        "current_count": len(current),
        "sql_count": len(sql),
        "current_tickers": current,
        "sql_tickers": sql,
        "diffs": diffs,
        "checks": checks,
        "errors": errors,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
        },
        "authority_boundary": {
            "read_only_validator": True,
            "structural_scope_only": True,
            "rich_answer_claim_cutover_allowed": False,
            "capital_or_execution_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", default="production-scope")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    result = build(db, args.scope)
    if args.write:
        atomic_write_json(OUT, result)
    print(json.dumps({"status": result["status"], "scope": result["scope"], "errors": len(result["errors"]), "written": [rel(OUT)] if args.write else []}, indent=2))
    return 1 if args.validate and result["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
