from __future__ import annotations

from board_state_contract import legacy_state
import json
from datetime import datetime, timezone
from typing import Any

from dashboard_core import (
    TMP,
    WORKSPACE,
    load_json,
    write_json,
    parse_date,
    get_path,
    normalize_records,
    get_market_session,
    assess_source,
    build_provenance,
    get_vault_freshness,
    summarize_source_freshness,
    status_worse,
    status_badge,
    fmt_num,
    fmt_pct,
    fmt_date_label,
    describe_overall_status,
)
from dashboard_validation import build_validation
from artifact_index import DEFAULT_DB as ARTIFACT_INDEX_DB, connect as connect_artifact_index, validate_index as validate_artifact_index
from sql_consumer_authority_guard import (
    NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT,
    NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES,
    active_sql_canon_approved_keys,
    build_phase4a_sql_consumer_authority_guard,
)
from market_data_utils import guard_dict_or_empty

HISTORY_PATH = TMP / "deployment-history.json"
ENTRY_BAND_REPORTS_DIR = WORKSPACE / "tmp" / "entry-band-reports"
WF63_READINESS_REPORT_PATH = TMP / "alpaca-paper-readiness" / "wf63-readiness-report.json"
WF63_PHASE_0_POLICY_PATH = TMP / "alpaca-paper-readiness" / "phase-0-policy.json"
PAPER_PILOT_STATUS_SURFACE_PATH = TMP / "alpaca-paper-readiness" / "paper-pilot-status-surface.json"
RESEARCH_FRESHNESS_OPPORTUNITY_PATH = TMP / "research-freshness-opportunity-review.json"
WEEKLY_POSITIONING_REVIEW_PATH = WORKSPACE / "05. Intelligence" / "Weekly Positioning Review.md"
NEAR_BAND_THRESHOLD_PCT = 5.0
ETF_OR_PROXY = {"SLV", "TLT", "XLI", "XLB", "XLC", "PAVE", "XLF", "XLE", "ITA", "VAW", "VXUS"}
ETF_OR_PROXY_ROLES = {"etf_monitor"}

# Wording the Command Center must NEVER use about WF63 while paper-submit is
# still blocked. These phrases imply OpenClaw has crossed an authority gate it
# has not crossed. The shape validator in _validate_payload_shape rejects them.
WF63_FORBIDDEN_LIVE_TRADING_PHRASES = (
    "paper trading active",
    "paper trading is active",
    "paper trading has started",
    "paper trading started",
    "paper orders enabled",
    "paper orders ready",
    "paper submit enabled",
    "paper submit allowed",
    "submitting paper orders",
    "trading is live",
    "trading is enabled",
    "order submission allowed",
    "order submission enabled",
    "alpaca connected",
    "alpaca api active",
    "approved for paper trading",
    "owner approved paper",
)

# Required payload-shape contract — keys the dashboard view layer relies on.
# Any time these are renamed in the payload assembler, update here too or the
# dashboard fails silent. Validation runs at the end of build_payload and
# emits warnings into the existing validation block.
REQUIRED_TODAY_ACTION_KEYS = ("deployable", "promotionReview", "almost", "blocked", "earningsPending", "riskOff")
REQUIRED_ACTION_CARD_KEYS = ("ticker", "close", "entryBand", "stop", "posture")
REQUIRED_DEPLOYMENT_RECORD_KEYS = (
    "ticker", "state", "close", "bandLabel", "bandLow", "bandHigh",
    "bandStatus", "bandPositionPct", "stop", "stopDistPct", "posture", "referenceBand", "executionBand",
)
REQUIRED_MACRO_REGIME_KEYS = ("regime_label", "policy_pillar", "credit_pillar", "breadth_pillar")
SQL_AUTHORITY_BOUNDARY = "derived_review_only_index_not_canon_not_apply"
SQL_CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
PHASE4A_SQL_CANON_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
PHASE4A_APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)
PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY = "portfolio:source_freshness_classification"
ENTRY_STOP_PILOT_WORKER_PATH = TMP / "wf72-entry-stop-sql-activation-pilot-worker.json"


