#!/usr/bin/env python3
"""Bounded, changed-files-only Graphify incremental owner.

This route inventories the admissible code corpus but sends only an explicit,
bounded changed subset to the public graphify.extract.extract API. It never
falls back to full extraction. Publication consumes only a verified stage
receipt, writes guarded rollback preimages, and reports remaining backlog.
"""
from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import importlib.metadata
import json
import os
import shutil
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


OWNER_VERSION = "0.4.0-bounded-incremental"
OWNER_SCHEMA = "veritas.graphify_incremental_owner.v2"
SUPPORTED_GRAPHIFY = "0.9.45"
CODE_SUFFIXES = frozenset({
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js",
    ".jsx", ".kt", ".php", ".ps1", ".py", ".rb", ".rs", ".sh",
    ".swift", ".ts", ".tsx",
})
MAX_TARGETS = 25
MAX_FILE_BYTES = 512_000
MAX_TOTAL_BYTES = 4_000_000
# Fresh AST nodes carry shared builtin/stdlib/external symbol stubs whose
# ``source_file`` is empty. Those nodes are file-UNOWNED by construction, so
# ownership falls to the maintained base graph, which already carries them
# (and always preserves them, because blank ``source_file`` never equals a
# target path). They must satisfy node/edge structural validity, but they
# must never be required to belong to a selected changed file.
SHARED_STUB_SOURCE = "__shared_stub__"
EXCLUDED_DIR_NAMES = frozenset({
    "graphify-out", "__pycache__", ".git", ".hg", ".svn", "tmp", "temp",
    ".tmp", "cache", "caches", ".cache", "node_modules", "vendor", "venv",
    ".venv", ".tox", "build", "dist", ".pytest_cache", ".mypy_cache",
    "generated", ".generated", "archives", "archive",
})
_SENSITIVE_SUBSTRINGS = (
    "credential", "secret", "passwd", "password", "private_key", "id_rsa",
    "id_ed25519", "token", "apikey", "api_key",
)
_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".kdbx"})
_SENSITIVE_BASENAMES = frozenset({".env", ".env.local", ".netrc", "_netrc"})
_GENERATED_MARKERS = (
    ".generated.", "_generated.", ".g.", "_pb2.", ".pb2.", ".designer.",
    ".min.js", ".min.css", ".d.ts",
)
_IGNORE_NAMES = (".graphifyignore", ".gitignore")
ExtractFn = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        default=str,
    ).encode("utf-8")).hexdigest()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sensitive(name_lower: str) -> bool:
    return (
        name_lower in _SENSITIVE_BASENAMES
        or any(name_lower.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)
        or any(marker in name_lower for marker in _SENSITIVE_SUBSTRINGS)
    )


def _generated(name_lower: str) -> bool:
    return any(marker in name_lower for marker in _GENERATED_MARKERS)


def _normalize_rel(raw: str | Path) -> str:
    text = str(raw).replace("\\", "/")
    if not text or text.startswith("/") or (len(text) > 1 and text[1] == ":"):
        raise ValueError("relative_path_required")
    parts = PurePosixPath(text).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValueError("unsafe_relative_path")
    return "/".join(parts)


def is_excluded_rel(rel_posix: str, *, is_dir: bool = False) -> tuple[bool, str]:
    """Disk-free exclusion policy shared by staging and health."""
    try:
        rel = _normalize_rel(rel_posix)
    except ValueError:
        return True, "unsafe_relative_path"
    parts = rel.split("/")
    for index, part in enumerate(parts):
        lowered = part.casefold()
        component_is_dir = is_dir or index < len(parts) - 1
        if lowered.startswith(".") and lowered not in _IGNORE_NAMES:
            return True, "hidden_component"
        if component_is_dir and lowered in EXCLUDED_DIR_NAMES:
            return True, "excluded_dir"
        if component_is_dir and _sensitive(lowered):
            return True, "sensitive_directory"
        if component_is_dir and _generated(lowered):
            return True, "generated_directory"
    if is_dir:
        return False, ""
    name = parts[-1].casefold()
    if name.endswith(("~", ".bak", ".tmp", ".swp", ".orig", ".rej")):
        return True, "backup_or_tmp_file"
    if _sensitive(name):
        return True, "sensitive_filename"
    if _generated(name):
        return True, "generated_file"
    return False, ""


