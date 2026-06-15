#!/usr/bin/env python3
"""Compose a WF60 review-only research freshness/opportunity surface.

This script consumes existing review artifacts and writes a bounded operator
review packet. It does not mutate canonical notes, portfolio state, deployment
state, watchlists, approvals, sizing, or trades.
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"

DEFAULT_SECTOR_BOARD = TMP / "sector-expansion-board.json"
DEFAULT_TICKER_PERFORMANCE = TMP / "ticker-monitoring-performance.json"
DEFAULT_PROMOTION_QUEUE = TMP / "sector-dashboard-promotion-queue.csv"
DEFAULT_DASHBOARD_HTML = TMP / "sector-dashboard-suite.html"
DEFAULT_PORTFOLIO_CONFIG = TMP / "portfolio-config.json"
DEFAULT_SMALL_MID_CAP_REGIME_FEED = TMP / "small-mid-cap-regime-feed.json"
DEFAULT_OUTPUT = TMP / "research-freshness-opportunity-review.json"
DEFAULT_MARKDOWN_OUTPUT = TMP / "research-freshness-opportunity-review.md"

SCHEMA_VERSION = 1
CONTEXT_FRESH_HOURS = 36

AUTHORITY = {
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "trade_execution_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inference_allowed": False,
    "probability_or_modeling_authority": False,
    "model_ranked_deployment_allowed": False,
    "model_driven_deployment_allowed": False,
    "capital_action_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def workspace_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else WORKSPACE / value


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def source_artifact(path: Path, payload: dict[str, Any] | None, *, required: bool, now: datetime, kind: str = "json") -> dict[str, Any]:
    exists = path.exists()
    generated = (payload or {}).get("generated_at_utc") or (payload or {}).get("generated_at")
    generated_dt = parse_dt(generated)
    freshness = "missing"
    age_hours: float | None = None
    if exists and generated_dt:
        age_hours = round((now - generated_dt).total_seconds() / 3600, 2)
        freshness = "fresh" if age_hours <= CONTEXT_FRESH_HOURS else "stale"
    elif exists:
        freshness = "unknown_generated_at" if kind == "json" else "present_unstamped"
    fresh_enough = bool(exists and freshness in {"fresh", "present_unstamped"})
    if required and kind == "json" and freshness != "fresh":
        fresh_enough = False
    return {
        "path": rel(path),
        "required": required,
        "exists": exists,
        "status": (payload or {}).get("status"),
        "generated_at_utc": generated,
        "freshness": freshness,
        "age_hours": age_hours,
        "fresh_enough_for_context": fresh_enough,
    }


def load_promotion_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def ticker_index(ticker_performance: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in ticker_performance.get("tickers") or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if ticker:
            out[ticker] = item
    return out


def promotion_candidates_from_board(sector_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sector in sector_board.get("sectors") or []:
        if not isinstance(sector, dict):
            continue
        for row in sector.get("promotion_review_status") or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("candidate") or "").upper().strip()
            if not ticker:
                continue
            out[ticker] = {
                "ticker": ticker,
                "sector": sector.get("sector"),
                "sector_etf": sector.get("ticker"),
                "sector_leadership_status": sector.get("leadership_status"),
                "sector_underexposed": bool(sector.get("underexposed")),
                "promotion_review_pending": row.get("promotion_review_pending"),
                "blocking_gate": row.get("blocking_gate"),
                "queue_judgment": row.get("automated_queue_judgment"),
                "next_action": row.get("next_action"),
                "owner_approval_granted": False,
                "watchlist_promotion_allowed": False,
            }
    return out


def merge_csv_rows(candidates: dict[str, dict[str, Any]], csv_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    out = {key: dict(value) for key, value in candidates.items()}
    for row in csv_rows:
        ticker = str(row.get("Candidate") or "").upper().strip()
        if not ticker:
            continue
        current = out.setdefault(ticker, {"ticker": ticker})
        current.setdefault("sector", row.get("Sector"))
        current.setdefault("sector_etf", row.get("ETF"))
        current.setdefault("blocking_gate", row.get("Blocking Gate"))
        current.setdefault("queue_judgment", row.get("Queue Judgment"))
        current.setdefault("next_action", row.get("Next Action"))
        current["owner_approval_granted"] = False
        current["watchlist_promotion_allowed"] = False
    return out


def portfolio_config_review_candidates(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract active review cues from the machine-tracked universe.

    This keeps manually promoted research from disappearing until the next
    sector-board generator learns the new names. It remains review-only and
    never grants promotion/sizing/sleeve/deployment authority.
    """
    tracked = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in tracked.items():
        if not isinstance(meta, dict):
            continue
        ticker_text = str(ticker or "").upper().strip()
        if not ticker_text:
            continue
        workflow = str(legacy_state(meta, "workflow_state") or "").upper()
        role = str(meta.get("portfolio_role") or "").lower()
        thesis = str(meta.get("thesis_status") or "")
        if workflow == "PROMOTION REVIEW" or role == "portfolio_review_candidate":
            out[ticker_text] = {
                "ticker": ticker_text,
                "sector": meta.get("sector"),
                "sector_etf": None,
                "sector_leadership_status": "manual_sector_expansion_review",
                "sector_underexposed": None,
                "promotion_review_pending": True,
                "blocking_gate": "separate owner-gated model/sleeve/deployment decision required",
                "queue_judgment": "owner-approved portfolio-review only; no allocation or deployment authority",
                "next_action": "Build or refresh portfolio-review packet; verify valuation, technical setup, concentration, and risk before any owner decision.",
                "owner_approval_granted": False,
                "watchlist_promotion_allowed": False,
            }
        elif workflow == "WATCH" and role == "sector_monitor" and "2026-05-15" in thesis:
            out[ticker_text] = {
                "ticker": ticker_text,
                "sector": meta.get("sector"),
                "sector_etf": None,
                "sector_leadership_status": "machine_tracked_research_monitor",
                "sector_underexposed": None,
                "promotion_review_pending": False,
                "blocking_gate": "research-only monitor; explicit promotion review required",
                "queue_judgment": "conditional watch; not a portfolio-review candidate yet",
                "next_action": "Keep machine-tracked research/technical monitoring; escalate only after fundamental, valuation, technical, and risk review.",
                "owner_approval_granted": False,
                "watchlist_promotion_allowed": False,
            }
    return out


