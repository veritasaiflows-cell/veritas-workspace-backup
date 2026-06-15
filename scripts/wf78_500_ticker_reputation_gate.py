#!/usr/bin/env python3
"""Build a review-only WF78 500-ticker reputation and batch gate.

This gate makes WF78 scaleout repeatable before any import or promotion path.
It reads existing WF78 source/validation artifacts, scores candidate reputation,
creates deterministic 100-name batch lanes, and emits repair/next-action queues.

It does not import/apply tickers, promote production answer paths, expand SQL
canon/cache authority, mutate canon or portfolio state, infer owner approval, or
authorize customer/external, paper/live, brokerage/account, or money actions.
"""
from __future__ import annotations

import argparse
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
import wf78_batch_manifest

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

SOURCE_REGISTRY = DATA / "finance" / "wf78-101-200-candidate-source-v1.json"
IMPORT_DECISION = TMP / "wf78-101-200-import-decision-packet.json"
PROVIDER_VALIDATION = TMP / "wf78-101-200-provider-source-validation.json"
MANIFEST = TMP / "wf78-100-to-200-candidate-manifest.json"
READINESS_INDEX = TMP / "wf78-sql-readiness-index.json"
PHASE_RUNNER = TMP / "wf78-phase-runner-current.json"

DEFAULT_OUT_JSON = TMP / "wf78-500-ticker-reputation-gate.json"
DEFAULT_OUT_DB = TMP / "wf78-500-ticker-reputation-gate.sqlite"
SCHEMA = "veritas.wf78_500_ticker_reputation_gate.v1"

TARGET_COUNT = 500
BATCH_SIZE = 100

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "read_existing_artifacts_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_first_promotion_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "read_existing_artifacts_only"}
REQUIRED_FALSE_FLAGS = {
    "ticker_import_allowed",
    "apply_allowed",
    "promotion_allowed",
    "production_answer_path_change_allowed",
    "sql_first_promotion_allowed",
    "sql_canon_expansion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
}

TIER_C_REQUIRED = [
    "identity",
    "sector",
    "sec_cik",
    "source_url",
    "source_hash",
    "provider_runtime",
    "sec_cik_match",
    "source_open",
]
TIER_B_REQUIRED = [
    "ticker_card",
    "fundamentals",
    "analyst_layer",
    "valuation_layer",
    "technical_layer",
    "official_source_evidence",
]
TIER_A_REQUIRED = [
    "entry_stop_band_context",
    "source_open_answer_contract",
    "production_answer_path_qa",
    "owner_approval",
]


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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def symbol(value: Any) -> str:
    return str(value or "").upper().replace(".", "-")


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def artifact_meta(path: Path, artifact_type: str, required: bool) -> dict[str, Any]:
    payload = load_dict(path) if path.suffix.lower() == ".json" and path.exists() else {}
    stat = path.stat() if path.exists() else None
    return {
        "artifact_type": artifact_type,
        "path": rel(path),
        "exists": path.exists(),
        "required": required,
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "size_bytes": stat.st_size if stat else None,
    }


def source_artifacts() -> list[dict[str, Any]]:
    artifacts = [
        artifact_meta(wf78_batch_manifest.DEFAULT_MANIFEST, "wf78_scaleout_batch_manifest", True),
        artifact_meta(SOURCE_REGISTRY, "wf78_101_200_candidate_source_registry", True),
        artifact_meta(IMPORT_DECISION, "wf78_101_200_import_decision_packet", True),
        artifact_meta(PROVIDER_VALIDATION, "wf78_101_200_provider_source_validation", True),
        artifact_meta(MANIFEST, "wf78_100_to_200_candidate_manifest", True),
        artifact_meta(READINESS_INDEX, "wf78_sql_readiness_index", True),
        artifact_meta(PHASE_RUNNER, "wf78_phase_runner_current", False),
    ]
    try:
        for spec in wf78_batch_manifest.batch_specs():
            artifacts.extend(
                [
                    artifact_meta(spec.source_artifact, f"wf78_batch_{spec.batch_label}_source", False),
                    artifact_meta(spec.provider_validation, f"wf78_batch_{spec.batch_label}_provider_validation", False),
                    artifact_meta(spec.owner_decision_packet, f"wf78_batch_{spec.batch_label}_owner_decision_packet", False),
                    artifact_meta(spec.import_gate, f"wf78_batch_{spec.batch_label}_import_gate", False),
                ]
            )
    except Exception:
        pass
    return artifacts


