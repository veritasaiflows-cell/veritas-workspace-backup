#!/usr/bin/env python3
"""WF78 live 25-name pilot isolated import gate.

This gate imports the approved 25-name WF78 live pilot into isolated SQL pilot
tables only. It creates backups first, probes provider runtime for all 25 names,
and reruns production regression gates. It does not add pilot names to the
production 42 answer path, ticker-card registry, canon cache, portfolio notes,
or any execution surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
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
from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"
BACKUP_ROOT = ROOT / "backups" / "wf78-live-pilot-import"

PRELIGHT_PATH = TMP / "wf78-live-25-pilot-preflight.json"
UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
OUT_JSON = TMP / "wf78-live-25-pilot-import-gate.json"
OUT_MD = TMP / "wf78-live-25-pilot-import-gate.md"
LIVE_PILOT_PACKET = TMP / "finance-intelligence-state-live-pilot.json"
PRODUCTION_CARD_DIR = TMP / "ticker-intelligence-cards"

EXPECTED_PRODUCTION_COUNT = 42
EXPECTED_CANDIDATE_COUNT = 25
EXPECTED_FIXTURE_COUNT = 11
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

AUTHORITY_BOUNDARY = {
    "posture": "review_only_isolated_live_pilot_import_gate",
    "isolated_live_pilot_sql_import_performed": True,
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
    "canon_cache_write_allowed": False,
    "db_path_migration_allowed": False,
    "tmp_artifact_promotion_allowed": False,
    "broad_ticker_import_allowed": False,
    "production_answer_path_overwrite_allowed": False,
}


def report_only_preview_boundary() -> dict[str, Any]:
    boundary = dict(AUTHORITY_BOUNDARY)
    boundary["report_only_preview"] = True
    boundary["isolated_live_pilot_sql_import_performed"] = False
    boundary["preview_requires_apply_and_owner_approval_reference"] = True
    return boundary


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(db_path: Path = STATE_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def preflight_candidates() -> list[dict[str, Any]]:
    packet = load_dict(PRELIGHT_PATH)
    candidates = packet.get("candidate_symbols")
    if not isinstance(candidates, list):
        return []
    return [row for row in candidates if isinstance(row, dict)]


def production_tickers() -> list[str]:
    migrated = sorted(legacy_42_tier_tickers())
    if migrated:
        return migrated
    universe = load_dict(UNIVERSE_PATH)
    entries = universe.get("entries")
    if not isinstance(entries, list):
        return []
    return sorted(
        str(row.get("ticker") or "").upper()
        for row in entries
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope", "production_current_42") == "production_current_42"
    )


def pilot_fixture_tickers() -> list[str]:
    universe = load_dict(UNIVERSE_PATH)
    entries = universe.get("entries")
    if not isinstance(entries, list):
        return []
    return sorted(
        str(row.get("ticker") or "").upper()
        for row in entries
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope") == "pilot_fixture"
    )


def backup_inputs(run_id: str) -> dict[str, Any]:
    backup_dir = BACKUP_ROOT / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for path in [UNIVERSE_PATH, STATE_DB, PRELIGHT_PATH]:
        if not path.exists():
            copied.append({"source": rel(path), "exists": False})
            continue
        target = backup_dir / path.name
        if path.suffix.lower() == ".sqlite":
            with sqlite3.connect(str(path)) as source, sqlite3.connect(str(target)) as dest:
                source.backup(dest)
        else:
            shutil.copy2(path, target)
        copied.append({
            "source": rel(path),
            "backup": rel(target),
            "sha256": sha256_file(target),
            "bytes": target.stat().st_size,
        })
    production_hashes = []
    for card in sorted(PRODUCTION_CARD_DIR.glob("*.current.json")):
        production_hashes.append({"path": rel(card), "sha256": sha256_file(card)})
    manifest = {
        "schema_version": 1,
        "artifact_type": "wf78_live_pilot_import_backup_manifest",
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "backup_dir": rel(backup_dir),
        "copied": copied,
        "production_ticker_card_hashes": production_hashes,
        "rollback_route": [
            "restore data/finance/universe-v1.json from backup if touched",
            "restore tmp/finance-intelligence-state.sqlite from backup if pilot SQL rollback is required",
            "delete only newly generated live-pilot artifacts after reference check",
            "rerun production 42 validators and artifact/workspace indexes",
        ],
    }
    atomic_write_json(backup_dir / "manifest.json", manifest)
    return manifest


def parse_chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    chart = payload.get("chart") if isinstance(payload, dict) else {}
    result = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(result, list) or not result:
        return {"ok": False, "error": f"missing chart result: {chart.get('error') if isinstance(chart, dict) else None}"}
    first = result[0] if isinstance(result[0], dict) else {}
    indicators = first.get("indicators") if isinstance(first.get("indicators"), dict) else {}
    quotes = indicators.get("quote") if isinstance(indicators.get("quote"), list) else []
    quote_row = quotes[0] if quotes and isinstance(quotes[0], dict) else {}
    closes = [value for value in (quote_row.get("close") or []) if value is not None]
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


def probe_symbol(ticker: str, retries: int, backoff_seconds: float, timeout: float) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    started = time.perf_counter()
    for attempt in range(1, retries + 2):
        attempt_started = time.perf_counter()
        try:
            payload = fetch_chart(ticker, timeout)
            elapsed = round(time.perf_counter() - attempt_started, 3)
            attempts.append({"attempt": attempt, "status": "ok" if payload.get("ok") else "error", "latency_seconds": elapsed, "error": payload.get("error")})
            if payload.get("ok"):
                return {
                    "ticker": ticker,
                    "status": "ok",
                    "provider": "yahoo_chart",
                    "latency_seconds": round(time.perf_counter() - started, 3),
                    "attempt_count": attempt,
                    "attempts": attempts,
                    "data": {key: payload.get(key) for key in ["close_count", "last_close", "last_timestamp", "currency", "exchange", "regular_market_time", "source_url"]},
                }
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            elapsed = round(time.perf_counter() - attempt_started, 3)
            attempts.append({"attempt": attempt, "status": "error", "latency_seconds": elapsed, "error": f"{type(exc).__name__}: {exc}"})
        if attempt <= retries:
            time.sleep(backoff_seconds * attempt)
    return {
        "ticker": ticker,
        "status": "error",
        "provider": "yahoo_chart",
        "latency_seconds": round(time.perf_counter() - started, 3),
        "attempt_count": len(attempts),
        "attempts": attempts,
        "data": {},
    }


def provider_probe(candidates: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    consecutive_errors = 0
    circuit_opened = False
    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        if consecutive_errors >= args.circuit_breaker_errors:
            circuit_opened = True
            results.append({"ticker": ticker, "status": "skipped_circuit_open", "provider": "yahoo_chart", "latency_seconds": 0, "attempt_count": 0, "attempts": [], "data": {}})
            continue
        result = probe_symbol(ticker, args.retries, args.backoff_seconds, args.timeout_seconds)
        results.append(result)
        consecutive_errors = consecutive_errors + 1 if result["status"] != "ok" else 0
    total_runtime = round(time.perf_counter() - started, 3)
    ok_rows = [row for row in results if row.get("status") == "ok"]
    error_rows = [row for row in results if row.get("status") != "ok"]
    max_latency = max((float(row.get("latency_seconds") or 0) for row in results), default=0.0)
    success_rate = round(len(ok_rows) / len(results), 4) if results else 0.0
    return {
        "status": "ok" if success_rate >= args.min_success_rate and total_runtime <= args.runtime_budget_seconds else "blocked",
        "summary": {
            "candidate_count": len(candidates),
            "ok_count": len(ok_rows),
            "error_count": len(error_rows),
            "success_rate": success_rate,
            "total_runtime_seconds": total_runtime,
            "max_latency_seconds": max_latency,
            "circuit_breaker_opened": circuit_opened,
        },
        "policy": {
            "provider": "yahoo_chart",
            "retry_attempts_after_first_failure": args.retries,
            "backoff_seconds_base": args.backoff_seconds,
            "timeout_seconds_per_attempt": args.timeout_seconds,
            "circuit_breaker_consecutive_errors": args.circuit_breaker_errors,
            "runtime_budget_seconds": args.runtime_budget_seconds,
            "minimum_success_rate": args.min_success_rate,
        },
        "rows": results,
    }


def init_live_pilot_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS live_pilot_candidate_registry (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            pilot_tier TEXT NOT NULL,
            role TEXT,
            rationale TEXT,
            pilot_status TEXT NOT NULL,
            production_answer_path_member INTEGER NOT NULL,
            decision_grade_eligible INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            thin_row_only INTEGER NOT NULL,
            on_demand_card_required_before_claim INTEGER NOT NULL,
            provider_telemetry_required INTEGER NOT NULL,
            stale_but_known_disclosure_required INTEGER NOT NULL,
            imported_at_utc TEXT NOT NULL,
            authority_flags_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS live_pilot_provider_status (
            ticker TEXT PRIMARY KEY REFERENCES live_pilot_candidate_registry(ticker) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            provider_status TEXT NOT NULL,
            last_probe_at_utc TEXT NOT NULL,
            last_successful_probe_at_utc TEXT,
            latest_close REAL,
            latest_timestamp INTEGER,
            latency_seconds REAL,
            attempt_count INTEGER NOT NULL,
            source_url TEXT,
            error_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS live_pilot_import_validation (
            check_name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        DROP VIEW IF EXISTS current_live_pilot_candidates;
        CREATE VIEW current_live_pilot_candidates AS
            SELECT c.ticker, c.name, c.sector, c.pilot_tier, c.role, c.pilot_status,
                   c.production_answer_path_member, c.decision_grade_eligible,
                   c.source_open_required, c.thin_row_only,
                   c.on_demand_card_required_before_claim,
                   c.provider_telemetry_required,
                   c.stale_but_known_disclosure_required,
                   p.provider_status, p.last_probe_at_utc,
                   p.last_successful_probe_at_utc, p.latest_close,
                   p.latest_timestamp, p.latency_seconds,
                   c.imported_at_utc, c.authority_flags_json
            FROM live_pilot_candidate_registry c
            LEFT JOIN live_pilot_provider_status p ON p.ticker = c.ticker
            WHERE c.production_answer_path_member = 0
              AND c.decision_grade_eligible = 0
              AND c.thin_row_only = 1
            ORDER BY c.ticker;
        """
    )


