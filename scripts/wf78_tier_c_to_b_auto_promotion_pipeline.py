#!/usr/bin/env python3
"""Run a bounded WF78 Tier C -> Tier B research-bench promotion pipeline.

This pipeline automates the manual repair/evidence/label path for explicit
Tier C attention candidates and Phase-2 funnel candidates with complete evidence.
It is non-capital only: passing rows may be added to the Tier B research bench
when --approve-passing is provided, but no universe, canon, portfolio,
ticker-card, SQL, account, brokerage, or execution surface is mutated.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_missing_band_context_repair import technical_band_context


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
ATTENTION_TRIGGER = TMP / "wf78-tier-c-attention-trigger.json"
PHASE2_REQUESTS = TMP / "wf78-tier-b-research-packet-requests.json"
PHASE2_GATE = TMP / "wf78-tier-funnel-promotion-gate.json"
OFFICIAL_SOURCE_REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
REGISTER = TMP / "wf78-tier-label-decision-register.json"
SYNC_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
DEFAULT_OUT = TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.json"
DEFAULT_CLOSEOUT = TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.closeout.json"
SCHEMA = "veritas.wf78_tier_c_to_b_auto_promotion_pipeline.v1"
TIER_B_CAP = 50

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_tier_b_research_bench_label_allowed_with_owner_batch_approval": True,
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
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}
REQUIRED_TRUE_FLAGS = {
    "review_only",
    "automated_non_capital_routing_allowed",
    "derived_tier_b_research_bench_label_allowed_with_owner_batch_approval",
}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}

OFFICIAL_SOURCE_URLS: dict[str, dict[str, str]] = {
    "ALB": {
        "label": "Albemarle Investor Relations",
        "url": "https://investors.albemarle.com/overview/default.aspx",
    },
    "ALLE": {
        "label": "Allegion Investor Relations",
        "url": "https://investor.allegion.com/",
    },
    "AMCR": {
        "label": "Amcor Investors",
        "url": "https://www.amcor.com/investors",
    },
    "AME": {
        "label": "AMETEK Investor Relations",
        "url": "https://investors.ametek.com/",
    },
    "AOS": {
        "label": "A. O. Smith Investor Relations",
        "url": "https://investor.aosmith.com/",
    },
    "AVGO": {
        "label": "Broadcom Investor Center",
        "url": "https://investors.broadcom.com/",
    },
    "CCL": {
        "label": "Carnival Corporation & plc Investors",
        "url": "https://www.carnivalcorp.com/investors",
    },
    "CEG": {
        "label": "Constellation Energy Investor Relations",
        "url": "https://investors.constellationenergy.com/",
    },
    "DASH": {
        "label": "DoorDash Investor Relations",
        "url": "https://ir.doordash.com/overview/default.aspx",
    },
    "EMR": {
        "label": "Emerson Investor Relations",
        "url": "https://ir.emerson.com/",
    },
    "QCOM": {
        "label": "Qualcomm Investor Relations",
        "url": "https://investor.qualcomm.com/overview/default.aspx",
    },
    "SCCO": {
        "label": "Southern Copper official company / investor source",
        "url": "https://southerncoppercorp.com/eng/",
    },
    "TDG": {
        "label": "TransDigm Group Investor Relations",
        "url": "https://www.transdigm.com/investor-relations/",
    },
    "TSM": {
        "label": "TSMC Investors",
        "url": "https://investor.tsmc.com/english",
    },
    "CASY": {
        "label": "Casey's Investor Relations",
        "url": "https://investor.caseys.com/",
    },
    "TXN": {
        "label": "Texas Instruments Investor Relations",
        "url": "https://investor.ti.com/",
    },
    "ASML": {
        "label": "ASML Investors",
        "url": "https://www.asml.com/investors",
    },
    "ARES": {
        "label": "Ares Management Investor Relations",
        "url": "https://ir.ares.com/",
    },
}


def normalise_official_source(raw: dict[str, Any]) -> dict[str, str]:
    url = str(raw.get("url") or raw.get("official_earnings_source_url") or raw.get("source_url") or "").strip()
    label = str(raw.get("label") or raw.get("source_label") or raw.get("source_section") or "Official source").strip()
    period = str(raw.get("period_label") or "").strip()
    source_section = str(raw.get("source_section") or "").strip()
    result = {"label": label, "url": url}
    if period:
        result["period_label"] = period
    if source_section:
        result["source_section"] = source_section
    return result


def official_source_map() -> dict[str, dict[str, str]]:
    sources = {symbol: dict(source) for symbol, source in OFFICIAL_SOURCE_URLS.items()}
    registry = load_dict(OFFICIAL_SOURCE_REGISTRY)
    tickers = as_dict(registry.get("tickers"))
    for symbol, raw in tickers.items():
        key = ticker(symbol)
        if not key or not isinstance(raw, dict):
            continue
        source = normalise_official_source(raw)
        if source.get("url"):
            sources[key] = source
    return sources

PASSABLE_BAND_STATUSES = {
    "IN_BAND",
    "NEAR_BAND",
    "ABOVE_BAND",
    "ABOVE_BAND_WAIT",
    "BELOW_BAND",
}

PHASE2_EVIDENCE_LABELS = {
    "macro_theme_fit": "macro/theme fit",
    "business_quality": "business quality reason",
    "fundamental_snapshot": "initial fundamentals snapshot available",
    "valuation_context": "valuation context available",
    "analyst_or_revision_context": "analyst/revision layer available or explicitly not applicable",
    "technical_price_band_context": "initial technical/price-band context",
    "official_earnings_capture": "official earnings capture/source proof",
    "risk_reason_understood": "risk reason understood",
    "portfolio_role": "portfolio role identified",
    "source_open_proof": "source-open proof usable",
    "repair_burden_acceptable": "evidence repair burden acceptable",
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


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def score_part_names(row: dict[str, Any]) -> set[str]:
    return {str(part.get("name") or "") for part in as_list(row.get("score_parts")) if isinstance(part, dict)}


def attention_rows_by_ticker(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get("attention_rows"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def attention_candidates(packet: dict[str, Any], limit: int | None = None) -> list[str]:
    rows = [
        row for row in as_list(packet.get("attention_rows"))
        if isinstance(row, dict)
        and row.get("attention_triggered") is True
        and ticker(row.get("ticker"))
        and row.get("attention_state") in {"C-CANDIDATE", "C-CANDIDATE-REPAIR"}
    ]
    rows.sort(
        key=lambda row: (
            -int(row.get("attention_score") or 0),
            -int(row.get("momentum_score") or 0),
            ticker(row.get("ticker")),
        )
    )
    selected = rows[:limit] if limit is not None and limit > 0 else rows
    return [ticker(row.get("ticker")) for row in selected]


def phase2_requests_by_ticker(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get("requests"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def phase2_decisions_by_ticker(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get("c_to_b_decisions"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def phase2_candidates(packet: dict[str, Any], limit: int | None = None) -> list[str]:
    selected = [
        ticker(row.get("ticker"))
        for row in as_list(packet.get("requests"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    ]
    return selected[:limit] if limit is not None and limit > 0 else selected


def analyst_buy_skew(card: dict[str, Any]) -> bool:
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    rating = str(analyst.get("consensus_rating") or "").lower()
    buy_count = int(analyst.get("buy_count") or 0)
    hold_count = int(analyst.get("hold_count") or 0)
    sell_count = int(analyst.get("sell_count") or 0)
    return "buy" in rating or buy_count > max(hold_count, sell_count)


def analyst_context_available(card: dict[str, Any]) -> bool:
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    if not analyst:
        return False
    status = str(analyst.get("status") or "").lower()
    if status in {"", "missing", "missing_manual_required"} or analyst.get("manual_review_required") is True:
        return False
    return bool(
        analyst.get("source_url")
        or analyst.get("consensus_rating")
        or analyst.get("average_target") is not None
        or analyst.get("buy_count") is not None
        or analyst.get("hold_count") is not None
        or analyst.get("sell_count") is not None
    )


def repair_burden_acceptable(blockers: list[str], band_status: str) -> bool:
    return not blockers and band_status != "BELOW_STOP"


SOURCE_OPEN_REPAIR_BLOCKERS = {
    "official_growth_bridge_source_open_required",
    "official_guidance_source_open_required",
    "orders_backlog_manual_capture_required",
}


def unresolved_repair_blockers(blockers: list[str], *, source_open: bool, technical_ok: bool) -> list[str]:
    unresolved: list[str] = []
    for blocker in blockers:
        if blocker in SOURCE_OPEN_REPAIR_BLOCKERS and source_open:
            continue
        if blocker == "technical_posture_missing" and technical_ok:
            continue
        unresolved.append(blocker)
    return unresolved


def valuation_available(card: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    valuation = as_dict(card.get("valuation")) or as_dict(as_dict(card.get("key_financial_metrics")).get("valuation"))
    forward_pe = as_float(valuation.get("forward_pe"))
    ev_to_ebitda = as_float(valuation.get("ev_to_ebitda_proxy"))
    has_context = str(valuation.get("valuation_context") or "") == "available" or forward_pe is not None or ev_to_ebitda is not None
    return has_context, {
        "forward_pe": forward_pe,
        "ev_to_ebitda_proxy": ev_to_ebitda,
        "earnings_yield_pct": as_float(valuation.get("earnings_yield_pct")),
        "fcf_yield_pct": as_float(valuation.get("fcf_yield_pct")),
    }


def latest_earnings_available(card: dict[str, Any]) -> bool:
    earnings = as_dict(card.get("latest_earnings_performance"))
    return earnings.get("status") == "available" and bool(earnings.get("period_end"))


def latest_earnings_metrics_available(card: dict[str, Any]) -> bool:
    earnings = as_dict(card.get("latest_earnings_performance"))
    if not latest_earnings_available(card):
        return False
    return any(earnings.get(name) is not None for name in ("diluted_eps", "revenue", "net_income"))


def official_earnings_capture_detail(
    card: dict[str, Any],
    official_source: dict[str, str] | None,
) -> dict[str, Any]:
    source_open = bool(official_source and official_source.get("url"))
    earnings = as_dict(card.get("latest_earnings_performance"))
    adjusted_eps = as_dict(earnings.get("official_adjusted_eps"))
    adjusted_eps_complete = (
        source_open
        and latest_earnings_available(card)
        and adjusted_eps.get("manual_capture_required") is not True
        and adjusted_eps.get("status") != "missing_manual_required"
        and (adjusted_eps.get("status") is not None or adjusted_eps.get("value") is not None)
    )
    latest_metrics_complete = source_open and latest_earnings_metrics_available(card)
    if adjusted_eps_complete:
        status = "official_adjusted_eps_captured"
        capture_mode = "official_adjusted_eps"
    elif latest_metrics_complete:
        status = "latest_earnings_metrics_with_official_source"
        capture_mode = "latest_earnings_metrics_with_source_open"
    elif not source_open:
        status = "source_open_required"
        capture_mode = "blocked_missing_official_source"
    elif not latest_earnings_available(card):
        status = "latest_earnings_missing"
        capture_mode = "blocked_missing_latest_earnings"
    else:
        status = "missing_manual_required"
        capture_mode = "blocked_missing_manual_capture"

    adjusted_eps_unresolved = adjusted_eps.get("manual_capture_required") is True or adjusted_eps.get("status") == "missing_manual_required"
    return {
        "status": status,
        "capture_mode": capture_mode,
        "gate_passed": bool(adjusted_eps_complete or latest_metrics_complete),
        "source_open": source_open,
        "source_url": official_source.get("url") if official_source else None,
        "period_end": earnings.get("period_end"),
        "diluted_eps": earnings.get("diluted_eps"),
        "revenue": earnings.get("revenue"),
        "net_income": earnings.get("net_income"),
        "free_cash_flow": earnings.get("free_cash_flow"),
        "official_adjusted_eps_status": adjusted_eps.get("status"),
        "official_adjusted_eps_value": adjusted_eps.get("value"),
        "official_adjusted_eps_manual_capture_required": adjusted_eps.get("manual_capture_required") is True,
        "official_adjusted_eps_detail_unresolved": bool(adjusted_eps_unresolved),
        "manual_capture_required_for_base_gate": False if latest_metrics_complete else bool(adjusted_eps_unresolved),
        "note": (
            "Base official earnings proof is satisfied by latest earnings metrics tied to an official source; "
            "official adjusted EPS detail remains unresolved."
            if latest_metrics_complete and not adjusted_eps_complete
            else None
        ),
    }


def official_earnings_capture_complete(card: dict[str, Any], *, source_open: bool) -> bool:
    source = {"url": "source-open-proof"} if source_open else {}
    return bool(official_earnings_capture_detail(card, source).get("gate_passed"))


def fundamental_available(card: dict[str, Any], row: dict[str, Any]) -> bool:
    fundamentals = as_dict(card.get("official_fundamentals"))
    return (
        "fundamental_snapshot_available" in score_part_names(row)
        or latest_earnings_available(card)
        or fundamentals.get("period_end") is not None
    )


def evidence_family_row(
    symbol: str,
    row: dict[str, Any],
    card: dict[str, Any],
    official_sources: dict[str, dict[str, str]],
) -> dict[str, Any]:
    parts = score_part_names(row)
    valuation_ok, valuation_detail = valuation_available(card)
    technical_context = technical_band_context(symbol)
    band = as_dict(technical_context.get("band"))
    band_status = str(band.get("band_status") or "")
    source = official_sources.get(symbol)
    warnings = [str(item) for item in as_list(row.get("warnings")) if str(item)]
    blockers = [str(item) for item in as_list(row.get("blockers")) if str(item)]
    technical_ok = technical_context.get("status") == "ok" and band_status in PASSABLE_BAND_STATUSES
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    source_open = bool(source and source.get("url"))
    official_capture = official_earnings_capture_detail(card, source)
    unresolved_blockers = unresolved_repair_blockers(blockers, source_open=source_open, technical_ok=technical_ok)
    no_unresolved_red_flags = repair_burden_acceptable(unresolved_blockers, band_status)

    families = {
        "macro_theme_fit": bool(row.get("attention_triggered")) and int(row.get("momentum_score") or 0) >= 15,
        "business_quality": int(row.get("fundamental_score") or 0) >= 25,
        "fundamental_snapshot": fundamental_available(card, row),
        "valuation_context": valuation_ok,
        "analyst_or_revision_context": "analyst_buy_skew" in parts or analyst_context_available(card),
        "technical_price_band_context": technical_ok,
        "official_earnings_capture": bool(official_capture.get("gate_passed")),
        "risk_reason_understood": bool(blockers) or bool(warnings),
        "portfolio_role": bool(row.get("sector") or row.get("industry")),
        "source_open_proof": source_open,
        "repair_burden_acceptable": no_unresolved_red_flags,
    }
    failed = [name for name, ok in families.items() if not ok]
    status = "eligible_for_tier_b_research_bench" if not failed else "blocked_pending_repair"
    if row.get("attention_state") not in {"C-CANDIDATE", "C-CANDIDATE-REPAIR"}:
        status = "blocked_invalid_attention_state"
        failed.append("attention_state_not_candidate")
    return {
        "ticker": symbol,
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "prior_attention_state": row.get("attention_state"),
        "attention_score": row.get("attention_score"),
        "momentum_score": row.get("momentum_score"),
        "fundamental_score": row.get("fundamental_score"),
        "status": status,
        "evidence_families": families,
        "failed_evidence_families": sorted(set(failed)),
        "blockers_before_repair": blockers,
        "unresolved_blockers_after_repair": unresolved_blockers,
        "warnings": warnings,
        "valuation_detail": valuation_detail,
        "analyst_detail": {
            "status": analyst.get("status"),
            "consensus_rating": analyst.get("consensus_rating"),
            "buy_skew": analyst_buy_skew(card),
            "source_url": analyst.get("source_url"),
        },
        "technical_band_context": {
            "status": technical_context.get("status"),
            "latest_close": as_dict(technical_context.get("inputs")).get("latest_close"),
            "data_date": as_dict(technical_context.get("inputs")).get("data_date"),
            "band_status": band_status,
            "entry_band_low": band.get("entry_band_low"),
            "entry_band_high": band.get("entry_band_high"),
            "stop_or_invalidation": band.get("stop_or_invalidation"),
            "warnings": as_list(technical_context.get("warnings")),
        },
        "official_source": source or {},
        "official_earnings_capture_detail": official_capture,
        "tier_b_research_bench_label_approved": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "would_mutate_universe": False,
        "source_artifacts": [
            rel(ATTENTION_TRIGGER),
            rel(CARD_DIR / f"{symbol}.current.json"),
            source.get("url") if source else None,
        ],
    }


def phase2_evidence_row(
    symbol: str,
    request: dict[str, Any],
    decision: dict[str, Any],
    card: dict[str, Any],
    official_sources: dict[str, dict[str, str]],
) -> dict[str, Any]:
    evidence_present = {str(item).strip().lower() for item in as_list(request.get("evidence_present"))}
    source = official_sources.get(symbol)
    official_capture = official_earnings_capture_detail(card, source)
    gate_ok = (
        decision.get("status") == "eligible_for_admission"
        and decision.get("from_tier") == "tier_c"
        and decision.get("to_tier") == "tier_b"
        and as_list(decision.get("missing_evidence")) == []
        and decision.get("admission_executed") is False
    )
    families = {
        family: label.lower() in evidence_present
        for family, label in PHASE2_EVIDENCE_LABELS.items()
    }
    if not source or not source.get("url"):
        families["source_open_proof"] = False
    families["official_earnings_capture"] = bool(official_capture.get("gate_passed"))
    failed = [name for name, ok in families.items() if not ok]
    if not gate_ok:
        failed.append("phase2_gate_not_eligible")
    if not card:
        failed.append("ticker_card_missing")

    status = "eligible_for_tier_b_research_bench" if not failed else "blocked_pending_repair"
    return {
        "ticker": symbol,
        "name": request.get("name") or decision.get("name"),
        "sector": None,
        "industry": None,
        "prior_attention_state": request.get("current_state") or decision.get("current_state"),
        "candidate_source": "phase2_funnel",
        "phase2_gate_status": decision.get("status"),
        "phase2_required_evidence_count": decision.get("required_evidence_count"),
        "phase2_evidence_present_count": decision.get("evidence_present_count"),
        "status": status,
        "evidence_families": families,
        "failed_evidence_families": sorted(set(failed)),
        "blockers_before_repair": [],
        "warnings": [],
        "valuation_detail": {},
        "technical_band_context": {
            "status": "proven_by_phase2_research_packet",
            "evidence_label": PHASE2_EVIDENCE_LABELS["technical_price_band_context"],
        },
        "official_source": source or {},
        "official_earnings_capture_detail": official_capture,
        "tier_b_research_bench_label_approved": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "would_mutate_universe": False,
        "source_artifacts": [
            rel(PHASE2_REQUESTS),
            rel(PHASE2_GATE),
            rel(CARD_DIR / f"{symbol}.current.json"),
            source.get("url") if source else None,
        ],
    }


def existing_register_records() -> list[dict[str, Any]]:
    register = load_dict(REGISTER)
    return [record for record in as_list(register.get("records")) if isinstance(record, dict)]


def approved_tier_b_labels_from_records(records: list[dict[str, Any]]) -> set[str]:
    return {
        ticker(item)
        for existing in records
        if existing.get("decision_type") == "tier_b_research_bench_label_only"
        for item in as_list(existing.get("approved_tickers"))
        if ticker(item)
    }


def current_auto_tier_b_tickers(router: dict[str, Any]) -> set[str]:
    return {
        ticker(item)
        for item in as_list(as_dict(router.get("summary")).get("auto_tier_b_tickers"))
        if ticker(item)
    }


def ranked_eligible_tickers(rows: list[dict[str, Any]]) -> list[str]:
    eligible = [row for row in rows if row.get("status") == "eligible_for_tier_b_research_bench"]
    eligible.sort(
        key=lambda row: (
            -int(row.get("attention_score") or 0),
            -int(row.get("momentum_score") or 0),
            -int(row.get("fundamental_score") or 0),
            ticker(row.get("ticker")),
        )
    )
    return [ticker(row.get("ticker")) for row in eligible if ticker(row.get("ticker"))]


def select_capacity_approved_tickers(
    rows: list[dict[str, Any]],
    *,
    existing_approved: set[str],
    current_router_tier_b: set[str],
    cap: int = TIER_B_CAP,
) -> tuple[list[str], list[str], list[str], int]:
    ranked = ranked_eligible_tickers(rows)
    already_approved = [symbol for symbol in ranked if symbol in existing_approved]
    remaining_capacity = max(0, cap - len(current_router_tier_b)) if current_router_tier_b else 0
    newly_approved = [symbol for symbol in ranked if symbol not in existing_approved][:remaining_capacity]
    approved = sorted(set(already_approved) | set(newly_approved))
    held = [symbol for symbol in ranked if symbol not in set(approved)]
    return approved, newly_approved, held, remaining_capacity


def write_approval_register(passing: list[str], source_packet: Path, approval_reference: str) -> dict[str, Any]:
    records = existing_register_records()
    approved_at = utc_now()
    if passing:
        decision_id = f"wf78-tier-b-research-bench-labels-{'-'.join(t.lower() for t in passing)}-{approved_at[:10]}"
        record = {
            "decision_id": decision_id,
            "decision_type": "tier_b_research_bench_label_only",
            "approval_status": "approved_label_only",
            "approval_reference": approval_reference,
            "approval_text": (
                "Owner approved automated Tier B research-bench labels only for passing "
                f"WF78 Tier C pipeline candidates: {', '.join(passing)}."
            ),
            "approved_at_local": None,
            "approved_tickers": passing,
            "approved_at_utc": approved_at,
            "source_packet": rel(source_packet),
            "label_semantics": {
                "tier": "B",
                "role": "research_bench",
                "deployment_ready": False,
                "capital_deployment_approval": False,
                "trade_or_execution_approval": False,
                "canon_or_portfolio_mutation": False,
                "separate_capital_or_execution_approval_required": True,
            },
            "record_only": True,
            "applied_to_universe": False,
            "owner_approval_inferred": False,
        }
        records = [item for item in records if item.get("decision_id") != decision_id]
        records.append(record)
    approved_tier_b = sorted(approved_tier_b_labels_from_records(records))
    checks: list[dict[str, Any]] = []
    for flag in REQUIRED_TRUE_FLAGS:
        checks.append({"name": f"authority_{flag}_true", "ok": AUTHORITY_BOUNDARY.get(flag) is True, "status": "ok", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})
    for flag in REQUIRED_FALSE_FLAGS:
        checks.append({"name": f"authority_{flag}_false", "ok": AUTHORITY_BOUNDARY.get(flag) is False, "status": "ok", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})
    if passing:
        checks.append({"name": "passing_tickers_present", "ok": True, "status": "ok", "severity": "critical", "detail": passing})
    else:
        checks.append({
            "name": "no_passing_tickers_register_refresh_only",
            "ok": True,
            "status": "ok",
            "severity": "critical",
            "detail": "No new passing candidates; refreshed the existing label register without adding a decision record.",
        })
    report = {
        "schema": "veritas.wf78_tier_label_decision_register.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF78 - Tier Label Decision Register",
        "purpose": "Record exact owner-approved tier-label decisions without applying labels or mutating any authority-bearing surface.",
        "authority_boundary": {
            "review_only": True,
            "report_only": True,
            "approval_register_only": True,
            "tier_label_apply_allowed": False,
            "universe_mutation_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "production_answer_path_change_allowed": False,
            "capital_deployment_allowed": False,
            "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
        "source_artifacts": {
            "tier_c_to_b_auto_promotion_pipeline": rel(source_packet),
        },
        "summary": {
            "record_count": len(records),
            "approved_tier_b_research_bench_label_count": len(approved_tier_b),
            "approved_tier_b_research_bench_labels": approved_tier_b,
            "tier_label_apply_executed": False,
            "universe_mutation_executed": False,
            "next_safe_action": "Refresh the separate preview/router artifacts; no capital or execution authority is created.",
        },
        "records": records,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This register records label approval only; it does not apply labels.",
            "No universe, canon, portfolio, ticker-card, SQL, customer, paper, live, brokerage, or account mutation.",
            "No capital deployment, paper/live order, or execution approval.",
            "No owner approval inference beyond the exact recorded label-only decision.",
        ],
    }
    atomic_write_json(REGISTER, report)
    return report


def run_child(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    attention = load_dict(ATTENTION_TRIGGER)
    phase2_request_packet = load_dict(PHASE2_REQUESTS)
    phase2_gate_packet = load_dict(PHASE2_GATE)
    official_sources = official_source_map()
    auto_router = load_dict(AUTO_ROUTER)
    requested = [ticker(item) for item in args.candidate if ticker(item)]
    if args.from_attention:
        requested.extend(attention_candidates(attention, args.max_candidates))
    if args.from_phase2_requests:
        requested.extend(phase2_candidates(phase2_request_packet, args.max_candidates))
    requested = sorted(dict.fromkeys(requested))
    attention_by_ticker = attention_rows_by_ticker(attention)
    phase2_by_ticker = phase2_requests_by_ticker(phase2_request_packet)
    phase2_decisions = phase2_decisions_by_ticker(phase2_gate_packet)
    rows: list[dict[str, Any]] = []
    missing_candidates: list[str] = []
    for symbol in requested:
        attention_row = attention_by_ticker.get(symbol)
        phase2_request = phase2_by_ticker.get(symbol)
        phase2_decision = phase2_decisions.get(symbol)
        card = load_dict(CARD_DIR / f"{symbol}.current.json")
        if attention_row and card:
            rows.append(evidence_family_row(symbol, attention_row, card, official_sources))
        elif phase2_request and phase2_decision:
            rows.append(phase2_evidence_row(symbol, phase2_request, phase2_decision, card, official_sources))
        else:
            missing_candidates.append(symbol)
            rows.append({
                "ticker": symbol,
                "status": "blocked_missing_attention_phase2_or_card",
                "failed_evidence_families": ["attention_phase2_or_card_missing"],
                "tier_b_research_bench_label_approved": False,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "would_mutate_universe": False,
            })

    passing = sorted(row["ticker"] for row in rows if row.get("status") == "eligible_for_tier_b_research_bench")
    existing_approved = approved_tier_b_labels_from_records(existing_register_records())
    router_tier_b_before = current_auto_tier_b_tickers(auto_router)
    approved_for_rows: list[str] = []
    newly_approved: list[str] = []
    capacity_held: list[str] = []
    approval_capacity_remaining = 0
    if args.approve_passing:
        approved_for_rows, newly_approved, capacity_held, approval_capacity_remaining = select_capacity_approved_tickers(
            rows,
            existing_approved=existing_approved,
            current_router_tier_b=router_tier_b_before,
        )
    blocked = sorted(row["ticker"] for row in rows if row.get("ticker") not in passing)
    status_counts = Counter(str(row.get("status")) for row in rows)
    child_runs: list[dict[str, Any]] = []
    register_summary: dict[str, Any] | None = None

    if args.approve_passing and args.write:
        register = write_approval_register(newly_approved, args.out if args.out.is_absolute() else ROOT / args.out, args.approval_reference)
        register_summary = as_dict(register.get("summary"))
        for row in rows:
            if row.get("ticker") in approved_for_rows:
                row["tier_b_research_bench_label_approved"] = True
                row["tier_b_research_bench_label_approval_status"] = "approved_label_only"
            elif row.get("ticker") in capacity_held:
                row["tier_b_research_bench_label_approval_status"] = "held_by_tier_b_capacity_cap"
                row["tier_b_research_bench_capacity_hold_reason"] = f"Tier B cap {TIER_B_CAP} reached before this eligible row."
        child_runs.append(run_child([sys.executable, str(ROOT / "scripts" / "wf78_tier_label_sync_preview.py"), "--write", "--validate"]))
        child_runs.append(run_child([sys.executable, str(ROOT / "scripts" / "wf78_auto_tier_router.py"), "--write", "--validate"]))

    checks: list[dict[str, Any]] = []
    checks.append({"name": "attention_trigger_present", "ok": bool(attention), "status": "ok" if attention else "fail", "severity": "critical", "detail": rel(ATTENTION_TRIGGER)})
    phase2_used = [row.get("ticker") for row in rows if row.get("candidate_source") == "phase2_funnel"]
    if phase2_used:
        checks.append({"name": "phase2_requests_present_for_phase2_candidates", "ok": bool(phase2_request_packet), "status": "ok" if phase2_request_packet else "fail", "severity": "critical", "detail": rel(PHASE2_REQUESTS)})
        checks.append({"name": "phase2_gate_present_for_phase2_candidates", "ok": bool(phase2_gate_packet), "status": "ok" if phase2_gate_packet else "fail", "severity": "critical", "detail": rel(PHASE2_GATE)})
        checks.append({"name": "phase2_gate_validation_ok", "ok": as_dict(phase2_gate_packet.get("validation")).get("status") == "ok", "status": "ok" if as_dict(phase2_gate_packet.get("validation")).get("status") == "ok" else "fail", "severity": "critical", "detail": as_dict(phase2_gate_packet.get("validation")).get("status")})
    requested_ok = bool(requested) or bool(args.from_attention) or bool(args.from_phase2_requests)
    checks.append({"name": "requested_candidates_present_or_dynamic_mode", "ok": requested_ok, "status": "ok" if requested_ok else "fail", "severity": "critical", "detail": {"requested": requested, "from_attention": bool(args.from_attention), "from_phase2_requests": bool(args.from_phase2_requests)}})
    checks.append({"name": "all_requested_candidates_evaluated", "ok": len(rows) == len(requested), "status": "ok" if len(rows) == len(requested) else "fail", "severity": "critical", "detail": {"rows": len(rows), "requested": len(requested)}})
    checks.append({"name": "missing_candidates_absent", "ok": not missing_candidates, "status": "ok" if not missing_candidates else "fail", "severity": "critical", "detail": missing_candidates})
    checks.append({"name": "no_universe_mutation", "ok": all(row.get("would_mutate_universe") is False for row in rows), "status": "ok", "severity": "critical", "detail": None})
    checks.append({"name": "no_capital_deployment_approved", "ok": all(row.get("capital_deployment_approved") is False for row in rows), "status": "ok", "severity": "critical", "detail": None})
    checks.append({"name": "no_trade_or_execution_approved", "ok": all(row.get("trade_or_execution_approved") is False for row in rows), "status": "ok", "severity": "critical", "detail": None})
    checks.append({"name": "child_refreshes_ok_if_run", "ok": all(run.get("ok") for run in child_runs), "status": "ok" if all(run.get("ok") for run in child_runs) else "fail", "severity": "critical", "detail": child_runs})
    for flag in REQUIRED_TRUE_FLAGS:
        ok = AUTHORITY_BOUNDARY.get(flag) is True
        checks.append({"name": f"authority_{flag}_true", "ok": ok, "status": "ok" if ok else "fail", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})
    for flag in REQUIRED_FALSE_FLAGS:
        ok = AUTHORITY_BOUNDARY.get(flag) is False
        checks.append({"name": f"authority_{flag}_false", "ok": ok, "status": "ok" if ok else "fail", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier C to Tier B Auto Promotion Pipeline",
        "purpose": "Evaluate explicit Tier C attention or Phase-2 complete-evidence candidates for Tier B research-bench admission and optionally append approved derived labels.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "owner_batch_approval_reference": args.approval_reference,
        "source_artifacts": {
            "tier_c_attention_trigger": rel(ATTENTION_TRIGGER),
            "phase2_research_packet_requests": rel(PHASE2_REQUESTS),
            "phase2_funnel_promotion_gate": rel(PHASE2_GATE),
            "official_source_registry": rel(OFFICIAL_SOURCE_REGISTRY),
            "ticker_cards": rel(CARD_DIR),
            "tier_label_decision_register": rel(REGISTER),
            "tier_label_sync_preview": rel(SYNC_PREVIEW),
            "auto_tier_router": rel(AUTO_ROUTER),
        },
        "summary": {
            "requested_count": len(requested),
            "requested_tickers": requested,
            "candidate_source": "+".join(
                source
                for source in [
                    "explicit_cli_candidates" if args.candidate else "",
                    "attention_trigger_dynamic" if args.from_attention else "",
                    "phase2_research_packet_requests" if args.from_phase2_requests else "",
                ]
                if source
            ) or "unspecified",
            "max_candidates": args.max_candidates if args.from_attention or args.from_phase2_requests else None,
            "phase2_candidate_count": len(phase2_used),
            "phase2_candidates": sorted(str(item) for item in phase2_used if item),
            "eligible_tier_b_research_bench_count": len(passing),
            "eligible_tier_b_research_bench_tickers": passing,
            "approval_capacity_tier_b_cap": TIER_B_CAP,
            "approval_capacity_current_router_tier_b_count": len(router_tier_b_before),
            "approval_capacity_remaining_before_run": approval_capacity_remaining,
            "capacity_held_eligible_count": len(capacity_held),
            "capacity_held_eligible_tickers": capacity_held,
            "blocked_count": len(blocked),
            "blocked_tickers": blocked,
            "status_counts": dict(sorted(status_counts.items())),
            "approve_passing_requested": bool(args.approve_passing),
            "approved_tier_b_research_bench_label_count": len(approved_for_rows) if args.approve_passing and args.write else 0,
            "approved_tier_b_research_bench_labels": approved_for_rows if args.approve_passing and args.write else [],
            "newly_approved_tier_b_research_bench_label_count": len(newly_approved) if args.approve_passing and args.write else 0,
            "newly_approved_tier_b_research_bench_labels": newly_approved if args.approve_passing and args.write else [],
            "register_summary_after_update": register_summary,
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "next_safe_action": "Keep blocked rows in C-CANDIDATE-REPAIR/monitor; use passing rows as Tier B research-bench only.",
        },
        "rows": rows,
        "child_runs": child_runs,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "Tier B research-bench labels do not approve capital deployment.",
            "No trade, order, paper/live execution, brokerage/account action, or money movement authority is created.",
            "This pipeline does not mutate universe, canon, portfolio, ticker-card, or SQL canon surfaces.",
            "Rows with unresolved warnings, failed source proof, failed band context, or below-stop posture stay blocked.",
        ],
    }


def closeout_from(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf78_tier_c_to_b_auto_promotion_pipeline.closeout.v1",
        "generated_at_utc": utc_now(),
        "status": report.get("status"),
        "workflow": report.get("workflow"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "source_artifacts": report.get("source_artifacts"),
        "stop_lines": report.get("stop_lines"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", default=[], help="Explicit ticker to evaluate.")
    parser.add_argument("--from-attention", action="store_true", help="Evaluate current Tier C attention candidates from the latest attention trigger artifact.")
    parser.add_argument("--from-phase2-requests", action="store_true", help="Evaluate current complete-evidence Phase-2 Tier C to Tier B request candidates.")
    parser.add_argument("--max-candidates", type=int, default=25, help="Maximum dynamic attention candidates to evaluate when --from-attention is used.")
    parser.add_argument("--approve-passing", action="store_true", help="Append owner-approved Tier B research-bench labels for passing rows.")
    parser.add_argument("--approval-reference", default="webchat 2026-07-05 Randall standing approval: automatically apply passing WF78 C-to-B derived Tier B research-bench labels only; no capital, execution, portfolio, canon, account, or owner-approval inference")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--closeout", type=Path, default=DEFAULT_CLOSEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    closeout = args.closeout if args.closeout.is_absolute() else ROOT / args.closeout
    if args.write:
        atomic_write_json(out, report)
        atomic_write_json(closeout, closeout_from(report))
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "closeout": rel(closeout),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
