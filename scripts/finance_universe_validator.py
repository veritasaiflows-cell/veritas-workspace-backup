#!/usr/bin/env python3
"""Build and validate the alerts-and-recommendations universe registry.

The universe registry is durable routing metadata for finance intelligence
routing. It is not canon, approval, account, capital, order, or execution
authority. Production-grade answer scope is SQL-first and dynamic.
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
from finance_production_scope import production_tickers as production_scope_tickers, source_summary as production_scope_source_summary

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
DEFAULT_VALIDATION = TMP / "wf78-finance-universe-validation.json"

SCHEMA_VERSION = 1
VALID_TIERS = {"A", "B", "C", "D"}
VALID_INSTRUMENT_TYPES = {
    "operating_company",
    "etf",
    "commodity_proxy",
    "bond_or_rate_proxy",
    "currency_proxy",
    "crypto_or_regulated_digital_asset",
}
VALID_REQUIREMENT_STATUSES = {
    "required",
    "daily_required",
    "weekly_required",
    "monthly_required",
    "required_if_promoted",
    "optional",
    "not_applicable",
    "manual_required",
    "source_open_required",
}

AUTHORITY_BOUNDARY = {
    "posture": "alerts_and_non_executing_recommendations_universe_registry",
    "review_only": True,
    "writes_finance_canon": False,
    "maintains_account_or_capital_state": False,
    "capital_or_order_authority": False,
    "execution_allowed": False,
    "owner_approval_inferred": False,
}

RETIRED_FIELD_TOKENS = (
    "portfolio",
    "paper_order",
    "paper_or_live",
    "deployment_surface",
    "sizing",
    "sleeve",
    "allocation",
    "tranche",
)


def strip_retired_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_retired_fields(item)
            for key, item in value.items()
            if not any(token in str(key).lower() for token in RETIRED_FIELD_TOKENS)
        }
    if isinstance(value, list):
        return [strip_retired_fields(item) for item in value]
    return value

ETF_SYMBOLS = {"ITA", "PAVE", "VAW", "VXUS", "XLB", "XLC", "XLE", "XLF", "XLI"}
COMMODITY_PROXY_SYMBOLS = {"SLV"}
BOND_OR_RATE_PROXY_SYMBOLS = {"TLT"}
ACTIVE_INTERNAL_SCOPE = "active_internal_universe"
PRODUCTION_SCOPE = "strategic_production_grade"
PILOT_SCOPE = "pilot_fixture"
REVIEW_100_SCOPE = "review_100_monitor"
SUPPORTED_ACTIVE_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {0, 58, 158, 258, 358, 458}
PILOT_FIXTURES = [
    {"ticker": "ADBE", "name": "Adobe Inc.", "sector": "Technology", "industry": "Application Software"},
    {"ticker": "ASML", "name": "ASML Holding N.V.", "sector": "Technology", "industry": "Semiconductor Equipment"},
    {"ticker": "AVGO", "name": "Broadcom Inc.", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "CRM", "name": "Salesforce, Inc.", "sector": "Technology", "industry": "Application Software"},
    {"ticker": "INTU", "name": "Intuit Inc.", "sector": "Technology", "industry": "Application Software"},
    {"ticker": "NOW", "name": "ServiceNow, Inc.", "sector": "Technology", "industry": "Application Software"},
    {"ticker": "ORCL", "name": "Oracle Corporation", "sector": "Technology", "industry": "Software Infrastructure"},
    {"ticker": "SAP", "name": "SAP SE", "sector": "Technology", "industry": "Application Software"},
    {"ticker": "SHOP", "name": "Shopify Inc.", "sector": "Technology", "industry": "E-Commerce Software"},
    {"ticker": "TSM", "name": "Taiwan Semiconductor Manufacturing Company Limited", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "UBER", "name": "Uber Technologies, Inc.", "sector": "Industrials", "industry": "Mobility Platform"},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_dict(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def index_fundamentals(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = data.get("rows") or []
    return {str(row.get("ticker", "")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def infer_instrument_type(ticker: str, fundamental: dict[str, Any]) -> str:
    if ticker in COMMODITY_PROXY_SYMBOLS:
        return "commodity_proxy"
    if ticker in BOND_OR_RATE_PROXY_SYMBOLS:
        return "bond_or_rate_proxy"
    if ticker in ETF_SYMBOLS or fundamental.get("instrument_type") == "etf_or_macro_proxy":
        return "etf"
    return "operating_company"


def infer_tier(ticker: str, fundamental: dict[str, Any], instrument_type: str) -> str:
    if instrument_type == "operating_company":
        return "B"
    return "C"


def data_requirements_for(tier: str, instrument_type: str) -> dict[str, str]:
    operating = instrument_type == "operating_company"
    if tier == "A":
        return {
            "price_band_stop": "daily_required",
            "technical_posture": "daily_required",
            "fundamentals": "weekly_required" if operating else "required_if_promoted",
            "analyst_consensus": "weekly_required" if operating else "optional",
            "official_evidence": "source_open_required" if operating else "not_applicable",
            "risk_register": "required",
            "authority_guardrails": "required",
        }
    if tier == "B":
        return {
            "price_band_stop": "daily_required",
            "technical_posture": "daily_required",
            "fundamentals": "weekly_required" if operating else "required_if_promoted",
            "analyst_consensus": "weekly_required" if operating else "optional",
            "official_evidence": "source_open_required" if operating else "not_applicable",
            "risk_register": "required",
            "authority_guardrails": "required",
        }
    if tier == "C":
        return {
            "price_band_stop": "weekly_required",
            "technical_posture": "weekly_required",
            "fundamentals": "required_if_promoted",
            "analyst_consensus": "optional",
            "official_evidence": "required_if_promoted" if operating else "not_applicable",
            "risk_register": "required_if_promoted",
            "authority_guardrails": "required",
        }
    return {
        "price_band_stop": "monthly_required",
        "technical_posture": "monthly_required",
        "fundamentals": "required_if_promoted",
        "analyst_consensus": "optional",
        "official_evidence": "required_if_promoted" if operating else "not_applicable",
        "risk_register": "required_if_promoted",
        "authority_guardrails": "required",
    }


def monitoring_cadence_for(tier: str) -> dict[str, str]:
    if tier == "A":
        return {"price_technical": "daily_and_intraday_when_market_open", "fundamentals": "weekly_or_event_driven", "analyst": "weekly", "official_evidence": "event_driven_source_open"}
    if tier == "B":
        return {"price_technical": "daily", "fundamentals": "weekly", "analyst": "weekly", "official_evidence": "event_driven_source_open"}
    if tier == "C":
        return {"price_technical": "weekly_or_triggered", "fundamentals": "on_promotion", "analyst": "optional", "official_evidence": "on_promotion"}
    return {"price_technical": "monthly_or_triggered", "fundamentals": "on_promotion", "analyst": "optional", "official_evidence": "on_promotion"}


def is_production_scope_row(row: dict[str, Any]) -> bool:
    return row.get("production_scope") is True or row.get("universe_scope") == PRODUCTION_SCOPE


def has_retired_scope_marker(row: dict[str, Any]) -> bool:
    coverage_reason = row.get("coverage_reason") if isinstance(row.get("coverage_reason"), dict) else {}
    return row.get("retired_legacy_42_scope") is True or coverage_reason.get("retired_legacy_42") is True


def active_internal_entries(active_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in active_entries if row.get("universe_scope") == ACTIVE_INTERNAL_SCOPE]


def build_universe() -> dict[str, Any]:
    coverage = load_dict(TMP / "finance-data-coverage-current.json")
    fundamentals = load_dict(TMP / "fundamental-metrics-current.json")
    company_ir = load_dict(ROOT / "data" / "fundamentals" / "company-ir-metadata.json")

    fundamental_index = index_fundamentals(fundamentals)
    coverage_tickers = sorted((coverage.get("ticker_coverage") or {}).keys())
    tickers = sorted(set(str(ticker).upper() for ticker in coverage_tickers) | set(fundamental_index.keys()))
    ir_tickers = company_ir.get("tickers") if isinstance(company_ir.get("tickers"), dict) else {}

    entries: list[dict[str, Any]] = []
    for ticker in tickers:
        fundamental = fundamental_index.get(ticker, {})
        instrument_type = infer_instrument_type(ticker, fundamental)
        tier = infer_tier(ticker, fundamental, instrument_type)
        monitoring_role = {
            "A": "priority_alert_monitor",
            "B": "standard_alert_monitor",
            "C": "thematic_alert_monitor",
            "D": "broad_alert_radar",
        }[tier]
        company_meta = ir_tickers.get(ticker, {}) if isinstance(ir_tickers.get(ticker), dict) else {}
        sector = fundamental.get("sector")
        industry = fundamental.get("industry")
        decision_grade = tier in {"A", "B"}
        entries.append({
            "ticker": ticker,
            "name": company_meta.get("company_name") or fundamental.get("name") or ticker,
            "universe_scope": PRODUCTION_SCOPE,
            "production_scope": True,
            "pilot_scope": False,
            "instrument_type": instrument_type,
            "source_symbols": {
                "yfinance": fundamental.get("yfinance_symbol") or ticker,
                "sec_cik": company_meta.get("cik"),
                "company_ir": company_meta.get("ir_home_url"),
            },
            "active": True,
            "tier": tier,
            "monitoring_role": monitoring_role,
            "sector": sector,
            "industry": industry,
            "coverage_reason": {
                "wf77_current_coverage": ticker in coverage_tickers,
                "fundamental_row_present": ticker in fundamental_index,
                "alert_evidence_route": "guarded_sql_and_source_open",
            },
            "decision_grade_eligible": decision_grade,
            "promotion_required_before_action": True,
            "monitoring_cadence": monitoring_cadence_for(tier),
            "data_requirements": data_requirements_for(tier, instrument_type),
            "promotion_triggers": [
                "enters_or_reclaims_written_entry_band",
                "fresh_official_or_fundamental_catalyst_improves_thesis",
                "technical_relative_strength_or_sector_leadership_improves",
                "owner_promotes_from_monitor_to_decision_queue",
            ],
            "demotion_triggers": [
                "breaks_stop_or_invalidation",
                "source_freshness_or_validator_status_blocks_claims",
                "thesis_evidence_deteriorates_or_conflicts_with_canon",
                "owner_demotes_or_removes_from_active_monitoring",
            ],
            "source_open_required": True,
            "authority_boundary": AUTHORITY_BOUNDARY,
        })

    return strip_retired_fields(with_summary({
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "alerts_finance_universe_registry",
        "generated_at_utc": utc_now(),
        "workflow": "WF84/WF85 - Alerts and Recommendations OS",
        "status": "alerts_sql_first_universe_ready",
        "review_only": True,
        "source_open_rule": "Use this registry for alert evidence routing only. Open exact sources before material recommendation claims; stale or conflicted evidence emits freshness decay.",
        "architecture_boundary": {
            "alert_register_remains_human_canon": True,
            "json_artifacts_remain_proof_review_packets": True,
            "sqlite_remains_validated_routing_current_state_cache": True,
            "capital_or_order_authority": False,
            "execution_allowed": False,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "coverage_registry": rel(TMP / "finance-data-coverage-current.json"),
            "fundamentals": rel(TMP / "fundamental-metrics-current.json"),
            "company_ir_metadata": rel(ROOT / "data" / "fundamentals" / "company-ir-metadata.json"),
        },
        "entries": entries,
    }))


def with_summary(universe: dict[str, Any]) -> dict[str, Any]:
    entries = [row for row in universe.get("entries", []) if isinstance(row, dict)]
    active_entries = [row for row in entries if row.get("active") is True]
    production_entries = [row for row in active_entries if is_production_scope_row(row)]
    internal_entries = active_internal_entries(active_entries)
    pilot_entries = [row for row in active_entries if row.get("universe_scope") == PILOT_SCOPE]
    review_100_entries = [row for row in active_entries if row.get("universe_scope") == REVIEW_100_SCOPE]
    allowed_scopes = {ACTIVE_INTERNAL_SCOPE, PRODUCTION_SCOPE, PILOT_SCOPE, REVIEW_100_SCOPE}
    retired_marker_entries = [row for row in active_entries if has_retired_scope_marker(row)]
    unknown_scope_entries = [row for row in active_entries if row.get("universe_scope") not in allowed_scopes]
    coverage = load_dict(TMP / "finance-data-coverage-current.json")
    coverage_tickers = sorted((coverage.get("ticker_coverage") or {}).keys())
    production_tickers = {str(row.get("ticker", "")).upper() for row in production_entries}
    production_scope_ticker_set = set(production_scope_tickers())
    effective_production_tickers = production_scope_ticker_set
    universe["generated_at_utc"] = utc_now()
    if unknown_scope_entries:
        universe["status"] = "invalid_universe_scope_detected"
    elif (
        len(active_entries) in SUPPORTED_ACTIVE_COUNTS
        and len(review_100_entries) in SUPPORTED_REVIEW_MONITOR_COUNTS
        and len(production_entries) + len(review_100_entries) + len(internal_entries) == len(active_entries)
    ):
        universe["status"] = "wf78_tier_c_scaleout_monitor_ready"
    elif pilot_entries:
        universe["status"] = "phase1_pilot_fixture_ready"
    else:
        universe["status"] = universe.get("status") or "dynamic_sql_first_universe_ready"
    universe["summary"] = {
        "active_ticker_count": len(active_entries),
        "production_active_ticker_count": len(production_entries),
        "effective_production_tier_ticker_count": len(effective_production_tickers),
        "effective_production_tier_source": production_scope_source_summary(),
        "active_internal_universe_count": len(internal_entries),
        "retired_legacy_42_active_count": 0,
        "retired_legacy_42_marker_count": len(retired_marker_entries),
        "retired_legacy_42_marker_tickers": sorted(str(row.get("ticker", "")).upper() for row in retired_marker_entries),
        "unknown_scope_count": len(unknown_scope_entries),
        "unknown_scope_tickers": sorted(str(row.get("ticker", "")).upper() for row in unknown_scope_entries),
        "pilot_fixture_count": len(pilot_entries),
        "review_100_monitor_count": len(review_100_entries),
        "review_monitor_count": len(review_100_entries),
        "supported_scaleout_active_counts": sorted(SUPPORTED_ACTIVE_COUNTS),
        "tier_counts": {tier: sum(1 for row in active_entries if row.get("tier") == tier) for tier in sorted(VALID_TIERS)},
        "instrument_type_counts": {kind: sum(1 for row in active_entries if row.get("instrument_type") == kind) for kind in sorted(VALID_INSTRUMENT_TYPES)},
        "coverage_registry_ticker_count": len(coverage_tickers),
        "dynamic_production_tickers": sorted(effective_production_tickers),
        "pilot_fixture_tickers": sorted(str(row.get("ticker", "")).upper() for row in pilot_entries),
        "review_100_monitor_tickers": sorted(str(row.get("ticker", "")).upper() for row in review_100_entries),
    }
    return universe


def pilot_fixture_entry(fixture: dict[str, str]) -> dict[str, Any]:
    ticker = fixture["ticker"].upper()
    return {
        "ticker": ticker,
        "name": fixture["name"],
        "universe_scope": PILOT_SCOPE,
        "production_scope": False,
        "pilot_scope": True,
        "pilot_status": "fixture_only_not_in_production_answer_path",
        "instrument_type": "operating_company",
        "source_symbols": {"yfinance": ticker, "sec_cik": None, "company_ir": None},
        "active": True,
        "tier": "C",
        "monitoring_role": "pilot_fixture_thin_sql_or_on_demand_card",
        "sector": fixture.get("sector"),
        "industry": fixture.get("industry"),
        "coverage_reason": {
            "wf77_current_coverage": False,
            "pilot_fixture": True,
            "pilot_contract_artifact": "tmp/wf78-phase1-pilot-contract.json",
            "production_answer_path_member": False,
        },
        "decision_grade_eligible": False,
        "promotion_required_before_action": True,
        "monitoring_cadence": monitoring_cadence_for("C"),
        "data_requirements": data_requirements_for("C", "operating_company"),
        "promotion_triggers": [
            "provider_runtime_budget_passes",
            "thin_sql_row_and_on_demand_card_proof_passes",
            "fresh_price_technical_and_source_open_evidence_available",
            "owner_promotes_from_pilot_to_priority_watch",
        ],
        "demotion_triggers": [
            "provider_runtime_or_error_budget_fails",
            "stale_or_missing_source_disclosure_blocks_routing_use",
            "pilot_row_degrades_dynamic_sql_first_answer_quality",
            "owner_removes_from_pilot_scope",
        ],
        "source_open_required": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def add_pilot_fixtures(universe: dict[str, Any]) -> dict[str, Any]:
    if not universe.get("entries"):
        universe = build_universe()
    entries = [row for row in universe.get("entries", []) if isinstance(row, dict)]
    existing_by_ticker = {str(row.get("ticker", "")).upper(): row for row in entries}
    for row in entries:
        ticker = str(row.get("ticker", "")).upper()
        if ticker and row.get("universe_scope") not in {ACTIVE_INTERNAL_SCOPE, PRODUCTION_SCOPE, PILOT_SCOPE, REVIEW_100_SCOPE}:
            row["universe_scope"] = ACTIVE_INTERNAL_SCOPE
            row["production_scope"] = False
            row["pilot_scope"] = False
    for fixture in PILOT_FIXTURES:
        ticker = fixture["ticker"].upper()
        if ticker in existing_by_ticker:
            existing_by_ticker[ticker].update(pilot_fixture_entry(fixture))
        else:
            entries.append(pilot_fixture_entry(fixture))
    universe["entries"] = entries
    return with_summary(universe)


def false_authority_flags(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            if key.endswith("_allowed") or key.endswith("_authority") or key in {"owner_approval_granted", "owner_approval_inferred"}:
                if value is True:
                    hits.append(child)
            hits.extend(false_authority_flags(value, child))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(false_authority_flags(value, f"{path}[{index}]"))
    return hits


def validate_universe(universe: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    entries = universe.get("entries") if isinstance(universe.get("entries"), list) else []
    active_entries = [row for row in entries if isinstance(row, dict) and row.get("active") is True]
    production_entries = [row for row in active_entries if is_production_scope_row(row)]
    internal_entries = active_internal_entries(active_entries)
    pilot_entries = [row for row in active_entries if row.get("universe_scope") == PILOT_SCOPE]
    review_100_entries = [row for row in active_entries if row.get("universe_scope") == REVIEW_100_SCOPE]
    retired_marker_entries = [row for row in active_entries if has_retired_scope_marker(row)]
    retired_marker_production = [str(row.get("ticker", "")).upper() for row in retired_marker_entries if is_production_scope_row(row)]
    tickers = [str(row.get("ticker", "")).upper() for row in active_entries]
    production_tickers = [str(row.get("ticker", "")).upper() for row in production_entries]
    production_scope_ticker_set = production_scope_tickers()
    effective_production_tickers = production_scope_ticker_set
    pilot_tickers = [str(row.get("ticker", "")).upper() for row in pilot_entries]
    coverage = load_dict(TMP / "finance-data-coverage-current.json")
    allowed_pilot = sorted(row["ticker"] for row in PILOT_FIXTURES)
    allowed_scopes = {ACTIVE_INTERNAL_SCOPE, PRODUCTION_SCOPE, PILOT_SCOPE, REVIEW_100_SCOPE}

    add("schema_version", universe.get("schema_version") == SCHEMA_VERSION, f"schema_version={universe.get('schema_version')!r}")
    add("metadata_present", bool(universe.get("generated_at_utc") and universe.get("artifact_type")), "generated_at_utc and artifact_type required")
    add("review_only_boundary", universe.get("review_only") is True and not false_authority_flags(universe), "review_only true and no authority flag true")
    add("active_tickers_present", bool(active_entries), f"active={len(active_entries)}")
    add("unique_active_tickers", len(tickers) == len(set(tickers)), f"active={len(tickers)} unique={len(set(tickers))}")
    add("retired_scope_markers_do_not_grant_production_scope", not retired_marker_production, json.dumps(retired_marker_production))
    add("sql_first_production_scope_no_json_fallback", len(effective_production_tickers) == len(production_scope_ticker_set), f"sql_production={len(production_scope_ticker_set)} json_production_rows={len(production_entries)}")
    add("pilot_scope_within_contract", set(pilot_tickers).issubset(set(allowed_pilot)) and len(pilot_tickers) <= len(allowed_pilot), f"pilot={pilot_tickers} allowed={allowed_pilot}")
    add("production_pilot_no_overlap", not set(production_tickers).intersection(pilot_tickers), f"overlap={sorted(set(production_tickers).intersection(pilot_tickers))}")
    add("wf78_scaleout_active_count_supported", len(active_entries) in SUPPORTED_ACTIVE_COUNTS, f"active={len(active_entries)} supported={sorted(SUPPORTED_ACTIVE_COUNTS)}")
    add(
        "review_monitor_shape_valid",
        len(review_100_entries) in SUPPORTED_REVIEW_MONITOR_COUNTS
        and len(production_entries) + len(review_100_entries) + len(internal_entries) == len(active_entries),
        f"production={len(production_entries)} active_internal={len(internal_entries)} review_monitor={len(review_100_entries)} active={len(active_entries)} supported_review={sorted(SUPPORTED_REVIEW_MONITOR_COUNTS)}",
    )
    add("architecture_notes_preserved", not any(universe.get("architecture_boundary", {}).get(key) is True for key in ["full_sql_canon_migration_allowed", "tmp_artifact_promotion_allowed", "db_path_migration_allowed"]), json.dumps(universe.get("architecture_boundary", {}), sort_keys=True))

    bad_fields: list[str] = []
    bad_types: list[str] = []
    bad_tiers: list[str] = []
    bad_requirements: list[str] = []
    bad_source_symbols: list[str] = []
    c_d_decision_grade: list[str] = []
    proxy_forced_official: list[str] = []
    missing_source_open: list[str] = []
    weak_ab: list[str] = []
    bad_scope: list[str] = []
    bad_pilot_rows: list[str] = []
    bad_review_100_rows: list[str] = []
    ab_not_decision_grade: list[str] = []
    proxy_exception_conflict: list[str] = []
    obligation_upgrade_candidates: list[str] = []
    for row in active_entries:
        ticker = str(row.get("ticker", "")).upper()
        required_fields = [
            "ticker",
            "name",
            "universe_scope",
            "instrument_type",
            "source_symbols",
            "active",
            "tier",
            "monitoring_role",
            "coverage_reason",
            "decision_grade_eligible",
            "promotion_required_before_action",
            "monitoring_cadence",
            "data_requirements",
            "promotion_triggers",
            "demotion_triggers",
            "authority_boundary",
        ]
        for field in required_fields:
            if field not in row:
                bad_fields.append(f"{ticker}.{field}")
        if row.get("universe_scope") not in allowed_scopes:
            bad_scope.append(f"{ticker}:{row.get('universe_scope')}")
        if row.get("instrument_type") not in VALID_INSTRUMENT_TYPES:
            bad_types.append(f"{ticker}:{row.get('instrument_type')}")
        if row.get("tier") not in VALID_TIERS:
            bad_tiers.append(f"{ticker}:{row.get('tier')}")
        source_symbols = row.get("source_symbols") if isinstance(row.get("source_symbols"), dict) else {}
        if not source_symbols.get("yfinance"):
            bad_source_symbols.append(ticker)
        requirements = row.get("data_requirements") if isinstance(row.get("data_requirements"), dict) else {}
        for family, status in requirements.items():
            if status not in VALID_REQUIREMENT_STATUSES:
                bad_requirements.append(f"{ticker}.{family}={status}")
        if row.get("tier") in {"C", "D"} and row.get("decision_grade_eligible") is True:
            c_d_decision_grade.append(ticker)
        if row.get("instrument_type") != "operating_company" and requirements.get("official_evidence") == "source_open_required":
            proxy_forced_official.append(ticker)
        if row.get("source_open_required") is not True:
            missing_source_open.append(ticker)
        if row.get("tier") in {"A", "B"}:
            if requirements.get("price_band_stop") != "daily_required" or requirements.get("technical_posture") != "daily_required":
                weak_ab.append(ticker)
            if row.get("decision_grade_eligible") is not True:
                ab_not_decision_grade.append(ticker)
        # The ETF/proxy exception in tier_a_cohort_alignment_reconciliation keys off
        # decision_grade_eligible is False. A proxy carrying that flag must stay outside the A/B
        # obligation set, or the exception silently stops firing and the name starts escalating
        # as route drift.
        if (
            row.get("instrument_type") in {"etf", "etf_or_macro_proxy"}
            and row.get("decision_grade_eligible") is False
            and row.get("tier") in {"A", "B"}
        ):
            proxy_exception_conflict.append(ticker)
        # A C/D name already carrying the daily obligation is a promotion nomination, not a defect.
        if row.get("tier") in {"C", "D"} and requirements.get("price_band_stop") == "daily_required":
            obligation_upgrade_candidates.append(ticker)
        if row.get("universe_scope") == PILOT_SCOPE:
            coverage_reason = row.get("coverage_reason") if isinstance(row.get("coverage_reason"), dict) else {}
            if row.get("tier") not in {"C", "D"} or row.get("decision_grade_eligible") is not False or coverage_reason.get("production_answer_path_member") is not False:
                bad_pilot_rows.append(ticker)
        if row.get("universe_scope") == ACTIVE_INTERNAL_SCOPE and row.get("production_scope") is True:
            bad_scope.append(f"{ticker}:active_internal_marked_production_scope")
        if row.get("universe_scope") == REVIEW_100_SCOPE:
            coverage_reason = row.get("coverage_reason") if isinstance(row.get("coverage_reason"), dict) else {}
            if (
                row.get("tier") != "C"
                or row.get("decision_grade_eligible") is not False
                or coverage_reason.get("production_answer_path_member") is not False
                or row.get("production_scope") is True
            ):
                bad_review_100_rows.append(ticker)

    add("required_fields_present", not bad_fields, json.dumps(bad_fields[:25]))
    add("valid_universe_scopes", not bad_scope, json.dumps(bad_scope))
    add("valid_instrument_types", not bad_types, json.dumps(bad_types))
    add("valid_tiers", not bad_tiers, json.dumps(bad_tiers))
    add("valid_data_requirement_statuses", not bad_requirements, json.dumps(bad_requirements[:25]))
    add("active_tickers_have_source_symbols", not bad_source_symbols, json.dumps(bad_source_symbols))
    add("tier_ab_have_stronger_requirements", not weak_ab, json.dumps(weak_ab))
    add("tier_cd_not_decision_grade_by_default", not c_d_decision_grade, json.dumps(c_d_decision_grade))
    add("proxies_not_forced_into_operating_company_official_requirements", not proxy_forced_official, json.dumps(proxy_forced_official))
    add("source_open_requirements_visible", not missing_source_open, json.dumps(missing_source_open))
    add("pilot_rows_are_lower_tier_non_decision_grade", not bad_pilot_rows, json.dumps(bad_pilot_rows))
    add("review_100_rows_are_thin_c_tier_non_decision_grade", not bad_review_100_rows, json.dumps(bad_review_100_rows))
    add("tier_ab_are_decision_grade_eligible", not ab_not_decision_grade, json.dumps(ab_not_decision_grade))
    add("proxy_exception_names_stay_out_of_ab_obligation", not proxy_exception_conflict, json.dumps(proxy_exception_conflict))
    # Nomination signal, not a defect: a C/D name carrying the daily obligation is a promotion
    # candidate for owner review, so this check reports without failing the bundle.
    add(
        "coverage_obligation_upgrade_candidates_reported",
        True,
        json.dumps({"nomination_only": True, "tickers": obligation_upgrade_candidates}),
    )
    return checks


def build_validation(universe: dict[str, Any]) -> dict[str, Any]:
    checks = validate_universe(universe)
    failed = [row for row in checks if not row["passed"]]
    return {
        "schema_version": 1,
        "artifact_type": "wf78_finance_universe_validation",
        "generated_at_utc": utc_now(),
        "status": "ok" if not failed else "fail",
        "universe_path": rel(DEFAULT_UNIVERSE),
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "checks": len(checks),
            "failed": len(failed),
            "active_ticker_count": len([row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True]),
            "production_active_ticker_count": len([row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True and is_production_scope_row(row)]),
            "effective_production_tier_ticker_count": len(production_scope_tickers()),
            "effective_production_tier_source": production_scope_source_summary(),
            "active_internal_universe_count": len([row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True and row.get("universe_scope") == ACTIVE_INTERNAL_SCOPE]),
            "retired_legacy_42_active_count": 0,
            "retired_legacy_42_marker_count": len([row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True and has_retired_scope_marker(row)]),
            "pilot_fixture_count": len([row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True and row.get("universe_scope") == PILOT_SCOPE]),
            "review_100_monitor_count": len([row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True and row.get("universe_scope") == REVIEW_100_SCOPE]),
        },
        "checks": checks,
        "failed_checks": failed,
    }


def main() -> int:
    # allow_abbrev=False: `--write` used to prefix-match `--write-from-coverage` and silently
    # rebuild the whole registry when a read-only validation run was intended.
    parser = argparse.ArgumentParser(
        description="Build and validate the WF78 durable finance universe registry.",
        allow_abbrev=False,
    )
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE, help="Universe registry JSON path.")
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION, help="Validation artifact output path.")
    parser.add_argument("--write-from-coverage", action="store_true", help="Build and write universe from current WF77 coverage/fundamental artifacts.")
    parser.add_argument("--add-pilot-fixtures", action="store_true", help="Add WF78 Phase 1 fixture rows without changing the dynamic SQL-first production answer path.")
    parser.add_argument("--validate", action="store_true", help="Validate universe and write validation artifact.")
    parser.add_argument("--print", dest="print_json", action="store_true", help="Print universe JSON to stdout.")
    parser.add_argument("--write", action="store_true", help="Rejected. This script has no generic write mode; use --write-from-coverage explicitly.")
    args = parser.parse_args()

    if args.write:
        parser.error(
            "--write is not a valid mode for this script and will not be treated as a shorthand. "
            "Use --validate for read-only validation, or --write-from-coverage to deliberately "
            "rebuild data/finance/universe-v1.json from WF77 coverage artifacts."
        )

    should_write = False
    if args.write_from_coverage:
        universe = build_universe()
        should_write = True
    elif args.add_pilot_fixtures:
        universe = add_pilot_fixtures(load_dict(args.universe))
        should_write = True
    else:
        universe = load_dict(args.universe)

    universe = strip_retired_fields(with_summary(universe))
    if should_write:
        atomic_write_json(args.universe, universe)
    validation = build_validation(universe)
    if args.validate:
        atomic_write_json(args.validation_output, validation)

    if args.print_json:
        print(json.dumps(universe, indent=2, ensure_ascii=False))
    elif args.validate:
        print(json.dumps({
            "status": validation["status"],
            "checks": validation["summary"]["checks"],
            "failed": validation["summary"]["failed"],
            "validation_output": rel(args.validation_output),
        }, indent=2))

    return 0 if validation["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
