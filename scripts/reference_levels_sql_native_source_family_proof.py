#!/usr/bin/env python3
"""SQL-native source-family proof for reference_levels.

This reads state/finance/finance-canon.sqlite in query-only mode and writes a
dry-run proof packet. It does not mutate SQLite, registry rows, portfolio/canon
notes, archive/delete surfaces, or execution authority.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT = ROOT / "tmp" / "reference-levels-sql-native-source-family-proof.json"
MD_OUT = ROOT / "tmp" / "reference-levels-sql-native-source-family-proof.md"
SCHEMA_VERSION = "reference_levels_sql_native_source_family_proof.v1"

PRICE_FIELDS = ("reference_price_low", "reference_price_high", "reference_invalidation_level")
LINEAGE_PRICE_FIELDS = set(PRICE_FIELDS)
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
    "sql_read_only": True,
    "registry_writer_allowed_now": False,
    "sql_mutation_performed": False,
    "schema_mutation_performed": False,
    "consumer_cutover_performed": False,
    "consumer_file_mutation_performed": False,
    "archive_move_or_delete_performed": False,
    "portfolio_or_canon_note_mutation_performed": False,
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


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def numeric_complete(row: dict[str, Any]) -> bool:
    return all(row.get(field) is not None for field in PRICE_FIELDS)


def source_score(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    target_count = int(candidate.get("target_reference_row_count") or 200)
    clean_status = 1 if candidate["validator_statuses"] and set(candidate["validator_statuses"]) <= {"ok", "pass"} else 0
    generated = 1 if candidate.get("max_generated_at_utc") else 0
    return (
        int(candidate["lineage_price_field_complete_tickers"] == target_count),
        int(candidate["numeric_complete_rows"] == target_count),
        clean_status,
        generated,
    )


def current_price_lineage_sources(
    lineage: list[dict[str, Any]],
    current_source: str | None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Select current-source price lineage without being confused by stale duplicates."""
    all_sources_by_field: dict[str, list[str]] = {}
    selected: dict[str, str] = {}
    for row in lineage:
        field_name = str(row.get("field_name") or "")
        if field_name not in LINEAGE_PRICE_FIELDS:
            continue
        source_path = str(row.get("source_artifact_path") or "")
        if not source_path:
            continue
        all_sources_by_field.setdefault(field_name, [])
        if source_path not in all_sources_by_field[field_name]:
            all_sources_by_field[field_name].append(source_path)
        if current_source and source_path == current_source:
            selected[field_name] = source_path
    if set(selected) != LINEAGE_PRICE_FIELDS:
        for field_name, sources in all_sources_by_field.items():
            if field_name not in selected and sources:
                selected[field_name] = sources[-1]
    return selected, {field: sorted(sources) for field, sources in all_sources_by_field.items()}


