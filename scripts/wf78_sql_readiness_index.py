#!/usr/bin/env python3
"""WF78 JSON-first SQLite readiness index.

This builds a report-only readiness/control-plane index for the current WF78
100-ticker state. It reads existing artifacts and databases only. It does not
import, apply, promote, expand SQL-canon authority, mutate canon/portfolio
state, infer owner approval, or authorize paper/live/account/money actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT_JSON = TMP / "wf78-sql-readiness-index.json"
DEFAULT_OUT_DB = TMP / "wf78-sql-readiness-index.sqlite"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
DESIGN_GATE = TMP / "sql-500-ticker-expansion-design-gate.json"
PHASE4_PACKET = TMP / "wf78-phase4-recommendation-packet.json"
CLEANUP_QUEUE = TMP / "wf78-review-monitor-source-open-cleanup-queue.json"

SCHEMA = "veritas.wf78_sql_readiness_index.v1"
EXPECTED_PRODUCTION_TICKERS = 42
SUPPORTED_TOTAL_TICKER_COUNTS = {100, 200, 300, 400, 500}
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "report_only": True,
    "read_existing_artifacts_only": True,
    "import_or_apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_AUTHORITY_FLAGS = {
    "import_or_apply_allowed",
    "promotion_allowed",
    "production_answer_path_change_allowed",
    "sql_canon_expansion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
}

REQUIRED_TRUE_AUTHORITY_FLAGS = {"report_only", "read_existing_artifacts_only"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_meta(path: Path, artifact_type: str, required: bool = True) -> dict[str, Any]:
    payload = load_json_artifact(path) if path.suffix.lower() == ".json" else None
    exists = path.exists()
    stat = path.stat() if exists else None
    generated_at = as_dict(payload).get("generated_at_utc") if isinstance(payload, dict) else None
    return {
        "artifact_type": artifact_type,
        "path": rel(path),
        "exists": exists,
        "required": required,
        "sha256": sha256_file(path) if exists else None,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stat else None,
        "size_bytes": stat.st_size if stat else None,
        "generated_at_utc": generated_at,
        "payload": payload,
    }


def connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect_write(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def required_schema_objects() -> dict[str, set[str]]:
    return {
        "tables": {
            "readiness_index",
            "source_coverage_summary",
            "promotion_recommendation",
            "artifact_provenance",
            "authority_boundary",
            "validation_results",
            "meta",
        }
    }


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS readiness_index;
        DROP TABLE IF EXISTS source_coverage_summary;
        DROP TABLE IF EXISTS promotion_recommendation;
        DROP TABLE IF EXISTS artifact_provenance;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE readiness_index (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT,
            sector TEXT,
            universe_scope TEXT NOT NULL,
            group_status TEXT NOT NULL,
            production_answer_path_member INTEGER NOT NULL CHECK (production_answer_path_member IN (0,1)),
            review_monitor_member INTEGER NOT NULL CHECK (review_monitor_member IN (0,1)),
            card_exists INTEGER NOT NULL CHECK (card_exists IN (0,1)),
            source_open_required INTEGER NOT NULL CHECK (source_open_required IN (0,1)),
            source_open_ready INTEGER NOT NULL CHECK (source_open_ready IN (0,1)),
            promotion_ready INTEGER NOT NULL CHECK (promotion_ready IN (0,1)),
            readiness_status TEXT NOT NULL,
            blocker_reason TEXT,
            missing_family_count INTEGER NOT NULL,
            stale_family_count INTEGER NOT NULL,
            missing_or_stale_count INTEGER NOT NULL,
            blocking_missing_count INTEGER NOT NULL,
            authority_forbidden_true_json TEXT NOT NULL,
            source_artifact_path TEXT,
            source_artifact_sha256 TEXT,
            source_artifact_generated_at_utc TEXT,
            source_artifact_mtime_utc TEXT,
            evidence_contract_json TEXT NOT NULL,
            raw_status_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE source_coverage_summary (
            id INTEGER PRIMARY KEY,
            family_id TEXT NOT NULL,
            status TEXT NOT NULL,
            ticker_count INTEGER NOT NULL,
            missing_count INTEGER NOT NULL,
            stale_count INTEGER NOT NULL,
            source_required_count INTEGER NOT NULL,
            source_paths_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE promotion_recommendation (
            ticker TEXT PRIMARY KEY,
            recommendation_group TEXT NOT NULL,
            rank INTEGER,
            ranking_score REAL,
            phase5_allowed_now INTEGER NOT NULL CHECK (phase5_allowed_now IN (0,1)),
            rationale TEXT,
            required_before_phase5_json TEXT NOT NULL,
            source_artifact_path TEXT NOT NULL,
            source_artifact_sha256 TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE artifact_provenance (
            artifact_key TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            required INTEGER NOT NULL CHECK (required IN (0,1)),
            exists_flag INTEGER NOT NULL CHECK (exists_flag IN (0,1)),
            sha256 TEXT,
            generated_at_utc TEXT,
            mtime_utc TEXT,
            size_bytes INTEGER,
            status TEXT NOT NULL,
            evidence_contract_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE authority_boundary (
            flag_name TEXT PRIMARY KEY,
            flag_value INTEGER NOT NULL CHECK (flag_value IN (0,1)),
            required_value INTEGER NOT NULL CHECK (required_value IN (0,1)),
            status TEXT NOT NULL
        ) STRICT;

        CREATE TABLE validation_results (
            check_name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;
        """
    )


