from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from market_data_utils import load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_DB = TMP / "veritas-artifact-index.sqlite"
SCHEMA_VERSION = 1

MARKET_EVENT_GLOBS = ["market-intelligence-events-*.json"]
DAILY_REVIEW_GLOBS = ["daily-review-objects-*.json"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE)).replace("\\", "/")


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return as_json(value)
    return str(value)


def bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def iter_artifact_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in [*MARKET_EVENT_GLOBS, *DAILY_REVIEW_GLOBS]:
        paths.extend(sorted(TMP.glob(pattern)))
    return sorted(dict.fromkeys(paths))


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


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifact_runs (
            id INTEGER PRIMARY KEY,
            source_file TEXT NOT NULL UNIQUE,
            artifact_type TEXT NOT NULL,
            window TEXT NOT NULL,
            schema_version INTEGER,
            generated_at_utc TEXT,
            indexed_at_utc TEXT NOT NULL,
            file_mtime_utc TEXT NOT NULL,
            consumer_posture TEXT,
            canonical_mutation_allowed INTEGER NOT NULL DEFAULT 0,
            owner_review_required INTEGER NOT NULL DEFAULT 1,
            summary_json TEXT NOT NULL DEFAULT '{}',
            system_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS market_events (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            window TEXT NOT NULL,
            generated_at_utc TEXT,
            list_name TEXT NOT NULL,
            rank INTEGER,
            event_id TEXT,
            ticker_or_macro_sleeve TEXT,
            event_type TEXT,
            recommended_route TEXT,
            urgency TEXT,
            materiality_score INTEGER,
            source_tier TEXT,
            event_title TEXT,
            evidence_json TEXT NOT NULL DEFAULT '[]',
            source_artifacts_json TEXT NOT NULL DEFAULT '[]',
            blocked_reason TEXT,
            owner_review_required INTEGER NOT NULL DEFAULT 1,
            canonical_mutation_allowed INTEGER NOT NULL DEFAULT 0,
            trade_execution_allowed INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS daily_review_objects (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            window TEXT NOT NULL,
            generated_at_utc TEXT,
            list_name TEXT NOT NULL,
            rank INTEGER,
            object_id TEXT,
            object_type TEXT,
            ticker TEXT,
            category TEXT,
            signal_score INTEGER,
            surface_state TEXT,
            recommended_route TEXT,
            urgency TEXT,
            materiality_score INTEGER,
            why_now TEXT,
            recommended_next_step TEXT,
            owner_question TEXT,
            owner_review_required INTEGER NOT NULL DEFAULT 1,
            evidence_json TEXT NOT NULL DEFAULT '[]',
            blockers_json TEXT NOT NULL DEFAULT '[]',
            supporting_artifacts_json TEXT NOT NULL DEFAULT '[]',
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS capital_recommendations (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            window TEXT NOT NULL,
            generated_at_utc TEXT,
            rank INTEGER,
            ticker TEXT,
            current_state TEXT,
            entry_band_status TEXT,
            fresh_intelligence_status TEXT,
            recommended_action TEXT,
            confidence TEXT,
            owner_approval_required INTEGER NOT NULL DEFAULT 1,
            trust_ceiling TEXT,
            guidance TEXT,
            risk_invalidation TEXT,
            raw_json TEXT NOT NULL
        ) STRICT;

        CREATE INDEX IF NOT EXISTS idx_artifact_runs_type_window ON artifact_runs(artifact_type, window, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_market_events_ticker ON market_events(ticker_or_macro_sleeve, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_market_events_route ON market_events(recommended_route, urgency, materiality_score);
        CREATE INDEX IF NOT EXISTS idx_daily_review_ticker ON daily_review_objects(ticker, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_daily_review_category ON daily_review_objects(category, signal_score);
        CREATE INDEX IF NOT EXISTS idx_capital_recs_ticker ON capital_recommendations(ticker, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_capital_recs_action ON capital_recommendations(recommended_action, confidence);
        """
    )
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))


def reset_index(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM market_events")
    conn.execute("DELETE FROM daily_review_objects")
    conn.execute("DELETE FROM capital_recommendations")
    conn.execute("DELETE FROM artifact_runs")


def artifact_type_for(path: Path) -> str:
    name = path.name
    if name.startswith("market-intelligence-events-"):
        return "market_intelligence_events"
    if name.startswith("daily-review-objects-"):
        return "daily_review_objects"
    return "unknown"


def insert_run(conn: sqlite3.Connection, path: Path, data: dict[str, Any], artifact_type: str, indexed_at: str) -> int:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cur = conn.execute(
        """
        INSERT INTO artifact_runs(
            source_file, artifact_type, window, schema_version, generated_at_utc, indexed_at_utc,
            file_mtime_utc, consumer_posture, canonical_mutation_allowed, owner_review_required,
            summary_json, system_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rel(path), artifact_type, str(data.get("window") or "unknown"), data.get("schema_version"),
            data.get("generated_at_utc"), indexed_at, mtime, str(data.get("consumer_posture") or ""),
            bool_int(data.get("canonical_mutation_allowed")), bool_int(data.get("owner_review_required", True)),
            as_json(data.get("summary") or {}), as_json(data.get("system") or {}),
        ),
    )
    return int(cur.lastrowid)


def insert_market_event(conn: sqlite3.Connection, run_id: int, source_file: str, window: str, generated_at: str, list_name: str, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO market_events(
            artifact_run_id, source_file, window, generated_at_utc, list_name, rank, event_id,
            ticker_or_macro_sleeve, event_type, recommended_route, urgency, materiality_score,
            source_tier, event_title, evidence_json, source_artifacts_json, blocked_reason,
            owner_review_required, canonical_mutation_allowed, trade_execution_allowed, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, source_file, window, generated_at, list_name, item.get("rank"), item.get("event_id"),
            item.get("ticker_or_macro_sleeve"), item.get("event_type"), item.get("recommended_route"), item.get("urgency"),
            item.get("materiality_score"), item.get("source_tier"), item.get("event_title"), as_json(item.get("evidence") or []),
            as_json(item.get("source_artifacts") or []), item.get("blocked_reason"), bool_int(item.get("owner_review_required", True)),
            bool_int(item.get("canonical_mutation_allowed")), bool_int(item.get("trade_execution_allowed")), as_json(item),
        ),
    )


def insert_daily_object(conn: sqlite3.Connection, run_id: int, source_file: str, window: str, generated_at: str, list_name: str, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO daily_review_objects(
            artifact_run_id, source_file, window, generated_at_utc, list_name, rank, object_id,
            object_type, ticker, category, signal_score, surface_state, recommended_route, urgency,
            materiality_score, why_now, recommended_next_step, owner_question, owner_review_required,
            evidence_json, blockers_json, supporting_artifacts_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, source_file, window, generated_at, list_name, item.get("rank"), item.get("id"),
            item.get("object_type"), item.get("ticker"), item.get("category"), item.get("signal_score"),
            item.get("surface_state"), item.get("recommended_route"), item.get("urgency"), item.get("materiality_score"),
            item.get("why_now"), item.get("recommended_next_step"), item.get("owner_question"),
            bool_int(item.get("owner_review_required", True)), as_json(item.get("evidence") or []), as_json(item.get("blockers") or []),
            as_json(item.get("supporting_artifacts") or []), as_json(item),
        ),
    )


def insert_capital_recommendation(conn: sqlite3.Connection, run_id: int, source_file: str, window: str, generated_at: str, rank: int, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO capital_recommendations(
            artifact_run_id, source_file, window, generated_at_utc, rank, ticker, current_state,
            entry_band_status, fresh_intelligence_status, recommended_action, confidence,
            owner_approval_required, trust_ceiling, guidance, risk_invalidation, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, source_file, window, generated_at, rank, item.get("ticker"), item.get("current_state"),
            item.get("entry_band_status"), item.get("fresh_intelligence_status"), item.get("recommended_action"),
            item.get("confidence"), bool_int(item.get("owner_approval_required", True)), clean_text(item.get("trust_ceiling")),
            clean_text(item.get("guidance")), clean_text(item.get("risk_invalidation")), as_json(item),
        ),
    )


def index_file(conn: sqlite3.Connection, path: Path, indexed_at: str) -> dict[str, int | str]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    artifact_type = artifact_type_for(path)
    run_id = insert_run(conn, path, data, artifact_type, indexed_at)
    source_file = rel(path)
    window = str(data.get("window") or "unknown")
    generated_at = str(data.get("generated_at_utc") or "")
    counts = {"source_file": source_file, "runs": 1, "market_events": 0, "daily_review_objects": 0, "capital_recommendations": 0}
    if artifact_type == "market_intelligence_events":
        for list_name in ("events", "escalations"):
            for item in data.get(list_name) or []:
                if isinstance(item, dict):
                    insert_market_event(conn, run_id, source_file, window, generated_at, list_name, item)
                    counts["market_events"] = int(counts["market_events"]) + 1
    elif artifact_type == "daily_review_objects":
        for list_name in ("review_objects", "escalations"):
            for item in data.get(list_name) or []:
                if isinstance(item, dict):
                    insert_daily_object(conn, run_id, source_file, window, generated_at, list_name, item)
                    counts["daily_review_objects"] = int(counts["daily_review_objects"]) + 1
        for rank, item in enumerate(data.get("capital_deployment_recommendations") or [], start=1):
            if isinstance(item, dict):
                insert_capital_recommendation(conn, run_id, source_file, window, generated_at, rank, item)
                counts["capital_recommendations"] = int(counts["capital_recommendations"]) + 1
    return counts


def rebuild(db_path: Path) -> None:
    paths = iter_artifact_paths()
    if not paths:
        raise FileNotFoundError("No market-intelligence or daily-review artifacts found under tmp/")
    indexed_at = utc_now()
    with connect(db_path) as conn:
        init_schema(conn)
        with conn:
            reset_index(conn)
            totals = {"runs": 0, "market_events": 0, "daily_review_objects": 0, "capital_recommendations": 0}
            for path in paths:
                counts = index_file(conn, path, indexed_at)
                for key in totals:
                    totals[key] += int(counts[key])
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("last_rebuilt_at_utc", indexed_at))
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("source_file_count", str(len(paths))))
        conn.execute("PRAGMA optimize")
    print(f"rebuilt {rel(db_path)}")
    print(f"source_files={len(paths)} runs={totals['runs']} market_events={totals['market_events']} daily_review_objects={totals['daily_review_objects']} capital_recommendations={totals['capital_recommendations']}")


def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, tuple(params)))


def print_table(result_rows: list[sqlite3.Row], columns: list[str]) -> None:
    if not result_rows:
        print("(no rows)")
        return
    print(" | ".join(columns))
    print(" | ".join("---" for _ in columns))
    for row in result_rows:
        print(" | ".join(clean_text(row[col]).replace("\n", " ")[:180] for col in columns))


def query_latest(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT 'market_event' AS kind, source_file, list_name, window, ticker_or_macro_sleeve AS ticker,
               recommended_route AS route, urgency, materiality_score AS score, event_title AS title, generated_at_utc
        FROM market_events
        WHERE list_name='escalations'
        UNION ALL
        SELECT 'daily_review' AS kind, source_file, list_name, window, ticker, category AS route,
               urgency, signal_score AS score, COALESCE(recommended_next_step, why_now, object_id) AS title,
               generated_at_utc
        FROM daily_review_objects
        WHERE list_name='escalations'
        ORDER BY generated_at_utc DESC, score DESC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["kind", "source_file", "list_name", "window", "ticker", "route", "urgency", "score", "title", "generated_at_utc"])


def query_ticker(conn: sqlite3.Connection, ticker: str, limit: int) -> None:
    token = ticker.upper()
    result = rows(
        conn,
        """
        SELECT 'market_event' AS kind, source_file, list_name, window, ticker_or_macro_sleeve AS ticker,
               recommended_route AS route, urgency, materiality_score AS score, event_title AS title, generated_at_utc
        FROM market_events
        WHERE upper(ticker_or_macro_sleeve)=?
        UNION ALL
        SELECT 'daily_review' AS kind, source_file, list_name, window, ticker, category AS route,
               urgency, signal_score AS score, COALESCE(recommended_next_step, why_now, object_id) AS title,
               generated_at_utc
        FROM daily_review_objects
        WHERE upper(ticker)=?
        UNION ALL
        SELECT 'capital_recommendation' AS kind, source_file, 'capital_deployment_recommendations' AS list_name,
               window, ticker, recommended_action AS route, '' AS urgency, NULL AS score, guidance AS title,
               generated_at_utc
        FROM capital_recommendations
        WHERE upper(ticker)=?
        ORDER BY generated_at_utc DESC, kind, score DESC
        LIMIT ?
        """,
        (token, token, token, limit),
    )
    print_table(result, ["kind", "source_file", "list_name", "window", "ticker", "route", "urgency", "score", "title", "generated_at_utc"])


def query_window(conn: sqlite3.Connection, window: str, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT source_file, artifact_type, window, generated_at_utc, consumer_posture,
               canonical_mutation_allowed, owner_review_required, summary_json
        FROM artifact_runs
        WHERE window=?
        ORDER BY generated_at_utc DESC, artifact_type
        LIMIT ?
        """,
        (window, limit),
    )
    print_table(result, ["source_file", "artifact_type", "window", "generated_at_utc", "consumer_posture", "canonical_mutation_allowed", "owner_review_required", "summary_json"])


def query_capital(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT window, ticker, current_state, entry_band_status, fresh_intelligence_status,
               recommended_action, confidence, owner_approval_required, generated_at_utc
        FROM capital_recommendations
        ORDER BY generated_at_utc DESC, rank ASC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["window", "ticker", "current_state", "entry_band_status", "fresh_intelligence_status", "recommended_action", "confidence", "owner_approval_required", "generated_at_utc"])


def query_trust(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT source_file, artifact_type, window, generated_at_utc, consumer_posture,
               canonical_mutation_allowed, owner_review_required, file_mtime_utc
        FROM artifact_runs
        ORDER BY generated_at_utc DESC, source_file
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["source_file", "artifact_type", "window", "generated_at_utc", "consumer_posture", "canonical_mutation_allowed", "owner_review_required", "file_mtime_utc"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and query a derived SQLite retrieval index for Veritas JSON artifacts.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path. Default: tmp/veritas-artifact-index.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rebuild", help="Rebuild the derived index from current tmp JSON artifacts.")
    latest = sub.add_parser("latest", help="Show latest escalations across indexed artifacts.")
    latest.add_argument("--limit", type=int, default=10)
    ticker = sub.add_parser("ticker", help="Show indexed events/review objects/capital recommendations for a ticker or macro sleeve.")
    ticker.add_argument("ticker")
    ticker.add_argument("--limit", type=int, default=20)
    window = sub.add_parser("window", help="Show indexed artifact runs for a window.")
    window.add_argument("window")
    window.add_argument("--limit", type=int, default=20)
    capital = sub.add_parser("capital", help="Show indexed capital deployment recommendations.")
    capital.add_argument("--limit", type=int, default=20)
    trust = sub.add_parser("trust", help="Show artifact trust/freshness boundary summary.")
    trust.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = WORKSPACE / db_path
    if args.command == "rebuild":
        rebuild(db_path)
        return 0
    if not db_path.exists():
        raise FileNotFoundError(f"Index DB not found: {db_path}. Run rebuild first.")
    with connect(db_path) as conn:
        if args.command == "latest":
            query_latest(conn, args.limit)
        elif args.command == "ticker":
            query_ticker(conn, args.ticker, args.limit)
        elif args.command == "window":
            query_window(conn, args.window, args.limit)
        elif args.command == "capital":
            query_capital(conn, args.limit)
        elif args.command == "trust":
            query_trust(conn, args.limit)
        else:
            raise ValueError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
