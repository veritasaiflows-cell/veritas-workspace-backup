#!/usr/bin/env python3
"""Build the SQL-canon migration charter, schema authority packet, and ledger.

This is the Phase 0/1 control surface for Randall's approved SQL-primary
finance-state migration. It does not mutate the finance canon database, import
tickers, migrate consumers, archive files, or grant execution authority.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_FINANCE = ROOT / "state" / "finance"
DB_PATH = STATE_FINANCE / "finance-canon.sqlite"

PLAN_OUT = TMP / "sql-canon-migration-master-plan.json"
LEDGER_OUT = TMP / "sql-canon-migration-ledger.json"
SCHEMA_OUT = TMP / "sql-canon-schema-authority-packet.json"

SCHEMA_VERSION = "sql_canon_migration_master_plan.v1"

APPROVAL_REFERENCE = {
    "source": "telegram",
    "message_id": "3336",
    "timestamp_mst": "2026-06-16 11:24:44",
    "summary": (
        "Randall approved making SQL canon/trustworthy finance state and "
        "migrating all consumers to SQL, with Veritas recommending cadence "
        "and proceeding phase-by-phase until fully implemented or blocked by "
        "a real decision."
    ),
}

AUTHORITY_BOUNDARY = {
    "standing_local_sql_canon_migration_approved": True,
    "sql_primary_internal_finance_state_target": True,
    "consumer_migration_planning_allowed": True,
    "consumer_migration_patch_allowed_after_inventory_and_parity": True,
    "sql_schema_and_loader_planning_allowed": True,
    "sql_db_row_mutation_performed_by_this_script": False,
    "consumer_file_mutation_performed_by_this_script": False,
    "ticker_import_performed_by_this_script": False,
    "legacy_archive_move_performed_by_this_script": False,
    "legacy_delete_allowed_by_this_script": False,
    "portfolio_or_canon_markdown_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "real_customer_data_or_external_delivery_allowed": False,
    "credential_config_channel_mutation_allowed": False,
    "owner_approval_inferred_for_capital_or_execution": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def artifact_state(path: Path) -> dict[str, Any]:
    payload = load_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "validation_status": (payload.get("validation") or {}).get("status") if isinstance(payload.get("validation"), dict) else None,
    }


def artifact_status(path: Path) -> str | None:
    payload = load_json(path, {})
    return payload.get("status") if isinstance(payload, dict) else None


def db_probe(path: Path = DB_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False, "status": "missing"}
    result: dict[str, Any] = {"path": rel(path), "exists": True}
    try:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            table_rows = conn.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name"
            ).fetchall()
            tables = [row[0] for row in table_rows if row[1] == "table"]
            views = [row[0] for row in table_rows if row[1] == "view"]
            counts: dict[str, int | str] = {}
            for table in tables:
                try:
                    counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                except sqlite3.Error as exc:
                    counts[table] = f"error:{exc}"
            result.update(
                {
                    "status": "ok" if integrity == "ok" else "warning",
                    "integrity_check": integrity,
                    "journal_mode": journal_mode,
                    "foreign_keys_on_this_connection": bool(foreign_keys),
                    "table_count": len(tables),
                    "view_count": len(views),
                    "tables": tables,
                    "views": views,
                    "row_counts": counts,
                }
            )
        finally:
            conn.close()
    except sqlite3.Error as exc:
        result.update({"status": "error", "error": str(exc)})
    return result


def build_schema_packet(generated_at: str) -> dict[str, Any]:
    field_families = [
        {
            "family": "identity_reference",
            "examples": ["ticker", "name", "instrument_type", "sector", "industry", "cik", "ir_url"],
            "authority_class": "machine_canon_candidate",
            "consumer_priority": "early",
            "write_gate": "source_lineage_and_universe_validation",
            "allowed_consumers": ["routing", "dashboards", "WF75 internal fixtures", "answer packet metadata"],
            "forbidden_semantics": ["approval", "trade", "order", "customer identity"],
        },
        {
            "family": "tier_routing_state",
            "examples": ["tier", "auto_state", "routing_bucket", "repair_lane", "freshness_sla"],
            "authority_class": "derived_non_capital_routing",
            "consumer_priority": "early",
            "write_gate": "WF78 router validators and movement ledger",
            "allowed_consumers": ["WF78", "WF77", "PM cockpit", "cron freshness"],
            "forbidden_semantics": ["capital approval", "execution approval", "portfolio mutation"],
        },
        {
            "family": "reference_levels",
            "examples": [
                "reference_price_low",
                "reference_price_high",
                "reference_invalidation_level",
                "reference_level_source_timestamp",
                "reference_level_source_sha256",
                "reference_level_owner_source_path",
            ],
            "authority_class": "approved_reference_metadata_with_owner_fallback",
            "consumer_priority": "early_after_parity",
            "write_gate": "exact field-family approval, source hash, fallback equality, rollback",
            "allowed_consumers": ["internal answer packets", "dashboards", "WF75 anonymous fixtures"],
            "forbidden_semantics": ["buy/sell/add/trim", "deployment entitlement", "order terms"],
        },
        {
            "family": "evidence_freshness",
            "examples": ["quote_freshness", "fundamentals_freshness", "earnings_freshness", "source_confidence"],
            "authority_class": "machine_control_state",
            "consumer_priority": "early",
            "write_gate": "source-specific validators",
            "allowed_consumers": ["cron", "answer routers", "WF75 internal QA", "PM cockpit"],
            "forbidden_semantics": ["owner approval", "capital readiness by itself"],
        },
        {
            "family": "proposal_and_owner_review",
            "examples": ["proposal_id", "preview_hash", "owner_review_required", "blocked_reason"],
            "authority_class": "proposal_only",
            "consumer_priority": "middle",
            "write_gate": "proposal validators and explicit not-applied flags",
            "allowed_consumers": ["PM cockpit", "operator packets", "review dashboards"],
            "forbidden_semantics": ["applied canon", "capital approval", "execution approval"],
        },
        {
            "family": "capital_execution_account",
            "examples": ["order", "trade", "paper/live execution", "brokerage account", "money movement"],
            "authority_class": "never_sql_canon_for_approval",
            "consumer_priority": "blocked",
            "write_gate": "WF67/WF63 paper-only guard or separate live-action approval; never inferred from SQL",
            "allowed_consumers": ["redacted status display only when separately gated"],
            "forbidden_semantics": ["autonomous execution", "owner approval inference"],
        },
    ]

    tables = [
        {
            "table": "finance_state_meta",
            "purpose": "database metadata, schema version, migration phase, approval reference",
            "write_owner": "migration loader",
            "consumer_mode": "read-only",
        },
        {
            "table": "securities",
            "purpose": "identity/reference metadata per ticker",
            "write_owner": "universe/source loader",
            "consumer_mode": "SQL-primary after parity",
        },
        {
            "table": "universe_membership",
            "purpose": "active universe, production/current/review monitor scope, tier membership",
            "write_owner": "WF78 universe loader",
            "consumer_mode": "SQL-primary after production-42 no-regression",
        },
        {
            "table": "tier_routing_state",
            "purpose": "derived non-capital routing state from WF78",
            "write_owner": "WF78 routing loader",
            "consumer_mode": "SQL-primary after WF78 parity",
        },
        {
            "table": "source_lineage",
            "purpose": "source artifact path/hash/timestamp/source confidence for every effective field",
            "write_owner": "all loaders",
            "consumer_mode": "required join for material claims",
        },
        {
            "table": "reference_levels",
            "purpose": "neutral entry/stop reference metadata with owner fallback lineage",
            "write_owner": "approved reference-level loader",
            "consumer_mode": "guarded SQL-primary with fallback equality",
        },
        {
            "table": "evidence_freshness",
            "purpose": "quote/fundamental/technical/earnings/source freshness state",
            "write_owner": "freshness loaders",
            "consumer_mode": "SQL-primary after freshness parity",
        },
        {
            "table": "consumer_migration_registry",
            "purpose": "consumer owner, mode, cutover state, fallback path, parity status",
            "write_owner": "migration inventory",
            "consumer_mode": "control plane",
        },
        {
            "table": "authority_events",
            "purpose": "approval references, scoped decisions, denied gates, rollback triggers",
            "write_owner": "migration controller",
            "consumer_mode": "audit only",
        },
        {
            "table": "migration_validation_runs",
            "purpose": "validator command/status/log artifact history",
            "write_owner": "migration validators",
            "consumer_mode": "audit/control",
        },
    ]

    return {
        "schema_version": "sql_canon_schema_authority_packet.v1",
        "generated_at_utc": generated_at,
        "status": "ready_for_phase1_schema_review",
        "approval_reference": APPROVAL_REFERENCE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "target_database": rel(DB_PATH),
        "sqlite_requirements": {
            "wal_required": True,
            "busy_timeout_ms": 5000,
            "foreign_keys_on_every_connection": True,
            "write_pattern": "single-writer loader scripts only; consumers read through typed access layer",
            "backup_pattern": "sqlite backup or VACUUM INTO plus WAL/shm awareness before cutover",
        },
        "field_families": field_families,
        "target_tables": tables,
        "consumer_access_contract": {
            "raw_sql_in_consumers_allowed": False,
            "typed_access_layer_required": True,
            "fail_closed_on_stale_or_authority_mismatch": True,
            "fallback_retained_until_shadow_soak_complete": True,
            "material_finance_claim_requires_source_open_or_source_lineage": True,
        },
        "stop_lines": [
            "No capital deployment, order execution, paper/live action, brokerage/account action, or money movement.",
            "No real customer data, external delivery, public launch, credential/config/channel mutation, or legal/compliance readiness claim.",
            "No legacy delete; archive-only requires a later exact manifest and reference scan.",
            "No production answer-path expansion until 42-card A/B parity is clean and a cutover packet says so.",
        ],
    }


def build_plan(generated_at: str, schema_packet: dict[str, Any]) -> dict[str, Any]:
    source_artifacts = {
        "finance_canon_db": db_probe(),
        "completion_audit": artifact_state(TMP / "sql-canon-completion-audit.json"),
        "consumer_registry_guard": artifact_state(TMP / "sql-canon-consumer-registry-guard.json"),
        "answer_path_ab_harness": artifact_state(TMP / "sql-canon-answer-path-ab-harness.json"),
        "rollback_rehearsal": artifact_state(TMP / "sql-canon-rollback-rehearsal.json"),
        "wf78_routing_parity": artifact_state(TMP / "sql-canon-wf78-routing-parity.json"),
        "sql_source_truth_promotion_readiness": artifact_state(TMP / "sql-source-truth-promotion-readiness-gate.json"),
        "sql_pre_phase5_hardening": artifact_state(TMP / "sql-pre-phase5-hardening-gate.json"),
        "retail_grade_readiness": artifact_state(TMP / "sql-canon-retail-grade-readiness.json"),
        "universe": artifact_state(ROOT / "data" / "finance" / "universe-v1.json"),
        "sql_source_truth_exact_apply_packet": artifact_state(TMP / "sql-source-truth-exact-apply-packet.json"),
        "sql_first_consumer_wiring_preflight": artifact_state(TMP / "sql-first-consumer-wiring-preflight.json"),
        "wf78_auto_tier_routing": artifact_state(TMP / "wf78-auto-tier-routing.json"),
        "wf78_tier_weighted_freshness_resolution": artifact_state(TMP / "wf78-tier-weighted-freshness-resolution.json"),
        "wf75_operator_console": artifact_state(TMP / "wf75-operator-console.json"),
        "sql_coverage_guard": artifact_state(TMP / "sql-coverage-guard.json"),
    }

    completion_payload = load_json(TMP / "sql-canon-completion-audit.json", {})
    completion_summary = completion_payload.get("summary", {}) if isinstance(completion_payload, dict) else {}
    internal_complete = (
        completion_payload.get("status") == "complete"
        and int(completion_summary.get("not_proven_count") or 0) == 0
    )
    registry_ok = artifact_status(TMP / "sql-canon-consumer-registry-guard.json") == "ok"
    answer_ab_ok = artifact_status(TMP / "sql-canon-answer-path-ab-harness.json") == "ok"
    rollback_ok = artifact_status(TMP / "sql-canon-rollback-rehearsal.json") == "ok"
    wf78_parity_ok = artifact_status(TMP / "sql-canon-wf78-routing-parity.json") == "ok"
    promotion_status = artifact_status(TMP / "sql-source-truth-promotion-readiness-gate.json")
    pre_phase5_status = artifact_status(TMP / "sql-pre-phase5-hardening-gate.json")
    retail_status = artifact_status(TMP / "sql-canon-retail-grade-readiness.json")
    core_proven = internal_complete and registry_ok and answer_ab_ok and rollback_ok

    phases = [
        {
            "phase": 0,
            "name": "charter_and_lane_control",
            "status": "complete" if internal_complete else "in_progress",
            "acceptance": ["lane leased", "charter artifact written", "hard stop lines encoded"],
        },
        {
            "phase": 1,
            "name": "schema_authority_and_consumer_inventory",
            "status": "complete" if registry_ok else "in_progress",
            "acceptance": ["schema packet ready", "consumer inventory ready", "migration backlog ready"],
        },
        {
            "phase": 2,
            "name": "backfill_shadow_sql_state",
            "status": "complete" if internal_complete else "pending",
            "acceptance": ["row counts match sources", "source lineage complete", "no proposals marked applied"],
        },
        {
            "phase": 3,
            "name": "parity_and_rollback_harness",
            "status": "complete" if answer_ab_ok and rollback_ok and wf78_parity_ok else "pending",
            "acceptance": ["42-card A/B clean", "WF78 routing parity clean", "rollback rehearsed"],
        },
        {
            "phase": 4,
            "name": "typed_access_layer_and_low_risk_consumers",
            "status": "complete" if core_proven else "pending",
            "acceptance": ["typed helper live", "no raw SQL consumers", "fail-closed guard tested"],
        },
        {
            "phase": 5,
            "name": "WF78_WF77_finance_consumers",
            "status": "complete" if wf78_parity_ok and core_proven else "pending",
            "acceptance": ["WF78 SQL-primary routing", "WF77 bridge parity", "ticker answer parity"],
        },
        {
            "phase": 6,
            "name": "WF75_productization_consumers",
            "status": "blocked_retail_grade" if retail_status == "blocked_for_sql_first_retail_grade" else ("complete" if core_proven else "pending"),
            "acceptance": ["anonymous fixtures pass", "no-leak validators pass", "operator console SQL-backed"],
        },
        {
            "phase": 7,
            "name": "cron_pm_cockpit_governance_cutover",
            "status": "complete" if core_proven else "pending",
            "acceptance": ["cron packets OK", "PM packet OK", "cockpit source registry OK"],
        },
        {
            "phase": 8,
            "name": "shadow_soak_and_production_answer_cutover",
            "status": "active_internal_primary_soak" if core_proven else "pending",
            "acceptance": ["3-5 business-day soak", "0 critical drift", "fallback retained"],
        },
        {
            "phase": 9,
            "name": "legacy_archive_retirement",
            "status": "pending",
            "acceptance": ["reference scan clean", "archive manifest hashes", "post-archive validators pass"],
        },
    ]

    parallel_lanes = [
        {"lane": "schema-loader", "phase": "1-2", "owner": "main/helper", "writes": ["schema packet", "loader proposal"], "can_parallelize": True},
        {"lane": "consumer-inventory", "phase": "1", "owner": "main/helper", "writes": ["inventory", "backlog"], "can_parallelize": True},
        {"lane": "parity-qa", "phase": "3", "owner": "helper", "writes": ["A/B reports", "rollback proof"], "can_parallelize": True},
        {"lane": "low-risk-consumers", "phase": "4", "owner": "helper", "writes": ["typed helper and first consumer patches"], "can_parallelize": True},
        {"lane": "WF78-WF77-consumers", "phase": "5", "owner": "helper", "writes": ["finance consumer patches"], "can_parallelize": True},
        {"lane": "WF75-consumers", "phase": "6", "owner": "helper", "writes": ["operator/service-state SQL reads"], "can_parallelize": True},
        {"lane": "governance-cutover", "phase": "7", "owner": "helper", "writes": ["cron/PM/cockpit patch proposals"], "can_parallelize": True},
    ]

    blockers = []
    if source_artifacts["finance_canon_db"].get("status") not in {"ok", "warning"}:
        blockers.append("finance_canon_db_not_ready_for_shadow_backfill")
    if not registry_ok:
        blockers.append("consumer_registry_guard_not_clean")

    promotion_blockers: list[str] = []
    if promotion_status and promotion_status not in {"ready_for_phase5_field_family_decision_packet"}:
        promotion_blockers.append(f"sql_source_truth_promotion:{promotion_status}")
    if pre_phase5_status and pre_phase5_status not in {"ok", "ready_for_phase5_design_only"}:
        promotion_blockers.append(f"pre_phase5_hardening:{pre_phase5_status}")
    external_activation_blockers: list[str] = []
    if retail_status == "blocked_for_sql_first_retail_grade":
        external_activation_blockers.append("retail_grade_sql_first_blocked")
    status = "internal_sql_canon_primary_guarded" if core_proven and not blockers else (
        "phase0_1_ready" if not blockers else "phase0_1_ready_with_blockers"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "status": status,
        "approval_reference": APPROVAL_REFERENCE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "target_end_state": {
            "sql_primary_internal_finance_state": True,
            "markdown_human_judgment_and_owner_authority_layer": True,
            "json_proof_and_rebuildable_packet_layer": True,
            "typed_sql_access_layer_required": True,
            "all_consumers_migrated_or_classified_source_or_archived": True,
        },
        "source_artifacts": source_artifacts,
        "schema_packet": {"path": rel(SCHEMA_OUT), "status": schema_packet.get("status")},
        "phases": phases,
        "parallel_lanes": parallel_lanes,
        "cadence": {
            "phase0_1": "same day",
            "phase2_3": "2-3 days shadow/backfill/parity",
            "phase4_7": "5-10 operating days consumer cutover",
            "phase8": "3-5 business days shadow soak",
            "phase9": "archive only after clean reference scan",
        },
        "current_blockers": blockers,
        "broader_promotion_blockers": promotion_blockers,
        "external_activation_blockers": external_activation_blockers,
        "next_action": (
            "Internal SQL-canon migration is primary and guard-clean. Continue broad closeout, keep retail/customer "
            "SQL-first activation blocked, and retire/archive duplicate legacy surfaces only through a separate "
            "reference-scan and archive manifest."
            if core_proven
            else "Run sql_canon_consumer_inventory.py, then use the inventory/backlog to split parallel implementation lanes."
        ),
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": blockers,
        },
    }


def build_ledger(generated_at: str, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "sql_canon_migration_ledger.v1",
        "generated_at_utc": generated_at,
        "status": "open",
        "approval_reference": APPROVAL_REFERENCE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "phase_status": [
            {
                "phase": row["phase"],
                "name": row["name"],
                "status": row["status"],
                "acceptance": row["acceptance"],
                "completed_at_utc": generated_at if row["status"] == "complete" else None,
            }
            for row in plan["phases"]
        ],
        "open_lanes": [
            {
                "lane": lane["lane"],
                "phase": lane["phase"],
                "status": "not_started",
                "can_parallelize": lane["can_parallelize"],
            }
            for lane in plan["parallel_lanes"]
        ],
        "proof_artifacts": {
            "master_plan": rel(PLAN_OUT),
            "schema_authority_packet": rel(SCHEMA_OUT),
            "consumer_inventory": "tmp/sql-canon-consumer-inventory.json",
            "consumer_backlog": "tmp/sql-canon-consumer-migration-backlog.json",
        },
        "stop_lines": plan.get("schema_packet", {}),
        "next_action": plan["next_action"],
    }


def run(write: bool) -> dict[str, Any]:
    generated_at = utc_now()
    schema_packet = build_schema_packet(generated_at)
    plan = build_plan(generated_at, schema_packet)
    ledger = build_ledger(generated_at, plan)
    if write:
        write_json(SCHEMA_OUT, schema_packet)
        write_json(PLAN_OUT, plan)
        write_json(LEDGER_OUT, ledger)
    return {
        "schema_version": "sql_canon_migration_master_plan_run.v1",
        "generated_at_utc": generated_at,
        "status": plan["status"],
        "written": [rel(SCHEMA_OUT), rel(PLAN_OUT), rel(LEDGER_OUT)] if write else [],
        "plan": plan,
        "ledger": ledger,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    payload = run(write=args.write)
    if args.validate and payload["plan"]["validation"]["errors"]:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