def write_live_pilot(conn: sqlite3.Connection, candidates: list[dict[str, Any]], probe: dict[str, Any]) -> None:
    now = utc_now()
    probe_rows = {str(row.get("ticker") or "").upper(): row for row in probe.get("rows", []) if isinstance(row, dict)}
    with conn:
        conn.execute("DELETE FROM live_pilot_candidate_registry")
        conn.execute("DELETE FROM live_pilot_provider_status")
        conn.execute("DELETE FROM live_pilot_import_validation")
        for row in candidates:
            ticker = str(row.get("ticker") or "").upper()
            conn.execute(
                """
                INSERT INTO live_pilot_candidate_registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticker,
                    row.get("name"),
                    row.get("sector"),
                    row.get("tier") or "C",
                    row.get("role"),
                    row.get("rationale"),
                    "isolated_live_pilot_imported_review_only",
                    0,
                    0,
                    1,
                    1,
                    1,
                    1,
                    1,
                    now,
                    json_text(AUTHORITY_BOUNDARY),
                    json_text(row),
                ),
            )
            result = probe_rows.get(ticker, {"status": "missing", "data": {}, "attempts": []})
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            errors = [attempt for attempt in result.get("attempts", []) if isinstance(attempt, dict) and attempt.get("status") != "ok"]
            conn.execute(
                """
                INSERT INTO live_pilot_provider_status VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticker,
                    result.get("provider") or "yahoo_chart",
                    result.get("status") or "missing",
                    now,
                    now if result.get("status") == "ok" else None,
                    data.get("last_close"),
                    data.get("last_timestamp"),
                    result.get("latency_seconds"),
                    int(result.get("attempt_count") or 0),
                    data.get("source_url"),
                    json_text(errors),
                    json_text(result),
                ),
            )


