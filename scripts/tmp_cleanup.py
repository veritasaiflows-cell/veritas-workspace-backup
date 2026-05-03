from __future__ import annotations

import argparse
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


def move_path(src: Path, dest_root: Path) -> str:
    rel = src.relative_to(TMP)
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return str(dest.relative_to(WORKSPACE)).replace("\\", "/")


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
            dest = move_path(path, archive_dir)
            moved.append({
                "source": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
                "destination": dest,
            })

    output = {
        "generated_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": "apply" if args.apply else "dry-run",
        "retention_days": max(0, args.days),
        "archive_root": str(archive_dir.relative_to(WORKSPACE)).replace("\\", "/"),
        "summary": {
            "eligible_count": len(candidates),
            "moved_count": len(moved),
        },
        "candidates": [str(path.relative_to(WORKSPACE)).replace("\\", "/") for path in candidates],
        "moved": moved,
    }
    atomic_write_json(OUT_PATH, output)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
