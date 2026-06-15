#!/usr/bin/env python3
"""Apply an exact approved delete pass for restore-tested archived files."""
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
ARCHIVE = ROOT / "09. Archive"
READINESS_PATH = TMP / "archive-delete-readiness-plan.json"
REPORT_PATH = TMP / "archive-delete-apply-report.json"
RESTORE_DRILL_ROOT = TMP / "archive-delete-restore-drill"

APPROVED_CLASSES = {
    "core_folder_flattening_archive",
    "tmp_markdown_sidecar_archive",
}

AUTHORITY_BOUNDARY = {
    "archive_delete_apply_script": True,
    "requires_apply_flag": True,
    "requires_exact_owner_approval_reference": True,
    "delete_limited_to_readiness_candidates": True,
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


def assert_inside_workspace(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {path}") from exc
    return resolved


def original_path_for_archive(path: Path) -> str | None:
    relative = rel(path)
    prefixes = [
        "09. Archive/Core Finance Human Surfaces/2026-05-30/",
        "09. Archive/Finance Human Notes Thinning/2026-05-30/",
    ]
    for prefix in prefixes:
        if relative.startswith(prefix):
            return relative.removeprefix(prefix)
    return None


def load_readiness() -> dict[str, Any]:
    with READINESS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def candidate_rows(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in readiness.get("rows", []):
        if row.get("delete_readiness") != "delete_candidate_after_retention_and_restore_test":
            continue
        if row.get("candidate_class") not in APPROVED_CLASSES:
            continue
        rows.append(row)
    return rows


def remove_empty_parent_dirs(path: Path, deleted_dirs: list[str]) -> None:
    current = path.parent
    archive_root = ARCHIVE.resolve()
    while current.resolve() != archive_root and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        deleted_dirs.append(rel(current))
        current = current.parent


def build_report(apply: bool, approval_reference: str | None) -> dict[str, Any]:
    readiness = load_readiness()
    rows = candidate_rows(readiness)
    report_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    deleted_dirs: list[str] = []
    drill_root = RESTORE_DRILL_ROOT / utc_now().replace(":", "").replace("-", "")

    for row in rows:
        relative = row["path"]
        path = assert_inside_workspace(ROOT / relative)
        path_info: dict[str, Any] = {
            "path": relative,
            "candidate_class": row.get("candidate_class"),
            "expected_sha256": row.get("sha256"),
            "expected_bytes": row.get("bytes"),
            "original_path": original_path_for_archive(path),
            "deleted": False,
            "restore_drill_passed": False,
        }
        try:
            path.relative_to(ARCHIVE.resolve())
        except ValueError:
            blockers.append({**path_info, "blocker": "path_not_inside_archive"})
            report_rows.append(path_info)
            continue
        if not path.exists() or not path.is_file():
            blockers.append({**path_info, "blocker": "missing_archive_file"})
            report_rows.append(path_info)
            continue
        actual_hash = sha256(path)
        path_info["actual_sha256"] = actual_hash
        path_info["actual_bytes"] = path.stat().st_size
        if actual_hash != row.get("sha256"):
            blockers.append({**path_info, "blocker": "hash_mismatch"})
            report_rows.append(path_info)
            continue
        if path_info["original_path"] is None:
            blockers.append({**path_info, "blocker": "cannot_derive_original_path"})
            report_rows.append(path_info)
            continue

        drill_target = drill_root / path_info["original_path"]
        assert_inside_workspace(drill_target)
        drill_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, drill_target)
        drill_hash = sha256(drill_target)
        path_info["restore_drill_path"] = rel(drill_target)
        path_info["restore_drill_sha256"] = drill_hash
        path_info["restore_drill_passed"] = drill_hash == actual_hash
        if not path_info["restore_drill_passed"]:
            blockers.append({**path_info, "blocker": "restore_drill_hash_mismatch"})
            report_rows.append(path_info)
            continue

        if apply:
            path.unlink()
            path_info["deleted"] = True
            remove_empty_parent_dirs(path, deleted_dirs)
        report_rows.append(path_info)

    if drill_root.exists():
        shutil.rmtree(drill_root)
        remove_empty_parent_dirs(drill_root, deleted_dirs)

    deleted_count = sum(1 for row in report_rows if row["deleted"])
    ready_count = sum(1 for row in report_rows if row["restore_drill_passed"])
    by_class: dict[str, int] = {}
    for row in report_rows:
        by_class[row["candidate_class"]] = by_class.get(row["candidate_class"], 0) + 1

    status = "dry_run_ready_no_delete_applied"
    if blockers:
        status = "blocked_no_delete_applied" if not apply or deleted_count == 0 else "partial_apply_with_blockers"
    elif apply:
        status = "applied_archive_delete"

    return {
        "schema_version": "archive_delete_apply.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "approval_reference": approval_reference,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "apply": apply,
            "readiness_report": rel(READINESS_PATH),
            "candidate_count": len(rows),
            "restore_drill_passed_count": ready_count,
            "deleted_count": deleted_count,
            "blocker_count": len(blockers),
            "deleted_empty_dirs_count": len(set(deleted_dirs)),
            "by_candidate_class": dict(sorted(by_class.items())),
        },
        "blockers": blockers,
        "deleted_empty_dirs": sorted(set(deleted_dirs)),
        "rows": report_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete approved archived files after proof checks.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--approval-reference")
    args = parser.parse_args()

    if args.apply and not args.approval_reference:
        raise SystemExit("--apply requires --approval-reference")

    report = build_report(apply=args.apply, approval_reference=args.approval_reference)
    if args.write:
        atomic_write_json(REPORT_PATH, report)
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT_PATH) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["summary"]["blocker_count"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
