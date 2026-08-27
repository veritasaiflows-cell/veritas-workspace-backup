#!/usr/bin/env python3
"""Rehearse SQL-canon DB rollback on a copy, without mutating the live DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-rollback-rehearsal.json"
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_WORKDIR = ROOT / "tmp" / "sql-canon-rollback-rehearsal"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(path: Path) -> dict[str, Any]:
    with connect_ro(path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        tables = [str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not str(row[0]).startswith("sqlite_")]
        views = [str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]
        counts = {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in tables}
    return {
        "path": rel(path),
        "sha256": sha256(path),
        "integrity_check": integrity,
        "foreign_key_issue_count": len(fk),
        "tables": tables,
        "views": views,
        "counts": counts,
    }


def sqlite_backup(src_path: Path, dst_path: Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src_path) as src, sqlite3.connect(dst_path) as dst:
        src.backup(dst)


def remove_sqlite_copy(path: Path) -> None:
    for candidate in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        if candidate.exists():
            candidate.unlink()


def build(db: Path, workdir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if not db.exists():
        add("db_exists", False, rel(db))
        return payload(checks, db, workdir, {}, {}, {})
    workdir.mkdir(parents=True, exist_ok=True)
    backup_path = workdir / "finance-canon-backup.sqlite"
    restored_path = workdir / "finance-canon-restored-copy.sqlite"
    remove_sqlite_copy(backup_path)
    remove_sqlite_copy(restored_path)
    sqlite_backup(db, backup_path)
    shutil.copy2(backup_path, restored_path)
    live = snapshot(db)
    backup = snapshot(backup_path)
    restored = snapshot(restored_path)
    add("live_integrity_ok", live["integrity_check"] == "ok" and live["foreign_key_issue_count"] == 0, live)
    add("backup_integrity_ok", backup["integrity_check"] == "ok" and backup["foreign_key_issue_count"] == 0, backup)
    add("restored_copy_integrity_ok", restored["integrity_check"] == "ok" and restored["foreign_key_issue_count"] == 0, restored)
    add("backup_counts_match_live", backup["counts"] == live["counts"], {"live": live["counts"], "backup": backup["counts"]})
    add("restored_counts_match_backup", restored["counts"] == backup["counts"], {"restored": restored["counts"], "backup": backup["counts"]})
    add("schema_shape_matches", backup["tables"] == live["tables"] and backup["views"] == live["views"], {"live_tables": live["tables"], "backup_tables": backup["tables"]})
    return payload(checks, db, workdir, live, backup, restored)


def payload(
    checks: list[dict[str, Any]],
    db: Path,
    workdir: Path,
    live: dict[str, Any],
    backup: dict[str, Any],
    restored: dict[str, Any],
) -> dict[str, Any]:
    errors = [check for check in checks if not check["ok"]]
    return {
        "schema_version": "sql_canon_rollback_rehearsal.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "db": rel(db),
        "workdir": rel(workdir),
        "live": live,
        "backup": backup,
        "restored_copy": restored,
        "checks": checks,
        "errors": errors,
        "authority_boundary": {
            "live_db_mutation_allowed": False,
            "copy_only_rehearsal": True,
            "archive_delete_allowed": False,
            "capital_or_execution_authority": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    workdir = args.workdir if args.workdir.is_absolute() else ROOT / args.workdir
    result = build(db, workdir)
    if args.write:
        atomic_write_json(OUT, result)
    print(json.dumps({"status": result["status"], "errors": len(result["errors"]), "written": [rel(OUT)] if args.write else []}, indent=2))
    return 1 if args.validate and result["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
