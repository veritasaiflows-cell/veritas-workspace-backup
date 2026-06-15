#!/usr/bin/env python3
"""Review-only WF78 source-open repair executor.

This script turns WF78 family-repair classification into concrete repair rows.
It does not edit ticker cards, canon, portfolio state, SQL canon/cache rows, or
any paper/live/account surface. "Execution" here means executing the repair
routing contract: inspect available source lineage, classify what is actually
repairable, and preserve blockers where source evidence is absent.
"""
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
OUT = TMP / "wf78-source-open-repair-execution.json"
REDUCTION = TMP / "wf78-evidence-drag-reduction.json"
SOURCE_REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
SCHEMA = "veritas.wf78_source_open_repair_execution.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "source_open_repair_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
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

TARGET_FAMILIES = {"price_band_stop", "price_band_stop_position_sizing", "deployment_readiness_surface"}
TIER_ORDER = {"Tier A": 0, "Tier B": 1, "Tier C": 2}
STATE_ORDER = {
    "A-READY": 0,
    "A-CHALLENGED": 1,
    "A-WATCH": 2,
    "B-VALIDATED": 3,
    "B-CANDIDATE": 4,
    "C-CANDIDATE-HOLD": 5,
    "C-MONITOR": 6,
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


def load_queue() -> list[dict[str, Any]]:
    return [as_dict(row) for row in as_list(load_dict(REDUCTION).get("queue"))]


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def card_for(ticker: str) -> dict[str, Any]:
    path = card_path(ticker)
    if not path.exists():
        return {}
    return load_dict(path)


def source_registry() -> dict[str, Any]:
    return as_dict(load_dict(SOURCE_REGISTRY).get("tickers"))


def stale_families(row: dict[str, Any]) -> list[str]:
    return [str(item) for item in as_list(row.get("stale_families"))]


def matched_families(row: dict[str, Any]) -> set[str]:
    return set(stale_families(row)) & TARGET_FAMILIES


def repair_mode(row: dict[str, Any]) -> str:
    matched = matched_families(row)
    tier = str(row.get("auto_tier") or "")
    state = str(row.get("route_state") or "")
    if "price_band_stop_position_sizing" in matched:
        return "position_sizing_readiness_surface_required"
    if "deployment_readiness_surface" in matched:
        return "deployment_readiness_surface_required"
    if "price_band_stop" in matched and (tier == "Tier C" or state.startswith("C-")):
        return "thin_monitor_source_open_entry_stop_required"
    if "price_band_stop" in matched:
        return "source_open_entry_stop_required"
    return "inspect"


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        TIER_ORDER.get(str(row.get("auto_tier")), 9),
        STATE_ORDER.get(str(row.get("route_state")), 99),
        -int(row.get("priority_score") or 0),
        int(row.get("queue_rank") or 99999),
        str(row.get("ticker") or ""),
    )


