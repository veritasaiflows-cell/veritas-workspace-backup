#!/usr/bin/env python3
"""Build a read-only lifecycle manifest for workspace SQLite databases.

This script labels SQLite files and proposes archive candidates. It never
moves, deletes, rewrites, checkpoints, or vacuums databases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
JSON_REPORT = TMP / "db-lifecycle-manifest.json"
MD_REPORT = TMP / "db-lifecycle-manifest.md"
ARCHIVE_APPROVAL_PACKET = TMP / "db-lifecycle-archive-approval-packet.json"
ARCHIVE_ROOT = Path("09. Archive/DB Lifecycle - Archived/2026-05-30")
ARCHIVE_SCAN_ROOT = ROOT / "09. Archive" / "DB Lifecycle - Archived"

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".csv",
    ".html",
    ".yaml",
    ".yml",
    ".ps1",
}
EXCLUDED_SCAN_DIRS = {
    ".git",
    ".obsidian",
    ".openclaw",
    ".clawhub",
    "__pycache__",
}

LIVE_STATE = {
    "finance-canon.sqlite": {
        "owner": "WF78 finance SQL canon candidate",
        "reason": "durable finance universe and answer-path scope machine-canon candidate",
        "rebuild": "python scripts\\finance_sql_canon.py --write --validate --approval-reference \"<owner approval reference>\"",
    },
    "veritas-canon-cache.sqlite": {
        "owner": "WF72 bounded SQL-canon/cache metadata",
        "reason": "bounded 265-row approved metadata cache; authority-bearing within narrow proof/cache boundary",
        "rebuild": "scripts/artifact_index.py low-risk/WF72 activation paths only after gated approval",
    },
    "finance-intelligence-state.sqlite": {
        "owner": "WF78 finance intelligence current-state router",
        "reason": "active 42-ticker current-state/query-packet database",
        "rebuild": "python scripts\\finance_intelligence_state.py build --pretty",
    },
    "wf67-paper-position-state.sqlite": {
        "owner": "WF63/WF67 paper-position read-only state",
        "reason": "active GET-only paper account/position visibility state",
        "rebuild": "python scripts\\alpaca_paper_position_sql_refresh.py refresh --create-kill-switch --expires-minutes 90",
    },
    "wf75-service-state.sqlite": {
        "owner": "WF75 anonymous service-state control plane",
        "reason": "active local service request/operator queue state for prototype work",
        "rebuild": "python scripts\\wf75_service_state_sqlite.py",
    },
}

DERIVED = {
    "workspace-index.sqlite": {
        "owner": "workspace FTS retrieval cache",
        "reason": "rebuildable FTS5 discovery index; source Markdown/files remain canon",
        "rebuild": "python scripts\\workspace_index.py",
    },
    "veritas-artifact-index.sqlite": {
        "owner": "artifact cockpit proof/index",
        "reason": "rebuildable artifact routing/proof index; not canon or approval authority",
        "rebuild": "python scripts\\artifact_index.py rebuild",
    },
    "json-sql-promotion-index.sqlite": {
        "owner": "JSON-to-SQL promotion derived index",
        "reason": "rebuildable index over stable JSON proof contracts; JSON artifacts remain source/proof authority",
        "rebuild": "python scripts\\json_sql_promotion_index.py --write --write-md --validate",
    },
    "pm-program-state.sqlite": {
        "owner": "WF75 PM program-state derived index",
        "reason": "rebuildable lookup over PM program-state JSON packets for lane, blocker, next-action, artifact, and authority status",
        "rebuild": "python scripts\\pm_control_packet.py --write --write-db --validate",
    },
    "pm-implementation-job-queue.sqlite": {
        "owner": "WF75 PM implementation job queue derived index",
        "reason": "rebuildable lookup over PM implementation job packets; JSON remains source proof and this does not execute jobs or grant authority",
        "rebuild": "python scripts\\pm_control_packet.py --write --write-db --validate",
    },
    "pm-control-packet.sqlite": {
        "owner": "WF75 consolidated PM control derived index",
        "reason": "rebuildable lookup over PM state, PM queue, heartbeat candidates, and main-session handoff; JSON remains source proof and this does not execute jobs or grant authority",
        "rebuild": "python scripts\\pm_control_packet.py --write --write-db --validate",
    },
    "workflow-routing-index.sqlite": {
        "owner": "WF73 workflow route-control derived index",
        "reason": "rebuildable SQLite lookup over workflow routing JSON proof; Active Workflows and continuity notes remain authority",
        "rebuild": "python scripts\\workflow_routing_index.py --write --write-db --validate",
    },
    "canonical-finance-data-plane.sqlite": {
        "owner": "WF84 canonical finance data-plane derived lookup",
        "reason": "rebuildable SQLite companion loaded only from tmp/canonical-finance-data-plane.json; JSON packet and source artifacts remain proof, and this DB is not canon, approval, portfolio, account, paper/live, or execution authority",
        "rebuild": "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
    },
    "generic-service-state.sqlite": {
        "owner": "WF75 SMB Workflow Clarity derived control plane",
        "reason": "rebuildable lookup over generic service-run, SMB scenario, renderer, validation, and pilot packet JSON artifacts; JSON remains source proof",
        "rebuild": "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
    },
    "wf78-sql-readiness-index.sqlite": {
        "owner": "WF78 SQL readiness derived index",
        "reason": "rebuildable lookup over WF78 readiness JSON artifacts; JSON artifacts remain source proof and this does not authorize SQL import",
        "rebuild": "python scripts\\wf78_sql_readiness_index.py --write --validate",
    },
    "wf78-routing-dashboard.sqlite": {
        "owner": "WF78 routing dashboard derived index",
        "reason": "rebuildable lookup over WF78 funnel/owner-decision JSON proof; routes lanes, verdicts, evidence gaps, and skill ownership without canon, approval, import, promotion, or execution authority",
        "rebuild": "python scripts\\wf78_routing_dashboard.py --write --write-db --validate",
    },
    "wf78-capital-review-queue.sqlite": {
        "owner": "WF78 capital-review queue derived index",
        "reason": "rebuildable SQLite companion for capital-review queue JSON proof; owner-action queue only and not capital deployment, approval, or execution authority",
        "rebuild": "python scripts\\wf78_capital_review_queue.py --write --write-db --validate",
    },
    "wf78-event-triggered-rerouting.sqlite": {
        "owner": "WF78 event-triggered rerouting derived index",
        "reason": "rebuildable SQLite companion for AI event-triggered rerouting JSON proof; work-selection only and not evidence mutation, capital deployment, approval, or execution authority",
        "rebuild": "python scripts\\wf78_event_triggered_rerouting.py --write --write-db --validate",
    },
    "wf78-100-to-200-candidate-manifest.sqlite": {
        "owner": "WF78 100-to-200 candidate manifest derived index",
        "reason": "rebuildable SQLite companion for the WF78 100-to-200 candidate manifest JSON; review-only and not import authority",
        "rebuild": "python scripts\\wf78_100_to_200_candidate_manifest.py --write --validate",
    },
    "wf78-101-200-candidate-source-registry.sqlite": {
        "owner": "WF78 101-200 candidate source registry derived index",
        "reason": "rebuildable SQLite companion for source-registry JSON proof; review-only and not provider import authority",
        "rebuild": "python scripts\\wf78_101_200_candidate_source_registry.py --write --validate",
    },
    "wf78-101-200-import-decision-packet.sqlite": {
        "owner": "WF78 101-200 import decision packet derived index",
        "reason": "rebuildable SQLite companion for owner-gated import decision JSON; review-only and not approval or import authority",
        "rebuild": "python scripts\\wf78_101_200_import_decision_packet.py --write --validate",
    },
    "wf78-101-200-provider-source-validation.sqlite": {
        "owner": "WF78 101-200 provider/source validation derived index",
        "reason": "rebuildable SQLite companion for provider and official-source validation JSON; review-only and not source promotion authority",
        "rebuild": "python scripts\\wf78_101_200_provider_source_validation.py --write --validate",
    },
    "wf78-500-ticker-reputation-gate.sqlite": {
        "owner": "WF78 500-ticker reputation gate derived index",
        "reason": "rebuildable SQLite companion for the WF78 reputation-gate JSON; review-only and not ticker import, promotion, or production authority",
        "rebuild": "python scripts\\wf78_500_ticker_reputation_gate.py --write --write-db --validate",
    },
    "wf78-macro-thesis-overlay-gate.sqlite": {
        "owner": "WF78 macro/thesis overlay gate derived index",
        "reason": "rebuildable SQLite companion for macro/thesis triage JSON; shortlist proof only and not Tier B/A promotion, recommendation, or capital-deployment authority",
        "rebuild": "python scripts\\wf78_macro_thesis_overlay_gate.py --write --write-db --validate",
    },
    "wf78-tier-promotion-review-gate.sqlite": {
        "owner": "WF78 tier promotion review gate derived index",
        "reason": "rebuildable SQLite companion for tier-promotion review JSON; owner-decision support only and not import/apply, Tier B/A promotion, or execution authority",
        "rebuild": "python scripts\\wf78_tier_promotion_review_gate.py --write --write-db --validate",
    },
    "wf78-tier-capacity-policy-gate.sqlite": {
        "owner": "WF78 tier capacity policy gate derived index",
        "reason": "rebuildable SQLite companion for tier capacity policy JSON; capacity proof only and not promotion, capital deployment, or execution authority",
        "rebuild": "python scripts\\wf78_tier_capacity_policy_gate.py --write --write-db --validate",
    },
    "wf78-tier-b-research-packets.sqlite": {
        "owner": "WF78 Tier B research packets derived index",
        "reason": "rebuildable SQLite companion for Tier B research packet JSON and request proof; review-only and not promotion, import, recommendation, capital-deployment, or execution authority",
        "rebuild": "python scripts\\wf78_tier_b_research_packet.py --write --write-db --validate",
    },
    "wf78-tier-b-evidence-repair.sqlite": {
        "owner": "WF78 Tier B evidence repair derived index",
        "reason": "rebuildable SQLite companion for Tier B evidence-repair JSON; review-only and not written-band, stop, admission, apply, portfolio/canon, paper/live/account, or approval authority",
        "rebuild": "python scripts\\wf78_tier_b_evidence_repair.py --quote <TICKER=PRICE> --write --write-db --validate",
    },
    "wf78-tier-c-attention-trigger.sqlite": {
        "owner": "WF78 Tier C attention trigger derived index",
        "reason": "rebuildable SQLite companion for Tier C attention-trigger JSON proof; review-only work selection and not ticker admission, promotion, portfolio/canon, paper/live/account, or approval authority",
        "rebuild": "python scripts\\wf78_tier_c_attention_trigger.py --write --write-db --validate",
    },
    "wf78-tier-c-top3-evidence-repair.sqlite": {
        "owner": "WF78 Tier C top-3 evidence repair derived index",
        "reason": "rebuildable SQLite companion for Tier C top-3 evidence repair JSON proof; review-only repair routing and not written-band, stop, admission, promotion, portfolio/canon, paper/live/account, or approval authority",
        "rebuild": "python scripts\\wf78_tier_b_evidence_repair.py --out tmp\\wf78-tier-c-top3-evidence-repair.json --db tmp\\wf78-tier-c-top3-evidence-repair.sqlite --write --write-db --validate",
    },
    "wf78-production-tier-adjudication.sqlite": {
        "owner": "WF78 42-production Tier A/B adjudication derived index",
        "reason": "rebuildable SQLite companion for the 42-production Tier A/B recommendation packet; review-only and not admission, promotion, apply, portfolio/canon, paper/live/account, or approval authority",
        "rebuild": "python scripts\\wf78_production_tier_adjudication.py --write --write-db --validate",
    },
    "wf78-legacy-42-tier-state-shadow.sqlite": {
        "owner": "WF78 legacy-42 to Tier A/B shadow migration reader",
        "reason": "derived shadow lookup mapping the legacy production-current-42 set into the Tier A/B migration model; read-only bridge/fallback, not canon or archive authority",
        "rebuild": "python scripts\\wf78_legacy_42_tier_migration_planner.py --write --write-db --validate",
    },
    "otel-ops.sqlite": {
        "owner": "WF74/OTEL local operations digest derived index",
        "reason": "rebuildable local-only SQLite companion for tmp/otel-ops-control.json and tmp/otel-ops-events.jsonl; review-only operations visibility",
        "rebuild": "python scripts\\otel_ops_control.py --write --write-db --validate",
    },
    "macro-metrics-current.sqlite": {
        "owner": "macro metrics official-source derived index",
        "reason": "rebuildable SQLite companion for tmp/macro-metrics-current.json; review-only macro evidence visibility and not forecast, probability, portfolio, canon, paper/live, account, or approval authority",
        "rebuild": "python scripts\\macro_metrics_ingest.py --write --write-db --validate",
    },
    "sqlite-concurrency-test.sqlite": {
        "owner": "WF73 local Postgres readiness benchmark proof",
        "reason": "rebuildable local SQLite concurrency benchmark artifact under tmp/local-postgres-readiness-benchmark-work; proof-only and not runtime, canon, portfolio, approval, account, paper/live, or production database authority",
        "rebuild": "python scripts\\wf73_postgres_shadow_pilot.py --write --validate",
    },
    "paper-order-reconciliation.vrt-wf86-assisted-approved.sqlite": {
        "owner": "WF86 assisted paper reconciliation derived proof",
        "reason": "rebuildable GET-only paper-order reconciliation companion for the WF86 assisted VRT proof path; review-only and not submit, cancel, sell, account, money-movement, approval, or execution authority",
        "rebuild": "python scripts\\wf86_daily_shadow_reconciliation_cron_runner.py --write --validate",
    },
}

SNAPSHOT = {
    "finance-stack-snapshot.sqlite": {
        "owner": "finance stack snapshot",
        "reason": "review-only snapshot surface documented in scripts README; useful but not canon",
        "rebuild": "python scripts\\finance_stack_snapshot.py --write --validate",
        "decision": "conditional_keep",
        "retention": "conditional keep; regenerate on demand and archive only after a superseding live route is confirmed",
    },
}

ARCHIVE_CANDIDATE_RULES = {
    "wf72-entry-stop-sql-activation-rollback-drill.sqlite": {
        "lifecycle": "drill",
        "owner": "WF72 rollback drill proof",
        "reason": "one-time rollback drill database; prior audit said retain until WF72 SQL work closes",
        "archive_bucket": "wf72-drill",
    },
    "wf72-phase4-six-key-stabilization-cache-copy.sqlite": {
        "lifecycle": "rollback",
        "owner": "WF72 phase 4 stabilization rollback copy",
        "reason": "historical cache copy; associated Markdown proof has already been archived",
        "archive_bucket": "wf72-rollback-copies",
    },
    "wf72-phase4-six-key-stabilization-postfix-cache-copy.sqlite": {
        "lifecycle": "rollback",
        "owner": "WF72 phase 4 stabilization post-fix rollback copy",
        "reason": "historical cache copy; associated Markdown proof has already been archived",
        "archive_bucket": "wf72-rollback-copies",
    },
    "veritas-canon-cache.pre-a1-20260604T041856Z.sqlite": {
        "lifecycle": "rollback",
        "owner": "WF72 A1 low-risk cache refresh rollback copy",
        "reason": "pre-A1 backup retained after the 13-row low-risk metadata refresh; active cache remains veritas-canon-cache.sqlite",
        "archive_bucket": "wf72-rollback-copies",
    },
    "wf67-paper-position-state.pre-block-test.20260528-175138.sqlite": {
        "lifecycle": "test",
        "owner": "WF67 paper-position block-test fixture",
        "reason": "test snapshot from WF67 block repair; active state now lives in wf67-paper-position-state.sqlite",
        "archive_bucket": "wf67-test-fixtures",
    },
}

DB_SUFFIXES = {".sqlite", ".db"}
SIDECAR_SUFFIXES = (".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm")
REFERENCE_BUCKETS = (
    "active_operational_consumer_references",
    "producer_rebuild_references",
    "proof_history_references",
    "tombstone_provenance_references",
    "lifecycle_rule_references",
)
PROOF_HISTORY_ROOTS = {"tmp", "09. Archive", "08. Audits", "memory", "backups"}
ARCHIVE_APPROVAL_TARGET_BASENAMES = {
    "veritas-canon-cache.pre-a1-20260604T041856Z.sqlite",
    "wf72-entry-stop-sql-activation-rollback-drill.sqlite",
}


@dataclass
class DbEntry:
    path: str
    basename: str
    lifecycle: str
    owner: str
    status: str
    recommendation: str
    archive_ready: bool
    delete_ready: bool
    owner_approval_required: bool
    apply_allowed: bool
    proposed_destination: str | None
    rebuild_command: str | None
    retention_policy: str | None
    size_bytes: int
    mtime_utc: str
    sha256: str | None
    active_reference_count: int
    operational_reference_count: int
    total_reference_count: int
    reference_classification: dict[str, Any]
    reference_notes: list[str]
    sqlite: dict[str, Any]
    sidecars: list[dict[str, Any]]
    evidence: list[str]
    blockers: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def path_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def iter_db_files() -> Iterable[Path]:
    files: list[Path] = []
    for base in (TMP, STATE, ARCHIVE_SCAN_ROOT):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in DB_SUFFIXES:
                files.append(path)
    return sorted(files, key=lambda p: rel(p).lower())


def iter_text_files() -> Iterable[Path]:
    roots = [
        ROOT / "scripts",
        ROOT / "06. Playbooks",
        ROOT / "08. Audits",
        ROOT / "memory",
        ROOT / "tmp",
        ROOT,
    ]
    seen: set[Path] = set()
    for base in roots:
        if not base.exists():
            continue
        paths = base.rglob("*") if base.is_dir() else [base]
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            try:
                rel_parts = path.relative_to(ROOT).parts
            except ValueError:
                continue
            if any(part in EXCLUDED_SCAN_DIRS for part in rel_parts):
                continue
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                yield path


def text_corpus() -> list[tuple[Path, str]]:
    corpus: list[tuple[Path, str]] = []
    for path in iter_text_files():
        try:
            corpus.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return corpus


def _empty_reference_classification() -> dict[str, list[str]]:
    return {bucket: [] for bucket in REFERENCE_BUCKETS}


def _reference_bucket(candidate: Path, reference_path: Path) -> tuple[str, str]:
    basename = candidate.name
    path_rel = rel(reference_path)
    parts = reference_path.relative_to(ROOT).parts
    path_lower = path_rel.lower()
    name_lower = reference_path.name.lower()
    root = parts[0] if parts else ""

    if path_rel == "scripts/db_lifecycle_manifest.py":
        return "lifecycle_rule_references", "lifecycle rule reference"

    if (
        path_rel == "scripts/wf72_entry_stop_sql_activate.py"
        and basename == "wf72-entry-stop-sql-activation-rollback-drill.sqlite"
    ):
        return "producer_rebuild_references", "producer recreates drill DB with copy2 before use"

    if "tombstone" in name_lower or "tombstone" in path_lower:
        return "tombstone_provenance_references", "tombstone/provenance reference"

    if root in PROOF_HISTORY_ROOTS:
        return "proof_history_references", "proof/audit/history reference"

    return "active_operational_consumer_references", "active operational consumer reference"


def reference_details(candidate: Path, corpus: list[tuple[Path, str]]) -> dict[str, Any]:
    rel_path = rel(candidate)
    win_path = rel_path.replace("/", "\\")
    basename = candidate.name
    needles = {rel_path, win_path, basename}
    total = 0
    notes: list[str] = []
    classification = _empty_reference_classification()
    for path, text in corpus:
        if path == candidate:
            continue
        if not any(needle in text for needle in needles):
            continue
        total += 1
        path_rel = rel(path)
        bucket, note = _reference_bucket(candidate, path)
        classification[bucket].append(path_rel)
        notes.append(f"{path_rel}: {note}")
    for bucket in REFERENCE_BUCKETS:
        classification[bucket] = sorted(set(classification[bucket]))
    operational = len(classification["active_operational_consumer_references"])
    active = (
        operational
        + len(classification["producer_rebuild_references"])
        + len(classification["lifecycle_rule_references"])
    )
    return {
        "active_reference_count": active,
        "operational_reference_count": operational,
        "total_reference_count": total,
        "reference_classification": {
            "summary": {bucket: len(classification[bucket]) for bucket in REFERENCE_BUCKETS},
            **classification,
        },
        "reference_notes": sorted(set(notes)),
    }


def sqlite_probe(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "open_status": "unknown",
        "journal_mode": None,
        "page_size": None,
        "page_count": None,
        "freelist_count": None,
        "integrity_check": None,
        "table_count": None,
        "index_count": None,
        "view_count": None,
        "sqlite_stat1_rows": None,
        "tables": [],
        "error": None,
    }
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error as exc:
        result["open_status"] = "error"
        result["error"] = str(exc)
        return result
    try:
        conn.row_factory = sqlite3.Row
        result["open_status"] = "ok"
        result["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        result["page_size"] = conn.execute("PRAGMA page_size").fetchone()[0]
        result["page_count"] = conn.execute("PRAGMA page_count").fetchone()[0]
        result["freelist_count"] = conn.execute("PRAGMA freelist_count").fetchone()[0]
        result["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        rows = conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'index', 'view')
              AND name NOT LIKE 'sqlite_autoindex%'
            ORDER BY type, name
            """
        ).fetchall()
        result["table_count"] = sum(1 for row in rows if row["type"] == "table")
        result["index_count"] = sum(1 for row in rows if row["type"] == "index")
        result["view_count"] = sum(1 for row in rows if row["type"] == "view")
        tables: list[dict[str, Any]] = []
        for row in rows:
            if row["type"] != "table":
                continue
            name = row["name"]
            if name.startswith("sqlite_"):
                continue
            entry: dict[str, Any] = {"name": name, "row_count": None}
            try:
                quoted = '"' + name.replace('"', '""') + '"'
                entry["row_count"] = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            except sqlite3.Error as exc:
                entry["row_count_error"] = str(exc)
            tables.append(entry)
        result["tables"] = tables
        try:
            result["sqlite_stat1_rows"] = conn.execute("SELECT COUNT(*) FROM sqlite_stat1").fetchone()[0]
        except sqlite3.Error:
            result["sqlite_stat1_rows"] = None
    except sqlite3.Error as exc:
        result["open_status"] = "error"
        result["error"] = str(exc)
    finally:
        conn.close()
    return result


