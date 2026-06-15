#!/usr/bin/env python3
"""Machine-executable rollback helper for the Phase 3C canon-cache write.

Default mode is dry-run. Use --apply only after explicit main-session approval.
Use --validate for an explicit dry-run validation proof of the rollback input.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def remove_db_family(db_path: Path, apply: bool) -> list[str]:
    removed = []
    for suffix in ["", "-wal", "-shm"]:
        path = Path(str(db_path) + suffix)
        if path.exists():
            removed.append(str(path))
            if apply:
                path.unlink()
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback the Phase 3C canon-cache write from a rollback export JSON.")
    parser.add_argument("--export", required=True, help="Rollback export JSON path")
    parser.add_argument("--db", default=None, help="Override DB path; defaults to export db_path")
    parser.add_argument("--validate", action="store_true", help="Validate rollback input and emit dry-run proof; does not mutate.")
    parser.add_argument("--apply", action="store_true", help="Actually mutate/delete the DB. Default is dry-run.")
    args = parser.parse_args()
    export_path = Path(args.export)
    artifact = json.loads(export_path.read_text(encoding="utf-8"))
    db_path = Path(args.db or artifact["db_path"])
    affected = {(row["scope"], row["field_name"]) for row in artifact.get("affected_keys", [])}
    result = {
        "generated_at_utc": utc_now(),
        "mode": "apply" if args.apply else "dry_run",
        "export_path": str(export_path),
        "db_path": str(db_path),
        "path_absent_before_phase3c": bool(artifact.get("path_absent")),
        "affected_keys": sorted([f"{scope}:{field}" for scope, field in affected]),
        "rows_to_restore": len(artifact.get("prior_rows", [])),
        "db_exists_before": db_path.exists(),
    }
    if artifact.get("path_absent"):
        result["action"] = "delete_phase3c_created_db_family"
        result["removed_paths"] = remove_db_family(db_path, args.apply)
    else:
        result["action"] = "restore_prior_rows"
        if args.apply:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            for scope, field in affected:
                conn.execute("DELETE FROM canon_cache_fields WHERE scope=? AND field_name=?", (scope, field))
            for row in artifact.get("prior_rows", []):
                columns = list(row.keys())
                placeholders = ",".join("?" for _ in columns)
                conn.execute(
                    f"INSERT INTO canon_cache_fields({','.join(columns)}) VALUES ({placeholders})",
                    [row[column] for column in columns],
                )
                conn.execute(
                    """
                    INSERT INTO canon_cache_change_ledger(operation, scope, field_name, old_value, new_value, source_artifact_path,
                        source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc)
                    VALUES ('rollback_restore', ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("scope"), row.get("field_name"), row.get("field_value"), row.get("source_artifact_path"),
                        row.get("source_artifact_hash"), artifact.get("approval_artifact_path"), str(export_path),
                        artifact.get("rows_sha256"), row.get("authority_boundary"), utc_now(),
                    ),
                )
            conn.commit()
            result["integrity_check_after"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
            result["remaining_rows_after"] = conn.execute("SELECT COUNT(*) FROM canon_cache_fields").fetchone()[0]
            conn.close()
    result["db_exists_after"] = db_path.exists()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
