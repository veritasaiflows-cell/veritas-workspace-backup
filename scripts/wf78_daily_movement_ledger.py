#!/usr/bin/env python3
"""WF78 daily ticker movement ledger and repair-priority queue.

This is a review-only synthesis layer. It reads existing WF78/WF84/WF85 proof
surfaces and creates one operator ledger for promote/hold/repair/no-chase/
invalidation decisions. It does not mutate universe, ticker cards, portfolio
canon, broker state, or execution state.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-daily-movement-ledger.json"
OUT_MD = TMP / "wf78-daily-movement-ledger.md"
REPAIR_OUT = TMP / "wf78-repair-priority-queue.json"
SCHEMA = "veritas.wf78_daily_movement_ledger.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_ledger_only": True,
    "repair_queue_only": True,
    "universe_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
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


def by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker", "")).upper()
        if ticker:
            result[ticker] = row
    return result


def collect_delta_tickers(delta: dict[str, Any]) -> dict[str, str]:
    actions: dict[str, str] = {}
    for action, key in (
        ("promote", "promotions"),
        ("demote", "demotions"),
        ("state_change", "state_changes"),
        ("added", "added"),
        ("removed", "removed"),
    ):
        for row in as_list(delta.get(key)):
            if isinstance(row, dict) and row.get("ticker"):
                actions[str(row["ticker"]).upper()] = action
    return actions


def repair_class(blockers: list[str], failed_families: list[str], warnings: list[str], stale_families: list[str]) -> str:
    combined = " ".join([*blockers, *failed_families, *warnings, *stale_families]).lower()
    if "owner" in combined or "lineage" in combined:
        return "owner_lineage_or_structural_gap"
    if "analyst" in combined or "revision" in combined:
        return "analyst_revision_gap"
    if "source" in combined or "official" in combined:
        return "source_open_gap"
    if "free_cash_flow" in combined or "fcf" in combined or "valuation" in combined:
        return "fcf_or_valuation_anomaly"
    if "below_stop" in combined or "technical" in combined or "price_band" in combined or "band" in combined:
        return "technical_or_band_gap"
    if "leverage" in combined:
        return "leverage_or_balance_sheet_risk"
    return "general_evidence_repair"


def repair_priority(auto_tier: str, decision: str, repair_kind: str) -> int:
    priority = 90
    if auto_tier == "Tier A":
        priority = 10
    elif auto_tier == "Tier B":
        priority = 30
    elif auto_tier == "Tier C":
        priority = 60
    if decision == "invalidation_review":
        priority -= 5
    if repair_kind == "source_open_gap":
        priority += 2
    elif repair_kind == "analyst_revision_gap":
        priority += 4
    elif repair_kind == "technical_or_band_gap":
        priority += 6
    elif repair_kind == "owner_lineage_or_structural_gap":
        priority += 12
    return max(priority, 1)


def decision_for(
    ticker: str,
    route: dict[str, Any],
    freshness: dict[str, Any],
    deployment: dict[str, Any],
    attention: dict[str, Any],
    pipeline: dict[str, Any],
    delta_action: str | None,
) -> tuple[str, str, str]:
    if delta_action == "promote":
        return "promote", "routing_delta_promoted", "promotion_review"
    if delta_action == "demote":
        return "demote", "routing_delta_demoted", "risk_review"
    if delta_action == "state_change":
        return "state_change", "routing_delta_state_change", "review"
    if deployment:
        action = str(deployment.get("autonomous_routing_action") or "")
        timing = str(deployment.get("final_timing_state") or "")
        if action == "invalidation_review" or "invalidation" in timing:
            return "invalidation_review", "deployment_queue_invalidation_review", "risk_review"
        if action == "no_chase_monitor" or "no_chase" in timing:
            return "no_chase", "deployment_queue_no_chase", "monitor"
        if action == "repair_first" or "repair" in timing:
            return "repair", "deployment_queue_repair_first", "repair"
    if pipeline:
        status = str(pipeline.get("status") or "")
        if status.startswith("blocked"):
            return "repair", "tier_c_to_b_blocked_pending_repair", "repair"
    route_state = str(route.get("auto_state") or freshness.get("route_state") or "")
    resolution_state = str(freshness.get("resolution_state") or "")
    if "REPAIR" in route_state or "blocked" in resolution_state:
        return "repair", "freshness_or_route_repair_required", "repair"
    if attention:
        return "newly_hot", "tier_c_attention_triggered", "attention_review"
    if freshness and not bool(freshness.get("tier_weighted_resolved", True)):
        return "repair", "tier_weighted_freshness_unresolved", "repair"
    return "hold", "no_material_movement", "monitor"


def build_ledger() -> dict[str, Any]:
    auto_router = load_dict(TMP / "wf78-auto-tier-routing.json")
    routing_delta = load_dict(TMP / "wf78-routing-delta.json")
    freshness_resolution = load_dict(TMP / "wf78-tier-weighted-freshness-resolution.json")
    attention_trigger = load_dict(TMP / "wf78-tier-c-attention-trigger.json")
    promotion_pipeline = load_dict(TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.json")
    deployment_cards = load_dict(TMP / "autonomous-routing-deployment-cards.json")
    decision_cards = load_dict(TMP / "trade-grade-decision-cards.json")
    wf84 = load_dict(TMP / "canonical-finance-data-plane.json")

    routes = by_ticker(as_list(auto_router.get("rows")))
    freshness = by_ticker(as_list(freshness_resolution.get("rows")))
    attention = by_ticker(as_list(attention_trigger.get("attention_rows")))
    pipeline = by_ticker(as_list(promotion_pipeline.get("rows")))
    deployment = by_ticker(as_list(deployment_cards.get("queue")))
    cards = by_ticker(as_list(decision_cards.get("cards")))
    delta_actions = collect_delta_tickers(routing_delta)

    records: list[dict[str, Any]] = []
    repair_rows: list[dict[str, Any]] = []
    decision_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for ticker in sorted(routes):
        route = routes[ticker]
        fresh = freshness.get(ticker, {})
        dep = deployment.get(ticker, {})
        attn = attention.get(ticker, {})
        pipe = pipeline.get(ticker, {})
        card = cards.get(ticker, {})
        decision, reason_code, next_action = decision_for(
            ticker,
            route,
            fresh,
            dep,
            attn,
            pipe,
            delta_actions.get(ticker),
        )
        blockers = [str(x) for x in as_list(dep.get("blockers")) + as_list(pipe.get("blockers_before_repair"))]
        failed_families = [str(x) for x in as_list(pipe.get("failed_evidence_families"))]
        warnings = [str(x) for x in as_list(dep.get("warnings")) + as_list(pipe.get("warnings"))]
        stale_families = [str(x) for x in as_list(fresh.get("stale_families"))]
        repair_kind = repair_class(blockers, failed_families, warnings, stale_families)
        auto_tier = str(route.get("auto_tier") or fresh.get("auto_tier") or "")
        auto_state = str(route.get("auto_state") or fresh.get("route_state") or "")
        record = {
            "ticker": ticker,
            "name": route.get("name") or card.get("name") or dep.get("name"),
            "sector": route.get("sector"),
            "auto_tier": auto_tier,
            "auto_state": auto_state,
            "decision": decision,
            "reason_code": reason_code,
            "next_action": next_action,
            "route_reason": route.get("route_reason"),
            "required_depth": fresh.get("required_depth"),
            "resolution_state": fresh.get("resolution_state"),
            "resolution_rationale": fresh.get("resolution_rationale"),
            "card_generated_at_utc": fresh.get("card_generated_at_utc"),
            "card_missing_or_stale_count": fresh.get("card_missing_or_stale_count"),
            "stale_families": stale_families,
            "attention_score": attn.get("attention_score") or route.get("tier_c_attention_score"),
            "attention_state": attn.get("attention_state"),
            "promotion_pipeline_status": pipe.get("status"),
            "failed_evidence_families": failed_families,
            "blockers": blockers,
            "warnings": warnings,
            "repair_class": repair_kind if decision in {"repair", "invalidation_review"} else None,
            "deployment_final_timing_state": dep.get("final_timing_state"),
            "deployment_action": dep.get("autonomous_routing_action"),
            "decision_state": dep.get("decision_state") or card.get("decision_state"),
            "current_price": dep.get("current_price") or card.get("current_price"),
            "band_status": as_dict(dep.get("entry_band")).get("band_status") or as_dict(card.get("entry_band")).get("band_status") or fresh.get("tier_c_monitor_band_status"),
            "source_artifacts": [
                "tmp/wf78-auto-tier-routing.json",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/trade-grade-decision-cards.json",
            ],
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        }
        records.append(record)
        decision_counts[decision] += 1
        tier_counts[auto_tier] += 1
        reason_counts[reason_code] += 1
        if decision in {"repair", "invalidation_review"}:
            repair_rows.append({
                "ticker": ticker,
                "name": record["name"],
                "auto_tier": auto_tier,
                "auto_state": auto_state,
                "decision": decision,
                "repair_class": repair_kind,
                "priority": repair_priority(auto_tier, decision, repair_kind),
                "reason_code": reason_code,
                "failed_evidence_families": failed_families,
                "blockers": blockers,
                "warnings": warnings,
                "stale_families": stale_families,
                "next_action": "repair_evidence_before_promotion_or_owner_review",
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
            })

    repair_rows.sort(key=lambda row: (int(row["priority"]), str(row["ticker"])))
    categories = {
        "moved_today": [r for r in records if r["decision"] in {"promote", "demote", "state_change"}],
        "blocked_today": [r for r in records if r["decision"] == "repair"],
        "newly_hot": [r for r in records if r["decision"] == "newly_hot"],
        "stale_but_important": [r for r in records if r["decision"] == "repair" and r["auto_tier"] in {"Tier A", "Tier B"}],
        "owner_review_candidates": [r for r in records if r["auto_tier"] in {"Tier A", "Tier B"} and r["decision"] not in {"repair", "invalidation_review", "no_chase"}],
        "no_chase_candidates": [r for r in records if r["decision"] == "no_chase"],
        "invalidation_candidates": [r for r in records if r["decision"] == "invalidation_review"],
    }

    repair_packet = {
        "schema": "veritas.wf78_repair_priority_queue.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "repair_count": len(repair_rows),
            "tier_counts": dict(Counter(row["auto_tier"] for row in repair_rows)),
            "repair_class_counts": dict(Counter(row["repair_class"] for row in repair_rows)),
            "top_repair_tickers": [row["ticker"] for row in repair_rows[:15]],
        },
        "rows": repair_rows,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }

    errors: list[str] = []
    if not records:
        errors.append("no ledger records generated")
    if any(AUTHORITY_BOUNDARY[key] for key in ("capital_deployment_allowed", "trade_or_execution_allowed", "paper_or_live_execution_allowed", "owner_approval_inferred")):
        errors.append("authority boundary widened unexpectedly")
    if auto_router.get("status") not in {None, "ok"}:
        errors.append("auto_router_not_ok")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "One daily review surface for WF78 ticker movement, blocked promotion repairs, no-chase, invalidation, and owner-review candidates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "auto_router": "tmp/wf78-auto-tier-routing.json",
            "routing_delta": "tmp/wf78-routing-delta.json",
            "tier_weighted_freshness_resolution": "tmp/wf78-tier-weighted-freshness-resolution.json",
            "tier_c_attention_trigger": "tmp/wf78-tier-c-attention-trigger.json",
            "tier_c_to_b_auto_promotion_pipeline": "tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json",
            "autonomous_routing_deployment_cards": "tmp/autonomous-routing-deployment-cards.json",
            "trade_grade_decision_cards": "tmp/trade-grade-decision-cards.json",
            "canonical_finance_data_plane": "tmp/canonical-finance-data-plane.json",
        },
        "source_freshness": {
            "auto_router_generated_at_utc": auto_router.get("generated_at_utc"),
            "wf84_generated_at_utc": wf84.get("generated_at_utc"),
            "wf85_cards_generated_at_utc": decision_cards.get("generated_at_utc"),
            "freshness_resolution_generated_at_utc": freshness_resolution.get("generated_at_utc"),
        },
        "summary": {
            "record_count": len(records),
            "tier_counts": dict(tier_counts),
            "decision_counts": dict(decision_counts),
            "reason_counts": dict(reason_counts),
            "repair_queue_count": len(repair_rows),
            "top_repair_tickers": [row["ticker"] for row in repair_rows[:15]],
            "moved_today_count": len(categories["moved_today"]),
            "blocked_today_count": len(categories["blocked_today"]),
            "newly_hot_count": len(categories["newly_hot"]),
            "stale_but_important_count": len(categories["stale_but_important"]),
            "owner_review_candidate_count": len(categories["owner_review_candidates"]),
            "no_chase_candidate_count": len(categories["no_chase_candidates"]),
            "invalidation_candidate_count": len(categories["invalidation_candidates"]),
            "next_safe_action": "Use the repair queue to unlock evidence-constrained promotions; keep capital/execution decisions owner-gated.",
        },
        "categories": {key: rows[:50] for key, rows in categories.items()},
        "records": records,
        "repair_priority_queue": repair_packet,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Ledger and repair queue are review-only derived artifacts.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF78 Daily Ticker Movement Ledger",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated UTC: {packet.get('generated_at_utc')}",
        f"- Records: {summary.get('record_count')}",
        f"- Repairs: {summary.get('repair_queue_count')}",
        f"- Newly hot: {summary.get('newly_hot_count')}",
        f"- No-chase: {summary.get('no_chase_candidate_count')}",
        f"- Invalidation: {summary.get('invalidation_candidate_count')}",
        "",
        "## Decision Counts",
    ]
    for key, value in sorted(as_dict(summary.get("decision_counts")).items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Repair Queue"])
    for row in as_list(as_dict(packet.get("repair_priority_queue")).get("rows"))[:20]:
        lines.append(f"- {row.get('ticker')}: {row.get('repair_class')} / {row.get('reason_code')} / priority {row.get('priority')}")
    lines.extend(["", "## Boundary", "- Review-only. No capital/execution/account/portfolio authority."])
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 daily movement ledger.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--repair-out", type=Path, default=REPAIR_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_ledger()
    repair_packet = as_dict(packet.get("repair_priority_queue"))
    if args.write:
        atomic_write_json(args.out, packet)
        atomic_write_json(args.repair_out, repair_packet)
        if args.write_md:
            atomic_write_text(OUT_MD, render_markdown(packet))
        print(
            f"wrote {rel(args.out)} status={packet['status']} "
            f"records={packet['summary']['record_count']} repairs={packet['summary']['repair_queue_count']}"
        )
    else:
        print(json.dumps(packet["summary"], indent=2))
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
