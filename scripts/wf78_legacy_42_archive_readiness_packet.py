#!/usr/bin/env python3
"""Build preview-only WF78 legacy-42 archive readiness packet.

This packet scopes the legacy-42 surfaces that might later be archived after
explicit owner approval. It does not move, delete, rewrite, checkpoint, vacuum,
or archive any file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

PLANNER = TMP / "wf78-legacy-42-tier-migration-planner.json"
DB_LIFECYCLE = TMP / "db-lifecycle-manifest.json"
OUT = TMP / "wf78-legacy-42-archive-readiness-packet.json"
SCHEMA = "veritas.wf78_legacy_42_archive_readiness_packet.v1"

ARCHIVE_ROOT = "09. Archive/WF78 Legacy 42 Tier Migration Surfaces/preview"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "preview_only": True,
    "archive_apply_allowed": False,
    "delete_apply_allowed": False,
    "move_allowed": False,
    "file_mutation_allowed": False,
    "database_mutation_allowed": False,
    "sql_canon_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "preview_only"}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}

RETIREMENT_POLICY = {
    "legacy_42_specific": {
        "recommendation": "archive_candidate_after_exact_approval",
        "rationale": "legacy-specific generated proof can be archived after no active consumers require it and rollback/tombstone proof is ready",
    },
    "wf72_42_derived_guard": {
        "recommendation": "retain_as_compatibility_guardrail",
        "rationale": "WF72 252/265 guardrails are still active SQL/cache support proof, not tier authority",
    },
    "shared_sql_cache": {
        "recommendation": "retain_protected",
        "rationale": "shared WF72 SQL/cache surface remains active support infrastructure and is not a legacy-tier-only artifact",
    },
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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_mtime_utc(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lifecycle_by_path(lifecycle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("path") or ""): entry
        for entry in as_list(lifecycle.get("entries"))
        if isinstance(entry, dict) and entry.get("path")
    }


def sidecar_rows(path: Path, destination: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if not sidecar.exists():
            continue
        rows.append(
            {
                "path": rel(sidecar),
                "exists": True,
                "size_bytes": sidecar.stat().st_size,
                "sha256": sha256_file(sidecar),
                "proposed_destination": f"{destination}{suffix}" if destination else None,
            }
        )
    return rows


def build_report() -> dict[str, Any]:
    planner = load_dict(PLANNER)
    db_lifecycle = load_dict(DB_LIFECYCLE)
    planner_summary = as_dict(planner.get("summary"))
    lifecycle_index = lifecycle_by_path(db_lifecycle)

    candidates: list[dict[str, Any]] = []
    for item in as_list(planner.get("legacy_surface_candidates")):
        if not isinstance(item, dict):
            continue
        rel_path = str(item.get("path") or "")
        path = ROOT / rel_path
        retirement_class = str(item.get("retirement_class") or "unknown")
        policy = RETIREMENT_POLICY.get(
            retirement_class,
            {
                "recommendation": "needs_manual_classification",
                "rationale": "unknown retirement class",
            },
        )
        lifecycle_entry = lifecycle_index.get(rel_path, {})
        archive_candidate = policy["recommendation"] == "archive_candidate_after_exact_approval"
        proposed_destination = f"{ARCHIVE_ROOT}/{Path(rel_path).name}" if archive_candidate else None
        blockers: list[str] = []
        if not path.exists():
            blockers.append("source_missing")
        if lifecycle_entry.get("lifecycle") in {"live", "derived"} and not archive_candidate:
            blockers.append("lifecycle_policy_says_keep")
        if archive_candidate and planner_summary.get("active_migration_blocker_count") != 0:
            blockers.append("active_migration_blockers_not_zero")
        if archive_candidate and planner_summary.get("legacy_db_deprecation_ready") is True:
            blockers.append("unexpected_planner_deprecation_ready_without_owner_gate")
        if archive_candidate:
            blockers.append("exact_archive_approval_required_before_move")

        candidates.append(
            {
                "path": rel_path,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "mtime_utc": path_mtime_utc(path),
                "sha256": sha256_file(path),
                "retirement_class": retirement_class,
                "planner_reason": item.get("reason"),
                "lifecycle": lifecycle_entry.get("lifecycle"),
                "lifecycle_owner": lifecycle_entry.get("owner"),
                "lifecycle_status": lifecycle_entry.get("status"),
                "recommendation": policy["recommendation"],
                "rationale": policy["rationale"],
                "archive_candidate_after_approval": archive_candidate,
                "delete_candidate": False,
                "apply_allowed_now": False,
                "proposed_destination": proposed_destination,
                "sidecars": sidecar_rows(path, proposed_destination),
                "rollback": f"Move {proposed_destination} back to {rel_path}" if proposed_destination else None,
                "blockers": blockers,
            }
        )

    archive_candidates = [row for row in candidates if row["archive_candidate_after_approval"]]
    retain_candidates = [row for row in candidates if not row["archive_candidate_after_approval"]]
    validation_errors: list[str] = []
    if as_dict(planner.get("validation")).get("status") != "ok":
        validation_errors.append("planner_validation_not_ok")
    if planner_summary.get("active_migration_blocker_count") != 0:
        validation_errors.append("active_migration_blockers_not_zero")
    if not candidates:
        validation_errors.append("no_legacy_surface_candidates")
    for flag in REQUIRED_TRUE_FLAGS:
        if AUTHORITY_BOUNDARY.get(flag) is not True:
            validation_errors.append(f"authority_{flag}_not_true")
    for flag in REQUIRED_FALSE_FLAGS:
        if AUTHORITY_BOUNDARY.get(flag) is not False:
            validation_errors.append(f"authority_{flag}_not_false")
    for row in candidates:
        if row["apply_allowed_now"] is not False:
            validation_errors.append(f"{row['path']}: apply_allowed_now_not_false")
        if row["delete_candidate"]:
            validation_errors.append(f"{row['path']}: delete_candidate_unexpected_true")
        if row["archive_candidate_after_approval"] and not row["sha256"]:
            validation_errors.append(f"{row['path']}: archive_candidate_missing_sha256")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ready_for_owner_archive_decision" if not validation_errors else "blocked",
        "purpose": "Preview the exact WF78 legacy-42 surfaces that may be archived later; no move/delete/archive is performed.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "planner": rel(PLANNER),
            "db_lifecycle_manifest": rel(DB_LIFECYCLE),
        },
        "summary": {
            "legacy_surface_candidate_count": len(candidates),
            "archive_candidate_after_approval_count": len(archive_candidates),
            "retain_count": len(retain_candidates),
            "delete_candidate_count": 0,
            "apply_allowed_now_count": 0,
            "active_migration_blocker_count": planner_summary.get("active_migration_blocker_count"),
            "legacy_db_deprecation_ready": planner_summary.get("legacy_db_deprecation_ready"),
            "archive_or_delete_allowed_by_planner": planner_summary.get("archive_or_delete_allowed"),
            "next_safe_action": "Ask Randall for exact archive approval only for rows marked archive_candidate_after_approval; retain WF72/shared SQL guardrails.",
        },
        "archive_candidates_after_approval": [row["path"] for row in archive_candidates],
        "retain_candidates": [row["path"] for row in retain_candidates],
        "candidates": candidates,
        "required_approval_text": (
            "Approve archive preview rows only, by exact path; no hard delete; preserve tombstone, hashes, rollback route, and post-archive validators."
        ),
        "post_archive_validation_plan": [
            "python scripts\\wf78_legacy_42_tier_migration_planner.py --write --write-db --validate",
            "python scripts\\wf78_production_tier_adjudication.py --write --write-db --validate",
            "python scripts\\wf78_auto_tier_router.py --write --validate",
            "python scripts\\sql_retail_expansion_phase_gate.py --write --validate",
            "python scripts\\db_lifecycle_manifest.py --write --validate",
            "python scripts\\artifact_index.py rebuild; python scripts\\artifact_index.py validate",
            "python scripts\\control_closeout_bundle.py --validation-budget shared --write --validate",
        ],
        "stop_lines": [
            "No archive/move/delete from this packet.",
            "No hard delete in the next lifecycle step; archive first only if exact approval is given.",
            "Do not archive WF72/shared SQL guardrails from the legacy-42 retirement packet.",
            "No universe/canon/portfolio/cash/risk-rule mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, customer delivery, or owner approval inference.",
        ],
        "validation": {
            "status": "ok" if not validation_errors else "error",
            "errors": validation_errors,
            "warnings": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(args.out, report)
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        print(json.dumps({"status": report.get("status"), "validation": report.get("validation"), "out": rel(args.out)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(args.out),
                "summary": report.get("summary"),
                "validation": report.get("validation"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