def source_lookup(cleanup: dict[str, Any], phase4: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(cleanup.get("cleanup_queue")):
        item = as_dict(row)
        ticker = str(item.get("ticker", "")).upper()
        if ticker:
            out[ticker] = item
    for row in as_list(cleanup.get("top_source_open_pass")):
        item = as_dict(row)
        ticker = str(item.get("ticker", "")).upper()
        if ticker:
            current = out.setdefault(ticker, {})
            current.update(item)
            current["source_open_ready"] = True
    for group_key, group in [
        ("recommended_pilot", phase4.get("recommended_phase5_pilot")),
        ("second_wave", phase4.get("second_wave_if_pilot_clean")),
        ("defer_for_now", phase4.get("defer_for_now")),
    ]:
        for row in as_list(group):
            item = as_dict(row)
            ticker = str(item.get("ticker", "")).upper()
            if ticker:
                current = out.setdefault(ticker, {})
                current["phase4_recommendation_group"] = item.get("recommendation_group") or group_key
                current["phase4_recommendation"] = item
    return out


def family_counts_by_ticker(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows(
        conn,
        """
        SELECT ticker,
               SUM(CASE WHEN status LIKE 'missing%' THEN 1 ELSE 0 END) AS missing_family_count,
               SUM(CASE WHEN status LIKE '%stale%' THEN 1 ELSE 0 END) AS stale_family_count,
               SUM(missing_count) AS missing_count,
               SUM(stale_count) AS stale_count,
               json_group_array(json_object(
                   'family_id', family_id,
                   'status', status,
                   'missing_count', missing_count,
                   'stale_count', stale_count,
                   'source_required', source_required,
                   'source_paths', source_paths_json
               )) AS family_status_json
          FROM ticker_family_status
         GROUP BY ticker
        """,
    ):
        out[str(row["ticker"]).upper()] = row
    return out


def build_readiness_rows(conn: sqlite3.Connection, artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cleanup = as_dict(artifacts["cleanup_queue"].get("payload"))
    phase4 = as_dict(artifacts["phase4_recommendation"].get("payload"))
    source_rows = source_lookup(cleanup, phase4)
    family_by_ticker = family_counts_by_ticker(conn)
    universe_rows = rows(conn, "SELECT * FROM all_ticker_sql_rows ORDER BY ticker")
    cleanup_meta = artifacts["cleanup_queue"]
    out: list[dict[str, Any]] = []

    for row in universe_rows:
        ticker = str(row["ticker"]).upper()
        source_row = source_rows.get(ticker, {})
        family = family_by_ticker.get(ticker, {})
        production = int_bool(row.get("production_answer_path_member"))
        review = int_bool(row.get("thin_monitor_row") or not production)
        source_open_ready = int_bool(source_row.get("source_open_ready") or source_row.get("promotion_gate_status") == "promotion_review_source_open_ready")
        promotion_ready = int_bool(source_row.get("promotion_ready"))
        blocking_missing = int(source_row.get("blocking_missing_count") or 0)
        missing_or_stale = int(source_row.get("missing_or_stale_count") or 0)
        missing_families = int(family.get("missing_family_count") or 0)
        stale_families = int(family.get("stale_family_count") or 0)
        authority_forbidden = row.get("authority_forbidden_true_json") or "[]"

        if production:
            group_status = "production_answer_path"
            readiness_status = "production_current_report_only"
            blocker = "production answer path remains current 42; this index grants no authority change"
        elif source_open_ready and promotion_ready:
            group_status = "review_monitor_source_open_ready"
            readiness_status = "source_open_ready_owner_gated"
            blocker = "owner approval, backup/rollback, A/B no-regression, consumer diff, and post-apply validation still required"
        else:
            group_status = "review_monitor_blocked_or_repair"
            readiness_status = "blocked_or_repair_required"
            cleanup_required = as_list(source_row.get("cleanup_required"))
            blocker = "; ".join(str(item) for item in cleanup_required) if cleanup_required else "not in current source-open-ready promotion set"

        evidence_contract = {
            "source_artifact_path": cleanup_meta["path"],
            "source_artifact_sha256": cleanup_meta["sha256"],
            "source_artifact_generated_at_utc": cleanup_meta["generated_at_utc"],
            "source_artifact_mtime_utc": cleanup_meta["mtime_utc"],
            "source_open_hits": as_dict(source_row.get("source_open_hits")),
            "cleanup_required": as_list(source_row.get("cleanup_required")),
            "authority_violations": as_list(source_row.get("authority_violations")),
            "source_open_required": bool(row.get("source_open_required")),
            "material_claim_requires_source_open": True,
            "owner_approval_inferred": False,
            "phase5_allowed_now": bool(as_dict(source_row.get("phase4_recommendation")).get("phase5_allowed_now")) if source_row.get("phase4_recommendation") else False,
        }
        out.append(
            {
                "ticker": ticker,
                "name": row.get("name"),
                "tier": row.get("tier"),
                "sector": row.get("sector"),
                "universe_scope": row.get("universe_scope"),
                "group_status": group_status,
                "production_answer_path_member": production,
                "review_monitor_member": review,
                "card_exists": int_bool(row.get("card_exists")),
                "source_open_required": int_bool(row.get("source_open_required")),
                "source_open_ready": source_open_ready,
                "promotion_ready": promotion_ready,
                "readiness_status": readiness_status,
                "blocker_reason": blocker,
                "missing_family_count": missing_families,
                "stale_family_count": stale_families,
                "missing_or_stale_count": missing_or_stale,
                "blocking_missing_count": blocking_missing,
                "authority_forbidden_true_json": authority_forbidden,
                "source_artifact_path": cleanup_meta["path"],
                "source_artifact_sha256": cleanup_meta["sha256"],
                "source_artifact_generated_at_utc": cleanup_meta["generated_at_utc"],
                "source_artifact_mtime_utc": cleanup_meta["mtime_utc"],
                "evidence_contract": evidence_contract,
                "raw_status": source_row,
            }
        )
    return out


def build_source_coverage(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        SELECT family_id,
               status,
               COUNT(*) AS ticker_count,
               SUM(missing_count) AS missing_count,
               SUM(stale_count) AS stale_count,
               SUM(source_required) AS source_required_count,
               json_group_array(source_paths_json) AS source_paths_json
          FROM ticker_family_status
         GROUP BY family_id, status
         ORDER BY family_id, status
        """,
    )


def build_promotion_rows(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    phase4 = as_dict(artifacts["phase4_recommendation"].get("payload"))
    source = artifacts["phase4_recommendation"]
    out: list[dict[str, Any]] = []
    for group_key, group in [
        ("recommended_pilot", phase4.get("recommended_phase5_pilot")),
        ("second_wave", phase4.get("second_wave_if_pilot_clean")),
        ("defer_for_now", phase4.get("defer_for_now")),
    ]:
        for row in as_list(group):
            item = as_dict(row)
            ticker = str(item.get("ticker", "")).upper()
            if not ticker:
                continue
            out.append(
                {
                    "ticker": ticker,
                    "recommendation_group": str(item.get("recommendation_group") or group_key),
                    "rank": item.get("rank"),
                    "ranking_score": item.get("ranking_score"),
                    "phase5_allowed_now": int_bool(item.get("phase5_allowed_now")),
                    "rationale": item.get("rationale"),
                    "required_before_phase5": as_list(item.get("required_before_phase5")),
                    "source_artifact_path": source["path"],
                    "source_artifact_sha256": source["sha256"],
                    "raw": item,
                }
            )
    return out


def summarize(readiness_rows: list[dict[str, Any]], promotion_rows: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    production = sum(1 for row in readiness_rows if row["production_answer_path_member"])
    review = sum(1 for row in readiness_rows if row["review_monitor_member"] and not row["production_answer_path_member"])
    source_open_ready = sum(1 for row in readiness_rows if row["group_status"] == "review_monitor_source_open_ready")
    blocked_or_repair = sum(1 for row in readiness_rows if row["group_status"] == "review_monitor_blocked_or_repair")
    missing_artifacts = [meta["path"] for meta in artifacts.values() if meta["required"] and not meta["exists"]]
    recommended = [row["ticker"] for row in promotion_rows if row["recommendation_group"] == "recommended_pilot"]
    phase4 = as_dict(artifacts["phase4_recommendation"].get("payload"))
    cleanup = as_dict(artifacts["cleanup_queue"].get("payload"))
    design_gate = as_dict(artifacts["design_gate"].get("payload"))
    return {
        "total_tickers": len(readiness_rows),
        "production_answer_path_count": production,
        "review_monitor_count": review,
        "source_open_ready_count": source_open_ready,
        "blocked_or_repair_count": blocked_or_repair,
        "recommended_pilot_tickers": recommended,
        "missing_artifacts": missing_artifacts,
        "source_artifact_counts": {
            "cleanup_top_source_open_pass_count": as_dict(cleanup.get("summary")).get("top_source_open_pass_count"),
            "cleanup_promotion_ready_count": as_dict(cleanup.get("summary")).get("promotion_ready_count"),
            "phase4_blocked_needs_source_repair_count": as_dict(phase4.get("evidence_summary")).get("blocked_needs_source_repair_count"),
            "design_gate_authority_forbidden_rows": as_dict(design_gate.get("current_state")).get("authority_forbidden_rows"),
        },
        "next_safe_action": (
            phase4.get("next_safe_action")
            or design_gate.get("next_safe_action")
            or "Prepare owner-reviewed approval scope and validation proof; do not apply/import/promote from this report."
        ),
    }


def validation_checks(report: dict[str, Any], out_json: Path | None = None, out_db: Path | None = None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    summary = as_dict(report.get("summary"))
    authority = as_dict(report.get("authority_boundary"))
    provenance = as_list(report.get("artifact_provenance"))

    add_check(checks, "required_source_db_exists", STATE_DB.exists(), rel(STATE_DB))
    add_check(checks, "total_ticker_count_supported_scaleout", summary.get("total_tickers") in SUPPORTED_TOTAL_TICKER_COUNTS, {"actual": summary.get("total_tickers"), "supported": sorted(SUPPORTED_TOTAL_TICKER_COUNTS)})
    add_check(checks, "production_answer_path_count_expected", summary.get("production_answer_path_count") == EXPECTED_PRODUCTION_TICKERS, summary.get("production_answer_path_count"))
    add_check(checks, "review_monitor_count_supported_scaleout", summary.get("review_monitor_count") in SUPPORTED_REVIEW_MONITOR_COUNTS, {"actual": summary.get("review_monitor_count"), "supported": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS)})
    add_check(checks, "row_counts_consistent", (summary.get("production_answer_path_count") or 0) + (summary.get("review_monitor_count") or 0) == summary.get("total_tickers"), summary)
    add_check(checks, "required_artifacts_present", not summary.get("missing_artifacts"), summary.get("missing_artifacts"))
    add_check(checks, "authority_true_flags_present", all(authority.get(key) is True for key in REQUIRED_TRUE_AUTHORITY_FLAGS), authority)
    add_check(checks, "authority_false_flags_present", all(authority.get(key) is False for key in REQUIRED_FALSE_AUTHORITY_FLAGS), authority)
    add_check(checks, "authority_flags_complete", REQUIRED_TRUE_AUTHORITY_FLAGS.union(REQUIRED_FALSE_AUTHORITY_FLAGS).issubset(authority), sorted(authority))
    add_check(checks, "recommended_pilot_available", len(as_list(summary.get("recommended_pilot_tickers"))) > 0, summary.get("recommended_pilot_tickers"), severity="warning")
    add_check(checks, "provenance_hashes_present", all((not item.get("exists")) or item.get("sha256") for item in provenance), provenance)

    if out_json is not None:
        ok = False
        detail: Any = rel(out_json)
        try:
            loaded = load_json_artifact(out_json)
            ok = isinstance(loaded, dict) and as_dict(loaded).get("schema") == SCHEMA
            detail = {"path": rel(out_json), "schema": as_dict(loaded).get("schema") if isinstance(loaded, dict) else None}
        except Exception as exc:
            detail = {"path": rel(out_json), "error": str(exc)}
        add_check(checks, "output_json_valid", ok, detail)

    if out_db is not None:
        db_checks: list[dict[str, Any]] = []
        ok = out_db.exists()
        detail: Any = {"path": rel(out_db), "exists": out_db.exists()}
        if ok:
            try:
                with connect_ro(out_db) as conn:
                    integrity = scalar(conn, "PRAGMA integrity_check")
                    objects = {row["name"]: row["type"] for row in conn.execute("SELECT name, type FROM sqlite_master WHERE type='table'")}
                    strict = {row["name"]: row["strict"] for row in conn.execute("SELECT name, strict FROM pragma_table_list WHERE schema='main'")}
                    required = required_schema_objects()["tables"]
                    db_checks = [
                        {"name": "integrity_check", "ok": integrity == "ok", "detail": integrity},
                        {"name": "required_tables", "ok": required.issubset(objects), "detail": sorted(objects)},
                        {"name": "strict_required_tables", "ok": all(strict.get(name) == 1 for name in required), "detail": strict},
                        {"name": "readiness_row_count", "ok": scalar(conn, "SELECT COUNT(*) FROM readiness_index") == summary.get("total_tickers"), "detail": {"actual": scalar(conn, "SELECT COUNT(*) FROM readiness_index"), "expected": summary.get("total_tickers")}},
                        {"name": "authority_boundary_rows", "ok": scalar(conn, "SELECT COUNT(*) FROM authority_boundary") >= len(REQUIRED_FALSE_AUTHORITY_FLAGS) + len(REQUIRED_TRUE_AUTHORITY_FLAGS), "detail": scalar(conn, "SELECT COUNT(*) FROM authority_boundary")},
                    ]
                    ok = all(item["ok"] for item in db_checks)
                    detail = {"path": rel(out_db), "db_checks": db_checks}
            except Exception as exc:
                ok = False
                detail = {"path": rel(out_db), "error": str(exc), "db_checks": db_checks}
        add_check(checks, "output_db_valid", ok, detail)

    return checks


def build_report() -> dict[str, Any]:
    generated_at = utc_now()
    artifacts = {
        "state_db": artifact_meta(STATE_DB, "sqlite_source_state", required=True),
        "design_gate": artifact_meta(DESIGN_GATE, "json_design_gate", required=True),
        "phase4_recommendation": artifact_meta(PHASE4_PACKET, "json_phase4_recommendation", required=True),
        "cleanup_queue": artifact_meta(CLEANUP_QUEUE, "json_source_open_cleanup_queue", required=True),
    }

    readiness_rows: list[dict[str, Any]] = []
    source_coverage: list[dict[str, Any]] = []
    if STATE_DB.exists():
        with connect_ro(STATE_DB) as conn:
            readiness_rows = build_readiness_rows(conn, artifacts)
            source_coverage = build_source_coverage(conn)
    promotion_rows = build_promotion_rows(artifacts)
    summary = summarize(readiness_rows, promotion_rows, artifacts)

    report = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "workflow": "WF78",
        "artifact_type": "sql_readiness_index_report_only",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "readiness_index": readiness_rows,
        "source_coverage_summary": source_coverage,
        "promotion_recommendation": promotion_rows,
        "artifact_provenance": [
            {key: value for key, value in meta.items() if key != "payload"}
            for meta in artifacts.values()
        ],
    }
    checks = validation_checks(report)
    report["validation"] = {
        "status": "ok" if all(check["ok"] for check in checks if check["severity"] == "critical") else "fail_closed",
        "checks": checks,
    }
    report["summary"]["validation_result"] = report["validation"]["status"]
    return report


def write_db(path: Path, report: dict[str, Any]) -> None:
    with connect_write(path) as conn:
        init_schema(conn)
        with conn:
            conn.executemany(
                """
                INSERT INTO readiness_index (
                    ticker, name, tier, sector, universe_scope, group_status,
                    production_answer_path_member, review_monitor_member, card_exists,
                    source_open_required, source_open_ready, promotion_ready, readiness_status,
                    blocker_reason, missing_family_count, stale_family_count,
                    missing_or_stale_count, blocking_missing_count, authority_forbidden_true_json,
                    source_artifact_path, source_artifact_sha256, source_artifact_generated_at_utc,
                    source_artifact_mtime_utc, evidence_contract_json, raw_status_json
                ) VALUES (
                    :ticker, :name, :tier, :sector, :universe_scope, :group_status,
                    :production_answer_path_member, :review_monitor_member, :card_exists,
                    :source_open_required, :source_open_ready, :promotion_ready, :readiness_status,
                    :blocker_reason, :missing_family_count, :stale_family_count,
                    :missing_or_stale_count, :blocking_missing_count, :authority_forbidden_true_json,
                    :source_artifact_path, :source_artifact_sha256, :source_artifact_generated_at_utc,
                    :source_artifact_mtime_utc, :evidence_contract_json, :raw_status_json
                )
                """,
                [
                    {
                        **row,
                        "evidence_contract_json": json_text(row["evidence_contract"]),
                        "raw_status_json": json_text(row["raw_status"]),
                    }
                    for row in as_list(report.get("readiness_index"))
                ],
            )
            conn.executemany(
                """
                INSERT INTO source_coverage_summary (
                    family_id, status, ticker_count, missing_count, stale_count,
                    source_required_count, source_paths_json
                ) VALUES (
                    :family_id, :status, :ticker_count, :missing_count, :stale_count,
                    :source_required_count, :source_paths_json
                )
                """,
                as_list(report.get("source_coverage_summary")),
            )
            conn.executemany(
                """
                INSERT INTO promotion_recommendation (
                    ticker, recommendation_group, rank, ranking_score, phase5_allowed_now,
                    rationale, required_before_phase5_json, source_artifact_path,
                    source_artifact_sha256, raw_json
                ) VALUES (
                    :ticker, :recommendation_group, :rank, :ranking_score, :phase5_allowed_now,
                    :rationale, :required_before_phase5_json, :source_artifact_path,
                    :source_artifact_sha256, :raw_json
                )
                """,
                [
                    {
                        **row,
                        "required_before_phase5_json": json_text(row["required_before_phase5"]),
                        "raw_json": json_text(row["raw"]),
                    }
                    for row in as_list(report.get("promotion_recommendation"))
                ],
            )
            conn.executemany(
                """
                INSERT INTO artifact_provenance (
                    artifact_key, path, required, exists_flag, sha256, generated_at_utc,
                    mtime_utc, size_bytes, status, evidence_contract_json
                ) VALUES (
                    :artifact_key, :path, :required, :exists_flag, :sha256, :generated_at_utc,
                    :mtime_utc, :size_bytes, :status, :evidence_contract_json
                )
                """,
                [
                    {
                        "artifact_key": item["artifact_type"],
                        "path": item["path"],
                        "required": int_bool(item["required"]),
                        "exists_flag": int_bool(item["exists"]),
                        "sha256": item.get("sha256"),
                        "generated_at_utc": item.get("generated_at_utc"),
                        "mtime_utc": item.get("mtime_utc"),
                        "size_bytes": item.get("size_bytes"),
                        "status": "ok" if item.get("exists") else "missing",
                        "evidence_contract_json": json_text(item),
                    }
                    for item in as_list(report.get("artifact_provenance"))
                ],
            )
            conn.executemany(
                """
                INSERT INTO authority_boundary (flag_name, flag_value, required_value, status)
                VALUES (:flag_name, :flag_value, :required_value, :status)
                """,
                [
                    {
                        "flag_name": key,
                        "flag_value": int_bool(value),
                        "required_value": 1 if key in REQUIRED_TRUE_AUTHORITY_FLAGS else 0,
                        "status": "ok" if ((key in REQUIRED_TRUE_AUTHORITY_FLAGS and value is True) or (key in REQUIRED_FALSE_AUTHORITY_FLAGS and value is False)) else "fail",
                    }
                    for key, value in sorted(as_dict(report.get("authority_boundary")).items())
                ],
            )
            conn.executemany(
                """
                INSERT INTO validation_results (check_name, status, severity, detail_json)
                VALUES (:check_name, :status, :severity, :detail_json)
                """,
                [
                    {
                        "check_name": check["name"],
                        "status": check["status"],
                        "severity": check["severity"],
                        "detail_json": json_text(check.get("detail")),
                    }
                    for check in as_list(as_dict(report.get("validation")).get("checks"))
                ],
            )
            for key, value in {
                "schema": report["schema"],
                "generated_at_utc": report["generated_at_utc"],
                "workflow": report["workflow"],
                "summary": json_text(report["summary"]),
                "authority_boundary": json_text(report["authority_boundary"]),
            }.items():
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (key, value))
        conn.execute("PRAGMA optimize")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF78 SQL readiness index.")
    parser.add_argument("--write", action="store_true", help="Write JSON and SQLite outputs.")
    parser.add_argument("--validate", action="store_true", help="Validate inputs and outputs; exits fail-closed on critical failures.")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON, help="JSON output path.")
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB, help="SQLite output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    out_json = args.out_json if args.out_json.is_absolute() else ROOT / args.out_json
    out_db = args.out_db if args.out_db.is_absolute() else ROOT / args.out_db

    report = build_report()

    if args.write:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_db.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out_json, report)
        write_db(out_db, report)

    if args.validate:
        checks = validation_checks(report, out_json if args.write else None, out_db if args.write else None)
        report["validation"] = {
            "status": "ok" if all(check["ok"] for check in checks if check["severity"] == "critical") else "fail_closed",
            "checks": checks,
        }
        report["summary"]["validation_result"] = report["validation"]["status"]
        if args.write:
            atomic_write_json(out_json, report)
            write_db(out_db, report)

    if not args.write:
        print(json.dumps({"summary": report["summary"], "validation": report["validation"]}, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": report["validation"]["status"],
                    "out_json": rel(out_json),
                    "out_db": rel(out_db),
                    "summary": report["summary"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0 if report["validation"]["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
