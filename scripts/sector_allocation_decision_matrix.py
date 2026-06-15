#!/usr/bin/env python3
"""Generalized report-only sector allocation decision matrix.

Builds a cross-sector/sleeve ranking from existing Veritas artifacts. It is a
review surface only: it may rank, route, and recommend review packets, but it
must not authorize portfolio mutation, owner approval, sizing, paper/live order
execution, brokerage/account actions, or money movement.
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "sector-allocation-decision-matrix.json"
DEFAULT_MD = TMP / "sector-allocation-decision-matrix.md"
SCHEMA_VERSION = 1

AUTHORITY_FALSE_FLAGS = [
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_order_execution_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "probability_or_modeling_authority",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
]

SECTOR_ALIASES = {
    "tech": "Technology / AI",
    "technology": "Technology / AI",
    "financial infrastructure": "Financials",
    "aerospace": "Defense / Aerospace",
    "aerospace & defense": "Defense / Aerospace",
    "defense": "Defense / Aerospace",
    "materials / infrastructure": "Materials / Infrastructure",
    "materials / services": "Materials / Infrastructure",
    "energy infrastructure": "Energy Security",
    "energy": "Energy Security",
    "industrials": "Industrials / AI-Power",
    "infrastructure": "Industrials / Infrastructure",
}

SECTOR_PRIORITY_NAMES = [
    "Industrials / AI-Power",
    "Defense / Aerospace",
    "Technology / AI",
    "Financials",
    "Energy Security",
    "Materials / Infrastructure",
    "Health Care",
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Real Estate",
    "Utilities",
    "International Equity",
    "Duration / Fixed Income",
    "Diversified Quality",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def authority_false_block() -> dict[str, bool]:
    return {key: False for key in AUTHORITY_FALSE_FLAGS}


def normalize_sector(value: Any, ticker: str | None = None) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = "Unknown"
    lower = raw.lower()
    if ticker in {"ITA", "LMT", "RTX", "KTOS"}:
        return "Defense / Aerospace"
    if ticker in {"ETN", "VRT", "PH", "CAT", "PAVE", "XLI"}:
        return "Industrials / AI-Power" if ticker in {"ETN", "VRT"} else "Industrials / Infrastructure"
    if ticker in {"XOM", "CVX", "LNG", "WMB", "XLE"}:
        return "Energy Security"
    if ticker in {"LIN", "VAW", "XLB", "ECL", "VMC"}:
        return "Materials / Infrastructure"
    if ticker in {"NVDA", "MSFT", "GOOG", "AMD", "AMZN", "PLTR", "XLK"}:
        return "Technology / AI"
    if ticker in {"JPM", "GS", "CME", "XLF"}:
        return "Financials"
    return SECTOR_ALIASES.get(lower, raw)


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def records_by_ticker(artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = artifact.get("records") or artifact.get("rows") or artifact.get("packets") or artifact.get("proposals") or []
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                out[str(row["ticker"]).upper()] = row
    return out


def entry_band_status(close: float | None, band_low: float | None, band_high: float | None, stop: float | None, state: str) -> str:
    if close is None:
        return "UNKNOWN"
    if stop is not None and close < stop:
        return "BELOW_STOP"
    if band_low is not None and band_high is not None:
        if band_low <= close <= band_high:
            return "IN_BAND"
        if close > band_high:
            return "ABOVE_BAND_WAIT"
        return "BELOW_BAND_WAIT"
    if "BELOW STOP" in state.upper():
        return "BELOW_STOP"
    return "UNKNOWN"


def candidate_score(row: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    state = str(row.get("state") or "").upper()
    status = row.get("entry_band_status")
    if state == "DEPLOYABLE NOW":
        score += 35; reasons.append("deployable-now board state")
    elif "PROMOTION REVIEW" in state:
        score += 22; reasons.append("promotion-review board state")
    elif "ALMOST" in state:
        score += 14; reasons.append("almost-deployable / wait-for-band")
    elif "WATCH" in state:
        score += 6; reasons.append("watch-lane candidate")
    elif "BENCH" in state or "REPAIR" in state:
        score -= 8; reasons.append("repair/bench state")
    if status == "IN_BAND":
        score += 20; reasons.append("in band")
    elif status == "ABOVE_BAND_WAIT":
        score += 4; reasons.append("above band / no chase")
    elif status == "BELOW_STOP":
        score -= 30; reasons.append("below stop")
    # Fundamental quality proxy; positive growth and margins help, FCF/ROIC if present.
    for key, weight in (("revenue_yoy_pct", 0.20), ("eps_yoy_pct", 0.12), ("net_income_yoy_pct", 0.08), ("operating_margin_pct", 0.15), ("net_margin_pct", 0.12)):
        val = as_float(row.get(key))
        if val is not None:
            score += max(min(val * weight, 8), -8)
    # Penalize obvious speculative/crowding/repair labels but keep as heuristic-only.
    text = " ".join(str(row.get(k) or "") for k in ("portfolio_role", "thesis_status", "trigger_condition"))
    if "speculative" in text.lower():
        score -= 6; reasons.append("speculative sleeve risk")
    if "suspended" in text.lower() or "repair" in text.lower():
        score -= 6; reasons.append("repair/suspended authority context")
    return round(score, 2), reasons[:6]


def classify_growth_value(row: dict[str, Any]) -> str:
    sector = str(row.get("sector") or "")
    ticker = str(row.get("ticker") or "")
    rev = as_float(row.get("revenue_yoy_pct"))
    margin = as_float(row.get("operating_margin_pct"))
    if ticker in {"XOM", "CVX", "WMB", "XLE", "JPM", "GS", "CME", "BRK.B"} or sector in {"Energy Security", "Financials", "Diversified Quality"}:
        return "value/income/macro hedge" if sector == "Energy Security" else "quality/value/cyclical"
    if ticker in {"VRT", "NVDA", "KTOS", "PLTR", "AMD"}:
        return "growth / high volatility"
    if rev is not None and rev >= 15:
        return "quality growth"
    if margin is not None and margin >= 15:
        return "quality compounder"
    return "balanced / monitor"


def build_matrix() -> dict[str, Any]:
    config = load_json(TMP / "portfolio-config.json")
    deployment = load_json(TMP / "deployment-check.json")
    trigger = load_json(TMP / "trigger-sheet.json")
    technical = load_json(TMP / "technical-refresh.json")
    fundamentals = load_json(TMP / "fundamental-metrics-current.json")
    sector_board = load_json(TMP / "sector-expansion-board.json")
    capital = load_json(TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json")
    probability = load_json(TMP / "probability-readiness-report.json")
    trust_gate = load_json(TMP / "advisor-packet-trust-coherence-gate.json")

    dep_by = records_by_ticker(deployment)
    trig_by = records_by_ticker(trigger)
    tech_by = records_by_ticker(technical)
    fund_by = records_by_ticker(fundamentals)
    cap_by = records_by_ticker(capital)
    universe = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}
    bands = config.get("entry_bands") if isinstance(config.get("entry_bands"), dict) else {}

    tickers = sorted(set(universe) | set(dep_by) | set(trig_by) | set(tech_by) | set(fund_by) | set(cap_by))
    candidates: list[dict[str, Any]] = []
    sectors: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "sector": "",
        "candidate_count": 0,
        "best_candidates": [],
        "entry_ready_count": 0,
        "promotion_review_count": 0,
        "below_stop_count": 0,
        "watch_only_count": 0,
        "aggregate_candidate_score": 0.0,
        "growth_value_mix": defaultdict(int),
    })

    for ticker in tickers:
        u = universe.get(ticker) if isinstance(universe.get(ticker), dict) else {}
        dep = dep_by.get(ticker, {})
        trig = trig_by.get(ticker, {})
        tech = tech_by.get(ticker, {})
        fund = fund_by.get(ticker, {})
        cap = cap_by.get(ticker, {})
        band = bands.get(ticker) if isinstance(bands.get(ticker), dict) else {}
        close = as_float(dep.get("close") or trig.get("close") or tech.get("close") or fund.get("close"))
        low = as_float((trig.get("entry_band") or {}).get("low") if isinstance(trig.get("entry_band"), dict) else None) or as_float(band.get("low"))
        high = as_float((trig.get("entry_band") or {}).get("high") if isinstance(trig.get("entry_band"), dict) else None) or as_float(band.get("high"))
        stop = as_float(trig.get("invalidation")) or as_float(band.get("stop"))
        state = str(legacy_state(dep, "action_state") or trig.get("deployment_state") or legacy_state(trig, "action_state") or legacy_state(u, "workflow_state") or "WATCH")
        sector = normalize_sector(u.get("sector") or fund.get("sector"), ticker)
        status = entry_band_status(close, low, high, stop, state)
        row: dict[str, Any] = {
            "ticker": ticker,
            "sector": sector,
            "state": state,
            "close": close,
            "band_low": low,
            "band_high": high,
            "stop": stop,
            "entry_band_status": status,
            "workflow_state": legacy_state(u, "workflow_state"),
            "coverage_lane": u.get("coverage_lane"),
            "portfolio_role": u.get("portfolio_role"),
            "thesis_status": u.get("thesis_status"),
            "trigger_condition": u.get("trigger_condition"),
            "capital_packet_posture": (cap.get("proposed_state") or {}).get("recommendation_posture") if isinstance(cap.get("proposed_state"), dict) else None,
        }
        for key in ("revenue_yoy_pct", "eps_yoy_pct", "net_income_yoy_pct", "operating_margin_pct", "net_margin_pct"):
            if key in fund:
                row[key] = fund.get(key)
        row["growth_value_profile"] = classify_growth_value(row)
        score, reasons = candidate_score(row)
        row["candidate_score"] = score
        row["score_drivers"] = reasons
        row["authority"] = authority_false_block()
        row["next_action"] = next_action_for_candidate(row)
        candidates.append(row)

        bucket = sectors[sector]
        bucket["sector"] = sector
        bucket["candidate_count"] += 1
        bucket["aggregate_candidate_score"] += max(score, -20)
        bucket["growth_value_mix"][row["growth_value_profile"]] += 1
        if state.upper() == "DEPLOYABLE NOW" or (status == "IN_BAND" and state.upper() in {"DEPLOYABLE NOW", "PROMOTION REVIEW"}):
            bucket["entry_ready_count"] += 1
        if "PROMOTION REVIEW" in state.upper():
            bucket["promotion_review_count"] += 1
        if status == "BELOW_STOP":
            bucket["below_stop_count"] += 1
        if "WATCH" in state.upper():
            bucket["watch_only_count"] += 1

    candidates.sort(key=lambda r: (r["candidate_score"], 1 if r["entry_band_status"] == "IN_BAND" else 0), reverse=True)
    for row in candidates:
        sectors[row["sector"]]["best_candidates"].append(row)

    sector_rows: list[dict[str, Any]] = []
    sector_board_summary = sector_board.get("summary") if isinstance(sector_board.get("summary"), dict) else {}
    improving = set(sector_board_summary.get("improving_leadership_sectors") or [])
    underexposed = set(sector_board_summary.get("underexposed_sectors") or [])
    exposure_by_sector = sector_exposure_map(sector_board)
    short_ma_by_sector = sector_short_ma_map(sector_board)
    concentration_warnings = list(sector_board_summary.get("concentration_warnings") or [])
    for sector, bucket in sectors.items():
        best = bucket["best_candidates"][:5]
        score = float(bucket["aggregate_candidate_score"])
        broad_sector = broad_sector_name(sector)
        exposure = exposure_by_sector.get(broad_sector, {})
        sector_timing = short_ma_by_sector.get(broad_sector, {})
        exposure_status = exposure.get("status")
        leadership_improving = sector in improving or broad_sector in improving
        is_underexposed = sector in underexposed or broad_sector in underexposed
        if leadership_improving:
            score += 12
        if is_underexposed:
            score += 8
        if exposure_status == "at_cap":
            score -= 45
        elif exposure_status == "near_cap":
            score -= 18
        if sector in {"Technology / AI", "Industrials / AI-Power"} and any("AI-power correlated sleeve" in str(w) for w in concentration_warnings):
            score -= 18
        if bucket["entry_ready_count"]:
            score += 10 * bucket["entry_ready_count"]
        if bucket["below_stop_count"]:
            score -= 5 * bucket["below_stop_count"]
        priority_note = sector_priority_note(sector, best, score, leadership_improving, is_underexposed, exposure_status)
        sector_rows.append({
            "sector": sector,
            "broad_sector": broad_sector,
            "sector_score": round(score, 2),
            "rank": None,
            "posture": priority_note[0],
            "why": priority_note[1],
            "candidate_count": bucket["candidate_count"],
            "entry_ready_count": bucket["entry_ready_count"],
            "promotion_review_count": bucket["promotion_review_count"],
            "below_stop_count": bucket["below_stop_count"],
            "leadership_improving": leadership_improving,
            "underexposed": is_underexposed,
            "portfolio_exposure": exposure,
            "sector_timing_warning": sector_timing,
            "concentration_warnings": concentration_warnings if sector in {"Technology / AI", "Industrials / AI-Power"} else [],
            "growth_value_mix": dict(bucket["growth_value_mix"]),
            "best_candidates": [compact_candidate(row) for row in best],
            "authority": authority_false_block(),
        })

    sector_rows.sort(key=lambda r: r["sector_score"], reverse=True)
    for idx, row in enumerate(sector_rows, 1):
        row["rank"] = idx

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "question": "Which sectors or sleeves should be prioritized across the active universe, and should we favor growth or value?",
        "source_artifacts": {
            "portfolio_config": "tmp/portfolio-config.json",
            "deployment_check": "tmp/deployment-check.json",
            "trigger_sheet": "tmp/trigger-sheet.json",
            "technical_refresh": "tmp/technical-refresh.json",
            "fundamental_metrics": "tmp/fundamental-metrics-current.json",
            "sector_expansion_board": "tmp/sector-expansion-board.json",
            "capital_recommendations": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
            "probability_readiness": "tmp/probability-readiness-report.json",
            "advisor_trust_gate": "tmp/advisor-packet-trust-coherence-gate.json",
        },
        "trust_state": {
            "sector_expansion_status": sector_board.get("status"),
            "sector_expansion_consumer_posture": sector_board.get("consumer_posture"),
            "probability_readiness": probability.get("verdict") or probability.get("status"),
            "advisor_trust_gate_status": trust_gate.get("status"),
            "advisor_presentation_posture": trust_gate.get("presentation_posture"),
            "downgrade": "Heuristic review-only ranking; no probability/win-rate language; degraded advisor artifacts require red trust banner when displayed.",
        },
        "authority": authority_false_block() | {
            "review_packet_generation_allowed": True,
            "report_only": True,
        },
        "sector_rankings": sector_rows,
        "top_candidate_watch_order": [compact_candidate(row) for row in candidates[:20]],
        "growth_vs_value_verdict": growth_value_verdict(sector_rows),
        "limits": [
            "Report-only sector allocation support; not a canon, portfolio, sizing, cash, risk-rule, approval, paper/live order, brokerage, account, or trade authority surface.",
            "Scores are heuristic routing aids only; WF55 probability readiness is not ready, so no win-rate/probability/expected-return claims are allowed.",
            "Fresh quote, band, stop, source-freshness, concentration, and WF67 guard checks are still required before any paper package can execute.",
            "Sector 5DMA/20DMA timing warnings are thin caution flags only; they do not override written entry bands, stops, thesis, source freshness, concentration limits, or owner approval gates.",
        ],
    }


def compact_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "sector": row.get("sector"),
        "candidate_score": row.get("candidate_score"),
        "state": row.get("state"),
        "close": row.get("close"),
        "band": f"{row.get('band_low')}-{row.get('band_high')}" if row.get("band_low") is not None and row.get("band_high") is not None else None,
        "stop": row.get("stop"),
        "entry_band_status": row.get("entry_band_status"),
        "growth_value_profile": row.get("growth_value_profile"),
        "next_action": row.get("next_action"),
    }


def next_action_for_candidate(row: dict[str, Any]) -> str:
    state = str(row.get("state") or "").upper()
    status = row.get("entry_band_status")
    ticker = row.get("ticker")
    if status == "BELOW_STOP":
        return "repair/reclaim watch only; no promotion or paper package"
    if state == "DEPLOYABLE NOW" and status == "IN_BAND":
        return "owner decision / paper-prep candidate after fresh quote and WF67 guards"
    if "PROMOTION REVIEW" in state and status == "IN_BAND":
        return "promotion-review packet candidate; no execution entitlement"
    if status == "ABOVE_BAND_WAIT":
        return "wait for band or explicit band-review; no chase"
    if ticker in {"ITA", "GE", "PH", "VRT", "LIN", "WMB"}:
        return "deeper review packet if fresh evidence and entry discipline clear"
    return "monitor"


def broad_sector_name(sector: str) -> str:
    if sector == "Technology / AI":
        return "Technology"
    if sector.startswith("Industrials"):
        return "Industrials"
    if sector == "Defense / Aerospace":
        return "Industrials"
    if sector == "Energy Security":
        return "Energy"
    if sector == "Materials / Infrastructure":
        return "Materials"
    if sector == "Healthcare":
        return "Health Care"
    return sector


def sector_exposure_map(sector_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = sector_board.get("sectors") if isinstance(sector_board.get("sectors"), list) else []
    for row in rows:
        if isinstance(row, dict) and row.get("sector"):
            exposure = row.get("portfolio_exposure") if isinstance(row.get("portfolio_exposure"), dict) else {}
            out[str(row["sector"])] = exposure
    return out


def sector_short_ma_map(sector_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = sector_board.get("sectors") if isinstance(sector_board.get("sectors"), list) else []
    for row in rows:
        if not isinstance(row, dict) or not row.get("sector"):
            continue
        short_ma = row.get("short_term_moving_averages")
        if isinstance(short_ma, dict):
            out[str(row["sector"])] = {
                "ticker": row.get("ticker"),
                "close": row.get("close"),
                "sma_5": short_ma.get("sma_5"),
                "sma_20": short_ma.get("sma_20"),
                "price_vs_5dma_pct": short_ma.get("price_vs_5dma_pct"),
                "price_vs_20dma_pct": short_ma.get("price_vs_20dma_pct"),
                "sma_5_vs_20_pct": short_ma.get("sma_5_vs_20_pct"),
                "signal": short_ma.get("signal"),
                "warning": short_ma.get("warning"),
            }
    return out


def sector_priority_note(sector: str, best: list[dict[str, Any]], score: float, improving: bool, underexposed: bool, exposure_status: Any = None) -> tuple[str, str]:
    names = ", ".join(str(row.get("ticker")) for row in best[:3]) or "no clear candidates"
    if exposure_status == "at_cap":
        posture = "cap_limited_monitor"
    elif exposure_status == "near_cap" and score < 80:
        posture = "cap_limited_review"
    elif score >= 80:
        posture = "prioritize"
    elif score >= 45:
        posture = "review_next"
    elif score >= 20:
        posture = "monitor_selectively"
    else:
        posture = "repair_or_watch"
    flags = []
    if improving:
        flags.append("improving leadership")
    if underexposed:
        flags.append("underexposed")
    if exposure_status:
        flags.append(f"portfolio exposure {exposure_status}")
    return posture, f"Best candidates: {names}." + (f" Flags: {', '.join(flags)}." if flags else "")


def growth_value_verdict(rows: list[dict[str, Any]]) -> str:
    top = [row.get("sector") for row in rows[:4]]
    return (
        "Favor quality growth and capex/backlog-linked compounders at disciplined entries, "
        "not a broad value rotation. Value/income sectors remain useful hedges only when entry/repair gates clear. "
        f"Current top sector/sleeve ranks: {', '.join(str(x) for x in top)}."
    )


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Sector Allocation Decision Matrix",
        "",
        f"Generated: {matrix.get('generated_at_utc')}",
        "",
        "## Verdict",
        "",
        str(matrix.get("growth_vs_value_verdict")),
        "",
        "## Sector rankings",
        "",
        "| Rank | Sector | Posture | Score | Best candidates | Notes |",
        "|---:|---|---|---:|---|---|",
    ]
    for row in matrix.get("sector_rankings") or []:
        best = ", ".join(str(c.get("ticker")) for c in row.get("best_candidates", [])[:5])
        lines.append(f"| {row.get('rank')} | {row.get('sector')} | {row.get('posture')} | {row.get('sector_score')} | {best} | {row.get('why')} |")
    lines += [
        "",
        "## Top candidate watch order",
        "",
        "| Rank | Ticker | Sector | State | Band status | Growth/value | Next action |",
        "|---:|---|---|---|---|---|---|",
    ]
    for idx, row in enumerate(matrix.get("top_candidate_watch_order") or [], 1):
        lines.append(f"| {idx} | {row.get('ticker')} | {row.get('sector')} | {row.get('state')} | {row.get('entry_band_status')} | {row.get('growth_value_profile')} | {row.get('next_action')} |")
    lines += [
        "",
        "## Trust state",
        "",
        f"- Sector board: `{matrix.get('trust_state', {}).get('sector_expansion_status')}` / `{matrix.get('trust_state', {}).get('sector_expansion_consumer_posture')}`",
        f"- Probability readiness: `{matrix.get('trust_state', {}).get('probability_readiness')}`",
        f"- Advisor trust gate: `{matrix.get('trust_state', {}).get('advisor_trust_gate_status')}` / `{matrix.get('trust_state', {}).get('advisor_presentation_posture')}`",
        "",
        "## Authority boundary",
        "",
        "Report-only. No portfolio/canon mutation, owner approval, sizing/cash/risk-rule change, paper/live order, brokerage/account action, or trade authority.",
        "",
    ]
    return "\n".join(lines)


def validate_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if matrix.get("status") != "ok":
        findings.append({"severity": "critical", "issue": "matrix status must be ok"})
    authority = matrix.get("authority") or {}
    for key in AUTHORITY_FALSE_FLAGS:
        if authority.get(key) is not False:
            findings.append({"severity": "critical", "field": f"authority.{key}", "issue": "must remain false"})
    if authority.get("report_only") is not True:
        findings.append({"severity": "critical", "field": "authority.report_only", "issue": "must be true"})
    sectors = matrix.get("sector_rankings")
    if not isinstance(sectors, list) or len(sectors) < 6:
        findings.append({"severity": "critical", "field": "sector_rankings", "issue": "must contain broad cross-sector rankings"})
    else:
        ranks = [row.get("rank") for row in sectors if isinstance(row, dict)]
        if ranks != list(range(1, len(ranks) + 1)):
            findings.append({"severity": "critical", "field": "sector_rankings.rank", "issue": "ranks must be contiguous"})
        for row in sectors:
            if not isinstance(row, dict):
                continue
            row_auth = row.get("authority") or {}
            for key in AUTHORITY_FALSE_FLAGS:
                if row_auth.get(key) is not False:
                    findings.append({"severity": "critical", "sector": row.get("sector"), "field": f"authority.{key}", "issue": "sector authority must remain false"})
            timing = row.get("sector_timing_warning")
            if timing and not isinstance(timing, dict):
                findings.append({"severity": "critical", "sector": row.get("sector"), "field": "sector_timing_warning", "issue": "must be an object when present"})
            if isinstance(timing, dict) and timing and "signal" not in timing:
                findings.append({"severity": "warning", "sector": row.get("sector"), "field": "sector_timing_warning.signal", "issue": "missing thin 5DMA/20DMA timing signal"})
    if matrix.get("trust_state", {}).get("probability_readiness") not in {"NOT_READY", "warning", "blocked", None}:
        findings.append({"severity": "warning", "field": "trust_state.probability_readiness", "issue": "unexpected probability readiness value; verify no probability language"})
    forbidden = ["win probability", "expected return", "auto-approved", "execute order", "place trade"]
    text = json.dumps(matrix, ensure_ascii=False).lower()
    for phrase in forbidden:
        if phrase in text:
            findings.append({"severity": "critical", "issue": "forbidden language in matrix", "phrase": phrase})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build generalized report-only sector allocation decision matrix.")
    parser.add_argument("--output", default=str(DEFAULT_JSON))
    parser.add_argument("--md-output", default=str(DEFAULT_MD))
    parser.add_argument("--validate", action="store_true", help="Validate an existing or generated matrix without writing unless --write is also supplied")
    parser.add_argument("--write", action="store_true", help="Write matrix artifacts")
    args = parser.parse_args()

    out = Path(args.output)
    md_out = Path(args.md_output)
    matrix = build_matrix()
    findings = validate_matrix(matrix)
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    matrix["validation"] = {"status": "ok" if critical == 0 else "critical", "critical": critical, "warning": warning, "findings": findings}
    if args.write:
        atomic_write_json(out, matrix)
        atomic_write_text(md_out, render_markdown(matrix))
    print(json.dumps({"status": matrix["validation"]["status"], "sectors": len(matrix.get("sector_rankings") or []), "critical": critical, "warning": warning, "output": str(out.relative_to(ROOT)) if out.is_absolute() else str(out)}, indent=2))
    return 0 if critical == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
