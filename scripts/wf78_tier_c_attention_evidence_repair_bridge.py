#!/usr/bin/env python3
"""Bridge Tier C attention candidates into focused evidence repair.

This is a review-only WF78 routing artifact. It consumes the fresh Tier C
attention trigger, improving-sector breadth surface, Tier C monitor-grade band
surface, ticker cards, and the Tier C-to-B evidence gate. It does not mutate
cards, canon, portfolio, SQL canon, or any brokerage/execution surface.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
ATTENTION = TMP / "wf78-tier-c-attention-trigger.json"
BREADTH = TMP / "breadth-state.json"
BAND_STATUS = TMP / "tier-c-band-status.json"
C_TO_B = TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.json"
OFFICIAL_REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
OUT = TMP / "wf78-tier-c-attention-evidence-repair-bridge.json"
SCHEMA = "veritas.wf78_tier_c_attention_evidence_repair_bridge.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "tier_c_attention_repair_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
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

IMPROVING_SECTOR_FALLBACK = {
    "Consumer Staples",
    "Financials",
    "Health Care",
    "Industrials",
    "Real Estate",
    "Technology",
    "Utilities",
}

SECTOR_ALIASES = {
    "consumer staples": "Consumer Staples",
    "financials": "Financials",
    "finance": "Financials",
    "health care": "Health Care",
    "healthcare": "Health Care",
    "industrials": "Industrials",
    "industrial": "Industrials",
    "real estate": "Real Estate",
    "information technology": "Technology",
    "technology": "Technology",
    "tech": "Technology",
    "utilities": "Utilities",
    "utility": "Utilities",
    "communication services": "Communication Services",
    "consumer discretionary": "Consumer Discretionary",
    "energy": "Energy",
    "materials": "Materials",
}

PASSABLE_PROMOTION_BANDS = {"IN_BAND", "NEAR_BAND", "BELOW_BAND", "ABOVE_BAND", "ABOVE_BAND_WAIT"}
HIGH_RISK_BANDS = {"BELOW_STOP", "RECLAIM_ONLY"}


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


def normalise_sector(value: Any) -> str:
    raw = str(value or "").strip()
    key = raw.lower()
    if key in SECTOR_ALIASES:
        return SECTOR_ALIASES[key]
    for needle, sector in SECTOR_ALIASES.items():
        if needle in key:
            return sector
    return raw


def improving_sectors(packet: dict[str, Any]) -> set[str]:
    sectors = as_list(as_dict(as_dict(packet.get("data")).get("sector_participation")).get("sectors"))
    selected = {
        normalise_sector(row.get("label"))
        for row in sectors
        if isinstance(row, dict) and row.get("above_50dma") is True and normalise_sector(row.get("label"))
    }
    return selected or set(IMPROVING_SECTOR_FALLBACK)


def attention_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in as_list(packet.get("attention_rows") or packet.get("rows"))
        if isinstance(row, dict)
        and row.get("attention_triggered") is True
        and ticker(row.get("ticker"))
        and row.get("attention_state") in {"C-CANDIDATE", "C-CANDIDATE-REPAIR"}
    ]
    rows.sort(key=lambda row: (-int(row.get("attention_score") or 0), -int(row.get("momentum_score") or 0), ticker(row.get("ticker"))))
    return rows


def rows_by_ticker(packet: dict[str, Any], key: str = "rows") -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get(key))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def official_sources(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for symbol, raw in as_dict(packet.get("tickers")).items():
        if isinstance(raw, dict) and ticker(symbol):
            url = str(raw.get("url") or raw.get("official_earnings_source_url") or raw.get("source_url") or "").strip()
            label = str(raw.get("label") or raw.get("source_label") or raw.get("source_section") or "Official source").strip()
            if url:
                sources[ticker(symbol)] = {
                    "url": url,
                    "label": label,
                    "period_label": raw.get("period_label"),
                    "source_section": raw.get("source_section"),
                }
    return sources


def available_dict(card: dict[str, Any], key: str) -> dict[str, Any]:
    value = as_dict(card.get(key))
    return value if value.get("status") in {"available", "ok", None} or value else {}


def fundamental_ok(card: dict[str, Any]) -> bool:
    fundamentals = available_dict(card, "official_fundamentals")
    metrics = available_dict(card, "key_financial_metrics")
    return bool(
        fundamentals.get("period_end")
        or metrics.get("status") == "available"
        or as_dict(metrics.get("growth")).get("revenue_yoy_pct") is not None
    )


def earnings_ok(card: dict[str, Any]) -> bool:
    earnings = as_dict(card.get("latest_earnings_performance"))
    return earnings.get("status") == "available" and bool(earnings.get("period_end"))


def portfolio_fit_ok(card: dict[str, Any]) -> bool:
    fit = as_dict(card.get("portfolio_fit_concentration"))
    return bool(fit.get("portfolio_role") or fit.get("coverage_lane") or fit.get("sector"))


def band_ok(band: dict[str, Any]) -> bool:
    status = str(band.get("band_status") or "").strip()
    return (
        str(band.get("technical_input_status") or "").lower() == "ok"
        and status in PASSABLE_PROMOTION_BANDS
        and band.get("latest_price") is not None
        and band.get("reference_band_low") is not None
        and band.get("reference_band_high") is not None
        and band.get("coarse_reference_stop") is not None
    )


def technical_ok(band: dict[str, Any], card: dict[str, Any]) -> bool:
    posture = as_dict(card.get("technical_posture"))
    return str(band.get("technical_input_status") or "").lower() == "ok" and bool(
        band.get("trend_stack") or posture.get("band_status") or band.get("band_status")
    )


def official_earnings_manual_gap(card: dict[str, Any]) -> bool:
    earnings = as_dict(card.get("latest_earnings_performance"))
    adjusted = as_dict(earnings.get("official_adjusted_eps"))
    return adjusted.get("manual_capture_required") is True or adjusted.get("status") == "missing_manual_required"


def repair_family_commands(families: list[str], *, include_source_capture: bool) -> list[str]:
    commands: list[str] = []
    if "official_source" in families or include_source_capture:
        commands.extend([
            "python scripts\\wf78_source_capture_requirements_queue.py --write --validate",
            "python scripts\\wf78_official_source_discovery_runner.py --write --validate",
            "python scripts\\wf78_official_registry_proposal.py --write --validate",
            "python scripts\\wf78_official_registry_apply_preview.py --write --write-proposed --validate",
        ])
    if "technical" in families or "band_stop" in families:
        commands.append("python scripts\\tier_c_band_status_refresh.py --no-skip-provider-refresh --write --validate")
    if any(family in families for family in ("fundamentals", "earnings", "portfolio_fit")):
        commands.append("python scripts\\finance_ticker_card_refresh_gate.py --write --validate --skip-provider-refresh --full-answer-mode changed")
    commands.append("python scripts\\wf78_tier_c_to_b_auto_promotion_pipeline.py --from-attention --max-candidates 25 --write --validate")
    return list(dict.fromkeys(commands))


def priority_score(row: dict[str, Any], *, in_improving_sector: bool, gap_count: int, band_status: str) -> int:
    score = int(row.get("attention_score") or 0)
    score += 20 if in_improving_sector else -30
    score += {
        "IN_BAND": 18,
        "NEAR_BAND": 15,
        "BELOW_BAND": 8,
        "ABOVE_BAND": 3,
        "ABOVE_BAND_WAIT": 1,
        "RECLAIM_ONLY": -20,
        "BELOW_STOP": -35,
    }.get(band_status, -10)
    score -= gap_count * 8
    return score


def build_row(
    attention_row: dict[str, Any],
    *,
    improving: set[str],
    band_by_ticker: dict[str, dict[str, Any]],
    c_to_b_by_ticker: dict[str, dict[str, Any]],
    source_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    symbol = ticker(attention_row.get("ticker"))
    card = load_dict(CARD_DIR / f"{symbol}.current.json")
    band = band_by_ticker.get(symbol, {})
    c_to_b = c_to_b_by_ticker.get(symbol, {})
    sector = normalise_sector(attention_row.get("sector") or as_dict(card.get("portfolio_fit_concentration")).get("sector"))
    in_improving_sector = sector in improving
    source = source_by_ticker.get(symbol) or as_dict(c_to_b.get("official_source"))
    band_status = str(band.get("band_status") or as_dict(c_to_b.get("technical_band_context")).get("band_status") or "").strip()

    evidence = {
        "official_source": bool(source.get("url")),
        "fundamentals": fundamental_ok(card),
        "earnings": earnings_ok(card),
        "technical": technical_ok(band, card),
        "band_stop": band_ok(band),
        "portfolio_fit": portfolio_fit_ok(card),
    }
    gaps = [name for name, ok in evidence.items() if not ok]
    if official_earnings_manual_gap(card) and "earnings" not in gaps:
        gaps.append("official_earnings_manual_capture")

    blockers = list(dict.fromkeys(str(item) for item in as_list(attention_row.get("blockers")) + as_list(c_to_b.get("failed_evidence_families")) if str(item)))
    if not in_improving_sector:
        blockers.append("outside_current_improving_sector_filter")
    if band_status in HIGH_RISK_BANDS:
        blockers.append(f"band_status_{band_status.lower()}")
    if gaps:
        blockers.append("evidence_repair_required")

    readiness = "blocked_pending_repair"
    if in_improving_sector and not gaps and band_status not in HIGH_RISK_BANDS and c_to_b.get("status") == "eligible_for_tier_b_research_bench":
        readiness = "promotion_review_ready"
    elif in_improving_sector:
        readiness = "repair_first"
    else:
        readiness = "sector_filtered_monitor"

    repair_families = [
        family for family in ["official_source", "fundamentals", "earnings", "technical", "band_stop", "portfolio_fit"]
        if family in gaps or (family == "official_source" and any("source" in blocker for blocker in blockers))
    ]

    score = priority_score(attention_row, in_improving_sector=in_improving_sector, gap_count=len(gaps), band_status=band_status)
    return {
        "ticker": symbol,
        "name": attention_row.get("name"),
        "sector": attention_row.get("sector"),
        "normalised_sector": sector,
        "in_improving_sector_filter": in_improving_sector,
        "attention_state": attention_row.get("attention_state"),
        "attention_score": attention_row.get("attention_score"),
        "momentum_score": attention_row.get("momentum_score"),
        "fundamental_score": attention_row.get("fundamental_score"),
        "repair_priority_score": score,
        "readiness": readiness,
        "evidence_status": evidence,
        "evidence_gaps": gaps,
        "repair_families": repair_families,
        "promotion_blockers": sorted(set(blockers)),
        "official_source": source,
        "band_context": {
            "data_date": band.get("data_date"),
            "latest_price": band.get("latest_price"),
            "band_status": band_status,
            "reference_band_low": band.get("reference_band_low"),
            "reference_band_high": band.get("reference_band_high"),
            "coarse_reference_stop": band.get("coarse_reference_stop"),
            "trend_stack": band.get("trend_stack"),
            "monitor_grade": band.get("monitor_grade"),
            "decision_grade": band.get("decision_grade"),
        },
        "c_to_b_gate_status": c_to_b.get("status"),
        "c_to_b_failed_evidence_families": c_to_b.get("failed_evidence_families", []),
        "next_repair_commands": repair_family_commands(repair_families, include_source_capture=bool(any("source" in blocker for blocker in blockers))),
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "source_artifacts": [
            rel(ATTENTION),
            rel(BAND_STATUS),
            rel(C_TO_B),
            rel(CARD_DIR / f"{symbol}.current.json"),
            rel(OFFICIAL_REGISTRY),
        ],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    attention = load_dict(ATTENTION)
    breadth = load_dict(BREADTH)
    band_packet = load_dict(BAND_STATUS)
    c_to_b_packet = load_dict(C_TO_B)
    registry = load_dict(OFFICIAL_REGISTRY)

    improving = improving_sectors(breadth)
    candidates = attention_rows(attention)
    band_by_ticker = rows_by_ticker(band_packet)
    c_to_b_by_ticker = rows_by_ticker(c_to_b_packet)
    source_by_ticker = official_sources(registry)

    rows = [
        build_row(row, improving=improving, band_by_ticker=band_by_ticker, c_to_b_by_ticker=c_to_b_by_ticker, source_by_ticker=source_by_ticker)
        for row in candidates
    ]
    rows.sort(key=lambda row: (-int(row.get("in_improving_sector_filter") is True), -int(row.get("repair_priority_score") or 0), str(row.get("ticker"))))
    if args.limit and args.limit > 0:
        rows = rows[:args.limit]

    selected = [row for row in rows if row.get("in_improving_sector_filter")]
    excluded = [row for row in rows if not row.get("in_improving_sector_filter")]
    gap_counts: Counter[str] = Counter()
    band_counts: Counter[str] = Counter()
    readiness_counts: Counter[str] = Counter()
    sector_counts: Counter[str] = Counter()
    for row in rows:
        gap_counts.update(str(gap) for gap in row.get("evidence_gaps", []))
        band_counts[str(as_dict(row.get("band_context")).get("band_status") or "unknown")] += 1
        readiness_counts[str(row.get("readiness"))] += 1
        sector_counts[str(row.get("normalised_sector") or "unknown")] += 1

    ready = [row["ticker"] for row in selected if row.get("readiness") == "promotion_review_ready"]
    repair_first = [row["ticker"] for row in selected if row.get("readiness") == "repair_first"]
    checks = [
        {"name": "attention_artifact_present", "ok": bool(attention), "severity": "critical", "detail": rel(ATTENTION)},
        {"name": "breadth_artifact_present", "ok": bool(breadth), "severity": "critical", "detail": rel(BREADTH)},
        {"name": "tier_c_band_status_present", "ok": bool(band_packet), "severity": "critical", "detail": rel(BAND_STATUS)},
        {"name": "all_attention_candidates_have_rows", "ok": len(rows) == len(candidates) or bool(args.limit), "severity": "critical", "detail": {"rows": len(rows), "candidates": len(candidates), "limit": args.limit}},
        {"name": "no_capital_deployment_approved", "ok": all(row.get("capital_deployment_approved") is False for row in rows), "severity": "critical", "detail": None},
        {"name": "no_trade_or_execution_approved", "ok": all(row.get("trade_or_execution_approved") is False for row in rows), "severity": "critical", "detail": None},
        {"name": "no_paper_or_live_execution_allowed", "ok": all(row.get("paper_or_live_execution_allowed") is False for row in rows), "severity": "critical", "detail": None},
    ]
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    status = "ok" if not errors else "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78 - Tier C Attention Evidence Repair Bridge",
        "purpose": "Route the 25 Tier C attention names through improving-sector and evidence-depth repair before any promotion review.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "tier_c_attention_trigger": rel(ATTENTION),
            "breadth_state": rel(BREADTH),
            "tier_c_band_status": rel(BAND_STATUS),
            "tier_c_to_b_auto_promotion_pipeline": rel(C_TO_B),
            "official_source_registry": rel(OFFICIAL_REGISTRY),
            "ticker_cards": rel(CARD_DIR),
        },
        "summary": {
            "attention_candidate_count": len(candidates),
            "row_count": len(rows),
            "improving_sector_filter": sorted(improving),
            "improving_sector_candidate_count": len(selected),
            "improving_sector_candidate_tickers": [row["ticker"] for row in selected],
            "excluded_candidate_count": len(excluded),
            "excluded_candidate_tickers": [row["ticker"] for row in excluded],
            "sector_counts": dict(sorted(sector_counts.items())),
            "readiness_counts": dict(sorted(readiness_counts.items())),
            "promotion_review_ready_count": len(ready),
            "promotion_review_ready_tickers": ready,
            "repair_first_count": len(repair_first),
            "repair_first_tickers": repair_first,
            "gap_counts": dict(sorted(gap_counts.items())),
            "band_status_counts": dict(sorted(band_counts.items())),
            "tier_c_band_status_summary": as_dict(band_packet.get("summary")),
            "top_repair_watchlist": [
                {
                    "ticker": row["ticker"],
                    "sector": row["normalised_sector"],
                    "repair_priority_score": row["repair_priority_score"],
                    "band_status": as_dict(row.get("band_context")).get("band_status"),
                    "evidence_gaps": row.get("evidence_gaps"),
                    "readiness": row.get("readiness"),
                }
                for row in selected[:10]
            ],
            "next_safe_action": "Repair selected evidence gaps, rerun the 25-name C-to-B gate, and promote only rows that pass evidence; no capital or execution approval is created.",
        },
        "rows": rows,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This bridge does not mutate universe, canon, portfolio, ticker cards, SQL canon, cash, sizing, brokerage, paper, or live-account state.",
            "Promotion review requires evidence clearance; price momentum alone is not enough.",
            "Tier C band context remains monitor-grade until a name clears promotion and decision-grade repair.",
            "No trade, order, paper/live execution, brokerage/account action, or money movement authority is created.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--limit", type=int, default=0, help="Optional max rows for debugging; 0 means all attention candidates.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
