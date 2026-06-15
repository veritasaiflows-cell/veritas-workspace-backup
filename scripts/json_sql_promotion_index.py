#!/usr/bin/env python3
"""Build the JSON-to-SQL promotion registry and derived SQLite indexes.

JSON remains the source/proof/rebuildable evidence. This SQLite database is a
derived lookup/control-plane layer only. It is not canon, not approval, not
portfolio authority, and not paper/live/account authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_DB = TMP / "json-sql-promotion-index.sqlite"
DEFAULT_REGISTRY_JSON = TMP / "json-sql-promotion-registry.json"
DEFAULT_REGISTRY_MD = DEFAULT_REGISTRY_JSON.with_suffix(".md")
DEFAULT_SUMMARY_JSON = TMP / "json-sql-promotion-index.json"
DEFAULT_SUMMARY_MD = DEFAULT_SUMMARY_JSON.with_suffix(".md")

SCHEMA = "veritas.json_sql_promotion_index.v1"
REGISTRY_SCHEMA = "veritas.json_sql_promotion_registry.v1"

FORBIDDEN_TRUE_KEYS = {
    "portfolio_or_canon_mutation_allowed",
    "portfolio_mutation_allowed",
    "canonical_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "capital_action_allowed",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "live_trade_or_account_action_allowed",
    "trade_execution_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "owner_approval_inference_allowed",
    "brokerage_or_account_connection_allowed",
    "external_delivery_allowed",
    "customer_output_external_delivery_allowed",
    "public_launch_allowed",
    "real_customer_data_allowed",
    "sql_or_ticker_import_allowed",
    "config_auth_channel_runtime_mutation_allowed",
}

REVIEW_ONLY_AUTHORITY = {
    "json_source_of_truth": True,
    "sqlite_derived_index_only": True,
    "review_only": True,
    "canon_or_portfolio_authority": False,
    "owner_approval_authority": False,
    "capital_action_allowed": False,
    "paper_or_live_execution_allowed": False,
    "customer_data_authority": False,
    "external_delivery_allowed": False,
}


@dataclass(frozen=True)
class RegistryEntry:
    artifact_key: str
    source_path: str
    owner_workflow: str
    domain: str
    lifecycle_status: str
    target_db: str
    target_tables: tuple[str, ...]
    validator_field: str
    promotion_phase: str
    rebuild_command: str
    notes: str


REGISTRY_ENTRIES: tuple[RegistryEntry, ...] = (
    RegistryEntry(
        "macro_event_calendar",
        "tmp/macro-event-calendar.json",
        "Macro/regime desk",
        "macro",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "macro_events"),
        "status",
        "phase_3_macro_pilot",
        "python scripts\\macro_event_calendar.py --write --validate",
        "Stable high-impact official-release calendar proof.",
    ),
    RegistryEntry(
        "macro_metrics_current",
        "tmp/macro-metrics-current.json",
        "Macro/regime desk",
        "macro",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "macro_metrics"),
        "validation.status",
        "phase_3_macro_pilot",
        "python scripts\\macro_metrics_ingest.py --write --validate",
        "Stable CPI/PPI/PCE/labor/rates/dollar metrics proof.",
    ),
    RegistryEntry(
        "macro_judgment_draft",
        "tmp/macro-judgment-draft.json",
        "Macro/regime desk",
        "macro",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "macro_judgments"),
        "validation.status",
        "phase_3_macro_pilot",
        "python scripts\\macro_judgment_draft.py --write --validate",
        "Repeatable review-only interpretation layer with manual dependencies labeled.",
    ),
    RegistryEntry(
        "wf75_service_state",
        "tmp/wf75-service-state-current.json",
        "WF75 product/control-plane desk",
        "wf75",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "wf75_service_runs"),
        "status",
        "phase_4_wf75_control_plane",
        "python scripts\\wf75_service_state.py --scenario-id anon-risk-freshness-edge-cases-v1 --write --validate",
        "Anonymous service state proof, not a customer database.",
    ),
    RegistryEntry(
        "wf75_operator_queue",
        "tmp/wf75-operator-queue.json",
        "WF75 product/control-plane desk",
        "wf75",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "wf75_queue_items"),
        "validation.status",
        "phase_4_wf75_control_plane",
        "python scripts\\wf75_service_state.py --scenario-id anon-risk-freshness-edge-cases-v1 --write --validate",
        "Local operator queue proof, not approval or execution authority.",
    ),
    RegistryEntry(
        "wf75_artifact_handoff",
        "tmp/wf75-artifact-only-pm-handoff.json",
        "WF75 PM department",
        "wf75",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents",),
        "validation.status",
        "phase_4_wf75_control_plane",
        "python scripts\\wf75_artifact_only_pm_handoff.py --write --validate",
        "Artifact-only PM handoff; internal review surface only.",
    ),
    RegistryEntry(
        "research_freshness_opportunity_review",
        "tmp/research-freshness-opportunity-review.json",
        "WF60 research desk",
        "research",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "research_opportunity_items"),
        "status",
        "phase_5_research_index",
        "python scripts\\research_freshness_opportunity_review.py --window post-close",
        "Research opportunity radar and freshness queue; review-only.",
    ),
    RegistryEntry(
        "small_mid_cap_regime_feed",
        "tmp/small-mid-cap-regime-feed.json",
        "WF61 research desk",
        "research",
        "active_index",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "research_opportunity_items"),
        "status",
        "phase_5_research_index",
        "python scripts\\small_mid_cap_regime_feed.py --window post-close",
        "Diversification regime feed; no sleeve/add/allocation authority.",
    ),
    RegistryEntry(
        "capital_deployment_recommendations",
        "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
        "Portfolio/deployment desk",
        "decision_packet",
        "candidate",
        "tmp/json-sql-promotion-index.sqlite",
        ("json_documents", "decision_packets"),
        "validation.status",
        "phase_6_decision_packet_index",
        "python scripts\\portfolio_mutation_proposal_generator.py --window post-close --write",
        "Decision packet indexing candidate only; owner approval remains external.",
    ),
    RegistryEntry(
        "ticker_intelligence_cards",
        "tmp/ticker-intelligence-cards",
        "WF77 finance intelligence desk",
        "ticker_card",
        "candidate",
        "future:finance-intelligence-state or derived index",
        ("future_ticker_card_index",),
        "validation.status",
        "future_phase",
        "python scripts\\finance_intelligence_state.py ticker-card <TICKER>",
        "Stable repeated query family, but broad promotion needs scoped follow-up.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def path_for(source_path: str) -> Path:
    return ROOT / source_path.replace("/", "\\")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def authority_from(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("authority_boundary", "authority"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def forbidden_true(authority: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    for key, value in authority.items():
        if key in FORBIDDEN_TRUE_KEYS and value is True:
            hits.append(key)
    return sorted(hits)


def source_record(entry: RegistryEntry) -> dict[str, Any]:
    path = path_for(entry.source_path)
    payload = load_json_artifact(path) if path.is_file() else None
    data = as_dict(payload)
    validation = as_dict(data.get("validation"))
    authority = authority_from(data)
    return {
        "artifact_key": entry.artifact_key,
        "source_path": entry.source_path,
        "exists": path.exists(),
        "is_file": path.is_file(),
        "parseable_json": isinstance(payload, dict),
        "sha256": sha256_file(path) if path.is_file() else None,
        "schema_version": data.get("schema") or data.get("schema_version"),
        "generated_at_utc": data.get("generated_at_utc"),
        "status": data.get("status"),
        "validator_status": get_nested(data, entry.validator_field),
        "authority_boundary": authority,
        "forbidden_true_authority_flags": forbidden_true(authority),
        "payload": data,
    }


def build_registry(now: str) -> dict[str, Any]:
    records = []
    for entry in REGISTRY_ENTRIES:
        src = source_record(entry)
        records.append(
            {
                "artifact_key": entry.artifact_key,
                "source_artifact_path": entry.source_path,
                "owner_workflow": entry.owner_workflow,
                "domain": entry.domain,
                "lifecycle_status": entry.lifecycle_status,
                "target_db": entry.target_db,
                "target_tables": list(entry.target_tables),
                "validator_field": entry.validator_field,
                "observed_validator_status": src["validator_status"],
                "source_exists": src["exists"],
                "parseable_json": src["parseable_json"],
                "schema_version": src["schema_version"],
                "generated_at_utc": src["generated_at_utc"],
                "source_sha256": src["sha256"],
                "promotion_phase": entry.promotion_phase,
                "rebuild_command": entry.rebuild_command,
                "authority_boundary": REVIEW_ONLY_AUTHORITY,
                "source_forbidden_true_authority_flags": src["forbidden_true_authority_flags"],
                "notes": entry.notes,
            }
        )
    return {
        "schema": REGISTRY_SCHEMA,
        "generated_at_utc": now,
        "status": "ok",
        "posture": "json_source_sql_derived_index_only",
        "authority_boundary": REVIEW_ONLY_AUTHORITY,
        "entries": records,
        "summary": {
            "entry_count": len(records),
            "active_index_count": sum(1 for r in records if r["lifecycle_status"] == "active_index"),
            "candidate_count": sum(1 for r in records if r["lifecycle_status"] == "candidate"),
        },
    }


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS promotion_registry (
            artifact_key TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            owner_workflow TEXT NOT NULL,
            domain TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            target_db TEXT NOT NULL,
            target_tables_json TEXT NOT NULL,
            validator_field TEXT NOT NULL,
            observed_validator_status TEXT,
            schema_version TEXT,
            generated_at_utc TEXT,
            source_sha256 TEXT,
            promotion_phase TEXT NOT NULL,
            rebuild_command TEXT NOT NULL,
            authority_boundary_json TEXT NOT NULL,
            notes TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS json_documents (
            artifact_key TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            domain TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            schema_version TEXT,
            generated_at_utc TEXT,
            status TEXT,
            validator_status TEXT,
            source_sha256 TEXT,
            authority_boundary_json TEXT NOT NULL,
            parseable_json INTEGER NOT NULL CHECK (parseable_json IN (0, 1)),
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS macro_events (
            event_id TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            event_at_utc TEXT,
            event_date TEXT,
            agency TEXT,
            metric TEXT,
            period TEXT,
            importance TEXT,
            status TEXT,
            days_until INTEGER,
            source_url TEXT,
            market_sensitivity TEXT,
            macro_channels_json TEXT NOT NULL,
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS macro_metrics (
            metric_key TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            category TEXT,
            agency TEXT,
            series_id TEXT,
            latest_date TEXT,
            latest_value REAL,
            previous_date TEXT,
            previous_value REAL,
            delta REAL,
            mom_pct REAL,
            yoy_pct REAL,
            status TEXT,
            source_url TEXT,
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS macro_judgments (
            judgment_key TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            confidence TEXT,
            judgment_text TEXT NOT NULL,
            source_basis_json TEXT NOT NULL,
            recommended_capital_posture TEXT,
            capital_action_allowed INTEGER NOT NULL CHECK (capital_action_allowed IN (0, 1)),
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wf75_service_runs (
            service_run_id TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            workflow TEXT,
            status TEXT,
            scenario TEXT,
            request_type TEXT,
            ticker_set_json TEXT NOT NULL,
            anonymous_service_request INTEGER NOT NULL CHECK (anonymous_service_request IN (0, 1)),
            real_customer_data_present INTEGER NOT NULL CHECK (real_customer_data_present IN (0, 1)),
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wf75_queue_items (
            queue_id TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            service_run_id TEXT,
            workflow TEXT,
            status TEXT,
            priority TEXT,
            owner TEXT,
            next_action TEXT,
            inline_execution_allowed INTEGER NOT NULL CHECK (inline_execution_allowed IN (0, 1)),
            external_delivery_allowed INTEGER NOT NULL CHECK (external_delivery_allowed IN (0, 1)),
            customer_data_use_allowed INTEGER NOT NULL CHECK (customer_data_use_allowed IN (0, 1)),
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_opportunity_items (
            item_id TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            item_type TEXT NOT NULL,
            name TEXT NOT NULL,
            item_status TEXT,
            context_json TEXT NOT NULL,
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS decision_packets (
            packet_key TEXT PRIMARY KEY,
            source_artifact_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            status TEXT,
            validator_status TEXT,
            owner_decision_required INTEGER NOT NULL CHECK (owner_decision_required IN (0, 1)),
            authority_boundary_json TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_documents_domain ON json_documents(domain, status, validator_status);
        CREATE INDEX IF NOT EXISTS idx_macro_events_date ON macro_events(event_date, importance);
        CREATE INDEX IF NOT EXISTS idx_macro_metrics_category ON macro_metrics(category, status);
        CREATE INDEX IF NOT EXISTS idx_research_items_type ON research_opportunity_items(item_type, item_status);
        CREATE INDEX IF NOT EXISTS idx_decision_packets_status ON decision_packets(status, validator_status);
        """
    )


