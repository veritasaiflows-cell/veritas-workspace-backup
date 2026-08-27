#!/usr/bin/env python3
"""Build a one-time WF78 retirement migration exception packet.

This is a dry-run policy and gated-writer scaffold for the 15 reference_levels
rows whose only complete numeric low/high/stop source is
tmp/wf78-missing-band-context-repair.json. It deliberately does not make WF78
band context an ongoing SQL source family, and it does not mutate SQLite,
source_lineage, consumer registry rows, portfolio/canon notes, or archives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
TARGETED_PACKET = ROOT / "tmp" / "reference-levels-targeted-repair-packet.json"
MISSING_BAND_CONTEXT = ROOT / "tmp" / "wf78-missing-band-context-repair.json"
OUT = ROOT / "tmp" / "reference-levels-wf78-retirement-migration-exception.json"
MD_OUT = ROOT / "tmp" / "reference-levels-wf78-retirement-migration-exception.md"

SCHEMA = "veritas.reference_levels_wf78_retirement_migration_exception.v1"
POLICY_ID = "legacy_wf78_band_context_migration_exception_2026_06_20"
TARGET_CLASSIFICATION = "blocked_numeric_source_available_but_apply_authority_missing"
SOURCE_AUTHORITY_CLASS = "reference_metadata_review_only_no_deployment_authority"
SOURCE_PATH = "tmp/wf78-missing-band-context-repair.json"
FALLBACK_RULE = "legacy_wf78_band_context_migration_exception_audit_fallback_only"
GOOG_NVDA = {"GOOG", "NVDA"}
PRICE_FIELDS = ("reference_price_low", "reference_price_high", "reference_invalidation_level")
LINEAGE_FIELDS = PRICE_FIELDS + ("reference_band_status", "reference_confidence")
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
    "one_time_migration_exception_scaffold": True,
    "permanent_wf78_source_policy_created": False,
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
    "repair_applied",
    "ticker_card_mutation_allowed",
    "owner_note_mutation_allowed",
    "deployment_surface_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "sql_canon_mutation_allowed",
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


def read_reference_state(db_path: Path, tickers: list[str]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not db_path.exists():
        return {"integrity_check": "missing_db", "active_ticker_count": 0, "reference_row_count": 0}, {}
    with connect_readonly(db_path) as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        active_count = int(conn.execute("SELECT COUNT(*) FROM securities WHERE active=1").fetchone()[0])
        reference_count = int(conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
        if not tickers:
            refs: dict[str, dict[str, Any]] = {}
        else:
            placeholders = ",".join("?" for _ in tickers)
            rows = conn.execute(
                f"SELECT {', '.join(REFERENCE_COLUMNS)} FROM reference_levels WHERE ticker IN ({placeholders})",
                tuple(tickers),
            ).fetchall()
            refs = {str(row["ticker"]).upper(): dict(row) for row in rows}
    return {
        "integrity_check": integrity,
        "query_only": True,
        "active_ticker_count": active_count,
        "reference_row_count": reference_count,
    }, refs


def rows_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(payload.get("rows")):
        row = as_dict(item)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            rows[ticker] = row
    return rows


def source_generated_at(payload: dict[str, Any]) -> str:
    generated = payload.get("generated_at_utc")
    if isinstance(generated, str) and generated:
        return generated
    return utc_now()


def band_values(row: dict[str, Any]) -> dict[str, Any]:
    band = as_dict(row.get("band"))
    technical_band = as_dict(as_dict(row.get("technical_band_context")).get("band"))
    return {
        "low": band.get("entry_band_low"),
        "high": band.get("entry_band_high"),
        "stop": band.get("stop_or_invalidation"),
        "band_status": band.get("band_status") or technical_band.get("band_status") or row.get("fresh_band_status"),
        "confidence": technical_band.get("band_confidence"),
        "source_timestamp": band.get("source_timestamp") or row.get("price_data_date"),
    }


def complete_band(values: dict[str, Any]) -> bool:
    return all(values.get(key) is not None for key in ("low", "high", "stop"))


def proposed_raw_json(
    *,
    ticker: str,
    source_row: dict[str, Any],
    source_hash: str | None,
    source_generated: str,
) -> str:
    payload = {
        "ticker": ticker,
        "source_policy": POLICY_ID,
        "policy_intent": "one_time_cleanup_to_retire_legacy_wf78_band_context_dependency",
        "permanent_wf78_source_authority": False,
        "source": {
            "source_artifact_path": SOURCE_PATH,
            "source_artifact_sha256": source_hash,
            "source_generated_at_utc": source_generated,
            "source_row_timestamp": band_values(source_row).get("source_timestamp"),
        },
        "band_context": {
            "band": as_dict(source_row.get("band")),
            "technical_band_context": as_dict(source_row.get("technical_band_context")),
            "current_price": source_row.get("current_price"),
            "price_data_date": source_row.get("price_data_date"),
            "price_source": source_row.get("price_source"),
            "repair_status": source_row.get("repair_status"),
            "tier": source_row.get("tier"),
        },
        "authority": AUTHORITY,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def proposed_reference_row(
    *,
    ticker: str,
    source_row: dict[str, Any],
    source_hash: str | None,
    source_generated: str,
) -> dict[str, Any]:
    values = band_values(source_row)
    return {
        "ticker": ticker,
        "reference_price_low": normalize_number(values["low"]),
        "reference_price_high": normalize_number(values["high"]),
        "reference_invalidation_level": normalize_number(values["stop"]),
        "reference_confidence": values.get("confidence"),
        "reference_band_status": values.get("band_status"),
        "source_artifact_path": SOURCE_PATH,
        "source_artifact_sha256": source_hash,
        "source_generated_at_utc": source_generated,
        "fallback_rule": FALLBACK_RULE,
        "authority_class": SOURCE_AUTHORITY_CLASS,
        "raw_json": proposed_raw_json(
            ticker=ticker,
            source_row=source_row,
            source_hash=source_hash,
            source_generated=source_generated,
        ),
    }


def proposed_lineage_rows(
    *,
    ticker: str,
    source_hash: str | None,
    source_generated: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in LINEAGE_FIELDS:
        rows.append(
            {
                "lineage_id": f"reference_levels:{ticker}:{field}:{POLICY_ID}",
                "scope": "ticker",
                "scope_key": ticker,
                "field_family": "reference_levels",
                "field_name": field,
                "source_artifact_path": SOURCE_PATH,
                "source_artifact_sha256": source_hash,
                "source_generated_at_utc": source_generated,
                "source_status": "ok_review_only_migration_exception",
                "validator_status": "ok",
                "authority_class": SOURCE_AUTHORITY_CLASS,
                "fallback_rule": FALLBACK_RULE,
                "inserted_at_utc": "<apply_time_utc>",
            }
        )
    return rows


def field_diff(before: dict[str, Any] | None, proposed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    before = before or {}
    diff: dict[str, dict[str, Any]] = {}
    for field in REFERENCE_COLUMNS:
        if field == "raw_json":
            continue
        old = before.get(field)
        new = proposed.get(field)
        if old != new:
            diff[field] = {"before": old, "after": new}
    return diff


def target_rows(targeted_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(targeted_payload.get("rows")):
        item = as_dict(row)
        if item.get("classification") == TARGET_CLASSIFICATION:
            rows.append(item)
    return sorted(rows, key=lambda item: str(item.get("ticker") or ""))


def source_decision_rows(targeted_payload: dict[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for row in as_list(targeted_payload.get("rows")):
        item = as_dict(row)
        ticker = str(item.get("ticker") or "").upper()
        if ticker in GOOG_NVDA:
            decisions.append(
                {
                    "ticker": ticker,
                    "status": "blocked_reproducible_source_required",
                    "classification_from_targeted_packet": item.get("classification"),
                    "issues": item.get("issues") or [],
                    "blockers": item.get("blockers") or [],
                    "migration_exception_in_scope": False,
                    "required_decision": (
                        "Choose a reproducible current source for SQL reference/source-lineage "
                        "authority; do not use the legacy WF78 band-context exception."
                    ),
                }
            )
    return sorted(decisions, key=lambda item: item["ticker"])


def lineage_only_rows(targeted_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(targeted_payload.get("rows")):
        item = as_dict(row)
        if item.get("classification") == "eligible_source_lineage_repair_dry_run_only":
            rows.append(
                {
                    "ticker": str(item.get("ticker") or "").upper(),
                    "status": "eligible_but_out_of_scope_for_wf78_retirement_exception",
                    "dry_run_lineage_update_count": len(as_list(item.get("dry_run_lineage_updates"))),
                    "required_next_gate": "separate_source_lineage_repair_writer_dry_run",
                }
            )
    return sorted(rows, key=lambda item: item["ticker"])


def build_packet(
    *,
    db_path: Path,
    targeted_packet_path: Path,
    missing_band_context_path: Path,
    require_active_count: int | None = 200,
    require_target_count: int | None = 15,
) -> dict[str, Any]:
    targeted_payload = load_json(targeted_packet_path)
    missing_payload = load_json(missing_band_context_path)
    source_hash = sha256_file(missing_band_context_path)
    source_generated = source_generated_at(missing_payload)
    target = target_rows(targeted_payload)
    target_tickers = [str(row.get("ticker") or "").upper() for row in target]
    source_rows = rows_by_ticker(missing_payload)
    sqlite_state, current_refs = read_reference_state(db_path, target_tickers)
    errors: list[str] = []
    warnings: list[str] = []

    if not targeted_payload:
        errors.append(f"targeted_packet_missing_or_unreadable:{rel(targeted_packet_path)}")
    if not missing_payload:
        errors.append(f"missing_band_context_missing_or_unreadable:{rel(missing_band_context_path)}")
    if source_hash is None:
        errors.append(f"missing_band_context_hash_unavailable:{rel(missing_band_context_path)}")
    if require_active_count is not None and sqlite_state.get("active_ticker_count") != require_active_count:
        errors.append(f"active_ticker_count_not_{require_active_count}")
    if sqlite_state.get("integrity_check") != "ok":
        errors.append(f"sqlite_integrity:{sqlite_state.get('integrity_check')}")
    if require_target_count is not None and len(target) != require_target_count:
        errors.append(f"target_migration_exception_count_not_{require_target_count}")

    unsafe_source = collect_true_authority(missing_payload)
    errors.extend(f"unsafe_missing_band_context_authority:{item}" for item in unsafe_source)

    proposed_updates: list[dict[str, Any]] = []
    proposed_lineage: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for target_row in target:
        ticker = str(target_row.get("ticker") or "").upper()
        source_row = source_rows.get(ticker)
        if ticker in GOOG_NVDA:
            errors.append(f"forbidden_goog_nvda_in_migration_exception:{ticker}")
            continue
        if not source_row:
            skipped.append({"ticker": ticker, "reason": "source_row_missing"})
            errors.append(f"{ticker}:source_row_missing")
            continue
        values = band_values(source_row)
        if not complete_band(values):
            skipped.append({"ticker": ticker, "reason": "source_row_incomplete_low_high_stop"})
            errors.append(f"{ticker}:source_row_incomplete_low_high_stop")
            continue
        if source_row.get("repair_status") != "ready_for_decision_grade_band_context":
            warnings.append(f"{ticker}:unexpected_repair_status:{source_row.get('repair_status')}")
        proposed = proposed_reference_row(
            ticker=ticker,
            source_row=source_row,
            source_hash=source_hash,
            source_generated=source_generated,
        )
        unsafe_proposed = collect_true_authority(proposed)
        errors.extend(f"{ticker}:unsafe_proposed_authority:{item}" for item in unsafe_proposed)
        before = current_refs.get(ticker)
        if not before:
            errors.append(f"{ticker}:current_reference_row_missing")
        proposed_lineage_rows_for_ticker = proposed_lineage_rows(
            ticker=ticker,
            source_hash=source_hash,
            source_generated=source_generated,
        )
        proposed_lineage.extend(proposed_lineage_rows_for_ticker)
        proposed_updates.append(
            {
                "ticker": ticker,
                "operation": "update_reference_levels_row_dry_run_only",
                "before": before,
                "proposed": proposed,
                "before_hash": row_hash(before),
                "proposed_hash": row_hash(proposed),
                "field_diff": field_diff(before, proposed),
                "source_lineage_rows": proposed_lineage_rows_for_ticker,
            }
        )

    classification_counts = Counter(str(as_dict(row).get("classification")) for row in as_list(targeted_payload.get("rows")))
    status = "blocked" if errors else "ready_for_owner_review"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "policy": {
            "policy_id": POLICY_ID,
            "policy_status": "proposed_one_time_migration_exception_ready_for_owner_review",
            "source_artifact_path": SOURCE_PATH,
            "source_artifact_sha256": source_hash,
            "source_generated_at_utc": source_generated,
            "allowed_scope": "exact 15 numeric-incomplete reference_levels rows from the targeted repair packet",
            "permanent_source_authority": False,
            "reason": (
                "Retire legacy WF78 band-context dependency by migrating complete review-only "
                "reference metadata once, under an explicit gate, instead of keeping WF78 band "
                "work alive as an ongoing source family."
            ),
        },
        "authority": dict(AUTHORITY),
        "sqlite": sqlite_state,
        "inputs": {
            "db_path": rel(db_path),
            "targeted_packet": rel(targeted_packet_path),
            "missing_band_context": rel(missing_band_context_path),
        },
        "summary": {
            "migration_exception_candidate_count": len(proposed_updates),
            "targeted_exception_row_count": len(target),
            "source_lineage_rows_proposed": len(proposed_lineage),
            "skipped_count": len(skipped),
            "source_authority_decision_count": len(source_decision_rows(targeted_payload)),
            "lineage_only_out_of_scope_count": len(lineage_only_rows(targeted_payload)),
            "targeted_packet_classification_counts": dict(sorted(classification_counts.items())),
            "sql_update_count": 0,
            "source_lineage_update_count": 0,
            "registry_writer_allowed_now": False,
            "sql_apply_allowed_now": False,
            "overall_sql_consumer_registry_status": (
                "blocked_pending_explicit_apply_gate_and_GOOG_NVDA_source_authority_decision"
            ),
            "next_safe_action": (
                "Owner/main-session gate may approve the exact one-time SQL write for the 15 rows; "
                "GOOG/NVDA still require a separate reproducible source-authority decision."
            ),
        },
        "migration_exception_tickers": [row["ticker"] for row in proposed_updates],
        "proposed_reference_level_updates": proposed_updates,
        "proposed_source_lineage_rows": proposed_lineage,
        "source_authority_decisions": source_decision_rows(targeted_payload),
        "lineage_only_out_of_scope": lineage_only_rows(targeted_payload),
        "skipped": skipped,
        "gated_writer_scaffold": {
            "writer_status": "not_executed_dry_run_only",
            "future_apply_requires": [
                "exact owner/main-session approval naming this policy_id and all affected tickers",
                "SQLite backup via sqlite3 backup API before BEGIN IMMEDIATE",
                "BEGIN IMMEDIATE transaction with busy_timeout and foreign_keys enabled",
                "write only reference_levels and source_lineage rows for migration_exception_tickers",
                "post-write finance_sql_canon_access validation",
                "rerun reference_levels_sql_native_source_family_proof",
                "rerun P0 A/B parity lane before any consumer registry promotion",
            ],
            "would_write_tables": ["reference_levels", "source_lineage"],
            "forbidden_writes": [
                "consumer_migration_registry until source-family proof and P0 parity pass",
                "portfolio/canon notes",
                "archive/delete/apply surfaces",
                "capital/trade/paper/live/account/customer surfaces",
            ],
            "reference_levels_sql_template": (
                "UPDATE reference_levels SET reference_price_low=?, reference_price_high=?, "
                "reference_invalidation_level=?, reference_confidence=?, reference_band_status=?, "
                "source_artifact_path=?, source_artifact_sha256=?, source_generated_at_utc=?, "
                "fallback_rule=?, authority_class=?, raw_json=? WHERE ticker=?"
            ),
            "source_lineage_sql_template": (
                "INSERT OR REPLACE INTO source_lineage(lineage_id, scope, scope_key, "
                "field_family, field_name, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc, source_status, validator_status, authority_class, "
                "fallback_rule, inserted_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
        },
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)),
        },
        "stop_lines": [
            "This packet does not approve or perform SQL writes.",
            "Do not create permanent WF78 band-context source authority.",
            "Do not include GOOG/NVDA in the legacy WF78 migration exception.",
            "Do not run the consumer registry writer until the SQL write is approved/applied, GOOG/NVDA are resolved, and source-family proof plus P0 parity pass.",
            "No portfolio/canon note mutation, archive/delete/apply, capital, trade, paper/live, brokerage, account, money movement, customer, or owner-approval inference authority.",
        ],
    }


def render_md(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        "# WF78 Retirement Migration Exception",
        "",
        f"- Status: `{packet['status']}`",
        f"- Policy: `{packet['policy']['policy_id']}`",
        f"- Permanent WF78 source authority: `{packet['policy']['permanent_source_authority']}`",
        f"- Candidate rows: `{summary['migration_exception_candidate_count']}`",
        f"- Proposed source-lineage rows: `{summary['source_lineage_rows_proposed']}`",
        f"- SQL updates performed: `{summary['sql_update_count']}`",
        f"- Registry writer allowed now: `{summary['registry_writer_allowed_now']}`",
        f"- Overall registry status: `{summary['overall_sql_consumer_registry_status']}`",
        "",
        "## Migration Exception Tickers",
    ]
    for ticker in packet.get("migration_exception_tickers", []):
        lines.append(f"- `{ticker}`")
    lines.extend(["", "## Separate Source Authority Decisions"])
    for row in packet.get("source_authority_decisions", []):
        lines.append(f"- `{row['ticker']}`: `{row['status']}`; blockers `{', '.join(row.get('blockers') or [])}`")
    lines.extend(["", "## Lineage-Only Out Of Scope"])
    for row in packet.get("lineage_only_out_of_scope", []):
        lines.append(f"- `{row['ticker']}`: `{row['status']}`")
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
    parser.add_argument("--missing-band-context", type=Path, default=MISSING_BAND_CONTEXT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--require-active-count", type=int, default=200)
    parser.add_argument("--require-target-count", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(
        db_path=resolve(args.db),
        targeted_packet_path=resolve(args.targeted_packet),
        missing_band_context_path=resolve(args.missing_band_context),
        require_active_count=args.require_active_count,
        require_target_count=args.require_target_count,
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
