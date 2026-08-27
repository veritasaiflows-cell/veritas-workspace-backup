#!/usr/bin/env python3
"""Build a single-ticker WF78 quick route packet.

The packet joins the current auto-tier route with available ticker-card,
stale-evidence, and repair-queue context. It is a derived review artifact only:
no capital deployment, execution, paper/live/account action, or portfolio/canon
mutation authority is created.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from route_readiness import route_readiness_from_route_context

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
TICKER_CARD_SUMMARY = TMP / "ticker-card-refresh-gate-card-build-summary.json"
WF85_CARDS = TMP / "trade-grade-decision-cards.json"
TIER_A_PACKET = TMP / "wf78-tier-a-final-promotion-packet.json"
TIER_B_REPAIR = TMP / "wf78-tier-b-evidence-repair.json"
SCHEMA = "veritas.wf78_route_ticker.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "single_ticker_route_only": True,
    "derived_state_only": True,
    "automated_non_capital_routing_allowed": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "single_ticker_route_only",
    "derived_state_only",
    "automated_non_capital_routing_allowed",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

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


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def ticker_key(value: Any) -> str:
    return str(value or "").strip().upper()


def ticker_card_path(ticker: str) -> Path:
    return TMP / "ticker-intelligence-cards" / f"{ticker}.current.json"


def find_row(rows: list[Any], ticker: str) -> dict[str, Any]:
    for row in rows:
        if isinstance(row, dict) and ticker_key(row.get("ticker")) == ticker:
            return row
    return {}


def stale_row(stale: dict[str, Any], ticker: str) -> dict[str, Any]:
    return find_row(as_list(stale.get("stale_ticker_cards")), ticker)


def card_summary_row(summary: dict[str, Any], ticker: str) -> dict[str, Any]:
    return find_row(as_list(summary.get("cards")), ticker)


def wf85_card_row(packet: dict[str, Any], ticker: str) -> dict[str, Any]:
    return find_row(as_list(packet.get("cards")), ticker)


def route_row(auto_router: dict[str, Any], ticker: str) -> dict[str, Any]:
    return find_row(as_list(auto_router.get("rows")), ticker)


def tier_a_context(packet: dict[str, Any], ticker: str) -> dict[str, Any]:
    if packet and (
        as_dict(packet.get("deprecation_status")).get("deprecated_for_authority") is True
        or TIER_A_PACKET.name == "wf78-tier-a-final-promotion-packet.json"
    ):
        return {
            "deprecated_for_authority": True,
            "replacement": "wf78-auto-tier-routing lane-qualified row",
        }
    row = find_row(as_list(packet.get("rows")), ticker)
    if not row:
        return {}
    return {
        "decision_status": row.get("decision_status"),
        "quote": row.get("quote"),
        "written_band": row.get("written_band"),
        "blockers": as_list(row.get("blockers")),
        "cautions": as_list(row.get("cautions")),
        "source_artifacts": as_list(row.get("source_artifacts")),
    }


def tier_b_repair_context(packet: dict[str, Any], ticker: str) -> dict[str, Any]:
    row = find_row(as_list(packet.get("rows")), ticker)
    if not row:
        return {}
    return {
        "status": row.get("status"),
        "prior_missing_evidence": as_list(row.get("prior_missing_evidence")),
        "repaired_evidence_families": as_list(row.get("repaired_evidence_families")),
        "fresh_price_context": row.get("fresh_price_context"),
        "research_only_context": row.get("research_only_context"),
        "blockers": as_list(row.get("blockers")),
        "cautions": as_list(row.get("cautions")),
    }


def normalize_missing(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def blocking_evidence(missing_or_stale: list[Any]) -> list[Any]:
    result = []
    for item in missing_or_stale:
        if isinstance(item, dict):
            if item.get("severity") == "blocking" or item.get("status") in {"missing", "stale_until_refreshed"}:
                result.append(item)
        elif item:
            result.append(item)
    return result


def route_readiness(route: dict[str, Any], wf85: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    return route_readiness_from_route_context(route, wf85, card)


def next_safe_action(route: dict[str, Any], card: dict[str, Any], stale: dict[str, Any], capital_card_warranted: bool) -> str:
    state = str(route.get("auto_state") or "")
    lane = str(route.get("review_lane") or "")
    support = str(as_dict(card.get("recommendation_support")).get("posture") or "")
    missing = normalize_missing(card.get("missing_or_stale_evidence")) or normalize_missing(stale.get("missing_or_stale"))
    if route.get("auto_tier") == "Tier A" and lane and lane != "equity_depth":
        return "Keep as lane-qualified opportunity routing; use the lane-specific evidence gate before any owner-review packet."
    if capital_card_warranted:
        return "Prepare a non-executing owner capital-review card; do not execute or imply approval."
    if state == "A-READY":
        return "Refresh quote/band/stop and source-open blockers before any owner approval-card preparation."
    if "CHALLENGED" in state:
        return "Keep in challenged review; repair thesis, evidence, or band/stop conflict before escalation."
    if state in {"B-VALIDATED", "B-CANDIDATE"}:
        return "Continue Tier B research/evidence repair; do not treat as deployment-ready."
    if state == "C-CANDIDATE-HOLD":
        return "Hold as Tier C candidate until quality, capacity, or evidence burden clears."
    if support == "blocked stale" or missing:
        return "Repair stale or missing ticker-card evidence before promotion or recommendation use."
    return "Monitor under current non-capital route; rerun WF78 gates if a material event changes evidence."


def build_packet(ticker: str) -> dict[str, Any]:
    auto_router = load_dict(AUTO_ROUTER)
    stale = load_dict(STALE_TICKERS)
    card_summary = load_dict(TICKER_CARD_SUMMARY)
    wf85_cards = load_dict(WF85_CARDS)
    tier_a = load_dict(TIER_A_PACKET)
    tier_b = load_dict(TIER_B_REPAIR)
    card_path = ticker_card_path(ticker)
    card = load_dict(card_path)
    route = route_row(auto_router, ticker)
    stale_context = stale_row(stale, ticker)
    summary_context = card_summary_row(card_summary, ticker)
    wf85_context = wf85_card_row(wf85_cards, ticker)
    missing_or_stale = normalize_missing(card.get("missing_or_stale_evidence")) or normalize_missing(stale_context.get("missing_or_stale"))
    blockers = as_list(stale_context.get("blockers")) or as_list(as_dict(card.get("recommendation_support")).get("blockers_or_gates"))
    blocking = blocking_evidence(missing_or_stale)
    recommendation = as_dict(card.get("recommendation_support"))
    band = as_dict(card.get("price_band_stop"))
    tier_a_ctx = tier_a_context(tier_a, ticker)
    tier_b_ctx = tier_b_repair_context(tier_b, ticker)
    auto_state = str(route.get("auto_state") or "")
    readiness = route_readiness(route, wf85_context, card)
    capital_card_warranted = (
        auto_state == "A-READY"
        and route.get("review_lane") in {None, "equity_depth"}
        and str(recommendation.get("posture_key") or recommendation.get("posture") or "").lower() in {"promotion_review", "approval_ready"}
        and not blocking
        and int(summary_context.get("missing_or_stale_count") or 0) == 0
    )

    checks: list[dict[str, Any]] = []
    add_check(checks, "auto_router_present", bool(auto_router), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_validated", as_dict(auto_router.get("validation")).get("status") == "ok", as_dict(auto_router.get("validation")).get("status"))
    add_check(checks, "ticker_found_in_auto_router", bool(route), ticker)
    add_check(checks, "ticker_card_present", bool(card), rel(card_path), severity="warning")
    add_check(checks, "capital_deployment_hard_false", AUTHORITY_BOUNDARY["capital_deployment_approved"] is False, None)
    add_check(checks, "trade_execution_hard_false", AUTHORITY_BOUNDARY["trade_or_execution_approved"] is False, None)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Quick Ticker Route",
        "ticker": ticker,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "auto_router": rel(AUTO_ROUTER),
            "wf85_decision_cards": rel(WF85_CARDS),
            "ticker_card": rel(card_path),
            "stale_tickers": rel(STALE_TICKERS),
            "ticker_card_summary": rel(TICKER_CARD_SUMMARY),
            "tier_a_final_packet_compatibility": rel(TIER_A_PACKET),
            "tier_a_final_packet_deprecated_for_authority": bool(tier_a),
            "tier_b_evidence_repair": rel(TIER_B_REPAIR),
        },
        "route": {
            "auto_tier": route.get("auto_tier"),
            "auto_state": route.get("auto_state"),
            "lane_tier": route.get("lane_tier"),
            "review_lane": route.get("review_lane"),
            "instrument_class": route.get("instrument_class"),
            "asset_class": route.get("asset_class"),
            "deployment_role": route.get("deployment_role"),
            "route_reason": route.get("route_reason"),
            "route_priority": route.get("route_priority"),
            "tier_seeded_from_legacy_label": bool(route.get("tier_seeded_from_legacy_label")),
            "legacy_monitoring_role": route.get("legacy_monitoring_role"),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        },
        "route_readiness": readiness,
        "ticker_context": {
            "name": route.get("name") or as_dict(card.get("universe_metadata")).get("name"),
            "sector": route.get("sector") or as_dict(card.get("universe_metadata")).get("sector"),
            "instrument_type": route.get("instrument_type") or card.get("instrument_type"),
            "recommendation_support": recommendation,
            "latest_known_price": card.get("latest_known_price"),
            "price_band_stop": band,
            "technical_posture": card.get("technical_posture"),
            "entry_stop_reference_metadata": card.get("entry_stop_reference_metadata"),
        },
        "evidence": {
            "summary_row": summary_context,
            "missing_or_stale": missing_or_stale,
            "blocking_evidence": blocking,
            "blockers": blockers,
            "tier_a_packet_context": tier_a_ctx,
            "tier_b_repair_context": tier_b_ctx,
        },
        "decision": {
            "capital_card_warranted": capital_card_warranted,
            "owner_review_packet_warranted": capital_card_warranted,
            "capital_card_warranted_reason": "A-READY with no blocking/stale evidence in current artifacts" if capital_card_warranted else "not warranted from current non-capital evidence context",
            "next_safe_action": readiness.get("next_route_action") or next_safe_action(route, card, stale_context, capital_card_warranted),
            "requires_owner_approval_for_capital_or_execution": True,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
        },
        "validation": {
            "status": "ok" if not errors else "error",
            "checks": checks,
            "errors": errors,
            "warnings": [check for check in checks if check["severity"] == "warning" and not check["ok"]],
        },
        "stop_lines": [
            "This is a quick route packet, not a recommendation or approval.",
            "Capital-card-warranted means prepare a non-executing review card only; it does not approve deployment.",
            "No paper/live order, brokerage/account action, portfolio/canon mutation, SQL-canon mutation, or owner approval is inferred.",
        ],
    }


def default_out(ticker: str) -> Path:
    return TMP / f"wf78-route-{ticker.lower()}.json"


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    ticker = ticker_key(args.ticker)
    out = resolve(args.out) if args.out else default_out(ticker)
    packet = build_packet(ticker)
    if args.write:
        atomic_write_json(out, packet)
    result = {
        "status": packet["status"],
        "ticker": ticker,
        "out": rel(out) if args.write else None,
        "route": packet["route"],
        "route_readiness": packet["route_readiness"],
        "decision": packet["decision"],
        "validation": {
            "status": as_dict(packet.get("validation")).get("status"),
            "errors": len(as_list(as_dict(packet.get("validation")).get("errors"))),
            "warnings": len(as_list(as_dict(packet.get("validation")).get("warnings"))),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
