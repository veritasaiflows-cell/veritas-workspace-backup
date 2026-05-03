from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from market_data_utils import atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[2]
MEMORY_DIR = WORKSPACE / "memory"
CANONICAL_DAILY_NOTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
REPORT_PATH = WORKSPACE / "tmp" / "daily-note-dedupe.json"


def canonical_daily_notes() -> list[Path]:
    if not MEMORY_DIR.exists():
        return []
    return sorted(
        path for path in MEMORY_DIR.iterdir() if path.is_file() and CANONICAL_DAILY_NOTE_RE.match(path.name)
    )


def dedupe_lines(lines: list[str]) -> tuple[list[str], dict[str, int]]:
    seen_bullets: set[str] = set()
    deduped: list[str] = []
    removed = 0
    duplicate_counts: dict[str, int] = {}

    for line in lines:
        if line.startswith("- "):
            if line in seen_bullets:
                removed += 1
                duplicate_counts[line] = duplicate_counts.get(line, 1) + 1
                continue
            seen_bullets.add(line)
        deduped.append(line)

    return deduped, {
        "removed": removed,
        "unique_duplicate_bullets": len(duplicate_counts),
        "max_occurrence_count": max(duplicate_counts.values(), default=1),
    }


def read_note(path: Path) -> tuple[str, str]:
    for encoding in ("utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("daily_note_dedupe", b"", 0, 1, f"Could not decode {path}")


def process_note(path: Path, *, apply: bool) -> dict[str, object]:
    original, encoding = read_note(path)
    lines = original.splitlines()
    deduped_lines, stats = dedupe_lines(lines)
    changed = deduped_lines != lines

    if changed and apply:
        content = "\n".join(deduped_lines)
        if original.endswith("\n"):
            content += "\n"
        atomic_write_text(path, content, encoding=encoding)

    return {
        "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
        "encoding": encoding,
        "changed": changed,
        "removed": stats["removed"],
        "unique_duplicate_bullets": stats["unique_duplicate_bullets"],
        "max_occurrence_count": stats["max_occurrence_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove exact duplicate bullets from canonical daily notes.")
    parser.add_argument("path", nargs="?", help="Optional path to a specific daily note.")
    parser.add_argument("--all", action="store_true", help="Process all canonical daily notes in memory/.")
    parser.add_argument("--apply", action="store_true", help="Write changes instead of dry-run only.")
    args = parser.parse_args()

    if args.path and args.all:
        parser.error("Use either a specific path or --all, not both.")

    if args.path:
        paths = [Path(args.path).resolve() if not Path(args.path).is_absolute() else Path(args.path)]
    elif args.all:
        paths = canonical_daily_notes()
    else:
        parser.error("Provide a note path or use --all.")

    results = [process_note(path, apply=args.apply) for path in paths]
    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "files_scanned": len(results),
        "files_changed": sum(1 for item in results if item["changed"]),
        "total_removed": sum(int(item["removed"]) for item in results),
        "results": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(REPORT_PATH, json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
