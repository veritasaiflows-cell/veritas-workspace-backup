#!/usr/bin/env python3
"""Review-only WF78 promotion visibility top-10 queue.

This packet answers one narrow question: which WF78 candidates deserve the next
research/routing attention pass after the daily core runs? It merges production
candidate visibility, complete C->B evidence gates, Tier C attention triggers,
and repair debt into one ranked queue without creating capital, execution,
portfolio, canon, or customer-output authority.
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
OUT = TMP / "wf78-promotion-visibility-top10.json"
SCHEMA = "veritas.wf78_promotion_visibility_top10.v1"

SOURCES = {
    "auto_tier_routing": TMP / "wf78-auto-tier-routing.json",
    "tier_b_phase2_eval": TMP / "wf78-tier-b-research-packet-phase2-eval.json",
    "tier_c_attention": TMP / "wf78-tier-c-attention-trigger.json",
    "macro_overlay_gate": TMP / "wf78-macro-thesis-overlay-gate.json",
    "repair_priority_queue": TMP / "wf78-repair-priority-queue.json",
    "wf78_visibility_queue": TMP / "wf78-opportunity-visibility-queue.json",
    "wf85_visibility_queue": TMP / "wf85-opportunity-visibility-queue.json",
    "decision_factory": TMP / "finance-decision-factory.json",
    "market_loop": TMP / "finance-market-deployment-operating-loop.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "promotion_visibility_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_state_only": True,
    "cron_schedule_mutation_allowed": False,
    "registry_apply_allowed": False,
    "owner_lineage_apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

ROW_FALSE_FIELDS = {
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False} | set(ROW_FALSE_FIELDS)

SOURCE_PRIORITY = {
    "owner_review_ready": 1000,
    "market_refresh_pending": 920,
    "gate_deferred": 820,
    "repair_or_wait": 740,
    "c_to_b_evidence_complete": 680,
    "tier_c_attention": 620,
    "decision_factory_candidate": 560,
    "evidence_repair": 430,
    "monitor": 100,
}

PRODUCTION_VISIBLE_LANES = {
    "owner_review_ready",
    "market_refresh_pending",
    "gate_deferred",
    "repair_or_wait",
    "decision_factory_candidate",
}
C_TO_B_ACTIONABLE_LANES = {"c_to_b_evidence_complete"}
TIER_C_ATTENTION_LANES = {"tier_c_attention"}
EVIDENCE_REPAIR_LANES = {"evidence_repair"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FALSE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{index}]"))
    return paths


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_drift_paths": authority_true_paths(payload),
    }


def index_by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        row = as_dict(row)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            indexed[ticker] = row
    return indexed


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def clean_blockers(*values: Any) -> list[str]:
    blockers: list[str] = []
    for value in values:
        for item in as_list(value):
            text = str(item).strip()
            if text and text not in blockers:
                blockers.append(text)
    return blockers


def lane_from_visibility_state(state: str) -> str:
    if state in SOURCE_PRIORITY:
        return state
    if state in {"wf85_owner_review_ready", "wf78_owner_review_ready"}:
        return "owner_review_ready"
    if state:
        return state
    return "monitor"


def tier_from_auto_row(row: dict[str, Any]) -> str | None:
    return first_present(row.get("auto_tier"), row.get("legacy_tier"))


def base_reason(source_lane: str, state: str | None = None) -> str:
    reasons = {
        "owner_review_ready": "Complete evidence is visible for owner review only.",
        "market_refresh_pending": "Production-grade candidate is blocked by market/freshness timing, not by promotion routing.",
        "gate_deferred": "Candidate is blocked by explicit decision/freshness gate blockers.",
        "repair_or_wait": "Candidate needs repair or timing/freshness clearance before owner-review visibility.",
        "c_to_b_evidence_complete": "Tier C -> Tier B evidence gate is complete and eligible for research-candidate nomination.",
        "tier_c_attention": "Tier C attention trigger fired from price/fundamental pressure.",
        "decision_factory_candidate": "Decision factory candidate exists but is not owner-review ready.",
        "evidence_repair": "Evidence repair queue identifies missing proof before promotion/review movement.",
    }
    return reasons.get(source_lane) or f"Review-only routing signal from {state or source_lane}."


def row_score(row: dict[str, Any]) -> float:
    lane = str(row.get("source_lane") or "monitor")
    score = float(SOURCE_PRIORITY.get(lane, 100))
    for field, weight in (
        ("attention_score", 1.0),
        ("overlay_score", 0.7),
        ("route_priority", 6.0),
        ("batch_nomination_index", -1.0),
    ):
        value = row.get(field)
        if isinstance(value, (int, float)):
            score += float(value) * weight
    if row.get("auto_tier") == "Tier A":
        score += 35
    elif row.get("auto_tier") == "Tier B":
        score += 15
    score -= len(as_list(row.get("blockers"))) * 4
    return round(score, 2)


def add_actionability(row: dict[str, Any]) -> None:
    lane = str(row.get("source_lane") or "")
    blockers = clean_blockers(row.get("blockers"))
    complete_evidence = lane in {"c_to_b_evidence_complete", "owner_review_ready"}
    if lane == "owner_review_ready" and blockers:
        complete_evidence = False
    actionable_now = complete_evidence and not blockers
    actionability_blockers = list(blockers)
    if lane == "market_refresh_pending":
        actionable_now = False
        if "market_refresh_pending" not in actionability_blockers:
            actionability_blockers.append("market_refresh_pending")
    elif lane in {"tier_c_attention", "evidence_repair", "gate_deferred", "repair_or_wait", "decision_factory_candidate"}:
        actionable_now = False
        if not actionability_blockers:
            actionability_blockers.append(f"{lane}_requires_repair_or_gate_clearance")
    row["complete_evidence"] = bool(complete_evidence)
    row["actionable_now"] = bool(actionable_now)
    row["actionability_blockers"] = actionability_blockers


def lane_rollup(
    rows: list[dict[str, Any]],
    top_rows: list[dict[str, Any]],
    actionable_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    def count_where(items: list[dict[str, Any]], lanes: set[str], *, actionable_only: bool = False) -> int:
        total = 0
        for row in items:
            lane = str(row.get("source_lane") or "")
            if lane not in lanes:
                continue
            if actionable_only and row.get("actionable_now") is not True:
                continue
            total += 1
        return total

    def tickers_where(items: list[dict[str, Any]], lanes: set[str]) -> list[str]:
        return [str(row.get("ticker")) for row in items if str(row.get("source_lane") or "") in lanes and row.get("ticker")]

    lane_counts = Counter(str(row.get("source_lane") or "unknown") for row in rows)
    top_lane_counts = Counter(str(row.get("source_lane") or "unknown") for row in top_rows)
    actionable_lane_counts = Counter(str(row.get("source_lane") or "unknown") for row in actionable_rows)
    return {
        "production_visible": {
            "count": count_where(rows, PRODUCTION_VISIBLE_LANES),
            "top10_count": count_where(top_rows, PRODUCTION_VISIBLE_LANES),
            "actionable_count": count_where(rows, PRODUCTION_VISIBLE_LANES, actionable_only=True),
            "top10_tickers": tickers_where(top_rows, PRODUCTION_VISIBLE_LANES),
        },
        "c_to_b_actionable": {
            "count": count_where(rows, C_TO_B_ACTIONABLE_LANES),
            "top10_count": count_where(top_rows, C_TO_B_ACTIONABLE_LANES),
            "actionable_count": count_where(rows, C_TO_B_ACTIONABLE_LANES, actionable_only=True),
            "actionable_top10_count": len(actionable_rows),
            "actionable_top10_tickers": tickers_where(actionable_rows, C_TO_B_ACTIONABLE_LANES),
        },
        "tier_c_attention": {
            "count": count_where(rows, TIER_C_ATTENTION_LANES),
            "top10_count": count_where(top_rows, TIER_C_ATTENTION_LANES),
            "actionable_count": count_where(rows, TIER_C_ATTENTION_LANES, actionable_only=True),
            "top10_tickers": tickers_where(top_rows, TIER_C_ATTENTION_LANES),
        },
        "evidence_repair": {
            "count": count_where(rows, EVIDENCE_REPAIR_LANES),
            "top10_count": count_where(top_rows, EVIDENCE_REPAIR_LANES),
            "actionable_count": count_where(rows, EVIDENCE_REPAIR_LANES, actionable_only=True),
            "top10_tickers": tickers_where(top_rows, EVIDENCE_REPAIR_LANES),
        },
        "raw": {
            "source_lane_counts": dict(lane_counts),
            "top_source_lane_counts": dict(top_lane_counts),
            "actionable_top10_source_lane_counts": dict(actionable_lane_counts),
        },
    }


def merge_candidate(candidates: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    ticker = str(row.get("ticker") or "").upper()
    if not ticker:
        return
    row["ticker"] = ticker
    row.update(ROW_FALSE_FIELDS)
    add_actionability(row)
    row["score"] = row_score(row)
    existing = candidates.get(ticker)
    if not existing or row["score"] > existing.get("score", 0):
        candidates[ticker] = row


def visibility_rows(
    payload: dict[str, Any],
    *,
    source_label: str,
    auto_rows: dict[str, dict[str, Any]],
    decision_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in as_list(payload.get("rows")):
        row = as_dict(raw)
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        auto_row = auto_rows.get(ticker, {})
        decision_row = decision_rows.get(ticker, {})
        state = str(first_present(row.get("wf85_visibility_state"), row.get("visibility_state"), "monitor"))
        lane = lane_from_visibility_state(state)
        entry_band = as_dict(row.get("entry_band"))
        out.append({
            "ticker": ticker,
            "name": first_present(row.get("name"), decision_row.get("name"), auto_row.get("name")),
            "source_lane": lane,
            "source_detail": source_label,
            "visibility_state": state,
            "auto_tier": first_present(row.get("auto_tier"), auto_row.get("auto_tier")),
            "auto_state": first_present(row.get("auto_state"), auto_row.get("auto_state")),
            "route_priority": auto_row.get("route_priority"),
            "current_price": first_present(row.get("current_price"), decision_row.get("current_price")),
            "current_band_status": first_present(
                row.get("current_band_status"),
                entry_band.get("band_status"),
                decision_row.get("current_band_status"),
            ),
            "entry_band": row.get("entry_band"),
            "stop_or_invalidation": row.get("stop_or_invalidation"),
            "blockers": clean_blockers(row.get("blockers"), decision_row.get("root_cause_blockers")),
            "next_safe_action": "refresh_market_window_or_gate_blockers_before_owner_review",
            "reason": row.get("reason") or base_reason(lane, state),
            "source_artifacts": [source_label, "tmp/wf78-auto-tier-routing.json", "tmp/finance-decision-factory.json"],
        })
    return out


def phase2_rows(
    payload: dict[str, Any],
    *,
    auto_rows: dict[str, dict[str, Any]],
    macro_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in as_list(payload.get("c_to_b_decisions")):
        row = as_dict(raw)
        if row.get("status") != "eligible_for_admission":
            continue
        ticker = str(row.get("ticker") or "").upper()
        auto_row = auto_rows.get(ticker, {})
        macro_row = macro_rows.get(ticker, {})
        out.append({
            "ticker": ticker,
            "name": first_present(row.get("name"), auto_row.get("name"), macro_row.get("name")),
            "source_lane": "c_to_b_evidence_complete",
            "source_detail": "phase2_c_to_b_evidence_gate",
            "visibility_state": "eligible_for_tier_b_research_nomination",
            "auto_tier": first_present(auto_row.get("auto_tier"), "Tier C"),
            "auto_state": first_present(auto_row.get("auto_state"), row.get("current_state")),
            "route_priority": auto_row.get("route_priority"),
            "overlay_score": macro_row.get("overlay_score"),
            "batch_nomination_index": row.get("batch_nomination_index"),
            "blockers": clean_blockers(row.get("missing_evidence")),
            "next_safe_action": "build_or_refresh_tier_b_research_packet_before_any_apply_path",
            "reason": row.get("reason") or base_reason("c_to_b_evidence_complete"),
            "source_artifacts": [
                "tmp/wf78-tier-b-research-packet-phase2-eval.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/wf78-macro-thesis-overlay-gate.json",
            ],
        })
    return out


def tier_c_attention_rows(
    payload: dict[str, Any],
    *,
    auto_rows: dict[str, dict[str, Any]],
    macro_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in as_list(payload.get("rows")):
        row = as_dict(raw)
        if row.get("attention_triggered") is not True:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        auto_row = auto_rows.get(ticker, {})
        auto_tier = str(first_present(auto_row.get("auto_tier"), "Tier C"))
        if auto_tier != "Tier C":
            continue
        macro_row = macro_rows.get(ticker, {})
        price_metrics = as_dict(row.get("price_metrics"))
        out.append({
            "ticker": ticker,
            "name": first_present(row.get("name"), auto_row.get("name"), macro_row.get("name")),
            "source_lane": "tier_c_attention",
            "source_detail": "tier_c_attention_trigger",
            "visibility_state": row.get("attention_state"),
            "auto_tier": auto_tier,
            "auto_state": first_present(auto_row.get("auto_state"), row.get("current_auto_state")),
            "route_priority": auto_row.get("route_priority"),
            "attention_score": row.get("attention_score"),
            "overlay_score": macro_row.get("overlay_score"),
            "current_price": price_metrics.get("latest_close"),
            "blockers": clean_blockers(row.get("blockers")),
            "next_safe_action": row.get("recommended_next_action") or "repair_source_open_and_band_context",
            "reason": base_reason("tier_c_attention"),
            "source_artifacts": [
                "tmp/wf78-tier-c-attention-trigger.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/wf78-macro-thesis-overlay-gate.json",
            ],
        })
    return out


def decision_factory_rows(payload: dict[str, Any], *, auto_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in as_list(payload.get("decision_ledger")):
        row = as_dict(raw)
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        auto_row = auto_rows.get(ticker, {})
        disposition = str(row.get("disposition") or row.get("decision_state") or "monitor")
        lane = "owner_review_ready" if disposition == "owner_card_and_wf67_request_ready" else "decision_factory_candidate"
        out.append({
            "ticker": ticker,
            "name": first_present(row.get("name"), auto_row.get("name")),
            "source_lane": lane,
            "source_detail": "finance_decision_factory",
            "visibility_state": disposition,
            "auto_tier": first_present(row.get("auto_tier"), auto_row.get("auto_tier")),
            "auto_state": first_present(auto_row.get("auto_state"), row.get("queue_state")),
            "route_priority": auto_row.get("route_priority"),
            "current_price": row.get("current_price"),
            "current_band_status": row.get("current_band_status"),
            "entry_band": {"low": row.get("entry_band_low"), "high": row.get("entry_band_high")},
            "stop_or_invalidation": row.get("stop_or_invalidation"),
            "blockers": clean_blockers(row.get("root_cause_blockers"), row.get("plain_english_blockers")),
            "next_safe_action": "refresh_visibility_queue_or_repair_decision_blockers",
            "reason": base_reason(lane, disposition),
            "source_artifacts": ["tmp/finance-decision-factory.json", "tmp/wf78-auto-tier-routing.json"],
        })
    return out


def repair_rows(payload: dict[str, Any], *, auto_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in as_list(payload.get("rows"))[:40]:
        row = as_dict(raw)
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        auto_row = auto_rows.get(ticker, {})
        priority = row.get("priority")
        route_priority = 1
        if isinstance(priority, (int, float)):
            route_priority = int(priority)
        out.append({
            "ticker": ticker,
            "name": first_present(row.get("name"), auto_row.get("name")),
            "source_lane": "evidence_repair",
            "source_detail": "repair_priority_queue",
            "visibility_state": row.get("repair_class") or "evidence_repair",
            "auto_tier": first_present(row.get("auto_tier"), auto_row.get("auto_tier")),
            "auto_state": first_present(row.get("auto_state"), auto_row.get("auto_state")),
            "route_priority": route_priority,
            "blockers": clean_blockers(row.get("blockers"), row.get("missing_evidence")),
            "next_safe_action": row.get("next_action") or "repair_evidence_before_routing_escalation",
            "reason": base_reason("evidence_repair"),
            "source_artifacts": ["tmp/wf78-repair-priority-queue.json", "tmp/wf78-auto-tier-routing.json"],
        })
    return out


def build_payload(paths: dict[str, Path] | None = None, *, limit: int = 10) -> dict[str, Any]:
    source_paths = paths or SOURCES
    payloads = {name: load(path) for name, path in source_paths.items()}
    auto_rows = index_by_ticker(as_list(payloads["auto_tier_routing"].get("rows")))
    macro_rows = index_by_ticker(as_list(payloads["macro_overlay_gate"].get("rows")))
    decision_rows = index_by_ticker(as_list(payloads["decision_factory"].get("decision_ledger")))

    candidates: dict[str, dict[str, Any]] = {}
    generators = [
        visibility_rows(
            payloads["wf85_visibility_queue"],
            source_label="tmp/wf85-opportunity-visibility-queue.json",
            auto_rows=auto_rows,
            decision_rows=decision_rows,
        ),
        visibility_rows(
            payloads["wf78_visibility_queue"],
            source_label="tmp/wf78-opportunity-visibility-queue.json",
            auto_rows=auto_rows,
            decision_rows=decision_rows,
        ),
        phase2_rows(payloads["tier_b_phase2_eval"], auto_rows=auto_rows, macro_rows=macro_rows),
        tier_c_attention_rows(payloads["tier_c_attention"], auto_rows=auto_rows, macro_rows=macro_rows),
        decision_factory_rows(payloads["decision_factory"], auto_rows=auto_rows),
        repair_rows(payloads["repair_priority_queue"], auto_rows=auto_rows),
    ]
    for rows in generators:
        for row in rows:
            merge_candidate(candidates, row)

    rows = sorted(candidates.values(), key=lambda row: (-float(row.get("score") or 0), str(row.get("ticker") or "")))
    top_rows = rows[: max(1, limit)]
    for rank, row in enumerate(top_rows, start=1):
        row["rank"] = rank
    actionable_rows = [
        row.copy()
        for row in rows
        if row.get("complete_evidence") is True and row.get("actionable_now") is True
    ][: max(1, limit)]
    for rank, row in enumerate(actionable_rows, start=1):
        row["actionable_rank"] = rank

    lane_counts = Counter(str(row.get("source_lane") or "unknown") for row in rows)
    top_lane_counts = Counter(str(row.get("source_lane") or "unknown") for row in top_rows)
    actionable_lane_counts = Counter(str(row.get("source_lane") or "unknown") for row in actionable_rows)
    lanes = lane_rollup(rows, top_rows, actionable_rows)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Review-only ranked queue for WF78 promotion visibility, Tier C attention, and evidence repair routing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {"limit": limit},
        "summary": {
            "candidate_count": len(rows),
            "top_count": len(top_rows),
            "actionable_top10_count": len(actionable_rows),
            "complete_evidence_count": sum(1 for row in rows if row.get("complete_evidence") is True),
            "actionable_now_count": sum(1 for row in rows if row.get("actionable_now") is True),
            "source_lane_counts": dict(lane_counts),
            "top_source_lane_counts": dict(top_lane_counts),
            "actionable_top10_source_lane_counts": dict(actionable_lane_counts),
            "owner_review_ready_count": lane_counts.get("owner_review_ready", 0),
            "market_refresh_pending_count": lane_counts.get("market_refresh_pending", 0),
            "c_to_b_evidence_complete_count": lane_counts.get("c_to_b_evidence_complete", 0),
            "tier_c_attention_count": lane_counts.get("tier_c_attention", 0),
            "evidence_repair_count": lane_counts.get("evidence_repair", 0),
            "production_visible_count": lanes["production_visible"]["count"],
            "production_visible_top10_count": lanes["production_visible"]["top10_count"],
            "c_to_b_actionable_count": lanes["c_to_b_actionable"]["actionable_count"],
            "c_to_b_actionable_top10_count": lanes["c_to_b_actionable"]["actionable_top10_count"],
            "tier_c_attention_top10_count": lanes["tier_c_attention"]["top10_count"],
            "evidence_repair_top10_count": lanes["evidence_repair"]["top10_count"],
            "canonical_owner_review_ready_count_source": "wf85_wf78_visibility_queue_owner_review_ready_lane",
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "paper_or_live_execution_allowed_count": 0,
            "next_safe_action": (
                "Use rank order for non-capital refresh/repair routing; do not treat any row as approval, "
                "execution authority, or portfolio/canon mutation authority."
            ),
        },
        "lanes": lanes,
        "operator_display_contract": {
            "canonical_top_of_funnel": "owner_review_ready_count",
            "do_not_label_ticker_top_actionable_when_owner_review_ready_count_zero": True,
            "separate_visibility_from_actionability": True,
        },
        "rows": top_rows,
        "actionable_top10_rows": actionable_rows,
        "all_candidate_count": len(rows),
        "source_records": [
            source_record(name, path, payloads.get(name, {}))
            for name, path in source_paths.items()
        ],
        "source_artifacts": {name: rel(path) for name, path in source_paths.items()},
        "stop_lines": [
            "Top-10 visibility is not Tier B/Tier A apply authority.",
            "Top-10 visibility is not capital deployment approval.",
            "No paper/live execution, brokerage/account action, money movement, customer output, or canon/portfolio mutation is permitted.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "ok" if payload["validation"]["status"] in {"ok", "warning"} else "blocked"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append(f"authority_drift:{','.join(drift[:8])}")
    for record in as_list(payload.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("authority_drift_paths"):
            errors.append(f"source_authority_drift:{record.get('name')}")
        if record.get("validation_status") == "error":
            warnings.append(f"source_validation_error:{record.get('name')}")
    for row in as_list(payload.get("rows")):
        ticker = row.get("ticker")
        for key, expected in ROW_FALSE_FIELDS.items():
            if row.get(key) is not expected:
                errors.append(f"row_{ticker}_{key}_not_false")
        if not row.get("source_lane"):
            errors.append(f"row_{ticker}_missing_source_lane")
        if not row.get("next_safe_action"):
            errors.append(f"row_{ticker}_missing_next_safe_action")
    summary = as_dict(payload.get("summary"))
    lanes = as_dict(payload.get("lanes"))
    for lane_key in ("production_visible", "c_to_b_actionable", "tier_c_attention", "evidence_repair"):
        if not isinstance(lanes.get(lane_key), dict):
            errors.append(f"missing_lane:{lane_key}")
    for key in (
        "capital_deployment_approved_count",
        "trade_or_execution_approved_count",
        "paper_or_live_execution_allowed_count",
    ):
        if summary.get(key) != 0:
            errors.append(f"summary_{key}_nonzero")
    c_to_b_lane = as_dict(lanes.get("c_to_b_actionable"))
    if summary.get("c_to_b_actionable_count") != c_to_b_lane.get("actionable_count"):
        errors.append("summary_c_to_b_actionable_count_mismatch")
    if summary.get("production_visible_count") != as_dict(lanes.get("production_visible")).get("count"):
        errors.append("summary_production_visible_count_mismatch")
    if int(summary.get("top_count") or 0) == 0:
        warnings.append("no_top10_rows")
    if int(summary.get("actionable_now_count") or 0) != len(as_list(payload.get("actionable_top10_rows"))):
        if int(summary.get("actionable_now_count") or 0) < len(as_list(payload.get("actionable_top10_rows"))):
            errors.append("actionable_top10_exceeds_actionable_now_count")
    for row in as_list(payload.get("actionable_top10_rows")):
        ticker = row.get("ticker")
        if row.get("complete_evidence") is not True:
            errors.append(f"actionable_row_{ticker}_missing_complete_evidence")
        if row.get("actionable_now") is not True:
            errors.append(f"actionable_row_{ticker}_not_actionable_now")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(limit=args.limit)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "validation": payload.get("validation"),
            "summary": payload.get("summary"),
            "out": rel(out) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
