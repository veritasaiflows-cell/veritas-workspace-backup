#!/usr/bin/env python3
"""Build the WF78 A-DEPLOY-CANDIDATE capital-review queue.

This is an owner-review preparation artifact only. It ranks A-READY names for
possible capital-review card work, but it does not approve capital deployment,
trade execution, paper/live orders, brokerage/account action, or portfolio/canon
mutation.
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
DEFAULT_OUT = TMP / "wf78-capital-review-queue.json"
DEFAULT_DB = TMP / "wf78-capital-review-queue.sqlite"

AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
ROUTING_DELTA = TMP / "wf78-routing-delta.json"
TIER_A_PACKET = TMP / "wf78-tier-a-final-promotion-packet.json"
CARD_SUMMARY = TMP / "ticker-card-refresh-gate-card-build-summary.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
MARKET_HARDENING = TMP / "market-execution-readiness-cron-hardening.json"
POST_CLOSE_FINAL_QUOTES = TMP / "post-close-final-quote-ledger.json"
WF84_DB = TMP / "canonical-finance-data-plane.sqlite"
WF84_PHASE = TMP / "canonical-finance-data-plane-phase6-10.json"

SCHEMA = "veritas.wf78_capital_review_queue.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "capital_review_preparation_only": True,
    "automated_non_capital_routing_allowed": True,
    "owner_action_required": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "customer_or_external_delivery_allowed": False,
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
    "capital_review_preparation_only",
    "automated_non_capital_routing_allowed",
    "owner_action_required",
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


def quote_freshness_status(quote: dict[str, Any], stale_row: dict[str, Any], card_row: dict[str, Any]) -> str:
    missing_count = int(card_row.get("missing_or_stale_count") or 0)
    if missing_count > 0 or stale_row:
        return "fresh_quote_required"
    if quote.get("current_price") is None:
        return "missing_quote"
    return "fresh_enough_for_review_packet"


def quote_snapshot_by_ticker(quote_proof: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker_key(row.get("symbol")): row
        for row in as_list(quote_proof.get("snapshots"))
        if isinstance(row, dict) and ticker_key(row.get("symbol"))
    }


def post_close_quote_by_ticker(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker_key(row.get("ticker")): row
        for row in as_list(ledger.get("rows"))
        if isinstance(row, dict) and ticker_key(row.get("ticker")) and row.get("status") == "ok"
    }


def connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def wf84_switch_enabled() -> bool:
    phase = load_dict(WF84_PHASE)
    summary = as_dict(phase.get("summary"))
    validation = as_dict(phase.get("validation"))
    authority = as_dict(phase.get("authority_boundary"))
    return (
        phase.get("status") == "ok"
        and validation.get("status") == "ok"
        and summary.get("consumer_default_switch_allowed") is True
        and authority.get("default_route_switch_allowed") is True
        and authority.get("capital_deployment_allowed") is False
        and authority.get("trade_or_execution_approved") is False
        and authority.get("paper_or_live_execution_allowed") is False
        and authority.get("owner_approval_inferred") is False
    )


def wf84_canonical_index() -> dict[str, dict[str, Any]]:
    if not WF84_DB.exists() or not wf84_switch_enabled():
        return {}
    try:
        with connect_ro(WF84_DB) as conn:
            authority = conn.execute("SELECT * FROM v_authority_boundary_false").fetchone()
            if authority and any(dict(authority).values()):
                return {}
            return {
                ticker_key(row["ticker"]): dict(row)
                for row in conn.execute("SELECT * FROM v_current_decision_overview")
            }
    except sqlite3.Error:
        return {}


def effective_band_fields(raw_band: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    if canonical:
        return {
            "entry_band_low": canonical.get("entry_band_low") if canonical.get("entry_band_low") is not None else raw_band.get("entry_band_low"),
            "entry_band_high": canonical.get("entry_band_high") if canonical.get("entry_band_high") is not None else raw_band.get("entry_band_high"),
            "stop_or_invalidation": canonical.get("stop_or_invalidation") if canonical.get("stop_or_invalidation") is not None else raw_band.get("stop_or_invalidation"),
            "card_reference_price": raw_band.get("card_reference_price"),
            "card_band_status": raw_band.get("card_band_status"),
            "current_band_status": canonical.get("band_status") or raw_band.get("current_band_status"),
            "source": "wf84_canonical_overlay",
            "decision_factory_band_snapshot": {
                "entry_band_low": raw_band.get("entry_band_low"),
                "entry_band_high": raw_band.get("entry_band_high"),
                "stop_or_invalidation": raw_band.get("stop_or_invalidation"),
                "current_band_status": raw_band.get("current_band_status"),
            },
        }
    return {**raw_band, "source": "tier_a_packet"}


def canonical_summary(canonical: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok" if canonical else "missing_or_switch_disabled",
        "ticker": canonical.get("ticker"),
        "auto_tier": canonical.get("auto_tier"),
        "auto_state": canonical.get("auto_state"),
        "primary_state": canonical.get("primary_state"),
        "queue_state": canonical.get("queue_state"),
        "actionability": canonical.get("actionability"),
        "latest_known_price": canonical.get("latest_known_price"),
        "band_status": canonical.get("band_status"),
        "entry_band_low": canonical.get("entry_band_low"),
        "entry_band_high": canonical.get("entry_band_high"),
        "stop_or_invalidation": canonical.get("stop_or_invalidation"),
        "authority_flags_false": (
            not any(int(canonical.get(key) or 0) for key in (
                "capital_deployment_approved",
                "trade_or_execution_approved",
                "paper_or_live_execution_allowed",
                "owner_approval_inferred",
            ))
            if canonical else None
        ),
    }


def current_band_status(price: float | None, low: float | None, high: float | None, stop: float | None) -> str:
    if price is None or low is None or high is None:
        return "UNKNOWN"
    if stop is not None and price < stop:
        return "BELOW_STOP"
    if price < low:
        return "BELOW_BAND"
    if price > high:
        return "ABOVE_BAND"
    return "IN_BAND"


def stale_row_reasons(stale_row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for item in as_list(stale_row.get("missing_or_stale")):
        item_dict = as_dict(item)
        family = item_dict.get("family")
        if family:
            reasons.append(str(family))
    return sorted(set(reasons))


def quote_current_for_non_executing_review(
    ticker: str,
    snapshot: dict[str, Any],
    market_hardening: dict[str, Any],
) -> bool:
    summary = as_dict(market_hardening.get("summary"))
    if market_hardening.get("status") not in {"ok", "warning"}:
        return False
    if int(summary.get("critical_count") or 0) > 0:
        return False
    if int(summary.get("stale_or_missing_snapshot_count") or 0) > 0:
        return False
    if int(summary.get("nonfresh_snapshot_count") or 0) > 0:
        return False
    if ticker_key(ticker) in {ticker_key(item) for item in as_list(summary.get("missing_required_symbols"))}:
        return False
    if snapshot.get("price") is None:
        return False
    return snapshot.get("freshness_status") in {"fresh", "current_but_not_intraday_fresh"}


def effective_freshness_context(
    ticker: str,
    stale_count: int,
    stale_row: dict[str, Any],
    snapshot: dict[str, Any],
    market_hardening: dict[str, Any],
) -> dict[str, Any]:
    reasons = stale_row_reasons(stale_row)
    only_quote_stale = bool(reasons) and set(reasons) == {"fresh_price_quote"}
    current_for_review = quote_current_for_non_executing_review(ticker, snapshot, market_hardening)
    resolved_for_review = stale_count > 0 and only_quote_stale and current_for_review
    return {
        "stale_reasons": reasons,
        "quote_snapshot": {
            "price": snapshot.get("price"),
            "bid": snapshot.get("bid"),
            "ask": snapshot.get("ask"),
            "source_timestamp_utc": snapshot.get("source_timestamp_utc"),
            "received_at_utc": snapshot.get("received_at_utc"),
            "freshness_status": snapshot.get("freshness_status"),
            "age_seconds": snapshot.get("age_seconds"),
        } if snapshot else {},
        "market_hardening_status": market_hardening.get("status"),
        "resolved_for_non_executing_review_card": resolved_for_review,
        "execution_freshness_approved": False,
        "note": (
            "Same-market-day quote proof clears the stale quote blocker for non-executing owner-card preparation only; "
            "it does not authorize execution or guarantee intraday freshness."
            if resolved_for_review
            else None
        ),
    }


def readiness_state(stale_count: int, blockers: list[Any], current_band_status: str) -> str:
    if stale_count > 0:
        return "A-DEPLOY-CANDIDATE-FRESHNESS-BLOCKED"
    if blockers:
        return "A-DEPLOY-CANDIDATE-BLOCKED"
    if current_band_status and current_band_status != "IN_BAND":
        return "A-DEPLOY-CANDIDATE-WAIT-FOR-BAND"
    return "A-DEPLOY-CANDIDATE-REVIEW-READY"


def effective_card_prep_blockers(blockers: list[Any], quote_context: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Separate true card-prep blockers from authority stop-line reminders."""
    effective: list[str] = []
    cautions: list[str] = []
    for raw in blockers:
        text = str(raw or "")
        lowered = text.lower()
        if quote_context.get("resolved_for_non_executing_review_card") and "fresh quote" in lowered:
            cautions.append(f"{text} (cleared for non-executing review by same-market-day quote proof)")
        elif "owner promotion/selection still required" in lowered:
            cautions.append(text)
        elif "grants no paper/live execution authority" in lowered:
            cautions.append(text)
        elif "capital deployment" in lowered or "execution" in lowered or "approval" in lowered:
            cautions.append(text)
        else:
            effective.append(text)
    return sorted(set(effective)), sorted(set(cautions))


