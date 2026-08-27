#!/usr/bin/env python3
"""Apply an exact owner-approved cleanup family microbatch."""
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
PACKET = TMP / "cleanup-autopilot-family-packets.json"
APPLY_REPORT = TMP / "cleanup-autopilot-family-apply-report.json"
ROLLBACK_ROOT = ROOT / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-family"
SCHEMA = "veritas.cleanup_autopilot_family_apply_report.v1"

AUTHORITY_BOUNDARY = {
    "approved_exact_family_microbatch_only": True,
    "broad_tmp_cleanup_performed": False,
    "archive_performed": False,
    "move_performed": False,
    "runtime_stop_or_mutation_performed": False,
    "db_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "config_auth_runtime_mutation_performed": False,
    "finance_canon_or_portfolio_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_record_bytes(row: dict[str, Any]) -> int:
    value = row.get("bytes")
    if value is None:
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def resolve_target(path_text: str) -> Path:
    normalized = normalize_rel(path_text)
    target = (ROOT / normalized).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_workspace:{normalized}") from exc
    if not normalized.startswith("tmp/"):
        raise ValueError(f"path_not_in_tmp_scope:{normalized}")
    return target


def load_packet() -> dict[str, Any]:
    payload = load_json_artifact(PACKET)
    return payload if isinstance(payload, dict) else {}


def find_family(packet: dict[str, Any], family_id: str) -> dict[str, Any]:
    for family in as_list(packet.get("families")):
        if isinstance(family, dict) and family.get("family_id") == family_id:
            return family
    return {}


def validate_family(family: dict[str, Any], approval_phrase: str | None) -> list[str]:
    errors: list[str] = []
    family_id = str(family.get("family_id") or "")
    if not family:
        return ["family_not_found"]
    if family.get("approval_ready_after_owner_phrase") is not True:
        errors.append(f"family_not_approval_ready:{family_id}")
    if family.get("delete_allowed_now") is not False:
        errors.append(f"family_packet_must_not_grant_delete_now:{family_id}")
    manifest = as_dict(family.get("record_manifest"))
    if manifest.get("complete_manifest_in_packet") is not True:
        errors.append(f"incomplete_record_manifest:{family_id}")
    if manifest.get("content_sha256_included") is not True:
        errors.append(f"content_sha256_required:{family_id}")
    reference = as_dict(family.get("reference_check"))
    if reference.get("status") not in {"ok", "historical_references_only"}:
        errors.append(f"reference_status_not_clean:{family_id}:{reference.get('status')}")
    if int(reference.get("active_hit_path_count") or 0) != 0:
        errors.append(f"active_reference_hits_not_zero:{family_id}")
    expected_phrase = as_dict(family.get("approval_surface")).get("approval_phrase")
    if not expected_phrase:
        errors.append(f"approval_phrase_missing:{family_id}")
    if approval_phrase != expected_phrase:
        errors.append("approval_phrase_mismatch")
    for row in as_list(family.get("records")):
        if not isinstance(row, dict):
            errors.append(f"invalid_record:{family_id}")
            continue
        path_text = normalize_rel(str(row.get("path") or ""))
        try:
            target = resolve_target(path_text)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not target.exists():
            errors.append(f"target_missing:{path_text}")
            continue
        if not target.is_file():
            errors.append(f"target_not_file:{path_text}")
            continue
        if target.stat().st_size != expected_record_bytes(row):
            errors.append(f"size_mismatch:{path_text}")
        if file_sha256(target) != row.get("sha256"):
            errors.append(f"sha256_mismatch:{path_text}")
    return errors


def backup_and_delete(row: dict[str, Any], run_stamp: str, family_id: str) -> dict[str, Any]:
    path_text = normalize_rel(str(row.get("path") or ""))
    target = resolve_target(path_text)
    rollback = ROLLBACK_ROOT / family_id / run_stamp / Path(path_text)
    rollback.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, rollback)
    expected_hash = str(row.get("sha256") or "")
    if file_sha256(rollback) != expected_hash:
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


def build_report(*, family_id: str, apply: bool, approval_phrase: str | None) -> dict[str, Any]:
    packet = load_packet()
    family = find_family(packet, family_id)
    errors = validate_family(family, approval_phrase)
    run_stamp = run_id()
    deleted: list[dict[str, Any]] = []
    if apply and not errors:
        for row in as_list(family.get("records")):
            if isinstance(row, dict):
                deleted.append(backup_and_delete(row, run_stamp, family_id))
    status = "blocked" if errors else "applied_cleanup_autopilot_family_microbatch" if apply else "dry_run_ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "source_packet": rel(PACKET),
        "family_id": family_id,
        "approval_phrase_required": as_dict(family.get("approval_surface")).get("approval_phrase") if family else None,
        "approval_phrase_matched": bool(family) and approval_phrase == as_dict(family.get("approval_surface")).get("approval_phrase"),
        "authority_boundary": {**AUTHORITY_BOUNDARY, "delete_performed": bool(deleted)},
        "summary": {
            "candidate_count": len(as_list(family.get("records"))) if family else 0,
            "candidate_bytes": int(family.get("bytes") or 0) if family else 0,
            "deleted_count": len(deleted),
            "deleted_bytes": sum(int(row.get("bytes") or 0) for row in deleted),
            "rollback_root": rel(ROLLBACK_ROOT / family_id / run_stamp) if deleted else None,
            "delete_performed": bool(deleted),
        },
        "deleted_records": deleted,
        "dry_run_rows": [
            {
                "path": normalize_rel(str(row.get("path") or "")),
                "bytes": row.get("bytes"),
                "sha256": row.get("sha256"),
            }
            for row in as_list(family.get("records"))
            if isinstance(row, dict)
        ],
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--approval-phrase")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(family_id=args.family_id, apply=bool(args.apply), approval_phrase=args.approval_phrase)
    if args.write:
        atomic_write_json(APPLY_REPORT, report)
    response = report if args.pretty else {
        "status": report.get("status"),
        "family_id": report.get("family_id"),
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
