"""technical_refresh.py

Live technical data refresh using yfinance.

Calculates close prices, 20/50/200-day MAs, and MA posture for the configured
technical universe plus the current WF78 Tier A review bench. Checks each name
against its defined entry band and stop. Writes structured JSON to
tmp/technical-refresh.json and prints a terminal summary.

Usage:
    python scripts/technical_refresh.py
    python scripts/technical_refresh.py --tickers AJG AXON --merge-existing

Requirements:
    pip install yfinance
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import yfinance as yf
import universe

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
OUT_PATH = TMP / "technical-refresh.json"
WF78_AUTO_TIER_ROUTING_PATH = TMP / "wf78-auto-tier-routing.json"
AUTO_BAND_APPLY_PATH = TMP / "auto-band-apply.json"
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


HistoryFetcher = Callable[[str], Any]


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_wf78_tier_a_tickers(path: Path = WF78_AUTO_TIER_ROUTING_PATH) -> list[str]:
    """Return the current Tier A bench without widening technical coverage to Tier B/C."""

    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    rows = payload.get("rows") if isinstance(payload, dict) else []
    tickers = {
        str(row.get("ticker") or "").strip().upper()
        for row in rows or []
        if isinstance(row, dict)
        and str(row.get("auto_tier") or "").strip() == "Tier A"
        and str(row.get("ticker") or "").strip()
    }
    return sorted(tickers)


def build_tracked_map(
    config: dict[str, Any],
    tier_a_tickers: Sequence[str] | None = None,
) -> dict[str, str]:
    tracked = (config.get("tracked_universe") or {})
    out: dict[str, str] = {}
    for ticker, meta in tracked.items():
        if not isinstance(meta, dict):
            continue
        if universe.is_entitled(ticker, meta, "technical_refresh"):
            out[ticker] = meta.get("yfinance") or ticker

    current_tier_a = load_wf78_tier_a_tickers() if tier_a_tickers is None else tier_a_tickers
    for raw_ticker in current_tier_a:
        ticker = str(raw_ticker or "").strip().upper()
        if not ticker or ticker in out:
            continue
        meta = tracked.get(ticker)
        yf_ticker = meta.get("yfinance") if isinstance(meta, dict) else None
        out[ticker] = yf_ticker or ticker.replace(".", "-")
    return out


def load_auto_applied_bands(path: Path = AUTO_BAND_APPLY_PATH) -> dict[str, dict[str, Any]]:
    """Load SQL-first auto-maintained reference bands when present.

    These bands are applied by auto_apply_entry_band_maintenance.py from the
    band-proposals.sql_first_current source and supersede the legacy portfolio
    config entry_bands. We use them so technical_refresh computes in_entry_band
    and below_stop against the same fresh reference levels the rest of the
    finance OS uses.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in payload.get("applied") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        # Prefer the newly applied levels; old_* are retained for audit.
        low = row.get("new_low") if row.get("new_low") is not None else row.get("old_low")
        high = row.get("new_high") if row.get("new_high") is not None else row.get("old_high")
        stop = row.get("new_stop") if row.get("new_stop") is not None else row.get("old_stop")
        if low is None or high is None:
            continue
        out[ticker] = {
            "low": low,
            "high": high,
            "stop": stop,
            "source": "auto-band-apply.json",
            "reference_only": bool(row.get("reference_only", False)),
            "data_date": row.get("data_date"),
            "method": row.get("method"),
        }
    return out


