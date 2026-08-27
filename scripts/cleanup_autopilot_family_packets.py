#!/usr/bin/env python3
"""Build review-only tmp cleanup family packets for owner-gated deletion.

This script does not delete, move, archive, stop runtimes, mutate databases, or
change producer contracts. It groups the large tmp/ footprint into separate
families so destructive approval can stay exact and staged.
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
OUT_JSON = TMP / "cleanup-autopilot-family-packets.json"
OUT_MD = TMP / "cleanup-autopilot-family-packets.md"
FULL_READINESS = TMP / "cleanup-autopilot-full-delete-readiness.json"
STALE_TEXT_APPLY = ROOT / "scripts" / "cleanup_autopilot_stale_text_apply.py"
FAMILY_APPLY = ROOT / "scripts" / "cleanup_autopilot_family_apply.py"
SCHEMA = "veritas.cleanup_autopilot_family_packets.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "delete_allowed_now": False,
    "archive_allowed_now": False,
    "move_allowed_now": False,
    "runtime_stop_or_mutation_allowed": False,
    "db_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "producer_contract_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
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
REFERENCE_SKIP_REL_PATHS = {
    "scripts/cleanup_autopilot_family_packets.py",
    "scripts/cleanup_autopilot_family_apply.py",
    "scripts/test_cleanup_autopilot_family_packets.py",
    "scripts/test_cleanup_autopilot_family_apply.py",
}
HISTORICAL_REFERENCE_PREFIXES = (
    "08. Audits/",
    "backups/",
    "data/state-history/",
    "memory/",
    "state/long-work-jobs/",
    "state/tmp-lifecycle-rollback/",
)
DB_ENDINGS = (".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite-shm", ".sqlite-wal", ".sqlite3")
PROOF_SUFFIXES = {".csv", ".html", ".json", ".jsonl", ".log", ".md", ".txt"}
AUDIO_SCRATCH_SUFFIXES = {".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".webm"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def age_days(path: Path, now: datetime) -> float:
    return max(0.0, (now.timestamp() - path.stat().st_mtime) / 86400.0)


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path, now: datetime, *, include_sha: bool = False) -> dict[str, Any]:
    record = {
        "path": rel(path),
        "bytes": path.stat().st_size,
        "last_write_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "age_days": round(age_days(path, now), 3),
        "suffix": path.suffix.lower(),
    }
    if include_sha:
        record["sha256"] = file_sha256(path)
    return record


def inventory_digest(records: list[dict[str, Any]]) -> str:
    payload = [
        {
            "path": row.get("path"),
            "bytes": row.get("bytes"),
            "last_write_utc": row.get("last_write_utc"),
            "sha256": row.get("sha256"),
        }
        for row in sorted(records, key=lambda item: str(item.get("path") or ""))
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reference_files(max_files: int = 6000) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for path in ROOT.rglob("*"):
        if len(files) >= max_files:
            truncated = True
            break
        if not path.is_file():
            continue
        try:
            parts = path.relative_to(ROOT).parts
        except ValueError:
            continue
        rel_path = rel(path)
        if rel_path in REFERENCE_SKIP_REL_PATHS:
            continue
        if any(part in REFERENCE_SKIP_PARTS for part in parts):
            continue
        if path.suffix.lower() not in REFERENCE_SUFFIXES:
            continue
        files.append(path)
    return files, truncated


def historical_reference(path_text: str) -> bool:
    return any(path_text.startswith(prefix) for prefix in HISTORICAL_REFERENCE_PREFIXES)


def scan_terms(terms: list[str], files: list[Path], truncated: bool) -> dict[str, Any]:
    normalized = [term for term in dict.fromkeys(terms) if term]
    hits: dict[str, list[str]] = {term: [] for term in normalized}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_path = rel(path)
        for term in normalized:
            if term in text:
                hits[term].append(rel_path)
    hit_terms = {term: paths[:20] for term, paths in hits.items() if paths}
    active_paths: set[str] = set()
    historical_paths: set[str] = set()
    for paths in hits.values():
        for path in paths:
            if historical_reference(path):
                historical_paths.add(path)
            else:
                active_paths.add(path)
    return {
        "status": "ok" if not hit_terms and not truncated else "blocked",
        "term_count": len(normalized),
        "hit_term_count": len(hit_terms),
        "total_hit_count": sum(len(paths) for paths in hits.values()),
        "active_hit_path_count": len(active_paths),
        "historical_hit_path_count": len(historical_paths),
        "active_hit_paths": sorted(active_paths)[:20],
        "historical_hit_paths": sorted(historical_paths)[:20],
        "hit_terms": hit_terms,
        "reference_file_count": len(files),
        "reference_scan_truncated": truncated,
    }


def all_tmp_files() -> list[Path]:
    if not TMP.exists():
        return []
    return [path for path in TMP.rglob("*") if path.is_file()]


def under(path: Path, prefixes: tuple[str, ...]) -> bool:
    path_text = rel(path)
    return any(path_text == prefix or path_text.startswith(f"{prefix}/") for prefix in prefixes)


def build_family(
    *,
    family_id: str,
    title: str,
    description: str,
    files: list[Path],
    now: datetime,
    reference_terms: list[str],
    reference_corpus: list[Path],
    reference_truncated: bool,
    readiness_state: str,
    deletion_boundary: str,
    next_action: str,
    sample_limit: int,
    include_sha_for_records: bool = False,
    approval_ready: bool = False,
    apply_wrapper: str | None = None,
    allow_historical_references: bool = False,
) -> dict[str, Any]:
    records = []
    for path in files:
        try:
            records.append(file_record(path, now, include_sha=include_sha_for_records))
        except (FileNotFoundError, OSError):
            continue
    digest = inventory_digest(records)
    reference_check = scan_terms(reference_terms, reference_corpus, reference_truncated)
    if (
        allow_historical_references
        and reference_check.get("active_hit_path_count") == 0
        and not reference_check.get("reference_scan_truncated")
    ):
        reference_check["status"] = "historical_references_only" if reference_check.get("historical_hit_path_count") else "ok"
    bytes_total = sum(int(row["bytes"]) for row in records)
    effective_approval_ready = (
        approval_ready
        and bool(records)
        and reference_check.get("status") in {"ok", "historical_references_only"}
        and int(reference_check.get("active_hit_path_count") or 0) == 0
        and not reference_check.get("reference_scan_truncated")
    )
    approval_phrase = None
    if effective_approval_ready:
        approval_phrase = (
            f"Approve Cleanup Autopilot {family_id} microbatch {digest} exactly as listed "
            "in tmp/cleanup-autopilot-family-packets.json."
        )
    return {
        "family_id": family_id,
        "title": title,
        "description": description,
        "readiness_state": readiness_state,
        "delete_allowed_now": False,
        "approval_ready_after_owner_phrase": effective_approval_ready,
        "deletion_boundary": deletion_boundary,
        "next_action": next_action,
        "file_count": len(records),
        "bytes": bytes_total,
        "mb": round(bytes_total / (1024 * 1024), 3),
        "inventory_digest": digest,
        "reference_check": reference_check,
        "records": records[:sample_limit],
        "record_manifest": {
            "complete_manifest_in_packet": len(records) <= sample_limit,
            "record_count": len(records),
            "sample_count": min(len(records), sample_limit),
            "content_sha256_included": include_sha_for_records,
        },
        "approval_surface": {
            "approval_phrase": approval_phrase,
            "apply_wrapper": apply_wrapper,
            "apply_wrapper_exists": bool(apply_wrapper and (ROOT / apply_wrapper).exists()),
            "rollback_required_before_delete": True,
            "post_apply_refresh_required": [
                "python scripts\\cleanup_autopilot_full_delete_readiness.py --write --write-md --validate",
                "python scripts\\cleanup_autopilot_family_packets.py --write --write-md --validate",
            ],
        },
    }


def next_text_microbatch(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in as_list(packet.get("next_owner_ready_text_microbatch")) if isinstance(row, dict)]


def build_packet(*, sample_limit: int = 100) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    full = load_optional(FULL_READINESS)
    files = all_tmp_files()
    reference_corpus, reference_truncated = reference_files()

    db_files = [path for path in files if rel(path).lower().endswith(DB_ENDINGS)]
    otel_files = [path for path in files if under(path, ("tmp/otel-collector",))]
    otel_archive_files = [path for path in otel_files if under(path, ("tmp/otel-collector/archive",))]
    otel_empty_pb_files = [
        path for path in otel_files
        if path.suffix.lower() == ".pb" and path.stat().st_size == 0
    ]
    otel_separate_ready = set(otel_archive_files + otel_empty_pb_files)
    otel_active_files = [path for path in otel_files if path not in otel_separate_ready]
    audio_files = [path for path in files if under(path, ("tmp/audio-tools",))]
    audio_scratch_files = [
        path for path in audio_files
        if path.parent == TMP / "audio-tools" and path.suffix.lower() in AUDIO_SCRATCH_SUFFIXES
    ]
    audio_cache_files = [path for path in audio_files if path not in set(audio_scratch_files)]
    go_current_files = [path for path in files if under(path, ("tmp/go-binaries",))]
    go_backup_files = [path for path in files if under(path, ("tmp/go-bin-backup-20260607",))]
    go_profile_files = [path for path in files if under(path, ("tmp/go-profile-binaries",))]
    referenced_proofs = [
        row
        for row in as_list(full.get("protected_or_family_packet_required_sample"))
        if isinstance(row, dict) and "referenced_by_cron_or_control" in as_list(row.get("protected_reasons"))
    ]
    text_ready_rows = next_text_microbatch(full)
    text_ready_bytes = sum(int(row.get("bytes") or 0) for row in text_ready_rows)
    text_ready_digest = as_dict(full.get("summary")).get("next_owner_ready_text_microbatch_digest")

    families = [
        build_family(
            family_id="sqlite_db_lifecycle",
            title="SQLite and DB Runtime/Index Family",
            description="All tmp database, WAL, and SHM files. These require DB lifecycle ownership, producer freshness proof, and rollback/export review before deletion.",
            files=db_files,
            now=now,
            reference_terms=[rel(path) for path in db_files] + [path.name for path in db_files],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="blocked_requires_db_lifecycle_packet",
            deletion_boundary="No DB/WAL/SHM deletion from cleanup autopilot. Use DB lifecycle packet and explicit owner approval.",
            next_action="Run DB lifecycle manifest and split active current DBs from retired DB/cache residues.",
            sample_limit=sample_limit,
        ),
        build_family(
            family_id="otel_collector_runtime_cache",
            title="OTEL Collector Active Runtime Output Family",
            description="Active collector runtime outputs such as metrics, traces, receipts, and live logs. These remain blocked while the collector route uses them.",
            files=otel_active_files,
            now=now,
            reference_terms=["tmp/otel-collector", "otel-collector", "metrics.jsonl", "traces.jsonl", "collector.err", "collector.out"],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="blocked_runtime_adjacent_retention_packet_required",
            deletion_boundary="No active collector output deletion while the collector route and probes reference the files.",
            next_action="Keep active OTEL outputs; only separate archive/empty probe residue can become owner-ready microbatches.",
            sample_limit=sample_limit,
        ),
        build_family(
            family_id="otel_collector_archived_logs",
            title="OTEL Collector Archived Logs",
            description="Archived collector logs that are not active collector outputs. Current metrics, traces, receipts, and live logs are excluded.",
            files=otel_archive_files,
            now=now,
            reference_terms=[term for path in otel_archive_files for term in (rel(path), path.name)],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="owner_ready_archived_log_after_exact_phrase",
            deletion_boundary="Delete only archived collector logs after exact approval; keep active OTEL runtime outputs and collector config.",
            next_action="Owner may approve the exact otel_collector_archived_logs phrase; apply wrapper will copy rollback before unlink.",
            sample_limit=sample_limit,
            include_sha_for_records=True,
            approval_ready=bool(otel_archive_files),
            apply_wrapper=rel(FAMILY_APPLY),
            allow_historical_references=True,
        ),
        build_family(
            family_id="otel_collector_empty_pb_files",
            title="OTEL Collector Empty Probe Files",
            description="Zero-byte OTEL protobuf probe residue. Active JSONL outputs and logs are excluded.",
            files=otel_empty_pb_files,
            now=now,
            reference_terms=[term for path in otel_empty_pb_files for term in (rel(path), path.name)],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="owner_ready_empty_probe_residue_after_exact_phrase",
            deletion_boundary="Delete only zero-byte OTEL probe residue after exact approval; keep active OTEL runtime outputs.",
            next_action="Owner may approve the exact otel_collector_empty_pb_files phrase; apply wrapper will copy rollback before unlink.",
            sample_limit=sample_limit,
            include_sha_for_records=True,
            approval_ready=bool(otel_empty_pb_files),
            apply_wrapper=rel(FAMILY_APPLY),
            allow_historical_references=True,
        ),
        build_family(
            family_id="audio_tools_cache",
            title="Audio Tools Model/Dependency Cache Family",
            description="Local audio tool cache/dependency tree. Deletion may force reinstall or re-download and needs cache-rebuild acceptance.",
            files=audio_cache_files,
            now=now,
            reference_terms=["tmp/audio-tools", "audio-tools", "Xenova", "whisper-base", "whisper-tiny"],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="blocked_cache_rebuild_acceptance_required",
            deletion_boundary="No audio cache deletion without owner acceptance of rebuild/re-download cost and rollback manifest.",
            next_action="Prepare a cache-delete approval packet after confirming local audio transcription can rebuild or is no longer needed.",
            sample_limit=sample_limit,
        ),
        build_family(
            family_id="audio_tools_scratch_voice_files",
            title="Audio Tools Scratch Voice Files",
            description="Temporary voice/audio scratch files directly under tmp/audio-tools. Dependency and model caches are excluded.",
            files=audio_scratch_files,
            now=now,
            reference_terms=[term for path in audio_scratch_files for term in (rel(path), path.name)],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="owner_ready_scratch_voice_after_exact_phrase",
            deletion_boundary="Delete only scratch voice files after exact approval; keep local audio dependency/model cache.",
            next_action="Owner may approve the exact audio_tools_scratch_voice_files phrase; apply wrapper will copy rollback before unlink.",
            sample_limit=sample_limit,
            include_sha_for_records=True,
            approval_ready=bool(audio_scratch_files),
            apply_wrapper=rel(FAMILY_APPLY),
            allow_historical_references=True,
        ),
        build_family(
            family_id="go_binary_current_cache",
            title="Go Current Binary Cache Family",
            description="Current Go validator binaries. These may be live proof dependencies and should remain until freshness/build routing proves otherwise.",
            files=go_current_files,
            now=now,
            reference_terms=["tmp/go-binaries", "go-binaries"],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="blocked_current_validator_dependency",
            deletion_boundary="No current Go binary deletion until validator freshness/build routing proves safe rebuild.",
            next_action="Keep current binaries; use go_binary_backup_cache for backup-only deletion readiness.",
            sample_limit=sample_limit,
        ),
        build_family(
            family_id="go_binary_backup_cache",
            title="Go Binary Backup Cache Family",
            description="Timestamped Go binary backup folder from 2026-06-07. Current binaries are excluded; historical memory/audit mentions are retained context, not runtime references.",
            files=go_backup_files,
            now=now,
            reference_terms=["tmp/go-bin-backup-20260607", "go-bin-backup-20260607"],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="owner_ready_backup_only_after_exact_phrase",
            deletion_boundary="Delete only the timestamped backup folder after exact approval; keep tmp/go-binaries current runtime proof binaries.",
            next_action="Owner may approve the exact go_binary_backup_cache phrase; apply wrapper will copy rollback before unlink.",
            sample_limit=sample_limit,
            include_sha_for_records=True,
            approval_ready=bool(go_backup_files),
            apply_wrapper=rel(FAMILY_APPLY),
            allow_historical_references=True,
        ),
        build_family(
            family_id="go_profile_binary_cache",
            title="Go Profile Binary Cache Family",
            description="Profile-specific Go binaries. Keep blocked until profiling route ownership and rebuild cost are reviewed.",
            files=go_profile_files,
            now=now,
            reference_terms=["tmp/go-profile-binaries", "go-profile-binaries"],
            reference_corpus=reference_corpus,
            reference_truncated=reference_truncated,
            readiness_state="blocked_profile_route_review_required",
            deletion_boundary="No profile binary deletion until profiling route ownership is confirmed.",
            next_action="Review whether profile binaries are still used by timing/profiling proof.",
            sample_limit=sample_limit,
        ),
    ]

    stale_text_phrase = None
    if text_ready_rows and text_ready_digest:
        stale_text_phrase = (
            "Approve Cleanup Autopilot stale generated text microbatch "
            f"{text_ready_digest} exactly as listed in tmp/cleanup-autopilot-full-delete-readiness.json."
        )
    stale_text_family = {
        "family_id": "stale_generated_text_proof_outputs",
        "title": "Stale Generated Text/Proof Outputs",
        "description": "Small next batch of old text-like generated outputs already reference-checked by the full readiness packet.",
        "readiness_state": "owner_ready_microbatch_after_exact_phrase" if text_ready_rows else "no_owner_ready_records",
        "delete_allowed_now": False,
        "approval_ready_after_owner_phrase": bool(text_ready_rows),
        "file_count": len(text_ready_rows),
        "bytes": text_ready_bytes,
        "mb": round(text_ready_bytes / (1024 * 1024), 3),
        "inventory_digest": text_ready_digest,
        "reference_check": {
            "status": "ok" if text_ready_rows else "not_run",
            "source": rel(FULL_READINESS),
            "all_records_reference_checked_ok": all(
                as_dict(row.get("reference_check")).get("status") == "ok" for row in text_ready_rows
            ),
        },
        "records": text_ready_rows,
        "record_manifest": {
            "complete_manifest_in_packet": True,
            "record_count": len(text_ready_rows),
            "sample_count": len(text_ready_rows),
            "content_sha256_included": bool(text_ready_rows),
        },
        "approval_surface": {
            "approval_phrase": stale_text_phrase,
            "apply_wrapper": rel(STALE_TEXT_APPLY),
            "apply_wrapper_exists": STALE_TEXT_APPLY.exists(),
            "rollback_required_before_delete": True,
            "post_apply_refresh_required": [
                "python scripts\\cleanup_autopilot_full_delete_readiness.py --write --write-md --validate",
                "python scripts\\cleanup_autopilot_family_packets.py --write --write-md --validate",
            ],
        },
    }
    families.append(stale_text_family)

    current_proof_family = {
        "family_id": "current_referenced_proof_outputs",
        "title": "Current Referenced Proof Outputs",
        "description": "Cron/control-referenced generated proof outputs. These are not cleanup candidates until producer contracts or retention policy changes.",
        "readiness_state": "blocked_current_or_referenced_proof",
        "delete_allowed_now": False,
        "approval_ready_after_owner_phrase": False,
        "file_count": len(referenced_proofs),
        "bytes": sum(int(row.get("bytes") or 0) for row in referenced_proofs),
        "mb": round(sum(int(row.get("bytes") or 0) for row in referenced_proofs) / (1024 * 1024), 3),
        "inventory_digest": inventory_digest(referenced_proofs),
        "reference_check": {
            "status": "blocked",
            "reason": "referenced_by_cron_or_control",
            "source": rel(FULL_READINESS),
        },
        "records": referenced_proofs[:sample_limit],
        "record_manifest": {
            "complete_manifest_in_packet": len(referenced_proofs) <= sample_limit,
            "record_count": len(referenced_proofs),
            "sample_count": min(len(referenced_proofs), sample_limit),
            "content_sha256_included": False,
        },
        "approval_surface": {
            "approval_phrase": None,
            "apply_wrapper": None,
            "apply_wrapper_exists": False,
            "rollback_required_before_delete": True,
            "post_apply_refresh_required": [],
        },
    }
    families.append(current_proof_family)

    total_family_bytes = sum(int(family.get("bytes") or 0) for family in families)
    owner_ready_families = [family for family in families if family.get("approval_ready_after_owner_phrase")]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "cleanup_family_packets_ready_no_apply",
        "purpose": "Separate large tmp/ cleanup into DB, runtime cache, rebuildable cache, binary-cache, and proof-output families.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "full_delete_readiness": rel(FULL_READINESS),
        },
        "summary": {
            "tmp_total_mb_from_full_readiness": as_dict(full.get("summary")).get("tmp_total_mb"),
            "family_count": len(families),
            "family_file_count": sum(int(family.get("file_count") or 0) for family in families),
            "family_mb": round(total_family_bytes / (1024 * 1024), 3),
            "owner_ready_family_count": len(owner_ready_families),
            "owner_ready_mb": round(sum(int(family.get("bytes") or 0) for family in owner_ready_families) / (1024 * 1024), 3),
            "blocked_or_requires_subpacket_family_count": len(families) - len(owner_ready_families),
            "full_3gb_one_shot_delete_ready": False,
        },
        "families": families,
        "full_deletion_gate": {
            "approval_needed": True,
            "one_shot_full_delete_ready": False,
            "reason": "Full tmp deletion still mixes current proof, active DBs, runtime-adjacent OTEL files, rebuildable caches, and stale proof outputs. Approval must be family-specific.",
            "owner_ready_approval_phrases": [
                as_dict(family.get("approval_surface")).get("approval_phrase")
                for family in owner_ready_families
                if as_dict(family.get("approval_surface")).get("approval_phrase")
            ],
            "next_safe_sequence": [
                "Approve/apply the small stale-generated-text proof batch if desired.",
                "Split Go binary cache into current required binaries versus backup-only delete candidates.",
                "Run DB lifecycle manifest before any SQLite/WAL/SHM action.",
                "Prepare OTEL collector retention packet before deleting collector archives/logs.",
                "Prepare audio-tools cache rebuild acceptance packet before deleting model/dependency cache.",
            ],
        },
        "validation": validate_packet(families),
    }
    return packet


def validate_packet(families: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        if key == "review_only":
            if value is not True:
                errors.append("authority_boundary.review_only_must_be_true")
        elif value is not False:
            errors.append(f"authority_boundary.{key}_must_be_false")
    if not families:
        errors.append("no_family_packets")
    for family in families:
        if family.get("delete_allowed_now") is not False:
            errors.append(f"family_delete_allowed_now_not_false:{family.get('family_id')}")
        if family.get("approval_ready_after_owner_phrase") and not as_dict(family.get("approval_surface")).get("approval_phrase"):
            errors.append(f"approval_ready_missing_phrase:{family.get('family_id')}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Cleanup Autopilot Family Packets",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- tmp total MB from readiness: {summary.get('tmp_total_mb_from_full_readiness')}",
        f"- Family MB represented: {summary.get('family_mb')}",
        f"- Owner-ready family count: {summary.get('owner_ready_family_count')}",
        f"- Owner-ready MB: {summary.get('owner_ready_mb')}",
        f"- Full one-shot delete ready: {summary.get('full_3gb_one_shot_delete_ready')}",
        "",
        "## Families",
        "",
    ]
    for family in as_list(packet.get("families")):
        if not isinstance(family, dict):
            continue
        lines.extend(
            [
                f"### {family.get('title')}",
                "",
                f"- ID: `{family.get('family_id')}`",
                f"- State: `{family.get('readiness_state')}`",
                f"- Files: {family.get('file_count')}",
                f"- MB: {family.get('mb')}",
                f"- Reference status: {as_dict(family.get('reference_check')).get('status')}",
                f"- Next action: {family.get('next_action') or as_dict(packet.get('full_deletion_gate')).get('reason')}",
                "",
            ]
        )
    phrases = as_list(as_dict(packet.get("full_deletion_gate")).get("owner_ready_approval_phrases"))
    if phrases:
        lines.extend(["## Owner-Ready Approval Phrases", ""])
        for phrase in phrases:
            lines.append(f"- `{phrase}`")
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "Review-only. No delete, archive, move, DB mutation, runtime stop, cron schedule change, config/auth/runtime mutation, finance mutation, paper/live action, or owner approval inference.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--sample-limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(sample_limit=args.sample_limit)
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
