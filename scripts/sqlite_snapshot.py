#!/usr/bin/env python3
"""WAL-safe SQLite snapshot helpers (shared module, lane WALSAFE-G6-RESTORE-20260927).

Why this exists (defect proven first-hand 2026-09-27 on a temp DB): the canon
runs ``journal_mode=wal``. When any other connection holds the DB open (for
example a long-lived reader), commits stay in the ``-wal`` file and the main
file hash does not change. A ``shutil.copyfile`` backup of the main file can
therefore miss uncheckpointed commits, and a copy-based restore can report a
matching hash while the failed change remains visible because SQLite replays
the WAL.

Contract:
  - ``logical_sha256(db)``: sha256 over ``sqlite3.iterdump()`` lines on a
    ``mode=ro`` connection. Hash of committed logical content (schema + rows),
    WAL-inclusive. ~0.15 s on the canon (measured 2026-09-27).
  - ``wal_safe_backup(src, dst)``: ``sqlite3.Connection.backup()`` snapshot
    (captures committed state including WAL frames), then
    ``PRAGMA journal_mode=DELETE`` so the backup is a standalone file with no
    sidecars, then verify the logical hashes are equal. Refuses if ``dst``
    already exists. Raises before any mutation of the live DB on failure.
  - ``wal_safe_restore(backup, db, expected_logical_sha256)``: refuse unless
    the backup's logical hash equals ``expected_logical_sha256``; restore
    through the SQLite backup API (transactional, WAL-aware); verify the live
    logical hash afterwards.

Reference implementation validated 2026-09-27:
``tmp/p4-2-writer-lane-20260927/walproof/sqlite_snapshot_ref.py``.
This module is the single shared home for these helpers; writers (g6 apply,
reference-level onboarding, tier membership) must import from here instead of
re-implementing copy-based backups.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

__all__ = ["logical_sha256", "wal_safe_backup", "wal_safe_restore"]


def _ro_uri(db_path: str | Path) -> str:
    return f"file:{Path(db_path).resolve().as_posix()}?mode=ro"


def logical_sha256(db_path: str | Path) -> str:
    """Hash of committed logical content (schema + rows), WAL-inclusive."""
    con = sqlite3.connect(_ro_uri(db_path), uri=True)
    try:
        h = hashlib.sha256()
        for line in con.iterdump():
            h.update(line.encode("utf-8"))
            h.update(b"\n")
        return h.hexdigest()
    finally:
        con.close()


def wal_safe_backup(db_path: str | Path, backup_path: str | Path) -> dict:
    """Consistent snapshot of committed state (includes WAL frames)."""
    backup_path = Path(backup_path)
    if backup_path.exists():
        raise ValueError(f"backup path already exists: {backup_path}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")  # standalone file, no sidecars
    finally:
        dst.close()
        src.close()
    before = logical_sha256(db_path)
    backup = logical_sha256(backup_path)
    if before != backup:
        raise ValueError("backup FAILED: logical hash mismatch; no mutation performed")
    return {"backup_path": str(backup_path).replace("\\", "/"),
            "logical_sha256_before": before, "logical_sha256_backup": backup}


def wal_safe_restore(backup_path: str | Path, db_path: str | Path,
                     expected_logical_sha256: str) -> str:
    """Restore through SQLite (transactional, WAL-aware); verify logically."""
    if logical_sha256(backup_path) != expected_logical_sha256:
        raise ValueError("restore refused: backup logical hash != recorded")
    src = sqlite3.connect(_ro_uri(backup_path), uri=True)
    dst = sqlite3.connect(str(db_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    after = logical_sha256(db_path)
    if after != expected_logical_sha256:
        raise ValueError("restore FAILED: live logical hash != backup logical hash")
    return after
