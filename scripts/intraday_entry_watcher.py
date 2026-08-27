"""intraday_entry_watcher.py

Small read-only market-hours watcher for the deployment-build target queue.

Purpose:
- fetch current/near-current market prices for the approved review-only target queue
- compare prices with written entry bands and workflow gates
- write a machine-readable alert surface for Veritas/operator review

It does not place orders, infer owner approval, mutate portfolio notes, touch
brokerage/account state, or create WF67 execution artifacts.

Outputs:
  tmp/intraday-entry-watch.json
  optional Markdown digest when --write-md is supplied

Usage:
  python scripts\\intraday_entry_watcher.py [--write-md]
"""

from __future__ import annotations

from board_state_contract import legacy_state
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

from market_data_utils import atomic_write_json, atomic_write_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
TRIGGER_PATH = TMP / "trigger-sheet.json"
DEPLOYMENT_PATH = TMP / "deployment-check.json"
OUT_JSON = TMP / "intraday-entry-watch.json"
OUT_MD = TMP / "intraday-entry-watch.md"
STATE_PATH = TMP / "intraday-entry-watch-state.json"
SCHEMA_VERSION = 1

# Review-only queue established in 03. Portfolio/Deployment Build Executive Packet - 2026-05-17.md.
TARGET_QUEUE: list[dict[str, Any]] = [
    {"rank": 1, "ticker": "ETN", "role": "first-call deploy-review candidate", "mode": "deployable_or_review"},
    {"rank": 2, "ticker": "SGOV", "role": "reserve/cash-like sleeve", "mode": "reserve_validation"},
    {"rank": 2, "ticker": "SHY", "role": "short Treasury reserve sleeve", "mode": "reserve_validation"},
    {"rank": 3, "ticker": "VXUS", "role": "international diversification", "mode": "watch_for_band"},
    {"rank": 4, "ticker": "LIN", "role": "Materials quality candidate", "mode": "promotion_review"},
    {"rank": 5, "ticker": "CME", "role": "financial infrastructure candidate", "mode": "promotion_review"},
    {"rank": 6, "ticker": "PH", "role": "industrial compounder candidate", "mode": "promotion_review"},
    {"rank": 7, "ticker": "ITA", "role": "defense/aerospace ETF candidate before GE", "mode": "promotion_review"},
    {"rank": 8, "ticker": "WMB", "role": "energy infrastructure watch packet", "mode": "watch_for_band"},
    {"rank": 9, "ticker": "TMUS", "role": "communication services monitor", "mode": "repair_monitor"},
]

ORDER_ALERT_BLOCK = {"NVDA", "MSFT", "JPM", "BRK.B", "LMT", "RTX", "XOM", "HYG", "JNK"}
NEAR_BAND_PCT = 1.0


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def finite_float(value: Any) -> float | None:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val):
        return None
    return val


def latest_price(yf_symbol: str) -> tuple[float | None, str, str | None]:
    """Return latest available yfinance price with source label and warning."""
    try:
        ticker = yf.Ticker(yf_symbol)
        fast = getattr(ticker, "fast_info", None)
        if fast:
            for key in ("last_price", "regular_market_price", "previous_close"):
                try:
                    val = finite_float(fast.get(key)) if hasattr(fast, "get") else finite_float(getattr(fast, key, None))
                except Exception:
                    val = None
                if val is not None:
                    return round(val, 4), f"yfinance.fast_info.{key}", None
    except Exception as exc:
        fast_warning = f"fast_info unavailable: {exc}"
    else:
        fast_warning = "fast_info unavailable"

    try:
        hist = yf.Ticker(yf_symbol).history(period="1d", interval="1m")
        if hist is not None and not hist.empty and "Close" in hist:
            close = hist["Close"].dropna()
            if not close.empty:
                return round(float(close.iloc[-1]), 4), "yfinance.history.1m.close", None
    except Exception as exc:
        return None, "yfinance.unavailable", f"{fast_warning}; history unavailable: {exc}"

    return None, "yfinance.unavailable", fast_warning


