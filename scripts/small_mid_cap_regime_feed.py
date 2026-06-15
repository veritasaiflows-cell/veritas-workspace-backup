#!/usr/bin/env python3
"""Build the WF61 review-only small/mid-cap and diversified fund regime feed.

This feed is an evidence surface only. It compares small-cap, mid-cap,
precious-metals, broad-commodity, and tactical commodity ETF/proxy behavior
against SPY and QQQ, then writes review-only artifacts under tmp/.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUTPUT_PATH = TMP / "small-mid-cap-regime-feed.json"
SUMMARY_PATH = TMP / "small-mid-cap-regime-feed.md"
CURRENT_ANALOG_MATCH = TMP / "current-regime-analog-match.json"
SCHEMA_VERSION = 1
HISTORY_PERIOD = "1y"
BENCHMARKS = ("SPY", "QQQ")
LOOKBACKS = {"5d": 5, "20d": 20, "60d": 60}
SMA_WINDOWS = (20, 50, 200)
ATR_WINDOW = 14
VOL_WINDOW = 20
LIQUIDITY_DOLLAR_VOLUME_WARNING = 25_000_000
MIN_ROWS_FOR_CORE_METRICS = 61
MAX_MARKET_DATA_AGE_DAYS = 5

AUTHORITY_FALSE_FLAGS = [
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "owner_approval_granted",
    "watchlist_promotion_allowed",
    "deployment_state_mutation_allowed",
    "owner_approval_inference_allowed",
    "probability_or_modeling_authority",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
]

UNIVERSE: list[dict[str, str]] = [
    {"ticker": "IWM", "bucket": "small_cap", "label": "Russell 2000 small caps"},
    {"ticker": "SCHA", "bucket": "small_cap", "label": "Schwab U.S. small-cap broad proxy"},
    {"ticker": "IJR", "bucket": "small_cap_quality", "label": "S&P SmallCap 600 quality-biased proxy"},
    {"ticker": "VB", "bucket": "small_cap", "label": "Vanguard small-cap broad proxy"},
    {"ticker": "AVUV", "bucket": "small_cap_value_quality", "label": "Avantis U.S. small-cap value/quality tilt"},
    {"ticker": "VBR", "bucket": "small_cap_value", "label": "Vanguard small-cap value proxy"},
    {"ticker": "IJS", "bucket": "small_cap_value", "label": "S&P SmallCap 600 value proxy"},
    {"ticker": "IJH", "bucket": "mid_cap", "label": "S&P MidCap 400 proxy"},
    {"ticker": "MDY", "bucket": "mid_cap", "label": "S&P MidCap 400 ETF"},
    {"ticker": "VO", "bucket": "mid_cap", "label": "Vanguard mid-cap broad proxy"},
    {"ticker": "SLV", "bucket": "precious_metals", "label": "Silver hard-asset proxy"},
    {"ticker": "GLD", "bucket": "precious_metals", "label": "Gold hard-asset proxy"},
    {"ticker": "PDBC", "bucket": "broad_commodities", "label": "Broad commodity fund"},
    {"ticker": "DBC", "bucket": "broad_commodities", "label": "Broad commodity ETF"},
    {"ticker": "USO", "bucket": "tactical_commodity", "label": "Oil tactical commodity expression"},
    {"ticker": "CPER", "bucket": "tactical_commodity", "label": "Copper tactical commodity expression"},
    {"ticker": "DBA", "bucket": "tactical_commodity", "label": "Agriculture tactical commodity expression"},
    {"ticker": "URA", "bucket": "tactical_commodity", "label": "Uranium tactical commodity expression"},
    {"ticker": "COPX", "bucket": "tactical_commodity", "label": "Copper miners tactical commodity expression"},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def authority_false_block() -> dict[str, bool]:
    return {flag: False for flag in AUTHORITY_FALSE_FLAGS}


def load_scenario_context() -> dict[str, Any]:
    payload = load_json_artifact(CURRENT_ANALOG_MATCH)
    if not isinstance(payload, dict) or payload.get("status") not in {"ok", "warning"}:
        return {
            "status": "unavailable",
            "source_artifact": rel(CURRENT_ANALOG_MATCH),
            "panel": None,
            "note": "Current-regime analog panel unavailable; refresh current_regime_analog_matcher.py for historical scenario context.",
            "authority": {
                "scenario_context_only": True,
                "probability_or_score_allowed": False,
                "capital_action_allowed": False,
                "owner_approval_inference_allowed": False,
            },
        }
    panel = payload.get("scenario_context_panel") if isinstance(payload.get("scenario_context_panel"), dict) else {}
    return {
        "status": payload.get("status"),
        "source_artifact": rel(CURRENT_ANALOG_MATCH),
        "generated_at_utc": payload.get("generated_at_utc"),
        "active_current_tags": panel.get("active_current_tags") or [],
        "primary_analogs": panel.get("primary_analogs") or [],
        "stress_caution_analogs": panel.get("stress_caution_analogs") or [],
        "scenario_observations": panel.get("scenario_observations") or [],
        "authority": {
            "scenario_context_only": True,
            "probability_or_score_allowed": False,
            "capital_action_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    }


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def pct_change(rows: list[dict[str, Any]], lookback: int) -> float | None:
    if len(rows) <= lookback:
        return None
    current = rows[-1].get("close")
    prior = rows[-1 - lookback].get("close")
    if current in (None, 0) or prior in (None, 0):
        return None
    return round(((float(current) - float(prior)) / float(prior)) * 100.0, 4)


def sma(rows: list[dict[str, Any]], window: int) -> float | None:
    if len(rows) < window:
        return None
    closes = [float(row["close"]) for row in rows[-window:] if row.get("close") is not None]
    if len(closes) < window:
        return None
    return round(sum(closes) / len(closes), 4)


def drawdown_from_high(rows: list[dict[str, Any]]) -> float | None:
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    if not closes:
        return None
    high = max(closes)
    if high <= 0:
        return None
    return round(((closes[-1] - high) / high) * 100.0, 4)


def median_dollar_volume(rows: list[dict[str, Any]], window: int = 20) -> float | None:
    values: list[float] = []
    for row in rows[-window:]:
        close = row.get("close")
        volume = row.get("volume")
        if close is None or volume is None:
            continue
        values.append(float(close) * float(volume))
    if not values:
        return None
    return round(statistics.median(values), 2)


def atr_pct(rows: list[dict[str, Any]], window: int = ATR_WINDOW) -> float | None:
    if len(rows) < window + 1:
        return None
    true_ranges: list[float] = []
    for idx in range(len(rows) - window, len(rows)):
        row = rows[idx]
        prev = rows[idx - 1]
        high = row.get("high")
        low = row.get("low")
        close = row.get("close")
        prev_close = prev.get("close")
        if high is None or low is None or close in (None, 0) or prev_close is None:
            continue
        tr = max(float(high) - float(low), abs(float(high) - float(prev_close)), abs(float(low) - float(prev_close)))
        true_ranges.append(tr / float(close) * 100.0)
    if not true_ranges:
        return None
    return round(sum(true_ranges) / len(true_ranges), 4)


def realized_volatility_pct(rows: list[dict[str, Any]], window: int = VOL_WINDOW) -> float | None:
    if len(rows) < window + 1:
        return None
    returns: list[float] = []
    for idx in range(len(rows) - window, len(rows)):
        current = rows[idx].get("close")
        prior = rows[idx - 1].get("close")
        if current in (None, 0) or prior in (None, 0):
            continue
        returns.append((float(current) - float(prior)) / float(prior))
    if len(returns) < 2:
        return None
    return round(statistics.stdev(returns) * math.sqrt(252) * 100.0, 4)


def fetch_price_history(ticker: str, period: str = HISTORY_PERIOD) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import yfinance as yf  # type: ignore

        hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if hist.empty:
            return [], f"{ticker}: no price history"
        closes = hist.get("Close")
        if closes is None or closes.dropna().empty:
            return [], f"{ticker}: close series missing"
        rows: list[dict[str, Any]] = []
        for idx, row in hist.iterrows():
            close = row.get("Close")
            if close is None or math.isnan(float(close)):
                continue
            rows.append({
                "date": idx.strftime("%Y-%m-%d"),
                "close": round(float(close), 4),
                "high": round(float(row.get("High")), 4) if row.get("High") is not None and not math.isnan(float(row.get("High"))) else None,
                "low": round(float(row.get("Low")), 4) if row.get("Low") is not None and not math.isnan(float(row.get("Low"))) else None,
                "volume": int(row.get("Volume")) if row.get("Volume") is not None and not math.isnan(float(row.get("Volume"))) else None,
            })
        return rows, None if rows else f"{ticker}: no usable rows"
    except Exception as exc:  # pragma: no cover - live provider behavior varies
        return [], f"{ticker}: {exc}"


def histories_from_provider(fetcher: Callable[[str], tuple[list[dict[str, Any]], str | None]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    for ticker in [*BENCHMARKS, *[item["ticker"] for item in UNIVERSE]]:
        rows, err = fetcher(ticker)
        if err:
            warnings.append(err)
        if rows:
            histories[ticker] = rows
    return histories, warnings


def relative_strength(rows: list[dict[str, Any]], benchmark_rows: list[dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for label, lookback in LOOKBACKS.items():
        own = pct_change(rows, lookback)
        bench = pct_change(benchmark_rows, lookback)
        out[label] = round(own - bench, 4) if own is not None and bench is not None else None
    return out


def classify_regime(row: dict[str, Any]) -> str:
    if row.get("status") != "ok":
        return "blocked"
    above = row.get("above_dma") or {}
    rs_spy = row.get("relative_strength_vs_spy") or {}
    rs_qqq = row.get("relative_strength_vs_qqq") or {}
    liquidity = row.get("liquidity_warning")
    r5_spy = rs_spy.get("5d")
    r20_spy = rs_spy.get("20d")
    r20_qqq = rs_qqq.get("20d")
    r60_spy = rs_spy.get("60d")
    if liquidity and row.get("bucket") == "tactical_commodity":
        return "blocked"
    if above.get("50dma") is True and above.get("200dma") is True and (r20_spy or 0) > 0 and (r20_qqq or 0) > 0:
        return "improving"
    if above.get("200dma") is False or ((r20_spy is not None and r20_spy < 0) and (r60_spy is not None and r60_spy < 0)):
        return "deteriorating"
    if above.get("50dma") is True or (r5_spy is not None and r5_spy > 0):
        return "neutral"
    return "deteriorating"


def owner_gated_recommendation(row: dict[str, Any]) -> str:
    regime = row.get("regime_label")
    bucket = row.get("bucket")
    if regime == "blocked":
        return "reject-bench until data/liquidity repairs; no portfolio action."
    if regime == "improving" and bucket in {"small_cap", "small_cap_quality", "small_cap_value_quality", "small_cap_value", "mid_cap"}:
        return "research packet candidate; compare against breadth, sector board, and risk budget before any owner-gated proposal."
    if regime == "improving" and bucket in {"precious_metals", "broad_commodities"}:
        return "proposal-candidate review only; require macro/correlation/risk packet and explicit owner approval before any action."
    if regime == "improving":
        return "tactical research packet only; high-volatility/correlation warnings required before any owner-gated proposal."
    if regime == "neutral":
        return "monitor; wait for sustained relative-strength confirmation before research-packet escalation."
    return "reject-bench for now; trend/relative-strength posture is not supportive."


def build_proxy_row(meta: dict[str, str], histories: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker = meta["ticker"]
    rows = histories.get(ticker, [])
    if not rows:
        return {
            **meta,
            "status": "missing_price_data",
            "as_of": None,
            "close": None,
            "relative_strength_vs_spy": {k: None for k in LOOKBACKS},
            "relative_strength_vs_qqq": {k: None for k in LOOKBACKS},
            "above_dma": {f"{w}dma": None for w in SMA_WINDOWS},
            "drawdown_from_52w_high_pct": None,
            "median_20d_dollar_volume": None,
            "liquidity_warning": True,
            "atr_14d_pct": None,
            "realized_volatility_20d_annualized_pct": None,
            "regime_label": "blocked",
            "owner_gated_recommendation": "Blocked until price history is available; no portfolio action.",
            "warnings": [f"{ticker} price history missing"],
        }

    close = rows[-1].get("close")
    above_dma: dict[str, bool | None] = {}
    for window in SMA_WINDOWS:
        avg = sma(rows, window)
        above_dma[f"{window}dma"] = bool(close is not None and avg is not None and float(close) > avg) if avg is not None else None

    med_dollar_volume = median_dollar_volume(rows)
    liquidity_warning = med_dollar_volume is None or med_dollar_volume < LIQUIDITY_DOLLAR_VOLUME_WARNING
    warnings: list[str] = []
    status = "ok"
    if len(rows) < MIN_ROWS_FOR_CORE_METRICS:
        status = "degraded"
        warnings.append(f"{ticker} has only {len(rows)} usable rows; 60d relative strength may be unavailable.")
    if liquidity_warning:
        warnings.append(f"{ticker} median 20d dollar volume below ${LIQUIDITY_DOLLAR_VOLUME_WARNING:,} or unavailable.")
    if meta["bucket"] == "tactical_commodity":
        warnings.append("Tactical commodity expression: require explicit volatility, correlation, and macro review before any owner-gated proposal.")

    row = {
        **meta,
        "status": status,
        "as_of": rows[-1].get("date"),
        "close": close,
        "returns_pct": {label: pct_change(rows, lookback) for label, lookback in LOOKBACKS.items()},
        "relative_strength_vs_spy": relative_strength(rows, histories.get("SPY", [])),
        "relative_strength_vs_qqq": relative_strength(rows, histories.get("QQQ", [])),
        "above_dma": above_dma,
        "sma": {f"{window}dma": sma(rows, window) for window in SMA_WINDOWS},
        "drawdown_from_52w_high_pct": drawdown_from_high(rows),
        "median_20d_dollar_volume": med_dollar_volume,
        "liquidity_warning": liquidity_warning,
        "atr_14d_pct": atr_pct(rows),
        "realized_volatility_20d_annualized_pct": realized_volatility_pct(rows),
        "warnings": warnings,
    }
    row["regime_label"] = classify_regime(row)
    row["owner_gated_recommendation"] = owner_gated_recommendation(row)
    return row


def bucket_summary(proxies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in proxies:
        bucket = str(row.get("bucket"))
        item = out.setdefault(bucket, {"reviewed": 0, "improving": [], "neutral": [], "deteriorating": [], "blocked": [], "liquidity_warnings": []})
        item["reviewed"] += 1
        regime = row.get("regime_label")
        if regime in {"improving", "neutral", "deteriorating", "blocked"}:
            item[regime].append(row.get("ticker"))
        if row.get("liquidity_warning"):
            item["liquidity_warnings"].append(row.get("ticker"))
    return out


def build_feed(window: str, fetcher: Callable[[str], tuple[list[dict[str, Any]], str | None]] = fetch_price_history) -> dict[str, Any]:
    histories, provider_warnings = histories_from_provider(fetcher)
    errors: list[str] = []
    for benchmark in BENCHMARKS:
        if benchmark not in histories:
            errors.append(f"{benchmark} benchmark price history missing; relative strength cannot be computed.")
        elif len(histories[benchmark]) < MIN_ROWS_FOR_CORE_METRICS:
            errors.append(f"{benchmark} benchmark has only {len(histories[benchmark])} usable rows; relative strength contract is insufficient.")

    proxies = [build_proxy_row(meta, histories) for meta in UNIVERSE]
    market_data_as_of = max((row.get("as_of") or "") for row in proxies) or None
    market_data_dt = parse_date(market_data_as_of)
    generated_dt = datetime.now(timezone.utc)
    market_data_age_days = None
    stale_market_data = False
    freshness_warnings: list[str] = []
    if market_data_dt is None:
        stale_market_data = True
        freshness_warnings.append("market_data_as_of missing or unparseable; feed degraded until fresh market data is available.")
    else:
        market_data_age_days = round((generated_dt.date() - market_data_dt.date()).days, 2)
        if market_data_age_days > MAX_MARKET_DATA_AGE_DAYS:
            stale_market_data = True
            freshness_warnings.append(f"market data stale: market_data_as_of={market_data_as_of} age_days={market_data_age_days} max={MAX_MARKET_DATA_AGE_DAYS}.")
    missing_count = sum(1 for row in proxies if row.get("status") == "missing_price_data")
    degraded_count = sum(1 for row in proxies if row.get("status") == "degraded")
    partial = bool(provider_warnings or freshness_warnings or missing_count or degraded_count)
    status = "blocked" if errors else "degraded" if partial else "ok"
    improving = [row["ticker"] for row in proxies if row.get("regime_label") == "improving"]
    research_packet_candidates = [
        row["ticker"] for row in proxies
        if row.get("regime_label") == "improving" and not row.get("liquidity_warning")
    ]
    scenario_context = load_scenario_context()

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": status,
        "consumer_posture": "review_only",
        "workflow": "WF61 - Small Mid Cap Regime Feed and Candidate Sleeve",
        "authority": authority_false_block(),
        "owner_approval_required_for_any_portfolio_action": True,
        "source": "yfinance daily adjusted price history via script fetcher",
        "source_artifacts": [
            {"path": rel(CURRENT_ANALOG_MATCH), "role": "review-only historical scenario context", "exists": CURRENT_ANALOG_MATCH.exists(), "status": scenario_context.get("status")},
        ],
        "benchmark_tickers": list(BENCHMARKS),
        "lookbacks": list(LOOKBACKS.keys()),
        "market_data_as_of": market_data_as_of,
        "market_data_age_days": market_data_age_days,
        "market_data_fresh_enough": not stale_market_data,
        "max_market_data_age_days": MAX_MARKET_DATA_AGE_DAYS,
        "summary": {
            "proxies_expected": len(UNIVERSE),
            "proxies_with_price_history": len(UNIVERSE) - missing_count,
            "missing_price_history_count": missing_count,
            "degraded_proxy_count": degraded_count,
            "improving_candidates": improving,
            "research_packet_candidates_review_only": research_packet_candidates,
            "bucket_summary": bucket_summary(proxies),
        },
        "scenario_context_panel": scenario_context,
        "proxies": proxies,
        "warnings": provider_warnings + freshness_warnings + [warning for row in proxies for warning in row.get("warnings", [])],
        "errors": errors,
        "limits": [
            "Review-only feed: no canonical mutation, portfolio mutation, owner approval inference, sizing/allocation recommendation, trade execution, watchlist promotion, or model/probability authority.",
            "Relative strength, moving-average posture, drawdown, liquidity, ATR, and volatility are descriptive trailing-market evidence only, not predictive deployment authority.",
            "Commodity probes require explicit macro, correlation, volatility, and risk-budget review before any owner-gated proposal.",
            "Small/mid-cap ETF improvement can justify research-packet review, not automatic sleeve creation or capital action.",
            "Historical analog context is scenario discipline only; it is not a probability model, score, ranking, sizing recommendation, or approval signal.",
        ],
    }


def render_markdown(feed: dict[str, Any]) -> str:
    lines = [
        "# Small/Mid-Cap Regime Feed - Review Only",
        "",
        f"- Generated: `{feed.get('generated_at_utc')}`",
        f"- Window: `{feed.get('window')}`",
        f"- Status: **{feed.get('status')}**",
        f"- Market data as of: `{feed.get('market_data_as_of')}`",
        "- Authority: review-only; no portfolio mutation, sizing/allocation recommendation, trade execution, watchlist promotion, or owner approval inference.",
        "",
        "## Summary",
        "",
        f"- Proxies with price history: {feed.get('summary', {}).get('proxies_with_price_history')} / {feed.get('summary', {}).get('proxies_expected')}",
        f"- Improving candidates: {', '.join(feed.get('summary', {}).get('improving_candidates') or []) or 'none'}",
        f"- Review-only research packet candidates: {', '.join(feed.get('summary', {}).get('research_packet_candidates_review_only') or []) or 'none'}",
        "",
        "## Scenario context",
        "",
    ]
    scenario = feed.get("scenario_context_panel") if isinstance(feed.get("scenario_context_panel"), dict) else {}
    if scenario.get("status") in {"ok", "warning"}:
        primary = scenario.get("primary_analogs") if isinstance(scenario.get("primary_analogs"), list) else []
        lines.append(f"- Source: `{scenario.get('source_artifact')}`")
        lines.append(f"- Active tags: {', '.join(scenario.get('active_current_tags') or []) or 'none'}")
        lines.append(f"- Primary analogs: {', '.join(str(row.get('label')) for row in primary[:4] if isinstance(row, dict)) or 'none'}")
    else:
        lines.append(f"- {scenario.get('note') or 'Scenario context unavailable.'}")
    lines.extend([
        "",
        "## Proxy table",
        "",
        "| Ticker | Bucket | As of | Close | Regime | RS vs SPY 5/20/60d | RS vs QQQ 5/20/60d | 20/50/200DMA | DD from 52w high | Liquidity warning | Review-only next action |",
        "|---|---|---:|---:|---|---:|---:|---|---:|---|---|",
    ])
    for row in feed.get("proxies") or []:
        spy = row.get("relative_strength_vs_spy") or {}
        qqq = row.get("relative_strength_vs_qqq") or {}
        above = row.get("above_dma") or {}
        lines.append(
            "| {ticker} | {bucket} | {as_of} | {close} | {regime} | {spy5}/{spy20}/{spy60} | {qqq5}/{qqq20}/{qqq60} | {a20}/{a50}/{a200} | {dd} | {liq} | {action} |".format(
                ticker=row.get("ticker"),
                bucket=row.get("bucket"),
                as_of=row.get("as_of") or "n/a",
                close=row.get("close") if row.get("close") is not None else "n/a",
                regime=row.get("regime_label"),
                spy5=spy.get("5d"), spy20=spy.get("20d"), spy60=spy.get("60d"),
                qqq5=qqq.get("5d"), qqq20=qqq.get("20d"), qqq60=qqq.get("60d"),
                a20=above.get("20dma"), a50=above.get("50dma"), a200=above.get("200dma"),
                dd=row.get("drawdown_from_52w_high_pct"),
                liq="yes" if row.get("liquidity_warning") else "no",
                action=str(row.get("owner_gated_recommendation") or "").replace("|", "/"),
            )
        )
    if feed.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in feed.get("warnings") or []:
            lines.append(f"- {warning}")
    if feed.get("errors"):
        lines.extend(["", "## Errors", ""])
        for error in feed.get("errors") or []:
            lines.append(f"- {error}")
    lines.extend(["", "## Limits", ""])
    for limit in feed.get("limits") or []:
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF61 review-only small/mid-cap and diversified fund regime feed.")
    parser.add_argument("--window", default="post-close", help="Review window label; defaults to post-close.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Output JSON path.")
    parser.add_argument("--markdown-output", type=Path, default=SUMMARY_PATH, help="Markdown summary path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown summary generation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    feed = build_feed(args.window)
    output = args.output if args.output.is_absolute() else WORKSPACE / args.output
    atomic_write_json(output, feed, indent=2, ensure_ascii=True)
    markdown_output = None
    if not args.no_markdown:
        markdown_output = args.markdown_output if args.markdown_output.is_absolute() else WORKSPACE / args.markdown_output
        atomic_write_text(markdown_output, render_markdown(feed), encoding="utf-8")
    print(json.dumps({
        "status": feed["status"],
        "window": args.window,
        "output": rel(output),
        "markdown_output": rel(markdown_output) if markdown_output else None,
        "proxies_reviewed": feed["summary"]["proxies_expected"],
        "improving_candidates": feed["summary"]["improving_candidates"],
        "research_packet_candidates_review_only": feed["summary"]["research_packet_candidates_review_only"],
    }, indent=2))
    return 0 if feed["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
