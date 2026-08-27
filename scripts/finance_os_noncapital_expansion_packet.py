#!/usr/bin/env python3
"""Build a validated non-capital Finance OS expansion packet."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "finance-os-noncapital-expansion-packet.json"
OUT_MD = TMP / "finance-os-noncapital-expansion-packet.md"
SCHEMA = "veritas.finance_os_noncapital_expansion_packet.v1"

INPUTS = {
    "status_card": TMP / "veritas-status-card.json",
    "wf78_auto_tier_routing": TMP / "wf78-auto-tier-routing.json",
    "wf78_clean_tier_roster": TMP / "wf78-clean-tier-roster.json",
    "wf78_truth_layer_map": TMP / "wf78-truth-layer-map.json",
    "canonical_finance_data_plane": TMP / "canonical-finance-data-plane.json",
    "trade_grade_full_answer_assembler": TMP / "trade-grade-full-answer-assembler.json",
    "workspace_automation_approval": TMP / "workspace-automation-approval-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "non_capital_routing_only": True,
    "derived_artifact_refresh_allowed": True,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
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


def extract_tickers(records: list[Any], limit: int = 20) -> list[str]:
    tickers: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in ("ticker", "symbol", "asset", "name"):
            value = record.get(key)
            if isinstance(value, str) and value and value.upper() == value:
                tickers.append(value)
                break
        if len(tickers) >= limit:
            break
    return tickers


def build_expansion_queue(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    wf78 = artifacts["wf78_auto_tier_routing"]
    roster = artifacts["wf78_clean_tier_roster"]
    status = artifacts["status_card"]
    wf78_visibility = as_dict(status.get("wf78_visibility"))
    wf78_summary = as_dict(wf78.get("summary"))
    roster_summary = as_dict(roster.get("summary"))
    candidates = (
        as_list(wf78.get("routing_candidates"))
        or as_list(wf78.get("candidate_routes"))
        or as_list(wf78.get("items"))
        or as_list(roster.get("clean_tier_roster"))
        or as_list(roster.get("tickers"))
    )
    tickers = extract_tickers(candidates)
    return [
        {
            "name": "WF78 non-capital routing refresh",
            "status": "ready_with_existing_gate" if wf78 else "needs_source_refresh",
            "allowed_action": "Refresh derived non-capital routing artifacts with existing validators.",
            "blocked_actions": [
                "No canon/portfolio mutation.",
                "No cash/sizing/risk change.",
                "No paper/live order or brokerage/account action.",
            ],
            "candidate_tickers_preview": tickers,
            "source_counts": {
                "wf78_actionable_now_count": wf78_visibility.get("actionable_now_count"),
                "wf78_owner_review_ready_count": wf78_visibility.get("owner_review_ready_count"),
                "wf78_auto_summary": wf78_summary,
                "clean_roster_summary": roster_summary,
            },
            "commands": [
                "python scripts\\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate",
                "python scripts\\wf78_auto_tier_router.py --write --validate",
                "python scripts\\wf78_clean_tier_roster.py --write --validate",
            ],
        },
        {
            "name": "Stale evidence repair queue",
            "status": "ready_for_review_packet",
            "allowed_action": "Prepare source-open repair targets for stale review-only ticker evidence.",
            "blocked_actions": [
                "No recommendation should imply deployment approval.",
                "No generated card becomes owner approval or portfolio truth.",
            ],
            "candidate_tickers_preview": tickers,
            "commands": [
                "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
                "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
            ],
        },
        {
            "name": "Decision-card prep",
            "status": "ready_for_noncapital_card_generation",
            "allowed_action": "Prepare owner-review cards with capital/execution flags false.",
            "blocked_actions": [
                "No trade/order submit/cancel/replace.",
                "No inferred approval from card generation.",
            ],
            "candidate_tickers_preview": tickers,
            "commands": [
                "python scripts\\artifact_index.py ticker-card <TICKER>",
                "python scripts\\artifact_index.py answer-packet <TICKER>",
            ],
        },
    ]


def build_packet(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    queue = build_expansion_queue(artifacts)
    missing = [name for name, path in INPUTS.items() if not path.exists()]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "noncapital_expansion_ready" if len(missing) < len(INPUTS) else "noncapital_expansion_needs_sources",
        "purpose": "Validated expansion queue for Finance OS non-capital routing, stale-evidence repair, and decision-card prep.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {name: rel(path) for name, path in INPUTS.items()},
        "source_status": [input_record(INPUTS[name], artifacts[name], required=False) for name in INPUTS],
        "summary": {
            "queue_count": len(queue),
            "missing_input_count": len(missing),
            "missing_inputs": missing,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
        },
        "expansion_queue": queue,
        "validation": validate_packet_fields(queue),
    }
    return packet


def validate_packet_fields(queue: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    false_flags = [
        "canon_or_portfolio_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ]
    for flag in false_flags:
        if AUTHORITY_BOUNDARY.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")
    if not queue:
        warnings.append("no finance expansion queue items were generated")
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Finance OS Non-Capital Expansion",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- Queue count: {summary.get('queue_count')}",
        f"- Missing inputs: {summary.get('missing_input_count')}",
        "",
        "## Boundary",
        "",
        "- Non-capital routing, stale-evidence repair, and owner-review decision-card prep only.",
        "- No canon/portfolio mutation, cash/sizing/risk change, capital approval, trade approval, or paper/live execution.",
        "",
        "## Queue",
        "",
    ]
    for item in as_list(packet.get("expansion_queue")):
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('name')}: {item.get('status')}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Finance OS non-capital expansion packet.")
    parser.add_argument("--write", action="store_true", help="Write tmp/finance-os-noncapital-expansion-packet.json.")
    parser.add_argument("--write-md", action="store_true", help="Write tmp/finance-os-noncapital-expansion-packet.md.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if packet validation fails.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = {name: load_optional(path) for name, path in INPUTS.items()}
    packet = build_packet(artifacts)
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
