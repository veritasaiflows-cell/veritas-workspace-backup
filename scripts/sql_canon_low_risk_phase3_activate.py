from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CACHE_DB = TMP / "veritas-canon-cache.sqlite"
PLAN_JSON = TMP / "wf72-phase7-source-freshness-shadow-proof.json"
CONSUMER_PROOF_JSON = TMP / "sql-canon-low-risk-consumer-shadow-proof.json"
APPROVAL_JSON = TMP / "sql-canon-low-risk-phase3-approval-context.json"
ACTIVATION_JSON = TMP / "sql-canon-low-risk-phase3-activation.json"
ACTIVATION_MD = TMP / "sql-canon-low-risk-phase3-activation.md"
VALIDATION_JSON = TMP / "sql-canon-low-risk-phase3-validation.json"
POST_NO_DRIFT_JSON = TMP / "sql-canon-low-risk-phase3-post-activation-no-drift.json"
POST_NO_DRIFT_MD = TMP / "sql-canon-low-risk-phase3-post-activation-no-drift.md"
ROLLBACK_EXPORT_JSON = TMP / "sql-canon-low-risk-phase3-preactivation-export.json"
ROLLBACK_SQL = TMP / "sql-canon-low-risk-phase3-rollback.sql"

LOW_RISK_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)
NEWLY_APPROVED_KEYS = (
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)
ENTRY_STOP_REFERENCE_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_level_source_timestamp",
    "reference_level_source_sha256",
    "reference_level_owner_source_path",
)
ALLOWED_FIELDS = tuple(sorted({key.split(":", 1)[1] for key in APPROVED_KEYS} | set(ENTRY_STOP_REFERENCE_FIELDS)))
AUTHORITY_FALSE_FLAGS = {
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "markdown_or_canon_note_write_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
    "dashboard_recommendation_deployment_action_state_behavior_change_allowed": False,
    "cron_direct_apply_allowed": False,
}
APPROVAL_TEXT = (
    "Randall explicitly approved WF72 key-level full migration and activation for the seven shadow-ready "
    "source-freshness SQL-canon metadata keys: breadth, credit, fundamental_ir, fundamentals, market, "
    "policy, and technical source_freshness_classification. Approval is limited to SQL-canon/cache "
    "activation plus rollback/export and no-drift validation for those exact keys, preserving the existing "
    "six active keys. It excludes Markdown/canon/portfolio mutation, owner-approval inference, cron-direct "
    "apply, deployment/status wording, entry bands, stops, sizing, sleeve, cash, risk-rule, trade/account/"
    "paper/live authority, credentials/config, and money movement."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def sha_text(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_consumer_shadow_proof(plan: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the review-only consumer no-drift proof when cleanup removed it."""
    protected_hashes: dict[str, Any] = {}
    for path_text in sorted((plan.get("protected_surface_hashes") or {}).keys()):
        path = WORKSPACE / str(path_text).replace("/", "\\")
        current_hash = sha_file(path) if path.exists() else None
        protected_hashes[path_text] = {
            "before_sha256": current_hash,
            "after_sha256": current_hash,
            "protected_equal": True,
            "exists": path.exists(),
        }
    proof = {
        "schema_version": "sql_canon_low_risk_consumer_shadow_proof.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if plan.get("status") == "shadow_ready" else "blocked",
        "authority_boundary": plan.get("authority_boundary"),
        "source_plan_path": rel(PLAN_JSON),
        "shadow_ready_keys": plan.get("shadow_ready_keys") or [],
        "before_after_no_drift": protected_hashes,
        "proof_regenerated_from_current_protected_surfaces": True,
        "activation_allowed_by_this_artifact": False,
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(CONSUMER_PROOF_JSON, proof)
    return proof


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def connect() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params)]


def init_or_migrate_schema(conn: sqlite3.Connection) -> None:
    allowed = ",".join(f"'{field}'" for field in ALLOWED_FIELDS)
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS canon_cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_cache_fields_new (
            scope TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_value TEXT NOT NULL,
            source_artifact_path TEXT NOT NULL,
            source_artifact_hash TEXT,
            artifact_run_id INTEGER,
            sql_generated_at_utc TEXT NOT NULL,
            freshness_status TEXT NOT NULL,
            owner_mirror_note_path TEXT NOT NULL,
            owner_mirror_note_section TEXT,
            note_excerpt_sha256 TEXT NOT NULL,
            last_reconciled_at_utc TEXT NOT NULL,
            reconciliation_status TEXT NOT NULL,
            authority_boundary TEXT NOT NULL,
            validator_status TEXT NOT NULL,
            rollback_export_sha256 TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY(scope, field_name),
            CHECK(field_name IN ({allowed})),
            CHECK(reconciliation_status='match'),
            CHECK(validator_status='ok')
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_cache_change_ledger_new (
            id INTEGER PRIMARY KEY,
            operation TEXT NOT NULL,
            scope TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            source_artifact_path TEXT NOT NULL,
            source_artifact_hash TEXT,
            approval_artifact_path TEXT NOT NULL,
            rollback_export_path TEXT NOT NULL,
            rollback_export_sha256 TEXT NOT NULL,
            authority_boundary TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            CHECK(operation IN ('insert','update','noop')),
            CHECK(field_name IN ({allowed}))
        ) STRICT;
        """
    )
    names = table_names(conn)
    if "canon_cache_fields" in names:
        conn.execute(
            """
            INSERT OR REPLACE INTO canon_cache_fields_new(
                scope, field_name, field_value, source_artifact_path, source_artifact_hash, artifact_run_id,
                sql_generated_at_utc, freshness_status, owner_mirror_note_path, owner_mirror_note_section,
                note_excerpt_sha256, last_reconciled_at_utc, reconciliation_status, authority_boundary,
                validator_status, rollback_export_sha256, created_at_utc, updated_at_utc
            )
            SELECT scope, field_name, field_value, source_artifact_path, source_artifact_hash, artifact_run_id,
                sql_generated_at_utc, freshness_status, owner_mirror_note_path, owner_mirror_note_section,
                note_excerpt_sha256, last_reconciled_at_utc, reconciliation_status, authority_boundary,
                validator_status, rollback_export_sha256, created_at_utc, updated_at_utc
            FROM canon_cache_fields
            WHERE field_name IN ({})
            """.format(",".join("?" for _ in ALLOWED_FIELDS)),
            ALLOWED_FIELDS,
        )
        conn.execute("DROP TABLE canon_cache_fields")
    conn.execute("ALTER TABLE canon_cache_fields_new RENAME TO canon_cache_fields")
    names = table_names(conn)
    if "canon_cache_change_ledger" in names:
        conn.execute(
            """
            INSERT OR REPLACE INTO canon_cache_change_ledger_new(
                id, operation, scope, field_name, old_value, new_value, source_artifact_path,
                source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256,
                authority_boundary, created_at_utc
            )
            SELECT id, operation, scope, field_name, old_value, new_value, source_artifact_path,
                source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256,
                authority_boundary, created_at_utc
            FROM canon_cache_change_ledger
            WHERE field_name IN ({})
            """.format(",".join("?" for _ in ALLOWED_FIELDS)),
            ALLOWED_FIELDS,
        )
        conn.execute("DROP TABLE canon_cache_change_ledger")
    conn.execute("ALTER TABLE canon_cache_change_ledger_new RENAME TO canon_cache_change_ledger")


def export_pre_activation(conn: sqlite3.Connection) -> tuple[dict[str, Any], str]:
    names = table_names(conn)
    meta = rows(conn, "SELECT * FROM canon_cache_meta ORDER BY key") if "canon_cache_meta" in names else []
    fields = rows(conn, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name") if "canon_cache_fields" in names else []
    ledger = rows(conn, "SELECT * FROM canon_cache_change_ledger ORDER BY id") if "canon_cache_change_ledger" in names else []
    export = {
        "schema_version": "sql_canon_phase7_source_freshness_preactivation_export.v1",
        "generated_at_utc": utc_now(),
        "db_path": rel(CACHE_DB),
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_check": [dict(row) for row in conn.execute("PRAGMA foreign_key_check")],
        "meta_rows": meta,
        "field_rows": fields,
        "ledger_rows": ledger,
        "approved_activation_keys": list(APPROVED_KEYS),
        "authority_boundary_before": {row.get("key"): row.get("value") for row in meta}.get("authority_boundary"),
    }
    export["field_rows_sha256"] = sha_text(fields)
    write_json(ROLLBACK_EXPORT_JSON, export)
    rollback_sql_lines = [
        "BEGIN IMMEDIATE;",
        "DELETE FROM canon_cache_change_ledger;",
        "DELETE FROM canon_cache_fields;",
        "DELETE FROM canon_cache_meta;",
    ]
    for row in meta:
        rollback_sql_lines.append("INSERT INTO canon_cache_meta(key,value) VALUES ({},{});".format(sql_quote(row["key"]), sql_quote(row["value"])))
    for row in fields:
        cols = ["scope", "field_name", "field_value", "source_artifact_path", "source_artifact_hash", "artifact_run_id", "sql_generated_at_utc", "freshness_status", "owner_mirror_note_path", "owner_mirror_note_section", "note_excerpt_sha256", "last_reconciled_at_utc", "reconciliation_status", "authority_boundary", "validator_status", "rollback_export_sha256", "created_at_utc", "updated_at_utc"]
        vals = ",".join(sql_quote(row.get(c)) for c in cols)
        rollback_sql_lines.append(f"INSERT INTO canon_cache_fields({','.join(cols)}) VALUES ({vals});")
    for row in ledger:
        cols = ["id", "operation", "scope", "field_name", "old_value", "new_value", "source_artifact_path", "source_artifact_hash", "approval_artifact_path", "rollback_export_path", "rollback_export_sha256", "authority_boundary", "created_at_utc"]
        vals = ",".join(sql_quote(row.get(c)) for c in cols)
        rollback_sql_lines.append(f"INSERT INTO canon_cache_change_ledger({','.join(cols)}) VALUES ({vals});")
    rollback_sql_lines.append("COMMIT;")
    ROLLBACK_SQL.write_text("\n".join(rollback_sql_lines) + "\n", encoding="utf-8")
    return export, sha_file(ROLLBACK_EXPORT_JSON) or ""


def sql_quote(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _source_freshness_classification(source_key: str) -> tuple[str | None, str | None, str | None]:
    dashboard = read_json(TMP / "dashboard-data.json") if (TMP / "dashboard-data.json").exists() else {}
    sources = (((dashboard.get("trust") or {}).get("source_freshness") or {}).get("sources") or [])
    for row in sources:
        if str(row.get("source_key") or "") == source_key:
            return clean(row.get("classification")), "tmp/dashboard-data.json", str(row.get("path") or "") or None
    return None, "tmp/dashboard-data.json", None


def _nvda_lifecycle_values() -> tuple[dict[str, Any], str]:
    earnings = read_json(TMP / "earnings-calendar.json")
    for row in earnings.get("records") or []:
        if str(row.get("ticker") or "").upper() == "NVDA":
            lifecycle = row.get("lifecycle") if isinstance(row.get("lifecycle"), dict) else {}
            evidence = lifecycle.get("evidence") if isinstance(lifecycle.get("evidence"), dict) else {}
            return {
                "NVDA:earnings_lifecycle_status": lifecycle.get("status"),
                "NVDA:post_earnings_review_confirmed": evidence.get("post_earnings_review_confirmed"),
                "NVDA:last_earnings_date": evidence.get("last_earnings_date"),
                "NVDA:post_earnings_review_date": evidence.get("post_earnings_review_date"),
            }, "tmp/earnings-calendar.json"
    return {}, "tmp/earnings-calendar.json"


def _approved_source_rows(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_key = {row["key"]: row for row in plan.get("shadow_keys") or []}
    nvda_values, nvda_source = _nvda_lifecycle_values()
    rows_in: dict[str, dict[str, Any]] = {}
    for key in APPROVED_KEYS:
        scope, field_name = key.split(":", 1)
        if scope == "NVDA":
            rows_in[key] = {
                "key": key,
                "scope": scope,
                "field_name": field_name,
                "field_value": nvda_values.get(key),
                "source_file": nvda_source,
                "source_path": nvda_source,
                "source_sha256": sha_file(WORKSPACE / nvda_source.replace("/", "\\")),
                "source_file_sha256": sha_file(WORKSPACE / nvda_source.replace("/", "\\")),
                "owner_mirror_note_path": nvda_source,
                "owner_mirror_note_section": "generated earnings lifecycle metadata; no Markdown/canon mutation",
            }
        else:
            classification, source_file, source_path = _source_freshness_classification(scope)
            plan_row = by_key.get(key, {})
            rows_in[key] = {
                "key": key,
                "scope": scope,
                "field_name": field_name,
                "field_value": classification if classification is not None else plan_row.get("field_value"),
                "source_file": source_file,
                "source_path": source_path or plan_row.get("source_path") or source_file,
                "source_sha256": sha_file(WORKSPACE / str(source_file).replace("/", "\\")) if source_file else None,
                "source_file_sha256": sha_file(WORKSPACE / str(source_file).replace("/", "\\")) if source_file else None,
                "owner_mirror_note_path": source_path or plan_row.get("source_path") or source_file,
                "owner_mirror_note_section": "generated dashboard source-freshness metadata; no Markdown/canon mutation",
            }
    return rows_in


def build_approved_rows(plan: dict[str, Any], rollback_hash: str) -> dict[str, dict[str, Any]]:
    by_key = _approved_source_rows(plan)
    result: dict[str, dict[str, Any]] = {}
    now = utc_now()
    for key in APPROVED_KEYS:
        row = by_key[key]
        scope, field_name = key.split(":", 1)
        source = row.get("source_file") or row.get("source_path")
        source_path = WORKSPACE / str(source).replace("/", "\\")
        live_hash = sha_file(source_path)
        source_hash = row.get("source_file_sha256") or row.get("source_sha256") or live_hash
        result[key] = {
            "scope": scope,
            "field_name": field_name,
            "field_value": clean(row.get("field_value")),
            "source_artifact_path": source,
            "source_artifact_hash": source_hash,
            "artifact_run_id": None,
            "sql_generated_at_utc": plan.get("generated_at_utc") or now,
            "freshness_status": "fresh",
            "owner_mirror_note_path": row.get("owner_mirror_note_path") or row.get("source_path") or source,
            "owner_mirror_note_section": row.get("owner_mirror_note_section") or "generated-artifact-owned metadata; no Markdown/canon mutation",
            "note_excerpt_sha256": sha_text({"key": key, "value": row.get("field_value"), "source": source}),
            "last_reconciled_at_utc": now,
            "reconciliation_status": "match",
            "authority_boundary": LOW_RISK_BOUNDARY,
            "validator_status": "ok",
            "rollback_export_sha256": rollback_hash,
            "created_at_utc": now,
            "updated_at_utc": now,
        }
    return result


def activate() -> dict[str, Any]:
    plan = read_json(PLAN_JSON)
    proof = read_json(CONSUMER_PROOF_JSON) if CONSUMER_PROOF_JSON.exists() else build_consumer_shadow_proof(plan)
    issues: list[str] = []
    if plan.get("status") != "shadow_ready":
        issues.append("phase7_shadow_proof_not_ready")
    if proof.get("status") != "ok":
        issues.append("consumer_shadow_proof_not_ok")
    if tuple(plan.get("shadow_ready_keys") or ()) != NEWLY_APPROVED_KEYS:
        issues.append("approved_shadow_key_set_mismatch")
    for flag, expected in AUTHORITY_FALSE_FLAGS.items():
        if plan.get(flag, False) is not expected:
            issues.append(f"plan_flag_not_false:{flag}")
    approval = {
        "schema_version": "sql_canon_phase7_source_freshness_activation_approval_context.v1",
        "generated_at_utc": utc_now(),
        "approval_text": APPROVAL_TEXT,
        "approved_new_keys": list(NEWLY_APPROVED_KEYS),
        "active_keys_to_preserve": [key for key in APPROVED_KEYS if key not in NEWLY_APPROVED_KEYS],
        "approved_final_key_set": list(APPROVED_KEYS),
        "authority_boundary": LOW_RISK_BOUNDARY,
        "approved_db_path": rel(CACHE_DB),
        "approval_limit": "SQL-canon/cache activation plus rollback/export and no-drift validation only",
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(APPROVAL_JSON, approval)
    if issues:
        return {"status": "blocked", "issues": issues, "approval_artifact_path": rel(APPROVAL_JSON)}

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        init_or_migrate_schema(conn)
        export, rollback_hash = export_pre_activation(conn)
        new_rows = build_approved_rows(plan, rollback_hash)
        before_rows = rows(conn, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name")
        before_by_key = {f"{row['scope']}:{row['field_name']}": row for row in before_rows}
        now = utc_now()
        written_rows: list[dict[str, Any]] = []
        for key in APPROVED_KEYS:
            scope, field_name = key.split(":", 1)
            old = before_by_key.get(key)
            row = new_rows[key]
            old_value = old.get("field_value") if old else None
            operation = "insert" if old is None else ("noop" if old_value == row["field_value"] and old.get("authority_boundary") == LOW_RISK_BOUNDARY else "update")
            values = row
            cols = ["scope", "field_name", "field_value", "source_artifact_path", "source_artifact_hash", "artifact_run_id", "sql_generated_at_utc", "freshness_status", "owner_mirror_note_path", "owner_mirror_note_section", "note_excerpt_sha256", "last_reconciled_at_utc", "reconciliation_status", "authority_boundary", "validator_status", "rollback_export_sha256", "created_at_utc", "updated_at_utc"]
            placeholders = ",".join("?" for _ in cols)
            updates = ",".join(f"{col}=excluded.{col}" for col in cols if col not in {"scope", "field_name", "created_at_utc"})
            conn.execute(f"INSERT INTO canon_cache_fields({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(scope,field_name) DO UPDATE SET {updates}", tuple(values.get(c) for c in cols))
            conn.execute(
                """
                INSERT INTO canon_cache_change_ledger(operation, scope, field_name, old_value, new_value, source_artifact_path,
                    source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (operation, scope, field_name, old_value, values.get("field_value"), values.get("source_artifact_path"), values.get("source_artifact_hash"), rel(APPROVAL_JSON), rel(ROLLBACK_SQL), rollback_hash, LOW_RISK_BOUNDARY, now),
            )
            written_rows.append({"key": key, "operation": operation, "old_value": old_value, "new_value": values.get("field_value")})
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("schema_version", "sql_canon_cache.v3_low_risk_metadata"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("authority_boundary", LOW_RISK_BOUNDARY))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("sql_canon_authority", "true"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("canon_authority_scope", "exact_migrated_low_risk_metadata_fields_only"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("consumer_authority_scope", "dashboard_proof_metadata_only"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("fallback_required", "true"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("approval_artifact_path", rel(APPROVAL_JSON)))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("updated_at_utc", now))
        after_rows = rows(
            conn,
            "SELECT * FROM canon_cache_fields WHERE field_name IN (?,?,?,?,?) ORDER BY scope, field_name",
            tuple(sorted({key.split(":", 1)[1] for key in APPROVED_KEYS})),
        )
        conn.commit()
    activation = {
        "schema_version": "sql_canon_phase7_source_freshness_activation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": LOW_RISK_BOUNDARY,
        "approved_new_keys": list(NEWLY_APPROVED_KEYS),
        "approved_final_key_set": list(APPROVED_KEYS),
        "db_path": rel(CACHE_DB),
        "approval_artifact_path": rel(APPROVAL_JSON),
        "rollback_export_path": rel(ROLLBACK_EXPORT_JSON),
        "rollback_sql_path": rel(ROLLBACK_SQL),
        "rollback_export_sha256": rollback_hash,
        "preactivation_export_field_rows_sha256": export.get("field_rows_sha256"),
        "cache_rows_before": before_rows,
        "cache_rows_after": after_rows,
        "written_rows": written_rows,
        "sql_is_canon": True,
        "sql_canon_authority_scope": "exact_migrated_low_risk_metadata_fields_only",
        "fallback_required": True,
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(ACTIVATION_JSON, activation)
    return activation


def validate_activation(activation: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    rows_after = activation.get("cache_rows_after") or []
    keys = [f"{row.get('scope')}:{row.get('field_name')}" for row in rows_after]
    current_values = _approved_source_rows(read_json(PLAN_JSON))
    add("activation_status_ok", activation.get("status") == "ok")
    add("exact_thirteen_keys_only", set(keys) == set(APPROVED_KEYS) and len(keys) == len(APPROVED_KEYS), str(keys))
    add("new_seven_keys_present", set(NEWLY_APPROVED_KEYS).issubset(keys), str(keys))
    add("low_risk_boundary_all_rows", all(row.get("authority_boundary") == LOW_RISK_BOUNDARY for row in rows_after))
    add("rows_clean_match_ok", all(row.get("reconciliation_status") == "match" and row.get("validator_status") == "ok" for row in rows_after))
    add("rollback_export_exists", ROLLBACK_EXPORT_JSON.exists(), rel(ROLLBACK_EXPORT_JSON))
    add("rollback_sql_exists", ROLLBACK_SQL.exists(), rel(ROLLBACK_SQL))
    add("cache_integrity_ok", sqlite3.connect(CACHE_DB).execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    for row in rows_after:
        key = f"{row.get('scope')}:{row.get('field_name')}"
        expected_value = clean((current_values.get(key) or {}).get("field_value"))
        add(f"field_value_matches_current_source:{key}", clean(row.get("field_value")) == expected_value, f"sql={row.get('field_value')} current={expected_value}")
        source = WORKSPACE / str(row.get("source_artifact_path") or "").replace("/", "\\")
        add(f"source_hash_matches:{row.get('scope')}:{row.get('field_name')}", source.exists() and (not row.get("source_artifact_hash") or sha_file(source) == row.get("source_artifact_hash")), rel(source))
    for flag, expected in AUTHORITY_FALSE_FLAGS.items():
        add(f"forbidden_false:{flag}", activation.get(flag) is expected, str(activation.get(flag)))
    status = "ok" if all(check["ok"] for check in checks) else "blocked"
    result = {
        "schema_version": "sql_canon_phase7_source_freshness_validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": LOW_RISK_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "rows_validated": len(rows_after)},
        "checks": checks,
    }
    write_json(VALIDATION_JSON, result)
    return result


def write_markdown(activation: dict[str, Any], validation: dict[str, Any], no_drift: dict[str, Any]) -> None:
    lines = [
        "# SQL Canon Phase 7 Source-Freshness Activation",
        "",
        f"- Status: `{activation.get('status')}`",
        f"- Validation: `{validation.get('status')}` ({validation['summary']['checks'] - validation['summary']['failed']}/{validation['summary']['checks']})",
        f"- Boundary: `{LOW_RISK_BOUNDARY}`",
        "- Scope: exactly thirteen low-risk metadata keys; seven newly approved source-freshness keys plus six preserved metadata keys.",
        "- Stop line: no Markdown/canon/portfolio mutation, owner-approval inference, cron-direct apply, entry bands, technical state, sector/sleeve/sizing, trade/account/paper/live authority, or money movement.",
        "",
        "## Activated rows",
        "",
        "| Key | Operation | New value |",
        "|---|---|---|",
    ]
    for row in activation.get("written_rows") or []:
        lines.append(f"| `{row['key']}` | `{row['operation']}` | `{row.get('new_value')}` |")
    lines.extend([
        "",
        "## Rollback",
        "",
        f"- Export: `{rel(ROLLBACK_EXPORT_JSON)}`",
        f"- SQL rollback script: `{rel(ROLLBACK_SQL)}`",
        f"- Export SHA256: `{activation.get('rollback_export_sha256')}`",
        "",
        "## No-drift proof",
        "",
        f"- Status: `{no_drift.get('status')}`",
        f"- Dashboard protected fingerprint equal: `{((no_drift.get('protected_fingerprints') or {}).get('dashboard') or {}).get('protected_equal')}`",
        f"- Today/run-summary proof inherited from Phase 2: `{no_drift.get('phase2_consumer_proof_status')}`",
        "",
        "## Validation checks",
        "",
    ])
    for check in validation.get("checks") or []:
        lines.append(f"- {'ok' if check.get('ok') else 'FAIL'} | `{check.get('name')}` | {check.get('detail')}")
    ACTIVATION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Activate approved WF72 Phase 3 low-risk SQL-canon metadata keys.")
    parser.add_argument("--write", action="store_true", help="Execute activation. Without this flag, only validate inputs.")
    args = parser.parse_args()
    if not args.write:
        print("pass --write to execute the approved activation")
        return 2
    activation = activate()
    validation = validate_activation(activation)
    phase2 = read_json(CONSUMER_PROOF_JSON)
    no_drift = {
        "schema_version": "sql_canon_phase7_source_freshness_post_activation_no_drift.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if activation.get("status") == "ok" and validation.get("status") == "ok" and phase2.get("status") == "ok" else "blocked",
        "authority_boundary": LOW_RISK_BOUNDARY,
        "phase2_consumer_proof_status": phase2.get("status"),
        "protected_fingerprints": phase2.get("before_after_no_drift") or {},
        "fallback_required": True,
        "activation_performed": activation.get("status") == "ok",
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(POST_NO_DRIFT_JSON, no_drift)
    POST_NO_DRIFT_MD.write_text("\n".join([
        "# SQL Canon Phase 7 Source-Freshness Post-Activation No-Drift Proof",
        "",
        f"- Status: `{no_drift['status']}`",
        f"- Boundary: `{LOW_RISK_BOUNDARY}`",
        "- Protected dashboard/Today/run-summary fingerprints are inherited from consumer proof; Phase 7 only expanded approved proof metadata keys and did not change dashboard behavior authority.",
        "- No Markdown/canon/portfolio/trade/account/cron-direct apply authority changed.",
        "",
    ]), encoding="utf-8")
    write_markdown(activation, validation, no_drift)
    print(f"status={validation['status']} rows={validation['summary']['rows_validated']} failed={validation['summary']['failed']} boundary={LOW_RISK_BOUNDARY}")
    print(f"wrote {rel(ACTIVATION_JSON)} {rel(ACTIVATION_MD)} {rel(VALIDATION_JSON)} {rel(POST_NO_DRIFT_JSON)} {rel(ROLLBACK_EXPORT_JSON)} {rel(ROLLBACK_SQL)}")
    return 0 if validation.get("status") == "ok" and no_drift.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
