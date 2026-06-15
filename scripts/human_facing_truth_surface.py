#!/usr/bin/env python3
"""Generate the compact human-facing truth surface for finance orientation.

This replaces scattered dashboard pickup with one review-only human surface.
It reads current proof artifacts and writes:

- 01. Dashboards/Executive Brief.md
- tmp/human-facing-truth-surface.json

It does not mutate portfolio/canon state, infer owner approval, or authorize
paper/live execution.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_index import DEFAULT_DB as ARTIFACT_INDEX_DB, validate_index
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "human-facing-truth-surface.json"
OUT_MD = ROOT / "01. Dashboards" / "Executive Brief.md"

SOURCES = {
    "finance_state_validation": TMP / "finance-intelligence-state-validation.json",
    "core_folder_watchdog": TMP / "core-folders-flattening-watchdog.json",
    "core_live_surface_migration": TMP / "core-live-surface-migration.json",
    "archive_delete_readiness": TMP / "archive-delete-readiness-plan.json",
    "artifact_index_validation": TMP / "artifact-index-validation.json",
    "dashboard_truth_lint": TMP / "dashboard-truth-lint.json",
    "workspace_boundary_check": TMP / "workspace-boundary-check.json",
    "workflow_hygiene": TMP / "workflow-hygiene-check.json",
    "pm_control_packet": TMP / "pm-control-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "human_orientation_surface": True,
    "generated_report_is_canonical": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_trade_execution_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "money_movement_allowed": False,
    "archive_apply_allowed_by_this_surface": False,
    "delete_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_sources() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for role, path in SOURCES.items():
        data = load_json_artifact(path)
        loaded[role] = data if isinstance(data, dict) else {}
    if not loaded["artifact_index_validation"] and ARTIFACT_INDEX_DB.exists():
        try:
            loaded["artifact_index_validation"] = validate_index(ARTIFACT_INDEX_DB)
        except Exception as exc:
            loaded["artifact_index_validation"] = {
                "status": "unavailable",
                "error": str(exc),
            }
    return loaded


def source_status(role: str, data: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "role": role,
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status") or data.get("overall") or ("ok" if data else "missing"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def build_surface() -> dict[str, Any]:
    sources = load_sources()
    finance = sources["finance_state_validation"]
    watchdog = sources["core_folder_watchdog"]
    migration = sources["core_live_surface_migration"]
    delete_plan = sources["archive_delete_readiness"]
    artifact_index = sources["artifact_index_validation"]
    truth_lint = sources["dashboard_truth_lint"]
    boundary = sources["workspace_boundary_check"]
    hygiene = sources["workflow_hygiene"]
    continuation = sources["heartbeat_continuation_candidates"]

    finance_summary = as_dict(finance.get("summary"))
    watchdog_summary = as_dict(watchdog.get("summary"))
    migration_summary = as_dict(migration.get("summary"))
    delete_summary = as_dict(delete_plan.get("summary"))
    delete_by_readiness = as_dict(delete_summary.get("by_delete_readiness"))
    lint_counts = as_dict(truth_lint.get("counts"))
    boundary_summary = as_dict(boundary.get("summary"))
    hygiene_summary = as_dict(hygiene.get("summary")) or as_dict(hygiene.get("counts"))

    residue: list[dict[str, Any]] = []
    if watchdog_summary.get("compress_live_count", 0):
        residue.append({
            "class": "compress_live",
            "count": watchdog_summary.get("compress_live_count"),
            "next_action": "Extract replacement summaries/SQL or JSON proof, then archive source-heavy notes by exact packet.",
        })
    if watchdog_summary.get("blocked_archive_candidate_count", 0):
        residue.append({
            "class": "blocked_archive_candidate",
            "count": watchdog_summary.get("blocked_archive_candidate_count"),
            "next_action": "Remove or update blocking script/control-surface references before moving.",
        })
    if delete_summary.get("delete_allowed_now_count", 0) == 0:
        residue.append({
            "class": "delete_blocked",
            "count": delete_by_readiness.get("delete_candidate_after_retention_and_restore_test"),
            "next_action": "Run retention/restore proof before any future delete helper exists.",
        })

    status = "review_only_warning"
    if (
        finance.get("status") == "ok"
        and artifact_index.get("status") == "ok"
        and boundary.get("status") == "ok"
        and truth_lint.get("status") == "ok"
    ):
        status = "review_only_ok"

    return {
        "schema_version": "human_facing_truth_surface.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sources": [
            source_status(role, sources[role], path)
            for role, path in SOURCES.items()
        ],
        "current_truth": {
            "finance_sql_state": {
                "status": finance.get("status"),
                "db_path": finance.get("db_path"),
                "universe_rows": finance_summary.get("universe_rows"),
                "current_ticker_cards": finance_summary.get("current_ticker_cards"),
                "latest_valid_entry_stop_refs": finance_summary.get("latest_valid_entry_stop_refs"),
                "sql_canon_authority_expanded": as_dict(finance.get("authority_boundary")).get("sql_canon_authority_expanded"),
                "full_sql_canon_migration_allowed": as_dict(finance.get("authority_boundary")).get("full_sql_canon_migration_allowed"),
            },
            "core_human_folders": {
                "files_scanned": watchdog_summary.get("files_scanned"),
                "eligible_archive_candidates": watchdog_summary.get("eligible_for_move_only_archive_count"),
                "blocked_archive_candidates": watchdog_summary.get("blocked_archive_candidate_count"),
                "compress_live_targets": watchdog_summary.get("compress_live_count"),
                "delete_allowed": watchdog_summary.get("delete_allowed"),
                "by_folder": watchdog_summary.get("by_folder") or {},
                "live_surface_migration": {
                    "status": migration.get("status"),
                    "earnings_scorecards_migrated": migration_summary.get("earnings_scorecards_migrated"),
                    "parser_compatible_surfaces_compressed": migration_summary.get("parser_compatible_surfaces_compressed"),
                    "audit_surfaces_compressed": migration_summary.get("audit_surfaces_compressed"),
                    "archives_written": migration_summary.get("archives_written"),
                    "archive_failures": migration_summary.get("archive_failures"),
                    "replacement_proof": migration.get("replacement_proof") or {},
                },
            },
            "archive_delete_plan": {
                "status": delete_plan.get("status"),
                "archive_files_scanned": delete_summary.get("archive_files_scanned"),
                "future_delete_candidates": delete_by_readiness.get("delete_candidate_after_retention_and_restore_test"),
                "delete_allowed_now": delete_summary.get("delete_allowed_now_count"),
            },
            "validators": {
                "artifact_index": artifact_index.get("status"),
                "workspace_boundary": boundary.get("status"),
                "dashboard_truth_lint": truth_lint.get("status"),
                "dashboard_truth_warnings": lint_counts.get("warnings"),
                "workflow_hygiene": hygiene.get("status"),
                "workflow_hygiene_blocking": hygiene_summary.get("blocking") if "blocking" in hygiene_summary else hygiene_summary.get("blocking_findings"),
            },
            "safe_continuation": {
                "status": continuation.get("status"),
                "handoff_ready_count": continuation.get("handoff_ready_count"),
                "blocked_count": continuation.get("blocked_count"),
            },
        },
        "canonical_routes": [
            {"need": "live finance/ticker proof", "route": "tmp/finance-intelligence-state.sqlite and tmp/ticker-intelligence-cards/"},
            {"need": "portfolio posture/model", "route": "03. Portfolio/Portfolio Snapshot.md"},
            {"need": "entry bands/stops/deployment state", "route": "03. Portfolio/Execution Board.md compact parser surface + state/finance/execution-board-replacement.json"},
            {"need": "research universe/watchlist", "route": "04. Research/Coverage and Watchlist.md compact parser surface + state/finance/coverage-watchlist-replacement.json"},
            {"need": "post-earnings scorecard lookup", "route": "05. Intelligence/Earnings/README.md + state/finance/earnings-scorecard-index.json"},
            {"need": "macro and regime", "route": "02. Markets/Macro Regime Dashboard.md plus tmp/macro-*.json artifacts"},
            {"need": "workflow status", "route": "06. Playbooks/Active Workflows.md and owning continuity notes"},
            {"need": "archive/delete posture", "route": "tmp/core-folders-flattening-watchdog.json and tmp/archive-delete-readiness-plan.json"},
        ],
        "residue": residue,
        "next_recommended_actions": [
            "Keep the new compact live surfaces parser-compatible while continuing to route source-open history through state/finance replacement proof and archive paths.",
            "Keep delete blocked until archived-file retention, restore drill, replacement proof, and a separate exact delete approval exist.",
            "Run the watchdog after each finance-chain or weekly hygiene pass so folders 01-05 stay flat.",
        ],
    }


def render_markdown(surface: dict[str, Any]) -> str:
    current = surface["current_truth"]
    finance = current["finance_sql_state"]
    folders = current["core_human_folders"]
    migration = folders.get("live_surface_migration") or {}
    delete_plan = current["archive_delete_plan"]
    validators = current["validators"]
    continuation = current["safe_continuation"]

    lines: list[str] = [
        "<!-- GENERATED REVIEW-ONLY SURFACE",
        f"Source JSON: {rel(OUT_JSON)}",
        f"Generated: {surface['generated_at_utc']}",
        "Authority: orientation only; not canon, approval, archive apply, delete apply, portfolio mutation, paper/live order, account action, or money movement.",
        "-->",
        "",
        "# Executive Brief",
        "",
        "## Bottom line",
        "",
        "This is the single fast human-facing truth surface for Randall and Veritas. It routes to the live proof owners and replaces scattered dashboard pickup notes as the first read.",
        "",
        f"- Status: **{surface['status']}**",
        f"- Generated: `{surface['generated_at_utc']}`",
        f"- Finance SQL state: `{finance.get('status')}` with `{finance.get('universe_rows')}` universe rows, `{finance.get('current_ticker_cards')}` current ticker cards, and `{finance.get('latest_valid_entry_stop_refs')}` latest valid entry/stop refs.",
        f"- SQL canon promotion: expanded authority is `{finance.get('sql_canon_authority_expanded')}`; full SQL canon migration allowed is `{finance.get('full_sql_canon_migration_allowed')}`.",
        f"- Core human folders 01-05: `{folders.get('files_scanned')}` live files, `{folders.get('eligible_archive_candidates')}` eligible archive candidates, `{folders.get('blocked_archive_candidates')}` blocked archive candidate, `{folders.get('compress_live_targets')}` compression targets.",
        f"- Live-surface migration: `{migration.get('status')}`; earnings `{migration.get('earnings_scorecards_migrated')}`, parser-compatible surfaces `{migration.get('parser_compatible_surfaces_compressed')}`, audit surfaces `{migration.get('audit_surfaces_compressed')}`, archived originals verified `{migration.get('archives_written')}`.",
        f"- Archive delete posture: `{delete_plan.get('status')}`; delete allowed now count is `{delete_plan.get('delete_allowed_now')}`.",
        "",
        "## Authority boundary",
        "",
        "This surface is review-only. It does not grant owner approval, canonical portfolio mutation, archive apply, delete apply, paper/live execution, brokerage/account action, sizing, sleeve, cash, risk-rule, customer delivery, or money-movement authority.",
        "",
        "## Validator posture",
        "",
        f"- Artifact index: `{validators.get('artifact_index')}`",
        f"- Workspace boundary: `{validators.get('workspace_boundary')}`",
        f"- Dashboard truth lint: `{validators.get('dashboard_truth_lint')}` with `{validators.get('dashboard_truth_warnings')}` warnings",
        f"- Workflow hygiene: `{validators.get('workflow_hygiene')}` with blocking count `{validators.get('workflow_hygiene_blocking')}`",
        f"- Heartbeat continuation candidates: `{continuation.get('status')}`, handoff-ready `{continuation.get('handoff_ready_count')}`, blocked `{continuation.get('blocked_count')}`",
        "",
        "## Canonical routes",
        "",
    ]
    for row in surface["canonical_routes"]:
        lines.append(f"- **{row['need']}** -> `{row['route']}`")
    lines.extend(["", "## Remaining residue", ""])
    for row in surface["residue"]:
        lines.append(f"- **{row['class']}**: `{row.get('count')}`. {row['next_action']}")
    lines.extend(["", "## Next actions", ""])
    for action in surface["next_recommended_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## Source proof", ""])
    for source in surface["sources"]:
        lines.append(
            f"- `{source['role']}` -> `{source['path']}` "
            f"(exists `{source['exists']}`, status `{source['status']}`, generated `{source.get('generated_at_utc')}`)"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    surface = build_surface()
    markdown = render_markdown(surface)
    if args.write:
        atomic_write_json(OUT_JSON, surface)
        atomic_write_text(OUT_MD, markdown)

    summary = {
        "status": surface["status"],
        "report": rel(OUT_JSON) if args.write else None,
        "markdown": rel(OUT_MD) if args.write else None,
        "finance_sql_state": surface["current_truth"]["finance_sql_state"]["status"],
        "live_core_files": surface["current_truth"]["core_human_folders"]["files_scanned"],
        "eligible_archive_candidates": surface["current_truth"]["core_human_folders"]["eligible_archive_candidates"],
        "compress_live_targets": surface["current_truth"]["core_human_folders"]["compress_live_targets"],
        "delete_allowed_now": surface["current_truth"]["archive_delete_plan"]["delete_allowed_now"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.validate and surface["current_truth"]["archive_delete_plan"]["delete_allowed_now"] not in (0, None):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