def source_status(ticker: str, card: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    reference = as_dict(card.get("entry_stop_reference_metadata"))
    price_band = as_dict(card.get("price_band_stop"))
    source_lineage = as_dict(reference.get("source_lineage"))
    registry_row = as_dict(registry.get(ticker))
    owner_source = source_lineage.get("owner_source_path")
    has_entry_stop = (
        reference.get("status") == "available"
        and bool(as_dict(reference.get("values")).get("reference_price_low") is not None)
        and bool(as_dict(reference.get("values")).get("reference_price_high") is not None)
        and bool(as_dict(reference.get("values")).get("reference_invalidation_level") is not None)
    )
    has_card_band = all(
        price_band.get(key) is not None
        for key in ("entry_band_low", "entry_band_high", "stop_or_invalidation")
    )
    return {
        "entry_stop_reference_status": reference.get("status") or "missing",
        "entry_stop_reference_available": bool(has_entry_stop),
        "card_price_band_available": bool(has_card_band),
        "owner_source_path": owner_source,
        "owner_source_timestamp": source_lineage.get("source_timestamp"),
        "owner_source_sha256": source_lineage.get("source_sha256"),
        "official_registry_available": bool(registry_row),
        "official_registry_source_url": registry_row.get("official_earnings_source_url"),
        "official_registry_label": registry_row.get("source_label"),
    }


def disposition(mode: str, status: dict[str, Any], tier: str) -> tuple[str, str]:
    if mode == "position_sizing_readiness_surface_required":
        if status["entry_stop_reference_available"] or status["card_price_band_available"]:
            return (
                "needs_position_sizing_surface",
                "entry/stop source exists; missing row is deployment or position-sizing readiness, not fabricated band/stop",
            )
        return (
            "needs_source_artifact",
            "position-sizing gap also lacks source-backed entry/stop reference; source-open repair required first",
        )
    if mode == "source_open_entry_stop_required":
        if status["entry_stop_reference_available"]:
            return ("repaired_from_owner_source", "owner source lineage already provides entry/stop reference")
        if status["official_registry_available"]:
            return ("needs_owner_entry_stop_source", "official earnings source exists, but owner entry/stop source is missing")
        return ("needs_source_artifact", "no owner entry/stop source or official registry pointer found")
    if mode == "thin_monitor_source_open_entry_stop_required":
        if tier == "Tier C":
            return ("thin_monitor_hold", "Tier C row remains monitor-only until promoted or source-open evidence is added")
        return ("needs_source_artifact", "non-Tier C row needs explicit source-open entry/stop repair")
    if mode == "deployment_readiness_surface_required":
        return ("needs_deployment_readiness_surface", "deployment-readiness context missing")
    return ("inspect", "unclassified repair mode")


def build_rows(tier: str, include_tier_c: bool) -> list[dict[str, Any]]:
    registry = source_registry()
    rows = []
    for row in sorted(load_queue(), key=sort_key):
        ticker = str(row.get("ticker") or "")
        auto_tier = str(row.get("auto_tier") or "")
        if not matched_families(row):
            continue
        if tier != "all" and auto_tier != f"Tier {tier}":
            continue
        if not include_tier_c and auto_tier == "Tier C":
            continue
        card = card_for(ticker)
        mode = repair_mode(row)
        status = source_status(ticker, card, registry)
        disp, reason = disposition(mode, status, auto_tier)
        rows.append({
            "ticker": ticker,
            "auto_tier": auto_tier,
            "route_state": row.get("route_state"),
            "queue_rank": row.get("queue_rank"),
            "priority_score": row.get("priority_score"),
            "matched_families": sorted(matched_families(row)),
            "all_stale_families": stale_families(row),
            "repair_mode": mode,
            "repair_disposition": disp,
            "disposition_reason": reason,
            "source_status": status,
            "card_path": rel(card_path(ticker)) if card else None,
            "next_action": next_action(disp, ticker),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    return rows


def next_action(disposition_name: str, ticker: str) -> str:
    if disposition_name == "needs_position_sizing_surface":
        return f"Add or refresh position-sizing/deployment-readiness surface row for {ticker}; then rerun ticker-card refresh gate."
    if disposition_name == "repaired_from_owner_source":
        return f"Rerun ticker-card refresh/evidence reducer to verify {ticker} clears source-open entry/stop debt."
    if disposition_name == "needs_owner_entry_stop_source":
        return f"Open owner entry/stop source for {ticker}; official earnings registry alone is not enough."
    if disposition_name == "needs_source_artifact":
        return f"Create/source-open owner entry/stop evidence for {ticker}, or preserve blocked proof."
    if disposition_name == "thin_monitor_hold":
        return f"Keep {ticker} thin-monitor until promoted or source-open entry/stop evidence exists."
    if disposition_name == "needs_deployment_readiness_surface":
        return f"Add {ticker} to deployment-readiness surface or preserve context blocker."
    return f"Inspect {ticker} repair row."


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rows = build_rows(args.tier, args.include_tier_c)
    mode_counts = Counter(row["repair_mode"] for row in rows)
    disposition_counts = Counter(row["repair_disposition"] for row in rows)
    tier_counts = Counter(row["auto_tier"] for row in rows)
    source_refs = sum(1 for row in rows if row["source_status"].get("entry_stop_reference_available"))
    validation_errors: list[str] = []
    if any(
        row.get("capital_deployment_approved")
        or row.get("trade_or_execution_approved")
        or row.get("paper_or_live_execution_allowed")
        or row.get("owner_approval_inferred")
        for row in rows
    ):
        validation_errors.append("authority boundary widened in one or more repair rows")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_errors else "ok",
        "purpose": "Execute review-only source-open repair routing over WF78 classified evidence debt.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(REDUCTION), rel(SOURCE_REGISTRY), "tmp/ticker-intelligence-cards/*.current.json"],
        "parameters": {
            "tier": args.tier,
            "include_tier_c": bool(args.include_tier_c),
        },
        "summary": {
            "row_count": len(rows),
            "tier_counts": dict(tier_counts.most_common()),
            "repair_mode_counts": dict(mode_counts.most_common()),
            "repair_disposition_counts": dict(disposition_counts.most_common()),
            "entry_stop_reference_available_count": source_refs,
            "priority_tickers": [row["ticker"] for row in rows[:35]],
            "next_safe_action": "Work needs_position_sizing_surface and needs_owner_entry_stop_source rows first; preserve thin-monitor holds.",
        },
        "rows": rows,
        "validation": {
            "status": "blocked" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [],
        },
        "stop_lines": [
            "This artifact classifies repair work only; it does not mutate ticker cards, canon, portfolio, or SQL canon/cache.",
            "Official earnings registry pointers do not replace owner entry/stop source evidence.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute review-only WF78 source-open repair routing.")
    parser.add_argument("--tier", choices=["A", "B", "C", "all"], default="all")
    parser.add_argument("--include-tier-c", action="store_true", help="Include Tier C thin-monitor rows.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} rows={report['summary']['row_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
