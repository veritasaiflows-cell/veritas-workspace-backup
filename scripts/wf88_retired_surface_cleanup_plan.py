#!/usr/bin/env python3
"""Build the WF88 retired-surface cleanup plan.

This is a review-only OS 2.0 cleanup planner. It consumes existing lifecycle,
retirement, DB, workflow, and artifact-index proof and emits owner-gated
microbatches. It never deletes, archives, moves, mutates cron/runtime/config,
or changes finance/canon/portfolio state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

TMP_LIFECYCLE = TMP / "tmp-lifecycle-guard.json"
HUMAN_RETIREMENT = TMP / "human-canon-thinning-retirement-inventory.json"
DB_LIFECYCLE = TMP / "db-lifecycle-manifest.json"
CRON_RETIRED_INVENTORY = TMP / "wf88-cron-retired-job-inventory.json"
WORKFLOW_ROUTING = TMP / "workflow-routing-index.json"
ARTIFACT_INDEX_DB = TMP / "veritas-artifact-index.sqlite"
OUT = TMP / "wf88-retired-surface-cleanup-plan.json"
MD_OUT = TMP / "wf88-retired-surface-cleanup-plan.md"

SCHEMA = "veritas.wf88_retired_surface_cleanup_plan.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proposal_only": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "owner_approval_inferred": False,
}

CURRENT_FRONT_DOORS = {
    "tmp/veritas-status-card.json",
    "tmp/startup-brief-packet.json",
    "tmp/future-session-enhancement-packet.json",
    "tmp/workflow-routing-index.json",
    "tmp/concurrent-lane-register.json",
    "tmp/pm-control-packet.json",
    "tmp/cron-control-packet.json",
    "tmp/cron-freshness-spine.json",
    "tmp/implementation-release-contract.json",
    "tmp/changed-file-validator-router.json",
    "tmp/validator-bundle-router.json",
    "tmp/control-closeout-bundle.json",
    "tmp/wf74-decision-docket.json",
    "tmp/wf85-decision-os-review-packet.json",
    "tmp/wf88-retired-surface-cleanup-plan.json",
}

PROTECTED_PREFIXES = (
    "tmp/ticker-intelligence-cards/",
    "tmp/official-ir-captures/",
    "tmp/portfolio-mutation-proposals/",
    "tmp/alpaca-paper-readiness/",
    "tmp/entry-band-reports/",
)

CURRENT_WORKFLOW_PREFIXES = (
    "tmp/wf78-",
    "tmp/wf84-",
    "tmp/wf85-",
    "tmp/wf86-",
    "tmp/wf87-",
    "tmp/wf88-",
)

REFERENCE_SCAN_DIRS = (
    "scripts",
    "06. Playbooks",
    "08. Audits",
    "memory",
)

REFERENCE_SCAN_FILES = (
    "TOOLS.md",
    "USER.md",
    "AGENTS.md",
)

FRONT_DOOR_REFERENCE_FILES = (
    "tmp/workflow-routing-index.json",
    "tmp/changed-file-validator-router.json",
    "tmp/validator-bundle-router.json",
    "tmp/implementation-release-contract.json",
    "tmp/db-lifecycle-manifest.json",
    "tmp/human-canon-thinning-retirement-inventory.json",
    "tmp/tmp-lifecycle-guard.json",
)

ROUTE_TARGET_HINTS = {
    "workflow_routing_index": ["scripts/workflow_routing_index.py", "scripts/workflow_router.py"],
    "runtime_performance_scorecard.py": ["scripts/runtime_performance_scorecard.py"],
    "validate_canonical_ownership.py": ["scripts/validate_canonical_ownership.py"],
    "today_card_generator.py": ["scripts/today_card_generator.py"],
    "veritas_question_router.py": ["scripts/veritas_question_router.py"],
    "scripts/ticker_answer_packet.py": ["scripts/ticker_answer_packet.py"],
}

REBUILDABLE_SAMPLE_INPUTS = {
    "tmp/research-automation/raw-events.json": {
        "producer": "scripts/research_intake_packet.py",
        "regeneration_command": "python scripts\\research_intake_packet.py --init-sample",
    },
    "tmp/research-automation/raw-freshness-candidates.json": {
        "producer": "scripts/canonical_freshness_patch.py",
        "regeneration_command": "python scripts\\canonical_freshness_patch.py --init-sample",
    },
}

FIRST_PASS_TMP_MICROBATCH_PREFIXES = {
    "tmp/audio-tools/node_modules/": {
        "owner_family": "dependency_cache",
        "microbatch": "tmp_closed_history_and_cache_microbatch",
        "rebuildability": "stale tmp dependency cache; future apply requires rollback manifest and local audio-tool smoke proof",
        "nonblocking_reference_sources": set(),
    },
    "tmp/wf38-fixtures/": {
        "owner_family": "closed_history_wf38_fixtures",
        "microbatch": "tmp_closed_history_and_cache_microbatch",
        "rebuildability": "closed WF38 fixture residue; retained proof history is non-operational",
        "nonblocking_reference_sources": {"scripts/README.md"},
    },
    "tmp/wf59-backups/": {
        "owner_family": "closed_history_wf59_backups",
        "microbatch": "tmp_closed_history_and_cache_microbatch",
        "rebuildability": "closed WF59 rollback backup residue; route-only continuity references are non-operational",
        "nonblocking_reference_sources": {
            "06. Playbooks/Project Continuity/Workflow 59 - Continuity and Compaction Hardening.md",
        },
    },
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


def load_required_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise SystemExit(f"missing or invalid JSON input: {rel(path)}")
    return data


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def path_exists(path: str) -> bool:
    return (ROOT / path.replace("/", "\\")).exists()


def family_for_path(path: str) -> str:
    norm = path.replace("\\", "/")
    parts = norm.split("/")
    if len(parts) > 2 and parts[0] == "tmp":
        return parts[1]
    if parts and parts[0] == "tmp":
        name = Path(norm).name
        return name.split("-", 1)[0] if "-" in name else "tmp-root"
    if parts and parts[0] == "scripts":
        return "scripts"
    return parts[0] if parts else "unknown"


def startswith_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def read_reference_corpus() -> list[tuple[str, str]]:
    corpus: list[tuple[str, str]] = []
    exts = {".py", ".md", ".json", ".yaml", ".yml", ".ps1", ".cmd", ".ts", ".js"}
    for root_name in REFERENCE_SCAN_DIRS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
            if any(part in {".git", "__pycache__", ".obsidian"} for part in path.relative_to(ROOT).parts):
                continue
            try:
                corpus.append((rel(path), path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    for file_name in REFERENCE_SCAN_FILES:
        path = ROOT / file_name
        if path.exists() and path.is_file():
            corpus.append((rel(path), path.read_text(encoding="utf-8", errors="ignore")))
    for file_name in FRONT_DOOR_REFERENCE_FILES:
        path = ROOT / file_name
        if path.exists() and path.is_file():
            corpus.append((rel(path), path.read_text(encoding="utf-8", errors="ignore")))
    return corpus


def ignored_reference_sources() -> set[str]:
    return {
        rel(TMP_LIFECYCLE),
        rel(HUMAN_RETIREMENT),
        rel(DB_LIFECYCLE),
        rel(OUT),
        rel(MD_OUT),
    }


def active_workflow_sources(workflow_payload: dict[str, Any]) -> set[str]:
    sources: set[str] = set()
    for route in as_list(workflow_payload.get("routes")):
        route_dict = as_dict(route)
        for key in ("continuity_note", "primary_route_artifact"):
            value = route_dict.get(key)
            if isinstance(value, str) and value:
                sources.add(value.replace("\\", "/"))
        for value in as_list(route_dict.get("secondary_artifacts")):
            if isinstance(value, str) and value:
                sources.add(value.replace("\\", "/"))
        for command in as_list(route_dict.get("validator_commands")):
            if not isinstance(command, str):
                continue
            for token in command.replace("\\", "/").split():
                if token.startswith("scripts/") or token.startswith("tmp/"):
                    sources.add(token)
    return sources


def reference_class(source_path: str, active_sources: set[str]) -> str:
    norm = source_path.replace("\\", "/")
    if norm in active_sources:
        return "active"
    if norm.startswith("scripts/"):
        return "active"
    if norm in REFERENCE_SCAN_FILES:
        return "active"
    if norm in FRONT_DOOR_REFERENCE_FILES:
        return "active"
    if norm.startswith("memory/") or norm.startswith("08. Audits/"):
        return "proof_history"
    if norm.startswith("06. Playbooks/"):
        return "proof_history"
    return "proof_history"


def classified_reference_hits(
    path: str,
    corpus: list[tuple[str, str]],
    active_sources: set[str],
    *,
    limit: int = 10,
) -> dict[str, list[str]]:
    needles = {path.replace("\\", "/"), path.replace("/", "\\")}
    ignored_sources = ignored_reference_sources()
    active_hits: list[str] = []
    proof_history_hits: list[str] = []
    for source_path, text in corpus:
        if source_path == path or source_path in ignored_sources:
            continue
        if any(needle and needle in text for needle in needles):
            if reference_class(source_path, active_sources) == "active":
                active_hits.append(source_path)
            else:
                proof_history_hits.append(source_path)
            if len(active_hits) >= limit and len(proof_history_hits) >= limit:
                break
    return {
        "active": active_hits[:limit],
        "proof_history": proof_history_hits[:limit],
    }


def artifact_index_counts(path: str, db_path: Path = ARTIFACT_INDEX_DB) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "available": False,
            "database": rel(db_path),
            "artifact_file_state_count": 0,
            "artifact_run_count": 0,
            "source_artifact_count": 0,
            "source_artifact_status_counts": {},
        }
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        normalized = path.replace("\\", "/")
        file_state_count = con.execute(
            "select count(*) from artifact_file_state where replace(source_file, '\\\\', '/') = ?",
            (normalized,),
        ).fetchone()[0]
        run_count = con.execute(
            "select count(*) from artifact_runs where replace(source_file, '\\\\', '/') = ?",
            (normalized,),
        ).fetchone()[0]
        status_rows = con.execute(
            "select status, count(*) as count from source_artifacts "
            "where replace(path, '\\\\', '/') = ? group by status",
            (normalized,),
        ).fetchall()
        con.close()
        statuses = {str(row["status"]): int(row["count"]) for row in status_rows}
        return {
            "available": True,
            "database": rel(db_path),
            "artifact_file_state_count": int(file_state_count),
            "artifact_run_count": int(run_count),
            "source_artifact_count": sum(statuses.values()),
            "source_artifact_status_counts": statuses,
        }
    except sqlite3.Error as exc:
        return {
            "available": False,
            "database": rel(db_path),
            "error": str(exc),
            "artifact_file_state_count": 0,
            "artifact_run_count": 0,
            "source_artifact_count": 0,
            "source_artifact_status_counts": {},
        }


def sample_input_regeneration_proof(path: str, active_references: list[str]) -> dict[str, Any]:
    norm = path.replace("\\", "/")
    spec = REBUILDABLE_SAMPLE_INPUTS.get(norm)
    if not spec:
        return {
            "is_rebuildable_sample_input": False,
            "producer": None,
            "regeneration_command": None,
            "reference_role": "ordinary_active_reference",
            "non_rebuildable_active_references": active_references,
        }
    producer = str(spec["producer"])
    producer_path = ROOT / producer
    try:
        producer_text = producer_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        producer_text = ""
    producer_has_init_sample = "--init-sample" in producer_text and norm in producer_text.replace("\\", "/")
    allowed_refs = {
        producer,
        "scripts/README.md",
        "scripts/wf88_retired_surface_cleanup_plan.py",
        "scripts/test_wf88_retired_surface_cleanup_plan.py",
    }
    non_rebuildable = [ref for ref in active_references if ref.replace("\\", "/") not in allowed_refs]
    ready = bool(producer_has_init_sample) and not non_rebuildable
    return {
        "is_rebuildable_sample_input": ready,
        "producer": producer,
        "producer_has_init_sample": producer_has_init_sample,
        "regeneration_command": spec["regeneration_command"],
        "reference_role": "rebuildable_sample_input_reference" if ready else "ordinary_active_reference",
        "non_rebuildable_active_references": non_rebuildable,
        "allowed_active_references": sorted(ref for ref in active_references if ref.replace("\\", "/") in allowed_refs),
    }


def first_pass_tmp_microbatch_spec(path: str) -> dict[str, Any] | None:
    norm = path.replace("\\", "/")
    for prefix, spec in FIRST_PASS_TMP_MICROBATCH_PREFIXES.items():
        if norm.startswith(prefix):
            return spec
    return None


def blocking_references_for_tmp_candidate(path: str, active_references: list[str]) -> list[str]:
    spec = first_pass_tmp_microbatch_spec(path)
    if not spec:
        return active_references
    nonblocking = {str(item).replace("\\", "/") for item in spec.get("nonblocking_reference_sources") or set()}
    return [ref for ref in active_references if ref.replace("\\", "/") not in nonblocking]


def classify_tmp_candidate(
    row: dict[str, Any],
    reference_proof: dict[str, list[str]],
    artifact_counts: dict[str, Any],
) -> dict[str, Any]:
    path = str(row.get("path") or "")
    protected_reasons = list(as_list(row.get("protected_reasons")))
    active_references = reference_proof.get("active", [])
    sample_proof = sample_input_regeneration_proof(path, active_references)
    blocking_active_references = blocking_references_for_tmp_candidate(
        path,
        as_list(sample_proof.get("non_rebuildable_active_references")),
    )
    proof_history_references = reference_proof.get("proof_history", [])
    if path in CURRENT_FRONT_DOORS:
        protected_reasons.append("current_front_door")
    if startswith_any(path, PROTECTED_PREFIXES):
        protected_reasons.append("protected_finance_or_paper_surface")
    if startswith_any(path, CURRENT_WORKFLOW_PREFIXES):
        protected_reasons.append("current_wf78_wf88_proof_family")
    if blocking_active_references:
        protected_reasons.append("active_text_reference_found")
    if artifact_counts.get("source_artifact_count"):
        protected_reasons.append("artifact_index_source_artifact_reference")

    family = family_for_path(path)
    first_pass_spec = first_pass_tmp_microbatch_spec(path)
    if first_pass_spec:
        owner_family = str(first_pass_spec["owner_family"])
        rebuildability = str(first_pass_spec["rebuildability"])
        proposed_microbatch = str(first_pass_spec["microbatch"])
    elif "node_modules" in path:
        owner_family = "dependency_cache"
        rebuildability = "requires local tool rebuild proof before owner approval"
        proposed_microbatch = "tmp_dependency_cache_rebuild_proof_needed"
    elif path.startswith("tmp/research-automation/"):
        owner_family = "closed_history_research_automation"
        rebuildability = "generated sample/proof packet; rebuild owner must be confirmed by reference packet"
        proposed_microbatch = "tmp_stale_research_automation_samples"
    elif row.get("suffix") in {".json", ".md", ".txt", ".html"}:
        owner_family = f"tmp_{family}"
        rebuildability = "generated tmp artifact; rebuildability must be confirmed by owner family"
        proposed_microbatch = "tmp_stale_generated_artifact_family_review"
    else:
        owner_family = f"tmp_{family}"
        rebuildability = "not classified as first-pass generated residue"
        proposed_microbatch = "tmp_retain_or_adjudicate"

    first_pass_ready = (
        proposed_microbatch in {"tmp_stale_research_automation_samples", "tmp_closed_history_and_cache_microbatch"}
        and not protected_reasons
        and int(row.get("size_bytes") or row.get("size") or 0) <= 256 * 1024
    )
    return {
        "path": path,
        "family": family,
        "owner_family": owner_family,
        "size_bytes": int(row.get("size_bytes") or row.get("size") or 0),
        "sha256": file_sha256(ROOT / path.replace("/", "\\")),
        "last_write_utc": row.get("last_write_utc"),
        "age_days": row.get("age_days"),
        "source_cleanup_preview_eligible": bool(row.get("cleanup_preview_eligible")),
        "active_reference_count": len(blocking_active_references),
        "active_reference_sample": active_references,
        "blocking_active_reference_sample": blocking_active_references,
        "nonblocking_reference_sample": sorted(
            set(active_references).difference(blocking_active_references)
        ),
        "rebuildable_sample_input_proof": sample_proof,
        "proof_history_reference_count": len(proof_history_references),
        "proof_history_reference_sample": proof_history_references,
        "artifact_index_reference_count": int(artifact_counts.get("source_artifact_count") or 0),
        "artifact_index_proof": artifact_counts,
        "protected_reasons": sorted(set(str(item) for item in protected_reasons)),
        "proposed_microbatch": proposed_microbatch,
        "first_pass_owner_approval_candidate": first_pass_ready,
        "rebuildability": rebuildability,
        "tombstone_path": f"state/archive-deletion-tombstone.json#{path}",
        "rollback_route": "No deletion in this plan. Future apply must preserve manifest hash, source hash, and restore path before mutation.",
        "post_cleanup_validators": [
            "python scripts\\tmp_lifecycle_guard.py --write --validate",
            "python scripts\\wf88_retired_surface_cleanup_plan.py --write --write-md --validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
            "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
        ],
        "delete_allowed_now": False,
        "archive_allowed_now": False,
    }


def build_tmp_lane(
    tmp_payload: dict[str, Any],
    corpus: list[tuple[str, str]],
    active_sources: set[str],
) -> dict[str, Any]:
    samples = [row for row in as_list(tmp_payload.get("cleanup_preview_samples")) if isinstance(row, dict)]
    rows = []
    for row in samples:
        path = str(row.get("path") or "")
        refs = classified_reference_hits(path, corpus, active_sources)
        art_counts = artifact_index_counts(path)
        rows.append(classify_tmp_candidate(row, refs, art_counts))

    first_batch = [
        row for row in rows
        if row["first_pass_owner_approval_candidate"]
    ][:25]
    first_batch_names = sorted({str(row.get("proposed_microbatch")) for row in first_batch})
    first_batch_name = first_batch_names[0] if len(first_batch_names) == 1 else "tmp_mixed_owner_review_microbatch"
    microbatch_counts = Counter(row["proposed_microbatch"] for row in rows)
    return {
        "lane_id": "WF88::TMP-DELETE-PROPOSAL",
        "mode": "review_only_owner_gated_microbatch",
        "status": "proposal_packet_ready_no_delete_authority" if rows else "no_candidates_from_source_packet",
        "delete_allowed_now": False,
        "archive_allowed_now": False,
        "source_summary": as_dict(tmp_payload.get("summary")),
        "microbatch_counts": dict(sorted(microbatch_counts.items())),
        "first_small_safe_proposal_batch": {
            "name": first_batch_name,
            "candidate_count": len(first_batch),
            "bytes": sum(int(row["size_bytes"]) for row in first_batch),
            "delete_allowed_now": False,
            "owner_approval_required_before_delete": True,
            "rows": first_batch,
        },
        "rows_reviewed_from_preview_sample": rows,
        "next_action": "Review first_small_safe_proposal_batch; build exact owner approval packet before any delete/archive.",
        "stop_line": "No delete/move/archive is authorized by this lane.",
    }


def route_files_for_item(path: str) -> list[str]:
    for marker, files in ROUTE_TARGET_HINTS.items():
        if marker in path:
            return [file for file in files if path_exists(file)]
    if path.startswith("scripts/"):
        script_path = path.split(":", 1)[0]
        return [script_path] if path_exists(script_path) else []
    return []


def build_script_lane(
    human_payload: dict[str, Any],
    corpus: list[tuple[str, str]],
    active_sources: set[str],
) -> dict[str, Any]:
    categories = as_dict(human_payload.get("categories"))
    rows: list[dict[str, Any]] = []
    for category in ("narrow_on_demand", "retire_candidate"):
        for item in as_list(categories.get(category)):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            target_files = route_files_for_item(path)
            target_refs = {}
            for file in target_files:
                reference_hits = classified_reference_hits(file, corpus, active_sources)
                target_refs[file] = {
                    "exists": path_exists(file),
                    "active_reference_count": len(reference_hits["active"]),
                    "active_reference_sample": reference_hits["active"],
                    "proof_history_reference_sample": reference_hits["proof_history"],
                    "artifact_index_proof": artifact_index_counts(file),
                }
            rows.append({
                "item": path,
                "category": category,
                "classification": item.get("classification"),
                "reason": item.get("reason"),
                "route_or_script_files": target_files,
                "target_reference_proof": target_refs,
                "recommended_contraction": recommended_route_contraction(path, category),
                "delete_allowed_now": False,
                "archive_allowed_now": False,
                "post_contraction_validators": [
                    "python -m py_compile <touched script files>",
                    "python scripts\\workflow_router.py WF88 --answer all --validate",
                    "python scripts\\changed_file_validator_router.py --write --validate",
                    "python scripts\\validator_bundle_router.py --write --validate",
                    "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
                ],
            })
    return {
        "lane_id": "WF88::SCRIPT-ROUTE-CONTRACTION",
        "mode": "implementation_preflight_no_script_deletion",
        "status": "route_contraction_preflight_ready" if rows else "no_route_contraction_candidates",
        "delete_allowed_now": False,
        "archive_allowed_now": False,
        "source_summary": as_dict(human_payload.get("summary")),
        "candidate_count": len(rows),
        "exact_files_for_next_route_contraction": sorted({file for row in rows for file in row["route_or_script_files"]}),
        "rows": rows,
        "next_action": "Patch default routes/checks only after exact files are leased; retain compatibility scripts until active_reference_count is zero and rollback proof exists.",
    }


def recommended_route_contraction(path: str, category: str) -> str:
    if "ticker_answer_packet" in path:
        return "Keep ticker_answer_packet.py compatibility-only; remove it from routine WF85 validation paths."
    if "runtime_performance_scorecard" in path:
        return "Move human-note SQL/Go parity probes behind explicit migration mode, outside default runtime scoring."
    if "validate_canonical_ownership" in path:
        return "Mode-gate legacy table/header completeness checks behind legacy/thinning validation mode."
    if "today_card_generator" in path:
        return "Relabel human-note links as context/policy/narrative, not structured data owners."
    if "veritas_question_router" in path:
        return "Keep SQL-first routing and label Markdown as human context/source-open fallback."
    if path.startswith("workflow_routing_index"):
        return "Remove legacy ticker answer packet from default WF85 route validation; retain retirement-plan validation."
    if category == "narrow_on_demand":
        return "Keep as targeted migration or compatibility probe, not default closeout cost."
    return "Retire from routine route only; do not delete source until reference and rollback proof are clean."


def build_db_lane(db_payload: dict[str, Any]) -> dict[str, Any]:
    recommended = as_dict(db_payload.get("recommended_owner_decision"))
    archive_paths = as_list(recommended.get("archive_now_after_approval"))
    entries = {
        str(row.get("path")): row
        for row in as_list(db_payload.get("entries"))
        if isinstance(row, dict)
    }
    rows = []
    for path in archive_paths:
        entry = as_dict(entries.get(str(path)))
        rows.append({
            "path": path,
            "size_bytes": entry.get("size_bytes"),
            "sha256": entry.get("sha256"),
            "owner": entry.get("owner"),
            "status": entry.get("status"),
            "recommendation": entry.get("recommendation"),
            "archive_ready_after_owner_approval": bool(entry.get("archive_ready")),
            "delete_ready": bool(entry.get("delete_ready")),
            "owner_approval_required": True,
            "proposed_destination": entry.get("proposed_destination"),
            "sidecars": as_list(entry.get("sidecars")),
            "active_reference_count": entry.get("active_reference_count"),
            "operational_reference_count": entry.get("operational_reference_count"),
            "reference_classification": entry.get("reference_classification"),
            "archive_allowed_now": False,
            "delete_allowed_now": False,
        })
    return {
        "lane_id": "WF88::DB-LIFECYCLE-MICROBATCH",
        "mode": "owner_decision_packet_no_archive_apply",
        "status": "owner_approval_packet_needed" if rows else "no_archive_candidate",
        "delete_allowed_now": False,
        "archive_allowed_now": False,
        "source_summary": as_dict(db_payload.get("summary")),
        "approval_packet": as_dict(db_payload.get("summary")).get("archive_approval_packet"),
        "candidate_count": len(rows),
        "rows": rows,
        "post_archive_validators": [
            "python scripts\\db_lifecycle_manifest.py --write --validate",
            "python scripts\\wf88_retired_surface_cleanup_plan.py --write --write-md --validate",
            "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
        ],
        "next_action": "Prepare owner approval microbatch; do not archive/delete from WF88 planner.",
    }


def build_cron_lane() -> dict[str, Any]:
    cron_control = TMP / "cron-control-packet.json"
    cron_payload = load_json_artifact(cron_control)
    payload = cron_payload if isinstance(cron_payload, dict) else {}
    inventory_payload = load_json_artifact(CRON_RETIRED_INVENTORY) if CRON_RETIRED_INVENTORY.exists() else {}
    inventory = inventory_payload if isinstance(inventory_payload, dict) else {}
    inventory_summary = as_dict(inventory.get("summary"))
    inventory_rows = [
        {
            "disabled_or_retired_job_id": as_dict(row).get("job_id"),
            "name": as_dict(row).get("name"),
            "current_status": as_dict(row).get("status"),
            "retirement_reason": as_dict(row).get("retirement_reason"),
            "enabled_contract_dependency_count": as_dict(row).get("expected_artifact_count"),
            "rollback_export_path": as_dict(row).get("rollback_export_path"),
            "approval_required_before_delete": as_dict(row).get("approval_required_before_delete"),
            "delete_ready_now": as_dict(row).get("delete_ready_now"),
        }
        for row in as_list(inventory.get("disabled_or_retired_jobs"))
    ]
    summary = as_dict(payload.get("summary")) or {
        key: payload.get(key)
        for key in ("status", "blocked_count", "requires_attention_count", "stale_count")
        if key in payload
    }
    return {
        "lane_id": "WF88::CRON-RETIRED-JOB-PACKET",
        "mode": "review_only_inventory_packet_ready" if inventory else "review_only_inventory_packet_needed",
        "status": "inventory_packet_ready_no_cron_mutation" if inventory else "packet_needed_no_cron_mutation",
        "cron_schedule_mutation_allowed": False,
        "delete_allowed_now": False,
        "archive_allowed_now": False,
        "source_packet": rel(cron_control) if cron_control.exists() else None,
        "source_inventory": rel(CRON_RETIRED_INVENTORY) if inventory else None,
        "source_summary": summary,
        "inventory_summary": inventory_summary,
        "rows": inventory_rows,
        "required_packet_fields": [
            "disabled_or_retired_job_id",
            "current_status",
            "retirement_reason",
            "enabled_contract_dependency_count",
            "rollback_export_path",
            "approval_required_before_delete",
        ],
        "post_packet_validators": [
            "python scripts\\cron_contract_validator.py --require-contracts --fail-on-drift --fail-on-prompt-bloat --write --validate",
            "python scripts\\cron_control_packet.py --write --validate",
        ],
        "next_action": (
            "Review disabled/retired cron inventory rows, export live scheduler state, and prove rollback before any owner approval request."
            if inventory
            else "Build a separate disabled/retired cron inventory packet with export/rollback proof; do not mutate schedules."
        ),
    }


def input_record(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "sha256": file_sha256(path),
    }


def build_plan() -> dict[str, Any]:
    tmp_payload = load_required_json(TMP_LIFECYCLE)
    human_payload = load_required_json(HUMAN_RETIREMENT)
    db_payload = load_required_json(DB_LIFECYCLE)
    workflow_payload = load_required_json(WORKFLOW_ROUTING)
    corpus = read_reference_corpus()
    active_sources = active_workflow_sources(workflow_payload)

    tmp_lane = build_tmp_lane(tmp_payload, corpus, active_sources)
    script_lane = build_script_lane(human_payload, corpus, active_sources)
    db_lane = build_db_lane(db_payload)
    cron_lane = build_cron_lane()
    workflow_routes = as_list(workflow_payload.get("routes"))
    wf88_routes = [row for row in workflow_routes if as_dict(row).get("workflow_id") == "WF88"]

    plan = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "proposal_ready_no_apply_authority",
        "purpose": "WF88 first-slice cleanup plan over existing proof packets; no cleanup is applied.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "tmp_lifecycle": input_record(TMP_LIFECYCLE, tmp_payload),
            "human_canon_retirement": input_record(HUMAN_RETIREMENT, human_payload),
            "db_lifecycle": input_record(DB_LIFECYCLE, db_payload),
            "workflow_routing_index": input_record(WORKFLOW_ROUTING, workflow_payload),
            "artifact_index": {
                "path": rel(ARTIFACT_INDEX_DB),
                "exists": ARTIFACT_INDEX_DB.exists(),
                "sha256": file_sha256(ARTIFACT_INDEX_DB),
            },
        },
        "workflow_route_context": {
            "workflow_id": "WF88",
            "route_count": len(wf88_routes),
            "routes": wf88_routes,
        },
        "parallel_plan": [
            {
                "lane_id": "WF88::TMP-DELETE-PROPOSAL",
                "can_run_in_parallel": True,
                "deliverable": "owner-gated tmp deletion proposal microbatch",
                "stop_line": "No delete/move/archive until exact approval.",
            },
            {
                "lane_id": "WF88::SCRIPT-ROUTE-CONTRACTION",
                "can_run_in_parallel": True,
                "deliverable": "default-route reductions without script deletion",
                "stop_line": "No script deletion or source feeder retirement.",
            },
            {
                "lane_id": "WF88::DB-LIFECYCLE-MICROBATCH",
                "can_run_in_parallel": True,
                "deliverable": "single DB archive approval packet",
                "stop_line": "No archive/delete before owner approval.",
            },
            {
                "lane_id": "WF88::CRON-RETIRED-JOB-PACKET",
                "can_run_in_parallel": True,
                "deliverable": "disabled/retired cron inventory plus rollback/export proof",
                "stop_line": "No cron mutation before owner approval.",
            },
            {
                "lane_id": "WF88::POST-CLEANUP-VALIDATION",
                "can_run_in_parallel": False,
                "deliverable": "post-state-change validation bundle",
                "stop_line": "No success claim while gates are stale.",
            },
        ],
        "lanes": {
            "tmp_delete_proposal": tmp_lane,
            "script_route_contraction": script_lane,
            "db_lifecycle_microbatch": db_lane,
            "cron_retired_job_packet": cron_lane,
        },
        "summary": {},
        "validation": {},
        "stop_lines": [
            "No delete, move, archive, cron mutation, config/runtime/auth mutation, or source feeder retirement.",
            "No portfolio/canon/cash/sizing/risk mutation and no paper/live/brokerage/account action.",
            "Generated cleanup packets are route proof only and do not outrank canonical owner notes or approval gates.",
        ],
    }
    plan["summary"] = summarize_plan(plan)
    plan["validation"] = validate_plan(plan)
    return plan


def summarize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    lanes = as_dict(plan.get("lanes"))
    tmp_lane = as_dict(lanes.get("tmp_delete_proposal"))
    script_lane = as_dict(lanes.get("script_route_contraction"))
    db_lane = as_dict(lanes.get("db_lifecycle_microbatch"))
    first_batch = as_dict(tmp_lane.get("first_small_safe_proposal_batch"))
    return {
        "status": plan.get("status"),
        "delete_allowed_now_count": 0,
        "archive_allowed_now_count": 0,
        "tmp_cleanup_preview_eligible_count": as_dict(tmp_lane.get("source_summary")).get("cleanup_preview_eligible_count"),
        "tmp_rows_reviewed_from_preview_sample": len(as_list(tmp_lane.get("rows_reviewed_from_preview_sample"))),
        "first_tmp_microbatch_candidate_count": first_batch.get("candidate_count", 0),
        "first_tmp_microbatch_bytes": first_batch.get("bytes", 0),
        "script_route_contraction_candidate_count": script_lane.get("candidate_count", 0),
        "script_route_contraction_exact_file_count": len(as_list(script_lane.get("exact_files_for_next_route_contraction"))),
        "db_archive_candidate_count": db_lane.get("candidate_count", 0),
        "cron_packet_status": as_dict(lanes.get("cron_retired_job_packet")).get("status"),
        "next_safe_action": "Run the planner review, then lease route-contraction files or build owner approval packets. Do not delete/archive/apply yet.",
    }


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(plan.get("authority_boundary"))
    for key in (
        "delete_allowed",
        "archive_allowed",
        "move_allowed",
        "apply_allowed",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "sql_mutation_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")
    lanes = as_dict(plan.get("lanes"))
    required = {"tmp_delete_proposal", "script_route_contraction", "db_lifecycle_microbatch", "cron_retired_job_packet"}
    missing = required - set(lanes)
    if missing:
        errors.append(f"missing_lanes:{','.join(sorted(missing))}")
    for lane_name, lane in lanes.items():
        lane_dict = as_dict(lane)
        if lane_dict.get("delete_allowed_now") is not False and lane_name != "cron_retired_job_packet":
            errors.append(f"{lane_name}_delete_allowed_now_not_false")
        if lane_dict.get("archive_allowed_now") is not False and lane_name != "cron_retired_job_packet":
            errors.append(f"{lane_name}_archive_allowed_now_not_false")
    if as_dict(plan.get("summary")).get("tmp_cleanup_preview_eligible_count", 0) == 0:
        warnings.append("tmp_lifecycle_packet_has_no_cleanup_preview_candidates")
    if as_dict(plan.get("summary")).get("script_route_contraction_candidate_count", 0) == 0:
        warnings.append("script_route_contraction_has_no_candidates")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    summary = as_dict(plan.get("summary"))
    lanes = as_dict(plan.get("lanes"))
    script_lane = as_dict(lanes.get("script_route_contraction"))
    db_lane = as_dict(lanes.get("db_lifecycle_microbatch"))
    tmp_batch = as_dict(as_dict(lanes.get("tmp_delete_proposal")).get("first_small_safe_proposal_batch"))
    lines = [
        "# WF88 Retired Surface Cleanup Plan",
        "",
        "## Verdict",
        "",
        "WF88 can start with route contraction and deletion proposals. No delete, archive, move, cron mutation, config/runtime mutation, or finance authority mutation is allowed by this packet.",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- tmp preview eligible count: `{summary.get('tmp_cleanup_preview_eligible_count')}`",
        f"- first tmp microbatch candidates: `{summary.get('first_tmp_microbatch_candidate_count')}`",
        f"- script route contraction candidates: `{summary.get('script_route_contraction_candidate_count')}`",
        f"- exact script/route files for next contraction: `{summary.get('script_route_contraction_exact_file_count')}`",
        f"- DB archive candidates: `{summary.get('db_archive_candidate_count')}`",
        f"- cron packet status: `{summary.get('cron_packet_status')}`",
        "",
        "## First Tmp Microbatch",
        "",
        f"- Name: `{tmp_batch.get('name')}`",
        f"- Candidate count: `{tmp_batch.get('candidate_count')}`",
        f"- Bytes: `{tmp_batch.get('bytes')}`",
        "- Delete allowed now: `False`",
        "",
        "## Script Route Contraction Files",
        "",
    ]
    for file in as_list(script_lane.get("exact_files_for_next_route_contraction")):
        lines.append(f"- `{file}`")
    lines.extend([
        "",
        "## DB Microbatch",
        "",
        f"- Candidate count: `{db_lane.get('candidate_count')}`",
        f"- Approval packet: `{db_lane.get('approval_packet')}`",
        "- Archive allowed now: `False`",
        "",
        "## Required Boundary",
        "",
        "- Generated cleanup packets are review-only route proof.",
        "- Destructive cleanup requires a separate exact owner approval packet with reference proof, hashes, tombstone/rollback path, and post-cleanup validators.",
    ])
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, plan)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(plan))
    response = {
        "status": plan.get("status"),
        "summary": plan.get("summary"),
        "validation": plan.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(plan if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(plan.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