def rank_score(tier_a_row: dict[str, Any], stale_count: int, blockers: list[Any], cautions: list[Any], band_status: str) -> float:
    score = float(tier_a_row.get("adjudication_score") or 0)
    if band_status == "IN_BAND":
        score += 5
    score -= stale_count * 10
    score -= len(blockers) * 25
    score -= len(cautions) * 2
    return round(score, 2)


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    auto_router = load_dict(AUTO_ROUTER)
    delta = load_dict(ROUTING_DELTA)
    tier_a = load_dict(TIER_A_PACKET)
    card_summary = load_dict(CARD_SUMMARY)
    stale = load_dict(STALE_TICKERS)
    quote_proof = load_dict(QUOTE_PROOF)
    market_hardening = load_dict(MARKET_HARDENING)
    post_close_quotes = load_dict(POST_CLOSE_FINAL_QUOTES)

    auto_rows = by_ticker(as_list(auto_router.get("rows")))
    tier_a_rows = by_ticker(as_list(tier_a.get("rows")))
    card_rows = by_ticker(as_list(card_summary.get("cards")))
    stale_rows = by_ticker(as_list(stale.get("stale_ticker_cards")))
    quote_snapshots = quote_snapshot_by_ticker(quote_proof)
    post_close_quote_rows = post_close_quote_by_ticker(post_close_quotes)
    canonical_rows = wf84_canonical_index()
    candidates = as_list(delta.get("capital_review_candidates"))

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_dict = as_dict(candidate)
        ticker = ticker_key(candidate_dict.get("ticker"))
        if not ticker:
            continue
        auto_row = auto_rows.get(ticker, {})
        tier_row = tier_a_rows.get(ticker, {})
        card_row = card_rows.get(ticker, {})
        stale_row = stale_rows.get(ticker, {})
        quote = as_dict(tier_row.get("quote"))
        raw_band = as_dict(tier_row.get("written_band"))
        canonical = canonical_rows.get(ticker, {})
        band = effective_band_fields(raw_band, canonical)
        blockers = as_list(candidate_dict.get("blockers")) or as_list(stale_row.get("blockers")) or as_list(tier_row.get("blockers"))
        cautions = as_list(tier_row.get("cautions"))
        stale_count = int(candidate_dict.get("missing_or_stale_count") or card_row.get("missing_or_stale_count") or 0)
        final_quote = post_close_quote_rows.get(ticker, {})
        final_close = final_quote.get("close")
        quote_context = effective_freshness_context(ticker, stale_count, stale_row, quote_snapshots.get(ticker, {}), market_hardening)
        quote_snapshot = as_dict(quote_context.get("quote_snapshot"))
        snapshot_price = quote_snapshot.get("price")
        snapshot_current_for_review = (
            quote_current_for_non_executing_review(ticker, quote_snapshots.get(ticker, {}), market_hardening)
            and snapshot_price is not None
        )
        effective_price = snapshot_price if snapshot_current_for_review else (final_close if final_close is not None else quote.get("current_price"))
        band_status = (
            current_band_status(
                effective_price,
                band.get("entry_band_low"),
                band.get("entry_band_high"),
                band.get("stop_or_invalidation"),
            )
            if effective_price is not None
            else str(band.get("current_band_status") or band.get("card_band_status") or "")
        )
        if final_close is not None:
            quote_context["post_close_final_quote"] = {
                "close": final_close,
                "market_date": final_quote.get("market_date"),
                "retrieved_at_utc": final_quote.get("retrieved_at_utc"),
                "source": final_quote.get("source"),
                "used_as_closed_market_overlay": not snapshot_current_for_review,
            }
        post_close_resolved = final_close is not None
        effective_stale_count = 0 if quote_context["resolved_for_non_executing_review_card"] or post_close_resolved else stale_count
        effective_stale_row_present = bool(stale_row) and not quote_context["resolved_for_non_executing_review_card"] and not post_close_resolved
        effective_blockers, authority_cautions = effective_card_prep_blockers(blockers, quote_context)
        queue_state = readiness_state(effective_stale_count, effective_blockers, band_status)
        rows.append({
            "ticker": ticker,
            "name": auto_row.get("name") or tier_row.get("name"),
            "sector": auto_row.get("sector"),
            "queue": "A-DEPLOY-CANDIDATE",
            "queue_state": queue_state,
            "rank_score": rank_score(tier_row, stale_count, blockers, cautions, band_status),
            "auto_tier": auto_row.get("auto_tier") or candidate_dict.get("auto_tier"),
            "auto_state": auto_row.get("auto_state") or candidate_dict.get("auto_state"),
            "route_reason": auto_row.get("route_reason") or candidate_dict.get("route_reason"),
            "adjudication_rank": tier_row.get("adjudication_rank"),
            "adjudication_score": tier_row.get("adjudication_score"),
            "recommendation_support": candidate_dict.get("recommendation_support"),
            "quote": {
                **quote,
                **({
                    "current_price": snapshot_price,
                    "source": "intraday_quote_snapshot_proof",
                    "quote_time_utc": quote_snapshot.get("source_timestamp_utc"),
                    "market_date": quote_snapshot.get("received_at_utc", "")[:10],
                    "previous_packet_price": quote.get("current_price"),
                } if snapshot_current_for_review else ({
                    "current_price": final_close,
                    "source": "post_close_final_quote_ledger",
                    "quote_time_utc": final_quote.get("retrieved_at_utc"),
                    "market_date": final_quote.get("market_date"),
                    "previous_packet_price": quote.get("current_price"),
                } if final_close is not None else {})),
            },
            "written_band": band,
            "wf84_canonical_data_plane": canonical_summary(canonical),
            "current_price": effective_price,
            "current_band_status": band_status or None,
            "stop_or_invalidation": band.get("stop_or_invalidation"),
            "quote_freshness_status": (
                "current_market_day_quote_available_for_non_executing_review"
                if snapshot_current_for_review else
                "post_close_final_quote_available_for_non_executing_review"
                if post_close_resolved else
                "current_market_day_quote_available_for_non_executing_review"
                if quote_context["resolved_for_non_executing_review_card"]
                else quote_freshness_status(quote, stale_row, card_row)
            ),
            "missing_or_stale_count": effective_stale_count,
            "raw_card_missing_or_stale_count": stale_count,
            "missing_or_stale": as_list(stale_row.get("missing_or_stale")),
            "quote_repair_context": quote_context,
            "blockers": effective_blockers,
            "raw_blockers": blockers,
            "cautions": sorted(set(cautions + authority_cautions)),
            "source_artifacts": sorted(set(as_list(tier_row.get("source_artifacts")) + [rel(AUTO_ROUTER), rel(ROUTING_DELTA), rel(QUOTE_PROOF), rel(MARKET_HARDENING), rel(POST_CLOSE_FINAL_QUOTES)])),
            "owner_action_required": True,
            "requires_fresh_quote_band_stop_before_deployment_review": effective_stale_count > 0 or effective_stale_row_present,
            "capital_review_card_preparable": queue_state == "A-DEPLOY-CANDIDATE-REVIEW-READY",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "next_safe_action": (
                "Refresh quote/band/stop and source-open blockers before owner approval-card preparation."
                if effective_stale_count > 0 or effective_stale_row_present
                else "Prepare a non-executing owner capital-review card; do not execute or imply approval."
            ),
        })
    rows.sort(key=lambda row: (-float(row.get("rank_score") or 0), int(row.get("adjudication_rank") or 999), str(row.get("ticker"))))
    for index, row in enumerate(rows, start=1):
        row["queue_rank"] = index
    sources = {
        "auto_router": rel(AUTO_ROUTER),
        "routing_delta": rel(ROUTING_DELTA),
        "tier_a_final_packet": rel(TIER_A_PACKET),
        "ticker_card_summary": rel(CARD_SUMMARY),
        "stale_tickers": rel(STALE_TICKERS),
        "quote_snapshot_proof": rel(QUOTE_PROOF),
        "market_execution_readiness_hardening": rel(MARKET_HARDENING),
        "post_close_final_quote_ledger": rel(POST_CLOSE_FINAL_QUOTES),
        "wf84_canonical_data_plane_sqlite": rel(WF84_DB),
        "wf84_phase6_10_switch_proof": rel(WF84_PHASE),
    }
    return rows, sources


