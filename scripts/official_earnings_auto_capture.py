"""Safe additive capture for independently discovered SEC earnings sources.

The parser is deliberately conservative: ETN has a matching-period 10-Q
bridge, while all other newly discovered sources receive field-specific,
evidence-bearing manual records until a value-level parser is proven. Nothing here mutates canon,
portfolio state, approval state, sizing, cash, trades, or accounts.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from official_ir_capture_common import (
    AUTHORITY as COMMON_AUTHORITY,
    build_capture_document,
    claim,
    fetch_source,
    html_to_text,
    rel,
    write_json,
    write_md,
)
from official_ir_capture_validator import validate_one

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "official-ir-captures"
SUPPORTED_TICKERS = {"ETN"}
SUPPORTED_SOURCE_TYPES = {
    "sec_8k_exhibit_99_1",
    "sec_10q_official_report",
    "sec_10k_official_report",
}
MANUAL_RECONCILIATION_FIELDS = (
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
    "quarterly_metrics",
)
CAPTURE_STATUSES = {
    "official_captured",
    "not_disclosed_in_release",
    "not_applicable",
    "manual_required",
    "partial",
}
GENERIC_FIELD_SIGNALS = {
    "adjusted_eps": (
        "adjusted earnings per share",
        "adjusted eps",
        "non-gaap diluted earnings per share",
        "non-gaap eps",
    ),
    "guidance": ("guidance", "outlook", "expects", "expectations"),
    "growth_bridge": ("organic growth", "foreign exchange", "currency", "revenue increased", "revenue decreased"),
    "segment_margins": ("segment margin", "operating margin", "operating income"),
    "orders_backlog": ("backlog", "book-to-bill", "orders"),
    "management_explanation": ("chief executive officer", " ceo ", "ceo said", "said"),
    "acquisition_debt_notes": ("acquisition", "debt", "leverage", "borrowings"),
    "quarterly_metrics": ("revenue", "net income", "earnings per share", "cash flow"),
}

AUTHORITY = {
    **COMMON_AUTHORITY,
    "statement": "Review-only auto-capture from an independently discovered official SEC earnings release. No workspace apply, approval inference, portfolio mutation, or execution authority.",
}


def _float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _range(pattern: str, text: str) -> dict[str, float] | None:
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return None
    try:
        return {"low": float(match.group(1)), "high": float(match.group(2))}
    except (TypeError, ValueError):
        return None


def _excerpt(text: str, needle: str, chars: int = 1100) -> str:
    index = text.lower().find(needle.lower())
    if index < 0:
        return ""
    start = max(0, index - chars // 3)
    end = min(len(text), index + chars)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _first_excerpt(text: str, *needles: str, chars: int = 1100) -> str:
    for needle in needles:
        excerpt = _excerpt(text, needle, chars=chars)
        if excerpt:
            return excerpt
    return ""


def _status(value: Any, excerpt: str) -> str:
    def complete(candidate: Any) -> bool:
        if candidate is None:
            return False
        if isinstance(candidate, str):
            return bool(candidate.strip())
        if isinstance(candidate, dict):
            return bool(candidate) and all(complete(item) for item in candidate.values())
        if isinstance(candidate, (list, tuple)):
            return bool(candidate) and all(complete(item) for item in candidate)
        return True

    if not complete(value):
        return "manual_required"
    if not excerpt:
        return "manual_required"
    return "official_captured"


def _capture_claim(source_url: str, value: Any, section: str, excerpt: str, note: str | None = None) -> dict[str, Any]:
    return claim(source_url, _status(value, excerpt), value, section, excerpt, note)


def _attach_official_evidence(captures: dict[str, dict[str, Any]], source_meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Attach an auditable official-source record to every field block.

    This is deliberately additive.  It does not promote a source, fill a value,
    or turn a manual field into a captured field.  A captured value must retain
    its own non-empty verbatim excerpt or it is downgraded to manual-required.
    """

    default_source_url = str(source_meta.get("source_url") or "")
    filing_url = str(source_meta.get("filing_url") or "")
    period_end = str(source_meta.get("period_end") or source_meta.get("latest_detected_period_end") or "")
    for field, block in captures.items():
        if not isinstance(block, dict):
            continue
        status = str(block.get("status") or "")
        excerpt = str(block.get("excerpt") or "")
        if status not in CAPTURE_STATUSES:
            block["status"] = "manual_required"
            status = "manual_required"
        if status == "official_captured" and _status(block.get("value"), excerpt) != "official_captured":
            block["status"] = "manual_required"
        elif status in {"partial", "not_disclosed_in_release"} and not excerpt:
            block["status"] = "manual_required"
        block["official_evidence"] = {
            "field": field,
            "official_url": str(block.get("source_url") or default_source_url),
            "filing_url": filing_url or None,
            "period_end": period_end or None,
            "exact_official_excerpt": excerpt,
        }
    return captures


