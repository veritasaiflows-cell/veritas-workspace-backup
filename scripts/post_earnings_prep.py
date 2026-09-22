"""post_earnings_prep.py

Read-only prep script for post-earnings interpretation workflows.

This script does not fetch live news or make final judgments. Instead, it reads
cached artifacts from tmp/ and prepares a structured packet for each tracked name
that is near, at, or just past an earnings window. The packet is designed for an
agent to fill the interpretation layer with three elements:
- what happened
- what it means
- what we do now

Usage:
    python scripts/post_earnings_prep.py

Inputs:
    tmp/technical-refresh.json
    tmp/deployment-check.json
    tmp/trigger-sheet.json
    tmp/earnings-calendar.json
    tmp/market-state.json (optional)

Outputs:
    tmp/post-earnings-prep.json
    terminal summary
"""

from __future__ import annotations

from board_state_contract import legacy_state
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
TECH_PATH = TMP / "technical-refresh.json"
DEPLOY_PATH = TMP / "deployment-check.json"
TRIGGER_PATH = TMP / "trigger-sheet.json"
EARNINGS_PATH = TMP / "earnings-calendar.json"
STATE_PATH = TMP / "market-state.json"
OFFICIAL_BRIDGE_PATH = TMP / "official-earnings-bridge.json"
ALERT_CONTROLLER_PATH = TMP / "alert-level-freshness-controller.json"
OUT_PATH = TMP / "post-earnings-prep.json"
STALE_HOURS = 24
# Trading-day back-window. 7 trading days ≈ 9-11 calendar days, which keeps the
# read-through window open for at least one full week of post-print interpretation
# without dragging stale prints into the panel.
WINDOW_BACK_TRADING_DAYS = 7
WINDOW_BACK_DAYS = 11  # calendar-day cap that maps to ~7 trading days
WINDOW_FORWARD_DAYS = 14

INTERPRETATION_CONFIG: dict[str, dict[str, Any]] = {
    "LMT": {
        "priority": "critical",
        "watch_items": [
            "backlog durability",
            "missile and munitions demand commentary",
            "F-35 delivery and program execution updates",
            "guidance raise, hold, or cut",
            "margin resilience",
        ],
        "sector_read_through": "Use RTX and NOC as defense read-through context before judging LMT in isolation.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
            "03. Portfolio/Portfolio Snapshot.md",
        ],
    },
    "RTX": {
        "priority": "high",
        "watch_items": [
            "defense demand tone",
            "aftermarket demand strength",
            "guidance change",
        ],
        "sector_read_through": "Defense read-through input for LMT.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
        ],
    },
    "NOC": {
        "priority": "high",
        "watch_items": [
            "defense demand tone",
            "program execution",
            "guidance quality",
        ],
        "sector_read_through": "Defense read-through input for LMT.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
        ],
    },
    "VRT": {
        "priority": "high",
        "watch_items": [
            "AI power and thermal demand",
            "guidance change",
            "margin quality",
            "whether leadership is becoming too crowded to chase",
        ],
        "sector_read_through": "Read-through for ETN and the broader AI power-enabler sleeve.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "04. Research/Coverage and Watchlist.md",
            "03. Portfolio/Execution Board.md",
        ],
    },
    "LRCX": {
        "priority": "monitor",
        "watch_items": [
            "AI-driven semiconductor capex tone",
            "revenue and EPS direction",
            "June-quarter guidance",
        ],
        "sector_read_through": "Read-through for NVDA, ETN, and AI infrastructure demand.",
        "note_targets": [
            "05. Intelligence/Weekly Intelligence Brief.md",
            "04. Research/Coverage and Watchlist.md",
        ],
    },
    "MSFT": {
        "priority": "critical",
        "watch_items": [
            "Azure growth",
            "Copilot monetization",
            "cloud margins",
            "capital expenditure tone",
        ],
        "sector_read_through": "Core portfolio earnings. Also matters for AI-platform and cloud tone.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
            "03. Portfolio/Portfolio Snapshot.md",
        ],
    },
    "GOOG": {
        "priority": "critical",
        "watch_items": [
            "Search resilience vs AI disruption narrative",
            "Google Cloud growth",
            "advertising demand",
            "margin and capex tone",
        ],
        "sector_read_through": "Core portfolio earnings. Also matters for mega-cap AI and ad-market tone.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
            "03. Portfolio/Portfolio Snapshot.md",
        ],
    },
    "AMZN": {
        "priority": "high",
        "watch_items": [
            "AWS growth",
            "operating leverage",
            "consumer demand tone",
        ],
        "sector_read_through": "Useful quality-growth and cloud read-through.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
        ],
    },
    "ETN": {
        "priority": "critical",
        "watch_items": [
            "grid and electrification demand",
            "AI power infrastructure commentary",
            "guidance quality",
            "timing/date-confirmation confidence",
        ],
        "sector_read_through": "Core read-through for the power-enabler sleeve.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
            "03. Portfolio/Portfolio Snapshot.md",
        ],
    },
    "XOM": {
        "priority": "critical",
        "watch_items": [
            "realized oil pricing",
            "production impact",
            "Q2 guidance",
            "tone after post-ceasefire oil weakness",
        ],
        "sector_read_through": "Must be read together with the latest EIA path and oil structure.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
            "03. Portfolio/Portfolio Snapshot.md",
            "04. Research/Coverage and Watchlist.md",
        ],
    },
    "NVDA": {
        "priority": "critical",
        "watch_items": [
            "Data Center revenue growth and backlog/demand durability",
            "Blackwell/Rubin platform demand and supply commentary",
            "gross margin resilience",
            "forward revenue guide and China/export-control assumptions",
            "AI infrastructure read-through for ETN, VRT, GE, MSFT, GOOG, AMD, and AI-power names",
            "whether post-print price action creates a revised band or remains no-chase",
        ],
        "sector_read_through": "Core AI infrastructure bellwether; read through to AI-power, hyperscaler capex, semiconductor, and data-center supply chain names without converting the print into automatic deployment authority.",
        "note_targets": [
            "05. Intelligence/Event Calendar.md",
            "05. Intelligence/Weekly Intelligence Brief.md",
            "03. Portfolio/Execution Board.md",
            "03. Portfolio/Portfolio Snapshot.md",
            "04. Research/Coverage and Watchlist.md",
        ],
    },
}

