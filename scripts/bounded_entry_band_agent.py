#!/usr/bin/env python3
"""
Bounded Entry Band Agent
========================

Decision-support agent for maintaining stock watchlist entry bands using the
policy:

    Keltner-first, Dual-MA-gated, SMA-envelope-audited.

The agent is intentionally bounded:
  - It never places trades.
  - It never mutates the input watchlist or price files.
  - It emits proposed bands, statuses, stops, and review flags only.
  - Earnings-window, stale-data, low-history, and broken-chart states require
    human review before deployment.

Expected price input
--------------------
Either:
  1. One CSV per ticker in --prices-dir, named TICKER.csv, with columns:
       date, open, high, low, close
     Optional columns: volume, adj_close, adjusted_close

  2. A single multi-ticker CSV passed through --prices-file, with columns:
       ticker, date, open, high, low, close

Expected watchlist input
------------------------
CSV with at least:
    ticker

Optional columns:
    earnings_date, prior_band_low, prior_band_high, prior_stop,
    lane, notes, last_human_review_utc

Example usage
-------------
    python bounded_entry_band_agent.py \
      --watchlist watchlist.csv \
      --prices-dir ./prices \
      --output-csv entry_band_recommendations.csv \
      --output-md entry_band_report.md

    python bounded_entry_band_agent.py \
      --watchlist watchlist.csv \
      --prices-file all_prices.csv \
      --as-of 2026-05-06

Notes
-----
This is not investment advice. It is a reproducible rules engine for a
human-reviewed watchlist workflow.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentConfig:
    # Indicator lengths
    ema_fast_length: int = 20
    ema_mid_length: int = 50
    sma_long_length: int = 200
    sma_envelope_length: int = 50
    atr_length: int = 20
    swing_low_length: int = 63
    reclaim_lookback: int = 20

    # Keltner volatility buckets using ATRP = ATR / close
    low_vol_atrp: float = 0.015
    high_vol_atrp: float = 0.035
    low_vol_keltner_mult: float = 1.5
    mid_vol_keltner_mult: float = 2.0
    high_vol_keltner_mult: float = 2.5

    # Entry-zone construction
    keltner_high_atr_add: float = 0.25
    ma_low_atr_sub: float = 0.50
    min_band_width_atr: float = 0.25
    reclaim_high_atr_add: float = 1.25
    vault_high_atr_add: float = 1.50

    # Stop/invalidation construction
    pullback_stop_atr_sub: float = 1.25
    swing_stop_atr_sub: float = 0.25
    reclaim_stop_atr_sub: float = 1.00
    vault_stop_atr_sub: float = 1.25

    # SMA envelope audit
    sma_envelope_pct: float = 0.05

    # Update policy
    materiality_pct: float = 0.01
    near_band_pct: float = 0.02
    near_band_atr_mult: float = 0.50

    # Earnings policy
    earnings_freeze_bdays: int = 7
    post_earnings_cooldown_bdays: int = 3

    # Data-quality policy
    min_history_rows: int = 220
    stale_data_bdays: int = 5

    # Bounded-agent behavior
    require_human_review: bool = True


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------


def parse_date(value: Any) -> Optional[pd.Timestamp]:
    """Parse a date-like value; return None for blanks/NaN/invalid values."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    try:
        return pd.Timestamp(text).normalize()
    except Exception:
        return None


def safe_float(value: Any) -> Optional[float]:
    """Convert to float or return None."""
    if value is None:
        return None
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except Exception:
        return None


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def pct_change_abs(new_value: Optional[float], old_value: Optional[float]) -> Optional[float]:
    if new_value is None or old_value is None or old_value == 0:
        return None
    return abs(new_value / old_value - 1.0)


def business_days_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    """
    Return signed business-day distance from start to end.

    Example: same day -> 0, next business day -> 1, prior business day -> -1.
    """
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if start == end:
        return 0
    if start < end:
        return max(0, len(pd.bdate_range(start=start, end=end)) - 1)
    return -max(0, len(pd.bdate_range(start=end, end=start)) - 1)


def format_money(value: Optional[float]) -> str:
    if value is None or not np.isfinite(value):
        return ""
    return f"${value:,.2f}"


# -----------------------------------------------------------------------------
# Price loading and normalization
# -----------------------------------------------------------------------------


REQUIRED_PRICE_COLUMNS = {"date", "open", "high", "low", "close"}


