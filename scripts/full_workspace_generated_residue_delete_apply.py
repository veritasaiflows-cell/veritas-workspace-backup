#!/usr/bin/env python3
"""Delete workspace generated-residue candidates after exact owner approval.

This helper is intentionally narrow: it only consumes rows already classified
as ``delete_ready_after_exact_approval`` by
``full_workspace_delete_readiness.py`` and verifies the current file hash before
removing anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
READINESS = TMP / "full-workspace-delete-readiness.json"
REPORT = TMP / "full-workspace-generated-residue-delete-apply-report.json"

ALLOWED_CLASSES = {
    "empty_generated_or_archive_dir",
    "os_metadata_cache",
    "python_bytecode_cache",
    "temporary_file",
    "tmp_log_file",
}

AUTHORITY_BOUNDARY = {
    "generated_residue_delete_apply_script": True,
    "requires_apply_flag": True,
    "requires_exact_owner_approval_reference": True,
    "delete_limited_to_readiness_delete_ready_rows": True,
    "allowed_candidate_classes": sorted(ALLOWED_CLASSES),
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


def assert_inside_workspace(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {path}") from exc
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_readiness() -> dict[str, Any]:
    if not READINESS.exists():
        raise SystemExit(f"missing readiness manifest: {rel(READINESS)}")
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "full_workspace_delete_readiness.v1":
        raise SystemExit(f"unexpected readiness manifest schema: {rel(READINESS)}")
    return data


def empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def remove_empty_parents(start: Path, removed: list[str]) -> None:
    current = start
    while current != ROOT and current.exists():
        if current.name not in {"__pycache__", "tmp"}:
            break
        try:
            current.rmdir()
        except OSError:
            break
        removed.append(rel(current))
        current = current.parent


def apply_from_readiness(apply: bool, approval_reference: str | None) -> dict[str, Any]:
    data = load_readiness()
    source_rows = data.get("delete_ready_rows", [])
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    removed_dirs: list[str] = []

    for source in source_rows:
        row = dict(source)
        row.update({
            "hash_verified": False,
            "deleted": False,
            "skipped": False,
        })
        candidate_class = row.get("candidate_class")
        if row.get("posture") != "delete_ready_after_exact_approval":
            row["blocker"] = "row_not_delete_ready"
            blockers.append(row)
            rows.append(row)
            continue
        if candidate_class not in ALLOWED_CLASSES:
            row["blocker"] = "candidate_class_not_allowed_by_apply_helper"
            blockers.append(row)
            rows.append(row)
            continue

        path = assert_inside_workspace(ROOT / str(row["path"]))
        if row.get("kind") == "file":
            if not path.exists():
                row["skipped"] = True
                row["skip_reason"] = "already_missing"
                rows.append(row)
                continue
            if not path.is_file():
                row["blocker"] = "expected_file"
                blockers.append(row)
                rows.append(row)
                continue
            current_hash = sha256(path)
            row["current_sha256"] = current_hash
            row["hash_verified"] = current_hash == row.get("sha256")
            if not row["hash_verified"]:
                row["blocker"] = "sha256_mismatch"
                blockers.append(row)
                rows.append(row)
                continue
            if apply:
                path.unlink()
                row["deleted"] = True
                remove_empty_parents(path.parent, removed_dirs)
            rows.append(row)
            continue

        if row.get("kind") == "empty_dir":
            if not path.exists():
                row["skipped"] = True
                row["skip_reason"] = "already_missing"
                rows.append(row)
                continue
            if not empty_dir(path):
                row["blocker"] = "directory_not_empty"
                blockers.append(row)
                rows.append(row)
                continue
            row["hash_verified"] = True
            if apply:
                path.rmdir()
                row["deleted"] = True
                removed_dirs.append(rel(path))
                remove_empty_parents(path.parent, removed_dirs)
            rows.append(row)
            continue

        row["blocker"] = "unsupported_row_kind"
        blockers.append(row)
        rows.append(row)

    deleted_count = sum(1 for row in rows if row["deleted"])
    skipped_count = sum(1 for row in rows if row["skipped"])
    verified_count = sum(1 for row in rows if row["hash_verified"])
    deleted_bytes = sum(int(row.get("bytes") or 0) for row in rows if row["deleted"])
    status = "dry_run_ready_no_delete_applied"
    if blockers:
        status = "blocked_no_delete_applied" if deleted_count == 0 else "partial_apply_with_blockers"
    elif apply:
        status = "applied_generated_residue_delete"

    return {
        "schema_version": "full_workspace_generated_residue_delete_apply.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "approval_reference": approval_reference,
        "readiness_manifest": rel(READINESS),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "apply": apply,
            "candidate_count": len(rows),
            "hash_verified_count": verified_count,
            "deleted_count": deleted_count,
            "skipped_count": skipped_count,
            "blocker_count": len(blockers),
            "deleted_bytes": deleted_bytes,
            "removed_empty_dirs_count": len(set(removed_dirs)),
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

    report = apply_from_readiness(args.apply, args.approval_reference)
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