def _safe_read_text(path: Any) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _load_phase4a_sql_canon_metadata(fallback_values_by_key: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read the bounded Phase 4A SQL canon cache for dashboard proof metadata.

    SQL is authoritative only for the exact approved metadata keys and only when
    the cache has been explicitly activated into the Phase 4A boundary and the
    consumer-side authority guard passes. Any degradation falls back to
    generated-artifact/Markdown proof surfaces.
    """
    approved_keys = active_sql_canon_approved_keys()
    base = {
        "enabled": True,
        "consumerFamily": "dashboard proof metadata",
        "dbPath": "tmp/veritas-canon-cache.sqlite",
        "approvedKeys": list(approved_keys),
        "authorityBoundary": PHASE4A_SQL_CANON_BOUNDARY,
        "sqlIsCanon": False,
        "sqlReadAllowed": False,
        "proofMetadataAuthority": False,
        "boundedSqlProofCache": True,
        "status": "degraded_fallback_required",
        "readMode": "not_opened_missing_db",
        "fallbackRequired": True,
        "canonicalNoteMutationAllowed": False,
        "portfolioMutationAllowed": False,
        "ownerApprovalInferred": False,
        "tradeOrAccountActionAllowed": False,
        "paperTradeAuthorityAllowed": False,
        "liveTradeAuthorityAllowed": False,
        "dashboardBehaviorChangeAllowed": False,
        "rows": {},
        "portfolioSourceFreshnessShadowMetadata": _portfolio_source_freshness_shadow_metadata(fallback_values_by_key),
        "neutralDeploymentEvidenceShadowMetadata": _neutral_deployment_evidence_shadow_metadata(fallback_values_by_key, None),
        "issues": [],
    }
    guard = build_phase4a_sql_consumer_authority_guard(fallback_values_by_key=fallback_values_by_key)
    base["authorityGuard"] = guard
    base["portfolioSourceFreshnessShadowMetadata"] = guard.get("portfolio_source_freshness_shadow_metadata") or base["portfolioSourceFreshnessShadowMetadata"]
    base["neutralDeploymentEvidenceShadowMetadata"] = guard.get("neutral_deployment_evidence_shadow_metadata") or base["neutralDeploymentEvidenceShadowMetadata"]
    base["readMode"] = (guard.get("cache_read") or {}).get("read_mode") or base["readMode"]
    base["integrityCheck"] = (guard.get("cache_read") or {}).get("integrity_check")
    base["meta"] = guard.get("cache_meta") or {}
    if guard.get("status") != "ok" or not guard.get("sql_read_allowed"):
        base["issues"].extend(guard.get("issues") or ["phase4a SQL consumer authority guard blocked SQL read"])
        return base
    row_map: dict[str, Any] = {}
    for row in guard.get("cache_rows") or []:
        key = f"{row.get('scope')}:{row.get('field_name')}"
        if key in approved_keys:
            row_map[key] = row
    base["rows"] = row_map
    base["status"] = "ok"
    base["sqlIsCanon"] = False
    base["sqlReadAllowed"] = True
    base["proofMetadataAuthority"] = True
    base["authorityWording"] = "bounded SQL proof-metadata cache; not canonical portfolio truth, owner approval, apply authority, or execution authority"
    return base


def _entry_stop_reference_fallback_values() -> dict[str, Any]:
    """Fallback values for gated WF72 entry/stop reference metadata."""
    try:
        data = json.loads(ENTRY_STOP_PILOT_WORKER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    fields = data.get("candidate_fields") or []
    out: dict[str, Any] = {}
    for row in data.get("candidate_rows") or []:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        ticker = str(row.get("ticker")).upper()
        for field in fields:
            if field in row:
                out[f"{ticker}:{field}"] = row.get(field)
    return out


def _portfolio_source_freshness_shadow_metadata(fallback_values_by_key: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback_values_by_key = fallback_values_by_key or {}
    state = fallback_values_by_key.get("portfolio:source_freshness_state")
    state = state if isinstance(state, dict) else {}
    classification = fallback_values_by_key.get(PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY) or state.get("classification")
    return {
        "key": PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY,
        "status": "shadow_only_manual_dependency_metadata",
        "classification": classification,
        "trustLevel": state.get("confidence_ceiling") or state.get("trust_level"),
        "path": state.get("path"),
        "metadataOnly": True,
        "degraded": classification == "manual_dependency",
        "manualDependency": classification == "manual_dependency",
        "sqlCanonActivationAllowed": False,
        "sqlReadAllowedForKey": False,
        "cacheRowAllowed": False,
        "normalizationToFreshOrCurrentAllowed": False,
        "dashboardBehaviorChangeAllowed": False,
        "canonicalNoteMutationAllowed": False,
        "portfolioMutationAllowed": False,
        "ownerApprovalInferred": False,
        "tradeOrAccountActionAllowed": False,
        "paperTradeAuthorityAllowed": False,
        "liveTradeAuthorityAllowed": False,
        "authorityWording": "Portfolio source freshness is degraded/manual-dependency trust metadata only; it is not a SQL-canon active key, portfolio truth, approval, apply authority, or execution authority.",
    }


def _neutral_deployment_evidence_shadow_metadata(
    fallback_values_by_key: dict[str, Any] | None = None,
    guard_shadow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback_values_by_key = fallback_values_by_key or {}
    values = fallback_values_by_key.get("deployment:evidence_completeness_display_values")
    values = values if isinstance(values, list) else list(NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES)
    return {
        **NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT,
        **(guard_shadow or {}),
        "fieldName": "evidence_completeness_display",
        "fallbackValues": values,
        "metadataOnly": True,
        "displayOnly": True,
        "sqlCanonActivationAllowed": False,
        "sqlReadAllowedForKey": False,
        "cacheRowAllowed": False,
        "currentValueMigrationAllowed": False,
        "currentFieldPermanentHold": True,
        "dashboardBehaviorChangeAllowed": False,
        "canonicalNoteMutationAllowed": False,
        "portfolioMutationAllowed": False,
        "ownerApprovalInferred": False,
        "tradeOrAccountActionAllowed": False,
        "paperTradeAuthorityAllowed": False,
        "liveTradeAuthorityAllowed": False,
        "authorityWording": "Neutral deployment evidence/completeness display metadata only; it does not drive action buckets, recommendations, approval, or execution authority.",
    }


def _sql_canon_proof_for_ticker(ticker: str, sql_canon: dict[str, Any], fallback_values: dict[str, Any]) -> dict[str, Any] | None:
    if ticker.upper() != "NVDA":
        return None
    fields: dict[str, Any] = {}
    for key in PHASE4A_APPROVED_KEYS:
        scope, field_name = key.split(":", 1)
        if scope != ticker.upper():
            continue
        row = (sql_canon.get("rows") or {}).get(key) or {}
        sql_value = row.get("field_value")
        fallback_value = fallback_values.get(field_name)
        use_sql = sql_canon.get("status") == "ok" and sql_value not in {None, ""}
        fields[field_name] = {
            "key": key,
            "effectiveValue": sql_value if use_sql else fallback_value,
            "sqlValue": sql_value,
            "fallbackValue": fallback_value,
            "readSource": "sql_canon" if use_sql else "generated_artifact_or_markdown_fallback",
            "sourceArtifactPath": row.get("source_artifact_path"),
            "ownerMirrorNotePath": row.get("owner_mirror_note_path"),
            "lastReconciledAtUtc": row.get("last_reconciled_at_utc"),
            "authorityBoundary": row.get("authority_boundary") or sql_canon.get("authorityBoundary"),
        }
    return {
        "consumerFamily": sql_canon.get("consumerFamily"),
        "status": sql_canon.get("status"),
        "sqlIsCanon": False,
        "sqlReadAllowed": bool(sql_canon.get("sqlReadAllowed")),
        "proofMetadataAuthority": bool(sql_canon.get("proofMetadataAuthority")),
        "authorityWording": sql_canon.get("authorityWording") or "SQL proof metadata only; not canonical portfolio truth or approval authority",
        "authorityBoundary": sql_canon.get("authorityBoundary"),
        "fallbackRequired": True,
        "metadataOnly": True,
        "dashboardBehaviorChangeAllowed": False,
        "canonicalNoteMutationAllowed": False,
        "portfolioMutationAllowed": False,
        "ownerApprovalInferred": False,
        "tradeOrAccountActionAllowed": False,
        "fields": fields,
        "issues": sql_canon.get("issues") or [],
    }


def _research_reviews_by_ticker(review_raw: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in normalize_records((review_raw or {}).get("candidate_reviews"))
        if row.get("ticker")
    }


GREEN_MACHINE_STATES = {"DEPLOYABLE", "DEPLOYABLE NOW", "GREEN"}
AUTHORITY_CONFLICT_PHRASES = (
    "trigger not live",
    "approval on hold",
    "approval-on-hold",
    "below formal band",
    "below stop",
    "repair",
    "frozen",
    "event freeze",
    "do not treat as deployable",
    "not deployable-now",
    "not deployable now",
    "watch-lane",
    "secondary review only",
)


def _contains_conflict_phrase(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(phrase in lowered for phrase in AUTHORITY_CONFLICT_PHRASES)


def _weekly_ticker_conflict(ticker: str, weekly_positioning_text: str) -> bool:
    ticker_l = ticker.lower()
    for line in weekly_positioning_text.splitlines():
        lowered = line.lower()
        if ticker_l in lowered and _contains_conflict_phrase(lowered):
            return True
    return False


def _authority_conflict_meta(
    ticker: str | None,
    research_review: dict[str, Any] | None,
    weekly_positioning_text: str,
    machine_state: str | None = None,
) -> dict[str, Any] | None:
    """Deprecated prose-veto guard.

    Machine state now owns live dashboard/review posture. Stale research or
    weekly prose should become a sync/repair item, not an AUTHORITY CONFLICT
    override. Hard facts still fail closed upstream: below-stop, repair mode,
    stale bands, catalyst blocks, and system stop lines.
    """
    del ticker, research_review, weekly_positioning_text, machine_state
    return None


def _almost_substate(ticker: str | None, action_state: str | None = None) -> dict[str, str] | None:
    state = str(action_state or "").upper()
    if state and state not in {"ALMOST", "ALMOST DEPLOYABLE", "ALMOST / NEAR-EARNINGS CAUTION"}:
        return None
    mapping = {
        "MSFT": ("OWNER_APPROVED_ABOVE_BAND", "Owner approved, above band — wait for reclaim/pullback"),
        "GOOG": ("NOT_YET_PROMOTED_ABOVE_BAND", "Not yet promoted, above band — no-chase wait"),
        "GS": ("NOT_YET_PROMOTED_ABOVE_BAND", "Not yet promoted, above band — no-chase wait"),
        "NVDA": ("EVENT_FREEZE", "Event freeze — near earnings / no-chase wait"),
    }
    value = mapping.get(str(ticker or "").upper())
    if not value:
        return None
    return {"almostSubState": value[0], "displaySubState": value[1]}


def _earnings_unconfirmed(value: Any) -> bool:
    if value is False or value is None:
        return True
    if isinstance(value, str) and value.strip().upper() == "UNCONFIRMED":
        return True
    return False


def _trend_tone(*values: Any) -> str:
    numeric = []
    for value in values:
        try:
            if value is not None:
                numeric.append(float(value))
        except Exception:
            pass
    if not numeric:
        return "info"
    if all(value > 0 for value in numeric):
        return "ok"
    if any(value < -20 for value in numeric):
        return "bad"
    if any(value < 0 for value in numeric):
        return "warn"
    return "info"


def _active_equity_tickers(tracked_universe: dict[str, Any]) -> set[str]:
    return {
        ticker
        for ticker, meta in tracked_universe.items()
        if ticker not in ETF_OR_PROXY
        and isinstance(meta, dict)
        and str(meta.get("coverage_lane") or "").lower() != "macro"
        and str(meta.get("portfolio_role") or "").lower() not in ETF_OR_PROXY_ROLES
    }


def _build_fundamental_trends(fund_raw: dict[str, Any], tracked_universe: dict[str, Any], ir_raw: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = normalize_records(fund_raw.get("rows")) if isinstance(fund_raw, dict) else []
    ir_packets = normalize_records((ir_raw or {}).get("packets")) if isinstance(ir_raw, dict) else []
    ir_by_ticker = {str(packet.get("ticker") or ""): packet for packet in ir_packets if packet.get("ticker")}
    ir_summary = (ir_raw or {}).get("summary") if isinstance(ir_raw, dict) else {}
    active_tickers = _active_equity_tickers(tracked_universe)
    cards: list[dict[str, Any]] = []
    quality_counts: dict[str, int] = {}
    sec_counts: dict[str, int] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "")
        quality = str(row.get("data_quality") or "unknown")
        sec_status = str(((row.get("sec_reconciliation") or {}).get("status")) or "unknown")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        sec_counts[sec_status] = sec_counts.get(sec_status, 0) + 1
        if row.get("instrument_type") != "equity":
            continue
        if ticker not in active_tickers:
            continue
        meta = tracked_universe.get(ticker, {}) if isinstance(tracked_universe.get(ticker), dict) else {}
        ir_packet = ir_by_ticker.get(ticker) or {}
        eps_rec = ir_packet.get("adjusted_eps_reconciliation") or {}
        guidance_rec = ir_packet.get("guidance_reconciliation") or {}
        bridge = ir_packet.get("official_earnings_bridge") or {}
        bridge_adjusted = bridge.get("adjusted_eps") if isinstance(bridge, dict) else {}
        bridge_guidance = bridge.get("guidance") if isinstance(bridge, dict) else {}
        ir_urls = ir_packet.get("source_urls") or {}
        cards.append({
            "ticker": ticker,
            "sector": row.get("sector") or meta.get("sector"),
            "coverageTier": row.get("coverage_tier") or meta.get("coverage_tier"),
            "workflowState": legacy_state(row, "workflow_state") or legacy_state(meta, "workflow_state"),
            "period": f"{row.get('period_end') or '—'} vs {row.get('comparison_period_end') or '—'}",
            "quality": quality,
            "secStatus": sec_status,
            "irStatus": str(((row.get("company_ir_reconciliation") or {}).get("status")) or "unknown"),
            "irPacketStatus": "manual_required" if ir_packet.get("manual_review_required") is True else ("missing" if not ir_packet else "unknown"),
            "adjustedEpsStatus": eps_rec.get("status") or "manual_required",
            "guidanceStatus": guidance_rec.get("status") or "manual_required",
            "officialEarningsBridgeStatus": bridge.get("status") if isinstance(bridge, dict) else "missing",
            "officialEarningsBridgeReviewOnly": bool(bridge.get("review_only")) if isinstance(bridge, dict) else False,
            "officialEarningsBridgeManualRequired": bridge.get("manual_review_required") is True if isinstance(bridge, dict) else True,
            "officialEarningsBridgeSourcePosture": bridge.get("source_posture") if isinstance(bridge, dict) else None,
            "officialAdjustedEpsBridgeStatus": (bridge_adjusted or {}).get("status") or "manual_required",
            "officialGuidanceBridgeStatus": (bridge_guidance or {}).get("status") or "manual_required",
            "officialEarningsReleaseUrl": bridge.get("official_earnings_release_url") if isinstance(bridge, dict) else None,
            "earningsUrl": ir_urls.get("earnings_url"),
            "irHomeUrl": ir_urls.get("ir_home_url"),
            "epsYoY": row.get("eps_yoy_pct"),
            "revenueYoY": row.get("revenue_yoy_pct"),
            "netIncomeYoY": row.get("net_income_yoy_pct"),
            "grossMargin": row.get("gross_margin_pct"),
            "operatingMargin": row.get("operating_margin_pct"),
            "netMargin": row.get("net_margin_pct"),
            "freeCashFlow": row.get("free_cash_flow"),
            "freeCashFlowYoY": row.get("free_cash_flow_yoy_pct"),
            "fcfInterpretation": row.get("fcf_interpretation"),
            "fcfInterpretationNote": row.get("fcf_interpretation_note"),
            "fcfPerShare": row.get("fcf_per_share"),
            "fcfPerSharePrior": row.get("fcf_per_share_prior"),
            "dilutedSharesYoY": row.get("diluted_shares_yoy_pct"),
            "fcfPerShareYoY": row.get("fcf_per_share_yoy_pct"),
            "fcfPerShareYoYBase": row.get("fcf_per_share_yoy_base"),
            "buybackYield": row.get("buyback_yield_pct"),
            "shareRepurchases": row.get("share_repurchases"),
            "netShareRepurchases": row.get("net_share_repurchases"),
            "stockBasedCompensation": row.get("stock_based_compensation"),
            "sbcPctRevenue": row.get("sbc_pct_of_revenue"),
            "sbcPctFcf": row.get("sbc_pct_of_fcf"),
            "dividendsPaid": row.get("dividends_paid"),
            "dividendYield": row.get("dividend_yield_pct"),
            "capitalReturnToFcf": row.get("capital_return_to_fcf_pct"),
            "netDebtIssued": row.get("net_debt_issued"),
            "netDebtInterpretation": row.get("net_debt_interpretation"),
            "shareholderYield": row.get("shareholder_yield_pct"),
            "shareholderYieldPeriod": row.get("shareholder_yield_period"),
            "fcfYield": row.get("fcf_yield_pct"),
            "earningsYield": row.get("earnings_yield_pct"),
            "roicProxy": row.get("roic_proxy_pct"),
            "evToEbitdaProxy": row.get("ev_to_ebitda_proxy"),
            "evToFcfProxy": row.get("ev_to_fcf_proxy"),
            "valuationContext": row.get("valuation_context"),
            "capitalAllocationQuality": row.get("capital_allocation_quality"),
            "capitalAllocationAnomalies": row.get("capital_allocation_anomalies") or [],
            "capitalAllocationAnomalyCount": row.get("capital_allocation_anomaly_count"),
            "debtToAnnualizedEbitda": row.get("debt_to_annualized_ebitda"),
            "wf65BankNativeVersion": row.get("wf65_bank_native_version"),
            "bankNativeStatus": row.get("bank_native_status"),
            "bankNativeSecStatus": row.get("bank_native_sec_status"),
            "bankNativeIrStatus": row.get("bank_native_ir_status"),
            "bankNativeAutoResolvedCount": row.get("bank_native_auto_resolved_count"),
            "bankNativeManualRequiredCount": row.get("bank_native_manual_required_count"),
            "bankNativeNote": row.get("bank_native_note"),
            "cet1Ratio": row.get("cet1_ratio"),
            "cet1RatioTrust": row.get("cet1_ratio_trust"),
            "cet1RatioNote": row.get("cet1_ratio_note"),
            "cet1RatioStandardized": row.get("cet1_ratio_standardized"),
            "cet1RatioAdvanced": row.get("cet1_ratio_advanced"),
            "cet1RatioBasis": row.get("cet1_ratio_basis"),
            "cet1RatioSourceUrl": row.get("cet1_ratio_source_url"),
            "tier1Ratio": row.get("tier1_ratio"),
            "tier1RatioTrust": row.get("tier1_ratio_trust"),
            "tier1RatioNote": row.get("tier1_ratio_note"),
            "tier1RatioStandardized": row.get("tier1_ratio_standardized"),
            "tier1RatioAdvanced": row.get("tier1_ratio_advanced"),
            "tier1RatioBasis": row.get("tier1_ratio_basis"),
            "tier1RatioSourceUrl": row.get("tier1_ratio_source_url"),
            "riskBasedCapitalSourceUrl": row.get("risk_based_capital_source_url"),
            "riskBasedCapitalSourceSection": row.get("risk_based_capital_source_section"),
            "riskBasedCapitalNoDerivedRatio": row.get("risk_based_capital_no_derived_ratio"),
            "riskBasedCapitalPrimaryFramework": row.get("risk_based_capital_primary_framework"),
            "tier1LeverageRatio": row.get("tier1_leverage_ratio"),
            "tier1LeverageRatioTrust": row.get("tier1_leverage_ratio_trust"),
            "tier1LeverageRatioNote": row.get("tier1_leverage_ratio_note"),
            "tbvPerShare": row.get("tbv_per_share"),
            "tbvPerShareTrust": row.get("tbv_per_share_trust"),
            "tbvPerShareSourceUrl": row.get("tbv_per_share_source_url"),
            "tbvPerShareNote": row.get("tbv_per_share_note"),
            "priceToTbv": row.get("price_to_tbv"),
            "provisionForCreditLosses": row.get("provision_for_credit_losses"),
            "netInterestIncome": row.get("net_interest_income"),
            "noninterestExpense": row.get("noninterest_expense"),
            "totalDeposits": row.get("total_deposits"),
            "netLoans": row.get("net_loans"),
            "tone": _trend_tone(row.get("eps_yoy_pct"), row.get("revenue_yoy_pct"), row.get("net_income_yoy_pct")),
            "notes": (row.get("quality_notes") or []) + (row.get("capital_allocation_notes") or []),
        })
    cards.sort(key=lambda row: (
        {"ok": 0, "info": 1, "warn": 2, "bad": 3}.get(row.get("tone"), 4),
        str(row.get("ticker") or ""),
    ))
    return {
        "generated_at": fund_raw.get("generated_at_utc") if isinstance(fund_raw, dict) else None,
        "source_posture": fund_raw.get("source_posture") if isinstance(fund_raw, dict) else "missing",
        "summary": fund_raw.get("summary") if isinstance(fund_raw, dict) else {},
        "quality_counts": quality_counts,
        "sec_reconciliation_counts": sec_counts,
        "ir_packet_summary": ir_summary or {},
        "ir_packet_generated_at": (ir_raw or {}).get("generated_at_utc") if isinstance(ir_raw, dict) else None,
        "authority": (fund_raw.get("authority") if isinstance(fund_raw, dict) else None) or {
            "review_packet_generation_allowed": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_action_allowed": False,
        },
        "rows": cards,
    }


def _band_label_from_values(band: dict[str, Any], fallback: str = "—") -> str:
    low = band.get("low")
    high = band.get("high")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return f"{fmt_num(low)}–{fmt_num(high)}"
    return str(band.get("label") or fallback)


def _stop_label_from_values(band: dict[str, Any], fallback: str = "—") -> str:
    stop = band.get("stop")
    if isinstance(stop, (int, float)):
        return fmt_num(stop)
    return str(band.get("stop_label") or fallback)


def _validate_payload_shape(
    today_action: dict[str, Any],
    deployment_records: list[dict[str, Any]],
    macro_regime: dict[str, Any],
    sectors_relative: list[dict[str, Any]],
    post_earnings: dict[str, Any],
    workflow_focus: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Catch breakage between the payload assembler and the view layer.

    Returns a list of validation warnings (same shape as build_validation).
    Treat shape drift as critical — it means the dashboard JS is reading
    fields that no longer exist, which produces silent blanks rather than errors.
    """
    issues: list[dict[str, Any]] = []

    def _add(code: str, severity: str, scope: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "scope": scope, "message": message})

    # today_action shape
    for key in REQUIRED_TODAY_ACTION_KEYS:
        if key not in today_action:
            _add(
                "today_action_missing_bucket", "critical", "shape",
                f"today_action missing required bucket '{key}' — the Overview action card will not render this section.",
            )
    for bucket_key in ("deployable", "promotionReview", "almost", "blocked"):
        for idx, card in enumerate(today_action.get(bucket_key) or []):
            for field in REQUIRED_ACTION_CARD_KEYS:
                if field not in card:
                    _add(
                        "today_action_card_missing_field", "critical", "shape",
                        f"today_action.{bucket_key}[{idx}] ({card.get('ticker','?')}) missing required field '{field}'.",
                    )
                    break

    # deployment_records shape
    if deployment_records:
        sample = deployment_records[0]
        for field in REQUIRED_DEPLOYMENT_RECORD_KEYS:
            if field not in sample:
                _add(
                    "deployment_record_missing_field", "critical", "shape",
                    f"deployment_records[0] ({sample.get('ticker','?')}) missing required field '{field}' — Deployment Board column will be blank.",
                )

    # macro_regime shape
    for key in REQUIRED_MACRO_REGIME_KEYS:
        if not macro_regime.get(key):
            _add(
                "macro_regime_missing_field", "warning", "shape",
                f"macro_regime.{key} is missing or empty — Macro tab regime banner will degrade.",
            )

    # sectors_relative
    if not sectors_relative:
        _add(
            "sectors_relative_empty", "warning", "shape",
            "sectors_relative is empty — Sector RS card will show no data. Check market-state.json sectors block.",
        )

    # post_earnings window contract — Phase 6 expects back_trading_days
    pe_window = (post_earnings or {}).get("window") or {}
    if "back_trading_days" not in pe_window:
        _add(
            "post_earnings_window_missing_field", "warning", "shape",
            "post_earnings.window.back_trading_days missing — re-run post_earnings_prep.py after picking up Phase 6 changes.",
        )

    # WF63/WF67 workflow-focus invariants — the Command Center must reflect
    # either readiness-only authority (WF63) or scoped WF67 paper-simulation
    # telemetry. Neither state may imply general/autonomous paper orders or live
    # trading/account authority.
    wf = workflow_focus or {}
    top = wf.get("top_workflow") or {}
    if not top:
        _add(
            "workflow_focus_missing_top", "critical", "wf63",
            "workflow_focus.top_workflow missing — Command Center cannot identify the top priority workflow.",
        )
    else:
        workflow_id = top.get("id")
        wf_scope = "wf67" if workflow_id == "WF67" else "wf63"
        if workflow_id not in {"WF63", "WF67"}:
            _add(
                "workflow_focus_wrong_top", "critical", "wf63",
                f"workflow_focus.top_workflow.id is {top.get('id')!r}; expected WF67 when scoped paper pilots are active, otherwise WF63 readiness.",
            )
        if top.get("paper_submit_allowed") is not False:
            _add(
                "paper_submit_not_general_blocked", "critical", wf_scope,
                "workflow_focus.top_workflow.paper_submit_allowed must be False for general/autonomous submits; only exact WF67 scoped artifacts may execute.",
            )
        if top.get("live_submit_allowed") is not False:
            _add(
                "live_submit_not_blocked", "critical", wf_scope,
                "workflow_focus.top_workflow.live_submit_allowed must be False; live order submission is not authorized.",
            )
        status_text = str(top.get("paper_trading_status") or "")
        if not status_text:
            _add(
                "paper_status_missing", "critical", wf_scope,
                "workflow_focus.top_workflow.paper_trading_status missing — readiness status must be visible.",
            )
        elif top.get("paper_submit_allowed") is False and top.get("live_submit_allowed") is False:
            normalized = status_text.lower()
            wf63_safe = "not ready" in normalized or "phase 1 read-only" in normalized
            wf67_safe = workflow_id == "WF67" and "scoped paper pilot" in normalized and "paper simulation only" in normalized
            if not wf63_safe and not wf67_safe:
                _add(
                    "paper_status_misleading", "critical", wf_scope,
                    f"paper_trading_status {status_text!r} does not state readiness-only or scoped-paper-simulation posture clearly.",
                )
        if not top.get("stop_lines"):
            _add(
                "workflow_stop_lines_missing", "critical", wf_scope,
                "workflow_focus.top_workflow.stop_lines must be present so the Command Center renders active workflow stop lines.",
            )
        else:
            stop_text = " ".join(str(line).lower() for line in top.get("stop_lines") or [])
            if workflow_id == "WF67":
                required_phrases = (
                    "paper simulation only",
                    "no live trade",
                    "no owner approval inferred",
                    "no close",
                    "paper results do not promote",
                )
            else:
                required_phrases = (
                    "no credentials in notes",
                    "no alpaca api",
                    "no paper",
                    "no brokerage",
                    "no money movement",
                    "no config",
                )
            for phrase in required_phrases:
                if phrase not in stop_text:
                    _add(
                        "workflow_stop_line_missing_phrase", "critical", wf_scope,
                        f"Active workflow stop lines must cover {phrase!r}.",
                    )
        if not top.get("next_approval_gate"):
            _add(
                "workflow_next_gate_missing", "critical", wf_scope,
                "workflow_focus.top_workflow.next_approval_gate must name the next required owner decision.",
            )
        if workflow_id == "WF67":
            authority = top.get("authority") or {}
            for field in ("live_trading_allowed", "live_endpoint_allowed", "money_movement_allowed", "account_settings_mutation_allowed", "owner_approval_inferred", "promotion_to_live_allowed"):
                if authority.get(field) is not False:
                    _add(
                        "wf67_authority_field_not_false", "critical", "wf67",
                        f"WF67 dashboard authority field {field!r} must be false.",
                    )
            if top.get("scoped_paper_pilot_active") is True and authority.get("paper_simulation_only") is not True:
                _add(
                    "wf67_paper_simulation_flag_missing", "critical", "wf67",
                    "WF67 scoped_paper_pilot_active requires authority.paper_simulation_only=true.",
                )

        # Scan rendered-language fields for phrases that would mislead the
        # reader into thinking paper trading is live or order submission is open.
        scan_targets: list[str] = []
        for key in ("paper_trading_status", "phase_label", "status_label", "next_approval_gate", "readiness_verdict"):
            value = top.get(key)
            if isinstance(value, str):
                scan_targets.append(value.lower())
        for line in top.get("stop_lines") or []:
            if isinstance(line, str):
                scan_targets.append(line.lower())
        scan_blob = " || ".join(scan_targets)
        for phrase in WF63_FORBIDDEN_LIVE_TRADING_PHRASES:
            if phrase in scan_blob:
                _add(
                    "wf63_misleading_active_language", "critical", "wf63",
                    f"Command Center WF63 text contains forbidden active-trading phrase {phrase!r}.",
                )

    monitors = wf.get("monitors") or []
    if not monitors:
        _add(
            "workflow_focus_monitors_missing", "warning", "wf63",
            "workflow_focus.monitors is empty — WF58/WF56/WF60/WF61 should be visible as monitors.",
        )
    else:
        ids = {m.get("id") for m in monitors if isinstance(m, dict)}
        for required in ("WF58", "WF56"):
            if required not in ids:
                _add(
                    "workflow_focus_monitor_missing", "warning", "wf63",
                    f"workflow_focus.monitors missing required monitor {required}.",
                )
        for monitor in monitors:
            if not isinstance(monitor, dict):
                continue
            if monitor.get("brokerage_authority") is True:
                _add(
                    "workflow_focus_monitor_brokerage_authority", "critical", "wf63",
                    f"workflow_focus monitor {monitor.get('id')} claims brokerage authority — WF56/WF58 are review-only.",
                )
            role_text = str(monitor.get("role") or "").lower()
            if monitor.get("id") in {"WF56", "WF58"} and role_text and "brokerage" not in role_text and "not brokerage" not in role_text:
                # Acceptable if it explicitly states it is review/proposal-only.
                if "review-only" not in role_text and "proposal" not in role_text and "recommend" not in role_text:
                    _add(
                        "workflow_focus_monitor_role_unclear", "warning", "wf63",
                        f"workflow_focus monitor {monitor.get('id')} role text should clarify it is review-only / not brokerage authority.",
                    )

    return issues


