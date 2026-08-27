#!/usr/bin/env python3
"""Apply the approved WF88 tmp delete microbatch.

This script is intentionally narrow. It consumes
``tmp/wf88-delete-readiness-packet.json`` and only deletes rows that the packet
marks ready after exact owner approval. It copies every target to a rollback
folder before unlinking it.
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
STATE = ROOT / "state"
READINESS_PACKET = TMP / "wf88-delete-readiness-packet.json"
APPLY_REPORT = TMP / "wf88-delete-microbatch-apply-report.json"
ROLLBACK_ROOT = STATE / "tmp-lifecycle-rollback" / "wf88-tmp-delete-microbatch"

SCHEMA = "veritas.wf88_tmp_delete_microbatch_apply_report.v1"
APPROVAL_PHRASE = "Approve WF88 tmp delete microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."

AUTHORITY_BOUNDARY = {
    "approved_tmp_delete_microbatch_only": True,
    "archive_performed": False,
    "move_performed": False,
    "cron_schedule_mutation_performed": False,
    "sql_mutation_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
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


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_readiness_packet() -> dict[str, Any]:
    payload = load_json_artifact(READINESS_PACKET)
    return payload if isinstance(payload, dict) else {}


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def resolve_target(path_text: str) -> Path:
    normalized = normalize_rel(path_text)
    target = (ROOT / normalized).resolve()
    root = ROOT.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path_outside_workspace:{normalized}") from exc
    if not normalized.startswith("tmp/"):
        raise ValueError(f"path_not_in_approved_tmp_scope:{normalized}")
    return target


def ready_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(as_dict(packet.get("tmp_delete_microbatch")).get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("delete_ready_after_owner_approval") is True:
            rows.append(row_dict)
    return rows


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not rows:
        errors.append("no_delete_ready_rows")
    for row in rows:
        path_text = str(row.get("path") or "")
        try:
            target = resolve_target(path_text)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if row.get("exists") is not True:
            errors.append(f"packet_row_not_marked_existing:{path_text}")
        if int(row.get("active_reference_count") or 0) != 0:
            errors.append(f"active_references_not_zero:{path_text}")
        if as_list(row.get("protected_reasons")):
            errors.append(f"protected_reasons_not_empty:{path_text}")
        if not target.exists():
            errors.append(f"target_missing:{path_text}")
            continue
        if not target.is_file():
            errors.append(f"target_not_file:{path_text}")
            continue
        expected_hash = row.get("sha256")
        actual_hash = file_sha256(target)
        if expected_hash and actual_hash != expected_hash:
            errors.append(f"sha256_mismatch:{path_text}")
    return errors


def backup_and_delete(row: dict[str, Any], run_stamp: str) -> dict[str, Any]:
    path_text = normalize_rel(str(row.get("path") or ""))
    target = resolve_target(path_text)
    rollback = ROLLBACK_ROOT / run_stamp / Path(path_text)
    rollback.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, rollback)
    expected_hash = str(row.get("sha256") or "")
    rollback_hash = file_sha256(rollback)
    if expected_hash and rollback_hash != expected_hash:
        raise RuntimeError(f"rollback_hash_mismatch:{path_text}")
    target.unlink()
    if target.exists():
        raise RuntimeError(f"target_still_exists_after_delete:{path_text}")
    return {
        "path": path_text,
        "size_bytes": row.get("size_bytes"),
        "sha256": expected_hash,
        "rollback_copy": rel(rollback),
        "deleted_at_utc": utc_now(),
    }


def build_report(*, apply: bool, approval_phrase: str | None) -> dict[str, Any]:
    packet = load_readiness_packet()
    rows = ready_rows(packet)
    errors = validate_rows(rows)
    approval_phrase_matched = approval_phrase == APPROVAL_PHRASE
    if apply and not approval_phrase_matched:
        errors.append("approval_phrase_mismatch")

    deleted_records: list[dict[str, Any]] = []
    run_stamp = run_id()
    if apply and not errors:
        for row in rows:
            deleted_records.append(backup_and_delete(row, run_stamp))

    status = "blocked" if errors else "applied_wf88_tmp_delete_microbatch" if apply else "dry_run_ok"
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "workflow_id": "WF88",
        "source_readiness_packet": rel(READINESS_PACKET),
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_phrase_matched": approval_phrase_matched,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "delete_performed": bool(apply and not errors),
        },
        "summary": {
            "candidate_count": len(rows),
            "deleted_count": len(deleted_records),
            "deleted_bytes": sum(int(record.get("size_bytes") or 0) for record in deleted_records),
            "rollback_root": rel(ROLLBACK_ROOT / run_stamp) if deleted_records else None,
            "delete_performed": bool(deleted_records),
            "archive_performed": False,
            "cron_schedule_mutation_performed": False,
            "sql_or_finance_mutation_performed": False,
        },
        "deleted_records": deleted_records,
        "dry_run_rows": [
            {
                "path": normalize_rel(str(row.get("path") or "")),
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
                "delete_ready_after_owner_approval": row.get("delete_ready_after_owner_approval"),
            }
            for row in rows
        ],
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }
    return report


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