GENERIC_NOTE_TARGETS = [
    "05. Intelligence/Event Calendar.md",
    "05. Intelligence/Weekly Intelligence Brief.md",
    "03. Portfolio/Execution Board.md",
]

GENERIC_WATCH_ITEMS = [
    "revenue and EPS versus expectations",
    "guidance change and management tone",
    "margin quality and cash-flow implications",
    "price reaction versus written band/stop",
    "sector or portfolio read-through",
]


def generic_config_for(ticker: str) -> dict[str, Any]:
    return {
        "priority": "monitor",
        "watch_items": GENERIC_WATCH_ITEMS,
        "sector_read_through": f"Generic tracked-name earnings packet for {ticker}; agent must interpret source evidence before any conclusion.",
        "note_targets": GENERIC_NOTE_TARGETS,
        "generated_from_fallback": True,
    }


def load_json(path: Path, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            print(f"ERROR: required file not found: {path}")
            sys.exit(1)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except Exception:
        return None


def days_from_today(date_str: str | None) -> int | None:
    d = parse_iso_date(date_str)
    if d is None:
        return None
    return (d - date.today()).days


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


def build_macro_context(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state or state.get("status") not in ("ok", "partial"):
        return {
            "status": "unavailable",
            "summary": "Market-state input unavailable",
        }
    data = state.get("data", {})
    return {
        "status": state.get("status"),
        "spx": data.get("equities", {}).get("spx"),
        "vix": data.get("volatility", {}).get("vix"),
        "brent": data.get("energy", {}).get("brent"),
        "wti": data.get("energy", {}).get("wti"),
        "summary": (
            f"S&P 500 {data.get('equities', {}).get('spx')}, "
            f"VIX {data.get('volatility', {}).get('vix')}, "
            f"Brent {data.get('energy', {}).get('brent')}, "
            f"WTI {data.get('energy', {}).get('wti')}"
        ),
    }


def infer_stage(days_to_earnings: int | None) -> str:
    if days_to_earnings is None:
        return "unscheduled or unknown"
    if days_to_earnings < -2:
        return "recently reported"
    if days_to_earnings < 0:
        return "just reported"
    if days_to_earnings == 0:
        return "reports today"
    if days_to_earnings <= 2:
        return "imminent"
    return "upcoming"


def infer_phase(days_to_earnings: int | None) -> str:
    """Coarser bucket for UI sectioning: pre / today / post."""
    if days_to_earnings is None:
        return "unknown"
    if days_to_earnings < 0:
        return "post_earnings"
    if days_to_earnings == 0:
        return "reporting_today"
    return "pre_earnings"


def bridges_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in payload.get("bridges", []) or []
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }


def alerts_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or "").upper(): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and str(row.get("ticker") or "").strip()
    }


