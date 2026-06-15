from __future__ import annotations

import argparse
import json
import math
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

from market_data_utils import atomic_open_for_write, atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DATA_DIR = WORKSPACE / "data" / "fundamentals"
CONFIG_PATH = TMP / "portfolio-config.json"
CURRENT_JSON_PATH = TMP / "fundamental-metrics-current.json"
CURRENT_MD_PATH = TMP / "fundamental-metrics-current.md"
BANK_NATIVE_PROBE_PATH = TMP / "bank-native-sec-concept-probe.json"
PERIOD_MAPPING_RECONCILIATION_PATH = TMP / "official-source-period-mapping-reconciliation.json"
HISTORY_PATH = DATA_DIR / "fundamentals-quarterly-v1.jsonl"
IR_METADATA_PATH = DATA_DIR / "company-ir-metadata.json"
SCHEMA_VERSION = 1
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "OpenClaw Veritas contact@example.com")
SEC_FACT_CONCEPTS = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
    "net_income": (
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLossAttributableToParent",
        "NetIncomeLoss",
        "ProfitLoss",
    ),
    "diluted_eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic"),
}
SEC_FACT_UNITS = {
    "revenue": ("USD",),
    "net_income": ("USD",),
    "diluted_eps": ("USD/shares", "USD/shares"),
}
SEC_RECONCILIATION_TOLERANCE = {"revenue": 0.01, "net_income": 0.01, "diluted_eps": 0.03}
NET_INCOME_DEFINITION_CONCEPTS = (
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
    "NetIncomeLossAttributableToParent",
)

ETF_OR_MACRO_LANES = {"macro"}
ETF_OR_MACRO_ROLES = {"etf_monitor"}
ETF_TICKERS = {"SLV", "TLT", "XLI", "XLB", "XLC", "PAVE", "XLF", "XLE", "ITA", "VAW", "VXUS"}
BANK_SECTORS = {"financials"}
BANK_BROKER_TICKERS = {"GS", "JPM"}
INSURANCE_INDUSTRY_MARKERS = ("insurance",)
ASSET_MANAGER_INDUSTRY_MARKERS = ("assetmanagement", "custodybanks")
PAYMENTS_INDUSTRY_MARKERS = ("payments",)
FOREIGN_ISSUER_TICKERS = {"ASML", "SAP", "TSM"}
NEARBY_PERIOD_MATCH_WINDOW_DAYS = 35

AUTHORITY = {
    "review_packet_generation_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "notes": "Fundamental metrics are review-only evidence. Growth or quality scores must not infer deployment, sizing, sleeve, cash, risk-rule, account, brokerage, paper/live order, or trade authority.",
}

