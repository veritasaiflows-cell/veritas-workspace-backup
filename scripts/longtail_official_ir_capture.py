from __future__ import annotations

"""WF70 long-tail official SEC/IR capture expansion and extractor layer.

This production entrypoint owns Q1 2026 long-tail official-source captures for
BKNG, KTOS, LNG, SMCI, LIN, ECL, VMC, NFLX, TMUS, CME, and WMB. It reuses the
common WF70 helper for fetch/source metadata/artifact writing while keeping
ticker-specific field extraction local. Review-only only: no canon/portfolio/
trade/account/paper-order authority and no owner-approval inference.
"""

import argparse
import json
from typing import Any

from official_ir_capture_common import build_capture_document, claim, first_excerpt, run_capture_batch

SOURCES: dict[str, dict[str, str]] = {
    "BKNG": {
        "company_name": "Booking Holdings Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1075531/000107553126000024/q1-26bkngearningsrelease.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1075531/000107553126000024/0001075531-26-000024-index.htm",
        "accession_number": "0001075531-26-000024",
        "source_title": "Booking Holdings Q1 2026 Earnings Release",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "KTOS": {
        "company_name": "Kratos Defense & Security Solutions, Inc.",
        "period_end": "2026-03-29",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1069258/000106925826000051/ktos202603298kexhibit991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1069258/000106925826000051/0001069258-26-000051-index.htm",
        "accession_number": "0001069258-26-000051",
        "source_title": "Kratos Reports First Quarter 2026 Financial Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "LNG": {
        "company_name": "Cheniere Energy, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/3570/000000357026000016/cei20261stqtrerex991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/3570/000000357026000016/0000003570-26-000016-index.htm",
        "accession_number": "0000003570-26-000016",
        "source_title": "Cheniere Reports First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "SMCI": {
        "company_name": "Super Micro Computer, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1375365/000137536526000013/exhibit991_20260331.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1375365/000137536526000013/0001375365-26-000013-index.htm",
        "accession_number": "0001375365-26-000013",
        "source_title": "Super Micro Computer Announces Third Quarter Fiscal 2026 Financial Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "LIN": {
        "company_name": "Linde plc",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1707925/000165495426004202/lin_ex991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1707925/000165495426004202/0001654954-26-004202-index.htm",
        "accession_number": "0001654954-26-004202",
        "source_title": "Linde Reports First-Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "ECL": {
        "company_name": "Ecolab Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/31462/000110465926049822/ecl-20260428xex99d1.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/31462/000110465926049822/0001104659-26-049822-index.htm",
        "accession_number": "0001104659-26-049822",
        "source_title": "Ecolab First Quarter 2026 Earnings Release",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "VMC": {
        "company_name": "Vulcan Materials Company",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1396009/000114036126017638/ef20071724_ex99-1.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1396009/000114036126017638/0001140361-26-017638-index.htm",
        "accession_number": "0001140361-26-017638",
        "source_title": "Vulcan Materials Reports First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "NFLX": {
        "company_name": "Netflix, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1065280/000106528026000137/ex991_q126.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1065280/000106528026000137/0001065280-26-000137-index.htm",
        "accession_number": "0001065280-26-000137",
        "source_title": "Netflix Q1 2026 Earnings Interview / Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "TMUS": {
        "company_name": "T-Mobile US, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1283699/000128369926000062/tmus03312026ex991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1283699/000128369926000062/0001283699-26-000062-index.htm",
        "accession_number": "0001283699-26-000062",
        "source_title": "T-Mobile Reports First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "CME": {
        "company_name": "CME Group Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1156375/000115637526000016/exhibit9913312026.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1156375/000115637526000016/0001156375-26-000016-index.htm",
        "accession_number": "0001156375-26-000016",
        "source_title": "CME Group Reports First-Quarter 2026 Financial Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "WMB": {
        "company_name": "The Williams Companies, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/107263/000010726326000015/wmb_20260331xer.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/107263/000010726326000015/0000107263-26-000015-index.htm",
        "accession_number": "0000107263-26-000015",
        "source_title": "Williams Reports First-Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
}

SUMMARY_NOTE = "Review-only long-tail official source capture; hardened ticker-specific fields are populated only where official evidence supports them, otherwise fields remain manual_required/not_disclosed/not_applicable/partial."

FIELD_NOTES: dict[str, str] = {
    "adjusted_eps": "Official source resolved; ticker-specific adjusted/non-GAAP EPS extraction remains manual_required for the long-tail v1 pass.",
    "guidance": "Official source resolved; guidance/outlook extraction remains manual_required for the long-tail v1 pass.",
    "growth_bridge": "Official source resolved; revenue/growth bridge extraction remains manual_required for the long-tail v1 pass.",
    "segment_margins": "Official source resolved; segment/margin extraction remains manual_required for the long-tail v1 pass.",
    "orders_backlog": "Official source resolved; orders/backlog/book-to-bill applicability and extraction remain manual_required for the long-tail v1 pass.",
    "management_explanation": "Official source resolved; management commentary extraction remains manual_required for the long-tail v1 pass.",
    "acquisition_debt_notes": "Official source resolved; acquisition/debt/capital-return note extraction remains manual_required for the long-tail v1 pass.",
}

REQUIRED_CAPTURE_FIELDS = set(FIELD_NOTES)

NEEDLES: dict[str, tuple[str, ...]] = {
    "adjusted_eps": ("adjusted", "diluted EPS", "earnings per share", "EPS"),
    "guidance": ("guidance", "outlook", "expect", "full year"),
    "growth_bridge": ("revenue", "sales", "net sales", "growth"),
    "segment_margins": ("margin", "segment", "operating income", "operating profit"),
    "orders_backlog": ("orders", "backlog", "book-to-bill", "book to bill"),
    "management_explanation": ("CEO", "Chief Executive", "said", "comment"),
    "acquisition_debt_notes": ("acquisition", "debt", "cash flow", "repurchase", "dividend"),
}


def manual_capture(ticker: str, text: str) -> dict[str, Any]:
    url = SOURCES[ticker]["source_url"]
    captures: dict[str, Any] = {}
    for field, note in FIELD_NOTES.items():
        excerpt = first_excerpt(text, *NEEDLES[field], chars=1000, fallback_to_start=True)
        captures[field] = claim(
            url,
            "manual_required",
            None,
            f"{SOURCES[ticker]['source_title']} / long-tail v1 source-resolved scan",
            excerpt,
            note,
        )
    return captures


def official_claim(ticker: str, field: str, status: str, value: Any, text: str, *needles: str, note: str | None = None) -> dict[str, Any]:
    return claim(
        SOURCES[ticker]["source_url"],
        status,
        value,
        f"{SOURCES[ticker]['source_title']} / {field}",
        first_excerpt(text, *needles, chars=1400, fallback_to_start=True),
        note,
    )


def bkng_captures(text: str) -> dict[str, Any]:
    ticker = "BKNG"
    return {
        "adjusted_eps": official_claim(
            ticker,
            "adjusted_eps",
            "official_captured",
            {"adjusted_eps": 1.14, "gaap_diluted_eps": 1.36, "adjusted_eps_growth_pct": 14, "gaap_eps_growth_pct": 239, "stock_split_reflected": "25-for-1 split reflected retroactively"},
            text,
            "Adjusted EPS $1.14",
            "GAAP EPS $1.36",
            note="Official release table reports adjusted EPS and GAAP EPS for Q1 2026.",
        ),
        "guidance": official_claim(
            ticker,
            "guidance",
            "official_captured",
            {
                "q2_2026_room_nights_growth_range_pct": [2, 4],
                "q2_2026_gross_bookings_growth_range_pct": [4, 6],
                "q2_2026_constant_currency_gross_bookings_growth_range_pct": [2, 4],
                "q2_2026_revenue_growth_range_pct": [4, 6],
                "q2_2026_constant_currency_revenue_growth_range_pct": [2, 4],
                "q2_2026_adjusted_ebitda_growth_range_pct": [4, 6],
                "fy_2026_gross_bookings_growth": "high single digits to low double digits",
                "fy_2026_revenue_growth": "high single digits",
                "fy_2026_adjusted_eps_growth": "low to mid-teens",
                "middle_east_conflict_assumption": "direct/indirect impact through end of June followed by second-half bookings recovery",
            },
            text,
            "Booking Holdings' guidance",
            "Q2 2026 FY 2026",
            note="Official release gives Q2 and FY 2026 growth guidance plus Middle East conflict assumptions.",
        ),
        "growth_bridge": official_claim(
            ticker,
            "growth_bridge",
            "official_captured",
            {
                "room_nights_million": 338,
                "room_nights_growth_pct": 6,
                "gross_bookings_billion": 53.8,
                "gross_bookings_growth_pct": 15,
                "gross_bookings_constant_currency_growth_pct": 8,
                "revenue_billion": 5.5,
                "revenue_growth_pct": 16,
                "revenue_constant_currency_growth_pct": 10,
                "middle_east_room_night_growth_headwind_pct_points": 2,
            },
            text,
            "Room Nights 338M",
            "Gross Bookings $53.8B",
            note="Official release table and bullets quantify top-line growth and Middle East headwind.",
        ),
        "segment_margins": official_claim(
            ticker,
            "segment_margins",
            "partial",
            {"net_income_margin_pct": 19.6, "adjusted_ebitda_margin_pct": 23.3, "marketing_expense_as_pct_of_gross_bookings": 3.8, "note": "Company-level margins captured; release does not provide operating segment margin percentages."},
            text,
            "Additional Highlights Margins",
            "Adjusted EBITDA margin",
            note="Company-level margin disclosures captured; segment-level margins remain not disclosed in this release.",
        ),
        "orders_backlog": official_claim(
            ticker,
            "orders_backlog",
            "not_applicable",
            {"rationale": "Travel agency/merchant model; order backlog/book-to-bill is not a standard operating KPI. Gross bookings and room nights are captured in growth_bridge."},
            text,
            "Gross bookings grew",
            "Room Nights",
            note="Backlog/book-to-bill is not applicable; official demand KPIs are room nights and gross bookings.",
        ),
        "management_explanation": official_claim(
            ticker,
            "management_explanation",
            "official_captured",
            {"summary": "Management cited Middle East conflict headwinds, resilient execution, stronger-than-expected underlying performance, U.S. strength, Connected Trip, global reach, and generative AI initiatives."},
            text,
            "Despite headwinds",
            "Glenn Fogel",
            note="CEO explanation captured from official release quote.",
        ),
        "acquisition_debt_notes": official_claim(
            ticker,
            "acquisition_debt_notes",
            "official_captured",
            {"dividend_per_share": 0.42, "q1_repurchases_billion": 3.6, "remaining_authorization_billion": 18.2, "cash_from_operations_billion": 3.2, "free_cash_flow_billion": 3.1},
            text,
            "Return of Capital to Shareholders",
            "Stock Repurchase Program",
            note="Official release captures dividend, repurchase authorization, operating cash flow, and free cash flow.",
        ),
    }


def nflx_captures(text: str) -> dict[str, Any]:
    ticker = "NFLX"
    return {
        "adjusted_eps": official_claim(
            ticker,
            "adjusted_eps",
            "not_disclosed_in_release",
            {"gaap_diluted_eps": 1.23, "gaap_diluted_eps_yoy_growth_pct": 86, "q2_2026_forecast_diluted_eps": 0.78},
            text,
            "Diluted EPS $ 0.66",
            "Diluted EPS for the quarter amounted",
            note="Netflix release reports GAAP diluted EPS but does not present adjusted/non-GAAP EPS.",
        ),
        "guidance": official_claim(
            ticker,
            "guidance",
            "official_captured",
            {"fy_2026_revenue_range_billion": [50.7, 51.7], "fy_2026_revenue_growth_range_pct": [12, 14], "fy_2026_fx_neutral_growth_range_pct": [11, 13], "fy_2026_operating_margin_target_pct": 31.5, "q2_2026_revenue_forecast_billion": 12.574, "q2_2026_revenue_growth_pct": 13, "q2_2026_fx_neutral_revenue_growth_pct": 12, "q2_2026_operating_margin_forecast_pct": 32.6, "q2_2026_diluted_eps_forecast": 0.78},
            text,
            "Our full year 2026 guidance is unchanged",
            "Q2'26 Forecast",
            note="Official shareholder letter provides FY 2026 and Q2 forecast metrics.",
        ),
        "growth_bridge": official_claim(
            ticker,
            "growth_bridge",
            "official_captured",
            {"q1_2026_revenue_billion": 12.250, "q1_2026_revenue_growth_pct": 16.2, "q1_2026_fx_neutral_revenue_growth_pct": 14, "drivers": ["membership growth", "higher pricing", "increased ad revenue", "favorable FX net of hedging"]},
            text,
            "Revenue in Q1 grew",
            "driven primarily by membership growth",
            note="Official shareholder letter explains Q1 revenue growth bridge and drivers.",
        ),
        "segment_margins": official_claim(
            ticker,
            "segment_margins",
            "partial",
            {"q1_2026_operating_income_billion": 3.957, "q1_2026_operating_income_growth_pct": 18, "q1_2026_operating_margin_pct": 32.3, "q2_2026_operating_margin_forecast_pct": 32.6, "note": "Company-level operating margin captured; Netflix does not disclose segment margin percentages in this release."},
            text,
            "Operating Margin 31.7",
            "operating margin of 32.3",
            note="Company-level operating margin captured; no segment margin split in release.",
        ),
        "orders_backlog": official_claim(
            ticker,
            "orders_backlog",
            "not_applicable",
            {"rationale": "Streaming subscription/media model; orders/backlog/book-to-bill is not a standard operating KPI in this release."},
            text,
            "membership growth",
            "members",
            note="Backlog/book-to-bill is not applicable to Netflix's disclosed operating model.",
        ),
        "management_explanation": official_claim(
            ticker,
            "management_explanation",
            "official_captured",
            {"summary": "Management emphasized stronger entertainment value, technology/AI-enabled service improvements, mobile redesign, advertising monetization, healthy membership growth, pricing, and ad revenue."},
            text,
            "We have a clear strategy",
            "Improving monetization",
            note="Management explanation captured from shareholder letter strategy and Q1 results commentary.",
        ),
        "acquisition_debt_notes": official_claim(
            ticker,
            "acquisition_debt_notes",
            "official_captured",
            {"interpositive_acquisition_disclosed": True, "gross_debt_billion": 14.4, "cash_and_equivalents_billion": 12.3, "q1_repurchases_billion": 1.3, "remaining_share_repurchase_authorization_billion": 6.8, "warner_bros_termination_fee_billion": 2.8},
            text,
            "acquired InterPositive",
            "gross debt",
            "share repurchase",
            note="Official shareholder letter captures acquisition note, debt/cash position, Warner Bros. termination fee, and buybacks.",
        ),
    }


def cme_captures(text: str) -> dict[str, Any]:
    ticker = "CME"
    return {
        "adjusted_eps": official_claim(
            ticker,
            "adjusted_eps",
            "official_captured",
            {"gaap_diluted_eps": 3.18, "adjusted_diluted_eps": 3.36, "gaap_diluted_eps_growth_pct": 20, "adjusted_diluted_eps_growth_pct": 20},
            text,
            "adjusted basis",
            "diluted earnings per common share were $3.36",
            note="Official release reports GAAP and adjusted diluted EPS.",
        ),
        "guidance": official_claim(
            ticker,
            "guidance",
            "not_disclosed_in_release",
            None,
            text,
            "Looking ahead",
            "will continue",
            note="Official release includes qualitative forward-looking commentary but no numeric guidance range.",
        ),
        "growth_bridge": official_claim(
            ticker,
            "growth_bridge",
            "official_captured",
            {"revenue_billion": 1.9, "revenue_growth_pct": 14, "clearing_and_transaction_fees_revenue_billion": 1.5, "market_data_revenue_million": 224, "average_rate_per_contract": 0.652, "net_income_billion": 1.2},
            text,
            "Record revenue",
            "Clearing and transaction fees",
            note="Official release quantifies revenue growth and fee/market-data revenue drivers.",
        ),
        "segment_margins": official_claim(
            ticker,
            "segment_margins",
            "partial",
            {"operating_income_billion": 1.3, "adjusted_operating_income_billion": 1.4, "total_revenues_billion": 1.8801, "total_expenses_million": 570.4, "note": "Release provides operating income and revenue, not segment margin percentages."},
            text,
            "Operating Income 1,309.7",
            "Adjusted Operating Income",
            note="Company-level operating income captured; segment margins not disclosed.",
        ),
        "orders_backlog": official_claim(
            ticker,
            "orders_backlog",
            "official_captured",
            {"q1_2026_adv_million_contracts": 36.2, "adv_growth_pct": 22, "non_us_adv_million_contracts": 11.4, "non_us_adv_growth_pct": 30, "apac_adv_growth_pct": 33, "emea_adv_growth_pct": 29, "records_across_asset_classes": 6, "note": "Exchange volume/ADV is the relevant demand KPI; backlog/book-to-bill is not applicable."},
            text,
            "First-quarter 2026 average daily volume",
            "Non-U.S. ADV",
            note="Official release captures exchange demand through ADV records rather than backlog.",
        ),
        "management_explanation": official_claim(
            ticker,
            "management_explanation",
            "official_captured",
            {"summary": "Management cited elevated risk management demand, record ADV across six asset classes, margin savings, FICC cross-margining expansion, and product/service innovation."},
            text,
            "risk has become the new normal",
            "Terry Duffy",
            note="CEO explanation captured from official release quote.",
        ),
        "acquisition_debt_notes": official_claim(
            ticker,
            "acquisition_debt_notes",
            "official_captured",
            {"cash_billion": 2.6, "debt_billion": 3.4, "dividends_paid_billion": 2.7, "repurchases_million": 536},
            text,
            "cash",
            "repurchased $536 million",
            note="Official release captures cash/debt position, dividends, and repurchases.",
        ),
    }


def ktos_captures(text: str) -> dict[str, Any]:
    ticker = "KTOS"
    return {
        "adjusted_eps": official_claim(
            ticker, "adjusted_eps", "official_captured",
            {"gaap_eps": 0.07, "adjusted_eps": 0.16, "prior_year_gaap_eps": 0.03, "prior_year_adjusted_eps": 0.12},
            text, "Adjusted earnings per share", "GAAP Net Income per share",
            note="Official release reports GAAP EPS and adjusted EPS for Q1 2026."),
        "guidance": official_claim(
            ticker, "guidance", "official_captured",
            {"fy_2026_revenue_range_billion": [1.700, 1.760], "fy_2026_adjusted_ebitda_range_million": [170.0, 176.0], "includes_orbit_acquisition": True, "guidance_change": "increased fiscal FY26 financial guidance"},
            text, "Fiscal 2026 Revenue Forecast", "Adjusted EBITDA Forecast",
            note="Official headline and release give raised FY26 revenue and adjusted EBITDA forecast."),
        "growth_bridge": official_claim(
            ticker, "growth_bridge", "official_captured",
            {"revenue_million": 371.0, "revenue_growth_pct": 22.6, "organic_revenue_growth_pct": 15.8, "unmanned_systems_revenue_million": 82.6, "unmanned_systems_organic_growth_pct": 30.9, "government_solutions_revenue_million": 288.4, "government_solutions_organic_growth_pct": 11.8, "defense_rocket_support_growth_pct": 45.8, "turbine_technologies_growth_pct": 20.3, "microwave_products_growth_pct": 12.3},
            text, "First Quarter 2026 Revenues", "Organic revenue growth",
            note="Official release quantifies consolidated and segment growth plus organic drivers."),
        "segment_margins": official_claim(
            ticker, "segment_margins", "partial",
            {"operating_income_million": 4.7, "adjusted_ebitda_million": 38.7, "kus_adjusted_ebitda_million": 5.2, "kgs_adjusted_ebitda_million": 33.5, "note": "Release provides segment adjusted EBITDA and operating income, not complete segment margin percentages."},
            text, "Adjusted EBITDA", "KUSs Adjusted EBITDA",
            note="Segment adjusted EBITDA captured; full segment margin percentages are not disclosed."),
        "orders_backlog": official_claim(
            ticker, "orders_backlog", "official_captured",
            {"q1_bookings_million": 605.2, "q1_book_to_bill": 1.6, "ltm_bookings_billion": 1.715, "ltm_book_to_bill": 1.2, "consolidated_backlog_billion": 2.010, "prior_quarter_backlog_billion": 1.573, "funded_backlog_billion": 1.457, "unfunded_backlog_million": 553.5, "bid_and_proposal_pipeline_billion": 14.3, "kus_backlog_million": 375.4, "kgs_backlog_billion": 1.635},
            text, "Total backlog", "book-to-bill", "Backlog on March 29",
            note="Official release provides bookings, book-to-bill, funded/unfunded backlog, and pipeline."),
        "management_explanation": official_claim(
            ticker, "management_explanation", "official_captured",
            {"summary": "Management cited a balanced business model, rapid fielding for the Department of War, defense industrial base recapitalization, FY26/FY27 defense funding, multi-year production frameworks, and alignment with department objectives."},
            text, "Eric DeMarco", "Kratos President and CEO",
            note="CEO explanation captured from official release quote."),
        "acquisition_debt_notes": official_claim(
            ticker, "acquisition_debt_notes", "partial",
            {"recent_acquisitions": ["Nomad Global Communication Solutions", "Orbit Technologies Ltd."], "free_cash_flow_used_million": 43.1, "cash_flow_used_in_operations_million": 27.4, "capital_expenditures_million": 19.9, "valkyrie_sale_proceeds_million": 4.2, "note": "Acquisition and cash-flow disclosures captured; debt balance not extracted from this release."},
            text, "Orbit Technologies", "Free Cash Flow Used",
            note="Official release captures acquisition context and cash-flow use; debt balance remains not extracted."),
    }


def smci_captures(text: str) -> dict[str, Any]:
    ticker = "SMCI"
    return {
        "adjusted_eps": official_claim(
            ticker, "adjusted_eps", "official_captured",
            {"gaap_diluted_eps": 0.72, "non_gaap_diluted_eps": 0.84, "prior_year_gaap_diluted_eps": 0.17, "prior_year_non_gaap_diluted_eps": 0.31},
            text, "Non-GAAP diluted net income per common share", "Diluted net income per common share",
            note="Official release reports GAAP and non-GAAP diluted EPS for fiscal Q3 2026."),
        "guidance": official_claim(
            ticker, "guidance", "official_captured",
            {"q4_fy2026_net_sales_range_billion": [11.0, 12.5], "q4_fy2026_gaap_eps_range": [0.53, 0.67], "q4_fy2026_non_gaap_eps_range": [0.65, 0.79], "fy2026_net_sales_range_billion": [38.9, 40.4], "gaap_tax_rate_assumption_pct": 19.4, "non_gaap_tax_rate_assumption_pct": 20.4},
            text, "Business Outlook", "For fiscal year 2026",
            note="Official release gives Q4 FY26 and FY26 net-sales/EPS outlook."),
        "growth_bridge": official_claim(
            ticker, "growth_bridge", "official_captured",
            {"net_sales_billion": 10.2, "prior_quarter_net_sales_billion": 12.7, "prior_year_net_sales_billion": 4.6, "net_income_million": 483, "prior_quarter_net_income_million": 401, "prior_year_net_income_million": 109, "drivers": ["DCBBS business growth", "AI and enterprise vertical demand", "new US manufacturing facilities"]},
            text, "Third Quarter Fiscal Year 2026 Highlights", "Net sales of $10.2 billion",
            note="Official release gives sales comparison and management demand drivers."),
        "segment_margins": official_claim(
            ticker, "segment_margins", "partial",
            {"gross_margin_pct": 9.9, "prior_quarter_gross_margin_pct": 6.3, "prior_year_gross_margin_pct": 9.6, "non_gaap_gross_margin_pct": 10.1, "prior_year_non_gaap_gross_margin_pct": 9.7, "note": "Company gross margins captured; segment margins not disclosed in release."},
            text, "Gross margin", "Non-GAAP gross margin",
            note="Company-level gross margin/non-GAAP gross margin captured; segment margins not disclosed."),
        "orders_backlog": official_claim(
            ticker, "orders_backlog", "partial",
            {"qualitative_demand": "massive demand for various AI and enterprise verticals", "customer_commitments_expectation": "additional customer commitments expected in upcoming quarters", "numeric_orders_or_backlog": None},
            text, "massive demand", "customer commitments",
            note="Official release provides qualitative demand/customer commitment language but no numeric orders/backlog."),
        "management_explanation": official_claim(
            ticker, "management_explanation", "official_captured",
            {"summary": "Management cited transformation into a total datacenter infrastructure provider, margin recovery, DCBBS growth, new US manufacturing capacity, and AI/enterprise demand."},
            text, "Supermicro's transformation", "Charles Liang",
            note="CEO explanation captured from official release quote."),
        "acquisition_debt_notes": official_claim(
            ticker, "acquisition_debt_notes", "official_captured",
            {"cash_and_equivalents_billion": 1.3, "bank_debt_and_convertible_notes_billion": 8.8, "cash_flow_used_in_operations_billion": 6.6, "capex_and_investments_million": 97},
            text, "total cash and cash equivalents", "bank debt and convertible notes",
            note="Official release captures cash, debt/convertible notes, operating cash use, and capex/investments."),
    }


def tmus_captures(text: str) -> dict[str, Any]:
    ticker = "TMUS"
    return {
        "adjusted_eps": official_claim(
            ticker, "adjusted_eps", "not_disclosed_in_release",
            {"gaap_diluted_eps": 2.27, "gaap_diluted_eps_yoy_change_pct": -12.0, "uscellular_merger_related_cost_impact_per_share": 0.43},
            text, "Diluted earnings per share", "Diluted EPS",
            note="Official release reports GAAP diluted EPS and UScellular cost impact but does not report adjusted/non-GAAP EPS."),
        "guidance": official_claim(
            ticker, "guidance", "official_captured",
            {"postpaid_net_account_additions_range_thousand": [950, 1050], "core_adjusted_ebitda_range_billion": [37.1, 37.5], "operating_cash_flow_range_billion": [28.1, 28.7], "capex_approx_billion": 10.0, "adjusted_free_cash_flow_range_billion": [18.1, 18.7], "guidance_change_midpoint_increase_million": 50},
            text, "Financial Guidance", "Postpaid net account additions",
            note="Official release raises 2026 guidance for accounts, Core Adjusted EBITDA, operating cash flow, and adjusted free cash flow."),
        "growth_bridge": official_claim(
            ticker, "growth_bridge", "official_captured",
            {"service_revenues_billion": 18.8, "service_revenue_growth_pct": 11, "postpaid_service_revenues_billion": 15.6, "postpaid_service_revenue_growth_pct": 15, "total_revenues_billion": 23.107, "total_revenues_yoy_growth_pct": 10.6, "core_adjusted_ebitda_billion": 9.2, "core_adjusted_ebitda_growth_pct": 12},
            text, "Service revenues of $18.8 billion", "Postpaid service revenues",
            note="Official release quantifies service/postpaid revenue growth and Core Adjusted EBITDA growth."),
        "segment_margins": official_claim(
            ticker, "segment_margins", "partial",
            {"core_adjusted_ebitda_billion": 9.2, "core_adjusted_ebitda_growth_pct": 12, "net_income_billion": 2.5, "note": "Release provides Core Adjusted EBITDA and net income; segment margin percentages are not captured."},
            text, "Core Adjusted EBITDA", "Net income of $2.5 billion",
            note="Profitability metrics captured; segment margin percentages not disclosed in release text."),
        "orders_backlog": official_claim(
            ticker, "orders_backlog", "official_captured",
            {"postpaid_net_account_additions_thousand": 217, "postpaid_net_account_additions_growth_pct": 6, "postpaid_arpa": 151.93, "postpaid_arpa_growth_pct": 3.9, "postpaid_account_churn_pct": 1.04, "total_postpaid_accounts_end_period_thousand": 34439, "note": "Telecom demand captured through postpaid account adds/churn/ARPA rather than backlog."},
            text, "Postpaid net account additions", "Postpaid ARPA",
            note="Official release captures customer/account demand KPIs; backlog/book-to-bill is not applicable."),
        "management_explanation": official_claim(
            ticker, "management_explanation", "official_captured",
            {"summary": "Management cited best network/value/experiences, accelerating postpaid net account growth, ARPA growth, deepening customer relationships, industry-leading financial growth, and growth portfolio in wireless, broadband, and adjacencies."},
            text, "Q1 marked a strong start", "Srini Gopalan",
            note="CEO explanation captured from official release quote."),
        "acquisition_debt_notes": official_claim(
            ticker, "acquisition_debt_notes", "official_captured",
            {"q1_stockholder_returns_billion": 6.0, "q1_repurchases_billion": 4.9, "q1_cash_dividends_billion": 1.1, "current_2026_return_authorization_billion": 18.2, "authorization_increase_billion": 3.6, "operating_cash_flow_billion": 7.2, "adjusted_free_cash_flow_billion": 4.6},
            text, "Stockholder Returns", "common stock repurchases",
            note="Official release captures stockholder returns, repurchases, dividends, authorization increase, and cash flow."),
    }


def lng_captures(text: str) -> dict[str, Any]:
    ticker = "LNG"
    return {
        "adjusted_eps": official_claim(ticker, "adjusted_eps", "not_disclosed_in_release", {"gaap_net_loss_billion": -3.50, "adjusted_net_income_disclosed": True, "note": "Release presents net loss and non-GAAP adjusted net income reconciliation but not adjusted EPS."}, text, "Adjusted Net Income", "Net Income (Loss)", note="Adjusted EPS is not disclosed in the official release."),
        "guidance": official_claim(ticker, "guidance", "official_captured", {"fy2026_consolidated_adjusted_ebitda_previous_range_billion": [6.75, 7.25], "fy2026_consolidated_adjusted_ebitda_revised_range_billion": [7.25, 7.75], "fy2026_distributable_cash_flow_previous_range_billion": [4.35, 4.85], "fy2026_distributable_cash_flow_revised_range_billion": [4.75, 5.25], "guidance_change": "raised full year 2026 financial guidance"}, text, "2026 FULL YEAR FINANCIAL GUIDANCE", "Raising full year 2026", note="Official release raises full-year adjusted EBITDA and distributable cash flow guidance."),
        "growth_bridge": official_claim(ticker, "growth_bridge", "official_captured", {"revenues_billion": 5.87, "revenue_growth_pct": 8, "consolidated_adjusted_ebitda_billion": 2.33, "adjusted_ebitda_growth_pct": 25, "distributable_cash_flow_billion": 1.67, "lng_cargoes": 187, "cargo_growth_pct": 11, "lng_volumes_tbtu": 688, "volume_growth_pct": 13}, text, "SUMMARY AND REVIEW OF FINANCIAL RESULTS", "LNG exported", note="Official release quantifies revenue, adjusted EBITDA, DCF, cargo and volume growth."),
        "segment_margins": official_claim(ticker, "segment_margins", "partial", {"consolidated_adjusted_ebitda_billion": 2.33, "distributable_cash_flow_billion": 1.67, "note": "Release provides consolidated adjusted EBITDA/DCF, not segment margin percentages."}, text, "Consolidated Adjusted EBITDA", "Distributable Cash Flow", note="Company-level profitability captured; segment margins not disclosed."),
        "orders_backlog": official_claim(ticker, "orders_backlog", "partial", {"lng_cargoes": 187, "lng_volumes_tbtu": 688, "train_6_first_lng_expected": "imminently", "note": "Official release captures production/export volumes and project milestones; no numeric orders/backlog disclosed."}, text, "Growth / Operations", "First LNG production", note="Energy infrastructure demand captured through cargo/volume and project milestones, not backlog."),
        "management_explanation": official_claim(ticker, "management_explanation", "official_captured", {"summary": "Management cited safety, operational excellence, higher LNG production forecast, higher market margins, optimization activities, and need for reliable LNG capacity."}, text, "CEO COMMENT", "Jack Fusco", note="CEO explanation captured from official release."),
        "acquisition_debt_notes": official_claim(ticker, "acquisition_debt_notes", "official_captured", {"capital_allocation_deployed_billion": 1.2, "shares_repurchased_million": 2.7, "repurchases_million": 537, "quarterly_dividend_per_share": 0.555, "dividends_million": 117, "long_term_debt_repaid_million": 253, "growth_capital_invested_billion": 1.0, "equity_funded_growth_capital_million": 301, "ratings_upgrade": "Moody's upgraded Cheniere/CCH notes to Baa2/Baa1 stable"}, text, "Capital Allocation", "Moody", note="Official release captures repurchases, dividend, debt repayment, growth capital and ratings upgrade."),
    }


def lin_captures(text: str) -> dict[str, Any]:
    ticker = "LIN"
    return {
        "adjusted_eps": official_claim(ticker, "adjusted_eps", "official_captured", {"gaap_eps": 3.98, "adjusted_eps": 4.33, "gaap_eps_growth_pct": 13, "adjusted_eps_growth_pct": 10}, text, "adjusted EPS $4.33", "EPS $3.98", note="Official release reports GAAP and adjusted EPS."),
        "guidance": official_claim(ticker, "guidance", "official_captured", {"q2_2026_adjusted_eps_range": [4.40, 4.50], "q2_2026_adjusted_eps_growth_range_pct": [8, 10], "fy2026_adjusted_eps_range": [17.60, 17.90], "fy2026_adjusted_eps_growth_range_pct": [7, 9], "fy2026_capex_range_billion": [5.0, 5.5]}, text, "For the second quarter of 2026", "For the full year 2026", note="Official release gives Q2 and FY26 adjusted EPS guidance and capex range."),
        "growth_bridge": official_claim(ticker, "growth_bridge", "official_captured", {"sales_billion": 8.781, "sales_growth_pct": 8, "underlying_sales_growth_pct": 3, "price_attainment_pct": 2, "volume_growth_pct": 1, "currency_benefit_pct": 5, "acquisition_sales_growth_pct": 1, "adjusted_operating_profit_billion": 2.630, "adjusted_operating_profit_growth_pct": 8}, text, "underlying sales increased", "price attainment", note="Official release quantifies sales growth bridge through price, volume, FX and acquisitions."),
        "segment_margins": official_claim(ticker, "segment_margins", "official_captured", {"company_operating_margin_pct": 27.8, "company_adjusted_operating_margin_pct": 30.0, "americas_operating_margin_pct": 31.6, "apac_operating_margin_pct": 28.0, "adjusted_ebitda_margin_pct": 39.3}, text, "First-Quarter 2026 Results by Segment", "Adjusted EBITDA as a % of Sales", note="Official release provides company and segment operating margin disclosures."),
        "orders_backlog": official_claim(ticker, "orders_backlog", "partial", {"contractual_sale_of_gas_project_backlog_billion": 7.1, "note": "Release gives project backlog but not order/book-to-bill metrics."}, text, "contractual sale of gas project backlog", "project backlog", note="Project backlog captured; order/book-to-bill not disclosed."),
        "management_explanation": official_claim(ticker, "management_explanation", "official_captured", {"summary": "Management cited 10% EPS growth, 30% operating margin, 24% return on capital, resilient operating model, capital allocation discipline, and management actions."}, text, "Commenting on the financial results", "Sanjiv Lamba", note="CEO explanation captured from official release quote."),
        "acquisition_debt_notes": official_claim(ticker, "acquisition_debt_notes", "official_captured", {"operating_cash_flow_billion": 2.240, "capex_billion": 1.342, "free_cash_flow_million": 898, "shareholder_returns_billion": 1.545, "short_term_debt_billion": 4.822, "current_long_term_debt_billion": 1.636, "long_term_debt_billion": 19.859}, text, "operating cash flow", "Short-term debt", note="Official release captures cash flow, capex/free cash flow, shareholder returns and debt balances."),
    }


def ecl_captures(text: str) -> dict[str, Any]:
    ticker = "ECL"
    return {
        "adjusted_eps": official_claim(ticker, "adjusted_eps", "official_captured", {"reported_diluted_eps": 1.52, "adjusted_diluted_eps": 1.70, "reported_eps_growth_pct": 8, "adjusted_eps_growth_pct": 13}, text, "ADJUSTED DILUTED EPS $1.70", "Reported diluted EPS", note="Official release reports reported and adjusted diluted EPS."),
        "guidance": official_claim(ticker, "guidance", "official_captured", {"fy2026_adjusted_eps_range": [8.43, 8.63], "fy2026_adjusted_eps_growth_range_pct": [12, 15], "q2_2026_adjusted_eps_range": [2.02, 2.12], "coolit_excluded_from_outlook": True}, text, "MAINTAINS 2026 OUTLOOK", "2Q 2026", note="Official release maintains FY26 adjusted EPS outlook and gives Q2 range."),
        "growth_bridge": official_claim(ticker, "growth_bridge", "official_captured", {"reported_sales_billion": 4.1, "reported_sales_growth_pct": 10, "organic_sales_growth_pct": 4, "growth_drivers": ["Life Sciences", "Global High-Tech", "Institutional and Specialty", "Pest Elimination", "Food & Beverage", "value pricing", "volume growth"]}, text, "Reported sales $4.1 billion", "Organic sales accelerated", note="Official release describes reported/organic sales growth and drivers."),
        "segment_margins": official_claim(ticker, "segment_margins", "official_captured", {"reported_operating_income_margin_pct": 15.3, "adjusted_operating_income_margin_pct": 16.7, "global_water_operating_margin_pct": 14.6, "global_water_organic_operating_margin_pct": 14.3}, text, "First Quarter 2026 Segment Review", "Adjusted operating income margin", note="Official release gives consolidated adjusted margin and segment review margins."),
        "orders_backlog": official_claim(ticker, "orders_backlog", "partial", {"record_new_business_wins": True, "numeric_orders_or_backlog": None, "note": "Release mentions record new business wins but no numeric orders/backlog."}, text, "record new business wins", "new business wins", note="Official release provides qualitative new-business signal, not numeric backlog."),
        "management_explanation": official_claim(ticker, "management_explanation", "official_captured", {"summary": "Management cited strong value pricing, accelerated volume growth, improved productivity, growth engines, Life Sciences, Global High-Tech, data-center cooling and CoolIT strategic fit."}, text, "CEO Comment", "Christophe Beck", note="CEO explanation captured from official release quote."),
        "acquisition_debt_notes": official_claim(ticker, "acquisition_debt_notes", "partial", {"pending_coolit_acquisition": True, "ovivo_electronics_debt_funding_mentioned": True, "interest_expense_headwind_per_share": 0.05, "shares_repurchased_million": 1.3, "note": "Acquisition/debt impact and repurchases captured; full balance-sheet debt amount not extracted from this release."}, text, "CoolIT", "Ovivo Electronics", "repurchased", note="Official release captures pending CoolIT deal, Ovivo debt-funding impact, and repurchases."),
    }


def vmc_captures(text: str) -> dict[str, Any]:
    ticker = "VMC"
    return {
        "adjusted_eps": official_claim(ticker, "adjusted_eps", "official_captured", {"gaap_diluted_eps": 1.27, "adjusted_diluted_eps": 1.35, "ttm_gaap_diluted_eps": 8.45, "ttm_adjusted_diluted_eps": 8.34}, text, "Adjusted earnings attributable", "Earnings attributable", note="Official release reports GAAP and adjusted diluted EPS."),
        "guidance": official_claim(ticker, "guidance", "official_captured", {"fy_adjusted_ebitda_range_billion": [2.4, 2.6], "guidance_status": "reaffirmed full-year earnings outlook"}, text, "Company Reaffirms Full Year Earnings Outlook", "between $2.4 and $2.6 billion", note="Official release reaffirms full-year adjusted EBITDA outlook."),
        "growth_bridge": official_claim(ticker, "growth_bridge", "official_captured", {"total_revenues_million": 1756, "prior_year_revenues_million": 1635, "gross_profit_million": 423, "prior_year_gross_profit_million": 365, "adjusted_ebitda_million": 447, "adjusted_ebitda_growth_pct": 9, "aggregates_shipments_million_tons": 50.0, "aggregates_price_per_ton": 22.80, "aggregates_gross_profit_per_ton": 8.01}, text, "Financial Highlights Include", "Aggregates segment Shipments", note="Official release quantifies revenue, EBITDA and aggregates price/shipments bridge."),
        "segment_margins": official_claim(ticker, "segment_margins", "official_captured", {"adjusted_ebitda_margin_pct": 25.5, "ttm_adjusted_ebitda_margin_pct": 29.3, "sag_as_pct_revenue": 7.7, "aggregates_gross_profit_per_ton": 8.01, "aggregates_cash_gross_profit_per_ton": 10.93}, text, "Adjusted EBITDA Margin", "Aggregates Segment gross profit", note="Official release gives adjusted EBITDA margin and aggregates unit margin/profit metrics."),
        "orders_backlog": official_claim(ticker, "orders_backlog", "partial", {"healthy_backlog_supported_by": ["large projects", "public construction activity"], "numeric_backlog": None}, text, "healthy backlog", "large projects", note="Release cites healthy backlog but does not quantify backlog."),
        "management_explanation": official_claim(ticker, "management_explanation", "official_captured", {"summary": "Management cited advantaged aggregates-led business, strategic disciplines, execution, innovation/technology, margin expansion, cash generation, healthy backlog, and public construction activity."}, text, "Ronnie Pruitt", "Chief Executive Officer", note="CEO explanation captured from official release quotes."),
        "acquisition_debt_notes": official_claim(ticker, "acquisition_debt_notes", "official_captured", {"debt_to_ttm_adjusted_ebitda": 1.9, "target_leverage_range": [2.0, 2.5], "roic_pct": 16.0, "capex_million": 90, "shareholder_returns_million": 217, "repurchases_million": 149, "dividends_million": 68}, text, "Financial Position, Liquidity and Capital Allocation", "total debt", note="Official release captures leverage, ROIC, capex and shareholder returns."),
    }


def wmb_captures(text: str) -> dict[str, Any]:
    ticker = "WMB"
    return {
        "adjusted_eps": official_claim(ticker, "adjusted_eps", "official_captured", {"gaap_eps": 0.70, "adjusted_eps": 0.73, "prior_year_gaap_eps": 0.56, "prior_year_adjusted_eps": 0.60, "adjusted_eps_growth_pct": 22}, text, "Adjusted Earnings Per Share", "Net Income Per Share", note="Official release reports GAAP and adjusted EPS."),
        "guidance": official_claim(ticker, "guidance", "official_captured", {"adjusted_ebitda_guidance_position": "upper half of 2026 guidance range", "dividend_coverage_ratio": 2.76}, text, "upper half of 2026 guidance range", "Dividend coverage ratio", note="Official release states Williams is on track for upper half of 2026 adjusted EBITDA guidance range."),
        "growth_bridge": official_claim(ticker, "growth_bridge", "official_captured", {"gaap_net_income_million": 864, "gaap_net_income_growth_pct": 25, "adjusted_ebitda_billion": 2.254, "adjusted_ebitda_growth_pct": 13, "cffo_billion": 1.603, "cffo_growth_pct": 12, "affo_billion": 1.770, "affo_growth_pct": 22, "drivers": ["Transco expansion projects", "new Gulf volumes", "higher storage revenues", "higher gathering volumes in the West"]}, text, "First-quarter GAAP net income", "Adjusted EBITDA grew", note="Official release quantifies income/EBITDA/cash-flow growth and drivers."),
        "segment_margins": official_claim(ticker, "segment_margins", "partial", {"transmission_power_gulf_adjusted_ebitda_million": 1010, "northeast_gp_adjusted_ebitda_million": 524, "west_adjusted_ebitda_million": 410, "gas_ngl_marketing_services_adjusted_ebitda_million": 227, "total_adjusted_ebitda_million": 2254, "note": "Segment EBITDA captured; margin percentages not disclosed."}, text, "Business Segment Results", "Adjusted EBITDA", note="Official release provides segment adjusted EBITDA, not segment margin percentages."),
        "orders_backlog": official_claim(ticker, "orders_backlog", "official_captured", {"neo_project_billion": 2.3, "neo_installed_capacity_mw": 682, "atlas_capacity_mmcfd": 164, "silver_spur_expansion_mmcfd": 275, "gathering_expansions_mmcfd_approx": 700, "power_express_capacity_mmcfd": 750}, text, "Disciplined execution drives business growth", "Signed customer agreement on Neo", note="Official release captures contracted project/customer agreements and capacity additions."),
        "management_explanation": official_claim(ticker, "management_explanation", "official_captured", {"summary": "Management cited natural-gas focused strategy, premier assets, Transco expansion projects, new Gulf volumes, higher storage revenues, West gathering volumes, and power innovation projects."}, text, "CEO Perspective", "Chad Zamarin", note="CEO explanation captured from official release quote."),
        "acquisition_debt_notes": official_claim(ticker, "acquisition_debt_notes", "official_captured", {"debt_to_adjusted_ebitda": 3.61, "capital_investments_excluding_acquisitions_billion": 1.642, "closed_south_mansfield_sale": True, "cash_purchases_reimbursable_power_equipment_million": 439}, text, "Debt-to-Adjusted EBITDA", "Capital Investments", "Closed on sale", note="Official release captures leverage, capital investments and portfolio optimization/sale note."),
    }


HARDENED_CAPTURE_BUILDERS = {
    "BKNG": bkng_captures,
    "NFLX": nflx_captures,
    "CME": cme_captures,
    "KTOS": ktos_captures,
    "SMCI": smci_captures,
    "TMUS": tmus_captures,
    "LNG": lng_captures,
    "LIN": lin_captures,
    "ECL": ecl_captures,
    "VMC": vmc_captures,
    "WMB": wmb_captures,
}


def validate_capture_contract(ticker: str, captures: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_CAPTURE_FIELDS - set(captures))
    extra = sorted(set(captures) - REQUIRED_CAPTURE_FIELDS)
    if missing or extra:
        raise ValueError(f"{ticker} capture fields mismatch; missing={missing}; extra={extra}")
    manual = sorted(field for field, block in captures.items() if block.get("status") == "manual_required")
    if ticker in HARDENED_CAPTURE_BUILDERS and manual:
        raise ValueError(f"{ticker} hardened capture still has manual_required fields: {manual}")


def build_captures(ticker: str, text: str) -> dict[str, Any]:
    builder = HARDENED_CAPTURE_BUILDERS.get(ticker)
    captures = builder(text) if builder else manual_capture(ticker, text)
    validate_capture_contract(ticker, captures)
    return captures


def self_check() -> dict[str, Any]:
    missing_builders = sorted(set(SOURCES) - set(HARDENED_CAPTURE_BUILDERS))
    builder_without_source = sorted(set(HARDENED_CAPTURE_BUILDERS) - set(SOURCES))
    sample_text = " ".join(needle for needles in NEEDLES.values() for needle in needles)
    ticker_checks = []
    for ticker in sorted(SOURCES):
        captures = build_captures(ticker, sample_text)
        ticker_checks.append({
            "ticker": ticker,
            "fields": len(captures),
            "manual_required_remaining": sum(1 for block in captures.values() if block.get("status") == "manual_required"),
        })
    status = "ok" if not missing_builders and not builder_without_source and all(row["manual_required_remaining"] == 0 for row in ticker_checks) else "warning"
    return {
        "status": status,
        "sources": len(SOURCES),
        "hardened_builders": len(HARDENED_CAPTURE_BUILDERS),
        "missing_builders": missing_builders,
        "builder_without_source": builder_without_source,
        "required_fields": sorted(REQUIRED_CAPTURE_FIELDS),
        "ticker_checks": ticker_checks,
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def build_capture(ticker: str, text: str, raw_html: str) -> dict[str, Any]:
    return build_capture_document(
        ticker=ticker,
        meta=SOURCES[ticker],
        captures=build_captures(ticker, text),
        text=text,
        raw_html=raw_html,
        summary_note=SUMMARY_NOTE,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture long-tail Q1 2026 official SEC/IR source coverage using WF70 common helper.")
    parser.add_argument("--ticker", choices=sorted(SOURCES), action="append", help="Ticker to capture. Repeatable. Defaults to all long-tail tickers.")
    parser.add_argument("--self-check", action="store_true", help="Run structural coverage checks without fetching sources.")
    args = parser.parse_args()
    if args.self_check:
        result = self_check()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "ok" else 1
    result = run_capture_batch(sources=SOURCES, selected_tickers=args.ticker, build_capture=build_capture)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
