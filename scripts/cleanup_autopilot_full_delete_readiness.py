#!/usr/bin/env python3
"""Build a staged readiness packet for reducing tmp/ toward the full 3GB target.

This script does not delete, move, or archive anything. It inventories tmp/,
classifies cleanup families, and prepares exact next-step approval surfaces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "cleanup-autopilot-full-delete-readiness.json"
OUT_MD = TMP / "cleanup-autopilot-full-delete-readiness.md"
STALE_TEXT_APPLY_WRAPPER = ROOT / "scripts" / "cleanup_autopilot_stale_text_apply.py"
SCHEMA = "veritas.cleanup_autopilot_full_delete_readiness.v1"

INPUTS = {
    "tmp_lifecycle_guard": TMP / "tmp-lifecycle-guard.json",
    "tmp_cleanup_report": TMP / "tmp-cleanup-report.json",
    "phase1_packet": TMP / "cleanup-autopilot-phase1.json",
    "phase1_apply_report": TMP / "cleanup-autopilot-phase1-apply-report.json",
    "cron_control": TMP / "cron-control-packet.json",
    "cron_freshness": TMP / "cron-freshness-spine.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "readiness_packet_only": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "broad_tmp_cleanup_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

SAFE_TEXT_SUFFIXES = {".csv", ".html", ".json", ".jsonl", ".log", ".md", ".txt"}
DB_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".wal", ".shm"}
PROTECTED_NAMES = {
    "tmp-cleanup-report.json",
    "cleanup-autopilot-phase1.json",
    "cleanup-autopilot-phase1.md",
    "cleanup-autopilot-phase1-apply-report.json",
    "cleanup-autopilot-full-delete-readiness.json",
    "cleanup-autopilot-full-delete-readiness.md",
}
PROTECTED_DIRS = {
    "entry-band-data",
    "entry-band-reports",
    "reports",
}
REFERENCE_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".ps1", ".py", ".sql", ".txt", ".yaml", ".yml"}
REFERENCE_SKIP_PARTS = {
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
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
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


def input_record(path: Path, payload: dict[str, Any], required: bool = False) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def file_age_days(path: Path, now: datetime) -> float:
    return max(0.0, (now.timestamp() - path.stat().st_mtime) / 86400.0)


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def referenced_tmp_paths(artifacts: dict[str, dict[str, Any]]) -> set[str]:
    references: set[str] = set()
    for artifact_name in ("cron_control", "cron_freshness"):
        payload = artifacts.get(artifact_name, {})
        for job in as_list(as_dict(payload.get("freshness")).get("jobs")) + as_list(payload.get("jobs")):
            job_dict = as_dict(job)
            for artifact in as_list(job_dict.get("expected_artifacts")):
                path = as_dict(artifact).get("path")
                if isinstance(path, str) and path.startswith("tmp/"):
                    references.add(path.replace("\\", "/"))
            for artifact in as_list(job_dict.get("artifacts")):
                path = as_dict(artifact).get("path")
                if isinstance(path, str) and path.startswith("tmp/"):
                    references.add(path.replace("\\", "/"))
    return references


def classify_path(path: Path, now: datetime, references: set[str]) -> dict[str, Any]:
    relative = rel(path)
    age_days = round(file_age_days(path, now), 3)
    suffix = path.suffix.lower()
    protected_reasons: list[str] = []
    parts = path.relative_to(TMP).parts
    if relative in references:
        protected_reasons.append("referenced_by_cron_or_control")
    if path.name in PROTECTED_NAMES:
        protected_reasons.append("cleanup_autopilot_owner_surface")
    if parts and parts[0] in PROTECTED_DIRS:
        protected_reasons.append("protected_tmp_owner_dir")
    if suffix in DB_SUFFIXES or relative.endswith((".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm")):
        protected_reasons.append("database_family_requires_db_lifecycle_packet")
    if "\\node_modules\\" in str(path) or "/node_modules/" in relative:
        protected_reasons.append("vendor_cache_or_dependency_tree_requires_family_packet")

    if protected_reasons:
        family = "protected_or_family_packet_required"
    elif path.name.endswith(".tmp"):
        family = "atomic_tmp_ready_family"
    elif suffix in SAFE_TEXT_SUFFIXES and age_days >= 14:
        family = "stale_generated_text_review_family"
    elif age_days < 14:
        family = "fresh_or_recent_hold"
    else:
        family = "unknown_review_required"

    return {
        "path": relative,
        "suffix": suffix,
        "bytes": path.stat().st_size,
        "age_days": age_days,
        "last_write_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "cleanup_family": family,
        "protected_reasons": protected_reasons,
    }


def directory_rollups(files: list[Path], limit: int = 20) -> list[dict[str, Any]]:
    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for path in files:
        parts = path.relative_to(TMP).parts
        key = f"tmp/{parts[0]}" if parts else "tmp"
        totals[key] += path.stat().st_size
        counts[key] += 1
    rows = [
        {"path": key, "bytes": value, "mb": round(value / (1024 * 1024), 3), "file_count": counts[key]}
        for key, value in totals.items()
    ]
    return sorted(rows, key=lambda row: (-int(row["bytes"]), row["path"]))[:limit]


def reference_files(max_files: int = 5000) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for path in ROOT.rglob("*"):
        if len(files) >= max_files:
            truncated = True
            break
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(ROOT).parts
        except ValueError:
            continue
        if any(part in REFERENCE_SKIP_PARTS for part in rel_parts):
            continue
        if path.suffix.lower() not in REFERENCE_SUFFIXES:
            continue
        files.append(path)
    return files, truncated


def scan_reference(row: dict[str, Any], files: list[Path], truncated: bool) -> dict[str, Any]:
    target_path = str(row.get("path") or "")
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


def scan_references(rows: list[dict[str, Any]], files: list[Path], truncated: bool) -> dict[str, dict[str, Any]]:
    exact_hits: dict[str, list[str]] = {str(row.get("path") or ""): [] for row in rows}
    basename_hits: dict[str, list[str]] = {str(row.get("path") or ""): [] for row in rows}
    names = {str(row.get("path") or ""): Path(str(row.get("path") or "")).name for row in rows}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_path = rel(path)
        for target_path, target_name in names.items():
            if target_path and target_path in text:
                exact_hits[target_path].append(rel_path)
            if target_name and target_name in text:
                basename_hits[target_path].append(rel_path)
    results: dict[str, dict[str, Any]] = {}
    for target_path in names:
        exact = exact_hits[target_path]
        basename = basename_hits[target_path]
        results[target_path] = {
            "status": "ok" if not exact and not basename and not truncated else "blocked",
            "exact_reference_count": len(exact),
            "basename_reference_count": len(basename),
            "exact_reference_paths": exact[:20],
            "basename_reference_paths": basename[:20],
            "reference_file_count": len(files),
            "reference_scan_truncated": truncated,
        }
    return results


def microbatch_digest(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "path": row.get("path"),
            "bytes": row.get("bytes"),
            "sha256": row.get("sha256"),
            "last_write_utc": row.get("last_write_utc"),
        }
        for row in rows
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_packet(artifacts: dict[str, dict[str, Any]], *, sample_limit: int = 50) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    references = referenced_tmp_paths(artifacts)
    files = [path for path in TMP.rglob("*") if path.is_file()]
    classified = [classify_path(path, now, references) for path in files]
    family_bytes: dict[str, int] = defaultdict(int)
    family_counts: dict[str, int] = defaultdict(int)
    for row in classified:
        family = str(row["cleanup_family"])
        family_bytes[family] += int(row["bytes"])
        family_counts[family] += 1

    safe_atomic = [
        row
        for row in classified
        if row["cleanup_family"] == "atomic_tmp_ready_family" and int(row["bytes"]) <= 10 * 1024 * 1024
    ]
    safe_atomic.sort(key=lambda row: (-float(row["age_days"]), row["path"]))
    text_review = [row for row in classified if row["cleanup_family"] == "stale_generated_text_review_family"]
    text_review.sort(key=lambda row: (-int(row["bytes"]), -float(row["age_days"]), row["path"]))
    protected = [row for row in classified if row["cleanup_family"] == "protected_or_family_packet_required"]
    total_bytes = sum(int(row["bytes"]) for row in classified)
    reference_corpus, reference_truncated = reference_files()
    text_sample: list[dict[str, Any]] = []
    for row in text_review[:sample_limit]:
        target = ROOT / str(row["path"])
        enriched = {
            **row,
            "sha256": file_sha256(target) if target.exists() and target.is_file() else None,
        }
        text_sample.append(enriched)
    reference_results = scan_references(text_sample, reference_corpus, reference_truncated) if text_sample else {}
    for row in text_sample:
        row["reference_check"] = reference_results.get(str(row.get("path") or ""), {"status": "not_run"})
    owner_ready_text = [
        row
        for row in text_sample
        if row.get("sha256") and as_dict(row.get("reference_check")).get("status") == "ok"
    ]
    owner_ready_text_digest = microbatch_digest(owner_ready_text)

    phase1_apply = artifacts["phase1_apply_report"]
    phase1_summary = as_dict(phase1_apply.get("summary"))
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "full_cleanup_readiness_packet_ready_no_apply",
        "purpose": "Staged readiness map for reducing tmp/ from roughly 3GB without blind or unapproved deletion.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {name: rel(path) for name, path in INPUTS.items()},
        "source_status": [input_record(INPUTS[name], artifacts[name]) for name in INPUTS],
        "summary": {
            "tmp_file_count": len(files),
            "tmp_total_mb": round(total_bytes / (1024 * 1024), 3),
            "referenced_tmp_path_count": len(references),
            "phase1_deleted_count": phase1_summary.get("deleted_count"),
            "phase1_deleted_bytes": phase1_summary.get("deleted_bytes"),
            "safe_atomic_candidate_count": len(safe_atomic),
            "safe_atomic_candidate_bytes": sum(int(row["bytes"]) for row in safe_atomic),
            "stale_generated_text_review_count": len(text_review),
            "stale_generated_text_review_mb": round(sum(int(row["bytes"]) for row in text_review) / (1024 * 1024), 3),
            "next_owner_ready_text_microbatch_count": len(owner_ready_text),
            "next_owner_ready_text_microbatch_mb": round(sum(int(row["bytes"]) for row in owner_ready_text) / (1024 * 1024), 3),
            "next_owner_ready_text_microbatch_digest": owner_ready_text_digest,
            "protected_or_family_packet_required_count": len(protected),
            "protected_or_family_packet_required_mb": round(sum(int(row["bytes"]) for row in protected) / (1024 * 1024), 3),
        },
        "family_rollups": [
            {
                "family": family,
                "file_count": family_counts[family],
                "bytes": family_bytes[family],
                "mb": round(family_bytes[family] / (1024 * 1024), 3),
            }
            for family in sorted(family_counts, key=lambda item: -family_bytes[item])
        ],
        "top_directories_by_size": directory_rollups(files, limit=20),
        "next_owner_ready_atomic_microbatch": safe_atomic[:sample_limit],
        "next_owner_ready_text_microbatch": owner_ready_text,
        "next_review_text_microbatch_sample": text_sample,
        "protected_or_family_packet_required_sample": protected[:sample_limit],
        "approval_surface": {
            "stale_text_microbatch_ready": bool(owner_ready_text),
            "stale_text_apply_wrapper": rel(STALE_TEXT_APPLY_WRAPPER),
            "stale_text_apply_wrapper_exists": STALE_TEXT_APPLY_WRAPPER.exists(),
            "approval_phrase_for_future_stale_text_apply": (
                "Approve Cleanup Autopilot stale generated text microbatch "
                f"{owner_ready_text_digest} exactly as listed in tmp/cleanup-autopilot-full-delete-readiness.json."
            )
            if owner_ready_text
            else None,
            "delete_allowed_now": False,
            "requires_separate_apply_wrapper": not STALE_TEXT_APPLY_WRAPPER.exists(),
        },
        "full_3gb_readiness": {
            "one_shot_delete_ready": False,
            "reason": "The 3GB tmp footprint includes current proof artifacts, referenced cron/control outputs, databases, vendor/cache trees, and stale generated text. These need family-specific packets and approvals.",
            "recommended_sequence": [
                "Apply exact owner-approved atomic tmp crumbs only after packet approval.",
                "Build stale generated text microbatches with reference checks and hashes.",
                "Handle database/WAL/SHM families only through DB lifecycle packets.",
                "Handle vendor/cache directories through directory-family rollback/export packets.",
                "Retain current cron/control/status/finance proof artifacts unless producer contracts are rewired.",
            ],
        },
        "validation": validate_packet_fields(classified),
    }
    return packet


def validate_packet_fields(classified: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    false_flags = [
        "delete_allowed",
        "archive_allowed",
        "move_allowed",
        "broad_tmp_cleanup_allowed",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ]
    for flag in false_flags:
        if AUTHORITY_BOUNDARY.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")
    if not classified:
        errors.append("tmp_inventory_empty")
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": []}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Cleanup Autopilot Full Delete Readiness",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- tmp files: {summary.get('tmp_file_count')}",
        f"- tmp total MB: {summary.get('tmp_total_mb')}",
        f"- Phase 1 deleted bytes: {summary.get('phase1_deleted_bytes')}",
        f"- Safe atomic candidates remaining: {summary.get('safe_atomic_candidate_count')}",
        f"- Stale generated text review MB: {summary.get('stale_generated_text_review_mb')}",
        f"- Next owner-ready text microbatch MB: {summary.get('next_owner_ready_text_microbatch_mb')}",
        f"- Next owner-ready text microbatch digest: {summary.get('next_owner_ready_text_microbatch_digest')}",
        f"- Protected/family-packet-required MB: {summary.get('protected_or_family_packet_required_mb')}",
        "",
        "## Boundary",
        "",
        "- Readiness only.",
        "- No delete, archive, move, cron schedule change, runtime/config mutation, finance mutation, or execution authority.",
        "",
        "## Family Rollups",
        "",
    ]
    for row in as_list(packet.get("family_rollups")):
        if isinstance(row, dict):
            lines.append(f"- {row.get('family')}: {row.get('file_count')} files, {row.get('mb')} MB")
    lines.extend(["", "## Next Step", "", as_dict(packet.get("full_3gb_readiness")).get("reason", "")])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--sample-limit", type=int, default=50)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = {name: load_optional(path) for name, path in INPUTS.items()}
    packet = build_packet(artifacts, sample_limit=args.sample_limit)
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
