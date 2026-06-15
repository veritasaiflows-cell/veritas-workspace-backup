#!/usr/bin/env python3
"""WF63/WF67 GET-only Alpaca paper-position SQL refresh.

This script reads Alpaca paper account, positions, and orders using GET only,
writes a review-only paper-position SQLite state slice, and exports compatibility
JSON/Markdown files. It never submits, cancels, replaces, closes, liquidates, or
mutates account state.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json

TMP = ROOT / "tmp"
OUT_DIR = TMP / "alpaca-paper-readiness"
DEFAULT_DB = TMP / "wf67-paper-position-state.sqlite"
DEFAULT_PACKET = TMP / "finance-intelligence-state-paper-positions.json"
DEFAULT_EXPORT = OUT_DIR / "current-paper-holdings-readonly.json"
DEFAULT_EXPORT_MD = OUT_DIR / "current-paper-holdings-readonly.md"
DEFAULT_KILL_SWITCH = OUT_DIR / "read-only-position-refresh-kill-switch.json"
DEFAULT_AUDIT_LOG = OUT_DIR / "audit-log.jsonl"

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://" + "api.alpaca.markets"
KEY_ENV = "ALPACA_PAPER_API_KEY_ID"
SECRET_ENV = "ALPACA_PAPER_API_SECRET_KEY"
ALLOWED_METHODS = ["GET"]
BLOCKED_METHODS = ["POST", "PATCH", "PUT", "DELETE"]
MAX_KILL_SWITCH_MINUTES = 180
SCHEMA_VERSION = 1

AMBIGUOUS_OR_LIVE_NAMES = {
    "ALPACA_API_KEY_ID",
    "ALPACA_SECRET_KEY",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "ALPACA_LIVE_API_KEY_ID",
    "ALPACA_LIVE_API_SECRET_KEY",
    "APCA_LIVE_API_KEY_ID",
    "APCA_LIVE_API_SECRET_KEY",
}


class BlockedRun(Exception):
    """Expected fail-closed block for unsafe or unavailable refreshes."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def authority_boundary() -> dict[str, Any]:
    return {
        "review_only": True,
        "get_only_refresh": True,
        "account_mode": "paper",
        "endpoint": PAPER_BASE_URL,
        "allowed_methods": ALLOWED_METHODS,
        "blocked_methods": BLOCKED_METHODS,
        "paper_submit_allowed": False,
        "paper_cancel_allowed": False,
        "paper_sell_allowed": False,
        "live_endpoint_allowed": False,
        "live_trade_or_account_action_allowed": False,
        "trade_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "account_settings_mutation_allowed": False,
        "owner_approval_inferred": False,
        "promotion_to_live_allowed": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "sizing_cash_or_risk_rule_mutation_allowed": False,
        "database_path_migration_performed": False,
        "artifact_index_is_state_owner": False,
        "canon_cache_used_for_paper_positions": False,
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


def connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS current_paper_positions;

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS paper_account_snapshot (
            snapshot_id TEXT PRIMARY KEY,
            generated_at_utc TEXT NOT NULL,
            account_mode TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            status TEXT NOT NULL,
            equity REAL,
            cash REAL,
            buying_power REAL,
            portfolio_value REAL,
            positions_count INTEGER NOT NULL,
            orders_count INTEGER NOT NULL,
            open_orders_count INTEGER NOT NULL,
            live_endpoint_detected INTEGER NOT NULL,
            secrets_redacted INTEGER NOT NULL,
            raw_response_bodies_persisted INTEGER NOT NULL,
            paper_submit_allowed INTEGER NOT NULL,
            paper_cancel_allowed INTEGER NOT NULL,
            live_trade_or_account_action_allowed INTEGER NOT NULL,
            trade_or_account_action_allowed INTEGER NOT NULL,
            money_movement_allowed INTEGER NOT NULL,
            account_settings_mutation_allowed INTEGER NOT NULL,
            owner_approval_inferred INTEGER NOT NULL,
            validation_findings_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS paper_position_snapshot (
            snapshot_id TEXT NOT NULL REFERENCES paper_account_snapshot(snapshot_id) ON DELETE CASCADE,
            symbol TEXT NOT NULL,
            quantity REAL,
            side TEXT,
            market_value REAL,
            average_entry_price REAL,
            current_price REAL,
            unrealized_pl REAL,
            unrealized_pl_percent REAL,
            change_today REAL,
            source TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (snapshot_id, symbol)
        ) STRICT;

        CREATE TABLE IF NOT EXISTS paper_position_freshness (
            snapshot_id TEXT PRIMARY KEY REFERENCES paper_account_snapshot(snapshot_id) ON DELETE CASCADE,
            generated_at_utc TEXT NOT NULL,
            age_seconds INTEGER NOT NULL,
            stale_threshold_seconds INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('fresh', 'stale', 'missing', 'blocked')),
            validation_findings_json TEXT NOT NULL,
            authority_boundary_json TEXT NOT NULL
        ) STRICT;

        CREATE VIEW current_paper_positions AS
            SELECT p.*
            FROM paper_position_snapshot p
            JOIN (
                SELECT snapshot_id
                FROM paper_account_snapshot
                WHERE status = 'ok'
                ORDER BY generated_at_utc DESC
                LIMIT 1
            ) latest ON latest.snapshot_id = p.snapshot_id
            ORDER BY p.symbol;

        CREATE INDEX IF NOT EXISTS idx_paper_account_generated ON paper_account_snapshot(generated_at_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_paper_account_status_generated ON paper_account_snapshot(status, generated_at_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_paper_position_symbol ON paper_position_snapshot(symbol);
        CREATE INDEX IF NOT EXISTS idx_paper_freshness_status ON paper_position_freshness(status);
        """
    )


def append_audit(event: dict[str, Any], audit_log: Path) -> None:
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with audit_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def audit_event(action: str, result: str, reason_code: str, artifact_paths: list[str]) -> dict[str, Any]:
    return {
        "timestamp_utc": utc_now(),
        "workflow": "WF63/WF67 paper position read-only refresh",
        "event_id": f"wf67-pos-{uuid.uuid4().hex[:12]}",
        "actor": "script",
        "action": action,
        "method_class": "GET" if action.startswith("read_") else "LOCAL_WRITE",
        "endpoint_mode": "paper",
        "request_intent": "paper_position_sql_refresh",
        "result": result,
        "reason_code": reason_code,
        "artifact_paths": artifact_paths,
        "redaction_status": "redacted",
        "secret_material_present": False,
        "trade_or_account_action_allowed": False,
    }


def ensure_kill_switch(path: Path, *, create: bool, expires_minutes: int, approval_note: str) -> dict[str, Any]:
    if expires_minutes < 1 or expires_minutes > MAX_KILL_SWITCH_MINUTES:
        raise BlockedRun("kill_switch_ttl_out_of_bounds")
    if create:
        payload = {
            "schema_version": 1,
            "workflow": "WF63/WF67 paper position read-only refresh",
            "generated_at_utc": utc_now(),
            "alpaca_access_enabled": True,
            "read_only_enabled": True,
            "paper_submit_enabled": False,
            "paper_cancel_enabled": False,
            "live_submit_enabled": False,
            "endpoint": PAPER_BASE_URL,
            "allowed_methods": ALLOWED_METHODS,
            "expires_at_utc": (datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "approval_source": "standing_read_only_policy",
            "owner_reference": "WF63/WF67 GET-only paper account/position visibility; no per-run trade approval implied.",
            "approval_note": approval_note,
            "trade_or_account_action_allowed": False,
        }
        atomic_write_json(path, payload)
        return payload
    if not path.exists():
        raise BlockedRun("kill_switch_absent")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise BlockedRun(f"kill_switch_unreadable:{type(exc).__name__}") from exc


def validate_kill_switch(payload: dict[str, Any]) -> str:
    checks = {
        "alpaca_access_enabled": payload.get("alpaca_access_enabled") is True,
        "read_only_enabled": payload.get("read_only_enabled") is True,
        "paper_submit_enabled_false": payload.get("paper_submit_enabled") is False,
        "paper_cancel_enabled_false": payload.get("paper_cancel_enabled") is False,
        "live_submit_enabled_false": payload.get("live_submit_enabled") is False,
        "endpoint_exact_paper": payload.get("endpoint") == PAPER_BASE_URL,
        "methods_get_only": payload.get("allowed_methods") == ALLOWED_METHODS,
        "trade_or_account_action_allowed_false": payload.get("trade_or_account_action_allowed") is False,
    }
    expires = payload.get("expires_at_utc")
    checks["expiration_present"] = isinstance(expires, str)
    checks["not_expired"] = isinstance(expires, str) and parse_utc(expires) > datetime.now(timezone.utc)
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BlockedRun("kill_switch_invalid:" + ",".join(failed))
    return "ok"


def credential_status() -> tuple[bool, list[str]]:
    selected_present = bool(os.environ.get(KEY_ENV)) and bool(os.environ.get(SECRET_ENV))
    ambiguous = sorted(name for name in AMBIGUOUS_OR_LIVE_NAMES if os.environ.get(name))
    return selected_present, ambiguous


def get_json(session: requests.Session, path: str, *, params: dict[str, Any] | None = None, timeout: int) -> tuple[Any, int]:
    url = PAPER_BASE_URL + path
    if not url.startswith(PAPER_BASE_URL) or url.startswith(LIVE_BASE_URL):
        raise BlockedRun("endpoint_not_exact_paper")
    try:
        response = session.get(url, params=params or {}, timeout=timeout)
    except requests.RequestException as exc:
        raise BlockedRun(f"get_failed:{path}:{type(exc).__name__}") from exc
    if not (200 <= response.status_code < 300):
        raise BlockedRun(f"get_failed:{path}:http_{response.status_code}")
    try:
        return response.json(), response.status_code
    except ValueError as exc:
        raise BlockedRun(f"json_decode_failed:{path}") from exc


def summarize_orders(orders: Any) -> dict[str, int]:
    items = orders if isinstance(orders, list) else []
    open_statuses = {"new", "accepted", "pending_new", "partially_filled", "held", "pending_replace", "accepted_for_bidding"}
    return {
        "orders_count": len(items),
        "open_orders_count": sum(1 for item in items if isinstance(item, dict) and str(item.get("status") or "").lower() in open_statuses),
    }


def blocked_payload(reason: str, db_path: Path, stale_threshold_seconds: int) -> dict[str, Any]:
    generated_at = utc_now()
    snapshot_id = f"blocked-{generated_at.replace(':', '').replace('-', '')}"
    findings = [{"severity": "critical", "code": reason}]
    write_db(
        db_path=db_path,
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        status="blocked",
        account={},
        positions=[],
        orders_summary={"orders_count": 0, "open_orders_count": 0},
        freshness_status="blocked",
        stale_threshold_seconds=stale_threshold_seconds,
        findings=findings,
    )
    return packet_from_db(db_path)


def latest_known_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    latest_ok = conn.execute(
        """
        SELECT *
        FROM paper_account_snapshot
        WHERE status = 'ok'
        ORDER BY generated_at_utc DESC
        LIMIT 1
        """
    ).fetchone()
    if not latest_ok:
        return {"snapshot_id": None, "positions_count": 0, "orders_count": 0, "open_orders_count": 0}
    return {
        "snapshot_id": latest_ok["snapshot_id"],
        "positions_count": int(latest_ok["positions_count"] or 0),
        "orders_count": int(latest_ok["orders_count"] or 0),
        "open_orders_count": int(latest_ok["open_orders_count"] or 0),
    }


def write_db(
    *,
    db_path: Path,
    snapshot_id: str,
    generated_at: str,
    status: str,
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    orders_summary: dict[str, int],
    freshness_status: str,
    stale_threshold_seconds: int,
    findings: list[dict[str, Any]],
) -> None:
    with connect(db_path) as conn:
        init_schema(conn)
        known = latest_known_summary(conn)
        positions_count = len(positions) if status == "ok" else int(known["positions_count"] or 0)
        orders_count = int(orders_summary.get("orders_count") or 0) if status == "ok" else int(known["orders_count"] or 0)
        open_orders_count = int(orders_summary.get("open_orders_count") or 0) if status == "ok" else int(known["open_orders_count"] or 0)
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("generated_at_utc", generated_at))
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("authority_boundary", json_text(authority_boundary())))
        conn.execute(
            """
            INSERT INTO paper_account_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                generated_at,
                "paper",
                PAPER_BASE_URL,
                "GET_only",
                status,
                as_float(account.get("equity")),
                as_float(account.get("cash")),
                as_float(account.get("buying_power")),
                as_float(account.get("portfolio_value")),
                positions_count,
                orders_count,
                open_orders_count,
                0,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                json_text(findings),
            ),
        )
        for item in positions:
            symbol = str(item.get("symbol") or "").upper()
            if not symbol:
                continue
            conn.execute(
                """
                INSERT INTO paper_position_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    snapshot_id,
                    symbol,
                    as_float(item.get("qty")),
                    item.get("side"),
                    as_float(item.get("market_value")),
                    as_float(item.get("avg_entry_price")),
                    as_float(item.get("current_price")),
                    as_float(item.get("unrealized_pl")),
                    as_float(item.get("unrealized_plpc")),
                    as_float(item.get("change_today")),
                    "alpaca_paper_get_only",
                    json_text({
                        "symbol": symbol,
                        "qty": item.get("qty"),
                        "side": item.get("side"),
                        "market_value": item.get("market_value"),
                        "avg_entry_price": item.get("avg_entry_price"),
                        "current_price": item.get("current_price"),
                        "unrealized_pl": item.get("unrealized_pl"),
                        "unrealized_plpc": item.get("unrealized_plpc"),
                        "change_today": item.get("change_today"),
                    }),
                ),
            )
        conn.execute(
            "INSERT INTO paper_position_freshness VALUES (?,?,?,?,?,?,?)",
            (
                snapshot_id,
                generated_at,
                0,
                stale_threshold_seconds,
                freshness_status,
                json_text(findings),
                json_text(authority_boundary()),
            ),
        )
        conn.execute("PRAGMA optimize")


def validate_db(db_path: Path) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        integrity = scalar(conn, "PRAGMA integrity_check")
        fk_rows = rows(conn, "PRAGMA foreign_key_check")
        account_rows = scalar(conn, "SELECT COUNT(*) FROM paper_account_snapshot")
        ok_account_rows = scalar(conn, "SELECT COUNT(*) FROM paper_account_snapshot WHERE status='ok'")
        freshness_rows = scalar(conn, "SELECT COUNT(*) FROM paper_position_freshness")
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
        latest = rows(
            conn,
            """
            SELECT a.*, f.status AS freshness_status, f.stale_threshold_seconds
            FROM paper_account_snapshot a
            JOIN paper_position_freshness f ON f.snapshot_id = a.snapshot_id
            ORDER BY a.generated_at_utc DESC
            LIMIT 1
            """,
        )
    checks = [
        {"name": "integrity_check_ok", "ok": integrity == "ok", "detail": integrity, "severity": "error"},
        {"name": "foreign_key_check_ok", "ok": len(fk_rows) == 0, "detail": {"rows": len(fk_rows)}, "severity": "error"},
        {"name": "account_snapshot_present", "ok": account_rows >= 1, "detail": {"rows": account_rows}, "severity": "error"},
        {"name": "freshness_row_present", "ok": freshness_rows >= 1, "detail": {"rows": freshness_rows}, "severity": "error"},
        {"name": "ok_snapshot_available_for_current_positions", "ok": ok_account_rows >= 1 or (latest and latest[0].get("status") == "blocked"), "detail": {"rows": ok_account_rows}, "severity": "warning"},
        {"name": "forbidden_authority_flags_false", "ok": forbidden_rows == 0, "detail": {"rows": forbidden_rows}, "severity": "error"},
        {"name": "latest_snapshot_fresh", "ok": bool(latest) and latest[0].get("freshness_status") == "fresh", "detail": latest[0] if latest else None, "severity": "warning"},
    ]
    status = "ok" if not [c for c in checks if not c["ok"] and c["severity"] == "error"] else "blocked"
    return {"status": status, "checks": checks}


def packet_from_db(db_path: Path) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
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
        positions = rows(conn, "SELECT * FROM current_paper_positions")
        validation = validate_db(db_path)
    latest = latest_rows[0] if latest_rows else {}
    latest_ok = latest_ok_rows[0] if latest_ok_rows else {}
    summary = latest_ok if latest.get("status") == "blocked" and latest_ok else latest
    last_known_positions_status = "current" if latest.get("status") == "ok" else ("stale_but_known" if latest_ok else "unavailable")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": "finance_intelligence_state_paper_positions",
        "status": "ok" if validation["status"] == "ok" and latest.get("status") == "ok" else latest.get("status", validation["status"]),
        "db_path": rel(db_path),
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
            "status": latest.get("status", validation["status"]),
            "generated_at_utc": latest.get("generated_at_utc"),
            "validation_findings": json.loads(latest.get("validation_findings_json") or "[]") if latest.get("validation_findings_json") else [],
        },
        "account_summary": {
            "account_mode": summary.get("account_mode"),
            "endpoint": summary.get("endpoint"),
            "method": summary.get("method"),
            "equity": summary.get("equity"),
            "cash": summary.get("cash"),
            "buying_power": summary.get("buying_power"),
            "portfolio_value": summary.get("portfolio_value"),
            "positions_count": summary.get("positions_count", len(positions)),
            "orders_count": summary.get("orders_count"),
            "open_orders_count": summary.get("open_orders_count"),
            "last_successful_snapshot_id": latest_ok.get("snapshot_id"),
            "last_successful_snapshot_at_utc": latest_ok.get("generated_at_utc"),
        },
        "positions": positions,
        "validation": validation,
        "authority_boundary": authority_boundary(),
        "answer_contract": {
            "sql_is_paper_position_current_state_only": True,
            "json_markdown_exports_are_compatibility_outputs_not_truth_owner": True,
            "must_disclose_stale_missing_or_blocked_freshness": True,
            "no_paper_submit_cancel_sell_authority_from_refresh": True,
            "no_live_trade_or_account_authority": True,
            "no_owner_approval_inference": True,
        },
    }
    packet["readiness_classification"] = classify_readiness(packet)
    atomic_write_json(DEFAULT_PACKET, packet)
    return packet


def finding_codes(findings: Any) -> list[str]:
    return [
        str(item.get("code"))
        for item in findings
        if isinstance(item, dict) and item.get("code")
    ]


def seconds_since_utc(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = parse_utc(value)
    except (TypeError, ValueError):
        return None
    return int(max(0, (datetime.now(timezone.utc) - dt).total_seconds()))


def classify_readiness(packet: dict[str, Any]) -> dict[str, Any]:
    freshness = packet.get("freshness") if isinstance(packet.get("freshness"), dict) else {}
    latest_refresh = packet.get("latest_refresh") if isinstance(packet.get("latest_refresh"), dict) else {}
    account = packet.get("account_summary") if isinstance(packet.get("account_summary"), dict) else {}
    positions = packet.get("positions") if isinstance(packet.get("positions"), list) else []
    codes = finding_codes(latest_refresh.get("validation_findings"))
    status = str(packet.get("status") or "").lower()
    freshness_status = str(freshness.get("status") or "").lower()
    latest_success_at = freshness.get("latest_successful_snapshot_at_utc")
    last_known_status = str(freshness.get("last_known_positions_status") or "")
    has_last_known_positions = bool(positions) and bool(latest_success_at)
    stale_but_known = status == "blocked" and last_known_status == "stale_but_known" and has_last_known_positions
    fresh = status == "ok" and freshness_status == "fresh"
    refresh_kill_switch_blocked = any(
        code == "kill_switch_absent"
        or code.startswith("kill_switch_invalid:")
        or code.startswith("kill_switch_unreadable:")
        or code == "kill_switch_ttl_out_of_bounds"
        for code in codes
    )

    if fresh:
        visibility_state = "fresh"
        planning_state = "fresh_positions_available"
        refresh_scope = "none"
        operator_action = "NO_REPLY"
        blocks_research = False
    elif stale_but_known:
        visibility_state = "stale_but_known"
        planning_state = "usable_with_stale_disclosure"
        refresh_scope = "read_only_refresh_only" if refresh_kill_switch_blocked else "paper_position_visibility_refresh"
        operator_action = "MAIN_SESSION_REVIEW_NON_URGENT"
        blocks_research = False
    else:
        visibility_state = "blocked_unavailable" if status == "blocked" else "unknown"
        planning_state = "blocked_no_current_position_visibility"
        refresh_scope = "paper_position_visibility"
        operator_action = "MAIN_HANDOFF_REQUIRED"
        blocks_research = True

    return {
        "paper_position_visibility_state": visibility_state,
        "planning_state": planning_state,
        "refresh_blocker_scope": refresh_scope,
        "refresh_blocker_codes": codes,
        "latest_successful_snapshot_at_utc": latest_success_at,
        "latest_successful_snapshot_age_seconds": seconds_since_utc(latest_success_at),
        "positions_count": len(positions),
        "open_orders_count": account.get("open_orders_count"),
        "blocks_research_shadow_or_planning": blocks_research,
        "blocks_paper_execution": True,
        "paper_execution_state": (
            "blocked_until_fresh_positions_exact_owner_approval_clean_wf67_guard_and_execution_kill_switch"
        ),
        "blocks_live_execution": True,
        "live_execution_state": "blocked_always_no_live_authority",
        "owner_approval_inferred": False,
        "paper_or_live_execution_allowed": False,
        "operator_action": operator_action,
        "notes": [
            "Read-only position visibility is not paper order approval.",
            "Stale-but-known positions may support review only when disclosed.",
            "Any paper submit/cancel/sell still requires exact owner approval, fresh WF67 guard proof, and execution kill switch.",
        ],
    }


def export_compatibility_files(packet: dict[str, Any], json_path: Path, md_path: Path) -> None:
    summary = packet.get("account_summary") if isinstance(packet.get("account_summary"), dict) else {}
    positions = packet.get("positions") if isinstance(packet.get("positions"), list) else []
    export = {
        "schema_version": 2,
        "generated_at_utc": packet.get("freshness", {}).get("generated_at_utc") or packet.get("generated_at_utc"),
        "status": packet.get("status"),
        "freshness": packet.get("freshness"),
        "account_mode": "paper",
        "endpoint": PAPER_BASE_URL,
        "method": "GET_only",
        "trade_or_account_action_allowed": False,
        "paper_submit_allowed": False,
        "paper_cancel_allowed": False,
        "live_endpoint_detected": False,
        "secrets_redacted": True,
        "sql_state_owner": rel(DEFAULT_DB),
        "summary": {
            "equity": summary.get("equity"),
            "cash": summary.get("cash"),
            "buying_power": summary.get("buying_power"),
            "portfolio_value": summary.get("portfolio_value"),
            "positions_count": summary.get("positions_count"),
            "orders_count": summary.get("orders_count"),
            "open_orders_count": summary.get("open_orders_count"),
        },
        "readiness_classification": packet.get("readiness_classification"),
        "positions": [
            {
                "symbol": row.get("symbol"),
                "qty": row.get("quantity"),
                "side": row.get("side"),
                "market_value": row.get("market_value"),
                "avg_entry_price": row.get("average_entry_price"),
                "current_price": row.get("current_price"),
                "unrealized_pl": row.get("unrealized_pl"),
                "unrealized_plpc": row.get("unrealized_pl_percent"),
                "change_today": row.get("change_today"),
            }
            for row in positions
        ],
    }
    atomic_write_json(json_path, export)

    lines = [
        "# Alpaca Paper Current Holdings - Read Only",
        "",
        f"- Generated UTC: `{export['generated_at_utc']}`",
        f"- Freshness: `{export['freshness'].get('status') if isinstance(export.get('freshness'), dict) else 'missing'}`",
        "- Endpoint: paper only / GET only",
        "- Boundary: no submit/cancel/sell, no live endpoint, no account mutation, no secrets persisted",
        f"- SQL state owner: `{export['sql_state_owner']}`",
        "",
        f"- Equity: `{summary.get('equity')}`",
        f"- Cash: `{summary.get('cash')}`",
        f"- Buying power: `{summary.get('buying_power')}`",
        f"- Portfolio value: `{summary.get('portfolio_value')}`",
        f"- Positions: `{summary.get('positions_count')}`",
        f"- Recent orders observed: `{summary.get('orders_count')}`",
        f"- Open orders observed: `{summary.get('open_orders_count')}`",
        "",
        "| Symbol | Qty | Side | Market value | Avg entry | Current | Unrealized P/L | Unrealized % | Today % |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in export["positions"]:
        lines.append(
            f"| {row.get('symbol')} | {row.get('qty')} | {row.get('side')} | {row.get('market_value')} | "
            f"{row.get('avg_entry_price')} | {row.get('current_price')} | {row.get('unrealized_pl')} | "
            f"{row.get('unrealized_plpc')} | {row.get('change_today')} |"
        )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db)
    artifact_paths = [rel(db_path), rel(DEFAULT_PACKET), rel(Path(args.export_json)), rel(Path(args.export_md))]
    try:
        kill_switch = ensure_kill_switch(
            Path(args.kill_switch),
            create=args.create_kill_switch,
            expires_minutes=args.expires_minutes,
            approval_note=args.approval_note,
        )
        validate_kill_switch(kill_switch)
        selected_present, ambiguous = credential_status()
        if ambiguous:
            raise BlockedRun("ambiguous_or_live_credential_names_present")
        if not selected_present:
            raise BlockedRun("paper_credentials_absent")

        session = requests.Session()
        session.headers.update({
            "APCA-API-KEY-ID": os.environ[KEY_ENV],
            "APCA-API-SECRET-KEY": os.environ[SECRET_ENV],
            "Accept": "application/json",
        })
        account, _ = get_json(session, "/v2/account", timeout=args.timeout_seconds)
        append_audit(audit_event("read_account_metadata", "observed", "ok", artifact_paths), Path(args.audit_log))
        positions_raw, _ = get_json(session, "/v2/positions", timeout=args.timeout_seconds)
        append_audit(audit_event("read_positions", "observed", "ok", artifact_paths), Path(args.audit_log))
        orders_raw, _ = get_json(session, "/v2/orders", params={"status": "all", "limit": 50, "direction": "desc"}, timeout=args.timeout_seconds)
        append_audit(audit_event("read_orders", "observed", "ok", artifact_paths), Path(args.audit_log))

        if not isinstance(account, dict):
            raise BlockedRun("account_payload_not_object")
        if not isinstance(positions_raw, list):
            raise BlockedRun("positions_payload_not_list")
        orders_summary = summarize_orders(orders_raw)
        generated_at = utc_now()
        snapshot_id = f"wf67-paper-pos-{generated_at.replace(':', '').replace('-', '')}"
        write_db(
            db_path=db_path,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            status="ok",
            account=account,
            positions=[row for row in positions_raw if isinstance(row, dict)],
            orders_summary=orders_summary,
            freshness_status="fresh",
            stale_threshold_seconds=args.stale_threshold_seconds,
            findings=[],
        )
        packet = packet_from_db(db_path)
        export_compatibility_files(packet, Path(args.export_json), Path(args.export_md))
        append_audit(audit_event("write_paper_position_sql_state", "allowed", "refresh_ok", artifact_paths), Path(args.audit_log))
        return packet
    except BlockedRun as exc:
        packet = blocked_payload(str(exc), db_path, args.stale_threshold_seconds)
        export_compatibility_files(packet, Path(args.export_json), Path(args.export_md))
        append_audit(audit_event("block_paper_position_sql_refresh", "blocked", str(exc), artifact_paths), Path(args.audit_log))
        return packet


def validate_command(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        packet = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "artifact_type": "finance_intelligence_state_paper_positions",
            "status": "missing",
            "db_path": rel(db_path),
            "freshness": {"status": "missing"},
            "positions": [],
            "authority_boundary": authority_boundary(),
        }
        atomic_write_json(DEFAULT_PACKET, packet)
        return packet
    packet = packet_from_db(db_path)
    export_compatibility_files(packet, DEFAULT_EXPORT, DEFAULT_EXPORT_MD)
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    refresh_parser = sub.add_parser("refresh", help="Run GET-only Alpaca paper account/position/order refresh and write SQL/export state.")
    refresh_parser.add_argument("--db", default=str(DEFAULT_DB))
    refresh_parser.add_argument("--kill-switch", default=str(DEFAULT_KILL_SWITCH))
    refresh_parser.add_argument("--create-kill-switch", action="store_true")
    refresh_parser.add_argument("--expires-minutes", type=int, default=90)
    refresh_parser.add_argument("--approval-note", default="Standing WF63/WF67 read-only Alpaca paper account/position refresh approved as GET-only review/proof state; no submit/cancel/sell/live/account mutation authority.")
    refresh_parser.add_argument("--timeout-seconds", type=int, default=15)
    refresh_parser.add_argument("--stale-threshold-seconds", type=int, default=28800)
    refresh_parser.add_argument("--export-json", default=str(DEFAULT_EXPORT))
    refresh_parser.add_argument("--export-md", default=str(DEFAULT_EXPORT_MD))
    refresh_parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG))
    refresh_parser.add_argument("--pretty", action="store_true")

    validate_parser = sub.add_parser("validate", help="Validate existing paper-position SQL state and write compact packet/export artifacts.")
    validate_parser.add_argument("--db", default=str(DEFAULT_DB))
    validate_parser.add_argument("--pretty", action="store_true")

    args = parser.parse_args()
    if args.command == "refresh":
        result = refresh(args)
    else:
        result = validate_command(Path(args.db))
    print(json.dumps(result, indent=2 if getattr(args, "pretty", False) else None, sort_keys=True))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
