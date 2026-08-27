#!/usr/bin/env python3
"""Build a review-only Chief Intelligence promotion gate.

The gate ranks candidates against each other before any paper-order card or
promotion proposal is treated as decision-ready. It is proof/routing only: it
does not mutate portfolio/canon notes, infer owner approval, or authorize paper
or live execution.
"""
from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT = TMP / "chief-intelligence-promotion-gate.json"
DEFAULT_VALIDATION_OUTPUT = TMP / "chief-intelligence-promotion-gate-validation.json"
DEFAULT_PORTFOLIO_CONFIG = TMP / "portfolio-config.json"
DEFAULT_BAND_PROPOSALS = TMP / "band-proposals.json"
SCHEMA_VERSION = "chief_intelligence_promotion_gate.v1"

AUTHORITY = {
    "review_only": True,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "paper_order_generation_allowed": False,
    "paper_order_execution_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "probability_or_modeling_authority": False,
    "model_ranked_deployment_allowed": False,
    "capital_action_allowed": False,
}

FALSE_AUTHORITY_KEYS = [key for key, value in AUTHORITY.items() if value is False]

AI_POWER_TICKERS = {"AMD", "AMZN", "ETN", "GOOG", "MSFT", "NVDA", "PLTR", "SMCI", "VRT"}
MONDAY_PACKET_TICKERS = {"XLB", "ETN", "VRT", "LIN", "NVDA"}
MATERIALS_TICKERS = {"XLB", "LIN", "VMC", "ECL", "VAW"}
ENERGY_TICKERS = {"XLE", "XOM", "CVX", "LNG", "WMB"}
FINANCIAL_TICKERS = {"XLF", "JPM", "GS", "CME"}
HARD_OPPORTUNITY_BLOCKER_TOKENS = {
    "above band",
    "above_band",
    "below stop",
    "below_stop",
    "blocked_missing",
    "do not touch",
    "do_not_touch",
    "evidence missing",
    "evidence repair",
    "invalidat",
    "missing source",
    "missing_source",
    "no chase",
    "no_chase",
    "not fresh",
    "repair mode",
    "source open missing",
    "source-open missing",
    "stale",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def artifact_status(path: Path, payload: dict[str, Any], *, max_age_hours: float | None = 72) -> dict[str, Any]:
    generated = payload.get("generated_at_utc") or payload.get("generated_at")
    generated_dt = parse_dt(generated)
    age_hours = None
    fresh_enough = path.exists()
    if generated_dt:
        age_hours = round((datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600, 2)
        if max_age_hours is not None:
            fresh_enough = age_hours <= max_age_hours
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") or payload.get("verdict") or payload.get("consumer_posture"),
        "generated_at_utc": generated,
        "age_hours": age_hours,
        "fresh_enough": bool(fresh_enough),
    }


def records_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("records") or payload.get("rows") or payload.get("tickers") or []
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                out[str(row["ticker"]).upper()] = row
    return out


def deployment_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    groups = payload.get("groups")
    if isinstance(groups, dict):
        for group_name, rows in groups.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict) and row.get("ticker"):
                    item = dict(row)
                    item.setdefault("surface_state", group_name)
                    out[str(row["ticker"]).upper()] = item
    return out


def portfolio_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("tracked_universe") if isinstance(payload.get("tracked_universe"), dict) else {}
    return {str(ticker).upper(): row for ticker, row in rows.items() if isinstance(row, dict)}


