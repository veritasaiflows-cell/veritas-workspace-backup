#!/usr/bin/env python3
"""Read-only workspace archive suggester.

This script proposes cleanup/archive candidates only. It never moves, deletes, or
rewrites source files. Suggestions are advisory and require owner approval before
any apply step exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
JSON_REPORT = TMP / "archive-suggestions.json"
MD_REPORT = TMP / "archive-suggestions.md"

EXCLUDED_SCAN_DIRS = {
    ".clawhub",
    ".git",
    ".obsidian",
    ".openclaw",
    "__pycache__",
    "migration-backups",
}
TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".csv",
    ".html",
    ".yaml",
    ".yml",
}
PROTECTED_ROOTS = {
    "01. Dashboards",
    "02. Markets",
    "03. Portfolio",
    "04. Research",
    "05. Intelligence",
    "06. Playbooks",
    "07. Risk",
    "08. Audits",
    "09. Archive",
    "data",
    "memory",
    "scripts",
    "skills",
}


@dataclass
class Suggestion:
    path: str
    kind: str
    recommendation: str
    proposed_destination: str | None
    confidence: str
    owner_approval_required: bool
    apply_allowed: bool
    reference_count: int
    blockers: list[str]
    evidence: list[str]
    sha256: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def iter_text_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in EXCLUDED_SCAN_DIRS for part in rel_parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def reference_count(candidate: Path) -> int:
    """Count text-file references to a basename or relative path.

    This is intentionally conservative. A positive count blocks any automatic
    archive recommendation; a zero count is still only advisory.
    """
    rel_path = rel(candidate)
    basename = candidate.name
    needles = {rel_path, rel_path.replace("/", "\\\\"), basename}
    count = 0
    for path in iter_text_files():
        if path == candidate:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            count += 1
    return count


def root_backups_suggestion() -> list[Suggestion]:
    path = ROOT / "backups"
    if not path.exists():
        return []
    refs = reference_count(path)
    blockers = ["root `backups/` is not documented as an active root entitlement"]
    if refs:
        blockers.append("inbound references found; inspect before moving")
    return [
        Suggestion(
            path="backups/",
            kind="undocumented_root_backup_surface",
            recommendation="classify as active migration backup, archive under `09. Archive/`, or remove only after owner approval and reference check",
            proposed_destination="09. Archive/backups - Archived/",
            confidence="medium" if refs == 0 else "low",
            owner_approval_required=True,
            apply_allowed=False,
            reference_count=refs,
            blockers=blockers,
            evidence=["workspace boundary audit reports root `backups/` as undocumented"],
        )
    ]


def tmp_python_suggestions() -> list[Suggestion]:
    if not TMP.exists():
        return []
    suggestions: list[Suggestion] = []
    for path in sorted(TMP.glob("*.py")):
        refs = reference_count(path)
        blockers = ["executable helper lives in generated-artifact tmp/ surface"]
        if refs:
            blockers.append("inbound references found; promote/archive only after inspecting current use")
        suggestions.append(
            Suggestion(
                path=rel(path),
                kind="tmp_executable_helper",
                recommendation="promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval",
                proposed_destination=f"09. Archive/tmp-python-helpers - Archived/{path.name}",
                confidence="medium" if refs == 0 else "low",
                owner_approval_required=True,
                apply_allowed=False,
                reference_count=refs,
                blockers=blockers,
                evidence=["tmp/ should hold generated artifacts and staged outputs, not durable executable helpers"],
                sha256=sha256_file(path),
            )
        )
    return suggestions


def cache_suggestions() -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    for cache in sorted(ROOT.rglob("__pycache__")):
        parts = cache.relative_to(ROOT).parts
        if any(part in {".git", ".obsidian", ".openclaw", ".clawhub"} for part in parts):
            continue
        suggestions.append(
            Suggestion(
                path=rel(cache) + "/",
                kind="runtime_cache",
                recommendation="safe cleanup candidate after confirming no process is relying on it; do not treat as operating evidence",
                proposed_destination=None,
                confidence="medium",
                owner_approval_required=True,
                apply_allowed=False,
                reference_count=0,
                blockers=["deletion is destructive; keep as approval-gated even for cache cleanup"],
                evidence=["Python runtime cache is rebuildable and non-canonical"],
            )
        )
    return suggestions


def tmp_markdown_report_suggestions(limit: int = 50) -> list[Suggestion]:
    if not TMP.exists():
        return []
    suggestions: list[Suggestion] = []
    for path in sorted(TMP.glob("*.md"))[:limit]:
        refs = reference_count(path)
        recommendation = "if decision-grade, promote to 08. Audits/; if proof-only residue, archive after owner approval"
        suggestions.append(
            Suggestion(
                path=rel(path),
                kind="tmp_markdown_report",
                recommendation=recommendation,
                proposed_destination=f"09. Archive/tmp-reports - Archived/{path.name}",
                confidence="low" if refs else "medium",
                owner_approval_required=True,
                apply_allowed=False,
                reference_count=refs,
                blockers=["tmp Markdown reports may still be live handoff/proof artifacts", "manual classification required"],
                evidence=["audit recommended classifying tmp reports before any broad archival"],
                sha256=sha256_file(path),
            )
        )
    return suggestions


def build_report(include_tmp_md: bool = False) -> dict:
    suggestions = root_backups_suggestion() + tmp_python_suggestions() + cache_suggestions()
    if include_tmp_md:
        suggestions += tmp_markdown_report_suggestions()
    by_kind: dict[str, int] = {}
    for suggestion in suggestions:
        by_kind[suggestion.kind] = by_kind.get(suggestion.kind, 0) + 1
    return {
        "status": "review_required" if suggestions else "ok",
        "generated_at_utc": utc_now(),
        "script": "scripts/archive_suggester.py",
        "apply_allowed": False,
        "moves_performed": False,
        "owner_approval_required": True,
        "canonical_truth_note": "This is a read-only cleanup suggestion report. It is not an archive apply plan and must not override source notes, queue surfaces, or owner approval boundaries.",
        "protected_surfaces": sorted(PROTECTED_ROOTS),
        "counts": {
            "suggestions": len(suggestions),
            "by_kind": by_kind,
            "with_inbound_references": sum(1 for suggestion in suggestions if suggestion.reference_count > 0),
        },
        "suggestions": [asdict(suggestion) for suggestion in suggestions],
    }


def write_markdown(report: dict) -> None:
    lines = [
        "# Workspace Archive Suggestions",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        "## Verdict",
        "",
        f"- Status: `{report['status']}`",
        "- This is read-only. No files were moved, deleted, or rewritten.",
        "- Owner approval is required before any archive/apply action.",
        "- Canonical finance notes, active workflow surfaces, durable `data/` state, scripts, skills, and memory are protected from automatic archive.",
        "",
        "## Counts",
        "",
        f"- Suggestions: {report['counts']['suggestions']}",
        f"- Suggestions with inbound references: {report['counts']['with_inbound_references']}",
        "",
        "## Suggestions",
        "",
    ]
    for suggestion in report["suggestions"]:
        lines.extend([
            f"### `{suggestion['path']}`",
            f"- Kind: `{suggestion['kind']}`",
            f"- Confidence: `{suggestion['confidence']}`",
            f"- Reference count: `{suggestion['reference_count']}`",
            f"- Recommendation: {suggestion['recommendation']}",
            f"- Proposed destination: `{suggestion['proposed_destination']}`" if suggestion["proposed_destination"] else "- Proposed destination: none / cleanup-only candidate",
            f"- Apply allowed: `{suggestion['apply_allowed']}`",
            "- Blockers: " + "; ".join(suggestion["blockers"]),
            "",
        ])
    MD_REPORT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write read-only archive suggestions for workspace cleanup.")
    parser.add_argument("--include-tmp-md", action="store_true", help="Also classify tmp/*.md reports as manual review suggestions.")
    args = parser.parse_args()
    report = build_report(include_tmp_md=args.include_tmp_md)
    TMP.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
