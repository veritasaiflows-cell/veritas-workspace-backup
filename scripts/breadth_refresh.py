"""breadth_refresh.py

Build the dedicated market-breadth artifact for the finance OS.

Tier-1 breadth layer — two signals:
1. Equal-weight vs. cap-weight: RSP / SPY ratio and its 5d / 20d trend.
2. Sector participation: count of 11 SPDR sector ETFs trading above their 50-day SMA.

Both signals require live price history; yfinance is the sole data source.
This script is intended to run on Windows where yfinance is available. The
py_compile check passes in the sandbox; live execution is deferred to Windows.

Usage:
    python scripts/breadth_refresh.py

Writes:
- tmp/breadth-state.json
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import yfinance as yf

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
OUT_PATH = WORKSPACE / "tmp" / "breadth-state.json"
STALE_AFTER_HOURS = 24
EXPECTED_UPDATE_WINDOW = (
    "Refresh after the close for overnight regime context and before weekly macro outputs. "
    "Refresh again on any session with significant intraday breadth divergence."
)

# RSP = Invesco S&P 500 Equal Weight ETF; SPY = SPDR S&P 500 ETF Trust
RSP_TICKER = "RSP"
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

FLAT_RATIO_THRESHOLD_PCT = 0.10   # 0.10% change in RSP/SPY ratio treated as flat
SMA_WINDOW = 50
HISTORY_PERIOD = "4mo"            # enough for 50-day SMA plus buffer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_write_json(path: Path, obj: Any) -> None:
    atomic_write_json(path, obj, indent=2, default=str, ensure_ascii=True)


def fetch_price_history(ticker: str, period: str = HISTORY_PERIOD) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch daily close history via yfinance. Returns list of {date, close} dicts ascending."""
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if hist.empty:
            return [], f"{ticker}: no price history"
        closes = hist.get("Close")
        if closes is None or closes.empty:
            return [], f"{ticker}: close series missing"
        closes = closes.dropna()
        if closes.empty:
            return [], f"{ticker}: close series empty after dropna"
        out: list[dict[str, Any]] = []
        for idx, value in closes.items():
            out.append({
                "date": idx.strftime("%Y-%m-%d"),
                "close": round(float(value), 4),
            })
        return out, None
    except Exception as exc:
        return [], f"{ticker}: {exc}"


