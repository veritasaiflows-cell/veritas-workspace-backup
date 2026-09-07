"""Build review-only ticker intelligence cards for WF77.

Cards are derived routing/review artifacts. They are not canon, approval, sizing,
portfolio mutation, or trade/account authority.
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from board_state_contract import deployment_contract
from finance_sql_canon_access import (
    FinanceSqlCanonAccess,
    ReferenceLevelRecord,
    UniverseMembershipRecord,
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
SQL_CANON_DB = WORKSPACE / "state" / "finance" / "finance-canon.sqlite"
LEGACY_PRODUCTION_COMPATIBILITY_COUNT = 42
ACTIVE_INTERNAL_SCOPE = "active_internal_universe"
ENTRY_STOP_REFERENCE_METADATA_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_level_source_timestamp",
    "reference_level_source_sha256",
    "reference_level_owner_source_path",
)
ENTRY_STOP_REFERENCE_METADATA_AUTHORITY_BOUNDARY = (
    "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority"
)
ANALYST_PROJECTION_FIELDS = {
    "source_status",
    "as_of",
    "source_lineage",
    "cross_check_conflict",
}
ANALYST_LINEAGE_FIELDS = {
    "provider",
    "provider_symbol",
    "source_url",
    "retrieval_method",
    "evidence_digest_sha256",
}
ANALYST_SOURCE_STATUSES = {
    "auto_sourced_yfinance",
    "partial_yfinance",
    "missing_yfinance",
    "missing_or_partial",
    "unavailable",
}
ANALYST_CROSS_CHECK_STATUSES = {"pass", "fail", "stale", "unavailable"}
ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS = {
    "display_reference_only": True,
    "fallback_required": True,
    "recommendation_allowed": False,
    "deployment_or_action_state_change_allowed": False,
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
}

AUTHORITY_BOUNDARY = {
    "artifact_role": "derived_review_and_question_routing_surface_only",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sizing_apply_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_card": False,
    "paper_order_cancel_allowed_by_card": False,
    "durable_sql_canon_current_state_allowed": True,
    "sql_canon_mutation_allowed": False,
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


def find_ticker_keyed_entry(obj: Any, ticker: str, key_name: str) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    rows = obj.get(key_name)
    if not isinstance(rows, dict):
        return None
    normalized = ticker.upper()
    for key, value in rows.items():
        if isinstance(key, str) and key.upper() == normalized and isinstance(value, dict):
            return {"ticker": normalized, **value}
    return None


def find_analyst_consensus_entry(obj: Any, ticker: str) -> dict[str, Any] | None:
    """Accept only the quarantined four-field consumer projection."""

    if (
        not isinstance(obj, dict)
        or obj.get("status") != "placeholder_manual_required"
        or obj.get("consumer_posture") != "quarantined_source_evidence_only_not_decision_input"
        or not isinstance(obj.get("tickers"), dict)
    ):
        return None
    normalized = ticker.upper()
    row = next(
        (
            value
            for key, value in obj["tickers"].items()
            if isinstance(key, str) and key.upper() == normalized and isinstance(value, dict)
        ),
        None,
    )
    lineage = row.get("source_lineage") if isinstance(row, dict) else None
    digest = lineage.get("evidence_digest_sha256") if isinstance(lineage, dict) else None
    if (
        not isinstance(row, dict)
        or set(row) != ANALYST_PROJECTION_FIELDS
        or row.get("source_status") not in ANALYST_SOURCE_STATUSES
        or not isinstance(lineage, dict)
        or set(lineage) != ANALYST_LINEAGE_FIELDS
        or not all(isinstance(lineage.get(field), str) and lineage.get(field) for field in ANALYST_LINEAGE_FIELDS - {"evidence_digest_sha256"})
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in digest)
        or row.get("cross_check_conflict") not in ANALYST_CROSS_CHECK_STATUSES
    ):
        return None
    return dict(row)


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


STALE_REFERENCE_BAND = "STALE_REFERENCE_BAND"
LOW_CONFIDENCE_REFERENCE_MAX = 2


def low_confidence_reference_band_requires_refresh(
    auto_tier_entry: dict[str, Any] | None,
    sql_canon_reference: dict[str, Any] | None,
    computed_band_status: str | None,
) -> bool:
    """Require a refreshed reference band before exposing a Tier A hard-stop claim."""

    if str((auto_tier_entry or {}).get("auto_tier") or "") != "Tier A":
        return False
    if computed_band_status != "BELOW_STOP":
        return False
    try:
        confidence = int((sql_canon_reference or {}).get("reference_confidence"))
    except (TypeError, ValueError):
        return False
    return confidence <= LOW_CONFIDENCE_REFERENCE_MAX


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


PERIOD_SENSITIVE_FUNDAMENTAL_FIELDS = (
    "revenue",
    "revenue_prior",
    "revenue_yoy_pct",
    "net_income",
    "net_income_prior",
    "net_income_yoy_pct",
    "diluted_eps",
    "diluted_eps_prior",
    "eps_yoy_pct",
    "gross_profit",
    "gross_margin_pct",
    "operating_income",
    "operating_margin_pct",
    "net_margin_pct",
    "ebitda",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "free_cash_flow_prior",
    "free_cash_flow_yoy_pct",
    "fcf_per_share",
    "fcf_per_share_prior",
    "fcf_per_share_yoy_pct",
    "cash_and_equivalents",
    "total_debt",
    "net_debt",
    "debt_to_annualized_ebitda",
    "total_assets",
    "total_equity",
    "invested_capital_proxy",
    "roic_proxy_pct",
    "debt_issued",
    "debt_repaid",
    "net_debt_issued",
    "dividends_paid",
    "share_repurchases",
    "net_share_repurchases",
    "buyback_yield_pct",
    "dividend_yield_pct",
    "shareholder_yield_pct",
    "stock_based_compensation",
    "sbc_pct_of_revenue",
    "sbc_pct_of_fcf",
    "capital_return_to_fcf_pct",
    "capital_allocation_anomalies",
    "capital_allocation_anomaly_count",
    "capital_allocation_quality",
    "capital_allocation_notes",
    "enterprise_value",
    "trailing_pe",
    "forward_pe",
    "fcf_yield_pct",
    "earnings_yield_pct",
    "price_to_sales",
    "price_to_book",
    "ev_to_ebitda_proxy",
    "ev_to_fcf_proxy",
)


def _period_tuple(value: Any) -> tuple[int, int, int] | None:
    try:
        year, month, day = (int(part) for part in str(value).split("-")[:3])
        return year, month, day
    except (TypeError, ValueError):
        return None


def latest_official_claim_period(official_claims: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    latest_period: str | None = None
    latest_claim: dict[str, Any] | None = None
    latest_key: tuple[int, int, int] | None = None
    for claim in official_claims.values():
        if not isinstance(claim, dict):
            continue
        period = claim.get("period")
        key = _period_tuple(period)
        if key is not None and (latest_key is None or key > latest_key):
            latest_key = key
            latest_period = str(period)
            latest_claim = claim
    return latest_period, latest_claim


def build_period_aligned_fundamentals(
    fundamentals: dict[str, Any] | None,
    official_claims: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prevent a newer official release from being mixed with an older provider row.

    A validated official capture may advance the earnings period before the broad
    normalized 10-Q metrics refresh is available.  In that state, retain the old
    row only as prior context, withhold period-sensitive fields, and overlay only
    explicitly captured current-period values.  This makes the stale boundary
    visible instead of silently presenting a hybrid-period card.
    """
    base = dict(fundamentals or {})
    normalized_period = base.get("period_end")
    official_period, _latest_claim = latest_official_claim_period(official_claims)
    normalized_key = _period_tuple(normalized_period)
    official_key = _period_tuple(official_period)
    if official_key is None or (normalized_key is not None and official_key <= normalized_key):
        alignment = {
            "status": "aligned" if official_key is None or normalized_key == official_key else "normalized_metrics_newer_than_official_capture",
            "latest_official_period_end": official_period,
            "normalized_metrics_period_end": normalized_period,
            "normalized_metrics_stale": False,
            "source_url": None,
            "withheld_fields": [],
        }
        base["period_alignment"] = alignment
        return base, alignment

    prior = {field: base.get(field) for field in PERIOD_SENSITIVE_FUNDAMENTAL_FIELDS if field in base}
    source_url = None
    for claim in official_claims.values():
        if isinstance(claim, dict) and claim.get("period") == official_period:
            source_url = claim.get("source_url") or source_url
    for field in PERIOD_SENSITIVE_FUNDAMENTAL_FIELDS:
        base[field] = None
    base["period_type"] = "quarterly"
    base["period_end"] = official_period
    base["comparison_period_end"] = normalized_period
    base["source"] = "official_sec_earnings_release_period_overlay"
    base["source_tier"] = "official_primary_review_only"
    base["data_quality"] = "partial"
    base["valuation_context"] = "partial_newer_period_metrics_withheld"
    base["quality_notes"] = [
        "A newer validated official earnings release was captured.",
        "Period-sensitive normalized fields not present in the release are withheld until the 10-Q/normalized refresh catches up.",
    ]

    metrics_claim = official_claims.get("quarterly_metrics")
    metrics = metrics_claim.get("value") if isinstance(metrics_claim, dict) and isinstance(metrics_claim.get("value"), dict) else {}
    period_bridge_fields = (
        "revenue",
        "revenue_prior",
        "net_income",
        "net_income_prior",
        "diluted_eps",
        "diluted_eps_prior",
    )
    verified_period_bridge = (
        isinstance(metrics_claim, dict)
        and metrics_claim.get("period") == official_period
        and metrics.get("official_period_bridge_verified") is True
        and metrics.get("period_bridge_validation") == "matching_period_official_10q"
        and all(metrics.get(field) is not None for field in period_bridge_fields)
    )
    if verified_period_bridge:
        for field in (
            "revenue",
            "revenue_prior",
            "revenue_yoy_pct",
            "net_income",
            "net_income_prior",
            "net_income_yoy_pct",
            "diluted_eps",
            "diluted_eps_prior",
            "eps_yoy_pct",
            "operating_cash_flow",
            "free_cash_flow",
            "free_cash_flow_yoy_pct",
        ):
            if metrics.get(field) is not None:
                base[field] = metrics[field]
        base["comparison_period_end"] = metrics.get("comparison_period_end") or normalized_period
        base["source"] = "official_sec_10q_period_bridge"
        base["source_tier"] = "official_primary_review_only"
        base["data_quality"] = "partial_official_period_bridge"
        base["valuation_context"] = "partial_current_period_10q_bridge"
        base["quality_notes"] = [
            "A matching-period official 10-Q bridge verified revenue, net income, and diluted EPS against the newer earnings period.",
            "The normalized provider refresh is still pending for non-bridged period-sensitive fields; no values were inferred.",
        ]
        if metrics_claim.get("source_url"):
            source_url = metrics_claim.get("source_url")
        alignment = {
            "status": "official_period_bridge_verified",
            "latest_official_period_end": official_period,
            "normalized_metrics_period_end": normalized_period,
            "normalized_metrics_stale": False,
            "normalized_provider_refresh_pending": True,
            "source_url": source_url,
            "withheld_fields": [field for field in PERIOD_SENSITIVE_FUNDAMENTAL_FIELDS if base.get(field) is None],
            "prior_normalized_metrics_retained": True,
            "bridge_required_fields": list(period_bridge_fields),
            "bridge_source_type": metrics.get("source_kind"),
        }
        base["prior_normalized_metrics"] = {
            "period_end": normalized_period,
            "source": fundamentals.get("source") if fundamentals else None,
            "metrics": prior,
        }
        base["period_alignment"] = alignment
        return base, alignment
    for field in ("revenue", "diluted_eps", "operating_cash_flow", "free_cash_flow", "free_cash_flow_yoy_pct"):
        if metrics.get(field) is not None:
            base[field] = metrics[field]
    growth_claim = official_claims.get("growth_bridge")
    growth = growth_claim.get("value") if isinstance(growth_claim, dict) and isinstance(growth_claim.get("value"), dict) else {}
    if growth.get("reported_sales_growth_pct") is not None:
        base["revenue_yoy_pct"] = growth["reported_sales_growth_pct"]
    if metrics_claim and metrics_claim.get("source_url"):
        source_url = metrics_claim.get("source_url")
    alignment = {
        "status": "newer_official_period_normalized_metrics_catch_up_required",
        "latest_official_period_end": official_period,
        "normalized_metrics_period_end": normalized_period,
        "normalized_metrics_stale": True,
        "source_url": source_url,
        "withheld_fields": [field for field in PERIOD_SENSITIVE_FUNDAMENTAL_FIELDS if base.get(field) is None],
        "prior_normalized_metrics_retained": True,
    }
    base["prior_normalized_metrics"] = {
        "period_end": normalized_period,
        "source": fundamentals.get("source") if fundamentals else None,
        "metrics": prior,
    }
    base["period_alignment"] = alignment
    return base, alignment


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


