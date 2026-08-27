#!/usr/bin/env python3
"""Read-only strategic production scope helpers.

This module is the replacement runtime helper for finance consumers that used
the retired 42-name shadow reader. It reads the SQL-canon typed access layer and
returns only the current proof-joined strategic production set. Empty is a valid
wait state when Tier A/A-READY proof is not decision-grade yet.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import FinanceSqlCanonAccess, SecurityState
from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "finance-production-scope.json"
SCHEMA = "veritas.finance_production_scope.v1"

AUTHORITY_BOUNDARY = {
    "read_only": True,
    "strategic_production_scope_only": True,
    "sql_write_allowed": False,
    "router_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _client(client: FinanceSqlCanonAccess | None = None) -> FinanceSqlCanonAccess:
    return client or FinanceSqlCanonAccess()


def _state_to_entry(state: SecurityState) -> dict[str, Any]:
    row = asdict(state) if is_dataclass(state) else dict(vars(state))
    row["active"] = True
    row["universe_scope"] = "strategic_production_grade"
    row["production_scope"] = True
    row["strategic_production_scope"] = "sql_tier_a_ready_proof_joined"
    row["source"] = "finance_sql_canon_access.production_answer_tickers"
    row["capital_deployment_approved"] = False
    row["trade_or_execution_approved"] = False
    return row


def production_tickers(*, client: FinanceSqlCanonAccess | None = None) -> list[str]:
    return sorted(_client(client).production_answer_tickers())


def production_entries(*, client: FinanceSqlCanonAccess | None = None) -> list[dict[str, Any]]:
    canon = _client(client)
    tickers = production_tickers(client=canon)
    states = canon.ticker_states(tickers)
    return [_state_to_entry(states[ticker]) for ticker in tickers if ticker in states]


def source_summary(*, client: FinanceSqlCanonAccess | None = None) -> dict[str, Any]:
    canon = _client(client)
    tickers = production_tickers(client=canon)
    return {
        "preferred_source": "finance_sql_canon_access.production_answer_tickers",
        "production_scope_definition": "proof_joined_sql_tier_a_ready",
        "production_ticker_count": len(tickers),
        "production_tickers": tickers,
        "empty_scope_is_valid_wait_state": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def build_packet() -> dict[str, Any]:
    entries = production_entries()
    tickers = [str(row.get("ticker")) for row in entries if row.get("ticker")]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Strategic production scope proof for consumers cut over from retired 42-name helper.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "production_ticker_count": len(tickers),
            "production_tickers": tickers,
            "empty_scope_is_valid_wait_state": True,
            "next_safe_action": "Use this helper for review-only strategic production scope; do not infer approval or execution authority.",
        },
        "entries": entries,
        "source_summary": source_summary(),
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = packet.get("authority_boundary") if isinstance(packet.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    if packet.get("status") != "ok":
        errors.append(f"unexpected_status:{packet.get('status')}")
    return sorted(errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet()
    errors = validate_packet(packet) if args.validate else []
    packet["validation"] = {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}
    if args.write:
        atomic_write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out) if args.write else None,
                "production_ticker_count": packet["summary"]["production_ticker_count"],
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
