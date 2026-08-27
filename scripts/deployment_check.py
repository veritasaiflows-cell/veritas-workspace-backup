"""deployment_check.py

Reads tmp/technical-refresh.json and tmp/market-state.json and outputs a
ranked deployment readiness table. Run this at session start to instantly
know which names are in their entry bands, which are blocked, and which need
more patience.

Usage:
    python scripts/deployment_check.py

No network calls. Reads only from the tmp/ cache files written by
technical_refresh.py and market_state_refresh.py.

Outputs:
    tmp/deployment-check.json   -- structured deployment-state summary
    Terminal summary            -- human-readable ranked table
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE   = Path(__file__).resolve().parents[1]
TECH_PATH   = WORKSPACE / "tmp" / "technical-refresh.json"
STATE_PATH  = WORKSPACE / "tmp" / "market-state.json"
CONFIG_PATH = WORKSPACE / "tmp" / "portfolio-config.json"
EARNINGS_PATH = WORKSPACE / "tmp" / "earnings-calendar.json"
BAND_PROPOSALS_PATH = WORKSPACE / "tmp" / "band-proposals.json"
OUT_PATH    = WORKSPACE / "tmp" / "deployment-check.json"
STALE_HOURS = 24
SCHEMA_VERSION = 1

PRIORITY: dict[str, int] = {
    "DEPLOYABLE NOW": 1,
    "PROMOTION REVIEW": 2,
    "ALMOST DEPLOYABLE": 2,
    "ENTRY POLICY REVIEW": 3,
    "BLOCKED": 4,
    "BELOW STOP": 5,
    "BENCH": 6,
    "WATCH / RESEARCH NEEDED": 7,
    "ERROR": 8,
}


def _formal_reclaim_debt_active(rec: dict[str, Any], meta: dict[str, Any]) -> bool:
    proposal = meta.get("_band_proposal")
    if not isinstance(proposal, dict):
        return False
    if proposal.get("canonical_apply_eligible") is True:
        return False
    if str(proposal.get("band_status") or "").upper() not in {"RECLAIM_ONLY", "BELOW_STOP"}:
        return False
    suggested_low = proposal.get("suggested_band_low")
    suggested_stop = proposal.get("suggested_stop")
    close = rec.get("close")
    if close is None or suggested_low is None:
        return False
    if suggested_stop is not None and close < suggested_stop:
        return False
    return close < suggested_low


def classify(rec: dict[str, Any], blocked: bool, meta: dict[str, Any]) -> tuple[str, str]:
    close = rec.get("close")
    in_band = rec.get("in_entry_band")
    below_stop = rec.get("below_stop")
    notes = rec.get("notes") or []
    coverage_lane = (meta.get("coverage_lane") or "").lower()
    entry_policy = (meta.get("entry_policy") or "").lower()
    workflow_state = (meta.get("workflow_state") or "").upper()
    owner_text = " ".join(
        str(meta.get(key) or "")
        for key in ("thesis_status", "trigger_condition", "authority_conflict")
    ).lower()
    approval_recorded_trigger_not_live = (
        bool(meta.get("owner_approval_date"))
        and ("trigger not live" in owner_text or "trigger is not live" in owner_text)
        and (
            "no automatic execution" in owner_text
            or "not deployable" in owner_text
            or "wait/no-chase" in owner_text
        )
    )
    repair_mode = workflow_state == "REPAIR" or bool(meta.get("repair_mode"))
    force_below_stop = bool(meta.get("force_do_not_touch_if_below_stop"))

    if close is None:
        msg = notes[0] if notes else "unknown"
        return "ERROR", "fetch failed -- " + msg

    # Repair mode is an owner-layer workflow gate. A simple below-stop technical
    # read must not erase that deliberate bench/do-not-touch judgment unless the
    # config explicitly says to force below-stop handling.
    if repair_mode and not (below_stop and force_below_stop):
        if in_band:
            return "BENCH", f"in band at {round(close, 2)} but workflow state is REPAIR -- wait for setup to rebuild"
        return "BENCH", "workflow state is REPAIR -- wait for setup to rebuild"

    if below_stop:
        if coverage_lane and coverage_lane != "execution":
            return "BELOW STOP", f"close {round(close, 2)} is below stop -- {coverage_lane}-lane monitor only, not execution-board entitled"
        return "BELOW STOP", f"close {round(close, 2)} is below stop -- do not deploy"

    if blocked:
        if in_band:
            return "BLOCKED", f"in entry band at {round(close, 2)} but earnings block active"
        return "BLOCKED", "earnings block active -- wait for print"

    if workflow_state == "DEPLOYED":
        if in_band:
            return "DEPLOYABLE NOW", f"owner-approved setup remains in entry band at {round(close, 2)}"
        if in_band is None:
            return "WATCH / RESEARCH NEEDED", "owner-approved setup is missing decision-grade entry-band data -- refresh levels before relying on it"
        return "ALMOST DEPLOYABLE", "owner-approved setup, but current close is outside the live entry band -- wait for reclaim or approved band update"

    if workflow_state == "WATCH":
        if in_band is None and entry_policy == "underdefined":
            if coverage_lane and coverage_lane != "execution":
                return "WATCH / RESEARCH NEEDED", f"{coverage_lane}-lane only -- explicit entry and stop are not defined yet"
            return "WATCH / RESEARCH NEEDED", "setup is not yet decision-grade -- requires explicit entry and stop definition"
        if coverage_lane and coverage_lane != "execution":
            if in_band:
                return "ENTRY POLICY REVIEW", f"in band, but {coverage_lane}-lane only -- main-session entry-policy review required; no execution-board entitlement"
            return "WATCH / RESEARCH NEEDED", f"{coverage_lane}-lane only -- not in execution-board scope yet"
        if in_band:
            return "ENTRY POLICY REVIEW", "in band, but this setup remains watch-only until main-session entry-policy review"
        return "WATCH / RESEARCH NEEDED", "levels are defined, but this execution setup remains watch-only until it is intentionally promoted"

    if workflow_state == "PROMOTION REVIEW":
        if in_band:
            return "PROMOTION REVIEW", f"in band at {round(close, 2)} -- portfolio-review only; separate owner model/sleeve/deployment decision required"
        if in_band is None:
            return "PROMOTION REVIEW", "portfolio-review only, but decision-grade numeric entry-band/stop data is missing -- refresh levels before review"
        return "PROMOTION REVIEW", "portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision"

    if workflow_state == "ALMOST":
        if _formal_reclaim_debt_active(rec, meta):
            return "ALMOST DEPLOYABLE", "formal reclaim band is not live -- wait for reclaim or explicit approved review"
        if approval_recorded_trigger_not_live:
            return "ALMOST DEPLOYABLE", "approval recorded, but trigger is not live -- wait for reclaim or explicit approved review"
        if in_band:
            return "PROMOTION REVIEW", f"in band at {round(close, 2)} -- explicit owner promotion review required before deployable-now status"
        return "ALMOST DEPLOYABLE", "workflow state is ALMOST -- constructive but not yet promoted"

    if entry_policy == "underdefined":
        if in_band:
            return "ENTRY POLICY REVIEW", "in band with underdefined entry policy -- main-session review required before recommendation"
        return "WATCH / RESEARCH NEEDED", "setup is not yet decision-grade -- requires explicit entry and stop definition"

    above_ma20 = rec.get("above_ma20")
    above_ma50 = rec.get("above_ma50")
    above_ma200 = rec.get("above_ma200")
    below_20_and_50 = (above_ma20 is False and above_ma50 is False)
    below_50_and_200 = (above_ma50 is False and above_ma200 is False)
    chart_weak = below_20_and_50 or below_50_and_200
    if chart_weak:
        if in_band:
            return "BENCH", f"in band at {round(close, 2)} but chart structure weak -- wait for posture to improve"
        return "BENCH", "chart structure weak -- wait for setup to improve"

    if in_band:
        return "DEPLOYABLE NOW", f"close {round(close, 2)} is within entry band"

    if in_band is None:
        return "WATCH / RESEARCH NEEDED", "entry band not yet defined -- research needed"

    return "ALMOST DEPLOYABLE", f"close {round(close, 2)} -- posture constructive but not yet in band"


def age_hours(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2)
    except Exception:
        return None


def fmt_age(hours: float | None) -> str:
    if hours is None:
        return "unknown age"
    if hours < 1:
        return f"{int(hours * 60)}m old"
    return f"{round(hours, 1)}h old"


def _fmt_num(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "--"
    fmt = "{:>8." + str(decimals) + "f}"
    return fmt.format(val)


def build_summary(names: list[str]) -> str:
    return ", ".join(names) if names else "none"


def main() -> None:
    sep = "=" * 74
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("")
    print(sep)
    print("  DEPLOYMENT CHECK  --  " + now)
    print(sep)

    if not TECH_PATH.exists():
        print("\n  ERROR: tmp/technical-refresh.json not found.")
        print("  Run: python scripts/technical_refresh.py\n")
        sys.exit(1)

    tech_raw = json.loads(TECH_PATH.read_text(encoding="utf-8"))
    tech_age = age_hours(tech_raw.get("generated_at_utc"))
    tech_stale_after = tech_raw.get("stale_after_hours", STALE_HOURS)
    tech_stale = tech_age is not None and tech_age > tech_stale_after
    records = tech_raw.get("records", [])

    if not records:
        print("\n  ERROR: technical-refresh.json contains no records.\n")
        sys.exit(1)

    state: dict[str, Any] | None = None
    state_age: float | None = None
    state_stale_after: int | float = STALE_HOURS
    state_stale = False
    state_warning: str | None = None
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            state_age = age_hours(state.get("generated_at_utc"))
            state_stale_after = state.get("stale_after_hours", STALE_HOURS)
            state_stale = state_age is not None and state_age > state_stale_after
        except Exception as exc:
            state = None
            state_warning = "market-state.json unreadable: " + str(exc)
    else:
        state_warning = "market-state.json not found"

    if state is not None and state.get("status") in ("ok", "partial"):
        d = state["data"]
        spx = d["equities"].get("spx")
        vix = d["volatility"].get("vix")
        y10 = d["treasuries"].get("10y")
        brent = d["energy"].get("brent")

        spx_s = "{:,.2f}".format(spx) if spx is not None else "n/a"
        vix_s = "{:.2f}".format(vix) if vix is not None else "n/a"
        y10_s = "{:.3f}%".format(y10) if y10 is not None else "n/a"
        brent_s = "${:.2f}".format(brent) if brent is not None else "n/a"

        print("\n  MARKET STATE")
        print("  " + "{:<14} {}".format("S&P 500", spx_s))
        print("  " + "{:<14} {}".format("VIX", vix_s))
        print("  " + "{:<14} {}".format("10Y Treasury", y10_s))
        print("  " + "{:<14} {}".format("Brent", brent_s))

    print("")
    age_str = "Technical data: " + fmt_age(tech_age)
    if tech_stale:
        age_str += "  *** STALE -- run technical_refresh.py ***"
    print("  " + age_str)
    if state_age is not None:
        state_age_str = "Market-state data: " + fmt_age(state_age)
        if state_stale:
            state_age_str += "  *** STALE -- run market_state_refresh.py ***"
        print("  " + state_age_str)
    elif state_warning:
        print("  Market-state data: unavailable -- " + state_warning)

    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    band_proposals_by_ticker: dict[str, dict[str, Any]] = {}
    if BAND_PROPOSALS_PATH.exists():
        try:
            band_proposals = json.loads(BAND_PROPOSALS_PATH.read_text(encoding="utf-8"))
            band_proposals_by_ticker = {
                proposal["ticker"]: proposal
                for proposal in (band_proposals.get("proposals") or [])
                if isinstance(proposal, dict) and proposal.get("ticker")
            }
        except Exception:
            band_proposals_by_ticker = {}

    earnings = {}
    if EARNINGS_PATH.exists():
        try:
            earnings = json.loads(EARNINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    last_trading_day = tech_raw.get("last_trading_day")
    blocked_tickers = set()
    if last_trading_day:
        try:
            ltd = datetime.fromisoformat(last_trading_day).date()
            for er in earnings.get("records", []):
                ticker = er.get("ticker")
                ed = er.get("next_earnings_date")
                if not ticker or not ed:
                    continue
                meta = config.get("tracked_universe", {}).get(ticker, {})
                if meta.get("earnings_policy") == "block_pre_earnings":
                    try:
                        ed_date = datetime.fromisoformat(ed).date()
                        if 0 <= (ed_date - ltd).days <= 14:
                            blocked_tickers.add(ticker)
                    except Exception:
                        pass
        except Exception:
            pass

    rows: list[dict[str, Any]] = []
    for rec in records:
        ticker = rec.get("ticker")
        blocked = ticker in blocked_tickers
        meta = dict(config.get("tracked_universe", {}).get(ticker, {}))
        if ticker in band_proposals_by_ticker:
            meta["_band_proposal"] = band_proposals_by_ticker[ticker]
        label, reason = classify(rec, blocked, meta)
        enriched = dict(rec)
        enriched["earnings_blocked"] = blocked
        enriched["action_state"] = label
        enriched["reason"] = reason
        enriched["priority"] = PRIORITY.get(label, 99)
        rows.append(enriched)
    rows.sort(key=lambda x: (x.get("priority", 99), x.get("ticker", "")))

    print("\n  " + "{:<8}  {:<14}  {:>8}  {:>8}  {:>8}  {:>8}".format(
        "Ticker", "State", "Close", "MA20", "MA50", "MA200"))
    print("  " + "-" * 68)

    prev_pri = None
    for rec in rows:
        pri = rec.get("priority", 99)
        if prev_pri is not None and pri != prev_pri:
            print("")
        prev_pri = pri

        t = rec.get("ticker", "?")
        c_s = _fmt_num(rec.get("close"))
        m20 = _fmt_num(rec.get("ma20"))
        m50 = _fmt_num(rec.get("ma50"))
        m200 = _fmt_num(rec.get("ma200"))

        print("  " + "{:<8}  {:<14}  {}  {}  {}  {}".format(t, rec["action_state"], c_s, m20, m50, m200))
        print("  " + "{:<8}  {}".format("", rec["reason"]))

    buckets = {
        "deployable": [r["ticker"] for r in rows if r["action_state"] == "DEPLOYABLE NOW"],
        "promotion_review": [r["ticker"] for r in rows if r["action_state"] == "PROMOTION REVIEW"],
        "entry_policy_review": [r["ticker"] for r in rows if r["action_state"] == "ENTRY POLICY REVIEW"],
        "almost": [r["ticker"] for r in rows if r["action_state"] == "ALMOST DEPLOYABLE"],
        "blocked": [r["ticker"] for r in rows if r["action_state"] == "BLOCKED"],
        "below_stop": [r["ticker"] for r in rows if r["action_state"] == "BELOW STOP"],
        "bench": [r["ticker"] for r in rows if r["action_state"] == "BENCH"],
        "watch": [r["ticker"] for r in rows if r["action_state"] == "WATCH / RESEARCH NEEDED"],
        "error": [r["ticker"] for r in rows if r["action_state"] == "ERROR"],
    }

    print("\n  BOTTOM LINE")
    print("  " + "-" * 50)
    print("  " + "{:<24} {}".format("Act now (in band):", build_summary(buckets["deployable"])))
    print("  " + "{:<24} {}".format("Promotion review:", build_summary(buckets["promotion_review"])))
    print("  " + "{:<24} {}".format("Entry-policy review:", build_summary(buckets["entry_policy_review"])))
    print("  " + "{:<24} {}".format("Almost (pullback only):", build_summary(buckets["almost"])))
    print("  " + "{:<24} {}".format("Earnings blocked:", build_summary(buckets["blocked"])))
    print("  " + "{:<24} {}".format("Below stop:", build_summary(buckets["below_stop"])))
    print("  " + "{:<24} {}".format("Bench (chart weak):", build_summary(buckets["bench"])))
    print("  " + "{:<24} {}".format("Research needed:", build_summary(buckets["watch"])))

    warnings: list[str] = []
    if tech_stale:
        warnings.append("technical-refresh.json is stale")
    if state_stale:
        warnings.append("market-state.json is stale")
    if state_warning:
        warnings.append(state_warning)
    if tech_raw.get("warnings"):
        warnings.extend(tech_raw.get("warnings", []))
    if state and state.get("warnings"):
        warnings.extend(state.get("warnings", []))

    if warnings:
        print("")
        for warning in warnings:
            print("  *** WARNING: " + warning)

    status = "ok" if not buckets["error"] else ("partial" if len(buckets["error"]) < len(rows) else "error")
    if tech_stale or state_stale:
        status = "partial" if status == "ok" else status

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stale_after_hours": STALE_HOURS,
        "expected_update_window": "Run after technical and market refresh, before trigger-sheet generation, dashboard generation, or any decision-grade execution review.",
        "last_trading_day": tech_raw.get("last_trading_day"),
        "source_last_trading_day": {
            "technical": tech_raw.get("last_trading_day"),
            "market_state": state.get("last_trading_day") if state else None,
        },
        "freshness": {
            "technical_file": {
                "path": str(TECH_PATH),
                "generated_at_utc": tech_raw.get("generated_at_utc"),
                "age_hours": tech_age,
                "stale_after_hours": tech_stale_after,
                "is_stale": tech_stale,
                "last_trading_day": tech_raw.get("last_trading_day"),
                "expected_update_window": tech_raw.get("expected_update_window"),
            },
            "market_state_file": {
                "path": str(STATE_PATH),
                "generated_at_utc": state.get("generated_at_utc") if state else None,
                "age_hours": state_age,
                "stale_after_hours": state_stale_after,
                "is_stale": state_stale,
                "last_trading_day": state.get("last_trading_day") if state else None,
                "expected_update_window": state.get("expected_update_window") if state else None,
            },
        },
        "warnings": warnings,
        "summary": buckets,
        "records": rows,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(sep)
    print("")
    print(f"Output written to {OUT_PATH}")
    print("")


if __name__ == "__main__":
    main()
