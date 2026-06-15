#!/usr/bin/env python3
"""Build a WF55/WF69 review-only historical regime event library.

This slice uses historical regimes as base-rate and stress-context evidence.
It does not emit calibrated probabilities, predictive scores, expected-return
claims, model-ranked deployment, capital approval, or trading authority.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

try:
    import yfinance as yf
except Exception:  # pragma: no cover - runtime dependency check handles this
    yf = None

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "historical-regime-event-library.json"
OUT_MD = TMP / "historical-regime-event-library.md"
WF61_FEED = TMP / "small-mid-cap-regime-feed.json"

SCHEMA = "veritas.historical_regime_event_library.v1"
HISTORY_START = "1968-01-01"
FORWARD_WINDOWS = (20, 60, 120, 252)
SYMBOLS = {
    "large_cap": "^GSPC",
    "small_cap": "^RUT",
    "tech": "^IXIC",
    "rates_proxy": "^TNX",
}

AUTHORITY: dict[str, bool] = {
    "report_only": True,
    "base_rate_context_only": True,
    "calibrated_probability_allowed": False,
    "prediction_allowed": False,
    "model_ranked_deployment_allowed": False,
    "return_projection_claim_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "capital_action_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inference_allowed": False,
}

EVENTS: list[dict[str, Any]] = [
    {
        "event_id": "1973_1974_oil_stagflation_bear",
        "label": "1973-1974 oil shock / stagflation bear market",
        "start": "1973-10-01",
        "end": "1974-12-31",
        "shock_types": ["war", "oil_supply_shock", "inflation", "bear_market"],
        "setup": "Oil embargo, inflation pressure, recession risk, equity de-rating.",
        "analog_notes": "Useful for inflation/geopolitical stress context; small-cap proxy data is weak for this era.",
    },
    {
        "event_id": "1980_1982_volcker_tightening",
        "label": "1980-1982 Volcker tightening / recession",
        "start": "1980-01-01",
        "end": "1982-08-12",
        "shock_types": ["inflation", "rate_shock", "recession", "policy_tightening"],
        "setup": "Restrictive monetary policy used to break inflation, with recessionary pressure.",
        "analog_notes": "Useful for rate-shock and inflation-break context, but market structure differs materially from today.",
    },
    {
        "event_id": "1987_crash",
        "label": "1987 crash",
        "start": "1987-10-19",
        "end": "1988-02-01",
        "shock_types": ["crash", "liquidity_shock", "valuation_unwind"],
        "setup": "Rapid index drawdown and liquidity stress after a strong bull run.",
        "analog_notes": "Useful for crash recovery/base-rate context, not a macro recession analog by itself.",
    },
    {
        "event_id": "1990_gulf_war_recession",
        "label": "1990 Gulf War / recession shock",
        "start": "1990-08-02",
        "end": "1991-03-01",
        "shock_types": ["war", "oil_shock", "recession", "credit_stress"],
        "setup": "Iraq invaded Kuwait, oil shock and U.S. recession risk hit cyclicals.",
        "analog_notes": "Useful for war/oil shock plus recession-risk sequencing.",
    },
    {
        "event_id": "1994_rate_shock",
        "label": "1994 bond/rate shock",
        "start": "1994-02-04",
        "end": "1994-12-31",
        "shock_types": ["rate_shock", "policy_tightening", "bond_selloff"],
        "setup": "Fed tightening surprised markets and hit rate-sensitive assets.",
        "analog_notes": "Useful for rate-stabilization comparison after a rate shock.",
    },
    {
        "event_id": "1998_ltcM_emerging_market_stress",
        "label": "1998 LTCM / emerging-market stress",
        "start": "1998-08-17",
        "end": "1998-12-31",
        "shock_types": ["liquidity_shock", "credit_stress", "emerging_market_stress"],
        "setup": "Credit/liquidity shock with policy backstop and rapid risk recovery.",
        "analog_notes": "Useful for liquidity-stress rebound context.",
    },
    {
        "event_id": "2000_2002_dotcom_bust",
        "label": "2000-2002 dot-com bust",
        "start": "2000-03-10",
        "end": "2002-10-09",
        "shock_types": ["valuation_unwind", "bear_market", "recession", "tech_bust"],
        "setup": "Speculative technology valuation unwind and broad earnings reset.",
        "analog_notes": "Useful for concentration/valuation bubble unwinds.",
    },
    {
        "event_id": "2007_2009_gfc",
        "label": "2007-2009 Global Financial Crisis",
        "start": "2007-10-09",
        "end": "2009-03-09",
        "shock_types": ["credit_crisis", "banking_crisis", "recession", "liquidity_shock"],
        "setup": "Housing, credit, banking, and liquidity shock with severe recession.",
        "analog_notes": "Useful as deep credit-stress comparator; not comparable to ordinary rate stabilization.",
    },
    {
        "event_id": "2011_eurozone_debt_ceiling",
        "label": "2011 Eurozone / U.S. debt-ceiling stress",
        "start": "2011-07-22",
        "end": "2011-10-03",
        "shock_types": ["sovereign_stress", "policy_stress", "risk_off"],
        "setup": "Sovereign and fiscal-policy stress hit risk appetite.",
        "analog_notes": "Useful for policy-stress drawdown and recovery context.",
    },
    {
        "event_id": "2020_covid_crash_rebound",
        "label": "2020 COVID crash / policy rebound",
        "start": "2020-02-19",
        "end": "2020-04-30",
        "shock_types": ["pandemic", "crash", "liquidity_shock", "policy_backstop"],
        "setup": "Exogenous shutdown shock followed by aggressive monetary/fiscal backstop.",
        "analog_notes": "Useful for crash/base-rate context but structurally unusual because of policy speed and scale.",
    },
    {
        "event_id": "2022_inflation_rate_shock",
        "label": "2022 inflation / rate shock",
        "start": "2022-01-03",
        "end": "2022-10-12",
        "shock_types": ["inflation", "rate_shock", "valuation_unwind", "bear_market"],
        "setup": "Inflation shock, rapid Fed tightening, multiple compression, and duration pain.",
        "analog_notes": "Most directly useful for current rate-stabilization comparisons.",
    },
    {
        "event_id": "2023_2024_soft_landing_broadening",
        "label": "2023-2024 soft-landing / broadening attempt",
        "start": "2023-10-27",
        "end": "2024-03-28",
        "shock_types": ["rate_stabilization", "soft_landing", "bull_market", "breadth_repair"],
        "setup": "Inflation cooled, recession was delayed, yields stabilized, and risk appetite broadened.",
        "analog_notes": "Useful for small/mid-cap broadening under rate-stabilization thesis.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
    except Exception:
        return None
    if not math.isfinite(result):
        return None
    return result


def fetch_history(symbol: str) -> list[dict[str, Any]]:
    if yf is None:
        return []
    hist = yf.Ticker(symbol).history(start=HISTORY_START, auto_adjust=False)
    rows: list[dict[str, Any]] = []
    if hist is None or hist.empty:
        return rows
    for idx, row in hist.iterrows():
        close = safe_float(row.get("Close"))
        if close is None:
            continue
        date_value = getattr(idx, "date", lambda: idx)()
        rows.append({"date": str(date_value), "close": close})
    return rows


def first_on_or_after(rows: list[dict[str, Any]], target: datetime) -> dict[str, Any] | None:
    target_key = target.date().isoformat()
    for row in rows:
        if str(row.get("date")) >= target_key:
            return row
    return None


def last_on_or_before(rows: list[dict[str, Any]], target: datetime) -> dict[str, Any] | None:
    target_key = target.date().isoformat()
    result = None
    for row in rows:
        if str(row.get("date")) <= target_key:
            result = row
        else:
            break
    return result


def pct(start: float | None, end: float | None) -> float | None:
    if start in (None, 0) or end is None:
        return None
    return round((end - start) / start * 100.0, 4)


def drawdown(rows: list[dict[str, Any]], start: datetime, end: datetime) -> float | None:
    scoped = [row for row in rows if start.date().isoformat() <= str(row.get("date")) <= end.date().isoformat()]
    if not scoped:
        return None
    closes = [float(row["close"]) for row in scoped if row.get("close") is not None]
    if not closes:
        return None
    peak = closes[0]
    worst = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak:
            worst = min(worst, (close - peak) / peak * 100.0)
    return round(worst, 4)


def compute_symbol_event(rows: list[dict[str, Any]], start: datetime, end: datetime) -> dict[str, Any]:
    start_row = first_on_or_after(rows, start)
    end_row = last_on_or_before(rows, end)
    event_return = pct(safe_float(start_row.get("close")) if start_row else None, safe_float(end_row.get("close")) if end_row else None)
    forward: dict[str, Any] = {}
    for days in FORWARD_WINDOWS:
        from_row = end_row
        to_row = first_on_or_after(rows, end + timedelta(days=days))
        forward[f"{days}d"] = pct(safe_float(from_row.get("close")) if from_row else None, safe_float(to_row.get("close")) if to_row else None)
    return {
        "status": "ok" if start_row and end_row else "insufficient_history",
        "start_price_date": start_row.get("date") if start_row else None,
        "end_price_date": end_row.get("date") if end_row else None,
        "event_window_return_pct": event_return,
        "event_window_max_drawdown_pct": drawdown(rows, start, end) if start_row and end_row else None,
        "forward_returns_pct": forward,
    }


def qualitative_base_rate(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if value >= 10:
        return "strong_positive"
    if value > 0:
        return "positive"
    if value <= -10:
        return "strong_negative"
    if value < 0:
        return "negative"
    return "flat"


def compare_small_large(large: dict[str, Any], small: dict[str, Any]) -> dict[str, Any]:
    forward: dict[str, Any] = {}
    for window in (f"{days}d" for days in FORWARD_WINDOWS):
        lval = safe_float((large.get("forward_returns_pct") or {}).get(window))
        sval = safe_float((small.get("forward_returns_pct") or {}).get(window))
        forward[window] = round(sval - lval, 4) if lval is not None and sval is not None else None
    event_large = safe_float(large.get("event_window_return_pct"))
    event_small = safe_float(small.get("event_window_return_pct"))
    return {
        "status": "ok" if event_large is not None and event_small is not None else "unavailable",
        "event_window_small_minus_large_pct": round(event_small - event_large, 4) if event_large is not None and event_small is not None else None,
        "forward_small_minus_large_pct": forward,
    }


def current_context() -> dict[str, Any]:
    wf61 = load_json_artifact(WF61_FEED) if WF61_FEED.exists() else None
    context: dict[str, Any] = {
        "source_artifact": rel(WF61_FEED),
        "source_exists": WF61_FEED.exists(),
        "market_data_as_of": None,
        "small_cap_proxy_state": "unknown",
        "current_analog_tags": ["rate_stabilization", "breadth_repair", "small_mid_broadening_review"],
    }
    if isinstance(wf61, dict):
        context["market_data_as_of"] = wf61.get("market_data_as_of")
        bucket_summary = (((wf61.get("summary") or {}).get("bucket_summary") or {}))
        small_buckets = {key: value for key, value in bucket_summary.items() if str(key).startswith("small_cap")}
        improving = []
        for value in small_buckets.values():
            if isinstance(value, dict):
                improving.extend(value.get("improving") or [])
        context["small_cap_proxy_state"] = "improving" if improving else "not_confirmed"
        context["small_cap_improving_proxies"] = sorted(set(improving))
    return context


def validate_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})

    authority = payload.get("authority") or {}
    for key, value in AUTHORITY.items():
        add(f"authority_{key}", authority.get(key) is value, authority.get(key))
    events = payload.get("events") or []
    add("event_count_minimum", len(events) >= 10, len(events))
    add("pre_1990_events_present", any(str(row.get("start")) < "1990-01-01" for row in events), [row.get("event_id") for row in events if str(row.get("start")) < "1990-01-01"])
    add("modern_events_present", any(str(row.get("start")) >= "2000-01-01" for row in events), [row.get("event_id") for row in events if str(row.get("start")) >= "2000-01-01"])
    add("large_cap_history_present", all((row.get("outcomes") or {}).get("large_cap", {}).get("status") == "ok" for row in events), [row.get("event_id") for row in events if (row.get("outcomes") or {}).get("large_cap", {}).get("status") != "ok"])
    add("small_large_comparison_available_some", sum(1 for row in events if (row.get("small_vs_large") or {}).get("status") == "ok") >= 5, sum(1 for row in events if (row.get("small_vs_large") or {}).get("status") == "ok"), "warning")
    forbidden_text = json.dumps(payload, sort_keys=True).lower()
    forbidden_phrases = ["win probability", "expected return", "model-ranked", "% chance", "trade approval"]
    found = [phrase for phrase in forbidden_phrases if phrase in forbidden_text]
    add("forbidden_probability_language_absent", not found, found)
    return checks


def build_payload() -> dict[str, Any]:
    histories = {name: fetch_history(symbol) for name, symbol in SYMBOLS.items()}
    events: list[dict[str, Any]] = []
    for event in EVENTS:
        start = parse_date(event["start"])
        end = parse_date(event["end"])
        outcomes = {name: compute_symbol_event(rows, start, end) for name, rows in histories.items()}
        large = outcomes["large_cap"]
        small = outcomes["small_cap"]
        event_row = {
            **event,
            "outcomes": outcomes,
            "small_vs_large": compare_small_large(large, small),
            "base_rate_context": {
                "large_cap_60d_forward_bucket": qualitative_base_rate((large.get("forward_returns_pct") or {}).get("60d")),
                "small_cap_60d_forward_bucket": qualitative_base_rate((small.get("forward_returns_pct") or {}).get("60d")),
                "usefulness": "base_rate_context_only",
            },
            "comparability_limits": [
                "Historical market structure, sector composition, policy reaction functions, and data availability differ from current conditions.",
                "This row supports analog review and stress framing only; it is not a calibrated live forecast.",
            ],
        }
        events.append(event_row)

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF55/WF69",
        "consumer_posture": "review_only",
        "purpose": "Historical regime/event analog and base-rate context for probability readiness without probability claims.",
        "authority": AUTHORITY,
        "data_sources": {
            "price_provider": "yfinance historical daily bars",
            "symbols": SYMBOLS,
            "history_start": HISTORY_START,
            "forward_windows": list(FORWARD_WINDOWS),
        },
        "current_context": current_context(),
        "events": events,
        "summary": {
            "event_count": len(events),
            "pre_1990_event_count": sum(1 for row in events if str(row.get("start")) < "1990-01-01"),
            "post_2000_event_count": sum(1 for row in events if str(row.get("start")) >= "2000-01-01"),
            "small_large_comparison_available_count": sum(1 for row in events if (row.get("small_vs_large") or {}).get("status") == "ok"),
            "rate_stabilization_direct_events": [row["event_id"] for row in events if "rate_stabilization" in row.get("shock_types", []) or "rate_shock" in row.get("shock_types", [])],
        },
        "next_use_contract": {
            "allowed": [
                "stress analog context",
                "historical base-rate table",
                "current-regime comparison prompt",
                "candidate research prioritization context",
            ],
            "blocked": [
                "calibrated probability",
                "deployment ranking",
                "expected-return output",
                "capital action",
                "paper/live execution",
                "owner approval inference",
            ],
        },
    }
    checks = validate_payload(payload)
    payload["validation"] = {
        "status": "ok" if all(check["ok"] or check["severity"] == "warning" for check in checks) else "fail",
        "checks": checks,
        "critical_count": sum(1 for check in checks if not check["ok"] and check["severity"] == "critical"),
        "warning_count": sum(1 for check in checks if not check["ok"] and check["severity"] == "warning"),
    }
    if payload["validation"]["critical_count"]:
        payload["status"] = "blocked"
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Historical Regime Event Library",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Events: `{payload.get('summary', {}).get('event_count')}`",
        f"- Small/large comparisons available: `{payload.get('summary', {}).get('small_large_comparison_available_count')}`",
        "",
        "## Boundary",
        "",
        "Review-only historical analog and base-rate context. No calibrated probability, deployment ranking, capital action, or execution authority.",
        "",
        "## Event Table",
        "",
        "| Event | Start | Shock Types | Large 60d | Small 60d | Small minus large 60d | Use |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for row in payload.get("events") or []:
        large = ((row.get("outcomes") or {}).get("large_cap") or {}).get("forward_returns_pct") or {}
        small = ((row.get("outcomes") or {}).get("small_cap") or {}).get("forward_returns_pct") or {}
        rel = ((row.get("small_vs_large") or {}).get("forward_small_minus_large_pct") or {})
        lines.append(
            f"| {row.get('label')} | {row.get('start')} | {', '.join(row.get('shock_types') or [])} | "
            f"{large.get('60d')} | {small.get('60d')} | {rel.get('60d')} | base-rate context |"
        )
    lines.extend([
        "",
        "## Next Use",
        "",
        "- Use as stress-context and analog evidence inside WF55/WF69.",
        "- Use as context for WF61/WF78 small/mid-cap broadening, especially rate-shock and rate-stabilization rows.",
        "- Keep all downstream language review-only until WF55 outcome depth and no-hindsight gates clear.",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF55/WF69 historical regime analog library.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.write:
        atomic_write_json(OUT_JSON, payload)
        atomic_write_text(OUT_MD, render_markdown(payload))
    print(json.dumps({
        "status": payload["status"],
        "validation": payload["validation"]["status"],
        "events": payload["summary"]["event_count"],
        "small_large_comparisons": payload["summary"]["small_large_comparison_available_count"],
        "out_json": rel(OUT_JSON) if args.write else None,
        "out_md": rel(OUT_MD) if args.write else None,
    }, indent=2))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
