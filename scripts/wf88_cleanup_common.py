#!/usr/bin/env python3
"""Shared helpers for WF88 cleanup and thinning proof.

This module is intentionally side-effect light. It centralizes path, hash,
JSON, and reference-classification helpers used by WF88 cleanup scripts so
future delete/archive packets are built from one proof vocabulary.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".jsonl",
    ".csv",
    ".html",
    ".yaml",
    ".yml",
    ".ps1",
}

SQLITE_DB_SUFFIXES = {".sqlite", ".db"}
SQLITE_SIDECAR_SUFFIXES = (".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm")

EXCLUDED_DIRS = {
    ".git",
    ".obsidian",
    ".openclaw",
    ".clawhub",
    "__pycache__",
    "node_modules",
}

WF88_CLEANUP_CONTROL_SCRIPTS = {
    "scripts/wf88_route_contraction_packet.py",
    "scripts/wf88_retired_surface_cleanup_plan.py",
    "scripts/wf88_script_cleanup_inventory.py",
    "scripts/wf88_typed_script_reference_graph.py",
    "scripts/human_canon_thinning_retirement_inventory.py",
    "scripts/ticker_answer_packet_retirement_plan.py",
    "scripts/deployment_contract_legacy_read_audit.py",
    "scripts/sql_canon_consumer_inventory.py",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_workspace_path(path: str | Path, root: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else root / str(p).replace("/", "\\")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sqlite_sidecar(path: Path, *, sidecar_suffixes: tuple[str, ...] = SQLITE_SIDECAR_SUFFIXES) -> bool:
    return path.name.lower().endswith(sidecar_suffixes)


def sqlite_sidecar_kind(path: Path) -> str | None:
    lower = path.name.lower()
    if lower.endswith("-wal"):
        return "wal"
    if lower.endswith("-shm"):
        return "shm"
    return None


def sqlite_parent_for_sidecar(path: Path) -> Path | None:
    if not is_sqlite_sidecar(path):
        return None
    return Path(str(path)[:-4])


def iter_sqlite_db_files(
    search_roots: list[Path] | tuple[Path, ...],
    *,
    db_suffixes: set[str] = SQLITE_DB_SUFFIXES,
    root: Path = ROOT,
) -> list[Path]:
    files: list[Path] = []
    for base in search_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in db_suffixes:
                files.append(path)
    return sorted(files, key=lambda p: rel(p, root).lower())


def iter_orphan_sqlite_sidecars(
    search_roots: list[Path] | tuple[Path, ...],
    *,
    db_files: list[Path] | tuple[Path, ...] | None = None,
    sidecar_suffixes: tuple[str, ...] = SQLITE_SIDECAR_SUFFIXES,
    root: Path = ROOT,
) -> list[Path]:
    known_dbs = {path.resolve() for path in (db_files or [])}
    sidecars: list[Path] = []
    for base in search_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or not path.name.lower().endswith(sidecar_suffixes):
                continue
            parent = sqlite_parent_for_sidecar(path)
            if parent is None:
                continue
            if parent.exists() or parent.resolve() in known_dbs:
                continue
            sidecars.append(path)
    return sorted(sidecars, key=lambda p: rel(p, root).lower())


def input_record(path: Path, payload: dict[str, Any] | None = None, *, root: Path = ROOT, required: bool | None = None) -> dict[str, Any]:
    payload = payload or {}
    record = {
        "path": rel(path, root),
        "present": path.exists(),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "sha256": file_sha256(path),
    }
    if required is not None:
        record["required"] = required
    return record


def wf88_reference_category(source_path: str, *, typed_graph: bool = False) -> str:
    norm = source_path.replace("\\", "/")
    if typed_graph and (norm.startswith("09. Archive/") or norm.startswith("backups/") or norm.startswith("migration-backups/")):
        return "archive_or_backup_history"
    if norm.startswith("tmp/"):
        return "generated_tmp_proof"
    if norm.startswith("memory/") or norm.startswith("08. Audits/"):
        return "history_or_audit"
    if norm.startswith("06. Playbooks/"):
        return "continuity_or_playbook" if typed_graph else "operating_procedure_or_continuity"
    if norm.startswith("scripts/test_"):
        return "test_consumer"
    if norm in WF88_CLEANUP_CONTROL_SCRIPTS:
        return "cleanup_or_migration_control" if typed_graph else "cleanup_or_retirement_control"
    if norm.startswith("scripts/") and (not typed_graph or norm.endswith(".py")):
        return "active_code_or_control_consumer"
    if norm.endswith("README.md"):
        return "documentation"
    return "other_text_reference" if typed_graph else "unknown"


def wf88_reference_need(category: str) -> str:
    if category == "active_code_or_control_consumer":
        return "must_replace_before_delete"
    if category in {"cleanup_or_migration_control", "cleanup_or_retirement_control", "test_consumer", "continuity_or_playbook", "operating_procedure_or_continuity", "documentation", "self_reference"}:
        return "can_be_updated_or_retained_as_proof"
    if category in {"archive_or_backup_history", "history_or_audit", "generated_tmp_proof"}:
        return "history_only"
    return "review_required"


def iter_text_files(root: Path = ROOT, *, text_extensions: set[str] | None = None, excluded_dirs: set[str] | None = None) -> list[Path]:
    extensions = text_extensions or TEXT_EXTENSIONS
    exclusions = excluded_dirs or EXCLUDED_DIRS
    files: list[Path] = []
    for path in root.rglob("*"):
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            rel_parts = path.parts
        if any(part in exclusions for part in rel_parts):
            continue
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        files.append(path)
    return files
