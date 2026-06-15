#!/usr/bin/env python3
"""Build WF78 position-sizing/deployment-readiness review packaging.

This script consumes existing source-open work packets and current ticker cards
to produce a review-only surface for rows that need position-sizing context. It
does not mutate ticker cards, deployment surfaces, canon, portfolio state, or
any execution/account surface.
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
SOURCE_PACKETS = TMP / "wf78-source-open-work-packets.json"
DEPLOYMENT_SURFACE = TMP / "deployment-readiness-surface.json"
DECISION_FACTORY = TMP / "finance-decision-factory.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT = TMP / "wf78-position-sizing-surface-review.json"
SCHEMA = "veritas.wf78_position_sizing_surface_review.v1"

TARGET_LANE = "position_sizing_surface"
TARGET_DISPOSITION = "needs_position_sizing_surface"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "position_sizing_surface_review_only": True,
    "non_executing_review_packaging_only": True,
    "automated_non_capital_routing_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_AUTHORITY = {
    "review_only",
    "position_sizing_surface_review_only",
    "non_executing_review_packaging_only",
    "automated_non_capital_routing_allowed",
}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    path = resolve(path)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    path = resolve(path)
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def card_path(symbol: str) -> Path:
    return CARD_DIR / f"{symbol}.current.json"


def load_card(symbol: str) -> dict[str, Any]:
    path = card_path(symbol)
    return load_dict(path) if path.exists() else {}


def deployment_rows(surface: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for group_name, group_rows in as_dict(surface.get("groups")).items():
        for item in as_list(group_rows):
            row = as_dict(item)
            symbol = ticker(row.get("ticker"))
            if symbol:
                row = dict(row)
                row["_surface_group"] = group_name
                rows[symbol] = row
    return rows


def decision_rows(factory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(factory.get("decision_ledger")):
        row = as_dict(item)
        symbol = ticker(row.get("ticker"))
        if symbol:
            rows[symbol] = row
    return rows


def current_band_context(packet_row: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    packet_band = as_dict(packet_row.get("current_band_context"))
    card_band = as_dict(card.get("price_band_stop"))
    reference = as_dict(card.get("entry_stop_reference_metadata"))
    values = as_dict(reference.get("values"))
    lineage = as_dict(reference.get("source_lineage"))
    return {
        "current_price": (
            card_band.get("latest_known_price")
            or card.get("latest_known_price")
            or packet_band.get("latest_known_price")
        ),
        "entry_band_low": (
            card_band.get("entry_band_low")
            or values.get("reference_price_low")
            or packet_band.get("entry_band_low")
        ),
        "entry_band_high": (
            card_band.get("entry_band_high")
            or values.get("reference_price_high")
            or packet_band.get("entry_band_high")
        ),
        "stop_or_invalidation": (
            card_band.get("stop_or_invalidation")
            or values.get("reference_invalidation_level")
            or packet_band.get("stop_or_invalidation")
        ),
        "band_status": card_band.get("band_status") or packet_band.get("band_status"),
        "entry_stop_reference_status": reference.get("status") or packet_band.get("entry_stop_reference_status"),
        "price_source": card_band.get("price_source"),
        "band_source": card_band.get("band_source"),
        "stop_source": card_band.get("stop_source"),
        "owner_source_path": (
            lineage.get("owner_source_path")
            or values.get("reference_level_owner_source_path")
            or packet_band.get("owner_source_path")
        ),
        "owner_source_timestamp": (
            lineage.get("source_timestamp")
            or values.get("reference_level_source_timestamp")
            or packet_band.get("owner_source_timestamp")
        ),
        "owner_source_sha256": (
            lineage.get("source_sha256")
            or values.get("reference_level_source_sha256")
            or packet_band.get("owner_source_sha256")
        ),
    }


def source_lineage(packet_row: dict[str, Any], card: dict[str, Any], band: dict[str, Any]) -> dict[str, Any]:
    source_artifacts = set(str(item) for item in as_list(packet_row.get("source_artifacts")) if item)
    symbol = ticker(packet_row.get("ticker"))
    if symbol:
        source_artifacts.add(rel(card_path(symbol)))
    reference = as_dict(card.get("entry_stop_reference_metadata"))
    source_rows = [
        {
            "key": as_dict(item).get("key"),
            "source_artifact_path": as_dict(item).get("source_artifact_path"),
            "freshness_status": as_dict(item).get("freshness_status"),
        }
        for item in as_list(reference.get("source_rows"))
    ]
    return {
        "available": bool(
            packet_row.get("source_lineage_available")
            or band.get("owner_source_path")
            or source_rows
        ),
        "owner_source_path": band.get("owner_source_path"),
        "owner_source_timestamp": band.get("owner_source_timestamp"),
        "owner_source_sha256": band.get("owner_source_sha256"),
        "source_artifacts": sorted(source_artifacts),
        "source_rows": source_rows[:6],
    }


def readiness_status(deploy: dict[str, Any]) -> dict[str, Any]:
    return {
        "deployment_surface_present": bool(deploy),
        "surface_group": deploy.get("_surface_group"),
        "deployment_status": deploy.get("deployment_status"),
        "band_position": deploy.get("band_position"),
        "display_label": deploy.get("display_label"),
        "status_reason": deploy.get("status_reason"),
        "review_only_no_apply_artifact": deploy.get("review_only_no_apply_artifact"),
        "source_artifact_path": deploy.get("source_artifact_path"),
        "source_generated_at_utc": deploy.get("source_generated_at_utc"),
    }


def decision_status(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "finance_decision_factory_present": bool(decision),
        "factory_disposition": decision.get("disposition"),
        "gate_verdict": decision.get("gate_verdict"),
        "blocked_reason": decision.get("blocked_reason"),
        "owner_card_path": decision.get("owner_card_path"),
        "wf67_request_path": decision.get("wf67_request_path"),
        "wf67_request_generation_status": decision.get("wf67_request_generation_status"),
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def readiness_impact(packet_row: dict[str, Any], deploy: dict[str, Any], decision: dict[str, Any]) -> str:
    if decision.get("disposition"):
        return "finance_decision_factory_context_exists_review_only"
    if deploy:
        return "deployment_surface_row_exists_review_only_recheck_needed"
    impact = str(packet_row.get("readiness_impact") or "")
    if impact:
        return impact
    tier = str(packet_row.get("auto_tier") or "")
    if tier == "Tier A":
        return "tier_a_repair_unblocks_decision_grade_review"
    if tier == "Tier B":
        return "tier_b_repair_unblocks_promotion_review"
    return "monitor_only_review_context"


def proposed_action(symbol: str, band: dict[str, Any], deploy: dict[str, Any]) -> str:
    if deploy:
        return (
            f"Review {symbol} against the existing deployment-readiness surface row, preserving "
            "review-only status and all execution/account/capital blocks."
        )
    if band.get("owner_source_path"):
        return (
            f"Package {symbol} for non-executing position-sizing/deployment-readiness review "
            "using the current card price, written band, stop, and owner source lineage."
        )
    return (
        f"Hold {symbol} for source-open repair before any position-sizing surface review row is packaged."
    )


def residual_blocker(card: dict[str, Any], band: dict[str, Any], lineage: dict[str, Any]) -> str | None:
    required = {
        "current_price": band.get("current_price"),
        "entry_band_low": band.get("entry_band_low"),
        "entry_band_high": band.get("entry_band_high"),
        "stop_or_invalidation": band.get("stop_or_invalidation"),
        "band_status": band.get("band_status"),
    }
    missing = [key for key, value in required.items() if value in {None, ""}]
    if not card:
        return "missing_current_ticker_card"
    if missing:
        return "missing_band_context:" + ",".join(missing)
    if not lineage.get("available"):
        return "missing_owner_entry_stop_source_lineage"
    return "awaits_main_session_integration_review_no_mutation_authority"


def validation_status(blocker: str | None) -> str:
    if blocker == "awaits_main_session_integration_review_no_mutation_authority":
        return "ready_for_non_executing_review_packaging"
    if blocker:
        return "blocked_" + blocker.split(":", 1)[0]
    return "ready_for_non_executing_review_packaging"


def target_packet_rows(source: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for packet_item in as_list(source.get("packets")):
        packet = as_dict(packet_item)
        if packet.get("lane") != TARGET_LANE or packet.get("disposition") != TARGET_DISPOSITION:
            continue
        for row_item in as_list(packet.get("rows")):
            row = as_dict(row_item)
            if row.get("repair_disposition") == TARGET_DISPOSITION:
                rows.append((packet, row))
    return rows


def build_rows(source: dict[str, Any], deployment: dict[str, Any], factory: dict[str, Any]) -> list[dict[str, Any]]:
    deploy_by_ticker = deployment_rows(deployment)
    decision_by_ticker = decision_rows(factory)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for packet, packet_row in target_packet_rows(source):
        symbol = ticker(packet_row.get("ticker"))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        card = load_card(symbol)
        band = current_band_context(packet_row, card)
        lineage = source_lineage(packet_row, card, band)
        deploy = deploy_by_ticker.get(symbol, {})
        decision = decision_by_ticker.get(symbol, {})
        blocker = residual_blocker(card, band, lineage)
        rows.append({
            "ticker": symbol,
            "packet_id": packet.get("packet_id"),
            "lane": packet.get("lane"),
            "disposition": packet.get("disposition"),
            "tier": packet_row.get("auto_tier"),
            "route_state": packet_row.get("route_state"),
            "queue_rank": packet_row.get("queue_rank"),
            "priority_score": packet_row.get("priority_score"),
            "freshness_state": packet_row.get("freshness_state"),
            "current_price": band.get("current_price"),
            "band": {
                "entry_band_low": band.get("entry_band_low"),
                "entry_band_high": band.get("entry_band_high"),
                "stop_or_invalidation": band.get("stop_or_invalidation"),
            },
            "band_status": band.get("band_status"),
            "source_lineage": lineage,
            "readiness_impact": readiness_impact(packet_row, deploy, decision),
            "deployment_readiness_context": readiness_status(deploy),
            "finance_decision_factory_context": decision_status(decision),
            "proposed_non_executing_review_action": proposed_action(symbol, band, deploy),
            "residual_blocker": blocker,
            "validation_status": validation_status(blocker),
            "authority_boundary": {
                "capital_deployment_allowed": False,
                "trade_or_execution_allowed": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "money_movement_allowed": False,
                "canon_or_portfolio_mutation_allowed": False,
                "ticker_card_mutation_allowed": False,
                "deployment_surface_mutation_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return rows


def validate_report(report: dict[str, Any], source_exists: bool) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = as_list(report.get("rows"))
    boundary = as_dict(report.get("authority_boundary"))
    for key in sorted(FALSE_AUTHORITY):
        if boundary.get(key) is not False:
            errors.append(f"authority flag not hard-false: {key}")
    if not source_exists:
        errors.append(f"missing source artifact: {rel(SOURCE_PACKETS)}")
    if not rows:
        warnings.append("no target position-sizing rows found")
    for row in rows:
        item = as_dict(row)
        if item.get("lane") != TARGET_LANE:
            errors.append(f"non-target lane included: {item.get('ticker')} lane={item.get('lane')}")
        if item.get("disposition") != TARGET_DISPOSITION:
            errors.append(f"non-target disposition included: {item.get('ticker')} disposition={item.get('disposition')}")
        if any(as_dict(item.get("authority_boundary")).get(key) is not False for key in [
            "capital_deployment_allowed",
            "trade_or_execution_allowed",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "money_movement_allowed",
            "canon_or_portfolio_mutation_allowed",
            "ticker_card_mutation_allowed",
            "deployment_surface_mutation_allowed",
            "owner_approval_inferred",
        ]):
            errors.append(f"row authority widened: {item.get('ticker')}")
    blocked_rows = [as_dict(row).get("ticker") for row in rows if str(as_dict(row).get("validation_status", "")).startswith("blocked_")]
    if blocked_rows:
        warnings.append("rows retain residual blockers: " + ",".join(str(item) for item in blocked_rows))
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    source_path = resolve(args.source)
    source = load_dict(source_path)
    deployment = load_dict(args.deployment_surface)
    factory = load_dict(args.decision_factory)
    rows = build_rows(source, deployment, factory)
    tier_counts = Counter(str(row.get("tier")) for row in rows)
    band_counts = Counter(str(row.get("band_status")) for row in rows)
    blocker_counts = Counter(str(row.get("residual_blocker")) for row in rows)
    impact_counts = Counter(str(row.get("readiness_impact")) for row in rows)
    packet_ids = sorted(set(str(row.get("packet_id")) for row in rows if row.get("packet_id")))
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "pending_validation",
        "purpose": "Review-only WF78 position-sizing/deployment-readiness packaging for source-open rows.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "target": {
            "lane": TARGET_LANE,
            "disposition": TARGET_DISPOSITION,
        },
        "source_artifacts": {
            "work_packets": rel(source_path),
            "deployment_readiness_surface": rel(args.deployment_surface),
            "finance_decision_factory": rel(args.decision_factory),
            "ticker_cards": "tmp/ticker-intelligence-cards/*.current.json",
        },
        "summary": {
            "target_row_count": len(rows),
            "target_packet_count": len(packet_ids),
            "target_packet_ids": packet_ids,
            "tier_counts": dict(tier_counts.most_common()),
            "band_status_counts": dict(band_counts.most_common()),
            "readiness_impact_counts": dict(impact_counts.most_common()),
            "residual_blocker_counts": dict(blocker_counts.most_common()),
            "deployment_surface_context_count": sum(1 for row in rows if as_dict(row.get("deployment_readiness_context")).get("deployment_surface_present")),
            "decision_factory_context_count": sum(1 for row in rows if as_dict(row.get("finance_decision_factory_context")).get("finance_decision_factory_present")),
            "next_safe_action": (
                "No pending position-sizing surface rows remain after the current repair/apply cycle."
                if not rows
                else "Review ready rows first; keep packaging non-executing and review-only."
            ),
        },
        "rows": rows,
        "validation": {},
        "stop_lines": [
            "Review-only packaging; do not mutate ticker cards, canon, portfolio, deployment surfaces, SQL canon/cache, or control surfaces.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference is granted by this artifact.",
            "A ready row means non-executing main-session review context only; Randall's exact approval remains required for any paper/live/account/capital action.",
        ],
    }
    validation = validate_report(report, source_path.exists())
    report["validation"] = validation
    report["status"] = validation["status"]
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 position-sizing surface review packaging.")
    parser.add_argument("--write", action="store_true", help="Write the JSON artifact.")
    parser.add_argument("--validate", action="store_true", help="Fail nonzero when validation is blocked.")
    parser.add_argument("--out", type=Path, default=OUT, help="Output JSON path.")
    parser.add_argument("--source", type=Path, default=SOURCE_PACKETS, help="Source-open work packets JSON path.")
    parser.add_argument("--deployment-surface", type=Path, default=DEPLOYMENT_SURFACE, help="Optional deployment-readiness surface JSON path.")
    parser.add_argument("--decision-factory", type=Path, default=DECISION_FACTORY, help="Optional finance decision factory JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = resolve(args.out)
    report = build_report(args)
    if args.write:
        atomic_write_json(out, report)
        print(
            f"wrote {rel(out)} status={report['status']} "
            f"rows={report['summary']['target_row_count']} packets={report['summary']['target_packet_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