def provider_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        symbol(row.get("ticker")): row
        for row in as_list(payload.get("candidate_rows"))
        if isinstance(row, dict) and row.get("ticker")
    }


def import_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        symbol(row.get("ticker")): row
        for row in as_list(payload.get("candidate_rows"))
        if isinstance(row, dict) and row.get("ticker")
    }


def readiness_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        symbol(row.get("ticker")): row
        for row in as_list(payload.get("readiness_index"))
        if isinstance(row, dict) and row.get("ticker")
    }


def current_universe_rows(readiness: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, row in readiness.items():
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "sector": row.get("sector"),
                "candidate_group": "current_baseline",
                "already_in_current_100": True,
                "already_in_current_universe": True,
                "identity_complete": bool(ticker and row.get("name") and row.get("sector")),
                "sec_cik": None,
                "source_url": row.get("source_artifact_path"),
                "source_sha256": row.get("source_artifact_sha256"),
                "selected_rank": None,
                "score": None,
                "readiness": row,
            }
        )
    return rows


def reputation_score(row: dict[str, Any], provider: dict[str, Any], decision: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    missing: list[str] = []
    repair: list[str] = []
    score = 0

    if row.get("identity_complete") and row.get("ticker") and row.get("name"):
        score += 20
    else:
        missing.append("identity")
        repair.append("repair identity/name/sector")
    if row.get("sector"):
        score += 5
    else:
        missing.append("sector")
    if row.get("sec_cik") or decision.get("sec_cik"):
        score += 15
    else:
        missing.append("sec_cik")
        repair.append("add SEC CIK identity")
    if row.get("source_url"):
        score += 10
    else:
        missing.append("source_url")
    if row.get("source_sha256"):
        score += 10
    else:
        missing.append("source_hash")
    if provider.get("provider_runtime_present") is True or decision.get("provider_runtime_present") is True:
        score += 15
    else:
        missing.append("provider_runtime")
        repair.append("run provider/runtime validation")
    if provider.get("sec_cik_match") is True or decision.get("sec_cik_match") is True:
        score += 10
    else:
        missing.append("sec_cik_match")
        repair.append("validate SEC CIK/provider identity match")
    if provider.get("source_open_ready") is True or decision.get("source_open_ready") is True:
        score += 10
    else:
        missing.append("source_open")
        repair.append("build source-open proof")
    if row.get("already_in_current_universe") or row.get("already_in_current_100"):
        score = max(0, score - 25)
        return min(score, 100), sorted(set(missing)), []

    missing.extend(TIER_B_REQUIRED)
    missing.extend(TIER_A_REQUIRED)
    return min(score, 100), sorted(set(missing)), sorted(set(repair))


def tier_and_action(row: dict[str, Any], score: int, missing: list[str], batch_index: int, next_import_batch_index: int, next_import_batch_label: str) -> tuple[str, str, bool, bool]:
    tier_c_missing = [item for item in TIER_C_REQUIRED if item in missing]
    tier_b_missing = [item for item in TIER_B_REQUIRED if item in missing]
    tier_a_missing = [item for item in TIER_A_REQUIRED if item in missing]
    if row.get("already_in_current_universe") or row.get("already_in_current_100"):
        return "current_baseline", "baseline only; do not re-import", False, False
    if not tier_c_missing and score >= 75 and batch_index == next_import_batch_index:
        return "tier_c_monitor_candidate", f"owner-gated {next_import_batch_label} Tier C review-monitor decision packet", True, False
    if not tier_c_missing and score >= 75:
        return "future_tier_c_candidate_waiting_for_prior_batch", "hold behind earlier scaleout batch; refresh validation before any future import decision", False, False
    if tier_b_missing or tier_a_missing:
        return "tier_c_only_not_decision_grade", "repair Tier C gaps first; then enrich for Tier B/Tier A separately", False, False
    return "repair_required", "repair identity/source/provider gaps before batch eligibility", False, False


def batch_provider_rows(specs: list[wf78_batch_manifest.BatchSpec]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in specs:
        payload = load_dict(spec.provider_validation)
        for ticker, row in provider_by_ticker(payload).items():
            enriched = dict(row)
            enriched["batch_label"] = spec.batch_label
            rows[ticker] = enriched
    return rows


def batch_decision_rows(specs: list[wf78_batch_manifest.BatchSpec]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in specs:
        payload = load_dict(spec.owner_decision_packet)
        for ticker, row in import_by_ticker(payload).items():
            enriched = dict(row)
            enriched["batch_label"] = spec.batch_label
            rows[ticker] = enriched
    return rows


def spec_for_candidate_rank(specs: list[wf78_batch_manifest.BatchSpec], rank: int) -> tuple[int, wf78_batch_manifest.BatchSpec] | None:
    for index, spec in enumerate(specs, start=2):
        if spec.candidate_rank_start <= rank <= spec.candidate_rank_end:
            return index, spec
    return None


def next_import_spec_index(specs: list[wf78_batch_manifest.BatchSpec], source_registry: dict[str, Any], active: set[str]) -> int:
    for index, spec in enumerate(specs, start=2):
        rows = wf78_batch_manifest.batch_candidates(spec, source_registry, active)
        tickers = {symbol(row.get("yfinance_symbol") or row.get("ticker")) for row in rows}
        if tickers and not tickers.issubset(active):
            return index
    return 0


def candidate_rows(source_registry: dict[str, Any], provider_payload: dict[str, Any], decision_payload: dict[str, Any], readiness_payload: dict[str, Any]) -> list[dict[str, Any]]:
    specs = wf78_batch_manifest.batch_specs()
    provider = {**provider_by_ticker(provider_payload), **batch_provider_rows(specs)}
    decision = {**import_by_ticker(decision_payload), **batch_decision_rows(specs)}
    readiness = readiness_by_ticker(readiness_payload)
    active = wf78_batch_manifest.active_universe_tickers()
    scaleout_rows = wf78_batch_manifest.ordered_scaleout_candidates(source_registry)

    # Preserve current rows for baseline, then use source order for deterministic future batches.
    # Dedupe by ticker so already-imported batches do not reappear as future candidates.
    current_rows = current_universe_rows(readiness)
    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_row in current_rows + scaleout_rows:
        ticker = symbol(source_row.get("yfinance_symbol") or source_row.get("ticker"))
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        combined.append(source_row)

    rows: list[dict[str, Any]] = []
    new_rank = 0
    current_count = len(current_rows)
    next_import_batch_index = next_import_spec_index(specs, source_registry, active)
    next_import_batch_label = next((spec.batch_label for index, spec in enumerate(specs, start=2) if index == next_import_batch_index), "next_unavailable_batch")
    for row in combined:
        ticker = symbol(row.get("yfinance_symbol") or row.get("ticker"))
        if not ticker:
            continue
        is_current = bool(row.get("already_in_current_universe") or row.get("already_in_current_100"))
        if is_current:
            batch_index = 1
            batch_label = f"current_{current_count}_baseline"
        else:
            new_rank = int(row.get("scaleout_candidate_rank") or (new_rank + 1))
            match = spec_for_candidate_rank(specs, new_rank)
            if not match:
                continue
            batch_index, spec = match
            batch_label = spec.batch_label
        score, missing, repair = reputation_score(row, provider.get(ticker, {}), decision.get(ticker, {}))
        tier, next_action, import_eligible, promotion_eligible = tier_and_action(row, score, missing, batch_index, next_import_batch_index, next_import_batch_label)
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "candidate_group": row.get("candidate_group") or ("current_baseline" if is_current else "eligible_pool"),
                "current_or_target_batch": batch_label,
                "batch_index": batch_index,
                "candidate_rank_for_500": None if is_current else new_rank,
                "current_tier": tier,
                "reputation_score": score,
                "identity_complete": bool(row.get("identity_complete")),
                "sec_cik": row.get("sec_cik") or decision.get(ticker, {}).get("sec_cik"),
                "source_open_status": "ready" if "source_open" not in missing else "missing_or_unvalidated",
                "provider_status": provider.get(ticker, {}).get("provider_status") or decision.get(ticker, {}).get("provider_status") or "not_validated_for_this_batch",
                "freshness_status": "batch_proof_current" if provider.get(ticker) or decision.get(ticker) else "future_batch_needs_fresh_validation",
                "missing_evidence_families": missing,
                "repair_queue": repair,
                "tier_c_import_review_eligible": import_eligible,
                "tier_b_research_eligible": False,
                "tier_a_production_eligible": promotion_eligible,
                "next_action": next_action,
                "authority_flags": AUTHORITY_BOUNDARY,
            }
        )
    return rows[:TARGET_COUNT]


def batch_plan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    current_count = len([row for row in rows if row["batch_index"] == 1])
    for batch_index in range(1, 6):
        batch_rows = [row for row in rows if row["batch_index"] == batch_index]
        eligible = [row for row in batch_rows if row["tier_c_import_review_eligible"]]
        repairs = [row for row in batch_rows if row["repair_queue"] and not row["tier_c_import_review_eligible"]]
        label = f"current {current_count} baseline" if batch_index == 1 else (batch_rows[0]["current_or_target_batch"] if batch_rows else f"future batch {batch_index}")
        if batch_index == 1:
            action = "protect production 42 and current review-monitor breadth; use as no-regression baseline"
        elif batch_index == 2 and len(eligible) == BATCH_SIZE:
            action = "prepare exact owner decision packet for Tier C review-monitor import; no apply without approval"
        else:
            action = "run provider/source-open validation and regenerate this gate before any import decision"
        plan.append(
            {
                "batch_index": batch_index,
                "batch_label": label,
                "row_count": len(batch_rows),
                "tier_c_import_review_eligible_count": len(eligible),
                "repair_or_validation_required_count": len(repairs),
                "average_reputation_score": round(sum(int(row["reputation_score"]) for row in batch_rows) / len(batch_rows), 2) if batch_rows else 0,
                "sector_counts": dict(sorted(Counter(str(row.get("sector") or "Unknown") for row in batch_rows).items())),
                "next_action": action,
            }
        )
    return plan


def build_report(_: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source_registry = load_dict(SOURCE_REGISTRY)
    decision = load_dict(IMPORT_DECISION)
    provider = load_dict(PROVIDER_VALIDATION)
    readiness = load_dict(READINESS_INDEX)
    runner = load_dict(PHASE_RUNNER)
    artifacts = source_artifacts()

    for item in artifacts:
        add_check(checks, f"{item['artifact_type']}_exists", item["exists"] or not item["required"], item)
    rows = candidate_rows(source_registry, provider, decision, readiness)
    batches = batch_plan(rows)
    repair_rows = [row for row in rows if row["repair_queue"]]
    current_baseline_rows = [row for row in rows if row["batch_index"] == 1]
    next_batch_rows = [row for row in rows if row["batch_index"] == 2]
    future_rows = [row for row in rows if row["batch_index"] > 2]
    future_repair_rows = [row for row in future_rows if row["repair_queue"]]
    future_hold_rows = [row for row in future_rows if not row["repair_queue"] and not row["tier_c_import_review_eligible"]]
    eligible_next_batch = [row for row in next_batch_rows if row["tier_c_import_review_eligible"]]
    next_batch_label = next_batch_rows[0]["current_or_target_batch"] if next_batch_rows else "next_unavailable_batch"

    add_check(checks, "source_registry_status_ok", source_registry.get("status") == "ok", source_registry.get("status"))
    add_check(checks, "provider_validation_status_ok", provider.get("status") == "ok", provider.get("status"))
    add_check(checks, "import_decision_status_present", decision.get("status") in {"decision_required", "approved_tier_c_review_monitor_only"}, decision.get("status"))
    add_check(checks, "readiness_index_status_ok", as_dict(readiness.get("validation")).get("status") == "ok", as_dict(readiness.get("validation")).get("status"))
    add_check(checks, "gate_has_500_rows", len(rows) == TARGET_COUNT, len(rows))
    add_check(checks, "current_baseline_present_supported", len(current_baseline_rows) in {100, 200, 300, 400, 500}, batches[0])
    add_check(checks, "next_batch_not_auto_imported_without_fresh_validation", len(eligible_next_batch) in {0, 100}, {"next_batch": next_batch_label, "eligible": len(eligible_next_batch)})
    add_check(checks, "future_batches_not_import_eligible_until_prior_batch", all(row["tier_c_import_review_eligible"] is False for row in future_rows), len(future_rows))
    add_check(checks, "phase_runner_no_apply_if_present", not runner or as_dict(runner.get("summary")).get("apply_or_import_executed") is False, as_dict(runner.get("summary")))
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    critical = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    status = "ok" if not critical else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_500_ticker_reputation_gate",
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "target_count": TARGET_COUNT,
            "row_count": len(rows),
            "batch_size": BATCH_SIZE,
            "current_baseline_count": len(current_baseline_rows),
            "current_100_count": len(current_baseline_rows),
            "next_batch_label": next_batch_label,
            "next_batch_tier_c_eligible_count": len(eligible_next_batch),
            "next_101_200_tier_c_eligible_count": 0 if len(current_baseline_rows) >= 200 else len(eligible_next_batch),
            "future_validation_required_count": len(future_repair_rows),
            "future_prior_batch_hold_count": len(future_hold_rows),
            "tier_b_research_eligible_count": len([row for row in rows if row["tier_b_research_eligible"]]),
            "tier_a_production_eligible_count": len([row for row in rows if row["tier_a_production_eligible"]]),
            "repair_queue_count": len(repair_rows),
            "status": status,
            "next_safe_action": "Use this gate as the repeated WF78 scaleout step; refresh proof, validate the next 100-name batch, then create an exact owner decision packet before any apply/import.",
        },
        "batch_plan": batches,
        "candidate_rows": rows,
        "repair_queue": [
            {
                "ticker": row["ticker"],
                "batch_index": row["batch_index"],
                "current_or_target_batch": row["current_or_target_batch"],
                "missing_evidence_families": row["missing_evidence_families"],
                "repair_queue": row["repair_queue"],
                "next_action": row["next_action"],
            }
            for row in repair_rows
        ],
        "source_artifacts": artifacts,
        "validation": {
            "status": "ok" if not critical else "error",
            "checks": checks,
            "errors": critical,
            "warnings": [],
        },
        "repeatable_sequence": [
            "run wf78_phase_runner.py --phase all-safe --write --validate",
            "run wf78_500_ticker_reputation_gate.py --write --write-db --validate",
            "if the next batch is clean, produce exact owner decision packet",
            "only after owner approval, use a scoped apply gate for Tier C review-monitor import",
            "post-apply: rerun phase runner, reputation gate, hardening, PM state, and cockpit validation",
        ],
        "stop_lines": [
            "No ticker import/apply.",
            "No production answer-path promotion.",
            "No SQL-first promotion or SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
            "No owner approval inference from a clean reputation gate.",
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
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS reputation_candidates;
        DROP TABLE IF EXISTS batch_plan;
        DROP TABLE IF EXISTS repair_queue;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE reputation_candidates (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            candidate_group TEXT NOT NULL,
            batch_index INTEGER NOT NULL,
            current_or_target_batch TEXT NOT NULL,
            current_tier TEXT NOT NULL,
            reputation_score INTEGER NOT NULL,
            source_open_status TEXT NOT NULL,
            provider_status TEXT NOT NULL,
            freshness_status TEXT NOT NULL,
            tier_c_import_review_eligible INTEGER NOT NULL CHECK (tier_c_import_review_eligible IN (0,1)),
            tier_b_research_eligible INTEGER NOT NULL CHECK (tier_b_research_eligible IN (0,1)),
            tier_a_production_eligible INTEGER NOT NULL CHECK (tier_a_production_eligible IN (0,1)),
            next_action TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE batch_plan (
            batch_index INTEGER PRIMARY KEY,
            batch_label TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            tier_c_import_review_eligible_count INTEGER NOT NULL,
            repair_or_validation_required_count INTEGER NOT NULL,
            average_reputation_score REAL NOT NULL,
            next_action TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE repair_queue (
            ticker TEXT NOT NULL,
            batch_index INTEGER NOT NULL,
            current_or_target_batch TEXT NOT NULL,
            missing_evidence_families_json TEXT NOT NULL,
            repair_queue_json TEXT NOT NULL,
            next_action TEXT NOT NULL,
            PRIMARY KEY (ticker, batch_index)
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
                INSERT INTO reputation_candidates (
                    ticker, name, sector, candidate_group, batch_index, current_or_target_batch,
                    current_tier, reputation_score, source_open_status, provider_status, freshness_status,
                    tier_c_import_review_eligible, tier_b_research_eligible, tier_a_production_eligible,
                    next_action, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("ticker"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("candidate_group"),
                    row.get("batch_index"),
                    row.get("current_or_target_batch"),
                    row.get("current_tier"),
                    int(row.get("reputation_score") or 0),
                    row.get("source_open_status"),
                    row.get("provider_status"),
                    row.get("freshness_status"),
                    int_bool(row.get("tier_c_import_review_eligible")),
                    int_bool(row.get("tier_b_research_eligible")),
                    int_bool(row.get("tier_a_production_eligible")),
                    row.get("next_action"),
                    json_text(row),
                ),
            )
        for row in as_list(report.get("batch_plan")):
            conn.execute(
                "INSERT INTO batch_plan VALUES (?,?,?,?,?,?,?,?)",
                (
                    row.get("batch_index"),
                    row.get("batch_label"),
                    row.get("row_count"),
                    row.get("tier_c_import_review_eligible_count"),
                    row.get("repair_or_validation_required_count"),
                    row.get("average_reputation_score"),
                    row.get("next_action"),
                    json_text(row),
                ),
            )
        for row in as_list(report.get("repair_queue")):
            conn.execute(
                "INSERT INTO repair_queue VALUES (?,?,?,?,?,?)",
                (
                    row.get("ticker"),
                    row.get("batch_index"),
                    row.get("current_or_target_batch"),
                    json_text(row.get("missing_evidence_families")),
                    json_text(row.get("repair_queue")),
                    row.get("next_action"),
                ),
            )
        for flag, value in as_dict(report.get("authority_boundary")).items():
            required = True if flag in REQUIRED_TRUE_FLAGS else False if flag in REQUIRED_FALSE_FLAGS else bool(value)
            conn.execute("INSERT INTO authority_boundary VALUES (?,?,?,?)", (flag, int_bool(value), int_bool(required), int_bool(bool(value) == required)))
        for row in as_list(as_dict(report.get("validation")).get("checks")):
            conn.execute("INSERT INTO validation_results VALUES (?,?,?,?,?)", (row.get("name"), row.get("status"), int_bool(row.get("ok")), row.get("severity"), json_text(row.get("detail"))))
        for key, value in {
            "schema": report.get("schema"),
            "generated_at_utc": report.get("generated_at_utc"),
            "status": report.get("status"),
            "summary": report.get("summary"),
        }.items():
            conn.execute("INSERT INTO meta VALUES (?,?)", (str(key), json_text(value)))
        conn.commit()


def validate_outputs(args: argparse.Namespace, report: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    if as_dict(report.get("validation")).get("errors"):
        errors.append("critical validation errors present")
    if args.write:
        loaded = load_json_artifact(args.out_json)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("JSON output missing or schema mismatch")
        if not args.out_db.exists():
            errors.append("SQLite output missing")
        else:
            with connect_ro(args.out_db) as conn:
                if scalar(conn, "PRAGMA integrity_check") != "ok":
                    errors.append("SQLite integrity_check failed")
                strict = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_list")
                    if row["schema"] == "main" and row["type"] == "table" and row["strict"] == 1
                }
                required = {"reputation_candidates", "batch_plan", "repair_queue", "authority_boundary", "validation_results", "meta"}
                missing = sorted(required - strict)
                if missing:
                    errors.append(f"missing STRICT tables: {missing}")
                if scalar(conn, "SELECT count(*) FROM authority_boundary WHERE ok=0"):
                    errors.append("unsafe authority rows present")
                if scalar(conn, "SELECT count(*) FROM reputation_candidates") != len(as_list(report.get("candidate_rows"))):
                    errors.append("candidate row count mismatch")
    return "ok" if not errors else "error", errors


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_json = resolve(args.out_json)
    args.out_db = resolve(args.out_db)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out_json, report, ensure_ascii=False)
    if args.write_db:
        write_sqlite(report, args.out_db)
    output_status = "not_run"
    output_errors: list[str] = []
    if args.validate:
        output_status, output_errors = validate_outputs(args, report)
    status = report["status"]
    if output_errors:
        status = "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "validation_result": as_dict(report.get("validation")).get("status"),
                "output_validation_result": output_status,
                "output_validation_errors": output_errors,
                "json_out": rel(args.out_json) if args.write else None,
                "db_out": rel(args.out_db) if args.write_db else None,
                "summary": report.get("summary"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