def reconciliation_requirements(
    *,
    phase: str,
    bridge: dict[str, Any],
    alert: dict[str, Any],
) -> dict[str, Any]:
    """Describe post-print review work without mutating notes or alert canon."""
    official = bridge.get("official_earnings_bridge") if isinstance(bridge.get("official_earnings_bridge"), dict) else {}
    post_earnings = phase == "post_earnings"
    return {
        "review_only": True,
        "scorecard_required": post_earnings,
        "thesis_reassessment_required": post_earnings,
        "catalyst_reconciliation_required": post_earnings,
        "alert_reconciliation_required": post_earnings,
        "official_evidence": {
            "source": "tmp/official-earnings-bridge.json",
            "available": bool(bridge),
            "status": bridge.get("status") if bridge else "unavailable",
            "evidence_status": official.get("official_evidence_status") if official else "unavailable",
            "period_end": bridge.get("period_end") if bridge else None,
        },
        "alert_context": {
            "source": "tmp/alert-level-freshness-controller.json",
            "available": bool(alert),
            "alert_state": alert.get("alert_state") if alert else "unavailable",
            "signal_state": alert.get("signal_state") if alert else "unavailable",
            "freshness_status": alert.get("freshness_status") if alert else "unavailable",
        },
        "automatic_note_or_alert_mutation_allowed": False,
    }


