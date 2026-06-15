#!/usr/bin/env python3
"""Delete phase-1 tmp lifecycle candidates after exact owner approval.

Phase 1 is intentionally narrow: raw OTEL protobuf payloads, compact-exec logs,
and empty manual-review directories already classified by
``tmp_lifecycle_delete_proposal.py``.
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
PROPOSAL = TMP / "tmp-lifecycle-delete-proposal.json"
REPORT = TMP / "tmp-lifecycle-phase1-delete-apply-report.json"

ALLOWED_PHASE = "phase_1_delete_candidate_after_exact_approval"
ALLOWED_CLASSES = {
    "compact_exec_command_log",
    "empty_manual_review_dir",
    "raw_telemetry_payload",
}

AUTHORITY_BOUNDARY = {
    "tmp_lifecycle_phase1_delete_apply_script": True,
    "requires_apply_flag": True,
    "requires_exact_owner_approval_reference": True,
    "delete_limited_to_tmp_lifecycle_phase1": True,
    "allowed_proposal_classes": sorted(ALLOWED_CLASSES),
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


def assert_inside_workspace(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {path}") from exc
    return resolved


def assert_inside_tmp(path: Path) -> Path:
    resolved = assert_inside_workspace(path)
    try:
        resolved.relative_to(TMP.resolve())
    except ValueError as exc:
        raise ValueError(f"path outside tmp lifecycle scope: {path}") from exc
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_proposal() -> dict[str, Any]:
    if not PROPOSAL.exists():
        raise SystemExit(f"missing proposal: {rel(PROPOSAL)}")
    data = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "tmp_lifecycle_delete_proposal.v1":
        raise SystemExit(f"unexpected proposal schema: {rel(PROPOSAL)}")
    return data


def remove_empty_parents(start: Path, removed: list[str]) -> None:
    current = start
    while current != ROOT and current.exists():
        if current.name not in {"compact-exec-logs", "otel-collector"}:
            break
        try:
            current.rmdir()
        except OSError:
            break
        removed.append(rel(current))
        current = current.parent


def build_report(apply: bool, approval_reference: str | None) -> dict[str, Any]:
    proposal = load_proposal()
    candidates = [
        row for row in proposal.get("rows", [])
        if row.get("proposal_phase") == ALLOWED_PHASE
    ]
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    removed_dirs: list[str] = []

    for source in candidates:
        row = dict(source)
        row.update({
            "deleted": False,
            "hash_verified": False,
            "skipped": False,
        })
        if row.get("proposal_class") not in ALLOWED_CLASSES:
            row["blocker"] = "proposal_class_not_allowed"
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
        if row.get("kind") == "file":
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
            if apply:
                path.unlink()
                row["deleted"] = True
                remove_empty_parents(path.parent, removed_dirs)
            rows.append(row)
            continue

        if row.get("kind") == "empty_dir":
            if not path.exists():
                row["skipped"] = True
                row["skip_reason"] = "already_missing"
                rows.append(row)
                continue
            if not path.is_dir():
                row["blocker"] = "expected_directory"
                blockers.append(row)
                rows.append(row)
                continue
            if any(path.iterdir()):
                row["blocker"] = "directory_not_empty"
                blockers.append(row)
                rows.append(row)
                continue
            row["hash_verified"] = True
            if apply:
                try:
                    path.rmdir()
                except OSError as exc:
                    row["blocker"] = f"directory_delete_failed: {exc.__class__.__name__}: {exc}"
                    blockers.append(row)
                    rows.append(row)
                    continue
                row["deleted"] = True
                removed_dirs.append(rel(path))
            rows.append(row)
            continue

        row["blocker"] = "unsupported_kind"
        blockers.append(row)
        rows.append(row)

    deleted_count = sum(1 for row in rows if row["deleted"])
    skipped_count = sum(1 for row in rows if row["skipped"])
    hash_verified_count = sum(1 for row in rows if row["hash_verified"])
    deleted_bytes = sum(int(row.get("bytes") or 0) for row in rows if row["deleted"])
    skipped_bytes = sum(int(row.get("bytes") or 0) for row in rows if row["skipped"])
    status = "dry_run_ready_no_delete_applied"
    if blockers:
        status = "blocked_no_delete_applied" if deleted_count == 0 else "partial_apply_with_blockers"
    elif apply:
        status = "applied_tmp_lifecycle_phase1_delete"

    return {
        "schema_version": "tmp_lifecycle_phase1_delete_apply.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "approval_reference": approval_reference,
        "proposal": rel(PROPOSAL),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "apply": apply,
            "candidate_count": len(rows),
            "hash_verified_count": hash_verified_count,
            "deleted_count": deleted_count,
            "skipped_count": skipped_count,
            "blocker_count": len(blockers),
            "deleted_bytes": deleted_bytes,
            "skipped_bytes": skipped_bytes,
            "removed_empty_dirs_count": len(set(removed_dirs)),
        },
        "blockers": blockers,
        "removed_empty_dirs": sorted(set(removed_dirs)),
        "rows": rows,
    }


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
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["summary"]["blocker_count"] != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
