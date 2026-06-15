#!/usr/bin/env python3
"""Rank WF78 evidence drag into a smaller repair queue.

Lane C proof. Reads WF78 event rerouting, capital-review queue, auto-router,
and stale ticker-card proof, then emits a ranked repair/card-prep queue. It does
not repair cards directly, mutate ticker/card/canon/portfolio state, or approve
capital/execution.
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
OUT = TMP / "wf78-evidence-drag-reduction.json"

SCHEMA = "veritas.wf78_evidence_drag_reduction.v1"

EVENT_REROUTING = TMP / "wf78-event-triggered-rerouting.json"
CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
ACTION_SCORER = TMP / "artifact-intelligence-action-scorer.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "evidence_ranking_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
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


def rows_by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        key = ticker(row_dict.get("ticker"))
        if key:
            result[key] = row_dict
    return result


def stale_families(row: dict[str, Any]) -> list[str]:
    raw = row.get("missing_or_stale")
    if isinstance(raw, list):
        families: list[str] = []
        for item in raw:
            if isinstance(item, str):
                families.append(item)
            elif isinstance(item, dict):
                families.append(str(item.get("family") or item.get("status") or "unknown"))
        return sorted(set(families))
    return []


def evidence_score(
    *,
    symbol: str,
    event_actions: list[dict[str, Any]],
    capital_row: dict[str, Any],
    auto_row: dict[str, Any],
    stale_row: dict[str, Any],
) -> tuple[int, str, list[str]]:
    reasons: list[str] = []
    score = 0
    state = str(auto_row.get("auto_state") or capital_row.get("auto_state") or "")
    tier = str(auto_row.get("auto_tier") or capital_row.get("auto_tier") or "")
    action_types = {str(row.get("action_type")) for row in event_actions}

    if capital_row:
        score += 100
        reasons.append("capital-review candidate")
        if capital_row.get("capital_review_card_preparable"):
            score += 25
            reasons.append("owner-card prep can proceed without local freshness blocker")
    if "prepare_owner_card" in action_types:
        score += 35
        reasons.append("event queue says prepare non-executing owner card")
    if state.startswith("A"):
        score += 40
        reasons.append(f"Tier A state {state}")
    elif state.startswith("B") or tier == "Tier B":
        score += 20
        reasons.append(f"Tier B state {state or tier}")
    families = stale_families(stale_row)
    score += min(30, len(families) * 5)
    if families:
        reasons.append(f"{len(families)} stale/missing evidence families")
    if "reroute_review" in action_types:
        score += 15
        reasons.append("route-review action present")
    if "repair_evidence" in action_types:
        score += 10
        reasons.append("evidence-repair action present")
    if not reasons:
        reasons.append("low-priority residual evidence row")
    return score, state or tier or "unrouted", reasons


def build_report(limit: int = 25) -> dict[str, Any]:
    event = load_dict(EVENT_REROUTING)
    capital = load_dict(CAPITAL_QUEUE)
    auto = load_dict(AUTO_ROUTER)
    stale = load_dict(STALE_TICKERS)
    scorer = load_dict(ACTION_SCORER)

    event_actions = [as_dict(row) for row in as_list(event.get("actions"))]
    actions_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for action in event_actions:
        actions_by_ticker.setdefault(ticker(action.get("ticker")), []).append(action)
    capital_rows = rows_by_ticker(as_list(capital.get("rows")))
    auto_rows = rows_by_ticker(as_list(auto.get("rows")))
    stale_rows = rows_by_ticker(as_list(stale.get("stale_ticker_cards")))
    symbols = sorted(set(actions_by_ticker) | set(capital_rows) | set(stale_rows))

    queue: list[dict[str, Any]] = []
    family_counter: Counter[str] = Counter()
    for symbol in symbols:
        if not symbol:
            continue
        event_rows = actions_by_ticker.get(symbol, [])
        cap = capital_rows.get(symbol, {})
        route = auto_rows.get(symbol, {})
        stale_row = stale_rows.get(symbol, {})
        families = stale_families(stale_row)
        family_counter.update(families)
        score, route_state, reasons = evidence_score(
            symbol=symbol,
            event_actions=event_rows,
            capital_row=cap,
            auto_row=route,
            stale_row=stale_row,
        )
        recommended_commands = []
        if cap and cap.get("capital_review_card_preparable"):
            recommended_commands.append("python scripts\\wf67_order_card_request_generator.py --require-promotion-gate --ticker " + symbol)
        if families:
            recommended_commands.append("python scripts\\finance_ticker_card_refresh_gate.py --write --validate")
        queue.append({
            "ticker": symbol,
            "priority_score": score,
            "route_state": route_state,
            "auto_tier": route.get("auto_tier") or cap.get("auto_tier"),
            "event_action_types": sorted({str(row.get("action_type")) for row in event_rows if row.get("action_type")}),
            "stale_family_count": len(families),
            "stale_families": families,
            "capital_review_candidate": bool(cap),
            "capital_review_card_preparable": bool(cap.get("capital_review_card_preparable")),
            "owner_action_required": bool(cap) or any(row.get("owner_action_required") for row in event_rows),
            "reason": "; ".join(reasons),
            "recommended_commands": recommended_commands,
            "apply_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "source_artifacts": sorted(set(
                [rel(EVENT_REROUTING), rel(AUTO_ROUTER), rel(STALE_TICKERS)]
                + ([rel(CAPITAL_QUEUE)] if cap else [])
            )),
        })
    queue.sort(key=lambda row: (-int(row["priority_score"]), row["ticker"]))
    for idx, row in enumerate(queue, start=1):
        row["queue_rank"] = idx

    card_prep = [row for row in queue if row["capital_review_card_preparable"]]
    top_repairs = queue[:limit]
    capital_flags_clean = all(
        not row.get("capital_deployment_approved")
        and not row.get("trade_or_execution_approved")
        and not row.get("paper_or_live_execution_allowed")
        and not row.get("apply_allowed")
        for row in queue
    )
    errors = [] if capital_flags_clean else ["one_or_more_queue_rows_widen_authority"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "purpose": "Rank WF78 evidence drag so repair/card-prep work starts with decision-impact names.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [
            rel(EVENT_REROUTING),
            rel(CAPITAL_QUEUE),
            rel(AUTO_ROUTER),
            rel(STALE_TICKERS),
            rel(ACTION_SCORER),
        ],
        "summary": {
            "event_action_count": len(event_actions),
            "stale_ticker_count": len(stale_rows),
            "ranked_queue_count": len(queue),
            "top_repair_count": len(top_repairs),
            "capital_review_candidate_count": len(capital_rows),
            "card_prep_ready_count": len(card_prep),
            "top_ticker": top_repairs[0]["ticker"] if top_repairs else None,
            "top_stale_families": [{"family": family, "count": count} for family, count in family_counter.most_common(10)],
            "artifact_scorer_action_count": scorer.get("summary", {}).get("action_count"),
            "next_safe_action": "Work top ranked repairs/card-prep only; keep all capital/trade/execution flags false.",
        },
        "capital_review_card_prep": card_prep,
        "top_repairs": top_repairs,
        "queue": queue,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "Evidence reducer ranks repair/card-prep only; no ticker-card mutation, canon/portfolio mutation, capital deployment, trade execution, paper/live/account action, customer output, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank WF78 evidence drag.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on critical validation errors.")
    parser.add_argument("--limit", type=int, default=25, help="Number of top repairs to include in the summary list.")
    args = parser.parse_args()
    report = build_report(limit=args.limit)
    if args.write:
        atomic_write_json(OUT, report)
        print(f"wrote {rel(OUT)} status={report['status']} ranked={report['summary']['ranked_queue_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
