#!/usr/bin/env python3
"""Build a GOOG/NVDA reference-level source-authority decision packet.

The stale execution-board anchor packet no longer reproduces GOOG/NVDA source
authority. This dry-run packet decides whether an existing current artifact can
replace that stale source for SQL reference_levels/source_lineage metadata. It
does not mutate SQLite, source_lineage, registry rows, portfolio/canon notes, or
archive surfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
TARGETED_PACKET = ROOT / "tmp" / "reference-levels-targeted-repair-packet.json"
BAND_PROPOSALS = ROOT / "tmp" / "band-proposals.json"
ANCHOR_PILOT = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
OUT = ROOT / "tmp" / "reference-levels-goog-nvda-source-authority-decision.json"
MD_OUT = ROOT / "tmp" / "reference-levels-goog-nvda-source-authority-decision.md"

SCHEMA = "veritas.reference_levels_goog_nvda_source_authority_decision.v1"
DECISION_ID = "goog_nvda_reference_levels_source_authority_decision_2026_06_20"
TICKERS = ("GOOG", "NVDA")
SOURCE_PATH = "tmp/band-proposals.json"
STALE_ANCHOR_PATH = "tmp/execution-board-canon-anchor-pilot.json"
AUTHORITY_CLASS = "reference_metadata_review_only_no_deployment_authority"
FALLBACK_RULE = "fallback_to_band_proposals_current_band_values_or_owner_notes"
PRICE_FIELDS = ("reference_price_low", "reference_price_high", "reference_invalidation_level")
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
    "query_only": True,
    "dry_run_only": True,
    "source_authority_decision_scaffold": True,
    "sql_mutation_performed": False,
    "source_lineage_mutation_performed": False,
    "consumer_registry_mutation_performed": False,
    "consumer_cutover_performed": False,
    "archive_move_or_delete_performed": False,
    "portfolio_or_canon_note_mutation_performed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

UNSAFE_TRUE_KEYS = {
    "sql_mutation_performed",
    "source_lineage_mutation_performed",
    "consumer_registry_mutation_performed",
    "consumer_cutover_performed",
    "archive_move_or_delete_performed",
    "portfolio_or_canon_note_mutation_performed",
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


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


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


def normalize_number(value: Any) -> float:
    return round(float(value), 4)


def numbers_equal(left: Any, right: Any) -> bool:
    try:
        return normalize_number(left) == normalize_number(right)
    except (TypeError, ValueError):
        return False


def collect_true_authority(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in UNSAFE_TRUE_KEYS and child is True:
                findings.append(dotted)
            findings.extend(collect_true_authority(child, dotted))
    elif isinstance(value, list):
        for idx, child in enumerate(value[:500]):
            findings.extend(collect_true_authority(child, f"{prefix}[{idx}]"))
    return findings


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def read_sql_rows(db_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if not db_path.exists():
        return {"integrity_check": "missing_db", "active_ticker_count": 0, "reference_row_count": 0}, {}, {}
    with connect_readonly(db_path) as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        active_count = int(conn.execute("SELECT COUNT(*) FROM securities WHERE active=1").fetchone()[0])
        reference_count = int(conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
        placeholders = ",".join("?" for _ in TICKERS)
        refs = {
            str(row["ticker"]).upper(): dict(row)
            for row in conn.execute(
                f"SELECT {', '.join(REFERENCE_COLUMNS)} FROM reference_levels WHERE ticker IN ({placeholders})",
                TICKERS,
            )
        }
        lineage: dict[str, list[dict[str, Any]]] = {}
        for row in conn.execute(
            """
            SELECT *
            FROM source_lineage
            WHERE field_family='reference_levels'
              AND scope_key IN ('GOOG', 'NVDA')
            ORDER BY scope_key, field_name
            """
        ):
            lineage.setdefault(str(row["scope_key"]).upper(), []).append(dict(row))
    return {
        "integrity_check": integrity,
        "query_only": True,
        "active_ticker_count": active_count,
        "reference_row_count": reference_count,
    }, refs, lineage


def rows_by_ticker(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(payload.get(key)):
        row = as_dict(item)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            rows[ticker] = row
    return rows


def source_generated_at(payload: dict[str, Any]) -> str:
    generated = payload.get("generated_at_utc")
    if isinstance(generated, str) and generated:
        return generated.replace("+00:00", "Z")
    return utc_now()


def current_band_values(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_price_low": row.get("current_band_low"),
        "reference_price_high": row.get("current_band_high"),
        "reference_invalidation_level": row.get("current_stop"),
        "reference_band_status": row.get("band_status"),
        "reference_confidence": row.get("band_confidence"),
        "data_date": row.get("data_date"),
        "close": row.get("close"),
        "current_value_source": "band_proposals_current_band_values",
    }


def suggested_band_values(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_price_low": row.get("suggested_band_low"),
        "reference_price_high": row.get("suggested_band_high"),
        "reference_invalidation_level": row.get("suggested_stop"),
        "reference_band_status": row.get("band_status"),
        "reference_confidence": row.get("band_confidence"),
        "data_date": row.get("data_date"),
        "close": row.get("close"),
        "current_value_source": "band_proposals_suggested_band_values",
    }


def values_match_reference(ref: dict[str, Any], values: dict[str, Any]) -> bool:
    return all(numbers_equal(ref.get(field), values.get(field)) for field in PRICE_FIELDS)


def proposed_raw_json(
    *,
    ticker: str,
    proposal_row: dict[str, Any],
    source_hash: str | None,
    source_generated: str,
) -> str:
    payload = {
        "ticker": ticker,
        "source_policy": DECISION_ID,
        "source_authority_decision": "band_proposals_current_band_values",
        "numeric_rewrite_required": False,
        "replaces_stale_source_artifact_path": STALE_ANCHOR_PATH,
        "source": {
            "source_artifact_path": SOURCE_PATH,
            "source_artifact_sha256": source_hash,
            "source_generated_at_utc": source_generated,
            "source_row_data_date": proposal_row.get("data_date"),
        },
        "band_proposal_snapshot": proposal_row,
        "authority": AUTHORITY,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def proposed_reference_metadata_row(
    *,
    ref: dict[str, Any],
    proposal_row: dict[str, Any],
    source_hash: str | None,
    source_generated: str,
) -> dict[str, Any]:
    ticker = str(ref.get("ticker") or "").upper()
    row = dict(ref)
    row.update(
        {
            "source_artifact_path": SOURCE_PATH,
            "source_artifact_sha256": source_hash,
            "source_generated_at_utc": source_generated,
            "fallback_rule": FALLBACK_RULE,
            "authority_class": AUTHORITY_CLASS,
            "raw_json": proposed_raw_json(
                ticker=ticker,
                proposal_row=proposal_row,
                source_hash=source_hash,
                source_generated=source_generated,
            ),
        }
    )
    return row


def proposed_lineage_rows(
    *,
    ticker: str,
    source_hash: str | None,
    source_generated: str,
) -> list[dict[str, Any]]:
    return [
        {
            "lineage_id": f"reference_levels:{ticker}:{field}:{DECISION_ID}",
            "scope": "ticker",
            "scope_key": ticker,
            "field_family": "reference_levels",
            "field_name": field,
            "source_artifact_path": SOURCE_PATH,
            "source_artifact_sha256": source_hash,
            "source_generated_at_utc": source_generated,
            "source_status": "ok_current_band_values_match_sql_reference",
            "validator_status": "ok",
            "authority_class": AUTHORITY_CLASS,
            "fallback_rule": FALLBACK_RULE,
            "inserted_at_utc": "<apply_time_utc>",
        }
        for field in PRICE_FIELDS
    ]


def build_decision_row(
    *,
    ticker: str,
    ref: dict[str, Any],
    lineage_rows: list[dict[str, Any]],
    proposal_row: dict[str, Any],
    anchor_rows: dict[str, dict[str, Any]],
    anchor_hash: str | None,
    band_hash: str | None,
    band_generated: str,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    anchor_rejection = {
        "source_artifact_path": STALE_ANCHOR_PATH,
        "current_file_sha256": anchor_hash,
        "sql_row_source_sha256": ref.get("source_artifact_sha256"),
        "anchor_present_for_ticker": ticker in anchor_rows,
        "status": "rejected_current_anchor_packet_not_reproducible",
        "reasons": [],
    }
    if ticker not in anchor_rows:
        anchor_rejection["reasons"].append("current_anchor_packet_missing_ticker")
    if anchor_hash != ref.get("source_artifact_sha256"):
        anchor_rejection["reasons"].append("current_anchor_hash_differs_from_sql_row_source_hash")

    current_values = current_band_values(proposal_row)
    suggested_values = suggested_band_values(proposal_row)
    current_values_match = values_match_reference(ref, current_values)
    suggested_values_match = values_match_reference(ref, suggested_values)
    if not current_values_match:
        errors.append(f"{ticker}:band_proposals_current_values_do_not_match_sql_reference")
    proposed = proposed_reference_metadata_row(
        ref=ref,
        proposal_row=proposal_row,
        source_hash=band_hash,
        source_generated=band_generated,
    )
    unsafe = collect_true_authority(proposed)
    errors.extend(f"{ticker}:unsafe_proposed_authority:{item}" for item in unsafe)
    lineage_proposed = proposed_lineage_rows(ticker=ticker, source_hash=band_hash, source_generated=band_generated)
    return (
        {
            "ticker": ticker,
            "decision": (
                "recommended_metadata_and_price_lineage_repair_to_band_proposals_current_band_values"
                if current_values_match
                else "blocked_current_band_values_do_not_match_sql_reference"
            ),
            "current_reference": ref,
            "current_price_lineage_sources": {
                str(row.get("field_name")): str(row.get("source_artifact_path"))
                for row in lineage_rows
                if str(row.get("field_name")) in PRICE_FIELDS
            },
            "stale_anchor_rejection": anchor_rejection,
            "recommended_source": {
                "source_artifact_path": SOURCE_PATH,
                "source_artifact_sha256": band_hash,
                "source_generated_at_utc": band_generated,
                "value_family": "current_band_low/current_band_high/current_stop",
                "current_values_match_sql_reference": current_values_match,
                "suggested_values_match_sql_reference": suggested_values_match,
                "numeric_rewrite_required": False,
                "current_values": current_values,
                "suggested_values": suggested_values,
                "canonical_apply_eligible": proposal_row.get("canonical_apply_eligible"),
                "needs_review": proposal_row.get("needs_review"),
                "workflow_state": proposal_row.get("workflow_state"),
            },
            "proposed_reference_metadata_update": {
                "operation": "update_source_metadata_only_dry_run",
                "before_hash": row_hash(ref),
                "proposed_hash": row_hash(proposed),
                "before": ref,
                "proposed": proposed,
                "field_diff": {
                    field: {"before": ref.get(field), "after": proposed.get(field)}
                    for field in (
                        "source_artifact_path",
                        "source_artifact_sha256",
                        "source_generated_at_utc",
                        "fallback_rule",
                        "authority_class",
                    )
                    if ref.get(field) != proposed.get(field)
                },
            },
            "proposed_source_lineage_rows": lineage_proposed,
        },
        errors,
    )


def build_packet(
    *,
    db_path: Path,
    targeted_packet_path: Path,
    band_proposals_path: Path,
    anchor_pilot_path: Path,
    require_active_count: int | None = 200,
) -> dict[str, Any]:
    targeted_payload = load_json(targeted_packet_path)
    band_payload = load_json(band_proposals_path)
    anchor_payload = load_json(anchor_pilot_path)
    band_hash = sha256_file(band_proposals_path)
    anchor_hash = sha256_file(anchor_pilot_path)
    band_generated = source_generated_at(band_payload)
    band_rows = rows_by_ticker(band_payload, "proposals")
    anchor_rows = rows_by_ticker(anchor_payload, "anchors")
    sqlite_state, refs, lineage = read_sql_rows(db_path)
    errors: list[str] = []
    warnings: list[str] = []

    if not targeted_payload:
        errors.append(f"targeted_packet_missing_or_unreadable:{rel(targeted_packet_path)}")
    if not band_payload:
        errors.append(f"band_proposals_missing_or_unreadable:{rel(band_proposals_path)}")
    if band_hash is None:
        errors.append(f"band_proposals_hash_unavailable:{rel(band_proposals_path)}")
    if sqlite_state.get("integrity_check") != "ok":
        errors.append(f"sqlite_integrity:{sqlite_state.get('integrity_check')}")
    if require_active_count is not None and sqlite_state.get("active_ticker_count") != require_active_count:
        errors.append(f"active_ticker_count_not_{require_active_count}")

    targeted_rows = rows_by_ticker(targeted_payload, "rows")
    decisions: list[dict[str, Any]] = []
    proposed_lineage: list[dict[str, Any]] = []
    for ticker in TICKERS:
        ref = refs.get(ticker)
        proposal_row = band_rows.get(ticker)
        if not ref:
            errors.append(f"{ticker}:sql_reference_row_missing")
            continue
        if not proposal_row:
            errors.append(f"{ticker}:band_proposal_row_missing")
            continue
        targeted_class = as_dict(targeted_rows.get(ticker)).get("classification")
        if targeted_class != "blocked_source_authority_or_reproducibility_required":
            warnings.append(f"{ticker}:unexpected_targeted_classification:{targeted_class}")
        decision, row_errors = build_decision_row(
            ticker=ticker,
            ref=ref,
            lineage_rows=lineage.get(ticker, []),
            proposal_row=proposal_row,
            anchor_rows=anchor_rows,
            anchor_hash=anchor_hash,
            band_hash=band_hash,
            band_generated=band_generated,
        )
        errors.extend(row_errors)
        decisions.append(decision)
        proposed_lineage.extend(as_list(decision.get("proposed_source_lineage_rows")))

    status = "blocked" if errors else "ready_for_owner_review"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "decision_id": DECISION_ID,
        "authority": dict(AUTHORITY),
        "sqlite": sqlite_state,
        "inputs": {
            "db_path": rel(db_path),
            "targeted_packet": rel(targeted_packet_path),
            "band_proposals": rel(band_proposals_path),
            "anchor_pilot": rel(anchor_pilot_path),
            "band_proposals_sha256": band_hash,
            "anchor_pilot_sha256": anchor_hash,
            "band_proposals_generated_at_utc": band_generated,
        },
        "summary": {
            "target_tickers": list(TICKERS),
            "decision_count": len(decisions),
            "recommended_source_artifact_path": SOURCE_PATH,
            "recommended_source_family": "band_proposals_current_band_values",
            "reference_metadata_update_count": len(decisions),
            "source_lineage_rows_proposed": len(proposed_lineage),
            "numeric_rewrite_count": 0,
            "sql_update_count": 0,
            "source_lineage_update_count": 0,
            "registry_writer_allowed_now": False,
            "next_safe_action": (
                "Use a separate exact gated writer to update GOOG/NVDA reference_levels "
                "source metadata and price-field source_lineage to tmp/band-proposals.json; "
                "do not treat stale anchor-pilot as reproducible authority."
            ),
        },
        "decisions": decisions,
        "proposed_source_lineage_rows": proposed_lineage,
        "gated_writer_scaffold": {
            "writer_status": "not_executed_dry_run_only",
            "future_apply_requires": [
                "exact owner/main-session approval naming this decision_id and tickers GOOG,NVDA",
                "SQLite backup via sqlite3 backup API before BEGIN IMMEDIATE",
                "BEGIN IMMEDIATE transaction with busy_timeout and foreign_keys enabled",
                "write only GOOG/NVDA reference_levels source metadata and price-field source_lineage rows",
                "post-write finance_sql_canon_access validation",
                "rerun reference_levels_sql_native_source_family_proof",
                "rerun P0 A/B parity lane before consumer registry promotion",
            ],
            "would_write_tables": ["reference_levels", "source_lineage"],
            "forbidden_writes": [
                "consumer_migration_registry until source-family proof and P0 parity pass",
                "portfolio/canon notes",
                "archive/delete/apply surfaces",
                "capital/trade/paper/live/account/customer surfaces",
            ],
        },
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)),
        },
        "stop_lines": [
            "This packet does not approve or perform SQL writes.",
            "Do not use the stale anchor-pilot file as reproducible GOOG/NVDA source authority.",
            "Do not change GOOG/NVDA numeric reference levels in this decision; this is metadata/lineage only.",
            "Do not run the consumer registry writer until this decision, the 15-row WF78 retirement exception, GS/VRT lineage repair, source-family proof, and P0 parity gates are clean.",
            "No portfolio/canon note mutation, archive/delete/apply, capital, trade, paper/live, brokerage, account, money movement, customer, or owner-approval inference authority.",
        ],
    }


def render_md(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        "# GOOG/NVDA Source Authority Decision",
        "",
        f"- Status: `{packet['status']}`",
        f"- Decision: `{packet['decision_id']}`",
        f"- Recommended source: `{summary['recommended_source_artifact_path']}`",
        f"- Reference metadata updates: `{summary['reference_metadata_update_count']}`",
        f"- Proposed source-lineage rows: `{summary['source_lineage_rows_proposed']}`",
        f"- Numeric rewrites: `{summary['numeric_rewrite_count']}`",
        f"- SQL updates performed: `{summary['sql_update_count']}`",
        f"- Registry writer allowed now: `{summary['registry_writer_allowed_now']}`",
        "",
        "## Decisions",
    ]
    for row in packet.get("decisions", []):
        rec = row["recommended_source"]
        lines.append(
            f"- `{row['ticker']}`: `{row['decision']}`; "
            f"current values match SQL `{rec['current_values_match_sql_reference']}`; "
            f"stale anchor `{row['stale_anchor_rejection']['status']}`"
        )
    lines.extend(["", "## Gated Writer Requirements"])
    for item in packet["gated_writer_scaffold"]["future_apply_requires"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Stop Lines"])
    for line in packet["stop_lines"]:
        lines.append(f"- {line}")
    validation = packet.get("validation", {})
    if validation.get("errors"):
        lines.extend(["", "## Validation Errors"])
        for error in validation["errors"]:
            lines.append(f"- `{error}`")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--targeted-packet", type=Path, default=TARGETED_PACKET)
    parser.add_argument("--band-proposals", type=Path, default=BAND_PROPOSALS)
    parser.add_argument("--anchor-pilot", type=Path, default=ANCHOR_PILOT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--require-active-count", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(
        db_path=resolve(args.db),
        targeted_packet_path=resolve(args.targeted_packet),
        band_proposals_path=resolve(args.band_proposals),
        anchor_pilot_path=resolve(args.anchor_pilot),
        require_active_count=args.require_active_count,
    )
    written: list[str] = []
    if args.write:
        atomic_write_json(resolve(args.output), packet)
        written.append(rel(resolve(args.output)))
    if args.write_md:
        atomic_write_text(resolve(args.md_output), render_md(packet))
        written.append(rel(resolve(args.md_output)))
    result = {
        "status": packet["validation"]["status"],
        "proof_status": packet["status"],
        "errors": packet["validation"]["errors"],
        "summary": packet["summary"],
        "written": written,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.validate and packet["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
