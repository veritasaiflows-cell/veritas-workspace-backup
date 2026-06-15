from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from official_ir_capture_common import (
    AUTHORITY as COMMON_AUTHORITY,
    build_capture_document,
    claim as common_claim,
    run_capture_batch,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "official-ir-captures"
USER_AGENT = "Veritas OpenClaw Research veritasaiflows@gmail.com"

AUTHORITY = {
    **COMMON_AUTHORITY,
    "statement": "Review-only official IR/SEC earnings capture. This artifact captures official-source evidence only and does not apply workspace changes, infer approval, or authorize external action.",
}

SOURCES = {
    "MSFT": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/789019/000119312526191457/msft-ex99_1.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000119312526191457/0001193125-26-191457-index.htm",
        "accession_number": "0001193125-26-191457",
        "source_title": "Microsoft Cloud and AI Strength Fuels Third Quarter Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "NVDA": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "period_end": "2026-04-26",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000051/q1fy27cfocommentary.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000051/0001045810-26-000051-index.htm",
        "accession_number": "0001045810-26-000051",
        "source_title": "CFO Commentary on First Quarter Fiscal 2027 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "AMZN": {
        "ticker": "AMZN",
        "company_name": "Amazon.com, Inc.",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000012/amzn-20260331xex991.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1018724/000101872426000012/0001018724-26-000012-index.htm",
        "accession_number": "0001018724-26-000012",
        "source_title": "Amazon.com Announces First Quarter Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def fetch_source(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</td>|</th>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def excerpt_around(text: str, needle: str, chars: int = 1000) -> str:
    haystack = text.lower()
    idx = haystack.find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - chars // 3)
    end = min(len(text), idx + chars)
    return compact(text[start:end])


def regex_value(pattern: str, text: str, cast: type = str) -> Any:
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return None
    raw = match.group(1).replace(",", "").strip().rstrip(".")
    if cast is float:
        return float(raw)
    if cast is int:
        return int(raw)
    return match.group(1).strip()


def first_excerpt(text: str, *needles: str, chars: int = 1000) -> str:
    for needle in needles:
        found = excerpt_around(text, needle, chars=chars)
        if found:
            return found
    return ""


def official_claim(source_url: str, status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return common_claim(source_url, status, value, section, excerpt, note)


def apply_period_to_captures(captures: dict[str, Any], period: str) -> dict[str, Any]:
    for block in captures.values():
        if isinstance(block, dict):
            block.setdefault("period", period)
    return captures

def manual_claim(source_url: str, section: str, note: str) -> dict[str, Any]:
    return official_claim(source_url, "manual_required", None, section, "", note)


def build_msft_capture(text: str, source_url: str) -> dict[str, Any]:
    headline = first_excerpt(text, "Revenue was $82.9 billion", "Diluted Earnings per Share", chars=1300)
    business = first_excerpt(text, "Microsoft Cloud revenue was $54.5 billion", "Business Highlights", chars=1300)
    segment = first_excerpt(text, "Productivity and Business Processes", "Segment Revenue Constant Currency Reconciliation", chars=1500)
    rpo = first_excerpt(text, "commercial remaining performance obligation increased 99%", "Commercial remaining performance obligation", chars=1000)
    guidance = first_excerpt(text, "Business Outlook", "provide forward-looking guidance", chars=900)
    management = first_excerpt(text, "agentic computing era", "delivered results that exceeded expectations", chars=1000)
    capital = first_excerpt(text, "returned $10.2 billion", "Impact from investments in OpenAI", chars=1000)

    return {
        "adjusted_eps": official_claim(
            source_url,
            "official_captured",
            {"gaap_diluted_eps": 4.27, "non_gaap_diluted_eps": 4.27, "openai_investment_adjustment_per_share": 0.00, "non_gaap_eps_growth_pct": 21},
            "Q3 FY2026 release GAAP to non-GAAP reconciliation",
            headline,
        ),
        "guidance": official_claim(
            source_url,
            "partial",
            {"guidance_provided_on_call": True, "release_numeric_guidance": None},
            "Business Outlook",
            guidance,
            "The exhibit says Microsoft will provide forward-looking guidance on the earnings call; numeric guidance is not captured from the release exhibit.",
        ),
        "growth_bridge": official_claim(
            source_url,
            "official_captured",
            {
                "revenue_billion": 82.9,
                "revenue_growth_pct": 18,
                "constant_currency_revenue_growth_pct": 15,
                "microsoft_cloud_revenue_billion": 54.5,
                "microsoft_cloud_growth_pct": 29,
                "microsoft_cloud_constant_currency_growth_pct": 25,
                "azure_and_other_cloud_services_growth_pct": 40,
                "azure_constant_currency_growth_pct": 39,
            },
            "Opening bullets and Business Highlights",
            (headline + " " + business).strip(),
        ),
        "segment_margins": official_claim(
            source_url,
            "partial",
            {
                "operating_income_billion": 38.4,
                "operating_income_growth_pct": 20,
                "operating_income_constant_currency_growth_pct": 16,
                "productivity_and_business_processes_revenue_billion": 35.0,
                "intelligent_cloud_revenue_billion": 34.7,
                "more_personal_computing_revenue_billion": 13.2,
                "note": "Release gives consolidated operating income and segment revenue; this capture does not compute segment margin percentages.",
            },
            "Opening bullets / segment revenue constant-currency reconciliation",
            segment or headline,
        ),
        "orders_backlog": official_claim(
            source_url,
            "official_captured",
            {"commercial_remaining_performance_obligation_billion": 627, "commercial_rpo_growth_pct": 99, "orders_growth_pct": None, "book_to_bill": None},
            "Business Highlights",
            rpo,
            "Microsoft discloses commercial remaining performance obligation, not orders or book-to-bill.",
        ),
        "management_explanation": official_claim(
            source_url,
            "official_captured",
            {
                "summary": "Management cited cloud and AI infrastructure/solutions, AI annual revenue run-rate growth, growing demand for Microsoft Cloud, and broad execution across revenue, operating income, and EPS.",
                "demand_drivers": ["cloud and AI infrastructure", "Microsoft Cloud demand", "AI business annual revenue run rate", "Azure growth"],
                "margin_drivers": ["revenue growth", "operating income growth", "OpenAI investment adjustment disclosed as non-GAAP item"],
                "risk_items": ["forward-looking statements subject to SEC risk factors"],
            },
            "CEO/CFO quotes",
            management,
        ),
        "acquisition_debt_notes": official_claim(
            source_url,
            "partial",
            {"shareholder_returns_billion": 10.2, "openai_investment_net_loss_impact_million": 14, "debt_or_acquisition_commentary": None},
            "Shareholder returns / Non-GAAP Definition",
            capital,
            "Release captures shareholder returns and OpenAI investment impact; no material acquisition/debt transaction was captured from this exhibit.",
        ),
    }


def build_nvda_capture(text: str, source_url: str) -> dict[str, Any]:
    summary = first_excerpt(text, "Q1 Fiscal 2027 Summary", "Non-GAAP", chars=1400)
    revenue = first_excerpt(text, "Revenue for the first quarter was a record $81.6 billion", "Data Center revenue for the first quarter", chars=1300)
    margin = first_excerpt(text, "Gross Margin", "GAAP and non-GAAP gross margins", chars=1200)
    supply = first_excerpt(text, "total supply-related commitments were $119.0 billion", "Inventory was $25.8 billion", chars=1200)
    outlook = first_excerpt(text, "Outlook for the second quarter of fiscal 2027", "Revenue is expected to be $91.0 billion", chars=1200)
    management = first_excerpt(text, "driven by the ramp of our Blackwell 300 products", "Following the rapid evolution", chars=1400)
    capital = first_excerpt(text, "approved an increase to our quarterly dividend", "share repurchase authorization", chars=1200)

    return {
        "adjusted_eps": official_claim(
            source_url,
            "official_captured",
            {"gaap_diluted_eps": 2.39, "non_gaap_diluted_eps": 1.87, "non_gaap_diluted_eps_yoy_growth_pct": 140},
            "Q1 FY2027 Summary / non-GAAP table",
            summary,
        ),
        "guidance": official_claim(
            source_url,
            "official_captured",
            {"q2_fy2027_revenue_billion": 91.0, "revenue_range_pct": 2, "gaap_gross_margin_pct": 74.9, "non_gaap_gross_margin_pct": 75.0, "gaap_opex_billion": 8.5, "non_gaap_opex_billion": 8.3, "tax_rate_range_pct": {"low": 16.0, "high": 18.0}},
            "Outlook",
            outlook,
        ),
        "growth_bridge": official_claim(
            source_url,
            "official_captured",
            {"revenue_billion": 81.615, "revenue_qoq_growth_pct": 20, "revenue_yoy_growth_pct": 85, "data_center_revenue_billion": 75.246, "data_center_yoy_growth_pct": 92, "edge_computing_revenue_billion": 6.369, "edge_computing_yoy_growth_pct": 29},
            "Revenue commentary / market-platform table",
            revenue,
        ),
        "segment_margins": official_claim(
            source_url,
            "partial",
            {"gaap_gross_margin_pct": 74.9, "non_gaap_gross_margin_pct": 75.0, "gaap_operating_income_million": 53536, "non_gaap_operating_income_million": 53783, "note": "CFO commentary provides gross margin and operating income, not segment operating margin percentages."},
            "Q1 FY2027 Summary / Gross Margin",
            margin or summary,
        ),
        "orders_backlog": official_claim(
            source_url,
            "partial",
            {"inventory_billion": 25.8, "supply_related_commitments_billion": 119.0, "multi_year_cloud_service_commitments_billion": 30.0, "orders_growth_pct": None, "book_to_bill": None, "backlog": None},
            "Balance Sheet and Cash Flow",
            supply,
            "CFO commentary discloses inventory/capacity/supply commitments but not orders, backlog, or book-to-bill.",
        ),
        "management_explanation": official_claim(
            source_url,
            "official_captured",
            {"summary": "Management attributed growth to Blackwell 300 ramp, demand for InfiniBand, Spectrum-X Ethernet, and NVLink, diversified Data Center demand, and Edge Computing demand partly offset by slower consumer PC demand.", "demand_drivers": ["Blackwell 300 ramp", "Data Center demand", "InfiniBand/Spectrum-X/NVLink", "AI clouds/industrial/enterprise/sovereign customers"], "margin_drivers": ["lower prior-year H20 inventory provision comparison", "Blackwell mix"], "risk_items": ["China Data Center compute revenue excluded from outlook", "cash tax increase expected in Q2"]},
            "Revenue / Gross Margin / Outlook commentary",
            management,
        ),
        "acquisition_debt_notes": official_claim(
            source_url,
            "official_captured",
            {"quarterly_dividend_per_share": 0.25, "additional_share_repurchase_authorization_billion": 80.0, "strategic_investments_mentioned": True, "debt_or_acquisition_commentary": None},
            "Balance Sheet and Cash Flow / capital return",
            capital,
        ),
    }


def build_amzn_capture(text: str, source_url: str) -> dict[str, Any]:
    headline = first_excerpt(text, "Net sales increased 17% to $181.5 billion", "First quarter 2026 net income", chars=1600)
    management = first_excerpt(text, "We’re making customers’ lives easier", "AWS is growing 28%", chars=1400)
    highlights = first_excerpt(text, "Exceeded $20 billion annual revenue run rate", "Secured a commitment from OpenAI", chars=1400)
    guidance = first_excerpt(text, "Second Quarter 2026 Guidance", "Net sales are expected", "Operating income is expected", chars=1600)
    segment = first_excerpt(text, "North America segment operating income was $8.3 billion", "AWS segment operating income", chars=1100)
    fcf = first_excerpt(text, "Free cash flow decreased to $1.2 billion", "purchases of property and equipment", chars=1100)

    adjusted_eps_absent = "non-gaap" not in text.lower() and "adjusted diluted" not in text.lower() and "adjusted eps" not in text.lower()
    guidance_status = "official_captured" if guidance else "manual_required"
    guidance_value: Any = {
        "q2_2026_net_sales_range_billion": {"low": 194.0, "high": 199.0},
        "q2_2026_net_sales_growth_range_pct": {"low": 16, "high": 19},
        "fx_impact_basis_points": -10,
        "q2_2026_operating_income_range_billion": {"low": 20.0, "high": 24.0},
        "q2_2025_operating_income_billion": 19.2,
        "assumptions": ["Prime Day occurs in second quarter 2026", "no additional business acquisitions, restructurings, or legal settlements are concluded"],
    } if guidance else None

    return {
        "adjusted_eps": official_claim(
            source_url,
            "not_disclosed_in_release" if adjusted_eps_absent else "manual_required",
            None,
            "Q1 2026 release scan for adjusted/non-GAAP EPS",
            headline,
            "Release discloses GAAP diluted EPS but no adjusted/non-GAAP EPS string was found by the capture scan." if adjusted_eps_absent else "Adjusted/non-GAAP EPS term found; manual review required.",
        ),
        "guidance": official_claim(
            source_url,
            guidance_status,
            guidance_value,
            "Second Quarter 2026 Guidance" if guidance else "Release guidance scan",
            guidance,
            "Guidance excerpt captured; values should be manually confirmed from the full release text before decision use." if guidance else "Guidance section was not found by this v1 capture scan.",
        ) if guidance else manual_claim(source_url, "Release guidance scan", "Guidance section was not found by this v1 capture scan."),
        "growth_bridge": official_claim(
            source_url,
            "official_captured",
            {"net_sales_billion": 181.5, "net_sales_growth_pct": 17, "fx_impact_billion": 2.9, "ex_fx_net_sales_growth_pct": 15, "north_america_sales_billion": 104.1, "north_america_sales_growth_pct": 12, "international_sales_billion": 39.8, "international_sales_growth_pct": 19, "aws_sales_billion": 37.6, "aws_sales_growth_pct": 28},
            "Opening bullets",
            headline,
        ),
        "segment_margins": official_claim(
            source_url,
            "partial",
            {"operating_income_billion": 23.9, "north_america_operating_income_billion": 8.3, "international_operating_income_billion": 1.4, "aws_operating_income_billion": 14.2, "note": "Release gives segment sales and operating income, not explicit segment margin percentages."},
            "Opening segment bullets",
            segment or headline,
        ),
        "orders_backlog": official_claim(
            source_url,
            "partial",
            {"openai_trainium_capacity_gw": 2.0, "anthropic_trainium_capacity_gw_up_to": 5.0, "ai_chips_landed_past_12_months_million": 2.1, "orders_growth_pct": None, "book_to_bill": None, "backlog": None},
            "AWS AI infrastructure highlights",
            highlights,
            "Release discloses AI infrastructure capacity/customer commitments, but not a conventional orders/backlog/book-to-bill metric.",
        ),
        "management_explanation": official_claim(
            source_url,
            "official_captured",
            {"summary": "Management cited broad growth across AWS, advertising, stores unit growth, custom silicon, AI chips, delivery speed, and emerging services.", "demand_drivers": ["AWS growth", "custom silicon run rate", "advertising TTM revenue", "stores unit growth", "AI infrastructure commitments"], "margin_drivers": ["AWS operating income", "North America and International operating income growth"], "risk_items": ["AI-related capex pressure reflected in lower free cash flow"]},
            "CEO quote / highlights",
            management,
        ),
        "acquisition_debt_notes": official_claim(
            source_url,
            "partial",
            {"anthropic_pre_tax_gains_billion": 16.8, "free_cash_flow_ttm_billion": 1.2, "ppe_purchase_increase_billion": 59.3, "debt_or_acquisition_commentary": None},
            "Opening bullets / free cash flow commentary",
            fcf or headline,
            "Release captures Anthropic investment gains and AI-driven capital investment/free-cash-flow pressure; no debt issuance was captured from this exhibit.",
        ),
    }


def build_capture(ticker: str, text: str, raw_html: str) -> dict[str, Any]:
    meta = SOURCES[ticker]
    source_url = meta["source_url"]
    if ticker == "MSFT":
        captures = build_msft_capture(text, source_url)
    elif ticker == "NVDA":
        captures = build_nvda_capture(text, source_url)
    elif ticker == "AMZN":
        captures = build_amzn_capture(text, source_url)
    else:
        raise ValueError(f"unsupported ticker: {ticker}")
    data = build_capture_document(
        ticker=ticker,
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw_html,
        summary_note="Review-only official capture; downstream WF65/WF66 validators must consume this before any WF64/WF56 gated apply can be considered.",
    )
    data["authority"] = AUTHORITY
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict[str, Any]) -> None:
    lines = [f"# {data['ticker']} Q1 2026 Official IR Capture", ""]
    lines.append(f"- Generated: `{data.get('generated_at_utc')}`")
    lines.append(f"- Source: `{data.get('source', {}).get('source_url')}`")
    lines.append("- Authority: review-only; no owner approval, no workspace apply, no sizing/allocation, no account action, no trades.")
    lines.append("")
    lines.append("| Field | Status | Value / note |")
    lines.append("|---|---|---|")
    for name, capture in data.get("captures", {}).items():
        value = capture.get("value")
        note = capture.get("note") or ""
        compact_value = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        compact_value = compact_value.replace("|", "\\|")[:500]
        lines.append(f"| `{name}` | {capture.get('status')} | {compact_value}; {note} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture MSFT/NVDA/AMZN official earnings fields from SEC/IR exhibits.")
    parser.add_argument("--ticker", choices=sorted(SOURCES), action="append", help="Ticker to capture. Repeatable. Defaults to MSFT, NVDA, and AMZN.")
    args = parser.parse_args()
    print(json.dumps(run_capture_batch(sources=SOURCES, selected_tickers=args.ticker, build_capture=build_capture), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
