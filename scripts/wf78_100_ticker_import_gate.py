#!/usr/bin/env python3
"""WF78 guarded 100-ticker review-monitor import gate.

This gate promotes the approved 58-name WF78 candidate scope into the durable
universe registry as review-only Tier C monitor rows. It keeps the production
42 answer path locked, creates backup/rollback proof, probes provider runtime,
and emits validation artifacts. It does not write ticker cards for the new
names, expand SQL-canon/cache authority, mutate portfolio/canon notes, infer
owner approval for capital action, or authorize paper/live execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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

from finance_universe_validator import (  # noqa: E402
    AUTHORITY_BOUNDARY as UNIVERSE_AUTHORITY_BOUNDARY,
    REVIEW_100_SCOPE,
    data_requirements_for,
    monitoring_cadence_for,
)
from market_data_utils import atomic_write_json, load_json_artifact  # noqa: E402
from finance_production_scope import production_tickers as production_scope_tickers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"
BACKUP_ROOT = ROOT / "backups" / "wf78-100-review-monitor-import"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
CANDIDATE_PACKET = TMP / "wf78-100-ticker-candidate-scope-packet.json"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
PRODUCTION_CARD_DIR = TMP / "ticker-intelligence-cards"
OUT_JSON = TMP / "wf78-100-ticker-import-gate.json"
OUT_MD = TMP / "wf78-100-ticker-import-gate.md"
PROVIDER_PROOF_OUT = TMP / "wf78-100-ticker-provider-runtime-proof.json"

PRODUCTION_SCOPE = "strategic_production_grade"
EXPECTED_PRODUCTION_COUNT = 42
EXPECTED_REVIEW_100_COUNT = 58
EXPECTED_TOTAL_COUNT = 100
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

AUTHORITY_BOUNDARY = {
    "posture": "guarded_review_only_100_ticker_monitor_import",
    "ticker_import_performed": True,
    "ticker_universe_write_allowed_by_this_gate": True,
    "review_only_thin_monitor_rows_only": True,
    "owner_approval_scope": "local_review_only_universe_monitor_import_not_capital_action",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "owner_approval_granted_for_capital_action": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "sql_canon_migration_allowed": False,
    "canon_cache_write_allowed": False,
    "sql_first_consumer_migration_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "customer_or_retail_sql_output_allowed": False,
    "db_path_migration_allowed": False,
    "tmp_artifact_promotion_allowed": False,
    "production_answer_path_overwrite_allowed": False,
}


def report_only_preview_boundary() -> dict[str, Any]:
    boundary = dict(AUTHORITY_BOUNDARY)
    boundary["report_only_preview"] = True
    boundary["ticker_import_performed"] = False
    boundary["ticker_universe_write_allowed_by_this_gate"] = False
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
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_text(value: Any) -> str:
    return hashlib.sha256(json_text(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def production_card_hashes() -> dict[str, str | None]:
    return {path.name: sha256_file(path) for path in sorted(PRODUCTION_CARD_DIR.glob("*.current.json"))}


def backup_inputs(run_id: str, candidate_hash: str) -> dict[str, Any]:
    backup_dir = BACKUP_ROOT / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for path in [UNIVERSE_PATH, STATE_DB, CANDIDATE_PACKET]:
        if not path.exists():
            copied.append({"source": rel(path), "exists": False})
            continue
        target = backup_dir / path.name
        if path.suffix.lower() == ".sqlite":
            import sqlite3

            with sqlite3.connect(str(path)) as source, sqlite3.connect(str(target)) as dest:
                source.backup(dest)
        else:
            shutil.copy2(path, target)
        copied.append({"source": rel(path), "backup": rel(target), "sha256": sha256_file(target), "bytes": target.stat().st_size})
    manifest = {
        "schema_version": 1,
        "artifact_type": "wf78_100_review_monitor_backup_manifest",
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "candidate_list_sha256": candidate_hash,
        "backup_dir": rel(backup_dir),
        "copied": copied,
        "production_ticker_card_hashes": [{"path": rel(path), "sha256": sha256_file(path)} for path in sorted(PRODUCTION_CARD_DIR.glob("*.current.json"))],
        "rollback_route": [
            "restore data/finance/universe-v1.json from this backup manifest",
            "restore tmp/finance-intelligence-state.sqlite from this backup if rebuilt state must be rolled back",
            "rerun finance_universe_validator, finance_data_coverage, finance_intelligence_state, router QA, artifact index, and harness validators",
            "do not delete historical proof without a separate lifecycle/archive approval",
        ],
    }
    atomic_write_json(backup_dir / "manifest.json", manifest)
    return manifest


def candidate_rows() -> list[dict[str, Any]]:
    packet = load_dict(CANDIDATE_PACKET)
    rows = packet.get("proposed_new_candidates")
    if not isinstance(rows, list):
        return []
    return sorted([row for row in rows if isinstance(row, dict) and row.get("ticker")], key=lambda row: str(row["ticker"]).upper())


def universe_entries(universe: dict[str, Any]) -> list[dict[str, Any]]:
    rows = universe.get("entries")
    return rows if isinstance(rows, list) else []


def production_tickers(entries: list[dict[str, Any]]) -> set[str]:
    migrated = set(production_scope_tickers())
    if migrated:
        return migrated
    return {
        str(row.get("ticker") or "").upper()
        for row in entries
        if row.get("active") is True and row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE
    }


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


def probe_symbol(row: dict[str, Any], retries: int, backoff_seconds: float, timeout: float) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
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
                    "source_open_required": True,
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
        "source_open_required": True,
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
            results.append({"ticker": ticker, "status": "skipped_circuit_open", "provider": "yahoo_chart", "latency_seconds": 0, "attempt_count": 0, "attempts": [], "data": {}, "source_open_required": True})
            continue
        result = probe_symbol(row, args.retries, args.backoff_seconds, args.timeout_seconds)
        results.append(result)
        consecutive_errors = consecutive_errors + 1 if result["status"] != "ok" else 0
    total_runtime = round(time.perf_counter() - started, 3)
    ok_rows = [row for row in results if row.get("status") == "ok"]
    error_rows = [row for row in results if row.get("status") != "ok"]
    max_latency = max((float(row.get("latency_seconds") or 0) for row in results), default=0.0)
    avg_latency = round(sum(float(row.get("latency_seconds") or 0) for row in results) / len(results), 3) if results else 0.0
    success_rate = round(len(ok_rows) / len(results), 4) if results else 0.0
    proof = {
        "schema_version": 1,
        "artifact_type": "wf78_100_ticker_provider_runtime_proof",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ok" if success_rate >= args.min_success_rate and total_runtime <= args.runtime_budget_seconds else "blocked",
        "review_only": True,
        "authority_boundary": report_only_preview_boundary() if getattr(args, "provider_proof_only", False) else AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(candidates),
            "ok_count": len(ok_rows),
            "error_count": len(error_rows),
            "success_rate": success_rate,
            "total_runtime_seconds": total_runtime,
            "avg_latency_seconds": avg_latency,
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
            "source_open_required_before_material_finance_claims": True,
        },
        "rows": results,
    }
    atomic_write_json(PROVIDER_PROOF_OUT, proof)
    return proof


def infer_industry(row: dict[str, Any]) -> str | None:
    theme = str(row.get("theme") or "").lower()
    sector = str(row.get("sector") or "")
    if "semiconductor" in theme or "memory" in theme:
        return "Semiconductors"
    if "software" in theme or "cloud" in theme or "cyber" in theme or "developer" in theme:
        return "Software"
    if "payments" in theme:
        return "Payments"
    if "utility" in theme or sector == "Utilities":
        return "Utilities"
    if "defense" in theme or "aerospace" in theme:
        return "Aerospace & Defense"
    if "health" in sector.lower() or "medtech" in theme or "biotech" in theme:
        return "Health Care"
    if "copper" in theme or "steel" in theme or "chemicals" in theme:
        return "Materials"
    return None


def review_100_entry(row: dict[str, Any], provider_row: dict[str, Any]) -> dict[str, Any]:
    ticker = str(row["ticker"]).upper()
    return {
        "ticker": ticker,
        "name": row.get("name") or ticker,
        "universe_scope": REVIEW_100_SCOPE,
        "production_scope": False,
        "pilot_scope": False,
        "review_100_scope": True,
        "review_100_status": "thin_monitor_imported_review_only",
        "instrument_type": "operating_company",
        "source_symbols": {"yfinance": ticker, "sec_cik": None, "company_ir": None},
        "active": True,
        "tier": "C",
        "monitoring_role": "review_100_thin_monitor",
        "sector": row.get("sector"),
        "industry": infer_industry(row),
        "coverage_reason": {
            "wf77_current_coverage": False,
            "wf78_100_review_monitor": True,
            "production_answer_path_member": False,
            "candidate_scope_packet": rel(CANDIDATE_PACKET),
            "candidate_source": row.get("source"),
            "provider_status": provider_row.get("status"),
        },
        "decision_grade_eligible": False,
        "promotion_required_before_action": True,
        "monitoring_cadence": monitoring_cadence_for("C"),
        "data_requirements": data_requirements_for("C", "operating_company"),
        "promotion_triggers": [
            "provider_runtime_budget_passes",
            "fresh_price_technical_and_source_open_evidence_available",
            "sector_or_relative_strength_improves",
            "owner_promotes_from_review_monitor_to_priority_watch",
        ],
        "demotion_triggers": [
            "provider_runtime_or_error_budget_fails",
            "source_freshness_or_validator_status_blocks_claims",
            "thesis_evidence_deteriorates_or_conflicts_with_canon",
            "owner_removes_from_review_monitor_scope",
        ],
        "source_open_required": True,
        "authority_boundary": UNIVERSE_AUTHORITY_BOUNDARY,
    }


def promote_universe(candidates: list[dict[str, Any]], provider_proof: dict[str, Any]) -> dict[str, Any]:
    universe = load_dict(UNIVERSE_PATH)
    entries = universe_entries(universe)
    production = production_tickers(entries)
    provider_rows = {str(row.get("ticker") or "").upper(): row for row in provider_proof.get("rows", []) if isinstance(row, dict)}
    candidate_tickers = {str(row.get("ticker") or "").upper() for row in candidates}
    retained = [
        row for row in entries
        if isinstance(row, dict)
        and str(row.get("ticker") or "").upper() not in candidate_tickers
        and row.get("universe_scope") != "pilot_fixture"
    ]
    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        if ticker in production:
            continue
        retained.append(review_100_entry(row, provider_rows.get(ticker, {})))
    universe["entries"] = sorted(retained, key=lambda row: (0 if row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE else 1, str(row.get("ticker") or "")))
    universe["generated_at_utc"] = utc_now()
    universe["status"] = "phase5_review_100_monitor_ready"
    universe["review_only"] = True
    universe["authority_boundary"] = UNIVERSE_AUTHORITY_BOUNDARY
    universe.setdefault("architecture_boundary", {})
    universe["architecture_boundary"].update({
        "markdown_owner_notes_remain_approved_canon": True,
        "json_artifacts_remain_proof_review_packets": True,
        "sqlite_remains_validated_routing_current_state_cache": True,
        "full_sql_canon_migration_allowed": False,
        "tmp_artifact_promotion_allowed": False,
        "db_path_migration_allowed": False,
    })
    atomic_write_json(UNIVERSE_PATH, universe)
    return universe


def run_command(args: list[str], label: str, timeout: int = 300) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "label": label,
        "command": "python " + " ".join(args),
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout.strip()[-3000:],
        "stderr_tail": completed.stderr.strip()[-3000:],
    }


def validate_packet(
    candidates: list[dict[str, Any]],
    provider: dict[str, Any],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    universe: dict[str, Any],
    validation_commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any, severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    entries = universe_entries(universe)
    production = [row for row in entries if row.get("active") is True and row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE]
    review_rows = [row for row in entries if row.get("active") is True and row.get("universe_scope") == REVIEW_100_SCOPE]
    candidate_tickers = [str(row.get("ticker") or "").upper() for row in candidates]
    review_tickers = [str(row.get("ticker") or "").upper() for row in review_rows]
    provider_summary = provider.get("summary") or {}
    add("candidate_count_58", len(candidates) == EXPECTED_REVIEW_100_COUNT, {"actual": len(candidates), "expected": EXPECTED_REVIEW_100_COUNT})
    add("candidate_symbols_unique", len(candidate_tickers) == len(set(candidate_tickers)), {"count": len(candidate_tickers), "unique": len(set(candidate_tickers))})
    add("provider_runtime_ok_for_58", provider.get("status") == "ok" and provider_summary.get("candidate_count") == EXPECTED_REVIEW_100_COUNT, provider_summary)
    add("production_scope_locked_42", len(production) == EXPECTED_PRODUCTION_COUNT, {"production": len(production)})
    add("review_100_monitor_rows_58", len(review_rows) == EXPECTED_REVIEW_100_COUNT, {"review_100": len(review_rows)})
    add("active_total_100", len([row for row in entries if row.get("active") is True]) == EXPECTED_TOTAL_COUNT, {"active": len([row for row in entries if row.get("active") is True])})
    add("review_100_matches_candidate_scope", sorted(review_tickers) == sorted(candidate_tickers), {"missing": sorted(set(candidate_tickers) - set(review_tickers)), "extra": sorted(set(review_tickers) - set(candidate_tickers))})
    bad_review_rows = [
        row.get("ticker")
        for row in review_rows
        if row.get("tier") != "C" or row.get("decision_grade_eligible") is not False or row.get("production_scope") is True
    ]
    add("review_100_rows_thin_c_tier_only", not bad_review_rows, bad_review_rows)
    add("production_card_hashes_unchanged", before_hashes == after_hashes, {"before_count": len(before_hashes), "after_count": len(after_hashes)})
    add("post_import_validators_ok", all(item.get("ok") for item in validation_commands), [{"label": item.get("label"), "ok": item.get("ok"), "returncode": item.get("returncode")} for item in validation_commands])
    return checks


def write_markdown(packet: dict[str, Any]) -> None:
    summary = packet.get("summary") or {}
    lines = [
        "# WF78 100-Ticker Review Monitor Import Gate",
        "",
        f"Status: `{packet.get('status')}`",
        "",
        "This gate promotes the 58-name candidate scope into review-only Tier C monitor rows. It preserves the production 42 answer path and grants no canon, portfolio, customer, paper, live, or account authority.",
        "",
        "## Summary",
        "",
        f"- Production rows: {summary.get('production_count')}",
        f"- Review-100 monitor rows: {summary.get('review_100_count')}",
        f"- Active total: {summary.get('active_total_count')}",
        f"- Provider success rate: {summary.get('provider_success_rate')}",
        f"- Candidate hash: `{packet.get('candidate_list_sha256')}`",
        "",
        "## Validation",
        "",
    ]
    for check in packet.get("checks", []):
        marker = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"- {marker} `{check.get('name')}`: {check.get('detail')}")
    lines.extend(["", "## Stop Lines", ""])
    lines.extend(f"- {line}" for line in packet.get("stop_lines", []))
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_gate(args: argparse.Namespace) -> dict[str, Any]:
    candidates = candidate_rows()
    candidate_hash = sha256_text([{"ticker": row.get("ticker"), "name": row.get("name"), "sector": row.get("sector"), "source": row.get("source")} for row in candidates])
    run_id = f"wf78-100-review-monitor-import-{stamp()}"
    before_hashes = production_card_hashes()
    backup = backup_inputs(run_id, candidate_hash)
    provider = provider_probe(candidates, args)
    universe = promote_universe(candidates, provider)
    validation_commands = [
        run_command(["scripts/finance_universe_validator.py", "--validate"], "finance_universe_validator", timeout=180),
        run_command(["scripts/finance_data_coverage.py", "--write"], "finance_data_coverage", timeout=240),
        run_command(["scripts/finance_intelligence_state.py", "build"], "finance_intelligence_state_build", timeout=240),
        run_command(["scripts/finance_intelligence_state.py", "validate"], "finance_intelligence_state_validate", timeout=180),
        run_command(["scripts/finance_intelligence_state.py", "phase3-qc"], "finance_intelligence_state_phase3_qc", timeout=240),
        run_command(["scripts/finance_intelligence_router_qa.py", "--out", "tmp/finance-intelligence-router-qa-wf78-100-review.json", "--pretty"], "finance_intelligence_router_qa_wf78_100_review", timeout=300),
    ]
    after_hashes = production_card_hashes()
    checks = validate_packet(candidates, provider, before_hashes, after_hashes, load_dict(UNIVERSE_PATH), validation_commands)
    failed = [check for check in checks if not check["ok"] and check.get("severity", "error") == "error"]
    entries = universe_entries(load_dict(UNIVERSE_PATH))
    review_rows = [row for row in entries if row.get("active") is True and row.get("universe_scope") == REVIEW_100_SCOPE]
    production = [row for row in entries if row.get("active") is True and row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE]
    packet = {
        "schema_version": 1,
        "artifact_type": "wf78_100_ticker_review_monitor_import_gate",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ok" if not failed else "blocked",
        "review_only": True,
        "owner_approval_reference": args.owner_approval_reference,
        "candidate_list_sha256": candidate_hash,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "production_count": len(production),
            "review_100_count": len(review_rows),
            "active_total_count": len([row for row in entries if row.get("active") is True]),
            "provider_success_rate": (provider.get("summary") or {}).get("success_rate"),
            "provider_ok_count": (provider.get("summary") or {}).get("ok_count"),
            "provider_error_count": (provider.get("summary") or {}).get("error_count"),
            "production_card_hash_count": len(after_hashes),
        },
        "candidate_tickers": [str(row.get("ticker") or "").upper() for row in candidates],
        "backup_manifest": backup,
        "provider_runtime_proof": rel(PROVIDER_PROOF_OUT),
        "post_import_validation_commands": validation_commands,
        "checks": checks,
        "failed_checks": failed,
        "stop_lines": [
            "Review-100 rows are thin Tier C monitor metadata only.",
            "Production 42 answer path remains the only ticker-card/current-state production surface.",
            "No ticker card registry write for new review-100 names.",
            "No SQL-canon/cache authority expansion.",
            "No customer/retail SQL output or external delivery authority.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner approval inference for capital action.",
            "No paper/live/brokerage/account action or money movement.",
        ],
    }
    atomic_write_json(OUT_JSON, packet)
    write_markdown(packet)
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Required to write the review-only 100-monitor universe rows.")
    parser.add_argument("--provider-proof-only", action="store_true", help="Refresh provider-runtime proof without importing or mutating universe rows.")
    parser.add_argument("--owner-approval-reference", default="", help="Exact owner approval reference for this local review-only universe monitor import.")
    parser.add_argument("--runtime-budget-seconds", type=float, default=240.0)
    parser.add_argument("--min-success-rate", type=float, default=0.92)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--backoff-seconds", type=float, default=0.75)
    parser.add_argument("--timeout-seconds", type=float, default=12.0)
    parser.add_argument("--circuit-breaker-errors", type=int, default=6)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true", help="Compatibility validation flag; gate validation is built into provider/apply paths.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.provider_proof_only:
        proof = provider_probe(candidate_rows(), args)
        print(json.dumps({
            "status": proof.get("status"),
            "provider_runtime_proof": rel(PROVIDER_PROOF_OUT),
            "summary": proof.get("summary"),
            "authority_boundary": proof.get("authority_boundary"),
            "validation_requested": bool(args.validate),
        }, indent=2 if args.pretty else None, sort_keys=True))
        return 0 if proof.get("status") == "ok" else 1
    if not args.apply:
        print(json.dumps({
            "status": "blocked_requires_apply",
            "message": "Rerun with --apply and an owner approval reference for this local review-only universe monitor import.",
            "authority_boundary": report_only_preview_boundary(),
        }, indent=2 if args.pretty else None, sort_keys=True))
        return 2
    if not args.owner_approval_reference.strip():
        raise SystemExit("--owner-approval-reference is required")
    packet = build_gate(args)
    print(json.dumps(packet, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if packet.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())


