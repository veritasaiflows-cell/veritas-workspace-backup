from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from official_ir_capture_common import (
    AUTHORITY as COMMON_AUTHORITY,
    build_capture_document,
    claim as common_claim,
    run_capture_batch,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "official-ir-captures"
AUTHORITY = COMMON_AUTHORITY

SOURCES: dict[str, dict[str, str]] = {
    "JPM": {
        "company_name": "JPMorgan Chase & Co.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/19617/000162828026024990/a1q26erfexhibit991narrative.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/19617/000162828026024990/0001628280-26-024990-index.htm",
        "accession_number": "0001628280-26-024990",
        "source_title": "JPMorgan Chase Reports First-Quarter 2026 Net Income",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "GS": {
        "company_name": "The Goldman Sachs Group, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/886982/000088698226000096/a1q26gsearningsresultspr.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/886982/000088698226000096/0000886982-26-000096-index.htm",
        "accession_number": "0000886982-26-000096",
        "source_title": "Goldman Sachs First Quarter 2026 Earnings Results Presentation",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "XOM": {
        "company_name": "Exxon Mobil Corporation",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/34088/000003408826000065/livef8k1q26991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/34088/000003408826000065/0000034088-26-000065-index.htm",
        "accession_number": "0000034088-26-000065",
        "source_title": "ExxonMobil Announces First-Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "LMT": {
        "company_name": "Lockheed Martin Corporation",
        "period_end": "2026-03-29",
        "source_url": "https://www.sec.gov/Archives/edgar/data/936468/000162828026026683/ex991q12026.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/936468/000162828026026683/0001628280-26-026683-index.htm",
        "accession_number": "0001628280-26-026683",
        "source_title": "Lockheed Martin Reports First Quarter 2026 Financial Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "RTX": {
        "company_name": "RTX Corporation",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/101829/000010182926000009/a2026-04x218xkerexhibit99.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/101829/000010182926000009/0000101829-26-000009-index.htm",
        "accession_number": "0000101829-26-000009",
        "source_title": "RTX Reports Q1 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "BRK.B": {
        "company_name": "Berkshire Hathaway Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1067983/000119312526202243/brka-20260331.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1067983/000119312526202243/0001193125-26-202243-index.htm",
        "accession_number": "0001193125-26-202243",
        "source_title": "Berkshire Hathaway 2026 Q1 Form 10-Q",
        "source_type": "sec_10q_official_report",
    },
}


def excerpt_around(text: str, needle: str, chars: int = 900) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return text[:chars].replace("\n", " ").strip()
    start = max(0, idx - chars // 3)
    end = min(len(text), idx + chars)
    return text[start:end].replace("\n", " ").strip()


def claim(source_url: str, status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return common_claim(source_url, status, value, section, excerpt, note)

def build_captures(ticker: str, text: str) -> dict[str, Any]:
    u = SOURCES[ticker]["source_url"]
    if ticker == "JPM":
        return {
            "adjusted_eps": claim(u, "not_disclosed_in_release", {"gaap_diluted_eps": 5.94}, "Q1 2026 earnings narrative EPS table", excerpt_around(text, "Earnings per share - diluted"), "JPM release discloses diluted EPS; no adjusted/non-GAAP EPS field is captured."),
            "guidance": claim(u, "not_disclosed_in_release", None, "Q1 2026 earnings narrative scan", excerpt_around(text, "Jamie Dimon"), "No formal company financial guidance/outlook range was captured in the earnings narrative."),
            "growth_bridge": claim(u, "official_captured", {"reported_revenue_billion": 49.8, "managed_revenue_billion": 50.5, "managed_revenue_growth_pct": 10, "net_interest_income_growth_pct": 9, "noninterest_revenue_growth_pct": 11, "markets_revenue_growth_pct": 20}, "Firmwide metrics and discussion of results", excerpt_around(text, "Reported revenue of $49.8 billion")),
            "segment_margins": claim(u, "partial", {"roe_pct": 19, "rotce_pct": 23, "reported_overhead_ratio_pct": 54, "managed_overhead_ratio_pct": 53, "note": "Bank profitability/cost ratios captured; operating-company segment margins are not forced."}, "Firmwide Metrics", excerpt_around(text, "ROE 19%")),
            "orders_backlog": claim(u, "not_applicable", {"rationale": "Banking issuer; order/backlog/book-to-bill is not a standard operating KPI in the seven-field dictionary."}, "Q1 2026 earnings narrative bank-native KPI scope", excerpt_around(text, "Investment Banking fees")),
            "management_explanation": claim(u, "official_captured", {"summary": "Management cited strong results, client activity, loans/deposits, CIB markets and investment banking strength, and uncertainty/risk discipline."}, "CEO quote and business-line bullets", excerpt_around(text, "Jamie Dimon, Chairman and CEO")),
            "acquisition_debt_notes": claim(u, "partial", {"cet1_standardized_pct": 14.3, "cet1_advanced_pct": 14.1, "tlac_billion": 572, "standardized_rwa_trillion": 2.0, "debt_underwriting_fees_context": "Investment Banking fees rose despite lower debt underwriting fees."}, "Capital metrics and CIB discussion", excerpt_around(text, "CET1 Capital Ratios")),
        }
    if ticker == "GS":
        return {
            "adjusted_eps": claim(u, "not_disclosed_in_release", {"gaap_eps": 17.55}, "Quarterly Highlights / Results Snapshot", excerpt_around(text, "EPS1 1Q26 $17.55"), "Presentation discloses EPS; no adjusted/non-GAAP EPS field is captured."),
            "guidance": claim(u, "not_disclosed_in_release", None, "Forward-looking statements scan", excerpt_around(text, "potential future guidance from tax authorities"), "Guidance term appears in tax-authority risk language, not a company financial outlook range."),
            "growth_bridge": claim(u, "official_captured", {"net_revenues_billion": 17.23, "net_earnings_billion": 5.63, "gbm_net_revenues_billion": 12.738, "gbm_net_revenues_yoy_pct": 19, "asset_wealth_management_pretax_margin_pct": 23}, "Results snapshot and financial overview", excerpt_around(text, "Net Revenues 1Q26 $17.23 billion")),
            "segment_margins": claim(u, "partial", {"annualized_roe_pct": 19.8, "annualized_rote_pct": 21.3, "asset_wealth_management_pretax_margin_pct": 23, "note": "Bank-native ROE/ROTE and AWM pre-tax margin captured; not an operating-company segment margin bridge."}, "Results Snapshot / AWM select data", excerpt_around(text, "1Q26 pre-tax margin of 23%")),
            "orders_backlog": claim(u, "partial", {"investment_banking_fees_backlog_qoq": "decreased slightly", "driver": "decrease in Advisory partly offset by increase in Debt underwriting"}, "Global Banking & Markets commentary", excerpt_around(text, "Investment banking fees backlog")),
            "management_explanation": claim(u, "official_captured", {"summary": "Management cited strong shareholder performance despite volatility, client dependence on execution/insights, confidence in business positioning, complex geopolitics, and disciplined risk management."}, "CEO quote", excerpt_around(text, "Goldman Sachs delivered very strong performance")),
            "acquisition_debt_notes": claim(u, "official_captured", {"completed_acquisitions": ["Industry Ventures in 1Q26", "Innovator Capital Management in 2Q26"], "market_rank_context": "#2 in leveraged lending and high-yield debt"}, "Quarterly Highlights", excerpt_around(text, "Completed the acquisitions")),
        }
    if ticker == "XOM":
        return {
            "adjusted_eps": claim(u, "official_captured", {"eps": 1.00, "eps_excluding_identified_item": 1.16, "eps_excluding_identified_item_and_estimated_timing_effects": 2.09}, "Opening results bullets", excerpt_around(text, "Generated earnings per share of $1.00")),
            "guidance": claim(u, "partial", {"cash_capex_full_year_guidance_range_billion": {"low": 27, "high": 29}}, "Capital expenditures / full-year guidance reference", excerpt_around(text, "full-year guidance range of $27-$29 billion"), "Release captured capex guidance; no full earnings/EPS guidance range captured."),
            "growth_bridge": claim(u, "partial", {"earnings_billion": 4.2, "earnings_excluding_timing_and_identified_items_billion": 8.8, "sales_and_other_operating_revenue_million": 83161, "total_revenues_and_other_income_million": 85138}, "Opening bullets and condensed income statement", excerpt_around(text, "Delivered first-quarter earnings of $4.2 billion")),
            "segment_margins": claim(u, "not_disclosed_in_release", None, "Release scan for segment margin percentages", excerpt_around(text, "Total Adjusted Operating Costs"), "Release provides earnings/costs and segment activity, but this capture did not identify official segment margin percentages."),
            "orders_backlog": claim(u, "not_applicable", {"rationale": "Integrated energy producer; orders/backlog/book-to-bill is not a standard current-quarter KPI in this source."}, "Q1 2026 release operating KPI scope", excerpt_around(text, "record production in Guyana")),
            "management_explanation": claim(u, "official_captured", {"summary": "Management described ExxonMobil as stronger and more resilient through disruption and market cycles, citing advantaged volumes, optimized operations, structural cost reductions, strengthened earnings power, disciplined capital allocation, and execution excellence."}, "Management quote", excerpt_around(text, "This quarter demonstrated")),
            "acquisition_debt_notes": claim(u, "official_captured", {"debt_to_capital_pct": 15.4, "net_debt_to_capital_pct": 13.1, "period_end_cash_billion": 8.4, "total_debt_billion": 47.7, "shareholder_distributions_billion": 9.2}, "Debt/capital and shareholder distribution bullets", excerpt_around(text, "debt-to-capital")),
        }
    if ticker == "LMT":
        return {
            "adjusted_eps": claim(u, "not_disclosed_in_release", {"gaap_diluted_eps": 6.44}, "Summary financial results", excerpt_around(text, "Diluted earnings per share"), "Release discloses diluted EPS; no adjusted/non-GAAP EPS field is captured."),
            "guidance": claim(u, "official_captured", {"status": "reaffirmed", "sales_growth_yoy_pct_approx": 5, "operating_profit_growth_yoy_pct_approx": 25, "free_cash_flow_range_billion": {"low": 6.5, "high": 6.8}}, "2026 financial outlook / CEO quote", excerpt_around(text, "reaffirm our 2026 full year guidance")),
            "growth_bridge": claim(u, "partial", {"sales_billion": 18.0, "net_earnings_billion": 1.5, "sales_commentary": "Total sales comparable year over year; higher MFC and Space offset by lower RMS and Aeronautics."}, "Summary financial results / operating discussion", excerpt_around(text, "Total sales during the quarter")),
            "segment_margins": claim(u, "partial", {"business_segment_operating_profit_million": 1823, "consolidated_operating_profit_million": 2063, "note": "Segment operating profit captured; full segment margin percentages not captured."}, "Summary Financial Results", excerpt_around(text, "Business segment operating profit")),
            "orders_backlog": claim(u, "partial", {"backlog_commentary": "substantial backlog", "orders_or_book_to_bill": None}, "CEO quote / backlog commentary", excerpt_around(text, "substantial backlog"), "Release gives qualitative backlog support but this capture did not identify an absolute backlog value or book-to-bill."),
            "management_explanation": claim(u, "official_captured", {"summary": "Management attributed results and backlog to strong customer demand, operational performance, focused risk management, and munitions production framework agreements."}, "CEO quote and opening bullets", excerpt_around(text, "strong customer demand")),
            "acquisition_debt_notes": claim(u, "official_captured", {"scheduled_long_term_debt_repayments_billion": 1.0, "capital_expenditures_million": 511, "cash_dividends_million": 816}, "Cash activities", excerpt_around(text, "scheduled long-term debt repayments")),
        }
    if ticker == "RTX":
        return {
            "adjusted_eps": claim(u, "official_captured", {"gaap_eps": 1.51, "adjusted_eps": 1.78, "adjusted_eps_yoy_growth_pct": 21}, "Opening Q1 2026 bullets", excerpt_around(text, "Adjusted EPS* of $1.78")),
            "guidance": claim(u, "official_captured", {"adjusted_sales_range_billion": {"low": 92.5, "high": 93.5}, "organic_sales_growth_range_pct": {"low": 5, "high": 6}, "adjusted_eps_range": {"low": 6.70, "high": 6.90}, "free_cash_flow_range_billion": {"low": 8.25, "high": 8.75}, "raised_cut_reaffirmed": "raises adjusted sales and adjusted EPS; confirms free cash flow"}, "Full-year 2026 outlook bullets", excerpt_around(text, "Updates outlook for full year 2026")),
            "growth_bridge": claim(u, "official_captured", {"sales_billion": 22.1, "reported_sales_growth_pct": 9, "organic_sales_growth_pct": 10, "adjusted_net_income_billion": 2.4, "adjusted_net_income_growth_pct": 22}, "Opening bullets / summary financial results", excerpt_around(text, "Sales of $22.1 billion")),
            "segment_margins": claim(u, "partial", {"note": "Release names adjusted/segment margin measures; this capture records company-level adjusted results and leaves detailed segment margin table for manual review."}, "Non-GAAP measures / segment results context", excerpt_around(text, "margin percentage (ROS)")),
            "orders_backlog": claim(u, "official_captured", {"company_backlog_billion": 271, "commercial_backlog_billion": 162, "defense_backlog_billion": 109}, "Opening Q1 2026 bullets", excerpt_around(text, "Company backlog of $271 billion")),
            "management_explanation": claim(u, "official_captured", {"summary": "Management cited organic sales and adjusted operating profit growth across all three segments, execution focus, backlog delivery, differentiated products, and strong demand."}, "CEO quote", excerpt_around(text, "RTX delivered a very strong start")),
            "acquisition_debt_notes": claim(u, "partial", {"gaap_eps_acquisition_accounting_adjustments": 0.27, "free_cash_flow_uses_note": "Free cash flow supports acquisitions, debt service, repurchases, and distributions."}, "Opening bullets / non-GAAP definition", excerpt_around(text, "acquisition accounting adjustments")),
        }
    if ticker == "BRK.B":
        return {
            "adjusted_eps": claim(u, "not_disclosed_in_release", {"net_earnings_per_equivalent_class_b_share": 4.68, "rationale": "Berkshire reports GAAP net earnings per equivalent Class B share; adjusted EPS is not normally applicable."}, "Consolidated statements of earnings", excerpt_around(text, "Net earnings per average equivalent Class B share"), "10-Q discloses GAAP net earnings per equivalent Class B share; no adjusted/non-GAAP EPS field is captured."),
            "guidance": claim(u, "not_disclosed_in_release", None, "Form 10-Q scan for company guidance/outlook", excerpt_around(text, "We do not currently expect"), "10-Q does not provide a Berkshire financial guidance/outlook range in this capture."),
            "growth_bridge": claim(u, "partial", {"net_earnings_million": 10179, "net_earnings_attributable_to_berkshire_million": 10106, "net_earnings_per_class_b_share": 4.68}, "Consolidated Statements of Earnings", excerpt_around(text, "Net earnings attributable to Berkshire shareholders")),
            "segment_margins": claim(u, "partial", {"bnsf_railroad_operating_revenues_million": 5959, "bnsf_railroad_operating_earnings_million": 2048, "electric_utility_margin_billion": 2.0, "electric_utility_margin_growth_pct": 2.4}, "BNSF and Berkshire Hathaway Energy discussion", excerpt_around(text, "Railroad operating earnings")),
            "orders_backlog": claim(u, "not_applicable", {"rationale": "Conglomerate/insurance/railroad/utility issuer; orders/backlog/book-to-bill is not a unified Berkshire KPI in the 10-Q."}, "Form 10-Q operating KPI scope", excerpt_around(text, "BNSF")),
            "management_explanation": claim(u, "partial", {"summary": "10-Q MD&A explains segment drivers including BNSF freight volumes, utility margin, insurance and operating company results; no earnings-release CEO quote was captured."}, "Management Discussion and Analysis", excerpt_around(text, "in the first quarter of 2026 compared to 2025")),
            "acquisition_debt_notes": claim(u, "official_captured", {"common_stock_repurchases_million": 235, "insurance_and_other_notes_payable_borrowings_million": 42835, "railroad_utilities_energy_notes_payable_borrowings_million": 86051}, "Equity statement / balance sheet liabilities", excerpt_around(text, "Acquisitions of common stock")),
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
        summary_note="Review-only official capture; bank-native fields remain bank-native and no portfolio/canon/trade/account authority is granted.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture priority Q1 2026 official SEC/IR earnings fields.")
    parser.add_argument("--ticker", choices=sorted(SOURCES), action="append", help="Ticker to capture. Repeatable. Defaults to all priority tickers.")
    args = parser.parse_args()
    result = run_capture_batch(sources=SOURCES, selected_tickers=args.ticker, build_capture=build_capture)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
