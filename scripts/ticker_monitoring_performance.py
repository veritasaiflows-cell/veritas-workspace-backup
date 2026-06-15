from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
STATE_HISTORY_PATH = WORKSPACE / "data" / "state-history" / "state-history-v1.jsonl"
OUTPUT_PATH = TMP / "ticker-monitoring-performance.json"
SUMMARY_PATH = TMP / "ticker-monitoring-performance.md"

DEPLOYMENT_CHECK_PATH = TMP / "deployment-check.json"
PRICE_SIGNALS_PATH = TMP / "daily-price-trend-signals.json"
SECTOR_BOARD_PATH = TMP / "sector-expansion-board.json"
SECTOR_CORRELATION_PATH = TMP / "sector-correlation-check.json"

SCHEMA_VERSION = 1
HISTORY_ROWS_MIN_FOR_OUTCOME_ANALYTICS = 5
CONTEXT_FRESH_HOURS = 36

AUTHORITY = {
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "trade_execution_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inference_allowed": False,
    "probability_or_modeling_authority": False,
    "model_ranked_deployment_allowed": False,
    "capital_action_allowed": False,
}

BLOCKING_BAND_STATES = {"BELOW_STOP", "STOPPED_OUT"}
REPAIR_WORKFLOW_STATES = {"REPAIR", "BENCH", "DO NOT TOUCH"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF54 review-only ticker monitoring performance analytics.")
    parser.add_argument("--window", default="post-close", help="Review window label; defaults to post-close.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Output JSON path.")
    parser.add_argument("--markdown-output", type=Path, default=SUMMARY_PATH, help="Optional Markdown summary path.")
    parser.add_argument("--no-markdown", action="store_true", help="Skip Markdown summary generation.")
    return parser.parse_args()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def source_artifact(path: Path, payload: dict[str, Any], *, required: bool, now: datetime) -> dict[str, Any]:
    generated = payload.get("generated_at_utc") or payload.get("generated_at")
    generated_dt = parse_dt(generated)
    age_hours: float | None = None
    freshness = "missing"
    if path.exists() and generated_dt:
        age_hours = round((now - generated_dt).total_seconds() / 3600, 2)
        freshness = "fresh" if age_hours <= CONTEXT_FRESH_HOURS else "stale"
    elif path.exists():
        freshness = "unknown_generated_at"
    return {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "generated_at_utc": generated,
        "status": payload.get("status") or payload.get("overall_classification"),
        "freshness": freshness,
        "age_hours": age_hours,
        "fresh_enough_for_context": bool(path.exists() and freshness in {"fresh", "unknown_generated_at"}),
    }


def count_state_history_rows(path: Path = STATE_HISTORY_PATH) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def history_status(path: Path = STATE_HISTORY_PATH) -> dict[str, Any]:
    rows = count_state_history_rows(path)
    return {
        "path": rel(path),
        "state_history_rows": rows,
        "available": rows > 0,
        "outcome_analytics_ready": False,
        "known_at_time_history_available": rows > 0,
        "future_realized_outcomes_available": False,
        "reason": (
            f"state history has {rows} row(s), which is present but insufficient for outcome analytics or calibration"
            if rows > 0 and rows < HISTORY_ROWS_MIN_FOR_OUTCOME_ANALYTICS
            else "state history is missing; current-state diagnostics only"
            if rows == 0
            else "state history row count threshold met, but WF54 v1 intentionally keeps outcome analytics disabled until realized outcomes are retained and audited"
        ),
        "minimum_rows_for_future_outcome_analytics": HISTORY_ROWS_MIN_FOR_OUTCOME_ANALYTICS,
    }


def index_price_signals(price_signals: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in price_signals.get("signals") or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if ticker:
            out[ticker] = item
    return out


def sector_context_by_ticker(sector_board: dict[str, Any], correlation: dict[str, Any], *, sector_context_fresh: bool, correlation_context_fresh: bool) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    promotion_candidates = set(str(t).upper() for t in ((sector_board.get("summary") or {}).get("promotion_review_candidates") or []))
    improving_sectors = set((sector_board.get("summary") or {}).get("improving_leadership_sectors") or [])
    underexposed_sectors = set((sector_board.get("summary") or {}).get("underexposed_sectors") or [])

    for sector in sector_board.get("sectors") or []:
        if not isinstance(sector, dict):
            continue
        sector_name = sector.get("sector")
        for candidate in sector.get("tracked_universe_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            ticker = str(candidate.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            out.setdefault(ticker, {})
            out[ticker].update({
                "sector": sector_name,
                "sector_leadership_status": sector.get("leadership_status"),
                "sector_underexposed": bool(sector.get("underexposed")),
                "sector_in_improving_leadership_list": sector_name in improving_sectors,
                "sector_in_underexposed_list": sector_name in underexposed_sectors,
                "sector_board_context_fresh_enough": sector_context_fresh,
            })

    for ticker in promotion_candidates:
        out.setdefault(ticker, {})["wf53_promotion_review_context"] = True
        out[ticker]["sector_board_context_fresh_enough"] = sector_context_fresh

    for row in (correlation.get("tracked_universe_context") or []):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        out.setdefault(ticker, {})
        out[ticker].update({
            "correlation_context_fresh_enough": correlation_context_fresh,
            "candidate_role": row.get("candidate_role"),
            "promotion_impact": row.get("promotion_impact"),
            "correlation_blockers": row.get("blockers") or [],
        })
    return out


def normalize_band_status(record: dict[str, Any], signal: dict[str, Any]) -> str:
    current = signal.get("current_state") if isinstance(signal.get("current_state"), dict) else {}
    value = current.get("band_status") or record.get("band_status") or record.get("band_position") or "UNKNOWN"
    return str(value).upper().strip()


def readiness_direction(record: dict[str, Any], signal: dict[str, Any], blocked_reasons: list[str]) -> str:
    if any(reason in blocked_reasons for reason in {"below_stop_or_stop_breach", "repair_or_bench_state"}):
        return "fail_closed_repair_or_stop"
    if blocked_reasons:
        return "blocked_or_needs_review"
    direction = signal.get("promotion_readiness_direction") or signal.get("readiness_direction")
    if direction in {"increased", "improving"}:
        return "improving_context"
    if direction in {"decreased", "weakening"}:
        return "weakening_context"
    action = str(record.get("action_state") or "").upper()
    if action in {"DEPLOYABLE NOW", "ALMOST DEPLOYABLE"}:
        return "monitor_constructive"
    return "monitor_only"


def monitoring_flags(record: dict[str, Any], signal: dict[str, Any], band_status: str) -> list[str]:
    flags: list[str] = []
    if record.get("below_stop") is True or band_status in BLOCKING_BAND_STATES:
        flags.append("below_stop_or_repair_fail_closed")
    if record.get("band_stale") is True:
        flags.append("band_review_debt")
    if record.get("earnings_blocked") is True:
        flags.append("earnings_blocked")
    current_state = signal.get("current_state") if isinstance(signal.get("current_state"), dict) else {}
    days = record.get("days_to_earnings") or current_state.get("days_to_earnings")
    if isinstance(days, int) and 0 <= days <= 21:
        flags.append("near_catalyst_window")
    if str(record.get("macro_gate") or "").upper() not in {"", "CLEAN", "UNKNOWN"}:
        flags.append("macro_context_degraded")
    blockers = signal.get("blockers") if isinstance(signal.get("blockers"), list) else []
    if "band_review_required" in blockers:
        flags.append("band_review_required")
    return sorted(set(flags))


def build_ticker(record: dict[str, Any], signal: dict[str, Any], sector_context: dict[str, Any]) -> dict[str, Any]:
    ticker = str(record.get("ticker") or signal.get("ticker") or "").upper().strip()
    band_status = normalize_band_status(record, signal)
    workflow_state = str(record.get("workflow_state") or (signal.get("current_state") or {}).get("workflow_state") or "UNKNOWN")
    deployment_status = str(record.get("action_state") or (signal.get("current_state") or {}).get("action_state") or "UNKNOWN")
    flags = monitoring_flags(record, signal, band_status)
    blocked_reasons: list[str] = []
    if band_status in BLOCKING_BAND_STATES or record.get("below_stop") is True:
        blocked_reasons.append("below_stop_or_stop_breach")
    if workflow_state.upper() in REPAIR_WORKFLOW_STATES or deployment_status.upper() in REPAIR_WORKFLOW_STATES:
        blocked_reasons.append("repair_or_bench_state")
    if "near_catalyst_window" in flags:
        blocked_reasons.append("near_catalyst_window")
    if "band_review_debt" in flags or "band_review_required" in flags:
        blocked_reasons.append("band_review_debt")
    for item in sector_context.get("correlation_blockers") or []:
        blocked_reasons.append(str(item))

    current_state = signal.get("current_state") if isinstance(signal.get("current_state"), dict) else {}
    return {
        "ticker": ticker,
        "known_at_time": {
            "data_date": record.get("data_date") or signal.get("data_date"),
            "close": record.get("close") or signal.get("close"),
            "ma_posture": record.get("ma_posture") or current_state.get("ma_posture"),
            "in_entry_band": record.get("in_entry_band") if "in_entry_band" in record else current_state.get("in_entry_band"),
            "below_stop": record.get("below_stop") if "below_stop" in record else current_state.get("below_stop"),
            "distance_to_band_pct": current_state.get("distance_to_band_pct"),
            "price_vs_band_midpoint_pct": current_state.get("price_vs_band_midpoint_pct"),
        },
        "future_realized_outcomes": {
            "retained": False,
            "used_in_this_artifact": False,
            "reason": "future realized outcomes are not retained/calibrated in WF54 v1",
        },
        "workflow_state": workflow_state,
        "deployment_status": deployment_status,
        "band_status": band_status,
        "below_stop_or_repair": bool(record.get("below_stop") is True or band_status in BLOCKING_BAND_STATES or workflow_state.upper() in REPAIR_WORKFLOW_STATES),
        "catalyst_flags": {
            "earnings_blocked": bool(record.get("earnings_blocked") is True),
            "near_catalyst_window": "near_catalyst_window" in flags,
            "days_to_earnings": record.get("days_to_earnings") or current_state.get("days_to_earnings"),
        },
        "sector_context": sector_context or {"available": False},
        "monitoring_flags": flags,
        "readiness_direction_label": readiness_direction(record, signal, blocked_reasons),
        "blocked_reasons": sorted(set(blocked_reasons)),
    }


def build_payload(window: str = "post-close") -> dict[str, Any]:
    now_dt = datetime.now(timezone.utc)
    deployment_check = load_json(DEPLOYMENT_CHECK_PATH)
    price_signals = load_json(PRICE_SIGNALS_PATH)
    sector_board = load_json(SECTOR_BOARD_PATH)
    sector_correlation = load_json(SECTOR_CORRELATION_PATH)

    sources = {
        "deployment_check": source_artifact(DEPLOYMENT_CHECK_PATH, deployment_check, required=True, now=now_dt),
        "daily_price_trend_signals": source_artifact(PRICE_SIGNALS_PATH, price_signals, required=False, now=now_dt),
        "sector_expansion_board": source_artifact(SECTOR_BOARD_PATH, sector_board, required=False, now=now_dt),
        "sector_correlation_check": source_artifact(SECTOR_CORRELATION_PATH, sector_correlation, required=False, now=now_dt),
        "state_history": {
            "path": rel(STATE_HISTORY_PATH),
            "required": False,
            "exists": STATE_HISTORY_PATH.exists(),
            "freshness": "append_only_history",
        },
    }
    signal_by_ticker = index_price_signals(price_signals)
    sector_by_ticker = sector_context_by_ticker(
        sector_board,
        sector_correlation,
        sector_context_fresh=bool(sources["sector_expansion_board"].get("fresh_enough_for_context")),
        correlation_context_fresh=bool(sources["sector_correlation_check"].get("fresh_enough_for_context")),
    )

    records = [row for row in deployment_check.get("records") or [] if isinstance(row, dict)]
    tickers = [build_ticker(row, signal_by_ticker.get(str(row.get("ticker") or "").upper(), {}), sector_by_ticker.get(str(row.get("ticker") or "").upper(), {})) for row in records]

    workflow_counts = Counter(item["workflow_state"] for item in tickers)
    deployment_counts = Counter(item["deployment_status"] for item in tickers)
    band_counts = Counter(item["band_status"] for item in tickers)
    readiness_counts = Counter(item["readiness_direction_label"] for item in tickers)
    flag_counts = Counter(flag for item in tickers for flag in item["monitoring_flags"])

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": "ok" if deployment_check.get("records") else "partial",
        "consumer_posture": "review_only",
        "authority": dict(AUTHORITY),
        "history_status": history_status(),
        "source_artifacts": sources,
        "tickers": tickers,
        "summary": {
            "ticker_count": len(tickers),
            "counts_by_workflow_state": dict(sorted(workflow_counts.items())),
            "counts_by_deployment_status": dict(sorted(deployment_counts.items())),
            "counts_by_band_status": dict(sorted(band_counts.items())),
            "counts_by_readiness_direction_label": dict(sorted(readiness_counts.items())),
            "monitoring_flag_counts": dict(sorted(flag_counts.items())),
            "fail_closed_tickers": [item["ticker"] for item in tickers if item["below_stop_or_repair"]],
            "blocked_or_review_required_tickers": [item["ticker"] for item in tickers if item["blocked_reasons"]],
            "promotion_review_context": {
                "wf53_available_for_context": bool(sources["sector_expansion_board"].get("fresh_enough_for_context")),
                "wf53_candidates": (sector_board.get("summary") or {}).get("promotion_review_candidates") or [],
                "tickers_with_wf53_context": sorted([ticker for ticker, ctx in sector_by_ticker.items() if ctx.get("wf53_promotion_review_context")]),
                "context_only_no_promotion_authority": True,
            },
        },
        "limits": [
            "review-only diagnostics; no canonical, portfolio, deployment, watchlist, sizing, trade, or owner-approval authority",
            "no probability, win-rate, expected-return, predictive calibration, or model-ranked deployment output",
            "known-at-time monitoring state is separated from future realized outcomes, which are not used in WF54 v1",
            "WF53 sector and correlation artifacts are context only and do not promote names or change risk limits",
        ],
    }
    validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("consumer_posture") != "review_only":
        raise ValueError("consumer_posture must be review_only")
    authority = payload.get("authority") or {}
    for key, expected in AUTHORITY.items():
        if authority.get(key) is not expected:
            raise ValueError(f"authority flag mismatch: {key}")
    hist = payload.get("history_status") or {}
    if hist.get("outcome_analytics_ready") is not False:
        raise ValueError("outcome analytics must remain disabled in v1")
    for item in payload.get("tickers") or []:
        if "known_at_time" not in item or "future_realized_outcomes" not in item:
            raise ValueError(f"ticker missing time-bound distinction: {item.get('ticker')}")
        if (item.get("future_realized_outcomes") or {}).get("used_in_this_artifact") is not False:
            raise ValueError(f"future outcomes must not be used: {item.get('ticker')}")


def markdown_summary(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    hist = payload.get("history_status") or {}
    return "\n".join([
        "# Ticker Monitoring Performance Analytics v1",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        "- Posture: review-only; no deployment, sizing, trade, watchlist, canonical mutation, probability, or owner-approval authority.",
        f"- History: {hist.get('state_history_rows')} row(s); outcome analytics ready = {hist.get('outcome_analytics_ready')}.",
        f"- Tickers reviewed: {summary.get('ticker_count')}",
        f"- Fail-closed tickers: {', '.join(summary.get('fail_closed_tickers') or []) or 'none'}",
        f"- WF53 context candidates: {', '.join((summary.get('promotion_review_context') or {}).get('wf53_candidates') or []) or 'none'}",
        "",
    ])


def main() -> int:
    args = parse_args()
    payload = build_payload(args.window)
    atomic_write_json(args.output, payload)
    if not args.no_markdown:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown_summary(payload), encoding="utf-8")
    print(f"wrote {rel(args.output)}")
    print(f"tickers={payload['summary']['ticker_count']} history_rows={payload['history_status']['state_history_rows']} outcome_ready={payload['history_status']['outcome_analytics_ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
