from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CACHE_DB = TMP / "veritas-canon-cache.sqlite"
WORKER_JSON = TMP / "wf72-entry-stop-sql-activation-pilot-worker.json"
APPROVAL_JSON = TMP / "wf72-entry-stop-sql-activation-first-slice-approval-request.json"
STATE_JSON = TMP / "wf72-entry-stop-sql-activation-state.json"
STATE_MD = TMP / "wf72-entry-stop-sql-activation-state.md"
PACKET_JSON = TMP / "wf72-entry-stop-sql-activation-packet.json"
PACKET_MD = TMP / "wf72-entry-stop-sql-activation-packet.md"
VALIDATION_JSON = TMP / "wf72-entry-stop-sql-activation-validation.json"
ROLLBACK_DRILL_JSON = TMP / "wf72-entry-stop-sql-activation-rollback-drill.json"
EXPORT_JSON = TMP / "wf72-entry-stop-sql-activation-prewrite-export.json"
ROLLBACK_SQL = TMP / "wf72-entry-stop-sql-activation-rollback.sql"

LOW_RISK_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
ENTRY_STOP_BOUNDARY = "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority"
MIXED_CACHE_META_BOUNDARIES = {LOW_RISK_BOUNDARY, ENTRY_STOP_BOUNDARY}
ENTRY_STOP_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_level_source_timestamp",
    "reference_level_source_sha256",
    "reference_level_owner_source_path",
)
LOW_RISK_FIELDS = (
    "earnings_lifecycle_status",
    "last_earnings_date",
    "post_earnings_review_confirmed",
    "post_earnings_review_date",
    "source_freshness_classification",
)
ALLOWED_FIELDS = LOW_RISK_FIELDS + ENTRY_STOP_FIELDS
AUTHORITY_FALSE_FLAGS = {
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "dashboard_recommendation_deployment_action_state_behavior_change_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
    "credential_config_mutation_allowed": False,
    "config_auth_channel_service_mutation_allowed": False,
}