def candidate_review_rows(candidates: dict[str, dict[str, Any]], tickers: dict[str, dict[str, Any]], *, sector_fresh: bool, ticker_fresh: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, candidate in sorted(candidates.items()):
        monitor = tickers.get(ticker, {})
        reconciled_candidate = reconcile_candidate_with_monitoring(ticker, candidate, monitor)
        known_at_time = monitor.get("known_at_time") if isinstance(monitor.get("known_at_time"), dict) else {}
        rows.append({
            **reconciled_candidate,
            "monitoring_context_available": bool(monitor),
            "sector_context_fresh_enough": sector_fresh,
            "ticker_monitoring_fresh_enough": ticker_fresh,
            "workflow_state": legacy_state(monitor, "workflow_state"),
            "deployment_status": monitor.get("deployment_status"),
            "band_status": monitor.get("band_status"),
            "below_stop_or_repair": monitor.get("below_stop_or_repair"),
            "monitoring_flags": monitor.get("monitoring_flags") or [],
            "blocked_reasons": monitor.get("blocked_reasons") or [],
            "data_date": known_at_time.get("data_date"),
            "close": known_at_time.get("close"),
            "review_only_next_step": "Human review only: verify research freshness, blocker state, and owner approval before any canonical or portfolio action.",
        })
    return rows


def monitor_band_status_label(band_status: str) -> str | None:
    normalized = band_status.upper().strip()
    if normalized in {"ABOVE_BAND", "ABOVE_BAND_WAIT", "NO_CHASE"}:
        return "above current band / no-chase"
    if normalized in {"IN_BAND", "IN_ENTRY_BAND"}:
        return "inside current band"
    if normalized in {"BELOW_BAND", "BELOW_BAND_WAIT"}:
        return "below current band / wait for reclaim"
    if normalized in {"BELOW_STOP", "BELOW_INVALIDATION"}:
        return "below stop or invalidation"
    return None


def stale_queue_text_conflicts_with_monitor(candidate: dict[str, Any], monitor: dict[str, Any]) -> bool:
    """Detect stale queue prose when fresh ticker monitoring has a different band state.

    WF60 intentionally carries owner/research queue text forward, but fresh
    ticker monitoring is the current source for band status. This guard prevents
    old narrative such as "below formal band / near invalidation" from being
    emitted beside a fresh ABOVE_BAND_WAIT monitor state.
    """
    band_status = str(monitor.get("band_status") or "").upper().strip()
    if not band_status:
        return False
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("blocking_gate", "queue_judgment", "next_action")
    ).lower()
    if band_status in {"ABOVE_BAND", "ABOVE_BAND_WAIT", "NO_CHASE"}:
        return any(
            marker in text
            for marker in (
                "below formal band",
                "below the ",
                "near invalidation",
                "close to ",
                "band reclaim",
            )
        )
    if band_status in {"BELOW_BAND", "BELOW_BAND_WAIT"}:
        return "above band" in text or "no-chase" in text or "no chase" in text
    if band_status in {"IN_BAND", "IN_ENTRY_BAND"}:
        return any(marker in text for marker in ("below formal band", "above band", "near invalidation", "below stop"))
    return False


