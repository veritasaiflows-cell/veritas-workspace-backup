#!/usr/bin/env python3
"""Small cross-process mutex for the WF84 SQLite companion.

The WF84 SQLite file is a derived lookup surface, but writers replace the file
while WF85 readers may open it. This mutex keeps recurring runners and manual
proof commands from colliding on Windows.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class WF84SqliteMutexTimeout(TimeoutError):
    """Raised when another process keeps the WF84 SQLite mutex too long."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lock_path_for(db_path: Path) -> Path:
    return db_path.with_name(db_path.name + ".lock")


@contextmanager
def wf84_sqlite_mutex(
    db_path: Path,
    *,
    role: str,
    timeout_seconds: float = 180.0,
    poll_seconds: float = 0.25,
) -> Iterator[Path]:
    """Acquire an exclusive workspace mutex near the WF84 SQLite DB.

    This intentionally serializes readers and writers for the short WF84/WF85
    proof window. It does not make the SQLite file canon, approval, or execution
    authority.
    """
    lock_path = lock_path_for(db_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    fd: int | None = None
    payload = {
        "role": role,
        "pid": os.getpid(),
        "acquired_at_utc": utc_now(),
        "db_path": str(db_path),
        "authority_boundary": "derived WF84 SQLite lookup mutex only; no canon/portfolio/trade/account authority",
    }
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise WF84SqliteMutexTimeout(f"timed out waiting for {lock_path}")
            time.sleep(poll_seconds)
    try:
        yield lock_path
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
