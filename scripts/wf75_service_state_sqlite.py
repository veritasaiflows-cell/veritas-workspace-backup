#!/usr/bin/env python3
"""Build the WF75 SQLite WAL control-plane proof for Veritas.

This is a local coordination/control-plane database for anonymous WF75 service
state, artifact references, queue rows, and claim behavior. It is not finance
canon, not customer truth, not an approval surface, not a ticker import path,
and not trade/account/paper/live authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_DB = TMP / "wf75-service-state.sqlite"
DEFAULT_SUMMARY = TMP / "wf75-service-state-sqlite.json"

SERVICE_STATE = TMP / "wf75-service-state-current.json"
DEFAULT_SERVICE_RUN = TMP / "wf75-service-runs" / "wf75-anon-watchlist-ai-infrastructure-v1.json"
OPERATOR_QUEUE = TMP / "wf75-operator-queue.json"
MOVEMENT = TMP / "wf75-automation-movement.json"
WF77_BRIDGE = TMP / "wf77-price-freshness-bridge.json"
WF77_SUPPLEMENTAL = TMP / "wf77-supplemental-price-evidence.json"
RENDERER_REGRESSION = TMP / "wf75-renderer-export-regression.json"
SCENARIO_LIBRARY = TMP / "wf75-scenario-template-library.json"
READINESS_PLAN = TMP / "wf75-service-led-saas-readiness-plan.json"
PM_WEEKLY_UPDATE = TMP / "wf75-pm-weekly-update.json"
OPERATOR_CONSOLE = TMP / "wf75-operator-console.json"

SCHEMA = "veritas.wf75.service_state_sqlite_control_plane.v1"

AUTHORITY_FALSE_KEYS = [
    "real_customer_data_allowed",
    "customer_data_retention_allowed",
    "customer_output_external_delivery_allowed",
    "public_launch_allowed",
    "legal_or_compliance_ready",
    "source_licensing_assumed",
    "personalized_regulated_advice_allowed",
    "brokerage_or_account_connection_allowed",
    "paper_order_execution_allowed",
    "live_trade_or_account_action_allowed",
    "portfolio_or_canon_mutation_allowed",
    "sql_or_ticker_import_allowed",
    "owner_approval_inferred",
    "config_auth_channel_runtime_mutation_allowed",
]

CONTROL_PLANE_FALSE_KEYS = [
    "finance_canon_source_of_truth",
    "customer_database",
    "portfolio_mutation_authority",
    "owner_approval_authority",
    "trade_or_account_authority",
    "external_delivery_authority",
    "ticker_import_authority",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS service_requests (
            request_id TEXT PRIMARY KEY,
            workflow TEXT NOT NULL,
            service_run_id TEXT NOT NULL,
            scenario TEXT NOT NULL,
            request_type TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            anonymous_service_request INTEGER NOT NULL CHECK (anonymous_service_request IN (0, 1)),
            real_customer_data_present INTEGER NOT NULL CHECK (real_customer_data_present IN (0, 1)),
            external_delivery_allowed INTEGER NOT NULL CHECK (external_delivery_allowed IN (0, 1)),
            authority_boundary_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifact_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL REFERENCES service_requests(request_id) ON DELETE CASCADE,
            artifact_key TEXT NOT NULL,
            path TEXT NOT NULL,
            required INTEGER NOT NULL CHECK (required IN (0, 1)),
            exists_flag INTEGER NOT NULL CHECK (exists_flag IN (0, 1)),
            parseable_json INTEGER NOT NULL CHECK (parseable_json IN (0, 1)),
            status TEXT,
            validation_status TEXT,
            sha256 TEXT,
            updated_at_utc TEXT NOT NULL,
            UNIQUE(request_id, artifact_key)
        );

        CREATE TABLE IF NOT EXISTS queue_items (
            queue_id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL REFERENCES service_requests(request_id) ON DELETE CASCADE,
            service_run_id TEXT NOT NULL,
            workflow TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            owner TEXT NOT NULL,
            next_action TEXT NOT NULL,
            inline_execution_allowed INTEGER NOT NULL CHECK (inline_execution_allowed IN (0, 1)),
            external_delivery_allowed INTEGER NOT NULL CHECK (external_delivery_allowed IN (0, 1)),
            customer_data_use_allowed INTEGER NOT NULL CHECK (customer_data_use_allowed IN (0, 1)),
            claimed_by TEXT,
            claimed_at_utc TEXT,
            claim_count INTEGER NOT NULL DEFAULT 0,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS claim_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            claim_status TEXT NOT NULL,
            claimed_at_utc TEXT NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_at_utc TEXT NOT NULL,
            event_type TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_artifact_refs_request ON artifact_refs(request_id);
        CREATE INDEX IF NOT EXISTS idx_queue_items_status ON queue_items(status, priority);
        CREATE INDEX IF NOT EXISTS idx_events_object ON events(object_type, object_id);
        """
    )


