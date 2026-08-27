#!/usr/bin/env python3
"""Build a review-only Tier A issuer-specific fundamental enrichment pass.

The pass answers a narrow sourcing question for Tier A tickers:

* which fundamental fields are automated from yfinance aggregator data,
* which are available from official SEC companyfacts API concepts,
* which are available only from official filing/IR capture, and
* which still need source-open/manual issuer-specific review.

It does not mutate ticker cards, SQL canon, portfolio notes, sizing, cash,
risk rules, or execution state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

AUTO_TIER_ROUTING = TMP / "wf78-auto-tier-routing.json"
COVERAGE_GATE = TMP / "tier-a-trade-grade-coverage-gate.json"
FUNDAMENTAL_METRICS = TMP / "fundamental-metrics-current.json"
OFFICIAL_EARNINGS_BRIDGE = TMP / "official-earnings-bridge.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT_JSON = TMP / "tier-a-fundamental-enrichment-pass.json"

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "OpenClaw Veritas contact@example.com")
ETF_OR_PROXY_TYPES = {"etf", "etf_or_macro_proxy", "macro_proxy"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "report_only": True,
    "artifact_role": "tier_a_fundamental_enrichment_review_only",
    "yfinance_is_official_source": False,
    "sec_companyfacts_is_official_api": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FIELD_CATALOG = [
    {
        "field_group": "core_statement_metrics",
        "automated_sources": ["yfinance statements", "SEC companyfacts reconciliation"],
        "official_api_status": "available_for_many_us_filers",
        "notes": "Revenue, net income, EPS and cash-flow rows are broadly automatable, but yfinance is not official.",
    },
    {
        "field_group": "balance_sheet_liquidity",
        "automated_sources": ["yfinance balance sheet", "SEC companyfacts concepts"],
        "official_api_status": "available_for_many_us_filers",
        "notes": "Cash, short-term investments, debt, assets and equity are usually automatable; taxonomy names vary.",
    },
    {
        "field_group": "valuation_and_book_value",
        "automated_sources": ["yfinance quote/statistics", "derived from equity/share count when present"],
        "official_api_status": "partial_derived_not_a_single_official_api_field",
        "notes": "P/E and market cap are aggregator fields; book value can be derived but share-class structures need review.",
    },
    {
        "field_group": "buybacks_and_capital_returns",
        "automated_sources": ["yfinance cash flow", "SEC companyfacts repurchase/dividend concepts"],
        "official_api_status": "available_when_tagged",
        "notes": "Buyback dollars are often automatable; interpretation still needs context.",
    },
    {
        "field_group": "investment_purchases_sales",
        "automated_sources": ["yfinance cash flow", "SEC companyfacts investment purchase/sale concepts"],
        "official_api_status": "partial_when_tagged",
        "notes": "Useful for Berkshire-like net investment activity, but equity-only classification can require issuer review.",
    },
    {
        "field_group": "segment_earnings_or_kpis",
        "automated_sources": ["official SEC/IR capture artifacts"],
        "official_api_status": "not_universal_standard_api",
        "notes": "Segments and issuer KPIs are official but usually require filing/IR capture, not generic yfinance.",
    },
    {
        "field_group": "moat_float_holdings_succession",
        "automated_sources": ["official SEC/IR capture artifacts", "source-open filings"],
        "official_api_status": "source_open_required",
        "notes": "Insurance float, portfolio concentration, major governance events and deal specifics are not clean universal API fields.",
    },
]

SEC_CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "short_term_investments": (
        "ShortTermInvestments",
        "CashCashEquivalentsAndShortTermInvestments",
        "OtherShortTermInvestments",
    ),
    "total_assets": ("Assets",),
    "stockholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "equity_securities_fair_value": (
        "EquitySecuritiesFvNi",
        "AvailableForSaleSecuritiesEquitySecurities",
        "MarketableSecuritiesEquitySecurities",
    ),
    "equity_security_purchases": (
        "PaymentsToAcquireEquitySecuritiesFvNi",
        "PaymentsToAcquireOtherInvestments",
        "PaymentsToAcquireInvestments",
    ),
    "equity_security_sales": (
        "ProceedsFromSaleOfEquitySecuritiesFvNi",
        "ProceedsFromSaleOfOtherInvestments",
        "ProceedsFromSaleOfInvestments",
    ),
    "share_repurchases": (
        "PaymentsForRepurchaseOfCommonStock",
        "StockRepurchasedDuringPeriodValue",
    ),
    "operating_income": ("OperatingIncomeLoss",),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the enrichment artifact.")
    parser.add_argument("--validate", action="store_true", help="Run validation and return non-zero on errors.")
    parser.add_argument("--no-sec-fetch", action="store_true", help="Do not fetch SEC companyfacts; use local artifacts only.")
    parser.add_argument("--tickers", nargs="*", help="Optional ticker subset; defaults to WF78 Tier A.")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    return parser.parse_args()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


def present(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict):
        return any(present(child) for child in value.values())
    if isinstance(value, list):
        return any(present(child) for child in value)
    return True


def load_rows_by_ticker(path: Path, row_key: str = "rows") -> dict[str, dict[str, Any]]:
    payload = load_json_artifact(path)
    rows = as_list(as_dict(payload).get(row_key))
    return {
        str(row.get("ticker") or "").upper(): row
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }


def load_tier_a_rows() -> list[dict[str, Any]]:
    payload = as_dict(load_json_artifact(AUTO_TIER_ROUTING))
    rows = [
        row for row in as_list(payload.get("rows"))
        if isinstance(row, dict) and row.get("auto_tier") == "Tier A"
    ]
    return sorted(rows, key=lambda row: str(row.get("ticker") or ""))


def card_for(ticker: str) -> dict[str, Any]:
    return as_dict(load_json_artifact(CARD_DIR / f"{ticker.upper()}.current.json"))


def official_bridge_rows() -> dict[str, dict[str, Any]]:
    payload = as_dict(load_json_artifact(OFFICIAL_EARNINGS_BRIDGE))
    rows = as_list(payload.get("bridges"))
    return {
        str(row.get("ticker") or "").upper(): row
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }


def sec_ticker_key(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def sec_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read().decode("utf-8")
    parsed = json.loads(data)
    return parsed if isinstance(parsed, dict) else {}


def load_sec_ticker_map() -> dict[str, str]:
    try:
        raw = sec_get_json(SEC_COMPANY_TICKERS_URL)
    except Exception:
        return {}
    mapping: dict[str, str] = {}
    for item in raw.values():
        if not isinstance(item, dict):
            continue
        ticker = sec_ticker_key(str(item.get("ticker") or ""))
        cik = item.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = str(cik).zfill(10)
    return mapping


def latest_sec_fact(companyfacts: dict[str, Any], concepts: tuple[str, ...], period_end: str | None) -> dict[str, Any] | None:
    facts = as_dict(as_dict(companyfacts.get("facts")).get("us-gaap"))
    candidates: list[dict[str, Any]] = []
    for concept in concepts:
        concept_facts = as_dict(facts.get(concept))
        label = concept_facts.get("label")
        for unit, entries in as_dict(concept_facts.get("units")).items():
            if unit not in {"USD", "USD/shares", "shares"}:
                continue
            for entry in as_list(entries):
                if not isinstance(entry, dict) or entry.get("val") is None:
                    continue
                if entry.get("form") not in {"10-Q", "10-K", "20-F", "40-F"}:
                    continue
                exact = period_end is not None and entry.get("end") == period_end
                candidates.append({
                    "concept": concept,
                    "label": label,
                    "unit": unit,
                    "value": round_or_none(safe_float(entry.get("val")), 4 if unit == "USD/shares" else 2),
                    "period_end": entry.get("end"),
                    "filed": entry.get("filed"),
                    "form": entry.get("form"),
                    "frame": entry.get("frame"),
                    "period_match": exact,
                })
    if not candidates:
        return None
    if period_end:
        exact = [item for item in candidates if item.get("period_match")]
        if exact:
            exact.sort(key=lambda item: str(item.get("filed") or ""), reverse=True)
            return exact[0]
    candidates.sort(key=lambda item: (str(item.get("filed") or ""), str(item.get("period_end") or "")), reverse=True)
    return candidates[0]


def sec_enrichment_for_ticker(
    ticker: str,
    period_end: str | None,
    sec_ticker_map: dict[str, str],
    cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    key = sec_ticker_key(ticker)
    cik = sec_ticker_map.get(key)
    if not cik:
        return {"status": "missing_cik", "concept_groups": {}, "source": "SEC companyfacts"}
    if cik not in cache:
        try:
            cache[cik] = sec_get_json(SEC_COMPANYFACTS_URL.format(cik10=cik))
        except Exception as exc:
            cache[cik] = None
            return {"status": "fetch_failed", "error": f"{type(exc).__name__}: {exc}", "cik": cik, "concept_groups": {}}
    companyfacts = cache.get(cik)
    if not companyfacts:
        return {"status": "fetch_failed", "cik": cik, "concept_groups": {}}
    groups = {
        group: latest_sec_fact(companyfacts, concepts, period_end)
        for group, concepts in SEC_CONCEPT_GROUPS.items()
    }
    present_groups = {group: fact for group, fact in groups.items() if fact}
    return {
        "status": "available" if present_groups else "no_matching_concepts",
        "source": "SEC companyfacts official API",
        "cik": cik,
        "concept_groups": groups,
        "present_group_count": len(present_groups),
    }


def official_capture_summary(bridge_row: dict[str, Any]) -> dict[str, Any]:
    bridge = as_dict(bridge_row.get("official_earnings_bridge"))
    capture = as_dict(bridge.get("official_capture"))
    evidence = as_list(bridge.get("evidence_claims"))
    values: dict[str, Any] = {}
    for field in (
        "adjusted_eps",
        "guidance",
        "growth_bridge",
        "orders_backlog",
        "management_explanation",
        "acquisition_debt_notes",
        "segment_margins",
    ):
        value = bridge.get(field)
        if present(value):
            values[field] = value
    return {
        "status": bridge_row.get("status") or bridge.get("official_evidence_status") or "missing",
        "source_authority_level": bridge.get("source_authority_level"),
        "source_freshness": bridge.get("source_freshness"),
        "official_capture": capture,
        "captured_fields": as_list(capture.get("captured_fields")),
        "addressed_fields": as_list(capture.get("addressed_fields")),
        "unresolved_official_fields": as_list(bridge.get("unresolved_official_fields")),
        "evidence_claims": evidence,
        "captured_values": values,
        "review_only": True,
        "manual_review_required": bridge_row.get("manual_review_required") is True or bridge.get("manual_review_required") is True,
    }


def derived_book_value(row: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    pbs = as_dict(card.get("price_band_stop"))
    price = safe_float(pbs.get("latest_known_price") or card.get("latest_known_price"))
    equity = safe_float(row.get("total_equity"))
    shares = safe_float(row.get("diluted_average_shares"))
    book_per_share = equity / shares if equity and shares else None
    derived_pb = price / book_per_share if price and book_per_share else None
    return {
        "latest_known_price": round_or_none(price),
        "total_equity": round_or_none(equity),
        "diluted_average_shares": round_or_none(shares),
        "book_value_per_diluted_share": round_or_none(book_per_share, 4),
        "price_to_book_derived": round_or_none(derived_pb, 4),
        "source": "derived from local yfinance/SEC-reconciled metrics and latest review price",
        "limits": [
            "Derived book value is review-only.",
            "Dual-class, financial-sector, and treasury-share structures may require issuer-specific review.",
        ],
    }


def standardized_metrics(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "period_end",
        "comparison_period_end",
        "source",
        "source_tier",
        "data_quality",
        "revenue",
        "revenue_yoy_pct",
        "net_income",
        "net_income_yoy_pct",
        "diluted_eps",
        "eps_yoy_pct",
        "operating_cash_flow",
        "free_cash_flow",
        "free_cash_flow_yoy_pct",
        "cash_and_equivalents",
        "total_debt",
        "net_debt",
        "total_assets",
        "total_equity",
        "share_repurchases",
        "buyback_yield_pct",
        "market_cap",
        "enterprise_value",
        "trailing_pe",
        "forward_pe",
        "price_to_book",
        "price_to_sales",
    ]
    return {key: row.get(key) for key in keys if key in row}


def availability_status(*values: Any) -> str:
    if any(present(value) for value in values):
        return "available"
    return "missing"


def field_availability(row: dict[str, Any], sec: dict[str, Any], official: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sec_groups = as_dict(sec.get("concept_groups"))
    captured_values = as_dict(official.get("captured_values"))
    return {
        "core_statement_metrics": {
            "status": availability_status(row.get("revenue"), row.get("net_income"), row.get("diluted_eps")),
            "source_class": "aggregator_secondary_plus_sec_reconciliation",
            "automatic": True,
        },
        "balance_sheet_liquidity": {
            "status": availability_status(row.get("cash_and_equivalents"), row.get("total_debt"), sec_groups.get("cash_and_equivalents")),
            "source_class": "yfinance_plus_sec_companyfacts_when_tagged",
            "automatic": True,
        },
        "valuation_and_book_value": {
            "status": availability_status(row.get("trailing_pe"), row.get("forward_pe"), row.get("total_equity")),
            "source_class": "aggregator_plus_derived_review_only",
            "automatic": True,
        },
        "buybacks_and_capital_returns": {
            "status": availability_status(row.get("share_repurchases"), sec_groups.get("share_repurchases"), captured_values.get("acquisition_debt_notes")),
            "source_class": "yfinance_sec_companyfacts_or_official_capture",
            "automatic": True,
        },
        "investment_purchases_sales": {
            "status": availability_status(sec_groups.get("equity_security_purchases"), sec_groups.get("equity_security_sales")),
            "source_class": "sec_companyfacts_when_tagged_or_yfinance_cashflow_if_preserved",
            "automatic": True,
            "limits": "Equity-only versus total-investment classification may require issuer review.",
        },
        "segment_earnings_or_kpis": {
            "status": availability_status(captured_values.get("segment_margins")),
            "source_class": "official_filing_capture_not_universal_api",
            "automatic": False,
            "limits": "Requires issuer-specific official capture/extraction before decision-grade use.",
        },
        "moat_float_holdings_succession": {
            "status": "source_open_required",
            "source_class": "official_filing_or_event_capture_required",
            "automatic": False,
            "limits": "Insurance float, portfolio concentration, and governance events are not clean universal yfinance/SEC companyfacts fields.",
        },
    }


def build_row(
    tier_row: dict[str, Any],
    fundamental_rows: dict[str, dict[str, Any]],
    bridge_rows: dict[str, dict[str, Any]],
    sec_ticker_map: dict[str, str],
    sec_cache: dict[str, dict[str, Any] | None],
    fetch_sec: bool,
) -> dict[str, Any]:
    ticker = str(tier_row.get("ticker") or "").upper()
    card = card_for(ticker)
    fundamental = fundamental_rows.get(ticker, {})
    official = official_capture_summary(bridge_rows.get(ticker, {}))
    instrument_type = str(tier_row.get("instrument_type") or as_dict(card.get("universe_metadata")).get("instrument_type") or "").lower()
    sec = (
        {"status": "not_applicable", "concept_groups": {}, "source": "SEC companyfacts"}
        if instrument_type in ETF_OR_PROXY_TYPES
        else sec_enrichment_for_ticker(ticker, fundamental.get("period_end"), sec_ticker_map, sec_cache)
        if fetch_sec else {"status": "skipped", "concept_groups": {}, "source": "SEC companyfacts"}
    )
    derived_book = derived_book_value(fundamental, card)
    availability = field_availability(fundamental, sec, official)
    api_available = sum(1 for item in availability.values() if item.get("automatic") and item.get("status") == "available")
    official_capture_groups = sum(1 for item in availability.values() if item.get("source_class") == "official_filing_capture_not_universal_api" and item.get("status") == "available")
    manual_required = sum(1 for item in availability.values() if not item.get("automatic") and item.get("status") != "available")
    return {
        "ticker": ticker,
        "name": tier_row.get("name") or as_dict(card.get("universe_metadata")).get("name"),
        "auto_tier": tier_row.get("auto_tier"),
        "auto_state": tier_row.get("auto_state"),
        "instrument_type": instrument_type or None,
        "fundamental_pass_applicable": instrument_type not in ETF_OR_PROXY_TYPES,
        "standardized_metrics": standardized_metrics(fundamental),
        "derived_book_value": derived_book,
        "sec_companyfacts_enrichment": sec,
        "official_capture_summary": official,
        "field_availability": availability,
        "summary": {
            "api_automatic_available_groups": api_available,
            "official_capture_available_groups": official_capture_groups,
            "manual_or_source_open_required_groups": manual_required,
            "yfinance_is_official_source": False,
            "decision_grade_claim_allowed": False,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_payload(tickers: list[str] | None = None, *, fetch_sec: bool = True) -> dict[str, Any]:
    tier_rows = load_tier_a_rows()
    if tickers:
        requested = {ticker.upper() for ticker in tickers}
        tier_rows = [row for row in tier_rows if str(row.get("ticker") or "").upper() in requested]
    fundamental_rows = load_rows_by_ticker(FUNDAMENTAL_METRICS)
    bridge_rows = official_bridge_rows()
    sec_ticker_map = load_sec_ticker_map() if fetch_sec else {}
    sec_cache: dict[str, dict[str, Any] | None] = {}
    rows = [
        build_row(row, fundamental_rows, bridge_rows, sec_ticker_map, sec_cache, fetch_sec)
        for row in tier_rows
    ]
    yfinance_rows = sum(1 for row in rows if as_dict(row.get("standardized_metrics")).get("source") == "yfinance")
    sec_rows = sum(1 for row in rows if as_dict(row.get("sec_companyfacts_enrichment")).get("status") == "available")
    official_capture_rows = sum(1 for row in rows if as_list(as_dict(row.get("official_capture_summary")).get("captured_fields")))
    return {
        "schema": "veritas.tier_a_fundamental_enrichment_pass.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only Tier A fundamental enrichment and source-automation availability map.",
        "source_artifacts": {
            "auto_tier_routing": rel(AUTO_TIER_ROUTING),
            "coverage_gate": rel(COVERAGE_GATE),
            "fundamental_metrics": rel(FUNDAMENTAL_METRICS),
            "official_earnings_bridge": rel(OFFICIAL_EARNINGS_BRIDGE),
            "ticker_cards": rel(CARD_DIR),
        },
        "sourcing_matrix": FIELD_CATALOG,
        "summary": {
            "tier_a_rows": len(rows),
            "operating_company_rows": sum(1 for row in rows if row.get("fundamental_pass_applicable")),
            "etf_or_proxy_rows": sum(1 for row in rows if not row.get("fundamental_pass_applicable")),
            "yfinance_aggregator_rows": yfinance_rows,
            "sec_companyfacts_available_rows": sec_rows,
            "official_capture_rows": official_capture_rows,
            "sec_fetch_enabled": fetch_sec,
            "decision_grade_allowed_count": 0,
        },
        "rows": rows,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "yfinance is an automated aggregator source, not an official source.",
            "SEC companyfacts is official API data but does not cover every issuer-specific KPI.",
            "Official filing/IR capture remains review-only and does not imply capital, execution, or owner approval.",
        ],
    }


def validate_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None, severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "detail": detail})

    boundary = as_dict(payload.get("authority_boundary"))
    rows = as_list(payload.get("rows"))
    add("rows_present", bool(rows), len(rows))
    add("yfinance_not_official", boundary.get("yfinance_is_official_source") is False, boundary)
    add("sec_companyfacts_official_api", boundary.get("sec_companyfacts_is_official_api") is True, boundary)
    for flag in (
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "ticker_card_mutation_allowed",
        "sql_canon_mutation_allowed",
        "capital_deployment_allowed",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        add(f"authority_{flag}_false", boundary.get(flag) is False, boundary)
    bad_rows = [
        row.get("ticker")
        for row in rows
        if as_dict(row).get("summary", {}).get("yfinance_is_official_source") is not False
        or as_dict(row).get("summary", {}).get("decision_grade_claim_allowed") is not False
    ]
    add("row_boundaries_preserved", not bad_rows, bad_rows)
    return checks


def main() -> int:
    args = parse_args()
    payload = build_payload(args.tickers, fetch_sec=not args.no_sec_fetch)
    checks = validate_payload(payload) if args.validate else []
    errors = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    payload["validation"] = {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "checks": checks,
    }
    if errors:
        payload["status"] = "blocked"
    if args.write:
        atomic_write_json(args.out, payload)
    print(json.dumps({
        "status": payload["status"],
        "out": rel(args.out),
        "summary": payload["summary"],
        "validation": payload["validation"],
    }, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
