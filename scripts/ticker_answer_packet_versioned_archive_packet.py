#!/usr/bin/env python3
"""Build the owner-review packet for a versioned legacy-42 archive.

This resolves the current preview-archive hash conflict by proposing a new
versioned archive root. It is proof-only: it does not create the archive
folder, move files, delete files, overwrite anything, or retire fallbacks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PLAN = TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json"
ARCHIVE_APPLY = TMP / "ticker-answer-packet-archive-apply-current.json"
DEFAULT_OUT = TMP / "ticker-answer-packet-versioned-archive-approval.json"
ARCHIVE_PARENT = ROOT / "09. Archive" / "WF85 Legacy Ticker Answer Packets"
PREVIEW_ARCHIVE_ROOT = ARCHIVE_PARENT / "preview"
SCHEMA = "veritas.ticker_answer_packet_versioned_archive_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "approval_packet_only": True,
    "archive_allowed_now": False,
    "delete_allowed_now": False,
    "move_allowed_now": False,
    "overwrite_allowed_now": False,
    "apply_allowed_now": False,
    "sql_write_allowed": False,
    "source_feeder_retirement_allowed": False,
    "fallback_removal_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_archive_label() -> str:
    return f"legacy-42-regenerated-{datetime.now(timezone.utc).strftime('%Y%m%d')}"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolved_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def clean_label(label: str) -> str:
    allowed = []
    for char in label.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            allowed.append(char)
        else:
            allowed.append("-")
    cleaned = "".join(allowed).strip(".-_")
    return cleaned or default_archive_label()


def preview_action(source: Path, destination: Path) -> str:
    source_hash = sha256_file(source)
    destination_hash = sha256_file(destination)
    if source.exists() and not destination.exists():
        return "preview_destination_clear"
    if source.exists() and destination.exists() and source_hash == destination_hash:
        return "preview_same_hash_duplicate_requires_delete_gate"
    if source.exists() and destination.exists():
        return "preview_destination_exists_with_different_hash"
    if not source.exists() and destination.exists():
        return "already_archived_to_preview"
    return "missing_source_and_preview_destination"


def candidate_rows(plan: dict[str, Any], versioned_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_texts = [item for item in as_list(plan.get("exact_archive_candidates")) if isinstance(item, str)]
    if not source_texts:
        source_texts = [
            str(row.get("path"))
            for row in as_list(plan.get("packet_rows"))
            if isinstance(row, dict)
            and row.get("built_from_assembler") is True
            and row.get("required_legacy_fields_present") is True
            and isinstance(row.get("path"), str)
        ]
    for source_text in source_texts:
        if not isinstance(source_text, str):
            continue
        source = ROOT / source_text
        preview_destination = PREVIEW_ARCHIVE_ROOT / source.name
        versioned_destination = versioned_root / source.name
        rows.append(
            {
                "source": rel(source),
                "source_exists": source.exists(),
                "source_sha256": sha256_file(source),
                "source_bytes": source.stat().st_size if source.exists() else None,
                "conflicting_preview_destination": rel(preview_destination),
                "conflicting_preview_destination_exists": preview_destination.exists(),
                "conflicting_preview_destination_sha256": sha256_file(preview_destination),
                "conflict_action_from_apply_guard": preview_action(source, preview_destination),
                "proposed_versioned_destination": rel(versioned_destination),
                "proposed_versioned_destination_exists": versioned_destination.exists(),
                "proposed_versioned_destination_sha256": sha256_file(versioned_destination),
                "post_approval_move_action": f"move {rel(source)} to {rel(versioned_destination)}",
                "rollback_action": f"move {rel(versioned_destination)} back to {rel(source)}",
                "apply_allowed_now": False,
                "delete_allowed_now": False,
                "overwrite_allowed_now": False,
            }
        )
    return rows


def build_packet(*, archive_label: str | None = None) -> dict[str, Any]:
    label = clean_label(archive_label or default_archive_label())
    versioned_root = ARCHIVE_PARENT / "versioned" / label
    plan = load_dict(PLAN)
    plan_summary = as_dict(plan.get("summary"))
    expected_count = int(plan_summary.get("legacy_packet_count") or 0)
    archive_completed = plan_summary.get("archive_completed") is True
    apply_report = load_dict(ARCHIVE_APPLY)
    rows = candidate_rows(plan, versioned_root)
    preview_conflict_count = sum(
        1 for row in rows if row["conflict_action_from_apply_guard"] == "preview_destination_exists_with_different_hash"
    )

    errors: list[str] = []
    warnings: list[str] = []

    if plan.get("status") not in {"planning_ready", "archived"}:
        errors.append("retirement_plan_not_planning_ready")
    if plan_summary.get("archive_ready_now") is not True and not archive_completed:
        errors.append("retirement_plan_not_archive_ready")
    if int(plan_summary.get("active_reference_count") or 0) != 0:
        errors.append("active_references_not_zero")
    if expected_count <= 0:
        errors.append("archive_expected_count_zero")
    if len(rows) != expected_count:
        errors.append("archive_candidate_count_mismatch")
    if preview_conflict_count != expected_count and not archive_completed:
        warnings.append("preview_archive_conflict_count_mismatch")
    if not resolved_under(versioned_root, ARCHIVE_PARENT):
        errors.append("versioned_root_outside_archive_parent")
    missing_sources = [row["source"] for row in rows if not row["source_exists"]]
    if missing_sources and not archive_completed:
        errors.append("missing_source_candidates")
    existing_versioned_destinations = [
        row["proposed_versioned_destination"]
        for row in rows
        if row["proposed_versioned_destination_exists"]
    ]
    if existing_versioned_destinations and not (
        archive_completed and len(existing_versioned_destinations) == len(rows)
    ):
        errors.append("versioned_archive_destination_already_exists")
    if any(row["source_sha256"] is None for row in rows) and not archive_completed:
        errors.append("missing_source_hashes")

    if errors:
        status = "blocked"
    elif archive_completed and len(existing_versioned_destinations) == len(rows):
        status = "versioned_archive_completed"
    elif archive_completed:
        status = "archive_completed_no_active_sources"
    else:
        status = "versioned_archive_owner_review_ready_apply_blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Owner-review/completion packet for the legacy-42 ticker answer packet versioned archive.",
        "recommendation": (
            "Archive is already complete; keep legacy snapshots archived and do not regenerate active compatibility files."
            if archive_completed
            else "Approve only if Randall wants these 42 active compatibility packets moved into the proposed versioned archive root; otherwise leave active compatibility files in place."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_plan": rel(PLAN),
        "source_apply_guard": rel(ARCHIVE_APPLY),
        "archive_parent": rel(ARCHIVE_PARENT),
        "archive_label": label,
        "proposed_versioned_archive_root": rel(versioned_root),
        "why_versioned_archive": {
            "preview_archive_root": rel(PREVIEW_ARCHIVE_ROOT),
            "preview_destination_hash_conflict_count": preview_conflict_count,
            "last_apply_guard_archive_root": apply_report.get("archive_root"),
            "last_apply_guard_status": apply_report.get("status"),
            "decision": "Do not overwrite preview archive files. Use a new versioned root for regenerated compatibility packets.",
        },
        "summary": {
            "candidate_count": len(rows),
            "source_exists_count": sum(1 for row in rows if row["source_exists"]),
            "source_hash_count": sum(1 for row in rows if row["source_sha256"]),
            "preview_destination_hash_conflict_count": preview_conflict_count,
            "versioned_destination_clear_count": sum(
                1 for row in rows if not row["proposed_versioned_destination_exists"]
            ),
            "versioned_destination_existing_count": len(existing_versioned_destinations),
            "move_count_after_approval": 0 if archive_completed else len(rows),
            "delete_count_after_approval": 0,
            "overwrite_count_after_approval": 0,
            "apply_performed": False,
            "archive_move_performed": False,
            "delete_performed": False,
            "overwrite_performed": False,
            "sql_write_performed": False,
            "canon_or_portfolio_mutation_performed": False,
            "capital_or_execution_authority": False,
        },
        "rows": rows,
        "approval_required": {
            "owner_exact_approval_required": not archive_completed,
            "approval_must_name": [
                "this packet path",
                "proposed_versioned_archive_root",
                f"candidate_count={expected_count}",
                "no overwrite",
                "no delete",
            ],
            "apply_allowed_now": False,
        },
        "future_apply_command_after_exact_approval": (
            "python scripts\\ticker_answer_packet_archive_apply.py "
            "--archive-root \""
            + rel(versioned_root).replace("/", "\\")
            + "\" --apply --approval-reference \"<exact approval reference>\" --write --validate"
        ),
        "rollback_proof": {
            "rollback_action_count": len(rows),
            "rollback_actions": [row["rollback_action"] for row in rows],
            "rollback_validation_commands": [
                "python scripts\\ticker_answer_packet_archive_apply.py --archive-root \""
                + rel(versioned_root).replace("/", "\\")
                + "\" --write --validate",
                "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
                "python scripts\\legacy_42_lifecycle_gate_packet.py --write --validate",
            ],
        },
        "post_apply_validation_commands": [
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\sql_canon_front_door_readiness_packet.py --write --validate",
            "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
            "python scripts\\legacy_42_lifecycle_gate_packet.py --write --validate",
            "python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate",
            "python scripts\\db_lifecycle_manifest.py --write --validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)),
        },
        "stop_lines": [
            "No archive folder creation, move, delete, overwrite, or cleanup is performed by this packet.",
            "No source-feeder, fallback, SQL-canon, portfolio/canon, customer, paper/live, account, capital, or money-movement authority.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-label", help="Versioned archive label under 09. Archive/.../versioned/.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet(archive_label=args.archive_label)
    if args.write:
        atomic_write_json(out, packet, indent=2, ensure_ascii=True)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out),
                "proposed_versioned_archive_root": packet["proposed_versioned_archive_root"],
                "summary": packet["summary"],
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and packet["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