def _period_label(period_end: str) -> str:
    year, month, _day = (int(part) for part in period_end.split("-"))
    quarter = ((month - 1) // 3) + 1
    return f"Q{quarter} {year}"


def _pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return round(((current / prior) - 1.0) * 100.0, 4)


def _html_attr(attrs: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*(['\"])(.*?)\1", attrs, flags=re.I | re.S)
    return match.group(2) if match else None


def _xbrl_facts(raw_html: str, concept: str) -> list[dict[str, Any]]:
    """Extract numeric inline-XBRL facts without guessing a period or value."""

    pattern = re.compile(r"<ix:nonFraction\b(?P<attrs>[^>]*)>(?P<value>.*?)</ix:nonFraction>", re.I | re.S)
    expected_name = f"us-gaap:{concept}".lower()
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(raw_html):
        attrs = match.group("attrs")
        if str(_html_attr(attrs, "name") or "").lower() != expected_name:
            continue
        context = _html_attr(attrs, "contextRef")
        if not context:
            continue
        value_text = html.unescape(re.sub(r"<[^>]+>", "", match.group("value"))).strip()
        negative = value_text.startswith("(") and value_text.endswith(")")
        cleaned = re.sub(r"[^0-9.\-]", "", value_text)
        try:
            value = float(cleaned)
        except ValueError:
            continue
        if negative:
            value = -abs(value)
        try:
            scale = int(_html_attr(attrs, "scale") or "0")
        except ValueError:
            scale = 0
        if str(_html_attr(attrs, "sign") or "").strip() == "-":
            value = -abs(value)
        rows.append({
            "context": context,
            "value": value * (10 ** scale),
            "excerpt": re.sub(r"\s+", " ", match.group(0)).strip(),
        })
    return rows


def _context_end_date(raw_html: str, context: str) -> str | None:
    pattern = re.compile(
        rf"<(?:xbrli:)?context\b[^>]*\bid=['\"]{re.escape(context)}['\"][^>]*>(.*?)</(?:xbrli:)?context>",
        re.I | re.S,
    )
    match = pattern.search(raw_html)
    if not match:
        return None
    end = re.search(r"<(?:xbrli:)?endDate[^>]*>\s*([^<\s]+)\s*</(?:xbrli:)?endDate>", match.group(1), re.I)
    return end.group(1) if end else None


def _fact_by_context(raw_html: str, concept: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in _xbrl_facts(raw_html, concept):
        rows.setdefault(str(row["context"]), row)
    return rows


def _etn_matching_period_10q_bridge(raw_html: str, period_end: str, source_url: str) -> dict[str, Any] | None:
    """Return exact ETN quarterly facts only when their context matches the release period."""

    eps_by_context = _fact_by_context(raw_html, "EarningsPerShareDiluted")
    current_context = next(
        (context for context in eps_by_context if _context_end_date(raw_html, context) == period_end),
        None,
    )
    if not current_context:
        return None
    prior_context = next((context for context in eps_by_context if context != current_context), None)
    if not prior_context:
        return None
    concepts = {
        "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "net_income": "NetIncomeLoss",
        "diluted_eps": "EarningsPerShareDiluted",
        "diluted_average_shares": "WeightedAverageNumberOfDilutedSharesOutstanding",
    }
    current: dict[str, dict[str, Any] | None] = {}
    prior: dict[str, dict[str, Any] | None] = {}
    for name, concept in concepts.items():
        values = _fact_by_context(raw_html, concept)
        current[name] = values.get(current_context)
        prior[name] = values.get(prior_context)
    required = ("revenue", "net_income", "diluted_eps")
    if any(current[name] is None or prior[name] is None for name in required):
        return None

    revenue = float(current["revenue"]["value"])
    revenue_prior = float(prior["revenue"]["value"])
    net_income = float(current["net_income"]["value"])
    net_income_prior = float(prior["net_income"]["value"])
    diluted_eps = float(current["diluted_eps"]["value"])
    diluted_eps_prior = float(prior["diluted_eps"]["value"])
    excerpts = [
        str(current[name]["excerpt"])
        for name in (*required,)
        if current[name] is not None
    ]
    return {
        "official_period_bridge_verified": True,
        "period_bridge_validation": "matching_period_official_10q",
        "source_kind": "sec_10q_official_report",
        "comparison_period_end": _context_end_date(raw_html, prior_context),
        "revenue": revenue,
        "revenue_prior": revenue_prior,
        "revenue_yoy_pct": _pct_change(revenue, revenue_prior),
        "net_income": net_income,
        "net_income_prior": net_income_prior,
        "net_income_yoy_pct": _pct_change(net_income, net_income_prior),
        "diluted_eps": diluted_eps,
        "diluted_eps_prior": diluted_eps_prior,
        "eps_yoy_pct": _pct_change(diluted_eps, diluted_eps_prior),
        "diluted_average_shares": current["diluted_average_shares"]["value"] if current["diluted_average_shares"] else None,
        "diluted_average_shares_prior": prior["diluted_average_shares"]["value"] if prior["diluted_average_shares"] else None,
        "period_bridge_required_fields": [
            "revenue",
            "revenue_prior",
            "net_income",
            "net_income_prior",
            "diluted_eps",
            "diluted_eps_prior",
        ],
        "source_url": source_url,
        "excerpt": " ".join(excerpts)[:2800],
        "current_context": current_context,
        "prior_context": prior_context,
    }


def _period_slug(period_end: str, supplied: str | None = None) -> str:
    if supplied:
        return supplied
    year, month, _day = (int(part) for part in period_end.split("-"))
    return f"q{((month - 1) // 3) + 1}-{year}"


def _safe_output(ticker: str, period_end: str, period_slug_value: str) -> Path:
    output = OUT_DIR / f"{ticker.lower()}-{period_slug_value}.json"
    if output.exists():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"existing target is not valid JSON: {output}: {exc}") from exc
        if str(existing.get("ticker", "")).upper() != ticker or str(existing.get("period_end")) != period_end:
            raise ValueError(f"refusing to overwrite an artifact with a different ticker/period: {output}")
    return output


def _company_name(ticker: str, source_meta: dict[str, Any]) -> str:
    explicit = str(source_meta.get("company_name") or "").strip()
    if explicit:
        return explicit
    for path in sorted(OUT_DIR.glob(f"{ticker.lower()}-*.json"), reverse=True):
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = str(existing.get("company_name") or "").strip()
        if name:
            return name
    return ticker


def build_generic_source_captures(source_meta: dict[str, Any], text: str) -> dict[str, dict[str, Any]]:
    """Create field-specific, no-guess evidence records for a verified source.

    The generic layer extracts only candidate excerpts.  It intentionally does
    not convert prose into financial values: absent a field-specific parser,
    each value remains ``None`` and manual-required.  That lets cron surface the
    exact source location while preserving review/decision gates.
    """

    source_url = str(source_meta.get("source_url") or "")
    period_end = str(source_meta.get("period_end") or source_meta.get("latest_detected_period_end") or "")
    if not source_url or not period_end:
        raise ValueError("generic source capture requires source_url and period_end")
    label = _period_label(period_end)
    captures: dict[str, dict[str, Any]] = {}
    for field in MANUAL_RECONCILIATION_FIELDS:
        signals = GENERIC_FIELD_SIGNALS.get(field, ())
        excerpt = _first_excerpt(text, *signals, chars=900)
        note = (
            "Field-specific official-source excerpt found; no value was inferred and source-open reconciliation remains required."
            if excerpt
            else "No reliable field-specific value was inferred from the official source; source-open reconciliation remains required."
        )
        captures[field] = claim(
            source_url,
            "manual_required",
            None,
            f"{label} verified official source: {field}",
            excerpt,
            note,
        )
    return _attach_official_evidence(captures, source_meta)


def build_etn_capture(
    text: str,
    source_meta: dict[str, Any],
    period_bridge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_url = str(source_meta["source_url"])
    period_end = str(source_meta["period_end"])
    label = _period_label(period_end)

    gaap_eps = _float(r"\bearnings per share were \$([0-9]+(?:\.[0-9]+)?)", text)
    adjusted_eps = _float(r"adjusted earnings per share were \$([0-9]+(?:\.[0-9]+)?)", text)
    charges_match = re.search(
        r"charges of \$([0-9.]+) per share related to intangible amortization,\s*\$([0-9.]+) per share related to acquisitions and divestitures,\s*and \$([0-9.]+) per share related to (?:a )?multi-year restructuring program",
        text,
        flags=re.I | re.S,
    )
    adjustments = (
        {
            "intangible_amortization": float(charges_match.group(1)),
            "acquisitions_and_divestitures": float(charges_match.group(2)),
            "multi_year_restructuring_program": float(charges_match.group(3)),
        }
        if charges_match
        else None
    )
    eps_value = {
        "gaap_eps": gaap_eps,
        "adjusted_eps": adjusted_eps,
        "adjustments_per_share": adjustments,
    }
    eps_excerpt = _first_excerpt(text, "adjusted earnings per share were", "earnings per share were")

    full_year_start = re.search(r"(?:For the )?full year \d{4}.*", text, flags=re.I)
    full_year_text = text[full_year_start.start() :] if full_year_start else text
    third_quarter = re.search(r"For the third quarter", full_year_text, flags=re.I)
    if third_quarter:
        full_year_text = full_year_text[: third_quarter.start()]
    eps_range = _range(r"earnings per share(?: expected)?(?: to be)? between \$([0-9.]+) and \$([0-9.]+)", full_year_text)
    adjusted_range = _range(r"adjusted earnings per share(?: expected)?(?: to be)? between \$([0-9.]+) and \$([0-9.]+)", full_year_text)
    organic_match = re.search(r"organic growth of ([0-9.]+)-([0-9.]+)%", full_year_text, flags=re.I)
    guidance_value = {
        "eps_range": eps_range,
        "adjusted_eps_range": adjusted_range,
        "organic_growth_guidance_range_pct": (
            {"low": float(organic_match.group(1)), "high": float(organic_match.group(2))}
            if organic_match
            else None
        ),
        "adjusted_eps_midpoint_growth_pct": _float(r"adjusted earnings per share expected to be between \$[0-9.]+ and \$[0-9.]+, up ([0-9.]+)%", text),
    }
    guidance_excerpt = _first_excerpt(text, "For the full year", "Guidance")

    sales_growth = _float(r"sales in the quarter were .*? up ([0-9.]+)%", text)
    organic_growth = _float(r"sales increase consisted of ([0-9.]+)% growth in organic sales", text)
    acquisition_growth = _float(r"and ([0-9.]+)% growth from acquisitions", text)
    growth_value = {
        "reported_sales_growth_pct": sales_growth,
        "organic_sales_growth_pct": organic_growth,
        "acquisition_growth_pct": acquisition_growth,
        "fx_growth_pct": None,
    }
    growth_excerpt = _first_excerpt(text, "sales in the quarter were", "sales increase consisted of")

    # Keep the latest-period card from mixing an older normalized provider row
    # with a newer official release.  These amounts are intentionally marked as
    # rounded where the release reports billions; they are review-only evidence,
    # not a replacement for the normalized 10-Q metrics pipeline.
    sales_billions = _float(r"sales in the quarter were \$([0-9.]+) billion", text)
    cashflow_match = re.search(
        r"Operating cash flow was \$([0-9.]+) billion, and free cash flow was \$([0-9.]+) million,"
        r" up ([0-9.]+)% and ([0-9.]+)%, respectively",
        text,
        flags=re.I | re.S,
    )
    quarterly_metrics_value = {
        "revenue": sales_billions * 1_000_000_000 if sales_billions is not None else None,
        "revenue_precision": "reported_rounded_billions" if sales_billions is not None else None,
        "diluted_eps": gaap_eps,
        "net_income": None,
        "operating_cash_flow": float(cashflow_match.group(1)) * 1_000_000_000 if cashflow_match else None,
        "operating_cash_flow_precision": "reported_rounded_billions" if cashflow_match else None,
        "free_cash_flow": float(cashflow_match.group(2)) * 1_000_000 if cashflow_match else None,
        "free_cash_flow_yoy_pct": float(cashflow_match.group(4)) if cashflow_match else None,
        "net_income_note": "Not disclosed in the discovered earnings release; obtain from the validated 10-Q/normalized metrics refresh.",
    }
    quarterly_metrics_excerpt = _first_excerpt(
        text,
        "Operating cash flow was",
        "sales in the quarter were",
    )
    quarterly_metrics_source_url = source_url
    if period_bridge:
        quarterly_metrics_value.update({
            key: value
            for key, value in period_bridge.items()
            if key not in {"source_url", "excerpt", "current_context", "prior_context"}
        })
        quarterly_metrics_value["revenue_precision"] = "exact_10q"
        quarterly_metrics_value["net_income_precision"] = "exact_10q"
        quarterly_metrics_value["diluted_eps_precision"] = "exact_10q"
        quarterly_metrics_value["net_income_note"] = "Exact matching-period amount from the validated official 10-Q bridge."
        quarterly_metrics_source_url = str(period_bridge["source_url"])
        quarterly_metrics_excerpt = str(period_bridge["excerpt"])

    company_margin = _float(r"Segment margins were ([0-9.]+)%", text)
    americas_margin = _float(r"Electrical Americas.*?operating margins in the quarter were ([0-9.]+)%", text)
    global_margin = _float(r"Electrical Global segment.*?operating margins in the quarter were ([0-9.]+)%", text)
    aerospace_margin = _float(r"Aerospace segment.*?Operating margins(?: of)? ([0-9.]+)%", text)
    mobility_margin = _float(r"Mobility segment.*?Operating margins in the quarter of ([0-9.]+)%", text)
    segment_value = {
        "company_segment_margin_pct": company_margin,
        "electrical_americas_operating_margin_pct": americas_margin,
        "electrical_global_operating_margin_pct": global_margin,
        "aerospace_operating_margin_pct": aerospace_margin,
        "mobility_operating_margin_pct": mobility_margin,
        "note": "Automatically parsed from the discovered official release; any missing sub-field remains manual-required.",
    }
    segment_excerpt = _first_excerpt(text, "Segment margins were", "Electrical Americas segment")

    def segment_section(marker: str, *next_markers: str) -> str:
        start = text.lower().find(marker.lower())
        if start < 0:
            return ""
        end = len(text)
        lowered = text.lower()
        for next_marker in next_markers:
            next_index = lowered.find(next_marker.lower(), start + len(marker))
            if next_index >= 0:
                end = min(end, next_index)
        return text[start:end]

    sections = {
        "americas": segment_section("Sales for the Electrical Americas segment", "Sales for the Electrical Global segment", "Aerospace segment sales", "Mobility segment posted"),
        "global": segment_section("Sales for the Electrical Global segment", "Aerospace segment sales", "Mobility segment posted"),
        "aerospace": segment_section("Aerospace segment sales", "Mobility segment posted"),
    }

    def segment_metric(section_name: str, metric: str) -> float | None:
        section = sections[section_name]
        if metric == "orders":
            pattern = r"orders in the [^.]+?up ([0-9.]+)%"
        else:
            pattern = r"backlog[^.]*?up ([0-9.]+)%"
        return _float(pattern, section)

    orders_value = {
        "electrical_americas_orders_growth_pct": segment_metric("americas", "orders"),
        "electrical_americas_backlog_growth_pct": segment_metric("americas", "backlog"),
        "electrical_global_orders_growth_pct": segment_metric("global", "orders"),
        "electrical_global_backlog_growth_pct": segment_metric("global", "backlog"),
        "aerospace_orders_growth_pct": segment_metric("aerospace", "orders"),
        "aerospace_backlog_growth_pct": segment_metric("aerospace", "backlog"),
        "electrical_businesses_book_to_bill": _float(r"book-to-bill ratio for the Electrical businesses .*?([0-9]+(?:\.[0-9]+)?)", text),
        "aerospace_book_to_bill": _float(r"book-to-bill ratio for the Aerospace segment .*?([0-9]+(?:\.[0-9]+)?)", text),
    }
    orders_excerpt = _first_excerpt(text, "orders in the", "backlog at the end", "book-to-bill ratio")

    management_excerpt = _first_excerpt(text, "chief executive officer", "CEO said")
    management_value = {"summary": management_excerpt or None}

    mobility_excerpt = _first_excerpt(text, "agreement to separate Mobility", "portfolio transformation")
    acquisition_value = {
        "mobility_separation_announced": bool(mobility_excerpt),
        "debt_or_leverage_commentary": None,
        "integration_or_synergy_commentary": mobility_excerpt or None,
    }

    captures = {
        "adjusted_eps": _capture_claim(source_url, eps_value, f"{label} earnings per share paragraph", eps_excerpt),
        "guidance": _capture_claim(source_url, guidance_value, f"{label} full-year guidance", guidance_excerpt),
        "growth_bridge": _capture_claim(source_url, growth_value, f"{label} sales bridge", growth_excerpt),
        "quarterly_metrics": _capture_claim(quarterly_metrics_source_url, quarterly_metrics_value, f"{label} reported quarterly metrics", quarterly_metrics_excerpt),
        "segment_margins": _capture_claim(source_url, segment_value, f"{label} segment commentary", segment_excerpt),
        "orders_backlog": _capture_claim(source_url, orders_value, f"{label} orders and backlog commentary", orders_excerpt),
        "management_explanation": _capture_claim(source_url, management_value, f"{label} CEO commentary", management_excerpt),
        "acquisition_debt_notes": claim(source_url, "partial", acquisition_value, f"{label} portfolio and acquisition commentary", mobility_excerpt, "The release supports the mobility-separation observation; debt/leverage fields remain unpopulated and require separate 10-Q review."),
    }
    return _attach_official_evidence(captures, source_meta)


def capture_etn(source_meta: dict[str, Any], *, write_markdown: bool = False) -> dict[str, Any]:
    """Fetch and write one additive ETN period artifact; never rewrite another period."""

    if str(source_meta.get("ticker", "")).upper() != "ETN":
        raise ValueError("automatic capture currently supports ETN only")
    if source_meta.get("source_type") != "sec_8k_exhibit_99_1":
        raise ValueError("automatic capture requires a verified SEC 8-K Exhibit 99 source")
    period_end = str(source_meta.get("latest_detected_period_end") or source_meta.get("period_end") or "")
    if not period_end:
        raise ValueError("automatic capture requires latest_detected_period_end")
    meta = dict(source_meta)
    meta["period_end"] = period_end
    meta["ticker"] = "ETN"
    meta["company_name"] = "Eaton Corporation plc"

    raw = fetch_source(str(meta["source_url"]))
    text = html_to_text(raw)
    period_bridge: dict[str, Any] | None = None
    related_official_sources: list[dict[str, Any]] = []
    report_source_url = str(meta.get("report_source_url") or "").strip()
    if report_source_url:
        try:
            report_raw = fetch_source(report_source_url)
            period_bridge = _etn_matching_period_10q_bridge(report_raw, period_end, report_source_url)
            if period_bridge:
                related_official_sources.append({
                    "source_type": str(meta.get("report_source_type") or "sec_10q_official_report"),
                    "source_url": report_source_url,
                    "filing_url": meta.get("report_filing_url"),
                    "accession_number": meta.get("report_accession_number"),
                    "source_html_sha256": hashlib.sha256(report_raw.encode("utf-8")).hexdigest(),
                    "matching_period_bridge_verified": True,
                })
        except Exception as exc:  # Keep the release evidence, but never invent a 10-Q bridge.
            related_official_sources.append({
                "source_type": str(meta.get("report_source_type") or "sec_10q_official_report"),
                "source_url": report_source_url,
                "filing_url": meta.get("report_filing_url"),
                "accession_number": meta.get("report_accession_number"),
                "matching_period_bridge_verified": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
    captures = build_etn_capture(text, meta, period_bridge=period_bridge)
    data = build_capture_document(
        ticker="ETN",
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw,
        summary_note="Review-only additive auto-capture from SEC-discovered official earnings release. Historical period artifacts remain unchanged.",
    )
    data["authority"] = AUTHORITY
    data["source_capture_status"] = "source_verified_review_fresh"
    data["source_verified"] = True
    data["capture_mode"] = "etn_release_with_matching_10q_bridge" if period_bridge else "etn_release_partial"
    if related_official_sources:
        data["related_official_sources"] = related_official_sources
    period_slug_value = _period_slug(period_end, str(meta.get("period_slug") or "") or None)
    output = _safe_output("ETN", period_end, period_slug_value)
    write_json(output, data)
    validation_output = output.with_name(output.stem + "-validation.json")
    validation_report = validate_one(output, validation_output, True)
    if write_markdown:
        write_md(output.with_suffix(".md"), data, period_label=_period_label(period_end))
    return {
        "status": "captured_review_only",
        "ticker": "ETN",
        "period_end": period_end,
        "period_slug": period_slug_value,
        "output": rel(output),
        "source_url": meta["source_url"],
        "validation": {
            "status": validation_report.get("status"),
            "output": rel(validation_output),
            "summary": validation_report.get("summary"),
        },
        "field_statuses": {name: block.get("status") for name, block in captures.items()},
        "matching_period_10q_bridge_verified": bool(period_bridge),
    }


def capture_discovered_source(source_meta: dict[str, Any], *, write_markdown: bool = False) -> dict[str, Any]:
    """Write a source-verified additive artifact for a newly discovered period.

    For source forms without a proven field parser, this explicitly records the
    verified SEC source and requires source-open reconciliation. It is enough to
    stop a silent prior-period carry-forward, but never enough to claim review or
    decision freshness.
    """

    ticker = str(source_meta.get("ticker") or "").upper().strip()
    source_type = str(source_meta.get("source_type") or "")
    period_end = str(source_meta.get("latest_detected_period_end") or source_meta.get("period_end") or "")
    if not ticker or not period_end:
        raise ValueError("automatic source capture requires ticker and latest_detected_period_end")
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise ValueError(f"automatic source capture requires a supported official source type, got: {source_type or 'missing'}")
    if ticker == "ETN" and source_type == "sec_8k_exhibit_99_1":
        return capture_etn(source_meta, write_markdown=write_markdown)

    meta = dict(source_meta)
    meta["ticker"] = ticker
    meta["period_end"] = period_end
    meta["company_name"] = _company_name(ticker, meta)
    required_meta = ("source_url", "filing_url", "accession_number", "source_title")
    missing = [field for field in required_meta if not str(meta.get(field) or "").strip()]
    if missing:
        raise ValueError("automatic source capture metadata missing: " + ", ".join(missing))

    raw = fetch_source(str(meta["source_url"]))
    text = html_to_text(raw)
    label = _period_label(period_end)
    captures = build_generic_source_captures(meta, text)
    data = build_capture_document(
        ticker=ticker,
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw,
        summary_note="Official SEC source verified automatically with field-specific evidence excerpts; values remain source-open/manual until a field-level parser is proven.",
    )
    data["authority"] = AUTHORITY
    data["source_capture_status"] = "source_verified_manual_reconciliation_pending"
    data["capture_mode"] = "source_verified_evidence_bearing_manual_reconciliation"
    data["manual_reconciliation_required"] = True
    data["source_verified"] = True
    period_slug_value = _period_slug(period_end, str(meta.get("period_slug") or "") or None)
    output = _safe_output(ticker, period_end, period_slug_value)
    write_json(output, data)
    validation_output = output.with_name(output.stem + "-validation.json")
    validation_report = validate_one(output, validation_output, True)
    if validation_report.get("status") != "ok":
        raise ValueError(f"generated capture did not validate: {validation_output}")
    if write_markdown:
        write_md(output.with_suffix(".md"), data, period_label=label)
    return {
        "status": "source_verified_manual_reconciliation_pending",
        "ticker": ticker,
        "period_end": period_end,
        "period_slug": period_slug_value,
        "output": rel(output),
        "source_url": meta["source_url"],
        "validation": {
            "status": validation_report.get("status"),
            "output": rel(validation_output),
            "summary": validation_report.get("summary"),
        },
        "field_statuses": {name: block.get("status") for name, block in captures.items()},
    }
