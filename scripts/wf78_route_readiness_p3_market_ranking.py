#!/usr/bin/env python3
"""Build the WF78 route-readiness P3 market/ranking proof packet.

This packet consumes the finance cache front door and existing market-session
policy to rank the current route-readiness queue without refreshing prices or
creating approval/execution authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finance_market_deployment_operating_loop import market_session
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
FRONTDOOR = TMP / "finance-cache-frontdoor.json"
MARKET_HOURS_READINESS = TMP / "wf85-market-hours-refresh-readiness.json"
DEFAULT_OUT = TMP / "wf78-route-readiness-p3-market-ranking.json"
SCHEMA = "veritas.wf78_route_readiness_p3_market_ranking.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "ranking_packet_only": True,
    "derived_state_only": True,
    "refreshes_market_data": False,
    "creates_owner_cards": False,
    "creates_approval_cards": False,
    "creates_order_cards": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}
REVIEW_ONLY_QUOTE_STATUSES = {
    "post_close_final_quote_available_for_non_executing_review",
    "review_only_price_context",
}
MONITOR_GRADE_QUOTE_STATUSES = {"tier_c_monitor_grade_reference"}

CATEGORY_ORDER = {
    "approval_card_candidate_owner_gated": 0,
    "in_band_review_monitor": 10,
    "reclaim_watch": 20,
    "evidence_or_freshness_repair": 30,
    "monitor_grade_triage": 40,
    "no_chase": 50,
    "avoid_until_reclaim_or_invalidation_repair": 60,
    "blocked_authority_conflict": 90,
    "monitor_only": 100,
}

TIER_ORDER = {
    "Tier A": 0,
    "Tier B": 10,
    "Tier C": 30,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0)
    except ValueError as exc:
        raise ValueError(f"invalid --now-utc timestamp: {value}") from exc


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def age_hours(value: Any, now: datetime) -> float | None:
    parsed = parse_generated_at(value)
    if parsed is None:
        return None
    return round((now - parsed).total_seconds() / 3600.0, 3)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def int_or_large(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 9999


def category_for(row: dict[str, Any]) -> str:
    timing = str(row.get("timing_state") or "")
    trade = str(row.get("trade_readiness_state") or "")
    authority = str(row.get("authority_state") or "")
    if authority != "review_only_no_capital_or_execution_authority":
        return "blocked_authority_conflict"
    if trade == "approval_card_candidate_owner_gated":
        return "approval_card_candidate_owner_gated"
    if timing in {"in_band_fresh_review", "in_band_review_only_quote"}:
        return "in_band_review_monitor"
    if timing in {"below_band_reclaim_watch", "below_band_monitor_grade_reclaim_watch"}:
        return "reclaim_watch"
    if timing in {"above_band_no_chase", "above_band_monitor_grade_no_chase"}:
        return "no_chase"
    if timing == "below_stop_or_invalidation":
        return "avoid_until_reclaim_or_invalidation_repair"
    if trade == "not_trade_ready_evidence_or_freshness_repair":
        return "evidence_or_freshness_repair"
    if trade == "not_trade_ready_monitor_grade" or "monitor_grade" in timing:
        return "monitor_grade_triage"
    return "monitor_only"


def row_needs_market_window_refresh(row: dict[str, Any], session: dict[str, Any]) -> bool:
    quote_status = str(row.get("quote_freshness_status") or row.get("route_quote_freshness_status") or "")
    if session.get("deployment_fresh_price_allowed") is not True:
        return True
    if quote_status in REVIEW_ONLY_QUOTE_STATUSES or quote_status in MONITOR_GRADE_QUOTE_STATUSES:
        return True
    return quote_status != "fresh"


def ranked_row(row: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    category = category_for(row)
    route_readiness = as_dict(row.get("route_readiness"))
    market_refresh_required = row_needs_market_window_refresh(row, session)
    return {
        "ticker": row.get("ticker"),
        "name": row.get("name"),
        "sector": row.get("sector"),
        "routing_tier": row.get("routing_tier") or row.get("auto_tier"),
        "routing_state": row.get("routing_state") or row.get("auto_state"),
        "route_priority": row.get("route_priority"),
        "latest_price": row.get("latest_price"),
        "entry_band_low": row.get("entry_band_low"),
        "entry_band_high": row.get("entry_band_high"),
        "stop_or_invalidation": row.get("stop_or_invalidation"),
        "band_status": row.get("band_status"),
        "quote_freshness_status": row.get("quote_freshness_status") or row.get("route_quote_freshness_status"),
        "timing_state": row.get("timing_state"),
        "decision_state": row.get("decision_state"),
        "trade_readiness_state": row.get("trade_readiness_state"),
        "authority_state": row.get("authority_state"),
        "category": category,
        "market_window_refresh_required": market_refresh_required,
        "market_window_state": session.get("window"),
        "review_only": True,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
        "next_route_action": route_readiness.get("next_route_action") or row.get("recommended_next_action"),
    }


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        CATEGORY_ORDER.get(str(row.get("category")), 999),
        TIER_ORDER.get(str(row.get("routing_tier")), 999),
        int_or_large(row.get("route_priority")),
        str(row.get("ticker") or ""),
    )


def counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def ticker_list(rows: list[dict[str, Any]], category: str, limit: int = 20) -> list[str]:
    return [str(row.get("ticker")) for row in rows if row.get("category") == category][:limit]


def build_payload(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    frontdoor = load_dict(FRONTDOOR)
    market_readiness = load_dict(MARKET_HOURS_READINESS)
    session = market_session(now)
    source_rows = [row for row in as_list(frontdoor.get("rows")) if isinstance(row, dict)]
    ranked_rows = sorted((ranked_row(row, session) for row in source_rows), key=sort_key)
    authority_conflicts = [row.get("ticker") for row in ranked_rows if row.get("authority_state") != "review_only_no_capital_or_execution_authority"]
    forbidden_true = [key for key in FALSE_AUTHORITY_KEYS if AUTHORITY_BOUNDARY.get(key) is True]
    errors: list[str] = []
    warnings: list[str] = []
    if frontdoor.get("status") != "ok":
        errors.append("finance_cache_frontdoor_status_not_ok")
    if as_dict(frontdoor.get("validation")).get("status") != "ok":
        errors.append("finance_cache_frontdoor_validation_not_ok")
    if not source_rows:
        errors.append("frontdoor_rows_missing")
    if authority_conflicts:
        errors.append(f"authority_conflicts:{','.join(str(item) for item in authority_conflicts[:20])}")
    if forbidden_true:
        errors.append(f"authority_boundary_true_forbidden:{','.join(forbidden_true)}")
    market_readiness_age = age_hours(market_readiness.get("generated_at_utc"), now)
    if not market_readiness:
        warnings.append("wf85_market_hours_readiness_missing")
    elif market_readiness_age is None or market_readiness_age > 24:
        warnings.append("wf85_market_hours_readiness_stale_or_unparseable")
    category_counts = counts(ranked_rows, "category")
    market_refresh_required = [row for row in ranked_rows if row.get("market_window_refresh_required")]
    top_route_queue = ranked_rows[:25]
    top_review_queue = [
        row for row in ranked_rows
        if row.get("category") in {"approval_card_candidate_owner_gated", "in_band_review_monitor", "reclaim_watch", "evidence_or_freshness_repair"}
    ][:25]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only WF78 route-readiness P3 market/ranking packet. It ranks the queue and labels market-window prerequisites without refreshing data or granting approval.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "finance_cache_frontdoor": rel(FRONTDOOR),
            "wf85_market_hours_readiness": rel(MARKET_HOURS_READINESS),
        },
        "source_state": {
            "frontdoor_status": frontdoor.get("status"),
            "frontdoor_validation_status": as_dict(frontdoor.get("validation")).get("status"),
            "frontdoor_generated_at_utc": frontdoor.get("generated_at_utc"),
            "frontdoor_age_hours": age_hours(frontdoor.get("generated_at_utc"), now),
            "market_hours_readiness_status": market_readiness.get("status"),
            "market_hours_readiness_classification": market_readiness.get("classification"),
            "market_hours_readiness_generated_at_utc": market_readiness.get("generated_at_utc"),
            "market_hours_readiness_age_hours": market_readiness_age,
        },
        "market_session": session,
        "summary": {
            "ticker_count": len(ranked_rows),
            "category_counts": category_counts,
            "routing_tier_counts": counts(ranked_rows, "routing_tier"),
            "routing_state_counts": counts(ranked_rows, "routing_state"),
            "timing_state_counts": counts(ranked_rows, "timing_state"),
            "trade_readiness_state_counts": counts(ranked_rows, "trade_readiness_state"),
            "authority_state_counts": counts(ranked_rows, "authority_state"),
            "market_window_refresh_required_count": len(market_refresh_required),
            "approval_card_candidate_owner_gated_count": category_counts.get("approval_card_candidate_owner_gated", 0),
            "in_band_review_monitor_count": category_counts.get("in_band_review_monitor", 0),
            "reclaim_watch_count": category_counts.get("reclaim_watch", 0),
            "no_chase_count": category_counts.get("no_chase", 0),
            "avoid_until_reclaim_or_invalidation_repair_count": category_counts.get("avoid_until_reclaim_or_invalidation_repair", 0),
            "top_route_queue_tickers": [str(row.get("ticker")) for row in top_route_queue],
            "top_review_queue_tickers": [str(row.get("ticker")) for row in top_review_queue],
            "approval_card_candidate_owner_gated_tickers": ticker_list(ranked_rows, "approval_card_candidate_owner_gated"),
            "in_band_review_monitor_tickers": ticker_list(ranked_rows, "in_band_review_monitor"),
            "market_window_state": session.get("window"),
            "regular_market_hours": session.get("regular_market_hours"),
            "market_holiday": session.get("market_holiday"),
            "early_close": session.get("early_close"),
            "next_safe_action": (
                "Wait for a market-window quote refresh before decision-card or paper-card preparation; use this as a review-only queue."
                if session.get("deployment_fresh_price_allowed") is not True
                else "Use this ranking for review-only triage, then run exact market-window quote/card gates before any owner-card preparation."
            ),
        },
        "top_route_queue": top_route_queue,
        "top_review_queue": top_review_queue,
        "rows": ranked_rows,
        "validation": {
            "status": "error" if errors else "warning" if warnings else "ok",
            "errors": errors,
            "warnings": warnings,
            "checks": {
                "frontdoor_rows": len(source_rows),
                "authority_conflict_count": len(authority_conflicts),
                "forbidden_authority_true_count": len(forbidden_true),
            },
        },
        "stop_lines": [
            "This ranking is review-only queue evidence, not approval, recommendation, paper/live execution, or brokerage/account authority.",
            "Approval-card candidate means owner-gated card-prep candidate only; exact Randall approval and fresh guard proof remain required.",
            "Market-window refresh required means wait for the proper quote/card refresh path; this script does not fetch market data.",
        ],
    }
    return payload


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--now-utc", help="Override current UTC timestamp for tests.")
    args = parser.parse_args(argv)
    payload = build_payload(parse_utc(args.now_utc) if args.now_utc else None)
    out = resolve(args.out)
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} tickers={tickers} categories={categories} "
        "market_window={window} refresh_required={refresh_required}".format(
            status=payload.get("status"),
            validation=as_dict(payload.get("validation")).get("status"),
            tickers=as_dict(payload.get("summary")).get("ticker_count"),
            categories=as_dict(payload.get("summary")).get("category_counts"),
            window=as_dict(payload.get("market_session")).get("window"),
            refresh_required=as_dict(payload.get("summary")).get("market_window_refresh_required_count"),
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
