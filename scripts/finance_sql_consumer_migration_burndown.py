#!/usr/bin/env python3
"""Build a review-only burn-down packet for SQL consumer migration."""

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
OUT = ROOT / "tmp" / "finance-sql-consumer-migration-burndown.json"
MD_OUT = ROOT / "tmp" / "finance-sql-consumer-migration-burndown.md"
SCHEMA_VERSION = "finance_sql_consumer_migration_burndown.v1"

AUTHORITY = {
    "review_only": True,
    "consumer_migration_planning_only": True,
    "db_row_mutation_performed": False,
    "schema_mutation_performed": False,
    "consumer_file_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
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


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA query_only=ON")
    return conn


def priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(priority, 9)


def lane_rank(lane: str) -> int:
    order = {
        "answer_path_parity_lane": 0,
        "reference_level_parity_lane": 1,
        "source_lineage_parity_lane": 2,
        "evidence_freshness_parity_lane": 3,
        "tier_routing_parity_lane": 4,
    }
    return order.get(lane, 8)


def load_registry(db_path: Path) -> list[dict[str, Any]]:
    with connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT consumer_path, consumer_type, priority, migration_lane, cutover_state,
                   fallback_required, parity_required, raw_sql_needs_review,
                   source_artifact_path, source_artifact_sha256, registered_at_utc
            FROM consumer_migration_registry
            ORDER BY priority, migration_lane, consumer_path
            """
        ).fetchall()
    return [dict(row) for row in rows]


def group_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["priority"]),
            str(row["migration_lane"]),
            str(row["consumer_type"]),
            str(row["cutover_state"]),
        )
        grouped[key].append(row)
    groups: list[dict[str, Any]] = []
    for (priority, lane, consumer_type, state), items in grouped.items():
        fallback_count = sum(int(item["fallback_required"] or 0) for item in items)
        parity_count = sum(int(item["parity_required"] or 0) for item in items)
        raw_review_count = sum(int(item["raw_sql_needs_review"] or 0) for item in items)
        groups.append(
            {
                "priority": priority,
                "migration_lane": lane,
                "consumer_type": consumer_type,
                "cutover_state": state,
                "consumer_count": len(items),
                "fallback_required_count": fallback_count,
                "parity_required_count": parity_count,
                "raw_sql_needs_review_count": raw_review_count,
                "sample_consumers": [item["consumer_path"] for item in items[:8]],
                "recommended_next_action": recommended_action(state, lane, raw_review_count),
                "cutover_allowed_now": False,
            }
        )
    return sorted(groups, key=lambda item: (priority_rank(item["priority"]), lane_rank(item["migration_lane"]), item["cutover_state"], item["consumer_type"]))


def recommended_action(state: str, lane: str, raw_review_count: int) -> str:
    if state == "sql_primary_guarded":
        return "monitor guard and fallback; no migration action needed in this packet"
    if state == "sql_shadow_validated":
        return "prepare guarded SQL-primary cutover only after field-family parity remains clean for two windows"
    if raw_review_count:
        return "review raw SQL usage before any cutover"
    if lane == "reference_level_parity_lane":
        return "wait for reference_levels all-42 parity repair before consumer cutover"
    return "build focused A/B parity proof with fallback retained"


def build_report(db_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    if not db_path.exists():
        errors.append(f"finance canon DB missing: {rel(db_path)}")
        rows: list[dict[str, Any]] = []
    else:
        rows = load_registry(db_path)
    states = Counter(str(row["cutover_state"]) for row in rows)
    priorities = Counter(str(row["priority"]) for row in rows)
    lanes = Counter(str(row["migration_lane"]) for row in rows)
    source_producer_rows = [row for row in rows if row.get("cutover_state") == "source_producer"]
    shadow_rows = [row for row in rows if row.get("cutover_state") == "sql_shadow_validated"]
    groups = group_rows(rows)
    next_batches = [
        group
        for group in groups
        if group["cutover_state"] in {"source_producer", "sql_shadow_validated"}
    ][:12]
    if source_producer_rows:
        warnings.append(f"{len(source_producer_rows)} consumers remain source_producer.")
    if shadow_rows:
        warnings.append(f"{len(shadow_rows)} consumers are shadow validated but not SQL-primary.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "generated_at_utc": generated_at,
        "authority": AUTHORITY,
        "source": {"db_path": rel(db_path), "table": "consumer_migration_registry"},
        "summary": {
            "registry_total": len(rows),
            "sql_primary_guarded": int(states.get("sql_primary_guarded", 0)),
            "sql_shadow_validated": int(states.get("sql_shadow_validated", 0)),
            "source_producer": int(states.get("source_producer", 0)),
            "state_counts": dict(states),
            "priority_counts": dict(priorities),
            "migration_lane_counts": dict(lanes),
            "group_count": len(groups),
            "cutover_performed": False,
        },
        "groups": groups,
        "recommended_next_batches": next_batches,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
            "consumer_cutover_allowed": False,
            "apply_blocker": "reference_levels parity and per-consumer A/B proof required before cutover",
        },
    }


def render_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Finance SQL Consumer Migration Burn-Down",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Registry rows: `{summary.get('registry_total', 0)}`",
        f"- SQL-primary guarded: `{summary.get('sql_primary_guarded', 0)}`",
        f"- Shadow validated: `{summary.get('sql_shadow_validated', 0)}`",
        f"- Source producer: `{summary.get('source_producer', 0)}`",
        "",
        "This packet ranks migration work only. It does not change consumers or SQL.",
        "",
        "## Recommended Next Batches",
        "",
        "| Priority | Lane | State | Consumers | Action |",
        "|---|---|---|---:|---|",
    ]
    for group in report.get("recommended_next_batches", []):
        lines.append(
            "| {priority} | {lane} | {state} | {count} | {action} |".format(
                priority=group["priority"],
                lane=group["migration_lane"],
                state=group["cutover_state"],
                count=group["consumer_count"],
                action=group["recommended_next_action"],
            )
        )
    if report.get("validation", {}).get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["validation"]["warnings"])
    lines.extend(["", "## Stop Lines", ""])
    lines.append("- No consumer cutover in this packet.")
    lines.append("- No SQL data/schema write.")
    lines.append("- No Python fallback retirement.")
    lines.append("- No finance answer-path promotion.")
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
        summary = report.get("summary", {})
        print(
            "status={status} registry={registry} sql_primary={primary} shadow={shadow} source_producer={source}".format(
                status=report["status"],
                registry=summary.get("registry_total", 0),
                primary=summary.get("sql_primary_guarded", 0),
                shadow=summary.get("sql_shadow_validated", 0),
                source=summary.get("source_producer", 0),
            )
        )
    if args.validate and report.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
