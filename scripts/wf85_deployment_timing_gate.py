#!/usr/bin/env python3
"""Build the WF85 Tier A/B deployment timing gate.

This is a review-only compositor over existing WF78/WF84/WF85 artifacts. It
does not fetch new market data and does not approve capital, paper/live orders,
portfolio changes, account actions, or owner approval.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from trade_grade_decision_os_contract import AUTHORITY_BOUNDARY as WF85_AUTHORITY_BOUNDARY

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "wf85-deployment-timing-gate.json"
CARDS_PATH = TMP / "trade-grade-decision-cards.json"
WF78_ROUTER_PATH = TMP / "wf78-auto-tier-routing.json"
WF84_PACKET_PATH = TMP / "canonical-finance-data-plane.json"
MACRO_SPINE_PATH = TMP / "macro-signal-spine.json"
SECTOR_BOARD_PATH = TMP / "sector-expansion-board.json"
WF87_SHADOW_PATH = TMP / "paper-autotrader" / "shadow-decisions.json"
CAPITAL_QUEUE_PATH = TMP / "wf78-capital-review-queue.json"
EARNINGS_CALENDAR_PATH = TMP / "earnings-calendar.json"
EARNINGS_SOURCE_CONFIDENCE_PATH = TMP / "earnings-date-source-confidence.json"

SCHEMA = "veritas.wf85_deployment_timing_gate.v1"
WORKFLOW_ID = "WF85"

TIER_AB = {"Tier A", "Tier B"}
IN_BAND_STATES = {"IN_BAND"}
NO_CHASE_STATES = {"ABOVE_BAND", "ABOVE_BAND_WAIT", "NO_CHASE"}
BELOW_BAND_STATES = {"BELOW_BAND", "BELOW_BAND_WAIT", "NEAR_BAND", "RECLAIM_ONLY"}
BELOW_STOP_STATES = {"BELOW_STOP"}
EXECUTION_FRESH_QUOTES = {"fresh", "ok", "intraday_fresh"}
REVIEW_ONLY_QUOTES = {
    "post_close_final_quote_available_for_non_executing_review",
    "current_price_technical_available_for_non_executing_review",
}
ETF_TYPES = {"etf", "fund", "index", "sector_etf"}
ETF_TICKERS = {"ITA", "PAVE", "VAW", "VXUS", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLRE", "XLP", "XLU", "XLY"}

AUTHORITY_BOUNDARY = {
    **WF85_AUTHORITY_BOUNDARY,
    "deployment_timing_gate_only": True,
    "automated_non_capital_routing_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def normalize_sector(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    aliases = {
        "Tech": "Technology",
        "Information Technology": "Technology",
        "Health Care": "Healthcare",
        "Communication Services": "Communication Services",
    }
    return aliases.get(text, text)


def rows_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = as_list(payload.get("rows"))
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            output[ticker] = row
    return output


def records_by_ticker(payload: dict[str, Any], key: str = "records") -> dict[str, dict[str, Any]]:
    rows = as_list(payload.get(key))
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            output[ticker] = row
    return output


def wf84_table_by_ticker(wf84: dict[str, Any], table: str) -> dict[str, dict[str, Any]]:
    rows = as_list(as_dict(wf84.get("tables")).get(table))
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            output[ticker] = row
    return output


def sector_rows_by_name(sector_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in as_list(sector_board.get("sectors")):
        if not isinstance(row, dict):
            continue
        sector = normalize_sector(row.get("sector"))
        if sector:
            output[sector] = row
    return output


def latest_shadow_by_ticker(shadow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in as_list(shadow.get("decisions")):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        prior = latest.get(ticker)
        if not prior or str(row.get("generated_at_utc") or "") > str(prior.get("generated_at_utc") or ""):
            latest[ticker] = row
    return latest


def ticker_set_from_rows(payload: dict[str, Any]) -> set[str]:
    output: set[str] = set()
    for row in as_list(payload.get("rows")):
        row_dict = as_dict(row)
        symbol = str(row_dict.get("ticker") or "").upper()
        if symbol:
            output.add(symbol)
    return output


def classify_price_band(card: dict[str, Any]) -> tuple[str, list[str]]:
    band_status = as_dict(card.get("entry_band")).get("band_status")
    if band_status in BELOW_STOP_STATES:
        return "below_stop_block", [f"band_status={band_status}"]
    if band_status in NO_CHASE_STATES:
        return "above_band_wait", [f"band_status={band_status}"]
    if band_status in BELOW_BAND_STATES:
        return "below_band_wait", [f"band_status={band_status}"]
    if band_status in IN_BAND_STATES:
        return "in_band", [f"band_status={band_status}"]
    return "missing_or_unknown_band", [f"band_status={band_status}"]


def classify_quote(card: dict[str, Any]) -> tuple[str, list[str]]:
    quote_status = as_dict(card.get("source_freshness")).get("quote_freshness_status")
    if quote_status in EXECUTION_FRESH_QUOTES:
        return "execution_fresh", [f"quote_freshness_status={quote_status}"]
    if quote_status in REVIEW_ONLY_QUOTES:
        return "review_only_price_context", [f"quote_freshness_status={quote_status}"]
    return "stale_or_missing", [f"quote_freshness_status={quote_status}"]


def price_display_context(card: dict[str, Any], quote_gate: str) -> dict[str, Any]:
    current_price = as_dict(card.get("current_price"))
    source_freshness = as_dict(card.get("source_freshness"))
    latest_price = current_price.get("latest_known_price")
    quote_status = current_price.get("quote_freshness_status") or source_freshness.get("quote_freshness_status")
    if latest_price is None:
        display_status = "provider_field_missing" if quote_status else "price_field_missing"
    elif quote_gate == "execution_fresh":
        display_status = "execution_fresh"
    elif quote_gate == "review_only_price_context":
        display_status = (
            "post_close_review_only"
            if quote_status == "post_close_final_quote_available_for_non_executing_review"
            else "technical_review_only"
        )
    else:
        display_status = "stale_or_missing"
    return {
        "latest_known_price_present": latest_price is not None,
        "display_status": display_status,
        "quote_freshness_status": quote_status,
        "market_date": current_price.get("market_date") or source_freshness.get("market_date"),
        "quote_time_utc": current_price.get("quote_time_utc") or source_freshness.get("quote_time_utc"),
        "source": current_price.get("source"),
        "fresh_quote_required": source_freshness.get("fresh_quote_required"),
    }


def classify_earnings(
    ticker: str,
    earnings: dict[str, Any],
    router_row: dict[str, Any],
    today: date,
    calendar_record: dict[str, Any] | None = None,
    confidence_record: dict[str, Any] | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    instrument_type = str(router_row.get("instrument_type") or "").lower()
    if instrument_type in ETF_TYPES or ticker in ETF_TICKERS:
        return "not_applicable_fund_or_etf", ["earnings_not_applicable_for_fund_or_etf"], {}

    calendar = as_dict(calendar_record)
    confidence = as_dict(confidence_record)
    lifecycle = as_dict(calendar.get("lifecycle"))
    wf84_next_date = parse_date(earnings.get("next_earnings_date"))
    calendar_next_date = parse_date(calendar.get("next_earnings_date"))
    confidence_provider_next_date = parse_date(confidence.get("provider_next_earnings_date"))
    next_date = wf84_next_date or calendar_next_date or confidence_provider_next_date
    if wf84_next_date:
        evidence_source = "wf84_earnings_catalyst"
        evidence_source_path = earnings.get("source_path") or rel(WF84_PACKET_PATH)
    elif calendar_next_date:
        evidence_source = "earnings_calendar"
        evidence_source_path = rel(EARNINGS_CALENDAR_PATH)
    elif confidence_provider_next_date:
        evidence_source = "earnings_source_confidence_provider"
        evidence_source_path = rel(EARNINGS_SOURCE_CONFIDENCE_PATH)
    else:
        evidence_source = "earnings_calendar" if calendar else "wf84_earnings_catalyst"
        evidence_source_path = rel(EARNINGS_CALENDAR_PATH) if calendar else earnings.get("source_path")
    days = earnings.get("days_to_earnings")
    if days is None and next_date:
        days = (next_date - today).days
    details = {
        "next_earnings_date": next_date.isoformat() if next_date else None,
        "days_to_earnings": days,
        "earnings_date_confirmed": earnings.get("earnings_date_confirmed"),
        "catalyst_status": earnings.get("catalyst_status"),
        "source_path": earnings.get("source_path"),
        "evidence_source": evidence_source,
        "evidence_source_path": evidence_source_path,
        "date_source": calendar.get("source") or confidence.get("provider_source"),
        "date_source_class": calendar.get("date_source_class"),
        "primary_confirmed": calendar.get("primary_confirmed"),
        "fetched_at_utc": calendar.get("fetched_at_utc") or confidence.get("provider_fetched_at_utc"),
        "source_confidence": confidence.get("source_confidence"),
        "primary_confirmation_status": confidence.get("primary_confirmation_status"),
        "provider_next_earnings_date": confidence.get("provider_next_earnings_date"),
        "lifecycle_status": lifecycle.get("status"),
        "lifecycle_reason": lifecycle.get("reason"),
    }
    if lifecycle.get("status") == "post_event_review_confirmed_next_date_pending" and next_date is None:
        details["gate_reason"] = "post_earnings_confirmed_next_date_pending"
        details["gate_clear_condition"] = "Next earnings date must appear in earnings-calendar/source-confidence, or a manual caution override must be recorded."
        return "unknown_block_or_caution", ["post_earnings_confirmed_next_date_pending"], details
    if days is None:
        details["gate_reason"] = "earnings_timing_unknown"
        details["gate_clear_condition"] = "Refresh or repair earnings-calendar/source-confidence until a next earnings date is available."
        return "unknown_block_or_caution", ["earnings_timing_unknown"], details
    try:
        numeric_days = int(days)
    except (TypeError, ValueError):
        details["gate_reason"] = "earnings_timing_unparseable"
        details["gate_clear_condition"] = "Repair the earnings date value before using this row for timing review."
        return "unknown_block_or_caution", ["earnings_timing_unparseable"], details
    details["days_to_earnings"] = numeric_days
    if numeric_days < 0 and abs(numeric_days) <= 10:
        details["gate_reason"] = "post_earnings_drift_window"
        details["gate_clear_condition"] = "Wait for the post-earnings drift window to clear or complete a fresh post-earnings review."
        return "post_earnings_drift_window", [f"days_since_earnings={abs(numeric_days)}"], details
    if 0 <= numeric_days <= 28:
        details["gate_reason"] = "upcoming_earnings_within_4_weeks"
        details["gate_clear_condition"] = "Wait until the earnings event passes and the post-earnings review/fresh calendar confirms the next safe window."
        return "earnings_within_4_weeks", [f"days_to_earnings={numeric_days}"], details
    details["gate_reason"] = "safe_window"
    details["gate_clear_condition"] = "No earnings gate block from current review-only calendar data."
    return "safe_window", [f"days_to_earnings={numeric_days}"], details


def classify_macro_sector(
    router_row: dict[str, Any],
    sector_row: dict[str, Any] | None,
    macro_spine: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    macro_posture = as_dict(macro_spine.get("summary")).get("macro_posture")
    if not sector_row:
        return "unknown_caution", ["sector_row_not_mapped"], {"macro_posture": macro_posture}
    leadership = sector_row.get("leadership_status")
    above_50dma = sector_row.get("above_50dma")
    short_term_signal = as_dict(sector_row.get("short_term_moving_averages")).get("signal")
    details = {
        "macro_posture": macro_posture,
        "sector": sector_row.get("sector"),
        "sector_ticker": sector_row.get("ticker"),
        "leadership_status": leadership,
        "above_50dma": above_50dma,
        "short_term_signal": short_term_signal,
    }
    reasons = [f"macro_posture={macro_posture}", f"sector_leadership={leadership}"]
    if leadership == "deteriorating" and above_50dma is False:
        return "sector_headwind_override", reasons + ["sector_below_50dma"], details
    if leadership in {"deteriorating", "lagging"} or short_term_signal == "short_term_repair_needed":
        return "caution", reasons + [f"short_term_signal={short_term_signal}"], details
    if macro_posture in {"defensive_neutral_selective", "defensive"}:
        return "caution", reasons, details
    return "clear", reasons, details


def classify_wf87_stub(
    ticker: str,
    shadow_row: dict[str, Any] | None,
    final_state: str,
    *,
    in_shadow_scope: bool = True,
) -> tuple[str, list[str], dict[str, Any]]:
    details = {
        "latest_shadow_decision_id": shadow_row.get("decision_id") if shadow_row else None,
        "latest_shadow_decision": shadow_row.get("shadow_decision") if shadow_row else None,
        "latest_shadow_generated_at_utc": shadow_row.get("generated_at_utc") if shadow_row else None,
        "in_current_shadow_scope": in_shadow_scope,
    }
    if final_state in {"review_ready_wait_approval", "review_ready_wait_fresh_quote"}:
        if not in_shadow_scope:
            return "shadow_seed_not_expected_current_scope", ["not_in_wf78_capital_review_queue"], details
        if shadow_row:
            return "existing_shadow_seed_present", ["latest_shadow_seed_found"], details
        return "issuance_stub_needed", ["no_shadow_seed_for_review_ready_ticker"], details
    return "not_scoreable_now", [f"final_timing_state={final_state}"], details


def final_timing_state(
    *,
    tier_scope: str,
    decision_state: str,
    price_gate: str,
    quote_gate: str,
    earnings_gate: str,
    macro_gate: str,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if tier_scope != "tier_a_b_decision_layer":
        return "thin_monitor_only", ["not_tier_a_b"]
    if price_gate == "below_stop_block":
        return "blocked_below_stop_or_invalidation", ["price_band_gate=below_stop_block"]
    if decision_state == "below_stop_or_invalidation":
        reasons = [f"decision_state={decision_state}"]
        if price_gate:
            reasons.append(f"price_band_gate={price_gate}")
        return "blocked_below_stop_or_invalidation", reasons
    if decision_state in {"blocked_missing_freshness", "evidence_repair", "monitor_only"}:
        return "repair_first", [f"decision_state={decision_state}"]
    if price_gate == "above_band_wait":
        return "wait_no_chase", ["price_band_gate=above_band_wait"]
    if price_gate == "below_band_wait":
        return "wait_for_band_reclaim", ["price_band_gate=below_band_wait"]
    if price_gate == "missing_or_unknown_band":
        return "repair_first", ["price_band_gate=missing_or_unknown_band"]
    if earnings_gate in {"earnings_within_4_weeks", "post_earnings_drift_window", "unknown_block_or_caution"}:
        blockers.append(f"earnings_gate={earnings_gate}")
    if macro_gate == "sector_headwind_override":
        blockers.append("macro_sector_gate=sector_headwind_override")
    if blockers:
        return "review_ready_suppressed", blockers
    if quote_gate != "execution_fresh":
        return "review_ready_wait_fresh_quote", [f"quote_freshness_class={quote_gate}"]
    if decision_state == "review_ready" and price_gate == "in_band":
        return "review_ready_wait_approval", ["review_only_owner_approval_required"]
    return "repair_first", [f"decision_state={decision_state}", f"price_band_gate={price_gate}"]


def build_rows(
    *,
    cards_payload: dict[str, Any],
    router_payload: dict[str, Any],
    wf84_payload: dict[str, Any],
    macro_payload: dict[str, Any],
    sector_payload: dict[str, Any],
    shadow_payload: dict[str, Any],
    earnings_calendar_payload: dict[str, Any] | None = None,
    earnings_confidence_payload: dict[str, Any] | None = None,
    shadow_scope_tickers: set[str] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    today = today or datetime.now(timezone.utc).date()
    router_by_ticker = rows_by_ticker(router_payload)
    security_by_ticker = wf84_table_by_ticker(wf84_payload, "security_master")
    earnings_by_ticker = wf84_table_by_ticker(wf84_payload, "earnings_catalyst")
    calendar_by_ticker = records_by_ticker(earnings_calendar_payload or {})
    confidence_by_ticker = records_by_ticker(earnings_confidence_payload or {})
    sectors_by_name = sector_rows_by_name(sector_payload)
    shadows_by_ticker = latest_shadow_by_ticker(shadow_payload)
    rows: list[dict[str, Any]] = []
    for card in as_list(cards_payload.get("cards")):
        if not isinstance(card, dict):
            continue
        ticker = str(card.get("ticker") or "").upper()
        router_row = router_by_ticker.get(ticker, {})
        security_row = security_by_ticker.get(ticker, {})
        auto_tier = card.get("auto_tier") or router_row.get("auto_tier")
        tier_scope = "tier_a_b_decision_layer" if auto_tier in TIER_AB else "tier_c_thin_monitor"
        sector_name = normalize_sector(router_row.get("sector") or security_row.get("sector"))
        sector_row = sectors_by_name.get(sector_name or "")
        price_gate, price_reasons = classify_price_band(card)
        quote_gate, quote_reasons = classify_quote(card)
        earnings_gate, earnings_reasons, earnings_details = classify_earnings(
            ticker,
            earnings_by_ticker.get(ticker, {}),
            {**security_row, **router_row},
            today,
            calendar_by_ticker.get(ticker),
            confidence_by_ticker.get(ticker),
        )
        macro_gate, macro_reasons, macro_details = classify_macro_sector(router_row or security_row, sector_row, macro_payload)
        state, state_reasons = final_timing_state(
            tier_scope=tier_scope,
            decision_state=str(card.get("decision_state") or ""),
            price_gate=price_gate,
            quote_gate=quote_gate,
            earnings_gate=earnings_gate,
            macro_gate=macro_gate,
        )
        in_shadow_scope = True if shadow_scope_tickers is None else ticker in shadow_scope_tickers
        wf87_status, wf87_reasons, wf87_details = classify_wf87_stub(
            ticker,
            shadows_by_ticker.get(ticker),
            state,
            in_shadow_scope=in_shadow_scope,
        )
        rows.append({
            "ticker": ticker,
            "name": card.get("name") or router_row.get("name") or security_row.get("name"),
            "auto_tier": auto_tier,
            "auto_state": card.get("auto_state") or router_row.get("auto_state"),
            "tier_scope": tier_scope,
            "sector": sector_name,
            "instrument_type": router_row.get("instrument_type") or security_row.get("instrument_type"),
            "decision_state": card.get("decision_state"),
            "current_price": as_dict(card.get("current_price")).get("latest_known_price"),
            "entry_band": card.get("entry_band"),
            "stop_or_invalidation": card.get("stop_or_invalidation"),
            "price_band_gate": price_gate,
            "price_band_reasons": price_reasons,
            "quote_freshness_class": quote_gate,
            "quote_reasons": quote_reasons,
            "price_display_context": price_display_context(card, quote_gate),
            "earnings_gate": earnings_gate,
            "earnings_reasons": earnings_reasons,
            "earnings": earnings_details,
            "macro_sector_gate": macro_gate,
            "macro_sector_reasons": macro_reasons,
            "macro_sector": macro_details,
            "wf87_stub_status": wf87_status,
            "wf87_stub_reasons": wf87_reasons,
            "wf87_stub": wf87_details,
            "final_timing_state": state,
            "final_timing_reasons": state_reasons,
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return rows


def build_payload() -> dict[str, Any]:
    generated = utc_now()
    sources = {
        "wf85_decision_cards": CARDS_PATH,
        "wf78_auto_tier_router": WF78_ROUTER_PATH,
        "wf84_canonical_data_plane": WF84_PACKET_PATH,
        "macro_signal_spine": MACRO_SPINE_PATH,
        "sector_expansion_board": SECTOR_BOARD_PATH,
        "wf87_shadow_decisions": WF87_SHADOW_PATH,
        "wf78_capital_review_queue": CAPITAL_QUEUE_PATH,
        "earnings_calendar": EARNINGS_CALENDAR_PATH,
        "earnings_date_source_confidence": EARNINGS_SOURCE_CONFIDENCE_PATH,
    }
    payloads = {name: load_json(path) for name, path in sources.items()}
    rows = build_rows(
        cards_payload=payloads["wf85_decision_cards"],
        router_payload=payloads["wf78_auto_tier_router"],
        wf84_payload=payloads["wf84_canonical_data_plane"],
        macro_payload=payloads["macro_signal_spine"],
        sector_payload=payloads["sector_expansion_board"],
        shadow_payload=payloads["wf87_shadow_decisions"],
        earnings_calendar_payload=payloads["earnings_calendar"],
        earnings_confidence_payload=payloads["earnings_date_source_confidence"],
        shadow_scope_tickers=ticker_set_from_rows(payloads["wf78_capital_review_queue"]),
    )
    tier_ab_rows = [row for row in rows if row.get("tier_scope") == "tier_a_b_decision_layer"]
    final_counts = Counter(row.get("final_timing_state") for row in rows)
    tier_ab_final_counts = Counter(row.get("final_timing_state") for row in tier_ab_rows)
    errors: list[str] = []
    warnings: list[str] = []
    missing_sources = [name for name, path in sources.items() if not path.exists()]
    if missing_sources:
        errors.append(f"missing_sources:{','.join(missing_sources)}")
    for name, payload in payloads.items():
        if not payload:
            errors.append(f"source_unparseable_or_empty:{name}")
    if len(rows) != len(as_list(payloads["wf85_decision_cards"].get("cards"))):
        errors.append("row_count_does_not_match_wf85_cards")
    if not tier_ab_rows:
        errors.append("tier_a_b_rows_missing")
    if any(row.get("authority_boundary", {}).get("capital_deployment_approved") for row in rows):
        errors.append("capital_deployment_authority_drift")
    if any(row.get("final_timing_state") == "review_ready_wait_approval" for row in rows):
        warnings.append("review_ready_wait_approval_rows_require_exact_owner_approval")
    if any(row.get("wf87_stub_status") == "issuance_stub_needed" for row in tier_ab_rows):
        warnings.append("wf87_issuance_stubs_needed_for_some_review_ready_rows")
    status = "blocked" if errors else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated,
        "workflow_id": WORKFLOW_ID,
        "status": status,
        "purpose": "Tier A/B deployment timing compositor over WF85 cards, WF84 earnings, sector/macro context, and WF87 shadow state.",
        "summary": {
            "row_count": len(rows),
            "tier_a_b_row_count": len(tier_ab_rows),
            "tier_counts": dict(Counter(row.get("auto_tier") for row in rows)),
            "final_timing_state_counts": dict(final_counts),
            "tier_a_b_final_timing_state_counts": dict(tier_ab_final_counts),
            "price_band_gate_counts": dict(Counter(row.get("price_band_gate") for row in tier_ab_rows)),
            "quote_freshness_class_counts": dict(Counter(row.get("quote_freshness_class") for row in tier_ab_rows)),
            "price_display_status_counts": dict(Counter(as_dict(row.get("price_display_context")).get("display_status") for row in tier_ab_rows)),
            "earnings_gate_counts": dict(Counter(row.get("earnings_gate") for row in tier_ab_rows)),
            "earnings_gate_reason_counts": dict(Counter(as_dict(row.get("earnings")).get("gate_reason") for row in tier_ab_rows)),
            "earnings_date_source_class_counts": dict(Counter(as_dict(row.get("earnings")).get("date_source_class") for row in tier_ab_rows)),
            "earnings_source_confidence_counts": dict(Counter(as_dict(row.get("earnings")).get("source_confidence") for row in tier_ab_rows)),
            "macro_sector_gate_counts": dict(Counter(row.get("macro_sector_gate") for row in tier_ab_rows)),
            "wf87_stub_status_counts": dict(Counter(row.get("wf87_stub_status") for row in tier_ab_rows)),
            "review_ready_wait_approval_count": tier_ab_final_counts.get("review_ready_wait_approval", 0),
            "review_ready_wait_fresh_quote_count": tier_ab_final_counts.get("review_ready_wait_fresh_quote", 0),
            "review_ready_suppressed_count": tier_ab_final_counts.get("review_ready_suppressed", 0),
            "next_safe_action": "Use Tier A/B rows for deploy-vs-wait review only; exact Randall approval and WF67 guard proof remain required before paper action.",
        },
        "rows": rows,
        "source_artifacts": {name: rel(path) for name, path in sources.items()},
        "validation": {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Review-only timing gate.",
            "No timing state is capital approval or execution approval.",
            "No paper/live order, brokerage/account action, money movement, canon/portfolio/cash/sizing/risk-rule mutation, or owner approval inference.",
        ],
    }


def self_test() -> dict[str, Any]:
    cards = {
        "cards": [
            {
                "ticker": "AAA",
                "name": "AAA Inc.",
                "auto_tier": "Tier A",
                "auto_state": "A-READY",
                "decision_state": "review_ready",
                "current_price": {"latest_known_price": 10},
                "entry_band": {"low": 9, "high": 11, "band_status": "IN_BAND"},
                "source_freshness": {"quote_freshness_status": "intraday_fresh"},
            },
            {
                "ticker": "BBB",
                "auto_tier": "Tier B",
                "decision_state": "review_ready",
                "current_price": {"latest_known_price": 20},
                "entry_band": {"low": 10, "high": 15, "band_status": "ABOVE_BAND"},
                "source_freshness": {"quote_freshness_status": "intraday_fresh"},
            },
            {
                "ticker": "CCC",
                "auto_tier": "Tier C",
                "decision_state": "monitor_only",
                "entry_band": {"band_status": "missing_required_refresh"},
                "source_freshness": {"quote_freshness_status": "current_price_technical_available_for_non_executing_review"},
            },
            {
                "ticker": "DDD",
                "auto_tier": "Tier A",
                "decision_state": "review_ready",
                "current_price": {"latest_known_price": 30, "market_date": "2026-06-13", "source": "test"},
                "entry_band": {"low": 25, "high": 35, "band_status": "IN_BAND"},
                "source_freshness": {"quote_freshness_status": "current_price_technical_available_for_non_executing_review"},
            },
        ]
    }
    router = {
        "rows": [
            {"ticker": "AAA", "auto_tier": "Tier A", "sector": "Technology", "instrument_type": "operating_company"},
            {"ticker": "BBB", "auto_tier": "Tier B", "sector": "Industrials", "instrument_type": "operating_company"},
            {"ticker": "CCC", "auto_tier": "Tier C", "sector": "Energy", "instrument_type": "operating_company"},
            {"ticker": "DDD", "auto_tier": "Tier A", "sector": "Technology", "instrument_type": "operating_company"},
        ]
    }
    wf84 = {
        "tables": {
            "security_master": [
                {"ticker": "AAA", "sector": "Technology", "instrument_type": "operating_company"},
                {"ticker": "BBB", "sector": "Industrials", "instrument_type": "operating_company"},
                {"ticker": "DDD", "sector": "Technology", "instrument_type": "operating_company"},
            ],
            "earnings_catalyst": [
                {"ticker": "AAA", "next_earnings_date": "2026-08-01", "days_to_earnings": 49, "earnings_date_confirmed": False},
                {"ticker": "BBB", "next_earnings_date": "2026-06-25", "days_to_earnings": 12, "earnings_date_confirmed": False},
            ],
        }
    }
    macro = {"summary": {"macro_posture": "risk_on"}}
    sectors = {"sectors": [{"sector": "Technology", "leadership_status": "improving", "above_50dma": True}]}
    shadow = {"decisions": [{"ticker": "AAA", "decision_id": "shadow-aaa", "generated_at_utc": "2026-06-13T00:00:00Z"}]}
    earnings_calendar = {
        "records": [
            {"ticker": "DDD", "next_earnings_date": "2026-07-20", "source": "yfinance", "date_source_class": "provider_estimate", "primary_confirmed": False},
        ]
    }
    earnings_confidence = {
        "records": [
            {"ticker": "DDD", "provider_next_earnings_date": "2026-07-20", "source_confidence": "provider_estimate"},
        ]
    }
    rows = build_rows(
        cards_payload=cards,
        router_payload=router,
        wf84_payload=wf84,
        macro_payload=macro,
        sector_payload=sectors,
        shadow_payload=shadow,
        earnings_calendar_payload=earnings_calendar,
        earnings_confidence_payload=earnings_confidence,
        shadow_scope_tickers={"AAA"},
        today=date(2026, 6, 13),
    )
    by_ticker = {row["ticker"]: row for row in rows}
    errors: list[str] = []
    if by_ticker["AAA"]["final_timing_state"] != "review_ready_wait_approval":
        errors.append("aaa_not_review_ready_wait_approval")
    if by_ticker["AAA"]["wf87_stub_status"] != "existing_shadow_seed_present":
        errors.append("aaa_shadow_seed_not_detected")
    if by_ticker["BBB"]["final_timing_state"] != "wait_no_chase":
        errors.append("bbb_above_band_not_no_chase")
    if by_ticker["CCC"]["final_timing_state"] != "thin_monitor_only":
        errors.append("tier_c_not_thin_monitor_only")
    if by_ticker["DDD"]["earnings"]["date_source_class"] != "provider_estimate":
        errors.append("ddd_calendar_source_not_exposed")
    if by_ticker["DDD"]["price_display_context"]["display_status"] != "technical_review_only":
        errors.append("ddd_price_display_context_not_review_only")
    if by_ticker["DDD"]["wf87_stub_status"] != "shadow_seed_not_expected_current_scope":
        errors.append("ddd_shadow_scope_not_honored")
    if any(row["authority_boundary"]["capital_deployment_approved"] for row in rows):
        errors.append("authority_boundary_drift")
    return {"status": "ok" if not errors else "blocked", "errors": errors}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 Tier A/B deployment timing gate.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        result = self_test()
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "ok" else 1
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} rows={rows} tier_ab={tier_ab} "
        "review_ready_wait_approval={approval} suppressed={suppressed}".format(
            status=payload.get("status"),
            validation=as_dict(payload.get("validation")).get("status"),
            rows=as_dict(payload.get("summary")).get("row_count"),
            tier_ab=as_dict(payload.get("summary")).get("tier_a_b_row_count"),
            approval=as_dict(payload.get("summary")).get("review_ready_wait_approval_count"),
            suppressed=as_dict(payload.get("summary")).get("review_ready_suppressed_count"),
        )
    )
    for item in as_list(as_dict(payload.get("validation")).get("errors")):
        print(f"  [error] {item}")
    for item in as_list(as_dict(payload.get("validation")).get("warnings")):
        print(f"  [warning] {item}")
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
