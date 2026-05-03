"""technical_refresh.py

Live technical data refresh using yfinance.

Calculates close prices, 20/50/200-day MAs, and MA posture for all tracked
names sourced from tmp/portfolio-config.json. Checks each name against its
defined entry band and stop. Writes structured JSON to tmp/technical-refresh.json
and prints a terminal summary.

Usage:
    python scripts/technical_refresh.py

Requirements:
    pip install yfinance
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf
import universe

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
OUT_PATH = TMP / "technical-refresh.json"
STALE_AFTER_HOURS = 36
EXPECTED_UPDATE_WINDOW = "Refresh each weekday, after material earnings moves, and before decision-grade deployment work."


@dataclass
class TechnicalRecord:
    ticker: str
    close: float | None
    ma20: float | None
    ma50: float | None
    ma200: float | None
    ma_posture: str | None
    above_ma20: bool | None
    above_ma50: bool | None
    above_ma200: bool | None
    in_entry_band: bool | None
    below_stop: bool | None
    data_date: str | None
    notes: list[str]


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def build_tracked_map(config: dict[str, Any]) -> dict[str, str]:
    tracked = (config.get("tracked_universe") or {})
    out: dict[str, str] = {}
    for ticker, meta in tracked.items():
        if not isinstance(meta, dict):
            continue
        if universe.is_entitled(ticker, meta, "technical_refresh"):
            out[ticker] = meta.get("yfinance") or ticker
    return out


def build_entry_bands(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = config.get("entry_bands") or {}
    return raw if isinstance(raw, dict) else {}


def classify_posture(close: float, ma20: float | None, ma50: float | None, ma200: float | None) -> str:
    if None in (ma20, ma50, ma200):
        return "insufficient data for full posture"
    positions = {"20d": close > ma20, "50d": close > ma50, "200d": close > ma200}
    above = [k for k, v in positions.items() if v]
    below = [k for k, v in positions.items() if not v]
    if len(above) == 3:
        if ma20 > ma50 > ma200:
            return "above all MAs -- bullish 20>50>200 stack"
        return "above all MAs"
    if len(above) == 2:
        return "above " + " and ".join(above) + ", below " + below[0]
    if len(above) == 1:
        return "above " + above[0] + ", below " + " and ".join(below)
    return "below all MAs"


def band_status(close: float, ticker: str, entry_bands: dict[str, dict[str, Any]]) -> tuple[bool | None, bool | None]:
    band = entry_bands.get(ticker, {})
    low, high, stop = band.get("low"), band.get("high"), band.get("stop")
    in_band = (low <= close <= high) if (low is not None and high is not None) else None
    below_stop = (close < stop) if stop is not None else None
    return in_band, below_stop


def fetch_record(display_ticker: str, yf_ticker: str, entry_bands: dict[str, dict[str, Any]]) -> TechnicalRecord:
    notes: list[str] = []
    blank = TechnicalRecord(
        display_ticker, None, None, None, None, None,
        None, None, None, None, None,
        None, notes,
    )
    try:
        t = yf.Ticker(yf_ticker)
        raw = t.history(period="1y")

        if raw.empty:
            notes.append("yfinance returned no data.")
            return blank

        closes = raw["Close"].dropna()
        if len(closes) < 20:
            notes.append("Only " + str(len(closes)) + " rows -- insufficient for MA calculations.")
            return blank

        close = round(float(closes.iloc[-1]), 2)
        data_date = closes.index[-1].strftime("%Y-%m-%d")

        ma20 = round(float(closes.rolling(20).mean().iloc[-1]), 2) if len(closes) >= 20 else None
        ma50 = round(float(closes.rolling(50).mean().iloc[-1]), 2) if len(closes) >= 50 else None
        ma200 = round(float(closes.rolling(200).mean().iloc[-1]), 2) if len(closes) >= 200 else None

        if ma200 is None:
            notes.append("Less than 200 trading days available.")

        posture = classify_posture(close, ma20, ma50, ma200)
        in_band, blw_stop = band_status(close, display_ticker, entry_bands)

        return TechnicalRecord(
            ticker=display_ticker,
            close=close,
            ma20=ma20,
            ma50=ma50,
            ma200=ma200,
            ma_posture=posture,
            above_ma20=close > ma20 if ma20 is not None else None,
            above_ma50=close > ma50 if ma50 is not None else None,
            above_ma200=close > ma200 if ma200 is not None else None,
            in_entry_band=in_band,
            below_stop=blw_stop,
            data_date=data_date,
            notes=notes,
        )

    except Exception as exc:
        notes.append("Fetch error: " + str(exc))
        return blank


def print_summary(records: list[TechnicalRecord], warnings: list[str], last_trading_day: str | None) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sep = "=" * 74
    print("\n" + sep)
    print("  TECHNICAL REFRESH  --  " + now)
    print(sep)

    if last_trading_day:
        print("\n  Last trading day covered: " + last_trading_day)

    print("\n  " + "{:<8} {:>8}  {:>8}  {:>8}  {:>8}  {:<12}".format(
        "Ticker", "Close", "MA20", "MA50", "MA200", "Date"))
    print("  " + "-" * 70)
    for r in records:
        if r.close is None:
            print("  " + "{:<8}  {:>8}  {:>8}  {:>8}  {:>8}".format(r.ticker, "ERROR", "--", "--", "--"))
        else:
            print("  " + "{:<8} {:>8.2f}  {:>8.2f}  {:>8.2f}  {:>8.2f}  {:<12}".format(
                r.ticker, r.close, r.ma20 or 0.0, r.ma50 or 0.0, r.ma200 or 0.0, r.data_date or "--"))

    print("\n  " + "{:<8}  {}".format("Ticker", "Posture / Status"))
    print("  " + "-" * 70)
    for r in records:
        if r.close is None:
            print("  " + "{:<8}  fetch error  -- {}".format(r.ticker, r.notes[0] if r.notes else ""))
            continue
        flags = []
        if r.in_entry_band:
            flags.append("IN ENTRY BAND")
        elif r.in_entry_band is False:
            flags.append("OUTSIDE BAND")
        if r.below_stop:
            flags.append("BELOW STOP")
        flag_str = ("  [" + "  ".join(flags) + "]") if flags else ""
        print("  " + "{:<8}  {}{}".format(r.ticker, r.ma_posture, flag_str))

    in_band = [r.ticker for r in records if r.in_entry_band]
    stopped = [r.ticker for r in records if r.below_stop]

    print("\n  DEPLOYMENT SUMMARY")
    print("  " + "-" * 40)
    print("  In entry band: " + (", ".join(in_band) if in_band else "none"))
    print("  Below stop:    " + (", ".join(stopped) if stopped else "none"))

    if warnings:
        print("\n  WARNINGS")
        print("  " + "-" * 40)
        for warning in warnings:
            print("  - " + warning)

    print(sep + "\n")


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = load_config()
    tracked = build_tracked_map(config)
    entry_bands = build_entry_bands(config)

    print("Fetching technical data for " + str(len(tracked)) + " tickers...")

    records: list[TechnicalRecord] = []
    for display_ticker, yf_ticker in tracked.items():
        print("  " + display_ticker + "...", end=" ", flush=True)
        record = fetch_record(display_ticker, yf_ticker, entry_bands)
        records.append(record)
        print("ok" if record.close is not None else "ERROR")

    all_ok = all(r.close is not None for r in records)
    any_ok = any(r.close is not None for r in records)
    status = "ok" if all_ok else ("partial" if any_ok else "error")

    valid_dates = sorted({r.data_date for r in records if r.data_date})
    last_trading_day = max(valid_dates) if valid_dates else None
    warnings: list[str] = []
    if status != "ok":
        warnings.append("One or more technical records failed to populate.")
    if last_trading_day is None:
        warnings.append("No valid trading date found in technical output.")

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "warnings": warnings,
        "source_config": str(CONFIG_PATH),
        "tracked_tickers": list(tracked.keys()),
        "records": [asdict(r) for r in records],
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print_summary(records, warnings, last_trading_day)
    print("Output written to " + str(OUT_PATH) + "  [status: " + status + "]")


if __name__ == "__main__":
    main()
