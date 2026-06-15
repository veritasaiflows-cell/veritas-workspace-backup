#!/usr/bin/env python3
"""Delete all archived files after hash and restore-drill proof, leaving a tombstone manifest."""
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
ARCHIVE = ROOT / "09. Archive"
STATE = ROOT / "state"
TMP = ROOT / "tmp"
REPORT = TMP / "full-archive-delete-apply-report.json"
TOMBSTONE = STATE / "archive-deletion-tombstone.json"
RESTORE_ROOT = TMP / "full-archive-delete-restore-drill"

AUTHORITY_BOUNDARY = {
    "archive_delete_apply_script": True,
    "requires_apply_flag": True,
    "requires_exact_owner_approval_reference": True,
    "delete_limited_to_archive_tree": True,
    "config_auth_channel_runtime_mutation_allowed": False,
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes expected root: {path}") from exc
    return resolved


def archive_files() -> list[Path]:
    if not ARCHIVE.exists():
        return []
    return sorted((path for path in ARCHIVE.rglob("*") if path.is_file()), key=lambda path: rel(path).lower())


def remove_empty_dirs(start: Path, stop: Path, removed: list[str]) -> None:
    current = start
    stop_resolved = stop.resolve()
    while current.exists() and current.resolve() != stop_resolved:
        try:
            current.rmdir()
        except OSError:
            break
        removed.append(rel(current))
        current = current.parent


def build_report(apply: bool, approval_reference: str | None) -> dict[str, Any]:
    files = archive_files()
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    removed_dirs: list[str] = []
    drill_root = RESTORE_ROOT / utc_now().replace(":", "").replace("-", "")

    for path in files:
        assert_inside(path, ARCHIVE)
        row: dict[str, Any] = {
            "path": rel(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "restore_drill_passed": False,
            "deleted": False,
        }
        drill_target = drill_root / path.relative_to(ARCHIVE)
        assert_inside(drill_target, RESTORE_ROOT)
        drill_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, drill_target)
        drill_hash = sha256(drill_target)
        row["restore_drill_path"] = rel(drill_target)
        row["restore_drill_sha256"] = drill_hash
        row["restore_drill_passed"] = drill_hash == row["sha256"]
        if not row["restore_drill_passed"]:
            blockers.append({**row, "blocker": "restore_drill_hash_mismatch"})
            rows.append(row)
            continue
        if apply:
            path.unlink()
            row["deleted"] = True
            remove_empty_dirs(path.parent, ARCHIVE, removed_dirs)
        rows.append(row)

    if drill_root.exists():
        shutil.rmtree(drill_root)
        remove_empty_dirs(drill_root.parent, TMP, removed_dirs)

    if apply and ARCHIVE.exists():
        remove_empty_dirs(ARCHIVE, ROOT, removed_dirs)

    deleted_count = sum(1 for row in rows if row["deleted"])
    restore_count = sum(1 for row in rows if row["restore_drill_passed"])
    tombstone = {
        "schema_version": "archive_deletion_tombstone.v1",
        "generated_at_utc": utc_now(),
        "approval_reference": approval_reference,
        "archive_root": "09. Archive",
        "deleted_file_count": deleted_count,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "deleted_files": [
            {
                "path": row["path"],
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
            for row in rows
            if row["deleted"]
        ],
    }
    if apply:
        atomic_write_json(TOMBSTONE, tombstone)

    status = "dry_run_ready_no_delete_applied"
    if blockers:
        status = "blocked_no_delete_applied" if deleted_count == 0 else "partial_apply_with_blockers"
    elif apply:
        status = "applied_full_archive_delete"

    return {
        "schema_version": "full_archive_delete_apply.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "approval_reference": approval_reference,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "apply": apply,
            "candidate_count": len(rows),
            "restore_drill_passed_count": restore_count,
            "deleted_count": deleted_count,
            "blocker_count": len(blockers),
            "removed_empty_dirs_count": len(set(removed_dirs)),
            "tombstone": rel(TOMBSTONE),
        },
        "blockers": blockers,
        "removed_empty_dirs": sorted(set(removed_dirs)),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--approval-reference")
    args = parser.parse_args()
    if args.apply and not args.approval_reference:
        raise SystemExit("--apply requires --approval-reference")
    report = build_report(args.apply, args.approval_reference)
    if args.write:
        atomic_write_json(REPORT, report)
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["summary"]["blocker_count"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
