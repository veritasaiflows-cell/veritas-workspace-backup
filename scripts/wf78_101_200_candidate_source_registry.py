#!/usr/bin/env python3
"""Build the WF78 next-100 candidate source registry.

The registry is a durable, review-only seed source for the next WF78 expansion
batch. It uses S&P 500 constituents as the primary source, records provenance,
excludes the current WF78 active universe from eligibility, and selects a
deterministic next-100 planning set. It does not import/apply tickers, mutate finance canon,
promote production answer paths, infer owner approval, or authorize execution.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"

UNIVERSE = DATA / "finance" / "universe-v1.json"
DEFAULT_OUT_JSON = DATA / "finance" / "wf78-101-200-candidate-source-v1.json"
DEFAULT_OUT_DB = TMP / "wf78-101-200-candidate-source-registry.sqlite"

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
DEFAULT_POLICY_URL = "https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/"
SCHEMA = "veritas.wf78_101_200_candidate_source_registry.v1"
SUPPORTED_CURRENT_UNIVERSE_COUNTS = {100, 200, 300, 400}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "report_only": True,
    "source_registry_only": True,
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

REQUIRED_TRUE_FLAGS = {"review_only", "report_only", "source_registry_only"}
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_universe_entries() -> list[dict[str, Any]]:
    payload = load_json_artifact(UNIVERSE)
    entries = as_list(as_dict(payload).get("entries"))
    return [row for row in entries if isinstance(row, dict)]


def current_tickers(entries: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("ticker", "")).upper() for row in entries if row.get("active") is True and row.get("ticker")}


def fetch_text(url: str, timeout: int) -> str:
    req = Request(url, headers={"User-Agent": "OpenClaw-Veritas/1.0 internal review-only WF78 source registry"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def normalize_ticker(symbol: str) -> str:
    return symbol.strip().upper()


def yfinance_symbol(symbol: str) -> str:
    return normalize_ticker(symbol).replace(".", "-")


def parse_sp500_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        symbol = normalize_ticker(raw.get("Symbol", ""))
        if not symbol:
            continue
        rows.append(
            {
                "ticker": symbol,
                "source_symbol": symbol,
                "yfinance_symbol": yfinance_symbol(symbol),
                "name": (raw.get("Security") or "").strip(),
                "sector": (raw.get("GICS Sector") or "").strip(),
                "industry": (raw.get("GICS Sub-Industry") or "").strip(),
                "headquarters_location": (raw.get("Headquarters Location") or "").strip(),
                "date_added": (raw.get("Date added") or "").strip(),
                "sec_cik": (raw.get("CIK") or "").strip(),
                "founded": (raw.get("Founded") or "").strip(),
                "source_row": dict(raw),
            }
        )
    return rows


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def score_candidate(row: dict[str, Any], sector_current_counts: Counter[str], sector_candidate_counts: Counter[str]) -> dict[str, Any]:
    sector = str(row.get("sector") or "Unknown")
    score = 50
    score += 20 if row.get("sec_cik") else 0
    score += 10 if row.get("industry") else 0
    score += 5 if row.get("date_added") else 0
    # Prefer sectors underrepresented in current WF78 100 and avoid simply adding more technology concentration.
    current_sector_count = sector_current_counts.get(sector, 0)
    score += max(0, 20 - min(20, current_sector_count))
    score -= min(12, sector_candidate_counts.get(sector, 0) // 8)
    return {
        "score": max(0, min(100, score)),
        "current_sector_count": current_sector_count,
        "scoring_notes": [
            "S&P 500 membership is used as a primary large-cap source seed.",
            "Score favors identity completeness, CIK availability, and current WF78 sector diversification.",
            "Financial quality/provider/source-open proof still required before import or promotion.",
        ],
    }


def select_round_robin(candidates: list[dict[str, Any]], target_new: int) -> list[str]:
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(candidates, key=lambda item: (-int(item.get("score", 0)), str(item.get("ticker", "")))):
        by_sector[str(row.get("sector") or "Unknown")].append(row)
    selected: list[str] = []
    seen: set[str] = set()
    sectors = sorted(by_sector, key=lambda sector: (-len(by_sector[sector]), sector))
    while len(selected) < target_new and any(by_sector.values()):
        for sector in sectors:
            bucket = by_sector.get(sector, [])
            if not bucket:
                continue
            row = bucket.pop(0)
            ticker = str(row.get("ticker", "")).upper()
            if ticker and ticker not in seen:
                selected.append(ticker)
                seen.add(ticker)
                if len(selected) >= target_new:
                    break
    return selected


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    generated_at = utc_now()

    universe_entries = load_universe_entries()
    active_tickers = current_tickers(universe_entries)
    add_check(checks, "current_universe_exists", UNIVERSE.exists(), rel(UNIVERSE))
    add_check(
        checks,
        "current_universe_has_supported_active_ticker_count",
        len(active_tickers) in SUPPORTED_CURRENT_UNIVERSE_COUNTS,
        {"actual": len(active_tickers), "supported": sorted(SUPPORTED_CURRENT_UNIVERSE_COUNTS)},
    )
    add_check(checks, "target_new_positive", args.target_new > 0, args.target_new)

    source_text = fetch_text(args.source_url, args.timeout)
    source_sha256 = sha256_text(source_text)
    source_rows = parse_sp500_csv(source_text)
    add_check(checks, "source_rows_loaded", len(source_rows) >= args.target_new, len(source_rows))
    unique_source_tickers = {row["ticker"] for row in source_rows}
    add_check(checks, "source_tickers_unique", len(unique_source_tickers) == len(source_rows), {"rows": len(source_rows), "unique": len(unique_source_tickers)})

    current_sector_counts = Counter(str(row.get("sector") or "Unknown") for row in universe_entries if row.get("active") is True)
    candidate_sector_counts = Counter(str(row.get("sector") or "Unknown") for row in source_rows)

    candidates: list[dict[str, Any]] = []
    eligible_rows: list[dict[str, Any]] = []
    blocked_identity = 0
    duplicates = 0
    for raw in source_rows:
        ticker = raw["ticker"]
        already = ticker in active_tickers or raw["yfinance_symbol"].upper() in active_tickers
        identity_complete = bool(raw.get("ticker") and raw.get("name") and raw.get("sector") and raw.get("sec_cik"))
        if already:
            group = "duplicate_or_current_100"
            duplicates += 1
        elif not identity_complete:
            group = "blocked_bad_or_missing_identity"
            blocked_identity += 1
        else:
            group = "eligible_pool_not_selected"
        score = score_candidate(raw, current_sector_counts, candidate_sector_counts)
        row = {
            **{key: value for key, value in raw.items() if key != "source_row"},
            "source_name": "S&P 500 constituent public CSV seed",
            "source_url": args.source_url,
            "index_policy_url": args.policy_url,
            "source_retrieved_at_utc": generated_at,
            "source_sha256": source_sha256,
            "source_posture": "public_constituent_seed_for_internal_review_not_index_provider_official_constituent_file",
            "index_family": "S&P 500",
            "overlay_family": "Russell overlay reserved; not used in this registry pass",
            "already_in_current_100": already,
            "eligible_for_101_200": not already and identity_complete,
            "identity_complete": identity_complete,
            "candidate_group": group,
            "score": score["score"],
            "score_detail": score,
            "inclusion_reason": "primary S&P 500 seed" if not already else "already present in current WF78 100",
            "authority_boundary": AUTHORITY_BOUNDARY,
            "source_row": raw["source_row"],
        }
        candidates.append(row)
        if row["eligible_for_101_200"]:
            eligible_rows.append(row)

    selected_tickers = select_round_robin(eligible_rows, args.target_new)
    selected_set = set(selected_tickers)
    selected_rank = {ticker: index + 1 for index, ticker in enumerate(selected_tickers)}
    for row in candidates:
        ticker = row["ticker"]
        if ticker in selected_set:
            row["candidate_group"] = "selected_101_200_primary_sp500"
            row["selected_for_101_200"] = True
            row["selected_rank"] = selected_rank[ticker]
        else:
            row["selected_for_101_200"] = False
            row["selected_rank"] = None

    if len(selected_tickers) < args.target_new:
        warnings.append(
            {
                "name": "selected_count_below_target",
                "severity": "warning",
                "detail": {"selected": len(selected_tickers), "target_new": args.target_new},
            }
        )

    group_counts = Counter(str(row.get("candidate_group")) for row in candidates)
    selected_sector_counts = Counter(str(row.get("sector") or "Unknown") for row in candidates if row.get("selected_for_101_200"))

    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))
    add_check(checks, "selected_count_matches_target", len(selected_tickers) == args.target_new, {"selected": len(selected_tickers), "target_new": args.target_new})

    errors = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    status = "ok" if not errors else "error"
    report = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_101_200_candidate_source_registry",
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_policy": {
            "primary_source": "S&P 500 constituent public CSV seed",
            "primary_source_url": args.source_url,
            "index_policy_url": args.policy_url,
            "source_posture": "review-only candidate seed; not index-provider official constituent file; source-open before material claims",
            "russell_overlay_policy": "reserved for later upside-discovery overlay after this S&P 500 primary source validates",
            "candidate_source_rule": "exclude current WF78 active universe; select deterministic next 100; do not import/apply from this registry",
        },
        "summary": {
            "current_universe_count": len(active_tickers),
            "source_row_count": len(source_rows),
            "eligible_candidate_count": len(eligible_rows),
            "selected_candidate_count": len(selected_tickers),
            "target_new": args.target_new,
            "duplicate_or_current_100_count": duplicates,
            "blocked_bad_or_missing_identity_count": blocked_identity,
            "group_counts": dict(sorted(group_counts.items())),
            "selected_sector_counts": dict(sorted(selected_sector_counts.items())),
            "missing_artifacts": [] if UNIVERSE.exists() else [rel(UNIVERSE)],
            "next_safe_action": "Run the 100->200 manifest against this source registry, then run provider/runtime proof before any import/apply decision.",
        },
        "selected_101_200": [row for row in sorted(candidates, key=lambda item: item.get("selected_rank") or 9999) if row_bool(row, "selected_for_101_200")],
        "candidates": sorted(candidates, key=lambda item: (str(item.get("candidate_group")), item.get("selected_rank") or 9999, str(item.get("ticker")))),
        "source_artifacts": [
            {
                "artifact_type": "current_wf78_universe",
                "path": rel(UNIVERSE),
                "exists": UNIVERSE.exists(),
            },
            {
                "artifact_type": "primary_sp500_seed_csv",
                "url": args.source_url,
                "sha256": source_sha256,
                "retrieved_at_utc": generated_at,
                "row_count": len(source_rows),
            },
            {
                "artifact_type": "sp_us_indices_methodology_policy",
                "url": args.policy_url,
            },
        ],
        "validation": {
            "status": status,
            "checks": checks,
            "warnings": warnings,
            "errors": errors,
        },
        "stop_lines": [
            "No import/apply from this registry.",
            "No production answer-path change.",
            "No SQL-canon/cache expansion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner approval inference.",
            "No customer/external delivery.",
            "No paper/live/brokerage/account action or money movement.",
            "Source-open exact evidence before material finance claims.",
        ],
    }
    return report


def row_bool(row: dict[str, Any], key: str) -> bool:
    return bool(row.get(key))


def connect_write(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def scalar(conn: sqlite3.Connection, sql: str) -> Any:
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql)]


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS source_candidates;
        DROP TABLE IF EXISTS selected_candidates;
        DROP TABLE IF EXISTS source_artifacts;
        DROP TABLE IF EXISTS authority_boundary;
        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE source_candidates (
            ticker TEXT PRIMARY KEY,
            source_symbol TEXT NOT NULL,
            yfinance_symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            industry TEXT,
            headquarters_location TEXT,
            date_added TEXT,
            sec_cik TEXT,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_retrieved_at_utc TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            source_posture TEXT NOT NULL,
            already_in_current_100 INTEGER NOT NULL CHECK (already_in_current_100 IN (0,1)),
            eligible_for_101_200 INTEGER NOT NULL CHECK (eligible_for_101_200 IN (0,1)),
            selected_for_101_200 INTEGER NOT NULL CHECK (selected_for_101_200 IN (0,1)),
            selected_rank INTEGER,
            candidate_group TEXT NOT NULL,
            score INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE selected_candidates (
            selected_rank INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            industry TEXT,
            score INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            source_retrieved_at_utc TEXT NOT NULL
        ) STRICT;

        CREATE TABLE source_artifacts (
            artifact_type TEXT PRIMARY KEY,
            path_or_url TEXT NOT NULL,
            artifact_exists INTEGER NOT NULL CHECK (artifact_exists IN (0,1)),
            sha256 TEXT,
            retrieved_at_utc TEXT,
            row_count INTEGER
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
        for row in as_list(report.get("candidates")):
            conn.execute(
                """
                INSERT INTO source_candidates (
                    ticker, source_symbol, yfinance_symbol, name, sector, industry,
                    headquarters_location, date_added, sec_cik, source_name, source_url,
                    source_retrieved_at_utc, source_sha256, source_posture,
                    already_in_current_100, eligible_for_101_200, selected_for_101_200,
                    selected_rank, candidate_group, score, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("ticker"),
                    row.get("source_symbol"),
                    row.get("yfinance_symbol"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("industry"),
                    row.get("headquarters_location"),
                    row.get("date_added"),
                    row.get("sec_cik"),
                    row.get("source_name"),
                    row.get("source_url"),
                    row.get("source_retrieved_at_utc"),
                    row.get("source_sha256"),
                    row.get("source_posture"),
                    int_bool(row.get("already_in_current_100")),
                    int_bool(row.get("eligible_for_101_200")),
                    int_bool(row.get("selected_for_101_200")),
                    row.get("selected_rank"),
                    row.get("candidate_group"),
                    int(row.get("score") or 0),
                    json_text(row),
                ),
            )
        for row in as_list(report.get("selected_101_200")):
            conn.execute(
                """
                INSERT INTO selected_candidates (
                    selected_rank, ticker, name, sector, industry, score, source_url,
                    source_retrieved_at_utc
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("selected_rank"),
                    row.get("ticker"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("industry"),
                    int(row.get("score") or 0),
                    row.get("source_url"),
                    row.get("source_retrieved_at_utc"),
                ),
            )
        for row in as_list(report.get("source_artifacts")):
            conn.execute(
                """
                INSERT INTO source_artifacts (
                    artifact_type, path_or_url, artifact_exists, sha256,
                    retrieved_at_utc, row_count
                ) VALUES (?,?,?,?,?,?)
                """,
                (
                    row.get("artifact_type"),
                    row.get("path") or row.get("url"),
                    int_bool(row.get("exists", True)),
                    row.get("sha256"),
                    row.get("retrieved_at_utc"),
                    row.get("row_count"),
                ),
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
        for row in as_list(as_dict(report.get("validation")).get("warnings")):
            conn.execute(
                "INSERT OR REPLACE INTO validation_results (name, status, ok, severity, detail_json) VALUES (?,?,?,?,?)",
                (row.get("name"), "warning", 1, row.get("severity", "warning"), json_text(row.get("detail"))),
            )
        for key, value in {
            "schema": report.get("schema"),
            "generated_at_utc": report.get("generated_at_utc"),
            "status": report.get("status"),
            "source_row_count": as_dict(report.get("summary")).get("source_row_count"),
            "eligible_candidate_count": as_dict(report.get("summary")).get("eligible_candidate_count"),
            "selected_candidate_count": as_dict(report.get("summary")).get("selected_candidate_count"),
            "target_new": as_dict(report.get("summary")).get("target_new"),
        }.items():
            conn.execute("INSERT INTO meta (key, value) VALUES (?,?)", (key, json_text(value)))
        conn.commit()


def validate_outputs(args: argparse.Namespace, report: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []
    if args.write:
        loaded = load_json_artifact(args.out_json)
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            errors.append("JSON output missing or schema mismatch")
        if not args.out_db.exists():
            errors.append(f"missing SQLite output: {rel(args.out_db)}")
        else:
            with connect_ro(args.out_db) as conn:
                integrity = scalar(conn, "PRAGMA integrity_check")
                if integrity != "ok":
                    errors.append(f"SQLite integrity_check={integrity}")
                strict_tables = {
                    row["name"]
                    for row in rows(conn, "PRAGMA table_list")
                    if row.get("schema") == "main" and row.get("type") == "table" and row.get("strict") == 1
                }
                required = {"source_candidates", "selected_candidates", "source_artifacts", "authority_boundary", "validation_results", "meta"}
                missing = sorted(required - strict_tables)
                if missing:
                    errors.append(f"missing STRICT tables: {missing}")
                unsafe = scalar(conn, "SELECT count(*) FROM authority_boundary WHERE ok=0")
                if unsafe:
                    errors.append(f"unsafe authority rows: {unsafe}")
                selected = scalar(conn, "SELECT count(*) FROM selected_candidates")
                expected = as_dict(report.get("summary")).get("selected_candidate_count")
                if selected != expected:
                    errors.append(f"selected_candidates rows {selected} != expected {expected}")
    return ("ok" if not errors else "error", errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--policy-url", default=DEFAULT_POLICY_URL)
    parser.add_argument("--target-new", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


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
        status = "error"
    print(
        json.dumps(
            {
                "status": status,
                "validation_result": report["status"],
                "output_validation_result": output_status,
                "output_validation_errors": output_errors,
                "json_out": rel(args.out_json) if args.write else None,
                "db_out": rel(args.out_db) if args.write else None,
                "summary": report["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