def bool_int(value: Any) -> int:
    return 1 if value is True else 0


def artifact_record(key: str, path: Path, required: bool = True) -> dict[str, Any]:
    payload = load_json_artifact(path)
    record: dict[str, Any] = {
        "artifact_key": key,
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
        "sha256": sha256_file(path),
    }
    if isinstance(payload, dict):
        record["status"] = payload.get("status")
        validation = payload.get("validation")
        if isinstance(validation, dict):
            record["validation_status"] = validation.get("status")
    return record


def current_service_run_path() -> Path:
    state = load(SERVICE_STATE)
    run = as_dict(state.get("current_service_run"))
    service_run_id = run.get("service_run_id")
    if service_run_id:
        return TMP / "wf75-service-runs" / f"{service_run_id}.json"
    return DEFAULT_SERVICE_RUN


def source_artifacts() -> list[dict[str, Any]]:
    service_run = current_service_run_path()
    return [
        artifact_record("service_state", SERVICE_STATE),
        artifact_record("service_run", service_run),
        artifact_record("operator_queue", OPERATOR_QUEUE),
        artifact_record("automation_movement", MOVEMENT),
        artifact_record("wf77_price_freshness_bridge", WF77_BRIDGE),
        artifact_record("wf77_supplemental_price_evidence", WF77_SUPPLEMENTAL),
        artifact_record("renderer_export_regression", RENDERER_REGRESSION),
        artifact_record("scenario_template_library", SCENARIO_LIBRARY),
        artifact_record("readiness_plan", READINESS_PLAN),
        artifact_record("pm_weekly_update", PM_WEEKLY_UPDATE),
        artifact_record("operator_console", OPERATOR_CONSOLE),
    ]


def clear_claim_state(conn: sqlite3.Connection, now: str) -> None:
    conn.execute(
        "UPDATE queue_items SET claimed_by = NULL, claimed_at_utc = NULL, claim_count = 0, updated_at_utc = ?",
        (now,),
    )
    conn.execute("DELETE FROM claim_log")


