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
from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers  # noqa: E402

STATE = ROOT / "state" / "finance"
DATA_FINANCE = ROOT / "data" / "finance"
TMP = ROOT / "tmp"
BACKUPS = ROOT / "backups" / "finance-sql-canon-promotion"

DB_PATH = STATE / "finance-canon.sqlite"
REPORT_PATH = TMP / "finance-sql-canon-promotion.json"
ARCHIVE_PLAN_PATH = TMP / "finance-sql-canon-legacy-42-archive-plan.json"
UNIVERSE_PATH = DATA_FINANCE / "universe-v1.json"

PRODUCTION_SCOPE = "production_current_42"
REVIEW_100_SCOPE = "review_100_monitor"
EXPECTED_PRODUCTION_COUNT = 42
SUPPORTED_ACTIVE_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}

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
    migrated_tickers = set(legacy_42_tier_tickers())
    legacy_tickers = sorted(
        migrated_tickers
        or {
            str(row.get("ticker", "")).upper()
            for row in entries
            if row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE
        }
    )
    return {
        "active_ticker_count": len(entries),
        "production_active_ticker_count": len(legacy_tickers),
        "review_100_monitor_count": by_scope.get(REVIEW_100_SCOPE, 0),
        "pilot_fixture_count": by_scope.get("pilot_fixture", 0),
        "tier_counts": dict(sorted(by_tier.items())),
        "instrument_type_counts": dict(sorted(by_type.items())),
        "review_100_monitor_tickers": sorted(
            str(row.get("ticker", "")).upper()
            for row in entries
            if row.get("universe_scope") == REVIEW_100_SCOPE
        ),
        "legacy_production_42_tickers": legacy_tickers,
        "legacy_production_42_source": "wf78_legacy_42_tier_state_shadow" if migrated_tickers else "universe_scope_fallback",
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
        expected["active_ticker_count"] == 200
        and expected["production_active_ticker_count"] == EXPECTED_PRODUCTION_COUNT
        and expected["review_100_monitor_count"] == 158
    ):
        universe["status"] = "wf78_101_200_tier_c_monitor_ready"
    elif (
        expected["active_ticker_count"] == 100
        and expected["production_active_ticker_count"] == EXPECTED_PRODUCTION_COUNT
        and expected["review_100_monitor_count"] == 58
    ):
        universe["status"] = "phase5_review_100_monitor_ready"
    elif (
        expected["active_ticker_count"] in SUPPORTED_ACTIVE_COUNTS
        and expected["production_active_ticker_count"] == EXPECTED_PRODUCTION_COUNT
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


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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
            monitoring_role TEXT NOT NULL,
            legacy_production_42 INTEGER NOT NULL CHECK(legacy_production_42 IN (0, 1)),
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
               u.legacy_production_42, u.review_100_monitor,
               u.decision_grade_eligible, u.source_open_required
        FROM securities s
        JOIN universe_membership u USING (ticker)
        WHERE s.active = 1;

        CREATE VIEW current_answer_path AS
        SELECT *
        FROM current_active_universe
        WHERE legacy_production_42 = 1;

        CREATE VIEW review_monitor_universe AS
        SELECT *
        FROM current_active_universe
        WHERE review_100_monitor = 1;
        """
    )


def insert_universe(conn: sqlite3.Connection, universe: dict[str, Any]) -> None:
    coverage = load_json(TMP / "finance-data-coverage-current.json", {}) or {}
    coverage_tickers = set((coverage.get("ticker_coverage") or {}).keys())
    provider = load_json(TMP / "wf78-100-ticker-provider-runtime-proof.json", {}) or {}
    provider_status = {
        str(row.get("ticker", "")).upper(): row.get("status")
        for row in provider.get("results", [])
        if isinstance(row, dict)
    }
    migrated_legacy_tickers = set(legacy_42_tier_tickers())
    for row in active_entries(universe):
        ticker = str(row.get("ticker", "")).upper()
        source_symbols = row.get("source_symbols") if isinstance(row.get("source_symbols"), dict) else {}
        scope = str(row.get("universe_scope", PRODUCTION_SCOPE))
        legacy_42 = ticker in migrated_legacy_tickers if migrated_legacy_tickers else scope == PRODUCTION_SCOPE
        review_100 = scope == REVIEW_100_SCOPE
        card_path = TMP / "ticker-intelligence-cards" / f"{ticker}.current.json"
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
                ticker, universe_scope, tier, monitoring_role, legacy_production_42, review_100_monitor,
                decision_grade_eligible, source_open_required, promotion_required_before_action, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                scope,
                str(row.get("tier") or "C"),
                str(row.get("monitoring_role") or "review_monitor"),
                int(legacy_42),
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
                int(legacy_42 and card_path.exists()),
                rel(card_path) if legacy_42 and card_path.exists() else None,
                int(ticker in coverage_tickers),
                provider_status.get(ticker),
                int(legacy_42),
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
                "legacy_production_42" if legacy_42 else "review_100_monitor",
                int(legacy_42),
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


def build_db(universe: dict[str, Any], approval_reference: str, run_id: str) -> dict[str, Any]:
    STATE.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        apply_pragmas(conn)
        with conn:
            create_schema(conn)
            conn.execute("INSERT INTO meta(key, value) VALUES('schema_version', 'finance_sql_canon.v1')")
            conn.execute("INSERT INTO meta(key, value) VALUES('generated_at_utc', ?)", (utc_now(),))
            conn.execute("INSERT INTO meta(key, value) VALUES('approval_reference', ?)", (approval_reference,))
            conn.execute("INSERT INTO meta(key, value) VALUES('authority_boundary_json', ?)", (json.dumps(AUTHORITY_BOUNDARY, sort_keys=True),))
            insert_universe(conn, universe)
            for path, role in [
                (UNIVERSE_PATH, "source_universe_json_audit_mirror"),
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
                    json.dumps({"approval_reference": approval_reference, "archive_plan": rel(ARCHIVE_PLAN_PATH)}, sort_keys=True),
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
        add("integrity_check_ok", integrity == "ok", integrity)
        add("foreign_key_check_ok", len(fk_rows) == 0, len(fk_rows))
        add("active_universe_supported_scaleout", active in SUPPORTED_ACTIVE_COUNTS, {"actual": active, "supported": sorted(SUPPORTED_ACTIVE_COUNTS)})
        add("legacy_answer_path_42", legacy == EXPECTED_PRODUCTION_COUNT, legacy)
        add("review_monitor_supported_scaleout", review in SUPPORTED_REVIEW_MONITOR_COUNTS, {"actual": review, "supported": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS)})
        add("production_card_generation_limited_to_42", prod_card_allowed == EXPECTED_PRODUCTION_COUNT, prod_card_allowed)
        add("forbidden_customer_execution_flags_zero", forbidden == 0, forbidden)
        add("archive_apply_disabled_first_pass", archive_now == 0, archive_now)
        add("validators_green_or_expected_design_status", len(validators_bad) == 0, [dict(row) for row in validators_bad])
    failed = [row for row in checks if not row["ok"]]
    return {"status": "ok" if not failed else "blocked", "checks": checks, "failed": len(failed)}


def build_report(approval_reference: str, write: bool) -> dict[str, Any]:
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