BATCH_SIZES = {"nvda": 1, "first-5": 5, "first-10": 10, "all": 42}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def activation_approval(batch: str) -> dict[str, Any]:
    """Validate the original activation gate or a deleted-artifact refresh gate.

    The first-slice request JSON was a generated proof artifact. If cleanup removed
    it after the 252-row family was already active, refreshes may still proceed only
    when the live cache proves the exact WF72 no-execution-authority family.
    """
    if APPROVAL_JSON.exists():
        approval = read_json(APPROVAL_JSON)
        if approval.get("recommended_first_slice", {}).get("ticker") != "NVDA":
            raise SystemExit("first-slice approval artifact mismatch")
        return approval
    if batch != "all":
        raise SystemExit(f"approval artifact missing for non-full batch: {rel(APPROVAL_JSON)}")
    if not CACHE_DB.exists():
        raise SystemExit(f"approval artifact missing and cache DB absent: {rel(APPROVAL_JSON)}")
    expected_keys = set(target_keys(batch))
    with connect() as conn:
        names = table_names(conn)
        if "canon_cache_fields" not in names or "canon_cache_meta" not in names:
            raise SystemExit(f"approval artifact missing and cache tables absent: {rel(APPROVAL_JSON)}")
        meta = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM canon_cache_meta")}
        field_rows = rows(
            conn,
            "SELECT scope, field_name, authority_boundary, validator_status, reconciliation_status "
            "FROM canon_cache_fields WHERE field_name IN (?,?,?,?,?,?)",
            ENTRY_STOP_FIELDS,
        )
    active_keys = {f"{row['scope']}:{row['field_name']}" for row in field_rows}
    if active_keys != expected_keys:
        raise SystemExit(
            f"approval artifact missing and active WF72 key set mismatch: "
            f"active={len(active_keys)} expected={len(expected_keys)}"
        )
    if any(row["authority_boundary"] != ENTRY_STOP_BOUNDARY for row in field_rows):
        raise SystemExit("approval artifact missing and active WF72 boundary mismatch")
    if any(row["validator_status"] != "ok" or row["reconciliation_status"] != "match" for row in field_rows):
        raise SystemExit("approval artifact missing and active WF72 validation state mismatch")
    if meta.get("authority_boundary") not in MIXED_CACHE_META_BOUNDARIES:
        raise SystemExit("approval artifact missing and cache authority boundary mismatch")
    return {
        "recommended_first_slice": {"ticker": "NVDA"},
        "approval_artifact_missing_after_cleanup": True,
        "mixed_family_cache_refresh_allowed": True,
        "cache_meta_authority_boundary": meta.get("authority_boundary"),
        "cache_meta_approval_artifact_path": meta.get("approval_artifact_path"),
        "existing_active_family_key_count": len(active_keys),
        "approval_artifact_path": rel(APPROVAL_JSON),
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except Exception:
        return None


def connect(path: Path = CACHE_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params)]


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def init_or_migrate_schema(conn: sqlite3.Connection) -> None:
    """Extend the strict cache table allowlist to WF72 reference fields."""
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
        cols = "scope, field_name, field_value, source_artifact_path, source_artifact_hash, artifact_run_id, sql_generated_at_utc, freshness_status, owner_mirror_note_path, owner_mirror_note_section, note_excerpt_sha256, last_reconciled_at_utc, reconciliation_status, authority_boundary, validator_status, rollback_export_sha256, created_at_utc, updated_at_utc"
        conn.execute(f"INSERT OR REPLACE INTO canon_cache_fields_new({cols}) SELECT {cols} FROM canon_cache_fields WHERE field_name IN ({','.join('?' for _ in ALLOWED_FIELDS)})", ALLOWED_FIELDS)
        conn.execute("DROP TABLE canon_cache_fields")
    conn.execute("ALTER TABLE canon_cache_fields_new RENAME TO canon_cache_fields")
    names = table_names(conn)
    if "canon_cache_change_ledger" in names:
        cols = "id, operation, scope, field_name, old_value, new_value, source_artifact_path, source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc"
        conn.execute(f"INSERT OR REPLACE INTO canon_cache_change_ledger_new({cols}) SELECT {cols} FROM canon_cache_change_ledger WHERE field_name IN ({','.join('?' for _ in ALLOWED_FIELDS)})", ALLOWED_FIELDS)
        conn.execute("DROP TABLE canon_cache_change_ledger")
    conn.execute("ALTER TABLE canon_cache_change_ledger_new RENAME TO canon_cache_change_ledger")


def worker_rows() -> list[dict[str, Any]]:
    data = read_json(WORKER_JSON)
    fields = tuple(data.get("candidate_fields") or [])
    if fields != ENTRY_STOP_FIELDS:
        raise SystemExit(f"candidate field contract mismatch: {fields}")
    candidates = [r for r in data.get("candidate_rows") or [] if isinstance(r, dict) and r.get("ticker")]
    if len(candidates) != 42:
        raise SystemExit(f"expected 42 candidate rows, got {len(candidates)}")
    by_ticker = {str(r["ticker"]).upper(): r for r in candidates}
    if "NVDA" not in by_ticker:
        raise SystemExit("NVDA first slice missing")
    ordered = [by_ticker["NVDA"]]
    ordered.extend(r for r in candidates if str(r.get("ticker")).upper() != "NVDA")
    return ordered


def target_tickers(batch: str) -> list[str]:
    ordered = worker_rows()
    size = BATCH_SIZES[batch]
    return [str(r["ticker"]).upper() for r in ordered[:size]]


def target_keys(batch: str) -> list[str]:
    return [f"{ticker}:{field}" for ticker in target_tickers(batch) for field in ENTRY_STOP_FIELDS]


def current_state() -> dict[str, Any]:
    if STATE_JSON.exists():
        try:
            return read_json(STATE_JSON)
        except Exception:
            return {}
    return {}


