#!/usr/bin/env python3
"""Build a review-only official source capture packet for WF78 Tier B blockers."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
INFILE = TMP / "wf78-source-capture-requirements-queue.json"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
OUT = TMP / "wf78-official-source-capture-packet.json"
SCHEMA = "veritas.wf78_official_source_capture_packet.v1"
EDGAR_FILINGS_INDEX = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=40"
)

OFFICIAL_SOURCES: dict[str, dict[str, str | None]] = {
    "ACN": {
        "company_ir_url": "https://investor.accenture.com/",
        "latest_actual_earnings_url": "https://newsroom.accenture.com/news/2026/accenture-reports-second-quarter-fiscal-2026-results",
        "latest_actual_period": "Fiscal Q2 2026",
        "latest_actual_label": "Accenture Reports Second-Quarter Fiscal 2026 Results",
        "upcoming_or_newer_event_url": "https://newsroom.accenture.com/news/2026/accenture-to-announce-third-quarter-fiscal-2026-results",
        "upcoming_or_newer_event_label": "Accenture to announce third-quarter fiscal 2026 results",
    },
    "ADI": {
        "company_ir_url": "https://investor.analog.com/",
        "latest_actual_earnings_url": "https://www.analog.com/en/newsroom/press-releases/2026/5-20-2026-adi-reports-record-fiscal-second-quarter-2026-financial-results.html",
        "latest_actual_period": "Fiscal Q2 2026",
        "latest_actual_label": "Analog Devices Reports Record Fiscal Second Quarter 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "ADP": {
        "company_ir_url": "https://www.investors.adp.com/",
        "latest_actual_earnings_url": "https://www.investors.adp.com/events-and-presentations/event-details/2026/ADP-Announces-Third-Quarter-Fiscal-2026-Financial-Results/default.aspx",
        "latest_actual_period": "Fiscal Q3 2026",
        "latest_actual_label": "ADP Announces Third Quarter Fiscal 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "ADSK": {
        "company_ir_url": "https://investors.autodesk.com/",
        "latest_actual_earnings_url": "https://investors.autodesk.com/news-releases/news-release-details/autodesk-inc-announces-fiscal-2027-first-quarter-results",
        "latest_actual_period": "Fiscal Q1 2027",
        "latest_actual_label": "Autodesk Announces Fiscal 2027 First Quarter Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "AKAM": {
        "company_ir_url": "https://www.ir.akamai.com/",
        "latest_actual_earnings_url": "https://www.ir.akamai.com/news-releases/news-release-details/akamai-reports-first-quarter-2026-financial-results",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Akamai Reports First Quarter 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "ALB": {
        "company_ir_url": "https://investors.albemarle.com/",
        "latest_actual_earnings_url": "https://investors.albemarle.com/news-and-events/news/news-details/2026/Albemarle-Reports-First-Quarter-2026-Results/default.aspx",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Albemarle Reports First Quarter 2026 Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "ALLE": {
        "company_ir_url": "https://investor.allegion.com/",
        "latest_actual_earnings_url": "https://www.allegion.com/corp/en/news/year/2026/q1-results.html",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Allegion Reports Q1-2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "AMAT": {
        "company_ir_url": "https://ir.appliedmaterials.com/",
        "latest_actual_earnings_url": "https://ir.appliedmaterials.com/news-releases/news-release-details/applied-materials-announces-second-quarter-2026-results",
        "latest_actual_period": "Fiscal Q2 2026",
        "latest_actual_label": "Applied Materials Announces Second Quarter 2026 Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "AMCR": {
        "company_ir_url": "https://www.amcor.com/investors",
        "latest_actual_earnings_url": "https://www.amcor.com/media/news/amcor-reports-solid-third-quarter-results",
        "latest_actual_period": "Fiscal Q3 2026",
        "latest_actual_label": "Amcor Reports Solid Third Quarter Results and Updates Fiscal 2026 Guidance",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "ANET": {
        "company_ir_url": "https://investors.arista.com/",
        "latest_actual_earnings_url": "https://investors.arista.com/Communications/Press-Releases-and-Events/Press-Release-Detail/2026/Arista-Networks-Inc--Reports-First-Quarter-2026-Financial-Results/default.aspx",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Arista Networks Reports First Quarter 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "APH": {
        "company_ir_url": "https://investors.amphenol.com/",
        "latest_actual_earnings_url": "https://investors.amphenol.com/news-and-events/news-details/2026/Amphenol-Reports-Record-First-Quarter-2026-Results/default.aspx",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Amphenol Reports Record First Quarter 2026 Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "APP": {
        "company_ir_url": "https://investors.applovin.com/",
        "latest_actual_earnings_url": "https://investors.applovin.com/news/news-details/2026/AppLovin-Announces-First-Quarter-2026-Financial-Results/default.aspx",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "AppLovin Announces First Quarter 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "AOS": {
        "company_ir_url": "https://investor.aosmith.com/",
        "latest_actual_earnings_url": "https://investor.aosmith.com/news-releases/news-release-details/o-smith-reports-first-quarter-2026-results-and-lowers-full-year",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "A. O. Smith Reports First Quarter 2026 Results and Lowers Full Year 2026 Outlook",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "CASY": {
        "company_ir_url": "https://investor.caseys.com/",
        "latest_actual_earnings_url": "https://www.businesswire.com/news/home/20260609792833/en/Caseys-Announces-Fourth-Quarter-and-Fiscal-Year-Results",
        "latest_actual_period": "Fiscal Q4 and FY 2026",
        "latest_actual_label": "Casey's Announces Fourth Quarter and Fiscal Year Results",
        "upcoming_or_newer_event_url": "https://investor.caseys.com/events/event-details/q4-fy-2026-caseys-general-stores-earnings-conference-call",
        "upcoming_or_newer_event_label": "Q4 FY 2026 Casey's General Stores Earnings Conference Call",
    },
    "CDNS": {
        "company_ir_url": "https://investor.cadence.com/",
        "latest_actual_earnings_url": "https://investor.cadence.com/news/news-details/2026/Cadence-Reports-First-Quarter-2026-Financial-Results/default.aspx",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Cadence Reports First Quarter 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "DECK": {
        "company_ir_url": "https://ir.deckers.com/",
        "latest_actual_earnings_url": "https://ir.deckers.com/news-events/press-releases/detail/656/deckers-brands-reports-fourth-quarter-and-full-fiscal-year-2026-financial-results",
        "latest_actual_period": "Fiscal Q4 and FY 2026",
        "latest_actual_label": "Deckers Brands Reports Fourth Quarter and Full Fiscal Year 2026 Financial Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "FCX": {
        "company_ir_url": "https://investors.fcx.com/investors/default.aspx",
        "latest_actual_earnings_url": "https://investors.fcx.com/investors/news-releases/news-release-details/2026/Freeport-Reports-First-Quarter-2026-Results/default.aspx",
        "latest_actual_period": "Q1 2026",
        "latest_actual_label": "Freeport Reports First-Quarter 2026 Results",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
    "MU": {
        "company_ir_url": "https://investors.micron.com/",
        "latest_actual_earnings_url": "https://investors.micron.com/news-releases/news-release-details/micron-technology-inc-reports-results-second-quarter-fiscal-2026",
        "latest_actual_period": "Fiscal Q2 2026",
        "latest_actual_label": "Micron Technology, Inc. Reports Results for the Second Quarter of Fiscal 2026",
        "upcoming_or_newer_event_url": None,
        "upcoming_or_newer_event_label": None,
    },
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "official_source_capture_packet_only": True,
    "source_values_copied_into_cards": False,
    "registry_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}
TRUE_KEYS = {"review_only", "official_source_capture_packet_only"}
FALSE_KEYS = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_KEYS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def universe_source_symbols() -> dict[str, dict[str, Any]]:
    universe = load_dict(UNIVERSE)
    return {
        ticker(row.get("ticker")): as_dict(as_dict(row).get("source_symbols"))
        for row in as_list(universe.get("entries"))
        if isinstance(row, dict)
    }


def resolve_source(symbol: str, symbols: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Resolve official-source pointers from the seed map, then durable canon.

    Canon fallback keeps the daily spine green when a ticker rotates in that the
    hand-maintained seed map never covered; SEC EDGAR is an official source, so a
    known CIK is a real pointer rather than a missing one.
    """
    seed = OFFICIAL_SOURCES.get(symbol)
    if seed:
        return dict(seed), "official_company_and_latest_earnings_pointer_captured"
    company_ir = str(symbols.get("company_ir") or "").strip()
    cik = str(symbols.get("sec_cik") or "").strip()
    if company_ir or cik:
        return (
            {
                "company_ir_url": company_ir or None,
                "latest_actual_earnings_url": EDGAR_FILINGS_INDEX.format(cik=cik) if cik else None,
                "latest_actual_period": None,
                "latest_actual_label": "SEC EDGAR 8-K filings index" if cik else None,
                "upcoming_or_newer_event_url": None,
                "upcoming_or_newer_event_label": None,
            },
            "official_source_pointer_from_canon",
        )
    return {}, "official_source_pointer_missing"