def entry_bands(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("entry_bands") if isinstance(payload.get("entry_bands"), dict) else {}
    return {str(ticker).upper(): row for ticker, row in rows.items() if isinstance(row, dict)}


def infer_status_from_levels(price: Any, low: Any, high: Any, stop: Any, fallback: Any = None) -> Any:
    try:
        price_f = float(price)
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return fallback
    try:
        stop_f = float(stop)
    except (TypeError, ValueError):
        stop_f = None
    if stop_f is not None and price_f < stop_f:
        return "BELOW_STOP"
    if price_f < low_f:
        return "BELOW_BAND_WAIT"
    if price_f > high_f:
        return "ABOVE_BAND_WAIT"
    return "IN_BAND"


def entry_bands_from_band_proposals(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bands: dict[str, dict[str, Any]] = {}
    for row in payload.get("proposals") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        use_suggested = row.get("canonical_apply_eligible") is True
        low = row.get("suggested_band_low") if use_suggested else row.get("current_band_low")
        high = row.get("suggested_band_high") if use_suggested else row.get("current_band_high")
        stop = row.get("suggested_stop") if use_suggested else row.get("current_stop")
        if low is None or high is None:
            continue
        status = row.get("band_status")
        if not use_suggested:
            status = infer_status_from_levels(row.get("close"), low, high, stop, fallback=status)
        bands[ticker] = {
            "low": low,
            "high": high,
            "stop": stop,
            "label": "sql-first current reference band" if use_suggested else "legacy current band proposal",
            "band_last_set": payload.get("generated_at_utc"),
            "source_priority": "sql_first_band_proposal" if use_suggested else "band_proposal_current_legacy",
            "source_artifact": rel(DEFAULT_BAND_PROPOSALS),
            "source_generated_at_utc": payload.get("generated_at_utc"),
            "canonical_apply_eligible": bool(row.get("canonical_apply_eligible")),
            "needs_review": bool(row.get("needs_review")),
            "band_status": status,
            "supersedes_portfolio_config_band": use_suggested,
            "legacy_current_band": {
                "low": row.get("current_band_low"),
                "high": row.get("current_band_high"),
                "stop": row.get("current_stop"),
            },
            "reasons": row.get("reasons") or [],
        }
    return bands


def sector_context(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    improving = set(summary.get("improving_leadership_sectors") or [])
    underexposed = set(summary.get("underexposed_sectors") or [])
    out: dict[str, dict[str, Any]] = {}
    for sector in payload.get("sectors") or []:
        if not isinstance(sector, dict):
            continue
        sector_name = sector.get("sector")
        tickers = [sector.get("ticker")]
        for candidate in sector.get("tracked_universe_candidates") or []:
            if isinstance(candidate, dict):
                tickers.append(candidate.get("ticker"))
        for ticker in tickers:
            ticker_text = str(ticker or "").upper().strip()
            if not ticker_text:
                continue
            out.setdefault(ticker_text, {})
            out[ticker_text].update({
                "sector": sector_name,
                "sector_etf": sector.get("ticker"),
                "leadership_status": sector.get("leadership_status"),
                "sector_return_5d_pct": (sector.get("sector_returns_pct") or {}).get("5d"),
                "sector_return_20d_pct": (sector.get("sector_returns_pct") or {}).get("20d"),
                "relative_strength_vs_spy_5d": (sector.get("relative_strength_vs_spy") or {}).get("5d"),
                "improving_leadership": sector_name in improving,
                "underexposed": sector_name in underexposed or bool(sector.get("underexposed")),
            })
    return out


def opportunity_context(payload: dict[str, Any]) -> dict[str, Any]:
    review = payload.get("opportunity_review") if isinstance(payload.get("opportunity_review"), dict) else {}
    digest = payload.get("response_recommendation_digest") if isinstance(payload.get("response_recommendation_digest"), dict) else {}
    candidate_reviews: dict[str, dict[str, Any]] = {}
    for row in payload.get("candidate_reviews") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker:
            candidate_reviews[ticker] = row
    return {
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "source_path": "tmp/research-freshness-opportunity-review.json",
        "improving_leadership_sectors": review.get("improving_leadership_sectors") or [],
        "underexposed_sectors": review.get("underexposed_sectors") or [],
        "portfolio_review_candidates": digest.get("portfolio_review_candidates") or review.get("portfolio_review_candidates") or [],
        "conditional_watch": digest.get("conditional_watch") or review.get("conditional_watch") or [],
        "blocked_or_deferred": digest.get("blocked_or_deferred") or review.get("blocked_or_deferred") or [],
        "candidate_reviews": candidate_reviews,
    }


def opportunity_review_hard_blocker(ticker: str, opportunity: dict[str, Any], band_status: str) -> bool:
    """Return true when opportunity-review debt should veto, not merely hold review."""
    if str(band_status or "").upper() != "IN_BAND":
        return True
    candidate_reviews = opportunity.get("candidate_reviews") if isinstance(opportunity.get("candidate_reviews"), dict) else {}
    row = candidate_reviews.get(ticker, {}) if isinstance(candidate_reviews.get(ticker), dict) else {}
    if not row:
        return True
    if row.get("below_stop_or_repair") is True:
        return True
    parts: list[str] = []
    for key in (
        "blocking_gate",
        "queue_judgment",
        "deployment_status",
        "workflow_state",
        "next_action",
    ):
        value = row.get(key)
        if value is not None:
            parts.append(str(value))
    for key in ("blocked_reasons", "monitoring_flags"):
        values = row.get(key)
        if isinstance(values, list):
            parts.extend(str(item) for item in values if str(item).strip())
    joined = " | ".join(parts).lower()
    return any(token in joined for token in HARD_OPPORTUNITY_BLOCKER_TOKENS)


def paper_position_context(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        import sqlite3
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        latest = conn.execute(
            "select snapshot_id from paper_account_snapshot where status='ok' order by generated_at_utc desc limit 1"
        ).fetchone()
        if not latest:
            return {}
        rows = conn.execute(
            "select symbol, quantity, average_entry_price, current_price, market_value, unrealized_pl, "
            "unrealized_pl_percent from paper_position_snapshot where snapshot_id=?",
            (latest["snapshot_id"],),
        ).fetchall()
        return {str(row["symbol"]).upper(): dict(row) for row in rows}
    except Exception:
        return {}
    finally:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass


def fnum(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_band_status(technical: dict[str, Any], deployment: dict[str, Any], band: dict[str, Any] | None = None) -> str:
    band = band or {}
    close = fnum(technical.get("close") or deployment.get("close"))
    low = fnum(band.get("low"))
    high = fnum(band.get("high"))
    stop = fnum(band.get("stop"))
    if close is not None and stop is not None and close < stop:
        return "BELOW_STOP"
    if close is not None and low is not None and high is not None:
        if low <= close <= high:
            return "IN_BAND"
        if close > high:
            return "ABOVE_BAND_WAIT"
        if close < low:
            return "BELOW_BAND_WAIT"
    if technical.get("below_stop") or str(deployment.get("band_position") or "").upper() in {"BELOW STOP", "BELOW_STOP"}:
        return "BELOW_STOP"
    if technical.get("in_entry_band") is True or str(deployment.get("band_position") or "").upper() in {"IN BAND", "IN_BAND"}:
        return "IN_BAND"
    text = " ".join(str(deployment.get(key) or "") for key in ("surface_state", "why", "trigger", "blocker"))
    if "above band" in text.lower() or "no chase" in text.lower():
        return "ABOVE_BAND_WAIT"
    if "below band" in text.lower():
        return "BELOW_BAND_WAIT"
    return "UNKNOWN"


def score_candidate(
    ticker: str,
    technical: dict[str, Any],
    deployment: dict[str, Any],
    sector: dict[str, Any],
    monitor: dict[str, Any],
    portfolio: dict[str, Any],
    band: dict[str, Any],
    paper: dict[str, Any],
    opportunity: dict[str, Any],
    probability_ready: bool,
) -> tuple[float, list[str], list[str], list[str]]:
    score = 0.0
    positives: list[str] = []
    vetoes: list[str] = []
    cautions: list[str] = []

    state = str(legacy_state(deployment, "surface_state") or monitor.get("deployment_status") or "").upper()
    workflow = str(legacy_state(deployment, "workflow_state") or legacy_state(monitor, "workflow_state") or legacy_state(portfolio, "workflow_state") or "").upper()
    band_status = infer_band_status(technical, deployment, band)
    coverage_lane = str(portfolio.get("coverage_lane") or "").lower()
    portfolio_role = str(portfolio.get("portfolio_role") or "").lower()

    if state == "DEPLOYABLE NOW":
        score += 38; positives.append("deployable-now current surface state")
    elif state == "PROMOTION REVIEW" or "PROMOTION" in workflow:
        score += 28; positives.append("promotion-review current surface state")
    elif state == "ALMOST DEPLOYABLE" or "ALMOST" in workflow:
        score += 18; positives.append("almost-deployable current surface state")
    elif "WATCH" in state or "WATCH" in workflow:
        score += 5; cautions.append("watch-lane only")
    elif "DO NOT TOUCH" in state or "REPAIR" in workflow:
        score -= 45; vetoes.append("repair/do-not-touch state")

    if coverage_lane == "watch" and ticker not in MONDAY_PACKET_TICKERS:
        score -= 10; cautions.append("watch coverage lane requires explicit promotion before paper packet")
    if "monitor" in portfolio_role and ticker not in MONDAY_PACKET_TICKERS:
        score -= 8; cautions.append("monitor-only portfolio role")

    if band_status == "IN_BAND":
        score += 25; positives.append("inside written band")
    elif band_status == "ABOVE_BAND_WAIT":
        score -= 12; vetoes.append("above band / no-chase")
    elif band_status == "BELOW_STOP":
        score -= 80; vetoes.append("below stop")
    elif band_status == "BELOW_BAND_WAIT":
        score -= 8; cautions.append("below band / wait for reclaim")
    else:
        cautions.append("band status unknown")

    posture = str(technical.get("ma_posture") or "").lower()
    if "above all mas" in posture:
        score += 12; positives.append("above all major moving averages")
    elif "above 50d and 200d" in posture:
        score += 7; positives.append("above 50d and 200d")
    elif "below all mas" in posture:
        score -= 15; cautions.append("below all major moving averages")

    if sector.get("improving_leadership"):
        score += 12; positives.append("sector leadership improving")
    if sector.get("underexposed"):
        score += 6; positives.append("sector is underexposed in model")
    if sector.get("leadership_status") == "deteriorating":
        score -= 6; cautions.append("sector leadership deteriorating")

    if ticker in MONDAY_PACKET_TICKERS:
        score += 6; positives.append("already in Monday band-gated review packet")
    if ticker in MATERIALS_TICKERS:
        score += 6; positives.append("Materials/diversification lane")
    if ticker in AI_POWER_TICKERS:
        score += 4; positives.append("AI infrastructure/power lane")
        cautions.append("AI-power / Technology correlation crowded")
    if ticker in ENERGY_TICKERS:
        score -= 8; cautions.append("Energy lane weak this week")
    if ticker in FINANCIAL_TICKERS and sector.get("leadership_status") == "deteriorating":
        score -= 3; cautions.append("financials need cleaner technical confirmation")

    if ticker in opportunity.get("portfolio_review_candidates", []):
        score += 5; positives.append("current opportunity digest portfolio-review candidate")
    if ticker in opportunity.get("conditional_watch", []):
        score += 2; cautions.append("current opportunity digest conditional watch")
    if ticker in opportunity.get("blocked_or_deferred", []):
        score -= 20
        if opportunity_review_hard_blocker(ticker, opportunity, band_status):
            vetoes.append("current opportunity digest blocked/deferred")
        else:
            cautions.append("current opportunity digest review debt")

    if paper:
        pl_pct = fnum(paper.get("unrealized_pl_percent"))
        if pl_pct is not None and pl_pct > 0:
            score += min(pl_pct * 100, 8); positives.append("paper position currently profitable")
        elif pl_pct is not None and pl_pct < 0:
            score += max(pl_pct * 100, -8); cautions.append("paper position currently losing")

    if not probability_ready:
        cautions.append("WF55 probability layer NOT_READY; no win-rate/model claim allowed")

    return round(score, 2), sorted(set(positives)), sorted(set(vetoes)), sorted(set(cautions))


def blocker_categories_from_text(text: str) -> list[str]:
    normalized = text.lower()
    categories: list[str] = []
    if "band" in normalized or "entry" in normalized:
        categories.append("entry_band_review")
    if "calibration" in normalized:
        categories.append("band_calibration_review")
    if "crowding" in normalized or "ai-power" in normalized or "technology" in normalized:
        categories.append("ai_technology_crowding_review")
    if "sizing" in normalized or "starter" in normalized:
        categories.append("starter_sizing_review")
    if "fresh" in normalized:
        categories.append("freshness_review")
    if not categories:
        categories.append("promotion_review")
    return sorted(set(categories))


def band_plain_text(band_status: str) -> str:
    normalized = str(band_status or "").upper().strip()
    if normalized == "IN_BAND":
        return "in band"
    if normalized in {"ABOVE_BAND", "ABOVE_BAND_WAIT"}:
        return "above the entry band"
    if normalized in {"BELOW_BAND", "BELOW_BAND_WAIT"}:
        return "below the entry band"
    if normalized == "BELOW_STOP":
        return "below stop or invalidation"
    return "without a clean band read"


def plain_english_veto_detail(
    ticker: str,
    veto: str,
    *,
    band_status: str,
    opportunity: dict[str, Any],
) -> dict[str, Any]:
    candidate_reviews = opportunity.get("candidate_reviews") if isinstance(opportunity.get("candidate_reviews"), dict) else {}
    opportunity_row = candidate_reviews.get(ticker, {}) if isinstance(candidate_reviews.get(ticker), dict) else {}
    source_blocker = opportunity_row.get("blocking_gate") or veto
    next_action = opportunity_row.get("next_action")
    blocked_reasons = [str(item) for item in opportunity_row.get("blocked_reasons") or [] if str(item).strip()]
    monitoring_flags = [str(item) for item in opportunity_row.get("monitoring_flags") or [] if str(item).strip()]

    details = [str(source_blocker)]
    if blocked_reasons:
        details.append("blocked reasons: " + ", ".join(blocked_reasons))
    if monitoring_flags:
        details.append("monitoring flags: " + ", ".join(monitoring_flags))
    detail_text = "; ".join(details)
    plain = (
        f"{ticker} was {band_plain_text(band_status)}, but could not be promoted because the "
        f"opportunity-review layer still carried unresolved promotion-review debt: {detail_text}."
    )
    if next_action:
        plain += f" Next: {next_action}"
    if any("crowding" in part.lower() or "ai-power" in part.lower() for part in details):
        plain += " Treat this as an AI/Technology concentration caution before any starter sizing is considered."
    if any("band" in part.lower() for part in details):
        plain += " Cron or the main session should clear the band review or refresh the entry-band contract before promotion."

    return {
        "veto": veto,
        "root_cause_categories": blocker_categories_from_text(detail_text),
        "source_blocker": source_blocker,
        "blocked_reasons": blocked_reasons,
        "monitoring_flags": monitoring_flags,
        "next_action": next_action,
        "source_artifact": opportunity.get("source_path"),
        "source_generated_at_utc": opportunity.get("generated_at_utc"),
        "plain_english": plain,
    }


def veto_details_for(ticker: str, vetoes: list[str], band_status: str, opportunity: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        plain_english_veto_detail(ticker, str(veto), band_status=band_status, opportunity=opportunity)
        for veto in vetoes
    ]


def verdict_from(score: float, vetoes: list[str], band_status: str, state: str, workflow: str, ticker: str) -> str:
    hard_veto = {"below stop", "repair/do-not-touch state"}
    if any(veto in hard_veto for veto in vetoes):
        return "reject_currently"
    if vetoes:
        return "defer_until_veto_clears"
    review_lane = (
        state == "DEPLOYABLE NOW"
        or state == "PROMOTION REVIEW"
        or "PROMOTION" in workflow
        or ticker in MONDAY_PACKET_TICKERS
    )
    if band_status == "IN_BAND" and score >= 45 and review_lane:
        return "promote_for_owner_review"
    if band_status == "IN_BAND" and score >= 30:
        return "in_band_review_hold"
    if score >= 30 and band_status == "BELOW_BAND_WAIT":
        return "watch_for_reclaim_or_pullback"
    return "monitor_only"


def build_gate() -> dict[str, Any]:
    paths = {
        "technical_refresh": TMP / "technical-refresh.json",
        "deployment_readiness_surface": TMP / "deployment-readiness-surface.json",
        "sector_expansion_board": TMP / "sector-expansion-board.json",
        "research_freshness_opportunity_review": TMP / "research-freshness-opportunity-review.json",
        "ticker_monitoring_performance": TMP / "ticker-monitoring-performance.json",
        "recommendation_outcome_ledger": TMP / "recommendation-outcome-ledger-current.json",
        "probability_readiness": TMP / "probability-readiness-report.json",
        "paper_position_state": TMP / "wf67-paper-position-state.sqlite",
        "portfolio_config": DEFAULT_PORTFOLIO_CONFIG,
        "band_proposals": DEFAULT_BAND_PROPOSALS,
    }
    artifacts = {name: load_json(path) for name, path in paths.items() if path.suffix != ".sqlite"}
    status = {
        name: artifact_status(paths[name], artifacts.get(name, {}), max_age_hours=96)
        for name in artifacts
    }
    technical = records_by_ticker(artifacts["technical_refresh"])
    deployment = deployment_records(artifacts["deployment_readiness_surface"])
    sectors = sector_context(artifacts["sector_expansion_board"])
    monitors = records_by_ticker(artifacts["ticker_monitoring_performance"])
    portfolio = portfolio_records(artifacts["portfolio_config"])
    legacy_bands = entry_bands(artifacts["portfolio_config"])
    sql_first_bands = entry_bands_from_band_proposals(artifacts["band_proposals"])
    bands = {**legacy_bands, **sql_first_bands}
    opportunity = opportunity_context(artifacts["research_freshness_opportunity_review"])
    paper = paper_position_context(paths["paper_position_state"])
    probability_ready = artifacts["probability_readiness"].get("verdict") == "READY"

    tickers = sorted(set(technical) | set(deployment) | set(sectors) | set(monitors) | set(portfolio) | set(bands) | set(MONDAY_PACKET_TICKERS) | set(paper))
    candidates: list[dict[str, Any]] = []
    for ticker in tickers:
        tech = technical.get(ticker, {})
        dep = deployment.get(ticker, {})
        sec = sectors.get(ticker, {})
        mon = monitors.get(ticker, {})
        port = portfolio.get(ticker, {})
        band = bands.get(ticker, {})
        pap = paper.get(ticker, {})
        band_status = infer_band_status(tech, dep, band)
        state = str(legacy_state(dep, "surface_state") or mon.get("deployment_status") or "").upper()
        workflow = str(legacy_state(dep, "workflow_state") or legacy_state(mon, "workflow_state") or legacy_state(port, "workflow_state") or "").upper()
        score, positives, vetoes, cautions = score_candidate(ticker, tech, dep, sec, mon, port, band, pap, opportunity, probability_ready)
        veto_details = veto_details_for(ticker, vetoes, band_status, opportunity)
        candidates.append({
            "ticker": ticker,
            "rank": None,
            "chief_intelligence_score": score,
            "chief_intelligence_verdict": verdict_from(score, vetoes, band_status, state, workflow, ticker),
            "surface_state": legacy_state(dep, "surface_state") or mon.get("deployment_status") or "UNKNOWN",
            "workflow_state": legacy_state(dep, "workflow_state") or legacy_state(mon, "workflow_state") or legacy_state(port, "workflow_state") or "UNKNOWN",
            "close": tech.get("close") or dep.get("close") or ((mon.get("known_at_time") or {}).get("close") if isinstance(mon.get("known_at_time"), dict) else None),
            "data_date": tech.get("data_date") or dep.get("source_generated_at_utc"),
            "band_status": band_status,
            "entry_band": {
                "low": band.get("low"),
                "high": band.get("high"),
                "stop": band.get("stop"),
                "label": band.get("label"),
                "band_last_set": band.get("band_last_set"),
                "source_priority": band.get("source_priority") or "legacy_portfolio_config",
                "source_artifact": band.get("source_artifact") or rel(DEFAULT_PORTFOLIO_CONFIG),
                "source_generated_at_utc": band.get("source_generated_at_utc"),
                "canonical_apply_eligible": band.get("canonical_apply_eligible"),
                "needs_review": band.get("needs_review"),
                "supersedes_portfolio_config_band": bool(band.get("supersedes_portfolio_config_band")),
                "legacy_current_band": band.get("legacy_current_band"),
            },
            "coverage_lane": port.get("coverage_lane"),
            "portfolio_role": port.get("portfolio_role"),
            "sector": sec.get("sector"),
            "sector_leadership_status": sec.get("leadership_status"),
            "positive_evidence": positives,
            "vetoes": vetoes,
            "veto_details": veto_details,
            "root_cause_blockers": sorted({
                category
                for detail in veto_details
                for category in detail.get("root_cause_categories", [])
            }),
            "plain_english_blockers": [detail["plain_english"] for detail in veto_details if detail.get("plain_english")],
            "cautions": cautions,
            "paper_position": {
                "present": bool(pap),
                "unrealized_pl": pap.get("unrealized_pl"),
                "unrealized_pl_percent": pap.get("unrealized_pl_percent"),
            },
            "authority": AUTHORITY.copy(),
        })

    candidates.sort(key=lambda item: item["chief_intelligence_score"], reverse=True)
    for index, item in enumerate(candidates, start=1):
        item["rank"] = index
        alternatives = [c["ticker"] for c in candidates[:5] if c["ticker"] != item["ticker"]]
        item["opportunity_cost_vs_top_alternatives"] = alternatives[:3]

    top_promotions = [c for c in candidates if c["chief_intelligence_verdict"] == "promote_for_owner_review"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "consumer_posture": "review_only_not_execution_authority",
        "authority": AUTHORITY.copy(),
        "source_artifacts": status,
        "summary": {
            "candidate_count": len(candidates),
            "promote_for_owner_review_count": len(top_promotions),
            "top_promote_for_owner_review": [c["ticker"] for c in top_promotions[:5]],
            "top_ranked": [c["ticker"] for c in candidates[:10]],
            "probability_readiness": artifacts["probability_readiness"].get("verdict"),
            "paper_positions_seen": sorted(paper),
            "global_cautions": [
                "WF55 probability layer is not ready; scores are deterministic review ranks only, not calibrated expected returns.",
                "Generated gate is review-only and does not authorize paper/live execution or owner approval.",
            ],
        },
        "candidates": candidates,
        "validation": validate_gate({"authority": AUTHORITY, "candidates": candidates}, include_summary=False),
    }


def validate_gate(gate: dict[str, Any], *, include_summary: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = gate.get("authority") if isinstance(gate.get("authority"), dict) else {}
    for key in FALSE_AUTHORITY_KEYS:
        if authority.get(key) is not False:
            errors.append(f"authority flag must be false: {key}")
    if authority.get("review_only") is not True:
        errors.append("authority.review_only must be true")
    candidates = gate.get("candidates") if isinstance(gate.get("candidates"), list) else []
    if not candidates:
        errors.append("no candidates emitted")
    for candidate in candidates:
        c_auth = candidate.get("authority") if isinstance(candidate, dict) else {}
        for key in FALSE_AUTHORITY_KEYS:
            if c_auth.get(key) is not False:
                errors.append(f"{candidate.get('ticker')}: candidate authority flag must be false: {key}")
        if candidate.get("chief_intelligence_verdict") == "promote_for_owner_review" and candidate.get("vetoes"):
            errors.append(f"{candidate.get('ticker')}: promoted candidate has vetoes")
        if candidate.get("chief_intelligence_verdict") == "promote_for_owner_review" and candidate.get("band_status") != "IN_BAND":
            errors.append(f"{candidate.get('ticker')}: promoted candidate is not in band")
    if not any(c.get("chief_intelligence_verdict") == "promote_for_owner_review" for c in candidates):
        warnings.append("no candidate reached promote_for_owner_review")
    status = "ok" if not errors else "error"
    out = {"status": status, "errors": errors, "warnings": warnings}
    if include_summary:
        out["candidate_count"] = len(candidates)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Chief Intelligence promotion gate artifact.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gate = build_gate()
    validation = validate_gate(gate)
    gate["validation"] = validation
    if args.write:
        atomic_write_json(args.output, gate)
        atomic_write_json(args.validation_output, validation)
    if args.validate and validation["status"] != "ok":
        print(json.dumps(validation, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({
        "status": gate["status"],
        "validation": validation["status"],
        "candidate_count": gate["summary"]["candidate_count"],
        "top_ranked": gate["summary"]["top_ranked"][:5],
        "promote_for_owner_review": gate["summary"]["top_promote_for_owner_review"],
        "output": rel(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
