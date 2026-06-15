#!/usr/bin/env python3
"""WF68 Phase 1 read-only intraday quote/snapshot proof.

This runner proves, or fails closed on, a sanitized read-only market-data path
for the intraday alert engine. It performs no brokerage/account/order actions,
uses only GET requests, never uses the live brokerage endpoint, and persists no
secrets, raw headers, or raw response bodies.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from market_calendar_freshness import classify_quote_freshness, market_session

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO_CONFIG = ROOT / "tmp" / "portfolio-config.json"
DEFAULT_WF78_AUTO_ROUTER = ROOT / "tmp" / "wf78-auto-tier-routing.json"
DEFAULT_WF78_CAPITAL_REVIEW_QUEUE = ROOT / "tmp" / "wf78-capital-review-queue.json"
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_JSON_OUTPUT = OUT_DIR / "quote-snapshot-proof.json"
DEFAULT_MD_OUTPUT = OUT_DIR / "quote-snapshot-proof.md"
DEFAULT_VALIDATION_OUTPUT = OUT_DIR / "quote-snapshot-proof-validation.json"

WORKFLOW = "WF68 - Intraday Alert Engine and Advisor Surface"
PHASE = "phase_1_intraday_data_proof"
PROVIDER = "alpaca_market_data"
DATA_BASE_URL = "https://data.alpaca.markets"
SNAPSHOT_PATH = "/v2/stocks/snapshots"
FORBIDDEN_LIVE_BROKERAGE_URL = "https://" + "api.alpaca.markets"
PAPER_BROKERAGE_URL = "https://paper-api.alpaca.markets"
KEY_ENV = "ALPACA_PAPER_API_KEY_ID"
SECRET_ENV = "ALPACA_PAPER_API_SECRET_KEY"
AMBIGUOUS_OR_LIVE_NAMES = {
    "ALPACA_API_KEY_ID",
    "ALPACA_SECRET_KEY",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "ALPACA_LIVE_API_KEY_ID",
    "ALPACA_LIVE_API_SECRET_KEY",
    "APCA_LIVE_API_KEY_ID",
    "APCA_LIVE_API_SECRET_KEY",
}
DEFAULT_SYMBOL_COUNT = 10
DEFAULT_EXTRA_SYMBOLS = ["ETN"]
FRESH_SECONDS = 15 * 60
CURRENT_SECONDS = 24 * 60 * 60


class BlockedRun(Exception):
    """Expected fail-closed provider-gap block."""


def utc_now_dt() -> datetime:
    # Preserve sub-second precision. Alpaca snapshot timestamps can include
    # nanosecond precision; truncating our receive time to whole seconds can
    # make a legitimately received quote look as if its source timestamp is in
    # the future, causing the downstream WF68 packet validator to fail closed.
    return datetime.now(timezone.utc)


def utc_now() -> str:
    return utc_now_dt().isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def symbols_from_wf78_auto_router(path: Path) -> list[str]:
    payload = load_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    symbols = summary.get("auto_tier_a_tickers")
    if isinstance(symbols, list):
        return [str(symbol) for symbol in symbols if isinstance(symbol, str)]
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return [
        str(row.get("ticker"))
        for row in rows
        if isinstance(row, dict) and row.get("auto_tier") == "Tier A" and isinstance(row.get("ticker"), str)
    ]


def symbols_from_capital_review_queue(path: Path) -> list[str]:
    payload = load_json(path)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return [str(row.get("ticker")) for row in rows if isinstance(row, dict) and isinstance(row.get("ticker"), str)]


def append_unique(symbols: list[str], additions: list[str]) -> list[str]:
    result = list(symbols)
    for symbol in additions:
        normalized = str(symbol or "").strip().upper()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def load_symbols(config_path: Path, explicit_symbols: list[str] | None, wf78_auto_router: Path, wf78_capital_review_queue: Path) -> tuple[list[str], dict[str, Any]]:
    if explicit_symbols:
        symbols = explicit_symbols
        policy = "explicit_symbols_only"
    else:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        universe = data.get("tracked_universe") or {}
        if not isinstance(universe, dict):
            raise BlockedRun("tracked_universe_missing_or_invalid")
        symbols = list(universe.keys())[:DEFAULT_SYMBOL_COUNT]
        symbols = append_unique(symbols, DEFAULT_EXTRA_SYMBOLS)
        tier_a_symbols = symbols_from_wf78_auto_router(wf78_auto_router)
        capital_review_symbols = symbols_from_capital_review_queue(wf78_capital_review_queue)
        symbols = append_unique(symbols, tier_a_symbols)
        symbols = append_unique(symbols, capital_review_symbols)
        policy = "portfolio_first_10_plus_etn_plus_wf78_tier_a_plus_capital_review_queue"
    cleaned: list[str] = []
    for symbol in symbols:
        if not isinstance(symbol, str):
            continue
        normalized = symbol.strip().upper()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    if not cleaned:
        raise BlockedRun("no_symbols_selected")
    return cleaned, {
        "policy": policy,
        "default_symbol_count": DEFAULT_SYMBOL_COUNT,
        "extra_symbols": DEFAULT_EXTRA_SYMBOLS,
        "wf78_auto_router": rel(wf78_auto_router),
        "wf78_capital_review_queue": rel(wf78_capital_review_queue),
        "requested_symbol_count": len(cleaned),
    }


def credential_status() -> tuple[bool, list[str]]:
    selected_present = bool(os.environ.get(KEY_ENV)) and bool(os.environ.get(SECRET_ENV))
    ambiguous_present = sorted(name for name in AMBIGUOUS_OR_LIVE_NAMES if os.environ.get(name))
    return selected_present, ambiguous_present


def classify_freshness(source_ts: str | None, received_at: datetime) -> tuple[str, int | None]:
    classified = classify_quote_freshness(
        source_ts,
        received_at,
        fresh_seconds=FRESH_SECONDS,
        current_seconds=CURRENT_SECONDS,
    )
    return str(classified.get("freshness_status")), classified.get("age_seconds")


def sanitize_snapshot(symbol: str, snapshot: dict[str, Any], received_at: datetime) -> dict[str, Any]:
    latest_trade = snapshot.get("latestTrade") if isinstance(snapshot.get("latestTrade"), dict) else {}
    latest_quote = snapshot.get("latestQuote") if isinstance(snapshot.get("latestQuote"), dict) else {}
    daily_bar = snapshot.get("dailyBar") if isinstance(snapshot.get("dailyBar"), dict) else {}
    source_ts = latest_trade.get("t") or latest_quote.get("t") or daily_bar.get("t")
    freshness = classify_quote_freshness(
        source_ts,
        received_at,
        fresh_seconds=FRESH_SECONDS,
        current_seconds=CURRENT_SECONDS,
    )
    price = latest_trade.get("p") if latest_trade.get("p") is not None else daily_bar.get("c")
    return {
        "symbol": symbol,
        "source_timestamp_utc": source_ts,
        "received_at_utc": received_at.isoformat().replace("+00:00", "Z"),
        "freshness_status": freshness.get("freshness_status"),
        "calendar_freshness_status": freshness.get("calendar_freshness_status"),
        "market_session_window": freshness.get("market_session_window"),
        "source_market_date": freshness.get("source_market_date"),
        "latest_market_date": freshness.get("latest_market_date"),
        "last_completed_market_date": freshness.get("last_completed_market_date"),
        "fresh_intraday_allowed": freshness.get("fresh_intraday_allowed"),
        "closed_market_expected_stale_allowed": freshness.get("closed_market_expected_stale_allowed"),
        "age_seconds": freshness.get("age_seconds"),
        "price": price,
        "bid": latest_quote.get("bp"),
        "ask": latest_quote.get("ap"),
    }


def authority_block() -> dict[str, bool]:
    return {
        "live_trade_or_account_action_allowed": False,
        "paper_trade_allowed": False,
        "brokerage_account_mutation_allowed": False,
        "money_movement_allowed": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "sizing_sleeve_cash_risk_rule_change_allowed": False,
        "cron_channel_config_mutation_allowed": False,
    }


def proof_skeleton(status: str, symbols: list[str], generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "phase": PHASE,
        "generated_at_utc": generated_at,
        "status": status,
        "provider": PROVIDER,
        "endpoint_classification": "market_data_read_only_get_not_brokerage_account_endpoint",
        "market_data_base_url": DATA_BASE_URL,
        "brokerage_endpoint_used": False,
        "paper_brokerage_endpoint_required_for_account_actions": PAPER_BROKERAGE_URL,
        "live_brokerage_endpoint_detected": False,
        "live_brokerage_endpoint_forbidden": True,
        "allowed_methods": ["GET"],
        "blocked_methods": ["POST", "PATCH", "PUT", "DELETE"],
        "symbols_requested": symbols,
        "credential_source": {
            "mode": "paper_named_credentials_for_alpaca_market_data_only",
            "selected_variable_names": [KEY_ENV, SECRET_ENV],
            "secret_values_persisted": False,
            "ambiguous_or_live_names_detected": False,
        },
        "secrets_redacted": True,
        "raw_headers_persisted": False,
        "raw_response_bodies_persisted": False,
        "authority": authority_block(),
        "snapshots": [],
    }


def fetch_snapshots(symbols: list[str], timeout_seconds: int, feed: str | None) -> tuple[int, dict[str, Any]]:
    url = DATA_BASE_URL + SNAPSHOT_PATH
    if url.startswith(FORBIDDEN_LIVE_BROKERAGE_URL) or "api.alpaca.markets" in url:
        raise BlockedRun("live_brokerage_endpoint_detected")
    session = requests.Session()
    session.headers.update({
        "APCA-API-KEY-ID": os.environ[KEY_ENV],
        "APCA-API-SECRET-KEY": os.environ[SECRET_ENV],
        "Accept": "application/json",
    })
    params = {"symbols": ",".join(symbols)}
    if feed:
        params["feed"] = feed
    response = session.get(url, params=params, timeout=timeout_seconds)
    status_code = response.status_code
    if not 200 <= status_code < 300:
        return status_code, {}
    payload = response.json()
    if not isinstance(payload, dict):
        raise BlockedRun("provider_payload_not_json_object")
    if isinstance(payload.get("snapshots"), dict):
        return status_code, payload["snapshots"]
    # Alpaca currently returns the multi-symbol stock snapshots as a direct
    # symbol -> snapshot map. Accept both documented/provider shapes while
    # still persisting only the sanitized field subset downstream.
    return status_code, payload


def validate_proof(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    authority = payload.get("authority") or {}
    for field, value in authority.items():
        if value is not False:
            findings.append({"severity": "critical", "code": "authority_flag_not_false", "field": field, "value": value})
    if payload.get("brokerage_endpoint_used") is not False:
        findings.append({"severity": "critical", "code": "brokerage_endpoint_used_not_false"})
    if payload.get("live_brokerage_endpoint_detected") is not False:
        findings.append({"severity": "critical", "code": "live_brokerage_endpoint_detected_not_false"})
    if payload.get("secrets_redacted") is not True or payload.get("raw_headers_persisted") is not False or payload.get("raw_response_bodies_persisted") is not False:
        findings.append({"severity": "critical", "code": "redaction_contract_failed"})
    snapshots = payload.get("snapshots") or []
    if payload.get("status") == "ok" and not snapshots:
        findings.append({"severity": "critical", "code": "ok_without_snapshots"})
    for item in snapshots:
        if not item.get("source_timestamp_utc"):
            findings.append({"severity": "warning", "code": "snapshot_missing_source_timestamp", "symbol": item.get("symbol")})
        calendar_status = item.get("calendar_freshness_status") or item.get("freshness_status")
        if calendar_status != "fresh_intraday":
            code = (
                "snapshot_current_for_last_completed_session_no_alert_fire"
                if calendar_status in {"current_last_completed_session", "market_closed_expected_stale"}
                else "snapshot_not_fresh_enough_for_alert_fire"
            )
            findings.append({
                "severity": "warning",
                "code": code,
                "symbol": item.get("symbol"),
                "freshness_status": item.get("freshness_status"),
                "calendar_freshness_status": calendar_status,
            })
        if item.get("price") is None and item.get("bid") is None and item.get("ask") is None:
            findings.append({"severity": "warning", "code": "snapshot_missing_price_bid_ask", "symbol": item.get("symbol")})
    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "phase": PHASE,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical_count == 0 else "error",
        "critical_count": critical_count,
        "warning_count": warning_count,
        "findings": findings,
        "validated_artifact": rel(DEFAULT_JSON_OUTPUT),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# WF68 Phase 1 Quote Snapshot Proof",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Endpoint classification: `{payload.get('endpoint_classification')}`",
        f"- Market session: `{(payload.get('market_session') or {}).get('market_session_window')}`",
        f"- Secrets/raw headers/raw bodies persisted: `false`",
        f"- Authority hard-false: `{all(v is False for v in (payload.get('authority') or {}).values())}`",
    ]
    if payload.get("blocked_reason"):
        lines.append(f"- Blocked reason: `{payload.get('blocked_reason')}`")
    lines.extend([
        "",
        "## Sanitized snapshots",
        "",
        "| Symbol | Legacy freshness | Calendar freshness | Source timestamp | Source market date | Received | Price | Bid | Ask |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for item in payload.get("snapshots") or []:
        lines.append(
            f"| {item.get('symbol')} | {item.get('freshness_status')} | {item.get('calendar_freshness_status')} | "
            f"{item.get('source_timestamp_utc')} | {item.get('source_market_date')} | "
            f"{item.get('received_at_utc')} | {item.get('price')} | {item.get('bid')} | {item.get('ask')} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "This artifact is read-only market-data proof only. It does not authorize live trading, paper trading, brokerage/account mutation, money movement, canonical-note mutation, portfolio mutation, owner-approval inference, cron/channel/config mutation, or sizing/sleeve/cash/risk-rule changes.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    generated_at = utc_now()
    symbols, symbol_selection = load_symbols(
        Path(args.portfolio_config),
        args.symbols,
        Path(args.wf78_auto_router),
        Path(args.wf78_capital_review_queue),
    )
    proof = proof_skeleton("blocked", symbols, generated_at)
    proof["symbol_selection"] = symbol_selection
    proof["market_session"] = market_session(utc_now_dt())
    try:
        selected_present, ambiguous_names = credential_status()
        proof["credential_source"]["ambiguous_or_live_names_detected"] = bool(ambiguous_names)
        if ambiguous_names:
            raise BlockedRun("ambiguous_or_live_credential_names_present")
        if not selected_present:
            raise BlockedRun("paper_named_market_data_credentials_absent")

        status_code, snapshots = fetch_snapshots(symbols, args.timeout_seconds, args.feed)
        proof["provider_status_code_class"] = f"{status_code // 100}xx" if status_code else None
        proof["provider_feed"] = args.feed or "provider_default"
        if not 200 <= status_code < 300:
            raise BlockedRun(f"provider_http_{status_code}")
        received_at = utc_now_dt()
        sanitized = [sanitize_snapshot(symbol, snapshots.get(symbol) or {}, received_at) for symbol in symbols]
        proof["snapshots"] = sanitized
        calendar_counts: dict[str, int] = {}
        for item in sanitized:
            status = str(item.get("calendar_freshness_status") or "unknown")
            calendar_counts[status] = calendar_counts.get(status, 0) + 1
        proof["symbols_observed"] = [item["symbol"] for item in sanitized if item.get("source_timestamp_utc") or item.get("price") is not None or item.get("bid") is not None or item.get("ask") is not None]
        proof["symbols_missing"] = [item["symbol"] for item in sanitized if item["symbol"] not in proof["symbols_observed"]]
        proof["freshness_summary"] = {
            "fresh": sum(1 for item in sanitized if item.get("freshness_status") == "fresh"),
            "current_but_not_intraday_fresh": sum(1 for item in sanitized if item.get("freshness_status") == "current_but_not_intraday_fresh"),
            "stale_or_missing": sum(1 for item in sanitized if item.get("freshness_status") in {"stale", "missing_source_timestamp"}),
            "calendar_freshness_counts": calendar_counts,
            "fresh_intraday": calendar_counts.get("fresh_intraday", 0),
            "current_last_completed_session": calendar_counts.get("current_last_completed_session", 0),
            "market_closed_expected_stale": calendar_counts.get("market_closed_expected_stale", 0),
            "stale_unexpected": calendar_counts.get("stale_unexpected", 0),
            "provider_missing": calendar_counts.get("provider_missing", 0),
        }
        if proof["symbols_missing"]:
            proof["status"] = "blocked"
            proof["blocked_reason"] = "one_or_more_symbols_missing_snapshot"
        else:
            proof["status"] = "ok"
            if calendar_counts.get("stale_unexpected") or calendar_counts.get("provider_missing"):
                proof["alert_fire_policy"] = "stale_or_missing_quotes_must_degrade_to_no_fire_or_monitor_only"
            elif calendar_counts.get("fresh_intraday") == len(sanitized):
                proof["alert_fire_policy"] = "fresh_intraday_quotes_may_feed_trigger_engine_after_dedupe_and_owner_surface_checks"
            else:
                proof["alert_fire_policy"] = "closed_market_or_last_completed_session_quotes_must_degrade_to_no_fire_or_monitor_only"
    except BlockedRun as exc:
        proof["status"] = "blocked"
        proof["blocked_reason"] = str(exc)
        proof["provider_gap_report"] = True
    except requests.RequestException as exc:
        proof["status"] = "blocked"
        proof["blocked_reason"] = "provider_request_failed"
        proof["provider_gap_report"] = True
        proof["error_type"] = type(exc).__name__
    except Exception as exc:  # noqa: BLE001
        proof["status"] = "blocked"
        proof["blocked_reason"] = "unexpected_runner_error"
        proof["provider_gap_report"] = True
        proof["error_type"] = type(exc).__name__

    json_output = Path(args.output)
    md_output = Path(args.markdown_output)
    validation_output = Path(args.validation_output)
    write_json(json_output, proof)
    write_markdown(md_output, proof)
    validation = validate_proof(proof)
    validation["validated_artifact"] = rel(json_output)
    write_json(validation_output, validation)
    summary = {
        "status": proof.get("status"),
        "blocked_reason": proof.get("blocked_reason"),
        "json_output": rel(json_output),
        "markdown_output": rel(md_output),
        "validation_output": rel(validation_output),
        "secrets_redacted": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if proof.get("status") == "ok" and validation.get("status") == "ok" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-config", default=str(DEFAULT_PORTFOLIO_CONFIG))
    parser.add_argument("--output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT))
    parser.add_argument("--validation-output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--symbols", nargs="*", help="Optional explicit symbol list; defaults to first 10 tracked-universe symbols plus ETN if absent.")
    parser.add_argument("--wf78-auto-router", default=str(DEFAULT_WF78_AUTO_ROUTER))
    parser.add_argument("--wf78-capital-review-queue", default=str(DEFAULT_WF78_CAPITAL_REVIEW_QUEUE))
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--feed", default="iex", help="Alpaca stock market-data feed hint; default keeps free/basic data paths from false provider gaps.")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
