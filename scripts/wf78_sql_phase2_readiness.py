#!/usr/bin/env python3
"""WF78 broad SQL/index hardening and Phase 2 readiness gate.

This validates the existing generated SQLite/index surfaces in place. It does
not move, promote, consolidate, or expand authority for any tmp database.

Use `wf78_sql_readiness_index.py` for the per-ticker WF78 readiness/control
plane index. This script remains the broad surface/readiness gate used by Go
parity, runtime scorecards, and SQL helper contract checks.
"""
from __future__ import annotations

import argparse
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
from wf78_legacy_42_tier_state import production_entries as legacy_42_tier_entries

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

ARTIFACT_INDEX_DB = TMP / "veritas-artifact-index.sqlite"
WORKSPACE_INDEX_DB = TMP / "workspace-index.sqlite"
CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
FINANCE_STACK_DB = TMP / "finance-stack-snapshot.sqlite"
FINANCE_INTELLIGENCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
UNIVERSE_VALIDATION_PATH = TMP / "wf78-finance-universe-validation.json"
ROUTER_QA_PATH = TMP / "finance-intelligence-router-qa-sql-canon-archive-apply.json"
TICKER_CARDS_DIR = TMP / "ticker-intelligence-cards"

SCHEMA_VERSION = 1
SUPPORTED_ACTIVE_UNIVERSE_TICKERS = {100, 200, 300, 400, 500}
EXPECTED_PRODUCTION_TICKERS = 42
SUPPORTED_REVIEW_MONITOR_TICKERS = {58, 158, 258, 358, 458}
EXPECTED_CANON_CACHE_ROWS = 265
FORBIDDEN_TRUE_AUTHORITY_FLAGS = {
    "trade_execution_allowed",
    "live_trade_or_account_action_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "generated_report_is_canonical",
    "paper_trade_submit_cancel_allowed_by_today_card",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
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


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def sqlite_surface(path: Path, required_tables: set[str], required_views: set[str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "checks": checks,
    }
    add_check(checks, "db_exists", path.exists(), rel(path))
    if not path.exists():
        report["status"] = "blocked"
        return report

    with connect_readonly(path) as conn:
        integrity = scalar(conn, "PRAGMA integrity_check")
        fk_rows = rows(conn, "PRAGMA foreign_key_check")
        objects = {
            row["name"]: row["type"]
            for row in conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
        }
        report.update(
            {
                "integrity_check": integrity,
                "foreign_key_check_rows": fk_rows,
                "tables": sorted(name for name, typ in objects.items() if typ == "table"),
                "views": sorted(name for name, typ in objects.items() if typ == "view"),
            }
        )
        add_check(checks, "integrity_check_ok", integrity == "ok", integrity)
        add_check(checks, "foreign_key_check_ok", len(fk_rows) == 0, {"rows": len(fk_rows)})
        add_check(checks, "required_tables_present", required_tables.issubset(objects), sorted(required_tables.intersection(objects)))
        add_check(checks, "required_views_present", required_views.issubset(objects), sorted(required_views.intersection(objects)))
    report["status"] = "ok" if all(check["ok"] for check in checks) else "blocked"
    return report


def audit_artifact_index() -> dict[str, Any]:
    report = sqlite_surface(
        ARTIFACT_INDEX_DB,
        required_tables={"artifact_runs", "artifact_file_state", "source_freshness_rows", "deployment_readiness_rows", "authority_flags"},
        required_views={"v_cockpit_deployment_readiness", "v_cockpit_trust_boundary", "v_cockpit_source_freshness"},
    )
    if not report.get("exists"):
        return report
    with connect_readonly(ARTIFACT_INDEX_DB) as conn:
        report["row_counts"] = {
            "artifact_runs": scalar(conn, "SELECT COUNT(*) FROM artifact_runs"),
            "artifact_file_state": scalar(conn, "SELECT COUNT(*) FROM artifact_file_state"),
            "deployment_readiness_rows": scalar(conn, "SELECT COUNT(*) FROM deployment_readiness_rows"),
            "source_freshness_rows": scalar(conn, "SELECT COUNT(*) FROM source_freshness_rows"),
        }
        placeholders = ",".join("?" for _ in FORBIDDEN_TRUE_AUTHORITY_FLAGS)
        forbidden_authority = scalar(
            conn,
            f"SELECT COUNT(*) FROM authority_flags WHERE flag_value != 0 AND flag_name IN ({placeholders})",
            tuple(sorted(FORBIDDEN_TRUE_AUTHORITY_FLAGS)),
        )
        add_check(report["checks"], "forbidden_authority_flags_false", forbidden_authority == 0, {"rows": forbidden_authority})
    report["status"] = "ok" if all(check["ok"] for check in report["checks"]) else "blocked"
    return report


def audit_workspace_index() -> dict[str, Any]:
    report = sqlite_surface(
        WORKSPACE_INDEX_DB,
        required_tables={"runs", "documents", "headings", "links", "aliases", "owners", "freshness", "artifacts", "artifact_metadata", "documents_fts"},
        required_views=set(),
    )
    if not report.get("exists"):
        return report
    with connect_readonly(WORKSPACE_INDEX_DB) as conn:
        report["row_counts"] = {
            "documents": scalar(conn, "SELECT COUNT(*) FROM documents"),
            "artifacts": scalar(conn, "SELECT COUNT(*) FROM artifacts"),
            "headings": scalar(conn, "SELECT COUNT(*) FROM headings"),
            "links": scalar(conn, "SELECT COUNT(*) FROM links"),
        }
        wf78_hits = scalar(conn, "SELECT COUNT(*) FROM documents WHERE path LIKE '%Workflow 78%'")
        universe_hits = scalar(conn, "SELECT COUNT(*) FROM artifacts WHERE path='data/finance/universe-v1.json'")
        add_check(report["checks"], "wf78_continuity_indexed", bool(wf78_hits), {"rows": wf78_hits})
        add_check(report["checks"], "wf78_universe_registry_indexed", bool(universe_hits), {"rows": universe_hits})
    report["status"] = "ok" if all(check["ok"] for check in report["checks"]) else "blocked"
    return report


def audit_canon_cache() -> dict[str, Any]:
    report = sqlite_surface(
        CANON_CACHE_DB,
        required_tables={"canon_cache_meta", "canon_cache_fields", "canon_cache_change_ledger"},
        required_views=set(),
    )
    if not report.get("exists"):
        return report
    with connect_readonly(CANON_CACHE_DB) as conn:
        field_rows = scalar(conn, "SELECT COUNT(*) FROM canon_cache_fields")
        distinct_scopes = scalar(conn, "SELECT COUNT(DISTINCT scope) FROM canon_cache_fields")
        dirty_rows = scalar(
            conn,
            "SELECT COUNT(*) FROM canon_cache_fields WHERE reconciliation_status!='match' OR validator_status!='ok'",
        )
        authority_rows = scalar(
            conn,
            "SELECT COUNT(*) FROM canon_cache_fields WHERE authority_boundary NOT LIKE '%metadata%'",
        )
        strict_tables = {
            row["name"]: row["strict"]
            for row in conn.execute(
                "SELECT name, strict FROM pragma_table_list WHERE name IN ('canon_cache_meta','canon_cache_fields','canon_cache_change_ledger')"
            )
        }
        report["row_counts"] = {
            "canon_cache_fields": field_rows,
            "distinct_scopes": distinct_scopes,
            "canon_cache_change_ledger": scalar(conn, "SELECT COUNT(*) FROM canon_cache_change_ledger"),
        }
        report["field_counts"] = rows(
            conn,
            "SELECT field_name, COUNT(*) AS row_count FROM canon_cache_fields GROUP BY field_name ORDER BY field_name",
        )
        report["strict_tables"] = strict_tables
        add_check(report["checks"], "exact_bounded_row_count", field_rows == EXPECTED_CANON_CACHE_ROWS, {"rows": field_rows})
        add_check(report["checks"], "rows_clean_match_ok", dirty_rows == 0, {"rows": dirty_rows})
        add_check(report["checks"], "authority_boundary_metadata_only", authority_rows == 0, {"rows": authority_rows})
        add_check(report["checks"], "strict_tables_ok", all(strict_tables.get(name) == 1 for name in ["canon_cache_meta", "canon_cache_fields", "canon_cache_change_ledger"]), strict_tables)
    report["status"] = "ok" if all(check["ok"] for check in report["checks"]) else "blocked"
    return report


def audit_finance_stack_snapshot() -> dict[str, Any]:
    report = sqlite_surface(
        FINANCE_STACK_DB,
        required_tables={"snapshot_runs", "ticker_rows", "web_evidence_rows"},
        required_views={"latest_snapshot", "latest_ticker_rows"},
    )
    if not report.get("exists"):
        return report
    with connect_readonly(FINANCE_STACK_DB) as conn:
        latest = conn.execute("SELECT id, status, freshness_grade FROM latest_snapshot").fetchone()
        deployable = [row["ticker"] for row in conn.execute("SELECT ticker FROM latest_ticker_rows WHERE readiness='DEPLOYABLE NOW' ORDER BY ticker")]
        report["latest"] = dict(latest) if latest else None
        report["row_counts"] = {
            "snapshot_runs": scalar(conn, "SELECT COUNT(*) FROM snapshot_runs"),
            "latest_ticker_rows": scalar(conn, "SELECT COUNT(*) FROM latest_ticker_rows"),
            "web_evidence_rows": scalar(conn, "SELECT COUNT(*) FROM web_evidence_rows"),
        }
        report["deployable_now"] = deployable
        add_check(report["checks"], "latest_snapshot_exists", latest is not None)
        add_check(report["checks"], "latest_snapshot_status_ok", latest is not None and latest["status"] in {"ok", "warning"}, dict(latest) if latest else None)
    report["status"] = "ok" if all(check["ok"] for check in report["checks"]) else "blocked"
    return report


def audit_finance_intelligence_state() -> dict[str, Any]:
    report = sqlite_surface(
        FINANCE_INTELLIGENCE_STATE_DB,
        required_tables={
            "source_run", "universe", "ticker_tier", "ticker_family_status",
            "latest_price_technical", "entry_stop_reference", "fundamental_snapshot",
            "analyst_snapshot", "earnings_calendar", "official_evidence_index",
            "promotion_signals", "card_registry", "validation_results", "pilot_fixture_registry",
        },
        required_views={
            "all_ticker_sql_rows", "current_ticker_cards", "latest_valid_entry_stop_refs", "stale_ticker_cards",
            "pending_approval_queue", "latest_validator_status", "artifact_provenance_map",
            "canon_conflict_candidates", "preopen_action_queue", "current_pilot_fixtures",
        },
    )
    if not report.get("exists"):
        return report
    with connect_readonly(FINANCE_INTELLIGENCE_STATE_DB) as conn:
        report["row_counts"] = {
            "universe": scalar(conn, "SELECT COUNT(*) FROM universe"),
            "all_ticker_sql_rows": scalar(conn, "SELECT COUNT(*) FROM all_ticker_sql_rows"),
            "production_answer_path_rows": scalar(conn, "SELECT COUNT(*) FROM universe WHERE production_answer_path_member=1"),
            "review_monitor_thin_rows": scalar(conn, "SELECT COUNT(*) FROM universe WHERE thin_monitor_row=1"),
            "current_ticker_cards": scalar(conn, "SELECT COUNT(*) FROM current_ticker_cards"),
            "latest_valid_entry_stop_refs": scalar(conn, "SELECT COUNT(*) FROM latest_valid_entry_stop_refs"),
            "card_registry": scalar(conn, "SELECT COUNT(*) FROM card_registry"),
            "fundamental_snapshot": scalar(conn, "SELECT COUNT(*) FROM fundamental_snapshot"),
            "analyst_snapshot": scalar(conn, "SELECT COUNT(*) FROM analyst_snapshot"),
            "preopen_action_queue": scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue"),
            "current_pilot_fixtures": scalar(conn, "SELECT COUNT(*) FROM current_pilot_fixtures"),
        }
        bad_authority = scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json!='[]'")
        source_open_missing = scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE source_open_required=0")
        failed_validators = scalar(conn, "SELECT COUNT(*) FROM validation_results WHERE status!='ok' AND severity='error'")
        add_check(report["checks"], "active_sql_rows_supported_scaleout_count", report["row_counts"]["all_ticker_sql_rows"] in SUPPORTED_ACTIVE_UNIVERSE_TICKERS, report["row_counts"])
        add_check(report["checks"], "production_current_42_present", report["row_counts"]["current_ticker_cards"] == EXPECTED_PRODUCTION_TICKERS and report["row_counts"]["production_answer_path_rows"] == EXPECTED_PRODUCTION_TICKERS, report["row_counts"])
        add_check(report["checks"], "review_monitor_thin_rows_supported_scaleout_count", report["row_counts"]["review_monitor_thin_rows"] in SUPPORTED_REVIEW_MONITOR_TICKERS, report["row_counts"])
        add_check(report["checks"], "all_snapshot_rows_supported_scaleout_count", report["row_counts"]["fundamental_snapshot"] in SUPPORTED_ACTIVE_UNIVERSE_TICKERS and report["row_counts"]["analyst_snapshot"] in SUPPORTED_ACTIVE_UNIVERSE_TICKERS and report["row_counts"]["card_registry"] in SUPPORTED_ACTIVE_UNIVERSE_TICKERS, report["row_counts"])
        add_check(report["checks"], "latest_valid_entry_stop_refs_42", report["row_counts"]["latest_valid_entry_stop_refs"] == EXPECTED_PRODUCTION_TICKERS, report["row_counts"])
        pilot_overlap = scalar(conn, "SELECT COUNT(*) FROM current_pilot_fixtures WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
        add_check(report["checks"], "pilot_fixtures_excluded_from_current_cards", pilot_overlap == 0, {"rows": pilot_overlap})
        add_check(report["checks"], "forbidden_authority_flags_false", bad_authority == 0, {"rows": bad_authority})
        add_check(report["checks"], "source_open_required_all_cards", source_open_missing == 0, {"rows": source_open_missing})
        add_check(report["checks"], "state_validators_clean", failed_validators == 0, {"rows": failed_validators})
    report["status"] = "ok" if all(check["ok"] for check in report["checks"]) else "blocked"
    return report


def audit_phase1_inputs() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {"checks": checks}
    universe = load_json_artifact(UNIVERSE_PATH) or {}
    validation = load_json_artifact(UNIVERSE_VALIDATION_PATH) or {}
    router_qa = load_json_artifact(ROUTER_QA_PATH) or {}
    entries = universe.get("entries") if isinstance(universe, dict) else None
    production_entries = legacy_42_tier_entries() or [
        row for row in entries or []
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope", "production_current_42") == "production_current_42"
    ]
    pilot_entries = [
        row for row in entries or []
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope") == "pilot_fixture"
    ]
    ticker_cards = sorted(TICKER_CARDS_DIR.glob("*.json")) if TICKER_CARDS_DIR.exists() else []
    authority = universe.get("authority_boundary", {}) if isinstance(universe, dict) else {}
    forbidden_true = [key for key, value in authority.items() if key.endswith("_allowed") and value is not False]

    report.update(
        {
            "universe_path": rel(UNIVERSE_PATH),
            "universe_ticker_count": len(entries) if isinstance(entries, list) else None,
            "production_ticker_count": len(production_entries),
            "pilot_fixture_count": len(pilot_entries),
            "universe_validation_status": validation.get("status") if isinstance(validation, dict) else None,
            "router_qa_status": router_qa.get("status") if isinstance(router_qa, dict) else None,
            "ticker_card_file_count": len(ticker_cards),
            "forbidden_true_authority_flags": forbidden_true,
        }
    )
    add_check(checks, "universe_exists", UNIVERSE_PATH.exists(), rel(UNIVERSE_PATH))
    add_check(checks, "active_universe_ticker_count_supported_scaleout", isinstance(entries, list) and len(entries) in SUPPORTED_ACTIVE_UNIVERSE_TICKERS, {"active_rows": len(entries) if isinstance(entries, list) else None})
    add_check(checks, "production_universe_ticker_count_42", isinstance(entries, list) and len(production_entries) == EXPECTED_PRODUCTION_TICKERS, {"production_rows": len(production_entries), "total_rows": len(entries) if isinstance(entries, list) else None})
    add_check(checks, "review_monitor_ticker_count_supported_scaleout", isinstance(entries, list) and len([row for row in entries if isinstance(row, dict) and row.get("universe_scope") == "review_100_monitor"]) in SUPPORTED_REVIEW_MONITOR_TICKERS, {"review_rows": len([row for row in entries if isinstance(row, dict) and row.get("universe_scope") == "review_100_monitor"]) if isinstance(entries, list) else None})
    add_check(checks, "pilot_fixture_count_within_contract", len(pilot_entries) <= 11, {"pilot_rows": len(pilot_entries)})
    add_check(checks, "universe_validation_ok", validation.get("status") == "ok", validation.get("summary"))
    add_check(checks, "router_qa_pass", router_qa.get("status") == "pass", router_qa.get("summary"))
    add_check(checks, "ticker_cards_present_42", len(ticker_cards) >= EXPECTED_PRODUCTION_TICKERS, {"files": len(ticker_cards)})
    add_check(checks, "universe_authority_flags_false", not forbidden_true, forbidden_true)
    report["status"] = "ok" if all(check["ok"] for check in checks) else "blocked"
    return report


def build_readiness() -> dict[str, Any]:
    surfaces = {
        "artifact_index": audit_artifact_index(),
        "workspace_index": audit_workspace_index(),
        "canon_cache": audit_canon_cache(),
        "finance_stack_snapshot": audit_finance_stack_snapshot(),
        "finance_intelligence_state": audit_finance_intelligence_state(),
        "phase1_inputs": audit_phase1_inputs(),
    }
    blocked = [name for name, surface in surfaces.items() if surface.get("status") != "ok"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "workflow": "WF78",
        "phase": "phase_2_readiness",
        "scope_note": "Broad SQL/index surface readiness gate; not the per-ticker readiness source of truth.",
        "per_ticker_readiness_index": "tmp/wf78-sql-readiness-index.json",
        "status": "ready" if not blocked else "blocked",
        "blocked_surfaces": blocked,
        "authority_boundary": {
            "database_path_migration_performed": False,
            "tmp_database_promotion_performed": False,
            "sql_canon_authority_expanded": False,
            "full_sql_canon_migration_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "paper_trade_execution_allowed": False,
            "human_approved_markdown_remains_canon": True,
            "json_remains_proof_review_layer": True,
            "sqlite_remains_validated_routing_cache_layer": True,
        },
        "phase2_ready_when": [
            "All SQLite surfaces pass integrity and foreign-key checks.",
            "Bounded canon-cache remains exactly 265 clean metadata rows in tmp with no authority expansion.",
            "Artifact/workspace indexes include WF78 Phase 1 universe artifacts.",
            "Finance stack snapshot SQL validates as generated review state.",
            "WF78 Phase 2 finance intelligence state validates as review-only current-state/query prototype.",
            "Phase 1 universe, ticker cards, and router QA remain clean.",
        ],
        "surfaces": surfaces,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(TMP / "wf78-sql-phase2-readiness.json"))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    readiness = build_readiness()
    out_path = Path(args.out)
    atomic_write_json(out_path, readiness)
    text = json.dumps(readiness, indent=2 if args.pretty else None, sort_keys=True)
    print(text)
    return 0 if readiness["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
