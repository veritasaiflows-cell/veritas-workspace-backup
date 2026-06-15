#!/usr/bin/env python3
"""Build a compact WF78 repair debt scoreboard for the next repair wave."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-repair-debt-scoreboard.json"
SCHEMA = "veritas.wf78_repair_debt_scoreboard.v1"

LEDGER = TMP / "wf78-ticker-freshness-ledger.json"
EXECUTOR = TMP / "wf78-source-open-repair-execution.json"
PACKETS = TMP / "wf78-source-open-work-packets.json"
POSITION = TMP / "wf78-position-sizing-integration-proposal.json"
DEPLOYMENT = TMP / "wf78-deployment-readiness-review.json"
REGISTRY_PREVIEW = TMP / "wf78-official-registry-apply-preview.json"
LINEAGE_DISCOVERY = TMP / "wf78-owner-lineage-discovery.json"
CONTRACT_GUARD = TMP / "wf78-contract-state-guard.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "scoreboard_only": True,
    "registry_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
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


def next_wave_items(position: dict[str, Any], deployment: dict[str, Any], registry_preview: dict[str, Any], lineage: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    pos_summary = as_dict(position.get("summary"))
    items.append({
        "phase": "position_sizing_surface_integration",
        "status": "ready_for_review" if int(pos_summary.get("ready_for_review_count") or 0) else "blocked",
        "row_count": pos_summary.get("proposal_row_count", 0),
        "ready_count": pos_summary.get("ready_for_review_count", 0),
        "blocked_count": pos_summary.get("blocked_count", 0),
        "recommended_next_action": "Review Tier A ready slice first, then Tier B ready slice; keep blocked rows out.",
    })
    dep_summary = as_dict(deployment.get("summary"))
    items.append({
        "phase": "deployment_readiness_singleton",
        "status": "ready_for_review" if int(dep_summary.get("ready_for_review_count") or 0) else "blocked_or_empty",
        "row_count": dep_summary.get("row_count", 0),
        "ready_count": dep_summary.get("ready_for_review_count", 0),
        "blocked_count": int(dep_summary.get("row_count") or 0) - int(dep_summary.get("ready_for_review_count") or 0),
        "recommended_next_action": "Package the singleton as review-only deployment-readiness row; do not mutate deployment surface.",
    })
    reg_summary = as_dict(registry_preview.get("summary"))
    items.append({
        "phase": "official_registry_apply_preview",
        "status": "preview_ready" if int(reg_summary.get("would_add_count") or 0) else "no_clean_additions",
        "row_count": reg_summary.get("preview_row_count", 0),
        "ready_count": reg_summary.get("would_add_count", 0),
        "blocked_count": reg_summary.get("blocked_or_skipped_count", 0),
        "recommended_next_action": "Use preview for separate owner/gated apply review only.",
    })
    lineage_summary = as_dict(lineage.get("summary"))
    lineage_counts = as_dict(lineage_summary.get("discovery_status_counts"))
    items.append({
        "phase": "owner_entry_stop_lineage",
        "status": "blocked_owner_decision_required" if int(lineage_summary.get("lineage_missing_or_owner_decision_count") or 0) else "lineage_found",
        "row_count": lineage_summary.get("target_row_count", 0),
        "ready_count": lineage_summary.get("lineage_found_count", 0),
        "blocked_count": lineage_summary.get("lineage_missing_or_owner_decision_count", 0),
        "status_counts": lineage_counts,
        "recommended_next_action": "Only lineage_found rows can advance; needs_owner_decision remains blocked.",
    })
    return items


def build() -> dict[str, Any]:
    ledger = load_dict(LEDGER)
    executor = load_dict(EXECUTOR)
    packets = load_dict(PACKETS)
    position = load_dict(POSITION)
    deployment = load_dict(DEPLOYMENT)
    registry_preview = load_dict(REGISTRY_PREVIEW)
    lineage = load_dict(LINEAGE_DISCOVERY)
    contract = load_dict(CONTRACT_GUARD)
    exec_summary = as_dict(executor.get("summary"))
    repair_counts = as_dict(exec_summary.get("repair_disposition_counts"))
    packet_summary = as_dict(packets.get("summary"))
    next_items = next_wave_items(position, deployment, registry_preview, lineage)
    wave_counts = Counter(str(item.get("status")) for item in next_items)
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        if key not in {"review_only", "scoreboard_only"} and value is not False:
            errors.append(f"authority flag not false: {key}")
    if as_dict(contract.get("validation")).get("status") not in {"ok", None}:
        errors.append("contract guard is not clean")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only WF78 repair debt scoreboard and next-wave planner.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(p) for p in [LEDGER, EXECUTOR, PACKETS, POSITION, DEPLOYMENT, REGISTRY_PREVIEW, LINEAGE_DISCOVERY, CONTRACT_GUARD]],
        "summary": {
            "freshness_state_counts": as_dict(as_dict(ledger.get("summary")).get("freshness_state_counts")),
            "explicit_repair_disposition_counts": repair_counts,
            "work_packet_counts": {
                "work_item_count": packet_summary.get("work_item_count"),
                "packet_count": packet_summary.get("packet_count"),
                "parallel_recommended_count": packet_summary.get("parallel_recommended_count"),
            },
            "next_wave_status_counts": dict(wave_counts),
            "next_safe_action": "Run position sizing review integration and deployment singleton review first; registry apply and owner-lineage remain gated/blocked until owner authority exists.",
        },
        "next_wave": next_items,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Scoreboard only; no registry/card/deployment/canon/portfolio/SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 repair debt scoreboard.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} phases={len(report['next_wave'])}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
