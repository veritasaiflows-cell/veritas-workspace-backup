#!/usr/bin/env python3
"""WF78 review-only finance intelligence state and query packet surface.

Builds a compact SQL current-state/query layer for the current WF78 universe.
This is routing/review infrastructure only. It does not replace Markdown canon,
promote tmp databases, infer owner approval, or authorize paper/live execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_sql_canon_access import (
    FinanceSqlCanonAccess,
    ReferenceLevelRecord,
    strategic_answer_route_context,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

# Derived SQL proof DB only. The refresh path rebuilds tmp/finance-intelligence-state.sqlite
# from source artifacts; rollback is to rerun the previous validated sources or restore the
# tmp artifact from normal workspace backup, never to promote this DB as canon.
DEFAULT_DB = TMP / "finance-intelligence-state.sqlite"
CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_VALIDATION = TMP / "finance-intelligence-state-validation.json"
DEFAULT_TICKER_PACKET = TMP / "finance-intelligence-state-ticker-packet.json"
DEFAULT_PREOPEN_PACKET = TMP / "finance-intelligence-state-preopen-packet.json"
DEFAULT_STALE_PACKET = TMP / "finance-intelligence-state-stale-tickers.json"
DEFAULT_PENDING_PACKET = TMP / "finance-intelligence-state-pending-approvals.json"
DEFAULT_VALIDATOR_PACKET = TMP / "finance-intelligence-state-validator-status.json"
DEFAULT_SOURCE_PROOF_PACKET = TMP / "finance-intelligence-state-source-proof.json"
DEFAULT_ENTRY_STOP_PACKET = TMP / "finance-intelligence-state-entry-stop-refs.json"
DEFAULT_ACTION_QUEUE_PACKET = TMP / "finance-intelligence-state-action-queue.json"
DEFAULT_PHASE3_QC = TMP / "finance-intelligence-state-phase3-qc.json"
DEFAULT_PAPER_POSITIONS_PACKET = TMP / "finance-intelligence-state-paper-positions.json"
DEFAULT_PILOT_FIXTURE_PACKET = TMP / "finance-intelligence-state-pilot-fixtures.json"
DEFAULT_LIVE_PILOT_PACKET = TMP / "finance-intelligence-state-live-pilot.json"
DEFAULT_REFRESH_100_PACKET = TMP / "finance-intelligence-state-refresh-100.json"

EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
COVERAGE_PATH = TMP / "finance-data-coverage-current.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
FULL_ANSWER_PARITY_DIR = TMP / "full-answer-parity"
FULL_ANSWER_PARITY_ROLLUP = FULL_ANSWER_PARITY_DIR / "full-answer-parity-rollup.json"
TRADE_GRADE_FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"
TRADE_GRADE_FULL_ANSWER_ROLLUP = TMP / "trade-grade-full-answer-assembler.json"
ROUTER_QA_PATH = TMP / "finance-intelligence-router-qa-sql-canon-archive-apply.json"
WF78_AUTO_TIER_ROUTING = TMP / "wf78-auto-tier-routing.json"
TIER_A_COVERAGE_GATE = TMP / "tier-a-trade-grade-coverage-gate.json"
PAPER_POSITION_DB = TMP / "wf67-paper-position-state.sqlite"
LEGACY_42_TIER_SHADOW_DB = TMP / "wf78-legacy-42-tier-state-shadow.sqlite"
CANONICAL_FINANCE_DATA_PLANE_DB = TMP / "canonical-finance-data-plane.sqlite"
CANONICAL_FINANCE_DATA_PLANE_PHASE = TMP / "canonical-finance-data-plane-phase6-10.json"

SCHEMA_VERSION = 2
EXPECTED_STRICT_PRODUCTION_TICKERS = 0
SUPPORTED_ACTIVE_TICKER_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}
SUPPORTED_CURRENT_SCOPE_COUNTS = SUPPORTED_ACTIVE_TICKER_COUNTS | SUPPORTED_REVIEW_MONITOR_COUNTS
ACTIVE_INTERNAL_SCOPE = "active_internal_universe"
PRODUCTION_SCOPE = "strategic_production_grade"
REVIEW_100_SCOPE = "review_100_monitor"
SUPPORTED_UNIVERSE_SCOPES = {ACTIVE_INTERNAL_SCOPE, PRODUCTION_SCOPE, REVIEW_100_SCOPE}
PILOT_SCOPE = "pilot_fixture"
ENTRY_STOP_REFERENCE_METADATA_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_level_source_timestamp",
    "reference_level_source_sha256",
    "reference_level_owner_source_path",
)
ENTRY_STOP_REFERENCE_METADATA_AUTHORITY_BOUNDARY = (
    "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority"
)
ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS = {
    "display_reference_only": True,
    "fallback_required": True,
    "recommendation_allowed": False,
    "deployment_or_action_state_change_allowed": False,
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
}
AUTHORITY_FALSE_KEYS = {
    "canonical_note_mutation_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "sizing_apply_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "live_trade_allowed",
    "live_brokerage_or_account_action_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed_by_card",
    "paper_order_cancel_allowed_by_card",
    "paper_order_submit_allowed_by_this_registry",
    "paper_order_cancel_allowed_by_this_registry",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    data = load_json_artifact(path)
    return default if data is None else data


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stale_tier_a_packet_tickers(router: dict[str, Any]) -> set[str]:
    summary = as_dict(router.get("summary"))
    tickers = {
        str(ticker).upper()
        for ticker in as_list(summary.get("tier_a_stale_packet_tickers"))
        if str(ticker).strip()
    }
    if tickers:
        return tickers
    return {
        str(row.get("ticker") or "").upper()
        for row in as_list(router.get("rows"))
        if isinstance(row, dict)
        and row.get("tier_a_packet_freshness_status") == "stale"
        and str(row.get("ticker") or "").strip()
    }


def suppress_stale_packet_approval_language(
    ticker: str,
    reco: dict[str, Any],
    blockers: list[Any],
    stale_packet_tickers: set[str],
    decision_grade_allowed_count: int,
) -> tuple[dict[str, Any], list[Any]]:
    posture_key = str(reco.get("posture_key") or "")
    if (
        ticker.upper() not in stale_packet_tickers
        or decision_grade_allowed_count != 0
        or posture_key not in {"approval_ready_if_fresh", "promotion_review", "deployable_now"}
    ):
        return reco, blockers
    updated = dict(reco)
    updated["prior_posture"] = reco.get("posture")
    updated["prior_posture_key"] = posture_key
    updated["posture"] = "stale final-promotion packet ignored; monitor only until regenerated"
    updated["posture_key"] = "stale_packet_monitor_only"
    updated["actionability"] = "not_decision_grade"
    updated["support_level"] = "stale_packet_ignored"
    updated["stale_packet_approval_language_suppressed"] = True
    updated["decision_grade_allowed_count_at_suppression"] = decision_grade_allowed_count
    return updated, sorted(set([*blockers, "stale_final_promotion_packet_ignored"]))


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_json_text(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return [] if default is None else default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value if default is None else default


def write_packet(path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    atomic_write_json(path, packet)
    return packet


def packet_header(artifact_type: str, db_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": artifact_type,
        "db_path": rel(db_path),
        "authority_boundary": authority_boundary(),
        "answer_contract": {
            "sql_is_routing_and_current_state_only": True,
            "material_finance_claim_requires_source_open": True,
            "canonical_markdown_remains_owner_truth": True,
            "must_not_infer_approval_or_execution_authority": True,
            "must_disclose_stale_or_conflicting_rows": True,
        },
        "sql_canon_migration": {
            "standing_local_sql_canon_migration_approved": True,
            "durable_sql_canon_db": "state/finance/finance-canon.sqlite",
            "typed_access_layer": "scripts/finance_sql_canon_access.py",
            "internal_sql_canon_primary_guarded": True,
            "internal_current_state_field_families_promoted": [
                "answer_path_scope",
                "evidence_freshness",
                "reference_levels",
                "source_lineage",
                "tier_routing_state",
                "universe_membership",
            ],
            "retail_or_customer_sql_first_allowed": False,
            "this_tmp_db_is_compatibility_cache": True,
            "sql_canon_authority_expanded": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


@contextmanager
def connect_ro(db_path: Path) -> Iterator[sqlite3.Connection]:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def sqlite_object_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row["name"]) for row in rows(conn, "SELECT name FROM sqlite_master")}


def disciplined_entry_band(ticker: str) -> dict[str, Any]:
    """Additive read of the disciplined (written) buy zone from the SQL-canon companion table.

    The disciplined band is canon-owned, so this reads ``state/finance/finance-canon.sqlite``
    directly rather than the derived tmp proof DB. It is the canonical, event-driven written
    band the no-chase gate binds to, deliberately separate from ``entry_stop_reference`` /
    ``reference_levels`` (the daily-refreshed tracking band, proximity/alert only). This reader
    never changes the tracking ``entry_band_low`` mapping; it exposes the disciplined band
    alongside it so consumers stop treating the chasing tracking band as the buy zone.
    """
    if not CANON_DB.exists():
        return {
            "present": False,
            "ticker": ticker,
            "reason": "canon_db_absent",
            "is_written_buy_zone": True,
            "distinct_from_tracking_band": True,
        }
    with connect_ro(CANON_DB) as conn:
        if "disciplined_reference_levels" not in sqlite_object_names(conn):
            return {
                "present": False,
                "ticker": ticker,
                "reason": "disciplined_reference_levels_table_absent",
                "is_written_buy_zone": True,
                "distinct_from_tracking_band": True,
            }
        row = conn.execute(
            "SELECT * FROM disciplined_reference_levels WHERE ticker=?", (ticker,)
        ).fetchone()
    if row is None:
        return {
            "present": False,
            "ticker": ticker,
            "reason": "no_disciplined_row_for_ticker",
            "is_written_buy_zone": True,
            "distinct_from_tracking_band": True,
        }
    row = dict(row)
    return {
        "present": True,
        "ticker": row.get("ticker"),
        "disciplined_band_low": row.get("disciplined_band_low"),
        "disciplined_band_high": row.get("disciplined_band_high"),
        "disciplined_stop": row.get("disciplined_stop"),
        "band_state": row.get("band_state"),
        "levels_set_at": row.get("disciplined_levels_set_at"),
        "level_trigger": row.get("disciplined_level_trigger"),
        "source_artifact_path": row.get("disciplined_source_artifact_path"),
        "source_artifact_hash": row.get("disciplined_source_sha256"),
        "authority_class": row.get("authority_class"),
        "is_written_buy_zone": True,
        "distinct_from_tracking_band": True,
        "levels_move_only_through_entry_band_gate": True,
        "reference_source_surface": "state/finance/finance-canon.sqlite:disciplined_reference_levels",
    }


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def source_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False}
    payload = load_json(path, {}) if path.suffix.lower() == ".json" else {}
    generated = payload.get("generated_at_utc") if isinstance(payload, dict) else None
    return {
        "path": rel(path),
        "exists": True,
        "generated_at_utc": generated,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "size_bytes": path.stat().st_size,
    }


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def authority_forbidden_true(*objects: Any) -> list[str]:
    found: list[str] = []
    for obj in objects:
        auth = as_dict(obj)
        for key in AUTHORITY_FALSE_KEYS:
            if auth.get(key) is True:
                found.append(key)
    return sorted(set(found))


def public_entry_stop_reference(row: dict[str, Any]) -> dict[str, Any]:
    """Expose current entry/stop fields without dumping legacy raw cache JSON."""
    public = dict(row)
    raw_json = public.pop("raw_json", None)
    if raw_json:
        public["legacy_raw_json_omitted"] = True
        public["legacy_raw_json_role"] = "compatibility_lineage_only_not_current_state"
    return public


def entry_stop_legacy_lineage(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "cache_role": "legacy_compatibility_cache_lineage_not_current_state",
        "source_artifact_path": row.get("source_artifact_path"),
        "source_artifact_hash": row.get("source_artifact_hash"),
        "source_timestamp": row.get("source_timestamp"),
        "freshness_status": row.get("freshness_status"),
        "validation_status": row.get("validation_status"),
        "raw_json_omitted_from_front_door": bool(row.get("raw_json")),
    }


def sql_canon_state_context(ticker: str | None = None) -> dict[str, Any]:
    route = strategic_answer_route_context(consumer="finance_intelligence_state")
    critical: list[str] = list(as_dict(route.get("validation")).get("errors") or [])
    warnings: list[Any] = list(as_dict(route.get("validation")).get("warnings") or [])
    registry: dict[str, Any] = {}
    field_family_summary: dict[str, Any] = {}
    production_tickers: list[str] = list(route.get("production_answer_tickers") or [])
    legacy_production_tickers: list[str] = list(route.get("legacy_production_answer_tickers") or [])
    ticker_state: dict[str, Any] | None = None
    reference_level: dict[str, Any] | None = None
    evidence_freshness: dict[str, Any] | None = None
    validation = {"status": route.get("access_validation_status")}

    if route.get("status") == "ok":
        try:
            client = FinanceSqlCanonAccess()
            registry = client.migration_registry_summary()
            field_family_summary = client.field_family_summary()
            if ticker:
                state = client.ticker_state(ticker)
                reference = client.reference_level_record(ticker)
                freshness = client.evidence_freshness(ticker)
                ticker_state = asdict(state) if state else None
                reference_level = (
                    {
                        "ticker": reference.ticker,
                        "reference_price_low": reference.reference_price_low,
                        "reference_price_high": reference.reference_price_high,
                        "reference_invalidation_level": reference.reference_invalidation_level,
                        "reference_confidence": reference.reference_confidence,
                        "reference_band_status": reference.reference_band_status,
                        "authority_class": reference.authority_class,
                        "fallback_rule": reference.fallback_rule,
                    }
                    if reference
                    else None
                )
                evidence_freshness = asdict(freshness) if freshness else None
        except (RuntimeError, ValueError) as exc:
            critical.append("sql_canon_access_guard_blocked")
            warnings.append(str(exc))
        if ticker and ticker_state is None:
            critical.append("sql_canon_ticker_state_missing")

    status = "blocked" if critical else "ok"
    return {
        "schema": "veritas.finance_intelligence_state.sql_canon_context.v1",
        "status": status,
        "access_validation_status": route.get("access_validation_status"),
        "sql_canon_db": "state/finance/finance-canon.sqlite",
        "production_answer_count": len(production_tickers),
        "production_answer_tickers": production_tickers,
        "production_answer_definition": route.get("production_answer_definition"),
        "legacy_production_answer_count": len(legacy_production_tickers),
        "legacy_production_answer_tickers": legacy_production_tickers,
        "legacy_production_answer_definition": route.get("legacy_production_answer_definition"),
        "legacy_42_retired_from_blocking": route.get("legacy_42_retired_from_blocking"),
        "legacy_42_count_advisory_only": route.get("legacy_42_count_advisory_only"),
        "compatibility_scope_active": False,
        "migration_registry_summary": registry,
        "p0_registry_lane_status": route.get("p0_registry_lane_status"),
        "answer_route_policy": route.get("answer_route_policy"),
        "field_family_summary": field_family_summary,
        "ticker_state": ticker_state,
        "reference_level": reference_level,
        "evidence_freshness": evidence_freshness,
        "validation": {"status": status, "critical_errors": critical, "warnings": warnings},
        "authority_boundary": {
            "durable_sql_canon_current_state": True,
            "internal_sql_canon_primary_guarded": True,
            "read_only_access_layer_required": True,
            "tmp_finance_intelligence_state_is_compatibility_cache": True,
            "source_open_required_before_material_finance_claims": True,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def sql_canon_reference_overlay(ticker: str) -> dict[str, Any]:
    context = sql_canon_state_context(ticker)
    reference = as_dict(context.get("reference_level"))
    return {
        "ticker": ticker.upper(),
        "status": "ok" if context.get("status") == "ok" and reference else "blocked",
        "sql_canon_db": context.get("sql_canon_db"),
        "reference_level": reference,
        "validation": context.get("validation"),
        "authority_boundary": {
            "reference_metadata_only": True,
            "not_recommendation_or_execution_authority": True,
            "source_open_required_before_material_claims": True,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def reference_level_record_as_entry_stop_row(record: ReferenceLevelRecord) -> dict[str, Any]:
    return {
        "ticker": record.ticker,
        "entry_band_low": record.reference_price_low,
        "entry_band_high": record.reference_price_high,
        "stop_or_invalidation": record.reference_invalidation_level,
        "band_source": "state/finance/finance-canon.sqlite:reference_levels",
        "stop_source": "state/finance/finance-canon.sqlite:reference_levels",
        "freshness_status": "current",
        "validation_status": "ok",
        "owner_note_path": record.source_artifact_path,
        "source_artifact_path": record.source_artifact_path,
        "source_artifact_hash": record.source_artifact_sha256,
        "source_timestamp": record.source_generated_at_utc,
        "raw_json": record.raw_json,
        "reference_source_surface": "state/finance/finance-canon.sqlite:reference_levels",
        "authority_class": record.authority_class,
    }


def build_entry_stop_reference_metadata(
    ticker: str,
    record: ReferenceLevelRecord | None,
) -> dict[str, Any]:
    """Project durable SQL reference lineage into the frozen compatibility shape."""

    ticker = ticker.upper()
    values: dict[str, Any] = {}
    source_rows: list[dict[str, Any]] = []
    if record is not None:
        values = {
            "reference_price_low": record.reference_price_low,
            "reference_price_high": record.reference_price_high,
            "reference_invalidation_level": record.reference_invalidation_level,
            "reference_level_source_timestamp": record.source_generated_at_utc,
            "reference_level_source_sha256": record.source_artifact_sha256,
            "reference_level_owner_source_path": record.source_artifact_path,
        }
        source_rows = [
            {
                "key": f"{ticker}:{field}",
                "source_artifact_path": record.source_artifact_path,
                "source_artifact_hash": record.source_artifact_sha256,
                "freshness_status": record.source_status,
                "last_reconciled_at_utc": record.lineage_inserted_at_utc,
                "updated_at_utc": record.lineage_inserted_at_utc,
            }
            for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS
        ]
    missing_fields = [field for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS if field not in values]
    issues = ["durable_reference_record_missing"] if record is None else []
    return {
        "schema_version": "wf72_entry_stop_reference_metadata.v1",
        "status": "available" if not issues else "fallback_required",
        "ticker": ticker,
        "authority_boundary": ENTRY_STOP_REFERENCE_METADATA_AUTHORITY_BOUNDARY,
        "sql_cache_path": "state/finance/finance-canon.sqlite",
        "sql_read_mode": "sqlite_uri_mode_ro",
        "approved_row_family": "durable_finance_canon_reference_level_compatibility_projection",
        "approved_fields": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS),
        "row_keys": [f"{ticker}:{field}" for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS if field in values],
        "values": values,
        "source_lineage": {
            "owner_source_path": values.get("reference_level_owner_source_path"),
            "source_timestamp": values.get("reference_level_source_timestamp"),
            "source_sha256": values.get("reference_level_source_sha256"),
        },
        "source_rows": source_rows,
        "missing_fields": missing_fields,
        "issues": issues,
        "notes": [
            "Reference metadata only; does not replace price_band_stop fallback values.",
            "No recommendation, deployment/action state, approval, portfolio mutation, or execution authority.",
        ],
        **ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS,
    }


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS preopen_action_queue;
        DROP VIEW IF EXISTS canon_conflict_candidates;
        DROP VIEW IF EXISTS artifact_provenance_map;
        DROP VIEW IF EXISTS current_pilot_fixtures;
        DROP VIEW IF EXISTS latest_validator_status;
        DROP VIEW IF EXISTS pending_approval_queue;
        DROP VIEW IF EXISTS stale_ticker_cards;
        DROP VIEW IF EXISTS latest_valid_entry_stop_refs;
        DROP VIEW IF EXISTS current_ticker_cards;
        DROP VIEW IF EXISTS all_ticker_sql_rows;

        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS pilot_fixture_registry;
        DROP TABLE IF EXISTS card_registry;
        DROP TABLE IF EXISTS promotion_signals;
        DROP TABLE IF EXISTS official_evidence_index;
        DROP TABLE IF EXISTS earnings_calendar;
        DROP TABLE IF EXISTS analyst_snapshot;
        DROP TABLE IF EXISTS fundamental_snapshot;
        DROP TABLE IF EXISTS entry_stop_reference;
        DROP TABLE IF EXISTS latest_price_technical;
        DROP TABLE IF EXISTS ticker_family_status;
        DROP TABLE IF EXISTS ticker_tier;
        DROP TABLE IF EXISTS universe;
        DROP TABLE IF EXISTS source_run;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;

        CREATE TABLE source_run (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE,
            generated_at_utc TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_status TEXT NOT NULL,
            source_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE universe (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL,
            instrument_type TEXT,
            tier TEXT NOT NULL,
            monitoring_role TEXT,
            sector TEXT,
            industry TEXT,
            universe_scope TEXT NOT NULL,
            production_answer_path_member INTEGER NOT NULL,
            thin_monitor_row INTEGER NOT NULL,
            decision_grade_eligible INTEGER NOT NULL,
            promotion_required_before_action INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            owner_note_path TEXT,
            universe_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE ticker_tier (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            tier TEXT NOT NULL,
            monitoring_cadence_json TEXT NOT NULL,
            data_requirements_json TEXT NOT NULL,
            promotion_triggers_json TEXT NOT NULL,
            demotion_triggers_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE ticker_family_status (
            ticker TEXT NOT NULL REFERENCES universe(ticker) ON DELETE CASCADE,
            family_id TEXT NOT NULL,
            status TEXT NOT NULL,
            missing_count INTEGER NOT NULL,
            stale_count INTEGER NOT NULL,
            source_required INTEGER NOT NULL,
            source_paths_json TEXT NOT NULL,
            PRIMARY KEY (ticker, family_id)
        ) STRICT;

        CREATE TABLE pilot_fixture_registry (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT NOT NULL,
            instrument_type TEXT,
            monitoring_role TEXT,
            sector TEXT,
            industry TEXT,
            pilot_status TEXT NOT NULL,
            production_answer_path_member INTEGER NOT NULL,
            decision_grade_eligible INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            thin_row_only INTEGER NOT NULL,
            on_demand_card_required_before_claim INTEGER NOT NULL,
            provider_telemetry_required INTEGER NOT NULL,
            stale_but_known_disclosure_required INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE latest_price_technical (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            latest_known_price REAL,
            price_source TEXT,
            band_status TEXT,
            technical_summary TEXT,
            technical_status TEXT,
            source_path TEXT,
            fresh_quote_required INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE entry_stop_reference (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            entry_band_low REAL,
            entry_band_high REAL,
            stop_or_invalidation REAL,
            band_source TEXT,
            stop_source TEXT,
            freshness_status TEXT,
            validation_status TEXT,
            owner_note_path TEXT,
            source_artifact_path TEXT,
            source_artifact_hash TEXT,
            source_timestamp TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE fundamental_snapshot (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            valuation_status TEXT,
            key_metrics_status TEXT,
            latest_earnings_status TEXT,
            source_path TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE analyst_snapshot (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            status TEXT,
            rating_summary TEXT,
            price_target_summary TEXT,
            source_path TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE earnings_calendar (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            catalyst_status TEXT,
            latest_earnings_status TEXT,
            next_earnings_date TEXT,
            source_path TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE official_evidence_index (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL REFERENCES universe(ticker) ON DELETE CASCADE,
            evidence_family TEXT NOT NULL,
            status TEXT,
            source_path TEXT,
            source_open_required INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE promotion_signals (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            recommendation_posture TEXT,
            recommendation_posture_key TEXT,
            support_level TEXT,
            actionability TEXT,
            pending_approval_count INTEGER NOT NULL,
            blockers_json TEXT NOT NULL,
            missing_or_stale_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE card_registry (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            card_path TEXT NOT NULL,
            card_exists INTEGER NOT NULL,
            card_generated_at_utc TEXT,
            card_schema_version INTEGER,
            review_only INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            authority_forbidden_true_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE validation_results (
            check_name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        CREATE VIEW current_ticker_cards AS
            SELECT u.ticker, u.name, u.tier, u.monitoring_role, u.sector, u.instrument_type,
                   u.universe_scope, u.production_answer_path_member, u.thin_monitor_row,
                   l.latest_known_price, l.band_status,
                   e.entry_band_low, e.entry_band_high, e.stop_or_invalidation,
                   p.recommendation_posture, p.recommendation_posture_key, p.actionability,
                   c.card_path, c.card_generated_at_utc, c.source_open_required,
                   c.authority_forbidden_true_json
            FROM universe u
            LEFT JOIN latest_price_technical l ON l.ticker = u.ticker
            LEFT JOIN entry_stop_reference e ON e.ticker = u.ticker
            LEFT JOIN promotion_signals p ON p.ticker = u.ticker
            LEFT JOIN card_registry c ON c.ticker = u.ticker
            WHERE u.active = 1
              AND u.production_answer_path_member = 1;

        CREATE VIEW all_ticker_sql_rows AS
            SELECT u.ticker, u.name, u.tier, u.monitoring_role, u.sector, u.instrument_type,
                   u.universe_scope, u.production_answer_path_member, u.thin_monitor_row,
                   u.decision_grade_eligible, c.card_exists,
                   l.latest_known_price, l.band_status, l.technical_status,
                   e.entry_band_low, e.entry_band_high, e.stop_or_invalidation,
                   e.freshness_status AS entry_stop_freshness_status,
                   e.validation_status AS entry_stop_validation_status,
                   f.valuation_status, f.key_metrics_status, f.latest_earnings_status,
                   a.status AS analyst_status,
                   p.recommendation_posture, p.recommendation_posture_key, p.actionability,
                   c.card_path, c.card_generated_at_utc, c.source_open_required,
                   c.authority_forbidden_true_json
            FROM universe u
            LEFT JOIN latest_price_technical l ON l.ticker = u.ticker
            LEFT JOIN entry_stop_reference e ON e.ticker = u.ticker
            LEFT JOIN fundamental_snapshot f ON f.ticker = u.ticker
            LEFT JOIN analyst_snapshot a ON a.ticker = u.ticker
            LEFT JOIN promotion_signals p ON p.ticker = u.ticker
            LEFT JOIN card_registry c ON c.ticker = u.ticker
            WHERE u.active = 1;

        CREATE VIEW latest_valid_entry_stop_refs AS
            SELECT *
            FROM entry_stop_reference
            WHERE validation_status = 'ok'
              AND freshness_status IN ('fresh', 'current')
              AND entry_band_low IS NOT NULL
              AND entry_band_high IS NOT NULL;

        CREATE VIEW stale_ticker_cards AS
            SELECT c.ticker, c.card_path, p.missing_or_stale_json, p.blockers_json
            FROM card_registry c
            JOIN promotion_signals p ON p.ticker = c.ticker
            WHERE p.missing_or_stale_json != '[]'
               OR p.blockers_json LIKE '%stale%';

        CREATE VIEW pending_approval_queue AS
            SELECT u.ticker, u.tier, u.monitoring_role, p.recommendation_posture,
                   p.support_level, p.pending_approval_count, p.blockers_json
            FROM universe u
            JOIN promotion_signals p ON p.ticker = u.ticker
            WHERE p.pending_approval_count > 0
               OR p.recommendation_posture_key IN ('approval_ready_if_fresh', 'promotion_review', 'deployable_now')
            ORDER BY CASE u.tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END, u.ticker;

        CREATE VIEW latest_validator_status AS
            SELECT check_name, status, severity, detail_json
            FROM validation_results
            ORDER BY severity DESC, check_name;

        CREATE VIEW current_pilot_fixtures AS
            SELECT *
            FROM pilot_fixture_registry
            WHERE production_answer_path_member = 0
              AND decision_grade_eligible = 0
              AND thin_row_only = 1
              AND on_demand_card_required_before_claim = 1
            ORDER BY ticker;

        CREATE VIEW artifact_provenance_map AS
            SELECT ticker, 'card' AS source_kind, card_path AS source_path, card_generated_at_utc AS generated_at_utc
            FROM card_registry
            UNION ALL
            SELECT ticker, 'entry_stop_reference' AS source_kind, source_artifact_path AS source_path, source_timestamp AS generated_at_utc
            FROM entry_stop_reference
            UNION ALL
            SELECT ticker, evidence_family AS source_kind, source_path, NULL AS generated_at_utc
            FROM official_evidence_index;

        CREATE VIEW canon_conflict_candidates AS
            SELECT e.ticker, e.entry_band_low, e.entry_band_high, e.stop_or_invalidation,
                   e.freshness_status, e.validation_status, e.owner_note_path
            FROM entry_stop_reference e
            WHERE e.validation_status != 'ok'
               OR e.freshness_status NOT IN ('fresh', 'current')
               OR e.owner_note_path IS NULL
               OR e.owner_note_path = '';

        CREATE VIEW preopen_action_queue AS
            SELECT c.*
            FROM current_ticker_cards c
            WHERE c.tier IN ('A', 'B')
              AND c.recommendation_posture_key NOT IN ('reject_defer')
            ORDER BY
              CASE c.recommendation_posture_key
                WHEN 'approval_ready_if_fresh' THEN 1
                WHEN 'deployable_now' THEN 2
                WHEN 'promotion_review' THEN 3
                WHEN 'no_chase' THEN 4
                ELSE 5
              END,
              CASE c.tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
              c.ticker;

        CREATE INDEX idx_universe_tier ON universe(tier, ticker);
        CREATE INDEX idx_family_status_family ON ticker_family_status(family_id, status);
        CREATE INDEX idx_price_band_status ON latest_price_technical(band_status);
        CREATE INDEX idx_promotion_posture ON promotion_signals(recommendation_posture_key);
        CREATE INDEX idx_entry_stop_valid ON entry_stop_reference(validation_status, freshness_status);
        """
    )


