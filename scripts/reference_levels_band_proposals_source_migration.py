#!/usr/bin/env python3
"""Build a gated source-provenance migration packet for reference_levels.

The packet makes ``tmp/band-proposals.json`` the source artifact for the
remaining reference_levels rows whose numeric values already match that source.
It does not apply SQL by itself; use ``reference_levels_derived_refresh_apply``
for backup, transaction, rollback packet, and rollback drill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
BAND_PROPOSALS = TMP / "band-proposals.json"
OUT = TMP / "reference-levels-band-proposals-source-migration.json"
SCHEMA = "veritas.reference_levels_band_proposals_source_migration.v1"
TARGET_TICKERS = ("GOOG", "GS", "NVDA", "VRT")
PRICE_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
)
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
AUTHORITY_CLASS = "reference_metadata_review_only_no_deployment_authority"
FALLBACK_RULE = "fallback_to_band_proposals_or_owner_notes"

AUTHORITY = {
    "review_only": True,
    "gated_apply_packet_only": True,
    "sql_mutation_performed": False,
    "schema_mutation_allowed": False,
    "portfolio_or_canon_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def proposal_by_ticker(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in as_list(packet.get("proposals")):
        if isinstance(row, dict) and row.get("ticker"):
            rows[str(row["ticker"]).upper()] = row
    return rows


def band_values(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_price_low": row.get("current_band_low"),
        "reference_price_high": row.get("current_band_high"),
        "reference_invalidation_level": row.get("current_stop"),
        "reference_band_status": row.get("band_status"),
        "reference_confidence": row.get("band_confidence"),
    }


def values_match(ref: dict[str, Any], proposal: dict[str, Any]) -> bool:
    values = band_values(proposal)
    for field in PRICE_FIELDS:
        left = ref.get(field)
        right = values.get(field)
        if left is None or right is None or round(float(left), 2) != round(float(right), 2):
            return False
    return True


def source_lineage_row(ticker: str, field_name: str, source_sha: str, generated_at: str) -> dict[str, Any]:
    return {
        "lineage_id": f"reference_levels:{ticker}:{field_name}:band_proposals_source_migration_2026_06_21",
        "scope": "ticker",
        "scope_key": ticker,
        "field_family": "reference_levels",
        "field_name": field_name,
        "source_artifact_path": "tmp/band-proposals.json",
        "source_artifact_sha256": source_sha,
        "source_generated_at_utc": generated_at,
        "source_status": "ok_current_band_values_match_sql_reference",
        "validator_status": "ok",
        "authority_class": AUTHORITY_CLASS,
        "fallback_rule": FALLBACK_RULE,
        "inserted_at_utc": "<apply_time_utc>",
    }


def proposed_raw_json(ticker: str, ref: dict[str, Any], proposal: dict[str, Any], source_sha: str, source_generated: str) -> str:
    payload = {
        "ticker": ticker,
        "source_policy": "band_proposals_current_band_values_2026_06_21",
        "source": {
            "source_artifact_path": "tmp/band-proposals.json",
            "source_artifact_sha256": source_sha,
            "source_generated_at_utc": source_generated,
            "value_family": "current_band_low/current_band_high/current_stop",
        },
        "reference_values": {
            "reference_price_low": ref.get("reference_price_low"),
            "reference_price_high": ref.get("reference_price_high"),
            "reference_invalidation_level": ref.get("reference_invalidation_level"),
            "reference_band_status": proposal.get("band_status") or ref.get("reference_band_status"),
            "reference_confidence": proposal.get("band_confidence") or ref.get("reference_confidence"),
        },
        "band_proposals_context": {
            "data_date": proposal.get("data_date"),
            "close": proposal.get("close"),
            "entry_band_method": proposal.get("entry_band_method"),
            "entry_band_type": proposal.get("entry_band_type"),
            "engine_version": proposal.get("engine_version"),
            "workflow_state": proposal.get("workflow_state"),
            "needs_review": proposal.get("needs_review"),
        },
        "authority": dict(AUTHORITY),
        "numeric_rewrite_performed": False,
    }
    return json_text(payload)


def build_packet(db_path: Path, source_path: Path) -> dict[str, Any]:
    source = load_json(source_path)
    source_rows = proposal_by_ticker(source)
    source_sha = sha256_file(source_path) if source_path.exists() else ""
    source_generated = str(source.get("generated_at_utc") or "")
    errors: list[str] = []
    warnings: list[str] = []
    if not source:
        errors.append("band_proposals_missing_or_unreadable")
    source_status = source.get("status")
    if source_status not in {"ok", "needs_review"}:
        errors.append(f"band_proposals_status_not_accepted:{source_status}")
    elif source_status == "needs_review":
        warnings.append("band_proposals_global_status_needs_review_target_rows_require_exact_value_match")
    if not source_generated:
        errors.append("band_proposals_missing_generated_at_utc")

    with connect_ro(db_path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        placeholders = ",".join("?" for _ in TARGET_TICKERS)
        db_rows = {
            str(row["ticker"]).upper(): dict(row)
            for row in conn.execute(
                f"SELECT {', '.join(REFERENCE_COLUMNS)} FROM reference_levels WHERE ticker IN ({placeholders})",
                TARGET_TICKERS,
            ).fetchall()
        }
    if integrity != "ok":
        errors.append(f"sqlite_integrity_not_ok:{integrity}")

    updates: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for ticker in TARGET_TICKERS:
        ref = db_rows.get(ticker)
        proposal = source_rows.get(ticker)
        if not ref:
            errors.append(f"{ticker}:missing_reference_row")
            continue
        if not proposal:
            errors.append(f"{ticker}:missing_band_proposals_row")
            continue
        match = values_match(ref, proposal)
        if not match:
            errors.append(f"{ticker}:band_proposals_values_do_not_match_sql_reference")
            continue
        proposed = {column: ref.get(column) for column in REFERENCE_COLUMNS}
        proposed.update(
            {
                "ticker": ticker,
                "source_artifact_path": "tmp/band-proposals.json",
                "source_artifact_sha256": source_sha,
                "source_generated_at_utc": source_generated,
                "fallback_rule": FALLBACK_RULE,
                "authority_class": AUTHORITY_CLASS,
                "raw_json": proposed_raw_json(ticker, ref, proposal, source_sha, source_generated),
            }
        )
        for field in PRICE_FIELDS:
            lineage_rows.append(source_lineage_row(ticker, field, source_sha, source_generated))
        updates.append(
            {
                "ticker": ticker,
                "reason": "migrate_reference_levels_source_provenance_to_band_proposals",
                "numeric_rewrite_required": False,
                "current": ref,
                "proposed": proposed,
            }
        )
        decisions.append(
            {
                "ticker": ticker,
                "current_source_artifact_path": ref.get("source_artifact_path"),
                "target_source_artifact_path": "tmp/band-proposals.json",
                "numeric_values_match_band_proposals": True,
                "reference_metadata_update_required": ref.get("source_artifact_path") != "tmp/band-proposals.json",
                "source_lineage_rows": 3,
            }
        )

    status = "ready_for_apply" if not errors and len(updates) == len(TARGET_TICKERS) else "blocked"
    if status == "ready_for_apply" and all(not row["reference_metadata_update_required"] for row in decisions):
        warnings.append("reference_metadata_already_on_band_proposals_for_all_targets")
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "db_path": rel(db_path),
        "source_path": rel(source_path),
        "source_sha256": source_sha,
        "source_generated_at_utc": source_generated,
        "target_source_artifact_path": "tmp/band-proposals.json",
        "target_tickers": list(TARGET_TICKERS),
        "summary": {
            "target_ticker_count": len(TARGET_TICKERS),
            "reference_metadata_update_count": sum(1 for row in decisions if row["reference_metadata_update_required"]),
            "source_lineage_rows_proposed": len(lineage_rows),
            "numeric_rewrite_count": 0,
            "sql_update_count": 0,
            "source_lineage_update_count": 0,
            "ready_for_apply": status == "ready_for_apply",
        },
        "decisions": decisions,
        "proposed_reference_level_updates": updates,
        "proposed_source_lineage_rows": lineage_rows,
        "authority": dict(AUTHORITY),
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "No numeric band rewrite.",
            "No schema mutation.",
            "No Markdown, portfolio, or canon note mutation.",
            "No capital, trade, paper/live, brokerage, account, money movement, customer, or approval authority.",
        ],
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--source", type=Path, default=BAND_PROPOSALS)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_packet(args.db if args.db.is_absolute() else ROOT / args.db, args.source if args.source.is_absolute() else ROOT / args.source)
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out_path, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "target_source_artifact_path": packet["target_source_artifact_path"],
                "reference_metadata_update_count": packet["summary"]["reference_metadata_update_count"],
                "source_lineage_rows_proposed": packet["summary"]["source_lineage_rows_proposed"],
                "out": rel(out_path),
            },
            indent=2,
        )
    )
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
