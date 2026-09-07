#!/usr/bin/env python3
"""Archive retired portfolio, deployment, sizing, and paper current-state artifacts.

The apply path is exact, hash-verified, rollback-capable, and fail-closed. SQLite
sources receive standalone backup-API copies before their original bytes move.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "09. Archive" / "Finance Runtime" / "2026-08-29-portfolio-paper-state-retirement"
RAW_ROOT = ARCHIVE / "source-state"
BACKUP_ROOT = ARCHIVE / "sqlite-backups"
MANIFEST = ARCHIVE / "archive-manifest.json"

DIRECTORY_ROOTS = (
    "tmp/alpaca-paper-readiness",
    "tmp/paper-autotrader",
    "tmp/portfolio-mutation-proposals",
    "tmp/full-answer-parity",
    "tmp/wf84-parity-convergence",
    "tmp/trade-grade-full-answer",
    "tmp/ticker-answer-packets",
    "tmp/ticker-intelligence-cards",
)

EXACT_FILES = (
    "state/finance/execution-board-replacement.json",
    "tmp/portfolio-config.json",
    "tmp/veritas-canon-cache.sqlite",
    "tmp/finance-vector-retrieval-summary.json",
    "tmp/market-state.json",
    "tmp/positioning-ranking.json",
    "tmp/autonomous-routing-deployment-cards.json",
    "tmp/wf85-deployment-timing-gate.json",
)

TOP_LEVEL_GLOBS = (
    "canonical-finance-data-plane*",
    "finance-intelligence-state*",
    "finance-stack-snapshot*",
    "veritas-canon-cache*",
    "wf67-paper-position-state*",
    "wf84-parity-convergence*",
    "trade-grade-*",
    "position-sizing-readiness-*",
    "tuesday-position-sizing-*",
    "tuesday-alert-proposal-sizing-*",
    "auto-position-sizing-*",
    "sector-allocation-*",
    "deployment-*",
    "autonomous-routing-deployment-*",
    "capital-deployment-*",
    "capital-base-sizing-*",
    "real-capital-active-deployment-*",
    "finance-market-deployment-*",
    "full-portfolio-*",
    "portfolio-*",
    "wf78-deployment-*",
    "wf78-position-sizing-*",
    "wf78-sizing-*",
    "wf85-paper-deployment-*",
    "morning-paper-deployment-*",
    "morning-market-paper-*",
    "midday-market-paper-*",
    "postclose-paper-*",
    "wf87-paper-*",
    "wf87-position-sizing-*",
    "wf87-portfolio-*",
    "main-session-approval-ready-wf67-order-card-*",
    "workbook-deployment-*",
)

KNOWN_EPHEMERAL_SIDECARS = {
    "tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    "tmp/canonical-finance-data-plane.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/canonical-finance-data-plane.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    "tmp/finance-intelligence-state.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/finance-intelligence-state.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    "tmp/finance-stack-snapshot.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/finance-stack-snapshot.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    "tmp/veritas-canon-cache.pre-a1-20260604T041856Z.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/veritas-canon-cache.pre-a1-20260604T041856Z.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    "tmp/wf67-paper-position-state.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/wf67-paper-position-state.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    "tmp/wf67-paper-position-state.pre-block-test.20260528-175138.sqlite-shm": {"bytes": 32768, "sha256": "fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb"},
    "tmp/wf67-paper-position-state.pre-block-test.20260528-175138.sqlite-wal": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_inside(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(parent.resolve())
    return resolved


def extended_path(path: Path) -> Path:
    """Return a Windows extended-length path so archived deep trees remain verifiable."""
    resolved = path.resolve()
    value = str(resolved)
    if value.startswith("\\\\?\\"):
        return Path(value)
    return Path("\\\\?\\" + value)


def selected_roots() -> tuple[list[Path], list[Path]]:
    directories = [ROOT / value for value in DIRECTORY_ROOTS if (ROOT / value).exists()]
    files: set[Path] = {ROOT / value for value in EXACT_FILES if (ROOT / value).is_file()}
    tmp = ROOT / "tmp"
    for pattern in TOP_LEVEL_GLOBS:
        files.update(path for path in tmp.glob(pattern) if path.is_file())
    directories = sorted({ensure_inside(path, ROOT) for path in directories}, key=lambda value: rel(value))
    files = {
        ensure_inside(path, ROOT)
        for path in files
        if not any(path.resolve().is_relative_to(directory.resolve()) for directory in directories)
    }
    return directories, sorted(files, key=lambda value: rel(value))


def all_source_files(directories: list[Path], files: list[Path]) -> list[Path]:
    result = list(files)
    for directory in directories:
        result.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(set(result), key=lambda value: rel(value))


def sqlite_proof(path: Path, backup: bool) -> dict[str, Any]:
    wal = Path(f"{path}-wal")
    wal_bytes = wal.stat().st_size if wal.exists() else 0
    if wal_bytes:
        raise RuntimeError(f"nonempty WAL blocks archive: {rel(path)} ({wal_bytes} bytes)")
    source = sqlite3.connect(path, timeout=5)
    destination: sqlite3.Connection | None = None
    try:
        source.execute("PRAGMA foreign_keys=ON")
        integrity = [row[0] for row in source.execute("PRAGMA integrity_check")]
        foreign_keys = [list(row) for row in source.execute("PRAGMA foreign_key_check")]
        tables = [
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {table: source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
        if integrity != ["ok"] or foreign_keys:
            raise RuntimeError(f"SQLite integrity/FK failure: {rel(path)}")
        backup_rel = None
        backup_hash = None
        if backup:
            target = ensure_inside(BACKUP_ROOT / path.relative_to(ROOT), ARCHIVE)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                destination = sqlite3.connect(target)
            else:
                destination = sqlite3.connect(target)
                source.backup(destination)
                destination.commit()
            backup_integrity = [row[0] for row in destination.execute("PRAGMA integrity_check")]
            backup_fk = [list(row) for row in destination.execute("PRAGMA foreign_key_check")]
            backup_counts = {
                table: destination.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in tables
            }
            if backup_integrity != ["ok"] or backup_fk or backup_counts != counts:
                raise RuntimeError(f"SQLite backup verification failed: {rel(path)}")
            backup_rel = target.relative_to(ROOT).as_posix()
            backup_hash = sha256(target)
        return {
            "source": rel(path),
            "source_sha256": sha256(path),
            "integrity_check": integrity,
            "foreign_key_violation_count": len(foreign_keys),
            "table_row_counts": counts,
            "wal_bytes": wal_bytes,
            "backup": backup_rel,
            "backup_sha256": backup_hash,
        }
    finally:
        if destination is not None:
            destination.close()
        source.close()


def build_inventory(directories: list[Path], files: list[Path]) -> list[dict[str, Any]]:
    entries = []
    for source in all_source_files(directories, files):
        destination = ensure_inside(RAW_ROOT / source.relative_to(ROOT), ARCHIVE)
        entries.append(
            {
                "source": rel(source),
                "destination": destination.relative_to(ROOT).as_posix(),
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
            }
        )
    return entries


def archived_inventory() -> list[dict[str, Any]]:
    entries = []
    if not RAW_ROOT.exists():
        return entries
    scan_root = extended_path(RAW_ROOT)
    for destination in sorted((path for path in scan_root.rglob("*") if path.is_file()), key=lambda value: value.as_posix()):
        original = destination.relative_to(scan_root).as_posix()
        normal_destination = RAW_ROOT / original
        entries.append(
            {
                "source": original,
                "destination": normal_destination.relative_to(ROOT).as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )
    return entries


def archived_sqlite_proofs() -> list[dict[str, Any]]:
    proofs: list[dict[str, Any]] = []
    for raw in sorted(RAW_ROOT.rglob("*.sqlite"), key=lambda value: value.as_posix()):
        original = raw.relative_to(RAW_ROOT)
        backup = BACKUP_ROOT / original
        if not backup.is_file():
            raise RuntimeError(f"standalone SQLite backup missing: {backup.relative_to(ROOT).as_posix()}")
        raw_check = sqlite_proof(raw, backup=False)
        backup_check = sqlite_proof(backup, backup=False)
        if raw_check["table_row_counts"] != backup_check["table_row_counts"]:
            raise RuntimeError(f"SQLite backup row-count mismatch: {original.as_posix()}")
        proofs.append(
            {
                "source": original.as_posix(),
                "source_sha256": sha256(raw),
                "integrity_check": raw_check["integrity_check"],
                "foreign_key_violation_count": raw_check["foreign_key_violation_count"],
                "table_row_counts": raw_check["table_row_counts"],
                "wal_bytes": raw_check["wal_bytes"],
                "backup": backup.relative_to(ROOT).as_posix(),
                "backup_sha256": sha256(backup),
            }
        )
    return proofs


def write_manifest(payload: dict[str, Any]) -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_archive() -> dict[str, Any]:
    directories, files = selected_roots()
    preflight_inventory = build_inventory(directories, files)
    if not preflight_inventory and not RAW_ROOT.exists():
        raise RuntimeError("no retirement candidates found")
    for entry in preflight_inventory:
        destination = extended_path(ROOT / entry["destination"])
        if destination.exists():
            raise RuntimeError(f"archive destination exists: {entry['destination']}")

    sqlite_sources = [ROOT / entry["source"] for entry in preflight_inventory if entry["source"].lower().endswith(".sqlite")]
    for path in sqlite_sources:
        sqlite_proof(path, backup=True)

    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    for directory in directories:
        destination = ensure_inside(RAW_ROOT / directory.relative_to(ROOT), ARCHIVE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(directory), str(destination))
    disappeared_sidecars: list[dict[str, Any]] = []
    preflight_by_source = {entry["source"]: entry for entry in preflight_inventory}
    for source in files:
        if not source.exists():
            if source.name.endswith(("-shm", "-wal")):
                prior = preflight_by_source.get(rel(source), {})
                disappeared_sidecars.append(
                    {
                        "source": rel(source),
                        "bytes": prior.get("bytes"),
                        "sha256": prior.get("sha256"),
                        "reason": "ephemeral SQLite sidecar removed by a clean close after verified backup; WAL was empty",
                    }
                )
                continue
            raise RuntimeError(f"source disappeared before archive move: {rel(source)}")
        destination = ensure_inside(RAW_ROOT / source.relative_to(ROOT), ARCHIVE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    inventory = archived_inventory()
    sqlite_checks = archived_sqlite_proofs()
    errors: list[str] = []
    for entry in inventory:
        source = extended_path(ROOT / entry["source"])
        destination = extended_path(ROOT / entry["destination"])
        if source.exists():
            errors.append(f"source still exists: {entry['source']}")
        if not destination.is_file():
            errors.append(f"archive missing: {entry['destination']}")
        elif sha256(destination) != entry["sha256"]:
            errors.append(f"archive hash mismatch: {entry['destination']}")

    payload = {
        "schema": "veritas.alerts_os_runtime_retirement.v1",
        "status": "ok" if not errors else "blocked",
        "applied": True,
        "generated_at_utc": utc_now(),
        "reason": "2026-08-29 user-authorized pivot from portfolio/paper operations to alerts and non-executing recommendations",
        "source_root": str(ROOT),
        "archive_root": rel(ARCHIVE),
        "file_count": len(inventory),
        "total_bytes": sum(entry["bytes"] for entry in inventory),
        "directory_roots": [rel(path) for path in directories],
        "standalone_sqlite_backups": sqlite_checks,
        "ephemeral_sidecars_retired": [
            {
                "source": source,
                **metadata,
                "reason": "ephemeral SQLite sidecar retired after a clean close; every WAL was empty and standalone backup integrity/row counts are verified",
            }
            for source, metadata in sorted(KNOWN_EPHEMERAL_SIDECARS.items())
            if not (ROOT / source).exists() and not (RAW_ROOT / source).exists()
        ] + disappeared_sidecars,
        "files": inventory,
        "errors": errors,
        "rollback": {
            "owner_gate_required": True,
            "command": "python scripts\\retire_portfolio_paper_runtime_state.py --restore --approval-reference \"<owner approval>\" --validate",
        },
        "boundaries": {
            "capital_or_execution_action": False,
            "account_or_brokerage_action": False,
            "cron_or_runtime_config_mutation": False,
            "historical_audit_preserved": True,
        },
    }
    write_manifest(payload)
    if errors:
        raise RuntimeError("; ".join(errors))
    return payload


def validate_archive() -> dict[str, Any]:
    if not MANIFEST.is_file():
        raise RuntimeError("archive manifest is missing")
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in payload.get("files", []):
        source = extended_path(ROOT / entry["source"])
        destination = extended_path(ROOT / entry["destination"])
        if source.exists():
            errors.append(f"source restored or recreated: {entry['source']}")
        if not destination.is_file():
            errors.append(f"archive missing: {entry['destination']}")
        elif sha256(destination) != entry["sha256"]:
            errors.append(f"archive hash mismatch: {entry['destination']}")
    for proof in payload.get("standalone_sqlite_backups", []):
        backup = ROOT / proof["backup"]
        if not backup.is_file() or sha256(backup) != proof["backup_sha256"]:
            errors.append(f"SQLite backup missing/hash mismatch: {proof.get('backup')}")
        else:
            check = sqlite_proof(backup, backup=False)
            if check["table_row_counts"] != proof["table_row_counts"]:
                errors.append(f"SQLite backup row-count mismatch: {proof.get('backup')}")
    result = {
        "status": "ok" if not errors else "blocked",
        "manifest": rel(MANIFEST),
        "file_count": payload.get("file_count", 0),
        "total_bytes": payload.get("total_bytes", 0),
        "errors": errors,
    }
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def restore_archive(approval_reference: str) -> dict[str, Any]:
    if not approval_reference.strip():
        raise RuntimeError("--approval-reference is required for restore")
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in payload.get("files", []):
        source = extended_path(ROOT / entry["source"])
        archived = extended_path(ROOT / entry["destination"])
        if source.exists():
            raise RuntimeError(f"restore target exists: {entry['source']}")
        if not archived.is_file() or sha256(archived) != entry["sha256"]:
            raise RuntimeError(f"archive unavailable or changed: {entry['destination']}")
    for entry in payload.get("files", []):
        source = extended_path(ROOT / entry["source"])
        archived = extended_path(ROOT / entry["destination"])
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archived), str(source))
    return {"status": "restored", "approval_reference": approval_reference, "file_count": payload.get("file_count", 0)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--approval-reference", default="")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.apply and args.restore:
        raise SystemExit("choose --apply or --restore")
    if args.restore:
        result = restore_archive(args.approval_reference)
    elif args.apply:
        result = apply_archive()
    elif args.validate:
        result = validate_archive()
    else:
        directories, files = selected_roots()
        inventory = build_inventory(directories, files)
        result = {
            "status": "preflight",
            "directory_roots": [rel(path) for path in directories],
            "file_count": len(inventory),
            "total_bytes": sum(entry["bytes"] for entry in inventory),
            "sqlite_count": sum(entry["source"].lower().endswith(".sqlite") for entry in inventory),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