SECTOR_ALIASES = {
    "AEROSPACE & DEFENSE": "INDUSTRIALS",
    "DEFENSE": "INDUSTRIALS",
    "DIVERSIFIED QUALITY": "FINANCIALS",
    "FINANCIAL INFRASTRUCTURE": "FINANCIALS",
    "INFRASTRUCTURE": "INDUSTRIALS",
    "INFORMATION TECHNOLOGY": "TECHNOLOGY",
    "MATERIALS / INFRASTRUCTURE": "MATERIALS",
    "TECH": "TECHNOLOGY",
}


def sector_record(data: dict[str, Any] | None, sector_or_ticker: str | None) -> dict[str, Any] | None:
    if not sector_or_ticker:
        return None
    raw = str(sector_or_ticker).strip()
    needle = raw.upper()
    alias = SECTOR_ALIASES.get(needle)
    candidates = [needle]
    if alias and alias not in candidates:
        candidates.append(alias)
    for row in (data or {}).get("sectors") or []:
        if not isinstance(row, dict):
            continue
        row_ticker = str(row.get("ticker", "")).upper()
        row_sector = str(row.get("sector", "")).upper()
        for candidate in candidates:
            if row_ticker == candidate or row_sector == candidate:
                matched = dict(row)
                matched["sector_query"] = raw
                matched["sector_match_basis"] = "exact" if candidate == needle else f"alias:{needle}->{candidate}"
                return matched
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
        "period_alignment": (fundamentals or {}).get("period_alignment"),
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
        "period_end": (fundamentals or {}).get("period_end"),
        "growth": metric(fundamentals or {}, ["revenue_yoy_pct", "net_income_yoy_pct", "eps_yoy_pct", "free_cash_flow_yoy_pct"]),
        "profitability": metric(fundamentals or {}, ["gross_margin_pct", "operating_margin_pct", "net_margin_pct", "roic_proxy_pct"]),
        "cash_flow": metric(fundamentals or {}, ["operating_cash_flow", "free_cash_flow", "fcf_per_share", "fcf_yield_pct"]),
        "balance_sheet": metric(fundamentals or {}, ["cash_and_equivalents", "total_debt", "net_debt", "debt_to_annualized_ebitda"]),
        "valuation": metric(fundamentals or {}, ["market_cap", "enterprise_value", "trailing_pe", "forward_pe", "price_to_sales", "price_to_book", "ev_to_ebitda_proxy", "ev_to_fcf_proxy", "earnings_yield_pct"]),
        "capital_returns": metric(fundamentals or {}, ["buyback_yield_pct", "dividend_yield_pct", "shareholder_yield_pct", "capital_return_to_fcf_pct"]),
        "data_quality": (fundamentals or {}).get("data_quality"),
        "period_alignment": (fundamentals or {}).get("period_alignment"),
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


