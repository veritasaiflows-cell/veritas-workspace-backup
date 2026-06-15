#!/usr/bin/env python3
"""Scan the workspace for deletion candidates without deleting anything.

This is a readiness packet only. It separates low-risk generated noise from
archived-file future-delete candidates and protected surfaces. Deletion remains
blocked until a separate exact owner approval and delete apply helper name a
specific class or file set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REPORT_PATH = TMP / "full-workspace-delete-readiness.json"
ARCHIVE_DELETE_PLAN = TMP / "archive-delete-readiness-plan.json"

AUTHORITY_BOUNDARY = {
    "plan_only": True,
    "delete_allowed_now": False,
    "delete_apply_allowed_by_this_script": False,
    "requires_separate_exact_owner_delete_approval": True,
    "config_auth_channel_runtime_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

SKIP_DIR_NAMES = {
    ".git",
    ".obsidian",
    ".openclaw",
    ".clawhub",
    ".claude",
    "node_modules",
}

PROTECTED_TOP_LEVEL = {
    "01. Dashboards",
    "02. Markets",
    "03. Portfolio",
    "04. Research",
    "05. Intelligence",
    "06. Playbooks",
    "07. Risk",
    "08. Audits",
    "data",
    "memory",
    "migration-backups",
    "scripts",
    "skills",
    "state",
    "backups",
    ".backups",
}

PROTECTED_ROOT_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "Continuity Protocol.md",
    "GEMINI.md",
    "HEARTBEAT.md",
    "Home.md",
    "IDENTITY.md",
    "MEMORY.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
    ".gitignore",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def iter_files() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for filename in filenames:
            path = current / filename
            try:
                path.relative_to(ROOT)
            except ValueError:
                continue
            files.append(path)
    return sorted(files, key=lambda path: rel(path).lower())


def iter_empty_dirs() -> list[Path]:
    empties: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT, topdown=False):
        current = Path(dirpath)
        if current == ROOT or any(part in SKIP_DIR_NAMES for part in current.relative_to(ROOT).parts):
            continue
        try:
            if not any(current.iterdir()):
                empties.append(current)
        except OSError:
            continue
    return sorted(empties, key=lambda path: rel(path).lower())


def root_part(path: Path) -> str:
    parts = path.relative_to(ROOT).parts
    return parts[0] if parts else ""


def classify_file(path: Path) -> tuple[str, str, list[str]]:
    relative = rel(path)
    parts = path.relative_to(ROOT).parts
    name = path.name
    suffix = path.suffix.lower()

    if len(parts) == 1 and name in PROTECTED_ROOT_FILES:
        return "protected", "root_control_file", ["root control/doctrine file"]
    if "__pycache__" in parts and suffix in {".pyc", ".pyo"}:
        return "delete_ready_after_exact_approval", "python_bytecode_cache", [
            "generated Python bytecode",
            "rebuildable",
            "not operating evidence",
        ]
    if name in {".DS_Store", "Thumbs.db", "desktop.ini"}:
        return "delete_ready_after_exact_approval", "os_metadata_cache", [
            "OS metadata cache",
            "rebuildable local noise",
        ]
    if root_part(path) in PROTECTED_TOP_LEVEL and root_part(path) != "09. Archive":
        return "protected", "active_domain_or_state_surface", ["active domain/state/data/memory/skill surface"]

    if suffix in {".tmp", ".temp"} or name.endswith(".tmp"):
        return "delete_ready_after_exact_approval", "temporary_file", [
            "temporary file extension",
            "requires hash packet and no active reference before deletion",
        ]
    if suffix in {".log"} and root_part(path) == "tmp":
        return "delete_ready_after_exact_approval", "tmp_log_file", [
            "generated tmp log",
            "not canonical truth",
        ]

    if relative.startswith("09. Archive/"):
        return "future_delete_after_retention_restore_and_exact_approval", "archived_file", [
            "archived material, not active workspace surface",
            "requires retention window and restore drill before deletion",
        ]

    if root_part(path) == "tmp":
        if suffix in {".html", ".pdf"}:
            return "retain_or_archive_first", "tmp_presentation_artifact", [
                "presentation artifact may be consumed by Veritas/PM/control surfaces",
                "archive/retention decision required before deletion",
            ]
        if suffix == ".md":
            return "blocked_or_archive_first", "tmp_markdown_residue", [
                "remaining tmp Markdown was not eligible under JSON-peer archive rule",
                "archive or reference retarget required before deletion",
            ]
        return "retain_tmp_or_lifecycle_review", "tmp_machine_artifact", [
            "generated machine artifact",
            "may be current proof/state/input for validators or dashboards",
        ]

    return "manual_review_required", "unclassified_file", ["outside automatic delete readiness classes"]


def classify_empty_dir(path: Path) -> tuple[str, str, list[str]]:
    top = root_part(path)
    if top in SKIP_DIR_NAMES or top in {".claude", ".openclaw", ".obsidian", ".clawhub"}:
        return "protected", "tool_runtime_empty_dir", ["tool/runtime directory"]
    parts = path.relative_to(ROOT).parts
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "references":
        return "protected", "skill_references_scaffold_empty_dir", [
            "empty skill references scaffold",
            "preserve unless a dedicated skill-maintenance pass removes it",
        ]
    if top in {"tmp", "09. Archive"}:
        return "delete_ready_after_exact_approval", "empty_generated_or_archive_dir", [
            "empty directory",
            "no file content loss",
        ]
    return "manual_review_required", "empty_dir_manual_review", ["empty directory outside generated/archive roots"]


def archive_delete_summary() -> dict[str, Any]:
    data = load_json(ARCHIVE_DELETE_PLAN)
    if not isinstance(data, dict):
        return {"status": "missing"}
    return {
        "status": data.get("status"),
        "summary": data.get("summary"),
        "path": rel(ARCHIVE_DELETE_PLAN),
    }


def build_report() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in iter_files():
        posture, candidate_class, evidence = classify_file(path)
        stat = path.stat()
        rows.append({
            "path": rel(path),
            "kind": "file",
            "bytes": stat.st_size,
            "sha256": sha256(path),
            "posture": posture,
            "candidate_class": candidate_class,
            "delete_allowed_now": False,
            "requirements_before_delete": requirements_for(posture, candidate_class),
            "evidence": evidence,
        })
    for path in iter_empty_dirs():
        posture, candidate_class, evidence = classify_empty_dir(path)
        rows.append({
            "path": rel(path),
            "kind": "empty_dir",
            "bytes": None,
            "sha256": None,
            "posture": posture,
            "candidate_class": candidate_class,
            "delete_allowed_now": False,
            "requirements_before_delete": requirements_for(posture, candidate_class),
            "evidence": evidence,
        })

    by_posture: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for row in rows:
        by_posture[row["posture"]] = by_posture.get(row["posture"], 0) + 1
        by_class[row["candidate_class"]] = by_class.get(row["candidate_class"], 0) + 1

    ready = [row for row in rows if row["posture"] == "delete_ready_after_exact_approval"]
    future = [row for row in rows if row["posture"] == "future_delete_after_retention_restore_and_exact_approval"]
    blocked = [
        row for row in rows
        if row["posture"] in {"blocked_or_archive_first", "retain_or_archive_first", "retain_tmp_or_lifecycle_review", "manual_review_required"}
    ]

    return {
        "schema_version": "full_workspace_delete_readiness.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_owner_delete_review_no_delete_applied",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "rows_scanned": len(rows),
            "delete_ready_after_exact_approval_count": len(ready),
            "future_archive_delete_after_retention_count": len(future),
            "blocked_or_review_count": len(blocked),
            "delete_allowed_now_count": 0,
            "by_posture": dict(sorted(by_posture.items())),
            "by_candidate_class": dict(sorted(by_class.items())),
        },
        "archive_delete_plan": archive_delete_summary(),
        "delete_ready_rows": ready,
        "future_archive_delete_rows": future,
        "blocked_or_review_rows": blocked,
        "rows": rows,
    }


def requirements_for(posture: str, candidate_class: str) -> list[str]:
    if posture == "delete_ready_after_exact_approval":
        return [
            "separate exact owner delete approval names this class or file set",
            "delete apply helper verifies path stays inside workspace",
            "post-delete workspace boundary and artifact validators pass",
        ]
    if posture == "future_delete_after_retention_restore_and_exact_approval":
        return [
            "retention window selected",
            "restore drill proves archived file can return to original path",
            "replacement proof remains live if applicable",
            "separate exact owner delete approval names this archive class or file set",
            "post-delete validators pass",
        ]
    if candidate_class in {"tmp_markdown_residue", "tmp_presentation_artifact", "tmp_machine_artifact"}:
        return [
            "prove no active script/control-surface consumption",
            "archive first when human-readable or presentation-facing",
            "retain current JSON/SQLite proof when validator/control surfaces depend on it",
        ]
    return ["manual review required before any delete action"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(REPORT_PATH, report)
    summary = {
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT_PATH) if args.write else None,
    }
    print(json.dumps(report if args.pretty else summary, indent=2, sort_keys=True))
    if args.validate and report["summary"]["delete_allowed_now_count"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