def build_report() -> dict[str, Any]:
    rows, sources = build_rows()
    checks: list[dict[str, Any]] = []
    for path, name in [
        (AUTO_ROUTER, "auto_router_present"),
        (ROUTING_DELTA, "routing_delta_present"),
        (TIER_A_PACKET, "tier_a_packet_present"),
        (CARD_SUMMARY, "ticker_card_summary_present"),
    ]:
        add_check(checks, name, path.exists(), rel(path))
    add_check(checks, "candidate_rows_present", bool(rows), len(rows), severity="warning")
    add_check(checks, "all_rows_owner_action_required", all(row.get("owner_action_required") is True for row in rows), None)
    add_check(checks, "all_rows_capital_deployment_false", all(row.get("capital_deployment_approved") is False for row in rows), None)
    add_check(checks, "all_rows_trade_execution_false", all(row.get("trade_or_execution_approved") is False for row in rows), None)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    review_ready = [row for row in rows if row.get("capital_review_card_preparable")]
    freshness_blocked = [row for row in rows if row.get("requires_fresh_quote_band_stop_before_deployment_review")]
    if review_ready:
        next_safe_action = "Prepare non-executing owner capital-review cards for review-ready rows; do not execute or imply approval."
    elif rows:
        next_safe_action = "Refresh stale quote/band/stop blockers first; then prepare non-executing owner approval cards for review-ready rows only."
    else:
        next_safe_action = "No A-DEPLOY-CANDIDATE rows are currently queued; keep monitoring non-capital routing evidence."
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - A-DEPLOY-CANDIDATE Capital Review Queue",
        "purpose": "Rank A-READY names for non-executing owner capital-review card preparation while preserving all capital/execution approval stop lines.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": sources,
        "summary": {
            "candidate_count": len(rows),
            "review_ready_count": len(review_ready),
            "freshness_blocked_count": len(freshness_blocked),
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "top_candidate": rows[0].get("ticker") if rows else None,
            "next_safe_action": next_safe_action,
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "checks": checks,
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "A-DEPLOY-CANDIDATE is review-card preparation only.",
            "No capital deployment, trade/order execution, paper/live action, brokerage/account action, or money movement is approved.",
            "No portfolio/canon/ticker-card/SQL-canon mutation is allowed from this artifact.",
            "Randall's exact approval is required before any capital deployment or execution step.",
        ],
    }


