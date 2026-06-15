#!/usr/bin/env python3
"""Validate WF78 101-200 candidates against provider/runtime and official-source identity.

This is a report-only validation layer for the selected 101-200 candidate seed.
It probes Yahoo chart runtime for provider availability and uses the official SEC
company ticker map to validate CIK/source identity pointers. It does not import
tickers, promote production answer paths, expand SQL canon/cache authority,
mutate canon or portfolio state, infer owner approval, or authorize execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
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

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"

SOURCE_REGISTRY = DATA / "finance" / "wf78-101-200-candidate-source-v1.json"
MANIFEST = TMP / "wf78-100-to-200-candidate-manifest.json"
DEFAULT_OUT_JSON = TMP / "wf78-101-200-provider-source-validation.json"
DEFAULT_OUT_DB = TMP / "wf78-101-200-provider-source-validation.sqlite"

SCHEMA = "veritas.wf78_101_200_provider_source_validation.v1"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "provider_runtime_probe_only": True,
    "official_source_open_validation_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "report_only",
    "provider_runtime_probe_only",
    "official_source_open_validation_only",
}
REQUIRED_FALSE_FLAGS = {
    "ticker_import_allowed",
    "apply_allowed",
    "promotion_allowed",
    "production_answer_path_change_allowed",
    "sql_canon_expansion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_key(symbol: str) -> str:
    return "".join(ch for ch in str(symbol).upper() if ch.isalnum())


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def add_warning(warnings: list[dict[str, Any]], name: str, detail: Any) -> None:
    warnings.append({"name": name, "severity": "warning", "detail": detail})


def selected_registry_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(payload.get("selected_101_200")):
        if isinstance(row, dict) and row.get("selected_for_101_200") and row.get("eligible_for_101_200"):
            rows.append(row)
    return sorted(rows, key=lambda item: int(item.get("selected_rank") or 9999))


def manifest_registry_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in as_list(payload.get("candidate_manifest")):
        if not isinstance(row, dict):
            continue
        if row.get("candidate_source") != "wf78_101_200_candidate_source_registry":
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            rows[ticker] = row
    return rows


def fetch_json(url: str, timeout: float, user_agent: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        req = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}, None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def sec_ticker_map(timeout: float, user_agent: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload, error = fetch_json(SEC_TICKERS_URL, timeout, user_agent)
    if payload is None:
        return {}, {"artifact_type": "sec_company_tickers_map", "status": "error", "url": SEC_TICKERS_URL, "error": error}
    index: dict[str, dict[str, Any]] = {}
    for row in payload.values():
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        clean = {
            "ticker": ticker,
            "title": row.get("title"),
            "cik": str(row.get("cik_str") or "").strip(),
        }
        index[normalize_key(ticker)] = clean
    return index, {
        "artifact_type": "sec_company_tickers_map",
        "status": "ok",
        "url": SEC_TICKERS_URL,
        "row_count": len(index),
        "retrieved_at_utc": utc_now(),
    }


def parse_chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    chart = as_dict(payload.get("chart"))
    result = chart.get("result")
    if not isinstance(result, list) or not result:
        return {"ok": False, "error": f"missing chart result: {chart.get('error')}"}
    first = as_dict(result[0])
    indicators = as_dict(first.get("indicators"))
    quotes = indicators.get("quote") if isinstance(indicators.get("quote"), list) else []
    quote_row = as_dict(quotes[0]) if quotes else {}
    closes = [value for value in as_list(quote_row.get("close")) if value is not None]
    timestamps = as_list(first.get("timestamp"))
    meta = as_dict(first.get("meta"))
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


def fetch_chart(symbol: str, timeout: float, user_agent: str) -> dict[str, Any]:
    url = YAHOO_CHART_URL.format(symbol=quote(symbol, safe=""))
    payload, error = fetch_json(url, timeout, user_agent)
    if payload is None:
        return {"ok": False, "error": error, "source_url": url}
    parsed = parse_chart_payload(payload)
    parsed["source_url"] = url
    return parsed


def probe_provider(symbol: str, timeout: float, retries: int, backoff_seconds: float, user_agent: str) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    started = time.perf_counter()
    for attempt in range(1, retries + 2):
        attempt_started = time.perf_counter()
        payload = fetch_chart(symbol, timeout, user_agent)
        latency = round(time.perf_counter() - attempt_started, 3)
        attempts.append({"attempt": attempt, "status": "ok" if payload.get("ok") else "error", "latency_seconds": latency, "error": payload.get("error")})
        if payload.get("ok"):
            return {
                "provider": "yahoo_chart",
                "provider_symbol": symbol,
                "provider_status": "ok",
                "attempt_count": attempt,
                "latency_seconds": round(time.perf_counter() - started, 3),
                "attempts": attempts,
                "data": {key: payload.get(key) for key in ("close_count", "last_close", "last_timestamp", "currency", "exchange", "regular_market_time", "source_url")},
            }
        if attempt <= retries:
            time.sleep(backoff_seconds * attempt)
    return {
        "provider": "yahoo_chart",
        "provider_symbol": symbol,
        "provider_status": "error",
        "attempt_count": len(attempts),
        "latency_seconds": round(time.perf_counter() - started, 3),
        "attempts": attempts,
        "data": {},
    }


def official_validation(row: dict[str, Any], sec_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_symbol = str(row.get("source_symbol") or row.get("ticker") or "").upper()
    provider_symbol = str(row.get("yfinance_symbol") or row.get("ticker") or "").upper()
    candidates = [source_symbol, provider_symbol, source_symbol.replace(".", "-"), source_symbol.replace("-", "."), provider_symbol.replace("-", "."), provider_symbol.replace(".", "-")]
    sec_row: dict[str, Any] = {}
    for symbol in candidates:
        sec_row = sec_index.get(normalize_key(symbol), {})
        if sec_row:
            break
    registry_cik = str(row.get("sec_cik") or "").lstrip("0")
    sec_cik = str(sec_row.get("cik") or "").lstrip("0")
    cik_match = bool(registry_cik and sec_cik and registry_cik == sec_cik)
    cik_for_url = (sec_cik or registry_cik).zfill(10) if (sec_cik or registry_cik) else None
    return {
        "sec_cik_present": bool(registry_cik),
        "sec_ticker_map_present": bool(sec_row),
        "sec_cik_match": cik_match,
        "sec_registry_cik": registry_cik or None,
        "sec_map_cik": sec_cik or None,
        "sec_map_ticker": sec_row.get("ticker"),
        "sec_map_title": sec_row.get("title"),
        "official_sec_browse_url": f"https://www.sec.gov/edgar/browse/?CIK={sec_cik or registry_cik}" if (sec_cik or registry_cik) else None,
        "official_sec_companyfacts_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_for_url}.json" if cik_for_url else None,
        "company_ir_present": False,
        "company_ir_status": "not_registered_for_101_200_seed",
    }


def cleanup_required(provider_ok: bool, official: dict[str, Any], identity_complete: bool) -> list[dict[str, Any]]:
    cleanup: list[dict[str, Any]] = []
    if not identity_complete:
        cleanup.append({"family": "identity", "severity": "blocking", "reason": "Ticker, name, sector, or CIK missing."})
    if not provider_ok:
        cleanup.append({"family": "provider_runtime", "severity": "blocking", "reason": "Yahoo chart provider did not return usable close data."})
    if not official.get("sec_cik_present"):
        cleanup.append({"family": "official_sec_identity", "severity": "blocking", "reason": "Candidate registry has no SEC CIK."})
    if not official.get("sec_ticker_map_present"):
        cleanup.append({"family": "official_sec_identity", "severity": "blocking", "reason": "Ticker not found in official SEC ticker map."})
    elif not official.get("sec_cik_match"):
        cleanup.append({"family": "official_sec_identity", "severity": "blocking", "reason": "Registry CIK does not match official SEC ticker map CIK."})
    if not official.get("company_ir_present"):
        cleanup.append({"family": "company_ir", "severity": "review_required", "reason": "Company IR URL is not registered for this 101-200 seed."})
    cleanup.append({"family": "fundamental_analyst_technical_card", "severity": "review_required", "reason": "Full ticker card families are not built for this seed; source-open readiness is pre-import only."})
    return cleanup


def build_candidate_row(registry_row: dict[str, Any], manifest_row: dict[str, Any], sec_index: dict[str, dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    ticker = str(manifest_row.get("ticker") or registry_row.get("yfinance_symbol") or registry_row.get("ticker") or "").upper()
    source_symbol = str(registry_row.get("source_symbol") or registry_row.get("ticker") or ticker).upper()
    provider_symbol = str(registry_row.get("yfinance_symbol") or ticker).upper()
    identity_complete = bool(ticker and registry_row.get("name") and registry_row.get("sector") and registry_row.get("sec_cik"))
    provider = probe_provider(provider_symbol, args.timeout_seconds, args.retries, args.backoff_seconds, args.user_agent)
    official = official_validation(registry_row, sec_index)
    provider_ok = provider.get("provider_status") == "ok"
    source_open_hits = {
        "identity_complete": identity_complete,
        "provider_runtime_present": provider_ok,
        "technical_fresh_quote_present": provider_ok,
        "sec_cik_present": official.get("sec_cik_present") is True,
        "sec_cik_match": official.get("sec_cik_match") is True,
        "official_management_source_url_present": bool(official.get("official_sec_browse_url")),
        "official_ir_fundamental_reconciliation_matched": False,
        "fundamentals_available": False,
        "analyst_consensus_present": False,
        "price_band_stop_complete": False,
        "no_blocking_missing_evidence": provider_ok and official.get("sec_cik_match") is True,
        "authority_clean": True,
    }
    source_open_hits["fundamental_source_reconciliation_matched"] = source_open_hits["sec_cik_match"]
    cleanup = cleanup_required(provider_ok, official, identity_complete)
    blocking = [row for row in cleanup if row.get("severity") == "blocking"]
    pre_import_ready = not blocking
    return {
        "ticker": ticker,
        "source_symbol": source_symbol,
        "yfinance_symbol": provider_symbol,
        "name": registry_row.get("name"),
        "sector": registry_row.get("sector"),
        "industry": registry_row.get("industry"),
        "sec_cik": registry_row.get("sec_cik"),
        "selected_rank": registry_row.get("selected_rank"),
        "identity_complete": identity_complete,
        "candidate_source": "wf78_101_200_candidate_source_registry",
        "source_registry_path": rel(SOURCE_REGISTRY),
        "source_registry_sha256": sha256_file(SOURCE_REGISTRY),
        "manifest_path": rel(MANIFEST),
        "manifest_sha256": sha256_file(MANIFEST),
        "provider": provider.get("provider"),
        "provider_symbol": provider_symbol,
        "provider_status": provider.get("provider_status"),
        "provider_runtime_present": provider_ok,
        "attempt_count": provider.get("attempt_count"),
        "latency_seconds": provider.get("latency_seconds"),
        "data": provider.get("data"),
        "provider_attempts": provider.get("attempts"),
        "source_open_required": True,
        "official_source_registry_present": False,
        "official_earnings_source_url": official.get("official_sec_browse_url"),
        "official_sec_companyfacts_url": official.get("official_sec_companyfacts_url"),
        "source_label": "SEC EDGAR official company page" if official.get("official_sec_browse_url") else None,
        "period_label": None,
        "source_section": "SEC company identity and filings",
        "sec_ticker_map_present": official.get("sec_ticker_map_present"),
        "sec_cik_match": official.get("sec_cik_match"),
        "company_ir_present": official.get("company_ir_present"),
        "source_open_hits": source_open_hits,
        "source_open_ready": pre_import_ready,
        "promotion_ready": False,
        "promotion_gate_status": "pre_import_source_validated_owner_gated" if pre_import_ready else "blocked_provider_or_official_source_repair",
        "blocker_reason": "pre-import validation passed; still requires full card/fundamental/analyst/source-open build before promotion" if pre_import_ready else "; ".join(str(row.get("reason")) for row in blocking),
        "cleanup_required": cleanup,
        "authority_violations": [],
        "manifest_row": manifest_row,
    }


def load_inputs(checks: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    registry = as_dict(load_json_artifact(SOURCE_REGISTRY))
    manifest = as_dict(load_json_artifact(MANIFEST))
    selected = selected_registry_rows(registry)
    manifest_rows = manifest_registry_rows(manifest)
    add_check(checks, "source_registry_exists", SOURCE_REGISTRY.exists(), rel(SOURCE_REGISTRY))
    add_check(checks, "manifest_exists", MANIFEST.exists(), rel(MANIFEST))
    add_check(checks, "selected_registry_count_100", len(selected) == 100, len(selected))
    add_check(checks, "manifest_registry_count_100", len(manifest_rows) == 100, len(manifest_rows))
    registry_provider_symbols = {str(row.get("yfinance_symbol") or row.get("ticker") or "").upper() for row in selected}
    add_check(checks, "manifest_matches_registry_symbols", set(manifest_rows.keys()) == registry_provider_symbols, {"missing": sorted(registry_provider_symbols - set(manifest_rows)), "extra": sorted(set(manifest_rows) - registry_provider_symbols)})
    return registry, manifest, selected, manifest_rows


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = utc_now()
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    registry, manifest, selected, manifest_rows = load_inputs(checks)
    sec_index, sec_meta = sec_ticker_map(args.sec_timeout_seconds, args.user_agent)
    add_check(checks, "sec_ticker_map_available", bool(sec_index), sec_meta, "critical")
    rows_out: list[dict[str, Any]] = []
    started = time.perf_counter()
    for row in selected:
        provider_symbol = str(row.get("yfinance_symbol") or row.get("ticker") or "").upper()
        manifest_row = manifest_rows.get(provider_symbol, {})
        rows_out.append(build_candidate_row(row, manifest_row, sec_index, args))
    runtime_seconds = round(time.perf_counter() - started, 3)

    provider_ok = [row for row in rows_out if row.get("provider_runtime_present")]
    sec_match = [row for row in rows_out if row.get("sec_cik_match")]
    pre_import_ready = [row for row in rows_out if row.get("source_open_ready")]
    blocked = [row for row in rows_out if not row.get("source_open_ready")]
    share_class_rows = [row for row in rows_out if str(row.get("source_symbol")) != str(row.get("yfinance_symbol"))]
    provider_success_rate = round(len(provider_ok) / len(rows_out), 4) if rows_out else 0.0
    sec_match_rate = round(len(sec_match) / len(rows_out), 4) if rows_out else 0.0
    pre_import_ready_rate = round(len(pre_import_ready) / len(rows_out), 4) if rows_out else 0.0

    if provider_success_rate < args.min_provider_success_rate:
        add_warning(warnings, "provider_success_rate_below_target", {"success_rate": provider_success_rate, "target": args.min_provider_success_rate})
    if blocked:
        add_warning(warnings, "candidate_repair_required_before_import_decision", {"blocked_count": len(blocked), "ready_count": len(pre_import_ready)})
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    add_check(checks, "candidate_rows_100", len(rows_out) == 100, len(rows_out))
    add_check(checks, "provider_probe_completed_for_100", len([row for row in rows_out if row.get("provider_status") in {"ok", "error"}]) == 100, len(rows_out))

    critical = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    validation_status = "ok" if not critical else "error"
    readiness_status = "pre_import_source_validated" if len(pre_import_ready) == len(rows_out) and rows_out else "repair_required"
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_101_200_provider_official_source_open_validation",
        "status": validation_status,
        "candidate_validation_status": readiness_status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_policy": {
            "source_registry": rel(SOURCE_REGISTRY),
            "manifest": rel(MANIFEST),
            "provider": "yahoo_chart",
            "official_identity_source": SEC_TICKERS_URL,
            "minimum_provider_success_rate": args.min_provider_success_rate,
            "markdown_output": False,
            "source_open_rule": "Provider and SEC identity proof are pre-import gates only; full ticker-card/fundamental/analyst/source-open validation remains required before promotion.",
        },
        "summary": {
            "selected_candidate_count": len(selected),
            "candidate_rows": len(rows_out),
            "provider_ok_count": len(provider_ok),
            "provider_error_count": len(rows_out) - len(provider_ok),
            "provider_success_rate": provider_success_rate,
            "sec_cik_match_count": len(sec_match),
            "sec_cik_match_rate": sec_match_rate,
            "pre_import_source_ready_count": len(pre_import_ready),
            "blocked_or_repair_count": len(blocked),
            "pre_import_source_ready_rate": pre_import_ready_rate,
            "share_class_normalization_count": len(share_class_rows),
            "runtime_seconds": runtime_seconds,
            "next_safe_action": "Use ready rows to prepare an owner-gated import decision packet; repair blocked rows before any import/apply.",
        },
        "candidate_rows": rows_out,
        "groups": {
            "pre_import_source_validated_owner_gated": [
                {"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"), "selected_rank": row.get("selected_rank")}
                for row in pre_import_ready
            ],
            "blocked_provider_or_official_source_repair": [
                {"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"), "blocker_reason": row.get("blocker_reason")}
                for row in blocked
            ],
            "share_class_normalization": [
                {"source_symbol": row.get("source_symbol"), "yfinance_symbol": row.get("yfinance_symbol"), "ticker": row.get("ticker")}
                for row in share_class_rows
            ],
        },
        "source_artifacts": [
            {"artifact_type": "source_registry", "path": rel(SOURCE_REGISTRY), "exists": SOURCE_REGISTRY.exists(), "sha256": sha256_file(SOURCE_REGISTRY)},
            {"artifact_type": "candidate_manifest", "path": rel(MANIFEST), "exists": MANIFEST.exists(), "sha256": sha256_file(MANIFEST)},
            sec_meta,
        ],
        "validation": {
            "status": validation_status,
            "checks": checks,
            "warnings": warnings,
            "errors": critical,
        },
        "stop_lines": [
            "No ticker import/apply from this validation.",
            "No production answer-path change.",
            "No SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner approval inference.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
            "No official index-provider claim beyond the recorded source registry posture.",
        ],
    }


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def db_rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql)]


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS candidate_validation;
        DROP TABLE IF EXISTS provider_attempts;
        DROP TABLE IF EXISTS source_artifacts;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE candidate_validation (
            ticker TEXT PRIMARY KEY,
            source_symbol TEXT NOT NULL,
            yfinance_symbol TEXT NOT NULL,
            name TEXT,
            sector TEXT,
            industry TEXT,
            sec_cik TEXT,
            selected_rank INTEGER,
            provider_status TEXT NOT NULL,
            provider_runtime_present INTEGER NOT NULL CHECK (provider_runtime_present IN (0,1)),
            sec_cik_match INTEGER NOT NULL CHECK (sec_cik_match IN (0,1)),
            source_open_ready INTEGER NOT NULL CHECK (source_open_ready IN (0,1)),
            promotion_ready INTEGER NOT NULL CHECK (promotion_ready IN (0,1)),
            promotion_gate_status TEXT NOT NULL,
            blocker_reason TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE provider_attempts (
            ticker TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            status TEXT NOT NULL,
            latency_seconds REAL,
            error TEXT,
            PRIMARY KEY (ticker, attempt)
        ) STRICT;

        CREATE TABLE source_artifacts (
            artifact_type TEXT PRIMARY KEY,
            path_or_url TEXT NOT NULL,
            artifact_exists INTEGER NOT NULL CHECK (artifact_exists IN (0,1)),
            sha256 TEXT,
            row_count INTEGER,
            status TEXT
        ) STRICT;

        CREATE TABLE authority_boundary (
            flag TEXT PRIMARY KEY,
            value INTEGER NOT NULL CHECK (value IN (0,1)),
            required_value INTEGER NOT NULL CHECK (required_value IN (0,1)),
            ok INTEGER NOT NULL CHECK (ok IN (0,1))
        ) STRICT;

        CREATE TABLE validation_results (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            ok INTEGER NOT NULL CHECK (ok IN (0,1)),
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;
        """
    )