def sidecars_for(path: Path, proposed_db_destination: str | None = None) -> list[dict[str, Any]]:
    candidates = [
        Path(str(path) + "-wal"),
        Path(str(path) + "-shm"),
    ]
    out: list[dict[str, Any]] = []
    for sidecar in candidates:
        if not sidecar.exists():
            continue
        destination = None
        if proposed_db_destination:
            suffix = sidecar.name[len(path.name):]
            destination = proposed_db_destination + suffix
        out.append({
            "path": rel(sidecar),
            "size_bytes": sidecar.stat().st_size,
            "mtime_utc": path_utc(sidecar),
            "sha256": sha256_file(sidecar),
            "proposed_destination": destination,
        })
    return out


def rollback_path_for(entry: dict[str, Any]) -> dict[str, Any]:
    proposed_destination = entry.get("proposed_destination")
    source = entry.get("path")
    if not proposed_destination:
        return {
            "available": False,
            "reason": "no proposed archive destination because candidate is not archive-ready",
        }
    return {
        "available": True,
        "source_after_archive": proposed_destination,
        "restore_destination": source,
        "sidecar_restore_paths": [
            {
                "source_after_archive": sidecar.get("proposed_destination"),
                "restore_destination": sidecar.get("path"),
            }
            for sidecar in entry.get("sidecars", [])
        ],
        "required_validation_after_restore": [
            "python scripts\\db_lifecycle_manifest.py --write --validate",
            "python scripts\\artifact_index.py validate",
            "python scripts\\fast_path_qa.py --write --validate",
        ],
    }


