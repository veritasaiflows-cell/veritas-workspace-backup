from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from official_ir_capture_common import (
    AUTHORITY as COMMON_AUTHORITY,
    build_capture_document,
    claim as common_claim,
    compact,
    run_capture_batch,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "official-ir-captures"
AUTHORITY = COMMON_AUTHORITY

SOURCES: dict[str, dict[str, str]] = {
    "AMD": {
        "company_name": "Advanced Micro Devices, Inc.",
        "period_end": "2026-03-28",
        "source_url": "https://www.sec.gov/Archives/edgar/data/2488/000000248826000072/q12026991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/2488/000000248826000072/0000002488-26-000072-index.htm",
        "accession_number": "0000002488-26-000072",
        "source_title": "AMD Reports First Quarter 2026 Financial Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "CAT": {
        "company_name": "Caterpillar Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/18230/000001823026000017/ex991toformcat1q2026earnin.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/18230/000001823026000017/0000018230-26-000017-index.htm",
        "accession_number": "0000018230-26-000017",
        "source_title": "Caterpillar Reports First-Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "CVX": {
        "company_name": "Chevron Corporation",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/93410/000009341026000110/a03312026ex9918-k.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/93410/000009341026000110/0000093410-26-000110-index.htm",
        "accession_number": "0000093410-26-000110",
        "source_title": "Chevron Reports First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "PLTR": {
        "company_name": "Palantir Technologies Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1321655/000132165526000026/a2026q1ex991pressrelease.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1321655/000132165526000026/0001321655-26-000026-index.htm",
        "accession_number": "0001321655-26-000026",
        "source_title": "Palantir Reports Q1 2026 U.S. Revenue Growth of 104% Y/Y and Revenue Growth of 85% Y/Y",
        "source_type": "sec_8k_exhibit_99_1",
    },
}


def excerpt_around(text: str, needle: str, chars: int = 1000) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - chars // 3)
    end = min(len(text), idx + chars)
    return compact(text[start:end])


def first_excerpt(text: str, *needles: str, chars: int = 1000) -> str:
    for needle in needles:
        found = excerpt_around(text, needle, chars=chars)
        if found:
            return found
    return ""


def claim(source_url: str, status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return common_claim(source_url, status, value, section, excerpt, note)


def build_captures(ticker: str, text: str) -> dict[str, Any]:
    source_url = SOURCES[ticker]["source_url"]
    if ticker == "CAT":
        return {
            "adjusted_eps": claim(source_url, "official_captured", {"gaap_profit_per_share": 5.47, "adjusted_profit_per_share": 5.54}, "Opening first-quarter table and bullets", first_excerpt(text, "Adjusted Profit Per Share", "profit per share", chars=1200)),
            "guidance": claim(source_url, "not_disclosed_in_release", None, "Release scan for outlook/guidance", first_excerpt(text, "forward-looking statements", "outlook", chars=900), "The release contains forward-looking-statement boilerplate but no explicit company financial guidance range was captured."),
            "growth_bridge": claim(source_url, "official_captured", {"sales_and_revenues_billion": 17.4, "sales_and_revenues_yoy_growth_pct": 22, "higher_sales_volume_billion": 2.3, "favorable_price_realization_million": 426}, "Consolidated sales and revenues commentary", first_excerpt(text, "Sales and revenues for the first quarter", "Sales and Revenues by Segment", chars=1400)),
            "segment_margins": claim(source_url, "partial", {"operating_profit_margin_pct": 17.7, "adjusted_operating_profit_margin_pct": 18.0, "power_energy_sales_billion": 7.031, "construction_industries_sales_billion": 7.161, "resource_industries_sales_billion": 3.797, "note": "Company-level operating margin and segment sales/profit commentary captured; detailed segment margin percentages were not fully captured."}, "Operating margin and sales by segment", first_excerpt(text, "Operating profit margin was 17.7%", "Sales and Revenues by Segment", chars=1500)),
            "orders_backlog": claim(source_url, "partial", {"qualitative_backlog": "record backlog", "order_activity": "robust order activity", "orders_or_book_to_bill": None}, "CEO quote / backlog commentary", first_excerpt(text, "record backlog", "robust order activity", chars=900), "Release gives qualitative order/backlog support but this capture did not identify a numeric backlog or book-to-bill."),
            "management_explanation": claim(source_url, "official_captured", {"summary": "Management cited resilient end markets, disciplined execution, solid sales and revenue growth, robust order activity, record backlog, and data-center-related Power & Energy demand."}, "CEO quote and segment commentary", first_excerpt(text, "Our team delivered a strong start", "Power Generation", chars=1300)),
            "acquisition_debt_notes": claim(source_url, "official_captured", {"enterprise_operating_cash_flow_billion": 1.9, "enterprise_cash_billion": 4.1, "share_repurchases_billion": 5.0, "dividends_billion": 0.7}, "Cash flow and capital return commentary", first_excerpt(text, "enterprise operating cash flow", "repurchases of Caterpillar common stock", chars=1000)),
        }
    if ticker == "CVX":
        return {
            "adjusted_eps": claim(source_url, "official_captured", {"gaap_diluted_eps": 1.11, "adjusted_diluted_eps": 1.41, "reported_earnings_billion": 2.2, "adjusted_earnings_billion": 2.8}, "Opening results and earnings summary", first_excerpt(text, "Adjusted earnings of $2.8 billion", "Earnings & Cash Flow Summary", chars=1300)),
            "guidance": claim(source_url, "partial", {"capital_spending_within_guidance": True}, "Management quote / guidance reference", first_excerpt(text, "capital spending remains within guidance", "guidance", chars=900), "Release references capex remaining within guidance but does not provide a fresh full-year financial guidance range in this capture."),
            "growth_bridge": claim(source_url, "partial", {"reported_earnings_billion": 2.2, "adjusted_earnings_billion": 2.8, "worldwide_production_growth_pct": 15, "us_production_growth_pct": 24, "cash_flow_from_operations_billion": 2.5, "cffo_excluding_working_capital_billion": 7.1}, "Opening bullets and earnings/cash-flow summary", first_excerpt(text, "Worldwide and U.S. production increased", "Earnings & Cash Flow Summary", chars=1500)),
            "segment_margins": claim(source_url, "partial", {"upstream_earnings_million": 3909, "downstream_loss_million": -817, "us_upstream_earnings_million": 2112, "us_net_oil_equivalent_production_mboed": 2024, "note": "Segment earnings and production metrics captured; margin percentages are not forced."}, "Segment highlights / upstream table", first_excerpt(text, "Segment Highlights", "U.S. Upstream", chars=1500)),
            "orders_backlog": claim(source_url, "not_applicable", {"rationale": "Integrated energy producer; orders/backlog/book-to-bill is not a standard current-quarter KPI in this release."}, "Release operating KPI scope", first_excerpt(text, "Net Oil-Equivalent Production", "Financial and Business Highlights", chars=900)),
            "management_explanation": claim(source_url, "official_captured", {"summary": "Management cited reliable operations, increased Kazakhstan/Gulf/Permian production, disciplined capital spending, structural cost reductions, financial flexibility, and energy-security focus amid Middle East uncertainty."}, "Management quote", first_excerpt(text, "drove higher production while maintaining financial flexibility", "Middle East", chars=1300)),
            "acquisition_debt_notes": claim(source_url, "official_captured", {"cash_returned_to_shareholders_billion": 6.0, "capex_billion": 4.1, "affiliate_capex_billion": 0.3, "free_cash_flow_billion": -1.5, "adjusted_free_cash_flow_billion": 4.1, "debt_to_cffo_ratio": "1.5x", "net_debt_to_cffo_ratio": "1.3x"}, "Financial highlights / capex and debt ratios", first_excerpt(text, "Debt-to-CFFO Ratio", "Returned $6.0 billion", chars=1300)),
        }
    if ticker == "PLTR":
        return {
            "adjusted_eps": claim(source_url, "official_captured", {"gaap_diluted_eps": 0.34, "adjusted_diluted_eps": 0.33}, "Q1 2026 highlights and financial summary", first_excerpt(text, "Adjusted EPS of $0.33", "GAAP EPS, Diluted", chars=1200)),
            "guidance": claim(source_url, "official_captured", {"q2_2026_revenue_range_billion": {"low": 1.797, "high": 1.801}, "q2_adjusted_income_from_operations_range_billion": {"low": 1.063, "high": 1.067}, "fy2026_revenue_guidance_range_billion": {"low": 7.650, "high": 7.662}, "fy2026_us_commercial_revenue_guidance_billion_over": 3.224, "fy2026_adjusted_income_from_operations_range_billion": {"low": 4.440, "high": 4.452}, "fy2026_adjusted_free_cash_flow_range_billion": {"low": 4.2, "high": 4.4}}, "Outlook", first_excerpt(text, "Outlook For Q2 2026", "For full year 2026", chars=1600)),
            "growth_bridge": claim(source_url, "official_captured", {"revenue_million": 1632.583, "revenue_yoy_growth_pct": 85, "revenue_qoq_growth_pct": 16, "us_revenue_billion": 1.282, "us_revenue_yoy_growth_pct": 104, "us_commercial_revenue_million": 595, "us_commercial_revenue_yoy_growth_pct": 133, "us_government_revenue_million": 687, "us_government_revenue_yoy_growth_pct": 84}, "Q1 2026 highlights", first_excerpt(text, "U.S. revenue grew 104%", "Revenue grew 85%", chars=1500)),
            "segment_margins": claim(source_url, "partial", {"gaap_income_from_operations_million": 753.998, "gaap_operating_margin_pct": 46, "adjusted_income_from_operations_million": 983.545, "adjusted_operating_margin_pct": 60, "gaap_net_income_margin_pct": 53, "adjusted_free_cash_flow_margin_pct": 57, "note": "Company margin metrics captured; issuer does not present conventional product segment margins in this release excerpt."}, "Financial summary and highlights", first_excerpt(text, "GAAP income from operations", "Adjusted Income from Operations", chars=1300)),
            "orders_backlog": claim(source_url, "official_captured", {"deals_over_1m": 206, "deals_over_5m": 72, "deals_over_10m": 47, "total_contract_value_billion": 2.41, "total_contract_value_yoy_growth_pct": 61, "us_commercial_tcv_billion": 1.176, "us_commercial_tcv_yoy_growth_pct": 45, "us_commercial_remaining_deal_value_billion": 4.92, "us_commercial_rdv_yoy_growth_pct": 112, "us_commercial_rdv_qoq_growth_pct": 12}, "Q1 2026 deal and remaining-deal-value highlights", first_excerpt(text, "Closed 206 deals", "remaining deal value", chars=1500)),
            "management_explanation": claim(source_url, "official_captured", {"summary": "Management attributed the quarter to exceptional AI infrastructure demand, record Rule of 40, more than doubling U.S. revenue, and confidence in an accelerating U.S. market."}, "CEO quote / opening commentary", first_excerpt(text, "Rule of 40 score has soared", "accelerating U.S. market", chars=1200)),
            "acquisition_debt_notes": claim(source_url, "partial", {"cash_cash_equivalents_short_term_treasuries_billion": 8.0, "cash_from_operations_million": 899.165, "adjusted_free_cash_flow_million": 924.630, "note": "No material acquisition/debt transaction was captured from the release; liquidity and cash-flow metrics captured as capital-allocation context."}, "Financial summary", first_excerpt(text, "Cash, cash equivalents, and short-term U.S. Treasury securities", "Cash from Operations", chars=1200)),
        }
    if ticker == "AMD":
        return {
            "adjusted_eps": claim(source_url, "official_captured", {"gaap_diluted_eps": 0.84, "non_gaap_diluted_eps": 1.37}, "Opening financial results", first_excerpt(text, "diluted earnings per share was $0.84", "non-GAAP", chars=1300)),
            "guidance": claim(source_url, "official_captured", {"q2_2026_revenue_approx_billion": 11.2, "q2_2026_revenue_range_plus_minus_million": 300, "q2_2026_revenue_midpoint_yoy_growth_pct": 46, "q2_2026_revenue_midpoint_qoq_growth_pct": 9, "q2_2026_non_gaap_gross_margin_approx_pct": 56}, "Current Outlook", first_excerpt(text, "For the second quarter of 2026", "Current Outlook", chars=1300)),
            "growth_bridge": claim(source_url, "official_captured", {"revenue_billion": 10.3, "revenue_million": 10253, "revenue_yoy_growth_pct": 38, "data_center_revenue_billion": 5.8, "data_center_revenue_yoy_growth_pct": 57, "client_and_gaming_revenue_billion": 3.6, "client_and_gaming_revenue_yoy_growth_pct": 23, "embedded_revenue_million": 873, "embedded_revenue_yoy_growth_pct": 6}, "Opening results and segment summary", first_excerpt(text, "First quarter revenue was $10.3 billion", "Data Center segment revenue", chars=1600)),
            "segment_margins": claim(source_url, "partial", {"gaap_gross_margin_pct": 53, "non_gaap_gross_margin_pct": 55, "gaap_operating_margin_pct": 14, "non_gaap_operating_margin_pct": 25, "note": "Company-level GAAP/non-GAAP margins captured plus segment revenue; detailed segment margin percentages were not fully captured."}, "GAAP and non-GAAP quarterly financial results", first_excerpt(text, "GAAP Quarterly Financial Results", "Non-GAAP Quarterly Financial Results", chars=1600)),
            "orders_backlog": claim(source_url, "partial", {"qualitative_demand": "accelerating demand for AI infrastructure", "customer_engagement": "MI450 Series and Helios strengthening", "pipeline": "growing pipeline of large-scale deployments", "orders_or_backlog_numeric": None}, "CEO quote / demand commentary", first_excerpt(text, "accelerating demand for AI infrastructure", "growing pipeline", chars=1200), "Release provides demand/pipeline commentary but no numeric backlog, orders, or book-to-bill captured."),
            "management_explanation": claim(source_url, "official_captured", {"summary": "Management cited accelerating AI infrastructure demand, Data Center as the primary revenue/earnings growth driver, inferencing and agentic AI demand, improving server supply, and strong financial leverage."}, "CEO and CFO quotes", first_excerpt(text, "We delivered an outstanding first quarter", "record quarterly free cash flow", chars=1500)),
            "acquisition_debt_notes": claim(source_url, "official_captured", {"cash_and_cash_equivalents_million": 5585, "short_term_investments_million": 6762, "inventories_million": 8045, "current_long_term_debt_million": 874, "long_term_debt_million": 2350, "acquisition_related_intangibles_net_million": 16154}, "Condensed consolidated balance sheets", first_excerpt(text, "Current portion of long-term debt", "Acquisition-related intangibles", chars=1300)),
        }
    raise KeyError(ticker)


def build_capture(ticker: str, text: str, raw_html: str) -> dict[str, Any]:
    meta = SOURCES[ticker]
    captures = build_captures(ticker, text)
    return build_capture_document(
        ticker=ticker,
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw_html,
        summary_note="Review-only official capture; no portfolio/canon/trade/account authority is granted.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture CAT/CVX/PLTR/AMD Q1 2026 official SEC/IR earnings fields.")
    parser.add_argument("--ticker", choices=sorted(SOURCES), action="append", help="Ticker to capture. Repeatable. Defaults to all batch-2 tickers.")
    args = parser.parse_args()
    result = run_capture_batch(sources=SOURCES, selected_tickers=args.ticker, build_capture=build_capture)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
