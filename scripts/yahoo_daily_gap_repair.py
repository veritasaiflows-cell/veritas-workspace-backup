"""Nightly Yahoo daily-bar gap check and same-source repair.

Owner-approved 2026-09-23 17:2x MST (Randall: "Proceed with the nightly cron
repair"), reversing the 2026-09-09 "no backfill" rule for this one mechanism:
Yahoo-only, automated, never manual entry, never another provider.

For every name in the live evaluated scope (read from the promoted controller,
so Phase 4 rotation is followed automatically), find daily bars Yahoo returns
as null and rebuild each from Yahoo's own 30-minute bars, but only when:

* the rebuild method reproduces Yahoo's official daily close on at least
  ``MIN_CALIBRATION_DAYS`` complete neighbouring sessions of the same name,
  with median error <= ``MEDIAN_CALIBRATION_ERROR`` and worst day <=
  ``MAX_CALIBRATION_ERROR`` (the last 30-minute bar is not the closing
  auction, so single-day outliers of 0.1-0.25% are normal);
* the gap is at least one session old: Yahoo posts the latest daily bar
  late in the evening, so the newest session is never treated as a gap;
* no dividend or split falls on the gap date;
* the intraday bars cover the session (at least ``MIN_INTRADAY_BARS``).

Accepted repairs are merged into a durable overlay
(``state/finance/price-repairs/yahoo-daily-repairs.json``) that the reference
level generator reads only where Yahoo's daily bar is null. Nothing here
writes canon: stored levels still change only through the owner-approved
renewal. All paths derive from ``root`` at call time.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SCHEMA_OVERLAY = "veritas.yahoo_daily_repairs.v1"
SCHEMA_REPORT = "veritas.yahoo_daily_gap_repair_report.v1"
OVERLAY_REL = "state/finance/price-repairs/yahoo-daily-repairs.json"
REPORT_REL = "tmp/yahoo-daily-gap-repair.json"
CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_SYMBOLS = {"BRK.B": "BRK-B"}
LOOKBACK_SESSIONS = 30          # 30-minute bars reach back ~60 calendar days
MEDIAN_CALIBRATION_ERROR = 0.001  # typical close error on complete days: 0.1%
MAX_CALIBRATION_ERROR = 0.005     # worst single day (closing-auction outlier): 0.5%
MIN_CALIBRATION_DAYS = 3
MIN_INTRADAY_BARS = 10          # a full session has 13 half-hour bars
EXCHANGE_TZ = ZoneInfo("America/New_York")
METHOD = "yahoo_30m_intraday_aggregate_v1"

HttpGet = Callable[[str], tuple[int, bytes]]


def default_http_get(url: str) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (review-only personal alert repair)"})
    with urlopen(request, timeout=25) as response:
        return int(response.status), response.read()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def scope_from_controller(root: Path) -> list[str]:
    try:
        controller = json.loads((root / CONTROLLER_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    tickers = {str(r.get("ticker")) for r in controller.get("rows") or [] if r.get("ticker")}
    return sorted(tickers)


def fetch_chart(ticker: str, interval: str, range_: str, http_get: HttpGet) -> dict | None:
    symbol = url_quote(YAHOO_SYMBOLS.get(ticker, ticker), safe="")
    url = f"{CHART}/{symbol}?interval={interval}&range={range_}&events=div%2Csplits"
    try:
        status, raw = http_get(url)
        if status != 200:
            return None
        result = json.loads(raw.decode("utf-8"))["chart"]["result"][0]
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def daily_bars(result: dict) -> tuple[dict[str, dict], set[str]]:
    """Return ({date: bar-or-None-fields}, event_dates)."""
    quote = result["indicators"]["quote"][0]
    out: dict[str, dict] = {}
    for i, ts in enumerate(result.get("timestamp") or []):
        day = datetime.fromtimestamp(int(ts), tz=EXCHANGE_TZ).date().isoformat()
        out[day] = {k: quote.get(k, [None] * (i + 1))[i] for k in ("open", "high", "low", "close", "volume")}
    events: set[str] = set()
    for kind in ("dividends", "splits"):
        for item in ((result.get("events") or {}).get(kind) or {}).values():
            if isinstance(item, dict) and finite(item.get("date")):
                events.add(datetime.fromtimestamp(int(item["date"]), tz=EXCHANGE_TZ).date().isoformat())
    return out, events


def intraday_daily(result: dict) -> dict[str, dict]:
    """Aggregate 30-minute bars into regular-session daily OHLCV."""
    quote = result["indicators"]["quote"][0]
    days: dict[str, list[tuple]] = {}
    for i, ts in enumerate(result.get("timestamp") or []):
        local = datetime.fromtimestamp(int(ts), tz=EXCHANGE_TZ)
        if not (9 * 60 + 30 <= local.hour * 60 + local.minute < 16 * 60):
            continue
        row = tuple(quote[k][i] for k in ("open", "high", "low", "close", "volume"))
        if not all(finite(v) for v in row[:4]):
            continue
        days.setdefault(local.date().isoformat(), []).append(row)
    out = {}
    for day, rows in days.items():
        out[day] = {
            "open": rows[0][0], "high": max(r[1] for r in rows), "low": min(r[2] for r in rows),
            "close": rows[-1][3], "volume": sum(r[4] for r in rows if finite(r[4])), "intraday_bars": len(rows),
        }
    return out


def complete(bar: dict | None) -> bool:
    return bool(bar) and all(finite(bar.get(k)) for k in ("open", "high", "low", "close", "volume"))


def evaluate_ticker(ticker: str, http_get: HttpGet, completed_through: str) -> dict[str, Any]:
    daily = fetch_chart(ticker, "1d", "3mo", http_get)
    if daily is None:
        return {"ticker": ticker, "status": "fetch_failed", "gaps": [], "repairs": {}}
    bars, events = daily_bars(daily)
    sessions = [d for d in sorted(bars) if d <= completed_through][-LOOKBACK_SESSIONS:]
    # Grace for the newest session: Yahoo posts it late; tomorrow's run repairs it if still null.
    gaps = [d for d in sessions[:-1] if not complete(bars[d])]
    pending = [d for d in sessions[-1:] if not complete(bars[d])]
    if not gaps:
        return {"ticker": ticker, "status": "clean", "gaps": [], "repairs": {}, "pending_latest": pending}
    intraday_result = fetch_chart(ticker, "30m", "60d", http_get)
    if intraday_result is None:
        return {"ticker": ticker, "status": "blocked", "gaps": gaps, "repairs": {},
                "blocked": {d: "intraday_fetch_failed" for d in gaps}}
    rebuilt = intraday_daily(intraday_result)
    errors = []
    for d in sessions:
        if complete(bars[d]) and d in rebuilt and rebuilt[d]["intraday_bars"] >= MIN_INTRADAY_BARS:
            errors.append((d, abs(rebuilt[d]["close"] - bars[d]["close"]) / bars[d]["close"]))
    ordered = sorted(e for _, e in errors)
    calibration = {
        "days": len(errors),
        "median_close_error": ordered[len(ordered) // 2] if ordered else None,
        "max_close_error": ordered[-1] if ordered else None,
        "dates": [d for d, _ in errors],
    }
    calibrated = (len(errors) >= MIN_CALIBRATION_DAYS
                  and calibration["median_close_error"] <= MEDIAN_CALIBRATION_ERROR
                  and calibration["max_close_error"] <= MAX_CALIBRATION_ERROR)
    repairs: dict[str, dict] = {}
    blocked: dict[str, str] = {}
    for d in gaps:
        if not calibrated:
            blocked[d] = "method_not_calibrated_for_ticker"
        elif d in events:
            blocked[d] = "corporate_action_on_gap_date"
        elif d not in rebuilt or rebuilt[d]["intraday_bars"] < MIN_INTRADAY_BARS:
            blocked[d] = "insufficient_intraday_coverage"
        else:
            r = rebuilt[d]
            repairs[d] = {
                "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"], "volume": r["volume"],
                "method": METHOD, "intraday_bars": r["intraday_bars"], "repaired_at_utc": utc_now(),
                "calibration": {"days": calibration["days"],
                                "median_close_error": round(calibration["median_close_error"], 6),
                                "max_close_error": round(calibration["max_close_error"], 6)},
            }
    status = "repaired" if repairs and not blocked else "partial" if repairs else "blocked"
    return {"ticker": ticker, "status": status, "gaps": gaps, "repairs": repairs, "blocked": blocked,
            "calibration": calibration, "pending_latest": pending}


def run(root: Path, *, tickers: list[str] | None = None, http_get: HttpGet = default_http_get,
        completed_through: str | None = None, write: bool = False) -> dict[str, Any]:
    scope = tickers if tickers is not None else scope_from_controller(root)
    if completed_through is None:
        now_ny = datetime.now(EXCHANGE_TZ)
        completed_through = (now_ny.date() if now_ny.hour >= 17 else
                             date.fromordinal(now_ny.date().toordinal() - 1)).isoformat()
    overlay_path = root / OVERLAY_REL
    try:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        overlay = {"schema": SCHEMA_OVERLAY, "repairs": {}}
    results = [evaluate_ticker(t, http_get, completed_through) for t in scope]
    added = 0
    for result in results:
        existing = overlay["repairs"].setdefault(result["ticker"], {})
        for day, repair in result["repairs"].items():
            if day not in existing:  # first accepted repair is kept; never silently rewritten
                existing[day] = repair
                added += 1
        if not existing:
            overlay["repairs"].pop(result["ticker"], None)
    blocked = {r["ticker"]: r["blocked"] for r in results if r.get("blocked")}
    failed = [r["ticker"] for r in results if r["status"] == "fetch_failed"]
    report = {
        "schema": SCHEMA_REPORT,
        "generated_at_utc": utc_now(),
        "completed_through": completed_through,
        "scope_source": "explicit" if tickers is not None else CONTROLLER_REL,
        "scope_count": len(scope),
        "status": "error" if not scope else "warning" if blocked or failed else "ok",
        "gaps_found": sum(len(r["gaps"]) for r in results),
        "repairs_added": added,
        "blocked": blocked,
        "fetch_failed": failed,
        "results": [{k: v for k, v in r.items() if k != "repairs"} | {"repaired_dates": sorted(r["repairs"])}
                    for r in results],
        "overlay_path": OVERLAY_REL,
        "authority": {"canon_write": False, "manual_entry": False, "other_provider": False,
                      "delivery": False, "owner_approval_inferred": False},
    }
    if write:
        if added:
            overlay["updated_at_utc"] = report["generated_at_utc"]
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = overlay_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(overlay_path)
        (root / REPORT_REL).parent.mkdir(parents=True, exist_ok=True)
        (root / REPORT_REL).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--ticker", action="append", help="override scope (diagnostic)")
    ap.add_argument("--completed-through", help="last completed session YYYY-MM-DD")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args(argv)
    report = run(Path(args.root), tickers=args.ticker, completed_through=args.completed_through, write=args.write)
    print(json.dumps({k: report[k] for k in ("status", "scope_count", "gaps_found", "repairs_added",
                                            "blocked", "fetch_failed", "completed_through")}, indent=2))
    # Blocked gaps are a truthful warning, not a job failure; an empty scope is.
    return 1 if args.validate and report["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
