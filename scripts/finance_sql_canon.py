#!/usr/bin/env python3
"""Build the first durable finance SQL canon candidate.

This is the Phase 1 promotion path from JSON-first WF78 universe metadata into
a durable state/finance SQLite store. It does not authorize portfolio changes,
customer output, paper/live execution, or brokerage/account action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json  # noqa: E402

STATE = ROOT / "state" / "finance"
DATA_FINANCE = ROOT / "data" / "finance"
TMP = ROOT / "tmp"
BACKUPS = ROOT / "backups" / "finance-sql-canon-promotion"

DB_PATH = STATE / "finance-canon.sqlite"
REPORT_PATH = TMP / "finance-sql-canon-promotion.json"
ARCHIVE_PLAN_PATH = TMP / "finance-sql-canon-legacy-42-archive-plan.json"
UNIVERSE_PATH = DATA_FINANCE / "universe-v1.json"
AUTO_ROUTER_PATH = TMP / "wf78-auto-tier-routing.json"
FRESHNESS_PATH = TMP / "wf78-tier-weighted-freshness-resolution.json"

# Production-scope proof join. Routing auto_tier is the single tier authority because it already
# drives required_depth in the freshness resolver; universe_membership.tier is the derived
# coverage obligation. "resolved_thin_monitor_current" only means staleness is tolerable at
# C-tier monitor depth, so "fresh" is the one state that clears full decision-grade depth.
PROOF_JOIN_TIERS = {"A", "B"}
PROOF_JOIN_FRESH_STATES = {"fresh"}
# The router demotes a name to *-CHALLENGED when its Tier A confidence gate finds a critical
# fundamentals conflict. Recommendation-grade output must not inherit a name the router itself
# demoted, so the join fails closed on anything other than an explicit "ready" with zero conflicts.
PROOF_JOIN_CONFIDENCE_STATUS = "ready"

RETIRED_PRODUCTION_SCOPE = "production_current_42"
PRODUCTION_SCOPE = "active_internal_universe"
REVIEW_100_SCOPE = "review_100_monitor"
EXPECTED_RETIRED_LEGACY_COUNT = 0
SUPPORTED_ACTIVE_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}
MIGRATION_MARKER_EVENT_TYPE = "alerts_os_sql_canon_migration"

AUTHORITY_BOUNDARY = {
    "workspace_sql_canon_promotion_allowed_by_owner_request": True,
    "sql_machine_canon_candidate": True,
    "json_remains_audit_and_rebuild_proof": True,
    "markdown_remains_human_judgment_layer": True,
    "production_42_archive_apply_allowed_by_this_script": False,
    "portfolio_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred_for_capital_action": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def active_entries(universe: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in universe.get("entries", []) if isinstance(row, dict) and row.get("active") is True]


def computed_summary(universe: dict[str, Any]) -> dict[str, Any]:
    entries = active_entries(universe)
    by_scope = Counter(str(row.get("universe_scope", PRODUCTION_SCOPE)) for row in entries)
    by_tier = Counter(str(row.get("tier") or "unknown") for row in entries)
    by_type = Counter(str(row.get("instrument_type") or "unknown") for row in entries)
    # Derived from source artifacts rather than read back from the DB: this runs while the
    # rebuild transaction is still constructing the SQL-first scope, so a DB read here would
    # always see an empty set. validate_db checks the built DB against this same rule.
    production_scope_ticker_set = proof_join_expected_tickers(universe)
    retired_legacy_tickers = sorted(
        {
            str(row.get("ticker", "")).upper()
            for row in entries
            if row.get("universe_scope") == RETIRED_PRODUCTION_SCOPE
        }
    )
    return {
        "active_ticker_count": len(entries),
        "production_active_ticker_count": len(production_scope_ticker_set),
        "review_100_monitor_count": by_scope.get(REVIEW_100_SCOPE, 0),
        "pilot_fixture_count": by_scope.get("pilot_fixture", 0),
        "tier_counts": dict(sorted(by_tier.items())),
        "instrument_type_counts": dict(sorted(by_type.items())),
        "review_100_monitor_tickers": sorted(
            str(row.get("ticker", "")).upper()
            for row in entries
            if row.get("universe_scope") == REVIEW_100_SCOPE
        ),
        "retired_legacy_42_tickers": retired_legacy_tickers,
        "retired_legacy_42_count": len(retired_legacy_tickers),
        "retired_legacy_42_source": "source_universe_retired_label_audit_only",
        "legacy_production_42_tickers": retired_legacy_tickers,
        "legacy_production_42_source": "retired_compatibility_summary_only",
    }


def sync_universe_summary(universe: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    expected = computed_summary(universe)
    existing = universe.get("summary") if isinstance(universe.get("summary"), dict) else {}
    stale = any(existing.get(key) != expected.get(key) for key in [
        "active_ticker_count",
        "production_active_ticker_count",
        "review_100_monitor_count",
        "pilot_fixture_count",
    ])
    universe["summary"] = {**existing, **expected}
    if (
        expected["active_ticker_count"] in SUPPORTED_ACTIVE_COUNTS
        and expected["production_active_ticker_count"] == len(proof_join_expected_tickers(universe))
        and expected["retired_legacy_42_count"] == EXPECTED_RETIRED_LEGACY_COUNT
        and expected["review_100_monitor_count"] in SUPPORTED_REVIEW_MONITOR_COUNTS
    ):
        universe["status"] = "wf78_tier_c_scaleout_monitor_ready"
    else:
        universe["status"] = "needs_review"
    universe["generated_at_utc"] = utc_now()
    return universe, stale


def backup_inputs(run_id: str, files: list[Path]) -> dict[str, Any]:
    backup_dir = BACKUPS / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for path in files:
        if not path.exists() or not path.is_file():
            copied.append({"path": rel(path), "exists": False})
            continue
        target = backup_dir / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append({
            "path": rel(path),
            "backup_path": rel(target),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "rollback": f"Copy {rel(target)} back to {rel(path)}",
            "exists": True,
        })
    manifest = {
        "schema_version": "finance_sql_canon_backup_manifest.v1",
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "authority_boundary": {
            "backup_only": True,
            "delete_allowed": False,
            "archive_move_allowed": False,
            "portfolio_or_trade_authority": False,
        },
        "files": copied,
    }
    write_json(backup_dir / "manifest.json", manifest)
    return {"backup_dir": rel(backup_dir), "manifest": rel(backup_dir / "manifest.json"), "files": copied}


def apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA temp_store=MEMORY")


# These tables survive a rebuild only through the fetch-before/restore-after mechanism below:
# DROP TABLE securities fires their ON DELETE CASCADE foreign keys, so any ticker-keyed
# extension table with that FK must be listed here or a rebuild silently empties it
# (disciplined_reference_levels lost its rows exactly this way before 2026-09-27).
PRESERVED_EXTENSION_TABLES = ("reference_levels", "evidence_freshness", "disciplined_reference_levels")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def fetch_preserved_extension_rows(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    preserved: dict[str, list[dict[str, Any]]] = {}
    for table in PRESERVED_EXTENSION_TABLES:
        if not table_exists(conn, table):
            preserved[table] = []
            continue
        columns = table_columns(conn, table)
        if "ticker" not in columns:
            preserved[table] = []
            continue
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        preserved[table] = [dict(zip(columns, row)) for row in rows]
    return preserved


def restore_preserved_extension_rows(
    conn: sqlite3.Connection,
    preserved: dict[str, list[dict[str, Any]]],
    universe: dict[str, Any],
) -> dict[str, int]:
    active_tickers = {
        str(row.get("ticker", "")).upper()
        for row in active_entries(universe)
        if row.get("ticker")
    }
    restored: dict[str, int] = {}
    for table, rows in preserved.items():
        restored[table] = 0
        if not rows or not table_exists(conn, table):
            continue
        current_columns = table_columns(conn, table)
        insert_columns = [column for column in current_columns if any(column in row for row in rows)]
        if "ticker" not in insert_columns:
            continue
        placeholders = ", ".join("?" for _ in insert_columns)
        column_sql = ", ".join(insert_columns)
        sql = f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({placeholders})"
        for row in rows:
            ticker = str(row.get("ticker", "")).upper()
            if ticker not in active_tickers:
                continue
            values = [row.get(column) for column in insert_columns]
            before = conn.total_changes
            conn.execute(sql, values)
            if conn.total_changes > before:
                restored[table] += 1
    return restored


SCHEMA_SQL = """
        DROP VIEW IF EXISTS current_active_universe;
        DROP VIEW IF EXISTS current_answer_path;
        DROP VIEW IF EXISTS review_monitor_universe;
        DROP TABLE IF EXISTS audit_events;
        DROP TABLE IF EXISTS archive_candidates;
        DROP TABLE IF EXISTS validator_runs;
        DROP TABLE IF EXISTS answer_path_scope;
        DROP TABLE IF EXISTS evidence_status;
        DROP TABLE IF EXISTS source_artifacts;
        DROP TABLE IF EXISTS universe_membership;
        DROP TABLE IF EXISTS securities;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE securities (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            instrument_type TEXT NOT NULL,
            sector TEXT,
            industry TEXT,
            yfinance_symbol TEXT,
            sec_cik TEXT,
            company_ir TEXT,
            active INTEGER NOT NULL CHECK(active IN (0, 1))
        );

        CREATE TABLE universe_membership (
            ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
            universe_scope TEXT NOT NULL,
            tier TEXT NOT NULL CHECK(tier IN ('A', 'B', 'C', 'D')),
            -- Same value as tier, named for what it actually means: the validator-enforced data
            -- coverage obligation (A/B = daily band/stop/technical, C/D = weekly). Live opportunity
            -- ranking is tier_routing_state.auto_tier and is a different semantic.
            coverage_obligation_tier TEXT NOT NULL CHECK(coverage_obligation_tier IN ('A', 'B', 'C', 'D')),
            monitoring_role TEXT NOT NULL,
            production_scope_member INTEGER NOT NULL DEFAULT 0 CHECK(production_scope_member IN (0, 1)),
            production_scope_source TEXT,
            sql_tier TEXT,
            sql_tier_state TEXT,
            tier_decision_scope TEXT,
            review_100_monitor INTEGER NOT NULL CHECK(review_100_monitor IN (0, 1)),
            decision_grade_eligible INTEGER NOT NULL CHECK(decision_grade_eligible IN (0, 1)),
            source_open_required INTEGER NOT NULL CHECK(source_open_required IN (0, 1)),
            promotion_required_before_action INTEGER NOT NULL CHECK(promotion_required_before_action IN (0, 1)),
            raw_json TEXT NOT NULL
        );

        CREATE TABLE source_artifacts (
            artifact_path TEXT PRIMARY KEY,
            artifact_role TEXT NOT NULL,
            exists_on_disk INTEGER NOT NULL CHECK(exists_on_disk IN (0, 1)),
            sha256 TEXT,
            generated_at_utc TEXT,
            validator_status TEXT
        );

        CREATE TABLE evidence_status (
            ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
            has_production_card INTEGER NOT NULL CHECK(has_production_card IN (0, 1)),
            card_path TEXT,
            coverage_registry_member INTEGER NOT NULL CHECK(coverage_registry_member IN (0, 1)),
            provider_status TEXT,
            recommendation_fields_allowed INTEGER NOT NULL CHECK(recommendation_fields_allowed IN (0, 1)),
            customer_output_allowed INTEGER NOT NULL CHECK(customer_output_allowed IN (0, 1)),
            paper_or_live_execution_allowed INTEGER NOT NULL CHECK(paper_or_live_execution_allowed IN (0, 1))
        );

        CREATE TABLE answer_path_scope (
            ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
            answer_scope TEXT NOT NULL,
            production_card_generation_allowed INTEGER NOT NULL CHECK(production_card_generation_allowed IN (0, 1)),
            source_open_required_before_claim INTEGER NOT NULL CHECK(source_open_required_before_claim IN (0, 1))
        );

        CREATE TABLE validator_runs (
            name TEXT PRIMARY KEY,
            artifact_path TEXT NOT NULL,
            status TEXT,
            generated_at_utc TEXT,
            summary_json TEXT NOT NULL
        );

        CREATE TABLE archive_candidates (
            path TEXT PRIMARY KEY,
            candidate_class TEXT NOT NULL,
            proposed_action TEXT NOT NULL,
            archive_apply_allowed_now INTEGER NOT NULL CHECK(archive_apply_allowed_now IN (0, 1)),
            blocker TEXT NOT NULL,
            rollback TEXT NOT NULL
        );

        CREATE TABLE audit_events (
            event_id TEXT PRIMARY KEY,
            event_time_utc TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail_json TEXT NOT NULL
        );

        CREATE VIEW current_active_universe AS
        SELECT s.ticker, s.name, s.instrument_type, s.sector, s.industry,
               u.universe_scope, u.tier, u.monitoring_role,
               u.production_scope_member, u.production_scope_source,
               u.sql_tier, u.sql_tier_state, u.tier_decision_scope, u.review_100_monitor,
               u.decision_grade_eligible, u.source_open_required
        FROM securities s
        JOIN universe_membership u USING (ticker)
        WHERE s.active = 1;

        CREATE VIEW current_answer_path AS
        SELECT *
        FROM current_active_universe
        WHERE production_scope_member = 1;

        CREATE VIEW review_monitor_universe AS
        SELECT *
        FROM current_active_universe
        WHERE review_100_monitor = 1;