def build_entry_bands(config: dict[str, Any], auto_applied: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Return entry bands for technical posture checks.

    SQL-first auto-maintained reference bands take priority. The legacy
    portfolio-config.json entry_bands remain as a fallback only when no fresh
    auto-applied band exists for a ticker.
    """
    raw = config.get("entry_bands") or {}
    legacy = raw if isinstance(raw, dict) else {}
    if not auto_applied:
        return legacy
    merged: dict[str, dict[str, Any]] = {}
    for ticker, band in legacy.items():
        merged[ticker] = dict(band)
        merged[ticker]["source"] = "portfolio-config.json"
    for ticker, band in auto_applied.items():
        merged[ticker] = band
    return merged


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


def fetch_history(yf_ticker: str) -> Any:
    return yf.Ticker(yf_ticker).history(period="1y")


def build_record(
    display_ticker: str,
    raw: Any,
    entry_bands: dict[str, dict[str, Any]],
) -> TechnicalRecord:
    notes: list[str] = []
    blank = TechnicalRecord(
        display_ticker, None, None, None, None, None,
        None, None, None, None, None,
        None, notes,
    )

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


def fetch_record(
    display_ticker: str,
    yf_ticker: str,
    entry_bands: dict[str, dict[str, Any]],
    history_fetcher: HistoryFetcher = fetch_history,
) -> TechnicalRecord:
    try:
        return build_record(display_ticker, history_fetcher(yf_ticker), entry_bands)
    except Exception as exc:
        notes: list[str] = ["Fetch error: " + str(exc)]
        blank = TechnicalRecord(
            display_ticker, None, None, None, None, None,
            None, None, None, None, None,
            None, notes,
        )
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh review-only technical evidence.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        help="Refresh only configured technical-refresh tickers or current WF78 Tier A tickers.",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Replace refreshed ticker rows in the existing output and retain all other rows.",
    )
    args = parser.parse_args(argv)
    if args.merge_existing and not args.tickers:
        parser.error("--merge-existing requires --tickers")
    return args


def select_tracked_tickers(tracked: dict[str, str], requested: Sequence[str] | None) -> dict[str, str]:
    if requested is None:
        return dict(tracked)

    selected: dict[str, str] = {}
    missing: list[str] = []
    for raw_ticker in requested:
        ticker = raw_ticker.strip().upper()
        if ticker in selected:
            continue
        if ticker not in tracked:
            missing.append(ticker)
            continue
        selected[ticker] = tracked[ticker]

    if missing:
        raise ValueError(
            "Ticker(s) not entitled to technical refresh: " + ", ".join(missing)
        )
    return selected


def merge_record_rows(
    existing_payload: dict[str, Any] | None,
    refreshed: list[TechnicalRecord],
) -> list[dict[str, Any]]:
    refreshed_by_ticker = {record.ticker: asdict(record) for record in refreshed}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    existing_rows = (existing_payload or {}).get("records") or []
    if isinstance(existing_rows, list):
        for row in existing_rows:
            if not isinstance(row, dict):
                continue
            ticker = row.get("ticker")
            if not isinstance(ticker, str) or ticker in seen:
                continue
            merged.append(refreshed_by_ticker.get(ticker, row))
            seen.add(ticker)

    for record in refreshed:
        if record.ticker not in seen:
            merged.append(asdict(record))
            seen.add(record.ticker)
    return merged


def build_payload(
    record_rows: list[dict[str, Any]],
    generated_at_utc: datetime | None = None,
) -> dict[str, Any]:
    all_ok = all(row.get("close") is not None for row in record_rows)
    any_ok = any(row.get("close") is not None for row in record_rows)
    status = "ok" if all_ok else ("partial" if any_ok else "error")

    valid_dates = sorted({
        row["data_date"]
        for row in record_rows
        if isinstance(row.get("data_date"), str) and row["data_date"]
    })
    last_trading_day = max(valid_dates) if valid_dates else None
    warnings: list[str] = []
    if status != "ok":
        warnings.append("One or more technical records failed to populate.")
    if last_trading_day is None:
        warnings.append("No valid trading date found in technical output.")

    generated_at = generated_at_utc or datetime.now(timezone.utc)
    return {
        "generated_at_utc": generated_at.isoformat(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "warnings": warnings,
        "source_config": str(CONFIG_PATH),
        "tracked_tickers": [row["ticker"] for row in record_rows if isinstance(row.get("ticker"), str)],
        "records": record_rows,
    }


def run_refresh(
    config: dict[str, Any],
    auto_applied: dict[str, dict[str, Any]] | None = None,
    requested_tickers: Sequence[str] | None = None,
    existing_payload: dict[str, Any] | None = None,
    history_fetcher: HistoryFetcher = fetch_history,
    generated_at_utc: datetime | None = None,
    tier_a_tickers: Sequence[str] | None = None,
) -> tuple[dict[str, Any], list[TechnicalRecord]]:
    tracked = select_tracked_tickers(build_tracked_map(config, tier_a_tickers), requested_tickers)
    entry_bands = build_entry_bands(config, auto_applied)

    print("Fetching technical data for " + str(len(tracked)) + " tickers...")

    records: list[TechnicalRecord] = []
    for display_ticker, yf_ticker in tracked.items():
        print("  " + display_ticker + "...", end=" ", flush=True)
        record = fetch_record(display_ticker, yf_ticker, entry_bands, history_fetcher)
        records.append(record)
        print("ok" if record.close is not None else "ERROR")

    rows = merge_record_rows(existing_payload, records) if existing_payload is not None else [asdict(r) for r in records]
    return build_payload(rows, generated_at_utc), records


def write_payload(payload: dict[str, Any], output_path: Path = OUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config()
    auto_applied = load_auto_applied_bands()
    existing_payload: dict[str, Any] | None = None
    if args.merge_existing and OUT_PATH.exists():
        existing_payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    try:
        payload, refreshed_records = run_refresh(
            config,
            auto_applied=auto_applied,
            requested_tickers=args.tickers,
            existing_payload=existing_payload if args.merge_existing else None,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    write_payload(payload)

    print_summary(refreshed_records, payload["warnings"], payload["last_trading_day"])
    print("Output written to " + str(OUT_PATH) + "  [status: " + payload["status"] + "]")


if __name__ == "__main__":
    main()
