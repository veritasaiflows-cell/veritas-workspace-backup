#!/usr/bin/env python3
"""Build WF78 deployment-readiness review rows from source-open work packets.

This is a review-only proof artifact. It packages deployment-readiness gaps for
owner review without editing deployment surfaces, ticker cards, canon, portfolio
state, SQL canon/cache, or any execution/account surface.
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
OUT = TMP / "wf78-deployment-readiness-review.json"
WORK_PACKETS = TMP / "wf78-source-open-work-packets.json"
DEPLOYMENT_SURFACE = TMP / "deployment-readiness-surface.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
SCHEMA = "veritas.wf78_deployment_readiness_review.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "deployment_readiness_review_packaging_only": True,
    "automated_non_capital_routing_allowed": True,
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

TRUE_AUTHORITY = {"review_only", "deployment_readiness_review_packaging_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


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


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def card_for(symbol: str) -> dict[str, Any]:
    path = CARD_DIR / f"{symbol}.current.json"
    if not path.exists():
        return {}
    return load_dict(path)


def deployment_rows() -> dict[str, dict[str, Any]]:
    surface = load_dict(DEPLOYMENT_SURFACE)
    rows: dict[str, dict[str, Any]] = {}
    for group_name, group in as_dict(surface.get("groups")).items():
        for item in as_list(group):
            row = as_dict(item)
            symbol = ticker(row.get("ticker"))
            if symbol:
                out = dict(row)
                out["_group"] = group_name
                rows[symbol] = out
    return rows


def target_items() -> list[dict[str, Any]]:
    packet = load_dict(WORK_PACKETS)
    items: list[dict[str, Any]] = []
    for work_packet in as_list(packet.get("packets")):
        packet_dict = as_dict(work_packet)
        if packet_dict.get("lane") != "deployment_readiness_surface" and packet_dict.get("disposition") != "needs_deployment_readiness_surface":
            continue
        for row in as_list(packet_dict.get("rows")):
            item = as_dict(row)
            if ticker(item.get("ticker")):
                item["_packet_id"] = packet_dict.get("packet_id")
                items.append(item)
    return items


def band_context(card: dict[str, Any], packet_row: dict[str, Any]) -> dict[str, Any]:
    packet_band = as_dict(packet_row.get("current_band_context"))
    card_band = as_dict(card.get("price_band_stop"))
    return {
        "latest_known_price": packet_band.get("latest_known_price") or card_band.get("latest_known_price") or card.get("latest_known_price"),
        "entry_band_low": packet_band.get("entry_band_low") or card_band.get("entry_band_low"),
        "entry_band_high": packet_band.get("entry_band_high") or card_band.get("entry_band_high"),
        "stop_or_invalidation": packet_band.get("stop_or_invalidation") or card_band.get("stop_or_invalidation"),
        "band_status": packet_band.get("band_status") or card_band.get("band_status"),
        "owner_source_path": packet_band.get("owner_source_path"),
        "owner_source_timestamp": packet_band.get("owner_source_timestamp"),
        "owner_source_sha256": packet_band.get("owner_source_sha256"),
    }


def readiness_recommendation(symbol: str, band: dict[str, Any], deployment_row: dict[str, Any]) -> tuple[str, str]:
    if deployment_row:
        return (
            "surface_row_exists_review_refresh_required",
            f"Refresh the existing deployment-readiness row for {symbol}; preserve review-only authority.",
        )
    if not band.get("entry_band_low") or not band.get("entry_band_high") or not band.get("stop_or_invalidation"):
        return (
            "blocked_missing_entry_stop_context",
            f"Keep {symbol} blocked until source-backed entry band and invalidation are available.",
        )
    return (
        "ready_for_non_executing_deployment_readiness_row",
        f"Prepare a review-only deployment-readiness row for {symbol}; no capital or execution authority.",
    )


def build_rows() -> list[dict[str, Any]]:
    deploy = deployment_rows()
    rows: list[dict[str, Any]] = []
    for item in target_items():
        symbol = ticker(item.get("ticker"))
        card = card_for(symbol)
        deployment_row = deploy.get(symbol, {})
        band = band_context(card, item)
        status, action = readiness_recommendation(symbol, band, deployment_row)
        rows.append({
            "ticker": symbol,
            "packet_id": item.get("_packet_id"),
            "auto_tier": item.get("auto_tier"),
            "route_state": item.get("route_state"),
            "priority_score": item.get("priority_score"),
            "readiness_impact": item.get("readiness_impact"),
            "review_status": status,
            "current_band_context": band,
            "deployment_surface_existing_row": {
                "present": bool(deployment_row),
                "group": deployment_row.get("_group"),
                "bucket": deployment_row.get("deployment_status") or deployment_row.get("surface_state") or deployment_row.get("display_label"),
                "source_artifact_path": deployment_row.get("source_artifact_path"),
                "source_generated_at_utc": deployment_row.get("source_generated_at_utc"),
            },
            "proposed_non_executing_review_action": action,
            "residual_blocker": None if status == "ready_for_non_executing_deployment_readiness_row" else status,
            "source_artifacts": sorted(set([
                rel(WORK_PACKETS),
                rel(DEPLOYMENT_SURFACE),
                rel(CARD_DIR / f"{symbol}.current.json"),
            ])),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    return rows


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rows = build_rows()
    errors: list[str] = []
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if args.validate and not WORK_PACKETS.exists():
        errors.append(f"missing work packet artifact: {rel(WORK_PACKETS)}")
    if any(row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred") for row in rows):
        errors.append("row authority boundary widened")
    status_counts = Counter(str(row.get("review_status")) for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Package WF78 deployment-readiness source-open gaps for owner review without mutation or execution authority.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(WORK_PACKETS), rel(DEPLOYMENT_SURFACE), "tmp/ticker-intelligence-cards/*.current.json"],
        "summary": {
            "row_count": len(rows),
            "review_status_counts": dict(status_counts.most_common()),
            "ready_for_review_count": status_counts.get("ready_for_non_executing_deployment_readiness_row", 0),
            "next_safe_action": "Review ready rows for deployment-readiness surface packaging; do not mutate deployment surfaces or infer approval.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Review-only packaging; no deployment-surface, ticker-card, canon, portfolio, or SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 deployment-readiness review rows.")
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
