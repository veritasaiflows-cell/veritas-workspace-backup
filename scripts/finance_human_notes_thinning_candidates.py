#!/usr/bin/env python3
"""Build a review-only candidate packet for thinning finance human notes.

The output is a planning artifact only. It does not archive, delete, mutate
canonical notes, or change portfolio/customer/execution state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_FINANCE_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
PLAN_PATH = TMP / "finance-human-notes-thinning-plan.json"
REPORT_PATH = TMP / "finance-human-notes-thinning-candidates.json"
GO_HUMAN_NOTES_SQL_CHECK = TMP / "go-binaries" / "go-finance-human-notes-sql-check.exe"
GO_HUMAN_NOTES_SQL_CHECK_REPORT = TMP / "go-finance-human-notes-sql-check.json"
SUPPORTED_ACTIVE_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}

TEXT_EXTENSIONS = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".ps1"}
SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / "06. Playbooks",
    ROOT / "skills",
    ROOT / "TOOLS.md",
    ROOT / "AGENTS.md",
    ROOT / "MEMORY.md",
]
KEEP_ROOT_FILES = {
    "AGENTS.md",
    "HEARTBEAT.md",
    "Home.md",
    "IDENTITY.md",
    "MEMORY.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
}
KEEP_TOP_LEVEL_DIRS = {
    ".git",
    ".obsidian",
    "06. Playbooks",
    "09. Archive",
    "backups",
    "data",
    "memory",
    "skills",
    "state",
}
NON_BLOCKING_REFERENCE_ROOTS = {"tmp", "09. Archive", "memory", "backups"}
CONTROL_SURFACE_FILES = {"TOOLS.md", "AGENTS.md", "MEMORY.md", "SOUL.md", "USER.md", "HEARTBEAT.md"}

AUTHORITY_BOUNDARY = {
    "plan_only": True,
    "candidate_packet_only": True,
    "human_note_archive_applied": False,
    "delete_allowed": False,
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
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


def load_scan_texts() -> list[tuple[Path, str]]:
    loaded: list[tuple[Path, str]] = []
    for path in iter_scan_files():
        try:
            loaded.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return loaded


def iter_markdown_notes() -> list[Path]:
    notes: list[Path] = []
    for path in ROOT.rglob("*.md"):
        rel_parts = path.relative_to(ROOT).parts
        if not rel_parts:
            continue
        if rel_parts[0] in {".git", ".obsidian", "node_modules"}:
            continue
        if "backups" in rel_parts:
            continue
        if rel_parts[0] == "09. Archive":
            continue
        if path.name in KEEP_ROOT_FILES and len(rel_parts) == 1:
            continue
        notes.append(path)
    return sorted(notes, key=lambda p: rel(p).lower())


def classify_note(path: Path) -> tuple[str, str, bool]:
    rel_parts = path.relative_to(ROOT).parts
    rel_path = rel(path)
    if rel_parts[0] == "tmp":
        json_peer = path.with_suffix(".json")
        if json_peer.exists():
            return "generated_markdown_sidecar_with_json_peer", "json_peer", True
        return "generated_markdown_sidecar_without_json_peer", "missing_replacement_proof", False
    if rel_parts[0] == "09. Archive":
        return "already_archived_note", "already_archived", False
    if rel_parts[0] in KEEP_TOP_LEVEL_DIRS:
        return "protected_human_or_control_note", "protected_owner_surface", False
    if rel_path.endswith("README.md"):
        return "readme_or_route_note", "protected_route_surface", False
    return "unclassified_markdown_note", "manual_review_required", False


def replacement_proof(path: Path, replacement_kind: str) -> dict[str, Any]:
    if replacement_kind == "json_peer":
        peer = path.with_suffix(".json")
        return {
            "kind": "json_peer",
            "path": rel(peer),
            "exists": peer.exists(),
            "sha256": sha256(peer) if peer.exists() and peer.is_file() else None,
        }
    return {"kind": replacement_kind, "exists": False}


def empty_reference_scan() -> dict[str, Any]:
    return {
        "total_reference_count": 0,
        "blocking_reference_count": 0,
        "references": [],
        "blocking_references": [],
    }


def reference_row(scan_path: Path) -> dict[str, Any]:
    scan_rel = rel(scan_path)
    scan_parts = scan_path.relative_to(ROOT).parts
    script_dependency = bool(scan_parts and scan_parts[0] == "scripts" and scan_path.suffix.lower() == ".py")
    control_surface = scan_path.name in CONTROL_SURFACE_FILES or scan_rel == "06. Playbooks/Active Workflows.md"
    non_blocking_history = bool(scan_parts and scan_parts[0] in NON_BLOCKING_REFERENCE_ROOTS)
    return {
        "path": scan_rel,
        "script_dependency": script_dependency,
        "control_surface": control_surface,
        "non_blocking_history": non_blocking_history,
    }


def build_reference_map(paths: list[Path], scan_texts: list[tuple[Path, str]]) -> dict[str, dict[str, Any]]:
    if not paths:
        return {}
    needle_to_rel: dict[str, str] = {}
    for path in paths:
        rel_path = rel(path)
        needle_to_rel[rel_path] = rel_path
        needle_to_rel[rel_path.replace("/", "\\")] = rel_path
    pattern = re.compile("|".join(re.escape(needle) for needle in sorted(needle_to_rel, key=len, reverse=True)))
    references_by_path: dict[str, dict[str, dict[str, Any]]] = {rel(path): {} for path in paths}
    for scan_path, text in scan_texts:
        matches = set(needle_to_rel[match.group(0)] for match in pattern.finditer(text))
        if not matches:
            continue
        row = reference_row(scan_path)
        for matched_rel in matches:
            if rel(scan_path) == matched_rel:
                continue
            references_by_path[matched_rel][row["path"]] = row
    result: dict[str, dict[str, Any]] = {}
    for rel_path, refs_by_scan in references_by_path.items():
        refs = sorted(refs_by_scan.values(), key=lambda row: row["path"].lower())
        blocking = [row for row in refs if row["script_dependency"] or row["control_surface"]]
        result[rel_path] = {
            "total_reference_count": len(refs),
            "blocking_reference_count": len(blocking),
            "references": refs,
            "blocking_references": blocking,
        }
    return result


def validate_sql_canon_python() -> dict[str, Any]:
    if not STATE_FINANCE_DB.exists():
        return {
            "status": "missing",
            "path": rel(STATE_FINANCE_DB),
            "route_runtime": "python_fallback",
            "python_fallback_retained": True,
        }
    uri = STATE_FINANCE_DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM current_active_universe").fetchone()[0]
        answer_path = conn.execute("SELECT COUNT(*) FROM current_answer_path").fetchone()[0]
        review_monitor = conn.execute("SELECT COUNT(*) FROM review_monitor_universe").fetchone()[0]
    return {
        "status": "ok" if integrity == "ok" and active in SUPPORTED_ACTIVE_COUNTS and answer_path == 42 and review_monitor in SUPPORTED_REVIEW_MONITOR_COUNTS else "blocked",
        "path": rel(STATE_FINANCE_DB),
        "integrity": integrity,
        "active_ticker_count": active,
        "active_ticker_supported_counts": sorted(SUPPORTED_ACTIVE_COUNTS),
        "legacy_answer_path_count": answer_path,
        "review_monitor_count": review_monitor,
        "review_monitor_supported_counts": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS),
        "route_runtime": "python_fallback",
        "python_fallback_retained": True,
    }


def validate_sql_canon_go_primary() -> dict[str, Any]:
    if not GO_HUMAN_NOTES_SQL_CHECK.exists():
        fallback = validate_sql_canon_python()
        fallback.update(
            {
                "controlled_route": "go_primary_with_python_fallback",
                "route_runtime": "python_fallback",
                "fallback_used": True,
                "fallback_reason": "go_binary_missing",
                "go_binary": rel(GO_HUMAN_NOTES_SQL_CHECK),
                "python_fallback_retained": True,
            }
        )
        return fallback

    command = [
        str(GO_HUMAN_NOTES_SQL_CHECK),
        "--root",
        str(ROOT),
        "--driver",
        "inprocess",
        "--out",
        str(GO_HUMAN_NOTES_SQL_CHECK_REPORT),
    ]
    started = datetime.now(timezone.utc)
    proc = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
    if proc.returncode == 0 and GO_HUMAN_NOTES_SQL_CHECK_REPORT.exists():
        try:
            go_report = json.loads(GO_HUMAN_NOTES_SQL_CHECK_REPORT.read_text(encoding="utf-8"))
            go_check = go_report.get("sql_canon_check")
            if isinstance(go_check, dict):
                routed = dict(go_check)
                routed.update(
                    {
                        "controlled_route": "go_primary_with_python_fallback",
                        "route_runtime": "go",
                        "fallback_used": False,
                        "fallback_reason": None,
                        "python_fallback_retained": True,
                        "go_binary": rel(GO_HUMAN_NOTES_SQL_CHECK),
                        "go_report": rel(GO_HUMAN_NOTES_SQL_CHECK_REPORT),
                    }
                )
                return routed
        except (OSError, json.JSONDecodeError):
            pass

    fallback = validate_sql_canon_python()
    fallback.update(
        {
            "controlled_route": "go_primary_with_python_fallback",
            "route_runtime": "python_fallback",
            "fallback_used": True,
            "fallback_reason": "go_primary_failed",
            "go_binary": rel(GO_HUMAN_NOTES_SQL_CHECK),
            "go_report": rel(GO_HUMAN_NOTES_SQL_CHECK_REPORT),
            "go_returncode": proc.returncode,
            "go_stdout_tail": (proc.stdout or "")[-500:],
            "go_stderr_tail": (proc.stderr or "")[-500:],
            "go_started_at_utc": started.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "python_fallback_retained": True,
        }
    )
    return fallback


def validate_sql_canon() -> dict[str, Any]:
    return validate_sql_canon_go_primary()


def build_report() -> dict[str, Any]:
    plan = load_json(PLAN_PATH, {}) or {}
    scan_texts = load_scan_texts()
    sql_canon = validate_sql_canon()
    rows: list[dict[str, Any]] = []
    notes = iter_markdown_notes()
    classified = [(path, *classify_note(path)) for path in notes]
    reference_map = build_reference_map(
        [path for path, _candidate_class, _replacement_kind, candidate_by_policy in classified if candidate_by_policy],
        scan_texts,
    )
    for path, candidate_class, replacement_kind, candidate_by_policy in classified:
        proof = replacement_proof(path, replacement_kind)
        refs = reference_map.get(rel(path), empty_reference_scan()) if candidate_by_policy else empty_reference_scan()
        eligible_for_future_archive = bool(
            candidate_by_policy
            and proof.get("exists") is True
            and refs["blocking_reference_count"] == 0
        )
        rows.append(
            {
                "path": rel(path),
                "candidate_class": candidate_class,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "candidate_by_policy": candidate_by_policy,
                "replacement_proof": proof,
                "reference_scan": refs,
                "eligible_for_future_move_only_archive": eligible_for_future_archive,
                "blocked_reason": None if eligible_for_future_archive else (
                    "not_candidate_by_policy" if not candidate_by_policy else
                    "missing_replacement_proof" if proof.get("exists") is not True else
                    "blocking_reference"
                ),
                "rollback": f"Move archived copy back to {rel(path)}",
            }
        )
    eligible = [row for row in rows if row["eligible_for_future_move_only_archive"]]
    candidate_rows = [row for row in rows if row["candidate_by_policy"]]
    return {
        "schema_version": "finance_human_notes_thinning_candidates.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_owner_review_no_archive_applied",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_plan": rel(PLAN_PATH),
        "source_plan_status": plan.get("status"),
        "sql_canon_check": sql_canon,
        "summary": {
            "markdown_notes_scanned": len(rows),
            "candidate_by_policy_count": len(candidate_rows),
            "eligible_for_future_move_only_archive_count": len(eligible),
            "blocked_candidate_count": len(candidate_rows) - len(eligible),
            "human_note_archive_applied": False,
            "delete_allowed": False,
        },
        "recommendation": {
            "next_action": "review eligible rows, then run a separate move-only archive helper in a microbatch only after explicit approval",
            "do_not_archive_now": [
                "owner-truth notes",
                "active workflow or continuity notes",
                "portfolio/risk/source-open narrative notes",
                "procedures, skills, memory, or control surfaces",
                "any note with a script or control-surface dependency",
            ],
        },
        "eligible_future_archive_rows": eligible,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write candidate packet.")
    parser.add_argument("--validate", action="store_true", help="Fail if the packet is not internally valid.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(REPORT_PATH, report)
    summary = {
        "status": report["status"],
        "markdown_notes_scanned": report["summary"]["markdown_notes_scanned"],
        "candidate_by_policy_count": report["summary"]["candidate_by_policy_count"],
        "eligible_for_future_move_only_archive_count": report["summary"]["eligible_for_future_move_only_archive_count"],
        "blocked_candidate_count": report["summary"]["blocked_candidate_count"],
        "sql_canon_check": report["sql_canon_check"]["status"],
        "report": rel(REPORT_PATH) if args.write else None,
    }
    print(json.dumps(report if args.pretty else summary, indent=2, sort_keys=True))
    if args.validate and report["sql_canon_check"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
