from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MONTH_CODES = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}


def get_fred_api_key() -> str | None:
    api_key = os.getenv("FRED_API_KEY") or os.getenv("fred_api_key")
    if api_key:
        return api_key

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            for value_name in ("FRED_API_KEY", "fred_api_key"):
                try:
                    api_key, _ = winreg.QueryValueEx(key, value_name)
                    if api_key:
                        return str(api_key)
                except FileNotFoundError:
                    continue
    except Exception:
        pass

    return None


def fetch_fred_observations(series_id: str, api_key: str | None = None, timeout: int = 20, limit: int = 30) -> tuple[list[dict[str, Any]], str | None]:
    api_key = api_key or get_fred_api_key()
    if not api_key:
        return [], "FRED_API_KEY not set"

    params = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": max(1, int(limit)),
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"

    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return [], f"FRED HTTP error {exc.code}"
    except URLError as exc:
        return [], f"FRED URL error: {exc.reason}"
    except Exception as exc:
        return [], f"FRED fetch error: {exc}"

    cleaned: list[dict[str, Any]] = []
    for obs in payload.get("observations", []):
        value = obs.get("value")
        date_str = obs.get("date")
        if value in (None, ".") or not date_str:
            continue
        try:
            cleaned.append({"date": str(date_str), "value": round(float(value), 4)})
        except Exception:
            continue

    if not cleaned:
        return [], "FRED returned no usable observations"

    return cleaned, None


def fetch_fred_latest(series_id: str, api_key: str | None = None, timeout: int = 20) -> tuple[float | None, str | None, str | None]:
    observations, error = fetch_fred_observations(series_id, api_key=api_key, timeout=timeout, limit=10)
    if error:
        return None, None, error

    latest = observations[0]
    return latest["value"], latest["date"], None


def zq_ticker_for_meeting_date(meeting_date: str | datetime) -> str | None:
    try:
        dt = meeting_date if isinstance(meeting_date, datetime) else datetime.strptime(meeting_date, "%Y-%m-%d")
    except Exception:
        return None
    month_code = MONTH_CODES.get(dt.month)
    if not month_code:
        return None
    return f"ZQ{month_code}{dt.year % 100:02d}"


def fetch_fedwatch_implied_rate(next_fomc_zq_ticker: str, timeout: int = 15) -> tuple[float | None, str | None, str | None]:
    cme_url = (
        "https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/305/G"
        "?quoteCodes=null&_t=" + str(int(datetime.now(timezone.utc).timestamp()))
    )
    cme_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.cmegroup.com/",
    }

    try:
        req = Request(cme_url, headers=cme_headers)
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        quotes = payload.get("quotes", [])
        for quote in quotes:
            if quote.get("productCode", "") == next_fomc_zq_ticker or next_fomc_zq_ticker in str(quote.get("expirationDate", "")):
                last = quote.get("last") or quote.get("settle")
                if last is not None:
                    implied_rate = round(100.0 - float(last), 4)
                    return implied_rate, f"CME 30-day Fed Funds Futures ({next_fomc_zq_ticker})", None
    except Exception as exc:
        cme_error = str(exc)
    else:
        cme_error = "contract not found in CME payload"

    try:
        import yfinance as yf

        candidates: list[str] = []
        for candidate in (next_fomc_zq_ticker, f"{next_fomc_zq_ticker}.CBT", "ZQ=F"):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        last_errors: list[str] = []
        for candidate in candidates:
            try:
                ticker_obj = yf.Ticker(candidate)
                info: Any = ticker_obj.fast_info
                last_price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
                if last_price is None:
                    hist = ticker_obj.history(period="2d", interval="1d")
                    if not hist.empty:
                        last_price = float(hist["Close"].iloc[-1])
                if last_price is not None:
                    implied_rate = round(100.0 - float(last_price), 4)
                    note = f"CME primary failed: {cme_error}" if candidate != next_fomc_zq_ticker else f"CME primary failed: {cme_error}"
                    return implied_rate, f"yfinance ZQ futures ({candidate}) - fallback", note
                last_errors.append(f"{candidate}: no price data")
            except Exception as exc:
                last_errors.append(f"{candidate}: {exc}")
    except Exception as exc:
        return None, None, f"Both CME and yfinance ZQ failed. CME: {cme_error}. yfinance import/runtime: {exc}"

    return None, None, f"ZQ price not available. CME: {cme_error}. yfinance tried: {'; '.join(last_errors)}"


def build_single_step_fomc_distribution(target_low: float, target_high: float, implied_rate: float) -> dict[str, Any]:
    target_mid = (target_low + target_high) / 2.0
    delta_bps = round((target_mid - implied_rate) * 100, 1)

    cut_prob = 0.0
    hike_prob = 0.0
    hold_prob = 100.0

    if delta_bps > 0:
        cut_prob = max(0.0, min(100.0, round(delta_bps / 25.0 * 100.0, 1)))
        hold_prob = round(max(0.0, 100.0 - cut_prob), 1)
    elif delta_bps < 0:
        hike_prob = max(0.0, min(100.0, round(abs(delta_bps) / 25.0 * 100.0, 1)))
        hold_prob = round(max(0.0, 100.0 - hike_prob), 1)

    distribution = [
        {"outcome": "hold", "probability": hold_prob},
        {"outcome": "cut_25bp", "probability": cut_prob},
        {"outcome": "hike_25bp", "probability": hike_prob},
    ]
    most_likely = max(distribution, key=lambda item: item["probability"])["outcome"]

    return {
        "target_mid": round(target_mid, 4),
        "implied_rate": round(implied_rate, 4),
        "delta_bps_vs_target_mid": delta_bps,
        "distribution": distribution,
        "most_likely_outcome": most_likely,
        "method_note": "Single-step 25bp approximation from one 30-day Fed Funds futures contract; not a full multi-outcome meeting-distribution model.",
    }


def fetch_fedwatch_probability(target_low: float, target_high: float, next_fomc_zq_ticker: str) -> tuple[float | None, str | None, str | None]:
    implied_rate, source_label, note = fetch_fedwatch_implied_rate(next_fomc_zq_ticker)
    if implied_rate is None:
        return None, None, note

    distribution = build_single_step_fomc_distribution(target_low, target_high, implied_rate)
    cut_prob = next((item["probability"] for item in distribution["distribution"] if item["outcome"] == "cut_25bp"), None)
    return cut_prob, source_label, note
