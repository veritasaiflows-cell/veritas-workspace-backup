#!/usr/bin/env python3
"""WF78 review-only finance intelligence state and query packet surface.

Builds a compact SQL current-state/query layer for the current WF78 universe.
This is routing/review infrastructure only. It does not replace Markdown canon,
promote tmp databases, infer owner approval, or authorize paper/live execution.
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
from wf72_entry_stop_reference_helper import build_entry_stop_reference_metadata

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

DEFAULT_DB = TMP / "finance-intelligence-state.sqlite"
DEFAULT_VALIDATION = TMP / "finance-intelligence-state-validation.json"
DEFAULT_TICKER_PACKET = TMP / "finance-intelligence-state-ticker-packet.json"
DEFAULT_PREOPEN_PACKET = TMP / "finance-intelligence-state-preopen-packet.json"
DEFAULT_STALE_PACKET = TMP / "finance-intelligence-state-stale-tickers.json"
DEFAULT_PENDING_PACKET = TMP / "finance-intelligence-state-pending-approvals.json"
DEFAULT_VALIDATOR_PACKET = TMP / "finance-intelligence-state-validator-status.json"
DEFAULT_SOURCE_PROOF_PACKET = TMP / "finance-intelligence-state-source-proof.json"
DEFAULT_ENTRY_STOP_PACKET = TMP / "finance-intelligence-state-entry-stop-refs.json"
DEFAULT_ACTION_QUEUE_PACKET = TMP / "finance-intelligence-state-action-queue.json"
DEFAULT_PHASE3_QC = TMP / "finance-intelligence-state-phase3-qc.json"
DEFAULT_PAPER_POSITIONS_PACKET = TMP / "finance-intelligence-state-paper-positions.json"
DEFAULT_PILOT_FIXTURE_PACKET = TMP / "finance-intelligence-state-pilot-fixtures.json"
DEFAULT_LIVE_PILOT_PACKET = TMP / "finance-intelligence-state-live-pilot.json"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
COVERAGE_PATH = TMP / "finance-data-coverage-current.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
ROUTER_QA_PATH = TMP / "finance-intelligence-router-qa-wf78-phase3.json"
PAPER_POSITION_DB = TMP / "wf67-paper-position-state.sqlite"

SCHEMA_VERSION = 1
EXPECTED_CURRENT_TICKERS = 42
PRODUCTION_SCOPE = "production_current_42"
PILOT_SCOPE = "pilot_fixture"
AUTHORITY_FALSE_KEYS = {
    "canonical_note_mutation_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "sizing_apply_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "live_trade_allowed",
    "live_brokerage_or_account_action_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed_by_card",
    "paper_order_cancel_allowed_by_card",
    "paper_order_submit_allowed_by_this_registry",
    "paper_order_cancel_allowed_by_this_registry",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    data = load_json_artifact(path)
    return default if data is None else data


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_json_text(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return [] if default is None else default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value if default is None else default


def write_packet(path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    atomic_write_json(path, packet)
    return packet


def packet_header(artifact_type: str, db_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": artifact_type,
        "db_path": rel(db_path),
        "authority_boundary": authority_boundary(),
        "answer_contract": {
            "sql_is_routing_and_current_state_only": True,
            "material_finance_claim_requires_source_open": True,
            "canonical_markdown_remains_owner_truth": True,
            "must_not_infer_approval_or_execution_authority": True,
            "must_disclose_stale_or_conflicting_rows": True,
        },
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


def card_path(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def source_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False}
    payload = load_json(path, {})
    generated = payload.get("generated_at_utc") if isinstance(payload, dict) else None
    return {
        "path": rel(path),
        "exists": True,
        "generated_at_utc": generated,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "size_bytes": path.stat().st_size,
    }


def authority_forbidden_true(*objects: Any) -> list[str]:
    found: list[str] = []
    for obj in objects:
        auth = as_dict(obj)
        for key in AUTHORITY_FALSE_KEYS:
            if auth.get(key) is True:
                found.append(key)
    return sorted(set(found))


def canon_cache_rows() -> dict[tuple[str, str], dict[str, Any]]:
    if not CANON_CACHE_DB.exists():
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    with connect_ro(CANON_CACHE_DB) as conn:
        for row in rows(conn, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name"):
            out[(str(row["scope"]).upper(), str(row["field_name"]))] = row
    return out


def canon_value(cache: dict[tuple[str, str], dict[str, Any]], ticker: str, field: str) -> dict[str, Any]:
    row = cache.get((ticker.upper(), field))
    return row if row else {}


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS preopen_action_queue;
        DROP VIEW IF EXISTS canon_conflict_candidates;
        DROP VIEW IF EXISTS artifact_provenance_map;
        DROP VIEW IF EXISTS current_pilot_fixtures;
        DROP VIEW IF EXISTS latest_validator_status;
        DROP VIEW IF EXISTS pending_approval_queue;
        DROP VIEW IF EXISTS stale_ticker_cards;
        DROP VIEW IF EXISTS latest_valid_entry_stop_refs;
        DROP VIEW IF EXISTS current_ticker_cards;

        DROP TABLE IF EXISTS validation_results;
        DROP TABLE IF EXISTS pilot_fixture_registry;
        DROP TABLE IF EXISTS card_registry;
        DROP TABLE IF EXISTS promotion_signals;
        DROP TABLE IF EXISTS official_evidence_index;
        DROP TABLE IF EXISTS earnings_calendar;
        DROP TABLE IF EXISTS analyst_snapshot;
        DROP TABLE IF EXISTS fundamental_snapshot;
        DROP TABLE IF EXISTS entry_stop_reference;
        DROP TABLE IF EXISTS latest_price_technical;
        DROP TABLE IF EXISTS ticker_family_status;
        DROP TABLE IF EXISTS ticker_tier;
        DROP TABLE IF EXISTS universe;
        DROP TABLE IF EXISTS source_run;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;

        CREATE TABLE source_run (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE,
            generated_at_utc TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_status TEXT NOT NULL,
            source_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE universe (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL,
            instrument_type TEXT,
            tier TEXT NOT NULL,
            monitoring_role TEXT,
            sector TEXT,
            industry TEXT,
            decision_grade_eligible INTEGER NOT NULL,
            promotion_required_before_action INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            owner_note_path TEXT,
            universe_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE ticker_tier (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            tier TEXT NOT NULL,
            monitoring_cadence_json TEXT NOT NULL,
            data_requirements_json TEXT NOT NULL,
            promotion_triggers_json TEXT NOT NULL,
            demotion_triggers_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE ticker_family_status (
            ticker TEXT NOT NULL REFERENCES universe(ticker) ON DELETE CASCADE,
            family_id TEXT NOT NULL,
            status TEXT NOT NULL,
            missing_count INTEGER NOT NULL,
            stale_count INTEGER NOT NULL,
            source_required INTEGER NOT NULL,
            source_paths_json TEXT NOT NULL,
            PRIMARY KEY (ticker, family_id)
        ) STRICT;

        CREATE TABLE pilot_fixture_registry (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT NOT NULL,
            instrument_type TEXT,
            monitoring_role TEXT,
            sector TEXT,
            industry TEXT,
            pilot_status TEXT NOT NULL,
            production_answer_path_member INTEGER NOT NULL,
            decision_grade_eligible INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            thin_row_only INTEGER NOT NULL,
            on_demand_card_required_before_claim INTEGER NOT NULL,
            provider_telemetry_required INTEGER NOT NULL,
            stale_but_known_disclosure_required INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE latest_price_technical (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            latest_known_price REAL,
            price_source TEXT,
            band_status TEXT,
            technical_summary TEXT,
            technical_status TEXT,
            source_path TEXT,
            fresh_quote_required INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE entry_stop_reference (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            entry_band_low REAL,
            entry_band_high REAL,
            stop_or_invalidation REAL,
            band_source TEXT,
            stop_source TEXT,
            freshness_status TEXT,
            validation_status TEXT,
            owner_note_path TEXT,
            source_artifact_path TEXT,
            source_artifact_hash TEXT,
            source_timestamp TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE fundamental_snapshot (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            valuation_status TEXT,
            key_metrics_status TEXT,
            latest_earnings_status TEXT,
            source_path TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE analyst_snapshot (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            status TEXT,
            rating_summary TEXT,
            price_target_summary TEXT,
            source_path TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE earnings_calendar (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            catalyst_status TEXT,
            latest_earnings_status TEXT,
            next_earnings_date TEXT,
            source_path TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE official_evidence_index (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL REFERENCES universe(ticker) ON DELETE CASCADE,
            evidence_family TEXT NOT NULL,
            status TEXT,
            source_path TEXT,
            source_open_required INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE promotion_signals (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            recommendation_posture TEXT,
            recommendation_posture_key TEXT,
            support_level TEXT,
            actionability TEXT,
            pending_approval_count INTEGER NOT NULL,
            blockers_json TEXT NOT NULL,
            missing_or_stale_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE card_registry (
            ticker TEXT PRIMARY KEY REFERENCES universe(ticker) ON DELETE CASCADE,
            card_path TEXT NOT NULL,
            card_exists INTEGER NOT NULL,
            card_generated_at_utc TEXT,
            card_schema_version INTEGER,
            review_only INTEGER NOT NULL,
            source_open_required INTEGER NOT NULL,
            authority_forbidden_true_json TEXT NOT NULL,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE validation_results (
            check_name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            detail_json TEXT NOT NULL
        ) STRICT;

        CREATE VIEW current_ticker_cards AS
            SELECT u.ticker, u.name, u.tier, u.monitoring_role, u.sector, u.instrument_type,
                   l.latest_known_price, l.band_status,
                   e.entry_band_low, e.entry_band_high, e.stop_or_invalidation,
                   p.recommendation_posture, p.recommendation_posture_key, p.actionability,
                   c.card_path, c.card_generated_at_utc, c.source_open_required,
                   c.authority_forbidden_true_json
            FROM universe u
            LEFT JOIN latest_price_technical l ON l.ticker = u.ticker
            LEFT JOIN entry_stop_reference e ON e.ticker = u.ticker
            LEFT JOIN promotion_signals p ON p.ticker = u.ticker
            LEFT JOIN card_registry c ON c.ticker = u.ticker
            WHERE u.active = 1;

        CREATE VIEW latest_valid_entry_stop_refs AS
            SELECT *
            FROM entry_stop_reference
            WHERE validation_status = 'ok'
              AND freshness_status IN ('fresh', 'current')
              AND entry_band_low IS NOT NULL
              AND entry_band_high IS NOT NULL;

        CREATE VIEW stale_ticker_cards AS
            SELECT c.ticker, c.card_path, p.missing_or_stale_json, p.blockers_json
            FROM card_registry c
            JOIN promotion_signals p ON p.ticker = c.ticker
            WHERE p.missing_or_stale_json != '[]'
               OR p.blockers_json LIKE '%stale%';

        CREATE VIEW pending_approval_queue AS
            SELECT u.ticker, u.tier, u.monitoring_role, p.recommendation_posture,
                   p.support_level, p.pending_approval_count, p.blockers_json
            FROM universe u
            JOIN promotion_signals p ON p.ticker = u.ticker
            WHERE p.pending_approval_count > 0
               OR p.recommendation_posture_key IN ('approval_ready_if_fresh', 'promotion_review', 'deployable_now')
            ORDER BY CASE u.tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END, u.ticker;

        CREATE VIEW latest_validator_status AS
            SELECT check_name, status, severity, detail_json
            FROM validation_results
            ORDER BY severity DESC, check_name;

        CREATE VIEW current_pilot_fixtures AS
            SELECT *
            FROM pilot_fixture_registry
            WHERE production_answer_path_member = 0
              AND decision_grade_eligible = 0
              AND thin_row_only = 1
              AND on_demand_card_required_before_claim = 1
            ORDER BY ticker;

        CREATE VIEW artifact_provenance_map AS
            SELECT ticker, 'card' AS source_kind, card_path AS source_path, card_generated_at_utc AS generated_at_utc
            FROM card_registry
            UNION ALL
            SELECT ticker, 'entry_stop_reference' AS source_kind, source_artifact_path AS source_path, source_timestamp AS generated_at_utc
            FROM entry_stop_reference
            UNION ALL
            SELECT ticker, evidence_family AS source_kind, source_path, NULL AS generated_at_utc
            FROM official_evidence_index;

        CREATE VIEW canon_conflict_candidates AS
            SELECT e.ticker, e.entry_band_low, e.entry_band_high, e.stop_or_invalidation,
                   e.freshness_status, e.validation_status, e.owner_note_path
            FROM entry_stop_reference e
            WHERE e.validation_status != 'ok'
               OR e.freshness_status NOT IN ('fresh', 'current')
               OR e.owner_note_path IS NULL
               OR e.owner_note_path = '';

        CREATE VIEW preopen_action_queue AS
            SELECT c.*
            FROM current_ticker_cards c
            WHERE c.tier IN ('A', 'B')
              AND c.recommendation_posture_key NOT IN ('reject_defer')
            ORDER BY
              CASE c.recommendation_posture_key
                WHEN 'approval_ready_if_fresh' THEN 1
                WHEN 'deployable_now' THEN 2
                WHEN 'promotion_review' THEN 3
                WHEN 'no_chase' THEN 4
                ELSE 5
              END,
              CASE c.tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
              c.ticker;

        CREATE INDEX idx_universe_tier ON universe(tier, ticker);
        CREATE INDEX idx_family_status_family ON ticker_family_status(family_id, status);
        CREATE INDEX idx_price_band_status ON latest_price_technical(band_status);
        CREATE INDEX idx_promotion_posture ON promotion_signals(recommendation_posture_key);
        CREATE INDEX idx_entry_stop_valid ON entry_stop_reference(validation_status, freshness_status);
        """
    )


