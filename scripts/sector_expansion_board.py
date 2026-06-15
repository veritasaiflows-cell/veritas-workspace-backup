#!/usr/bin/env python3
"""Build the WF53 review-only daily sector expansion board.

The board answers one operator question without mutating canonical notes:
Where is sector leadership improving, where are we underexposed, and which names
deserve promotion review?
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
QUESTION = "Where is sector leadership improving, where are we underexposed, and which names deserve promotion review?"
SCHEMA_VERSION = 1
SMA_WINDOW = 50
SHORT_SMA_WINDOWS = (5, 20)
HISTORY_PERIOD = "4mo"
SPY_TICKER = "SPY"
SECTOR_ETFS: dict[str, str] = {
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Technology",
    "XLU": "Utilities",
}
AUTHORITY_FALSE_FLAGS = [
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "owner_approval_granted",
    "probability_or_modeling_authority",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def authority_false_block() -> dict[str, bool]:
    return {flag: False for flag in AUTHORITY_FALSE_FLAGS}


def number(value: Any) -> int | float:
    n = float(value)
    return int(n) if n.is_integer() else round(n, 4)


def normalize_sector(sector: str | None) -> str:
    if not sector:
        return "Unknown"
    value = str(sector).strip()
    aliases = {
        "Tech": "Technology",
        "Tech / AI Infrastructure": "Technology",
        "Tech / Defense": "Technology",
        "Healthcare": "Health Care",
        "Health Care": "Health Care",
        "Consumer Defensive": "Consumer Staples",
        "Consumer Cyclical": "Consumer Discretionary",
        "Real Estate": "Real Estate",
        "Communication Services": "Communication Services",
    }
    return aliases.get(value, value)


def load_json(path: Path) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else None


def pct_change(series: list[dict[str, Any]], lookback: int) -> float | None:
    if len(series) <= lookback:
        return None
    current = series[-1].get("close")
    prior = series[-1 - lookback].get("close")
    if current in (None, 0) or prior in (None, 0):
        return None
    return round(((float(current) - float(prior)) / float(prior)) * 100.0, 4)


def compute_sma(series: list[dict[str, Any]], window: int = SMA_WINDOW) -> float | None:
    if len(series) < window:
        return None
    closes = [float(row["close"]) for row in series[-window:] if row.get("close") is not None]
    if len(closes) < window:
        return None
    return round(sum(closes) / len(closes), 4)


def short_ma_signal(close: float | None, sma_5: float | None, sma_20: float | None) -> dict[str, Any]:
    """Classify short-term timing context without turning it into authority."""
    if close is None or sma_5 is None or sma_20 is None:
        return {
            "status": "unknown",
            "warning": "5DMA/20DMA timing signal unavailable; do not infer short-term confirmation.",
            "price_vs_5dma_pct": None,
            "price_vs_20dma_pct": None,
            "sma_5_vs_20_pct": None,
        }
    price_vs_5 = round(((close - sma_5) / sma_5) * 100.0, 4)
    price_vs_20 = round(((close - sma_20) / sma_20) * 100.0, 4)
    sma_spread = round(((sma_5 - sma_20) / sma_20) * 100.0, 4)
    if close >= sma_5 and sma_5 >= sma_20:
        status = "short_term_confirmed"
        warning = "Short-term tape confirms; still subordinate to band, stop, thesis, and concentration checks."
    elif close < sma_5 and close >= sma_20 and sma_5 >= sma_20:
        status = "constructive_pullback"
        warning = "Normal pullback inside short-term uptrend; watch for reclaim rather than chase."
    elif close < sma_20 and sma_5 >= sma_20:
        status = "momentum_cooling"
        warning = "Price is below 20DMA while 5DMA remains above 20DMA; stage smaller or wait for reclaim."
    elif sma_5 < sma_20:
        status = "short_term_repair_needed"
        warning = "5DMA is below 20DMA; short-term trend needs repair before aggressive deployment."
    else:
        status = "mixed"
        warning = "5DMA/20DMA signal is mixed; use only as a thin timing caution."
    return {
        "status": status,
        "warning": warning,
        "price_vs_5dma_pct": price_vs_5,
        "price_vs_20dma_pct": price_vs_20,
        "sma_5_vs_20_pct": sma_spread,
    }


def classify_relative(change: float | None, threshold: float = 0.10) -> str:
    if change is None:
        return "unknown"
    if change > threshold:
        return "outperforming"
    if change < -threshold:
        return "underperforming"
    return "flat"


def classify_leadership(relative_returns: dict[str, float | None], above_50dma: bool | None) -> str:
    r5 = relative_returns.get("5d")
    r20 = relative_returns.get("20d")
    if r5 is None and r20 is None:
        return "unknown"
    if (r5 is not None and r5 > 0) and (r20 is not None and r20 > 0) and above_50dma is True:
        return "improving_leadership"
    if (r5 is not None and r5 > 0) and above_50dma is True:
        return "improving"
    if (r5 is not None and r5 < 0) and (r20 is not None and r20 < 0):
        return "deteriorating"
    if above_50dma is False:
        return "repair_needed"
    return "mixed"


def fetch_price_history(ticker: str, period: str = HISTORY_PERIOD) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import yfinance as yf  # type: ignore

        hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if hist.empty:
            return [], f"{ticker}: no price history"
        closes = hist.get("Close")
        if closes is None or closes.empty:
            return [], f"{ticker}: close series missing"
        closes = closes.dropna()
        if closes.empty:
            return [], f"{ticker}: close series empty after dropna"
        out = [{"date": idx.strftime("%Y-%m-%d"), "close": round(float(value), 4)} for idx, value in closes.items()]
        return out, None
    except Exception as exc:  # pragma: no cover - live provider behavior varies
        return [], f"{ticker}: {exc}"


def histories_from_provider(fetcher: Callable[[str], tuple[list[dict[str, Any]], str | None]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    for ticker in [SPY_TICKER, *SECTOR_ETFS.keys()]:
        rows, err = fetcher(ticker)
        if err:
            warnings.append(err)
        if rows:
            histories[ticker] = rows
    return histories, warnings


def breadth_sector_map(breadth: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    sectors = (((breadth or {}).get("data") or {}).get("sector_participation") or {}).get("sectors") or []
    out: dict[str, dict[str, Any]] = {}
    for row in sectors:
        if isinstance(row, dict) and row.get("ticker"):
            out[str(row["ticker"]).upper()] = row
    return out


def portfolio_exposure_by_sector(config: dict[str, Any] | None, correlation: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: {"draft_weight_pct": 0.0, "tickers": [], "status": "unrepresented"})
    corr_sectors = (((correlation or {}).get("portfolio_exposure") or {}).get("sectors") or [])
    if corr_sectors:
        for row in corr_sectors:
            if not isinstance(row, dict):
                continue
            sector = normalize_sector(row.get("sector"))
            out[sector] = {
                "draft_weight_pct": float(row.get("draft_weight_pct") or 0),
                "tickers": list(row.get("tickers") or []),
                "status": row.get("status") or "unknown",
                "risk_cap_pct": row.get("risk_cap_pct"),
                "distance_to_cap_pct": row.get("distance_to_cap_pct"),
            }
        return dict(out)
    portfolio = (config or {}).get("portfolio") or {}
    for sleeve in ("core", "tactical", "speculative"):
        for item in portfolio.get(sleeve) or []:
            if not isinstance(item, dict):
                continue
            sector = normalize_sector(item.get("sector"))
            if sector not in set(SECTOR_ETFS.values()):
                continue
            out[sector]["draft_weight_pct"] += float(item.get("weight") or 0)
            out[sector]["tickers"].append(str(item.get("ticker")))
            out[sector]["status"] = "represented"
    return dict(out)


def tracked_candidates_by_sector(config: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    universe = (config or {}).get("tracked_universe") or {}
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ticker, item in universe.items():
        if not isinstance(item, dict):
            continue
        sector = normalize_sector(item.get("sector"))
        out[sector].append({
            "ticker": str(ticker),
            "sector": sector,
            "coverage_tier": item.get("coverage_tier"),
            "coverage_lane": item.get("coverage_lane"),
            "portfolio_role": item.get("portfolio_role"),
            "workflow_state": legacy_state(item, "workflow_state"),
        })
    for sector in out:
        out[sector].sort(key=lambda row: str(row.get("ticker")))
    return dict(out)


def promotion_row_is_pending(row: dict[str, Any]) -> bool:
    """Return True only for names still awaiting a promotion-review decision."""
    judgment = str(row.get("automated_queue_judgment") or "").lower()
    next_action = str(row.get("next_action") or "").lower()
    approved_markers = (
        "approved conditional add",
        "approval recorded",
        "explicit owner promotion granted",
        "owner promotion granted",
        "tier 1 explicit",
    )
    return not any(marker in judgment or marker in next_action for marker in approved_markers)


def parse_promotion_queue(text: str | None) -> dict[str, dict[str, Any]]:
    if not text:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or "---" in line or "Candidate" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 12:
            continue
        ticker = cells[0].upper()
        row = {
            "candidate": ticker,
            "proposed_lane": cells[1],
            "blocking_gate": cells[8],
            "automated_queue_judgment": cells[9],
            "next_action": cells[10],
            "last_reviewed": cells[11],
            "parse_status": "ok",
            "owner_approval_granted": False,
            "watchlist_promotion_allowed": False,
        }
        row["promotion_review_pending"] = promotion_row_is_pending(row)
        rows[ticker] = row
    return rows


def source_warnings(correlation: dict[str, Any] | None, breadth: dict[str, Any] | None, market_state: dict[str, Any] | None) -> list[str]:
    warnings: list[str] = []
    for label, doc in (("sector_correlation_check", correlation), ("breadth_state", breadth), ("market_state", market_state)):
        if not isinstance(doc, dict):
            warnings.append(f"{label} missing or unparsable")
            continue
        if doc.get("status") not in {"ok", None}:
            warnings.append(f"{label} status={doc.get('status')}")
        for warning in doc.get("warnings") or []:
            warnings.append(f"{label}: {warning}")
        source_quality = doc.get("source_quality")
        if isinstance(source_quality, dict) and source_quality.get("trust_level") != "clean":
            warnings.extend(str(x) for x in source_quality.get("issues") or [])
    return warnings


def sector_action(sector: str, leadership: str, exposure: dict[str, Any], candidates: list[dict[str, Any]], promo: list[dict[str, Any]], corr_warnings: list[str]) -> str:
    weight = float(exposure.get("draft_weight_pct") or 0)
    status = str(exposure.get("status") or "")
    if any("correlation" in w.lower() or "cap" in w.lower() for w in corr_warnings) or status in {"near_cap", "at_cap", "over_cap"}:
        return "Review concentration/correlation warning before any owner-gated promotion review; no sizing or deployment authority."
    if weight == 0 and (leadership in {"improving", "improving_leadership"}) and (candidates or promo):
        return "Underexposed improving sector: prepare owner-gated promotion review candidates; no automatic promotion."
    if weight == 0:
        return "Underexposed/unrepresented: monitor for quality candidates and require explicit promotion review before any lane change."
    if promo:
        return "Existing exposure with queued candidates: keep promotion review owner-gated and check risk/sizing before any change."
    return "Maintain review-only monitoring; no canonical mutation or capital action."


def build_board(window: str, fetcher: Callable[[str], tuple[list[dict[str, Any]], str | None]] = fetch_price_history) -> dict[str, Any]:
    breadth = load_json(TMP / "breadth-state.json")
    market_state = load_json(TMP / "market-state.json")
    correlation = load_json(TMP / "sector-correlation-check.json")
    config = load_json(TMP / "portfolio-config.json")
    queue_text = None
    try:
        queue_text = (WORKSPACE / "06. Playbooks" / "Promotion Review Queue.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        pass

    histories, provider_warnings = histories_from_provider(fetcher)
    warnings = provider_warnings + source_warnings(correlation, breadth, market_state)
    errors: list[str] = []
    if SPY_TICKER not in histories:
        errors.append("SPY price history missing; relative strength cannot be computed.")
    sector_history_count = sum(1 for ticker in SECTOR_ETFS if ticker in histories)
    if sector_history_count == 0:
        errors.append("No sector ETF price history available; sector board blocked.")

    breadth_map = breadth_sector_map(breadth)
    exposure_map = portfolio_exposure_by_sector(config, correlation)
    candidate_map = tracked_candidates_by_sector(config)
    promotion_rows = parse_promotion_queue(queue_text)
    correlation_warnings = [str(w.get("reason") or w.get("status") or w) for w in (((correlation or {}).get("portfolio_exposure") or {}).get("correlated_sleeves") or [])]

    spy = histories.get(SPY_TICKER, [])
    sectors: list[dict[str, Any]] = []
    partial = bool(provider_warnings)
    for ticker, label in SECTOR_ETFS.items():
        history = histories.get(ticker, [])
        breadth_row = breadth_map.get(ticker, {})
        if not history:
            partial = True
            sectors.append({
                "ticker": ticker,
                "sector": label,
                "status": "missing_price_data",
                "relative_strength_vs_spy": {"1d": None, "5d": None, "20d": None},
                "short_term_moving_averages": {
                    "sma_5": None,
                    "sma_20": None,
                    "price_vs_5dma_pct": None,
                    "price_vs_20dma_pct": None,
                    "sma_5_vs_20_pct": None,
                    "signal": "unknown",
                    "warning": "Sector price history missing; short-term timing signal unavailable.",
                },
                "above_50dma": breadth_row.get("above_50dma"),
                "portfolio_exposure": exposure_map.get(label, {"draft_weight_pct": 0, "tickers": [], "status": "unrepresented"}),
                "tracked_universe_candidates": candidate_map.get(label, []),
                "promotion_review_status": [],
                "warnings": [f"{ticker} price history missing"],
                "owner_gated_next_review_action": "Blocked until sector price data is available; no promotion or capital action.",
            })
            continue
        relative: dict[str, float | None] = {}
        sector_returns: dict[str, float | None] = {}
        spy_returns: dict[str, float | None] = {}
        for label_lookback, lookback in (("1d", 1), ("5d", 5), ("20d", 20)):
            sret = pct_change(history, lookback)
            pret = pct_change(spy, lookback) if spy else None
            sector_returns[label_lookback] = sret
            spy_returns[label_lookback] = pret
            relative[label_lookback] = round(sret - pret, 4) if sret is not None and pret is not None else None
        close = float(history[-1]["close"])
        sma = compute_sma(history)
        sma_5 = compute_sma(history, 5)
        sma_20 = compute_sma(history, 20)
        ma_signal = short_ma_signal(close, sma_5, sma_20)
        above = breadth_row.get("above_50dma")
        if above is None and sma is not None:
            above = bool(float(history[-1]["close"]) > sma)
        if above is None:
            partial = True
        exposure = exposure_map.get(label, {"draft_weight_pct": 0, "tickers": [], "status": "unrepresented"})
        candidates = candidate_map.get(label, [])
        tickers = {str(c.get("ticker", "")).upper() for c in candidates} | {str(t).upper() for t in exposure.get("tickers") or []}
        promo = [row for ticker_key, row in promotion_rows.items() if ticker_key in tickers]
        sector_corr_warnings = [w for w in correlation_warnings if label.lower() in w.lower() or (label == "Technology" and "ai" in w.lower())]
        leadership = classify_leadership(relative, above)
        sectors.append({
            "ticker": ticker,
            "sector": label,
            "status": "ok" if relative.get("1d") is not None else "degraded",
            "as_of": history[-1].get("date"),
            "close": history[-1].get("close"),
            "relative_strength_vs_spy": relative,
            "sector_returns_pct": sector_returns,
            "spy_returns_pct": spy_returns,
            "relative_labels": {k: classify_relative(v) for k, v in relative.items()},
            "short_term_moving_averages": {
                "sma_5": sma_5,
                "sma_20": sma_20,
                "price_vs_5dma_pct": ma_signal["price_vs_5dma_pct"],
                "price_vs_20dma_pct": ma_signal["price_vs_20dma_pct"],
                "sma_5_vs_20_pct": ma_signal["sma_5_vs_20_pct"],
                "signal": ma_signal["status"],
                "warning": ma_signal["warning"],
            },
            "sma_50": breadth_row.get("sma_50") or sma,
            "above_50dma": above,
            "leadership_status": leadership,
            "portfolio_exposure": exposure,
            "underexposed": float(exposure.get("draft_weight_pct") or 0) == 0,
            "tracked_universe_candidates": candidates,
            "promotion_review_status": promo,
            "warnings": sector_corr_warnings,
            "owner_gated_next_review_action": sector_action(label, leadership, exposure, candidates, promo, sector_corr_warnings),
        })

    status = "blocked" if errors else "degraded" if partial or warnings else "ok"
    improving = [s["sector"] for s in sectors if s.get("leadership_status") in {"improving", "improving_leadership"}]
    underexposed = [s["sector"] for s in sectors if s.get("underexposed")]
    promo_rows = [row for rows in [s.get("promotion_review_status") or [] for s in sectors] for row in rows]
    promo_candidates = sorted({row["candidate"] for row in promo_rows if row.get("promotion_review_pending") is not False})
    approved_promotion_names = sorted({row["candidate"] for row in promo_rows if row.get("promotion_review_pending") is False})

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": status,
        "consumer_posture": "review_only",
        "status_question": QUESTION,
        "authority": authority_false_block(),
        "owner_approval_required_for_capital": True,
        "market_data_as_of": (market_state or {}).get("last_trading_day") or (breadth or {}).get("last_trading_day"),
        "source_artifacts": {
            "breadth_state": "tmp/breadth-state.json",
            "market_state": "tmp/market-state.json",
            "sector_correlation_check": "tmp/sector-correlation-check.json",
            "portfolio_config": "tmp/portfolio-config.json",
            "promotion_review_queue": "06. Playbooks/Promotion Review Queue.md",
        },
        "summary": {
            "sectors_reviewed": len(sectors),
            "sector_etfs_expected": list(SECTOR_ETFS.keys()),
            "sector_etfs_with_price_history": sector_history_count,
            "improving_leadership_sectors": improving,
            "underexposed_sectors": underexposed,
            "promotion_review_candidates": promo_candidates,
            "approved_promotion_names": approved_promotion_names,
            "concentration_warnings": correlation_warnings,
        },
        "sectors": sectors,
        "warnings": warnings,
        "errors": errors,
        "limits": [
            "Review-only board: no canonical mutation, portfolio/deployment mutation, watchlist promotion, sizing/allocation recommendation, trade execution, owner approval inference, or probability/modeling authority.",
            "Sector relative strength is descriptive trailing price context only, not predictive deployment authority.",
            "Sector 5DMA/20DMA fields are thin timing warnings only; they do not override ticker bands, stops, source freshness, thesis, concentration limits, or owner approval gates.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only daily sector expansion board JSON.")
    parser.add_argument("--window", default="post-close", help="Review window label to stamp into the artifact.")
    parser.add_argument("--output", default="tmp/sector-expansion-board.json", help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    board = build_board(args.window)
    output = Path(args.output)
    if not output.is_absolute():
        output = WORKSPACE / output
    atomic_write_json(output, board, indent=2, ensure_ascii=True)
    print(json.dumps({
        "status": board["status"],
        "window": args.window,
        "output": str(output.relative_to(WORKSPACE)).replace("\\", "/"),
        "sectors_reviewed": board["summary"]["sectors_reviewed"],
        "improving_leadership_sectors": board["summary"]["improving_leadership_sectors"],
        "underexposed_sectors": board["summary"]["underexposed_sectors"],
        "promotion_review_candidates": board["summary"]["promotion_review_candidates"],
    }, indent=2))
    return 0 if board["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
