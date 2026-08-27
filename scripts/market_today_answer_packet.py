#!/usr/bin/env python3
"""Build a local-only market-today answer packet.

This assembler exists so a main session can answer "how did the market do
today?" from workspace artifacts before reaching for the web. It performs no
external fetches and grants no finance action authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "market-today-answer-packet.json"
DEFAULT_MD = TMP / "market-today-answer-packet.md"
SQL_CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
SCHEMA = "veritas.market_today_answer_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "external_fetch_allowed_by_this_script": False,
    "raw_news_claim_allowed_without_source_packet": False,
    "forecast_or_probability_claim_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "durable_sql_canon_current_state_allowed": True,
    "sql_canon_mutation_allowed": False,
    "sql_write_or_import_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

SOURCES = {
    "market_state": TMP / "market-state.json",
    "postmarket_snapshot": TMP / "postmarket-snapshot.json",
    "macro_metrics": TMP / "macro-metrics-current.json",
    "macro_signal_spine": TMP / "macro-signal-spine.json",
    "wf77_price_state": ROOT / "data" / "market" / "price-snapshots" / "wf77-price-state-current.json",
}

FULL_RECAP_REQUIRED_FIELDS = {
    "dow_close_change",
    "nasdaq_composite_close_change",
    "russell_2000_daily_point_change",
    "spx_daily_point_change_percent",
    "normalized_broad_index_daily_change_table",
    "source_backed_market_driver_news_digest",
    "treasury_2y_same_day_value",
}


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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def get_path(value: Any, dotted: str) -> Any:
    cur = value
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    generated = payload.get("generated_at_utc") or payload.get("generated_at")
    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        warnings = as_list(as_dict(payload.get("validation")).get("warnings"))
    return {
        "id": name,
        "path": rel(path),
        "exists": path.exists(),
        "json_readable": bool(payload),
        "status": payload.get("status") or payload.get("overall"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": generated,
        "warning_count": len(warnings),
    }


def sql_canon_context() -> dict[str, Any]:
    context: dict[str, Any] = {
        "schema": "veritas.market_today_answer_packet.sql_canon_context.v1",
        "status": "blocked",
        "sql_canon_db": rel(SQL_CANON_DB),
        "typed_access_layer": "scripts/finance_sql_canon_access.py",
        "access_validation_status": None,
        "production_answer_count": None,
        "legacy_production_answer_count": None,
        "production_answer_definition": "SQL-canon production scope; zero is a valid fail-closed wait state",
        "registry_summary": {},
        "validation": {"status": "blocked", "errors": [], "warnings": []},
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    guard = finance_sql_canon_guard_context(consumer=rel(Path(__file__)), db_path=SQL_CANON_DB)
    guard_validation = as_dict(guard.get("validation"))
    errors = as_list(guard_validation.get("errors"))
    warnings = as_list(guard_validation.get("warnings"))
    production_count = guard.get("production_answer_count")
    context["access_validation_status"] = guard.get("access_validation_status")
    context["production_answer_count"] = production_count
    context["legacy_production_answer_count"] = guard.get("legacy_production_answer_count")
    context["registry_summary"] = guard.get("migration_registry_summary") or {}
    context["validation"]["errors"] = errors
    context["validation"]["warnings"] = warnings
    if guard.get("status") == "ok" and production_count == 0:
        context["validation"]["warnings"].append("production_answer_set_empty_fail_closed")
    context["validation"]["status"] = "blocked" if errors else "ok"
    context["status"] = "blocked" if errors else "ok"
    return context


def number(value: Any, digits: int = 2) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def signed(value: float | None, suffix: str = "%") -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}{suffix}"


def market_snapshot(
    *,
    symbol: str,
    label: str,
    value: float | None,
    change: float | None = None,
    change_pct: float | None = None,
    as_of: Any = None,
    source: Any = None,
    proxy: bool = False,
    missing_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "label": label,
        "value": value,
        "change": change,
        "change_pct": change_pct,
        "as_of": as_of,
        "source": source,
        "proxy": proxy,
        "available": value is not None,
        "missing_reason": missing_reason,
    }


def broad_market_levels(market_state: dict[str, Any], macro_signal: dict[str, Any]) -> dict[str, Any]:
    market_data = as_dict(market_state.get("data"))
    index_map = as_dict(get_path(macro_signal, "signal_buckets.expanded_index_breadth.signals.index_map"))
    broad_indices = as_dict(market_data.get("broad_indices"))
    spx = as_dict(as_dict(market_data.get("equities")).get("spx"))
    volatility = as_dict(market_data.get("volatility"))

    def index_record(key: str, label: str, *, proxy: bool = False) -> dict[str, Any]:
        row = as_dict(index_map.get(key))
        return market_snapshot(
            symbol=key,
            label=label,
            value=number(row.get("close")),
            as_of=row.get("date"),
            source=row.get("source"),
            proxy=proxy,
            missing_reason=None if row else "not_present_in_macro_signal_spine",
        ) | {
            "change_5d_pct": number(row.get("change_5d_pct")),
            "change_20d_pct": number(row.get("change_20d_pct")),
            "above_50dma": row.get("above_50dma"),
            "above_200dma": row.get("above_200dma"),
            "pct_from_52w_high": number(row.get("pct_from_52w_high")),
        }

    def close_change_record(key: str, symbol: str, label: str, *, proxy: bool = False) -> dict[str, Any]:
        row = as_dict(broad_indices.get(key))
        if row:
            return market_snapshot(
                symbol=symbol,
                label=label,
                value=number(row.get("close")),
                change=number(row.get("point_change")),
                change_pct=number(row.get("change_pct")),
                as_of=row.get("as_of"),
                source=row.get("source"),
                proxy=proxy,
                missing_reason=None if row.get("available") else row.get("note") or "not_available",
            )
        return market_snapshot(
            symbol=symbol,
            label=label,
            value=None,
            proxy=proxy,
            missing_reason="not_present_in_market_state_broad_indices",
        )

    spx_daily = close_change_record("spx", "^GSPC", "S&P 500 cash")
    if spx_daily.get("available") is not True:
        spx_daily = market_snapshot(
            symbol="^GSPC",
            label="S&P 500 cash",
            value=number(as_dict(market_data.get("equities")).get("spx")),
            as_of=as_dict(market_data.get("equities")).get("as_of"),
            source=as_dict(market_data.get("equities")).get("source"),
        )

    return {
        "spx_cash": spx_daily,
        "vix_cash": market_snapshot(
            symbol="^VIX",
            label="VIX",
            value=number(volatility.get("vix")),
            as_of=volatility.get("as_of"),
            source=volatility.get("source"),
        ),
        "dow_cash": close_change_record("dow", "^DJI", "Dow Jones Industrial Average"),
        "nasdaq_composite_cash": close_change_record("nasdaq_composite", "^IXIC", "Nasdaq Composite"),
        "spx_trend": index_record("^GSPC", "S&P 500 trend"),
        "nasdaq_100_trend": close_change_record("nasdaq_100", "^NDX", "Nasdaq 100") | {
            "change_5d_pct": number(as_dict(index_map.get("^NDX")).get("change_5d_pct")),
            "change_20d_pct": number(as_dict(index_map.get("^NDX")).get("change_20d_pct")),
            "above_50dma": as_dict(index_map.get("^NDX")).get("above_50dma"),
            "above_200dma": as_dict(index_map.get("^NDX")).get("above_200dma"),
            "pct_from_52w_high": number(as_dict(index_map.get("^NDX")).get("pct_from_52w_high")),
        },
        "russell_2000_trend": close_change_record("russell_2000", "^RUT", "Russell 2000") | {
            "change_5d_pct": number(as_dict(index_map.get("^RUT")).get("change_5d_pct")),
            "change_20d_pct": number(as_dict(index_map.get("^RUT")).get("change_20d_pct")),
            "above_50dma": as_dict(index_map.get("^RUT")).get("above_50dma"),
            "above_200dma": as_dict(index_map.get("^RUT")).get("above_200dma"),
            "pct_from_52w_high": number(as_dict(index_map.get("^RUT")).get("pct_from_52w_high")),
        },
        "spy_proxy": close_change_record("spy", "SPY", "SPY S&P 500 ETF proxy", proxy=True) | {
            "change_5d_pct": number(as_dict(index_map.get("SPY")).get("change_5d_pct")),
            "change_20d_pct": number(as_dict(index_map.get("SPY")).get("change_20d_pct")),
            "above_50dma": as_dict(index_map.get("SPY")).get("above_50dma"),
            "above_200dma": as_dict(index_map.get("SPY")).get("above_200dma"),
            "pct_from_52w_high": number(as_dict(index_map.get("SPY")).get("pct_from_52w_high")),
        },
        "qqq_proxy": close_change_record("qqq", "QQQ", "QQQ Nasdaq 100 ETF proxy", proxy=True) | {
            "change_5d_pct": number(as_dict(index_map.get("QQQ")).get("change_5d_pct")),
            "change_20d_pct": number(as_dict(index_map.get("QQQ")).get("change_20d_pct")),
            "above_50dma": as_dict(index_map.get("QQQ")).get("above_50dma"),
            "above_200dma": as_dict(index_map.get("QQQ")).get("above_200dma"),
            "pct_from_52w_high": number(as_dict(index_map.get("QQQ")).get("pct_from_52w_high")),
        },
        "iwm_proxy": close_change_record("iwm", "IWM", "IWM Russell 2000 ETF proxy", proxy=True) | {
            "change_5d_pct": number(as_dict(index_map.get("IWM")).get("change_5d_pct")),
            "change_20d_pct": number(as_dict(index_map.get("IWM")).get("change_20d_pct")),
            "above_50dma": as_dict(index_map.get("IWM")).get("above_50dma"),
            "above_200dma": as_dict(index_map.get("IWM")).get("above_200dma"),
            "pct_from_52w_high": number(as_dict(index_map.get("IWM")).get("pct_from_52w_high")),
        },
    }


def normalized_broad_index_table(levels: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = [
        ("spx_cash", "SPX"),
        ("dow_cash", "DOW"),
        ("nasdaq_composite_cash", "NASDAQ_COMPOSITE"),
        ("nasdaq_100_trend", "NASDAQ_100"),
        ("russell_2000_trend", "RUSSELL_2000"),
        ("spy_proxy", "SPY"),
        ("qqq_proxy", "QQQ"),
        ("iwm_proxy", "IWM"),
    ]
    rows: list[dict[str, Any]] = []
    for key, normalized_symbol in mapping:
        item = as_dict(levels.get(key))
        rows.append(
            {
                "key": key,
                "normalized_symbol": normalized_symbol,
                "symbol": item.get("symbol"),
                "label": item.get("label"),
                "close": item.get("value"),
                "point_change": item.get("change"),
                "percent_change": item.get("change_pct"),
                "as_of": item.get("as_of"),
                "source": item.get("source"),
                "available": item.get("available") is True and item.get("change_pct") is not None,
                "proxy": item.get("proxy") is True,
                "missing_reason": item.get("missing_reason"),
            }
        )
    return rows


def sector_moves(market_state: dict[str, Any]) -> list[dict[str, Any]]:
    sectors = as_dict(get_path(market_state, "data.sectors"))
    rows: list[dict[str, Any]] = []
    for key in ("xlk", "xli", "xlf", "xle"):
        item = as_dict(sectors.get(key))
        if not item:
            continue
        rows.append(
            {
                "key": key,
                "ticker": item.get("ticker"),
                "label": item.get("label"),
                "last_price": number(item.get("last_price")),
                "change": number(item.get("change")),
                "change_pct": number(item.get("change_pct")),
                "relative_label": item.get("relative_label"),
                "source": item.get("source"),
            }
        )
    return rows


def rates_energy_fx(market_state: dict[str, Any]) -> dict[str, Any]:
    data = as_dict(market_state.get("data"))
    treasuries = as_dict(data.get("treasuries"))
    energy = as_dict(data.get("energy"))
    fx = as_dict(data.get("fx"))
    return {
        "treasury_10y_pct": number(treasuries.get("10y"), 3),
        "treasury_10y_as_of": treasuries.get("10y_as_of"),
        "treasury_10y_source": treasuries.get("10y_source"),
        "treasury_2y_pct": number(treasuries.get("2y"), 3),
        "treasury_2y_as_of": treasuries.get("2y_as_of"),
        "treasury_2y_source": treasuries.get("2y_source"),
        "treasury_2y_note": treasuries.get("2y_note"),
        "curve_2s10s_bps": number(treasuries.get("curve_2s10s_bps"), 1),
        "curve_3m10y_bps": number(treasuries.get("curve_3m10y_bps"), 1),
        "dxy": number(fx.get("dxy")),
        "dxy_as_of": fx.get("as_of"),
        "brent": number(energy.get("brent")),
        "brent_as_of": energy.get("brent_as_of"),
        "wti": number(energy.get("wti")),
        "wti_as_of": energy.get("wti_as_of"),
    }


def cpi_event(macro_metrics: dict[str, Any]) -> dict[str, Any]:
    detail = as_dict(get_path(macro_metrics, "summary.cpi_release_detail"))
    return {
        "status": detail.get("status"),
        "source": detail.get("source"),
        "source_url": detail.get("source_url"),
        "source_mode": detail.get("source_mode"),
        "release_period": detail.get("release_period"),
        "release_date_text": detail.get("release_date_text"),
        "all_items_mom_pct": number(get_path(detail, "all_items.latest_mom_pct")),
        "all_items_yoy_pct": number(get_path(detail, "all_items.yoy_pct")),
        "core_mom_pct": number(get_path(detail, "core.latest_mom_pct")),
        "core_yoy_pct": number(get_path(detail, "core.yoy_pct")),
        "energy_mom_pct": number(get_path(detail, "energy.latest_mom_pct")),
        "energy_yoy_pct": number(get_path(detail, "energy.yoy_pct")),
        "gasoline_mom_pct": number(get_path(detail, "gasoline.latest_mom_pct")),
        "gasoline_yoy_pct": number(get_path(detail, "gasoline.yoy_pct")),
    }


def classify_cpi_driver(macro: dict[str, Any]) -> dict[str, str] | None:
    """Classify current monthly CPI evidence without inferring pressure from presence alone."""
    headline = number(macro.get("all_items_mom_pct"))
    core = number(macro.get("core_mom_pct"))
    energy = number(macro.get("energy_mom_pct"))
    gasoline = number(macro.get("gasoline_mom_pct"))
    if headline is None or core is None:
        return None
    if core >= 0.3:
        return {
            "driver_id": "cpi_broad_core_pressure",
            "summary": "Latest monthly CPI evidence shows broad core pressure rather than an energy/gasoline-only impulse.",
        }
    if headline >= 0.35 and gasoline is not None and gasoline >= 1.0:
        return {
            "driver_id": "cpi_energy_gasoline_headline_pressure",
            "summary": "CPI monthly evidence shows an energy/gasoline headline-pressure impulse.",
        }
    if headline >= 0.35 and energy is not None and energy >= 1.0:
        return {
            "driver_id": "cpi_energy_headline_pressure",
            "summary": "CPI monthly headline pressure is energy-led; gasoline did not independently clear the pressure threshold.",
        }
    if headline < 0.25 and core < 0.25:
        return {
            "driver_id": "cpi_monthly_contained",
            "summary": "Latest monthly headline and core CPI are contained; energy/gasoline are not adding monthly headline pressure.",
        }
    return {
        "driver_id": "cpi_mixed",
        "summary": "Latest monthly CPI evidence is mixed and does not support a single energy/gasoline pressure claim.",
    }


def source_backed_market_driver_digest(
    *,
    broad_table: list[dict[str, Any]],
    sectors: list[dict[str, Any]],
    macro: dict[str, Any],
    rates: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cpi_driver = classify_cpi_driver(macro)
    if cpi_driver is not None:
        rows.append(
            {
                "driver_id": cpi_driver["driver_id"],
                "driver_type": "macro_release",
                "summary": cpi_driver["summary"],
                "evidence": {
                    "headline_mom_pct": macro.get("all_items_mom_pct"),
                    "headline_yoy_pct": macro.get("all_items_yoy_pct"),
                    "core_mom_pct": macro.get("core_mom_pct"),
                    "core_yoy_pct": macro.get("core_yoy_pct"),
                    "energy_mom_pct": macro.get("energy_mom_pct"),
                    "gasoline_mom_pct": macro.get("gasoline_mom_pct"),
                },
                "source_refs": [macro.get("source_url") or macro.get("source")],
                "confidence": "high",
                "claim_boundary": "source-backed macro input; not a single-cause explanation for the full market move",
            }
        )
    xle = next((row for row in sectors if row.get("ticker") == "XLE"), {})
    if rates.get("brent") is not None or rates.get("wti") is not None or xle:
        rows.append(
            {
                "driver_id": "oil_and_energy_relative_strength",
                "driver_type": "cross_asset_tape",
                "summary": "Oil is elevated and energy outperformed the tracked sector tape.",
                "evidence": {
                    "brent": rates.get("brent"),
                    "wti": rates.get("wti"),
                    "xle_change_pct": xle.get("change_pct"),
                    "xle_relative_label": xle.get("relative_label"),
                },
                "source_refs": [
                    "tmp/market-state.json:data.energy",
                    "tmp/market-state.json:data.sectors.xle",
                ],
                "confidence": "medium",
                "claim_boundary": "observed tape/rates context; does not prove causality by itself",
            }
        )
    tech = next((row for row in sectors if row.get("ticker") == "XLK"), {})
    industrials = next((row for row in sectors if row.get("ticker") == "XLI"), {})
    nasdaq = next((row for row in broad_table if row.get("normalized_symbol") == "NASDAQ_COMPOSITE"), {})
    spx = next((row for row in broad_table if row.get("normalized_symbol") == "SPX"), {})
    if tech or industrials or nasdaq or spx:
        rows.append(
            {
                "driver_id": "growth_and_cyclical_pressure",
                "driver_type": "market_tape",
                "summary": "Tech/industrial weakness and Nasdaq/SPX changes define the equity-tape risk context.",
                "evidence": {
                    "spx_percent_change": spx.get("percent_change"),
                    "nasdaq_composite_percent_change": nasdaq.get("percent_change"),
                    "xlk_change_pct": tech.get("change_pct"),
                    "xli_change_pct": industrials.get("change_pct"),
                },
                "source_refs": [
                    "tmp/market-state.json:data.broad_indices",
                    "tmp/market-state.json:data.sectors",
                ],
                "confidence": "medium",
                "claim_boundary": "observed market tape; narrative attribution requires source-open news review",
            }
        )
    if rates.get("treasury_2y_pct") is not None or rates.get("treasury_10y_pct") is not None:
        rows.append(
            {
                "driver_id": "rates_sensitivity_window",
                "driver_type": "rates",
                "summary": "2Y/10Y rates and the coming FOMC window keep duration and growth-stock sensitivity elevated.",
                "evidence": {
                    "treasury_2y_pct": rates.get("treasury_2y_pct"),
                    "treasury_2y_as_of": rates.get("treasury_2y_as_of"),
                    "treasury_10y_pct": rates.get("treasury_10y_pct"),
                    "treasury_10y_as_of": rates.get("treasury_10y_as_of"),
                    "curve_2s10s_bps": rates.get("curve_2s10s_bps"),
                },
                "source_refs": [
                    rates.get("treasury_2y_source") or "tmp/market-state.json:data.treasuries.2y",
                    rates.get("treasury_10y_source") or "tmp/market-state.json:data.treasuries.10y",
                ],
                "confidence": "medium",
                "claim_boundary": "rates context only; no Fed decision prediction",
            }
        )
    return [row for row in rows if any(row.get("source_refs") or [])]


def breadth_context(macro_signal: dict[str, Any]) -> list[dict[str, Any]]:
    index_map = as_dict(get_path(macro_signal, "signal_buckets.expanded_index_breadth.signals.index_map"))
    rows: list[dict[str, Any]] = []
    for key in ("SPY", "QQQ", "IWM", "MDY", "RSP", "VUG", "VXUS", "^VIX"):
        item = as_dict(index_map.get(key))
        if not item:
            continue
        rows.append(
            {
                "symbol": key,
                "date": item.get("date"),
                "close": number(item.get("close")),
                "change_5d_pct": number(item.get("change_5d_pct")),
                "change_20d_pct": number(item.get("change_20d_pct")),
                "above_50dma": item.get("above_50dma"),
                "above_200dma": item.get("above_200dma"),
                "pct_from_52w_high": number(item.get("pct_from_52w_high")),
            }
        )
    return rows


def tracked_name_context(postmarket: dict[str, Any], price_state: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(price_state.get("summary"))
    return {
        "postmarket_trust_label": postmarket.get("trust_label"),
        "postmarket_trust_reason": postmarket.get("trust_reason"),
        "deployable_now": as_list(postmarket.get("deployable_now")),
        "promotion_review": as_list(postmarket.get("promotion_review")),
        "almost_deployable": as_list(postmarket.get("almost_deployable")),
        "production_ticker_count": summary.get("production_ticker_count"),
        "fresh_in_band_count": summary.get("fresh_in_band_count"),
        "fresh_in_band_tickers": as_list(summary.get("fresh_in_band_tickers")),
        "fresh_below_stop_count": summary.get("fresh_below_stop_count"),
        "fresh_below_stop_tickers": as_list(summary.get("fresh_below_stop_tickers")),
    }


def missing_fields(
    levels: dict[str, Any],
    market_state: dict[str, Any],
    broad_table: list[dict[str, Any]],
    driver_digest: list[dict[str, Any]],
) -> list[str]:
    missing = set()
    if not as_dict(levels.get("dow_cash")).get("available"):
        missing.add("dow_close_change")
    if not as_dict(levels.get("nasdaq_composite_cash")).get("available"):
        missing.add("nasdaq_composite_close_change")
    if as_dict(levels.get("russell_2000_trend")).get("change_pct") is None:
        missing.add("russell_2000_daily_point_change")
    if as_dict(levels.get("spx_cash")).get("change_pct") is None:
        missing.add("spx_daily_point_change_percent")
    required_symbols = {"SPX", "DOW", "NASDAQ_COMPOSITE", "RUSSELL_2000"}
    available_symbols = {str(row.get("normalized_symbol")) for row in broad_table if row.get("available") is True}
    if not required_symbols.issubset(available_symbols):
        missing.add("normalized_broad_index_daily_change_table")
    if not driver_digest:
        missing.add("source_backed_market_driver_news_digest")
    market_day = market_state.get("last_trading_day")
    if get_path(market_state, "data.treasuries.2y") is None or get_path(market_state, "data.treasuries.2y_as_of") != market_day:
        missing.add("treasury_2y_same_day_value")
    return sorted(missing)


def local_summary(
    levels: dict[str, Any],
    sectors: list[dict[str, Any]],
    macro: dict[str, Any],
    rates: dict[str, Any],
    broad_table: list[dict[str, Any]],
    driver_digest: list[dict[str, Any]],
) -> str:
    spx = as_dict(levels.get("spx_cash")).get("value")
    spx_change = as_dict(levels.get("spx_cash")).get("change_pct")
    vix = as_dict(levels.get("vix_cash")).get("value")
    sector_bits = [
        f"{row.get('ticker')} {signed(row.get('change_pct'))}"
        for row in sectors
        if row.get("change_pct") is not None
    ]
    cpi = (
        f"CPI {macro.get('all_items_yoy_pct')}% YoY / core {macro.get('core_yoy_pct')}% YoY"
        if macro.get("all_items_yoy_pct") is not None and macro.get("core_yoy_pct") is not None
        else "CPI detail unavailable"
    )
    oil = (
        f"Brent ${rates.get('brent')}, WTI ${rates.get('wti')}"
        if rates.get("brent") is not None and rates.get("wti") is not None
        else "oil unavailable"
    )
    recap = (
        "full broad-index close/change and source-backed driver digest available locally"
        if broad_table and driver_digest
        else "full broad-index close/change or source-backed driver recap remains incomplete locally"
    )
    return (
        f"Local workspace data supports a post-close market read: S&P 500 {spx} ({signed(spx_change)}), VIX {vix}; "
        f"sector tape: {', '.join(sector_bits) if sector_bits else 'sector moves unavailable'}; "
        f"{cpi}; {oil}. {recap}."
    )


def build_packet() -> dict[str, Any]:
    loaded = {name: load(path) for name, path in SOURCES.items()}
    source_records = [source_record(name, path, loaded[name]) for name, path in SOURCES.items()]
    sql_context = sql_canon_context()
    market_state = loaded["market_state"]
    macro_signal = loaded["macro_signal_spine"]
    macro_metrics = loaded["macro_metrics"]
    postmarket = loaded["postmarket_snapshot"]
    price_state = loaded["wf77_price_state"]

    levels = broad_market_levels(market_state, macro_signal)
    sectors = sector_moves(market_state)
    rates = rates_energy_fx(market_state)
    macro_event = cpi_event(macro_metrics)
    breadth = breadth_context(macro_signal)
    tracked = tracked_name_context(postmarket, price_state)
    broad_table = normalized_broad_index_table(levels)
    driver_digest = source_backed_market_driver_digest(
        broad_table=broad_table,
        sectors=sectors,
        macro=macro_event,
        rates=rates,
    )
    missing = missing_fields(levels, market_state, broad_table, driver_digest)

    required_sources_missing = [
        item["id"] for item in source_records if item["id"] in {"market_state", "postmarket_snapshot"} and not item["exists"]
    ]
    basic_ready = not required_sources_missing and bool(as_dict(levels.get("spx_cash")).get("available")) and bool(sectors)
    full_ready = basic_ready and not (FULL_RECAP_REQUIRED_FIELDS & set(missing))
    warning_sources = [
        item["id"]
        for item in source_records
        if str(item.get("status") or "").lower() in {"warning", "partial", "degraded"} or item.get("warning_count", 0) > 0
    ]

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if required_sources_missing else "warning" if (not full_ready or warning_sources) else "ok",
        "operator_action": "BLOCKED" if required_sources_missing else "MAIN_SESSION_REVIEW" if not full_ready else "NO_REPLY",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": source_records,
        "sql_canon_context": sql_context,
        "as_of": {
            "market_state_last_trading_day": market_state.get("last_trading_day"),
            "macro_signal_as_of_date": macro_signal.get("as_of_date"),
            "postmarket_snapshot_date": postmarket.get("snapshot_date"),
            "price_state_latest_market_data_date": get_path(price_state, "source_freshness.latest_market_data_date"),
        },
        "answer_readiness": {
            "can_answer_basic_market_day_without_web": basic_ready,
            "can_answer_full_market_close_recap_without_web": full_ready,
            "required_sources_missing": required_sources_missing,
            "warning_sources": warning_sources,
            "missing_for_web_free_full_recap": missing,
        },
        "market_levels": levels,
        "normalized_broad_index_daily_change_table": broad_table,
        "sector_moves": sectors,
        "rates_energy_fx": rates,
        "source_backed_market_driver_news_digest": driver_digest,
        "macro_events": {"cpi_release": macro_event},
        "breadth_context": breadth,
        "tracked_name_context": tracked,
        "local_answer_summary": local_summary(levels, sectors, macro_event, rates, broad_table, driver_digest),
        "stop_lines": [
            "Use this packet as local review evidence only.",
            "Do not present missing broad-index/driver fields as known local facts.",
            "Do not infer portfolio/capital/execution approval from this packet.",
        ],
    }
    packet["validation"] = validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if packet.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if not packet.get("inputs"):
        errors.append("inputs_missing")
    if as_dict(packet.get("sql_canon_context")).get("status") != "ok":
        errors.append("sql_canon_guard_blocked")
    if as_dict(packet.get("market_levels")).get("spx_cash", {}).get("available") is not True:
        errors.append("spx_cash_missing")
    broad_table = as_list(packet.get("normalized_broad_index_daily_change_table"))
    if not broad_table:
        warnings.append("normalized_broad_index_daily_change_table_missing")
    else:
        required_symbols = {"SPX", "DOW", "NASDAQ_COMPOSITE", "RUSSELL_2000"}
        available_symbols = {str(row.get("normalized_symbol")) for row in broad_table if isinstance(row, dict) and row.get("available") is True}
        if not required_symbols.issubset(available_symbols):
            warnings.append("normalized_broad_index_daily_change_table_incomplete")
    if not as_list(packet.get("source_backed_market_driver_news_digest")):
        warnings.append("source_backed_market_driver_news_digest_missing")
    if not as_list(packet.get("sector_moves")):
        warnings.append("sector_moves_missing")
    readiness = as_dict(packet.get("answer_readiness"))
    if not readiness.get("can_answer_full_market_close_recap_without_web"):
        warnings.append("full_market_close_recap_still_requires_local_data_expansion")
    missing = set(as_list(readiness.get("missing_for_web_free_full_recap")))
    if not readiness.get("can_answer_full_market_close_recap_without_web") and not FULL_RECAP_REQUIRED_FIELDS & missing:
        warnings.append("full_recap_missing_field_contract_not_exercised")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_md(packet: dict[str, Any]) -> str:
    readiness = as_dict(packet.get("answer_readiness"))
    lines = [
        "# Market Today Answer Packet",
        "",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Basic web-free answer ready: `{str(readiness.get('can_answer_basic_market_day_without_web')).lower()}`",
        f"- Full web-free recap ready: `{str(readiness.get('can_answer_full_market_close_recap_without_web')).lower()}`",
        "",
        "## Local Summary",
        "",
        str(packet.get("local_answer_summary") or ""),
        "",
        "## Missing For Full Web-Free Recap",
        "",
    ]
    for item in as_list(readiness.get("missing_for_web_free_full_recap")):
        lines.append(f"- `{item}`")
    lines.extend(["", "Authority: review-only/local-only. No portfolio/canon mutation, capital approval, paper/live/account action, external delivery, or owner approval inference."])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local-only market-today answer packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet, indent=2, ensure_ascii=True)
        if args.write_md:
            atomic_write_text(md_out, render_md(packet))
    print(
        json.dumps(
            {
                "status": packet.get("status"),
                "operator_action": packet.get("operator_action"),
                "out": rel(out),
                "validation": packet.get("validation"),
                "answer_readiness": packet.get("answer_readiness"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.validate and as_dict(packet.get("validation")).get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
