#!/usr/bin/env python3
"""WF68 Phase 2 intraday alert trigger engine.

Thin, review-only trigger logic over the Phase 1 sanitized quote snapshot proof
and tmp/portfolio-config.json entry bands/stops. It emits alert packets only
under tmp/intraday-alerts/ and performs no market, brokerage, paper order,
account, cron/channel/config, canonical-note, or portfolio mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intraday_alert_packet_validator import validate_packet

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_QUOTES = OUT_DIR / "quote-snapshot-proof.json"
DEFAULT_PORTFOLIO_CONFIG = ROOT / "tmp" / "portfolio-config.json"
DEFAULT_PAPER_RESULT = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-execution-result.etn-2026-05-19-market.json"
DEFAULT_CURRENT_ALERTS_JSON = OUT_DIR / "current-alerts.json"
DEFAULT_CURRENT_ALERTS_MD = OUT_DIR / "current-alerts.md"
DEFAULT_VALIDATION = OUT_DIR / "trigger-engine-validation.json"
DEFAULT_DEDUPE_STATE = OUT_DIR / "alert-dedupe-state.json"
SCHEMA = OUT_DIR / "alert-packet.schema.json"

CORE_10 = ["ETN", "JPM", "GOOG", "MSFT", "LMT", "BRK.B", "XOM", "NVDA", "AMZN", "BKNG"]
ALERT_FRESHNESS = {"fresh", "current"}
NO_FIRE_FRESHNESS = {"current_but_not_intraday_fresh", "stale", "missing", "partial", "ambiguous"}
AUTHORITY = {
    "posture": "review_only_no_authority",
    "live_trade_or_account_action_allowed": False,
    "paper_trade_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
}
RATE_LIMIT = {
    "max_alerts_per_ticker_per_hour": 2,
    "max_alerts_total_per_hour": 12,
    "burst_policy": "Suppress duplicate ticker-event-band packets during the dedupe window unless severity increases.",
}
QUIET_RULE = "Emit only material band/stop/no-chase/paper-state alerts; suppress duplicate ticker-event-band packets inside the dedupe window unless severity increases."
STALE_RULE = "Fresh/current data may alert; current-but-not-intraday-fresh, stale, missing, partial, ambiguous, or contradictory data must no-fire or monitor-only."


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def quote_by_symbol(snapshot_proof: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(q.get("symbol")): q for q in snapshot_proof.get("snapshots", []) if q.get("symbol")}


def symbols_to_track(portfolio_config: dict[str, Any], paper_result: dict[str, Any] | None) -> list[str]:
    symbols = list(CORE_10)
    if isinstance(paper_result, dict):
        symbol = (
            paper_result.get("broker_redacted_result", {}).get("paper_order_symbol")
            or paper_result.get("broker_redacted_result", {}).get("symbol")
        )
        status = str(paper_result.get("broker_redacted_result", {}).get("paper_order_status") or "").lower()
        if symbol and status not in {"canceled", "rejected", "expired"} and symbol not in symbols:
            symbols.append(symbol)
    # Keep only symbols with bands for v1. Missing-band symbols are summarized as no-fire.
    bands = portfolio_config.get("entry_bands", {}) if isinstance(portfolio_config, dict) else {}
    return [s for s in symbols if s in bands or s in CORE_10]


def quote_is_alert_fresh(quote: dict[str, Any]) -> bool:
    status = quote.get("freshness_status")
    age = quote.get("age_seconds", 0)
    return status in ALERT_FRESHNESS and isinstance(age, (int, float)) and 0 <= float(age) <= 1800


def freshness_for_packet(quote: dict[str, Any]) -> dict[str, Any] | None:
    if not quote_is_alert_fresh(quote):
        return None
    return {
        "status": quote.get("freshness_status"),
        "age_seconds": max(0, float(quote.get("age_seconds", 0))),
        "stale_after_seconds": 1800,
        "ambiguity_state": "unambiguous",
    }


def classify_price(symbol: str, quote: dict[str, Any], band: dict[str, Any]) -> dict[str, Any] | None:
    freshness = quote.get("freshness_status")
    price = quote.get("price")
    low, high, stop = band.get("low"), band.get("high"), band.get("stop")
    if not quote_is_alert_fresh(quote) or not isinstance(price, (int, float)):
        return None
    if not all(isinstance(v, (int, float)) for v in (low, high, stop)):
        return None

    if price < stop:
        return {
            "event_type": "price_breaches_stop",
            "severity": "CRITICAL",
            "action_type": "owner_decision_required",
            "summary": f"{symbol} price {price:.2f} is below written stop/reference {stop:.2f}; review invalidation state.",
            "recommended_next_step": "owner_decision_required",
        }
    if low <= price <= high:
        return {
            "event_type": "price_enters_band",
            "severity": "HIGH",
            "action_type": "owner_decision_required",
            "summary": f"{symbol} price {price:.2f} is inside written entry band {low:.2f}-{high:.2f}; review only.",
            "recommended_next_step": "owner_decision_required",
        }
    if price > high:
        return {
            "event_type": "no_chase_upper_band_breach",
            "severity": "MONITOR",
            "action_type": "review",
            "summary": f"{symbol} price {price:.2f} is above no-chase upper band {high:.2f}; monitor, do not chase.",
            "recommended_next_step": "review",
        }
    return None


def packet_id_for(dedupe_key: str, generated_at: str) -> str:
    digest = hashlib.sha256(f"{dedupe_key}|{generated_at}".encode("utf-8")).hexdigest()[:12]
    return f"wf68-{digest}"


def build_packet(symbol: str, quote: dict[str, Any], band: dict[str, Any], trigger: dict[str, Any], generated_at: str) -> dict[str, Any]:
    low, high, stop = band.get("low"), band.get("high"), band.get("stop")
    event_type = trigger["event_type"]
    dedupe_key = f"{symbol}|{event_type}|{low}-{high}|{band.get('band_last_set', 'unknown')}"
    band_label = band.get("label") or f"{low}-{high}"
    stop_label = band.get("stop_label") or str(stop)
    return {
        "schema_version": "wf68.alert_packet.v0",
        "packet_id": packet_id_for(dedupe_key, generated_at),
        "generated_at_utc": generated_at,
        "workflow": "WF68",
        "taxonomy": {
            "severity": trigger["severity"],
            "action_type": trigger["action_type"],
            "quiet_rule": QUIET_RULE,
            "stale_data_rule": STALE_RULE,
        },
        "event": {
            "ticker": symbol,
            "event_type": event_type,
            "trigger": {
                "observed_price": quote.get("price"),
                "entry_band_low": low,
                "entry_band_high": high,
                "stop": stop,
                "band_last_set": band.get("band_last_set"),
                "freshness_status": quote.get("freshness_status"),
            },
            "summary": trigger["summary"],
        },
        "source": {
            "provider": "alpaca_market_data_sanitized_snapshot_proof",
            "source_timestamp_utc": quote.get("source_timestamp_utc"),
            "received_at_utc": quote.get("received_at_utc"),
            "freshness": freshness_for_packet(quote),
        },
        "owner_surfaces": [
            {
                "path": "03. Portfolio/Execution Board.md",
                "reference": f"{symbol} execution-board context; exact machine-readable band/stop in tmp/portfolio-config.json",
                "last_verified_at_utc": generated_at,
            },
            {
                "path": "tmp/portfolio-config.json",
                "reference": f"entry_bands.{symbol} {band_label} stop {stop_label}",
                "last_verified_at_utc": generated_at,
            },
        ],
        "dedupe": {"dedupe_key": dedupe_key, "suppression_window_minutes": 60},
        "rate_limit": RATE_LIMIT,
        "decision_packet": {
            "thesis": f"{symbol} alert is tied to the written owner-surface trigger condition and current portfolio config band.",
            "why_stack": [
                f"Written band/stop reference: {band_label} / stop {stop_label}.",
                "Alert is decision support only; it grants no trade, account, paper-order, sizing, sleeve, cash, portfolio, or approval authority.",
            ],
            "entry_logic": "Review only against fresh/current price evidence and the written band; do not chase above the upper band.",
            "invalidation": f"Stop/reference invalidation remains {stop_label} unless a separate gated owner-surface update changes it.",
            "recommended_next_step": trigger["recommended_next_step"],
            "owner_action_required": "Randall must explicitly decide any real or paper action; this packet only asks for review.",
        },
        "authority": AUTHORITY,
    }


def apply_dedupe(packets: list[dict[str, Any]], dedupe_state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    emitted: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    seen = dedupe_state.setdefault("seen_keys", {})
    severity_rank = {"INFO": 0, "MONITOR": 1, "HIGH": 2, "CRITICAL": 3}
    for packet in packets:
        key = packet["dedupe"]["dedupe_key"]
        severity = packet["taxonomy"]["severity"]
        prior = seen.get(key)
        if prior and severity_rank.get(severity, 0) <= severity_rank.get(prior.get("severity", "INFO"), 0):
            suppressed.append({"ticker": packet["event"]["ticker"], "event_type": packet["event"]["event_type"], "dedupe_key": key, "reason": "duplicate_same_or_lower_severity"})
            continue
        seen[key] = {"severity": severity, "last_packet_id": packet["packet_id"], "last_seen_at_utc": packet["generated_at_utc"]}
        emitted.append(packet)
    return emitted, suppressed, dedupe_state


def paper_state_summary(paper_result: dict[str, Any] | None, generated_at: str) -> list[dict[str, Any]]:
    if not isinstance(paper_result, dict):
        return []
    redacted = paper_result.get("broker_redacted_result", {}) if isinstance(paper_result.get("broker_redacted_result"), dict) else {}
    symbol = redacted.get("paper_order_symbol") or redacted.get("symbol")
    status = redacted.get("paper_order_status")
    if not symbol or not status:
        return []
    return [{
        "ticker": symbol,
        "event_type": "paper_position_or_fill_state_change",
        "status": "placeholder_no_packet",
        "observed_paper_order_status": status,
        "generated_at_utc": generated_at,
        "reason": "Phase 2 records sanitized paper order/fill state as monitor-only placeholder; no paper order submit/cancel/account action is allowed here.",
    }]


def run_engine(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = utc_now()
    quote_proof = load_json(args.quotes)
    portfolio_config = load_json(args.portfolio_config)
    paper_result = load_json(args.paper_result, default=None) if args.paper_result else None
    quotes = quote_by_symbol(quote_proof)
    bands = portfolio_config.get("entry_bands", {})
    tracked = symbols_to_track(portfolio_config, paper_result)
    no_fire: list[dict[str, Any]] = []
    candidate_packets: list[dict[str, Any]] = []

    for symbol in tracked:
        quote = quotes.get(symbol)
        band = bands.get(symbol)
        if not quote:
            no_fire.append({"ticker": symbol, "reason": "missing_quote", "freshness_status": "missing"})
            continue
        if not band:
            no_fire.append({"ticker": symbol, "reason": "missing_entry_band", "freshness_status": quote.get("freshness_status")})
            continue
        freshness = quote.get("freshness_status")
        if not quote_is_alert_fresh(quote):
            no_fire.append({
                "ticker": symbol,
                "reason": "freshness_policy_no_fire",
                "freshness_status": freshness,
                "age_seconds": quote.get("age_seconds"),
                "policy": "HIGH/CRITICAL actionable price alerts require fresh/current quote status and age <= 1800 seconds; current_but_not_intraday_fresh is no-fire/monitor-only.",
            })
            continue
        trigger = classify_price(symbol, quote, band)
        if trigger:
            candidate_packets.append(build_packet(symbol, quote, band, trigger, generated_at))
        else:
            no_fire.append({"ticker": symbol, "reason": "price_outside_actionable_band_without_no_chase_event", "freshness_status": freshness})

    state = load_json(args.dedupe_state, default={"seen_keys": {}}) if args.use_dedupe_state else {"seen_keys": {}}
    emitted, suppressed, updated_state = apply_dedupe(candidate_packets, state)
    if args.use_dedupe_state:
        write_json(args.dedupe_state, updated_state)

    validation_results = [validate_packet(packet, Path(f"<generated:{packet['packet_id']}>") , SCHEMA) for packet in emitted]
    validation = {
        "workflow": "WF68",
        "phase": "phase_2_trigger_engine_v1",
        "status": "ok" if all(v["status"] == "ok" for v in validation_results) else "error",
        "generated_at_utc": generated_at,
        "packet_count": len(emitted),
        "suppressed_duplicate_count": len(suppressed),
        "no_fire_count": len(no_fire),
        "authority": {**AUTHORITY, "brokerage_account_mutation_allowed": False, "cron_channel_config_mutation_allowed": False, "money_movement_allowed": False},
        "results": validation_results,
    }

    alert_doc = {
        "schema_version": "wf68.trigger_engine.current_alerts.v1",
        "workflow": "WF68",
        "phase": "phase_2_trigger_engine_v1",
        "status": validation["status"],
        "generated_at_utc": generated_at,
        "input_artifacts": {
            "quotes": str(args.quotes.relative_to(ROOT) if args.quotes.is_absolute() and ROOT in args.quotes.parents else args.quotes),
            "portfolio_config": str(args.portfolio_config.relative_to(ROOT) if args.portfolio_config.is_absolute() and ROOT in args.portfolio_config.parents else args.portfolio_config),
            "paper_result": str(args.paper_result.relative_to(ROOT) if args.paper_result and args.paper_result.is_absolute() and ROOT in args.paper_result.parents else args.paper_result) if args.paper_result else None,
        },
        "tracked_symbols": tracked,
        "alert_fire_policy": "Only fresh/current, unambiguous quote evidence may produce alert packets; current_but_not_intraday_fresh/stale/missing/partial/ambiguous data no-fires or monitor-only.",
        "alerts": emitted,
        "no_fire_or_monitor_only": no_fire,
        "duplicate_suppressed": suppressed,
        "paper_state_placeholders": paper_state_summary(paper_result, generated_at),
        "authority": validation["authority"],
        "validation": {"path": str(args.validation_output), "status": validation["status"]},
    }
    write_json(args.output_json, alert_doc)
    write_json(args.validation_output, validation)
    write_markdown(args.output_md, alert_doc)
    return {"alerts": alert_doc, "validation": validation}


def write_markdown(path: Path, alert_doc: dict[str, Any]) -> None:
    lines = [
        "# WF68 Current Intraday Alerts",
        "",
        f"- Generated UTC: {alert_doc['generated_at_utc']}",
        f"- Status: {alert_doc['status']}",
        f"- Alert packets emitted: {len(alert_doc['alerts'])}",
        f"- No-fire / monitor-only rows: {len(alert_doc['no_fire_or_monitor_only'])}",
        f"- Duplicate suppressed: {len(alert_doc['duplicate_suppressed'])}",
        "- Authority: review-only; no live/paper order, account, brokerage, canonical-note, portfolio, sizing/sleeve/cash/risk-rule, cron/channel/config mutation, or inferred owner approval.",
        "",
    ]
    if alert_doc["alerts"]:
        lines.append("## Alert packets")
        for packet in alert_doc["alerts"]:
            lines.append(f"- **{packet['taxonomy']['severity']}** {packet['event']['ticker']} `{packet['event']['event_type']}`: {packet['event']['summary']}")
        lines.append("")
    else:
        lines.append("No alert packets emitted. Current inputs did not satisfy fresh/current actionable fire policy or were outside trigger conditions.")
        lines.append("")
    if alert_doc["no_fire_or_monitor_only"]:
        lines.append("## No-fire / monitor-only")
        for row in alert_doc["no_fire_or_monitor_only"]:
            lines.append(f"- {row.get('ticker')}: {row.get('reason')} ({row.get('freshness_status')})")
        lines.append("")
    if alert_doc["paper_state_placeholders"]:
        lines.append("## Paper state placeholders")
        for row in alert_doc["paper_state_placeholders"]:
            lines.append(f"- {row.get('ticker')}: {row.get('observed_paper_order_status')} — {row.get('reason')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WF68 Phase 2 review-only intraday trigger engine.")
    parser.add_argument("--quotes", type=Path, default=DEFAULT_QUOTES)
    parser.add_argument("--portfolio-config", type=Path, default=DEFAULT_PORTFOLIO_CONFIG)
    parser.add_argument("--paper-result", type=Path, default=DEFAULT_PAPER_RESULT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_CURRENT_ALERTS_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_CURRENT_ALERTS_MD)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--dedupe-state", type=Path, default=DEFAULT_DEDUPE_STATE)
    parser.add_argument("--use-dedupe-state", action="store_true", help="Persist/read dedupe state. Default test/run mode suppresses duplicates only inside one engine invocation.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_engine(args)
    print(json.dumps({
        "workflow": "WF68",
        "phase": "phase_2_trigger_engine_v1",
        "status": result["validation"]["status"],
        "alerts_emitted": len(result["alerts"]["alerts"]),
        "no_fire_or_monitor_only": len(result["alerts"]["no_fire_or_monitor_only"]),
        "duplicate_suppressed": len(result["alerts"]["duplicate_suppressed"]),
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "validation_output": str(args.validation_output),
        "authority": result["validation"]["authority"],
    }, indent=2))
    return 0 if result["validation"]["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
