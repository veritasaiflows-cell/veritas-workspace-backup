#!/usr/bin/env python3
"""Prepare or apply the production-scope schema retirement.

The default path keeps the prior neutral alias migration available. The
owner-approved hard-retirement path removes the active Legacy 42 compatibility
columns from the SQL runtime schema, converts the old production-current label
to the SQL-first review universe, and activates explicit SQL Tier A/B/C fields.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, backup_sqlite_database


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
TMP = ROOT / "tmp"
BACKUPS = ROOT / "backups" / "finance-production-scope-schema-retirement"
DEFAULT_OUT = TMP / "production-scope-schema-retirement-plan.json"
DEFAULT_INVENTORY = TMP / "production-scope-schema-retirement-inventory.json"

SCHEMA = "veritas.production_scope_schema_retirement_plan.v2"

RETIRED_PRODUCTION_SCOPE = "production_current_42"
ACTIVE_INTERNAL_SCOPE = "active_internal_universe"

NEUTRAL_COLUMNS = {
    "production_scope_member": "INTEGER NOT NULL DEFAULT 0",
    "production_scope_source": "TEXT",
    "tier_ab_decision_scope": "TEXT",
    "compatibility_reason": "TEXT",
}
SQL_FIRST_COLUMNS = {
    "production_scope_member": "INTEGER NOT NULL DEFAULT 0",
    "production_scope_source": "TEXT",
    "sql_tier": "TEXT",
    "sql_tier_state": "TEXT",
    "tier_decision_scope": "TEXT",
}
HARD_RETIRED_COLUMNS = {
    "legacy_production_42",
    "tier_ab_decision_scope",
    "compatibility_reason",
}

SEARCH_ROOTS = [
    "scripts",
    "state",
    "tmp",
    "data",
    "06. Playbooks",
]
SEARCH_SUFFIXES = {".py", ".json", ".jsonl", ".md", ".txt"}
SEARCH_TERMS = [
    "legacy_production_42",
    "production_current_42",
    "legacy_42_",
    "Legacy 42",
]

AUTHORITY_BOUNDARY = {
    "schema_neutral_alias_apply_allowed": True,
    "hard_rename_drop_delete_allowed": False,
    "legacy_compatibility_fields_retained": True,
    "sql_first_tier_schema_active": False,
    "source_artifact_content_mutation_allowed": False,
    "portfolio_or_canon_note_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

HARD_RETIRE_AUTHORITY_BOUNDARY = {
    **AUTHORITY_BOUNDARY,
    "schema_neutral_alias_apply_allowed": False,
    "hard_rename_drop_delete_allowed": True,
    "legacy_compatibility_fields_retained": False,
    "sql_first_tier_schema_active": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def connect_rw(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def connect_ro(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def backup_db(run_id: str) -> dict[str, Any]:
    backup_dir = BACKUPS / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_sqlite_database(DB_PATH, backup_dir / DB_PATH.name)
    copied: list[dict[str, Any]] = [
        {
            "path": rel(DB_PATH),
            "backup_path": rel(backup_path),
            "sha256": sha256(DB_PATH),
            "backup_sha256": sha256(backup_path),
            "bytes": DB_PATH.stat().st_size,
            "rollback": f"Replace {rel(DB_PATH)} with {rel(backup_path)} after stopping writers.",
        }
    ]
    manifest = {
        "schema": "veritas.production_scope_schema_retirement_backup.v1",
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "authority_boundary": {
            "backup_only": True,
            "hard_delete_allowed": False,
            "portfolio_or_execution_authority": False,
        },
        "files": copied,
    }
    write_json(backup_dir / "manifest.json", manifest)
    return {"backup_dir": rel(backup_dir), "manifest": rel(backup_dir / "manifest.json"), "files": copied}


def inventory_references() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    counts = Counter()
    for root_text in SEARCH_ROOTS:
        root = ROOT / root_text
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SEARCH_SUFFIXES:
                continue
            rel_path = rel(path)
            if rel_path.startswith("09. Archive/"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for term in SEARCH_TERMS:
                count = text.count(term)
                if count:
                    counts[term] += count
                    hits.append(
                        {
                            "path": rel_path,
                            "term": term,
                            "count": count,
                            "classification": classify_reference(rel_path),
                        }
                    )
    class_counts = Counter(str(hit["classification"]) for hit in hits)
    return {
        "schema": "veritas.production_scope_compatibility_inventory.v1",
        "generated_at_utc": utc_now(),
        "search_terms": SEARCH_TERMS,
        "hit_count": len(hits),
        "term_counts": dict(sorted(counts.items())),
        "classification_counts": dict(sorted(class_counts.items())),
        "hits": sorted(hits, key=lambda row: (row["classification"], row["path"], row["term"]))[:500],
        "note": "Inventory is for schema/history cleanup routing; generated tmp/history hits are not runtime blockers by themselves.",
    }


def classify_reference(rel_path: str) -> str:
    if rel_path.startswith("tmp/") or "snapshot" in rel_path:
        return "generated_or_snapshot"
    if rel_path.startswith("state/implementation-completion-ledger-snapshots/"):
        return "historical_snapshot"
    if rel_path.startswith("06. Playbooks/"):
        return "documentation_or_history"
    if rel_path.startswith("state/"):
        return "state_registry_or_history"
    if rel_path.startswith("data/"):
        return "source_universe_compatibility"
    if rel_path.startswith("scripts/test_"):
        return "test_compatibility"
    if rel_path.startswith("scripts/"):
        return "active_script_or_governance"
    return "other"


def row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def desired_values(row: sqlite3.Row, production_tickers: set[str]) -> dict[str, Any]:
    ticker = str(row["ticker"]).upper()
    tier = str(row["tier"] or "").upper()
    legacy = int(row_value(row, "legacy_production_42", 0) or 0) == 1
    review = int(row["review_100_monitor"] or 0) == 1
    production_member = ticker in production_tickers
    if production_member:
        production_source = "finance_sql_canon_access.production_answer_tickers"
    else:
        production_source = "not_current_proof_joined_production_scope"
    if tier in {"A", "B"}:
        tier_scope = f"tier_{tier.lower()}_review_scope"
    elif review:
        tier_scope = "review_monitor_scope"
    else:
        tier_scope = "non_tier_ab_monitor_scope"
    compatibility_reason = None
    if legacy:
        compatibility_reason = "archived_legacy_42_compatibility_alias_not_production_authority"
    elif str(row["universe_scope"]) == RETIRED_PRODUCTION_SCOPE:
        compatibility_reason = "retired_production_current_42_label_retained_for_history"
    return {
        "production_scope_member": int(production_member),
        "production_scope_source": production_source,
        "tier_ab_decision_scope": tier_scope,
        "compatibility_reason": compatibility_reason,
    }


def normalize_sql_tier(*, tier: Any) -> str:
    # universe_membership carries coverage-obligation semantics only. Live route state belongs to
    # tier_routing_state.auto_tier and must never be folded in here, or the same column means
    # "obligation" or "route" depending on which writer touched the row last.
    legacy = str(tier or "C").strip().upper()
    if legacy in {"A", "B", "C", "D"}:
        return f"Tier {legacy}"
    if legacy.startswith("TIER "):
        return f"Tier {legacy.split()[-1].upper()}"
    return "Tier C"


def sql_first_values(row: sqlite3.Row, production_tickers: set[str]) -> dict[str, Any]:
    ticker = str(row["ticker"]).upper()
    production_member = ticker in production_tickers
    sql_tier = normalize_sql_tier(tier=row_value(row, "tier"))
    sql_tier_state = "sql_first_wait_for_routing"
    tier_letter = sql_tier.split()[-1].lower() if " " in sql_tier else "c"
    if tier_letter in {"a", "b", "c"}:
        tier_decision_scope = f"tier_{tier_letter}_sql_first_review_scope"
    else:
        tier_decision_scope = "non_tier_abc_monitor_scope"
    universe_scope = str(row_value(row, "universe_scope") or ACTIVE_INTERNAL_SCOPE)
    if universe_scope == RETIRED_PRODUCTION_SCOPE:
        universe_scope = ACTIVE_INTERNAL_SCOPE
    return {
        "universe_scope": universe_scope,
        "production_scope_member": int(production_member),
        "production_scope_source": (
            "finance_sql_canon_access.production_answer_tickers"
            if production_member
            else "not_current_proof_joined_production_scope"
        ),
        "sql_tier": sql_tier,
        "sql_tier_state": sql_tier_state,
        "tier_decision_scope": tier_decision_scope,
    }


def recreate_routing_view(conn: sqlite3.Connection) -> None:
    columns = table_columns(conn, "universe_membership")
    sql_tier_expr = "u.sql_tier" if "sql_tier" in columns else "NULL AS sql_tier"
    sql_state_expr = "u.sql_tier_state" if "sql_tier_state" in columns else "NULL AS sql_tier_state"
    tier_scope_expr = "u.tier_decision_scope" if "tier_decision_scope" in columns else "NULL AS tier_decision_scope"
    legacy_expr = "u.legacy_production_42," if "legacy_production_42" in columns else ""
    tier_ab_expr = "u.tier_ab_decision_scope," if "tier_ab_decision_scope" in columns else ""
    compatibility_expr = "u.compatibility_reason," if "compatibility_reason" in columns else ""
    conn.executescript(
        f"""
        DROP VIEW IF EXISTS current_sql_canon_routing;
        DROP VIEW IF EXISTS current_active_universe;
        DROP VIEW IF EXISTS current_answer_path;
        DROP VIEW IF EXISTS review_monitor_universe;
        CREATE VIEW current_sql_canon_routing AS
        SELECT s.ticker, s.name, s.instrument_type, s.sector, s.industry,
               u.universe_scope, u.tier AS legacy_tier,
               {legacy_expr}
               u.production_scope_member, u.production_scope_source,
               {tier_ab_expr}
               {compatibility_expr}
               {sql_tier_expr}, {sql_state_expr}, {tier_scope_expr},
               t.auto_tier, t.auto_state, t.route_priority,
               e.has_production_card, e.provider_status,
               a.answer_scope, a.production_card_generation_allowed,
               r.reference_price_low, r.reference_price_high, r.reference_invalidation_level,
               r.reference_band_status, r.reference_confidence
        FROM securities s
        JOIN universe_membership u USING (ticker)
        LEFT JOIN tier_routing_state t USING (ticker)
        LEFT JOIN evidence_status e USING (ticker)
        LEFT JOIN evidence_freshness f USING (ticker)
        LEFT JOIN answer_path_scope a USING (ticker)
        LEFT JOIN reference_levels r USING (ticker)
        WHERE s.active = 1;

        CREATE VIEW current_active_universe AS
        SELECT s.ticker, s.name, s.instrument_type, s.sector, s.industry,
               u.universe_scope, u.tier AS source_universe_tier, u.monitoring_role,
               u.production_scope_member, u.production_scope_source,
               {sql_tier_expr}, {sql_state_expr}, {tier_scope_expr},
               u.review_100_monitor, u.decision_grade_eligible, u.source_open_required
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
    )


