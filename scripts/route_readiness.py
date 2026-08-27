#!/usr/bin/env python3
"""Shared review-only route-readiness classification helpers.

This module keeps routing tier/state, timing, decision readiness, trade
readiness, and authority state separated. It is presentation/routing logic only:
it grants no capital, trade, paper/live, brokerage/account, or owner-approval
authority.
"""
from __future__ import annotations

from typing import Any

REVIEW_ONLY_QUOTE_STATUSES = {
    "post_close_final_quote_available_for_non_executing_review",
    "review_only_price_context",
}

MONITOR_GRADE_QUOTE_STATUSES = {
    "tier_c_monitor_grade_reference",
}

FORBIDDEN_AUTHORITY_KEYS = (
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "live_trade_allowed",
    "brokerage_or_account_action_allowed",
    "live_brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
)

ROW_AUTHORITY_KEYS = (
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "owner_approval_inferred",
)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def row_authority_flags(row: dict[str, Any]) -> dict[str, bool]:
    return {key: bool(row.get(key)) for key in ROW_AUTHORITY_KEYS}


def timing_state_for(band_status: Any, quote_freshness_status: Any) -> str:
    raw_band = str(band_status or "").strip()
    upper_band = raw_band.upper()
    quote_status = str(quote_freshness_status or "").strip()
    review_only_quote = quote_status in REVIEW_ONLY_QUOTE_STATUSES
    monitor_grade_quote = quote_status in MONITOR_GRADE_QUOTE_STATUSES

    if upper_band == "BELOW_STOP":
        return "below_stop_or_invalidation"
    if upper_band == "ABOVE_BAND":
        if monitor_grade_quote:
            return "above_band_monitor_grade_no_chase"
        return "above_band_no_chase"
    if upper_band == "BELOW_BAND":
        if monitor_grade_quote:
            return "below_band_monitor_grade_reclaim_watch"
        return "below_band_reclaim_watch"
    if upper_band == "IN_BAND":
        if monitor_grade_quote:
            return "in_band_monitor_grade"
        return "in_band_review_only_quote" if review_only_quote else "in_band_fresh_review"
    if upper_band == "NEAR_BAND":
        return "near_band_monitor_grade" if monitor_grade_quote else "band_status_near_band"
    if upper_band == "RECLAIM_ONLY":
        return "reclaim_only_monitor_grade" if monitor_grade_quote else "band_status_reclaim_only"
    if not raw_band or upper_band == "UNKNOWN":
        return "quote_or_band_status_unknown"
    return f"band_status_{raw_band.lower()}"


def authority_state_for(authority: dict[str, Any]) -> str:
    forbidden_true = [key for key in FORBIDDEN_AUTHORITY_KEYS if authority.get(key) is True]
    if forbidden_true:
        return "blocked_authority_flag_true"
    return "review_only_no_capital_or_execution_authority"


def trade_readiness_state_for(decision_state: Any, timing_state: str, authority_state: str) -> str:
    decision = str(decision_state or "unknown")
    if authority_state != "review_only_no_capital_or_execution_authority":
        return "blocked_authority_conflict"
    if timing_state == "below_stop_or_invalidation" or decision == "below_stop_or_invalidation":
        return "not_trade_ready_below_stop_or_invalidation"
    if timing_state in {"above_band_no_chase", "above_band_monitor_grade_no_chase"} or decision == "no_chase":
        return "not_trade_ready_no_chase"
    if decision in {"evidence_repair", "blocked_missing_freshness", "blocked_missing_source_open"}:
        return "not_trade_ready_evidence_or_freshness_repair"
    if decision == "review_ready":
        if timing_state in {"in_band_fresh_review", "in_band_review_only_quote"}:
            return "approval_card_candidate_owner_gated"
        return "review_ready_but_timing_not_trade_ready"
    if timing_state in {"below_band_reclaim_watch", "below_band_monitor_grade_reclaim_watch"}:
        return "not_trade_ready_reclaim_watch"
    if timing_state in {"in_band_monitor_grade", "near_band_monitor_grade", "reclaim_only_monitor_grade"}:
        return "not_trade_ready_monitor_grade"
    if timing_state in {"in_band_fresh_review", "in_band_review_only_quote"}:
        return "not_trade_ready_in_band_monitor_only"
    if decision == "monitor_only":
        return "not_trade_ready_monitor_only"
    return "not_trade_ready_unknown_or_blocked"


