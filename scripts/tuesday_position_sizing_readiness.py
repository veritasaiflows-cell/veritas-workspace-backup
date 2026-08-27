#!/usr/bin/env python3
"""Build a current position-sizing readiness packet.

This is advisory/report-only preparation. It recommends owner-gated sizing zones
and paper-request readiness, but it does not authorize or submit live/paper
orders, mutate portfolio/canon files, move cash, or infer approval.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "position-sizing-readiness-current.json"
DEFAULT_MD = TMP / "position-sizing-readiness-current.md"
LEGACY_JSON = TMP / "tuesday-position-sizing-readiness-2026-05-26.json"
LEGACY_MD = TMP / "tuesday-position-sizing-readiness-2026-05-26.md"

AUTHORITY_FALSE = {
    "live_trade_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_this_packet": False,
    "paper_order_cancel_allowed_by_this_packet": False,
    "owner_approval_inferred": False,
    "owner_approval_granted_for_orders": False,
    "portfolio_or_canon_apply_allowed": False,
    "sizing_apply_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "probability_or_win_rate_claim_allowed": False,
}

PRIORITY_TICKERS = ["ETN", "VRT", "CME", "PH", "NVDA", "ITA", "GE", "LIN", "GOOG", "JPM", "MSFT", "GS"]
STARTER_BY_TIER = {
    "tier1": (400, 600),
    "tier2": (200, 350),
    "tier3": (50, 150),
    "blocked": (0, 0),
}
TARGET_BY_TIER = {
    "tier1": (800, 1200),
    "tier2": (400, 700),
    "tier3": (100, 300),
    "blocked": (0, 0),
}

TIER_OVERRIDE = {
    "ETN": "tier1",
    "NVDA": "tier2",
    "VRT": "tier2",
    "CME": "tier2",
    "PH": "tier2",
    "ITA": "tier2",
    "GE": "tier2",
    "LIN": "tier2",
    "GOOG": "tier1",
    "JPM": "tier1",
    "MSFT": "tier1",
    "GS": "tier2",
}


def normalize_band_status(value: Any) -> str:
    return str(value or "UNKNOWN").upper().replace(" ", "_")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("ticker", "")).upper(): r for r in rows if isinstance(r, dict) and r.get("ticker")}


def paper_position_map(paper: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = paper.get("positions") if isinstance(paper.get("positions"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        normalized = dict(row)
        if "qty" not in normalized and "quantity" in normalized:
            normalized["qty"] = normalized.get("quantity")
        out[str(normalized["symbol"]).upper()] = normalized
    return out


def money_range(values: tuple[int, int]) -> dict[str, int]:
    return {"low_usd": values[0], "high_usd": values[1], "mid_usd": int(round((values[0] + values[1]) / 2))}


def fnum(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def recommended_status(row: dict[str, Any], ticker: str) -> tuple[str, str]:
    state = str(row.get("state") or "").upper()
    band_status = normalize_band_status(row.get("band_status") or row.get("entry_band_status") or row.get("band_position"))
    auto_tier = str(row.get("auto_tier") or "")
    auto_state = str(row.get("auto_state") or "")
    if ticker == "ETN" and band_status == "IN_BAND" and "DEPLOYABLE" in state:
        return "ready_if_fresh_quote_confirms", "Primary current candidate; existing paper ETN 1 share can count as starter exposure unless Randall wants incremental add."
    if ticker in {"VRT", "CME", "PH"} and band_status == "IN_BAND":
        return "conditional_ready_after_owner_promotion", "Promotion-review candidate; prepare exact paper request only after owner chooses it and fresh quote remains in band."
    if ticker == "NVDA" and band_status == "IN_BAND":
        return "cap_limited_conditional", "In band, but direct Tech is already at cap; only use if Randall explicitly accepts substitution/exception."
    if ticker in {"ITA", "LIN", "GOOG", "JPM", "MSFT", "GS"} and band_status.startswith("ABOVE"):
        return "wait_for_band_no_chase", "Do not chase above the written band; prepare alert/order terms only if Tuesday pullback re-enters band or owner approves a new band review."
    if ticker == "GE" and band_status == "IN_BAND":
        return "review_only_not_promoted", "Good Defense/aerospace review candidate, but still watch-lane; requires promotion/sizing decision before any paper package."
    if band_status == "BELOW_STOP":
        return "blocked_below_stop", "Blocked until reclaim/fresh review."
    if band_status == "IN_BAND" and (auto_tier == "Tier A" or auto_state.startswith("A-")):
        return "ready_if_fresh_quote_confirms", "Current Tier A in-band candidate; exact paper/deployment terms still require owner approval and fresh guard proof."
    if band_status == "IN_BAND" and (auto_tier == "Tier B" or auto_state.startswith("B-")):
        return "conditional_ready_after_owner_promotion", "Current Tier B in-band candidate; promotion/capital judgment remains main-session and owner-gated."
    return "monitor", "Monitor only."


def index_deployment(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    groups = data.get("groups") if isinstance(data.get("groups"), dict) else {}
    for group, rows in groups.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or not row.get("ticker"):
                continue
            item = dict(row)
            item.setdefault("state", group)
            out[str(row["ticker"]).upper()] = item
    return out


def index_technical(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = data.get("records")
    if isinstance(rows, dict):
        return {str(ticker).upper(): dict(row) for ticker, row in rows.items() if isinstance(row, dict)}
    if isinstance(rows, list):
        return {str(row.get("ticker")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}
    return {}


def index_auto_tier(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    return {str(row.get("ticker")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def band_config(config: dict[str, Any], ticker: str) -> dict[str, Any]:
    bands = config.get("entry_bands") if isinstance(config.get("entry_bands"), dict) else {}
    value = bands.get(ticker) or bands.get(ticker.upper()) or bands.get(ticker.lower()) or {}
    return value if isinstance(value, dict) else {}


def classify_band(price: Any, low: Any, high: Any, stop: Any) -> str | None:
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return None
    try:
        if stop is not None and price_f < float(stop):
            return "BELOW_STOP"
    except (TypeError, ValueError):
        pass
    try:
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return None
    if price_f < low_f:
        return "BELOW_BAND"
    if price_f > high_f:
        return "ABOVE_BAND"
    return "IN_BAND"


def tier_from_auto(auto_row: dict[str, Any], ticker: str) -> str:
    if ticker in TIER_OVERRIDE:
        return TIER_OVERRIDE[ticker]
    auto_tier = str(auto_row.get("auto_tier") or "")
    if auto_tier == "Tier A":
        return "tier1"
    if auto_tier == "Tier B":
        return "tier2"
    if auto_tier == "Tier C":
        return "tier3"
    return "tier2"


def same_money(left: Any, right: Any) -> bool:
    left_f = fnum(left)
    right_f = fnum(right)
    if left_f is None or right_f is None:
        return left_f is right_f
    return round(left_f, 2) == round(right_f, 2)


def capital_validator_no_candidate_warning(validation: dict[str, Any]) -> bool:
    """Treat an empty capital packet window as review-only, not a blocker."""
    if validation.get("status") != "warning":
        return False
    summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    if int(summary.get("critical") or 0) != 0:
        return False
    findings = validation.get("findings") if isinstance(validation.get("findings"), list) else []
    return any(
        isinstance(item, dict)
        and item.get("severity") == "warning"
        and item.get("issue") == "no capital recommendation packets produced for this window"
        for item in findings
    )


def load_sql_reference_index(tickers: list[str]) -> dict[str, dict[str, Any]]:
    try:
        from finance_sql_canon_access import FinanceSqlCanonAccess

        client = FinanceSqlCanonAccess()
        validation = client.validate()
        if validation.get("status") != "ok":
            return {}
        refs: dict[str, dict[str, Any]] = {}
        for symbol in tickers:
            reference = client.reference_level(symbol)
            if not reference:
                continue
            refs[symbol] = {
                "reference_price_low": reference.reference_price_low,
                "reference_price_high": reference.reference_price_high,
                "reference_invalidation_level": reference.reference_invalidation_level,
                "reference_confidence": reference.reference_confidence,
                "reference_band_status": reference.reference_band_status,
                "authority_class": reference.authority_class,
                "fallback_rule": reference.fallback_rule,
            }
        return refs
    except Exception:
        return {}


def build() -> dict[str, Any]:
    watch = load(TMP / "tuesday-entry-opportunity-watchlist-2026-05-26.json")
    matrix = load(TMP / "sector-allocation-decision-matrix.json")
    deployment = load(TMP / "deployment-readiness-surface.json")
    technical = load(TMP / "technical-refresh.json")
    auto_tier = load(TMP / "wf78-auto-tier-routing.json")
    paper = load(TMP / "finance-intelligence-state-paper-positions.json")
    if not paper:
        paper = load(TMP / "alpaca-paper-readiness" / "current-paper-holdings-readonly.json")
    validation = load(TMP / "capital-deployment-recommendation-validation.json")
    probability = load(TMP / "probability-readiness-report.json")
    config = load(TMP / "portfolio-config.json")

    watch_rows = by_ticker(watch.get("watchlist") if isinstance(watch.get("watchlist"), list) else [])
    matrix_rows = by_ticker(matrix.get("top_candidate_watch_order") if isinstance(matrix.get("top_candidate_watch_order"), list) else [])
    deployment_rows = index_deployment(deployment)
    technical_rows = index_technical(technical)
    auto_rows = index_auto_tier(auto_tier)
    positions = paper_position_map(paper)
    overlay = (((config.get("portfolio") or {}).get("capital_base_sizing_overlay")) or {}) if isinstance(config.get("portfolio"), dict) else {}
    capital_base = int(overlay.get("capital_base_usd") or 10000)
    cash_target = int(overlay.get("cash_target_usd") or 1000)
    investable = int(overlay.get("investable_capital_usd") or 9000)

    current_tier_tickers = [
        ticker for ticker, row in auto_rows.items()
        if str(row.get("auto_tier") or "") in {"Tier A", "Tier B"} or str(row.get("auto_state") or "").startswith(("A-", "B-"))
    ]
    candidate_tickers = sorted(set(PRIORITY_TICKERS) | set(current_tier_tickers) | set(deployment_rows))
    sql_reference_rows = load_sql_reference_index(candidate_tickers)
    candidates = []
    for ticker in candidate_tickers:
        config_band = band_config(config, ticker)
        row = dict(watch_rows.get(ticker) or matrix_rows.get(ticker) or {})
        row.update({k: v for k, v in deployment_rows.get(ticker, {}).items() if v not in (None, "", [], {})})
        tech = technical_rows.get(ticker, {})
        auto = auto_rows.get(ticker, {})
        if auto:
            row.update({k: v for k, v in auto.items() if k in {"auto_tier", "auto_state", "route_reason", "route_priority"}})
        if not row and not auto:
            continue
        sql_reference = sql_reference_rows.get(ticker, {})
        tier = tier_from_auto(auto, ticker)
        close = fnum(row.get("close") if row.get("close") is not None else tech.get("close"))
        legacy_band_low = row.get("band_low") if row.get("band_low") is not None else config_band.get("low")
        legacy_band_high = row.get("band_high") if row.get("band_high") is not None else config_band.get("high")
        legacy_stop = row.get("stop") if row.get("stop") is not None else config_band.get("stop")
        band_low = sql_reference.get("reference_price_low")
        band_high = sql_reference.get("reference_price_high")
        stop = sql_reference.get("reference_invalidation_level")
        band_source = "state/finance/finance-canon.sqlite:reference_levels" if any(
            value is not None for value in (band_low, band_high, stop)
        ) else "legacy_candidate_or_portfolio_config"
        band_low = band_low if band_low is not None else legacy_band_low
        band_high = band_high if band_high is not None else legacy_band_high
        stop = stop if stop is not None else legacy_stop
        band_status = normalize_band_status(
            classify_band(close, band_low, band_high, stop)
            or row.get("band_status")
            or row.get("entry_band_status")
            or row.get("band_position")
            or classify_band(close, band_low, band_high, stop)
        )
        superseded_legacy_band = None
        if band_source.startswith("state/finance") and not (
            same_money(legacy_band_low, band_low)
            and same_money(legacy_band_high, band_high)
            and same_money(legacy_stop, stop)
        ):
            superseded_legacy_band = {
                "status": "superseded_by_sql_canon_reference",
                "band_low": legacy_band_low,
                "band_high": legacy_band_high,
                "stop": legacy_stop,
                "source": "legacy Tuesday watchlist/deployment row or portfolio-config fallback",
            }
        row["close"] = close
        row["band_low"] = band_low
        row["band_high"] = band_high
        row["stop"] = stop
        row["band_status"] = band_status
        status, note = recommended_status(row, ticker)
        if status in {"wait_for_band_no_chase", "blocked_below_stop", "monitor", "review_only_not_promoted", "cap_limited_conditional"} and ticker not in {"NVDA", "GE"}:
            effective_tier = "blocked"
        else:
            effective_tier = tier
        starter = money_range(STARTER_BY_TIER[effective_tier])
        target = money_range(TARGET_BY_TIER[effective_tier])
        paper_pos = positions.get(ticker, {})
        current_paper_value = fnum(paper_pos.get("market_value"))
        current_paper_qty = fnum(paper_pos.get("qty"))
        incremental_mid = max(starter["mid_usd"] - (current_paper_value or 0), 0) if status == "ready_if_fresh_quote_confirms" else starter["mid_usd"]
        candidates.append({
            "ticker": ticker,
            "readiness": status,
            "tier": tier,
            "recommended_starter_notional": starter,
            "recommended_target_notional": target,
            "suggested_tuesday_incremental_paper_notional_usd": round(incremental_mid, 2),
            "suggested_order_style_if_approved": "limit/day preferred; market/day only with exact owner approval and WF67 guard validation",
            "fresh_quote_required": True,
            "state": row.get("state"),
            "close_reference": close,
            "band_low": band_low,
            "band_high": band_high,
            "stop": stop,
            "band_source": band_source,
            "sql_canon_reference": sql_reference or None,
            "superseded_legacy_band_context": superseded_legacy_band,
            "band_status": band_status,
            "wf78_auto_tier": auto.get("auto_tier"),
            "wf78_auto_state": auto.get("auto_state"),
            "paper_current_qty": current_paper_qty,
            "paper_current_market_value_usd": current_paper_value,
            "decision_note": note,
            "must_have_before_any_order": [
                "fresh quote confirms band/stop state",
                "Randall gives exact paper order terms or explicitly approves generated exact request artifact",
                "WF67 request artifact generated",
                "WF67 dry run passes",
                "paper/live isolation guard validation passes",
                "fresh short-lived kill switch exists for the execution window",
                "main-session capital-package notification is prepared",
            ],
            "authority": AUTHORITY_FALSE | {"sizing_recommendation_review_allowed": True},
        })

    critical = []
    warnings = []
    if validation.get("status") != "ok":
        if capital_validator_no_candidate_warning(validation):
            warnings.append("capital deployment validator has no recommendation packets for this window")
        else:
            critical.append("capital deployment validator is not ok")
    if probability.get("verdict") != "NOT_READY":
        # Not a blocker, but this packet intentionally avoids probability language either way.
        pass
    for c in candidates:
        auth = c["authority"]
        for key in AUTHORITY_FALSE:
            if auth.get(key) is not False:
                critical.append(f"{c['ticker']} authority drift: {key}")

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else "review_only_ok" if warnings else "ok",
        "market_day_target": "current review window",
        "purpose": "Owner-gated sizing readiness and paper-order preparation checklist for the current review window; no order execution authority.",
        "capital_framework": {
            "capital_base_usd": capital_base,
            "cash_reserve_target_usd": cash_target,
            "investable_capital_usd": investable,
            "fractional_shares_default": True,
            "two_tranche_default": True,
            "risk_rules": "Tier 1 8-12%; Tier 2 4-7%; Tier 3 1-3%; 15% normal single-name ceiling; 25% sector cap.",
        },
        "source_artifacts": [
            "tmp/tuesday-entry-opportunity-watchlist-2026-05-26.json",
            "tmp/sector-allocation-decision-matrix.json",
            "tmp/deployment-readiness-surface.json",
            "tmp/technical-refresh.json",
            "tmp/wf78-auto-tier-routing.json",
            "tmp/capital-deployment-recommendation-validation.json",
            "tmp/probability-readiness-report.json",
            "tmp/finance-intelligence-state-paper-positions.json",
            "tmp/wf67-paper-position-state.sqlite",
            "tmp/alpaca-paper-readiness/current-paper-holdings-readonly.json",
            "tmp/portfolio-config.json",
            "state/finance/finance-canon.sqlite",
        ],
        "trust_state": {
            "capital_deployment_validator": validation.get("status"),
            "capital_deployment_validator_classification": "no_candidates_review_only" if warnings else "standard",
            "probability_readiness": probability.get("verdict"),
            "paper_account_read_mode": paper.get("method"),
            "paper_positions_seen": list(positions.keys()),
            "downgrade": "Review-only readiness surface; fresh quote/guard proof remains required before any exact paper request or capital decision.",
        },
        "authority": AUTHORITY_FALSE | {"sizing_recommendation_review_allowed": True, "paper_request_preparation_allowed_after_exact_owner_terms": True},
        "candidates": candidates,
        "critical_findings": critical,
        "warning_findings": warnings,
        "owner_decisions_needed_before_tuesday_orders": [
            "Choose which candidates, if any, should become exact WF67 paper request artifacts.",
            "Confirm paper-only versus live. Live remains blocked here; paper can proceed only through WF67 guards.",
            "Confirm order style: limit/day preferred; market/day requires exact owner approval.",
            "Confirm whether any existing paper position counts as starter or whether to add incremental notional.",
            "Confirm whether NVDA/GOOG/MSFT tech-cap exposure should be avoided, substituted, or explicitly exception-reviewed.",
        ],
    }


def render(packet: dict[str, Any]) -> str:
    lines = [
        "# Current Position Sizing Readiness",
        "",
        f"Generated: {packet['generated_at_utc']}",
        "",
        "## Verdict",
        "",
        "Ready for review prep, not execution. Current Tier A/B and deployment-surface names are refreshed into an owner-gated sizing-readiness packet; exact capital/paper action still requires fresh guard proof and Randall approval.",
        "",
        "## Capital framework",
        "",
        f"- Capital base: ${packet['capital_framework']['capital_base_usd']:,}",
        f"- Cash reserve target: ${packet['capital_framework']['cash_reserve_target_usd']:,}",
        f"- Investable capital: ${packet['capital_framework']['investable_capital_usd']:,}",
        "- Fractional shares + two-tranche sizing by default.",
        "",
        "## Sizing readiness table",
        "",
        "| Ticker | Readiness | Starter | Target | Incremental paper prep | Band status | Note |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for c in packet["candidates"]:
        starter = c["recommended_starter_notional"]
        target = c["recommended_target_notional"]
        lines.append(
            f"| {c['ticker']} | {c['readiness']} | ${starter['low_usd']}-${starter['high_usd']} | ${target['low_usd']}-${target['high_usd']} | ${c['suggested_tuesday_incremental_paper_notional_usd']} | {c.get('band_status')} | {c['decision_note']} |"
        )
    lines += [
        "",
        "## Owner decisions needed before any Tuesday order",
        "",
    ]
    lines += [f"- {item}" for item in packet["owner_decisions_needed_before_tuesday_orders"]]
    lines += [
        "",
        "## Authority boundary",
        "",
        "No live trade, brokerage/account action, money movement, paper order execution, owner approval inference, portfolio/canon apply, sizing apply, cash/risk-rule mutation, or probability/win-rate claim is authorized by this packet.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_JSON))
    parser.add_argument("--md-output", default=str(DEFAULT_MD))
    parser.add_argument("--write-legacy", action="store_true", help="Also refresh the historical 2026-05-26 compatibility paths.")
    args = parser.parse_args()
    packet = build()
    if args.write:
        atomic_write_json(args.output, packet)
        atomic_write_text(args.md_output, render(packet))
        if args.write_legacy:
            atomic_write_json(LEGACY_JSON, packet)
            atomic_write_text(LEGACY_MD, render(packet))
    print(json.dumps({"status": packet["status"], "candidates": len(packet["candidates"]), "critical": len(packet["critical_findings"]), "output": args.output}, indent=2))
    return 0 if packet["status"] in {"ok", "review_only_ok"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
