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
    "LLY": {
        "company_name": "Eli Lilly and Company",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/59478/000005947826000043/q126lillysalesandearningsp.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/59478/000005947826000043/0000059478-26-000043-index.htm",
        "accession_number": "0000059478-26-000043",
        "source_title": "Lilly reports first-quarter 2026 financial results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "META": {
        "company_name": "Meta Platforms, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1326801/000162828026028364/meta-03312026xexhibit991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1326801/000162828026028364/0001628280-26-028364-index.htm",
        "accession_number": "0001628280-26-028364",
        "source_title": "Meta Reports First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "PH": {
        "company_name": "Parker-Hannifin Corporation",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/76334/000007633426000070/exhibit991q3fy26.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/76334/000007633426000070/0000076334-26-000070-index.htm",
        "accession_number": "0000076334-26-000070",
        "source_title": "Parker Reports Fiscal 2026 Third Quarter Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "GE": {
        "company_name": "GE Aerospace",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/40545/000004054526000026/ge1q2026earningsrelease.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/40545/000004054526000026/0000040545-26-000026-index.htm",
        "accession_number": "0000040545-26-000026",
        "source_title": "GE Aerospace Announces First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
}


def excerpt_around(text: str, needle: str, chars: int = 1200) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - chars // 3)
    end = min(len(text), idx + chars)
    return compact(text[start:end])


def first_excerpt(text: str, *needles: str, chars: int = 1200) -> str:
    for needle in needles:
        excerpt = excerpt_around(text, needle, chars=chars)
        if excerpt:
            return excerpt
    return ""


