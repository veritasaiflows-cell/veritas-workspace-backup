#!/usr/bin/env python3
"""Copy-only recovery drill for the migrated finance SQL canon.

Reads the source database through a read-only SQLite URI. All writable databases
live under tmp/finance-canon-recovery-drills/<unique-run>/; no live restore path
exists in this script. The result is evidence for a separately gated recovery
procedure, not authorization to restore the production database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlite_snapshot import logical_sha256, wal_safe_backup, wal_safe_restore

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DRILL_ROOT = ROOT / "tmp" / "finance-canon-recovery-drills"
MIGRATION_MARKER = "alerts_os_sql_canon_migration"
PRESERVED_TABLES = (
    "securities", "universe_membership", "reference_levels", "source_lineage", "audit_events"
)


def _ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(db: Path) -> dict:
    with closing(_ro(db)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in PRESERVED_TABLES
        }
        marker = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type=?", (MIGRATION_MARKER,)
        ).fetchone()[0]
    if integrity != "ok" or fk or marker != 1:
        raise ValueError(f"snapshot invalid: integrity={integrity}, fk={fk}, migration_marker={marker}")
    return {"integrity": integrity, "foreign_key_violations": fk,
            "migration_markers": marker, "table_counts": counts}


def run_drill(source: Path, out_dir: Path) -> dict:
    """Produce a durable copy-only report; refuse reuse and paths outside tmp."""
    source = source.resolve(strict=True)
    out_dir = out_dir.resolve()
    if not out_dir.is_relative_to(DRILL_ROOT.resolve()) or out_dir == DRILL_ROOT.resolve():
        raise ValueError("drill output must be a unique child under tmp/finance-canon-recovery-drills")
    if out_dir.exists():
        raise ValueError("drill output exists; refusing overwrite")
    out_dir.mkdir(parents=True)
    base = out_dir / "source-snapshot.sqlite"
    backup = out_dir / "verified-backup.sqlite"
    working = out_dir / "recovery-target.sqlite"

    # SQLite's backup API sees committed WAL frames. Source is opened mode=ro,
    # unlike a raw main-file copy or an ordinary writable sqlite3.connect.
    src = _ro(source)
    dst = sqlite3.connect(base)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    source_hash = logical_sha256(source)
    original_hash = logical_sha256(base)
    if source_hash != original_hash:
        raise ValueError("source changed during snapshot; discard this drill")
    original = _check(base)
    backup_record = wal_safe_backup(base, backup)
    if backup_record["logical_sha256_backup"] != original_hash:
        raise ValueError("backup logical hash mismatch")
    wal_safe_restore(backup, working, original_hash)

    # Inject a disposable post-backup fault while an open reader pins the WAL.
    with closing(sqlite3.connect(working)) as setup:
        setup.execute("PRAGMA journal_mode=WAL")
    reader = sqlite3.connect(working)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM audit_events").fetchone()
        main_file_before = _sha256_file(working)
        with closing(sqlite3.connect(working)) as writer:
            with writer:
                writer.execute("CREATE TABLE recovery_drill_fault(marker TEXT)")
                writer.execute("INSERT INTO recovery_drill_fault(marker) VALUES ('post-backup-fault')")
        fault_hash = logical_sha256(working)
        wal_pending = working.with_name(working.name + "-wal").exists()
        main_file_unchanged = _sha256_file(working) == main_file_before
        if fault_hash == original_hash or not wal_pending or not main_file_unchanged:
            raise ValueError("WAL fault was not independently visible with an unchanged main file")
    finally:
        reader.close()

    # A mismatched recorded hash must refuse before touching even the copy.
    before_bad_restore = logical_sha256(working)
    wrong_hash_refused = False
    try:
        wal_safe_restore(backup, working, "0" * 64)
    except ValueError as exc:
        wrong_hash_refused = "backup logical hash" in str(exc)
    if not wrong_hash_refused or logical_sha256(working) != before_bad_restore:
        raise ValueError("wrong-hash restore did not refuse without altering target")

    restored_hash = wal_safe_restore(backup, working, original_hash)
    restored = _check(working)
    with closing(_ro(working)) as conn:
        fault_table_remaining = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='recovery_drill_fault'"
        ).fetchone()[0]
    if restored_hash != original_hash or restored != original or fault_table_remaining:
        raise ValueError("restored copy differs from verified snapshot")

    report = {
        "schema": "veritas.finance_sql_canon_recovery_drill.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok_copy_only",
        "source": str(source), "out_dir": str(out_dir),
        "authority": {"live_restore_allowed": False, "live_canon_written": False,
                      "tier_changed": False, "restore_target_is_disposable_copy": True},
        "source_logical_sha256": source_hash,
        "snapshot_logical_sha256": original_hash,
        "backup_logical_sha256": backup_record["logical_sha256_backup"],
        "fault_logical_sha256": fault_hash,
        "restored_logical_sha256": restored_hash,
        "main_file_unchanged_during_wal_fault": main_file_unchanged,
        "uncheckpointed_wal_visible": wal_pending,
        "wrong_hash_refused_without_change": wrong_hash_refused,
        "fault_removed_after_restore": fault_table_remaining == 0,
        "original_validation": original,
        "restored_validation": restored,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="New child directory under tmp/finance-canon-recovery-drills")
    args = parser.parse_args()
    report = run_drill(LIVE_DB, args.out)
    print(json.dumps({"status": report["status"], "report": str(args.out / "report.json"),
                      "logical_sha256": report["restored_logical_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
