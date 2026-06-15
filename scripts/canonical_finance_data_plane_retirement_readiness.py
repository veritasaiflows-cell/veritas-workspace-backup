#!/usr/bin/env python3
"""Assess WF84 duplicate-surface retirement readiness.

This is a preview-only proof packet. It does not archive, move, delete, rewrite,
checkpoint, vacuum, or mutate any data surface.

Any future approved lifecycle action must hand off to
`scripts/db_lifecycle_manifest.py`; this script only proves readiness remains
blocked.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "canonical-finance-data-plane-retirement-readiness.json"

SCHEMA = "veritas.canonical_finance_data_plane_retirement_readiness.v1"

SURFACES = [
    {
        "path": "tmp/finance-intelligence-state.sqlite",
        "owner": "WF78 finance intelligence state",
        "classification": "retain_active_consumer_fallback",
        "reason": "Existing ticker/front-door consumer still owns fallback and rich packet behavior; WF84 overlay is additive only.",
    },
    {
        "path": "tmp/wf78-auto-tier-routing.json",
        "owner": "WF78 auto-router",
        "classification": "retain_source_feeder",
        "reason": "Primary non-capital Tier A/B/C routing source feeding WF84; not duplicate truth.",
    },
    {
        "path": "tmp/wf78-tier-weighted-freshness-resolution.json",
        "owner": "WF78 freshness resolution",
        "classification": "retain_source_feeder",
        "reason": "Evidence/freshness resolution source feeding WF84; not replaced by canonical interface.",
    },
    {
        "path": "tmp/finance-decision-sync-spine.json",
        "owner": "finance decision sync spine",
        "classification": "retain_optional_enrichment",
        "reason": "Wider 206-row sync/enrichment surface; WF84 records its 6 extras but does not replace its synchronization role.",
    },
    {
        "path": "tmp/wf78-capital-review-queue.json",
        "owner": "WF78 capital-review preparation",
        "classification": "retain_non_executing_review_queue",
        "reason": "Owner-review queue source only; WF84 normalizes selected fields but does not own queue generation.",
    },
    {
        "path": "tmp/canonical-finance-data-plane-contract.json",
        "owner": "WF84 canonical finance data-plane",
        "classification": "retain_contract",
        "reason": "Schema/feeder/validator contract remains the design control surface for the packet and DB companion.",
    },
    {
        "path": "tmp/ticker-answer-packets",
        "owner": "ticker answer packet response layer",
        "classification": "compatibility_snapshot_retirement_candidate_planning_only",
        "reason": "Legacy generated answer packets are now compatibility snapshots generated from the WF85 full-answer assembler; keep them until active readers are migrated and Randall approves the exact retirement packet.",
    },
    {
        "path": "tmp/ticker-intelligence-cards",
        "owner": "ticker intelligence evidence cache",
        "classification": "retain_evidence_cache",
        "reason": "Cards still carry rich source-fed evidence sections and remain source-openable evidence caches under WF84/WF85.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def text_files() -> list[Path]:
    roots = [ROOT / "scripts", ROOT / "06. Playbooks", ROOT / "TOOLS.md", ROOT / "memory"]
    suffixes = {".py", ".md", ".json", ".txt"}
    out: list[Path] = []
    for root in roots:
        if root.is_file():
            out.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes and "__pycache__" not in path.parts:
                out.append(path)
    return out


def reference_count(surface_path: str, files: list[Path]) -> dict[str, Any]:
    needles = {
        surface_path,
        surface_path.replace("/", "\\"),
        Path(surface_path).name,
    }
    refs: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            refs.append(rel(path))
    active_refs = [
        item for item in refs
        if not item.startswith("memory/") and not item.startswith("06. Playbooks/Project Continuity/")
    ]
    return {
        "reference_count": len(refs),
        "active_reference_count": len(active_refs),
        "sample_references": refs[:20],
    }


def build_packet() -> dict[str, Any]:
    files = text_files()
    parity_path = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
    try:
        parity = json.loads(parity_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        parity = {}
    parity_summary = parity.get("summary") if isinstance(parity, dict) else {}
    rows: list[dict[str, Any]] = []
    for surface in SURFACES:
        path = ROOT / surface["path"]
        refs = reference_count(surface["path"], files)
        rows.append({
            **surface,
            "exists": path.exists(),
            "archive_ready": False,
            "delete_ready": False,
            "apply_allowed": False,
            "owner_approval_plan": {
                "candidate_action": "retain_now",
                "approval_required_before_archive_or_delete": True,
                "minimum_future_evidence": [
                    "WF84 consumer default switch remains clean",
                    "WF84/WF85 full-answer value parity is clean across the full WF84 ticker population",
                    "WF85 full-answer assembler remains the default ticker answer path",
                    "legacy answer packets are generated only from the assembler",
                    "additional consumers prove parity against WF84",
                    "active references no longer require this surface as feeder or fallback",
                    "ticker-answer-packet retirement approval plan remains planning_ready",
                    "db_lifecycle_manifest.py classifies the database or sidecar as archive_ready",
                    "Randall approves the exact archive packet",
                ],
            },
            **refs,
        })
    archive_ready = [row for row in rows if row["archive_ready"]]
    delete_ready = [row for row in rows if row["delete_ready"]]
    validation = {
        "status": "ok" if not archive_ready and not delete_ready and all(row["apply_allowed"] is False for row in rows) else "blocked",
        "errors": [],
        "warnings": [
        ],
        "checks": [
            {"check": "archive_ready_count_zero", "status": "ok" if not archive_ready else "blocked", "count": len(archive_ready)},
            {"check": "delete_ready_count_zero", "status": "ok" if not delete_ready else "blocked", "count": len(delete_ready)},
            {"check": "apply_allowed_false", "status": "ok" if all(row["apply_allowed"] is False for row in rows) else "blocked"},
        ],
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": validation["status"],
        "workflow_id": "WF84",
        "purpose": "Preview-only retirement readiness for duplicate finance data-plane surfaces after WF84 Phase 1-3.",
        "authority_boundary": {
            "review_only": True,
            "preview_only": True,
            "archive_allowed": False,
            "delete_allowed": False,
            "move_allowed": False,
            "db_mutation_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "capital_or_execution_authority": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "surface_count": len(rows),
            "archive_ready_count": len(archive_ready),
            "delete_ready_count": len(delete_ready),
            "apply_allowed_count": sum(1 for row in rows if row["apply_allowed"]),
            "approval_plan_prepared": True,
            "source_feeder_retirement_ready_count": 0,
            "duplicate_surface_retirement_ready_count": 0,
            "full_answer_parity_status": parity.get("status") if isinstance(parity, dict) else "missing",
            "full_answer_parity_ready_to_start_duplicate_surface_retirement_planning": bool((parity_summary or {}).get("ready_to_start_duplicate_surface_retirement_planning")),
            "archive_plan_owner_action_required": True,
            "next_safe_action": "Use the prepared owner-approval plan only; keep source feeders/fallback surfaces until additional consumer parity and DB lifecycle approval gates clear.",
        },
        "archive_approval_plan": {
            "status": "prepared_for_owner_review",
            "apply_allowed_now": False,
            "archive_allowed_now": False,
            "delete_allowed_now": False,
            "recommended_decision": "do_not_archive_trade_grade_feeders_yet",
            "retained_surfaces": [row["path"] for row in rows],
            "approval_sequence": [
                "Keep WF84 as the default read-only consumer interface while source feeders remain retained.",
                "Use full-answer parity results to identify generated duplicate surfaces, but retain source artifacts and evidence caches.",
                "Run WF84/WF85 freshness, phase 6-10, retirement readiness, and DB lifecycle proof after each consumer migration.",
                "Require active-reference review for every candidate surface.",
                "Prepare a db_lifecycle_archive_apply.py packet only for surfaces that become archive_ready in db_lifecycle_manifest.py.",
                "Ask Randall for exact archive approval before any move/delete/archive apply.",
            ],
        },
        "surfaces": rows,
        "validation": validation,
        "stop_lines": [
            "No archive, move, delete, rewrite, checkpoint, vacuum, or cleanup action.",
            "No source feeder is retired while WF84 remains an interface built from those feeders.",
            "No generated packet or SQLite row becomes canon, portfolio, capital, or execution authority.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    packet = build_packet()
    if args.write:
        atomic_write_json(args.out, packet)
    print(json.dumps({"status": packet["status"], "out": rel(args.out), "summary": packet["summary"], "validation": packet["validation"]}, indent=2))
    if args.validate and packet["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