def build_proof(db_path: Path) -> dict[str, Any]:
    with connect_readonly(db_path) as conn:
        active_tickers = [
            str(row["ticker"]).upper()
            for row in rows(conn, "SELECT ticker FROM securities WHERE active=1 ORDER BY ticker")
        ]
        reference_rows = rows(
            conn,
            f"SELECT {', '.join(REFERENCE_COLUMNS)} FROM reference_levels ORDER BY ticker",
        )
        lineage_rows = rows(
            conn,
            """
            SELECT scope_key AS ticker, field_name, source_artifact_path,
                   source_generated_at_utc, source_status, validator_status,
                   authority_class, fallback_rule
            FROM source_lineage
            WHERE field_family='reference_levels'
            ORDER BY scope_key, field_name, source_artifact_path
            """,
        )
        source_artifacts = rows(
            conn,
            """
            SELECT artifact_path, artifact_role, exists_on_disk, sha256,
                   generated_at_utc, validator_status
            FROM source_artifacts
            ORDER BY artifact_path
            """,
        )
        integrity_check = conn.execute("PRAGMA integrity_check").fetchone()[0]

    reference_by_ticker = {str(row["ticker"]).upper(): row for row in reference_rows}
    reference_tickers = sorted(reference_by_ticker)
    active_without_reference = sorted(set(active_tickers) - set(reference_tickers))
    reference_target_count = len(reference_tickers)
    lineage_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    lineage_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lineage_rows:
        ticker = str(row["ticker"]).upper()
        row["ticker"] = ticker
        lineage_by_ticker[ticker].append(row)
        lineage_by_source[str(row["source_artifact_path"])].append(row)

    candidates: list[dict[str, Any]] = []
    all_sources = sorted(
        {
            str(row.get("source_artifact_path") or "")
            for row in reference_rows + lineage_rows
            if row.get("source_artifact_path")
        }
    )
    for source in all_sources:
        ref_for_source = [row for row in reference_rows if row.get("source_artifact_path") == source]
        lineage_for_source = lineage_by_source.get(source, [])
        price_lineage_by_ticker: dict[str, set[str]] = defaultdict(set)
        for row in lineage_for_source:
            if row["field_name"] in LINEAGE_PRICE_FIELDS:
                price_lineage_by_ticker[row["ticker"]].add(str(row["field_name"]))
        complete_price_lineage_tickers = [
            ticker for ticker, fields in price_lineage_by_ticker.items() if fields == LINEAGE_PRICE_FIELDS
        ]
        candidate = {
            "source_artifact_path": source,
            "target_reference_row_count": reference_target_count,
            "reference_row_count": len(ref_for_source),
            "numeric_complete_rows": sum(1 for row in ref_for_source if numeric_complete(row)),
            "lineage_row_count": len(lineage_for_source),
            "lineage_ticker_count": len({row["ticker"] for row in lineage_for_source}),
            "lineage_field_count": len({row["field_name"] for row in lineage_for_source}),
            "lineage_price_field_complete_tickers": len(complete_price_lineage_tickers),
            "lineage_field_names": sorted({str(row["field_name"]) for row in lineage_for_source}),
            "validator_statuses": sorted({str(row.get("validator_status")) for row in lineage_for_source if row.get("validator_status")}),
            "source_statuses": sorted({str(row.get("source_status")) for row in lineage_for_source if row.get("source_status")}),
            "min_generated_at_utc": min(
                [str(row["source_generated_at_utc"]) for row in lineage_for_source if row.get("source_generated_at_utc")]
                or [None]
            ),
            "max_generated_at_utc": max(
                [str(row["source_generated_at_utc"]) for row in lineage_for_source if row.get("source_generated_at_utc")]
                or [None]
            ),
            "single_source_daily_ready": False,
            "blockers": [],
        }
        blockers = []
        if candidate["reference_row_count"] != reference_target_count:
            blockers.append("reference_row_count_not_target")
        if candidate["numeric_complete_rows"] != reference_target_count:
            blockers.append("numeric_complete_rows_not_target")
        if candidate["lineage_price_field_complete_tickers"] != reference_target_count:
            blockers.append("price_lineage_complete_tickers_not_target")
        if set(candidate["validator_statuses"]) - {"ok", "pass"}:
            blockers.append("lineage_validator_status_not_clean")
        if not candidate["max_generated_at_utc"]:
            blockers.append("missing_source_generated_at_utc")
        candidate["blockers"] = blockers
        candidate["single_source_daily_ready"] = not blockers
        candidates.append(candidate)

    candidates.sort(key=lambda item: source_score(item), reverse=True)
    ready_sources = [candidate for candidate in candidates if candidate["single_source_daily_ready"]]

    row_proofs: list[dict[str, Any]] = []
    issue_counter: Counter[str] = Counter()
    metadata_issue_counter: Counter[str] = Counter()
    for ticker in reference_tickers:
        ref = reference_by_ticker.get(ticker)
        lineage = lineage_by_ticker.get(ticker, [])
        current_source = str(ref.get("source_artifact_path") or "") if ref else None
        price_lineage_sources, all_price_lineage_sources = current_price_lineage_sources(lineage, current_source)
        issues: list[str] = []
        metadata_issues: list[str] = []
        if ref is None:
            issues.append("missing_reference_row")
        else:
            if not numeric_complete(ref):
                issues.append("numeric_reference_fields_incomplete")
            if not ref.get("source_artifact_path"):
                issues.append("missing_reference_source_artifact_path")
        if set(price_lineage_sources) != LINEAGE_PRICE_FIELDS:
            issues.append("missing_complete_price_field_lineage")
        if ref and price_lineage_sources:
            lineage_sources = set(price_lineage_sources.values())
            if len(lineage_sources) > 1:
                metadata_issues.append("price_lineage_multi_source")
            if ref.get("source_artifact_path") not in lineage_sources:
                metadata_issues.append("reference_row_source_not_in_price_lineage")
        issue_counter.update(issues)
        metadata_issue_counter.update(metadata_issues)
        row_proofs.append(
            {
                "ticker": ticker,
                "current_source_artifact_path": ref.get("source_artifact_path") if ref else None,
                "numeric_complete": numeric_complete(ref) if ref else False,
                "price_lineage_sources": price_lineage_sources,
                "all_price_lineage_sources": all_price_lineage_sources,
                "issues": issues,
                "metadata_issues": metadata_issues,
                "dry_run_action": "retain_current_row_no_sql_update",
            }
        )

    artifact_by_path = {row["artifact_path"]: row for row in source_artifacts}
    selected = ready_sources[0] if ready_sources else None
    row_level_provenance_clean = not issue_counter
    status = "ok" if row_level_provenance_clean else "blocked"
    blocker_reasons = []
    non_blocking_readiness_gaps = []
    if not selected:
        non_blocking_readiness_gaps.append(
            "no_single_source_family_covers_all_current_reference_rows_with_clean_lineage"
        )
    if active_without_reference:
        non_blocking_readiness_gaps.append(f"active_tickers_without_reference_levels:{len(active_without_reference)}")
    if metadata_issue_counter:
        non_blocking_readiness_gaps.append(f"reference_source_lineage_metadata_issues:{sum(metadata_issue_counter.values())}")
    if issue_counter:
        blocker_reasons.append("row_level_lineage_or_numeric_gaps_present")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "db_path": rel(db_path),
        "sqlite": {
            "integrity_check": integrity_check,
            "query_only": True,
            "table_counts": {
                "securities_active": len(active_tickers),
                "reference_levels": len(reference_rows),
                "source_lineage_reference_levels": len(lineage_rows),
                "source_artifacts": len(source_artifacts),
            },
        },
        "authority": dict(AUTHORITY),
        "summary": {
            "active_ticker_count": len(active_tickers),
            "reference_row_count": len(reference_rows),
            "active_without_reference_count": len(active_without_reference),
            "candidate_source_count": len(candidates),
            "single_source_daily_ready_count": len(ready_sources),
            "approved_daily_source_path": selected["source_artifact_path"] if selected else None,
            "sql_first_reference_provenance_clean": row_level_provenance_clean,
            "single_source_daily_ready_required": False,
            "registry_writer_allowed_now": bool(selected and row_level_provenance_clean),
            "dry_run_sql_update_count": 0,
            "row_proof_count": len(row_proofs),
            "row_issue_counts": dict(sorted(issue_counter.items())),
            "row_metadata_issue_counts": dict(sorted(metadata_issue_counter.items())),
            "blocker_reasons": blocker_reasons,
            "non_blocking_readiness_gaps": non_blocking_readiness_gaps,
            "next_safe_action": (
                "prepare_gated_registry_writer_dry_run_for_p0_not_cut_over_consumers"
                if selected and row_level_provenance_clean
                else (
                    "retain_sql_first_reference_levels_as_current_owner_single_source_json_not_required"
                    if row_level_provenance_clean
                    else "repair_row_level_reference_source_lineage_before_registry_writer"
                )
            ),
        },
        "candidate_sources": candidates,
        "source_artifacts_for_candidates": {
            source: artifact_by_path.get(source)
            for source in all_sources
            if source in artifact_by_path
        },
        "row_proofs": row_proofs,
        "dry_run_diff": {
            "scope": "all_active_reference_level_rows",
            "compared_row_count": len(row_proofs),
            "sql_update_count": 0,
            "updates": [],
            "note": (
                "No SQL update is proposed by this proof. It proves current SQL row-level reference provenance; "
                "single-source JSON coverage is informational in SQL-first posture."
            ),
        },
    }