def next_route_action_for(timing_state: str, decision_state: Any, trade_readiness_state: str) -> str:
    decision = str(decision_state or "unknown")
    if trade_readiness_state == "approval_card_candidate_owner_gated":
        return "Prepare non-executing owner approval-card review; exact approval still required before paper/live action."
    if trade_readiness_state == "not_trade_ready_below_stop_or_invalidation":
        return "Avoid until reclaim/invalidation repair clears."
    if trade_readiness_state == "not_trade_ready_no_chase":
        return "Monitor; no chase while above band."
    if trade_readiness_state == "not_trade_ready_reclaim_watch":
        return "Keep on reclaim watch; below-band is not automatic entry."
    if trade_readiness_state == "not_trade_ready_evidence_or_freshness_repair":
        return "Repair source, freshness, or decision blockers before review escalation."
    if trade_readiness_state == "not_trade_ready_monitor_grade":
        return "Use monitor-grade band context for triage only; promote and refresh before decision-card or trade-readiness work."
    if timing_state in {"in_band_fresh_review", "in_band_review_only_quote"} and decision == "monitor_only":
        return "Keep as in-band review monitor; refresh market-window timing before approval-card work."
    if timing_state == "band_status_missing_required_refresh":
        return "Refresh band/stop context before timing, decision-card, or trade-readiness escalation."
    return "Monitor under current review-only route."


def build_route_readiness(
    *,
    routing_tier: Any,
    routing_state: Any,
    decision_state: Any,
    band_status: Any,
    quote_freshness_status: Any,
    authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authority_flags = dict(authority or {})
    timing_state = timing_state_for(band_status, quote_freshness_status)
    authority_state = authority_state_for(authority_flags)
    trade_readiness_state = trade_readiness_state_for(decision_state, timing_state, authority_state)
    return {
        "routing_tier": routing_tier,
        "routing_state": routing_state,
        "timing_state": timing_state,
        "decision_state": decision_state,
        "trade_readiness_state": trade_readiness_state,
        "authority_state": authority_state,
        "band_status": band_status,
        "quote_freshness_status": quote_freshness_status,
        "review_only": True,
        "requires_exact_owner_approval_before_capital_or_execution": True,
        "authority": authority_flags,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
        "next_route_action": next_route_action_for(timing_state, decision_state, trade_readiness_state),
    }


def route_readiness_from_wf84_row(row: dict[str, Any], decision_state: Any) -> dict[str, Any]:
    return build_route_readiness(
        routing_tier=row.get("auto_tier"),
        routing_state=row.get("auto_state"),
        decision_state=decision_state,
        band_status=row.get("band_status"),
        quote_freshness_status=row.get("quote_freshness_status"),
        authority=row_authority_flags(row),
    )


def route_readiness_from_wf85_card(wf85: dict[str, Any]) -> dict[str, Any]:
    entry_band = as_dict(wf85.get("entry_band"))
    current_price = as_dict(wf85.get("current_price"))
    return build_route_readiness(
        routing_tier=wf85.get("auto_tier"),
        routing_state=wf85.get("auto_state"),
        decision_state=wf85.get("decision_state"),
        band_status=entry_band.get("band_status"),
        quote_freshness_status=current_price.get("quote_freshness_status"),
        authority=as_dict(wf85.get("authority_boundary")),
    )


def route_readiness_from_route_context(
    route: dict[str, Any],
    wf85: dict[str, Any],
    card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = as_dict(card)
    wf85_band = as_dict(wf85.get("entry_band"))
    wf85_price = as_dict(wf85.get("current_price"))
    card_band = as_dict(card.get("price_band_stop"))
    return build_route_readiness(
        routing_tier=route.get("auto_tier"),
        routing_state=route.get("auto_state"),
        decision_state=wf85.get("decision_state") or "monitor_only",
        band_status=first_present(wf85_band.get("band_status"), card_band.get("band_status")),
        quote_freshness_status=first_present(
            wf85_price.get("quote_freshness_status"),
            card_band.get("quote_freshness_status"),
        ),
        authority=as_dict(wf85.get("authority_boundary")),
    )