def build_state(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    generated_at = utc_now()
    run_id = f"wf78-phase2-state-{generated_at.replace(':', '').replace('-', '')}"
    universe = as_dict(load_json(UNIVERSE_PATH, {}))
    coverage = as_dict(load_json(COVERAGE_PATH, {}))
    coverage_by_ticker = as_dict(coverage.get("ticker_coverage"))
    router_qa = as_dict(load_json(ROUTER_QA_PATH, {}))
    canon_cache = canon_cache_rows()
    entries = [
        row for row in as_list(universe.get("entries"))
        if isinstance(row, dict)
        and row.get("ticker")
        and row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE
    ]
    pilot_entries = [
        row for row in as_list(universe.get("entries"))
        if isinstance(row, dict)
        and row.get("ticker")
        and row.get("universe_scope") == PILOT_SCOPE
    ]

    with connect(db_path) as conn:
        init_schema(conn)
        conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.execute("INSERT INTO meta(key, value) VALUES ('generated_at_utc', ?)", (generated_at,))
        conn.execute("INSERT INTO meta(key, value) VALUES ('authority_boundary', ?)", (json_text(authority_boundary()),))
        for source_name, path in [
            ("universe", UNIVERSE_PATH),
            ("coverage", COVERAGE_PATH),
            ("router_qa", ROUTER_QA_PATH),
        ]:
            meta = source_meta(path)
            conn.execute(
                "INSERT INTO source_run(run_id, generated_at_utc, source_path, source_status, source_json) VALUES (?,?,?,?,?)",
                (f"{run_id}:{source_name}", generated_at, meta["path"], "present" if meta.get("exists") else "missing", json_text(meta)),
            )
        for entry in pilot_entries:
            ticker = str(entry["ticker"]).upper()
            coverage_reason = as_dict(entry.get("coverage_reason"))
            conn.execute(
                """
                INSERT INTO pilot_fixture_registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticker,
                    entry.get("name"),
                    entry.get("tier") or "D",
                    entry.get("instrument_type"),
                    entry.get("monitoring_role"),
                    entry.get("sector"),
                    entry.get("industry"),
                    entry.get("pilot_status") or "fixture_only_not_in_production_answer_path",
                    1 if coverage_reason.get("production_answer_path_member") else 0,
                    1 if entry.get("decision_grade_eligible") else 0,
                    1 if entry.get("source_open_required") else 0,
                    1,
                    1,
                    1,
                    1,
                    json_text(entry),
                ),
            )
        for entry in entries:
            ticker = str(entry["ticker"]).upper()
            card = as_dict(load_json(card_path(ticker), {}))
            card_meta = source_meta(card_path(ticker))
            universe_auth = as_dict(entry.get("authority_boundary"))
            card_auth = as_dict(card.get("authority_boundary"))
            forbidden = authority_forbidden_true(universe_auth, card_auth)
            price = as_dict(card.get("price_band_stop"))
            tech = as_dict(card.get("technical_posture"))
            reco = as_dict(card.get("recommendation_support"))
            missing_or_stale = as_list(card.get("missing_or_stale_evidence"))
            coverage_row = as_dict(coverage_by_ticker.get(ticker))
            families = as_dict(coverage_row.get("families"))
            source_paths = sorted({item.get("path") for item in as_list(card.get("source_artifacts")) if isinstance(item, dict) and item.get("path")})

            conn.execute(
                """
                INSERT INTO universe VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ticker, entry.get("name"), 1 if entry.get("active") is not False else 0,
                    entry.get("instrument_type"), entry.get("tier") or "D",
                    entry.get("monitoring_role"), entry.get("sector"), entry.get("industry"),
                    1 if entry.get("decision_grade_eligible") else 0,
                    1 if entry.get("promotion_required_before_action") else 0,
                    1 if entry.get("source_open_required") else 0,
                    entry.get("owner_note_path") or "04. Research/Coverage and Watchlist.md",
                    json_text(entry),
                ),
            )
            conn.execute(
                "INSERT INTO ticker_tier VALUES (?,?,?,?,?,?)",
                (
                    ticker, entry.get("tier") or "D",
                    json_text(entry.get("monitoring_cadence") or {}),
                    json_text(entry.get("data_requirements") or {}),
                    json_text(entry.get("promotion_triggers") or []),
                    json_text(entry.get("demotion_triggers") or []),
                ),
            )
            for family_id, status in families.items():
                if not isinstance(status, dict):
                    continue
                conn.execute(
                    "INSERT INTO ticker_family_status VALUES (?,?,?,?,?,?,?)",
                    (
                        ticker, family_id, status.get("status") or "unknown",
                        len(as_list(status.get("missing_sources"))),
                        len(as_list(status.get("stale_sources"))),
                        1 if status.get("source_open_required_for_claims", True) else 0,
                        json_text(status.get("source_paths") or []),
                    ),
                )
            conn.execute(
                "INSERT INTO latest_price_technical VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ticker, fnum(price.get("latest_known_price")), price.get("price_source"),
                    price.get("band_status"), tech.get("summary") or tech.get("status"),
                    tech.get("status"), price.get("price_source") or "tmp/ticker-intelligence-cards",
                    1 if price.get("fresh_quote_required", True) else 0,
                    json_text({"price_band_stop": price, "technical_posture": tech}),
                ),
            )

            canon_low = canon_value(canon_cache, ticker, "reference_price_low")
            canon_high = canon_value(canon_cache, ticker, "reference_price_high")
            canon_stop = canon_value(canon_cache, ticker, "reference_invalidation_level")
            canon_owner = canon_value(canon_cache, ticker, "reference_level_owner_source_path")
            canon_hash = canon_value(canon_cache, ticker, "reference_level_source_sha256")
            canon_ts = canon_value(canon_cache, ticker, "reference_level_source_timestamp")
            freshness = canon_low.get("freshness_status") or "missing"
            validator = canon_low.get("validator_status") or "missing"
            conn.execute(
                "INSERT INTO entry_stop_reference VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ticker,
                    fnum(canon_low.get("field_value") if canon_low else price.get("entry_band_low")),
                    fnum(canon_high.get("field_value") if canon_high else price.get("entry_band_high")),
                    fnum(canon_stop.get("field_value") if canon_stop else price.get("stop_or_invalidation")),
                    price.get("band_source") or canon_low.get("source_artifact_path"),
                    price.get("stop_source") or canon_stop.get("source_artifact_path"),
                    freshness,
                    validator,
                    canon_owner.get("field_value") or canon_low.get("owner_mirror_note_path"),
                    canon_low.get("source_artifact_path"),
                    canon_hash.get("field_value") or canon_low.get("source_artifact_hash"),
                    canon_ts.get("field_value"),
                    json_text({"card_price_band_stop": price, "canon_cache_rows": {
                        "low": canon_low, "high": canon_high, "stop": canon_stop,
                    }}),
                ),
            )
            conn.execute(
                "INSERT INTO fundamental_snapshot VALUES (?,?,?,?,?,?)",
                (
                    ticker,
                    as_dict(card.get("valuation")).get("status"),
                    as_dict(card.get("key_financial_metrics")).get("status"),
                    as_dict(card.get("latest_earnings_performance")).get("status"),
                    "tmp/ticker-intelligence-cards",
                    json_text({
                        "valuation": card.get("valuation"),
                        "key_financial_metrics": card.get("key_financial_metrics"),
                        "latest_earnings_performance": card.get("latest_earnings_performance"),
                    }),
                ),
            )
            analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
            conn.execute(
                "INSERT INTO analyst_snapshot VALUES (?,?,?,?,?,?)",
                (
                    ticker, analyst.get("status"),
                    analyst.get("rating_summary") or analyst.get("consensus_rating"),
                    analyst.get("price_target_summary") or analyst.get("price_target"),
                    "tmp/analyst-consensus-current.json",
                    json_text(analyst),
                ),
            )
            catalyst = as_dict(card.get("catalyst_earnings_state"))
            latest_earnings = as_dict(card.get("latest_earnings_performance"))
            conn.execute(
                "INSERT INTO earnings_calendar VALUES (?,?,?,?,?,?)",
                (
                    ticker, catalyst.get("status"), latest_earnings.get("status"),
                    catalyst.get("next_earnings_date") or latest_earnings.get("next_earnings_date"),
                    "tmp/official-earnings-bridge.json",
                    json_text({"catalyst_earnings_state": catalyst, "latest_earnings_performance": latest_earnings}),
                ),
            )
            for family, payload in [
                ("competitive_moat", card.get("competitive_moat")),
                ("recent_developments", card.get("recent_developments")),
                ("orders_backlog_book_to_bill", card.get("orders_backlog_book_to_bill")),
                ("official_capture_developments_orders_backlog", card.get("official_capture_developments_orders_backlog")),
            ]:
                conn.execute(
                    "INSERT INTO official_evidence_index(ticker, evidence_family, status, source_path, source_open_required, raw_json) VALUES (?,?,?,?,?,?)",
                    (
                        ticker, family, as_dict(payload).get("status"),
                        "tmp/official-earnings-bridge.json",
                        1,
                        json_text(payload or {}),
                    ),
                )
            blockers = as_list(reco.get("blockers_or_gates"))
            posture_key = str(reco.get("posture_key") or "")
            pending_approval_count = 1 if posture_key in {"approval_ready_if_fresh", "promotion_review", "deployable_now"} else 0
            conn.execute(
                "INSERT INTO promotion_signals VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ticker, reco.get("posture"), reco.get("posture_key"),
                    reco.get("support_level"), reco.get("actionability"),
                    pending_approval_count,
                    json_text(blockers), json_text(missing_or_stale),
                    json_text(reco),
                ),
            )
            conn.execute(
                "INSERT INTO card_registry VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ticker, rel(card_path(ticker)), 1 if card_path(ticker).exists() else 0,
                    card.get("generated_at_utc") or card_meta.get("generated_at_utc"),
                    int(card.get("schema_version") or 0),
                    1 if card.get("review_only", True) else 0,
                    1 if card_auth.get("source_open_required_before_final_recommendation_or_action_claim", True) else 0,
                    json_text(forbidden),
                    json_text({"card_source_paths": source_paths, "card": card}),
                ),
            )

        validation = validate_db(conn, expected_tickers=len(entries), router_qa=router_qa)
        for check in validation["checks"]:
            conn.execute(
                "INSERT INTO validation_results VALUES (?,?,?,?)",
                (check["name"], "ok" if check["ok"] else "fail", check["severity"], json_text(check.get("detail"))),
            )
        conn.execute("PRAGMA optimize")

    return validate_state(db_path)