def export_cache(affected_keys: list[str]) -> tuple[dict[str, Any], str]:
    with connect() as conn:
        field_rows = rows(conn, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name")
        meta_rows = rows(conn, "SELECT * FROM canon_cache_meta ORDER BY key")
        ledger_rows = rows(conn, "SELECT * FROM canon_cache_change_ledger ORDER BY id")
    before_by_key = {f"{r['scope']}:{r['field_name']}": r for r in field_rows}
    export = {
        "schema_version": "wf72_entry_stop_sql_activation_prewrite_export.v1",
        "generated_at_utc": utc_now(),
        "db_path": rel(CACHE_DB),
        "affected_keys": affected_keys,
        "affected_prior_rows": [before_by_key[k] for k in affected_keys if k in before_by_key],
        "all_field_rows": field_rows,
        "meta_rows": meta_rows,
        "ledger_rows": ledger_rows,
        **AUTHORITY_FALSE_FLAGS,
    }
    payload = json.dumps(export, indent=2, sort_keys=True).encode("utf-8")
    export["export_sha256"] = sha256_bytes(payload)
    write_json(EXPORT_JSON, export)
    return export, export["export_sha256"]


def sql_quote(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def write_rollback_sql(export: dict[str, Any]) -> str:
    cols = [
        "scope", "field_name", "field_value", "source_artifact_path", "source_artifact_hash", "artifact_run_id",
        "sql_generated_at_utc", "freshness_status", "owner_mirror_note_path", "owner_mirror_note_section",
        "note_excerpt_sha256", "last_reconciled_at_utc", "reconciliation_status", "authority_boundary",
        "validator_status", "rollback_export_sha256", "created_at_utc", "updated_at_utc",
    ]
    lines = ["BEGIN IMMEDIATE;"]
    for key in export["affected_keys"]:
        scope, field = key.split(":", 1)
        lines.append(f"DELETE FROM canon_cache_fields WHERE scope={sql_quote(scope)} AND field_name={sql_quote(field)};")
    for row in export["affected_prior_rows"]:
        vals = ",".join(sql_quote(row.get(c)) for c in cols)
        lines.append(f"INSERT INTO canon_cache_fields({','.join(cols)}) VALUES ({vals});")
    # Restore the metadata rows captured immediately before the batch.
    lines.append("DELETE FROM canon_cache_meta;")
    for row in export["meta_rows"]:
        lines.append(f"INSERT INTO canon_cache_meta(key,value) VALUES ({sql_quote(row.get('key'))},{sql_quote(row.get('value'))});")
    lines.append("COMMIT;")
    ROLLBACK_SQL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sha256_file(ROLLBACK_SQL) or ""


def build_rows(batch: str, rollback_hash: str) -> list[dict[str, Any]]:
    by_ticker = {str(r["ticker"]).upper(): r for r in worker_rows()}
    now = utc_now()
    out: list[dict[str, Any]] = []
    source_path = WORKSPACE / "03. Portfolio" / "Execution Board.md"
    source_hash = sha256_file(source_path)
    for ticker in target_tickers(batch):
        src = by_ticker[ticker]
        if src.get("reference_level_owner_source_path") != "03. Portfolio/Execution Board.md":
            raise SystemExit(f"unexpected source path for {ticker}: {src.get('reference_level_owner_source_path')}")
        if source_hash and src.get("reference_level_source_sha256") != source_hash:
            raise SystemExit(f"source hash mismatch for {ticker}: worker={src.get('reference_level_source_sha256')} live={source_hash}")
        for field in ENTRY_STOP_FIELDS:
            value = src.get(field)
            excerpt = f"{ticker}:{field}:{value}:{src.get('reference_level_source_sha256')}".encode("utf-8")
            out.append({
                "scope": ticker,
                "field_name": field,
                "field_value": str(value),
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": src.get("reference_level_source_sha256"),
                "artifact_run_id": None,
                "sql_generated_at_utc": now,
                "freshness_status": "fresh",
                "owner_mirror_note_path": "03. Portfolio/Execution Board.md",
                "owner_mirror_note_section": "WF72 entry/stop reference metadata; display/proof cache only; no action-state or execution authority",
                "note_excerpt_sha256": sha256_bytes(excerpt),
                "last_reconciled_at_utc": now,
                "reconciliation_status": "match",
                "authority_boundary": ENTRY_STOP_BOUNDARY,
                "validator_status": "ok",
                "rollback_export_sha256": rollback_hash,
                "created_at_utc": now,
                "updated_at_utc": now,
            })
    return out


def build_packet(batch: str, target: list[str], export_hash: str, rollback_hash: str) -> dict[str, Any]:
    by_ticker = {str(r["ticker"]).upper(): r for r in worker_rows()}
    packet = {
        "schema_version": "wf72_entry_stop_sql_activation_packet.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_batch_write",
        "batch": batch,
        "target_tickers": target_tickers(batch),
        "target_keys": target,
        "target_key_count": len(target),
        "authority_boundary": ENTRY_STOP_BOUNDARY,
        "approval_source": "Randall approved NVDA first slice and staged 1->5->10->remaining expansion on 2026-05-24 14:07 MST; exact family remains reference metadata only.",
        "export_path": rel(EXPORT_JSON),
        "export_sha256": export_hash,
        "rollback_sql_path": rel(ROLLBACK_SQL),
        "rollback_sql_sha256": rollback_hash,
        "source_lineage": {
            ticker: {
                "owner_source_path": by_ticker[ticker].get("reference_level_owner_source_path"),
                "source_timestamp": by_ticker[ticker].get("reference_level_source_timestamp"),
                "source_sha256": by_ticker[ticker].get("reference_level_source_sha256"),
            }
            for ticker in target_tickers(batch)
        },
        "fallback_equality_no_drift": [
            {"key": key, "status": "match", "fallback_source": "tmp/wf72-entry-stop-sql-activation-pilot-worker.json + 03. Portfolio/Execution Board.md"}
            for key in target
        ],
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(PACKET_JSON, packet)
    PACKET_MD.write_text(
        "# WF72 entry/stop SQL activation packet\n\n"
        f"- Batch: `{batch}`\n"
        f"- Status: `{packet['status']}`\n"
        f"- Target keys: {len(target)}\n"
        f"- Boundary: `{ENTRY_STOP_BOUNDARY}`\n"
        "- Authority: metadata/proof cache only; no portfolio/canon/apply/trade/account/paper/live authority.\n",
        encoding="utf-8",
    )
    return packet


def activate(batch: str) -> dict[str, Any]:
    activation_approval(batch)
    keys = target_keys(batch)
    export, export_hash = export_cache(keys)
    rollback_hash = write_rollback_sql(export)
    packet = build_packet(batch, keys, export_hash, rollback_hash)
    new_rows = build_rows(batch, rollback_hash)
    prior_meta = {row.get("key"): row.get("value") for row in export.get("meta_rows") or []}
    meta_authority_boundary = prior_meta.get("authority_boundary")
    if meta_authority_boundary not in MIXED_CACHE_META_BOUNDARIES:
        meta_authority_boundary = ENTRY_STOP_BOUNDARY
    cols = [
        "scope", "field_name", "field_value", "source_artifact_path", "source_artifact_hash", "artifact_run_id",
        "sql_generated_at_utc", "freshness_status", "owner_mirror_note_path", "owner_mirror_note_section",
        "note_excerpt_sha256", "last_reconciled_at_utc", "reconciliation_status", "authority_boundary",
        "validator_status", "rollback_export_sha256", "created_at_utc", "updated_at_utc",
    ]
    before_by_key = {f"{r['scope']}:{r['field_name']}": r for r in export["all_field_rows"]}
    written: list[dict[str, Any]] = []
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        init_or_migrate_schema(conn)
        now = utc_now()
        for row in new_rows:
            key = f"{row['scope']}:{row['field_name']}"
            old = before_by_key.get(key)
            operation = "insert" if old is None else ("noop" if old.get("field_value") == row["field_value"] and old.get("authority_boundary") == ENTRY_STOP_BOUNDARY else "update")
            placeholders = ",".join("?" for _ in cols)
            updates = ",".join(f"{col}=excluded.{col}" for col in cols if col not in {"scope", "field_name", "created_at_utc"})
            conn.execute(f"INSERT INTO canon_cache_fields({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(scope,field_name) DO UPDATE SET {updates}", tuple(row.get(c) for c in cols))
            conn.execute(
                """
                INSERT INTO canon_cache_change_ledger(operation, scope, field_name, old_value, new_value, source_artifact_path,
                    source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (operation, row["scope"], row["field_name"], old.get("field_value") if old else None, row["field_value"], row["source_artifact_path"], row["source_artifact_hash"], rel(APPROVAL_JSON), rel(EXPORT_JSON), rollback_hash, ENTRY_STOP_BOUNDARY, now),
            )
            written.append({"key": key, "operation": operation, "old_value": old.get("field_value") if old else None, "new_value": row["field_value"]})
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("schema_version", "sql_canon_cache.v4_mixed_low_risk_plus_wf72_entry_stop_reference_metadata"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("authority_boundary", meta_authority_boundary))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("sql_canon_authority", "true"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("canon_authority_scope", "low_risk_metadata_plus_exact_gated_entry_stop_reference_metadata_only"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("consumer_authority_scope", "dashboard_proof_metadata_only"))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("fallback_required", "true"))
        if prior_meta.get("approval_artifact_path"):
            conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("approval_artifact_path", prior_meta.get("approval_artifact_path")))
        else:
            conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("approval_artifact_path", rel(APPROVAL_JSON)))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("wf72_entry_stop_authority_boundary", ENTRY_STOP_BOUNDARY))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("wf72_entry_stop_approval_artifact_path", rel(APPROVAL_JSON)))
        conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key,value) VALUES (?,?)", ("updated_at_utc", now))
        conn.commit()
    state = {
        "schema_version": "wf72_entry_stop_sql_activation_state.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if batch != "all" else "activation_ready",
        "last_batch": batch,
        "active_tickers": target_tickers(batch),
        "active_entry_stop_reference_keys": keys,
        "active_entry_stop_reference_key_count": len(keys),
        "full_family_candidate_key_count": 252,
        "full_family_activation_ready": batch == "all",
        "authority_boundary": ENTRY_STOP_BOUNDARY,
        "activation_packet_path": rel(PACKET_JSON),
        "rollback_sql_path": rel(ROLLBACK_SQL),
        "prewrite_export_path": rel(EXPORT_JSON),
        "written_rows": written,
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(STATE_JSON, state)
    STATE_MD.write_text(
        "# WF72 entry/stop SQL activation state\n\n"
        f"- Status: `{state['status']}`\n"
        f"- Last batch: `{batch}`\n"
        f"- Active tickers: {len(state['active_tickers'])}\n"
        f"- Active reference keys: {len(keys)} / 252\n"
        f"- Full-family activation ready: `{state['full_family_activation_ready']}`\n",
        encoding="utf-8",
    )
    return state


def validate(batch: str) -> dict[str, Any]:
    state = current_state()
    expected_keys = target_keys(batch)
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    with connect() as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        cache_rows = rows(conn, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name")
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM canon_cache_meta")}
    row_by_key = {f"{r['scope']}:{r['field_name']}": r for r in cache_rows}
    add("cache_integrity_ok", integrity == "ok", str(integrity))
    add("state_matches_batch", state.get("last_batch") == batch, str(state.get("last_batch")))
    add("expected_keys_present", all(k in row_by_key for k in expected_keys), str([k for k in expected_keys if k not in row_by_key][:5]))
    add("no_extra_entry_stop_keys", sorted(k for k in row_by_key if k.split(":",1)[1] in ENTRY_STOP_FIELDS) == sorted(expected_keys), "")
    add("entry_stop_rows_boundary_ok", all(row_by_key[k].get("authority_boundary") == ENTRY_STOP_BOUNDARY for k in expected_keys if k in row_by_key), "")
    add("entry_stop_rows_match_ok", all(row_by_key[k].get("reconciliation_status") == "match" and row_by_key[k].get("validator_status") == "ok" for k in expected_keys if k in row_by_key), "")
    add("meta_boundary_allowed_for_mixed_cache", meta.get("authority_boundary") in MIXED_CACHE_META_BOUNDARIES, str(meta.get("authority_boundary")))
    add("wf72_meta_boundary_recorded", meta.get("wf72_entry_stop_authority_boundary") in {None, ENTRY_STOP_BOUNDARY}, str(meta.get("wf72_entry_stop_authority_boundary")))
    add("rollback_sql_exists", ROLLBACK_SQL.exists(), rel(ROLLBACK_SQL))
    add("export_exists", EXPORT_JSON.exists(), rel(EXPORT_JSON))
    validation = {
        "schema_version": "wf72_entry_stop_sql_activation_validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if all(c["ok"] for c in checks) else "blocked",
        "batch": batch,
        "expected_key_count": len(expected_keys),
        "active_entry_stop_key_count": len([k for k in row_by_key if k.split(":",1)[1] in ENTRY_STOP_FIELDS]),
        "checks": checks,
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(VALIDATION_JSON, validation)
    return validation


def rollback_drill(batch: str) -> dict[str, Any]:
    drill_db = TMP / "wf72-entry-stop-sql-activation-rollback-drill.sqlite"
    if drill_db.exists():
        drill_db.unlink()
    shutil.copy2(CACHE_DB, drill_db)
    sql = ROLLBACK_SQL.read_text(encoding="utf-8")
    export = read_json(EXPORT_JSON)
    expected_rows = export.get("all_field_rows") or []
    with connect(drill_db) as conn:
        before_integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.executescript(sql)
        after_integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        after_rows = rows(conn, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name")
    expected_hash = sha256_bytes(json.dumps(expected_rows, sort_keys=True).encode("utf-8"))
    after_hash = sha256_bytes(json.dumps(after_rows, sort_keys=True).encode("utf-8"))
    drill = {
        "schema_version": "wf72_entry_stop_sql_activation_rollback_drill.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if before_integrity == "ok" and after_integrity == "ok" and expected_hash == after_hash else "blocked",
        "batch": batch,
        "drill_db_path": rel(drill_db),
        "rollback_sql_path": rel(ROLLBACK_SQL),
        "before_integrity": before_integrity,
        "after_integrity": after_integrity,
        "rollback_restored_prewrite_field_rows": expected_hash == after_hash,
        "prewrite_field_rows_sha256": expected_hash,
        "after_rollback_field_rows_sha256": after_hash,
        "real_cache_mutated_by_drill": False,
        **AUTHORITY_FALSE_FLAGS,
    }
    write_json(ROLLBACK_DRILL_JSON, drill)
    return drill


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", choices=sorted(BATCH_SIZES), required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Required for activation writes. Omit with --validate-only for routine proof.")
    args = parser.parse_args()
    if args.validate_only:
        validation = validate(args.batch)
        print(json.dumps({"status": validation["status"], "batch": args.batch, "expected_key_count": validation["expected_key_count"]}, indent=2))
        return 0 if validation["status"] == "ok" else 1
    if not args.apply:
        print(json.dumps({
            "status": "blocked_requires_apply",
            "batch": args.batch,
            "message": "Activation writes require --apply. Use --validate-only for routine proof.",
        }, indent=2))
        return 2
    state = activate(args.batch)
    validation = validate(args.batch)
    drill = rollback_drill(args.batch)
    status = "ok" if state.get("status") in {"ok", "activation_ready"} and validation.get("status") == "ok" and drill.get("status") == "ok" else "blocked"
    print(json.dumps({"status": status, "batch": args.batch, "active_keys": state.get("active_entry_stop_reference_key_count"), "full_family_activation_ready": state.get("full_family_activation_ready")}, indent=2))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
