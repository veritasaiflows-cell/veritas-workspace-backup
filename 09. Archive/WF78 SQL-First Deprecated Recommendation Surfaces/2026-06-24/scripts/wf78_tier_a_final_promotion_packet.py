#!/usr/bin/env python3
"""Deprecated-for-authority static Tier A promotion input packet.

This packet is for label/admission review only. It checks current quote inputs
against the written bands/stops from ticker cards and prepares inputs for the
automated non-capital tier router. It does not apply Tier A labels, mutate
canon/portfolio state, infer capital/execution approval, or authorize
paper/live/account action.

As of 2026-06-25 this script is retained only as a compatibility/audit surface.
Forward routing must use dynamic SQL/router/coverage/confidence proof and
lane-qualified fields (`review_lane`, `instrument_class`, and `lane_tier`).
Do not use this packet as the current Tier A denominator or recommendation
source.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
ADJUDICATION = TMP / "wf78-production-tier-adjudication.json"
SHARED_HEADER = TMP / "wf78-packet-shared-header.json"
DEFAULT_OUT = TMP / "wf78-tier-a-final-promotion-packet.json"
SCHEMA = "veritas.wf78_tier_a_final_promotion_packet.v1"
DEPRECATION_STATUS = {
    "deprecated_for_authority": True,
    "deprecated_at_utc": "2026-06-25T03:00:00Z",
    "replacement_surfaces": [
        "tmp/wf78-auto-tier-routing.json",
        "tmp/wf78-clean-tier-roster.json",
        "tmp/wf78-tier-semantics-guard.json",
    ],
    "archive_readiness": "ready_after_one_clean_lane_qualified_validation_cycle_and_explicit_archive_approval",
}

DEFAULT_CANDIDATES = ["GOOG", "NVDA", "VRT"]

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "auto_routing_input_packet_allowed": False,
    "tier_a_label_applied": False,
    "canon_or_portfolio_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_or_execution_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}


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


def parse_quote(raw: str) -> tuple[str, float]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--quote must use TICKER=PRICE")
    ticker, price = raw.split("=", 1)
    ticker = ticker.strip().upper()
    if not ticker:
        raise argparse.ArgumentTypeError("quote ticker is empty")
    try:
        parsed = float(price)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid price for {ticker}: {price}") from exc
    return ticker, parsed


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


def candidate_from_card(ticker: str, quote: float | None, quote_source: str, quote_time_utc: str | None, adjudication_rank: dict[str, Any]) -> dict[str, Any]:
    card_path = CARD_DIR / f"{ticker}.current.json"
    card = load_dict(card_path)
    band = as_dict(card.get("price_band_stop"))
    technical = as_dict(card.get("technical_posture"))
    valuation = as_dict(card.get("valuation"))
    support = as_dict(card.get("recommendation_support"))
    low = band.get("entry_band_low")
    high = band.get("entry_band_high")
    stop = band.get("stop_or_invalidation")
    band_status = current_band_status(quote, low, high, stop)
    blockers: list[str] = []
    cautions: list[str] = []

    if quote is None:
        blockers.append("current quote missing")
    if band_status != "IN_BAND":
        blockers.append(f"current quote not in written band: {band_status}")
    if quote is not None and stop is not None and quote <= stop:
        blockers.append("current quote is at/below stop")
    if technical.get("macro_gate") == "DEGRADED":
        cautions.append("macro/technical gate is DEGRADED")
    forward_pe = valuation.get("forward_pe")
    if isinstance(forward_pe, (int, float)) and forward_pe > 30:
        cautions.append(f"forward PE elevated at {forward_pe}")
    for item in as_list(card.get("risk_register")):
        if isinstance(item, dict) and item.get("severity") in {"critical", "warning"}:
            cautions.append(str(item.get("detail") or item.get("category") or "risk flag"))

    decision_status = "eligible_for_auto_tier_a_routing" if not blockers else "blocked_before_auto_routing"
    return {
        "ticker": ticker,
        "name": card.get("name") or card.get("company_name") or adjudication_rank.get("name"),
        "adjudication_rank": adjudication_rank.get("rank"),
        "adjudication_score": adjudication_rank.get("score"),
        "prior_recommendation": adjudication_rank.get("recommendation"),
        "quote": {
            "current_price": quote,
            "source": quote_source,
            "quote_time_utc": quote_time_utc,
        },
        "written_band": {
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "card_reference_price": band.get("latest_known_price"),
            "card_band_status": band.get("band_status"),
            "current_band_status": band_status,
        },
        "card_context": {
            "recommendation_posture": support.get("posture"),
            "state_source": support.get("state_source") or support.get("readiness_state_source"),
            "technical_data_date": technical.get("data_date"),
            "ma_posture": technical.get("ma_posture"),
            "macro_gate": technical.get("macro_gate"),
            "forward_pe": forward_pe,
        },
        "decision_status": decision_status,
        "blockers": sorted(set(blockers)),
        "cautions": sorted(set(cautions)),
        "source_artifacts": [rel(card_path), rel(ADJUDICATION)],
        "authority_boundary": {
            "tier_a_label_applied": False,
            "owner_approval_required_for_routing": False,
            "owner_approval_required_for_capital_or_execution": True,
            "paper_or_live_execution_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
        },
    }


def build_report(candidates: list[str], quotes: dict[str, float], quote_source: str, quote_time_utc: str | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    adjudication = load_dict(ADJUDICATION)
    by_ticker = {str(row.get("ticker") or "").upper(): row for row in as_list(adjudication.get("rows")) if isinstance(row, dict)}
    rows = [candidate_from_card(ticker, quotes.get(ticker), quote_source, quote_time_utc, as_dict(by_ticker.get(ticker))) for ticker in candidates]
    eligible = [row for row in rows if row.get("decision_status") == "eligible_for_auto_tier_a_routing"]
    blocked = [row for row in rows if row.get("decision_status") != "eligible_for_auto_tier_a_routing"]

    add_check(checks, "adjudication_packet_present", bool(adjudication), rel(ADJUDICATION))
    add_check(checks, "adjudication_validation_ok", as_dict(adjudication.get("validation")).get("status") == "ok", as_dict(adjudication.get("validation")))
    add_check(checks, "candidate_count_three", len(rows) == 3, {"count": len(rows), "expected": 3})
    add_check(checks, "quotes_present_for_all_candidates", all(row["quote"]["current_price"] is not None for row in rows), [row["ticker"] for row in rows if row["quote"]["current_price"] is None])
    add_check(checks, "all_candidates_in_band", all(row["written_band"]["current_band_status"] == "IN_BAND" for row in rows), {row["ticker"]: row["written_band"]["current_band_status"] for row in rows})
    add_check(checks, "no_tier_label_applied", AUTHORITY_BOUNDARY["tier_a_label_applied"] is False, AUTHORITY_BOUNDARY["tier_a_label_applied"])
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    status = "deprecated_compatibility_packet" if not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Tier A Final Promotion Compatibility Packet",
        "purpose": "Retained compatibility/audit packet for the retired static Tier A promotion path; not current routing authority.",
        "deprecation_status": DEPRECATION_STATUS,
        "shared_header_ref": rel(SHARED_HEADER),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "production_adjudication": rel(ADJUDICATION),
            "ticker_cards": rel(CARD_DIR),
            "shared_header": rel(SHARED_HEADER),
        },
        "summary": {
            "candidate_count": len(rows),
            "eligible_for_historical_tier_a_routing_count": len(eligible),
            "blocked_in_historical_packet_count": len(blocked),
            "eligible_tickers": [row["ticker"] for row in eligible],
            "blocked_tickers": [row["ticker"] for row in blocked],
            "auto_routing_action": "deprecated_for_authority; use SQL-first lane-qualified wf78_auto_tier_router.py output instead.",
            "recommended_answer": "do_not_use_as_recommendation_surface",
            "next_safe_action": "Use SQL-first lane-qualified WF78 router and downstream gates; reserve this packet for compatibility review only.",
            "deprecated_for_authority": True,
            "forward_replacement": "Use dynamic lane-qualified WF78 router output instead of this static GOOG/NVDA/VRT packet.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "This packet does not apply Tier A labels.",
            "This packet does not approve any buy/sell/paper/live order.",
            "This packet does not mutate canon, portfolio, sizing, cash, sleeve, or risk-rule state.",
            "This packet does not infer capital deployment or execution approval from validation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", choices=DEFAULT_CANDIDATES, help="candidate ticker; defaults to GOOG/NVDA/VRT")
    parser.add_argument("--quote", action="append", type=parse_quote, required=True, help="current quote as TICKER=PRICE")
    parser.add_argument("--quote-source", required=True)
    parser.add_argument("--quote-time-utc")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    candidates = args.candidate or DEFAULT_CANDIDATES
    quotes = dict(args.quote)
    report = build_report(candidates, quotes, args.quote_source, args.quote_time_utc)
    out_path = Path(args.out)
    if args.write:
        atomic_write_json(out_path, report)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(out_path),
                "summary": report.get("summary"),
                "validation": {
                    "status": as_dict(report.get("validation")).get("status"),
                    "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
                    "warnings": len(as_list(as_dict(report.get("validation")).get("warnings"))),
                },
            },
            indent=2,
        )
    )
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