def reset_domain_tables(conn: sqlite3.Connection) -> None:
    for table in (
        "promotion_registry",
        "json_documents",
        "macro_events",
        "macro_metrics",
        "macro_judgments",
        "wf75_service_runs",
        "wf75_queue_items",
        "research_opportunity_items",
        "decision_packets",
    ):
        conn.execute(f"DELETE FROM {table}")


def bool_int(value: Any) -> int:
    return 1 if value is True else 0


def write_registry_tables(conn: sqlite3.Connection, registry: dict[str, Any], now: str) -> None:
    for row in as_list(registry.get("entries")):
        conn.execute(
            """
            INSERT OR REPLACE INTO promotion_registry (
                artifact_key, source_artifact_path, owner_workflow, domain, lifecycle_status,
                target_db, target_tables_json, validator_field, observed_validator_status,
                schema_version, generated_at_utc, source_sha256, promotion_phase,
                rebuild_command, authority_boundary_json, notes, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["artifact_key"],
                row["source_artifact_path"],
                row["owner_workflow"],
                row["domain"],
                row["lifecycle_status"],
                row["target_db"],
                json_text(row["target_tables"]),
                row["validator_field"],
                row.get("observed_validator_status"),
                row.get("schema_version"),
                row.get("generated_at_utc"),
                row.get("source_sha256"),
                row["promotion_phase"],
                row["rebuild_command"],
                json_text(row["authority_boundary"]),
                row["notes"],
                now,
            ),
        )


def write_json_documents(conn: sqlite3.Connection, records: dict[str, dict[str, Any]], now: str) -> None:
    entries = {entry.artifact_key: entry for entry in REGISTRY_ENTRIES}
    for key, src in records.items():
        entry = entries[key]
        if not src["is_file"]:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO json_documents (
                artifact_key, source_artifact_path, domain, lifecycle_status,
                schema_version, generated_at_utc, status, validator_status, source_sha256,
                authority_boundary_json, parseable_json, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                entry.source_path,
                entry.domain,
                entry.lifecycle_status,
                src.get("schema_version"),
                src.get("generated_at_utc"),
                src.get("status"),
                src.get("validator_status"),
                src.get("sha256"),
                json_text(src.get("authority_boundary") or REVIEW_ONLY_AUTHORITY),
                bool_int(src.get("parseable_json")),
                now,
            ),
        )


def write_macro_tables(conn: sqlite3.Connection, records: dict[str, dict[str, Any]], now: str) -> None:
    events = records["macro_event_calendar"]
    metrics = records["macro_metrics_current"]
    judgments = records["macro_judgment_draft"]
    event_auth = json_text(events.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)
    metric_auth = json_text(metrics.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)
    judgment_auth = json_text(judgments.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)

    for event in as_list(events["payload"].get("events")):
        event = as_dict(event)
        event_id = event.get("event_id")
        if not event_id:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO macro_events (
                event_id, source_artifact_path, source_sha256, event_at_utc, event_date,
                agency, metric, period, importance, status, days_until, source_url,
                market_sensitivity, macro_channels_json, authority_boundary_json, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                "tmp/macro-event-calendar.json",
                events["sha256"],
                event.get("event_at_utc"),
                event.get("date"),
                event.get("agency"),
                event.get("metric"),
                event.get("period"),
                event.get("importance"),
                event.get("status"),
                event.get("days_until"),
                event.get("source_url"),
                event.get("market_sensitivity"),
                json_text(event.get("macro_channels") or []),
                event_auth,
                now,
            ),
        )

    for metric in as_list(metrics["payload"].get("metrics")):
        metric = as_dict(metric)
        metric_key = metric.get("key")
        if not metric_key:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO macro_metrics (
                metric_key, source_artifact_path, source_sha256, category, agency,
                series_id, latest_date, latest_value, previous_date, previous_value,
                delta, mom_pct, yoy_pct, status, source_url, authority_boundary_json,
                indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric_key,
                "tmp/macro-metrics-current.json",
                metrics["sha256"],
                metric.get("category"),
                metric.get("agency"),
                metric.get("series_id"),
                metric.get("latest_date"),
                metric.get("latest_value"),
                metric.get("previous_date"),
                metric.get("previous_value"),
                metric.get("delta"),
                metric.get("mom_pct"),
                metric.get("yoy_pct"),
                metric.get("status"),
                metric.get("source_url"),
                metric_auth,
                now,
            ),
        )

    recommended = as_dict(judgments["payload"].get("recommended_capital_action"))
    for key, value in as_dict(judgments["payload"].get("judgments")).items():
        item = as_dict(value)
        conn.execute(
            """
            INSERT OR REPLACE INTO macro_judgments (
                judgment_key, source_artifact_path, source_sha256, confidence,
                judgment_text, source_basis_json, recommended_capital_posture,
                capital_action_allowed, authority_boundary_json, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                "tmp/macro-judgment-draft.json",
                judgments["sha256"],
                item.get("confidence"),
                item.get("text") or "",
                json_text(item.get("source_basis") or []),
                recommended.get("posture"),
                bool_int(recommended.get("capital_action_allowed")),
                judgment_auth,
                now,
            ),
        )