def ratio_series(num_series: list[dict[str, Any]], den_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Align two close series by date and compute num/den ratio."""
    den_map = {row["date"]: row["close"] for row in den_series}
    out: list[dict[str, Any]] = []
    for row in num_series:
        d = row["date"]
        den_val = den_map.get(d)
        if den_val and den_val != 0:
            out.append({"date": d, "ratio": round(row["close"] / den_val, 6)})
    return out


def pct_change(series: list[dict[str, Any]], key: str, lookback: int) -> float | None:
    if len(series) <= lookback:
        return None
    current = series[-1][key]
    prior = series[-1 - lookback][key]
    if current is None or prior in (None, 0):
        return None
    return round(((float(current) - float(prior)) / float(prior)) * 100.0, 4)


def classify_direction(change_pct: float | None, threshold: float = FLAT_RATIO_THRESHOLD_PCT) -> str | None:
    if change_pct is None:
        return None
    if change_pct > threshold:
        return "improving"
    if change_pct < -threshold:
        return "deteriorating"
    return "flat"


def compute_sma(series: list[dict[str, Any]], window: int = SMA_WINDOW) -> float | None:
    if len(series) < window:
        return None
    closes = [row["close"] for row in series[-window:]]
    return round(sum(closes) / len(closes), 4)


def classify_breadth_regime(
    above_count: int,
    total: int,
    rsp_spy_direction: str | None,
) -> str:
    """
    Classify overall breadth regime from sector participation + RSP/SPY trend.

    broad        — >= 7/11 sectors above 50DMA and RSP/SPY not deteriorating
    recovering   — >= 6/11 sectors but RSP/SPY improving OR >= 7 sectors with deteriorating RSP/SPY
    narrow       — < 5/11 sectors above 50DMA
    deteriorating — >= 5 sectors but RSP/SPY deteriorating and participation <= 6
    mixed        — all other states
    """
    if total == 0:
        return "mixed"
    pct = above_count / total
    if pct >= (7 / 11) and rsp_spy_direction != "deteriorating":
        return "broad"
    if pct >= (7 / 11) and rsp_spy_direction == "deteriorating":
        return "recovering"
    if pct >= (6 / 11) and rsp_spy_direction == "improving":
        return "recovering"
    if pct < (5 / 11):
        return "narrow"
    if rsp_spy_direction == "deteriorating":
        return "deteriorating"
    return "mixed"


def composite_breadth_score(above_count: int, total: int, rsp_spy_change_5d: float | None) -> float | None:
    """
    Simple 0–1 composite: 70% weight on sector participation pct, 30% on RSP/SPY 5d momentum.
    RSP/SPY 5d change is capped at ±2% for the momentum component.
    """
    if total == 0:
        return None
    participation_score = above_count / total
    if rsp_spy_change_5d is None:
        return round(participation_score, 4)
    momentum_raw = max(-2.0, min(2.0, rsp_spy_change_5d))
    momentum_score = (momentum_raw + 2.0) / 4.0   # normalise to 0–1
    return round(0.70 * participation_score + 0.30 * momentum_score, 4)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    warnings: list[str] = []
    freshness_notes: list[str] = [
        "breadth_signals_based_on_daily_closes_not_intraday",
        "sector_50dma_computed_from_rolling_50_trading_day_close_average",
    ]

    print("Refreshing market breadth...")

    # --- 1. RSP / SPY ratio ---
    rsp_series, rsp_error = fetch_price_history(RSP_TICKER)
    spy_series, spy_error = fetch_price_history(SPY_TICKER)

    if rsp_error:
        warnings.append(f"RSP fetch failed: {rsp_error}")
    if spy_error:
        warnings.append(f"SPY fetch failed: {spy_error}")

    rsp_spy_ratio: float | None = None
    rsp_spy_ratio_5d: float | None = None
    rsp_spy_ratio_20d: float | None = None
    rsp_close: float | None = None
    spy_close: float | None = None
    rsp_as_of: str | None = None
    spy_as_of: str | None = None
    rsp_spy_direction: str | None = None
    ratio_hist: list[dict[str, Any]] = []

    if rsp_series and spy_series:
        ratio_hist = ratio_series(rsp_series, spy_series)
        if ratio_hist:
            rsp_spy_ratio = ratio_hist[-1]["ratio"]
            rsp_spy_ratio_5d = pct_change(ratio_hist, "ratio", 5)
            rsp_spy_ratio_20d = pct_change(ratio_hist, "ratio", 20)
            rsp_spy_direction = classify_direction(rsp_spy_ratio_5d)
        rsp_close = rsp_series[-1]["close"] if rsp_series else None
        spy_close = spy_series[-1]["close"] if spy_series else None
        rsp_as_of = rsp_series[-1]["date"] if rsp_series else None
        spy_as_of = spy_series[-1]["date"] if spy_series else None
        print(f"  RSP/SPY ratio ........ {rsp_spy_ratio} ({rsp_as_of}), 5d chg: {rsp_spy_ratio_5d}%")
    else:
        warnings.append("RSP/SPY ratio unavailable — both series required.")
        print("  RSP/SPY ratio ........ FAILED")

    # --- 2. Sector participation ---
    sectors_above_50dma = 0
    sectors_total = len(SECTOR_ETFS)
    sector_records: list[dict[str, Any]] = []
    sector_errors: list[str] = []
    sector_as_of_dates: list[str] = []

    for ticker, label in SECTOR_ETFS.items():
        series, error = fetch_price_history(ticker)
        if error or not series:
            sector_errors.append(f"{ticker}: {error or 'empty series'}")
            sector_records.append({
                "ticker": ticker,
                "label": label,
                "close": None,
                "sma_50": None,
                "above_50dma": None,
                "as_of": None,
                "error": error,
            })
            continue

        close = series[-1]["close"]
        as_of = series[-1]["date"]
        sma_50 = compute_sma(series, window=SMA_WINDOW)
        above = (close > sma_50) if (sma_50 is not None) else None

        if above is True:
            sectors_above_50dma += 1

        sector_as_of_dates.append(as_of)
        sector_records.append({
            "ticker": ticker,
            "label": label,
            "close": close,
            "sma_50": sma_50,
            "above_50dma": above,
            "as_of": as_of,
        })

    if sector_errors:
        warnings.append("Sector ETF fetch gaps: " + "; ".join(sector_errors))

    participation_pct = round(sectors_above_50dma / sectors_total * 100.0, 1) if sectors_total else None

    if sectors_above_50dma >= 7:
        participation_regime = "broad"
    elif sectors_above_50dma <= 4:
        participation_regime = "narrow"
    else:
        participation_regime = "mixed"

    print(f"  Sectors above 50DMA .. {sectors_above_50dma}/{sectors_total} ({participation_pct}%) — {participation_regime}")

    # --- 3. Composite breadth regime ---
    breadth_regime = classify_breadth_regime(sectors_above_50dma, sectors_total, rsp_spy_direction)
    composite_score = composite_breadth_score(sectors_above_50dma, sectors_total, rsp_spy_ratio_5d)

    print(f"  Breadth regime ....... {breadth_regime}  (composite score: {composite_score})")

    # --- Status ---
    has_rsp_spy = rsp_spy_ratio is not None
    has_sector = sectors_above_50dma > 0 or len(sector_records) > 0
    sectors_with_data = sum(1 for r in sector_records if r.get("above_50dma") is not None)

    if not has_rsp_spy and sectors_with_data == 0:
        status = "error"
        warnings.append("No breadth data available from any source.")
    elif not has_rsp_spy or sectors_with_data < sectors_total:
        status = "partial"
    else:
        status = "ok"

    # --- Date tracking ---
    all_dates = [d for d in (rsp_as_of, spy_as_of) + tuple(sector_as_of_dates) if d]
    last_trading_day = max(all_dates) if all_dates else None

    source_last_trading_day: dict[str, str | None] = {
        "rsp_spy_ratio": rsp_as_of,
        "sector_participation": max(sector_as_of_dates) if sector_as_of_dates else None,
    }

    notes = [
        "RSP/SPY ratio measures equal-weight vs. cap-weight S&P 500 performance; a rising ratio signals broadening participation.",
        "Sector participation counts SPDR sector ETFs with daily close above rolling 50-day SMA.",
        "Breadth regime is a heuristic classification; it is not a licensed breadth index.",
        "Composite score: 70% sector participation rate + 30% RSP/SPY 5-day momentum (capped ±2%), normalised to 0–1.",
    ]

    payload: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "source_last_trading_day": source_last_trading_day,
        "freshness_notes": freshness_notes,
        "warnings": list(dict.fromkeys(warnings)),
        "data": {
            "source_label": "yfinance",
            "source_mode": "primary" if status == "ok" else "partial",
            "equal_weight_vs_cap_weight": {
                "rsp_spy_ratio": rsp_spy_ratio,
                "rsp_spy_ratio_5d_change_pct": rsp_spy_ratio_5d,
                "rsp_spy_ratio_20d_change_pct": rsp_spy_ratio_20d,
                "rsp_close": rsp_close,
                "spy_close": spy_close,
                "rsp_as_of": rsp_as_of,
                "spy_as_of": spy_as_of,
                "direction": rsp_spy_direction,
            },
            "sector_participation": {
                "sectors_above_50dma": sectors_above_50dma,
                "sectors_total": sectors_total,
                "participation_pct": participation_pct,
                "participation_regime": participation_regime,
                "sectors": sector_records,
            },
            "major_index_breadth": {
                "breadth_regime": breadth_regime,
                "composite_score": composite_score,
                "notes": [
                    "Regime derived from sector participation count and RSP/SPY 5-day direction.",
                    "Broad: >= 7/11 sectors above 50DMA and RSP/SPY not deteriorating.",
                    "Narrow: < 5/11 sectors above 50DMA.",
                    "Recovering: >= 6/11 sectors with improving RSP/SPY, or >= 7 sectors despite deteriorating RSP/SPY.",
                    "Deteriorating: 5-6 sectors above 50DMA and RSP/SPY deteriorating.",
                ],
            },
            "notes": notes,
        },
    }

    safe_write_json(OUT_PATH, payload)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
