#!/usr/bin/env python3
"""Apply the approved WF78 legacy-42 proof archive microbatch.

This moves only archive-plan candidates that have no live script dependency.
It never deletes files and never archives active SQL, source, canon, portfolio,
account, or runtime surfaces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PLAN_PATH = TMP / "finance-sql-canon-legacy-42-archive-plan.json"
REPORT_PATH = TMP / "finance-sql-canon-legacy-42-archive-apply-report.json"
ARCHIVE_ROOT = ROOT / "09. Archive" / "WF78 Finance SQL Canon Legacy 42 Proof" / "2026-05-30"

TEXT_EXTENSIONS = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".ps1"}
SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / "06. Playbooks",
    ROOT / "skills",
    ROOT / "TOOLS.md",
    ROOT / "AGENTS.md",
    ROOT / "MEMORY.md",
]
NON_BLOCKING_ROOT_PARTS = {"tmp", "09. Archive", "memory", "backups"}
NON_BLOCKING_SCRIPT_REFERENCES = {
    "scripts/finance_sql_canon.py",
    "scripts/finance_sql_canon_archive_apply.py",
}

AUTHORITY_BOUNDARY = {
    "owner_archive_approval": "Randall 2026-05-30 21:40 MST: Yes, proceed. Approval to archive.",
    "move_only": True,
    "delete_allowed": False,
    "archive_active_script_dependencies_allowed": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def resolve_workspace(path_text: str) -> Path:
    path = (ROOT / path_text).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes workspace: {path_text}")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                files.append(path)
    return sorted(set(files), key=lambda p: rel(p).lower())


def references_for(candidate: Path, scan_files: list[Path]) -> dict[str, Any]:
    rel_path = rel(candidate)
    win_path = rel_path.replace("/", "\\")
    needles = {rel_path, win_path, candidate.name}
    references: list[dict[str, Any]] = []
    for path in scan_files:
        if path.resolve() == candidate.resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not any(needle in text for needle in needles):
            continue
        parts = path.relative_to(ROOT).parts
        path_rel = rel(path)
        is_script_dependency = bool(
            parts
            and parts[0] == "scripts"
            and path.suffix.lower() == ".py"
            and path_rel not in NON_BLOCKING_SCRIPT_REFERENCES
        )
        is_control_surface = path_rel in {"TOOLS.md", "AGENTS.md", "MEMORY.md"} or (
            len(parts) >= 2 and parts[0] == "06. Playbooks" and parts[1] == "Active Workflows.md"
        )
        non_blocking_history = bool(parts and parts[0] in NON_BLOCKING_ROOT_PARTS)
        references.append({
            "path": path_rel,
            "script_dependency": is_script_dependency,
            "control_surface": is_control_surface,
            "non_blocking_history": non_blocking_history,
        })
    blocking = [
        row for row in references
        if row["script_dependency"] or row["control_surface"]
    ]
    return {
        "total_reference_count": len(references),
        "blocking_reference_count": len(blocking),
        "references": references,
        "blocking_references": blocking,
    }


def destination_for(source: Path) -> Path:
    return ARCHIVE_ROOT / rel(source)


def move_candidate(candidate: dict[str, Any], scan_files: list[Path], apply: bool) -> dict[str, Any]:
    source = resolve_workspace(str(candidate["path"]))
    dest = destination_for(source)
    row: dict[str, Any] = {
        "source": rel(source),
        "destination": rel(dest),
        "candidate_class": candidate.get("candidate_class"),
        "exists_before": source.exists(),
        "eligible": False,
        "moved": False,
        "already_archived": False,
        "verified": False,
        "blocked_reason": None,
        "rollback": f"Move {rel(dest)} back to {rel(source)}",
    }
    if not source.exists():
        if dest.exists() and dest.is_file():
            row["already_archived"] = True
            row["verified"] = True
            row["destination_exists_after"] = True
            row["destination_sha256_existing"] = sha256(dest)
            row["bytes"] = dest.stat().st_size
            return row
        row["blocked_reason"] = "source_missing"
        return row
    if not source.is_file():
        row["blocked_reason"] = "source_not_file"
        return row
    refs = references_for(source, scan_files)
    row["reference_scan"] = refs
    if refs["blocking_reference_count"]:
        row["blocked_reason"] = "blocking_script_or_control_surface_reference"
        return row
    if dest.exists():
        row["blocked_reason"] = "destination_exists"
        row["destination_sha256_existing"] = sha256(dest)
        return row

    before_hash = sha256(source)
    row["sha256_before"] = before_hash
    row["bytes"] = source.stat().st_size
    row["eligible"] = True
    if not apply:
        row["verified"] = True
        row["dry_run"] = True
        return row

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))
    after_hash = sha256(dest)
    row["sha256_after"] = after_hash
    row["moved"] = True
    row["source_exists_after"] = source.exists()
    row["destination_exists_after"] = dest.exists()
    row["verified"] = after_hash == before_hash and not source.exists() and dest.exists()
    return row


def build_report(apply: bool) -> dict[str, Any]:
    plan = load_json(PLAN_PATH)
    scan_files = iter_scan_files()
    rows = [move_candidate(candidate, scan_files, apply) for candidate in plan.get("candidates", [])]
    errors = [
        row for row in rows
        if row.get("eligible") and (row.get("moved") != apply or not row.get("verified"))
    ]
    moved = [row for row in rows if row.get("moved")]
    already_archived = [row for row in rows if row.get("already_archived")]
    blocked = [row for row in rows if row.get("blocked_reason")]
    return {
        "schema_version": "finance_sql_canon_legacy_42_archive_apply_report.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "dry_run": not apply,
        "plan_path": rel(PLAN_PATH),
        "archive_root": rel(ARCHIVE_ROOT),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(rows),
            "eligible_count": sum(1 for row in rows if row.get("eligible")),
            "moved_count": len(moved),
            "already_archived_count": len(already_archived),
            "blocked_count": len(blocked),
            "error_count": len(errors),
        },
        "rows": rows,
        "blocked": blocked,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Move eligible files into archive.")
    parser.add_argument("--write", action="store_true", help="Write apply report.")
    parser.add_argument("--validate", action="store_true", help="Fail when eligible moves are not verified.")
    args = parser.parse_args()

    report = build_report(apply=args.apply)
    if args.write:
        atomic_write_json(REPORT_PATH, report)
    print(json.dumps({
        "status": report["status"],
        "dry_run": report["dry_run"],
        "candidate_count": report["summary"]["candidate_count"],
        "eligible_count": report["summary"]["eligible_count"],
        "moved_count": report["summary"]["moved_count"],
        "already_archived_count": report["summary"]["already_archived_count"],
        "blocked_count": report["summary"]["blocked_count"],
        "error_count": report["summary"]["error_count"],
        "report": rel(REPORT_PATH) if args.write else None,
    }, indent=2))
    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
