#!/usr/bin/env python3
"""Archive an exactly approved tmp Python helper microbatch.

The apply path consumes ``tmp/tmp-python-helper-archive-packet.json`` and
requires the exact approval phrase embedded in that packet. It copies each
helper into a timestamped archive folder, verifies the copied hash, and only
then removes the active tmp/ source file.
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
PACKET = TMP / "tmp-python-helper-archive-packet.json"
APPLY_REPORT = TMP / "tmp-python-helper-archive-apply-report.json"
ARCHIVE_ROOT = ROOT / "09. Archive" / "tmp-python-helpers - Archived"

SCHEMA = "veritas.tmp_python_helper_archive_apply_report.v1"

AUTHORITY_BOUNDARY = {
    "approved_tmp_python_helper_archive_only": True,
    "delete_performed": False,
    "cron_schedule_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
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


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_target(path_text: str) -> Path:
    normalized = normalize_rel(path_text)
    target = (ROOT / normalized).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_workspace:{normalized}") from exc
    if not normalized.startswith("tmp/"):
        raise ValueError(f"path_not_in_tmp_scope:{normalized}")
    if "/" in normalized.removeprefix("tmp/"):
        raise ValueError(f"path_not_root_tmp_python_helper:{normalized}")
    if not normalized.endswith(".py"):
        raise ValueError(f"path_not_python_helper:{normalized}")
    return target


def load_packet() -> dict[str, Any]:
    payload = load_json_artifact(PACKET)
    return payload if isinstance(payload, dict) else {}


def ready_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(as_dict(packet.get("microbatch")).get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("archive_ready_after_owner_approval") is True:
            rows.append(row_dict)
    return rows


def microbatch_digest(rows: list[dict[str, Any]]) -> str:
    digest_rows = [
        {
            "path": row.get("path"),
            "size_bytes": row.get("size_bytes"),
            "sha256": row.get("sha256"),
            "archive_ready_after_owner_approval": row.get("archive_ready_after_owner_approval"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_rows(packet: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not rows:
        errors.append("no_archive_ready_rows")
    packet_digest = as_dict(packet.get("microbatch")).get("digest")
    actual_digest = microbatch_digest(rows)
    if packet_digest != actual_digest:
        errors.append("microbatch_digest_mismatch")
    seen: set[str] = set()
    for row in rows:
        path_text = normalize_rel(str(row.get("path") or ""))
        if path_text in seen:
            errors.append(f"duplicate_path:{path_text}")
        seen.add(path_text)
        try:
            target = resolve_target(path_text)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if row.get("exists") is not True:
            errors.append(f"packet_row_not_marked_existing:{path_text}")
        if row.get("durable_promotion_recommended") is True:
            errors.append(f"promotion_recommended_not_archive_ready:{path_text}")
        if int(row.get("active_reference_count") or 0) != 0:
            errors.append(f"active_references_not_zero:{path_text}")
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


def archive_row(row: dict[str, Any], run_stamp: str) -> dict[str, Any]:
    path_text = normalize_rel(str(row.get("path") or ""))
    target = resolve_target(path_text)
    archive_path = ARCHIVE_ROOT / run_stamp / Path(path_text)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, archive_path)
    expected_hash = str(row.get("sha256") or "")
    archive_hash = file_sha256(archive_path)
    if expected_hash and archive_hash != expected_hash:
        raise RuntimeError(f"archive_hash_mismatch:{path_text}")
    target.unlink()
    if target.exists():
        raise RuntimeError(f"target_still_exists_after_archive:{path_text}")
    return {
        "path": path_text,
        "size_bytes": row.get("size_bytes"),
        "sha256": expected_hash,
        "archive_copy": rel(archive_path),
        "archived_at_utc": utc_now(),
    }


def build_report(*, apply: bool, approval_phrase: str | None) -> dict[str, Any]:
    packet = load_packet()
    rows = ready_rows(packet)
    errors = validate_rows(packet, rows)
    required_phrase = as_dict(as_dict(packet.get("summary"))).get("approval_phrase") or as_dict(packet.get("microbatch")).get("approval_phrase")
    approval_phrase_matched = approval_phrase == required_phrase
    if apply and not approval_phrase_matched:
        errors.append("approval_phrase_mismatch")

    archived_records: list[dict[str, Any]] = []
    stamp = run_id()
    if apply and not errors:
        for row in rows:
            archived_records.append(archive_row(row, stamp))

    status = "blocked" if errors else "applied_tmp_python_helper_archive" if apply else "dry_run_ok"
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "source_packet": rel(PACKET),
        "approval_phrase_required": required_phrase,
        "approval_phrase_matched": approval_phrase_matched,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "archive_performed": bool(apply and not errors),
            "move_performed": bool(apply and not errors),
        },
        "summary": {
            "candidate_count": len(rows),
            "archived_count": len(archived_records),
            "archived_bytes": sum(int(record.get("size_bytes") or 0) for record in archived_records),
            "archive_root": rel(ARCHIVE_ROOT / stamp) if archived_records else None,
            "archive_performed": bool(archived_records),
            "delete_performed": False,
            "cron_schedule_mutation_performed": False,
            "sql_or_finance_mutation_performed": False,
        },
        "archived_records": archived_records,
        "dry_run_rows": [
            {
                "path": normalize_rel(str(row.get("path") or "")),
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
                "archive_ready_after_owner_approval": row.get("archive_ready_after_owner_approval"),
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
