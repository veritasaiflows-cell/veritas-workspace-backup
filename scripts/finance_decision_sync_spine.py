#!/usr/bin/env python3
"""Build the finance decision sync spine.

This is a derived synchronization surface for the finance OS. It joins the
morning paper recommendation cards, WF78 routing/capital-review state, WF68
alerts, WF67 request artifacts, band/repair posture, paper positions, and the
decision factory into one per-ticker state ledger.

It does not approve capital deployment, submit/cancel/sell/modify paper or live
orders, mutate accounts, move money, or mutate portfolio/canon state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_decision_state_compiler import (
    ABOVE_BAND_STATES,
    ABOVE_BAND_VETO,
    BAND_POSITION_VETOES,
    BELOW_STOP_VETO,
    IN_BAND_HOLD_VERDICT,
    PROMOTE_VERDICT,
    STATE_ORDER,
    normalized_promotion_gate_fields,
    primary_state_from_states,
    state_for_promotion_gate_verdict,
)
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "finance-decision-sync-spine.json"
DEFAULT_MD_OUT = TMP / "finance-decision-sync-spine.md"

MORNING_CARDS = TMP / "morning-paper-deployment-recommendation-cards.json"
CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
DECISION_FACTORY = TMP / "finance-decision-factory.json"
OWNER_CARD_PREP = TMP / "wf78-owner-card-prep-loop.json"
EVENT_REROUTING = TMP / "wf78-event-triggered-rerouting.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
CONFIDENCE_GATE = TMP / "wf78-tier-a-confidence-gate.json"
PROMOTION_GATE = TMP / "chief-intelligence-promotion-gate.json"
BAND_PROPOSALS = TMP / "band-proposals.json"
BAND_HYGIENE = TMP / "band-hygiene-freshness-controller.json"
CURRENT_ALERTS = TMP / "intraday-alerts" / "current-alerts.json"
DELIVERY_ROUTER = TMP / "intraday-alerts" / "delivery-router-status.json"
PAPER_POSITIONS = TMP / "finance-intelligence-state-paper-positions.json"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
MARKET_HARDENING = TMP / "market-execution-readiness-cron-hardening.json"

SCHEMA = "veritas.finance_decision_sync_spine.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "derived_sync_surface_only": True,
    "automated_non_capital_state_sync_allowed": True,
    "owner_action_required_for_capital": True,
    "owner_card_generation_allowed": False,
    "wf67_request_artifact_generation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_cancel_sell_modify_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_FLAGS = {
    "review_only",
    "derived_sync_surface_only",
    "automated_non_capital_state_sync_allowed",
    "owner_action_required_for_capital",
}

APPLIED_BAND_MAINTENANCE_STATES = {"applied_auto_maintenance", "applied_auto_maintenance_watch"}


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


def index_rows(rows: list[Any], key: str = "ticker") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get(key))
        if symbol:
            out[symbol] = row_dict
    return out


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def money_equal(left: Any, right: Any) -> bool:
    try:
        return round(float(left), 2) == round(float(right), 2)
    except (TypeError, ValueError):
        return left == right


def infer_band_status_from_levels(
    price: Any,
    low: Any,
    high: Any,
    stop: Any,
    fallback: Any = None,
) -> Any:
    try:
        price_f = float(price)
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return fallback
    try:
        stop_f = float(stop)
    except (TypeError, ValueError):
        stop_f = None
    if stop_f is not None and price_f < stop_f:
        return "BELOW_STOP"
    if price_f < low_f:
        return "BELOW_BAND_WAIT"
    if price_f > high_f:
        return "ABOVE_BAND_WAIT"
    return "IN_BAND"


def band_proposal_current_context(band_row: dict[str, Any]) -> dict[str, Any]:
    if not band_row:
        return {}
    use_suggested = band_row.get("canonical_apply_eligible") is True
    low_key = "suggested_band_low" if use_suggested else "current_band_low"
    high_key = "suggested_band_high" if use_suggested else "current_band_high"
    stop_key = "suggested_stop" if use_suggested else "current_stop"
    status = infer_band_status_from_levels(
        band_row.get("close"),
        band_row.get(low_key),
        band_row.get(high_key),
        band_row.get(stop_key),
        fallback=band_row.get("band_status"),
    )
    return {
        "entry_band_low": band_row.get(low_key),
        "entry_band_high": band_row.get(high_key),
        "stop_or_invalidation": band_row.get(stop_key),
        "band_status": status,
        "current_price": band_row.get("close"),
        "canonical_apply_eligible": bool(band_row.get("canonical_apply_eligible")),
        "needs_review": bool(band_row.get("needs_review")),
        "source": "sql_first_band_proposal" if use_suggested else "band_proposal_current_legacy",
        "supersedes_legacy_band": use_suggested,
        "legacy_current_band": {
            "entry_band_low": band_row.get("current_band_low"),
            "entry_band_high": band_row.get("current_band_high"),
            "stop_or_invalidation": band_row.get("current_stop"),
        },
    }


def canonical_band_context(
    morning_row: dict[str, Any],
    capital_row: dict[str, Any],
    decision_row: dict[str, Any],
    band_row: dict[str, Any],
) -> dict[str, Any]:
    """Pick the current band/stop route before older card/proposal snapshots."""

    capital_wf84 = as_dict(capital_row.get("wf84_canonical_data_plane"))
    decision_wf84 = as_dict(decision_row.get("wf84_canonical_data_plane"))
    written_band = as_dict(capital_row.get("written_band"))
    band_proposal_context = band_proposal_current_context(band_row)
    context_candidates: list[tuple[str, dict[str, Any], str, str, str, str, str]] = [
        (
            "band_proposals.sql_first_current",
            band_proposal_context,
            "entry_band_low",
            "entry_band_high",
            "stop_or_invalidation",
            "band_status",
            "current_price",
        ),
        (
            "wf78_capital_review_queue.wf84_canonical_data_plane",
            capital_wf84,
            "entry_band_low",
            "entry_band_high",
            "stop_or_invalidation",
            "band_status",
            "latest_known_price",
        ),
        (
            "finance_decision_factory.wf84_canonical_data_plane",
            decision_wf84,
            "entry_band_low",
            "entry_band_high",
            "stop_or_invalidation",
            "band_status",
            "latest_known_price",
        ),
        (
            "wf78_capital_review_queue.written_band",
            written_band,
            "entry_band_low",
            "entry_band_high",
            "stop_or_invalidation",
            "current_band_status",
            "card_reference_price",
        ),
        (
            "finance_decision_factory",
            decision_row,
            "entry_band_low",
            "entry_band_high",
            "stop_or_invalidation",
            "current_band_status",
            "current_price",
        ),
        (
            "morning_paper_deployment_cards",
            morning_row,
            "entry_band_low",
            "entry_band_high",
            "stop_or_invalidation",
            "band_status",
            "current_price",
        ),
        (
            "band_proposals.legacy_current",
            band_row,
            "current_band_low",
            "current_band_high",
            "current_stop",
            "band_status",
            "close",
        ),
    ]
    selected: dict[str, Any] = {}
    selected_source = "missing"
    for source, row, low_key, high_key, stop_key, status_key, price_key in context_candidates:
        if not row:
            continue
        low = row.get(low_key)
        high = row.get(high_key)
        stop = row.get(stop_key)
        if any(value is not None for value in (low, high, stop)):
            selected = {
                "entry_band_low": low,
                "entry_band_high": high,
                "stop_or_invalidation": stop,
                "band_status": row.get(status_key),
                "current_price": row.get(price_key),
            }
            selected_source = source
            break

    legacy_contexts: list[dict[str, Any]] = []
    for source, row, low_key, high_key, stop_key, status_key, price_key in context_candidates:
        if source == selected_source or not row:
            continue
        low = row.get(low_key)
        high = row.get(high_key)
        stop = row.get(stop_key)
        if not any(value is not None for value in (low, high, stop)):
            continue
        if (
            money_equal(low, selected.get("entry_band_low"))
            and money_equal(high, selected.get("entry_band_high"))
            and money_equal(stop, selected.get("stop_or_invalidation"))
        ):
            continue
        legacy_contexts.append({
            "status": "superseded_by_current_wf84_sql_canon_route",
            "source": source,
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "band_status": row.get(status_key),
            "current_price": row.get(price_key),
        })

    selected["band_source"] = selected_source
    selected["superseded_legacy_band_context"] = legacy_contexts
    return selected


def add_source(sources: set[str], path: Path) -> None:
    if path.exists():
        sources.add(rel(path))


def alert_index(alerts_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for alert in as_list(alerts_payload.get("alerts")):
        alert_dict = as_dict(alert)
        event = as_dict(alert_dict.get("event"))
        symbol = ticker(event.get("ticker") or alert_dict.get("ticker") or alert_dict.get("symbol"))
        if not symbol:
            continue
        out.setdefault(symbol, []).append({
            "event_type": event.get("event_type"),
            "summary": event.get("summary"),
            "recommended_next_step": as_dict(alert_dict.get("decision_packet")).get("recommended_next_step"),
            "trigger": event.get("trigger"),
            "authority": alert_dict.get("authority"),
        })
    return out


def reroute_action_index(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in as_list(payload.get("actions")):
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if not symbol:
            continue
        out.setdefault(symbol, []).append({
            "action_type": row_dict.get("action_type"),
            "trigger": row_dict.get("trigger"),
            "priority": row_dict.get("priority"),
            "current_route": row_dict.get("current_route"),
            "proposed_route": row_dict.get("proposed_route"),
            "reason": row_dict.get("reason"),
            "apply_allowed": row_dict.get("apply_allowed"),
            "capital_deployment_approved": row_dict.get("capital_deployment_approved"),
            "paper_or_live_execution_allowed": row_dict.get("paper_or_live_execution_allowed"),
        })
    return out


def source_status(path: Path) -> dict[str, Any]:
    payload = load_dict(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
    }


def authority_clean(*payloads: dict[str, Any]) -> bool:
    forbidden_true = {
        "capital_deployment_allowed",
        "capital_deployment_approved",
        "trade_or_execution_allowed",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "paper_submit_cancel_sell_modify_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "canon_or_portfolio_mutation_allowed",
        "cash_sizing_sleeve_risk_rule_mutation_allowed",
        "owner_approval_inferred",
        "paper_trade_allowed",
        "paper_trade_execution_allowed",
        "paper_order_execution_allowed",
        "paper_order_submit_allowed_by_this_registry",
        "paper_order_cancel_allowed_by_this_registry",
        "live_trade_or_account_action_allowed",
        "portfolio_mutation_allowed",
    }
    for payload in payloads:
        for key in ("authority_boundary", "authority"):
            boundary = as_dict(payload.get(key))
            for flag in forbidden_true:
                if boundary.get(flag) is True:
                    return False
    return True


primary_state = primary_state_from_states


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    morning = load_dict(MORNING_CARDS)
    capital_queue = load_dict(CAPITAL_QUEUE)
    decision_factory = load_dict(DECISION_FACTORY)
    owner_prep = load_dict(OWNER_CARD_PREP)
    rerouting = load_dict(EVENT_REROUTING)
    auto_router = load_dict(AUTO_ROUTER)
    confidence = load_dict(CONFIDENCE_GATE)
    promotion = load_dict(PROMOTION_GATE)
    bands = load_dict(BAND_PROPOSALS)
    hygiene = load_dict(BAND_HYGIENE)
    current_alerts = load_dict(CURRENT_ALERTS)
    delivery_router = load_dict(DELIVERY_ROUTER)
    paper_positions = load_dict(PAPER_POSITIONS)

    morning_by_ticker = index_rows(as_list(morning.get("cards")))
    capital_by_ticker = index_rows(as_list(capital_queue.get("rows")))
    decision_by_ticker = index_rows(as_list(decision_factory.get("decision_ledger")))
    owner_by_ticker = index_rows(as_list(owner_prep.get("prepared")))
    router_by_ticker = index_rows(as_list(auto_router.get("rows")))
    confidence_by_ticker = index_rows(as_list(confidence.get("rows")))
    promotion_by_ticker = index_rows(as_list(promotion.get("candidates")))
    band_by_ticker = index_rows(as_list(bands.get("proposals")))
    hygiene_by_ticker = index_rows(as_list(hygiene.get("rows")))
    alerts_by_ticker = alert_index(current_alerts)
    actions_by_ticker = reroute_action_index(rerouting)
    positions_by_ticker = index_rows(as_list(paper_positions.get("positions")), key="symbol")

    tickers = sorted(set().union(
        morning_by_ticker,
        capital_by_ticker,
        decision_by_ticker,
        owner_by_ticker,
        router_by_ticker,
        promotion_by_ticker,
        band_by_ticker,
        hygiene_by_ticker,
        alerts_by_ticker,
        actions_by_ticker,
        positions_by_ticker,
    ))

    rows: list[dict[str, Any]] = []
    for symbol in tickers:
        morning_row = morning_by_ticker.get(symbol, {})
        capital_row = capital_by_ticker.get(symbol, {})
        decision_row = decision_by_ticker.get(symbol, {})
        owner_row = owner_by_ticker.get(symbol, {})
        router_row = router_by_ticker.get(symbol, {})
        confidence_row = confidence_by_ticker.get(symbol, {})
        promotion_row = promotion_by_ticker.get(symbol, {})
        band_row = band_by_ticker.get(symbol, {})
        hygiene_row = hygiene_by_ticker.get(symbol, {})
        alert_rows = alerts_by_ticker.get(symbol, [])
        action_rows = actions_by_ticker.get(symbol, [])
        position_row = positions_by_ticker.get(symbol, {})

        states: set[str] = set()
        blockers: list[str] = []
        warnings: list[str] = []
        sources: set[str] = set()

        for path in [
            MORNING_CARDS,
            CAPITAL_QUEUE,
            DECISION_FACTORY,
            OWNER_CARD_PREP,
            EVENT_REROUTING,
            AUTO_ROUTER,
            CONFIDENCE_GATE,
            PROMOTION_GATE,
            BAND_PROPOSALS,
            BAND_HYGIENE,
            CURRENT_ALERTS,
            DELIVERY_ROUTER,
            PAPER_POSITIONS,
        ]:
            add_source(sources, path)

        event_types = {str(alert.get("event_type") or "") for alert in alert_rows}
        band_context = canonical_band_context(morning_row, capital_row, decision_row, band_row)
        band_status = (
            band_context.get("band_status")
            or promotion_row.get("band_status")
            or band_row.get("band_status")
        )
        gate_verdict = (
            morning_row.get("gate_verdict")
            or decision_row.get("gate_verdict")
            or promotion_row.get("chief_intelligence_verdict")
        )
        promotion_gate_vetoes = (
            morning_row.get("gate_vetoes")
            or decision_row.get("gate_vetoes")
            or promotion_row.get("vetoes")
        )
        wf67_status = (
            morning_row.get("wf67_request_generation_status")
            or decision_row.get("wf67_request_generation_status")
            or owner_row.get("wf67_request_generation_status")
        )
        route_state = (
            morning_row.get("wf78_route_state")
            or capital_row.get("auto_state")
            or router_row.get("auto_state")
        )
        confidence_state = (
            morning_row.get("confidence_gate_state")
            or confidence_row.get("tier_a_confidence_status")
        )
        current_price = first_present(
            band_context.get("current_price"),
            morning_row.get("current_price"),
            capital_row.get("current_price"),
            band_row.get("close"),
        )
        if current_price is None and alert_rows:
            current_price = as_dict(as_dict(alert_rows[0]).get("trigger")).get("observed_price")

        band_needs_review = bool(band_row.get("needs_review"))
        band_repair_mode = str(band_row.get("entry_policy") or "").lower() == "repair_mode"
        band_blocking = symbol in set(as_list(as_dict(bands.get("summary")).get("blocking_review_tickers")))
        hygiene_state = hygiene_row.get("state")
        hygiene_blockers = as_list(hygiene_row.get("blockers"))
        entry_policy_review = as_dict(hygiene_row.get("entry_policy_review"))
        morning_clean = bool(morning_row.get("clean_for_randall_approval_review"))
        legacy_band_context = as_list(band_context.get("superseded_legacy_band_context"))
        if legacy_band_context:
            warnings.append("superseded_legacy_band_context_present")

        gate_fields = normalized_promotion_gate_fields(
            gate_verdict,
            promotion_gate_vetoes,
            band_status,
        )
        gate_verdict = gate_fields.get("gate_verdict")
        promotion_gate_vetoes = gate_fields.get("gate_vetoes")
        warnings.extend(as_list(gate_fields.get("warnings")))

        if band_status == "BELOW_STOP":
            states.add("below_stop_or_invalidation")
            blockers.append("price_breaches_stop_or_below_stop")
        elif "price_breaches_stop" in event_types:
            warnings.append("superseded_legacy_stop_alert_present")
        if band_status in ABOVE_BAND_STATES:
            states.add("no_chase")
            blockers.append("no_chase_or_above_band")
        elif "no_chase_upper_band_breach" in event_types:
            warnings.append("superseded_legacy_no_chase_alert_present")
        if band_repair_mode:
            states.add("repair_mode")
            blockers.append("band_entry_policy_repair_mode")
        if (band_needs_review or band_blocking) and hygiene_state not in APPLIED_BAND_MAINTENANCE_STATES:
            if band_status == "IN_BAND":
                states.add("in_band_not_clean")
            else:
                states.add("repair_mode")
            blockers.append("band_proposal_needs_review")
        if hygiene_state in APPLIED_BAND_MAINTENANCE_STATES:
            warnings.append("routine_band_maintenance_applied")
        elif hygiene_state == "post_apply_review_still_open":
            states.add("in_band_not_clean" if band_status == "IN_BAND" else "repair_mode")
            blockers.append("post_apply_band_review_still_open")
        elif hygiene_state == "eligible_auto_maintenance_pending":
            states.add("in_band_not_clean")
            blockers.append("eligible_band_maintenance_pending")
        elif hygiene_state == "exception_owner_review":
            states.add("in_band_not_clean" if band_status == "IN_BAND" else "repair_mode")
            blockers.append("band_exception_owner_review")
        elif hygiene_state in {"missing_band_context", "band_refresh_skipped"}:
            states.add("repair_mode")
            blockers.append(f"band_hygiene_state={hygiene_state}")
        if "quote_not_intraday_fresh" in hygiene_blockers or "missing_quote_snapshot" in hygiene_blockers:
            states.add("blocked_missing_freshness")
            blockers.append("band_hygiene_quote_not_fresh")
        if morning_row and as_dict(morning_row.get("quote_snapshot")).get("freshness_status") != "fresh":
            states.add("blocked_missing_freshness")
            blockers.append("morning_card_quote_not_fresh")
        gate_state = state_for_promotion_gate_verdict(gate_verdict)
        if gate_state:
            states.add(gate_state)
            blockers.append(f"promotion_gate_verdict={gate_verdict}")
        if wf67_status == "blocked":
            states.add("wf67_request_blocked")
            blockers.append("wf67_request_blocked")
        if any(action.get("action_type") == "repair_evidence" for action in action_rows):
            states.add("evidence_repair")
        if alert_rows:
            states.add("alert_only")
        if entry_policy_review.get("candidate") is True:
            states.add("entry_policy_review_required")
            warnings.append("entry_policy_review_candidate_non_authorizing")
        if position_row:
            states.add("paper_position_monitor")
        if capital_row.get("capital_review_card_preparable"):
            states.add("owner_card_preparable")
        if wf67_status == "ok" and (morning_row.get("wf67_request_path") or decision_row.get("wf67_request_path") or owner_row.get("wf67_request_path")):
            states.add("paper_request_ready_pending_exact_approval")
        if morning_clean:
            states.add("approval_card_clean")
        if morning_clean and blockers:
            states.discard("approval_card_clean")
            warnings.append("morning_card_clean_conflicts_with_sync_blockers")
        if "approval_card_clean" in states and "paper_request_ready_pending_exact_approval" not in states:
            states.discard("approval_card_clean")
            states.add("wf67_request_blocked")
            blockers.append("clean_card_missing_wf67_request")
        if not states:
            states.add("route_monitor")

        primary = primary_state_from_states(states)
        rows.append({
            "ticker": symbol,
            "primary_state": primary,
            "states": sorted(states, key=lambda item: STATE_ORDER.index(item) if item in STATE_ORDER else 999),
            "clean_for_paper_deployment_review": primary in {"approval_card_clean", "paper_request_ready_pending_exact_approval"} and not blockers,
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "current_price": current_price,
            "band_status": band_status,
            "band_source": band_context.get("band_source"),
            "band_needs_review": band_needs_review,
            "band_repair_mode": band_repair_mode,
            "band_review_reasons": as_list(band_row.get("reasons")),
            "band_hygiene_state": hygiene_state,
            "band_hygiene_blockers": hygiene_blockers,
            "band_hygiene_auto_apply": as_dict(hygiene_row.get("auto_apply")),
            "entry_policy_review_candidate": entry_policy_review.get("candidate") is True,
            "entry_policy_review_action": entry_policy_review.get("recommended_entry_policy_action"),
            "entry_policy_review": entry_policy_review,
            "entry_band_low": band_context.get("entry_band_low"),
            "entry_band_high": band_context.get("entry_band_high"),
            "stop_or_invalidation": band_context.get("stop_or_invalidation"),
            "superseded_legacy_band_context": legacy_band_context,
            "route_state": route_state,
            "confidence_gate_state": confidence_state,
            "confidence_promotion_effect": confidence_row.get("promotion_effect"),
            "promotion_gate_verdict": gate_verdict,
            "promotion_gate_vetoes": promotion_gate_vetoes,
            "morning_card_status": morning_row.get("status"),
            "owner_card_path": morning_row.get("owner_card_path") or decision_row.get("owner_card_path") or owner_row.get("card_path"),
            "wf67_request_path": morning_row.get("wf67_request_path") or decision_row.get("wf67_request_path") or owner_row.get("wf67_request_path"),
            "wf67_request_generation_status": wf67_status,
            "decision_factory_disposition": decision_row.get("disposition"),
            "decision_factory_blocked_reason": decision_row.get("blocked_reason"),
            "alert_events": alert_rows,
            "rerouting_actions": action_rows[:5],
            "paper_position": ({
                "quantity": position_row.get("quantity"),
                "market_value": position_row.get("market_value"),
                "unrealized_pl": position_row.get("unrealized_pl"),
                "unrealized_pl_percent": position_row.get("unrealized_pl_percent"),
            } if position_row else None),
            "source_artifacts": sorted(sources),
            "owner_action_required": (
                entry_policy_review.get("candidate") is True
                or primary in {
                    "approval_card_clean",
                    "paper_request_ready_pending_exact_approval",
                    "below_stop_or_invalidation",
                    "promotion_vetoed",
                    "in_band_not_clean",
                    "wf67_request_blocked",
                }
            ),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })

    sources_payload = {
        "morning_cards": source_status(MORNING_CARDS),
        "capital_queue": source_status(CAPITAL_QUEUE),
        "decision_factory": source_status(DECISION_FACTORY),
        "owner_card_prep": source_status(OWNER_CARD_PREP),
        "event_rerouting": source_status(EVENT_REROUTING),
        "auto_router": source_status(AUTO_ROUTER),
        "confidence_gate": source_status(CONFIDENCE_GATE),
        "promotion_gate": source_status(PROMOTION_GATE),
        "band_proposals": source_status(BAND_PROPOSALS),
        "band_hygiene": source_status(BAND_HYGIENE),
        "current_alerts": source_status(CURRENT_ALERTS),
        "delivery_router": source_status(DELIVERY_ROUTER),
        "paper_positions": source_status(PAPER_POSITIONS),
        "quote_proof": source_status(QUOTE_PROOF),
        "market_hardening": source_status(MARKET_HARDENING),
    }
    return rows, sources_payload


def build_payload() -> dict[str, Any]:
    rows, sources = build_rows()
    state_counts: dict[str, int] = {}
    for row in rows:
        state = str(row.get("primary_state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1
    clean = [row["ticker"] for row in rows if row.get("clean_for_paper_deployment_review")]
    owner_required = [row["ticker"] for row in rows if row.get("owner_action_required")]
    entry_policy_review = [row["ticker"] for row in rows if row.get("entry_policy_review_candidate")]
    sync_conflicts = [
        row["ticker"] for row in rows
        if "morning_card_clean_conflicts_with_sync_blockers" in as_list(row.get("warnings"))
    ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Single derived finance decision-state spine for WF78/WF68/WF67/band/repair/paper-position synchronization.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "ticker_count": len(rows),
            "state_counts": dict(sorted(state_counts.items())),
            "clean_for_paper_deployment_review_count": len(clean),
            "clean_for_paper_deployment_review_tickers": clean,
            "owner_action_required_count": len(owner_required),
            "entry_policy_review_candidate_count": len(entry_policy_review),
            "entry_policy_review_candidate_tickers": entry_policy_review,
            "sync_conflict_count": len(sync_conflicts),
            "sync_conflict_tickers": sync_conflicts,
            "next_safe_action": (
                "Review clean names only after exact Randall approval; inspect sync conflicts and blockers before treating any in-band name as clean."
            ),
        },
        "sources": sources,
        "rows": rows,
        "validation": {},
        "stop_lines": [
            "Derived sync spine only; no order submit/cancel/sell/modify/approval.",
            "No live endpoint, brokerage/account action, money movement, portfolio/canon mutation, or owner approval inference.",
            "Clean review state still means Randall review only; any paper execution requires exact approval, fresh WF67 guards, and a short-lived kill switch.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" and not sync_conflicts else "warning"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    for key in TRUE_FLAGS:
        if boundary.get(key) is not True:
            errors.append(f"required_true_authority_{key}_not_true")
    rows = as_list(payload.get("rows"))
    if not rows:
        errors.append("rows_missing")
    for row in rows:
        row_dict = as_dict(row)
        symbol = row_dict.get("ticker")
        band_status = str(row_dict.get("band_status") or "").strip().upper()
        gate_verdict = row_dict.get("promotion_gate_verdict")
        gate_vetoes = {str(item).strip() for item in as_list(row_dict.get("promotion_gate_vetoes"))}
        for key in ("capital_deployment_approved", "trade_or_execution_approved", "paper_or_live_execution_allowed", "owner_approval_inferred"):
            if row_dict.get(key) is not False:
                errors.append(f"{symbol}:{key}_not_false")
        if row_dict.get("clean_for_paper_deployment_review") and row_dict.get("blockers"):
            errors.append(f"{symbol}:clean_with_blockers")
        if band_status == "IN_BAND" and gate_vetoes.intersection(BAND_POSITION_VETOES):
            errors.append(f"{symbol}:in_band_with_band_position_veto")
        if band_status in ABOVE_BAND_STATES and gate_verdict in {PROMOTE_VERDICT, IN_BAND_HOLD_VERDICT}:
            errors.append(f"{symbol}:above_band_with_in_band_gate_verdict")
        if band_status == "BELOW_STOP" and BELOW_STOP_VETO not in gate_vetoes:
            errors.append(f"{symbol}:below_stop_missing_gate_veto")
    source_payloads = [load_dict(Path(str(as_dict(src).get("path") or ""))) for src in as_dict(payload.get("sources")).values()]
    if not authority_clean(*source_payloads):
        errors.append("source_authority_widened")
    conflict_count = int(as_dict(payload.get("summary")).get("sync_conflict_count") or 0)
    if conflict_count:
        warnings.append(f"sync_conflicts_present:{conflict_count}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Finance Decision Sync Spine",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Clean for paper review: `{summary.get('clean_for_paper_deployment_review_count')}`",
        f"- Sync conflicts: `{summary.get('sync_conflict_count')}`",
        "",
        "| Ticker | State | Price | Band | Route | Gate | WF67 | Blockers |",
        "|---|---|---:|---|---|---|---|---|",
    ]
    priority_rows = [
        row for row in as_list(payload.get("rows"))
        if as_dict(row).get("owner_action_required") or as_dict(row).get("primary_state") in {"approval_card_clean", "paper_request_ready_pending_exact_approval"}
    ]
    for row in priority_rows[:40]:
        row_dict = as_dict(row)
        blockers = "; ".join(str(item) for item in as_list(row_dict.get("blockers"))[:2])
        lines.append(
            f"| {row_dict.get('ticker')} | {row_dict.get('primary_state')} | "
            f"{row_dict.get('current_price') if row_dict.get('current_price') is not None else ''} | "
            f"{row_dict.get('band_status') or ''} | {row_dict.get('route_state') or ''} | "
            f"{row_dict.get('promotion_gate_verdict') or ''} | {row_dict.get('wf67_request_generation_status') or ''} | {blockers} |"
        )
    lines.extend([
        "",
        "Boundary: derived review-only sync surface. No paper/live order action, account action, money movement, capital deployment approval, portfolio/canon mutation, or owner approval inference.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the finance decision sync spine.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        atomic_write_json(args.out, payload)
    if args.write_md:
        atomic_write_text(args.md_out, render_markdown(payload))
    result = {
        "status": payload["status"],
        "out": rel(args.out),
        "md_out": rel(args.md_out) if args.write_md else None,
        "summary": payload["summary"],
        "validation": payload["validation"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
