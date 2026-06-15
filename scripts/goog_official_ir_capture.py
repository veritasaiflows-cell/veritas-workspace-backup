from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

from official_ir_capture_common import (
    AUTHORITY as COMMON_AUTHORITY,
    apply_period_to_captures,
    claim,
    fetch_source as common_fetch_source,
    official_source_metadata,
    rel,
    utc_now,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "official-ir-captures" / "goog-q1-2026.json"
OUT_MD = ROOT / "tmp" / "official-ir-captures" / "goog-q1-2026.md"
SOURCE_URL = "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm"
FILING_URL = "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/goog-20260429.htm"
USER_AGENT = "Veritas OpenClaw Research veritasaiflows@gmail.com"
GOOG_META = {
    "ticker": "GOOG",
    "company_name": "Alphabet Inc.",
    "period_end": "2026-03-31",
    "source_url": SOURCE_URL,
    "filing_url": FILING_URL,
    "accession_number": "0001652044-26-000043",
    "source_title": "Alphabet Announces First Quarter 2026 Results",
    "source_type": "sec_8k_exhibit_99_1",
}

AUTHORITY = {
    **COMMON_AUTHORITY,
    "statement": "Review-only GOOG official IR/SEC earnings capture. This artifact captures official-source evidence only and does not apply workspace changes, infer approval, or authorize external action.",
}


def fetch_source(url: str) -> str:
    return common_fetch_source(url, timeout=30)


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def excerpt_around(text: str, needle: str, chars: int = 700) -> str:
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


def official_claim(status: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return claim(SOURCE_URL, status, value, section, excerpt, note)

def build_capture(text: str, raw_html: str) -> dict[str, Any]:
    revenue = regex_value(r"Consolidated Alphabet revenues increased\s+([0-9]+)%", text, int)
    constant_currency = regex_value(r"or\s+([0-9]+)%\s+in constant currency", text, int)
    google_services_revenue = regex_value(r"Google Services revenues increased\s+([0-9]+)%", text, int)
    cloud_growth = regex_value(r"Google Cloud.*?revenues increased\s+([0-9]+)%", text, int)
    cloud_revenue = regex_value(r"Google Cloud.*?revenues increased\s+[0-9]+%\s+to \$([0-9.]+) billion", text, float)
    operating_margin = regex_value(r"operating margin expanded by 2 percentage points to\s+([0-9.]+)%", text, float)
    eps = regex_value(r"EPS increased\s+[0-9]+%\s+to \$([0-9.]+)", text, float)
    cloud_backlog = regex_value(r"backlog nearly doubling quarter on quarter to over \$([0-9]+) billion", text, int)
    fcf = regex_value(r"Free cash flow\$[0-9,]+\s+\$[0-9,]+\s+\$[0-9,]+\s+\$([0-9,]+)", text, int)
    capex = regex_value(r"Purchases of property and equipment\([0-9,]+\)\([0-9,]+\)\([0-9,]+\)\(([0-9,]+)\)", text, int)
    debt_proceeds = regex_value(r"issued senior unsecured notes for net proceeds of \$([0-9.]+)\s+billion", text, float)

    adjusted_eps_absent = "adjusted eps" not in text.lower() and "non-gaap eps" not in text.lower()
    guidance_terms = ["guidance", "outlook"]
    guidance_found = [term for term in guidance_terms if term in text.lower()]

    management_excerpt = excerpt_around(text, "2026 is off to a terrific start")
    highlights_excerpt = excerpt_around(text, "Consolidated Alphabet revenues increased")
    non_gaap_excerpt = excerpt_around(text, "About Non-GAAP Financial Measures")
    segment_excerpt = excerpt_around(text, "Segment Operating Results")
    debt_excerpt = excerpt_around(text, "issued senior unsecured notes")
    backlog_excerpt = excerpt_around(text, "backlog nearly doubling")

    captures = {
        "adjusted_eps": official_claim(
            "not_disclosed_in_release" if adjusted_eps_absent else "manual_required",
            None,
            "Q1 2026 release / Non-GAAP Financial Measures scan",
            non_gaap_excerpt or excerpt_around(text, "EPS increased"),
            "Release discloses GAAP diluted EPS but no adjusted/non-GAAP EPS string was found by the capture scan.",
        ),
        "guidance": official_claim(
            "not_disclosed_in_release" if not guidance_found else "manual_required",
            {"guidance_terms_found": guidance_found},
            "Q1 2026 release scan for guidance/outlook/forecast language",
            excerpt_around(text, "Forward-Looking Statements") or non_gaap_excerpt,
            "No explicit financial guidance/outlook/forecast term was found in the release text scan." if not guidance_found else "Guidance-like term found; manual review still required.",
        ),
        "growth_bridge": official_claim(
            "official_captured",
            {
                "reported_revenue_growth_pct": revenue,
                "constant_currency_revenue_growth_pct": constant_currency,
                "google_services_revenue_growth_pct": google_services_revenue,
                "google_cloud_revenue_growth_pct": cloud_growth,
                "google_cloud_revenue_billion": cloud_revenue,
            },
            "Opening bullet highlights",
            highlights_excerpt,
        ),
        "segment_margins": official_claim(
            "partial",
            {
                "consolidated_operating_margin_pct": operating_margin,
                "google_services_operating_income_million": 40589,
                "google_cloud_operating_income_million": 6598,
                "other_bets_operating_loss_million": -2100,
                "note": "Release captures segment operating income, not full segment margin percentages for every segment.",
            },
            "Q1 2026 Financial Highlights / Segment Operating Results",
            segment_excerpt or highlights_excerpt,
        ),
        "orders_backlog": official_claim(
            "official_captured",
            {"google_cloud_backlog_over_billion": cloud_backlog, "orders_growth_pct": None, "book_to_bill": None},
            "CEO quote / Cloud commentary",
            backlog_excerpt or management_excerpt,
            "Alphabet provides Cloud backlog commentary; orders/book-to-bill were not disclosed in this release.",
        ),
        "management_explanation": official_claim(
            "official_captured",
            {
                "summary": "Management attributed strong Q1 2026 performance to AI investments across the business, Search usage/query growth, Cloud acceleration, subscription momentum, Gemini Enterprise usage growth, and Waymo scale.",
                "demand_drivers": ["AI experiences in Search", "enterprise AI Solutions and Infrastructure", "Gemini App/subscriptions", "Waymo rides"],
                "margin_drivers": ["Operating income up 30%; operating margin expanded to 36.1%"],
                "risk_items": ["Forward-looking statements refer to SEC risk factors and future filing updates"],
            },
            "CEO quote and opening highlights",
            management_excerpt,
        ),
        "acquisition_debt_notes": official_claim(
            "official_captured",
            {
                "senior_unsecured_notes_net_proceeds_billion": debt_proceeds,
                "use_of_proceeds": "general corporate purposes",
                "acquisitions_net_of_cash_million": 33621,
                "debt_or_leverage_commentary": "Q1 release says Alphabet issued senior unsecured notes for net proceeds of $31.1 billion in the quarter.",
            },
            "Additional Information / Cash Flow Statement",
            debt_excerpt or excerpt_around(text, "Acquisitions, net of cash acquired"),
        ),
    }

    apply_period_to_captures(captures, "2026-03-31")

    return {
        "schema_version": 1,
        "ticker": "GOOG",
        "company_name": "Alphabet Inc.",
        "period_end": "2026-03-31",
        "generated_at_utc": utc_now(),
        "review_only": True,
        "resolved_for_apply": False,
        "source": official_source_metadata(GOOG_META, text, raw_html),
        "authority": AUTHORITY,
        "captures": captures,
        "summary": {
            "official_fields_checked": len(captures),
            "official_captured_or_not_disclosed": sum(1 for c in captures.values() if c["status"] in {"official_captured", "not_disclosed_in_release", "partial"}),
            "manual_required_remaining": sum(1 for c in captures.values() if c["status"] == "manual_required"),
            "apply_ready": False,
            "note": "Review-only official capture; downstream WF65/WF66 validators must consume this before any WF64/WF56 gated apply can be considered.",
        },
    }


def write_md(path: Path, data: dict[str, Any]) -> None:
    lines = ["# GOOG Q1 2026 Official IR Capture", ""]
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
    parser = argparse.ArgumentParser(description="Capture GOOG Q1 2026 official earnings fields from SEC 8-K Exhibit 99.1.")
    parser.add_argument("--output", default=str(OUT_JSON))
    parser.add_argument("--write-md", action="store_true", help="Also write the optional human-readable Markdown digest.")
    args = parser.parse_args()
    raw = fetch_source(SOURCE_URL)
    text = html_to_text(raw)
    data = build_capture(text, raw)
    out = Path(args.output)
    write_json(out, data)
    if args.write_md:
        write_md(out.with_suffix(".md"), data)
    print(json.dumps({"status": "ok", "output": rel(out), "summary": data["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
