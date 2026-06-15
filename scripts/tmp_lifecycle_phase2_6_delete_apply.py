#!/usr/bin/env python3
"""Apply tmp lifecycle phase 2-6 deletions with tombstone proof.

This helper is intentionally conservative:
- it only deletes paths under tmp/
- phase 2 backup/restore copies can be deleted after exact approval with hashes
- phases 3, 4, and 5 delete only zero-live-reference rows
- phase 6 deletes only unreferenced machine artifacts
- referenced Markdown, active presentation fallbacks, and referenced proof packets
  are reported as blockers for a retarget/retention follow-up.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
PROPOSAL = TMP / "tmp-lifecycle-delete-proposal.json"
REPORT = TMP / "tmp-lifecycle-phase2-6-delete-apply-report.json"
TOMBSTONE = STATE / "tmp-lifecycle-deletion-tombstone.json"

PHASE_2 = "phase_2_delete_candidate_after_restore_proof"
PHASE_3 = "phase_3_archive_or_delete_after_reference_retarget"
PHASE_4 = "phase_4_presentation_format_adjudication"
PHASE_5 = "phase_5_retention_policy_needed"
PHASE_6 = "phase_6_candidate_after_family_review"

ALLOWED = {
    (PHASE_2, "tmp_backup_or_restore_copy"),
    (PHASE_3, "tmp_markdown_human_residue"),
    (PHASE_4, "tmp_presentation_output"),
    (PHASE_5, "workflow_proof_packet"),
    (PHASE_6, "unreferenced_tmp_machine_artifact"),
}

REFERENCE_SENSITIVE_PHASES = {PHASE_3, PHASE_4, PHASE_5, PHASE_6}

ACTIVE_PRESENTATION_PATHS = {
    "tmp/entry-band-status.html",
    "tmp/retail-saas-fixture-demo.html",
    "tmp/sector-dashboard-suite.html",
    "tmp/veritas-command-center.html",
    "tmp/veritas-command-center.last-good.html",
}

AUTHORITY_BOUNDARY = {
    "tmp_lifecycle_phase2_6_delete_apply_script": True,
    "requires_apply_flag": True,
    "requires_exact_owner_approval_reference": True,
    "delete_limited_to_tmp": True,
    "allowed_phase_classes": sorted(f"{phase}:{klass}" for phase, klass in ALLOWED),
    "reference_sensitive_phases_require_zero_live_references": True,
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


def assert_inside_tmp(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
        resolved.relative_to(TMP.resolve())
    except ValueError as exc:
        raise ValueError(f"path outside tmp lifecycle scope: {path}") from exc
    return resolved


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_proposal() -> dict[str, Any]:
    data = load_json(PROPOSAL, {})
    if not isinstance(data, dict) or data.get("schema_version") != "tmp_lifecycle_delete_proposal.v1":
        raise SystemExit(f"unexpected or missing proposal: {rel(PROPOSAL)}")
    return data


def remove_empty_tmp_parents(path: Path, removed: list[str]) -> None:
    current = path
    tmp_resolved = TMP.resolve()
    while current.exists() and current.resolve() != tmp_resolved:
        try:
            current.resolve().relative_to(tmp_resolved)
        except ValueError:
            break
        try:
            current.rmdir()
        except OSError:
            break
        removed.append(rel(current))
        current = current.parent


def is_candidate(row: dict[str, Any]) -> bool:
    return (row.get("proposal_phase"), row.get("proposal_class")) in ALLOWED


def block_reason(row: dict[str, Any]) -> str | None:
    path = str(row.get("path", ""))
    phase = row.get("proposal_phase")
    if not path.startswith("tmp/"):
        return "outside_tmp_scope"
    if not is_candidate(row):
        return "phase_class_not_allowed"
    live_refs = row.get("live_reference_count", row.get("reference_count"))
    if phase in REFERENCE_SENSITIVE_PHASES and int(live_refs or 0) != 0:
        return "reference_retarget_required_before_delete"
    if path in ACTIVE_PRESENTATION_PATHS:
        return "active_presentation_surface_retained"
    if row.get("kind") != "file":
        return "only_file_rows_supported"
    return None


def build_report(apply: bool, approval_reference: str | None) -> dict[str, Any]:
    proposal = load_proposal()
    candidates = [row for row in proposal.get("rows", []) if row.get("proposal_phase") in {PHASE_2, PHASE_3, PHASE_4, PHASE_5, PHASE_6}]
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    deleted_records: list[dict[str, Any]] = []
    removed_dirs: list[str] = []

    for source in candidates:
        row = dict(source)
        row.update({"deleted": False, "skipped": False, "hash_verified": False})
        reason = block_reason(row)
        if reason:
            row["blocker"] = reason
            blockers.append(row)
            rows.append(row)
            continue

        try:
            path = assert_inside_tmp(ROOT / str(row["path"]))
        except ValueError as exc:
            row["blocker"] = str(exc)
            blockers.append(row)
            rows.append(row)
            continue
        if not path.exists():
            row["skipped"] = True
            row["skip_reason"] = "already_missing"
            rows.append(row)
            continue
        if not path.is_file():
            row["blocker"] = "expected_file"
            blockers.append(row)
            rows.append(row)
            continue

        current_hash = sha256(path)
        row["current_sha256"] = current_hash
        row["hash_verified"] = current_hash == row.get("sha256")
        if not row["hash_verified"]:
            row["blocker"] = "sha256_mismatch"
            blockers.append(row)
            rows.append(row)
            continue

        record = {
            "path": row["path"],
            "bytes": row.get("bytes") or 0,
            "sha256": current_hash,
            "proposal_phase": row.get("proposal_phase"),
            "proposal_class": row.get("proposal_class"),
            "reference_count_at_delete": row.get("reference_count"),
            "live_reference_count_at_delete": row.get("live_reference_count"),
            "deleted_at_utc": utc_now() if apply else None,
        }
        if apply:
            path.unlink()
            row["deleted"] = True
            deleted_records.append(record)
            remove_empty_tmp_parents(path.parent, removed_dirs)
        rows.append(row)

    deleted_count = sum(1 for row in rows if row["deleted"])
    skipped_count = sum(1 for row in rows if row["skipped"])
    deleted_bytes = sum(int(row.get("bytes") or 0) for row in rows if row["deleted"])
    status = "dry_run_ready_no_delete_applied"
    if blockers:
        status = "partial_apply_with_blockers" if deleted_count else "blocked_no_delete_applied"
    elif apply:
        status = "applied_tmp_lifecycle_phase2_6_delete"

    report = {
        "schema_version": "tmp_lifecycle_phase2_6_delete_apply.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "approval_reference": approval_reference,
        "proposal": rel(PROPOSAL),
        "tombstone": rel(TOMBSTONE),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "apply": apply,
            "candidate_count": len(rows),
            "deleted_count": deleted_count,
            "skipped_count": skipped_count,
            "blocker_count": len(blockers),
            "deleted_bytes": deleted_bytes,
            "removed_empty_dirs_count": len(set(removed_dirs)),
            "tombstone_records_added": len(deleted_records),
        },
        "blockers": blockers,
        "removed_empty_dirs": sorted(set(removed_dirs)),
        "deleted_records": deleted_records,
        "rows": rows,
    }
    return report


def update_tombstone(report: dict[str, Any]) -> None:
    existing = load_json(TOMBSTONE, {
        "schema_version": "tmp_lifecycle_deletion_tombstone.v1",
        "created_at_utc": utc_now(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "deleted_records": [],
        "runs": [],
    })
    existing.setdefault("deleted_records", []).extend(report["deleted_records"])
    existing.setdefault("runs", []).append({
        "generated_at_utc": report["generated_at_utc"],
        "status": report["status"],
        "approval_reference": report["approval_reference"],
        "summary": report["summary"],
        "report": rel(REPORT),
    })
    existing["updated_at_utc"] = utc_now()
    atomic_write_json(TOMBSTONE, existing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--approval-reference")
    args = parser.parse_args()
    if args.apply and not args.approval_reference:
        raise SystemExit("--apply requires --approval-reference")
    report = build_report(args.apply, args.approval_reference)
    if args.write:
        atomic_write_json(REPORT, report)
    if args.apply:
        update_tombstone(report)
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT) if args.write else None,
        "tombstone": rel(TOMBSTONE) if args.apply else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["summary"]["blocker_count"] and not report["summary"]["deleted_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
