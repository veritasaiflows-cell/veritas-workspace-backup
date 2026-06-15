#!/usr/bin/env python3
"""Run the repeatable parallel work bundle for WF78/WF67/macro hardening.

This runner coordinates existing owner scripts instead of replacing them. It
refreshes evidence, refreshes macro overlay proof, prepares non-executing owner
decision cards for capital-review candidates, and records Tier A challenged
repair state. It does not execute paper/live orders, mutate canon/portfolio
state, infer approval, or change customer/public output.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "parallel-repeatable-work-orchestration.json"
CARD_PREP_OUT = TMP / "wf78-owner-card-prep-loop.json"
TIER_A_REPAIR_OUT = TMP / "wf78-tier-a-evidence-repair-batch.json"
MACRO_GUARD_OUT = TMP / "macro-event-guard-loop.json"
CARD_DIR = TMP / "alpaca-paper-readiness" / "main-session-cards"
REQUEST_DIR = TMP / "alpaca-paper-readiness"

SCHEMA = "veritas.parallel_repeatable_work_orchestration.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "orchestration_only": True,
    "non_executing_owner_card_prep_allowed": True,
    "wf67_request_artifact_generation_allowed": True,
    "automated_non_capital_evidence_refresh_allowed": True,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_canon_mutation_allowed": False,
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


def slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def run_step(name: str, command: list[str], timeout: int = 900) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-4000:],
            "stderr_preview": proc.stderr.strip()[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else "",
        }


def lane_macro() -> dict[str, Any]:
    steps = [
        run_step("macro_metrics_ingest", py_cmd("scripts\\macro_metrics_ingest.py", "--write", "--validate")),
        run_step("macro_judgment_draft", py_cmd("scripts\\macro_judgment_draft.py", "--write", "--validate")),
        run_step("wf78_macro_thesis_overlay_gate", py_cmd("scripts\\wf78_macro_thesis_overlay_gate.py", "--write", "--write-db", "--validate")),
    ]
    macro_metrics = load_dict(TMP / "macro-metrics-current.json")
    macro_judgment = load_dict(TMP / "macro-judgment-draft.json")
    macro_overlay = load_dict(TMP / "wf78-macro-thesis-overlay-gate.json")
    report = {
        "schema": "veritas.macro_event_guard_loop.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if all(step["ok"] for step in steps) else "blocked",
        "purpose": "Refresh review-only macro context and WF78 macro/thesis overlay before ticker card-prep decisions.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "steps": steps,
        "summary": {
            "macro_metrics_status": macro_metrics.get("status"),
            "macro_judgment_status": macro_judgment.get("status"),
            "macro_overlay_status": macro_overlay.get("status"),
            "macro_overlay_shortlist_count": len(as_list(macro_overlay.get("tier_b_research_shortlist"))),
            "next_safe_action": "Use macro overlay as review-only routing context; do not treat it as capital readiness.",
        },
        "source_artifacts": [
            "tmp/macro-metrics-current.json",
            "tmp/macro-judgment-draft.json",
            "tmp/wf78-macro-thesis-overlay-gate.json",
            "tmp/wf78-macro-thesis-overlay-gate.sqlite",
        ],
    }
    atomic_write_json(MACRO_GUARD_OUT, report)
    return report


def lane_evidence(skip_provider_refresh: bool) -> dict[str, Any]:
    refresh_cmd = py_cmd("scripts\\finance_ticker_card_refresh_gate.py", "--write", "--validate")
    if skip_provider_refresh:
        refresh_cmd.append("--skip-provider-refresh")
    steps = [
        run_step("finance_ticker_card_refresh_gate", refresh_cmd),
        run_step("wf78_auto_tier_router", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate")),
        run_step("wf78_event_triggered_rerouting", py_cmd("scripts\\wf78_event_triggered_rerouting.py", "--write", "--write-db", "--validate")),
        run_step("wf78_evidence_drag_reducer", py_cmd("scripts\\wf78_evidence_drag_reducer.py", "--write", "--validate")),
    ]
    return {
        "status": "ok" if all(step["ok"] for step in steps) else "blocked",
        "skip_provider_refresh": skip_provider_refresh,
        "steps": steps,
        "source_artifacts": [
            "tmp/finance-ticker-card-refresh-gate.json",
            "tmp/ticker-card-refresh-gate-card-build-summary.json",
            "tmp/wf78-auto-tier-routing.json",
            "tmp/wf78-event-triggered-rerouting.json",
            "tmp/wf78-evidence-drag-reduction.json",
        ],
    }


def choose_limit_price(row: dict[str, Any]) -> float:
    band = as_dict(row.get("written_band"))
    current = float(row.get("current_price") or as_dict(row.get("quote")).get("current_price") or 0)
    high = float(band.get("entry_band_high") or current or 1)
    if current > 0:
        return round(min(current, high), 2)
    return round(high, 2)


def build_main_session_card(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("ticker") or "").upper()
    band = as_dict(row.get("written_band"))
    limit_price = choose_limit_price(row)
    notional = min(500.0, max(1.0, limit_price))
    stop = band.get("stop_or_invalidation")
    estimated_loss = round(max(1.0, limit_price - float(stop or limit_price * 0.9)), 2)
    return {
        "schema_version": 1,
        "artifact_type": "main_session_wf67_order_decision_card",
        "request_id": f"wf78-owner-card-prep-{symbol}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at_utc": utc_now(),
        "authority": {
            "main_session_recommendation_allowed": True,
            "wf67_request_artifact_generation_allowed": True,
            "paper_only": True,
            "paper_order_execution_allowed_by_card": False,
            "live_trade_allowed": False,
            "owner_approval_inferred": False,
            "portfolio_or_canon_apply_allowed": False,
            "cash_or_risk_rule_mutation_allowed": False,
        },
        "order": {
            "symbol": symbol,
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": limit_price,
            "qty": None,
            "notional": round(notional, 2),
        },
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": round(notional, 2),
            "max_notional_usd": 500.0,
            "max_loss_usd": min(500.0, estimated_loss),
            "entry_band_low": band.get("entry_band_low"),
            "entry_band_high": band.get("entry_band_high"),
            "observed_price": row.get("current_price"),
            "observed_entry_status": row.get("current_band_status"),
            "stop": stop,
            "sizing_rationale": "Paper-only starter request sized at or below WF67 $500 pilot cap; exact execution remains blocked pending Randall approval and fresh guard proof.",
        },
        "source": {
            "source_artifact": "tmp/wf78-capital-review-queue.json",
            "capital_recommendation_source": "wf78_non_executing_owner_card_prep",
            "owner_or_pilot_scope": "WF78 capital-review candidate, paper-only starter card, pending exact Randall approval",
            "approval_artifact": None,
        },
        "owner_approval": {
            "status": "pending_exact_randall_approval",
            "approved_by": None,
            "approval_text": None,
            "market_order_owner_approved": False,
        },
        "decision_context": {
            "name": row.get("name"),
            "sector": row.get("sector"),
            "queue_state": row.get("queue_state"),
            "recommendation_support": row.get("recommendation_support"),
            "cautions": row.get("cautions") or [],
            "source_artifacts": row.get("source_artifacts") or [],
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
        },
    }


def prepare_owner_cards() -> dict[str, Any]:
    queue = load_dict(TMP / "wf78-capital-review-queue.json")
    reducer = load_dict(TMP / "wf78-evidence-drag-reduction.json")
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    rows = [row for row in as_list(queue.get("rows")) if as_dict(row).get("capital_review_card_preparable")]
    prepared: list[dict[str, Any]] = []
    for row in rows:
        row = as_dict(row)
        symbol = str(row.get("ticker") or "").upper()
        card = build_main_session_card(row)
        card_path = CARD_DIR / f"{symbol}.owner-card.json"
        atomic_write_json(card_path, card)
        request_path = REQUEST_DIR / f"paper-trade-request.wf78-owner-card-prep-{slug(symbol)}.json"
        wf67_step = run_step(
            f"wf67_request_generator_{symbol}",
            py_cmd(
                "scripts\\wf67_order_card_request_generator.py",
                "--card",
                rel(card_path),
                "--output",
                rel(request_path),
                "--require-promotion-gate",
            ),
        )
        prepared.append({
            "ticker": symbol,
            "card_path": rel(card_path),
            "wf67_request_path": rel(request_path) if wf67_step["ok"] else None,
            "wf67_request_generation_status": "ok" if wf67_step["ok"] else "blocked",
            "wf67_step": wf67_step,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    blocked = [row for row in prepared if row["wf67_request_generation_status"] != "ok"]
    report = {
        "schema": "veritas.wf78_owner_card_prep_loop.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if prepared else "blocked",
        "purpose": "Prepare non-executing owner cards and WF67 request artifacts where promotion gate allows.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "capital_review_rows": len(rows),
            "owner_cards_written": len(prepared),
            "wf67_request_artifacts_written": len(prepared) - len(blocked),
            "wf67_request_blocked_count": len(blocked),
            "reducer_status": reducer.get("status"),
            "next_safe_action": "Present cards for owner review only; no execution is allowed without exact Randall approval and fresh WF67 guard proof.",
        },
        "prepared": prepared,
        "stop_lines": [
            "Cards and WF67 requests are non-executing review artifacts.",
            "Pending cards do not carry Randall approval metadata.",
            "No paper/live/account action, money movement, canon/portfolio mutation, or inferred approval is allowed.",
        ],
    }
    atomic_write_json(CARD_PREP_OUT, report)
    return report


def tier_a_repair_batch() -> dict[str, Any]:
    reducer = load_dict(TMP / "wf78-evidence-drag-reduction.json")
    top = []
    for row in as_list(reducer.get("queue")):
        item = as_dict(row)
        if item.get("auto_tier") == "Tier A" and str(item.get("route_state") or "").startswith("A-CHALLENGED"):
            top.append(item)
        if len(top) >= 10:
            break
    report = {
        "schema": "veritas.wf78_tier_a_evidence_repair_batch.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if reducer.get("status") == "ok" else "blocked",
        "purpose": "Track the Tier A challenged evidence repair batch after ticker-card refresh and rerouting.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "tier_a_challenged_top_count": len(top),
            "tickers": [row.get("ticker") for row in top],
            "next_safe_action": "Continue evidence repair by rank; do not treat repaired evidence as deployment approval.",
        },
        "rows": top,
    }
    atomic_write_json(TIER_A_REPAIR_OUT, report)
    return report


def build_report(skip_provider_refresh: bool) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        macro_future = executor.submit(lane_macro)
        evidence_future = executor.submit(lane_evidence, skip_provider_refresh)
        macro_report = macro_future.result()
        evidence_report = evidence_future.result()
    owner_cards = prepare_owner_cards()
    repair_batch = tier_a_repair_batch()
    lane_statuses = {
        "macro_event_guard_loop": macro_report.get("status"),
        "evidence_refresh_and_reroute": evidence_report.get("status"),
        "owner_card_prep_loop": owner_cards.get("status"),
        "tier_a_evidence_repair_batch": repair_batch.get("status"),
    }
    blocked = [name for name, status in lane_statuses.items() if status != "ok"]
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not blocked else "blocked",
        "purpose": "Parallel repeatable work orchestration for WF78 evidence repair, owner cards, macro overlay, and reusable closeout proof.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "lane_statuses": lane_statuses,
            "blocked_lanes": blocked,
            "owner_cards_written": owner_cards.get("summary", {}).get("owner_cards_written"),
            "wf67_request_artifacts_written": owner_cards.get("summary", {}).get("wf67_request_artifacts_written"),
            "tier_a_challenged_batch_count": repair_batch.get("summary", {}).get("tier_a_challenged_top_count"),
            "skip_provider_refresh": skip_provider_refresh,
            "next_safe_action": "Run repeatable closeout chain, then review owner-card artifacts without execution authority.",
        },
        "outputs": {
            "macro_event_guard_loop": rel(MACRO_GUARD_OUT),
            "owner_card_prep_loop": rel(CARD_PREP_OUT),
            "tier_a_evidence_repair_batch": rel(TIER_A_REPAIR_OUT),
            "orchestration_report": rel(OUT),
        },
        "lanes": {
            "macro_event_guard_loop": macro_report,
            "evidence_refresh_and_reroute": evidence_report,
            "owner_card_prep_loop": owner_cards,
            "tier_a_evidence_repair_batch": repair_batch,
        },
        "validation": {
            "status": "ok" if not blocked else "blocked",
            "errors": blocked,
            "warnings": [],
        },
        "stop_lines": [
            "This orchestration is review-only and non-executing.",
            "No capital deployment, paper/live order execution, account action, money movement, canon/portfolio mutation, SQL-canon mutation, customer output, or owner approval inference is allowed.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeatable parallel WF78/WF67/macro work.")
    parser.add_argument("--write", action="store_true", help="Write orchestration proof artifacts.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on blocked validation.")
    parser.add_argument("--skip-provider-refresh", action="store_true", help="Use local evidence only for ticker-card refresh.")
    args = parser.parse_args()

    report = build_report(skip_provider_refresh=args.skip_provider_refresh)
    if args.write:
        atomic_write_json(OUT, report)
        print(f"wrote {rel(OUT)} status={report['status']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