def main() -> None:
    tech = load_json(TECH_PATH, required=False) or {}
    # deployment-check is a retired compatibility surface. A missing copy may
    # not prevent the review-only earnings queue from being built.
    deploy = load_json(DEPLOY_PATH, required=False) or {}
    trigger = load_json(TRIGGER_PATH, required=False) or {}
    earnings = load_json(EARNINGS_PATH, required=True)
    state = load_json(STATE_PATH, required=False)
    official_bridge = load_json(OFFICIAL_BRIDGE_PATH, required=False) or {}
    alert_controller = load_json(ALERT_CONTROLLER_PATH, required=False) or {}

    tech_map = {rec["ticker"]: rec for rec in tech.get("records", []) or []}
    deploy_map = {rec["ticker"]: rec for rec in deploy.get("records", []) or []}
    trigger_map = {rec["ticker"]: rec for rec in trigger.get("records", []) or []}
    earnings_map = {rec["ticker"]: rec for rec in earnings.get("records", []) or []}
    bridge_map = bridges_by_ticker(official_bridge)
    alert_map = alerts_by_ticker(alert_controller)
    earnings_lifecycle = earnings.get("earnings_lifecycle") if isinstance(earnings.get("earnings_lifecycle"), dict) else {}
    lifecycle_closeouts = earnings_lifecycle.get("closeouts") if isinstance(earnings_lifecycle.get("closeouts"), list) else []

    packets: list[dict[str, Any]] = []

    candidate_tickers = set(INTERPRETATION_CONFIG)
    candidate_tickers.update(earnings_map)
    candidate_tickers.update(trigger_map)
    candidate_tickers.update(deploy_map)
    candidate_tickers.update(tech_map)

    fallback_tickers: list[str] = []

    for ticker in sorted(candidate_tickers):
        cfg = INTERPRETATION_CONFIG.get(ticker) or generic_config_for(ticker)
        if cfg.get("generated_from_fallback"):
            fallback_tickers.append(ticker)
        earnings_rec = earnings_map.get(ticker, {})
        next_earnings = earnings_rec.get("next_earnings_date")
        days_to = days_from_today(next_earnings)

        if days_to is None or not (-WINDOW_BACK_DAYS <= days_to <= WINDOW_FORWARD_DAYS):
            continue

        trigger_rec = trigger_map.get(ticker, {})
        tech_rec = tech_map.get(ticker, {})
        deploy_rec = deploy_map.get(ticker, {})
        phase = infer_phase(days_to)

        packet = {
            "ticker": ticker,
            "priority": cfg.get("priority", "monitor"),
            "stage": infer_stage(days_to),
            "phase": phase,
            "days_to_or_from_earnings": days_to,
            "next_earnings_date": next_earnings,
            "source_class": earnings_rec.get("date_source_class"),
            "primary_confirmed": earnings_rec.get("primary_confirmed"),
            "earnings_lifecycle": earnings_rec.get("lifecycle") or {},
            "fallback_config": bool(cfg.get("generated_from_fallback")),
            "watch_items": cfg.get("watch_items", []),
            "sector_read_through": cfg.get("sector_read_through"),
            "note_targets": [
                target
                for target in cfg.get("note_targets", [])
                if not str(target).startswith("03. Portfolio/")
            ],
            "technical_context": {
                "close": tech_rec.get("close"),
                "ma_posture": tech_rec.get("ma_posture"),
                "in_entry_band": tech_rec.get("in_entry_band"),
                "below_stop": tech_rec.get("below_stop"),
                "data_date": tech_rec.get("data_date"),
            },
            "deployment_context": {
                "action_state": legacy_state(deploy_rec, "action_state"),
                "reason": deploy_rec.get("reason"),
                "source": "tmp/deployment-check.json" if deploy else "unavailable_uses_trigger_context",
            },
            "trigger_context": {
                "action_state": legacy_state(trigger_rec, "action_state"),
                "technical_trigger": trigger_rec.get("technical_trigger"),
                "catalyst_blocker": trigger_rec.get("catalyst_blocker"),
                "why": trigger_rec.get("why"),
                "invalidation": trigger_rec.get("invalidation"),
                "size_tier": trigger_rec.get("size_tier"),
            },
            "interpretation_slots": {
                "what_happened": None,
                "what_it_means": None,
                "what_we_do_now": None,
                "evidence_status": "pending post-earnings evidence" if days_to >= 0 else "needs post-report review",
            },
            "reconciliation": reconciliation_requirements(
                phase=phase,
                bridge=bridge_map.get(ticker, {}),
                alert=alert_map.get(ticker, {}),
            ),
        }
        packets.append(packet)

    priority_order = {"critical": 1, "high": 2, "monitor": 3}
    packets.sort(key=lambda p: (priority_order.get(p["priority"], 99), p["days_to_or_from_earnings"], p["ticker"]))

    warnings: list[str] = []
    if trigger.get("warnings"):
        warnings.extend(trigger.get("warnings", []))
    if earnings.get("warnings"):
        warnings.extend(earnings.get("warnings", []))
    if not tech:
        warnings.append("technical-refresh.json unavailable; earnings packet omits technical context")
    if not trigger:
        warnings.append("trigger-sheet.json unavailable; earnings packet omits legacy trigger context")
    if not deploy:
        warnings.append("deployment-check.json unavailable; prep uses trigger-sheet context only and does not infer deployment state")
    if not official_bridge:
        warnings.append("official-earnings-bridge.json unavailable; post-earnings evidence remains source-open")
    if not alert_controller:
        warnings.append("alert-level-freshness-controller.json unavailable; alert reconciliation remains pending")
    near_fallbacks = sorted([p["ticker"] for p in packets if p.get("fallback_config")])
    if near_fallbacks:
        warnings.append("Generic fallback post-earnings config used for: " + ", ".join(near_fallbacks) + ". Add ticker-specific watch items if this is a material tracked name.")
    warnings = list(dict.fromkeys(warnings))

    trigger_age = age_hours(trigger.get("generated_at_utc"))
    earnings_age = age_hours(earnings.get("generated_at_utc"))
    trigger_stale = trigger_age is not None and trigger_age > trigger.get("stale_after_hours", STALE_HOURS)
    earnings_stale = earnings_age is not None and earnings_age > earnings.get("stale_after_hours", STALE_HOURS)
    trigger_last_trading_day = trigger.get("last_trading_day")
    trigger_source_days = trigger.get("source_last_trading_day") or {}
    source_last_trading_day = {
        "trigger": trigger_last_trading_day,
        "technical": trigger_source_days.get("technical"),
        "deployment": trigger_source_days.get("deployment"),
        "market_state": trigger_source_days.get("market_state"),
        "earnings": earnings.get("last_trading_day"),
    }
    status = "ok"
    if trigger.get("status") != "ok" or earnings.get("status") != "ok" or trigger_stale or earnings_stale:
        status = "partial"
    if not official_bridge or not alert_controller:
        status = "partial"

    warning_queue = [
        {
            "ticker": packet["ticker"],
            "priority": packet["priority"],
            "next_earnings_date": packet["next_earnings_date"],
            "days_to_earnings": packet["days_to_or_from_earnings"],
            "primary_confirmed": packet["primary_confirmed"],
            "source_class": packet["source_class"],
            "queue_reason": "primary_confirmation_needed" if not packet["primary_confirmed"] else "near_earnings_review",
            "review_only": True,
        }
        for packet in packets
        if packet["phase"] in {"pre_earnings", "reporting_today"}
    ]
    reconciliation_queue = [
        {
            "ticker": packet["ticker"],
            "priority": packet["priority"],
            "next_earnings_date": packet["next_earnings_date"],
            "required_reviews": ["scorecard", "thesis", "catalyst", "alert"],
            "review_only": True,
            "automatic_mutation_allowed": False,
        }
        for packet in packets
        if packet["phase"] == "post_earnings"
    ]

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stale_after_hours": STALE_HOURS,
        "expected_update_window": "Run after trigger_sheet_refresh.py and before post-earnings note targeting or post-earnings vault edits.",
        "last_trading_day": trigger_last_trading_day,
        "source_last_trading_day": source_last_trading_day,
        "freshness": {
            "trigger_file": {
                "path": str(TRIGGER_PATH),
                "generated_at_utc": trigger.get("generated_at_utc"),
                "age_hours": trigger_age,
                "age_label": fmt_age(trigger_age),
                "is_stale": trigger_stale,
            },
            "earnings_file": {
                "path": str(EARNINGS_PATH),
                "generated_at_utc": earnings.get("generated_at_utc"),
                "age_hours": earnings_age,
                "age_label": fmt_age(earnings_age),
                "is_stale": earnings_stale,
            },
        },
        "macro_context": build_macro_context(state),
        "window": {
            "back_days": WINDOW_BACK_DAYS,
            "back_trading_days": WINDOW_BACK_TRADING_DAYS,
            "forward_days": WINDOW_FORWARD_DAYS,
        },
        "warnings": warnings,
        "input_status": {
            "deployment_check": "available" if deploy else "unavailable_uses_trigger_context",
            "official_earnings_bridge": "available" if official_bridge else "unavailable",
            "alert_level_freshness_controller": "available" if alert_controller else "unavailable",
        },
        "earnings_lifecycle": {
            "source": "tmp/earnings-calendar.json",
            "closeouts": lifecycle_closeouts,
            "authority": {
                "review_only": True,
                "portfolio_mutation_allowed": False,
                "canonical_note_mutation_allowed": False,
                "trade_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        "fallback_config_tickers": near_fallbacks,
        "packets": packets,
        "near_earnings_warning_queue": warning_queue,
        "post_earnings_reconciliation_queue": reconciliation_queue,
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    sep = "=" * 86
    print("\n" + sep)
    print("  POST-EARNINGS PREP  --  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(sep)
    print("\n  MACRO CONTEXT")
    print("  " + payload["macro_context"].get("summary", "unavailable"))
    print("\n  {:<8}  {:<10}  {:<18}  {:<22}  {:<18}".format("Ticker", "Priority", "Stage", "Action state", "Earnings date"))
    print("  " + "-" * 82)
    for packet in packets:
        print("  {:<8}  {:<10}  {:<18}  {:<22}  {:<18}".format(
            packet["ticker"],
            packet["priority"],
            packet["stage"],
            legacy_state(packet["trigger_context"], "action_state") or "--",
            packet.get("next_earnings_date") or "--",
        ))

    if warnings:
        print("\n  WARNINGS")
        print("  " + "-" * 40)
        for warning in warnings:
            print("  - " + warning)

    print("\nOutput written to " + str(OUT_PATH))
    print("")


if __name__ == "__main__":
    main()