def classify(path: Path, active_refs: int, operational_refs: int, sqlite_meta: dict[str, Any]) -> dict[str, Any]:
    name = path.name
    path_rel = rel(path)
    evidence: list[str] = []
    blockers: list[str] = []
    proposed_destination: str | None = None
    lifecycle = "unknown"
    owner = "unclassified"
    status = "needs_review"
    recommendation = "classify before archive/delete decisions"
    archive_ready = False
    delete_ready = False
    rebuild_command: str | None = None
    retention_policy: str | None = None

    if name in LIVE_STATE:
        rule = LIVE_STATE[name]
        lifecycle = "live"
        owner = rule["owner"]
        status = "keep"
        recommendation = "protect; do not archive or delete"
        rebuild_command = rule["rebuild"]
        retention_policy = "protected active state; no archive/delete without replacing the authority route"
        evidence.append(rule["reason"])
        evidence.append(f"rebuild path: {rebuild_command}")
        blockers.append("active authority/state surface")
    elif name in DERIVED:
        rule = DERIVED[name]
        lifecycle = "derived"
        owner = rule["owner"]
        status = "keep"
        recommendation = "retain as active rebuildable cache; cleanup only through owner rebuild/retention procedure"
        rebuild_command = rule["rebuild"]
        retention_policy = "active derived cache; rebuild instead of archive/delete during normal hygiene"
        evidence.append(rule["reason"])
        evidence.append(f"rebuild path: {rebuild_command}")
        blockers.append("active derived retrieval/proof surface")
    elif name in SNAPSHOT:
        rule = SNAPSHOT[name]
        lifecycle = "snapshot"
        owner = rule["owner"]
        status = "conditional_keep"
        recommendation = "keep as a labeled snapshot; regenerate on demand and archive only after deciding this surface is superseded"
        rebuild_command = rule["rebuild"]
        retention_policy = rule.get("retention")
        evidence.append(rule["reason"])
        evidence.append(f"rebuild path: {rebuild_command}")
        if retention_policy:
            evidence.append(f"retention policy: {retention_policy}")
        blockers.append("still documented and currently reusable")
    elif path_rel.startswith("tmp/backups/") and path_rel.endswith("/state/openclaw.sqlite"):
        lifecycle = "rollback"
        owner = "OpenClaw runtime remediation rollback/provenance backup"
        status = "conditional_keep"
        recommendation = (
            "retain as labeled runtime rollback/provenance backup; archive only with the parent backup set "
            "after explicit owner approval and reference review"
        )
        retention_policy = "conditional keep while remediation provenance is active; no delete automation"
        evidence.append("OpenClaw runtime state backup captured under tmp/backups during approved remediation")
        evidence.append("runtime/control-plane backup; not a live authority database and not safe for automatic cleanup")
        blockers.append("runtime backup provenance requires owner decision before archive/delete")
        if sqlite_meta.get("integrity_check") != "ok":
            blockers.append("integrity check is not ok; preserve for investigation")
    elif name in ARCHIVE_CANDIDATE_RULES:
        rule = ARCHIVE_CANDIDATE_RULES[name]
        lifecycle = rule["lifecycle"]
        owner = rule["owner"]
        if rel(path).startswith("09. Archive/"):
            lifecycle = "archived"
            status = "archived"
            recommendation = "retain in archive; do not delete until a later retention proof"
            archive_ready = False
        else:
            status = "archive_candidate"
            recommendation = "archive after owner approval; do not delete in this pass"
            archive_ready = True
        evidence.append(rule["reason"])
        proposed_destination = (ARCHIVE_ROOT / rule["archive_bucket"] / path.name).as_posix()
        if status == "archive_candidate" and operational_refs:
            blockers.append("active operational references exist; inspect before archiving")
        if status == "archive_candidate" and sqlite_meta.get("integrity_check") != "ok":
            blockers.append("integrity check is not ok; preserve for investigation instead of cleanup")
    else:
        evidence.append("no known lifecycle rule matched")
        blockers.append("unclassified database")

    return {
        "lifecycle": lifecycle,
        "owner": owner,
        "status": status,
        "recommendation": recommendation,
        "archive_ready": archive_ready and not blockers,
        "delete_ready": delete_ready,
        "proposed_destination": proposed_destination,
        "rebuild_command": rebuild_command,
        "retention_policy": retention_policy,
        "evidence": evidence,
        "blockers": blockers,
    }


