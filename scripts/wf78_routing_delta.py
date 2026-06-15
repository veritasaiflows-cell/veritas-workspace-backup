#!/usr/bin/env python3
"""Build the WF78 daily derived non-capital routing delta.

This reads the current auto-tier router artifact and, when a previous
``tmp/wf78-routing-delta.json`` exists, compares the current ticker route state
against that prior snapshot. First run is a baseline: it reports current
sections without inventing history.
"""
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
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
TICKER_CARD_SUMMARY = TMP / "ticker-card-refresh-gate-card-build-summary.json"
DEFAULT_OUT = TMP / "wf78-routing-delta.json"
SCHEMA = "veritas.wf78_routing_delta.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "derived_delta_only": True,
    "automated_non_capital_routing_allowed": True,
    "read_existing_artifacts_only": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "derived_delta_only",
    "automated_non_capital_routing_allowed",
    "read_existing_artifacts_only",
}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}
TIER_RANK = {"Tier C": 1, "Tier B": 2, "Tier A": 3}


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


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def ticker_key(value: Any) -> str:
    return str(value or "").strip().upper()


def current_snapshot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = ticker_key(row.get("ticker"))
        if not ticker:
            continue
        result[ticker] = {
            "ticker": ticker,
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "route_reason": row.get("route_reason"),
            "route_priority": row.get("route_priority"),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
    return result


def previous_snapshot(previous: dict[str, Any]) -> dict[str, dict[str, Any]]:
    snapshot = as_dict(previous.get("current_snapshot"))
    rows = as_dict(snapshot.get("rows_by_ticker"))
    return {ticker_key(key): as_dict(value) for key, value in rows.items() if ticker_key(key)}


def compare_snapshots(current: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    sections = {"promotions": [], "demotions": [], "state_changes": [], "added": [], "removed": []}
    for ticker, row in sorted(current.items()):
        prior = previous.get(ticker)
        if not prior:
            sections["added"].append(row)
            continue
        old_tier = str(prior.get("auto_tier") or "")
        new_tier = str(row.get("auto_tier") or "")
        old_rank = TIER_RANK.get(old_tier, 0)
        new_rank = TIER_RANK.get(new_tier, 0)
        change = {
            "ticker": ticker,
            "prior_auto_tier": old_tier,
            "current_auto_tier": new_tier,
            "prior_auto_state": prior.get("auto_state"),
            "current_auto_state": row.get("auto_state"),
            "route_reason": row.get("route_reason"),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
        if new_rank > old_rank:
            sections["promotions"].append(change)
        elif new_rank < old_rank:
            sections["demotions"].append(change)
        elif prior.get("auto_state") != row.get("auto_state"):
            sections["state_changes"].append(change)
    for ticker, row in sorted(previous.items()):
        if ticker not in current:
            sections["removed"].append({
                "ticker": ticker,
                "prior_auto_tier": row.get("auto_tier"),
                "prior_auto_state": row.get("auto_state"),
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
            })
    return sections


def stale_map(stale: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker_key(row.get("ticker")): row
        for row in as_list(stale.get("stale_ticker_cards"))
        if isinstance(row, dict) and ticker_key(row.get("ticker"))
    }


def card_summary_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker_key(row.get("ticker")): row
        for row in as_list(summary.get("cards"))
        if isinstance(row, dict) and ticker_key(row.get("ticker"))
    }


def stale_sections(rows: list[dict[str, Any]], stale_rows: dict[str, dict[str, Any]], card_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        ticker = ticker_key(row.get("ticker"))
        stale = stale_rows.get(ticker)
        card = card_rows.get(ticker, {})
        if not stale and int(card.get("missing_or_stale_count") or 0) <= 0:
            continue
        result.append({
            "ticker": ticker,
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "recommendation_support": card.get("recommendation_support"),
            "missing_or_stale_count": card.get("missing_or_stale_count"),
            "missing_or_stale": as_list(as_dict(stale).get("missing_or_stale")),
            "blockers": as_list(as_dict(stale).get("blockers")),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        })
    return result


def capital_review_candidate(row: dict[str, Any], stale_by_ticker: dict[str, dict[str, Any]], card_by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    ticker = ticker_key(row.get("ticker"))
    if row.get("auto_state") != "A-READY":
        return None
    card = card_by_ticker.get(ticker, {})
    stale = stale_by_ticker.get(ticker)
    stale_count = int(card.get("missing_or_stale_count") or 0)
    return {
        "ticker": ticker,
        "auto_tier": row.get("auto_tier"),
        "auto_state": row.get("auto_state"),
        "route_reason": row.get("route_reason"),
        "recommendation_support": card.get("recommendation_support"),
        "missing_or_stale_count": stale_count,
        "non_executing_review_candidate": True,
        "capital_card_warranted": stale_count == 0 and not stale,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "next_safe_action": "Prepare or refresh a non-executing owner approval card only after fresh quote/band/stop and source-open checks pass.",
    }


def build_report(out: Path) -> dict[str, Any]:
    auto_router = load_dict(AUTO_ROUTER)
    stale = load_dict(STALE_TICKERS)
    card_summary = load_dict(TICKER_CARD_SUMMARY)
    previous = load_dict(out)

    rows = [row for row in as_list(auto_router.get("rows")) if isinstance(row, dict)]
    current = current_snapshot(rows)
    prior = previous_snapshot(previous)
    compared = compare_snapshots(current, prior) if prior else {"promotions": [], "demotions": [], "state_changes": [], "added": [], "removed": []}
    stale_by_ticker = stale_map(stale)
    card_by_ticker = card_summary_map(card_summary)
    challenged = [row for row in rows if str(row.get("auto_state") or "").endswith("CHALLENGED")]
    holds = [row for row in rows if str(row.get("auto_state") or "") in {"C-CANDIDATE-HOLD", "B-HOLD"}]
    stale_names = stale_sections(rows, stale_by_ticker, card_by_ticker)
    capital_candidates = [
        candidate for row in rows
        if (candidate := capital_review_candidate(row, stale_by_ticker, card_by_ticker)) is not None
    ]

    tier_counts = Counter(row.get("auto_tier") for row in rows)
    state_counts = Counter(row.get("auto_state") for row in rows)
    checks: list[dict[str, Any]] = []
    add_check(checks, "auto_router_present", bool(auto_router), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_validated", as_dict(auto_router.get("validation")).get("status") == "ok", as_dict(auto_router.get("validation")).get("status"))
    add_check(checks, "active_rows_present", bool(rows), len(rows))
    add_check(checks, "hard_false_capital_deployment", all(row.get("capital_deployment_approved") is False for row in rows), None)
    add_check(checks, "hard_false_trade_execution", all(row.get("trade_or_execution_approved") is False for row in rows), None)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    baseline = not bool(prior)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Daily Non-Capital Routing Delta",
        "purpose": "Compact daily delta over the WF78 auto-tier router. Baseline mode is used when no prior delta snapshot exists.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "auto_router": rel(AUTO_ROUTER),
            "stale_tickers": rel(STALE_TICKERS),
            "ticker_card_summary": rel(TICKER_CARD_SUMMARY),
            "prior_delta": rel(out),
        },
        "delta_mode": "baseline_no_prior_snapshot" if baseline else "compared_to_prior_snapshot",
        "changed_since": None if baseline else previous.get("generated_at_utc"),
        "summary": {
            "active_ticker_count": len(rows),
            "auto_tier_counts": dict(sorted(tier_counts.items())),
            "auto_state_counts": dict(sorted(state_counts.items())),
            "promotions_count": len(compared["promotions"]),
            "demotions_count": len(compared["demotions"]),
            "state_changes_count": len(compared["state_changes"]),
            "challenged_count": len(challenged),
            "holds_count": len(holds),
            "stale_count": len(stale_names),
            "capital_review_candidate_count": len(capital_candidates),
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "next_safe_action": "Review challenged, hold, and stale sections; use route-ticker for single-name packets. No capital or execution authority is granted.",
        },
        "promotions": compared["promotions"],
        "demotions": compared["demotions"],
        "state_changes": compared["state_changes"],
        "added": compared["added"],
        "removed": compared["removed"],
        "challenged": [
            {
                "ticker": row.get("ticker"),
                "auto_tier": row.get("auto_tier"),
                "auto_state": row.get("auto_state"),
                "route_reason": row.get("route_reason"),
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
            }
            for row in challenged
        ],
        "holds": [
            {
                "ticker": row.get("ticker"),
                "auto_tier": row.get("auto_tier"),
                "auto_state": row.get("auto_state"),
                "route_reason": row.get("route_reason"),
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
            }
            for row in holds
        ],
        "stale": stale_names,
        "capital_review_candidates": capital_candidates,
        "current_snapshot": {
            "generated_at_utc": as_dict(auto_router).get("generated_at_utc"),
            "rows_by_ticker": current,
        },
        "validation": {
            "status": "ok" if not errors else "error",
            "checks": checks,
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "This delta is derived non-capital routing proof only.",
            "Capital-review candidates are approval-card preparation candidates, not approved deployments.",
            "No paper/live order, brokerage/account action, portfolio/canon mutation, SQL-canon mutation, or owner approval is inferred.",
        ],
    }


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    out = resolve(args.out)
    report = build_report(out)
    if args.write:
        atomic_write_json(out, report)
    result = {
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "delta_mode": report["delta_mode"],
        "summary": report["summary"],
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