def build_state(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    generated_at = utc_now()
    run_id = f"wf78-phase2-state-{generated_at.replace(':', '').replace('-', '')}"
    sql_client = FinanceSqlCanonAccess()
    memberships = sql_client.universe_memberships()
    sql_reference_records = sql_client.reference_level_records(memberships)
    unsupported_scopes = sorted({
        record.universe_scope
        for record in memberships.values()
        if record.universe_scope not in SUPPORTED_UNIVERSE_SCOPES
    })
    if unsupported_scopes:
        raise RuntimeError(f"unsupported guarded SQL universe scopes: {unsupported_scopes}")
    entries: list[dict[str, Any]] = []
    for record in memberships.values():
        entry = dict(record.raw_json)
        entry.update({
            "ticker": record.ticker,
            "name": record.name,
            "active": record.active,
            "instrument_type": record.instrument_type,
            "sector": record.sector,
            "industry": record.industry,
            "yfinance_symbol": record.yfinance_symbol,
            "sec_cik": record.sec_cik,
            "company_ir": record.company_ir,
            "universe_scope": record.universe_scope,
            "tier": record.tier,
            "coverage_obligation_tier": record.coverage_obligation_tier,
            "monitoring_role": record.monitoring_role,
            "production_scope_member": record.production_scope_member,
            "production_scope_source": record.production_scope_source,
            "sql_tier": record.sql_tier,
            "sql_tier_state": record.sql_tier_state,
            "tier_decision_scope": record.tier_decision_scope,
            "review_100_monitor": record.review_100_monitor,
            "decision_grade_eligible": record.decision_grade_eligible,
            "source_open_required": record.source_open_required,
            "promotion_required_before_action": record.promotion_required_before_action,
        })
        entries.append(entry)
    pilot_entries = [entry for entry in entries if entry["universe_scope"] == PILOT_SCOPE]
    coverage = as_dict(load_json(COVERAGE_PATH, {}))
    coverage_by_ticker = as_dict(coverage.get("ticker_coverage"))
    router_qa = as_dict(load_json(ROUTER_QA_PATH, {}))
    auto_router = as_dict(load_json(WF78_AUTO_TIER_ROUTING, {}))
    coverage_gate = as_dict(load_json(TIER_A_COVERAGE_GATE, {}))
    stale_packet_tickers = stale_tier_a_packet_tickers(auto_router)
    decision_grade_allowed_count = int(as_dict(coverage_gate.get("summary")).get("decision_grade_allowed_count") or 0)

    with closing(connect(db_path)) as conn, conn:
        init_schema(conn)
        conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.execute("INSERT INTO meta(key, value) VALUES ('generated_at_utc', ?)", (generated_at,))
        conn.execute("INSERT INTO meta(key, value) VALUES ('authority_boundary', ?)", (json_text(authority_boundary()),))
        for source_name, path in [
            ("durable_sql_canon", CANON_DB),
            ("universe_evidence_enrichment", UNIVERSE_PATH),
            ("coverage", COVERAGE_PATH),
            ("router_qa", ROUTER_QA_PATH),
            ("legacy_42_tier_shadow", LEGACY_42_TIER_SHADOW_DB),
        ]:
            meta = source_meta(path)
            conn.execute(
                "INSERT INTO source_run(run_id, generated_at_utc, source_path, source_status, source_json) VALUES (?,?,?,?,?)",
                (f"{run_id}:{source_name}", generated_at, meta["path"], "present" if meta.get("exists") else "missing", json_text(meta)),
            )
        for entry in pilot_entries:
            ticker = str(entry["ticker"]).upper()
            coverage_reason = as_dict(entry.get("coverage_reason"))
            conn.execute(
                """
                INSERT INTO pilot_fixture_registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticker,
                    entry.get("name"),
                    entry.get("tier") or "D",
                    entry.get("instrument_type"),
                    entry.get("monitoring_role"),
                    entry.get("sector"),
                    entry.get("industry"),
                    entry.get("pilot_status") or "fixture_only_not_in_production_answer_path",
                    1 if coverage_reason.get("production_answer_path_member") else 0,
                    1 if entry.get("decision_grade_eligible") else 0,
                    1 if entry.get("source_open_required") else 0,
                    1,
                    1,
                    1,
                    1,
                    json_text(entry),
                ),
            )
        for entry in entries:
            ticker = str(entry["ticker"]).upper()
            universe_scope = entry.get("universe_scope", ACTIVE_INTERNAL_SCOPE)
            production_member = bool(entry.get("production_scope_member"))
            thin_monitor = bool(entry.get("review_100_monitor"))
            card = as_dict(load_json(card_path(ticker), {}))
            card_meta = source_meta(card_path(ticker))
            universe_auth = as_dict(entry.get("authority_boundary"))
            card_auth = as_dict(card.get("authority_boundary"))
            forbidden = authority_forbidden_true(universe_auth, card_auth)
            price = as_dict(card.get("price_band_stop"))
            tech = as_dict(card.get("technical_posture"))
            reco = as_dict(card.get("recommendation_support"))
            missing_or_stale = as_list(card.get("missing_or_stale_evidence"))
            coverage_row = as_dict(coverage_by_ticker.get(ticker))
            if entry.get("universe_scope", ACTIVE_INTERNAL_SCOPE) == REVIEW_100_SCOPE:
                missing_or_stale = sorted(set(
                    [str(item) for item in as_list(coverage_row.get("missing_families"))]
                    + [f"stale:{item}" for item in as_list(coverage_row.get("stale_families"))]
                ))
            families = as_dict(coverage_row.get("families"))
            source_paths = sorted({item.get("path") for item in as_list(card.get("source_artifacts")) if isinstance(item, dict) and item.get("path")})
            card_exists = card_path(ticker).exists()
            thin_missing_context = {
                "status": "thin_monitor_missing_required_evidence" if thin_monitor else "missing",
                "source": "finance_data_coverage",
                "coverage_families": families,
                "universe_scope": universe_scope,
                "review_boundary": "SQL row exists for routing/coverage only; source-open evidence and promotion are required before material claims.",
            }

            conn.execute(
                """
                INSERT INTO universe VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticker, entry.get("name"), 1 if entry.get("active") is not False else 0,
                    entry.get("instrument_type"), entry.get("tier") or "D",
                    entry.get("monitoring_role"), entry.get("sector"), entry.get("industry"),
                    universe_scope,
                    1 if production_member else 0,
                    1 if thin_monitor else 0,
                    1 if entry.get("decision_grade_eligible") else 0,
                    1 if entry.get("promotion_required_before_action") else 0,
                    1 if entry.get("source_open_required") else 0,
                    entry.get("owner_note_path") or "04. Research/Coverage and Watchlist.md",
                    json_text(entry),
                ),
            )
            conn.execute(
                "INSERT INTO ticker_tier VALUES (?,?,?,?,?,?)",
                (
                    ticker, entry.get("tier") or "D",
                    json_text(entry.get("monitoring_cadence") or {}),
                    json_text(entry.get("data_requirements") or {}),
                    json_text(entry.get("promotion_triggers") or []),
                    json_text(entry.get("demotion_triggers") or []),
                ),
            )
            for family_id, status in families.items():
                if not isinstance(status, dict):
                    continue
                conn.execute(
                    "INSERT INTO ticker_family_status VALUES (?,?,?,?,?,?,?)",
                    (
                        ticker, family_id, status.get("status") or "unknown",
                        len(as_list(status.get("missing_sources"))),
                        len(as_list(status.get("stale_sources"))),
                        1 if status.get("source_open_required_for_claims", True) else 0,
                        json_text(status.get("source_paths") or []),
                    ),
                )
            conn.execute(
                "INSERT INTO latest_price_technical VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ticker, fnum(price.get("latest_known_price")), price.get("price_source"),
                    price.get("band_status") or ("missing_required_refresh" if thin_monitor else None),
                    tech.get("summary") or tech.get("status") or ("thin monitor: price/technical refresh required" if thin_monitor else None),
                    tech.get("status") or ("missing_required_refresh" if thin_monitor else None),
                    price.get("price_source") or ("tmp/finance-data-coverage-current.json" if thin_monitor else "tmp/ticker-intelligence-cards"),
                    1 if price.get("fresh_quote_required", True) else 0,
                    json_text({"price_band_stop": price, "technical_posture": tech, "thin_missing_context": thin_missing_context if thin_monitor else {}}),
                ),
            )

            sql_record = sql_reference_records.get(ticker)
            if sql_record is not None:
                sql_ref = reference_level_record_as_entry_stop_row(sql_record)
                entry_band_low = sql_record.reference_price_low
                entry_band_high = sql_record.reference_price_high
                stop_or_invalidation = sql_record.reference_invalidation_level
                band_source = sql_ref["reference_source_surface"]
                stop_source = sql_ref["reference_source_surface"]
                freshness = sql_ref["freshness_status"]
                validator = sql_ref["validation_status"]
                owner_path = sql_record.source_artifact_path
                source_path = sql_record.source_artifact_path
                source_hash = sql_record.source_artifact_sha256
                source_ts = sql_record.source_generated_at_utc
            else:
                sql_ref = {}
                entry_band_low = None
                entry_band_high = None
                stop_or_invalidation = None
                band_source = "state/finance/finance-canon.sqlite:reference_levels"
                stop_source = "state/finance/finance-canon.sqlite:reference_levels"
                freshness = "missing_reference_level"
                validator = "blocked"
                owner_path = entry.get("owner_note_path") or "04. Research/Coverage and Watchlist.md"
                source_path = None
                source_hash = None
                source_ts = None
            conn.execute(
                "INSERT INTO entry_stop_reference VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ticker,
                    fnum(entry_band_low),
                    fnum(entry_band_high),
                    fnum(stop_or_invalidation),
                    band_source,
                    stop_source,
                    freshness,
                    validator,
                    owner_path,
                    source_path,
                    source_hash,
                    source_ts,
                    json_text({
                        "sql_canon_reference_level": asdict(sql_record) if sql_record is not None else None,
                        "missing_reason": None if sql_record is not None else "durable_sql_reference_level_absent",
                        "thin_missing_context": thin_missing_context if thin_monitor else {},
                    }),
                ),
            )
            conn.execute(
                "INSERT INTO fundamental_snapshot VALUES (?,?,?,?,?,?)",
                (
                    ticker,
                    as_dict(card.get("valuation")).get("status") or as_dict(families.get("valuation_multiples")).get("status") or ("missing_required_if_promoted" if thin_monitor else None),
                    as_dict(card.get("key_financial_metrics")).get("status") or as_dict(families.get("key_financial_metrics")).get("status") or as_dict(families.get("revenue_growth_margins_fcf_debt")).get("status") or ("missing_required_if_promoted" if thin_monitor else None),
                    as_dict(card.get("latest_earnings_performance")).get("status") or as_dict(families.get("latest_earnings_performance")).get("status") or ("missing_required_if_promoted" if thin_monitor else None),
                    "tmp/finance-data-coverage-current.json" if thin_monitor else "tmp/ticker-intelligence-cards",
                    json_text({
                        "valuation": card.get("valuation"),
                        "key_financial_metrics": card.get("key_financial_metrics"),
                        "latest_earnings_performance": card.get("latest_earnings_performance"),
                        "thin_missing_context": thin_missing_context if thin_monitor else {},
                    }),
                ),
            )
            analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
            conn.execute(
                "INSERT INTO analyst_snapshot VALUES (?,?,?,?,?,?)",
                (
                    ticker, analyst.get("status") or as_dict(families.get("analyst_consensus")).get("status") or ("optional_missing_for_thin_monitor" if thin_monitor else None),
                    analyst.get("rating_summary") or analyst.get("consensus_rating"),
                    analyst.get("price_target_summary") or analyst.get("price_target"),
                    "tmp/finance-data-coverage-current.json" if thin_monitor else "tmp/analyst-consensus-current.json",
                    json_text(analyst or (thin_missing_context if thin_monitor else {})),
                ),
            )
            catalyst = as_dict(card.get("catalyst_earnings_state"))
            latest_earnings = as_dict(card.get("latest_earnings_performance"))
            conn.execute(
                "INSERT INTO earnings_calendar VALUES (?,?,?,?,?,?)",
                (
                    ticker, catalyst.get("status") or ("missing_required_if_promoted" if thin_monitor else None),
                    latest_earnings.get("status") or as_dict(families.get("latest_earnings_performance")).get("status") or ("missing_required_if_promoted" if thin_monitor else None),
                    catalyst.get("next_earnings_date") or latest_earnings.get("next_earnings_date"),
                    "tmp/finance-data-coverage-current.json" if thin_monitor else "tmp/official-earnings-bridge.json",
                    json_text({"catalyst_earnings_state": catalyst, "latest_earnings_performance": latest_earnings, "thin_missing_context": thin_missing_context if thin_monitor else {}}),
                ),
            )
            for family, payload in [
                ("competitive_moat", card.get("competitive_moat")),
                ("recent_developments", card.get("recent_developments")),
                ("orders_backlog_book_to_bill", card.get("orders_backlog_book_to_bill")),
                ("official_capture_developments_orders_backlog", card.get("official_capture_developments_orders_backlog")),
            ]:
                conn.execute(
                    "INSERT INTO official_evidence_index(ticker, evidence_family, status, source_path, source_open_required, raw_json) VALUES (?,?,?,?,?,?)",
                    (
                        ticker, family, as_dict(payload).get("status"),
                        "tmp/finance-data-coverage-current.json" if thin_monitor else "tmp/official-earnings-bridge.json",
                        1,
                        json_text(payload or (thin_missing_context if thin_monitor else {})),
                    ),
                )
            blockers = as_list(reco.get("blockers_or_gates"))
            if thin_monitor:
                blockers = sorted(set(blockers + [
                    "thin_monitor_sql_row_only",
                    "fresh_price_band_stop_required",
                    "technical_posture_required",
                    "official_fundamentals_required_if_promoted",
                    "risk_register_required_if_promoted",
                ]))
            reco, blockers = suppress_stale_packet_approval_language(
                ticker,
                reco,
                blockers,
                stale_packet_tickers,
                decision_grade_allowed_count,
            )
            posture_key = str(reco.get("posture_key") or "")
            pending_approval_count = 0 if thin_monitor else (1 if posture_key in {"approval_ready_if_fresh", "promotion_review", "deployable_now"} else 0)
            conn.execute(
                "INSERT INTO promotion_signals VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ticker,
                    reco.get("posture") or ("thin monitor; not decision-grade" if thin_monitor else None),
                    reco.get("posture_key") or ("thin_monitor_no_action" if thin_monitor else None),
                    reco.get("support_level") or ("missing_required_evidence" if thin_monitor else None),
                    reco.get("actionability") or ("not_decision_grade" if thin_monitor else None),
                    pending_approval_count,
                    json_text(blockers), json_text(missing_or_stale),
                    json_text(reco or (thin_missing_context if thin_monitor else {})),
                ),
            )
            conn.execute(
                "INSERT INTO card_registry VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ticker, rel(card_path(ticker)), 1 if card_exists else 0,
                    card.get("generated_at_utc") or card_meta.get("generated_at_utc"),
                    int(card.get("schema_version") or 0),
                    1 if card.get("review_only", True) else 0,
                    1 if card_auth.get("source_open_required_before_final_recommendation_or_action_claim", True) else 0,
                    json_text(forbidden),
                    json_text({"card_source_paths": source_paths, "card": card}),
                ),
            )

        validation = validate_db(conn, expected_tickers=len(entries), router_qa=router_qa)
        for check in validation["checks"]:
            conn.execute(
                "INSERT INTO validation_results VALUES (?,?,?,?)",
                (check["name"], "ok" if check["ok"] else "fail", check["severity"], json_text(check.get("detail"))),
            )
        conn.execute("PRAGMA optimize")

    return validate_state(db_path)


