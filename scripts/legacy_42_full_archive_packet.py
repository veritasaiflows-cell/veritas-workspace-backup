#!/usr/bin/env python3
"""Build/apply the owner-approved Legacy 42 full archive packet.

This is a move-only archive helper for the exact Legacy 42 scripts and proof
artifacts made eligible by the no-runtime-import guard. It never deletes files
and never mutates SQL schema, canon notes, portfolio, cash, sizing, risk,
brokerage, paper/live, cron schedules, or account state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "legacy-42-full-archive-packet.json"
CLOSEOUT = TMP / "legacy-42-full-archive-apply-closeout.json"
GUARD = TMP / "legacy-42-no-runtime-imports-guard.json"
ARCHIVE_ROOT = ROOT / "09. Archive" / "WF78 Legacy 42 Full Archive" / "2026-06-24"
SCHEMA = "veritas.legacy_42_full_archive_packet.v1"

OWNER_APPROVAL_REFERENCE = (
    "Telegram #4643, 2026-06-24 08:41 MST, Randall: "
    "Yes please proceed and approval provided for full archive."
)

SCRIPT_CANDIDATES = [
    "scripts/wf78_legacy_42_tier_migration_planner.py",
    "scripts/wf78_legacy_42_archive_readiness_packet.py",
    "scripts/wf78_legacy_42_tier_state.py",
    "scripts/legacy_42_lifecycle_gate_packet.py",
    "scripts/test_legacy_42_lifecycle_gate_packet.py",
]

ARTIFACT_CANDIDATES = [
    "tmp/wf78-legacy-42-tier-migration-planner.json",
    "tmp/wf78-legacy-42-tier-state-shadow.sqlite",
    "tmp/wf78-legacy-42-archive-readiness-packet.json",
    "tmp/legacy-42-lifecycle-gate-packet.json",
]

AUTHORITY_BOUNDARY = {
    "owner_archive_approval_reference": OWNER_APPROVAL_REFERENCE,
    "archive_move_only": True,
    "delete_allowed": False,
    "overwrite_allowed": False,
    "sql_schema_mutation_allowed": False,
    "source_artifact_content_rewrite_allowed": False,
    "portfolio_or_canon_note_mutation_allowed": False,
    "cash_sizing_or_risk_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_workspace(path_text: str) -> Path:
    path = (ROOT / path_text).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes workspace: {path_text}")
    return path


def archive_destination(path_text: str) -> Path:
    source = resolve_workspace(path_text)
    dest = (ARCHIVE_ROOT / path_text).resolve()
    archive_root = ARCHIVE_ROOT.resolve()
    if dest != archive_root and archive_root not in dest.parents:
        raise ValueError(f"destination escapes archive root: {path_text}")
    if source == dest:
        raise ValueError(f"source equals destination: {path_text}")
    return dest


def candidate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path_text in SCRIPT_CANDIDATES + ARTIFACT_CANDIDATES:
        source = resolve_workspace(path_text)
        dest = archive_destination(path_text)
        row = {
            "source": path_text,
            "destination": rel(dest),
            "kind": "script" if path_text.startswith("scripts/") else "artifact",
            "source_exists": source.exists(),
            "destination_exists": dest.exists(),
            "source_sha256": sha256_file(source),
            "destination_sha256": sha256_file(dest),
            "source_bytes": source.stat().st_size if source.exists() and source.is_file() else None,
            "move_allowed_after_owner_approval": True,
            "delete_allowed": False,
            "overwrite_allowed": False,
            "rollback": f"Move {rel(dest)} back to {path_text}",
        }
        if not source.exists() and dest.exists():
            row["already_archived"] = True
        rows.append(row)
    return rows


def validate_preconditions(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    guard = load_dict(GUARD)
    summary = guard.get("summary") if isinstance(guard.get("summary"), dict) else {}
    if guard.get("status") != "ready_for_archive_packet_prep":
        errors.append("no_runtime_guard_not_ready")
    if int(summary.get("active_runtime_blocker_count") or 0) != 0:
        errors.append("active_runtime_blockers_not_zero")
    guard_candidates = guard.get("archive_candidate_scripts_after_runtime_cutover")
    if isinstance(guard_candidates, list) and sorted(guard_candidates) != sorted(SCRIPT_CANDIDATES):
        errors.append("script_candidate_set_drift")
    missing = [row["source"] for row in rows if not row["source_exists"] and not row.get("already_archived")]
    if missing:
        errors.append(f"missing_sources:{','.join(missing)}")
    existing = [
        row["destination"]
        for row in rows
        if row["source_exists"] and row["destination_exists"]
    ]
    if existing:
        errors.append(f"destination_exists:{','.join(existing)}")
    unhashed = [row["source"] for row in rows if row["source_exists"] and not row["source_sha256"]]
    if unhashed:
        errors.append(f"source_hash_missing:{','.join(unhashed)}")
    return sorted(errors)


def build_packet(*, apply: bool = False) -> dict[str, Any]:
    rows = candidate_rows()
    pre_errors = validate_preconditions(rows)
    move_rows: list[dict[str, Any]] = []
    move_errors: list[str] = []

    if apply and pre_errors:
        move_errors.extend(pre_errors)
    elif apply:
        for row in rows:
            source = resolve_workspace(row["source"])
            dest = archive_destination(row["source"])
            applied = dict(row)
            if not source.exists() and dest.exists():
                applied.update(
                    {
                        "moved": False,
                        "already_archived": True,
                        "verified": True,
                        "destination_sha256_after": sha256_file(dest),
                    }
                )
                move_rows.append(applied)
                continue
            before_hash = sha256_file(source)
            if before_hash != row["source_sha256"]:
                move_errors.append(f"source_hash_changed:{row['source']}")
                applied["verified"] = False
                move_rows.append(applied)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))
            after_hash = sha256_file(dest)
            applied.update(
                {
                    "moved": True,
                    "source_exists_after": source.exists(),
                    "destination_exists_after": dest.exists(),
                    "destination_sha256_after": after_hash,
                    "verified": after_hash == before_hash and not source.exists() and dest.exists(),
                }
            )
            if not applied["verified"]:
                move_errors.append(f"move_not_verified:{row['source']}")
            move_rows.append(applied)

    effective_rows = move_rows if apply else rows
    moved_count = sum(1 for row in effective_rows if row.get("moved"))
    already_archived_count = sum(1 for row in effective_rows if row.get("already_archived"))
    verified_count = sum(1 for row in effective_rows if row.get("verified"))
    status = "archived" if apply and not move_errors else "owner_approved_archive_ready" if not pre_errors else "blocked"
    if apply and move_errors:
        status = "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "apply": apply,
        "archive_root": rel(ARCHIVE_ROOT),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(rows),
            "script_candidate_count": len(SCRIPT_CANDIDATES),
            "artifact_candidate_count": len(ARTIFACT_CANDIDATES),
            "source_exists_count": sum(1 for row in rows if row["source_exists"]),
            "destination_existing_count": sum(1 for row in rows if row["destination_exists"]),
            "moved_count": moved_count,
            "already_archived_count": already_archived_count,
            "verified_count": verified_count,
            "delete_count": 0,
            "overwrite_count": 0,
            "precondition_error_count": len(pre_errors),
            "move_error_count": len(move_errors),
        },
        "owner_approval_reference": OWNER_APPROVAL_REFERENCE,
        "rows": effective_rows,
        "precondition_errors": pre_errors,
        "move_errors": move_errors,
        "post_archive_validation_plan": [
            "python scripts\\legacy_42_no_runtime_imports_guard.py --write --validate",
            "python scripts\\finance_production_scope.py --write --validate",
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\finance_production_grade_policy_gate.py --write --validate",
            "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
            "python scripts\\validator_bundle_router.py --write --validate",
            "python scripts\\go_binary_freshness_guard.py --write --validate",
            "python scripts\\control_closeout_bundle.py --validation-budget shared --write --validate",
            "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
        ],
        "stop_lines": [
            "Archive is move-only; no delete or overwrite.",
            "Do not archive schema compatibility fields from this packet.",
            "Do not mutate SQL schema, source content, portfolio/canon notes, cash/sizing/risk, cron schedules, paper/live, brokerage/account, or customer/public delivery.",
        ],
        "validation": {
            "status": "ok" if not pre_errors and not move_errors else "error",
            "errors": pre_errors + move_errors,
            "warnings": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Move exact candidates into the archive root.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_packet(apply=args.apply)
    out = CLOSEOUT if args.apply else OUT
    if args.write:
        atomic_write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "apply": packet["apply"],
                "out": rel(out),
                "summary": packet["summary"],
                "validation": packet["validation"],
            },
            indent=2,
        )
    )
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
