#!/usr/bin/env python3
"""Apply an exact owner-approved Cleanup Autopilot Phase 1 tmp microbatch."""
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
STATE = ROOT / "state"
PACKET = TMP / "cleanup-autopilot-phase1.json"
APPLY_REPORT = TMP / "cleanup-autopilot-phase1-apply-report.json"
ROLLBACK_ROOT = STATE / "tmp-lifecycle-rollback" / "cleanup-autopilot-phase1"
SCHEMA = "veritas.cleanup_autopilot_phase1_apply_report.v1"
APPROVAL_PHRASE = (
    "Approve Cleanup Autopilot Phase 1 tmp microbatch "
    "787c01e87bf54c8bfd9b6db6e28e9d7a3290283fef91f8e0869048db78bb5c64 exactly as listed."
)

AUTHORITY_BOUNDARY = {
    "approved_exact_tmp_microbatch_only": True,
    "broad_tmp_cleanup_allowed": False,
    "archive_performed": False,
    "move_performed": False,
    "cron_schedule_mutation_performed": False,
    "config_auth_runtime_mutation_performed": False,
    "finance_canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "external_delivery_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_target(path_text: str) -> Path:
    normalized = normalize_rel(path_text)
    target = (ROOT / normalized).resolve()
    root = ROOT.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path_outside_workspace:{normalized}") from exc
    if not normalized.startswith("tmp/"):
        raise ValueError(f"path_not_in_tmp_scope:{normalized}")
    return target


def packet_digest(records: list[dict[str, Any]]) -> str:
    payload = [
        {
            "path": record.get("path"),
            "sha256": record.get("sha256"),
            "bytes": record.get("bytes"),
            "newest_mtime_utc": record.get("newest_mtime_utc"),
        }
        for record in records
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_packet() -> dict[str, Any]:
    payload = load_json_artifact(PACKET)
    return payload if isinstance(payload, dict) else {}


def approved_records(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [record for record in as_list(packet.get("microbatch_candidates")) if isinstance(record, dict)]
    return [row for row in rows if as_dict(row.get("reference_check")).get("status") == "ok"]


def validate_records(packet: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    summary = as_dict(packet.get("summary"))
    expected_digest = summary.get("microbatch_digest")
    actual_digest = packet_digest(records)
    if not records:
        errors.append("no_reference_checked_microbatch_records")
    if expected_digest != actual_digest:
        errors.append(f"microbatch_digest_mismatch:{actual_digest}!={expected_digest}")
    if summary.get("microbatch_owner_approval_ready_count") != len(records):
        errors.append("approval_ready_count_mismatch")
    if packet.get("status") != "owner_approval_ready_no_apply":
        errors.append(f"packet_status_not_owner_ready:{packet.get('status')}")
    if as_dict(packet.get("approval_surface")).get("approval_phrase_for_future_apply") != APPROVAL_PHRASE:
        errors.append("packet_approval_phrase_mismatch")

    for row in records:
        path_text = normalize_rel(str(row.get("path") or ""))
        reference = as_dict(row.get("reference_check"))
        try:
            target = resolve_target(path_text)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if reference.get("exact_reference_count") not in {0, None}:
            errors.append(f"exact_references_not_zero:{path_text}")
        if reference.get("basename_reference_count") not in {0, None}:
            errors.append(f"basename_references_not_zero:{path_text}")
        if not target.exists():
            errors.append(f"target_missing:{path_text}")
            continue
        if not target.is_file():
            errors.append(f"target_not_file:{path_text}")
            continue
        actual_hash = file_sha256(target)
        if actual_hash != row.get("sha256"):
            errors.append(f"sha256_mismatch:{path_text}")
        if target.stat().st_size != int(row.get("bytes") or -1):
            errors.append(f"size_mismatch:{path_text}")
    return errors


def backup_and_delete(row: dict[str, Any], run_stamp: str) -> dict[str, Any]:
    path_text = normalize_rel(str(row.get("path") or ""))
    target = resolve_target(path_text)
    rollback = ROLLBACK_ROOT / run_stamp / Path(path_text)
    rollback.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, rollback)
    rollback_hash = file_sha256(rollback)
    expected_hash = str(row.get("sha256") or "")
    if rollback_hash != expected_hash:
        raise RuntimeError(f"rollback_hash_mismatch:{path_text}")
    target.unlink()
    if target.exists():
        raise RuntimeError(f"target_still_exists_after_delete:{path_text}")
    return {
        "path": path_text,
        "bytes": row.get("bytes"),
        "sha256": expected_hash,
        "rollback_copy": rel(rollback),
        "deleted_at_utc": utc_now(),
    }


def build_report(*, apply: bool, approval_phrase: str | None) -> dict[str, Any]:
    packet = load_packet()
    records = approved_records(packet)
    errors = validate_records(packet, records)
    approval_phrase_matched = approval_phrase == APPROVAL_PHRASE
    if apply and not approval_phrase_matched:
        errors.append("approval_phrase_mismatch")

    run_stamp = run_id()
    deleted_records: list[dict[str, Any]] = []
    if apply and not errors:
        for row in records:
            deleted_records.append(backup_and_delete(row, run_stamp))

    status = "blocked" if errors else "applied_cleanup_autopilot_phase1_microbatch" if apply else "dry_run_ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "source_packet": rel(PACKET),
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_phrase_matched": approval_phrase_matched,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "delete_performed": bool(deleted_records),
        },
        "summary": {
            "candidate_count": len(records),
            "deleted_count": len(deleted_records),
            "deleted_bytes": sum(int(record.get("bytes") or 0) for record in deleted_records),
            "rollback_root": rel(ROLLBACK_ROOT / run_stamp) if deleted_records else None,
            "delete_performed": bool(deleted_records),
            "broad_tmp_cleanup_performed": False,
        },
        "deleted_records": deleted_records,
        "dry_run_rows": [
            {
                "path": normalize_rel(str(record.get("path") or "")),
                "bytes": record.get("bytes"),
                "sha256": record.get("sha256"),
                "reference_check": record.get("reference_check"),
            }
            for record in records
        ],
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approval-phrase")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(apply=bool(args.apply), approval_phrase=args.approval_phrase)
    if args.write:
        atomic_write_json(APPLY_REPORT, report)
    response = report if args.pretty else {
        "status": report.get("status"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "out": rel(APPLY_REPORT) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