def refresh_100_packet(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    """Refresh the scaleout SQL routing surface from current workspace artifacts."""
    coverage_proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "finance_data_coverage.py"), "--validate"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    validation = build_state(db_path)
    coverage = as_dict(load_json(COVERAGE_PATH, {}))
    summary = as_dict(validation.get("summary"))
    packet = {
        **packet_header("finance_intelligence_state_refresh_100", db_path),
        "status": "ok" if validation.get("status") == "ok" and coverage_proc.returncode == 0 else "blocked",
        "refresh_scope": {
            "active_tickers": summary.get("universe_rows"),
            "strict_production_grade_rows": summary.get("production_answer_path_rows"),
            "expected_strict_production_grade_rows": EXPECTED_STRICT_PRODUCTION_TICKERS,
            "review_monitor_thin_rows": summary.get("review_monitor_thin_rows"),
            "supported_active_ticker_counts": sorted(SUPPORTED_ACTIVE_TICKER_COUNTS),
            "source": rel(CANON_DB),
        },
        "coverage_refresh": {
            "command": "python scripts\\finance_data_coverage.py --validate",
            "returncode": coverage_proc.returncode,
            "status": coverage.get("status"),
            "summary": coverage.get("summary"),
        },
        "state_validation": validation,
        "refresh_boundary": {
            "sql_rows_refreshed_from_existing_workspace_artifacts": True,
            "external_market_provider_fetch_performed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
            "paper_or_live_execution_allowed": False,
            "thin_rows_must_be_source_opened_and_promoted_before_material_claims": True,
        },
    }
    return write_packet(DEFAULT_REFRESH_100_PACKET, packet)


