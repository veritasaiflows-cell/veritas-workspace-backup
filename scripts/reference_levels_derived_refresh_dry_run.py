#!/usr/bin/env python3
"""Build a review-only dry-run patch for SQL reference_levels.

This script compares the Execution Board canon-anchor preview with
state/finance/finance-canon.sqlite and writes a proposed row-level update
packet. It does not mutate SQLite, Markdown canon, portfolio state, or any
execution authority surface.
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
ANCHOR_IN = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT = ROOT / "tmp" / "reference-levels-derived-refresh-dry-run.json"
MD_OUT = ROOT / "tmp" / "reference-levels-derived-refresh-dry-run.md"
APPLY_OUT = ROOT / "tmp" / "reference-levels-derived-refresh-apply-packet.json"
APPLY_MD_OUT = ROOT / "tmp" / "reference-levels-derived-refresh-apply-packet.md"
SCHEMA_VERSION = "reference_levels_derived_refresh_dry_run.v1"

APPROVED_SOURCE_FAMILY = "execution_board_anchor_preview_packet"
PROPOSED_SQL_SOURCE_PATH = "tmp/execution-board-canon-anchor-pilot.json"
AUTHORITY_CLASS = "reference_metadata_review_only_no_deployment_authority"
FALLBACK_RULE = "fallback_to_execution_board_anchor_preview_or_owner_notes"

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
    "dry_run_only": True,
    "apply_packet_only": True,
    "sql_mutation_performed": False,
    "schema_mutation_performed": False,
    "human_canon_mutation_performed": False,
    "consumer_file_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "archive_move_or_delete_performed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
    "explicit_apply_approval_required": True,
}


def legacy_anchor_compat_required_report() -> dict[str, Any]:
    generated_at = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked_legacy_anchor_compat_flag_required",
        "generated_at_utc": generated_at,
        "authority": {
            **AUTHORITY,
            "legacy_anchor_compatibility_only": True,
        },
        "source": {
            "legacy_anchor_path": rel(ANCHOR_IN),
            "current_sql_first_replacement": "reference_levels_sql_native_source_family_proof",
            "current_band_source": "tmp/band-proposals.json",
        },
        "summary": {
            "anchor_count": 0,
            "sql_row_count": 0,
            "update_count": 0,
            "insert_count": 0,
            "no_change_count": 0,
            "approval_required": True,
            "sql_write_performed": False,
            "legacy_anchor_compatibility_only": True,
        },
        "source_lineage_decision": {
            "chosen_sql_source_family": None,
            "chosen_sql_source_artifact_path": None,
            "chosen_sql_source_artifact_sha256": None,
            "blocked_reason": "legacy_anchor_compat_flag_required",
        },
        "rows": [],
        "validation": {
            "status": "blocked",
            "errors": ["legacy_anchor_compat_flag_required"],
            "warnings": [
                "Execution Board anchor dry-run is legacy compatibility evidence only; use SQL-native source-family proof for active SQL-first migration."
            ],
            "sql_write_performed": False,
            "apply_ready": False,
            "apply_blocker": "pass --legacy-anchor-compat only for explicit legacy audit/regression work",
        },
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def normalize_number(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def same_value(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        if left is None or right is None:
            return left is None and right is None
        return abs(float(left) - float(right)) <= 0.0001
    return left == right


def sql_reference_rows(db_path: Path, tickers: list[str]) -> dict[str, dict[str, Any]]:
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    with connect_readonly(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT {", ".join(REFERENCE_COLUMNS)}
            FROM reference_levels
            WHERE ticker IN ({placeholders})
            """,
            tuple(tickers),
        ).fetchall()
    return {str(row["ticker"]).upper(): dict(row) for row in rows}


