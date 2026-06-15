#!/usr/bin/env python3
"""Classify remaining archived files for a manual delete decision packet."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "09. Archive"
TMP = ROOT / "tmp"
REPORT = TMP / "archive-manual-delete-review.json"

TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".json5",
    ".jsx",
    ".md",
    ".ps1",
    ".py",
    ".sql",
    ".txt",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}

RETAIN_PREFIXES = (
    "09. Archive/Finance Canon/",
    "09. Archive/WF78 Finance SQL Canon Legacy 42 Proof/",
)

GENERATED_RESIDUE_PREFIXES = (
    "09. Archive/Auto Archive - Generated Residue/",
    "09. Archive/Scripts and Tmp Cleanup - Archived/",
    "09. Archive/Tmp Referenced Archive Candidates - Archived/",
    "09. Archive/tmp-python-helpers - Archived/",
    "09. Archive/tmp-helper-residue-20260529/",
    "09. Archive/tmp-helper-scripts - Archived/",
    "09. Archive/DB Lifecycle - Archived/",
    "09. Archive/Archive Logs/",
    "09. Archive/entry-band-reports - Archived/",
    "09. Archive/temp-skill-inspect - Archived/",
)

HISTORICAL_BUSINESS_PREFIXES = (
    "09. Archive/01. Dashboards - Archived/",
    "09. Archive/02. Opportunities - Archived/",
    "09. Archive/03. Offers - Archived/",
    "09. Archive/04. Departments - Archived/",
    "09. Archive/05. Plans - Archived/",
    "09. Archive/06. Project Continuity - Archived/",
    "09. Archive/06. Training Documents - Archived/",
    "09. Archive/08. Audits - Archived/",
    "09. Archive/Broad Workspace Archive - Owner Approved/",
    "09. Archive/Evening Review - Archived/",
    "09. Archive/Manual IC Prompts - Archived/",
    "09. Archive/templates - Archived/",
)

RESEARCH_DELIVERABLE_PREFIXES = (
    "09. Archive/06. Research Deliverables/",
)

CONTINUITY_PREFIXES = (
    "09. Archive/Project Continuity/",
    "09. Archive/memory - Archived/",
    "09. Archive/Bootstrap Audit Backups ",
)

EXCLUDE_REF_SCAN_DIRS = {
    ".git",
    ".obsidian",
    ".openclaw",
    ".clawhub",
    ".claude",
    "node_modules",
    "09. Archive",
    "tmp",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def archive_files() -> list[Path]:
    return sorted((p for p in ARCHIVE.rglob("*") if p.is_file()), key=lambda p: rel(p).lower())


def iter_live_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        try:
            parts = path.relative_to(ROOT).parts
        except ValueError:
            continue
        if not path.is_file():
            continue
        if any(part in EXCLUDE_REF_SCAN_DIRS for part in parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def build_reference_index(needles: list[str]) -> dict[str, list[str]]:
    hits = {needle: [] for needle in needles}
    if not needles:
        return hits
    live_files = iter_live_text_files()
    for source in live_files:
        try:
            text = source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in needles:
            if needle in text:
                hits[needle].append(rel(source))
    return hits


def group_name(relative: str) -> str:
    parts = relative.split("/")
    return parts[1] if len(parts) > 1 else ""


def startswith_any(value: str, prefixes: tuple[str, ...]) -> bool:
    return any(value.startswith(prefix) for prefix in prefixes)


def classify(relative: str, live_refs: list[str]) -> tuple[str, str, list[str]]:
    if live_refs:
        return "retain_referenced_or_adjudicate_first", "live_reference_present", [
            "live non-archive files still reference this archive path",
            "retarget references or explicitly accept broken provenance before deletion",
        ]
    if startswith_any(relative, RETAIN_PREFIXES):
        return "retain_for_now", "finance_or_sql_transition_proof", [
            "finance-canon or SQL transition proof remains useful for provenance",
        ]
    if startswith_any(relative, GENERATED_RESIDUE_PREFIXES):
        return "phase_1_delete_candidate_after_exact_approval", "generated_residue_archive", [
            "archived generated residue or cleanup log",
            "no live reference found",
        ]
    if startswith_any(relative, HISTORICAL_BUSINESS_PREFIXES):
        return "phase_2_delete_candidate_after_owner_business_history_decision", "historical_business_archive", [
            "old business/consulting/history archive",
            "deletion is a human memory/history decision, not a technical cleanup decision",
        ]
    if startswith_any(relative, RESEARCH_DELIVERABLE_PREFIXES):
        return "phase_3_delete_or_export_candidate_after_owner_decision", "binary_research_deliverable", [
            "old binary research deliverable",
            "consider external export or explicit discard before deletion",
        ]
    if startswith_any(relative, CONTINUITY_PREFIXES):
        return "phase_4_delete_candidate_after_continuity_reconciliation", "archived_continuity_or_memory", [
            "archived continuity/memory surface",
            "delete only after durable continuity has been reconciled",
        ]
    return "manual_review_required", "unclassified_archive", ["no safe class matched"]


def build_report() -> dict[str, Any]:
    files = archive_files()
    relatives = [rel(path) for path in files]
    ref_index = build_reference_index(relatives)
    rows = []
    for path, relative in zip(files, relatives):
        refs = ref_index.get(relative, [])
        posture, cls, rationale = classify(relative, refs)
        rows.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "top_archive_group": group_name(relative),
            "posture": posture,
            "candidate_class": cls,
            "live_reference_count": len(refs),
            "live_references": refs[:20],
            "delete_allowed_now": False,
            "rationale": rationale,
        })
    by_posture = Counter(row["posture"] for row in rows)
    by_class = Counter(row["candidate_class"] for row in rows)
    by_group = Counter(row["top_archive_group"] for row in rows)
    return {
        "schema_version": "archive_manual_delete_review.v1",
        "generated_at_utc": utc_now(),
        "status": "manual_review_packet_ready_no_delete_authority",
        "authority_boundary": {
            "report_only": True,
            "delete_allowed_now": False,
            "requires_separate_exact_owner_delete_approval": True,
            "config_auth_channel_runtime_mutation_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "trade_or_account_action_allowed": False,
            "money_movement_allowed": False,
        },
        "summary": {
            "archive_files_scanned": len(rows),
            "by_posture": dict(sorted(by_posture.items())),
            "by_candidate_class": dict(sorted(by_class.items())),
            "top_archive_groups": dict(by_group.most_common()),
            "delete_allowed_now_count": 0,
        },
        "recommended_phases": [
            "Phase 1: generated-residue archive deletion only after exact approval and restore-proof apply.",
            "Phase 2: historical business/archive deletion only after Randall explicitly chooses to discard that history.",
            "Phase 3: binary research deliverables: either export outside workspace or explicitly discard.",
            "Phase 4: archived continuity/memory: reconcile durable continuity first, then delete only explicitly selected stale copies.",
            "Retain for now: finance-canon/SQL transition proof and any archive file with live references.",
        ],
        "rows": rows,
    }


def main() -> int:
    report = build_report()
    atomic_write_json(REPORT, report)
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