def authority_boundary() -> dict[str, Any]:
    return {
        "review_only": True,
        "database_path": rel(DEFAULT_DB),
        "standing_local_sql_canon_migration_approved": True,
        "durable_sql_canon_db": "state/finance/finance-canon.sqlite",
        "typed_sql_canon_access_layer": "scripts/finance_sql_canon_access.py",
        "internal_sql_canon_primary_guarded": True,
        "internal_sql_canon_current_state_field_families": [
            "answer_path_scope",
            "evidence_freshness",
            "reference_levels",
            "source_lineage",
            "tier_routing_state",
            "universe_membership",
        ],
        "retail_or_customer_sql_first_allowed": False,
        "tmp_database_is_compatibility_cache": True,
        "database_path_migration_performed": False,
        "tmp_database_promotion_performed": False,
        "full_sql_canon_migration_allowed": False,
        "sql_canon_authority_expanded": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "paper_trade_execution_allowed": False,
        "live_trade_or_account_action_allowed": False,
        "source_open_required_before_finance_claims": True,
    }


def paper_position_authority_boundary(paper_db_path: Path) -> dict[str, Any]:
    boundary = authority_boundary()
    boundary["database_path"] = rel(paper_db_path)
    boundary["paper_position_sql_state_only"] = True
    boundary["paper_order_execution_allowed"] = False
    boundary["paper_order_submit_allowed_by_this_registry"] = False
    boundary["paper_order_cancel_allowed_by_this_registry"] = False
    boundary["trade_or_account_action_allowed"] = False
    boundary["canon_cache_used_for_paper_positions"] = False
    boundary["artifact_index_is_state_owner"] = False
    return boundary


def validate_db(conn: sqlite3.Connection, expected_tickers: int | None, router_qa: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "", severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    integrity = scalar(conn, "PRAGMA integrity_check")
    fk_rows = rows(conn, "PRAGMA foreign_key_check")
    add("integrity_check_ok", integrity == "ok", integrity)
    add("foreign_key_check_ok", len(fk_rows) == 0, {"rows": len(fk_rows)})
    universe_count = int(scalar(conn, "SELECT COUNT(*) FROM universe") or 0)
    active_sql_rows = int(scalar(conn, "SELECT COUNT(*) FROM all_ticker_sql_rows") or 0)
    production_answer_path_rows = int(scalar(conn, "SELECT COUNT(*) FROM universe WHERE production_answer_path_member=1") or 0)
    current_card_rows = int(scalar(conn, "SELECT COUNT(*) FROM current_ticker_cards") or 0)
    latest_valid_entry_stop_rows = int(scalar(conn, "SELECT COUNT(*) FROM latest_valid_entry_stop_refs") or 0)
    review_monitor_rows = int(scalar(conn, "SELECT COUNT(*) FROM universe WHERE universe_scope=? AND thin_monitor_row=1 AND decision_grade_eligible=0", (REVIEW_100_SCOPE,)) or 0)
    if expected_tickers is not None:
        add("universe_count_matches_expected", universe_count == expected_tickers, {"expected": expected_tickers, "actual": universe_count})
    else:
        add("universe_count_supported_scaleout", universe_count in SUPPORTED_CURRENT_SCOPE_COUNTS, {"actual": universe_count, "supported": sorted(SUPPORTED_CURRENT_SCOPE_COUNTS)})
    add("active_sql_rows_supported_scaleout_count", active_sql_rows in SUPPORTED_CURRENT_SCOPE_COUNTS, {"actual": active_sql_rows, "supported": sorted(SUPPORTED_CURRENT_SCOPE_COUNTS)})
    add(
        "current_ticker_cards_match_production_scope",
        current_card_rows == production_answer_path_rows,
        {
            "actual": current_card_rows,
            "expected_production_scope": production_answer_path_rows,
            "expected_strict_production_scope": EXPECTED_STRICT_PRODUCTION_TICKERS,
            "dynamic_scope_source": "sql_first_universe_production_answer_path_member",
            "empty_production_scope_is_wait_state": production_answer_path_rows == 0,
        },
    )
    add("cards_exist_for_dynamic_production_scope", scalar(conn, "SELECT COUNT(*) FROM card_registry c JOIN universe u ON u.ticker=c.ticker WHERE u.production_answer_path_member=1 AND c.card_exists=0") == 0, {"missing": scalar(conn, "SELECT COUNT(*) FROM card_registry c JOIN universe u ON u.ticker=c.ticker WHERE u.production_answer_path_member=1 AND c.card_exists=0")})
    add("review_monitor_thin_rows_supported_scaleout_count", review_monitor_rows in SUPPORTED_REVIEW_MONITOR_COUNTS, {"actual": review_monitor_rows, "supported": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS)})
    add("entry_stop_rows_for_all_tickers", scalar(conn, "SELECT COUNT(*) FROM entry_stop_reference") == universe_count, {"expected": universe_count, "actual": scalar(conn, "SELECT COUNT(*) FROM entry_stop_reference")})
    add("fundamental_rows_for_all_tickers", scalar(conn, "SELECT COUNT(*) FROM fundamental_snapshot") == universe_count, {"expected": universe_count, "actual": scalar(conn, "SELECT COUNT(*) FROM fundamental_snapshot")})
    add("analyst_rows_for_all_tickers", scalar(conn, "SELECT COUNT(*) FROM analyst_snapshot") == universe_count, {"expected": universe_count, "actual": scalar(conn, "SELECT COUNT(*) FROM analyst_snapshot")})
    add(
        "latest_valid_entry_stop_refs_cover_dynamic_production_scope",
        production_answer_path_rows == 0 or latest_valid_entry_stop_rows >= production_answer_path_rows,
        {
            "valid_reference_rows": latest_valid_entry_stop_rows,
            "strict_production_scope_rows": production_answer_path_rows,
            "expected_strict_production_scope": EXPECTED_STRICT_PRODUCTION_TICKERS,
            "dynamic_scope_source": "sql_first_universe_production_answer_path_member",
            "empty_production_scope_is_wait_state": production_answer_path_rows == 0,
        },
    )
    add("pilot_fixtures_excluded_from_production_cards", scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")})
    add("pilot_fixtures_thin_on_demand_only", scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE production_answer_path_member!=0 OR decision_grade_eligible!=0 OR thin_row_only!=1 OR on_demand_card_required_before_claim!=1") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE production_answer_path_member!=0 OR decision_grade_eligible!=0 OR thin_row_only!=1 OR on_demand_card_required_before_claim!=1")})
    add("no_forbidden_authority_in_cards", scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json!='[]'") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json!='[]'")})
    add("router_qa_pass", router_qa.get("status") == "pass", router_qa.get("summary"))
    add("source_open_required_all_cards", scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE source_open_required=0") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE source_open_required=0")})
    add("preopen_action_queue_has_rows", scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue") > 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue")}, "warning")
    status = "ok" if all(check["ok"] or check["severity"] == "warning" for check in checks) and not [c for c in checks if not c["ok"] and c["severity"] == "error"] else "blocked"
    return {"status": status, "checks": checks}


