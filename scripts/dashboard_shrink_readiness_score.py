"""Score readiness for thinning/replacing the legacy dashboard payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

LEGACY = TMP / "dashboard-data.json"
THIN = TMP / "dashboard-data-thin-preview.json"
COMPAT = TMP / "dashboard-compatibility-payload.json"
COMPACT_ACCEPTANCE = TMP / "dashboard-presentation-acceptance.json"
SHELL_ACCEPTANCE = TMP / "dashboard-compact-shell-acceptance.json"
OUT = TMP / "dashboard-shrink-readiness-score.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_report() -> dict[str, Any]:
    legacy_size = LEGACY.stat().st_size if LEGACY.exists() else 0
    thin = as_dict(read_json(THIN)) if THIN.exists() else {}
    compat = as_dict(read_json(COMPAT)) if COMPAT.exists() else {}
    compact_acceptance = as_dict(read_json(COMPACT_ACCEPTANCE)) if COMPACT_ACCEPTANCE.exists() else {}
    shell_acceptance = as_dict(read_json(SHELL_ACCEPTANCE)) if SHELL_ACCEPTANCE.exists() else {}
    compact_bytes = int(as_dict(thin.get("summary")).get("compact_route_artifact_bytes") or 0)
    compat_summary = as_dict(compat.get("summary"))
    route_count = int(compat_summary.get("required_section_count") or 0)
    compact_coverage = int(compat_summary.get("compact_or_metadata_coverage_count") or 0)
    row_dependency_sections = as_list(compat_summary.get("current_js_row_table_dependency_sections"))
    shell_summary = as_dict(shell_acceptance.get("summary"))
    compact_shell_active_reader_ready = (
        as_dict(shell_acceptance).get("status") == "ok"
        and shell_summary.get("all_compact_panels_migrated") is True
        and shell_summary.get("legacy_payload_embedded") is False
    )
    blocker_details: list[dict[str, Any]] = []
    blockers = []
    if compat.get("drop_in_replacement_ready") is not True:
        blockers.append("compatibility_payload_not_drop_in_ready")
        blocker_details.append(
            {
                "blocker": "compatibility_payload_not_drop_in_ready",
                "reason": compat_summary.get("replacement_blocker")
                or "Current JS requires concrete DATA values that the compact route-ref payload does not include.",
                "exact_dependency_sections": row_dependency_sections,
                "current_js_row_table_dependency_count": compat_summary.get("current_js_row_table_dependency_count", len(row_dependency_sections)),
                "files_with_data_reads": compat_summary.get("current_js_files_with_data_reads"),
                "next_action": "Either migrate the legacy JS readers for these sections to compact view-model panels or build a drop-in compatibility payload containing these concrete row/object values.",
            }
        )
    if as_dict(compact_acceptance).get("status") != "ok":
        blockers.append("compact_acceptance_not_ok")
        blocker_details.append(
            {
                "blocker": "compact_acceptance_not_ok",
                "next_action": "Regenerate and validate the compact presentation acceptance artifact.",
            }
        )
    if as_dict(shell_acceptance).get("status") != "ok":
        blockers.append("compact_shell_acceptance_not_ok")
        blocker_details.append(
            {
                "blocker": "compact_shell_acceptance_not_ok",
                "next_action": "Regenerate and validate the compact shell before using it as a parallel reader.",
            }
        )
    if legacy_size == 0:
        blockers.append("legacy_payload_missing")
        blocker_details.append(
            {
                "blocker": "legacy_payload_missing",
                "next_action": "Regenerate the legacy dashboard payload before comparing shrink readiness.",
            }
        )
    readiness_pct = round((compact_coverage / route_count) * 100, 1) if route_count else 0.0
    size_pct = round((compact_bytes / legacy_size) * 100, 2) if legacy_size else 0.0
    compatibility_only_blocked = blockers == ["compatibility_payload_not_drop_in_ready"]
    legacy_retained_by_design = compact_shell_active_reader_ready and compatibility_only_blocked
    active_route_status = (
        "ready_compact_reader_legacy_retained"
        if legacy_retained_by_design
        else ("blocked" if blockers else "ready_for_legacy_payload_replacement")
    )
    active_route_blockers = [] if legacy_retained_by_design else blockers
    return {
        "schema_version": "dashboard_shrink_readiness_score.v1",
        "status": active_route_status,
        "replacement_ready": False if blockers else True,
        "legacy_retained_by_design": legacy_retained_by_design,
        "randall_full_detail_view_retained": True,
        "summary": {
            "required_route_count": route_count,
            "compact_or_metadata_coverage_count": compact_coverage,
            "route_coverage_pct": readiness_pct,
            "legacy_dashboard_bytes": legacy_size,
            "compact_route_artifact_bytes": compact_bytes,
            "compact_artifact_pct_of_legacy": size_pct,
            "blocker_count": len(active_route_blockers),
            "legacy_retirement_blocker_count": len(blockers),
            "compact_shell_active_reader_ready": compact_shell_active_reader_ready,
            "compact_shell_promotable_as_active_route": compact_shell_active_reader_ready,
            "legacy_payload_retained_by_design": legacy_retained_by_design,
            "randall_full_detail_view": "tmp/veritas-command-center.html",
            "veritas_first_read_view": "tmp/veritas-command-center-compact.html",
            "veritas_first_read_json": "tmp/veritas-command-center-compact-reader.json",
            "compact_shell_panel_count": shell_summary.get("panel_count"),
            "current_js_row_table_dependency_count": compat_summary.get("current_js_row_table_dependency_count", len(row_dependency_sections)),
            "current_js_row_table_dependency_sections": row_dependency_sections,
            "canonical_reader_debt_count": compat_summary.get("canonical_reader_debt_count", 0),
        },
        "blockers": active_route_blockers,
        "legacy_retirement_blockers": blockers,
        "blocker_details": [] if legacy_retained_by_design else blocker_details,
        "legacy_retirement_blocker_details": blocker_details,
        "active_reader_migration": {
            "compact_shell_ready": compact_shell_active_reader_ready,
            "all_compact_panels_migrated": shell_summary.get("all_compact_panels_migrated") is True,
            "legacy_payload_embedded": shell_summary.get("legacy_payload_embedded") is True,
            "legacy_payload_retained_by_design": legacy_retained_by_design,
            "randall_full_detail_view_retained": True,
            "legacy_dashboard_replaced": False,
            "result": "compact_shell_reader_promoted_legacy_retained_by_design"
            if legacy_retained_by_design
            else ("compact_shell_reader_ready_legacy_js_drop_in_blocked" if compact_shell_active_reader_ready and blockers
            else ("compact_shell_reader_ready" if compact_shell_active_reader_ready else "compact_shell_reader_not_ready"),
            )
        },
        "deployment_contract_safeguards": {
            "canonical_reader_debt": as_list(compat.get("deployment_contract_reader_debt")),
            "canonical_reader_debt_count": compat_summary.get("canonical_reader_debt_count", 0),
            "top_level_legacy_alias_reintroduction_allowed": False,
            "deployment_readiness_surface_alias_absence_verified_by": "scripts/deployment_contract_migration_validation_bundle.py --write --full",
        },
        "artifacts": {
            "legacy": relpath(LEGACY),
            "randall_full_detail_view": "tmp/veritas-command-center.html",
            "veritas_compact_shell": "tmp/veritas-command-center-compact.html",
            "veritas_compact_reader": "tmp/veritas-command-center-compact-reader.json",
            "thin_preview": relpath(THIN),
            "compatibility_payload": relpath(COMPAT),
            "compact_acceptance": relpath(COMPACT_ACCEPTANCE),
            "shell_acceptance": relpath(SHELL_ACCEPTANCE),
        },
        "authority": {
            "review_only": True,
            "legacy_dashboard_replaced": False,
            "legacy_payload_retained_by_design": True,
            "randall_full_detail_view_retained": True,
            "proof_deletion_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score dashboard shrink readiness.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"dashboard_shrink_readiness_score: {report['status']} ({len(report['blockers'])} blockers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
