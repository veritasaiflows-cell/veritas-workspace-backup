#!/usr/bin/env python3
"""Build an anonymous-scenario Retail Investor Finance Intelligence demo.

The generated customer export is fixture-only. It is not a launch artifact, not
customer-data authority, not advice, and not trading/brokerage authority.
It uses anonymous service request scenarios instead of fake-person personas.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from retail_saas_customer_output_validator import validate_payload, validate_rendered_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
DEFAULT_JSON = TMP / "retail-saas-fixture-demo.json"
DEFAULT_CUSTOMER_JSON = TMP / "retail-saas-fixture-demo.customer-export.json"
DEFAULT_MD = TMP / "retail-saas-fixture-demo.md"
DEFAULT_VALIDATION = TMP / "retail-saas-fixture-demo-validation.json"
DEFAULT_SEEDED_BAD = TMP / "retail-saas-fixture-demo.seeded-bad.json"
DEFAULT_SEEDED_BAD_VALIDATION = TMP / "retail-saas-fixture-demo.seeded-bad-validation.json"
DEFAULT_SEEDED_BAD_MD = TMP / "retail-saas-fixture-demo.seeded-bad.md"
DEFAULT_SEEDED_BAD_MD_VALIDATION = TMP / "retail-saas-fixture-demo.seeded-bad-md-validation.json"
DEFAULT_TICKERS = ["ETN", "MSFT", "NVDA", "JPM", "VRT"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_card(ticker: str) -> dict[str, Any]:
    path = CARD_DIR / f"{ticker}.current.json"
    payload = load_json_artifact(path)
    if not isinstance(payload, dict):
        raise SystemExit(f"Missing or invalid ticker card: {path}")
    return payload


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def freshness_from_card(card: dict[str, Any]) -> str:
    missing = as_list(card.get("missing_or_stale_evidence"))
    if missing:
        return "partial"
    latest = str(card.get("generated_at_utc") or "")
    return "current" if latest else "unknown"


def compact_evidence_gaps(card: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    for row in as_list(card.get("missing_or_stale_evidence"))[:4]:
        if isinstance(row, dict):
            family = row.get("family") or row.get("field") or "evidence gap"
            status = row.get("status") or row.get("freshness") or row.get("reason") or "requires review"
            gaps.append(f"{family}: {status}")
        elif isinstance(row, str):
            gaps.append(row)
    return gaps or ["No major stale/missing evidence flag was present in the internal card, but source verification is still required before relying on this output."]


def risk_flags(card: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    for row in as_list(card.get("risk_register"))[:3]:
        if isinstance(row, dict):
            category = row.get("category") or "risk"
            summary = row.get("summary") or row.get("risk") or row.get("description") or row.get("note") or "Requires review."
            risks.append(f"{category}: {summary}")
        elif isinstance(row, str):
            risks.append(row)
    return risks or ["Risk review required before any investor decision."]


def what_to_watch(card: dict[str, Any]) -> list[str]:
    ticker = str(card.get("ticker") or "")
    band = card.get("price_band_stop") if isinstance(card.get("price_band_stop"), dict) else {}
    earnings = card.get("latest_earnings_performance") if isinstance(card.get("latest_earnings_performance"), dict) else {}
    items = [
        f"Price context: latest known price {band.get('latest_known_price', 'unknown')} versus research watch zone {band.get('entry_band_low', 'unknown')} to {band.get('entry_band_high', 'unknown')}.",
        f"Risk line to review: {band.get('stop_or_invalidation', 'unknown')}.",
    ]
    if earnings.get("status"):
        items.append(f"Earnings context available for period ending {earnings.get('period_end', 'unknown')}; verify official-source details before relying on it.")
    if ticker:
        items.append(f"Use {ticker} as a research watch item, not as an instruction.")
    return items


def build_watchlist_item(card: dict[str, Any]) -> dict[str, Any]:
    meta = card.get("universe_metadata") if isinstance(card.get("universe_metadata"), dict) else {}
    band = card.get("price_band_stop") if isinstance(card.get("price_band_stop"), dict) else {}
    thesis = card.get("thesis_bull_bear_entry_context") if isinstance(card.get("thesis_bull_bear_entry_context"), dict) else {}
    return {
        "ticker": card.get("ticker"),
        "company_name": meta.get("name") or card.get("ticker"),
        "sector": meta.get("sector") or "Unknown",
        "research_posture": "Research watch item, not a recommendation or action instruction.",
        "plain_language_summary": thesis.get("thesis") or "Research summary requires source-open review before final use.",
        "evidence_freshness": freshness_from_card(card),
        "source_timestamp": card.get("generated_at_utc") or "unknown",
        "customer_safe_source_categories": [
            "generated_ticker_research_card",
            "company_official_or_sec_evidence_when_available",
            "market_data_snapshot_requiring_refresh",
        ],
        "claim_freshness": {
            "price_context": "stale_until_fresh_quote_refresh",
            "business_summary": "requires_source_open_review_before_reliance",
            "risk_context": "partial_review_required",
        },
        "price_context": {
            "latest_known_price": band.get("latest_known_price"),
            "watch_zone_low": band.get("entry_band_low"),
            "watch_zone_high": band.get("entry_band_high"),
            "risk_review_level": band.get("stop_or_invalidation"),
            "status_label": band.get("band_status"),
            "fresh_quote_required": bool(band.get("fresh_quote_required")),
            "staleness_note": band.get("staleness_note") or "Refresh price data before relying on this output.",
        },
        "what_to_watch": what_to_watch(card),
        "risk_flags": risk_flags(card),
        "stale_or_missing_evidence": compact_evidence_gaps(card),
    }


def build_payload(tickers: list[str]) -> dict[str, Any]:
    cards = [load_card(t) for t in tickers]
    now = utc_now()
    customer_export = {
        "customer_visible": True,
        "product_name": "Veritas Retail Investor Finance Intelligence",
        "product_posture": "Educational and informational research support only; not investment advice, not brokerage, and not execution.",
        "fixture_notice": "Internal anonymous service request scenario using real public ticker evidence where available. No real customer data, personal identity, portfolio, or suitability data is used.",
        "anonymous_service_request": {
            "request_id": "anon-watchlist-ai-infrastructure-v1",
            "request_type": "watchlist_brief",
            "audience_segment": "self_directed_retail_investor",
            "scenario": "ai_infrastructure_and_quality_watchlist",
            "personal_data_used": False,
            "suitability_data_used": False,
            "portfolio_data_used": False,
            "watchlist_intent_is_personalized": False,
            "ticker_set": tickers,
        },
        "brief_title": "Anonymous Watchlist Intelligence Brief",
        "generated_at": now,
        "watchlist_items": [build_watchlist_item(card) for card in cards],
        "portfolio_level_notes": [
            "This demo prioritizes evidence freshness, risk flags, and research questions over action instructions.",
            "Items outside a research watch zone are framed as no-chase/review context, not as missed trades.",
            "Missing or stale evidence is shown explicitly instead of hidden."
        ],
        "disclaimers": [
            "For educational and informational purposes only.",
            "Not investment, tax, legal, accounting, retirement, or financial planning advice.",
            "Not a broker-dealer, exchange, custodian, or order-execution service.",
            "Investing involves risk, including possible loss of principal.",
            "Data may be delayed, incomplete, stale, or wrong; verify important facts with primary sources.",
            "Users are responsible for their own decisions and should consult qualified professionals where appropriate."
        ],
        "authority_boundary": {
            "investment_advice": False,
            "brokerage_connection": False,
            "trade_execution": False,
            "account_management": False,
            "guaranteed_return": False,
            "personalized_recommendation": False,
            "real_customer_data": False,
            "suitability_analysis": False,
        },
    }
    return {
        "schema": "veritas.retail_saas.fixture_demo.v1",
        "generated_at_utc": now,
        "status": "fixture_demo_ready",
        "real_customer_data_used": False,
        "external_delivery_allowed": False,
        "customer_export": customer_export,
        "internal_input_summary": {
            "source_family": "WF77 ticker intelligence cards",
            "tickers": tickers,
            "customer_visible": False,
            "notes": "Internal provenance only. Do not expose this section to customers.",
        },
        "authority_boundary": {
            "fixture_grants_launch_readiness": False,
            "fixture_grants_customer_data_authority": False,
            "fixture_grants_external_delivery_authority": False,
            "fixture_grants_brokerage_or_execution_authority": False,
            "fixture_grants_regulated_advice_authority": False,
        },
    }


def customer_export_document(payload: dict[str, Any]) -> dict[str, Any]:
    export = dict(payload["customer_export"])
    return {"schema": "veritas.retail_saas.customer_export.v1", **export}


def render_md(payload: dict[str, Any]) -> str:
    export = payload["customer_export"]
    lines = [
        "# Anonymous Watchlist Intelligence Brief",
        "",
        f"Generated: {export['generated_at']}",
        "",
        export["fixture_notice"],
        "",
        "## Service Request",
        "",
        f"- Request ID: {export['anonymous_service_request']['request_id']}",
        f"- Request type: {export['anonymous_service_request']['request_type']}",
        f"- Audience segment: {export['anonymous_service_request']['audience_segment']}",
        f"- Scenario: {export['anonymous_service_request']['scenario']}",
        "- Personal/customer/suitability data used: false",
        "",
        "## Watchlist",
        "",
    ]
    for item in export["watchlist_items"]:
        lines.extend([
            f"### {item['ticker']} - {item['company_name']}",
            "",
            f"- Posture: {item['research_posture']}",
            f"- Freshness: {item['evidence_freshness']} as of {item['source_timestamp']}",
            f"- Price context: {item['price_context']['latest_known_price']} vs watch zone {item['price_context']['watch_zone_low']} to {item['price_context']['watch_zone_high']}; risk review level {item['price_context']['risk_review_level']}",
            "- What to watch:",
        ])
        lines.extend(f"  - {x}" for x in item["what_to_watch"])
        lines.append("- Risk flags:")
        lines.extend(f"  - {x}" for x in item["risk_flags"])
        lines.append("- Stale or missing evidence:")
        lines.extend(f"  - {x}" for x in item["stale_or_missing_evidence"])
        lines.append("")
    lines.extend([
        "## Disclaimers",
        "",
    ])
    lines.extend(f"- {x}" for x in export["disclaimers"])
    lines.extend([
        "",
        "## Boundary",
        "",
        "This demo is educational research support only. It does not connect to financial accounts, manage assets, submit transactions, or provide personalized recommendations.",
        "",
    ])
    return "\n".join(lines)


def write_seeded_bad(clean_payload: dict[str, Any], path: Path, validation_path: Path) -> dict[str, Any]:
    bad = dict(clean_payload)
    bad["customer_export"] = dict(clean_payload["customer_export"])
    bad["customer_export"]["brief_title"] = "Guaranteed return trade now demo"
    bad["customer_export"]["portfolio_level_notes"] = list(bad["customer_export"].get("portfolio_level_notes", [])) + [
        "Strong buy. Buy now and hold. Expected upside is 25% with a $500 price target."
    ]
    if bad["customer_export"].get("watchlist_items"):
        bad["customer_export"]["watchlist_items"][0] = dict(bad["customer_export"]["watchlist_items"][0])
        bad["customer_export"]["watchlist_items"][0]["evidence_freshness"] = "current"
        bad["customer_export"]["watchlist_items"][0]["stale_or_missing_evidence"] = ["No issues"]
    bad["customer_export"]["customer_visible_note"] = "Internal proof: tmp/ticker-intelligence-cards/ETN.current.json and C:\\Users\\Veritas\\.openclaw\\workspace\\tmp\\veritas-artifact-index.sqlite"
    bad["customer_export"]["authority_boundary"] = dict(clean_payload["customer_export"]["authority_boundary"])
    bad["customer_export"]["authority_boundary"]["trade_execution"] = True
    atomic_write_json(path, bad)
    validation = validate_payload(bad)
    atomic_write_json(validation_path, validation)
    return validation


def write_seeded_bad_markdown(path: Path, validation_path: Path) -> dict[str, Any]:
    text = "\n".join([
        "# Seeded Bad Retail SaaS Brief",
        "",
        "Strong buy. Buy now and hold.",
        "Expected upside is 25% with a $500 price target.",
        "Internal proof path: C:\\Users\\Veritas\\.openclaw\\workspace\\tmp\\veritas-artifact-index.sqlite",
    ])
    atomic_write_text(path, text)
    findings = validate_rendered_text(text, path.name)
    validation = {
        "schema": "veritas.retail_saas.customer_output_validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not findings else "error",
        "critical_count": sum(1 for f in findings if f["severity"] == "critical"),
        "warning_count": sum(1 for f in findings if f["severity"] == "warning"),
        "findings": findings,
        "rendered_text_validated": str(path),
        "authority_boundary": {
            "validator_grants_launch_readiness": False,
            "validator_grants_customer_data_authority": False,
            "validator_grants_external_delivery_authority": False,
            "validator_grants_brokerage_or_execution_authority": False,
            "validator_grants_regulated_advice_authority": False,
        },
    }
    atomic_write_json(validation_path, validation)
    return validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixture-only Retail Investor Finance Intelligence SaaS demo.")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS, help="Ticker cards to include")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON), help="Demo JSON output")
    parser.add_argument("--customer-json-out", default=str(DEFAULT_CUSTOMER_JSON), help="Customer-only export JSON output")
    parser.add_argument("--md-out", default=str(DEFAULT_MD), help="Demo Markdown output")
    parser.add_argument("--validation-out", default=str(DEFAULT_VALIDATION), help="Validation JSON output")
    parser.add_argument("--write-seeded-bad", action="store_true", help="Write a seeded-bad fixture and validation proof")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.tickers)
    validation = validate_payload(payload)
    rendered = render_md(payload)
    rendered_findings = validate_rendered_text(rendered, Path(args.md_out).name)
    validation["findings"].extend(rendered_findings)
    validation["critical_count"] = sum(1 for f in validation["findings"] if f["severity"] == "critical")
    validation["warning_count"] = sum(1 for f in validation["findings"] if f["severity"] == "warning")
    validation["status"] = "ok" if validation["critical_count"] == 0 else "error"
    validation["rendered_text_validated"] = str(args.md_out)
    customer_export = customer_export_document(payload)
    customer_validation = validate_payload(customer_export)
    validation["customer_export_validation_status"] = customer_validation["status"]
    if customer_validation["status"] != "ok":
        validation["findings"].extend(customer_validation["findings"])
        validation["critical_count"] = sum(1 for f in validation["findings"] if f["severity"] == "critical")
        validation["warning_count"] = sum(1 for f in validation["findings"] if f["severity"] == "warning")
        validation["status"] = "error"
    atomic_write_json(args.json_out, payload)
    atomic_write_json(args.customer_json_out, customer_export)
    atomic_write_text(args.md_out, rendered)
    atomic_write_json(args.validation_out, validation)
    seeded_status = "not_written"
    seeded_md_status = "not_written"
    if args.write_seeded_bad:
        seeded_validation = write_seeded_bad(payload, DEFAULT_SEEDED_BAD, DEFAULT_SEEDED_BAD_VALIDATION)
        seeded_status = seeded_validation["status"]
        seeded_md_validation = write_seeded_bad_markdown(DEFAULT_SEEDED_BAD_MD, DEFAULT_SEEDED_BAD_MD_VALIDATION)
        seeded_md_status = seeded_md_validation["status"]
    print(f"status={validation['status']} critical={validation['critical_count']} warning={validation['warning_count']} seeded_bad={seeded_status} seeded_bad_md={seeded_md_status}")
    return 0 if validation["status"] == "ok" and seeded_status in {"not_written", "error"} and seeded_md_status in {"not_written", "error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