"""


def create_schema(conn: sqlite3.Connection) -> None:
    # executescript() would first COMMIT any pending transaction and then run every
    # DROP/CREATE in autocommit, so a failure mid-insert left the canon with its tables
    # already dropped (verified on a temp copy 2026-09-27: 300 securities -> 0, audit
    # history gone). SQLite DDL is transactional, so execute the statements inside one
    # explicit transaction that joins the caller's `with conn:` block: the rebuild then
    # commits or rolls back as a whole.
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    buffer = ""
    for line in SCHEMA_SQL.splitlines():
        buffer += line + "\n"
        if sqlite3.complete_statement(buffer):
            if buffer.strip():
                conn.execute(buffer)
            buffer = ""
    if buffer.strip():
        raise ValueError("SCHEMA_SQL ends with an incomplete statement")


def normalize_routing_tier(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if text.startswith("TIER "):
        text = text[5:].strip()
    return text or None


def load_proof_join_freshness() -> dict[str, dict[str, Any]] | None:
    """Per-ticker freshness rows for the production-scope proof join.

    Returns None when the freshness proof is absent so the join fails closed instead of
    promoting names on missing evidence.
    """
    freshness = load_json(FRESHNESS_PATH, None)
    if not isinstance(freshness, dict):
        return None
    rows = freshness.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    return {
        str(row.get("ticker", "")).upper(): row
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }


def load_proof_join_routing() -> dict[str, dict[str, Any]] | None:
    """Per-ticker router rows carrying the Tier A confidence verdict.

    Returns None when the router proof is absent so the join fails closed rather than
    promoting names whose confidence state is simply unknown.
    """
    router = load_json(AUTO_ROUTER_PATH, None)
    if not isinstance(router, dict):
        return None
    rows = router.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    return {
        str(row.get("ticker", "")).upper(): row
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }


def resolve_production_scope(
    ticker: str,
    freshness_rows: dict[str, dict[str, Any]] | None,
    routing_rows: dict[str, dict[str, Any]] | None,
    in_coverage: bool,
    card_exists: bool,
) -> tuple[bool, str]:
    if freshness_rows is None:
        return False, "freshness_proof_unavailable_fail_closed"
    if routing_rows is None:
        return False, "routing_proof_unavailable_fail_closed"
    row = freshness_rows.get(ticker)
    if row is None:
        return False, "no_freshness_row"
    if normalize_routing_tier(row.get("auto_tier")) not in PROOF_JOIN_TIERS:
        return False, "routing_tier_below_ab"
    if str(row.get("resolution_state")) not in PROOF_JOIN_FRESH_STATES:
        return False, "not_decision_grade_fresh"
    # Production scope means "answerable at decision grade", so only blocking-severity card
    # gaps disqualify. Context gaps (e.g. absence from the owner-side deployment-readiness
    # surface) describe owner workflow state, not missing evidence. Absent proof fails closed.
    blocking_gaps = row.get("card_blocking_gap_count")
    if not isinstance(blocking_gaps, int) or isinstance(blocking_gaps, bool):
        return False, "card_blocking_gap_proof_unavailable_fail_closed"
    if blocking_gaps != 0:
        return False, "card_blocking_gap_present"
    routing = routing_rows.get(ticker)
    if routing is None:
        return False, "no_routing_row"
    if routing.get("critical_data_conflict_count") != 0:
        return False, "critical_data_conflict_or_unknown"
    if str(routing.get("tier_a_confidence_status")) != PROOF_JOIN_CONFIDENCE_STATUS:
        return False, "confidence_status_not_ready"
    if not in_coverage:
        return False, "not_in_coverage_registry"
    if not card_exists:
        return False, "no_production_card_on_disk"
    return True, "proof_joined_routing_tier_ab_fresh_confident_card_coverage"


def proof_join_expected_tickers(universe: dict[str, Any]) -> set[str]:
    """Recompute the production-scope set straight from source artifacts.

    Used by validation so the DB is checked against the evidence rather than against a
    hardcoded count. If the freshness proof is missing this returns an empty set, which
    keeps the guard fail-closed exactly as it was before the join existed.
    """
    freshness_rows = load_proof_join_freshness()
    routing_rows = load_proof_join_routing()
    coverage = load_json(TMP / "finance-data-coverage-current.json", {}) or {}
    coverage_tickers = set((coverage.get("ticker_coverage") or {}).keys())
    expected: set[str] = set()
    for row in active_entries(universe):
        ticker = str(row.get("ticker", "")).upper()
        card_path = TMP / "ticker-intelligence-cards" / f"{ticker}.current.json"
        member, _ = resolve_production_scope(
            ticker,
            freshness_rows,
            routing_rows,
            in_coverage=ticker in coverage_tickers,
            card_exists=card_path.exists(),
        )
        if member:
            expected.add(ticker)
    return expected


def insert_universe(conn: sqlite3.Connection, universe: dict[str, Any]) -> None:
    coverage = load_json(TMP / "finance-data-coverage-current.json", {}) or {}
    coverage_tickers = set((coverage.get("ticker_coverage") or {}).keys())
    provider = load_json(TMP / "wf78-100-ticker-provider-runtime-proof.json", {}) or {}
    provider_status = {
        str(row.get("ticker", "")).upper(): row.get("status")
        for row in provider.get("results", [])
        if isinstance(row, dict)
    }
    freshness_rows = load_proof_join_freshness()
    routing_rows = load_proof_join_routing()
    for row in active_entries(universe):
        ticker = str(row.get("ticker", "")).upper()
        source_symbols = row.get("source_symbols") if isinstance(row.get("source_symbols"), dict) else {}
        source_scope = str(row.get("universe_scope", PRODUCTION_SCOPE))
        legacy_42 = source_scope == RETIRED_PRODUCTION_SCOPE
        scope = PRODUCTION_SCOPE if legacy_42 else source_scope
        review_100 = source_scope == REVIEW_100_SCOPE
        card_path = TMP / "ticker-intelligence-cards" / f"{ticker}.current.json"
        production_scope_member, production_scope_source = resolve_production_scope(
            ticker,
            freshness_rows,
            routing_rows,
            in_coverage=ticker in coverage_tickers,
            card_exists=card_path.exists(),
        )
        tier = str(row.get("tier") or "C")
        sql_tier = f"Tier {tier.upper()}" if tier.upper() in {"A", "B", "C", "D"} else "Tier C"
        sql_tier_state = "sql_first_wait_for_routing"
        tier_decision_scope = (
            f"tier_{tier.lower()}_sql_first_review_scope"
            if tier.upper() in {"A", "B"}
            else (f"tier_{tier.lower()}_sql_first_review_scope" if tier.upper() == "C" else "non_tier_abc_monitor_scope")
        )
        conn.execute(
            """
            INSERT INTO securities(ticker, name, instrument_type, sector, industry, yfinance_symbol, sec_cik, company_ir, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                ticker,
                str(row.get("name") or ticker),
                str(row.get("instrument_type") or "operating_company"),
                row.get("sector"),
                row.get("industry"),
                source_symbols.get("yfinance") or ticker,
                source_symbols.get("sec_cik"),
                source_symbols.get("company_ir"),
            ),
        )
        conn.execute(
            """
            INSERT INTO universe_membership(
                ticker, universe_scope, tier, coverage_obligation_tier, monitoring_role,
                production_scope_member, production_scope_source, sql_tier, sql_tier_state, tier_decision_scope,
                review_100_monitor,
                decision_grade_eligible, source_open_required, promotion_required_before_action, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                scope,
                tier,
                tier,
                str(row.get("monitoring_role") or "review_monitor"),
                int(production_scope_member),
                production_scope_source,
                sql_tier,
                sql_tier_state,
                tier_decision_scope,
                int(review_100),
                int(bool(row.get("decision_grade_eligible"))),
                int(row.get("source_open_required") is True),
                int(row.get("promotion_required_before_action") is True),
                json.dumps(row, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT INTO evidence_status(
                ticker, has_production_card, card_path, coverage_registry_member, provider_status,
                recommendation_fields_allowed, customer_output_allowed, paper_or_live_execution_allowed
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                ticker,
                int(card_path.exists() and production_scope_member),
                rel(card_path) if card_path.exists() and production_scope_member else None,
                int(ticker in coverage_tickers),
                provider_status.get(ticker),
                int(production_scope_member),
            ),
        )
        conn.execute(
            """
            INSERT INTO answer_path_scope(
                ticker, answer_scope, production_card_generation_allowed, source_open_required_before_claim
            )
            VALUES (?, ?, ?, 1)
            """,
            (
                ticker,
                "sql_first_production_grade" if production_scope_member else "sql_first_review_monitor",
                int(production_scope_member),
            ),
        )


def sync_tier_routing_state(conn: sqlite3.Connection, universe: dict[str, Any]) -> None:
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tier_routing_state'"
    ).fetchone()
    if not existing:
        return
    router = load_json(AUTO_ROUTER_PATH, {}) or {}
    router_by_ticker = {
        str(row.get("ticker", "")).upper(): row
        for row in router.get("rows", [])
        if isinstance(row, dict) and row.get("ticker")
    }
    active_tickers = sorted(
        str(row.get("ticker", "")).upper()
        for row in active_entries(universe)
        if row.get("ticker")
    )
    if not active_tickers:
        return
    placeholders = ",".join("?" for _ in active_tickers)
    conn.execute(f"DELETE FROM tier_routing_state WHERE ticker NOT IN ({placeholders})", active_tickers)
    source_sha = sha256(AUTO_ROUTER_PATH) if AUTO_ROUTER_PATH.exists() else None
    source_generated = router.get("generated_at_utc") if isinstance(router, dict) else None
    for ticker in active_tickers:
        row = router_by_ticker.get(ticker, {})
        conn.execute(
            """
            INSERT OR REPLACE INTO tier_routing_state(
                ticker, auto_tier, auto_state, route_reason, route_priority,
                data_confidence_rating, fundamentals_confidence, tier_a_confidence_status,
                critical_data_conflict_count, tier_c_attention_score, tier_c_attention_next_action,
                capital_deployment_approved, trade_or_execution_approved,
                requires_separate_capital_or_execution_approval, source_artifact_path,
                source_artifact_sha256, source_generated_at_utc, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1, ?, ?, ?, ?)
            """,
            (
                ticker,
                row.get("auto_tier") or row.get("opportunity_tier") or "Tier C",
                row.get("auto_state") or "C-MONITOR",
                row.get("route_reason") or "sql_first_dynamic_universe_sync",
                row.get("route_priority"),
                row.get("data_confidence_rating"),
                row.get("fundamentals_confidence"),
                row.get("tier_a_confidence_status"),
                int(row.get("critical_data_conflict_count") or 0),
                row.get("tier_c_attention_score"),
                row.get("tier_c_attention_next_action"),
                rel(AUTO_ROUTER_PATH),
                source_sha,
                source_generated,
                json.dumps(row or {"ticker": ticker, "fallback": "sql_first_dynamic_universe_sync"}, sort_keys=True),
            ),
        )


def insert_artifact(conn: sqlite3.Connection, path: Path, role: str, status: str | None = None) -> None:
    exists = path.exists()
    generated = None
    if exists and path.suffix == ".json":
        data = load_json(path, {}) or {}
        if isinstance(data, dict):
            generated = data.get("generated_at_utc")
            status = status or data.get("status") or (data.get("validation") or {}).get("status")
    conn.execute(
        """
        INSERT OR REPLACE INTO source_artifacts(artifact_path, artifact_role, exists_on_disk, sha256, generated_at_utc, validator_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rel(path), role, int(exists), sha256(path) if exists and path.is_file() else None, generated, status),
    )


