#!/usr/bin/env python3
"""Build a review-only small/mid-cap candidate pass for WF78 scaleout.

This pass prepares candidates for a future ticker-universe migration batch. It
does not import tickers, mutate finance canon, promote tiers, approve capital,
or authorize trading. The thesis filter is explicit: rate stabilization can
benefit liquid small/mid-cap operating companies in rate-sensitive groups.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

try:
    import yfinance as yf
except Exception:  # pragma: no cover - validated at runtime
    yf = None

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CANONICAL_DB = TMP / "canonical-finance-data-plane.sqlite"
WF61_FEED = TMP / "small-mid-cap-regime-feed.json"
CURRENT_ANALOG_MATCH = TMP / "current-regime-analog-match.json"
OUT_JSON = TMP / "wf78-small-mid-cap-scaleout-candidate-pass.json"
OUT_MD = TMP / "wf78-small-mid-cap-scaleout-candidate-pass.md"

SCHEMA = "veritas.wf78_small_mid_cap_scaleout_candidate_pass.v1"
HISTORY_PERIOD = "1y"
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MAX_MARKET_DATA_AGE_DAYS = 5

AUTHORITY: dict[str, bool] = {
    "report_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_FLAGS = {
    key for key, value in AUTHORITY.items() if value is False
}


CANDIDATE_UNIVERSE: list[dict[str, Any]] = [
    # Regional banks / credit-sensitive financials.
    {"ticker": "WAL", "bucket": "regional_bank", "rate_thesis_weight": 5, "thesis": "Deposit-cost relief, CRE fear normalization, and credit-spread stabilization."},
    {"ticker": "ZION", "bucket": "regional_bank", "rate_thesis_weight": 5, "thesis": "High sensitivity to rate/funding pressure; beneficiary if deposit beta and credit fears ease."},
    {"ticker": "KEY", "bucket": "regional_bank", "rate_thesis_weight": 5, "thesis": "Rate-stability and curve normalization candidate; requires credit/CRE guardrails."},
    {"ticker": "FHN", "bucket": "regional_bank", "rate_thesis_weight": 4, "thesis": "Regional-bank rerating candidate if funding pressure and credit marks stabilize."},
    {"ticker": "PNFP", "bucket": "regional_bank", "rate_thesis_weight": 4, "thesis": "Quality regional bank with rate-stability and loan-growth optionality."},
    {"ticker": "UMBF", "bucket": "regional_bank", "rate_thesis_weight": 4, "thesis": "Regional bank with funding-cost and credit-cycle sensitivity."},
    {"ticker": "BPOP", "bucket": "regional_bank", "rate_thesis_weight": 4, "thesis": "Regional financial with margin and credit-cycle sensitivity."},
    {"ticker": "FNB", "bucket": "regional_bank", "rate_thesis_weight": 4, "thesis": "Smaller bank beneficiary if funding-cost pressure cools."},
    {"ticker": "ONB", "bucket": "regional_bank", "rate_thesis_weight": 4, "thesis": "Smaller bank with rate/funding sensitivity; needs credit-quality review."},
    # REITs and real-asset yield equities.
    {"ticker": "REXR", "bucket": "reit_industrial", "rate_thesis_weight": 4, "thesis": "Industrial REIT multiple can recover if rates stabilize and cap-rate fears ease."},
    {"ticker": "EPRT", "bucket": "reit_net_lease", "rate_thesis_weight": 4, "thesis": "Net-lease REIT valuation support if long rates stop rising."},
    {"ticker": "STAG", "bucket": "reit_industrial", "rate_thesis_weight": 4, "thesis": "Industrial REIT with rate-sensitive valuation and income appeal."},
    {"ticker": "HIW", "bucket": "reit_office", "rate_thesis_weight": 3, "thesis": "Office REIT rebound candidate only if rates stabilize; high structural risk."},
    {"ticker": "MAC", "bucket": "reit_retail", "rate_thesis_weight": 3, "thesis": "High-beta REIT rerating candidate; requires leverage and tenant-risk review."},
    {"ticker": "COLD", "bucket": "reit_logistics", "rate_thesis_weight": 3, "thesis": "Specialty logistics REIT with rate-sensitive valuation; operational proof required."},
    # Housing / building products.
    {"ticker": "MTH", "bucket": "homebuilder", "rate_thesis_weight": 5, "thesis": "Mortgage-rate stabilization can support orders, affordability, and builder margins."},
    {"ticker": "KBH", "bucket": "homebuilder", "rate_thesis_weight": 5, "thesis": "Rate-sensitive entry-level/move-up housing demand candidate."},
    {"ticker": "TMHC", "bucket": "homebuilder", "rate_thesis_weight": 5, "thesis": "Builder with operating leverage to mortgage-rate stabilization."},
    {"ticker": "MHO", "bucket": "homebuilder", "rate_thesis_weight": 4, "thesis": "Smaller homebuilder with high sensitivity to mortgage-rate relief."},
    {"ticker": "CCS", "bucket": "homebuilder", "rate_thesis_weight": 4, "thesis": "High-beta housing demand beneficiary if rates stabilize."},
    {"ticker": "SKY", "bucket": "housing_products", "rate_thesis_weight": 4, "thesis": "Affordable-housing/manufactured-housing beneficiary if financing pressure eases."},
    {"ticker": "TREX", "bucket": "building_products", "rate_thesis_weight": 3, "thesis": "Repair/remodel and housing turnover candidate; needs demand proof."},
    # Small/mid industrials and distributors.
    {"ticker": "ATKR", "bucket": "industrial_cyclical", "rate_thesis_weight": 3, "thesis": "Cyclical industrial/building-products candidate if capex and construction sentiment improve."},
    {"ticker": "WCC", "bucket": "industrial_distributor", "rate_thesis_weight": 3, "thesis": "Distributor with construction/electrical-cycle leverage and valuation sensitivity."},
    {"ticker": "GATX", "bucket": "industrial_finance", "rate_thesis_weight": 3, "thesis": "Leasing/industrial finance candidate with rate and freight-cycle sensitivity."},
    {"ticker": "FLS", "bucket": "industrial_cyclical", "rate_thesis_weight": 3, "thesis": "Industrial orders/capex candidate; rate stability can help cyclical appetite."},
    {"ticker": "HRI", "bucket": "industrial_rental", "rate_thesis_weight": 3, "thesis": "Equipment rental candidate tied to construction and capex conditions."},
    {"ticker": "ENS", "bucket": "industrial_components", "rate_thesis_weight": 2, "thesis": "Industrial/battery components candidate; rate stability helps cyclicals but thesis is less direct."},
    {"ticker": "ROAD", "bucket": "infrastructure_services", "rate_thesis_weight": 2, "thesis": "Infrastructure contractor; rate thesis secondary to project backlog and margins."},
    {"ticker": "STRL", "bucket": "infrastructure_services", "rate_thesis_weight": 2, "thesis": "Infrastructure/industrial services growth; less pure rate-stability exposure."},
    # Consumer finance / durable spending.
    {"ticker": "CROX", "bucket": "consumer_discretionary", "rate_thesis_weight": 2, "thesis": "Discretionary rerating candidate if risk appetite broadens; debt/refi review needed."},
    {"ticker": "WH", "bucket": "travel_lodging", "rate_thesis_weight": 2, "thesis": "Franchise lodging cyclicality; rate thesis indirect through risk appetite."},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
    except Exception:
        return None
    if not math.isfinite(result):
        return None
    return result


def pct_change(values: list[float], lookback: int) -> float | None:
    if len(values) <= lookback:
        return None
    current = values[-1]
    prior = values[-1 - lookback]
    if prior == 0:
        return None
    return round((current - prior) / prior * 100.0, 4)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def cap_bucket(market_cap: float | None) -> str:
    if market_cap is None:
        return "unknown"
    if market_cap < 2_000_000_000:
        return "micro_or_lower_small"
    if market_cap < 5_000_000_000:
        return "small_cap"
    if market_cap < 10_000_000_000:
        return "lower_mid_cap"
    if market_cap < 20_000_000_000:
        return "mid_cap"
    return "above_target_cap"


def active_tickers() -> set[str]:
    if not CANONICAL_DB.exists():
        return set()
    uri = CANONICAL_DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT ticker FROM security_master WHERE active=1").fetchall()
    return {str(row["ticker"]).upper() for row in rows}


def history_rows(ticker: str) -> list[dict[str, Any]]:
    if yf is None:
        return []
    hist = yf.Ticker(ticker).history(period=HISTORY_PERIOD, auto_adjust=False)
    rows: list[dict[str, Any]] = []
    if hist is None or hist.empty:
        return rows
    for idx, row in hist.iterrows():
        close = safe_float(row.get("Close"))
        volume = safe_float(row.get("Volume"))
        if close is None:
            continue
        date = getattr(idx, "date", lambda: idx)()
        rows.append({"date": str(date), "close": close, "volume": volume})
    return rows


def fast_info(ticker: str) -> dict[str, Any]:
    if yf is None:
        return {}


def scenario_context_panel() -> dict[str, Any]:
    payload = load_json_artifact(CURRENT_ANALOG_MATCH)
    if not isinstance(payload, dict) or payload.get("status") not in {"ok", "warning"}:
        return {
            "status": "unavailable",
            "source_artifact": rel(CURRENT_ANALOG_MATCH),
            "note": "Current-regime analog scenario panel unavailable; candidate review remains based on live proxy and ticker evidence only.",
            "authority": {
                "scenario_context_only": True,
                "probability_or_score_allowed": False,
                "deployment_ranking_allowed": False,
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
            "deployment_ranking_allowed": False,
            "capital_action_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    }
    try:
        t = yf.Ticker(ticker)
        info = {}
        try:
            fi = t.fast_info
            for key in ("market_cap", "last_price", "currency"):
                try:
                    info[key] = fi.get(key) if hasattr(fi, "get") else getattr(fi, key, None)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            raw = t.get_info()
            if isinstance(raw, dict):
                for key in ("shortName", "longName", "sector", "industry", "marketCap", "quoteType"):
                    info[key] = raw.get(key, info.get(key))
        except Exception:
            pass
        return info
    except Exception:
        return {}


def benchmark_returns(tickers: tuple[str, ...] = ("SPY", "IWM")) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for ticker in tickers:
        rows = history_rows(ticker)
        closes = [float(row["close"]) for row in rows if row.get("close") is not None]
        result[ticker] = {
            "5d": pct_change(closes, 5),
            "20d": pct_change(closes, 20),
            "60d": pct_change(closes, 60),
        }
    return result


def score_candidate(candidate: dict[str, Any], metrics: dict[str, Any]) -> tuple[float, list[str], list[str], str]:
    score = 0.0
    positives: list[str] = []
    warnings: list[str] = []

    bucket = metrics.get("cap_bucket")
    if bucket in {"small_cap", "lower_mid_cap"}:
        score += 20
        positives.append(f"target cap bucket {bucket}")
    elif bucket == "mid_cap":
        score += 14
        positives.append("mid-cap bucket")
    elif bucket == "micro_or_lower_small":
        score += 5
        warnings.append("below $2B; likely too small for first scalable batch")
    else:
        score -= 8
        warnings.append("above target cap or market cap unavailable")

    median_dollar_volume = safe_float(metrics.get("median_20d_dollar_volume"))
    if median_dollar_volume is not None and median_dollar_volume >= MIN_MEDIAN_DOLLAR_VOLUME:
        score += 15
        positives.append("liquidity above floor")
    else:
        score -= 20
        warnings.append("liquidity below floor or unavailable")

    above_dma = metrics.get("above_dma") or {}
    if above_dma.get("50dma"):
        score += 8
        positives.append("above 50DMA")
    else:
        warnings.append("not above 50DMA")
    if above_dma.get("200dma"):
        score += 10
        positives.append("above 200DMA")
    else:
        score -= 8
        warnings.append("not above 200DMA")

    returns = metrics.get("returns_pct") or {}
    for key, weight in (("20d", 6), ("60d", 8)):
        value = safe_float(returns.get(key))
        if value is not None and value > 0:
            score += weight
            positives.append(f"{key} positive")
        elif value is not None and value < -8:
            score -= weight
            warnings.append(f"{key} weak")

    rel_spy = metrics.get("relative_strength_vs_spy") or {}
    rel_iwm = metrics.get("relative_strength_vs_iwm") or {}
    if safe_float(rel_spy.get("20d")) is not None and rel_spy["20d"] > 0:
        score += 6
        positives.append("20d relative strength vs SPY positive")
    if safe_float(rel_iwm.get("20d")) is not None and rel_iwm["20d"] > 0:
        score += 6
        positives.append("20d relative strength vs IWM positive")

    rate_weight = safe_float(candidate.get("rate_thesis_weight")) or 0
    score += rate_weight * 5
    if rate_weight >= 4:
        positives.append("direct rate-stabilization thesis")
    elif rate_weight <= 2:
        warnings.append("rate thesis is indirect")

    drawdown = safe_float(metrics.get("drawdown_from_52w_high_pct"))
    if drawdown is not None and drawdown < -35:
        score -= 10
        warnings.append("deep drawdown; potential impairment or broken trend")

    if metrics.get("status") != "ok":
        score -= 30
        warnings.append("market data unavailable")

    if score >= 70 and median_dollar_volume and median_dollar_volume >= MIN_MEDIAN_DOLLAR_VOLUME:
        route = "migration_candidate"
    elif score >= 55:
        route = "watchlist_candidate"
    else:
        route = "hold_or_reject"

    return round(score, 2), positives[:8], warnings[:8], route


def build_candidate(candidate: dict[str, Any], active: set[str], bench: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    ticker = str(candidate["ticker"]).upper()
    excluded = ticker in active
    info = fast_info(ticker)
    if not isinstance(info, dict):
        info = {}
    rows = history_rows(ticker)
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    volumes = [float(row["volume"]) for row in rows if row.get("volume") is not None and row.get("close") is not None]
    dollar_volumes = [float(row["close"]) * float(row["volume"]) for row in rows[-20:] if row.get("volume") is not None]

    market_cap = safe_float(info.get("market_cap") or info.get("marketCap"))
    current_close = closes[-1] if closes else None
    sma20 = mean(closes[-20:]) if len(closes) >= 20 else None
    sma50 = mean(closes[-50:]) if len(closes) >= 50 else None
    sma200 = mean(closes[-200:]) if len(closes) >= 200 else None
    high = max(closes) if closes else None
    drawdown = round((current_close - high) / high * 100.0, 4) if current_close and high else None
    returns = {
        "5d": pct_change(closes, 5),
        "20d": pct_change(closes, 20),
        "60d": pct_change(closes, 60),
    }

    def relative(benchmark: str, key: str) -> float | None:
        value = safe_float(returns.get(key))
        b = safe_float(bench.get(benchmark, {}).get(key))
        if value is None or b is None:
            return None
        return round(value - b, 4)

    metrics: dict[str, Any] = {
        "status": "ok" if closes else "missing_price_history",
        "as_of": rows[-1]["date"] if rows else None,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": market_cap,
        "market_cap_b": round(market_cap / 1_000_000_000, 2) if market_cap else None,
        "cap_bucket": cap_bucket(market_cap),
        "close": round(current_close, 4) if current_close else None,
        "median_20d_dollar_volume": round(median(dollar_volumes) or 0, 2) if dollar_volumes else None,
        "returns_pct": returns,
        "relative_strength_vs_spy": {key: relative("SPY", key) for key in ("5d", "20d", "60d")},
        "relative_strength_vs_iwm": {key: relative("IWM", key) for key in ("5d", "20d", "60d")},
        "sma": {
            "20dma": round(sma20, 4) if sma20 else None,
            "50dma": round(sma50, 4) if sma50 else None,
            "200dma": round(sma200, 4) if sma200 else None,
        },
        "above_dma": {
            "20dma": bool(current_close and sma20 and current_close > sma20),
            "50dma": bool(current_close and sma50 and current_close > sma50),
            "200dma": bool(current_close and sma200 and current_close > sma200),
        },
        "drawdown_from_52w_high_pct": drawdown,
    }
    score, positives, warnings, route = score_candidate(candidate, metrics)
    if excluded:
        route = "excluded_existing_universe"
        warnings.append("already active in canonical finance data plane")
    return {
        "ticker": ticker,
        "bucket": candidate["bucket"],
        "rate_stabilization_thesis": candidate["thesis"],
        "rate_thesis_weight": candidate["rate_thesis_weight"],
        "score": score,
        "route": route,
        "excluded_existing_universe": excluded,
        "positive_factors": positives,
        "warnings": warnings,
        "metrics": metrics,
        "migration_stub": {
            "ticker": ticker,
            "name": metrics["name"],
            "instrument_type": "operating_company",
            "sector": metrics["sector"],
            "industry": metrics["industry"],
            "tier": "C",
            "monitoring_role": "small_mid_rate_stabilization_candidate",
            "universe_scope": "wf78_next_batch_candidate",
            "decision_grade_eligible": False,
            "production_answer_path_member": False,
            "thin_monitor_row": True,
            "source_open_required": True,
            "promotion_required_before_action": True,
        },
    }


def validate(payload: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})

    authority = payload.get("authority") or {}
    for key in REQUIRED_FALSE_FLAGS:
        add(f"authority_false_{key}", authority.get(key) is False, authority.get(key))
    add("report_only_true", authority.get("report_only") is True, authority.get("report_only"))

    candidates = payload.get("candidates") or []
    migration = [row for row in candidates if row.get("route") == "migration_candidate"]
    fresh_failures: list[str] = []
    today = date.today()
    for row in migration:
        as_of = ((row.get("metrics") or {}).get("as_of"))
        try:
            age_days = (today - datetime.strptime(str(as_of), "%Y-%m-%d").date()).days
        except Exception:
            fresh_failures.append(str(row.get("ticker")))
            continue
        if age_days > MAX_MARKET_DATA_AGE_DAYS:
            fresh_failures.append(str(row.get("ticker")))
    add("candidate_rows_present", len(candidates) >= 20, len(candidates))
    add("migration_candidates_present", len(migration) >= 5, len(migration), "warning")
    add("existing_universe_excluded", all(not row.get("excluded_existing_universe") for row in migration), [row.get("ticker") for row in migration if row.get("excluded_existing_universe")])
    add("liquidity_floor_for_migration", all((row.get("metrics") or {}).get("median_20d_dollar_volume", 0) >= MIN_MEDIAN_DOLLAR_VOLUME for row in migration), [row.get("ticker") for row in migration if ((row.get("metrics") or {}).get("median_20d_dollar_volume") or 0) < MIN_MEDIAN_DOLLAR_VOLUME])
    add("market_data_fresh_for_migration", not fresh_failures, fresh_failures)
    add("no_import_side_effect", payload.get("migration_ready") is True and payload.get("import_executed") is False, {"migration_ready": payload.get("migration_ready"), "import_executed": payload.get("import_executed")})
    return checks


def markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# WF78 Small/Mid-Cap Scaleout Candidate Pass",
        "",
        f"- Generated: `{payload['generated_at_utc']}`",
        f"- Status: `{payload['status']}`",
        f"- Thesis: {payload['thesis']}",
        f"- Candidates reviewed: `{summary['candidates_reviewed']}`",
        f"- Migration candidates: `{summary['migration_candidate_count']}`",
        f"- Watchlist candidates: `{summary['watchlist_candidate_count']}`",
        f"- Existing universe exclusions: `{summary['existing_universe_exclusion_count']}`",
        "",
        "## Scenario Context",
        "",
    ]
    scenario = payload.get("scenario_context_panel") if isinstance(payload.get("scenario_context_panel"), dict) else {}
    if scenario.get("status") in {"ok", "warning"}:
        primary = scenario.get("primary_analogs") if isinstance(scenario.get("primary_analogs"), list) else []
        stress = scenario.get("stress_caution_analogs") if isinstance(scenario.get("stress_caution_analogs"), list) else []
        lines.append(f"- Source: `{scenario.get('source_artifact')}`")
        lines.append(f"- Primary analogs: {', '.join(str(row.get('label')) for row in primary[:4] if isinstance(row, dict)) or 'none'}")
        lines.append(f"- Stress/caution analogs: {', '.join(str(row.get('label')) for row in stress[:3] if isinstance(row, dict)) or 'none'}")
    else:
        lines.append(f"- {scenario.get('note') or 'Scenario context unavailable.'}")
    lines.extend([
        "",
        "## Migration Candidates",
        "",
        "| Ticker | Route | Score | Cap | Bucket | 20d vs SPY | 20d vs IWM | Thesis |",
        "|---|---|---:|---:|---|---:|---:|---|",
    ])
    for row in payload["top_migration_candidates"]:
        m = row["metrics"]
        lines.append(
            f"| {row['ticker']} | {row['route']} | {row['score']} | "
            f"{m.get('market_cap_b') or 'n/a'}B | {row['bucket']} | "
            f"{(m.get('relative_strength_vs_spy') or {}).get('20d')} | "
            f"{(m.get('relative_strength_vs_iwm') or {}).get('20d')} | "
            f"{row['rate_stabilization_thesis']} |"
        )
    lines.extend([
        "",
        "## Migration Contract",
        "",
        "- Review-only candidate packet for WF78 next-batch planning.",
        "- Proposed rows are thin-monitor `operating_company` stubs with `source_open_required=true`.",
        "- No ticker import, no tier promotion, no SQL/canon expansion, no portfolio mutation, no capital approval, and no trade/order authority.",
        "",
        "## Required Next Gates",
        "",
        "1. Provider/runtime proof for the exact selected candidate set.",
        "2. Official source registry and company IR/source-open capture.",
        "3. A/B no-regression proof against current 200-name production/review universe.",
        "4. WF78 import gate with explicit owner approval before any durable universe mutation.",
    ])
    return "\n".join(lines) + "\n"


def build_payload() -> dict[str, Any]:
    active = active_tickers()
    wf61 = load_json_artifact(WF61_FEED) if WF61_FEED.exists() else {}
    scenario = scenario_context_panel()
    bench = benchmark_returns()
    candidates = [build_candidate(row, active, bench) for row in CANDIDATE_UNIVERSE]
    candidates.sort(key=lambda row: (row["route"] != "migration_candidate", -row["score"], row["ticker"]))
    counts = Counter(row["route"] for row in candidates)
    bucket_counts = Counter(row["bucket"] for row in candidates if row["route"] == "migration_candidate")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF78",
        "supporting_workflow": "WF61",
        "thesis": "Rate stabilization can broaden market leadership and improve financing-sensitive small/mid-cap operating-company fundamentals, valuation multiples, and risk appetite.",
        "authority": AUTHORITY,
        "source_artifacts": [
            {"path": rel(CANONICAL_DB), "role": "existing active ticker exclusion source", "exists": CANONICAL_DB.exists()},
            {"path": rel(WF61_FEED), "role": "small/mid proxy regime confirmation", "exists": WF61_FEED.exists(), "market_data_as_of": (wf61 or {}).get("market_data_as_of")},
            {"path": rel(CURRENT_ANALOG_MATCH), "role": "review-only historical scenario context", "exists": CURRENT_ANALOG_MATCH.exists(), "status": scenario.get("status")},
        ],
        "benchmark_returns_pct": bench,
        "scenario_context_panel": scenario,
        "summary": {
            "candidates_reviewed": len(candidates),
            "migration_candidate_count": counts.get("migration_candidate", 0),
            "watchlist_candidate_count": counts.get("watchlist_candidate", 0),
            "hold_or_reject_count": counts.get("hold_or_reject", 0),
            "existing_universe_exclusion_count": counts.get("excluded_existing_universe", 0),
            "migration_candidate_buckets": dict(sorted(bucket_counts.items())),
            "minimum_median_20d_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
        },
        "top_migration_candidates": [row for row in candidates if row["route"] == "migration_candidate"][:15],
        "watchlist_candidates": [row for row in candidates if row["route"] == "watchlist_candidate"][:20],
        "candidates": candidates,
        "migration_ready": True,
        "import_executed": False,
        "next_batch_contract": {
            "candidate_scope": "small_mid_rate_stabilization",
            "default_tier": "C",
            "default_monitoring_role": "small_mid_rate_stabilization_candidate",
            "thin_monitor_row": True,
            "source_open_required": True,
            "promotion_required_before_action": True,
            "required_future_gate": "explicit WF78 import gate approval with provider proof, source-open registry, backup/rollback, and post-import validators",
        },
    }
    checks = validate(payload)
    payload["validation"] = {
        "status": "ok" if all(check["ok"] or check["severity"] == "warning" for check in checks) else "fail",
        "checks": checks,
        "failed_critical_count": sum(1 for check in checks if not check["ok"] and check["severity"] == "critical"),
        "warning_count": sum(1 for check in checks if not check["ok"] and check["severity"] == "warning"),
    }
    if payload["validation"]["failed_critical_count"]:
        payload["status"] = "blocked"
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write JSON/Markdown artifacts")
    parser.add_argument("--validate", action="store_true", help="fail nonzero on validation failure")
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        atomic_write_json(OUT_JSON, payload)
        atomic_write_text(OUT_MD, markdown(payload))
    print(json.dumps({
        "status": payload["status"],
        "validation": payload["validation"]["status"],
        "candidates_reviewed": payload["summary"]["candidates_reviewed"],
        "migration_candidates": payload["summary"]["migration_candidate_count"],
        "watchlist_candidates": payload["summary"]["watchlist_candidate_count"],
        "output_json": rel(OUT_JSON) if args.write else None,
        "output_md": rel(OUT_MD) if args.write else None,
    }, indent=2))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