def _stat_is_reparse(st: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attrs = int(getattr(st, "st_file_attributes", 0) or 0)
    return stat.S_ISLNK(st.st_mode) or bool(attrs & flag)


def _is_reparse_or_link(path: Path) -> bool:
    try:
        return _stat_is_reparse(path.lstat())
    except OSError:
        return False


def _existing_components(path: Path) -> list[Path]:
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    if not parts:
        return []
    current = Path(parts[0])
    result = [current]
    for part in parts[1:]:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            break
        result.append(current)
    return result


def _reject_reparse_components(path: Path) -> str | None:
    for component in _existing_components(path):
        if _is_reparse_or_link(component):
            return f"reparse_component:{component}"
    return None


def _resolved(path: Path) -> Path:
    return Path(os.path.abspath(path)).resolve(strict=False)


def _overlap(a: Path, b: Path) -> bool:
    ar, br = _resolved(a), _resolved(b)
    return ar == br or ar in br.parents or br in ar.parents


def _validate_stage_paths(
    source_root: Path, graph_path: Path, manifest_path: Path, stage_dir: Path
) -> tuple[dict[str, Path] | None, str | None]:
    paths = {
        "source_root": Path(source_root),
        "graph_path": Path(graph_path),
        "manifest_path": Path(manifest_path),
        "stage_dir": Path(stage_dir),
    }
    for name, path in paths.items():
        reason = _reject_reparse_components(path)
        if reason:
            return None, f"{name}_{reason}"
    source = _resolved(paths["source_root"])
    graph = _resolved(paths["graph_path"])
    manifest = _resolved(paths["manifest_path"])
    stage = _resolved(paths["stage_dir"])
    if not source.is_dir():
        return None, "source_root_missing_or_not_directory"
    if not graph.is_file() or not manifest.is_file():
        return None, "graph_or_manifest_missing_or_not_file"
    if graph == manifest:
        return None, "graph_manifest_alias_refused"
    try:
        if os.path.samefile(graph, manifest):
            return None, "graph_manifest_alias_refused"
    except OSError:
        return None, "graph_manifest_identity_unverifiable"
    if graph.parent != manifest.parent:
        return None, "graph_manifest_output_mismatch"
    if stage.exists():
        return None, "stage_dir_must_not_exist"
    if _overlap(stage, source) or _overlap(stage, graph.parent):
        return None, "stage_path_overlap_refused"
    return {
        "source_root": source,
        "graph_path": graph,
        "manifest_path": manifest,
        "stage_dir": stage,
    }, None


def hash_file(path: Path, *, cap: int | None = None) -> dict[str, Any]:
    """Stream MD5 (manifest compatibility) and SHA-256.

    Inventory calls use an unlimited cap so unchanged corpus bytes never
    consume the changed-subset budget. Target caps are evaluated after hashes
    identify the selected changed subset.
    """
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                size += len(chunk)
                if cap is not None and size > cap:
                    return {"ok": False, "reason": "oversized", "size": size}
                md5.update(chunk)
                sha256.update(chunk)
    except OSError as exc:
        return {
            "ok": False,
            "reason": f"unreadable:{exc.__class__.__name__}",
            "size": size,
        }
    return {
        "ok": True,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
        "size": size,
    }


def _parse_ignore_bytes(
    payload: bytes,
    *,
    source_rel: str,
    base_rel: str,
    subject_prefix: str = "",
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return [], f"ignore_not_utf8:{source_rel}"
    rules: list[dict[str, Any]] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if "\\" in line:
            return [], f"unsupported_ignore_escape:{source_rel}:{line_no}"
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        anchored = line.startswith("/")
        if anchored:
            line = line[1:]
        directory_only = line.endswith("/")
        if directory_only:
            line = line[:-1]
        if not line or line.startswith("/") or "\x00" in line:
            return [], f"invalid_ignore_rule:{source_rel}:{line_no}"
        if any(part == ".." for part in PurePosixPath(line).parts):
            return [], f"unsafe_ignore_rule:{source_rel}:{line_no}"
        rules.append({
            "source": source_rel,
            "base": base_rel,
            "line": line_no,
            "pattern": line,
            "negated": negated,
            "anchored": anchored,
            "directory_only": directory_only,
            "subject_prefix": subject_prefix,
        })
    return rules, None


def _rule_matches(rule: dict[str, Any], rel: str, *, is_dir: bool) -> bool:
    prefix = str(rule.get("subject_prefix") or "").strip("/")
    if prefix:
        rel = f"{prefix}/{rel}" if rel else prefix
    base = str(rule["base"])
    if base:
        if rel == base:
            sub = ""
        elif rel.startswith(base + "/"):
            sub = rel[len(base) + 1:]
        else:
            return False
    else:
        sub = rel
    if not sub:
        return False
    pattern = str(rule["pattern"])
    parts = sub.split("/")
    if rule["anchored"] or "/" in pattern:
        matched = fnmatch.fnmatchcase(sub, pattern)
        if rule["directory_only"] and not matched:
            matched = any(
                fnmatch.fnmatchcase("/".join(parts[:index]), pattern)
                for index in range(1, len(parts) + (1 if is_dir else 0))
            )
        return matched
    candidate_parts = parts if is_dir else parts[:-1]
    if not rule["directory_only"]:
        candidate_parts = parts
    return any(fnmatch.fnmatchcase(part, pattern) for part in candidate_parts)


def is_ignored_rel(rel: str, rules: list[dict[str, Any]], *, is_dir: bool = False) -> bool:
    ignored = False
    for rule in rules:
        if _rule_matches(rule, rel, is_dir=is_dir):
            ignored = not bool(rule["negated"])
    return ignored


def _parent_repository_ignore_context(source_root: Path) -> dict[str, Any]:
    """Load ignore rules between a containing repository and ``source_root``.

    Rules remain relative to the directory that owns each ignore file.  The
    subject prefix lets the existing matcher evaluate a source-relative path
    as that owner directory sees it.  No ancestor is searched above the
    nearest repository marker.
    """
    rules: list[dict[str, Any]] = []
    ignore_files: list[dict[str, Any]] = []
    blockers: list[str] = []
    repository_root: Path | None = None
    for candidate in (source_root, *source_root.parents):
        marker = candidate / ".git"
        try:
            marker_stat = marker.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            blockers.append(
                f"repository_marker_lstat_failed:{candidate}:{exc.__class__.__name__}"
            )
            return {"rules": rules, "ignore_files": ignore_files, "blockers": blockers}
        if _stat_is_reparse(marker_stat):
            blockers.append(f"linked_repository_marker_refused:{marker}")
            return {"rules": rules, "ignore_files": ignore_files, "blockers": blockers}
        if not (stat.S_ISDIR(marker_stat.st_mode) or stat.S_ISREG(marker_stat.st_mode)):
            blockers.append(f"invalid_repository_marker_refused:{marker}")
            return {"rules": rules, "ignore_files": ignore_files, "blockers": blockers}
        repository_root = candidate
        break

    if repository_root is None or repository_root == source_root:
        return {"rules": rules, "ignore_files": ignore_files, "blockers": blockers}

    directories: list[Path] = []
    directory = source_root.parent
    while True:
        directories.append(directory)
        if directory == repository_root:
            break
        directory = directory.parent
    for directory in reversed(directories):
        subject_prefix = source_root.relative_to(directory).as_posix()
        owner_rel = directory.relative_to(repository_root).as_posix()
        owner_rel = "" if owner_rel == "." else owner_rel
        for ignore_name in _IGNORE_NAMES:
            ignore_path = directory / ignore_name
            try:
                ignore_stat = ignore_path.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                blockers.append(
                    f"parent_ignore_lstat_failed:{ignore_path}:{exc.__class__.__name__}"
                )
                continue
            source_rel = f"@repository/{owner_rel}/{ignore_name}".replace("//", "/")
            if _stat_is_reparse(ignore_stat) or not stat.S_ISREG(ignore_stat.st_mode):
                blockers.append(f"linked_or_nonregular_ignore_refused:{source_rel}")
                continue
            try:
                payload = ignore_path.read_bytes()
            except OSError as exc:
                blockers.append(
                    f"ignore_unreadable:{source_rel}:{exc.__class__.__name__}"
                )
                continue
            parsed, error = _parse_ignore_bytes(
                payload,
                source_rel=source_rel,
                base_rel="",
                subject_prefix=subject_prefix,
            )
            if error:
                blockers.append(error)
                continue
            rules.extend(parsed)
            ignore_files.append({
                "path": source_rel,
                "sha256": _sha256_bytes(payload),
                "size": len(payload),
            })
    return {"rules": rules, "ignore_files": ignore_files, "blockers": blockers}


def _inventory(source_root: Path) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    blockers: list[str] = []
    ignore_files: list[dict[str, Any]] = []
    all_rules: list[dict[str, Any]] = []
    case_paths: dict[str, str] = {}

    root_reason = _reject_reparse_components(source_root)
    if root_reason:
        blockers.append(f"source_root_{root_reason}")
    elif not source_root.is_dir():
        blockers.append("source_root_missing_or_not_directory")
    else:
        parent_context = _parent_repository_ignore_context(source_root)
        all_rules.extend(parent_context["rules"])
        ignore_files.extend(parent_context["ignore_files"])
        blockers.extend(parent_context["blockers"])

    def walk(directory: Path, rel_dir: str, inherited: list[dict[str, Any]]) -> None:
        if blockers:
            return
        reason = _reject_reparse_components(directory)
        if reason:
            blockers.append(f"directory_{reason}")
            return
        rules = list(inherited)
        for ignore_name in _IGNORE_NAMES:
            ignore_path = directory / ignore_name
            try:
                ignore_stat = ignore_path.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                blockers.append(
                    f"ignore_lstat_failed:{rel_dir}/{ignore_name}:{exc.__class__.__name__}"
                )
                continue
            ignore_rel = f"{rel_dir}/{ignore_name}".strip("/")
            if _stat_is_reparse(ignore_stat) or not stat.S_ISREG(ignore_stat.st_mode):
                blockers.append(f"linked_or_nonregular_ignore_refused:{ignore_rel}")
                continue
            try:
                payload = ignore_path.read_bytes()
            except OSError as exc:
                blockers.append(f"ignore_unreadable:{ignore_rel}:{exc.__class__.__name__}")
                continue
            parsed, error = _parse_ignore_bytes(
                payload, source_rel=ignore_rel, base_rel=rel_dir
            )
            if error:
                blockers.append(error)
                continue
            rules.extend(parsed)
            all_rules.extend(parsed)
            ignore_files.append({
                "path": ignore_rel,
                "sha256": _sha256_bytes(payload),
                "size": len(payload),
            })
        if blockers:
            return
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
        except OSError as exc:
            blockers.append(
                f"directory_unreadable:{rel_dir or '.'}:{exc.__class__.__name__}"
            )
            return
        for entry in entries:
            path = directory / entry.name
            rel = f"{rel_dir}/{entry.name}".strip("/").replace("\\", "/")
            try:
                entry_stat = path.lstat()
            except OSError as exc:
                blockers.append(f"lstat_failed:{rel}:{exc.__class__.__name__}")
                continue
            if _stat_is_reparse(entry_stat):
                skipped.append({"path": rel, "reason": "reparse_or_symlink_not_followed"})
                continue
            is_dir = stat.S_ISDIR(entry_stat.st_mode)
            excluded, exclusion_reason = is_excluded_rel(rel, is_dir=is_dir)
            if excluded:
                skipped.append({"path": rel, "reason": exclusion_reason})
                continue
            if is_ignored_rel(rel, rules, is_dir=is_dir):
                skipped.append({"path": rel, "reason": "ignored_by_rule"})
                continue
            if is_dir:
                walk(path, rel, rules)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                skipped.append({"path": rel, "reason": "nonregular_file"})
                continue
            if path.suffix.casefold() not in CODE_SUFFIXES:
                skipped.append({"path": rel, "reason": "unsupported_file_type"})
                continue
            folded = rel.casefold()
            if folded in case_paths and case_paths[folded] != rel:
                blockers.append(f"case_ambiguous_disk_paths:{case_paths[folded]}:{rel}")
                continue
            case_paths[folded] = rel
            hashed = hash_file(path, cap=None)
            if not hashed["ok"]:
                blockers.append(f"source_{hashed['reason']}:{rel}")
                continue
            files[rel] = {
                "path": rel,
                "mtime": entry_stat.st_mtime,
                "md5": hashed["md5"],
                "sha256": hashed["sha256"],
                "size": hashed["size"],
            }

    if not blockers:
        if is_ignored_rel("", all_rules, is_dir=True):
            skipped.append({"path": ".", "reason": "ignored_by_parent_rule"})
        else:
            walk(source_root, "", all_rules)
    snapshot = {
        "files": [files[key] for key in sorted(files)],
        "ignore_files": sorted(ignore_files, key=lambda item: item["path"]),
        "ignore_rules": all_rules,
        "blockers": sorted(set(blockers)),
    }
    return {
        **snapshot,
        "files_by_path": files,
        "skipped": skipped,
        "inventory_snapshot_sha256": canonical_hash(snapshot),
    }


def _normalize_manifest(
    manifest_rows: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    normalized: dict[str, dict[str, Any]] = {}
    folded: dict[str, str] = {}
    errors: list[str] = []
    for raw_key, row in manifest_rows.items():
        try:
            key = _normalize_rel(str(raw_key))
        except ValueError:
            errors.append(f"unsafe_manifest_key:{raw_key}")
            continue
        if not isinstance(row, dict):
            errors.append(f"manifest_row_not_object:{key}")
            continue
        if key in normalized:
            errors.append(f"duplicate_manifest_key:{key}")
            continue
        case_key = key.casefold()
        if case_key in folded and folded[case_key] != key:
            errors.append(f"case_ambiguous_manifest_paths:{folded[case_key]}:{key}")
            continue
        folded[case_key] = key
        normalized[key] = row
    return normalized, errors


def select_targets(
    source_root: Path,
    manifest_rows: dict[str, Any],
    *,
    changed_paths: list[str] | None = None,
    max_targets: int = MAX_TARGETS,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Inventory everything admissible; cap and extract only selected drift."""
    # Keep the lexical path until reparse checks complete.  Resolving here
    # would erase a source-root symlink/junction before health inventory sees it.
    source_root = Path(os.path.abspath(source_root))
    inventory = _inventory(source_root)
    manifest, manifest_errors = _normalize_manifest(manifest_rows)
    current = inventory["files_by_path"]
    changed_all: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for rel in sorted(current):
        entry = dict(current[rel])
        row = manifest.get(rel)
        if row is None:
            entry["kind"] = "new"
            changed_all.append(entry)
        elif row.get("ast_hash") != entry["md5"]:
            entry["kind"] = "changed"
            changed_all.append(entry)
        else:
            unchanged.append(rel)

    excluded_manifest_rows: list[str] = []
    deleted_refused: list[str] = []
    rules = inventory["ignore_rules"]
    for rel in sorted(manifest):
        if rel in current:
            continue
        excluded, _ = is_excluded_rel(rel)
        if (
            excluded
            or Path(rel).suffix.casefold() not in CODE_SUFFIXES
            or is_ignored_rel(rel, rules)
        ):
            excluded_manifest_rows.append(rel)
        else:
            deleted_refused.append(rel)

    allowlist_errors: list[str] = []
    allowlist: list[str] | None = None
    if changed_paths is not None:
        allowlist = []
        seen_case: dict[str, str] = {}
        current_case = {path.casefold(): path for path in current}
        for raw in changed_paths:
            try:
                rel = _normalize_rel(raw)
            except ValueError:
                allowlist_errors.append(f"unsafe_changed_path:{raw}")
                continue
            folded = rel.casefold()
            if folded in seen_case:
                allowlist_errors.append(f"duplicate_changed_path:{rel}")
                continue
            seen_case[folded] = rel
            actual = current_case.get(folded)
            if actual is None:
                allowlist_errors.append(f"changed_path_missing_or_inadmissible:{rel}")
                continue
            if actual != rel:
                allowlist_errors.append(f"changed_path_case_mismatch:{rel}:{actual}")
                continue
            allowlist.append(rel)

    changed_by_path = {entry["path"]: entry for entry in changed_all}
    requested_paths = (
        sorted(changed_by_path)
        if allowlist is None
        else sorted(path for path in allowlist if path in changed_by_path)
    )
    targets: list[dict[str, Any]] = []
    deferred: list[str] = []
    oversized: list[str] = []
    target_bytes = 0
    for path in requested_paths:
        entry = changed_by_path[path]
        size = int(entry["size"])
        if size > max_file_bytes:
            oversized.append(path)
            deferred.append(path)
            continue
        if len(targets) >= max_targets or target_bytes + size > max_total_bytes:
            deferred.append(path)
            continue
        targets.append(entry)
        target_bytes += size
    deferred.extend(
        path for path in sorted(changed_by_path) if path not in requested_paths
    )
    deferred = sorted(set(deferred))
    policy_reasons = (
        list(inventory["blockers"]) + manifest_errors + allowlist_errors
    )
    if oversized and allowlist is not None:
        policy_reasons.append(
            f"target_file_bytes_exceed_cap:{','.join(sorted(oversized))}:{max_file_bytes}"
        )
    policy_block = ";".join(sorted(set(policy_reasons))) if policy_reasons else None
    return {
        "targets": targets,
        "all_changed": changed_all,
        "deferred_changed": deferred,
        "unserviceable_changed": sorted(oversized),
        "unchanged": unchanged,
        "skipped": inventory["skipped"],
        "deleted_refused": deleted_refused,
        "excluded_manifest_rows": excluded_manifest_rows,
        "total_target_bytes": target_bytes,
        "policy_block": policy_block,
        "inventory_snapshot_sha256": inventory["inventory_snapshot_sha256"],
        "ignore_files": inventory["ignore_files"],
        "current_code_files": len(current),
        "tracked_code_files": sum(
            1
            for rel in manifest
            if not is_excluded_rel(rel)[0]
            and Path(rel).suffix.casefold() in CODE_SUFFIXES
            and not is_ignored_rel(rel, rules)
        ),
        "subset_allowlist": allowlist,
    }


def freshness_report(source_root: Path, manifest_rows: dict[str, Any]) -> dict[str, Any]:
    """Health report using the exact inventory/hash/exclusion policy."""
    selection = select_targets(source_root, manifest_rows)
    modified = sorted(
        item["path"] for item in selection["all_changed"]
        if item["kind"] == "changed"
    )
    new = sorted(
        item["path"] for item in selection["all_changed"] if item["kind"] == "new"
    )
    deleted = selection["deleted_refused"]
    blocked = selection["policy_block"] is not None
    stale = bool(modified or new or deleted)
    status = "blocked" if blocked else "stale" if stale else "fresh"
    return {
        "status": status,
        "coverage_status": "unknown" if blocked else status,
        "changed_count": len(modified),
        "new_count": len(new),
        "deleted_count": len(deleted),
        "changed_sample": modified[:10],
        "new_sample": new[:10],
        "deleted_sample": deleted[:10],
        "policy_block": selection["policy_block"],
        "tracked_code_files": selection["tracked_code_files"],
        "current_code_files": selection["current_code_files"],
        "inventory_snapshot_sha256": selection["inventory_snapshot_sha256"],
    }


def _source_file(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    try:
        return _normalize_rel(str(item.get("source_file", "")))
    except ValueError:
        return ""


def _is_ast(item: dict[str, Any]) -> bool:
    origin = str(item.get("_origin", "")).casefold()
    if origin == "semantic":
        return False
    if origin == "ast":
        return True
    return origin == "" and item.get("file_type") == "code"


def _hyperedge_lists(graph: dict[str, Any]) -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    if "hyperedges" in graph:
        values.append(("top", graph.get("hyperedges")))
    metadata = graph.get("graph")
    if isinstance(metadata, dict) and "hyperedges" in metadata:
        values.append(("nested", metadata.get("hyperedges")))
    return values


def validate_graph(graph: dict[str, Any], *, label: str) -> dict[str, Any]:
    nodes = graph.get("nodes")
    has_links, has_edges = "links" in graph, "edges" in graph
    if has_links and has_edges:
        return {"ok": False, "error": f"{label}_ambiguous_edge_slots"}
    edges = graph.get("links" if has_links else "edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {"ok": False, "error": f"{label}_malformed_lists"}
    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            return {"ok": False, "error": f"{label}_node_missing_string_id"}
        if node["id"] in ids:
            return {"ok": False, "error": f"{label}_duplicate_node_id", "id": node["id"]}
        ids.add(node["id"])
    edge_fingerprints: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            return {"ok": False, "error": f"{label}_edge_not_object"}
        if edge.get("source") not in ids or edge.get("target") not in ids:
            return {
                "ok": False,
                "error": f"{label}_dangling_edge",
                "edge": {key: edge.get(key) for key in ("source", "target")},
            }
        fingerprint = canonical_hash(edge)
        if fingerprint in edge_fingerprints:
            return {"ok": False, "error": f"{label}_duplicate_edge"}
        edge_fingerprints.add(fingerprint)
    hyperedge_count = 0
    for slot, hyperedges in _hyperedge_lists(graph):
        if not isinstance(hyperedges, list):
            return {"ok": False, "error": f"{label}_{slot}_hyperedges_not_list"}
        seen_hyperedges: set[str] = set()
        for hyperedge in hyperedges:
            if not isinstance(hyperedge, dict):
                return {"ok": False, "error": f"{label}_{slot}_hyperedge_not_object"}
            members = hyperedge.get("nodes")
            if not isinstance(members, list) or not all(
                isinstance(member, str) and member for member in members
            ):
                return {"ok": False, "error": f"{label}_{slot}_hyperedge_members_malformed"}
            if len(members) != len(set(members)):
                return {"ok": False, "error": f"{label}_{slot}_hyperedge_duplicate_member"}
            missing = sorted(set(members) - ids)
            if missing:
                return {
                    "ok": False,
                    "error": f"{label}_{slot}_hyperedge_dangling",
                    "ids": missing[:20],
                }
            fingerprint = canonical_hash(hyperedge)
            if fingerprint in seen_hyperedges:
                return {"ok": False, "error": f"{label}_{slot}_duplicate_hyperedge"}
            seen_hyperedges.add(fingerprint)
        hyperedge_count += len(hyperedges)
    return {
        "ok": True,
        "nodes": len(nodes),
        "edges": len(edges),
        "hyperedges": hyperedge_count,
        "edge_slot": "links" if has_links else "edges",
    }


def unchanged_resolution_context(
    graph: dict[str, Any], changed_paths: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return unchanged AST-only context; changed and semantic rows stay out."""
    edges = graph.get("links", graph.get("edges", []))
    nodes = [
        copy.deepcopy(node)
        for node in graph.get("nodes", [])
        if isinstance(node, dict)
        and _is_ast(node)
        and _source_file(node) not in changed_paths
    ]
    ids = {node["id"] for node in nodes}
    context_edges = [
        copy.deepcopy(edge)
        for edge in edges
        if isinstance(edge, dict)
        and _is_ast(edge)
        and _source_file(edge) not in changed_paths
        and edge.get("source") in ids
        and edge.get("target") in ids
    ]
    return nodes, context_edges


def default_extract(
    paths: list[Path],
    *,
    root: Path,
    cache_root: Path,
    resolution_context_nodes: list[dict[str, Any]] | None,
    resolution_context_edges: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Call only the installed public API with explicit changed paths."""
    from graphify.extract import extract

    if not paths:
        raise ValueError("explicit_changed_paths_required")
    return extract(
        [Path(path) for path in paths],
        root=root,
        cache_root=cache_root,
        parallel=False,
        resolution_context_nodes=resolution_context_nodes,
        resolution_context_edges=resolution_context_edges,
    )


def _fresh_source_key(value: Any, source_root: Path) -> str:
    """Resolve an extracted ``source_file`` to a source-root-relative key.

    A blank ``source_file`` denotes a SHARED resolution stub (builtin / stdlib
    / external symbol), so it maps to ``SHARED_STUB_SOURCE`` instead of being
    treated as a foreign path. Every genuine ``source_file`` value still
    receives the strict absolute/relative path checks unchanged.
    """
    text = str(value or "").replace("\\", "/")
    if not text:
        return SHARED_STUB_SOURCE
    candidate = Path(text)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
        try:
            return resolved.relative_to(source_root).as_posix()
        except ValueError as exc:
            raise ValueError("foreign_absolute_source") from exc
    return _normalize_rel(text)


def merge_candidate(
    base_graph: dict[str, Any],
    fresh: dict[str, Any],
    target_paths: set[str],
    *,
    source_root: Path,
) -> dict[str, Any]:
    """Replace selected AST ownership only and validate the full candidate."""
    base_validation = validate_graph(base_graph, label="base")
    if not base_validation["ok"]:
        return base_validation
    fresh_nodes = fresh.get("nodes")
    fresh_edges = fresh.get("edges", fresh.get("links"))
    if not isinstance(fresh_nodes, list) or not isinstance(fresh_edges, list):
        return {"ok": False, "error": "fresh_extraction_malformed"}
    failed: list[str] = []
    for raw in fresh.get("failed_sources") or []:
        try:
            failed.append(_fresh_source_key(raw, source_root))
        except ValueError:
            failed.append(f"foreign:{raw}")
    if failed:
        return {
            "ok": False,
            "error": "fresh_extraction_failures",
            "failed_sources": sorted(failed),
        }

    base_nodes = base_graph["nodes"]
    edge_slot = base_validation["edge_slot"]
    base_edges = base_graph[edge_slot]
    base_index = {
        node["id"]: node
        for node in base_nodes
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    preserved_nodes = [
        copy.deepcopy(node)
        for node in base_nodes
        if not (_is_ast(node) and _source_file(node) in target_paths)
    ]
    preserved_ids = {node["id"] for node in preserved_nodes}

    normalized_nodes: list[dict[str, Any]] = []
    emitted: dict[str, int] = {path: 0 for path in target_paths}
    fresh_ids: set[str] = set()
    seen_node_hashes: dict[str, str] = {}
    duplicate_nodes_dropped = 0
    shared_stub_base_wins = 0
    shared_stub_new = 0
    for node in fresh_nodes:
        if not isinstance(node, dict):
            return {"ok": False, "error": "fresh_node_not_object"}
        if node.get("_origin") != "ast":
            return {
                "ok": False,
                "error": "fresh_non_ast_node_refused",
                "id": str(node.get("id") or "")[:120],
            }
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            return {"ok": False, "error": "fresh_node_missing_string_id"}
        node_hash = canonical_hash(node)
        prior_hash = seen_node_hashes.get(node_id)
        if prior_hash is not None:
            if prior_hash == node_hash:
                # Exact duplicate from extract(); upstream cli.py collapses
                # these via dedupe_nodes, so collapse here with the same
                # first-wins semantics instead of refusing the whole batch.
                duplicate_nodes_dropped += 1
                continue
            return {"ok": False, "error": "fresh_duplicate_node_id", "id": node_id}
        seen_node_hashes[node_id] = node_hash
        try:
            source = _fresh_source_key(node.get("source_file"), source_root)
        except ValueError:
            return {
                "ok": False,
                "error": "fresh_node_foreign_source",
                "id": node_id[:120],
                "source_file": str(node.get("source_file") or "")[:200],
            }
        if source == SHARED_STUB_SOURCE:
            # Blank source_file marks a shared resolution stub (builtin /
            # stdlib / external symbol). The maintained base graph already
            # carries thousands of these, and a blank source_file can never
            # equal a target path, so base stubs are always preserved: when
            # the base already owns this id the preserved copy wins and the
            # fresh duplicate is dropped; a genuinely new id is kept as a
            # shared stub. Stubs claim no file ownership and never count
            # toward the per-target emission requirement.
            if node_id in fresh_ids:
                continue
            if node_id in base_index:
                shared_stub_base_wins += 1
                continue
            fresh_ids.add(node_id)
            shared_stub_new += 1
            normalized_nodes.append(copy.deepcopy(node))
            continue
        if source not in target_paths:
            return {
                "ok": False,
                "error": "fresh_node_outside_selected_sources",
                "id": node_id[:120],
                "source_file": source[:200],
            }
        if node_id in fresh_ids:
            return {"ok": False, "error": "fresh_duplicate_node_id", "id": node_id}
        fresh_ids.add(node_id)
        emitted[source] += 1
        normalized_nodes.append(copy.deepcopy(node))
    omitted = sorted(path for path, count in emitted.items() if count == 0)
    if omitted:
        return {
            "ok": False,
            "error": "fresh_selected_source_omitted_or_empty",
            "paths": omitted,
        }
    collisions = sorted(preserved_ids & fresh_ids)
    if collisions:
        return {
            "ok": False,
            "error": "ambiguous_ownership_refused",
            "ids": collisions[:20],
        }
    preserved_edges = [
        copy.deepcopy(edge)
        for edge in base_edges
        if not (_is_ast(edge) and _source_file(edge) in target_paths)
    ]
    known = preserved_ids | fresh_ids
    normalized_edges: list[dict[str, Any]] = []
    seen_edge_keys: set[tuple[Any, Any, Any]] = set()
    duplicate_edges_dropped = 0
    dropped_unresolvable_edges = 0
    unresolvable_symbols: set[str] = set()
    for edge in fresh_edges:
        if not isinstance(edge, dict):
            return {"ok": False, "error": "fresh_edge_not_object"}
        if edge.get("_origin") != "ast":
            return {
                "ok": False,
                "error": "fresh_non_ast_edge_refused",
                "source": str(edge.get("source") or "")[:120],
            }
        edge_key = (edge.get("source"), edge.get("target"), edge.get("relation"))
        if edge_key in seen_edge_keys:
            # Parallel duplicate from extract(); upstream collapses by
            # (source, target, relation) in graphify.build.dedupe_edges, which
            # the cli and watch write paths apply before building a graph.
            # Match that contract here instead of failing candidate_duplicate.
            duplicate_edges_dropped += 1
            continue
        seen_edge_keys.add(edge_key)
        try:
            source_file = _fresh_source_key(edge.get("source_file"), source_root)
        except ValueError:
            return {
                "ok": False,
                "error": "fresh_edge_foreign_source",
                "source": str(edge.get("source") or "")[:120],
                "source_file": str(edge.get("source_file") or "")[:200],
            }
        if source_file != SHARED_STUB_SOURCE and source_file not in target_paths:
            return {
                "ok": False,
                "error": "fresh_edge_outside_selected_sources",
                "source": str(edge.get("source") or "")[:120],
                "source_file": source_file[:200],
            }
        if not str(edge.get("source_file") or ""):
            # Edge claims no owning file at all. Keeping it would assert a
            # relation the base graph never records; upstream assembly drops
            # it, so drop it here too, counted and bounded.
            dropped_unresolvable_edges += 1
            continue
        missing_endpoints = [
            endpoint
            for endpoint in (edge.get("source"), edge.get("target"))
            if endpoint not in known
        ]
        if missing_endpoints:
            file_owned_missing = [
                endpoint
                for endpoint in missing_endpoints
                if endpoint in base_index
                and str(base_index[endpoint].get("source_file") or "")
            ]
            if file_owned_missing:
                # The endpoint exists in the base graph but belongs to a file
                # whose ownership this batch replaces, and the fresh batch
                # did not re-emit it: a genuine stale reference. Refuse,
                # fail closed, exactly as before.
                return {
                    "ok": False,
                    "error": "fresh_edge_dangling_refused",
                    "edge": {
                        key: edge.get(key) for key in ("source", "target")
                    },
                    "missing": missing_endpoints[:10],
                    "file_owned_missing": file_owned_missing[:10],
                }
            # The endpoint resolves to no node in the fresh batch or anywhere
            # in the maintained base graph: an external/unresolvable symbol
            # (bare stdlib module ids such as json or argparse). The full
            # build drops these at assembly — the base graph contains zero
            # edges targeting them — so drop them here, count them, and never
            # invent stub nodes for them.
            dropped_unresolvable_edges += 1
            unresolvable_symbols.update(
                str(endpoint) for endpoint in missing_endpoints
            )
            continue
        normalized_edges.append(copy.deepcopy(edge))

    candidate = copy.deepcopy(base_graph)
    candidate["nodes"] = preserved_nodes + normalized_nodes
    candidate[edge_slot] = preserved_edges + normalized_edges
    validation = validate_graph(candidate, label="candidate")
    if not validation["ok"]:
        return validation
    if validation["nodes"] < base_validation["nodes"]:
        return {
            "ok": False,
            "error": "candidate_node_shrink_refused",
            "base": base_validation["nodes"],
            "candidate": validation["nodes"],
        }
    if validation["edges"] < base_validation["edges"]:
        return {
            "ok": False,
            "error": "candidate_edge_shrink_refused",
            "base": base_validation["edges"],
            "candidate": validation["edges"],
        }
    return {
        "ok": True,
        "candidate": candidate,
        "base": base_validation,
        "candidate_counts": validation,
        "preserved_nodes": len(preserved_nodes),
        "preserved_edges": len(preserved_edges),
        "fresh_nodes": len(normalized_nodes),
        "fresh_edges": len(normalized_edges),
        "duplicate_nodes_dropped": duplicate_nodes_dropped,
        "duplicate_edges_dropped": duplicate_edges_dropped,
        "shared_stub_base_wins": shared_stub_base_wins,
        "shared_stub_new": shared_stub_new,
        "dropped_unresolvable_edges": dropped_unresolvable_edges,
        "unresolvable_symbols": sorted(unresolvable_symbols)[:20],
    }


def stamp_manifest_subset(
    manifest_rows: dict[str, Any],
    selection: dict[str, Any],
    fresh_ok_paths: set[str],
) -> tuple[dict[str, Any], list[str]]:
    staged = copy.deepcopy(manifest_rows)
    targets = {item["path"]: item for item in selection["targets"]}
    stamped: list[str] = []
    for path in sorted(fresh_ok_paths):
        target = targets.get(path)
        if target is None:
            continue
        prior = staged.get(path)
        row = copy.deepcopy(prior) if isinstance(prior, dict) else {}
        row["mtime"] = target["mtime"]
        row["ast_hash"] = target["md5"]
        row["semantic_hash"] = ""
        staged[path] = row
        stamped.append(path)
    return staged, stamped


def _read_json_with_bytes(path: Path) -> tuple[Any | None, bytes | None, str | None]:
    try:
        payload = path.read_bytes()
        return json.loads(payload.decode("utf-8")), payload, None
    except FileNotFoundError:
        return None, None, "missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, None, f"unreadable:{exc.__class__.__name__}"


def _backend_identity(
    extract_fn: ExtractFn | None, backend_name: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    if extract_fn is not None:
        if not isinstance(backend_name, str) or "fake" not in backend_name.casefold():
            return None, "fake_backend_must_be_plainly_labeled"
        return {
            "kind": "fake_injected",
            "label": backend_name,
            "package": None,
            "actual_version": None,
        }, None
    try:
        actual = importlib.metadata.version("graphifyy")
    except importlib.metadata.PackageNotFoundError:
        return None, "graphifyy_metadata_missing"
    if actual != SUPPORTED_GRAPHIFY:
        return None, f"graphifyy_version_mismatch:{actual}:{SUPPORTED_GRAPHIFY}"
    return {
        "kind": "actual_public_graphify_extract",
        "label": f"graphifyy-{actual}",
        "package": "graphifyy",
        "actual_version": actual,
    }, None


def _selection_recheck_matches(
    before: dict[str, Any], after: dict[str, Any]
) -> bool:
    keys = (
        "inventory_snapshot_sha256", "deleted_refused", "policy_block",
        "deferred_changed", "subset_allowlist",
    )
    if any(before.get(key) != after.get(key) for key in keys):
        return False
    before_targets = {
        item["path"]: (item["sha256"], item["md5"], item["mtime"], item["size"])
        for item in before["targets"]
    }
    after_targets = {
        item["path"]: (item["sha256"], item["md5"], item["mtime"], item["size"])
        for item in after["targets"]
    }
    return before_targets == after_targets


def _recheck_inputs(
    *,
    source_root: Path,
    graph_path: Path,
    manifest_path: Path,
    graph_sha256: str,
    manifest_sha256: str,
    manifest: dict[str, Any],
    selection: dict[str, Any],
    changed_paths: list[str] | None,
    max_targets: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        if _sha256_bytes(graph_path.read_bytes()) != graph_sha256:
            return False, "maintained_graph_drift_during_stage", None
        if _sha256_bytes(manifest_path.read_bytes()) != manifest_sha256:
            return False, "maintained_manifest_drift_during_stage", None
    except OSError as exc:
        return False, f"maintained_output_recheck_failed:{exc.__class__.__name__}", None
    after = select_targets(
        source_root,
        manifest,
        changed_paths=changed_paths,
        max_targets=max_targets,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if not _selection_recheck_matches(selection, after):
        return False, "source_or_ignore_inventory_drift_during_stage", after
    return True, "", after


def _write_exclusive(path: Path, payload: bytes) -> None:
    with open(path, "xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_replace(path: Path, payload: bytes) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        _write_exclusive(temp, payload)
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _validate_publish_paths(
    source_root: Path, graph_path: Path, manifest_path: Path, stage_dir: Path
) -> tuple[dict[str, Path] | None, str | None]:
    paths = {
        "source_root": Path(source_root),
        "graph_path": Path(graph_path),
        "manifest_path": Path(manifest_path),
        "stage_dir": Path(stage_dir),
    }
    for name, path in paths.items():
        reason = _reject_reparse_components(path)
        if reason:
            return None, f"{name}_{reason}"
    source = _resolved(paths["source_root"])
    graph = _resolved(paths["graph_path"])
    manifest = _resolved(paths["manifest_path"])
    stage = _resolved(paths["stage_dir"])
    if not source.is_dir():
        return None, "source_root_missing_or_not_directory"
    if not graph.is_file() or not manifest.is_file():
        return None, "graph_or_manifest_missing_or_not_file"
    if graph == manifest or graph.parent != manifest.parent:
        return None, "graph_manifest_output_mismatch"
    try:
        if os.path.samefile(graph, manifest):
            return None, "graph_manifest_alias_refused"
    except OSError:
        return None, "graph_manifest_identity_unverifiable"
    if not stage.is_dir() or _overlap(stage, source) or _overlap(stage, graph.parent):
        return None, "stage_path_invalid"
    return {
        "source_root": source,
        "graph_path": graph,
        "manifest_path": manifest,
        "stage_dir": stage,
    }, None


def _stage_blocked(
    proof: dict[str, Any], reason: str, stage_dir: Path, **extra: Any
) -> dict[str, Any]:
    """Record a refusal and discard the partial stage directory it created.

    run_stage creates the stage directory and its extract cache before the
    merge refusals that can follow. Without this helper a refused run leaks
    ~3 MB of extraction cache per attempt (seven such orphans accumulated
    before 0.4.0). Only run_stage post-mkdir refusals may call this; callers
    before the mkdir never created anything to discard.
    """
    shutil.rmtree(stage_dir, ignore_errors=True)
    return {**proof, "outcome": "blocked", "reason": reason, **extra}


def run_stage(
    *,
    source_root: Path,
    graph_path: Path,
    manifest_path: Path,
    stage_dir: Path,
    changed_paths: list[str] | None = None,
    extract_fn: ExtractFn | None = None,
    backend_name: str | None = None,
    max_targets: int = MAX_TARGETS,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Create immutable stage artifacts and a receipt; never publish."""
    proof: dict[str, Any] = {
        "schema": OWNER_SCHEMA,
        "owner_version": OWNER_VERSION,
        "generated_at_utc": utc_now(),
        "mode": "stage",
        "publication": "publication_not_supported",
        "reports_html_status": "stale_not_regenerated",
        "full_graph_freshness_claimed": False,
        "current_head_claimed": False,
    }
    paths, path_error = _validate_stage_paths(
        source_root, graph_path, manifest_path, stage_dir
    )
    if path_error:
        return {**proof, "outcome": "blocked", "reason": path_error}
    assert paths is not None
    source_root = paths["source_root"]
    graph_path = paths["graph_path"]
    manifest_path = paths["manifest_path"]
    stage_dir = paths["stage_dir"]

    graph, graph_bytes, graph_error = _read_json_with_bytes(graph_path)
    manifest, manifest_bytes, manifest_error = _read_json_with_bytes(manifest_path)
    if graph_error or not isinstance(graph, dict):
        return {
            **proof,
            "outcome": "blocked",
            "reason": f"base_graph_{graph_error or 'malformed'}",
        }
    if manifest_error or not isinstance(manifest, dict):
        return {
            **proof,
            "outcome": "blocked",
            "reason": f"base_manifest_{manifest_error or 'malformed'}",
        }
    assert graph_bytes is not None and manifest_bytes is not None
    base_validation = validate_graph(graph, label="base")
    if not base_validation["ok"]:
        return {
            **proof,
            "outcome": "blocked",
            "reason": base_validation["error"],
            "detail": base_validation,
        }
    selection = select_targets(
        source_root,
        manifest,
        changed_paths=changed_paths,
        max_targets=max_targets,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    proof["selection"] = {
        "targets": [item["path"] for item in selection["targets"]],
        "all_changed_count": len(selection["all_changed"]),
        "deferred_changed": selection["deferred_changed"],
        "unserviceable_changed": selection["unserviceable_changed"],
        "target_bytes": selection["total_target_bytes"],
        "unchanged_count": len(selection["unchanged"]),
        "deleted_refused": selection["deleted_refused"],
        "policy_block": selection["policy_block"],
        "subset_allowlist": selection["subset_allowlist"],
        "inventory_snapshot_sha256": selection["inventory_snapshot_sha256"],
    }
    if selection["policy_block"]:
        return {
            **proof,
            "outcome": "blocked",
            "reason": selection["policy_block"],
        }
    if selection["deleted_refused"]:
        return {
            **proof,
            "outcome": "blocked",
            "reason": "deleted_sources_need_review",
            "deleted": selection["deleted_refused"],
        }
    if not selection["targets"]:
        ok, reason, _ = _recheck_inputs(
            source_root=source_root,
            graph_path=graph_path,
            manifest_path=manifest_path,
            graph_sha256=_sha256_bytes(graph_bytes),
            manifest_sha256=_sha256_bytes(manifest_bytes),
            manifest=manifest,
            selection=selection,
            changed_paths=changed_paths,
            max_targets=max_targets,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        if not ok:
            return {**proof, "outcome": "blocked", "reason": reason}
        return {
            **proof,
            "outcome": "no-op",
            "stamped": [],
            "manifest_changed_rows": [],
            "note": "no selected changed targets; no artifact or freshness claim",
        }

    backend, backend_error = _backend_identity(extract_fn, backend_name)
    if backend_error:
        return {**proof, "outcome": "blocked", "reason": backend_error}
    proof["backend"] = backend
    target_paths = {item["path"] for item in selection["targets"]}
    all_changed_paths = {item["path"] for item in selection["all_changed"]}
    context_nodes, context_edges = unchanged_resolution_context(
        graph, all_changed_paths
    )
    try:
        stage_dir.mkdir(parents=True, exist_ok=False)
        cache_root = stage_dir / "extract-cache"
        cache_root.mkdir()
    except OSError as exc:
        return {
            **proof,
            "outcome": "blocked",
            "reason": f"stage_create_failed:{exc.__class__.__name__}",
        }
    try:
        fresh = (extract_fn or default_extract)(
            [source_root / path for path in sorted(target_paths)],
            root=source_root,
            cache_root=cache_root,
            resolution_context_nodes=context_nodes,
            resolution_context_edges=context_edges,
        )
    except Exception as exc:
        return _stage_blocked(
            proof, f"extraction_exception:{exc.__class__.__name__}", stage_dir
        )
    if not isinstance(fresh, dict):
        return _stage_blocked(proof, "extraction_malformed", stage_dir)

    ok, reason, _ = _recheck_inputs(
        source_root=source_root,
        graph_path=graph_path,
        manifest_path=manifest_path,
        graph_sha256=_sha256_bytes(graph_bytes),
        manifest_sha256=_sha256_bytes(manifest_bytes),
        manifest=manifest,
        selection=selection,
        changed_paths=changed_paths,
        max_targets=max_targets,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if not ok:
        return _stage_blocked(proof, reason, stage_dir)
    merged = merge_candidate(
        graph, fresh, target_paths, source_root=source_root
    )
    if not merged["ok"]:
        return _stage_blocked(
            proof,
            merged["error"],
            stage_dir,
            detail={
                key: value
                for key, value in merged.items()
                if key not in ("ok", "candidate")
            },
        )
    staged_manifest, stamped = stamp_manifest_subset(
        manifest, selection, target_paths
    )
    if stamped != sorted(target_paths):
        return _stage_blocked(proof, "subset_stamp_mismatch", stage_dir)
    candidate = merged["candidate"]
    candidate_graph_bytes = _json_bytes(candidate)
    candidate_manifest_bytes = _json_bytes(staged_manifest)
    try:
        _write_exclusive(stage_dir / "staged_graph.json", candidate_graph_bytes)
        _write_exclusive(stage_dir / "staged_manifest.json", candidate_manifest_bytes)
    except OSError as exc:
        return _stage_blocked(
            proof, f"stage_artifact_write_failed:{exc.__class__.__name__}", stage_dir
        )

    ok, reason, _ = _recheck_inputs(
        source_root=source_root,
        graph_path=graph_path,
        manifest_path=manifest_path,
        graph_sha256=_sha256_bytes(graph_bytes),
        manifest_sha256=_sha256_bytes(manifest_bytes),
        manifest=manifest,
        selection=selection,
        changed_paths=changed_paths,
        max_targets=max_targets,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if not ok:
        return _stage_blocked(proof, reason, stage_dir)
    receipt = {
        "receipt_schema": "veritas.graphify_incremental_stage_receipt.v1",
        "owner_version": OWNER_VERSION,
        "backend": backend,
        "baseline_graph_sha256": _sha256_bytes(graph_bytes),
        "baseline_manifest_sha256": _sha256_bytes(manifest_bytes),
        "staged_graph_sha256": _sha256_bytes(candidate_graph_bytes),
        "staged_manifest_sha256": _sha256_bytes(candidate_manifest_bytes),
        "target_sha256": {
            item["path"]: item["sha256"] for item in selection["targets"]
        },
        "exact_subset_stamps": stamped,
        "inventory_snapshot_sha256": selection["inventory_snapshot_sha256"],
        "deferred_changed": selection["deferred_changed"],
        "unserviceable_changed": selection["unserviceable_changed"],
        "subset_allowlist": selection["subset_allowlist"],
        "base_counts": merged["base"],
        "candidate_counts": merged["candidate_counts"],
        "all_graph_metadata_and_hyperedges_bound": True,
        "full_graph_freshness_claimed": False,
        "current_head_claimed": False,
        "publication": "staged_not_published",
    }
    full_proof = {
        **proof,
        "outcome": "staged",
        "receipt": receipt,
        "receipt_sha256": canonical_hash(receipt),
        "merge": {
            key: value for key, value in merged.items()
            if key not in ("ok", "candidate")
        },
        "stamped": stamped,
        "manifest_changed_rows": stamped,
    }
    try:
        _write_exclusive(stage_dir / "proof.json", _json_bytes(full_proof))
    except OSError as exc:
        return _stage_blocked(
            proof, f"stage_receipt_write_failed:{exc.__class__.__name__}", stage_dir
        )
    return full_proof


def run_publish(
    *, source_root: Path, graph_path: Path, manifest_path: Path, stage_dir: Path
) -> dict[str, Any]:
    """Atomically publish one verified staged batch, with rollback preimages."""
    proof = {
        "schema": OWNER_SCHEMA,
        "owner_version": OWNER_VERSION,
        "generated_at_utc": utc_now(),
        "mode": "publish",
        "full_graph_freshness_claimed": False,
        "current_head_claimed": False,
    }
    paths, path_error = _validate_publish_paths(
        source_root, graph_path, manifest_path, stage_dir
    )
    if path_error:
        return {**proof, "outcome": "blocked", "reason": path_error}
    assert paths is not None
    source_root = paths["source_root"]
    graph_path = paths["graph_path"]
    manifest_path = paths["manifest_path"]
    stage_dir = paths["stage_dir"]
    stage_proof, _, stage_error = _read_json_with_bytes(stage_dir / "proof.json")
    staged_graph, staged_graph_bytes, graph_error = _read_json_with_bytes(
        stage_dir / "staged_graph.json"
    )
    staged_manifest, staged_manifest_bytes, manifest_error = _read_json_with_bytes(
        stage_dir / "staged_manifest.json"
    )
    if (
        stage_error
        or not isinstance(stage_proof, dict)
        or graph_error
        or not isinstance(staged_graph, dict)
        or manifest_error
        or not isinstance(staged_manifest, dict)
    ):
        return {**proof, "outcome": "blocked", "reason": "stage_artifacts_unreadable"}
    receipt = stage_proof.get("receipt")
    if not isinstance(receipt, dict) or stage_proof.get("outcome") != "staged":
        return {**proof, "outcome": "blocked", "reason": "stage_receipt_invalid"}
    if (
        receipt.get("staged_graph_sha256") != _sha256_bytes(staged_graph_bytes or b"")
        or receipt.get("staged_manifest_sha256") != _sha256_bytes(staged_manifest_bytes or b"")
        or receipt.get("receipt_schema") != "veritas.graphify_incremental_stage_receipt.v1"
    ):
        return {**proof, "outcome": "blocked", "reason": "stage_hash_mismatch"}
    try:
        graph_bytes = graph_path.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {**proof, "outcome": "blocked", "reason": f"publication_baseline_unreadable:{exc.__class__.__name__}"}
    if (
        receipt.get("baseline_graph_sha256") != _sha256_bytes(graph_bytes)
        or receipt.get("baseline_manifest_sha256") != _sha256_bytes(manifest_bytes)
    ):
        return {**proof, "outcome": "blocked", "reason": "publication_baseline_drift"}
    if not isinstance(manifest, dict):
        return {**proof, "outcome": "blocked", "reason": "base_manifest_malformed"}
    changed_paths = receipt.get("subset_allowlist")
    if changed_paths is not None and not isinstance(changed_paths, list):
        return {**proof, "outcome": "blocked", "reason": "receipt_allowlist_malformed"}
    selection = select_targets(source_root, manifest, changed_paths=changed_paths)
    expected_hashes = receipt.get("target_sha256")
    if (
        selection["policy_block"]
        or selection["inventory_snapshot_sha256"] != receipt.get("inventory_snapshot_sha256")
        or not isinstance(expected_hashes, dict)
        or expected_hashes != {item["path"]: item["sha256"] for item in selection["targets"]}
        or receipt.get("exact_subset_stamps") != sorted(expected_hashes)
    ):
        return {**proof, "outcome": "blocked", "reason": "publication_source_drift"}
    try:
        _write_exclusive(stage_dir / "rollback_graph.preimage", graph_bytes)
        _write_exclusive(stage_dir / "rollback_manifest.preimage", manifest_bytes)
    except OSError as exc:
        return {**proof, "outcome": "blocked", "reason": f"rollback_preimage_write_failed:{exc.__class__.__name__}"}
    try:
        _atomic_replace(graph_path, staged_graph_bytes or b"")
        _atomic_replace(manifest_path, staged_manifest_bytes or b"")
    except OSError as exc:
        try:
            _atomic_replace(graph_path, graph_bytes)
            _atomic_replace(manifest_path, manifest_bytes)
        except OSError as rollback_exc:
            return {**proof, "outcome": "blocked", "reason": f"publication_apply_failed_rollback_failed:{rollback_exc.__class__.__name__}"}
        return {**proof, "outcome": "blocked", "reason": f"publication_apply_failed_rolled_back:{exc.__class__.__name__}"}
    if graph_path.read_bytes() != staged_graph_bytes or manifest_path.read_bytes() != staged_manifest_bytes:
        return {**proof, "outcome": "blocked", "reason": "publication_postwrite_mismatch"}
    freshness = freshness_report(source_root, staged_manifest)
    backlog = {
        "remaining_changed_count": (
            freshness["changed_count"] + freshness["new_count"] + freshness["deleted_count"]
        ),
        "changed_sample": freshness["changed_sample"],
        "new_sample": freshness["new_sample"],
        "deleted_sample": freshness["deleted_sample"],
        "policy_block": freshness["policy_block"],
        "resumable": freshness["status"] == "stale",
    }
    fresh = freshness["status"] == "fresh"
    return {
        **proof,
        "outcome": "published" if fresh else "published_with_backlog",
        "publication": "published_bounded_batch",
        "full_graph_freshness_claimed": fresh,
        "current_head_claimed": fresh,
        "backlog": backlog,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("stage", "publish"), default="stage")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--stage-dir", required=True)
    parser.add_argument("--changed-path", action="append", default=None)
    parser.add_argument("--max-targets", type=int, default=MAX_TARGETS)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=MAX_TOTAL_BYTES)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "publish":
        result = run_publish(
            source_root=Path(args.source_root),
            graph_path=Path(args.graph),
            manifest_path=Path(args.manifest),
            stage_dir=Path(args.stage_dir),
        )
    else:
        result = run_stage(
            source_root=Path(args.source_root),
            graph_path=Path(args.graph),
            manifest_path=Path(args.manifest),
            stage_dir=Path(args.stage_dir),
            changed_paths=args.changed_path,
            max_targets=max(1, args.max_targets),
            max_file_bytes=max(1, args.max_file_bytes),
            max_total_bytes=max(1, args.max_total_bytes),
        )
    print(json.dumps({
        key: result.get(key)
        for key in (
            "outcome", "reason", "stamped", "selection", "publication",
            "reports_html_status", "receipt_sha256", "backlog", 
        )
    }, sort_keys=True))
    return 0 if result.get("outcome") in (
        "staged",
        "no-op",
        "published",
        "published_with_backlog",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
