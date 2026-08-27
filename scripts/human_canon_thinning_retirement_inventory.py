#!/usr/bin/env python3
"""Inventory human-canon thinning retirement candidates.

This is a review-only routing packet. It classifies validators/scripts/checks
after the human finance notes were thinned, but it never archives, deletes,
moves, mutates cron, mutates SQL/canon/portfolio state, or grants approval.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "human-canon-thinning-retirement-inventory.json"
SCHEMA = "veritas.human_canon_thinning_retirement_inventory.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "classification_only": True,
    "archive_allowed": False,
    "delete_allowed": False,
    "move_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

HUMAN_CONTEXT_SURFACES = [
    "03. Portfolio/Execution Board.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "04. Research/Coverage and Watchlist.md",
]

KEEP_ITEMS = [
    (
        "scripts/md_finance_structured_drift_lint.py",
        "thinning_guard",
        "Detects structured finance facts regrowing in human Markdown; keep targeted by changed-file route and governance sweeps.",
    ),
    (
        "scripts/finance_sql_markdown_field_ownership.py",
        "field_family_guard",
        "Classifies SQL-proof-only versus human-judgment fields so cross-class drift cannot create fake blockers.",
    ),
    (
        "scripts/validate_canonical_ownership.py",
        "thin_contract_boundary_guard",
        "Validates retired redirects, thin human-surface contracts, and note-layer ownership boundaries.",
    ),
    (
        "scripts/finance_sql_canon_access.py",
        "structured_owner_guard",
        "Typed SQL/JSON access layer for current structured state; not a retirement candidate.",
    ),
    (
        "scripts/trade_grade_full_answer_assembler.py",
        "default_answer_owner",
        "WF85 full-answer assembler is the replacement owner for legacy ticker answer packets.",
    ),
    (
        "scripts/finance_human_notes_thinning_candidates.py",
        "owner_review_lifecycle_planner",
        "Plans human-note thinning/archive candidates without applying archive/delete.",
    ),
    (
        "scripts/finance_human_notes_archive_apply.py",
        "owner_gated_apply_helper",
        "Retain only for exact owner-gated lifecycle apply path; not a routine validator.",
    ),
    (
        "scripts/sql_source_truth_authority_manifest.py",
        "source_truth_manifest",
        "Documents source-truth authority and source-open fallback; not old structured-note validation.",
    ),
]

NARROW_ON_DEMAND_ITEMS = [
    (
        "scripts/runtime_performance_scorecard.py:human_note_migration_group",
        "runtime_budget_contraction",
        "Run human-notes SQL/Go checks only under targeted migration mode, not default runtime performance scoring.",
    ),
    (
        "go-finance-human-notes-sql-check",
        "compiled_migration_probe",
        "Retain as targeted migration parity probe; do not pay this cost for unrelated closeout.",
    ),
    (
        "scripts/python_go_finance_human_notes_sql_check_parity.py",
        "migration_parity_probe",
        "Run when human-note SQL migration parity is in scope.",
    ),
    (
        "go-source-truth-parity-validator",
        "source_truth_migration_probe",
        "Retarget to SQL-native proof or keep as expected-pending migration evidence only.",
    ),
    (
        "scripts/python_go_source_truth_parity_validator_parity.py",
        "source_truth_migration_parity_probe",
        "Run with SQL/source-truth migration proof, not broad implementation closeout.",
    ),
    (
        "scripts/ticker_answer_packet.py",
        "legacy_compatibility_wrapper",
        "Keep for explicit legacy compatibility/retirement proof; default owner is trade_grade_full_answer_assembler.py.",
    ),
    (
        "scripts/veritas_technical_pass_validate.py",
        "skill_contract_validator",
        "Use after technical-pass skill edits; weak evidence for finance data readiness.",
    ),
    (
        "scripts/today_card_generator.py:human_note_links",
        "operator_context_label",
        "Keep Today card generator but label human notes as context links, not structured owners.",
    ),
    (
        "scripts/veritas_question_router.py:human_note_context_labels",
        "route_label_contraction",
        "Keep router SQL-first; label Markdown as human context/source-open fallback.",
    ),
]

RETIRE_CANDIDATES = [
    (
        "workflow_routing_index:WF85:ticker_answer_packet_default_validation",
        "routine_legacy_answer_packet_validation",
        "Remove routine WF85 use of ticker_answer_packet.py; keep only under compatibility/retirement proof.",
    ),
    (
        "validate_canonical_ownership.py:default_legacy_table_checks",
        "pre_thinning_table_contract_default",
        "Move old row/header/thesis completeness checks behind legacy mode.",
    ),
    (
        "runtime_performance_scorecard.py:default_human_note_parity_commands",
        "broad_runtime_cost",
        "Default runtime scoring should not rerun human-note SQL/Go migration parity checks.",
    ),
]

DO_NOT_RETIRE = [
    (
        "03. Portfolio/Execution Board.md",
        "thin_human_surface",
        "Still owns execution discipline, policy, owner decisions, and source-open context.",
    ),
    (
        "03. Portfolio/Portfolio Snapshot.md",
        "thin_human_surface",
        "Still owns human portfolio posture, policy, and durable allocation decisions.",
    ),
    (
        "04. Research/Coverage and Watchlist.md",
        "thin_human_surface",
        "Still owns human research index, thesis-work pointers, and owner research decisions.",
    ),
    (
        "source_feeders_for_wf84_wf85",
        "active_source_feeders",
        "Current retirement readiness shows source_feeder_retirement_ready_count=0.",
    ),
    (
        "python_default_sql_helpers",
        "python_owner_default",
        "Current helper retirement gate says retire_python_now_count=0 and Python fallback retained.",
    ),
    (
        "portfolio_canon_gate_validators",
        "authority_boundary_controls",
        "Retain validators that enforce exact approved portfolio/canon maintenance gates.",
    ),
    (
        "audit_provenance_backup_archive_ledgers",
        "provenance_controls",
        "Audit trails, backups, and tombstones are not cleanup targets.",
    ),
]

ARTIFACTS = {
    "md_structured_drift_lint": TMP / "md-finance-structured-drift-lint.json",
    "field_ownership": TMP / "finance-sql-markdown-field-ownership.json",
    "canonical_ownership": TMP / "canonical-ownership-validation.json",
    "data_plane_retirement": TMP / "canonical-finance-data-plane-retirement-readiness.json",
    "ticker_packet_retirement": TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json",
    "python_go_sql_helper_retirement": TMP / "python-go-sql-helper-retirement-gate.json",
    "go_human_notes_sql_check": TMP / "go-finance-human-notes-sql-check.json",
    "go_human_notes_parity": TMP / "python-go-finance-human-notes-sql-check-parity.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def artifact_status(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    data = as_dict(payload)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
        "summary": data.get("summary"),
    }


def row(path: str, classification: str, reason: str, category: str) -> dict[str, Any]:
    filesystem_path = ROOT / path if "." in Path(path).name or "/" in path else None
    return {
        "path": path,
        "category": category,
        "classification": classification,
        "reason": reason,
        "exists": filesystem_path.exists() if filesystem_path else None,
    }


def rows(items: list[tuple[str, str, str]], category: str) -> list[dict[str, Any]]:
    return [row(path, classification, reason, category) for path, classification, reason in items]


def build_inventory() -> dict[str, Any]:
    artifacts = {name: artifact_status(path) for name, path in ARTIFACTS.items()}
    keep = rows(KEEP_ITEMS, "keep")
    narrow = rows(NARROW_ON_DEMAND_ITEMS, "narrow_on_demand")
    retire = rows(RETIRE_CANDIDATES, "retire_candidate")
    do_not_retire = rows(DO_NOT_RETIRE, "do_not_retire")

    categories = {
        "keep": keep,
        "narrow_on_demand": narrow,
        "retire_candidate": retire,
        "do_not_retire": do_not_retire,
    }
    category_counts = {name: len(items) for name, items in categories.items()}
    existing_status_counts = Counter(
        str(item.get("exists")) for items in categories.values() for item in items if item.get("exists") is not None
    )
    warnings: list[str] = []
    if as_dict(artifacts["md_structured_drift_lint"].get("summary")).get("requires_action_count") not in {0, None}:
        warnings.append("md_structured_drift_lint_has_active_thinning_work")
    if as_dict(artifacts["data_plane_retirement"].get("summary")).get("source_feeder_retirement_ready_count") not in {0, None}:
        warnings.append("source_feeder_retirement_ready_nonzero_review_before_contracting")
    if as_dict(artifacts["python_go_sql_helper_retirement"].get("summary")).get("retire_python_now_count") not in {0, None}:
        warnings.append("python_helper_retirement_ready_nonzero_review_before_contracting")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning" if warnings else "ok",
        "purpose": "Classify post-thinning human-canon validators/scripts/checks for retention, on-demand routing, or future retirement proposal.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "human_context_surfaces": HUMAN_CONTEXT_SURFACES,
        "summary": {
            "category_counts": category_counts,
            "item_count": sum(category_counts.values()),
            "existing_status_counts": dict(existing_status_counts),
            "archive_or_delete_candidates_ready_now": 0,
            "cron_schedule_mutation_ready_now": 0,
            "next_safe_action": "Patch validator routing and labels only; prepare separate owner-gated lifecycle packets before any archive/delete.",
        },
        "categories": categories,
        "source_artifacts": artifacts,
        "validation": {
            "status": "warning" if warnings else "ok",
            "errors": [],
            "warnings": warnings,
        },
    }


def validate_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    categories = as_dict(payload.get("categories"))
    for category in ("keep", "narrow_on_demand", "retire_candidate", "do_not_retire"):
        values = categories.get(category)
        if not isinstance(values, list) or not values:
            errors.append(f"missing_category:{category}")
    if int(as_dict(payload.get("summary")).get("archive_or_delete_candidates_ready_now") or 0) != 0:
        errors.append("archive_delete_ready_must_be_zero")
    if int(as_dict(payload.get("summary")).get("cron_schedule_mutation_ready_now") or 0) != 0:
        errors.append("cron_mutation_ready_must_be_zero")
    if as_dict(payload.get("validation")).get("warnings"):
        warnings.extend(as_dict(payload.get("validation")).get("warnings") or [])
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_inventory()
    validation = validate_inventory(payload)
    payload["validation"] = validation
    if validation["status"] == "error":
        payload["status"] = "blocked"
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            f"status={payload['status']} items={summary['item_count']} "
            f"retire_candidates={summary['category_counts']['retire_candidate']} out={rel(out)}"
        )
    if args.validate and validation["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
