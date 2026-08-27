"""trigger_sheet_refresh.py

Reads tmp/technical-refresh.json, tmp/deployment-check.json, tmp/market-state.json,
tmp/earnings-calendar.json, and tmp/portfolio-config.json to generate a
machine-readable deployment trigger sheet. Read-only.

Outputs:
    tmp/trigger-sheet.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from universe import is_entitled

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
TECH_PATH = TMP / "technical-refresh.json"
DEPLOY_PATH = TMP / "deployment-check.json"
STATE_PATH = TMP / "market-state.json"
EARNINGS_PATH = TMP / "earnings-calendar.json"
CONFIG_PATH = TMP / "portfolio-config.json"
OUT_PATH = TMP / "trigger-sheet.json"
STALE_HOURS = 24
SCHEMA_VERSION = 1
EXPECTED_UPDATE_WINDOW = (
    "Run after deployment check, earnings enrichment, and market-state refresh "
    "before dashboard generation or note-layer deployment review."
)

DEPLOY_STATE_MAP = {
    # Canonical forms (deployment_check.py emits these since WF32B)
    "DEPLOYABLE NOW": "DEPLOYABLE NOW",
    "PROMOTION REVIEW": "PROMOTION REVIEW",
    "ENTRY POLICY REVIEW": "ENTRY POLICY REVIEW",
    "ALMOST DEPLOYABLE": "ALMOST DEPLOYABLE",
    "BLOCKED": "BLOCKED",
    "BELOW STOP": "DO NOT TOUCH",
    "BENCH": "BENCH",
    "WATCH / RESEARCH NEEDED": "WATCH / RESEARCH NEEDED",
    "ERROR": "ERROR",
    # Legacy aliases for backward compatibility with older cached artifacts
    "DEPLOYABLE": "DEPLOYABLE NOW",
    "ALMOST": "ALMOST DEPLOYABLE",
    "WATCH": "WATCH / RESEARCH NEEDED",
}

ACTION_STATE_RANK = {
    "DEPLOYABLE NOW": 0,
    "PROMOTION REVIEW": 1,
    "ENTRY POLICY REVIEW": 2,
    "ALMOST DEPLOYABLE": 3,
    "BLOCKED": 4,
    "BENCH": 5,
    "DO NOT TOUCH": 6,
    "WATCH / RESEARCH NEEDED": 7,
    "ERROR": 8,
}


def load_json(path: Path, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            print(f"ERROR: required file not found: {path}")
            sys.exit(1)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


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


def map_action_state(deploy_state: str, ticker: str, rec: dict[str, Any], meta: dict[str, Any]) -> str:
    mapped = DEPLOY_STATE_MAP.get(deploy_state, "WATCH / RESEARCH NEEDED")
    workflow_state = (meta.get("workflow_state") or "").upper()

    # A hard stop breach is an override, not an ordinary watch-state nuance.
    # Owner approval, watch-lane status, or workflow labels must not soften it
    # into "almost deployable" / "watch" on generated trigger surfaces.
    if rec.get("below_stop") or (deploy_state or "").upper() == "BELOW STOP":
        return "DO NOT TOUCH"

    # Workflow-state gates take precedence over raw machine deployment state.
    # This prevents false promotions where price touches an entry band before the
    # setup is actually decision-grade in the canonical workflow layer.
    if meta.get("repair_mode") or workflow_state == "REPAIR":
        return "DO NOT TOUCH"
    if (deploy_state or "").upper() == "ENTRY POLICY REVIEW":
        return "ENTRY POLICY REVIEW"
    if workflow_state == "WATCH" or meta.get("entry_policy") == "underdefined":
        return "WATCH / RESEARCH NEEDED"
    if workflow_state == "BLOCKED":
        return "BLOCKED"

    return mapped


def build_macro_snapshot(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state or state.get("status") not in ("ok", "partial"):
        return {"status": "unavailable", "summary": "Market-state input unavailable"}
    data = state.get("data", {})
    eq = data.get("equities", {})
    vol = data.get("volatility", {})
    tr = data.get("treasuries", {})
    en = data.get("energy", {})
    return {
        "status": state.get("status"),
        "spx": eq.get("spx"),
        "vix": vol.get("vix"),
        "treasury_10y": tr.get("10y"),
        "brent": en.get("brent"),
        "wti": en.get("wti"),
        "summary": f"S&P 500 {eq.get('spx')}, VIX {vol.get('vix')}, 10Y {tr.get('10y')}, Brent {en.get('brent')}",
    }


def build_earnings_map(earnings: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not earnings:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for rec in earnings.get("records", []) or []:
        ticker = rec.get("ticker")
        if ticker:
            out[ticker] = rec
    return out


def build_alert_map(earnings: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not earnings:
        return out
    for alert in earnings.get("watchlist_alerts", []) or []:
        if isinstance(alert, str) and ":" in alert:
            ticker = alert.split(":", 1)[0].strip()
            if ticker:
                out[ticker] = alert
    return out


def days_until(date_str: str | None, *, today: datetime | None = None) -> int | None:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    base = (today or datetime.now(timezone.utc)).date()
    return (dt.date() - base).days


def parse_iso_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def post_earnings_review_confirmed(last_earnings_date: str | None, review_date: str | None) -> bool:
    last_dt = parse_iso_date(last_earnings_date)
    review_dt = parse_iso_date(review_date)
    if not last_dt or not review_dt:
        return False
    # Same-day post-print reviews are valid after the official release is captured.
    # This confirms catalyst review state only; it does not grant execution authority.
    return review_dt.date() >= last_dt.date()


def derive_catalyst_blocker(*, ticker: str, earnings_blocked: bool, next_earnings_date: str | None,
                            days_to_earnings: int | None, watchlist_alert: str | None) -> tuple[str, str]:
    """Derive catalyst_blocker text mechanically. Returns (text, source)."""
    parts: list[str] = []
    if earnings_blocked and next_earnings_date:
        if days_to_earnings is not None and days_to_earnings >= 0:
            parts.append(f"Earnings block active until {next_earnings_date} ({days_to_earnings}d)")
        else:
            parts.append(f"Earnings block active until {next_earnings_date}")
    elif earnings_blocked:
        parts.append("Earnings block active (date unconfirmed)")
    elif next_earnings_date and days_to_earnings is not None:
        if days_to_earnings < 0:
            parts.append(f"Last earnings reported {next_earnings_date} ({abs(days_to_earnings)}d ago); next print not yet on calendar")
        elif days_to_earnings <= 14:
            parts.append(f"Next earnings {next_earnings_date} in {days_to_earnings}d -- treat as timing-sensitive")
        else:
            parts.append(f"Next earnings {next_earnings_date} ({days_to_earnings}d out)")
    elif next_earnings_date:
        parts.append(f"Next earnings date: {next_earnings_date}")
    else:
        parts.append("No immediate hard catalyst block from cached earnings data")

    source = "derived"
    if watchlist_alert:
        if "DATE CHANGED" in watchlist_alert:
            parts.append("earnings date changed in latest provider feed; verify against IR before relying on timing")
            source = "alert_modified"
        elif "NEW" in watchlist_alert:
            parts.append("this name is newly added to the calendar; confirm against vault watchlist")
            source = "alert_modified"
    return "; ".join(parts), source


_MONTH_TO_NUM = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


def override_looks_stale(override_text: str, *, next_earnings_date: str | None,
                         today: datetime | None = None) -> bool:
    """Heuristic: an override mentioning specific dates that have all elapsed,
    or that disagree with the current next-earnings date, is stale prose.
    """
    if not override_text:
        return False
    base_date = (today or datetime.now(timezone.utc)).date()
    iso_dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", override_text)
    iso_in_future = []
    for raw in iso_dates:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        iso_in_future.append(dt >= base_date)
    if iso_dates and not any(iso_in_future):
        return True
    month_re = r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})\b"
    month_hits = re.findall(month_re, override_text)
    if month_hits and next_earnings_date:
        try:
            ned = datetime.strptime(next_earnings_date, "%Y-%m-%d").date()
        except ValueError:
            return False
        any_close = False
        for month_abbr, day_str in month_hits:
            try:
                month = _MONTH_TO_NUM[month_abbr[:3]]
                day = int(day_str)
                for year in (ned.year, ned.year - 1, ned.year + 1):
                    try:
                        candidate = datetime(year, month, day).date()
                    except ValueError:
                        continue
                    if abs((candidate - ned).days) <= 14:
                        any_close = True
                        break
                if any_close:
                    break
            except (KeyError, ValueError):
                continue
        if not any_close:
            return True
    return False


def _fmt_price(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "—"


def _trigger_range_is_current(trigger_text: str | None, band: dict[str, Any]) -> bool:
    """Return True when trigger prose appears aligned with the current band.

    Trigger prose is owner-readable text, but stale hard-coded ranges create a
    dangerous dashboard contradiction: the card's ENTRY BAND can be current
    while the TRIGGER box still points to an older band. If the prose contains
    numeric ranges and they do not include the current band endpoints, replace
    it with generated current-band guidance.
    """
    if not trigger_text:
        return False
    low = band.get("low")
    high = band.get("high")
    if low is None or high is None:
        return True
    nums: list[float] = []
    for raw in re.findall(r"\b\d+(?:\.\d+)?\b", trigger_text):
        try:
            nums.append(float(raw))
        except ValueError:
            continue
    # No numeric range in the prose: there is no band contradiction to detect.
    if len(nums) < 2:
        return True

    def has_value(target: Any) -> bool:
        try:
            value = float(target)
        except (TypeError, ValueError):
            return False
        return any(abs(value - num) <= 0.05 for num in nums)

    return has_value(low) and has_value(high)


def build_technical_trigger(meta: dict[str, Any], deploy_rec: dict[str, Any], band: dict[str, Any], action_state: str) -> tuple[str, str]:
    original = str(meta.get("trigger_condition") or deploy_rec.get("reason") or "").strip()
    if _trigger_range_is_current(original, band):
        return original, "owner_config"

    low = _fmt_price(band.get("low"))
    high = _fmt_price(band.get("high"))
    stop = _fmt_price(band.get("stop"))
    state = (action_state or "").upper()

    if state == "DEPLOYABLE NOW":
        text = (
            f"Current gated execution band is {low} to {high}; manual execution only; "
            f"do not chase above {high}; explicit stop {stop}."
        )
    elif state == "PROMOTION REVIEW":
        text = (
            f"Promotion review only inside/reclaiming the current gated execution band {low} to {high}; "
            f"owner approval is required before deployable-now status; explicit stop {stop}."
        )
    elif "ALMOST" in state:
        text = (
            f"Almost-deployable review around current gated execution band {low} to {high}; "
            f"no deployable-now status without explicit owner promotion; explicit stop {stop}."
        )
    elif state in {"DO NOT TOUCH", "BENCH", "BLOCKED"}:
        text = (
            f"No deployment from current gated execution band {low} to {high}; "
            f"repair/review required before re-engagement; explicit stop {stop}."
        )
    else:
        text = (
            f"Current gated execution band is {low} to {high}; reference only until the workflow state grants "
            f"execution-board entitlement; explicit stop {stop}."
        )
    return text, "generated_current_band_due_to_stale_config_range"


def main() -> None:
    tech = load_json(TECH_PATH, required=True)
    deploy = load_json(DEPLOY_PATH, required=True)
    state = load_json(STATE_PATH, required=False)
    earnings = load_json(EARNINGS_PATH, required=False)
    config = load_json(CONFIG_PATH, required=True)

    tech_records = {rec["ticker"]: rec for rec in (tech.get("records") or [])}
    deploy_records = deploy.get("records") or []
    earnings_map = build_earnings_map(earnings)
    alert_map = build_alert_map(earnings)
    tracked_universe = config.get("tracked_universe") or {}
    entry_bands = config.get("entry_bands") or {}

    trigger_records: list[dict[str, Any]] = []
    warnings: list[str] = []

    tech_age = age_hours(tech.get("generated_at_utc"))
    deploy_age = age_hours(deploy.get("generated_at_utc"))
    state_age = age_hours(state.get("generated_at_utc")) if state else None
    earnings_age = age_hours(earnings.get("generated_at_utc")) if earnings else None

    if tech_age is not None and tech_age > tech.get("stale_after_hours", STALE_HOURS):
        warnings.append("technical-refresh.json is stale")
    if deploy_age is not None and deploy_age > deploy.get("stale_after_hours", STALE_HOURS):
        warnings.append("deployment-check.json is stale")
    if state and state_age is not None and state_age > state.get("stale_after_hours", STALE_HOURS):
        warnings.append("market-state.json is stale")
    if earnings and earnings_age is not None and earnings_age > earnings.get("stale_after_days", 7) * 24:
        warnings.append("earnings-calendar.json is stale")

    deploy_meta = (deploy.get("freshness") or {}).get("technical_file", {})
    deploy_tech_ts = deploy_meta.get("generated_at_utc")
    current_tech_ts = tech.get("generated_at_utc")
    if deploy_tech_ts and current_tech_ts and deploy_tech_ts != current_tech_ts:
        warnings.append("deployment-check.json was built from different technical-refresh.json output; rerun deployment_check.py")
    deploy_state_meta = (deploy.get("freshness") or {}).get("market_state_file", {})
    deploy_state_ts = deploy_state_meta.get("generated_at_utc")
    current_state_ts = state.get("generated_at_utc") if state else None
    if deploy_state_ts and current_state_ts and deploy_state_ts != current_state_ts:
        warnings.append("deployment-check.json was built from different market-state.json output; rerun deployment_check.py")
    if tech.get("warnings"):
        warnings.extend(tech.get("warnings", []))
    if deploy.get("warnings"):
        warnings.extend(deploy.get("warnings", []))
    if state and state.get("warnings"):
        warnings.extend(state.get("warnings", []))
    if earnings and earnings.get("warnings"):
        warnings.extend(earnings.get("warnings", []))
    warnings = list(dict.fromkeys(warnings))

    for deploy_rec in deploy_records:
        ticker = deploy_rec.get("ticker")
        if not ticker:
            continue
        meta = tracked_universe.get(ticker, {})
        # Lane-based entitlement (Phase 1). Only execution-lane names belong on
        # the trigger sheet. Resolver consults coverage_lane and falls back to
        # the legacy include_in_trigger_sheet boolean if the lane field is
        # absent — sub-pass 1 stamped the field on every entry, so the legacy
        # path is now compatibility data, not active logic.
        if not is_entitled(ticker, meta, "trigger_sheet"):
            continue

        tech_rec = tech_records.get(ticker, {})
        earnings_rec = earnings_map.get(ticker, {})
        band = entry_bands.get(ticker, {})
        action_state = map_action_state(deploy_rec.get("action_state", "WATCH"), ticker, tech_rec, meta)

        next_date = earnings_rec.get("earnings_date") or earnings_rec.get("next_earnings_date")
        earnings_lifecycle = earnings_rec.get("lifecycle") if isinstance(earnings_rec.get("lifecycle"), dict) else {}
        days_to_earn = days_until(next_date)
        watchlist_alert = alert_map.get(ticker)
        derived_blocker, derived_source = derive_catalyst_blocker(
            ticker=ticker,
            earnings_blocked=bool(deploy_rec.get("earnings_blocked")),
            next_earnings_date=next_date,
            days_to_earnings=days_to_earn,
            watchlist_alert=watchlist_alert,
        )

        override_text = meta.get("catalyst_blocker_override")
        if override_text and not override_looks_stale(override_text, next_earnings_date=next_date):
            catalyst_blocker = override_text
            catalyst_blocker_source = "override"
            if watchlist_alert and ("DATE CHANGED" in watchlist_alert or "NEW" in watchlist_alert):
                catalyst_blocker = f"{override_text}; {watchlist_alert}"
                catalyst_blocker_source = "override_with_alert"
        else:
            catalyst_blocker = derived_blocker
            catalyst_blocker_source = derived_source
            if override_text:
                warnings.append(
                    f"{ticker} catalyst_blocker_override appears stale relative to next_earnings_date {next_date}; "
                    f"derived text is being used. Override: {override_text!r}"
                )
        if earnings_lifecycle.get("status") == "post_event_review_confirmed_next_date_pending" and (
            not catalyst_blocker or catalyst_blocker == "No immediate hard catalyst block from cached earnings data"
        ):
            closed_date = earnings_lifecycle.get("closed_watchlist_date")
            catalyst_blocker = f"Last earnings reported {closed_date}; post-earnings review confirmed; next print not yet on calendar"
            catalyst_blocker_source = "post_earnings_lifecycle"

        why = deploy_rec.get("reason") or "No reason available"
        workflow_state = (meta.get("workflow_state") or "").upper()
        entry_policy = (meta.get("entry_policy") or "").lower()
        coverage_lane = (meta.get("coverage_lane") or "").lower()
        last_earnings_date = meta.get("last_earnings_date")
        post_earnings_review_date = meta.get("post_earnings_review_date")
        earnings_date_ir_confirmed = meta.get("earnings_date_ir_confirmed")
        earnings_date_ir_confirmed_date = meta.get("earnings_date_ir_confirmed_date")
        if current_tech_ts and deploy_tech_ts and current_tech_ts != deploy_tech_ts:
            why = "Deployment reasoning is stale relative to current technical refresh; rerun deployment_check.py before trusting this state"
        if tech_rec.get("below_stop") or deploy_rec.get("below_stop") or deploy_rec.get("action_state") == "BELOW STOP":
            stop = band.get("stop")
            close = tech_rec.get("close") if tech_rec.get("close") is not None else deploy_rec.get("close")
            if stop is not None and close is not None:
                why = f"close {round(float(close), 2)} is below stop {round(float(stop), 2)} -- do not deploy"
            else:
                why = "below explicit stop -- do not deploy"
        elif meta.get("repair_mode"):
            why = "Repair mode remains active until chart structure and support rebuild make the setup decision-grade again"
        elif workflow_state == "WATCH":
            if deploy_rec.get("action_state") == "ENTRY POLICY REVIEW":
                why = deploy_rec.get("reason") or "Existing band/technical surfaces show a setup, but main-session entry-policy review is required before recommendation"
            elif tech_rec.get("in_entry_band") is None and entry_policy == "underdefined":
                if coverage_lane and coverage_lane != "execution":
                    why = f"{coverage_lane}-lane only -- explicit entry and stop are not defined yet"
                else:
                    why = "setup is not yet decision-grade -- requires explicit entry and stop definition"
            elif coverage_lane and coverage_lane != "execution":
                if tech_rec.get("in_entry_band"):
                    why = f"in band, but {coverage_lane}-lane only -- no execution-board entitlement"
                else:
                    why = f"{coverage_lane}-lane only -- not in execution-board scope yet"
            elif tech_rec.get("in_entry_band"):
                why = "in band, but this execution setup remains watch-only until it is intentionally promoted"
            else:
                why = "levels are defined, but this execution setup remains watch-only until it is intentionally promoted"
        elif entry_policy == "underdefined":
            why = "Name is tracked, but not yet decision-grade because explicit entry and stop are still missing"
        elif ticker == "ETN" and "ALMOST" in (deploy_rec.get("action_state") or ""):
            why = "Best chart in the sheet, but current price is extended versus the preferred zone"

        technical_trigger, technical_trigger_source = build_technical_trigger(meta, deploy_rec, band, action_state)

        record = {
            "ticker": ticker,
            "coverage_tier": meta.get("coverage_tier"),
            "portfolio_role": meta.get("portfolio_role"),
            "thesis_status": meta.get("thesis_status", "review needed"),
            "macro_fit": meta.get("macro_fit", "review needed"),
            "technical_trigger": technical_trigger,
            "technical_trigger_source": technical_trigger_source,
            "entry_band": {"low": band.get("low"), "high": band.get("high"), "label": band.get("label")},
            "invalidation": band.get("stop"),
            "size_tier": meta.get("sizing_tier", "review needed"),
            "workflow_state": meta.get("workflow_state"),
            "action_state": action_state,
            "why": why,
            "catalyst_blocker": catalyst_blocker,
            "catalyst_blocker_source": catalyst_blocker_source,
            "days_to_earnings": days_to_earn,
            "close": tech_rec.get("close") if tech_rec.get("close") is not None else deploy_rec.get("close"),
            "ma_posture": tech_rec.get("ma_posture"),
            "in_entry_band": tech_rec.get("in_entry_band"),
            "below_stop": tech_rec.get("below_stop"),
            "earnings_blocked": deploy_rec.get("earnings_blocked", False),
            "data_date": tech_rec.get("data_date"),
            "deployment_state": deploy_rec.get("action_state"),
            "deployment_reason": deploy_rec.get("reason"),
            "next_earnings_date": next_date,
            "earnings_lifecycle": earnings_lifecycle,
            "last_earnings_date": last_earnings_date,
            "post_earnings_review_date": post_earnings_review_date,
            "post_earnings_review_confirmed": post_earnings_review_confirmed(last_earnings_date, post_earnings_review_date),
            "earnings_date_ir_confirmed": earnings_date_ir_confirmed,
            "earnings_date_ir_confirmed_date": earnings_date_ir_confirmed_date,
            "earnings_source_status": earnings_rec.get("source_status") or earnings_rec.get("status"),
        }
        trigger_records.append(record)

    trigger_records.sort(key=lambda r: (ACTION_STATE_RANK.get(r.get("action_state"), 9), r.get("ticker") or ""))

    summary: dict[str, list[str]] = {
        "deployable_now": [], "promotion_review": [], "almost_deployable": [], "blocked": [],
        "do_not_touch": [], "watch": [], "error": [],
    }
    bucket_for_state = {
        "DEPLOYABLE NOW": "deployable_now",
        "PROMOTION REVIEW": "promotion_review",
        "ALMOST DEPLOYABLE": "almost_deployable",
        "BLOCKED": "blocked",
        "DO NOT TOUCH": "do_not_touch",
        "WATCH / RESEARCH NEEDED": "watch",
        "ERROR": "error",
    }
    for rec in trigger_records:
        bucket = bucket_for_state.get(rec.get("action_state"))
        if bucket:
            summary[bucket].append(rec["ticker"])

    last_trading_day = (
        tech.get("last_trading_day")
        or deploy.get("last_trading_day")
        or (state.get("last_trading_day") if state else None)
        or (earnings.get("last_trading_day") if earnings else None)
    )

    output = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if not warnings else "ok_with_warnings",
        "stale_after_hours": STALE_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": last_trading_day,
        "source_last_trading_day": {
            "technical": tech.get("last_trading_day"),
            "deployment": deploy.get("last_trading_day"),
            "market_state": state.get("last_trading_day") if state else None,
            "earnings": earnings.get("last_trading_day") if earnings else None,
        },
        "freshness": {
            "technical_age_hours": tech_age,
            "deployment_age_hours": deploy_age,
            "market_state_age_hours": state_age,
            "earnings_age_hours": earnings_age,
        },
        "warnings": warnings,
        "summary": summary,
        "macro_snapshot": build_macro_snapshot(state),
        "records": trigger_records,
    }

    write_json(OUT_PATH, output)

    print("trigger_sheet_refresh.py")
    print(f"  Records:           {len(trigger_records)}")
    for bucket_label in ("deployable_now", "promotion_review", "almost_deployable", "blocked", "do_not_touch", "watch", "error"):
        names = summary.get(bucket_label, [])
        joined = " ".join(names) if names else "-"
        print(f"  {bucket_label:18s} {len(names):2d}  {joined}")
    if warnings:
        print("  Warnings:")
        for w in warnings:
            print(f"    - {w}")
    print(f"  Output written to {OUT_PATH}")


if __name__ == "__main__":
    main()
