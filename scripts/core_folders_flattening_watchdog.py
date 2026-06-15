#!/usr/bin/env python3
"""Classify and monitor flattening candidates in folders 01-05.

This is the watchdog/control packet for thinning human-facing finance folders.
It is conservative: it proposes archive candidates and compression targets, but
does not move or delete files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REPORT_PATH = TMP / "core-folders-flattening-watchdog.json"
TARGET_ROOTS = [
    "01. Dashboards",
    "02. Markets",
    "03. Portfolio",
    "04. Research",
    "05. Intelligence",
]
ARCHIVE_ROOT = "09. Archive/Core Finance Human Surfaces/2026-05-30"
TEXT_EXTENSIONS = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".ps1"}
SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / "06. Playbooks",
    ROOT / "skills",
    ROOT / "TOOLS.md",
    ROOT / "AGENTS.md",
    ROOT / "MEMORY.md",
]
CONTROL_SURFACE_FILES = {"TOOLS.md", "AGENTS.md", "MEMORY.md", "SOUL.md", "USER.md", "HEARTBEAT.md"}

AUTHORITY_BOUNDARY = {
    "watchdog_only": True,
    "archive_candidate_packet": True,
    "archive_apply_allowed_by_this_script": False,
    "delete_allowed": False,
    "broad_delete_planned_only": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

DATED_RE = re.compile(r"(?P<date>20\d{2}-\d{2}-\d{2})")
WEEK_RE = re.compile(r"(?P<week>20\d{2}-W\d{2})")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for root_name in TARGET_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files, key=lambda p: rel(p).lower())


def iter_scan_texts() -> list[tuple[Path, str]]:
    texts: list[tuple[Path, str]] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        scan_files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in scan_files:
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                texts.append((path, path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    return texts


def build_reference_map(paths: list[Path], scan_texts: list[tuple[Path, str]]) -> dict[str, dict[str, Any]]:
    if not paths:
        return {}
    needle_to_rel: dict[str, str] = {}
    for path in paths:
        rel_path = rel(path)
        needle_to_rel[rel_path] = rel_path
        needle_to_rel[rel_path.replace("/", "\\")] = rel_path
    pattern = re.compile("|".join(re.escape(needle) for needle in sorted(needle_to_rel, key=len, reverse=True)))
    refs_by_target: dict[str, dict[str, dict[str, Any]]] = {rel(path): {} for path in paths}
    for scan_path, text in scan_texts:
        matches = set(needle_to_rel[match.group(0)] for match in pattern.finditer(text))
        if not matches:
            continue
        scan_rel = rel(scan_path)
        parts = scan_path.relative_to(ROOT).parts
        row = {
            "path": scan_rel,
            "script_dependency": bool(parts and parts[0] == "scripts" and scan_path.suffix.lower() == ".py"),
            "control_surface": scan_path.name in CONTROL_SURFACE_FILES or scan_rel == "06. Playbooks/Active Workflows.md",
        }
        for matched in matches:
            if matched != scan_rel:
                refs_by_target[matched][scan_rel] = row
    result: dict[str, dict[str, Any]] = {}
    for target, rows in refs_by_target.items():
        refs = sorted(rows.values(), key=lambda row: row["path"].lower())
        blocking = [row for row in refs if row["script_dependency"] or row["control_surface"]]
        result[target] = {
            "total_reference_count": len(refs),
            "blocking_reference_count": len(blocking),
            "references": refs,
            "blocking_references": blocking,
        }
    return result


def dated_key(path: Path) -> str | None:
    text = path.name
    match = DATED_RE.search(text)
    if match:
        return match.group("date")
    match = WEEK_RE.search(text)
    if match:
        return match.group("week")
    return None


def latest_by_group(files: list[Path], group_prefix: str, keep: int) -> set[str]:
    grouped: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for path in files:
        if not rel(path).startswith(group_prefix):
            continue
        key = dated_key(path)
        if key:
            grouped[path.parent.as_posix()].append((key, path))
    kept: set[str] = set()
    for rows in grouped.values():
        for _key, path in sorted(rows, key=lambda item: item[0], reverse=True)[:keep]:
            kept.add(rel(path))
    return kept


def classify(path: Path, keep_latest: set[str]) -> tuple[str, str, bool, list[str]]:
    rel_path = rel(path)
    name = path.name
    parts = path.relative_to(ROOT).parts
    evidence: list[str] = []
    generated_stub = False
    if path.suffix.lower() == ".md":
        try:
            generated_stub = "GENERATED CORE LIVE SURFACE STUB" in path.read_text(encoding="utf-8", errors="ignore")[:600]
        except OSError:
            generated_stub = False

    if parts[0] == "01. Dashboards":
        if name in {"Executive Brief.md", "Next Actions.md", "This Week.md", "Today.md"}:
            return "keep_live", "current_dashboard_surface", False, ["current dashboard/control note"]
        if "Review-Only Briefs" in parts and name == "README.md":
            return "archive_candidate", "dashboard_stub_readme_superseded", True, ["stub README superseded by Executive Brief routing surface"]
        if name == "README.md":
            return "keep_live", "dashboard_readme", False, ["readme route surface"]
        if rel_path in keep_latest:
            return "keep_live", "recent_dashboard_snapshot", False, ["latest retained snapshot in its dashboard group"]
        if dated_key(path):
            return "archive_candidate", "dated_dashboard_snapshot_superseded", True, ["dated dashboard snapshot older than retained latest set"]
        return "manual_review", "dashboard_other", False, evidence

    if parts[0] == "02. Markets":
        if name in {"Macro Regime Dashboard.md", "Regime Scoring Matrix.md"}:
            return "keep_live", "current_macro_surface", False, ["current macro/regime surface"]
        if rel_path in keep_latest:
            return "keep_live", "recent_macro_snapshot", False, ["latest retained macro snapshot"]
        if dated_key(path):
            return "archive_candidate", "dated_macro_snapshot_superseded", True, ["older macro snapshot"]
        return "manual_review", "market_other", False, evidence

    if parts[0] == "03. Portfolio":
        if name in {"Investor Profile.md", "Model Portfolio.md", "Portfolio Snapshot.md"}:
            return "keep_live", "portfolio_owner_truth", False, ["owner/model/current portfolio truth"]
        if generated_stub and name in {"Execution Board.md", "Rebalance Log.md"}:
            return "keep_live", "compressed_live_stub", False, ["compressed live stub with replacement proof and archived source-open original"]
        if name == "Execution Board.md":
            return "compress_live", "large_current_portfolio_board", False, ["current operating board should be compressed after extraction, not archived blind"]
        if name == "Deployment Build Executive Packet - 2026-05-17.md":
            return "archive_candidate", "superseded_portfolio_build_packet", True, ["dated deployment build packet superseded by current portfolio surfaces and daily memory"]
        if name == "Rebalance Log.md":
            return "compress_live", "portfolio_history_log", False, ["approval/history surface; plan migration before archive"]
        return "manual_review", "portfolio_other", False, evidence

    if parts[0] == "04. Research":
        if name in {"Call Log.md", "Coverage and Watchlist.md", "Investment Thesis Template.md"}:
            return "keep_live", "active_research_surface", False, ["active research/call/template surface"]
        if dated_key(path):
            return "archive_candidate", "dated_research_review_superseded", True, ["dated research review, likely summarized by current coverage or workflow continuity"]
        return "manual_review", "research_other", False, evidence

    if parts[0] == "05. Intelligence":
        if name in {"Event Calendar.md", "Weekly Intelligence Brief.md", "Weekly Positioning Review.md"}:
            return "keep_live", "current_intelligence_surface", False, ["current intelligence/event/positioning surface"]
        if name == "Weekly Intelligence Brief - machine.md":
            return "archive_candidate", "machine_weekly_brief_superseded", True, ["machine mirror superseded by human weekly brief/current artifacts"]
        if "Earnings" in parts and generated_stub:
            return "keep_live", "compressed_earnings_index_stub", False, ["earnings scorecards migrated to structured proof and archived originals"]
        if "Earnings" in parts:
            return "compress_live", "earnings_scorecard_source_open_note", False, ["source-open earnings narrative; compress/migrate before archive"]
        return "manual_review", "intelligence_other", False, evidence

    return "manual_review", "outside_target", False, evidence


def build_report() -> dict[str, Any]:
    files = iter_target_files()
    keep_latest = set()
    keep_latest |= latest_by_group(files, "01. Dashboards/Daily Executive Summary/", 1)
    keep_latest |= latest_by_group(files, "01. Dashboards/Post-Market Snapshot/", 1)
    keep_latest |= latest_by_group(files, "01. Dashboards/Pre-Market Snapshot/", 1)
    keep_latest |= latest_by_group(files, "01. Dashboards/Review-Only Briefs/", 0)
    keep_latest |= latest_by_group(files, "02. Markets/Weekly Macro Snapshot/", 1)
    refs = build_reference_map(files, iter_scan_texts())

    rows: list[dict[str, Any]] = []
    for path in files:
        posture, candidate_class, archive_candidate, evidence = classify(path, keep_latest)
        ref_scan = refs.get(rel(path), {
            "total_reference_count": 0,
            "blocking_reference_count": 0,
            "references": [],
            "blocking_references": [],
        })
        eligible = archive_candidate and ref_scan["blocking_reference_count"] == 0
        rows.append({
            "path": rel(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "folder": path.relative_to(ROOT).parts[0],
            "posture": posture,
            "candidate_class": candidate_class,
            "archive_candidate": archive_candidate,
            "eligible_for_move_only_archive": eligible,
            "blocked_reason": None if eligible else (
                "not_archive_candidate" if not archive_candidate else "blocking_script_or_control_surface_reference"
            ),
            "reference_scan": ref_scan,
            "proposed_destination": f"{ARCHIVE_ROOT}/{rel(path)}" if archive_candidate else None,
            "evidence": evidence,
            "rollback": f"Move {ARCHIVE_ROOT}/{rel(path)} back to {rel(path)}",
        })

    by_posture = defaultdict(int)
    by_folder = defaultdict(int)
    for row in rows:
        by_posture[row["posture"]] += 1
        by_folder[row["folder"]] += 1

    eligible = [row for row in rows if row["eligible_for_move_only_archive"]]
    blocked = [row for row in rows if row["archive_candidate"] and not row["eligible_for_move_only_archive"]]
    return {
        "schema_version": "core_folders_flattening_watchdog.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_archive_microbatch" if eligible else "no_archive_candidates_ready",
        "target_roots": TARGET_ROOTS,
        "archive_root": ARCHIVE_ROOT,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "phased_approach": [
            "Phase 1: archive dated/generated/superseded dashboard, macro, research, and machine intelligence notes with no active references.",
            "Phase 2: compress live large notes such as Execution Board and Coverage/Watchlist into current-state summaries backed by SQL/JSON.",
            "Phase 3: migrate durable inventory/status/proof state into SQL/JSON lookups, retaining human notes only for owner truth, judgment, procedure, approvals, and source-open narrative.",
            "Phase 4: watchdog the folders after each finance chain or weekly hygiene pass.",
            "Phase 5: produce a separate delete proposal for archived copies only after retention age, duplicate proof, restore test, and explicit delete approval.",
        ],
        "summary": {
            "files_scanned": len(rows),
            "by_folder": dict(sorted(by_folder.items())),
            "by_posture": dict(sorted(by_posture.items())),
            "archive_candidate_count": sum(1 for row in rows if row["archive_candidate"]),
            "eligible_for_move_only_archive_count": len(eligible),
            "blocked_archive_candidate_count": len(blocked),
            "compress_live_count": sum(1 for row in rows if row["posture"] == "compress_live"),
            "delete_allowed": False,
        },
        "eligible_archive_rows": eligible,
        "blocked_archive_rows": blocked,
        "rows": rows,
    }


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
    if args.validate and report["summary"]["blocked_archive_candidate_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
