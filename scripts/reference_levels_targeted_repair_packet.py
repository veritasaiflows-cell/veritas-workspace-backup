#!/usr/bin/env python3
"""Build a targeted repair packet for SQL reference_levels blockers.

This is a query-only planner. It identifies which current blockers are
repairable from existing validated artifacts and which require fresh source
evidence or an explicit source-authority decision. It does not mutate SQLite,
registry rows, source_lineage rows, portfolio/canon notes, or archive surfaces.
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
WF78_PATH = ROOT / "tmp" / "wf78-tier-weighted-freshness-resolution.json"
FINANCE_STATE_DB = ROOT / "tmp" / "finance-intelligence-state.sqlite"
BAND_PROPOSALS = ROOT / "tmp" / "band-proposals.json"
AUTO_BAND_APPLY = ROOT / "tmp" / "auto-band-apply.json"
ANCHOR_PILOT = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
MISSING_BAND_CONTEXT = ROOT / "tmp" / "wf78-missing-band-context-repair.json"
OUT = ROOT / "tmp" / "reference-levels-targeted-repair-packet.json"
MD_OUT = ROOT / "tmp" / "reference-levels-targeted-repair-packet.md"

SCHEMA = "veritas.reference_levels_targeted_repair_packet.v1"
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
    "sql_mutation_performed": False,
    "source_lineage_mutation_performed": False,
    "registry_writer_allowed_now": False,
    "consumer_cutover_performed": False,
    "archive_move_or_delete_performed": False,
    "portfolio_or_canon_note_mutation_performed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
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
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA query_only=ON")
    return conn


def numeric_complete(row: dict[str, Any] | None) -> bool:
    return bool(row) and all(row.get(field) is not None for field in PRICE_FIELDS)


def current_hash_for_source(source_path: str) -> str | None:
    if not source_path:
        return None
    path = ROOT / source_path
    return sha256_file(path)


def json_rows_by_ticker(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(payload.get(key)):
        row = as_dict(item)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            rows[ticker] = row
    return rows


def finance_state_refs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with connect_readonly(path) as conn:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "entry_stop_reference" not in tables:
            return {}
        rows = conn.execute(
            """
            SELECT ticker, entry_band_low, entry_band_high, stop_or_invalidation,
                   freshness_status, validation_status, source_artifact_path,
                   source_timestamp, owner_note_path
            FROM entry_stop_reference
            """
        ).fetchall()
    return {str(row["ticker"]).upper(): dict(row) for row in rows}


def read_sql_state(db_path: Path) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], str]:
    with connect_readonly(db_path) as conn:
        active = [
            str(row["ticker"]).upper()
            for row in conn.execute("SELECT ticker FROM securities WHERE active=1 ORDER BY ticker")
        ]
        refs = {
            str(row["ticker"]).upper(): dict(row)
            for row in conn.execute(f"SELECT {', '.join(REFERENCE_COLUMNS)} FROM reference_levels")
        }
        lineage: dict[str, list[dict[str, Any]]] = {}
        for row in conn.execute(
            """
            SELECT scope_key AS ticker, field_name, source_artifact_path,
                   source_artifact_sha256, source_generated_at_utc, source_status,
                   validator_status, fallback_rule, authority_class
            FROM source_lineage
            WHERE field_family='reference_levels'
            """
        ):
            ticker = str(row["ticker"]).upper()
            lineage.setdefault(ticker, []).append(dict(row))
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    return active, refs, lineage, integrity


def candidate_numeric_sources(
    ticker: str,
    wf78_rows: dict[str, dict[str, Any]],
    finance_refs: dict[str, dict[str, Any]],
    band_proposals: dict[str, dict[str, Any]],
    missing_band_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    wf78 = wf78_rows.get(ticker, {})
    candidates.append(
        {
            "source": "tmp/wf78-tier-weighted-freshness-resolution.json",
            "low": wf78.get("tier_c_monitor_reference_band_low"),
            "high": wf78.get("tier_c_monitor_reference_band_high"),
            "stop": wf78.get("tier_c_monitor_reference_stop"),
            "status": "complete" if all(wf78.get(k) is not None for k in ("tier_c_monitor_reference_band_low", "tier_c_monitor_reference_band_high", "tier_c_monitor_reference_stop")) else "missing_numeric_values",
            "source_status": wf78.get("resolution_state"),
        }
    )
    fin = finance_refs.get(ticker, {})
    candidates.append(
        {
            "source": "tmp/finance-intelligence-state.sqlite:entry_stop_reference",
            "low": fin.get("entry_band_low"),
            "high": fin.get("entry_band_high"),
            "stop": fin.get("stop_or_invalidation"),
            "status": "complete" if all(fin.get(k) is not None for k in ("entry_band_low", "entry_band_high", "stop_or_invalidation")) else "missing_numeric_values",
            "source_status": fin.get("validation_status"),
        }
    )
    proposal = band_proposals.get(ticker, {})
    candidates.append(
        {
            "source": "tmp/band-proposals.json",
            "low": proposal.get("suggested_band_low"),
            "high": proposal.get("suggested_band_high"),
            "stop": proposal.get("suggested_stop"),
            "status": "complete" if all(proposal.get(k) is not None for k in ("suggested_band_low", "suggested_band_high", "suggested_stop")) else "missing_numeric_values",
            "source_status": "proposal_available" if proposal else "missing_proposal",
        }
    )
    missing_band = missing_band_rows.get(ticker, {})
    missing_band_values = as_dict(missing_band.get("band"))
    missing_band_complete = all(
        missing_band_values.get(k) is not None
        for k in ("entry_band_low", "entry_band_high", "stop_or_invalidation")
    )
    candidates.append(
        {
            "source": "tmp/wf78-missing-band-context-repair.json",
            "low": missing_band_values.get("entry_band_low"),
            "high": missing_band_values.get("entry_band_high"),
            "stop": missing_band_values.get("stop_or_invalidation"),
            "status": (
                "complete_review_only_authority_required"
                if missing_band_complete
                else "missing_numeric_values"
            ),
            "source_status": missing_band.get("repair_status") or "missing_repair_row",
            "authority_blocker": (
                "missing_band_context_repair_stop_line_blocks_direct_canon_or_sql_apply"
                if missing_band_complete
                else None
            ),
        }
    )
    return candidates


def price_lineage_sources(lineage_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["field_name"]): row
        for row in lineage_rows
        if str(row.get("field_name")) in PRICE_FIELDS
    }


def mismatch_repair(
    ticker: str,
    ref: dict[str, Any],
    lineages: dict[str, dict[str, Any]],
    *,
    band_apply_rows: dict[str, dict[str, Any]],
    band_hash: str | None,
    anchor_payload: dict[str, Any],
    anchor_hash: str | None,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    source = str(ref.get("source_artifact_path") or "")
    current_hash = current_hash_for_source(source)
    lineage_updates: list[dict[str, Any]] = []
    blockers: list[str] = []
    if source == "tmp/band-proposals.json":
        if ticker not in band_apply_rows:
            blockers.append("band_apply_row_missing")
        if ref.get("source_artifact_sha256") != band_hash:
            blockers.append("band_proposals_hash_mismatch")
        if not blockers:
            for field in PRICE_FIELDS:
                lineage_updates.append(
                    {
                        "ticker": ticker,
                        "field_name": field,
                        "proposed_source_artifact_path": source,
                        "proposed_source_artifact_sha256": band_hash,
                        "proposed_source_generated_at_utc": ref.get("source_generated_at_utc"),
                        "proposed_fallback_rule": ref.get("fallback_rule"),
                    }
                )
            return "eligible_source_lineage_repair_dry_run_only", lineage_updates, blockers
    elif source == "tmp/execution-board-canon-anchor-pilot.json":
        anchors = {
            str(as_dict(item).get("ticker") or "").upper(): as_dict(item)
            for item in as_list(anchor_payload.get("anchors"))
        }
        if ticker not in anchors:
            blockers.append("anchor_pilot_current_file_missing_ticker")
        if ref.get("source_artifact_sha256") != anchor_hash:
            blockers.append("anchor_pilot_hash_mismatch_current_file_not_reproducible")
        if current_hash != ref.get("source_artifact_sha256"):
            blockers.append("current_source_hash_differs_from_sql_row")
    else:
        blockers.append("unsupported_reference_source_for_lineage_repair")

    if not set(lineages) >= set(PRICE_FIELDS):
        blockers.append("price_lineage_fields_incomplete")
    return "blocked_source_authority_or_reproducibility_required", lineage_updates, sorted(set(blockers))


def build_packet(
    *,
    db_path: Path,
    wf78_path: Path,
    finance_state_db: Path,
    band_proposals_path: Path,
    auto_band_apply_path: Path,
    anchor_pilot_path: Path,
    missing_band_context_path: Path,
) -> dict[str, Any]:
    active, refs, lineage, integrity = read_sql_state(db_path)
    wf78_payload = load_json(wf78_path)
    finance_refs = finance_state_refs(finance_state_db)
    band_payload = load_json(band_proposals_path)
    auto_apply_payload = load_json(auto_band_apply_path)
    anchor_payload = load_json(anchor_pilot_path)
    missing_band_payload = load_json(missing_band_context_path)

    wf78_rows = json_rows_by_ticker(wf78_payload, "rows")
    band_proposals = json_rows_by_ticker(band_payload, "proposals")
    band_apply_rows = json_rows_by_ticker(auto_apply_payload, "applied")
    missing_band_rows = json_rows_by_ticker(missing_band_payload, "rows")
    band_hash = sha256_file(band_proposals_path)
    anchor_hash = sha256_file(anchor_pilot_path)

    rows: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    dry_run_reference_updates: list[dict[str, Any]] = []
    dry_run_lineage_updates: list[dict[str, Any]] = []

    for ticker in active:
        ref = refs.get(ticker)
        lineages = price_lineage_sources(lineage.get(ticker, []))
        issues: list[str] = []
        classification = "clean"
        blockers: list[str] = []
        numeric_sources: list[dict[str, Any]] = []
        lineage_updates: list[dict[str, Any]] = []

        if not numeric_complete(ref):
            issues.append("numeric_reference_fields_incomplete")
            numeric_sources = candidate_numeric_sources(ticker, wf78_rows, finance_refs, band_proposals, missing_band_rows)
            complete_sources = [item for item in numeric_sources if item["status"] == "complete"]
            review_only_sources = [
                item for item in numeric_sources if item["status"] == "complete_review_only_authority_required"
            ]
            if complete_sources:
                classification = "eligible_reference_level_numeric_repair_dry_run_only"
                dry_run_reference_updates.append({"ticker": ticker, "source": complete_sources[0]})
            elif review_only_sources:
                classification = "blocked_numeric_source_available_but_apply_authority_missing"
                blockers.append(str(review_only_sources[0].get("authority_blocker")))
            else:
                classification = "blocked_missing_numeric_source_evidence"
                blockers.append("no_current_source_has_complete_low_high_stop")

        if ref and set(lineages) >= set(PRICE_FIELDS):
            lineage_source_set = {str(row.get("source_artifact_path")) for row in lineages.values()}
            if ref.get("source_artifact_path") not in lineage_source_set:
                issues.append("reference_row_source_not_in_price_lineage")
                classification, lineage_updates, mismatch_blockers = mismatch_repair(
                    ticker,
                    ref,
                    lineages,
                    band_apply_rows=band_apply_rows,
                    band_hash=band_hash,
                    anchor_payload=anchor_payload,
                    anchor_hash=anchor_hash,
                )
                blockers.extend(mismatch_blockers)
                dry_run_lineage_updates.extend(lineage_updates)
        elif ref:
            issues.append("missing_complete_price_field_lineage")
            blockers.append("price_lineage_fields_incomplete")

        if issues:
            issue_counts.update(issues)
            rows.append(
                {
                    "ticker": ticker,
                    "classification": classification,
                    "issues": issues,
                    "blockers": sorted(set(blockers)),
                    "current_reference": {key: ref.get(key) for key in REFERENCE_COLUMNS if ref} if ref else None,
                    "price_lineage_sources": {field: row.get("source_artifact_path") for field, row in lineages.items()},
                    "numeric_source_candidates": numeric_sources,
                    "dry_run_lineage_updates": lineage_updates,
                    "dry_run_action": (
                        "source_lineage_update_candidate_no_write"
                        if lineage_updates
                        else "retain_blocked_until_source_evidence_or_authority_policy"
                    ),
                }
            )

    class_counts = Counter(row["classification"] for row in rows)
    blocked_count = sum(1 for row in rows if row["classification"].startswith("blocked"))
    eligible_count = sum(1 for row in rows if row["classification"].startswith("eligible"))
    sql_first_reference_provenance_clean = not rows
    if sql_first_reference_provenance_clean:
        next_safe_action = "rerun_sql_native_source_family_proof_and_retain_sql_first_reference_levels_as_current_owner"
    elif class_counts.get("blocked_numeric_source_available_but_apply_authority_missing"):
        next_safe_action = "define_approved_sql_reference_level_source_policy_or_gated_writer_for_review_only_band_context_before_registry_writer"
    elif blocked_count:
        next_safe_action = "capture_fresh_numeric_entry_stop_source_for_blocked_rows_before_registry_writer"
    else:
        next_safe_action = "prepare_gated_source_lineage_repair_writer_dry_run_then_rerun_source_family_proof"
    status = "ok" if not rows else "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "db_path": rel(db_path),
        "authority": dict(AUTHORITY),
        "sqlite": {
            "integrity_check": integrity,
            "query_only": True,
            "active_ticker_count": len(active),
            "reference_row_count": len(refs),
        },
        "inputs": {
            "wf78_resolution": rel(wf78_path),
            "finance_state_db": rel(finance_state_db),
            "band_proposals": rel(band_proposals_path),
            "auto_band_apply": rel(auto_band_apply_path),
            "anchor_pilot": rel(anchor_pilot_path),
            "missing_band_context": rel(missing_band_context_path),
            "band_proposals_sha256": band_hash,
            "anchor_pilot_sha256": anchor_hash,
        },
        "summary": {
            "target_issue_row_count": len(rows),
            "blocked_row_count": blocked_count,
            "eligible_repair_row_count": eligible_count,
            "classification_counts": dict(sorted(class_counts.items())),
            "issue_counts": dict(sorted(issue_counts.items())),
            "dry_run_reference_update_count": len(dry_run_reference_updates),
            "dry_run_source_lineage_update_count": len(dry_run_lineage_updates),
            "registry_writer_allowed_now": False,
            "sql_first_reference_provenance_clean": sql_first_reference_provenance_clean,
            "reference_source_family_proof_can_pass_now": sql_first_reference_provenance_clean,
            "next_safe_action": next_safe_action,
        },
        "rows": rows,
        "dry_run_diff": {
            "reference_level_updates": dry_run_reference_updates,
            "source_lineage_updates": dry_run_lineage_updates,
            "sql_update_count": 0,
            "source_lineage_update_count": 0,
            "note": "Planner only. No SQL or source_lineage writes were performed.",
        },
        "stop_lines": [
            "Do not run the SQL consumer registry writer while blocked_row_count is non-zero.",
            "Do not backfill numeric reference levels without complete low/high/stop source evidence.",
            "Do not use stale anchor-pilot rows as reproducible authority when the current artifact no longer contains the ticker.",
            "No portfolio/canon note, archive/delete, capital, paper/live, brokerage, account, customer, or approval authority.",
        ],
    }


def render_md(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        "# Reference Levels Targeted Repair Packet",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- Target issue rows: `{summary['target_issue_row_count']}`",
        f"- Blocked rows: `{summary['blocked_row_count']}`",
        f"- Eligible repair rows: `{summary['eligible_repair_row_count']}`",
        f"- Dry-run reference updates: `{summary['dry_run_reference_update_count']}`",
        f"- Dry-run source-lineage updates: `{summary['dry_run_source_lineage_update_count']}`",
        f"- Registry writer allowed now: `{summary['registry_writer_allowed_now']}`",
        "",
        "## Classification Counts",
    ]
    for key, value in summary["classification_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Rows"])
    for row in packet["rows"]:
        lines.append(
            f"- `{row['ticker']}`: `{row['classification']}`; "
            f"issues `{', '.join(row['issues'])}`; "
            f"blockers `{', '.join(row['blockers']) or 'none'}`"
        )
    lines.extend(["", "## Stop Lines"])
    for line in packet["stop_lines"]:
        lines.append(f"- {line}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--wf78", type=Path, default=WF78_PATH)
    parser.add_argument("--finance-state-db", type=Path, default=FINANCE_STATE_DB)
    parser.add_argument("--band-proposals", type=Path, default=BAND_PROPOSALS)
    parser.add_argument("--auto-band-apply", type=Path, default=AUTO_BAND_APPLY)
    parser.add_argument("--anchor-pilot", type=Path, default=ANCHOR_PILOT)
    parser.add_argument("--missing-band-context", type=Path, default=MISSING_BAND_CONTEXT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    packet = build_packet(
        db_path=resolve(args.db),
        wf78_path=resolve(args.wf78),
        finance_state_db=resolve(args.finance_state_db),
        band_proposals_path=resolve(args.band_proposals),
        auto_band_apply_path=resolve(args.auto_band_apply),
        anchor_pilot_path=resolve(args.anchor_pilot),
        missing_band_context_path=resolve(args.missing_band_context),
    )
    if args.write:
        atomic_write_json(resolve(args.output), packet)
    if args.write_md:
        atomic_write_text(resolve(args.md_output), render_md(packet))

    errors: list[str] = []
    if packet["sqlite"]["integrity_check"] != "ok":
        errors.append("sqlite_integrity_not_ok")
    if packet["sqlite"]["active_ticker_count"] != 200:
        errors.append("active_ticker_count_not_200")
    if packet["authority"]["sql_mutation_performed"] or packet["authority"]["source_lineage_mutation_performed"]:
        errors.append("unexpected_mutation_flag")
    if packet["summary"]["registry_writer_allowed_now"]:
        errors.append("registry_writer_unexpectedly_allowed")
    result = {
        "status": "error" if errors else "ok",
        "proof_status": packet["status"],
        "errors": errors,
        "summary": packet["summary"],
        "written": [rel(resolve(args.output))] if args.write else [],
    }
    if args.write_md:
        result["written"].append(rel(resolve(args.md_output)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.validate and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