def run_command(args: list[str], label: str, timeout: int = 300) -> dict[str, Any]:
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
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout.strip()[-2000:],
        "stderr_tail": completed.stderr.strip()[-2000:],
    }


def production_card_hashes() -> dict[str, str | None]:
    return {path.name: sha256_file(path) for path in sorted(PRODUCTION_CARD_DIR.glob("*.current.json"))}


def validate_import(conn: sqlite3.Connection, candidates: list[dict[str, Any]], before_hashes: dict[str, str | None], after_hashes: dict[str, str | None], probe: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any, severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    candidate_tickers = [str(row.get("ticker") or "").upper() for row in candidates]
    production = production_tickers()
    fixtures = pilot_fixture_tickers()
    overlap = sorted(set(candidate_tickers).intersection(production))
    row_count = scalar(conn, "SELECT COUNT(*) FROM live_pilot_candidate_registry")
    view_count = scalar(conn, "SELECT COUNT(*) FROM current_live_pilot_candidates")
    provider_ok = scalar(conn, "SELECT COUNT(*) FROM live_pilot_provider_status WHERE provider_status='ok'")
    provider_total = scalar(conn, "SELECT COUNT(*) FROM live_pilot_provider_status")
    bad_authority = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM live_pilot_candidate_registry
        WHERE production_answer_path_member != 0
           OR decision_grade_eligible != 0
           OR source_open_required != 1
           OR thin_row_only != 1
           OR on_demand_card_required_before_claim != 1
        """,
    )
    production_overlap_sql = scalar(conn, "SELECT COUNT(*) FROM live_pilot_candidate_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
    integrity = scalar(conn, "PRAGMA integrity_check")
    fk_rows = rows(conn, "PRAGMA foreign_key_check")
    add("preflight_status_ready_for_review", load_dict(PRELIGHT_PATH).get("status") == "ready_for_review", {"status": load_dict(PRELIGHT_PATH).get("status")})
    add("candidate_count_25", len(candidate_tickers) == EXPECTED_CANDIDATE_COUNT, {"actual": len(candidate_tickers), "expected": EXPECTED_CANDIDATE_COUNT})
    add("candidate_symbols_unique", len(candidate_tickers) == len(set(candidate_tickers)), {"duplicates": sorted({ticker for ticker in candidate_tickers if candidate_tickers.count(ticker) > 1})})
    add("production_count_locked_42", len(production) == EXPECTED_PRODUCTION_COUNT, {"actual": len(production), "expected": EXPECTED_PRODUCTION_COUNT})
    add("fixture_count_locked_11", len(fixtures) == EXPECTED_FIXTURE_COUNT, {"actual": len(fixtures), "expected": EXPECTED_FIXTURE_COUNT})
    add("production_overlap_zero", not overlap, {"overlap": overlap})
    add("live_pilot_registry_count_25", row_count == EXPECTED_CANDIDATE_COUNT, {"rows": row_count})
    add("current_live_pilot_view_count_25", view_count == EXPECTED_CANDIDATE_COUNT, {"rows": view_count})
    add("provider_probe_success_rate", probe.get("status") == "ok", probe.get("summary"))
    add("provider_rows_loaded_25", provider_total == EXPECTED_CANDIDATE_COUNT and provider_ok >= int(EXPECTED_CANDIDATE_COUNT * 0.92), {"provider_total": provider_total, "provider_ok": provider_ok})
    add("live_pilot_authority_flags_false", bad_authority == 0, {"rows": bad_authority})
    add("live_pilot_excluded_from_production_current_cards", production_overlap_sql == 0, {"rows": production_overlap_sql})
    add("production_card_hashes_unchanged", before_hashes == after_hashes, {"before_count": len(before_hashes), "after_count": len(after_hashes)})
    add("sqlite_integrity_ok", integrity == "ok", integrity)
    add("sqlite_foreign_key_check_ok", len(fk_rows) == 0, {"rows": len(fk_rows)})
    return checks


def live_pilot_packet(conn: sqlite3.Connection, checks: list[dict[str, Any]], probe: dict[str, Any], backup_manifest: dict[str, Any]) -> dict[str, Any]:
    candidates = rows(conn, "SELECT * FROM current_live_pilot_candidates ORDER BY ticker")
    failed = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    packet = {
        "schema_version": 1,
        "artifact_type": "finance_intelligence_state_live_pilot_packet",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ok" if not failed else "blocked",
        "review_only": True,
        "db_path": rel(STATE_DB),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "answer_contract": {
            "sql_is_routing_and_current_state_only": True,
            "material_finance_claim_requires_source_open": True,
            "canonical_markdown_remains_owner_truth": True,
            "must_not_infer_approval_or_execution_authority": True,
            "must_disclose_stale_or_conflicting_rows": True,
        },
        "summary": {
            "candidate_count": len(candidates),
            "provider_status": probe.get("status"),
            **(probe.get("summary") or {}),
        },
        "candidates": candidates,
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed_checks": failed},
        "backup_manifest": backup_manifest,
        "stop_lines": [
            "Pilot rows are isolated SQL/query rows only.",
            "No production 42 answer-path overwrite.",
            "No production ticker-card registry write.",
            "No SQL-canon or canon-cache write.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner approval inference.",
            "No paper/live/brokerage/account action or money movement.",
        ],
    }
    atomic_write_json(LIVE_PILOT_PACKET, packet)
    return packet


def write_markdown(packet: dict[str, Any]) -> None:
    summary = packet.get("summary") or {}
    checks = packet.get("validation", {}).get("checks", [])
    lines = [
        "# WF78 Live 25 Pilot Import Gate",
        "",
        f"Status: `{packet.get('status')}`",
        "",
        "This gate writes the 25-name pilot only to isolated WF78 SQL pilot surfaces. It is not production import, canon mutation, owner approval, or execution authority.",
        "",
        "## Summary",
        "",
        f"- Candidate rows: {summary.get('candidate_count')}",
        f"- Provider status: {summary.get('provider_status')}",
        f"- Provider success rate: {summary.get('success_rate')}",
        f"- Total runtime seconds: {summary.get('total_runtime_seconds')}",
        "",
        "## Validation",
        "",
    ]
    for check in checks:
        marker = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"- {marker} `{check.get('name')}`: {check.get('detail')}")
    lines.extend([
        "",
        "## Stop Lines",
        "",
    ])
    lines.extend(f"- {line}" for line in packet.get("stop_lines", []))
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_gate(args: argparse.Namespace) -> dict[str, Any]:
    candidates = preflight_candidates()
    run_id = f"wf78-live-pilot-import-{stamp()}"
    before_hashes = production_card_hashes()
    backup_manifest = backup_inputs(run_id)
    probe = provider_probe(candidates, args)
    with connect(STATE_DB) as conn:
        init_live_pilot_schema(conn)
        write_live_pilot(conn, candidates, probe)
        after_hashes = production_card_hashes()
        checks = validate_import(conn, candidates, before_hashes, after_hashes, probe)
        packet = live_pilot_packet(conn, checks, probe, backup_manifest)
        with conn:
            conn.execute("DELETE FROM live_pilot_import_validation")
            for check in checks:
                conn.execute(
                    "INSERT INTO live_pilot_import_validation VALUES (?,?,?,?)",
                    (check["name"], "ok" if check["ok"] else "blocked", check.get("severity", "error"), json_text(check.get("detail"))),
                )
    write_markdown(packet)
    atomic_write_json(OUT_JSON, packet)
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Required to write isolated live-pilot SQL rows and backup artifacts.")
    parser.add_argument("--runtime-budget-seconds", type=float, default=180.0)
    parser.add_argument("--min-success-rate", type=float, default=0.92)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--backoff-seconds", type=float, default=0.75)
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--circuit-breaker-errors", type=int, default=4)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.apply:
        print(json.dumps({
            "status": "blocked_requires_apply",
            "message": "This gate writes isolated live-pilot SQL rows and backup artifacts. Rerun with --apply only with explicit approval scope.",
            "authority_boundary": report_only_preview_boundary(),
        }, indent=2 if args.pretty else None, sort_keys=True))
        return 2
    packet = build_gate(args)
    print(json.dumps(packet, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if packet.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