def insert_validators(conn: sqlite3.Connection) -> None:
    validators = {
        "wf78_finance_universe_validation": TMP / "wf78-finance-universe-validation.json",
        "wf78_100_ticker_import_gate": TMP / "wf78-100-ticker-import-gate.json",
        "finance_intelligence_state_validation": TMP / "finance-intelligence-state-validation.json",
        "finance_intelligence_state_phase3_qc": TMP / "finance-intelligence-state-phase3-qc.json",
        "finance_router_qa_100_review": TMP / "finance-intelligence-router-qa-wf78-100-review.json",
        "sql_pre_phase5_hardening": TMP / "sql-pre-phase5-hardening-gate.json",
        "sql_retail_expansion_phase_gate": TMP / "sql-retail-expansion-phases-1-4-gate.json",
        "sql_500_ticker_expansion_design_gate": TMP / "sql-500-ticker-expansion-design-gate.json",
        "ticker_card_100_validate_only": TMP / "ticker-card-wf78-100-import-production42-validate-summary.json",
    }
    for name, path in validators.items():
        data = load_json(path, {}) if path.exists() else {}
        if not isinstance(data, dict):
            data = {}
        status = data.get("status") or (data.get("validation") or {}).get("status")
        if not status and name == "ticker_card_100_validate_only" and data.get("artifact_type") and isinstance(data.get("cards"), list):
            status = "ok"
        if not status and name == "ticker_card_100_validate_only" and not path.exists() and (TMP / "finance-ticker-card-refresh-gate.json").exists():
            status = "not_required_superseded_by_ticker_card_refresh_gate"
        conn.execute(
            """
            INSERT OR REPLACE INTO validator_runs(name, artifact_path, status, generated_at_utc, summary_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, rel(path), status, data.get("generated_at_utc"), json.dumps(data.get("summary") or data.get("validation") or {}, sort_keys=True)),
        )


def build_archive_plan(conn: sqlite3.Connection) -> dict[str, Any]:
    candidates = [
        ("tmp/wf72-entry-stop-helper-42-no-drift-review.json", "legacy_42_no_drift_proof"),
        ("tmp/ticker-card-wf78-phase1-build-summary.json", "legacy_42_phase_summary"),
        ("tmp/ticker-card-wf78-live-pilot-import-regression-summary.json", "legacy_42_regression_summary"),
        ("tmp/finance-intelligence-router-qa-wf78-phase1.json", "legacy_42_router_qa"),
        ("tmp/finance-intelligence-router-qa-wf78-phase2.json", "legacy_42_router_qa"),
        ("tmp/finance-intelligence-router-qa-wf78-phase3.json", "legacy_42_router_qa"),
        ("tmp/finance-intelligence-router-qa-wf78-live-pilot-import.json", "legacy_42_router_qa"),
        ("tmp/wf78-pilot-on-demand-card-build-summary.json", "superseded_pilot_fixture_proof"),
        ("tmp/wf78-pilot-on-demand-card-proof.json", "superseded_pilot_fixture_proof"),
        ("tmp/wf78-pilot-provider-runtime-proof.json", "superseded_pilot_fixture_proof"),
    ]
    planned: list[dict[str, Any]] = []
    for rel_path, cls in candidates:
        path = ROOT / rel_path
        exists = path.exists()
        blocker = "reference_check_required_and_consumers_not_cut_over_to_state_finance_sql_canon"
        row = {
            "path": rel_path,
            "exists": exists,
            "candidate_class": cls,
            "proposed_action": "archive_after_sql_consumer_cutover",
            "archive_apply_allowed_now": False,
            "blocker": blocker,
            "rollback": f"Move archived copy back to {rel_path}",
        }
        planned.append(row)
        conn.execute(
            """
            INSERT OR REPLACE INTO archive_candidates(path, candidate_class, proposed_action, archive_apply_allowed_now, blocker, rollback)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (rel_path, cls, "archive_after_sql_consumer_cutover", blocker, row["rollback"]),
        )
    plan = {
        "schema_version": "finance_sql_canon_legacy_42_archive_plan.v1",
        "generated_at_utc": utc_now(),
        "status": "planned_blocked_until_consumer_cutover",
        "authority_boundary": {
            "owner_approved_archive_direction": True,
            "archive_apply_allowed_now": False,
            "delete_allowed": False,
            "reason": "First pass creates the SQL canon candidate and archive plan; actual moves wait for reference checks and consumer cutover proof.",
        },
        "candidate_count": len(planned),
        "existing_candidate_count": sum(1 for row in planned if row["exists"]),
        "candidates": planned,
    }
    write_json(ARCHIVE_PLAN_PATH, plan)
    return plan


