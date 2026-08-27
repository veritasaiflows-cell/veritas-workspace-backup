#!/usr/bin/env python3
"""Build a read-only finance cache cleanup readiness packet.

This packet inventories finance cache databases and large proof JSON surfaces so
cleanup can be planned without moving, deleting, or mutating anything.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-cache-cleanup-readiness.json"

SCHEMA = "veritas.finance_cache_cleanup_readiness.v1"

DB_TARGETS = [
    ("sql_canon_primary", ROOT / "state" / "finance" / "finance-canon.sqlite", "primary_guarded_sql_truth"),
    ("legacy_canon_cache", TMP / "veritas-canon-cache.sqlite", "legacy_compatibility_proof_cache"),
    ("finance_intelligence_state", TMP / "finance-intelligence-state.sqlite", "compatibility_query_cache"),
    ("wf84_canonical_data_plane", TMP / "canonical-finance-data-plane.sqlite", "wf84_current_query_cache"),
]

JSON_TARGETS = [
    ("finance_cache_frontdoor", TMP / "finance-cache-frontdoor.json", "chat_cache_frontdoor"),
    ("cache_dependency_manifest", TMP / "cache-dependency-manifest.json", "cache_dependency_guard"),
    ("json_first_activation_preflight", TMP / "artifact-index-json-first-default-validation.json", "old_activation_preflight_residue"),
    ("trade_grade_full_answer_rollup", TMP / "trade-grade-full-answer-assembler.json", "wf85_answer_rollup"),
    ("trade_grade_source_freshness_gate", TMP / "trade-grade-source-freshness-gate.json", "source_open_freshness_gate"),
    ("trade_grade_os_freshness_runner", TMP / "trade-grade-os-freshness-cron-runner.json", "cron_owned_os_freshness_proof"),
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cleanup_readiness_only": True,
    "sqlite_read_only_checks": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cache_database_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = tuple(
    key for key in AUTHORITY_BOUNDARY
    if key.endswith("_allowed") or key.endswith("_inferred")
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def file_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "present": False, "size_bytes": 0}
    stat = path.stat()
    return {
        "path": rel(path),
        "present": True,
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def sqlite_check(name: str, path: Path, role: str) -> dict[str, Any]:
    meta = file_meta(path)
    result = {
        "id": name,
        "role": role,
        **meta,
        "cleanup_classification": cleanup_classification(role),
        "integrity_check": None,
        "foreign_key_violation_count": None,
        "table_count": None,
        "row_count_sample": {},
        "errors": [],
    }
    if not path.exists():
        result["errors"].append("sqlite_missing")
        return result
    try:
        conn = connect_ro(path)
        try:
            result["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
            result["foreign_key_violation_count"] = len(fk_rows)
            tables = [
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            ]
            result["table_count"] = len(tables)
            sample: dict[str, int | str] = {}
            for table in tables[:12]:
                try:
                    sample[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                except sqlite3.Error as exc:
                    sample[table] = f"count_error:{exc}"
            result["row_count_sample"] = sample
        finally:
            conn.close()
    except sqlite3.Error as exc:
        result["errors"].append(f"sqlite_read_failed:{exc}")
    return result


def cleanup_classification(role: str) -> str:
    if role == "primary_guarded_sql_truth":
        return "not_cleanup_candidate_primary_truth"
    if role == "wf84_current_query_cache":
        return "retain_current_query_cache"
    if role in {"legacy_compatibility_proof_cache", "compatibility_query_cache"}:
        return "compatibility_lineage_owner_gated_cleanup_candidate"
    return "review_required"


def json_artifact_record(name: str, path: Path, role: str) -> dict[str, Any]:
    meta = file_meta(path)
    payload = as_dict(load_json_artifact(path)) if path.exists() else {}
    classification = "normal_proof_surface"
    if role == "old_activation_preflight_residue":
        classification = "classified_old_activation_preflight_residue"
    elif int(meta.get("size_bytes") or 0) > 1_000_000:
        classification = "large_json_prompt_pressure_candidate"
    return {
        "id": name,
        "role": role,
        **meta,
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "classification": classification,
        "delete_allowed_now": False,
        "requires_owner_packet_for_delete_or_archive": True,
    }


def build_packet() -> dict[str, Any]:
    dbs = [sqlite_check(name, path, role) for name, path, role in DB_TARGETS]
    artifacts = [json_artifact_record(name, path, role) for name, path, role in JSON_TARGETS]
    db_errors = [
        f"{db['id']}:{error}"
        for db in dbs
        for error in db.get("errors", [])
        if db["id"] != "legacy_canon_cache" or error != "sqlite_missing"
    ]
    cleanup_candidates = [
        db for db in dbs
        if db.get("cleanup_classification") == "compatibility_lineage_owner_gated_cleanup_candidate"
    ]
    large_json = [item for item in artifacts if item.get("classification") == "large_json_prompt_pressure_candidate"]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not db_errors else "blocked",
        "purpose": "Read-only cache cleanup readiness inventory for SQL-first finance intelligence.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sqlite_caches": dbs,
        "json_proof_surfaces": artifacts,
        "summary": {
            "sqlite_cache_count": len(dbs),
            "sqlite_error_count": len(db_errors),
            "compatibility_lineage_cleanup_candidate_count": len(cleanup_candidates),
            "large_json_prompt_pressure_candidate_count": len(large_json),
            "current_truth_db": "state/finance/finance-canon.sqlite",
            "current_chat_facade": "tmp/finance-cache-frontdoor.json",
            "phase2_requires_owner_approval": True,
            "next_safe_action": "Use this packet to prepare owner-gated cleanup; do not delete, archive, move, or mutate cache DBs from phase 1.",
        },
        "validation": {"status": "ok" if not db_errors else "blocked", "errors": db_errors, "warnings": []},
    }
    return packet


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors = list(as_dict(packet.get("validation")).get("errors") or [])
    boundary = as_dict(packet.get("authority_boundary"))
    for key in FALSE_AUTHORITY_KEYS:
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")
    if boundary.get("sqlite_read_only_checks") is not True:
        errors.append("sqlite_read_only_checks_not_true")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, packet)
    errors = validate_packet(packet) if args.validate else []
    print(json.dumps({"status": packet["status"], "out": rel(out), "summary": packet["summary"], "validation_errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
