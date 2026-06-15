#!/usr/bin/env python3
"""Validate a WF78 scaleout batch against provider/runtime and SEC identity.

Report-only. This generalizes the old 101-200 validator so 201-300,
301-400, and 401-500 all use the same provider/source-open proof path.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf78_101_200_provider_source_validation as legacy_provider  # noqa: E402
from market_data_utils import atomic_write_json  # noqa: E402
from wf78_batch_manifest import (  # noqa: E402
    AUTHORITY_BOUNDARY,
    DEFAULT_MANIFEST,
    artifact_meta,
    batch_artifacts,
    batch_spec,
    load_dict,
    rel,
    sha256_file,
    symbol,
    utc_now,
)
from wf78_batch_source_selector import build_report as build_source_report  # noqa: E402

SCHEMA = "veritas.wf78_batch_provider_source_validation.v1"
SEC_TICKERS_URL = legacy_provider.SEC_TICKERS_URL

PROVIDER_AUTHORITY = {
    **AUTHORITY_BOUNDARY,
    "provider_runtime_probe_only": True,
    "official_source_open_validation_only": True,
}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def add_warning(warnings: list[dict[str, Any]], name: str, detail: Any) -> None:
    warnings.append({"name": name, "severity": "warning", "detail": detail})


def source_payload_for(batch: str) -> dict[str, Any]:
    spec = batch_spec(batch)
    payload = load_dict(spec.source_artifact)
    if payload:
        return payload
    return build_source_report(batch)


def provider_probe(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    provider_symbol = symbol(row.get("yfinance_symbol") or row.get("ticker"))
    if args.skip_provider_probe:
        return {
            "provider": "yahoo_chart",
            "provider_symbol": provider_symbol,
            "provider_status": "skipped",
            "attempt_count": 0,
            "latency_seconds": 0.0,
            "attempts": [],
            "data": {},
        }
    return legacy_provider.probe_provider(provider_symbol, args.timeout_seconds, args.retries, args.backoff_seconds, args.user_agent)


def build_candidate_row(row: dict[str, Any], sec_index: dict[str, dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    ticker = symbol(row.get("yfinance_symbol") or row.get("ticker"))
    provider = provider_probe(row, args)
    official = legacy_provider.official_validation(row, sec_index)
    provider_ok = provider.get("provider_status") == "ok"
    identity_complete = bool(ticker and row.get("name") and row.get("sector") and row.get("sec_cik"))
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
        "fundamental_source_reconciliation_matched": official.get("sec_cik_match") is True,
    }
    cleanup = legacy_provider.cleanup_required(provider_ok, official, identity_complete)
    blocking = [item for item in cleanup if item.get("severity") == "blocking"]
    pre_import_ready = not blocking
    return {
        "ticker": ticker,
        "source_symbol": symbol(row.get("source_symbol") or row.get("ticker")),
        "yfinance_symbol": symbol(row.get("yfinance_symbol") or row.get("ticker")),
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "sec_cik": row.get("sec_cik"),
        "batch_label": row.get("batch_label"),
        "target_rank": row.get("target_rank"),
        "scaleout_candidate_rank": row.get("scaleout_candidate_rank"),
        "identity_complete": identity_complete,
        "candidate_source": "wf78_scaleout_batch_manifest",
        "source_pool_rank": row.get("scaleout_candidate_rank"),
        "source_pool_sha256": sha256_file(batch_spec(str(row.get("batch_label"))).source_artifact) if row.get("batch_label") else None,
        "provider": provider.get("provider"),
        "provider_symbol": provider.get("provider_symbol"),
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
        "blocker_reason": "pre-import validation passed; still requires full card/fundamental/analyst/source-open build before promotion" if pre_import_ready else "; ".join(str(item.get("reason")) for item in blocking),
        "cleanup_required": cleanup,
        "authority_violations": [],
        "source_row": row,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = utc_now()
    spec = batch_spec(args.batch)
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    source = source_payload_for(args.batch)
    source_rows = [row for row in as_list(source.get("candidate_rows")) if isinstance(row, dict)]

    sec_index: dict[str, dict[str, Any]] = {}
    sec_meta: dict[str, Any] = {"artifact_type": "sec_company_tickers_map", "status": "skipped"}
    if args.skip_sec_fetch:
        add_warning(warnings, "sec_fetch_skipped", "SEC ticker-map validation skipped by argument; output is not import-ready.")
    else:
        sec_index, sec_meta = legacy_provider.sec_ticker_map(args.sec_timeout_seconds, args.user_agent)
    add_check(checks, "source_batch_count_100", len(source_rows) == 100, len(source_rows))
    add_check(checks, "sec_ticker_map_available", bool(sec_index) or args.skip_sec_fetch, sec_meta, "critical")

    started = time.perf_counter()
    rows = [build_candidate_row(row, sec_index, args) for row in source_rows]
    runtime_seconds = round(time.perf_counter() - started, 3)

    provider_ok = [row for row in rows if row.get("provider_runtime_present")]
    sec_match = [row for row in rows if row.get("sec_cik_match")]
    ready = [row for row in rows if row.get("source_open_ready")]
    blocked = [row for row in rows if not row.get("source_open_ready")]
    provider_success_rate = round(len(provider_ok) / len(rows), 4) if rows else 0.0
    sec_match_rate = round(len(sec_match) / len(rows), 4) if rows else 0.0
    ready_rate = round(len(ready) / len(rows), 4) if rows else 0.0

    if provider_success_rate < args.min_provider_success_rate and not args.skip_provider_probe:
        add_warning(warnings, "provider_success_rate_below_target", {"success_rate": provider_success_rate, "target": args.min_provider_success_rate})
    if blocked:
        add_warning(warnings, "candidate_repair_required_before_import_decision", {"blocked_count": len(blocked), "ready_count": len(ready)})
    add_check(checks, "candidate_rows_100", len(rows) == 100, len(rows))
    add_check(checks, "authority_review_only_true", PROVIDER_AUTHORITY.get("review_only") is True, PROVIDER_AUTHORITY)
    for flag, value in PROVIDER_AUTHORITY.items():
        if flag.endswith("_allowed") or flag == "owner_approval_inferred":
            add_check(checks, f"authority_{flag}_false", value is False, value)

    critical = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    status = "ok" if not critical else "blocked"
    readiness = "pre_import_source_validated" if rows and len(ready) == len(rows) else "repair_required"
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_batch_provider_source_validation",
        "status": status,
        "candidate_validation_status": readiness,
        "batch": {
            "batch_label": spec.batch_label,
            "rank_start": spec.rank_start,
            "rank_end": spec.rank_end,
            "candidate_rank_start": spec.candidate_rank_start,
            "candidate_rank_end": spec.candidate_rank_end,
            "artifacts": batch_artifacts(spec),
        },
        "authority_boundary": PROVIDER_AUTHORITY,
        "input_policy": {
            "batch_manifest": rel(DEFAULT_MANIFEST),
            "source_artifact": rel(spec.source_artifact),
            "provider": "yahoo_chart",
            "official_identity_source": SEC_TICKERS_URL,
            "minimum_provider_success_rate": args.min_provider_success_rate,
            "source_open_rule": "Provider and SEC identity proof are pre-import gates only; full ticker-card/fundamental/analyst/source-open validation remains required before promotion.",
        },
        "summary": {
            "selected_candidate_count": len(source_rows),
            "candidate_rows": len(rows),
            "provider_ok_count": len(provider_ok),
            "provider_error_count": len(rows) - len(provider_ok),
            "provider_success_rate": provider_success_rate,
            "sec_cik_match_count": len(sec_match),
            "sec_cik_match_rate": sec_match_rate,
            "pre_import_source_ready_count": len(ready),
            "blocked_or_repair_count": len(blocked),
            "pre_import_source_ready_rate": ready_rate,
            "runtime_seconds": runtime_seconds,
            "next_safe_action": "Use ready rows to prepare an owner-gated batch import decision packet; repair blocked rows before any apply.",
        },
        "candidate_rows": rows,
        "groups": {
            "pre_import_source_validated_owner_gated": [{"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"), "target_rank": row.get("target_rank")} for row in ready],
            "blocked_provider_or_official_source_repair": [{"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"), "blocker_reason": row.get("blocker_reason")} for row in blocked],
        },
        "source_artifacts": [
            artifact_meta(DEFAULT_MANIFEST, "wf78_scaleout_batch_manifest", True),
            artifact_meta(spec.source_artifact, "wf78_batch_source_selector", True),
            sec_meta,
        ],
        "validation": {
            "status": "ok" if not critical else "error",
            "checks": checks,
            "warnings": warnings,
            "errors": critical,
        },
        "stop_lines": [
            "No ticker import/apply from this validation.",
            "No production answer-path change.",
            "No SQL-first or SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner approval inference.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--sec-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--backoff-seconds", type=float, default=0.5)
    parser.add_argument("--min-provider-success-rate", type=float, default=0.9)
    parser.add_argument("--user-agent", default="Veritas OpenClaw Research veritasaiflows@gmail.com")
    parser.add_argument("--skip-provider-probe", action="store_true")
    parser.add_argument("--skip-sec-fetch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = batch_spec(args.batch)
    out = args.out_json or spec.provider_validation
    report = build_report(args)
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
    output_errors: list[str] = []
    if args.validate:
        if as_dict(report.get("validation")).get("errors"):
            output_errors.append("critical validation errors present")
        if args.write:
            loaded = load_dict(out)
            if loaded.get("schema") != SCHEMA:
                output_errors.append("written output schema mismatch")
    status = "blocked" if output_errors or report["status"] != "ok" else "ok"
    print(json.dumps({
        "status": status,
        "candidate_validation_status": report.get("candidate_validation_status"),
        "json_out": rel(out) if args.write else None,
        "summary": report.get("summary"),
        "output_validation_errors": output_errors,
    }, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
