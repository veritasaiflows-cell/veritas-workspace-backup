#!/usr/bin/env python3
"""WF78 ticker freshness ledger.

Builds a per-ticker, per-family freshness state so WF78 does not rediscover
stale-card debt in broad cleanup waves. The ledger is review-only and routes
rows to refresh, source-open repair, structural hold, or monitor.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-ticker-freshness-ledger.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
SOURCE_EXECUTOR = TMP / "wf78-source-open-repair-execution.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
SCHEMA = "veritas.wf78_ticker_freshness_ledger.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "freshness_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
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

# Ordered hardest blocker first. A row's overall state must describe the work that
# actually gates it, otherwise a cheap refreshable family outvotes an expensive
# source-open one and the row is routed to a gate that cannot clear it.
STATE_SEVERITY = (
    "blocked_structural",
    "stale_source_open",
    "stale_review_required",
    "source_open_repaired_rerun_needed",
    "stale_refreshable",
)

REFRESHABLE_FAMILIES = {"fresh_price_quote", "stale:technical_posture", "technical_posture"}
SOURCE_OPEN_FAMILIES = {
    "price_band_stop",
    "price_band_stop_position_sizing",
    "deployment_readiness_surface",
    "stale:price_band_stop",
    "stale:deployment_readiness",
    "stale:portfolio_fit_concentration",
    "stale:recommendation_support",
}


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


def family_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("family") or item.get("status") or "unknown")
    return str(item)


def stale_rows() -> dict[str, dict[str, Any]]:
    packet = load_dict(STALE_TICKERS)
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(packet.get("stale_ticker_cards")):
        row = as_dict(item)
        symbol = ticker(row.get("ticker"))
        if symbol:
            rows[symbol] = row
    return rows


def route_rows() -> dict[str, dict[str, Any]]:
    packet = load_dict(AUTO_ROUTER)
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(packet.get("rows")):
        row = as_dict(item)
        symbol = ticker(row.get("ticker"))
        if symbol:
            rows[symbol] = row
    return rows


def repair_rows() -> dict[str, dict[str, Any]]:
    packet = load_dict(SOURCE_EXECUTOR)
    rows: dict[str, dict[str, Any]] = {}
    for item in as_list(packet.get("rows")):
        row = as_dict(item)
        symbol = ticker(row.get("ticker"))
        if symbol:
            rows[symbol] = row
    return rows


def card_generated_at(symbol: str) -> str | None:
    path = CARD_DIR / f"{symbol}.current.json"
    if not path.exists():
        return None
    return load_dict(path).get("generated_at_utc")


def stale_families(row: dict[str, Any]) -> list[str]:
    raw = row.get("missing_or_stale") or row.get("stale_reasons") or []
    return sorted({family_name(item) for item in as_list(raw)})


def family_state(family: str, tier: str, repair_disposition: str | None) -> str:
    if family in REFRESHABLE_FAMILIES:
        return "stale_refreshable"
    if family in SOURCE_OPEN_FAMILIES:
        if tier == "Tier C" and repair_disposition in {None, "thin_monitor_hold"}:
            return "blocked_structural"
        if repair_disposition in {"repaired_from_owner_source"}:
            return "source_open_repaired_rerun_needed"
        return "stale_source_open"
    return "stale_review_required"


def ticker_sla(tier: str) -> dict[str, Any]:
    if tier == "Tier A":
        return {"quote_technical_hours": 24, "evidence_hours": 24, "source_open_days": 7}
    if tier == "Tier B":
        return {"quote_technical_hours": 72, "evidence_hours": 168, "source_open_days": 14}
    return {"quote_technical_hours": 168, "evidence_hours": 720, "source_open_days": None}


def next_action(overall: str, symbol: str) -> str:
    if overall == "fresh":
        return "monitor"
    if overall == "stale_refreshable":
        return "python scripts\\finance_ticker_card_refresh_gate.py --write --validate"
    if overall == "source_open_repaired_rerun_needed":
        return "rerun refresh gate, auto-router, evidence reducer, and freshness ledger"
    if overall == "stale_source_open":
        return f"run source-open repair for {symbol}; do not fabricate evidence"
    if overall == "blocked_structural":
        return f"keep {symbol} thin-monitor or promote before source-open repair"
    return f"inspect {symbol} freshness row"


def build_report() -> dict[str, Any]:
    stale = stale_rows()
    routes = route_rows()
    repairs = repair_rows()
    symbols = sorted(set(stale) | set(routes))
    rows: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    unclassified_families: Counter[str] = Counter()
    for symbol in symbols:
        route = routes.get(symbol, {})
        stale_row = stale.get(symbol, {})
        repair = repairs.get(symbol, {})
        tier = str(route.get("auto_tier") or "unknown")
        families = stale_families(stale_row)
        family_states = []
        repair_disposition = repair.get("repair_disposition")
        for family in families:
            state = family_state(family, tier, repair_disposition)
            family_states.append({"family": family, "state": state})
            family_counts[family] += 1
        family_state_values = {item["state"] for item in family_states}
        unclassified = [fam for fam in families if fam not in REFRESHABLE_FAMILIES and fam not in SOURCE_OPEN_FAMILIES]
        if unclassified:
            unclassified_families.update(unclassified)
        if not families:
            overall = "fresh"
        else:
            overall = next(
                (state for state in STATE_SEVERITY if state in family_state_values),
                "stale_review_required",
            )
        state_counts[overall] += 1
        tier_counts[tier] += 1
        rows.append({
            "ticker": symbol,
            "auto_tier": tier,
            "route_state": route.get("auto_state") or route.get("route_state"),
            "overall_freshness_state": overall,
            "stale_families": families,
            "family_states": family_states,
            "unclassified_families": unclassified,
            "repair_disposition": repair_disposition,
            "sla": ticker_sla(tier),
            "card_generated_at_utc": card_generated_at(symbol),
            "next_action": next_action(overall, symbol),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    warnings = []
    if unclassified_families:
        warnings.append(
            "unclassified stale families routed to stale_review_required: "
            + ", ".join(f"{fam}({count})" for fam, count in unclassified_families.most_common())
        )
    errors = []
    if any(row["capital_deployment_approved"] or row["trade_or_execution_approved"] or row["paper_or_live_execution_allowed"] or row["owner_approval_inferred"] for row in rows):
        errors.append("authority boundary widened in freshness rows")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Per-ticker WF78 freshness ledger for recurring refresh/source-open routing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(STALE_TICKERS), rel(AUTO_ROUTER), rel(SOURCE_EXECUTOR)],
        "summary": {
            "ticker_count": len(rows),
            "tier_counts": dict(tier_counts.most_common()),
            "freshness_state_counts": dict(state_counts.most_common()),
            "top_stale_families": [{"family": fam, "count": count} for fam, count in family_counts.most_common(12)],
            "unclassified_stale_families": [{"family": fam, "count": count} for fam, count in unclassified_families.most_common()],
            "tier_a_attention": [row["ticker"] for row in rows if row["auto_tier"] == "Tier A" and row["overall_freshness_state"] != "fresh"],
            "tier_b_attention": [row["ticker"] for row in rows if row["auto_tier"] == "Tier B" and row["overall_freshness_state"] != "fresh"],
            "next_safe_action": "Daily loop should refresh refreshable rows, run source-open repair for Tier A/B, and preserve Tier C structural holds.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Freshness ledger routes attention only; no ticker-card/canon/portfolio mutation.",
            "Tier C structural holds are honest debt, not failed automation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 ticker freshness ledger.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} tickers={report['summary']['ticker_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
