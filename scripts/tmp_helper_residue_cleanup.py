#!/usr/bin/env python3
"""Move known one-off tmp Python helpers into archive with a manifest.

This is a bounded workspace hygiene tool. It only targets executable Python
helpers directly under tmp/ and never deletes files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ARCHIVE_DIR = ROOT / "09. Archive" / "tmp-helper-residue-20260529"
MANIFEST = TMP / "tmp-helper-residue-cleanup-manifest.json"

AUTHORITY = {
    "move_only": True,
    "delete_allowed": False,
    "canonical_note_mutation_allowed": False,
    "config_auth_channel_service_runtime_mutation_allowed": False,
    "finance_canon_portfolio_mutation_allowed": False,
    "trade_account_paper_live_authority_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def references_for(path: Path) -> list[str]:
    name = path.name
    refs: list[str] = []
    for root in [ROOT / "scripts", ROOT / "06. Playbooks", ROOT / "skills", ROOT / "memory"]:
        if not root.exists():
            continue
        for candidate in root.rglob("*"):
            if candidate.is_file() and candidate.suffix.lower() in {".py", ".md", ".json", ".txt"}:
                try:
                    text = candidate.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if name in text or rel(path) in text:
                    refs.append(rel(candidate))
    return sorted(set(refs))


def build_report(move: bool) -> dict[str, Any]:
    candidates = sorted(TMP.glob("*.py"))
    rows: list[dict[str, Any]] = []
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for source in candidates:
        target = ARCHIVE_DIR / source.name
        before_hash = sha256(source)
        refs = references_for(source)
        moved = False
        if move:
            shutil.move(str(source), str(target))
            moved = True
            after_hash = sha256(target)
        else:
            after_hash = before_hash if target.exists() else None
        rows.append(
            {
                "source": rel(source),
                "target": rel(target),
                "sha256_before": before_hash,
                "sha256_after": after_hash,
                "references_found": refs,
                "reference_count": len(refs),
                "moved": moved,
                "rollback": f"Move {rel(target)} back to {rel(source)}",
            }
        )
    return {
        "schema_version": "tmp_helper_residue_cleanup_manifest.v1",
        "generated_at_utc": utc_now(),
        "status": "moved" if move else "planned",
        "candidate_count": len(candidates),
        "archive_dir": rel(ARCHIVE_DIR),
        "authority_boundary": AUTHORITY,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--move", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report(move=args.move)
    if args.write:
        MANIFEST.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"status={report['status']} candidates={report['candidate_count']} archive={report['archive_dir']} manifest={rel(MANIFEST) if args.write else 'stdout'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