def write_sqlite(report: dict[str, Any], db_path: Path) -> None:
    with connect_write(db_path) as conn:
        init_schema(conn)
        for row in as_list(report.get("candidate_rows")):
            conn.execute(
                """
                INSERT INTO candidate_validation (
                    ticker, source_symbol, yfinance_symbol, name, sector, industry, sec_cik,
                    selected_rank, provider_status, provider_runtime_present, sec_cik_match,
                    source_open_ready, promotion_ready, promotion_gate_status, blocker_reason, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("ticker"),
                    row.get("source_symbol"),
                    row.get("yfinance_symbol"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("industry"),
                    row.get("sec_cik"),
                    row.get("selected_rank"),
                    row.get("provider_status"),
                    int_bool(row.get("provider_runtime_present")),
                    int_bool(row.get("sec_cik_match")),
                    int_bool(row.get("source_open_ready")),
                    int_bool(row.get("promotion_ready")),
                    row.get("promotion_gate_status"),
                    row.get("blocker_reason"),
                    json_text(row),
                ),
            )
            for attempt in as_list(row.get("provider_attempts")):
                conn.execute(
                    "INSERT INTO provider_attempts (ticker, attempt, status, latency_seconds, error) VALUES (?,?,?,?,?)",
                    (row.get("ticker"), attempt.get("attempt"), attempt.get("status"), attempt.get("latency_seconds"), attempt.get("error")),
                )
        for item in as_list(report.get("source_artifacts")):
            conn.execute(
                "INSERT INTO source_artifacts (artifact_type, path_or_url, artifact_exists, sha256, row_count, status) VALUES (?,?,?,?,?,?)",
                (item.get("artifact_type"), item.get("path") or item.get("url"), int_bool(item.get("exists", True)), item.get("sha256"), item.get("row_count"), item.get("status")),
            )
        for flag, value in as_dict(report.get("authority_boundary")).items():
            required = True if flag in REQUIRED_TRUE_FLAGS else False if flag in REQUIRED_FALSE_FLAGS else bool(value)
            conn.execute(
                "INSERT INTO authority_boundary (flag, value, required_value, ok) VALUES (?,?,?,?)",
                (flag, int_bool(value), int_bool(required), int_bool(bool(value) == required)),
            )
        for row in as_list(as_dict(report.get("validation")).get("checks")):
            conn.execute(
                "INSERT INTO validation_results (name, status, ok, severity, detail_json) VALUES (?,?,?,?,?)",
                (row.get("name"), row.get("status"), int_bool(row.get("ok")), row.get("severity"), json_text(row.get("detail"))),
            )
        for row in as_list(as_dict(report.get("validation")).get("warnings")):
            conn.execute(
                "INSERT OR REPLACE INTO validation_results (name, status, ok, severity, detail_json) VALUES (?,?,?,?,?)",
                (row.get("name"), "warning", 1, row.get("severity", "warning"), json_text(row.get("detail"))),
            )
        for key, value in {
            "schema": report.get("schema"),
            "generated_at_utc": report.get("generated_at_utc"),
            "status": report.get("status"),
            "candidate_validation_status": report.get("candidate_validation_status"),
            "candidate_rows": as_dict(report.get("summary")).get("candidate_rows"),
            "pre_import_source_ready_count": as_dict(report.get("summary")).get("pre_import_source_ready_count"),
            "blocked_or_repair_count": as_dict(report.get("summary")).get("blocked_or_repair_count"),
        }.items():
            conn.execute("INSERT INTO meta (key, value) VALUES (?,?)", (key, json_text(value)))
        conn.commit()


def validate_outputs(args: argparse.Namespace, report: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    if args.write:
        loaded = load_json_artifact(args.out_json)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("JSON output missing or schema mismatch")
        if not args.out_db.exists():
            errors.append(f"missing SQLite output: {rel(args.out_db)}")
        else:
            with connect_ro(args.out_db) as conn:
                integrity = scalar(conn, "PRAGMA integrity_check")
                if integrity != "ok":
                    errors.append(f"SQLite integrity_check={integrity}")
                strict = {
                    row["name"]
                    for row in db_rows(conn, "PRAGMA table_list")
                    if row.get("schema") == "main" and row.get("type") == "table" and row.get("strict") == 1
                }
                required = {"candidate_validation", "provider_attempts", "source_artifacts", "authority_boundary", "validation_results", "meta"}
                missing = sorted(required - strict)
                if missing:
                    errors.append(f"missing STRICT tables: {missing}")
                unsafe = scalar(conn, "SELECT count(*) FROM authority_boundary WHERE ok=0")
                if unsafe:
                    errors.append(f"unsafe authority rows: {unsafe}")
                rows_count = scalar(conn, "SELECT count(*) FROM candidate_validation")
                if rows_count != len(as_list(report.get("candidate_rows"))):
                    errors.append(f"candidate_validation rows {rows_count} != expected {len(as_list(report.get('candidate_rows')))}")
    return "ok" if not errors else "error", errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--sec-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--backoff-seconds", type=float, default=0.5)
    parser.add_argument("--min-provider-success-rate", type=float, default=0.9)
    parser.add_argument("--user-agent", default="Veritas OpenClaw Research veritasaiflows@gmail.com")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.out_json = resolve(args.out_json)
    args.out_db = resolve(args.out_db)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out_json, report, ensure_ascii=False)
        write_sqlite(report, args.out_db)
    output_status = "not_run"
    output_errors: list[str] = []
    if args.validate:
        output_status, output_errors = validate_outputs(args, report)
    status = report["status"]
    if output_errors:
        status = "error"
    print(
        json.dumps(
            {
                "status": status,
                "candidate_validation_status": report.get("candidate_validation_status"),
                "validation_result": report["status"],
                "output_validation_result": output_status,
                "output_validation_errors": output_errors,
                "json_out": rel(args.out_json) if args.write else None,
                "db_out": rel(args.out_db) if args.write else None,
                "summary": report["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
