#!/usr/bin/env python3
"""Build the review-only SQL-primary finance migration plan.

This packet records Randall's current direction: finish the SQL-primary
finance-state migration with schedule and parity gates. It does not mutate the
finance canon database, human canon notes, cron schedules, archives, or
consumer files.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT = ROOT / "tmp" / "finance-sql-primary-migration-plan.json"
MD_OUT = ROOT / "tmp" / "finance-sql-primary-migration-plan.md"

SCHEMA_VERSION = "finance_sql_primary_migration_plan.v1"

AUTHORITY = {
    "review_only": True,
    "sql_primary_migration_target_committed": True,
    "schedule_and_parity_plan_allowed": True,
    "db_row_mutation_performed": False,
    "schema_mutation_performed": False,
    "consumer_file_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "human_canon_mutation_performed": False,
    "archive_move_or_delete_performed": False,
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


def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def grouped_counts(conn: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    if column not in table_columns(conn, table):
        return {}
    rows = conn.execute(
        f'SELECT "{column}" AS key, COUNT(*) AS count FROM "{table}" GROUP BY "{column}" ORDER BY count DESC, key'
    ).fetchall()
    return {str(row["key"]): int(row["count"]) for row in rows}


def raw_json_sizes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for table in ["reference_levels", "universe_membership", "tier_routing_state", "evidence_freshness", "evidence_status"]:
        if "raw_json" not in table_columns(conn, table):
            continue
        row = conn.execute(f'SELECT COUNT(*) AS rows, COALESCE(SUM(LENGTH(raw_json)), 0) AS bytes FROM "{table}"').fetchone()
        result.append({"table": table, "rows": int(row["rows"]), "raw_json_bytes": int(row["bytes"])})
    return result


def reference_source_families(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not {"source_artifact_path", "source_generated_at_utc"} <= table_columns(conn, "reference_levels"):
        return []
    rows = conn.execute(
        """
        SELECT source_artifact_path, COUNT(*) AS rows,
               MIN(source_generated_at_utc) AS oldest_source_generated_at_utc,
               MAX(source_generated_at_utc) AS newest_source_generated_at_utc
        FROM reference_levels
        GROUP BY source_artifact_path
        ORDER BY rows DESC, source_artifact_path
        """
    ).fetchall()
    return [dict(row) for row in rows]


def build_db_probe(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"path": rel(db_path), "exists": False, "status": "missing"}
    with connect_readonly(db_path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        registry_rows = int(conn.execute("SELECT COUNT(*) FROM consumer_migration_registry").fetchone()[0])
        reference_rows = int(conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
        lineage_rows = int(conn.execute("SELECT COUNT(*) FROM source_lineage").fetchone()[0])
        return {
            "path": rel(db_path),
            "exists": True,
            "status": "ok" if integrity == "ok" else "blocked",
            "integrity_check": integrity,
            "consumer_migration_registry_rows": registry_rows,
            "reference_level_rows": reference_rows,
            "source_lineage_rows": lineage_rows,
            "cutover_state_counts": grouped_counts(conn, "consumer_migration_registry", "cutover_state"),
            "migration_lane_counts": grouped_counts(conn, "consumer_migration_registry", "migration_lane"),
            "priority_counts": grouped_counts(conn, "consumer_migration_registry", "priority"),
            "raw_sql_needs_review": int(
                conn.execute("SELECT COUNT(*) FROM consumer_migration_registry WHERE raw_sql_needs_review != 0").fetchone()[0]
            ),
            "fallback_required": int(
                conn.execute("SELECT COUNT(*) FROM consumer_migration_registry WHERE fallback_required != 0").fetchone()[0]
            ),
            "parity_required": int(
                conn.execute("SELECT COUNT(*) FROM consumer_migration_registry WHERE parity_required != 0").fetchone()[0]
            ),
            "reference_source_families": reference_source_families(conn),
            "raw_json_sizes": raw_json_sizes(conn),
        }


def migration_phases() -> list[dict[str, Any]]:
    return [
        {
            "phase": "0_current_lane",
            "objective": "Stop fake blockers and duplicate operator work while preserving all authority boundaries.",
            "parallel_work": [
                "Generate the SQL-primary migration packet and field-ownership classifier.",
                "Refresh SQL-native reference source-family proof and targeted repair packet.",
                "Run the old-anchor residue guard so active route/front-door surfaces cannot regress.",
            ],
            "acceptance": [
                "finance_sql_primary_migration_plan validates.",
                "finance_sql_markdown_field_ownership classifies every reconciliation row.",
                "reference_levels_sql_native_source_family_proof reports row_issue_counts={}.",
                "sql_canon_old_anchor_residue_guard reports no active old-anchor references.",
            ],
            "mutation_boundary": "scripts/tmp proof only in this lane.",
        },
        {
            "phase": "1_sql_first_reference_provenance",
            "objective": "Keep SQL reference_levels current-source metadata and source_lineage clean without relying on the retired Execution Board anchor packet.",
            "schedule": "daily after technical refresh, before PM/cron health packets read finance state",
            "parity_gate": [
                "current reference row source appears in selected price-field source_lineage",
                "row-level low/high/stop values have complete numeric evidence",
                "source artifact hash/timestamp matches the current row source",
            ],
            "required_before_apply": [
                "gated repair packet with exact target rows",
                "SQL backup/export and rollback drill",
                "post-write finance_sql_canon_access and source-family proof validation",
            ],
        },
        {
            "phase": "2_band_proposals_reference_source",
            "objective": "Use tmp/band-proposals.json as the current source for eligible band-maintenance repairs while SQL remains the 200-row canon owner.",
            "schedule": "daily technical refresh chain, not ad hoc one-shot backfill",
            "parity_gate": [
                "target rows match tmp/band-proposals.json low/high/stop values within cent tolerance",
                "numeric rewrite count is zero unless a separate gated value-repair packet exists",
                "single 200-row JSON source coverage remains informational, not a SQL-first blocker",
            ],
            "required_before_apply": [
                "SQL backup/export",
                "one-run dry-run diff for all affected rows",
                "rollback recipe",
                "post-write finance_sql_canon_access validation",
            ],
        },
        {
            "phase": "3_consumer_cutover_burndown",
            "objective": "Move remaining source_producer and shadow consumers to SQL-primary only when parity/fallback guards pass.",
            "schedule": "weekly burn-down packet; prioritize high-impact read paths first",
            "parity_gate": [
                "consumer output A/B equality or documented intended delta",
                "fallback retained until two clean windows",
                "consumer_migration_registry state updated only through a gated writer",
            ],
            "target_state": "all eligible finance-state consumers sql_primary_guarded; blocked families explicitly marked out of scope",
        },
        {
            "phase": "4_duplicate_surface_retirement",
            "objective": "Demote JSON mirrors, raw_json columns, and redundant sqlite surfaces only after parity and rollback proof.",
            "schedule": "separate owner-approved cleanup microbatches",
            "parity_gate": [
                "lineage covers fields removed from raw_json",
                "consumer search proves no active data dependency",
                "archive/delete apply path and restore recipe exist",
            ],
            "mutation_boundary": "no cleanup is authorized by this plan packet alone.",
        },
    ]


def build_report(db_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    db = build_db_probe(db_path)
    cutover = Counter(db.get("cutover_state_counts") or {})
    total = int(db.get("consumer_migration_registry_rows") or 0)
    sql_primary = int(cutover.get("sql_primary_guarded", 0))
    shadow = int(cutover.get("sql_shadow_validated", 0))
    source_producer = int(cutover.get("source_producer", 0))
    raw_json_total = sum(int(item["raw_json_bytes"]) for item in db.get("raw_json_sizes", []))
    ref_sources = db.get("reference_source_families") or []

    warnings: list[str] = []
    if source_producer:
        warnings.append(f"{source_producer} registry rows remain source_producer and need burn-down or explicit out-of-scope classification.")
    if len(ref_sources) > 1:
        warnings.append(
            f"reference_levels currently has {len(ref_sources)} source artifact families; SQL-first row-level provenance proof, not single-source JSON coverage, owns blocker status."
        )
    if raw_json_total:
        warnings.append(f"raw_json columns still carry {raw_json_total} bytes of duplicate payload pending a schema cleanup gate.")

    errors: list[str] = []
    if db.get("status") != "ok":
        errors.append("finance-canon DB integrity probe is not ok")
    if total <= 0:
        errors.append("consumer_migration_registry has no rows")
    if AUTHORITY["db_row_mutation_performed"] or AUTHORITY["human_canon_mutation_performed"]:
        errors.append("plan authority flags are unsafe")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "generated_at_utc": generated_at,
        "authority": AUTHORITY,
        "decision": {
            "sql_primary_migration_policy": "finish_sql_primary_migration_with_schedule_and_parity",
            "scope": "finance current-state routing, reference levels, source lineage, tier routing, evidence freshness, and eligible consumers",
            "not_in_scope": [
                "capital deployment approval",
                "paper/live order execution",
                "portfolio/canon note mutation without a gated apply packet",
                "archive/delete cleanup without a gated apply packet",
                "cron schedule mutation without WF76/cron authority approval",
            ],
        },
        "current_state": {
            "db": db,
            "registry_total": total,
            "sql_primary_guarded": sql_primary,
            "sql_shadow_validated": shadow,
            "source_producer": source_producer,
            "sql_primary_completion_pct": round((sql_primary / total) * 100, 2) if total else 0.0,
            "sql_or_shadow_pct": round(((sql_primary + shadow) / total) * 100, 2) if total else 0.0,
            "raw_json_total_bytes": raw_json_total,
            "reference_source_family_count": len(ref_sources),
        },
        "migration_phases": migration_phases(),
        "parallel_first_wave": [
            "field ownership classifier",
            "reference-levels targeted repair packet",
            "SQL-native source-family proof",
            "old-anchor active-route residue guard",
        ],
        "acceptance_commands": [
            "python scripts\\finance_sql_primary_migration_plan.py --write --write-md --validate",
            "python scripts\\finance_sql_markdown_field_ownership.py --write --validate",
            "python scripts\\reference_levels_targeted_repair_packet.py --write --validate",
            "python scripts\\reference_levels_sql_native_source_family_proof.py --write --validate",
            "python scripts\\sql_canon_old_anchor_residue_guard.py --write --validate",
            "python scripts\\artifact_index.py incremental",
            "python scripts\\changed_file_validator_router.py --write --validate",
        ],
        "warnings": warnings,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
        },
    }


def render_md(report: dict[str, Any]) -> str:
    state = report["current_state"]
    lines = [
        "# Finance SQL-Primary Migration Plan",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Decision: `{report['decision']['sql_primary_migration_policy']}`",
        "",
        "## Current State",
        "",
        f"- Registry rows: `{state['registry_total']}`",
        f"- SQL-primary guarded: `{state['sql_primary_guarded']}` (`{state['sql_primary_completion_pct']}%`)",
        f"- SQL shadow validated: `{state['sql_shadow_validated']}`",
        f"- Source producer rows: `{state['source_producer']}`",
        f"- Reference source families: `{state['reference_source_family_count']}`",
        f"- raw_json bytes pending cleanup gate: `{state['raw_json_total_bytes']}`",
        "",
        "## Phases",
        "",
    ]
    for phase in report["migration_phases"]:
        lines.append(f"### {phase['phase']}")
        lines.append(f"- Objective: {phase['objective']}")
        if phase.get("schedule"):
            lines.append(f"- Schedule: {phase['schedule']}")
        if phase.get("mutation_boundary"):
            lines.append(f"- Boundary: {phase['mutation_boundary']}")
        lines.append("")
    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
        lines.append("")
    lines.extend(["## Stop Lines", ""])
    lines.extend(f"- {item}" for item in report["decision"]["not_in_scope"])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--md-output", default=str(MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    report = build_report(db_path)
    if args.write:
        atomic_write_json(args.output, report)
    if args.write_md:
        atomic_write_text(args.md_output, render_md(report))
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        state = report["current_state"]
        print(
            "status={status} registry={registry} sql_primary={primary} shadow={shadow} source_producer={source}".format(
                status=report["status"],
                registry=state["registry_total"],
                primary=state["sql_primary_guarded"],
                shadow=state["sql_shadow_validated"],
                source=state["source_producer"],
            )
        )
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