CET1_MANUAL_NOTE = "CET1 risk-based ratio not tagged as structured XBRL fact by this filer; requires manual population from earnings supplement or 10-Q capital adequacy table."
TIER1_MANUAL_NOTE = "Tier 1 risk-based ratio not tagged as structured XBRL fact by this filer; requires manual population from earnings supplement or 10-Q capital adequacy table."
TIER1_LEVERAGE_NOTE = "Tier 1 leverage ratio (Tier 1 capital / average total assets) — NOT a risk-based capital ratio; distinct from CET1 risk-based capital adequacy metric; do not compare to CET1 benchmarks."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh covered-universe fundamental metrics into review-only artifacts.")
    parser.add_argument("--tickers", nargs="*", help="Optional explicit ticker shard to refresh instead of the full covered universe.")
    parser.add_argument("--merge-existing", action="store_true", help="Merge refreshed ticker rows into the existing current artifact instead of replacing unrefreshed rows.")
    parser.add_argument("--no-history", action="store_true", help="Do not append this run to the durable JSONL history.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_key(value: Any) -> str:
    return str(value or "").lower().replace(" ", "").replace("_", "").replace("-", "")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isnan(float(value))


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except Exception:
        return None


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def abs_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return abs(float(value))


def pct(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or abs(old) < 1e-12:
        return None
    return round(((new - old) / abs(old)) * 100.0, 2)


def yfinance_symbol(ticker: str, meta: dict[str, Any]) -> str:
    raw = str(meta.get("yfinance") or ticker)
    return raw.replace(".", "-")


def financial_company_subtype(record: dict[str, Any]) -> str | None:
    ticker = str(record.get("ticker") or "").upper()
    sector = normalize_key(record.get("sector"))
    industry = normalize_key(record.get("industry"))
    if sector not in BANK_SECTORS:
        return None
    if ticker in BANK_BROKER_TICKERS:
        return "bank_broker"
    if any(marker in industry for marker in INSURANCE_INDUSTRY_MARKERS):
        return "insurer"
    if any(marker in industry for marker in ASSET_MANAGER_INDUSTRY_MARKERS):
        return "asset_manager"
    if any(marker in industry for marker in PAYMENTS_INDUSTRY_MARKERS):
        return "payments_network"
    return "financial_standard"


def is_bank_sector(record: dict[str, Any]) -> bool:
    # Bank-native FCF/CET1 handling is intentionally narrow. Broad
    # Financials includes insurers, asset managers, payments networks, and
    # brokers that should not inherit bank capital rules automatically.
    return financial_company_subtype(record) == "bank_broker"


def company_type_for_reconciliation(record: dict[str, Any]) -> str:
    sector = normalize_key(record.get("sector"))
    financial_subtype = financial_company_subtype(record)
    if financial_subtype:
        return financial_subtype
    if sector in {"financialinfrastructure", "exchanges", "capitalmarketsinfrastructure"}:
        return "exchange_operator"
    return "industrial_or_standard_operating_company"


def sec_concepts_for_metric(metric: str, record: dict[str, Any] | None = None) -> tuple[str, ...]:
    if metric != "net_income":
        return SEC_FACT_CONCEPTS.get(metric, ())
    local_rows = (record or {}).get("income_statement_source_rows") or {}
    local_label = normalize_key(local_rows.get("net_income"))
    if local_label == "netincome":
        return NET_INCOME_DEFINITION_CONCEPTS
    return SEC_FACT_CONCEPTS.get(metric, ())


def sec_comparison_policy(metric: str, record: dict[str, Any]) -> dict[str, Any]:
    local_rows = record.get("income_statement_source_rows") or {}
    local_label = local_rows.get(metric)
    if metric == "net_income":
        company_type = company_type_for_reconciliation(record)
        if company_type == "bank_broker":
            rule = "Compare yfinance headline Net Income to the same-period SEC headline net income concept; keep common-stockholder income visible separately."
        elif company_type in {"insurer", "asset_manager", "payments_network", "financial_standard"}:
            rule = "Compare yfinance headline Net Income to the same-period SEC net income concept that matches the local row; do not apply bank-native capital rules unless explicitly configured."
        elif company_type == "exchange_operator":
            rule = "Compare yfinance headline Net Income to the same-period SEC headline net income/profit-loss concept; keep common-stockholder income visible separately."
        else:
            rule = "Compare yfinance net-income row to the same-period SEC GAAP concept that matches the local row definition; unresolved mismatches stay conflicts."
        return {
            "company_type": company_type,
            "local_source": "yfinance quarterly income statement/cashflow/balance sheet",
            "local_metric_row": local_label,
            "sec_source": "SEC companyfacts us-gaap",
            "selection_rule": rule,
            "alternate_sec_concepts_are_definition_context": True,
        }
    return {
        "company_type": company_type_for_reconciliation(record),
        "local_source": "yfinance quarterly income statement/cashflow/balance sheet",
        "local_metric_row": local_label,
        "sec_source": "SEC companyfacts us-gaap",
        "selection_rule": "Compare against the preferred same-period SEC GAAP concept for this metric.",
    }


def is_etf_or_macro_proxy(ticker: str, meta: dict[str, Any]) -> bool:
    """Return true when operating-company fundamentals are not applicable."""
    lane = str(meta.get("coverage_lane") or "").lower()
    role = str(meta.get("portfolio_role") or "").lower()
    return ticker in ETF_TICKERS or lane in ETF_OR_MACRO_LANES or role in ETF_OR_MACRO_ROLES


def sec_ticker_key(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def sec_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def load_sec_ticker_map() -> dict[str, str]:
    try:
        raw = sec_get_json(SEC_COMPANY_TICKERS_URL)
    except Exception:
        return {}
    mapping: dict[str, str] = {}
    for item in raw.values():
        ticker = sec_ticker_key(str(item.get("ticker") or ""))
        cik = item.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = str(cik).zfill(10)
    return mapping


def load_ir_metadata() -> dict[str, dict[str, Any]]:
    raw = load_json_artifact(IR_METADATA_PATH)
    if not isinstance(raw, dict):
        return {}
    tickers = raw.get("tickers") or {}
    return tickers if isinstance(tickers, dict) else {}


def load_period_mapping_aliases(path: Path = PERIOD_MAPPING_RECONCILIATION_PATH) -> dict[tuple[str, str], dict[str, Any]]:
    """Load explicit review-confirmed fiscal-period aliases.

    The mapping is review-only: it allows SEC companyfacts matching against a
    company fiscal quarter-end when the workspace period bucket uses a calendar
    or fiscal-month-end convention. It does not change canon, portfolio state,
    or authority.
    """
    payload = load_json_artifact(path)
    aliases: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return aliases
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        expected = str(row.get("workspace_expected_period_end") or "")
        fiscal = str(row.get("fiscal_quarter_end_confirmed") or "")
        verdict = str(row.get("mapping_verdict") or "")
        if ticker and expected and fiscal and verdict.startswith("legitimate_"):
            aliases[(ticker, expected)] = row
    return aliases


def period_end_candidates(ticker: str, period_end: str | None, aliases: dict[tuple[str, str], dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if not period_end:
        return []
    candidates = [{"period_end": period_end, "mapping_source": "workspace_period", "mapped_from": None, "mapping_verdict": None}]
    alias = (aliases or {}).get((str(ticker or "").upper(), str(period_end)))
    fiscal = str((alias or {}).get("fiscal_quarter_end_confirmed") or "")
    if fiscal and fiscal != period_end:
        candidates.append({
            "period_end": fiscal,
            "mapping_source": "review_confirmed_period_alias",
            "mapped_from": period_end,
            "mapping_verdict": alias.get("mapping_verdict"),
            "mapping_rationale": alias.get("mapping_rationale"),
        })
    return candidates


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def sec_discrete_quarter_entry(item: dict[str, Any], period_type: str | None) -> bool:
    if item.get("form") not in {"10-Q", "10-K", "20-F", "40-F"}:
        return False
    if period_type != "quarterly":
        return True
    frame = str(item.get("frame") or "")
    return bool(frame and "Q" in frame and "I" not in frame)


def sec_metric_entries(
    companyfacts: dict[str, Any],
    metric: str,
    period_type: str | None,
    record: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    facts = ((companyfacts.get("facts") or {}).get("us-gaap") or {}) if isinstance(companyfacts, dict) else {}
    entries_out: list[dict[str, Any]] = []
    for concept in sec_concepts_for_metric(metric, record):
        concept_facts = facts.get(concept) or {}
        units = concept_facts.get("units") or {}
        for unit in SEC_FACT_UNITS.get(metric, ("USD",)):
            entries = units.get(unit) or []
            if not isinstance(entries, list):
                continue
            for item in entries:
                if item.get("val") is None or not sec_discrete_quarter_entry(item, period_type):
                    continue
                entries_out.append({
                    "concept": concept,
                    "unit": unit,
                    "value": round_or_none(safe_float(item.get("val")), 4 if metric == "diluted_eps" else 2),
                    "period_end": item.get("end"),
                    "filed": item.get("filed"),
                    "form": item.get("form"),
                    "frame": item.get("frame"),
                })
    entries_out.sort(key=lambda item: (str(item.get("filed") or ""), str(item.get("period_end") or "")), reverse=True)
    return entries_out


def nearby_period_sec_fact(
    companyfacts: dict[str, Any],
    metric: str,
    period_end: str | None,
    period_type: str | None,
    local_value: Any,
    record: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    target = parse_date(period_end)
    local_number = safe_float(local_value)
    tolerance = SEC_RECONCILIATION_TOLERANCE.get(metric)
    if target is None or local_number is None or tolerance is None:
        return None
    candidates: list[dict[str, Any]] = []
    for fact in sec_metric_entries(companyfacts, metric, period_type, record):
        fact_end = parse_date(fact.get("period_end"))
        fact_value = safe_float(fact.get("value"))
        if fact_end is None or fact_value is None or fact_end == target:
            continue
        day_delta = abs((fact_end - target).days)
        if day_delta > NEARBY_PERIOD_MATCH_WINDOW_DAYS:
            continue
        diff = abs(fact_value - local_number) / max(abs(local_number), 1.0)
        if diff <= tolerance:
            item = dict(fact)
            item["period_mapping"] = {
                "source": "auto_detected_nearby_fiscal_period",
                "workspace_period_end": period_end,
                "sec_period_end_used": fact.get("period_end"),
                "mapping_verdict": "candidate_legitimate_fiscal_calendar_mismatch",
                "mapping_rationale": f"SEC fact matched local {metric} within tolerance at nearby fiscal period-end {fact.get('period_end')}.",
                "review_only": True,
            }
            item["nearby_period_day_delta"] = day_delta
            candidates.append(item)
    if not candidates:
        return None
    if metric == "net_income":
        return choose_sec_fact(metric, candidates, local_value, record)
    candidates.sort(key=lambda item: (item.get("nearby_period_day_delta") or 999, str(item.get("filed") or "")))
    return candidates[0]


def classify_no_period_reconciliation(ticker: str, record: dict[str, Any], companyfacts: dict[str, Any], result: dict[str, Any]) -> None:
    period_end = record.get("period_end")
    period_type = record.get("period_type")
    matched = 0
    checked = 0
    mapped_periods: set[str] = set()
    for metric in ("revenue", "net_income", "diluted_eps"):
        local_value = record.get(metric)
        if local_value is None:
            continue
        checked += 1
        sec_fact = nearby_period_sec_fact(companyfacts, metric, period_end, period_type, local_value, record)
        if not sec_fact:
            continue
        matched += 1
        mapping = sec_fact.get("period_mapping") or {}
        if mapping.get("sec_period_end_used"):
            mapped_periods.add(str(mapping["sec_period_end_used"]))
        result["metrics"][metric] = {
            "local_value": local_value,
            "local_metric_row": (record.get("income_statement_source_rows") or {}).get(metric),
            "comparison_policy": sec_comparison_policy(metric, record),
            "sec_fact": sec_fact,
            "status": "matched_via_nearby_period",
            "difference_pct": 0.0,
        }
    if checked and matched == checked and len(mapped_periods) == 1:
        mapped_period = sorted(mapped_periods)[0]
        result["status"] = "matched_via_period_alias"
        result["period_mapping"] = {
            "workspace_period_end": period_end,
            "candidate_period_ends": [period_end, mapped_period],
            "mapping_source": "auto_detected_nearby_fiscal_period",
            "mapping_verdict": "candidate_legitimate_fiscal_calendar_mismatch",
            "mapping_rationale": "SEC companyfacts matched all available local core metrics at a nearby fiscal period-end; promote to explicit alias after review if repeated.",
            "review_only": True,
        }
        result["notes"].append("SEC companyfacts matched through auto-detected nearby fiscal-period mapping; review-only, no authority change.")
        return

    ticker_key = str(ticker or "").upper()
    if ticker_key in FOREIGN_ISSUER_TICKERS:
        result["status"] = "foreign_issuer_ir_required"
        result["notes"].append("Foreign issuer/ADR companyfacts did not expose a matching quarterly SEC period; use company IR or 6-K/IFRS source-open reconciliation.")
        return

    latest_period = None
    latest_filed = None
    for metric in ("revenue", "net_income", "diluted_eps"):
        for fact in sec_metric_entries(companyfacts, metric, period_type, record):
            fact_end = parse_date(fact.get("period_end"))
            if fact_end and (latest_period is None or fact_end > latest_period):
                latest_period = fact_end
                latest_filed = fact.get("filed")
    target = parse_date(period_end)
    if latest_period and target and latest_period < target:
        result["status"] = "sec_lag_wait"
        result["notes"].append(f"SEC companyfacts latest discrete period {latest_period.isoformat()} is before local period {period_end}; likely filing/companyfacts lag unless IR confirms otherwise.")
        if latest_filed:
            result["latest_sec_filed"] = latest_filed
    else:
        result["status"] = "manual_review_required"
        result["notes"].append("SEC companyfacts did not expose matching or nearby period-end facts; manual source-open period mapping required.")


def sec_fact_candidates_for_date(
    companyfacts: dict[str, Any],
    metric: str,
    period_end: str | None,
    period_type: str | None,
    record: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    facts = ((companyfacts.get("facts") or {}).get("us-gaap") or {}) if isinstance(companyfacts, dict) else {}
    matches: list[dict[str, Any]] = []
    for concept in sec_concepts_for_metric(metric, record):
        concept_facts = facts.get(concept) or {}
        units = concept_facts.get("units") or {}
        for unit in SEC_FACT_UNITS.get(metric, ("USD",)):
            entries = units.get(unit) or []
            if not isinstance(entries, list):
                continue
            candidates = [
                item for item in entries
                if item.get("val") is not None and item.get("form") in {"10-Q", "10-K", "20-F", "40-F"}
            ]
            if period_end:
                exact = [item for item in candidates if item.get("end") == period_end]
                if period_type == "quarterly":
                    # SEC companyfacts often includes year-to-date 10-Q facts with
                    # the same end date. Only compare to aggregator quarterly values
                    # when the SEC frame is a discrete quarter, not CY####Q#I YTD.
                    exact = [
                        item for item in exact
                        if item.get("frame") and "Q" in str(item.get("frame")) and "I" not in str(item.get("frame"))
                    ]
                if exact:
                    candidates = exact
                else:
                    # If yfinance reports a future/synthetic fiscal date, keep SEC data
                    # visible but do not call it a period match.
                    candidates = []
            if not candidates:
                continue
            candidates.sort(key=lambda item: (str(item.get("filed") or ""), str(item.get("end") or "")), reverse=True)
            chosen = candidates[0]
            matches.append({
                "concept": concept,
                "unit": unit,
                "value": round_or_none(safe_float(chosen.get("val")), 4 if metric == "diluted_eps" else 2),
                "period_end": chosen.get("end"),
                "filed": chosen.get("filed"),
                "form": chosen.get("form"),
                "frame": chosen.get("frame"),
            })
            break
    return matches


def choose_sec_fact(metric: str, facts: list[dict[str, Any]], local_value: Any, record: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not facts:
        return None
    local_number = safe_float(local_value)
    tolerance = SEC_RECONCILIATION_TOLERANCE.get(metric)
    if metric == "net_income" and local_number is not None and tolerance is not None:
        scored: list[tuple[float, int, dict[str, Any]]] = []
        for index, fact in enumerate(facts):
            fact_value = safe_float(fact.get("value"))
            if fact_value is None:
                continue
            diff = abs(fact_value - local_number) / max(abs(local_number), 1.0)
            scored.append((diff, index, fact))
        if scored:
            scored.sort(key=lambda item: (item[0], item[1]))
            best_diff, _, best_fact = scored[0]
            chosen = dict(best_fact)
            chosen["selection_method"] = "same_period_best_definition_match" if best_diff <= tolerance else "same_period_preferred_concept_fallback"
            chosen["alternate_sec_facts"] = [
                {key: alt.get(key) for key in ("concept", "unit", "value", "period_end", "filed", "form", "frame")}
                for alt in facts
                if alt.get("concept") != best_fact.get("concept")
            ]
            if record is not None:
                chosen["comparison_policy"] = sec_comparison_policy(metric, record)
            return chosen
    chosen = dict(facts[0])
    if record is not None:
        chosen["comparison_policy"] = sec_comparison_policy(metric, record)
    return chosen


def sec_fact_latest_for_date(
    companyfacts: dict[str, Any],
    metric: str,
    period_end: str | None,
    period_type: str | None,
    record: dict[str, Any] | None = None,
    local_value: Any = None,
) -> dict[str, Any] | None:
    facts = sec_fact_candidates_for_date(companyfacts, metric, period_end, period_type, record)
    chosen = choose_sec_fact(metric, facts, local_value, record)
    if chosen:
        return chosen
    return None


def sec_fact_latest_for_period_candidates(
    companyfacts: dict[str, Any],
    metric: str,
    candidates: list[dict[str, Any]],
    period_type: str | None,
    record: dict[str, Any] | None = None,
    local_value: Any = None,
) -> dict[str, Any] | None:
    for candidate in candidates:
        fact = sec_fact_latest_for_date(companyfacts, metric, candidate.get("period_end"), period_type, record, local_value)
        if fact:
            if candidate.get("mapping_source") != "workspace_period":
                fact["period_mapping"] = {
                    "source": candidate.get("mapping_source"),
                    "workspace_period_end": candidate.get("mapped_from"),
                    "sec_period_end_used": candidate.get("period_end"),
                    "mapping_verdict": candidate.get("mapping_verdict"),
                    "mapping_rationale": candidate.get("mapping_rationale"),
                }
            return fact
    return None


def recompute_revenue_dependent_fields(record: dict[str, Any]) -> None:
    revenue = safe_float(record.get("revenue"))
    if not revenue:
        return
    record["revenue_yoy_pct"] = pct(record.get("revenue"), record.get("revenue_prior"))
    record["gross_margin_pct"] = round_or_none((record["gross_profit"] / revenue * 100.0) if record.get("gross_profit") is not None else None)
    record["operating_margin_pct"] = round_or_none((record["operating_income"] / revenue * 100.0) if record.get("operating_income") is not None else None)
    record["net_margin_pct"] = round_or_none((record["net_income"] / revenue * 100.0) if record.get("net_income") is not None else None)
    record["sbc_pct_of_revenue"] = round_or_none((record["stock_based_compensation"] / revenue * 100.0) if record.get("stock_based_compensation") is not None else None)


def apply_sec_revenue_override(record: dict[str, Any], companyfacts: dict[str, Any], result: dict[str, Any], ticker: str, aliases: dict[tuple[str, str], dict[str, Any]]) -> None:
    """Use SEC companyfacts revenue when it period-matches and yfinance disagrees.

    This resolves real SEC-vs-aggregator conflicts without suppressing the
    validator: current and prior revenue both need SEC period matches so YoY
    and revenue-dependent percentages stay internally coherent.
    """
    period_end = record.get("period_end")
    comparison_period_end = record.get("comparison_period_end")
    current_fact = sec_fact_latest_for_period_candidates(companyfacts, "revenue", period_end_candidates(ticker, period_end, aliases), record.get("period_type"), record, record.get("revenue"))
    prior_fact = sec_fact_latest_for_period_candidates(companyfacts, "revenue", period_end_candidates(ticker, comparison_period_end, aliases), record.get("period_type"), record, record.get("revenue_prior"))
    local_current = safe_float(record.get("revenue"))
    local_prior = safe_float(record.get("revenue_prior"))
    sec_current = safe_float((current_fact or {}).get("value"))
    sec_prior = safe_float((prior_fact or {}).get("value"))
    if local_current is None or sec_current is None or sec_prior is None:
        return
    diff_pct = abs(sec_current - local_current) / max(abs(local_current), 1.0)
    if diff_pct <= SEC_RECONCILIATION_TOLERANCE["revenue"]:
        return
    record["revenue_aggregator_original"] = round_or_none(local_current)
    record["revenue_prior_aggregator_original"] = round_or_none(local_prior)
    record["revenue"] = round_or_none(sec_current)
    record["revenue_prior"] = round_or_none(sec_prior)
    record["revenue_source"] = "sec_companyfacts_period_match_override"
    record["revenue_source_url"] = result.get("source_url")
    record["revenue_source_concept"] = current_fact.get("concept") if current_fact else None
    record["revenue_source_period_end"] = period_end
    record["revenue_prior_source_concept"] = prior_fact.get("concept") if prior_fact else None
    record["revenue_prior_source_period_end"] = comparison_period_end
    record["revenue_override_note"] = "SEC companyfacts period-matched revenue replaced yfinance aggregator revenue after a material conflict; review-only, no authority change."
    record.setdefault("quality_notes", []).append("Revenue uses SEC companyfacts period-match override after yfinance aggregator conflict.")
    result["notes"].append("Revenue overridden from yfinance aggregator to SEC companyfacts period-match value before reconciliation.")
    recompute_revenue_dependent_fields(record)


def build_sec_reconciliation(ticker: str, record: dict[str, Any], sec_ticker_map: dict[str, str], period_aliases: dict[tuple[str, str], dict[str, Any]] | None = None) -> dict[str, Any]:
    ticker_key = sec_ticker_key(ticker)
    cik10 = sec_ticker_map.get(ticker_key)
    result: dict[str, Any] = {
        "source": "SEC companyfacts",
        "source_url": None,
        "cik": cik10,
        "status": "not_found",
        "metrics": {},
        "conflicts": [],
        "notes": [],
    }
    if record.get("instrument_type") != "equity":
        result["status"] = "not_applicable"
        result["notes"].append("ETF/macro proxy; SEC operating-company reconciliation not applicable.")
        return result
    if not cik10:
        result["status"] = "no_cik_mapping"
        result["notes"].append("No SEC ticker-to-CIK mapping found; likely non-U.S. filer, renamed ticker, or mapping gap.")
        return result
    url = SEC_COMPANYFACTS_URL.format(cik10=cik10)
    result["source_url"] = url
    try:
        companyfacts = sec_get_json(url)
    except urllib.error.HTTPError as exc:
        result["status"] = "sec_error"
        result["notes"].append(f"SEC HTTP error {exc.code}")
        return result
    except Exception as exc:
        result["status"] = "sec_error"
        result["notes"].append(str(exc)[:200])
        return result

    aliases = period_aliases or {}
    apply_sec_revenue_override(record, companyfacts, result, ticker, aliases)

    matched = 0
    checked = 0
    conflicts: list[str] = []
    period_end = record.get("period_end")
    candidates = period_end_candidates(ticker, period_end, aliases)
    if len(candidates) > 1:
        result["period_mapping"] = {
            "workspace_period_end": period_end,
            "candidate_period_ends": [candidate.get("period_end") for candidate in candidates],
            "mapping_source": candidates[-1].get("mapping_source"),
            "mapping_verdict": candidates[-1].get("mapping_verdict"),
            "mapping_rationale": candidates[-1].get("mapping_rationale"),
            "review_only": True,
        }
    for metric in ("revenue", "net_income", "diluted_eps"):
        local_value = record.get(metric)
        sec_fact = sec_fact_latest_for_period_candidates(companyfacts, metric, candidates, record.get("period_type"), record, local_value)
        item = {
            "local_value": local_value,
            "local_metric_row": (record.get("income_statement_source_rows") or {}).get(metric),
            "comparison_policy": sec_comparison_policy(metric, record),
            "sec_fact": sec_fact,
            "status": "missing",
        }
        if sec_fact and local_value is not None and sec_fact.get("value") is not None:
            checked += 1
            denom = max(abs(float(local_value)), 1.0)
            diff_pct = abs(float(sec_fact["value"]) - float(local_value)) / denom
            item["difference_pct"] = round(diff_pct * 100.0, 4)
            if diff_pct <= SEC_RECONCILIATION_TOLERANCE[metric]:
                item["status"] = "matched"
                matched += 1
            else:
                item["status"] = "conflict"
                conflicts.append(metric)
        elif sec_fact:
            item["status"] = "sec_available_local_missing"
        elif local_value is not None:
            item["status"] = "local_available_sec_missing"
        result["metrics"][metric] = item

    result["conflicts"] = conflicts
    if conflicts:
        result["status"] = "conflict"
    elif checked and matched == checked:
        result["status"] = "matched"
        if result.get("period_mapping"):
            result["notes"].append("SEC companyfacts matched through review-confirmed fiscal-period mapping; review-only period alias, no authority change.")
    elif checked:
        result["status"] = "partial"
    else:
        classify_no_period_reconciliation(ticker, record, companyfacts, result)
    return result


def compare_official_ir_fundamentals(config: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    metrics = config.get("metrics") or {}
    metric_results: dict[str, Any] = {}
    conflicts: list[str] = []
    matched = 0
    checked = 0
    for metric in ("revenue", "net_income", "diluted_eps"):
        official = metrics.get(metric) or {}
        if not isinstance(official, dict):
            continue
        official_value = safe_float(official.get("normalized_value"))
        local_value = safe_float(record.get(metric))
        tolerance = safe_float(official.get("tolerance_pct"))
        if tolerance is None:
            tolerance = SEC_RECONCILIATION_TOLERANCE.get(metric, 0.01) * 100.0
        status = "missing"
        difference_pct = None
        if official_value is not None and local_value is not None:
            checked += 1
            denom = max(abs(local_value), 1.0)
            difference_pct = round(abs(official_value - local_value) / denom * 100.0, 4)
            if difference_pct <= tolerance:
                status = "matched"
                matched += 1
            else:
                status = "conflict"
                conflicts.append(metric)
        elif official_value is not None:
            status = "official_available_local_missing"
        elif local_value is not None:
            status = "local_available_official_missing"
        metric_results[metric] = {
            "local_value": local_value,
            "official_value": official_value,
            "official_label": official.get("official_label"),
            "official_basis": official.get("basis"),
            "unit": official.get("unit"),
            "status": status,
            "difference_pct": difference_pct,
            "tolerance_pct": tolerance,
            "note": official.get("note"),
        }
    if conflicts:
        status = "conflict_local_repair_required"
    elif checked and matched == checked:
        status = "matched"
    elif checked:
        status = "partial"
    else:
        status = "manual_required"
    return {
        "status": status,
        "source_type": "official_company_ir_fundamentals",
        "source_url": config.get("source_url"),
        "source_label": config.get("source_label"),
        "period_label": config.get("period_label"),
        "official_period_end": config.get("official_period_end"),
        "workspace_expected_period_end": config.get("workspace_expected_period_end"),
        "accounting_basis": config.get("accounting_basis"),
        "currency": config.get("currency"),
        "metrics": metric_results,
        "matched_count": matched,
        "checked_count": checked,
        "conflicts": conflicts,
        "notes": config.get("notes") or [],
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_action_allowed": False,
            "capital_action_allowed": False,
        },
    }


def apply_official_ir_metric_repairs(record: dict[str, Any], ticker: str, ir_metadata: dict[str, dict[str, Any]] | None) -> None:
    """Apply explicit review-only official-IR repairs for known aggregator conflicts."""
    ir_meta = (ir_metadata or {}).get(str(ticker or "").upper()) or {}
    config = ir_meta.get("official_fundamental_reconciliation") or {}
    if not isinstance(config, dict):
        return
    if str(config.get("workspace_expected_period_end") or "") != str(record.get("period_end") or ""):
        return
    metrics = config.get("metrics") or {}
    if not isinstance(metrics, dict):
        return
    repairs: list[dict[str, Any]] = []
    for metric, official in metrics.items():
        if not isinstance(official, dict):
            continue
        action = str(official.get("local_repair_action") or "")
        if action != "override_with_official_ir_value":
            continue
        official_value = safe_float(official.get("normalized_value"))
        prior_value = record.get(metric)
        if official_value is None:
            continue
        record[metric] = round_or_none(official_value, 4 if metric.endswith("eps") else 2)
        repairs.append({
            "metric": metric,
            "action": action,
            "prior_local_value": prior_value,
            "official_value": record[metric],
            "official_label": official.get("official_label"),
            "official_basis": official.get("basis"),
            "source_url": config.get("source_url"),
            "period_label": config.get("period_label"),
            "review_only": True,
            "note": official.get("note"),
        })
    if not repairs:
        return
    record["official_ir_metric_repairs"] = repairs
    record["source_tier"] = "aggregator_secondary_with_official_ir_repair"
    record.setdefault("quality_notes", []).append(
        "One or more local aggregator metric values were replaced with explicit official company IR values because the aggregator row conflicted with official period evidence."
    )


def build_company_ir_reconciliation(meta: dict[str, Any], ticker: str | None = None, ir_metadata: dict[str, dict[str, Any]] | None = None, record: dict[str, Any] | None = None) -> dict[str, Any]:
    ir_meta = (ir_metadata or {}).get(str(ticker or "")) or {}
    ir_url = meta.get("company_ir_url") or meta.get("ir_url") or meta.get("investor_relations_url") or ir_meta.get("ir_home_url")
    earnings_url = ir_meta.get("earnings_url")
    guidance_url = ir_meta.get("guidance_url")
    result = {
        "source": "company IR",
        "source_url": ir_url,
        "earnings_url": earnings_url,
        "guidance_url": guidance_url,
        "status": "manual_required" if not ir_url else "configured_manual_review_required",
        "notes": [
            "Official adjusted EPS, guidance, and management commentary require company IR earnings-release reconciliation; V1.1 records the gate but does not scrape or overwrite adjusted metrics."
        ],
    }
    official_reconciliation = ir_meta.get("official_fundamental_reconciliation")
    if isinstance(official_reconciliation, dict) and record is not None:
        official_result = compare_official_ir_fundamentals(official_reconciliation, record)
        result["official_fundamental_reconciliation"] = official_result
        result["status"] = official_result["status"]
        result["notes"] = [
            "Official company IR fundamental reconciliation was compared against local aggregator values; review-only and no authority change."
        ] + list(official_result.get("notes") or [])
    return result


def load_bank_native_probe() -> dict[str, Any]:
    if not BANK_NATIVE_PROBE_PATH.exists():
        return {}
    data = load_json_artifact(BANK_NATIVE_PROBE_PATH)
    return data if isinstance(data, dict) else {}


def concept_value(concepts: dict[str, Any], field: str) -> Any:
    concept = concepts.get(field) or {}
    if concept.get("status") not in {"found", "found_needs_review"}:
        return None
    return concept.get("value_normalized")


def concept_trust(concepts: dict[str, Any], field: str) -> str | None:
    concept = concepts.get(field) or {}
    return concept.get("trust_level") if concept else None


def concept_source(concepts: dict[str, Any], field: str) -> str | None:
    concept = concepts.get(field) or {}
    return concept.get("resolved_concept") if concept else None


def _official_ratio_value(config: dict[str, Any], key: str) -> float | None:
    ratio = config.get(key) or {}
    if not isinstance(ratio, dict):
        return None
    return round_or_none(safe_float(ratio.get("primary")), 4)


def _official_ratio_framework_value(config: dict[str, Any], key: str, framework: str) -> float | None:
    ratio = config.get(key) or {}
    if not isinstance(ratio, dict):
        return None
    return round_or_none(safe_float(ratio.get(framework)), 4)


def apply_official_bank_capital(row: dict[str, Any], bank_meta: dict[str, Any]) -> None:
    capital = bank_meta.get("bank_native_capital") or {}
    if not isinstance(capital, dict):
        return
    trust = str(capital.get("trust") or "")
    source_url = capital.get("source_url")
    no_derived = capital.get("no_derived_ratio") is True
    if trust != "manual_confirmed" or not source_url or not no_derived:
        row.setdefault("quality_notes", []).append("Bank-native official capital metadata is incomplete; CET1/Tier1 risk-based ratios remain manual-required.")
        return

    source = capital.get("source") or "official_sec_filing"
    period = capital.get("period")
    section = capital.get("source_section")
    primary_framework = capital.get("primary_framework")
    note = capital.get("note") or "Official risk-based capital ratios manually captured from bank filing/supplement; values are not derived from capital/RWA or leverage ratios."
    row.update({
        "bank_native_status": "partial",
        "bank_native_ir_status": "manual_confirmed",
        "bank_native_note": f"WF65 V1.5 official bank-capital supplement: SEC companyfacts resolves several bank-native fields, while CET1 and Tier 1 risk-based ratios are manual-confirmed from official bank filing/supplement metadata for {period or 'the reported bank-capital period'}; ratios are not derived from capital/RWA or leverage metrics.",
        "bank_native_official_source": source,
        "bank_native_official_source_url": source_url,
        "bank_native_official_period": period,
        "bank_native_official_source_section": section,
        "bank_native_manual_confirmed_count": 2,
        "risk_based_capital_period": period,
        "risk_based_capital_source": source,
        "risk_based_capital_source_url": source_url,
        "risk_based_capital_source_section": section,
        "risk_based_capital_trust": trust,
        "risk_based_capital_no_derived_ratio": True,
        "risk_based_capital_primary_framework": primary_framework,
        "risk_based_capital_note": note,
        "cet1_ratio": _official_ratio_value(capital, "cet1_ratio"),
        "cet1_ratio_standardized": _official_ratio_framework_value(capital, "cet1_ratio", "standardized"),
        "cet1_ratio_advanced": _official_ratio_framework_value(capital, "cet1_ratio", "advanced"),
        "cet1_ratio_basis": (capital.get("cet1_ratio") or {}).get("primary_basis"),
        "cet1_ratio_source": source,
        "cet1_ratio_source_url": source_url,
        "cet1_ratio_source_section": section,
        "cet1_ratio_period": period,
        "cet1_ratio_trust": trust,
        "cet1_ratio_note": note,
        "tier1_ratio": _official_ratio_value(capital, "tier1_ratio"),
        "tier1_ratio_standardized": _official_ratio_framework_value(capital, "tier1_ratio", "standardized"),
        "tier1_ratio_advanced": _official_ratio_framework_value(capital, "tier1_ratio", "advanced"),
        "tier1_ratio_basis": (capital.get("tier1_ratio") or {}).get("primary_basis"),
        "tier1_ratio_source": source,
        "tier1_ratio_source_url": source_url,
        "tier1_ratio_source_section": section,
        "tier1_ratio_period": period,
        "tier1_ratio_trust": trust,
        "tier1_ratio_note": note,
        "cet1_capital_official": round_or_none(safe_float(capital.get("cet1_capital"))),
        "tier1_capital_official": round_or_none(safe_float(capital.get("tier1_capital"))),
        "risk_weighted_assets_standardized": round_or_none(safe_float(capital.get("risk_weighted_assets_standardized"))),
        "risk_weighted_assets_advanced": round_or_none(safe_float(capital.get("risk_weighted_assets_advanced"))),
    })
    confirmed = int(row.get("bank_native_manual_confirmed_count") or 0)
    existing_manual_required = int(row.get("bank_native_manual_required_count") or 0)
    row["bank_native_manual_required_count"] = max(0, existing_manual_required - confirmed)


def apply_official_bank_tbv(row: dict[str, Any], bank_meta: dict[str, Any]) -> None:
    tbv = bank_meta.get("bank_native_tbv") or {}
    if not isinstance(tbv, dict) or tbv.get("trust") != "manual_confirmed" or not tbv.get("source_url"):
        return
    tbv_per_share = safe_float(tbv.get("tbv_per_share"))
    if tbv_per_share is None:
        return
    row.update({
        "tbv_per_share": round_or_none(tbv_per_share, 4),
        "tbv_per_share_trust": "manual_confirmed",
        "tbv_per_share_source": tbv.get("source") or "official_sec_filing",
        "tbv_per_share_source_url": tbv.get("source_url"),
        "tbv_per_share_source_section": tbv.get("source_section"),
        "tbv_per_share_period": tbv.get("period"),
        "tbv_per_share_note": tbv.get("note") or "Official company TBV/share reconciliation overrides SEC companyfacts proxy components for this bank row.",
        "tangible_common_equity_official": round_or_none(safe_float(tbv.get("tangible_common_equity"))),
        "common_stockholders_equity_official": round_or_none(safe_float(tbv.get("common_stockholders_equity"))),
        "other_intangible_assets_official": round_or_none(safe_float(tbv.get("other_intangible_assets"))),
        "deferred_tax_liabilities_tce_addback": round_or_none(safe_float(tbv.get("deferred_tax_liabilities_addback"))),
    })
    if tbv.get("other_intangible_assets") is not None:
        row["intangible_assets"] = round_or_none(safe_float(tbv.get("other_intangible_assets")))
        row["intangible_assets_trust"] = "manual_confirmed"
        row["intangible_assets_source"] = tbv.get("source") or "official_sec_filing"
    market_cap = safe_float(row.get("market_cap"))
    shares = safe_float(row.get("diluted_average_shares"))
    if market_cap is not None and shares and tbv_per_share > 0:
        implied_price = market_cap / shares
        row["price_to_tbv"] = round_or_none(implied_price / tbv_per_share, 4)
        row["price_to_tbv_trust"] = "official_tbv_market_cap_proxy"
        row["price_to_tbv_note"] = "Uses official TBV/share with yfinance market-cap/diluted-share proxy; review-only, not an execution trigger."


def apply_bank_native_v15_partial(row: dict[str, Any], bank_probe: dict[str, Any], ir_metadata: dict[str, dict[str, Any]] | None = None) -> None:
    if not is_bank_sector(row):
        return
    row.update({
        "wf65_bank_native_version": "v1_5_partial",
        "bank_native_status": "partial",
        "bank_native_sec_status": "manual_required",
        "bank_native_ir_status": "manual_required",
        "bank_native_note": "WF65 V1.5 partial: SEC companyfacts resolves several bank-native metrics; CET1 and Tier 1 risk-based ratios require official filing/supplement confirmation before use.",
        "cet1_ratio": None,
        "cet1_ratio_source": "not_available_sec_xbrl",
        "cet1_ratio_trust": "manual_required",
        "cet1_ratio_note": CET1_MANUAL_NOTE,
        "tier1_ratio": None,
        "tier1_ratio_source": "not_available_sec_xbrl",
        "tier1_ratio_trust": "manual_required",
        "tier1_ratio_note": TIER1_MANUAL_NOTE,
        "tier1_leverage_ratio": None,
        "tier1_leverage_ratio_source": None,
        "tier1_leverage_ratio_trust": None,
        "tier1_leverage_ratio_note": TIER1_LEVERAGE_NOTE,
        "capital_return_to_fcf_pct": None,
    })
    ticker = str(row.get("ticker") or "")
    result = ((bank_probe.get("results") or {}).get(ticker) or {}) if isinstance(bank_probe, dict) else {}
    concepts = result.get("concepts") or {}
    if not concepts:
        row["bank_native_status"] = "manual_required"
        row.setdefault("quality_notes", []).append("WF65 V1.5 bank-native probe artifact missing for this bank row; CET1/Tier1 remain manual-required unless official metadata is configured.")
    else:
        auto_fields = [name for name, concept in concepts.items() if (concept or {}).get("status") in {"found", "found_needs_review"}]
        manual_fields = [name for name, concept in concepts.items() if (concept or {}).get("status") == "manual_required"]
        row["bank_native_sec_status"] = "partial" if auto_fields else "manual_required"
        row["bank_native_auto_resolved_count"] = len(auto_fields)
        row["bank_native_manual_required_count"] = len(manual_fields)
        row["bank_native_probe_generated_at"] = bank_probe.get("generated_at_utc")
        row["bank_native_probe_summary_note"] = ((bank_probe.get("summary") or {}).get(ticker) or {}).get("summary_note")

        mapping = {
            "stockholders_equity": "stockholders_equity_sec_verified",
            "goodwill": "goodwill",
            "intangible_assets": "intangible_assets",
            "provision_for_credit_losses": "provision_for_credit_losses",
            "net_interest_income": "net_interest_income",
            "noninterest_expense": "noninterest_expense",
            "deposits": "total_deposits",
            "net_loans": "net_loans",
        }
        for source_field, target_field in mapping.items():
            value = concept_value(concepts, source_field)
            row[target_field] = round_or_none(value) if value is not None else None
            row[f"{target_field}_trust"] = concept_trust(concepts, source_field)
            row[f"{target_field}_source"] = concept_source(concepts, source_field)

        leverage = concept_value(concepts, "tier1_leverage_ratio")
        if leverage is not None:
            row["tier1_leverage_ratio"] = round_or_none(leverage, 4)
            row["tier1_leverage_ratio_source"] = concept_source(concepts, "tier1_leverage_ratio")
            row["tier1_leverage_ratio_trust"] = concept_trust(concepts, "tier1_leverage_ratio") or "auto"

        derived = result.get("derived_computations") or {}
        tbv = (derived.get("tbv_per_share_probe") or {})
        ptbv = (derived.get("price_to_tbv_probe") or {})
        row["tbv_per_share"] = tbv.get("value") if tbv.get("status") == "computed" else None
        row["tbv_per_share_trust"] = "needs_ir_crosscheck" if row.get("intangible_assets_trust") == "needs_ir_crosscheck" else ("auto" if row.get("tbv_per_share") is not None else None)
        row["price_to_tbv"] = ptbv.get("value") if ptbv.get("status") == "computed" else None
        row["price_to_tbv_trust"] = "auto" if row.get("price_to_tbv") is not None else None

    bank_meta = (ir_metadata or {}).get(ticker) or {}
    apply_official_bank_capital(row, bank_meta)
    apply_official_bank_tbv(row, bank_meta)


def pick_row(df: Any, names: list[str]) -> Any | None:
    if df is None or getattr(df, "empty", True):
        return None
    index = {normalize_key(idx): idx for idx in df.index}
    for name in names:
        key = normalize_key(name)
        if key in index:
            return index[key]
    for idx_key, original in index.items():
        for name in names:
            key = normalize_key(name)
            if key and key in idx_key:
                return original
    return None


def value_at(df: Any, row: Any | None, column: Any) -> float | None:
    if row is None or column is None:
        return None
    try:
        return safe_float(df.loc[row, column])
    except Exception:
        return None


def latest_comparable_pair(df: Any, rows: dict[str, Any], lag: int) -> tuple[Any | None, Any | None, dict[str, float | None]]:
    columns = list(df.columns) if df is not None and not getattr(df, "empty", True) else []
    best: tuple[int, Any, Any, dict[str, float | None]] | None = None
    if len(columns) <= lag:
        return None, None, {}
    for idx in range(len(columns) - lag):
        current, prior = columns[idx], columns[idx + lag]
        metrics = {
            "revenue": value_at(df, rows.get("revenue"), current),
            "revenue_prior": value_at(df, rows.get("revenue"), prior),
            "net_income": value_at(df, rows.get("net_income"), current),
            "net_income_prior": value_at(df, rows.get("net_income"), prior),
            "diluted_eps": value_at(df, rows.get("diluted_eps"), current),
            "diluted_eps_prior": value_at(df, rows.get("diluted_eps"), prior),
            "diluted_average_shares": value_at(df, rows.get("diluted_average_shares"), current),
            "diluted_average_shares_prior": value_at(df, rows.get("diluted_average_shares"), prior),
            "gross_profit": value_at(df, rows.get("gross_profit"), current),
            "operating_income": value_at(df, rows.get("operating_income"), current),
            "ebitda": value_at(df, rows.get("ebitda"), current),
        }
        core_count = sum(metrics.get(key) is not None for key in ("revenue", "revenue_prior", "net_income", "net_income_prior", "diluted_eps", "diluted_eps_prior"))
        if core_count == 0:
            continue
        candidate = (core_count, current, prior, metrics)
        if best is None or core_count > best[0]:
            best = candidate
        if core_count >= 5:
            return current, prior, metrics
    if best:
        return best[1], best[2], best[3]
    return None, None, {}


def latest_cashflow_pair(df: Any, rows: dict[str, Any], lag: int = 4) -> tuple[Any | None, Any | None, dict[str, float | None]]:
    columns = list(df.columns) if df is not None and not getattr(df, "empty", True) else []
    if not columns:
        return None, None, {}
    current = columns[0]
    prior = columns[lag] if len(columns) > lag else (columns[1] if len(columns) > 1 else None)
    metrics = {
        "operating_cash_flow": value_at(df, rows.get("operating_cash_flow"), current),
        "operating_cash_flow_prior": value_at(df, rows.get("operating_cash_flow"), prior),
        "capital_expenditure": value_at(df, rows.get("capital_expenditure"), current),
        "capital_expenditure_prior": value_at(df, rows.get("capital_expenditure"), prior),
        "free_cash_flow": value_at(df, rows.get("free_cash_flow"), current),
        "free_cash_flow_prior": value_at(df, rows.get("free_cash_flow"), prior),
        "repurchase_of_stock": value_at(df, rows.get("repurchase_of_stock"), current),
        "issuance_of_stock": value_at(df, rows.get("issuance_of_stock"), current),
        "stock_based_compensation": value_at(df, rows.get("stock_based_compensation"), current),
        "dividends_paid": value_at(df, rows.get("dividends_paid"), current),
        "debt_issuance": value_at(df, rows.get("debt_issuance"), current),
        "debt_repayment": value_at(df, rows.get("debt_repayment"), current),
    }
    return current, prior, metrics


def build_capital_allocation_anomalies(record: dict[str, Any]) -> list[dict[str, Any]]:
    if record.get("instrument_type") != "equity":
        return []
    anomalies: list[dict[str, Any]] = []
    bank = is_bank_sector(record)

    def add(code: str, severity: str, message: str) -> None:
        anomalies.append({"code": code, "severity": severity, "message": message})

    buyback = record.get("share_repurchases")
    net_buyback = record.get("net_share_repurchases")
    sbc = record.get("stock_based_compensation")
    fcf = record.get("free_cash_flow")
    fcf_ps_yoy = record.get("fcf_per_share_yoy_pct")
    eps_yoy = record.get("eps_yoy_pct")
    shares_yoy = record.get("diluted_shares_yoy_pct")
    dividends = record.get("dividends_paid")
    net_debt_issued = record.get("net_debt_issued")
    capital_return_to_fcf = record.get("capital_return_to_fcf_pct")
    debt_to_ebitda = record.get("debt_to_annualized_ebitda")
    roic = record.get("roic_proxy_pct")

    if shares_yoy is not None and shares_yoy > 3:
        add("share_count_dilution", "warning", "Diluted average shares increased materially; EPS growth needs denominator review.")
    if buyback and shares_yoy is not None and shares_yoy > 0:
        add("buybacks_with_net_dilution", "warning", "Repurchases occurred but diluted share count still increased; check SBC/issuance offset.")
    if buyback and sbc and sbc > buyback * 0.5:
        add("sbc_offsets_buybacks", "warning", "SBC consumes more than half of gross repurchases; net shareholder return quality is weaker.")
    if net_buyback is not None and net_buyback < 0:
        add("net_share_issuance", "warning", "Stock issuance exceeded repurchases in the latest cash-flow period.")
    if bank:
        add("bank_fcf_not_applicable", "info", "Bank sector: FCF/share, capital-return-to-FCF, and debt-issuance anomaly gates suppressed. Bank operating cash flow reflects loan origination, securities activity, deposit/funding flows, and balance-sheet changes, not industrial FCF. Use CET1, ROTCE/ROE, NIM, deposit growth, and credit quality for capital adequacy review.")
    else:
        if fcf is not None and fcf < 0 and (buyback or dividends):
            add("capital_returns_with_negative_fcf", "critical", "Capital returns occurred while free cash flow was negative; funding quality requires review.")
        if capital_return_to_fcf is not None and capital_return_to_fcf > 100:
            add("capital_return_exceeds_fcf", "warning", "Buybacks plus dividends exceeded free cash flow for the latest cash-flow period.")
        if net_debt_issued is not None and net_debt_issued > 0 and (buyback or dividends) and (fcf is None or fcf <= 0 or capital_return_to_fcf is None or capital_return_to_fcf > 75):
            add("debt_funded_capital_return_risk", "warning", "Net debt issuance coincided with capital returns and weak/strained FCF coverage.")
        if eps_yoy is not None and fcf_ps_yoy is not None and eps_yoy > 10 and fcf_ps_yoy < -10:
            add("eps_fcf_per_share_divergence", "warning", "EPS grew while FCF/share declined materially; earnings quality needs review.")
    if debt_to_ebitda is not None and debt_to_ebitda > 3.5:
        add("leverage_elevated", "warning", "Debt to annualized EBITDA proxy is elevated; capital returns need leverage context.")
    if roic is not None and roic < 5:
        add("low_roic_proxy", "warning", "ROIC proxy is low; reinvestment/capital-allocation quality needs review.")
    return anomalies


def capital_allocation_quality(record: dict[str, Any]) -> tuple[str, list[str]]:
    if record.get("instrument_type") != "equity":
        return "not_applicable", ["ETF/macro proxy; capital-allocation quality is not applicable."]
    if is_bank_sector(record):
        return "bank_manual_review", [
            "Bank sector: industrial FCF/debt anomaly gates suppressed. Capital adequacy review requires CET1, ROTCE/ROE, NIM/rates, deposit trends, and credit quality from 10-Q/IR before entry use."
        ]
    notes: list[str] = []
    buyback = record.get("share_repurchases")
    sbc = record.get("stock_based_compensation")
    fcf = record.get("free_cash_flow")
    shares_yoy = record.get("diluted_shares_yoy_pct")
    if buyback is None and sbc is None and shares_yoy is None and record.get("dividends_paid") is None:
        return "manual_review_required", ["Buyback/SBC/dividend/share-count fields missing from available cash-flow/income-statement data."]
    anomalies = build_capital_allocation_anomalies(record)
    notes.extend(str(item.get("message") or item.get("code")) for item in anomalies)
    if record.get("buyback_yield_pct") is not None and record.get("buyback_yield_pct") > 3:
        notes.append("High buyback yield; verify valuation discipline and source disclosure.")
    return ("caution" if notes else "tracked"), notes


def recompute_capital_allocation_classification(record: dict[str, Any]) -> None:
    ca_quality, ca_notes = capital_allocation_quality(record)
    anomalies = build_capital_allocation_anomalies(record)
    record["capital_allocation_quality"] = ca_quality
    record["capital_allocation_notes"] = ca_notes
    record["capital_allocation_anomalies"] = anomalies
    record["capital_allocation_anomaly_count"] = len(anomalies)


def classify_quality(record: dict[str, Any]) -> tuple[str, list[str]]:
    if record.get("instrument_type") != "equity":
        return "not_applicable", ["Not an operating-company equity; EPS/revenue/net income fields intentionally null."]
    notes: list[str] = []
    if record.get("fetch_error"):
        return "error", [str(record["fetch_error"])]
    core = ["revenue_yoy_pct", "net_income_yoy_pct", "eps_yoy_pct"]
    missing = [field for field in core if record.get(field) is None]
    if len(missing) == 3:
        return "missing", ["All core growth metrics missing from available income-statement data."]
    if missing:
        notes.append("Missing core metric(s): " + ", ".join(missing))
        return "partial", notes
    return "clean", notes


def load_covered_universe() -> dict[str, dict[str, Any]]:
    config = load_json_artifact(CONFIG_PATH)
    if not isinstance(config, dict):
        raise FileNotFoundError(f"Missing or invalid {CONFIG_PATH}")
    tracked = config.get("tracked_universe") or {}
    if not isinstance(tracked, dict):
        raise ValueError("tracked_universe must be an object")
    return {ticker: meta for ticker, meta in tracked.items() if isinstance(meta, dict)}


def normalize_universe_meta(row: dict[str, Any]) -> dict[str, Any]:
    source_symbols = row.get("source_symbols") if isinstance(row.get("source_symbols"), dict) else {}
    coverage_reason = row.get("coverage_reason") if isinstance(row.get("coverage_reason"), dict) else {}
    return {
        "yfinance": source_symbols.get("yfinance") or row.get("ticker"),
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "coverage_tier": row.get("tier"),
        "portfolio_role": coverage_reason.get("portfolio_role") or row.get("monitoring_role"),
        "workflow_state": row.get("monitoring_role"),
        "coverage_lane": coverage_reason.get("coverage_lane") or row.get("universe_scope"),
        "instrument_type": row.get("instrument_type"),
    }


def load_wf78_universe() -> dict[str, dict[str, Any]]:
    path = WORKSPACE / "data" / "finance" / "universe-v1.json"
    data = load_json_artifact(path)
    entries = data.get("entries") if isinstance(data, dict) else []
    out: dict[str, dict[str, Any]] = {}
    if isinstance(entries, list):
        for row in entries:
            if isinstance(row, dict) and row.get("ticker"):
                out[str(row["ticker"]).upper()] = normalize_universe_meta(row)
    return out


def load_existing_rows() -> dict[str, dict[str, Any]]:
    data = load_json_artifact(CURRENT_JSON_PATH)
    rows = data.get("rows") if isinstance(data, dict) else []
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                out[str(row["ticker"]).upper()] = row
    return out


def fetch_equity_record(ticker: str, meta: dict[str, Any], generated_at: str, ir_metadata: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    yf_symbol = yfinance_symbol(ticker, meta)
    base = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "ticker": ticker,
        "yfinance_symbol": yf_symbol,
        "name": meta.get("name"),
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "coverage_tier": meta.get("coverage_tier"),
        "portfolio_role": meta.get("portfolio_role"),
        "workflow_state": meta.get("workflow_state"),
        "coverage_lane": meta.get("coverage_lane"),
        "instrument_type": "equity",
        "source": "yfinance",
        "source_tier": "aggregator_secondary",
        "period_type": None,
        "period_end": None,
        "comparison_period_end": None,
        "revenue": None,
        "revenue_prior": None,
        "revenue_yoy_pct": None,
        "net_income": None,
        "net_income_prior": None,
        "net_income_yoy_pct": None,
        "diluted_eps": None,
        "diluted_eps_prior": None,
        "eps_yoy_pct": None,
        "gross_profit": None,
        "gross_margin_pct": None,
        "operating_income": None,
        "operating_margin_pct": None,
        "net_margin_pct": None,
        "ebitda": None,
        "operating_cash_flow": None,
        "capital_expenditure": None,
        "free_cash_flow": None,
        "free_cash_flow_prior": None,
        "free_cash_flow_yoy_pct": None,
        "fcf_interpretation": None,
        "fcf_interpretation_note": None,
        "market_cap": None,
        "enterprise_value": None,
        "trailing_pe": None,
        "forward_pe": None,
        "fcf_yield_pct": None,
        "earnings_yield_pct": None,
        "price_to_sales": None,
        "price_to_book": None,
        "ev_to_ebitda_proxy": None,
        "ev_to_fcf_proxy": None,
        "diluted_average_shares": None,
        "diluted_average_shares_prior": None,
        "diluted_shares_yoy_pct": None,
        "fcf_per_share": None,
        "fcf_per_share_prior": None,
        "fcf_per_share_yoy_pct": None,
        "fcf_per_share_yoy_base": None,
        "share_repurchases": None,
        "stock_issuance": None,
        "net_share_repurchases": None,
        "buyback_yield_pct": None,
        "stock_based_compensation": None,
        "sbc_pct_of_revenue": None,
        "sbc_pct_of_fcf": None,
        "dividends_paid": None,
        "dividend_yield_pct": None,
        "capital_return_to_fcf_pct": None,
        "debt_issued": None,
        "debt_repaid": None,
        "net_debt_issued": None,
        "shareholder_yield_pct": None,
        "shareholder_yield_period": "latest_period_market_cap_proxy",
        "total_assets": None,
        "total_equity": None,
        "net_debt": None,
        "net_debt_interpretation": None,
        "invested_capital_proxy": None,
        "roic_proxy_pct": None,
        "valuation_context": "unknown",
        "capital_allocation_anomalies": [],
        "capital_allocation_anomaly_count": 0,
        "capital_allocation_quality": "unknown",
        "capital_allocation_notes": [],
        "cash_and_equivalents": None,
        "total_debt": None,
        "debt_to_annualized_ebitda": None,
        "data_quality": "missing",
        "quality_notes": [],
        "fetch_error": None,
        "sec_reconciliation": None,
        "company_ir_reconciliation": build_company_ir_reconciliation(meta, ticker, ir_metadata),
        "authority": AUTHORITY,
    }
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        bank_sector = is_bank_sector(base)
        income_q = ticker_obj.quarterly_income_stmt
        income_rows = {
            "revenue": pick_row(income_q, ["Total Revenue", "Operating Revenue"]),
            "net_income": pick_row(income_q, ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing And Discontinued Operation"]),
            "diluted_eps": pick_row(income_q, ["Diluted EPS", "Basic EPS"]),
            "diluted_average_shares": pick_row(income_q, ["Diluted Average Shares", "Basic Average Shares", "Average Dilution Earnings", "Diluted Shares"]),
            "gross_profit": pick_row(income_q, ["Gross Profit"]),
            "operating_income": pick_row(income_q, ["Operating Income", "Total Operating Income As Reported"]),
            "ebitda": pick_row(income_q, ["EBITDA", "Normalized EBITDA"]),
        }
        base["income_statement_source_rows"] = {key: (str(value) if value is not None else None) for key, value in income_rows.items()}
        current, prior, metrics = latest_comparable_pair(income_q, income_rows, lag=4)
        period_type = "quarterly"
        if current is None:
            income_a = ticker_obj.income_stmt
            income_rows = {
                "revenue": pick_row(income_a, ["Total Revenue", "Operating Revenue"]),
                "net_income": pick_row(income_a, ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing And Discontinued Operation"]),
                "diluted_eps": pick_row(income_a, ["Diluted EPS", "Basic EPS"]),
                "diluted_average_shares": pick_row(income_a, ["Diluted Average Shares", "Basic Average Shares", "Average Dilution Earnings", "Diluted Shares"]),
                "gross_profit": pick_row(income_a, ["Gross Profit"]),
                "operating_income": pick_row(income_a, ["Operating Income", "Total Operating Income As Reported"]),
                "ebitda": pick_row(income_a, ["EBITDA", "Normalized EBITDA"]),
            }
            base["income_statement_source_rows"] = {key: (str(value) if value is not None else None) for key, value in income_rows.items()}
            current, prior, metrics = latest_comparable_pair(income_a, income_rows, lag=1)
            period_type = "annual_fallback"

        if current is not None and prior is not None:
            base["period_type"] = period_type
            base["period_end"] = current.date().isoformat()
            base["comparison_period_end"] = prior.date().isoformat()
            for key, value in metrics.items():
                base[key] = round_or_none(value, 4 if key.endswith("eps") or key.endswith("eps_prior") else 2)
            apply_official_ir_metric_repairs(base, ticker, ir_metadata)
            base["revenue_yoy_pct"] = pct(base["revenue"], base["revenue_prior"])
            base["net_income_yoy_pct"] = pct(base["net_income"], base["net_income_prior"])
            base["eps_yoy_pct"] = pct(base["diluted_eps"], base["diluted_eps_prior"])
            base["diluted_shares_yoy_pct"] = pct(base["diluted_average_shares"], base["diluted_average_shares_prior"])
            if base["revenue"]:
                base["gross_margin_pct"] = pct(base["gross_profit"], base["revenue"] - base["gross_profit"] if base["gross_profit"] is not None else None)
                # Recompute as profit / revenue, not growth pct.
                base["gross_margin_pct"] = round_or_none((base["gross_profit"] / base["revenue"] * 100.0) if base["gross_profit"] is not None else None)
                base["operating_margin_pct"] = round_or_none((base["operating_income"] / base["revenue"] * 100.0) if base["operating_income"] is not None else None)
                base["net_margin_pct"] = round_or_none((base["net_income"] / base["revenue"] * 100.0) if base["net_income"] is not None else None)

        cashflow_q = ticker_obj.quarterly_cashflow
        if cashflow_q is not None and not cashflow_q.empty:
            cashflow_rows = {
                "operating_cash_flow": pick_row(cashflow_q, ["Operating Cash Flow", "Total Cash From Operating Activities"]),
                "capital_expenditure": pick_row(cashflow_q, ["Capital Expenditure", "Capital Expenditures"]),
                "free_cash_flow": pick_row(cashflow_q, ["Free Cash Flow"]),
                "repurchase_of_stock": pick_row(cashflow_q, ["Repurchase Of Capital Stock", "Repurchase Of Stock", "Common Stock Payments", "Purchase Of Business Stock"]),
                "issuance_of_stock": pick_row(cashflow_q, ["Issuance Of Capital Stock", "Common Stock Issuance", "Sale Of Stock"]),
                "stock_based_compensation": pick_row(cashflow_q, ["Stock Based Compensation", "Share Based Compensation"]),
                "dividends_paid": pick_row(cashflow_q, ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividends Paid"]),
                "debt_issuance": pick_row(cashflow_q, ["Issuance Of Debt", "Long Term Debt Issuance", "Short Term Debt Issuance"]),
                "debt_repayment": pick_row(cashflow_q, ["Repayment Of Debt", "Long Term Debt Payments", "Short Term Debt Payments"]),
            }
            _, _, cf_metrics = latest_cashflow_pair(cashflow_q, cashflow_rows, lag=4)
            ocf = cf_metrics.get("operating_cash_flow")
            capex = cf_metrics.get("capital_expenditure")
            fcf = cf_metrics.get("free_cash_flow")
            if fcf is None and ocf is not None and capex is not None:
                fcf = ocf + capex  # capex is usually negative in yfinance cashflow.
            fcf_prior = cf_metrics.get("free_cash_flow_prior")
            if fcf_prior is None and cf_metrics.get("operating_cash_flow_prior") is not None and cf_metrics.get("capital_expenditure_prior") is not None:
                fcf_prior = cf_metrics.get("operating_cash_flow_prior") + cf_metrics.get("capital_expenditure_prior")
            base["operating_cash_flow"] = round_or_none(ocf)
            base["capital_expenditure"] = round_or_none(capex)
            base["free_cash_flow"] = round_or_none(fcf)
            base["free_cash_flow_prior"] = round_or_none(fcf_prior)
            base["free_cash_flow_yoy_pct"] = pct(base["free_cash_flow"], base["free_cash_flow_prior"])
            base["share_repurchases"] = round_or_none(abs_or_none(cf_metrics.get("repurchase_of_stock")))
            base["stock_issuance"] = round_or_none(abs_or_none(cf_metrics.get("issuance_of_stock")))
            if base["share_repurchases"] is not None or base["stock_issuance"] is not None:
                base["net_share_repurchases"] = round_or_none((base["share_repurchases"] or 0.0) - (base["stock_issuance"] or 0.0))
            base["stock_based_compensation"] = round_or_none(abs_or_none(cf_metrics.get("stock_based_compensation")))
            base["dividends_paid"] = round_or_none(abs_or_none(cf_metrics.get("dividends_paid")))
            base["debt_issued"] = round_or_none(abs_or_none(cf_metrics.get("debt_issuance")))
            base["debt_repaid"] = round_or_none(abs_or_none(cf_metrics.get("debt_repayment")))
            if base["debt_issued"] is not None or base["debt_repaid"] is not None:
                base["net_debt_issued"] = round_or_none((base["debt_issued"] or 0.0) - (base["debt_repaid"] or 0.0))
            if base.get("diluted_average_shares"):
                base["fcf_per_share"] = round_or_none(base["free_cash_flow"] / base["diluted_average_shares"], 4) if base.get("free_cash_flow") is not None else None
            if base.get("diluted_average_shares_prior"):
                base["fcf_per_share_prior"] = round_or_none(base["free_cash_flow_prior"] / base["diluted_average_shares_prior"], 4) if base.get("free_cash_flow_prior") is not None else None
            base["fcf_per_share_yoy_pct"] = pct(base["fcf_per_share"], base["fcf_per_share_prior"])
            if base.get("fcf_per_share") is not None and base.get("fcf_per_share_prior") is not None:
                if base["fcf_per_share"] < 0 and base["fcf_per_share_prior"] < 0:
                    base["fcf_per_share_yoy_base"] = "negative"
            if bank_sector:
                base["fcf_interpretation"] = "bank_structural"
                base["fcf_interpretation_note"] = "Bank operating cash flow reflects loan origination, securities activity, deposit/funding flows, and balance-sheet changes that are core business activity; standard industrial FCF/share and FCF yield are not capital-allocation gates."
            if base.get("revenue"):
                base["sbc_pct_of_revenue"] = round_or_none(base["stock_based_compensation"] / base["revenue"] * 100.0) if base.get("stock_based_compensation") is not None else None
            if base.get("free_cash_flow"):
                if bank_sector and base.get("free_cash_flow") < 0:
                    # For banks, a structurally negative FCF denominator is not an
                    # industrial FCF coverage base. Keep SBC/revenue visible, but
                    # do not publish SBC/FCF as if it were an interpretable ratio.
                    base["sbc_pct_of_fcf"] = None
                else:
                    base["sbc_pct_of_fcf"] = round_or_none(base["stock_based_compensation"] / abs(base["free_cash_flow"]) * 100.0) if base.get("stock_based_compensation") is not None else None
                capital_return = (base.get("share_repurchases") or 0.0) + (base.get("dividends_paid") or 0.0)
                base["capital_return_to_fcf_pct"] = round_or_none(capital_return / abs(base["free_cash_flow"]) * 100.0) if capital_return else None

        try:
            fast_info = getattr(ticker_obj, "fast_info", {}) or {}
            market_cap = None
            if hasattr(fast_info, "get"):
                market_cap = fast_info.get("market_cap") or fast_info.get("marketCap")
            if market_cap is None:
                market_cap = getattr(fast_info, "market_cap", None)
            info = None
            if market_cap is None:
                info = getattr(ticker_obj, "info", {}) or {}
                market_cap = info.get("marketCap") if isinstance(info, dict) else None
            if info is None:
                info = getattr(ticker_obj, "info", {}) or {}
            if isinstance(info, dict):
                base["enterprise_value"] = round_or_none(safe_float(info.get("enterpriseValue")))
                base["trailing_pe"] = round_or_none(safe_float(info.get("trailingPE")))
                base["forward_pe"] = round_or_none(safe_float(info.get("forwardPE")))
                base["price_to_sales"] = round_or_none(safe_float(info.get("priceToSalesTrailing12Months")))
                base["price_to_book"] = round_or_none(safe_float(info.get("priceToBook")))
            base["market_cap"] = round_or_none(safe_float(market_cap))
        except Exception:
            base["market_cap"] = None
        if base.get("market_cap"):
            base["buyback_yield_pct"] = round_or_none(base["share_repurchases"] / base["market_cap"] * 100.0) if base.get("share_repurchases") is not None else None
            base["dividend_yield_pct"] = round_or_none(base["dividends_paid"] / base["market_cap"] * 100.0) if base.get("dividends_paid") is not None else None
            base["fcf_yield_pct"] = round_or_none(base["free_cash_flow"] / base["market_cap"] * 100.0) if base.get("free_cash_flow") is not None else None
            base["earnings_yield_pct"] = round_or_none(base["net_income"] / base["market_cap"] * 100.0) if base.get("net_income") is not None else None
            net_payout = (base.get("net_share_repurchases") or 0.0) + (base.get("dividends_paid") or 0.0)
            base["shareholder_yield_pct"] = round_or_none(net_payout / base["market_cap"] * 100.0) if net_payout else None

        balance_q = ticker_obj.quarterly_balance_sheet
        if balance_q is not None and not balance_q.empty:
            bcol = list(balance_q.columns)[0]
            cash_row = pick_row(balance_q, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"])
            debt_row = pick_row(balance_q, ["Total Debt", "Net Debt"])
            assets_row = pick_row(balance_q, ["Total Assets"])
            equity_row = pick_row(balance_q, ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity", "Total Stockholder Equity"])
            base["cash_and_equivalents"] = round_or_none(value_at(balance_q, cash_row, bcol))
            base["total_debt"] = round_or_none(value_at(balance_q, debt_row, bcol))
            base["total_assets"] = round_or_none(value_at(balance_q, assets_row, bcol))
            base["total_equity"] = round_or_none(value_at(balance_q, equity_row, bcol))
            if base["total_debt"] is not None or base["cash_and_equivalents"] is not None:
                base["net_debt"] = round_or_none((base["total_debt"] or 0.0) - (base["cash_and_equivalents"] or 0.0))
            if bank_sector and base.get("net_debt") is not None:
                base["net_debt_interpretation"] = "bank_balance_sheet_structure"
            if base["total_debt"] is not None or base["total_equity"] is not None or base["cash_and_equivalents"] is not None:
                invested = (base["total_debt"] or 0.0) + (base["total_equity"] or 0.0) - (base["cash_and_equivalents"] or 0.0)
                base["invested_capital_proxy"] = round_or_none(invested) if invested > 0 else None
            if base["invested_capital_proxy"] and base["operating_income"] is not None:
                # Proxy only: latest-quarter operating income annualized, tax-adjusted at a conservative 21%.
                nopat_proxy = base["operating_income"] * 4.0 * 0.79
                base["roic_proxy_pct"] = round_or_none(nopat_proxy / base["invested_capital_proxy"] * 100.0)
            if base["total_debt"] is not None and base["ebitda"]:
                base["debt_to_annualized_ebitda"] = round_or_none(base["total_debt"] / (base["ebitda"] * 4.0), 2)
        if base.get("enterprise_value") and base.get("ebitda"):
            base["ev_to_ebitda_proxy"] = round_or_none(base["enterprise_value"] / (base["ebitda"] * 4.0), 2)
        if base.get("enterprise_value") and base.get("free_cash_flow"):
            base["ev_to_fcf_proxy"] = round_or_none(base["enterprise_value"] / (base["free_cash_flow"] * 4.0), 2) if base.get("free_cash_flow") > 0 else None
        valuation_signals = [base.get("trailing_pe"), base.get("forward_pe"), base.get("fcf_yield_pct"), base.get("earnings_yield_pct"), base.get("price_to_sales"), base.get("price_to_book"), base.get("ev_to_ebitda_proxy"), base.get("ev_to_fcf_proxy")]
        base["valuation_context"] = "available" if any(value is not None for value in valuation_signals) else "missing"

    except Exception as exc:
        base["fetch_error"] = str(exc)

    quality, notes = classify_quality(base)
    if base.get("official_ir_metric_repairs"):
        notes = list(notes) + [
            "Official company IR repair applied to reconcile a known aggregator metric conflict; see official_ir_metric_repairs."
        ]
    base["data_quality"] = quality
    base["quality_notes"] = notes
    recompute_capital_allocation_classification(base)
    base["company_ir_reconciliation"] = build_company_ir_reconciliation(meta, ticker, ir_metadata, base)
    return base


def not_applicable_record(ticker: str, meta: dict[str, Any], generated_at: str, ir_metadata: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    quality, notes = "not_applicable", ["ETF or macro proxy; issuer operating-company EPS/revenue/net income tracking is not applicable."]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "ticker": ticker,
        "yfinance_symbol": yfinance_symbol(ticker, meta),
        "name": meta.get("name"),
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "coverage_tier": meta.get("coverage_tier"),
        "portfolio_role": meta.get("portfolio_role"),
        "workflow_state": meta.get("workflow_state"),
        "coverage_lane": meta.get("coverage_lane"),
        "instrument_type": "etf_or_macro_proxy",
        "source": "not_applicable",
        "source_tier": "n/a",
        "period_type": None,
        "period_end": None,
        "comparison_period_end": None,
        "revenue": None,
        "revenue_prior": None,
        "revenue_yoy_pct": None,
        "net_income": None,
        "net_income_prior": None,
        "net_income_yoy_pct": None,
        "diluted_eps": None,
        "diluted_eps_prior": None,
        "eps_yoy_pct": None,
        "gross_profit": None,
        "gross_margin_pct": None,
        "operating_income": None,
        "operating_margin_pct": None,
        "net_margin_pct": None,
        "ebitda": None,
        "operating_cash_flow": None,
        "capital_expenditure": None,
        "free_cash_flow": None,
        "free_cash_flow_prior": None,
        "free_cash_flow_yoy_pct": None,
        "market_cap": None,
        "enterprise_value": None,
        "trailing_pe": None,
        "forward_pe": None,
        "price_to_sales": None,
        "price_to_book": None,
        "ev_to_ebitda_proxy": None,
        "diluted_average_shares": None,
        "diluted_average_shares_prior": None,
        "diluted_shares_yoy_pct": None,
        "fcf_per_share": None,
        "fcf_per_share_prior": None,
        "fcf_per_share_yoy_pct": None,
        "share_repurchases": None,
        "stock_issuance": None,
        "net_share_repurchases": None,
        "buyback_yield_pct": None,
        "stock_based_compensation": None,
        "sbc_pct_of_revenue": None,
        "sbc_pct_of_fcf": None,
        "dividends_paid": None,
        "dividend_yield_pct": None,
        "capital_return_to_fcf_pct": None,
        "debt_issued": None,
        "debt_repaid": None,
        "net_debt_issued": None,
        "shareholder_yield_pct": None,
        "total_assets": None,
        "total_equity": None,
        "net_debt": None,
        "invested_capital_proxy": None,
        "roic_proxy_pct": None,
        "valuation_context": "not_applicable",
        "capital_allocation_anomalies": [],
        "capital_allocation_anomaly_count": 0,
        "capital_allocation_quality": "not_applicable",
        "capital_allocation_notes": ["ETF/macro proxy; capital-allocation quality is not applicable."],
        "cash_and_equivalents": None,
        "total_debt": None,
        "debt_to_annualized_ebitda": None,
        "data_quality": quality,
        "quality_notes": notes,
        "fetch_error": None,
        "sec_reconciliation": {"source": "SEC companyfacts", "status": "not_applicable", "metrics": {}, "conflicts": [], "notes": ["ETF/macro proxy; SEC operating-company reconciliation not applicable."]},
        "company_ir_reconciliation": build_company_ir_reconciliation(meta, ticker, ir_metadata),
        "authority": AUTHORITY,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    quality_counts: dict[str, int] = {}
    sec_counts: dict[str, int] = {}
    ir_counts: dict[str, int] = {}
    capital_allocation_counts: dict[str, int] = {}
    anomaly_counts: dict[str, int] = {}
    valuation_counts: dict[str, int] = {}
    for row in rows:
        quality = str(row.get("data_quality") or "unknown")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        sec_status = str(((row.get("sec_reconciliation") or {}).get("status")) or "unknown")
        ir_status = str(((row.get("company_ir_reconciliation") or {}).get("status")) or "unknown")
        sec_counts[sec_status] = sec_counts.get(sec_status, 0) + 1
        ir_counts[ir_status] = ir_counts.get(ir_status, 0) + 1
        ca_quality = str(row.get("capital_allocation_quality") or "unknown")
        capital_allocation_counts[ca_quality] = capital_allocation_counts.get(ca_quality, 0) + 1
        valuation_context = str(row.get("valuation_context") or "unknown")
        valuation_counts[valuation_context] = valuation_counts.get(valuation_context, 0) + 1
        for anomaly in row.get("capital_allocation_anomalies") or []:
            if isinstance(anomaly, dict):
                code = str(anomaly.get("code") or "unknown")
                anomaly_counts[code] = anomaly_counts.get(code, 0) + 1
    equity_rows = [row for row in rows if row.get("instrument_type") == "equity"]
    clean_equity_rows = [row for row in equity_rows if row.get("data_quality") == "clean"]
    return {
        "covered_tickers": len(rows),
        "equity_tickers": len(equity_rows),
        "clean_equity_tickers": len(clean_equity_rows),
        "quality_counts": quality_counts,
        "sec_reconciliation_counts": sec_counts,
        "company_ir_reconciliation_counts": ir_counts,
        "capital_allocation_quality_counts": capital_allocation_counts,
        "capital_allocation_anomaly_counts": anomaly_counts,
        "valuation_context_counts": valuation_counts,
        "authority": "review_only_no_apply",
    }


def fmt_pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.1f}%"


def fmt_fcf_per_share_yoy(row: dict[str, Any]) -> str:
    if is_bank_sector(row) and row.get("fcf_interpretation"):
        if row.get("fcf_per_share_yoy_pct") is None:
            return "bank n/a"
        suffix = " neg-base" if row.get("fcf_per_share_yoy_base") == "negative" else " bank n/a"
        return f"{fmt_pct(row.get('fcf_per_share_yoy_pct'))} ({suffix.strip()})"
    return fmt_pct(row.get("fcf_per_share_yoy_pct"))


def fmt_fcf_yield(row: dict[str, Any]) -> str:
    if is_bank_sector(row) and row.get("fcf_interpretation"):
        return "bank n/a"
    return fmt_pct(row.get("fcf_yield_pct"))


def fmt_return_to_fcf(row: dict[str, Any]) -> str:
    if is_bank_sector(row) and row.get("fcf_interpretation"):
        return "bank n/a"
    return fmt_pct(row.get("capital_return_to_fcf_pct"))


def render_markdown(payload: dict[str, Any]) -> str:
    rows = payload.get("rows") or []
    lines = [
        "# Fundamental Metrics Current",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        "- Source posture: yfinance aggregator pull with SEC companyfacts period-match reconciliation where available; company IR adjusted/guidance reconciliation remains a manual gate.",
        "- Authority: no canonical-note mutation, portfolio mutation, deployment, sizing, sleeve, cash, account, brokerage, paper/live order, or trade authority.",
        "",
        "| Ticker | Quality | SEC | IR | Capital allocation | Period | EPS YoY | Shares YoY | FCF/share YoY | Buyback yield | SBC/Rev | Return/FCF | FCF yield | ROIC proxy | Anomalies | Notes |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        period = "—"
        if row.get("period_end") and row.get("comparison_period_end"):
            period = f"{row.get('period_end')} vs {row.get('comparison_period_end')}"
        notes = "; ".join(row.get("quality_notes") or [])
        lines.append(
            "| {ticker} | {quality} | {sec} | {ir} | {ca} | {period} | {eps} | {shares} | {fcfps} | {buyback} | {sbc_rev} | {rev} | {ni} | {om} | {anomalies} | {notes} |".format(
                ticker=row.get("ticker"),
                quality=row.get("data_quality"),
                sec=(row.get("sec_reconciliation") or {}).get("status") or "—",
                ir=(row.get("company_ir_reconciliation") or {}).get("status") or "—",
                ca=row.get("capital_allocation_quality") or "—",
                period=period,
                eps=fmt_pct(row.get("eps_yoy_pct")),
                shares=fmt_pct(row.get("diluted_shares_yoy_pct")),
                fcfps=fmt_fcf_per_share_yoy(row),
                buyback=fmt_pct(row.get("buyback_yield_pct")),
                sbc_rev=fmt_pct(row.get("sbc_pct_of_revenue")),
                rev=fmt_return_to_fcf(row),
                ni=fmt_fcf_yield(row),
                om=fmt_pct(row.get("roic_proxy_pct")),
                anomalies=row.get("capital_allocation_anomaly_count") or 0,
                notes=(notes or "; ".join(row.get("capital_allocation_notes") or [])).replace("|", "/"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def append_history(rows: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    if HISTORY_PATH.exists():
        existing = HISTORY_PATH.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
    additions = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    atomic_write_text(HISTORY_PATH, existing + additions)


def main() -> int:
    args = parse_args()
    generated_at = utc_now_iso()
    universe = load_covered_universe()
    universe.update({ticker: meta for ticker, meta in load_wf78_universe().items() if ticker not in universe})
    requested_tickers = {str(t).upper() for t in (args.tickers or [])}
    if requested_tickers:
        missing = sorted(requested_tickers - set(universe))
        if missing:
            raise SystemExit(f"Requested ticker(s) not found in tracked/WF78 universe: {', '.join(missing)}")
        universe = {ticker: universe[ticker] for ticker in sorted(requested_tickers)}
    sec_ticker_map = load_sec_ticker_map()
    period_aliases = load_period_mapping_aliases()
    ir_metadata = load_ir_metadata()
    bank_native_probe = load_bank_native_probe()
    rows: list[dict[str, Any]] = []
    print(f"Refreshing fundamental metrics for {len(universe)} covered tickers...")
    for ticker, meta in universe.items():
        if is_etf_or_macro_proxy(ticker, meta):
            record = not_applicable_record(ticker, meta, generated_at, ir_metadata)
            print(f"  {ticker}... n/a")
        else:
            print(f"  {ticker}...", end=" ", flush=True)
            record = fetch_equity_record(ticker, meta, generated_at, ir_metadata)
            record["sec_reconciliation"] = build_sec_reconciliation(ticker, record, sec_ticker_map, period_aliases)
            apply_bank_native_v15_partial(record, bank_native_probe, ir_metadata)
            recompute_capital_allocation_classification(record)
            print(record.get("data_quality"))
        rows.append(record)

    refreshed_rows = list(rows)
    if args.merge_existing:
        merged = load_existing_rows()
        for row in refreshed_rows:
            merged[str(row["ticker"]).upper()] = row
        rows = [merged[ticker] for ticker in sorted(merged)]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "source": "yfinance quarterly income statement/cashflow/balance sheet; SEC companyfacts reconciliation where period-match is available; annual fallback when quarterly comparable pair is unavailable",
        "source_posture": "aggregator_secondary_plus_sec_ir_capital_allocation_bank_native_review_only_v1_5_official_bank_capital_supplement",
        "history_path": str(HISTORY_PATH.relative_to(WORKSPACE)),
        "authority": AUTHORITY,
        "summary": summarize(rows),
        "rows": rows,
    }
    atomic_write_json(CURRENT_JSON_PATH, payload)
    atomic_write_text(CURRENT_MD_PATH, render_markdown(payload))
    if not args.no_history:
        append_history(refreshed_rows)
    print(f"wrote {CURRENT_JSON_PATH.relative_to(WORKSPACE)}")
    print(f"wrote {CURRENT_MD_PATH.relative_to(WORKSPACE)}")
    if not args.no_history:
        print(f"appended {HISTORY_PATH.relative_to(WORKSPACE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
