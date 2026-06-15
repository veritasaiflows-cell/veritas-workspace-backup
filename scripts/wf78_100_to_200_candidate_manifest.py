#!/usr/bin/env python3
"""Build a report-only WF78 next-batch candidate manifest.

This is a planning and scoring surface for the next WF78 expansion step. It
reads existing artifacts only. It does not invent tickers, import/apply rows,
promote production answer paths, expand SQL canon authority, mutate canon or
portfolio state, infer owner approval, or authorize paper/live/account actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

DEFAULT_OUT_JSON = TMP / "wf78-100-to-200-candidate-manifest.json"
DEFAULT_OUT_DB = TMP / "wf78-100-to-200-candidate-manifest.sqlite"

UNIVERSE = DATA / "finance" / "universe-v1.json"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
SQL_READINESS_JSON = TMP / "wf78-sql-readiness-index.json"
SQL_READINESS_DB = TMP / "wf78-sql-readiness-index.sqlite"
SCOPE_PACKET = TMP / "wf78-100-ticker-candidate-scope-packet.json"
DESIGN_GATE = TMP / "sql-500-ticker-expansion-design-gate.json"
PROVIDER_PROOF = TMP / "wf78-100-ticker-provider-runtime-proof.json"
CLEANUP_QUEUE = TMP / "wf78-review-monitor-source-open-cleanup-queue.json"
PHASE4_PACKET = TMP / "wf78-phase4-recommendation-packet.json"
LIVE_PILOT_PREFLIGHT = TMP / "wf78-live-25-pilot-preflight.json"
LIVE_PILOT_IMPORT_GATE = TMP / "wf78-live-25-pilot-import-gate.json"
OFFICIAL_REGISTRY = DATA / "finance" / "wf78-source-open-official-registry.json"
COMPANY_IR = DATA / "fundamentals" / "company-ir-metadata.json"
SOURCE_REGISTRY = DATA / "finance" / "wf78-101-200-candidate-source-v1.json"

SCHEMA = "veritas.wf78_100_to_200_candidate_manifest.v1"
SUPPORTED_CURRENT_UNIVERSE_COUNTS = {100, 200, 300, 400, 500}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "report_only": True,
    "read_existing_artifacts_only": True,
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

REQUIRED_TRUE_FLAGS = {"report_only", "read_existing_artifacts_only"}
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


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_meta(path: Path, artifact_type: str, required: bool) -> dict[str, Any]:
    exists = path.exists()
    stat = path.stat() if exists else None
    payload: Any = None
    generated_at = None
    if exists and path.suffix.lower() == ".json":
        payload = load_json_artifact(path)
        generated_at = as_dict(payload).get("generated_at_utc")
    return {
        "artifact_type": artifact_type,
        "path": rel(path),
        "exists": exists,
        "required": required,
        "sha256": sha256_file(path) if exists else None,
        "size_bytes": stat.st_size if stat else None,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stat else None,
        "generated_at_utc": generated_at,
        "payload": payload,
    }


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def add_warning(warnings: list[dict[str, Any]], name: str, detail: Any) -> None:
    warnings.append({"name": name, "severity": "warning", "detail": detail})


def load_universe() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = load_json_artifact(UNIVERSE)
    data = payload if isinstance(payload, dict) else {}
    entries = [row for row in as_list(data.get("entries")) if isinstance(row, dict)]
    return data, entries


def source_symbols(row: dict[str, Any]) -> dict[str, Any]:
    return as_dict(row.get("source_symbols"))


def current_active_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in entries if row.get("active") is True and row.get("ticker")]


def current_tickers(entries: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("ticker")).upper() for row in current_active_entries(entries)}


def source_artifacts() -> list[dict[str, Any]]:
    return [
        artifact_meta(UNIVERSE, "current_universe_registry", True),
        artifact_meta(STATE_DB, "finance_intelligence_state_sqlite", True),
        artifact_meta(SQL_READINESS_JSON, "wf78_sql_readiness_index_json", True),
        artifact_meta(SQL_READINESS_DB, "wf78_sql_readiness_index_sqlite", False),
        artifact_meta(SCOPE_PACKET, "historical_42_to_100_candidate_scope_packet", True),
        artifact_meta(DESIGN_GATE, "sql_500_expansion_design_gate", True),
        artifact_meta(PROVIDER_PROOF, "wf78_100_provider_runtime_proof", False),
        artifact_meta(CLEANUP_QUEUE, "wf78_review_monitor_source_open_cleanup_queue", False),
        artifact_meta(PHASE4_PACKET, "wf78_phase4_recommendation_packet", False),
        artifact_meta(LIVE_PILOT_PREFLIGHT, "wf78_live_25_pilot_preflight", False),
        artifact_meta(LIVE_PILOT_IMPORT_GATE, "wf78_live_25_pilot_import_gate", False),
        artifact_meta(OFFICIAL_REGISTRY, "wf78_official_source_registry", False),
        artifact_meta(COMPANY_IR, "company_ir_metadata", False),
        artifact_meta(SOURCE_REGISTRY, "wf78_101_200_candidate_source_registry", True),
    ]


def state_db_snapshot(checks: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    snapshot: dict[str, Any] = {"exists": STATE_DB.exists(), "integrity_check": None, "tables": {}, "counts": {}}
    all_rows: dict[str, dict[str, Any]] = {}
    family_rows: dict[str, list[dict[str, Any]]] = {}
    if not STATE_DB.exists():
        add_check(checks, "state_db_exists", False, rel(STATE_DB))
        return all_rows, family_rows, snapshot

    with connect_ro(STATE_DB) as conn:
        integrity = scalar(conn, "PRAGMA integrity_check")
        snapshot["integrity_check"] = integrity
        add_check(checks, "state_db_integrity_ok", integrity == "ok", integrity)
        for table in ("all_ticker_sql_rows", "ticker_family_status", "fundamental_snapshot", "analyst_snapshot"):
            exists = bool(scalar(conn, "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?", (table,)))
            snapshot["tables"][table] = exists
            add_check(checks, f"{table}_exists", exists, table)
            if exists:
                snapshot["counts"][table] = scalar(conn, f"SELECT count(*) FROM {table}")

        if snapshot["tables"].get("all_ticker_sql_rows"):
            for row in rows(conn, "SELECT * FROM all_ticker_sql_rows"):
                all_rows[str(row.get("ticker", "")).upper()] = row
        if snapshot["tables"].get("ticker_family_status"):
            for row in rows(conn, "SELECT * FROM ticker_family_status"):
                family_rows.setdefault(str(row.get("ticker", "")).upper(), []).append(row)
    return all_rows, family_rows, snapshot


def readiness_by_ticker(readiness_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in as_list(readiness_payload.get("readiness_index")):
        if isinstance(row, dict) and row.get("ticker"):
            result[str(row["ticker"]).upper()] = row
    return result


def source_open_registry_tickers(payload: dict[str, Any]) -> set[str]:
    tickers = payload.get("tickers")
    if isinstance(tickers, dict):
        return {str(ticker).upper() for ticker in tickers.keys()}
    if isinstance(tickers, list):
        return {str(as_dict(row).get("ticker", "")).upper() for row in tickers if as_dict(row).get("ticker")}
    return set()


def company_ir_tickers(payload: dict[str, Any]) -> set[str]:
    tickers = as_dict(payload.get("tickers"))
    return {str(ticker).upper() for ticker in tickers.keys()}


def historical_scope_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for row in as_list(payload.get("proposed_new_candidates")):
        if isinstance(row, dict) and row.get("ticker"):
            candidates.append(row)
    return candidates


def runtime_tickers(payload: dict[str, Any]) -> set[str]:
    return {str(as_dict(row).get("ticker", "")).upper() for row in as_list(payload.get("rows")) if as_dict(row).get("ticker")}


def live_pilot_tickers(payload: dict[str, Any]) -> set[str]:
    tickers = set()
    for key in ("candidate_symbols", "tickers", "pilot_tickers"):
        value = payload.get(key)
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict) and row.get("ticker"):
                    tickers.add(str(row["ticker"]).upper())
                elif isinstance(row, str):
                    tickers.add(row.upper())
    return tickers


def registry_selected_candidates(payload: dict[str, Any], active_tickers: set[str]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in as_list(payload.get("selected_101_200")):
        if not isinstance(row, dict):
            continue
        normalized = str(row.get("yfinance_symbol") or row.get("ticker") or "").upper()
        raw_symbol = str(row.get("ticker") or row.get("source_symbol") or normalized).upper()
        if not normalized or normalized in seen or normalized in active_tickers:
            continue
        if not row.get("selected_for_101_200") or not row.get("eligible_for_101_200"):
            continue
        selected.append({**row, "manifest_ticker": normalized, "raw_source_symbol": raw_symbol})
        seen.add(normalized)
    return sorted(selected, key=lambda item: int(item.get("selected_rank") or 9999))


def score_current_row(
    universe_row: dict[str, Any],
    sql_row: dict[str, Any],
    families: list[dict[str, Any]],
    readiness: dict[str, Any],
    official_tickers: set[str],
    ir_tickers: set[str],
    runtime_ok: set[str],
) -> dict[str, Any]:
    ticker = str(universe_row.get("ticker", "")).upper()
    src = source_symbols(universe_row)
    identity_points = 0
    identity_points += 10 if ticker else 0
    identity_points += 10 if universe_row.get("name") else 0
    identity_points += 5 if universe_row.get("sector") else 0
    identity_points += 5 if universe_row.get("instrument_type") else 0
    official_points = 0
    official_points += 10 if src.get("company_ir") or ticker in ir_tickers else 0
    official_points += 10 if src.get("sec_cik") else 0
    official_points += 10 if ticker in official_tickers else 0
    family_good = sum(1 for row in families if str(row.get("status", "")).lower() in {"ok", "present", "complete", "fresh"})
    family_points = min(25, family_good)
    readiness_points = 0
    if readiness.get("source_open_ready"):
        readiness_points += 15
    if readiness.get("promotion_ready"):
        readiness_points += 10
    if ticker in runtime_ok:
        readiness_points += 10
    duplicate_penalty = 35
    score = max(0, min(100, identity_points + official_points + family_points + readiness_points - duplicate_penalty))
    return {
        "identity_points": identity_points,
        "official_source_points": official_points,
        "coverage_points": family_points,
        "readiness_points": readiness_points,
        "duplicate_or_current_penalty": duplicate_penalty,
        "score": score,
        "scoring_notes": [
            "Current universe members are not eligible as 101-200 expansion candidates.",
            "Score is retained for baseline/readiness comparison only.",
        ],
    }


def group_for_current(readiness: dict[str, Any], sql_row: dict[str, Any]) -> str:
    if sql_row.get("production_answer_path_member"):
        return "production_locked"
    if readiness.get("source_open_ready") or readiness.get("promotion_ready"):
        return "review_100_source_open_ready_owner_gated"
    return "needs_source_repair"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    artifacts = source_artifacts()
    artifact_by_type = {row["artifact_type"]: row for row in artifacts}

    if args.target_count <= 0 or args.batch_size <= 0:
        add_check(checks, "target_and_batch_positive", False, {"target_count": args.target_count, "batch_size": args.batch_size})
    else:
        add_check(checks, "target_and_batch_positive", True, {"target_count": args.target_count, "batch_size": args.batch_size})

    universe_payload, universe_entries = load_universe()
    active_entries = current_active_entries(universe_entries)
    active_tickers = current_tickers(universe_entries)
    duplicate_active_count = len(active_entries) - len(active_tickers)
    target_new_needed = max(0, args.target_count - len(active_tickers))
    target_already_satisfied = target_new_needed == 0
    add_check(checks, "universe_artifact_exists", UNIVERSE.exists(), rel(UNIVERSE))
    add_check(
        checks,
        "current_universe_count_supported_scaleout",
        len(active_entries) in SUPPORTED_CURRENT_UNIVERSE_COUNTS,
        {"actual": len(active_entries), "supported": sorted(SUPPORTED_CURRENT_UNIVERSE_COUNTS)},
    )
    add_check(checks, "current_universe_unique_tickers", duplicate_active_count == 0, {"active": len(active_entries), "unique": len(active_tickers)})
    add_check(
        checks,
        "target_exceeds_current_count_or_already_satisfied",
        args.target_count > len(active_entries) or target_already_satisfied,
        {"target_count": args.target_count, "current_count": len(active_entries), "target_already_satisfied": target_already_satisfied},
    )

    all_sql_rows, family_rows, state_snapshot = state_db_snapshot(checks)
    add_check(checks, "state_sql_rows_cover_current_universe", len(all_sql_rows) == len(active_tickers), {"sql_rows": len(all_sql_rows), "current_tickers": len(active_tickers)})

    readiness_payload = as_dict(artifact_by_type["wf78_sql_readiness_index_json"].get("payload"))
    readiness_map = readiness_by_ticker(readiness_payload)
    add_check(checks, "sql_readiness_index_covers_current_universe", len(readiness_map) == len(active_tickers), {"readiness_rows": len(readiness_map), "current_tickers": len(active_tickers)})

    scope_payload = as_dict(artifact_by_type["historical_42_to_100_candidate_scope_packet"].get("payload"))
    scope_candidates = historical_scope_candidates(scope_payload)
    scope_external = [row for row in scope_candidates if str(row.get("ticker", "")).upper() not in active_tickers]
    duplicate_scope = [row for row in scope_candidates if str(row.get("ticker", "")).upper() in active_tickers]
    source_registry_payload = as_dict(artifact_by_type["wf78_101_200_candidate_source_registry"].get("payload"))
    source_registry_candidates = registry_selected_candidates(source_registry_payload, active_tickers)

    official_tickers = source_open_registry_tickers(as_dict(artifact_by_type["wf78_official_source_registry"].get("payload")))
    ir_tickers = company_ir_tickers(as_dict(artifact_by_type["company_ir_metadata"].get("payload")))
    runtime_ok = runtime_tickers(as_dict(artifact_by_type["wf78_100_provider_runtime_proof"].get("payload")))
    live_pilot_overlap = live_pilot_tickers(as_dict(artifact_by_type["wf78_live_25_pilot_preflight"].get("payload"))) & active_tickers

    candidate_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = {
        "candidate_ready_for_200_manifest": [],
        "needs_source_repair": [],
        "defer_low_priority": [],
        "blocked_bad_or_missing_identity": [],
        "duplicate_or_already_present": [],
        "candidate_pool_insufficient": [],
        "production_locked": [],
        "review_100_source_open_ready_owner_gated": [],
    }

    for row in sorted(active_entries, key=lambda item: str(item.get("ticker", "")).upper()):
        ticker = str(row.get("ticker", "")).upper()
        sql_row = all_sql_rows.get(ticker, {})
        readiness = readiness_map.get(ticker, {})
        families = family_rows.get(ticker, [])
        group = group_for_current(readiness, sql_row)
        score = score_current_row(row, sql_row, families, readiness, official_tickers, ir_tickers, runtime_ok)
        source_symbol_map = source_symbols(row)
        manifest_row = {
            "ticker": ticker,
            "name": row.get("name") or sql_row.get("name"),
            "sector": row.get("sector") or sql_row.get("sector"),
            "industry": row.get("industry"),
            "tier": row.get("tier") or sql_row.get("tier"),
            "instrument_type": row.get("instrument_type") or sql_row.get("instrument_type"),
            "universe_scope": row.get("universe_scope") or sql_row.get("universe_scope"),
            "manifest_group": group,
            "candidate_source": "current_100_universe_baseline",
            "already_present": True,
            "eligible_for_100_to_200": False,
            "identity_complete": bool(ticker and (row.get("name") or sql_row.get("name"))),
            "sec_cik_present": bool(source_symbol_map.get("sec_cik")),
            "company_ir_present": bool(source_symbol_map.get("company_ir") or ticker in ir_tickers),
            "official_source_registry_present": ticker in official_tickers,
            "provider_runtime_present": ticker in runtime_ok,
            "source_open_ready": bool(readiness.get("source_open_ready")),
            "promotion_ready": bool(readiness.get("promotion_ready")),
            "blocker_reason": readiness.get("blocker_reason") or "already present in current 100 baseline",
            "score": score["score"],
            "raw_json": {
                "universe": row,
                "sql": sql_row,
                "readiness": readiness,
                "score": score,
            },
        }
        candidate_rows.append(manifest_row)
        score_rows.append({"ticker": ticker, "candidate_source": "current_100_universe_baseline", **score})
        groups.setdefault(group, []).append(
            {
                "ticker": ticker,
                "name": manifest_row["name"],
                "sector": manifest_row["sector"],
                "score": manifest_row["score"],
                "blocker_reason": manifest_row["blocker_reason"],
            }
        )

    for row in sorted(duplicate_scope, key=lambda item: str(item.get("ticker", "")).upper()):
        ticker = str(row.get("ticker", "")).upper()
        groups["duplicate_or_already_present"].append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "sector": row.get("sector"),
                "source": row.get("source"),
                "reason": "historical 42-to-100 candidate already exists in current 100 universe",
            }
        )

    for row in sorted(scope_external, key=lambda item: str(item.get("ticker", "")).upper()):
        ticker = str(row.get("ticker", "")).upper()
        candidate_rows.append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "tier": row.get("proposed_tier"),
                "instrument_type": "unknown",
                "universe_scope": "outside_current_100",
                "manifest_group": "candidate_ready_for_200_manifest",
                "candidate_source": "historical_scope_packet_external_residue",
                "already_present": False,
                "eligible_for_100_to_200": True,
                "identity_complete": bool(ticker and row.get("name")),
                "sec_cik_present": False,
                "company_ir_present": False,
                "official_source_registry_present": ticker in official_tickers,
                "provider_runtime_present": ticker in runtime_ok,
                "source_open_ready": False,
                "promotion_ready": False,
                "blocker_reason": "external historical candidate residue needs fresh source-open proof",
                "score": 25,
                "raw_json": {"source_candidate": row},
            }
        )
        groups["candidate_ready_for_200_manifest"].append({"ticker": ticker, "name": row.get("name"), "sector": row.get("sector"), "score": 25})

    for row in source_registry_candidates:
        ticker = str(row.get("manifest_ticker") or row.get("ticker", "")).upper()
        score = int(row.get("score") or 0)
        manifest_row = {
            "ticker": ticker,
            "name": row.get("name"),
            "sector": row.get("sector"),
            "industry": row.get("industry"),
            "tier": "candidate_review",
            "instrument_type": "equity",
            "universe_scope": "outside_current_100",
            "manifest_group": "candidate_ready_for_200_manifest",
            "candidate_source": "wf78_101_200_candidate_source_registry",
            "already_present": False,
            "eligible_for_100_to_200": True,
            "identity_complete": bool(ticker and row.get("name") and row.get("sector") and row.get("sec_cik")),
            "sec_cik_present": bool(row.get("sec_cik")),
            "company_ir_present": False,
            "official_source_registry_present": False,
            "provider_runtime_present": False,
            "source_open_ready": False,
            "promotion_ready": False,
            "blocker_reason": "source-registry seed only; needs provider/runtime, official-source, source-open, and card validation before any import or promotion",
            "score": score,
            "raw_json": {"source_registry_candidate": row},
        }
        candidate_rows.append(manifest_row)
        score_rows.append(
            {
                "ticker": ticker,
                "candidate_source": "wf78_101_200_candidate_source_registry",
                "identity_points": 30 if manifest_row["identity_complete"] else 10,
                "official_source_points": 10 if row.get("sec_cik") else 0,
                "coverage_points": 0,
                "readiness_points": 0,
                "duplicate_or_current_penalty": 0,
                "score": score,
                "scoring_notes": [
                    "Selected by durable WF78 101-200 S&P 500 source registry.",
                    "Review-only seed; no import/apply/promotion authority.",
                    "Provider/runtime and official-source validation remain required.",
                ],
            }
        )
        groups["candidate_ready_for_200_manifest"].append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "sector": row.get("sector"),
                "score": score,
                "source": "wf78_101_200_candidate_source_registry",
                "selected_rank": row.get("selected_rank"),
            }
        )

    available_external_count = len(scope_external) + len(source_registry_candidates)
    missing_candidate_count = max(0, target_new_needed - available_external_count)
    if missing_candidate_count:
        insufficiency = {
            "needed_new_candidates": target_new_needed,
            "available_external_candidates": available_external_count,
            "missing_new_candidates": missing_candidate_count,
            "reason": "Insufficient durable out-of-universe candidate source rows are available.",
            "next_required_decision": "Provide or approve additional source rows before any wider 100-to-200 manifest can be populated.",
        }
        groups["candidate_pool_insufficient"].append(insufficiency)
        add_warning(warnings, "candidate_pool_insufficient", insufficiency)

    if not scope_candidates and available_external_count == 0:
        add_check(checks, "candidate_source_artifact_present", False, "No historical, registry, or external candidate artifact found")
    else:
        add_check(
            checks,
            "candidate_source_artifact_present",
            True,
            {
                "historical_scope_candidates": len(scope_candidates),
                "source_registry_candidates": len(source_registry_candidates),
                "external_candidates": available_external_count,
            },
        )

    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    critical_failures = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    validation_status = "ok" if not critical_failures else "error"
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in candidate_rows if row.get("candidate_source") == "current_100_universe_baseline")
    group_counts = {name: len(items) for name, items in groups.items()}
    group_counts["new_100_to_200_candidates_available"] = available_external_count
    group_counts["new_100_to_200_candidates_needed"] = target_new_needed
    group_counts["live_pilot_evidence_overlap_current_100"] = len(live_pilot_overlap)

    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_100_to_200_candidate_manifest",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input_policy": {
            "target_count": args.target_count,
            "batch_size": args.batch_size,
            "default_outputs": {
                "json": rel(args.out_json),
                "sqlite": rel(args.out_db),
            },
            "candidate_source_rule": "Use existing durable candidate/universe artifacts only; do not invent or hardcode new tickers.",
            "durable_101_200_source_registry": rel(SOURCE_REGISTRY),
            "markdown_output": False,
        },
        "summary": {
            "current_universe_count": len(active_tickers),
            "target_count": args.target_count,
            "requested_batch_size": args.batch_size,
            "needed_new_candidate_count": target_new_needed,
            "available_candidate_count": available_external_count,
            "ready_count": len(groups["candidate_ready_for_200_manifest"]),
            "repair_count": len(groups["needs_source_repair"]),
            "defer_count": len(groups["defer_low_priority"]),
            "blocked_identity_count": len(groups["blocked_bad_or_missing_identity"]),
            "duplicate_count": len(groups["duplicate_or_already_present"]),
            "missing_artifacts": [row["path"] for row in artifacts if row["required"] and not row["exists"]],
            "validation_result": validation_status,
            "candidate_pool_status": "insufficient" if missing_candidate_count else "available",
            "next_safe_action": "Run provider/runtime, official-source, source-open, and card validation for the selected 101-200 seed before any expansion/import decision.",
        },
        "current_baseline": {
            "production_locked": len(groups["production_locked"]),
            "review_100_source_open_ready_owner_gated": len(groups["review_100_source_open_ready_owner_gated"]),
            "review_100_blocked_or_repair": len(groups["needs_source_repair"]),
            "sector_counts": dict(sorted(sector_counts.items())),
            "state_db_snapshot": state_snapshot,
        },
        "groups": groups,
        "group_counts": group_counts,
        "candidate_manifest": candidate_rows,
        "candidate_scores": score_rows,
        "source_artifacts": [
            {key: value for key, value in row.items() if key != "payload"}
            for row in artifacts
        ],
        "validation": {
            "status": validation_status,
            "checks": checks,
            "warnings": warnings,
            "errors": [row for row in checks if not row["ok"]],
        },
        "stop_lines": [
            "No invented 101-200 ticker list.",
            "No ticker import/apply.",
            "No production answer-path change.",
            "No SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner approval inference.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
        ],
    }
    return report


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS candidate_manifest;
        DROP TABLE IF EXISTS candidate_scores;
        DROP TABLE IF EXISTS source_artifacts;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE candidate_manifest (
            ticker TEXT NOT NULL,
            candidate_source TEXT NOT NULL,
            name TEXT,
            sector TEXT,
            industry TEXT,
            tier TEXT,
            instrument_type TEXT,
            universe_scope TEXT,
            manifest_group TEXT NOT NULL,
            already_present INTEGER NOT NULL CHECK (already_present IN (0,1)),
            eligible_for_100_to_200 INTEGER NOT NULL CHECK (eligible_for_100_to_200 IN (0,1)),
            identity_complete INTEGER NOT NULL CHECK (identity_complete IN (0,1)),
            sec_cik_present INTEGER NOT NULL CHECK (sec_cik_present IN (0,1)),
            company_ir_present INTEGER NOT NULL CHECK (company_ir_present IN (0,1)),
            official_source_registry_present INTEGER NOT NULL CHECK (official_source_registry_present IN (0,1)),
            provider_runtime_present INTEGER NOT NULL CHECK (provider_runtime_present IN (0,1)),
            source_open_ready INTEGER NOT NULL CHECK (source_open_ready IN (0,1)),
            promotion_ready INTEGER NOT NULL CHECK (promotion_ready IN (0,1)),
            blocker_reason TEXT,
            score INTEGER NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (ticker, candidate_source)
        ) STRICT;

        CREATE TABLE candidate_scores (
            ticker TEXT NOT NULL,
            candidate_source TEXT NOT NULL,
            identity_points INTEGER NOT NULL,
            official_source_points INTEGER NOT NULL,
            coverage_points INTEGER NOT NULL,
            readiness_points INTEGER NOT NULL,
            duplicate_or_current_penalty INTEGER NOT NULL,
            score INTEGER NOT NULL,
            scoring_notes_json TEXT NOT NULL,
            PRIMARY KEY (ticker, candidate_source)
        ) STRICT;

        CREATE TABLE source_artifacts (
            artifact_type TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            artifact_exists INTEGER NOT NULL CHECK (artifact_exists IN (0,1)),
            required INTEGER NOT NULL CHECK (required IN (0,1)),
            sha256 TEXT,
            size_bytes INTEGER,
            generated_at_utc TEXT,
            mtime_utc TEXT
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
        for row in as_list(report.get("candidate_manifest")):
            conn.execute(
                """
                INSERT INTO candidate_manifest (
                    ticker, candidate_source, name, sector, industry, tier, instrument_type,
                    universe_scope, manifest_group, already_present, eligible_for_100_to_200,
                    identity_complete, sec_cik_present, company_ir_present,
                    official_source_registry_present, provider_runtime_present, source_open_ready,
                    promotion_ready, blocker_reason, score, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("ticker"),
                    row.get("candidate_source"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("industry"),
                    row.get("tier"),
                    row.get("instrument_type"),
                    row.get("universe_scope"),
                    row.get("manifest_group"),
                    int_bool(row.get("already_present")),
                    int_bool(row.get("eligible_for_100_to_200")),
                    int_bool(row.get("identity_complete")),
                    int_bool(row.get("sec_cik_present")),
                    int_bool(row.get("company_ir_present")),
                    int_bool(row.get("official_source_registry_present")),
                    int_bool(row.get("provider_runtime_present")),
                    int_bool(row.get("source_open_ready")),
                    int_bool(row.get("promotion_ready")),
                    row.get("blocker_reason"),
                    int(row.get("score") or 0),
                    json_text(row.get("raw_json")),
                ),
            )
        for row in as_list(report.get("candidate_scores")):
            conn.execute(
                """
                INSERT INTO candidate_scores (
                    ticker, candidate_source, identity_points, official_source_points,
                    coverage_points, readiness_points, duplicate_or_current_penalty,
                    score, scoring_notes_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("ticker"),
                    row.get("candidate_source"),
                    int(row.get("identity_points") or 0),
                    int(row.get("official_source_points") or 0),
                    int(row.get("coverage_points") or 0),
                    int(row.get("readiness_points") or 0),
                    int(row.get("duplicate_or_current_penalty") or 0),
                    int(row.get("score") or 0),
                    json_text(row.get("scoring_notes")),
                ),
            )
        for row in as_list(report.get("source_artifacts")):
            conn.execute(
                """
                INSERT INTO source_artifacts (
                    artifact_type, path, artifact_exists, required, sha256, size_bytes,
                    generated_at_utc, mtime_utc
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("artifact_type"),
                    row.get("path"),
                    int_bool(row.get("exists")),
                    int_bool(row.get("required")),
                    row.get("sha256"),
                    row.get("size_bytes"),
                    row.get("generated_at_utc"),
                    row.get("mtime_utc"),
                ),
            )
        for flag, value in as_dict(report.get("authority_boundary")).items():
            if flag in REQUIRED_TRUE_FLAGS:
                required = True
            elif flag in REQUIRED_FALSE_FLAGS:
                required = False
            else:
                required = bool(value)
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
            "workflow": report.get("workflow"),
            "artifact_type": report.get("artifact_type"),
            "validation_status": as_dict(report.get("validation")).get("status"),
            "current_universe_count": as_dict(report.get("summary")).get("current_universe_count"),
            "target_count": as_dict(report.get("summary")).get("target_count"),
            "available_candidate_count": as_dict(report.get("summary")).get("available_candidate_count"),
            "candidate_pool_status": as_dict(report.get("summary")).get("candidate_pool_status"),
        }.items():
            conn.execute("INSERT INTO meta (key, value) VALUES (?,?)", (str(key), json_text(value)))
        conn.commit()


