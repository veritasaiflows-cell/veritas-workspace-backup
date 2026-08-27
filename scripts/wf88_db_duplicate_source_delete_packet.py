#!/usr/bin/env python3
"""Build and apply the WF88 DB duplicate-source delete packet.

This handles only the case where a DB lifecycle entry is still present under
tmp/ but the archive destination already contains the same hashes. It is
fail-closed and requires an explicit owner-approval reference before apply.
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
STATE = ROOT / "state"

MANIFEST = TMP / "db-lifecycle-manifest.json"
PACKET_OUT = TMP / "wf88-db-duplicate-source-delete-packet.json"
APPLY_REPORT = TMP / "wf88-db-duplicate-source-delete-apply-report.json"
TOMBSTONE = STATE / "tmp-lifecycle-deletion-tombstone.json"
ROLLBACK_ROOT = STATE / "tmp-lifecycle-rollback" / "wf88-db-duplicate-source-delete"

SCHEMA = "veritas.wf88_db_duplicate_source_delete_packet.v1"
TARGET_BASENAME = "wf72-entry-stop-sql-activation-rollback-drill.sqlite"
APPROVAL_REFERENCE = (
    "Telegram message 5128, 2026-06-27 09:06:35 MST: "
    '"Yes, approved to fully delete and continue with additional scripts."'
)

NEUTRALIZED_OPERATIONAL_REFS = {
    "06. Playbooks/Project Continuity/Workflow 88 - Veritas OS 2.0.md": "continuity/proof reference; does not require tmp duplicate to exist",
    "scripts/test_wf88_retired_surface_cleanup_plan.py": "test fixture/control reference; does not require tmp duplicate to exist",
}

AUTHORITY_BOUNDARY = {
    "owner_approved_exact_duplicate_source_delete": True,
    "delete_scope": "tmp duplicate WF72 rollback-drill DB and its WAL/SHM sidecars only",
    "archive_mutation_allowed": False,
    "script_deletion_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "portfolio_or_canon_note_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_workspace(path_text: str) -> Path:
    path = (ROOT / path_text.replace("/", "\\")).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes workspace: {path_text}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_files_for(entry: dict[str, Any]) -> list[dict[str, Any]]:
    files = [
        {
            "kind": "database",
            "source": entry.get("path"),
            "archive_destination": entry.get("proposed_destination"),
            "sha256": entry.get("sha256"),
            "size_bytes": entry.get("size_bytes"),
        }
    ]
    for sidecar in as_list(entry.get("sidecars")):
        row = as_dict(sidecar)
        files.append(
            {
                "kind": "sidecar",
                "source": row.get("path"),
                "archive_destination": row.get("proposed_destination"),
                "sha256": row.get("sha256"),
                "size_bytes": row.get("size_bytes"),
            }
        )
    return files


def find_duplicate_entry(manifest: dict[str, Any]) -> dict[str, Any] | None:
    for entry in as_list(manifest.get("entries")):
        row = as_dict(entry)
        if row.get("basename") == TARGET_BASENAME and row.get("path") == f"tmp/{TARGET_BASENAME}":
            return row
    return None


def file_row_status(row: dict[str, Any]) -> dict[str, Any]:
    source_text = str(row.get("source") or "")
    archive_text = str(row.get("archive_destination") or "")
    source = resolve_workspace(source_text)
    archive = resolve_workspace(archive_text)
    expected = row.get("sha256")
    source_hash = sha256_file(source)
    archive_hash = sha256_file(archive)
    exists = source.exists()
    archive_exists = archive.exists()
    hashes_match = bool(expected and source_hash == expected and archive_hash == expected)
    return {
        **row,
        "source_exists": exists,
        "archive_exists": archive_exists,
        "source_sha256_actual": source_hash,
        "archive_sha256_actual": archive_hash,
        "archive_matches_source": bool(source_hash and archive_hash and source_hash == archive_hash),
        "ready": bool(exists and archive_exists and hashes_match),
    }


def neutralized_refs(entry: dict[str, Any]) -> dict[str, Any]:
    refs = as_dict(entry.get("reference_classification"))
    operational = [
        str(item)
        for item in as_list(as_dict(refs.get("summary")).get("active_operational_consumer_references"))
    ]
    if not operational:
        operational = [
            str(item)
            for item in as_list(refs.get("active_operational_consumer_references"))
        ]
    neutralized = [
        {"path": ref, "reason": NEUTRALIZED_OPERATIONAL_REFS[ref]}
        for ref in operational
        if ref in NEUTRALIZED_OPERATIONAL_REFS
    ]
    unneutralized = [ref for ref in operational if ref not in NEUTRALIZED_OPERATIONAL_REFS]
    return {
        "operational_reference_count": len(operational),
        "operational_references": operational,
        "neutralized_operational_references": neutralized,
        "unneutralized_operational_references": unneutralized,
    }


def build_packet() -> dict[str, Any]:
    manifest = load_json(MANIFEST)
    apply_report = load_json(APPLY_REPORT) if APPLY_REPORT.exists() else {}
    entry = find_duplicate_entry(manifest)
    candidate: dict[str, Any] | None = None
    errors: list[str] = []
    warnings: list[str] = []
    if entry is None:
        if apply_report.get("status") == "applied_wf88_db_duplicate_source_delete":
            candidate = {
                "path": f"tmp/{TARGET_BASENAME}",
                "status": "already_applied_missing_from_manifest",
                "deleted_records": apply_report.get("deleted_records") or [],
                "rollback_root": apply_report.get("rollback_root"),
                "tombstone_path": rel(TOMBSTONE),
            }
        else:
            errors.append("target_duplicate_entry_missing")
    else:
        files = [file_row_status(row) for row in source_files_for(entry)]
        refs = neutralized_refs(entry)
        candidate = {
            "path": entry.get("path"),
            "basename": entry.get("basename"),
            "status": entry.get("status"),
            "recommendation": entry.get("recommendation"),
            "archive_destination": entry.get("proposed_destination"),
            "sha256": entry.get("sha256"),
            "size_bytes": entry.get("size_bytes"),
            "sqlite": entry.get("sqlite"),
            "references": refs,
            "files": files,
            "rollback_root": rel(ROLLBACK_ROOT),
            "tombstone_path": rel(TOMBSTONE),
        }
        if entry.get("status") != "archive_destination_already_present":
            errors.append(f"target_status_not_duplicate:{entry.get('status')}")
        if refs["unneutralized_operational_references"]:
            errors.append("unneutralized_operational_references_remain")
        if any(not row.get("ready") for row in files):
            errors.append("one_or_more_duplicate_files_not_ready")
        sqlite_meta = as_dict(entry.get("sqlite"))
        if sqlite_meta.get("open_status") != "ok" or sqlite_meta.get("integrity_check") != "ok":
            errors.append("sqlite_integrity_not_ok")
        if not files:
            errors.append("no_files_planned")
    already_applied = (
        entry is None
        and apply_report.get("status") == "applied_wf88_db_duplicate_source_delete"
    )
    ready = not errors and candidate is not None and not already_applied
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": (
            "approved_duplicate_source_delete_already_applied"
            if already_applied
            else "owner_approved_duplicate_source_delete_ready"
            if ready
            else "blocked"
        ),
        "source_manifest": rel(MANIFEST),
        "approval_reference": APPROVAL_REFERENCE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "candidate": candidate,
        "summary": {
            "target_basename": TARGET_BASENAME,
            "planned_file_count": len(as_list(candidate.get("files"))) if candidate else 0,
            "ready_file_count": sum(1 for row in as_list(candidate.get("files")) if as_dict(row).get("ready")) if candidate else 0,
            "source_delete_allowed_after_owner_approval": ready,
            "already_applied_count": len(as_list(candidate.get("deleted_records"))) if already_applied and candidate else 0,
            "script_deletion_allowed": False,
            "archive_mutation_allowed": False,
            "cron_mutation_allowed": False,
        },
        "post_apply_validation_floor": [
            "python scripts\\db_lifecycle_manifest.py --write --write-md --validate",
            "python scripts\\wf88_db_duplicate_source_delete_packet.py --write --validate",
            "python scripts\\wf88_delete_readiness_packet.py --write --write-md --validate",
            "python scripts\\wf88_os2_control_packet.py --write --write-md --validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
            "python scripts\\validator_bundle_router.py --write --validate",
            "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
        ],
        "validation": {"status": "ok" if ready or already_applied else "blocked", "errors": errors, "warnings": warnings},
    }
    return packet


def append_tombstone(rows: list[dict[str, Any]], generated_at_utc: str, dry_run: bool) -> None:
    existing: dict[str, Any]
    if TOMBSTONE.exists():
        existing = load_json(TOMBSTONE)
    else:
        existing = {"schema": "veritas.tmp_lifecycle_deletion_tombstone.v1", "events": []}
    events = as_list(existing.get("events"))
    events.append(
        {
            "event": "wf88_db_duplicate_source_delete",
            "generated_at_utc": generated_at_utc,
            "dry_run": dry_run,
            "approval_reference": APPROVAL_REFERENCE,
            "records": rows,
        }
    )
    existing["events"] = events
    existing["updated_at_utc"] = utc_now()
    atomic_write_json(TOMBSTONE, existing)


def apply_delete(*, dry_run: bool) -> dict[str, Any]:
    packet = build_packet()
    validation = as_dict(packet.get("validation"))
    if validation.get("status") != "ok":
        return {
            "schema": "veritas.wf88_db_duplicate_source_delete_apply_report.v1",
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "dry_run": dry_run,
            "packet_validation": validation,
            "deleted_records": [],
            "summary": {"planned_files": 0, "deleted_files": 0, "rollback_files": 0, "errors": len(as_list(validation.get("errors")))},
        }
    generated_at = utc_now()
    stamp = generated_at.replace("-", "").replace(":", "").replace("Z", "Z")
    rollback_dir = ROLLBACK_ROOT / stamp
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for file_row in as_list(as_dict(packet.get("candidate")).get("files")):
        row = as_dict(file_row)
        source = resolve_workspace(str(row.get("source")))
        rollback = rollback_dir / str(row.get("source")).replace("/", "\\")
        before_hash = sha256_file(source)
        record = {
            "path": row.get("source"),
            "archive_destination": row.get("archive_destination"),
            "expected_sha256": row.get("sha256"),
            "sha256_before": before_hash,
            "size_bytes": source.stat().st_size if source.exists() else None,
            "rollback_copy": rel(rollback),
            "deleted": False,
            "verified_missing_after": False,
            "error": None,
        }
        if before_hash != row.get("sha256"):
            record["error"] = "source_hash_mismatch_before_delete"
            errors.append(f"{row.get('source')}:source_hash_mismatch_before_delete")
        elif dry_run:
            record["dry_run"] = True
        else:
            rollback.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, rollback)
            if sha256_file(rollback) != before_hash:
                record["error"] = "rollback_hash_mismatch"
                errors.append(f"{row.get('source')}:rollback_hash_mismatch")
            else:
                source.unlink()
                record["deleted"] = True
                record["verified_missing_after"] = not source.exists()
                if not record["verified_missing_after"]:
                    record["error"] = "source_still_exists_after_delete"
                    errors.append(f"{row.get('source')}:source_still_exists_after_delete")
        records.append(record)
    status = "dry_run_ok" if dry_run and not errors else "applied_wf88_db_duplicate_source_delete" if not errors else "blocked"
    if not dry_run and not errors:
        append_tombstone(records, generated_at, dry_run=False)
    return {
        "schema": "veritas.wf88_db_duplicate_source_delete_apply_report.v1",
        "generated_at_utc": generated_at,
        "status": status,
        "dry_run": dry_run,
        "packet_path": rel(PACKET_OUT),
        "authority_boundary": {
            "delete_performed": bool(not dry_run and not errors and records),
            "deleted_only_tmp_duplicate_source": True,
            "archive_mutation_performed": False,
            "script_deletion_performed": False,
            "cron_mutation_performed": False,
            "sql_canon_or_portfolio_mutation_performed": False,
            "brokerage_or_execution_authority": False,
        },
        "approval_reference": APPROVAL_REFERENCE,
        "rollback_root": rel(rollback_dir),
        "deleted_records": records,
        "summary": {
            "planned_files": len(records),
            "deleted_files": sum(1 for row in records if row.get("deleted")),
            "rollback_files": sum(1 for row in records if row.get("deleted") and row.get("rollback_copy")),
            "errors": len(errors),
        },
        "errors": errors,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write packet")
    parser.add_argument("--validate", action="store_true", help="fail when packet/apply report is not clean")
    parser.add_argument("--apply", action="store_true", help="delete the approved duplicate source files")
    parser.add_argument("--dry-run", action="store_true", help="validate apply plan without deleting")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    if args.write:
        atomic_write_json(PACKET_OUT, packet)
    if args.apply or args.dry_run:
        report = apply_delete(dry_run=args.dry_run)
        if args.write:
            atomic_write_json(APPLY_REPORT, report)
        response: dict[str, Any] = {
            "status": report.get("status"),
            "summary": report.get("summary"),
            "report": rel(APPLY_REPORT) if args.write else None,
            "packet": rel(PACKET_OUT) if args.write else None,
        }
        print(json.dumps(report if args.pretty else response, indent=2, sort_keys=True))
        if args.validate and report.get("status") not in {"dry_run_ok", "applied_wf88_db_duplicate_source_delete"}:
            return 1
        return 0
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "packet": rel(PACKET_OUT) if args.write else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
