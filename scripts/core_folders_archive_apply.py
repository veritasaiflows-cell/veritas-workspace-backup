#!/usr/bin/env python3
"""Apply move-only archive microbatches for folders 01-05.

Reads the watchdog packet from core_folders_flattening_watchdog.py and moves
only rows already marked eligible. It never deletes files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
WATCHDOG_PATH = TMP / "core-folders-flattening-watchdog.json"
REPORT_PATH = TMP / "core-folders-archive-apply-report.json"

AUTHORITY_BOUNDARY_BASE = {
    "move_only": True,
    "delete_allowed": False,
    "archive_owner_truth_notes_allowed": False,
    "archive_active_script_dependencies_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def resolve_workspace(path_text: str) -> Path:
    path = (ROOT / path_text).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes workspace: {path_text}")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_rows(limit: int | None) -> tuple[str, list[dict[str, Any]]]:
    packet = load_json(WATCHDOG_PATH)
    archive_root = str(packet["archive_root"])
    rows = [row for row in packet.get("eligible_archive_rows", []) if row.get("eligible_for_move_only_archive") is True]
    rows = sorted(rows, key=lambda row: str(row.get("path", "")).lower())
    if limit is not None:
        rows = rows[:limit]
    return archive_root, rows


def process_row(row: dict[str, Any], archive_root: str, apply: bool) -> dict[str, Any]:
    source = resolve_workspace(str(row["path"]))
    dest = resolve_workspace(f"{archive_root}/{row['path']}")
    result: dict[str, Any] = {
        "source": rel(source),
        "destination": rel(dest),
        "candidate_class": row.get("candidate_class"),
        "exists_before": source.exists(),
        "eligible": False,
        "moved": False,
        "already_archived": False,
        "verified": False,
        "blocked_reason": None,
        "rollback": f"Move {rel(dest)} back to {rel(source)}",
    }
    if row.get("eligible_for_move_only_archive") is not True:
        result["blocked_reason"] = "not_marked_eligible"
        return result
    refs = row.get("reference_scan") or {}
    if refs.get("blocking_reference_count", 0):
        result["blocked_reason"] = "blocking_script_or_control_surface_reference"
        return result
    if not source.exists():
        if dest.exists() and dest.is_file():
            result["already_archived"] = True
            result["verified"] = True
            result["destination_sha256_existing"] = sha256(dest)
            result["bytes"] = dest.stat().st_size
            return result
        result["blocked_reason"] = "source_missing"
        return result
    if not source.is_file():
        result["blocked_reason"] = "source_not_file"
        return result
    before_hash = sha256(source)
    if row.get("sha256") and before_hash != row.get("sha256"):
        result["blocked_reason"] = "source_hash_changed"
        result["source_current_sha256"] = before_hash
        result["source_expected_sha256"] = row.get("sha256")
        return result
    if dest.exists():
        result["blocked_reason"] = "destination_exists"
        result["destination_sha256_existing"] = sha256(dest)
        return result
    result["sha256_before"] = before_hash
    result["bytes"] = source.stat().st_size
    result["eligible"] = True
    if not apply:
        result["dry_run"] = True
        result["verified"] = True
        return result

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))
    after_hash = sha256(dest)
    result["sha256_after"] = after_hash
    result["moved"] = True
    result["source_exists_after"] = source.exists()
    result["destination_exists_after"] = dest.exists()
    result["verified"] = after_hash == before_hash and not source.exists() and dest.exists()
    return result


def build_report(apply: bool, approval_reference: str | None, limit: int | None) -> dict[str, Any]:
    archive_root, rows = selected_rows(limit)
    processed = [process_row(row, archive_root, apply=apply) for row in rows]
    errors = [
        row for row in processed
        if row.get("eligible") and (row.get("moved") != apply or not row.get("verified"))
    ]
    if apply and not approval_reference:
        errors.append({"blocked_reason": "apply_requires_approval_reference"})
    blocked = [row for row in processed if row.get("blocked_reason")]
    moved = [row for row in processed if row.get("moved")]
    already_archived = [row for row in processed if row.get("already_archived")]
    return {
        "schema_version": "core_folders_archive_apply_report.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "dry_run": not apply,
        "source_watchdog": rel(WATCHDOG_PATH),
        "archive_root": archive_root,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY_BASE,
            "owner_archive_approval": approval_reference,
            "archive_apply_requested": apply,
            "archive_apply_allowed": bool(apply and approval_reference),
        },
        "summary": {
            "candidate_count": len(processed),
            "eligible_count": sum(1 for row in processed if row.get("eligible")),
            "moved_count": len(moved),
            "already_archived_count": len(already_archived),
            "blocked_count": len(blocked),
            "error_count": len(errors),
            "limit": limit,
        },
        "rows": processed,
        "blocked": blocked,
        "errors": errors,
        "delete_phase_plan": {
            "status": "planned_only_not_allowed",
            "delete_allowed_now": False,
            "requirements": [
                "archived file retention window selected by owner",
                "restore drill from archive to original path",
                "duplicate proof or generated-current replacement proof",
                "workspace index and boundary validators clean after archive",
                "separate exact owner delete approval",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--approval-reference")
    args = parser.parse_args()

    report = build_report(apply=args.apply, approval_reference=args.approval_reference, limit=args.limit)
    if args.write:
        atomic_write_json(REPORT_PATH, report)
    print(json.dumps({
        "status": report["status"],
        "dry_run": report["dry_run"],
        "candidate_count": report["summary"]["candidate_count"],
        "eligible_count": report["summary"]["eligible_count"],
        "moved_count": report["summary"]["moved_count"],
        "already_archived_count": report["summary"]["already_archived_count"],
        "blocked_count": report["summary"]["blocked_count"],
        "error_count": report["summary"]["error_count"],
        "report": rel(REPORT_PATH) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
