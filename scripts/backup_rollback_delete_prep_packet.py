#!/usr/bin/env python3
"""Build a review-only prep packet for backup and rollback cleanup.

This script inventories two high-space targets:

- backups/
- state/tmp-lifecycle-rollback/

It never deletes, archives, renames, moves, rewrites, checkpoints, vacuums, or
restores anything. The output is an approval surface only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
OUT = WORKSPACE_ROOT / "tmp" / "backup-rollback-delete-prep-packet.json"
MD_OUT = WORKSPACE_ROOT / "tmp" / "backup-rollback-delete-prep-packet.md"
DB_LIFECYCLE_MANIFEST = WORKSPACE_ROOT / "tmp" / "db-lifecycle-manifest.json"
TMP_LIFECYCLE_TOMBSTONE = WORKSPACE_ROOT / "state" / "tmp-lifecycle-deletion-tombstone.json"

SCHEMA = "veritas.backup_rollback_delete_prep_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_inventory_only": True,
    "content_preview_performed": False,
    "delete_performed": False,
    "archive_performed": False,
    "rename_performed": False,
    "move_performed": False,
    "sqlite_write_performed": False,
    "sqlite_checkpoint_or_vacuum_performed": False,
    "restore_performed": False,
    "cron_schedule_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def mb(value: int) -> float:
    return round(value / 1024 / 1024, 3)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel_to(path, WORKSPACE_ROOT), "exists": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": rel_to(path, WORKSPACE_ROOT), "exists": True, "error": str(exc)}
    if not isinstance(data, dict):
        return {"path": rel_to(path, WORKSPACE_ROOT), "exists": True, "error": "json_not_object"}
    return data


def iter_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: rel_to(item, WORKSPACE_ROOT).lower())


def sqlite_quick_check(path: Path, *, root: Path = WORKSPACE_ROOT) -> dict[str, Any]:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        row = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        return {
            "path": rel_to(path, root),
            "status": "error",
            "result": None,
            "error": str(exc),
        }
    finally:
        if connection is not None:
            connection.close()
    result = row[0] if row else None
    return {
        "path": rel_to(path, root),
        "status": "ok" if result == "ok" else "warning",
        "result": result,
        "error": None,
    }


def tree_inventory(
    path: Path,
    *,
    include_sqlite_checks: bool = False,
    root: Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    files = iter_files(path)
    manifest_digest = hashlib.sha256()
    total_bytes = 0
    oldest: str | None = None
    newest: str | None = None
    suffix_counts: dict[str, int] = {}
    hash_errors: list[str] = []
    sqlite_checks: list[dict[str, Any]] = []

    for file_path in files:
        rel_path = rel_to(file_path, root)
        try:
            stat = file_path.stat()
            file_hash = file_sha256(file_path)
        except OSError as exc:
            hash_errors.append(f"{rel_path}:{exc}")
            continue
        mtime = iso_from_timestamp(stat.st_mtime)
        total_bytes += stat.st_size
        oldest = mtime if oldest is None or mtime < oldest else oldest
        newest = mtime if newest is None or mtime > newest else newest
        suffix = file_path.suffix.lower() or "<none>"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
        manifest_digest.update(
            json.dumps(
                {
                    "path": rel_path,
                    "size_bytes": stat.st_size,
                    "mtime_utc": mtime,
                    "sha256": file_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        manifest_digest.update(b"\n")
        if include_sqlite_checks and file_path.suffix.lower() == ".sqlite":
            sqlite_checks.append(sqlite_quick_check(file_path, root=root))

    sqlite_status_counts: dict[str, int] = {}
    for check in sqlite_checks:
        status = str(check.get("status"))
        sqlite_status_counts[status] = sqlite_status_counts.get(status, 0) + 1

    return {
        "path": rel_to(path, root),
        "exists": path.exists(),
        "root_type": "file" if path.is_file() else "directory",
        "file_count": len(files),
        "size_bytes": total_bytes,
        "size_mb": mb(total_bytes),
        "oldest_mtime_utc": oldest,
        "newest_mtime_utc": newest,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "file_manifest_digest": manifest_digest.hexdigest(),
        "file_hash_error_count": len(hash_errors),
        "file_hash_errors": hash_errors[:20],
        "file_hash_errors_truncated": len(hash_errors) > 20,
        "sqlite_quick_check_count": len(sqlite_checks),
        "sqlite_quick_check_status_counts": dict(sorted(sqlite_status_counts.items())),
        "sqlite_quick_check_errors": [check for check in sqlite_checks if check.get("status") == "error"][:20],
        "sqlite_quick_check_errors_truncated": sum(1 for check in sqlite_checks if check.get("status") == "error") > 20,
    }


def build_backup_rows(backups_root: Path, *, include_sqlite_checks: bool, root: Path) -> list[dict[str, Any]]:
    if not backups_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for child in sorted(backups_root.iterdir(), key=lambda item: item.name.lower()):
        inventory = tree_inventory(child, include_sqlite_checks=include_sqlite_checks, root=root)
        row = {
            **inventory,
            "target_root": "backups",
            "classification": "finance_or_workspace_backup_recovery_surface",
            "delete_ready_after_owner_approval": False,
            "blocked_reason": "backup_retention_and_restore_proof_required",
            "recommended_action": "retain_until_backup_retention_policy_and_restore_proof_packet_exists",
            "proposed_delete_target": inventory["path"],
            "rollback_plan_after_delete": "No local rollback from this packet after deletion; restore would require an external copy or a separately retained backup.",
        }
        rows.append(row)
    return rows


def build_rollback_rows(rollback_root: Path, *, root: Path) -> list[dict[str, Any]]:
    if not rollback_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for child in sorted(rollback_root.iterdir(), key=lambda item: item.name.lower()):
        inventory = tree_inventory(child, include_sqlite_checks=False, root=root)
        row = {
            **inventory,
            "target_root": "state/tmp-lifecycle-rollback",
            "classification": "cleanup_apply_rollback_copy",
            "delete_ready_after_owner_approval": True,
            "risk_acceptance_required": "Deleting this removes local rollback for prior approved cleanup applies.",
            "recommended_action": "delete_after_exact_owner_approval_if_no_rollback_needed",
            "proposed_delete_target": inventory["path"],
            "rollback_plan_after_delete": "None inside workspace after deletion; recovery would require external backup or rerunning/recreating the original producer where possible.",
        }
        rows.append(row)
    return rows


def rows_digest(rows: list[dict[str, Any]], *, include_readiness: bool) -> str:
    digest_rows = [
        {
            "path": row.get("path"),
            "file_count": row.get("file_count"),
            "size_bytes": row.get("size_bytes"),
            "file_manifest_digest": row.get("file_manifest_digest"),
            "delete_ready_after_owner_approval": row.get("delete_ready_after_owner_approval") if include_readiness else None,
            "proposed_delete_target": row.get("proposed_delete_target"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_db_lifecycle_manifest(path: Path, *, root: Path = WORKSPACE_ROOT) -> dict[str, Any]:
    manifest = load_json_if_present(path)
    if manifest.get("exists") is False or manifest.get("error"):
        return {
            "path": rel_to(path, root),
            "exists": manifest.get("exists", True),
            "error": manifest.get("error"),
            "status": "missing_or_unreadable",
            "delete_ready_count": None,
            "archive_ready_count": None,
            "unknown_count": None,
            "validation_errors": [],
        }
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    return {
        "path": rel_to(path, root),
        "exists": True,
        "generated_at_utc": manifest.get("generated_at_utc"),
        "status": manifest.get("status"),
        "delete_ready_count": summary.get("delete_ready_count"),
        "archive_ready_count": summary.get("archive_ready_count"),
        "unknown_count": summary.get("unknown_count"),
        "integrity_error_count": summary.get("integrity_error_count"),
        "validation_errors": manifest.get("validation_errors") if isinstance(manifest.get("validation_errors"), list) else [],
    }


def parse_tmp_tombstone(path: Path, *, root: Path = WORKSPACE_ROOT) -> dict[str, Any]:
    tombstone = load_json_if_present(path)
    if tombstone.get("exists") is False or tombstone.get("error"):
        return {
            "path": rel_to(path, root),
            "exists": tombstone.get("exists", True),
            "error": tombstone.get("error"),
        }
    deleted_records = tombstone.get("deleted_records")
    runs = tombstone.get("runs")
    events = tombstone.get("events")
    return {
        "path": rel_to(path, root),
        "exists": True,
        "schema_version": tombstone.get("schema_version"),
        "created_at_utc": tombstone.get("created_at_utc"),
        "updated_at_utc": tombstone.get("updated_at_utc"),
        "deleted_record_count": len(deleted_records) if isinstance(deleted_records, list) else None,
        "run_count": len(runs) if isinstance(runs, list) else None,
        "event_count": len(events) if isinstance(events, list) else None,
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    authority = packet.get("authority_boundary", {})
    for key in (
        "delete_performed",
        "archive_performed",
        "rename_performed",
        "move_performed",
        "sqlite_write_performed",
        "restore_performed",
        "owner_approval_inferred",
    ):
        if authority.get(key) is not False:
            errors.append(f"authority_boundary_not_false:{key}")

    rollback_rows = packet.get("rollback_delete_microbatch", {}).get("rows", [])
    backup_rows = packet.get("backup_retention_review", {}).get("rows", [])

    if not isinstance(rollback_rows, list) or not isinstance(backup_rows, list):
        errors.append("rows_not_lists")
        rollback_rows = []
        backup_rows = []

    for row in rollback_rows:
        path = str(row.get("path") or "")
        if not path.startswith("state/tmp-lifecycle-rollback/"):
            errors.append(f"rollback_path_out_of_scope:{path}")
        if row.get("delete_ready_after_owner_approval") is not True:
            errors.append(f"rollback_row_not_owner_ready:{path}")
        if row.get("file_hash_error_count"):
            errors.append(f"rollback_hash_errors:{path}")

    for row in backup_rows:
        path = str(row.get("path") or "")
        if not path.startswith("backups/"):
            errors.append(f"backup_path_out_of_scope:{path}")
        if row.get("delete_ready_after_owner_approval") is not False:
            errors.append(f"backup_row_unexpectedly_owner_ready:{path}")
        if row.get("file_hash_error_count"):
            errors.append(f"backup_hash_errors:{path}")
        if row.get("sqlite_quick_check_status_counts", {}).get("error"):
            warnings.append(f"backup_sqlite_quick_check_errors:{path}")

    db_lifecycle = packet.get("source_artifacts", {}).get("db_lifecycle_manifest", {})
    if db_lifecycle.get("status") != "ok":
        warnings.append(f"db_lifecycle_manifest_not_ok:{db_lifecycle.get('status')}")
    if db_lifecycle.get("delete_ready_count") not in (0, None):
        warnings.append(f"db_lifecycle_manifest_delete_ready_count:{db_lifecycle.get('delete_ready_count')}")

    summary = packet.get("summary", {})
    if summary.get("backup_owner_ready_delete_bytes") != 0:
        errors.append("backup_owner_ready_delete_bytes_nonzero")
    if summary.get("rollback_owner_ready_delete_bytes") != summary.get("rollback_total_bytes"):
        errors.append("rollback_owner_ready_bytes_mismatch")

    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_packet(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    generated_at_utc: str | None = None,
    include_sqlite_checks: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at_utc or utc_now()
    backups_root = workspace_root / "backups"
    rollback_root = workspace_root / "state" / "tmp-lifecycle-rollback"

    backup_rows = build_backup_rows(backups_root, include_sqlite_checks=include_sqlite_checks, root=workspace_root)
    rollback_rows = build_rollback_rows(rollback_root, root=workspace_root)

    backup_digest = rows_digest(backup_rows, include_readiness=True)
    rollback_digest = rows_digest(rollback_rows, include_readiness=True)
    rollback_approval_phrase = (
        f"Approve tmp lifecycle rollback delete microbatch {rollback_digest} exactly as listed in "
        "tmp/backup-rollback-delete-prep-packet.json."
    )

    backup_total = sum(int(row.get("size_bytes") or 0) for row in backup_rows)
    rollback_total = sum(int(row.get("size_bytes") or 0) for row in rollback_rows)
    sqlite_check_status_counts: dict[str, int] = {}
    for row in backup_rows:
        for status, count in row.get("sqlite_quick_check_status_counts", {}).items():
            sqlite_check_status_counts[status] = sqlite_check_status_counts.get(status, 0) + int(count)

    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "owner_approval_ready_for_rollback_only_backups_blocked",
        "purpose": "Review-only preparation for deleting rollback copies and scoping finance/workspace backup retention cleanup.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "db_lifecycle_manifest": parse_db_lifecycle_manifest(
                workspace_root / DB_LIFECYCLE_MANIFEST.relative_to(WORKSPACE_ROOT),
                root=workspace_root,
            ),
            "tmp_lifecycle_deletion_tombstone": parse_tmp_tombstone(
                workspace_root / TMP_LIFECYCLE_TOMBSTONE.relative_to(WORKSPACE_ROOT),
                root=workspace_root,
            ),
        },
        "summary": {
            "backup_bundle_count": len(backup_rows),
            "backup_total_bytes": backup_total,
            "backup_total_mb": mb(backup_total),
            "backup_owner_ready_delete_bytes": 0,
            "backup_owner_ready_delete_mb": 0.0,
            "backup_delete_status": "blocked_pending_retention_policy_and_restore_proof",
            "backup_bundle_digest": backup_digest,
            "backup_sqlite_quick_check_status_counts": dict(sorted(sqlite_check_status_counts.items())),
            "rollback_bundle_count": len(rollback_rows),
            "rollback_total_bytes": rollback_total,
            "rollback_total_mb": mb(rollback_total),
            "rollback_owner_ready_delete_bytes": rollback_total,
            "rollback_owner_ready_delete_mb": mb(rollback_total),
            "rollback_microbatch_digest": rollback_digest,
            "rollback_approval_phrase": rollback_approval_phrase,
            "content_preview_included": False,
            "delete_performed": False,
            "archive_performed": False,
            "rename_performed": False,
            "move_performed": False,
        },
        "recommendation": {
            "safe_next_delete_target": "state/tmp-lifecycle-rollback",
            "safe_next_delete_rationale": "rollback-only copies from prior cleanup applies; deletion is safe only if Randall accepts loss of local rollback for those applies",
            "do_not_delete_backups_root_yet": True,
            "backups_blocker": "Finance/SQL backup root is the recovery layer and needs an explicit retention policy plus restore/integrity proof before any deletion microbatch is owner-ready.",
            "backup_retention_next_step": "Build a finance backup retention packet that keeps the newest valid recovery point per backup family and proposes only older redundant bundles after restore proof.",
        },
        "rollback_plan": {
            "state_tmp_lifecycle_rollback": "No workspace rollback remains after deletion; only external backups or rerunning producers can recover removed rollback copies.",
            "backups": "No delete approval is emitted for backups in this packet. If a future retention packet deletes backup bundles, it must preserve the retained restore set and list restore instructions.",
        },
        "rollback_delete_microbatch": {
            "name": "tmp_lifecycle_rollback_delete",
            "digest": rollback_digest,
            "approval_phrase": rollback_approval_phrase,
            "delete_ready_after_owner_approval": bool(rollback_rows),
            "rows": rollback_rows,
        },
        "backup_retention_review": {
            "name": "finance_workspace_backup_retention_review",
            "digest": backup_digest,
            "delete_ready_after_owner_approval": False,
            "approval_phrase": None,
            "rows": backup_rows,
        },
        "validation": {"status": "pending", "errors": [], "warnings": []},
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] != "ok":
        packet["status"] = "blocked"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    validation = packet.get("validation", {})
    source = packet.get("source_artifacts", {})
    lines = [
        "# Backup And Rollback Delete Prep Packet",
        "",
        f"- Generated UTC: `{packet.get('generated_at_utc')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Backups total: `{summary.get('backup_total_bytes')}` bytes / `{summary.get('backup_total_mb')}` MB",
        f"- Backups delete status: `{summary.get('backup_delete_status')}`",
        f"- Rollback total: `{summary.get('rollback_total_bytes')}` bytes / `{summary.get('rollback_total_mb')}` MB",
        f"- Rollback owner-ready delete: `{summary.get('rollback_owner_ready_delete_bytes')}` bytes / `{summary.get('rollback_owner_ready_delete_mb')}` MB",
        f"- Rollback digest: `{summary.get('rollback_microbatch_digest')}`",
        f"- Validation: `{validation.get('status')}`",
        "",
        "## Exact Approval Phrase",
        "",
        "```text",
        str(summary.get("rollback_approval_phrase")),
        "```",
        "",
        "## Backup Blocker",
        "",
        "No backup deletion approval phrase is emitted. `backups/` is still the finance/workspace recovery layer and needs a retention packet that proves the retained restore set before any backup bundle is deleted.",
        "",
        "## Source Artifacts",
        "",
        f"- DB lifecycle manifest: `{source.get('db_lifecycle_manifest', {}).get('path')}` status `{source.get('db_lifecycle_manifest', {}).get('status')}`",
        f"- Tmp lifecycle tombstone: `{source.get('tmp_lifecycle_deletion_tombstone', {}).get('path')}`",
        "",
        "## Boundary",
        "",
        "This packet is metadata-only. It performed no delete, archive, rename, move, SQLite write/checkpoint/vacuum, restore, config/runtime mutation, canon/portfolio mutation, or external action.",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--skip-sqlite-checks", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet(include_sqlite_checks=not args.skip_sqlite_checks)
    if args.write:
        atomic_write_json(OUT, packet)
    if args.write_md:
        atomic_write_text(MD_OUT, render_markdown(packet))
    response = (
        packet
        if args.pretty
        else {
            "status": packet.get("status"),
            "summary": packet.get("summary"),
            "validation": packet.get("validation"),
            "out": rel_to(OUT, WORKSPACE_ROOT) if args.write else None,
            "md_out": rel_to(MD_OUT, WORKSPACE_ROOT) if args.write_md else None,
        }
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
