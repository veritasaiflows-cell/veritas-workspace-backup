#!/usr/bin/env python3
"""Build the review-only finance data coverage registry for WF77 Phase 1.

The registry answers recurring routing questions without broad workspace scans:
- do we collect a data family?
- which tickers lack it?
- is the source artifact present/fresh/indexed?

This is a derived review/routing surface only. It is not canon, approval,
portfolio mutation authority, paper/live trading authority, or account-action
permission.
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

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT = TMP / "finance-data-coverage-current.json"
DEFAULT_CONTRACT = TMP / "finance-intelligence-router-contract-2026-05-26.json"
UNIVERSE_PATH = ROOT / "data" / "finance" / "universe-v1.json"
SCHEMA_VERSION = 1
CONTRACT_SCHEMA_VERSION = 1
DEFAULT_STALE_AFTER_HOURS = 36

REVIEW_ONLY_AUTHORITY = {
    "posture": "derived_review_only_routing_registry_not_canon_not_approval_not_apply_authority",
    "canonical_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_this_registry": False,
    "paper_order_cancel_allowed_by_this_registry": False,
}

SOURCE_ARTIFACTS: dict[str, dict[str, Any]] = {
    "fundamental_metrics_current": {
        "path": TMP / "fundamental-metrics-current.json",
        "families": [
            "valuation_multiples",
            "official_fundamentals",
            "revenue_growth_margins_fcf_debt",
            "source_freshness",
            "authority_guardrails",
        ],
        "stale_after_hours": 36,
    },
    "deployment_readiness_surface": {
        "path": TMP / "deployment-readiness-surface.json",
        "families": [
            "price_band_stop",
            "technical_posture",
            "catalyst_earnings_state",
            "deployment_readiness",
            "source_freshness",
            "authority_guardrails",
        ],
        "stale_after_hours": 18,
    },
    "position_sizing_readiness_current": {
        "path": TMP / "position-sizing-readiness-current.json",
        "families": [
            "price_band_stop",
            "technical_posture",
            "deployment_readiness",
            "portfolio_fit_concentration",
            "recommendation_support",
            "authority_guardrails",
        ],
        "stale_after_hours": 36,
    },
    "ticker_intelligence_cards": {
        "path": TMP / "ticker-intelligence-cards",
        "families": [
            "price_band_stop",
            "technical_posture",
            "catalyst_earnings_state",
            "deployment_readiness",
            "portfolio_fit_concentration",
            "recommendation_support",
            "analyst_consensus",
            "analyst_ratings",
            "analyst_price_targets",
            "latest_earnings_performance",
            "key_financial_metrics",
            "risk_register",
            "competitive_moat",
            "recent_developments",
            "orders_backlog_book_to_bill",
            "current_sector_performance",
            "thesis_bull_bear_entry_context",
            "authority_guardrails",
        ],
        "stale_after_hours": 36,
    },
    "official_earnings_bridge": {
        "path": TMP / "official-earnings-bridge.json",
        "families": ["latest_earnings_performance", "recent_developments", "orders_backlog_book_to_bill", "source_freshness", "proof_provenance"],
        "stale_after_hours": 72,
    },
    "sector_expansion_board": {
        "path": TMP / "sector-expansion-board.json",
        "families": ["current_sector_performance", "source_freshness", "proof_provenance"],
        "stale_after_hours": 36,
    },
    "technical_refresh": {
        "path": TMP / "technical-refresh.json",
        "families": ["technical_posture", "price_band_stop", "source_freshness"],
        "stale_after_hours": 18,
    },
    "current_window_artifacts": {
        "path": TMP / "current-window-artifacts.json",
        "families": ["source_freshness", "proof_provenance", "authority_guardrails"],
        "stale_after_hours": 36,
    },
    "market_state": {
        "path": TMP / "market-state.json",
        "families": ["source_freshness", "macro_market_context"],
        "stale_after_hours": 18,
    },
    "capital_deployment_recommendations": {
        "path": TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json",
        "families": [
            "technical_posture",
            "catalyst_earnings_state",
            "portfolio_fit_concentration",
            "recommendation_support",
            "source_freshness",
            "authority_guardrails",
        ],
        "stale_after_hours": 36,
    },
    "capital_deployment_recommendation_validation": {
        "path": TMP / "capital-deployment-recommendation-validation.json",
        "families": ["proof_provenance", "authority_guardrails", "source_freshness"],
        "stale_after_hours": 36,
    },
    "analyst_consensus_current": {
        "path": TMP / "analyst-consensus-current.json",
        "families": ["analyst_consensus", "analyst_ratings", "analyst_price_targets", "source_freshness"],
        "stale_after_hours": 72,
        "future_expected": True,
    },
}

FAMILY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "valuation_multiples": {
        "label": "Valuation multiples",
        "question_aliases": ["valuation", "multiples", "pe", "p/e", "ev/ebitda", "fcf yield"],
        "per_ticker": True,
        "required_sources": ["fundamental_metrics_current"],
        "fields_any": ["trailing_pe", "forward_pe", "price_to_sales", "price_to_book", "ev_to_ebitda_proxy", "ev_to_fcf_proxy", "fcf_yield_pct", "earnings_yield_pct"],
        "source_open_required_for_claims": True,
    },
    "official_fundamentals": {
        "label": "Official/structured fundamentals",
        "question_aliases": ["fundamentals", "official fundamentals", "sec", "company ir"],
        "per_ticker": True,
        "required_sources": ["fundamental_metrics_current"],
        "fields_any": ["revenue", "net_income", "diluted_eps", "operating_income", "sec_reconciliation", "company_ir_reconciliation"],
        "source_open_required_for_claims": True,
        "notes": ["Current artifact may include secondary aggregator fields plus SEC/IR reconciliation status; open source row before calling evidence official."],
    },
    "revenue_growth_margins_fcf_debt": {
        "label": "Revenue/growth/margins/FCF/debt",
        "question_aliases": ["revenue", "growth", "margin", "fcf", "free cash flow", "debt", "leverage"],
        "per_ticker": True,
        "required_sources": ["fundamental_metrics_current"],
        "fields_any": ["revenue_yoy_pct", "gross_margin_pct", "operating_margin_pct", "free_cash_flow", "free_cash_flow_yoy_pct", "net_debt", "total_debt", "debt_to_annualized_ebitda"],
        "source_open_required_for_claims": True,
    },
    "price_band_stop": {
        "label": "Price/band/stop",
        "question_aliases": ["price", "entry band", "band", "stop", "invalidation", "no chase"],
        "per_ticker": True,
        "required_sources": ["deployment_readiness_surface", "position_sizing_readiness_current", "ticker_intelligence_cards"],
        "fields_any": ["close", "close_reference", "latest_known_price", "band_position", "band_status", "band_low", "band_high", "entry_band_low", "entry_band_high", "stop", "stop_or_invalidation", "trigger", "band_stale"],
        "source_open_required_for_claims": True,
    },
    "technical_posture": {
        "label": "Technical posture",
        "question_aliases": ["technical", "chart", "setup", "trend"],
        "per_ticker": True,
        "required_sources": ["deployment_readiness_surface", "capital_deployment_recommendations", "position_sizing_readiness_current", "ticker_intelligence_cards"],
        "fields_any": ["technical_gate", "technical_posture", "band_position", "surface_state", "machine_state", "band_status", "state", "readiness"],
        "source_open_required_for_claims": True,
    },
    "catalyst_earnings_state": {
        "label": "Catalyst/earnings state",
        "question_aliases": ["catalyst", "earnings", "next earnings", "post earnings"],
        "per_ticker": True,
        "required_sources": ["deployment_readiness_surface", "capital_deployment_recommendations", "ticker_intelligence_cards"],
        "fields_any": ["days_to_earnings", "next_earnings_date", "last_earnings_date", "post_earnings_review_confirmed", "catalyst_gate", "official_earnings_gate", "catalyst_earnings_state"],
        "source_open_required_for_claims": True,
    },
    "deployment_readiness": {
        "label": "Deployment readiness",
        "question_aliases": ["ready", "readiness", "deployable", "promotion review", "watch"],
        "per_ticker": True,
        "required_sources": ["deployment_readiness_surface", "position_sizing_readiness_current", "ticker_intelligence_cards"],
        "fields_any": ["surface_state", "action_state", "workflow_state", "why", "readiness", "state", "recommendation_support"],
        "source_open_required_for_claims": True,
    },
    "portfolio_fit_concentration": {
        "label": "Portfolio fit/concentration",
        "question_aliases": ["portfolio fit", "concentration", "sector", "sizing", "correlation"],
        "per_ticker": True,
        "required_sources": ["capital_deployment_recommendations", "position_sizing_readiness_current", "ticker_intelligence_cards"],
        "fields_any": ["concentration_check", "risk_sizing_gate", "sector_exposure_before_after", "correlated_sleeve_exposure_before_after", "current_portfolio_model", "proposed_portfolio_model", "recommended_starter_notional", "recommended_target_notional", "portfolio_fit_concentration"],
        "source_open_required_for_claims": True,
    },
    "source_freshness": {
        "label": "Source freshness",
        "question_aliases": ["fresh", "stale", "updated", "timestamp", "indexed"],
        "per_ticker": False,
        "required_sources": list(SOURCE_ARTIFACTS.keys()),
        "fields_any": ["generated_at_utc", "file_mtime_utc", "status"],
        "source_open_required_for_claims": False,
    },
    "analyst_consensus": {
        "label": "Analyst consensus",
        "question_aliases": ["analyst consensus", "consensus"],
        "per_ticker": True,
        "required_sources": ["analyst_consensus_current"],
        "fields_any": ["consensus_rating", "buy_count", "hold_count", "sell_count"],
        "source_open_required_for_claims": True,
        "expected_status": "future_expected_missing_until_provider_or_manual_artifact_exists",
    },
    "analyst_ratings": {
        "label": "Analyst ratings",
        "question_aliases": ["analyst ratings", "ratings", "buy hold sell"],
        "per_ticker": True,
        "required_sources": ["analyst_consensus_current"],
        "fields_any": ["ratings", "buy_count", "hold_count", "sell_count", "rating_changes"],
        "source_open_required_for_claims": True,
        "expected_status": "future_expected_missing_until_provider_or_manual_artifact_exists",
    },
    "analyst_price_targets": {
        "label": "Analyst price targets",
        "question_aliases": ["price target", "target price", "analyst target", "upside"],
        "per_ticker": True,
        "required_sources": ["analyst_consensus_current"],
        "fields_any": ["average_target", "median_target", "high_target", "low_target", "implied_upside_downside_pct"],
        "source_open_required_for_claims": True,
        "expected_status": "future_expected_missing_until_provider_or_manual_artifact_exists",
    },
    "latest_earnings_performance": {
        "label": "Latest earnings performance",
        "question_aliases": ["last earnings", "latest earnings", "earnings performance", "quarter performance"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["latest_earnings_performance", "official_adjusted_eps", "official_growth_bridge", "official_guidance", "management_explanation", "revenue_yoy_pct", "eps_yoy_pct"],
        "source_open_required_for_claims": True,
    },
    "key_financial_metrics": {
        "label": "Key financial metrics",
        "question_aliases": ["key metrics", "financial metrics", "margins", "cash flow", "debt", "growth"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["key_financial_metrics", "growth", "profitability", "cash_flow", "balance_sheet", "valuation", "capital_returns"],
        "source_open_required_for_claims": True,
    },
    "risk_register": {
        "label": "Key risks / risk register",
        "question_aliases": ["risk", "risks", "bear risk", "downside", "risk register"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["risk_register", "missing_or_stale_evidence"],
        "source_open_required_for_claims": True,
    },
    "competitive_moat": {
        "label": "Competitive moat",
        "question_aliases": ["moat", "competitive moat", "competitive advantage", "business quality"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["competitive_moat"],
        "source_open_required_for_claims": True,
        "notes": ["Current card field is structured but may be source-open/manual-required until sourced thesis artifacts populate evidence."],
    },
    "recent_developments": {
        "label": "Recent developments / acquisition / product notes",
        "question_aliases": ["recent developments", "developments", "acquisitions", "business development", "news"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["recent_developments", "official_capture_developments_orders_backlog", "acquisition_debt_notes", "management_explanation"],
        "source_open_required_for_claims": True,
    },
    "orders_backlog_book_to_bill": {
        "label": "Orders / backlog / book-to-bill",
        "question_aliases": ["orders", "backlog", "book to bill", "book-to-bill", "demand KPI"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["orders_backlog_book_to_bill", "orders_backlog"],
        "source_open_required_for_claims": True,
    },
    "current_sector_performance": {
        "label": "Current sector performance",
        "question_aliases": ["sector performance", "sector", "relative strength", "leadership", "industry performance"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["current_sector_performance", "relative_strength_vs_spy", "sector_returns_pct", "relative_labels", "leadership_status"],
        "source_open_required_for_claims": True,
    },
    "thesis_bull_bear_entry_context": {
        "label": "Thesis / bull / bear / entry context",
        "question_aliases": ["thesis", "bull case", "bear case", "entry context", "full picture"],
        "per_ticker": True,
        "required_sources": ["ticker_intelligence_cards"],
        "fields_any": ["thesis_bull_bear_entry_context", "bull_case_inputs", "bear_case_inputs", "entry_context"],
        "source_open_required_for_claims": True,
    },
    "authority_guardrails": {
        "label": "Authority/guardrails",
        "question_aliases": ["authority", "approval", "guardrail", "paper", "live", "trade", "apply"],
        "per_ticker": False,
        "required_sources": ["current_window_artifacts", "capital_deployment_recommendations", "capital_deployment_recommendation_validation", "fundamental_metrics_current"],
        "fields_any": ["authority", "owner_approval_granted", "trade_execution_allowed", "portfolio_mutation_allowed"],
        "source_open_required_for_claims": True,
    },
    "proof_provenance": {
        "label": "Proof/provenance",
        "question_aliases": ["proof", "provenance", "source artifact", "validator"],
        "per_ticker": False,
        "required_sources": ["current_window_artifacts", "capital_deployment_recommendation_validation"],
        "fields_any": ["artifacts", "findings", "status"],
        "source_open_required_for_claims": True,
    },
    "recommendation_support": {
        "label": "Recommendation support context",
        "question_aliases": ["recommendation", "supportable", "buy", "paper buy", "deploy", "approval-ready"],
        "per_ticker": True,
        "required_sources": ["capital_deployment_recommendations", "deployment_readiness_surface", "position_sizing_readiness_current", "ticker_intelligence_cards"],
        "fields_any": ["proposed_state", "recommendation_support", "decision_rationale", "risk_rule_check", "technical_gate", "catalyst_gate", "readiness", "decision_note"],
        "source_open_required_for_claims": True,
    },
    "macro_market_context": {
        "label": "Macro/market context",
        "question_aliases": ["market", "macro", "vix", "rates", "dxy", "oil"],
        "per_ticker": False,
        "required_sources": ["market_state"],
        "fields_any": ["data", "macro_freshness", "warnings"],
        "source_open_required_for_claims": True,
    },
}

QUESTION_CLASSES = {
    "coverage": "Do we collect/index a data family? Route to finance-data-coverage-current.json family_registry first.",
    "missing_evidence": "Which tickers or families lack required evidence? Route to missing_by_family/missing_by_ticker first.",
    "freshness": "Is a source/data family fresh? Route to source_artifacts and family_registry freshness fields first.",
    "proof_provenance": "Where is proof? Route to current-window/artifact index, then open exact source artifact.",
    "ticker_intelligence": "What do we know about a ticker? Route to ticker_coverage now; later ticker cards.",
    "recommendation_support": "Is guidance supportable? Route to recommendation_support family, then source-open exact artifacts.",
    "authority_guardrail": "Can anything be applied/traded/papered? Route to authority_boundary and exact guard artifacts; registry never grants authority.",
    "workflow_runtime_status": "What workflow/status owns this? Route to WF77 continuity and generated registry proof.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def generated_at(data: dict[str, Any]) -> str | None:
    value = data.get("generated_at_utc") or data.get("generated_at")
    return str(value) if value else None


def hours_old(value: str | None, now: datetime) -> float | None:
    dt = parse_utc(value)
    if dt is None:
        return None
    return round((now - dt).total_seconds() / 3600, 2)


def source_state(source_id: str, spec: dict[str, Any], data: dict[str, Any], now: datetime) -> dict[str, Any]:
    path = spec["path"]
    exists = path.exists()
    gen = generated_at(data) if exists else None
    mtime = None
    if exists:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    reference_time = gen or mtime
    age = hours_old(reference_time, now)
    stale_after = int(spec.get("stale_after_hours") or DEFAULT_STALE_AFTER_HOURS)
    artifact_status = str(data.get("status") or data.get("consumer_posture") or "").lower() if exists else ""
    placeholder_missing = any(token in artifact_status for token in ["placeholder", "manual_required", "missing_provider"])
    if not exists:
        status = "missing_expected" if spec.get("future_expected") else "missing"
    elif placeholder_missing:
        status = "placeholder_manual_required"
    elif age is None:
        status = "present_unknown_timestamp"
    elif age > stale_after:
        status = "stale"
    else:
        status = "fresh"
    usable_for_values = exists and status not in {"missing", "missing_expected", "placeholder_manual_required"}
    return {
        "source_id": source_id,
        "path": rel(path),
        "exists": exists,
        "status": status,
        "usable_for_values": usable_for_values,
        "indexed_by_registry": exists,
        "generated_at_utc": gen,
        "file_mtime_utc": mtime,
        "age_hours": age,
        "stale_after_hours": stale_after,
        "families": spec.get("families", []),
        "future_expected": bool(spec.get("future_expected", False)),
    }


def first_present(row: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if row.get(field) not in (None, "", [], {})]


def index_fundamentals(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(data.get("rows")):
        if isinstance(row, dict) and row.get("ticker"):
            out[str(row["ticker"]).upper()] = row
    return out


def index_deployment(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for group, rows in as_dict(data.get("groups")).items():
        for row in as_list(rows):
            if isinstance(row, dict) and row.get("ticker"):
                item = dict(row)
                item["readiness_group"] = group
                out[str(row["ticker"]).upper()] = item
    return out


def index_capital(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(data.get("proposals")):
        if isinstance(row, dict):
            ticker = row.get("ticker") or row.get("ticker_or_scope")
            if ticker:
                out[str(ticker).upper()] = row
    return out


def index_analyst(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = data.get("rows") or data.get("tickers") or data.get("coverage") or data.get("analyst_consensus")
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, dict):
        for ticker, row in rows.items():
            if isinstance(row, dict):
                item = dict(row)
                item.setdefault("ticker", ticker)
                out[str(ticker).upper()] = item
        return out
    for row in as_list(rows):
        if isinstance(row, dict):
            ticker = row.get("ticker") or row.get("symbol")
            if ticker:
                out[str(ticker).upper()] = row
    return out


def index_tuesday_readiness(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(data.get("candidates")):
        if isinstance(row, dict) and row.get("ticker"):
            out[str(row["ticker"]).upper()] = row
    return out


def load_ticker_cards() -> dict[str, Any]:
    card_dir = TMP / "ticker-intelligence-cards"
    cards: dict[str, Any] = {}
    generated: list[str] = []
    if card_dir.exists():
        for path in sorted(card_dir.glob("*.current.json")):
            data = load_dict(path)
            ticker = str(data.get("ticker") or path.name.split(".")[0]).upper()
            if ticker:
                data.setdefault("_card_path", rel(path))
                cards[ticker] = data
                if data.get("generated_at_utc"):
                    generated.append(str(data.get("generated_at_utc")))
    return {
        "schema_version": 1,
        "generated_at_utc": max(generated) if generated else None,
        "status": "ok" if cards else "missing_expected",
        "cards": cards,
    }


def index_ticker_cards(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for ticker, row in as_dict(data.get("cards")).items():
        if isinstance(row, dict):
            out[str(ticker).upper()] = row
    return out


def source_ticker_indexes(source_data: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "fundamental_metrics_current": index_fundamentals(source_data.get("fundamental_metrics_current", {})),
        "deployment_readiness_surface": index_deployment(source_data.get("deployment_readiness_surface", {})),
        "position_sizing_readiness_current": index_tuesday_readiness(source_data.get("position_sizing_readiness_current", {})),
        "ticker_intelligence_cards": index_ticker_cards(source_data.get("ticker_intelligence_cards", {})),
        "capital_deployment_recommendations": index_capital(source_data.get("capital_deployment_recommendations", {})),
        "analyst_consensus_current": index_analyst(source_data.get("analyst_consensus_current", {})),
    }


def family_row_for_ticker(
    family_id: str,
    family_spec: dict[str, Any],
    ticker: str,
    ticker_indexes: dict[str, dict[str, dict[str, Any]]],
    source_states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required_sources = list(family_spec.get("required_sources", []))
    fields_any = list(family_spec.get("fields_any", []))
    present_sources: list[str] = []
    fields_present: dict[str, list[str]] = {}
    source_paths: list[str] = []
    stale_sources: list[str] = []
    missing_sources: list[str] = []

    for source_id in required_sources:
        state = source_states.get(source_id, {})
        if not state.get("exists"):
            missing_sources.append(source_id)
            continue
        if not state.get("usable_for_values", True):
            missing_sources.append(source_id)
            continue
        if state.get("status") == "stale":
            stale_sources.append(source_id)
        idx = ticker_indexes.get(source_id, {})
        row = idx.get(ticker)
        if row:
            found = first_present(row, fields_any)
            if source_id == "ticker_intelligence_cards":
                for nested_name, nested_value in row.items():
                    if isinstance(nested_value, dict):
                        nested_found = first_present(nested_value, fields_any)
                        found.extend([f"{nested_name}.{field}" for field in nested_found])
            if found:
                present_sources.append(source_id)
                fields_present[source_id] = found
                if source_id == "ticker_intelligence_cards" and isinstance(row.get("_card_path"), str):
                    source_paths.append(str(row.get("_card_path")))
                else:
                    source_paths.append(str(state.get("path")))

    covered = bool(present_sources)
    if covered and stale_sources:
        status = "covered_but_source_stale"
    elif covered:
        status = "covered"
    elif missing_sources and all(s in missing_sources for s in required_sources):
        status = "missing_source_artifact"
    else:
        status = "missing_ticker_or_fields"

    return {
        "covered": covered,
        "status": status,
        "present_sources": sorted(set(present_sources)),
        "missing_required_sources": sorted(set(missing_sources)),
        "stale_sources": sorted(set(stale_sources)),
        "fields_present": fields_present,
        "source_artifacts": sorted(set(source_paths)),
    }


def non_ticker_family_status(family_id: str, family_spec: dict[str, Any], source_states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required_sources = list(family_spec.get("required_sources", []))
    present = [s for s in required_sources if source_states.get(s, {}).get("exists")]
    usable_present = [s for s in present if source_states.get(s, {}).get("usable_for_values", True)]
    missing = [s for s in required_sources if not source_states.get(s, {}).get("exists") or not source_states.get(s, {}).get("usable_for_values", True)]
    stale = [s for s in usable_present if source_states.get(s, {}).get("status") == "stale"]
    future_missing = [s for s in missing if source_states.get(s, {}).get("future_expected")]
    collected = bool(usable_present)
    if collected and stale:
        status = "collected_but_some_sources_stale"
    elif collected and missing:
        status = "partially_collected_some_sources_missing"
    elif collected:
        status = "collected"
    elif future_missing:
        status = "future_expected_missing"
    else:
        status = "missing"
    return {
        "collected": collected,
        "status": status,
        "present_sources": usable_present,
        "missing_required_sources": missing,
        "stale_sources": stale,
        "source_artifacts": [str(source_states[s].get("path")) for s in usable_present],
    }


def build_contract() -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "workflow": "WF77 - Finance Intelligence Coverage and Question Router",
        "posture": "review_only_router_contract",
        "question_classes": QUESTION_CLASSES,
        "source_open_rules": {
            "default": "Use registry/index to route; open exact source artifact or canonical owner note before final finance, readiness, recommendation, authority, or action claims.",
            "coverage_answers": "Registry can answer whether a data family is currently collected/indexed and which tickers appear missing.",
            "finance_claims": "Source-open rule remains mandatory for substantive claims about values, readiness, bands, stops, evidence quality, or recommendations.",
            "authority_claims": "Open exact guardrail/authority artifact; no generated registry/card grants approval, canon mutation, portfolio mutation, live execution, paper execution, or account action authority.",
        },
        "artifact_ownership": {
            "contract": rel(DEFAULT_CONTRACT),
            "coverage_registry": rel(DEFAULT_OUTPUT),
            "future_ticker_cards": "tmp/ticker-intelligence-cards/<TICKER>.current.json",
            "sql_cockpit": "tmp/veritas-artifact-index.sqlite via scripts/artifact_index.py",
            "canonical_owner_notes": "Workspace notes remain canon where applicable; generated registries are derived review surfaces only.",
        },
        "authority_boundary": REVIEW_ONLY_AUTHORITY,
        "acceptance_gates": [
            "Contract JSON parses and lists all initial question classes.",
            "Coverage registry JSON parses and lists initial data families.",
            "Registry answers do-we-collect, missing-by-ticker, and indexed/fresh status without broad workspace search.",
            "Analyst consensus/ratings/targets are explicit future/missing when provider artifact is absent; values are not fabricated.",
            "Source-open requirement and authority stop lines remain visible in contract and registry.",
            "No registry/card field widens canon, portfolio, cash/risk/sizing, live, paper, brokerage/account, money movement, or owner-approval authority.",
        ],
        "initial_data_families": sorted(FAMILY_DEFINITIONS.keys()),
        "initial_source_artifacts": {source_id: rel(spec["path"]) for source_id, spec in SOURCE_ARTIFACTS.items()},
    }


def build_registry() -> dict[str, Any]:
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    source_data = {source_id: load_dict(spec["path"]) for source_id, spec in SOURCE_ARTIFACTS.items()}
    source_data["ticker_intelligence_cards"] = load_ticker_cards()
    universe = load_dict(UNIVERSE_PATH)
    universe_entries = {
        str(row.get("ticker", "")).upper(): row
        for row in universe.get("entries", [])
        if isinstance(row, dict) and row.get("ticker")
    }
    source_states = {source_id: source_state(source_id, spec, source_data[source_id], now_dt) for source_id, spec in SOURCE_ARTIFACTS.items()}
    ticker_indexes = source_ticker_indexes(source_data)
    tickers = sorted(set().union(*(set(idx.keys()) for idx in ticker_indexes.values())) | set(universe_entries.keys()))

    family_registry: dict[str, Any] = {}
    ticker_coverage: dict[str, Any] = {
        ticker: {
            "ticker": ticker,
            "universe": universe_entries.get(ticker),
            "families": {},
            "missing_families": [],
            "stale_families": [],
        }
        for ticker in tickers
    }
    missing_by_family: dict[str, list[str]] = {}
    stale_by_family: dict[str, list[str]] = {}

    for family_id, spec in FAMILY_DEFINITIONS.items():
        per_ticker = bool(spec.get("per_ticker"))
        required_sources = list(spec.get("required_sources", []))
        source_status = non_ticker_family_status(family_id, spec, source_states)
        family_entry = {
            "family_id": family_id,
            "label": spec["label"],
            "question_aliases": spec.get("question_aliases", []),
            "per_ticker": per_ticker,
            "required_sources": required_sources,
            "source_open_required_for_claims": bool(spec.get("source_open_required_for_claims", True)),
            "indexed_by_registry": True,
            "collection_status": source_status["status"],
            "collected": source_status["collected"],
            "present_sources": source_status["present_sources"],
            "missing_required_sources": source_status["missing_required_sources"],
            "stale_sources": source_status["stale_sources"],
            "source_artifacts": source_status["source_artifacts"],
            "expected_status": spec.get("expected_status"),
            "notes": spec.get("notes", []),
        }
        if per_ticker:
            covered_tickers: list[str] = []
            missing_tickers: list[str] = []
            stale_tickers: list[str] = []
            for ticker in tickers:
                row = family_row_for_ticker(family_id, spec, ticker, ticker_indexes, source_states)
                ticker_coverage[ticker]["families"][family_id] = row
                if row["covered"]:
                    covered_tickers.append(ticker)
                else:
                    missing_tickers.append(ticker)
                    ticker_coverage[ticker]["missing_families"].append(family_id)
                if row["stale_sources"]:
                    stale_tickers.append(ticker)
                    ticker_coverage[ticker]["stale_families"].append(family_id)
            family_entry.update({
                "covered_ticker_count": len(covered_tickers),
                "missing_ticker_count": len(missing_tickers),
                "covered_tickers_sample": covered_tickers[:25],
                "missing_tickers": missing_tickers,
                "stale_tickers": stale_tickers,
            })
            missing_by_family[family_id] = missing_tickers
            stale_by_family[family_id] = stale_tickers
        family_registry[family_id] = family_entry

    missing_by_ticker = {ticker: row["missing_families"] for ticker, row in ticker_coverage.items() if row["missing_families"]}
    stale_by_ticker = {ticker: row["stale_families"] for ticker, row in ticker_coverage.items() if row["stale_families"]}
    source_missing = [source_id for source_id, state in source_states.items() if not state["exists"]]
    source_stale = [source_id for source_id, state in source_states.items() if state["status"] == "stale"]
    source_unusable_placeholder = [source_id for source_id, state in source_states.items() if state["status"] == "placeholder_manual_required"]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_dt.isoformat().replace("+00:00", "Z"),
        "workflow": "WF77 - Finance Intelligence Coverage and Question Router",
        "status": "ok_with_explicit_gaps" if source_missing or source_stale else "ok",
        "posture": "derived_review_only_coverage_registry_not_canon_not_approval_not_apply_authority",
        "authority_boundary": REVIEW_ONLY_AUTHORITY,
        "source_open_rule": "Use this registry for routing and coverage/missing/freshness answers. Open exact source artifacts or canonical owner notes before final finance, readiness, recommendation, authority, or action claims.",
        "summary": {
            "source_artifact_count": len(source_states),
            "source_artifacts_present": len(source_states) - len(source_missing),
            "source_artifacts_missing": len(source_missing),
            "source_artifacts_stale": len(source_stale),
            "source_artifacts_unusable_placeholder": len(source_unusable_placeholder),
            "ticker_count_indexed": len(tickers),
            "data_family_count": len(family_registry),
            "analyst_layer_status": family_registry["analyst_consensus"]["collection_status"],
            "universe_registry_status": "present" if universe_entries else "missing",
            "universe_ticker_count": len(universe_entries),
        },
        "universe_registry": {
            "path": rel(UNIVERSE_PATH),
            "exists": UNIVERSE_PATH.exists(),
            "schema_version": universe.get("schema_version"),
            "generated_at_utc": universe.get("generated_at_utc"),
            "status": universe.get("status") if universe else "missing",
            "role": "durable_review_only_tier_type_routing_metadata_not_canon_not_approval",
            "architecture_boundary": universe.get("architecture_boundary") if isinstance(universe, dict) else None,
            "authority_boundary": universe.get("authority_boundary") if isinstance(universe, dict) else None,
            "ticker_count": len(universe_entries),
        },
        "question_classes": QUESTION_CLASSES,
        "source_artifacts": source_states,
        "family_registry": family_registry,
        "ticker_coverage": ticker_coverage,
        "missing_by_family": missing_by_family,
        "missing_by_ticker": missing_by_ticker,
        "stale_by_family": stale_by_family,
        "stale_by_ticker": stale_by_ticker,
        "routing_examples": {
            "do_we_collect_analyst_ratings": "family_registry.analyst_ratings.collected (currently false until tmp/analyst-consensus-current.json exists).",
            "which_tickers_lack_price_targets": "missing_by_family.analyst_price_targets",
            "is_valuation_indexed_fresh": "family_registry.valuation_multiples plus source_artifacts.fundamental_metrics_current.status",
            "what_is_missing_for_ticker": "missing_by_ticker.<TICKER> and ticker_coverage.<TICKER>.families",
        },
    }


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if registry.get("authority_boundary", {}).get("trade_execution_allowed") is not False:
        errors.append("trade_execution_allowed must be false")
    if registry.get("authority_boundary", {}).get("owner_approval_inferred") is not False:
        errors.append("owner_approval_inferred must be false")
    for family in FAMILY_DEFINITIONS:
        if family not in registry.get("family_registry", {}):
            errors.append(f"missing family_registry entry: {family}")
    for question_class in QUESTION_CLASSES:
        if question_class not in registry.get("question_classes", {}):
            errors.append(f"missing question class: {question_class}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/query the WF77 finance data coverage registry.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Coverage registry output JSON path.")
    parser.add_argument("--contract-output", type=Path, default=DEFAULT_CONTRACT, help="Router contract output JSON path.")
    parser.add_argument("--write-contract", action="store_true", help="Also write the router contract JSON.")
    parser.add_argument("--print", dest="print_json", action="store_true", help="Print registry JSON to stdout.")
    parser.add_argument("--family", help="Print one family entry after building/writing.")
    parser.add_argument("--ticker", help="Print one ticker coverage entry after building/writing.")
    parser.add_argument("--validate", action="store_true", help="Validate generated registry before writing/printing.")
    args = parser.parse_args()

    registry = build_registry()
    errors = validate_registry(registry) if args.validate else []
    if errors:
        print(json.dumps({"status": "error", "errors": errors}, indent=2), file=sys.stderr)
        return 2

    atomic_write_json(args.output, registry)
    if args.write_contract:
        atomic_write_json(args.contract_output, build_contract())

    if args.family:
        family = args.family.strip().lower().replace("-", "_").replace(" ", "_")
        print(json.dumps(registry["family_registry"].get(family, {"error": "unknown_family", "family": family}), indent=2, ensure_ascii=False))
    elif args.ticker:
        ticker = args.ticker.strip().upper()
        print(json.dumps(registry["ticker_coverage"].get(ticker, {"error": "unknown_ticker", "ticker": ticker}), indent=2, ensure_ascii=False))
    elif args.print_json:
        print(json.dumps(registry, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({
            "status": "ok",
            "output": rel(args.output),
            "contract_output": rel(args.contract_output) if args.write_contract else None,
            "summary": registry["summary"],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
