#!/usr/bin/env python3
"""
memory_append_idempotent.py

Idempotent append helper for memory/YYYY-MM-DD.md files.

Prevents the redundant memory-append retries that happen when a compaction
resumes in split turns: the script checks whether the destination file already
contains a requested anchor/section header before writing.

Usage:
  python scripts\memory_append_idempotent.py ^
    --path memory\2026-08-17.md ^
    --anchor "## 12:38 Phoenix" ^
    --content-file tmp\memory-section-to-append.md ^
    --outcome-marker "band-maintenance-2026-08-17" ^
    --write --validate

Exit codes:
  0  success (appended, or already present and skipped idempotently)
  1  unexpected error
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone


def file_contains_anchor(path: Path, anchor: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return anchor in text


def append_content(path: Path, content: str, outcome_marker: str | None = None) -> dict:
    path = Path(path)
    if not path.exists():
        path.write_text("", encoding="utf-8")

    if outcome_marker:
        marker_line = f"\n<!-- idempotent-outcome: {outcome_marker} -->\n"
        if marker_line.strip() in path.read_text(encoding="utf-8"):
            return {
                "appended": False,
                "reason": "outcome_marker_present",
                "outcome_marker": outcome_marker,
                "path": str(path),
            }

    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
        if not content.endswith("\n"):
            f.write("\n")
        if outcome_marker:
            f.write(f"<!-- idempotent-outcome: {outcome_marker} -->\n")

    return {
        "appended": True,
        "path": str(path),
        "outcome_marker": outcome_marker,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotent memory append helper")
    parser.add_argument("--path", required=True, help="Destination memory file path")
    parser.add_argument("--anchor", required=True, help="Section header/anchor to check for presence")
    parser.add_argument("--content-file", help="File containing content to append")
    parser.add_argument("--content", help="Literal content to append (alternative to --content-file)")
    parser.add_argument("--outcome-marker", help="Machine-readable marker to embed after append")
    parser.add_argument("--write", action="store_true", help="Actually modify the file")
    parser.add_argument("--validate", action="store_true", help="Write a JSON result file to tmp/")
    args = parser.parse_args()

    path = Path(args.path)

    if args.content_file and args.content:
        print("ERROR: use --content-file or --content, not both", file=sys.stderr)
        return 1

    content = ""
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        print("ERROR: --content-file or --content required", file=sys.stderr)
        return 1

    result: dict

    if file_contains_anchor(path, args.anchor):
        result = {
            "appended": False,
            "reason": "anchor_present",
            "anchor": args.anchor,
            "path": str(path),
        }
    elif args.write:
        result = append_content(path, content, args.outcome_marker)
    else:
        result = {
            "appended": False,
            "reason": "dry_run",
            "anchor": args.anchor,
            "path": str(path),
            "would_append": True,
        }

    print(json.dumps(result, indent=2))

    if args.validate:
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)
        stem = path.stem
        result_file = tmp_dir / f"memory-append-idempotent-{stem}.json"
        result_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
