#!/usr/bin/env python3
"""Build a not-applied official registry proposal from WF78 discovery output."""
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
DISCOVERY = TMP / "wf78-official-source-discovery.json"
REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
OUT = TMP / "wf78-official-registry-proposal.json"
SCHEMA = "veritas.wf78_official_registry_proposal.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "registry_proposal_only": True,
    "proposal_applied": False,
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
TRUE_KEYS = {"review_only", "registry_proposal_only"}
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


def existing_registry() -> dict[str, dict[str, Any]]:
    registry = load_dict(REGISTRY)
    return {ticker(symbol): as_dict(row) for symbol, row in as_dict(registry.get("tickers")).items()}


def proposal_row(row: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    symbol = ticker(row.get("ticker"))
    candidate = as_dict(row.get("source_candidate"))
    existing = registry.get(symbol)
    has_existing = bool(existing)
    if has_existing:
        action = "no_change_existing_registry_row"
    elif row.get("discovery_confidence") == "official_exact" and candidate.get("official_earnings_source_url"):
        action = "propose_add_registry_row"
    elif row.get("discovery_confidence") == "official_index_page":
        action = "manual_review_required_index_only"
    else:
        action = "manual_review_required_not_found"
    return {
        "ticker": symbol,
        "proposal_action": action,
        "proposal_applied": False,
        "conflict_status": "existing_registry_row_present" if has_existing else "no_existing_registry_row",
        "discovery_confidence": row.get("discovery_confidence"),
        "proposed_registry_row": {
            "official_earnings_source_url": candidate.get("official_earnings_source_url"),
            "source_label": candidate.get("source_label"),
            "period_label": candidate.get("period_label"),
            "source_section": candidate.get("source_section"),
        },
        "supporting_company_ir_url": candidate.get("company_ir_url"),
        "owner_entry_stop_lineage_still_required": row.get("owner_entry_stop_lineage_still_required"),
        "registry_mutation_allowed": False,
        "ticker_card_mutation_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def build() -> dict[str, Any]:
    discovery = load_dict(DISCOVERY)
    registry = existing_registry()
    rows = [proposal_row(as_dict(row), registry) for row in as_list(discovery.get("rows"))]
    errors: list[str] = []
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    for row in rows:
        if row.get("registry_mutation_allowed") or row.get("ticker_card_mutation_allowed") or row.get("proposal_applied"):
            errors.append(f"{row.get('ticker')} row implies apply/mutation")
        if row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred"):
            errors.append(f"{row.get('ticker')} authority boundary widened")
    action_counts = Counter(str(row.get("proposal_action")) for row in rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only official registry proposal; not applied.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(DISCOVERY), rel(REGISTRY)],
        "summary": {
            "row_count": len(rows),
            "proposal_action_counts": dict(action_counts),
            "add_registry_row_count": action_counts.get("propose_add_registry_row", 0),
            "manual_review_count": action_counts.get("manual_review_required_index_only", 0) + action_counts.get("manual_review_required_not_found", 0),
            "owner_entry_stop_lineage_still_required_count": sum(1 for row in rows if row.get("owner_entry_stop_lineage_still_required")),
            "next_safe_action": "If approved through a separate gated apply path, add conflict-free registry rows; do not solve owner entry/stop lineage here.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Registry proposal only; no registry/card/canon/portfolio/deployment/SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 official registry proposal.")
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
