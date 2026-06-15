#!/usr/bin/env python3
"""Refresh held Tier C quote/card context before attention routing.

This is a review-only cron helper. It refreshes post-close quote overlays for
Tier C held/repair candidates, rebuilds their ticker cards, then reruns the
Tier C attention trigger and auto-router so C-MONITOR/C-CANDIDATE movement can
be detected without manual one-off work.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-tier-c-hold-recheck.json"
CARD_SUMMARY = TMP / "wf78-tier-c-hold-recheck-card-summary.json"
ROUTER = TMP / "wf78-auto-tier-routing.json"
ATTENTION = TMP / "wf78-tier-c-attention-trigger.json"
SCHEMA = "veritas.wf78_tier_c_hold_recheck.v1"

DEFAULT_TARGET_STATES = {"C-CANDIDATE-HOLD", "C-CANDIDATE-REPAIR", "C-CANDIDATE"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_refresh_allowed": True,
    "canon_or_portfolio_mutation_allowed": False,
    "universe_mutation_allowed": False,
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "routing", "candidates", "items"):
        raw = payload.get(key)
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
    return []


def ticker(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or "").upper().strip()


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-2400:],
            "stderr_preview": proc.stderr.strip()[-1200:],
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
            "stdout_preview": (exc.stdout or "")[-2400:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def target_tickers(target_states: set[str], max_tickers: int, explicit: list[str] | None) -> list[str]:
    if explicit:
        return sorted({item.upper().strip() for item in explicit if item.upper().strip()})[:max_tickers]
    router = load(ROUTER)
    selected: list[str] = []
    for row in rows(router):
        state = str(row.get("auto_state") or row.get("state") or "").upper()
        tier = str(row.get("auto_tier") or row.get("tier") or "").upper()
        symbol = ticker(row)
        if not symbol or tier != "TIER C":
            continue
        if state in target_states:
            selected.append(symbol)
    return sorted(set(selected))[:max_tickers]


def attention_index() -> dict[str, dict[str, Any]]:
    return {ticker(row): row for row in rows(load(ATTENTION)) if ticker(row)}


def router_index() -> dict[str, dict[str, Any]]:
    return {ticker(row): row for row in rows(load(ROUTER)) if ticker(row)}


def quote_rows() -> dict[str, dict[str, Any]]:
    return {ticker(row): row for row in rows(load(TMP / "post-close-final-quote-ledger.json")) if ticker(row)}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    states = {item.strip().upper() for raw in args.target_state for item in raw.split(",") if item.strip()}
    targets = target_tickers(states or DEFAULT_TARGET_STATES, args.max_tickers, args.ticker)
    steps: list[dict[str, Any]] = []
    if targets:
        quote_command = py_cmd("scripts\\post_close_final_quote_ledger.py", "--write", "--validate")
        for symbol in targets:
            quote_command.extend(["--ticker", symbol])
        steps.append(run_step("post_close_final_quote_ledger", quote_command, 180))
        card_command = py_cmd("scripts\\ticker_intelligence_card.py", "--summary-output", str(rel(CARD_SUMMARY)))
        for symbol in targets:
            card_command.extend(["--ticker", symbol])
        steps.append(run_step("ticker_intelligence_card_refresh", card_command, 240))
    steps.append(run_step("wf78_tier_c_attention_trigger", py_cmd("scripts\\wf78_tier_c_attention_trigger.py", "--write", "--write-db", "--validate"), 240))
    steps.append(run_step("wf78_auto_tier_router", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180))

    attention = attention_index()
    routing = router_index()
    quotes = quote_rows()
    target_rows = []
    moved_attention = []
    for symbol in targets:
        arow = attention.get(symbol, {})
        rrow = routing.get(symbol, {})
        qrow = quotes.get(symbol, {})
        attention_state = arow.get("attention_state")
        router_state = rrow.get("auto_state")
        if attention_state in {"C-CANDIDATE", "C-CANDIDATE-REPAIR"}:
            moved_attention.append(symbol)
        target_rows.append(
            {
                "ticker": symbol,
                "quote_status": qrow.get("status"),
                "quote_close": qrow.get("close"),
                "quote_market_date": qrow.get("market_date"),
                "attention_state": attention_state,
                "attention_score": arow.get("attention_score"),
                "momentum_score": arow.get("momentum_score"),
                "fundamental_score": arow.get("fundamental_score"),
                "attention_blockers": arow.get("blockers"),
                "router_tier": rrow.get("auto_tier"),
                "router_state": router_state,
                "route_reason": rrow.get("route_reason"),
            }
        )

    failed = [step["name"] for step in steps if not step.get("ok")]
    errors = [f"failed_steps:{','.join(failed)}"] if failed else []
    if any(AUTHORITY_BOUNDARY[key] for key in ("capital_deployment_allowed", "trade_or_execution_allowed", "owner_approval_inferred")):
        errors.append("authority_boundary_widened")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only Tier C hold/repair quote-card recheck before attention routing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "target_states": sorted(states or DEFAULT_TARGET_STATES),
            "max_tickers": args.max_tickers,
            "explicit_tickers": sorted(args.ticker or []),
        },
        "steps": steps,
        "summary": {
            "target_count": len(targets),
            "target_tickers": targets,
            "moved_attention_count": len(moved_attention),
            "moved_attention_tickers": sorted(moved_attention),
            "card_summary_path": rel(CARD_SUMMARY),
            "next_safe_action": "Use moved_attention_tickers as Tier C repair/research candidates; Tier B and capital/execution remain separately gated.",
        },
        "target_rows": target_rows,
        "validation": {"status": "error" if errors else "ok", "errors": errors, "warnings": []},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh held Tier C quote/card context and rerun attention routing.")
    parser.add_argument("--ticker", action="append", default=None, help="Explicit ticker override; repeatable.")
    parser.add_argument("--target-state", action="append", default=["C-CANDIDATE-HOLD,C-CANDIDATE-REPAIR,C-CANDIDATE"])
    parser.add_argument("--max-tickers", type=int, default=25)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, report)
        print(f"wrote {rel(out)} status={report['status']} targets={report['summary']['target_count']} moved={report['summary']['moved_attention_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
