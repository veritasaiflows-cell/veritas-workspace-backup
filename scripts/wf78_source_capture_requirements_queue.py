#!/usr/bin/env python3
"""Build a review-only WF78 source-capture requirements queue.

This queue consumes the WF78 source-artifact capture review artifact, current
ticker cards, and the optional official source registry. It reports what
evidence is required for each blocker without copying source values into cards
or mutating any owner, canon, portfolio, SQL, deployment, brokerage, or
execution surface.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SOURCE_CAPTURE_REVIEW = TMP / "wf78-source-artifact-capture-review.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
OUT = TMP / "wf78-source-capture-requirements-queue.json"
SCHEMA = "veritas.wf78_source_capture_requirements_queue.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "source_capture_requirements_queue_only": True,
    "hard_false_authority_boundary": True,
    "automated_non_capital_work_routing_allowed": True,
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

TRUE_AUTHORITY_KEYS = {
    "review_only",
    "source_capture_requirements_queue_only",
    "hard_false_authority_boundary",
    "automated_non_capital_work_routing_allowed",
}
FALSE_AUTHORITY_KEYS = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY_KEYS}

ROW_FALSE_AUTHORITY_KEYS = {
    "source_value_copy_allowed",
    "ticker_card_mutation_allowed",
    "capital_deployment_allowed",
    "trade_or_execution_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
}

FORBIDDEN_ROW_ACTION_TERMS = {
    "apply",
    "approve",
    "approved",
    "approval",
    "buy",
    "sell",
    "submit",
    "execute",
    "execution",
    "mutate",
    "mutation",
    "trade",
    "order",
    "deploy capital",
    "portfolio update",
    "canon update",
}

STOP_LINES = [
    "Review-only requirements queue; no ticker-card, registry, canon, portfolio, deployment, SQL-canon, or owner-note mutation.",
    "Do not copy source values from this artifact into cards; capture and reconciliation require a separate gated integration pass.",
    "No capital deployment, trade/order execution, paper/live brokerage action, account action, money movement, or inferred owner approval.",
]


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


def norm_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def registry_tickers(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        norm_ticker(symbol): as_dict(row)
        for symbol, row in as_dict(registry.get("tickers")).items()
        if norm_ticker(symbol)
    }


def review_rows(review: dict[str, Any]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in as_list(review.get("rows")):
        row = as_dict(row)
        ticker = norm_ticker(row.get("ticker"))
        if ticker:
            rows[ticker] = row
    return sorted(rows.values(), key=lambda row: (str(row.get("tier") or ""), norm_ticker(row.get("ticker"))))


def source_symbols(card: dict[str, Any]) -> dict[str, Any]:
    universe = as_dict(card.get("universe_metadata"))
    symbols = as_dict(universe.get("source_symbols"))
    return {
        "yfinance": symbols.get("yfinance"),
        "sec_cik": symbols.get("sec_cik"),
        "company_ir": symbols.get("company_ir"),
    }


def universe_metadata(card: dict[str, Any]) -> dict[str, Any]:
    universe = as_dict(card.get("universe_metadata"))
    return {
        "name": universe.get("name"),
        "instrument_type": universe.get("instrument_type") or card.get("instrument_type"),
        "sector": universe.get("sector"),
        "industry": universe.get("industry"),
        "universe_scope": universe.get("universe_scope"),
        "monitoring_role": universe.get("monitoring_role"),
        "source_symbols": source_symbols(card),
    }


def company_ir_status(card: dict[str, Any], registry_row: dict[str, Any], review_row: dict[str, Any]) -> dict[str, Any]:
    symbols = source_symbols(card)
    card_ir = first_text(symbols.get("company_ir"))
    review_ir = first_text(review_row.get("ir_url"))
    registry_url = first_text(registry_row.get("official_earnings_source_url"))
    if card_ir:
        status = "present_in_card_source_symbols"
    elif review_ir:
        status = "present_in_source_capture_review"
    elif registry_url:
        status = "registry_official_earnings_url_present_but_company_ir_missing"
    else:
        status = "missing"
    return {
        "status": status,
        "company_ir_url_present": bool(card_ir or review_ir),
        "card_source_symbols_company_ir_present": bool(card_ir),
        "source_capture_review_ir_url_present": bool(review_ir),
        "registry_official_url_present": bool(registry_url),
    }


def latest_earnings_source_status(card: dict[str, Any], registry_row: dict[str, Any]) -> dict[str, Any]:
    earnings = as_dict(card.get("latest_earnings_performance"))
    official_fields = (
        "official_adjusted_eps",
        "official_growth_bridge",
        "official_guidance",
        "management_explanation",
    )
    present_fields: list[str] = []
    missing_fields: list[str] = []
    for field in official_fields:
        status = str(as_dict(earnings.get(field)).get("status") or "")
        if status == "available":
            present_fields.append(field)
        else:
            missing_fields.append(field)
    registry_present = bool(first_text(registry_row.get("official_earnings_source_url")))
    required = bool(missing_fields or not registry_present)
    if not earnings:
        status = "card_latest_earnings_section_missing"
    elif registry_present and not missing_fields:
        status = "official_latest_earnings_source_pointer_present"
    elif registry_present:
        status = "registry_pointer_present_manual_capture_still_required"
    else:
        status = "official_latest_earnings_source_required"
    return {
        "status": status,
        "required": required,
        "registry_entry_present": registry_present,
        "official_capture_fields_present": present_fields,
        "official_capture_fields_missing_or_manual": missing_fields,
    }


def owner_entry_stop_source_status(card: dict[str, Any], review_row: dict[str, Any]) -> dict[str, Any]:
    review_lineage = as_dict(review_row.get("source_lineage_availability"))
    card_reference = as_dict(card.get("entry_stop_reference_metadata"))
    card_lineage = as_dict(card_reference.get("source_lineage"))
    owner_path = first_text(review_lineage.get("owner_source_path"), card_lineage.get("owner_source_path"))
    timestamp = first_text(review_lineage.get("source_timestamp"), card_lineage.get("source_timestamp"))
    sha256 = first_text(review_lineage.get("source_sha256"), card_lineage.get("source_sha256"))
    available = bool(review_lineage.get("available")) or bool(owner_path and timestamp and sha256)
    return {
        "status": "present" if available else "required",
        "required": not available,
        "entry_stop_reference_status": first_text(
            review_row.get("entry_stop_reference_status"),
            card_reference.get("status"),
        ) or "missing",
        "owner_source_path_present": bool(owner_path),
        "source_timestamp_present": bool(timestamp),
        "source_sha256_present": bool(sha256),
    }


def registry_status(registry_row: dict[str, Any]) -> dict[str, Any]:
    present = bool(registry_row)
    return {
        "present": present,
        "entry_needed": not present,
        "registry_path": rel(REGISTRY),
        "has_official_earnings_source_url": bool(first_text(registry_row.get("official_earnings_source_url"))),
        "has_source_label": bool(first_text(registry_row.get("source_label"))),
        "has_period_label": bool(first_text(registry_row.get("period_label"))),
        "has_source_section": bool(first_text(registry_row.get("source_section"))),
    }


def residual_blocker(review_row: dict[str, Any], requirements: dict[str, dict[str, Any]]) -> str:
    review_blocker = first_text(review_row.get("residual_blocker"))
    if review_blocker:
        return review_blocker
    missing: list[str] = []
    if as_dict(requirements.get("registry_entry")).get("entry_needed"):
        missing.append("registry_entry_missing")
    if as_dict(requirements.get("latest_earnings_source")).get("required"):
        missing.append("latest_earnings_source_required")
    if as_dict(requirements.get("owner_entry_stop_source")).get("required"):
        missing.append("owner_entry_stop_source_required")
    if as_dict(requirements.get("company_ir_url")).get("status") == "missing":
        missing.append("company_ir_url_missing")
    return "none" if not missing else "+".join(missing)


def proposed_next_step(ticker: str, requirements: dict[str, dict[str, Any]]) -> str:
    needed: list[str] = []
    if as_dict(requirements.get("company_ir_url")).get("status") == "missing":
        needed.append("company IR URL")
    if as_dict(requirements.get("latest_earnings_source")).get("required"):
        needed.append("latest earnings source pointer")
    if as_dict(requirements.get("owner_entry_stop_source")).get("required"):
        needed.append("owner entry/stop source lineage")
    if as_dict(requirements.get("registry_entry")).get("entry_needed"):
        needed.append("official registry entry")
    if not needed:
        return f"Review {ticker} evidence pointers for consistency; keep this queue review-only and do not copy values into cards."
    return (
        f"Open official IR and owner evidence for {ticker}; capture required pointers for review only: "
        f"{', '.join(needed)}. Keep card, registry, canon, and portfolio files unchanged in this queue."
    )


def row_for(review_row: dict[str, Any], registry_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ticker = norm_ticker(review_row.get("ticker"))
    path = card_path(ticker)
    card = load_dict(path)
    registry_row = registry_rows.get(ticker, {})
    requirements = {
        "company_ir_url": company_ir_status(card, registry_row, review_row),
        "latest_earnings_source": latest_earnings_source_status(card, registry_row),
        "owner_entry_stop_source": owner_entry_stop_source_status(card, review_row),
        "registry_entry": registry_status(registry_row),
    }
    blocker = residual_blocker(review_row, requirements)
    return {
        "ticker": ticker,
        "tier": review_row.get("tier"),
        "route_state": review_row.get("route_state"),
        "packet_id": review_row.get("packet_id"),
        "repair_disposition": review_row.get("repair_disposition"),
        "card": {
            "available": bool(card),
            "path": rel(path),
        },
        "universe_source_symbol_metadata": universe_metadata(card) if card else {},
        "required_evidence_checklist": requirements,
        "exact_residual_blocker": blocker,
        "proposed_non_mutating_next_step": proposed_next_step(ticker, requirements),
        "no_source_value_copying": True,
        "source_value_copy_allowed": False,
        "ticker_card_mutation_allowed": False,
        "capital_deployment_allowed": False,
        "trade_or_execution_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "owner_approval_inferred": False,
    }


def row_implies_forbidden_action(row: dict[str, Any]) -> str | None:
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("proposed_non_mutating_next_step", "exact_residual_blocker", "repair_disposition")
    )
    for term in sorted(FORBIDDEN_ROW_ACTION_TERMS):
        if term in text:
            return term
    return None


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if artifact.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    authority = as_dict(artifact.get("authority_boundary"))
    for key in sorted(TRUE_AUTHORITY_KEYS):
        if authority.get(key) is not True:
            errors.append(f"authority_not_true:{key}")
    for key in sorted(FALSE_AUTHORITY_KEYS):
        if authority.get(key) is not False:
            errors.append(f"authority_not_false:{key}")
    rows = [as_dict(row) for row in as_list(artifact.get("rows"))]
    if not rows:
        return {"status": "ok_no_work", "errors": [], "warnings": ["rows_empty"]}
    for row in rows:
        ticker = norm_ticker(row.get("ticker"))
        if not ticker:
            errors.append("row_missing_ticker")
        for key in sorted(ROW_FALSE_AUTHORITY_KEYS):
            if row.get(key) is not False:
                errors.append(f"row_authority_not_false:{ticker or 'unknown'}:{key}")
        if row.get("no_source_value_copying") is not True:
            errors.append(f"row_no_source_value_copying_not_true:{ticker or 'unknown'}")
        forbidden = row_implies_forbidden_action(row)
        if forbidden:
            errors.append(f"row_implies_forbidden_action:{ticker or 'unknown'}:{forbidden}")
        checklist = as_dict(row.get("required_evidence_checklist"))
        for required_key in ("company_ir_url", "latest_earnings_source", "owner_entry_stop_source", "registry_entry"):
            if required_key not in checklist:
                errors.append(f"row_missing_checklist_item:{ticker or 'unknown'}:{required_key}")
        if not as_dict(row.get("card")).get("available"):
            warnings.append(f"card_missing:{ticker}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build() -> dict[str, Any]:
    review = load_dict(SOURCE_CAPTURE_REVIEW)
    registry = load_dict(REGISTRY)
    registry_rows = registry_tickers(registry)
    rows = [row_for(row, registry_rows) for row in review_rows(review)]

    tier_counts = Counter(str(row.get("tier") or "unknown") for row in rows)
    blocker_counts = Counter(str(row.get("exact_residual_blocker") or "unknown") for row in rows)
    company_ir_counts = Counter(
        str(as_dict(as_dict(row.get("required_evidence_checklist")).get("company_ir_url")).get("status") or "unknown")
        for row in rows
    )

    latest_required = sum(
        1
        for row in rows
        if as_dict(as_dict(row.get("required_evidence_checklist")).get("latest_earnings_source")).get("required")
    )
    owner_entry_stop_required = sum(
        1
        for row in rows
        if as_dict(as_dict(row.get("required_evidence_checklist")).get("owner_entry_stop_source")).get("required")
    )
    registry_needed = sum(
        1
        for row in rows
        if as_dict(as_dict(row.get("required_evidence_checklist")).get("registry_entry")).get("entry_needed")
    )
    card_available = sum(1 for row in rows if as_dict(row.get("card")).get("available"))

    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Review-only WF78 source-capture requirements queue for source-artifact blockers.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "source_capture_review_path": rel(SOURCE_CAPTURE_REVIEW),
            "ticker_card_glob": rel(CARD_DIR / "*.current.json"),
            "official_registry_path": rel(REGISTRY),
            "official_registry_loaded": bool(registry),
        },
        "summary": {
            "row_count": len(rows),
            "ticker_count": len({row.get("ticker") for row in rows}),
            "tier_counts": dict(tier_counts),
            "card_available_count": card_available,
            "card_missing_count": len(rows) - card_available,
            "company_ir_url_status_counts": dict(company_ir_counts),
            "latest_earnings_source_required_count": latest_required,
            "owner_entry_stop_source_required_count": owner_entry_stop_required,
            "registry_entry_needed_count": registry_needed,
            "residual_blocker_counts": dict(blocker_counts),
            "source_values_copied_into_cards": False,
            "next_safe_action": "Use this queue to gather required source pointers in a separate review pass; do not mutate cards, registry, canon, portfolio, or execution surfaces.",
        },
        "rows": rows,
        "stop_lines": STOP_LINES,
    }
    artifact["validation"] = validate_artifact(artifact)
    artifact["status"] = artifact["validation"]["status"]
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the requirements queue artifact to disk.")
    parser.add_argument("--validate", action="store_true", help="Fail if the generated artifact does not validate.")
    parser.add_argument("--out", default=str(OUT), help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = build()
    out_path = Path(args.out)
    if args.write:
        atomic_write_json(out_path, artifact)
    validation = artifact["validation"]
    if args.validate and not str(validation["status"]).startswith("ok"):
        for error in validation["errors"]:
            print(error)
        return 1
    print(
        f"{validation['status']}: rows={artifact['summary']['row_count']} "
        f"registry_needed={artifact['summary']['registry_entry_needed_count']} "
        f"latest_required={artifact['summary']['latest_earnings_source_required_count']} "
        f"owner_entry_stop_required={artifact['summary']['owner_entry_stop_source_required_count']} "
        f"out={rel(out_path) if args.write else '<not-written>'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