def required_anchor_errors(anchor: dict[str, Any]) -> list[str]:
    required_fields = [
        "ticker",
        "band_low",
        "band_high",
        "stop",
        "source_artifact_path",
        "source_artifact_sha256",
        "source_generated_at_utc",
    ]
    errors = [field for field in required_fields if anchor.get(field) in (None, "")]
    for flag in ("capital_deployment_allowed", "execution_authority_allowed", "owner_approval_inferred"):
        if anchor.get(flag) is not False:
            errors.append(f"unsafe_{flag}")
    return errors


def proposed_raw_json(anchor: dict[str, Any], packet_source_sha256: str | None) -> str:
    payload = {
        "ticker": anchor.get("ticker"),
        "source_policy": APPROVED_SOURCE_FAMILY,
        "anchor": {
            "canon_id": anchor.get("canon_id"),
            "lane": anchor.get("lane"),
            "action_state": anchor.get("action_state"),
            "close": anchor.get("close"),
            "close_date": anchor.get("close_date"),
            "band_low": anchor.get("band_low"),
            "band_high": anchor.get("band_high"),
            "stop": anchor.get("stop"),
            "band_position": anchor.get("band_position"),
            "technical_posture": anchor.get("technical_posture"),
            "blocker_condition": anchor.get("blocker_condition"),
            "source_artifact_path": anchor.get("source_artifact_path"),
            "source_artifact_paths": anchor.get("source_artifact_paths") or [],
            "source_artifact_sha256": anchor.get("source_artifact_sha256"),
            "source_generated_at_utc": anchor.get("source_generated_at_utc"),
        },
        "sql_reference_level_authority": {
            "review_only": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "proposed_sql_source": {
            "source_artifact_path": PROPOSED_SQL_SOURCE_PATH,
            "source_artifact_sha256": packet_source_sha256,
            "fallback_rule": FALLBACK_RULE,
            "authority_class": AUTHORITY_CLASS,
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def proposed_row(anchor: dict[str, Any], packet_source_sha256: str | None) -> dict[str, Any]:
    return {
        "ticker": str(anchor.get("ticker") or "").upper(),
        "reference_price_low": normalize_number(anchor.get("band_low")),
        "reference_price_high": normalize_number(anchor.get("band_high")),
        "reference_invalidation_level": normalize_number(anchor.get("stop")),
        "reference_confidence": None,
        "reference_band_status": anchor.get("band_position"),
        "source_artifact_path": PROPOSED_SQL_SOURCE_PATH,
        "source_artifact_sha256": packet_source_sha256,
        "source_generated_at_utc": anchor.get("source_generated_at_utc"),
        "fallback_rule": FALLBACK_RULE,
        "authority_class": AUTHORITY_CLASS,
        "raw_json": proposed_raw_json(anchor, packet_source_sha256),
    }


def diff_row(current: dict[str, Any] | None, proposed: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    if current is None:
        return REFERENCE_COLUMNS[:], [
            {"field": column, "before": None, "after": proposed.get(column)} for column in REFERENCE_COLUMNS
        ]
    changed: list[str] = []
    diffs: list[dict[str, Any]] = []
    for column in REFERENCE_COLUMNS:
        before = current.get(column)
        after = proposed.get(column)
        if not same_value(before, after):
            changed.append(column)
            diffs.append({"field": column, "before": before, "after": after})
    return changed, diffs


def sql_update_preview(row: dict[str, Any]) -> dict[str, Any]:
    update_columns = [column for column in REFERENCE_COLUMNS if column != "ticker"]
    return {
        "statement": (
            "UPDATE reference_levels SET "
            + ", ".join(f"{column}=?" for column in update_columns)
            + " WHERE ticker=?;"
        ),
        "parameters": [row.get(column) for column in update_columns] + [row["ticker"]],
    }


def build_apply_packet(report: dict[str, Any], db_path: Path) -> dict[str, Any]:
    before_hashes = {row["ticker"]: row["current_row_hash"] for row in report.get("rows", [])}
    after_hashes = {row["ticker"]: row["proposed_row_hash"] for row in report.get("rows", [])}
    return {
        "schema_version": "reference_levels_derived_refresh_apply_packet.v1",
        "status": "blocked_pending_explicit_approval",
        "generated_at_utc": report["generated_at_utc"],
        "authority": AUTHORITY,
        "source_dry_run": rel(OUT),
        "db_path": rel(db_path),
        "approval_required": True,
        "sql_write_performed": False,
        "schema_mutation_performed": False,
        "backup_plan": {
            "required": True,
            "recommended_command": "sqlite3 state/finance/finance-canon.sqlite \".backup tmp/reference-levels-pre-apply-YYYYMMDD-HHMMSS.sqlite\"",
            "acceptable_alternative": "VACUUM INTO a timestamped tmp/reference-levels-pre-apply-*.sqlite backup before BEGIN IMMEDIATE.",
        },
        "rollback_plan": {
            "required": True,
            "recipe": [
                "Stop if any post-apply validator fails.",
                "Restore the timestamped backup to state/finance/finance-canon.sqlite only under an explicit rollback instruction.",
                "Re-run finance_sql_canon_access, expected parity validator, and artifact index validation.",
            ],
        },
        "summary": {
            **report["summary"],
            "current_row_hashes": before_hashes,
            "proposed_row_hashes": after_hashes,
        },
        "sql_operation_preview": [
            row["sql_update_preview"]
            for row in report.get("rows", [])
            if row.get("operation") in {"update", "insert"}
        ],
        "validator_commands": [
            "python scripts\\reference_levels_expected_parity_validator.py --write --write-md --validate",
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\execution_board_canon_anchor_drift_validator.py --write --validate --fail-on-drift",
            "python scripts\\artifact_index.py incremental",
            "python scripts\\artifact_index.py validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
        ],
        "stop_lines": [
            "No apply without explicit approval after reviewing this packet.",
            "No schema mutation.",
            "No Execution Board mutation.",
            "No SQL-first consumer promotion.",
            "No portfolio/capital/execution authority.",
        ],
    }


def build_report(anchor_path: Path, db_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    if not anchor_path.exists():
        errors.append(f"anchor preview missing: {rel(anchor_path)}")
    if not db_path.exists():
        errors.append(f"finance canon DB missing: {rel(db_path)}")
    if errors:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "generated_at_utc": generated_at,
            "authority": AUTHORITY,
            "validation": {"status": "blocked", "errors": errors, "warnings": warnings},
        }

    anchor_packet = load_json(anchor_path)
    anchors = anchor_packet.get("anchors", []) if isinstance(anchor_packet, dict) else []
    tickers = [str(anchor.get("ticker") or "").upper() for anchor in anchors if anchor.get("ticker")]
    current_rows = sql_reference_rows(db_path, tickers)
    packet_source_sha256 = sha_file(anchor_path)

    rows: list[dict[str, Any]] = []
    source_paths: Counter[str] = Counter()
    source_dates: Counter[str] = Counter()
    missing_required: list[dict[str, Any]] = []
    source_exceptions: list[dict[str, Any]] = []

    for anchor in anchors:
        ticker = str(anchor.get("ticker") or "").upper()
        required_errors = required_anchor_errors(anchor)
        if required_errors:
            missing_required.append({"ticker": ticker, "missing_or_unsafe": required_errors})
        for path in anchor.get("source_artifact_paths") or [anchor.get("source_artifact_path")]:
            if path:
                source_paths[str(path)] += 1
        if anchor.get("source_generated_at_utc"):
            source_dates[str(anchor["source_generated_at_utc"])] += 1
        if anchor.get("source_artifact_path") != "tmp/deployment-check.json":
            source_exceptions.append(
                {
                    "ticker": ticker,
                    "underlying_source_artifact_path": anchor.get("source_artifact_path"),
                    "reason": "anchor source is not the dominant deployment-check family; retained as underlying provenance while SQL source collapses to anchor preview packet",
                }
            )
        proposed = proposed_row(anchor, packet_source_sha256)
        current = current_rows.get(ticker)
        changed_fields, field_diffs = diff_row(current, proposed)
        operation = "insert" if current is None else ("no_change" if not changed_fields else "update")
        rows.append(
            {
                "ticker": ticker,
                "operation": operation,
                "changed_field_count": len(changed_fields),
                "changed_fields": changed_fields,
                "field_diffs": field_diffs,
                "current": current,
                "proposed": proposed,
                "current_row_hash": row_hash(current or {}),
                "proposed_row_hash": row_hash(proposed),
                "expected_anchor_parity_fields": {
                    "band_low": proposed["reference_price_low"],
                    "band_high": proposed["reference_price_high"],
                    "stop": proposed["reference_invalidation_level"],
                    "source_generated_at_utc": proposed["source_generated_at_utc"],
                },
                "sql_update_preview": sql_update_preview(proposed),
            }
        )

    operation_counts = Counter(row["operation"] for row in rows)
    if missing_required:
        errors.append(f"{len(missing_required)} anchors are missing required fields or have unsafe authority flags")
    if len(rows) != 42:
        warnings.append(f"expected 42 anchor rows; found {len(rows)}")
    if operation_counts.get("update", 0) or operation_counts.get("insert", 0):
        warnings.append("dry-run proposes SQL reference_levels row changes; explicit approval is required before any apply")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "generated_at_utc": generated_at,
        "authority": AUTHORITY,
        "source": {
            "anchor_path": rel(anchor_path),
            "anchor_packet_sha256": packet_source_sha256,
            "anchor_packet_status": anchor_packet.get("status"),
            "db_path": rel(db_path),
            "source_family_policy": APPROVED_SOURCE_FAMILY,
            "proposed_sql_source_artifact_path": PROPOSED_SQL_SOURCE_PATH,
        },
        "summary": {
            "anchor_count": len(anchors),
            "sql_row_count": len(current_rows),
            "insert_count": int(operation_counts.get("insert", 0)),
            "update_count": int(operation_counts.get("update", 0)),
            "no_change_count": int(operation_counts.get("no_change", 0)),
            "proposed_change_count": int(operation_counts.get("insert", 0) + operation_counts.get("update", 0)),
            "missing_required_count": len(missing_required),
            "underlying_source_path_counts": dict(source_paths),
            "source_generated_at_counts": dict(source_dates),
            "underlying_source_exception_count": len(source_exceptions),
            "approval_required": True,
            "sql_write_performed": False,
            "expected_post_apply_parity_target": "42/42",
        },
        "source_lineage_decision": {
            "chosen_sql_source_family": APPROVED_SOURCE_FAMILY,
            "chosen_sql_source_artifact_path": PROPOSED_SQL_SOURCE_PATH,
            "chosen_sql_source_artifact_sha256": packet_source_sha256,
            "underlying_anchor_source_path_counts": dict(source_paths),
            "underlying_source_exceptions": source_exceptions,
            "rationale": "Collapse SQL reference_levels rows to the generated anchor preview as the immediate derived source, while preserving underlying Execution Board/source artifact provenance inside raw_json. This prevents mixed SQL source families during the repair packet.",
        },
        "rows": rows,
        "missing_required": missing_required,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
            "sql_write_performed": False,
            "apply_ready": False,
            "apply_blocker": "explicit approval, backup, rollback, and post-apply validators required",
        },
    }


def render_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Reference Levels Derived Refresh Dry Run",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Anchor rows: `{summary.get('anchor_count', 0)}`",
        f"- SQL rows found: `{summary.get('sql_row_count', 0)}`",
        f"- Proposed updates: `{summary.get('update_count', 0)}`",
        f"- Proposed inserts: `{summary.get('insert_count', 0)}`",
        f"- No-change rows: `{summary.get('no_change_count', 0)}`",
        f"- Approval required: `{summary.get('approval_required')}`",
        "",
        "This packet is review-only. It performs no SQL write, schema mutation, Execution Board mutation, portfolio mutation, or execution authority change.",
        "",
        "## Source Policy",
        "",
        f"- Chosen SQL source family: `{report.get('source_lineage_decision', {}).get('chosen_sql_source_family')}`",
        f"- Chosen SQL source artifact: `{report.get('source_lineage_decision', {}).get('chosen_sql_source_artifact_path')}`",
        f"- Anchor packet SHA-256: `{report.get('source_lineage_decision', {}).get('chosen_sql_source_artifact_sha256')}`",
        "",
        "## Row Diff",
        "",
        "| Ticker | Operation | Changed fields | Proposed low | Proposed high | Proposed stop | Source date |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report.get("rows", []):
        proposed = row.get("proposed") or {}
        lines.append(
            "| {ticker} | {operation} | {changed} | {low} | {high} | {stop} | {date} |".format(
                ticker=row.get("ticker"),
                operation=row.get("operation"),
                changed=row.get("changed_field_count"),
                low=proposed.get("reference_price_low"),
                high=proposed.get("reference_price_high"),
                stop=proposed.get("reference_invalidation_level"),
                date=proposed.get("source_generated_at_utc"),
            )
        )
    if report.get("validation", {}).get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["validation"]["warnings"])
    if report.get("validation", {}).get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["validation"]["errors"])
    lines.extend(
        [
            "",
            "## Apply Stop Line",
            "",
            "Do not apply this SQL diff without explicit approval, DB backup, rollback proof, all-42 expected parity, and finance_sql_canon_access validation.",
            "",
        ]
    )
    return "\n".join(lines)


