from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
ARCHIVE_ROOT = WORKSPACE / "09. Archive" / "Scripts and Tmp Cleanup - Archived"
OUT_PATH = TMP / "tmp-cleanup-report.json"

PROTECTED_FILES = {
    "band-note-sync.json",
    "band-note-sync.md",
    "band-proposals.json",
    "band-update-log.txt",
    "breadth-state.json",
    "call-log-sync.json",
    "credit-spreads.json",
    "daily-executive-brief.json",
    "daily-note-dedupe.json",
    "dashboard-acceptance-report.json",
    "dashboard-data.json",
    "dashboard-delta.json",
    "dashboard-last.json",
    "dashboard-validation.json",
    "deployment-check.json",
    "deployment-history.json",
    "deployment-readiness-surface.json",
    "earnings-calendar.json",
    "entry-band-status.html",
    "macro-regime.json",
    "market-state.json",
    "policy-expectations.json",
    "portfolio-config-validation.json",
    "portfolio-config.json",
    "positioning-ranking.json",
    "post-earnings-note-targets.json",
    "post-earnings-prep.json",
    "postmarket-snapshot.json",
    "premarket-snapshot.json",
    "regime-scores.json",
    "technical-refresh.json",
    "trigger-sheet.json",
    "tmp-cleanup-report.json",
    "universe-consistency.json",
    "veritas-command-center.html",
    "veritas-command-center.last-good.html",
    "weekly-intelligence-brief.json",
    "weekly-macro-snapshot.json",
    "weekly-review-skeleton.json",
    "workbook-build-validation.json",
    "workbook-control-panel.csv",
    "workbook-deployment-ranking.csv",
    "workbook-earnings-tracker.csv",
    "workbook-export-manifest.json",
    "workbook-technical-drift.csv",
    "workbook-watchlist-board.csv",
}

PROTECTED_PREFIXES = (
    "run-chain-",
    "run-summary-",
)

PROTECTED_DIRS = {
    "entry-band-data",
    "entry-band-reports",
    "reports",
    # Sole copy of the five default-route compiled SQL helpers; scripts/go/bin
    # holds older builds only. See scripts/go/README.md.
    "go-binaries",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive old one-off tmp artifacts behind an explicit operator gate.")
    parser.add_argument("--days", type=int, default=7, help="Minimum age in days before a non-governed tmp artifact becomes archive-eligible.")
    parser.add_argument("--dry-run", action="store_true", help="Print archive-eligible artifacts without moving anything. This is also the default when --apply is omitted.")
    parser.add_argument("--apply", action="store_true", help="Move eligible artifacts into the archive location.")
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_cache_path() -> Path:
    # Computed per call so tests that repoint WORKSPACE stay hermetic.
    return WORKSPACE / "state" / "tmp-cleanup-hash-cache.json"


HASH_CACHE_MAX_ENTRIES = 20000
# Files larger than this are not content-hashed: eligibility is age-based
# (newest_mtime, always exact) and hashing multi-GB trees dominated runtime
# (tmp/ holds ~4.5GB in a few dirs). Skipped files record bytes+mtime with
# sha256 None plus an explicit flag; dirs already report sha256 None.
HASH_SKIP_BYTES = 32 * 1024 * 1024

# Per-run memo of candidate scans: one traversal serves newest_mtime,
# manifest_record, and candidate_digest. Values are identical to repeated
# rglob passes; only redundant I/O is removed.
_scan_cache: dict[str, dict[str, Any]] = {}
_hash_cache: dict[str, str] = {}
_hash_cache_seen: set[str] = set()


def _dir_id(path: str) -> tuple[int, int] | None:
    import os

    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_dev, st.st_ino)


def _scan_subtree(root: str, seed: frozenset[tuple[int, int]]) -> tuple[float, list[tuple[str, int, int]]]:
    """Walk one subtree: (max mtime epoch, [(path, size, mtime_ns)]).

    Cycle-safe: directory (device, inode) pairs are tracked and revisited
    dirs are skipped, which breaks junction/symlink loops. On acyclic trees
    every dir is visited exactly once, so results are identical to rglob.
    """
    import os

    seen = set(seed)
    newest = 0.0
    files: list[tuple[str, int, int]] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            st = os.stat(current)
        except OSError:
            continue
        dir_id = (st.st_dev, st.st_ino)
        if dir_id in seen:
            continue
        seen.add(dir_id)
        if st.st_mtime > newest:
            newest = st.st_mtime
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.is_symlink() or entry.is_file(follow_symlinks=False):
                    fst = os.stat(entry.path)
                    if fst.st_mtime > newest:
                        newest = fst.st_mtime
                    files.append((entry.path, fst.st_size, fst.st_mtime_ns))
            except OSError:
                continue
    return newest, files


