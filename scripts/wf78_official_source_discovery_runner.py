#!/usr/bin/env python3
"""Discover official-source candidates for WF78 source-capture blockers.

This is a review-only discovery packet. It uses current blocker requirements,
existing registry rows, ticker cards, and the known official-source seed map to
produce source candidates. It does not mutate the official registry, cards,
canon, portfolio, deployment surfaces, SQL canon, or execution/account surfaces.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_official_source_capture_packet import OFFICIAL_SOURCES

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REQUIREMENTS = TMP / "wf78-source-capture-requirements-queue.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
OUT = TMP / "wf78-official-source-discovery.json"
SCHEMA = "veritas.wf78_official_source_discovery.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "official_source_discovery_only": True,
    "registry_mutation_allowed": False,
    "source_values_copied_into_cards": False,
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
TRUE_KEYS = {"review_only", "official_source_discovery_only"}
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


def card_for(symbol: str) -> dict[str, Any]:
    return load_dict(CARD_DIR / f"{symbol}.current.json")


def source_symbols(card: dict[str, Any]) -> dict[str, Any]:
    return as_dict(as_dict(card.get("universe_metadata")).get("source_symbols"))


def registry_rows() -> dict[str, dict[str, Any]]:
    registry = load_dict(REGISTRY)
    return {ticker(symbol): as_dict(row) for symbol, row in as_dict(registry.get("tickers")).items()}


def row_requirements(row: dict[str, Any]) -> dict[str, Any]:
    checklist = as_dict(row.get("required_evidence_checklist"))
    return {
        "company_ir_required": as_dict(checklist.get("company_ir_url")).get("status") == "missing",
        "latest_earnings_source_required": bool(as_dict(checklist.get("latest_earnings_source")).get("required")),
        "owner_entry_stop_source_required": bool(as_dict(checklist.get("owner_entry_stop_source")).get("required")),
        "registry_entry_needed": bool(as_dict(checklist.get("registry_entry")).get("entry_needed")),
    }


def discovery_for(row: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    symbol = ticker(row.get("ticker"))
    card = card_for(symbol)
    symbols = source_symbols(card)
    registry_row = registry.get(symbol, {})
    seed = OFFICIAL_SOURCES.get(symbol, {})
    requirements = row_requirements(row)

    if registry_row.get("official_earnings_source_url"):
        confidence = "official_registry_existing"
        source = {
            "company_ir_url": symbols.get("company_ir") or seed.get("company_ir_url"),
            "official_earnings_source_url": registry_row.get("official_earnings_source_url"),
            "source_label": registry_row.get("source_label"),
            "period_label": registry_row.get("period_label"),
            "source_section": registry_row.get("source_section"),
        }
        proposal_needed = False
    elif seed.get("latest_actual_earnings_url"):
        confidence = "official_exact"
        source = {
            "company_ir_url": seed.get("company_ir_url"),
            "official_earnings_source_url": seed.get("latest_actual_earnings_url"),
            "source_label": seed.get("latest_actual_label"),
            "period_label": seed.get("latest_actual_period"),
            "source_section": "official earnings release",
            "upcoming_or_newer_event_url": seed.get("upcoming_or_newer_event_url"),
            "upcoming_or_newer_event_label": seed.get("upcoming_or_newer_event_label"),
        }
        proposal_needed = True
    elif symbols.get("company_ir"):
        confidence = "official_index_page"
        source = {
            "company_ir_url": symbols.get("company_ir"),
            "official_earnings_source_url": None,
            "source_label": None,
            "period_label": None,
            "source_section": "company investor relations index",
        }
        proposal_needed = True
    else:
        confidence = "not_found"
        source = {
            "company_ir_url": None,
            "official_earnings_source_url": None,
            "source_label": None,
            "period_label": None,
            "source_section": None,
        }
        proposal_needed = False

    return {
        "ticker": symbol,
        "tier": row.get("tier"),
        "route_state": row.get("route_state"),
        "discovery_confidence": confidence,
        "source_candidate": source,
        "requirements": requirements,
        "registry_proposal_needed": proposal_needed,
        "owner_entry_stop_lineage_still_required": requirements["owner_entry_stop_source_required"],
        "source_values_copied_into_cards": False,
        "registry_mutation_allowed": False,
        "ticker_card_mutation_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def build() -> dict[str, Any]:
    requirements = load_dict(REQUIREMENTS)
    registry = registry_rows()
    rows = [discovery_for(as_dict(row), registry) for row in as_list(requirements.get("rows"))]
    errors: list[str] = []
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    for row in rows:
        if row.get("registry_mutation_allowed") or row.get("ticker_card_mutation_allowed") or row.get("source_values_copied_into_cards"):
            errors.append(f"{row.get('ticker')} row implies mutation")
        if row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred"):
            errors.append(f"{row.get('ticker')} authority boundary widened")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only official source discovery for WF78 source-capture blockers.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(REQUIREMENTS), rel(REGISTRY)],
        "summary": {
            "row_count": len(rows),
            "confidence_counts": dict(Counter(str(row.get("discovery_confidence")) for row in rows)),
            "registry_proposal_needed_count": sum(1 for row in rows if row.get("registry_proposal_needed")),
            "owner_entry_stop_lineage_still_required_count": sum(1 for row in rows if row.get("owner_entry_stop_lineage_still_required")),
            "next_safe_action": "Build a registry proposal from official_exact rows; keep owner entry/stop lineage separate and promotion-only.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Discovery only; no official registry, card, canon, portfolio, deployment, or SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 official source discovery packet.")
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
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
