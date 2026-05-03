"""credit_spread_refresh.py

Build the dedicated credit-spread artifact for the finance OS.

Primary posture:
- FRED / ICE BofA OAS series for IG and HY spreads

Fallback posture:
- yfinance proxy basket using HYG, JNK, and LQD relative behavior

Usage:
    python scripts/credit_spread_refresh.py

Writes:
- tmp/credit-spreads.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import yfinance as yf

from market_data_utils import fetch_fred_observations

WORKSPACE = Path(__file__).resolve().parents[1]
OUT_PATH = WORKSPACE / "tmp" / "credit-spreads.json"
STALE_AFTER_HOURS = 36
EXPECTED_UPDATE_WINDOW = "Refresh after the close for next-session regime work and before weekly macro outputs."

IG_SERIES = "BAMLC0A0CM"
HY_SERIES = "BAMLH0A0HYM2"
FLAT_THRESHOLD_PCT = 0.03  # 3 bps
PROXY_RATIO_THRESHOLD_PCT = 0.25  # 0.25%
PROXY_TICKERS = {
    "HYG": "iShares iBoxx $ High Yield Corporate Bond ETF",
    "JNK": "SPDR Bloomberg High Yield Bond ETF",
    "LQD": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def classify_oas_direction(current: float | None, prior: float | None, threshold: float = FLAT_THRESHOLD_PCT) -> str | None:
    if current is None or prior is None:
        return None
    delta = current - prior
    if delta > threshold:
        return "widening"
    if delta < -threshold:
        return "tightening"
    return "flat"


def classify_proxy_direction(change_pct: float | None, inverse: bool = False, threshold: float = PROXY_RATIO_THRESHOLD_PCT) -> str | None:
    if change_pct is None:
        return None
    adjusted = -change_pct if inverse else change_pct
    if adjusted > threshold:
        return "tightening"
    if adjusted < -threshold:
        return "widening"
    return "flat"


def compute_change_pct(series: list[dict[str, Any]], lookback: int) -> float | None:
    if len(series) <= lookback:
        return None
    current = series[-1].get("value")
    prior = series[-1 - lookback].get("value")
    if current in (None, 0) or prior in (None, 0):
        return None
    return round(((float(current) - float(prior)) / float(prior)) * 100.0, 4)


def fetch_proxy_series(ticker: str, period: str = "3mo") -> tuple[list[dict[str, Any]], str | None]:
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
        if hist.empty:
            return [], "no price history"
        closes = hist.get("Close")
        if closes is None:
            return [], "close series missing"
        closes = closes.dropna()
        if closes.empty:
            return [], "close series empty"
        out: list[dict[str, Any]] = []
        for idx, value in closes.items():
            out.append({
                "date": idx.strftime("%Y-%m-%d"),
                "value": round(float(value), 4),
            })
        return out, None
    except Exception as exc:
        return [], str(exc)


def infer_stress_regime(ig_oas: float | None, hy_oas: float | None, hy_minus_ig: float | None, proxy_score: float | None = None) -> str:
    if hy_oas is not None or ig_oas is not None or hy_minus_ig is not None:
        if (hy_oas is not None and hy_oas >= 6.0) or (ig_oas is not None and ig_oas >= 2.25) or (hy_minus_ig is not None and hy_minus_ig >= 4.5):
            return "severe"
        if (hy_oas is not None and hy_oas >= 4.5) or (ig_oas is not None and ig_oas >= 1.75) or (hy_minus_ig is not None and hy_minus_ig >= 3.25):
            return "stressed"
        if (hy_oas is not None and hy_oas >= 3.5) or (ig_oas is not None and ig_oas >= 1.25) or (hy_minus_ig is not None and hy_minus_ig >= 2.5):
            return "watch"
        return "benign"

    if proxy_score is None:
        return "watch"
    if proxy_score <= -2.0:
        return "severe"
    if proxy_score <= -1.0:
        return "stressed"
    if proxy_score < 0:
        return "watch"
    return "benign"


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    warnings: list[str] = []
    freshness_notes: list[str] = [
        "fred_ice_bofa_series_can_lag_one_trading_day",
        "direction_labels_use_latest_vs_5d_and_20d_observation_comparison",
    ]

    print("Refreshing credit spreads...")

    ig_obs, ig_error = fetch_fred_observations(IG_SERIES, limit=40)
    hy_obs, hy_error = fetch_fred_observations(HY_SERIES, limit=40)

    ig_series = list(reversed(ig_obs)) if ig_obs else []
    hy_series = list(reversed(hy_obs)) if hy_obs else []

    ig_latest = ig_series[-1]["value"] if ig_series else None
    ig_as_of = ig_series[-1]["date"] if ig_series else None
    hy_latest = hy_series[-1]["value"] if hy_series else None
    hy_as_of = hy_series[-1]["date"] if hy_series else None

    if ig_latest is not None:
        print(f"  IG OAS ............... {ig_latest:.2f}% ({ig_as_of})")
    else:
        print(f"  IG OAS ............... FAILED ({ig_error})")
        warnings.append(f"IG OAS fetch failed for {IG_SERIES}. {ig_error}")

    if hy_latest is not None:
        print(f"  HY OAS ............... {hy_latest:.2f}% ({hy_as_of})")
    else:
        print(f"  HY OAS ............... FAILED ({hy_error})")
        warnings.append(f"HY OAS fetch failed for {HY_SERIES}. {hy_error}")

    ig_5d = classify_oas_direction(ig_latest, ig_series[-6]["value"] if len(ig_series) > 5 else None)
    ig_20d = classify_oas_direction(ig_latest, ig_series[-21]["value"] if len(ig_series) > 20 else None)
    hy_5d = classify_oas_direction(hy_latest, hy_series[-6]["value"] if len(hy_series) > 5 else None)
    hy_20d = classify_oas_direction(hy_latest, hy_series[-21]["value"] if len(hy_series) > 20 else None)

    hy_minus_ig = round(hy_latest - ig_latest, 4) if hy_latest is not None and ig_latest is not None else None

    source_label = "FRED ICE BofA OAS"
    source_mode = "primary"
    fallback_proxies: list[dict[str, Any]] = []
    proxy_score: float | None = None

    needs_proxy = any(value is None for value in (ig_latest, hy_latest, ig_5d, ig_20d, hy_5d, hy_20d))
    if needs_proxy:
        source_mode = "mixed" if (ig_latest is not None or hy_latest is not None) else "fallback"
        warnings.append("Direct OAS coverage is incomplete; using proxy basket to preserve directional context.")

        proxy_errors: list[str] = []
        proxy_changes: dict[str, dict[str, float | None]] = {}
        proxy_series_map: dict[str, list[dict[str, Any]]] = {}
        for ticker, label in PROXY_TICKERS.items():
            series, error = fetch_proxy_series(ticker)
            if error:
                proxy_errors.append(f"{ticker}: {error}")
                continue
            proxy_series_map[ticker] = series
            proxy_changes[ticker] = {
                "change_5d_pct": compute_change_pct(series, 5),
                "change_20d_pct": compute_change_pct(series, 20),
            }
            fallback_proxies.append(
                {
                    "ticker": ticker,
                    "label": label,
                    "last_close": series[-1]["value"],
                    "as_of": series[-1]["date"],
                    "change_5d_pct": proxy_changes[ticker]["change_5d_pct"],
                    "change_20d_pct": proxy_changes[ticker]["change_20d_pct"],
                }
            )

        if proxy_errors:
            warnings.append("Proxy basket gaps: " + "; ".join(proxy_errors))

        def ratio_change_pct(num: str, den: str, lookback: int) -> float | None:
            num_series = proxy_series_map.get(num)
            den_series = proxy_series_map.get(den)
            if not num_series or not den_series:
                return None
            joined_len = min(len(num_series), len(den_series))
            if joined_len <= lookback:
                return None
            num_current = num_series[-1]["value"]
            num_prior = num_series[-1 - lookback]["value"]
            den_current = den_series[-1]["value"]
            den_prior = den_series[-1 - lookback]["value"]
            if min(num_current, num_prior, den_current, den_prior) in (None, 0):
                return None
            current_ratio = float(num_current) / float(den_current)
            prior_ratio = float(num_prior) / float(den_prior)
            if prior_ratio == 0:
                return None
            return round(((current_ratio - prior_ratio) / prior_ratio) * 100.0, 4)

        lqd_5d = proxy_changes.get("LQD", {}).get("change_5d_pct")
        lqd_20d = proxy_changes.get("LQD", {}).get("change_20d_pct")
        hyg_lqd_5d = ratio_change_pct("HYG", "LQD", 5)
        hyg_lqd_20d = ratio_change_pct("HYG", "LQD", 20)
        jnk_lqd_5d = ratio_change_pct("JNK", "LQD", 5)
        jnk_lqd_20d = ratio_change_pct("JNK", "LQD", 20)

        if ig_5d is None:
            ig_5d = classify_proxy_direction(lqd_5d, inverse=False)
        if ig_20d is None:
            ig_20d = classify_proxy_direction(lqd_20d, inverse=False)
        if hy_5d is None:
            ratio_5d_candidates = [x for x in (hyg_lqd_5d, jnk_lqd_5d) if x is not None]
            avg_ratio_5d = round(sum(ratio_5d_candidates) / len(ratio_5d_candidates), 4) if ratio_5d_candidates else None
            hy_5d = classify_proxy_direction(avg_ratio_5d, inverse=False)
        if hy_20d is None:
            ratio_20d_candidates = [x for x in (hyg_lqd_20d, jnk_lqd_20d) if x is not None]
            avg_ratio_20d = round(sum(ratio_20d_candidates) / len(ratio_20d_candidates), 4) if ratio_20d_candidates else None
            hy_20d = classify_proxy_direction(avg_ratio_20d, inverse=False)

        proxy_score_parts = [x for x in (hyg_lqd_5d, hyg_lqd_20d, jnk_lqd_5d, jnk_lqd_20d, lqd_5d, lqd_20d) if x is not None]
        if proxy_score_parts:
            proxy_score = round(sum(proxy_score_parts) / len(proxy_score_parts), 4)

    stress_regime = infer_stress_regime(ig_latest, hy_latest, hy_minus_ig, proxy_score=proxy_score)

    status = "ok"
    if ig_latest is None and hy_latest is None and not fallback_proxies:
        status = "error"
        warnings.append("No trustworthy direct or proxy credit read is available.")
    elif ig_latest is None or hy_latest is None:
        status = "partial"
    elif any(value is None for value in (ig_5d, ig_20d, hy_5d, hy_20d)):
        status = "partial"
    elif source_mode != "primary":
        status = "partial"

    source_last_trading_day = {
        "ig_oas": ig_as_of,
        "hy_oas": hy_as_of,
    }
    if fallback_proxies:
        for proxy in fallback_proxies:
            source_last_trading_day[f"proxy_{proxy['ticker'].lower()}"] = proxy.get("as_of")

    available_dates = [d for d in source_last_trading_day.values() if d]
    last_trading_day = max(available_dates) if available_dates else None

    notes = [
        "Stress regime is a heuristic credit-state classification, not a licensed credit model.",
        "Direction labels use latest versus 5-trading-day and 20-trading-day prior observations with a 3bp flat threshold for direct OAS series.",
    ]
    if fallback_proxies:
        notes.append("Fallback proxies use HYG, JNK, and LQD relative behavior when direct OAS coverage is incomplete.")

    payload = {
        "generated_at_utc": utc_now(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "source_last_trading_day": source_last_trading_day,
        "freshness_notes": freshness_notes,
        "warnings": list(dict.fromkeys(warnings)),
        "data": {
            "source_label": source_label,
            "source_mode": source_mode,
            "investment_grade_oas": {
                "value": ig_latest,
                "unit": "percent",
                "series": IG_SERIES,
                "as_of": ig_as_of,
            },
            "high_yield_oas": {
                "value": hy_latest,
                "unit": "percent",
                "series": HY_SERIES,
                "as_of": hy_as_of,
            },
            "hy_minus_ig_spread": hy_minus_ig,
            "direction": {
                "ig_5d": ig_5d,
                "ig_20d": ig_20d,
                "hy_5d": hy_5d,
                "hy_20d": hy_20d,
            },
            "stress_regime": stress_regime,
            "fallback_proxies": fallback_proxies,
            "notes": notes,
        },
    }

    safe_write_json(OUT_PATH, payload)
    print(f"  Stress regime ........ {stress_regime}")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
