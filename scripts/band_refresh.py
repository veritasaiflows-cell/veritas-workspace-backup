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
from datetime import datetime, timezone
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
OUT_PATH = TMP / "band-proposals.json"

STALE_TRADING_DAYS = 7       # flag needs_review if band older than this many trading days
PRICE_DRIFT_PCT = 5.0        # flag needs_review if price moved >5% from band midpoint
ATR_STOP_MULTIPLIER = 1.5    # stop = MA20 - (ATR14 * multiplier)
ATR_BAND_LOW_OFFSET = 0.5    # band low = MA20 - (ATR14 * offset)
ATR_BAND_HIGH_OFFSET = 1.5   # band high = MA20 + (ATR14 * offset)
EXPECTED_UPDATE_WINDOW = (
    "Run after technical_refresh.py. Review proposals and approve via "
    "apply_band_update.py before updating portfolio-config.json or the "
    "Technical Entry and Invalidation Sheet."
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
    atr14: float | None
    ma20_vs_band_midpoint_pct: float | None
    price_vs_band_midpoint_pct: float | None
    suggested_band_low: float | None
    suggested_band_high: float | None
    suggested_stop: float | None
    needs_review: bool
    skip_reason: str | None
    reasons: list[str] = field(default_factory=list)
    data_date: str | None = None


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path} ({label})")
    return json.loads(path.read_text(encoding="utf-8"))


def calendar_days_old(band_last_set: str | None) -> int | None:
    if not band_last_set:
        return None
    try:
        set_date = datetime.strptime(band_last_set, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now.date() - set_date.date()).days
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


def suggest_band(
    ma20: float | None,
    atr14: float | None,
    close: float | None,
) -> tuple[float | None, float | None, float | None]:
    """
    Suggest entry band and stop anchored to current MA20 and ATR14.

    Band low  = MA20 - (ATR * ATR_BAND_LOW_OFFSET)
    Band high = MA20 + (ATR * ATR_BAND_HIGH_OFFSET)
    Stop      = MA20 - (ATR * ATR_STOP_MULTIPLIER)

    All values rounded to 2 decimal places.
    Returns (suggested_low, suggested_high, suggested_stop).
    """
    if ma20 is None or atr14 is None:
        return None, None, None
    low = round(ma20 - atr14 * ATR_BAND_LOW_OFFSET, 2)
    high = round(ma20 + atr14 * ATR_BAND_HIGH_OFFSET, 2)
    stop = round(ma20 - atr14 * ATR_STOP_MULTIPLIER, 2)
    return low, high, stop