def reconcile_candidate_with_monitoring(ticker: str, candidate: dict[str, Any], monitor: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(monitor, dict) or not monitor:
        return dict(candidate)
    if not stale_queue_text_conflicts_with_monitor(candidate, monitor):
        return dict(candidate)

    known_at_time = monitor.get("known_at_time") if isinstance(monitor.get("known_at_time"), dict) else {}
    band_status = str(monitor.get("band_status") or "").upper().strip()
    fresh_gate = monitor_band_status_label(band_status) or "fresh monitoring review required"
    close = known_at_time.get("close")
    data_date = known_at_time.get("data_date")
    price_text = f" at {close}" if close is not None else ""
    date_text = f" on {data_date}" if data_date else ""
    out = dict(candidate)
    out["stale_queue_text_reconciled"] = True
    out["reconciliation_source"] = "ticker_monitoring_performance"
    out["stale_queue_text"] = {
        "blocking_gate": candidate.get("blocking_gate"),
        "queue_judgment": candidate.get("queue_judgment"),
        "next_action": candidate.get("next_action"),
    }
    out["blocking_gate"] = f"{fresh_gate}; prior queue text conflicted with fresh monitoring"
    out["queue_judgment"] = "trigger not live; fresh monitoring overrides stale queue prose"
    out["next_action"] = (
        f"Fresh ticker monitoring{date_text} has {ticker}{price_text} as {fresh_gate}. "
        "Keep any prior owner approval or review history recorded, but do not treat it as deployable-now "
        "until price/band context is re-cleared or an explicit band review updates the gate."
    )
    return out


def diversified_fund_regime_cues(small_mid_cap_feed: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(small_mid_cap_feed, dict) or not small_mid_cap_feed:
        return {
            "status": "missing_optional_feed",
            "small_mid_cap_posture": "manual_review_required",
            "commodity_review_candidates": [],
            "macro_correlation_required": True,
            "review_only": True,
            "authority_boundary": "Optional diversified-fund regime cues are missing; no allocation, sleeve, sizing, or approval authority is inferred.",
        }
    summary = small_mid_cap_feed.get("summary") if isinstance(small_mid_cap_feed.get("summary"), dict) else {}
    bucket_summary = summary.get("bucket_summary") if isinstance(summary.get("bucket_summary"), dict) else {}
    small_mid_buckets = ["small_cap", "small_cap_quality", "small_cap_value_quality", "small_cap_value", "mid_cap"]
    small_mid_improving: list[str] = []
    small_mid_deteriorating: list[str] = []
    for bucket in small_mid_buckets:
        block = bucket_summary.get(bucket) if isinstance(bucket_summary.get(bucket), dict) else {}
        small_mid_improving.extend(str(ticker) for ticker in block.get("improving") or [])
        small_mid_deteriorating.extend(str(ticker) for ticker in block.get("deteriorating") or [])
    commodity_candidates: list[str] = []
    for row in small_mid_cap_feed.get("proxies") or []:
        if not isinstance(row, dict):
            continue
        bucket = str(row.get("bucket") or "")
        if bucket in {"precious_metals", "broad_commodities", "tactical_commodity"} and row.get("regime_label") == "improving":
            commodity_candidates.append(str(row.get("ticker") or "").upper())
    if small_mid_improving:
        small_mid_posture = "improving_review_only"
    elif small_mid_deteriorating:
        small_mid_posture = "deteriorating_review_only"
    else:
        small_mid_posture = "neutral_or_mixed_review_only"
    return {
        "status": small_mid_cap_feed.get("status") or "unknown",
        "generated_at_utc": small_mid_cap_feed.get("generated_at_utc"),
        "market_data_as_of": small_mid_cap_feed.get("market_data_as_of"),
        "market_data_fresh_enough": small_mid_cap_feed.get("market_data_fresh_enough"),
        "small_mid_cap_posture": small_mid_posture,
        "small_mid_cap_improving": sorted(set(small_mid_improving)),
        "small_mid_cap_deteriorating": sorted(set(small_mid_deteriorating)),
        "commodity_review_candidates": sorted(set(commodity_candidates)),
        "macro_correlation_required": True,
        "review_only": True,
        "authority_boundary": "Diversified-fund regime cues are review-only context; no allocation, sleeve, sizing, cash, deployment, trade/account action, or owner approval is inferred.",
    }


def response_recommendation_digest(candidate_rows: list[dict[str, Any]], opportunity_review: dict[str, Any], small_mid_cap_feed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Small user-facing digest for Veritas responses and cron handoffs.

    The digest intentionally turns leadership research into review cues, not
    portfolio actions. It gives the main session enough structure to embed the
    same pattern Randall asked for in normal replies: what is improving, what
    deserves review, what is blocked, and what authority is still owner-gated.
    """
    portfolio_review_candidates: list[str] = []
    conditional_watch: list[str] = []
    blocked_or_deferred: list[str] = []
    top_review_cues: list[dict[str, Any]] = []

    for row in candidate_rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        blockers = [str(item) for item in row.get("blocked_reasons") or [] if str(item).strip()]
        queue_text = " ".join(str(row.get(key) or "") for key in ("queue_judgment", "next_action", "blocking_gate")).lower()
        if "conditional watch" in queue_text or "research-only monitor" in queue_text:
            conditional_watch.append(ticker)
        elif "portfolio" in queue_text and "review" in queue_text:
            portfolio_review_candidates.append(ticker)
        elif blockers or row.get("below_stop_or_repair"):
            blocked_or_deferred.append(ticker)
        else:
            conditional_watch.append(ticker)
        if len(top_review_cues) < 8:
            top_review_cues.append({
                "ticker": ticker,
                "sector": row.get("sector"),
                "leadership_status": row.get("sector_leadership_status"),
                "review_cue": row.get("next_action") or row.get("queue_judgment") or "manual review only",
                "blocker": row.get("blocking_gate") or ("; ".join(blockers[:3]) if blockers else None),
                "owner_approval_granted": False,
                "apply_allowed": False,
            })

    return {
        "include_in_veritas_responses": True,
        "digest_posture": "review_only_opportunity_radar",
        "improving_leadership": opportunity_review.get("improving_leadership_sectors") or [],
        "underexposed_lanes": opportunity_review.get("underexposed_sectors") or [],
        "portfolio_review_candidates": sorted(set(portfolio_review_candidates)),
        "conditional_watch": sorted(set(conditional_watch)),
        "blocked_or_deferred": sorted(set(blocked_or_deferred or opportunity_review.get("blocked_or_review_required_candidates") or [])),
        "diversified_fund_regime_cues": diversified_fund_regime_cues(small_mid_cap_feed),
        "top_review_cues": top_review_cues,
        "required_boundary_sentence": "Review-only cue: no promotion, sizing, sleeve, cash, deployment, trade, account action, or owner approval is inferred from this cron output.",
    }


def build_payload(
    window: str = "post-close",
    *,
    sector_board_path: Path = DEFAULT_SECTOR_BOARD,
    ticker_performance_path: Path = DEFAULT_TICKER_PERFORMANCE,
    promotion_queue_path: Path = DEFAULT_PROMOTION_QUEUE,
    dashboard_html_path: Path = DEFAULT_DASHBOARD_HTML,
    portfolio_config_path: Path = DEFAULT_PORTFOLIO_CONFIG,
    small_mid_cap_regime_feed_path: Path = DEFAULT_SMALL_MID_CAP_REGIME_FEED,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    sector_board = load_json(sector_board_path)
    ticker_performance = load_json(ticker_performance_path)
    portfolio_config = load_json(portfolio_config_path)
    small_mid_cap_regime_feed = load_json(small_mid_cap_regime_feed_path)
    promotion_csv = load_promotion_csv(promotion_queue_path)

    sources = {
        "sector_expansion_board": source_artifact(sector_board_path, sector_board, required=True, now=now),
        "ticker_monitoring_performance": source_artifact(ticker_performance_path, ticker_performance, required=True, now=now),
        "portfolio_config": source_artifact(portfolio_config_path, portfolio_config, required=False, now=now),
        "small_mid_cap_regime_feed": source_artifact(small_mid_cap_regime_feed_path, small_mid_cap_regime_feed, required=False, now=now),
        "sector_dashboard_promotion_queue": source_artifact(promotion_queue_path, {}, required=False, now=now, kind="csv"),
        "sector_dashboard_suite_html": source_artifact(dashboard_html_path, {}, required=False, now=now, kind="html"),
    }
    sector_fresh = bool(sources["sector_expansion_board"].get("fresh_enough_for_context"))
    ticker_fresh = bool(sources["ticker_monitoring_performance"].get("fresh_enough_for_context"))

    warnings: list[str] = []
    errors: list[str] = []
    for name, source in sources.items():
        if source["required"] and not source["exists"]:
            errors.append(f"required source missing: {name}")
        elif source["required"] and source["freshness"] == "stale":
            warnings.append(f"required source stale: {name} age_hours={source['age_hours']}")
        elif source["required"] and source["freshness"] == "unknown_generated_at":
            warnings.append(f"required source unstamped or unparseable generated_at: {name}")
        elif source["required"] and source["freshness"] == "missing":
            errors.append(f"required source has no usable payload: {name}")
        elif not source["required"] and not source["exists"]:
            warnings.append(f"optional source missing: {name}")
    for name, doc in (("sector_expansion_board", sector_board), ("ticker_monitoring_performance", ticker_performance)):
        status = doc.get("status")
        if status not in {"ok", None}:
            warnings.append(f"source {name} status={status}")

    candidates = merge_csv_rows({**portfolio_config_review_candidates(portfolio_config), **promotion_candidates_from_board(sector_board)}, promotion_csv)
    tickers = ticker_index(ticker_performance)
    candidate_rows = candidate_review_rows(candidates, tickers, sector_fresh=sector_fresh, ticker_fresh=ticker_fresh)

    sector_summary = sector_board.get("summary") if isinstance(sector_board.get("summary"), dict) else {}
    ticker_summary = ticker_performance.get("summary") if isinstance(ticker_performance.get("summary"), dict) else {}
    blocked = [row["ticker"] for row in candidate_rows if row.get("blocked_reasons")]
    missing_monitor = [row["ticker"] for row in candidate_rows if not row.get("monitoring_context_available")]
    leadership_counts = Counter(str(row.get("sector_leadership_status") or "unknown") for row in candidate_rows)
    pending_candidates = sorted(sector_summary.get("promotion_review_candidates") or [
        row["ticker"] for row in candidate_rows if row.get("promotion_review_pending") is not False
    ])

    opportunity_review = {
        "improving_leadership_sectors": sector_summary.get("improving_leadership_sectors") or [],
        "underexposed_sectors": sector_summary.get("underexposed_sectors") or [],
        "promotion_review_candidates": pending_candidates,
        "queue_names_reviewed": sorted(candidates),
        "candidate_count": len(candidate_rows),
        "pending_candidate_count": len(pending_candidates),
        "candidate_leadership_counts": dict(sorted(leadership_counts.items())),
        "blocked_or_review_required_candidates": blocked,
        "candidates_missing_monitoring_context": missing_monitor,
        "fail_closed_tickers_from_monitoring": ticker_summary.get("fail_closed_tickers") or [],
    }

    status = "blocked" if errors else "degraded" if warnings or missing_monitor else "ok"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": status,
        "consumer_posture": "review_only",
        "authority": dict(AUTHORITY),
        "source_artifacts": sources,
        "research_freshness_review": {
            "all_required_sources_fresh_enough": bool(sector_fresh and ticker_fresh),
            "stale_or_missing_required_sources": [name for name, source in sources.items() if source["required"] and not source["fresh_enough_for_context"]],
            "outcome_analytics_ready": ((ticker_performance.get("history_status") or {}).get("outcome_analytics_ready") is True),
            "future_realized_outcomes_used": False,
        },
        "opportunity_review": opportunity_review,
        "response_recommendation_digest": response_recommendation_digest(candidate_rows, opportunity_review, small_mid_cap_regime_feed),
        "candidate_reviews": candidate_rows,
        "warnings": warnings,
        "errors": errors,
        "limits": [
            "review-only composition of existing artifacts; no canonical note mutation, portfolio mutation, deployment mutation, watchlist promotion, sizing, trade execution, owner-approval inference, probability modeling, or capital action authority",
            "sector and ticker context are descriptive freshness/opportunity inputs only; stale or missing sources degrade the artifact instead of filling gaps",
            "candidate rows are review objects, not recommendations to add, size, promote, or execute",
        ],
    }
    validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("consumer_posture") != "review_only":
        raise ValueError("consumer_posture must be review_only")
    for key, expected in AUTHORITY.items():
        if (payload.get("authority") or {}).get(key) is not expected:
            raise ValueError(f"authority flag mismatch: {key}")
    freshness = payload.get("research_freshness_review") or {}
    if freshness.get("future_realized_outcomes_used") is not False:
        raise ValueError("future realized outcomes must not be used")
    for row in payload.get("candidate_reviews") or []:
        if row.get("owner_approval_granted") is not False:
            raise ValueError(f"candidate owner approval drift: {row.get('ticker')}")
        if row.get("watchlist_promotion_allowed") is not False:
            raise ValueError(f"candidate watchlist promotion authority drift: {row.get('ticker')}")
    digest = payload.get("response_recommendation_digest") or {}
    if digest.get("digest_posture") != "review_only_opportunity_radar":
        raise ValueError("response recommendation digest must stay review-only")
    diversified = digest.get("diversified_fund_regime_cues") or {}
    if diversified.get("review_only") is not True or diversified.get("macro_correlation_required") is not True:
        raise ValueError("diversified fund regime cues must stay review-only and macro/correlation gated")
    for row in digest.get("top_review_cues") or []:
        if row.get("owner_approval_granted") is not False or row.get("apply_allowed") is not False:
            raise ValueError(f"digest authority drift: {row.get('ticker')}")


def markdown_summary(payload: dict[str, Any]) -> str:
    opp = payload.get("opportunity_review") or {}
    fresh = payload.get("research_freshness_review") or {}
    digest = payload.get("response_recommendation_digest") or {}
    warnings = payload.get("warnings") or []
    errors = payload.get("errors") or []
    return "\n".join([
        "# Research Freshness Opportunity Review v1",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        "- Posture: review-only; no canonical, portfolio, deployment, watchlist, sizing, trade, approval, probability, or capital-action authority.",
        f"- Required sources fresh enough: {fresh.get('all_required_sources_fresh_enough')}",
        f"- Promotion-review candidates: {', '.join(opp.get('promotion_review_candidates') or []) or 'none'}",
        f"- Blocked/review-required candidates: {', '.join(opp.get('blocked_or_review_required_candidates') or []) or 'none'}",
        f"- Missing monitoring context: {', '.join(opp.get('candidates_missing_monitoring_context') or []) or 'none'}",
        f"- Improving leadership sectors: {', '.join(opp.get('improving_leadership_sectors') or []) or 'none'}",
        f"- Underexposed sectors: {', '.join(opp.get('underexposed_sectors') or []) or 'none'}",
        f"- Response radar candidates: portfolio review={', '.join(digest.get('portfolio_review_candidates') or []) or 'none'}; conditional watch={', '.join(digest.get('conditional_watch') or []) or 'none'}; blocked/deferred={', '.join(digest.get('blocked_or_deferred') or []) or 'none'}",
        f"- Diversified fund cues: small/mid posture={(digest.get('diversified_fund_regime_cues') or {}).get('small_mid_cap_posture')}; commodity review candidates={', '.join((digest.get('diversified_fund_regime_cues') or {}).get('commodity_review_candidates') or []) or 'none'}; macro/correlation required={(digest.get('diversified_fund_regime_cues') or {}).get('macro_correlation_required')}",
        f"- Boundary sentence for replies: {digest.get('required_boundary_sentence')}",
        f"- Warnings: {'; '.join(warnings) if warnings else 'none'}",
        f"- Errors: {'; '.join(errors) if errors else 'none'}",
        "",
    ])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF60 review-only research freshness/opportunity review artifact.")
    parser.add_argument("--window", default="post-close", help="Review window label.")
    parser.add_argument("--sector-board", type=Path, default=DEFAULT_SECTOR_BOARD, help="Input sector expansion board JSON.")
    parser.add_argument("--ticker-performance", type=Path, default=DEFAULT_TICKER_PERFORMANCE, help="Input ticker monitoring performance JSON.")
    parser.add_argument("--promotion-queue", type=Path, default=DEFAULT_PROMOTION_QUEUE, help="Optional dashboard promotion queue CSV.")
    parser.add_argument("--dashboard-html", type=Path, default=DEFAULT_DASHBOARD_HTML, help="Optional sector dashboard HTML.")
    parser.add_argument("--portfolio-config", type=Path, default=DEFAULT_PORTFOLIO_CONFIG, help="Optional portfolio config JSON for active review-candidate carry-forward.")
    parser.add_argument("--small-mid-cap-regime-feed", type=Path, default=DEFAULT_SMALL_MID_CAP_REGIME_FEED, help="Optional WF61 small/mid-cap and diversified-fund regime feed JSON.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT, help="Output Markdown path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown summary generation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.window,
        sector_board_path=workspace_path(args.sector_board),
        ticker_performance_path=workspace_path(args.ticker_performance),
        promotion_queue_path=workspace_path(args.promotion_queue),
        dashboard_html_path=workspace_path(args.dashboard_html),
        portfolio_config_path=workspace_path(args.portfolio_config),
        small_mid_cap_regime_feed_path=workspace_path(args.small_mid_cap_regime_feed),
    )
    output = workspace_path(args.output)
    atomic_write_json(output, payload, indent=2, ensure_ascii=False)
    if not args.no_markdown:
        atomic_write_text(workspace_path(args.markdown_output), markdown_summary(payload))
    print(f"wrote {rel(output)}")
    print(f"status={payload['status']} candidates={payload['opportunity_review']['candidate_count']} required_fresh={payload['research_freshness_review']['all_required_sources_fresh_enough']}")
    return 0 if payload["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
