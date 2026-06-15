from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sql_consumer_authority_guard import (
    DEFAULT_CANON_CACHE_DB,
    ENTRY_STOP_REFERENCE_METADATA_FIELDS,
    WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
    active_entry_stop_reference_keys,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_CARD_DIR = TMP / "ticker-intelligence-cards"
NO_DRIFT_PILOT_JSON = TMP / "wf72-entry-stop-helper-no-drift-pilot.json"

PILOT_TICKERS = ("ETN", "VRT", "NVDA")
NUMERIC_FIELDS = {
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
}
NO_DRIFT_FIELDS = (
    "latest_known_price",
    "price_band_stop",
    "recommendation_support",
)
AUTHORITY_FALSE_FLAGS = {
    "display_reference_only": True,
    "fallback_required": True,
    "recommendation_allowed": False,
    "deployment_or_action_state_change_allowed": False,
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def connect_readonly(db_path: Path = DEFAULT_CANON_CACHE_DB) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def typed_value(field_name: str, value: Any) -> float | str | None:
    if value is None:
        return None
    if field_name in NUMERIC_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return str(value)


def active_reference_key_set() -> set[str]:
    keys = set(active_entry_stop_reference_keys())
    allowed_fields = set(ENTRY_STOP_REFERENCE_METADATA_FIELDS)
    return {
        key
        for key in keys
        if ":" in key and key.split(":", 1)[1] in allowed_fields
    }


def load_entry_stop_reference_rows(
    tickers: list[str] | tuple[str, ...] | None = None,
    *,
    db_path: Path = DEFAULT_CANON_CACHE_DB,
) -> dict[str, list[dict[str, Any]]]:
    """Read only the approved WF72 entry/stop reference metadata rows."""
    requested_tickers = [ticker.upper() for ticker in (tickers or []) if ticker]
    active_keys = active_reference_key_set()
    if len(active_keys) != 252:
        return {ticker: [] for ticker in requested_tickers}
    allowed_fields = set(ENTRY_STOP_REFERENCE_METADATA_FIELDS)
    target_keys = {
        key
        for key in active_keys
        if not requested_tickers or key.split(":", 1)[0].upper() in requested_tickers
    }
    if not target_keys:
        return {ticker: [] for ticker in requested_tickers}
    fields = sorted({key.split(":", 1)[1] for key in target_keys})
    scopes = sorted({key.split(":", 1)[0] for key in target_keys})
    placeholders_scopes = ",".join("?" for _ in scopes)
    placeholders_fields = ",".join("?" for _ in fields)
    sql = f"""
        SELECT scope, field_name, field_value, source_artifact_path, source_artifact_hash,
               sql_generated_at_utc, freshness_status, owner_mirror_note_path,
               owner_mirror_note_section, last_reconciled_at_utc, reconciliation_status,
               authority_boundary, validator_status, updated_at_utc
        FROM canon_cache_fields
        WHERE scope IN ({placeholders_scopes})
          AND field_name IN ({placeholders_fields})
          AND authority_boundary = ?
        ORDER BY scope, field_name
    """
    grouped: dict[str, list[dict[str, Any]]] = {scope.upper(): [] for scope in scopes}
    with connect_readonly(db_path) as conn:
        for row in conn.execute(sql, tuple(scopes) + tuple(fields) + (WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,)):
            item = dict(row)
            key = f"{item['scope']}:{item['field_name']}"
            if key not in active_keys or item["field_name"] not in allowed_fields:
                continue
            grouped.setdefault(str(item["scope"]).upper(), []).append(item)
    return grouped


def build_entry_stop_reference_metadata(
    ticker: str,
    *,
    db_path: Path = DEFAULT_CANON_CACHE_DB,
) -> dict[str, Any]:
    ticker = ticker.upper()
    rows = load_entry_stop_reference_rows([ticker], db_path=db_path).get(ticker, [])
    rows_by_field = {row["field_name"]: row for row in rows}
    missing_fields = [
        field for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS
        if field not in rows_by_field
    ]
    values = {
        field: typed_value(field, rows_by_field[field]["field_value"])
        for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS
        if field in rows_by_field
    }
    row_keys = [f"{ticker}:{field}" for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS if field in rows_by_field]
    issues: list[str] = []
    if missing_fields:
        issues.append("approved_reference_rows_missing:" + ",".join(missing_fields))
    bad_rows = [
        field for field, row in rows_by_field.items()
        if row.get("reconciliation_status") != "match"
        or row.get("validator_status") != "ok"
        or row.get("authority_boundary") != WF72_ENTRY_STOP_SQL_CANON_BOUNDARY
    ]
    if bad_rows:
        issues.append("reference_row_contract_issue:" + ",".join(sorted(bad_rows)))
    return {
        "schema_version": "wf72_entry_stop_reference_metadata.v1",
        "status": "available" if not issues else "fallback_required",
        "ticker": ticker,
        "authority_boundary": WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
        "sql_cache_path": rel(db_path),
        "sql_read_mode": "sqlite_uri_mode_ro",
        "approved_row_family": "exact_252_wf72_entry_stop_reference_metadata_rows",
        "approved_fields": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS),
        "row_keys": row_keys,
        "values": values,
        "source_lineage": {
            "owner_source_path": values.get("reference_level_owner_source_path"),
            "source_timestamp": values.get("reference_level_source_timestamp"),
            "source_sha256": values.get("reference_level_source_sha256"),
        },
        "source_rows": [
            {
                "key": f"{row['scope']}:{row['field_name']}",
                "source_artifact_path": row.get("source_artifact_path"),
                "source_artifact_hash": row.get("source_artifact_hash"),
                "freshness_status": row.get("freshness_status"),
                "last_reconciled_at_utc": row.get("last_reconciled_at_utc"),
                "updated_at_utc": row.get("updated_at_utc"),
            }
            for row in rows
        ],
        "missing_fields": missing_fields,
        "issues": issues,
        "notes": [
            "Reference metadata only; does not replace price_band_stop fallback values.",
            "No recommendation, deployment/action state, approval, portfolio mutation, or execution authority.",
        ],
        **AUTHORITY_FALSE_FLAGS,
    }


def load_card(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def no_drift_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for field in NO_DRIFT_FIELDS:
        if before.get(field) != after.get(field):
            diffs.append({"field": field, "before": before.get(field), "after": after.get(field)})
    return diffs


def build_no_drift_pilot(
    before_cards: dict[str, dict[str, Any]],
    after_cards: dict[str, dict[str, Any]],
    *,
    tickers: tuple[str, ...] = PILOT_TICKERS,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for ticker in tickers:
        before = before_cards.get(ticker) or {}
        after = after_cards.get(ticker) or {}
        diffs = no_drift_diff(before, after)
        metadata = after.get("entry_stop_reference_metadata") or {}
        results.append({
            "ticker": ticker,
            "status": "no_drift" if not diffs else "drift_detected",
            "compared_fields": list(NO_DRIFT_FIELDS),
            "diffs": diffs,
            "metadata_status": metadata.get("status"),
            "metadata_row_keys": metadata.get("row_keys") or [],
            "metadata_values": metadata.get("values") or {},
            "metadata_authority_boundary": metadata.get("authority_boundary"),
            "price_band_stop_unchanged": before.get("price_band_stop") == after.get("price_band_stop"),
            "recommendation_support_unchanged": before.get("recommendation_support") == after.get("recommendation_support"),
            "latest_known_price_unchanged": before.get("latest_known_price") == after.get("latest_known_price"),
        })
    drift = [row for row in results if row["status"] != "no_drift"]
    return {
        "schema_version": "wf72_entry_stop_helper_no_drift_pilot.v1",
        "generated_at_utc": utc_now(),
        "status": "no_drift" if not drift else "drift_detected",
        "pilot_tickers": list(tickers),
        "proof_scope": "ticker_card_additive_sql_reference_metadata_only",
        "proof_artifact_path": rel(NO_DRIFT_PILOT_JSON),
        "sql_cache_path": rel(DEFAULT_CANON_CACHE_DB),
        "sql_read_mode": "sqlite_uri_mode_ro",
        "authority_boundary": WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
        "results": results,
        **AUTHORITY_FALSE_FLAGS,
    }


def write_no_drift_pilot(
    before_cards: dict[str, dict[str, Any]],
    after_cards: dict[str, dict[str, Any]],
    *,
    output_path: Path = NO_DRIFT_PILOT_JSON,
) -> dict[str, Any]:
    proof = build_no_drift_pilot(before_cards, after_cards)
    output_path.write_text(json.dumps(proof, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Read WF72 entry/stop reference metadata from SQL cache in read-only mode.")
    parser.add_argument("--ticker", action="append", dest="tickers", help="Ticker to read; repeatable. Defaults to ETN/VRT/NVDA.")
    parser.add_argument("--json", action="store_true", help="Print full metadata JSON.")
    args = parser.parse_args()
    tickers = tuple(t.upper() for t in (args.tickers or list(PILOT_TICKERS)))
    metadata = {ticker: build_entry_stop_reference_metadata(ticker) for ticker in tickers}
    status = "ok" if all(row["status"] == "available" for row in metadata.values()) else "fallback_required"
    payload = {
        "status": status,
        "ticker_count": len(tickers),
        "tickers": metadata,
        "sql_read_mode": "sqlite_uri_mode_ro",
        "sql_cache_path": rel(DEFAULT_CANON_CACHE_DB),
        **AUTHORITY_FALSE_FLAGS,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps({
            "status": status,
            "ticker_count": len(tickers),
            "tickers": {ticker: {"status": row["status"], "row_count": len(row["row_keys"])} for ticker, row in metadata.items()},
        }, indent=2))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
