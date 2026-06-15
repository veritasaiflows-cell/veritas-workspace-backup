#!/usr/bin/env python3
"""Plan, but do not perform, future deletion of archived workspace files."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "09. Archive"
TMP = ROOT / "tmp"
REPORT_PATH = TMP / "archive-delete-readiness-plan.json"

AUTHORITY_BOUNDARY = {
    "plan_only": True,
    "delete_allowed_now": False,
    "archive_delete_apply_allowed_by_this_script": False,
    "requires_separate_exact_owner_delete_approval": True,
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_files() -> list[Path]:
    if not ARCHIVE.exists():
        return []
    return sorted((path for path in ARCHIVE.rglob("*") if path.is_file()), key=lambda p: rel(p).lower())


def classify(path: Path) -> tuple[str, str, list[str]]:
    rel_path = rel(path)
    if rel_path.startswith("09. Archive/Core Finance Human Surfaces/"):
        return "delete_candidate_after_retention_and_restore_test", "core_folder_flattening_archive", [
            "created by approved move-only core-folder flattening archive",
            "source path is preserved under archive root",
        ]
    if rel_path.startswith("09. Archive/Finance Human Notes Thinning/"):
        return "delete_candidate_after_retention_and_restore_test", "tmp_markdown_sidecar_archive", [
            "created by generated Markdown sidecar thinning archive",
            "machine JSON proof should remain live or separately retained",
        ]
    if "WF78 Finance SQL Canon Legacy 42 Proof" in rel_path:
        return "retain_archived_proof", "wf78_legacy_sql_canon_proof", [
            "audit proof for SQL-canon transition; retain until longer retention decision",
        ]
    return "manual_review_required", "other_archive_file", ["archive file outside current delete-planning scope"]


def build_report() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in archive_files():
        posture, cls, evidence = classify(path)
        rows.append({
            "path": rel(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "delete_readiness": posture,
            "candidate_class": cls,
            "delete_allowed_now": False,
            "requirements_before_delete": [
                "owner selects retention window",
                "restore drill proves archived file can return to original path",
                "replacement proof remains live when applicable",
                "workspace boundary/index validators pass after archive",
                "separate exact owner delete approval names this class or file set",
            ],
            "evidence": evidence,
        })
    by_readiness: dict[str, int] = {}
    for row in rows:
        by_readiness[row["delete_readiness"]] = by_readiness.get(row["delete_readiness"], 0) + 1
    return {
        "schema_version": "archive_delete_readiness_plan.v1",
        "generated_at_utc": utc_now(),
        "status": "planned_delete_blocked_requires_future_exact_approval",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "archive_files_scanned": len(rows),
            "by_delete_readiness": dict(sorted(by_readiness.items())),
            "delete_allowed_now_count": 0,
        },
        "recommendation": [
            "Do not delete archived files yet.",
            "Keep at least one restore-tested retention window before any delete apply helper exists.",
            "If deletion is later approved, delete only by class-specific packet with hashes, restore proof, and post-delete validators.",
        ],
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(REPORT_PATH, report)
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT_PATH) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["summary"]["delete_allowed_now_count"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