def authority_boundary() -> dict[str, Any]:
    return {
        "review_only": True,
        "database_path": rel(DEFAULT_DB),
        "database_path_migration_performed": False,
        "tmp_database_promotion_performed": False,
        "full_sql_canon_migration_allowed": False,
        "sql_canon_authority_expanded": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "paper_trade_execution_allowed": False,
        "live_trade_or_account_action_allowed": False,
        "source_open_required_before_finance_claims": True,
    }


def paper_position_authority_boundary(paper_db_path: Path) -> dict[str, Any]:
    boundary = authority_boundary()
    boundary["database_path"] = rel(paper_db_path)
    boundary["paper_position_sql_state_only"] = True
    boundary["paper_order_execution_allowed"] = False
    boundary["paper_order_submit_allowed_by_this_registry"] = False
    boundary["paper_order_cancel_allowed_by_this_registry"] = False
    boundary["trade_or_account_action_allowed"] = False
    boundary["canon_cache_used_for_paper_positions"] = False
    boundary["artifact_index_is_state_owner"] = False
    return boundary


def validate_db(conn: sqlite3.Connection, expected_tickers: int, router_qa: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "", severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    integrity = scalar(conn, "PRAGMA integrity_check")
    fk_rows = rows(conn, "PRAGMA foreign_key_check")
    add("integrity_check_ok", integrity == "ok", integrity)
    add("foreign_key_check_ok", len(fk_rows) == 0, {"rows": len(fk_rows)})
    add("universe_count_matches_expected", scalar(conn, "SELECT COUNT(*) FROM universe") == expected_tickers, {"expected": expected_tickers, "actual": scalar(conn, "SELECT COUNT(*) FROM universe")})
    add("current_42_present", scalar(conn, "SELECT COUNT(*) FROM current_ticker_cards") == EXPECTED_CURRENT_TICKERS, {"actual": scalar(conn, "SELECT COUNT(*) FROM current_ticker_cards")})
    add("cards_exist_for_all_universe_rows", scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE card_exists=0") == 0, {"missing": scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE card_exists=0")})
    add("entry_stop_rows_for_all_tickers", scalar(conn, "SELECT COUNT(*) FROM entry_stop_reference") == expected_tickers, {"actual": scalar(conn, "SELECT COUNT(*) FROM entry_stop_reference")})
    add("latest_valid_entry_stop_refs_42", scalar(conn, "SELECT COUNT(*) FROM latest_valid_entry_stop_refs") == EXPECTED_CURRENT_TICKERS, {"actual": scalar(conn, "SELECT COUNT(*) FROM latest_valid_entry_stop_refs")})
    add("pilot_fixtures_excluded_from_production_cards", scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")})
    add("pilot_fixtures_thin_on_demand_only", scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE production_answer_path_member!=0 OR decision_grade_eligible!=0 OR thin_row_only!=1 OR on_demand_card_required_before_claim!=1") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE production_answer_path_member!=0 OR decision_grade_eligible!=0 OR thin_row_only!=1 OR on_demand_card_required_before_claim!=1")})
    add("no_forbidden_authority_in_cards", scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json!='[]'") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json!='[]'")})
    add("router_qa_pass", router_qa.get("status") == "pass", router_qa.get("summary"))
    add("source_open_required_all_cards", scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE source_open_required=0") == 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM card_registry WHERE source_open_required=0")})
    add("preopen_action_queue_has_rows", scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue") > 0, {"rows": scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue")}, "warning")
    status = "ok" if all(check["ok"] or check["severity"] == "warning" for check in checks) and not [c for c in checks if not c["ok"] and c["severity"] == "error"] else "blocked"
    return {"status": status, "checks": checks}


