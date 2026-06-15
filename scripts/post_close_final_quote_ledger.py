#!/usr/bin/env python3
"""Write a review-only post-close final quote ledger for recommendation candidates.

This is a quote freshness overlay, not a ticker-card/canon mutation path. It is
intended for closed-market/weekend recommendation work where cached promotion
packets may still carry older intraday/reference prices.
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
OUT = TMP / "post-close-final-quote-ledger.json"

CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
DECISION_FACTORY = TMP / "finance-decision-factory.json"
PH_PACKET = TMP / "wf78-ph-owner-review-candidate-packet.json"
TIER_RESOLUTION = TMP / "wf78-tier-weighted-freshness-resolution.json"
FRESHNESS_LEDGER = TMP / "wf78-ticker-freshness-ledger.json"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"

SCHEMA = "veritas.post_close_final_quote_ledger.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "quote_freshness_overlay_only": True,
    "recommendation_freshness_support_allowed": True,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
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


def parse_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def yfinance_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def collect_targets(extra: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    reasons: dict[str, list[str]] = {}

    def add(symbol: Any, reason: str) -> None:
        normalized = ticker(symbol)
        if not normalized:
            return
        reasons.setdefault(normalized, [])
        if reason not in reasons[normalized]:
            reasons[normalized].append(reason)

    for symbol in extra:
        add(symbol, "cli")

    for row in as_list(load_dict(CAPITAL_QUEUE).get("rows")):
        add(as_dict(row).get("ticker"), "capital_review_queue")

    for row in as_list(load_dict(DECISION_FACTORY).get("decision_ledger")):
        add(as_dict(row).get("ticker"), "finance_decision_factory")

    ph_summary = as_dict(load_dict(PH_PACKET).get("summary"))
    if ph_summary.get("candidate_ready_for_owner_review"):
        add(ph_summary.get("ticker"), "wf78_ph_owner_review_candidate")

    for row in as_list(load_dict(TIER_RESOLUTION).get("rows")):
        row = as_dict(row)
        if row.get("resolution_state") == "blocked_fresh_quote_required_before_final_use":
            add(row.get("ticker"), "wf78_fresh_quote_gate")

    for row in as_list(load_dict(FRESHNESS_LEDGER).get("rows")):
        row = as_dict(row)
        stale_families = {str(item) for item in as_list(row.get("stale_families"))}
        if stale_families == {"fresh_price_quote"}:
            add(row.get("ticker"), "wf78_raw_fresh_quote_gate")

    if FINANCE_STATE_DB.exists():
        try:
            conn = sqlite3.connect(FINANCE_STATE_DB)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT ticker, price_source, source_path, raw_json FROM latest_price_technical"
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            rows = []
        for row in rows:
            item = dict(row)
            raw = parse_json(item.get("raw_json"))
            price_band_stop = as_dict(raw.get("price_band_stop"))
            sources = {
                str(item.get("price_source") or ""),
                str(item.get("source_path") or ""),
                str(price_band_stop.get("price_source") or ""),
            }
            has_post_close_payload = bool(as_dict(price_band_stop.get("post_close_final_quote")))
            claims_post_close_ledger = any("post-close-final-quote-ledger.json" in source for source in sources)
            if has_post_close_payload or claims_post_close_ledger:
                add(item.get("ticker"), "finance_state_existing_post_close_overlay")

    return sorted(reasons), reasons


def fetch_close(symbol: str) -> dict[str, Any]:
    yf_symbol = yfinance_symbol(symbol)
    try:
        import yfinance as yf  # type: ignore
    except Exception as exc:
        return {
            "ticker": symbol,
            "yfinance_symbol": yf_symbol,
            "status": "provider_unavailable",
            "error": f"yfinance import failed: {exc}",
        }
    try:
        hist = yf.Ticker(yf_symbol).history(period="5d", interval="1d", auto_adjust=False)
    except Exception as exc:
        return {
            "ticker": symbol,
            "yfinance_symbol": yf_symbol,
            "status": "fetch_error",
            "error": str(exc),
        }
    if hist is None or hist.empty or "Close" not in hist:
        return {
            "ticker": symbol,
            "yfinance_symbol": yf_symbol,
            "status": "no_data",
            "error": "yfinance returned no daily close rows",
        }
    closes = hist["Close"].dropna()
    if closes.empty:
        return {
            "ticker": symbol,
            "yfinance_symbol": yf_symbol,
            "status": "no_close",
            "error": "yfinance returned no usable close values",
        }
    latest_index = closes.index[-1]
    if hasattr(latest_index, "date"):
        market_date = latest_index.date().isoformat()
    else:
        market_date = str(latest_index)[:10]
    return {
        "ticker": symbol,
        "yfinance_symbol": yf_symbol,
        "status": "ok",
        "close": round(float(closes.iloc[-1]), 4),
        "market_date": market_date,
        "source": "yfinance",
        "retrieval_method": "yf.Ticker(symbol).history(period='5d', interval='1d')",
        "retrieved_at_utc": utc_now(),
    }


def build(extra: list[str]) -> dict[str, Any]:
    targets, reasons = collect_targets(extra)
    rows = []
    for symbol in targets:
        row = fetch_close(symbol)
        row["target_reasons"] = reasons.get(symbol, [])
        row["review_only"] = True
        row["execution_freshness_approved"] = False
        rows.append(row)

    ok_rows = [row for row in rows if row.get("status") == "ok"]
    market_dates = sorted({str(row.get("market_date")) for row in ok_rows if row.get("market_date")})
    errors = [f"{row.get('ticker')}: {row.get('status')} {row.get('error') or ''}".strip() for row in rows if row.get("status") != "ok"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors and rows else "warning" if rows else "blocked",
        "purpose": "Closed-market/post-close final quote overlay for recommendation candidates; review-only and non-executing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "capital_review_queue": rel(CAPITAL_QUEUE),
            "finance_decision_factory": rel(DECISION_FACTORY),
            "ph_owner_review_candidate_packet": rel(PH_PACKET),
            "tier_weighted_freshness_resolution": rel(TIER_RESOLUTION),
            "wf78_ticker_freshness_ledger": rel(FRESHNESS_LEDGER),
            "finance_state_existing_post_close_overlay": rel(FINANCE_STATE_DB),
        },
        "summary": {
            "target_count": len(rows),
            "ok_count": len(ok_rows),
            "error_count": len(errors),
            "latest_market_date": market_dates[-1] if market_dates else None,
            "target_tickers": targets,
            "ok_tickers": [row["ticker"] for row in ok_rows],
            "error_tickers": [row["ticker"] for row in rows if row.get("status") != "ok"],
            "next_safe_action": "Use as the preferred closed-market quote overlay for recommendation prep; do not treat as execution freshness or approval.",
        },
        "rows": rows,
        "validation": {"status": "ok" if rows else "error", "errors": [] if rows else ["no target tickers"], "warnings": errors},
        "stop_lines": [
            "This ledger does not mutate ticker cards, portfolio notes, canon, SQL canon, or brokerage/account state.",
            "Post-close quotes support recommendation review only and do not authorize paper/live execution.",
            "Owner approval remains required for capital deployment or execution.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", default=[], help="Extra ticker to include.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build(args.ticker)
    if args.write:
        atomic_write_json(args.out, payload)
    print(json.dumps({"status": payload["status"], "out": rel(args.out), "summary": payload["summary"], "validation": payload["validation"]}, indent=2))
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
