#!/usr/bin/env python3
"""Validate the WF63/WF67 paper-position read-only cron refresh output.

This is a cron-facing proof script only. It inspects the read-only paper
position artifacts after refresh and does not submit, cancel, sell, replace,
liquidate, mutate accounts, or touch live endpoints.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_DIR = TMP / "alpaca-paper-readiness"

DEFAULT_DB = TMP / "wf67-paper-position-state.sqlite"
DEFAULT_PACKET = TMP / "finance-intelligence-state-paper-positions.json"
DEFAULT_EXPORT = OUT_DIR / "current-paper-holdings-readonly.json"
DEFAULT_SNAPSHOT = TMP / "finance-stack-snapshot.json"
DEFAULT_OUTPUT = OUT_DIR / "paper-position-refresh-cron-check.json"

PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
FORBIDDEN_AUTHORITY_COLUMNS = (
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "live_trade_or_account_action_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "account_settings_mutation_allowed",
    "owner_approval_inferred",
    "live_endpoint_detected",
)
FORBIDDEN_PACKET_FLAGS = (
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed_by_this_registry",
    "paper_order_cancel_allowed_by_this_registry",
    "paper_trade_execution_allowed",
    "live_trade_or_account_action_allowed",
    "trade_or_account_action_allowed",
    "owner_approval_inferred",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def check_json_artifact(path: Path, label: str, findings: list[dict[str, Any]], *, require_ok: bool = True) -> Any:
    data = load_json(path)
    if data is None:
        findings.append({"severity": "critical", "code": f"{label}_missing", "path": rel(path)})
        return None
    if not isinstance(data, dict):
        findings.append({"severity": "critical", "code": f"{label}_not_object", "path": rel(path)})
        return data
    status = data.get("status")
    if require_ok and status != "ok":
        findings.append(
            {"severity": "critical", "code": f"{label}_status_not_ok", "path": rel(path), "status": status}
        )
    return data


def check_packet_authority(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    authority = packet.get("authority_boundary")
    if not isinstance(authority, dict):
        findings.append({"severity": "critical", "code": "paper_packet_authority_missing"})
        return
    for key in FORBIDDEN_PACKET_FLAGS:
        if authority.get(key) is True:
            findings.append({"severity": "critical", "code": "forbidden_packet_authority_true", "flag": key})
    endpoint = authority.get("endpoint")
    if endpoint not in (None, PAPER_ENDPOINT):
        findings.append({"severity": "critical", "code": "unexpected_packet_endpoint", "endpoint": endpoint})


def classify_packet_status(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    status = packet.get("status")
    classification = as_dict(packet.get("readiness_classification"))
    planning_state = classification.get("planning_state")
    execution_blocked = classification.get("blocks_paper_execution") is True
    authority_false = as_dict(packet.get("authority_boundary")).get("trade_or_account_action_allowed") is False
    nonblocking_review_state = (
        status == "blocked"
        and planning_state == "usable_with_stale_disclosure"
        and execution_blocked
        and authority_false
    )
    if status == "ok":
        return
    if nonblocking_review_state:
        findings.append(
            {
                "severity": "warning",
                "code": "paper_positions_refresh_blocked_last_known_stale",
                "planning_state": planning_state,
                "refresh_blocker_scope": classification.get("refresh_blocker_scope"),
                "refresh_blocker_codes": as_list(classification.get("refresh_blocker_codes")),
                "paper_execution_state": classification.get("paper_execution_state"),
            }
        )
        return
    findings.append(
        {
            "severity": "critical",
            "code": "paper_positions_packet_status_not_ok",
            "status": status,
            "planning_state": planning_state,
        }
    )


def latest_account_row(con: sqlite3.Connection) -> sqlite3.Row | None:
    con.row_factory = sqlite3.Row
    row = con.execute(
        """
        SELECT *
        FROM paper_account_snapshot
        WHERE status = 'ok'
        ORDER BY generated_at_utc DESC
        LIMIT 1
        """
    ).fetchone()
    return row


def check_sqlite(db_path: Path, findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not db_path.exists():
        findings.append({"severity": "critical", "code": "sqlite_missing", "path": rel(db_path)})
        return {"path": rel(db_path), "exists": False}

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk_rows = con.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok":
            findings.append({"severity": "critical", "code": "sqlite_integrity_failed", "detail": integrity})
        if fk_rows:
            findings.append({"severity": "critical", "code": "sqlite_foreign_key_failed", "rows": len(fk_rows)})

        latest = latest_account_row(con)
        if latest is None:
            findings.append({"severity": "critical", "code": "latest_ok_snapshot_missing"})
            return {
                "path": rel(db_path),
                "exists": True,
                "integrity_check": integrity,
                "foreign_key_rows": len(fk_rows),
                "latest_snapshot": None,
            }

        endpoint = latest["endpoint"]
        method = latest["method"]
        if endpoint != PAPER_ENDPOINT:
            findings.append({"severity": "critical", "code": "unexpected_sqlite_endpoint", "endpoint": endpoint})
        if method != "GET_only":
            findings.append({"severity": "critical", "code": "unexpected_sqlite_method", "method": method})
        for key in FORBIDDEN_AUTHORITY_COLUMNS:
            if int(latest[key] or 0) != 0:
                findings.append({"severity": "critical", "code": "forbidden_sqlite_authority_true", "flag": key})

        freshness = con.execute(
            "SELECT * FROM paper_position_freshness WHERE snapshot_id = ?", (latest["snapshot_id"],)
        ).fetchone()
        if freshness is None:
            findings.append({"severity": "critical", "code": "freshness_row_missing", "snapshot_id": latest["snapshot_id"]})
            freshness_status = None
        else:
            freshness_status = freshness["status"]
            if freshness_status != "fresh":
                findings.append(
                    {
                        "severity": "critical",
                        "code": "freshness_not_fresh",
                        "snapshot_id": latest["snapshot_id"],
                        "freshness_status": freshness_status,
                    }
                )

        position_count = con.execute(
            "SELECT COUNT(*) FROM paper_position_snapshot WHERE snapshot_id = ?", (latest["snapshot_id"],)
        ).fetchone()[0]
        if position_count != int(latest["positions_count"] or 0):
            findings.append(
                {
                    "severity": "warning",
                    "code": "position_count_mismatch",
                    "snapshot_id": latest["snapshot_id"],
                    "account_count": latest["positions_count"],
                    "position_rows": position_count,
                }
            )

        return {
            "path": rel(db_path),
            "exists": True,
            "integrity_check": integrity,
            "foreign_key_rows": len(fk_rows),
            "latest_snapshot": {
                "snapshot_id": latest["snapshot_id"],
                "generated_at_utc": latest["generated_at_utc"],
                "status": latest["status"],
                "endpoint": endpoint,
                "method": method,
                "positions_count": latest["positions_count"],
                "open_orders_count": latest["open_orders_count"],
                "freshness_status": freshness_status,
                "position_rows": position_count,
            },
        }
    finally:
        con.close()


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    packet = check_json_artifact(args.packet, "paper_positions_packet", findings, require_ok=False)
    export = check_json_artifact(args.export, "holdings_export", findings, require_ok=False)
    snapshot = check_json_artifact(args.snapshot, "finance_stack_snapshot", findings)
    sqlite_summary = check_sqlite(args.db, findings)

    if isinstance(packet, dict):
        classify_packet_status(packet, findings)
        freshness = packet.get("freshness")
        if isinstance(freshness, dict) and freshness.get("status") != "fresh":
            classification = as_dict(packet.get("readiness_classification"))
            stale_review_ok = classification.get("planning_state") == "usable_with_stale_disclosure"
            findings.append(
                {
                    "severity": "warning" if stale_review_ok else "critical",
                    "code": "paper_packet_freshness_not_fresh",
                    "freshness_status": freshness.get("status"),
                    "planning_state": classification.get("planning_state"),
                }
            )
        check_packet_authority(packet, findings)
    if isinstance(export, dict):
        if export.get("status") != "ok":
            classification = as_dict(export.get("readiness_classification"))
            stale_review_ok = classification.get("planning_state") == "usable_with_stale_disclosure"
            findings.append(
                {
                    "severity": "warning" if stale_review_ok else "critical",
                    "code": "holdings_export_status_not_ok",
                    "status": export.get("status"),
                    "planning_state": classification.get("planning_state"),
                }
            )
        authority = export.get("authority_boundary")
        if isinstance(authority, dict):
            if authority.get("endpoint") != PAPER_ENDPOINT:
                findings.append(
                    {"severity": "critical", "code": "holdings_export_bad_endpoint", "endpoint": authority.get("endpoint")}
                )
            if authority.get("method") != "GET_only":
                findings.append(
                    {"severity": "critical", "code": "holdings_export_bad_method", "method": authority.get("method")}
                )
    if isinstance(snapshot, dict) and snapshot.get("status") != "ok":
        findings.append({"severity": "warning", "code": "finance_stack_snapshot_not_ok", "status": snapshot.get("status")})

    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    status = "ok" if critical == 0 else "blocked"
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": {
            "review_only": True,
            "paper_position_sql_state_only": True,
            "allowed_methods": ["GET"],
            "endpoint": PAPER_ENDPOINT,
            "paper_order_submit_allowed": False,
            "paper_order_cancel_allowed": False,
            "paper_order_execution_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "account_or_credential_action_allowed": False,
            "money_movement_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
            "cron_schedule_mutation_allowed_by_this_packet": False,
        },
        "sources": {
            "db": rel(args.db),
            "paper_positions_packet": rel(args.packet),
            "holdings_export": rel(args.export),
            "finance_stack_snapshot": rel(args.snapshot),
        },
        "sqlite": sqlite_summary,
        "summary": {
            "critical": critical,
            "warning": warning,
            "findings": len(findings),
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_packet(args)
    if args.write:
        atomic_write_json(args.output, packet)

    print(json.dumps({"status": packet["status"], "output": rel(args.output), "summary": packet["summary"]}, indent=2))
    if args.validate and packet["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