def validate_state(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        router_qa = as_dict(load_json(ROUTER_QA_PATH, {}))
        validation = validate_db(conn, EXPECTED_CURRENT_TICKERS, router_qa)
        summary = {
            "universe_rows": scalar(conn, "SELECT COUNT(*) FROM universe"),
            "current_ticker_cards": scalar(conn, "SELECT COUNT(*) FROM current_ticker_cards"),
            "latest_valid_entry_stop_refs": scalar(conn, "SELECT COUNT(*) FROM latest_valid_entry_stop_refs"),
            "stale_ticker_cards": scalar(conn, "SELECT COUNT(*) FROM stale_ticker_cards"),
            "pending_approval_queue": scalar(conn, "SELECT COUNT(*) FROM pending_approval_queue"),
            "preopen_action_queue": scalar(conn, "SELECT COUNT(*) FROM preopen_action_queue"),
            "pilot_fixture_rows": scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry"),
            "current_pilot_fixtures": scalar(conn, "SELECT COUNT(*) FROM current_pilot_fixtures"),
            "canon_conflict_candidates": scalar(conn, "SELECT COUNT(*) FROM canon_conflict_candidates"),
        }
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": "finance_intelligence_state_validation",
        "db_path": rel(db_path),
        "status": validation["status"],
        "summary": summary,
        "authority_boundary": authority_boundary(),
        "checks": validation["checks"],
    }
    atomic_write_json(DEFAULT_VALIDATION, report)
    return report