def build_manifest() -> dict[str, Any]:
    corpus = text_corpus()
    entries: list[DbEntry] = []
    for path in iter_db_files():
        refs = reference_details(path, corpus)
        active_refs = refs["active_reference_count"]
        operational_refs = refs["operational_reference_count"]
        total_refs = refs["total_reference_count"]
        reference_classification = refs["reference_classification"]
        sqlite_meta = sqlite_probe(path)
        classification = classify(path, active_refs, operational_refs, sqlite_meta)
        proposed_destination = classification["proposed_destination"]
        entries.append(
            DbEntry(
                path=rel(path),
                basename=path.name,
                lifecycle=classification["lifecycle"],
                owner=classification["owner"],
                status=classification["status"],
                recommendation=classification["recommendation"],
                archive_ready=classification["archive_ready"],
                delete_ready=classification["delete_ready"],
                owner_approval_required=True,
                apply_allowed=False,
                proposed_destination=proposed_destination,
                rebuild_command=classification["rebuild_command"],
                retention_policy=classification["retention_policy"],
                size_bytes=path.stat().st_size,
                mtime_utc=path_utc(path),
                sha256=sha256_file(path),
                active_reference_count=active_refs,
                operational_reference_count=operational_refs,
                total_reference_count=total_refs,
                reference_classification=reference_classification,
                reference_notes=refs["reference_notes"],
                sqlite=sqlite_meta,
                sidecars=sidecars_for(path, proposed_destination),
                evidence=classification["evidence"],
                blockers=classification["blockers"],
            )
        )

    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.lifecycle] = counts.get(entry.lifecycle, 0) + 1
    archive_ready = [entry for entry in entries if entry.archive_ready]
    archive_candidates = [entry for entry in entries if entry.status == "archive_candidate"]
    archived_entries = [entry for entry in entries if entry.status == "archived"]
    unknown = [entry for entry in entries if entry.lifecycle == "unknown"]
    integrity_errors = [
        entry for entry in entries
        if entry.sqlite.get("open_status") != "ok" or entry.sqlite.get("integrity_check") != "ok"
    ]

    sidecars = [
        sidecar
        for entry in entries
        for sidecar in entry.sidecars
    ]
    archive_candidate_sidecars = [
        sidecar
        for entry in archive_candidates
        for sidecar in entry.sidecars
    ]
    archive_ready_sidecars = [
        sidecar
        for entry in archive_ready
        for sidecar in entry.sidecars
    ]

    return {
        "status": "needs_review" if unknown or integrity_errors else "ready_for_owner_decision",
        "generated_at_utc": utc_now(),
        "workspace_root": str(ROOT),
        "scope": "tmp/**/*.sqlite, state/**/*.sqlite, and SQLite sidecars",
        "authority_boundary": {
            "read_only": True,
            "apply_allowed": False,
            "archive_apply_allowed": False,
            "delete_apply_allowed": False,
            "owner_approval_required_before_move_or_delete": True,
            "canon_or_portfolio_mutation": False,
            "brokerage_or_execution_authority": False,
        },
        "summary": {
            "database_count": len(entries),
            "sidecar_count": len(sidecars),
            "lifecycle_counts": counts,
            "archive_candidate_count": len(archive_candidates),
            "archive_ready_count": len(archive_ready),
            "archived_count": len(archived_entries),
            "archive_candidate_sidecar_count": len(archive_candidate_sidecars),
            "archive_ready_sidecar_count": len(archive_ready_sidecars),
            "delete_ready_count": 0,
            "archive_candidate_bytes": sum(entry.size_bytes for entry in archive_candidates),
            "archive_candidate_sidecar_bytes": sum(int(sidecar.get("size_bytes") or 0) for sidecar in archive_candidate_sidecars),
            "archive_candidate_total_bytes": (
                sum(entry.size_bytes for entry in archive_candidates)
                + sum(int(sidecar.get("size_bytes") or 0) for sidecar in archive_candidate_sidecars)
            ),
            "archive_ready_bytes": sum(entry.size_bytes for entry in archive_ready),
            "archive_ready_sidecar_bytes": sum(int(sidecar.get("size_bytes") or 0) for sidecar in archive_ready_sidecars),
            "archive_ready_total_bytes": (
                sum(entry.size_bytes for entry in archive_ready)
                + sum(int(sidecar.get("size_bytes") or 0) for sidecar in archive_ready_sidecars)
            ),
            "unknown_count": len(unknown),
            "integrity_error_count": len(integrity_errors),
            "archive_approval_packet": rel(ARCHIVE_APPROVAL_PACKET),
        },
        "recommended_owner_decision": {
            "archive_now_after_approval": [entry.path for entry in archive_ready],
            "archive_after_reference_review": [
                entry.path for entry in archive_candidates if not entry.archive_ready
            ],
            "keep_protected": [
                entry.path for entry in entries if entry.lifecycle in {"live", "derived"}
            ],
            "conditional_keep": [
                entry.path for entry in entries if entry.status == "conditional_keep"
            ],
            "delete_now": [],
            "already_archived": [entry.path for entry in archived_entries],
        },
        "entries": [asdict(entry) for entry in entries],
    }