def claim(source_url: str, status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return common_claim(source_url, status, value, section, excerpt, note)


def build_lly_capture(text: str, url: str) -> dict[str, Any]:
    headline = first_excerpt(text, "Revenue in Q1 2026 increased", "Q1 2026 EPS", chars=1500)
    results = first_excerpt(text, "In Q1 2026, worldwide revenue", "First-Quarter Reported Results", chars=1600)
    margin = first_excerpt(text, "Gross margin increased", "First-Quarter Non-GAAP Measures", chars=1300)
    guide = first_excerpt(text, "2026 Financial Guidance", "Updated", chars=1500)
    management = first_excerpt(text, "2026 is off to a strong start", "David A. Ricks", chars=1300)
    business_development = first_excerpt(text, "Business development activity included", "Lilly to acquire Ajax Therapeutics", chars=1600)
    return {
        "adjusted_eps": claim(url, "official_captured", {"reported_eps": 8.26, "non_gaap_eps": 8.55, "non_gaap_eps_growth_pct": 156, "acquired_iprd_charge_per_share": 0.52}, "Opening bullets / EPS reconciliation", headline),
        "guidance": claim(url, "official_captured", {"updated_revenue_range_billion": {"low": 82.0, "high": 85.0}, "updated_non_gaap_eps_range": {"low": 35.50, "high": 37.00}, "performance_margin_range_pct": {"low": 47.0, "high": 48.5}, "tax_rate_range_pct": {"low": 18, "high": 19}}, "2026 Financial Guidance", guide),
        "growth_bridge": claim(url, "official_captured", {"worldwide_revenue_billion": 19.8, "reported_revenue_growth_pct": 56, "volume_growth_pct": 65, "realized_price_impact_pct": -13, "us_revenue_billion": 12.1, "us_revenue_growth_pct": 43, "outside_us_revenue_billion": 7.7, "outside_us_revenue_growth_pct": 81, "key_products_revenue_billion": 13.4}, "First-Quarter Reported Results", results),
        "segment_margins": claim(url, "partial", {"reported_gross_margin_billion": 16.2, "reported_gross_margin_pct_of_revenue": 81.9, "non_gaap_gross_margin_billion": 16.4, "non_gaap_gross_margin_pct_of_revenue": 82.6, "note": "Company-level gross margin captured; therapeutic/product segment margins were not disclosed in this release capture."}, "Gross margin / non-GAAP measures", margin),
        "orders_backlog": claim(url, "not_applicable", {"rationale": "Pharmaceutical issuer; orders/backlog/book-to-bill is not a standard current-quarter KPI in this source."}, "Q1 2026 release operating KPI scope", first_excerpt(text, "Selected Revenue Highlights", "Mounjaro", chars=1000)),
        "management_explanation": claim(url, "official_captured", {"summary": "Management cited 56% revenue growth, higher full-year revenue guidance, Foundayo FDA approval, pipeline progress, and investment in future growth through four acquisitions."}, "CEO quote and opening bullets", management),
        "acquisition_debt_notes": claim(url, "official_captured", {"business_development_agreements": ["Orna Therapeutics", "Centessa Pharmaceuticals plc", "Kelonia Therapeutics", "Ajax Therapeutics"], "acquired_iprd_charges_million": 584}, "Business development / acquired IPR&D", business_development),
    }


def build_meta_capture(text: str, url: str) -> dict[str, Any]:
    financials = first_excerpt(text, "First Quarter 2026 Financial Highlights", "Diluted earnings per share", chars=1700)
    operational = first_excerpt(text, "First Quarter 2026 Operational and Other Financial Highlights", "Family daily active people", chars=1700)
    guide = first_excerpt(text, "CFO Outlook Commentary", "We expect second quarter 2026", chars=1500)
    segment = first_excerpt(text, "Segment Results", "Family of Apps", chars=1400)
    capex = first_excerpt(text, "Capital expenditures", "Capital return program", chars=1300)
    management = first_excerpt(text, "We had a milestone quarter", "personal superintelligence", chars=900)
    return {
        "adjusted_eps": claim(url, "not_disclosed_in_release", {"gaap_diluted_eps": 10.44, "eps_excluding_tax_benefit": 7.31, "tax_benefit_eps_impact": 3.13}, "Financial highlights / tax footnote", financials, "Release discloses GAAP diluted EPS and tax-benefit EPS impact; no adjusted/non-GAAP EPS metric is captured."),
        "guidance": claim(url, "official_captured", {"q2_2026_revenue_range_billion": {"low": 58, "high": 61}, "full_year_2026_total_expenses_range_billion": {"low": 162, "high": 169}, "capex_2026_range_billion": {"low": 125, "high": 145}, "remaining_2026_tax_rate_range_pct": {"low": 13, "high": 16}}, "CFO Outlook Commentary", guide),
        "growth_bridge": claim(url, "official_captured", {"revenue_billion": 56.311, "revenue_growth_pct": 33, "constant_currency_revenue_growth_pct": 29, "ad_impressions_growth_pct": 19, "average_price_per_ad_growth_pct": 12, "family_daily_active_people_billion": 3.56, "dap_growth_pct": 4}, "Financial / operational highlights", (financials + " " + operational).strip()),
        "segment_margins": claim(url, "partial", {"operating_margin_pct": 41, "income_from_operations_billion": 22.872, "family_of_apps_and_reality_labs_segment_tables_present": True, "note": "Company operating margin captured; detailed segment revenue and income table is present but v1 capture does not compute segment margin percentages."}, "Financial highlights / segment results", segment or financials),
        "orders_backlog": claim(url, "not_applicable", {"rationale": "Advertising/social-platform issuer; orders/backlog/book-to-bill is not a standard current-quarter KPI in this source."}, "Q1 2026 operational KPI scope", operational),
        "management_explanation": claim(url, "official_captured", {"summary": "Management described strong app momentum and Meta Superintelligence Labs progress, with CFO commentary highlighting revenue growth, ad impressions, pricing, expenses, capex, tax, and legal/regulatory risk."}, "CEO quote / CFO Outlook Commentary", (management + " " + guide).strip()),
        "acquisition_debt_notes": claim(url, "partial", {"capital_expenditures_billion": 19.84, "full_year_capex_range_billion": {"low": 125, "high": 145}, "dividend_and_equivalent_payments_billion": 1.35, "cash_and_marketable_securities_billion": 81.18, "debt_or_acquisition_commentary": None}, "Operational highlights / capital return", capex),
    }


def build_ph_capture(text: str, url: str) -> dict[str, Any]:
    headline = first_excerpt(text, "Fiscal 2026 Third Quarter Highlights", "Adjusted EPS increased", chars=1600)
    guide = first_excerpt(text, "Outlook", "Guidance for the fiscal year", chars=1300)
    segments = first_excerpt(text, "Segment Results", "Diversified Industrial Segment", chars=2200)
    orders = first_excerpt(text, "Order Rates", "Backlog increased", chars=1200)
    management = first_excerpt(text, "Our global team delivered another quarter", "Jenny Parmentier", chars=1200)
    cash = first_excerpt(text, "cash flow from operations", "Repurchased", chars=1200)
    return {
        "adjusted_eps": claim(url, "official_captured", {"gaap_eps": 7.06, "adjusted_eps": 8.17, "adjusted_eps_growth_pct": 18}, "Fiscal 2026 third quarter highlights", headline),
        "guidance": claim(url, "official_captured", {"reported_sales_growth_pct": 7, "organic_sales_growth_pct": 5.5, "acquisitions_impact_pct": 1, "divestitures_impact_pct": -1, "currency_impact_pct": 1.5, "segment_operating_margin_pct": 23.9, "adjusted_segment_operating_margin_pct": 27.2, "eps": 27.10, "adjusted_eps": 31.20}, "Outlook", guide),
        "growth_bridge": claim(url, "official_captured", {"sales_billion": 5.5, "sales_growth_pct": 11, "organic_sales_growth_pct": 6.5, "adjusted_net_income_billion": 1.0, "adjusted_net_income_growth_pct": 16}, "Fiscal 2026 third quarter highlights", headline),
        "segment_margins": claim(url, "official_captured", {"company_segment_operating_margin_pct": 23.4, "company_adjusted_segment_operating_margin_pct": 26.7, "diversified_industrial_na_margin_pct": 22.6, "diversified_industrial_na_adjusted_margin_pct": 25.3, "diversified_industrial_international_margin_pct": 22.3, "diversified_industrial_international_adjusted_margin_pct": 25.3, "aerospace_systems_margin_pct": 25.2, "aerospace_systems_adjusted_margin_pct": 29.5}, "Segment Results", segments),
        "orders_backlog": claim(url, "official_captured", {"parker_order_rate_pct": 9, "diversified_industrial_na_order_rate_pct": 7, "diversified_industrial_international_order_rate_pct": 6, "aerospace_systems_order_rate_pct": 14, "backlog_billion": 12.5}, "Order Rates", orders),
        "management_explanation": claim(url, "official_captured", {"summary": "Management cited record sales, adjusted segment operating income and margin, adjusted EPS, year-to-date operating cash flow, strong orders, record backlog, raised outlook, and an 11% quarterly dividend increase."}, "CEO quote", management),
        "acquisition_debt_notes": claim(url, "partial", {"share_repurchases_million": 275, "cash_flow_from_operations_ytd_billion": 2.6, "cash_flow_from_operations_pct_sales": 16.7, "quarterly_dividend_increase_pct": 11, "debt_or_acquisition_commentary": None}, "Highlights / cash deployment", cash),
    }


def build_ge_capture(text: str, url: str) -> dict[str, Any]:
    headline = first_excerpt(text, "First Quarter 2026:", "Total orders of", chars=1600)
    guide = first_excerpt(text, "GE Aerospace Full-Year 2026 Guidance", "2026 Guidance Assumptions", chars=1800)
    segment = first_excerpt(text, "By Segment", "Commercial Engines & Services", chars=1300)
    management = first_excerpt(text, "GE Aerospace Chairman and CEO", "H. Lawrence Culp", chars=1600)
    highlights = first_excerpt(text, "Recent highlights include", "Announced commercial wins", chars=1700)
    return {
        "adjusted_eps": claim(url, "official_captured", {"gaap_continuing_eps": 1.83, "adjusted_eps": 1.86, "adjusted_eps_growth_pct": 25}, "Opening bullets / total company results", headline),
        "guidance": claim(url, "official_captured", {"status": "maintained; trending toward higher end", "operating_profit_range_billion": {"low": 9.85, "high": 10.25}, "adjusted_eps_range": {"low": 7.10, "high": 7.40}, "free_cash_flow_range_billion": {"low": 8.0, "high": 8.4}, "fcf_conversion": ">100%", "adjusted_revenue_growth": "LDD"}, "GE Aerospace Full-Year 2026 Guidance", guide),
        "growth_bridge": claim(url, "official_captured", {"total_orders_billion": 23.0, "orders_growth_pct": 87, "total_revenue_billion": 12.4, "total_revenue_growth_pct": 25, "adjusted_revenue_billion": 11.6, "adjusted_revenue_growth_pct": 29, "operating_profit_billion": 2.5, "operating_profit_growth_pct": 18}, "Opening bullets / total company results", headline),
        "segment_margins": claim(url, "partial", {"profit_margin_gaap_pct": 17.7, "operating_profit_margin_pct": 21.8, "commercial_engines_services_revenue_billion": 8.920, "defense_propulsion_technologies_revenue_billion": 3.214, "commercial_engines_services_operating_profit_billion": 2.356, "defense_propulsion_technologies_operating_profit_billion": 0.379, "note": "Segment revenue and operating profit captured; explicit segment margin percentages are not shown in this excerpt."}, "By Segment / total company results", segment or headline),
        "orders_backlog": claim(url, "official_captured", {"total_orders_billion": 23.0, "orders_growth_pct": 87, "commercial_services_backlog_billion": 170, "commercial_engine_wins_count_more_than": 650}, "Opening bullets / CEO quote / recent highlights", (headline + " " + management + " " + highlights).strip()),
        "management_explanation": claim(url, "official_captured", {"summary": "Management cited orders growth, revenue growth, double-digit earnings/free-cash-flow growth, FLIGHT DECK execution, output and durability improvements, commercial services backlog, and guidance trending toward the high end."}, "CEO quote", management),
        "acquisition_debt_notes": claim(url, "partial", {"us_manufacturing_and_supplier_investment_billion": 1.0, "planned_and_potential_transactions_risk_disclosed": True, "debt_or_acquisition_transaction": None}, "Recent highlights / forward-looking statements", highlights),
    }


def build_capture(ticker: str, text: str, raw_html: str) -> dict[str, Any]:
    meta = SOURCES[ticker]
    url = meta["source_url"]
    builders = {"LLY": build_lly_capture, "META": build_meta_capture, "PH": build_ph_capture, "GE": build_ge_capture}
    captures = builders[ticker](text, url)
    return build_capture_document(
        ticker=ticker,
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw_html,
        summary_note="Review-only official capture; no portfolio/canon/trade/account/paper/order/money/sizing/sleeve/cash/risk-rule authority is granted.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture LLY/META/PH/GE official Q1 2026 SEC/IR earnings fields.")
    parser.add_argument("--ticker", choices=sorted(SOURCES), action="append", help="Ticker to capture. Repeatable. Defaults to LLY, META, PH, and GE.")
    args = parser.parse_args()
    result = run_capture_batch(sources=SOURCES, selected_tickers=args.ticker, build_capture=build_capture)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
