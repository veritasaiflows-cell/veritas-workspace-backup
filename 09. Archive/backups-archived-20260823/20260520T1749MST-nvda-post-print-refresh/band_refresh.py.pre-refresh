"""band_refresh.py

Read-only band staleness detector and proposal generator.

Reads:
  tmp/technical-refresh.json  -- live prices, MAs, posture per ticker
  tmp/portfolio-config.json   -- current entry bands and band_last_set dates

For each tracked name with a defined or partially defined band:
  - Computes days since band_last_set
  - Computes MA20 drift since band was set (approximated from current MA20 vs band midpoint)
  - Computes ATR-14 from yfinance to calibrate stop distance
  - Proposes an updated entry band and stop anchored to current MA structure
  - Flags needs_review=true if band is >7 trading days old or price has moved
    more than 5% from the band midpoint

Does NOT write to portfolio-config.json. All changes require human review
and must be applied via apply_band_update.py.

Writes:
  tmp/band-proposals.json

Usage:
    python scripts/band_refresh.py

Requirements:
    pip install yfinance
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

from market_data_utils import atomic_write_json
import universe

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
TECH_PATH = TMP / "technical-refresh.json"
CONFIG_PATH = TMP / "portfolio-config.json"
EARNINGS_PATH = TMP / "earnings-calendar.json"
OUT_PATH = TMP / "band-proposals.json"

STALE_TRADING_DAYS = 7       # flag needs_review if band older than this many trading days
PRICE_DRIFT_PCT = 5.0        # flag needs_review if price moved >5% from band midpoint
MATERIAL_BAND_CHANGE_PCT = 1.0
EARNINGS_FREEZE_DAYS = 7
EARNINGS_TIMING_WINDOW_DAYS = 14
AUTO_APPLY_BAND_STATUSES = {"IN_BAND", "NEAR_BAND"}
AUTO_APPLY_EARNINGS_STATES = {"CLEAR"}
SMA_ENVELOPE_PCT = 5.0
ENGINE_VERSION = "keltner-ma-v1"
EXPECTED_UPDATE_WINDOW = (
    "Run after technical_refresh.py. Review proposals and approve via "
    "apply_band_update.py before updating portfolio-config.json or the "
    "Execution Board."
)


@dataclass
class BandProposal:
    ticker: str
    coverage_lane: str | None
    workflow_state: str | None
    entry_policy: str | None
    current_band_low: float | None
    current_band_high: float | None
    current_stop: float | None
    band_last_set: str | None
    days_old: int | None
    trading_days_old: int | None
    close: float | None
    ma20: float | None
    ma50: float | None
    ma200: float | None
    atr14: float | None
    ema20: float | None = None
    ema50: float | None = None
    sma200: float | None = None
    atr20: float | None = None
    atrp20: float | None = None
    atr_multiplier: float | None = None
    ma20_vs_band_midpoint_pct: float | None = None
    price_vs_band_midpoint_pct: float | None = None
    suggested_band_low: float | None = None
    suggested_band_high: float | None = None
    suggested_stop: float | None = None
    entry_band_method: str | None = None
    entry_band_type: str | None = None
    band_status: str | None = None
    distance_to_band_pct: float | None = None
    stop_basis: str | None = None
    trend_stack: str | None = None
    sma_envelope_low: float | None = None
    sma_envelope_high: float | None = None
    earnings_state: str | None = None
    days_to_earnings: int | None = None
    earnings_date_source_class: str | None = None
    earnings_primary_confirmed: bool | None = None
    band_confidence: int | None = None
    canonical_apply_eligible: bool = True
    calculation_warnings: list[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    needs_review: bool = False
    skip_reason: str | None = None
    reasons: list[str] = field(default_factory=list)
    data_date: str | None = None


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path} ({label})")
    return json.loads(path.read_text(encoding="utf-8"))


def calendar_days_old(band_last_set: str | None, as_of_date: str | None = None) -> int | None:
    if not band_last_set:
        return None
    try:
        set_date = date.fromisoformat(band_last_set)
        reference_date = date.fromisoformat(as_of_date) if as_of_date else datetime.now(timezone.utc).date()
        return max(0, (reference_date - set_date).days)
    except (ValueError, TypeError):
        return None


def approx_trading_days_old(calendar_days: int | None) -> int | None:
    """Approximate trading days from calendar days (5/7 ratio, rounded)."""
    if calendar_days is None:
        return None
    return round(calendar_days * 5 / 7)


def band_midpoint(low: float | None, high: float | None) -> float | None:
    if low is not None and high is not None:
        return (low + high) / 2.0
    return None


def pct_diff(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None or reference == 0:
        return None
    return round((current - reference) / abs(reference) * 100, 2)


def fetch_atr14(yf_ticker: str) -> float | None:
    """Fetch ATR-14 from yfinance. Returns None on any failure."""
    try:
        t = yf.Ticker(yf_ticker)
        raw = t.history(period="60d")
        if raw.empty or len(raw) < 15:
            return None
        high = raw["High"]
        low = raw["Low"]
        close_prev = raw["Close"].shift(1)
        tr = (
            (high - low)
            .combine(abs(high - close_prev), max)
            .combine(abs(low - close_prev), max)
        )
        atr = round(float(tr.rolling(14).mean().iloc[-1]), 2)
        return atr
    except Exception:
        return None


def fetch_engine_inputs(yf_ticker: str) -> dict[str, float | None]:
    """Fetch daily technical inputs for the Keltner/MA band engine.

    Falls back cleanly to None-valued fields on provider failure. The caller
    must fail closed into review-only handling rather than fabricating levels.
    """
    empty = {
        "ema20": None,
        "ema50": None,
        "sma200": None,
        "atr20": None,
        "atr14": None,
        "atrp20": None,
    }
    try:
        t = yf.Ticker(yf_ticker)
        raw = t.history(period="260d")
        if raw.empty or len(raw) < 50:
            return empty
        high = raw["High"]
        low = raw["Low"]
        close = raw["Close"]
        close_prev = close.shift(1)
        tr = (
            (high - low)
            .combine(abs(high - close_prev), max)
            .combine(abs(low - close_prev), max)
        )
        latest_close = float(close.iloc[-1]) if len(close) else None
        atr20 = round(float(tr.rolling(20).mean().iloc[-1]), 2) if len(tr) >= 20 else None
        atr14 = round(float(tr.rolling(14).mean().iloc[-1]), 2) if len(tr) >= 14 else None
        atrp20 = round(atr20 / latest_close, 4) if atr20 is not None and latest_close else None
        return {
            "ema20": round(float(close.ewm(span=20, adjust=False).mean().iloc[-1]), 2),
            "ema50": round(float(close.ewm(span=50, adjust=False).mean().iloc[-1]), 2),
            "sma200": round(float(close.rolling(200).mean().iloc[-1]), 2) if len(close) >= 200 else None,
            "atr20": atr20,
            "atr14": atr14,
            "atrp20": atrp20,
        }
    except Exception:
        return empty


def classify_trend(close: float | None, ema20: float | None, ema50: float | None, sma200: float | None) -> str | None:
    if close is None or ema20 is None or ema50 is None or sma200 is None:
        return None
    if close > ema20 > ema50 > sma200:
        return "BULLISH_20_50_200"
    if close > ema20 and close > ema50 and close > sma200:
        return "ABOVE_ALL_MAS"
    if close > sma200 and (close < ema20 or close < ema50):
        return "ABOVE_200_BELOW_20_50"
    if close < sma200 and close < ema20 and close < ema50:
        return "BELOW_ALL_MAS"
    if close < sma200:
        return "BELOW_200"
    return "MIXED"


def select_atr_multiplier(atrp20: float | None) -> float | None:
    if atrp20 is None:
        return None
    if atrp20 < 0.015:
        return 1.5
    if atrp20 <= 0.035:
        return 2.0
    return 2.5


def classify_band_status(close: float | None, low: float | None, high: float | None, stop: float | None, trend: str | None) -> tuple[str | None, float | None]:
    if close is None:
        return None, None
    if stop is not None and close < stop:
        return "BELOW_STOP", None
    if trend in {"BELOW_200", "BELOW_ALL_MAS"}:
        return "RECLAIM_ONLY", None
    if low is None or high is None:
        return "NO_BAND", None
    if low <= close <= high:
        return "IN_BAND", round((close - high) / high * 100, 2)
    if close > high:
        dist = round((close - high) / high * 100, 2)
        threshold = 5.0 if high and ((high - low) / high * 100) > 5 else 3.0
        if dist <= threshold:
            return "NEAR_BAND", dist
        return "ABOVE_BAND_WAIT", dist
    return "BELOW_BAND", round((close - low) / low * 100, 2) if low else None


def earnings_source_metadata(ticker: str, earnings_records: dict[str, dict[str, Any]]) -> tuple[str | None, bool | None]:
    record = earnings_records.get(ticker) or {}
    source_class = record.get("date_source_class")
    primary_confirmed = record.get("primary_confirmed")
    return (
        str(source_class) if source_class is not None else None,
        bool(primary_confirmed) if primary_confirmed is not None else None,
    )


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def post_earnings_review_clears_freeze(meta: dict[str, Any], earnings_date: date | None) -> bool:
    """Return True when a same-day/past earnings freeze has a captured review.

    Provider calendars can keep reporting today's earnings date after the print is
    already captured. Once the portfolio config records that the earnings date
    and a post-earnings review date are both at or after that event date, the
    band engine may leave the binary-event freeze and produce normal review
    levels. This only clears the freeze for band review; it does not grant
    deployment, sizing, owner approval, or trade/account authority.
    """
    if earnings_date is None:
        return False
    last_earnings = parse_date(meta.get("last_earnings_date"))
    review_date = parse_date(meta.get("post_earnings_review_date"))
    return bool(last_earnings and review_date and last_earnings >= earnings_date and review_date >= earnings_date)


def earnings_state(ticker: str, earnings_records: dict[str, dict[str, Any]], as_of_date: str | None, meta: dict[str, Any] | None = None) -> tuple[str, int | None]:
    record = earnings_records.get(ticker)
    meta = meta or {}
    if not record or not record.get("next_earnings_date") or not as_of_date:
        return "UNKNOWN", None
    earnings_date = parse_date(record.get("next_earnings_date"))
    as_of = parse_date(as_of_date)
    if earnings_date is None or as_of is None:
        return "UNKNOWN", None
    days = (earnings_date - as_of).days
    if days <= EARNINGS_FREEZE_DAYS and post_earnings_review_clears_freeze(meta, earnings_date):
        return "CLEAR", days
    if days < 0:
        return "CLEAR", days
    if days <= EARNINGS_FREEZE_DAYS:
        return "IMMINENT", days
    if days <= EARNINGS_TIMING_WINDOW_DAYS:
        return "TIMING_WINDOW", days
    return "CLEAR", days


def material_band_change_pct(current_low: float | None, current_high: float | None, new_low: float | None, new_high: float | None) -> float | None:
    current_mid = band_midpoint(current_low, current_high)
    new_mid = band_midpoint(new_low, new_high)
    return pct_diff(new_mid, current_mid)


def calculate_entry_band(
    close: float | None,
    ema20: float | None,
    ema50: float | None,
    sma200: float | None,
    atr20: float | None,
    atrp20: float | None,
    earnings: str,
    current_low: float | None,
    current_high: float | None,
    current_stop: float | None,
) -> dict[str, Any]:
    """Keltner-first, dual-MA-gated, SMA-envelope-audited band selector."""
    trend = classify_trend(close, ema20, ema50, sma200)
    multiplier = select_atr_multiplier(atrp20)
    warnings: list[str] = []
    if close is None or ema20 is None or ema50 is None or sma200 is None or atr20 is None or multiplier is None:
        return {
            "low": None,
            "high": None,
            "stop": None,
            "method": None,
            "type": None,
            "status": None,
            "trend": trend,
            "multiplier": multiplier,
            "sma_low": round(ema50 * (1 - SMA_ENVELOPE_PCT / 100), 2) if ema50 else None,
            "sma_high": round(ema50 * (1 + SMA_ENVELOPE_PCT / 100), 2) if ema50 else None,
            "stop_basis": None,
            "distance_to_band_pct": None,
            "confidence": 1,
            "apply_eligible": False,
            "warnings": ["insufficient EMA/SMA/ATR inputs for Keltner-MA band calculation"],
        }

    kc_low = ema20 - multiplier * atr20
    kc_mid = ema20
    sma_low = round(ema50 * (1 - SMA_ENVELOPE_PCT / 100), 2)
    sma_high = round(ema50 * (1 + SMA_ENVELOPE_PCT / 100), 2)
    method = "KELTNER_PRIMARY"
    band_type = "WATCH"
    stop_basis = "entry_low minus 1.25x ATR20"
    apply_eligible = True
    confidence = 3

    if earnings == "IMMINENT":
        # Freeze deployment-relevant application around a binary event. Keep the
        # current visible band when one exists; otherwise expose the calculated
        # Keltner zone as review-only context that apply_band_update must skip.
        low = current_low if current_low is not None else kc_low
        high = current_high if current_high is not None else kc_mid + 0.25 * atr20
        stop = current_stop if current_stop is not None else low - 1.25 * atr20
        method = "EARNINGS_FROZEN"
        band_type = "EVENT_RISK"
        confidence = 1
        apply_eligible = False
        warnings.append("earnings imminent; normal band update is frozen and cannot be auto-applied")
    elif trend in {"BELOW_200", "BELOW_ALL_MAS"}:
        low = max(ema50, sma200)
        high = low + 1.25 * atr20
        stop = low - 1.0 * atr20
        method = "DUAL_MA_RECLAIM"
        band_type = "VAULT_RECLAIM"
        stop_basis = "reclaim low minus 1.0x ATR20"
        confidence = 2
    elif trend == "BULLISH_20_50_200":
        low = max(kc_low, ema50 - 0.50 * atr20)
        high = ema20 + 0.25 * atr20
        if low >= high:
            warnings.append("MA/Keltner intersection was too narrow; used blended bullish fallback")
            low = min(kc_low, high - 0.75 * atr20)
        stop = min(low - 1.25 * atr20, ema50 - 1.5 * atr20)
        method = "KELTNER_MA_CONSTRAINED"
        band_type = "PULLBACK"
        stop_basis = "min(entry low - 1.25x ATR20, EMA50 - 1.5x ATR20)"
        confidence = 4
    else:
        low = kc_low
        high = kc_mid + 0.25 * atr20
        stop = low - 1.25 * atr20
        method = "KELTNER_PRIMARY"
        band_type = "WATCH"
        confidence = 3 if trend not in {None, "MIXED"} else 2

    low = round(low, 2)
    high = round(high, 2)
    stop = round(stop, 2)
    status, distance = classify_band_status(close, low, high, stop, trend)
    if earnings == "IMMINENT":
        status = "EARNINGS_IMMINENT"
    return {
        "low": low,
        "high": high,
        "stop": stop,
        "method": method,
        "type": band_type,
        "status": status,
        "trend": trend,
        "multiplier": multiplier,
        "sma_low": sma_low,
        "sma_high": sma_high,
        "stop_basis": stop_basis,
        "distance_to_band_pct": distance,
        "confidence": confidence,
        "apply_eligible": apply_eligible,
        "warnings": warnings,
    }


def build_proposal(
    ticker: str,
    band: dict[str, Any],
    meta: dict[str, Any] | None,
    tech_rec: dict[str, Any] | None,
    yf_ticker: str,
    earnings_records: dict[str, dict[str, Any]],
    earnings_as_of: str | None,
) -> BandProposal:
    """Build one review-only proposal using the Keltner/MA/SMA audit engine."""
    meta = meta or {}
    current_low = band.get("low")
    current_high = band.get("high")
    current_stop = band.get("stop")
    band_last_set = band.get("band_last_set")
    coverage_lane = meta.get("coverage_lane")
    workflow_state = meta.get("workflow_state")
    entry_policy = meta.get("entry_policy")

    data_date = tech_rec.get("data_date") if tech_rec else None
    days_old = calendar_days_old(band_last_set, data_date)
    trading_days_old = approx_trading_days_old(days_old)

    if tech_rec is None:
        return BandProposal(
            ticker=ticker,
            coverage_lane=coverage_lane,
            workflow_state=workflow_state,
            entry_policy=entry_policy,
            current_band_low=current_low,
            current_band_high=current_high,
            current_stop=current_stop,
            band_last_set=band_last_set,
            days_old=days_old,
            trading_days_old=trading_days_old,
            close=None,
            ma20=None,
            ma50=None,
            ma200=None,
            atr14=None,
            needs_review=True,
            canonical_apply_eligible=False,
            skip_reason="No technical record found — cannot compute proposal",
            reasons=["No technical data available; band review required manually"],
        )

    close = tech_rec.get("close")
    ma20 = tech_rec.get("ma20")
    ma50 = tech_rec.get("ma50")
    ma200 = tech_rec.get("ma200")
    engine_inputs = fetch_engine_inputs(yf_ticker)
    earnings, days_to_earnings = earnings_state(ticker, earnings_records, earnings_as_of, meta)
    earnings_date_source_class, earnings_primary_confirmed = earnings_source_metadata(ticker, earnings_records)
    calc = calculate_entry_band(
        close=close,
        ema20=engine_inputs.get("ema20"),
        ema50=engine_inputs.get("ema50"),
        sma200=engine_inputs.get("sma200") or ma200,
        atr20=engine_inputs.get("atr20"),
        atrp20=engine_inputs.get("atrp20"),
        earnings=earnings,
        current_low=current_low,
        current_high=current_high,
        current_stop=current_stop,
    )

    midpoint = band_midpoint(current_low, current_high)
    ma20_vs_mid = pct_diff(ma20, midpoint)
    price_vs_mid = pct_diff(close, midpoint)
    band_change = material_band_change_pct(current_low, current_high, calc.get("low"), calc.get("high"))

    reasons: list[str] = []
    needs_review = False

    if current_low is None and current_high is None and current_stop is None:
        needs_review = True
        reasons.append("No band defined — initial Keltner/MA proposal requires human review before applying")

    if calc.get("low") is None or calc.get("high") is None or calc.get("stop") is None:
        needs_review = True
        reasons.append("Keltner/MA engine could not produce complete suggested levels; manual review required")

    if trading_days_old is not None and trading_days_old > STALE_TRADING_DAYS:
        needs_review = True
        reasons.append(
            f"Band is approximately {trading_days_old} trading days old "
            f"(set {band_last_set}); exceeds {STALE_TRADING_DAYS}-day review threshold"
        )

    if price_vs_mid is not None and abs(price_vs_mid) > PRICE_DRIFT_PCT:
        needs_review = True
        direction = "above" if price_vs_mid > 0 else "below"
        reasons.append(
            f"Close {close} is {abs(price_vs_mid):.1f}% {direction} the band midpoint "
            f"{midpoint}; exceeds {PRICE_DRIFT_PCT}% drift threshold"
        )

    if ma20_vs_mid is not None and abs(ma20_vs_mid) > PRICE_DRIFT_PCT:
        needs_review = True
        direction = "above" if ma20_vs_mid > 0 else "below"
        reasons.append(
            f"MA20 {ma20} is {abs(ma20_vs_mid):.1f}% {direction} the band midpoint "
            f"{midpoint}; suggests band may no longer be calibrated to current structure"
        )

    if band_change is not None and abs(band_change) > MATERIAL_BAND_CHANGE_PCT:
        needs_review = True
        direction = "higher" if band_change > 0 else "lower"
        reasons.append(
            f"Keltner/MA proposed midpoint is {abs(band_change):.1f}% {direction} than current midpoint; "
            f"exceeds {MATERIAL_BAND_CHANGE_PCT}% material-change threshold"
        )

    if earnings == "IMMINENT":
        needs_review = True
        reasons.append(f"Earnings are imminent ({days_to_earnings} days); freeze normal band application")
    elif earnings == "TIMING_WINDOW":
        reasons.append(f"Earnings timing window is open ({days_to_earnings} days); review sizing/event-risk before relying on band")
    elif earnings == "UNKNOWN":
        reasons.append("Earnings timing is unknown; keep catalyst confidence downgraded")

    for warning in calc.get("warnings") or []:
        reasons.append(warning)

    if not reasons:
        pct_str = f"price is {abs(price_vs_mid):.1f}% from midpoint" if price_vs_mid is not None else "no current band midpoint"
        method = calc.get("method") or "unknown method"
        status = calc.get("status") or "unknown status"
        reasons.append(
            f"Band is ~{trading_days_old} trading days old; {pct_str}; {method} status {status}; no review required at this time"
        )

    apply_blockers: list[str] = []
    if not calc.get("apply_eligible"):
        apply_blockers.append("engine marked proposal non-applyable")
    if coverage_lane != "execution":
        apply_blockers.append("non-execution lane proposals are review-only")
    if entry_policy != "band_defined":
        apply_blockers.append("entry policy is not band_defined")
    if workflow_state not in {"ALMOST", "PROMOTION REVIEW", "DEPLOYED"}:
        apply_blockers.append("workflow state is not decision-grade for band application")
    if earnings not in AUTO_APPLY_EARNINGS_STATES:
        apply_blockers.append(f"earnings state {earnings} is not clear")
    if calc.get("status") not in AUTO_APPLY_BAND_STATUSES:
        apply_blockers.append(f"band status {calc.get('status') or 'unknown'} is not auto-apply approved")
    if apply_blockers:
        reasons.extend(apply_blockers)

    return BandProposal(
        ticker=ticker,
        coverage_lane=coverage_lane,
        workflow_state=workflow_state,
        entry_policy=entry_policy,
        current_band_low=current_low,
        current_band_high=current_high,
        current_stop=current_stop,
        band_last_set=band_last_set,
        days_old=days_old,
        trading_days_old=trading_days_old,
        close=close,
        ma20=ma20,
        ma50=ma50,
        ma200=ma200,
        atr14=engine_inputs.get("atr14"),
        ema20=engine_inputs.get("ema20"),
        ema50=engine_inputs.get("ema50"),
        sma200=engine_inputs.get("sma200") or ma200,
        atr20=engine_inputs.get("atr20"),
        atrp20=engine_inputs.get("atrp20"),
        atr_multiplier=calc.get("multiplier"),
        ma20_vs_band_midpoint_pct=ma20_vs_mid,
        price_vs_band_midpoint_pct=price_vs_mid,
        suggested_band_low=calc.get("low"),
        suggested_band_high=calc.get("high"),
        suggested_stop=calc.get("stop"),
        entry_band_method=calc.get("method"),
        entry_band_type=calc.get("type"),
        band_status=calc.get("status"),
        distance_to_band_pct=calc.get("distance_to_band_pct"),
        stop_basis=calc.get("stop_basis"),
        trend_stack=calc.get("trend"),
        sma_envelope_low=calc.get("sma_low"),
        sma_envelope_high=calc.get("sma_high"),
        earnings_state=earnings,
        days_to_earnings=days_to_earnings,
        earnings_date_source_class=earnings_date_source_class,
        earnings_primary_confirmed=earnings_primary_confirmed,
        band_confidence=calc.get("confidence"),
        canonical_apply_eligible=not apply_blockers,
        calculation_warnings=list(calc.get("warnings") or []),
        needs_review=needs_review,
        skip_reason=None,
        reasons=reasons,
        data_date=data_date,
    )

def is_accepted_repair_mode_blocker(proposal: BandProposal) -> bool:
    """Return True for deliberate repair-mode wait states that should not be dashboard blockers."""
    if not proposal.needs_review or proposal.skip_reason is not None:
        return False
    return (
        proposal.entry_policy == "repair_mode"
        and proposal.workflow_state == "REPAIR"
        and proposal.canonical_apply_eligible is False
    )


def is_accepted_review_only_wait_state(proposal: BandProposal) -> bool:
    """Return True for review-only band proposals that cannot be safely applied.

    These should stay visible in ``tmp/band-proposals.json`` as manual context,
    but they should not become dashboard-level stale-band debt because the
    applier is intentionally forbidden from resolving them. Earnings-frozen
    proposals remain blocking because they represent an event-risk stop line,
    not a normal wait/no-chase or non-decision-lane state.
    """
    if not proposal.needs_review or proposal.skip_reason is not None:
        return False
    if proposal.canonical_apply_eligible is not False:
        return False
    if proposal.entry_band_method == "EARNINGS_FROZEN":
        return False
    return True


def is_blocking_review(proposal: BandProposal) -> bool:
    """Return True when a review item should remain a dashboard-level blocker.

    Price-only extension above or below the existing midpoint is still useful to
    surface in the proposal artifact, but it is not by itself a trust blocker.
    A blocker should reflect structural drift, stale calibration, or missing
    numeric setup rather than deliberate no-chase posture. Explicit repair-mode
    wait states stay visible in the proposal artifact but are accepted manual
    blockers, not stale-band debt.
    """
    if not proposal.needs_review or proposal.skip_reason is not None:
        return False

    if is_accepted_repair_mode_blocker(proposal) or is_accepted_review_only_wait_state(proposal):
        return False

    if proposal.current_band_low is None or proposal.current_band_high is None or proposal.current_stop is None:
        return proposal.entry_policy == "band_defined"

    if proposal.suggested_band_low is None or proposal.suggested_band_high is None or proposal.suggested_stop is None:
        return proposal.entry_policy == "band_defined"

    if proposal.entry_band_method == "EARNINGS_FROZEN":
        return True

    if proposal.trading_days_old is not None and proposal.trading_days_old > STALE_TRADING_DAYS:
        return True

    if proposal.ma20_vs_band_midpoint_pct is not None and abs(proposal.ma20_vs_band_midpoint_pct) > PRICE_DRIFT_PCT:
        return True

    return False


def print_summary(proposals: list[BandProposal]) -> None:
    sep = "=" * 74
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{sep}")
    print(f"  BAND REFRESH  --  {now}")
    print(sep)

    needs_review = [p for p in proposals if p.needs_review]
    ok = [p for p in proposals if not p.needs_review and p.skip_reason is None]
    skipped = [p for p in proposals if p.skip_reason is not None]

    print(f"\n  Proposals: {len(proposals)} total | "
          f"{len(needs_review)} need review | "
          f"{len(ok)} within tolerance | "
          f"{len(skipped)} skipped (no band defined)")

    if needs_review:
        print(f"\n  {'-'*70}")
        print(f"  NEEDS REVIEW ({len(needs_review)})")
        print(f"  {'-'*70}")
        for p in needs_review:
            print(f"\n  {p.ticker}")
            print(f"    Current band:   {p.current_band_low} – {p.current_band_high}  stop {p.current_stop}")
            print(f"    Suggested band: {p.suggested_band_low} – {p.suggested_band_high}  stop {p.suggested_stop}")
            print(f"    Method/status:  {p.entry_band_method} / {p.band_status}  trend {p.trend_stack}")
            print(f"    Close: {p.close}  EMA20: {p.ema20}  EMA50: {p.ema50}  ATR20: {p.atr20}")
            print(f"    Band age: ~{p.trading_days_old} trading days (set {p.band_last_set})")
            for reason in p.reasons:
                print(f"    ⚠  {reason}")

    if ok:
        print(f"\n  {'-'*70}")
        print(f"  WITHIN TOLERANCE ({len(ok)})")
        print(f"  {'-'*70}")
        for p in ok:
            print(f"  {p.ticker:<8}  band {p.current_band_low}–{p.current_band_high}  "
                  f"close {p.close}  ~{p.trading_days_old}d old  "
                  f"{p.entry_band_method}/{p.band_status}  price vs mid: {p.price_vs_band_midpoint_pct:+.1f}%"
                  if p.price_vs_band_midpoint_pct is not None
                  else f"  {p.ticker:<8}  band {p.current_band_low}–{p.current_band_high}  "
                       f"close {p.close}  ~{p.trading_days_old}d old  {p.entry_band_method}/{p.band_status}")

    if skipped:
        print(f"\n  {'-'*70}")
        print(f"  SKIPPED — CANNOT GENERATE PROPOSAL ({len(skipped)})")
        print(f"  {'-'*70}")
        for p in skipped:
            print(f"  {p.ticker:<8}  {p.skip_reason}")

    print(f"\n{sep}\n")


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Loading technical-refresh.json...")
    tech = load_json(TECH_PATH, "technical-refresh")
    tech_records: dict[str, dict[str, Any]] = {
        rec["ticker"]: rec for rec in (tech.get("records") or [])
    }

    print("Loading portfolio-config.json...")
    config = load_json(CONFIG_PATH, "portfolio-config")
    entry_bands: dict[str, dict[str, Any]] = config.get("entry_bands") or {}
    tracked_universe: dict[str, dict[str, Any]] = config.get("tracked_universe") or {}

    earnings_data = load_json(EARNINGS_PATH, "earnings-calendar") if EARNINGS_PATH.exists() else {}
    earnings_records = {rec.get("ticker"): rec for rec in (earnings_data.get("records") or []) if rec.get("ticker")}
    earnings_as_of = earnings_data.get("as_of_date")

    # Build yfinance ticker map
    yf_map: dict[str, str] = {}
    for ticker, meta in tracked_universe.items():
        if isinstance(meta, dict):
            yf_map[ticker] = meta.get("yfinance") or ticker

    proposals: list[BandProposal] = []
    excluded_tickers: list[str] = []
    for ticker, band in entry_bands.items():
        meta = tracked_universe.get(ticker, {}) if isinstance(tracked_universe, dict) else {}
        if not isinstance(meta, dict) or not universe.is_entitled(ticker, meta, "band_drift"):
            excluded_tickers.append(ticker)
            print(f"  Processing {ticker}... excluded (lane not band-drift entitled)")
            continue
        tech_rec = tech_records.get(ticker)
        yf_ticker = yf_map.get(ticker, ticker)
        print(f"  Processing {ticker}...", end=" ", flush=True)
        proposal = build_proposal(ticker, band, meta, tech_rec, yf_ticker, earnings_records, earnings_as_of)
        proposals.append(proposal)
        if proposal.skip_reason:
            print("skipped")
        elif proposal.needs_review:
            print("NEEDS REVIEW")
        else:
            print("ok")

    needs_review_count = sum(1 for p in proposals if p.needs_review)
    blocking_review_tickers = [p.ticker for p in proposals if is_blocking_review(p)]
    accepted_repair_mode_blocker_tickers = [p.ticker for p in proposals if is_accepted_repair_mode_blocker(p)]
    monitor_only_review_tickers = [
        p.ticker for p in proposals
        if p.needs_review and not p.skip_reason and p.ticker not in blocking_review_tickers
    ]
    ok_count = sum(1 for p in proposals if not p.needs_review and not p.skip_reason)
    skipped_count = sum(1 for p in proposals if p.skip_reason)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "needs_review" if needs_review_count > 0 else "ok",
        "engine_version": ENGINE_VERSION,
        "method_policy": "Keltner-first, Dual-MA-gated, SMA-envelope-audited",
        "stale_threshold_trading_days": STALE_TRADING_DAYS,
        "price_drift_threshold_pct": PRICE_DRIFT_PCT,
        "material_band_change_pct": MATERIAL_BAND_CHANGE_PCT,
        "earnings_freeze_days": EARNINGS_FREEZE_DAYS,
        "sma_envelope_pct": SMA_ENVELOPE_PCT,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "summary": {
            "total": len(proposals),
            "excluded_not_entitled": len(excluded_tickers),
            "needs_review": needs_review_count,
            "blocking_review": len(blocking_review_tickers),
            "monitor_only_review": len(monitor_only_review_tickers),
            "within_tolerance": ok_count,
            "skipped_no_band": skipped_count,
            "needs_review_tickers": [p.ticker for p in proposals if p.needs_review],
            "blocking_review_tickers": blocking_review_tickers,
            "accepted_repair_mode_blockers": accepted_repair_mode_blocker_tickers,
            "monitor_only_review_tickers": monitor_only_review_tickers,
            "within_tolerance_tickers": [p.ticker for p in proposals if not p.needs_review and not p.skip_reason],
            "skipped_tickers": [p.ticker for p in proposals if p.skip_reason],
            "excluded_tickers": excluded_tickers,
        },
        "proposals": [asdict(p) for p in proposals],
    }

    atomic_write_json(OUT_PATH, output, indent=2, ensure_ascii=True)
    print_summary(proposals)
    print(f"Output written to {OUT_PATH}  [status: {output['status']}]")
    print(f"  {needs_review_count} band(s) need review | "
          f"{ok_count} within tolerance | "
          f"{skipped_count} skipped\n")


if __name__ == "__main__":
    main()
