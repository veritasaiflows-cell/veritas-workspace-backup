#!/usr/bin/env python3
"""Build the WF75 anonymous scenario-template library.

Templates are internal/review-only service request fixtures. They use ticker
sets and scenario metadata only, not fake-person profiles or real customer data.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf75-scenario-template-library.json"

SCHEMA = "veritas.wf75.scenario_template_library.v1"

AUTHORITY_BOUNDARY = {
    "real_customer_data_allowed": False,
    "fake_person_persona_allowed": False,
    "external_delivery_allowed": False,
    "public_launch_allowed": False,
    "personalized_regulated_advice_allowed": False,
    "brokerage_or_account_connection_allowed": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_library() -> dict[str, Any]:
    scenarios = [
        {
            "scenario_id": "anon-watchlist-ai-infrastructure-v1",
            "request_type": "watchlist_brief",
            "scenario": "ai_infrastructure_and_quality_watchlist",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["ETN", "MSFT", "NVDA", "JPM", "VRT"],
            "coverage_intent": "AI infrastructure, large-cap quality, and financial-sector watchlist context.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-materials-diversification-v1",
            "request_type": "sector_watchlist_brief",
            "scenario": "materials_diversification_starter_review",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["XLB", "LIN", "VAW", "VMC", "ECL"],
            "coverage_intent": "Materials ETF/single-name diversification context with explicit risk and freshness labels.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-risk-freshness-edge-cases-v1",
            "request_type": "freshness_and_risk_brief",
            "scenario": "supplemental_price_and_risk_edge_cases",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["KTOS", "SLV", "SMCI", "TLT", "CME"],
            "coverage_intent": "Regression coverage for supplemental price evidence, macro/speculative lanes, and below-stop review labels.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-single-ticker-deep-dive-v1",
            "request_type": "single_ticker_review",
            "scenario": "single_ticker_evidence_and_entry_context",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["NVDA"],
            "coverage_intent": "Single-ticker depth regression for source freshness, entry context, risk, and non-advice wording.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-etf-comparison-v1",
            "request_type": "etf_comparison_brief",
            "scenario": "sector_etf_comparison_without_personalization",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["XLB", "VAW", "XLI", "XLC"],
            "coverage_intent": "ETF comparison coverage without suitability, portfolio-fit, or personalized allocation claims.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-earnings-follow-up-v1",
            "request_type": "earnings_follow_up_brief",
            "scenario": "earnings_catalyst_follow_up_watchlist",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["NVDA", "ETN", "MSFT", "VRT"],
            "coverage_intent": "Catalyst follow-up regression for quality names where earnings/freshness labels matter.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-below-stop-repair-review-v1",
            "request_type": "risk_repair_review",
            "scenario": "below_stop_or_repair_queue_review",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["CME", "LMT", "XOM", "ECL", "TLT"],
            "coverage_intent": "Below-stop and repair-watchlist wording regression with no sell/trim/action inference.",
            "expected_validator_outcome": "clean",
        },
        {
            "scenario_id": "anon-insufficient-evidence-v1",
            "request_type": "evidence_gap_brief",
            "scenario": "insufficient_or_degraded_evidence_handling",
            "audience_segment": "self_directed_retail_investor",
            "ticker_set": ["SMCI", "KTOS", "BRK.B", "META"],
            "coverage_intent": "Evidence-gap regression for degraded, supplemental, or stale-source handling.",
            "expected_validator_outcome": "clean",
        },
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "template_count": len(scenarios),
        "templates": scenarios,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": validate_library(scenarios),
    }


def validate_library(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if len(scenarios) < 8:
        errors.append("template_count_below_8")
    seen: set[str] = set()
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id") or "")
        if not scenario_id:
            errors.append("template_missing_scenario_id")
        if scenario_id in seen:
            errors.append(f"duplicate_scenario_id={scenario_id}")
        seen.add(scenario_id)
        if not scenario.get("ticker_set"):
            errors.append(f"{scenario_id}_missing_ticker_set")
        if scenario.get("fake_person_persona_used") is True:
            errors.append(f"{scenario_id}_fake_person_persona_used")
    return {"status": "ok" if not errors else "error", "errors": errors}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF75 scenario-template library.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.out.is_absolute():
        args.out = ROOT / args.out
    payload = build_library()
    if args.write:
        atomic_write_json(args.out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["validation"]["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
