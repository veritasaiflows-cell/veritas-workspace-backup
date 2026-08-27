#!/usr/bin/env python3
"""WF78 pilot provider/runtime and on-demand card proof gate.

This is a narrow review-only gate for the WF78 fixture set. It probes market
data provider runtime behavior for the 11 pilot fixtures and optionally builds
formal on-demand cards for a small fixture sample. It does not import fixtures
into the production answer path, promote tmp state, infer owner approval, or
authorize paper/live execution.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_production_scope import production_entries as production_scope_entries

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
PROVIDER_PROOF_OUT = TMP / "wf78-legacy-pilot-provider-runtime-proof-refresh.json"
CARD_PROOF_OUT = TMP / "wf78-legacy-pilot-on-demand-card-proof-refresh.json"
CARD_OUT_DIR = TMP / "wf78-pilot-on-demand-cards"
PRODUCTION_CARD_DIR = TMP / "ticker-intelligence-cards"

PILOT_SCOPE = "pilot_fixture"
REVIEW_100_SCOPE = "review_100_monitor"
EXPECTED_PRODUCTION_TICKERS = 42
EXPECTED_PILOT_FIXTURES = 11
DEFAULT_SAMPLE = ["ADBE", "ASML", "AVGO"]
LEGACY_FIXTURE_SEEDS = {"ADBE", "ASML", "AVGO", "CRM", "INTU", "NOW", "ORCL", "SAP", "SHOP", "TSM", "UBER"}
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

AUTHORITY_BOUNDARY = {
    "posture": "review_only_provider_runtime_and_on_demand_card_proof",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "sql_canon_migration_allowed": False,
    "db_path_migration_allowed": False,
    "tmp_artifact_promotion_allowed": False,
    "broad_ticker_import_allowed": False,
    "production_answer_path_overwrite_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def fixture_rows() -> list[dict[str, Any]]:
    rows = load_dict(UNIVERSE_PATH).get("entries")
    if not isinstance(rows, list):
        return []
    fixtures = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("active") is True
        and (
            row.get("universe_scope") == PILOT_SCOPE
            or (row.get("universe_scope") == REVIEW_100_SCOPE and str(row.get("ticker") or "").upper() in LEGACY_FIXTURE_SEEDS)
        )
    ]
    return sorted(fixtures, key=lambda row: str(row.get("ticker", "")))


def production_rows() -> list[dict[str, Any]]:
    migrated = production_scope_entries()
    if migrated:
        return migrated
    rows = load_dict(UNIVERSE_PATH).get("entries")
    if not isinstance(rows, list):
        return []
    return [
        row for row in rows
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("production_scope") is True
    ]


def yahoo_symbol(row: dict[str, Any]) -> str:
    source_symbols = row.get("source_symbols")
    if isinstance(source_symbols, dict) and source_symbols.get("yfinance"):
        return str(source_symbols["yfinance"]).strip()
    return str(row.get("ticker") or "").strip()


def parse_chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    chart = payload.get("chart") if isinstance(payload, dict) else {}
    result = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(result, list) or not result:
        error = chart.get("error") if isinstance(chart, dict) else None
        return {"ok": False, "error": f"missing chart result: {error}"}
    first = result[0] if isinstance(result[0], dict) else {}
    quote_rows = first.get("indicators", {}).get("quote", []) if isinstance(first.get("indicators"), dict) else []
    quote = quote_rows[0] if isinstance(quote_rows, list) and quote_rows and isinstance(quote_rows[0], dict) else {}
    closes = [value for value in (quote.get("close") or []) if value is not None]
    timestamps = first.get("timestamp") if isinstance(first.get("timestamp"), list) else []
    meta = first.get("meta") if isinstance(first.get("meta"), dict) else {}
    return {
        "ok": bool(closes),
        "close_count": len(closes),
        "last_close": closes[-1] if closes else None,
        "last_timestamp": timestamps[-1] if timestamps else None,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName") or meta.get("fullExchangeName"),
        "regular_market_time": meta.get("regularMarketTime"),
        "error": None if closes else "no close values returned",
    }


def fetch_chart(symbol: str, timeout: float) -> dict[str, Any]:
    url = YAHOO_CHART_URL.format(symbol=quote(symbol, safe=""))
    request = Request(url, headers={"User-Agent": "Veritas OpenClaw Research veritasaiflows@gmail.com"})
    with urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", None)
        payload = json.loads(response.read().decode("utf-8"))
    parsed = parse_chart_payload(payload)
    parsed.update({"http_status": status, "source_url": url})
    return parsed


def probe_symbol(row: dict[str, Any], retries: int, backoff_seconds: float, timeout: float) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    symbol = yahoo_symbol(row)
    attempts: list[dict[str, Any]] = []
    started = time.perf_counter()
    for attempt in range(1, retries + 2):
        attempt_started = time.perf_counter()
        try:
            payload = fetch_chart(symbol, timeout)
            elapsed = round(time.perf_counter() - attempt_started, 3)
            attempts.append({"attempt": attempt, "status": "ok" if payload.get("ok") else "error", "latency_seconds": elapsed, "error": payload.get("error")})
            if payload.get("ok"):
                return {
                    "ticker": ticker,
                    "provider_symbol": symbol,
                    "status": "ok",
                    "provider": "yahoo_chart",
                    "latency_seconds": round(time.perf_counter() - started, 3),
                    "attempt_count": attempt,
                    "attempts": attempts,
                    "data": {k: payload.get(k) for k in ["close_count", "last_close", "last_timestamp", "currency", "exchange", "regular_market_time", "source_url"]},
                    "source_open_required": True,
                }
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            elapsed = round(time.perf_counter() - attempt_started, 3)
            attempts.append({"attempt": attempt, "status": "error", "latency_seconds": elapsed, "error": f"{type(exc).__name__}: {exc}"})
        if attempt <= retries:
            time.sleep(backoff_seconds * attempt)
    return {
        "ticker": ticker,
        "provider_symbol": symbol,
        "status": "error",
        "provider": "yahoo_chart",
        "latency_seconds": round(time.perf_counter() - started, 3),
        "attempt_count": len(attempts),
        "attempts": attempts,
        "data": {},
        "source_open_required": True,
    }


def run_command(args: list[str], label: str, timeout: int = 240) -> dict[str, Any]:
    started = utc_now()
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "label": label,
        "command": "python " + " ".join(args),
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout.strip()[-2000:],
        "stderr_tail": completed.stderr.strip()[-2000:],
    }


def build_provider_proof(args: argparse.Namespace) -> dict[str, Any]:
    fixtures = fixture_rows()
    production = production_rows()
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    consecutive_errors = 0
    circuit_opened = False
    for row in fixtures:
        if consecutive_errors >= args.circuit_breaker_errors:
            circuit_opened = True
            rows.append({
                "ticker": str(row.get("ticker") or "").upper(),
                "provider_symbol": yahoo_symbol(row),
                "status": "skipped_circuit_open",
                "provider": "yahoo_chart",
                "latency_seconds": 0,
                "attempt_count": 0,
                "attempts": [],
                "data": {},
                "source_open_required": True,
            })
            continue
        result = probe_symbol(row, args.retries, args.backoff_seconds, args.timeout_seconds)
        rows.append(result)
        consecutive_errors = consecutive_errors + 1 if result["status"] != "ok" else 0

    total_runtime = round(time.perf_counter() - started, 3)
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    error_rows = [row for row in rows if row.get("status") != "ok"]
    production_symbols = {str(row.get("ticker") or "").upper() for row in production}
    fixture_symbols = {str(row.get("ticker") or "").upper() for row in fixtures}
    max_latency = max((float(row.get("latency_seconds") or 0) for row in rows), default=0.0)
    avg_latency = round(sum(float(row.get("latency_seconds") or 0) for row in rows) / len(rows), 3) if rows else 0.0
    success_rate = round(len(ok_rows) / len(rows), 4) if rows else 0.0

    checks = [
        {"name": "production_count_locked_42", "ok": len(production) == EXPECTED_PRODUCTION_TICKERS, "detail": {"actual": len(production), "expected": EXPECTED_PRODUCTION_TICKERS}, "severity": "error"},
        {"name": "fixture_count_11", "ok": len(fixtures) == EXPECTED_PILOT_FIXTURES, "detail": {"actual": len(fixtures), "expected": EXPECTED_PILOT_FIXTURES}, "severity": "error"},
        {"name": "all_fixture_rows_probed_or_circuit_labeled", "ok": len(rows) == len(fixtures), "detail": {"rows": len(rows), "fixtures": len(fixtures)}, "severity": "error"},
        {"name": "provider_success_rate", "ok": success_rate >= args.min_success_rate, "detail": {"success_rate": success_rate, "minimum": args.min_success_rate, "ok": len(ok_rows), "errors": len(error_rows)}, "severity": "error"},
        {"name": "runtime_budget_seconds", "ok": total_runtime <= args.runtime_budget_seconds, "detail": {"actual": total_runtime, "budget": args.runtime_budget_seconds}, "severity": "error"},
        {"name": "max_latency_budget_seconds", "ok": max_latency <= args.max_latency_seconds, "detail": {"actual": max_latency, "budget": args.max_latency_seconds}, "severity": "warning"},
        {"name": "retry_backoff_policy_recorded", "ok": args.retries >= 1 and args.backoff_seconds > 0, "detail": {"retries": args.retries, "backoff_seconds": args.backoff_seconds}, "severity": "error"},
        {"name": "circuit_breaker_policy_recorded", "ok": args.circuit_breaker_errors > 0, "detail": {"consecutive_error_limit": args.circuit_breaker_errors, "opened": circuit_opened}, "severity": "error"},
        {"name": "production_answer_path_untouched", "ok": not fixture_symbols.intersection(production_symbols), "detail": "Fixture/review-monitor seeds are not production-answer-path members; review-monitor cards may exist separately in the 200-card layer.", "severity": "error"},
    ]
    failed = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    proof = {
        "schema_version": 1,
        "artifact_type": "wf78_pilot_provider_runtime_proof",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ok" if not failed else "blocked",
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "provider_runtime_policy": {
            "provider": "yahoo_chart",
            "fixture_only": True,
            "production_answer_path_member": False,
            "retry_attempts_after_first_failure": args.retries,
            "backoff_seconds_base": args.backoff_seconds,
            "timeout_seconds_per_attempt": args.timeout_seconds,
            "circuit_breaker_consecutive_errors": args.circuit_breaker_errors,
            "runtime_budget_seconds": args.runtime_budget_seconds,
            "minimum_success_rate": args.min_success_rate,
            "source_open_required_before_material_finance_claims": True,
        },
        "summary": {
            "fixture_count": len(fixtures),
            "production_ticker_count": len(production),
            "ok_count": len(ok_rows),
            "error_count": len(error_rows),
            "success_rate": success_rate,
            "total_runtime_seconds": total_runtime,
            "avg_latency_seconds": avg_latency,
            "max_latency_seconds": max_latency,
            "circuit_breaker_opened": circuit_opened,
        },
        "checks": checks,
        "failed_checks": failed,
        "rows": rows,
        "blocked_next_steps_until_ok": [
            "live 25-name pilot import",
            "100/200/350/500 ticker expansion",
            "production answer-path overwrite",
            "decision-grade claims from fixture rows without source-open proof",
        ],
    }
    atomic_write_json(PROVIDER_PROOF_OUT, proof)
    return proof


def build_card_proof(sample: list[str]) -> dict[str, Any]:
    CARD_OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = TMP / "wf78-legacy-pilot-on-demand-card-build-summary-refresh.json"
    command = [
        "scripts/ticker_intelligence_card.py",
        "--out-dir", rel(CARD_OUT_DIR),
        "--summary-output", rel(summary_path),
    ]
    for ticker in sample:
        command.extend(["--ticker", ticker])
    result = run_command(command, "build_on_demand_fixture_cards")
    summary = load_dict(summary_path)
    cards = summary.get("cards") if isinstance(summary.get("cards"), list) else []
    errors = summary.get("errors") if isinstance(summary.get("errors"), list) else []
    fixture_symbols = {str(row.get("ticker") or "").upper() for row in fixture_rows()}
    production_symbols = {str(row.get("ticker") or "").upper() for row in production_rows()}
    card_paths = [CARD_OUT_DIR / f"{ticker}.current.json" for ticker in sample]
    card_payloads = [load_dict(path) for path in card_paths if path.exists()]
    checks = [
        {"name": "sample_is_fixture_only", "ok": all(ticker in fixture_symbols and ticker not in production_symbols for ticker in sample), "detail": {"sample": sample}, "severity": "error"},
        {"name": "build_command_ok", "ok": result["ok"], "detail": {"returncode": result["returncode"]}, "severity": "error"},
        {"name": "formal_card_count", "ok": len(cards) == len(sample), "detail": {"actual": len(cards), "expected": len(sample)}, "severity": "error"},
        {"name": "no_card_build_errors", "ok": not errors, "detail": errors, "severity": "error"},
        {"name": "cards_written_to_isolated_pilot_dir", "ok": all(path.exists() and CARD_OUT_DIR in path.parents for path in card_paths), "detail": [rel(path) for path in card_paths], "severity": "error"},
        {"name": "cards_remain_review_only", "ok": all(card.get("review_only") is True for card in card_payloads), "detail": {"cards": len(card_payloads)}, "severity": "error"},
        {"name": "source_open_boundary_present", "ok": all((card.get("authority_boundary") or {}).get("source_open_required_before_final_recommendation_or_action_claim") is True for card in card_payloads), "detail": {"cards": len(card_payloads)}, "severity": "error"},
        {"name": "production_card_registry_untouched_by_output", "ok": all(not (PRODUCTION_CARD_DIR / f"{ticker}.current.json").exists() for ticker in sample), "detail": {"production_card_dir": rel(PRODUCTION_CARD_DIR)}, "severity": "error"},
    ]
    failed = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    proof = {
        "schema_version": 1,
        "artifact_type": "wf78_pilot_on_demand_card_proof",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ok" if not failed else "blocked",
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sample_tickers": sample,
        "summary_path": rel(summary_path),
        "card_output_dir": rel(CARD_OUT_DIR),
        "command_result": result,
        "build_summary": summary,
        "checks": checks,
        "failed_checks": failed,
        "lower_tier_policy": {
            "thin_sql_row_or_on_demand_card_only": True,
            "material_claim_requires_source_open": True,
            "missing_or_stale_evidence_blocks_actionability": True,
            "must_not_block_current_42_production_answers": True,
        },
    }
    atomic_write_json(CARD_PROOF_OUT, proof)
    return proof


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-only", action="store_true", help="Only write provider runtime proof.")
    parser.add_argument("--cards-only", action="store_true", help="Only write formal on-demand card proof.")
    parser.add_argument("--sample", default=",".join(DEFAULT_SAMPLE), help="Comma-separated fixture sample for formal card proof.")
    parser.add_argument("--runtime-budget-seconds", type=float, default=90.0)
    parser.add_argument("--max-latency-seconds", type=float, default=15.0)
    parser.add_argument("--min-success-rate", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--backoff-seconds", type=float, default=0.75)
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--circuit-breaker-errors", type=int, default=4)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample = [ticker.strip().upper() for ticker in args.sample.split(",") if ticker.strip()]
    if args.provider_only and args.cards_only:
        raise SystemExit("--provider-only and --cards-only cannot both be set")
    results: dict[str, Any] = {}
    if not args.cards_only:
        results["provider_runtime_proof"] = build_provider_proof(args)
    if not args.provider_only:
        results["on_demand_card_proof"] = build_card_proof(sample)
    status = "ok" if all(value.get("status") == "ok" for value in results.values()) else "blocked"
    packet = {
        "schema_version": 1,
        "artifact_type": "wf78_pilot_provider_and_card_gate_result",
        "generated_at_utc": utc_now(),
        "status": status,
        "outputs": {
            "provider_runtime_proof": rel(PROVIDER_PROOF_OUT) if "provider_runtime_proof" in results else None,
            "on_demand_card_proof": rel(CARD_PROOF_OUT) if "on_demand_card_proof" in results else None,
        },
        "results": results,
    }
    print(json.dumps(packet, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())


