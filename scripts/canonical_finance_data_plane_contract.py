#!/usr/bin/env python3
"""Define the internal canonical finance data-plane contract.

This is the WF84 starting surface for a trade-grade personal finance OS data
model. It writes a schema/feeder/validator contract only. It does not create a
database, mutate canon notes, import tickers, approve capital, or touch
paper/live/account systems.
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

DEFAULT_OUT = TMP / "canonical-finance-data-plane-contract.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
FINANCE_STATE_DB = TMP / "finance-intelligence-state.sqlite"
TIER_WEIGHTED_FRESHNESS = TMP / "wf78-tier-weighted-freshness-resolution.json"
DECISION_SYNC_SPINE = TMP / "finance-decision-sync-spine.json"
TICKER_CARD_GATE = TMP / "finance-ticker-card-refresh-gate.json"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
FINANCE_COVERAGE = TMP / "finance-data-coverage-current.json"
TICKER_FRESHNESS_LEDGER = TMP / "wf78-ticker-freshness-ledger.json"
TIER_A_CONFIDENCE_GATE = TMP / "wf78-tier-a-confidence-gate.json"
VERITAS_CANON_CACHE = TMP / "veritas-canon-cache.sqlite"
FUNDAMENTAL_METRICS = TMP / "fundamental-metrics-current.json"
FUNDAMENTAL_IR_RECONCILIATION = TMP / "fundamental-ir-reconciliation-packets.json"
WF78_SEC_RECONCILIATION = TMP / "wf78-sec-reconciliation-scaler-current.json"
FINANCE_DECISION_FACTORY = TMP / "finance-decision-factory.json"
CAPITAL_REVIEW_QUEUE = TMP / "wf78-capital-review-queue.json"
EVENT_REROUTING = TMP / "wf78-event-triggered-rerouting.json"
TIER_C_BAND_STATUS = TMP / "tier-c-band-status.json"
PAPER_POSITIONS_PACKET = TMP / "finance-intelligence-state-paper-positions.json"

SCHEMA = "veritas.canonical_finance_data_plane_contract.v1"
WORKFLOW_ID = "WF84"
EXPECTED_ACTIVE_TICKERS = 200

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "internal_personal_finance_infrastructure": True,
    "schema_contract_only": True,
    "writes_database": False,
    "imports_or_promotes_tickers": False,
    "customer_or_public_output_allowed": False,
    "real_customer_data_allowed": False,
    "account_or_brokerage_data_required": False,
    "pii_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_FLAGS = {
    "writes_database",
    "imports_or_promotes_tickers",
    "customer_or_public_output_allowed",
    "real_customer_data_allowed",
    "account_or_brokerage_data_required",
    "pii_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "capital_deployment_allowed",
    "trade_or_execution_approved",
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


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sqlite_count(db_path: Path, table: str) -> int | None:
    if not db_path.exists():
        return None
    uri = db_path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    except sqlite3.Error:
        return None


def sqlite_integrity_check(db_path: Path) -> str | None:
    if not db_path.exists():
        return None
    uri = db_path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    except sqlite3.Error:
        return None


def source_meta(path: Path, *, required: bool, role: str, source_type: str) -> dict[str, Any]:
    payload = load_json_artifact(path) if source_type == "json" else None
    meta = {
        "path": rel(path),
        "role": role,
        "source_type": source_type,
        "required_for_mvp": required,
        "exists": path.exists(),
    }
    if path.exists():
        meta["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        meta["size_bytes"] = path.stat().st_size
    if isinstance(payload, dict):
        meta["schema"] = payload.get("schema") or payload.get("schema_version")
        meta["status"] = payload.get("status")
        meta["generated_at_utc"] = payload.get("generated_at_utc")
        validation = as_dict(payload.get("validation"))
        if validation:
            meta["validation_status"] = validation.get("status")
    if source_type == "sqlite" and path.exists():
        integrity = sqlite_integrity_check(path)
        meta["sqlite_integrity_check"] = integrity
        meta["sqlite_integrity_observed"] = integrity == "ok"
    return meta


def canonical_tables() -> list[dict[str, Any]]:
    return [
        {
            "name": "schema_run",
            "purpose": "One row per canonical data-plane build/validation run.",
            "primary_key": ["run_id"],
            "fields": [
                ["run_id", "TEXT", False, "unique run id"],
                ["schema_version", "TEXT", False, "data-plane schema version"],
                ["generated_at_utc", "TEXT", False, "run timestamp"],
                ["local_market_date", "TEXT", True, "America/Phoenix or market-date context when available"],
                ["status", "TEXT", False, "ok, warning, or blocked"],
                ["builder_version", "TEXT", True, "writer version when implemented"],
                ["authority_boundary_json", "TEXT", False, "serialized authority boundary"],
                ["validation_status", "TEXT", False, "validation summary status"],
            ],
        },
        {
            "name": "source_artifact",
            "purpose": "Provenance table for every source artifact feeding material fields.",
            "primary_key": ["artifact_id"],
            "fields": [
                ["artifact_id", "TEXT", False, "stable artifact id"],
                ["path", "TEXT", False, "workspace-relative artifact path"],
                ["role", "TEXT", False, "feeder role"],
                ["exists_on_disk", "BOOLEAN", False, "source exists at build time"],
                ["generated_at_utc", "TEXT", True, "artifact generated timestamp"],
                ["mtime_utc", "TEXT", True, "filesystem modified timestamp"],
                ["sha256", "TEXT", True, "future source hash"],
                ["schema", "TEXT", True, "artifact schema"],
                ["status", "TEXT", True, "artifact status"],
                ["validation_status", "TEXT", True, "artifact validation status"],
                ["source_rank", "INTEGER", True, "feeder priority"],
                ["raw_summary_json", "TEXT", True, "compact source summary"],
            ],
        },
        {
            "name": "security_master",
            "purpose": "One row per internal tracked security, ETF, or approved instrument.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "canonical uppercase ticker or provider symbol"],
                ["name", "TEXT", True, "security or company display name"],
                ["instrument_type", "TEXT", True, "equity, ETF, commodity proxy, bond proxy, etc."],
                ["sector", "TEXT", True, "sector context"],
                ["industry", "TEXT", True, "industry context"],
                ["yfinance_symbol", "TEXT", True, "provider symbol"],
                ["sec_cik", "TEXT", True, "SEC CIK when available"],
                ["company_ir_url", "TEXT", True, "official investor relations URL when registered"],
                ["active", "BOOLEAN", False, "active in current internal finance universe"],
            ],
        },
        {
            "name": "universe_membership",
            "purpose": "Internal universe scope and production/review-monitor membership.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["universe_scope", "TEXT", False, "production, review monitor, pilot fixture, etc."],
                ["legacy_universe_tier", "TEXT", True, "legacy tier label when present"],
                ["legacy_monitoring_role", "TEXT", True, "legacy monitoring role when present"],
                ["production_answer_path_member", "BOOLEAN", False, "member of current production answer path"],
                ["thin_monitor_row", "BOOLEAN", False, "thin-monitor row with lighter evidence expectations"],
                ["decision_grade_eligible", "BOOLEAN", False, "eligible for decision-grade review after gates"],
                ["promotion_required_before_action", "BOOLEAN", False, "true when promotion is required before actionability"],
                ["source_open_required", "BOOLEAN", False, "material finance claim requires source-open evidence"],
                ["owner_note_path", "TEXT", True, "owner note path when available"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "routing_state_current",
            "purpose": "Current non-capital WF78 Tier A/B/C routing state.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["auto_tier", "TEXT", False, "Tier A, Tier B, Tier C, or future Tier D"],
                ["auto_state", "TEXT", False, "workflow state such as A-READY, B-CANDIDATE, B-VALIDATED, C-MONITOR"],
                ["route_priority", "INTEGER", True, "routing priority if supplied"],
                ["route_reason", "TEXT", True, "route explanation"],
                ["data_confidence_rating", "TEXT", True, "confidence label"],
                ["fundamentals_confidence", "TEXT", True, "fundamental confidence label"],
                ["tier_a_confidence_status", "TEXT", True, "Tier A confidence gate state"],
                ["tier_a_confidence_promotion_effect", "TEXT", True, "confidence-gate effect"],
                ["critical_data_conflict_count", "INTEGER", True, "critical conflict count"],
                ["requires_separate_capital_or_execution_approval", "BOOLEAN", False, "always true for action"],
                ["capital_deployment_approved", "BOOLEAN", False, "must remain false"],
                ["trade_or_execution_approved", "BOOLEAN", False, "must remain false"],
                ["would_mutate_universe", "BOOLEAN", False, "must remain false for this workflow"],
                ["source_artifact_id", "TEXT", False, "source_artifact reference"],
            ],
        },
        {
            "name": "evidence_family_status",
            "purpose": "Per-ticker evidence-family freshness, missingness, and repair status.",
            "primary_key": ["ticker", "family_id"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["family_id", "TEXT", False, "evidence family id"],
                ["status", "TEXT", False, "fresh, stale, missing, blocked, resolved"],
                ["missing_count", "INTEGER", False, "missing evidence count"],
                ["stale_count", "INTEGER", False, "stale evidence count"],
                ["source_required", "BOOLEAN", False, "source required before material claim"],
                ["required_depth", "TEXT", False, "thin, research, decision, owner-card"],
                ["resolution_state", "TEXT", True, "tier-weighted resolution state"],
                ["tier_weighted_resolved", "BOOLEAN", False, "resolved under tier policy"],
                ["source_paths_json", "TEXT", True, "source artifact paths"],
            ],
        },
        {
            "name": "price_technical_current",
            "purpose": "Latest review-grade price, quote, technical, and band-position state.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["latest_known_price", "REAL", True, "latest available review-grade price"],
                ["price_source", "TEXT", True, "price source"],
                ["quote_time_utc", "TEXT", True, "quote timestamp"],
                ["market_date", "TEXT", True, "market date"],
                ["band_status", "TEXT", True, "IN_BAND, ABOVE_BAND, BELOW_BAND, BELOW_STOP, etc."],
                ["technical_status", "TEXT", True, "technical state"],
                ["technical_summary", "TEXT", True, "brief technical summary"],
                ["fresh_quote_required", "BOOLEAN", False, "true when execution/owner-card would need fresh quote"],
                ["quote_freshness_status", "TEXT", False, "fresh, stale, missing, warning"],
                ["source_artifact_id", "TEXT", False, "source_artifact reference"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "entry_stop_reference",
            "purpose": "Entry band and stop/invalidation reference state.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["entry_band_low", "REAL", True, "lower written/reference band"],
                ["entry_band_high", "REAL", True, "upper written/reference band"],
                ["stop_or_invalidation", "REAL", True, "stop or invalidation reference"],
                ["band_source", "TEXT", False, "canonical note, approved cache, or generated proposal source"],
                ["stop_source", "TEXT", True, "stop source"],
                ["freshness_status", "TEXT", False, "fresh, stale, missing, generated_review_only"],
                ["validation_status", "TEXT", False, "validation state"],
                ["owner_note_path", "TEXT", True, "owner note path when available"],
                ["source_artifact_path", "TEXT", True, "source artifact path"],
                ["source_artifact_hash", "TEXT", True, "future source hash"],
                ["source_timestamp", "TEXT", True, "source timestamp"],
                ["authority_boundary", "TEXT", False, "authority boundary for reference"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "fundamental_snapshot",
            "purpose": "Review-grade fundamental, valuation, earnings, and reconciliation state.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["period_end", "TEXT", True, "latest fundamental period end"],
                ["period_age_days", "INTEGER", True, "period age"],
                ["data_quality", "TEXT", False, "quality status"],
                ["valuation_status", "TEXT", True, "valuation status"],
                ["key_metrics_status", "TEXT", True, "key metrics status"],
                ["latest_earnings_status", "TEXT", True, "latest earnings state"],
                ["sec_reconciliation_status", "TEXT", True, "SEC reconciliation state"],
                ["sec_conflicts_json", "TEXT", True, "SEC conflicts"],
                ["company_ir_reconciliation_status", "TEXT", True, "company IR reconciliation state"],
                ["capital_allocation_quality", "TEXT", True, "capital allocation quality"],
                ["source_path", "TEXT", False, "source artifact path"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "analyst_snapshot",
            "purpose": "Analyst/consensus snapshot when source-available.",
            "primary_key": ["ticker", "provider"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["provider", "TEXT", False, "data provider"],
                ["status", "TEXT", False, "available, stale, missing, manual_review"],
                ["accessed_at_utc", "TEXT", True, "access timestamp"],
                ["consensus_rating", "TEXT", True, "consensus label"],
                ["rating_summary", "TEXT", True, "summary"],
                ["average_target", "REAL", True, "average target price"],
                ["median_target", "REAL", True, "median target price"],
                ["implied_upside_downside_pct", "REAL", True, "implied upside/downside"],
                ["confidence", "TEXT", True, "confidence label"],
                ["manual_review_required", "BOOLEAN", False, "true when source needs manual review"],
                ["source_url", "TEXT", True, "source URL"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "earnings_catalyst",
            "purpose": "Earnings and catalyst state for review routing.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["latest_earnings_status", "TEXT", True, "latest earnings state"],
                ["latest_period_end", "TEXT", True, "latest reported period"],
                ["next_earnings_date", "TEXT", True, "next earnings date"],
                ["days_to_earnings", "INTEGER", True, "days until next earnings"],
                ["earnings_date_confirmed", "BOOLEAN", False, "confirmed date flag"],
                ["post_earnings_review_confirmed", "BOOLEAN", False, "post-earnings review flag"],
                ["catalyst_status", "TEXT", True, "catalyst state"],
                ["source_path", "TEXT", False, "source artifact path"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "official_evidence",
            "purpose": "Official/source-open evidence pointers and capture state.",
            "primary_key": ["evidence_id"],
            "fields": [
                ["evidence_id", "TEXT", False, "unique evidence id"],
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["evidence_family", "TEXT", False, "evidence family"],
                ["status", "TEXT", False, "registered, proposed, missing, blocked"],
                ["source_url", "TEXT", True, "official/source URL"],
                ["source_section", "TEXT", True, "source section"],
                ["period", "TEXT", True, "evidence period"],
                ["manual_capture_required", "BOOLEAN", False, "manual capture needed"],
                ["inferred", "BOOLEAN", False, "true if inferred; must not be treated as source-open"],
                ["source_open_required", "BOOLEAN", False, "source-open requirement flag"],
                ["source_path", "TEXT", True, "source artifact path"],
                ["raw_json", "TEXT", True, "source row snapshot"],
            ],
        },
        {
            "name": "decision_queue_state",
            "purpose": "Decision-card queue state separated from authority/order state.",
            "primary_key": ["ticker"],
            "fields": [
                ["ticker", "TEXT", False, "security_master.ticker"],
                ["primary_state", "TEXT", False, "monitor, repair, owner_review_candidate, no_chase, invalidation_review"],
                ["states_json", "TEXT", True, "all observed states"],
                ["recommendation_posture_key", "TEXT", True, "recommendation posture"],
                ["actionability", "TEXT", False, "review-only actionability classification"],
                ["queue_state", "TEXT", False, "queue state"],
                ["rank_score", "REAL", True, "rank score when present"],
                ["gate_verdict", "TEXT", True, "gate verdict"],
                ["gate_vetoes_json", "TEXT", True, "gate vetoes"],
                ["owner_card_path", "TEXT", True, "owner-card path"],
                ["wf67_request_path", "TEXT", True, "WF67 request artifact path"],
                ["wf67_request_generation_status", "TEXT", True, "request generation status"],
                ["blockers_json", "TEXT", True, "blockers"],
                ["warnings_json", "TEXT", True, "warnings"],
                ["owner_action_required", "BOOLEAN", False, "true only when Randall decision is needed"],
                ["capital_deployment_approved", "BOOLEAN", False, "must remain false"],
                ["trade_or_execution_approved", "BOOLEAN", False, "must remain false"],
                ["paper_or_live_execution_allowed", "BOOLEAN", False, "must remain false"],
                ["owner_approval_inferred", "BOOLEAN", False, "must remain false"],
            ],
        },
        {
            "name": "validation_result",
            "purpose": "Detailed validation findings for future data-plane writer runs.",
            "primary_key": ["run_id", "check_name"],
            "fields": [
                ["run_id", "TEXT", False, "validation_run.run_id"],
                ["check_name", "TEXT", False, "check name"],
                ["status", "TEXT", False, "ok, warning, blocked"],
                ["severity", "TEXT", False, "info, warning, critical"],
                ["detail_json", "TEXT", True, "finding detail"],
                ["source_artifact_id", "TEXT", True, "source artifact reference"],
            ],
        },
    ]


def feeder_sources() -> list[dict[str, Any]]:
    return [
        source_meta(UNIVERSE, required=True, role="universe/security base feed", source_type="json"),
        source_meta(AUTO_ROUTER, required=True, role="primary non-capital tier/routing feed", source_type="json"),
        source_meta(FINANCE_STATE_DB, required=True, role="current-state SQL feeder", source_type="sqlite"),
        source_meta(FINANCE_COVERAGE, required=False, role="coverage/family status feed", source_type="json"),
        source_meta(TICKER_FRESHNESS_LEDGER, required=False, role="ticker freshness ledger feed", source_type="json"),
        source_meta(TIER_WEIGHTED_FRESHNESS, required=True, role="tier-weighted evidence/freshness feed", source_type="json"),
        source_meta(DECISION_SYNC_SPINE, required=False, role="decision-readiness spine feed", source_type="json"),
        source_meta(TICKER_CARD_GATE, required=True, role="ticker-card repair/staleness feed", source_type="json"),
        source_meta(TIER_A_CONFIDENCE_GATE, required=False, role="Tier A confidence/fundamentals gate feed", source_type="json"),
        source_meta(VERITAS_CANON_CACHE, required=False, role="entry/stop reference cache feed", source_type="sqlite"),
        source_meta(FUNDAMENTAL_METRICS, required=False, role="fundamental metrics feed", source_type="json"),
        source_meta(FUNDAMENTAL_IR_RECONCILIATION, required=False, role="fundamental IR reconciliation feed", source_type="json"),
        source_meta(WF78_SEC_RECONCILIATION, required=False, role="SEC reconciliation scaler feed", source_type="json"),
        source_meta(FINANCE_DECISION_FACTORY, required=False, role="finance decision factory feed", source_type="json"),
        source_meta(CAPITAL_REVIEW_QUEUE, required=False, role="non-executing owner-review queue feed", source_type="json"),
        source_meta(EVENT_REROUTING, required=False, role="event-triggered repair/reroute feed", source_type="json"),
        source_meta(TIER_C_BAND_STATUS, required=False, role="Tier C monitor-grade band status feed", source_type="json"),
        source_meta(PAPER_POSITIONS_PACKET, required=False, role="paper visibility feed; separate read-only boundary only", source_type="json"),
    ]


def build_validation(sources: list[dict[str, Any]], tables: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key in FORBIDDEN_TRUE_FLAGS:
        if AUTHORITY_BOUNDARY.get(key) is True:
            errors.append(f"authority_flag_true:{key}")
    missing_required = [item["path"] for item in sources if item["required_for_mvp"] and not item["exists"]]
    if missing_required:
        errors.append(f"missing_required_sources:{missing_required}")

    names = [table["name"] for table in tables]
    if len(names) != len(set(names)):
        errors.append("duplicate_table_names")
    for table in tables:
        field_names = [field[0] for field in table.get("fields", [])]
        if not table.get("primary_key"):
            errors.append(f"missing_primary_key:{table.get('name')}")
        if len(field_names) != len(set(field_names)):
            errors.append(f"duplicate_fields:{table.get('name')}")

    router = load_json(AUTO_ROUTER)
    summary = as_dict(router.get("summary"))
    active_count = summary.get("active_ticker_count")
    if active_count != EXPECTED_ACTIVE_TICKERS:
        errors.append(f"unexpected_router_active_count:{active_count}")
    if summary.get("capital_deployment_approved_count", 0) != 0:
        errors.append("router_capital_deployment_approved_nonzero")
    if summary.get("trade_or_execution_approved_count", 0) != 0:
        errors.append("router_trade_or_execution_approved_nonzero")

    universe_count = sqlite_count(FINANCE_STATE_DB, "universe")
    ticker_tier_count = sqlite_count(FINANCE_STATE_DB, "ticker_tier")
    if universe_count != EXPECTED_ACTIVE_TICKERS:
        errors.append(f"unexpected_finance_state_universe_count:{universe_count}")
    if ticker_tier_count != EXPECTED_ACTIVE_TICKERS:
        errors.append(f"unexpected_finance_state_ticker_tier_count:{ticker_tier_count}")

    for optional in (DECISION_SYNC_SPINE, FUNDAMENTAL_METRICS, FUNDAMENTAL_IR_RECONCILIATION, WF78_SEC_RECONCILIATION):
        if not optional.exists():
            warnings.append(f"optional_source_missing:{rel(optional)}")

    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
        "observed_counts": {
            "expected_active_tickers": EXPECTED_ACTIVE_TICKERS,
            "router_active_tickers": active_count,
            "finance_state_universe_rows": universe_count,
            "finance_state_ticker_tier_rows": ticker_tier_count,
            "canonical_table_count": len(tables),
            "feeder_source_count": len(sources),
        },
    }


def build_report() -> dict[str, Any]:
    tables = canonical_tables()
    sources = feeder_sources()
    validation = build_validation(sources, tables)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if validation["status"] == "ok" else "blocked",
        "workflow_id": WORKFLOW_ID,
        "purpose": "Internal trade-grade personal finance OS canonical data-plane contract. Review-only starter contract; no customer/account/PII/retail-launch scope.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "design_principles": [
            "WF78 remains the research/routing engine; this contract becomes the stable internal finance truth interface.",
            "JSON artifacts and exact source notes remain proof/owner surfaces until a future validated read-only writer exists.",
            "Every material decision field must carry source, freshness, and authority context.",
            "Capital deployment, execution, paper/live/account action, customer/public output, and owner approval remain separate gated decisions.",
        ],
        "mvp_tables": tables,
        "feeder_sources": sources,
        "future_artifacts": {
            "contract": rel(DEFAULT_OUT),
            "planned_read_only_packet": "tmp/canonical-finance-data-plane.json",
            "planned_sqlite_companion": "tmp/canonical-finance-data-plane.sqlite",
            "planned_validation_packet": "tmp/canonical-finance-data-plane-validation.json",
        },
        "next_phases": [
            "Build read-only packet writer from WF78 auto-router and finance-intelligence-state.",
            "Add SQLite companion only after JSON packet validator is clean.",
            "Migrate one consumer, likely finance_intelligence_state ticker answer or PM cockpit read path, behind fallback.",
            "Lifecycle-classify derived companions after consumer parity proof, not before.",
        ],
        "validation": validation,
        "stop_lines": [
            "No database writer exists in this contract.",
            "No customer, account, brokerage, suitability, tax, retirement, income, net-worth, or PII schema is authorized.",
            "No canon/portfolio/cash/risk-rule mutation, no capital approval, no paper/live/order/account action, no owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the WF84 canonical finance data-plane contract.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build_report()
    if args.write:
        atomic_write_json(args.out, report)
    print(json.dumps({
        "status": report["status"],
        "out": rel(args.out),
        "summary": report["validation"]["observed_counts"],
        "validation": report["validation"],
    }, indent=2))
    if args.validate and report["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
