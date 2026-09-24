"""Recommendation funnel: eligibility, context gates, and ranking (read-only).

Design: 06. Playbooks/Project Continuity/Recommendation Readiness Before
Ledger - 2026-09-23.md (items 4 and 6). Produces tmp/recommendation-funnel.json.
It changes no alert, band, thesis, or canon, sends nothing, and grants no
capital, order, account, or execution authority. Weights were approved by
Randall 2026-09-23 and stay uncalibrated until the ledger scorer can test them.

Funnel per name in the live controller scope:
1. Eligible: accepted thesis within review_due, fresh band (quote/level not in
   freshness_decay), non-null reference_confidence, price not below invalidation.
2. Context gates (never suppress an invalidation alert; they only decide
   whether a name is a recommendation-review candidate):
   - defensive macro posture raises the bar: conviction must be high, unless
     the thesis explicitly favors the current posture (owner-approved
     2026-09-23, e.g. a defensive franchise like CME);
   - thesis marks the current posture as disfavored: board only;
   - earnings within EARNINGS_WINDOW_DAYS: binary_event flag (kept, penalised).
3. Rank: weighted score of band position, conviction, regime fit, relative
   strength vs SPY and the sector ETF (63 sessions), catalyst clearance, and
   data confidence. Top TOP_N become recommendation-review candidates.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen

import thesis_record_validator as validator

FUNNEL_VERSION = "funnel-v1"
CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
MACRO_REL = "tmp/macro-signal-spine.json"
EARNINGS_REL = "tmp/earnings-calendar.json"
OUT_REL = "tmp/recommendation-funnel.json"
DEFENSIVE_POSTURES = {"defensive_review_bias", "defensive_neutral_selective"}
EARNINGS_WINDOW_DAYS = 10
RS_LOOKBACK = 63
TOP_N = 5
WEIGHTS = {  # owner-approved 2026-09-23 ~20:40 MST; uncalibrated until the ledger scorer tests them
    "band_position": 0.30, "conviction": 0.20, "regime_fit": 0.15,
    "relative_strength": 0.15, "catalyst_clear": 0.10, "data_confidence": 0.10,
}
CONVICTION = {"high": 1.0, "medium": 0.6, "low": 0.3}
CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_SYMBOLS = {"BRK.B": "BRK-B"}

Closes = Callable[[str], list[float]]


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def yahoo_closes(symbol: str) -> list[float]:
    url = f"{CHART}/{url_quote(YAHOO_SYMBOLS.get(symbol, symbol), safe='')}?interval=1d&range=6mo"
    raw = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 (review-only funnel)"}), timeout=25).read()
    result = json.loads(raw)["chart"]["result"][0]
    return [c for c in result["indicators"]["quote"][0]["close"] if isinstance(c, (int, float))]


def period_return(closes: list[float], n: int = RS_LOOKBACK) -> float | None:
    if len(closes) <= n or not closes[-n - 1]:
        return None
    return closes[-1] / closes[-n - 1] - 1


def band_position_score(row: dict) -> float | None:
    px, low, high, inv = (row.get("latest_price"), row.get("reference_low"), row.get("reference_high"),
                          row.get("invalidation_threshold"))
    if None in (px, low, high, inv):
        return None
    if px < inv:
        return None
    if px > high:
        return 0.0                      # above band: no chase
    if px < low:
        return 0.6                      # between invalidation and band low
    return 1.0 - 0.5 * (px - low) / (high - low) if high > low else 1.0  # nearer the low scores higher


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def evaluate(root: Path, *, closes: Closes = yahoo_closes, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rows = {r["ticker"]: r for r in load(root / CONTROLLER_REL).get("rows") or [] if r.get("ticker")}
    posture = (load(root / MACRO_REL).get("summary") or {}).get("macro_posture")
    earnings = {r["ticker"]: r.get("next_earnings_date") for r in load(root / EARNINGS_REL).get("records") or []
                if isinstance(r, dict) and r.get("ticker")}
    validation = validator.validate_dir(root, today=today)
    eligible_theses = set(validation["eligible"])
    cache: dict[str, list[float]] = {}

    def ret(symbol: str) -> float | None:
        if symbol not in cache:
            try:
                cache[symbol] = closes(symbol)
            except Exception:
                cache[symbol] = []
        return period_return(cache[symbol])

    names = []
    for ticker in sorted(rows):
        row = rows[ticker]
        thesis = load(root / validator.THESIS_REL / f"{ticker}.json")
        entry: dict[str, Any] = {"ticker": ticker, "stage": None, "reasons": [], "flags": []}
        conf = (row.get("sql_reference") or {}).get("reference_confidence")
        band = band_position_score(row)
        if ticker not in eligible_theses:
            entry["reasons"].append("no accepted thesis")
        if row.get("alert_state") == "freshness_decay":
            entry["reasons"].append("band or quote not fresh")
        if conf is None:
            entry["reasons"].append("no reference_confidence")
        if band is None:
            entry["reasons"].append("price below invalidation or levels missing")
        if entry["reasons"]:
            entry["stage"] = "monitor_only"
            names.append(entry)
            continue
        conviction = thesis.get("conviction")
        fit = thesis.get("regime_fit") or {}
        if posture in (fit.get("disfavored_postures") or []):
            entry["reasons"].append(f"thesis disfavors current macro posture ({posture})")
        favored = posture in (fit.get("favored_postures") or [])
        if posture in DEFENSIVE_POSTURES and conviction != "high" and not favored:
            entry["reasons"].append(f"defensive posture ({posture}) requires high conviction or a thesis that favors it; thesis is {conviction}")
        days = None
        if earnings.get(ticker):
            try:
                days = (date.fromisoformat(earnings[ticker]) - today).days
            except ValueError:
                days = None
        if days is not None and 0 <= days <= EARNINGS_WINDOW_DAYS:
            entry["flags"].append(f"binary_event: earnings in {days} days")
        sector = (thesis.get("benchmark") or {}).get("sector")
        r_name, r_spy = ret(ticker), ret("SPY")
        r_sector = ret(sector) if sector else None
        rs_parts = [r_name - b for b in (r_spy, r_sector) if r_name is not None and b is not None]
        rs = sum(rs_parts) / len(rs_parts) if rs_parts else None
        components = {
            "band_position": band,
            "conviction": CONVICTION.get(conviction, 0.3),
            "regime_fit": 1.0 if posture in (fit.get("favored_postures") or []) else
                          0.0 if posture in (fit.get("disfavored_postures") or []) else 0.5,
            "relative_strength": clamp01((rs + 0.10) / 0.20) if rs is not None else 0.5,
            "catalyst_clear": 0.0 if days is not None and 0 <= days <= EARNINGS_WINDOW_DAYS else 1.0,
            "data_confidence": clamp01(float(conf) / 0.5),
        }
        entry.update({
            "conviction": conviction, "thesis_type": thesis.get("thesis_type"), "days_to_earnings": days,
            "relative_strength_63d": {"vs_spy": None if r_name is None or r_spy is None else round(r_name - r_spy, 4),
                                      "vs_sector": None if r_name is None or r_sector is None else round(r_name - r_sector, 4),
                                      "sector_etf": sector},
            "components": {k: round(v, 3) for k, v in components.items()},
            "score": round(sum(WEIGHTS[k] * v for k, v in components.items()), 4),
            "price": row.get("latest_price"), "band": [row.get("reference_low"), row.get("reference_high")],
            "invalidation": row.get("invalidation_threshold"), "relationship": row.get("level_relationship_state"),
        })
        entry["stage"] = "board_only" if entry["reasons"] else "ranked"
        names.append(entry)
    ranked = sorted((n for n in names if n["stage"] == "ranked"), key=lambda n: -n["score"])
    for i, n in enumerate(ranked):
        n["rank"] = i + 1
        n["stage"] = "review_candidate" if i < TOP_N and n["components"]["band_position"] > 0 else "ranked_not_candidate"
    return {
        "schema": "veritas.recommendation_funnel.v1",
        "funnel_version": FUNNEL_VERSION,
        "weights_status": "owner_approved_uncalibrated",
        "weights": WEIGHTS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "macro_posture": posture,
        "scope_count": len(rows),
        "counts": {s: sum(1 for n in names if n["stage"] == s) for s in
                   ("review_candidate", "ranked_not_candidate", "board_only", "monitor_only")},
        "candidates": [n["ticker"] for n in names if n["stage"] == "review_candidate"],
        "names": names,
        "authority": {"review_only": True, "alert_or_canon_change": False, "delivery": False,
                      "capital_or_execution": False, "owner_approval_inferred": False},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only recommendation funnel.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    out = evaluate(root)
    if args.write:
        (root / OUT_REL).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("macro_posture", "counts", "candidates", "weights_status")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
