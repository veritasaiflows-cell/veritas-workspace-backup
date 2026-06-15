#!/usr/bin/env python3
"""Repair WF78 missing band-context blockers as review-only proof rows.

This fills the missing current price / band-status context for rows that already
have owner band/stop lineage. It writes a repair packet only and does not mutate
ticker cards, owner notes, deployment surfaces, canon, portfolio, SQL canon/cache,
or any execution/account surface.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from band_refresh import ENGINE_VERSION as BAND_ENGINE_VERSION
from band_refresh import calculate_entry_band
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT = TMP / "wf78-missing-band-context-repair.json"
POSITION_PROPOSAL = TMP / "wf78-position-sizing-integration-proposal.json"
DECISION_CARDS = TMP / "trade-grade-decision-cards.json"
SCHEMA = "veritas.wf78_missing_band_context_repair.v1"
FALLBACK_TARGETS = ["KTOS", "SMCI"]
DEFAULT_TARGET_TIERS = ("Tier A", "Tier B")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "missing_band_context_repair_only": True,
    "automated_non_capital_routing_allowed": True,
    "repair_applied": False,
    "ticker_card_mutation_allowed": False,
    "owner_note_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_AUTHORITY = {"review_only", "missing_band_context_repair_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


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


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def classify_band(price: float | None, low: float | None, high: float | None, stop: float | None) -> str | None:
    if price is None:
        return None
    if stop is not None and price < stop:
        return "BELOW_STOP"
    if low is None or high is None:
        return "NO_BAND"
    if price < low:
        return "BELOW_BAND"
    if price > high:
        return "ABOVE_BAND"
    return "IN_BAND"


def rows_by_ticker(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_dict(path)
    return {
        ticker(row.get("ticker")): as_dict(row)
        for row in as_list(payload.get("rows"))
        if ticker(as_dict(row).get("ticker"))
    }


def decision_grade_band_missing(card: dict[str, Any]) -> bool:
    band = as_dict(card.get("entry_band"))
    stop = as_dict(card.get("stop_or_invalidation"))
    return (
        band.get("low") is None
        or band.get("high") is None
        or stop.get("level") is None
        or band.get("band_status") in {None, "", "UNKNOWN", "missing_required_refresh"}
    )


def card_uses_repair_context(card: dict[str, Any]) -> bool:
    repair_path = rel(OUT)
    band = as_dict(card.get("entry_band"))
    price = as_dict(card.get("current_price"))
    stop = as_dict(card.get("stop_or_invalidation"))
    return repair_path in {
        str(band.get("source_path") or "").replace("\\", "/"),
        str(price.get("source") or "").replace("\\", "/"),
        str(stop.get("source_path") or "").replace("\\", "/"),
    }


def missing_decision_grade_targets(tiers: tuple[str, ...] = DEFAULT_TARGET_TIERS) -> list[str]:
    payload = load_dict(DECISION_CARDS)
    cards = as_list(payload.get("cards"))
    return sorted({
        ticker(card.get("ticker"))
        for card in cards
        if isinstance(card, dict)
        and card.get("auto_tier") in tiers
        and decision_grade_band_missing(card)
        and ticker(card.get("ticker"))
    })


def dynamic_targets(tiers: tuple[str, ...] = DEFAULT_TARGET_TIERS) -> list[str]:
    payload = load_dict(DECISION_CARDS)
    cards = as_list(payload.get("cards"))
    if not cards:
        return FALLBACK_TARGETS
    tickers = [
        ticker(card.get("ticker"))
        for card in cards
        if isinstance(card, dict)
        and card.get("auto_tier") in tiers
        and (decision_grade_band_missing(card) or card_uses_repair_context(card))
    ]
    unique = sorted({item for item in tickers if item})
    return unique


def decision_card_tiers() -> dict[str, str]:
    payload = load_dict(DECISION_CARDS)
    return {
        ticker(card.get("ticker")): str(card.get("auto_tier") or "")
        for card in as_list(payload.get("cards"))
        if isinstance(card, dict) and ticker(card.get("ticker"))
    }


def fetch_close(symbol: str) -> dict[str, Any]:
    try:
        hist = yf.Ticker(symbol).history(period="1y")
    except Exception as exc:
        return {"status": "blocked_fetch_error", "error": f"{type(exc).__name__}: {exc}"}
    if hist is None or hist.empty or "Close" not in hist:
        return {"status": "blocked_no_history", "error": "yfinance returned no 1y close history"}
    closes = hist["Close"].dropna()
    if closes.empty:
        return {"status": "blocked_no_close", "error": "no close values returned"}
    return {
        "status": "ok",
        "source": "yfinance",
        "retrieval_method": "yf.Ticker(symbol).history(period='1y')",
        "latest_close": round(float(closes.iloc[-1]), 2),
        "data_date": closes.index[-1].strftime("%Y-%m-%d"),
        "close_count": int(len(closes)),
    }


def fetch_technical_band_inputs(symbol: str) -> dict[str, Any]:
    try:
        hist = yf.Ticker(symbol).history(period="260d")
    except Exception as exc:
        return {"status": "blocked_fetch_error", "error": f"{type(exc).__name__}: {exc}"}
    if hist is None or hist.empty:
        return {"status": "blocked_no_history", "error": "yfinance returned no 260d history"}
    required = {"High", "Low", "Close"}
    if not required.issubset(set(hist.columns)):
        return {"status": "blocked_missing_ohlc", "error": f"missing columns: {sorted(required - set(hist.columns))}"}
    close = hist["Close"].dropna()
    if len(close) < 200:
        return {"status": "blocked_insufficient_history", "error": f"need at least 200 closes, got {len(close)}"}
    high = hist["High"]
    low = hist["Low"]
    close_prev = hist["Close"].shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - close_prev).abs(),
            (low - close_prev).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=True).dropna()
    latest_close = float(close.iloc[-1])
    atr20_series = tr.rolling(20, min_periods=20).mean().dropna()
    atr20 = float(atr20_series.iloc[-1]) if not atr20_series.empty else None
    if atr20 is None:
        return {"status": "blocked_insufficient_atr", "error": "need at least 20 true-range rows"}
    return {
        "status": "ok",
        "source": "yfinance",
        "retrieval_method": "yf.Ticker(symbol).history(period='260d')",
        "latest_close": round(latest_close, 2),
        "data_date": close.index[-1].strftime("%Y-%m-%d"),
        "close_count": int(len(close)),
        "ema20": round(float(close.ewm(span=20, adjust=False).mean().iloc[-1]), 2),
        "ema50": round(float(close.ewm(span=50, adjust=False).mean().iloc[-1]), 2),
        "sma200": round(float(close.rolling(200).mean().iloc[-1]), 2),
        "atr20": round(atr20, 2),
        "atrp20": round(atr20 / latest_close, 4) if latest_close else None,
    }


def technical_band_context(symbol: str) -> dict[str, Any]:
    inputs = fetch_technical_band_inputs(symbol)
    if inputs.get("status") != "ok":
        return {
            "status": "blocked",
            "engine_version": BAND_ENGINE_VERSION,
            "inputs": inputs,
            "band": {
                "entry_band_low": None,
                "entry_band_high": None,
                "stop_or_invalidation": None,
                "band_status": None,
            },
            "warnings": [inputs.get("error") or str(inputs.get("status"))],
        }
    calc = calculate_entry_band(
        close=as_float(inputs.get("latest_close")),
        ema20=as_float(inputs.get("ema20")),
        ema50=as_float(inputs.get("ema50")),
        sma200=as_float(inputs.get("sma200")),
        atr20=as_float(inputs.get("atr20")),
        atrp20=as_float(inputs.get("atrp20")),
        earnings="CLEAR",
        current_low=None,
        current_high=None,
        current_stop=None,
    )
    low = as_float(calc.get("low"))
    high = as_float(calc.get("high"))
    stop = as_float(calc.get("stop"))
    band_status = calc.get("status") or classify_band(as_float(inputs.get("latest_close")), low, high, stop)
    complete = low is not None and high is not None and stop is not None and band_status not in {None, "", "NO_BAND"}
    return {
        "status": "ok" if complete else "blocked",
        "engine_version": BAND_ENGINE_VERSION,
        "inputs": inputs,
        "band": {
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "band_status": band_status,
            "band_source": "review_only_technical_band_context",
            "stop_source": "review_only_technical_band_context",
            "entry_band_method": calc.get("method"),
            "entry_band_type": calc.get("type"),
            "trend_stack": calc.get("trend"),
            "stop_basis": calc.get("stop_basis"),
            "band_confidence": calc.get("confidence"),
            "distance_to_band_pct": calc.get("distance_to_band_pct"),
            "sma_envelope_low": calc.get("sma_low"),
            "sma_envelope_high": calc.get("sma_high"),
        },
        "warnings": as_list(calc.get("warnings")),
    }


def card_band(symbol: str) -> tuple[dict[str, Any], dict[str, Any]]:
    card = load_dict(CARD_DIR / f"{symbol}.current.json")
    band = as_dict(card.get("price_band_stop"))
    reference = as_dict(card.get("entry_stop_reference_metadata"))
    return band, reference


def repair_row(symbol: str, proposal_rows: dict[str, dict[str, Any]], tier_override: str | None = None) -> dict[str, Any]:
    source_row = proposal_rows.get(symbol, {})
    band, reference = card_band(symbol)
    price = fetch_close(symbol)
    technical_context = technical_band_context(symbol)
    technical_band = as_dict(technical_context.get("band"))
    low = as_float(band.get("entry_band_low"))
    high = as_float(band.get("entry_band_high"))
    stop = as_float(band.get("stop_or_invalidation"))
    repaired_low = low if low is not None else as_float(technical_band.get("entry_band_low"))
    repaired_high = high if high is not None else as_float(technical_band.get("entry_band_high"))
    repaired_stop = stop if stop is not None else as_float(technical_band.get("stop_or_invalidation"))
    current = as_float(price.get("latest_close"))
    lineage = as_dict(reference.get("source_lineage"))
    lineage_available = bool(lineage.get("owner_source_path") and lineage.get("source_timestamp") and lineage.get("source_sha256"))
    owner_ready = price.get("status") == "ok" and low is not None and high is not None and stop is not None and lineage_available
    technical_ready = (
        price.get("status") == "ok"
        and technical_context.get("status") == "ok"
        and repaired_low is not None
        and repaired_high is not None
        and repaired_stop is not None
    )
    if owner_ready:
        status = "ready_for_position_sizing_repair_recheck"
    elif technical_ready:
        status = "ready_for_decision_grade_band_context"
    else:
        status = "blocked_incomplete_band_context_repair"
    return {
        "ticker": symbol,
        "tier": source_row.get("tier") or tier_override or "Tier B",
        "route_state": source_row.get("route_state"),
        "prior_proposal_status": source_row.get("proposal_status"),
        "repair_status": status,
        "current_price": current,
        "price_data_date": price.get("data_date"),
        "price_source": price,
        "band": {
            "entry_band_low": repaired_low,
            "entry_band_high": repaired_high,
            "stop_or_invalidation": repaired_stop,
            "band_status": technical_band.get("band_status") if low is None or high is None or stop is None else classify_band(current, low, high, stop),
            "band_source": band.get("band_source") or technical_band.get("band_source"),
            "stop_source": band.get("stop_source") or technical_band.get("stop_source"),
            "source_timestamp": reference.get("source_timestamp") or price.get("data_date") or technical_context.get("inputs", {}).get("data_date"),
            "source_artifact_path": rel(OUT),
        },
        "fresh_band_status": classify_band(current, repaired_low, repaired_high, repaired_stop),
        "technical_band_context": technical_context,
        "owner_source_lineage": {
            "available": lineage_available,
            "owner_source_path": lineage.get("owner_source_path"),
            "source_timestamp": lineage.get("source_timestamp"),
            "source_sha256": lineage.get("source_sha256"),
            "entry_stop_reference_status": reference.get("status"),
        },
        "proposed_next_step": (
            f"Re-run position-sizing integration review for {symbol} using repaired current price and band status; do not apply."
            if owner_ready
            else f"Use review-only technical band context for {symbol} decision-grade routing proof; do not apply to canon or cards directly."
            if technical_ready
            else f"Keep {symbol} blocked until current price, band, stop, and owner lineage are all present."
        ),
        "repair_applied": False,
        "source_artifacts": [
            rel(POSITION_PROPOSAL),
            rel(CARD_DIR / f"{symbol}.current.json"),
            "yfinance 1y close history",
        ],
        "ticker_card_mutation_allowed": False,
        "owner_note_mutation_allowed": False,
        "deployment_surface_mutation_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def build(targets: list[str] | None = None) -> dict[str, Any]:
    proposal_rows = rows_by_ticker(POSITION_PROPOSAL)
    tier_by_ticker = decision_card_tiers()
    missing_targets = missing_decision_grade_targets()
    missing_tier_counts = Counter(tier_by_ticker.get(symbol) or "unknown" for symbol in missing_targets)
    selected_targets = targets or dynamic_targets()
    rows = [repair_row(symbol, proposal_rows, tier_by_ticker.get(symbol)) for symbol in selected_targets]
    status_counts = Counter(str(row.get("repair_status")) for row in rows)
    band_counts = Counter(str(row.get("fresh_band_status")) for row in rows)
    tier_counts = Counter(str(row.get("tier") or "unknown") for row in rows)
    errors: list[str] = []
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if len(rows) != len(selected_targets):
        errors.append(f"expected {len(selected_targets)} repair rows, got {len(rows)}")
    if any(row.get("repair_applied") for row in rows):
        errors.append("one or more rows imply applied repair")
    if any(
        row.get("ticker_card_mutation_allowed")
        or row.get("owner_note_mutation_allowed")
        or row.get("deployment_surface_mutation_allowed")
        or row.get("capital_deployment_approved")
        or row.get("trade_or_execution_approved")
        or row.get("paper_or_live_execution_allowed")
        or row.get("owner_approval_inferred")
        for row in rows
    ):
        errors.append("row authority boundary widened")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only repair packet for WF78 missing band-context blockers.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(POSITION_PROPOSAL), "tmp/ticker-intelligence-cards/*.current.json", "yfinance 1y close history"],
        "summary": {
            "target_source": "trade_grade_decision_cards_tier_a_b_missing_decision_grade_band",
            "target_semantics": "active_missing_or_repair_backed_tier_a_b_band_context",
            "target_tiers": list(DEFAULT_TARGET_TIERS),
            "target_tickers": selected_targets,
            "target_tier_counts": dict(tier_counts.most_common()),
            "target_count": len(selected_targets),
            "missing_decision_grade_band_count": len(missing_targets),
            "missing_decision_grade_band_tickers": missing_targets,
            "missing_decision_grade_band_tier_counts": dict(missing_tier_counts.most_common()),
            "repair_row_count": len(rows),
            "ready_for_recheck_count": status_counts.get("ready_for_position_sizing_repair_recheck", 0),
            "ready_for_decision_grade_band_context_count": status_counts.get("ready_for_decision_grade_band_context", 0),
            "repair_status_counts": dict(status_counts.most_common()),
            "fresh_band_status_counts": dict(band_counts.most_common()),
            "repair_applied": False,
            "next_safe_action": "Use ready rows as review-only band-context proof for WF84/WF85 decision-grade routing; do not mutate canon, cards, or portfolio notes.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Band-context repair proof only; no ticker-card, deployment-surface, canon, portfolio, or SQL-canon mutation.",
            "Generated rows may target Tier A/B decision-grade band coverage, but daily coverage proof is not canon apply authority.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 missing band-context repair packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--target", action="append", dest="targets", help="Explicit ticker target; default derives Tier A/B missing decision-grade band rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    explicit_targets = sorted({ticker(item) for item in (args.targets or []) if ticker(item)})
    report = build(explicit_targets or None)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"ready={report['summary']['ready_for_recheck_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