def pct_fragment(label: str, value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{label} {float(value):.2f}%"
    except (TypeError, ValueError):
        return None


def claim_value_summary(claim: dict[str, Any] | None) -> str | None:
    if not claim:
        return None
    value = claim.get("value")
    if isinstance(value, dict):
        summary = value.get("summary")
        if summary:
            return str(summary)
        drivers = value.get("demand_drivers")
        if isinstance(drivers, list) and drivers:
            return "Demand drivers: " + ", ".join(str(item) for item in drivers[:4])
        keys = [key for key in value.keys() if key not in {"rationale", "note"}]
        if keys:
            return "Captured official fields: " + ", ".join(str(key) for key in keys[:5])
    if value:
        return str(value)
    return claim.get("claim_text")


def claim_evidence(label: str, claim: dict[str, Any] | None) -> dict[str, Any] | None:
    if not claim:
        return None
    summary = claim_value_summary(claim)
    if not summary:
        return None
    return {
        "label": label,
        "summary": summary,
        "source_url": claim.get("source_url"),
        "source_section": claim.get("source_section"),
        "period": claim.get("period"),
        "status": claim.get("capture_status") or claim.get("status"),
        "source_artifact": str(OFFICIAL_EARNINGS_BRIDGE_PATH.relative_to(WORKSPACE)),
    }


def build_review_thesis_context(
    ticker: str,
    fundamentals: dict[str, Any] | None,
    official_claims: dict[str, Any],
    sector_entry: dict[str, Any] | None,
    price_band_stop: dict[str, Any],
    missing: list[dict[str, str]],
    universe_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    if (fundamentals or {}).get("instrument_type") == "etf_or_macro_proxy":
        evidence.append(
            {
                "label": "etf_or_macro_proxy_profile",
                "summary": f"ETF/macro proxy classified for {(fundamentals or {}).get('sector') or 'broad exposure'}; operating-company fundamentals are not applicable.",
                "source_artifact": str(FUNDAMENTALS_PATH.relative_to(WORKSPACE)),
                "portfolio_role": (fundamentals or {}).get("portfolio_role"),
                "coverage_lane": (fundamentals or {}).get("coverage_lane"),
            }
        )
    growth_bits = [
        pct_fragment("revenue YoY", (fundamentals or {}).get("revenue_yoy_pct")),
        pct_fragment("EPS YoY", (fundamentals or {}).get("eps_yoy_pct")),
        pct_fragment("FCF YoY", (fundamentals or {}).get("free_cash_flow_yoy_pct")),
    ]
    growth_summary = ", ".join(bit for bit in growth_bits if bit)
    if growth_summary:
        evidence.append(
            {
                "label": "fundamental_snapshot",
                "summary": growth_summary,
                "source_artifact": str(FUNDAMENTALS_PATH.relative_to(WORKSPACE)),
                "period_end": (fundamentals or {}).get("period_end"),
                "source_tier": (fundamentals or {}).get("source_tier"),
            }
        )
    for label, key in (
        ("management_explanation", "management_explanation"),
        ("growth_bridge", "growth_bridge"),
        ("orders_backlog_or_activity", "orders_backlog"),
    ):
        row = claim_evidence(label, official_claims.get(key))
        if row:
            evidence.append(row)
    if sector_entry:
        evidence.append(
            {
                "label": "sector_proxy_context",
                "summary": f"{sector_entry.get('sector')} via {sector_entry.get('ticker')} versus SPY; leadership={sector_entry.get('leadership_status')}",
                "source_artifact": str(SECTOR_EXPANSION_BOARD_PATH.relative_to(WORKSPACE)),
                "as_of": sector_entry.get("as_of"),
                "match_basis": sector_entry.get("sector_match_basis"),
            }
        )
    if not evidence:
        return {
            "thesis": "Card-level thesis synthesis requires source-open review of fundamentals, official captures, sector context, and technical posture before final answer.",
            "bull_case_inputs": ["latest_earnings_performance", "key_financial_metrics", "official_capture_developments_orders_backlog", "current_sector_performance", "technical_posture"],
            "bear_case_inputs": ["risk_register", "missing_or_stale_evidence", "valuation", "price_band_stop"],
            "entry_context": price_band_stop,
            "source_open_required": True,
        }

    name = (universe_entry or {}).get("name") or ticker
    band_status = price_band_stop.get("band_status") or "unknown band status"
    risk_count = len([item for item in missing if item.get("severity") in {"blocking", "context"}])
    thesis = (
        f"{name} has a review-only synthesized Tier A thesis from local sourced artifacts: "
        f"{evidence[0]['summary']}. Entry posture is {band_status}; "
        f"{risk_count} evidence/freshness gaps still require review before decision-grade use."
    )
    return {
        "status": "synthesized_review_only_source_backed",
        "thesis": thesis,
        "bull_case_inputs": ["latest_earnings_performance", "key_financial_metrics", "official_capture_developments_orders_backlog", "current_sector_performance", "technical_posture"],
        "bear_case_inputs": ["risk_register", "missing_or_stale_evidence", "valuation", "price_band_stop"],
        "entry_context": price_band_stop,
        "synthesis_evidence": evidence,
        "source_open_required": True,
        "limits": [
            "Review-only synthesis generated from existing local sourced artifacts.",
            "This does not clear owner approval, capital deployment, paper/live execution, or final recommendation authority.",
        ],
    }


def build_review_competitive_moat(
    fundamentals: dict[str, Any] | None,
    official_claims: dict[str, Any],
    sector_entry: dict[str, Any] | None,
    universe_entry: dict[str, Any] | None,
    instrument_type: str | None,
) -> dict[str, Any]:
    if instrument_type == "etf_or_macro_proxy":
        return {
            "status": "not_applicable_etf_or_macro_proxy",
            "summary": "ETF/macro proxy; use sector/proxy profile rather than issuer competitive moat.",
            "evidence": [
                {
                    "label": "instrument_type",
                    "summary": "Ticker is classified as etf_or_macro_proxy in the local fundamentals layer.",
                    "source_artifact": str(FUNDAMENTALS_PATH.relative_to(WORKSPACE)),
                }
            ],
            "source_open_required": True,
        }

    evidence: list[dict[str, Any]] = []
    profitability = []
    for label, key in (
        ("operating margin", "operating_margin_pct"),
        ("net margin", "net_margin_pct"),
        ("ROIC proxy", "roic_proxy_pct"),
    ):
        bit = pct_fragment(label, (fundamentals or {}).get(key))
        if bit:
            profitability.append(bit)
    if profitability:
        evidence.append(
            {
                "label": "profitability_quality",
                "summary": ", ".join(profitability),
                "source_artifact": str(FUNDAMENTALS_PATH.relative_to(WORKSPACE)),
                "period_end": (fundamentals or {}).get("period_end"),
                "source_tier": (fundamentals or {}).get("source_tier"),
            }
        )
    for label, key in (
        ("management_explanation", "management_explanation"),
        ("demand_or_backlog_activity", "orders_backlog"),
    ):
        row = claim_evidence(label, official_claims.get(key))
        if row:
            evidence.append(row)
    if sector_entry:
        evidence.append(
            {
                "label": "sector_proxy_position",
                "summary": f"{sector_entry.get('sector')} proxy {sector_entry.get('ticker')} leadership={sector_entry.get('leadership_status')}",
                "source_artifact": str(SECTOR_EXPANSION_BOARD_PATH.relative_to(WORKSPACE)),
                "as_of": sector_entry.get("as_of"),
                "match_basis": sector_entry.get("sector_match_basis"),
            }
        )
    if not evidence:
        return {
            "status": "not_yet_structured_source_open_required",
            "summary": None,
            "evidence": [],
            "note": "Ticker cards now reserve this field; populate only from sourced thesis/official/research artifacts, not model inference.",
        }
    name = (universe_entry or {}).get("name") or (fundamentals or {}).get("ticker") or "Ticker"
    return {
        "status": "partially_structured_source_backed_review_required",
        "summary": f"{name} has preliminary moat evidence from profitability, official operating commentary, demand/activity signals, or sector proxy context; this is not a final competitive-position conclusion.",
        "evidence": evidence,
        "source_open_required": True,
        "limits": [
            "Evidence supports structured review coverage, not a final moat grade.",
            "Peer comparison and source-open competitive research remain required before decision-grade use.",
        ],
    }


def compact_source(path: Path, data: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(WORKSPACE)),
        "exists": path.exists(),
        "generated_at_utc": (data or {}).get("generated_at_utc"),
        "status": (data or {}).get("status"),
    }


def review_post_close_quote_available(post_close_quote: dict[str, Any] | None) -> bool:
    if not isinstance(post_close_quote, dict):
        return False
    market_date = str(post_close_quote.get("market_date") or "").strip()
    retrieved_at_utc = str(post_close_quote.get("retrieved_at_utc") or "").strip()
    source = str(post_close_quote.get("source") or "").strip()
    return bool(market_date and retrieved_at_utc and source)


def effective_review_fresh_quote_required(
    readiness: dict[str, Any] | None,
    post_close_quote: dict[str, Any] | None,
) -> bool:
    if not bool((readiness or {}).get("fresh_quote_required")):
        return False
    return not review_post_close_quote_available(post_close_quote)


def metric(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: row.get(key) for key in keys if key in row}


def build_recommendation_posture(
    ticker: str,
    readiness: dict[str, Any] | None,
    post_close_quote: dict[str, Any] | None,
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
    fresh_required = effective_review_fresh_quote_required(readiness, post_close_quote)
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
    post_close_quote: dict[str, Any] | None,
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
    items.append({
        "family": "analyst_consensus_ratings_targets",
        "severity": "context",
        "status": "analyst_quarantined",
        "detail": "Analyst evidence is lineage-only and cannot affect completeness, confidence, bands, invalidation, thesis, or recommendation posture.",
    })
    if effective_review_fresh_quote_required(readiness, post_close_quote):
        items.append({"family": "fresh_price_quote", "severity": "context", "status": "stale_until_refreshed", "detail": "Readiness packet uses pre-Tuesday/reference price and requires fresh quote confirmation"})
    return items


def reference_level_compatibility_projection(record: ReferenceLevelRecord) -> dict[str, Any]:
    """Project a verified durable record to the frozen eight-field card shape."""

    return {
        "ticker": record.ticker,
        "reference_price_low": record.reference_price_low,
        "reference_price_high": record.reference_price_high,
        "reference_invalidation_level": record.reference_invalidation_level,
        "reference_confidence": record.reference_confidence,
        "reference_band_status": record.reference_band_status,
        "authority_class": record.authority_class,
        "fallback_rule": record.fallback_rule,
    }


def build_entry_stop_reference_metadata(
    ticker: str,
    record: ReferenceLevelRecord | None,
) -> dict[str, Any]:
    """Build the frozen display-only compatibility shape from verified SQL lineage."""

    ticker = ticker.upper()
    values: dict[str, Any] = {}
    source_rows: list[dict[str, Any]] = []
    if record is not None:
        values = {
            "reference_price_low": record.reference_price_low,
            "reference_price_high": record.reference_price_high,
            "reference_invalidation_level": record.reference_invalidation_level,
            "reference_level_source_timestamp": record.source_generated_at_utc,
            "reference_level_source_sha256": record.source_artifact_sha256,
            "reference_level_owner_source_path": record.source_artifact_path,
        }
        source_rows = [
            {
                "key": f"{ticker}:{field}",
                "source_artifact_path": record.source_artifact_path,
                "source_artifact_hash": record.source_artifact_sha256,
                "freshness_status": record.source_status,
                "last_reconciled_at_utc": record.lineage_inserted_at_utc,
                "updated_at_utc": record.lineage_inserted_at_utc,
            }
            for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS
        ]
    missing_fields = [field for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS if field not in values]
    issues = ["durable_reference_record_missing"] if record is None else []
    return {
        "schema_version": "wf72_entry_stop_reference_metadata.v1",
        "status": "available" if record is not None else "fallback_required",
        "ticker": ticker,
        "authority_boundary": ENTRY_STOP_REFERENCE_METADATA_AUTHORITY_BOUNDARY,
        "sql_cache_path": "state/finance/finance-canon.sqlite",
        "sql_read_mode": "sqlite_uri_mode_ro",
        "approved_row_family": "durable_finance_canon_reference_level_compatibility_projection",
        "approved_fields": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS),
        "row_keys": [f"{ticker}:{field}" for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS if field in values],
        "values": values,
        "source_lineage": {
            "owner_source_path": values.get("reference_level_owner_source_path"),
            "source_timestamp": values.get("reference_level_source_timestamp"),
            "source_sha256": values.get("reference_level_source_sha256"),
        },
        "source_rows": source_rows,
        "missing_fields": missing_fields,
        "issues": issues,
        "notes": [
            "Reference metadata only; does not replace price_band_stop fallback values.",
            "No recommendation, deployment/action state, approval, portfolio mutation, or execution authority.",
        ],
        **ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS,
    }


def sql_membership_universe_projection(
    record: UniverseMembershipRecord,
    compatibility_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep descriptive compatibility evidence while SQL owns identity, scope, and tier."""

    projected = dict(record.raw_json)
    for key, value in (compatibility_entry or {}).items():
        projected.setdefault(key, value)
    projected.update({
        "ticker": record.ticker,
        "name": record.name,
        "instrument_type": record.instrument_type,
        "sector": record.sector,
        "industry": record.industry,
        "source_symbols": {
            "yfinance": record.yfinance_symbol,
            "sec_cik": record.sec_cik,
            "company_ir": record.company_ir,
        },
        "active": record.active,
        "universe_scope": record.universe_scope,
        "production_scope": record.production_scope_member,
        "tier": record.tier,
        "coverage_obligation_tier": record.coverage_obligation_tier,
        "monitoring_role": record.monitoring_role,
        "sql_tier": record.sql_tier,
        "sql_tier_state": record.sql_tier_state,
        "tier_decision_scope": record.tier_decision_scope,
        "review_100_monitor": record.review_100_monitor,
        "decision_grade_eligible": record.decision_grade_eligible,
        "source_open_required": record.source_open_required,
        "promotion_required_before_action": record.promotion_required_before_action,
        "identity_scope_tier_authority_source": "state/finance/finance-canon.sqlite:universe_membership",
    })
    return projected


def sql_membership_tier_projection(
    record: UniverseMembershipRecord,
    compatibility_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Overlay SQL-owned tier state without treating the legacy route packet as authority."""

    projected = dict(compatibility_entry or {})
    projected.update({
        "ticker": record.ticker,
        "name": record.name,
        "sector": record.sector,
        "instrument_type": record.instrument_type,
        "auto_tier": record.sql_tier or f"Tier {record.tier}",
        "auto_state": record.sql_tier_state,
        "tier_decision_scope": record.tier_decision_scope,
        "monitoring_role": record.monitoring_role,
        "decision_grade_eligible": record.decision_grade_eligible,
        "source_open_required": record.source_open_required,
        "promotion_required_before_action": record.promotion_required_before_action,
        "would_mutate_universe": False,
        "identity_scope_tier_authority_source": "state/finance/finance-canon.sqlite:universe_membership",
    })
    return projected


def build_card(ticker: str, inputs: dict[str, Any]) -> dict[str, Any]:
    ticker = ticker.upper()
    fundamentals = inputs["fundamental_index"].get(ticker)
    readiness = find_ticker_entry(inputs["tuesday_readiness"], ticker)
    deployment_entry = find_ticker_entry(inputs["deployment_surface"], ticker)
    analyst_entry = find_analyst_consensus_entry(inputs["analyst_consensus"], ticker)
    official_claims = index_official_claims(inputs.get("official_earnings_bridge"), ticker)
    card_fundamentals, period_alignment = build_period_aligned_fundamentals(fundamentals, official_claims)
    tech_entry = technical_record(inputs.get("technical_refresh"), ticker)
    sector_entry = sector_record(inputs.get("sector_expansion_board"), (card_fundamentals or {}).get("sector") or ticker)
    config_band = portfolio_config_band(inputs.get("portfolio_config"), ticker)
    sql_canon_membership = inputs.get("sql_canon_membership_index", {}).get(ticker)
    legacy_universe_entry = inputs.get("universe_index", {}).get(ticker)
    legacy_auto_tier_entry = inputs.get("auto_tier_index", {}).get(ticker)
    universe_entry = (
        sql_membership_universe_projection(sql_canon_membership, legacy_universe_entry)
        if isinstance(sql_canon_membership, UniverseMembershipRecord)
        else legacy_universe_entry
    )
    auto_tier_entry = (
        sql_membership_tier_projection(sql_canon_membership, legacy_auto_tier_entry)
        if isinstance(sql_canon_membership, UniverseMembershipRecord)
        else legacy_auto_tier_entry
    )
    sql_canon_state = inputs.get("sql_canon_state_index", {}).get(ticker)
    sql_canon_reference = inputs.get("sql_canon_reference_index", {}).get(ticker)
    sql_canon_reference_record = inputs.get("sql_canon_reference_record_index", {}).get(ticker)
    sql_reference_available = isinstance(sql_canon_reference, dict) and any(
        sql_canon_reference.get(key) is not None
        for key in ("reference_price_low", "reference_price_high", "reference_invalidation_level")
    )
    decision_spine_entry = inputs.get("decision_spine_index", {}).get(ticker)
    capital_queue_entry = inputs.get("capital_queue_index", {}).get(ticker)
    capital_written_band = (capital_queue_entry or {}).get("written_band")
    if not isinstance(capital_written_band, dict):
        capital_written_band = {}
    post_close_quote = post_close_quote_row(inputs, ticker)
    order_card, order_card_path = find_order_card(ticker)
    missing = build_missing_and_stale(ticker, card_fundamentals, readiness, post_close_quote, deployment_entry, analyst_entry, universe_entry, auto_tier_entry)
    if period_alignment.get("normalized_metrics_stale"):
        missing.append({
            "family": "fundamental_period_alignment",
            "severity": "context",
            "status": "newer_official_period_normalized_metrics_catch_up_required",
            "detail": f"Official period {period_alignment.get('latest_official_period_end')} is newer than normalized metrics period {period_alignment.get('normalized_metrics_period_end')}; withheld fields remain manual/10-Q required.",
        })
    instrument_type = (card_fundamentals or {}).get("instrument_type") or (fundamentals or {}).get("instrument_type")
    fresh_quote_required = effective_review_fresh_quote_required(readiness, post_close_quote)

    latest_price, latest_price_source = first_present(
        ((post_close_quote or {}).get("close"), "tmp/post-close-final-quote-ledger.json"),
        ((deployment_entry or {}).get("close"), "tmp/deployment-readiness-surface.json"),
        ((tech_entry or {}).get("close"), "tmp/technical-refresh.json"),
        ((readiness or {}).get("close_reference"), "tmp/position-sizing-readiness-current.json"),
    )
    band_low, band_low_source = first_present(
        (sql_canon_reference.get("reference_price_low") if sql_reference_available else None, "state/finance/finance-canon.sqlite:reference_levels"),
        (capital_written_band.get("entry_band_low"), "tmp/wf78-capital-review-queue.json"),
        ((decision_spine_entry or {}).get("entry_band_low"), "tmp/finance-decision-sync-spine.json"),
        (config_band.get("low"), "tmp/portfolio-config.json"),
        (((order_card or {}).get("risk_check") or {}).get("entry_band_low"), order_card_path),
        ((readiness or {}).get("band_low"), "tmp/position-sizing-readiness-current.json"),
    )
    band_high, band_high_source = first_present(
        (sql_canon_reference.get("reference_price_high") if sql_reference_available else None, "state/finance/finance-canon.sqlite:reference_levels"),
        (capital_written_band.get("entry_band_high"), "tmp/wf78-capital-review-queue.json"),
        ((decision_spine_entry or {}).get("entry_band_high"), "tmp/finance-decision-sync-spine.json"),
        (config_band.get("high"), "tmp/portfolio-config.json"),
        (((order_card or {}).get("risk_check") or {}).get("entry_band_high"), order_card_path),
        ((readiness or {}).get("band_high"), "tmp/position-sizing-readiness-current.json"),
    )
    stop, stop_source = first_present(
        (sql_canon_reference.get("reference_invalidation_level") if sql_reference_available else None, "state/finance/finance-canon.sqlite:reference_levels"),
        (capital_written_band.get("stop_or_invalidation"), "tmp/wf78-capital-review-queue.json"),
        ((capital_queue_entry or {}).get("stop_or_invalidation"), "tmp/wf78-capital-review-queue.json"),
        ((decision_spine_entry or {}).get("stop_or_invalidation"), "tmp/finance-decision-sync-spine.json"),
        (config_band.get("stop"), "tmp/portfolio-config.json"),
        (((order_card or {}).get("risk_check") or {}).get("stop"), order_card_path),
        ((readiness or {}).get("stop"), "tmp/position-sizing-readiness-current.json"),
    )
    band_status = classify_band_status(latest_price, band_low, band_high, stop) or (deployment_entry or {}).get("band_position") or (readiness or {}).get("band_status")
    stale_low_confidence_reference_band = low_confidence_reference_band_requires_refresh(
        auto_tier_entry,
        sql_canon_reference if sql_reference_available else None,
        band_status,
    )
    if stale_low_confidence_reference_band:
        band_status = STALE_REFERENCE_BAND

    price_band_stop = {
        "latest_known_price": latest_price,
        "price_source": latest_price_source,
        "entry_band_low": band_low,
        "entry_band_high": band_high,
        "stop_or_invalidation": stop,
        "band_status": band_status,
        "band_source": band_low_source if band_low_source == band_high_source else {"low": band_low_source, "high": band_high_source},
        "stop_source": stop_source,
        "fresh_quote_required": True if stale_low_confidence_reference_band else fresh_quote_required,
        "staleness_note": "Low-confidence fallback reference band requires refreshed/validated reference-band evidence before a hard stop claim; technical freshness alone does not validate it." if stale_low_confidence_reference_band else "Reference price/band from prepared packet; refresh before final use." if fresh_quote_required else None,
        "reference_band_refresh_required": stale_low_confidence_reference_band,
        "sql_canon_reference": sql_canon_reference or None,
    }
    if post_close_quote:
        price_band_stop["post_close_final_quote"] = {
            "market_date": post_close_quote.get("market_date"),
            "retrieved_at_utc": post_close_quote.get("retrieved_at_utc"),
            "source": post_close_quote.get("source"),
            "review_only": True,
            "execution_freshness_approved": False,
        }
    entry_stop_reference_metadata = build_entry_stop_reference_metadata(ticker, sql_canon_reference_record)
    recommendation = build_recommendation_posture(ticker, readiness, post_close_quote, deployment_entry, price_band_stop, order_card, missing)

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
        compact_source(SQL_CANON_DB, inputs.get("sql_canon_context")),
    ]
    if order_card_path:
        source_artifacts.append({"path": order_card_path, "exists": True, "created_at_utc": (order_card or {}).get("created_at_utc"), "status": (order_card or {}).get("status")})
    risk_register = build_risk_register(card_fundamentals, readiness, deployment_entry, missing)
    thesis_context = build_review_thesis_context(ticker, card_fundamentals, official_claims, sector_entry, price_band_stop, missing, universe_entry)
    competitive_moat = build_review_competitive_moat(card_fundamentals, official_claims, sector_entry, universe_entry, instrument_type)

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
        "durable_sql_canon_state": sql_canon_state or {
            "status": "missing_sql_canon_state",
            "source": str(SQL_CANON_DB.relative_to(WORKSPACE)),
            "note": "Durable SQL-canon state missing; card remains review-only and source-open required.",
        },
        "wf78_auto_tier_routing": auto_tier_entry or {
            "status": "missing_auto_tier_routing",
            "source": str(WF78_AUTO_TIER_ROUTING_PATH.relative_to(WORKSPACE)),
            "note": "Auto-tier routing metadata missing; legacy universe metadata remains available but promotion/deployment claims require source-open review.",
        },
        "latest_known_price": price_band_stop["latest_known_price"],
        "price_band_stop": price_band_stop,
        "entry_stop_reference_metadata": entry_stop_reference_metadata,
        "thesis_bull_bear_entry_context": thesis_context,
        "latest_earnings_performance": build_latest_earnings_performance(card_fundamentals, official_claims, instrument_type),
        "key_financial_metrics": build_key_financial_metrics(card_fundamentals, instrument_type),
        "valuation": metric(card_fundamentals or {}, ["valuation_context", "market_cap", "enterprise_value", "trailing_pe", "forward_pe", "fcf_yield_pct", "earnings_yield_pct", "price_to_sales", "price_to_book", "ev_to_ebitda_proxy", "ev_to_fcf_proxy"]),
        "official_fundamentals": metric(card_fundamentals or {}, ["source", "source_tier", "period_type", "period_end", "comparison_period_end", "revenue", "revenue_yoy_pct", "net_income", "net_income_yoy_pct", "diluted_eps", "eps_yoy_pct", "gross_margin_pct", "operating_margin_pct", "net_margin_pct", "operating_cash_flow", "free_cash_flow", "free_cash_flow_yoy_pct", "fcf_per_share", "fcf_per_share_yoy_pct", "cash_and_equivalents", "total_debt", "net_debt", "debt_to_annualized_ebitda", "roic_proxy_pct", "data_quality"]),
        "fundamental_period_alignment": period_alignment,
        "fundamental_reconciliation": {
            "sec_status": ((card_fundamentals or {}).get("sec_reconciliation") or {}).get("status"),
            "sec_source_url": ((card_fundamentals or {}).get("sec_reconciliation") or {}).get("source_url"),
            "company_ir_status": ((card_fundamentals or {}).get("company_ir_reconciliation") or {}).get("status"),
            "company_ir_source_url": ((card_fundamentals or {}).get("company_ir_reconciliation") or {}).get("source_url"),
            "quality_notes": (card_fundamentals or {}).get("quality_notes") or [],
            "period_alignment": period_alignment,
        },
        "analyst_consensus_ratings_targets": analyst_entry or {
            "source_status": "unavailable",
            "as_of": None,
            "source_lineage": {},
            "cross_check_conflict": "unavailable",
        },
        "competitive_moat": competitive_moat,
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
            "sector": (card_fundamentals or {}).get("sector"),
            "sector_query": (sector_entry or {}).get("sector_query"),
            "sector_match_basis": (sector_entry or {}).get("sector_match_basis"),
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
        "etf_or_macro_proxy_profile": build_etf_profile(card_fundamentals, sector_entry),
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
            "sql_canon_legacy_tier": (sql_canon_state or {}).get("legacy_tier"),
            "sql_canon_universe_scope": (sql_canon_state or {}).get("universe_scope"),
            "sql_canon_production_answer_path_member": bool(
                (sql_canon_state or {}).get("auto_tier") == "Tier A"
                and (sql_canon_state or {}).get("auto_state") == "A-READY"
                and (sql_canon_state or {}).get("production_card_generation_allowed")
            ),
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
        "risk_register": risk_register,
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
    band_status = pbs.get("band_status") if pbs.get("reference_band_refresh_required") else classify_band_status(
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
        "fresh_quote_required": pbs.get("fresh_quote_required") if pbs.get("reference_band_refresh_required") else False if review_post_close_quote_available(row) else pbs.get("fresh_quote_required"),
        "staleness_note": pbs.get("staleness_note") if pbs.get("reference_band_refresh_required") else None if review_post_close_quote_available(row) else pbs.get("staleness_note"),
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
        "durable_sql_canon_state",
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
    for key in ["live_trade_allowed", "paper_order_execution_allowed", "owner_approval_inferred", "portfolio_mutation_allowed", "sql_canon_mutation_allowed"]:
        if authority.get(key) is not False:
            errors.append(f"authority boundary widened or missing false flag: {key}")
    if authority.get("durable_sql_canon_current_state_allowed") is not True:
        errors.append("durable SQL-canon current-state read flag must be true")
    analyst = card.get("analyst_consensus_ratings_targets") or {}
    if set(analyst) != ANALYST_PROJECTION_FIELDS:
        errors.append("analyst evidence must use the exact quarantined four-field projection")
    elif analyst.get("source_status") not in ANALYST_SOURCE_STATUSES:
        errors.append("analyst source status is outside the quarantined contract")
    elif analyst.get("cross_check_conflict") not in ANALYST_CROSS_CHECK_STATUSES:
        errors.append("analyst cross-check status must be pass, fail, stale, or unavailable")
    else:
        lineage = analyst.get("source_lineage")
        digest = lineage.get("evidence_digest_sha256") if isinstance(lineage, dict) else None
        unavailable_fallback = (
            analyst.get("source_status") == "unavailable"
            and analyst.get("as_of") is None
            and lineage == {}
            and analyst.get("cross_check_conflict") == "unavailable"
        )
        if not unavailable_fallback and (
            not isinstance(lineage, dict)
            or set(lineage) != ANALYST_LINEAGE_FIELDS
            or not all(isinstance(lineage.get(field), str) and lineage.get(field) for field in ANALYST_LINEAGE_FIELDS - {"evidence_digest_sha256"})
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in digest)
        ):
            errors.append("analyst source_lineage must use the exact quarantined lineage schema")
    if card.get("competitive_moat", {}).get("status") != "not_yet_structured_source_open_required" and not card.get("competitive_moat", {}).get("evidence"):
        errors.append("competitive moat claims require structured evidence")
    if not card.get("universe_metadata") or card.get("universe_metadata", {}).get("status") == "missing_universe_metadata":
        errors.append("universe_metadata must be present from data/finance/universe-v1.json")
    if not card.get("durable_sql_canon_state") or card.get("durable_sql_canon_state", {}).get("status") == "missing_sql_canon_state":
        errors.append("durable_sql_canon_state must be present from state/finance/finance-canon.sqlite")
    if not isinstance(card.get("risk_register"), list) or not card.get("risk_register"):
        errors.append("risk_register must be a non-empty list")
    technical_close = (card.get("technical_posture") or {}).get("latest_close")
    if technical_close is not None and card.get("latest_known_price") is None:
        errors.append("latest_known_price must fall back to technical_posture.latest_close when readiness/deployment price is absent")
    return errors


def load_sql_canon_inputs(tickers: list[str] | None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "schema": "wf77.ticker_intelligence_card.sql_canon_context.v1",
        "status": "blocked",
        "sql_canon_db": str(SQL_CANON_DB.relative_to(WORKSPACE)),
        "typed_access_layer": "scripts/finance_sql_canon_access.py",
        "production_answer_count": None,
        "missing_ticker_state": [],
        "identity_resolution": {},
        "selected_ticker_count": 0,
        "verified_reference_count": 0,
        "unavailable_reference_count": 0,
        "registry_summary": {},
        "validation": {"status": "blocked", "errors": [], "warnings": []},
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    resolved_tickers: list[str] = []
    membership_index: dict[str, UniverseMembershipRecord] = {}
    state_index: dict[str, dict[str, Any]] = {}
    reference_index: dict[str, dict[str, Any]] = {}
    reference_record_index: dict[str, ReferenceLevelRecord] = {}

    def result() -> dict[str, Any]:
        return {
            "context": context,
            "resolved_tickers": resolved_tickers,
            "membership_index": membership_index,
            "state_index": state_index,
            "reference_index": reference_index,
            "reference_record_index": reference_record_index,
        }

    try:
        client = FinanceSqlCanonAccess(SQL_CANON_DB)
        validation = client.validate()
        context["access_validation_status"] = validation.get("status")
        if validation.get("status") != "ok":
            context["validation"]["errors"].append({"sql_canon_access_blocked": validation.get("errors")})
            return result()

        if tickers is None:
            all_memberships = client.universe_memberships()
            membership_index.update({
                ticker: record
                for ticker, record in all_memberships.items()
                if record.universe_scope == ACTIVE_INTERNAL_SCOPE
            })
            resolved_tickers.extend(membership_index)
            context["identity_resolution"] = {ticker: ticker for ticker in resolved_tickers}
            context["selection_mode"] = "default_active_internal_sql_universe"
        else:
            resolution = client.resolve_tickers(tickers)
            resolved_tickers.extend(dict.fromkeys(resolution.values()))
            membership_index.update(client.universe_memberships(resolved_tickers))
            context["identity_resolution"] = resolution
            context["selection_mode"] = "explicit_or_coverage_sql_identity_resolution"

        context["selected_ticker_count"] = len(resolved_tickers)
        if not resolved_tickers:
            context["validation"]["errors"].append("sql_identity_selection_empty")
            return result()
        if set(resolved_tickers) != set(membership_index):
            missing_membership = sorted(set(resolved_tickers) - set(membership_index))
            context["validation"]["errors"].append({"missing_sql_membership": missing_membership})
            return result()

        states = client.ticker_states(resolved_tickers)
        reference_records = client.reference_level_records(resolved_tickers)
        for ticker, state in states.items():
            state_index[ticker] = asdict(state)
        for ticker, record in reference_records.items():
            if record is None:
                continue
            reference_record_index[ticker] = record
            reference_index[ticker] = reference_level_compatibility_projection(record)
        context["verified_reference_count"] = len(reference_record_index)
        context["unavailable_reference_count"] = len(resolved_tickers) - len(reference_record_index)
        missing = sorted(set(resolved_tickers) - set(states))
        production = client.production_answer_tickers()
        legacy = client.legacy_production_answer_tickers()
        context["production_answer_count"] = len(production)
        context["production_answer_definition"] = "validated proof-joined production-grade set"
        context["legacy_production_answer_count"] = len(legacy)
        context["legacy_production_answer_definition"] = "retired legacy 42 compatibility inventory"
        context["missing_ticker_state"] = missing
        context["registry_summary"] = client.migration_registry_summary()
        errors = context["validation"]["errors"]
        context["legacy_42_retired_from_blocking"] = True
        context["legacy_42_count_advisory_only"] = True
        if not production:
            context["validation"]["warnings"].append("production_grade_set_empty_wait_for_decision_grade_gates")
        if len(legacy) != LEGACY_PRODUCTION_COMPATIBILITY_COUNT:
            context["validation"]["warnings"].append({
                "legacy_42_compatibility_count": len(legacy),
                "expected": LEGACY_PRODUCTION_COMPATIBILITY_COUNT,
            })
        if missing:
            errors.append({"missing_ticker_state": missing[:25]})
        context["validation"]["status"] = "blocked" if errors else "ok"
        context["status"] = "blocked" if errors else "ok"
    except Exception as exc:  # noqa: BLE001 - card builder must fail closed on SQL-canon guard errors.
        context["validation"]["errors"].append({"exception": repr(exc)})
    return result()


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
        requested_tickers: list[str] | None = coverage_tickers
        if args.tickers:
            requested = {ticker.upper() for ticker in args.tickers}
            requested_tickers = [ticker for ticker in requested_tickers if ticker in requested]
    else:
        requested_tickers = [t.upper() for t in args.tickers] if args.tickers else None
    sql_canon_inputs = load_sql_canon_inputs(requested_tickers)
    tickers = sql_canon_inputs["resolved_tickers"]
    inputs.update({
        "sql_canon_context": sql_canon_inputs["context"],
        "sql_canon_membership_index": sql_canon_inputs["membership_index"],
        "sql_canon_state_index": sql_canon_inputs["state_index"],
        "sql_canon_reference_index": sql_canon_inputs["reference_index"],
        "sql_canon_reference_record_index": sql_canon_inputs["reference_record_index"],
    })
    out_dir = Path(args.out_dir)

    summary = {
        "schema_version": 1,
        "artifact_type": "wf77_ticker_card_registry_build_summary",
        "generated_at_utc": utc_now_iso(),
        "status": "ok",
        "mode": "all_from_coverage" if args.all_from_coverage else "explicit_or_default_tickers",
        "validate_only": bool(args.validate_only),
        "requested_ticker_count": len(requested_tickers) if requested_tickers is not None else len(tickers),
        "resolved_ticker_count": len(tickers),
        "cards": [],
        "errors": [],
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_context": sql_canon_inputs["context"],
    }
    if args.all_from_coverage and not requested_tickers:
        summary["status"] = "error"
        summary["errors"].append({"scope": "coverage_registry", "errors": ["No tickers found in tmp/finance-data-coverage-current.json ticker_coverage"]})
    if sql_canon_inputs["context"].get("status") != "ok":
        summary["status"] = "error"
        summary["errors"].append({"scope": "sql_canon_guard", "errors": [sql_canon_inputs["context"].get("validation")]})
    if summary["status"] != "ok":
        summary["card_count"] = 0
        summary["error_count"] = len(summary["errors"])
        print(json.dumps(summary, indent=2))
        return 1
    if not args.validate_only:
        out_dir.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        card = build_card(ticker, inputs)
        card = apply_approved_wf78_card_field_repair(card)
        card = apply_post_close_price_overlay(card, inputs)
        errors = validate_card(card)
        rel_path = str((out_dir / f"{ticker}.current.json").relative_to(WORKSPACE)) if out_dir.is_absolute() and out_dir.is_relative_to(WORKSPACE) else str(out_dir / f"{ticker}.current.json")
        if errors:
            summary["status"] = "error"
            summary["errors"].append({"ticker": ticker, "errors": errors})
            continue
        if not args.validate_only:
            (out_dir / f"{ticker}.current.json").write_text(json.dumps(card, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        gaps = card["missing_or_stale_evidence"]
        summary["cards"].append({
            "ticker": ticker,
            "path": rel_path,
            "recommendation_support": card["recommendation_support"]["posture"],
            "missing_or_stale_count": len(gaps),
            "blocking_gap_count": len([item for item in gaps if item.get("severity") == "blocking"]),
            "context_gap_count": len([item for item in gaps if item.get("severity") == "context"]),
            "blocking_gap_families": sorted({str(item.get("family")) for item in gaps if item.get("severity") == "blocking"}),
        })

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
