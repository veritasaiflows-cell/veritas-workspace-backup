#!/usr/bin/env python3
"""Deprecated-for-authority Tier B final-promotion input packet.

Tier B is an active research bench, not a deployment queue. This packet can
check the production-bench candidates from the 42-name adjudication layer or
the next Phase 2 eligible C->B names from the funnel gate. It feeds automated
non-capital routing. It does not apply Tier B labels, mutate canon/portfolio
state, infer capital/execution approval, or authorize paper/live/account action.

As of 2026-06-25 this script is retained only as a compatibility/audit surface.
Forward routing must use SQL-first canon plus lane-qualified WF78 router fields
(`review_lane`, `instrument_class`, and `lane_tier`). Do not use this packet as
current Tier B authority, a recommendation surface, or owner-card source.
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
PHASE2_GATE = TMP / "wf78-tier-funnel-promotion-gate.json"
EVIDENCE_REPAIR = TMP / "wf78-tier-b-evidence-repair.json"
SHARED_HEADER = TMP / "wf78-packet-shared-header.json"
DEFAULT_OUT = TMP / "wf78-tier-b-final-promotion-packet.json"
SCHEMA = "veritas.wf78_tier_b_final_promotion_packet.v1"

DEFAULT_MAX_CANDIDATES = 5
SOURCES = {"production_bench", "phase2_eligible"}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "auto_routing_input_packet_allowed": False,
    "tier_b_label_applied": False,
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

DEPRECATION_STATUS = {
    "deprecated_for_authority": True,
    "deprecated_at_utc": "2026-06-25T03:50:00Z",
    "replacement_surfaces": [
        "tmp/wf78-auto-tier-routing.json",
        "tmp/wf78-clean-tier-roster.json",
        "tmp/wf78-tier-semantics-guard.json",
    ],
    "archive_readiness": "ready_after_phase_runner_cutover_and_explicit_archive_gate",
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


def source_open_usable(card: dict[str, Any]) -> bool:
    authority = as_dict(card.get("authority_boundary"))
    sources = as_list(card.get("source_artifacts"))
    source_required = authority.get("source_open_required_before_final_recommendation_or_action_claim") is True
    has_universe = any("data\\finance\\universe-v1.json" in str(item.get("path") or "") or "data/finance/universe-v1.json" in str(item.get("path") or "") for item in sources if isinstance(item, dict))
    return bool(source_required and sources and has_universe)


def risk_summaries(card: dict[str, Any]) -> tuple[list[str], list[str]]:
    cautions: list[str] = []
    blockers: list[str] = []
    for item in as_list(card.get("risk_register")):
        if not isinstance(item, dict):
            continue
        detail = str(item.get("detail") or item.get("category") or "risk flag")
        family = str(item.get("family") or "")
        severity = str(item.get("severity") or "")
        if family in {"deployment_readiness_surface", "price_band_stop_position_sizing"}:
            cautions.append(f"{family}: {detail}")
        elif severity == "critical":
            cautions.append(f"critical risk: {detail}")
        elif severity in {"blocking", "warning"}:
            cautions.append(detail)
    return sorted(set(blockers)), sorted(set(cautions))


def production_candidates(adjudication: dict[str, Any], max_candidates: int, offset: int) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(adjudication.get("rows"))
        if isinstance(row, dict) and row.get("recommended_bucket") == "B_RESEARCH"
    ]
    rows.sort(key=lambda row: (row.get("rank") is None, row.get("rank") or 999999, str(row.get("ticker") or "")))
    return rows[offset:offset + max_candidates]


def phase2_candidates(phase2_gate: dict[str, Any], max_candidates: int, offset: int) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(phase2_gate.get("c_to_b_decisions"))
        if isinstance(row, dict) and row.get("status") == "eligible_for_admission"
    ]
    rows.sort(key=lambda row: (row.get("batch_nomination_index") is None, row.get("batch_nomination_index") or 999999, str(row.get("ticker") or "")))
    return rows[offset:offset + max_candidates]


def repair_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in as_list(report.get("rows"))
        if isinstance(row, dict) and row.get("ticker")
    }


def source_rows_for(source: str, requested: list[str] | None, max_candidates: int, offset: int, adjudication: dict[str, Any], phase2_gate: dict[str, Any]) -> list[dict[str, Any]]:
    if requested:
        requested_symbols = [ticker.upper().strip() for ticker in requested if ticker.strip()]
        if source == "production_bench":
            by_ticker = {str(row.get("ticker") or "").upper(): row for row in as_list(adjudication.get("rows")) if isinstance(row, dict)}
        elif source == "phase2_eligible":
            by_ticker = {str(row.get("ticker") or "").upper(): row for row in as_list(phase2_gate.get("c_to_b_decisions")) if isinstance(row, dict)}
        else:
            by_ticker = {}
        return [{"ticker": ticker, **as_dict(by_ticker.get(ticker))} for ticker in requested_symbols[:max_candidates]]
    if source == "production_bench":
        return production_candidates(adjudication, max_candidates, offset)
    if source == "phase2_eligible":
        return phase2_candidates(phase2_gate, max_candidates, offset)
    return []


def source_eligibility(source: str, source_row: dict[str, Any]) -> tuple[bool, str | None]:
    if source == "production_bench":
        bucket = source_row.get("recommended_bucket")
        if bucket == "B_RESEARCH":
            return True, None
        return False, f"not in B_RESEARCH adjudication bucket: {bucket}"
    if source == "phase2_eligible":
        status = source_row.get("status")
        if status == "eligible_for_admission":
            return True, None
        return False, f"not Phase 2 eligible_for_admission: {status}"
    return False, f"unknown source: {source}"


def candidate_from_card(ticker: str, source: str, quote: float | None, quote_source: str | None, quote_time_utc: str | None, source_row: dict[str, Any], repair_row: dict[str, Any]) -> dict[str, Any]:
    card_path = CARD_DIR / f"{ticker}.current.json"
    card = load_dict(card_path)
    band = as_dict(card.get("price_band_stop"))
    technical = as_dict(card.get("technical_posture"))
    recommendation = as_dict(card.get("recommendation_support"))
    universe = as_dict(card.get("universe_metadata"))
    portfolio_fit = as_dict(card.get("portfolio_fit_concentration"))
    valuation = as_dict(card.get("valuation"))
    repair_price = as_dict(repair_row.get("fresh_price_context")).get("current_price")
    repair_quote_source = as_dict(repair_row.get("fresh_price_context")).get("quote_source")
    repair_quote_time = as_dict(repair_row.get("fresh_price_context")).get("quote_time_utc")
    latest_known_price = band.get("latest_known_price") or card.get("latest_known_price")
    effective_price = quote if quote is not None else (repair_price if repair_price is not None else latest_known_price)
    low = band.get("entry_band_low")
    high = band.get("entry_band_high")
    stop = band.get("stop_or_invalidation")
    band_status = current_band_status(effective_price, low, high, stop)

    blockers: list[str] = []
    cautions: list[str] = []
    source_ok, source_blocker = source_eligibility(source, source_row)
    if not source_ok and source_blocker:
        blockers.append(source_blocker)
    if not card:
        blockers.append("ticker card missing")
    if low is None or high is None or stop is None:
        if source == "phase2_eligible":
            cautions.append("written band/stop missing; acceptable for Tier B research-bench label only, not deployment")
        else:
            blockers.append("written band/stop missing")
    if not technical.get("data_date"):
        if source == "phase2_eligible":
            cautions.append("technical data date missing; Phase 2 repair supplies research-only price context")
        else:
            blockers.append("technical data date missing")
    if band_status == "BELOW_STOP":
        blockers.append("current/reference price is below stop")
    if not source_open_usable(card):
        blockers.append("source-open proof not usable")

    if quote is None:
        if repair_price is not None:
            cautions.append("using evidence-repair fresh price context; fresh quote not supplied directly to final packet")
        else:
            cautions.append("using card latest_known_price; fresh quote not supplied")
    if band_status in {"ABOVE_BAND", "BELOW_BAND"}:
        cautions.append(f"not deployable from band discipline: {band_status}")
    if recommendation.get("posture_key") == "blocked_stale":
        cautions.append("card recommendation posture is blocked_stale; acceptable for Tier B research only, not action")
    if universe.get("decision_grade_eligible") is False:
        cautions.append("universe marks decision_grade_eligible false; treat as sector/proxy research bench, not decision queue")
    forward_pe = valuation.get("forward_pe")
    if isinstance(forward_pe, (int, float)) and forward_pe > 30:
        cautions.append(f"forward PE elevated at {forward_pe}")
    risk_blockers, risk_cautions = risk_summaries(card)
    blockers.extend(risk_blockers)
    cautions.extend(risk_cautions)

    decision_status = "eligible_for_auto_tier_b_routing" if not blockers else "blocked_before_auto_routing"
    return {
        "ticker": ticker,
        "name": card.get("name") or card.get("company_name") or universe.get("name") or source_row.get("name"),
        "instrument_type": universe.get("instrument_type") or card.get("instrument_type"),
        "candidate_source": source,
        "source_eligibility": {
            "ok": source_ok,
            "status": source_row.get("status") or source_row.get("recommended_bucket"),
            "reason": source_row.get("reason"),
            "batch_id": source_row.get("batch_id"),
            "batch_nomination_index": source_row.get("batch_nomination_index"),
        },
        "adjudication_rank": source_row.get("rank"),
        "adjudication_score": source_row.get("score"),
        "prior_recommendation": source_row.get("recommendation"),
        "quote": {
            "current_price": quote,
            "effective_price_used": effective_price,
            "source": quote_source if quote is not None else (repair_quote_source or band.get("price_source")),
            "quote_time_utc": quote_time_utc if quote is not None else (repair_quote_time or as_dict(card.get("entry_stop_reference_metadata")).get("source_lineage", {}).get("source_timestamp")),
            "fresh_quote_supplied": quote is not None or repair_price is not None,
            "from_evidence_repair": quote is None and repair_price is not None,
        },
        "written_band": {
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "card_reference_price": latest_known_price,
            "card_band_status": band.get("band_status"),
            "current_or_reference_band_status": band_status,
        },
        "card_context": {
            "legacy_tier": universe.get("tier"),
            "monitoring_role": universe.get("monitoring_role"),
            "portfolio_role": portfolio_fit.get("portfolio_role"),
            "workflow_state": as_dict(universe.get("coverage_reason")).get("workflow_state"),
            "recommendation_posture": recommendation.get("posture"),
            "technical_data_date": technical.get("data_date"),
            "ma_posture": technical.get("ma_posture"),
            "forward_pe": forward_pe,
            "prepared_order_card_present": recommendation.get("prepared_order_card_present"),
        },
        "tier_b_interpretation": {
            "research_bench_only": True,
            "deployment_ready": False,
            "tier_a_candidate": False,
            "owner_approval_required_for_routing": False,
            "separate_trade_or_paper_order_approval_required": True,
        },
        "decision_status": decision_status,
        "blockers": sorted(set(blockers)),
        "cautions": sorted(set(cautions)),
        "source_artifacts": [rel(card_path), rel(ADJUDICATION if source == "production_bench" else PHASE2_GATE), rel(EVIDENCE_REPAIR)] if source == "phase2_eligible" else [rel(card_path), rel(ADJUDICATION)],
        "authority_boundary": {
            "tier_b_label_applied": False,
            "owner_approval_required_for_routing": False,
            "owner_approval_required_for_capital_or_execution": True,
            "paper_or_live_execution_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
        },
    }


def build_report(source: str, candidates: list[str] | None, max_candidates: int, offset: int, quotes: dict[str, float], quote_source: str | None, quote_time_utc: str | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    adjudication = load_dict(ADJUDICATION)
    phase2_gate = load_dict(PHASE2_GATE)
    evidence_repair = load_dict(EVIDENCE_REPAIR)
    repairs = repair_map(evidence_repair)
    selected_source_rows = source_rows_for(source, candidates, max_candidates, offset, adjudication, phase2_gate)
    rows = [
        candidate_from_card(
            str(source_row.get("ticker") or "").upper(),
            source,
            quotes.get(str(source_row.get("ticker") or "").upper()),
            quote_source,
            quote_time_utc,
            as_dict(source_row),
            as_dict(repairs.get(str(source_row.get("ticker") or "").upper())),
        )
        for source_row in selected_source_rows
        if str(source_row.get("ticker") or "").strip()
    ]
    eligible = [row for row in rows if row.get("decision_status") == "eligible_for_auto_tier_b_routing"]
    blocked = [row for row in rows if row.get("decision_status") != "eligible_for_auto_tier_b_routing"]

    if source == "production_bench":
        add_check(checks, "adjudication_packet_present", bool(adjudication), rel(ADJUDICATION))
        add_check(checks, "adjudication_validation_ok", as_dict(adjudication.get("validation")).get("status") == "ok", as_dict(adjudication.get("validation")))
        add_check(checks, "all_candidates_from_b_research_bucket", all(as_dict(row.get("source_eligibility")).get("ok") is True for row in rows), {row["ticker"]: as_dict(row.get("source_eligibility")).get("status") for row in rows})
    if source == "phase2_eligible":
        add_check(checks, "phase2_gate_present", bool(phase2_gate), rel(PHASE2_GATE))
        add_check(checks, "phase2_gate_validation_ok", as_dict(phase2_gate.get("validation")).get("status") == "ok", as_dict(phase2_gate.get("validation")))
        add_check(checks, "all_candidates_phase2_eligible", all(as_dict(row.get("source_eligibility")).get("ok") is True for row in rows), {row["ticker"]: as_dict(row.get("source_eligibility")).get("status") for row in rows})
        add_check(checks, "evidence_repair_present", bool(evidence_repair), rel(EVIDENCE_REPAIR))
        add_check(checks, "evidence_repair_validation_ok", as_dict(evidence_repair.get("validation")).get("status") == "ok", as_dict(evidence_repair.get("validation")))
    add_check(checks, "candidate_count_within_limit", len(rows) <= max_candidates, {"count": len(rows), "max": max_candidates})
    add_check(checks, "at_least_one_candidate_auto_routing_eligible", len(eligible) > 0, [row["ticker"] for row in eligible], "warning")
    add_check(checks, "no_tier_b_label_applied", AUTHORITY_BOUNDARY["tier_b_label_applied"] is False, AUTHORITY_BOUNDARY["tier_b_label_applied"])
    add_check(checks, "tier_b_packet_allows_no_deployment", all(as_dict(row.get("tier_b_interpretation")).get("deployment_ready") is False for row in rows), None)
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    if errors:
        status = "blocked"
    else:
        status = "deprecated_compatibility_packet"
    eligible_tickers = [row["ticker"] for row in eligible]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Tier B Final Promotion Compatibility Packet",
        "purpose": "Retained compatibility/audit packet for historical Tier B promotion inputs; not current routing authority.",
        "shared_header_ref": rel(SHARED_HEADER),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "deprecation_status": DEPRECATION_STATUS,
        "source_artifacts": {
            "production_adjudication": rel(ADJUDICATION),
            "phase2_gate": rel(PHASE2_GATE),
            "tier_b_evidence_repair": rel(EVIDENCE_REPAIR),
            "ticker_cards": rel(CARD_DIR),
            "shared_header": rel(SHARED_HEADER),
        },
        "summary": {
            "candidate_source": source,
            "candidate_limit": max_candidates,
            "candidate_offset": offset,
            "candidate_count": len(rows),
            "eligible_for_historical_tier_b_routing_count": len(eligible),
            "blocked_in_historical_packet_count": len(blocked),
            "eligible_tickers": eligible_tickers,
            "blocked_tickers": [row["ticker"] for row in blocked],
            "auto_routing_action": (
                "deprecated_for_authority; use wf78_auto_tier_router.py SQL-first lane-qualified output instead."
            ),
            "recommended_answer": "do_not_use_as_recommendation_surface",
            "next_safe_action": "Use SQL-first lane-qualified WF78 router and downstream gates; reserve this packet for compatibility review only.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "This packet does not apply Tier B labels.",
            "Tier B means research bench only, not deployment readiness.",
            "This packet does not approve any buy/sell/paper/live order.",
            "This packet does not mutate canon, portfolio, sizing, cash, sleeve, or risk-rule state.",
            "This packet does not infer capital deployment or execution approval from validation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", help="candidate ticker; defaults to the next candidates from --source")
    parser.add_argument("--source", choices=sorted(SOURCES), default="production_bench", help="candidate queue to evaluate")
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    parser.add_argument("--offset", type=int, default=0, help="zero-based offset into the selected source queue when --candidate is omitted")
    parser.add_argument("--quote", action="append", type=parse_quote, help="optional current quote as TICKER=PRICE; otherwise card latest_known_price is used")
    parser.add_argument("--quote-source")
    parser.add_argument("--quote-time-utc")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    if args.max_candidates < 1:
        raise SystemExit("--max-candidates must be >= 1")
    if args.offset < 0:
        raise SystemExit("--offset must be >= 0")
    candidates = args.candidate
    quotes = dict(args.quote or [])
    report = build_report(args.source, candidates, args.max_candidates, args.offset, quotes, args.quote_source, args.quote_time_utc)
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