def build_proposal(
    ticker: str,
    band: dict[str, Any],
    meta: dict[str, Any] | None,
    tech_rec: dict[str, Any] | None,
    yf_ticker: str,
) -> BandProposal:
    """Build a BandProposal for one ticker."""
    meta = meta or {}
    current_low = band.get("low")
    current_high = band.get("high")
    current_stop = band.get("stop")
    band_last_set = band.get("band_last_set")
    coverage_lane = meta.get("coverage_lane")
    workflow_state = meta.get("workflow_state")
    entry_policy = meta.get("entry_policy")

    days_old = calendar_days_old(band_last_set)
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
            atr14=None,
            ma20_vs_band_midpoint_pct=None,
            price_vs_band_midpoint_pct=None,
            suggested_band_low=None,
            suggested_band_high=None,
            suggested_stop=None,
            needs_review=True,
            skip_reason="No technical record found — cannot compute proposal",
            reasons=["No technical data available; band review required manually"],
        )

    close = tech_rec.get("close")
    ma20 = tech_rec.get("ma20")
    ma50 = tech_rec.get("ma50")
    data_date = tech_rec.get("data_date")

    # If no band or stop defined, generate an initial proposal when MA20+ATR14 are available.
    # This handles underdefined names that have technical coverage but no band yet.
    if current_low is None and current_high is None and current_stop is None:
        atr14 = fetch_atr14(yf_ticker)
        if ma20 is not None and atr14 is not None:
            suggested_low, suggested_high, suggested_stop = suggest_band(ma20, atr14, close)
            return BandProposal(
                ticker=ticker,
                coverage_lane=coverage_lane,
                workflow_state=workflow_state,
                entry_policy=entry_policy,
                current_band_low=None,
                current_band_high=None,
                current_stop=None,
                band_last_set=band_last_set,
                days_old=days_old,
                trading_days_old=trading_days_old,
                close=close,
                ma20=ma20,
                ma50=ma50,
                atr14=atr14,
                ma20_vs_band_midpoint_pct=None,
                price_vs_band_midpoint_pct=None,
                suggested_band_low=suggested_low,
                suggested_band_high=suggested_high,
                suggested_stop=suggested_stop,
                needs_review=True,
                skip_reason=None,
                reasons=["No band defined — initial proposal from current MA20 and ATR14; requires human review before applying"],
                data_date=data_date,
            )
        else:
            return BandProposal(
                ticker=ticker,
                coverage_lane=coverage_lane,
                workflow_state=workflow_state,
                entry_policy=entry_policy,
                current_band_low=None,
                current_band_high=None,
                current_stop=None,
                band_last_set=band_last_set,
                days_old=days_old,
                trading_days_old=trading_days_old,
                close=close,
                ma20=ma20,
                ma50=ma50,
                atr14=None,
                ma20_vs_band_midpoint_pct=None,
                price_vs_band_midpoint_pct=None,
                suggested_band_low=None,
                suggested_band_high=None,
                suggested_stop=None,
                needs_review=False,
                skip_reason="No band defined and MA20/ATR14 unavailable — cannot generate initial proposal",
                data_date=data_date,
            )

    # Fetch ATR14 for names with any band or stop component defined
    atr14 = fetch_atr14(yf_ticker)

    midpoint = band_midpoint(current_low, current_high)
    ma20_vs_mid = pct_diff(ma20, midpoint)
    price_vs_mid = pct_diff(close, midpoint)

    suggested_low, suggested_high, suggested_stop = suggest_band(ma20, atr14, close)

    reasons: list[str] = []
    needs_review = False

    # Staleness gate
    if trading_days_old is not None and trading_days_old > STALE_TRADING_DAYS:
        needs_review = True
        reasons.append(
            f"Band is approximately {trading_days_old} trading days old "
            f"(set {band_last_set}); exceeds {STALE_TRADING_DAYS}-day review threshold"
        )

    # Price drift gate (only meaningful when band midpoint exists)
    if price_vs_mid is not None and abs(price_vs_mid) > PRICE_DRIFT_PCT:
        needs_review = True
        direction = "above" if price_vs_mid > 0 else "below"
        reasons.append(
            f"Close {close} is {abs(price_vs_mid):.1f}% {direction} the band midpoint "
            f"{midpoint}; exceeds {PRICE_DRIFT_PCT}% drift threshold"
        )

    # MA20 drift gate (only when midpoint exists)
    if ma20_vs_mid is not None and abs(ma20_vs_mid) > PRICE_DRIFT_PCT:
        needs_review = True
        direction = "above" if ma20_vs_mid > 0 else "below"
        reasons.append(
            f"MA20 {ma20} is {abs(ma20_vs_mid):.1f}% {direction} the band midpoint "
            f"{midpoint}; suggests band may no longer be calibrated to current structure"
        )

    # ATR unavailable note
    if atr14 is None:
        reasons.append("ATR14 fetch failed; suggested band and stop values are unavailable")

    if not reasons:
        if price_vs_mid is not None:
            pct_str = f"price is {abs(price_vs_mid):.1f}% from midpoint"
        else:
            pct_str = "no band midpoint (entry low/high undefined — stop-only entry)"
        reasons.append(
            f"Band is ~{trading_days_old} trading days old; {pct_str}; no review required at this time"
        )

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
        atr14=atr14,
        ma20_vs_band_midpoint_pct=ma20_vs_mid,
        price_vs_band_midpoint_pct=price_vs_mid,
        suggested_band_low=suggested_low,
        suggested_band_high=suggested_high,
        suggested_stop=suggested_stop,
        needs_review=needs_review,
        skip_reason=None,
        reasons=reasons,
        data_date=data_date,
    )


def is_blocking_review(proposal: BandProposal) -> bool:
    """Return True when a review item should remain a dashboard-level blocker.

    Price-only extension above or below the existing midpoint is still useful to
    surface in the proposal artifact, but it is not by itself a trust blocker.
    A blocker should reflect structural drift, stale calibration, or missing
    numeric setup rather than deliberate no-chase posture.
    """
    if not proposal.needs_review or proposal.skip_reason is not None:
        return False

    if proposal.current_band_low is None or proposal.current_band_high is None or proposal.current_stop is None:
        return proposal.entry_policy == "band_defined"

    if proposal.suggested_band_low is None or proposal.suggested_band_high is None or proposal.suggested_stop is None:
        return proposal.entry_policy == "band_defined"

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
            print(f"    Close: {p.close}  MA20: {p.ma20}  ATR14: {p.atr14}")
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
                  f"price vs mid: {p.price_vs_band_midpoint_pct:+.1f}%"
                  if p.price_vs_band_midpoint_pct is not None
                  else f"  {p.ticker:<8}  band {p.current_band_low}–{p.current_band_high}  "
                       f"close {p.close}  ~{p.trading_days_old}d old")

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
        proposal = build_proposal(ticker, band, meta, tech_rec, yf_ticker)
        proposals.append(proposal)
        if proposal.skip_reason:
            print("skipped")
        elif proposal.needs_review:
            print("NEEDS REVIEW")
        else:
            print("ok")

    needs_review_count = sum(1 for p in proposals if p.needs_review)
    blocking_review_tickers = [p.ticker for p in proposals if is_blocking_review(p)]
    monitor_only_review_tickers = [
        p.ticker for p in proposals
        if p.needs_review and not p.skip_reason and p.ticker not in blocking_review_tickers
    ]
    ok_count = sum(1 for p in proposals if not p.needs_review and not p.skip_reason)
    skipped_count = sum(1 for p in proposals if p.skip_reason)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "needs_review" if needs_review_count > 0 else "ok",
        "stale_threshold_trading_days": STALE_TRADING_DAYS,
        "price_drift_threshold_pct": PRICE_DRIFT_PCT,
        "atr_stop_multiplier": ATR_STOP_MULTIPLIER,
        "atr_band_low_offset": ATR_BAND_LOW_OFFSET,
        "atr_band_high_offset": ATR_BAND_HIGH_OFFSET,
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