def write_wf75_tables(conn: sqlite3.Connection, records: dict[str, dict[str, Any]], now: str) -> None:
    service = records["wf75_service_state"]
    queue = records["wf75_operator_queue"]
    service_auth = json_text(service.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)
    queue_auth = json_text(queue.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)

    for run in as_list(service["payload"].get("service_runs")):
        run = as_dict(run)
        request = as_dict(run.get("request"))
        data_trust = as_dict(run.get("data_trust_state"))
        service_run_id = run.get("service_run_id")
        if not service_run_id:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wf75_service_runs (
                service_run_id, source_artifact_path, source_sha256, workflow, status,
                scenario, request_type, ticker_set_json, anonymous_service_request,
                real_customer_data_present, authority_boundary_json, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                service_run_id,
                "tmp/wf75-service-state-current.json",
                service["sha256"],
                run.get("workflow"),
                run.get("status"),
                request.get("scenario"),
                request.get("request_type"),
                json_text(request.get("ticker_set") or []),
                bool_int(request.get("anonymous_service_request")),
                bool_int(data_trust.get("real_customer_data_present")),
                service_auth,
                now,
            ),
        )

    for item in as_list(queue["payload"].get("current_queue")):
        item = as_dict(item)
        queue_id = item.get("queue_id")
        if not queue_id:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wf75_queue_items (
                queue_id, source_artifact_path, source_sha256, service_run_id, workflow,
                status, priority, owner, next_action, inline_execution_allowed,
                external_delivery_allowed, customer_data_use_allowed,
                authority_boundary_json, indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                queue_id,
                "tmp/wf75-operator-queue.json",
                queue["sha256"],
                item.get("service_run_id"),
                item.get("workflow"),
                item.get("status"),
                item.get("priority"),
                item.get("owner"),
                item.get("next_action"),
                bool_int(item.get("inline_execution_allowed")),
                bool_int(item.get("external_delivery_allowed")),
                bool_int(item.get("customer_data_use_allowed")),
                queue_auth,
                now,
            ),
        )