def ticker_packet(ticker: str, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    ticker = ticker.upper()
    with connect_ro(db_path) as conn:
        current = rows(conn, "SELECT * FROM current_ticker_cards WHERE ticker=?", (ticker,))
        if not current:
            return {"status": "missing", "ticker": ticker, "db_path": rel(db_path)}
        packet = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "artifact_type": "finance_intelligence_state_ticker_packet",
            "status": "ok",
            "ticker": ticker,
            "db_path": rel(db_path),
            "current": current[0],
            "family_status": rows(conn, "SELECT * FROM ticker_family_status WHERE ticker=? ORDER BY family_id", (ticker,)),
            "entry_stop_reference": rows(conn, "SELECT * FROM entry_stop_reference WHERE ticker=?", (ticker,))[0],
            "provenance": rows(conn, "SELECT * FROM artifact_provenance_map WHERE ticker=? ORDER BY source_kind, source_path", (ticker,)),
            "authority_boundary": authority_boundary(),
            "answer_contract": {
                "may_answer_from_sql_for_inventory_or_routing": True,
                "material_finance_claim_requires_source_open": True,
                "must_not_infer_approval_or_execution_authority": True,
                "must_state_missing_or_stale_evidence": True,
            },
        }
    atomic_write_json(DEFAULT_TICKER_PACKET, packet)
    return packet


def preopen_packet(db_path: Path = DEFAULT_DB, limit: int = 20) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        queue = rows(conn, "SELECT * FROM preopen_action_queue LIMIT ?", (limit,))
        stale = rows(conn, "SELECT * FROM stale_ticker_cards ORDER BY ticker LIMIT ?", (limit,))
        pending = rows(conn, "SELECT * FROM pending_approval_queue LIMIT ?", (limit,))
        validation = rows(conn, "SELECT * FROM latest_validator_status")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "artifact_type": "finance_intelligence_state_preopen_packet",
        "status": "ok",
        "db_path": rel(db_path),
        "queue": queue,
        "stale_ticker_cards": stale,
        "pending_approval_queue": pending,
        "validator_status": validation,
        "authority_boundary": authority_boundary(),
        "source_open_rule": "Use this compact SQL packet for routing/current-state triage only; open listed source artifacts and canonical owner notes before material finance claims.",
    }
    atomic_write_json(DEFAULT_PREOPEN_PACKET, packet)
    return packet


def stale_tickers_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        stale_rows = rows(conn, "SELECT * FROM stale_ticker_cards ORDER BY ticker LIMIT ?", (limit,))
    normalized = []
    for row in stale_rows:
        row = dict(row)
        row["missing_or_stale"] = parse_json_text(row.pop("missing_or_stale_json", "[]"), [])
        row["blockers"] = parse_json_text(row.pop("blockers_json", "[]"), [])
        normalized.append(row)
    packet = {
        **packet_header("finance_intelligence_state_stale_tickers_packet", db_path),
        "status": "ok",
        "count": len(normalized),
        "stale_ticker_cards": normalized,
    }
    return write_packet(DEFAULT_STALE_PACKET, packet)


def pending_approvals_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        pending_rows = rows(conn, "SELECT * FROM pending_approval_queue LIMIT ?", (limit,))
    normalized = []
    for row in pending_rows:
        row = dict(row)
        row["blockers"] = parse_json_text(row.pop("blockers_json", "[]"), [])
        normalized.append(row)
    packet = {
        **packet_header("finance_intelligence_state_pending_approvals_packet", db_path),
        "status": "ok",
        "count": len(normalized),
        "pending_approval_queue": normalized,
        "review_boundary": "Rows are review/promotion/approval-prep routing only; they do not grant owner approval or execution authority.",
    }
    return write_packet(DEFAULT_PENDING_PACKET, packet)


