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
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive old one-off tmp artifacts behind an explicit operator gate.")
    parser.add_argument("--days", type=int, default=7, help="Minimum age in days before a non-governed tmp artifact becomes archive-eligible.")
    parser.add_argument("--dry-run", action="store_true", help="Print archive-eligible artifacts without moving anything. This is also the default when --apply is omitted.")
    parser.add_argument("--apply", action="store_true", help="Move eligible artifacts into the archive location.")
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def newest_mtime(path: Path) -> datetime:
    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    mtimes = [datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) for p in path.rglob("*") if p.exists()]
    mtimes.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    return max(mtimes)


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
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def manifest_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
        "kind": "dir" if path.is_dir() else "file",
        "bytes": stat.st_size if path.is_file() else None,
        "newest_mtime_utc": newest_mtime(path).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sha256": sha256_path(path),
    }


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
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