def render_apply_md(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    lines = [
        "# Reference Levels Derived Refresh Apply Packet",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- Proposed change count: `{summary.get('proposed_change_count', 0)}`",
        f"- Approval required: `{packet.get('approval_required')}`",
        f"- SQL write performed: `{packet.get('sql_write_performed')}`",
        "",
        "This is not approval and does not perform the apply.",
        "",
        "## Required Backup",
        "",
        f"`{packet['backup_plan']['recommended_command']}`",
        "",
        "## Required Validators",
        "",
    ]
    lines.extend(f"- `{command}`" for command in packet.get("validator_commands", []))
    lines.extend(["", "## Stop Lines", ""])
    lines.extend(f"- {line}" for line in packet.get("stop_lines", []))
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ANCHOR_IN))
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--md-output", default=str(MD_OUT))
    parser.add_argument("--apply-output", default=str(APPLY_OUT))
    parser.add_argument("--apply-md-output", default=str(APPLY_MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--legacy-anchor-compat",
        action="store_true",
        help="Run the retired Execution Board anchor compatibility dry-run. Not an active SQL-first migration proof.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    if not args.legacy_anchor_compat:
        report = legacy_anchor_compat_required_report()
        apply_packet = None
    else:
        report = build_report(input_path, db_path)
        apply_packet = build_apply_packet(report, db_path) if report.get("validation", {}).get("status") == "ok" else None
    if args.write:
        atomic_write_json(args.output, report)
        if apply_packet is not None:
            atomic_write_json(args.apply_output, apply_packet)
    if args.write_md:
        atomic_write_text(args.md_output, render_md(report))
        if apply_packet is not None:
            atomic_write_text(args.apply_md_output, render_apply_md(apply_packet))
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report.get("summary", {})
        print(
            "status={status} anchors={anchors} updates={updates} inserts={inserts} no_change={no_change} approval_required={approval}".format(
                status=report["status"],
                anchors=summary.get("anchor_count", 0),
                updates=summary.get("update_count", 0),
                inserts=summary.get("insert_count", 0),
                no_change=summary.get("no_change_count", 0),
                approval=summary.get("approval_required"),
            )
        )
    if args.validate and report.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