def scan_candidate(path: Path) -> dict[str, Any]:
    """Single-pass scan: newest mtime plus per-file identity for hashing.

    Covers exactly the entries path.rglob("*") plus path itself (symlinked
    dirs not descended, matching rglob; existence resolved the same way).
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    path = Path(path)
    key = str(path)
    cached = _scan_cache.get(key)
    if cached is not None:
        return cached
    try:
        top_mtime = path.stat().st_mtime
    except OSError:
        top_mtime = 0.0
    newest = top_mtime
    files: list[tuple[str, int, int]] = []
    try:
        children = sorted(os.scandir(path), key=lambda entry: entry.name)
    except OSError:
        children = []
    subdirs = [entry.path for entry in children if entry.is_dir(follow_symlinks=False)]
    for entry in children:
        # Top-level files/symlinks resolved exactly like the old rglob pass.
        try:
            if entry.is_symlink() or entry.is_file(follow_symlinks=False):
                st = os.stat(entry.path)
                if st.st_mtime > newest:
                    newest = st.st_mtime
                files.append((entry.path, st.st_size, st.st_mtime_ns))
        except OSError:
            continue
    if subdirs:
        workers = min(8, max(1, os.cpu_count() or 4))
        root_id = _dir_id(str(path))
        jobs = []
        for sub in subdirs:
            seed = {root_id} if root_id else set()
            sub_id = _dir_id(sub)
            if sub_id:
                seed.add(sub_id)
            jobs.append((sub, frozenset(seed)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for sub_newest, sub_files in pool.map(lambda job: _scan_subtree(*job), jobs):
                if sub_newest > newest:
                    newest = sub_newest
                files.extend(sub_files)
    files.sort(key=lambda item: item[0])
    result = {
        "newest_mtime": datetime.fromtimestamp(newest, tz=timezone.utc),
        "files": files,
    }
    _scan_cache[key] = result
    return result


def load_hash_cache() -> None:
    _hash_cache.clear()
    _hash_cache_seen.clear()
    try:
        payload = json.loads(hash_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, str):
                _hash_cache[key] = value


def save_hash_cache() -> None:
    # Drop entries for files that no longer match; cap size (keep recent).
    pruned = {key: _hash_cache[key] for key in _hash_cache_seen if key in _hash_cache}
    if len(pruned) > HASH_CACHE_MAX_ENTRIES:
        pruned = dict(list(pruned.items())[-HASH_CACHE_MAX_ENTRIES:])
    try:
        cache_file = hash_cache_path()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_handle = cache_file.with_suffix(cache_file.suffix + ".tmp")
        tmp_handle.write_text(json.dumps(pruned, sort_keys=True), encoding="utf-8")
        tmp_handle.replace(cache_file)
    except OSError:
        pass


def hash_cache_key(path: Path, size: int, mtime_ns: int) -> str:
    try:
        rel = path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        rel = str(path)
    return f"{rel}|{size}|{mtime_ns}"


def newest_mtime(path: Path) -> datetime:
    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return scan_candidate(path)["newest_mtime"]


def is_protected(path: Path) -> bool:
    rel = path.relative_to(TMP)
    parts = rel.parts
    if parts and parts[0] in PROTECTED_DIRS:
        return True
    name = path.name
    if name in PROTECTED_FILES:
        return True
    return any(name.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def is_candidate(path: Path, cutoff: datetime) -> bool:
    if is_protected(path):
        return False
    return newest_mtime(path) < cutoff


def archive_destination(run_date: str) -> Path:
    return ARCHIVE_ROOT / f"{run_date}-tmp-cleanup"


def sha256_path(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    key = hash_cache_key(path, stat.st_size, stat.st_mtime_ns)
    if stat.st_size > HASH_SKIP_BYTES:
        _hash_cache_seen.add(key)
        return None
    cached = _hash_cache.get(key)
    if cached is not None:
        _hash_cache_seen.add(key)
        return cached
    try:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
    except OSError:
        return None
    _hash_cache[key] = digest
    _hash_cache_seen.add(key)
    return digest


def manifest_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = sha256_path(path)
    record = {
        "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
        "kind": "dir" if path.is_dir() else "file",
        "bytes": stat.st_size if path.is_file() else None,
        "newest_mtime_utc": newest_mtime(path).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sha256": digest,
    }
    if path.is_file() and digest is None and stat.st_size > HASH_SKIP_BYTES:
        record["sha256_skipped_oversize"] = True
    return record


def candidate_digest(candidates: list[Path]) -> str:
    payload = [
        {
            "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
            "kind": "dir" if path.is_dir() else "file",
            "newest_mtime_utc": newest_mtime(path).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_path(path),
        }
        for path in candidates
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def protection_assertions(candidates: list[Path], moved: list[dict[str, Any]], apply_requested: bool) -> dict[str, Any]:
    violations = [str(path.relative_to(WORKSPACE)).replace("\\", "/") for path in candidates if is_protected(path)]
    return {
        "protected_file_count": len(PROTECTED_FILES),
        "protected_prefixes": list(PROTECTED_PREFIXES),
        "protected_dir_count": len(PROTECTED_DIRS),
        "protected_dirs": sorted(PROTECTED_DIRS),
        "candidate_protected_violation_count": len(violations),
        "candidate_protected_violations": violations,
        "all_candidates_pass_protection_filter": len(violations) == 0,
        "apply_requested": apply_requested,
        "dry_run_no_delete_assertion": (not apply_requested) and len(moved) == 0,
        "move_count_matches_mode": (len(moved) == 0) if not apply_requested else True,
        "destructive_cleanup_requires_separate_owner_approval": True,
    }


def rollback_plan(archive_dir: Path, moved: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "available_only_after_apply": bool(moved),
        "archive_dir": str(archive_dir.relative_to(WORKSPACE)).replace("\\", "/"),
        "moved_record_count": len(moved),
        "restore_method": (
            "Move each destination path back to its source path from moved[]. "
            "Then rerun the cleanup dry-run and affected validators before closing."
        ),
        "rollback_manifest_source": "moved",
    }


def authority_boundary(apply_requested: bool) -> dict[str, Any]:
    return {
        "review_only_dry_run": not apply_requested,
        "apply_requested": apply_requested,
        "archive_move_allowed": apply_requested,
        "delete_allowed": False,
        "cron_state_mutation_allowed": False,
        "cron_schedule_mutation_allowed": False,
        "runtime_config_mutation_allowed": False,
        "finance_canon_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "customer_or_external_delivery_allowed": False,
        "owner_approval_inferred": False,
    }


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    protection = report.get("protection_assertions", {})
    boundary = report.get("authority_boundary", {})

    if protection.get("candidate_protected_violation_count") != 0:
        errors.append("protected_candidates_present")
    if protection.get("all_candidates_pass_protection_filter") is not True:
        errors.append("candidate_protection_filter_failed")
    if protection.get("move_count_matches_mode") is not True:
        errors.append("move_count_does_not_match_mode")
    if report.get("mode") == "dry-run" and protection.get("dry_run_no_delete_assertion") is not True:
        errors.append("dry_run_move_or_delete_detected")
    if protection.get("destructive_cleanup_requires_separate_owner_approval") is not True:
        errors.append("destructive_cleanup_owner_approval_gate_missing")

    for key in (
        "delete_allowed",
        "cron_state_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "runtime_config_mutation_allowed",
        "finance_canon_mutation_allowed",
        "portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_not_false")

    if report.get("mode") == "apply":
        warnings.append("cleanup_apply_mode_requires_operator_closeout_review")

    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def move_path(src: Path, dest_root: Path) -> dict[str, Any]:
    before = manifest_record(src)
    rel = src.relative_to(TMP)
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    after = manifest_record(dest)
    return {"source": before, "destination": after}


def main() -> int:
    args = parse_args()
    _scan_cache.clear()
    load_hash_cache()
    now = utc_now()
    cutoff = now - timedelta(days=max(0, args.days))
    run_date = now.date().isoformat()

    candidates = [path for path in sorted(TMP.iterdir()) if is_candidate(path, cutoff)]
    moved: list[dict[str, Any]] = []
    archive_dir = archive_destination(run_date)

    if args.apply and candidates:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for path in candidates:
            moved.append(move_path(path, archive_dir))

    output = {
        "generated_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "mode": "apply" if args.apply else "dry-run",
        "retention_days": max(0, args.days),
        "archive_root": str(archive_dir.relative_to(WORKSPACE)).replace("\\", "/"),
        "summary": {
            "eligible_count": len(candidates),
            "moved_count": len(moved),
            "candidate_digest": candidate_digest(candidates),
            "protected_violation_count": 0,
        },
        "protection_assertions": protection_assertions(candidates, moved, args.apply),
        "authority_boundary": authority_boundary(args.apply),
        "rollback_plan": rollback_plan(archive_dir, moved),
        "candidates": [manifest_record(path) for path in candidates],
        "moved": moved,
    }
    output["summary"]["protected_violation_count"] = output["protection_assertions"]["candidate_protected_violation_count"]
    validation = validate_report(output)
    output["validation"] = validation
    output["status"] = "blocked" if validation["errors"] else validation["status"]
    output["operator_action"] = "BLOCKED" if validation["errors"] else "MAIN_SESSION_REQUIRED" if validation["warnings"] else "NO_REPLY"
    atomic_write_json(OUT_PATH, output)
    save_hash_cache()
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
