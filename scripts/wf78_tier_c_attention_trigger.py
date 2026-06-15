#!/usr/bin/env python3
"""Build the WF78 Tier C attention-trigger queue.

This report-only layer catches Tier C names that deserve fresh research
attention because price momentum, initial fundamentals, and repair burden have
changed enough to stop treating them as passive monitors. It does not promote a
name to Tier B/A, mutate universe/canon/portfolio state, or approve capital or
execution.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
DEFAULT_OUT = TMP / "wf78-tier-c-attention-trigger.json"
DEFAULT_DB = TMP / "wf78-tier-c-attention-trigger.sqlite"
SCHEMA = "veritas.wf78_tier_c_attention_trigger.v1"

ATTENTION_SCORE_THRESHOLD = 45
HIGH_ATTENTION_SCORE_THRESHOLD = 60
MOMENTUM_SCORE_THRESHOLD = 15
MAX_ATTENTION_ROWS = 25

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "automated_non_capital_routing_allowed": True,
    "tier_c_attention_only": True,
    "tier_b_promotion_allowed": False,
    "tier_a_promotion_allowed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "report_only",
    "automated_non_capital_routing_allowed",
    "tier_c_attention_only",
}
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


def ticker_key(value: Any) -> str:
    return str(value or "").upper().strip()


def yf_symbol(value: str) -> str:
    # Yahoo uses dashes for share classes such as BRK.B.
    return value.replace(".", "-")


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def active_tier_c_entries() -> list[dict[str, Any]]:
    universe = load_dict(UNIVERSE)
    auto_router = load_dict(AUTO_ROUTER)
    auto_by_ticker = {
        ticker_key(row.get("ticker")): row
        for row in as_list(auto_router.get("rows"))
        if isinstance(row, dict) and row.get("ticker")
    }
    entries: list[dict[str, Any]] = []
    for row in as_list(universe.get("entries")):
        entry = as_dict(row)
        ticker = ticker_key(entry.get("ticker"))
        if not ticker or entry.get("active") is False:
            continue
        auto_row = auto_by_ticker.get(ticker)
        if auto_row:
            if str(auto_row.get("auto_tier") or "") != "Tier C":
                continue
        elif str(entry.get("tier") or "").upper() != "C":
            continue
        entries.append({**entry, "ticker": ticker, "current_auto_state": as_dict(auto_row).get("auto_state")})
    return entries


def fetch_price_metrics(symbols: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if not symbols:
        return {}, {}
    yf_symbols = [yf_symbol(symbol) for symbol in symbols]
    symbol_map = dict(zip(yf_symbols, symbols))
    try:
        import yfinance as yf  # type: ignore
        data = yf.download(
            yf_symbols,
            period="1mo",
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as exc:
        return {}, {symbol: f"yfinance_download_failed: {exc}" for symbol in symbols}

    metrics: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for yf_sym, ticker in symbol_map.items():
        try:
            frame = data[yf_sym] if len(yf_symbols) > 1 else data
            if frame is None or frame.empty or "Close" not in frame:
                errors[ticker] = "missing_close_history"
                continue
            clean = frame.dropna(subset=["Close"])
            closes = [float(value) for value in clean["Close"].tolist()]
            volumes = [float(value) for value in clean["Volume"].fillna(0).tolist()] if "Volume" in clean else []
            if len(closes) < 6:
                errors[ticker] = f"insufficient_close_history:{len(closes)}"
                continue
            latest = closes[-1]
            five_day = ((latest / closes[-6]) - 1.0) * 100.0
            ten_day = ((latest / closes[-11]) - 1.0) * 100.0 if len(closes) >= 11 else None
            twenty_day = ((latest / closes[-21]) - 1.0) * 100.0 if len(closes) >= 21 else None
            volume_ratio = None
            if len(volumes) >= 10 and sum(volumes[-10:-5]) > 0:
                volume_ratio = (sum(volumes[-5:]) / 5.0) / (sum(volumes[-10:-5]) / 5.0)
            metrics[ticker] = {
                "price_source": "yfinance",
                "provider_symbol": yf_sym,
                "latest_close": round(latest, 4),
                "price_date": str(clean.index[-1].date()),
                "close_count": len(closes),
                "five_day_pct": round(five_day, 2),
                "ten_day_pct": round(ten_day, 2) if ten_day is not None else None,
                "twenty_day_pct": round(twenty_day, 2) if twenty_day is not None else None,
                "five_day_volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
            }
        except Exception as exc:
            errors[ticker] = f"price_metric_error: {exc}"
    return metrics, errors


def num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def add_score(parts: list[dict[str, Any]], name: str, points: int, detail: Any) -> None:
    if points:
        parts.append({"name": name, "points": int(points), "detail": detail})


def score_momentum(price: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    parts: list[dict[str, Any]] = []
    score = 0
    five = num(price.get("five_day_pct"))
    ten = num(price.get("ten_day_pct"))
    vol_ratio = num(price.get("five_day_volume_ratio"))
    if five is not None:
        points = 30 if five >= 10 else 22 if five >= 7 else 15 if five >= 5 else 8 if five >= 3 else 0
        score += points
        add_score(parts, "five_day_price_momentum", points, five)
    if ten is not None:
        points = 8 if ten >= 10 else 4 if ten >= 5 else 0
        score += points
        add_score(parts, "ten_day_confirmation", points, ten)
    if vol_ratio is not None:
        points = 6 if vol_ratio >= 1.5 else 3 if vol_ratio >= 1.2 else 0
        score += points
        add_score(parts, "volume_confirmation", points, vol_ratio)
    return score, parts


def score_fundamentals(card: dict[str, Any]) -> tuple[int, list[dict[str, Any]], list[str], list[str]]:
    metrics = as_dict(card.get("key_financial_metrics"))
    valuation = as_dict(card.get("valuation"))
    growth = as_dict(metrics.get("growth"))
    profitability = as_dict(metrics.get("profitability"))
    balance = as_dict(metrics.get("balance_sheet"))
    cash_flow = as_dict(metrics.get("cash_flow"))
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    earnings = as_dict(card.get("latest_earnings_performance"))
    orders = as_dict(card.get("orders_backlog_book_to_bill"))
    recommendation = as_dict(card.get("recommendation_support"))

    parts: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    score = 0
    if metrics.get("status") == "available":
        score += 10
        add_score(parts, "fundamental_snapshot_available", 10, metrics.get("data_quality"))
    else:
        blockers.append("fundamental_snapshot_missing")

    revenue = num(growth.get("revenue_yoy_pct"))
    eps = num(growth.get("eps_yoy_pct"))
    net_income = num(growth.get("net_income_yoy_pct"))
    fcf_growth = num(growth.get("free_cash_flow_yoy_pct"))
    operating_margin = num(profitability.get("operating_margin_pct"))
    gross_margin = num(profitability.get("gross_margin_pct"))
    roic = num(profitability.get("roic_proxy_pct"))
    debt_ebitda = num(balance.get("debt_to_annualized_ebitda"))
    net_debt = num(balance.get("net_debt"))
    fcf = num(cash_flow.get("free_cash_flow"))
    forward_pe = num(valuation.get("forward_pe"))
    ev_ebitda = num(valuation.get("ev_to_ebitda_proxy"))
    price_to_book = num(valuation.get("price_to_book"))
    consensus = str(analyst.get("consensus_rating") or "").lower()

    if revenue is not None:
        points = 8 if revenue >= 20 else 5 if revenue >= 8 else 0
        score += points
        add_score(parts, "revenue_growth", points, revenue)
    if eps is not None or net_income is not None:
        value = max([v for v in [eps, net_income] if v is not None], default=0)
        points = 8 if value >= 50 else 5 if value >= 20 else 0
        score += points
        add_score(parts, "earnings_growth", points, value)
    if fcf_growth is not None:
        points = 6 if fcf_growth >= 50 else 3 if fcf_growth >= 15 else 0
        score += points
        add_score(parts, "fcf_growth", points, fcf_growth)
    if operating_margin is not None or gross_margin is not None:
        value = max([v for v in [operating_margin, gross_margin] if v is not None], default=0)
        points = 7 if value >= 40 else 4 if value >= 20 else 0
        score += points
        add_score(parts, "margin_strength", points, value)
    if roic is not None:
        points = 6 if roic >= 25 else 3 if roic >= 12 else 0
        score += points
        add_score(parts, "roic_strength", points, roic)
    if debt_ebitda is not None:
        points = 6 if debt_ebitda <= 1.5 else 3 if debt_ebitda <= 2.5 else 0
        score += points
        add_score(parts, "balance_sheet_leverage", points, debt_ebitda)
        if debt_ebitda > 3.0:
            warnings.append("high_leverage")
    if net_debt is not None and net_debt < 0:
        score += 4
        add_score(parts, "net_cash_balance_sheet", 4, net_debt)
    if forward_pe is not None and 0 < forward_pe <= 20:
        score += 4
        add_score(parts, "valuation_forward_pe_reasonable", 4, forward_pe)
    if "buy" in consensus:
        score += 3
        add_score(parts, "analyst_buy_skew", 3, consensus)

    if fcf is not None and fcf < 0:
        warnings.append("negative_free_cash_flow")
        score -= 8
        add_score(parts, "negative_free_cash_flow_penalty", -8, fcf)
    if ev_ebitda is not None and ev_ebitda > 100:
        warnings.append("valuation_anomaly_ev_to_ebitda")
        score -= 8
        add_score(parts, "valuation_anomaly_penalty", -8, ev_ebitda)
    if price_to_book is not None and price_to_book > 50:
        warnings.append("valuation_anomaly_price_to_book")
    if as_dict(earnings.get("official_guidance")).get("status") == "missing_manual_required":
        blockers.append("official_guidance_source_open_required")
    if as_dict(earnings.get("official_growth_bridge")).get("status") == "missing_manual_required":
        blockers.append("official_growth_bridge_source_open_required")
    if orders.get("status") == "missing_manual_required":
        blockers.append("orders_backlog_manual_capture_required")
    if as_dict(card.get("price_band_stop")).get("entry_band_low") is None:
        blockers.append("price_band_stop_missing")
    if as_dict(card.get("technical_posture")).get("latest_close") is None:
        blockers.append("technical_posture_missing")
    if str(recommendation.get("posture_key") or "") == "promotion_review":
        score += 8
        add_score(parts, "existing_promotion_review_posture", 8, recommendation.get("posture"))

    return score, parts, sorted(set(blockers)), sorted(set(warnings))


def attention_state(total_score: int, blockers: list[str], warnings: list[str]) -> str:
    if total_score >= HIGH_ATTENTION_SCORE_THRESHOLD and not any("anomaly" in item for item in warnings):
        return "C-CANDIDATE"
    if "price_band_stop_missing" in blockers or "technical_posture_missing" in blockers:
        return "C-CANDIDATE-REPAIR"
    return "C-THEME-WATCH"


def build_rows(entries: list[dict[str, Any]], price_metrics: dict[str, dict[str, Any]], price_errors: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        ticker = ticker_key(entry.get("ticker"))
        card = load_dict(card_path(ticker))
        price = price_metrics.get(ticker, {})
        momentum_score, momentum_parts = score_momentum(price)
        fundamental_score, fundamental_parts, blockers, warnings = score_fundamentals(card)
        total_score = momentum_score + fundamental_score
        attention = (
            momentum_score >= MOMENTUM_SCORE_THRESHOLD
            and fundamental_score > 0
            and total_score >= ATTENTION_SCORE_THRESHOLD
            and bool(price)
        )
        state = attention_state(total_score, blockers, warnings) if attention else "C-MONITOR"
        row = {
            "ticker": ticker,
            "name": entry.get("name") or ticker,
            "sector": entry.get("sector"),
            "industry": entry.get("industry"),
            "legacy_tier": entry.get("tier"),
            "current_auto_state": entry.get("current_auto_state"),
            "attention_triggered": attention,
            "attention_state": state,
            "attention_score": round(total_score, 2),
            "momentum_score": momentum_score,
            "fundamental_score": fundamental_score,
            "price_metrics": price,
            "price_error": price_errors.get(ticker),
            "score_parts": momentum_parts + fundamental_parts,
            "blockers": blockers,
            "warnings": warnings,
            "recommended_next_action": (
                "advance_to_tier_b_packet_candidate_queue_after_source_and_band_repair"
                if attention and state == "C-CANDIDATE"
                else "repair_source_open_and_price_band_context_before_tier_b_packet"
                if attention
                else "keep_tier_c_monitor"
            ),
            "tier_b_promoted": False,
            "tier_a_promoted": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "source_artifacts": [rel(card_path(ticker)), rel(UNIVERSE), rel(AUTO_ROUTER)],
        }
        rows.append(row)
    rows.sort(key=lambda item: (-int(bool(item["attention_triggered"])), -float(item["attention_score"]), str(item["ticker"])))
    return rows


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def validation_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    rows = as_list(report.get("rows"))
    attention_rows = [as_dict(row) for row in rows if as_dict(row).get("attention_triggered")]
    add_check(checks, "universe_present", UNIVERSE.exists(), rel(UNIVERSE))
    add_check(checks, "tier_c_rows_present", bool(rows), len(rows))
    add_check(checks, "attention_rows_generated", bool(attention_rows), len(attention_rows), "warning")
    add_check(checks, "attention_row_limit_respected", len(attention_rows) <= MAX_ATTENTION_ROWS, len(attention_rows))
    add_check(checks, "no_tier_b_promotion", all(as_dict(row).get("tier_b_promoted") is False for row in rows), None)
    add_check(checks, "no_tier_a_promotion", all(as_dict(row).get("tier_a_promoted") is False for row in rows), None)
    add_check(checks, "no_capital_deployment_approved", all(as_dict(row).get("capital_deployment_approved") is False for row in rows), None)
    add_check(checks, "no_trade_or_execution_approved", all(as_dict(row).get("trade_or_execution_approved") is False for row in rows), None)
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    return checks


def build_report() -> dict[str, Any]:
    entries = active_tier_c_entries()
    price_metrics, price_errors = fetch_price_metrics([ticker_key(row.get("ticker")) for row in entries])
    rows = build_rows(entries, price_metrics, price_errors)
    attention_rows = [row for row in rows if row.get("attention_triggered")][:MAX_ATTENTION_ROWS]
    state_counts = Counter(str(row.get("attention_state") or "") for row in rows)
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in attention_rows)
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF78 - Tier C Attention Trigger",
        "purpose": "Escalate fresh Tier C attention candidates into non-capital repair/research routing before the static Tier B packet batch misses them.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "thresholds": {
            "attention_score_threshold": ATTENTION_SCORE_THRESHOLD,
            "high_attention_score_threshold": HIGH_ATTENTION_SCORE_THRESHOLD,
            "momentum_score_threshold": MOMENTUM_SCORE_THRESHOLD,
            "max_attention_rows": MAX_ATTENTION_ROWS,
        },
        "source_artifacts": {
            "universe": rel(UNIVERSE),
            "auto_router_prior": rel(AUTO_ROUTER),
            "ticker_cards": rel(CARD_DIR),
        },
        "summary": {
            "tier_c_candidate_count": len(entries),
            "priced_count": len(price_metrics),
            "price_error_count": len(price_errors),
            "attention_count": len(attention_rows),
            "attention_tickers": [str(row.get("ticker")) for row in attention_rows],
            "attention_state_counts": dict(sorted(state_counts.items())),
            "attention_sector_counts": dict(sorted(sector_counts.items())),
            "tier_b_promoted_count": 0,
            "tier_a_promoted_count": 0,
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "next_safe_action": "Auto-router may mark these as Tier C attention/repair candidates; Tier B promotion still requires the WF78 evidence gate.",
        },
        "attention_rows": attention_rows,
        "rows": rows,
        "price_errors": price_errors,
        "stop_lines": [
            "This trigger is Tier C attention routing only, not Tier B/A promotion.",
            "No capital deployment, paper/live order, brokerage/account action, money movement, or owner approval inference.",
            "Source-open, official earnings/orders capture, and band/technical repair still gate higher tier promotion.",
        ],
    }
    checks = validation_checks(report)
    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    report["status"] = "ok" if not errors else "blocked"
    report["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": [check for check in checks if check["severity"] == "warning" and not check["ok"]],
        "checks": checks,
    }
    return report


def write_db(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS attention_rows")
        conn.execute(
            """
            CREATE TABLE attention_rows (
                rank INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                name TEXT,
                sector TEXT,
                attention_state TEXT,
                attention_score REAL,
                momentum_score REAL,
                fundamental_score REAL,
                five_day_pct REAL,
                ten_day_pct REAL,
                latest_close REAL,
                blockers_json TEXT,
                warnings_json TEXT,
                recommended_next_action TEXT
            )
            """
        )
        for rank, row in enumerate(as_list(report.get("attention_rows")), start=1):
            row_dict = as_dict(row)
            price = as_dict(row_dict.get("price_metrics"))
            conn.execute(
                "INSERT INTO attention_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rank,
                    row_dict.get("ticker"),
                    row_dict.get("name"),
                    row_dict.get("sector"),
                    row_dict.get("attention_state"),
                    row_dict.get("attention_score"),
                    row_dict.get("momentum_score"),
                    row_dict.get("fundamental_score"),
                    price.get("five_day_pct"),
                    price.get("ten_day_pct"),
                    price.get("latest_close"),
                    json.dumps(row_dict.get("blockers"), sort_keys=True),
                    json.dumps(row_dict.get("warnings"), sort_keys=True),
                    row_dict.get("recommended_next_action"),
                ),
            )
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db-out", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    db_out = args.db_out if args.db_out.is_absolute() else ROOT / args.db_out
    if args.write:
        atomic_write_json(out, report)
    if args.write_db:
        write_db(report, db_out)
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "db_out": rel(db_out) if args.write_db else None,
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
            "warnings": len(as_list(as_dict(report.get("validation")).get("warnings"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
