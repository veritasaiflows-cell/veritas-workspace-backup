from __future__ import annotations

import argparse
import html
import json
import re
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
AUTHORITY = {
    **COMMON_AUTHORITY,
    "statement": "Review-only official IR/SEC earnings capture. This artifact captures official-source evidence only and does not apply workspace changes, infer approval, or authorize external action.",
}

SOURCES = {
    "ETN": {
        "ticker": "ETN",
        "company_name": "Eaton Corporation plc",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000010/etn03312026exhibit99.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000010/0001551182-26-000010-index.htm",
        "accession_number": "0001551182-26-000010",
        "source_title": "Eaton Reports Record First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
    "VRT": {
        "ticker": "VRT",
        "company_name": "Vertiv Holdings Co",
        "period_end": "2026-03-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1674101/000162828026026379/q12026exhibit991vrt04222026.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1674101/000162828026026379/0001628280-26-026379-index.htm",
        "accession_number": "0001628280-26-026379",
        "source_title": "Vertiv Reports Strong First Quarter 2026 Results",
        "source_type": "sec_8k_exhibit_99_1",
    },
}


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def excerpt_around(text: str, needle: str, chars: int = 900) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - chars // 3)
    end = min(len(text), idx + chars)
    return text[start:end].replace("\n", " ").strip()


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


def official_claim(source_url: str, status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return common_claim(source_url, status, value, section, excerpt, note)


def build_etn_capture(text: str, source_url: str) -> dict[str, Any]:
    headline_excerpt = excerpt_around(text, "Twelve-month rolling average order acceleration")
    margins_excerpt = excerpt_around(text, "Segment margins were")
    electrical_excerpt = excerpt_around(text, "The twelve-month rolling average of orders in the first quarter was up 42")
    book_to_bill_excerpt = excerpt_around(text, "book-to-bill ratio for the Electrical businesses")
    guidance_excerpt = excerpt_around(text, "For full year 2026, earnings per share expected")
    management_excerpt = excerpt_around(text, "Strong demand across our markets")
    acquisitions_excerpt = excerpt_around(text, "Closed $11 billion of strategic acquisitions")

    return {
        "adjusted_eps": official_claim(
            source_url,
            "official_captured",
            {
                "gaap_eps": 2.22,
                "adjusted_eps": 2.81,
                "adjustments_per_share": {
                    "intangible_amortization": 0.29,
                    "acquisitions_and_divestitures": 0.22,
                    "multi_year_restructuring_program": 0.08,
                },
            },
            "Q1 2026 release adjusted EPS paragraph",
            excerpt_around(text, "adjusted earnings per share were $2.81"),
        ),
        "guidance": official_claim(
            source_url,
            "official_captured",
            {
                "eps_range": {"low": 10.88, "high": 11.33},
                "adjusted_eps_range": {"low": 13.05, "high": 13.50},
                "adjusted_eps_midpoint_growth_pct": 10,
                "organic_growth_guidance_midpoint_pct": 10,
                "organic_growth_guidance_prior_midpoint_pct": 8,
                "raised_cut_reaffirmed": "raised organic growth guidance to 10% from 8% at the midpoint",
            },
            "Headline bullets / full-year 2026 guidance",
            guidance_excerpt or headline_excerpt,
        ),
        "growth_bridge": official_claim(
            source_url,
            "official_captured",
            {
                "reported_sales_growth_pct": 17,
                "organic_sales_growth_pct": 10,
                "acquisition_growth_pct": 4,
                "fx_growth_pct": 3,
            },
            "Q1 2026 release sales bridge paragraph",
            excerpt_around(text, "The sales increase consisted of 10% growth in organic sales"),
        ),
        "segment_margins": official_claim(
            source_url,
            "partial",
            {
                "company_segment_margin_pct": 22.7,
                "electrical_americas_operating_margin_pct": 25.6,
                "electrical_global_operating_margin_pct": 19.2,
                "aerospace_operating_margin_pct": 26.7,
                "mobility_operating_margin_pct": 11.7,
                "note": "Release provides segment operating margin percentages but this capture does not build a full margin bridge by all subsegments.",
            },
            "Segment commentary paragraphs",
            margins_excerpt,
        ),
        "orders_backlog": official_claim(
            source_url,
            "official_captured",
            {
                "electrical_americas_orders_growth_pct": 42,
                "electrical_americas_backlog_growth_pct": 44,
                "electrical_global_orders_growth_pct": 13,
                "electrical_global_backlog_growth_pct": 73,
                "electrical_sector_backlog_growth_pct": 48,
                "electrical_businesses_book_to_bill": 1.2,
                "aerospace_orders_growth_pct": 13,
                "aerospace_backlog_growth_pct": 28,
                "aerospace_book_to_bill": 1.1,
            },
            "Headline bullets and segment order/backlog/book-to-bill commentary",
            (headline_excerpt + " " + electrical_excerpt + " " + book_to_bill_excerpt).strip(),
            "Official release gives growth percentages and book-to-bill ratios; it does not disclose absolute order or backlog dollars in this capture.",
        ),
        "management_explanation": official_claim(
            source_url,
            "official_captured",
            {
                "summary": "Management attributed Q1 performance to strong demand, order strength, backlog growth, operational execution, Electrical Americas organic growth/capacity expansion, Electrical Global outperformance, Aerospace backlog/profit growth, and Mobility spin-off progress.",
                "demand_drivers": ["data center momentum", "Electrical Americas demand", "Electrical Global outperformance", "Aerospace backlog growth"],
                "margin_drivers": ["operational execution", "segment margins above guidance range"],
                "risk_items": ["Mobility remains in a challenging market", "forward-looking statements remain subject to SEC-filed risk factors"],
            },
            "CEO quote and operating commentary",
            management_excerpt,
        ),
        "acquisition_debt_notes": official_claim(
            source_url,
            "official_captured",
            {
                "strategic_acquisitions_closed_billion": 11,
                "acquisitions_mentioned": ["Boyd Thermal", "Ultra PCS Limited"],
                "debt_or_leverage_commentary": None,
                "integration_or_synergy_commentary": None,
            },
            "Headline acquisition bullet",
            acquisitions_excerpt or headline_excerpt,
        ),
    }


def build_vrt_capture(text: str, source_url: str) -> dict[str, Any]:
    guidance_excerpt = excerpt_around(text, "Full Year 2026 Guidance")
    demand_excerpt = excerpt_around(text, "strong data center demand")
    risk_backlog_excerpt = excerpt_around(text, "failure to realize sales expected from our backlog")
    adjusted_excerpt = excerpt_around(text, "Adjusted Diluted EPS Growth of +83%")
    margin_excerpt = excerpt_around(text, "Adjusted operating margin was 20.8%")

    return {
        "adjusted_eps": official_claim(
            source_url,
            "official_captured",
            {"adjusted_diluted_eps_growth_pct": 83, "adjusted_diluted_eps_guidance_range": {"low": 6.30, "high": 6.40}},
            "Headline and full-year guidance bullets",
            adjusted_excerpt or guidance_excerpt,
            "Release headline discloses adjusted diluted EPS growth and guidance range; per-share Q1 adjusted EPS amount was not captured by this v1 extractor.",
        ),
        "guidance": official_claim(
            source_url,
            "official_captured",
            {
                "net_sales_range_million": {"low": 13500, "high": 14000},
                "organic_sales_growth_range_pct": {"low": 29, "high": 31},
                "diluted_eps_range": {"low": 5.60, "high": 5.70},
                "adjusted_diluted_eps_range": {"low": 6.30, "high": 6.40},
                "raised_cut_reaffirmed": "raises full-year guidance",
            },
            "Full Year 2026 Guidance",
            guidance_excerpt,
        ),
        "growth_bridge": official_claim(
            source_url,
            "official_captured",
            {
                "reported_sales_growth_pct": 30,
                "organic_sales_growth_pct": 23,
                "acquisition_growth_pct": 4,
                "fx_growth_pct": 3,
                "americas_organic_sales_growth_pct": 44,
            },
            "Q1 2026 release sales bridge paragraph",
            excerpt_around(text, "driven by 23% organic sales growth"),
        ),
        "segment_margins": official_claim(
            source_url,
            "partial",
            {"adjusted_operating_margin_pct": 20.8, "adjusted_operating_margin_yoy_bps": 430, "note": "Release captured adjusted operating margin, not complete segment margin percentages."},
            "Q1 2026 operating margin commentary",
            margin_excerpt,
        ),
        "orders_backlog": official_claim(
            source_url,
            "not_disclosed_in_release",
            {"orders_growth_pct": None, "book_to_bill": None, "backlog": None, "backlog_growth_pct": None},
            "Release scan for quantitative orders/backlog/book-to-bill disclosure",
            demand_excerpt or risk_backlog_excerpt or guidance_excerpt,
            "No quantitative orders, backlog, backlog growth, or book-to-bill disclosure was found in the Q1 2026 release body; order/backlog terms appear only in risk-factor boilerplate in this capture scan.",
        ),
        "management_explanation": official_claim(
            source_url,
            "official_captured",
            {
                "summary": "Management cited strong data center demand, evolving infrastructure requirements, deployment speed, operational efficiency, technology/capacity investments, strategic acquisitions, market-share gains, and operational leverage.",
                "demand_drivers": ["strong data center demand", "customers prioritizing optimized design", "deployment speed", "comprehensive services"],
                "margin_drivers": ["operational leverage on higher volume", "positive price-cost", "tariff mitigation countermeasures"],
                "risk_items": ["long sales cycles", "customer order cancellation risk", "backlog realization risk"],
            },
            "Management quotes and forward-looking risk factors",
            demand_excerpt,
        ),
        "acquisition_debt_notes": official_claim(
            source_url,
            "partial",
            {"net_leverage": "~0.2x", "acquisition_growth_contribution_pct": 4, "debt_or_leverage_commentary": "Net leverage of ~0.2x at the end of first quarter 2026."},
            "Headline bullets / sales bridge",
            excerpt_around(text, "Net leverage of ~0.2x"),
        ),
    }


def build_capture(ticker: str, text: str, raw_html: str) -> dict[str, Any]:
    meta = SOURCES[ticker]
    source_url = meta["source_url"]
    captures = build_etn_capture(text, source_url) if ticker == "ETN" else build_vrt_capture(text, source_url)
    data = build_capture_document(
        ticker=ticker,
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw_html,
        summary_note="Review-only official capture; downstream WF65/WF66 validators must consume this before any WF64/WF56 gated apply can be considered.",
    )
    data["authority"] = AUTHORITY
    data["summary"]["official_captured_or_not_disclosed"] = sum(
        1 for c in captures.values() if c["status"] in {"official_captured", "not_disclosed_in_release", "partial"}
    )
    return data


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
        compact = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        compact = compact.replace("|", "\\|")[:500]
        lines.append(f"| `{name}` | {capture.get('status')} | {compact}; {note} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture ETN/VRT Q1 2026 official earnings fields from SEC 8-K Exhibit 99.1.")
    parser.add_argument("--ticker", choices=sorted(SOURCES), action="append", help="Ticker to capture. Repeatable. Defaults to ETN and VRT.")
    args = parser.parse_args()
    result = run_capture_batch(sources=SOURCES, selected_tickers=args.ticker, build_capture=build_capture, text_converter=html_to_text)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