def _merge_shape_warnings(validation: dict[str, Any], shape_warnings: list[dict[str, Any]]) -> None:
    """Append shape warnings to the existing validation block and re-tally."""
    if not shape_warnings:
        return
    validation.setdefault("warnings", []).extend(shape_warnings)
    summary = validation.setdefault("summary", {"critical": 0, "warning": 0, "info": 0})
    for w in shape_warnings:
        sev = w["severity"]
        summary[sev] = summary.get(sev, 0) + 1
    if summary.get("critical"):
        validation["overall"] = "critical"
    elif summary.get("warning") and validation.get("overall") != "critical":
        validation["overall"] = "warning"


def _degrade_source_status(
    source_status: dict[str, dict[str, Any]],
    source_key: str,
    *,
    issue: str,
    tag: str,
    overall_status: str,
) -> str:
    info = source_status.get(source_key)
    if not info:
        return overall_status
    if issue not in info["issues"]:
        info["issues"].append(issue)
    if tag not in info["tags"]:
        info["tags"].append(tag)
    info["status"] = status_worse(info["status"], "partial")
    info["fresh"] = info["status"] in {"fresh", "usable_with_caution"}
    if info["critical"]:
        overall_status = status_worse(overall_status, info["status"])
    return overall_status


def _compute_band_status(
    close: float | None,
    band_low: float | None,
    band_high: float | None,
    in_band: bool | None,
    below_stop: bool | None,
) -> tuple[str, float | None]:
    if close is None:
        return "NO DATA", None
    if below_stop:
        return "BELOW STOP", None
    if in_band:
        return "IN BAND", None
    if band_low is None or band_high is None:
        return "NO BAND", None
    dist_pct = round((close - band_high) / band_high * 100, 2)
    if close < band_low:
        return "BELOW BAND", dist_pct
    if dist_pct <= NEAR_BAND_THRESHOLD_PCT:
        return "NEAR BAND", dist_pct
    return "ABOVE BAND", dist_pct


def _reference_band_authority_label(proposal: dict[str, Any] | None) -> str:
    if not proposal:
        return "missing reference proposal"
    if proposal.get("canonical_apply_eligible") is True:
        return "execution-band eligible only through the gated apply/owner-approved path"
    blockers: list[str] = []
    lane = proposal.get("coverage_lane")
    state = legacy_state(proposal, "workflow_state")
    policy = proposal.get("entry_policy")
    earnings = proposal.get("earnings_state")
    status = proposal.get("band_status")
    if lane != "execution":
        blockers.append("watch/reference lane")
    if policy != "band_defined":
        blockers.append(str(policy or "non-band-defined policy"))
    if state not in {"ALMOST", "PROMOTION REVIEW", "DEPLOYED"}:
        blockers.append(str(state or "non-decision state"))
    if earnings != "CLEAR":
        blockers.append(f"earnings {earnings or 'unknown'}")
    if status not in {"IN_BAND", "NEAR_BAND"}:
        blockers.append(str(status or "status unknown"))
    if not blockers:
        blockers.append("not execution-entitled")
    return "reference only / no execution entitlement — " + ", ".join(dict.fromkeys(blockers))


def _reference_band_from_proposal(proposal: dict[str, Any] | None) -> dict[str, Any] | None:
    if not proposal:
        return None
    required = ("suggested_band_low", "suggested_band_high", "suggested_stop")
    if any(proposal.get(field) is None for field in required):
        return None
    return {
        "low": proposal.get("suggested_band_low"),
        "high": proposal.get("suggested_band_high"),
        "stop": proposal.get("suggested_stop"),
        "label": f"{fmt_num(proposal.get('suggested_band_low'), prefix='$')}–{fmt_num(proposal.get('suggested_band_high'), prefix='$')}",
        "stopLabel": fmt_num(proposal.get("suggested_stop"), prefix="$"),
        "method": proposal.get("entry_band_method"),
        "status": proposal.get("band_status"),
        "dataDate": proposal.get("data_date"),
        "canonicalApplyEligible": proposal.get("canonical_apply_eligible") is True,
        "authorityLabel": _reference_band_authority_label(proposal),
        "authority": {
            "referenceOnly": proposal.get("canonical_apply_eligible") is not True,
            "executionBandMutationAllowed": False,
            "capitalActionAllowed": False,
            "ownerApprovalInferred": False,
            "tradeOrAccountAuthority": False,
            "sizingSleeveCashRiskRuleAuthority": False,
        },
    }


def update_history(payload: dict[str, Any]) -> list[dict[str, Any]]:
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []

    history.append({
        "generated_at_utc": payload.get("generated_at_utc") or payload.get("generated_at", ""),
        "schema_version": 2,
        "technical": [
            {
                "ticker": t["ticker"],
                "action_state": t.get("actionState"),
                "close": t["close"],
                "in_band": t.get("inBand"),
                "blocked": t.get("blocked"),
                "below_stop": t.get("belowStop"),
                "band_gap_dollar": t.get("bandGapDollar"),
                "earnings_date": t.get("earningsDate"),
            }
            for t in payload.get("technical", [])
        ],
    })

    if len(history) > 50:
        history = history[-50:]

    write_json(HISTORY_PATH, history)
    return history