def refuse_migrated_rebuild(conn: sqlite3.Connection) -> None:
    """This JSON-era whole-DB builder must not overwrite a migrated canon."""
    if table_exists(conn, "audit_events") and conn.execute(
        "SELECT 1 FROM audit_events WHERE event_type=? LIMIT 1",
        (MIGRATION_MARKER_EVENT_TYPE,),
    ).fetchone():
        raise RuntimeError(
            "Refusing legacy whole-canon rebuild: migrated SQL canon detected. "
            "Use the separately gated recovery route; approval-reference is not an override."
        )


def preflight_rebuild_target() -> None:
    """Read only; reject before the report path writes JSON, backups, or plans."""
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        refuse_migrated_rebuild(conn)


def build_db(universe: dict[str, Any], approval_reference: str, run_id: str) -> dict[str, Any]:
    preflight_rebuild_target()
    STATE.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # Recheck on the same connection before PRAGMAs or any DDL. Direct callers
        # cannot bypass the report-level preflight, and a changed target fails shut.
        refuse_migrated_rebuild(conn)
        apply_pragmas(conn)
        preserved_extension_rows = fetch_preserved_extension_rows(conn)
        with conn:
            create_schema(conn)
            conn.execute("INSERT INTO meta(key, value) VALUES('schema_version', 'finance_sql_canon.v1')")
            conn.execute("INSERT INTO meta(key, value) VALUES('generated_at_utc', ?)", (utc_now(),))
            conn.execute("INSERT INTO meta(key, value) VALUES('approval_reference', ?)", (approval_reference,))
            conn.execute("INSERT INTO meta(key, value) VALUES('authority_boundary_json', ?)", (json.dumps(AUTHORITY_BOUNDARY, sort_keys=True),))
            insert_universe(conn, universe)
            sync_tier_routing_state(conn, universe)
            restored_extensions = restore_preserved_extension_rows(conn, preserved_extension_rows, universe)
            for path, role in [
                (UNIVERSE_PATH, "source_universe_json_audit_mirror"),
                (AUTO_ROUTER_PATH, "dynamic_sql_first_tier_routing_source"),
                (TMP / "wf78-finance-universe-validation.json", "validator"),
                (TMP / "finance-data-coverage-current.json", "coverage_registry"),
                (TMP / "wf78-100-ticker-import-gate.json", "import_gate_proof"),
                (TMP / "wf78-100-ticker-provider-runtime-proof.json", "provider_runtime_proof"),
                (TMP / "finance-intelligence-router-qa-wf78-100-review.json", "router_qa"),
            ]:
                insert_artifact(conn, path, role)
            insert_validators(conn)
            archive_plan = build_archive_plan(conn)
            conn.execute(
                "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    utc_now(),
                    "finance_sql_canon_candidate_built",
                    json.dumps({
                        "approval_reference": approval_reference,
                        "archive_plan": rel(ARCHIVE_PLAN_PATH),
                        "restored_extension_rows": restored_extensions,
                    }, sort_keys=True),
                ),
            )
        conn.execute("PRAGMA optimize")
    return archive_plan