def record_maps(trigger: dict[str, Any], deployment: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    trigger_records = {r.get("ticker"): r for r in trigger.get("records", []) if isinstance(r, dict) and r.get("ticker")}
    deploy_records = {r.get("ticker"): r for r in deployment.get("records", []) if isinstance(r, dict) and r.get("ticker")}
    return trigger_records, deploy_records


def band_from_sources(ticker: str, trig: dict[str, Any], dep: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    band = trig.get("entry_band") if isinstance(trig.get("entry_band"), dict) else None
    if not band:
        band = (config.get("entry_bands") or {}).get(ticker) if isinstance(config.get("entry_bands"), dict) else None
    if not isinstance(band, dict):
        return {"low": None, "high": None, "label": None, "source": "missing"}
    low = finite_float(band.get("low") or band.get("current_band_low"))
    high = finite_float(band.get("high") or band.get("current_band_high"))
    label = band.get("label") or (f"{low}-{high}" if low is not None and high is not None else None)
    return {"low": low, "high": high, "label": label, "source": "trigger/config"}


def classify_target(target: dict[str, Any], price: float | None, band: dict[str, Any], trig: dict[str, Any], dep: dict[str, Any]) -> dict[str, Any]:
    ticker = target["ticker"]
    mode = target["mode"]
    action_state = legacy_state(trig, "action_state") or legacy_state(dep, "action_state")
    deployment_state = trig.get("deployment_state") or legacy_state(dep, "action_state")
    below_stop = bool(trig.get("below_stop") or dep.get("below_stop"))
    earnings_blocked = bool(trig.get("earnings_blocked") or dep.get("earnings_blocked"))
    low = band.get("low")
    high = band.get("high")

    reasons: list[str] = []
    alert_level = "none"
    entry_state = "not_actionable"
    distance_to_band_pct: float | None = None
    in_band = False

    if mode in {"repair_monitor"}:
        return {
            "entry_state": "blocked_or_repair_monitor",
            "alert_level": "none",
            "distance_to_band_pct": None,
            "reasons": ["Target is in repair-monitor posture; no entry alert."],
        }
    order_alert_blocked = ticker in ORDER_ALERT_BLOCK

    if price is None:
        return {
            "entry_state": "price_unavailable",
            "alert_level": "warning",
            "distance_to_band_pct": None,
            "reasons": ["Live/near-live price unavailable; cannot evaluate entry."],
        }

    if below_stop:
        return {
            "entry_state": "below_stop_do_not_touch",
            "alert_level": "warning",
            "distance_to_band_pct": None,
            "reasons": ["Below-stop/do-not-touch state overrides entry interest."],
        }

    if earnings_blocked:
        return {
            "entry_state": "earnings_blocked",
            "alert_level": "warning",
            "distance_to_band_pct": None,
            "reasons": ["Earnings/catalyst blocker active; no entry alert."],
        }

    if low is None or high is None:
        if mode == "reserve_validation":
            return {
                "entry_state": "reserve_validation_required",
                "alert_level": "info",
                "distance_to_band_pct": None,
                "reasons": ["Reserve sleeve needs issuer/yield/duration/cash-policy validation; no price-band trigger defined."],
            }
        return {
            "entry_state": "missing_entry_band",
            "alert_level": "warning",
            "distance_to_band_pct": None,
            "reasons": ["No numeric entry band found; needs validator/source work before paper entry."],
        }

    if low <= price <= high:
        in_band = True
        distance_to_band_pct = 0.0
    elif price < low:
        distance_to_band_pct = round((low - price) / low * 100, 2)
    else:
        distance_to_band_pct = round((price - high) / high * 100, 2)

    if in_band and mode == "deployable_or_review" and action_state == "DEPLOYABLE NOW" and not order_alert_blocked:
        alert_level = "entry_candidate"
        entry_state = "deployable_in_band_review_required"
        reasons.append("Deployable-now target is inside written entry band; requires owner-approved paper order terms before any trade.")
    elif in_band and order_alert_blocked:
        alert_level = "review_candidate"
        entry_state = "order_alert_blocked_review_attention"
        reasons.append("Inside written band, but order/buy alert remains blocked; main-session review only.")
    elif in_band and action_state == "ENTRY POLICY REVIEW":
        alert_level = "review_candidate"
        entry_state = "entry_policy_review_in_band"
        reasons.append("Existing surfaces show an in-band setup, but entry policy is not decision-grade yet; review only.")
    elif in_band and mode == "promotion_review":
        alert_level = "review_candidate"
        entry_state = "promotion_review_in_band"
        reasons.append("Promotion-review target is inside written band; source/packet validation and owner review still required.")
    elif in_band:
        alert_level = "review_candidate"
        entry_state = "watch_target_in_band"
        reasons.append("Watch target is inside written band but lacks deployable authority; review only.")
    elif distance_to_band_pct is not None and distance_to_band_pct <= NEAR_BAND_PCT:
        alert_level = "near_band"
        entry_state = "near_entry_band"
        side = "below lower band" if price < low else "above upper/no-chase band"
        reasons.append(f"Within {NEAR_BAND_PCT}% of entry band ({side}); monitor closely, no auto-buy.")
    else:
        entry_state = "outside_entry_band"
        reasons.append("Outside written entry band; no-chase discipline remains active.")

    return {
        "entry_state": entry_state,
        "alert_level": alert_level,
        "distance_to_band_pct": distance_to_band_pct,
        "reasons": reasons,
        "action_state": action_state,
        "deployment_state": deployment_state,
    }


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Intraday Entry Watch",
        "",
        f"Generated: `{result['generated_at_utc']}`",
        f"Status: **{result['status']}**",
        "",
        "## Summary",
        "",
        f"- Entry candidates: `{result['summary']['entry_candidate_count']}`",
        f"- Review candidates: `{result['summary']['review_candidate_count']}`",
        f"- Near band: `{result['summary']['near_band_count']}`",
        f"- Warnings: `{result['summary']['warning_count']}`",
        f"- Notification required: `{str(result['notification']['required']).lower()}`",
        "",
        "## Authority boundary",
        "",
        "Read-only alerting only. No live trade, no paper order, no brokerage/account action, no money movement, no owner-approval inference, and no canonical portfolio apply.",
        "",
        "## Watched targets",
        "",
        "| Rank | Ticker | Price | Band | State | Alert | Notes |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for rec in result["targets"]:
        price = "--" if rec.get("price") is None else f"{rec['price']:.2f}"
        band = rec.get("entry_band", {})
        band_label = band.get("label") or "--"
        notes = "; ".join(rec.get("reasons") or [])
        lines.append(
            f"| {rec.get('rank')} | {rec.get('ticker')} | {price} | {band_label} | {rec.get('entry_state')} | {rec.get('alert_level')} | {notes} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest.")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH)
    trigger = load_json(TRIGGER_PATH)
    deployment = load_json(DEPLOYMENT_PATH)
    trigger_records, deploy_records = record_maps(trigger, deployment)
    tracked = config.get("tracked_universe") if isinstance(config.get("tracked_universe"), dict) else {}

    targets: list[dict[str, Any]] = []
    warnings: list[str] = []
    for target in TARGET_QUEUE:
        ticker = target["ticker"]
        meta = tracked.get(ticker, {}) if isinstance(tracked, dict) else {}
        yf_symbol = meta.get("yfinance") if isinstance(meta, dict) else None
        if not yf_symbol:
            yf_symbol = ticker.replace(".", "-")
        price, price_source, price_warning = latest_price(yf_symbol)
        trig = trigger_records.get(ticker, {})
        dep = deploy_records.get(ticker, {})
        band = band_from_sources(ticker, trig, dep, config)
        cls = classify_target(target, price, band, trig, dep)
        if price_warning:
            warnings.append(f"{ticker}: {price_warning}")
        rec = {
            **target,
            "yfinance_symbol": yf_symbol,
            "price": price,
            "price_source": price_source,
            "entry_band": band,
            "technical_context": {
                "action_state": legacy_state(trig, "action_state") or legacy_state(dep, "action_state"),
                "deployment_state": trig.get("deployment_state") or legacy_state(dep, "action_state"),
                "below_stop": bool(trig.get("below_stop") or dep.get("below_stop")),
                "earnings_blocked": bool(trig.get("earnings_blocked") or dep.get("earnings_blocked")),
                "data_date": trig.get("data_date") or dep.get("data_date"),
            },
            **cls,
        }
        targets.append(rec)

    entry_candidates = [r for r in targets if r.get("alert_level") == "entry_candidate"]
    review_candidates = [r for r in targets if r.get("alert_level") == "review_candidate"]
    near_band = [r for r in targets if r.get("alert_level") == "near_band"]
    warning_targets = [r for r in targets if r.get("alert_level") == "warning"]

    status = "alert" if entry_candidates or review_candidates or near_band else "ok"
    if warning_targets and not (entry_candidates or review_candidates or near_band):
        status = "warning"

    alert_signature = [
        {
            "ticker": r.get("ticker"),
            "alert_level": r.get("alert_level"),
            "entry_state": r.get("entry_state"),
            "price": r.get("price"),
        }
        for r in targets
        if r.get("alert_level") in {"entry_candidate", "review_candidate", "near_band", "warning"}
    ]
    # Dedupe on alert identity, not tick-by-tick price, to avoid noisy repeated
    # intraday notifications while the same target remains in the same state.
    alert_identity = [
        {"ticker": r["ticker"], "alert_level": r["alert_level"], "entry_state": r["entry_state"]}
        for r in alert_signature
    ]
    previous_state = load_json(STATE_PATH)
    previous_identity = previous_state.get("last_alert_identity") if isinstance(previous_state, dict) else None
    notification_required = alert_identity != previous_identity
    notification_reason = "alert_state_changed" if notification_required else "unchanged_alert_state"

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "workflow": "Intraday Entry Watch - read-only",
        "authority": {
            "read_only": True,
            "paper_order_allowed": False,
            "live_trading_allowed": False,
            "brokerage_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
            "canonical_portfolio_apply_allowed": False,
        },
        "summary": {
            "target_count": len(targets),
            "entry_candidate_count": len(entry_candidates),
            "review_candidate_count": len(review_candidates),
            "near_band_count": len(near_band),
            "warning_count": len(warning_targets) + len(warnings),
            "entry_candidates": [r["ticker"] for r in entry_candidates],
            "review_candidates": [r["ticker"] for r in review_candidates],
            "near_band": [r["ticker"] for r in near_band],
        },
        "notification": {
            "required": notification_required,
            "reason": notification_reason,
            "alert_identity": alert_identity,
            "alert_signature": alert_signature,
        },
        "targets": targets,
        "warnings": warnings,
        "source_artifacts": [str(CONFIG_PATH.relative_to(WORKSPACE)), str(TRIGGER_PATH.relative_to(WORKSPACE)), str(DEPLOYMENT_PATH.relative_to(WORKSPACE))],
        "stop_lines": [
            "No paper order without exact owner confirmation of ticker/side/qty/limit/TIF and WF67 guard validation.",
            "No live trading, live endpoint, account mutation, money movement, or inferred owner approval.",
            "No chase above written band.",
        ],
    }
    atomic_write_json(OUT_JSON, result)
    if args.write_md:
        atomic_write_text(OUT_MD, build_markdown(result))
    atomic_write_json(STATE_PATH, {
        "schema_version": 1,
        "updated_at_utc": result["generated_at_utc"],
        "last_status": status,
        "last_alert_identity": alert_identity,
    })

    print(json.dumps({
        "status": result["status"],
        "summary": result["summary"],
        "output": str(OUT_JSON.relative_to(WORKSPACE)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
