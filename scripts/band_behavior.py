from __future__ import annotations

from typing import Any

from board_state_contract import actionable_records

DEFAULT_NEAR_BAND_PCT = 1.0


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_distance(value: float, reference: float) -> float:
    return ((value - reference) / reference) * 100.0 if reference else 0.0


def _quote_for_record(record: dict[str, Any], market_state: dict[str, Any] | None) -> dict[str, Any]:
    ticker = str(record.get("ticker") or "").strip()
    actionable = (((market_state or {}).get("data") or {}).get("actionable") or {})
    if isinstance(actionable, dict) and ticker in actionable and isinstance(actionable[ticker], dict):
        return actionable[ticker]
    return {}


def band_behavior_for_record(
    record: dict[str, Any],
    market_state: dict[str, Any] | None,
    *,
    near_band_pct: float = DEFAULT_NEAR_BAND_PCT,
) -> dict[str, Any]:
    """Return a review-only post-close intraday-vs-band signal for one record.

    This is a status/explanation signal only. It does not change action state,
    owner approval, sizing, deployment authority, or any canonical portfolio note.
    """
    ticker = str(record.get("ticker") or "").strip()
    band = record.get("entry_band") or {}
    quote = _quote_for_record(record, market_state)

    low = _as_float(band.get("low"))
    high = _as_float(band.get("high"))
    close = _as_float(record.get("close"))
    open_price = _as_float(quote.get("open"))
    day_high = _as_float(quote.get("day_high") or quote.get("high"))
    day_low = _as_float(quote.get("day_low") or quote.get("low"))

    if low is None or high is None or close is None:
        return {
            "ticker": ticker,
            "available": False,
            "reason": "missing entry band or close",
            "authority": "review_only_status_signal_no_portfolio_authority",
        }

    near_fraction = max(float(near_band_pct), 0.0) / 100.0
    near_lower_threshold = low * (1.0 + near_fraction)
    near_upper_threshold = high * (1.0 - near_fraction)

    closed_in_band = low <= close <= high
    closed_below_band = close < low
    closed_above_band = close > high
    closed_near_lower_band = low <= close <= near_lower_threshold
    closed_near_upper_band = near_upper_threshold <= close <= high

    lower_band_tested = day_low is not None and day_low <= near_lower_threshold
    lower_band_reclaimed = lower_band_tested and close > low and (day_low is None or close > day_low)
    upper_band_breached_intraday = day_high is not None and day_high > high
    upper_band_tested = day_high is not None and day_high >= near_upper_threshold
    no_chase_active = closed_near_upper_band or closed_above_band or upper_band_breached_intraday

    flags: list[str] = []
    if lower_band_reclaimed:
        flags.append("lower_band_tested_and_reclaimed")
    elif lower_band_tested:
        flags.append("lower_band_tested")
    if closed_near_lower_band:
        flags.append("closed_near_lower_band")
    if closed_near_upper_band:
        flags.append("closed_near_upper_band")
    if upper_band_breached_intraday:
        flags.append("intraday_above_band")
    elif upper_band_tested:
        flags.append("upper_band_tested")
    if closed_above_band:
        flags.append("closed_above_band")
    elif closed_below_band:
        flags.append("closed_below_band")
    elif closed_in_band:
        flags.append("closed_in_band")
    if no_chase_active:
        flags.append("no_chase_active")

    summary_parts: list[str] = []
    if lower_band_reclaimed:
        summary_parts.append("tested lower-band support and reclaimed")
    elif lower_band_tested:
        summary_parts.append("tested lower-band support")
    if upper_band_breached_intraday:
        summary_parts.append("briefly breached upper band intraday")
    elif upper_band_tested:
        summary_parts.append("tested upper-band resistance")
    if closed_near_upper_band:
        summary_parts.append("closed near no-chase ceiling")
    elif closed_near_lower_band:
        summary_parts.append("closed near lower-band support")
    elif closed_above_band:
        summary_parts.append("closed above band")
    elif closed_below_band:
        summary_parts.append("closed below band")
    elif closed_in_band:
        summary_parts.append("closed in band")

    return {
        "ticker": ticker,
        "available": True,
        "authority": "review_only_status_signal_no_portfolio_authority",
        "near_band_pct": near_band_pct,
        "open": open_price,
        "day_low": day_low,
        "day_high": day_high,
        "close": close,
        "entry_band_low": low,
        "entry_band_high": high,
        "distance_low_to_band_low": None if day_low is None else round(day_low - low, 4),
        "distance_close_to_band_high": round(high - close, 4),
        "pct_close_vs_band_high": round(_pct_distance(close, high), 4),
        "closed_in_band": closed_in_band,
        "lower_band_tested": lower_band_tested,
        "lower_band_reclaimed": lower_band_reclaimed,
        "upper_band_tested": upper_band_tested,
        "upper_band_breached_intraday": upper_band_breached_intraday,
        "no_chase_active": no_chase_active,
        "flags": flags,
        "summary": "; ".join(summary_parts) if summary_parts else "no band-behavior signal",
    }


def qualified_band_behavior(
    trigger: dict[str, Any] | None,
    market_state: dict[str, Any] | None,
    *,
    near_band_pct: float = DEFAULT_NEAR_BAND_PCT,
) -> list[dict[str, Any]]:
    records = (trigger or {}).get("records") or []
    qualified = actionable_records([record for record in records if isinstance(record, dict)])
    return [band_behavior_for_record(record, market_state, near_band_pct=near_band_pct) for record in qualified]


def band_behavior_by_ticker(
    trigger: dict[str, Any] | None,
    market_state: dict[str, Any] | None,
    *,
    near_band_pct: float = DEFAULT_NEAR_BAND_PCT,
) -> dict[str, dict[str, Any]]:
    return {item.get("ticker", ""): item for item in qualified_band_behavior(trigger, market_state, near_band_pct=near_band_pct)}


def format_band_behavior(item: dict[str, Any] | None) -> str:
    if not item or not item.get("available"):
        return "band behavior unavailable"
    close = item.get("close")
    low = item.get("day_low")
    high = item.get("day_high")
    summary = item.get("summary") or "no band-behavior signal"
    parts = []
    if low is not None and high is not None and close is not None:
        parts.append(f"intraday {low:,.2f}-{high:,.2f}, close {close:,.2f}")
    parts.append(str(summary))
    if item.get("no_chase_active"):
        parts.append("no-chase active")
    return "; ".join(parts)
