#!/usr/bin/env python3
"""Small cross-process mutex for the WF84 SQLite companion.

The WF84 SQLite file is a derived lookup surface, but writers replace the file
while WF85 readers may open it. This mutex keeps recurring runners and manual
proof commands from colliding on Windows.
"""
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_STALE_AFTER_SECONDS = 900.0

RECLAIM_LEDGER = Path(__file__).resolve().parent.parent / "tmp" / "wf84-sqlite-mutex-reclaims.jsonl"


class WF84SqliteMutexTimeout(TimeoutError):
    """Raised when another process keeps the WF84 SQLite mutex too long."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lock_path_for(db_path: Path) -> Path:
    return db_path.with_name(db_path.name + ".lock")


def pid_alive(pid: int) -> bool | None:
    """Return True/False for holder liveness, or None when it cannot be determined.

    Never signals the target. ``os.kill(pid, 0)`` is unsafe on Windows because
    CPython routes non-console signals to TerminateProcess.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER means no such process; anything else is inconclusive.
            return False if ctypes.get_last_error() == 87 else None
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def read_lock_payload(lock_path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def lock_age_seconds(lock_path: Path) -> float | None:
    try:
        return max(0.0, time.time() - lock_path.stat().st_mtime)
    except OSError:
        return None


def classify_lock(lock_path: Path, stale_after_seconds: float) -> dict[str, Any]:
    """Decide whether an existing lock is reclaimable, and say why."""
    payload = read_lock_payload(lock_path)
    age = lock_age_seconds(lock_path)
    if age is None:
        return {"stale": False, "reason": "lock_vanished", "payload": payload, "age_seconds": None}
    holder_pid = (payload or {}).get("pid")
    alive = pid_alive(holder_pid) if isinstance(holder_pid, int) else None
    if payload is None and age >= stale_after_seconds:
        return {"stale": True, "reason": "unreadable_lock_payload_beyond_max_age", "payload": None, "age_seconds": age}
    if alive is False:
        return {"stale": True, "reason": "holder_pid_not_running", "payload": payload, "age_seconds": age}
    if age >= stale_after_seconds:
        return {"stale": True, "reason": "lock_age_exceeded_max_age", "payload": payload, "age_seconds": age}
    return {"stale": False, "reason": "holder_active", "payload": payload, "age_seconds": age}


def _record_reclaim(lock_path: Path, verdict: dict[str, Any], role: str) -> None:
    record = {
        "event": "wf84_sqlite_mutex_stale_lock_reclaimed",
        "lock_path": str(lock_path),
        "reclaimed_at_utc": utc_now(),
        "reclaimed_by_pid": os.getpid(),
        "reclaiming_role": role,
        "reason": verdict.get("reason"),
        "lock_age_seconds": round(verdict["age_seconds"], 3) if verdict.get("age_seconds") is not None else None,
        "previous_holder": verdict.get("payload"),
        "authority_boundary": "derived WF84 SQLite lookup mutex only; no canon/portfolio/trade/account authority",
    }
    try:
        RECLAIM_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with RECLAIM_LEDGER.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass


def _try_reclaim(lock_path: Path, verdict: dict[str, Any], role: str) -> bool:
    """Move a stale lock aside atomically so only one racer can reclaim it."""
    salvage = lock_path.with_name(f"{lock_path.name}.stale-{os.getpid()}-{time.monotonic_ns()}")
    try:
        os.rename(str(lock_path), str(salvage))
    except OSError:
        return False
    _record_reclaim(lock_path, verdict, role)
    try:
        os.unlink(str(salvage))
    except OSError:
        pass
    return True


@contextmanager
def wf84_sqlite_mutex(
    db_path: Path,
    *,
    role: str,
    timeout_seconds: float = 180.0,
    poll_seconds: float = 0.25,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> Iterator[Path]:
    """Acquire an exclusive workspace mutex near the WF84 SQLite DB.

    This intentionally serializes readers and writers for the short WF84/WF85
    proof window. It does not make the SQLite file canon, approval, or execution
    authority.

    A lock whose holder process is gone, or which outlives ``stale_after_seconds``,
    is reclaimed so one killed writer cannot wedge every later run.
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
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, encoded)
            break
        except FileExistsError:
            verdict = classify_lock(lock_path, stale_after_seconds)
            if verdict["stale"] and _try_reclaim(lock_path, verdict, role):
                continue
            if time.monotonic() >= deadline:
                raise WF84SqliteMutexTimeout(
                    f"timed out waiting for {lock_path} (holder={verdict.get('payload')}, reason={verdict['reason']})"
                )
            time.sleep(poll_seconds)
    try:
        yield lock_path
    finally:
        if fd is not None:
            os.close(fd)
        # Only drop the lock if it is still ours; it may have been reclaimed.
        if read_lock_payload(lock_path) == payload:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
