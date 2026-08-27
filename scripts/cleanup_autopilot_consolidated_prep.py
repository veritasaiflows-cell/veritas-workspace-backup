#!/usr/bin/env python3
"""Build one review packet for the next Cleanup Autopilot pass.

This consolidates the repeated review-only producers used before cleanup
approval. It does not delete, archive, move, restart services, mutate cron, or
change runtime/config surfaces.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "cleanup-autopilot-consolidated-prep.json"
OUT_MD = TMP / "cleanup-autopilot-consolidated-prep.md"

FULL_READINESS = TMP / "cleanup-autopilot-full-delete-readiness.json"
FAMILY_PACKETS = TMP / "cleanup-autopilot-family-packets.json"
DB_MANIFEST = TMP / "db-lifecycle-manifest.json"
DB_ARCHIVE_PACKET = TMP / "db-lifecycle-archive-approval-packet.json"
OTEL_RETENTION = TMP / "otel-log-retention.json"
OTEL_OPS = TMP / "otel-ops-control.json"
GO_FRESHNESS = TMP / "go-binary-freshness-guard.json"

AUTHORITY_BOUNDARY = {
    "review_packet_only": True,
    "delete_allowed_now": False,
    "archive_apply_allowed": False,
    "move_apply_allowed": False,
    "runtime_restart_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "external_delivery_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

PRODUCER_COMMANDS = [
    {
        "id": "full_delete_readiness",
        "command": [
            sys.executable,
            "scripts\\cleanup_autopilot_full_delete_readiness.py",
            "--write",
            "--write-md",
            "--validate",
        ],
        "writes": [
            "tmp/cleanup-autopilot-full-delete-readiness.json",
            "tmp/cleanup-autopilot-full-delete-readiness.md",
        ],
        "purpose": "Refresh tmp-wide classification and stale text microbatch readiness.",
    },
    {
        "id": "db_lifecycle_manifest",
        "command": [
            sys.executable,
            "scripts\\db_lifecycle_manifest.py",
            "--write",
            "--write-md",
            "--validate",
        ],
        "writes": [
            "tmp/db-lifecycle-manifest.json",
            "tmp/db-lifecycle-manifest.md",
            "tmp/db-lifecycle-archive-approval-packet.json",
        ],
        "purpose": "Split DB/WAL/SHM surfaces into live, derived, conditional keep, archive, and blocked rows.",
    },
    {
        "id": "otel_log_retention_dry_run",
        "command": [
            sys.executable,
            "scripts\\otel_log_retention.py",
            "--dry-run",
            "--write",
            "--validate",
        ],
        "writes": ["tmp/otel-log-retention.json"],
        "purpose": "Check collector log rotation need without restart, deletion, or archive pruning.",
    },
    {
        "id": "otel_ops_control",
        "default_enabled": False,
        "command": [
            sys.executable,
            "scripts\\otel_ops_control.py",
            "--write",
            "--write-db",
            "--multi-window",
            "--validate",
        ],
        "writes": [
            "tmp/otel-ops-control.json",
            "tmp/otel-ops-window-summary.json",
            "tmp/otel-ops.sqlite",
        ],
        "purpose": "Optionally refresh heavier OTEL operational status before runtime-adjacent cleanup.",
    },
    {
        "id": "go_binary_freshness",
        "command": [
            sys.executable,
            "scripts\\go_binary_freshness_guard.py",
            "--write",
            "--validate",
        ],
        "writes": ["tmp/go-binary-freshness-guard.json"],
        "purpose": "Prove current Go validator binaries are fresh before deciding whether caches are removable.",
    },
    {
        "id": "family_packets",
        "command": [
            sys.executable,
            "scripts\\cleanup_autopilot_family_packets.py",
            "--write",
            "--write-md",
            "--validate",
        ],
        "writes": [
            "tmp/cleanup-autopilot-family-packets.json",
            "tmp/cleanup-autopilot-family-packets.md",
        ],
        "purpose": "Refresh owner-ready and blocked cleanup families after the source producers run.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def run_producers(*, include_otel_ops: bool = False, timeout_seconds: float = 120.0) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for producer in PRODUCER_COMMANDS:
        if producer.get("id") == "otel_ops_control" and not include_otel_ops:
            results.append(
                {
                    "id": producer["id"],
                    "command": " ".join(producer["command"]),
                    "returncode": None,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "status": "skipped_cached_source",
                    "writes": producer["writes"],
                    "purpose": producer["purpose"],
                }
            )
            continue
        try:
            completed = subprocess.run(
                producer["command"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            results.append(
                {
                    "id": producer["id"],
                    "command": " ".join(producer["command"]),
                    "returncode": "timeout",
                    "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
                    "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
                    "status": "timeout",
                    "writes": producer["writes"],
                    "purpose": producer["purpose"],
                    "timeout_seconds": timeout_seconds,
                }
            )
            continue
        results.append(
            {
                "id": producer["id"],
                "command": " ".join(producer["command"]),
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
                "status": "ok" if completed.returncode == 0 else "error",
                "writes": producer["writes"],
                "purpose": producer["purpose"],
            }
        )
    return results


def family_rows(family_packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in as_list(family_packet.get("families")):
        if not isinstance(family, dict):
            continue
        rows.append(
            {
                "family_id": family.get("family_id"),
                "readiness_state": family.get("readiness_state"),
                "file_count": family.get("file_count"),
                "bytes": family.get("bytes"),
                "mb": family.get("mb"),
                "inventory_digest": family.get("inventory_digest"),
                "approval_ready_after_owner_phrase": bool(family.get("approval_ready_after_owner_phrase")),
                "approval_phrase": as_dict(family.get("approval_surface")).get("approval_phrase"),
                "apply_wrapper": as_dict(family.get("approval_surface")).get("apply_wrapper"),
                "next_action": family.get("next_action"),
                "deletion_boundary": family.get("deletion_boundary"),
            }
        )
    return rows


def blocked_families(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked = [
        row
        for row in rows
        if not row.get("approval_ready_after_owner_phrase") and int(row.get("bytes") or 0) > 0
    ]
    return sorted(blocked, key=lambda row: int(row.get("bytes") or 0), reverse=True)


def owner_ready_families(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ready = [
        row
        for row in rows
        if row.get("approval_ready_after_owner_phrase") and row.get("approval_phrase")
    ]
    return sorted(ready, key=lambda row: int(row.get("bytes") or 0), reverse=True)


def source_status(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
        "validation": data.get("validation") or data.get("validation_errors"),
    }


def build_packet(*, producer_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    full = load_json(FULL_READINESS)
    families = load_json(FAMILY_PACKETS)
    db_manifest = load_json(DB_MANIFEST)
    db_archive = load_json(DB_ARCHIVE_PACKET)
    otel_retention = load_json(OTEL_RETENTION)
    otel_ops = load_json(OTEL_OPS)
    go_freshness = load_json(GO_FRESHNESS)

    rows = family_rows(families)
    ready = owner_ready_families(rows)
    blocked = blocked_families(rows)
    full_summary = as_dict(full.get("summary"))
    family_summary = as_dict(families.get("summary"))
    db_summary = as_dict(db_manifest.get("summary"))
    otel_validation = as_dict(otel_retention.get("validation"))
    go_status = go_freshness.get("status")

    approval_phrases = [str(row["approval_phrase"]) for row in ready if row.get("approval_phrase")]
    blocked_mb = round(sum(int(row.get("bytes") or 0) for row in blocked) / (1024 * 1024), 3)
    owner_ready_mb = round(sum(int(row.get("bytes") or 0) for row in ready) / (1024 * 1024), 3)

    return {
        "schema": "veritas.cleanup_autopilot_consolidated_prep.v1",
        "generated_at_utc": utc_now(),
        "status": "review_ready",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_artifacts": {
            "full_delete_readiness": rel(FULL_READINESS),
            "family_packets": rel(FAMILY_PACKETS),
            "db_lifecycle_manifest": rel(DB_MANIFEST),
            "db_archive_approval_packet": rel(DB_ARCHIVE_PACKET),
            "otel_log_retention": rel(OTEL_RETENTION),
            "otel_ops_control": rel(OTEL_OPS),
            "go_binary_freshness": rel(GO_FRESHNESS),
        },
        "source_status": [
            source_status(FULL_READINESS, full),
            source_status(FAMILY_PACKETS, families),
            source_status(DB_MANIFEST, db_manifest),
            source_status(DB_ARCHIVE_PACKET, db_archive),
            source_status(OTEL_RETENTION, otel_retention),
            source_status(OTEL_OPS, otel_ops),
            source_status(GO_FRESHNESS, go_freshness),
        ],
        "producer_results": producer_results or [],
        "summary": {
            "tmp_total_mb": full_summary.get("tmp_total_mb"),
            "family_mb": family_summary.get("family_mb"),
            "blocked_or_requires_subpacket_family_count": len(blocked),
            "blocked_or_requires_subpacket_mb": blocked_mb,
            "owner_ready_delete_microbatch_count": len(ready),
            "owner_ready_delete_mb": owner_ready_mb,
            "approval_phrase_count": len(approval_phrases),
            "full_cleanup_one_shot_ready": False,
            "staged_passes_collapsed_by_this_packet": [
                "DB lifecycle review",
                "OTEL retention dry-run and ops status",
                "audio cache rebuild decision surface",
                "Go/profile dependency review",
                "referenced-proof retirement review",
            ],
        },
        "skip_strategy": {
            "what_can_be_skipped": [
                "Separate manual prep passes for DB lifecycle, OTEL status, audio cache classification, Go freshness, and referenced-proof rollup.",
                "Separate chat turns for each currently owner-ready microbatch when approval phrases exist; the phrases can be pasted together in one owner message.",
            ],
            "what_cannot_be_skipped": [
                "Exact owner approval for destructive delete/apply.",
                "Rollback copy before unlink.",
                "DB lifecycle protection for SQLite/WAL/SHM.",
                "Runtime-sensitive OTEL restart/rotation approval.",
                "Audio cache rebuild/re-download acceptance.",
                "Go binary dependency proof.",
                "Referenced-proof retirement or producer-contract retargeting.",
            ],
            "current_fast_path": (
                "Run `python scripts\\cleanup_autopilot_consolidated_prep.py --write --write-md --validate`; "
                "approve only the owner-ready phrases it emits; apply wrappers remain scoped and rollback-backed. "
                "Add `--refresh-otel-ops` only when the heavier OTEL multi-window packet needs a fresh rebuild."
            ),
        },
        "owner_ready_delete_microbatches": ready,
        "owner_ready_approval_phrases": approval_phrases,
        "blocked_full_cleanup_families": blocked,
        "db_lifecycle_decision": {
            "status": db_manifest.get("status"),
            "database_count": db_summary.get("database_count"),
            "archive_candidate_count": db_summary.get("archive_candidate_count"),
            "archive_ready_count": db_summary.get("archive_ready_count"),
            "delete_ready_count": db_summary.get("delete_ready_count"),
            "archive_approval_packet": rel(DB_ARCHIVE_PACKET),
            "recommended_owner_decision": db_manifest.get("recommended_owner_decision"),
        },
        "otel_retention_decision": {
            "status": otel_retention.get("status"),
            "action": otel_retention.get("action"),
            "needs_rotation": otel_retention.get("needs_rotation"),
            "validation": otel_validation,
            "before": otel_retention.get("before"),
            "after": otel_retention.get("after"),
            "owner_gated_next_action": "Run OTEL log retention with --restart only if Randall approves local collector restart/rotation.",
        },
        "otel_ops_decision": {
            "status": otel_ops.get("status"),
            "summary": otel_ops.get("summary"),
            "authority_boundary": otel_ops.get("authority_boundary"),
        },
        "go_dependency_decision": {
            "status": go_status,
            "binary_count": go_freshness.get("binary_count"),
            "stale_count": go_freshness.get("stale_count"),
            "missing_count": go_freshness.get("missing_count"),
            "operator_action": go_freshness.get("operator_action"),
            "current_binary_cache_posture": "keep unless a future packet proves source-build/rebuild-on-demand can replace tmp/go-binaries.",
            "profile_binary_cache_posture": "blocked until profile route ownership and rebuild cost are reviewed.",
        },
        "referenced_proof_retirement_decision": {
            "status": "blocked_until_producer_contract_retirement",
            "current_referenced_family": next(
                (row for row in blocked if row.get("family_id") == "current_referenced_proof_outputs"),
                None,
            ),
            "next_action": "Retire or retarget producer contracts before deleting referenced proof outputs.",
        },
        "validation": validate_packet(
            full=full,
            families=families,
            db_manifest=db_manifest,
            otel_retention=otel_retention,
            go_freshness=go_freshness,
            producer_results=producer_results or [],
        ),
    }


def validate_packet(
    *,
    full: dict[str, Any],
    families: dict[str, Any],
    db_manifest: dict[str, Any],
    otel_retention: dict[str, Any],
    go_freshness: dict[str, Any],
    producer_results: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if as_dict(full.get("validation")).get("status") != "ok":
        errors.append("full_delete_readiness_not_ok")
    if as_dict(families.get("validation")).get("status") != "ok":
        errors.append("family_packets_not_ok")
    if db_manifest.get("status") == "validation_error":
        errors.append("db_lifecycle_manifest_validation_error")
    if as_dict(otel_retention.get("validation")).get("status") == "blocked":
        errors.append("otel_retention_blocked")
    if go_freshness and go_freshness.get("status") != "ok":
        errors.append("go_binary_freshness_not_ok")
    elif not go_freshness:
        warnings.append("go_binary_freshness_packet_missing")
    failed_producers = [
        row.get("id")
        for row in producer_results
        if row.get("status") != "skipped_cached_source" and row.get("returncode") not in (None, 0)
    ]
    if failed_producers:
        errors.append("producer_failed:" + ",".join(str(item) for item in failed_producers))
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Cleanup Autopilot Consolidated Prep",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- tmp total MB: {summary.get('tmp_total_mb')}",
        f"- Owner-ready delete MB: {summary.get('owner_ready_delete_mb')}",
        f"- Owner-ready microbatches: {summary.get('owner_ready_delete_microbatch_count')}",
        f"- Blocked/requires subpacket MB: {summary.get('blocked_or_requires_subpacket_mb')}",
        f"- Full cleanup one-shot ready: {summary.get('full_cleanup_one_shot_ready')}",
        "",
        "## Boundary",
        "",
        "Review packet only. No delete, archive, move, runtime restart, cron schedule change, config mutation, finance mutation, external delivery, or execution authority.",
        "",
        "## Owner-Ready Approval Phrases",
        "",
    ]
    phrases = as_list(packet.get("owner_ready_approval_phrases"))
    if phrases:
        lines.extend(f"- {phrase}" for phrase in phrases)
    else:
        lines.append("- None")
    lines.extend(["", "## Blocked Families", ""])
    for row in as_list(packet.get("blocked_full_cleanup_families")):
        if isinstance(row, dict):
            lines.append(
                f"- {row.get('family_id')}: {row.get('file_count')} files, "
                f"{row.get('mb')} MB, {row.get('readiness_state')}"
            )
    lines.extend(["", "## Skip Strategy", ""])
    for item in as_list(as_dict(packet.get("skip_strategy")).get("what_can_be_skipped")):
        lines.append(f"- {item}")
    lines.extend(["", "Still cannot skip:", ""])
    for item in as_list(as_dict(packet.get("skip_strategy")).get("what_cannot_be_skipped")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true", help="Read existing producer packets only.")
    parser.add_argument("--refresh-otel-ops", action="store_true", help="Also refresh the heavier OTEL ops multi-window packet.")
    parser.add_argument("--producer-timeout-seconds", type=float, default=120.0)
    args = parser.parse_args()

    producer_results = (
        []
        if args.skip_refresh
        else run_producers(include_otel_ops=args.refresh_otel_ops, timeout_seconds=args.producer_timeout_seconds)
    )
    packet = build_packet(producer_results=producer_results)
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
