#!/usr/bin/env python3
"""Rank Tier C review candidates for the next WF78 repair pass.

This is a review-only scoreboard. It consumes existing WF78 routing,
attention, card, and fundamentals artifacts to decide where research repair
work is most likely to produce Tier B evidence value. It does not promote
tickers, mutate the universe, edit canonical notes, or authorize capital/trades.
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
CARD_DIR = TMP / "ticker-intelligence-cards"
ROUTER = TMP / "wf78-auto-tier-routing.json"
ATTENTION = TMP / "wf78-tier-c-attention-trigger.json"
HOLD_RECHECK = TMP / "wf78-tier-c-hold-recheck.json"
FUNDAMENTALS = TMP / "fundamental-metrics-current.json"
DEFAULT_OUT = TMP / "wf78-tier-c-opportunity-scoreboard.json"
SCHEMA = "veritas.wf78_tier_c_opportunity_scoreboard.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_scoreboard_only": True,
    "tier_b_promotion_allowed": False,
    "tier_a_promotion_allowed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKER_REPAIR_WEIGHTS = {
    "price_band_stop_missing": 12,
    "technical_posture_missing": 9,
    "official_growth_bridge_source_open_required": 8,
    "official_guidance_source_open_required": 8,
    "orders_backlog_manual_capture_required": 6,
    "fresh_price_quote": 5,
    "deployment_readiness_surface": 4,
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "routing", "candidates", "items"):
        raw = payload.get(key)
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
    return []


def ticker(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or "").upper().strip()


def by_ticker(row_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {ticker(row): row for row in row_list if ticker(row)}


def num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"none", "n/a", "missing", "unknown"}
    return True


def load_card(symbol: str) -> dict[str, Any]:
    return load(CARD_DIR / f"{symbol}.current.json")


def card_missing_families(card: dict[str, Any]) -> list[str]:
    families: list[str] = []
    for item in as_list(card.get("missing_or_stale_evidence")):
        if isinstance(item, dict):
            family = str(item.get("family") or "").strip()
            if family:
                families.append(family)
    return families


def blocker_names(attention_row: dict[str, Any], card: dict[str, Any]) -> list[str]:
    blockers = [str(item) for item in as_list(attention_row.get("blockers")) if str(item).strip()]
    blockers.extend(card_missing_families(card))
    return sorted(set(blockers))


def score_components(
    symbol: str,
    router_row: dict[str, Any],
    attention_row: dict[str, Any],
    hold_row: dict[str, Any],
    fundamental_row: dict[str, Any],
    card: dict[str, Any],
) -> dict[str, Any]:
    valuation = as_dict(card.get("valuation")) or fundamental_row
    official_fundamentals = as_dict(card.get("official_fundamentals")) or fundamental_row
    price_band = as_dict(card.get("price_band_stop"))
    recommendation = as_dict(card.get("recommendation_support"))
    price_metrics = as_dict(attention_row.get("price_metrics"))
    blockers = blocker_names(attention_row, card)

    attention_score = num(attention_row.get("attention_score"))
    momentum_score = num(attention_row.get("momentum_score"))
    fundamental_score = num(attention_row.get("fundamental_score"))
    score = (0.45 * attention_score) + (0.25 * fundamental_score) + (0.15 * momentum_score)

    router_state = str(router_row.get("auto_state") or "").upper()
    attention_state = str(attention_row.get("attention_state") or "").upper()
    band_status = str(price_band.get("band_status") or recommendation.get("band_status") or "").lower()
    valuation_context = str(valuation.get("valuation_context") or "").lower()
    forward_pe = num(valuation.get("forward_pe"), None) if present(valuation.get("forward_pe")) else None
    fcf = num(official_fundamentals.get("free_cash_flow"), None) if present(official_fundamentals.get("free_cash_flow")) else None
    fcf_yield = num(valuation.get("fcf_yield_pct"), None) if present(valuation.get("fcf_yield_pct")) else None
    fresh_price = present(price_metrics.get("latest_close")) or present(price_band.get("post_close_final_quote"))

    score += 12 if attention_state == "C-CANDIDATE" else 0
    score += 8 if attention_state == "C-CANDIDATE-REPAIR" else 0
    score += 8 if router_state == "C-CANDIDATE-HOLD" else 0
    score += 6 if router_state == "C-CANDIDATE-REPAIR" else 0
    score += 8 if hold_row else 0
    score += 5 if fresh_price else 0
    score += 4 if valuation_context == "available" else 0
    score += 3 if fcf is not None and fcf > 0 else 0
    score += 2 if fcf_yield is not None and fcf_yield > 0 else 0
    score += 2 if forward_pe is not None and 0 < forward_pe <= 25 else 0

    score -= min(18, len(blockers) * 2)
    if "price_band_stop_missing" in blockers:
        score -= 6
    if "technical_posture_missing" in blockers:
        score -= 4
    if not card:
        score -= 10
    if fcf is not None and fcf < 0:
        score -= 8
    if "no_chase" in band_status or "above" in band_status:
        score -= 3

    repair_weight = sum(BLOCKER_REPAIR_WEIGHTS.get(blocker, 3) for blocker in blockers)
    score = max(0.0, min(100.0, round(score, 2)))
    return {
        "ticker": symbol,
        "opportunity_score": score,
        "attention_score": attention_score,
        "momentum_score": momentum_score,
        "fundamental_score": fundamental_score,
        "repair_weight": repair_weight,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "router_state": router_row.get("auto_state"),
        "router_tier": router_row.get("auto_tier"),
        "attention_state": attention_row.get("attention_state"),
        "attention_triggered": attention_row.get("attention_triggered") is True,
        "held_phase2_candidate": bool(hold_row),
        "fresh_price_available": bool(fresh_price),
        "latest_close": price_metrics.get("latest_close") or price_band.get("latest_known_price"),
        "price_date": price_metrics.get("price_date"),
        "five_day_pct": price_metrics.get("five_day_pct"),
        "ten_day_pct": price_metrics.get("ten_day_pct"),
        "twenty_day_pct": price_metrics.get("twenty_day_pct"),
        "band_status": price_band.get("band_status") or recommendation.get("band_status"),
        "valuation_context": valuation.get("valuation_context"),
        "forward_pe": valuation.get("forward_pe"),
        "fcf_yield_pct": valuation.get("fcf_yield_pct"),
        "free_cash_flow": official_fundamentals.get("free_cash_flow"),
        "revenue_yoy_pct": official_fundamentals.get("revenue_yoy_pct"),
        "eps_yoy_pct": official_fundamentals.get("eps_yoy_pct"),
    }


def bucket_for(row: dict[str, Any]) -> str:
    state = str(row.get("attention_state") or "").upper()
    router_state = str(row.get("router_state") or "").upper()
    score = num(row.get("opportunity_score"))
    blocker_count = int(row.get("blocker_count") or 0)
    if score >= 58 or state == "C-CANDIDATE":
        return "promote_watch"
    if score >= 38 or state == "C-CANDIDATE-REPAIR" or router_state in {"C-CANDIDATE-HOLD", "C-CANDIDATE-REPAIR"}:
        return "repair_first"
    if score >= 25 and blocker_count <= 5:
        return "monitor"
    return "deprioritize"


def next_action(row: dict[str, Any]) -> str:
    bucket = row["bucket"]
    blockers = set(row.get("blockers") or [])
    if bucket == "promote_watch":
        return "run_tier_b_evidence_repair_packet_next_if_source_and_band_repairs_clear"
    if bucket == "deprioritize":
        return "deprioritize_near_term_repair_capacity"
    if bucket == "monitor":
        return "keep_in_c_monitor_until_price_or_fundamental_trigger_improves"
    if "price_band_stop_missing" in blockers or "technical_posture_missing" in blockers:
        return "repair_price_band_and_technical_posture_before_promotion_review"
    if any("official" in blocker or "orders_backlog" in blocker for blocker in blockers):
        return "source_open_official_growth_guidance_or_backlog_evidence"
    if bucket == "repair_first":
        return "complete_minimum_research_repair_then_recheck_attention"
    return "keep_in_c_monitor_until_price_or_fundamental_trigger_improves"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    router = load(ROUTER)
    attention = load(ATTENTION)
    hold = load(HOLD_RECHECK)
    fundamentals = load(FUNDAMENTALS)

    router_rows = by_ticker(rows(router))
    attention_rows = by_ticker(rows(attention))
    hold_rows = by_ticker([row for row in as_list(hold.get("target_rows")) if isinstance(row, dict)])
    fundamental_rows = by_ticker([row for row in as_list(fundamentals.get("rows")) if isinstance(row, dict)])

    selected = [
        symbol for symbol, row in router_rows.items()
        if str(row.get("auto_tier") or "").upper() == "TIER C"
    ]
    if args.ticker:
        explicit = {item.upper().strip() for raw in args.ticker for item in raw.split(",") if item.strip()}
        selected = [symbol for symbol in selected if symbol in explicit]

    scored: list[dict[str, Any]] = []
    for symbol in sorted(selected):
        card = load_card(symbol)
        computed = score_components(
            symbol,
            router_rows.get(symbol, {}),
            attention_rows.get(symbol, {}),
            hold_rows.get(symbol, {}),
            fundamental_rows.get(symbol, {}),
            card,
        )
        computed["bucket"] = bucket_for(computed)
        computed["recommended_next_action"] = next_action(computed)
        computed["source_artifacts"] = [
            rel(ROUTER),
            rel(ATTENTION),
            rel(HOLD_RECHECK),
            rel(FUNDAMENTALS),
            rel(CARD_DIR / f"{symbol}.current.json"),
        ]
        computed["capital_deployment_approved"] = False
        computed["trade_or_execution_approved"] = False
        scored.append(computed)

    scored.sort(key=lambda row: (-num(row.get("opportunity_score")), -num(row.get("repair_weight")), row["ticker"]))
    for index, row in enumerate(scored, start=1):
        row["rank"] = index

    bucket_counts = Counter(row["bucket"] for row in scored)
    state_counts = Counter(str(row.get("router_state") or "unknown") for row in scored)
    rows_by_bucket = {
        bucket: [row for row in scored if row["bucket"] == bucket]
        for bucket in ("promote_watch", "repair_first", "monitor", "deprioritize")
    }
    top_n = args.top
    validation_errors: list[str] = []
    if not router_rows:
        validation_errors.append("missing_router_rows")
    if not attention_rows:
        validation_errors.append("missing_attention_rows")
    if not selected:
        validation_errors.append("no_tier_c_rows_selected")
    if any(AUTHORITY_BOUNDARY[key] for key in (
        "tier_b_promotion_allowed",
        "tier_a_promotion_allowed",
        "capital_deployment_allowed",
        "capital_deployment_approved",
        "trade_or_execution_allowed",
        "trade_or_execution_approved",
        "owner_approval_inferred",
    )):
        validation_errors.append("authority_boundary_widened")

    next_batch = rows_by_bucket["promote_watch"][: args.batch_size]
    if len(next_batch) < args.batch_size:
        needed = args.batch_size - len(next_batch)
        next_batch.extend(rows_by_bucket["repair_first"][:needed])

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_errors else "ok",
        "purpose": "Review-only Tier C opportunity and repair ranking for WF78 non-capital research routing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "ticker_filter": args.ticker or [],
            "top": top_n,
            "batch_size": args.batch_size,
        },
        "source_artifacts": {
            "router": rel(ROUTER),
            "attention": rel(ATTENTION),
            "hold_recheck": rel(HOLD_RECHECK),
            "fundamentals": rel(FUNDAMENTALS),
            "cards_dir": rel(CARD_DIR),
        },
        "summary": {
            "tier_c_ranked_count": len(scored),
            "bucket_counts": dict(bucket_counts),
            "router_state_counts": dict(state_counts),
            "top_promote_watch": [row["ticker"] for row in rows_by_bucket["promote_watch"][:top_n]],
            "top_repair_first": [row["ticker"] for row in rows_by_bucket["repair_first"][:top_n]],
            "top_monitor": [row["ticker"] for row in rows_by_bucket["monitor"][:top_n]],
            "top_deprioritize": [row["ticker"] for row in rows_by_bucket["deprioritize"][:top_n]],
            "recommended_next_batch": [row["ticker"] for row in next_batch],
            "next_safe_action": "Run Tier B evidence/repair packet only on recommended_next_batch; keep remaining Tier C names in monitor/repair queues until evidence value is proven.",
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
        },
        "rows": scored,
        "buckets": {
            bucket: rows_by_bucket[bucket][:top_n]
            for bucket in ("promote_watch", "repair_first", "monitor", "deprioritize")
        },
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": [],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-only Tier C opportunity scoreboard.")
    parser.add_argument("--ticker", action="append", help="Optional ticker filter; repeatable or comma-delimited.")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=7)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, report)
        print(
            f"wrote {rel(out)} status={report['status']} "
            f"ranked={report['summary']['tier_c_ranked_count']} "
            f"next_batch={','.join(report['summary']['recommended_next_batch'])}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