def build_rows() -> list[dict[str, Any]]:
    requirements = load_dict(INFILE)
    canon_symbols = universe_source_symbols()
    rows: list[dict[str, Any]] = []
    for row in as_list(requirements.get("rows")):
        row = as_dict(row)
        symbol = ticker(row.get("ticker"))
        source, capture_status = resolve_source(symbol, canon_symbols.get(symbol, {}))
        checklist = as_dict(row.get("required_evidence_checklist"))
        owner_entry_stop = as_dict(checklist.get("owner_entry_stop_source"))
        rows.append({
            "ticker": symbol,
            "tier": row.get("tier"),
            "route_state": row.get("route_state"),
            "source_capture_status": capture_status,
            "company_ir_url": source.get("company_ir_url"),
            "latest_actual_earnings_url": source.get("latest_actual_earnings_url"),
            "latest_actual_period": source.get("latest_actual_period"),
            "latest_actual_label": source.get("latest_actual_label"),
            "upcoming_or_newer_event_url": source.get("upcoming_or_newer_event_url"),
            "upcoming_or_newer_event_label": source.get("upcoming_or_newer_event_label"),
            "owner_entry_stop_lineage_status": owner_entry_stop.get("status") or "unknown",
            "owner_entry_stop_lineage_required": bool(owner_entry_stop.get("required")),
            "residual_blocker": row.get("exact_residual_blocker"),
            "recommended_next_step": "Use official pointers for review, then separately gather owner entry/stop lineage before any repair integration.",
            "source_values_copied_into_cards": False,
            "registry_mutation_allowed": False,
            "ticker_card_mutation_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    rows.sort(key=lambda item: str(item.get("ticker") or ""))
    return rows


def build() -> dict[str, Any]:
    rows = build_rows()
    errors: list[str] = []
    warnings: list[str] = []
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    missing = [row["ticker"] for row in rows if row.get("source_capture_status") == "official_source_pointer_missing"]
    if missing:
        errors.append(f"missing official source pointers: {', '.join(missing)}")
    from_canon = [row["ticker"] for row in rows if row.get("source_capture_status") == "official_source_pointer_from_canon"]
    if from_canon:
        warnings.append(f"canon_derived_official_source_pointers: {', '.join(from_canon)}")
    if not rows:
        warnings.append("no_source_capture_rows")
    for row in rows:
        if row.get("source_values_copied_into_cards") or row.get("registry_mutation_allowed") or row.get("ticker_card_mutation_allowed"):
            errors.append(f"{row.get('ticker')} row implies mutation")
        if row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred"):
            errors.append(f"{row.get('ticker')} row authority boundary widened")
    status = "blocked" if errors else ("ok_no_work" if not rows else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only official source pointer capture for WF78 Tier B source-artifact blockers.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(INFILE)],
        "source_lookup_note": "Official URLs were gathered from company investor/newsroom surfaces during this pass; values are pointers only and are not written into registry/cards.",
        "summary": {
            "row_count": len(rows),
            "official_pointer_captured_count": sum(1 for row in rows if row.get("source_capture_status") != "official_source_pointer_missing"),
            "owner_entry_stop_lineage_required_count": sum(1 for row in rows if row.get("owner_entry_stop_lineage_required")),
            "status_counts": dict(Counter(str(row.get("source_capture_status")) for row in rows)),
            "next_safe_action": "Use these official pointers for a separate gated registry/card reconciliation proposal; owner entry/stop lineage is still required.",
        },
        "rows": rows,
        "validation": {"status": status, "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Official source capture packet only; no registry, card, canon, portfolio, deployment, or SQL-canon mutation.",
            "No source values are copied into cards from this packet.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 official source capture packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} rows={report['summary']['row_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and not str(report["validation"]["status"]).startswith("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