def upsert_from_artifacts(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
    state = load(SERVICE_STATE)
    run = as_dict(state.get("current_service_run")) or load(current_service_run_path())
    queue = load(OPERATOR_QUEUE)
    queue_item = as_dict(as_list(queue.get("current_queue"))[0] if as_list(queue.get("current_queue")) else {})
    request = as_dict(run.get("request"))
    trust = as_dict(run.get("data_trust_state"))
    request_id = str(request.get("request_id") or "anon-watchlist-ai-infrastructure-v1")
    service_run_id = str(run.get("service_run_id") or request_id)
    authority = {key: False for key in AUTHORITY_FALSE_KEYS}

    conn.execute(
        """
        INSERT INTO service_requests (
            request_id, workflow, service_run_id, scenario, request_type, status, priority,
            anonymous_service_request, real_customer_data_present, external_delivery_allowed,
            authority_boundary_json, created_at_utc, updated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(request_id) DO UPDATE SET
            workflow=excluded.workflow,
            service_run_id=excluded.service_run_id,
            scenario=excluded.scenario,
            request_type=excluded.request_type,
            status=excluded.status,
            priority=excluded.priority,
            anonymous_service_request=excluded.anonymous_service_request,
            real_customer_data_present=excluded.real_customer_data_present,
            external_delivery_allowed=excluded.external_delivery_allowed,
            authority_boundary_json=excluded.authority_boundary_json,
            updated_at_utc=excluded.updated_at_utc
        """,
        (
            request_id,
            "WF75",
            service_run_id,
            str(request.get("scenario") or "anonymous_service_request"),
            str(request.get("request_type") or "watchlist_brief"),
            str(run.get("status") or state.get("status") or "unknown"),
            str(queue_item.get("priority") or "normal"),
            bool_int(request.get("anonymous_service_request")),
            bool_int(trust.get("real_customer_data_present")),
            bool_int(queue_item.get("external_delivery_allowed")),
            json_text(authority),
            now,
            now,
        ),
    )

    artifacts = source_artifacts()
    for artifact in artifacts:
        conn.execute(
            """
            INSERT INTO artifact_refs (
                request_id, artifact_key, path, required, exists_flag, parseable_json,
                status, validation_status, sha256, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(request_id, artifact_key) DO UPDATE SET
                path=excluded.path,
                required=excluded.required,
                exists_flag=excluded.exists_flag,
                parseable_json=excluded.parseable_json,
                status=excluded.status,
                validation_status=excluded.validation_status,
                sha256=excluded.sha256,
                updated_at_utc=excluded.updated_at_utc
            """,
            (
                request_id,
                artifact["artifact_key"],
                artifact["path"],
                bool_int(artifact["required"]),
                bool_int(artifact["exists"]),
                bool_int(artifact["parseable_json"]),
                artifact.get("status"),
                artifact.get("validation_status"),
                artifact.get("sha256"),
                now,
            ),
        )

    queue_id = str(queue_item.get("queue_id") or "wf75-service-state-current")
    conn.execute(
        """
        INSERT INTO queue_items (
            queue_id, request_id, service_run_id, workflow, status, priority, owner, next_action,
            inline_execution_allowed, external_delivery_allowed, customer_data_use_allowed,
            updated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(queue_id) DO UPDATE SET
            request_id=excluded.request_id,
            service_run_id=excluded.service_run_id,
            workflow=excluded.workflow,
            status=excluded.status,
            priority=excluded.priority,
            owner=excluded.owner,
            next_action=excluded.next_action,
            inline_execution_allowed=excluded.inline_execution_allowed,
            external_delivery_allowed=excluded.external_delivery_allowed,
            customer_data_use_allowed=excluded.customer_data_use_allowed,
            updated_at_utc=excluded.updated_at_utc
        """,
        (
            queue_id,
            request_id,
            service_run_id,
            "WF75",
            str(queue_item.get("status") or "handoff_ready"),
            str(queue_item.get("priority") or "normal"),
            str(queue_item.get("owner") or "Veritas main session"),
            str(queue_item.get("next_action") or "Review WF75 service state."),
            bool_int(queue_item.get("inline_execution_allowed")),
            bool_int(queue_item.get("external_delivery_allowed")),
            bool_int(queue_item.get("customer_data_use_allowed")),
            now,
        ),
    )

    conn.execute(
        """
        INSERT INTO events (event_at_utc, event_type, object_type, object_id, details_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            now,
            "control_plane_refresh",
            "service_request",
            request_id,
            json_text({"source": rel(SERVICE_STATE), "artifact_count": len(artifacts), "queue_id": queue_id}),
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value, updated_at_utc) VALUES (?, ?, ?)",
        ("schema", SCHEMA, now),
    )
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value, updated_at_utc) VALUES (?, ?, ?)",
        ("authority", json_text({key: False for key in CONTROL_PLANE_FALSE_KEYS}), now),
    )
    return {"request_id": request_id, "queue_id": queue_id, "artifact_count": len(artifacts)}


def claim_queue_item(db_path: Path, queue_id: str, worker_id: str) -> dict[str, Any]:
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT queue_id, status, claimed_by FROM queue_items WHERE queue_id = ?",
            (queue_id,),
        ).fetchone()
        if row is None:
            result = {"worker_id": worker_id, "queue_id": queue_id, "claim_status": "missing_queue_item"}
        elif row["claimed_by"]:
            result = {
                "worker_id": worker_id,
                "queue_id": queue_id,
                "claim_status": "already_claimed",
                "claimed_by": row["claimed_by"],
            }
        elif row["status"] in {"blocked"}:
            result = {"worker_id": worker_id, "queue_id": queue_id, "claim_status": "blocked_status", "status": row["status"]}
        else:
            conn.execute(
                """
                UPDATE queue_items
                SET claimed_by = ?, claimed_at_utc = ?, claim_count = claim_count + 1, updated_at_utc = ?
                WHERE queue_id = ? AND claimed_by IS NULL
                """,
                (worker_id, now, now, queue_id),
            )
            result = {"worker_id": worker_id, "queue_id": queue_id, "claim_status": "claimed", "claimed_at_utc": now}
        conn.execute(
            """
            INSERT INTO claim_log (queue_id, worker_id, claim_status, claimed_at_utc, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (queue_id, worker_id, result["claim_status"], now, json_text(result)),
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def simulate_claims(db_path: Path, queue_id: str) -> list[dict[str, Any]]:
    return [
        claim_queue_item(db_path, queue_id, "wf75-worker-alpha"),
        claim_queue_item(db_path, queue_id, "wf75-worker-beta"),
    ]


def pragma_state(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "busy_timeout_ms": conn.execute("PRAGMA busy_timeout").fetchone()[0],
        "foreign_keys": conn.execute("PRAGMA foreign_keys").fetchone()[0],
        "synchronous": conn.execute("PRAGMA synchronous").fetchone()[0],
    }


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = ["service_requests", "artifact_refs", "queue_items", "claim_log", "events"]
    return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}


def validate_db(db_path: Path, claim_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not db_path.exists():
        return {"status": "error", "errors": [f"db missing: {rel(db_path)}"], "warnings": warnings}

    conn = connect(db_path)
    try:
        pragmas = pragma_state(conn)
        if str(pragmas.get("journal_mode")).lower() != "wal":
            errors.append(f"journal_mode not WAL: {pragmas.get('journal_mode')}")
        if int(pragmas.get("busy_timeout_ms") or 0) < 5000:
            errors.append("busy_timeout below 5000ms")
        if int(pragmas.get("foreign_keys") or 0) != 1:
            errors.append("foreign_keys pragma not enabled")

        counts = table_counts(conn)
        if counts.get("service_requests", 0) < 1:
            errors.append("service_requests missing rows")
        if counts.get("artifact_refs", 0) < 8:
            errors.append("artifact_refs missing expected proof rows")
        if counts.get("queue_items", 0) < 1:
            errors.append("queue_items missing rows")

        bad_artifacts = [
            dict(row)
            for row in conn.execute(
                "SELECT artifact_key, path, exists_flag, parseable_json FROM artifact_refs WHERE required = 1 AND (exists_flag != 1 OR parseable_json != 1)"
            ).fetchall()
        ]
        if bad_artifacts:
            errors.append(f"required artifacts missing or unparseable: {bad_artifacts}")

        unsafe_service_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT request_id, anonymous_service_request, real_customer_data_present, external_delivery_allowed
                FROM service_requests
                WHERE anonymous_service_request != 1 OR real_customer_data_present != 0 OR external_delivery_allowed != 0
                """
            ).fetchall()
        ]
        if unsafe_service_rows:
            errors.append(f"service request boundary rows unsafe: {unsafe_service_rows}")

        unsafe_queue_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT queue_id, inline_execution_allowed, external_delivery_allowed, customer_data_use_allowed
                FROM queue_items
                WHERE inline_execution_allowed != 0 OR external_delivery_allowed != 0 OR customer_data_use_allowed != 0
                """
            ).fetchall()
        ]
        if unsafe_queue_rows:
            errors.append(f"queue boundary rows unsafe: {unsafe_queue_rows}")

        claim_rows = [dict(row) for row in conn.execute("SELECT worker_id, claim_status FROM claim_log ORDER BY id").fetchall()]
        claimed = [row for row in claim_rows if row.get("claim_status") == "claimed"]
        if claim_results is not None and len(claim_results) >= 2:
            if len(claimed) != 1:
                errors.append(f"claim simulation must have exactly one claimed row: {claim_rows}")
            statuses = [row.get("claim_status") for row in claim_rows]
            if "already_claimed" not in statuses:
                errors.append(f"claim simulation did not prove second-worker exclusion: {claim_rows}")
        elif not claim_rows:
            warnings.append("claim simulation not present in DB")

        return {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
            "pragmas": pragmas,
            "table_counts": counts,
            "claim_rows": claim_rows,
            "db_path": rel(db_path),
        }
    finally:
        conn.close()


def build_summary(db_path: Path, write_result: dict[str, Any] | None, claim_results: list[dict[str, Any]] | None) -> dict[str, Any]:
    validation = validate_db(db_path, claim_results)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": "control_plane_ready" if validation.get("status") == "ok" else "blocked",
        "db_path": rel(db_path),
        "write_result": write_result,
        "claim_simulation": claim_results or [],
        "validation": validation,
        "authority_boundary": {key: False for key in CONTROL_PLANE_FALSE_KEYS},
        "data_boundary": {
            "anonymous_service_requests_only": True,
            "artifact_paths_only": True,
            "real_customer_identity_present": False,
            "real_customer_portfolio_present": False,
            "suitability_or_risk_profile_present": False,
            "brokerage_or_account_data_present": False,
            "credential_data_present": False,
        },
        "next_safe_action": (
            "Use this WAL DB as the local Veritas control plane for WF75 artifact references, "
            "queue status, and worker-claim proof; keep source artifacts as truth surfaces."
        ),
    }


def write_db(db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = utc_now()
    conn = connect(db_path)
    try:
        init_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        write_result = upsert_from_artifacts(conn, now)
        clear_claim_state(conn, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    claim_results = simulate_claims(db_path, write_result["queue_id"])
    return write_result, claim_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF75 SQLite WAL control-plane proof.")
    parser.add_argument("--write", action="store_true", help="Create/update the SQLite WAL DB and summary artifact.")
    parser.add_argument("--validate", action="store_true", help="Validate the SQLite WAL DB and authority boundaries.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY), help="JSON summary output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    summary_out = Path(args.summary_out)
    if not summary_out.is_absolute():
        summary_out = ROOT / summary_out

    write_result: dict[str, Any] | None = None
    claim_results: list[dict[str, Any]] | None = None
    if args.write:
        write_result, claim_results = write_db(db_path)

    summary = build_summary(db_path, write_result, claim_results)
    if args.write:
        atomic_write_json(summary_out, summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.validate and summary.get("status") != "control_plane_ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