def validate_state(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        router_qa = as_dict(load_json(ROUTER_QA_PATH, {}))
        validation = validate_db(conn, None, router_qa)
        summary = {
            "universe_rows": scalar(conn, "SELECT COUNT(*) FROM universe"),
            "all_ticker_sql_rows": scalar(conn, "SELECT COUNT(*) FROM all_ticker_sql_rows"),
            "production_answer_path_rows": scalar(conn, "SELECT COUNT(*) FROM universe WHERE production_answer_path_member=1"),
            "review_monitor_thin_rows": scalar(conn, "SELECT COUNT(*) FROM universe WHERE thin_monitor_row=1"),
            "current_ticker_cards": scalar(conn, "SELECT COUNT(*) FROM current_ticker_cards"),
            "latest_valid_entry_stop_refs": scalar(conn, "SELECT COUNT(*) FROM latest_valid_entry_stop_refs"),
            "fundamental_snapshot_rows": scalar(conn, "SELECT COUNT(*) FROM fundamental_snapshot"),
            "analyst_snapshot_rows": scalar(conn, "SELECT COUNT(*) FROM analyst_snapshot"),
            "stale_ticker_cards": scalar(conn, "SELECT COUNT(*) FROM stale_ticker_cards"),
            "pending_approval_queue": scalar(conn, "SELECT COUNT(*) FROM pending_approval_queue"),
            "preopen_action_queue": scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue"),
            "pilot_fixture_rows": scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry"),
            "current_pilot_fixtures": scalar(conn, "SELECT COUNT(*) FROM current_pilot_fixtures"),
            "canon_conflict_candidates": scalar(conn, "SELECT COUNT(*) FROM canon_conflict_candidates"),
        }
    sql_canon_context = sql_canon_state_context()
    sql_canon_errors = as_dict(sql_canon_context.get("validation")).get("critical_errors") or []
    checks = [
        *validation["checks"],
        {
            "name": "durable_sql_canon_access_ok",
            "ok": sql_canon_context.get("status") == "ok",
            "detail": sql_canon_context,
            "severity": "error",
        },
    ]
    checks.extend(
        {"name": f"sql_canon:{item}", "ok": False, "detail": sql_canon_context, "severity": "error"}
        for item in sql_canon_errors
    )
    status = "ok" if validation["status"] == "ok" and not sql_canon_errors else "blocked"
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": "finance_intelligence_state_validation",
        "db_path": rel(db_path),
        "status": status,
        "summary": summary,
        "sql_canon_state": sql_canon_context,
        "authority_boundary": authority_boundary(),
        "checks": checks,
    }
    atomic_write_json(DEFAULT_VALIDATION, report)
    return report