def validate_db() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if not DB_PATH.exists():
        add("db_exists", False, rel(DB_PATH))
        return {"status": "blocked", "checks": checks, "failed": 1}

    uri = DB_PATH.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        active = conn.execute("SELECT COUNT(*) FROM current_active_universe").fetchone()[0]
        legacy = conn.execute("SELECT COUNT(*) FROM current_answer_path").fetchone()[0]
        review = conn.execute("SELECT COUNT(*) FROM review_monitor_universe").fetchone()[0]
        prod_card_allowed = conn.execute("SELECT COUNT(*) FROM answer_path_scope WHERE production_card_generation_allowed=1").fetchone()[0]
        forbidden = conn.execute(
            """
            SELECT COUNT(*)
            FROM evidence_status
            WHERE customer_output_allowed != 0
               OR paper_or_live_execution_allowed != 0
            """
        ).fetchone()[0]
        archive_now = conn.execute("SELECT COUNT(*) FROM archive_candidates WHERE archive_apply_allowed_now != 0").fetchone()[0]
        reference_rows = conn.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0] if table_exists(conn, "reference_levels") else 0
        freshness_rows = conn.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0] if table_exists(conn, "evidence_freshness") else 0
        validators_bad = conn.execute(
            """
            SELECT name, status
            FROM validator_runs
            WHERE COALESCE(status, '') NOT IN (
                'ok', 'pass', 'ready_for_phase5_design_no_import', 'ready_for_next_gate_design',
                'ready_for_source_open_cleanup', 'not_required_superseded_by_ticker_card_refresh_gate'
            )
            ORDER BY name
            """
        ).fetchall()
        validators_bad = [
            row for row in validators_bad
            if not (row["name"] == "sql_500_ticker_expansion_design_gate" and row["status"] == "blocked")
        ]
        add("integrity_check_ok", integrity == "ok", integrity)
        add("foreign_key_check_ok", len(fk_rows) == 0, len(fk_rows))
        add("active_universe_supported_scaleout", active in SUPPORTED_ACTIVE_COUNTS, {"actual": active, "supported": sorted(SUPPORTED_ACTIVE_COUNTS)})
        expected_production = proof_join_expected_tickers(load_json(UNIVERSE_PATH, {}) or {})
        db_production = {
            str(row["ticker"]).upper()
            for row in conn.execute("SELECT ticker FROM current_answer_path").fetchall()
        }
        add(
            "sql_first_answer_path_matches_proof_join",
            db_production == expected_production,
            {
                "db_count": legacy,
                "expected_count": len(expected_production),
                "in_db_not_expected": sorted(db_production - expected_production),
                "expected_not_in_db": sorted(expected_production - db_production),
            },
        )
        add("review_monitor_supported_scaleout", review in SUPPORTED_REVIEW_MONITOR_COUNTS, {"actual": review, "supported": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS)})
        add(
            "production_card_generation_matches_proof_join",
            prod_card_allowed == len(expected_production),
            {"allowed": prod_card_allowed, "expected": len(expected_production)},
        )
        add(
            "production_scope_never_exceeds_active_universe",
            len(expected_production) <= active,
            {"production": len(expected_production), "active": active},
        )
        add("reference_levels_not_emptied_by_rebuild", reference_rows > 0, reference_rows)
        add("evidence_freshness_not_emptied_by_rebuild", freshness_rows > 0, freshness_rows)
        add("forbidden_customer_execution_flags_zero", forbidden == 0, forbidden)
        add("archive_apply_disabled_first_pass", archive_now == 0, archive_now)
        add("validators_green_or_expected_design_status", len(validators_bad) == 0, [dict(row) for row in validators_bad])
    failed = [row for row in checks if not row["ok"]]
    return {"status": "ok" if not failed else "blocked", "checks": checks, "failed": len(failed)}


