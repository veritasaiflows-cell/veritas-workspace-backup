#!/usr/bin/env python3
"""Report-only diff between the live WF78 production-scope proof join and its inputs.

The join itself lives in `finance_sql_canon.resolve_production_scope` and is imported here
rather than reimplemented, so this script cannot drift into a second definition of
production scope. What it adds is per-gate attribution: which gate blocks each name, and
how the routing-tier authority compares against the derived coverage obligation tier.

This writes nothing to SQL canon, the registry, or any card.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sqlite3
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finance_sql_canon import (  # noqa: E402
    PROOF_JOIN_CONFIDENCE_STATUS,
    PROOF_JOIN_FRESH_STATES,
    PROOF_JOIN_TIERS,
    load_proof_join_freshness,
    load_proof_join_routing,
    normalize_routing_tier,
    resolve_production_scope,
)

TMP = ROOT / "tmp"
REGISTRY = ROOT / "data" / "finance" / "universe-v1.json"
COVERAGE = TMP / "finance-data-coverage-current.json"
CARDS = TMP / "ticker-intelligence-cards"
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_OUT = TMP / "wf78-production-scope-proof-join-shadow.json"

OBLIGATION_TIERS = {"A", "B"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"required input missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def live_production_tickers() -> set[str]:
    if not DB_PATH.exists():
        return set()
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        return {
            str(row[0]).upper()
            for row in conn.execute(
                "SELECT ticker FROM universe_membership WHERE production_scope_member=1"
            )
        }


def build_rows() -> list[dict[str, Any]]:
    registry = load_json(REGISTRY)
    coverage = load_json(COVERAGE)
    coverage_tickers = set((coverage.get("ticker_coverage") or {}).keys())
    freshness_rows = load_proof_join_freshness()
    routing_rows = load_proof_join_routing()

    rows: list[dict[str, Any]] = []
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict) or entry.get("active") is not True:
            continue
        ticker = str(entry.get("ticker", "")).upper()
        fresh = (freshness_rows or {}).get(ticker, {})
        routing = (routing_rows or {}).get(ticker, {})
        obligation_tier = normalize_routing_tier(entry.get("tier")) or "C"
        member, source = resolve_production_scope(
            ticker,
            freshness_rows,
            routing_rows,
            in_coverage=ticker in coverage_tickers,
            card_exists=(CARDS / f"{ticker}.current.json").exists(),
        )
        rows.append(
            {
                "ticker": ticker,
                "coverage_obligation_tier": obligation_tier,
                "routing_auto_tier": normalize_routing_tier(fresh.get("auto_tier")),
                "routing_auto_state": routing.get("auto_state"),
                "resolution_state": fresh.get("resolution_state"),
                "critical_data_conflict_count": routing.get("critical_data_conflict_count"),
                "tier_a_confidence_status": routing.get("tier_a_confidence_status"),
                "registry_decision_grade_eligible": bool(entry.get("decision_grade_eligible")),
                "obligation_tier_ab": obligation_tier in OBLIGATION_TIERS,
                "production_scope_member": member,
                "production_scope_source": source,
            }
        )
    return rows


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    joined = {r["ticker"] for r in rows if r["production_scope_member"]}
    live = live_production_tickers()
    obligation_ab = {r["ticker"] for r in rows if r["obligation_tier_ab"]}

    return {
        "schema_version": 2,
        "artifact_type": "wf78_production_scope_proof_join_shadow",
        "review_only": True,
        "authority_boundary": {
            "shadow_report_only": True,
            "sql_canon_mutation_allowed": False,
            "registry_mutation_allowed": False,
            "card_mutation_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "owner_approval_inferred": False,
        },
        "join_rule": {
            "owner": "scripts/finance_sql_canon.py:resolve_production_scope",
            "tier_authority": "tier_routing_state.auto_tier",
            "accepted_tiers": sorted(PROOF_JOIN_TIERS),
            "accepted_freshness_states": sorted(PROOF_JOIN_FRESH_STATES),
            "required_confidence_status": PROOF_JOIN_CONFIDENCE_STATUS,
            "required_critical_data_conflict_count": 0,
            "also_requires": ["coverage registry membership", "ticker card on disk"],
        },
        "source_artifacts": {
            "registry": rel(REGISTRY),
            "coverage": rel(COVERAGE),
            "cards_dir": rel(CARDS),
            "canon_db": rel(DB_PATH),
        },
        "summary": {
            "active_tickers": len(rows),
            "recomputed_production_scope": len(joined),
            "live_db_production_scope": len(live),
            "recomputed_matches_live_db": joined == live,
            "recomputed_not_in_live_db": sorted(joined - live),
            "live_db_not_recomputed": sorted(live - joined),
            "coverage_obligation_tier_ab": len(obligation_ab),
            "obligation_ab_blocked_from_production": len(obligation_ab - joined),
            "production_not_obligation_ab": sorted(joined - obligation_ab),
        },
        "blocking_gate_breakdown": dict(
            collections.Counter(r["production_scope_source"] for r in rows).most_common()
        ),
        "obligation_ab_blocking_gate_breakdown": dict(
            collections.Counter(
                r["production_scope_source"] for r in rows if r["obligation_tier_ab"]
            ).most_common()
        ),
        "production_tickers": sorted(joined),
        "obligation_ab_blocked_tickers": sorted(obligation_ab - joined),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report-only diff of the live WF78 production-scope proof join.",
        allow_abbrev=False,
    )
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT, help="Shadow report output path.")
    parser.add_argument("--write", action="store_true", help="Write the shadow report JSON.")
    parser.add_argument("--pretty", action="store_true", help="Print the summary to stdout.")
    args = parser.parse_args()

    report = build_report(build_rows())

    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    if args.pretty or not args.write:
        print(
            json.dumps(
                {
                    "summary": report["summary"],
                    "blocking_gate_breakdown": report["blocking_gate_breakdown"],
                    "obligation_ab_blocking_gate_breakdown": report["obligation_ab_blocking_gate_breakdown"],
                    "out": rel(args.out) if args.write else None,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
