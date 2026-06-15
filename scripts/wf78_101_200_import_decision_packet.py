#!/usr/bin/env python3
"""Build a report-only WF78 101-200 import decision packet.

This packet summarizes the selected 101-200 candidate proof and presents the
next owner decision. It does not import/apply tickers, promote production answer
paths, expand SQL canon authority, mutate canon or portfolio state, infer owner
approval, or authorize paper/live/account actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

SOURCE_REGISTRY = DATA / "finance" / "wf78-101-200-candidate-source-v1.json"
MANIFEST = TMP / "wf78-100-to-200-candidate-manifest.json"
PROVIDER_VALIDATION = TMP / "wf78-101-200-provider-source-validation.json"
RUNNER = TMP / "wf78-phase-runner-current.json"

DEFAULT_OUT_JSON = TMP / "wf78-101-200-import-decision-packet.json"
DEFAULT_OUT_DB = TMP / "wf78-101-200-import-decision-packet.sqlite"

SCHEMA = "veritas.wf78_101_200_import_decision_packet.v1"
EXPECTED_SELECTED = 100

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "decision_packet_only": True,
    "read_existing_artifacts_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "sql_canon_expansion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "decision_packet_only", "read_existing_artifacts_only"}
REQUIRED_FALSE_FLAGS = {
    "ticker_import_allowed",
    "apply_allowed",
    "promotion_allowed",
    "production_answer_path_change_allowed",
    "sql_canon_expansion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
}


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
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def symbol_key(value: Any) -> str:
    return str(value or "").upper().replace(".", "-")


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def artifact_meta(path: Path, artifact_type: str, required: bool) -> dict[str, Any]:
    payload = load_dict(path) if path.suffix.lower() == ".json" and path.exists() else {}
    stat = path.stat() if path.exists() else None
    return {
        "artifact_type": artifact_type,
        "path": rel(path),
        "exists": path.exists(),
        "required": required,
        "sha256": sha256_file(path),
        "size_bytes": stat.st_size if stat else None,
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
    }


def selected_source_rows(source_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = as_list(source_registry.get("selected_101_200"))
    return {symbol_key(row.get("yfinance_symbol") or row.get("ticker")): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def selected_manifest_rows(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = as_list(manifest.get("candidate_manifest"))
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = symbol_key(row.get("ticker"))
        if ticker and row.get("eligible_for_100_to_200") is True and row.get("already_present") is False:
            selected[ticker] = row
    return selected


def decision_rows(provider_validation: dict[str, Any], source_rows: dict[str, dict[str, Any]], manifest_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(provider_validation.get("candidate_rows")):
        if not isinstance(row, dict):
            continue
        ticker = symbol_key(row.get("ticker"))
        source = source_rows.get(ticker, {})
        manifest = manifest_rows.get(ticker, {})
        provider_ok = row.get("provider_status") == "ok" and row.get("provider_runtime_present") is True
        sec_ok = row.get("sec_cik_match") is True
        source_ready = row.get("source_open_ready") is True
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name") or source.get("name") or manifest.get("name"),
                "sector": row.get("sector") or source.get("sector") or manifest.get("sector"),
                "industry": row.get("industry") or source.get("industry") or manifest.get("industry"),
                "selected_rank": row.get("selected_rank") or source.get("selected_rank"),
                "source_symbol": row.get("source_symbol") or source.get("source_symbol"),
                "yfinance_symbol": row.get("yfinance_symbol") or source.get("yfinance_symbol"),
                "sec_cik": row.get("sec_cik") or source.get("sec_cik"),
                "provider_status": row.get("provider_status"),
                "provider_runtime_present": bool(provider_ok),
                "sec_cik_match": bool(sec_ok),
                "source_open_ready": bool(source_ready),
                "pre_import_source_validated": bool(provider_ok and sec_ok and source_ready),
                "decision_grade_eligible": False,
                "thin_monitor_import_review_eligible": bool(provider_ok and sec_ok and source_ready),
                "recommended_import_scope": "review_only_tier_c_thin_monitor_candidate",
                "required_before_import_apply": [
                    "Randall exact owner approval for 101-200 thin-monitor import scope",
                    "backup and rollback proof",
                    "no-regression proof for current production 42 and review 100",
                    "post-apply validation plan",
                ],
                "required_before_promotion": [
                    "full ticker card build",
                    "fundamental, analyst, valuation, technical, risk, and official-source evidence layers",
                    "production answer-path consumer diff and owner approval",
                ],
            }
        )
    return sorted(rows, key=lambda item: int(item.get("selected_rank") or 9999))


def build_report(_: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source_registry = load_dict(SOURCE_REGISTRY)
    manifest = load_dict(MANIFEST)
    provider_validation = load_dict(PROVIDER_VALIDATION)
    runner = load_dict(RUNNER)

    artifacts = [
        artifact_meta(SOURCE_REGISTRY, "wf78_101_200_candidate_source_registry", True),
        artifact_meta(MANIFEST, "wf78_100_to_200_candidate_manifest", True),
        artifact_meta(PROVIDER_VALIDATION, "wf78_101_200_provider_source_validation", True),
        artifact_meta(RUNNER, "wf78_phase_runner_current", False),
    ]
    for item in artifacts:
        add_check(checks, f"{item['artifact_type']}_exists", item["exists"] or not item["required"], item)

    source_rows = selected_source_rows(source_registry)
    manifest_rows = selected_manifest_rows(manifest)
    rows = decision_rows(provider_validation, source_rows, manifest_rows)

    source_tickers = set(source_rows)
    manifest_tickers = set(manifest_rows)
    row_tickers = {symbol_key(row.get("ticker")) for row in rows}
    source_ready = [row for row in rows if row.get("pre_import_source_validated") is True]
    not_ready = [row for row in rows if row.get("pre_import_source_validated") is not True]
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in rows)

    add_check(checks, "source_registry_selected_100", len(source_rows) == EXPECTED_SELECTED, len(source_rows))
    add_check(checks, "manifest_selected_100", len(manifest_rows) == EXPECTED_SELECTED, len(manifest_rows))
    add_check(checks, "provider_validation_rows_100", len(rows) == EXPECTED_SELECTED, len(rows))
    add_check(checks, "registry_manifest_provider_ticker_sets_match", source_tickers == manifest_tickers == row_tickers, {
        "source_only": sorted(source_tickers - row_tickers),
        "manifest_only": sorted(manifest_tickers - row_tickers),
        "provider_only": sorted(row_tickers - source_tickers),
    })
    add_check(checks, "provider_validation_status_ok", provider_validation.get("status") == "ok", provider_validation.get("status"))
    add_check(checks, "provider_validation_pre_import_source_validated", provider_validation.get("candidate_validation_status") == "pre_import_source_validated", provider_validation.get("candidate_validation_status"))
    add_check(checks, "all_candidates_source_ready", len(source_ready) == EXPECTED_SELECTED, {"ready": len(source_ready), "not_ready": len(not_ready)})
    add_check(checks, "runner_all_safe_ok_if_present", not runner or (runner.get("status") == "ok" and as_dict(runner.get("summary")).get("failed_steps") == 0), as_dict(runner.get("summary")), "warning")
    add_check(checks, "runner_no_apply_or_import_if_present", not runner or as_dict(runner.get("summary")).get("apply_or_import_executed") is False, as_dict(runner.get("summary")))
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    critical = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    status = "decision_required" if not critical else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_101_200_import_decision_packet",
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "selected_candidate_count": len(rows),
            "pre_import_source_validated_count": len(source_ready),
            "blocked_or_repair_count": len(not_ready),
            "thin_monitor_import_review_eligible_count": len([row for row in rows if row.get("thin_monitor_import_review_eligible") is True]),
            "decision_grade_eligible_count": 0,
            "sector_counts": dict(sorted(sector_counts.items())),
            "recommended_decision": "Choose whether to approve a scoped 101-200 review-only Tier C thin-monitor import packet, or require deeper per-ticker card/fundamental/analyst validation first.",
            "recommended_default": "deeper_card_fundamental_analyst_validation_before_import_apply",
        },
        "decision_required": {
            "owner_question": "Approve preparation of an exact 101-200 review-only thin-monitor import apply gate, or require deeper per-ticker card/fundamental/analyst validation first?",
            "option_a_recommended": "Build deeper per-ticker card/fundamental/analyst/source-open validation for the 100 selected names before any import apply.",
            "option_b": "Prepare an exact owner-gated import apply packet for 100 Tier C thin-monitor rows only; still no production promotion.",
            "not_authorized_by_this_packet": [
                "ticker import/apply",
                "production answer-path expansion",
                "SQL canon expansion",
                "portfolio/canon mutation",
                "paper/live/account action",
                "owner approval inference",
            ],
        },
        "candidate_rows": rows,
        "groups": {
            "thin_monitor_import_review_eligible": [{"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"), "selected_rank": row.get("selected_rank")} for row in source_ready],
            "blocked_or_repair": [{"ticker": row["ticker"], "name": row.get("name"), "blocker": "provider_or_source_repair_required"} for row in not_ready],
        },
        "source_artifacts": artifacts,
        "validation": {
            "status": "ok" if not critical else "error",
            "checks": checks,
            "errors": critical,
        },
        "stop_lines": [
            "This packet does not import/apply tickers.",
            "This packet does not approve production answer-path expansion.",
            "This packet does not expand SQL canon/cache authority.",
            "This packet does not mutate canon, portfolio, cash, risk rules, or execution entitlement.",
            "This packet does not infer owner approval.",
            "This packet does not authorize paper/live/brokerage/account actions or money movement.",
        ],
    }


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS decision_candidates;
        DROP TABLE IF EXISTS source_artifacts;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE decision_candidates (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            industry TEXT,
            selected_rank INTEGER,
            provider_status TEXT NOT NULL,
            sec_cik_match INTEGER NOT NULL CHECK (sec_cik_match IN (0,1)),
            source_open_ready INTEGER NOT NULL CHECK (source_open_ready IN (0,1)),
            pre_import_source_validated INTEGER NOT NULL CHECK (pre_import_source_validated IN (0,1)),
            thin_monitor_import_review_eligible INTEGER NOT NULL CHECK (thin_monitor_import_review_eligible IN (0,1)),
            decision_grade_eligible INTEGER NOT NULL CHECK (decision_grade_eligible IN (0,1)),
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE source_artifacts (
            artifact_type TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            artifact_exists INTEGER NOT NULL CHECK (artifact_exists IN (0,1)),
            required INTEGER NOT NULL CHECK (required IN (0,1)),
            sha256 TEXT,
            status TEXT
        ) STRICT;

        CREATE TABLE authority_boundary (
            flag TEXT PRIMARY KEY,
            value INTEGER NOT NULL CHECK (value IN (0,1)),
            required_value INTEGER NOT NULL CHECK (required_value IN (0,1)),
            ok INTEGER NOT NULL CHECK (ok IN (0,1))
        ) STRICT;

        CREATE TABLE validation_results (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            ok INTEGER NOT NULL CHECK (ok IN (0,1)),
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;
        """
    )


