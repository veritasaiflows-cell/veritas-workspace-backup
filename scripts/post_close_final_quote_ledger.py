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
TIER_A_COVERAGE_GATE = TMP / "tier-a-trade-grade-coverage-gate.json"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"
TRADE_GRADE_DECISION_CARDS = TMP / "trade-grade-decision-cards.json"

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


def existing_post_close_overlays() -> dict[str, dict[str, Any]]:
    if not FINANCE_STATE_DB.exists():
        return {}
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
        return {}

    overlays: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        symbol = ticker(item.get("ticker"))
        raw = parse_json(item.get("raw_json"))
        price_band_stop = as_dict(raw.get("price_band_stop"))
        post_close = as_dict(price_band_stop.get("post_close_final_quote"))
        sources = {
            str(item.get("price_source") or ""),
            str(item.get("source_path") or ""),
            str(price_band_stop.get("price_source") or ""),
        }
        claims_post_close_ledger = any("post-close-final-quote-ledger.json" in source for source in sources)
        if not symbol or not (post_close or claims_post_close_ledger):
            continue
        latest_price = price_band_stop.get("latest_known_price")
        if latest_price is None:
            continue
        overlays[symbol] = {
            "ticker": symbol,
            "yfinance_symbol": yfinance_symbol(symbol),
            "status": "ok",
            "close": round(float(latest_price), 4),
            "market_date": post_close.get("market_date"),
            "source": "finance_state_existing_post_close_overlay",
            "original_source": post_close.get("source"),
            "retrieval_method": "local finance_state post_close_final_quote fallback after provider miss",
            "retrieved_at_utc": post_close.get("retrieved_at_utc"),
            "cached_overlay_used": True,
            "cached_overlay_source_path": item.get("source_path") or item.get("price_source"),
        }
    return overlays


def yfinance_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def market_date_newer(candidate: Any, current: Any) -> bool:
    if not candidate or not current:
        return False
    return str(candidate) > str(current)


def tier_a_coverage_gate_fresh_quote_targets() -> list[str]:
    gate = load_dict(TIER_A_COVERAGE_GATE)
    cohorts = as_dict(gate.get("cohorts"))
    tickers: set[str] = set()
    for cohort_rows in cohorts.values():
        for row in as_list(cohort_rows):
            row = as_dict(row)
            blockers = {str(item) for item in as_list(row.get("depth_blockers"))}
            if "fresh_quote_required" not in blockers:
                continue
            symbol = ticker(row.get("ticker"))
            if symbol:
                tickers.add(symbol)
    return sorted(tickers)


def tier_ab_stale_decision_card_price_targets() -> list[str]:
    cards_payload = load_dict(TRADE_GRADE_DECISION_CARDS)
    cards = [as_dict(card) for card in as_list(cards_payload.get("cards"))]
    tier_cards = [
        card for card in cards
        if str(card.get("auto_tier") or card.get("tier") or "") in {"Tier A", "Tier B"}
    ]
    market_dates = [
        str(as_dict(card.get("current_price")).get("market_date"))
        for card in tier_cards
        if as_dict(card.get("current_price")).get("market_date")
    ]
    expected_date = max(market_dates) if market_dates else None
    if not expected_date:
        return []
    stale: set[str] = set()
    for card in tier_cards:
        symbol = ticker(card.get("ticker"))
        price = as_dict(card.get("current_price"))
        if symbol and price.get("market_date") != expected_date:
            stale.add(symbol)
    return sorted(stale)


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

    for symbol in tier_a_coverage_gate_fresh_quote_targets():
        add(symbol, "tier_a_trade_grade_coverage_gate_fresh_quote_blocker")

    for symbol in tier_ab_stale_decision_card_price_targets():
        add(symbol, "tier_a_b_stale_decision_card_price_context")

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
    cached_overlays = existing_post_close_overlays()
    rows = []
    provider_warnings = []
    for symbol in targets:
        row = fetch_close(symbol)
        cached = cached_overlays.get(symbol)
        if row.get("status") != "ok":
            provider_warnings.append(f"{symbol}: {row.get('status')} {row.get('error') or ''}".strip())
            if cached:
                row = dict(cached)
                row["provider_status_before_cache"] = provider_warnings[-1]
        elif cached and market_date_newer(cached.get("market_date"), row.get("market_date")):
            provider_warnings.append(
                f"{symbol}: provider_market_date {row.get('market_date')} older than cached_overlay {cached.get('market_date')}"
            )
            row = dict(cached)
            row["provider_status_before_cache"] = provider_warnings[-1]
        row["target_reasons"] = reasons.get(symbol, [])
        row["review_only"] = True
        row["execution_freshness_approved"] = False
        rows.append(row)

    ok_rows = [row for row in rows if row.get("status") == "ok"]
    cached_rows = [row for row in rows if row.get("cached_overlay_used") is True]
    market_dates = sorted({str(row.get("market_date")) for row in ok_rows if row.get("market_date")})
    errors = [f"{row.get('ticker')}: {row.get('status')} {row.get('error') or ''}".strip() for row in rows if row.get("status") != "ok"]
    warnings = errors + [warning for warning in provider_warnings if warning and warning not in errors]
    status = "ok" if not errors and rows else "warning" if rows else "blocked"
    if cached_rows and status == "ok":
        status = "warning"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Closed-market/post-close final quote overlay for recommendation candidates; review-only and non-executing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "capital_review_queue": rel(CAPITAL_QUEUE),
            "finance_decision_factory": rel(DECISION_FACTORY),
            "ph_owner_review_candidate_packet": rel(PH_PACKET),
            "tier_weighted_freshness_resolution": rel(TIER_RESOLUTION),
            "wf78_ticker_freshness_ledger": rel(FRESHNESS_LEDGER),
            "tier_a_trade_grade_coverage_gate": rel(TIER_A_COVERAGE_GATE),
            "trade_grade_decision_cards": rel(TRADE_GRADE_DECISION_CARDS),
            "finance_state_existing_post_close_overlay": rel(FINANCE_STATE_DB),
        },
        "summary": {
            "target_count": len(rows),
            "ok_count": len(ok_rows),
            "error_count": len(errors),
            "cached_overlay_count": len(cached_rows),
            "provider_warning_count": len(provider_warnings),
            "latest_market_date": market_dates[-1] if market_dates else None,
            "target_tickers": targets,
            "ok_tickers": [row["ticker"] for row in ok_rows],
            "error_tickers": [row["ticker"] for row in rows if row.get("status") != "ok"],
            "next_safe_action": "Use as the preferred closed-market quote overlay for recommendation prep; do not treat as execution freshness or approval.",
        },
        "rows": rows,
        "validation": {"status": "ok" if rows else "error", "errors": [] if rows else ["no target tickers"], "warnings": warnings},
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