def build_archive_approval_packet(manifest: dict[str, Any]) -> dict[str, Any]:
    entries = manifest.get("entries") or []
    selected = [
        entry for entry in entries
        if entry.get("basename") in ARCHIVE_APPROVAL_TARGET_BASENAMES
    ]
    missing_targets = sorted(
        ARCHIVE_APPROVAL_TARGET_BASENAMES
        - {str(entry.get("basename")) for entry in selected}
    )
    candidates: list[dict[str, Any]] = []
    for entry in selected:
        ready = bool(entry.get("archive_ready"))
        candidates.append({
            "path": entry.get("path"),
            "basename": entry.get("basename"),
            "decision_status": "ready_for_owner_archive_decision" if ready else "not_ready_for_archive",
            "archive_ready": ready,
            "delete_ready": False,
            "owner_approval_required": True,
            "apply_allowed": False,
            "source": entry.get("path"),
            "destination": entry.get("proposed_destination"),
            "sha256": entry.get("sha256"),
            "size_bytes": entry.get("size_bytes"),
            "mtime_utc": entry.get("mtime_utc"),
            "sidecars": entry.get("sidecars") or [],
            "references": {
                "active_reference_count": entry.get("active_reference_count"),
                "operational_reference_count": entry.get("operational_reference_count"),
                "total_reference_count": entry.get("total_reference_count"),
                "classification": entry.get("reference_classification") or {},
                "notes": entry.get("reference_notes") or [],
            },
            "evidence": entry.get("evidence") or [],
            "blockers": entry.get("blockers") or [],
            "rollback_path": rollback_path_for(entry),
        })
    return {
        "schema": "veritas.db_lifecycle_archive_approval_packet.v1",
        "status": "owner_decision_required",
        "generated_at_utc": manifest.get("generated_at_utc"),
        "source_manifest": rel(JSON_REPORT),
        "authority_boundary": {
            "review_packet_only": True,
            "apply_allowed": False,
            "archive_apply_allowed": False,
            "delete_apply_allowed": False,
            "owner_approval_required_before_move_or_delete": True,
            "canon_or_portfolio_mutation": False,
            "brokerage_or_execution_authority": False,
        },
        "scope": {
            "requested_targets": sorted(ARCHIVE_APPROVAL_TARGET_BASENAMES),
            "missing_targets": missing_targets,
            "archive_ready_targets": [
                candidate["path"] for candidate in candidates
                if candidate.get("archive_ready")
            ],
            "not_ready_targets": [
                candidate["path"] for candidate in candidates
                if not candidate.get("archive_ready")
            ],
        },
        "validation_commands": [
            "python scripts\\db_lifecycle_manifest.py --write --validate",
            "python scripts\\workflow_router.py WF84 --answer all --validate",
            "python scripts\\workflow_router.py WF85 --answer all --validate",
            "python scripts\\workflow_router.py WF72 --answer all --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate",
            "python scripts\\cron_control_packet.py --write --validate",
            "python scripts\\fast_path_qa.py --write --validate",
            "python scripts\\artifact_index.py validate",
        ],
        "candidates": candidates,
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = manifest.get("authority_boundary", {})
    for key in ("apply_allowed", "archive_apply_allowed", "delete_apply_allowed", "canon_or_portfolio_mutation", "brokerage_or_execution_authority"):
        if boundary.get(key) is not False:
            errors.append(f"authority boundary {key} must be false")
    entries = manifest.get("entries", [])
    if not entries:
        errors.append("no database entries found")
    for entry in entries:
        lifecycle = entry.get("lifecycle")
        if lifecycle == "unknown":
            errors.append(f"{entry.get('path')} is unclassified")
        if entry.get("apply_allowed") is not False:
            errors.append(f"{entry.get('path')} has apply_allowed not false")
        if entry.get("delete_ready"):
            errors.append(f"{entry.get('path')} unexpectedly delete-ready")
        if entry.get("archive_ready") and int(entry.get("operational_reference_count") or 0) != 0:
            errors.append(f"{entry.get('path')} archive-ready with active operational references")
        if entry.get("archive_ready") and not entry.get("proposed_destination"):
            errors.append(f"{entry.get('path')} archive-ready without destination")
        if lifecycle in {"live", "derived"} and entry.get("archive_ready"):
            errors.append(f"{entry.get('path')} protected lifecycle marked archive-ready")
        sqlite_meta = entry.get("sqlite") or {}
        if sqlite_meta.get("open_status") != "ok":
            errors.append(f"{entry.get('path')} SQLite open failed: {sqlite_meta.get('error')}")
        if sqlite_meta.get("integrity_check") != "ok":
            errors.append(f"{entry.get('path')} integrity not ok: {sqlite_meta.get('integrity_check')}")
        if not entry.get("sha256"):
            errors.append(f"{entry.get('path')} missing sha256")
    return errors


def markdown_report(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# DB Lifecycle Manifest",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Generated UTC: `{manifest['generated_at_utc']}`",
        f"- Databases: `{summary['database_count']}`",
        f"- Archive candidates: `{summary['archive_candidate_count']}` / ready now `{summary['archive_ready_count']}`",
        f"- Delete-ready: `{summary['delete_ready_count']}`",
        f"- Archive candidate bytes: `{summary['archive_candidate_bytes']}`",
        "",
        "Authority boundary: read-only manifest only. No move, delete, rewrite, vacuum, checkpoint, canon mutation, portfolio mutation, or brokerage/execution authority.",
        "",
        "## Decision",
        "",
        "Archive after approval:",
    ]
    archive_now = manifest["recommended_owner_decision"]["archive_now_after_approval"]
    if archive_now:
        lines.extend(f"- `{path}`" for path in archive_now)
    else:
        lines.append("- None")
    lines.extend(["", "Keep protected:"])
    lines.extend(f"- `{path}`" for path in manifest["recommended_owner_decision"]["keep_protected"])
    lines.extend(["", "Conditional keep:"])
    conditional = manifest["recommended_owner_decision"]["conditional_keep"]
    if conditional:
        lines.extend(f"- `{path}`" for path in conditional)
    else:
        lines.append("- None")
    lines.extend(["", "## Inventory", ""])
    lines.append("| Path | Lifecycle | Status | Size | Active refs | Recommendation |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for entry in manifest["entries"]:
        rec = str(entry["recommendation"]).replace("|", "/")
        lines.append(
            f"| `{entry['path']}` | `{entry['lifecycle']}` | `{entry['status']}` | "
            f"{entry['size_bytes']} | {entry['active_reference_count']} | {rec} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write JSON manifest")
    parser.add_argument("--write-md", action="store_true", help="write Markdown sidecar")
    parser.add_argument("--validate", action="store_true", help="fail if manifest has classification/integrity errors")
    parser.add_argument("--pretty", action="store_true", help="print pretty JSON")
    args = parser.parse_args()

    manifest = build_manifest()
    errors = validate_manifest(manifest)
    if errors:
        manifest["status"] = "validation_error"
        manifest["validation_errors"] = errors
    else:
        manifest["validation_errors"] = []
    archive_approval_packet = build_archive_approval_packet(manifest)

    if args.write:
        atomic_write_json(JSON_REPORT, manifest)
        atomic_write_json(ARCHIVE_APPROVAL_PACKET, archive_approval_packet)
    if args.write_md:
        atomic_write_text(MD_REPORT, markdown_report(manifest))

    if args.pretty or not args.write:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({
            "status": manifest["status"],
            "summary": manifest["summary"],
            "json": rel(JSON_REPORT),
            "markdown": rel(MD_REPORT) if args.write_md else None,
            "archive_approval_packet": rel(ARCHIVE_APPROVAL_PACKET),
            "validation_errors": errors,
        }, indent=2))

    if args.validate and errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