def validate_outputs(report: dict[str, Any], args: argparse.Namespace) -> tuple[str, list[str]]:
    errors: list[str] = []
    if args.write:
        if not args.out_json.exists():
            errors.append(f"missing JSON output: {rel(args.out_json)}")
        else:
            loaded = load_json_artifact(args.out_json)
            if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
                errors.append("JSON output schema mismatch")
        if not args.out_db.exists():
            errors.append(f"missing SQLite output: {rel(args.out_db)}")
        else:
            with connect_ro(args.out_db) as conn:
                integrity = scalar(conn, "PRAGMA integrity_check")
                if integrity != "ok":
                    errors.append(f"SQLite integrity_check={integrity}")
                table_rows = rows(conn, "PRAGMA table_list")
                strict_tables = {
                    row["name"]
                    for row in table_rows
                    if row.get("type") == "table" and row.get("schema") == "main" and row.get("strict") == 1
                }
                required = {"candidate_manifest", "candidate_scores", "source_artifacts", "authority_boundary", "validation_results", "meta"}
                missing = sorted(required - strict_tables)
                if missing:
                    errors.append(f"SQLite missing STRICT tables: {missing}")
                unsafe = scalar(conn, "SELECT count(*) FROM authority_boundary WHERE ok=0")
                if unsafe:
                    errors.append(f"unsafe authority rows: {unsafe}")
                manifest_rows = scalar(conn, "SELECT count(*) FROM candidate_manifest")
                expected = len(as_list(report.get("candidate_manifest")))
                if manifest_rows != expected:
                    errors.append(f"candidate_manifest rows {manifest_rows} != expected {expected}")
    return ("ok" if not errors else "error"), errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write JSON and SQLite proof artifacts.")
    parser.add_argument("--validate", action="store_true", help="Validate report and outputs.")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--target-count", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=100)
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
    output_validation_status = "not_run"
    output_validation_errors: list[str] = []
    if args.validate:
        output_validation_status, output_validation_errors = validate_outputs(report, args)
    status = as_dict(report.get("validation")).get("status")
    if output_validation_errors:
        status = "error"
    result = {
        "status": status,
        "validation_result": as_dict(report.get("validation")).get("status"),
        "output_validation_result": output_validation_status,
        "output_validation_errors": output_validation_errors,
        "json_out": rel(args.out_json) if args.write else None,
        "db_out": rel(args.out_db) if args.write else None,
        "summary": report.get("summary"),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
