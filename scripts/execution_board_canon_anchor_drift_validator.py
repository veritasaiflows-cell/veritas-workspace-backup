#!/usr/bin/env python3
"""Compare Execution Board anchor preview rows to SQL reference_levels."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_IN = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT = ROOT / "tmp" / "execution-board-canon-anchor-drift-validator.json"
SCHEMA_VERSION = "execution_board_canon_anchor_drift_validator.v1"

AUTHORITY = {
    "review_only": True,
    "drift_detection_only": True,
    "sql_mutation_performed": False,
    "human_canon_mutation_performed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def nearly_equal(a: float | None, b: float | None, tolerance: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tolerance


def sql_reference_levels(db_path: Path, tickers: list[str]) -> dict[str, dict[str, Any]]:
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    with connect_readonly(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT ticker, reference_price_low, reference_price_high,
                   reference_invalidation_level, source_artifact_path,
                   source_artifact_sha256, source_generated_at_utc,
                   authority_class, fallback_rule
            FROM reference_levels
            WHERE ticker IN ({placeholders})
            """,
            tuple(tickers),
        ).fetchall()
    return {str(row["ticker"]).upper(): dict(row) for row in rows}


def compare(anchor: dict[str, Any], sql_row: dict[str, Any] | None, tolerance: float) -> dict[str, Any]:
    ticker = str(anchor.get("ticker") or "").upper()
    if not sql_row:
        return {"ticker": ticker, "status": "missing_sql", "mismatches": ["missing_sql_reference_level"]}
    field_pairs = [
        ("band_low", "reference_price_low"),
        ("band_high", "reference_price_high"),
        ("stop", "reference_invalidation_level"),
    ]
    mismatches: list[dict[str, Any]] = []
    for anchor_field, sql_field in field_pairs:
        if not nearly_equal(anchor.get(anchor_field), sql_row.get(sql_field), tolerance):
            mismatches.append(
                {
                    "field": anchor_field,
                    "anchor_value": anchor.get(anchor_field),
                    "sql_field": sql_field,
                    "sql_value": sql_row.get(sql_field),
                }
            )
    if anchor.get("source_generated_at_utc") and sql_row.get("source_generated_at_utc"):
        anchor_date = str(anchor.get("source_generated_at_utc"))[:10]
        sql_date = str(sql_row.get("source_generated_at_utc"))[:10]
        if anchor_date != sql_date:
            mismatches.append(
                {
                    "field": "source_generated_at_utc",
                    "anchor_value": anchor.get("source_generated_at_utc"),
                    "sql_field": "source_generated_at_utc",
                    "sql_value": sql_row.get("source_generated_at_utc"),
                }
            )
    return {
        "ticker": ticker,
        "status": "match" if not mismatches else "drift",
        "mismatches": mismatches,
        "anchor": {
            "band_low": anchor.get("band_low"),
            "band_high": anchor.get("band_high"),
            "stop": anchor.get("stop"),
            "source_generated_at_utc": anchor.get("source_generated_at_utc"),
        },
        "sql": {
            "reference_price_low": sql_row.get("reference_price_low"),
            "reference_price_high": sql_row.get("reference_price_high"),
            "reference_invalidation_level": sql_row.get("reference_invalidation_level"),
            "source_artifact_path": sql_row.get("source_artifact_path"),
            "source_generated_at_utc": sql_row.get("source_generated_at_utc"),
        },
    }


def build_report(anchor_path: Path, db_path: Path, tolerance: float) -> dict[str, Any]:
    errors: list[str] = []
    if not anchor_path.exists():
        errors.append(f"anchor preview missing: {rel(anchor_path)}")
    if not db_path.exists():
        errors.append(f"finance canon DB missing: {rel(db_path)}")
    if errors:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "generated_at_utc": utc_now(),
            "authority": AUTHORITY,
            "validation": {"status": "blocked", "errors": errors, "warnings": []},
        }
    payload = load_json(anchor_path)
    anchors = payload.get("anchors", []) if isinstance(payload, dict) else []
    tickers = [str(anchor.get("ticker")).upper() for anchor in anchors if anchor.get("ticker")]
    sql_rows = sql_reference_levels(db_path, tickers)
    rows = [compare(anchor, sql_rows.get(str(anchor.get("ticker")).upper()), tolerance) for anchor in anchors]
    status_counts = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    drift_count = int(status_counts.get("drift", 0))
    missing_count = int(status_counts.get("missing_sql", 0))
    domain_status = "blocked" if drift_count or missing_count else "ok"
    warnings: list[str] = []
    if domain_status == "blocked":
        warnings.append("Anchor-vs-SQL drift is present; downstream SQL-primary apply gates must fail closed until repaired.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": domain_status,
        "generated_at_utc": utc_now(),
        "authority": AUTHORITY,
        "source": {
            "anchor_path": rel(anchor_path),
            "db_path": rel(db_path),
            "tolerance": tolerance,
        },
        "summary": {
            "anchor_count": len(anchors),
            "sql_row_count": len(sql_rows),
            "match_count": int(status_counts.get("match", 0)),
            "drift_count": drift_count,
            "missing_sql_count": missing_count,
            "status_counts": status_counts,
        },
        "rows": rows,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": warnings,
            "domain_status": domain_status,
            "strict_fail_on_drift_available": True,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ANCHOR_IN))
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--fail-on-drift", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    report = build_report(input_path, db_path, args.tolerance)
    if args.write:
        atomic_write_json(args.output, report)
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report.get("summary", {})
        print(
            "status={status} anchors={anchors} match={match} drift={drift} missing_sql={missing}".format(
                status=report["status"],
                anchors=summary.get("anchor_count", 0),
                match=summary.get("match_count", 0),
                drift=summary.get("drift_count", 0),
                missing=summary.get("missing_sql_count", 0),
            )
        )
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    if args.fail_on_drift and report["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