def normalize_price_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common price-column variants to lowercase canonical names."""
    rename_map: Dict[str, str] = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        if key in {"adj_close", "adjusted_close", "adjustedclose"}:
            rename_map[col] = "adj_close"
        elif key in {"date", "datetime", "timestamp"}:
            rename_map[col] = "date"
        elif key in {"ticker", "symbol"}:
            rename_map[col] = "ticker"
        elif key in {"open", "high", "low", "close", "volume"}:
            rename_map[col] = key
        else:
            rename_map[col] = key

    df = df.rename(columns=rename_map).copy()
    missing = REQUIRED_PRICE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"price data is missing required columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    for col in ["open", "high", "low", "close", "adj_close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Prefer adjusted close for the close series if supplied. Open/high/low are
    # left as raw values because adjusted OHLC is not always available.
    if "adj_close" in df.columns and df["adj_close"].notna().any():
        df["close_raw"] = df["close"]
        df["close"] = df["adj_close"].fillna(df["close"])

    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df = df.reset_index(drop=True)
    return df


def load_watchlist(path: Optional[Path], prices_dir: Optional[Path]) -> pd.DataFrame:
    """Load watchlist or infer tickers from CSV filenames if no watchlist is given."""
    if path is not None:
        df = pd.read_csv(path)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        if "symbol" in df.columns and "ticker" not in df.columns:
            df = df.rename(columns={"symbol": "ticker"})
        if "ticker" not in df.columns:
            raise ValueError("watchlist CSV must contain a 'ticker' column")
        df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
        df = df[df["ticker"].ne("")].drop_duplicates(subset=["ticker"], keep="first")
        return df.reset_index(drop=True)

    if prices_dir is None:
        raise ValueError("provide --watchlist or --prices-dir so tickers can be inferred")

    tickers = [p.stem.upper() for p in sorted(prices_dir.glob("*.csv"))]
    if not tickers:
        raise ValueError(f"no CSV files found in {prices_dir}")
    return pd.DataFrame({"ticker": tickers})


def load_prices_map(
    tickers: Iterable[str],
    prices_dir: Optional[Path] = None,
    prices_file: Optional[Path] = None,
) -> Dict[str, pd.DataFrame]:
    """Load price data for all tickers."""
    ticker_set = {str(t).upper().strip() for t in tickers}
    prices: Dict[str, pd.DataFrame] = {}

    if prices_file is not None:
        all_prices = pd.read_csv(prices_file)
        all_prices.columns = [c.strip().lower().replace(" ", "_") for c in all_prices.columns]
        if "symbol" in all_prices.columns and "ticker" not in all_prices.columns:
            all_prices = all_prices.rename(columns={"symbol": "ticker"})
        if "ticker" not in all_prices.columns:
            raise ValueError("--prices-file must contain a 'ticker' column")
        all_prices["ticker"] = all_prices["ticker"].astype(str).str.upper().str.strip()
        for ticker, group in all_prices.groupby("ticker"):
            if ticker in ticker_set:
                prices[ticker] = normalize_price_columns(group.drop(columns=["ticker"]))

    if prices_dir is not None:
        for ticker in ticker_set:
            if ticker in prices:
                continue
            path = prices_dir / f"{ticker}.csv"
            if not path.exists():
                # Case-insensitive fallback.
                candidates = list(prices_dir.glob(f"{ticker}.*")) + list(prices_dir.glob(f"{ticker.lower()}.*"))
                candidates = [p for p in candidates if p.suffix.lower() == ".csv"]
                if candidates:
                    path = candidates[0]
            if path.exists():
                prices[ticker] = normalize_price_columns(pd.read_csv(path))

    return prices


# -----------------------------------------------------------------------------
# Indicator engine
# -----------------------------------------------------------------------------


def compute_indicators(df: pd.DataFrame, cfg: AgentConfig) -> pd.DataFrame:
    """Add EMA/SMA/ATR/Keltner/SMA-envelope audit fields."""
    data = df.copy()

    close = data["close"]
    high = data["high"]
    low = data["low"]
    prev_close = close.shift(1)

    data["ema20"] = close.ewm(span=cfg.ema_fast_length, adjust=False).mean()
    data["ema50"] = close.ewm(span=cfg.ema_mid_length, adjust=False).mean()
    data["sma50"] = close.rolling(cfg.sma_envelope_length, min_periods=cfg.sma_envelope_length).mean()
    data["sma200"] = close.rolling(cfg.sma_long_length, min_periods=cfg.sma_long_length).mean()

    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["tr"] = true_range
    data["atr20"] = true_range.rolling(cfg.atr_length, min_periods=cfg.atr_length).mean()
    data["atrp20"] = data["atr20"] / close

    data["recent_swing_low_63"] = low.rolling(cfg.swing_low_length, min_periods=cfg.swing_low_length).min()
    data["recent_reclaim_high_20"] = close.rolling(cfg.reclaim_lookback, min_periods=cfg.reclaim_lookback).max()

    # SMA envelope audit. This is not the operating band, only an audit/reference band.
    data["sma_envelope_low"] = data["sma50"] * (1.0 - cfg.sma_envelope_pct)
    data["sma_envelope_high"] = data["sma50"] * (1.0 + cfg.sma_envelope_pct)

    # ATR-multiple Keltner channel.
    data["keltner_mult"] = data["atrp20"].apply(lambda atrp: keltner_multiplier(atrp, cfg))
    data["kc_mid"] = data["ema20"]
    data["kc_low"] = data["ema20"] - data["keltner_mult"] * data["atr20"]
    data["kc_high"] = data["ema20"] + data["keltner_mult"] * data["atr20"]

    return data


def keltner_multiplier(atrp: Any, cfg: AgentConfig) -> float:
    atrp_float = safe_float(atrp)
    if atrp_float is None:
        return cfg.mid_vol_keltner_mult
    if atrp_float < cfg.low_vol_atrp:
        return cfg.low_vol_keltner_mult
    if atrp_float > cfg.high_vol_atrp:
        return cfg.high_vol_keltner_mult
    return cfg.mid_vol_keltner_mult


# -----------------------------------------------------------------------------
# Policy engine
# -----------------------------------------------------------------------------


class BoundedEntryBandAgent:
    """
    Bounded rules engine.

    The only allowed action is to emit a recommendation record. The agent never
    executes orders, edits input files, or auto-promotes a band without review.
    """

    ALLOWED_ACTIONS = {
        "PUBLISH_PROPOSAL",
        "HOLD_PRIOR_STABLE",
        "BLOCKED_BY_EARNINGS",
        "POST_EARNINGS_REVIEW",
        "REVIEW_REQUIRED",
        "NO_ACTION_ABOVE_BAND",
        "DATA_INSUFFICIENT",
        "PRICE_DATA_MISSING",
    }

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self.cfg = config or AgentConfig()

    def evaluate_watchlist(
        self,
        watchlist: pd.DataFrame,
        prices: Dict[str, pd.DataFrame],
        as_of: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        records: List[Dict[str, Any]] = []
        as_of_ts = pd.Timestamp(as_of).normalize() if as_of is not None else None

        for _, wrow in watchlist.iterrows():
            ticker = str(wrow.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            price_df = prices.get(ticker)
            if price_df is None or price_df.empty:
                records.append(self._missing_price_record(ticker, wrow, as_of_ts))
                continue

            try:
                indicators = compute_indicators(price_df, self.cfg)
                record = self.evaluate_ticker(ticker, wrow, indicators, as_of_ts)
            except Exception as exc:
                record = self._missing_price_record(ticker, wrow, as_of_ts)
                record.update(
                    {
                        "agent_action": "DATA_INSUFFICIENT",
                        "data_quality_flag": "ERROR",
                        "review_reason": f"indicator/evaluation error: {exc}",
                    }
                )
            records.append(record)

        output = pd.DataFrame(records)
        if not output.empty:
            sort_cols = [c for c in ["agent_rank", "ticker"] if c in output.columns]
            output = output.sort_values(sort_cols).reset_index(drop=True)
        return output

    def evaluate_ticker(
        self,
        ticker: str,
        watch_row: pd.Series,
        data: pd.DataFrame,
        as_of: Optional[pd.Timestamp] = None,
    ) -> Dict[str, Any]:
        cfg = self.cfg
        if as_of is None:
            as_of = pd.Timestamp(data["date"].iloc[-1]).normalize()
        else:
            as_of = pd.Timestamp(as_of).normalize()

        available = data[data["date"] <= as_of].copy()
        if available.empty:
            return self._missing_price_record(ticker, watch_row, as_of)

        row = available.iloc[-1]
        latest_date = pd.Timestamp(row["date"]).normalize()
        history_rows = len(available)
        data_quality = self._data_quality(history_rows, latest_date, as_of)

        prior_low = safe_float(watch_row.get("prior_band_low"))
        prior_high = safe_float(watch_row.get("prior_band_high"))
        prior_stop = safe_float(watch_row.get("prior_stop"))
        earnings_date = parse_date(watch_row.get("earnings_date"))
        earnings_state = self._earnings_state(as_of, earnings_date)
        trend_state = self._trend_state(row)

        missing_core = any(
            safe_float(row.get(col)) is None
            for col in ["close", "ema20", "ema50", "sma200", "atr20", "kc_low", "kc_high"]
        )
        if missing_core or data_quality in {"LOW_HISTORY", "ERROR"}:
            return self._insufficient_record(
                ticker=ticker,
                watch_row=watch_row,
                row=row,
                as_of=as_of,
                latest_date=latest_date,
                history_rows=history_rows,
                data_quality=data_quality,
                earnings_state=earnings_state,
                trend_state=trend_state,
                prior_low=prior_low,
                prior_high=prior_high,
                prior_stop=prior_stop,
            )

        proposed = self._propose_band(row, trend_state, earnings_state, prior_low, prior_high, prior_stop)
        final_band = self._apply_materiality_policy(proposed, prior_low, prior_high, earnings_state)

        band_status, distance_pct, direction = self._classify_price_vs_band(
            close=float(row["close"]),
            atr=float(row["atr20"]),
            entry_low=final_band["entry_band_low"],
            entry_high=final_band["entry_band_high"],
            stop=final_band["stop_price"],
        )
        final_band["band_status"] = band_status
        final_band["distance_to_band_pct"] = distance_pct
        final_band["direction_to_band"] = direction

        action, review_reason = self._bounded_action(
            band_status=band_status,
            trend_state=trend_state,
            earnings_state=earnings_state,
            data_quality=data_quality,
            materiality_action=final_band.get("materiality_action"),
        )
        confidence = self._confidence_score(
            trend_state=trend_state,
            earnings_state=earnings_state,
            data_quality=data_quality,
            band_status=band_status,
            atrp=float(row["atrp20"]),
            history_rows=history_rows,
        )

        record = {
            "ticker": ticker,
            "as_of": as_of.date().isoformat(),
            "price_date": latest_date.date().isoformat(),
            "close": round(float(row["close"]), 4),
            "entry_band_low": round(final_band["entry_band_low"], 4),
            "entry_band_high": round(final_band["entry_band_high"], 4),
            "entry_band_method": final_band["entry_band_method"],
            "entry_band_type": final_band["entry_band_type"],
            "band_status": band_status,
            "distance_to_band_pct": round(distance_pct, 4),
            "direction_to_band": direction,
            "stop_price": round(final_band["stop_price"], 4),
            "stop_basis": final_band["stop_basis"],
            "trend_stack": trend_state,
            "earnings_state": earnings_state,
            "earnings_date": earnings_date.date().isoformat() if earnings_date is not None else "",
            "band_confidence": confidence,
            "agent_action": action,
            "needs_human_review": bool(self.cfg.require_human_review or action != "PUBLISH_PROPOSAL"),
            "review_reason": review_reason,
            "data_quality_flag": data_quality,
            "history_rows": int(history_rows),
            "atr20": round(float(row["atr20"]), 4),
            "atrp20": round(float(row["atrp20"]), 6),
            "ema20": round(float(row["ema20"]), 4),
            "ema50": round(float(row["ema50"]), 4),
            "sma200": round(float(row["sma200"]), 4),
            "keltner_mult": round(float(row["keltner_mult"]), 4),
            "kc_low": round(float(row["kc_low"]), 4),
            "kc_mid": round(float(row["kc_mid"]), 4),
            "kc_high": round(float(row["kc_high"]), 4),
            "sma_envelope_low": self._round_or_blank(row.get("sma_envelope_low")),
            "sma_envelope_high": self._round_or_blank(row.get("sma_envelope_high")),
            "prior_band_low": prior_low if prior_low is not None else "",
            "prior_band_high": prior_high if prior_high is not None else "",
            "materiality_action": final_band.get("materiality_action", ""),
            "underlying_entry_band_method": final_band.get("underlying_entry_band_method", ""),
            "underlying_entry_band_type": final_band.get("underlying_entry_band_type", ""),
            "agent_rank": self._rank_record(action, band_status, trend_state, distance_pct),
            "lane": watch_row.get("lane", ""),
            "notes": watch_row.get("notes", ""),
            "engine_version": "bounded_entry_band_agent_v1.0",
        }
        self._assert_action_is_bounded(record["agent_action"])
        return record

    def _propose_band(
        self,
        row: pd.Series,
        trend_state: str,
        earnings_state: str,
        prior_low: Optional[float],
        prior_high: Optional[float],
        prior_stop: Optional[float],
    ) -> Dict[str, Any]:
        cfg = self.cfg
        close = float(row["close"])
        atr = float(row["atr20"])
        ema20 = float(row["ema20"])
        ema50 = float(row["ema50"])
        sma200 = float(row["sma200"])
        kc_low = float(row["kc_low"])
        kc_mid = float(row["kc_mid"])
        recent_swing_low = float(row["recent_swing_low_63"])
        recent_reclaim_high = float(row["recent_reclaim_high_20"])

        # Earnings freeze: keep old band if available. If not, calculate a band
        # but mark it blocked, so the user can see the proposed mechanical level.
        if earnings_state == "EARNINGS_FROZEN" and prior_low is not None and prior_high is not None:
            stop = prior_stop if prior_stop is not None else max(0.01, prior_low - cfg.pullback_stop_atr_sub * atr)
            return {
                "entry_band_low": prior_low,
                "entry_band_high": prior_high,
                "entry_band_method": "EARNINGS_FROZEN",
                "entry_band_type": "FROZEN_PRIOR_BAND",
                "stop_price": stop,
                "stop_basis": "prior band retained during earnings freeze",
            }

        # Broken chart / reclaim-only mode.
        if trend_state == "BELOW_200_OR_ALL_MAS":
            reclaim_low = max(ema50, sma200, recent_reclaim_high)
            entry_low = reclaim_low
            entry_high = reclaim_low + cfg.vault_high_atr_add * atr
            stop = max(0.01, reclaim_low - cfg.vault_stop_atr_sub * atr)
            return {
                "entry_band_low": entry_low,
                "entry_band_high": entry_high,
                "entry_band_method": "DUAL_MA_RECLAIM",
                "entry_band_type": "BELOW_STOP_VAULT",
                "stop_price": stop,
                "stop_basis": "vault reclaim: max(EMA50, SMA200, 20d reclaim high) - 1.25 ATR",
            }

        # Above the 200-day but below fast/mid MAs: require reclaim.
        if trend_state == "ABOVE_200_BELOW_FAST_MA":
            reclaim_low = max(ema50, sma200, recent_reclaim_high)
            entry_low = reclaim_low
            entry_high = reclaim_low + cfg.reclaim_high_atr_add * atr
            stop = max(0.01, reclaim_low - cfg.reclaim_stop_atr_sub * atr)
            return {
                "entry_band_low": entry_low,
                "entry_band_high": entry_high,
                "entry_band_method": "DUAL_MA_RECLAIM",
                "entry_band_type": "RECLAIM_ONLY",
                "stop_price": stop,
                "stop_basis": "reclaim: max(EMA50, SMA200, 20d reclaim high) - 1.0 ATR",
            }

        # Bullish / constructive / mixed charts: Keltner is primary, constrained
        # by the Dual-MA stack.
        kc_zone_low = kc_low
        kc_zone_high = kc_mid + cfg.keltner_high_atr_add * atr
        ma_zone_low = ema50 - cfg.ma_low_atr_sub * atr
        ma_zone_high = ema20 + cfg.keltner_high_atr_add * atr

        entry_low = max(kc_zone_low, ma_zone_low)
        entry_high = min(kc_zone_high, ma_zone_high)
        width = entry_high - entry_low

        if width <= cfg.min_band_width_atr * atr:
            # Fallback keeps the band valid without abandoning Keltner/MA logic.
            entry_low = max(kc_zone_low, ema50 - cfg.ma_low_atr_sub * atr)
            entry_high = ema20 + cfg.keltner_high_atr_add * atr

        if trend_state == "BULLISH_STACK":
            method = "KELTNER_MA_CONSTRAINED"
            band_type = "PULLBACK_BAND"
        elif trend_state == "ABOVE_ALL_EXTENDED":
            method = "KELTNER_MA_CONSTRAINED"
            band_type = "WAIT_FOR_PULLBACK"
        elif trend_state in {"ABOVE_ALL_UNSTACKED", "CONSTRUCTIVE_PULLBACK"}:
            method = "KELTNER_MA_CONSTRAINED"
            band_type = "CONSTRUCTIVE_BAND"
        else:
            method = "KELTNER_PRIMARY"
            band_type = "MIXED_TREND_BAND"

        stop = min(
            entry_low - cfg.pullback_stop_atr_sub * atr,
            recent_swing_low - cfg.swing_stop_atr_sub * atr,
        )
        stop = max(0.01, stop)

        if earnings_state == "EARNINGS_FROZEN":
            method = "EARNINGS_FROZEN"
            band_type = "FROZEN_CALCULATED_REVIEW_ONLY"
        elif earnings_state == "POST_EARNINGS_COOLDOWN":
            band_type = f"{band_type}_POST_EARNINGS_REVIEW"

        return {
            "entry_band_low": entry_low,
            "entry_band_high": entry_high,
            "entry_band_method": method,
            "entry_band_type": band_type,
            "stop_price": stop,
            "stop_basis": "pullback: min(entry_low - 1.25 ATR, 63d swing low - 0.25 ATR)",
        }

    def _apply_materiality_policy(
        self,
        proposed: Dict[str, Any],
        prior_low: Optional[float],
        prior_high: Optional[float],
        earnings_state: str,
    ) -> Dict[str, Any]:
        cfg = self.cfg
        result = dict(proposed)

        if earnings_state == "EARNINGS_FROZEN":
            result["underlying_entry_band_method"] = result.get("entry_band_method", "")
            result["underlying_entry_band_type"] = result.get("entry_band_type", "")
            result["entry_band_method"] = "EARNINGS_FROZEN"
            if result.get("entry_band_type") != "FROZEN_PRIOR_BAND":
                result["entry_band_type"] = f"FROZEN_REVIEW_ONLY__{result.get('entry_band_type', 'CALCULATED_BAND')}"
            result["materiality_action"] = "FROZEN_FOR_EARNINGS"
            return result

        if prior_low is None or prior_high is None:
            result["materiality_action"] = "NEW_BAND"
            return result

        low_delta = pct_change_abs(result["entry_band_low"], prior_low)
        high_delta = pct_change_abs(result["entry_band_high"], prior_high)
        max_delta = max(low_delta or 0.0, high_delta or 0.0)

        if max_delta < cfg.materiality_pct:
            result["entry_band_low"] = prior_low
            result["entry_band_high"] = prior_high
            result["materiality_action"] = "HOLD_PRIOR_STABLE"
        else:
            result["materiality_action"] = "MATERIAL_UPDATE"

        return result

    def _trend_state(self, row: pd.Series) -> str:
        close = safe_float(row.get("close"))
        ema20 = safe_float(row.get("ema20"))
        ema50 = safe_float(row.get("ema50"))
        sma200 = safe_float(row.get("sma200"))
        atr = safe_float(row.get("atr20"))
        kc_high = safe_float(row.get("kc_high"))

        if None in {close, ema20, ema50, sma200, atr, kc_high}:
            return "INSUFFICIENT_DATA"

        assert close is not None and ema20 is not None and ema50 is not None and sma200 is not None
        assert atr is not None and kc_high is not None

        above_all = close > ema20 and close > ema50 and close > sma200
        bullish_stack = close > ema20 > ema50 > sma200
        below_all = close < ema20 and close < ema50 and close < sma200

        if close < sma200 or below_all:
            return "BELOW_200_OR_ALL_MAS"
        if close > sma200 and close < ema20 and close < ema50:
            return "ABOVE_200_BELOW_FAST_MA"
        if bullish_stack and close > kc_high:
            return "ABOVE_ALL_EXTENDED"
        if bullish_stack:
            return "BULLISH_STACK"
        if above_all:
            return "ABOVE_ALL_UNSTACKED"
        if close > sma200 and (close < ema20 or close < ema50):
            return "CONSTRUCTIVE_PULLBACK"
        return "MIXED"

    def _earnings_state(self, as_of: pd.Timestamp, earnings_date: Optional[pd.Timestamp]) -> str:
        if earnings_date is None:
            return "NONE"
        days = business_days_between(as_of, earnings_date)
        if 0 <= days <= self.cfg.earnings_freeze_bdays:
            return "EARNINGS_FROZEN"
        if -self.cfg.post_earnings_cooldown_bdays <= days < 0:
            return "POST_EARNINGS_COOLDOWN"
        if days < -self.cfg.post_earnings_cooldown_bdays:
            return "POST_EARNINGS_CLEAR"
        return "NONE"

    def _classify_price_vs_band(
        self,
        close: float,
        atr: float,
        entry_low: float,
        entry_high: float,
        stop: float,
    ) -> Tuple[str, float, str]:
        near_abs = max(self.cfg.near_band_pct * close, self.cfg.near_band_atr_mult * atr)

        if close < stop:
            distance = ((stop - close) / close) * 100.0
            return "BELOW_STOP", distance, "below_stop"

        if entry_low <= close <= entry_high:
            return "IN_BAND", 0.0, "in_band"

        if close > entry_high:
            distance = ((close - entry_high) / close) * 100.0
            if close - entry_high <= near_abs:
                return "NEAR_BAND", distance, "above_band_near"
            return "ABOVE_BAND", distance, "above_band"

        distance = ((entry_low - close) / close) * 100.0
        if entry_low - close <= near_abs:
            return "NEAR_BAND", distance, "below_band_near"
        return "BELOW_BAND", distance, "below_band"

    def _bounded_action(
        self,
        band_status: str,
        trend_state: str,
        earnings_state: str,
        data_quality: str,
        materiality_action: Optional[str],
    ) -> Tuple[str, str]:
        if data_quality not in {"OK", "STALE"}:
            return "DATA_INSUFFICIENT", f"data quality flag is {data_quality}"
        if data_quality == "STALE":
            return "REVIEW_REQUIRED", "price data is stale"
        if earnings_state == "EARNINGS_FROZEN":
            return "BLOCKED_BY_EARNINGS", "normal band is frozen inside earnings risk window"
        if earnings_state == "POST_EARNINGS_COOLDOWN":
            return "POST_EARNINGS_REVIEW", "post-earnings range not fully established"
        if band_status == "BELOW_STOP":
            return "REVIEW_REQUIRED", "price is below technical invalidation"
        if trend_state in {"BELOW_200_OR_ALL_MAS", "ABOVE_200_BELOW_FAST_MA"}:
            return "REVIEW_REQUIRED", "reclaim-only or vault-band state"
        if materiality_action == "HOLD_PRIOR_STABLE":
            return "HOLD_PRIOR_STABLE", "new band change is below materiality threshold"
        if band_status in {"IN_BAND", "NEAR_BAND"}:
            return "PUBLISH_PROPOSAL", "actionable band proposal requires human gate"
        if band_status == "ABOVE_BAND":
            return "NO_ACTION_ABOVE_BAND", "price is above the proposed entry band; avoid chasing"
        return "REVIEW_REQUIRED", "mixed state requires review"

    def _confidence_score(
        self,
        trend_state: str,
        earnings_state: str,
        data_quality: str,
        band_status: str,
        atrp: float,
        history_rows: int,
    ) -> int:
        score = 50.0

        trend_adjust = {
            "BULLISH_STACK": 22,
            "ABOVE_ALL_EXTENDED": 12,
            "ABOVE_ALL_UNSTACKED": 10,
            "CONSTRUCTIVE_PULLBACK": 8,
            "MIXED": -2,
            "ABOVE_200_BELOW_FAST_MA": -8,
            "BELOW_200_OR_ALL_MAS": -18,
            "INSUFFICIENT_DATA": -30,
        }
        score += trend_adjust.get(trend_state, 0)

        status_adjust = {
            "IN_BAND": 10,
            "NEAR_BAND": 6,
            "ABOVE_BAND": -4,
            "BELOW_BAND": -6,
            "BELOW_STOP": -24,
        }
        score += status_adjust.get(band_status, 0)

        if earnings_state == "EARNINGS_FROZEN":
            score -= 30
        elif earnings_state == "POST_EARNINGS_COOLDOWN":
            score -= 15

        if data_quality == "STALE":
            score -= 15
        elif data_quality != "OK":
            score -= 30

        if history_rows >= 300:
            score += 5
        if atrp > 0.06:
            score -= 10
        elif atrp > 0.04:
            score -= 5

        return int(round(clamp(score, 0, 100)))

    def _data_quality(self, history_rows: int, latest_date: pd.Timestamp, as_of: pd.Timestamp) -> str:
        if history_rows < self.cfg.min_history_rows:
            return "LOW_HISTORY"
        lag = business_days_between(latest_date, as_of)
        if lag > self.cfg.stale_data_bdays:
            return "STALE"
        return "OK"

    def _rank_record(self, action: str, band_status: str, trend_state: str, distance_pct: float) -> int:
        action_rank = {
            "PUBLISH_PROPOSAL": 10,
            "HOLD_PRIOR_STABLE": 20,
            "NO_ACTION_ABOVE_BAND": 30,
            "REVIEW_REQUIRED": 40,
            "POST_EARNINGS_REVIEW": 50,
            "BLOCKED_BY_EARNINGS": 60,
            "DATA_INSUFFICIENT": 90,
            "PRICE_DATA_MISSING": 99,
        }.get(action, 80)
        status_bonus = {"IN_BAND": 0, "NEAR_BAND": 2, "ABOVE_BAND": 8, "BELOW_BAND": 8, "BELOW_STOP": 20}.get(band_status, 10)
        trend_bonus = {"BULLISH_STACK": 0, "ABOVE_ALL_EXTENDED": 4, "CONSTRUCTIVE_PULLBACK": 6}.get(trend_state, 8)
        distance_bonus = int(min(20, max(0, distance_pct)))
        return action_rank + status_bonus + trend_bonus + distance_bonus

    def _insufficient_record(
        self,
        ticker: str,
        watch_row: pd.Series,
        row: pd.Series,
        as_of: pd.Timestamp,
        latest_date: pd.Timestamp,
        history_rows: int,
        data_quality: str,
        earnings_state: str,
        trend_state: str,
        prior_low: Optional[float],
        prior_high: Optional[float],
        prior_stop: Optional[float],
    ) -> Dict[str, Any]:
        close = safe_float(row.get("close"))
        record = {
            "ticker": ticker,
            "as_of": as_of.date().isoformat(),
            "price_date": latest_date.date().isoformat(),
            "close": close if close is not None else "",
            "entry_band_low": prior_low if prior_low is not None else "",
            "entry_band_high": prior_high if prior_high is not None else "",
            "entry_band_method": "DATA_INSUFFICIENT",
            "entry_band_type": "NO_NEW_BAND",
            "band_status": "UNKNOWN",
            "distance_to_band_pct": "",
            "direction_to_band": "unknown",
            "stop_price": prior_stop if prior_stop is not None else "",
            "stop_basis": "prior stop retained if available",
            "trend_stack": trend_state,
            "earnings_state": earnings_state,
            "earnings_date": parse_date(watch_row.get("earnings_date")).date().isoformat()
            if parse_date(watch_row.get("earnings_date")) is not None
            else "",
            "band_confidence": 0,
            "agent_action": "DATA_INSUFFICIENT",
            "needs_human_review": True,
            "review_reason": f"insufficient usable history or indicators; data_quality={data_quality}",
            "data_quality_flag": data_quality,
            "history_rows": history_rows,
            "atr20": self._round_or_blank(row.get("atr20")),
            "atrp20": self._round_or_blank(row.get("atrp20")),
            "ema20": self._round_or_blank(row.get("ema20")),
            "ema50": self._round_or_blank(row.get("ema50")),
            "sma200": self._round_or_blank(row.get("sma200")),
            "keltner_mult": self._round_or_blank(row.get("keltner_mult")),
            "kc_low": self._round_or_blank(row.get("kc_low")),
            "kc_mid": self._round_or_blank(row.get("kc_mid")),
            "kc_high": self._round_or_blank(row.get("kc_high")),
            "sma_envelope_low": self._round_or_blank(row.get("sma_envelope_low")),
            "sma_envelope_high": self._round_or_blank(row.get("sma_envelope_high")),
            "prior_band_low": prior_low if prior_low is not None else "",
            "prior_band_high": prior_high if prior_high is not None else "",
            "materiality_action": "NO_UPDATE",
            "underlying_entry_band_method": "",
            "underlying_entry_band_type": "",
            "agent_rank": 90,
            "lane": watch_row.get("lane", ""),
            "notes": watch_row.get("notes", ""),
            "engine_version": "bounded_entry_band_agent_v1.0",
        }
        self._assert_action_is_bounded(record["agent_action"])
        return record

    def _missing_price_record(
        self,
        ticker: str,
        watch_row: pd.Series,
        as_of: Optional[pd.Timestamp],
    ) -> Dict[str, Any]:
        as_of_str = as_of.date().isoformat() if as_of is not None else ""
        prior_low = safe_float(watch_row.get("prior_band_low"))
        prior_high = safe_float(watch_row.get("prior_band_high"))
        prior_stop = safe_float(watch_row.get("prior_stop"))
        record = {
            "ticker": ticker,
            "as_of": as_of_str,
            "price_date": "",
            "close": "",
            "entry_band_low": prior_low if prior_low is not None else "",
            "entry_band_high": prior_high if prior_high is not None else "",
            "entry_band_method": "PRICE_DATA_MISSING",
            "entry_band_type": "NO_NEW_BAND",
            "band_status": "UNKNOWN",
            "distance_to_band_pct": "",
            "direction_to_band": "unknown",
            "stop_price": prior_stop if prior_stop is not None else "",
            "stop_basis": "prior stop retained if available",
            "trend_stack": "UNKNOWN",
            "earnings_state": "UNKNOWN",
            "earnings_date": "",
            "band_confidence": 0,
            "agent_action": "PRICE_DATA_MISSING",
            "needs_human_review": True,
            "review_reason": "no price data found for ticker",
            "data_quality_flag": "MISSING",
            "history_rows": 0,
            "atr20": "",
            "atrp20": "",
            "ema20": "",
            "ema50": "",
            "sma200": "",
            "keltner_mult": "",
            "kc_low": "",
            "kc_mid": "",
            "kc_high": "",
            "sma_envelope_low": "",
            "sma_envelope_high": "",
            "prior_band_low": prior_low if prior_low is not None else "",
            "prior_band_high": prior_high if prior_high is not None else "",
            "materiality_action": "NO_UPDATE",
            "underlying_entry_band_method": "",
            "underlying_entry_band_type": "",
            "agent_rank": 99,
            "lane": watch_row.get("lane", ""),
            "notes": watch_row.get("notes", ""),
            "engine_version": "bounded_entry_band_agent_v1.0",
        }
        self._assert_action_is_bounded(record["agent_action"])
        return record

    @staticmethod
    def _round_or_blank(value: Any, ndigits: int = 4) -> Any:
        value_float = safe_float(value)
        if value_float is None:
            return ""
        return round(value_float, ndigits)

    def _assert_action_is_bounded(self, action: str) -> None:
        if action not in self.ALLOWED_ACTIONS:
            raise RuntimeError(f"unbounded/unknown agent action emitted: {action}")


# -----------------------------------------------------------------------------
# Markdown reporting
# -----------------------------------------------------------------------------


def write_markdown_report(output: pd.DataFrame, path: Path, cfg: AgentConfig) -> None:
    lines: List[str] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines.append("# Entry Band Agent Report")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")
    lines.append("Policy: **Keltner-first, Dual-MA-gated, SMA-envelope-audited**.")
    lines.append("")
    lines.append("Bounded-agent constraints: no trade execution, no input mutation, human review required before deployment.")
    lines.append("")

    if output.empty:
        lines.append("No records generated.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    counts = output["agent_action"].value_counts().to_dict()
    lines.append("## Action Summary")
    lines.append("")
    for action, count in counts.items():
        lines.append(f"- **{action}**: {count}")
    lines.append("")

    display_cols = [
        "ticker",
        "close",
        "entry_band_low",
        "entry_band_high",
        "band_status",
        "entry_band_type",
        "stop_price",
        "trend_stack",
        "earnings_state",
        "band_confidence",
        "agent_action",
    ]
    display_cols = [c for c in display_cols if c in output.columns]
    report_df = output[display_cols].copy()

    for col in ["close", "entry_band_low", "entry_band_high", "stop_price"]:
        if col in report_df.columns:
            report_df[col] = report_df[col].apply(lambda x: format_money(safe_float(x)))

    lines.append("## Watchlist Bands")
    lines.append("")
    lines.append(report_df.to_markdown(index=False))
    lines.append("")

    lines.append("## Configuration")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(asdict(cfg), indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded entry-band agent for stock watchlists.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--watchlist", type=Path, help="Watchlist CSV with ticker and optional metadata.")
    parser.add_argument("--prices-dir", type=Path, help="Directory containing one price CSV per ticker.")
    parser.add_argument("--prices-file", type=Path, help="Single multi-ticker price CSV.")
    parser.add_argument("--as-of", type=str, help="Evaluation date, e.g. 2026-05-06. Defaults to latest price date per ticker.")
    parser.add_argument("--output-csv", type=Path, default=Path("entry_band_recommendations.csv"), help="Output CSV path.")
    parser.add_argument("--output-md", type=Path, help="Optional Markdown report path.")
    parser.add_argument("--output-json", type=Path, help="Optional JSON records path.")

    parser.add_argument("--sma-envelope-pct", type=float, default=AgentConfig.sma_envelope_pct, help="SMA envelope audit percentage.")
    parser.add_argument("--materiality-pct", type=float, default=AgentConfig.materiality_pct, help="Minimum band delta before replacing prior band.")
    parser.add_argument("--near-band-pct", type=float, default=AgentConfig.near_band_pct, help="Percent threshold for NEAR_BAND.")
    parser.add_argument("--earnings-freeze-bdays", type=int, default=AgentConfig.earnings_freeze_bdays, help="Business days before earnings to freeze bands.")
    parser.add_argument("--post-earnings-cooldown-bdays", type=int, default=AgentConfig.post_earnings_cooldown_bdays, help="Business days after earnings requiring review.")
    parser.add_argument("--min-history-rows", type=int, default=AgentConfig.min_history_rows, help="Minimum daily rows required for new bands.")
    parser.add_argument("--stale-data-bdays", type=int, default=AgentConfig.stale_data_bdays, help="Max allowed business-day lag from as-of date.")
    parser.add_argument("--no-human-review-required", action="store_true", help="Set needs_human_review false for clean PUBLISH_PROPOSAL records only.")
    return parser


def config_from_args(args: argparse.Namespace) -> AgentConfig:
    return AgentConfig(
        sma_envelope_pct=args.sma_envelope_pct,
        materiality_pct=args.materiality_pct,
        near_band_pct=args.near_band_pct,
        earnings_freeze_bdays=args.earnings_freeze_bdays,
        post_earnings_cooldown_bdays=args.post_earnings_cooldown_bdays,
        min_history_rows=args.min_history_rows,
        stale_data_bdays=args.stale_data_bdays,
        require_human_review=not args.no_human_review_required,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.prices_dir is None and args.prices_file is None:
        parser.error("provide --prices-dir or --prices-file")

    cfg = config_from_args(args)
    as_of = parse_date(args.as_of) if args.as_of else None

    watchlist = load_watchlist(args.watchlist, args.prices_dir)
    prices = load_prices_map(
        tickers=watchlist["ticker"].tolist(),
        prices_dir=args.prices_dir,
        prices_file=args.prices_file,
    )

    agent = BoundedEntryBandAgent(cfg)
    output = agent.evaluate_watchlist(watchlist, prices, as_of=as_of)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output_csv, index=False)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(output.to_json(orient="records", indent=2), encoding="utf-8")

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown_report(output, args.output_md, cfg)

    print(f"Wrote {len(output)} records to {args.output_csv}")
    if args.output_md:
        print(f"Wrote Markdown report to {args.output_md}")
    if args.output_json:
        print(f"Wrote JSON records to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
