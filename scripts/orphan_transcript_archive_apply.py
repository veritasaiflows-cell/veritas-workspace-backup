#!/usr/bin/env python3
"""Apply an exactly approved orphan transcript archive microbatch.

This consumes ``tmp/orphan-transcript-inventory-packet.json``. It never reads
transcript content as text, previews content, deletes files, or mutates
``sessions.json``. The only apply action is a hash-checked rename from the
packet source path to the packet's proposed ``.deleted.<stamp>`` archive path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = WORKSPACE_ROOT / "tmp" / "orphan-transcript-inventory-packet.json"
DEFAULT_REPORT = WORKSPACE_ROOT / "tmp" / "orphan-transcript-archive-apply-report.json"

PACKET_SCHEMA = "veritas.orphan_transcript_inventory_packet.v1"
REPORT_SCHEMA = "veritas.orphan_transcript_archive_apply_report.v1"

AUTHORITY_BOUNDARY = {
    "approved_orphan_transcript_archive_only": True,
    "content_preview_performed": False,
    "delete_performed": False,
    "doctor_fix_performed": False,
    "sessions_index_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
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


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def microbatch_digest(rows: list[dict[str, Any]]) -> str:
    digest_rows = [
        {
            "path": row.get("path"),
            "size_bytes": row.get("size_bytes"),
            "mtime_utc": row.get("mtime_utc"),
            "sha256": row.get("sha256"),
            "proposed_archive_path": row.get("proposed_archive_path"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def openclaw_home_from_packet(packet: dict[str, Any]) -> Path:
    sessions_root_text = as_dict(packet.get("source_artifacts")).get("sessions_root")
    if sessions_root_text:
        sessions_root = Path(str(sessions_root_text)).resolve()
        if sessions_root.name.lower() == "sessions" and sessions_root.parent.name.lower() == "main":
            return sessions_root.parent.parent.parent
    return WORKSPACE_ROOT.parent


def resolve_openclaw_path(openclaw_home: Path, path_text: str) -> Path:
    normalized = normalize_rel(path_text)
    target = (openclaw_home / normalized).resolve()
    try:
        target.relative_to(openclaw_home.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_openclaw_home:{normalized}") from exc
    return target


def validate_row_paths(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    path_text = normalize_rel(str(row.get("path") or ""))
    archive_text = normalize_rel(str(row.get("proposed_archive_path") or ""))
    if not path_text.startswith("agents/main/sessions/"):
        errors.append(f"path_outside_main_sessions:{path_text}")
    if not path_text.endswith(".jsonl") or path_text.endswith(".trajectory.jsonl") or ".deleted." in path_text:
        errors.append(f"path_not_bare_transcript:{path_text}")
    if archive_text != f"{path_text}.deleted.{archive_text.rsplit('.deleted.', 1)[-1]}" if ".deleted." in archive_text else True:
        errors.append(f"archive_path_not_source_deleted_suffix:{archive_text}")
    if not archive_text.startswith("agents/main/sessions/") or ".jsonl.deleted." not in archive_text:
        errors.append(f"archive_path_not_in_main_sessions_deleted_suffix:{archive_text}")
    return errors


def packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(as_dict(packet.get("microbatch")).get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("archive_ready_after_exact_owner_approval") is True:
            rows.append(row_dict)
    return rows


def expected_approval_phrase(digest: str) -> str:
    return (
        f"Approve orphan transcript archive microbatch {digest} exactly as listed in "
        "tmp/orphan-transcript-inventory-packet.json."
    )


def prevalidate(packet: dict[str, Any], *, approval_phrase: str | None, apply: bool) -> tuple[list[str], list[dict[str, Any]], Path, str]:
    errors: list[str] = []
    if packet.get("schema") != PACKET_SCHEMA:
        errors.append("packet_schema_mismatch")
    rows = packet_rows(packet)
    if not rows:
        errors.append("no_archive_ready_rows")
    digest = microbatch_digest(rows)
    packet_digest = as_dict(packet.get("microbatch")).get("digest")
    if packet_digest != digest:
        errors.append("microbatch_digest_mismatch")
    required_phrase = expected_approval_phrase(digest)
    packet_phrase = as_dict(packet.get("microbatch")).get("approval_phrase") or as_dict(packet.get("summary")).get("approval_phrase")
    if packet_phrase != required_phrase:
        errors.append("packet_approval_phrase_mismatch")
    approval_phrase_matched = approval_phrase == required_phrase
    if apply and not approval_phrase_matched:
        errors.append("approval_phrase_mismatch")
    if approval_phrase is not None and not approval_phrase_matched:
        errors.append("provided_approval_phrase_mismatch")

    openclaw_home = openclaw_home_from_packet(packet)
    seen: set[str] = set()
    prepared_rows: list[dict[str, Any]] = []
    for row in rows:
        path_text = normalize_rel(str(row.get("path") or ""))
        archive_text = normalize_rel(str(row.get("proposed_archive_path") or ""))
        if path_text in seen:
            errors.append(f"duplicate_path:{path_text}")
        seen.add(path_text)
        errors.extend(validate_row_paths(row))
        if int(row.get("active_reference_count") or 0) != 0:
            errors.append(f"active_reference_count_not_zero:{path_text}")
        source = resolve_openclaw_path(openclaw_home, path_text)
        archive = resolve_openclaw_path(openclaw_home, archive_text)
        if archive == source:
            errors.append(f"archive_path_equals_source:{path_text}")
        if not source.exists():
            errors.append(f"source_missing:{path_text}")
            continue
        if not source.is_file():
            errors.append(f"source_not_file:{path_text}")
            continue
        if archive.exists():
            errors.append(f"archive_target_exists:{archive_text}")
        expected_size = int(row.get("size_bytes") or -1)
        actual_size = source.stat().st_size
        if expected_size != actual_size:
            errors.append(f"size_mismatch:{path_text}")
        expected_hash = str(row.get("sha256") or "")
        actual_hash = file_sha256(source)
        if expected_hash != actual_hash:
            errors.append(f"sha256_mismatch:{path_text}")
        prepared_rows.append(
            {
                "path": path_text,
                "proposed_archive_path": archive_text,
                "source_abs": str(source),
                "archive_abs": str(archive),
                "size_bytes": actual_size,
                "sha256": actual_hash,
                "precheck": "ok",
            }
        )
    return errors, prepared_rows, openclaw_home, required_phrase


def apply_archive(prepared_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    archived: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in prepared_rows:
        source = Path(str(row["source_abs"]))
        archive = Path(str(row["archive_abs"]))
        archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            source.rename(archive)
        except OSError as exc:
            errors.append(f"rename_failed:{row['path']}:{exc}")
            break
        if source.exists():
            errors.append(f"source_still_exists_after_rename:{row['path']}")
            break
        if not archive.exists():
            errors.append(f"archive_missing_after_rename:{row['proposed_archive_path']}")
            break
        archive_hash = file_sha256(archive)
        archive_size = archive.stat().st_size
        if archive_hash != row["sha256"]:
            errors.append(f"archive_sha256_mismatch:{row['proposed_archive_path']}")
            break
        if archive_size != row["size_bytes"]:
            errors.append(f"archive_size_mismatch:{row['proposed_archive_path']}")
            break
        archived.append(
            {
                "path": row["path"],
                "archive_path": row["proposed_archive_path"],
                "size_bytes": archive_size,
                "sha256": archive_hash,
                "source_absent": True,
                "archive_exists": True,
                "archived_at_utc": utc_now(),
                "rollback_instruction": "verify archived sha256 matches this report, then rename archive_path back to path",
            }
        )
    return archived, errors


def build_report(
    *,
    packet_path: Path,
    approval_phrase: str | None,
    apply: bool,
) -> dict[str, Any]:
    packet = as_dict(load_json(packet_path))
    errors, prepared_rows, openclaw_home, required_phrase = prevalidate(packet, approval_phrase=approval_phrase, apply=apply)
    archived_rows: list[dict[str, Any]] = []
    apply_errors: list[str] = []
    if apply and not errors:
        archived_rows, apply_errors = apply_archive(prepared_rows)
        errors.extend(apply_errors)

    digest = as_dict(packet.get("microbatch")).get("digest")
    total_bytes = sum(int(row.get("size_bytes") or 0) for row in prepared_rows)
    archive_performed = bool(apply and not errors and archived_rows)
    status = "blocked" if errors else "applied_orphan_transcript_archive" if apply else "dry_run_ok"
    validation_status = "ok" if not errors else "blocked"
    report = {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "source_packet": rel(packet_path),
        "source_packet_digest": digest,
        "approval_phrase_required": required_phrase,
        "approval_phrase_matched": approval_phrase == required_phrase,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "archive_performed": archive_performed,
            "rename_performed": archive_performed,
            "move_performed": archive_performed,
        },
        "summary": {
            "candidate_count": len(prepared_rows),
            "prevalidated_count": len(prepared_rows) if not errors or not apply_errors else len(prepared_rows),
            "archived_count": len(archived_rows),
            "candidate_bytes": total_bytes,
            "archived_bytes": sum(int(row.get("size_bytes") or 0) for row in archived_rows),
            "archive_performed": archive_performed,
            "delete_performed": False,
            "content_preview_performed": False,
            "sessions_index_mutation_performed": False,
            "openclaw_home": str(openclaw_home),
        },
        "dry_run_rows": [
            {
                "path": row["path"],
                "proposed_archive_path": row["proposed_archive_path"],
                "size_bytes": row["size_bytes"],
                "sha256": row["sha256"],
                "precheck": row["precheck"],
            }
            for row in prepared_rows
        ],
        "archived_rows": archived_rows,
        "rollback_plan": {
            "strategy": "rename_each_archived_file_back_to_original_path",
            "pre_restore_check": "verify archive_path exists and sha256 matches this report",
            "post_restore_check": "verify original path exists, sha256 matches this report, and archive_path is absent",
            "sessions_index_mutation_required": False,
        },
        "validation": {"status": validation_status, "errors": errors, "warnings": []},
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--approval-phrase")
    parser.add_argument("--out", default=str(DEFAULT_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(packet_path=Path(args.packet), approval_phrase=args.approval_phrase, apply=bool(args.apply))
    out_path = Path(args.out)
    if args.write:
        atomic_write_json(out_path, report)
    response = report if args.pretty else {
        "status": report.get("status"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "out": rel(out_path) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