def write_sqlite(report: dict[str, Any], db_path: Path) -> None:
    with connect_write(db_path) as conn:
        init_schema(conn)
        for row in as_list(report.get("candidate_rows")):
            conn.execute(
                """
                INSERT INTO decision_candidates (
                    ticker, name, sector, industry, selected_rank, provider_status,
                    sec_cik_match, source_open_ready, pre_import_source_validated,
                    thin_monitor_import_review_eligible, decision_grade_eligible, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("ticker"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("industry"),
                    row.get("selected_rank"),
                    row.get("provider_status"),
                    int_bool(row.get("sec_cik_match")),
                    int_bool(row.get("source_open_ready")),
                    int_bool(row.get("pre_import_source_validated")),
                    int_bool(row.get("thin_monitor_import_review_eligible")),
                    int_bool(row.get("decision_grade_eligible")),
                    json_text(row),
                ),
            )
        for item in as_list(report.get("source_artifacts")):
            conn.execute(
                "INSERT INTO source_artifacts (artifact_type, path, artifact_exists, required, sha256, status) VALUES (?,?,?,?,?,?)",
                (item.get("artifact_type"), item.get("path"), int_bool(item.get("exists")), int_bool(item.get("required")), item.get("sha256"), item.get("status")),
            )
        for flag, value in as_dict(report.get("authority_boundary")).items():
            required = True if flag in REQUIRED_TRUE_FLAGS else False if flag in REQUIRED_FALSE_FLAGS else bool(value)
            conn.execute(
                "INSERT INTO authority_boundary (flag, value, required_value, ok) VALUES (?,?,?,?)",
                (flag, int_bool(value), int_bool(required), int_bool(bool(value) == required)),
            )
        for row in as_list(as_dict(report.get("validation")).get("checks")):
            conn.execute(
                "INSERT INTO validation_results (name, status, ok, severity, detail_json) VALUES (?,?,?,?,?)",
                (row.get("name"), row.get("status"), int_bool(row.get("ok")), row.get("severity"), json_text(row.get("detail"))),
            )
        for key, value in {
            "schema": report.get("schema"),
            "generated_at_utc": report.get("generated_at_utc"),
            "status": report.get("status"),
            "selected_candidate_count": as_dict(report.get("summary")).get("selected_candidate_count"),
            "pre_import_source_validated_count": as_dict(report.get("summary")).get("pre_import_source_validated_count"),
            "decision_grade_eligible_count": as_dict(report.get("summary")).get("decision_grade_eligible_count"),
        }.items():
            conn.execute("INSERT INTO meta (key, value) VALUES (?,?)", (key, json_text(value)))
        conn.commit()


def validate_outputs(args: argparse.Namespace, report: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    if as_dict(report.get("validation")).get("errors"):
        errors.append("critical validation errors present")
    if args.write:
        loaded = load_json_artifact(args.out_json)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("JSON output missing or schema mismatch")
        if not args.out_db.exists():
            errors.append("SQLite output missing")
        else:
            with connect_ro(args.out_db) as conn:
                if scalar(conn, "PRAGMA integrity_check") != "ok":
                    errors.append("SQLite integrity_check failed")
                strict = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_list")
                    if row["schema"] == "main" and row["type"] == "table" and row["strict"] == 1
                }
                required = {"decision_candidates", "source_artifacts", "authority_boundary", "validation_results", "meta"}
                missing = sorted(required - strict)
                if missing:
                    errors.append(f"missing STRICT tables: {missing}")
                if scalar(conn, "SELECT count(*) FROM authority_boundary WHERE ok=0"):
                    errors.append("unsafe authority rows present")
                if scalar(conn, "SELECT count(*) FROM decision_candidates") != len(as_list(report.get("candidate_rows"))):
                    errors.append("decision candidate row count mismatch")
    return "ok" if not errors else "error", errors


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_json = resolve(args.out_json)
    args.out_db = resolve(args.out_db)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out_json, report, ensure_ascii=False)
        write_sqlite(report, args.out_db)
    output_status = "not_run"
    output_errors: list[str] = []
    if args.validate:
        output_status, output_errors = validate_outputs(args, report)
    status = report["status"]
    if output_errors:
        status = "blocked"
    print(
        json.dumps(
            {
                "status": status,
                "validation_result": as_dict(report.get("validation")).get("status"),
                "output_validation_result": output_status,
                "output_validation_errors": output_errors,
                "json_out": rel(args.out_json) if args.write else None,
                "db_out": rel(args.out_db) if args.write else None,
                "summary": report.get("summary"),
                "decision_required": report.get("decision_required"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status in {"decision_required", "ok"} and not output_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
