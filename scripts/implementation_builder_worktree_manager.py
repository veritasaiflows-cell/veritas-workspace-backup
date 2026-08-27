#!/usr/bin/env python3
"""Prepare and verify the implementation-builder's isolated writable worktree.

This controller is deliberately model-free.  It stages only an explicit frozen
handoff, creates a local Git baseline, and records hashes that Main can verify
before and after an isolated builder run.  It never changes OpenClaw config,
starts an agent, deletes a prior worktree, or applies the builder's output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


MANIFEST_SCHEMA = "veritas.implementation_builder_worktree_manifest.v1"
SENTINEL_SCHEMA = "veritas.implementation_builder_worktree_sentinel.v1"
PROOF_SCHEMA = "veritas.implementation_builder_worktree_proof.v1"
MAX_FILES = 6
MAX_TOTAL_BYTES = 120_000
MAX_FILE_BYTES = MAX_TOTAL_BYTES
MAX_LINE_BYTES = 40_000
MAX_ESTIMATED_CONTEXT_TOKENS = 30_000
MAX_ALLOWED_WRITE_PATHS = 12
MANIFEST_FILENAME = "handoff-manifest.json"
SENTINEL_FILENAME = ".veritas-scoped-worktree.json"
WORKTREE_CONTROL_FILES = frozenset({MANIFEST_FILENAME})
RESERVED_CONTROL_FILES = frozenset({MANIFEST_FILENAME, SENTINEL_FILENAME})
RESERVED_CONTROL_FILES_FOLDED = frozenset(
    item.casefold() for item in RESERVED_CONTROL_FILES
)
PYTHON_BYTECODE_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPYCACHEPREFIX": "/tmp/veritas-implementation-builder-pycache",
}
WINDOWS_RESERVED_BASENAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)

DEFAULT_AGENT_WORKSPACE = (
    Path.home() / ".openclaw" / "workspaces" / "implementation-builder"
)
DEFAULT_HANDOFF_ROOT = DEFAULT_AGENT_WORKSPACE / "handoff"
DEFAULT_TARGET = DEFAULT_HANDOFF_ROOT / "scoped-worktree"


class WorktreeError(RuntimeError):
    """A fail-closed scoped-worktree contract violation."""


@dataclass(frozen=True)
class FrozenFile:
    relative_path: str
    source_path: Path
    byte_count: int
    sha256: str

    def manifest_row(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "bytes": self.byte_count,
            "sha256": self.sha256,
            "encoding": "utf-8",
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_relative_path(raw: str) -> str:
    candidate = raw.strip().replace("\\", "/")
    if not candidate:
        raise WorktreeError("relative path must not be empty")
    if any(ord(char) < 32 for char in candidate):
        raise WorktreeError(f"control characters are forbidden in paths: {raw}")
    posix = PurePosixPath(candidate)
    if posix.is_absolute() or any(":" in part for part in posix.parts):
        raise WorktreeError(f"absolute path is forbidden: {raw}")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise WorktreeError(f"path traversal is forbidden: {raw}")
    for part in posix.parts:
        if part.casefold() == ".git":
            raise WorktreeError(f"reserved Git control path is forbidden: {raw}")
        if part.rstrip(" .") != part:
            raise WorktreeError(f"Windows trailing dot or space is forbidden: {raw}")
        if any(char in '<>"|?*' for char in part):
            raise WorktreeError(f"Windows-invalid path character is forbidden: {raw}")
        windows_basename = part.split(".", 1)[0].rstrip(" .").casefold()
        if windows_basename in WINDOWS_RESERVED_BASENAMES:
            raise WorktreeError(f"Windows device path alias is forbidden: {raw}")
    normalized = posix.as_posix()
    if normalized.casefold() in RESERVED_CONTROL_FILES_FOLDED:
        raise WorktreeError(f"reserved control path is forbidden: {raw}")
    return normalized


def normalize_path_list(values: Sequence[str], *, label: str) -> list[str]:
    normalized = [normalize_relative_path(item) for item in values]
    folded = [item.casefold() for item in normalized]
    if len(set(folded)) != len(folded):
        raise WorktreeError(f"{label} contains duplicate or case-colliding paths")
    return sorted(normalized)


def is_link_or_reparse(path: Path) -> bool:
    """Return True for symlinks, junctions, or other Windows reparse points."""
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise WorktreeError(f"unable to inspect path link state: {path}") from exc


def assert_exact_target(target: Path, handoff_root: Path) -> tuple[Path, Path]:
    root = Path(os.path.abspath(str(handoff_root.expanduser())))
    lexical_target = Path(os.path.abspath(str(target.expanduser())))
    expected = root / "scoped-worktree"
    if os.path.normcase(str(lexical_target)) != os.path.normcase(str(expected)):
        raise WorktreeError(
            f"target must resolve exactly to the scoped worktree: {expected}"
        )
    if is_link_or_reparse(root):
        raise WorktreeError("handoff root must not be a symlink, junction, or reparse point")
    if is_link_or_reparse(lexical_target):
        raise WorktreeError("scoped worktree must not be a symlink, junction, or reparse point")
    return lexical_target, root


def sentinel_path_for(handoff_root: Path) -> Path:
    """Return the host control path kept outside the Git worktree inventory."""
    return handoff_root / SENTINEL_FILENAME


def require_python_bytecode_environment(manifest: dict[str, Any]) -> None:
    if manifest.get("execution_environment") != PYTHON_BYTECODE_ENV:
        raise WorktreeError("manifest Python bytecode environment contract mismatch")


def _resolved_source_file(source_root: Path, relative_path: str) -> Path:
    root = source_root.expanduser().resolve(strict=True)
    candidate = root.joinpath(*PurePosixPath(relative_path).parts)
    if candidate.is_symlink():
        raise WorktreeError(f"source symlink is forbidden: {relative_path}")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorktreeError(f"source path escapes the source root: {relative_path}") from exc
    if not resolved.is_file():
        raise WorktreeError(f"source path is not a regular file: {relative_path}")
    return resolved


def inspect_frozen_files(source_root: Path, relative_paths: Sequence[str]) -> list[FrozenFile]:
    if not relative_paths:
        raise WorktreeError("at least one --file is required")
    if len(relative_paths) > MAX_FILES:
        raise WorktreeError(f"handoff exceeds the {MAX_FILES}-file limit")

    normalized = normalize_path_list(relative_paths, label="handoff")

    frozen: list[FrozenFile] = []
    total_bytes = 0
    for relative_path in sorted(normalized):
        source_path = _resolved_source_file(source_root, relative_path)
        payload = source_path.read_bytes()
        byte_count = len(payload)
        if byte_count > MAX_FILE_BYTES:
            raise WorktreeError(
                f"{relative_path} exceeds the {MAX_FILE_BYTES}-byte file limit"
            )
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorktreeError(f"{relative_path} is not valid UTF-8") from exc
        longest_line = max((len(line.encode("utf-8")) for line in text.splitlines()), default=0)
        if longest_line > MAX_LINE_BYTES:
            raise WorktreeError(
                f"{relative_path} exceeds the {MAX_LINE_BYTES}-byte physical-line limit"
            )
        total_bytes += byte_count
        frozen.append(
            FrozenFile(
                relative_path=relative_path,
                source_path=source_path,
                byte_count=byte_count,
                sha256=sha256_bytes(payload),
            )
        )

    estimated_tokens = (total_bytes + 3) // 4
    if total_bytes > MAX_TOTAL_BYTES:
        raise WorktreeError(f"handoff exceeds the {MAX_TOTAL_BYTES}-byte total limit")
    if estimated_tokens > MAX_ESTIMATED_CONTEXT_TOKENS:
        raise WorktreeError(
            f"handoff exceeds the {MAX_ESTIMATED_CONTEXT_TOKENS}-token estimate limit"
        )
    return frozen


def run_git(cwd: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git:
        raise WorktreeError("git executable is unavailable")
    completed = subprocess.run(
        [git, *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise WorktreeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def run_git_bytes(cwd: Path, *args: str) -> bytes:
    """Run one Git query and preserve its exact stdout bytes."""
    git = shutil.which("git")
    if not git:
        raise WorktreeError("git executable is unavailable")
    completed = subprocess.run(
        [git, *args],
        cwd=cwd,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise WorktreeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def refresh_git_index(target: Path) -> None:
    """Refresh cached stat data before trusting a sandbox Git inventory.

    Git may return 1 when an allowed builder file is genuinely modified.  The
    byte/content inventory that immediately follows is authoritative for that
    case; every other Git failure remains fatal.
    """
    git = shutil.which("git")
    if not git:
        raise WorktreeError("git executable is unavailable")
    completed = subprocess.run(
        [git, "update-index", "--refresh", "--"],
        cwd=target,
        check=False,
        capture_output=True,
    )
    if completed.returncode not in (0, 1):
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise WorktreeError(f"git update-index --refresh failed: {detail}")


def git_path_matches_head_blob(target: Path, relative_path: str) -> bool:
    """Require exact worktree/HEAD bytes and an empty content diff."""
    normalized = (
        relative_path
        if relative_path in WORKTREE_CONTROL_FILES
        else normalize_relative_path(relative_path)
    )
    head_oid = run_git(target, "rev-parse", f"HEAD:{normalized}").strip().lower()
    worktree_oid = run_git(
        target, "hash-object", "--no-filters", "--", normalized
    ).strip().lower()
    content_diff = run_git_bytes(
        target,
        "diff",
        "--binary",
        "--no-ext-diff",
        "HEAD",
        "--",
        normalized,
    )
    return bool(head_oid) and head_oid == worktree_oid and not content_diff


def _normalize_git_inventory_paths(raw_paths: list[bytes]) -> list[str]:
    """Decode exact Git paths and enforce the scoped path contract."""
    normalized_paths: list[str] = []
    for raw_path in raw_paths:
        try:
            decoded = raw_path.decode("utf-8")
            normalized = (
                decoded
                if decoded in RESERVED_CONTROL_FILES
                else normalize_relative_path(decoded)
            )
        except (UnicodeDecodeError, WorktreeError) as exc:
            raise WorktreeError("Git inventory contains an invalid path") from exc
        if decoded != normalized:
            raise WorktreeError("Git inventory path is not canonically normalized")
        normalized_paths.append(normalized)
    return sorted(set(normalized_paths))


def _decode_git_nul_paths(raw: bytes) -> list[str]:
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise WorktreeError("Git path inventory is not NUL terminated")
    return _normalize_git_inventory_paths(raw[:-1].split(b"\0"))


def _decode_git_status_paths(raw: bytes) -> list[str]:
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise WorktreeError("Git status inventory is not NUL terminated")
    raw_paths: list[bytes] = []
    for record in raw[:-1].split(b"\0"):
        if len(record) < 4 or record[2:3] != b" ":
            raise WorktreeError("Git status inventory contains a malformed record")
        raw_paths.append(record[3:])
    return _normalize_git_inventory_paths(raw_paths)


def capture_git_path_inventory(
    target: Path,
    *,
    allow_identical_status_only_paths: Sequence[str] = (),
) -> dict[str, Any]:
    """Capture one internally stable tracked/untracked Git path inventory."""
    refresh_git_index(target)
    status_args = (
        "-c",
        "core.quotepath=false",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--no-renames",
        "--ignore-submodules=none",
    )
    status_before = run_git_bytes(target, *status_args)
    tracked_diff = run_git_bytes(
        target,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        "HEAD",
        "--",
    )
    untracked = run_git_bytes(
        target,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
    )
    status_after = run_git_bytes(target, *status_args)
    if status_before != status_after:
        raise WorktreeError("Git inventory changed during capture")
    raw_status_paths = _decode_git_status_paths(status_before)
    tracked_paths = _decode_git_nul_paths(tracked_diff)
    untracked_paths = _decode_git_nul_paths(untracked)
    paths = sorted(set(tracked_paths) | set(untracked_paths))
    allowed_metadata_paths = set(allow_identical_status_only_paths)
    if not allowed_metadata_paths.issubset(WORKTREE_CONTROL_FILES):
        raise WorktreeError("status-only metadata drift allowlist is invalid")
    status_only_paths = sorted(set(raw_status_paths) - set(paths))
    packaging_metadata_drift_paths = [
        path
        for path in status_only_paths
        if path in allowed_metadata_paths and git_path_matches_head_blob(target, path)
    ]
    status_paths = sorted(
        set(raw_status_paths) - set(packaging_metadata_drift_paths)
    )
    if status_paths != paths:
        raise WorktreeError("Git status and tracked/untracked inventories differ")
    return {
        "paths": paths,
        "status_paths": status_paths,
        "packaging_metadata_drift_paths": packaging_metadata_drift_paths,
        "tracked_diff_paths": tracked_paths,
        "untracked_paths": untracked_paths,
        "status_porcelain_sha256": sha256_bytes(status_before),
        "tracked_diff_output_sha256": sha256_bytes(tracked_diff),
        "untracked_output_sha256": sha256_bytes(untracked),
    }


def git_inventory_matches_changed_paths(
    inventory: Any, changed_paths: Sequence[str]
) -> bool:
    required_fields = {
        "paths",
        "status_paths",
        "packaging_metadata_drift_paths",
        "tracked_diff_paths",
        "untracked_paths",
        "status_porcelain_sha256",
        "tracked_diff_output_sha256",
        "untracked_output_sha256",
    }
    legacy_required_fields = required_fields - {"packaging_metadata_drift_paths"}
    if not isinstance(inventory, dict) or set(inventory) not in (
        required_fields,
        legacy_required_fields,
    ):
        return False
    legacy_inventory = set(inventory) == legacy_required_fields
    path_lists = {
        name: (
            []
            if legacy_inventory and name == "packaging_metadata_drift_paths"
            else inventory.get(name)
        )
        for name in (
            "paths",
            "status_paths",
            "packaging_metadata_drift_paths",
            "tracked_diff_paths",
            "untracked_paths",
        )
    }
    if any(
        not isinstance(paths, list)
        or any(not isinstance(path, str) for path in paths)
        or paths != sorted(set(paths))
        for paths in path_lists.values()
    ):
        return False
    tracked_paths = path_lists["tracked_diff_paths"]
    untracked_paths = path_lists["untracked_paths"]
    metadata_paths = path_lists["packaging_metadata_drift_paths"]
    return (
        path_lists["paths"] == sorted(changed_paths)
        and path_lists["status_paths"] == sorted(changed_paths)
        and set(metadata_paths).isdisjoint(path_lists["paths"])
        and set(tracked_paths).isdisjoint(untracked_paths)
        and sorted(set(tracked_paths) | set(untracked_paths)) == sorted(changed_paths)
        and all(
            isinstance(inventory.get(name), str)
            and len(inventory[name]) == 64
            and inventory[name] == inventory[name].lower()
            and all(char in "0123456789abcdef" for char in inventory[name])
            for name in (
                "status_porcelain_sha256",
                "tracked_diff_output_sha256",
                "untracked_output_sha256",
            )
        )
    )


def git_inventory_checkpoints_sha256(
    checkpoints: Any, changed_paths: Sequence[str]
) -> str:
    """Return the canonical aggregate digest for two equal inventories."""
    required_checkpoints = {"before_binding_recheck", "after_binding_recheck"}
    if not isinstance(checkpoints, dict) or set(checkpoints) != required_checkpoints:
        raise WorktreeError("Git inventory checkpoints are missing or malformed")
    before = checkpoints["before_binding_recheck"]
    after = checkpoints["after_binding_recheck"]
    if (
        before != after
        or not git_inventory_matches_changed_paths(before, changed_paths)
        or not git_inventory_matches_changed_paths(after, changed_paths)
    ):
        raise WorktreeError("Git inventory checkpoints do not match the declared changes")
    canonical_payload = {
        "schema": "veritas.git_path_inventory_checkpoints.v1",
        "checkpoints": checkpoints,
    }
    try:
        canonical_bytes = json.dumps(
            canonical_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WorktreeError("Git inventory checkpoints are not canonically serializable") from exc
    return sha256_bytes(canonical_bytes)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorktreeError(f"invalid JSON control file: {path}") from exc
    if not isinstance(payload, dict):
        raise WorktreeError(f"JSON control file must contain an object: {path}")
    return payload


def prepare_worktree(
    *,
    job_id: str,
    source_root: Path,
    source_base_label: str,
    relative_paths: Sequence[str],
    allowed_output_paths: Sequence[str] = (),
    target: Path = DEFAULT_TARGET,
    handoff_root: Path = DEFAULT_HANDOFF_ROOT,
) -> dict[str, Any]:
    target, handoff_root = assert_exact_target(target, handoff_root)
    sentinel_path = sentinel_path_for(handoff_root)
    job_id = job_id.strip()
    source_base_label = source_base_label.strip()
    if not job_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:" for char in job_id):
        raise WorktreeError("job id must use only letters, digits, dash, underscore, dot, or colon")
    if not source_base_label:
        raise WorktreeError("source base label must not be empty")

    frozen = inspect_frozen_files(source_root, relative_paths)
    frozen_paths = [item.relative_path for item in frozen]
    normalized_outputs = normalize_path_list(
        allowed_output_paths, label="allowed output path list"
    )
    frozen_folded = {item.casefold() for item in frozen_paths}
    overlap = [item for item in normalized_outputs if item.casefold() in frozen_folded]
    if overlap:
        raise WorktreeError(
            "allowed output paths must be new paths, not frozen inputs: "
            + ", ".join(overlap)
        )
    allowed_write_paths = sorted(frozen_paths + normalized_outputs)
    if len(allowed_write_paths) > MAX_ALLOWED_WRITE_PATHS:
        raise WorktreeError(
            f"handoff exceeds the {MAX_ALLOWED_WRITE_PATHS}-path write allowlist limit"
        )
    if target.exists() and any(target.iterdir()):
        raise WorktreeError(
            "scoped worktree is not empty; close and move it explicitly before preparing another job"
        )
    if sentinel_path.exists() or is_link_or_reparse(sentinel_path):
        raise WorktreeError(
            "scoped-worktree sentinel already exists; move it explicitly before preparing another job"
        )

    handoff_root.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()
    for item in frozen:
        destination = target.joinpath(*PurePosixPath(item.relative_path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item.source_path, destination)

    total_bytes = sum(item.byte_count for item in frozen)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at_utc": created_at,
        "job_id": job_id,
        "source_base_label": source_base_label,
        "limits": {
            "max_files": MAX_FILES,
            "max_file_bytes": MAX_FILE_BYTES,
            "max_line_bytes": MAX_LINE_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
            "max_estimated_context_tokens": MAX_ESTIMATED_CONTEXT_TOKENS,
            "max_allowed_write_paths": MAX_ALLOWED_WRITE_PATHS,
        },
        "file_count": len(frozen),
        "total_bytes": total_bytes,
        "estimated_context_tokens": (total_bytes + 3) // 4,
        "files": [item.manifest_row() for item in frozen],
        "allowed_write_paths": allowed_write_paths,
        "execution_environment": dict(PYTHON_BYTECODE_ENV),
        "authority": {
            "writable_root": "/worktree",
            "main_acceptance_required": True,
            "runtime_config_mutation_allowed": False,
            "network_allowed": False,
            "external_delivery_allowed": False,
        },
    }
    sentinel = {
        "schema": SENTINEL_SCHEMA,
        "job_id": job_id,
        "state": "active",
        "created_at_utc": created_at,
    }
    write_json(target / MANIFEST_FILENAME, manifest)
    write_json(sentinel_path, sentinel)

    run_git(target, "init", "--quiet")
    # Preserve the frozen handoff byte-for-byte in the baseline commit.  The
    # host may have a global core.autocrlf=true setting while the isolated
    # Linux runner does not; allowing the host filter to normalize staged
    # bytes makes an otherwise untouched worktree appear dirty in /worktree.
    run_git(target, "config", "core.autocrlf", "false")
    run_git(target, "config", "user.name", "Veritas Implementation Builder")
    run_git(target, "config", "user.email", "implementation-builder@localhost")
    baseline_paths = sorted(frozen_paths + list(WORKTREE_CONTROL_FILES))
    run_git(target, "add", "--force", "--", *baseline_paths)
    run_git(target, "commit", "--quiet", "-m", f"Frozen builder handoff: {job_id}")
    baseline_commit = run_git(target, "rev-parse", "HEAD").strip()
    tracked_baseline = sorted(
        item for item in run_git(target, "ls-files", "-z", "--").split("\0") if item
    )
    if tracked_baseline != baseline_paths:
        raise WorktreeError("Git baseline does not exactly match the frozen manifest")

    proof = {
        "schema": PROOF_SCHEMA,
        "action": "prepare",
        "status": "ok",
        "generated_at_utc": utc_now(),
        "job_id": job_id,
        "target": str(target),
        "baseline_commit": baseline_commit,
        "manifest_sha256": sha256_file(target / MANIFEST_FILENAME),
        "sentinel_path": str(sentinel_path),
        "sentinel_sha256": sha256_file(sentinel_path),
        "file_count": len(frozen),
        "total_bytes": total_bytes,
        "estimated_context_tokens": (total_bytes + 3) // 4,
        "files": [item.manifest_row() for item in frozen],
        "allowed_write_paths": allowed_write_paths,
        "writes_outside_target_attempted": False,
        "config_mutation_attempted": False,
        "network_attempted": False,
    }
    return proof


def verify_worktree(
    *,
    target: Path = DEFAULT_TARGET,
    handoff_root: Path = DEFAULT_HANDOFF_ROOT,
) -> dict[str, Any]:
    target, handoff_root = assert_exact_target(target, handoff_root)
    sentinel_path = sentinel_path_for(handoff_root)
    manifest = load_json(target / MANIFEST_FILENAME)
    sentinel = load_json(sentinel_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise WorktreeError("manifest schema mismatch")
    require_python_bytecode_environment(manifest)
    if sentinel.get("schema") != SENTINEL_SCHEMA or sentinel.get("state") != "active":
        raise WorktreeError("sentinel is not an active scoped-worktree contract")
    if manifest.get("job_id") != sentinel.get("job_id"):
        raise WorktreeError("manifest and sentinel job ids differ")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILES:
        raise WorktreeError("manifest file list is invalid")
    allowed_write_paths = manifest.get("allowed_write_paths")
    if not isinstance(allowed_write_paths, list):
        raise WorktreeError("manifest write allowlist is missing")
    normalized_allowed = normalize_path_list(
        [str(item) for item in allowed_write_paths], label="manifest write allowlist"
    )
    if normalized_allowed != allowed_write_paths:
        raise WorktreeError("manifest write allowlist is not normalized and sorted")
    if len(normalized_allowed) > MAX_ALLOWED_WRITE_PATHS:
        raise WorktreeError("manifest write allowlist exceeds its limit")
    frozen_paths: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise WorktreeError("manifest file row is invalid")
        relative_path = normalize_relative_path(str(row.get("relative_path") or ""))
        frozen_paths.append(relative_path)
        file_path = target.joinpath(*PurePosixPath(relative_path).parts)
        if not file_path.is_file() or file_path.is_symlink():
            raise WorktreeError(f"staged file is missing or not regular: {relative_path}")
        if file_path.stat().st_size != row.get("bytes"):
            raise WorktreeError(f"staged file size mismatch: {relative_path}")
        if sha256_file(file_path) != row.get("sha256"):
            raise WorktreeError(f"staged file hash mismatch: {relative_path}")
    if not {item.casefold() for item in frozen_paths}.issubset(
        {item.casefold() for item in normalized_allowed}
    ):
        raise WorktreeError("manifest write allowlist omits a frozen input")
    if not git_path_matches_head_blob(target, MANIFEST_FILENAME):
        raise WorktreeError(
            "worktree manifest bytes or content diff differ from the committed blob"
        )
    inventory_before = capture_git_path_inventory(
        target,
        allow_identical_status_only_paths=(MANIFEST_FILENAME,),
    )
    inventory_after = capture_git_path_inventory(
        target,
        allow_identical_status_only_paths=(MANIFEST_FILENAME,),
    )
    inventory_checkpoints = {
        "before_binding_recheck": inventory_before,
        "after_binding_recheck": inventory_after,
    }
    inventory_sha256 = git_inventory_checkpoints_sha256(
        inventory_checkpoints, []
    )
    baseline_commit = run_git(target, "rev-parse", "HEAD").strip()
    return {
        "schema": PROOF_SCHEMA,
        "action": "verify",
        "status": "ok",
        "generated_at_utc": utc_now(),
        "job_id": manifest.get("job_id"),
        "target": str(target),
        "baseline_commit": baseline_commit,
        "manifest_sha256": sha256_file(target / MANIFEST_FILENAME),
        "sentinel_path": str(sentinel_path),
        "sentinel_sha256": sha256_file(sentinel_path),
        "file_count": len(rows),
        "allowed_write_paths": normalized_allowed,
        "clean": True,
        "packaging_metadata_drift_paths": inventory_after[
            "packaging_metadata_drift_paths"
        ],
        "git_path_inventory_checkpoints": inventory_checkpoints,
        "git_path_inventory_sha256": inventory_sha256,
    }


def _all_changed_paths(target: Path) -> list[str]:
    tracked = {
        item
        for item in run_git(target, "diff", "--name-only", "-z", "HEAD", "--").split("\0")
        if item
    }
    untracked = {
        item
        for item in run_git(target, "ls-files", "--others", "-z", "--").split("\0")
        if item
    }
    return sorted(tracked | untracked)


def verify_filesystem_scope(target: Path, allowed_write_paths: Sequence[str]) -> None:
    """Reject every on-disk entry outside controls and allowlisted path ancestors."""
    allowed_files = set(allowed_write_paths) | set(WORKTREE_CONTROL_FILES)
    allowed_directories: set[str] = set()
    for relative_path in allowed_files:
        parts = PurePosixPath(relative_path).parts
        for index in range(1, len(parts)):
            allowed_directories.add(PurePosixPath(*parts[:index]).as_posix())

    unexpected: list[str] = []
    for current_root, directory_names, file_names in os.walk(target, topdown=True, followlinks=False):
        current = Path(current_root)
        relative_root = current.relative_to(target)
        kept_directories: list[str] = []
        for name in directory_names:
            relative = (relative_root / name).as_posix()
            child = current / name
            if relative == ".git":
                if is_link_or_reparse(child) or not child.is_dir():
                    unexpected.append(relative)
                continue
            if is_link_or_reparse(child) or relative not in allowed_directories:
                unexpected.append(relative)
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in file_names:
            relative = (relative_root / name).as_posix()
            child = current / name
            if is_link_or_reparse(child) or relative not in allowed_files:
                unexpected.append(relative)
    if unexpected:
        raise WorktreeError(
            "worktree contains entries outside the manifest scope: "
            + ", ".join(sorted(set(unexpected)))
        )


def inspect_changed_file(target: Path, relative_path: str) -> dict[str, Any]:
    """Validate one existing builder output before Git renders a patch."""
    file_path = target.joinpath(*PurePosixPath(relative_path).parts)
    current = target
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if is_link_or_reparse(current):
            raise WorktreeError(f"builder output link or reparse point is forbidden: {relative_path}")
    try:
        resolved = file_path.resolve(strict=True)
        resolved.relative_to(target.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise WorktreeError(f"builder output escapes the scoped worktree: {relative_path}") from exc
    if not resolved.is_file():
        raise WorktreeError(f"builder output is not a regular file: {relative_path}")
    byte_count = resolved.stat().st_size
    if byte_count > MAX_FILE_BYTES:
        raise WorktreeError(
            f"builder output exceeds the {MAX_FILE_BYTES}-byte file limit: {relative_path}"
        )
    payload = resolved.read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorktreeError(f"builder output is not valid UTF-8: {relative_path}") from exc
    longest_line = max((len(line.encode("utf-8")) for line in text.splitlines()), default=0)
    if longest_line > MAX_LINE_BYTES:
        raise WorktreeError(
            f"builder output exceeds the {MAX_LINE_BYTES}-byte physical-line limit: {relative_path}"
        )
    return {
        "relative_path": relative_path,
        "exists": True,
        "bytes": byte_count,
        "sha256": sha256_bytes(payload),
    }


def close_worktree(
    *,
    patch_path: Path,
    target: Path = DEFAULT_TARGET,
    handoff_root: Path = DEFAULT_HANDOFF_ROOT,
) -> dict[str, Any]:
    target, handoff_root = assert_exact_target(target, handoff_root)
    manifest_path = target / MANIFEST_FILENAME
    manifest = load_json(manifest_path)
    manifest_sha256 = sha256_file(manifest_path)
    sentinel_path = sentinel_path_for(handoff_root)
    sentinel = load_json(sentinel_path)
    if sentinel.get("state") != "active":
        raise WorktreeError("only an active scoped worktree can be closed")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise WorktreeError("manifest schema mismatch")
    require_python_bytecode_environment(manifest)
    if sentinel.get("schema") != SENTINEL_SCHEMA:
        raise WorktreeError("sentinel schema mismatch")
    if manifest.get("job_id") != sentinel.get("job_id"):
        raise WorktreeError("manifest and sentinel job ids differ")

    allowed_values = manifest.get("allowed_write_paths")
    if not isinstance(allowed_values, list):
        raise WorktreeError("manifest write allowlist is missing")
    allowed_write_paths = normalize_path_list(
        [str(item) for item in allowed_values], label="manifest write allowlist"
    )
    if allowed_write_paths != allowed_values:
        raise WorktreeError("manifest write allowlist is not normalized and sorted")
    if len(allowed_write_paths) > MAX_ALLOWED_WRITE_PATHS:
        raise WorktreeError("manifest write allowlist exceeds its limit")

    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise WorktreeError("manifest frozen file list is invalid")
    frozen_paths = normalize_path_list(
        [str(row.get("relative_path") or "") for row in rows if isinstance(row, dict)],
        label="manifest frozen file list",
    )
    if len(frozen_paths) != len(rows):
        raise WorktreeError("manifest frozen file list contains invalid rows")

    verify_filesystem_scope(target, allowed_write_paths)

    all_changed_paths = _all_changed_paths(target)
    changed_controls = sorted(
        item
        for item in all_changed_paths
        if item.casefold() in RESERVED_CONTROL_FILES_FOLDED
        or any(part.casefold() == ".git" for part in PurePosixPath(item).parts)
    )
    if changed_controls:
        raise WorktreeError(
            "frozen control files changed: " + ", ".join(changed_controls)
        )
    changed_paths = normalize_path_list(all_changed_paths, label="builder changed path list")
    if not changed_paths:
        raise WorktreeError("builder output is a no-op")
    allowed_exact = set(allowed_write_paths)
    allowed_folded = {item.casefold() for item in allowed_write_paths}
    case_aliases = [
        item
        for item in changed_paths
        if item not in allowed_exact and item.casefold() in allowed_folded
    ]
    if case_aliases:
        raise WorktreeError(
            "builder changed a case alias instead of the exact manifest path: "
            + ", ".join(case_aliases)
        )
    unexpected = [item for item in changed_paths if item not in allowed_exact]
    if unexpected:
        raise WorktreeError(
            "builder changed paths outside the manifest allowlist: "
            + ", ".join(unexpected)
        )
    changed_files: list[dict[str, Any]] = []
    changed_total_bytes = 0
    for relative_path in changed_paths:
        file_path = target.joinpath(*PurePosixPath(relative_path).parts)
        if file_path.exists():
            row = inspect_changed_file(target, relative_path)
            changed_total_bytes += int(row["bytes"])
            changed_files.append(row)
        else:
            changed_files.append({"relative_path": relative_path, "exists": False})
    if changed_total_bytes > MAX_TOTAL_BYTES:
        raise WorktreeError(
            f"builder outputs exceed the {MAX_TOTAL_BYTES}-byte total limit"
        )

    # Intent-to-add makes declared new files part of the returned exact UTF-8
    # patch without committing or accepting them.  The container cannot mutate
    # .git; this host-side closeout step runs only after scope validation.
    frozen_exact = set(frozen_paths)
    new_paths = [
        row["relative_path"]
        for row in changed_files
        if row.get("exists") is True and row["relative_path"] not in frozen_exact
    ]
    if new_paths:
        run_git(target, "add", "--intent-to-add", "--force", "--", *new_paths)
    patch_paths = sorted(
        item
        for item in run_git(target, "diff", "--name-only", "-z", "HEAD", "--").split("\0")
        if item
    )
    if patch_paths != changed_paths:
        raise WorktreeError("returned patch path set does not match the validated changes")
    diff_text = run_git(target, "diff", "--binary", "--no-ext-diff", "HEAD", "--")
    if not diff_text.strip():
        raise WorktreeError("builder output produced an empty patch")
    patch_path = patch_path.expanduser().resolve(strict=False)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_bytes = diff_text.encode("utf-8")
    patch_path.write_bytes(patch_bytes)
    patch_sha256 = sha256_file(patch_path)
    if patch_sha256 != sha256_bytes(patch_bytes):
        raise WorktreeError("returned patch byte hash mismatch")

    baseline_commit = run_git(target, "rev-parse", "HEAD").strip().lower()
    inventory_before = capture_git_path_inventory(
        target,
        allow_identical_status_only_paths=(MANIFEST_FILENAME,),
    )
    if not git_inventory_matches_changed_paths(inventory_before, changed_paths):
        raise WorktreeError("Git inventory does not equal the declared changed paths")
    rechecked_changed_files: list[dict[str, Any]] = []
    for relative_path in changed_paths:
        file_path = target.joinpath(*PurePosixPath(relative_path).parts)
        if file_path.exists():
            rechecked_changed_files.append(inspect_changed_file(target, relative_path))
        else:
            rechecked_changed_files.append(
                {"relative_path": relative_path, "exists": False}
            )
    if rechecked_changed_files != changed_files:
        raise WorktreeError("builder outputs changed during close proof generation")
    if (
        run_git(target, "rev-parse", "HEAD").strip().lower() != baseline_commit
        or sha256_file(manifest_path) != manifest_sha256
        or sha256_file(patch_path) != patch_sha256
    ):
        raise WorktreeError("worktree evidence changed during close proof generation")
    inventory_after = capture_git_path_inventory(
        target,
        allow_identical_status_only_paths=(MANIFEST_FILENAME,),
    )
    inventory_checkpoints = {
        "before_binding_recheck": inventory_before,
        "after_binding_recheck": inventory_after,
    }
    inventory_sha256 = git_inventory_checkpoints_sha256(
        inventory_checkpoints, changed_paths
    )

    closed_at = utc_now()
    sentinel["state"] = "closed"
    sentinel["closed_at_utc"] = closed_at
    sentinel["changed_file_count"] = len(changed_files)
    sentinel["tracked_diff_sha256"] = patch_sha256
    sentinel["patch_sha256"] = patch_sha256
    write_json(sentinel_path, sentinel)

    return {
        "schema": PROOF_SCHEMA,
        "action": "close",
        "status": "ok",
        "generated_at_utc": closed_at,
        "job_id": manifest.get("job_id"),
        "target": str(target),
        "baseline_commit": baseline_commit,
        "manifest_sha256": manifest_sha256,
        "sentinel_path": str(sentinel_path),
        "sentinel_sha256": sha256_file(sentinel_path),
        "patch_path": str(patch_path),
        "tracked_diff_sha256": patch_sha256,
        "patch_sha256": patch_sha256,
        "patch_scope": "all manifest-allowlisted changed files, including declared new files",
        "allowed_write_paths": allowed_write_paths,
        "unexpected_changed_paths": [],
        "patch_includes_declared_new_files": True,
        "git_path_inventory_checkpoints": inventory_checkpoints,
        "git_path_inventory_sha256": inventory_sha256,
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "main_acceptance_status": "pending",
    }


def emit(payload: dict[str, Any], out: Path | None) -> None:
    if out is not None:
        write_json(out.expanduser().resolve(strict=False), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--handoff-root", type=Path, default=DEFAULT_HANDOFF_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="stage and commit a frozen handoff")
    prepare.add_argument("--job-id", required=True)
    prepare.add_argument("--source-root", type=Path, required=True)
    prepare.add_argument("--source-base-label", required=True)
    prepare.add_argument("--file", action="append", default=[], dest="files")
    prepare.add_argument(
        "--allow-output", action="append", default=[], dest="allowed_outputs"
    )
    prepare.add_argument("--out", type=Path)

    verify = subparsers.add_parser("verify", help="verify clean frozen state before dispatch")
    verify.add_argument("--out", type=Path)

    close = subparsers.add_parser("close", help="freeze the builder output without applying it")
    close.add_argument("--patch-out", type=Path, required=True)
    close.add_argument("--out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            payload = prepare_worktree(
                job_id=args.job_id,
                source_root=args.source_root,
                source_base_label=args.source_base_label,
                relative_paths=args.files,
                allowed_output_paths=args.allowed_outputs,
                target=args.target,
                handoff_root=args.handoff_root,
            )
        elif args.command == "verify":
            payload = verify_worktree(target=args.target, handoff_root=args.handoff_root)
        else:
            payload = close_worktree(
                patch_path=args.patch_out,
                target=args.target,
                handoff_root=args.handoff_root,
            )
        emit(payload, args.out)
        return 0
    except WorktreeError as exc:
        print(json.dumps({"schema": PROOF_SCHEMA, "status": "error", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
