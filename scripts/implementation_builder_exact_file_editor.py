#!/usr/bin/env python3
"""Apply hash-bound text edits to existing implementation-builder worktree files.

The implementation builder runs this pinned read-only helper inside its Docker
sandbox when OpenClaw's atomic file tools cannot replace an exact file bind.
The helper never creates, removes, renames, or follows a link.  It reads the
active worktree manifest, pins existing manifest-allowlisted regular files,
validates every preimage and postimage before the first write, then overwrites
those already-open files in place.  The host-side worktree manager and Main
still own patch generation, validation, and acceptance.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


REQUEST_SCHEMA = "veritas.implementation_builder_exact_file_edits.v1"
MANIFEST_SCHEMA = "veritas.implementation_builder_worktree_manifest.v1"
WORKTREE_ROOT = Path("/worktree")
MANIFEST_PATH = WORKTREE_ROOT / "handoff-manifest.json"
MAX_REQUEST_BYTES = 512_000
MAX_OPERATIONS = 12
MAX_TOTAL_BYTES = 120_000
MAX_FILE_BYTES = 120_000
MAX_LINE_BYTES = 40_000
RESERVED_NAMES = {"handoff-manifest.json", ".veritas-scoped-worktree.json"}
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class ExactFileEditError(RuntimeError):
    """A fail-closed exact-file edit contract violation."""


@dataclass
class PreparedEdit:
    relative_path: str
    fd: int
    before: bytes
    after: bytes
    before_sha256: str
    after_sha256: str


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strict_object(value: Any, required: set[str], optional: set[str] = set()) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - required - optional or not required.issubset(value):
        raise ExactFileEditError("request object fields are missing or unexpected")
    return value


def normalize_relative_path(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ExactFileEditError("edit path must be a string")
    candidate = raw.strip().replace("\\", "/")
    if not candidate or any(ord(char) < 32 for char in candidate):
        raise ExactFileEditError("edit path is empty or contains control characters")
    posix = PurePosixPath(candidate)
    if posix.is_absolute() or any(part in {"", ".", ".."} or ":" in part for part in posix.parts):
        raise ExactFileEditError(f"edit path is not a normalized relative path: {raw}")
    if any(part.casefold() == ".git" for part in posix.parts):
        raise ExactFileEditError("Git metadata paths are forbidden")
    normalized = posix.as_posix()
    if normalized.casefold() in {name.casefold() for name in RESERVED_NAMES}:
        raise ExactFileEditError("worktree control paths are forbidden")
    if normalized != candidate:
        raise ExactFileEditError(f"edit path is not canonically normalized: {raw}")
    return normalized


def _lower_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ExactFileEditError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _decode_base64(value: Any, *, field: str, maximum: int) -> bytes:
    if not isinstance(value, str) or len(value) > ((maximum + 2) // 3) * 4 + 8:
        raise ExactFileEditError(f"{field} is missing or too large")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ExactFileEditError(f"{field} is not canonical base64") from exc
    if len(decoded) > maximum:
        raise ExactFileEditError(f"{field} exceeds its byte limit")
    return decoded


def decode_request_b64(value: str) -> tuple[dict[str, Any], str]:
    raw = _decode_base64(value, field="request_b64", maximum=MAX_REQUEST_BYTES)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExactFileEditError("request_b64 does not contain one UTF-8 JSON object") from exc
    if not isinstance(payload, dict):
        raise ExactFileEditError("request payload must be an object")
    return payload, sha256_bytes(raw)


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExactFileEditError("active worktree manifest is unreadable") from exc
    _strict_object(
        payload,
        {
            "schema",
            "generated_at_utc",
            "job_id",
            "source_base_label",
            "limits",
            "file_count",
            "total_bytes",
            "estimated_context_tokens",
            "files",
            "allowed_write_paths",
            "execution_environment",
            "authority",
        },
        {"output_placeholders"},
    )
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise ExactFileEditError("worktree manifest schema mismatch")
    authority = payload.get("authority")
    if not isinstance(authority, dict) or authority.get("writable_root") != "/worktree":
        raise ExactFileEditError("worktree manifest authority mismatch")
    if authority.get("network_allowed") is not False or authority.get("main_acceptance_required") is not True:
        raise ExactFileEditError("worktree manifest safety flags mismatch")
    allowed = payload.get("allowed_write_paths")
    if not isinstance(allowed, list) or not 1 <= len(allowed) <= MAX_OPERATIONS:
        raise ExactFileEditError("worktree manifest write allowlist is invalid")
    normalized = [normalize_relative_path(item) for item in allowed]
    if normalized != sorted(set(normalized)):
        raise ExactFileEditError("worktree manifest write allowlist is not normalized and unique")
    return payload


def _validate_postimage(payload: bytes, relative_path: str) -> None:
    if len(payload) > MAX_FILE_BYTES:
        raise ExactFileEditError(f"postimage exceeds the per-file limit: {relative_path}")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExactFileEditError(f"postimage is not UTF-8: {relative_path}") from exc
    if any(len(line.encode("utf-8")) > MAX_LINE_BYTES for line in text.splitlines(keepends=True)):
        raise ExactFileEditError(f"postimage contains an overlong line: {relative_path}")


def _apply_operation(before: bytes, operation: dict[str, Any], relative_path: str) -> bytes:
    has_edits = "edits" in operation
    has_content = "content_b64" in operation
    if has_edits == has_content:
        raise ExactFileEditError(f"operation must use exactly one edit mode: {relative_path}")
    if has_content:
        return _decode_base64(operation["content_b64"], field="content_b64", maximum=MAX_FILE_BYTES)
    try:
        text = before.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExactFileEditError(f"preimage is not UTF-8: {relative_path}") from exc
    edits = operation.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ExactFileEditError(f"edits must be a non-empty list: {relative_path}")
    for edit in edits:
        _strict_object(edit, {"old", "new"})
        old = edit.get("old")
        new = edit.get("new")
        if not isinstance(old, str) or not old or not isinstance(new, str):
            raise ExactFileEditError(f"each edit needs non-empty old text and string new text: {relative_path}")
        if text.count(old) != 1:
            raise ExactFileEditError(f"edit preimage must match exactly once: {relative_path}")
        text = text.replace(old, new, 1)
    return text.encode("utf-8")


def _open_existing_file_posix(root_fd: int, relative_path: str) -> int:
    parts = PurePosixPath(relative_path).parts
    directory_fd = os.dup(root_fd)
    try:
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        for segment in parts[:-1]:
            next_fd = os.open(segment, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        return os.open(parts[-1], flags, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)


def _open_existing_file(root: Path, root_fd: int | None, relative_path: str) -> int:
    if os.name == "posix":
        if root_fd is None:
            raise ExactFileEditError("root descriptor is unavailable")
        return _open_existing_file_posix(root_fd, relative_path)
    candidate = root.joinpath(*PurePosixPath(relative_path).parts)
    root_resolved = root.resolve(strict=True)
    if candidate.is_symlink() or candidate.resolve(strict=True).parent != candidate.parent.resolve(strict=True):
        raise ExactFileEditError(f"linked edit target is forbidden: {relative_path}")
    try:
        candidate.resolve(strict=True).relative_to(root_resolved)
    except ValueError as exc:
        raise ExactFileEditError(f"edit target escapes the worktree: {relative_path}") from exc
    return os.open(candidate, os.O_RDWR | getattr(os, "O_BINARY", 0))


def _read_fd(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, 65_536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise ExactFileEditError("preimage exceeds the per-file limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _write_fd(fd: int, payload: bytes) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short exact-file write")
        view = view[written:]
    os.ftruncate(fd, len(payload))
    os.fsync(fd)


def prepare_edits(
    request: dict[str, Any],
    *,
    root: Path = WORKTREE_ROOT,
    manifest_path: Path = MANIFEST_PATH,
) -> tuple[str, list[PreparedEdit]]:
    _strict_object(request, {"schema", "job_id", "operations"})
    if request.get("schema") != REQUEST_SCHEMA:
        raise ExactFileEditError("request schema mismatch")
    manifest = load_manifest(manifest_path)
    job_id = request.get("job_id")
    if not isinstance(job_id, str) or job_id != manifest.get("job_id"):
        raise ExactFileEditError("request job_id does not match the active worktree")
    operations = request.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= MAX_OPERATIONS:
        raise ExactFileEditError("request operations list is invalid")
    allowed = set(manifest["allowed_write_paths"])
    seen: set[str] = set()
    prepared: list[PreparedEdit] = []
    root_fd: int | None = None
    try:
        if os.name == "posix":
            root_fd = os.open(
                root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
        for raw_operation in operations:
            operation = _strict_object(
                raw_operation,
                {"path", "expected_sha256"},
                {"edits", "content_b64"},
            )
            relative_path = normalize_relative_path(operation.get("path"))
            if relative_path not in allowed:
                raise ExactFileEditError(f"edit target is outside the manifest allowlist: {relative_path}")
            if relative_path in seen:
                raise ExactFileEditError(f"duplicate edit target: {relative_path}")
            seen.add(relative_path)
            expected_sha256 = _lower_sha256(operation.get("expected_sha256"), field="expected_sha256")
            fd = _open_existing_file(root, root_fd, relative_path)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ExactFileEditError(f"edit target is not one unlinked regular file: {relative_path}")
                before = _read_fd(fd)
                before_sha256 = sha256_bytes(before)
                if before_sha256 != expected_sha256:
                    raise ExactFileEditError(f"edit target preimage hash mismatch: {relative_path}")
                after = _apply_operation(before, operation, relative_path)
                _validate_postimage(after, relative_path)
                if after == before:
                    raise ExactFileEditError(f"edit operation is a no-op: {relative_path}")
                prepared.append(
                    PreparedEdit(
                        relative_path=relative_path,
                        fd=fd,
                        before=before,
                        after=after,
                        before_sha256=before_sha256,
                        after_sha256=sha256_bytes(after),
                    )
                )
                fd = -1
            finally:
                if fd >= 0:
                    os.close(fd)
        if sum(len(item.after) for item in prepared) > MAX_TOTAL_BYTES:
            raise ExactFileEditError("combined postimages exceed the total byte limit")
        return str(job_id), prepared
    except Exception:
        for item in prepared:
            os.close(item.fd)
        raise
    finally:
        if root_fd is not None:
            os.close(root_fd)


def commit_edits(job_id: str, prepared: Sequence[PreparedEdit], request_sha256: str) -> dict[str, Any]:
    written: list[PreparedEdit] = []
    try:
        for item in prepared:
            _write_fd(item.fd, item.after)
            written.append(item)
            if sha256_bytes(_read_fd(item.fd)) != item.after_sha256:
                raise ExactFileEditError(f"post-write hash mismatch: {item.relative_path}")
    except Exception as exc:
        rollback_errors: list[str] = []
        for item in reversed(written):
            try:
                _write_fd(item.fd, item.before)
            except Exception as rollback_exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_errors.append(f"{item.relative_path}:{type(rollback_exc).__name__}")
        detail = f"exact-file write failed and rollback_errors={rollback_errors}" if rollback_errors else "exact-file write failed; written files restored"
        raise ExactFileEditError(detail) from exc
    finally:
        for item in prepared:
            os.close(item.fd)
    return {
        "schema": "veritas.implementation_builder_exact_file_edit_result.v1",
        "status": "ok",
        "job_id": job_id,
        "request_sha256": request_sha256,
        "changed_file_count": len(prepared),
        "changed_files": [
            {
                "relative_path": item.relative_path,
                "before_sha256": item.before_sha256,
                "after_sha256": item.after_sha256,
                "bytes": len(item.after),
            }
            for item in prepared
        ],
        "files_created": False,
        "files_removed": False,
        "main_acceptance_claimed": False,
    }


def apply_request(
    request: dict[str, Any],
    *,
    request_sha256: str,
    root: Path = WORKTREE_ROOT,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    job_id, prepared = prepare_edits(request, root=root, manifest_path=manifest_path)
    return commit_edits(job_id, prepared, request_sha256)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-b64", required=True, help="Base64 UTF-8 JSON request envelope")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        request, request_sha256 = decode_request_b64(args.request_b64)
        result = apply_request(request, request_sha256=request_sha256)
    except (ExactFileEditError, OSError) as exc:
        print(
            json.dumps(
                {
                    "schema": "veritas.implementation_builder_exact_file_edit_result.v1",
                    "status": "blocked",
                    "error": str(exc),
                    "main_acceptance_claimed": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
