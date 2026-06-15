#!/usr/bin/env python3
"""Apply the owner-approved SQLite DB lifecycle archive microbatch.

This moves only databases listed as `archive_ready` in
tmp/db-lifecycle-manifest.json, plus their WAL/SHM sidecars, into the manifest's
proposed archive destinations. It verifies hashes after the move and writes a
closeout report. It never deletes files.
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
MANIFEST = TMP / "db-lifecycle-manifest.json"
REPORT = TMP / "db-lifecycle-archive-apply-report.json"
ARCHIVE_ROOT = ROOT / "09. Archive" / "DB Lifecycle - Archived"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_workspace(path_text: str) -> Path:
    path = (ROOT / path_text).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes workspace: {path_text}")
    return path


def resolve_archive(path_text: str) -> Path:
    path = resolve_workspace(path_text)
    archive_root = ARCHIVE_ROOT.resolve()
    if path != archive_root and archive_root not in path.parents:
        raise ValueError(f"destination escapes DB lifecycle archive root: {path_text}")
    return path


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def move_one(src: Path, dest: Path, expected_sha256: str | None, dry_run: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": rel(src),
        "destination": rel(dest),
        "expected_sha256": expected_sha256,
        "moved": False,
        "verified": False,
        "error": None,
    }
    if not src.exists():
        row["error"] = "source_missing"
        return row
    if not src.is_file():
        row["error"] = "source_not_file"
        return row
    before_hash = sha256_file(src)
    row["source_sha256_before"] = before_hash
    if expected_sha256 and before_hash != expected_sha256:
        row["error"] = "source_hash_mismatch"
        return row
    if dest.exists():
        row["error"] = "destination_exists"
        row["destination_sha256_existing"] = sha256_file(dest)
        return row
    if dry_run:
        row["dry_run"] = True
        row["verified"] = True
        return row
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    row["moved"] = True
    dest_hash = sha256_file(dest)
    row["destination_sha256_after"] = dest_hash
    row["source_exists_after"] = src.exists()
    row["destination_exists_after"] = dest.exists()
    row["verified"] = (dest_hash == before_hash) and not src.exists()
    return row


def build_file_plan(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for entry in manifest.get("entries", []):
        if not entry.get("archive_ready"):
            continue
        dest = entry.get("proposed_destination")
        if not isinstance(dest, str) or not dest:
            raise ValueError(f"archive-ready entry missing destination: {entry.get('path')}")
        plan.append({
            "source": entry["path"],
            "destination": dest,
            "expected_sha256": entry.get("sha256"),
            "kind": "database",
        })
        for sidecar in entry.get("sidecars", []):
            side_dest = sidecar.get("proposed_destination")
            if not isinstance(side_dest, str) or not side_dest:
                raise ValueError(f"sidecar missing destination: {sidecar.get('path')}")
            plan.append({
                "source": sidecar["path"],
                "destination": side_dest,
                "expected_sha256": sidecar.get("sha256"),
                "kind": "sidecar",
            })
    return plan


def apply_archive(*, dry_run: bool) -> dict[str, Any]:
    manifest = load_manifest()
    if manifest.get("status") != "ready_for_owner_decision":
        raise ValueError(f"manifest is not decision-ready: {manifest.get('status')}")
    boundary = manifest.get("authority_boundary") or {}
    if boundary.get("archive_apply_allowed") is not False or boundary.get("delete_apply_allowed") is not False:
        raise ValueError("manifest authority boundary is not fail-closed")
    plan = build_file_plan(manifest)
    moves: list[dict[str, Any]] = []
    for item in plan:
        src = resolve_workspace(item["source"])
        dest = resolve_archive(item["destination"])
        moves.append(move_one(src, dest, item.get("expected_sha256"), dry_run))
    errors = [row for row in moves if row.get("error")]
    unverified = [row for row in moves if not row.get("verified")]
    return {
        "schema_version": "db_lifecycle_archive_apply_report.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors and not unverified else "blocked",
        "dry_run": dry_run,
        "manifest_path": rel(MANIFEST),
        "authority_boundary": {
            "archive_move_performed": not dry_run and not errors and not unverified,
            "delete_performed": False,
            "canon_or_portfolio_mutation": False,
            "brokerage_or_execution_authority": False,
            "owner_approval_source": "webchat 2026-05-30 16:08 MST: Yes, proceed with archiving; approved.",
        },
        "counts": {
            "planned_files": len(plan),
            "moved_files": sum(1 for row in moves if row.get("moved")),
            "verified_files": sum(1 for row in moves if row.get("verified")),
            "errors": len(errors),
        },
        "moves": moves,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="verify plan without moving files")
    parser.add_argument("--write", action="store_true", help="write closeout report")
    parser.add_argument("--validate", action="store_true", help="fail when archive report is not ok")
    args = parser.parse_args()

    report = apply_archive(dry_run=args.dry_run)
    if args.write:
        atomic_write_json(REPORT, report)
    print(json.dumps({
        "status": report["status"],
        "dry_run": report["dry_run"],
        "counts": report["counts"],
        "report": rel(REPORT) if args.write else None,
    }, indent=2))
    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