def validator_status_packet(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        validator_rows = rows(conn, "SELECT * FROM latest_validator_status")
    normalized = []
    for row in validator_rows:
        row = dict(row)
        row["detail"] = parse_json_text(row.pop("detail_json", "{}"), {})
        normalized.append(row)
    error_failures = [row for row in normalized if row.get("severity") == "error" and row.get("status") != "ok"]
    packet = {
        **packet_header("finance_intelligence_state_validator_status_packet", db_path),
        "status": "ok" if not error_failures else "blocked",
        "error_failures": len(error_failures),
        "validator_status": normalized,
    }
    return write_packet(DEFAULT_VALIDATOR_PACKET, packet)


def source_proof_packet(ticker: str, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    ticker = ticker.upper()
    with connect_ro(db_path) as conn:
        proof_rows = rows(conn, "SELECT * FROM artifact_provenance_map WHERE ticker=? ORDER BY source_kind, source_path", (ticker,))
        owner_rows = rows(conn, "SELECT ticker, owner_note_path, source_artifact_path, source_artifact_hash, source_timestamp, freshness_status, validation_status FROM entry_stop_reference WHERE ticker=?", (ticker,))
        card_rows = rows(conn, "SELECT ticker, card_path, card_generated_at_utc, source_open_required FROM card_registry WHERE ticker=?", (ticker,))
    packet = {
        **packet_header("finance_intelligence_state_source_proof_packet", db_path),
        "status": "ok" if proof_rows else "missing",
        "ticker": ticker,
        "card": card_rows[0] if card_rows else None,
        "entry_stop_owner_proof": owner_rows[0] if owner_rows else None,
        "provenance": proof_rows,
        "source_open_rule": "Open the listed source artifact or owner note before making a material finance, readiness, recommendation, or authority claim.",
    }
    return write_packet(DEFAULT_SOURCE_PROOF_PACKET, packet)


def entry_stop_refs_packet(db_path: Path = DEFAULT_DB, ticker: str | None = None, limit: int = 100) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        if ticker:
            ref_rows = rows(conn, "SELECT * FROM latest_valid_entry_stop_refs WHERE ticker=? ORDER BY ticker LIMIT ?", (ticker.upper(), limit))
        else:
            ref_rows = rows(conn, "SELECT * FROM latest_valid_entry_stop_refs ORDER BY ticker LIMIT ?", (limit,))
    trimmed = [
        {
            "ticker": row["ticker"],
            "entry_band_low": row["entry_band_low"],
            "entry_band_high": row["entry_band_high"],
            "stop_or_invalidation": row["stop_or_invalidation"],
            "sql_first_reference_metadata": build_entry_stop_reference_metadata(row["ticker"]),
            "freshness_status": row["freshness_status"],
            "validation_status": row["validation_status"],
            "owner_note_path": row["owner_note_path"],
            "source_artifact_path": row["source_artifact_path"],
            "source_artifact_hash": row["source_artifact_hash"],
            "source_timestamp": row["source_timestamp"],
        }
        for row in ref_rows
    ]
    packet = {
        **packet_header("finance_intelligence_state_entry_stop_refs_packet", db_path),
        "status": "ok",
        "ticker": ticker.upper() if ticker else None,
        "count": len(trimmed),
        "sql_first_read_scope": "42-ticker entry/stop reference metadata only",
        "sql_first_consumer_migration_performed": True,
        "markdown_owner_fallback_required": True,
        "entry_stop_refs": trimmed,
        "cache_boundary": "Validated metadata/reference cache only; not recommendation, deployment, approval, or execution authority.",
    }
    return write_packet(DEFAULT_ENTRY_STOP_PACKET, packet)


def action_queue_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        queue = rows(conn, "SELECT * FROM preopen_action_queue LIMIT ?", (limit,))
    packet = {
        **packet_header("finance_intelligence_state_action_queue_packet", db_path),
        "status": "ok",
        "count": len(queue),
        "queue": queue,
        "queue_boundary": "Queue order is triage/routing only. It is not approval, sizing, cash/risk-rule, paper, live, or account authority.",
    }
    return write_packet(DEFAULT_ACTION_QUEUE_PACKET, packet)


def pilot_fixtures_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    with connect_ro(db_path) as conn:
        fixtures = rows(conn, "SELECT * FROM current_pilot_fixtures LIMIT ?", (limit,))
        production_overlap = scalar(conn, "SELECT COUNT(*) FROM pilot_fixture_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
    trimmed = [
        {
            "ticker": row["ticker"],
            "name": row["name"],
            "tier": row["tier"],
            "instrument_type": row["instrument_type"],
            "monitoring_role": row["monitoring_role"],
            "sector": row["sector"],
            "industry": row["industry"],
            "pilot_status": row["pilot_status"],
            "thin_row_only": bool(row["thin_row_only"]),
            "on_demand_card_required_before_claim": bool(row["on_demand_card_required_before_claim"]),
            "provider_telemetry_required": bool(row["provider_telemetry_required"]),
            "stale_but_known_disclosure_required": bool(row["stale_but_known_disclosure_required"]),
        }
        for row in fixtures
    ]
    packet = {
        **packet_header("finance_intelligence_state_pilot_fixtures_packet", db_path),
        "status": "ok" if trimmed and production_overlap == 0 else "blocked",
        "count": len(trimmed),
        "production_overlap_count": production_overlap,
        "pilot_fixtures": trimmed,
        "pilot_boundary": {
            "thin_sql_rows_only": True,
            "on_demand_cards_required_before_material_claims": True,
            "excluded_from_current_42_production_cards": production_overlap == 0,
            "provider_telemetry_required_before_live_pilot": True,
            "no_broad_import_or_production_overwrite": True,
        },
    }
    return write_packet(DEFAULT_PILOT_FIXTURE_PACKET, packet)


def live_pilot_packet(db_path: Path = DEFAULT_DB, limit: int = 50) -> dict[str, Any]:
    if not db_path.exists():
        packet = {
            **packet_header("finance_intelligence_state_live_pilot_packet", db_path),
            "status": "missing",
            "count": 0,
            "candidates": [],
            "validation": {
                "status": "blocked",
                "checks": [{"name": "finance_intelligence_state_db_present", "ok": False, "severity": "error", "detail": rel(db_path)}],
            },
        }
        return write_packet(DEFAULT_LIVE_PILOT_PACKET, packet)

    with connect_ro(db_path) as conn:
        live_view_exists = scalar(conn, "SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name='current_live_pilot_candidates'")
        if not live_view_exists:
            packet = {
                **packet_header("finance_intelligence_state_live_pilot_packet", db_path),
                "status": "missing",
                "count": 0,
                "candidates": [],
                "validation": {
                    "status": "blocked",
                    "checks": [{"name": "current_live_pilot_candidates_view_present", "ok": False, "severity": "error", "detail": "view missing"}],
                },
                "live_pilot_boundary": {
                    "isolated_sql_surface_only": True,
                    "production_42_answer_path_unchanged": True,
                    "material_claim_requires_source_open": True,
                },
            }
            return write_packet(DEFAULT_LIVE_PILOT_PACKET, packet)
        candidates = rows(conn, "SELECT * FROM current_live_pilot_candidates LIMIT ?", (limit,))
        candidate_count = scalar(conn, "SELECT COUNT(*) FROM current_live_pilot_candidates")
        provider_ok = scalar(conn, "SELECT COUNT(*) FROM live_pilot_provider_status WHERE provider_status='ok'")
        production_overlap = scalar(conn, "SELECT COUNT(*) FROM live_pilot_candidate_registry WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
        bad_authority = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM live_pilot_candidate_registry
            WHERE production_answer_path_member != 0
               OR decision_grade_eligible != 0
               OR source_open_required != 1
               OR thin_row_only != 1
               OR on_demand_card_required_before_claim != 1
            """,
        )
    checks = [
        {"name": "live_pilot_rows_present", "ok": candidate_count > 0, "severity": "error", "detail": {"rows": candidate_count}},
        {"name": "live_pilot_rows_isolated_from_production", "ok": production_overlap == 0, "severity": "error", "detail": {"rows": production_overlap}},
        {"name": "live_pilot_authority_flags_false", "ok": bad_authority == 0, "severity": "error", "detail": {"rows": bad_authority}},
        {"name": "live_pilot_provider_status_present", "ok": provider_ok > 0, "severity": "error", "detail": {"provider_ok": provider_ok}},
    ]
    failed = [check for check in checks if not check["ok"] and check["severity"] == "error"]
    packet = {
        **packet_header("finance_intelligence_state_live_pilot_packet", db_path),
        "status": "ok" if not failed else "blocked",
        "count": len(candidates),
        "total_count": candidate_count,
        "provider_ok_count": provider_ok,
        "production_overlap_count": production_overlap,
        "candidates": candidates,
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed_checks": failed},
        "live_pilot_boundary": {
            "isolated_sql_surface_only": True,
            "production_42_answer_path_unchanged": production_overlap == 0,
            "thin_or_on_demand_only": True,
            "material_claim_requires_source_open": True,
            "no_canon_portfolio_or_execution_authority": True,
        },
    }
    return write_packet(DEFAULT_LIVE_PILOT_PACKET, packet)


def paper_positions_packet(paper_db_path: Path = PAPER_POSITION_DB) -> dict[str, Any]:
    if not paper_db_path.exists():
        packet = {
            **packet_header("finance_intelligence_state_paper_positions_packet", paper_db_path),
            "authority_boundary": paper_position_authority_boundary(paper_db_path),
            "status": "missing",
            "freshness": {"status": "missing"},
            "account_summary": {},
            "positions": [],
            "validation": {
                "status": "blocked",
                "checks": [{"name": "paper_position_db_present", "ok": False, "severity": "error", "detail": rel(paper_db_path)}],
            },
            "paper_boundary": {
                "paper_position_sql_state_only": True,
                "no_paper_submit_cancel_sell_authority": True,
                "no_live_trade_or_account_authority": True,
                "json_markdown_exports_are_not_truth_owner": True,
            },
        }
        return write_packet(DEFAULT_PAPER_POSITIONS_PACKET, packet)

    try:
        with connect_ro(paper_db_path) as conn:
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
            position_rows = rows(conn, "SELECT * FROM current_paper_positions")
            integrity = scalar(conn, "PRAGMA integrity_check")
            fk_rows = rows(conn, "PRAGMA foreign_key_check")
            ok_snapshot_rows = scalar(conn, "SELECT COUNT(*) FROM paper_account_snapshot WHERE status='ok'")
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
    except sqlite3.Error as exc:
        packet = {
            **packet_header("finance_intelligence_state_paper_positions_packet", paper_db_path),
            "authority_boundary": paper_position_authority_boundary(paper_db_path),
            "status": "blocked",
            "freshness": {"status": "blocked"},
            "account_summary": {},
            "positions": [],
            "validation": {
                "status": "blocked",
                "checks": [{"name": "paper_position_db_readable", "ok": False, "severity": "error", "detail": type(exc).__name__}],
            },
        }
        return write_packet(DEFAULT_PAPER_POSITIONS_PACKET, packet)

    latest = latest_rows[0] if latest_rows else {}
    latest_ok = latest_ok_rows[0] if latest_ok_rows else {}
    summary = latest_ok if latest.get("status") == "blocked" and latest_ok else latest
    last_known_positions_status = "current" if latest.get("status") == "ok" else ("stale_but_known" if latest_ok else "unavailable")
    checks = [
        {"name": "integrity_check_ok", "ok": integrity == "ok", "severity": "error", "detail": integrity},
        {"name": "foreign_key_check_ok", "ok": len(fk_rows) == 0, "severity": "error", "detail": {"rows": len(fk_rows)}},
        {"name": "paper_snapshot_present", "ok": bool(latest_rows), "severity": "error", "detail": {"rows": len(latest_rows)}},
        {"name": "ok_snapshot_available_for_current_positions", "ok": ok_snapshot_rows >= 1 or latest.get("status") == "blocked", "severity": "warning", "detail": {"rows": ok_snapshot_rows}},
        {"name": "forbidden_authority_flags_false", "ok": forbidden_rows == 0, "severity": "error", "detail": {"rows": forbidden_rows}},
        {
            "name": "paper_position_freshness_fresh",
            "ok": latest.get("freshness_status") == "fresh",
            "severity": "warning",
            "detail": {"freshness_status": latest.get("freshness_status"), "generated_at_utc": latest.get("generated_at_utc")},
        },
    ]
    validation_status = "ok" if not [check for check in checks if not check["ok"] and check["severity"] == "error"] else "blocked"
    packet = {
        **packet_header("finance_intelligence_state_paper_positions_packet", paper_db_path),
        "authority_boundary": paper_position_authority_boundary(paper_db_path),
        "status": "ok" if validation_status == "ok" and latest.get("status") == "ok" else latest.get("status", validation_status),
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
            "status": latest.get("status", validation_status),
            "generated_at_utc": latest.get("generated_at_utc"),
            "validation_findings": parse_json_text(latest.get("validation_findings_json"), []),
        },
        "account_summary": {
            "account_mode": summary.get("account_mode"),
            "endpoint": summary.get("endpoint"),
            "method": summary.get("method"),
            "equity": summary.get("equity"),
            "cash": summary.get("cash"),
            "buying_power": summary.get("buying_power"),
            "portfolio_value": summary.get("portfolio_value"),
            "positions_count": summary.get("positions_count"),
            "orders_count": summary.get("orders_count"),
            "open_orders_count": summary.get("open_orders_count"),
            "last_successful_snapshot_id": latest_ok.get("snapshot_id"),
            "last_successful_snapshot_at_utc": latest_ok.get("generated_at_utc"),
        },
        "positions": position_rows,
        "validation": {"status": validation_status, "checks": checks},
        "paper_boundary": {
            "paper_position_sql_state_only": True,
            "no_paper_submit_cancel_sell_authority": True,
            "no_live_trade_or_account_authority": True,
            "no_owner_approval_inference": True,
            "json_markdown_exports_are_not_truth_owner": True,
            "canon_cache_used_for_paper_positions": False,
            "artifact_index_is_state_owner": False,
        },
        "source_open_rule": "Use this packet for paper-position routing/current-state only. Stale, missing, or blocked freshness must be disclosed before paper-advisor context.",
    }
    return write_packet(DEFAULT_PAPER_POSITIONS_PACKET, packet)


def phase3_qc_packet(db_path: Path = DEFAULT_DB, sample_tickers: list[str] | None = None) -> dict[str, Any]:
    sample_tickers = [ticker.upper() for ticker in (sample_tickers or ["ETN", "VRT", "NVDA", "CME"])]
    validation = validate_state(db_path)
    samples = {ticker: ticker_packet(ticker, db_path) for ticker in sample_tickers}
    preopen = preopen_packet(db_path, limit=10)
    stale = stale_tickers_packet(db_path, limit=10)
    pending = pending_approvals_packet(db_path, limit=20)
    validators = validator_status_packet(db_path)
    entry_refs = entry_stop_refs_packet(db_path, limit=50)
    pilot_fixtures = pilot_fixtures_packet(db_path, limit=50)
    source_proofs = {ticker: source_proof_packet(ticker, db_path) for ticker in sample_tickers}

    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "", severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    add("state_validation_ok", validation.get("status") == "ok", validation.get("summary"))
    add("sample_ticker_packets_ok", all(packet.get("status") == "ok" for packet in samples.values()), {ticker: packet.get("status") for ticker, packet in samples.items()})
    add("sample_packets_source_open_required", all(packet.get("answer_contract", {}).get("material_finance_claim_requires_source_open") is True for packet in samples.values()))
    add("preopen_packet_ok", preopen.get("status") == "ok" and len(preopen.get("queue") or []) > 0, {"rows": len(preopen.get("queue") or [])})
    add("pending_packet_ok", pending.get("status") == "ok", {"rows": pending.get("count")})
    add("validator_packet_ok", validators.get("status") == "ok", {"error_failures": validators.get("error_failures")})
    add("entry_stop_refs_complete", entry_refs.get("count") == EXPECTED_CURRENT_TICKERS, {"rows": entry_refs.get("count")})
    add("pilot_fixtures_packet_ok", pilot_fixtures.get("status") == "ok", {"rows": pilot_fixtures.get("count"), "production_overlap_count": pilot_fixtures.get("production_overlap_count")})
    add("source_proof_packets_ok", all(packet.get("status") == "ok" for packet in source_proofs.values()), {ticker: packet.get("status") for ticker, packet in source_proofs.items()})

    all_packets = [validation, preopen, stale, pending, validators, entry_refs, pilot_fixtures, *samples.values(), *source_proofs.values()]
    forbidden_flags = [
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "owner_approval_inferred",
        "paper_trade_execution_allowed",
        "live_trade_or_account_action_allowed",
        "full_sql_canon_migration_allowed",
        "sql_canon_authority_expanded",
        "tmp_database_promotion_performed",
        "database_path_migration_performed",
    ]
    forbidden_true = []
    for packet in all_packets:
        boundary = as_dict(packet.get("authority_boundary"))
        for flag in forbidden_flags:
            if boundary.get(flag) is True:
                forbidden_true.append({"artifact_type": packet.get("artifact_type"), "flag": flag})
    add("all_query_packets_preserve_forbidden_authority_false", not forbidden_true, forbidden_true)
    status = "ok" if all(check["ok"] or check["severity"] == "warning" for check in checks) and not [c for c in checks if not c["ok"] and c["severity"] == "error"] else "blocked"
    packet = {
        **packet_header("finance_intelligence_state_phase3_qc", db_path),
        "status": status,
        "phase": "WF78 Phase 3",
        "sample_tickers": sample_tickers,
        "checks": checks,
        "generated_packets": {
            "validation": rel(DEFAULT_VALIDATION),
            "ticker_packet": rel(DEFAULT_TICKER_PACKET),
            "preopen": rel(DEFAULT_PREOPEN_PACKET),
            "stale_tickers": rel(DEFAULT_STALE_PACKET),
            "pending_approvals": rel(DEFAULT_PENDING_PACKET),
            "validator_status": rel(DEFAULT_VALIDATOR_PACKET),
            "source_proof": rel(DEFAULT_SOURCE_PROOF_PACKET),
            "entry_stop_refs": rel(DEFAULT_ENTRY_STOP_PACKET),
            "action_queue": rel(DEFAULT_ACTION_QUEUE_PACKET),
            "pilot_fixtures": rel(DEFAULT_PILOT_FIXTURE_PACKET),
            "live_pilot": rel(DEFAULT_LIVE_PILOT_PACKET),
            "paper_positions": rel(DEFAULT_PAPER_POSITIONS_PACKET),
        },
        "scope_boundary": "Read-only query surface over existing WF78 SQL current-state prototype. No database path move, no tmp promotion, no full SQL-canon migration, no authority expansion.",
    }
    return write_packet(DEFAULT_PHASE3_QC, packet)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "build", "validate", "ticker", "preopen", "stale-tickers",
            "pending-approvals", "validator-status", "source-proof",
            "entry-stop-refs", "action-queue", "pilot-fixtures", "live-pilot", "phase3-qc", "paper-positions",
        ],
    )
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sample-tickers", default="ETN,VRT,NVDA,CME")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.command == "build":
        result = build_state(db_path)
    elif args.command == "validate":
        result = validate_state(db_path)
    elif args.command == "ticker":
        if not args.ticker:
            parser.error("ticker command requires a ticker")
        result = ticker_packet(args.ticker, db_path)
    elif args.command == "preopen":
        result = preopen_packet(db_path, args.limit)
    elif args.command == "stale-tickers":
        result = stale_tickers_packet(db_path, args.limit)
    elif args.command == "pending-approvals":
        result = pending_approvals_packet(db_path, args.limit)
    elif args.command == "validator-status":
        result = validator_status_packet(db_path)
    elif args.command == "source-proof":
        if not args.ticker:
            parser.error("source-proof command requires a ticker")
        result = source_proof_packet(args.ticker, db_path)
    elif args.command == "entry-stop-refs":
        result = entry_stop_refs_packet(db_path, args.ticker, args.limit)
    elif args.command == "action-queue":
        result = action_queue_packet(db_path, args.limit)
    elif args.command == "pilot-fixtures":
        result = pilot_fixtures_packet(db_path, args.limit)
    elif args.command == "live-pilot":
        result = live_pilot_packet(db_path, args.limit)
    elif args.command == "paper-positions":
        result = paper_positions_packet(PAPER_POSITION_DB)
    else:
        sample_tickers = [item.strip().upper() for item in args.sample_tickers.split(",") if item.strip()]
        result = phase3_qc_packet(db_path, sample_tickers)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("status") in {"ok", "ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
