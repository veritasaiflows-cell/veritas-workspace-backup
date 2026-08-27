#!/usr/bin/env python3
"""Build the review-only Cleanup Autopilot Phase 1 packet.

This packet prepares a narrow tmp-cleanup approval surface. It does not delete,
archive, move, or apply cleanup candidates. Destructive cleanup remains blocked
until Randall approves an exact microbatch after this packet exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "cleanup-autopilot-phase1.json"
OUT_MD = TMP / "cleanup-autopilot-phase1.md"
SCHEMA = "veritas.cleanup_autopilot_phase1.v1"

INPUTS = {
    "tmp_cleanup_report": TMP / "tmp-cleanup-report.json",
    "tmp_lifecycle_guard": TMP / "tmp-lifecycle-guard.json",
    "wf88_cleanup_plan": TMP / "wf88-retired-surface-cleanup-plan.json",
    "wf88_deletion_prep": TMP / "wf88-deletion-approval-prep-packet.json",
    "workspace_automation_approval": TMP / "workspace-automation-approval-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "approval_packet_only": True,
    "delete_archive_move_allowed": False,
    "cleanup_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "09. Archive",
    "node_modules",
    "tmp",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def input_record(path: Path, payload: dict[str, Any], required: bool = True) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def is_safe_tmp_atomic_candidate(record: dict[str, Any]) -> bool:
    path = str(record.get("path") or "")
    name = Path(path).name
    return (
        path.startswith("tmp/")
        and record.get("kind") == "file"
        and name.endswith(".tmp")
        and bool(record.get("sha256"))
    )


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


def reference_files(max_files: int = 5000) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for path in ROOT.rglob("*"):
        if len(files) >= max_files:
            truncated = True
            break
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_PARTS for part in rel_parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return files, truncated


def scan_reference(candidate: dict[str, Any], files: list[Path], truncated: bool) -> dict[str, Any]:
    target_path = str(candidate.get("path") or "")
    target_name = Path(target_path).name
    exact_hits: list[str] = []
    basename_hits: list[str] = []

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_path = rel(path)
        if target_path and target_path in text:
            exact_hits.append(rel_path)
        if target_name and target_name in text:
            basename_hits.append(rel_path)

    return {
        "status": "ok" if not exact_hits and not basename_hits and not truncated else "blocked",
        "exact_reference_count": len(exact_hits),
        "basename_reference_count": len(basename_hits),
        "exact_reference_paths": exact_hits[:20],
        "basename_reference_paths": basename_hits[:20],
        "reference_file_count": len(files),
        "reference_scan_truncated": truncated,
    }


def build_packet(artifacts: dict[str, dict[str, Any]], microbatch_limit: int = 10, reference_check: bool = True) -> dict[str, Any]:
    cleanup_report = artifacts["tmp_cleanup_report"]
    cleanup_summary = as_dict(cleanup_report.get("summary"))
    candidates = [record for record in as_list(cleanup_report.get("candidates")) if isinstance(record, dict)]
    atomic_candidates = [record for record in candidates if is_safe_tmp_atomic_candidate(record)]
    proposed = atomic_candidates[: max(0, microbatch_limit)]

    files: list[Path] = []
    truncated = False
    if reference_check and proposed:
        files, truncated = reference_files()

    checked: list[dict[str, Any]] = []
    for record in proposed:
        reference = scan_reference(record, files, truncated) if reference_check else {"status": "not_run"}
        checked.append({**record, "reference_check": reference})

    approval_ready = [
        record
        for record in checked
        if as_dict(record.get("reference_check")).get("status") == "ok"
    ]
    digest = packet_digest(approval_ready)

    status = "owner_approval_ready_no_apply" if approval_ready else "review_packet_ready_no_apply"
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": (
            "Review-only Cleanup Autopilot Phase 1 packet for narrow, reference-checked tmp cleanup microbatches."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {name: rel(path) for name, path in INPUTS.items()},
        "source_status": [
            input_record(INPUTS[name], artifacts[name], required=(name == "tmp_cleanup_report"))
            for name in INPUTS
        ],
        "summary": {
            "tmp_cleanup_mode": cleanup_report.get("mode"),
            "tmp_cleanup_retention_days": cleanup_report.get("retention_days"),
            "cleanup_candidate_count": cleanup_summary.get("eligible_count", len(candidates)),
            "cleanup_candidate_digest": cleanup_summary.get("candidate_digest"),
            "cleanup_moved_count": cleanup_summary.get("moved_count"),
            "protected_violation_count": cleanup_summary.get("protected_violation_count"),
            "safe_atomic_tmp_candidate_count": len(atomic_candidates),
            "microbatch_review_count": len(checked),
            "microbatch_owner_approval_ready_count": len(approval_ready),
            "microbatch_digest": digest,
        },
        "phase1_cadence": {
            "recommended_name": "Runtime - Cleanup Autopilot Phase 1 Review",
            "recommended_schedule": "weekly after the Sunday cleanup dry-run",
            "recommended_timezone": "America/Phoenix",
            "commands": [
                "python scripts\\tmp_cleanup.py --dry-run --days 7",
                "python scripts\\cleanup_autopilot_phase1.py --write --write-md --validate",
                "python scripts\\workspace_automation_approval_packet.py --write --write-md --validate",
            ],
            "no_apply_assertion": True,
        },
        "approval_surface": {
            "destructive_action_ready": False,
            "approval_required_after_packet_review": True,
            "approval_phrase_for_future_apply": (
                f"Approve Cleanup Autopilot Phase 1 tmp microbatch {digest} exactly as listed."
            )
            if approval_ready
            else None,
            "blocked_until": [
                "Owner reviews exact microbatch records in this packet.",
                "A separate apply path validates packet digest, hashes, paths, and rollback before moving anything.",
            ],
        },
        "microbatch_candidates": checked,
        "validation": validate_packet_fields(
            cleanup_report=cleanup_report,
            approval_ready=approval_ready,
            checked=checked,
        ),
    }
    return packet


def validate_packet_fields(
    cleanup_report: dict[str, Any], approval_ready: list[dict[str, Any]], checked: list[dict[str, Any]]
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    cleanup_summary = as_dict(cleanup_report.get("summary"))

    false_flags = [
        "delete_archive_move_allowed",
        "cleanup_apply_allowed",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ]
    for flag in false_flags:
        if AUTHORITY_BOUNDARY.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")

    if cleanup_report.get("mode") not in {None, "dry-run"}:
        errors.append("tmp_cleanup_report must be dry-run for Phase 1 review packet")
    if cleanup_summary.get("moved_count") not in {None, 0}:
        errors.append("tmp_cleanup_report moved_count must be zero")
    if cleanup_summary.get("protected_violation_count") not in {None, 0}:
        errors.append("tmp_cleanup_report protected_violation_count must be zero")
    if checked and not approval_ready:
        warnings.append("microbatch candidates exist but reference checks did not clear")

    return {
        "status": "error" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    approval = as_dict(packet.get("approval_surface"))
    lines = [
        "# Cleanup Autopilot Phase 1",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- Cleanup candidates: {summary.get('cleanup_candidate_count')}",
        f"- Safe atomic tmp candidates: {summary.get('safe_atomic_tmp_candidate_count')}",
        f"- Review microbatch count: {summary.get('microbatch_review_count')}",
        f"- Owner-approval-ready count: {summary.get('microbatch_owner_approval_ready_count')}",
        f"- Microbatch digest: {summary.get('microbatch_digest')}",
        "",
        "## Boundary",
        "",
        "- Review-only packet.",
        "- No delete, archive, move, apply, config/runtime mutation, finance mutation, or execution authority.",
        "- Tmp cleanup apply remains blocked until an exact post-packet owner approval and apply validator exist.",
        "",
        "## Future Approval Phrase",
        "",
        approval.get("approval_phrase_for_future_apply") or "No microbatch is owner-approval-ready yet.",
    ]
    candidates = [record for record in as_list(packet.get("microbatch_candidates")) if isinstance(record, dict)]
    if candidates:
        lines.extend(["", "## Candidate Preview", ""])
        for record in candidates[:10]:
            reference = as_dict(record.get("reference_check"))
            lines.append(
                f"- {record.get('path')} | bytes={record.get('bytes')} | refs={reference.get('status')}"
            )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the review-only Cleanup Autopilot Phase 1 packet.")
    parser.add_argument("--write", action="store_true", help="Write tmp/cleanup-autopilot-phase1.json.")
    parser.add_argument("--write-md", action="store_true", help="Write tmp/cleanup-autopilot-phase1.md.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if packet validation fails.")
    parser.add_argument("--microbatch-limit", type=int, default=10, help="Maximum safe tmp atomic candidates to review.")
    parser.add_argument("--no-reference-check", action="store_true", help="Skip active-workspace reference checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = {name: load_optional(path) for name, path in INPUTS.items()}
    packet = build_packet(
        artifacts,
        microbatch_limit=args.microbatch_limit,
        reference_check=not args.no_reference_check,
    )

    if args.write:
        atomic_write_json(OUT_JSON, packet)
    if args.write_md:
        atomic_write_text(OUT_MD, render_markdown(packet))

    print(json.dumps({"status": packet["status"], "summary": packet["summary"], "validation": packet["validation"]}, indent=2))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
