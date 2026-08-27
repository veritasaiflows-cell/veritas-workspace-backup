#!/usr/bin/env python3
"""Refresh SQL-canon tier_routing_state from the validated WF78 router.

This is intentionally narrower than sql_canon_phase2_backfill.py. It does not
clear or reload reference_levels, evidence_freshness, consumer registry, schema,
portfolio/canon notes, archives, cron, or answer-path behavior.
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


def connect(write: bool = False) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(DB_PATH)
    else:
        conn = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    if write:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


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


def backup_db(run_id: str) -> dict[str, Any]:
    backup_dir = BACKUPS / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_sqlite_database(DB_PATH, backup_dir / "finance-canon.sqlite")
    items: list[dict[str, Any]] = [
        {
            "path": rel(DB_PATH),
            "backup_path": rel(backup_path),
            "sha256": sha256(backup_path),
            "rollback": f"Restore {rel(backup_path)} over {rel(DB_PATH)} after closing SQL consumers.",
        }
    ]
    manifest = {
        "schema_version": "sql_canon_tier_routing_refresh_backup_manifest.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "items": items,
        "authority_boundary": {
            "rollback_proof_only": True,
            "capital_or_execution_authority": False,
        },
    }
    atomic_write_json(backup_dir / "manifest.json", manifest)
    return {"backup_dir": rel(backup_dir), "manifest": rel(backup_dir / "manifest.json"), "items": items}


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


def apply_refresh() -> dict[str, Any]:
    payload, rows = source_rows()
    errors = validate_source(payload, rows)
    if errors:
        return {"applied": False, "errors": errors}

    run_id = "tier-routing-" + utc_now().replace(":", "").replace("-", "").replace("T", "-").replace("Z", "Z")
    backup = backup_db(run_id)
    source_hash = sha256(SOURCE)
    inserted_at = utc_now()
    with connect(write=True) as conn:
        before_reference_digest = table_digest(conn, "reference_levels")
        before_diffs = current_diffs(conn, rows)
        with conn:
            conn.execute("DELETE FROM source_lineage WHERE field_family='tier_routing_state'")
            for row in rows:
                ticker = str(row.get("ticker") or "").upper()
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
                        rel(SOURCE),
                        source_hash,
                        payload.get("generated_at_utc"),
                        json.dumps(row, sort_keys=True),
                    ),
                )
                for field in LINEAGE_FIELDS:
                    lineage_id = "|".join(["ticker", ticker, "tier_routing_state", field])
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO source_lineage(
                            lineage_id, scope, scope_key, field_family, field_name,
                            source_artifact_path, source_artifact_sha256, source_generated_at_utc,
                            source_status, validator_status, authority_class, fallback_rule, inserted_at_utc
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            lineage_id,
                            "ticker",
                            ticker,
                            "tier_routing_state",
                            field,
                            rel(SOURCE),
                            source_hash,
                            payload.get("generated_at_utc"),
                            payload.get("status"),
                            "ok",
                            "derived_non_capital_routing",
                            "fallback_to_wf78_auto_tier_routing_json",
                            inserted_at,
                        ),
                    )
            conn.execute(
                "INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc) VALUES (?, ?, ?)",
                ("tier_routing_state_refreshed_at_utc", inserted_at, inserted_at),
            )
        after_reference_digest = table_digest(conn, "reference_levels")
        after_diffs = current_diffs(conn, rows)
        false_flags = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM tier_routing_state
                WHERE capital_deployment_approved != 0 OR trade_or_execution_approved != 0
                """
            ).fetchone()[0]
        )
        routing_count = int(conn.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0])
        lineage_count = int(conn.execute("SELECT COUNT(*) FROM source_lineage WHERE field_family='tier_routing_state'").fetchone()[0])
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_count = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    return {
        "applied": True,
        "backup": backup,
        "before_diff_count": len(before_diffs),
        "after_diff_count": len(after_diffs),
        "reference_levels_preserved": before_reference_digest == after_reference_digest,
        "reference_levels_digest_before": before_reference_digest,
        "reference_levels_digest_after": after_reference_digest,
        "routing_count": routing_count,
        "tier_routing_lineage_count": lineage_count,
        "authority_false_flag_count": false_flags,
        "integrity_check": integrity,
        "foreign_key_error_count": fk_count,
        "errors": [],
    }


def build(apply_db: bool) -> dict[str, Any]:
    payload, rows = source_rows()
    source_errors = validate_source(payload, rows)
    with connect(write=False) as conn:
        diffs = current_diffs(conn, rows) if not source_errors else []
        reference_digest = table_digest(conn, "reference_levels")
    apply_result = apply_refresh() if apply_db and not source_errors else {"applied": False, "errors": source_errors}
    errors = list(source_errors)
    if apply_result.get("applied"):
        for check_name in [
            "reference_levels_preserved",
        ]:
            if apply_result.get(check_name) is not True:
                errors.append(check_name)
        if apply_result.get("after_diff_count") != 0:
            errors.append("after_diff_count_not_zero")
        if apply_result.get("authority_false_flag_count") != 0:
            errors.append("authority_flags_not_false")
        if apply_result.get("integrity_check") != "ok":
            errors.append("integrity_check_failed")
        if apply_result.get("foreign_key_error_count") != 0:
            errors.append("foreign_key_check_failed")
    status = "ok" if apply_result.get("applied") and not errors else ("ready_for_db_apply" if not source_errors else "blocked")
    return {
        "schema_version": "sql_canon_tier_routing_refresh.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "target_database": rel(DB_PATH),
        "source": {
            "path": rel(SOURCE),
            "sha256": sha256(SOURCE),
            "status": payload.get("status"),
            "validation_status": (payload.get("validation") or {}).get("status") if isinstance(payload.get("validation"), dict) else None,
            "row_count": len(rows),
            "expected_row_count": expected_source_row_count(payload),
        },
        "pre_apply_diff_count": len(diffs),
        "pre_apply_reference_levels_digest": reference_digest,
        "apply_result": apply_result,
        "validation": {
            "status": "ok" if status == "ok" else ("warning" if status == "ready_for_db_apply" else "error"),
            "errors": errors,
            "checks": {
                "source_ok": not source_errors,
                "source_row_count_matches_expected": (
                    expected_source_row_count(payload) is not None
                    and len(rows) == expected_source_row_count(payload)
                ),
                "routing_only": True,
                "reference_levels_preserved": apply_result.get("reference_levels_preserved") if apply_result.get("applied") else None,
                "after_diff_count": apply_result.get("after_diff_count") if apply_result.get("applied") else None,
            },
        },
        "authority_boundary": {
            "derived_non_capital_routing_sql_refresh": True,
            "tier_routing_state_only": True,
            "reference_levels_mutation_allowed": False,
            "schema_mutation_allowed": False,
            "portfolio_or_canon_markdown_mutation_allowed": False,
            "production_answer_path_change_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--apply-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build(apply_db=args.apply_db)
    if args.write:
        atomic_write_json(OUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "db_apply_performed": bool(payload["apply_result"].get("applied")),
                "pre_apply_diff_count": payload["pre_apply_diff_count"],
                "after_diff_count": payload["apply_result"].get("after_diff_count"),
                "reference_levels_preserved": payload["apply_result"].get("reference_levels_preserved"),
                "errors": payload["validation"]["errors"],
                "written": [rel(OUT)] if args.write else [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and payload["status"] not in {"ok", "ready_for_db_apply"}:
        return 1
    if args.validate and args.apply_db and payload["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