def apply_migration() -> dict[str, Any]:
    run_id = "production-scope-schema-retirement-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_db(run_id)
    columns_added: list[str] = []
    with connect_rw() as conn:
        before = table_columns(conn, "universe_membership")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for name, definition in NEUTRAL_COLUMNS.items():
                if name not in before:
                    conn.execute(f"ALTER TABLE universe_membership ADD COLUMN {name} {definition}")
                    columns_added.append(name)
            production_tickers = {
                str(row["ticker"]).upper()
                for row in conn.execute(
                    """
                    SELECT ticker
                    FROM current_sql_canon_routing
                    WHERE auto_tier='Tier A'
                      AND auto_state='A-READY'
                      AND legacy_production_42=1
                    ORDER BY ticker
                    """
                )
            }
            # The strict production-scope helper is proof-joined and currently
            # fail-closed. Avoid promoting label-only rows by default.
            production_tickers = set()
            rows = conn.execute("SELECT * FROM universe_membership ORDER BY ticker").fetchall()
            for row in rows:
                values = desired_values(row, production_tickers)
                conn.execute(
                    """
                    UPDATE universe_membership
                    SET production_scope_member=?,
                        production_scope_source=?,
                        tier_ab_decision_scope=?,
                        compatibility_reason=?
                    WHERE ticker=?
                    """,
                    (
                        values["production_scope_member"],
                        values["production_scope_source"],
                        values["tier_ab_decision_scope"],
                        values["compatibility_reason"],
                        row["ticker"],
                    ),
                )
            recreate_routing_view(conn)
            conn.execute(
                """
                INSERT INTO migration_validation_runs(
                    run_id, run_time_utc, validator_name, status, artifact_path, detail_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    utc_now(),
                    "production_scope_schema_retirement_plan",
                    "ok",
                    rel(DEFAULT_OUT),
                    json.dumps(
                        {
                            "columns_added": columns_added,
                            "hard_rename_drop_delete_allowed": False,
                            "backup": backup,
                        },
                        sort_keys=True,
                    ),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        conn.execute("PRAGMA optimize")
    return {"run_id": run_id, "backup": backup, "columns_added": columns_added}


def apply_hard_retirement() -> dict[str, Any]:
    run_id = "legacy-42-hard-retirement-sql-first-tier-schema-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_db(run_id)
    retired_rows: list[dict[str, Any]] = []
    with connect_rw() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            production_tickers: set[str] = set()
            rows = conn.execute(
                """
                SELECT u.*, t.auto_tier, t.auto_state
                FROM universe_membership AS u
                LEFT JOIN tier_routing_state AS t USING (ticker)
                ORDER BY u.ticker
                """
            ).fetchall()
            for row in rows:
                legacy_flag = int(row_value(row, "legacy_production_42", 0) or 0) == 1
                if legacy_flag or row_value(row, "universe_scope") == RETIRED_PRODUCTION_SCOPE:
                    retired_rows.append(
                        {
                            "ticker": row["ticker"],
                            "legacy_production_42": int(legacy_flag),
                            "old_universe_scope": row_value(row, "universe_scope"),
                            "new_universe_scope": ACTIVE_INTERNAL_SCOPE,
                        }
                    )

            conn.executescript(
                """
                DROP VIEW IF EXISTS current_sql_canon_routing;
                DROP VIEW IF EXISTS current_active_universe;
                DROP VIEW IF EXISTS current_answer_path;
                DROP VIEW IF EXISTS review_monitor_universe;

                CREATE TABLE universe_membership_hard_retired_new (
                    ticker TEXT PRIMARY KEY REFERENCES securities(ticker) ON DELETE CASCADE,
                    universe_scope TEXT NOT NULL,
                    tier TEXT NOT NULL CHECK(tier IN ('A', 'B', 'C', 'D')),
                    coverage_obligation_tier TEXT NOT NULL CHECK(coverage_obligation_tier IN ('A', 'B', 'C', 'D')),
                    monitoring_role TEXT NOT NULL,
                    review_100_monitor INTEGER NOT NULL CHECK(review_100_monitor IN (0, 1)),
                    decision_grade_eligible INTEGER NOT NULL CHECK(decision_grade_eligible IN (0, 1)),
                    source_open_required INTEGER NOT NULL CHECK(source_open_required IN (0, 1)),
                    promotion_required_before_action INTEGER NOT NULL CHECK(promotion_required_before_action IN (0, 1)),
                    raw_json TEXT NOT NULL,
                    production_scope_member INTEGER NOT NULL DEFAULT 0 CHECK(production_scope_member IN (0, 1)),
                    production_scope_source TEXT,
                    sql_tier TEXT,
                    sql_tier_state TEXT,
                    tier_decision_scope TEXT
                );
                """
            )
            for row in rows:
                values = sql_first_values(row, production_tickers)
                conn.execute(
                    """
                    INSERT INTO universe_membership_hard_retired_new(
                        ticker, universe_scope, tier, coverage_obligation_tier, monitoring_role, review_100_monitor,
                        decision_grade_eligible, source_open_required,
                        promotion_required_before_action, raw_json,
                        production_scope_member, production_scope_source,
                        sql_tier, sql_tier_state, tier_decision_scope
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["ticker"],
                        values["universe_scope"],
                        row["tier"],
                        row_value(row, "coverage_obligation_tier", None) or row["tier"],
                        row["monitoring_role"],
                        row["review_100_monitor"],
                        row["decision_grade_eligible"],
                        row["source_open_required"],
                        row["promotion_required_before_action"],
                        row["raw_json"],
                        values["production_scope_member"],
                        values["production_scope_source"],
                        values["sql_tier"],
                        values["sql_tier_state"],
                        values["tier_decision_scope"],
                    ),
                )
            conn.executescript(
                """
                DROP TABLE universe_membership;
                ALTER TABLE universe_membership_hard_retired_new RENAME TO universe_membership;
                """
            )
            if "answer_path_scope" in {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                conn.execute(
                    """
                    UPDATE answer_path_scope
                    SET answer_scope = CASE
                            WHEN ticker IN (
                                SELECT ticker FROM universe_membership WHERE production_scope_member=1
                            )
                            THEN 'sql_first_production_grade'
                            ELSE 'sql_first_review_monitor'
                        END,
                        production_card_generation_allowed = CASE
                            WHEN ticker IN (
                                SELECT ticker FROM universe_membership WHERE production_scope_member=1
                            )
                            THEN 1 ELSE 0 END,
                        source_open_required_before_claim = 1
                    """
                )
            if "evidence_status" in {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                conn.execute("UPDATE evidence_status SET recommendation_fields_allowed=0")
            recreate_routing_view(conn)
            conn.execute(
                """
                INSERT INTO migration_validation_runs(
                    run_id, run_time_utc, validator_name, status, artifact_path, detail_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    utc_now(),
                    "production_scope_schema_retirement_plan",
                    "ok",
                    rel(DEFAULT_OUT),
                    json.dumps(
                        {
                            "hard_retired_columns": sorted(HARD_RETIRED_COLUMNS),
                            "retired_legacy_rows": retired_rows,
                            "backup": backup,
                            "sql_first_columns": sorted(SQL_FIRST_COLUMNS),
                        },
                        sort_keys=True,
                    ),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        conn.execute("PRAGMA optimize")
    return {
        "run_id": run_id,
        "backup": backup,
        "hard_retired_columns": sorted(HARD_RETIRED_COLUMNS),
        "sql_first_columns": sorted(SQL_FIRST_COLUMNS),
        "retired_legacy_row_count": len(retired_rows),
        "retired_legacy_rows": retired_rows,
    }


def schema_state(*, hard_retire: bool = False) -> dict[str, Any]:
    if not DB_PATH.exists():
        required = SQL_FIRST_COLUMNS if hard_retire else NEUTRAL_COLUMNS
        return {"db_exists": False, "columns": [], "missing_columns": sorted(required)}
    with connect_ro() as conn:
        columns = table_columns(conn, "universe_membership")
        view_columns = table_columns(conn, "current_sql_canon_routing")
        has_legacy = "legacy_production_42" in columns
        has_sql_first = set(SQL_FIRST_COLUMNS).issubset(columns)
        counts = {
            "total_rows": int(conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0]),
            "production_current_42_rows": int(conn.execute("SELECT COUNT(*) FROM universe_membership WHERE universe_scope=?", (RETIRED_PRODUCTION_SCOPE,)).fetchone()[0]),
        }
        if has_legacy:
            counts["legacy_production_42_rows"] = int(conn.execute("SELECT COUNT(*) FROM universe_membership WHERE legacy_production_42=1").fetchone()[0])
        else:
            counts["legacy_production_42_rows"] = 0
        if set(NEUTRAL_COLUMNS).issubset(columns):
            counts.update(
                {
                    "production_scope_member_rows": int(conn.execute("SELECT COUNT(*) FROM universe_membership WHERE production_scope_member=1").fetchone()[0]),
                    "tier_ab_decision_scope_counts": {
                        str(row["tier_ab_decision_scope"]): int(row["count"])
                        for row in conn.execute(
                            "SELECT tier_ab_decision_scope, COUNT(*) AS count FROM universe_membership GROUP BY tier_ab_decision_scope ORDER BY tier_ab_decision_scope"
                        )
                    },
                    "compatibility_reason_counts": {
                        str(row["compatibility_reason"]): int(row["count"])
                        for row in conn.execute(
                            "SELECT COALESCE(compatibility_reason, 'none') AS compatibility_reason, COUNT(*) AS count FROM universe_membership GROUP BY COALESCE(compatibility_reason, 'none') ORDER BY compatibility_reason"
                        )
                    },
                }
            )
        if has_sql_first:
            counts.update(
                {
                    "production_scope_member_rows": int(conn.execute("SELECT COUNT(*) FROM universe_membership WHERE production_scope_member=1").fetchone()[0]),
                    "sql_tier_counts": {
                        str(row["sql_tier"]): int(row["count"])
                        for row in conn.execute(
                            "SELECT sql_tier, COUNT(*) AS count FROM universe_membership GROUP BY sql_tier ORDER BY sql_tier"
                        )
                    },
                    "tier_decision_scope_counts": {
                        str(row["tier_decision_scope"]): int(row["count"])
                        for row in conn.execute(
                            "SELECT tier_decision_scope, COUNT(*) AS count FROM universe_membership GROUP BY tier_decision_scope ORDER BY tier_decision_scope"
                        )
                    },
                }
            )
        if "answer_path_scope" in {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            counts["production_card_generation_allowed_rows"] = int(
                conn.execute("SELECT COUNT(*) FROM answer_path_scope WHERE production_card_generation_allowed=1").fetchone()[0]
            )
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_count = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    required_columns = SQL_FIRST_COLUMNS if hard_retire else NEUTRAL_COLUMNS
    required_view_columns = set(required_columns)
    return {
        "db_exists": True,
        "columns": sorted(columns),
        "missing_columns": sorted(set(required_columns) - columns),
        "routing_view_missing_columns": sorted(required_view_columns - view_columns),
        "hard_retired_columns_present": sorted(HARD_RETIRED_COLUMNS & columns),
        "routing_view_hard_retired_columns_present": sorted(HARD_RETIRED_COLUMNS & view_columns),
        "counts": counts,
        "integrity_check": integrity,
        "foreign_key_issue_count": fk_count,
    }


def validate(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_boundary = HARD_RETIRE_AUTHORITY_BOUNDARY if packet.get("hard_retire") else AUTHORITY_BOUNDARY
    boundary = packet.get("authority_boundary") if isinstance(packet.get("authority_boundary"), dict) else {}
    for key, expected in expected_boundary.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    state = packet.get("schema_state") if isinstance(packet.get("schema_state"), dict) else {}
    if packet.get("apply") is True:
        if state.get("missing_columns"):
            errors.append(f"neutral_columns_missing:{state.get('missing_columns')}")
        if state.get("routing_view_missing_columns"):
            errors.append(f"routing_view_neutral_columns_missing:{state.get('routing_view_missing_columns')}")
        if state.get("integrity_check") != "ok":
            errors.append(f"integrity_check_not_ok:{state.get('integrity_check')}")
        if int(state.get("foreign_key_issue_count") or 0) != 0:
            errors.append(f"foreign_key_issues:{state.get('foreign_key_issue_count')}")
        if packet.get("hard_retire"):
            if state.get("hard_retired_columns_present"):
                errors.append(f"hard_retired_columns_still_present:{state.get('hard_retired_columns_present')}")
            if state.get("routing_view_hard_retired_columns_present"):
                errors.append(f"routing_view_hard_retired_columns_still_present:{state.get('routing_view_hard_retired_columns_present')}")
            counts = state.get("counts") if isinstance(state.get("counts"), dict) else {}
            if int(counts.get("production_current_42_rows") or 0) != 0:
                errors.append(f"production_current_42_rows_remaining:{counts.get('production_current_42_rows')}")
            if int(counts.get("total_rows") or 0) != 200:
                errors.append(f"row_count_not_200:{counts.get('total_rows')}")
            if int(counts.get("production_card_generation_allowed_rows") or 0) != int(counts.get("production_scope_member_rows") or 0):
                errors.append("answer_path_scope_not_sql_first_fail_closed")
    return sorted(errors)


def build_packet(*, apply: bool, hard_retire: bool = False) -> dict[str, Any]:
    inventory = inventory_references()
    apply_result = (
        apply_hard_retirement()
        if apply and hard_retire
        else apply_migration()
        if apply
        else {
        "run_id": None,
        "backup": None,
        "columns_added": [],
        "planned_columns": sorted(SQL_FIRST_COLUMNS if hard_retire else NEUTRAL_COLUMNS),
        "planned_hard_retired_columns": sorted(HARD_RETIRED_COLUMNS) if hard_retire else [],
    }
    )
    state = schema_state(hard_retire=hard_retire)
    authority_boundary = HARD_RETIRE_AUTHORITY_BOUNDARY if hard_retire else AUTHORITY_BOUNDARY
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "apply": bool(apply),
        "hard_retire": bool(hard_retire),
        "authority_boundary": authority_boundary,
        "db_path": rel(DB_PATH),
        "apply_result": apply_result,
        "schema_state": state,
        "inventory_path": rel(DEFAULT_INVENTORY),
        "summary": {
            "neutral_columns": sorted(NEUTRAL_COLUMNS),
            "sql_first_columns": sorted(SQL_FIRST_COLUMNS),
            "neutral_columns_present": not state.get("missing_columns"),
            "routing_view_neutral_columns_present": not state.get("routing_view_missing_columns"),
            "hard_retired_columns_absent": not state.get("hard_retired_columns_present"),
            "routing_view_hard_retired_columns_absent": not state.get("routing_view_hard_retired_columns_present"),
            "hard_rename_drop_delete_allowed": bool(hard_retire),
            "next_required_approval": (
                "Historical snapshot archive/delete remains separately manifest-gated."
                if hard_retire
                else "Exact owner approval is still required before any compatibility column rename/drop/delete or historical snapshot removal."
            ),
            "inventory_hit_count": inventory["hit_count"],
            "inventory_classification_counts": inventory["classification_counts"],
        },
        "validation": {"status": "not_run", "errors": [], "warnings": []},
    }
    errors = validate(packet)
    packet["validation"] = {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}
    packet["status"] = "ok" if not errors else "blocked"
    write_json(DEFAULT_INVENTORY, inventory)
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--hard-retire", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet(apply=args.apply, hard_retire=args.hard_retire)
    if args.write:
        write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "apply": packet["apply"],
                "hard_retire": packet["hard_retire"],
                "out": rel(out) if args.write else None,
                "missing_columns": packet["schema_state"].get("missing_columns"),
                "routing_view_missing_columns": packet["schema_state"].get("routing_view_missing_columns"),
                "hard_retired_columns_present": packet["schema_state"].get("hard_retired_columns_present"),
                "routing_view_hard_retired_columns_present": packet["schema_state"].get("routing_view_hard_retired_columns_present"),
                "hard_rename_drop_delete_allowed": packet["summary"].get("hard_rename_drop_delete_allowed"),
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if args.validate and packet["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
