#!/usr/bin/env python3
"""Build the WF78 AI event-triggered rerouting queue.

The output is AI plumbing for the workspace: it turns stale evidence, band
state, capital-review queue state, and routing deltas into prioritized
non-capital rerouting/repair actions. It does not approve capital deployment,
execution, paper/live orders, account action, portfolio mutation, or customer
delivery.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf78-event-triggered-rerouting.json"
DEFAULT_DB = TMP / "wf78-event-triggered-rerouting.sqlite"

AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
ROUTING_DELTA = TMP / "wf78-routing-delta.json"
CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"

SCHEMA = "veritas.wf78_event_triggered_rerouting.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "ai_routing_plumbing": True,
    "automated_non_capital_routing_allowed": True,
    "cron_may_refresh_artifact": True,
    "owner_action_required_for_capital": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
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

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "ai_routing_plumbing",
    "automated_non_capital_routing_allowed",
    "cron_may_refresh_artifact",
    "owner_action_required_for_capital",
}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}


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


def ticker_key(value: Any) -> str:
    return str(value or "").strip().upper()


def by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        ticker = ticker_key(row_dict.get("ticker"))
        if ticker:
            result[ticker] = row_dict
    return result


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def make_action(
    *,
    ticker: str,
    action_type: str,
    trigger: str,
    priority: int,
    current_route: str | None,
    proposed_route: str | None,
    reason: str,
    source_artifacts: list[str],
    owner_action_required: bool = False,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "action_type": action_type,
        "trigger": trigger,
        "priority": priority,
        "current_route": current_route,
        "proposed_route": proposed_route,
        "reason": reason,
        "source_artifacts": sorted(set(source_artifacts)),
        "owner_action_required": owner_action_required,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "apply_allowed": False,
    }


def build_actions() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    auto_router = load_dict(AUTO_ROUTER)
    routing_delta = load_dict(ROUTING_DELTA)
    capital_queue = load_dict(CAPITAL_QUEUE)
    stale_tickers = load_dict(STALE_TICKERS)

    auto_rows = by_ticker(as_list(auto_router.get("rows")))
    capital_rows = by_ticker(as_list(capital_queue.get("rows")))
    stale_rows = by_ticker(as_list(stale_tickers.get("stale_ticker_cards")))
    actions: list[dict[str, Any]] = []

    for ticker, row in capital_rows.items():
        queue_state = str(row.get("queue_state") or "")
        band_status = str(row.get("current_band_status") or "")
        route = str(row.get("auto_state") or row.get("queue") or "")
        source_artifacts = as_list(row.get("source_artifacts")) + [rel(CAPITAL_QUEUE)]
        if row.get("requires_fresh_quote_band_stop_before_deployment_review"):
            actions.append(make_action(
                ticker=ticker,
                action_type="refresh_evidence",
                trigger="capital_candidate_fresh_quote_band_stop_required",
                priority=100,
                current_route=route,
                proposed_route="A-DEPLOY-CANDIDATE-FRESHNESS-BLOCKED",
                reason="Capital-review candidate cannot become an owner approval card until quote/band/stop proof is refreshed.",
                source_artifacts=source_artifacts,
                owner_action_required=True,
            ))
        elif queue_state == "A-DEPLOY-CANDIDATE-REVIEW-READY":
            actions.append(make_action(
                ticker=ticker,
                action_type="prepare_owner_card",
                trigger="capital_candidate_review_ready",
                priority=90,
                current_route=route,
                proposed_route="OWNER_CARD_PREP_ONLY",
                reason="Candidate has no local freshness blockers; prepare a non-executing owner review card only.",
                source_artifacts=source_artifacts,
                owner_action_required=True,
            ))
        elif band_status and band_status != "IN_BAND":
            actions.append(make_action(
                ticker=ticker,
                action_type="wait_for_band",
                trigger="capital_candidate_out_of_band",
                priority=70,
                current_route=route,
                proposed_route="A-DEPLOY-CANDIDATE-WAIT-FOR-BAND",
                reason=f"Candidate is not in written band ({band_status}); keep watch state and do not prepare approval card.",
                source_artifacts=source_artifacts,
                owner_action_required=True,
            ))

    for ticker, row in stale_rows.items():
        if ticker in capital_rows:
            continue
        auto_row = auto_rows.get(ticker, {})
        missing_count = int(row.get("missing_or_stale_count") or len(as_list(row.get("missing_or_stale"))) or 0)
        if missing_count <= 0:
            continue
        auto_state = str(auto_row.get("auto_state") or row.get("recommendation_posture") or "")
        priority = 80 if auto_state.startswith("A") else 60 if auto_state.startswith("B") else 40
        actions.append(make_action(
            ticker=ticker,
            action_type="repair_evidence",
            trigger="stale_or_missing_evidence",
            priority=priority,
            current_route=auto_state or None,
            proposed_route="EVIDENCE_REPAIR_QUEUE",
            reason=f"{missing_count} stale/missing evidence families block reliable routing or decision-card use.",
            source_artifacts=[rel(STALE_TICKERS), rel(AUTO_ROUTER)],
        ))

    for key in ("challenged", "holds"):
        for row in as_list(routing_delta.get(key)):
            row_dict = as_dict(row)
            ticker = ticker_key(row_dict.get("ticker"))
            if not ticker:
                continue
            actions.append(make_action(
                ticker=ticker,
                action_type="reroute_review",
                trigger=f"routing_delta_{key}",
                priority=75 if key == "challenged" else 55,
                current_route=str(row_dict.get("auto_state") or row_dict.get("current_state") or ""),
                proposed_route="ROUTE_REVIEW",
                reason=f"Routing delta classified ticker in {key}; keep non-capital route review explicit.",
                source_artifacts=[rel(ROUTING_DELTA), rel(AUTO_ROUTER)],
            ))

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for action in actions:
        key = (str(action.get("ticker")), str(action.get("action_type")), str(action.get("trigger")))
        existing = deduped.get(key)
        if not existing or int(action.get("priority") or 0) > int(existing.get("priority") or 0):
            deduped[key] = action
    final_actions = sorted(deduped.values(), key=lambda row: (-int(row.get("priority") or 0), str(row.get("ticker")), str(row.get("action_type"))))
    for index, action in enumerate(final_actions, start=1):
        action["queue_rank"] = index
    sources = {
        "auto_router": rel(AUTO_ROUTER),
        "routing_delta": rel(ROUTING_DELTA),
        "capital_review_queue": rel(CAPITAL_QUEUE),
        "stale_tickers": rel(STALE_TICKERS),
    }
    return final_actions, sources


def build_report() -> dict[str, Any]:
    actions, sources = build_actions()
    checks: list[dict[str, Any]] = []
    for path, name in [
        (AUTO_ROUTER, "auto_router_present"),
        (ROUTING_DELTA, "routing_delta_present"),
        (CAPITAL_QUEUE, "capital_review_queue_present"),
    ]:
        add_check(checks, name, path.exists(), rel(path))
    add_check(checks, "actions_generated", len(actions) > 0, len(actions), "warning")
    add_check(checks, "all_actions_no_apply", all(action.get("apply_allowed") is False for action in actions), None)
    add_check(checks, "all_actions_no_capital_approval", all(action.get("capital_deployment_approved") is False for action in actions), None)
    add_check(checks, "all_actions_no_execution_approval", all(action.get("trade_or_execution_approved") is False for action in actions), None)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    by_type: dict[str, int] = {}
    owner_required = 0
    for action in actions:
        action_type = str(action.get("action_type") or "")
        by_type[action_type] = by_type.get(action_type, 0) + 1
        if action.get("owner_action_required") is True:
            owner_required += 1
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - AI Event-Triggered Rerouting",
        "purpose": "Prioritize non-capital rerouting, evidence repair, and owner-card preparation triggers for AI-assisted workspace operation.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": sources,
        "summary": {
            "action_count": len(actions),
            "owner_action_required_count": owner_required,
            "action_type_counts": by_type,
            "top_action": actions[0] if actions else None,
            "cron_embedding": "refresh through existing P0/WF78 all-safe proof; do not add a new enabled cron",
            "next_safe_action": "Repair evidence and reroute labels only; prepare owner review cards only after freshness blockers clear.",
        },
        "actions": actions,
        "validation": {
            "status": "ok" if not errors else "error",
            "checks": checks,
            "errors": errors,
            "warnings": [check for check in checks if check["severity"] == "warning" and not check["ok"]],
        },
        "stop_lines": [
            "AI rerouting actions are review-only work items.",
            "Cron may refresh this artifact but may not apply routing that mutates canon, portfolio, production answer path, SQL canon, or ticker cards.",
            "No generated action implies capital deployment, trade/order execution, paper/live action, brokerage/account action, money movement, or owner approval.",
        ],
    }


def write_db(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE event_rerouting_actions (
                queue_rank INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                action_type TEXT NOT NULL,
                trigger TEXT NOT NULL,
                priority INTEGER NOT NULL,
                current_route TEXT,
                proposed_route TEXT,
                owner_action_required INTEGER NOT NULL,
                apply_allowed INTEGER NOT NULL,
                reason TEXT NOT NULL,
                source_artifacts_json TEXT NOT NULL
            )
            """
        )
        for action in as_list(report.get("actions")):
            action_dict = as_dict(action)
            conn.execute(
                """
                INSERT INTO event_rerouting_actions (
                    queue_rank, ticker, action_type, trigger, priority, current_route,
                    proposed_route, owner_action_required, apply_allowed, reason,
                    source_artifacts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_dict.get("queue_rank"),
                    action_dict.get("ticker"),
                    action_dict.get("action_type"),
                    action_dict.get("trigger"),
                    int(action_dict.get("priority") or 0),
                    action_dict.get("current_route"),
                    action_dict.get("proposed_route"),
                    1 if action_dict.get("owner_action_required") else 0,
                    1 if action_dict.get("apply_allowed") else 0,
                    action_dict.get("reason"),
                    json.dumps(as_list(action_dict.get("source_artifacts")), sort_keys=True),
                ),
            )
        conn.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            [
                ("schema", str(report.get("schema"))),
                ("generated_at_utc", str(report.get("generated_at_utc"))),
                ("status", str(report.get("status"))),
                ("authority_boundary_json", json.dumps(report.get("authority_boundary"), sort_keys=True)),
                ("summary_json", json.dumps(report.get("summary"), sort_keys=True)),
            ],
        )
        conn.execute("PRAGMA integrity_check")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db-out", type=Path, default=DEFAULT_DB)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.out = resolve(args.out)
    args.db_out = resolve(args.db_out)
    report = build_report()
    if args.write:
        atomic_write_json(args.out, report, ensure_ascii=False)
    if args.write_db:
        write_db(report, args.db_out)
    print(json.dumps({
        "status": report["status"],
        "validation": report["validation"]["status"],
        "actions": report["summary"]["action_count"],
        "owner_action_required": report["summary"]["owner_action_required_count"],
        "out": rel(args.out) if args.write else None,
        "db_out": rel(args.db_out) if args.write_db else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