def add_research_item(
    conn: sqlite3.Connection,
    source_key: str,
    source_path: str,
    source_sha: str,
    auth_json: str,
    now: str,
    item_type: str,
    name: str,
    item_status: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    item_id = f"{source_key}:{item_type}:{name}".lower().replace(" ", "_")
    conn.execute(
        """
        INSERT OR REPLACE INTO research_opportunity_items (
            item_id, source_artifact_path, source_sha256, item_type, name,
            item_status, context_json, authority_boundary_json, indexed_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, source_path, source_sha, item_type, name, item_status, json_text(context or {}), auth_json, now),
    )


def write_research_tables(conn: sqlite3.Connection, records: dict[str, dict[str, Any]], now: str) -> None:
    research = records["research_freshness_opportunity_review"]
    smid = records["small_mid_cap_regime_feed"]
    research_auth = json_text(research.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)
    smid_auth = json_text(smid.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)
    opp = as_dict(research["payload"].get("opportunity_review"))

    for sector in as_list(opp.get("improving_leadership_sectors")):
        add_research_item(conn, "research", "tmp/research-freshness-opportunity-review.json", research["sha256"], research_auth, now, "improving_leadership_sector", str(sector), "review_cue")
    for sector in as_list(opp.get("underexposed_sectors")):
        add_research_item(conn, "research", "tmp/research-freshness-opportunity-review.json", research["sha256"], research_auth, now, "underexposed_sector", str(sector), "review_cue")
    for ticker in as_list(opp.get("promotion_review_candidates")):
        add_research_item(conn, "research", "tmp/research-freshness-opportunity-review.json", research["sha256"], research_auth, now, "promotion_review_candidate", str(ticker), "owner_review_required")
    for ticker in as_list(opp.get("blocked_or_review_required_candidates")):
        add_research_item(conn, "research", "tmp/research-freshness-opportunity-review.json", research["sha256"], research_auth, now, "blocked_or_review_required_candidate", str(ticker), "blocked_or_review_required")

    # WF61 shapes have changed over time; index the stable top-level queues when present.
    payload = smid["payload"]
    for key in ("candidate_queue", "review_queue", "etf_proxy_queue", "watch_queue"):
        for item in as_list(payload.get(key)):
            item_d = as_dict(item)
            name = item_d.get("ticker") or item_d.get("symbol") or item_d.get("name")
            if name:
                add_research_item(conn, "wf61", "tmp/small-mid-cap-regime-feed.json", smid["sha256"], smid_auth, now, key, str(name), item_d.get("status"), item_d)


def write_decision_packets(conn: sqlite3.Connection, records: dict[str, dict[str, Any]], now: str) -> None:
    decision = records["capital_deployment_recommendations"]
    if not decision["is_file"]:
        return
    auth_json = json_text(decision.get("authority_boundary") or REVIEW_ONLY_AUTHORITY)
    conn.execute(
        """
        INSERT OR REPLACE INTO decision_packets (
            packet_key, source_artifact_path, source_sha256, status, validator_status,
            owner_decision_required, authority_boundary_json, indexed_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "capital_deployment_recommendations",
            "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
            decision["sha256"],
            decision.get("status"),
            decision.get("validator_status"),
            1,
            auth_json,
            now,
        ),
    )


def count_table(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def build_index(db_path: Path, registry: dict[str, Any], records: dict[str, dict[str, Any]], now: str) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        with conn:
            init_schema(conn)
            reset_domain_tables(conn)
            conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?, ?)", ("schema", SCHEMA, now))
            conn.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?, ?)", ("authority_boundary", json_text(REVIEW_ONLY_AUTHORITY), now))
            write_registry_tables(conn, registry, now)
            write_json_documents(conn, records, now)
            write_macro_tables(conn, records, now)
            write_wf75_tables(conn, records, now)
            write_research_tables(conn, records, now)
            write_decision_packets(conn, records, now)
            conn.execute("PRAGMA optimize")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [dict(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
        counts = {
            table: count_table(conn, table)
            for table in (
                "promotion_registry",
                "json_documents",
                "macro_events",
                "macro_metrics",
                "macro_judgments",
                "wf75_service_runs",
                "wf75_queue_items",
                "research_opportunity_items",
                "decision_packets",
            )
        }
    finally:
        conn.close()

    return {
        "db_path": rel(db_path),
        "integrity_check": integrity,
        "foreign_key_errors": foreign_keys,
        "table_counts": counts,
    }


def validate(registry: dict[str, Any], records: dict[str, dict[str, Any]], db_result: dict[str, Any] | None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if registry.get("schema") != REGISTRY_SCHEMA:
        errors.append("registry schema mismatch")
    if registry.get("authority_boundary", {}).get("sqlite_derived_index_only") is not True:
        errors.append("registry authority boundary missing sqlite_derived_index_only=true")

    for entry in REGISTRY_ENTRIES:
        src = records[entry.artifact_key]
        if entry.lifecycle_status == "active_index":
            if not src["exists"]:
                errors.append(f"{entry.artifact_key}: active source missing")
            if not src["parseable_json"]:
                errors.append(f"{entry.artifact_key}: active source not parseable JSON")
            if src["forbidden_true_authority_flags"]:
                errors.append(f"{entry.artifact_key}: forbidden true authority flags {src['forbidden_true_authority_flags']}")
            observed = src.get("validator_status")
            status = src.get("status")
            if observed not in {"ok", None} and status not in {"ok", "warning", "degraded"}:
                warnings.append(f"{entry.artifact_key}: validator/status is {observed or status}")
        elif entry.lifecycle_status == "candidate" and not src["exists"]:
            warnings.append(f"{entry.artifact_key}: candidate source not present")

    if db_result is not None:
        if db_result.get("integrity_check") != "ok":
            errors.append("sqlite integrity_check failed")
        if db_result.get("foreign_key_errors"):
            errors.append("sqlite foreign_key_check returned rows")
        counts = as_dict(db_result.get("table_counts"))
        if counts.get("macro_events", 0) <= 0:
            errors.append("macro_events has no rows")
        if counts.get("macro_metrics", 0) <= 0:
            errors.append("macro_metrics has no rows")
        if counts.get("macro_judgments", 0) < 10:
            errors.append("macro_judgments missing expected judgment fields")
        if counts.get("promotion_registry", 0) != len(REGISTRY_ENTRIES):
            errors.append("promotion_registry row count mismatch")

    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_registry_md(registry: dict[str, Any]) -> str:
    lines = [
        "# JSON to SQLite Promotion Registry",
        "",
        f"- Generated: `{registry['generated_at_utc']}`",
        "- Posture: JSON is proof/source; SQLite is derived index/control plane only.",
        "- Boundary: no canon, approval, portfolio, capital-action, customer, paper/live/account, or external-delivery authority.",
        "",
        "| Artifact | Status | Domain | Phase | Target tables | Validator |",
        "|---|---:|---|---|---|---|",
    ]
    for row in registry["entries"]:
        lines.append(
            f"| `{row['source_artifact_path']}` | `{row['lifecycle_status']}` | {row['domain']} | {row['promotion_phase']} | "
            f"`{', '.join(row['target_tables'])}` | `{row['observed_validator_status']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def render_summary_md(summary: dict[str, Any]) -> str:
    counts = summary["sqlite"]["table_counts"]
    lines = [
        "# JSON to SQLite Promotion Index",
        "",
        f"- Generated: `{summary['generated_at_utc']}`",
        f"- Status: `{summary['status']}`",
        f"- DB: `{summary['sqlite']['db_path']}`",
        f"- Integrity: `{summary['sqlite']['integrity_check']}`",
        "",
        "| Table | Rows |",
        "|---|---:|",
    ]
    for table, count in counts.items():
        lines.append(f"| `{table}` | {count} |")
    lines.extend(
        [
            "",
            "## Authority",
            "",
            "- JSON artifacts remain source/proof/rebuildable evidence.",
            "- SQLite is a derived lookup layer only.",
            "- No owner approval, portfolio/canon mutation, capital action, customer data authority, or paper/live/account authority is created.",
            "",
        ]
    )
    if summary["validation"]["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        for warning in summary["validation"]["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def build_payload(db_path: Path, write_db: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    now = utc_now()
    registry = build_registry(now)
    records = {entry.artifact_key: source_record(entry) for entry in REGISTRY_ENTRIES}
    db_result = build_index(db_path, registry, records, now) if write_db else None
    validation = validate(registry, records, db_result)
    status = "ok" if validation["status"] == "ok" and not validation["warnings"] else "warning"
    if validation["status"] != "ok":
        status = "error"
    summary = {
        "schema": SCHEMA,
        "generated_at_utc": now,
        "status": status,
        "posture": "json_source_sql_derived_index_only",
        "authority_boundary": REVIEW_ONLY_AUTHORITY,
        "registry_path": rel(DEFAULT_REGISTRY_JSON),
        "sqlite": db_result or {"db_path": rel(db_path), "not_written": True, "table_counts": {}},
        "source_summary": {
            "registry_entry_count": len(REGISTRY_ENTRIES),
            "active_index_count": sum(1 for e in REGISTRY_ENTRIES if e.lifecycle_status == "active_index"),
            "candidate_count": sum(1 for e in REGISTRY_ENTRIES if e.lifecycle_status == "candidate"),
        },
        "validation": validation,
    }
    return registry, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--write", action="store_true", help="Write registry JSON and SQLite index")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown summaries")
    parser.add_argument("--validate", action="store_true", help="Validate generated or existing outputs")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    registry, summary = build_payload(db_path, write_db=args.write)

    if args.write:
        atomic_write_json(DEFAULT_REGISTRY_JSON, registry)
        atomic_write_json(DEFAULT_SUMMARY_JSON, summary)
    if args.write_md:
        atomic_write_text(DEFAULT_REGISTRY_MD, render_registry_md(registry))
        atomic_write_text(DEFAULT_SUMMARY_MD, render_summary_md(summary))

    if args.validate:
        print(summary["status"])
        if summary["validation"]["errors"]:
            for error in summary["validation"]["errors"]:
                print(f"ERROR: {error}")
            return 1
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