def compute_delta(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    gen_at = current.get("generated_at", "")
    if previous is None:
        return {
            "generated_at": gen_at,
            "compared_to": None,
            "first_run": True,
            "changes": [],
            "summary": "First run, no prior snapshot to compare.",
        }

    changes: list[dict[str, Any]] = []
    cur_tech = {t["ticker"]: t for t in current.get("technical", [])}
    prev_tech = {t["ticker"]: t for t in previous.get("technical", [])}

    for ticker, ct in cur_tech.items():
        pt = prev_tech.get(ticker)
        if not pt:
            changes.append({"type": "new_ticker", "ticker": ticker})
            continue
        if ct.get("actionState") != pt.get("actionState"):
            changes.append({"type": "action_state_change", "ticker": ticker, "from": pt.get("actionState"), "to": ct.get("actionState")})
        if ct.get("belowStop") and not pt.get("belowStop"):
            changes.append({"type": "below_stop_entered", "ticker": ticker})
        elif not ct.get("belowStop") and pt.get("belowStop"):
            changes.append({"type": "below_stop_exited", "ticker": ticker})
        if ct.get("blocked") and not pt.get("blocked"):
            changes.append({"type": "new_blocker", "ticker": ticker})
        elif not ct.get("blocked") and pt.get("blocked"):
            changes.append({"type": "blocker_cleared", "ticker": ticker})

        cur_gap = ct.get("bandGapDollar")
        prev_gap = pt.get("bandGapDollar")
        if cur_gap is not None and prev_gap is not None:
            was_in = prev_gap <= 0
            now_in = cur_gap <= 0
            if now_in and not was_in:
                changes.append({"type": "entered_band", "ticker": ticker})
            elif was_in and not now_in:
                changes.append({"type": "exited_band", "ticker": ticker})

        if ct.get("earningsDate") != pt.get("earningsDate") and ct.get("earningsDate"):
            changes.append({"type": "earnings_date_change", "ticker": ticker, "from": pt.get("earningsDate"), "to": ct.get("earningsDate")})

    cur_sources = {f["label"]: f["status"] for f in current.get("trust", {}).get("sources", [])}
    prev_sources = {f["label"]: f["status"] for f in previous.get("trust", {}).get("sources", [])}
    for label, status in cur_sources.items():
        prior = prev_sources.get(label)
        if prior and prior != status:
            changes.append({"type": "source_status_change", "source": label, "from": prior, "to": status})

    if current.get("exec_freshness") != previous.get("exec_freshness"):
        changes.append({"type": "exec_freshness_change", "from": previous.get("exec_freshness"), "to": current.get("exec_freshness")})

    counts: dict[str, int] = {}
    for change in changes:
        counts[change["type"]] = counts.get(change["type"], 0) + 1
    parts = []
    summary_specs = [
        ("new_ticker", "new ticker(s) on the board"),
        ("action_state_change", "action state change(s)"),
        ("earnings_date_change", "earnings date shift(s)"),
        ("source_status_change", "source status change(s)"),
        ("exec_freshness_change", "exec-freshness change(s)"),
        ("new_blocker", "new blocker(s)"),
        ("blocker_cleared", "blocker(s) cleared"),
        ("below_stop_entered", "below-stop entry(ies)"),
        ("below_stop_exited", "below-stop exit(s)"),
        ("entered_band", "band entry(ies)"),
        ("exited_band", "band exit(s)"),
    ]
    enumerated_keys = {key for key, _ in summary_specs}
    for key, label in summary_specs:
        if counts.get(key):
            parts.append(f"{counts[key]} {label}")
    # Safety net: never claim "No material changes" while changes is non-empty.
    unenumerated = [c for c in changes if c["type"] not in enumerated_keys]
    if unenumerated:
        parts.append(f"{len(unenumerated)} other change(s)")
    if not changes:
        parts.append("No material changes")
    elif not parts:
        parts.append(f"{len(changes)} change(s) detected")

    return {
        "generated_at": gen_at,
        "compared_to": previous.get("generated_at"),
        "first_run": False,
        "changes": changes,
        "summary": "; ".join(parts),
    }


def _latest_window_artifact(prefix: str, window: str = "post-close") -> tuple[dict[str, Any], str | None]:
    """Load the current dashboard-window artifact without making it canonical."""
    preferred = TMP / f"{prefix}-{window}.json"
    if preferred.exists():
        return load_json(preferred) or {}, preferred.as_posix()
    matches = sorted(TMP.glob(f"{prefix}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return load_json(matches[0]) or {}, matches[0].as_posix()
    return {}, None


def _authority_boundary(*artifacts: dict[str, Any]) -> dict[str, Any]:
    return {
        "consumer_posture": "review_only",
        "owner_approval_required": True,
        "owner_approval_granted": False,
        "canonical_mutation_allowed": all(a.get("canonical_mutation_allowed") is True for a in artifacts) if artifacts else False,
        "portfolio_mutation_allowed": False,
        "deployment_state_mutation_allowed": all(a.get("deployment_state_mutation_allowed") is True for a in artifacts) if artifacts else False,
        "trade_execution_allowed": all(a.get("trade_execution_allowed") is True for a in artifacts) if artifacts else False,
        "language": "Review-only queue. Owner approval is required before any canonical note, portfolio, deployment-state, or trade action.",
    }


def _artifact_proves(path: Any) -> bool:
    if hasattr(path, "exists") and not path.exists():
        return False
    payload = load_json(path) or {}
    return bool(payload.get("generated_at_utc") or payload.get("generated_at") or payload.get("summary"))


def _rel_workspace_path(path: Any) -> str:
    if hasattr(path, "relative_to"):
        try:
            return str(path.relative_to(WORKSPACE)).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")
    return str(path).replace("\\", "/")


def _load_sql_handoff_source_metadata(paths: list[Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Load SQL cockpit provenance for dashboard handoff lanes without changing proof authority."""
    rel_paths = [_rel_workspace_path(path) for path in paths]
    health: dict[str, Any] = {
        "enabled": ARTIFACT_INDEX_DB.exists(),
        "status": "missing" if not ARTIFACT_INDEX_DB.exists() else "unknown",
        "operator_action_required": not ARTIFACT_INDEX_DB.exists(),
        "authority_boundary": SQL_AUTHORITY_BOUNDARY,
        "proof_authority": "provenance_and_health_only_not_handoff_proof",
    }
    if not ARTIFACT_INDEX_DB.exists() or not rel_paths:
        return {}, health
    try:
        report = validate_artifact_index(ARTIFACT_INDEX_DB)
        health.update({
            "status": report.get("status") or "unknown",
            "operator_action_required": report.get("status") != "ok",
            "checks": report.get("summary") or {},
            "safety_counts": report.get("safety_counts") or {},
        })
        placeholders = ",".join("?" for _ in rel_paths)
        records: dict[str, dict[str, Any]] = {}
        with connect_artifact_index(ARTIFACT_INDEX_DB) as conn:
            source_rows = conn.execute(
                f"""
                SELECT role, path, status, generated_at_utc, read_status, source_file, id
                FROM source_artifacts
                WHERE replace(path, '\\', '/') IN ({placeholders})
                ORDER BY COALESCE(generated_at_utc, '') DESC, id DESC
                """,
                tuple(rel_paths),
            ).fetchall()
            for row in source_rows:
                rel_path = str(row["path"] or "").replace("\\", "/")
                if rel_path in records:
                    continue
                records[rel_path] = {
                    "match": True,
                    "source_role": row["role"],
                    "path": rel_path,
                    "status": row["status"],
                    "generated_at_utc": row["generated_at_utc"],
                    "read_status": row["read_status"],
                    "indexed_from": row["source_file"],
                    "authority_boundary": SQL_AUTHORITY_BOUNDARY,
                }
            missing = [path for path in rel_paths if path not in records]
            if missing:
                run_placeholders = ",".join("?" for _ in missing)
                run_rows = conn.execute(
                    f"""
                    SELECT source_file, artifact_type, window, generated_at_utc, consumer_posture,
                           owner_review_required, canonical_mutation_allowed
                    FROM artifact_runs
                    WHERE replace(source_file, '\\', '/') IN ({run_placeholders})
                    ORDER BY COALESCE(generated_at_utc, '') DESC, id DESC
                    """,
                    tuple(missing),
                ).fetchall()
                for row in run_rows:
                    rel_path = str(row["source_file"] or "").replace("\\", "/")
                    if rel_path in records:
                        continue
                    records[rel_path] = {
                        "match": True,
                        "source_role": row["artifact_type"],
                        "path": rel_path,
                        "status": row["consumer_posture"] or "indexed",
                        "generated_at_utc": row["generated_at_utc"],
                        "read_status": "indexed_artifact_run",
                        "indexed_from": row["source_file"],
                        "owner_review_required": bool(row["owner_review_required"]),
                        "canonical_mutation_allowed": bool(row["canonical_mutation_allowed"]),
                        "authority_boundary": SQL_AUTHORITY_BOUNDARY,
                    }
        return records, health
    except Exception as exc:  # fail-soft; the dashboard keeps its file/artifact fallback.
        health.update({
            "status": "unavailable",
            "operator_action_required": True,
            "error": str(exc)[:180],
        })
        return {}, health


def _build_handoff_proof_state() -> list[dict[str, Any]]:
    """Expose which scheduled/research handoffs have first proof.

    Until a lane has a live proof artifact, it must render as pending rather
    than silently inheriting trust from the weekday research lane.
    """
    lanes = [
        ("weekday_research", "Weekday research", RESEARCH_FRESHNESS_OPPORTUNITY_PATH, True),
        ("morning", "Morning handoff", TMP / "run-summary-morning.json", False),
        ("post_close", "Post-close handoff", TMP / "run-summary-post-close.json", False),
        ("sunday_weekly", "Sunday weekly handoff", TMP / "weekly-intelligence-brief.json", False),
        ("sunday_research", "Sunday research handoff", TMP / "sunday-research-review.json", False),
    ]
    sql_records, sql_health = _load_sql_handoff_source_metadata([path for _, _, path, _ in lanes])
    out: list[dict[str, Any]] = []
    for key, label, path, standing_proved in lanes:
        # Worker artifacts are not handoff proof. A handoff is PROVED only when
        # the main-session systemEvent path itself has been proved/processed;
        # as of the current ledger, only weekday research has that proof.
        payload = (load_json(path) or {}) if standing_proved and path.exists() else {}
        proved = bool(standing_proved)
        rel_path = _rel_workspace_path(path)
        sql_source = sql_records.get(rel_path) or {
            "match": False,
            "path": rel_path,
            "authority_boundary": SQL_AUTHORITY_BOUNDARY,
        }
        out.append({
            "key": key,
            "label": label,
            "state": "PROVED" if proved else "PENDING_FIRST_PROOF",
            "tone": "ok" if proved else "warn",
            "source_path": rel_path,
            "generated_at_utc": payload.get("generated_at_utc") or payload.get("generated_at"),
            "sql_source": sql_source,
            "sql_artifact_index": {
                "enabled": sql_health.get("enabled"),
                "status": sql_health.get("status"),
                "operator_action_required": sql_health.get("operator_action_required"),
                "checks": sql_health.get("checks"),
                "safety_counts": sql_health.get("safety_counts"),
                "authority_boundary": SQL_AUTHORITY_BOUNDARY,
                "proof_authority": "provenance_and_health_only_not_handoff_proof",
            },
            "proof_authority_note": "SQL metadata is freshness/provenance support only; it does not set or upgrade this handoff proof state.",
        })
    return out


def _load_daily_intel_from_db(window: str) -> tuple[dict[str, Any], str | None, dict[str, Any], str | None] | None:
    """Query SQLite cockpit for daily review and market intelligence data.

    Routes reads through v_cockpit_action_queue / capital_recommendations /
    daily_review_objects / market_events instead of loading JSON files directly.
    Returns (daily, daily_path, intel, intel_path) with the same dict shape as
    _latest_window_artifact, or None when the DB is absent/empty so the caller
    can fall back to direct JSON load.

    Authority: derived_review_only_index_not_canon_not_apply — read-only index
    query, no source fetches, no canon/portfolio/trade mutations.
    """
    if not ARTIFACT_INDEX_DB.exists():
        return None
    try:
        import json as _json
        conn = connect_artifact_index(ARTIFACT_INDEX_DB)

        daily_run = conn.execute(
            "SELECT source_file, generated_at_utc, consumer_posture, summary_json "
            "FROM artifact_runs WHERE artifact_type='daily_review_objects' AND window=? "
            "ORDER BY generated_at_utc DESC LIMIT 1",
            (window,),
        ).fetchone()
        intel_run = conn.execute(
            "SELECT source_file, generated_at_utc, consumer_posture, summary_json "
            "FROM artifact_runs WHERE artifact_type='market_intelligence_events' AND window=? "
            "ORDER BY generated_at_utc DESC LIMIT 1",
            (window,),
        ).fetchone()

        if not daily_run and not intel_run:
            conn.close()
            return None

        daily: dict[str, Any] = {}
        daily_path: str | None = None
        if daily_run:
            sf = str(daily_run["source_file"])
            daily_path = (WORKSPACE / sf).as_posix()
            esc_rows = conn.execute(
                "SELECT raw_json FROM daily_review_objects WHERE source_file=? AND list_name='escalations' "
                "ORDER BY rank ASC, signal_score DESC",
                (sf,),
            ).fetchall()
            obj_rows = conn.execute(
                "SELECT raw_json FROM daily_review_objects WHERE source_file=? AND list_name='review_objects' "
                "ORDER BY rank ASC, signal_score DESC",
                (sf,),
            ).fetchall()
            cap_rows = conn.execute(
                "SELECT raw_json FROM capital_recommendations WHERE source_file=? ORDER BY rank ASC",
                (sf,),
            ).fetchall()
            daily = {
                "generated_at_utc": str(daily_run["generated_at_utc"] or ""),
                "consumer_posture": str(daily_run["consumer_posture"] or "review_only"),
                "summary": _json.loads(str(daily_run["summary_json"] or "{}")),
                "review_objects": [_json.loads(str(r["raw_json"])) for r in obj_rows],
                "escalations": [_json.loads(str(r["raw_json"])) for r in esc_rows],
                "capital_deployment_recommendations": [_json.loads(str(r["raw_json"])) for r in cap_rows],
            }

        intel: dict[str, Any] = {}
        intel_path: str | None = None
        if intel_run:
            sf = str(intel_run["source_file"])
            intel_path = (WORKSPACE / sf).as_posix()
            event_rows = conn.execute(
                "SELECT raw_json FROM market_events WHERE source_file=? AND list_name='events' "
                "ORDER BY rank ASC, materiality_score DESC",
                (sf,),
            ).fetchall()
            esc_rows = conn.execute(
                "SELECT raw_json FROM market_events WHERE source_file=? AND list_name='escalations' "
                "ORDER BY rank ASC, materiality_score DESC",
                (sf,),
            ).fetchall()
            intel = {
                "generated_at_utc": str(intel_run["generated_at_utc"] or ""),
                "consumer_posture": str(intel_run["consumer_posture"] or "review_only"),
                "summary": _json.loads(str(intel_run["summary_json"] or "{}")),
                "events": [_json.loads(str(r["raw_json"])) for r in event_rows],
                "escalations": [_json.loads(str(r["raw_json"])) for r in esc_rows],
            }

        conn.close()
        if not daily and not intel:
            return None
        return daily, daily_path, intel, intel_path
    except Exception:
        return None


def _build_decision_queue(window: str = "post-close") -> dict[str, Any]:
    db_result = _load_daily_intel_from_db(window)
    if db_result is not None:
        daily, daily_path, intel, intel_path = db_result
    else:
        daily, daily_path = _latest_window_artifact("daily-review-objects", window)
        intel, intel_path = _latest_window_artifact("market-intelligence-events", window)
    daily_summary = daily.get("summary") if isinstance(daily.get("summary"), dict) else {}
    intel_summary = intel.get("summary") if isinstance(intel.get("summary"), dict) else {}
    review_objects = daily.get("review_objects") if isinstance(daily.get("review_objects"), list) else []
    intel_events = intel.get("events") if isinstance(intel.get("events"), list) else []
    explicit_daily_escalations = daily.get("escalations") if isinstance(daily.get("escalations"), list) else []
    daily_escalations = explicit_daily_escalations or [obj for obj in review_objects if str(legacy_state(obj, "surface_state") or "").upper() == "REVIEW REQUIRED"]
    capital_recommendations = daily.get("capital_deployment_recommendations") if isinstance(daily.get("capital_deployment_recommendations"), list) else []
    if not capital_recommendations:
        capital_recommendations = [obj for obj in review_objects if obj.get("object_type") == "capital_recommendation"]
    if not capital_recommendations:
        capital_recommendations = [obj for obj in review_objects if obj.get("recommended_action") and obj.get("owner_approval_required") is True]
    market_escalations = [event for event in intel_events if event.get("owner_review_required") or (event.get("rank") or 99) <= 5]

    def _review_item(obj: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": obj.get("id") or obj.get("event_id") or (f"capital:{obj.get('ticker')}" if obj.get("recommended_action") and obj.get("ticker") else None),
            "ticker": obj.get("ticker") or obj.get("ticker_or_macro_sleeve") or "SYSTEM",
            "type": obj.get("object_type") or obj.get("event_type") or ("capital_recommendation" if obj.get("recommended_action") else "review_object"),
            "title": obj.get("why_now") or obj.get("event_title") or obj.get("recommended_action") or obj.get("category") or "Review object",
            "route": obj.get("recommended_route") or obj.get("route") or "owner_review",
            "urgency": obj.get("urgency") or "review",
            "score": obj.get("signal_score") or obj.get("materiality_score"),
            "owner_question": obj.get("owner_question") or "Owner approval required before action.",
            "next_step": obj.get("recommended_next_step") or obj.get("guidance") or obj.get("blocked_reason") or obj.get("reason") or "Review before changing canonical state or capital posture.",
            "evidence": (obj.get("evidence") or obj.get("risk_invalidation") or [])[:2] if isinstance(obj.get("evidence") or obj.get("risk_invalidation"), list) else [],
            "owner_review_required": obj.get("owner_review_required", True),
            "rank": obj.get("rank"),
        }

    daily_counts = {
        "review_object_count": daily_summary.get("review_object_count", len(review_objects)),
        "escalated_count": daily_summary.get("escalated_count", len(daily_escalations)),
        "capital_recommendation_count": daily_summary.get("capital_recommendation_count", len(capital_recommendations)),
    }
    intel_counts = {
        "event_count": intel_summary.get("event_count", len(intel_events)),
        "escalated_count": intel_summary.get("escalated_count", len(market_escalations)),
        "top_routes": intel_summary.get("top_routes") or [],
        "top_tickers_or_sleeves": intel_summary.get("top_tickers_or_sleeves") or [],
    }

    return {
        "window": window,
        "status": "ok" if daily_path or intel_path else "missing",
        "daily_review": {
            "source_path": daily_path,
            "generated_at_utc": daily.get("generated_at_utc"),
            "consumer_posture": daily.get("consumer_posture") or "review_only",
            "counts": daily_counts,
            "escalations": [_review_item(obj) for obj in daily_escalations[:6]],
            "capital_recommendations": [_review_item(obj) for obj in capital_recommendations],
            "portfolio_call": daily_summary.get("portfolio_call") or {},
        },
        "market_intelligence": {
            "source_path": intel_path,
            "generated_at_utc": intel.get("generated_at_utc"),
            "consumer_posture": intel.get("consumer_posture") or "review_only",
            "counts": intel_counts,
            "escalations": [_review_item(obj) for obj in market_escalations[:8]],
        },
        "authority": _authority_boundary(daily, intel),
    }


def _build_workflow_focus() -> dict[str, Any]:
    """Surface the active top-priority workflow and monitor lanes.

    Prefer WF67 paper-simulation telemetry when scoped pilots are active;
    otherwise fall back to WF63 readiness. The payload it emits is the contract
    the renderer and validators key off — keep the field names and shape stable.
    """
    report = load_json(WF63_READINESS_REPORT_PATH) or {}
    policy = load_json(WF63_PHASE_0_POLICY_PATH) or {}
    paper_surface = load_json(PAPER_PILOT_STATUS_SURFACE_PATH) or {}

    authority = report.get("authority") or policy.get("current_authority") or {}
    paper_submit_allowed = authority.get("openclaw_paper_submit_allowed") is True
    live_submit_allowed = authority.get("live_submit_allowed") is True
    read_only_connection_allowed = authority.get("read_only_connection_allowed") is True

    if paper_submit_allowed or live_submit_allowed:
        paper_status = "WARNING: paper-submit authority asserted by readiness artifact — investigate"
    elif read_only_connection_allowed:
        paper_status = "Phase 1 read-only paper connection authorized — still NO ORDER SUBMIT"
    else:
        paper_status = "NOT READY FOR PAPER ORDERS"

    next_gate = (
        policy.get("next_required_owner_decision")
        or "Phase 1 read-only Alpaca paper connection planning (no order submit, no live endpoint)"
    )

    wf63_stop_lines = [
        "No credentials in notes or chat",
        "No Alpaca API calls yet",
        "No paper or live order submit",
        "No brokerage or account mutation",
        "No money movement",
        "No POST, PATCH, PUT, or DELETE to Alpaca",
        "No cancel or replace orders",
        "No config or auth mutation without approval",
        "No inferred owner approval from validators",
        "No secrets in notes, memory, logs, or generated artifacts",
    ]

    proof_artifacts = [
        "tmp/alpaca-paper-readiness/phase-0-policy.json",
        "tmp/alpaca-paper-readiness/wf63-readiness-report.json",
        "06. Playbooks/Operating Procedures/Alpaca Paper Credential Handling Procedure.md",
        "tmp/alpaca-paper-readiness/read-only-connection-proof.schema.json",
        "tmp/alpaca-paper-readiness/phase-1-2-readiness-spec.json",
        "06. Playbooks/Project Continuity/Workflow 63 - Alpaca Paper Trading Readiness.md",
        "07. Risk/Alpaca Paper Trading Guardrails.md",
    ]

    pilots = paper_surface.get("pilots") if isinstance(paper_surface.get("pilots"), list) else []
    paper_authority = paper_surface.get("authority") if isinstance(paper_surface.get("authority"), dict) else {}
    if paper_surface.get("status") == "ok" and pilots:
        top_workflow = {
            "id": "WF67",
            "title": "Alpaca Paper Execution Guardrail",
            "phase_key": "phase_6_scoped_paper_pilot",
            "phase_label": "Phase 6 - scoped paper-only pilot telemetry",
            "status_label": "Scoped paper pilot active - paper simulation only; live trading blocked",
            "paper_trading_status": "Scoped paper pilot active — paper simulation only; live trading, money movement, account mutation, and promotion-to-live blocked",
            # This field intentionally remains false: it means general or
            # autonomous paper submit authority, not exact WF67 scoped artifacts.
            "paper_submit_allowed": False,
            "general_autonomous_paper_submit_allowed": False,
            "scoped_paper_pilot_active": True,
            "scoped_paper_submit_cancel_guard_ready": paper_authority.get("scoped_paper_submit_cancel_allowed") is True,
            "live_submit_allowed": False,
            "read_only_connection_allowed": read_only_connection_allowed,
            "next_approval_gate": "Read-only post-open reconciliation; no close/cancel/sell/replacement without explicit owner instruction.",
            "readiness_report_status": report.get("status"),
            "readiness_verdict": "WF67 scoped paper pilots are visible for monitoring only; no live authority or inferred approval.",
            "required_endpoint": "https://paper-api.alpaca.markets",
            "forbidden_endpoint": "https://" + "api.alpaca.markets",
            "stop_lines": paper_surface.get("stop_lines") or [
                "Paper simulation only; no live trade/account/money movement authority.",
                "No owner approval inferred from recommendation packets, validation, or paper fills.",
                "No close/cancel/sell unless Randall explicitly instructs inside WF67 guardrails.",
                "Paper results do not promote a ticker to live deployment or portfolio mutation authority.",
            ],
            "authority": paper_authority,
            "paper_pilot_status": {
                "generated_at_utc": paper_surface.get("generated_at_utc"),
                "status": paper_surface.get("status"),
                "summary": paper_surface.get("summary") or {},
                "pilots": pilots[:6],
            },
            "proof_artifacts": [
                "tmp/alpaca-paper-readiness/paper-pilot-status-surface.json",
                "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
                "tmp/alpaca-paper-readiness/wf63-readiness-report.json",
                "06. Playbooks/Project Continuity/Workflow 67 - Alpaca Paper Execution Guardrail.md",
                "07. Risk/Alpaca Paper Trading Guardrails.md",
            ],
        }
    else:
        top_workflow = {
            "id": "WF63",
            "title": "Alpaca Paper Trading Readiness",
            "phase_key": report.get("phase") or policy.get("phase"),
            "phase_label": "Phase 0 - policy and architecture lock (readiness scaffold)",
            "status_label": "Opened / readiness only - order placement blocked",
            "paper_trading_status": paper_status,
            "paper_submit_allowed": paper_submit_allowed,
            "live_submit_allowed": live_submit_allowed,
            "read_only_connection_allowed": read_only_connection_allowed,
            "next_approval_gate": next_gate,
            "readiness_report_status": report.get("status"),
            "readiness_verdict": report.get("verdict"),
            "required_endpoint": policy.get("required_endpoint"),
            "forbidden_endpoint": policy.get("forbidden_endpoint"),
            "stop_lines": wf63_stop_lines,
            "authority": authority,
            "proof_artifacts": proof_artifacts,
        }

    monitors = [
        {
            "id": "WF63",
            "title": "Alpaca Paper Trading Readiness",
            "status": "Guardrail foundation / read-only proof clean" if report.get("status") == "ok" else "Guardrail foundation / review required",
            "role": "Paper endpoint isolation and no-submit guard foundation under WF67",
            "brokerage_authority": False,
        },
        {
            "id": "WF58",
            "title": "Dashboard freshness, entry-band automation, capital recommendations, discrepancy resolver",
            "status": "Implemented / cron-owned monitor",
            "role": "Generates review-only capital recommendations and proposals; not brokerage authority",
            "brokerage_authority": False,
        },
        {
            "id": "WF56",
            "title": "Portfolio Mutation Proposal Object and Gated Apply Helper",
            "status": "Owner-gated wait / no approved apply artifact active",
            "role": "Proposes scoped canonical note edits; not brokerage authority",
            "brokerage_authority": False,
        },
        {
            "id": "WF60",
            "title": "Research Freshness and Opportunity Cron Automation",
            "status": "Implemented / cron-owned monitor",
            "role": "Generates review-only research and opportunity feeds; not brokerage authority",
            "brokerage_authority": False,
        },
        {
            "id": "WF61",
            "title": "Small Mid Cap Regime Feed and Candidate Sleeve",
            "status": "Implemented / WF60-owned downstream monitor",
            "role": "Regime signal feed; no portfolio addition or brokerage authority",
            "brokerage_authority": False,
        },
    ]

    artifacts_present = WF63_READINESS_REPORT_PATH.exists() and WF63_PHASE_0_POLICY_PATH.exists()
    return {
        "generated_at_utc": report.get("generated_at_utc") or policy.get("generated_at_utc"),
        "artifacts_present": artifacts_present,
        "top_workflow": top_workflow,
        "monitors": monitors,
    }


def build_payload(sources: dict[str, dict | None]) -> dict[str, Any]:
    print("generate_dashboard.py v5, assembling payload …")
    trigger_sheet_raw = load_json(TMP / "trigger-sheet.json") or {}
    post_earnings_raw = load_json(TMP / "post-earnings-prep.json") or {}
    band_proposals_raw = load_json(TMP / "band-proposals.json") or {}
    research_review_raw = load_json(RESEARCH_FRESHNESS_OPPORTUNITY_PATH) or {}
    research_review_by_ticker = _research_reviews_by_ticker(research_review_raw)
    weekly_positioning_text = _safe_read_text(WEEKLY_POSITIONING_REVIEW_PATH)

    market_raw = sources["market"] or {}
    policy_raw = sources["policy"] or {}
    credit_raw = sources.get("credit") or {}
    breadth_raw = sources.get("breadth") or {}
    tech_raw = sources["technical"] or {}
    deploy_raw = sources["deployment"] or {}
    earn_raw = sources["earnings"] or {}
    pf_raw = sources["portfolio"] or {}
    fund_raw = sources.get("fundamentals") or {}
    fundamental_ir_raw = sources.get("fundamental_ir") or {}

    now = datetime.now(timezone.utc)
    market_session = get_market_session(now)
    source_status = {name: assess_source(name, src) for name, src in sources.items()}
    vault_freshness = get_vault_freshness()
    shape_warnings: list[dict[str, Any]] = []

    overall_status = "fresh"
    for name, info in source_status.items():
        if info["critical"]:
            overall_status = status_worse(overall_status, info["status"])

    last_trade = tech_raw.get("last_trading_day") or market_raw.get("last_trading_day") or now.strftime("%Y-%m-%d")
    last_trade_dt = parse_date(last_trade) or now

    ms_data = market_raw.get("data", {})
    policy_data = policy_raw.get("data", {}) if isinstance(policy_raw.get("data"), dict) else {}
    credit_data = credit_raw.get("data", {}) if isinstance(credit_raw.get("data"), dict) else {}
    breadth_data = breadth_raw.get("data", {}) if isinstance(breadth_raw.get("data"), dict) else {}
    sector_shape_messages: list[str] = []
    sectors_raw, _ = guard_dict_or_empty(get_path(market_raw, "data.sectors"), sector_shape_messages, "market-state.data.sectors")

    market = {
        "generated_at": market_raw.get("generated_at_utc"),
        "fed": {
            "target_low": get_path(ms_data, "fed.target_low"),
            "target_high": get_path(ms_data, "fed.target_high"),
            "cut_prob": get_path(ms_data, "fed.cut_probability_next_meeting"),
            "manual_update_required": get_path(ms_data, "fed.manual_update_required"),
        },
        "treasuries": {
            "y2": get_path(ms_data, "treasuries.2y"),
            "y10": get_path(ms_data, "treasuries.10y"),
            "m3": get_path(ms_data, "treasuries.3m_tbill"),
            "curve_2s10s": get_path(ms_data, "treasuries.curve_2s10s_bps"),
            "curve_3m10y": get_path(ms_data, "treasuries.curve_3m10y_bps"),
        },
        "vix": get_path(ms_data, "volatility.vix"),
        "spx": get_path(ms_data, "equities.spx"),
        "dxy": get_path(ms_data, "fx.dxy"),
        "brent": get_path(ms_data, "energy.brent"),
        "wti": get_path(ms_data, "energy.wti"),
        "warnings": list(dict.fromkeys(market_raw.get("warnings", []))),
        "macro_freshness": market_raw.get("macro_freshness") or {},
    }
    policy_expectations = {
        "generated_at": policy_raw.get("generated_at_utc"),
        "status": policy_raw.get("status"),
        "policy_status": policy_raw.get("policy_status"),
        "freshness_status": policy_raw.get("freshness_status"),
        "freshness_contract": policy_raw.get("freshness_contract") or {},
        "remediation": policy_raw.get("remediation") or {},
        "safety": policy_raw.get("safety") or {},
        "source_label": get_path(policy_data, "source_label"),
        "source_mode": get_path(policy_data, "source_mode"),
        "implied_rate_source_mode": get_path(policy_data, "implied_rate_source_mode"),
        "warnings": list(dict.fromkeys(policy_raw.get("warnings", []))),
        "freshness_notes": list(dict.fromkeys(policy_raw.get("freshness_notes", []))),
        "current_target_range": get_path(policy_data, "current_target_range") or {},
        "next_fomc": get_path(policy_data, "next_fomc") or {},
        "next_two_meetings": get_path(policy_data, "next_two_meetings") or [],
        "manual_dependencies": get_path(policy_data, "manual_dependencies") or [],
    }
    credit_spreads = {
        "generated_at": credit_raw.get("generated_at_utc"),
        "status": credit_raw.get("status"),
        "source_label": get_path(credit_data, "source_label"),
        "source_mode": get_path(credit_data, "source_mode"),
        "warnings": list(dict.fromkeys(credit_raw.get("warnings", []))),
        "investment_grade_oas": get_path(credit_data, "investment_grade_oas") or {},
        "high_yield_oas": get_path(credit_data, "high_yield_oas") or {},
        "hy_minus_ig_spread": get_path(credit_data, "hy_minus_ig_spread"),
        "direction": get_path(credit_data, "direction") or {},
        "stress_regime": get_path(credit_data, "stress_regime"),
    }
    market_breadth = {
        "generated_at": breadth_raw.get("generated_at_utc"),
        "status": breadth_raw.get("status"),
        "source_mode": get_path(breadth_data, "source_mode"),
        "warnings": list(dict.fromkeys(breadth_raw.get("warnings", []))),
        "equal_weight_vs_cap_weight": get_path(breadth_data, "equal_weight_vs_cap_weight") or {},
        "sector_participation": get_path(breadth_data, "sector_participation") or {},
        "major_index_breadth": get_path(breadth_data, "major_index_breadth") or {},
        "tier2_metrics": get_path(breadth_data, "tier2_metrics") or {},
    }

    macro_regime_raw = load_json(TMP / "macro-regime.json") or {}
    macro_regime = {
        "generated_at": macro_regime_raw.get("generated_at_utc"),
        "status": macro_regime_raw.get("status"),
        "freshness_contract": macro_regime_raw.get("freshness_contract") or {},
        "regime_label": get_path(macro_regime_raw, "regime.label"),
        "regime_key": get_path(macro_regime_raw, "regime.key"),
        "policy_pillar": get_path(macro_regime_raw, "pillars.policy") or {},
        "credit_pillar": get_path(macro_regime_raw, "pillars.credit") or {},
        "breadth_pillar": get_path(macro_regime_raw, "pillars.breadth") or {},
    }

    sectors_relative: list[dict[str, Any]] = []
    for key, info in sectors_raw.items():
        sector_info, bad = guard_dict_or_empty(info, sector_shape_messages, f"market-state.data.sectors.{key}")
        if bad:
            continue
        sectors_relative.append({
            "ticker": sector_info.get("ticker") or key.upper(),
            "label": sector_info.get("label") or key.upper(),
            "change_pct": sector_info.get("change_pct"),
            "relative_vs_spx_pct": sector_info.get("relative_vs_spx_pct"),
            "relative_label": sector_info.get("relative_label"),
            "last_price": sector_info.get("last_price"),
        })
    sectors_relative.sort(key=lambda s: s.get("relative_vs_spx_pct") if s.get("relative_vs_spx_pct") is not None else -999, reverse=True)

    for message in sector_shape_messages:
        shape_warnings.append({
            "code": "market_sectors_invalid_shape",
            "severity": "warning",
            "scope": "shape",
            "message": message,
        })
        overall_status = _degrade_source_status(
            source_status,
            "market",
            issue=message,
            tag="shape_invalid",
            overall_status=overall_status,
        )

    exec_freshness = overall_status
    provenance = build_provenance(source_status)
    source_freshness = summarize_source_freshness([info["source_state"] for info in source_status.values()])

    entry_bands = pf_raw.get("entry_bands", {}) if isinstance(pf_raw.get("entry_bands"), dict) else {}
    posture_labels = pf_raw.get("posture_labels", {}) if isinstance(pf_raw.get("posture_labels"), dict) else {}
    tracked_universe = pf_raw.get("tracked_universe", {}) if isinstance(pf_raw.get("tracked_universe"), dict) else {}
    fundamental_trends = _build_fundamental_trends(fund_raw, tracked_universe, fundamental_ir_raw)
    reference_band_by_ticker = {
        p.get("ticker"): _reference_band_from_proposal(p)
        for p in normalize_records(band_proposals_raw.get("proposals"))
        if p.get("ticker")
    }
    band_stale_tickers = set((band_proposals_raw.get("summary") or {}).get("blocking_review_tickers") or [])
    deploy_by_ticker = {r.get("ticker"): r for r in normalize_records(deploy_raw.get("records"))}
    earnings_records = normalize_records(earn_raw.get("records"))
    earnings_by_ticker = {r.get("ticker"): r for r in earnings_records if r.get("ticker")}
    nvda_meta = tracked_universe.get("NVDA", {}) if isinstance(tracked_universe.get("NVDA"), dict) else {}
    nvda_earnings_rec = earnings_by_ticker.get("NVDA") or {}
    sql_fallback_values = {
        "NVDA:post_earnings_review_confirmed": nvda_meta.get("post_earnings_review_confirmed"),
        "NVDA:earnings_lifecycle_status": get_path(nvda_earnings_rec, "lifecycle.status") or get_path(nvda_earnings_rec, "lifecycle.hold.status") or get_path(nvda_earnings_rec, "lifecycle.evidence.status"),
        "NVDA:last_earnings_date": nvda_meta.get("last_earnings_date"),
        "NVDA:post_earnings_review_date": nvda_meta.get("post_earnings_review_date"),
        "deployment:source_freshness_classification": get_path(source_status, "deployment.source_state.classification"),
        "earnings:source_freshness_classification": get_path(source_status, "earnings.source_state.classification"),
        "breadth:source_freshness_classification": get_path(source_status, "breadth.source_state.classification"),
        "credit:source_freshness_classification": get_path(source_status, "credit.source_state.classification"),
        "fundamental_ir:source_freshness_classification": get_path(source_status, "fundamental_ir.source_state.classification"),
        "fundamentals:source_freshness_classification": get_path(source_status, "fundamentals.source_state.classification"),
        "market:source_freshness_classification": get_path(source_status, "market.source_state.classification"),
        "policy:source_freshness_classification": get_path(source_status, "policy.source_state.classification"),
        "technical:source_freshness_classification": get_path(source_status, "technical.source_state.classification"),
        "portfolio:source_freshness_classification": get_path(source_status, "portfolio.source_state.classification"),
        "portfolio:source_freshness_state": get_path(source_status, "portfolio.source_state"),
    }
    sql_fallback_values.update(_entry_stop_reference_fallback_values())
    sql_canon = _load_phase4a_sql_canon_metadata(sql_fallback_values)

    def _coverage_lane_label(lane: str | None) -> str:
        lane_key = (lane or "").lower()
        return {
            "execution": "Exec",
            "watch": "Watch",
            "macro": "Macro",
            "speculative": "Spec",
        }.get(lane_key, "—")

    technical: list[dict[str, Any]] = []
    for record in normalize_records(tech_raw.get("records")):
        ticker = record.get("ticker")
        band = entry_bands.get(ticker, {})
        reference_band = reference_band_by_ticker.get(ticker)
        meta = tracked_universe.get(ticker, {}) if isinstance(tracked_universe.get(ticker), dict) else {}
        research_review = research_review_by_ticker.get(str(ticker or "").upper()) or {}
        band_low, band_high, stop_val = band.get("low"), band.get("high"), band.get("stop")
        close = record.get("close")

        band_gap_dollar = None
        band_gap_pct = None
        if close is not None and band_low is not None and band_high is not None and close != 0:
            if close > band_high:
                band_gap_dollar = round(close - band_high, 2)
            elif close < band_low:
                band_gap_dollar = round(close - band_low, 2)
            else:
                band_gap_dollar = 0.0
            band_gap_pct = round((band_gap_dollar / close) * 100, 2)

        stop_dist_pct = None
        if close is not None and stop_val is not None and close > 0:
            stop_dist_pct = round(((close - stop_val) / close) * 100, 2)

        earnings_rec = earnings_by_ticker.get(ticker) or {}
        earnings_date = earnings_rec.get("next_earnings_date")
        earnings_dt = parse_date(earnings_date)
        days_to_earnings = (earnings_dt.date() - last_trade_dt.date()).days if earnings_dt else None
        sql_canon_proof = _sql_canon_proof_for_ticker(str(ticker or ""), sql_canon, {
            "post_earnings_review_confirmed": meta.get("post_earnings_review_confirmed"),
            "earnings_lifecycle_status": get_path(earnings_rec, "lifecycle.status") or get_path(earnings_rec, "lifecycle.hold.status") or get_path(earnings_rec, "lifecycle.evidence.status"),
            "last_earnings_date": meta.get("last_earnings_date"),
            "post_earnings_review_date": meta.get("post_earnings_review_date"),
        })

        deploy = deploy_by_ticker.get(ticker)
        action_state = legacy_state(deploy, "action_state") if deploy else "UNKNOWN"
        action_reason = deploy.get("reason") if deploy else "No deployment record found"
        priority = deploy.get("priority") if deploy else 99
        conflict = _authority_conflict_meta(ticker, research_review, weekly_positioning_text, action_state)
        if conflict:
            action_state = "AUTHORITY CONFLICT"
            action_reason = conflict["reason"]

        almost_meta = _almost_substate(ticker, action_state)

        earnings_blocked = deploy.get("earnings_blocked", False) if deploy else False

        trigger_ready = bool(
            exec_freshness in {"fresh", "usable_with_caution"}
            and band_gap_dollar is not None
            and band_gap_dollar <= 0
            and not earnings_blocked
            and not record.get("below_stop")
            and action_state in {"DEPLOYABLE", "ALMOST", "DEPLOYABLE NOW", "PROMOTION REVIEW", "ALMOST DEPLOYABLE"}
        )

        band_status, band_dist_pct = _compute_band_status(
            close, band_low, band_high,
            record.get("in_entry_band"), record.get("below_stop"),
        )
        workflow_state = str(legacy_state(meta, "workflow_state") or legacy_state((deploy or {}), "workflow_state") or "").upper()
        override_rule = (deploy or {}).get("override_rule")
        override_reason = (deploy or {}).get("override_reason")
        repair_override = bool(
            workflow_state == "REPAIR"
            or override_rule
            or str(action_state or "").upper() in {"DO NOT TOUCH", "BENCH"}
        )
        repair_override_label = None
        if repair_override:
            repair_override_label = "REPAIR OVERRIDE / band position irrelevant"
        report_file = ENTRY_BAND_REPORTS_DIR / f"{ticker}_entry_band.html"
        entry_band_report_path = (
            f"entry-band-reports/{ticker}_entry_band.html"
            if report_file.exists() else None
        )

        technical.append({
            "ticker": ticker,
            "close": close,
            "ma20": record.get("ma20"),
            "ma50": record.get("ma50"),
            "ma200": record.get("ma200"),
            "posture": posture_labels.get(record.get("ma_posture"), record.get("ma_posture")),
            "raw_ma_posture": record.get("ma_posture"),
            "above20": record.get("above_ma20"),
            "above50": record.get("above_ma50"),
            "above200": record.get("above_ma200"),
            "inBand": record.get("in_entry_band"),
            "belowStop": record.get("below_stop"),
            "blocked": earnings_blocked,
            "entry": _band_label_from_values(band, "TBD"),
            "executionBand": {
                "low": band_low,
                "high": band_high,
                "stop": stop_val,
                "label": _band_label_from_values(band, "TBD"),
                "stopLabel": _stop_label_from_values(band, "TBD"),
                "lastSet": band.get("band_last_set"),
            },
            "referenceBand": reference_band,
            "stop": _stop_label_from_values(band, "TBD"),
            "actionState": action_state,
            "actionReason": action_reason,
            **(conflict or {}),
            **(almost_meta or {}),
            "priority": priority,
            "bandGapDollar": band_gap_dollar,
            "bandGapPct": band_gap_pct,
            "stopDistPct": stop_dist_pct,
            "daysToEarnings": days_to_earnings,
            "earningsDate": earnings_date,
            "earningsDateConfirmed": not _earnings_unconfirmed(earnings_rec.get("primary_confirmed")),
            "earningsDateSourceClass": earnings_rec.get("date_source_class"),
            "earningsPrimaryConfirmed": earnings_rec.get("primary_confirmed"),
            "earningsLifecycle": earnings_rec.get("lifecycle") or {},
            "lastEarningsDate": meta.get("last_earnings_date"),
            "postEarningsReviewDate": meta.get("post_earnings_review_date"),
            "postEarningsReviewConfirmed": meta.get("post_earnings_review_confirmed"),
            "sqlCanonProofMetadata": sql_canon_proof,
            "triggerToday": trigger_ready,
            "bandStatus": band_status,
            "bandDistPct": band_dist_pct,
            "repairOverride": repair_override,
            "repairOverrideLabel": repair_override_label,
            "bandVisualSuppressed": repair_override,
            "overrideRule": override_rule,
            "overrideReason": override_reason,
            "sourceArtifactPath": "tmp/technical-refresh.json + tmp/deployment-check.json",
            "sourceGeneratedAtUtc": tech_raw.get("generated_at_utc") or deploy_raw.get("generated_at_utc"),
            "researchArtifactPath": "tmp/research-freshness-opportunity-review.json",
            "researchGeneratedAtUtc": research_review_raw.get("generated_at_utc"),
            "bandStale": ticker in band_stale_tickers,
            "coverageLane": meta.get("coverage_lane"),
            "coverageLaneLabel": _coverage_lane_label(meta.get("coverage_lane")),
            "entryBandReportPath": entry_band_report_path,
        })

    pf = pf_raw.get("portfolio", {}) if isinstance(pf_raw.get("portfolio"), dict) else {}
    sector_map = pf_raw.get("sector_map", {}) if isinstance(pf_raw.get("sector_map"), dict) else {}
    all_positions = pf.get("core", []) + pf.get("tactical", []) + pf.get("speculative", [])
    sector_weights: dict[str, float] = {}
    for sector, tickers in sector_map.items():
        weight = round(sum((p.get("weight") or 0) for p in all_positions if p.get("ticker") in tickers), 2)
        if weight > 0:
            sector_weights[sector] = weight

    validation = build_validation(sources, source_status, technical, sector_weights, last_trade_dt)

    manual_dependencies: list[dict[str, Any]] = []
    fed = get_path(market_raw, "data.fed") or {}
    # Friendlier human labels and tone hints for the rendered Trust panel.
    dep_status_meta = {
        "manual":                {"label": "Manual",          "tone": "warn"},
        "unconfirmed":           {"label": "Unconfirmed",     "tone": "bad"},
        "unconfirmed_change":    {"label": "Date changed",    "tone": "bad"},
        "unconfirmed_addition":  {"label": "New on calendar", "tone": "warn"},
    }

    def _add_dep(label: str, scope: str, status: str, detail: str) -> None:
        meta = dep_status_meta.get(status, {"label": status, "tone": "bad"})
        manual_dependencies.append({
            "label": label,
            "scope": scope,
            "status": status,
            "statusLabel": meta["label"],
            "tone": meta["tone"],
            "detail": detail,
        })

    if policy_raw:
        for dep in policy_expectations["manual_dependencies"]:
            if isinstance(dep, dict):
                _add_dep(
                    dep.get("label") or dep.get("field") or "Policy dependency",
                    "Macro",
                    "manual",
                    dep.get("detail") or "Manual policy-layer maintenance remains in place.",
                )
        if policy_expectations.get("implied_rate_source_mode") == "fallback_proxy":
            _add_dep(
                "Policy expectations source path",
                "Macro",
                "unconfirmed",
                "Policy expectations are currently using the generic ZQ=F front-contract proxy because the contract-specific ZQ quote was unavailable.",
            )
    else:
        if fed.get("manual_update_required"):
            _add_dep(
                "Fed target range",
                "Macro",
                "manual",
                "Update the hardcoded Fed target range in scripts/policy_expectations_refresh.py after each FOMC decision.",
            )
        if fed.get("cut_probability_next_meeting") is None:
            _add_dep(
                "FedWatch cut probability",
                "Macro",
                "unconfirmed",
                "Keep this null until a stable CME FedWatch source is wired or manually verified in the note layer.",
            )
    for alert in earn_raw.get("watchlist_alerts", []):
        # Both DATE CHANGED and NEW alerts represent script/vault drift that the
        # operator needs to acknowledge. Distinct status values let the UI color
        # them differently (change vs addition) without losing the underlying detail.
        if "DATE CHANGED" in alert:
            _add_dep(alert.split(":", 1)[0], "Earnings timing", "unconfirmed_change", alert)
        elif "NEW" in alert:
            _add_dep(alert.split(":", 1)[0], "Earnings coverage", "unconfirmed_addition", alert)

    trust_sources = []
    for info in source_status.values():
        badge = status_badge(info["status"])
        trust_sources.append({
            "label": info["label"],
            "status": info["status"],
            "statusLabel": badge["label"],
            "tone": badge["tone"],
            "ageLabel": f"{info['age_h']}h" if info["age_h"] is not None else "Unavailable",
            "generatedLabel": info["generated_at"] or "Unavailable",
            "tags": info["tags"],
            "issues": info["issues"],
            "source": info["source"],
        })

    def _band_gap_phrase(row: dict[str, Any]) -> str:
        gap = row.get("bandGapDollar")
        if gap is None:
            return "Band undefined"
        if gap == 0:
            return "In band"
        return f"{fmt_num(abs(gap), prefix='$')} {'above' if gap > 0 else 'below'} band"

    tech_by_ticker = {row["ticker"]: row for row in technical}
    trigger_records = [r for r in normalize_records(trigger_sheet_raw.get("records")) if r.get("ticker")]
    for trigger in trigger_records:
        ticker = trigger.get("ticker")
        trigger_machine_state = trigger.get("deployment_state") or legacy_state(trigger, "action_state")
        conflict = _authority_conflict_meta(ticker, research_review_by_ticker.get(str(ticker or "").upper()), weekly_positioning_text, trigger_machine_state)
        if conflict:
            trigger.update({
                "action_state": "AUTHORITY CONFLICT",
                "deployment_state": "AUTHORITY CONFLICT",
                "why": conflict["reason"],
                "proseConflict": True,
                "proseConflictSource": conflict["proseConflictSource"],
                "conflictMachineState": conflict["conflictMachineState"],
                "conflictProseState": conflict["conflictProseState"],
                "displaySubState": conflict["displaySubState"],
                "reviewOnlyNoApplyArtifact": True,
            })
        trigger_state_for_almost = legacy_state(trigger, "action_state") or trigger.get("deployment_state")
        almost_meta = _almost_substate(ticker, trigger_state_for_almost)
        if almost_meta:
            trigger.update(almost_meta)
        if _earnings_unconfirmed(trigger.get("earnings_date_ir_confirmed")):
            trigger["earningsDateConfirmed"] = False
    trigger_sheet_raw["records"] = trigger_records
    trigger_by_ticker = {r["ticker"]: r for r in trigger_records}
    trigger_summary_raw = trigger_sheet_raw.get("summary") if isinstance(trigger_sheet_raw.get("summary"), dict) else {}
    if trigger_summary_raw:
        deployable_summary = list(trigger_summary_raw.get("deployable_now") or [])
        conflict_names = []
        for name in deployable_summary:
            trigger = trigger_by_ticker.get(name, {})
            machine_state = trigger.get("deployment_state") or legacy_state(trigger, "action_state") or "DEPLOYABLE NOW"
            if _authority_conflict_meta(name, research_review_by_ticker.get(str(name or "").upper()), weekly_positioning_text, machine_state):
                conflict_names.append(name)
        if conflict_names:
            trigger_summary_raw["deployable_now"] = [t for t in deployable_summary if t not in conflict_names]
            conflict_bucket = list(trigger_summary_raw.get("authority_conflict") or [])
            for name in conflict_names:
                if name not in conflict_bucket:
                    conflict_bucket.append(name)
            trigger_summary_raw["authority_conflict"] = conflict_bucket
            trigger_sheet_raw["summary"] = trigger_summary_raw

    deployment_summary = {
        "deployable": [],
        "promotion_review": [],
        "almost": [],
        "blocked": [],
        "below_stop": [],
        "bench": [],
        "watch": [],
        "error": [],
    }
    state_to_bucket = {
        # Canonical state keys (WF32 normalization)
        "DEPLOYABLE NOW": "deployable",
        "PROMOTION REVIEW": "promotion_review",
        "ALMOST DEPLOYABLE": "almost",
        "ALMOST / NEAR-EARNINGS CAUTION": "almost",
        "POST-EARNINGS REVIEW": "almost",
        "BLOCKED": "blocked",
        "BELOW STOP": "below_stop",
        "BENCH": "bench",
        "DO NOT TOUCH": "bench",
        "SYSTEM HOLD": "bench",
        "WATCH / RESEARCH NEEDED": "watch",
        "ERROR": "error",
        # Legacy short-form aliases for stale deployment-check.json artifacts
        "DEPLOYABLE": "deployable",
        "ALMOST": "almost",
        "WATCH": "watch",
    }
    for row in technical:
        bucket = state_to_bucket.get(str(row.get("actionState") or "").upper())
        if bucket:
            deployment_summary[bucket].append(row["ticker"])

    # Authority-conflict names are not clean deployable, but they are still
    # owner-review names. Keep them visible in the Overview promotion/review
    # counter so the summary strip cannot show "0" while a conflict card is
    # present in Today's Action Card.
    for row in technical:
        if row.get("proseConflict") or str(row.get("actionState") or "").upper() == "AUTHORITY CONFLICT":
            ticker = row.get("ticker")
            if ticker and ticker not in deployment_summary["promotion_review"]:
                deployment_summary["promotion_review"].append(ticker)

    priority_buckets = {
        "deployable": 1,
        "promotion_review": 2,
        "almost": 3,
        "blocked": 3,
        "below_stop": 4,
        "bench": 5,
        "watch": 6,
    }
    priority_map: dict[str, int] = {}
    for bucket_name, rank in priority_buckets.items():
        for ticker in deployment_summary.get(bucket_name, []):
            priority_map.setdefault(ticker, rank)

    def _dashboard_state_for_ticker(ticker: str) -> str:
        trigger = trigger_by_ticker.get(ticker, {})
        tech_row = tech_by_ticker.get(ticker, {})
        meta = tracked_universe.get(ticker, {}) if isinstance(tracked_universe.get(ticker), dict) else {}
        action_state = str(tech_row.get("actionState") or legacy_state(trigger, "action_state") or "").upper()
        if tech_row.get("proseConflict") or trigger.get("proseConflict"):
            return "AUTHORITY CONFLICT"
        repair_mode = str(legacy_state(meta, "workflow_state") or "").upper() == "REPAIR" or bool(meta.get("repair_mode"))
        force_below_stop = bool(meta.get("force_do_not_touch_if_below_stop"))

        # Owner-layer repair/bench state should remain visible even when the
        # price is below stop. The below-stop fact still appears in band/risk
        # fields; only explicitly forced names render as BELOW STOP here.
        if action_state in {"DO NOT TOUCH", "BENCH"} and repair_mode and not (tech_row.get("belowStop") and force_below_stop):
            return "BENCH"
        if tech_row.get("belowStop"):
            return "BELOW STOP"

        if "DEPLOYABLE" in action_state and "ALMOST" not in action_state:
            return "DEPLOYABLE"
        if action_state == "PROMOTION REVIEW":
            return "REVIEW"
        if "ALMOST" in action_state:
            return "ALMOST"
        if action_state == "BLOCKED":
            return "BLOCKED"
        if "WATCH" in action_state:
            return "WATCH"
        if action_state in {"DO NOT TOUCH", "BENCH"}:
            return "BENCH"

        deployment_state = str(trigger.get("deployment_state") or "").upper()
        if deployment_state in {"DEPLOYABLE", "ALMOST", "BLOCKED", "WATCH", "BENCH",
                                "DEPLOYABLE NOW", "ALMOST DEPLOYABLE", "WATCH / RESEARCH NEEDED"}:
            return deployment_state
        return "WATCH"

    def _action_card(
        row: dict[str, Any],
        *,
        state_override: str | None = None,
        reason: str | None = None,
        trigger_label: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ticker": row["ticker"],
            "state": state_override or row["actionState"],
            "close": fmt_num(row["close"], prefix="$"),
            "entryBand": row["entry"],
            "referenceBand": row.get("referenceBand"),
            "executionBand": row.get("executionBand"),
            "stop": row["stop"],
            "posture": row.get("posture") or row.get("raw_ma_posture") or "—",
            "displaySubState": row.get("displaySubState"),
            "almostSubState": row.get("almostSubState"),
            "proseConflict": row.get("proseConflict", False),
            "proseConflictSource": row.get("proseConflictSource"),
            "conflictMachineState": row.get("conflictMachineState"),
            "conflictProseState": row.get("conflictProseState"),
            "reviewOnlyNoApplyArtifact": row.get("state") == "DEPLOYABLE" or row.get("actionState") in {"DEPLOYABLE", "DEPLOYABLE NOW"},
            "earningsDateConfirmed": row.get("earningsDateConfirmed"),
            "bandGap": "Machine execution band only — conflict active" if row.get("proseConflict") else _band_gap_phrase(row),
            "bandGapPct": "—" if row.get("proseConflict") else (fmt_pct(row["bandGapPct"], 2) if row["bandGapPct"] is not None else "—"),
            "bandStatus": "AUTHORITY CONFLICT" if row.get("proseConflict") else (row.get("bandStatus") or "—"),
            "stopDist": "See conflict note" if row.get("proseConflict") else (fmt_pct(row["stopDistPct"], 1) if row["stopDistPct"] is not None else "—"),
            "earnings": fmt_date_label(row["earningsDate"], last_trade_dt) if row["earningsDate"] else "No near earnings on file",
            "daysToEarnings": row.get("daysToEarnings"),
            "sqlCanonProofMetadata": row.get("sqlCanonProofMetadata"),
            "sourceArtifactPath": row.get("sourceArtifactPath"),
            "sourceGeneratedAtUtc": row.get("sourceGeneratedAtUtc"),
            "researchArtifactPath": row.get("researchArtifactPath"),
            "researchGeneratedAtUtc": row.get("researchGeneratedAtUtc"),
            "bandStale": row.get("bandStale"),
            "overrideRule": row.get("overrideRule"),
            "overrideReason": row.get("overrideReason"),
            "triggerLabel": trigger_label if trigger_label is not None else ("Trigger conditions met" if row["triggerToday"] else "Wait for better price or cleaner setup"),
            **({"reason": reason} if reason else {}),
        }

    deployable_cards = [
        _action_card(tech_by_ticker[ticker], state_override="DEPLOYABLE")
        for ticker in deployment_summary["deployable"][:3]
        if ticker in tech_by_ticker
    ]
    almost_cards = [
        _action_card(tech_by_ticker[ticker], state_override="ALMOST")
        for ticker in deployment_summary["almost"][:3]
        if ticker in tech_by_ticker
    ]
    review_cards = [
        _action_card(tech_by_ticker[ticker], state_override="REVIEW")
        for ticker in deployment_summary["promotion_review"][:3]
        if ticker in tech_by_ticker and not tech_by_ticker[ticker].get("proseConflict")
    ]
    conflict_cards = [
        _action_card(
            row,
            state_override=row.get("displayState") or "AUTHORITY CONFLICT",
            reason=row.get("reason") or row.get("actionReason"),
            trigger_label="Approval recorded; trigger not live",
        )
        for row in technical
        if row.get("proseConflict")
    ]
    review_cards = conflict_cards + review_cards
    blocked_cards = [
        _action_card(
            tech_by_ticker[ticker],
            state_override="BLOCKED",
            reason=trigger_by_ticker.get(ticker, {}).get("why") or "Blocker remains active in the trigger layer",
            trigger_label="Blocker must clear before deployment",
        )
        for ticker in deployment_summary["blocked"][:3]
        if ticker in tech_by_ticker
    ]
    earnings_pending = [
        _action_card(
            tech_by_ticker[ticker],
            state_override="BLOCKED",
            reason="Earnings catalyst pending — do not deploy until print is reviewed",
            trigger_label="Catalyst pause remains active",
        )
        for ticker, trigger in trigger_by_ticker.items()
        if trigger.get("earnings_blocked") and ticker in tech_by_ticker
    ][:3]
    risk_off = [
        _action_card(
            tech_by_ticker[ticker],
            state_override="BELOW STOP",
            reason=f"Closed {fmt_num(tech_by_ticker[ticker]['close'], prefix='$')} vs stop {tech_by_ticker[ticker]['stop']} — risk-off until repair confirmed",
            trigger_label="Repair confirmation required before re-engagement",
        )
        for ticker in deployment_summary["below_stop"][:3]
        if ticker in tech_by_ticker
    ]

    today_action = {
        "enabled": exec_freshness in {"fresh", "usable_with_caution"},
        "status": exec_freshness,
        "deployable": deployable_cards,
        "promotionReview": review_cards,
        "almost": almost_cards,
        "blocked": blocked_cards,
        "earningsPending": earnings_pending,
        "riskOff": risk_off,
        # Backward-compatible alias, constrained to clean deployable cards only.
        # Review/conflict/almost cards live in their explicit buckets so older
        # consumers cannot treat a fail-closed review state as actionable.
        "actionable": deployable_cards,
        "blockedLegacy": [{"ticker": x["ticker"], "detail": x.get("earnings") or x.get("reason")} for x in earnings_pending],
        "belowStop": [{"ticker": x["ticker"], "detail": x["reason"]} for x in risk_off],
        "message": describe_overall_status(exec_freshness),
    }

    deployment_records = []
    ordered_tickers: list[str] = []
    for bucket_name in ("deployable", "promotion_review", "almost", "blocked", "below_stop", "bench", "watch"):
        for ticker in deployment_summary.get(bucket_name, []):
            if ticker not in ordered_tickers:
                ordered_tickers.append(ticker)
    for ticker in trigger_by_ticker:
        if ticker not in ordered_tickers:
            ordered_tickers.append(ticker)

    for ticker in ordered_tickers:
        r = trigger_by_ticker.get(ticker, {})
        tech_row = tech_by_ticker.get(ticker, {})
        band = entry_bands.get(ticker, {})
        reference_band = reference_band_by_ticker.get(ticker)
        close = tech_row.get("close", r.get("close"))
        band_low = band.get("low")
        band_high = band.get("high")
        position_pct = None
        if close is not None and band_low is not None and band_high is not None and band_high != band_low:
            position_pct = round(((close - band_low) / (band_high - band_low)) * 100, 1)

        state = _dashboard_state_for_ticker(ticker)
        reason = r.get("why") or r.get("reason") or tech_row.get("actionReason") or ""
        if state == "BELOW STOP" and close is not None:
            reason = f"close {fmt_num(close)} is below stop — do not deploy"
        if state == "AUTHORITY CONFLICT":
            reason = tech_row.get("actionReason") or r.get("why") or reason
        deployment_records.append({
            "ticker": ticker,
            "state": state,
            "reason": reason,
            "close": fmt_num(close, prefix="$"),
            "closeRaw": close,
            "bandLabel": tech_row.get("entry") or _band_label_from_values(band),
            "bandLow": band_low,
            "bandHigh": band_high,
            "executionBand": tech_row.get("executionBand") or {
                "low": band_low,
                "high": band_high,
                "stop": band.get("stop"),
                "label": _band_label_from_values(band),
                "stopLabel": _stop_label_from_values(band),
                "lastSet": band.get("band_last_set"),
            },
            "referenceBand": reference_band,
            "bandStatus": tech_row.get("bandStatus") or "—",
            "bandPositionPct": position_pct,
            "bandVisualSuppressed": bool(tech_row.get("bandVisualSuppressed")),
            "repairOverride": bool(tech_row.get("repairOverride")),
            "repairOverrideLabel": tech_row.get("repairOverrideLabel"),
            "overrideRule": tech_row.get("overrideRule"),
            "overrideReason": tech_row.get("overrideReason"),
            "sourceArtifactPath": tech_row.get("sourceArtifactPath") or "tmp/trigger-sheet.json",
            "sourceGeneratedAtUtc": tech_row.get("sourceGeneratedAtUtc") or trigger_sheet_raw.get("generated_at_utc"),
            "researchArtifactPath": tech_row.get("researchArtifactPath"),
            "researchGeneratedAtUtc": tech_row.get("researchGeneratedAtUtc"),
            "bandStale": tech_row.get("bandStale"),
            "stop": tech_row.get("stop") or _stop_label_from_values(band),
            "stopDistPct": tech_row.get("stopDistPct"),
            "posture": tech_row.get("posture") or tech_row.get("raw_ma_posture") or "—",
            "earningsDate": tech_row.get("earningsDate"),
            "earningsDateConfirmed": tech_row.get("earningsDateConfirmed"),
            "daysToEarnings": tech_row.get("daysToEarnings"),
            "sqlCanonProofMetadata": tech_row.get("sqlCanonProofMetadata"),
            "displaySubState": tech_row.get("displaySubState") or r.get("displaySubState"),
            "almostSubState": tech_row.get("almostSubState") or r.get("almostSubState"),
            "proseConflict": bool(tech_row.get("proseConflict") or r.get("proseConflict")),
            "proseConflictSource": tech_row.get("proseConflictSource") or r.get("proseConflictSource"),
            "conflictMachineState": tech_row.get("conflictMachineState") or r.get("conflictMachineState"),
            "conflictProseState": tech_row.get("conflictProseState") or r.get("conflictProseState"),
            "reviewOnlyNoApplyArtifact": state == "DEPLOYABLE" or bool(r.get("reviewOnlyNoApplyArtifact")),
            "priority": f"P{priority_map.get(ticker, 9)}",
        })

    history = update_history({"generated_at_utc": now.isoformat(), "technical": technical})

    earnings = sorted(
        [{"ticker": r.get("ticker"), "date": r.get("next_earnings_date")} for r in earnings_records if r.get("ticker") and r.get("next_earnings_date")],
        key=lambda item: item["date"],
    )
    earnings_alerts = earn_raw.get("watchlist_alerts", [])

    risk_thresholds = pf_raw.get("risk_thresholds", {}) if isinstance(pf_raw.get("risk_thresholds"), dict) else {}
    sizing_rules = pf_raw.get("sizing_rules", []) if isinstance(pf_raw.get("sizing_rules"), list) else []
    escalation_triggers = pf_raw.get("escalation_triggers", []) if isinstance(pf_raw.get("escalation_triggers"), list) else []
    regime_indicators = [
        {
            "label": item.get("label"),
            "value": item.get("value"),
            "detail": item.get("detail"),
            "colorKey": item.get("color_key", "amber"),
        }
        for item in pf_raw.get("regime_indicators", [])
    ]

    tech_concentration_tickers = set(sector_map.get("Tech", []))
    core_positions = pf.get("core", [])
    active_positions = pf.get("core", []) + pf.get("tactical", [])
    max_single = risk_thresholds.get("max_single_position_normal", 15)
    max_sector = risk_thresholds.get("max_sector_pct", 35)
    min_cash = risk_thresholds.get("min_cash_pct", 5)
    compliance_checks = [
        {
            "label": "Position sizing",
            "status": "warn" if any((p.get("weight") or 0) >= max_single for p in core_positions) else "ok",
            "detail": f"{sum(1 for p in core_positions if (p.get('weight') or 0) >= max_single)} core position(s) at or above {max_single}% normal cap.",
        },
        {
            "label": "Tech concentration",
            "status": "warn" if sum((p.get("weight") or 0) for p in active_positions if p.get("ticker") in tech_concentration_tickers) > max_sector else "ok",
            "detail": f"Tech sleeve is {round(sum((p.get('weight') or 0) for p in active_positions if p.get('ticker') in tech_concentration_tickers), 2)}% against {max_sector}% sector threshold.",
        },
        {
            "label": "Stop discipline",
            "status": "bad" if any(row["belowStop"] for row in technical) else "ok",
            "detail": "; ".join(f"{row['ticker']} below stop" for row in technical if row["belowStop"]) or "No tracked name is below stop.",
        },
        {
            "label": "Cash reserve",
            "status": "ok" if (pf.get("cash") or 0) >= min_cash else "bad",
            "detail": f"Cash is {pf.get('cash', 0)}% against minimum {min_cash}%.",
        },
        {
            "label": "Data integrity",
            "status": "bad" if validation["summary"]["critical"] else ("warn" if validation["summary"]["warning"] else "ok"),
            "detail": f"{validation['summary']['critical']} critical and {validation['summary']['warning']} warning integrity issue(s).",
        },
    ]

    overview_cards = [
        {"label": "S&P 500", "value": fmt_num(market["spx"]), "detail": "Cash index", "tone": "ok"},
        {"label": "VIX", "value": fmt_num(market["vix"]), "detail": "Volatility context", "tone": "warn" if (market["vix"] or 0) >= 20 else "ok"},
        {"label": "10Y Treasury", "value": fmt_pct(market["treasuries"]["y10"], 2), "detail": "Rates backdrop", "tone": "info"},
        {"label": "DXY", "value": fmt_num(market["dxy"]), "detail": "Dollar context", "tone": "info"},
        {"label": "Brent", "value": fmt_num(market["brent"], prefix="$"), "detail": "Energy complex", "tone": "info"},
        {"label": "Fed funds", "value": f"{fmt_num(market['fed']['target_low'])}-{fmt_num(market['fed']['target_high'])}%" if market['fed']['target_low'] is not None and market['fed']['target_high'] is not None else "—", "detail": "Manual dependency if post-FOMC not updated", "tone": "warn" if fed.get("manual_update_required") else "info"},
    ]

    alerts: list[dict[str, Any]] = []
    if exec_freshness in {"partial", "stale", "missing"}:
        alerts.append({"tone": "bad" if exec_freshness in {"stale", "missing"} else "warn", "title": "Execution trust degraded", "detail": describe_overall_status(exec_freshness)})
    if manual_dependencies:
        alerts.append({"tone": "warn", "title": "Manual and unconfirmed dependencies remain", "detail": "; ".join(dep["detail"] for dep in manual_dependencies[:3])})
    if validation["summary"]["critical"]:
        alerts.append({"tone": "bad", "title": "Integrity contradictions detected", "detail": f"{validation['summary']['critical']} critical issue(s) need attention before trusting the rendered view."})
    elif validation["summary"]["warning"]:
        alerts.append({"tone": "warn", "title": "Integrity warnings present", "detail": f"{validation['summary']['warning']} warning issue(s) were surfaced by the generator."})

    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")

    consistency_raw = load_json(TMP / "universe-consistency.json") or {}
    decision_queue = _build_decision_queue("post-close")
    workflow_focus = _build_workflow_focus()
    handoff_proof_state = _build_handoff_proof_state()

    payload = {
        "generated_at": generated_at,
        "last_trade_date": last_trade,
        "exec_freshness": exec_freshness,
        "source_freshness": source_freshness,
        "market_session": market_session,
        "vault_freshness": vault_freshness,
        "history": history,
        "freshness": [
            {
                "label": info["label"],
                "time": info["generated_at"] or "Unavailable",
                "fresh": info["status"] in {"fresh", "usable_with_caution"},
                "age_h": info["age_h"],
                "status": info["status"],
                "issues": info["issues"],
            }
            for info in source_status.values()
        ],
        "provenance": provenance,
        "trust": {
            "overall_status": exec_freshness,
            "overall_label": status_badge(exec_freshness)["label"],
            "summary": describe_overall_status(exec_freshness),
            "source_freshness": source_freshness,
            "sources": trust_sources,
            "manual_dependencies": manual_dependencies,
            "handoff_proof_state": handoff_proof_state,
            "sql_canon": sql_canon,
            "consistency": consistency_raw,
        },
        "validation": validation,
        "market": market,
        "policy_expectations": policy_expectations,
        "credit_spreads": credit_spreads,
        "market_breadth": market_breadth,
        "macro_regime": macro_regime,
        "sectors_relative": sectors_relative,
        "technical": technical,
        "sql_canon": sql_canon,
        "reference_bands": {
            "source": "tmp/band-proposals.json",
            "generated_at_utc": band_proposals_raw.get("generated_at_utc"),
            "data_date": max((b.get("dataDate") for b in reference_band_by_ticker.values() if b), default=None),
            "authority": {
                "reference_band_visibility_only": True,
                "execution_band_mutation_allowed": False,
                "capital_action_allowed": False,
                "owner_approval_inferred": False,
                "trade_or_account_authority": False,
                "sizing_sleeve_cash_risk_rule_authority": False,
            },
            "by_ticker": {ticker: band for ticker, band in reference_band_by_ticker.items() if band},
        },
        "deployment_summary": deployment_summary,
        "deployment_records": deployment_records,
        "earnings": earnings,
        "earnings_alerts": earnings_alerts,
        "portfolio": pf,
        "fundamental_trends": fundamental_trends,
        "sizing_rules": sizing_rules,
        "escalation_triggers": escalation_triggers,
        "regime_indicators": regime_indicators,
        "risk_thresholds": risk_thresholds,
        "today_action": today_action,
        "workflow_focus": workflow_focus,
        "decision_queue": decision_queue,
        "daily_review": decision_queue["daily_review"],
        "market_intelligence": decision_queue["market_intelligence"],
        "sector_weights": sector_weights,
        "ui": {
            "alerts": alerts,
            "overview_cards": overview_cards,
            "compliance_checks": compliance_checks,
        },
        "trigger_sheet": trigger_sheet_raw,
        "post_earnings": post_earnings_raw,
    }

    shape_warnings.extend(_validate_payload_shape(
        today_action=today_action,
        deployment_records=deployment_records,
        macro_regime=macro_regime,
        sectors_relative=sectors_relative,
        post_earnings=post_earnings_raw or {},
        workflow_focus=workflow_focus,
    ))
    _merge_shape_warnings(payload["validation"], shape_warnings)

    return payload