def _parse_iso_hours_old(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return delta.total_seconds() / 3600.0


def resolve_answer_packet(ticker: str) -> dict[str, Any]:
    """Compatibility descriptor for the old ticker_answer_packet_v1 route.

    This descriptor can read an existing compatibility artifact, but it cannot
    assemble, regenerate, or dispatch the retired full-answer route.
    """
    ticker = ticker.upper()
    full_answer_path = TRADE_GRADE_FULL_ANSWER_DIR / f"{ticker}.json"
    card = card_path(ticker)
    fallback_chain = [
        rel(card),
        "03. Portfolio/Execution Board.md",
        "04. Research/Coverage and Watchlist.md",
    ]
    base = {
        "ticker": ticker,
        "compatibility_route": "ticker_answer_packet_v1",
        "canonical_answer_path": rel(full_answer_path),
        "legacy_file_dependency": False,
        "fallback_chain": fallback_chain,
        "review_only": True,
    }
    packet = load_json(full_answer_path, None) if full_answer_path.exists() else None
    if not isinstance(packet, dict):
        return {
            **base,
            "availability": "missing",
            "preferred_source": "ticker_card_and_sources",
            "reason": "WF85 full-answer compatibility artifact missing; in-memory assembly is retired",
        }
    validation = as_dict(packet.get("validation"))
    status = packet.get("status")
    card_payload = load_json(card, None) if card.exists() else None
    card_generated = card_payload.get("generated_at_utc") if isinstance(card_payload, dict) else None
    age_hours = _parse_iso_hours_old(packet.get("generated_at_utc"))
    confidence = as_dict(packet.get("answer_confidence"))
    machine_state = as_dict(packet.get("machine_state"))
    owner_action = as_dict(machine_state.get("owner_action"))
    if status != "ok":
        return {
            **base,
            "availability": "blocked",
            "preferred_source": "ticker_card_and_sources",
            "reason": f"WF85 full-answer assembler status={status}",
            "validation": validation,
        }
    missing_sections = as_list(validation.get("missing_sections"))
    descriptor = {
        **base,
        "availability": "present_from_wf85_assembler",
        "preferred_source": "wf85_full_answer_assembler",
        "reason": "legacy packet route is satisfied by the WF85 canonical full-answer assembler",
        "card_generated_at_utc": card_generated,
        "answer_generated_at_utc": packet.get("generated_at_utc"),
        "answer_age_hours": round(age_hours, 2) if age_hours is not None else None,
        "answer_confidence": confidence.get("overall_level"),
        "answer_confidence_score": confidence.get("score"),
        "decision_state": machine_state.get("decision_state"),
        "recommended_next_action": owner_action.get("owner_action"),
        "required_section_count": len(as_list(packet.get("section_order"))),
        "missing_sections": missing_sections,
        "source_count": packet.get("source_count"),
    }
    if missing_sections:
        descriptor.update({
            "availability": "present_with_section_warnings",
            "reason": "WF85 assembler present, but some sections remain source-open required",
        })
    return descriptor


def canonical_data_plane_overlay(ticker: str) -> dict[str, Any]:
    """Return WF84 read-only canonical overlay when available.

    This is a fallback-backed consumer migration only. The existing finance
    intelligence packet remains usable if the WF84 derived lookup is absent.
    """
    if not CANONICAL_FINANCE_DATA_PLANE_DB.exists():
        return {
            "status": "unavailable",
            "reason": "WF84 canonical data-plane SQLite companion missing",
            "fallback_used": True,
            "db_path": rel(CANONICAL_FINANCE_DATA_PLANE_DB),
        }
    try:
        with connect_ro(CANONICAL_FINANCE_DATA_PLANE_DB) as conn:
            current = rows(conn, "SELECT * FROM v_current_decision_overview WHERE ticker=?", (ticker.upper(),))
            authority = rows(conn, "SELECT * FROM v_authority_boundary_false")
            if not current:
                return {
                    "status": "missing",
                    "reason": "ticker absent from WF84 canonical data-plane view",
                    "fallback_used": True,
                    "db_path": rel(CANONICAL_FINANCE_DATA_PLANE_DB),
                }
            forbidden = authority[0] if authority else {}
            forbidden_count = sum(int(value or 0) for value in forbidden.values())
            return {
                "status": "ok" if forbidden_count == 0 else "blocked",
                "fallback_used": False,
                "db_path": rel(CANONICAL_FINANCE_DATA_PLANE_DB),
                "view": "v_current_decision_overview",
                "current": current[0],
                "authority_false_view": forbidden,
                "answer_contract": {
                    "internal_review_only": True,
                    "canonical_interface_not_owner_truth": True,
                    "does_not_authorize_capital_or_execution": True,
                    "existing_finance_intelligence_state_fallback_retained": True,
                },
            }
    except sqlite3.Error as exc:
        return {
            "status": "unavailable",
            "reason": f"WF84 canonical data-plane read failed: {exc}",
            "fallback_used": True,
            "db_path": rel(CANONICAL_FINANCE_DATA_PLANE_DB),
        }


def wf84_entry_stop_reference(ticker: str) -> dict[str, Any]:
    if not CANONICAL_FINANCE_DATA_PLANE_DB.exists():
        return {}
    try:
        with connect_ro(CANONICAL_FINANCE_DATA_PLANE_DB) as conn:
            current = rows(conn, "SELECT * FROM entry_stop_reference WHERE ticker=?", (ticker.upper(),))
            return current[0] if current else {}
    except sqlite3.Error:
        return {}


def entry_stop_cache_freshness_guard(ticker: str, finance_entry_row: dict[str, Any]) -> dict[str, Any]:
    """Report legacy entry/stop cache drift without letting it outrank SQL-canon."""
    ticker = ticker.upper()
    owner_hash = sha256_file(EXECUTION_BOARD)
    wf84_entry_row = wf84_entry_stop_reference(ticker)
    sql_canon_context = sql_canon_state_context(ticker)
    sql_reference = as_dict(sql_canon_context.get("reference_level"))
    sql_reference_row = {
        "entry_band_low": sql_reference.get("reference_price_low"),
        "entry_band_high": sql_reference.get("reference_price_high"),
        "stop_or_invalidation": sql_reference.get("reference_invalidation_level"),
    }

    def values_match(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for field in ("entry_band_low", "entry_band_high", "stop_or_invalidation"):
            try:
                left_value = float(left.get(field))
                right_value = float(right.get(field))
                ok = abs(left_value - right_value) <= 0.01
            except (TypeError, ValueError):
                left_value = left.get(field)
                right_value = right.get(field)
                ok = left_value == right_value and left_value not in (None, "")
            checks.append({"field": field, "ok": ok, "finance_state": left_value, "wf84": right_value})
        return {
            "status": "ok" if all(check["ok"] for check in checks) else "blocked",
            "checks": checks,
        }

    def check_layer(name: str, row: dict[str, Any]) -> dict[str, Any]:
        source_path = str(row.get("source_artifact_path") or "")
        source_hash = row.get("source_artifact_hash")
        validation = row.get("validation_status")
        freshness = row.get("freshness_status")
        if not row:
            return {"name": name, "status": "blocked", "reason": "entry_stop_reference_row_missing"}
        if source_path.replace("\\", "/") != "03. Portfolio/Execution Board.md":
            return {
                "name": name,
                "status": "fallback_required",
                "reason": "entry_stop_source_not_execution_board",
                "source_artifact_path": source_path,
                "validation_status": validation,
                "freshness_status": freshness,
            }
        if not owner_hash:
            return {"name": name, "status": "blocked", "reason": "execution_board_hash_missing"}
        if source_hash != owner_hash:
            return {
                "name": name,
                "status": "stale",
                "reason": "entry_stop_source_hash_mismatch",
                "source_artifact_path": source_path,
                "cached_source_hash": source_hash,
                "current_owner_hash": owner_hash,
                "validation_status": validation,
                "freshness_status": freshness,
            }
        if validation not in (None, "", "ok"):
            return {
                "name": name,
                "status": "blocked",
                "reason": f"validation_status={validation}",
                "source_artifact_path": source_path,
                "cached_source_hash": source_hash,
                "current_owner_hash": owner_hash,
                "freshness_status": freshness,
            }
        return {
            "name": name,
            "status": "ok",
            "reason": "entry_stop_source_hash_matches_owner_truth",
            "source_artifact_path": source_path,
            "cached_source_hash": source_hash,
            "current_owner_hash": owner_hash,
            "validation_status": validation,
            "freshness_status": freshness,
        }

    layers = [
        check_layer("finance_intelligence_state", finance_entry_row),
        check_layer("wf84_canonical_data_plane", wf84_entry_row),
    ]
    value_consistency = values_match(finance_entry_row, wf84_entry_row)
    sql_reference_available = sql_canon_context.get("status") == "ok" and bool(sql_reference)
    if sql_reference_available:
        finance_sql_consistency = values_match(finance_entry_row, sql_reference_row)
        wf84_sql_consistency = values_match(wf84_entry_row, sql_reference_row)
        sql_reference_consistency = {
            "status": "authoritative",
            "reference_source": "state/finance/finance-canon.sqlite:reference_levels",
            "sql_canon_reference": sql_reference_row,
            "finance_state_vs_sql_canon": finance_sql_consistency,
            "wf84_vs_sql_canon": wf84_sql_consistency,
            "legacy_value_mismatch_blocks_front_door": False,
        }
    else:
        sql_reference_consistency = {
            "status": "blocked",
            "reason": "sql_canon_reference_missing_or_guard_blocked",
            "sql_canon_status": sql_canon_context.get("status"),
            "sql_canon_validation": sql_canon_context.get("validation"),
        }
    statuses = {layer["status"] for layer in layers}
    status = "ok" if statuses == {"ok"} and value_consistency["status"] == "ok" else "blocked"
    hash_only_legacy_warning = (
        "stale" in statuses
        and statuses <= {"ok", "stale"}
        and value_consistency["status"] == "ok"
        and sql_reference_available
    )
    legacy_decoupled_warning = (
        sql_reference_available
        and (
            statuses != {"ok"}
            or value_consistency["status"] != "ok"
            or as_dict(sql_reference_consistency.get("finance_state_vs_sql_canon")).get("status") != "ok"
            or as_dict(sql_reference_consistency.get("wf84_vs_sql_canon")).get("status") != "ok"
        )
    )
    if not sql_reference_available:
        status = "fallback_required"
    elif legacy_decoupled_warning:
        status = "ok_sql_canon_authoritative_legacy_decoupled"
    else:
        status = "ok_sql_canon_authoritative"
    return {
        "ticker": ticker,
        "status": status,
        "owner_source_path": rel(EXECUTION_BOARD),
        "owner_source_sha256": owner_hash,
        "layers": layers,
        "value_consistency": value_consistency,
        "sql_canon_reference_consistency": sql_reference_consistency,
        "legacy_compatibility_hash_warning": {
            "present": hash_only_legacy_warning or legacy_decoupled_warning,
            "reason": (
                "legacy compatibility entry/stop cache trails SQL-canon current-state references; "
                "recorded as lineage drift only and not allowed to block the front door"
                if legacy_decoupled_warning
                else "legacy tmp compatibility cache source hashes trail the current owner-file hash, but SQL-canon, finance-state, and WF84 reference values match"
            ),
            "warning_layers": [layer for layer in layers if layer.get("status") == "stale"],
            "blocks_front_door": False if (hash_only_legacy_warning or legacy_decoupled_warning) else None,
        },
        "legacy_compatibility_value_warning": {
            "present": legacy_decoupled_warning,
            "finance_state_vs_wf84": value_consistency,
            "finance_state_vs_sql_canon": as_dict(sql_reference_consistency.get("finance_state_vs_sql_canon")),
            "wf84_vs_sql_canon": as_dict(sql_reference_consistency.get("wf84_vs_sql_canon")),
            "blocks_front_door": False if legacy_decoupled_warning else None,
        },
        "sql_canon_reference_authority": {
            "current_state_authority": sql_reference_available,
            "reference_source": "state/finance/finance-canon.sqlite:reference_levels",
            "json_proof_required_before_material_claims": True,
            "legacy_42_entry_stop_retirement_ready": sql_reference_available,
        },
        "front_door_policy": {
            "prefer_wf85_full_answer": status in {
                "ok",
                "ok_legacy_cache_hash_warning",
                "ok_sql_canon_authoritative",
                "ok_sql_canon_authoritative_legacy_decoupled",
            },
            "source_open_required_before_material_claims": True,
            "stale_entry_stop_cache_blocks_generated_answer": False
            if sql_reference_available
            else True,
            "legacy_compatibility_blocks_front_door": False if sql_reference_available else True,
        },
    }


def canonical_data_plane_switch_gate() -> dict[str, Any]:
    """Return the WF84 read-only default-route switch gate."""
    phase = load_json(CANONICAL_FINANCE_DATA_PLANE_PHASE, None)
    if not isinstance(phase, dict):
        return {
            "status": "disabled",
            "reason": "WF84 phase 6-10 proof missing or unreadable",
            "phase_path": rel(CANONICAL_FINANCE_DATA_PLANE_PHASE),
        }
    summary = phase.get("summary") if isinstance(phase.get("summary"), dict) else {}
    validation = phase.get("validation") if isinstance(phase.get("validation"), dict) else {}
    authority = phase.get("authority_boundary") if isinstance(phase.get("authority_boundary"), dict) else {}
    allowed = (
        phase.get("status") == "ok"
        and validation.get("status") == "ok"
        and summary.get("consumer_default_switch_allowed") is True
        and authority.get("default_route_switch_allowed") is True
        and authority.get("capital_deployment_allowed") is False
        and authority.get("trade_or_execution_approved") is False
        and authority.get("paper_or_live_execution_allowed") is False
        and authority.get("owner_approval_inferred") is False
    )
    return {
        "status": "enabled" if allowed else "disabled",
        "phase_path": rel(CANONICAL_FINANCE_DATA_PLANE_PHASE),
        "phase_generated_at_utc": phase.get("generated_at_utc"),
        "phase_status": phase.get("status"),
        "validation_status": validation.get("status"),
        "consumer_default_switch_allowed": summary.get("consumer_default_switch_allowed"),
        "default_route_switch_allowed": authority.get("default_route_switch_allowed"),
        "source_open_required_before_material_finance_claims": authority.get("source_open_required_before_material_finance_claims"),
        "fallback_surfaces_retained_for_resilience": True,
        "reason": "WF84 phase proof clean and switch allowed" if allowed else "WF84 phase proof has not enabled the default switch",
    }


def full_answer_parity_status(ticker: str) -> dict[str, Any]:
    """Return the full-answer parity gate for the ticker front door."""
    ticker = ticker.upper()
    rollup = load_json(FULL_ANSWER_PARITY_ROLLUP, {})
    ticker_path = FULL_ANSWER_PARITY_DIR / f"{ticker}.json"
    ticker_parity = load_json(ticker_path, {})
    rollup_summary = as_dict(as_dict(rollup).get("summary"))
    ticker_validation = as_dict(as_dict(ticker_parity).get("validation"))
    return {
        "ticker": ticker,
        "status": as_dict(ticker_parity).get("status") or "missing",
        "artifact": rel(ticker_path),
        "rollup_artifact": rel(FULL_ANSWER_PARITY_ROLLUP),
        "rollup_status": as_dict(rollup).get("status") or "missing",
        "critical_errors": ticker_validation.get("critical_errors") or [],
        "warnings": ticker_validation.get("warnings") or [],
        "ready_to_start_duplicate_surface_retirement_planning": bool(rollup_summary.get("ready_to_start_duplicate_surface_retirement_planning")),
        "full_answer_claim_mode": "wf84_wf85_full_answer_allowed" if as_dict(ticker_parity).get("status") == "ok" else "section_status_only_fail_closed",
        "source_open_required_before_material_claims": True,
        "archive_delete_apply_allowed": False,
    }


def trade_grade_full_answer_status(ticker: str) -> dict[str, Any]:
    """Return an existing full-answer compatibility descriptor, read-only."""
    ticker = ticker.upper()
    path = TRADE_GRADE_FULL_ANSWER_DIR / f"{ticker}.json"
    payload = load_json(path, None)
    if not isinstance(payload, dict):
        return {
            "ticker": ticker,
            "status": "missing",
            "artifact": rel(path),
            "rollup_artifact": rel(TRADE_GRADE_FULL_ANSWER_ROLLUP),
            "reason": "full-answer compatibility artifact missing; in-memory assembly is retired",
            "review_only": True,
            "source_open_required_before_material_claims": True,
            "archive_delete_apply_allowed": False,
        }
    validation = as_dict(payload.get("validation"))
    machine = as_dict(payload.get("machine_state"))
    sections = as_dict(payload.get("sections"))
    human_text = str(payload.get("human_answer_text") or "")
    return {
        "ticker": ticker,
        "status": payload.get("status") or validation.get("status") or "unknown",
        "artifact": rel(path),
        "rollup_artifact": rel(TRADE_GRADE_FULL_ANSWER_ROLLUP),
        "assembled_in_memory": False,
        "issues": [],
        "schema": payload.get("schema"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "section_count": len(sections),
        "required_section_count": len(payload.get("section_order") or []),
        "missing_sections": validation.get("missing_sections") or [],
        "machine_state": {
            "research_tier": machine.get("research_tier"),
            "decision_state": machine.get("decision_state"),
            "primary_state": machine.get("primary_state"),
            "queue_state": machine.get("queue_state"),
            "trade_grade": as_dict(machine.get("trade_grade")).get("grade"),
            "actionability": as_dict(machine.get("trade_grade")).get("actionability"),
            "owner_action": as_dict(machine.get("owner_action")).get("owner_action"),
        },
        "human_answer_text": human_text,
        "human_answer_preview": human_text[:1200],
        "answer_packet_role": "legacy_compatibility_snapshot_only",
        "review_only": True,
        "source_open_required_before_material_claims": True,
        "archive_delete_apply_allowed": False,
    }


def assert_wf72_support_only_answer_route(preferred_answer_source: str, answer_contract: dict[str, Any]) -> None:
    """Fail closed if WF72 is ever promoted into ticker answer ownership."""
    lowered_source = str(preferred_answer_source or "").lower()
    disallowed_source = lowered_source.startswith("wf72") or "wf72_sql" in lowered_source
    if disallowed_source:
        raise AssertionError("WF72 is support-only and must not be a finance answer source")
    if answer_contract.get("wf72_sql_cache_is_support_only") is not True:
        raise AssertionError("WF72 support-only contract missing")
    if answer_contract.get("wf72_finance_answer_front_door_allowed") is True:
        raise AssertionError("WF72 finance answer front-door authority is blocked")
    if answer_contract.get("prefer_wf85_full_answer_assembler_when_available") is not True:
        raise AssertionError("WF85 must remain the preferred full-answer route")


def ticker_packet(ticker: str, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    ticker = ticker.upper()
    with connect_ro(db_path) as conn:
        current = rows(conn, "SELECT * FROM all_ticker_sql_rows WHERE ticker=?", (ticker,))
        if not current:
            return {"status": "missing", "ticker": ticker, "db_path": rel(db_path)}
        entry_stop_rows = rows(conn, "SELECT * FROM entry_stop_reference WHERE ticker=?", (ticker,))
        entry_stop_reference = entry_stop_rows[0] if entry_stop_rows else {}
        entry_stop_guard = entry_stop_cache_freshness_guard(ticker, entry_stop_reference)
        answer_route = resolve_answer_packet(ticker)
        try:
            import finance_cache_frontdoor

            cache_frontdoor_payload = finance_cache_frontdoor.load_or_build_payload()
            cache_frontdoor_row = finance_cache_frontdoor.row_by_ticker(cache_frontdoor_payload, ticker)
            cache_frontdoor_context = {
                "status": cache_frontdoor_payload.get("status"),
                "path": "tmp/finance-cache-frontdoor.json",
                "generated_at_utc": cache_frontdoor_payload.get("generated_at_utc"),
                "row": cache_frontdoor_row,
                "route_readiness": as_dict(cache_frontdoor_row.get("route_readiness")),
                "routing_tier": cache_frontdoor_row.get("routing_tier"),
                "routing_state": cache_frontdoor_row.get("routing_state"),
                "timing_state": cache_frontdoor_row.get("timing_state"),
                "decision_state": cache_frontdoor_row.get("decision_state"),
                "trade_readiness_state": cache_frontdoor_row.get("trade_readiness_state"),
                "authority_state": cache_frontdoor_row.get("authority_state"),
                "summary": cache_frontdoor_payload.get("summary"),
            }
        except Exception as exc:
            cache_frontdoor_context = {
                "status": "unavailable",
                "path": "tmp/finance-cache-frontdoor.json",
                "reason": str(exc),
            }
        canonical_overlay = canonical_data_plane_overlay(ticker)
        canonical_switch = canonical_data_plane_switch_gate()
        full_parity = full_answer_parity_status(ticker)
        trade_grade_answer = trade_grade_full_answer_status(ticker)
        sql_canon_context = sql_canon_state_context(ticker)
        entry_stop_policy = as_dict(entry_stop_guard.get("front_door_policy"))
        entry_stop_cache_ok = entry_stop_policy.get("prefer_wf85_full_answer") is True
        sql_canon_ok = sql_canon_context.get("status") == "ok"
        canonical_default = canonical_switch.get("status") == "enabled" and canonical_overlay.get("status") == "ok" and entry_stop_cache_ok and sql_canon_ok
        if canonical_default and trade_grade_answer.get("status") == "ok":
            preferred_answer_source = "wf85_full_answer_assembler"
        elif canonical_default:
            preferred_answer_source = "wf84_canonical_data_plane"
        elif not sql_canon_ok:
            preferred_answer_source = "source_open_required_due_sql_canon_guard"
            trade_grade_answer = {
                **trade_grade_answer,
                "claim_mode": "blocked_by_sql_canon_guard",
                "sql_canon_guard_status": sql_canon_context.get("status"),
            }
        elif not entry_stop_cache_ok:
            preferred_answer_source = "source_open_required_due_entry_stop_cache_guard"
            trade_grade_answer = {
                **trade_grade_answer,
                "claim_mode": "blocked_by_entry_stop_cache_guard",
                "entry_stop_cache_guard_status": entry_stop_guard.get("status"),
            }
        else:
            preferred_answer_source = answer_route["preferred_source"]
        answer_contract = {
            "default_ticker_info_front_door": "python scripts\\finance_cache_frontdoor.py ticker <TICKER> --read-only --pretty",
            "deeper_ticker_envelope": "python scripts\\finance_intelligence_state.py ticker <TICKER> --pretty",
            "ticker_card_is_current_evidence_cache": True,
            "finance_cache_frontdoor_is_chat_read_facade": True,
            "sql_first_truth_production_cache_first_chat_consumption": True,
            "wf85_full_answer_assembler_is_default_full_answer_path": True,
            "answer_packet_is_legacy_compatibility_snapshot": True,
            "wf78_operational_surfaces_are_escalation_only": True,
            "wf72_sql_cache_is_support_only": True,
            "wf72_finance_answer_front_door_allowed": False,
            "may_answer_from_sql_for_inventory_or_routing": True,
            "durable_sql_canon_required_for_current_state": True,
            "finance_intelligence_state_sqlite_is_compatibility_cache": True,
            "prefer_answer_packet_when_present_and_fresh": False,
            "prefer_wf84_canonical_data_plane_when_phase_switch_enabled": True,
            "prefer_wf85_full_answer_assembler_when_available": True,
            "full_answer_parity_required_before_retiring_duplicate_surfaces": True,
            "canonical_data_plane_overlay_is_read_only_and_fallback_backed": True,
            "thin_monitor_rows_are_not_decision_grade": True,
            "material_finance_claim_requires_source_open": True,
            "must_not_infer_approval_or_execution_authority": True,
            "must_state_missing_or_stale_evidence": True,
        }
        assert_wf72_support_only_answer_route(preferred_answer_source, answer_contract)
        packet = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "artifact_type": "finance_intelligence_state_ticker_packet",
            "status": "ok" if sql_canon_ok else "blocked",
            "ticker": ticker,
            "db_path": rel(db_path),
            "front_door_role": {
                "default_for_ticker_questions": True,
                "purpose": "single ticker finance intelligence lookup envelope",
                "route_chain": "ticker request -> finance_cache_frontdoor -> WF84 data plane -> WF85 full answer/card -> source-open fallback when material or stale",
                "source_hierarchy": [
                    "Finance cache front door for lightweight chat answers and source-open/material-claim flags",
                    "WF85 full-answer assembler for section-level JSON plus human answer text when WF84/WF85 gates are clean",
                    "WF84 canonical data-plane overlay for read-only normalized routing/decision joins when available",
                    "WF72 entry/stop SQL cache as support/index infrastructure only, never the answer front door",
                    "legacy ticker_answer_packet compatibility snapshot when older consumers require it",
                    "current ticker_intelligence_card plus source artifacts when packet is stale or missing",
                    "WF78 repair/promotion surfaces only for repair, promotion, freshness debt, owner-card, or capital-review questions",
                ],
                "not_a_new_source_of_truth": True,
            },
            "preferred_answer_source": preferred_answer_source,
            "finance_cache_frontdoor": cache_frontdoor_context,
            "sql_canon_state": sql_canon_context,
            "answer_packet": answer_route,
            "canonical_data_plane_overlay": canonical_overlay,
            "entry_stop_cache_freshness_guard": entry_stop_guard,
            "canonical_data_plane_default_route": {
                "enabled": canonical_default,
                "switch_gate": canonical_switch,
                "preferred_source_when_enabled": "wf85_full_answer_assembler",
                "fallback_preferred_source": answer_route["preferred_source"],
                "entry_stop_cache_guard_status": entry_stop_guard.get("status"),
                "sql_canon_guard_status": sql_canon_context.get("status"),
                "source_open_required_before_material_claims": True,
                "does_not_authorize_capital_or_execution": True,
            },
            "full_intelligence_answer_parity": full_parity,
            "trade_grade_full_answer": trade_grade_answer,
            "current": current[0],
            "family_status": rows(conn, "SELECT * FROM ticker_family_status WHERE ticker=? ORDER BY family_id", (ticker,)),
            "entry_stop_reference": public_entry_stop_reference(entry_stop_reference),
            "disciplined_entry_band": disciplined_entry_band(ticker),
            "entry_stop_legacy_lineage": entry_stop_legacy_lineage(entry_stop_reference),
            "provenance": rows(conn, "SELECT * FROM artifact_provenance_map WHERE ticker=? ORDER BY source_kind, source_path", (ticker,)),
            "authority_boundary": authority_boundary(),
            "answer_contract": answer_contract,
        }
    atomic_write_json(DEFAULT_TICKER_PACKET, packet)
    return packet


def preopen_packet(db_path: Path = DEFAULT_DB, limit: int = 20) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        queue = rows(conn, "SELECT * FROM preopen_action_queue LIMIT ?", (limit,))
        stale = rows(conn, "SELECT * FROM stale_ticker_cards ORDER BY ticker LIMIT ?", (limit,))
        pending = rows(conn, "SELECT * FROM pending_approval_queue LIMIT ?", (limit,))
        validation = rows(conn, "SELECT * FROM latest_validator_status")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": "finance_intelligence_state_preopen_packet",
        "status": "ok",
        "db_path": rel(db_path),
        "queue": queue,
        "stale_ticker_cards": stale,
        "pending_approval_queue": pending,
        "validator_status": validation,
        "authority_boundary": authority_boundary(),
        "source_open_rule": "Use this compact SQL packet for routing/current-state triage only; open listed source artifacts and canonical owner notes before material finance claims.",
    }
    atomic_write_json(DEFAULT_PREOPEN_PACKET, packet)
    return packet


def stale_tickers_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        stale_rows = rows(conn, "SELECT * FROM stale_ticker_cards ORDER BY ticker LIMIT ?", (limit,))
    normalized = []
    for row in stale_rows:
        row = dict(row)
        row["missing_or_stale"] = parse_json_text(row.pop("missing_or_stale_json", "[]"), [])
        row["blockers"] = parse_json_text(row.pop("blockers_json", "[]"), [])
        normalized.append(row)
    packet = {
        **packet_header("finance_intelligence_state_stale_tickers_packet", db_path),
        "status": "ok",
        "count": len(normalized),
        "stale_ticker_cards": normalized,
    }
    return write_packet(DEFAULT_STALE_PACKET, packet)


def pending_approvals_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        pending_rows = rows(conn, "SELECT * FROM pending_approval_queue LIMIT ?", (limit,))
    normalized = []
    for row in pending_rows:
        row = dict(row)
        row["blockers"] = parse_json_text(row.pop("blockers_json", "[]"), [])
        normalized.append(row)
    packet = {
        **packet_header("finance_intelligence_state_pending_approvals_packet", db_path),
        "status": "ok",
        "count": len(normalized),
        "pending_approval_queue": normalized,
        "review_boundary": "Rows are review/promotion/approval-prep routing only; they do not grant owner approval or execution authority.",
    }
    return write_packet(DEFAULT_PENDING_PACKET, packet)


def validator_status_packet(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        validator_rows = rows(conn, "SELECT * FROM latest_validator_status")
    normalized = []
    for row in validator_rows:
        row = dict(row)
        row["detail"] = parse_json_text(row.pop("detail_json", "{}"), {})
        normalized.append(row)
    error_failures = [row for row in normalized if row.get("severity") == "error" and row.get("status") != "ok"]
    packet = {
        **packet_header("finance_intelligence_state_validator_status_packet", db_path),
        "status": "ok" if not error_failures else "blocked",
        "error_failures": len(error_failures),
        "validator_status": normalized,
    }
    return write_packet(DEFAULT_VALIDATOR_PACKET, packet)


def source_proof_packet(ticker: str, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    ticker = ticker.upper()
    with connect_ro(db_path) as conn:
        proof_rows = rows(conn, "SELECT * FROM artifact_provenance_map WHERE ticker=? ORDER BY source_kind, source_path", (ticker,))
        owner_rows = rows(conn, "SELECT ticker, owner_note_path, source_artifact_path, source_artifact_hash, source_timestamp, freshness_status, validation_status FROM entry_stop_reference WHERE ticker=?", (ticker,))
        card_rows = rows(conn, "SELECT ticker, card_path, card_generated_at_utc, source_open_required FROM card_registry WHERE ticker=?", (ticker,))
    packet = {
        **packet_header("finance_intelligence_state_source_proof_packet", db_path),
        "status": "ok" if proof_rows else "missing",
        "ticker": ticker,
        "card": card_rows[0] if card_rows else None,
        "entry_stop_owner_proof": owner_rows[0] if owner_rows else None,
        "provenance": proof_rows,
        "source_open_rule": "Open the listed source artifact or owner note before making a material finance, readiness, recommendation, or authority claim.",
    }
    return write_packet(DEFAULT_SOURCE_PROOF_PACKET, packet)


def entry_stop_refs_packet(
    db_path: Path = DEFAULT_DB,
    ticker: str | None = None,
    limit: int = 100,
    *,
    write_output: bool = True,
) -> dict[str, Any]:
    client = FinanceSqlCanonAccess()
    reference_records = client.reference_level_records([ticker] if ticker else None)
    canonical_ticker = next(iter(reference_records), None) if ticker else None
    selected_records = [
        record
        for record in reference_records.values()
        if record is not None
    ][:limit]
    canon_context = sql_canon_state_context(canonical_ticker)
    trimmed = []
    for record in selected_records:
        row = reference_level_record_as_entry_stop_row(record)
        guard = entry_stop_cache_freshness_guard(row["ticker"], row)
        trimmed.append({
            "ticker": row["ticker"],
            "entry_band_low": row["entry_band_low"],
            "entry_band_high": row["entry_band_high"],
            "stop_or_invalidation": row["stop_or_invalidation"],
            "sql_canon_reference_overlay": sql_canon_reference_overlay(row["ticker"]),
            "sql_first_reference_metadata": build_entry_stop_reference_metadata(row["ticker"], record),
            "freshness_status": row["freshness_status"],
            "validation_status": row["validation_status"],
            "owner_note_path": row["owner_note_path"],
            "source_artifact_path": row["source_artifact_path"],
            "source_artifact_hash": row["source_artifact_hash"],
            "current_owner_source_hash": guard.get("owner_source_sha256"),
            "compatibility_source_hash_status": guard.get("status"),
            "compatibility_source_hash_blocks_front_door": as_dict(guard.get("front_door_policy")).get("stale_entry_stop_cache_blocks_generated_answer"),
            "legacy_source_hash_warning": as_dict(guard.get("legacy_compatibility_hash_warning")).get("present") is True,
            "legacy_source_hash_warning_reason": as_dict(guard.get("legacy_compatibility_hash_warning")).get("reason"),
            "source_timestamp": row["source_timestamp"],
            "reference_source_surface": row.get("reference_source_surface") or "tmp/finance-intelligence-state.sqlite:latest_valid_entry_stop_refs",
        })
    blocked_overlays = [
        row["ticker"]
        for row in trimmed
        if as_dict(row.get("sql_canon_reference_overlay")).get("status") != "ok"
    ]
    if ticker and canonical_ticker and reference_records.get(canonical_ticker) is None:
        blocked_overlays.append(canonical_ticker)
    packet = {
        **packet_header("finance_intelligence_state_entry_stop_refs_packet", db_path),
        "status": "ok" if not blocked_overlays else "blocked",
        "ticker": canonical_ticker,
        "count": len(trimmed),
        "sql_first_read_scope": "Durable SQL-canon reference_levels/evidence_freshness/source_lineage are the guarded internal current-state layer for the dynamic active universe. Legacy WF72/finance-intelligence compatibility caches are support-only lineage; stale whole-file source hashes do not block the front door when SQL-canon, WF84, and finance-state reference values match. Review-monitor rows still require source-open proof before material finance claims.",
        "sql_canon_field_family_summary": canon_context.get("field_family_summary"),
        "sql_canon_reference_overlay_blocked": blocked_overlays,
        "sql_first_consumer_migration_performed": True,
        "markdown_owner_fallback_required": True,
        "entry_stop_refs": trimmed,
        "cache_boundary": "Validated metadata/reference cache only; not recommendation, deployment, approval, or execution authority.",
    }
    return write_packet(DEFAULT_ENTRY_STOP_PACKET, packet) if write_output else packet


def action_queue_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        queue = rows(conn, "SELECT * FROM preopen_action_queue LIMIT ?", (limit,))
    packet = {
        **packet_header("finance_intelligence_state_action_queue_packet", db_path),
        "status": "ok",
        "count": len(queue),
        "queue": queue,
        "queue_boundary": "Queue order is triage/routing only. It is not approval, sizing, cash/risk-rule, paper, live, or account authority.",
    }
    return write_packet(DEFAULT_ACTION_QUEUE_PACKET, packet)


def pilot_fixtures_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        fixtures = rows(conn, "SELECT * FROM current_pilot_fixtures LIMIT ?", (limit,))
        production_overlap = scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
        review_100_count = int(scalar(
            conn,
            "SELECT COUNT(*) FROM universe WHERE universe_scope=? AND thin_monitor_row=1",
            (REVIEW_100_SCOPE,),
        ) or 0)
    trimmed = [
        {
            "ticker": row["ticker"],
            "name": row["name"],
            "tier": row["tier"],
            "instrument_type": row["instrument_type"],
            "monitoring_role": row["monitoring_role"],
            "sector": row["sector"],
            "industry": row["industry"],
            "pilot_status": row["pilot_status"],
            "thin_row_only": bool(row["thin_row_only"]),
            "on_demand_card_required_before_claim": bool(row["on_demand_card_required_before_claim"]),
            "provider_telemetry_required": bool(row["provider_telemetry_required"]),
            "stale_but_known_disclosure_required": bool(row["stale_but_known_disclosure_required"]),
        }
        for row in fixtures
    ]
    packet = {
        **packet_header("finance_intelligence_state_pilot_fixtures_packet", db_path),
        "status": "ok" if (trimmed or review_100_count in SUPPORTED_REVIEW_MONITOR_COUNTS) and production_overlap == 0 else "blocked",
        "count": len(trimmed),
        "production_overlap_count": production_overlap,
        "review_100_monitor_count": review_100_count,
        "pilot_fixtures": trimmed,
        "pilot_boundary": {
            "thin_sql_rows_only": True,
            "on_demand_cards_required_before_material_claims": True,
            "excluded_from_dynamic_production_cards": production_overlap == 0,
            "provider_telemetry_required_before_live_pilot": True,
            "no_broad_import_or_production_overwrite": True,
            "pilot_fixtures_may_be_converted_to_review_100_monitor_scope": True,
        },
    }
    return write_packet(DEFAULT_PILOT_FIXTURE_PACKET, packet)


def live_pilot_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    if not db_path.exists():
        packet = {
            **packet_header("finance_intelligence_state_live_pilot_packet", db_path),
            "status": "missing",
            "count": 0,
            "candidates": [],
            "validation": {
                "status": "blocked",
                "checks": [{"name": "finance_intelligence_state_db_present", "ok": False, "severity": "error", "detail": rel(db_path)}],
            },
        }
        return write_packet(DEFAULT_LIVE_PILOT_PACKET, packet)

    with connect_ro(db_path) as conn:
        live_view_exists = scalar(conn, "SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name='current_live_pilot_candidates'")
        if not live_view_exists:
            packet = {
                **packet_header("finance_intelligence_state_live_pilot_packet", db_path),
                "status": "missing",
                "count": 0,
                "candidates": [],
                "validation": {
                    "status": "blocked",
                    "checks": [{"name": "current_live_pilot_candidates_view_present", "ok": False, "severity": "error", "detail": "view missing"}],
                },
                "live_pilot_boundary": {
                    "isolated_sql_surface_only": True,
                    "dynamic_production_answer_path_unchanged": True,
                    "material_claim_requires_source_open": True,
                },
            }
            return write_packet(DEFAULT_LIVE_PILOT_PACKET, packet)
        candidates = rows(conn, "SELECT * FROM current_live_pilot_candidates LIMIT ?", (limit,))
        candidate_count = scalar(conn, "SELECT COUNT(*) FROM current_live_pilot_candidates")
        provider_ok = scalar(conn, "SELECT COUNT(*) FROM live_pilot_provider_status WHERE provider_status='ok'")
        production_overlap = scalar(conn, "SELECT COUNT(*) FROM live_pilot_candidate_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
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
    checks = [
        {"name": "live_pilot_rows_present", "ok": candidate_count > 0, "severity": "error", "detail": {"rows": candidate_count}},
        {"name": "live_pilot_rows_isolated_from_production", "ok": production_overlap == 0, "severity": "error", "detail": {"rows": production_overlap}},
        {"name": "live_pilot_authority_flags_false", "ok": bad_authority == 0, "severity": "error", "detail": {"rows": bad_authority}},
        {"name": "live_pilot_provider_status_present", "ok": provider_ok > 0, "severity": "error", "detail": {"provider_ok": provider_ok}},
    ]
    failed = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    packet = {
        **packet_header("finance_intelligence_state_live_pilot_packet", db_path),
        "status": "ok" if not failed else "blocked",
        "count": len(candidates),
        "total_count": candidate_count,
        "provider_ok_count": provider_ok,
        "production_overlap_count": production_overlap,
        "candidates": candidates,
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed_checks": failed},
        "live_pilot_boundary": {
            "isolated_sql_surface_only": True,
            "dynamic_production_answer_path_unchanged": production_overlap == 0,
            "thin_or_on_demand_only": True,
            "material_claim_requires_source_open": True,
            "no_canon_portfolio_or_execution_authority": True,
        },
    }
    return write_packet(DEFAULT_LIVE_PILOT_PACKET, packet)


def paper_positions_packet(paper_db_path: Path = PAPER_POSITION_DB) -> dict[str, Any]:
    if not paper_db_path.exists():
        packet = {
            **packet_header("finance_intelligence_state_paper_positions_packet", paper_db_path),
            "authority_boundary": paper_position_authority_boundary(paper_db_path),
            "status": "missing",
            "freshness": {"status": "missing"},
            "account_summary": {},
            "positions": [],
            "validation": {
                "status": "blocked",
                "checks": [{"name": "paper_position_db_present", "ok": False, "severity": "error", "detail": rel(paper_db_path)}],
            },
            "paper_boundary": {
                "paper_position_sql_state_only": True,
                "no_paper_submit_cancel_sell_authority": True,
                "no_live_trade_or_account_authority": True,
                "json_markdown_exports_are_not_truth_owner": True,
            },
        }
        return write_packet(DEFAULT_PAPER_POSITIONS_PACKET, packet)

    try:
        with connect_ro(paper_db_path) as conn:
            latest_rows = rows(
                conn,
                """
                SELECT a.*, f.status AS freshness_status, f.age_seconds, f.stale_threshold_seconds
                FROM paper_account_snapshot a
                JOIN paper_position_freshness f ON f.snapshot_id = a.snapshot_id
                ORDER BY a.generated_at_utc DESC
                LIMIT 1
                """,
            )
            latest_ok_rows = rows(
                conn,
                """
                SELECT *
                FROM paper_account_snapshot
                WHERE status = 'ok'
                ORDER BY generated_at_utc DESC
                LIMIT 1
                """,
            )
            position_rows = rows(conn, "SELECT * FROM current_paper_positions")
            integrity = scalar(conn, "PRAGMA integrity_check")
            fk_rows = rows(conn, "PRAGMA foreign_key_check")
            ok_snapshot_rows = scalar(conn, "SELECT COUNT(*) FROM paper_account_snapshot WHERE status='ok'")
            forbidden_rows = scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM paper_account_snapshot
                WHERE paper_submit_allowed != 0
                   OR paper_cancel_allowed != 0
                   OR live_trade_or_account_action_allowed != 0
                   OR trade_or_account_action_allowed != 0
                   OR money_movement_allowed != 0
                   OR account_settings_mutation_allowed != 0
                   OR owner_approval_inferred != 0
                """,
            )
    except sqlite3.Error as exc:
        packet = {
            **packet_header("finance_intelligence_state_paper_positions_packet", paper_db_path),
            "authority_boundary": paper_position_authority_boundary(paper_db_path),
            "status": "blocked",
            "freshness": {"status": "blocked"},
            "account_summary": {},
            "positions": [],
            "validation": {
                "status": "blocked",
                "checks": [{"name": "paper_position_db_readable", "ok": False, "severity": "error", "detail": type(exc).__name__}],
            },
        }
        return write_packet(DEFAULT_PAPER_POSITIONS_PACKET, packet)

    latest = latest_rows[0] if latest_rows else {}
    latest_ok = latest_ok_rows[0] if latest_ok_rows else {}
    summary = latest_ok if latest.get("status") == "blocked" and latest_ok else latest
    last_known_positions_status = "current" if latest.get("status") == "ok" else ("stale_but_known" if latest_ok else "unavailable")
    checks = [
        {"name": "integrity_check_ok", "ok": integrity == "ok", "severity": "error", "detail": integrity},
        {"name": "foreign_key_check_ok", "ok": len(fk_rows) == 0, "severity": "error", "detail": {"rows": len(fk_rows)}},
        {"name": "paper_snapshot_present", "ok": bool(latest_rows), "severity": "error", "detail": {"rows": len(latest_rows)}},
        {"name": "ok_snapshot_available_for_current_positions", "ok": ok_snapshot_rows >= 1 or latest.get("status") == "blocked", "severity": "warning", "detail": {"rows": ok_snapshot_rows}},
        {"name": "forbidden_authority_flags_false", "ok": forbidden_rows == 0, "severity": "error", "detail": {"rows": forbidden_rows}},
        {
            "name": "paper_position_freshness_fresh",
            "ok": latest.get("freshness_status") == "fresh",
            "severity": "warning",
            "detail": {"freshness_status": latest.get("freshness_status"), "generated_at_utc": latest.get("generated_at_utc")},
        },
    ]
    validation_status = "ok" if not [check for check in checks if not check["ok"] and check["severity"] == "error"] else "blocked"
    packet = {
        **packet_header("finance_intelligence_state_paper_positions_packet", paper_db_path),
        "authority_boundary": paper_position_authority_boundary(paper_db_path),
        "status": "ok" if validation_status == "ok" and latest.get("status") == "ok" else latest.get("status", validation_status),
        "freshness": {
            "status": latest.get("freshness_status", "missing"),
            "generated_at_utc": latest.get("generated_at_utc"),
            "age_seconds": latest.get("age_seconds"),
            "stale_threshold_seconds": latest.get("stale_threshold_seconds"),
            "latest_successful_snapshot_at_utc": latest_ok.get("generated_at_utc"),
            "last_known_positions_status": last_known_positions_status,
        },
        "latest_refresh": {
            "snapshot_id": latest.get("snapshot_id"),
            "status": latest.get("status", validation_status),
            "generated_at_utc": latest.get("generated_at_utc"),
            "validation_findings": parse_json_text(latest.get("validation_findings_json"), []),
        },
        "account_summary": {
            "account_mode": summary.get("account_mode"),
            "endpoint": summary.get("endpoint"),
            "method": summary.get("method"),
            "equity": summary.get("equity"),
            "cash": summary.get("cash"),
            "buying_power": summary.get("buying_power"),
            "portfolio_value": summary.get("portfolio_value"),
            "positions_count": summary.get("positions_count"),
            "orders_count": summary.get("orders_count"),
            "open_orders_count": summary.get("open_orders_count"),
            "last_successful_snapshot_id": latest_ok.get("snapshot_id"),
            "last_successful_snapshot_at_utc": latest_ok.get("generated_at_utc"),
        },
        "positions": position_rows,
        "validation": {"status": validation_status, "checks": checks},
        "paper_boundary": {
            "paper_position_sql_state_only": True,
            "no_paper_submit_cancel_sell_authority": True,
            "no_live_trade_or_account_authority": True,
            "no_owner_approval_inference": True,
            "json_markdown_exports_are_not_truth_owner": True,
            "canon_cache_used_for_paper_positions": False,
            "artifact_index_is_state_owner": False,
        },
        "source_open_rule": "Use this packet for paper-position routing/current-state only. Stale, missing, or blocked freshness must be disclosed before paper-advisor context.",
    }
    return write_packet(DEFAULT_PAPER_POSITIONS_PACKET, packet)


def phase3_qc_sample_tickers(
    requested: Iterable[str] | None,
    default_count: int = 4,
) -> list[str]:
    client = FinanceSqlCanonAccess()
    if requested is None:
        return list(client.universe_memberships())[:default_count]
    requested_list = [str(item) for item in requested]
    resolved = client.resolve_tickers(requested_list)
    canonical: list[str] = []
    seen: set[str] = set()
    for item in requested_list:
        ticker = resolved[str(item).strip().upper()]
        if ticker not in seen:
            seen.add(ticker)
            canonical.append(ticker)
    return canonical


def phase3_qc_packet(db_path: Path = DEFAULT_DB, sample_tickers: list[str] | None = None) -> dict[str, Any]:
    sample_tickers = phase3_qc_sample_tickers(sample_tickers)
    validation = validate_state(db_path)
    samples = {ticker: ticker_packet(ticker, db_path) for ticker in sample_tickers}
    preopen = preopen_packet(db_path, limit=10)
    stale = stale_tickers_packet(db_path, limit=10)
    pending = pending_approvals_packet(db_path, limit=20)
    validators = validator_status_packet(db_path)
    entry_refs = entry_stop_refs_packet(db_path, limit=50)
    pilot_fixtures = pilot_fixtures_packet(db_path, limit=50)
    source_proofs = {ticker: source_proof_packet(ticker, db_path) for ticker in sample_tickers}

    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "", severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    add("state_validation_ok", validation.get("status") == "ok", validation.get("summary"))
    add("sample_ticker_packets_ok", all(packet.get("status") == "ok" for packet in samples.values()), {ticker: packet.get("status") for ticker, packet in samples.items()})
    add("sample_packets_source_open_required", all(packet.get("answer_contract", {}).get("material_finance_claim_requires_source_open") is True for packet in samples.values()))
    add("preopen_packet_ok", preopen.get("status") == "ok" and len(preopen.get("queue") or []) > 0, {"rows": len(preopen.get("queue") or [])})
    add("pending_packet_ok", pending.get("status") == "ok", {"rows": pending.get("count")})
    add("validator_packet_ok", validators.get("status") == "ok", {"error_failures": validators.get("error_failures")})
    add("entry_stop_refs_packet_has_rows", entry_refs.get("status") == "ok" and int(entry_refs.get("count") or 0) > 0, {"rows": entry_refs.get("count")})
    add("pilot_fixtures_packet_ok", pilot_fixtures.get("status") == "ok", {"rows": pilot_fixtures.get("count"), "production_overlap_count": pilot_fixtures.get("production_overlap_count")})
    add("source_proof_packets_ok", all(packet.get("status") == "ok" for packet in source_proofs.values()), {ticker: packet.get("status") for ticker, packet in source_proofs.items()})

    all_packets = [validation, preopen, stale, pending, validators, entry_refs, pilot_fixtures, *samples.values(), *source_proofs.values()]
    forbidden_flags = [
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "owner_approval_inferred",
        "paper_trade_execution_allowed",
        "live_trade_or_account_action_allowed",
        "full_sql_canon_migration_allowed",
        "sql_canon_authority_expanded",
        "tmp_database_promotion_performed",
        "database_path_migration_performed",
    ]
    forbidden_true = []
    for packet in all_packets:
        boundary = as_dict(packet.get("authority_boundary"))
        for flag in forbidden_flags:
            if boundary.get(flag) is True:
                forbidden_true.append({"artifact_type": packet.get("artifact_type"), "flag": flag})
    add("all_query_packets_preserve_forbidden_authority_false", not forbidden_true, forbidden_true)
    status = "ok" if all(check["ok"] or check["severity"] == "warning" for check in checks) and not [c for c in checks if not c["ok"] and c["severity"] == "error"] else "blocked"
    packet = {
        **packet_header("finance_intelligence_state_phase3_qc", db_path),
        "status": status,
        "phase": "WF78 Phase 3",
        "sample_tickers": sample_tickers,
        "checks": checks,
        "generated_packets": {
            "validation": rel(DEFAULT_VALIDATION),
            "ticker_packet": rel(DEFAULT_TICKER_PACKET),
            "preopen": rel(DEFAULT_PREOPEN_PACKET),
            "stale_tickers": rel(DEFAULT_STALE_PACKET),
            "pending_approvals": rel(DEFAULT_PENDING_PACKET),
            "validator_status": rel(DEFAULT_VALIDATOR_PACKET),
            "source_proof": rel(DEFAULT_SOURCE_PROOF_PACKET),
            "entry_stop_refs": rel(DEFAULT_ENTRY_STOP_PACKET),
            "action_queue": rel(DEFAULT_ACTION_QUEUE_PACKET),
            "pilot_fixtures": rel(DEFAULT_PILOT_FIXTURE_PACKET),
            "live_pilot": rel(DEFAULT_LIVE_PILOT_PACKET),
            "paper_positions": rel(DEFAULT_PAPER_POSITIONS_PACKET),
        },
        "scope_boundary": "Read-only query surface over internal SQL-canon primary guarded current-state plus the legacy compatibility cache where still required. No database path move, no tmp promotion, no retail/customer activation, and no capital/execution authority expansion.",
    }
    return write_packet(DEFAULT_PHASE3_QC, packet)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "build", "refresh-100", "validate", "ticker", "preopen", "stale-tickers",
            "pending-approvals", "validator-status", "source-proof",
            "entry-stop-refs", "action-queue", "pilot-fixtures", "live-pilot", "phase3-qc", "paper-positions",
        ],
    )
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sample-tickers")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.command == "build":
        result = build_state(db_path)
    elif args.command == "refresh-100":
        result = refresh_100_packet(db_path)
    elif args.command == "validate":
        result = validate_state(db_path)
    elif args.command == "ticker":
        if not args.ticker:
            parser.error("ticker command requires a ticker")
        result = ticker_packet(args.ticker, db_path)
    elif args.command == "preopen":
        result = preopen_packet(db_path, args.limit)
    elif args.command == "stale-tickers":
        result = stale_tickers_packet(db_path, args.limit)
    elif args.command == "pending-approvals":
        result = pending_approvals_packet(db_path, args.limit)
    elif args.command == "validator-status":
        result = validator_status_packet(db_path)
    elif args.command == "source-proof":
        if not args.ticker:
            parser.error("source-proof command requires a ticker")
        result = source_proof_packet(args.ticker, db_path)
    elif args.command == "entry-stop-refs":
        result = entry_stop_refs_packet(db_path, args.ticker, args.limit)
    elif args.command == "action-queue":
        result = action_queue_packet(db_path, args.limit)
    elif args.command == "pilot-fixtures":
        result = pilot_fixtures_packet(db_path, args.limit)
    elif args.command == "live-pilot":
        result = live_pilot_packet(db_path, args.limit)
    elif args.command == "paper-positions":
        result = paper_positions_packet(PAPER_POSITION_DB)
    else:
        sample_tickers = (
            [item.strip() for item in args.sample_tickers.split(",") if item.strip()]
            if args.sample_tickers
            else None
        )
        result = phase3_qc_packet(db_path, sample_tickers)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("status") in {"ok", "ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
