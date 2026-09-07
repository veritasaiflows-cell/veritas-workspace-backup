"""Bounded local byte observations; Windows handles pin the checked path chain.

No snapshot-of-the-filesystem claim. Production callers must run acquisition in
a killable process: byte/deadline checks alone cannot cancel stalled file I/O.
"""
from __future__ import annotations
import ctypes
import hashlib
import json
import os
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath


class CaptureError(RuntimeError):
    pass


def relative_parts(raw: str) -> tuple[str, ...]:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise CaptureError("source_path_invalid")
    win = PureWindowsPath(raw)
    parts = tuple(raw.replace("\\", "/").split("/"))
    if win.drive or win.root or any(
        p in ("", ".", "..") or ":" in p or p.endswith((".", " "))
        or p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}
        for p in parts
    ):
        raise CaptureError("source_path_invalid")
    return parts


@contextmanager
def _windows_fd(path: Path, *, mutable: bool = False):
    import msvcrt
    from ctypes import wintypes as w
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
    k.CreateFileW.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.GetFinalPathNameByHandleW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]
    k.GetFinalPathNameByHandleW.restype = w.DWORD
    class Attr(ctypes.Structure):
        _fields_ = [("attributes", w.DWORD), ("tag", w.DWORD)]
    k.GetFileInformationByHandleEx.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]
    handles = []
    fd = None
    absolute = Path(os.path.abspath(path))
    chain = list(reversed(absolute.parents)) + [absolute]
    try:
        for i, item in enumerate(chain):
            final = i == len(chain) - 1
            # No FILE_SHARE_DELETE: ancestors cannot be replaced after inspection.
            # Sources also deny writers; SQLite main-file observation permits
            # writers and therefore MUST pass the metadata stability check.
            sharing = 1 | (2 if not final or mutable else 0)
            access = 0x80000000 if final else 0  # GENERIC_READ / metadata only
            h = k.CreateFileW(str(item), access, sharing, None, 3, 0x00200000 | 0x02000000, None)
            if h == ctypes.c_void_p(-1).value:
                error = ctypes.get_last_error()
                if error in (2, 3):
                    raise FileNotFoundError()
                raise CaptureError("source_open_system_failure")
            handles.append(h)
            a = Attr()
            if not k.GetFileInformationByHandleEx(h, 9, ctypes.byref(a), ctypes.sizeof(a)):
                raise CaptureError("source_identity_system_failure")
            if a.attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                raise CaptureError("source_path_invalid")
            if bool(a.attributes & 0x10) == final:
                raise CaptureError("source_not_regular_file")
            name = ctypes.create_unicode_buffer(32768)
            n = k.GetFinalPathNameByHandleW(h, name, len(name), 0)
            if n == 0 or n >= len(name):
                raise CaptureError("source_identity_system_failure")
            actual = name.value
            if actual.startswith("\\\\?\\"):
                actual = actual[4:]
            if os.path.normcase(actual) != os.path.normcase(str(item)):
                raise CaptureError("source_path_invalid")
        fd = msvcrt.open_osfhandle(handles[-1], os.O_RDONLY | os.O_BINARY)
        handles.pop()  # fd now owns the final handle
        yield fd
    finally:
        if fd is not None:
            os.close(fd)
        for h in reversed(handles):
            k.CloseHandle(h)


@contextmanager
def safe_fd(root: Path, raw: str, *, mutable: bool = False):
    parts = relative_parts(raw)
    root = Path(os.path.abspath(root))
    if os.name == "nt":
        if root.drive.startswith("\\\\"):
            raise CaptureError("source_path_invalid")
        with _windows_fd(root.joinpath(*parts), mutable=mutable) as fd:
            yield fd
        return
    # POSIX fallback uses descriptor-relative no-follow traversal, not resolve()
    # followed by a racy pathname open. Pin every ancestor including root.
    fds = []
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        fds.append(fd)
        for part in (*root.parts[1:], *parts[:-1]):
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            fds.append(fd)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        fds.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise CaptureError("source_not_regular_file")
        yield fd
    finally:
        for fd in reversed(fds):
            os.close(fd)


class Capture:
    """Cache the exact observed bytes once, including guard consumers."""
    def __init__(self, root: Path, deadline: float):
        self.root = Path(root)
        self.deadline = deadline
        self.cache: dict[str, bytes | None] = {}
        self.observations: dict[str, dict] = {}
        self.total = 0

    def check(self):
        if time.monotonic() >= self.deadline:
            raise CaptureError("capture_deadline_exceeded")

    def read(self, raw: str, *, physical: bool = False) -> bytes | None:
        self.check()
        name = "/".join(relative_parts(raw))
        if name in self.cache:
            return self.cache[name]
        if len(self.cache) >= 1024:
            raise CaptureError("capture_count_exceeded")
        limit = 64 * 1024 * 1024 if physical else 10 * 1024 * 1024
        started = datetime.now(timezone.utc).isoformat()
        try:
            with safe_fd(self.root, name, mutable=physical) as fd:
                before = os.fstat(fd)
                if before.st_size > limit:
                    raise CaptureError("capture_size_exceeded")
                chunks = []
                size = 0
                while True:
                    self.check()
                    chunk = os.read(fd, min(65536, limit + 1 - size))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit or self.total + size > 64 * 1024 * 1024:
                        raise CaptureError("capture_size_exceeded")
                    chunks.append(chunk)
                after = os.fstat(fd)
                key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                if key(before) != key(after) or size != before.st_size:
                    raise CaptureError("source_observation_unstable")
                data = b"".join(chunks)
        except FileNotFoundError:
            data = None  # absence only; permission/OS/resource errors are systemic
        except CaptureError:
            raise
        except OSError:
            raise CaptureError("source_read_system_failure") from None
        self.check()
        self.cache[name] = data
        self.total += len(data) if data is not None else 0
        self.observations[name] = {
            "path": name, "exists": data is not None,
            "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "bytes": len(data) if data is not None else 0,
            "started_at_utc": started,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "meaning": "physical_main_file_observation_only_not_sql_snapshot" if physical else "captured_source_bytes",
        }
        return data
