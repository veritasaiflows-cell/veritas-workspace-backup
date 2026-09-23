#!/usr/bin/env python3
"""Age-limit retention for untracked bulk archives (Workspace Review item 2, rec. 3).

Randall-approved 2026-09-22 19:37 MST. Scope is deliberately narrow: only dated
tmp-cleanup archive dirs and skills-backup zips that git does NOT track (they are
excluded by .gitignore, so the local disk holds the only copy and git history does
not need them). Tracked archives are the off-machine backup and are never touched.

An item is eligible only when all hold:
- it matches a retention pattern and its date stamp is older than --days (default 30);
- no file under it is tracked by git;
- no active script or state file references its folder/file name.

Dry-run by default. --apply deletes eligible items and writes a deletion manifest.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "09. Archive"
OUT = ROOT / "tmp" / "archive-retention-report.json"
MANIFEST_DIR = ROOT / "state" / "archive-retention"
RULES = (
    (ARCHIVE / "Scripts and Tmp Cleanup - Archived", re.compile(r"^(\d{4}-\d{2}-\d{2})-tmp-cleanup$")),
    (ARCHIVE, re.compile(r"^skills-backup-(\d{4})(\d{2})(\d{2})\.zip$")),
)
REFERENCE_ROOTS = (ROOT / "scripts", ROOT / "state")
REFERENCE_SUFFIXES = {".py", ".json", ".jsonl", ".md", ".ps1"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def stamp_date(match: re.Match[str]) -> date:
    groups = match.groups()
    text = groups[0] if len(groups) == 1 else "-".join(groups)
    return date.fromisoformat(text)


def tracked_count(path: Path) -> int:
    result = subprocess.run(["git", "ls-files", "--", rel(path)], cwd=ROOT, capture_output=True, text=True, check=True)
    return len([line for line in result.stdout.splitlines() if line.strip()])


def referenced_by(name: str) -> list[str]:
    hits: list[str] = []
    for base in REFERENCE_ROOTS:
        for path in base.rglob("*"):
            if path.suffix not in REFERENCE_SUFFIXES or not path.is_file() or path.name == Path(__file__).name:
                continue
            if "archive-retention" in path.parts:
                continue
            try:
                if name in path.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(rel(path))
            except OSError:
                continue
    return hits


def evaluate(days: int, today: date) -> list[dict[str, Any]]:
    rows = []
    for parent, pattern in RULES:
        if not parent.exists():
            continue
        for item in sorted(parent.iterdir()):
            match = pattern.match(item.name)
            if not match:
                continue
            age_days = (today - stamp_date(match)).days
            tracked = tracked_count(item)
            refs = referenced_by(item.name) if age_days >= days and not tracked else []
            reasons = []
            if age_days < days:
                reasons.append(f"age_{age_days}d_below_{days}d")
            if tracked:
                reasons.append(f"git_tracked_{tracked}_files")
            if refs:
                reasons.append("referenced")
            rows.append({
                "path": rel(item),
                "age_days": age_days,
                "git_tracked_files": tracked,
                "references": refs[:10],
                "eligible": not reasons,
                "reasons": reasons,
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--apply", action="store_true", help="Delete eligible items (default: dry-run).")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    rows = evaluate(args.days, now.date())
    deleted = []
    if args.apply:
        for row in rows:
            if not row["eligible"]:
                continue
            target = ROOT / row["path"]
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            deleted.append(row["path"])
        if deleted:
            MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
            atomic_write_json(MANIFEST_DIR / f"deleted-{now.strftime('%Y%m%dT%H%M%SZ')}.json",
                              {"generated_at_utc": now.isoformat(), "days": args.days, "deleted": deleted})
    report = {
        "schema": "veritas.archive_retention.v1",
        "generated_at_utc": now.replace(microsecond=0).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "days": args.days,
        "items": rows,
        "eligible_count": sum(1 for row in rows if row["eligible"]),
        "deleted": deleted,
        "authority_boundary": {"tracked_archives_touched": False, "scope": "untracked tmp-cleanup dirs and skills-backup zips only"},
    }
    atomic_write_json(OUT, report)
    print(f"mode={report['mode']} items={len(rows)} eligible={report['eligible_count']} deleted={len(deleted)}")
    for row in rows:
        print(f"  {'ELIGIBLE' if row['eligible'] else 'keep    '} {row['path']} age={row['age_days']}d {','.join(row['reasons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