def write_db(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.execute("DROP TABLE IF EXISTS capital_review_queue")
        conn.execute(
            """
            CREATE TABLE capital_review_queue (
                ticker TEXT PRIMARY KEY,
                queue_rank INTEGER NOT NULL,
                queue_state TEXT NOT NULL,
                rank_score REAL NOT NULL,
                auto_tier TEXT,
                auto_state TEXT,
                current_price REAL,
                current_band_status TEXT,
                missing_or_stale_count INTEGER NOT NULL,
                owner_action_required INTEGER NOT NULL,
                capital_deployment_approved INTEGER NOT NULL,
                trade_or_execution_approved INTEGER NOT NULL,
                raw_json TEXT NOT NULL
            ) STRICT
            """
        )
        for row in as_list(report.get("rows")):
            row_dict = as_dict(row)
            conn.execute(
                """
                INSERT INTO capital_review_queue (
                    ticker, queue_rank, queue_state, rank_score, auto_tier, auto_state,
                    current_price, current_band_status, missing_or_stale_count,
                    owner_action_required, capital_deployment_approved,
                    trade_or_execution_approved, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_dict.get("ticker"),
                    int(row_dict.get("queue_rank") or 0),
                    row_dict.get("queue_state"),
                    float(row_dict.get("rank_score") or 0),
                    row_dict.get("auto_tier"),
                    row_dict.get("auto_state"),
                    row_dict.get("current_price"),
                    row_dict.get("current_band_status"),
                    int(row_dict.get("missing_or_stale_count") or 0),
                    1 if row_dict.get("owner_action_required") else 0,
                    1 if row_dict.get("capital_deployment_approved") else 0,
                    1 if row_dict.get("trade_or_execution_approved") else 0,
                    json.dumps(row_dict, sort_keys=True),
                ),
            )
        conn.execute("PRAGMA integrity_check")


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    out = resolve(args.out)
    db = resolve(args.db)
    report = build_report()
    if args.write:
        atomic_write_json(out, report)
    if args.write_db:
        write_db(report, db)
    print(json.dumps({
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "db": rel(db) if args.write_db else None,
        "summary": report["summary"],
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(report.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
