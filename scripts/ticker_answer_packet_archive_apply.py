#!/usr/bin/env python3
"""Dry-run or apply the approved WF85 legacy ticker-answer archive move.

The default mode is proof-only. Applying requires an explicit approval
reference and refuses to overwrite an existing archive destination. If a
regenerated active packet differs from a prior archive copy, this script stops
and emits a reconcile packet instead of replacing history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PLAN = TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json"
DEFAULT_OUT = TMP / "ticker-answer-packet-archive-apply-current.json"
ARCHIVE_PARENT = ROOT / "09. Archive" / "WF85 Legacy Ticker Answer Packets"
ARCHIVE_ROOT = ARCHIVE_PARENT / "preview"

SCHEMA = "veritas.ticker_answer_packet_archive_apply.v1"
EXPECTED_COUNT = 42

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_archive_move_tool": True,
    "delete_allowed": False,
    "overwrite_allowed": False,
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


def archive_rows(plan: dict[str, Any], *, archive_root: Path = ARCHIVE_ROOT) -> list[dict[str, Any]]:
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
        destination = archive_root / source.name
        source_hash = sha256_file(source)
        destination_hash = sha256_file(destination)
        source_exists = source.exists()
        destination_exists = destination.exists()
        if source_exists and not destination_exists:
            action = "move_ready"
        elif source_exists and destination_exists and source_hash == destination_hash:
            action = "active_duplicate_same_hash_cleanup_requires_delete_gate"
        elif source_exists and destination_exists:
            action = "blocked_destination_exists_with_different_hash"
        elif not source_exists and destination_exists:
            action = "already_archived"
        else:
            action = "missing_source_and_destination"
        rows.append(
            {
                "source": rel(source),
                "destination": rel(destination),
                "source_exists": source_exists,
                "destination_exists": destination_exists,
                "source_sha256": source_hash,
                "destination_sha256": destination_hash,
                "bytes": source.stat().st_size if source_exists else None,
                "action": action,
                "rollback": f"move {rel(destination)} back to {rel(source)}",
            }
        )
    return rows


def build_report(
    *,
    apply: bool,
    approval_reference: str | None,
    archive_root: Path = ARCHIVE_ROOT,
) -> dict[str, Any]:
    plan = load_dict(PLAN)
    summary = as_dict(plan.get("summary"))
    rows = archive_rows(plan, archive_root=archive_root)
    move_ready = [row for row in rows if row["action"] == "move_ready"]
    conflicts = [row for row in rows if row["action"] == "blocked_destination_exists_with_different_hash"]
    same_hash_duplicates = [row for row in rows if row["action"] == "active_duplicate_same_hash_cleanup_requires_delete_gate"]
    already_archived = [row for row in rows if row["action"] == "already_archived"]
    missing = [row for row in rows if row["action"] == "missing_source_and_destination"]

    errors: list[str] = []
    if summary.get("planning_ready") is not True:
        errors.append("retirement_plan_not_planning_ready")
    if int(summary.get("active_reference_count") or 0) != 0:
        errors.append("active_references_not_zero")
    if len(rows) != EXPECTED_COUNT:
        errors.append("archive_candidate_count_not_42")
    if conflicts:
        errors.append("archive_destination_hash_conflicts_present")
    if same_hash_duplicates:
        errors.append("active_duplicates_require_delete_gate_not_archive_move")
    if missing:
        errors.append("missing_source_and_destination")
    if apply and not approval_reference:
        errors.append("apply_requires_approval_reference")
    for row in rows:
        source = ROOT / str(row["source"])
        destination = ROOT / str(row["destination"])
        if not resolved_under(source, ROOT):
            errors.append(f"source_outside_workspace:{row['source']}")
        if not resolved_under(destination, archive_root):
            errors.append(f"destination_outside_archive_root:{row['destination']}")
        if not resolved_under(destination, ARCHIVE_PARENT):
            errors.append(f"destination_outside_archive_parent:{row['destination']}")

    applied: list[dict[str, Any]] = []
    apply_allowed = apply and not errors
    if apply_allowed:
        archive_root.mkdir(parents=True, exist_ok=True)
        for row in move_ready:
            source = ROOT / str(row["source"])
            destination = ROOT / str(row["destination"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            applied.append(
                {
                    **row,
                    "post_move_destination_sha256": sha256_file(destination),
                    "post_move_source_exists": source.exists(),
                }
            )

    if applied and apply_allowed:
        status = "applied"
    elif errors:
        status = "blocked"
    elif already_archived and len(already_archived) == len(rows) and not move_ready:
        status = "already_archived"
    else:
        status = "ready_to_apply"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "apply_requested": apply,
        "apply_performed": bool(applied),
        "approval_reference": approval_reference,
        "source_plan": rel(PLAN),
        "archive_root": rel(archive_root),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(rows),
            "move_ready_count": len(move_ready),
            "already_archived_count": len(already_archived),
            "destination_hash_conflict_count": len(conflicts),
            "active_duplicate_same_hash_count": len(same_hash_duplicates),
            "missing_count": len(missing),
            "applied_count": len(applied),
            "delete_performed": False,
            "overwrite_performed": False,
            "sql_write_performed": False,
            "canon_or_portfolio_mutation_performed": False,
            "capital_or_execution_authority": False,
        },
        "rows": rows,
        "applied": applied,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": sorted(set(errors)),
            "warnings": [
                "Existing archive destinations with different hashes require a versioned archive or replace approval packet.",
                "Same-hash active duplicates require a separate delete/cleanup gate.",
            ],
        },
        "stop_lines": [
            "No overwrite of existing archive files.",
            "No delete cleanup of active duplicates.",
            "No source-feeder or fallback retirement.",
            "No SQL, canon, portfolio, capital, paper/live, account, or money movement action.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Move files only if all no-overwrite gates pass.")
    parser.add_argument("--approval-reference", help="Exact owner approval reference required with --apply.")
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=ARCHIVE_ROOT,
        help="Approved archive root. Defaults to the legacy preview archive root.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    archive_root = args.archive_root if args.archive_root.is_absolute() else ROOT / args.archive_root
    report = build_report(
        apply=args.apply,
        approval_reference=args.approval_reference,
        archive_root=archive_root,
    )
    if args.write:
        atomic_write_json(out, report, indent=2, ensure_ascii=True)
    print(
        json.dumps(
            {
                "status": report["status"],
                "out": rel(out),
                "summary": report["summary"],
                "validation": report["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and as_dict(report.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