def render_md(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        "# Reference Levels SQL-Native Source-Family Proof",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- DB: `{packet['db_path']}`",
        f"- Active tickers compared: `{summary['row_proof_count']}`",
        f"- Candidate sources: `{summary['candidate_source_count']}`",
        f"- Single-source daily-ready candidates: `{summary['single_source_daily_ready_count']}`",
        f"- Approved daily source: `{summary['approved_daily_source_path']}`",
        f"- Registry writer allowed now: `{summary['registry_writer_allowed_now']}`",
        f"- Dry-run SQL updates: `{summary['dry_run_sql_update_count']}`",
        "",
        "## Blockers",
    ]
    for reason in summary["blocker_reasons"] or ["none"]:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Row Issue Counts"])
    for key, value in summary["row_issue_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    if not summary["row_issue_counts"]:
        lines.append("- none")
    lines.extend(["", "## Row Metadata Issue Counts"])
    for key, value in summary.get("row_metadata_issue_counts", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    if not summary.get("row_metadata_issue_counts"):
        lines.append("- none")
    lines.extend(["", "## Candidate Sources"])
    for source in packet["candidate_sources"]:
        lines.append(
            "- "
            + f"`{source['source_artifact_path']}`: "
            + f"rows `{source['reference_row_count']}`, "
            + f"numeric `{source['numeric_complete_rows']}`, "
            + f"price-lineage-complete `{source['lineage_price_field_complete_tickers']}`, "
            + f"ready `{source['single_source_daily_ready']}`, "
            + f"blockers `{', '.join(source['blockers']) or 'none'}`"
        )
    lines.extend(
        [
            "",
            "## Authority",
            "",
            "- Review/proof only.",
            "- No SQL mutation, registry writer, consumer cutover, archive/delete/apply, portfolio/canon note mutation, or execution authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=MD_OUT)
    args = parser.parse_args()

    packet = build_proof(args.db)
    errors: list[str] = []
    if packet["sqlite"]["integrity_check"] != "ok":
        errors.append("sqlite_integrity_not_ok")
    if packet["summary"]["reference_row_count"] <= 0:
        errors.append("reference_row_count_zero")
    if packet["summary"]["row_proof_count"] != packet["summary"]["reference_row_count"]:
        errors.append("row_proof_count_not_reference_row_count")
    if packet["authority"]["sql_mutation_performed"]:
        errors.append("sql_mutation_performed")
    if packet["authority"]["registry_writer_allowed_now"] != packet["summary"]["registry_writer_allowed_now"]:
        errors.append("authority_summary_registry_writer_mismatch")
    if packet["summary"]["dry_run_sql_update_count"] != 0:
        errors.append("unexpected_sql_update_count")

    packet["validation"] = {
        "status": "error" if errors else "ok",
        "errors": errors,
        "warnings": [],
    }
    if args.write:
        atomic_write_json(args.output, packet)
    if args.write_md:
        atomic_write_text(args.md_output, render_md(packet))

    result = {
        "status": packet["validation"]["status"],
        "proof_status": packet["status"],
        "errors": errors,
        "summary": packet["summary"],
        "written": [rel(args.output)] if args.write else [],
    }
    if args.write_md:
        result["written"].append(rel(args.md_output))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.validate and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
