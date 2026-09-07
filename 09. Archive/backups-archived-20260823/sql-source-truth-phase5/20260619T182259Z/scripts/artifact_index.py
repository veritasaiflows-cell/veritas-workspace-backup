from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from market_data_utils import load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_DB = TMP / "veritas-artifact-index.sqlite"
SCHEMA_VERSION = 7
SQL_AUTHORITY_BOUNDARY = "derived_review_only_index_not_canon_not_apply"
FORBIDDEN_TRUE_AUTHORITY_FLAGS = {
    "trade_execution_allowed",
    "live_trade_or_account_action_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "generated_report_is_canonical",
    "paper_trade_submit_cancel_allowed_by_today_card",
}

MARKET_EVENT_GLOBS = ["market-intelligence-events-*.json"]
DAILY_REVIEW_GLOBS = ["daily-review-objects-*.json"]
TRUTH_SPINE_FILES = [
    "today-card.json",
    "today-card-validation.json",
    "today-card-published-validation.json",
    "current-window-artifacts.json",
    "dashboard-validation.json",
    "dashboard-data.json",
    "dashboard-presentation-dto.json",
    "dashboard-presentation-dto-design.json",
    "dashboard-presentation-compatibility-proof.json",
    "dashboard-presentation-adapter.json",
    "dashboard-presentation-view-model.json",
    "dashboard-presentation-renderer-validation.json",
    "dashboard-presentation-acceptance.json",
    "dashboard-data-thin-preview.json",
    "dashboard-data-thin-preview-validation.json",
    "dashboard-v2-reader-migration.json",
    "dashboard-compact-shell-validation.json",
    "dashboard-compact-shell-acceptance.json",
    "dashboard-shrink-readiness-score.json",
    "dashboard-compatibility-payload.json",
    "dashboard-compatibility-payload-validation.json",
    "presentation-artifact-flattening-inventory.json",
    "presentation-render-default-compatibility.json",
    "presentation-retrieval-route-map.json",
    "presentation-retrieval-enforcement.json",
    "workflow-routing-index.json",
    "workflow-routing-index-validation.json",
    "concurrent-lane-register.json",
    "parallel-lane-recommendation.json",
    "truth-surface-inventory.json",
    "route-efficiency-scorecard.json",
    "fast-path-qa.json",
    "parallel-repeatable-work-orchestration.json",
    "macro-event-guard-loop.json",
    "macro-energy-supply.json",
    "macro-geopolitical-sweep.json",
    "wf78-owner-card-prep-loop.json",
    "wf78-tier-a-evidence-repair-batch.json",
    "repeatable-work-closeout.json",
    "finance-decision-factory.json",
    "post-close-final-quote-ledger.json",
    "wf78-evidence-repair-batch.json",
    "wf78-evidence-family-repair.json",
    "wf78-source-open-repair-execution.json",
    "wf78-source-open-work-packets.json",
    "wf78-position-sizing-surface-review.json",
    "wf78-deployment-readiness-review.json",
    "wf78-source-artifact-capture-review.json",
    "wf78-position-sizing-integration-proposal.json",
    "wf78-tier-a-owner-readiness-proposals.json",
    "wf78-missing-band-context-repair.json",
    "wf78-source-capture-requirements-queue.json",
    "wf78-official-source-discovery.json",
    "wf78-official-registry-proposal.json",
    "wf78-official-registry-apply-preview.json",
    "wf78-official-registry-proposed.preview.json",
    "wf78-promotion-owner-lineage-queue.json",
    "wf78-contract-state-guard.json",
    "wf78-owner-lineage-discovery.json",
    "wf78-owner-lineage-proposal.json",
    "wf78-repair-debt-scoreboard.json",
    "wf78-scaleout-policy-dry-run.json",
    "wf78-ph-owner-review-candidate-packet.json",
    "wf78-tier-a-invalidation-review-queue.json",
    "wf78-official-source-capture-packet.json",
    "wf78-next-owner-review-and-source-capture-integration.json",
    "wf78-ticker-freshness-ledger.json",
    "tier-c-band-status.json",
    "wf78-tier-weighted-freshness-resolution.json",
    "wf78-daily-freshness-loop.json",
    "canonical-finance-data-plane-contract.json",
    "canonical-finance-data-plane.json",
    "canonical-finance-data-plane-validation.json",
    "canonical-finance-data-plane-phase6-10.json",
    "canonical-finance-data-plane-retirement-readiness.json",
    "full-answer-parity-rollup.json",
    "trade-grade-decision-os-contract.json",
    "trade-grade-source-freshness-gate.json",
    "trade-grade-decision-cards.json",
    "trade-grade-decision-card-authority-validation.json",
    "trade-grade-approval-card-gate.json",
    "trade-grade-risk-sizing-overlay.json",
    "trade-grade-full-answer-assembler.json",
    "ticker-answer-packet-retirement-approval-plan-20260609.json",
    "trade-grade-repair-conveyor.json",
    "trade-grade-os-freshness-cron-runner.json",
    "weekday-morning-review-cron-runner.json",
    "retail-automation-control-plane-cron-runner.json",
    "control-closeout-bundle.json",
    "pm-execution-loop.json",
    "artifact-intelligence-action-scorer.json",
    "wf78-tier-a-confidence-gate.json",
    "wf78-auto-tier-routing.json",
    "wf78-legacy-42-tier-migration-planner.json",
    "wf78-routing-delta.json",
    "wf78-capital-review-queue.json",
    "wf78-event-triggered-rerouting.json",
    "wf78-evidence-drag-reduction.json",
    "market-execution-readiness-cron-hardening.json",
    "wf78-packet-summary-consolidation.json",
    "wf78-packet-shared-header.json",
    "deployment-readiness-surface.json",
    "research-freshness-opportunity-review.json",
    "capital-deployment-recommendation-validation.json",
    "otel-ops-control.json",
    "otel-ops-window-summary.json",
    "otel/control-loop.json",
    "model-run-ledger-current.json",
    "finance-recommendation-correctness-ledger-current.json",
    "model-quality-scorecard.json",
    "earnings-calendar.json",
    "earnings-date-source-confidence.json",
    "post-earnings-prep.json",
    "post-earnings-note-targets.json",
    "event-calendar-rollforward.json",
    "finance-intelligence-state-paper-positions.json",
    "finance-intelligence-state-live-pilot.json",
    "wf78-live-25-pilot-import-gate.json",
    "wf72-finance-canon-cleanup-proposals.json",
    "wf72-phase2-canon-sync-apply.json",
]
FILE_STATE_ONLY_FILES = [
    "workflow-routing-index.sqlite",
    "wf78-legacy-42-tier-state-shadow.sqlite",
    "canonical-finance-data-plane.sqlite",
]
INDEXED_TABLES = [
    "artifact_runs", "market_events", "daily_review_objects", "capital_recommendations",
    "source_artifacts", "validator_runs", "authority_flags", "canon_proposals",
    "today_decision_items", "official_ir_capture_runs", "official_ir_capture_fields",
    "source_field_lineage", "canon_proposal_staging", "canon_proposal_evidence_links",
    "earnings_lifecycle_events", "dashboard_findings", "source_freshness_rows",
    "deployment_readiness_rows", "artifact_file_state",
]
DRIFT_FINGERPRINT_EXCLUDED_COLUMNS = {
    "id",
    "artifact_run_id",
    "capture_run_id",
    "canon_proposal_staging_id",
    "downstream_artifact_run_id",
    "downstream_row_id",
    "upstream_artifact_run_id",
    "upstream_row_id",
    "artifact_run_id",
    "indexed_at_utc",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return as_json(value)
    return str(value)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def sha_text(value: Any) -> str:
    return hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iter_artifact_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in [*MARKET_EVENT_GLOBS, *DAILY_REVIEW_GLOBS]:
        paths.extend(sorted(TMP.glob(pattern)))
    captures_dir = TMP / "official-ir-captures"
    if captures_dir.exists():
        for path in sorted(captures_dir.glob("*.json")):
            if path.name.endswith("-validation.json") or path.name == "all-validation.json":
                continue
            paths.append(path)
    for name in TRUTH_SPINE_FILES:
        path = TMP / name
        if path.exists():
            paths.append(path)
    for name in FILE_STATE_ONLY_FILES:
        path = TMP / name
        if path.exists():
            paths.append(path)
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

        CREATE TABLE IF NOT EXISTS artifact_file_state (
            source_file TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            file_mtime_utc TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_sha256 TEXT,
            artifact_run_id INTEGER REFERENCES artifact_runs(id) ON DELETE SET NULL,
            indexed_at_utc TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'indexed'
        ) STRICT;

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

        CREATE TABLE IF NOT EXISTS source_artifacts (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            role TEXT NOT NULL,
            path TEXT,
            required INTEGER NOT NULL DEFAULT 0,
            exists_flag INTEGER NOT NULL DEFAULT 0,
            status TEXT,
            generated_at_utc TEXT,
            read_status TEXT,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS validator_runs (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            validator_name TEXT NOT NULL,
            status TEXT,
            critical INTEGER NOT NULL DEFAULT 0,
            warning INTEGER NOT NULL DEFAULT 0,
            checked_count INTEGER,
            authority_json TEXT NOT NULL DEFAULT '{}',
            summary_json TEXT NOT NULL DEFAULT '{}',
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS authority_flags (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            surface TEXT NOT NULL,
            flag_name TEXT NOT NULL,
            flag_value INTEGER NOT NULL,
            raw_value TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_proposals (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            proposal_id TEXT,
            target_file TEXT,
            drift_class TEXT,
            authority_classification TEXT,
            requires_owner_approval INTEGER NOT NULL DEFAULT 1,
            applied INTEGER NOT NULL DEFAULT 0,
            status TEXT,
            old_text_sha256 TEXT,
            new_text_sha256 TEXT,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS today_decision_items (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            rank INTEGER,
            ticker TEXT,
            item_state TEXT,
            recommendation_posture TEXT,
            owner_action_needed INTEGER NOT NULL DEFAULT 0,
            close REAL,
            band_low REAL,
            band_high REAL,
            entry_band_status TEXT,
            authority_boundary TEXT,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS official_ir_capture_runs (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL UNIQUE,
            ticker TEXT NOT NULL,
            company_name TEXT,
            period_end TEXT,
            capture_generated_at_utc TEXT,
            review_only INTEGER NOT NULL DEFAULT 1,
            resolved_for_apply INTEGER NOT NULL DEFAULT 0,
            source_type TEXT,
            source_url TEXT,
            filing_url TEXT,
            accession_number TEXT,
            retrieved_at_utc TEXT,
            source_text_sha256 TEXT,
            source_html_sha256 TEXT,
            source_title TEXT,
            summary_json TEXT NOT NULL DEFAULT '{}',
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS official_ir_capture_fields (
            id INTEGER PRIMARY KEY,
            capture_run_id INTEGER NOT NULL REFERENCES official_ir_capture_runs(id) ON DELETE CASCADE,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            ticker TEXT NOT NULL,
            period TEXT NOT NULL,
            field_name TEXT NOT NULL,
            status TEXT NOT NULL,
            value_json TEXT NOT NULL DEFAULT '{}',
            source_url TEXT,
            source_section TEXT,
            excerpt TEXT,
            excerpt_sha256 TEXT,
            inferred INTEGER NOT NULL DEFAULT 0,
            capture_date_utc TEXT,
            note TEXT,
            manual_required INTEGER NOT NULL DEFAULT 0,
            not_disclosed INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS source_field_lineage (
            id INTEGER PRIMARY KEY,
            downstream_artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            downstream_source_file TEXT NOT NULL,
            downstream_table TEXT NOT NULL,
            downstream_row_id INTEGER,
            downstream_field TEXT NOT NULL,
            lineage_kind TEXT NOT NULL,
            upstream_artifact_run_id INTEGER REFERENCES artifact_runs(id) ON DELETE SET NULL,
            upstream_source_file TEXT,
            upstream_table TEXT,
            upstream_row_id INTEGER,
            upstream_field TEXT,
            upstream_source_url TEXT,
            upstream_source_section TEXT,
            upstream_excerpt_sha256 TEXT,
            confidence TEXT NOT NULL DEFAULT 'direct_or_declared',
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_proposal_staging (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            target_file TEXT NOT NULL,
            target_section TEXT,
            proposal_kind TEXT NOT NULL,
            authority_classification TEXT,
            requires_owner_approval INTEGER NOT NULL DEFAULT 1,
            proposal_apply_allowed INTEGER NOT NULL DEFAULT 0,
            applied INTEGER NOT NULL DEFAULT 0,
            old_text_sha256 TEXT,
            new_text_sha256 TEXT,
            diff_sha256 TEXT,
            evidence_status TEXT NOT NULL DEFAULT 'unstaged',
            validator_status TEXT,
            source_lineage_status TEXT NOT NULL DEFAULT 'unverified',
            status TEXT NOT NULL DEFAULT 'review_only_staged',
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_proposal_evidence_links (
            id INTEGER PRIMARY KEY,
            canon_proposal_staging_id INTEGER NOT NULL REFERENCES canon_proposal_staging(id) ON DELETE CASCADE,
            evidence_kind TEXT NOT NULL,
            evidence_table TEXT NOT NULL,
            evidence_row_id INTEGER,
            evidence_source_file TEXT,
            evidence_field TEXT,
            evidence_sha256 TEXT,
            evidence_url TEXT,
            required INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'linked',
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS earnings_lifecycle_events (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            ticker TEXT NOT NULL,
            event_kind TEXT NOT NULL,
            lifecycle_status TEXT,
            watchlist_date TEXT,
            provider_date_before_closeout TEXT,
            last_earnings_date TEXT,
            post_earnings_review_date TEXT,
            post_earnings_review_confirmed INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            review_only INTEGER NOT NULL DEFAULT 1,
            portfolio_mutation_allowed INTEGER NOT NULL DEFAULT 0,
            canonical_note_mutation_allowed INTEGER NOT NULL DEFAULT 0,
            trade_or_account_action_allowed INTEGER NOT NULL DEFAULT 0,
            owner_approval_inferred INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS dashboard_findings (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            finding_kind TEXT NOT NULL,
            code TEXT,
            severity TEXT,
            scope TEXT,
            ticker TEXT,
            message TEXT,
            stop_line INTEGER NOT NULL DEFAULT 0,
            review_only INTEGER NOT NULL DEFAULT 1,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS source_freshness_rows (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            source_key TEXT NOT NULL,
            path TEXT,
            classification TEXT,
            trust_level TEXT,
            criticality TEXT,
            owner_layer TEXT,
            usable_for_review INTEGER NOT NULL DEFAULT 0,
            usable_for_presentation INTEGER NOT NULL DEFAULT 0,
            usable_for_canonical_mutation INTEGER NOT NULL DEFAULT 0,
            stop_line INTEGER NOT NULL DEFAULT 0,
            generated_at_utc TEXT,
            age_hours REAL,
            stale_after_hours REAL,
            confidence_ceiling TEXT,
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE IF NOT EXISTS deployment_readiness_rows (
            id INTEGER PRIMARY KEY,
            artifact_run_id INTEGER NOT NULL REFERENCES artifact_runs(id) ON DELETE CASCADE,
            source_file TEXT NOT NULL,
            ticker TEXT NOT NULL,
            bucket TEXT NOT NULL,
            surface_state TEXT,
            base_surface_state TEXT,
            workflow_state TEXT,
            machine_state TEXT,
            close REAL,
            band_position TEXT,
            macro_gate TEXT,
            review_only_no_apply_artifact INTEGER NOT NULL DEFAULT 0,
            band_stale INTEGER NOT NULL DEFAULT 0,
            post_earnings_review_confirmed INTEGER NOT NULL DEFAULT 0,
            next_earnings_date TEXT,
            catalyst_blocker TEXT,
            source_artifact_path TEXT,
            source_generated_at_utc TEXT,
            authority_boundary TEXT NOT NULL DEFAULT 'review_only_dashboard_surface_not_apply',
            raw_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE INDEX IF NOT EXISTS idx_artifact_runs_type_window ON artifact_runs(artifact_type, window, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_artifact_runs_window_latest ON artifact_runs(window, generated_at_utc DESC, artifact_type);
        CREATE INDEX IF NOT EXISTS idx_artifact_file_state_status ON artifact_file_state(status, indexed_at_utc);
        CREATE INDEX IF NOT EXISTS idx_market_events_ticker ON market_events(ticker_or_macro_sleeve, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_market_events_ticker_upper_time ON market_events(upper(ticker_or_macro_sleeve), generated_at_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_market_events_route ON market_events(recommended_route, urgency, materiality_score);
        CREATE INDEX IF NOT EXISTS idx_market_events_escalations_latest ON market_events(generated_at_utc DESC, materiality_score DESC) WHERE list_name='escalations';
        CREATE INDEX IF NOT EXISTS idx_daily_review_ticker ON daily_review_objects(ticker, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_daily_review_ticker_upper_time ON daily_review_objects(upper(ticker), generated_at_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_daily_review_category ON daily_review_objects(category, signal_score);
        CREATE INDEX IF NOT EXISTS idx_daily_review_escalations_latest ON daily_review_objects(generated_at_utc DESC, signal_score DESC) WHERE list_name='escalations';
        CREATE INDEX IF NOT EXISTS idx_capital_recs_ticker ON capital_recommendations(ticker, generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_capital_recs_ticker_upper_time ON capital_recommendations(upper(ticker), generated_at_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_capital_recs_action ON capital_recommendations(recommended_action, confidence);
        CREATE INDEX IF NOT EXISTS idx_source_artifacts_role ON source_artifacts(role, status);
        CREATE INDEX IF NOT EXISTS idx_validator_runs_name ON validator_runs(validator_name, status);
        CREATE INDEX IF NOT EXISTS idx_validator_runs_status_severity ON validator_runs(status, critical DESC, warning DESC);
        CREATE INDEX IF NOT EXISTS idx_authority_flags_name ON authority_flags(flag_name, flag_value);
        CREATE INDEX IF NOT EXISTS idx_canon_proposals_target ON canon_proposals(target_file, status);
        CREATE INDEX IF NOT EXISTS idx_today_decision_ticker ON today_decision_items(ticker, rank);
        CREATE INDEX IF NOT EXISTS idx_official_ir_runs_ticker_period ON official_ir_capture_runs(ticker, period_end, capture_generated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_official_ir_runs_source_hash ON official_ir_capture_runs(source_text_sha256, source_url);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_official_ir_field_once ON official_ir_capture_fields(capture_run_id, field_name);
        CREATE INDEX IF NOT EXISTS idx_official_ir_fields_ticker_field ON official_ir_capture_fields(ticker, field_name, period);
        CREATE INDEX IF NOT EXISTS idx_official_ir_fields_status ON official_ir_capture_fields(status, manual_required, not_disclosed);
        CREATE INDEX IF NOT EXISTS idx_official_ir_fields_excerpt_hash ON official_ir_capture_fields(excerpt_sha256);
        CREATE INDEX IF NOT EXISTS idx_source_lineage_downstream ON source_field_lineage(downstream_source_file, downstream_field);
        CREATE INDEX IF NOT EXISTS idx_source_lineage_upstream ON source_field_lineage(upstream_source_file, upstream_field);
        CREATE INDEX IF NOT EXISTS idx_source_lineage_kind ON source_field_lineage(lineage_kind, confidence);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_canon_stage_proposal ON canon_proposal_staging(proposal_id, target_file);
        CREATE INDEX IF NOT EXISTS idx_canon_stage_target ON canon_proposal_staging(target_file, status);
        CREATE INDEX IF NOT EXISTS idx_canon_stage_stopline ON canon_proposal_staging(proposal_apply_allowed, applied, requires_owner_approval, status);
        CREATE INDEX IF NOT EXISTS idx_canon_stage_authority ON canon_proposal_staging(requires_owner_approval, proposal_apply_allowed, applied);
        CREATE INDEX IF NOT EXISTS idx_canon_stage_lineage ON canon_proposal_staging(source_lineage_status, evidence_status, validator_status);
        CREATE INDEX IF NOT EXISTS idx_canon_evidence_stage ON canon_proposal_evidence_links(canon_proposal_staging_id, evidence_kind);
        CREATE INDEX IF NOT EXISTS idx_canon_evidence_source ON canon_proposal_evidence_links(evidence_source_file, evidence_field);
        CREATE INDEX IF NOT EXISTS idx_earnings_lifecycle_ticker_time ON earnings_lifecycle_events(upper(ticker), watchlist_date DESC, event_kind);
        CREATE INDEX IF NOT EXISTS idx_earnings_lifecycle_status ON earnings_lifecycle_events(lifecycle_status, event_kind);
        CREATE INDEX IF NOT EXISTS idx_dashboard_findings_code ON dashboard_findings(severity, code, scope);
        CREATE INDEX IF NOT EXISTS idx_source_freshness_key ON source_freshness_rows(source_key, classification, stop_line);
        CREATE INDEX IF NOT EXISTS idx_deployment_readiness_ticker ON deployment_readiness_rows(upper(ticker), bucket, surface_state);

        DROP VIEW IF EXISTS v_cockpit_action_queue_deduped;
        DROP VIEW IF EXISTS v_cockpit_action_queue;
        DROP VIEW IF EXISTS v_cockpit_ticker_timeline;
        DROP VIEW IF EXISTS v_cockpit_trust_boundary;
        DROP VIEW IF EXISTS v_cockpit_official_source_fields;
        DROP VIEW IF EXISTS v_cockpit_canon_staging;
        DROP VIEW IF EXISTS v_cockpit_earnings_lifecycle;
        DROP VIEW IF EXISTS v_cockpit_dashboard_findings;
        DROP VIEW IF EXISTS v_cockpit_source_freshness;
        DROP VIEW IF EXISTS v_cockpit_deployment_readiness;

        CREATE VIEW IF NOT EXISTS v_cockpit_action_queue AS
        SELECT 'today' AS priority_kind, ticker, recommendation_posture AS route, entry_band_status AS urgency,
               rank AS score, item_state AS action_text, owner_action_needed, authority_boundary,
               source_file, NULL AS generated_at_utc
        FROM today_decision_items
        UNION ALL
        SELECT 'capital' AS priority_kind, ticker, recommended_action AS route, entry_band_status AS urgency,
               rank AS score, guidance AS action_text, owner_approval_required AS owner_action_needed,
               trust_ceiling AS authority_boundary, source_file, generated_at_utc
        FROM capital_recommendations
        UNION ALL
        SELECT 'daily_escalation' AS priority_kind, ticker, recommended_route AS route, urgency,
               signal_score AS score, COALESCE(recommended_next_step, why_now, object_id) AS action_text,
               owner_review_required AS owner_action_needed, 'review_only_owner_gated' AS authority_boundary,
               source_file, generated_at_utc
        FROM daily_review_objects WHERE list_name='escalations'
        UNION ALL
        SELECT 'market_escalation' AS priority_kind, ticker_or_macro_sleeve AS ticker, recommended_route AS route, urgency,
               materiality_score AS score, event_title AS action_text, owner_review_required AS owner_action_needed,
               COALESCE(blocked_reason, 'review_only_owner_gated') AS authority_boundary,
               source_file, generated_at_utc
        FROM market_events WHERE list_name='escalations';

        CREATE VIEW IF NOT EXISTS v_cockpit_action_queue_deduped AS
        WITH ranked AS (
            SELECT
                priority_kind, ticker, route, urgency, score, action_text,
                owner_action_needed, authority_boundary, source_file, generated_at_utc,
                lower(trim(coalesce(priority_kind, ''))) || '|' ||
                lower(trim(coalesce(ticker, ''))) || '|' ||
                lower(trim(coalesce(route, ''))) || '|' ||
                lower(trim(coalesce(urgency, ''))) || '|' ||
                lower(trim(coalesce(action_text, ''))) || '|' ||
                lower(trim(coalesce(owner_action_needed, ''))) || '|' ||
                lower(trim(coalesce(authority_boundary, ''))) AS action_dedupe_key,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        lower(trim(coalesce(priority_kind, ''))),
                        lower(trim(coalesce(ticker, ''))),
                        lower(trim(coalesce(route, ''))),
                        lower(trim(coalesce(urgency, ''))),
                        lower(trim(coalesce(action_text, ''))),
                        lower(trim(coalesce(owner_action_needed, ''))),
                        lower(trim(coalesce(authority_boundary, '')))
                    ORDER BY
                        coalesce(generated_at_utc, '') DESC,
                        CAST(coalesce(score, 0) AS REAL) DESC,
                        source_file DESC
                ) AS action_dedupe_rank
            FROM v_cockpit_action_queue
        )
        SELECT
            priority_kind, ticker, route, urgency, score, action_text,
            owner_action_needed, authority_boundary, source_file, generated_at_utc,
            action_dedupe_key, action_dedupe_rank
        FROM ranked
        WHERE action_dedupe_rank=1;

        CREATE VIEW IF NOT EXISTS v_cockpit_ticker_timeline AS
        SELECT ticker_or_macro_sleeve AS ticker, 'market_event' AS kind, source_file, generated_at_utc,
               recommended_route AS route, urgency AS status, materiality_score AS score, event_title AS summary
        FROM market_events WHERE ticker_or_macro_sleeve IS NOT NULL AND ticker_or_macro_sleeve != ''
        UNION ALL
        SELECT ticker, 'daily_review' AS kind, source_file, generated_at_utc,
               recommended_route AS route, COALESCE(surface_state, urgency) AS status, signal_score AS score,
               COALESCE(recommended_next_step, why_now, object_id) AS summary
        FROM daily_review_objects WHERE ticker IS NOT NULL AND ticker != ''
        UNION ALL
        SELECT ticker, 'capital_recommendation' AS kind, source_file, generated_at_utc,
               recommended_action AS route, entry_band_status AS status, rank AS score, guidance AS summary
        FROM capital_recommendations WHERE ticker IS NOT NULL AND ticker != ''
        UNION ALL
        SELECT ticker, 'official_ir_field' AS kind, source_file, capture_date_utc AS generated_at_utc,
               field_name AS route, status, NULL AS score, source_section AS summary
        FROM official_ir_capture_fields WHERE ticker IS NOT NULL AND ticker != ''
        UNION ALL
        SELECT e.ticker, 'earnings_lifecycle' AS kind, e.source_file,
               COALESCE(ar.generated_at_utc, e.watchlist_date) AS generated_at_utc,
               e.event_kind AS route, e.lifecycle_status AS status, NULL AS score,
               COALESCE(e.reason, 'earnings lifecycle event') AS summary
        FROM earnings_lifecycle_events e
        LEFT JOIN artifact_runs ar ON ar.id=e.artifact_run_id
        WHERE e.ticker IS NOT NULL AND e.ticker != ''
        UNION ALL
        SELECT d.ticker, 'deployment_readiness' AS kind, d.source_file,
               COALESCE(ar.generated_at_utc, d.source_generated_at_utc) AS generated_at_utc,
               d.bucket AS route, d.surface_state AS status, NULL AS score,
               COALESCE(d.catalyst_blocker, d.band_position, d.machine_state) AS summary
        FROM deployment_readiness_rows d
        LEFT JOIN artifact_runs ar ON ar.id=d.artifact_run_id
        WHERE d.ticker IS NOT NULL AND d.ticker != '';

        CREATE VIEW IF NOT EXISTS v_cockpit_deployment_readiness AS
        SELECT ticker, bucket, surface_state, base_surface_state, workflow_state, machine_state,
               close, band_position, macro_gate, review_only_no_apply_artifact, band_stale,
               post_earnings_review_confirmed, next_earnings_date, catalyst_blocker,
               source_artifact_path, source_generated_at_utc, source_file, authority_boundary
        FROM deployment_readiness_rows;

        CREATE VIEW IF NOT EXISTS v_cockpit_dashboard_findings AS
        SELECT finding_kind, code, severity, scope, ticker, message, stop_line, review_only,
               source_file, 'review_only_validation_finding_not_apply' AS authority_boundary
        FROM dashboard_findings;

        CREATE VIEW IF NOT EXISTS v_cockpit_source_freshness AS
        SELECT source_key, path, classification, trust_level, criticality, owner_layer,
               usable_for_review, usable_for_presentation, usable_for_canonical_mutation,
               stop_line, generated_at_utc, age_hours, stale_after_hours, confidence_ceiling,
               source_file, 'review_only_source_freshness_not_apply' AS authority_boundary
        FROM source_freshness_rows;

        CREATE VIEW IF NOT EXISTS v_cockpit_trust_boundary AS
        SELECT ar.source_file, ar.artifact_type, ar.window, ar.generated_at_utc, ar.consumer_posture,
               ar.owner_review_required, ar.canonical_mutation_allowed,
               COALESCE(v.critical, 0) AS critical, COALESCE(v.warning, 0) AS warning,
               COALESCE(f.forbidden_true_flags, 0) AS forbidden_true_flags,
               'derived_review_only_index_not_canon_not_apply' AS authority_boundary
        FROM artifact_runs ar
        LEFT JOIN (
            SELECT artifact_run_id, SUM(critical) AS critical, SUM(warning) AS warning
            FROM validator_runs GROUP BY artifact_run_id
        ) v ON v.artifact_run_id = ar.id
        LEFT JOIN (
            SELECT artifact_run_id, COUNT(*) AS forbidden_true_flags
            FROM authority_flags
            WHERE flag_value != 0
              AND flag_name IN ('trade_execution_allowed', 'live_trade_or_account_action_allowed',
                                'trade_or_account_action_allowed', 'money_movement_allowed',
                                'owner_approval_inferred', 'generated_report_is_canonical',
                                'paper_trade_submit_cancel_allowed_by_today_card')
            GROUP BY artifact_run_id
        ) f ON f.artifact_run_id = ar.id;

        CREATE VIEW IF NOT EXISTS v_cockpit_official_source_fields AS
        SELECT ticker, period, field_name, status, value_json, source_url, source_section,
               excerpt_sha256, manual_required, not_disclosed, inferred, source_file,
               'official_source_review_only_non_apply' AS authority_boundary
        FROM official_ir_capture_fields;

        CREATE VIEW IF NOT EXISTS v_cockpit_canon_staging AS
        SELECT s.proposal_id, s.target_file, s.proposal_kind, s.requires_owner_approval,
               s.proposal_apply_allowed, s.applied, s.evidence_status, s.source_lineage_status,
               COUNT(e.id) AS evidence_links, s.status,
               'review_only_staging_not_apply_engine' AS authority_boundary
        FROM canon_proposal_staging s
        LEFT JOIN canon_proposal_evidence_links e ON e.canon_proposal_staging_id = s.id
        GROUP BY s.id;

        CREATE VIEW IF NOT EXISTS v_cockpit_earnings_lifecycle AS
        SELECT ticker, event_kind, lifecycle_status, watchlist_date, provider_date_before_closeout,
               last_earnings_date, post_earnings_review_date, post_earnings_review_confirmed,
               reason, source_file,
               review_only, portfolio_mutation_allowed, canonical_note_mutation_allowed,
               trade_or_account_action_allowed, owner_approval_inferred,
               'review_only_lifecycle_proof_not_canon_not_apply' AS authority_boundary
        FROM earnings_lifecycle_events;
        """
    )
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))


def reset_index(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM artifact_file_state")
    conn.execute("DELETE FROM market_events")
    conn.execute("DELETE FROM daily_review_objects")
    conn.execute("DELETE FROM capital_recommendations")
    conn.execute("DELETE FROM source_artifacts")
    conn.execute("DELETE FROM validator_runs")
    conn.execute("DELETE FROM authority_flags")
    conn.execute("DELETE FROM canon_proposals")
    conn.execute("DELETE FROM today_decision_items")
    conn.execute("DELETE FROM canon_proposal_evidence_links")
    conn.execute("DELETE FROM canon_proposal_staging")
    conn.execute("DELETE FROM earnings_lifecycle_events")
    conn.execute("DELETE FROM dashboard_findings")
    conn.execute("DELETE FROM source_freshness_rows")
    conn.execute("DELETE FROM deployment_readiness_rows")
    conn.execute("DELETE FROM source_field_lineage")
    conn.execute("DELETE FROM official_ir_capture_fields")
    conn.execute("DELETE FROM official_ir_capture_runs")
    conn.execute("DELETE FROM artifact_runs")


def artifact_type_for(path: Path) -> str:
    name = path.name
    if name.startswith("market-intelligence-events-"):
        return "market_intelligence_events"
    if name.startswith("daily-review-objects-"):
        return "daily_review_objects"
    if name == "today-card.json":
        return "today_card"
    if name in {"today-card-validation.json", "today-card-published-validation.json"}:
        return "today_card_validation"
    if name == "current-window-artifacts.json":
        return "current_window_artifacts"
    if name == "dashboard-validation.json":
        return "dashboard_validation"
    if name == "dashboard-data.json":
        return "dashboard_data"
    if name == "deployment-readiness-surface.json":
        return "deployment_readiness_surface"
    if name == "canonical-finance-data-plane-contract.json":
        return "canonical_finance_data_plane_contract"
    if name == "canonical-finance-data-plane.json":
        return "canonical_finance_data_plane"
    if name == "canonical-finance-data-plane-validation.json":
        return "canonical_finance_data_plane_validation"
    if name == "canonical-finance-data-plane-phase6-10.json":
        return "canonical_finance_data_plane_phase6_10"
    if name == "canonical-finance-data-plane-retirement-readiness.json":
        return "canonical_finance_data_plane_retirement_readiness"
    if name == "full-answer-parity-rollup.json":
        return "full_intelligence_answer_parity"
    if path.parent.name == "full-answer-parity" and name.endswith(".json"):
        return "full_intelligence_answer_parity_ticker"
    if name == "trade-grade-decision-os-contract.json":
        return "trade_grade_decision_os_contract"
    if name == "trade-grade-source-freshness-gate.json":
        return "trade_grade_source_freshness_gate"
    if name == "trade-grade-decision-cards.json":
        return "trade_grade_decision_cards"
    if name == "trade-grade-decision-card-authority-validation.json":
        return "trade_grade_decision_card_authority_validation"
    if name == "trade-grade-approval-card-gate.json":
        return "trade_grade_approval_card_gate"
    if name == "trade-grade-risk-sizing-overlay.json":
        return "trade_grade_risk_sizing_overlay"
    if name == "trade-grade-full-answer-assembler.json":
        return "trade_grade_full_answer_assembler"
    if path.parent.name == "trade-grade-full-answer" and name.endswith(".json"):
        return "trade_grade_full_answer_ticker"
    if name == "ticker-answer-packet-retirement-approval-plan-20260609.json":
        return "ticker_answer_packet_retirement_plan"
    if name == "trade-grade-repair-conveyor.json":
        return "trade_grade_repair_conveyor"
    if name == "trade-grade-os-freshness-cron-runner.json":
        return "trade_grade_os_freshness_cron_runner"
    if name == "weekday-morning-review-cron-runner.json":
        return "weekday_morning_review_cron_runner"
    if name == "retail-automation-control-plane-cron-runner.json":
        return "retail_automation_control_plane_cron_runner"
    if name == "research-freshness-opportunity-review.json":
        return "research_freshness_opportunity_review"
    if name == "capital-deployment-recommendation-validation.json":
        return "capital_deployment_recommendation_validation"
    if name == "earnings-calendar.json":
        return "earnings_calendar"
    if name == "earnings-date-source-confidence.json":
        return "earnings_date_source_confidence"
    if name == "post-earnings-prep.json":
        return "post_earnings_prep"
    if name == "post-earnings-note-targets.json":
        return "post_earnings_note_targets"
    if name == "event-calendar-rollforward.json":
        return "event_calendar_rollforward"
    if name == "wf72-finance-canon-cleanup-proposals.json":
        return "canon_cleanup_proposals"
    if name == "wf72-phase2-canon-sync-apply.json":
        return "canon_sync_apply_audit"
    if path.parent.name == "official-ir-captures" and name.endswith(".json") and not name.endswith("-validation.json") and name != "all-validation.json":
        return "official_ir_capture"
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
            rel(path), artifact_type, str(data.get("window") or "unknown"), int(data.get("schema_version")) if isinstance(data.get("schema_version"), int) or str(data.get("schema_version") or "").isdigit() else None,
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
            legacy_state(item, "surface_state"), item.get("recommended_route"), item.get("urgency"), item.get("materiality_score"),
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


def insert_authority_flags(conn: sqlite3.Connection, run_id: int, source_file: str, surface: str, authority: dict[str, Any]) -> int:
    count = 0
    for key, value in sorted(authority.items()):
        if isinstance(value, bool):
            conn.execute(
                """
                INSERT INTO authority_flags(artifact_run_id, source_file, surface, flag_name, flag_value, raw_value)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, source_file, surface, key, bool_int(value), json.dumps(value)),
            )
            count += 1
    return count


def insert_source_artifacts(conn: sqlite3.Connection, run_id: int, source_file: str, records: list[Any]) -> int:
    count = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        conn.execute(
            """
            INSERT INTO source_artifacts(
                artifact_run_id, source_file, role, path, required, exists_flag,
                status, generated_at_utc, read_status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, source_file, clean_text(record.get("role")), record.get("path"),
                bool_int(record.get("required")), bool_int(record.get("exists")),
                clean_text(record.get("status")), record.get("generated_at_utc"),
                clean_text(record.get("read_status")), as_json(record),
            ),
        )
        count += 1
    return count


def insert_validator_run(conn: sqlite3.Connection, run_id: int, source_file: str, name: str, data: dict[str, Any]) -> None:
    summary = as_dict(data.get("summary"))
    checked = summary.get("captures_checked") or summary.get("packets") or summary.get("bridges") or summary.get("packets_checked")
    conn.execute(
        """
        INSERT INTO validator_runs(
            artifact_run_id, source_file, validator_name, status, critical, warning,
            checked_count, authority_json, summary_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, source_file, name, clean_text(data.get("status")),
            int(summary.get("critical") or summary.get("critical_count") or 0),
            int(summary.get("warning") or summary.get("warning_count") or 0),
            int(checked) if checked is not None else None,
            as_json(data.get("authority") or {}), as_json(summary), as_json(data),
        ),
    )


def insert_today_decision_items(conn: sqlite3.Connection, run_id: int, source_file: str, items: list[Any]) -> int:
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        price = as_dict(item.get("price_vs_band"))
        conn.execute(
            """
            INSERT INTO today_decision_items(
                artifact_run_id, source_file, rank, ticker, item_state, recommendation_posture,
                owner_action_needed, close, band_low, band_high, entry_band_status,
                authority_boundary, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, source_file, item.get("rank"), item.get("ticker_or_scope"), item.get("item_state"),
                item.get("recommendation_posture"), bool_int(item.get("owner_action_needed")),
                price.get("close"), price.get("band_low"), price.get("band_high"), price.get("entry_band_status"),
                clean_text(item.get("authority_boundary")), as_json(item),
            ),
        )
        count += 1
    return count


def insert_canon_proposals(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> int:
    count = 0
    applied_ids = {str(x.get("proposal_id")) for x in as_list(data.get("applied")) if isinstance(x, dict)}
    proposal_rows = as_list(data.get("proposals")) or as_list(data.get("applied"))
    for row in proposal_rows:
        if not isinstance(row, dict):
            continue
        proposal_id = row.get("proposal_id")
        conn.execute(
            """
            INSERT INTO canon_proposals(
                artifact_run_id, source_file, proposal_id, target_file, drift_class,
                authority_classification, requires_owner_approval, applied, status,
                old_text_sha256, new_text_sha256, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, source_file, proposal_id, row.get("target_file"), row.get("drift_class"),
                row.get("authority_classification"), bool_int(row.get("requires_owner_approval", True)),
                bool_int(str(proposal_id) in applied_ids or data.get("schema_version") == "wf72.phase2_canon_sync_apply.v1"),
                clean_text(row.get("status") or data.get("status")),
                sha_text(row.get("exact_old_text")) if row.get("exact_old_text") is not None else None,
                sha_text(row.get("proposed_new_text")) if row.get("proposed_new_text") is not None else None,
                as_json(row),
            ),
        )
        count += 1
    return count


def insert_official_ir_capture(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> dict[str, int]:
    source = as_dict(data.get("source"))
    captures = as_dict(data.get("captures"))
    cur = conn.execute(
        """
        INSERT INTO official_ir_capture_runs(
            artifact_run_id, source_file, ticker, company_name, period_end, capture_generated_at_utc,
            review_only, resolved_for_apply, source_type, source_url, filing_url, accession_number,
            retrieved_at_utc, source_text_sha256, source_html_sha256, source_title, summary_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, source_file, clean_text(data.get("ticker")), clean_text(data.get("company_name")),
            clean_text(data.get("period_end")), clean_text(data.get("generated_at_utc")),
            bool_int(data.get("review_only", True)), bool_int(data.get("resolved_for_apply")),
            clean_text(source.get("source_type")), clean_text(source.get("source_url")), clean_text(source.get("filing_url")),
            clean_text(source.get("accession_number")), clean_text(source.get("retrieved_at_utc")),
            clean_text(source.get("source_text_sha256")), clean_text(source.get("source_html_sha256")),
            clean_text(source.get("source_title")), as_json(data.get("summary") or {}), as_json(data),
        ),
    )
    capture_run_id = int(cur.lastrowid)
    field_count = 0
    lineage_count = 0
    for field_name, capture in sorted(captures.items()):
        if not isinstance(capture, dict):
            continue
        excerpt = clean_text(capture.get("excerpt"))
        status = clean_text(capture.get("status"))
        cur = conn.execute(
            """
            INSERT INTO official_ir_capture_fields(
                capture_run_id, artifact_run_id, source_file, ticker, period, field_name, status,
                value_json, source_url, source_section, excerpt, excerpt_sha256, inferred,
                capture_date_utc, note, manual_required, not_disclosed, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capture_run_id, run_id, source_file, clean_text(data.get("ticker")),
                clean_text(capture.get("period") or data.get("period_end")), clean_text(field_name), status,
                as_json(capture.get("value")), clean_text(capture.get("source_url") or source.get("source_url")),
                clean_text(capture.get("source_section")), excerpt, sha_text(excerpt) if excerpt else None,
                bool_int(capture.get("inferred")), clean_text(capture.get("capture_date_utc")),
                clean_text(capture.get("note")), bool_int(status == "manual_required"),
                bool_int(status == "not_disclosed_in_release"), as_json(capture),
            ),
        )
        field_count += 1
        field_row_id = int(cur.lastrowid)
        if capture.get("source_url") or excerpt:
            conn.execute(
                """
                INSERT INTO source_field_lineage(
                    downstream_artifact_run_id, downstream_source_file, downstream_table, downstream_row_id,
                    downstream_field, lineage_kind, upstream_artifact_run_id, upstream_source_file,
                    upstream_table, upstream_row_id, upstream_field, upstream_source_url,
                    upstream_source_section, upstream_excerpt_sha256, confidence, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, source_file, "official_ir_capture_fields", field_row_id, clean_text(field_name),
                    "official_source_excerpt", run_id, source_file, "official_ir_capture_runs", capture_run_id,
                    clean_text(field_name), clean_text(capture.get("source_url") or source.get("source_url")),
                    clean_text(capture.get("source_section")), sha_text(excerpt) if excerpt else None,
                    "direct_or_declared", as_json({"field_name": field_name, "capture_status": status}),
                ),
            )
            lineage_count += 1
    return {"official_ir_capture_runs": 1, "official_ir_capture_fields": field_count, "source_field_lineage": lineage_count}


def insert_canon_proposal_staging(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> dict[str, int]:
    count = 0
    evidence_count = 0
    applied_ids = {str(x.get("proposal_id")) for x in as_list(data.get("applied")) if isinstance(x, dict)}
    proposal_rows = as_list(data.get("proposals")) or as_list(data.get("applied"))
    for row in proposal_rows:
        if not isinstance(row, dict) or not row.get("proposal_id") or not row.get("target_file"):
            continue
        old_hash = sha_text(row.get("exact_old_text")) if row.get("exact_old_text") is not None else None
        new_hash = sha_text(row.get("proposed_new_text")) if row.get("proposed_new_text") is not None else None
        diff_hash = sha_text(f"{old_hash or ''}->{new_hash or ''}") if old_hash or new_hash else None
        applied = bool_int(str(row.get("proposal_id")) in applied_ids or data.get("schema_version") == "wf72.phase2_canon_sync_apply.v1")
        cur = conn.execute(
            """
            INSERT INTO canon_proposal_staging(
                artifact_run_id, source_file, proposal_id, target_file, target_section, proposal_kind,
                authority_classification, requires_owner_approval, proposal_apply_allowed, applied,
                old_text_sha256, new_text_sha256, diff_sha256, evidence_status, validator_status,
                source_lineage_status, status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, source_file, clean_text(row.get("proposal_id")), clean_text(row.get("target_file")),
                clean_text(row.get("target_section")), clean_text(row.get("drift_class") or row.get("proposal_kind") or "canon_text_patch"),
                clean_text(row.get("authority_classification")), bool_int(row.get("requires_owner_approval", True)),
                bool_int(row.get("proposal_apply_allowed")), applied, old_hash, new_hash, diff_hash,
                "linked" if row.get("proof") else "unstaged", clean_text(data.get("status")),
                "unverified", clean_text(row.get("status") or data.get("status") or "review_only_staged"), as_json(row),
            ),
        )
        stage_id = int(cur.lastrowid)
        count += 1
        for proof in as_list(row.get("proof")):
            conn.execute(
                """
                INSERT INTO canon_proposal_evidence_links(
                    canon_proposal_staging_id, evidence_kind, evidence_table, evidence_source_file,
                    evidence_field, evidence_sha256, evidence_url, required, status, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stage_id, "declared_proof", "declared_text", clean_text(proof), None,
                    sha_text(proof), None, 1, "linked", as_json({"proof": proof}),
                ),
            )
            evidence_count += 1
    return {"canon_proposal_staging": count, "canon_proposal_evidence_links": evidence_count}


def insert_earnings_lifecycle_events(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> int:
    lifecycle = as_dict(data.get("earnings_lifecycle"))
    rows: list[tuple[str, dict[str, Any]]] = []
    for item in as_list(lifecycle.get("closeouts")):
        if isinstance(item, dict):
            rows.append(("closeout", item))
    for item in as_list(lifecycle.get("active_holds")):
        if isinstance(item, dict):
            rows.append(("active_hold", item))

    count = 0
    for event_kind, item in rows:
        ticker = clean_text(item.get("ticker")).upper()
        if not ticker:
            continue
        evidence = as_dict(item.get("evidence"))
        authority = as_dict(item.get("authority"))
        conn.execute(
            """
            INSERT INTO earnings_lifecycle_events(
                artifact_run_id, source_file, ticker, event_kind, lifecycle_status,
                watchlist_date, provider_date_before_closeout, last_earnings_date,
                post_earnings_review_date, post_earnings_review_confirmed, reason,
                review_only, portfolio_mutation_allowed, canonical_note_mutation_allowed,
                trade_or_account_action_allowed, owner_approval_inferred, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, source_file, ticker, event_kind, clean_text(item.get("status")),
                clean_text(item.get("watchlist_date")), clean_text(item.get("provider_date_before_closeout")),
                clean_text(evidence.get("last_earnings_date")), clean_text(evidence.get("post_earnings_review_date")),
                bool_int(evidence.get("post_earnings_review_confirmed")), clean_text(item.get("reason")),
                bool_int(authority.get("review_only", True)), bool_int(authority.get("portfolio_mutation_allowed")),
                bool_int(authority.get("canonical_note_mutation_allowed")), bool_int(authority.get("trade_or_account_action_allowed")),
                bool_int(authority.get("owner_approval_inferred")), as_json(item),
            ),
        )
        count += 1
    return count


def insert_dashboard_findings(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> int:
    count = 0
    for finding_kind in ("critical", "warnings", "info", "findings"):
        for item in as_list(data.get(finding_kind)):
            if not isinstance(item, dict):
                continue
            details = as_dict(item.get("details"))
            ticker = clean_text(item.get("ticker") or details.get("ticker"))
            conn.execute(
                """
                INSERT INTO dashboard_findings(
                    artifact_run_id, source_file, finding_kind, code, severity, scope, ticker,
                    message, stop_line, review_only, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, source_file, finding_kind, clean_text(item.get("code")), clean_text(item.get("severity")),
                    clean_text(item.get("scope")), ticker, clean_text(item.get("message")),
                    bool_int(item.get("stop_line")), 1, as_json(item),
                ),
            )
            count += 1
    return count


def insert_source_freshness_rows(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> int:
    freshness = as_dict(data.get("source_freshness"))
    trust_level = clean_text(freshness.get("trust_level"))
    count = 0
    source_items = as_list(freshness.get("sources"))
    if not source_items and isinstance(data.get("freshness"), list):
        source_items = [
            {
                "source_key": item.get("label"),
                "path": item.get("label"),
                "classification": item.get("status") or ("fresh" if item.get("fresh") else "review_required"),
                "generated_at_utc": item.get("time"),
                "age_hours": item.get("age_h"),
                "criticality": "presentation",
                "owner_layer": "dashboard_payload",
                "usable_for_review": item.get("fresh") is True,
                "usable_for_presentation": item.get("fresh") is True,
                "usable_for_canonical_mutation": False,
                "stop_line": item.get("status") in {"stale", "missing", "blocked"},
            }
            for item in data.get("freshness")
            if isinstance(item, dict)
        ]
        if source_items and not trust_level:
            trust_level = "dashboard_payload_fallback"
    for item in source_items:
        if not isinstance(item, dict):
            continue
        conn.execute(
            """
            INSERT INTO source_freshness_rows(
                artifact_run_id, source_file, source_key, path, classification, trust_level,
                criticality, owner_layer, usable_for_review, usable_for_presentation,
                usable_for_canonical_mutation, stop_line, generated_at_utc, age_hours,
                stale_after_hours, confidence_ceiling, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, source_file, clean_text(item.get("source_key")), clean_text(item.get("path")),
                clean_text(item.get("classification")), trust_level, clean_text(item.get("criticality")),
                clean_text(item.get("owner_layer")), bool_int(item.get("usable_for_review")),
                bool_int(item.get("usable_for_presentation")), bool_int(item.get("usable_for_canonical_mutation")),
                bool_int(item.get("stop_line")), clean_text(item.get("generated_at_utc")),
                float(item.get("age_hours")) if item.get("age_hours") is not None else None,
                float(item.get("stale_after_hours")) if item.get("stale_after_hours") is not None else None,
                clean_text(item.get("confidence_ceiling")), as_json(item),
            ),
        )
        count += 1
    return count


def insert_deployment_readiness_rows(conn: sqlite3.Connection, run_id: int, source_file: str, data: dict[str, Any]) -> int:
    count = 0
    for bucket, items in as_dict(data.get("groups")).items():
        for item in as_list(items):
            if not isinstance(item, dict):
                continue
            ticker = clean_text(item.get("ticker")).upper()
            if not ticker:
                continue
            conn.execute(
                """
                INSERT INTO deployment_readiness_rows(
                    artifact_run_id, source_file, ticker, bucket, surface_state, base_surface_state,
                    workflow_state, machine_state, close, band_position, macro_gate,
                    review_only_no_apply_artifact, band_stale, post_earnings_review_confirmed,
                    next_earnings_date, catalyst_blocker, source_artifact_path,
                    source_generated_at_utc, authority_boundary, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, source_file, ticker, clean_text(bucket), clean_text(legacy_state(item, "surface_state")),
                    clean_text(legacy_state(item, "base_surface_state")), clean_text(legacy_state(item, "workflow_state")),
                    clean_text(legacy_state(item, "machine_state")), item.get("close"), clean_text(item.get("band_position")),
                    clean_text(item.get("macro_gate")), bool_int(item.get("review_only_no_apply_artifact")),
                    bool_int(item.get("band_stale")), bool_int(item.get("post_earnings_review_confirmed")),
                    clean_text(item.get("next_earnings_date")), clean_text(item.get("catalyst_blocker")),
                    clean_text(item.get("source_artifact_path")), clean_text(item.get("source_generated_at_utc")),
                    "review_only_dashboard_surface_not_apply", as_json(item),
                ),
            )
            count += 1
    return count


def index_file(conn: sqlite3.Connection, path: Path, indexed_at: str) -> dict[str, int | str]:
    data = load_json_artifact(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    artifact_type = artifact_type_for(path)
    run_id = insert_run(conn, path, data, artifact_type, indexed_at)
    source_file = rel(path)
    window = str(data.get("window") or "unknown")
    generated_at = str(data.get("generated_at_utc") or "")
    counts = {
        "source_file": source_file, "runs": 1, "market_events": 0, "daily_review_objects": 0,
        "capital_recommendations": 0, "source_artifacts": 0, "validator_runs": 0,
        "authority_flags": 0, "canon_proposals": 0, "today_decision_items": 0,
        "official_ir_capture_runs": 0, "official_ir_capture_fields": 0, "source_field_lineage": 0,
        "canon_proposal_staging": 0, "canon_proposal_evidence_links": 0, "earnings_lifecycle_events": 0,
        "dashboard_findings": 0, "source_freshness_rows": 0, "deployment_readiness_rows": 0,
    }
    counts["authority_flags"] = insert_authority_flags(conn, run_id, source_file, artifact_type, as_dict(data.get("authority")))
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
    elif artifact_type == "today_card":
        counts["source_artifacts"] = insert_source_artifacts(conn, run_id, source_file, as_list(data.get("source_artifacts")))
        counts["today_decision_items"] = insert_today_decision_items(conn, run_id, source_file, as_list(data.get("decision_items")))
        for name, validator in as_dict(data.get("validator_status")).items():
            if isinstance(validator, dict):
                insert_validator_run(conn, run_id, source_file, f"today_card_embedded_{name}", {"status": validator.get("status") or validator.get("overall"), "summary": validator, "authority": data.get("authority") or {}, "raw": validator})
                counts["validator_runs"] = int(counts["validator_runs"]) + 1
    elif artifact_type in {"today_card_validation", "capital_deployment_recommendation_validation"}:
        insert_validator_run(conn, run_id, source_file, artifact_type, data)
        counts["validator_runs"] = 1
    elif artifact_type == "current_window_artifacts":
        records = as_list(data.get("artifacts"))
        counts["source_artifacts"] = insert_source_artifacts(conn, run_id, source_file, records)
    elif artifact_type in {"canon_cleanup_proposals", "canon_sync_apply_audit"}:
        counts["canon_proposals"] = insert_canon_proposals(conn, run_id, source_file, data)
        staged = insert_canon_proposal_staging(conn, run_id, source_file, data)
        counts["canon_proposal_staging"] = staged["canon_proposal_staging"]
        counts["canon_proposal_evidence_links"] = staged["canon_proposal_evidence_links"]
    elif artifact_type == "official_ir_capture":
        official_counts = insert_official_ir_capture(conn, run_id, source_file, data)
        counts["official_ir_capture_runs"] = official_counts["official_ir_capture_runs"]
        counts["official_ir_capture_fields"] = official_counts["official_ir_capture_fields"]
        counts["source_field_lineage"] = official_counts["source_field_lineage"]
    elif artifact_type == "earnings_calendar":
        counts["earnings_lifecycle_events"] = insert_earnings_lifecycle_events(conn, run_id, source_file, data)
    elif artifact_type == "dashboard_validation":
        insert_validator_run(conn, run_id, source_file, artifact_type, data)
        counts["validator_runs"] = 1
        counts["dashboard_findings"] = insert_dashboard_findings(conn, run_id, source_file, data)
        counts["source_freshness_rows"] = insert_source_freshness_rows(conn, run_id, source_file, data)
    elif artifact_type == "dashboard_data":
        counts["source_freshness_rows"] = insert_source_freshness_rows(conn, run_id, source_file, data)
    elif artifact_type == "deployment_readiness_surface":
        counts["deployment_readiness_rows"] = insert_deployment_readiness_rows(conn, run_id, source_file, data)
    return counts


def empty_index_counts(source_file: str) -> dict[str, int | str]:
    return {
        "source_file": source_file, "runs": 0, "market_events": 0, "daily_review_objects": 0,
        "capital_recommendations": 0, "source_artifacts": 0, "validator_runs": 0,
        "authority_flags": 0, "canon_proposals": 0, "today_decision_items": 0,
        "official_ir_capture_runs": 0, "official_ir_capture_fields": 0, "source_field_lineage": 0,
        "canon_proposal_staging": 0, "canon_proposal_evidence_links": 0, "earnings_lifecycle_events": 0,
        "dashboard_findings": 0, "source_freshness_rows": 0, "deployment_readiness_rows": 0,
    }


def upsert_file_state(conn: sqlite3.Connection, path: Path, artifact_run_id: int | None, indexed_at: str, status: str = "indexed") -> None:
    artifact_type = artifact_type_for(path)
    conn.execute(
        """
        INSERT INTO artifact_file_state(source_file, artifact_type, file_mtime_utc, file_size, file_sha256, artifact_run_id, indexed_at_utc, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_file) DO UPDATE SET
            artifact_type=excluded.artifact_type,
            file_mtime_utc=excluded.file_mtime_utc,
            file_size=excluded.file_size,
            file_sha256=excluded.file_sha256,
            artifact_run_id=excluded.artifact_run_id,
            indexed_at_utc=excluded.indexed_at_utc,
            status=excluded.status
        """,
        (rel(path), artifact_type, file_mtime_utc(path), path.stat().st_size, sha_file(path), artifact_run_id, indexed_at, status),
    )


def index_file_with_state(conn: sqlite3.Connection, path: Path, indexed_at: str) -> dict[str, int | str]:
    if path.name in FILE_STATE_ONLY_FILES:
        upsert_file_state(conn, path, None, indexed_at, "file_state_only")
        return empty_index_counts(rel(path))
    counts = index_file(conn, path, indexed_at)
    run_id = conn.execute("SELECT id FROM artifact_runs WHERE source_file=?", (rel(path),)).fetchone()[0]
    upsert_file_state(conn, path, int(run_id), indexed_at)
    return counts


def count_tables(conn: sqlite3.Connection) -> dict[str, int]:
    return {name: int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) for name in INDEXED_TABLES}


def drift_fingerprint_for_table(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
    semantic_columns = [col for col in columns if col not in DRIFT_FINGERPRINT_EXCLUDED_COLUMNS]
    quoted_columns = ", ".join(f'"{col}"' for col in semantic_columns)
    signatures: list[str] = []
    for row in conn.execute(f"SELECT {quoted_columns} FROM {table}"):
        signatures.append(as_json({col: row[col] for col in semantic_columns}))
    signatures.sort()
    digest = hashlib.sha256("\n".join(signatures).encode("utf-8")).hexdigest()
    return {
        "row_count": len(signatures),
        "sha256": digest,
        "semantic_columns": semantic_columns,
        "excluded_columns": [col for col in columns if col in DRIFT_FINGERPRINT_EXCLUDED_COLUMNS],
    }


def drift_fingerprints(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {table: drift_fingerprint_for_table(conn, table) for table in INDEXED_TABLES}


def rebuild(db_path: Path) -> None:
    paths = iter_artifact_paths()
    if not paths:
        raise FileNotFoundError("No market-intelligence or daily-review artifacts found under tmp/")
    indexed_at = utc_now()
    with connect(db_path) as conn:
        init_schema(conn)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        try:
            reset_index(conn)
            totals = {
                "runs": 0, "market_events": 0, "daily_review_objects": 0, "capital_recommendations": 0,
                "source_artifacts": 0, "validator_runs": 0, "authority_flags": 0,
                "canon_proposals": 0, "today_decision_items": 0,
                "official_ir_capture_runs": 0, "official_ir_capture_fields": 0, "source_field_lineage": 0,
                "canon_proposal_staging": 0, "canon_proposal_evidence_links": 0,
                "earnings_lifecycle_events": 0, "dashboard_findings": 0,
                "source_freshness_rows": 0, "deployment_readiness_rows": 0,
            }
            for path in paths:
                counts = index_file_with_state(conn, path, indexed_at)
                for key in totals:
                    totals[key] += int(counts[key])
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("last_rebuilt_at_utc", indexed_at))
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("source_file_count", str(len(paths))))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        conn.execute("PRAGMA optimize")
    print(f"rebuilt {rel(db_path)}")
    print(
        f"source_files={len(paths)} runs={totals['runs']} market_events={totals['market_events']} "
        f"daily_review_objects={totals['daily_review_objects']} capital_recommendations={totals['capital_recommendations']} "
        f"source_artifacts={totals['source_artifacts']} validator_runs={totals['validator_runs']} "
        f"authority_flags={totals['authority_flags']} canon_proposals={totals['canon_proposals']} "
        f"today_decision_items={totals['today_decision_items']} official_ir_capture_runs={totals['official_ir_capture_runs']} "
        f"official_ir_capture_fields={totals['official_ir_capture_fields']} source_field_lineage={totals['source_field_lineage']} "
        f"canon_proposal_staging={totals['canon_proposal_staging']} canon_proposal_evidence_links={totals['canon_proposal_evidence_links']} "
        f"earnings_lifecycle_events={totals['earnings_lifecycle_events']} dashboard_findings={totals['dashboard_findings']} "
        f"source_freshness_rows={totals['source_freshness_rows']} deployment_readiness_rows={totals['deployment_readiness_rows']}"
    )


def incremental_rebuild(db_path: Path) -> None:
    paths = iter_artifact_paths()
    indexed_at = utc_now()
    current_by_source = {rel(path): path for path in paths}
    changed = 0
    unchanged = 0
    removed = 0
    with connect(db_path) as conn:
        init_schema(conn)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = {
                str(row["source_file"]): row
                for row in conn.execute("SELECT source_file, file_mtime_utc, file_size, file_sha256 FROM artifact_file_state")
            }
            for source_file in sorted(set(existing) - set(current_by_source)):
                conn.execute("DELETE FROM artifact_runs WHERE source_file=?", (source_file,))
                conn.execute("DELETE FROM artifact_file_state WHERE source_file=?", (source_file,))
                removed += 1
            for source_file, path in sorted(current_by_source.items()):
                state = existing.get(source_file)
                mtime = file_mtime_utc(path)
                size = path.stat().st_size
                digest = None if state and state["file_mtime_utc"] == mtime and int(state["file_size"]) == size else sha_file(path)
                if state and state["file_mtime_utc"] == mtime and int(state["file_size"]) == size:
                    unchanged += 1
                    continue
                if state and state["file_sha256"] == digest:
                    conn.execute(
                        "UPDATE artifact_file_state SET file_mtime_utc=?, file_size=?, indexed_at_utc=?, status='indexed' WHERE source_file=?",
                        (mtime, size, indexed_at, source_file),
                    )
                    unchanged += 1
                    continue
                conn.execute("DELETE FROM artifact_runs WHERE source_file=?", (source_file,))
                index_file_with_state(conn, path, indexed_at)
                changed += 1
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("last_incremental_rebuilt_at_utc", indexed_at))
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("source_file_count", str(len(paths))))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        conn.execute("PRAGMA optimize")
    print(f"incremental_rebuilt {rel(db_path)}")
    print(f"source_files={len(paths)} changed_or_new={changed} unchanged={unchanged} removed={removed}")


def validate_index(db_path: Path) -> dict[str, Any]:
    with connect(db_path) as conn:
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: str = "") -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        add("integrity_check", integrity == "ok", clean_text(integrity))
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        add("foreign_key_check", len(fk_rows) == 0, f"rows={len(fk_rows)}")
        for view in [
            "v_cockpit_action_queue", "v_cockpit_action_queue_deduped", "v_cockpit_ticker_timeline", "v_cockpit_trust_boundary",
            "v_cockpit_official_source_fields", "v_cockpit_canon_staging", "v_cockpit_earnings_lifecycle",
            "v_cockpit_dashboard_findings", "v_cockpit_source_freshness", "v_cockpit_deployment_readiness",
        ]:
            exists = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name=?", (view,)).fetchone()[0]
            add(f"view_exists:{view}", exists == 1)
        forbidden = conn.execute(
            f"SELECT COUNT(*) FROM authority_flags WHERE flag_value != 0 AND flag_name IN ({','.join('?' for _ in FORBIDDEN_TRUE_AUTHORITY_FLAGS)})",
            tuple(sorted(FORBIDDEN_TRUE_AUTHORITY_FLAGS)),
        ).fetchone()[0]
        add("forbidden_true_authority_flags_zero", int(forbidden) == 0, f"count={forbidden}")
        apply_allowed = conn.execute("SELECT COUNT(*) FROM canon_proposal_staging WHERE proposal_apply_allowed != 0").fetchone()[0]
        add("canon_stage_apply_allowed_zero", int(apply_allowed) == 0, f"count={apply_allowed}")
        canon_stage_readiness = build_canon_stage_readiness_report(conn)
        stage_summary = as_dict(canon_stage_readiness.get("summary"))
        activation_ready = int(stage_summary.get("activation_or_apply_ready_rows") or 0)
        add("canon_stage_activation_or_apply_ready_rows_zero", activation_ready == 0, f"count={activation_ready}")
        official_without_lineage = conn.execute(
            """
            SELECT COUNT(*) FROM official_ir_capture_fields f
            WHERE (f.source_url != '' OR f.excerpt_sha256 IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM source_field_lineage l
                  WHERE l.downstream_table='official_ir_capture_fields'
                    AND l.downstream_row_id=f.id
              )
            """
        ).fetchone()[0]
        add("official_ir_fields_have_lineage", int(official_without_lineage) == 0, f"missing={official_without_lineage}")
        cockpit_rows = conn.execute("SELECT COUNT(*) FROM v_cockpit_action_queue").fetchone()[0]
        add("cockpit_action_queue_has_rows", int(cockpit_rows) > 0, f"rows={cockpit_rows}")
        cockpit_deduped_rows = conn.execute("SELECT COUNT(*) FROM v_cockpit_action_queue_deduped").fetchone()[0]
        add("cockpit_action_queue_deduped_has_rows", int(cockpit_deduped_rows) > 0, f"rows={cockpit_deduped_rows}")
        add(
            "cockpit_action_queue_deduped_not_larger_than_raw",
            int(cockpit_deduped_rows) <= int(cockpit_rows),
            f"raw={cockpit_rows} deduped={cockpit_deduped_rows}",
        )
        cockpit_deduped_duplicates = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT action_dedupe_key, COUNT(*) AS count
                FROM v_cockpit_action_queue_deduped
                GROUP BY action_dedupe_key
                HAVING count > 1
            )
            """
        ).fetchone()[0]
        add("cockpit_action_queue_deduped_unique_keys", int(cockpit_deduped_duplicates) == 0, f"duplicates={cockpit_deduped_duplicates}")
        amd = conn.execute("SELECT COUNT(*) FROM v_cockpit_official_source_fields WHERE upper(ticker)='AMD' AND field_name='adjusted_eps' AND excerpt_sha256 IS NOT NULL").fetchone()[0]
        add("official_field_proof_amd_adjusted_eps", int(amd) > 0, f"rows={amd}")
        etn = conn.execute("SELECT COUNT(*) FROM v_cockpit_ticker_timeline WHERE upper(ticker)='ETN'").fetchone()[0]
        add("ticker_timeline_etn_has_rows", int(etn) > 0, f"rows={etn}")
        nvda_lifecycle = conn.execute("SELECT COUNT(*) FROM v_cockpit_earnings_lifecycle WHERE upper(ticker)='NVDA' AND review_only=1 AND trade_or_account_action_allowed=0 AND owner_approval_inferred=0").fetchone()[0]
        add("earnings_lifecycle_nvda_review_only", int(nvda_lifecycle) > 0, f"rows={nvda_lifecycle}")
        deployment_etn = conn.execute("SELECT COUNT(*) FROM v_cockpit_deployment_readiness WHERE upper(ticker)='ETN'").fetchone()[0]
        etn_buckets = [str(row[0]) for row in conn.execute("SELECT DISTINCT bucket FROM v_cockpit_deployment_readiness WHERE upper(ticker)='ETN' ORDER BY bucket")]
        add("deployment_readiness_etn_indexed", int(deployment_etn) > 0, f"rows={deployment_etn} buckets={etn_buckets}")
        freshness_rows = conn.execute("SELECT COUNT(*) FROM v_cockpit_source_freshness").fetchone()[0]
        add("source_freshness_rows_indexed", int(freshness_rows) > 0, f"rows={freshness_rows}")
        dashboard_findings = conn.execute("SELECT COUNT(*) FROM v_cockpit_dashboard_findings").fetchone()[0]
        add("dashboard_findings_indexed", int(dashboard_findings) > 0, f"rows={dashboard_findings}")
        plan_text = "\n".join(clean_text(tuple(row)) for row in conn.execute("EXPLAIN QUERY PLAN SELECT * FROM daily_review_objects WHERE upper(ticker)=? ORDER BY generated_at_utc DESC LIMIT 5", ("ETN",)))
        add("ticker_expression_index_query_plan", "idx_daily_review_ticker_upper_time" in plan_text, plan_text)
        counts = count_tables(conn)
        metadata = {str(row["key"]): str(row["value"]) for row in conn.execute("SELECT key, value FROM meta")}
        fingerprints = drift_fingerprints(conn)
        empty_fingerprints = [table for table, info in fingerprints.items() if int(info["row_count"]) != counts.get(table, -1)]
        add("drift_fingerprint_row_counts_match", not empty_fingerprints, ", ".join(empty_fingerprints))

        # Freshness/stale-source drift checks — read-only, no index mutation.
        # Compares live artifact_file_state against current iter_artifact_paths() results.
        live_paths = {rel(path): path for path in iter_artifact_paths()}
        db_state = {
            str(row["source_file"]): {
                "mtime": str(row["file_mtime_utc"] or ""),
                "size": int(row["file_size"]),
                "sha256": str(row["file_sha256"] or ""),
            }
            for row in conn.execute("SELECT source_file, file_mtime_utc, file_size, file_sha256 FROM artifact_file_state")
        }
        not_indexed = sorted(sf for sf in live_paths if sf not in db_state)
        orphaned = sorted(sf for sf in db_state if sf not in live_paths)
        stale: list[str] = []
        for sf, path in sorted(live_paths.items()):
            stored = db_state.get(sf)
            if not stored:
                continue
            live_mtime = file_mtime_utc(path)
            live_size = path.stat().st_size
            if stored["mtime"] == live_mtime and stored["size"] == live_size:
                continue
            live_sha = sha_file(path)
            if live_sha != stored["sha256"]:
                stale.append(sf)
        add(
            "freshness_live_files_all_indexed",
            len(not_indexed) == 0,
            f"not_indexed={len(not_indexed)}" + (f" files=[{', '.join(not_indexed[:5])}]" if not_indexed else ""),
        )
        add(
            "freshness_no_orphaned_rows",
            len(orphaned) == 0,
            f"orphaned={len(orphaned)}" + (f" files=[{', '.join(orphaned[:5])}]" if orphaned else ""),
        )
        add(
            "freshness_no_stale_content",
            len(stale) == 0,
            f"stale={len(stale)}" + (f" files=[{', '.join(stale[:5])}]" if stale else ""),
        )
        last_full = metadata.get("last_rebuilt_at_utc")
        last_incr = metadata.get("last_incremental_rebuilt_at_utc")
        add(
            "freshness_index_has_been_built",
            bool(last_full or last_incr),
            f"last_rebuilt={last_full} last_incremental={last_incr}",
        )

        ok = all(check["ok"] for check in checks)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok" if ok else "blocked",
            "generated_at_utc": utc_now(),
            "authority": {
                "derived_index_only": True,
                "staging_only": True,
                "canonical_note_mutation_allowed": False,
                "portfolio_mutation_allowed": False,
                "proposal_apply_allowed": False,
                "trade_or_account_action_allowed": False,
                "paper_or_live_order_allowed": False,
                "owner_approval_inferred": False,
            },
            "meta": metadata,
            "counts": counts,
            "safety_counts": {
                "forbidden_true_authority_flags": int(forbidden),
                "canon_stage_apply_allowed": int(apply_allowed),
                "canon_stage_historical_applied_rows": int(stage_summary.get("historical_applied_rows") or 0),
                "canon_stage_pending_review_only_rows": int(stage_summary.get("pending_review_only_rows") or 0),
                "canon_stage_incomplete_review_only_rows": int(stage_summary.get("incomplete_review_only_rows") or 0),
                "canon_stage_activation_or_apply_ready_rows": activation_ready,
                "official_ir_fields_without_lineage": int(official_without_lineage),
            },
            "canon_proposal_staging_readiness": canon_stage_readiness,
            "freshness_summary": {
                "live_files": len(live_paths),
                "indexed_files": len(db_state),
                "not_indexed": len(not_indexed),
                "orphaned": len(orphaned),
                "stale_content": len(stale),
                "last_rebuilt_at_utc": last_full,
                "last_incremental_rebuilt_at_utc": last_incr,
            },
            "drift_fingerprints": fingerprints,
            "checks": checks,
            "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"])},
        }


def query_fingerprints(conn: sqlite3.Connection, json_output: bool = False) -> None:
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "authority_boundary": "derived_review_only_index_not_canon_not_apply",
        "tables": drift_fingerprints(conn),
    }
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    result_rows = [
        {"table": table, "row_count": info["row_count"], "sha256": info["sha256"]}
        for table, info in report["tables"].items()
    ]
    columns = ["table", "row_count", "sha256"]
    if not result_rows:
        print("(no rows)")
        return
    print(" | ".join(columns))
    print(" | ".join("---" for _ in columns))
    for row in result_rows:
        print(" | ".join(clean_text(row[col]) for col in columns))


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
        SELECT ticker, kind, source_file, generated_at_utc, route, status, score, summary
        FROM v_cockpit_ticker_timeline
        WHERE upper(ticker)=?
        ORDER BY generated_at_utc DESC, kind, score DESC
        LIMIT ?
        """,
        (token, limit),
    )
    print_table(result, ["ticker", "kind", "source_file", "generated_at_utc", "route", "status", "score", "summary"])


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


def query_today(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT ticker, item_state, recommendation_posture, owner_action_needed,
               close, band_low, band_high, entry_band_status, authority_boundary
        FROM today_decision_items
        ORDER BY rank ASC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["ticker", "item_state", "recommendation_posture", "owner_action_needed", "close", "band_low", "band_high", "entry_band_status", "authority_boundary"])


def query_validators(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT source_file, validator_name, status, critical, warning, checked_count
        FROM validator_runs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["source_file", "validator_name", "status", "critical", "warning", "checked_count"])


def query_canon(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT proposal_id, target_file, drift_class, authority_classification,
               requires_owner_approval, applied, status
        FROM canon_proposals
        ORDER BY id ASC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["proposal_id", "target_file", "drift_class", "authority_classification", "requires_owner_approval", "applied", "status"])


def query_authority(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT source_file, surface, flag_name, flag_value
        FROM authority_flags
        WHERE flag_value != 0
        ORDER BY source_file, flag_name
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["source_file", "surface", "flag_name", "flag_value"])


def query_official_ir(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT r.ticker, r.period_end, r.source_type, r.source_url,
               COUNT(f.id) AS fields,
               SUM(CASE WHEN f.status='partial' THEN 1 ELSE 0 END) AS partial,
               SUM(f.manual_required) AS manual_required,
               SUM(f.not_disclosed) AS not_disclosed,
               r.review_only, r.resolved_for_apply
        FROM official_ir_capture_runs r
        LEFT JOIN official_ir_capture_fields f ON f.capture_run_id = r.id
        GROUP BY r.id
        ORDER BY r.capture_generated_at_utc DESC, r.ticker
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["ticker", "period_end", "source_type", "source_url", "fields", "partial", "manual_required", "not_disclosed", "review_only", "resolved_for_apply"])


def query_lineage(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT downstream_source_file, downstream_table, downstream_field, lineage_kind,
               upstream_source_file, upstream_field, upstream_source_url, upstream_excerpt_sha256, confidence
        FROM source_field_lineage
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["downstream_source_file", "downstream_table", "downstream_field", "lineage_kind", "upstream_source_file", "upstream_field", "upstream_source_url", "upstream_excerpt_sha256", "confidence"])



def build_canon_stage_readiness_report(conn: sqlite3.Connection, limit: int = 200) -> dict[str, Any]:
    """Classify canon_proposal_staging rows as review context, not apply readiness.

    The staging table intentionally remains a derived SQL/index surface. This
    report makes the row semantics explicit so historical applied rows and
    pending review-only proposals cannot be mistaken for SQL-canon activation,
    canonical apply readiness, owner approval, or execution authority.
    """
    result_rows = rows(
        conn,
        """
        SELECT proposal_id, target_file, proposal_kind, requires_owner_approval,
               proposal_apply_allowed, applied, evidence_status, validator_status,
               source_lineage_status, status, source_file
        FROM canon_proposal_staging
        ORDER BY applied DESC, target_file, proposal_id
        LIMIT ?
        """,
        (limit,),
    )
    categories = {
        "historical_applied_non_activation_context": [],
        "pending_review_only_complete": [],
        "incomplete_review_only": [],
        "unsafe_apply_allowed_or_activation_ready": [],
    }
    status_counts: dict[str, int] = {}
    for row in result_rows:
        item = dict(row)
        apply_allowed = bool(int(item.get("proposal_apply_allowed") or 0))
        applied = bool(int(item.get("applied") or 0))
        requires_owner = bool(int(item.get("requires_owner_approval") or 0))
        evidence_linked = clean_text(item.get("evidence_status")).lower() == "linked"
        lineage_verified = clean_text(item.get("source_lineage_status")).lower() not in {"", "unverified"}
        validator_ok = clean_text(item.get("validator_status")).lower() == "ok"
        if apply_allowed:
            category = "unsafe_apply_allowed_or_activation_ready"
            readiness_blocker = "proposal_apply_allowed_true_stop_line"
        elif applied:
            category = "historical_applied_non_activation_context"
            readiness_blocker = "historical_applied_rows_are_audit_history_not_pending_apply_readiness"
        elif requires_owner and evidence_linked and lineage_verified and validator_ok:
            category = "pending_review_only_complete"
            readiness_blocker = "review_only_owner_gated_no_proposal_apply_authority"
        else:
            category = "incomplete_review_only"
            missing = []
            if not requires_owner:
                missing.append("requires_owner_approval")
            if not evidence_linked:
                missing.append("linked_evidence")
            if not lineage_verified:
                missing.append("verified_source_lineage")
            if not validator_ok:
                missing.append("validator_ok")
            readiness_blocker = "missing_" + "+".join(missing) if missing else "incomplete_review_only"
        item["readiness_category"] = category
        item["activation_or_apply_readiness"] = False
        item["readiness_blocker"] = readiness_blocker
        categories[category].append(item)
        status_counts[category] = status_counts.get(category, 0) + 1
    total_rows = sum(status_counts.values())
    activation_rows = len(categories["unsafe_apply_allowed_or_activation_ready"])
    historical_rows = len(categories["historical_applied_non_activation_context"])
    pending_complete_rows = len(categories["pending_review_only_complete"])
    incomplete_rows = len(categories["incomplete_review_only"])
    blockers = []
    if activation_rows:
        blockers.append("proposal_apply_allowed rows exist; apply/activation stop line is breached")
    if historical_rows:
        blockers.append("historical applied rows exist in staging; treat as audit/history only, not pending readiness")
    if incomplete_rows:
        blockers.append("pending review-only rows are incomplete; source/evidence/validator gaps block apply readiness claims")
    if pending_complete_rows:
        blockers.append("complete pending rows remain review-only and owner-gated because proposal_apply_allowed is false")
    return {
        "schema_version": "wf72.canon_proposal_staging_readiness.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked_for_activation_or_apply_readiness" if blockers or activation_rows else "review_only_staging_clean_no_apply_authority",
        "boundary": "derived_review_only_index_not_canon_not_apply",
        "authority": {
            "sql_is_derived_index_only": True,
            "report_is_review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "proposal_apply_allowed": False,
            "activation_allowed": False,
            "cron_direct_apply_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_action_allowed": False,
            "paper_or_live_order_allowed": False,
            "money_movement_allowed": False,
            "config_auth_channel_service_mutation_allowed": False,
        },
        "summary": {
            "total_rows": total_rows,
            "historical_applied_rows": historical_rows,
            "pending_review_only_rows": pending_complete_rows + incomplete_rows,
            "pending_review_only_complete_rows": pending_complete_rows,
            "incomplete_review_only_rows": incomplete_rows,
            "activation_or_apply_ready_rows": activation_rows,
        },
        "readiness_blockers": blockers,
        "category_counts": status_counts,
        "categories": {key: value[:limit] for key, value in categories.items()},
        "interpretation": "canon_proposal_staging is display/index/proof context only. Historical applied rows and pending review-only rows cannot support SQL-canon activation, canonical apply readiness, owner approval, cron-direct apply, or execution authority.",
    }


def render_canon_stage_readiness_markdown(report: dict[str, Any]) -> str:
    summary = as_dict(report.get("summary"))
    lines = [
        "# WF72 canon proposal staging readiness report",
        "",
        f"- Generated: {report.get('generated_at_utc')}",
        f"- Status: `{report.get('status')}`",
        f"- Boundary: `{report.get('boundary')}`",
        "- Authority: review-only derived SQL index; not canon, not apply authority, not owner approval, not execution authority.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key in [
        "total_rows", "historical_applied_rows", "pending_review_only_rows",
        "pending_review_only_complete_rows", "incomplete_review_only_rows",
        "activation_or_apply_ready_rows",
    ]:
        lines.append(f"| {key} | {summary.get(key, 0)} |")
    lines.extend(["", "## Readiness blockers", ""])
    blockers = as_list(report.get("readiness_blockers"))
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- None, but rows remain review-only unless a separate exact approval/apply gate says otherwise.")
    lines.extend(["", "## Category counts", ""])
    for key, count in sorted(as_dict(report.get("category_counts")).items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Interpretation", "", clean_text(report.get("interpretation")), ""])
    return "\n".join(lines)


def query_canon_stage_readiness(conn: sqlite3.Connection, limit: int, json_output: bool = False, output: str | None = None, md_output: str | None = None) -> None:
    report = build_canon_stage_readiness_report(conn, limit=limit)
    if output:
        output_path = WORKSPACE / output.replace("/", "\\")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if md_output:
        md_path = WORKSPACE / md_output.replace("/", "\\")
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_canon_stage_readiness_markdown(report), encoding="utf-8")
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    summary = as_dict(report.get("summary"))
    print(f"status={report['status']} total={summary.get('total_rows')} historical_applied={summary.get('historical_applied_rows')} pending_review_only={summary.get('pending_review_only_rows')} incomplete_review_only={summary.get('incomplete_review_only_rows')} activation_or_apply_ready={summary.get('activation_or_apply_ready_rows')}")
    for blocker in as_list(report.get("readiness_blockers")):
        print(f"blocker | {blocker}")

def query_canon_stage(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT proposal_id, target_file, proposal_kind, requires_owner_approval,
               proposal_apply_allowed, applied, evidence_status, source_lineage_status, status
        FROM canon_proposal_staging
        ORDER BY id ASC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["proposal_id", "target_file", "proposal_kind", "requires_owner_approval", "proposal_apply_allowed", "applied", "evidence_status", "source_lineage_status", "status"])


def query_cockpit(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT priority_kind, ticker, route, urgency, score, action_text,
               owner_action_needed, authority_boundary, source_file, generated_at_utc
        FROM v_cockpit_action_queue
        ORDER BY owner_action_needed DESC, generated_at_utc DESC, score DESC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["priority_kind", "ticker", "route", "urgency", "score", "action_text", "owner_action_needed", "authority_boundary", "source_file", "generated_at_utc"])


def query_ticker_cockpit(conn: sqlite3.Connection, ticker: str, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT ticker, kind, source_file, generated_at_utc, route, status, score, summary
        FROM v_cockpit_ticker_timeline
        WHERE upper(ticker)=?
        ORDER BY generated_at_utc DESC, kind, score DESC
        LIMIT ?
        """,
        (ticker.upper(), limit),
    )
    print_table(result, ["ticker", "kind", "source_file", "generated_at_utc", "route", "status", "score", "summary"])


def query_trust_cockpit(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT source_file, artifact_type, window, generated_at_utc, owner_review_required,
               canonical_mutation_allowed, critical, warning, forbidden_true_flags, authority_boundary
        FROM v_cockpit_trust_boundary
        ORDER BY forbidden_true_flags DESC, critical DESC, warning DESC, generated_at_utc DESC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["source_file", "artifact_type", "window", "generated_at_utc", "owner_review_required", "canonical_mutation_allowed", "critical", "warning", "forbidden_true_flags", "authority_boundary"])


def query_proof_field(conn: sqlite3.Connection, ticker: str, field_name: str, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT ticker, period, field_name, status, source_url, source_section,
               excerpt_sha256, manual_required, not_disclosed, inferred, source_file, authority_boundary
        FROM v_cockpit_official_source_fields
        WHERE upper(ticker)=? AND field_name=?
        ORDER BY period DESC, source_file
        LIMIT ?
        """,
        (ticker.upper(), field_name, limit),
    )
    print_table(result, ["ticker", "period", "field_name", "status", "source_url", "source_section", "excerpt_sha256", "manual_required", "not_disclosed", "inferred", "source_file", "authority_boundary"])


def query_data_coverage(ticker: str | None = None, family: str | None = None, json_output: bool = False) -> None:
    """Print the WF77 finance data coverage registry.

    This command is a thin cockpit wrapper over tmp/finance-data-coverage-current.json.
    The registry remains a derived review/routing surface only; source-open is still
    required before substantive finance claims.
    """
    path = TMP / "finance-data-coverage-current.json"
    if not path.exists():
        raise FileNotFoundError("Coverage registry not found: tmp/finance-data-coverage-current.json. Run scripts\\finance_data_coverage.py --validate --write-contract first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if json_output:
        payload: Any = data
        if ticker:
            payload = as_dict(data.get("ticker_coverage")).get(ticker.upper(), {})
        if family:
            payload = as_dict(data.get("family_registry")).get(family, payload if ticker else {})
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if ticker:
        row = as_dict(data.get("ticker_coverage")).get(ticker.upper())
        if not row:
            print(f"No ticker coverage row for {ticker.upper()} in tmp/finance-data-coverage-current.json")
            return
        rows_out = []
        for family_id, fam_any in sorted(as_dict(row.get("families")).items()):
            fam_row = as_dict(fam_any)
            rows_out.append({
                "ticker": ticker.upper(),
                "family": family_id,
                "status": fam_row.get("status"),
                "covered": fam_row.get("covered"),
                "present_sources": ", ".join(as_list(fam_row.get("present_sources"))),
                "source_artifacts": ", ".join(as_list(fam_row.get("source_artifacts"))),
            })
        print_table(rows_out, ["ticker", "family", "status", "covered", "present_sources", "source_artifacts"])
        return
    family_rows = []
    for family_id, row_any in sorted(as_dict(data.get("family_registry")).items()):
        if family and family_id != family:
            continue
        row = as_dict(row_any)
        family_rows.append({
            "family": family_id,
            "status": row.get("collection_status"),
            "collected": row.get("collected"),
            "indexed": row.get("indexed_by_registry"),
            "freshness": row.get("freshness_status"),
            "covered_tickers": len(as_list(row.get("covered_tickers"))),
            "missing_tickers": len(as_list(row.get("missing_tickers"))),
            "source_open_required": row.get("source_open_required_for_claims"),
        })
    print_table(family_rows, ["family", "status", "collected", "indexed", "freshness", "covered_tickers", "missing_tickers", "source_open_required"])


def query_missing_data(family: str | None = None, ticker: str | None = None, json_output: bool = False) -> None:
    path = TMP / "finance-data-coverage-current.json"
    if not path.exists():
        raise FileNotFoundError("Coverage registry not found: tmp/finance-data-coverage-current.json.")
    data = json.loads(path.read_text(encoding="utf-8"))
    payload = {
        "missing_by_family": as_dict(data.get("missing_by_family")),
        "missing_by_ticker": as_dict(data.get("missing_by_ticker")),
        "source_open_rule": data.get("source_open_rule"),
    }
    if family:
        payload = {"family": family, "missing": as_dict(data.get("missing_by_family")).get(family, [])}
    if ticker:
        payload = {"ticker": ticker.upper(), "missing": as_dict(data.get("missing_by_ticker")).get(ticker.upper(), [])}
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    rows_out = []
    if family:
        for item in as_list(payload.get("missing")):
            row = as_dict(item)
            rows_out.append({"family": family, "ticker": row.get("ticker"), "reason": row.get("reason") or row.get("status") or row})
        print_table(rows_out, ["family", "ticker", "reason"])
        return
    if ticker:
        for item in as_list(payload.get("missing")):
            if isinstance(item, str):
                rows_out.append({"ticker": ticker.upper(), "family": item, "reason": "missing_or_not_covered"})
            else:
                row = as_dict(item)
                rows_out.append({"ticker": ticker.upper(), "family": row.get("family_id") or row.get("family"), "reason": row.get("reason") or row.get("status") or row})
        print_table(rows_out, ["ticker", "family", "reason"])
        return
    for fam, items in as_dict(payload.get("missing_by_family")).items():
        rows_out.append({"family": fam, "missing_count": len(as_list(items))})
    print_table(rows_out, ["family", "missing_count"])


def query_ticker_card(ticker: str, json_output: bool = False) -> None:
    path = TMP / "ticker-intelligence-cards" / f"{ticker.upper()}.current.json"
    if not path.exists():
        raise FileNotFoundError(f"Ticker intelligence card not found: {path.relative_to(WORKSPACE)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if json_output:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    support = as_dict(data.get("recommendation_support"))
    band = as_dict(data.get("price_band_stop"))
    valuation = as_dict(data.get("valuation"))
    rows_out = [{
        "ticker": data.get("ticker"),
        "posture": support.get("posture"),
        "support_level": support.get("support_level"),
        "latest_price": band.get("latest_known_price"),
        "band_low": band.get("entry_band_low"),
        "band_high": band.get("entry_band_high"),
        "stop": band.get("stop_or_invalidation"),
        "forward_pe": valuation.get("forward_pe"),
        "analyst_status": as_dict(data.get("analyst_consensus_ratings_targets")).get("status"),
        "source_open_required": as_dict(data.get("authority_boundary")).get("source_open_required_before_final_recommendation_or_action_claim"),
    }]
    print_table(rows_out, ["ticker", "posture", "support_level", "latest_price", "band_low", "band_high", "stop", "forward_pe", "analyst_status", "source_open_required"])


def query_answer_packet(ticker: str, json_output: bool = False) -> None:
    """Route a ticker to the WF85 full-answer assembler.

    The command name is retained for backwards CLI compatibility, but the static
    packet directory is no longer treated as an input truth surface.
    """
    ticker = ticker.upper()

    def answer_age_hours(value: Any) -> float | None:
        if not isinstance(value, str) or not value:
            return None
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0

    answer_path = TMP / "trade-grade-full-answer" / f"{ticker}.json"
    rollup_path = TMP / "trade-grade-full-answer-assembler.json"
    card_path = TMP / "ticker-intelligence-cards" / f"{ticker}.current.json"
    fallback_chain = [
        rel(card_path),
        "03. Portfolio/Execution Board.md",
        "04. Research/Coverage and Watchlist.md",
    ]
    if not answer_path.exists():
        descriptor = {
            "ticker": ticker,
            "availability": "missing",
            "preferred_source": "ticker_card_and_sources",
            "canonical_answer_path": rel(answer_path),
            "assembler_rollup": rel(rollup_path),
            "legacy_file_dependency": False,
            "fallback_chain": fallback_chain,
            "review_only": True,
            "reason": "WF85 full-answer assembler artifact missing for this ticker",
        }
    else:
        packet = json.loads(answer_path.read_text(encoding="utf-8"))
        card_generated = None
        if card_path.exists():
            try:
                card_generated = json.loads(card_path.read_text(encoding="utf-8")).get("generated_at_utc")
            except (json.JSONDecodeError, OSError):
                card_generated = None
        age_hours = answer_age_hours(packet.get("generated_at_utc"))
        confidence = as_dict(packet.get("answer_confidence"))
        machine_state = as_dict(packet.get("machine_state"))
        owner_action = as_dict(machine_state.get("owner_action"))
        validation = as_dict(packet.get("validation"))
        missing_sections = validation.get("missing_sections") if isinstance(validation.get("missing_sections"), list) else []
        availability = "present_from_wf85_assembler" if packet.get("status") == "ok" and not missing_sections else "present_with_section_warnings"
        descriptor = {
            "ticker": ticker,
            "availability": availability,
            "preferred_source": "wf85_full_answer_assembler",
            "canonical_answer_path": rel(answer_path),
            "assembler_rollup": rel(rollup_path),
            "legacy_file_dependency": False,
            "fallback_chain": fallback_chain,
            "review_only": True,
            "card_generated_at_utc": card_generated,
            "answer_generated_at_utc": packet.get("generated_at_utc"),
            "answer_age_hours": round(age_hours, 2) if age_hours is not None else None,
            "answer_confidence": confidence.get("overall_level"),
            "answer_confidence_score": confidence.get("score"),
            "decision_state": machine_state.get("decision_state"),
            "recommended_next_action": owner_action.get("owner_action"),
            "required_section_count": len(packet.get("section_order") or []),
            "missing_sections": missing_sections,
            "reason": "legacy answer-packet command now resolves to WF85 full-answer assembler",
        }
    if json_output:
        print(json.dumps(descriptor, indent=2, sort_keys=True))
        return
    print_table([descriptor], ["ticker", "availability", "preferred_source", "answer_confidence", "decision_state", "canonical_answer_path"])


def query_answer_contract(question: str, json_output: bool = False, output: str | None = None) -> None:
    """Build a read-only WF77 SQL/JSON-first answer contract for a question."""
    import veritas_question_router

    route = veritas_question_router.build_route(question)
    contract = route.get("answer_contract_v2", {})
    payload = {
        "schema_version": 1,
        "artifact_type": "wf77_sql_json_first_answer_contract_wrapper",
        "review_only": True,
        "route": route,
        "answer_contract_v2": contract,
        "authority_boundary": contract.get("authority_boundary", route.get("authority_boundary", {})),
    }
    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = WORKSPACE / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    rows_out = [{
        "question_class": route.get("question_class"),
        "ticker": route.get("ticker"),
        "family": route.get("data_family_id") or route.get("data_family"),
        "source_open_count": len(route.get("source_open_requirements") or []),
        "missing_or_residue": len(route.get("missing_or_residue") or []),
        "final_answer_allowed": as_dict(contract.get("freshness_and_conflict_checks")).get("final_answer_allowed"),
    }]
    print_table(rows_out, ["question_class", "ticker", "family", "source_open_count", "missing_or_residue", "final_answer_allowed"])


def query_validate_answer_contract(input_path: str, json_output: bool = False) -> int:
    """Validate the minimum WF77 answer-contract stop lines without applying anything."""
    path = Path(input_path)
    if not path.is_absolute():
        path = WORKSPACE / path
    data = json.loads(path.read_text(encoding="utf-8"))
    contract = as_dict(data.get("answer_contract_v2") or as_dict(data.get("route")).get("answer_contract_v2"))
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    boundary = as_dict(contract.get("authority_boundary"))
    add("contract_schema_v2", contract.get("schema_version") == 2, f"schema_version={contract.get('schema_version')!r}")
    add("review_only", boundary.get("review_only") is True, f"review_only={boundary.get('review_only')!r}")
    forbidden = [key for key in ["canonical_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "paper_or_live_order_allowed", "trade_or_account_action_allowed"] if boundary.get(key) is True]
    add("forbidden_authority_flags_false", not forbidden, f"forbidden_true={forbidden}")
    required = as_dict(contract.get("proof_requirements")).get("required_before_final_answer") or []
    add("source_open_requirements_present", bool(required), f"required_count={len(required)}")
    route = as_dict(contract.get("route"))
    add("sql_first_commands_present", bool(route.get("sql_first_commands")), f"commands={route.get('sql_first_commands')!r}")
    status = "ok" if all(row["ok"] for row in checks) else "fail"
    payload = {"schema_version": 1, "artifact_type": "wf77_answer_contract_validation", "status": status, "input": rel(path), "checks": checks}
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status={status} checks={len(checks)} failed={sum(1 for row in checks if not row['ok'])}")
        for row in checks:
            print(f"{'ok' if row['ok'] else 'FAIL'} | {row['name']} | {row['detail']}")
    return 0 if status == "ok" else 1


def query_earnings_lifecycle(conn: sqlite3.Connection, ticker: str | None, limit: int) -> None:
    where = "WHERE upper(ticker)=?" if ticker else ""
    params: tuple[Any, ...] = (ticker.upper(), limit) if ticker else (limit,)
    result = rows(
        conn,
        f"""
        SELECT ticker, event_kind, lifecycle_status, watchlist_date, provider_date_before_closeout,
               last_earnings_date, post_earnings_review_date, post_earnings_review_confirmed,
               review_only, trade_or_account_action_allowed, owner_approval_inferred,
               source_file, authority_boundary
        FROM v_cockpit_earnings_lifecycle
        {where}
        ORDER BY watchlist_date DESC, ticker, event_kind
        LIMIT ?
        """,
        params,
    )
    print_table(result, [
        "ticker", "event_kind", "lifecycle_status", "watchlist_date", "provider_date_before_closeout",
        "last_earnings_date", "post_earnings_review_date", "post_earnings_review_confirmed",
        "review_only", "trade_or_account_action_allowed", "owner_approval_inferred",
        "source_file", "authority_boundary",
    ])


def query_deployment_readiness(conn: sqlite3.Connection, ticker: str | None, limit: int) -> None:
    where = "WHERE upper(ticker)=?" if ticker else ""
    params: tuple[Any, ...] = (ticker.upper(), limit) if ticker else (limit,)
    result = rows(
        conn,
        f"""
        SELECT ticker, bucket, surface_state, workflow_state, machine_state, close,
               band_position, macro_gate, review_only_no_apply_artifact, band_stale,
               next_earnings_date, catalyst_blocker, source_artifact_path, authority_boundary
        FROM v_cockpit_deployment_readiness
        {where}
        ORDER BY bucket, ticker
        LIMIT ?
        """,
        params,
    )
    print_table(result, [
        "ticker", "bucket", "surface_state", "workflow_state", "machine_state", "close",
        "band_position", "macro_gate", "review_only_no_apply_artifact", "band_stale",
        "next_earnings_date", "catalyst_blocker", "source_artifact_path", "authority_boundary",
    ])


def query_dashboard_findings(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT severity, code, scope, ticker, message, stop_line, review_only, source_file, authority_boundary
        FROM v_cockpit_dashboard_findings
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, code
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["severity", "code", "scope", "ticker", "message", "stop_line", "review_only", "source_file", "authority_boundary"])


def query_source_freshness(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT source_key, path, classification, trust_level, criticality, usable_for_review,
               usable_for_presentation, usable_for_canonical_mutation, stop_line,
               age_hours, stale_after_hours, confidence_ceiling, source_file, authority_boundary
        FROM v_cockpit_source_freshness
        ORDER BY stop_line DESC, classification DESC, source_key
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, [
        "source_key", "path", "classification", "trust_level", "criticality", "usable_for_review",
        "usable_for_presentation", "usable_for_canonical_mutation", "stop_line",
        "age_hours", "stale_after_hours", "confidence_ceiling", "source_file", "authority_boundary",
    ])


def query_stoplines(conn: sqlite3.Connection, limit: int) -> None:
    result = rows(
        conn,
        """
        SELECT proposal_id, target_file, proposal_kind, requires_owner_approval,
               proposal_apply_allowed, applied, evidence_status, source_lineage_status,
               evidence_links, status, authority_boundary
        FROM v_cockpit_canon_staging
        ORDER BY proposal_apply_allowed DESC, applied DESC, target_file, proposal_id
        LIMIT ?
        """,
        (limit,),
    )
    print_table(result, ["proposal_id", "target_file", "proposal_kind", "requires_owner_approval", "proposal_apply_allowed", "applied", "evidence_status", "source_lineage_status", "evidence_links", "status", "authority_boundary"])


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def build_handoff_packet(conn: sqlite3.Connection, db_path: Path, workflow: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Build a helper handoff packet from the derived SQL cockpit.

    The packet is intentionally a locator/provenance bundle. Canonical next-step
    text still belongs to Active Workflows and owner notes.
    """
    token = clean_text(workflow).strip()
    like = f"%{token.lower()}%" if token else None
    params: tuple[Any, ...] = (like, like, like, like, limit) if like else (limit,)
    artifact_where = "WHERE lower(source_file) LIKE ? OR lower(artifact_type) LIKE ? OR lower(summary_json) LIKE ? OR lower(system_json) LIKE ?" if like else ""
    artifacts = [_row_dict(row) for row in rows(
        conn,
        f"""
        SELECT source_file, artifact_type, window, generated_at_utc, consumer_posture,
               owner_review_required, canonical_mutation_allowed, file_mtime_utc
        FROM artifact_runs
        {artifact_where}
        ORDER BY COALESCE(generated_at_utc, indexed_at_utc, file_mtime_utc) DESC, source_file
        LIMIT ?
        """,
        params,
    )]
    source_where = "WHERE lower(role) LIKE ? OR lower(path) LIKE ? OR lower(source_file) LIKE ? OR lower(raw_json) LIKE ?" if like else ""
    source_artifacts = [_row_dict(row) for row in rows(
        conn,
        f"""
        SELECT role, path, status, generated_at_utc, read_status, source_file
        FROM source_artifacts
        {source_where}
        ORDER BY COALESCE(generated_at_utc, '') DESC, id DESC
        LIMIT ?
        """,
        params,
    )]
    fallback_used = False
    if token and not artifacts and not source_artifacts:
        fallback_used = True
        artifacts = [_row_dict(row) for row in rows(
            conn,
            """
            SELECT source_file, artifact_type, window, generated_at_utc, consumer_posture,
                   owner_review_required, canonical_mutation_allowed, file_mtime_utc
            FROM artifact_runs
            ORDER BY COALESCE(generated_at_utc, indexed_at_utc, file_mtime_utc) DESC, source_file
            LIMIT ?
            """,
            (limit,),
        )]
        source_artifacts = [_row_dict(row) for row in rows(
            conn,
            """
            SELECT role, path, status, generated_at_utc, read_status, source_file
            FROM source_artifacts
            ORDER BY COALESCE(generated_at_utc, '') DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )]
    validators = [_row_dict(row) for row in rows(
        conn,
        """
        SELECT source_file, validator_name, status, critical, warning, checked_count
        FROM validator_runs
        ORDER BY critical DESC, warning DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )]
    stoplines = [_row_dict(row) for row in rows(
        conn,
        """
        SELECT proposal_id, target_file, proposal_kind, requires_owner_approval,
               proposal_apply_allowed, applied, evidence_status, source_lineage_status,
               evidence_links, status, authority_boundary
        FROM v_cockpit_canon_staging
        ORDER BY proposal_apply_allowed DESC, applied DESC, target_file, proposal_id
        LIMIT ?
        """,
        (limit,),
    )]
    validation = validate_index(db_path)
    return {
        "schema_version": "wf72.sql_handoff.v1",
        "generated_at_utc": utc_now(),
        "workflow_focus": token or "all",
        "fallback_used": fallback_used,
        "authority_boundary": SQL_AUTHORITY_BOUNDARY,
        "canonical_next_step_owner": "06. Playbooks/Active Workflows.md",
        "must_inspect_before_claim": [
            "Open the source artifact paths returned here before making content/readiness claims.",
            "Open canonical owner notes before making canon/portfolio claims.",
            "Do not infer owner approval, portfolio mutation authority, or trade/account authority from SQL rows.",
        ],
        "artifact_index_health": {
            "status": validation.get("status"),
            "summary": validation.get("summary"),
            "safety_counts": validation.get("safety_counts"),
        },
        "latest_artifact_runs": artifacts,
        "latest_source_artifacts": source_artifacts,
        "validators": validators,
        "stoplines": stoplines,
    }


def query_handoff(conn: sqlite3.Connection, db_path: Path, workflow: str | None, limit: int, json_output: bool = False) -> None:
    packet = build_handoff_packet(conn, db_path, workflow=workflow, limit=limit)
    if json_output:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return
    print(f"workflow_focus={packet['workflow_focus']} authority_boundary={packet['authority_boundary']} health={packet['artifact_index_health'].get('status')}")
    if packet.get("fallback_used"):
        print("note=No exact workflow-token SQL match; showing latest derived artifact/source rows as locator fallback.")
    print("canonical_next_step_owner=06. Playbooks/Active Workflows.md")
    print("\n[latest_artifact_runs]")
    columns = ["source_file", "artifact_type", "window", "generated_at_utc", "owner_review_required", "canonical_mutation_allowed"]
    if packet["latest_artifact_runs"]:
        print(" | ".join(columns))
        print(" | ".join("---" for _ in columns))
        for row in packet["latest_artifact_runs"]:
            print(" | ".join(clean_text(row.get(col)).replace("\n", " ")[:180] for col in columns))
    else:
        print("(no rows)")
    print("\n[latest_source_artifacts]")
    columns = ["role", "path", "status", "generated_at_utc", "read_status", "source_file"]
    if packet["latest_source_artifacts"]:
        print(" | ".join(columns))
        print(" | ".join("---" for _ in columns))
        for row in packet["latest_source_artifacts"]:
            print(" | ".join(clean_text(row.get(col)).replace("\n", " ")[:180] for col in columns))
    else:
        print("(no rows)")
    print("\n[validator_attention]")
    columns = ["source_file", "validator_name", "status", "critical", "warning", "checked_count"]
    if packet["validators"]:
        print(" | ".join(columns))
        print(" | ".join("---" for _ in columns))
        for row in packet["validators"]:
            print(" | ".join(clean_text(row.get(col)).replace("\n", " ")[:180] for col in columns))
    else:
        print("(no rows)")
    print("\n[stoplines]")
    columns = ["proposal_id", "target_file", "proposal_apply_allowed", "applied", "status", "authority_boundary"]
    if packet["stoplines"]:
        print(" | ".join(columns))
        print(" | ".join("---" for _ in columns))
        for row in packet["stoplines"]:
            print(" | ".join(clean_text(row.get(col)).replace("\n", " ")[:180] for col in columns))
    else:
        print("(no rows)")


PHASE2_RECONCILIATION_BOUNDARY = "phase2_review_only_sql_markdown_reconciliation_not_canon_not_apply"
PHASE2_SAMPLE_TICKERS = ["ETN", "NVDA", "JPM", "LMT"]
PHASE2_FORBIDDEN_AUTHORITY_TRUE_KEYS = {
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "proposal_apply_allowed",
    "trade_or_account_action_allowed",
    "trade_execution_allowed",
    "live_trade_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "generated_report_is_canonical",
    "paper_trade_submit_cancel_allowed_by_today_card",
}


PHASE3A_DRY_RUN_BOUNDARY = "phase3a_dry_run_markdown_owned_sql_cache_design_not_canon_not_apply"
PHASE3A_ALLOWED_FIELDS = {
    "post_earnings_review_confirmed",
    "earnings_lifecycle_status",
}
PHASE3A_EXCLUDED_FIELD_FAMILIES = [
    "entry_bands",
    "entry_band_values",
    "entry_band_status",
    "weights",
    "model_portfolio_weights",
    "cash",
    "sizing",
    "sleeves",
    "sector_posture",
    "owner_approval_state",
    "risk_rules",
    "account_state",
    "brokerage_state",
    "trade_state",
    "paper_order_state",
    "live_order_state",
    "credentials",
]
PHASE3A_FORBIDDEN_AUTHORITY_TRUE_KEYS = PHASE2_FORBIDDEN_AUTHORITY_TRUE_KEYS | {
    "sql_is_canon",
    "sql_owned_canon_write_allowed",
    "durable_canon_table_write_allowed",
    "markdown_mutation_allowed",
    "portfolio_mutation_allowed",
}

PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY = "phase3b_writepath_preflight_review_only_no_sql_canon_cache_writes"
PHASE3B_DURABLE_CACHE_DB = "tmp/veritas-canon-cache.sqlite"
PHASE3B_SCHEMA_VERSION = "sql_canon_phase3b_writepath_preflight.v1"
PHASE3B_FORBIDDEN_AUTHORITY_TRUE_KEYS = PHASE3A_FORBIDDEN_AUTHORITY_TRUE_KEYS | {
    "sql_write_allowed",
    "paper_trade_submit_cancel_allowed",
    "paper_trade_authority_allowed",
    "live_trade_authority_allowed",
    "account_action_allowed",
}
PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY = "phase3c_approved_sql_structured_cache_write_markdown_owned_cache_not_canon_not_apply"
PHASE3C_CACHE_SCHEMA_VERSION = "sql_canon_cache.v1"
PHASE3C_WRITE_SCHEMA_VERSION = "sql_canon_phase3c_cache_write.v1"
PHASE3C_VALIDATION_SCHEMA_VERSION = "sql_canon_phase3c_cache_validation.v1"
PHASE3C_APPROVED_CANDIDATE_KEYS = [
    "NVDA:post_earnings_review_confirmed",
    "NVDA:earnings_lifecycle_status",
]
PHASE3C_APPROVAL_ARTIFACT = "tmp/sql-canon-phase3c-approval-context.json"
PHASE3C_APPROVAL_TEXT = (
    "Randall/main approved a one-time SQL structured cache write for exactly two rows: "
    "NVDA:post_earnings_review_confirmed and NVDA:earnings_lifecycle_status, using "
    "tmp/veritas-canon-cache.sqlite, with rollback/export preflight."
)
PHASE3D_CONSUMER_PARITY_BOUNDARY = "phase3d_consumer_parity_read_only_no_consumer_migration"
PHASE3D_SCHEMA_VERSION = "sql_canon_phase3d_consumer_parity.v1"
PHASE3D_VALIDATION_SCHEMA_VERSION = "sql_canon_phase3d_consumer_parity_validation.v1"
PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY = "phase3e_dashboard_proof_metadata_pilot_sql_cache_optional_with_fallback_no_behavior_change"
PHASE3E_SCHEMA_VERSION = "sql_canon_phase3e_dashboard_proof_pilot.v1"
PHASE3E_VALIDATION_SCHEMA_VERSION = "sql_canon_phase3e_dashboard_proof_pilot_validation.v1"
PHASE3F_PREFLIGHT_BOUNDARY = "phase3f_activation_preflight_review_only_no_consumer_migration_no_write_expansion"
PHASE3F_SCHEMA_VERSION = "sql_canon_phase3f_activation_preflight.v1"
PHASE3F_VALIDATION_SCHEMA_VERSION = "sql_canon_phase3f_activation_preflight_validation.v1"
PHASE4A_SQL_CANON_BOUNDARY = "phase4a_sql_canon_authority_dashboard_proof_metadata_exact_keys_only_no_execution_authority"
PHASE4A_SCHEMA_VERSION = "sql_canon_phase4a_dashboard_proof_metadata_activation.v1"
PHASE4A_VALIDATION_SCHEMA_VERSION = "sql_canon_phase4a_dashboard_proof_metadata_activation_validation.v1"
PHASE4A_APPROVAL_ARTIFACT = "tmp/sql-canon-phase4a-approval-context.json"
PHASE4A_APPROVAL_TEXT = (
    "Randall explicitly approved implementation of Phase 4 and making SQL canon authority on "
    "2026-05-23 16:19 MST. Activation is bounded to the exact migrated canon fields "
    "NVDA:post_earnings_review_confirmed and NVDA:earnings_lifecycle_status, and to the "
    "dashboard proof-metadata consumer only. It does not authorize Markdown/canonical note "
    "mutation, portfolio mutation, owner-approval inference, paper/live trading, account action, "
    "money movement, credential use, cron changes, or any dashboard recommendation/deployment/action-state behavior change."
)
WORKSPACE_INDEX_DB = "tmp/workspace-index.sqlite"


def phase2_field_registry() -> dict[str, Any]:
    """Declare Phase 2A review-only field ownership and proof routes."""
    fields = [
        {
            "field_name": "last_earnings_date",
            "current_canonical_owner": "Markdown finance notes; generated artifacts provide proof only",
            "sql_proof_source": "v_cockpit_earnings_lifecycle.last_earnings_date; fallback v_cockpit_deployment_readiness.last_earnings_date when present in raw_json",
            "markdown_owner_note_path": "03. Portfolio/Execution Board.md",
            "markdown_owner_section": "Ticker parser-compatible section; earnings prose line if present",
            "generated_source_artifact_path": "tmp/earnings-calendar.json or tmp/deployment-readiness-surface.json",
            "source_artifact_hash_or_run_id_required": True,
            "freshness_contract": "Use artifact generated/source timestamp, not SQL insertion time; stale or absent Markdown parse becomes manual_review_required.",
            "conflict_policy": "Explicit conflict, non-promotable; inspect source artifact and owner note before any proposal.",
            "promotion_eligibility": "phase3_candidate_after_clean_repeated_reconciliation_only",
            "allowed_posture": "read-only",
        },
        {
            "field_name": "post_earnings_review_date",
            "current_canonical_owner": "Markdown finance notes; generated artifacts provide proof only",
            "sql_proof_source": "v_cockpit_earnings_lifecycle.post_earnings_review_date; fallback v_cockpit_deployment_readiness raw_json",
            "markdown_owner_note_path": "03. Portfolio/Execution Board.md",
            "markdown_owner_section": "Ticker parser-compatible section; post-earnings prose line if present",
            "generated_source_artifact_path": "tmp/earnings-calendar.json or tmp/deployment-readiness-surface.json",
            "source_artifact_hash_or_run_id_required": True,
            "freshness_contract": "Use artifact generated/source timestamp, not SQL insertion time; stale or absent Markdown parse becomes manual_review_required.",
            "conflict_policy": "Explicit conflict, non-promotable; inspect source artifact and owner note before any proposal.",
            "promotion_eligibility": "phase3_candidate_after_clean_repeated_reconciliation_only",
            "allowed_posture": "read-only",
        },
        {
            "field_name": "post_earnings_review_confirmed",
            "current_canonical_owner": "Markdown finance notes; generated artifacts provide proof only",
            "sql_proof_source": "v_cockpit_earnings_lifecycle.post_earnings_review_confirmed; v_cockpit_deployment_readiness.post_earnings_review_confirmed",
            "markdown_owner_note_path": "03. Portfolio/Execution Board.md",
            "markdown_owner_section": "Ticker parser-compatible section; post-earnings/reported prose if present",
            "generated_source_artifact_path": "tmp/earnings-calendar.json or tmp/deployment-readiness-surface.json",
            "source_artifact_hash_or_run_id_required": True,
            "freshness_contract": "Boolean comparison is exact only when Markdown explicitly indicates reviewed/confirmed/reported; otherwise manual_review_required.",
            "conflict_policy": "Explicit conflict, non-promotable; ambiguous Markdown is manual_review_required.",
            "promotion_eligibility": "phase3_candidate_after_clean_repeated_reconciliation_only",
            "allowed_posture": "read-only",
        },
        {
            "field_name": "earnings_lifecycle_status",
            "current_canonical_owner": "Markdown finance notes; SQL lifecycle table is derived proof only",
            "sql_proof_source": "v_cockpit_earnings_lifecycle.lifecycle_status",
            "markdown_owner_note_path": "03. Portfolio/Execution Board.md",
            "markdown_owner_section": "Ticker parser-compatible section; earnings/prose state",
            "generated_source_artifact_path": "tmp/earnings-calendar.json",
            "source_artifact_hash_or_run_id_required": True,
            "freshness_contract": "Compare only explicit lifecycle words; otherwise manual_review_required.",
            "conflict_policy": "Explicit conflict, non-promotable.",
            "promotion_eligibility": "phase3_candidate_after_clean_repeated_reconciliation_only",
            "allowed_posture": "read-only",
        },
        {
            "field_name": "source_freshness_classification",
            "current_canonical_owner": "Generated dashboard validation artifact; Markdown is presentation/mirror only when present",
            "sql_proof_source": "v_cockpit_source_freshness.classification by source_key",
            "markdown_owner_note_path": "05. Intelligence/Weekly Positioning Review.md",
            "markdown_owner_section": "Source freshness/currentness section if present",
            "generated_source_artifact_path": "tmp/dashboard-validation.json",
            "source_artifact_hash_or_run_id_required": True,
            "freshness_contract": "Freshness status is timestamped by dashboard-validation generated_at_utc; no canonical mutation authority.",
            "conflict_policy": "Generated artifact wins for review display; Markdown mismatch is conflict/non-promotable until inspected.",
            "promotion_eligibility": "not_phase2a_clean_match_candidate_review_surface_only",
            "allowed_posture": "read-only",
        },
        {
            "field_name": "deployment_proof_status",
            "current_canonical_owner": "03. Portfolio/Execution Board.md for action-state truth; SQL deployment readiness remains derived dashboard/index context only",
            "sql_proof_source": "v_cockpit_deployment_readiness.surface_state/bucket/review_only_no_apply_artifact",
            "markdown_owner_note_path": "03. Portfolio/Execution Board.md",
            "markdown_owner_section": "Current execution table ticker row and ticker parser-compatible section",
            "generated_source_artifact_path": "tmp/deployment-readiness-surface.json",
            "source_artifact_hash_or_run_id_required": True,
            "freshness_contract": "Current deployment_proof_status field/value set is action/deployment semantic and is not eligible for SQL-canon migration.",
            "conflict_policy": "Rejected current field / permanent-hold after WF72 Phase 9 and Gate 14; current values are display/action-state context only and cannot support activation, approval, apply readiness, or execution authority.",
            "promotion_eligibility": "rejected_current_field_permanent_hold_phase9_gate14_no_sql_canon_migration",
            "allowed_posture": "read-only",
            "migration_posture": "rejected_current_field_permanent_hold_phase9_gate14_no_sql_canon_migration",
            "activation_allowed": False,
            "current_field_migration_allowed": False,
            "neutral_replacement_requires_separate_exact_gate": True,
        },
    ]
    return {
        "schema_version": "sql_canon_phase2_field_registry.v1",
        "generated_at_utc": utc_now(),
        "authority_boundary": PHASE2_RECONCILIATION_BOUNDARY,
        "phase": "2A",
        "review_only": True,
        "sql_is_canon": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "proposal_apply_allowed": False,
        "trade_or_account_action_allowed": False,
        "owner_approval_inferred": False,
        "excluded_fields": ["entry_band_values", "entry_band_status_promotion", "sizing", "cash", "weights", "sleeves", "sector_posture", "owner_approval_state", "risk_rules", "account_or_brokerage_state"],
        "separate_contract_fields": ["next_earnings_date"],
        "fields": fields,
    }


def _parse_isoish(value: Any) -> datetime | None:
    text = clean_text(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(text[:10] + "T00:00:00+00:00")
        except ValueError:
            return None


def reconciliation_status(sql_value: Any, markdown_value: Any, sql_timestamp: Any = None, markdown_timestamp: Any = None, parse_status: str = "parsed") -> str:
    if parse_status in {"parse_failed", "manual_review_required"}:
        return parse_status
    sql_missing = clean_text(sql_value).strip() == ""
    md_missing = clean_text(markdown_value).strip() == ""
    if sql_missing and md_missing:
        return "manual_review_required"
    if sql_missing:
        return "missing_sql"
    if md_missing:
        return "missing_note"
    if clean_text(sql_value).strip().lower() == clean_text(markdown_value).strip().lower():
        return "match"
    sql_dt = _parse_isoish(sql_timestamp)
    md_dt = _parse_isoish(markdown_timestamp)
    if sql_dt and md_dt:
        if sql_dt > md_dt:
            return "sql_newer"
        if md_dt > sql_dt:
            return "note_newer"
    return "conflict"


def _read_note(path_text: str) -> tuple[Path, str, str | None, str | None]:
    path = _resolve_workspace_note(path_text)
    if not path.exists():
        return path, "", None, None
    text = path.read_text(encoding="utf-8")
    return path, text, file_mtime_utc(path), sha_text(text)


def _extract_markdown_section(text: str, heading: str) -> tuple[str, str, str]:
    marker = f"### {heading.upper()}"
    upper_text = text.upper()
    start = upper_text.find(marker)
    if start < 0:
        return "", "manual_review_required", ""
    next_start = upper_text.find("\n---\n\n### ", start + len(marker))
    if next_start < 0:
        next_start = upper_text.find("\n### ", start + len(marker))
    section = text[start: next_start if next_start > start else len(text)]
    return section, "parsed", sha_text(section)


def _extract_execution_table_rows(text: str) -> dict[str, dict[str, str]]:
    rows_by_ticker: dict[str, dict[str, str]] = {}
    lines = text.splitlines()
    headers: list[str] = []
    in_table = False
    for line in lines:
        if line.startswith("| Ticker | Lane | Action state |"):
            headers = [part.strip() for part in line.strip("|").split("|")]
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table:
            if not line.startswith("|") or line.strip() == "":
                break
            cells = [part.strip().strip("*") for part in line.strip("|").split("|")]
            if len(cells) >= len(headers):
                row = {headers[i]: cells[i] for i in range(len(headers))}
                ticker = row.get("Ticker", "").upper()
                if ticker:
                    rows_by_ticker[ticker] = row
    return rows_by_ticker


def _normalize_deployment_state(value: str) -> str:
    text = value.replace("**", "").strip().lower()
    if "deployable now" in text:
        return "DEPLOYABLE NOW"
    if "promotion review" in text:
        return "PROMOTION REVIEW"
    if "almost deployable" in text:
        return "ALMOST DEPLOYABLE"
    if "do not touch" in text:
        return "DO NOT TOUCH"
    if "watch-only" in text:
        return "WATCH / RESEARCH NEEDED"
    return text.upper()


def _extract_earnings_markdown_value(section: str, field_name: str) -> tuple[str, str]:
    lower = section.lower()
    import re
    if field_name in {"last_earnings_date", "post_earnings_review_date"}:
        candidate_lines = [line for line in section.splitlines() if any(token in line.lower() for token in ["earnings", "post-earnings", "reported"])]
        candidate_text = "\n".join(candidate_lines)
        dates = re.findall(r"20\d{2}-\d{2}-\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}", candidate_text, flags=re.I)
        if dates:
            return dates[0], "parsed"
        return "", "manual_review_required"
    if field_name == "post_earnings_review_confirmed":
        if any(token in lower for token in ["post-earnings", "reported / interpreted", "review confirmed", "evidence is captured"]):
            return "1", "parsed"
        return "", "manual_review_required"
    if field_name == "earnings_lifecycle_status":
        if "reported / interpreted" in lower or "pre-print blocker has passed" in lower:
            return "watchlist_already_closed", "parsed"
        return "", "manual_review_required"
    return "", "manual_review_required"


def _artifact_proof(conn: sqlite3.Connection, source_file: str) -> dict[str, Any]:
    row = conn.execute("SELECT id, generated_at_utc, file_mtime_utc FROM artifact_runs WHERE source_file=?", (source_file,)).fetchone()
    path = WORKSPACE / source_file.replace("/", "\\")
    return {
        "source_artifact_path": source_file,
        "source_artifact_hash": sha_file(path) if path.exists() else None,
        "artifact_run_id": int(row["id"]) if row else None,
        "sql_generated_at_utc": row["generated_at_utc"] if row else None,
        "source_file_mtime_utc": row["file_mtime_utc"] if row else None,
    }


def _phase2_row(registry_by_field: dict[str, dict[str, Any]], scope: str, field_name: str, sql_value: Any, markdown_value: Any, parse_status: str, note_path: str, note_section: str, note_hash: str | None, note_mtime: str | None, proof: dict[str, Any]) -> dict[str, Any]:
    status = reconciliation_status(sql_value, markdown_value, proof.get("sql_generated_at_utc") or proof.get("source_file_mtime_utc"), note_mtime, parse_status)
    conflict = status in {"conflict", "parse_failed", "manual_review_required"}
    return {
        "scope": scope,
        "ticker": scope if scope.isalpha() or "." in scope else None,
        "field": field_name,
        "sql_value": clean_text(sql_value),
        "markdown_value": clean_text(markdown_value),
        "source_artifact_path": proof.get("source_artifact_path"),
        "source_artifact_hash": proof.get("source_artifact_hash"),
        "artifact_run_id": proof.get("artifact_run_id"),
        "sql_generated_at_utc": proof.get("sql_generated_at_utc"),
        "note_path": note_path,
        "note_section": note_section,
        "note_mtime_utc": note_mtime,
        "note_excerpt_sha256": note_hash,
        "reconciliation_status": status,
        "review_needed": status != "match",
        "phase3_review_candidate": False if conflict or field_name in {"source_freshness_classification", "deployment_proof_status"} else status == "match",
        "authority_boundary": PHASE2_RECONCILIATION_BOUNDARY,
        "allowed_posture": registry_by_field[field_name]["allowed_posture"],
        "manual_review_required": status in {"parse_failed", "manual_review_required", "conflict", "missing_note", "missing_sql"},
        "registry_owner": registry_by_field[field_name]["current_canonical_owner"],
        "sql_proof_source": registry_by_field[field_name]["sql_proof_source"],
        "markdown_owner_path": registry_by_field[field_name]["markdown_owner_note_path"],
    }


def build_sql_markdown_reconciliation(conn: sqlite3.Connection, limit: int = 200, sample_tickers: list[str] | None = None) -> dict[str, Any]:
    registry = phase2_field_registry()
    registry_by_field = {field["field_name"]: field for field in registry["fields"]}
    rows_out: list[dict[str, Any]] = []
    exec_path = "03. Portfolio/Execution Board.md"
    _, exec_text, exec_mtime, exec_hash = _read_note(exec_path)
    table_rows = _extract_execution_table_rows(exec_text)
    sample_upper = {ticker.upper() for ticker in (sample_tickers or [])}

    lifecycle_rows = rows(conn, "SELECT * FROM v_cockpit_earnings_lifecycle ORDER BY ticker LIMIT ?", (limit,))
    for erow in lifecycle_rows:
        ticker = clean_text(erow["ticker"]).upper()
        if sample_upper and ticker not in sample_upper:
            continue
        section, section_status, section_hash = _extract_markdown_section(exec_text, ticker)
        proof = _artifact_proof(conn, clean_text(erow["source_file"]))
        for field_name, col in [
            ("last_earnings_date", "last_earnings_date"),
            ("post_earnings_review_date", "post_earnings_review_date"),
            ("post_earnings_review_confirmed", "post_earnings_review_confirmed"),
            ("earnings_lifecycle_status", "lifecycle_status"),
        ]:
            md_value, parse_status = _extract_earnings_markdown_value(section, field_name) if section_status == "parsed" else ("", section_status)
            rows_out.append(_phase2_row(registry_by_field, ticker, field_name, erow[col], md_value, parse_status, exec_path, f"### {ticker}", section_hash or exec_hash, exec_mtime, proof))

    deploy_rows = rows(conn, "SELECT * FROM v_cockpit_deployment_readiness ORDER BY ticker LIMIT ?", (limit,))
    for drow in deploy_rows:
        ticker = clean_text(drow["ticker"]).upper()
        if sample_upper and ticker not in sample_upper:
            continue
        table_row = table_rows.get(ticker)
        if table_row:
            md_value = _normalize_deployment_state(table_row.get("Action state", ""))
            parse_status = "parsed"
            note_section = "Current execution table"
            note_hash = sha_text(as_json(table_row))
        else:
            md_value = ""
            parse_status = "manual_review_required"
            note_section = "Current execution table"
            note_hash = exec_hash
        proof = _artifact_proof(conn, clean_text(drow["source_file"]))
        rows_out.append(_phase2_row(registry_by_field, ticker, "deployment_proof_status", legacy_state(drow, "surface_state"), md_value, parse_status, exec_path, note_section, note_hash, exec_mtime, proof))

    freshness_path = "05. Intelligence/Weekly Positioning Review.md"
    _, fresh_text, fresh_mtime, fresh_hash = _read_note(freshness_path)
    fresh_rows = rows(conn, "SELECT * FROM v_cockpit_source_freshness ORDER BY source_key LIMIT ?", (limit,))
    for frow in fresh_rows:
        source_key = clean_text(frow["source_key"])
        md_value = ""
        parse_status = "manual_review_required"
        for line in fresh_text.splitlines():
            if source_key.lower() in line.lower() and clean_text(frow["classification"]).lower() in line.lower():
                md_value = clean_text(frow["classification"])
                parse_status = "parsed"
                break
        proof = _artifact_proof(conn, clean_text(frow["source_file"]))
        rows_out.append(_phase2_row(registry_by_field, source_key, "source_freshness_classification", frow["classification"], md_value, parse_status, freshness_path, "source freshness/currentness section", fresh_hash, fresh_mtime, proof))

    status_counts: dict[str, int] = {}
    for row in rows_out:
        status_counts[row["reconciliation_status"]] = status_counts.get(row["reconciliation_status"], 0) + 1
    return {
        "schema_version": "sql_markdown_reconciliation.v1",
        "generated_at_utc": utc_now(),
        "authority": {
            "review_only": True,
            "sql_is_canon": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "proposal_apply_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "authority_boundary": PHASE2_RECONCILIATION_BOUNDARY,
        "field_registry_path": "tmp/sql-canon-field-registry.json",
        "summary": {
            "row_count": len(rows_out),
            "review_needed_count": sum(1 for row in rows_out if row["review_needed"]),
            "phase3_review_candidate_count": sum(1 for row in rows_out if row["phase3_review_candidate"]),
            "status_counts": status_counts,
            "sample_tickers_checked": sorted(sample_upper or set(PHASE2_SAMPLE_TICKERS)),
        },
        "rows": rows_out,
    }


def validate_sql_markdown_reconciliation(report: dict[str, Any], registry: dict[str, Any], required_samples: list[str] | None = None) -> dict[str, Any]:
    fields = {field["field_name"]: field for field in as_list(registry.get("fields")) if isinstance(field, dict)}
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    report_rows = as_list(report.get("rows"))
    add("registry_review_only_boundary", registry.get("authority_boundary") == PHASE2_RECONCILIATION_BOUNDARY and registry.get("review_only") is True)
    for key in PHASE2_FORBIDDEN_AUTHORITY_TRUE_KEYS:
        add(f"registry_forbidden_false:{key}", registry.get(key) in {False, None, 0})
    missing_registry = [row.get("field") for row in report_rows if row.get("field") not in fields]
    add("every_row_has_field_registry_owner", not missing_registry, ", ".join(sorted(set(clean_text(x) for x in missing_registry))))
    missing_paths = [f"{row.get('scope')}:{row.get('field')}" for row in report_rows if not row.get("sql_proof_source") or not row.get("markdown_owner_path") or not row.get("note_section")]
    add("every_row_has_sql_and_markdown_route", not missing_paths, "; ".join(missing_paths[:10]))
    missing_artifacts = [f"{row.get('scope')}:{row.get('field')}" for row in report_rows if not row.get("source_artifact_path") or not (row.get("source_artifact_hash") or row.get("artifact_run_id"))]
    add("every_row_has_source_artifact_hash_or_run_id", not missing_artifacts, "; ".join(missing_artifacts[:10]))
    bad_conflicts = [f"{row.get('scope')}:{row.get('field')}" for row in report_rows if row.get("reconciliation_status") == "conflict" and row.get("phase3_review_candidate")]
    add("conflicts_non_promotable", not bad_conflicts, "; ".join(bad_conflicts[:10]))
    bad_ambiguous = [f"{row.get('scope')}:{row.get('field')}" for row in report_rows if row.get("reconciliation_status") in {"parse_failed", "manual_review_required"} and not row.get("manual_review_required")]
    add("ambiguous_parsing_manual_review_required", not bad_ambiguous, "; ".join(bad_ambiguous[:10]))
    auth = as_dict(report.get("authority"))
    forbidden_true = [key for key in PHASE2_FORBIDDEN_AUTHORITY_TRUE_KEYS if auth.get(key) is True]
    add("no_forbidden_authority_in_report", not forbidden_true, ", ".join(forbidden_true))
    write_fields = [row.get("field") for row in report_rows if row.get("allowed_posture") != "read-only"]
    add("no_write_or_apply_posture_in_phase2", not write_fields, ", ".join(sorted(set(clean_text(x) for x in write_fields))))
    required = required_samples or PHASE2_SAMPLE_TICKERS
    for ticker in required:
        count = sum(1 for row in report_rows if clean_text(row.get("ticker")).upper() == ticker.upper())
        add(f"sample_ticker_checked:{ticker.upper()}", count > 0, f"rows={count}")
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": "sql_reconciliation_validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE2_RECONCILIATION_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "rows_validated": len(report_rows)},
        "checks": checks,
    }


def render_sql_markdown_reconciliation_markdown(report: dict[str, Any], validation: dict[str, Any]) -> str:
    summary = as_dict(report.get("summary"))
    lines = [
        "# SQL/Markdown reconciliation report ? Phase 2A",
        "",
        f"- Generated: {report.get('generated_at_utc')}",
        f"- Boundary: `{report.get('authority_boundary')}`",
        "- Posture: review-only; SQL remains derived proof/index/staging, not canon or apply authority.",
        f"- Rows: {summary.get('row_count')} | Review needed: {summary.get('review_needed_count')} | Phase 3 review candidates: {summary.get('phase3_review_candidate_count')}",
        f"- Status counts: `{as_json(summary.get('status_counts') or {})}`",
        f"- Validation: {validation.get('status')} ({as_dict(validation.get('summary')).get('failed')} failed / {as_dict(validation.get('summary')).get('checks')} checks)",
        "",
        "## Rows",
        "",
        "| Scope | Field | SQL value | Markdown value | Status | Review needed | Phase 3 review candidate | Source artifact | Note path/section |",
        "|---|---|---|---|---|---:|---:|---|---|",
    ]
    for row in as_list(report.get("rows")):
        values = [
            row.get("scope"), row.get("field"), row.get("sql_value"), row.get("markdown_value"),
            row.get("reconciliation_status"), row.get("review_needed"), row.get("phase3_review_candidate"),
            row.get("source_artifact_path"), f"{row.get('note_path')}#{row.get('note_section')}",
        ]
        lines.append("| " + " | ".join(clean_text(value).replace("|", "\\|").replace("\n", " ")[:160] for value in values) + " |")
    lines.append("")
    return "\n".join(lines)


def query_sql_markdown_reconciliation(conn: sqlite3.Connection, limit: int, output: str | None = None, md_output: str | None = None, validation_output: str | None = None, registry_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    registry = phase2_field_registry()
    report = build_sql_markdown_reconciliation(conn, limit=limit)
    validation = validate_sql_markdown_reconciliation(report, registry)
    default_registry = WORKSPACE / "tmp" / "sql-canon-field-registry.json"
    default_json = WORKSPACE / "tmp" / "sql-markdown-reconciliation.json"
    default_md = default_json.with_suffix(".md")
    default_validation = WORKSPACE / "tmp" / "sql-reconciliation-validation.json"
    targets = [
        (registry_output or str(default_registry), registry),
        (output or str(default_json), report),
        (validation_output or str(default_validation), validation),
    ]
    for path_text, data in targets:
        path = Path(path_text)
        if not path.is_absolute():
            path = WORKSPACE / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    md_path = Path(md_output or str(default_md))
    if (write_md or md_output) and not md_path.is_absolute():
        md_path = WORKSPACE / md_path
    if write_md or md_output:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_sql_markdown_reconciliation_markdown(report, validation), encoding="utf-8")
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} rows={report['summary']['row_count']} review_needed={report['summary']['review_needed_count']} boundary={PHASE2_RECONCILIATION_BOUNDARY}")
    outputs = [rel(default_registry), rel(default_json), rel(default_validation)]
    if write_md or md_output:
        outputs.insert(2, rel(md_path))
    print("wrote " + " ".join(outputs))


def build_phase3a_architecture_artifact(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Describe Phase 3A durable-canon/cache architecture without creating tables or writes."""
    registry = registry or phase2_field_registry()
    return {
        "schema_version": "sql_canon_phase3a_architecture.v1",
        "generated_at_utc": utc_now(),
        "phase": "3A",
        "mode": "dry_run_architecture_only",
        "authority_boundary": PHASE3A_DRY_RUN_BOUNDARY,
        "decision": "Option B: Markdown-owned canon remains active; SQL may later hold a structured cache only after explicit approval.",
        "sql_is_canon": False,
        "review_only": True,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "proposal_apply_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "sql_owned_canon_write_allowed": False,
        "durable_canon_table_write_allowed": False,
        "markdown_mutation_allowed": False,
        "recommended_storage": {
            "phase3a_dry_run": "No SQL schema/table creation; emit tmp review artifacts only.",
            "approved_future_write": "Use a separate durable canon/cache DB such as tmp/veritas-canon-cache.sqlite or an attached protected DB, never a table wiped by artifact-index rebuild/reset.",
            "proof_cockpit": "tmp/veritas-artifact-index.sqlite remains rebuildable derived proof/index/staging only.",
            "required_pragmas": ["PRAGMA journal_mode=WAL", "PRAGMA busy_timeout=5000", "PRAGMA foreign_keys=ON"],
        },
        "candidate_field_allowlist": sorted(PHASE3A_ALLOWED_FIELDS),
        "allowed_field_family": "earnings lifecycle fields only when Phase 2 reconciliation row is a clean match and phase3_review_candidate=true",
        "excluded_field_families": PHASE3A_EXCLUDED_FIELD_FAMILIES,
        "required_future_columns": [
            "scope_or_ticker",
            "field_name",
            "field_value",
            "source_artifact_path",
            "source_artifact_hash_or_run_id",
            "generated_at_utc",
            "freshness_status",
            "owner_mirror_note_path",
            "last_reconciled_at_utc",
            "authority_boundary",
            "validator_status",
            "rollback_export_metadata",
        ],
        "lineage_requirements": [
            "source_artifact_path required",
            "source_artifact_hash or artifact_run_id required",
            "sql_generated_at_utc required for freshness",
            "note_path and note_excerpt_sha256 required for mirror/reconciliation proof",
            "registry owner and SQL proof source required",
        ],
        "rollback_export_requirements": [
            "Before any future write, export last known good cache rows with hashes and schema version.",
            "A rollback artifact must be human-readable and machine-readable.",
            "Rebuild of artifact_index.py must not erase or reset future durable cache/canon DB.",
        ],
        "consumer_migration_policy": "No consumer reads from SQL cache until parity tests pass; no deployment/recommendation behavior change in Phase 3A dry-run.",
        "source_registry_boundary": registry.get("authority_boundary"),
    }


def _phase3a_rejection_reason(row: dict[str, Any]) -> str:
    field = clean_text(row.get("field"))
    if field not in PHASE3A_ALLOWED_FIELDS:
        return "field_not_in_phase3a_allowlist"
    if row.get("reconciliation_status") != "match":
        return "reconciliation_not_clean_match"
    if row.get("phase3_review_candidate") is not True:
        return "phase2_not_marked_phase3_review_candidate"
    if not row.get("source_artifact_path") or not (row.get("source_artifact_hash") or row.get("artifact_run_id")):
        return "missing_source_lineage_hash_or_run_id"
    if not row.get("sql_generated_at_utc"):
        return "missing_source_freshness_timestamp"
    if not row.get("note_path") or not row.get("note_excerpt_sha256"):
        return "missing_owner_mirror_note_lineage"
    return "eligible_dry_run_candidate"


def build_phase3a_dry_run_promotion(report: dict[str, Any], registry: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    rows_in = as_list(report.get("rows"))
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows_in:
        reason = _phase3a_rejection_reason(row)
        item = {
            "scope": row.get("scope"),
            "ticker": row.get("ticker"),
            "field": row.get("field"),
            "value": row.get("sql_value"),
            "reconciliation_status": row.get("reconciliation_status"),
            "phase2_review_candidate": row.get("phase3_review_candidate"),
            "source_artifact_path": row.get("source_artifact_path"),
            "source_artifact_hash": row.get("source_artifact_hash"),
            "artifact_run_id": row.get("artifact_run_id"),
            "sql_generated_at_utc": row.get("sql_generated_at_utc"),
            "owner_mirror_note_path": row.get("note_path"),
            "owner_mirror_note_section": row.get("note_section"),
            "note_excerpt_sha256": row.get("note_excerpt_sha256"),
            "registry_owner": row.get("registry_owner"),
            "sql_proof_source": row.get("sql_proof_source"),
            "authority_boundary": PHASE3A_DRY_RUN_BOUNDARY,
            "dry_run_only": True,
            "sql_write_allowed": False,
            "markdown_write_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
        }
        if reason == "eligible_dry_run_candidate":
            candidates.append(item)
        else:
            item["rejection_reason"] = reason
            rejected.append(item)
    return {
        "schema_version": "sql_canon_phase3a_dry_run_promotion.v1",
        "generated_at_utc": utc_now(),
        "phase": "3A",
        "mode": "dry_run_promotion_only_no_writes",
        "authority_boundary": PHASE3A_DRY_RUN_BOUNDARY,
        "review_only": True,
        "sql_is_canon": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "proposal_apply_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "sql_owned_canon_write_allowed": False,
        "durable_canon_table_write_allowed": False,
        "markdown_mutation_allowed": False,
        "phase2_report_path": "tmp/sql-markdown-reconciliation.json",
        "phase2_registry_path": "tmp/sql-canon-field-registry.json",
        "architecture_artifact_path": "tmp/sql-canon-phase3a-architecture.json",
        "allowlist": sorted(PHASE3A_ALLOWED_FIELDS),
        "excluded_field_families": PHASE3A_EXCLUDED_FIELD_FAMILIES,
        "rollback_export_required_before_future_write": True,
        "rebuild_safety_requirement": architecture.get("recommended_storage", {}).get("approved_future_write"),
        "summary": {
            "input_rows": len(rows_in),
            "candidate_count": len(candidates),
            "rejected_count": len(rejected),
            "candidate_fields": sorted({clean_text(row.get("field")) for row in candidates}),
            "candidate_scopes": sorted({clean_text(row.get("scope")) for row in candidates}),
        },
        "dry_run_candidates": candidates,
        "rejected_rows": rejected,
    }


def validate_phase3a_dry_run(architecture: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    candidates = as_list(promotion.get("dry_run_candidates"))
    rejected = as_list(promotion.get("rejected_rows"))
    add("architecture_dry_run_boundary", architecture.get("authority_boundary") == PHASE3A_DRY_RUN_BOUNDARY and architecture.get("review_only") is True)
    add("promotion_dry_run_boundary", promotion.get("authority_boundary") == PHASE3A_DRY_RUN_BOUNDARY and promotion.get("review_only") is True)
    for key in PHASE3A_FORBIDDEN_AUTHORITY_TRUE_KEYS:
        add(f"forbidden_false:architecture:{key}", architecture.get(key) in {False, None, 0})
        add(f"forbidden_false:promotion:{key}", promotion.get(key) in {False, None, 0})
    bad_fields = [clean_text(row.get("scope")) + ":" + clean_text(row.get("field")) for row in candidates if row.get("field") not in PHASE3A_ALLOWED_FIELDS]
    add("candidates_within_exact_allowlist", not bad_fields, "; ".join(bad_fields[:10]))
    bad_lineage = [clean_text(row.get("scope")) + ":" + clean_text(row.get("field")) for row in candidates if not row.get("source_artifact_path") or not (row.get("source_artifact_hash") or row.get("artifact_run_id")) or not row.get("sql_generated_at_utc") or not row.get("owner_mirror_note_path") or not row.get("note_excerpt_sha256")]
    add("candidates_have_lineage_and_freshness", not bad_lineage, "; ".join(bad_lineage[:10]))
    bad_status = [clean_text(row.get("scope")) + ":" + clean_text(row.get("field")) for row in candidates if row.get("reconciliation_status") != "match" or row.get("phase2_review_candidate") is not True]
    add("candidates_are_clean_phase2_matches", not bad_status, "; ".join(bad_status[:10]))
    bad_candidate_write_flags = [clean_text(row.get("scope")) + ":" + clean_text(row.get("field")) for row in candidates if row.get("sql_write_allowed") is not False or row.get("markdown_write_allowed") is not False or row.get("portfolio_mutation_allowed") is not False or row.get("trade_or_account_action_allowed") is not False]
    add("candidates_have_no_write_or_execution_flags", not bad_candidate_write_flags, "; ".join(bad_candidate_write_flags[:10]))
    forbidden_field_text = " ".join([clean_text(row.get("field")) for row in candidates]).lower()
    forbidden_hits = [family for family in PHASE3A_EXCLUDED_FIELD_FAMILIES if family.lower() in forbidden_field_text]
    add("no_excluded_field_families_promoted", not forbidden_hits, ", ".join(forbidden_hits))
    add("non_candidates_are_rejected_with_reasons", all(row.get("rejection_reason") for row in rejected), "")
    add("rollback_export_required", promotion.get("rollback_export_required_before_future_write") is True and bool(promotion.get("rebuild_safety_requirement")), "")
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": "sql_canon_phase3a_dry_run_validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3A_DRY_RUN_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "candidates_validated": len(candidates), "rejected_rows_checked": len(rejected)},
        "checks": checks,
    }


def render_phase3a_architecture_markdown(architecture: dict[str, Any]) -> str:
    storage = as_dict(architecture.get("recommended_storage"))
    lines = [
        "# SQL canon Phase 3A architecture dry-run",
        "",
        f"- Generated: {architecture.get('generated_at_utc')}",
        f"- Boundary: `{architecture.get('authority_boundary')}`",
        f"- Decision: {architecture.get('decision')}",
        "- Posture: dry-run only; no SQL canon/cache tables created; no Markdown/canon/portfolio writes.",
        f"- Future storage recommendation: {storage.get('approved_future_write')}",
        "",
        "## Allowlist",
        "",
        "- " + "\n- ".join(as_list(architecture.get("candidate_field_allowlist"))),
        "",
        "## Excluded field families",
        "",
        "- " + "\n- ".join(as_list(architecture.get("excluded_field_families"))),
        "",
        "## Rollback/export + rebuild safety",
        "",
    ]
    for item in as_list(architecture.get("rollback_export_requirements")):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def render_phase3a_promotion_markdown(promotion: dict[str, Any], validation: dict[str, Any]) -> str:
    summary = as_dict(promotion.get("summary"))
    lines = [
        "# SQL canon Phase 3A dry-run promotion report",
        "",
        f"- Generated: {promotion.get('generated_at_utc')}",
        f"- Boundary: `{promotion.get('authority_boundary')}`",
        "- Posture: dry-run only; SQL is not canon; no writes/apply/approval/trade authority.",
        f"- Candidates: {summary.get('candidate_count')} | Rejected: {summary.get('rejected_count')} | Validation: {validation.get('status')}",
        f"- Allowlist: `{as_json(promotion.get('allowlist') or [])}`",
        "",
        "## Dry-run candidates",
        "",
        "| Scope | Field | Value | Source artifact | Hash/run id | Note proof |",
        "|---|---|---|---|---|---|",
    ]
    for row in as_list(promotion.get("dry_run_candidates")):
        hash_or_run = row.get("source_artifact_hash") or row.get("artifact_run_id")
        values = [row.get("scope"), row.get("field"), row.get("value"), row.get("source_artifact_path"), hash_or_run, f"{row.get('owner_mirror_note_path')}#{row.get('owner_mirror_note_section')}"]
        lines.append("| " + " | ".join(clean_text(value).replace("|", "\\|").replace("\n", " ")[:160] for value in values) + " |")
    lines.extend(["", "## Rejection summary", ""])
    reason_counts: dict[str, int] = {}
    for row in as_list(promotion.get("rejected_rows")):
        reason = clean_text(row.get("rejection_reason"))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"- {reason}: {count}")
    lines.append("")
    return "\n".join(lines)


def query_phase3a_dry_run(conn: sqlite3.Connection, limit: int, architecture_output: str | None = None, architecture_md_output: str | None = None, promotion_output: str | None = None, promotion_md_output: str | None = None, validation_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    registry = phase2_field_registry()
    report = build_sql_markdown_reconciliation(conn, limit=limit)
    phase2_validation = validate_sql_markdown_reconciliation(report, registry)
    architecture = build_phase3a_architecture_artifact(registry)
    promotion = build_phase3a_dry_run_promotion(report, registry, architecture)
    validation = validate_phase3a_dry_run(architecture, promotion)
    validation["phase2_reconciliation_validation_status"] = phase2_validation.get("status")
    default_arch = WORKSPACE / "tmp" / "sql-canon-phase3a-architecture.json"
    default_arch_md = default_arch.with_suffix(".md")
    default_promo = WORKSPACE / "tmp" / "sql-canon-phase3a-dry-run-promotion.json"
    default_promo_md = default_promo.with_suffix(".md")
    default_validation = WORKSPACE / "tmp" / "sql-canon-phase3a-validation.json"
    targets = [
        (architecture_output or str(default_arch), architecture),
        (promotion_output or str(default_promo), promotion),
        (validation_output or str(default_validation), validation),
    ]
    for path_text, data in targets:
        path = Path(path_text)
        if not path.is_absolute():
            path = WORKSPACE / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    arch_md = Path(architecture_md_output or str(default_arch_md))
    promo_md = Path(promotion_md_output or str(default_promo_md))
    md_targets: list[tuple[Path, str]] = []
    if write_md or architecture_md_output:
        md_targets.append((arch_md, render_phase3a_architecture_markdown(architecture)))
    if write_md or promotion_md_output:
        md_targets.append((promo_md, render_phase3a_promotion_markdown(promotion, validation)))
    for path, content in md_targets:
        if not path.is_absolute():
            path = WORKSPACE / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if json_output:
        print(json.dumps(promotion, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} phase2={phase2_validation['status']} candidates={promotion['summary']['candidate_count']} rejected={promotion['summary']['rejected_count']} boundary={PHASE3A_DRY_RUN_BOUNDARY}")
    outputs = [rel(default_arch), rel(default_promo), rel(default_validation)]
    if write_md or architecture_md_output:
        outputs.insert(1, rel(arch_md if arch_md.is_absolute() else WORKSPACE / arch_md))
    if write_md or promotion_md_output:
        outputs.insert(-1, rel(promo_md if promo_md.is_absolute() else WORKSPACE / promo_md))
    print("wrote " + " ".join(outputs))


def build_phase3b_writepath_preflight(architecture: dict[str, Any], promotion: dict[str, Any], phase3a_validation: dict[str, Any]) -> dict[str, Any]:
    """Design the future durable SQL cache write path without creating DBs/tables or writing cache rows."""
    candidates = as_list(promotion.get("dry_run_candidates"))
    return {
        "schema_version": PHASE3B_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "phase": "3B",
        "mode": "writepath_preflight_only_no_durable_sql_writes",
        "authority_boundary": PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY,
        "review_only": True,
        "actual_write_path_blocked": True,
        "blocker": "No explicit main/Randall approval for durable SQL cache writes; this pass may only emit preflight artifacts.",
        "approval_gate_required_before_any_write": True,
        "approval_gate": {
            "required_decision_owner": "Randall/main Veritas session",
            "required_scope": "Approve exactly the Phase 3A candidate rows for a one-time SQL structured cache write preflight-to-write promotion.",
            "candidate_count": len(candidates),
            "candidate_keys": [f"{row.get('scope')}:{row.get('field')}" for row in candidates],
            "allowed_fields": sorted(PHASE3A_ALLOWED_FIELDS),
            "approval_must_not_infer": [
                "canonical note mutation", "portfolio mutation", "owner approval state", "cash/sizing/risk rules",
                "paper trading authority", "live trading authority", "account or credential action",
            ],
        },
        "sql_is_canon": False,
        "sql_write_allowed": False,
        "sql_owned_canon_write_allowed": False,
        "durable_canon_table_write_allowed": False,
        "canonical_note_mutation_allowed": False,
        "markdown_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "proposal_apply_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
        "live_trade_or_account_action_allowed": False,
        "live_trade_authority_allowed": False,
        "paper_trade_submit_cancel_allowed": False,
        "paper_trade_submit_cancel_allowed_by_today_card": False,
        "paper_trade_authority_allowed": False,
        "account_action_allowed": False,
        "money_movement_allowed": False,
        "generated_report_is_canonical": False,
        "candidate_rows": candidates,
        "durable_cache_db_plan": {
            "recommended_path": PHASE3B_DURABLE_CACHE_DB,
            "artifact_index_db": rel(DEFAULT_DB),
            "separation_rule": "Keep durable cache in a separate SQLite DB not touched by artifact_index.py rebuild/incremental reset paths.",
            "creation_in_this_phase_allowed": False,
            "tables_to_create_after_approval_only": [
                {
                    "name": "canon_cache_meta",
                    "purpose": "schema version, migration ledger pointer, created/updated timestamps, and authority boundary marker",
                    "required_columns": ["key TEXT PRIMARY KEY", "value TEXT NOT NULL"],
                },
                {
                    "name": "canon_cache_fields",
                    "purpose": "one current structured cache value per scope/field with source lineage and mirror proof",
                    "required_columns": [
                        "scope TEXT NOT NULL", "field_name TEXT NOT NULL", "field_value TEXT NOT NULL",
                        "source_artifact_path TEXT NOT NULL", "source_artifact_hash TEXT", "artifact_run_id INTEGER",
                        "sql_generated_at_utc TEXT NOT NULL", "freshness_status TEXT NOT NULL",
                        "owner_mirror_note_path TEXT NOT NULL", "owner_mirror_note_section TEXT", "note_excerpt_sha256 TEXT NOT NULL",
                        "last_reconciled_at_utc TEXT NOT NULL", "reconciliation_status TEXT NOT NULL",
                        "authority_boundary TEXT NOT NULL", "validator_status TEXT NOT NULL", "rollback_export_sha256 TEXT NOT NULL",
                        "created_at_utc TEXT NOT NULL", "updated_at_utc TEXT NOT NULL",
                        "PRIMARY KEY(scope, field_name)", "CHECK(field_name IN ('earnings_lifecycle_status','post_earnings_review_confirmed'))",
                        "CHECK(reconciliation_status='match')", "CHECK(validator_status='ok')",
                    ],
                },
                {
                    "name": "canon_cache_change_ledger",
                    "purpose": "append-only write audit for future approved writes and rollbacks",
                    "required_columns": [
                        "id INTEGER PRIMARY KEY", "operation TEXT NOT NULL", "scope TEXT NOT NULL", "field_name TEXT NOT NULL",
                        "old_value TEXT", "new_value TEXT", "source_artifact_path TEXT NOT NULL", "source_artifact_hash TEXT",
                        "approval_artifact_path TEXT NOT NULL", "rollback_export_path TEXT NOT NULL", "created_at_utc TEXT NOT NULL",
                    ],
                },
            ],
            "required_pragmas_per_connection": ["PRAGMA journal_mode=WAL", "PRAGMA busy_timeout=5000", "PRAGMA foreign_keys=ON", "PRAGMA synchronous=NORMAL"],
            "migration_plan_after_approval_only": [
                "Open separate durable cache DB with required pragmas.",
                "Create STRICT tables in a single transaction after rollback/export preflight passes.",
                "Insert only the explicitly approved candidate rows that still match Phase 2/3A validation at write time.",
                "Write append-only ledger rows tied to approval artifact and rollback export hash.",
                "Run integrity_check, foreign_key_check, and cache validator before consumers can read it.",
            ],
        },
        "rollback_export_preflight_contract": {
            "required_before_future_write": True,
            "machine_readable_path_pattern": "tmp/sql-canon-cache-rollback-export-<timestamp>.json",
            "human_readable_path_pattern": "tmp/sql-canon-cache-rollback-export-<timestamp>.md",
            "must_include": [
                "schema_version", "db_path", "table_names", "pre_write_integrity_check", "pre_write_foreign_key_check",
                "full prior rows for affected scope/field keys", "row_count", "sha256 for exported rows", "approval artifact path", "restore procedure",
            ],
            "empty_db_case": "If DB does not exist yet, export an explicit empty-db baseline with path_absent=true; do not create the DB during export preflight.",
        },
        "rebuild_safety_test_plan": [
            "Record existence/hash/mtime for tmp/veritas-canon-cache.sqlite and WAL/SHM sidecars before artifact_index.py rebuild.",
            "Run artifact_index.py rebuild against tmp/veritas-artifact-index.sqlite only.",
            "Verify durable cache DB and sidecars are unchanged or still absent if absent before test.",
            "Run artifact_index.py validate and Phase 3B preflight again; ensure candidate readiness unchanged.",
        ],
        "consumer_parity_test_plan": [
            "Keep all consumers on Markdown/generated artifact sources until parity passes.",
            "For each future consumer, compare SQL cache reads vs current Markdown/artifact read for the same scope/field.",
            "Required sample scopes: ETN, NVDA, JPM, LMT when available; NVDA must cover both Phase 3A candidate fields.",
            "No deployment/readiness/recommendation behavior may change during parity testing.",
            "Fallback to Markdown remains mandatory until main accepts parity proof.",
        ],
        "validation_inputs": {
            "phase3a_architecture_status": architecture.get("authority_boundary"),
            "phase3a_validation_status": phase3a_validation.get("status"),
            "phase3a_candidate_count": len(candidates),
            "phase3a_candidate_keys": [f"{row.get('scope')}:{row.get('field')}" for row in candidates],
        },
    }


def validate_phase3b_writepath_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    candidates = as_list(preflight.get("candidate_rows"))
    add("preflight_boundary", preflight.get("authority_boundary") == PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY and preflight.get("review_only") is True)
    add("actual_write_path_blocked", preflight.get("actual_write_path_blocked") is True and preflight.get("approval_gate_required_before_any_write") is True)
    for key in PHASE3B_FORBIDDEN_AUTHORITY_TRUE_KEYS:
        add(f"forbidden_false:preflight:{key}", preflight.get(key) in {False, None, 0})
    add("durable_db_not_created_by_contract", as_dict(preflight.get("durable_cache_db_plan")).get("creation_in_this_phase_allowed") is False)
    add("separate_db_required", as_dict(preflight.get("durable_cache_db_plan")).get("recommended_path") == PHASE3B_DURABLE_CACHE_DB)
    add("candidate_count_matches_phase3a", len(candidates) == as_dict(preflight.get("validation_inputs")).get("phase3a_candidate_count") and len(candidates) == 2)
    add("candidates_exact_allowlist", all(row.get("field") in PHASE3A_ALLOWED_FIELDS for row in candidates))
    add("candidates_still_no_write_flags", all(row.get("sql_write_allowed") is False and row.get("markdown_write_allowed") is False and row.get("portfolio_mutation_allowed") is False and row.get("trade_or_account_action_allowed") is False for row in candidates))
    add("rollback_export_contract_present", bool(as_dict(preflight.get("rollback_export_preflight_contract")).get("required_before_future_write")))
    add("rebuild_safety_plan_present", len(as_list(preflight.get("rebuild_safety_test_plan"))) >= 3)
    add("consumer_parity_plan_present", len(as_list(preflight.get("consumer_parity_test_plan"))) >= 3)
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": "sql_canon_phase3b_writepath_preflight_validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY,
        "actual_write_path_blocked": True,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "candidates_validated": len(candidates)},
        "checks": checks,
    }


def render_phase3b_preflight_markdown(preflight: dict[str, Any], validation: dict[str, Any]) -> str:
    plan = as_dict(preflight.get("durable_cache_db_plan"))
    lines = [
        "# SQL canon Phase 3B write-path preflight",
        "",
        f"- Generated: {preflight.get('generated_at_utc')}",
        f"- Boundary: `{preflight.get('authority_boundary')}`",
        f"- Validation: {validation.get('status')}",
        "- Posture: review-only preflight; no durable canon/cache DB or table creation; no SQL cache rows written.",
        "- Actual write path: BLOCKED pending explicit main/Randall approval gate.",
        f"- Future DB path: `{plan.get('recommended_path')}` separate from `tmp/veritas-artifact-index.sqlite`.",
        "",
        "## Approved-for-review candidates from Phase 3A",
        "",
        "| Scope | Field | Value | Source artifact | Note proof |",
        "|---|---|---|---|---|",
    ]
    for row in as_list(preflight.get("candidate_rows")):
        values = [row.get("scope"), row.get("field"), row.get("value"), row.get("source_artifact_path"), f"{row.get('owner_mirror_note_path')}#{row.get('owner_mirror_note_section')}"]
        lines.append("| " + " | ".join(clean_text(value).replace("|", "\\|").replace("\n", " ")[:160] for value in values) + " |")
    lines.extend(["", "## Required gate before any future write", ""])
    gate = as_dict(preflight.get("approval_gate"))
    lines.append(f"- Owner: {gate.get('required_decision_owner')}")
    lines.append(f"- Scope: {gate.get('required_scope')}")
    lines.append("- Forbidden inference: no note/portfolio/trade/account/paper/live authority.")
    lines.extend(["", "## Rollback/export preflight", ""])
    for item in as_list(as_dict(preflight.get("rollback_export_preflight_contract")).get("must_include")):
        lines.append(f"- {item}")
    lines.extend(["", "## Rebuild safety test plan", ""])
    for item in as_list(preflight.get("rebuild_safety_test_plan")):
        lines.append(f"- {item}")
    lines.extend(["", "## Consumer parity test plan", ""])
    for item in as_list(preflight.get("consumer_parity_test_plan")):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def query_phase3b_writepath_preflight(conn: sqlite3.Connection, limit: int, output: str | None = None, md_output: str | None = None, validation_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    registry = phase2_field_registry()
    report = build_sql_markdown_reconciliation(conn, limit=limit)
    architecture = build_phase3a_architecture_artifact(registry)
    promotion = build_phase3a_dry_run_promotion(report, registry, architecture)
    phase3a_validation = validate_phase3a_dry_run(architecture, promotion)
    preflight = build_phase3b_writepath_preflight(architecture, promotion, phase3a_validation)
    validation = validate_phase3b_writepath_preflight(preflight)
    default_output = WORKSPACE / "tmp" / "sql-canon-phase3b-writepath-preflight.json"
    default_md = WORKSPACE / "tmp" / "sql-canon-phase3b-writepath-preflight.md"
    default_validation = WORKSPACE / "tmp" / "sql-canon-phase3b-validation.json"
    targets = [(output or str(default_output), preflight), (validation_output or str(default_validation), validation)]
    for path_text, data in targets:
        path = Path(path_text)
        if not path.is_absolute():
            path = WORKSPACE / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    md_path = Path(md_output or str(default_md))
    if write_md or md_output:
        if not md_path.is_absolute():
            md_path = WORKSPACE / md_path
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_phase3b_preflight_markdown(preflight, validation), encoding="utf-8")
    if json_output:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} candidates={validation['summary']['candidates_validated']} write_path_blocked={preflight['actual_write_path_blocked']} boundary={PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY}")
    outputs = [rel(default_output), rel(default_validation)]
    if write_md or md_output:
        outputs.insert(1, rel(md_path))
    print("wrote " + " ".join(outputs))


def connect_canon_cache(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_canon_cache_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS canon_cache_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_cache_fields (
            scope TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_value TEXT NOT NULL,
            source_artifact_path TEXT NOT NULL,
            source_artifact_hash TEXT,
            artifact_run_id INTEGER,
            sql_generated_at_utc TEXT NOT NULL,
            freshness_status TEXT NOT NULL,
            owner_mirror_note_path TEXT NOT NULL,
            owner_mirror_note_section TEXT,
            note_excerpt_sha256 TEXT NOT NULL,
            last_reconciled_at_utc TEXT NOT NULL,
            reconciliation_status TEXT NOT NULL,
            authority_boundary TEXT NOT NULL,
            validator_status TEXT NOT NULL,
            rollback_export_sha256 TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY(scope, field_name),
            CHECK(field_name IN ('earnings_lifecycle_status','post_earnings_review_confirmed')),
            CHECK(reconciliation_status='match'),
            CHECK(validator_status='ok')
        ) STRICT;

        CREATE TABLE IF NOT EXISTS canon_cache_change_ledger (
            id INTEGER PRIMARY KEY,
            operation TEXT NOT NULL,
            scope TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            source_artifact_path TEXT NOT NULL,
            source_artifact_hash TEXT,
            approval_artifact_path TEXT NOT NULL,
            rollback_export_path TEXT NOT NULL,
            rollback_export_sha256 TEXT NOT NULL,
            authority_boundary TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            CHECK(operation IN ('insert','update','noop')),
            CHECK(field_name IN ('earnings_lifecycle_status','post_earnings_review_confirmed'))
        ) STRICT;
        """
    )


def _canon_cache_sidecar_paths(db_path: Path) -> list[Path]:
    return [db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")]


def _file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False}
    return {
        "path": rel(path),
        "exists": True,
        "size": path.stat().st_size,
        "mtime_utc": file_mtime_utc(path),
        "sha256": sha_file(path),
    }


def _canon_cache_file_states(db_path: Path) -> dict[str, dict[str, Any]]:
    return {path.name: _file_state(path) for path in _canon_cache_sidecar_paths(db_path)}


def _phase3c_candidate_core(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": row.get("scope"),
        "field": row.get("field"),
        "value": clean_text(row.get("value")),
        "reconciliation_status": row.get("reconciliation_status"),
        "phase2_review_candidate": row.get("phase2_review_candidate"),
        "source_artifact_path": row.get("source_artifact_path"),
        "source_artifact_hash": row.get("source_artifact_hash"),
        "artifact_run_id": row.get("artifact_run_id"),
        "sql_generated_at_utc": row.get("sql_generated_at_utc"),
        "owner_mirror_note_path": row.get("owner_mirror_note_path"),
        "owner_mirror_note_section": row.get("owner_mirror_note_section"),
        "note_excerpt_sha256": row.get("note_excerpt_sha256"),
    }


def _phase3c_candidate_key(row: dict[str, Any]) -> str:
    return f"{row.get('scope')}:{row.get('field')}"


def build_phase3c_live_preflight(conn: sqlite3.Connection, limit: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    registry = phase2_field_registry()
    report = build_sql_markdown_reconciliation(conn, limit=limit)
    architecture = build_phase3a_architecture_artifact(registry)
    promotion = build_phase3a_dry_run_promotion(report, registry, architecture)
    phase3a_validation = validate_phase3a_dry_run(architecture, promotion)
    preflight = build_phase3b_writepath_preflight(architecture, promotion, phase3a_validation)
    phase3b_validation = validate_phase3b_writepath_preflight(preflight)
    return promotion, phase3a_validation, preflight, phase3b_validation


def validate_phase3c_write_readiness(live_preflight: dict[str, Any], phase3a_validation: dict[str, Any], phase3b_validation: dict[str, Any], baseline_preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    candidates = as_list(live_preflight.get("candidate_rows"))
    keys = [_phase3c_candidate_key(row) for row in candidates]
    add("phase3a_validation_still_ok", phase3a_validation.get("status") == "ok")
    add("phase3b_validation_still_ok", phase3b_validation.get("status") == "ok")
    add("exact_two_approved_candidate_keys", keys == PHASE3C_APPROVED_CANDIDATE_KEYS, ", ".join(keys))
    add("approved_fields_only", all(row.get("field") in PHASE3A_ALLOWED_FIELDS for row in candidates))
    add("approved_scope_only_nvda", all(row.get("scope") == "NVDA" for row in candidates))
    add("candidates_clean_matches", all(row.get("reconciliation_status") == "match" and row.get("phase2_review_candidate") is True for row in candidates))
    add("candidate_write_flags_still_false", all(row.get("sql_write_allowed") is False and row.get("markdown_write_allowed") is False and row.get("portfolio_mutation_allowed") is False and row.get("trade_or_account_action_allowed") is False for row in candidates))
    bad_lineage = [key for key, row in zip(keys, candidates) if not row.get("source_artifact_path") or not (row.get("source_artifact_hash") or row.get("artifact_run_id")) or not row.get("sql_generated_at_utc") or not row.get("owner_mirror_note_path") or not row.get("note_excerpt_sha256")]
    add("candidate_lineage_complete", not bad_lineage, "; ".join(bad_lineage))
    if baseline_preflight is None:
        add("baseline_preflight_available_for_drift_check", False, "missing tmp/sql-canon-phase3b-writepath-preflight.json")
    else:
        baseline_rows = {_phase3c_candidate_key(row): _phase3c_candidate_core(row) for row in as_list(baseline_preflight.get("candidate_rows"))}
        live_rows = {_phase3c_candidate_key(row): _phase3c_candidate_core(row) for row in candidates}
        add("candidate_core_matches_baseline_no_drift", live_rows == baseline_rows, as_json({"baseline": baseline_rows, "live": live_rows}) if live_rows != baseline_rows else "")
    for key in PHASE3B_FORBIDDEN_AUTHORITY_TRUE_KEYS | {"sql_is_canon", "canonical_note_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed"}:
        add(f"prewrite_forbidden_false:{key}", live_preflight.get(key) in {False, None, 0})
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": "sql_canon_phase3c_prewrite_readiness.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "candidates_validated": len(candidates)},
        "checks": checks,
    }


def export_canon_cache_rollback(db_path: Path, candidates: list[dict[str, Any]], approval_artifact_path: str, timestamp: str) -> tuple[dict[str, Any], str, str]:
    rollback_path = WORKSPACE / "tmp" / f"sql-canon-cache-rollback-export-{timestamp}.json"
    rollback_md_path = WORKSPACE / "tmp" / f"sql-canon-cache-rollback-export-{timestamp}.md"
    db_exists = db_path.exists()
    affected_keys = [{"scope": row.get("scope"), "field_name": row.get("field")} for row in candidates]
    export_rows: list[dict[str, Any]] = []
    table_names: list[str] = []
    integrity = "db_absent"
    fk_check: list[Any] = []
    if db_exists:
        with connect_canon_cache(db_path) as conn:
            table_names = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_check = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
            if "canon_cache_fields" in table_names:
                for key in affected_keys:
                    for row in rows(conn, "SELECT * FROM canon_cache_fields WHERE scope=? AND field_name=?", (key["scope"], key["field_name"])):
                        export_rows.append(dict(row))
    row_hash = sha_text(as_json(export_rows))
    artifact = {
        "schema_version": "sql_canon_cache_rollback_export.v1",
        "generated_at_utc": utc_now(),
        "db_path": rel(db_path),
        "path_absent": not db_exists,
        "table_names": table_names,
        "pre_write_integrity_check": integrity,
        "pre_write_foreign_key_check": fk_check,
        "affected_keys": affected_keys,
        "prior_rows": export_rows,
        "row_count": len(export_rows),
        "rows_sha256": row_hash,
        "approval_artifact_path": approval_artifact_path,
        "restore_procedure": "If rollback is needed, restore canon_cache_fields values for affected_keys from prior_rows and append compensating canon_cache_change_ledger rows; if path_absent=true, delete only the Phase 3C-created cache DB and sidecars after main approval.",
    }
    rollback_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    md_lines = [
        "# SQL canon cache rollback export",
        "",
        f"- Generated: {artifact['generated_at_utc']}",
        f"- DB path: `{artifact['db_path']}`",
        f"- Path absent before write: {artifact['path_absent']}",
        f"- Prior affected row count: {artifact['row_count']}",
        f"- Rows SHA256: `{artifact['rows_sha256']}`",
        f"- Integrity check: `{artifact['pre_write_integrity_check']}`",
        f"- Approval artifact: `{approval_artifact_path}`",
        "",
        "## Affected keys",
        "",
    ]
    for key in affected_keys:
        md_lines.append(f"- {key['scope']}:{key['field_name']}")
    md_lines.extend(["", "## Restore procedure", "", artifact["restore_procedure"], ""])
    rollback_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return artifact, rel(rollback_path), rel(rollback_md_path)


def validate_canon_cache_db(db_path: Path, expected_candidates: list[dict[str, Any]], rollback_export_sha256: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    add("cache_db_exists", db_path.exists(), rel(db_path))
    rows_out: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    if db_path.exists():
        with connect_canon_cache(db_path) as conn:
            table_names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            add("planned_strict_tables_exist", {"canon_cache_meta", "canon_cache_fields", "canon_cache_change_ledger"}.issubset(table_names), ", ".join(sorted(table_names)))
            for table in ["canon_cache_meta", "canon_cache_fields", "canon_cache_change_ledger"]:
                strict = conn.execute("SELECT strict FROM pragma_table_list WHERE name=?", (table,)).fetchone()
                add(f"strict_table:{table}", bool(strict and strict[0] == 1))
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            add("integrity_check_ok", integrity == "ok", clean_text(integrity))
            fk_rows = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
            add("foreign_key_check_ok", not fk_rows, as_json(fk_rows))
            rows_out = [dict(row) for row in conn.execute("SELECT * FROM canon_cache_fields ORDER BY scope, field_name")]
            ledger_rows = [dict(row) for row in conn.execute("SELECT * FROM canon_cache_change_ledger ORDER BY id")]
            expected = sorted([{"scope": row.get("scope"), "field_name": row.get("field"), "field_value": clean_text(row.get("value"))} for row in expected_candidates], key=lambda x: (x["scope"], x["field_name"]))
            actual = sorted([{"scope": row.get("scope"), "field_name": row.get("field_name"), "field_value": row.get("field_value")} for row in rows_out], key=lambda x: (x["scope"], x["field_name"]))
            add("exact_two_cache_rows", len(rows_out) == 2, f"rows={len(rows_out)}")
            add("cache_rows_match_approved_candidates", actual == expected, as_json({"actual": actual, "expected": expected}) if actual != expected else "")
            add("cache_rows_clean_match_ok", all(row.get("reconciliation_status") == "match" and row.get("validator_status") == "ok" for row in rows_out))
            add("cache_rows_approved_boundary", all(row.get("authority_boundary") in {PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY, PHASE4A_SQL_CANON_BOUNDARY} for row in rows_out))
            add("ledger_has_rows_for_each_candidate", len(ledger_rows) >= len(expected_candidates), f"ledger_rows={len(ledger_rows)}")
            add("ledger_tied_to_approval", all(row.get("approval_artifact_path") in {PHASE3C_APPROVAL_ARTIFACT, PHASE4A_APPROVAL_ARTIFACT} for row in ledger_rows[-len(expected_candidates):]))
            if rollback_export_sha256:
                add("rows_tied_to_rollback_export_hash", all(row.get("rollback_export_sha256") == rollback_export_sha256 for row in rows_out), rollback_export_sha256)
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": PHASE3C_VALIDATION_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "cache_rows": len(rows_out), "ledger_rows": len(ledger_rows)},
        "checks": checks,
    }


def execute_phase3c_cache_write(conn: sqlite3.Connection, limit: int, json_output: bool = False) -> None:
    timestamp = utc_now().replace(":", "").replace("-", "").replace("Z", "Z")
    cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
    baseline_path = WORKSPACE / "tmp" / "sql-canon-phase3b-writepath-preflight.json"
    baseline_preflight = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else None
    promotion, phase3a_validation, live_preflight, phase3b_validation = build_phase3c_live_preflight(conn, limit)
    prewrite_validation = validate_phase3c_write_readiness(live_preflight, phase3a_validation, phase3b_validation, baseline_preflight)
    candidates = as_list(live_preflight.get("candidate_rows"))
    approval_artifact = {
        "schema_version": "sql_canon_phase3c_approval_context.v1",
        "generated_at_utc": utc_now(),
        "approval_text": PHASE3C_APPROVAL_TEXT,
        "approved_candidate_keys": PHASE3C_APPROVED_CANDIDATE_KEYS,
        "approved_db_path": PHASE3B_DURABLE_CACHE_DB,
        "forbidden_scope": ["Markdown/canonical note mutation", "portfolio mutation", "owner approval inference", "trade/account/paper/live authority", "cash/sizing/risk-rule/sleeve/entry-band/weight fields", "credentials/live endpoints"],
    }
    approval_path = WORKSPACE / PHASE3C_APPROVAL_ARTIFACT
    approval_path.write_text(json.dumps(approval_artifact, indent=2, sort_keys=True), encoding="utf-8")
    rollback_export, rollback_path, rollback_md_path = export_canon_cache_rollback(cache_db, candidates, PHASE3C_APPROVAL_ARTIFACT, timestamp)
    rollback_export_sha256 = sha_file(WORKSPACE / rollback_path.replace("/", "\\"))
    if prewrite_validation.get("status") != "ok":
        result = {
            "schema_version": PHASE3C_WRITE_SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "status": "blocked_no_write",
            "authority_boundary": PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY,
            "blocked_reason": "Phase 3C pre-write validation failed; no cache DB write executed.",
            "prewrite_validation": prewrite_validation,
            "rollback_export_path": rollback_path,
            "rollback_export_sha256": rollback_export_sha256,
        }
        (WORKSPACE / "tmp" / "sql-canon-phase3c-write-result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        raise RuntimeError("Phase 3C pre-write validation failed; no cache DB write executed")
    before_rebuild_states = _canon_cache_file_states(cache_db)
    now = utc_now()
    written_rows: list[dict[str, Any]] = []
    with connect_canon_cache(cache_db) as cache_conn:
        cache_conn.execute("BEGIN IMMEDIATE")
        init_canon_cache_schema(cache_conn)
        cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("schema_version", PHASE3C_CACHE_SCHEMA_VERSION))
        cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("authority_boundary", PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY))
        cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("updated_at_utc", now))
        for row in candidates:
            old = cache_conn.execute("SELECT field_value FROM canon_cache_fields WHERE scope=? AND field_name=?", (row.get("scope"), row.get("field"))).fetchone()
            old_value = old["field_value"] if old else None
            operation = "insert" if old is None else ("noop" if old_value == clean_text(row.get("value")) else "update")
            existing_created = cache_conn.execute("SELECT created_at_utc FROM canon_cache_fields WHERE scope=? AND field_name=?", (row.get("scope"), row.get("field"))).fetchone()
            created_at = existing_created["created_at_utc"] if existing_created else now
            cache_conn.execute(
                """
                INSERT INTO canon_cache_fields(
                    scope, field_name, field_value, source_artifact_path, source_artifact_hash, artifact_run_id,
                    sql_generated_at_utc, freshness_status, owner_mirror_note_path, owner_mirror_note_section,
                    note_excerpt_sha256, last_reconciled_at_utc, reconciliation_status, authority_boundary,
                    validator_status, rollback_export_sha256, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, field_name) DO UPDATE SET
                    field_value=excluded.field_value,
                    source_artifact_path=excluded.source_artifact_path,
                    source_artifact_hash=excluded.source_artifact_hash,
                    artifact_run_id=excluded.artifact_run_id,
                    sql_generated_at_utc=excluded.sql_generated_at_utc,
                    freshness_status=excluded.freshness_status,
                    owner_mirror_note_path=excluded.owner_mirror_note_path,
                    owner_mirror_note_section=excluded.owner_mirror_note_section,
                    note_excerpt_sha256=excluded.note_excerpt_sha256,
                    last_reconciled_at_utc=excluded.last_reconciled_at_utc,
                    reconciliation_status=excluded.reconciliation_status,
                    authority_boundary=excluded.authority_boundary,
                    validator_status=excluded.validator_status,
                    rollback_export_sha256=excluded.rollback_export_sha256,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    row.get("scope"), row.get("field"), clean_text(row.get("value")), row.get("source_artifact_path"), row.get("source_artifact_hash"), row.get("artifact_run_id"),
                    row.get("sql_generated_at_utc"), "fresh", row.get("owner_mirror_note_path"), row.get("owner_mirror_note_section"),
                    row.get("note_excerpt_sha256"), now, row.get("reconciliation_status"), PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY,
                    "ok", rollback_export_sha256, created_at, now,
                ),
            )
            cache_conn.execute(
                """
                INSERT INTO canon_cache_change_ledger(operation, scope, field_name, old_value, new_value, source_artifact_path,
                    source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (operation, row.get("scope"), row.get("field"), old_value, clean_text(row.get("value")), row.get("source_artifact_path"), row.get("source_artifact_hash"), PHASE3C_APPROVAL_ARTIFACT, rollback_path, rollback_export_sha256, PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY, now),
            )
            written_rows.append({"scope": row.get("scope"), "field_name": row.get("field"), "field_value": clean_text(row.get("value")), "operation": operation})
        cache_conn.commit()
    post_write_validation = validate_canon_cache_db(cache_db, candidates, rollback_export_sha256)
    after_write_states = _canon_cache_file_states(cache_db)
    artifact_rebuild_before = _canon_cache_file_states(cache_db)
    rebuild(DEFAULT_DB)
    artifact_rebuild_after = _canon_cache_file_states(cache_db)
    rebuild_safety = {
        "before_rebuild": artifact_rebuild_before,
        "after_rebuild": artifact_rebuild_after,
        "cache_db_preserved_after_artifact_index_rebuild": artifact_rebuild_before.get(cache_db.name, {}).get("sha256") == artifact_rebuild_after.get(cache_db.name, {}).get("sha256"),
    }
    artifact_index_validation = validate_index(DEFAULT_DB)
    final_cache_validation = validate_canon_cache_db(cache_db, candidates, rollback_export_sha256)
    result = {
        "schema_version": PHASE3C_WRITE_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if post_write_validation.get("status") == "ok" and final_cache_validation.get("status") == "ok" and artifact_index_validation.get("status") == "ok" and rebuild_safety["cache_db_preserved_after_artifact_index_rebuild"] else "failed",
        "authority_boundary": PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY,
        "sql_is_canon": False,
        "canonical_note_mutation_allowed": False,
        "markdown_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
        "db_path": PHASE3B_DURABLE_CACHE_DB,
        "approval_artifact_path": PHASE3C_APPROVAL_ARTIFACT,
        "rollback_export_path": rollback_path,
        "rollback_export_md_path": rollback_md_path,
        "rollback_export_sha256": rollback_export_sha256,
        "rollback_export_rows_sha256": rollback_export.get("rows_sha256"),
        "written_rows": written_rows,
        "prewrite_validation": prewrite_validation,
        "post_write_validation": post_write_validation,
        "final_cache_validation": final_cache_validation,
        "artifact_index_validation_status": artifact_index_validation.get("status"),
        "cache_file_states_before_write": before_rebuild_states,
        "cache_file_states_after_write": after_write_states,
        "rebuild_safety": rebuild_safety,
    }
    result_path = WORKSPACE / "tmp" / "sql-canon-phase3c-write-result.json"
    result_md_path = WORKSPACE / "tmp" / "sql-canon-phase3c-write-result.md"
    validation_path = WORKSPACE / "tmp" / "sql-canon-phase3c-validation.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(json.dumps(final_cache_validation, indent=2, sort_keys=True), encoding="utf-8")
    md_lines = [
        "# SQL canon Phase 3C approved cache write result",
        "",
        f"- Generated: {result['generated_at_utc']}",
        f"- Status: {result['status']}",
        f"- Boundary: `{result['authority_boundary']}`",
        "- Posture: SQL structured cache only; SQL is not canon/apply/approval/trade authority; Markdown/canonical notes were not mutated.",
        f"- DB path: `{PHASE3B_DURABLE_CACHE_DB}`",
        f"- Rollback export: `{rollback_path}` (`{rollback_export_sha256}`)",
        "",
        "## Rows written",
        "",
        "| Scope | Field | Value | Operation |",
        "|---|---|---|---|",
    ]
    for row in written_rows:
        md_lines.append("| " + " | ".join(clean_text(row.get(col)) for col in ["scope", "field_name", "field_value", "operation"]) + " |")
    md_lines.extend(["", "## Proof", "", f"- Cache validation: {final_cache_validation.get('status')}", f"- Artifact-index validation after rebuild: {artifact_index_validation.get('status')}", f"- Cache DB preserved after artifact-index rebuild: {rebuild_safety['cache_db_preserved_after_artifact_index_rebuild']}", ""])
    result_md_path.write_text("\n".join(md_lines), encoding="utf-8")
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"status={result['status']} rows={len(written_rows)} cache_validation={final_cache_validation['status']} rebuild_safe={rebuild_safety['cache_db_preserved_after_artifact_index_rebuild']} boundary={PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY}")
    print(f"wrote {rel(result_path)} {rel(result_md_path)} {rel(validation_path)} {rollback_path} {rollback_md_path} {PHASE3C_APPROVAL_ARTIFACT}")


def read_canon_cache_rows_readonly(db_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read Phase 3C cache rows without creating or mutating the cache database."""
    if not db_path.exists():
        return [], {"db_path": rel(db_path), "exists": False, "read_mode": "not_opened_missing_db"}
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        table_names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        if "canon_cache_fields" not in table_names:
            return [], {"db_path": rel(db_path), "exists": True, "read_mode": "sqlite_ro", "integrity_check": integrity, "table_names": table_names}
        cache_rows = [dict(row) for row in conn.execute("SELECT * FROM canon_cache_fields ORDER BY scope, field_name")]
    return cache_rows, {"db_path": rel(db_path), "exists": True, "read_mode": "sqlite_ro", "integrity_check": integrity, "table_names": table_names}


def _phase3d_generated_artifact_value(source_artifact_path: str, scope: str, field_name: str) -> str:
    """Read the current generated artifact value directly for the two approved NVDA lifecycle fields."""
    path = WORKSPACE / source_artifact_path.replace("/", "\\")
    if not path.exists() or path.name != "earnings-calendar.json":
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    ticker = scope.upper()
    for hold in as_list(as_dict(data.get("earnings_lifecycle")).get("active_holds")):
        if clean_text(hold.get("ticker")).upper() != ticker:
            continue
        if field_name == "earnings_lifecycle_status":
            return clean_text(hold.get("status"))
        if field_name == "post_earnings_review_confirmed":
            value = as_dict(hold.get("evidence")).get("post_earnings_review_confirmed")
            return "1" if value is True else ("0" if value is False else clean_text(value))
    for record in as_list(data.get("records")):
        if clean_text(record.get("ticker")).upper() != ticker:
            continue
        lifecycle = as_dict(record.get("lifecycle"))
        if field_name == "post_earnings_review_confirmed":
            value = as_dict(lifecycle.get("evidence")).get("post_earnings_review_confirmed")
            return "1" if value is True else ("0" if value is False else clean_text(value))
    return ""


def build_phase3d_consumer_parity(conn: sqlite3.Connection, limit: int) -> dict[str, Any]:
    """Compare Phase 3C SQL cache rows to current Markdown/generated proof sources without migrating consumers."""
    cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
    cache_rows, cache_read = read_canon_cache_rows_readonly(cache_db)
    reconciliation = build_sql_markdown_reconciliation(conn, limit=limit)
    recon_by_key = {f"{row.get('scope')}:{row.get('field')}": row for row in as_list(reconciliation.get("rows"))}
    cache_by_key = {f"{row.get('scope')}:{row.get('field_name')}": row for row in cache_rows}
    parity_rows: list[dict[str, Any]] = []
    for key in PHASE3C_APPROVED_CANDIDATE_KEYS:
        scope, field_name = key.split(":", 1)
        cache_row = cache_by_key.get(key) or {}
        recon_row = recon_by_key.get(key) or {}
        cache_value = clean_text(cache_row.get("field_value"))
        sql_value = clean_text(recon_row.get("sql_value"))
        markdown_value = clean_text(recon_row.get("markdown_value"))
        direct_generated_value = _phase3d_generated_artifact_value(clean_text(recon_row.get("source_artifact_path")), scope, field_name)
        generated_artifact_consistent = bool(
            cache_value
            and cache_value == sql_value
            and cache_value == direct_generated_value
            and cache_row.get("source_artifact_path") == recon_row.get("source_artifact_path")
            and (clean_text(cache_row.get("source_artifact_hash")) == clean_text(recon_row.get("source_artifact_hash")) or clean_text(cache_row.get("artifact_run_id")) == clean_text(recon_row.get("artifact_run_id")))
        )
        markdown_consistent = bool(
            cache_value
            and cache_value == markdown_value
            and cache_row.get("owner_mirror_note_path") == recon_row.get("markdown_owner_path")
            and clean_text(cache_row.get("note_excerpt_sha256")) == clean_text(recon_row.get("note_excerpt_sha256"))
        )
        status = "consistent" if generated_artifact_consistent and markdown_consistent and recon_row.get("reconciliation_status") == "match" else "conflict_review_required"
        parity_rows.append({
            "key": key,
            "scope": scope,
            "field": field_name,
            "cache_value": cache_value,
            "current_generated_sql_value": sql_value,
            "current_generated_artifact_value": direct_generated_value,
            "current_markdown_value": markdown_value,
            "source_artifact_path_cache": cache_row.get("source_artifact_path"),
            "source_artifact_path_current": recon_row.get("source_artifact_path"),
            "source_artifact_hash_cache": cache_row.get("source_artifact_hash"),
            "source_artifact_hash_current": recon_row.get("source_artifact_hash"),
            "artifact_run_id_cache": cache_row.get("artifact_run_id"),
            "artifact_run_id_current": recon_row.get("artifact_run_id"),
            "owner_mirror_note_path_cache": cache_row.get("owner_mirror_note_path"),
            "markdown_owner_path_current": recon_row.get("markdown_owner_path"),
            "note_excerpt_sha256_cache": cache_row.get("note_excerpt_sha256"),
            "note_excerpt_sha256_current": recon_row.get("note_excerpt_sha256"),
            "cache_authority_boundary": cache_row.get("authority_boundary"),
            "current_reconciliation_status": recon_row.get("reconciliation_status"),
            "generated_artifact_parity_status": "consistent" if generated_artifact_consistent else "conflict_review_required",
            "markdown_parity_status": "consistent" if markdown_consistent else "conflict_review_required",
            "overall_parity_status": status,
            "consumer_migration_allowed": False,
            "behavior_change_allowed": False,
        })
    consumer_parity_plan = [
        {"order": 1, "consumer_family": "dashboard proof metadata", "phase3d_action": "parity_compare_only", "fallback_required": True, "migration_allowed_now": False},
        {"order": 2, "consumer_family": "trigger sheet freshness/lifecycle reads", "phase3d_action": "parity_compare_only", "fallback_required": True, "migration_allowed_now": False},
        {"order": 3, "consumer_family": "post-earnings prep/note-target context", "phase3d_action": "parity_compare_only", "fallback_required": True, "migration_allowed_now": False},
        {"order": 4, "consumer_family": "run summary / handoff packets", "phase3d_action": "parity_compare_only", "fallback_required": True, "migration_allowed_now": False},
    ]
    return {
        "schema_version": PHASE3D_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if all(row["overall_parity_status"] == "consistent" for row in parity_rows) and cache_read.get("exists") else "blocked",
        "authority_boundary": PHASE3D_CONSUMER_PARITY_BOUNDARY,
        "db_path": PHASE3B_DURABLE_CACHE_DB,
        "approved_candidate_keys": PHASE3C_APPROVED_CANDIDATE_KEYS,
        "cache_read": cache_read,
        "parity_rows": parity_rows,
        "consumer_parity_plan": consumer_parity_plan,
        "consumer_migration_allowed": False,
        "dashboard_or_trigger_behavior_change_allowed": False,
        "canonical_note_mutation_allowed": False,
        "markdown_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
    }


def validate_phase3d_consumer_parity(parity: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    rows_out = as_list(parity.get("parity_rows"))
    keys = [row.get("key") for row in rows_out]
    add("phase3d_boundary", parity.get("authority_boundary") == PHASE3D_CONSUMER_PARITY_BOUNDARY)
    add("cache_db_readonly_available", as_dict(parity.get("cache_read")).get("exists") is True and as_dict(parity.get("cache_read")).get("read_mode") == "sqlite_ro", as_json(parity.get("cache_read")))
    add("exact_two_approved_keys", keys == PHASE3C_APPROVED_CANDIDATE_KEYS, ", ".join(clean_text(key) for key in keys))
    add("all_rows_consistent", all(row.get("overall_parity_status") == "consistent" for row in rows_out), as_json(rows_out))
    add("generated_artifact_parity_consistent", all(row.get("generated_artifact_parity_status") == "consistent" for row in rows_out))
    add("markdown_parity_consistent", all(row.get("markdown_parity_status") == "consistent" for row in rows_out))
    add("cache_rows_approved_boundary", all(row.get("cache_authority_boundary") in {PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY, PHASE4A_SQL_CANON_BOUNDARY} for row in rows_out))
    add("current_reconciliation_still_match", all(row.get("current_reconciliation_status") == "match" for row in rows_out))
    add("no_consumer_migration_or_behavior_change", parity.get("consumer_migration_allowed") is False and parity.get("dashboard_or_trigger_behavior_change_allowed") is False and all(row.get("consumer_migration_allowed") is False and row.get("behavior_change_allowed") is False for row in rows_out))
    for key in ["canonical_note_mutation_allowed", "markdown_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed", "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed"]:
        add(f"forbidden_false:{key}", parity.get(key) is False)
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": PHASE3D_VALIDATION_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3D_CONSUMER_PARITY_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "rows_validated": len(rows_out)},
        "checks": checks,
    }


def render_phase3d_consumer_parity_markdown(parity: dict[str, Any], validation: dict[str, Any]) -> str:
    lines = [
        "# SQL canon Phase 3D consumer parity",
        "",
        f"- Generated: {parity.get('generated_at_utc')}",
        f"- Status: {parity.get('status')}",
        f"- Validation: {validation.get('status')}",
        f"- Boundary: `{parity.get('authority_boundary')}`",
        "- Scope: read-only parity plan/test artifacts for exactly NVDA:post_earnings_review_confirmed and NVDA:earnings_lifecycle_status.",
        "- Stop line: no consumer migration, no dashboard/trigger/handoff behavior change, no Markdown/canon/portfolio mutation, no trade/account/paper/live authority.",
        "",
        "## Parity rows",
        "",
        "| Key | Cache value | Generated artifact value | Generated/SQL value | Markdown value | Generated parity | Markdown parity | Overall |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in as_list(parity.get("parity_rows")):
        lines.append("| " + " | ".join(clean_text(row.get(col)) for col in ["key", "cache_value", "current_generated_artifact_value", "current_generated_sql_value", "current_markdown_value", "generated_artifact_parity_status", "markdown_parity_status", "overall_parity_status"]) + " |")
    lines.extend(["", "## Consumer plan", ""])
    for item in as_list(parity.get("consumer_parity_plan")):
        lines.append(f"- {item.get('order')}. {item.get('consumer_family')}: {item.get('phase3d_action')}; fallback_required={item.get('fallback_required')}; migration_allowed_now={item.get('migration_allowed_now')}")
    lines.extend(["", "## Validation checks", ""])
    for check in as_list(validation.get("checks")):
        lines.append(f"- {'ok' if check.get('ok') else 'FAIL'} | {check.get('name')} | {check.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def query_phase3d_consumer_parity(conn: sqlite3.Connection, limit: int, output: str | None = None, md_output: str | None = None, validation_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    parity = build_phase3d_consumer_parity(conn, limit)
    validation = validate_phase3d_consumer_parity(parity)
    parity["status"] = "ok" if validation.get("status") == "ok" else "blocked"
    output_path = WORKSPACE / (output or "tmp/sql-canon-phase3d-consumer-parity.json")
    md_path = WORKSPACE / (md_output or "tmp/sql-canon-phase3d-consumer-parity.md")
    validation_path = WORKSPACE / (validation_output or "tmp/sql-canon-phase3d-validation.json")
    write_targets = [(output_path, json.dumps(parity, indent=2, sort_keys=True)), (validation_path, json.dumps(validation, indent=2, sort_keys=True))]
    if write_md or md_output:
        write_targets.append((md_path, render_phase3d_consumer_parity_markdown(parity, validation)))
    for path, content in write_targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if json_output:
        print(json.dumps(parity, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} rows={validation['summary']['rows_validated']} consumer_migration_allowed={parity['consumer_migration_allowed']} boundary={PHASE3D_CONSUMER_PARITY_BOUNDARY}")
    outputs = [rel(output_path), rel(validation_path)]
    if write_md or md_output:
        outputs.insert(1, rel(md_path))
    print("wrote " + " ".join(outputs))


def build_phase3e_dashboard_proof_pilot(conn: sqlite3.Connection, limit: int) -> dict[str, Any]:
    """Pilot dashboard proof-metadata reads from the Phase 3C cache with artifact fallback.

    This intentionally does not mutate dashboard payloads or deployment logic. It is a
    proof artifact for the first consumer-migration lane only: dashboard proof metadata.
    """
    parity = build_phase3d_consumer_parity(conn, limit)
    parity_validation = validate_phase3d_consumer_parity(parity)
    cache_rows, cache_read = read_canon_cache_rows_readonly(WORKSPACE / PHASE3B_DURABLE_CACHE_DB)
    cache_by_key = {f"{row.get('scope')}:{row.get('field_name')}": row for row in cache_rows}
    parity_by_key = {row.get("key"): row for row in as_list(parity.get("parity_rows"))}
    rows_out: list[dict[str, Any]] = []
    for key in PHASE3C_APPROVED_CANDIDATE_KEYS:
        scope, field_name = key.split(":", 1)
        cache_row = cache_by_key.get(key) or {}
        parity_row = parity_by_key.get(key) or {}
        cache_value = clean_text(cache_row.get("field_value"))
        fallback_value = clean_text(parity_row.get("current_generated_artifact_value")) or clean_text(parity_row.get("current_markdown_value"))
        sql_cache_usable = bool(
            cache_value
            and cache_read.get("read_mode") == "sqlite_ro"
            and parity_row.get("overall_parity_status") == "consistent"
            and parity_validation.get("status") == "ok"
        )
        rows_out.append({
            "key": key,
            "scope": scope,
            "field": field_name,
            "dashboard_consumer_family": "dashboard proof metadata",
            "pilot_read_source": "sql_cache" if sql_cache_usable else "generated_artifact_fallback",
            "sql_cache_value": cache_value,
            "fallback_generated_artifact_value": clean_text(parity_row.get("current_generated_artifact_value")),
            "fallback_markdown_value": clean_text(parity_row.get("current_markdown_value")),
            "effective_metadata_value": cache_value if sql_cache_usable else fallback_value,
            "fallback_available": bool(fallback_value),
            "parity_status": parity_row.get("overall_parity_status") or "missing_parity_row",
            "cache_authority_boundary": cache_row.get("authority_boundary"),
            "source_artifact_path": parity_row.get("source_artifact_path_current") or parity_row.get("source_artifact_path_cache"),
            "owner_mirror_note_path": parity_row.get("markdown_owner_path_current") or parity_row.get("owner_mirror_note_path_cache"),
            "metadata_only": True,
            "dashboard_payload_mutated": False,
            "dashboard_behavior_change_allowed": False,
            "recommendation_or_deployment_behavior_changed": False,
        })
    return {
        "schema_version": PHASE3E_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if parity_validation.get("status") == "ok" and all(row.get("fallback_available") for row in rows_out) else "blocked",
        "authority_boundary": PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY,
        "consumer_family": "dashboard proof metadata",
        "pilot_scope": "exact_two_nvda_earnings_lifecycle_cache_fields_only",
        "approved_candidate_keys": PHASE3C_APPROVED_CANDIDATE_KEYS,
        "cache_read": cache_read,
        "parity_validation_status": parity_validation.get("status"),
        "phase3d_parity_rows": as_list(parity.get("parity_rows")),
        "dashboard_metadata_rows": rows_out,
        "fallback_policy": "If SQL cache is missing, unreadable, outside the exact key allowlist, or not parity-consistent, dashboard proof metadata must use existing generated-artifact/Markdown fallback values.",
        "dashboard_payload_mutated": False,
        "dashboard_or_trigger_behavior_change_allowed": False,
        "consumer_migration_allowed": False,
        "canonical_note_mutation_allowed": False,
        "markdown_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
    }


def validate_phase3e_dashboard_proof_pilot(pilot: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    rows_out = as_list(pilot.get("dashboard_metadata_rows"))
    keys = [row.get("key") for row in rows_out]
    add("phase3e_boundary", pilot.get("authority_boundary") == PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY)
    add("exact_two_approved_keys_only", keys == PHASE3C_APPROVED_CANDIDATE_KEYS, ", ".join(clean_text(key) for key in keys))
    add("dashboard_metadata_consumer_only", pilot.get("consumer_family") == "dashboard proof metadata" and all(row.get("dashboard_consumer_family") == "dashboard proof metadata" for row in rows_out))
    add("phase3d_parity_still_clean", pilot.get("parity_validation_status") == "ok" and all(row.get("parity_status") == "consistent" for row in rows_out))
    add("fallback_available_for_every_row", all(row.get("fallback_available") is True and clean_text(row.get("fallback_generated_artifact_value")) for row in rows_out))
    add("sql_cache_optional_or_readonly", as_dict(pilot.get("cache_read")).get("read_mode") in {"sqlite_ro", "not_opened_missing_db"})
    add("metadata_only_no_payload_mutation", pilot.get("dashboard_payload_mutated") is False and all(row.get("metadata_only") is True and row.get("dashboard_payload_mutated") is False for row in rows_out))
    add("no_dashboard_or_deployment_behavior_change", pilot.get("dashboard_or_trigger_behavior_change_allowed") is False and all(row.get("dashboard_behavior_change_allowed") is False and row.get("recommendation_or_deployment_behavior_changed") is False for row in rows_out))
    add("no_consumer_migration", pilot.get("consumer_migration_allowed") is False)
    for key in ["canonical_note_mutation_allowed", "markdown_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed", "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed"]:
        add(f"forbidden_false:{key}", pilot.get(key) is False)
    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "schema_version": PHASE3E_VALIDATION_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "rows_validated": len(rows_out)},
        "checks": checks,
    }


def render_phase3e_dashboard_proof_pilot_markdown(pilot: dict[str, Any], validation: dict[str, Any]) -> str:
    lines = [
        "# SQL canon Phase 3E dashboard proof metadata pilot",
        "",
        f"- Generated: {pilot.get('generated_at_utc')}",
        f"- Status: {pilot.get('status')}",
        f"- Validation: {validation.get('status')}",
        f"- Boundary: `{pilot.get('authority_boundary')}`",
        "- Scope: dashboard proof metadata only for exactly NVDA:post_earnings_review_confirmed and NVDA:earnings_lifecycle_status.",
        "- Stop line: no dashboard payload mutation, no recommendation/deployment/action-state behavior change, no trigger/handoff/post-earnings migration.",
        "- Fallback: generated artifact / Markdown proof remains available and required.",
        "",
        "## Pilot metadata rows",
        "",
        "| Key | Pilot read source | SQL cache value | Generated fallback | Markdown fallback | Effective metadata | Parity |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in as_list(pilot.get("dashboard_metadata_rows")):
        lines.append("| " + " | ".join(clean_text(row.get(col)) for col in ["key", "pilot_read_source", "sql_cache_value", "fallback_generated_artifact_value", "fallback_markdown_value", "effective_metadata_value", "parity_status"]) + " |")
    lines.extend(["", "## Validation checks", ""])
    for check in as_list(validation.get("checks")):
        lines.append(f"- {'ok' if check.get('ok') else 'FAIL'} | {check.get('name')} | {check.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def query_phase3e_dashboard_proof_pilot(conn: sqlite3.Connection, limit: int, output: str | None = None, md_output: str | None = None, validation_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    pilot = build_phase3e_dashboard_proof_pilot(conn, limit)
    validation = validate_phase3e_dashboard_proof_pilot(pilot)
    pilot["status"] = "ok" if validation.get("status") == "ok" else "blocked"
    output_path = WORKSPACE / (output or "tmp/sql-canon-phase3e-dashboard-proof-pilot.json")
    md_path = WORKSPACE / (md_output or "tmp/sql-canon-phase3e-dashboard-proof-pilot.md")
    validation_path = WORKSPACE / (validation_output or "tmp/sql-canon-phase3e-validation.json")
    write_targets = [(output_path, json.dumps(pilot, indent=2, sort_keys=True)), (validation_path, json.dumps(validation, indent=2, sort_keys=True))]
    if write_md or md_output:
        write_targets.append((md_path, render_phase3e_dashboard_proof_pilot_markdown(pilot, validation)))
    for path, content in write_targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if json_output:
        print(json.dumps(pilot, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} rows={validation['summary']['rows_validated']} dashboard_behavior_change_allowed={pilot['dashboard_or_trigger_behavior_change_allowed']} boundary={PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY}")
    outputs = [rel(output_path), rel(validation_path)]
    if write_md or md_output:
        outputs.insert(1, rel(md_path))
    print("wrote " + " ".join(outputs))


def _parse_iso_utc(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def build_sql_consumer_authority_guard(conn: sqlite3.Connection) -> dict[str, Any]:
    placeholders = ",".join("?" for _ in FORBIDDEN_TRUE_AUTHORITY_FLAGS)
    forbidden_rows = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT artifact_run_id, flag_name, flag_value, surface, raw_value, source_file
            FROM authority_flags
            WHERE flag_value != 0 AND flag_name IN ({placeholders})
            ORDER BY source_file, flag_name
            """,
            tuple(sorted(FORBIDDEN_TRUE_AUTHORITY_FLAGS)),
        )
    ]
    canon_stage_apply = conn.execute("SELECT COUNT(*) FROM canon_proposal_staging WHERE proposal_apply_allowed != 0").fetchone()[0]
    cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
    cache_read: dict[str, Any] = {"db_path": PHASE3B_DURABLE_CACHE_DB, "exists": cache_db.exists(), "read_mode": "not_opened_missing_db"}
    cache_forbidden_rows: list[dict[str, Any]] = []
    if cache_db.exists():
        cache_rows, cache_read = read_canon_cache_rows_readonly(cache_db)
        from sql_consumer_authority_guard import (
            ENTRY_STOP_REFERENCE_METADATA_FIELDS,
            LOW_RISK_SQL_CANON_BOUNDARY,
            WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
            active_entry_stop_reference_keys,
            active_sql_canon_approved_keys,
        )

        allowed_keys = active_sql_canon_approved_keys()
        active_entry_stop_keys = set(active_entry_stop_reference_keys())
        allowed = {(key.split(":", 1)[0], key.split(":", 1)[1]) for key in allowed_keys}
        allowed_boundaries = {
            PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY,
            PHASE4A_SQL_CANON_BOUNDARY,
            LOW_RISK_SQL_CANON_BOUNDARY,
            WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
        }
        for row in cache_rows:
            field_name = clean_text(row.get("field_name"))
            key = f"{row.get('scope')}:{field_name}"
            is_active_entry_stop_reference_key = key in active_entry_stop_keys and field_name in ENTRY_STOP_REFERENCE_METADATA_FIELDS
            family_blocked = any(term in field_name.lower() for term in ["entry", "weight", "cash", "sizing", "risk", "trade", "paper", "live", "account", "credential"]) and not is_active_entry_stop_reference_key
            if (row.get("scope"), field_name) not in allowed or family_blocked or row.get("authority_boundary") not in allowed_boundaries:
                cache_forbidden_rows.append(row)
    return {
        "status": "ok" if not forbidden_rows and canon_stage_apply == 0 and not cache_forbidden_rows and as_dict(cache_read).get("integrity_check", "ok") == "ok" else "blocked",
        "generated_at_utc": utc_now(),
        "authority_boundary": PHASE3F_PREFLIGHT_BOUNDARY,
        "guard_name": "sql_consumer_forbidden_authority_guard",
        "consumer_side_required_before_non_optional_sql_reads": True,
        "forbidden_true_authority_flags": sorted(FORBIDDEN_TRUE_AUTHORITY_FLAGS),
        "forbidden_true_rows": forbidden_rows,
        "canon_stage_apply_allowed_true_count": canon_stage_apply,
        "cache_read": cache_read,
        "cache_forbidden_rows": cache_forbidden_rows,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
    }


def _latest_phase3c_rollback_export(prefer_path_absent: bool = True) -> Path | None:
    candidates = sorted((WORKSPACE / "tmp").glob("sql-canon-cache-rollback-export-*.json"))
    parsed: list[tuple[str, bool, Path]] = []
    for path in candidates:
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        parsed.append((clean_text(artifact.get("generated_at_utc")), bool(artifact.get("path_absent")), path))
    if not parsed:
        return None
    if prefer_path_absent:
        absent = [item for item in parsed if item[1]]
        if absent:
            return sorted(absent, key=lambda item: item[0])[0][2]
    return sorted(parsed, key=lambda item: item[0])[-1][2]


def _rollback_script_text() -> str:
    return r'''#!/usr/bin/env python3
"""Machine-executable rollback helper for the Phase 3C canon-cache write.

Default mode is dry-run. Use --apply only after explicit main-session approval.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def remove_db_family(db_path: Path, apply: bool) -> list[str]:
    removed = []
    for suffix in ["", "-wal", "-shm"]:
        path = Path(str(db_path) + suffix)
        if path.exists():
            removed.append(str(path))
            if apply:
                path.unlink()
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback the Phase 3C canon-cache write from a rollback export JSON.")
    parser.add_argument("--export", required=True, help="Rollback export JSON path")
    parser.add_argument("--db", default=None, help="Override DB path; defaults to export db_path")
    parser.add_argument("--apply", action="store_true", help="Actually mutate/delete the DB. Default is dry-run.")
    args = parser.parse_args()
    export_path = Path(args.export)
    artifact = json.loads(export_path.read_text(encoding="utf-8"))
    db_path = Path(args.db or artifact["db_path"])
    affected = {(row["scope"], row["field_name"]) for row in artifact.get("affected_keys", [])}
    result = {
        "generated_at_utc": utc_now(),
        "mode": "apply" if args.apply else "dry_run",
        "export_path": str(export_path),
        "db_path": str(db_path),
        "path_absent_before_phase3c": bool(artifact.get("path_absent")),
        "affected_keys": sorted([f"{scope}:{field}" for scope, field in affected]),
        "rows_to_restore": len(artifact.get("prior_rows", [])),
        "db_exists_before": db_path.exists(),
    }
    if artifact.get("path_absent"):
        result["action"] = "delete_phase3c_created_db_family"
        result["removed_paths"] = remove_db_family(db_path, args.apply)
    else:
        result["action"] = "restore_prior_rows"
        if args.apply:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            for scope, field in affected:
                conn.execute("DELETE FROM canon_cache_fields WHERE scope=? AND field_name=?", (scope, field))
            for row in artifact.get("prior_rows", []):
                columns = list(row.keys())
                placeholders = ",".join("?" for _ in columns)
                conn.execute(
                    f"INSERT INTO canon_cache_fields({','.join(columns)}) VALUES ({placeholders})",
                    [row[column] for column in columns],
                )
                conn.execute(
                    """
                    INSERT INTO canon_cache_change_ledger(operation, scope, field_name, old_value, new_value, source_artifact_path,
                        source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc)
                    VALUES ('rollback_restore', ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("scope"), row.get("field_name"), row.get("field_value"), row.get("source_artifact_path"),
                        row.get("source_artifact_hash"), artifact.get("approval_artifact_path"), str(export_path),
                        artifact.get("rows_sha256"), row.get("authority_boundary"), utc_now(),
                    ),
                )
            conn.commit()
            result["integrity_check_after"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
            result["remaining_rows_after"] = conn.execute("SELECT COUNT(*) FROM canon_cache_fields").fetchone()[0]
            conn.close()
    result["db_exists_after"] = db_path.exists()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_phase3f_executable_rollback_preflight() -> dict[str, Any]:
    export_path = _latest_phase3c_rollback_export(prefer_path_absent=True)
    script_path = WORKSPACE / "scripts" / "sql_canon_cache_rollback_phase3c.py"
    compile_result = subprocess.run(["python", "-m", "py_compile", str(script_path)], cwd=WORKSPACE, text=True, capture_output=True)
    dry_run_result: dict[str, Any] = {"status": "not_run", "reason": "missing rollback export"}
    apply_sim_result: dict[str, Any] = {"status": "not_run", "reason": "missing rollback export or cache db"}
    if export_path is not None:
        dry = subprocess.run(["python", str(script_path), "--export", str(export_path)], cwd=WORKSPACE, text=True, capture_output=True)
        dry_run_result = {"returncode": dry.returncode, "stdout": dry.stdout.strip(), "stderr": dry.stderr.strip()}
        cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
        if cache_db.exists():
            with tempfile.TemporaryDirectory(prefix="phase3f-rollback-", ignore_cleanup_errors=True) as tmpdir:
                tmp_db = Path(tmpdir) / "rollback-test.sqlite"
                shutil.copy2(cache_db, tmp_db)
                apply = subprocess.run(["python", str(script_path), "--export", str(export_path), "--db", str(tmp_db), "--apply"], cwd=WORKSPACE, text=True, capture_output=True)
                apply_json = None
                try:
                    apply_json = json.loads(apply.stdout) if apply.stdout.strip() else None
                except json.JSONDecodeError:
                    apply_json = None
                apply_sim_result = {
                    "returncode": apply.returncode,
                    "stdout_json": apply_json,
                    "stderr": apply.stderr.strip(),
                    "temp_db_exists_after_apply": tmp_db.exists(),
                }
    status = "ok" if export_path is not None and compile_result.returncode == 0 and dry_run_result.get("returncode") == 0 and apply_sim_result.get("returncode") == 0 else "blocked"
    return {
        "status": status,
        "generated_at_utc": utc_now(),
        "authority_boundary": PHASE3F_PREFLIGHT_BOUNDARY,
        "script_path": rel(script_path),
        "rollback_export_path": rel(export_path) if export_path else None,
        "compile_returncode": compile_result.returncode,
        "compile_stderr": compile_result.stderr.strip(),
        "dry_run_result": dry_run_result,
        "apply_simulation_result": apply_sim_result,
        "actual_cache_db_mutated": False,
        "write_scope_expansion_allowed": False,
        "requires_explicit_apply_approval": True,
    }


def build_cross_db_stale_check(conn: sqlite3.Connection, threshold_hours: int = 24) -> dict[str, Any]:
    workspace_db = WORKSPACE / WORKSPACE_INDEX_DB
    checks: list[dict[str, Any]] = []
    artifact_rows = [dict(row) for row in conn.execute("""
        SELECT ar.source_file, ar.generated_at_utc, ar.file_mtime_utc, afs.file_sha256
        FROM artifact_runs ar
        LEFT JOIN artifact_file_state afs ON afs.source_file = ar.source_file
        ORDER BY ar.source_file
    """)]
    workspace_artifacts: dict[str, dict[str, Any]] = {}
    workspace_documents: dict[str, dict[str, Any]] = {}
    workspace_counts: dict[str, int] = {}
    if workspace_db.exists():
        with sqlite3.connect(workspace_db) as wconn:
            wconn.row_factory = sqlite3.Row
            workspace_counts = {
                "documents": wconn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
                "artifacts": wconn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
                "owners": wconn.execute("SELECT COUNT(*) FROM owners").fetchone()[0],
                "freshness": wconn.execute("SELECT COUNT(*) FROM freshness").fetchone()[0],
            }
            workspace_artifacts = {row["path"]: dict(row) for row in wconn.execute("SELECT path, mtime_utc, sha256, status FROM artifacts")}
            workspace_documents = {row["path"]: dict(row) for row in wconn.execute("SELECT path, mtime_utc, sha256, note_type FROM documents")}
    joined_rows: list[dict[str, Any]] = []
    missing_workspace_artifacts = 0
    modified_after_indexed = 0
    for row in artifact_rows:
        wa = workspace_artifacts.get(row["source_file"])
        if not wa:
            missing_workspace_artifacts += 1
            continue
        artifact_mtime = _parse_iso_utc(row.get("file_mtime_utc"))
        workspace_mtime = _parse_iso_utc(wa.get("mtime_utc"))
        is_modified_after = bool(artifact_mtime and workspace_mtime and workspace_mtime > artifact_mtime)
        if is_modified_after:
            modified_after_indexed += 1
        joined_rows.append({
            "source_file": row["source_file"],
            "artifact_index_mtime_utc": row.get("file_mtime_utc"),
            "workspace_index_mtime_utc": wa.get("mtime_utc"),
            "artifact_index_sha256": row.get("file_sha256"),
            "workspace_index_sha256": wa.get("sha256"),
            "sha256_match": clean_text(row.get("file_sha256")) == clean_text(wa.get("sha256")),
            "workspace_modified_after_artifact_index": is_modified_after,
        })
    pilot = build_phase3e_dashboard_proof_pilot(conn, limit=200)
    target_rows: list[dict[str, Any]] = []
    for row in as_list(pilot.get("dashboard_metadata_rows")):
        owner = workspace_documents.get(clean_text(row.get("owner_mirror_note_path")))
        source = workspace_artifacts.get(clean_text(row.get("source_artifact_path")))
        cache_rows, _cache_read = read_canon_cache_rows_readonly(WORKSPACE / PHASE3B_DURABLE_CACHE_DB)
        cache = next((item for item in cache_rows if f"{item.get('scope')}:{item.get('field_name')}" == row.get("key")), {})
        reconciled_at = _parse_iso_utc(cache.get("last_reconciled_at_utc"))
        owner_mtime = _parse_iso_utc(as_dict(owner).get("mtime_utc"))
        source_mtime = _parse_iso_utc(as_dict(source).get("mtime_utc"))
        source_modified_after_reconcile = bool(reconciled_at and source_mtime and source_mtime > reconciled_at)
        owner_modified_after_reconcile = bool(reconciled_at and owner_mtime and owner_mtime > reconciled_at)
        source_sha_matches_cache = bool(cache.get("source_artifact_hash") and clean_text(as_dict(source).get("sha256")) == clean_text(cache.get("source_artifact_hash")))
        # Mtime-only drift is too sharp for Phase 4 readiness: regenerated files can
        # receive a newer mtime while retaining byte-identical content. Block Phase 4
        # only when the source content hash diverges from the reconciled cache hash,
        # or when the owner mirror note changed after reconciliation.
        source_content_changed_after_reconcile = bool(source_modified_after_reconcile and not source_sha_matches_cache)
        target_rows.append({
            "key": row.get("key"),
            "source_artifact_path": row.get("source_artifact_path"),
            "owner_mirror_note_path": row.get("owner_mirror_note_path"),
            "cache_last_reconciled_at_utc": cache.get("last_reconciled_at_utc"),
            "workspace_source_mtime_utc": as_dict(source).get("mtime_utc"),
            "workspace_owner_note_mtime_utc": as_dict(owner).get("mtime_utc"),
            "source_modified_after_cache_reconcile": source_modified_after_reconcile,
            "source_sha256_matches_cache": source_sha_matches_cache,
            "source_content_changed_after_cache_reconcile": source_content_changed_after_reconcile,
            "owner_note_modified_after_cache_reconcile": owner_modified_after_reconcile,
            "blocking_stale_for_phase4": bool(source_content_changed_after_reconcile or owner_modified_after_reconcile),
        })
    blocking_target_rows = [row for row in target_rows if row.get("blocking_stale_for_phase4")]
    return {
        "status": "ok" if workspace_db.exists() and not blocking_target_rows and modified_after_indexed == 0 else "review_required",
        "generated_at_utc": utc_now(),
        "authority_boundary": PHASE3F_PREFLIGHT_BOUNDARY,
        "workspace_index_path": WORKSPACE_INDEX_DB,
        "workspace_index_exists": workspace_db.exists(),
        "workspace_counts": workspace_counts,
        "summary": {
            "artifact_index_rows": len(artifact_rows),
            "joined_workspace_artifacts": len(joined_rows),
            "missing_workspace_artifacts": missing_workspace_artifacts,
            "modified_after_indexed": modified_after_indexed,
            "target_rows": len(target_rows),
            "blocking_target_rows": len(blocking_target_rows),
            "threshold_hours": threshold_hours,
        },
        "target_field_staleness_rows": target_rows,
        "artifact_workspace_rows_sample": joined_rows[:50],
        "read_only": True,
        "consumer_migration_allowed": False,
    }


def validate_phase3f_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    guard = as_dict(preflight.get("authority_guard"))
    rollback = as_dict(preflight.get("rollback_preflight"))
    stale = as_dict(preflight.get("cross_db_stale_check"))
    add("phase3f_boundary", preflight.get("authority_boundary") == PHASE3F_PREFLIGHT_BOUNDARY)
    add("planning_not_execution", preflight.get("consumer_migration_allowed") is False and preflight.get("write_scope_expansion_allowed") is False)
    add("authority_guard_ok", guard.get("status") == "ok", as_json(guard.get("forbidden_true_rows") or []))
    add("consumer_side_guard_required", guard.get("consumer_side_required_before_non_optional_sql_reads") is True)
    add("rollback_script_compiles", rollback.get("compile_returncode") == 0, clean_text(rollback.get("compile_stderr")))
    add("rollback_dry_run_ok", as_dict(rollback.get("dry_run_result")).get("returncode") == 0)
    add("rollback_apply_simulation_ok", as_dict(rollback.get("apply_simulation_result")).get("returncode") == 0)
    add("actual_cache_not_mutated", rollback.get("actual_cache_db_mutated") is False)
    add("workspace_index_available", stale.get("workspace_index_exists") is True, stale.get("workspace_index_path"))
    add("workspace_owner_freshness_populated", as_dict(stale.get("workspace_counts")).get("owners", 0) > 0 and as_dict(stale.get("workspace_counts")).get("freshness", 0) > 0)
    add("no_phase4_target_stale_blockers", as_dict(stale.get("summary")).get("blocking_target_rows") == 0, as_json(stale.get("target_field_staleness_rows") or []))
    for key in ["canonical_note_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed", "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed"]:
        add(f"forbidden_false:{key}", preflight.get(key) is False)
    status = "ok" if all(check["ok"] for check in checks) else "blocked"
    return {
        "schema_version": PHASE3F_VALIDATION_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE3F_PREFLIGHT_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"])},
        "checks": checks,
    }


def render_phase3f_preflight_markdown(preflight: dict[str, Any], validation: dict[str, Any]) -> str:
    stale_summary = as_dict(as_dict(preflight.get("cross_db_stale_check")).get("summary"))
    lines = [
        "# SQL canon Phase 3F implementation preflight",
        "",
        f"- Generated: {preflight.get('generated_at_utc')}",
        f"- Status: {preflight.get('status')}",
        f"- Validation: {validation.get('status')} ({as_dict(validation.get('summary')).get('checks') - as_dict(validation.get('summary')).get('failed')}/{as_dict(validation.get('summary')).get('checks')})",
        f"- Boundary: `{preflight.get('authority_boundary')}`",
        "- Scope: authority guard, machine-executable rollback preflight, and cross-database stale-check only.",
        "- Stop line: no non-optional consumer migration, SQL write expansion, canon/portfolio mutation, owner approval inference, or trade/account/paper/live authority.",
        "",
        "## Results",
        "",
        f"- Authority guard: {as_dict(preflight.get('authority_guard')).get('status')}",
        f"- Rollback preflight: {as_dict(preflight.get('rollback_preflight')).get('status')} (`{as_dict(preflight.get('rollback_preflight')).get('script_path')}`)",
        f"- Cross-DB stale-check: {as_dict(preflight.get('cross_db_stale_check')).get('status')}",
        f"- Workspace owners/freshness: owners={as_dict(as_dict(preflight.get('cross_db_stale_check')).get('workspace_counts')).get('owners')}, freshness={as_dict(as_dict(preflight.get('cross_db_stale_check')).get('workspace_counts')).get('freshness')}",
        f"- Target stale blockers: {stale_summary.get('blocking_target_rows')}",
        "",
        "## Validation checks",
        "",
    ]
    for check in as_list(validation.get("checks")):
        lines.append(f"- {'ok' if check.get('ok') else 'FAIL'} | {check.get('name')} | {check.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def query_phase3f_preflight(conn: sqlite3.Connection, threshold_hours: int, output: str | None = None, md_output: str | None = None, validation_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    authority_guard = build_sql_consumer_authority_guard(conn)
    rollback_preflight = build_phase3f_executable_rollback_preflight()
    stale_check = build_cross_db_stale_check(conn, threshold_hours=threshold_hours)
    preflight = {
        "schema_version": PHASE3F_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": PHASE3F_PREFLIGHT_BOUNDARY,
        "phase4_non_optional_consumer_ready": False,
        "consumer_migration_allowed": False,
        "write_scope_expansion_allowed": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
        "authority_guard": authority_guard,
        "rollback_preflight": rollback_preflight,
        "cross_db_stale_check": stale_check,
    }
    validation = validate_phase3f_preflight(preflight)
    preflight["status"] = "ok" if validation.get("status") == "ok" else "blocked"
    preflight["phase4_non_optional_consumer_ready"] = validation.get("status") == "ok"
    output_path = WORKSPACE / (output or "tmp/sql-canon-phase3f-implementation-preflight.json")
    md_path = WORKSPACE / md_output if md_output else output_path.with_suffix(".md")
    validation_path = WORKSPACE / (validation_output or "tmp/sql-canon-phase3f-validation.json")
    write_targets = [(output_path, json.dumps(preflight, indent=2, sort_keys=True)), (validation_path, json.dumps(validation, indent=2, sort_keys=True))]
    if write_md or md_output:
        write_targets.append((md_path, render_phase3f_preflight_markdown(preflight, validation)))
    for path, content in write_targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if json_output:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} checks={validation['summary']['checks']} failed={validation['summary']['failed']} phase4_ready={preflight['phase4_non_optional_consumer_ready']} boundary={PHASE3F_PREFLIGHT_BOUNDARY}")
    outputs = [rel(output_path), rel(validation_path), str(as_dict(rollback_preflight).get('script_path'))]
    if write_md or md_output:
        outputs.insert(1, rel(md_path))
    print("wrote " + " ".join(outputs))


def build_phase4a_activation(conn: sqlite3.Connection, threshold_hours: int = 24) -> dict[str, Any]:
    """Promote exactly the approved Phase 3C cache rows into bounded SQL canon authority.

    This is a durable SQL metadata/authority transition for the first migrated
    consumer family only: dashboard proof metadata. It intentionally leaves all
    portfolio, Markdown, approval, and trade/account authority flags false.
    """
    cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
    phase3d = build_phase3d_consumer_parity(conn, limit=200)
    phase3d_validation = validate_phase3d_consumer_parity(phase3d)
    phase3e = build_phase3e_dashboard_proof_pilot(conn, limit=200)
    phase3e_validation = validate_phase3e_dashboard_proof_pilot(phase3e)
    phase3f_authority_guard = build_sql_consumer_authority_guard(conn)
    phase3f_rollback = build_phase3f_executable_rollback_preflight()
    phase3f_stale = build_cross_db_stale_check(conn, threshold_hours=threshold_hours)
    phase3f = {
        "schema_version": PHASE3F_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": PHASE3F_PREFLIGHT_BOUNDARY,
        "consumer_migration_allowed": False,
        "write_scope_expansion_allowed": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
        "authority_guard": phase3f_authority_guard,
        "rollback_preflight": phase3f_rollback,
        "cross_db_stale_check": phase3f_stale,
    }
    phase3f_validation = validate_phase3f_preflight(phase3f)
    phase3f["status"] = "ok" if phase3f_validation.get("status") == "ok" else "blocked"
    cache_rows_before, cache_read_before = read_canon_cache_rows_readonly(cache_db)
    before_by_key = {f"{row.get('scope')}:{row.get('field_name')}": row for row in cache_rows_before}
    approval_artifact = {
        "schema_version": "sql_canon_phase4a_approval_context.v1",
        "generated_at_utc": utc_now(),
        "approval_text": PHASE4A_APPROVAL_TEXT,
        "approved_candidate_keys": PHASE3C_APPROVED_CANDIDATE_KEYS,
        "approved_db_path": PHASE3B_DURABLE_CACHE_DB,
        "approved_consumer_family": "dashboard proof metadata",
        "authority_boundary": PHASE4A_SQL_CANON_BOUNDARY,
        "forbidden_scope": [
            "Markdown/canonical note mutation",
            "portfolio mutation",
            "owner approval inference",
            "trade/account/paper/live authority",
            "cash/sizing/risk-rule/sleeve/entry-band/weight fields",
            "credentials/live endpoints",
            "cron schedule changes",
            "dashboard recommendation/deployment/action-state behavior change",
        ],
    }
    approval_path = WORKSPACE / PHASE4A_APPROVAL_ARTIFACT
    approval_path.write_text(json.dumps(approval_artifact, indent=2, sort_keys=True), encoding="utf-8")
    preconditions_ok = bool(
        phase3d_validation.get("status") == "ok"
        and phase3e_validation.get("status") == "ok"
        and phase3f_validation.get("status") == "ok"
        and cache_read_before.get("exists") is True
        and set(before_by_key) == set(PHASE3C_APPROVED_CANDIDATE_KEYS)
    )
    written_rows: list[dict[str, Any]] = []
    if preconditions_ok:
        now = utc_now()
        with connect_canon_cache(cache_db) as cache_conn:
            cache_conn.execute("BEGIN IMMEDIATE")
            init_canon_cache_schema(cache_conn)
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("schema_version", "sql_canon_cache.v2"))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("authority_boundary", PHASE4A_SQL_CANON_BOUNDARY))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("sql_canon_authority", "true"))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("canon_authority_scope", "exact_migrated_fields_only:NVDA:post_earnings_review_confirmed,NVDA:earnings_lifecycle_status"))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("consumer_authority_scope", "dashboard_proof_metadata_only"))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("fallback_required", "true"))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("approval_artifact_path", PHASE4A_APPROVAL_ARTIFACT))
            cache_conn.execute("INSERT OR REPLACE INTO canon_cache_meta(key, value) VALUES (?, ?)", ("updated_at_utc", now))
            for key in PHASE3C_APPROVED_CANDIDATE_KEYS:
                scope, field_name = key.split(":", 1)
                row = cache_conn.execute("SELECT * FROM canon_cache_fields WHERE scope=? AND field_name=?", (scope, field_name)).fetchone()
                if row is None:
                    continue
                old_boundary = row["authority_boundary"]
                cache_conn.execute(
                    """
                    UPDATE canon_cache_fields
                    SET authority_boundary=?, validator_status='ok', updated_at_utc=?
                    WHERE scope=? AND field_name=?
                    """,
                    (PHASE4A_SQL_CANON_BOUNDARY, now, scope, field_name),
                )
                cache_conn.execute(
                    """
                    INSERT INTO canon_cache_change_ledger(operation, scope, field_name, old_value, new_value, source_artifact_path,
                        source_artifact_hash, approval_artifact_path, rollback_export_path, rollback_export_sha256, authority_boundary, created_at_utc)
                    VALUES ('update', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scope, field_name, old_boundary, PHASE4A_SQL_CANON_BOUNDARY,
                        row["source_artifact_path"], row["source_artifact_hash"], PHASE4A_APPROVAL_ARTIFACT,
                        "scripts/sql_canon_cache_rollback_phase3c.py", row["rollback_export_sha256"], PHASE4A_SQL_CANON_BOUNDARY, now,
                    ),
                )
                written_rows.append({"key": key, "operation": "authority_boundary_update", "old_boundary": old_boundary, "new_boundary": PHASE4A_SQL_CANON_BOUNDARY})
            cache_conn.commit()
    cache_rows_after, cache_read_after = read_canon_cache_rows_readonly(cache_db)
    return {
        "schema_version": PHASE4A_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if preconditions_ok and len(written_rows) == len(PHASE3C_APPROVED_CANDIDATE_KEYS) else "blocked",
        "authority_boundary": PHASE4A_SQL_CANON_BOUNDARY,
        "db_path": PHASE3B_DURABLE_CACHE_DB,
        "approval_artifact_path": PHASE4A_APPROVAL_ARTIFACT,
        "approved_candidate_keys": PHASE3C_APPROVED_CANDIDATE_KEYS,
        "consumer_family": "dashboard proof metadata",
        "sql_is_canon": True,
        "sql_canon_authority_scope": "explicit_migrated_fields_only",
        "fallback_required": True,
        "canonical_note_mutation_allowed": False,
        "markdown_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
        "dashboard_recommendation_deployment_action_state_behavior_change_allowed": False,
        "preconditions_ok": preconditions_ok,
        "phase3d_validation_status": phase3d_validation.get("status"),
        "phase3e_validation_status": phase3e_validation.get("status"),
        "phase3f_validation_status": phase3f_validation.get("status"),
        "cache_read_before": cache_read_before,
        "cache_read_after": cache_read_after,
        "cache_rows_before": cache_rows_before,
        "cache_rows_after": cache_rows_after,
        "written_rows": written_rows,
    }


def validate_phase4a_activation(activation: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    rows_after = as_list(activation.get("cache_rows_after"))
    keys_after = [f"{row.get('scope')}:{row.get('field_name')}" for row in rows_after]
    add("phase4a_boundary", activation.get("authority_boundary") == PHASE4A_SQL_CANON_BOUNDARY)
    add("preconditions_ok", activation.get("preconditions_ok") is True)
    add("phase3d_3e_3f_clean", activation.get("phase3d_validation_status") == "ok" and activation.get("phase3e_validation_status") == "ok" and activation.get("phase3f_validation_status") == "ok")
    add("exact_two_approved_keys_only", set(keys_after) == set(PHASE3C_APPROVED_CANDIDATE_KEYS) and len(keys_after) == len(PHASE3C_APPROVED_CANDIDATE_KEYS), ", ".join(keys_after))
    add("sql_canon_true_for_bounded_scope", activation.get("sql_is_canon") is True and activation.get("sql_canon_authority_scope") == "explicit_migrated_fields_only")
    add("dashboard_proof_metadata_consumer_only", activation.get("consumer_family") == "dashboard proof metadata")
    add("fallback_required", activation.get("fallback_required") is True)
    add("rows_promoted_to_phase4_boundary", all(row.get("authority_boundary") == PHASE4A_SQL_CANON_BOUNDARY for row in rows_after), as_json(rows_after))
    add("rows_clean_match_ok", all(row.get("reconciliation_status") == "match" and row.get("validator_status") == "ok" for row in rows_after))
    add("activation_wrote_exact_two_rows", len(as_list(activation.get("written_rows"))) == len(PHASE3C_APPROVED_CANDIDATE_KEYS))
    add("cache_readonly_after_available", as_dict(activation.get("cache_read_after")).get("read_mode") == "sqlite_ro" and as_dict(activation.get("cache_read_after")).get("integrity_check") == "ok")
    for key in ["canonical_note_mutation_allowed", "markdown_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed", "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed", "dashboard_recommendation_deployment_action_state_behavior_change_allowed"]:
        add(f"forbidden_false:{key}", activation.get(key) is False)
    status = "ok" if all(check["ok"] for check in checks) else "blocked"
    return {
        "schema_version": PHASE4A_VALIDATION_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": PHASE4A_SQL_CANON_BOUNDARY,
        "summary": {"checks": len(checks), "failed": sum(1 for check in checks if not check["ok"]), "rows_validated": len(rows_after)},
        "checks": checks,
    }


def render_phase4a_activation_markdown(activation: dict[str, Any], validation: dict[str, Any]) -> str:
    lines = [
        "# SQL canon Phase 4A dashboard proof-metadata activation",
        "",
        f"- Generated: {activation.get('generated_at_utc')}",
        f"- Status: {activation.get('status')}",
        f"- Validation: {validation.get('status')} ({as_dict(validation.get('summary')).get('checks') - as_dict(validation.get('summary')).get('failed')}/{as_dict(validation.get('summary')).get('checks')})",
        f"- Boundary: `{activation.get('authority_boundary')}`",
        "- Scope: SQL is canon authority only for exactly `NVDA:post_earnings_review_confirmed` and `NVDA:earnings_lifecycle_status` in the dashboard proof-metadata consumer.",
        "- Stop line: no Markdown/canon note mutation, no portfolio mutation, no owner-approval inference, no paper/live trade/account authority, and no recommendation/deployment/action-state behavior change.",
        "- Fallback: generated-artifact/Markdown fallback remains required for degraded SQL reads.",
        "",
        "## Activated rows",
        "",
        "| Key | Operation | Old boundary | New boundary |",
        "|---|---|---|---|",
    ]
    for row in as_list(activation.get("written_rows")):
        lines.append("| " + " | ".join(clean_text(row.get(col)) for col in ["key", "operation", "old_boundary", "new_boundary"]) + " |")
    lines.extend(["", "## Validation checks", ""])
    for check in as_list(validation.get("checks")):
        lines.append(f"- {'ok' if check.get('ok') else 'FAIL'} | {check.get('name')} | {check.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def query_phase4a_activate(conn: sqlite3.Connection, threshold_hours: int, output: str | None = None, md_output: str | None = None, validation_output: str | None = None, json_output: bool = False, write_md: bool = False) -> None:
    activation = build_phase4a_activation(conn, threshold_hours=threshold_hours)
    validation = validate_phase4a_activation(activation)
    activation["status"] = "ok" if validation.get("status") == "ok" else "blocked"
    output_path = WORKSPACE / (output or "tmp/sql-canon-phase4a-activation.json")
    md_path = WORKSPACE / md_output if md_output else output_path.with_suffix(".md")
    validation_path = WORKSPACE / (validation_output or "tmp/sql-canon-phase4a-validation.json")
    write_targets = [(output_path, json.dumps(activation, indent=2, sort_keys=True)), (validation_path, json.dumps(validation, indent=2, sort_keys=True))]
    if write_md or md_output:
        write_targets.append((md_path, render_phase4a_activation_markdown(activation, validation)))
    for path, content in write_targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if json_output:
        print(json.dumps(activation, indent=2, sort_keys=True))
        return
    print(f"status={validation['status']} rows={validation['summary']['rows_validated']} sql_is_canon={activation['sql_is_canon']} boundary={PHASE4A_SQL_CANON_BOUNDARY}")
    outputs = [rel(output_path), rel(validation_path), PHASE4A_APPROVAL_ARTIFACT]
    if write_md or md_output:
        outputs.insert(1, rel(md_path))
    print("wrote " + " ".join(outputs))


def _resolve_workspace_note(path_text: str) -> Path:
    return WORKSPACE / path_text.replace("/", "\\")


def build_note_drift_report(conn: sqlite3.Connection, limit: int = 100) -> dict[str, Any]:
    result_rows = rows(
        conn,
        """
        SELECT proposal_id, target_file, proposal_kind, requires_owner_approval,
               proposal_apply_allowed, applied, old_text_sha256, new_text_sha256,
               evidence_status, source_lineage_status, status, source_file, raw_json
        FROM canon_proposal_staging
        ORDER BY applied ASC, target_file, proposal_id
        LIMIT ?
        """,
        (limit,),
    )
    candidates: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for row in result_rows:
        raw = as_dict(json.loads(row["raw_json"] or "{}"))
        target_file = clean_text(row["target_file"])
        note_path = _resolve_workspace_note(target_file)
        note_exists = note_path.exists()
        note_text = note_path.read_text(encoding="utf-8") if note_exists else ""
        exact_old = raw.get("exact_old_text")
        proposed_new = raw.get("proposed_new_text")
        old_present = exact_old in note_text if isinstance(exact_old, str) and exact_old else None
        new_present = proposed_new in note_text if isinstance(proposed_new, str) and proposed_new else None
        if not note_exists:
            drift_status = "missing_target_note_review_needed"
        elif exact_old is None and proposed_new is None:
            drift_status = "hash_only_inspect_source_artifact"
        elif int(row["applied"] or 0):
            if new_present is True:
                drift_status = "applied_text_present"
            elif old_present is True:
                drift_status = "applied_row_but_old_text_still_present_review_needed"
            else:
                drift_status = "applied_row_text_not_found_inspect"
        else:
            if old_present is True and new_present is not True:
                drift_status = "open_candidate_old_text_present"
            elif new_present is True:
                drift_status = "candidate_text_already_present_or_manually_synced"
            elif old_present is False:
                drift_status = "source_note_changed_or_candidate_stale_review_needed"
            else:
                drift_status = "inspect_source_artifact"
        status_counts[drift_status] = status_counts.get(drift_status, 0) + 1
        candidates.append({
            "proposal_id": row["proposal_id"],
            "target_file": target_file,
            "source_file": row["source_file"],
            "proposal_kind": row["proposal_kind"],
            "requires_owner_approval": bool(row["requires_owner_approval"]),
            "proposal_apply_allowed": bool(row["proposal_apply_allowed"]),
            "applied": bool(row["applied"]),
            "note_exists": note_exists,
            "old_text_present_in_note": old_present,
            "new_text_present_in_note": new_present,
            "old_text_sha256": row["old_text_sha256"],
            "new_text_sha256": row["new_text_sha256"],
            "note_sha256": sha_text(note_text) if note_exists else None,
            "evidence_status": row["evidence_status"],
            "source_lineage_status": row["source_lineage_status"],
            "sql_stage_status": row["status"],
            "drift_status": drift_status,
            "review_needed": "review_needed" in drift_status or drift_status in {"hash_only_inspect_source_artifact", "inspect_source_artifact"},
        })
    return {
        "schema_version": "wf72.sql_to_note_drift.v1",
        "generated_at_utc": utc_now(),
        "authority": {
            "sql_is_derived_index_only": True,
            "report_is_candidate_review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "proposal_apply_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "boundary": SQL_AUTHORITY_BOUNDARY,
        "canonical_note_lookup_procedure": "06. Playbooks/Obsidian CLI Runtime Note.md#canonical-finance-note-lookup-procedure",
        "summary": {
            "candidate_count": len(candidates),
            "review_needed_count": sum(1 for row in candidates if row["review_needed"]),
            "status_counts": status_counts,
        },
        "candidates": candidates,
    }


def render_note_drift_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# WF72 SQL-to-note drift candidate report",
        "",
        f"- Generated: {report.get('generated_at_utc')}",
        f"- Boundary: `{report.get('boundary')}`",
        "- Posture: review-only candidate report; SQL is not canon, approval, or apply authority.",
        "- Required before any note sync/apply: inspect the source artifact and canonical target note.",
        "",
        "## Summary",
        "",
        f"- Candidates checked: {as_dict(report.get('summary')).get('candidate_count')}",
        f"- Review-needed candidates: {as_dict(report.get('summary')).get('review_needed_count')}",
        f"- Status counts: `{as_json(as_dict(report.get('summary')).get('status_counts') or {})}`",
        "",
        "## Candidates",
        "",
        "| Proposal | Target note | Applied | Old text present | New text present | Drift status | Source artifact |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in as_list(report.get("candidates")):
        lines.append(
            "| "
            + " | ".join(
                clean_text(value).replace("|", "\\|")
                for value in [
                    row.get("proposal_id"), row.get("target_file"), row.get("applied"),
                    row.get("old_text_present_in_note"), row.get("new_text_present_in_note"),
                    row.get("drift_status"), row.get("source_file"),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def query_note_drift(conn: sqlite3.Connection, limit: int, json_output: bool = False, output: str | None = None, md_output: str | None = None) -> None:
    report = build_note_drift_report(conn, limit=limit)
    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = WORKSPACE / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if md_output:
        md_path = Path(md_output)
        if not md_path.is_absolute():
            md_path = WORKSPACE / md_path
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_note_drift_markdown(report), encoding="utf-8")
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"status=review_only candidates={report['summary']['candidate_count']} review_needed={report['summary']['review_needed_count']} boundary={report['boundary']}")
    result_rows = [
        {"proposal_id": row.get("proposal_id"), "target_file": row.get("target_file"), "applied": row.get("applied"), "drift_status": row.get("drift_status"), "source_file": row.get("source_file")}
        for row in as_list(report.get("candidates"))
    ]
    if not result_rows:
        print("(no rows)")
        return
    columns = ["proposal_id", "target_file", "applied", "drift_status", "source_file"]
    print(" | ".join(columns))
    print(" | ".join("---" for _ in columns))
    for row in result_rows:
        print(" | ".join(clean_text(row.get(col)).replace("\n", " ")[:180] for col in columns))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and query a derived SQLite retrieval index for Veritas JSON artifacts.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path. Default: tmp/veritas-artifact-index.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rebuild", help="Rebuild the derived index from current tmp JSON artifacts.")
    sub.add_parser("incremental", help="Incrementally refresh changed/new/removed artifacts in the derived index.")
    validate = sub.add_parser("validate", help="Validate existing derived index without rebuilding it.")
    validate.add_argument("--json", action="store_true", help="Emit validation report as JSON.")
    fingerprints = sub.add_parser("fingerprints", help="Emit stable row fingerprints for full-vs-incremental drift proof.")
    fingerprints.add_argument("--json", action="store_true", help="Emit fingerprint report as JSON.")
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
    today = sub.add_parser("today", help="Show SQL-indexed Today-card decision items.")
    today.add_argument("--limit", type=int, default=20)
    validators = sub.add_parser("validators", help="Show SQL-indexed validator runs.")
    validators.add_argument("--limit", type=int, default=20)
    canon = sub.add_parser("canon", help="Show SQL-indexed canon proposal/apply staging rows.")
    canon.add_argument("--limit", type=int, default=20)
    authority = sub.add_parser("authority", help="Show any indexed true authority flags for review.")
    authority.add_argument("--limit", type=int, default=20)
    official_ir = sub.add_parser("official-ir", help="Show SQL-indexed official IR capture runs and field-status counts.")
    official_ir.add_argument("--limit", type=int, default=20)
    lineage = sub.add_parser("lineage", help="Show explicit SQL-indexed source field lineage rows.")
    lineage.add_argument("--limit", type=int, default=20)
    canon_stage = sub.add_parser("canon-stage", help="Show exact SQL-staged canon proposal rows and apply stop lines.")
    canon_stage.add_argument("--limit", type=int, default=20)
    canon_stage_readiness = sub.add_parser("canon-stage-readiness", help="Classify canon proposal staging rows as historical applied, pending review-only, incomplete review-only, or unsafe apply-ready.")
    canon_stage_readiness.add_argument("--limit", type=int, default=200)
    canon_stage_readiness.add_argument("--json", action="store_true", help="Emit readiness report as JSON.")
    canon_stage_readiness.add_argument("--output", default=None, help="Optional JSON output path.")
    canon_stage_readiness.add_argument("--md-output", default=None, help="Optional Markdown output path.")
    cockpit = sub.add_parser("cockpit", help="Show fast operating cockpit action queue.")
    cockpit.add_argument("--limit", type=int, default=20)
    ticker_cockpit = sub.add_parser("ticker-cockpit", help="Show fast ticker cockpit timeline.")
    ticker_cockpit.add_argument("ticker")
    ticker_cockpit.add_argument("--limit", type=int, default=30)
    trust_cockpit = sub.add_parser("trust-cockpit", help="Show cockpit trust/authority/freshness boundary.")
    trust_cockpit.add_argument("--limit", type=int, default=50)
    proof_field = sub.add_parser("proof-field", help="Show official-source proof for one ticker field.")
    proof_field.add_argument("ticker")
    proof_field.add_argument("field_name")
    proof_field.add_argument("--limit", type=int, default=10)
    data_coverage = sub.add_parser("data-coverage", help="Show WF77 finance data coverage registry rows.")
    data_coverage.add_argument("--ticker", default=None, help="Optional ticker coverage row.")
    data_coverage.add_argument("--family", default=None, help="Optional data family id.")
    data_coverage.add_argument("--json", action="store_true", help="Emit JSON for the selected coverage scope.")
    missing_data = sub.add_parser("missing-data", help="Show WF77 missing finance data by family or ticker.")
    missing_data.add_argument("--family", default=None, help="Optional data family id.")
    missing_data.add_argument("--ticker", default=None, help="Optional ticker.")
    missing_data.add_argument("--json", action="store_true", help="Emit JSON for the selected missing-data scope.")
    ticker_card = sub.add_parser("ticker-card", help="Show WF77 ticker-card feeder/source summary.")
    ticker_card.add_argument("ticker")
    ticker_card.add_argument("--json", action="store_true", help="Emit full ticker card JSON.")
    answer_packet = sub.add_parser("answer-packet", help="Route a ticker to the WF85 full-answer assembler with legacy compatibility/card fallback.")
    answer_packet.add_argument("ticker")
    answer_packet.add_argument("--json", action="store_true", help="Emit the full answer-packet route descriptor JSON.")
    answer_contract = sub.add_parser("answer-contract", help="Build a read-only WF77 SQL/JSON-first answer contract for a finance question.")
    answer_contract.add_argument("question", nargs="+", help="Question text to route and contract-check.")
    answer_contract.add_argument("--json", action="store_true", help="Emit JSON answer-contract wrapper.")
    answer_contract.add_argument("--output", default=None, help="Optional JSON output path.")
    validate_answer_contract = sub.add_parser("validate-answer-contract", help="Validate a read-only WF77 answer contract artifact.")
    validate_answer_contract.add_argument("--input", required=True, help="Answer contract JSON path.")
    validate_answer_contract.add_argument("--json", action="store_true", help="Emit JSON validation report.")
    stoplines = sub.add_parser("stoplines", help="Show SQL-staged canon proposal stop lines.")
    stoplines.add_argument("--limit", type=int, default=50)
    lifecycle = sub.add_parser("earnings-lifecycle", help="Show SQL-indexed earnings lifecycle closeouts/holds.")
    lifecycle.add_argument("ticker", nargs="?", default=None)
    lifecycle.add_argument("--limit", type=int, default=20)
    deployment = sub.add_parser("deployment-readiness", help="Show SQL-indexed deployment readiness rows.")
    deployment.add_argument("ticker", nargs="?", default=None)
    deployment.add_argument("--limit", type=int, default=30)
    dashboard_findings = sub.add_parser("dashboard-findings", help="Show SQL-indexed dashboard validation findings.")
    dashboard_findings.add_argument("--limit", type=int, default=30)
    source_freshness = sub.add_parser("source-freshness", help="Show SQL-indexed source freshness rows.")
    source_freshness.add_argument("--limit", type=int, default=30)
    handoff = sub.add_parser("handoff", help="Build a helper handoff locator packet from the derived SQL cockpit.")
    handoff.add_argument("--workflow", default=None, help="Optional workflow token such as WF72. SQL filters on indexed artifact/source text and falls back to latest rows if no exact token match.")
    handoff.add_argument("--limit", type=int, default=20)
    handoff.add_argument("--json", action="store_true", help="Emit the handoff packet as JSON.")
    note_drift = sub.add_parser("note-drift", help="Report SQL-routed canon/note drift candidates without applying changes.")
    note_drift.add_argument("--limit", type=int, default=100)
    note_drift.add_argument("--json", action="store_true", help="Emit the drift candidate report as JSON.")
    note_drift.add_argument("--output", default=None, help="Optional JSON output path.")
    note_drift.add_argument("--md-output", default=None, help="Optional Markdown output path.")
    reconcile = sub.add_parser("reconcile-sql-markdown", help="Generate Phase 2A SQL/Markdown reconciliation reports without applying changes.")
    reconcile.add_argument("--limit", type=int, default=200)
    reconcile.add_argument("--json", action="store_true", help="Emit reconciliation report as JSON.")
    reconcile.add_argument("--output", default=None, help="Optional JSON output path; defaults to tmp/sql-markdown-reconciliation.json.")
    reconcile.add_argument("--md-output", default=None, help="Optional Markdown output path; defaults beside the JSON output when --write-md is used.")
    reconcile.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    reconcile.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-reconciliation-validation.json.")
    reconcile.add_argument("--registry-output", default=None, help="Optional field-registry JSON path; defaults to tmp/sql-canon-field-registry.json.")
    phase3a = sub.add_parser("phase3a-dry-run", help="Generate Phase 3A SQL canon/cache architecture and dry-run promotion artifacts without writes.")
    phase3a.add_argument("--limit", type=int, default=200)
    phase3a.add_argument("--json", action="store_true", help="Emit dry-run promotion report as JSON.")
    phase3a.add_argument("--architecture-output", default=None, help="Optional architecture JSON output path; defaults to tmp/sql-canon-phase3a-architecture.json.")
    phase3a.add_argument("--architecture-md-output", default=None, help="Optional architecture Markdown output path; defaults beside the JSON output when --write-md is used.")
    phase3a.add_argument("--promotion-output", default=None, help="Optional promotion JSON output path; defaults to tmp/sql-canon-phase3a-dry-run-promotion.json.")
    phase3a.add_argument("--promotion-md-output", default=None, help="Optional promotion Markdown output path; defaults beside the JSON output when --write-md is used.")
    phase3a.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    phase3a.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-canon-phase3a-validation.json.")
    phase3b = sub.add_parser("phase3b-writepath-preflight", help="Generate Phase 3B future write-path preflight artifacts without creating a durable cache DB or writing SQL canon/cache rows.")
    phase3b.add_argument("--limit", type=int, default=200)
    phase3b.add_argument("--json", action="store_true", help="Emit preflight report as JSON.")
    phase3b.add_argument("--output", default=None, help="Optional JSON output path; defaults to tmp/sql-canon-phase3b-writepath-preflight.json.")
    phase3b.add_argument("--md-output", default=None, help="Optional Markdown output path; defaults to tmp/sql-canon-phase3b-writepath-preflight.md.")
    phase3b.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    phase3b.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-canon-phase3b-validation.json.")
    phase3c = sub.add_parser("phase3c-cache-write", help="Execute the approved one-time Phase 3C SQL structured cache write for exactly two NVDA earnings lifecycle rows.")
    phase3c.add_argument("--limit", type=int, default=200)
    phase3c.add_argument("--json", action="store_true", help="Emit write result as JSON.")
    phase3d = sub.add_parser("phase3d-consumer-parity", help="Generate read-only Phase 3D parity plan/test artifacts without migrating consumers or changing behavior.")
    phase3d.add_argument("--limit", type=int, default=200)
    phase3d.add_argument("--json", action="store_true", help="Emit consumer parity report as JSON.")
    phase3d.add_argument("--output", default=None, help="Optional JSON output path; defaults to tmp/sql-canon-phase3d-consumer-parity.json.")
    phase3d.add_argument("--md-output", default=None, help="Optional Markdown output path; defaults to tmp/sql-canon-phase3d-consumer-parity.md.")
    phase3d.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    phase3d.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-canon-phase3d-validation.json.")
    phase3e = sub.add_parser("phase3e-dashboard-proof-pilot", help="Generate a read-only Phase 3E dashboard proof-metadata pilot artifact using optional SQL cache reads with fallback.")
    phase3e.add_argument("--limit", type=int, default=200)
    phase3e.add_argument("--json", action="store_true", help="Emit dashboard proof-metadata pilot report as JSON.")
    phase3e.add_argument("--output", default=None, help="Optional JSON output path; defaults to tmp/sql-canon-phase3e-dashboard-proof-pilot.json.")
    phase3e.add_argument("--md-output", default=None, help="Optional Markdown output path; defaults to tmp/sql-canon-phase3e-dashboard-proof-pilot.md.")
    phase3e.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    phase3e.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-canon-phase3e-validation.json.")
    phase3f = sub.add_parser("phase3f-preflight", help="Run Phase 3F implementation preflight: authority guard, executable rollback proof, and cross-DB stale-check without migration or write expansion.")
    phase3f.add_argument("--threshold-hours", type=int, default=24, help="Age threshold metadata for stale-check reporting; target cache checks use exact modified-after-reconcile gates.")
    phase3f.add_argument("--json", action="store_true", help="Emit Phase 3F preflight report as JSON.")
    phase3f.add_argument("--output", default=None, help="Optional JSON output path; defaults to tmp/sql-canon-phase3f-implementation-preflight.json.")
    phase3f.add_argument("--md-output", default=None, help="Optional Markdown output path; defaults beside the JSON output when --write-md is used.")
    phase3f.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    phase3f.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-canon-phase3f-validation.json.")
    phase4a = sub.add_parser("phase4a-activate", help="Legacy mutating Phase 4A SQL canon activation path. Guarded; prefer dedicated WF72 activators.")
    phase4a.add_argument("--threshold-hours", type=int, default=24, help="Age threshold metadata for stale-check reporting; target cache checks use exact modified-after-reconcile gates.")
    phase4a.add_argument("--json", action="store_true", help="Emit Phase 4A activation report as JSON.")
    phase4a.add_argument("--output", default=None, help="Optional JSON output path; defaults to tmp/sql-canon-phase4a-activation.json.")
    phase4a.add_argument("--md-output", default=None, help="Optional Markdown output path; defaults beside the JSON output when --write-md is used.")
    phase4a.add_argument("--write-md", action="store_true", help="Also write legacy Markdown proof output; JSON remains the default proof contract.")
    phase4a.add_argument("--validation-output", default=None, help="Optional validation JSON path; defaults to tmp/sql-canon-phase4a-validation.json.")
    phase4a.add_argument("--allow-legacy-mutation", action="store_true", help="Required explicit guard for this legacy mutating command. Use only with a fresh approval packet.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = WORKSPACE / db_path
    if args.command == "rebuild":
        rebuild(db_path)
        return 0
    if args.command == "incremental":
        incremental_rebuild(db_path)
        return 0
    if not db_path.exists():
        raise FileNotFoundError(f"Index DB not found: {db_path}. Run rebuild first.")
    if args.command == "validate":
        report = validate_index(db_path)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"status={report['status']} checks={report['summary']['checks']} failed={report['summary']['failed']}")
            for check in report["checks"]:
                print(f"{'ok' if check['ok'] else 'FAIL'} | {check['name']} | {check['detail']}")
        return 0 if report["status"] == "ok" else 1
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
        elif args.command == "today":
            query_today(conn, args.limit)
        elif args.command == "validators":
            query_validators(conn, args.limit)
        elif args.command == "canon":
            query_canon(conn, args.limit)
        elif args.command == "authority":
            query_authority(conn, args.limit)
        elif args.command == "official-ir":
            query_official_ir(conn, args.limit)
        elif args.command == "lineage":
            query_lineage(conn, args.limit)
        elif args.command == "canon-stage":
            query_canon_stage(conn, args.limit)
        elif args.command == "canon-stage-readiness":
            query_canon_stage_readiness(conn, args.limit, args.json, args.output, args.md_output)
        elif args.command == "cockpit":
            query_cockpit(conn, args.limit)
        elif args.command == "ticker-cockpit":
            query_ticker_cockpit(conn, args.ticker, args.limit)
        elif args.command == "trust-cockpit":
            query_trust_cockpit(conn, args.limit)
        elif args.command == "proof-field":
            query_proof_field(conn, args.ticker, args.field_name, args.limit)
        elif args.command == "data-coverage":
            query_data_coverage(args.ticker, args.family, args.json)
        elif args.command == "missing-data":
            query_missing_data(args.family, args.ticker, args.json)
        elif args.command == "ticker-card":
            query_ticker_card(args.ticker, args.json)
        elif args.command == "answer-packet":
            query_answer_packet(args.ticker, args.json)
        elif args.command == "answer-contract":
            query_answer_contract(" ".join(args.question), args.json, args.output)
        elif args.command == "validate-answer-contract":
            return query_validate_answer_contract(args.input, args.json)
        elif args.command == "stoplines":
            query_stoplines(conn, args.limit)
        elif args.command == "earnings-lifecycle":
            query_earnings_lifecycle(conn, args.ticker, args.limit)
        elif args.command == "deployment-readiness":
            query_deployment_readiness(conn, args.ticker, args.limit)
        elif args.command == "dashboard-findings":
            query_dashboard_findings(conn, args.limit)
        elif args.command == "source-freshness":
            query_source_freshness(conn, args.limit)
        elif args.command == "fingerprints":
            query_fingerprints(conn, args.json)
        elif args.command == "handoff":
            query_handoff(conn, db_path, args.workflow, args.limit, args.json)
        elif args.command == "note-drift":
            query_note_drift(conn, args.limit, args.json, args.output, args.md_output)
        elif args.command == "reconcile-sql-markdown":
            query_sql_markdown_reconciliation(conn, args.limit, args.output, args.md_output, args.validation_output, args.registry_output, args.json, args.write_md)
        elif args.command == "phase3a-dry-run":
            query_phase3a_dry_run(conn, args.limit, args.architecture_output, args.architecture_md_output, args.promotion_output, args.promotion_md_output, args.validation_output, args.json, args.write_md)
        elif args.command == "phase3b-writepath-preflight":
            query_phase3b_writepath_preflight(conn, args.limit, args.output, args.md_output, args.validation_output, args.json, args.write_md)
        elif args.command == "phase3c-cache-write":
            execute_phase3c_cache_write(conn, args.limit, args.json)
        elif args.command == "phase3d-consumer-parity":
            query_phase3d_consumer_parity(conn, args.limit, args.output, args.md_output, args.validation_output, args.json, args.write_md)
        elif args.command == "phase3e-dashboard-proof-pilot":
            query_phase3e_dashboard_proof_pilot(conn, args.limit, args.output, args.md_output, args.validation_output, args.json, args.write_md)
        elif args.command == "phase3f-preflight":
            query_phase3f_preflight(conn, args.threshold_hours, args.output, args.md_output, args.validation_output, args.json, args.write_md)
        elif args.command == "phase4a-activate":
            if not args.allow_legacy_mutation:
                raise SystemExit(
                    "phase4a-activate is a legacy mutating SQL-canon/cache command. "
                    "Use dedicated WF72 activators, or rerun with --allow-legacy-mutation only after a fresh approval packet."
                )
            query_phase4a_activate(conn, args.threshold_hours, args.output, args.md_output, args.validation_output, args.json, args.write_md)
        else:
            raise ValueError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
