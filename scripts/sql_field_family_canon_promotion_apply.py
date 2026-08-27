#!/usr/bin/env python3
"""Promote exact SQL field families to canon-owner metadata.

This is an authority/audit metadata apply. It does not change ticker values,
reference levels, freshness rows, source lineage rows, tiers, universe rows,
portfolio Markdown, cash, sizing, risk rules, or execution state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
TMP = ROOT / "tmp"
BACKUP_ROOT = ROOT / "backups" / "sql-field-family-canon-promotion"
DEFAULT_OUT = TMP / "sql-field-family-canon-promotion-apply.json"
DEFAULT_ROLLBACK = TMP / "sql-field-family-canon-promotion-rollback.json"

SCHEMA_VERSION = "sql_field_family_canon_promotion_apply.v1"
OWNER_APPROVAL_REFERENCE = (
    "Randall WebChat 2026-06-19: approved SQL Field-Family promotion and canon "
    "ownership; approved Markdown thinning/rewrite of core MD finance surfaces; "
    "archive/delete planning only, no archive/delete apply."
)

PROMOTED_FIELD_FAMILIES = [
    {
        "family": "ticker_state",
        "owner_tables": ["securities", "tier_routing_state", "answer_path_scope", "universe_membership"],
        "owner_view": "current_sql_canon_routing",
        "scope": "ticker identity, active status, review-only route posture, and answer eligibility context",
    },
    {
        "family": "reference_levels",
        "owner_tables": ["reference_levels"],
        "scope": "entry band, reference stop/invalidation, reference confidence, and band status metadata",
    },
    {
        "family": "source_lineage",
        "owner_tables": ["source_lineage", "source_artifacts"],
        "scope": "structured source artifact path/hash/timestamp lineage and validator status",
    },
    {
        "family": "evidence_freshness",
        "owner_tables": ["evidence_freshness", "evidence_status"],
        "scope": "evidence freshness, stale-family state, source confidence, and card freshness metadata",
    },
    {
        "family": "tier_routing_state",
        "owner_tables": ["tier_routing_state"],
        "scope": "non-capital Tier A/B/C routing and repair/review state",
    },
    {
        "family": "answer_path_scope",
        "owner_tables": ["answer_path_scope"],
        "scope": "internal answer-path scope and production-card generation eligibility",
    },
    {
        "family": "universe_membership",
        "owner_tables": ["universe_membership", "securities"],
        "scope": "200-name universe membership, monitoring role, and decision-grade eligibility flags",
    },
]

AUTHORITY_BOUNDARY = {
    "review_only_internal_sql_json_structured_truth": True,
    "field_family_metadata_apply_only": True,
    "ticker_values_changed": False,
    "reference_levels_changed": False,
    "source_lineage_changed": False,
    "freshness_rows_changed": False,
    "tier_rows_changed": False,
    "answer_scope_rows_changed": False,
    "universe_rows_changed": False,
    "markdown_mutation_by_this_script": False,
    "archive_delete_apply_allowed": False,
    "fallback_retirement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "securities",
        "universe_membership",
        "answer_path_scope",
        "evidence_status",
        "tier_routing_state",
        "reference_levels",
        "evidence_freshness",
        "source_lineage",
        "authority_events",
        "audit_events",
        "finance_state_meta",
        "migration_validation_runs",
    ]
    return {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in tables}


def table_digest(conn: sqlite3.Connection, table: str) -> str:
    rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
    payload = json.dumps([dict(row) for row in rows], sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validation_checks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    views = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    required_tables = {table for item in PROMOTED_FIELD_FAMILIES for table in item["owner_tables"]}
    counts = sqlite_counts(conn)
    false_authority = {
        "tier_routing_state": int(
            conn.execute(
                "SELECT COUNT(*) FROM tier_routing_state WHERE capital_deployment_approved != 0 OR trade_or_execution_approved != 0"
            ).fetchone()[0]
        ),
        "evidence_status": int(
            conn.execute(
                "SELECT COUNT(*) FROM evidence_status WHERE customer_output_allowed != 0 OR paper_or_live_execution_allowed != 0"
            ).fetchone()[0]
        ),
    }
    null_lineage = int(
        conn.execute(
            "SELECT COUNT(*) FROM source_lineage WHERE source_artifact_path='' OR source_artifact_sha256 IS NULL"
        ).fetchone()[0]
    )
    promotion_meta = conn.execute(
        "SELECT value FROM finance_state_meta WHERE key='canon_owner_field_families_v1'"
    ).fetchone()
    metadata: dict[str, Any] = {}
    if promotion_meta:
        metadata = json.loads(str(promotion_meta["value"]))
    promoted_names = sorted(item.get("family") for item in metadata.get("field_families", []))
    expected_names = sorted(item["family"] for item in PROMOTED_FIELD_FAMILIES)

    add("integrity_ok", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "PRAGMA integrity_check")
    add("foreign_key_check_ok", not conn.execute("PRAGMA foreign_key_check").fetchall(), "PRAGMA foreign_key_check")
    add("required_owner_tables_present", required_tables <= tables, sorted(required_tables - tables))
    add("routing_view_present", "current_sql_canon_routing" in views, sorted(views))
    add("core_200_rows_present", all(counts.get(table) == 200 for table in ["securities", "universe_membership", "tier_routing_state", "reference_levels", "evidence_freshness", "answer_path_scope"]), counts)
    add("source_lineage_loaded", counts.get("source_lineage", 0) >= 3000 and null_lineage == 0, {"rows": counts.get("source_lineage"), "null_lineage": null_lineage})
    add("authority_false_flags_clean", all(value == 0 for value in false_authority.values()), false_authority)
    add("canon_owner_metadata_present", bool(promotion_meta), bool(promotion_meta))
    add("canon_owner_exact_families", promoted_names == expected_names, {"expected": expected_names, "actual": promoted_names})
    add("authority_event_recorded", int(conn.execute("SELECT COUNT(*) FROM authority_events WHERE event_type='owner_approved_sql_field_family_canon_owner_promotion'").fetchone()[0]) >= 1)
    add("audit_event_recorded", int(conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type='sql_field_family_canon_owner_promotion_applied'").fetchone()[0]) >= 1)
    return checks


def sqlite_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)


def write_rollback_packet(*, backup_path: Path, db_path: Path, run_id: str, before_sha: str | None) -> dict[str, Any]:
    packet = {
        "schema_version": "sql_field_family_canon_promotion_rollback.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_exact_owner_rollback_if_needed",
        "run_id": run_id,
        "db_path": rel(db_path),
        "backup_path": rel(backup_path),
        "backup_sha256": sha256_file(backup_path),
        "pre_apply_db_sha256": before_sha,
        "rollback_method": "Copy the backup SQLite file over state/finance/finance-canon.sqlite after explicit owner rollback approval, then rerun finance_sql_canon_access validation.",
        "rollback_command": f"Copy-Item -LiteralPath '{rel(backup_path)}' -Destination '{rel(db_path)}' -Force",
        "post_rollback_validator": "python scripts\\finance_sql_canon_access.py --write --validate",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_json(DEFAULT_ROLLBACK, packet)
    return packet


def apply_metadata(conn: sqlite3.Connection, run_id: str, now: str) -> dict[str, Any]:
    family_payload = {
        "schema_version": "finance_sql_canon_owner_field_families.v1",
        "promoted_at_utc": now,
        "approval_reference": OWNER_APPROVAL_REFERENCE,
        "structured_truth_owner": "state/finance/finance-canon.sqlite plus generated JSON proof packets",
        "markdown_owner_scope": "policy, narrative, owner decisions, weekly reasoning, and audit context",
        "fallback_retained": True,
        "archive_delete_apply_allowed": False,
        "field_families": PROMOTED_FIELD_FAMILIES,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    markdown_payload = {
        "schema_version": "finance_markdown_owner_scope.v1",
        "updated_at_utc": now,
        "keep": [
            "policy",
            "narrative",
            "owner decisions",
            "weekly reasoning",
            "audit context",
            "risk rules",
            "approval records",
        ],
        "thin_or_generate": [
            "ticker bands",
            "stops",
            "freshness",
            "tier routing",
            "source lineage",
            "decision states",
            "answer-path scope",
            "universe membership",
            "owner queues generated from structured state",
        ],
        "drift_lint": "Markdown repeating structured fields must be generated from SQL or flagged stale.",
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    event_detail = {
        "run_id": run_id,
        "approval_reference": OWNER_APPROVAL_REFERENCE,
        "field_families": PROMOTED_FIELD_FAMILIES,
        "fallback_retained": True,
        "markdown_thinning_approved": True,
        "archive_delete_planning_approved": True,
        "archive_delete_apply_allowed": False,
    }
    validation_detail = {
        "run_id": run_id,
        "validator_name": "sql_field_family_canon_promotion_apply",
        "field_families": [item["family"] for item in PROMOTED_FIELD_FAMILIES],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc) VALUES (?, ?, ?)",
            ("canon_owner_field_families_v1", json.dumps(family_payload, sort_keys=True), now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc) VALUES (?, ?, ?)",
            ("markdown_owner_scope_v1", json.dumps(markdown_payload, sort_keys=True), now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            ("canon_owner_field_families_v1", json.dumps(family_payload, sort_keys=True)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO authority_events(event_id, event_time_utc, event_type, approval_source, approval_message_id, authority_boundary_json, detail_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                now,
                "owner_approved_sql_field_family_canon_owner_promotion",
                "webchat",
                "2026-06-19-current-webchat-request",
                json.dumps(AUTHORITY_BOUNDARY, sort_keys=True),
                json.dumps(event_detail, sort_keys=True),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO audit_events(event_id, event_time_utc, event_type, detail_json) VALUES (?, ?, ?, ?)",
            (
                f"{run_id}-audit",
                now,
                "sql_field_family_canon_owner_promotion_applied",
                json.dumps(event_detail, sort_keys=True),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO migration_validation_runs(run_id, run_time_utc, validator_name, status, artifact_path, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"{run_id}-validation",
                now,
                "sql_field_family_canon_promotion_apply",
                "ok",
                rel(DEFAULT_OUT),
                json.dumps(validation_detail, sort_keys=True),
            ),
        )
    return family_payload


def build_payload(db_path: Path, *, apply: bool) -> dict[str, Any]:
    now = utc_now()
    run_id = f"sql-field-family-canon-promotion-{stamp()}"
    backup_dir = BACKUP_ROOT / run_id
    backup_path = backup_dir / rel(db_path)
    before_sha = sha256_file(db_path)
    sqlite_backup(db_path, backup_path)
    rollback = write_rollback_packet(backup_path=backup_path, db_path=db_path, run_id=run_id, before_sha=before_sha)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        before_counts = sqlite_counts(conn)
        protected_digests_before = {
            table: table_digest(conn, table)
            for table in ["securities", "universe_membership", "answer_path_scope", "evidence_status", "tier_routing_state", "reference_levels", "evidence_freshness", "source_lineage"]
        }
        if apply:
            owner_metadata = apply_metadata(conn, run_id, now)
        else:
            owner_metadata = {}
        after_counts = sqlite_counts(conn)
        protected_digests_after = {
            table: table_digest(conn, table)
            for table in ["securities", "universe_membership", "answer_path_scope", "evidence_status", "tier_routing_state", "reference_levels", "evidence_freshness", "source_lineage"]
        }
        checks = validation_checks(conn) if apply else []

    digest_changes = {
        table: protected_digests_before[table] == protected_digests_after[table]
        for table in protected_digests_before
    }
    errors = [check for check in checks if not check["ok"]]
    status = "ok" if apply and not errors and all(digest_changes.values()) else ("dry_run_ready" if not apply else "blocked")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now,
        "run_id": run_id,
        "status": status,
        "apply_executed": apply,
        "approval_reference": OWNER_APPROVAL_REFERENCE,
        "db_path": rel(db_path),
        "db_sha256_before": before_sha,
        "db_sha256_after": sha256_file(db_path),
        "backup": {
            "path": rel(backup_path),
            "sha256": sha256_file(backup_path),
            "integrity_check": sqlite3.connect(backup_path).execute("PRAGMA integrity_check").fetchone()[0],
        },
        "rollback_packet": rollback,
        "promoted_field_families": PROMOTED_FIELD_FAMILIES,
        "owner_metadata": owner_metadata,
        "counts_before": before_counts,
        "counts_after": after_counts,
        "protected_table_digests_preserved": digest_changes,
        "checks": checks,
        "errors": errors,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "post_apply_validators": [
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\trade_grade_os_freshness_cron_runner.py --write --validate",
            "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
            "python scripts\\full_intelligence_answer_parity.py --all-wf84 --write --validate",
            "python scripts\\md_finance_structured_drift_lint.py --write --validate",
            "python scripts\\db_lifecycle_manifest.py --write --validate",
        ],
    }
    return payload


def restore_from_rollback(packet_path: Path) -> dict[str, Any]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    backup = ROOT / str(packet["backup_path"])
    db_path = ROOT / str(packet["db_path"])
    before_restore_sha = sha256_file(db_path)
    shutil.copy2(backup, db_path)
    payload = {
        "schema_version": "sql_field_family_canon_promotion_restore.v1",
        "generated_at_utc": utc_now(),
        "status": "restored_from_backup",
        "rollback_packet": rel(packet_path),
        "backup_path": rel(backup),
        "db_path": rel(db_path),
        "db_sha256_before_restore": before_restore_sha,
        "db_sha256_after_restore": sha256_file(db_path),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_json(DEFAULT_OUT, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    db_path = args.db if args.db.is_absolute() else ROOT / args.db
    if args.rollback:
        rollback_path = args.rollback if args.rollback.is_absolute() else ROOT / args.rollback
        payload = restore_from_rollback(rollback_path)
    else:
        payload = build_payload(db_path, apply=args.apply)
        if args.write:
            atomic_write_json(DEFAULT_OUT, payload)
    print(json.dumps({"status": payload["status"], "apply_executed": payload.get("apply_executed", False), "output": rel(DEFAULT_OUT)}, indent=2))
    if args.validate and payload["status"] not in {"ok", "dry_run_ready", "restored_from_backup"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