def build_report(approval_reference: str, write: bool) -> dict[str, Any]:
    if write:
        preflight_rebuild_target()
    run_id = "finance-sql-canon-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    universe = load_json(UNIVERSE_PATH, {}) or {}
    universe, summary_was_stale = sync_universe_summary(universe)
    backup = backup_inputs(run_id, [
        UNIVERSE_PATH,
        TMP / "finance-intelligence-state.sqlite",
        TMP / "finance-intelligence-state.sqlite-wal",
        TMP / "finance-intelligence-state.sqlite-shm",
        DB_PATH,
        DB_PATH.with_name(DB_PATH.name + "-wal"),
        DB_PATH.with_name(DB_PATH.name + "-shm"),
    ])
    if write:
        write_json(UNIVERSE_PATH, universe)
        archive_plan = build_db(universe, approval_reference, run_id)
    else:
        archive_plan = {"status": "not_written", "candidate_count": 0}
    validation = validate_db() if write else {"status": "not_run", "checks": [], "failed": 0}
    summary = computed_summary(universe)
    report = {
        "schema_version": "finance_sql_canon_promotion.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if write and validation["status"] == "ok" else ("planned" if not write else "blocked"),
        "approval_reference": approval_reference,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "db_path": rel(DB_PATH),
        "source_universe": rel(UNIVERSE_PATH),
        "summary": {
            **summary,
            "source_universe_summary_was_stale": summary_was_stale,
            "archive_plan_status": archive_plan.get("status"),
            "archive_apply_allowed_now": False,
        },
        "backup": backup,
        "archive_plan_path": rel(ARCHIVE_PLAN_PATH),
        "validation": validation,
        "next_required_before_archive_apply": [
            "Reference scan over archive candidates",
            "SQL consumer cutover proof for universe lookup and answer-path scope",
            "Rollback drill from backup manifest",
            "Post-cutover router QA and ticker-card validate-only proof",
        ],
    }
    if write:
        write_json(REPORT_PATH, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write synced universe summary, durable SQL canon candidate DB, and proof reports.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero when validation is not ok.")
    parser.add_argument("--approval-reference", required=True, help="Exact owner approval reference for workspace SQL-canon promotion work.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = build_report(args.approval_reference, write=args.write)
    output = report if args.pretty else {
        "status": report["status"],
        "db_path": report["db_path"],
        "active_ticker_count": report["summary"]["active_ticker_count"],
        "legacy_42": report["summary"]["production_active_ticker_count"],
        "review_100": report["summary"]["review_100_monitor_count"],
        "validation": report["validation"]["status"],
        "failed": report["validation"]["failed"],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 1 if args.validate and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())

