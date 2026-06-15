"""Build review-only ticker intelligence cards for WF77.

Cards are derived routing/review artifacts. They are not canon, approval, sizing,
portfolio mutation, or trade/account authority.
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from board_state_contract import deployment_contract
from wf72_entry_stop_reference_helper import (
    NO_DRIFT_PILOT_JSON,
    PILOT_TICKERS,
    build_entry_stop_reference_metadata,
    write_no_drift_pilot,
)
from wf78_ticker_card_field_repair_apply import apply_rows as apply_wf78_repair_rows
from wf78_ticker_card_field_repair_apply import collect_rows as collect_wf78_repair_rows

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "ticker-intelligence-cards"

FUNDAMENTALS_PATH = WORKSPACE / "tmp" / "fundamental-metrics-current.json"
DEPLOYMENT_SURFACE_PATH = WORKSPACE / "tmp" / "deployment-readiness-surface.json"
POSITION_SIZING_READINESS_PATH = WORKSPACE / "tmp" / "position-sizing-readiness-current.json"
ANALYST_CONSENSUS_PATH = WORKSPACE / "tmp" / "analyst-consensus-current.json"
COVERAGE_PATH = WORKSPACE / "tmp" / "finance-data-coverage-current.json"
UNIVERSE_PATH = WORKSPACE / "data" / "finance" / "universe-v1.json"
WF78_AUTO_TIER_ROUTING_PATH = WORKSPACE / "tmp" / "wf78-auto-tier-routing.json"
ORDER_CARD_DIR = WORKSPACE / "tmp" / "alpaca-paper-readiness"
OFFICIAL_EARNINGS_BRIDGE_PATH = WORKSPACE / "tmp" / "official-earnings-bridge.json"
SECTOR_EXPANSION_BOARD_PATH = WORKSPACE / "tmp" / "sector-expansion-board.json"
TECHNICAL_REFRESH_PATH = WORKSPACE / "tmp" / "technical-refresh.json"
PORTFOLIO_CONFIG_PATH = WORKSPACE / "tmp" / "portfolio-config.json"
WF78_CARD_FIELD_REPAIR_APPLY_PATH = WORKSPACE / "tmp" / "wf78-ticker-card-field-repair-apply.json"
POST_CLOSE_FINAL_QUOTE_LEDGER_PATH = WORKSPACE / "tmp" / "post-close-final-quote-ledger.json"
DECISION_SYNC_SPINE_PATH = WORKSPACE / "tmp" / "finance-decision-sync-spine.json"
CAPITAL_REVIEW_QUEUE_PATH = WORKSPACE / "tmp" / "wf78-capital-review-queue.json"

AUTHORITY_BOUNDARY = {
    "artifact_role": "derived_review_and_question_routing_surface_only",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sizing_apply_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_card": False,
    "paper_order_cancel_allowed_by_card": False,
    "live_trade_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "source_open_required_before_final_recommendation_or_action_claim": True,
}

RECOMMENDATION_LABELS = {
    "deployable_now": "deployable now",
    "approval_ready_if_fresh": "approval-ready paper starter if fresh in band",
    "promotion_review": "promotion review",
    "watch_only": "watch only",
    "no_chase": "no chase",
    "blocked_stale": "blocked stale",
    "blocked_authority": "blocked authority",
    "reject_defer": "reject/defer",
}


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def approved_wf78_card_field_repair_rows(ticker: str) -> list[dict[str, Any]]:
    gate = load_json(WF78_CARD_FIELD_REPAIR_APPLY_PATH, {})
    if not isinstance(gate, dict):
        return []
    if gate.get("status") != "ok" or gate.get("mode") != "apply":
        return []
    approved_types: list[str] = []
    for result in gate.get("results") or []:
        if str(result.get("ticker") or "").upper() != ticker.upper():
            continue
        repair_types = result.get("repair_types")
        if isinstance(repair_types, list) and repair_types:
            approved_types.extend(str(value) for value in repair_types if value)
        elif result.get("repair_type"):
            approved_types.append(str(result.get("repair_type")))
    if not approved_types:
        selected = {str(value).upper() for value in (gate.get("selected_tickers") or [])}
        if ticker.upper() not in selected:
            return []
    live_rows_by_type: dict[str, list[dict[str, Any]]] = {}
    for row in collect_wf78_repair_rows():
        if str(row.get("ticker") or "").upper() != ticker.upper():
            continue
        repair_type = str(row.get("repair_type") or "")
        if repair_type:
            live_rows_by_type.setdefault(repair_type, []).append(row)
    approved_rows: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for repair_type in approved_types:
        if repair_type in seen_types:
            continue
        rows = live_rows_by_type.get(repair_type) or []
        if rows:
            approved_rows.append(rows[0])
            seen_types.add(repair_type)
    if approved_rows:
        return approved_rows
    return [
        row for row in collect_wf78_repair_rows()
        if str(row.get("ticker") or "").upper() == ticker.upper()
    ]


def apply_approved_wf78_card_field_repair(card: dict[str, Any]) -> dict[str, Any]:
    ticker = str(card.get("ticker") or "").upper()
    rows = approved_wf78_card_field_repair_rows(ticker)
    if not rows:
        return card
    patched, _ = apply_wf78_repair_rows(card, rows, "approved-wf78-card-builder")
    repair = patched.get("wf78_card_field_repair")
    if isinstance(repair, dict):
        repair["persisted_by_card_builder"] = True
        repair["apply_gate"] = str(WF78_CARD_FIELD_REPAIR_APPLY_PATH.relative_to(WORKSPACE))
    sequence = patched.get("wf78_card_field_repair_sequence")
    if isinstance(sequence, dict):
        sequence["persisted_by_card_builder"] = True
        sequence["apply_gate"] = str(WF78_CARD_FIELD_REPAIR_APPLY_PATH.relative_to(WORKSPACE))
    return patched


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def index_fundamentals(data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (data or {}).get("rows") or []
    return {str(row.get("ticker", "")).upper(): row for row in rows if row.get("ticker")}


def index_universe(data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (data or {}).get("entries") or []
    return {str(row.get("ticker", "")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def index_rows_by_ticker(data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (data or {}).get("rows") or []
    return {str(row.get("ticker", "")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def find_ticker_entry(obj: Any, ticker: str) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        symbol = obj.get("ticker") or obj.get("symbol")
        if isinstance(symbol, str) and symbol.upper() == ticker:
            return obj
        # Support both list-of-rows artifacts and ticker-keyed maps such as
        # tmp/analyst-consensus-current.json {"tickers": {"CME": {...}}}.
        for key, value in obj.items():
            if isinstance(key, str) and key.upper() == ticker and isinstance(value, dict):
                return {"ticker": ticker, **value}
            found = find_ticker_entry(value, ticker)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_ticker_entry(value, ticker)
            if found is not None:
                return found
    return None


def find_order_card(ticker: str) -> tuple[dict[str, Any] | None, str | None]:
    if not ORDER_CARD_DIR.exists():
        return None, None
    candidates = sorted(ORDER_CARD_DIR.glob(f"order-card.{ticker.lower()}-*.json"))
    if not candidates:
        candidates = sorted(ORDER_CARD_DIR.glob(f"*{ticker.lower()}*.json"))
    if not candidates:
        return None, None
    path = candidates[-1]
    return load_json(path), str(path.relative_to(WORKSPACE))


def first_present(*candidates: tuple[Any, str | None]) -> tuple[Any, str | None]:
    """Return the first non-null/non-empty value with its source label.

    Ticker cards aggregate review context from multiple artifacts. A missing
    readiness/deployment row should block actionability, not erase a valid
    latest close or configured band from lower-priority review sources.
    """
    for value, source in candidates:
        if value is not None and value != "":
            return value, source
    return None, None


def post_close_quote_row(inputs: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    rows = inputs.get("post_close_final_quote_index")
    if not isinstance(rows, dict):
        rows = index_rows_by_ticker(inputs.get("post_close_final_quote_ledger"))
        inputs["post_close_final_quote_index"] = rows
    row = rows.get(ticker.upper())
    if isinstance(row, dict) and row.get("status") == "ok" and row.get("close") is not None:
        return row
    return None


def portfolio_config_band(config: dict[str, Any] | None, ticker: str) -> dict[str, Any]:
    bands = (config or {}).get("entry_bands") or {}
    row = bands.get(ticker) or bands.get(ticker.upper()) or bands.get(ticker.lower()) or {}
    return row if isinstance(row, dict) else {}


def classify_band_status(price: Any, low: Any, high: Any, stop: Any) -> str | None:
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return None
    try:
        if stop is not None and price_f < float(stop):
            return "BELOW_STOP"
    except (TypeError, ValueError):
        pass
    try:
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return None
    if price_f < low_f:
        return "BELOW_BAND"
    if price_f > high_f:
        return "ABOVE_BAND"
    return "IN_BAND"


def normalize_claim_key(claim: dict[str, Any]) -> str:
    raw = str(claim.get("claim_type") or claim.get("capture_key") or "")
    return raw.removeprefix("official_capture_")


def index_official_claims(bridge: dict[str, Any] | None, ticker: str) -> dict[str, Any]:
    """Return official earnings claims keyed by capture family for one ticker.

    This keeps the card review-only while making the existing WF70/WF66 official
    capture work visible in the ticker-card surface. Values remain source-open
    required and are not treated as canonical or recommendation authority.
    """
    entry = find_ticker_entry(bridge or {}, ticker)
    claims = (((entry or {}).get("official_earnings_bridge") or {}).get("evidence_claims") or [])
    indexed: dict[str, Any] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        key = normalize_claim_key(claim)
        if key:
            indexed[key] = claim
    return indexed


def claim_summary(claim: dict[str, Any] | None) -> dict[str, Any]:
    if not claim:
        return {
            "status": "missing_manual_required",
            "value": None,
            "source_url": None,
            "source_section": None,
            "manual_capture_required": True,
            "note": "No validated official capture found in tmp/official-earnings-bridge.json; do not fabricate.",
        }
    return {
        "status": claim.get("capture_status") or claim.get("status"),
        "value": claim.get("value"),
        "source_url": claim.get("source_url"),
        "source_section": claim.get("source_section"),
        "period": claim.get("period"),
        "manual_capture_required": bool(claim.get("manual_capture_required")),
        "inferred": bool(claim.get("inferred")),
        "claim_text": claim.get("claim_text"),
    }


def technical_record(data: dict[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    records = (data or {}).get("records")
    if isinstance(records, dict):
        value = records.get(ticker)
        return value if isinstance(value, dict) else None
    if isinstance(records, list):
        for row in records:
            if isinstance(row, dict) and str(row.get("ticker", "")).upper() == ticker:
                return row
    return None


def sector_record(data: dict[str, Any] | None, sector_or_ticker: str | None) -> dict[str, Any] | None:
    if not sector_or_ticker:
        return None
    needle = str(sector_or_ticker).upper()
    for row in (data or {}).get("sectors") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("ticker", "")).upper() == needle or str(row.get("sector", "")).upper() == needle:
            return row
    return None


def build_latest_earnings_performance(fundamentals: dict[str, Any] | None, official_claims: dict[str, Any], instrument_type: str | None) -> dict[str, Any]:
    if instrument_type == "etf_or_macro_proxy":
        return {
            "status": "not_applicable_etf_or_macro_proxy",
            "period_end": None,
            "summary": "ETF/macro proxy; issuer earnings performance is not applicable. Use sector/constituent/relative-strength context instead.",
            "official_adjusted_eps": None,
            "official_guidance": None,
            "management_explanation": None,
        }
    return {
        "status": "available" if fundamentals or official_claims else "missing_manual_required",
        "period_type": (fundamentals or {}).get("period_type"),
        "period_end": (fundamentals or {}).get("period_end"),
        "comparison_period_end": (fundamentals or {}).get("comparison_period_end"),
        "revenue": (fundamentals or {}).get("revenue"),
        "revenue_yoy_pct": (fundamentals or {}).get("revenue_yoy_pct"),
        "net_income": (fundamentals or {}).get("net_income"),
        "net_income_yoy_pct": (fundamentals or {}).get("net_income_yoy_pct"),
        "diluted_eps": (fundamentals or {}).get("diluted_eps"),
        "eps_yoy_pct": (fundamentals or {}).get("eps_yoy_pct"),
        "free_cash_flow": (fundamentals or {}).get("free_cash_flow"),
        "free_cash_flow_yoy_pct": (fundamentals or {}).get("free_cash_flow_yoy_pct"),
        "official_adjusted_eps": claim_summary(official_claims.get("adjusted_eps")),
        "official_growth_bridge": claim_summary(official_claims.get("growth_bridge")),
        "official_guidance": claim_summary(official_claims.get("guidance")),
        "management_explanation": claim_summary(official_claims.get("management_explanation")),
        "source_open_required": True,
    }


def build_key_financial_metrics(fundamentals: dict[str, Any] | None, instrument_type: str | None) -> dict[str, Any]:
    if instrument_type == "etf_or_macro_proxy":
        return {
            "status": "not_applicable_etf_or_macro_proxy",
            "note": "Operating-company financial metrics are not applicable to ETF/macro proxy cards.",
        }
    return {
        "status": "available" if fundamentals else "missing_manual_required",
        "growth": metric(fundamentals or {}, ["revenue_yoy_pct", "net_income_yoy_pct", "eps_yoy_pct", "free_cash_flow_yoy_pct"]),
        "profitability": metric(fundamentals or {}, ["gross_margin_pct", "operating_margin_pct", "net_margin_pct", "roic_proxy_pct"]),
        "cash_flow": metric(fundamentals or {}, ["operating_cash_flow", "free_cash_flow", "fcf_per_share", "fcf_yield_pct"]),
        "balance_sheet": metric(fundamentals or {}, ["cash_and_equivalents", "total_debt", "net_debt", "debt_to_annualized_ebitda"]),
        "valuation": metric(fundamentals or {}, ["market_cap", "enterprise_value", "trailing_pe", "forward_pe", "price_to_sales", "price_to_book", "ev_to_ebitda_proxy", "ev_to_fcf_proxy", "earnings_yield_pct"]),
        "capital_returns": metric(fundamentals or {}, ["buyback_yield_pct", "dividend_yield_pct", "shareholder_yield_pct", "capital_return_to_fcf_pct"]),
        "data_quality": (fundamentals or {}).get("data_quality"),
        "source_open_required": True,
    }


def build_risk_register(
    fundamentals: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    deployment_entry: dict[str, Any] | None,
    missing: list[dict[str, str]],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for anomaly in (fundamentals or {}).get("capital_allocation_anomalies") or []:
        if isinstance(anomaly, dict):
            risks.append({"category": "capital_allocation", "severity": anomaly.get("severity", "warning"), "detail": anomaly.get("message") or anomaly.get("code")})
    if (readiness or {}).get("band_status") and (readiness or {}).get("band_status") != "IN_BAND":
        risks.append({"category": "entry_discipline", "severity": "context", "detail": f"Band status is {(readiness or {}).get('band_status')}; avoid no-chase entries without fresh reclaim evidence."})
    if (deployment_entry or {}).get("near_earnings_caution"):
        risks.append({"category": "catalyst", "severity": "context", "detail": "Near-earnings caution is active in deployment surface."})
    for item in missing:
        risks.append({"category": "evidence_gap", "severity": item.get("severity"), "detail": item.get("detail"), "family": item.get("family")})
    if not risks:
        risks.append({"category": "source_open", "severity": "context", "detail": "No card-level risk flags found; open source artifacts before making a final recommendation."})
    return risks


def build_etf_profile(fundamentals: dict[str, Any] | None, sector: dict[str, Any] | None) -> dict[str, Any] | None:
    if (fundamentals or {}).get("instrument_type") != "etf_or_macro_proxy":
        return None
    return {
        "status": "available" if sector else "sector_context_missing",
        "proxy_type": "sector_or_macro_etf",
        "sector": (fundamentals or {}).get("sector"),
        "sector_proxy_ticker": (sector or {}).get("ticker"),
        "sector_relative_strength_vs_spy": (sector or {}).get("relative_strength_vs_spy"),
        "sector_returns_pct": (sector or {}).get("sector_returns_pct"),
        "spy_returns_pct": (sector or {}).get("spy_returns_pct"),
        "relative_labels": (sector or {}).get("relative_labels"),
        "leadership_status": (sector or {}).get("leadership_status"),
        "portfolio_exposure": (sector or {}).get("portfolio_exposure"),
        "underexposed": (sector or {}).get("underexposed"),
        "tracked_universe_candidates": (sector or {}).get("tracked_universe_candidates"),
        "owner_gated_next_review_action": (sector or {}).get("owner_gated_next_review_action"),
    }


def compact_source(path: Path, data: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(WORKSPACE)),
        "exists": path.exists(),
        "generated_at_utc": (data or {}).get("generated_at_utc"),
        "status": (data or {}).get("status"),
    }


def metric(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: row.get(key) for key in keys if key in row}


def build_recommendation_posture(
    ticker: str,
    readiness: dict[str, Any] | None,
    deployment_entry: dict[str, Any] | None,
    price_band_stop: dict[str, Any],
    order_card: dict[str, Any] | None,
    missing: list[dict[str, str]],
) -> dict[str, Any]:
    authority_block = not AUTHORITY_BOUNDARY["paper_order_execution_allowed"]
    stale_blockers = [item["family"] for item in missing if item.get("severity") == "blocking"]
    readiness_state = (readiness or {}).get("state") or (readiness or {}).get("readiness")
    deployment_state = legacy_state((deployment_entry or {}), "surface_state") or legacy_state((deployment_entry or {}), "action_state") or legacy_state((deployment_entry or {}), "machine_state")
    state = deployment_state or readiness_state
    band_status = price_band_stop.get("band_status") or (readiness or {}).get("band_status")
    fresh_required = bool((readiness or {}).get("fresh_quote_required"))
    has_prepared_order_card = bool(order_card)

    if stale_blockers:
        label_key = "blocked_stale"
    elif band_status and band_status not in {"IN_BAND", "IN BAND"}:
        label_key = "no_chase"
    elif state == "DEPLOYABLE NOW":
        label_key = "deployable_now"
    elif has_prepared_order_card and band_status == "IN_BAND":
        label_key = "approval_ready_if_fresh"
    elif state == "PROMOTION REVIEW" or (readiness or {}).get("readiness") == "conditional_ready_after_owner_promotion":
        label_key = "promotion_review"
    else:
        label_key = "watch_only"

    blockers = []
    if fresh_required:
        blockers.append("fresh quote/band/stop check required before any final recommendation or paper-order approval request")
    if state == "PROMOTION REVIEW" or (readiness or {}).get("readiness") == "conditional_ready_after_owner_promotion":
        blockers.append("owner promotion/selection still required before treating as deployed")
    if band_status and band_status not in {"IN_BAND", "IN BAND"}:
        blockers.append("current price is outside the written band; wait for re-entry/reclaim or explicit owner-approved band review")
    if authority_block:
        blockers.append("card itself grants no paper/live execution authority and infers no approval")
    blockers.extend(stale_blockers)

    canonical_state = deployment_contract(
        {
            "surface_state": legacy_state((deployment_entry or {}), "surface_state"),
            "base_surface_state": legacy_state((deployment_entry or {}), "base_surface_state"),
            "action_state": legacy_state((deployment_entry or {}), "action_state"),
            "machine_state": legacy_state((deployment_entry or {}), "machine_state"),
            "workflow_state": legacy_state((deployment_entry or {}), "workflow_state"),
            "band_status": band_status,
            "below_stop": bool((deployment_entry or {}).get("below_stop")),
        }
    )

    return {
        "posture": RECOMMENDATION_LABELS[label_key],
        "posture_key": label_key,
        "deployment_contract": canonical_state,
        "support_level": "prepared_order_card_present" if has_prepared_order_card else "review_context_only",
        "state_source": state,
        "readiness_state_source": readiness_state,
        "deployment_surface_state_source": deployment_state,
        "band_status": band_status,
        "fresh_quote_required": fresh_required,
        "prepared_order_card_present": has_prepared_order_card,
        "actionability": "review_only_owner_gated",
        "blockers_or_gates": blockers,
        "notes": [
            "This is recommendation support, not a black-box buy/sell engine.",
            "Open source artifacts before final readiness, recommendation, approval, or action claims.",
        ],
    }


def build_missing_and_stale(
    ticker: str,
    fundamentals: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    deployment_entry: dict[str, Any] | None,
    analyst_entry: dict[str, Any] | None,
    universe_entry: dict[str, Any] | None = None,
    auto_tier_entry: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not fundamentals:
        items.append({"family": "official_fundamentals", "severity": "blocking", "status": "missing", "detail": "No row in tmp/fundamental-metrics-current.json"})
    if not readiness:
        auto_tier = str((auto_tier_entry or {}).get("auto_tier") or "")
        auto_state = str((auto_tier_entry or {}).get("auto_state") or "")
        legacy_tier = str((universe_entry or {}).get("tier") or "")
        tier_c_thin_monitor = auto_tier == "Tier C" or auto_state.startswith("C-") or (not auto_tier and legacy_tier == "C")
        if not tier_c_thin_monitor:
            items.append(
                {
                    "family": "price_band_stop_position_sizing",
                    "severity": "blocking",
                    "status": "missing",
                    "detail": "No row in current position-sizing readiness packet for Tier A/B deployment or promotion-prep context",
                }
            )
    if not deployment_entry:
        items.append({"family": "deployment_readiness_surface", "severity": "context", "status": "missing", "detail": "Ticker not present in current deployment-readiness surface groups"})
    if not analyst_entry:
        items.append({"family": "analyst_consensus_ratings_targets", "severity": "context", "status": "missing_manual_required", "detail": "tmp/analyst-consensus-current.json is absent or lacks ticker; do not fabricate ratings/targets"})
    elif analyst_entry.get("status") == "missing_manual_required" or analyst_entry.get("manual_required") is True:
        items.append({"family": "analyst_consensus_ratings_targets", "severity": "context", "status": "missing_manual_required", "detail": "Analyst consensus placeholder is present but values remain null/manual-required; do not fabricate ratings/targets"})
    if readiness and readiness.get("fresh_quote_required"):
        items.append({"family": "fresh_price_quote", "severity": "context", "status": "stale_until_refreshed", "detail": "Readiness packet uses pre-Tuesday/reference price and requires fresh quote confirmation"})
    return items


def build_card(ticker: str, inputs: dict[str, Any]) -> dict[str, Any]:
    ticker = ticker.upper()
    fundamentals = inputs["fundamental_index"].get(ticker)
    readiness = find_ticker_entry(inputs["tuesday_readiness"], ticker)
    deployment_entry = find_ticker_entry(inputs["deployment_surface"], ticker)
    analyst_entry = find_ticker_entry(inputs["analyst_consensus"], ticker)
    official_claims = index_official_claims(inputs.get("official_earnings_bridge"), ticker)
    tech_entry = technical_record(inputs.get("technical_refresh"), ticker)
    sector_entry = sector_record(inputs.get("sector_expansion_board"), (fundamentals or {}).get("sector") or ticker)
    config_band = portfolio_config_band(inputs.get("portfolio_config"), ticker)
    universe_entry = inputs.get("universe_index", {}).get(ticker)
    auto_tier_entry = inputs.get("auto_tier_index", {}).get(ticker)
    decision_spine_entry = inputs.get("decision_spine_index", {}).get(ticker)
    capital_queue_entry = inputs.get("capital_queue_index", {}).get(ticker)
    capital_written_band = (capital_queue_entry or {}).get("written_band")
    if not isinstance(capital_written_band, dict):
        capital_written_band = {}
    post_close_quote = post_close_quote_row(inputs, ticker)
    order_card, order_card_path = find_order_card(ticker)
    missing = build_missing_and_stale(ticker, fundamentals, readiness, deployment_entry, analyst_entry, universe_entry, auto_tier_entry)
    instrument_type = (fundamentals or {}).get("instrument_type")

    latest_price, latest_price_source = first_present(
        ((post_close_quote or {}).get("close"), "tmp/post-close-final-quote-ledger.json"),
        ((deployment_entry or {}).get("close"), "tmp/deployment-readiness-surface.json"),
        ((tech_entry or {}).get("close"), "tmp/technical-refresh.json"),
        ((readiness or {}).get("close_reference"), "tmp/position-sizing-readiness-current.json"),
    )
    band_low, band_low_source = first_present(
        (capital_written_band.get("entry_band_low"), "tmp/wf78-capital-review-queue.json"),
        ((decision_spine_entry or {}).get("entry_band_low"), "tmp/finance-decision-sync-spine.json"),
        (config_band.get("low"), "tmp/portfolio-config.json"),
        (((order_card or {}).get("risk_check") or {}).get("entry_band_low"), order_card_path),
        ((readiness or {}).get("band_low"), "tmp/position-sizing-readiness-current.json"),
    )
    band_high, band_high_source = first_present(
        (capital_written_band.get("entry_band_high"), "tmp/wf78-capital-review-queue.json"),
        ((decision_spine_entry or {}).get("entry_band_high"), "tmp/finance-decision-sync-spine.json"),
        (config_band.get("high"), "tmp/portfolio-config.json"),
        (((order_card or {}).get("risk_check") or {}).get("entry_band_high"), order_card_path),
        ((readiness or {}).get("band_high"), "tmp/position-sizing-readiness-current.json"),
    )
    stop, stop_source = first_present(
        (capital_written_band.get("stop_or_invalidation"), "tmp/wf78-capital-review-queue.json"),
        ((capital_queue_entry or {}).get("stop_or_invalidation"), "tmp/wf78-capital-review-queue.json"),
        ((decision_spine_entry or {}).get("stop_or_invalidation"), "tmp/finance-decision-sync-spine.json"),
        (config_band.get("stop"), "tmp/portfolio-config.json"),
        (((order_card or {}).get("risk_check") or {}).get("stop"), order_card_path),
        ((readiness or {}).get("stop"), "tmp/position-sizing-readiness-current.json"),
    )
    band_status = classify_band_status(latest_price, band_low, band_high, stop) or (deployment_entry or {}).get("band_position") or (readiness or {}).get("band_status")

    price_band_stop = {
        "latest_known_price": latest_price,
        "price_source": latest_price_source,
        "entry_band_low": band_low,
        "entry_band_high": band_high,
        "stop_or_invalidation": stop,
        "band_status": band_status,
        "band_source": band_low_source if band_low_source == band_high_source else {"low": band_low_source, "high": band_high_source},
        "stop_source": stop_source,
        "fresh_quote_required": bool((readiness or {}).get("fresh_quote_required")),
        "staleness_note": "Reference price/band from prepared packet; refresh before final use." if (readiness or {}).get("fresh_quote_required") else None,
    }
    if post_close_quote:
        price_band_stop["post_close_final_quote"] = {
            "market_date": post_close_quote.get("market_date"),
            "retrieved_at_utc": post_close_quote.get("retrieved_at_utc"),
            "source": post_close_quote.get("source"),
            "review_only": True,
            "execution_freshness_approved": False,
        }
    entry_stop_reference_metadata = build_entry_stop_reference_metadata(ticker)
    recommendation = build_recommendation_posture(ticker, readiness, deployment_entry, price_band_stop, order_card, missing)

    source_artifacts = [
        compact_source(FUNDAMENTALS_PATH, inputs["fundamentals"]),
        compact_source(DEPLOYMENT_SURFACE_PATH, inputs["deployment_surface"]),
        compact_source(POSITION_SIZING_READINESS_PATH, inputs["tuesday_readiness"]),
        compact_source(ANALYST_CONSENSUS_PATH, inputs["analyst_consensus"]),
        compact_source(OFFICIAL_EARNINGS_BRIDGE_PATH, inputs.get("official_earnings_bridge")),
        compact_source(SECTOR_EXPANSION_BOARD_PATH, inputs.get("sector_expansion_board")),
        compact_source(TECHNICAL_REFRESH_PATH, inputs.get("technical_refresh")),
        compact_source(PORTFOLIO_CONFIG_PATH, inputs.get("portfolio_config")),
        compact_source(POST_CLOSE_FINAL_QUOTE_LEDGER_PATH, inputs.get("post_close_final_quote_ledger")),
        compact_source(DECISION_SYNC_SPINE_PATH, inputs.get("decision_sync_spine")),
        compact_source(CAPITAL_REVIEW_QUEUE_PATH, inputs.get("capital_review_queue")),
        compact_source(UNIVERSE_PATH, inputs.get("universe")),
        compact_source(WF78_AUTO_TIER_ROUTING_PATH, inputs.get("auto_tier_routing")),
    ]
    if order_card_path:
        source_artifacts.append({"path": order_card_path, "exists": True, "created_at_utc": (order_card or {}).get("created_at_utc"), "status": (order_card or {}).get("status")})

    return {
        "schema_version": 2,
        "artifact_type": "wf77_ticker_intelligence_card",
        "generated_at_utc": utc_now_iso(),
        "ticker": ticker,
        "review_only": True,
        "instrument_type": instrument_type,
        "universe_metadata": universe_entry or {
            "status": "missing_universe_metadata",
            "source": str(UNIVERSE_PATH.relative_to(WORKSPACE)),
            "note": "WF78 universe metadata missing for ticker; card remains review-only and source-open required.",
        },
        "wf78_auto_tier_routing": auto_tier_entry or {
            "status": "missing_auto_tier_routing",
            "source": str(WF78_AUTO_TIER_ROUTING_PATH.relative_to(WORKSPACE)),
            "note": "Auto-tier routing metadata missing; legacy universe metadata remains available but promotion/deployment claims require source-open review.",
        },
        "latest_known_price": price_band_stop["latest_known_price"],
        "price_band_stop": price_band_stop,
        "entry_stop_reference_metadata": entry_stop_reference_metadata,
        "thesis_bull_bear_entry_context": {
            "thesis": "Card-level thesis synthesis requires source-open review of fundamentals, official captures, sector context, and technical posture before final answer.",
            "bull_case_inputs": ["latest_earnings_performance", "key_financial_metrics", "official_capture_developments_orders_backlog", "current_sector_performance", "technical_posture"],
            "bear_case_inputs": ["risk_register", "missing_or_stale_evidence", "valuation", "price_band_stop"],
            "entry_context": price_band_stop,
            "source_open_required": True,
        },
        "latest_earnings_performance": build_latest_earnings_performance(fundamentals, official_claims, instrument_type),
        "key_financial_metrics": build_key_financial_metrics(fundamentals, instrument_type),
        "valuation": metric(fundamentals or {}, ["valuation_context", "market_cap", "enterprise_value", "trailing_pe", "forward_pe", "fcf_yield_pct", "earnings_yield_pct", "price_to_sales", "price_to_book", "ev_to_ebitda_proxy", "ev_to_fcf_proxy"]),
        "official_fundamentals": metric(fundamentals or {}, ["source", "source_tier", "period_type", "period_end", "comparison_period_end", "revenue", "revenue_yoy_pct", "net_income", "net_income_yoy_pct", "diluted_eps", "eps_yoy_pct", "gross_margin_pct", "operating_margin_pct", "net_margin_pct", "operating_cash_flow", "free_cash_flow", "free_cash_flow_yoy_pct", "fcf_per_share", "fcf_per_share_yoy_pct", "cash_and_equivalents", "total_debt", "net_debt", "debt_to_annualized_ebitda", "roic_proxy_pct", "data_quality"]),
        "fundamental_reconciliation": {
            "sec_status": ((fundamentals or {}).get("sec_reconciliation") or {}).get("status"),
            "sec_source_url": ((fundamentals or {}).get("sec_reconciliation") or {}).get("source_url"),
            "company_ir_status": ((fundamentals or {}).get("company_ir_reconciliation") or {}).get("status"),
            "company_ir_source_url": ((fundamentals or {}).get("company_ir_reconciliation") or {}).get("source_url"),
            "quality_notes": (fundamentals or {}).get("quality_notes") or [],
        },
        "analyst_consensus_ratings_targets": analyst_entry or {
            "status": "missing_manual_required",
            "consensus_rating": None,
            "buy_hold_sell_counts": None,
            "average_target": None,
            "median_target": None,
            "high_target": None,
            "low_target": None,
            "implied_upside_downside": None,
            "note": "Analyst consensus layer is WF77 Phase 3; no value is fabricated here.",
        },
        "competitive_moat": {
            "status": "not_yet_structured_source_open_required",
            "summary": None,
            "evidence": [],
            "note": "Ticker cards now reserve this field; populate only from sourced thesis/official/research artifacts, not model inference.",
        },
        "recent_developments": claim_summary(official_claims.get("acquisition_debt_notes")),
        "orders_backlog_book_to_bill": claim_summary(official_claims.get("orders_backlog")),
        "official_capture_developments_orders_backlog": {
            "management_explanation": claim_summary(official_claims.get("management_explanation")),
            "acquisition_debt_notes": claim_summary(official_claims.get("acquisition_debt_notes")),
            "orders_backlog": claim_summary(official_claims.get("orders_backlog")),
            "source_open_required": True,
        },
        "current_sector_performance": {
            "status": "available" if sector_entry else "missing",
            "sector": (fundamentals or {}).get("sector"),
            "sector_proxy_ticker": (sector_entry or {}).get("ticker"),
            "as_of": (sector_entry or {}).get("as_of"),
            "relative_strength_vs_spy": (sector_entry or {}).get("relative_strength_vs_spy"),
            "sector_returns_pct": (sector_entry or {}).get("sector_returns_pct"),
            "spy_returns_pct": (sector_entry or {}).get("spy_returns_pct"),
            "relative_labels": (sector_entry or {}).get("relative_labels"),
            "leadership_status": (sector_entry or {}).get("leadership_status"),
            "portfolio_exposure": (sector_entry or {}).get("portfolio_exposure"),
            "underexposed": (sector_entry or {}).get("underexposed"),
            "owner_gated_next_review_action": (sector_entry or {}).get("owner_gated_next_review_action"),
        },
        "etf_or_macro_proxy_profile": build_etf_profile(fundamentals, sector_entry),
        "catalyst_earnings_state": {
            "workflow_state": legacy_state((fundamentals or {}), "workflow_state") or legacy_state((deployment_entry or {}), "workflow_state"),
            "surface_state": legacy_state((deployment_entry or {}), "surface_state"),
            "days_to_earnings": (deployment_entry or {}).get("days_to_earnings"),
            "earnings_date_confirmed": (deployment_entry or {}).get("earnings_date_confirmed"),
            "last_earnings_date": (deployment_entry or {}).get("last_earnings_date"),
            "post_earnings_review_confirmed": (deployment_entry or {}).get("post_earnings_review_confirmed"),
        },
        "technical_posture": {
            "band_status": price_band_stop["band_status"],
            "latest_close": (tech_entry or {}).get("close"),
            "ma20": (tech_entry or {}).get("ma20"),
            "ma50": (tech_entry or {}).get("ma50"),
            "ma200": (tech_entry or {}).get("ma200"),
            "ma_posture": (tech_entry or {}).get("ma_posture"),
            "above_ma20": (tech_entry or {}).get("above_ma20"),
            "above_ma50": (tech_entry or {}).get("above_ma50"),
            "above_ma200": (tech_entry or {}).get("above_ma200"),
            "data_date": (tech_entry or {}).get("data_date"),
            "deployment_surface_state": legacy_state((deployment_entry or {}), "surface_state"),
            "macro_gate": (deployment_entry or {}).get("macro_gate"),
            "near_earnings_caution": (deployment_entry or {}).get("near_earnings_caution"),
            "why": (deployment_entry or {}).get("why"),
        },
        "portfolio_fit_concentration": {
            "sector": (fundamentals or {}).get("sector"),
            "wf78_tier": (universe_entry or {}).get("tier"),
            "wf78_auto_tier": (auto_tier_entry or {}).get("auto_tier"),
            "wf78_auto_state": (auto_tier_entry or {}).get("auto_state"),
            "wf78_monitoring_role": (universe_entry or {}).get("monitoring_role"),
            "wf78_decision_grade_eligible": (universe_entry or {}).get("decision_grade_eligible"),
            "wf78_promotion_required_before_action": (universe_entry or {}).get("promotion_required_before_action"),
            "coverage_tier": (fundamentals or {}).get("coverage_tier"),
            "portfolio_role": (fundamentals or {}).get("portfolio_role"),
            "coverage_lane": (fundamentals or {}).get("coverage_lane"),
            "readiness_tier": (readiness or {}).get("tier"),
            "recommended_starter_notional": (readiness or {}).get("recommended_starter_notional"),
            "recommended_target_notional": (readiness or {}).get("recommended_target_notional"),
            "decision_note": (readiness or {}).get("decision_note"),
            "prepared_order_card_path": order_card_path,
        },
        "capital_allocation_quality": {
            "quality": (fundamentals or {}).get("capital_allocation_quality"),
            "anomalies": (fundamentals or {}).get("capital_allocation_anomalies") or [],
            "notes": (fundamentals or {}).get("capital_allocation_notes") or [],
        },
        "risk_register": build_risk_register(fundamentals, readiness, deployment_entry, missing),
        "recommendation_support": recommendation,
        "missing_or_stale_evidence": missing,
        "source_artifacts": source_artifacts,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def apply_post_close_price_overlay(card: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    ticker = str(card.get("ticker") or "").upper()
    row = post_close_quote_row(inputs, ticker)
    if not row:
        return card
    pbs = card.get("price_band_stop") if isinstance(card.get("price_band_stop"), dict) else {}
    close = row.get("close")
    band_status = classify_band_status(
        close,
        pbs.get("entry_band_low"),
        pbs.get("entry_band_high"),
        pbs.get("stop_or_invalidation"),
    ) or pbs.get("band_status")
    pbs = {
        **pbs,
        "latest_known_price": close,
        "price_source": "tmp/post-close-final-quote-ledger.json",
        "band_status": band_status,
        "post_close_final_quote": {
            "market_date": row.get("market_date"),
            "retrieved_at_utc": row.get("retrieved_at_utc"),
            "source": row.get("source"),
            "review_only": True,
            "execution_freshness_approved": False,
        },
    }
    card["latest_known_price"] = close
    card["price_band_stop"] = pbs
    entry_context = (card.get("thesis_bull_bear_entry_context") or {}).get("entry_context")
    if isinstance(entry_context, dict):
        entry_context.update(pbs)
    technical_posture = card.get("technical_posture")
    if isinstance(technical_posture, dict):
        technical_posture["band_status"] = band_status
    return card


def uses_current_wf84_band_precedence(card: dict[str, Any]) -> bool:
    pbs = card.get("price_band_stop") if isinstance(card.get("price_band_stop"), dict) else {}
    source_text = json.dumps({
        "band_source": pbs.get("band_source"),
        "stop_source": pbs.get("stop_source"),
    }, sort_keys=True)
    return "tmp/finance-decision-sync-spine.json" in source_text or "tmp/wf78-capital-review-queue.json" in source_text


def validate_card(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "ticker",
        "latest_known_price",
        "price_band_stop",
        "thesis_bull_bear_entry_context",
        "latest_earnings_performance",
        "key_financial_metrics",
        "valuation",
        "official_fundamentals",
        "universe_metadata",
        "analyst_consensus_ratings_targets",
        "competitive_moat",
        "recent_developments",
        "orders_backlog_book_to_bill",
        "current_sector_performance",
        "risk_register",
        "recommendation_support",
        "missing_or_stale_evidence",
        "source_artifacts",
        "authority_boundary",
    ]
    for key in required:
        if key not in card:
            errors.append(f"missing required key: {key}")
    authority = card.get("authority_boundary") or {}
    for key in ["live_trade_allowed", "paper_order_execution_allowed", "owner_approval_inferred", "portfolio_mutation_allowed"]:
        if authority.get(key) is not False:
            errors.append(f"authority boundary widened or missing false flag: {key}")
    analyst = card.get("analyst_consensus_ratings_targets") or {}
    if analyst.get("status") == "missing_manual_required" and analyst.get("average_target") is not None:
        errors.append("analyst targets must remain null when status is missing_manual_required")
    if card.get("competitive_moat", {}).get("status") != "not_yet_structured_source_open_required" and not card.get("competitive_moat", {}).get("evidence"):
        errors.append("competitive moat claims require structured evidence")
    if not card.get("universe_metadata") or card.get("universe_metadata", {}).get("status") == "missing_universe_metadata":
        errors.append("universe_metadata must be present from data/finance/universe-v1.json")
    if not isinstance(card.get("risk_register"), list) or not card.get("risk_register"):
        errors.append("risk_register must be a non-empty list")
    technical_close = (card.get("technical_posture") or {}).get("latest_close")
    if technical_close is not None and card.get("latest_known_price") is None:
        errors.append("latest_known_price must fall back to technical_posture.latest_close when readiness/deployment price is absent")
    return errors


def tickers_from_coverage(path: Path = COVERAGE_PATH) -> list[str]:
    """Return canonical tickers indexed by the WF77 coverage registry."""
    data = load_json(path, {})
    tickers = sorted((data.get("ticker_coverage") or {}).keys()) if isinstance(data, dict) else []
    return [str(ticker).upper() for ticker in tickers]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF77 review-only ticker intelligence cards.")
    parser.add_argument("--ticker", action="append", dest="tickers", help="Ticker to build. Can be passed multiple times.")
    parser.add_argument("--all-from-coverage", action="store_true", help="Build cards for every ticker in tmp/finance-data-coverage-current.json ticker_coverage.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory for <TICKER>.current.json cards.")
    parser.add_argument("--validate-only", action="store_true", help="Build in memory and validate without writing files.")
    parser.add_argument("--summary-output", type=Path, default=None, help="Optional JSON path for the build/validation summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fundamentals = load_json(FUNDAMENTALS_PATH, {})
    inputs = {
        "fundamentals": fundamentals,
        "fundamental_index": index_fundamentals(fundamentals),
        "deployment_surface": load_json(DEPLOYMENT_SURFACE_PATH, {}),
        "tuesday_readiness": load_json(POSITION_SIZING_READINESS_PATH, {}),
        "analyst_consensus": load_json(ANALYST_CONSENSUS_PATH, {}),
        "universe": load_json(UNIVERSE_PATH, {}),
        "universe_index": index_universe(load_json(UNIVERSE_PATH, {})),
        "auto_tier_routing": load_json(WF78_AUTO_TIER_ROUTING_PATH, {}),
        "auto_tier_index": index_rows_by_ticker(load_json(WF78_AUTO_TIER_ROUTING_PATH, {})),
        "official_earnings_bridge": load_json(OFFICIAL_EARNINGS_BRIDGE_PATH, {}),
        "sector_expansion_board": load_json(SECTOR_EXPANSION_BOARD_PATH, {}),
        "technical_refresh": load_json(TECHNICAL_REFRESH_PATH, {}),
        "portfolio_config": load_json(PORTFOLIO_CONFIG_PATH, {}),
        "post_close_final_quote_ledger": load_json(POST_CLOSE_FINAL_QUOTE_LEDGER_PATH, {}),
        "post_close_final_quote_index": index_rows_by_ticker(load_json(POST_CLOSE_FINAL_QUOTE_LEDGER_PATH, {})),
        "decision_sync_spine": load_json(DECISION_SYNC_SPINE_PATH, {}),
        "decision_spine_index": index_rows_by_ticker(load_json(DECISION_SYNC_SPINE_PATH, {})),
        "capital_review_queue": load_json(CAPITAL_REVIEW_QUEUE_PATH, {}),
        "capital_queue_index": index_rows_by_ticker(load_json(CAPITAL_REVIEW_QUEUE_PATH, {})),
    }
    if args.all_from_coverage:
        coverage_tickers = tickers_from_coverage()
        tickers = coverage_tickers
        if args.tickers:
            requested = {ticker.upper() for ticker in args.tickers}
            tickers = [ticker for ticker in tickers if ticker in requested]
    else:
        tickers = [t.upper() for t in (args.tickers or ["CME", "PH"])]
    out_dir = Path(args.out_dir)
    if not args.validate_only:
        out_dir.mkdir(parents=True, exist_ok=True)
    before_pilot_cards: dict[str, dict[str, Any]] = {}
    requested_pilot = set(PILOT_TICKERS).issubset(set(tickers))
    if requested_pilot and not args.validate_only:
        for ticker in PILOT_TICKERS:
            existing_path = out_dir / f"{ticker}.current.json"
            if existing_path.exists():
                before_pilot_cards[ticker] = apply_post_close_price_overlay(load_json(existing_path, {}), inputs)

    summary = {
        "schema_version": 1,
        "artifact_type": "wf77_ticker_card_registry_build_summary",
        "generated_at_utc": utc_now_iso(),
        "status": "ok",
        "mode": "all_from_coverage" if args.all_from_coverage else "explicit_or_default_tickers",
        "validate_only": bool(args.validate_only),
        "requested_ticker_count": len(tickers),
        "cards": [],
        "errors": [],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    after_pilot_cards: dict[str, dict[str, Any]] = {}
    pilot_band_precedence_refresh: set[str] = set()
    if args.all_from_coverage and not tickers:
        summary["status"] = "error"
        summary["errors"].append({"scope": "coverage_registry", "errors": ["No tickers found in tmp/finance-data-coverage-current.json ticker_coverage"]})
    for ticker in tickers:
        card = build_card(ticker, inputs)
        card = apply_approved_wf78_card_field_repair(card)
        card = apply_post_close_price_overlay(card, inputs)
        if requested_pilot and ticker in before_pilot_cards:
            if uses_current_wf84_band_precedence(card):
                pilot_band_precedence_refresh.add(ticker)
            else:
                additive_card = dict(before_pilot_cards[ticker])
                additive_card["entry_stop_reference_metadata"] = card["entry_stop_reference_metadata"]
                additive_card["generated_at_utc"] = card["generated_at_utc"]
                additive_card = apply_post_close_price_overlay(additive_card, inputs)
                card = additive_card
        if ticker in PILOT_TICKERS:
            after_pilot_cards[ticker] = card
        errors = validate_card(card)
        rel_path = str((out_dir / f"{ticker}.current.json").relative_to(WORKSPACE)) if out_dir.is_absolute() and out_dir.is_relative_to(WORKSPACE) else str(out_dir / f"{ticker}.current.json")
        if errors:
            summary["status"] = "error"
            summary["errors"].append({"ticker": ticker, "errors": errors})
            continue
        if not args.validate_only:
            (out_dir / f"{ticker}.current.json").write_text(json.dumps(card, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        summary["cards"].append({"ticker": ticker, "path": rel_path, "recommendation_support": card["recommendation_support"]["posture"], "missing_or_stale_count": len(card["missing_or_stale_evidence"])})

    if requested_pilot and not args.validate_only and pilot_band_precedence_refresh:
        summary["wf72_entry_stop_no_drift_pilot"] = {
            "status": "skipped_due_to_current_wf84_band_precedence_refresh",
            "path": str(NO_DRIFT_PILOT_JSON.relative_to(WORKSPACE)).replace("\\", "/"),
            "tickers": sorted(pilot_band_precedence_refresh),
            "authority": "derived_card_refresh_only_no_canon_or_portfolio_mutation",
        }
    elif requested_pilot and not args.validate_only and len(before_pilot_cards) == len(PILOT_TICKERS) and len(after_pilot_cards) == len(PILOT_TICKERS):
        pilot = write_no_drift_pilot(before_pilot_cards, after_pilot_cards)
        summary["wf72_entry_stop_no_drift_pilot"] = {
            "status": pilot.get("status"),
            "path": str(NO_DRIFT_PILOT_JSON.relative_to(WORKSPACE)).replace("\\", "/"),
            "tickers": list(PILOT_TICKERS),
        }
        if pilot.get("status") != "no_drift":
            summary["status"] = "error"
            summary["errors"].append({"scope": "wf72_entry_stop_no_drift_pilot", "errors": ["price/band/stop or posture drift detected"]})
    elif requested_pilot and not args.validate_only:
        summary["wf72_entry_stop_no_drift_pilot"] = {
            "status": "skipped_missing_before_or_after_cards",
            "path": str(NO_DRIFT_PILOT_JSON.relative_to(WORKSPACE)).replace("\\", "/"),
            "tickers": list(PILOT_TICKERS),
        }

    summary["card_count"] = len(summary["cards"])
    summary["error_count"] = len(summary["errors"])
    if args.summary_output:
        output_path = args.summary_output if args.summary_output.is_absolute() else WORKSPACE / args.summary_output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
