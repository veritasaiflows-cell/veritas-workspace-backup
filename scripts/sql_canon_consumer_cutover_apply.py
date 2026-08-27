#!/usr/bin/env python3
"""Apply exact consumer cutover-state updates to finance-canon SQLite.

This is a narrow registry maintenance tool. It does not migrate a consumer by
itself, retire fallbacks, archive files, change answer behavior, or grant any
finance authority. It only records a validated consumer cutover state after the
separate proof artifacts already exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, backup_sqlite_database


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DEFAULT_OUT = ROOT / "tmp" / "sql-canon-consumer-cutover-apply.json"
DEFAULT_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"
BACKUP_DIR = ROOT / "backups" / "finance-sql-canon-migration"

ALLOWED_STATES = {
    "not_cut_over",
    "sql_shadow_validated",
    "sql_primary_guarded",
    "blocked",
    "source_producer",
}
AUTHORITY_BOUNDARY = {
    "registry_update_only": True,
    "consumer_behavior_change_by_this_tool": False,
    "fallback_retirement_allowed": False,
    "archive_delete_apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backup_db(source: Path, timestamp: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_ts = timestamp.replace(":", "").replace("-", "").replace("Z", "Z")
    backup = BACKUP_DIR / f"finance-canon-consumer-cutover-{safe_ts}.sqlite"
    return backup_sqlite_database(source, backup)


def parse_consumers(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        for item in value.split(","):
            item = item.strip().replace("\\", "/")
            if item:
                out.append(item)
    return sorted(set(out))


def consumers_from_backlog_lane(backlog_path: Path, lane: str) -> list[str]:
    resolved = backlog_path if backlog_path.is_absolute() else ROOT / backlog_path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    lanes = payload.get("recommended_parallel_lanes") or []
    for row in lanes:
        if isinstance(row, dict) and row.get("lane") == lane:
            return sorted({str(path).replace("\\", "/") for path in row.get("paths", []) if path})
    return []


def consumers_from_registry(db_path: Path, *, lane: str = "", state: str = "") -> list[str]:
    clauses: list[str] = []
    params: list[str] = []
    if lane:
        clauses.append("migration_lane=?")
        params.append(lane)
    if state:
        clauses.append("cutover_state=?")
        params.append(state)
    if not clauses:
        return []
    query = "SELECT consumer_path FROM consumer_migration_registry WHERE " + " AND ".join(clauses)
    with connect(db_path) as conn:
        return sorted(str(row["consumer_path"]).replace("\\", "/") for row in conn.execute(query, params))


def load_proof_rows(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        if not resolved.exists():
            errors.append(f"proof_missing:{rel(resolved)}")
        rows.append({
            "path": rel(resolved),
            "exists": resolved.exists(),
            "sha256": sha256_file(resolved),
        })
    return rows, errors


def read_registry_rows(conn: sqlite3.Connection, consumers: list[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for consumer in consumers:
        row = conn.execute(
            "SELECT * FROM consumer_migration_registry WHERE consumer_path=?",
            (consumer,),
        ).fetchone()
        if row:
            rows[consumer] = dict(row)
    return rows


def registry_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "priority_counts": {
            str(row["priority"]): int(row["count"])
            for row in conn.execute("SELECT priority, COUNT(*) AS count FROM consumer_migration_registry GROUP BY priority")
        },
        "cutover_state_counts": {
            str(row["cutover_state"]): int(row["count"])
            for row in conn.execute("SELECT cutover_state, COUNT(*) AS count FROM consumer_migration_registry GROUP BY cutover_state")
        },
    }


def build_payload(
    db_path: Path,
    consumers: list[str],
    state: str,
    proof_paths: list[Path],
    *,
    apply: bool,
) -> dict[str, Any]:
    timestamp = utc_now()
    critical: list[str] = []
    warnings: list[str] = []
    proof_rows, proof_errors = load_proof_rows(proof_paths)
    critical.extend(proof_errors)
    if state not in ALLOWED_STATES:
        critical.append(f"unsupported_state:{state}")
    if not consumers:
        critical.append("no_consumers_requested")
    if not db_path.exists():
        critical.append(f"db_missing:{rel(db_path)}")
        return {
            "schema": "veritas.sql_canon_consumer_cutover_apply.v1",
            "generated_at_utc": timestamp,
            "status": "blocked",
            "db_path": rel(db_path),
            "requested_state": state,
            "consumers": consumers,
            "proof_artifacts": proof_rows,
            "validation": {"status": "blocked", "critical_errors": critical, "warnings": warnings},
            "authority_boundary": AUTHORITY_BOUNDARY,
        }

    backup_path: Path | None = None
    before_rows: dict[str, dict[str, Any]] = {}
    after_rows: dict[str, dict[str, Any]] = {}
    summary_before: dict[str, Any] = {}
    summary_after: dict[str, Any] = {}
    run_id = f"sql-canon-consumer-cutover-{timestamp}"

    with connect(db_path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok":
            critical.append(f"integrity_check:{integrity}")
        if fk_issues:
            critical.append(f"foreign_key_issues:{len(fk_issues)}")
        before_rows = read_registry_rows(conn, consumers)
        missing = sorted(set(consumers) - set(before_rows))
        if missing:
            critical.append("unregistered_consumers:" + ",".join(missing))
        summary_before = registry_summary(conn)

    if apply and not critical:
        backup_path = backup_db(db_path, timestamp)
        with connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            for consumer in consumers:
                if state == "source_producer":
                    conn.execute(
                        """
                        UPDATE consumer_migration_registry
                        SET cutover_state=?
                        WHERE consumer_path=?
                        """,
                        (state, consumer),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE consumer_migration_registry
                        SET cutover_state=?, raw_sql_needs_review=0
                        WHERE consumer_path=?
                        """,
                        (state, consumer),
                    )
            detail = {
                "consumers": consumers,
                "state": state,
                "proof_artifacts": proof_rows,
                "backup_path": rel(backup_path),
                "authority_boundary": AUTHORITY_BOUNDARY,
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO migration_validation_runs
                    (run_id, run_time_utc, validator_name, status, artifact_path, detail_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    timestamp,
                    "sql_canon_consumer_cutover_apply",
                    "ok",
                    rel(DEFAULT_OUT),
                    json.dumps(detail, sort_keys=True),
                ),
            )
            conn.commit()

    with connect(db_path) as conn:
        after_rows = read_registry_rows(conn, consumers)
        summary_after = registry_summary(conn)
        integrity_after = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_after = conn.execute("PRAGMA foreign_key_check").fetchall()
    if integrity_after != "ok":
        critical.append(f"post_integrity_check:{integrity_after}")
    if fk_after:
        critical.append(f"post_foreign_key_issues:{len(fk_after)}")
    if apply and not critical:
        not_updated = [consumer for consumer, row in after_rows.items() if row.get("cutover_state") != state]
        if not_updated:
            critical.append("consumers_not_updated:" + ",".join(not_updated))
    if not apply and not critical:
        warnings.append("dry_run_only_no_db_change")

    status = "ok" if not critical else "blocked"
    return {
        "schema": "veritas.sql_canon_consumer_cutover_apply.v1",
        "generated_at_utc": timestamp,
        "status": status,
        "db_path": rel(db_path),
        "apply_requested": apply,
        "requested_state": state,
        "consumers": consumers,
        "backup_path": rel(backup_path) if backup_path else None,
        "proof_artifacts": proof_rows,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "registry_summary_before": summary_before,
        "registry_summary_after": summary_after,
        "migration_validation_run_id": run_id if apply and status == "ok" else None,
        "validation": {"status": status, "critical_errors": critical, "warnings": warnings},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Registry update only; this does not change answer output by itself.",
            "Fallbacks remain required unless a separate lifecycle gate retires them.",
            "No capital, execution, brokerage/account, customer, external delivery, archive, delete, or portfolio/canon mutation authority.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--consumer", action="append", default=[], help="Consumer path; repeat or comma-separate.")
    parser.add_argument("--consumer-from-backlog-lane", default="")
    parser.add_argument("--consumer-from-registry-lane", default="")
    parser.add_argument("--consumer-from-registry-state", default="", choices=sorted(ALLOWED_STATES | {""}))
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--state", default="sql_primary_guarded", choices=sorted(ALLOWED_STATES))
    parser.add_argument("--proof", action="append", type=Path, default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    consumers = parse_consumers(args.consumer)
    if args.consumer_from_backlog_lane:
        backlog = args.backlog if args.backlog.is_absolute() else ROOT / args.backlog
        consumers.extend(consumers_from_backlog_lane(backlog, args.consumer_from_backlog_lane))
    if args.consumer_from_registry_lane or args.consumer_from_registry_state:
        consumers.extend(
            consumers_from_registry(
                db,
                lane=args.consumer_from_registry_lane,
                state=args.consumer_from_registry_state,
            )
        )
    payload = build_payload(
        db,
        sorted(set(consumers)),
        args.state,
        args.proof,
        apply=args.apply,
    )
    if args.write:
        atomic_write_json(DEFAULT_OUT, payload)
    print(json.dumps({
        "status": payload["status"],
        "apply_requested": payload["apply_requested"],
        "consumers": payload["consumers"],
        "requested_state": payload["requested_state"],
        "backup_path": payload["backup_path"],
        "validation": payload["validation"],
        "written": [rel(DEFAULT_OUT)] if args.write else [],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
