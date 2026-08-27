#!/usr/bin/env python3
"""Build the WF78 100-ticker candidate-scope decision packet.

This packet prepares the research and import gate for expanding from the
current production 42 plus isolated pilot names toward a 100-name monitored
universe. It does not import tickers, write SQL, change production answer
paths, or make customer/portfolio/execution claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finance_production_scope import production_tickers as production_scope_tickers

TMP = ROOT / "tmp"
DATA = ROOT / "data"
DEFAULT_OUT = TMP / "wf78-100-ticker-candidate-scope-packet.json"
UNIVERSE = DATA / "finance" / "universe-v1.json"
PREFLIGHT_25 = TMP / "wf78-live-25-pilot-preflight.json"
SCHEMA_VERSION = "wf78_100_ticker_candidate_scope_packet.v1"

AUTHORITY_FALSE_FLAGS = {
    "owner_approval_inferred": False,
    "ticker_import_performed": False,
    "ticker_universe_write_allowed_by_this_packet": False,
    "sql_writes_allowed_by_this_packet": False,
    "production_answer_path_change_allowed": False,
    "sql_canon_expansion_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
}

CANDIDATE_BACKLOG = [
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "theme": "mega-cap platform hardware/services"},
    {"ticker": "COST", "name": "Costco Wholesale Corporation", "sector": "Consumer Staples", "theme": "defensive consumer quality"},
    {"ticker": "MA", "name": "Mastercard Incorporated", "sector": "Financials", "theme": "payments network"},
    {"ticker": "V", "name": "Visa Inc.", "sector": "Financials", "theme": "payments network"},
    {"ticker": "AXP", "name": "American Express Company", "sector": "Financials", "theme": "consumer credit/spending"},
    {"ticker": "ISRG", "name": "Intuitive Surgical, Inc.", "sector": "Health Care", "theme": "medical technology"},
    {"ticker": "TXN", "name": "Texas Instruments Incorporated", "sector": "Technology", "theme": "analog semiconductor cycle"},
    {"ticker": "QCOM", "name": "QUALCOMM Incorporated", "sector": "Technology", "theme": "mobile/edge semiconductor"},
    {"ticker": "MU", "name": "Micron Technology, Inc.", "sector": "Technology", "theme": "memory/AI infrastructure cycle"},
    {"ticker": "PANW", "name": "Palo Alto Networks, Inc.", "sector": "Technology", "theme": "cybersecurity leadership"},
    {"ticker": "SNOW", "name": "Snowflake Inc.", "sector": "Technology", "theme": "cloud data platform"},
    {"ticker": "CRWD", "name": "CrowdStrike Holdings, Inc.", "sector": "Technology", "theme": "cybersecurity growth"},
    {"ticker": "DDOG", "name": "Datadog, Inc.", "sector": "Technology", "theme": "cloud observability"},
    {"ticker": "MDB", "name": "MongoDB, Inc.", "sector": "Technology", "theme": "developer data infrastructure"},
    {"ticker": "DE", "name": "Deere & Company", "sector": "Industrials", "theme": "automation/agriculture capex"},
    {"ticker": "HON", "name": "Honeywell International Inc.", "sector": "Industrials", "theme": "industrial automation/aerospace"},
    {"ticker": "UNP", "name": "Union Pacific Corporation", "sector": "Industrials", "theme": "rail/freight cycle"},
    {"ticker": "URI", "name": "United Rentals, Inc.", "sector": "Industrials", "theme": "construction/industrial capex"},
    {"ticker": "EMR", "name": "Emerson Electric Co.", "sector": "Industrials", "theme": "automation/instrumentation"},
    {"ticker": "NOC", "name": "Northrop Grumman Corporation", "sector": "Industrials", "theme": "defense prime"},
    {"ticker": "GD", "name": "General Dynamics Corporation", "sector": "Industrials", "theme": "defense/aerospace"},
    {"ticker": "TDG", "name": "TransDigm Group Incorporated", "sector": "Industrials", "theme": "aerospace components"},
    {"ticker": "BA", "name": "The Boeing Company", "sector": "Industrials", "theme": "aerospace turnaround/high-risk monitor"},
    {"ticker": "SCCO", "name": "Southern Copper Corporation", "sector": "Materials", "theme": "copper/electrification"},
    {"ticker": "FCX", "name": "Freeport-McMoRan Inc.", "sector": "Materials", "theme": "copper/gold cycle"},
    {"ticker": "NUE", "name": "Nucor Corporation", "sector": "Materials", "theme": "steel/industrial cycle"},
    {"ticker": "SHW", "name": "The Sherwin-Williams Company", "sector": "Materials", "theme": "housing/industrial coatings"},
    {"ticker": "APD", "name": "Air Products and Chemicals, Inc.", "sector": "Materials", "theme": "industrial gases/hydrogen"},
    {"ticker": "NEE", "name": "NextEra Energy, Inc.", "sector": "Utilities", "theme": "renewables/grid/utility rates"},
    {"ticker": "CEG", "name": "Constellation Energy Corporation", "sector": "Utilities", "theme": "nuclear/data-center power"},
    {"ticker": "SO", "name": "The Southern Company", "sector": "Utilities", "theme": "regulated utility/power demand"},
    {"ticker": "DUK", "name": "Duke Energy Corporation", "sector": "Utilities", "theme": "regulated utility/grid capex"},
    {"ticker": "MPC", "name": "Marathon Petroleum Corporation", "sector": "Energy", "theme": "refining/downstream"},
    {"ticker": "EOG", "name": "EOG Resources, Inc.", "sector": "Energy", "theme": "E&P quality"},
    {"ticker": "SLB", "name": "SLB", "sector": "Energy", "theme": "oilfield services/global capex"},
    {"ticker": "COP", "name": "ConocoPhillips", "sector": "Energy", "theme": "large-cap E&P"},
    {"ticker": "AMGN", "name": "Amgen Inc.", "sector": "Health Care", "theme": "large-cap biotech"},
    {"ticker": "UNH", "name": "UnitedHealth Group Incorporated", "sector": "Health Care", "theme": "managed care/risk monitor"},
    {"ticker": "TMO", "name": "Thermo Fisher Scientific Inc.", "sector": "Health Care", "theme": "life-science tools"},
    {"ticker": "SYK", "name": "Stryker Corporation", "sector": "Health Care", "theme": "medtech quality"},
    {"ticker": "MCK", "name": "McKesson Corporation", "sector": "Health Care", "theme": "health-care distribution"},
    {"ticker": "WMT", "name": "Walmart Inc.", "sector": "Consumer Staples", "theme": "defensive retail/consumer health"},
    {"ticker": "PG", "name": "Procter & Gamble Company", "sector": "Consumer Staples", "theme": "consumer staples quality"},
    {"ticker": "PEP", "name": "PepsiCo, Inc.", "sector": "Consumer Staples", "theme": "staples/snacks/beverages"},
    {"ticker": "MCD", "name": "McDonald's Corporation", "sector": "Consumer Discretionary", "theme": "global consumer/value"},
    {"ticker": "HD", "name": "The Home Depot, Inc.", "sector": "Consumer Discretionary", "theme": "housing/renovation cycle"},
    {"ticker": "ORLY", "name": "O'Reilly Automotive, Inc.", "sector": "Consumer Discretionary", "theme": "auto aftermarket quality"},
    {"ticker": "NKE", "name": "NIKE, Inc.", "sector": "Consumer Discretionary", "theme": "consumer brand turnaround"},
    {"ticker": "DIS", "name": "The Walt Disney Company", "sector": "Communication Services", "theme": "media/parks/streaming"},
    {"ticker": "SPOT", "name": "Spotify Technology S.A.", "sector": "Communication Services", "theme": "audio platform"},
    {"ticker": "TTD", "name": "The Trade Desk, Inc.", "sector": "Communication Services", "theme": "ad-tech growth"},
    {"ticker": "BX", "name": "Blackstone Inc.", "sector": "Financials", "theme": "alternatives/private markets"},
    {"ticker": "KKR", "name": "KKR & Co. Inc.", "sector": "Financials", "theme": "alternatives/private markets"},
    {"ticker": "MS", "name": "Morgan Stanley", "sector": "Financials", "theme": "wealth/investment banking"},
    {"ticker": "BLK", "name": "BlackRock, Inc.", "sector": "Financials", "theme": "asset management/ETF flows"},
    {"ticker": "SCHW", "name": "The Charles Schwab Corporation", "sector": "Financials", "theme": "brokerage/wealth"},
    {"ticker": "AMT", "name": "American Tower Corporation", "sector": "Real Estate", "theme": "tower REIT/rates"},
    {"ticker": "PLD", "name": "Prologis, Inc.", "sector": "Real Estate", "theme": "logistics real estate"},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def universe_rows() -> list[dict[str, Any]]:
    rows = load_json(UNIVERSE).get("entries")
    return rows if isinstance(rows, list) else []


def current_tickers() -> set[str]:
    migrated = set(production_scope_tickers())
    if migrated:
        return migrated
    return {
        str(row.get("ticker")).upper()
        for row in universe_rows()
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("production_scope") is True
    }


def pilot_tickers() -> set[str]:
    return {
        str(row.get("ticker")).upper()
        for row in universe_rows()
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope") == "pilot_fixture"
    }


def preflight_candidates() -> list[dict[str, Any]]:
    rows = load_json(PREFLIGHT_25).get("candidate_symbols")
    return rows if isinstance(rows, list) else []


def build_packet() -> dict[str, Any]:
    production = current_tickers()
    pilot = pilot_tickers()
    existing = production | pilot
    preflight = [row for row in preflight_candidates() if isinstance(row, dict)]
    preflight_by_ticker = {str(row.get("ticker")).upper(): row for row in preflight}

    seed_rows: list[dict[str, Any]] = []
    for ticker, row in sorted(preflight_by_ticker.items()):
        if ticker and ticker not in production:
            seed_rows.append({
                "ticker": ticker,
                "name": row.get("name"),
                "sector": row.get("sector"),
                "source": "wf78_live_25_pilot_preflight",
                "theme": row.get("rationale"),
                "proposed_tier": "C",
                "decision_grade_eligible": False,
            })
    for row in CANDIDATE_BACKLOG:
        ticker = row["ticker"].upper()
        if ticker in existing or ticker in {item["ticker"] for item in seed_rows}:
            continue
        seed_rows.append({
            **row,
            "source": "sector_leadership_gap_backlog",
            "proposed_tier": "C",
            "decision_grade_eligible": False,
        })

    target_new = 58
    proposed_new = seed_rows[:target_new]
    proposed_total = len(production) + len(proposed_new)
    sector_counts = Counter(row.get("sector") or "Unknown" for row in proposed_new)
    checks = {
        "production_base_is_42": len(production) == 42,
        "candidate_new_count_is_58": len(proposed_new) == target_new,
        "target_total_is_100": proposed_total == 100,
        "no_production_overlap": not (production & {row["ticker"] for row in proposed_new}),
        "no_duplicates": len({row["ticker"] for row in proposed_new}) == len(proposed_new),
        "all_review_only_tier_c": all(row.get("proposed_tier") == "C" and row.get("decision_grade_eligible") is False for row in proposed_new),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ready_for_100_candidate_scope_review" if not blockers else "blocked",
        "authority_boundary": {
            "posture": "candidate_scope_packet_only_no_import_no_sql_writes_no_customer_or_execution_authority",
            **AUTHORITY_FALSE_FLAGS,
        },
        **AUTHORITY_FALSE_FLAGS,
        "checks": checks,
        "blockers": blockers,
        "target_scope": {
            "current_production_count": len(production),
            "new_candidate_count": len(proposed_new),
            "target_total_monitored_count": proposed_total,
            "candidate_policy": "Tier C thin monitor rows first; no production answer path and no decision-grade promotion from this packet.",
        },
        "research_needed_before_import": [
            "fresh provider/runtime proof for all 58 proposed new tickers",
            "source/licensing check for provider redistribution and customer-facing use",
            "sector/industry classification review",
            "official IR/SEC source route for any future material claims",
            "thin-row metadata only: ticker, name, sector, theme, provider status, source-open requirement",
            "production-42 A/B no-regression proof before and after any import",
            "backup/rollback packet for universe registry and finance SQL state",
        ],
        "sector_leadership_rationale": {
            "summary": "Broaden from AI/industrial/portfolio-heavy coverage into payments, health care, utilities/power, consumer quality, defense, energy, materials, real estate, and alternatives.",
            "new_candidate_sector_counts": dict(sorted(sector_counts.items())),
        },
        "proposed_new_candidates": proposed_new,
        "excluded_from_scope": [
            "recommendation/deployment/action-state fields",
            "entry bands/stops for new names until source-open proof exists",
            "portfolio/canon note mutation",
            "customer/retail answer output",
            "paper/live/account/trade authority",
            "ticker import/write execution",
        ],
        "required_next_packet_before_import": {
            "name": "WF78 100-name import packet",
            "must_include": [
                "exact candidate list hash",
                "provider/runtime budget proof",
                "backup manifest",
                "rollback route",
                "SQL row shape",
                "A/B production-42 no-regression proof",
                "post-import validators",
                "owner approval reference",
            ],
        },
        "validator_commands": [
            "python scripts\\wf78_100_ticker_candidate_scope_packet.py --write --validate",
            "python scripts\\sql_500_ticker_expansion_design_gate.py --write --validate",
            "python scripts\\sql_retail_expansion_phase_gate.py --write --validate",
            "python scripts\\artifact_index.py validate",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    payload = build_packet()
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    if args.validate:
        drifted = [key for key, expected in AUTHORITY_FALSE_FLAGS.items() if payload.get(key) is not expected]
        if drifted:
            raise SystemExit(f"authority false flag drift: {drifted}")
        if payload["status"] != "ready_for_100_candidate_scope_review":
            raise SystemExit(f"candidate scope blocked: {payload['blockers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


