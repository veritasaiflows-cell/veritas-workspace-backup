#!/usr/bin/env python3
"""Prepare or apply a guarded human-note thinning archive microbatch.

This moves only generated Markdown sidecars already marked eligible by
finance_human_notes_thinning_candidates.py. It never deletes files and never
archives owner-truth, workflow, procedure, portfolio, risk, source-open, memory,
skill, or control-surface notes.
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
CANDIDATES_PATH = TMP / "finance-human-notes-thinning-candidates.json"
REPORT_PATH = TMP / "finance-human-notes-archive-apply-report.json"
ARCHIVE_ROOT = ROOT / "09. Archive" / "Finance Human Notes Thinning" / "2026-05-30"

AUTHORITY_BOUNDARY_BASE = {
    "move_only": True,
    "delete_allowed": False,
    "archive_owner_truth_notes_allowed": False,
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


def destination_for(source: Path) -> Path:
    return ARCHIVE_ROOT / rel(source)


def selected_candidates(limit: int | None) -> list[dict[str, Any]]:
    packet = load_json(CANDIDATES_PATH)
    rows = packet.get("eligible_future_archive_rows", [])
    rows = [row for row in rows if row.get("eligible_for_future_move_only_archive") is True]
    rows = sorted(rows, key=lambda row: str(row.get("path", "")).lower())
    if limit is not None:
        rows = rows[:limit]
    return rows


def validate_candidate(row: dict[str, Any]) -> tuple[bool, str | None]:
    if row.get("candidate_class") != "generated_markdown_sidecar_with_json_peer":
        return False, "not_generated_markdown_sidecar_with_json_peer"
    if row.get("eligible_for_future_move_only_archive") is not True:
        return False, "not_marked_eligible"
    refs = row.get("reference_scan") or {}
    if refs.get("blocking_reference_count", 0) != 0:
        return False, "blocking_reference"
    proof = row.get("replacement_proof") or {}
    if proof.get("kind") != "json_peer" or proof.get("exists") is not True:
        return False, "missing_json_peer_replacement_proof"
    return True, None


def process_candidate(row: dict[str, Any], apply: bool) -> dict[str, Any]:
    source = resolve_workspace(str(row["path"]))
    dest = destination_for(source)
    result: dict[str, Any] = {
        "source": rel(source),
        "destination": rel(dest),
        "candidate_class": row.get("candidate_class"),
        "exists_before": source.exists(),
        "eligible": False,
        "moved": False,
        "already_archived": False,
        "verified": False,
        "blocked_reason": None,
        "rollback": f"Move {rel(dest)} back to {rel(source)}",
    }

    valid, blocked = validate_candidate(row)
    if not valid:
        result["blocked_reason"] = blocked
        return result

    proof = row.get("replacement_proof") or {}
    proof_path = resolve_workspace(str(proof["path"]))
    if not proof_path.exists():
        result["blocked_reason"] = "replacement_json_peer_missing"
        return result
    proof_hash = sha256(proof_path)
    if proof.get("sha256") and proof_hash != proof.get("sha256"):
        result["blocked_reason"] = "replacement_json_peer_hash_changed"
        result["replacement_current_sha256"] = proof_hash
        result["replacement_expected_sha256"] = proof.get("sha256")
        return result

    if not source.exists():
        if dest.exists() and dest.is_file():
            result["already_archived"] = True
            result["verified"] = True
            result["destination_exists_after"] = True
            result["destination_sha256_existing"] = sha256(dest)
            result["bytes"] = dest.stat().st_size
            return result
        result["blocked_reason"] = "source_missing"
        return result
    if not source.is_file():
        result["blocked_reason"] = "source_not_file"
        return result
    if dest.exists():
        result["blocked_reason"] = "destination_exists"
        result["destination_sha256_existing"] = sha256(dest)
        return result

    before_hash = sha256(source)
    expected_hash = row.get("sha256")
    if expected_hash and before_hash != expected_hash:
        result["blocked_reason"] = "source_hash_changed"
        result["source_current_sha256"] = before_hash
        result["source_expected_sha256"] = expected_hash
        return result

    result["sha256_before"] = before_hash
    result["bytes"] = source.stat().st_size
    result["eligible"] = True
    result["replacement_proof"] = {
        "path": rel(proof_path),
        "sha256": proof_hash,
    }
    if not apply:
        result["dry_run"] = True
        result["verified"] = True
        return result

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))
    after_hash = sha256(dest)
    result["sha256_after"] = after_hash
    result["moved"] = True
    result["source_exists_after"] = source.exists()
    result["destination_exists_after"] = dest.exists()
    result["verified"] = after_hash == before_hash and not source.exists() and dest.exists()
    return result


def build_report(apply: bool, limit: int | None, approval_reference: str | None) -> dict[str, Any]:
    rows = [process_candidate(row, apply=apply) for row in selected_candidates(limit)]
    errors = [
        row for row in rows
        if row.get("eligible") and (row.get("moved") != apply or not row.get("verified"))
    ]
    blocked = [row for row in rows if row.get("blocked_reason")]
    moved = [row for row in rows if row.get("moved")]
    already_archived = [row for row in rows if row.get("already_archived")]
    authority_boundary = {
        **AUTHORITY_BOUNDARY_BASE,
        "owner_archive_approval": approval_reference,
        "archive_apply_requested": apply,
        "archive_apply_allowed": bool(apply and approval_reference),
    }
    if apply and not approval_reference:
        errors.append({"blocked_reason": "apply_requires_approval_reference"})
    status = "ok" if not errors else "blocked"
    return {
        "schema_version": "finance_human_notes_archive_apply_report.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "dry_run": not apply,
        "source_candidates": rel(CANDIDATES_PATH),
        "archive_root": rel(ARCHIVE_ROOT),
        "authority_boundary": authority_boundary,
        "summary": {
            "candidate_count": len(rows),
            "eligible_count": sum(1 for row in rows if row.get("eligible")),
            "moved_count": len(moved),
            "already_archived_count": len(already_archived),
            "blocked_count": len(blocked),
            "error_count": len(errors),
            "limit": limit,
        },
        "rows": rows,
        "blocked": blocked,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Move selected eligible Markdown sidecars into archive.")
    parser.add_argument("--write", action="store_true", help="Write apply/readiness report.")
    parser.add_argument("--validate", action="store_true", help="Fail when the selected microbatch is not fully verified.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum eligible rows to process; default 50.")
    parser.add_argument("--all", action="store_true", help="Process all eligible rows instead of the default microbatch limit.")
    parser.add_argument("--approval-reference", help="Exact owner approval reference; required with --apply.")
    args = parser.parse_args()

    limit = None if args.all else args.limit
    report = build_report(apply=args.apply, limit=limit, approval_reference=args.approval_reference)
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
    }, indent=2, sort_keys=True))
    if args.validate and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
