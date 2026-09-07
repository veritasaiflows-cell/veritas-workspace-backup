#!/usr/bin/env python3
"""Build the legacy-42 lifecycle gate packet.

This packet is a planning and readiness surface only. It inventories the
legacy-42 compatibility answer-packet surface, ties it to the SQL-canon/WF85
front-door proof, and names the separate archive/delete lifecycle gates that
must clear before any move/delete/apply action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "legacy-42-lifecycle-gate-packet.json"

SCHEMA = "veritas.legacy_42_lifecycle_gate_packet.v1"

SQL_CANON_PLAN = ROOT / "06. Playbooks" / "Project Continuity" / "SQL Canon Full Migration Execution Plan - 2026-06-19.md"
RETAIL_TRUTH_PLAN = ROOT / "06. Playbooks" / "Project Continuity" / "Retail-Grade Truth Routing System.md"
TRADE_GRADE_OS_PLAN = ROOT / "06. Playbooks" / "Project Continuity" / "Veritas OS V2 - Trade-Grade Autonomous OS Upgrade Plan.md"

FRONT_DOOR_READINESS = TMP / "sql-canon-front-door-readiness-packet.json"
CONSUMER_INVENTORY = TMP / "sql-canon-consumer-inventory.json"
TICKER_PACKET_RETIREMENT = TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json"
RETIREMENT_READINESS = TMP / "canonical-finance-data-plane-retirement-readiness.json"
NO_RUNTIME_IMPORTS_GUARD = TMP / "legacy-42-no-runtime-imports-guard.json"
DB_LIFECYCLE = TMP / "db-lifecycle-manifest.json"
OWNER_DECISION = TMP / "sql-canon-owner-decision-packet.json"
WF78_ROUTING = TMP / "wf78-auto-tier-routing.json"
TRADE_GRADE_OS = TMP / "trade-grade-os-freshness-cron-runner.json"
TIER_AB_BAND_GUARD = TMP / "tier-ab-band-freshness-cron-guard.json"
WF87_COMMAND = TMP / "wf87-autonomy-command-center.json"
CRON_REDUCTION = TMP / "cron-reduction-inventory.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
RETAIL_CUSTOMER_DECISION = TMP / "retail-customer-output-decision-packet.json"
RETAIL_CONTROL = TMP / "retail-automation-control-plane.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "planning_packet_only": True,
    "consumer_inventory_only": True,
    "archive_allowed_now": False,
    "delete_allowed_now": False,
    "move_allowed_now": False,
    "apply_allowed_now": False,
    "patch_apply_allowed_now": False,
    "sql_write_allowed": False,
    "sql_first_front_door_promotion_allowed": False,
    "source_feeder_retirement_allowed": False,
    "python_fallback_retirement_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return as_dict(payload)


def p0_consumers(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in as_list(inventory.get("consumers")):
        item = as_dict(row)
        if item.get("priority") != "P0":
            continue
        rows.append(
            {
                "path": item.get("path"),
                "consumer_type": item.get("consumer_type"),
                "migration_action": item.get("migration_action"),
                "raw_sql_classification": item.get("raw_sql_classification"),
                "fallback_required": True,
                "cutover_requires_parity": True,
            }
        )
    return rows


def docs_alignment() -> dict[str, Any]:
    return {
        "sql_canon_full_migration_execution_plan": {
            "path": rel(SQL_CANON_PLAN),
            "exists": SQL_CANON_PLAN.exists(),
            "alignment": "legacy 42 remains compatibility-only; SQL-canon/WF84/WF85 proof owns routing readiness; destructive actions are Phase 8 hard-stop packets.",
        },
        "retail_grade_truth_routing_system": {
            "path": rel(RETAIL_TRUTH_PLAN),
            "exists": RETAIL_TRUTH_PLAN.exists(),
            "alignment": "internal retail truth routing may consume guarded truth surfaces, but customer/public output remains blocked.",
        },
        "trade_grade_autonomous_os_upgrade_plan": {
            "path": rel(TRADE_GRADE_OS_PLAN),
            "exists": TRADE_GRADE_OS_PLAN.exists(),
            "alignment": "WF87/Trade-Grade Autonomous OS preparation remains proof and assisted-readiness only; no paper/live execution authority.",
        },
    }


def build_packet() -> dict[str, Any]:
    front = read_json(FRONT_DOOR_READINESS)
    front_proof = as_dict(front.get("proof_summary"))
    inventory = read_json(CONSUMER_INVENTORY)
    inventory_summary = as_dict(inventory.get("summary"))
    ticker_plan = read_json(TICKER_PACKET_RETIREMENT)
    ticker_summary = as_dict(ticker_plan.get("summary"))
    retirement = read_json(RETIREMENT_READINESS)
    retirement_summary = as_dict(retirement.get("summary"))
    no_runtime_guard = read_json(NO_RUNTIME_IMPORTS_GUARD)
    no_runtime_summary = as_dict(no_runtime_guard.get("summary"))
    db_lifecycle = read_json(DB_LIFECYCLE)
    db_summary = as_dict(db_lifecycle.get("summary"))
    owner = read_json(OWNER_DECISION)
    wf78 = read_json(WF78_ROUTING)
    wf78_summary = as_dict(wf78.get("summary"))
    trade_grade = read_json(TRADE_GRADE_OS)
    trade_grade_summary = as_dict(trade_grade.get("summary"))
    tier_ab_band_guard = read_json(TIER_AB_BAND_GUARD)
    tier_ab_band_summary = as_dict(tier_ab_band_guard.get("summary"))
    tier_ab_band_validation = as_dict(tier_ab_band_guard.get("validation"))
    wf87 = read_json(WF87_COMMAND)
    wf87_summary = as_dict(wf87.get("summary"))
    cron_reduction = read_json(CRON_REDUCTION)
    cron_reduction_summary = as_dict(cron_reduction.get("summary"))
    cron_control = read_json(CRON_CONTROL)
    cron_control_summary = as_dict(cron_control.get("summary"))
    retail_customer = read_json(RETAIL_CUSTOMER_DECISION)
    retail_control = read_json(RETAIL_CONTROL)

    reference_inventory = [
        as_dict(row)
        for row in as_list(ticker_plan.get("reference_inventory"))
    ]
    active_references = [
        as_dict(row)
        for row in reference_inventory
        if as_dict(row).get("blocking") is True
    ]
    exact_archive_candidates = [
        str(path)
        for path in as_list(ticker_plan.get("exact_archive_candidates"))
        if isinstance(path, str)
    ]
    legacy_packet_count = int(ticker_summary.get("legacy_packet_count") or 0)
    archived_packet_count = int(ticker_summary.get("legacy_packets_archived_count") or 0)
    archive_completed = (
        ticker_plan.get("status") == "archived"
        and ticker_summary.get("archive_completed") is True
        and legacy_packet_count > 0
        and archived_packet_count == legacy_packet_count
        and int(ticker_summary.get("active_reference_count") or 0) == 0
    )

    front_scope = as_dict(front.get("scope"))
    front_contract = as_dict(front.get("readiness_contract"))
    strategic_evaluated_count = int(front_proof.get("strategic_front_door_evaluated_count") or 0)
    strategic_wf85_count = int(front_proof.get("strategic_front_door_wf85_default_count") or 0)
    front_route_aligned = (
        front.get("status")
        in {
            "readiness_green_promotion_still_owner_gated",
            "readiness_waiting_no_validated_production_scope",
            "readiness_waiting_source_open_guard_retained",
        }
        and as_dict(front.get("validation")).get("status") == "ok"
        and int(front_proof.get("front_door_hard_blocked_count") or 0) == 0
        and front_scope.get("legacy_42_retired_from_blocking") is True
        and front_contract.get("legacy_42_count_advisory_only") is True
        and (strategic_evaluated_count == 0 or strategic_wf85_count == strategic_evaluated_count)
    )
    archive_planning_ready = (
        ticker_plan.get("status") in {"planning_ready", "archived"}
        and ticker_summary.get("archive_ready_now") is True
        and int(ticker_summary.get("active_reference_count") or 0) == 0
        and int(ticker_summary.get("legacy_packets_archived_count") or 0) == 0
        and len(exact_archive_candidates) == int(ticker_summary.get("legacy_packet_count") or 0)
        and len(exact_archive_candidates) > 0
    ) or archive_completed

    runtime_blocker_count = int(no_runtime_summary.get("active_runtime_blocker_count") or 0)
    no_runtime_guard_clean = no_runtime_guard.get("status") == "ready_for_archive_packet_prep" and runtime_blocker_count == 0

    status = "planning_ready_apply_blocked"
    if runtime_blocker_count > 0:
        status = "planning_ready_runtime_cutover_required"
    if not front_route_aligned or not archive_planning_ready:
        status = "blocked_pending_route_or_inventory_proof"

    lifecycle_gates = [
        {
            "gate": "legacy_42_no_runtime_imports_guard",
            "status": "complete" if no_runtime_guard_clean else "runtime_cutover_required",
            "proof_artifact": rel(NO_RUNTIME_IMPORTS_GUARD),
            "current_value": {
                "guard_status": no_runtime_guard.get("status"),
                "active_runtime_blocker_count": runtime_blocker_count,
                "archive_candidate_script_count": no_runtime_summary.get("archive_candidate_script_count"),
                "archive_or_delete_allowed_now": False,
            },
            "acceptance": "Active runtime import/call blockers must be zero before Legacy 42 scripts can be placed in an owner archive-approval packet.",
        },
        {
            "gate": "exact_consumer_inventory",
            "status": "complete",
            "proof_artifact": rel(CONSUMER_INVENTORY),
            "current_value": {
                "consumer_count": inventory_summary.get("consumer_count"),
                "backlog_count": inventory_summary.get("backlog_count"),
                "p0_answer_path_consumer_count": len(p0_consumers(inventory)),
                "raw_sql_review_count": inventory_summary.get("raw_sql_review_count"),
            },
            "acceptance": "Inventory is current, P0 consumers are named, raw-SQL actionable review is zero, and active ticker-packet readers are classified.",
        },
        {
            "gate": "patch_diff_packet",
            "status": "not_started_hard_stop",
            "proof_artifact": None,
            "current_value": {
                "patch_diff_ready": False,
                "apply_allowed_now": False,
            },
            "acceptance": "Separate packet must name every source/destination, code reference patch, side effect, and exact command diff before archive/delete.",
        },
        {
            "gate": "rollback_proof",
            "status": "not_started_hard_stop",
            "proof_artifact": None,
            "current_value": {
                "rollback_proof_ready": False,
                "proposed_archive_destination": ticker_plan.get("proposed_archive_destination"),
                "candidate_count": len(exact_archive_candidates),
            },
            "acceptance": "Rollback must prove every moved artifact can be restored and validators return to the pre-apply state.",
        },
        {
            "gate": "post_apply_validation",
            "status": "specified_not_run",
            "proof_artifact": None,
            "current_value": {
                "post_apply_validation_ready": False,
                "commands": [
                    "python scripts\\finance_sql_canon_access.py --write --validate",
                    "python scripts\\sql_canon_front_door_readiness_packet.py --write --validate",
                    "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
                    "python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate",
                    "python scripts\\db_lifecycle_manifest.py --write --validate",
                    "python scripts\\trade_grade_os_freshness_cron_runner.py --component all --full-answer-mode changed --write --write-md --validate",
                    "python scripts\\retail_truth_routing_contract.py --write --validate",
                    "python scripts\\retail_answer_harness.py --write --validate",
                    "python scripts\\cron_contract_validator.py --write --validate --require-contracts",
                    "python scripts\\changed_file_validator_router.py --write --validate",
                ],
            },
            "acceptance": "Post-apply validators must pass after archive/delete apply and before the lifecycle lane closes.",
        },
        {
            "gate": "explicit_owner_approval",
            "status": "required_not_granted",
            "proof_artifact": None,
            "current_value": {
                "randall_exact_archive_approval": False,
                "randall_exact_delete_approval": False,
            },
            "acceptance": "Randall must approve the exact lifecycle packet scope after seeing inventory, diff, rollback, and validation plan.",
        },
    ]

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "SQL-CANON",
        "purpose": "Separate lifecycle gate for planning legacy-42 compatibility packet archive/delete without performing archive/delete.",
        "recommendation": (
            "continue parallel proof phases; prepare a separate archive approval/diff packet for tmp/ticker-answer-packets; "
            "do not delete/apply/retire fallback or source feeders yet"
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "routing_alignment": docs_alignment(),
        "current_route_health": {
            "sql_canon_front_door": {
                "artifact": rel(FRONT_DOOR_READINESS),
                "status": front.get("status"),
                "validation_status": as_dict(front.get("validation")).get("status"),
                "front_door_wf85_default": f"{front_proof.get('front_door_wf85_default_count')}/{front_proof.get('front_door_evaluated_count')}",
                "strategic_front_door_wf85_default": f"{front_proof.get('strategic_front_door_wf85_default_count')}/{front_proof.get('strategic_front_door_evaluated_count')}",
                "legacy_entry_stop_front_door_blockers": front_proof.get("legacy_entry_stop_front_door_blocker_count"),
                "legacy_42_retired_from_blocking": front_scope.get("legacy_42_retired_from_blocking"),
                "legacy_42_count_advisory_only": front_contract.get("legacy_42_count_advisory_only"),
                "source_open_contract_true_count": front_proof.get("source_open_contract_true_count"),
                "route_good_for_next_packet": front_route_aligned,
            },
            "owner_decision_packet": {
                "artifact": rel(OWNER_DECISION),
                "status": owner.get("status"),
                "hard_gate_actions_allowed": owner.get("hard_gate_actions_allowed"),
            },
            "wf78_tier_routing": {
                "artifact": rel(WF78_ROUTING),
                "status": wf78.get("status"),
                "tier_counts": wf78_summary.get("tier_counts"),
                "state_counts": wf78_summary.get("state_counts"),
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
            },
            "wf84_wf85_trade_grade": {
                "artifact": rel(TRADE_GRADE_OS),
                "status": trade_grade.get("status"),
                "live_validation_status": (
                    "blocked"
                    if tier_ab_band_validation.get("status") == "error"
                    else trade_grade.get("status")
                ),
                "trade_grade_data_ready_for_decisions": trade_grade_summary.get("trade_grade_data_ready_for_decisions"),
                "wf85_full_answer_assembler_status": trade_grade_summary.get("wf85_full_answer_assembler_status"),
                "wf85_full_answer_assembler_built_count": trade_grade_summary.get("wf85_full_answer_assembler_built_count"),
                "wf85_review_ready_count": trade_grade_summary.get("wf85_review_ready_count"),
                "wf85_approval_card_draft_count": trade_grade_summary.get("wf85_approval_card_draft_count"),
                "wf85_decision_blocked_count": trade_grade_summary.get("wf85_decision_blocked_count"),
                "authority_violation_count": trade_grade_summary.get("wf85_authority_violation_count"),
                "tier_a_b_band_guard_artifact": rel(TIER_AB_BAND_GUARD),
                "tier_a_b_band_guard_status": tier_ab_band_guard.get("status"),
                "tier_a_b_band_guard_validation": tier_ab_band_validation.get("status"),
                "tier_a_b_stale_complete_band_context_count": tier_ab_band_summary.get("stale_complete_band_context_count"),
                "tier_a_b_stale_complete_band_context_tickers": tier_ab_band_summary.get("stale_complete_band_context_tickers"),
                "trade_grade_os_upgrade_readiness_blocker": (
                    "tier_a_b_complete_band_context_stale"
                    if tier_ab_band_validation.get("status") == "error"
                    else None
                ),
            },
            "retail_truth_routing": {
                "customer_decision_artifact": rel(RETAIL_CUSTOMER_DECISION),
                "customer_decision_status": retail_customer.get("status"),
                "control_plane_artifact": rel(RETAIL_CONTROL),
                "control_plane_status": retail_control.get("status"),
                "customer_output_allowed": False,
                "internal_truth_routing_alignment": "retain source-open and unsafe-prompt gates; route internal answers through guarded truth contracts only",
            },
            "trade_grade_autonomous_os": {
                "artifact": rel(WF87_COMMAND),
                "status": wf87.get("status"),
                "autonomy_state": wf87_summary.get("autonomy_state"),
                "phase_c_autonomous_paper_buy_ready": wf87_summary.get("phase_c_autonomous_paper_buy_ready"),
                "autonomous_execution_allowed_now": wf87_summary.get("autonomous_execution_allowed_now"),
                "live_execution_allowed_now": wf87_summary.get("live_execution_allowed_now"),
                "shadow_decisions": wf87_summary.get("shadow_decisions"),
                "shadow_sessions": wf87_summary.get("shadow_sessions"),
                "binding_blockers": wf87_summary.get("binding_blockers"),
            },
            "cron_reduction": {
                "inventory_artifact": rel(CRON_REDUCTION),
                "control_artifact": rel(CRON_CONTROL),
                "inventory_status": cron_reduction.get("status"),
                "control_status": cron_control.get("status"),
                "enabled_jobs": cron_reduction_summary.get("enabled_jobs"),
                "phase2_target_enabled_jobs": cron_reduction_summary.get("phase2_target_enabled_jobs"),
                "final_target_enabled_jobs": cron_reduction_summary.get("final_target_enabled_jobs"),
                "control_blocked_count": cron_control_summary.get("blocked_count"),
                "next_slice": "phase2_market_window_shadow_proof_before_live_disable",
                "ready_for_live_disable_to_25_27_now": False,
            },
        },
        "legacy_42_lifecycle_scope": {
            "candidate_surface": "tmp/ticker-answer-packets",
            "replacement_owner": "scripts/trade_grade_full_answer_assembler.py",
            "replacement_artifact_pattern": "tmp/trade-grade-full-answer/<TICKER>.json",
            "legacy_packet_count": ticker_summary.get("legacy_packet_count"),
            "archive_planning_ready": archive_planning_ready,
            "archive_completed": archive_completed,
            "archive_ready_now_from_ticker_packet_plan": ticker_summary.get("archive_ready_now"),
            "delete_ready_now": False,
            "apply_allowed_now": False,
            "active_reference_count": ticker_summary.get("active_reference_count"),
            "compatibility_or_governance_reference_count": ticker_summary.get("compatibility_or_governance_reference_count"),
            "reference_inventory": reference_inventory,
            "active_references": active_references,
            "exact_archive_candidates": exact_archive_candidates,
            "proposed_archive_destination": ticker_plan.get("proposed_archive_destination"),
            "db_lifecycle_summary": {
                "artifact": rel(DB_LIFECYCLE),
                "status": db_lifecycle.get("status"),
                "archive_ready_count": db_summary.get("archive_ready_count"),
                "delete_ready_count": db_summary.get("delete_ready_count"),
                "unknown_count": db_summary.get("unknown_count"),
                "integrity_error_count": db_summary.get("integrity_error_count"),
            },
            "duplicate_surface_retirement_summary": {
                "artifact": rel(RETIREMENT_READINESS),
                "status": retirement.get("status"),
                "archive_ready_count": retirement_summary.get("archive_ready_count"),
                "delete_ready_count": retirement_summary.get("delete_ready_count"),
                "source_feeder_retirement_ready_count": retirement_summary.get("source_feeder_retirement_ready_count"),
                "duplicate_surface_retirement_ready_count": retirement_summary.get("duplicate_surface_retirement_ready_count"),
            },
            "no_runtime_imports_guard_summary": {
                "artifact": rel(NO_RUNTIME_IMPORTS_GUARD),
                "status": no_runtime_guard.get("status"),
                "active_runtime_blocker_count": runtime_blocker_count,
                "archive_candidate_script_count": no_runtime_summary.get("archive_candidate_script_count"),
            },
        },
        "exact_consumer_inventory": {
            "artifact": rel(CONSUMER_INVENTORY),
            "status": inventory.get("status"),
            "summary": inventory_summary,
            "p0_answer_path_consumers": p0_consumers(inventory),
            "legacy_packet_reference_inventory": reference_inventory,
        },
        "lifecycle_gates": lifecycle_gates,
        "parallel_phase_plan": [
            {
                "phase": "A",
                "lane": "SQL-CANON::front-door-sql-first-promotion-decision",
                "goal": "Build the exact SQL-first promotion decision packet only from strategic SQL production proof; legacy 42 stays compatibility inventory.",
                "can_run_parallel": True,
                "must_not_do": ["apply promotion", "retire fallback", "change customer output"],
                "acceptance": [
                    "front-door packet validates SQL-first strategic readiness or a clean no-production wait state",
                    "fallback/source-open contract remains retained",
                    "patch diff and rollback proof are named but not applied",
                ],
            },
            {
                "phase": "B",
                "lane": "SQL-CANON::legacy-42-archive-diff-rollback",
                "goal": "Prepare the exact archive approval/diff packet for tmp/ticker-answer-packets.",
                "can_run_parallel": True,
                "must_not_do": ["delete files", "move/archive files", "retire ticker_answer_packet.py"],
                "acceptance": [
                    "all 42 archive candidates named",
                    "active references remain zero or explicitly classified compatibility-only",
                    "restore/rollback command path is proven before asking for approval",
                ],
            },
            {
                "phase": "C",
                "lane": "WF-RETAIL-ROUTING::sql-canon-truth-contract-alignment",
                "goal": "Keep Retail-Grade Truth Routing pointed at guarded SQL/WF85 truth for internal answer safety while customer output remains blocked.",
                "can_run_parallel": True,
                "must_not_do": ["customer/public output", "personalization/suitability/account routing"],
                "acceptance": [
                    "retail truth routing validators pass",
                    "unsafe prompt coverage remains clean",
                    "customer output decision remains blocked without separate gates",
                ],
            },
            {
                "phase": "D",
                "lane": "WF87::trade-grade-autonomous-os-sql-canon-readiness-bridge",
                "goal": "Connect SQL-canon/WF85 route health into the WF87 command-center readiness view without creating execution authority.",
                "can_run_parallel": True,
                "must_not_do": ["paper order submit/cancel/sell", "live endpoint", "owner approval inference"],
                "acceptance": [
                    "WF87 command center remains validation-ok",
                    "SQL-canon status and WF85 route health are visible",
                    "autonomous execution remains false until WF87 maturity gates clear",
                ],
            },
            {
                "phase": "E",
                "lane": "CRON::phase2-market-window-shadow-reduction",
                "goal": "Continue cron reduction toward 25-27 by proving Phase2 replacement contracts during valid market windows.",
                "can_run_parallel": True,
                "must_not_do": ["disable jobs", "edit schedules", "change runtime service/channel"],
                "acceptance": [
                    "Phase2 shadow parity is clean during market-session windows",
                    "rollback IDs and contract validation are clean",
                    "separate owner approval packet exists before live disable",
                ],
            },
        ],
        "readiness_decision": {
            "continue_parallel_proof_phases": True,
            "ready_to_prepare_archive_approval_packet": archive_planning_ready and not archive_completed and runtime_blocker_count == 0,
            "ready_to_prepare_full_legacy_42_script_archive_packet": no_runtime_guard_clean,
            "runtime_cutover_required_before_full_archive": runtime_blocker_count > 0,
            "active_runtime_blocker_count": runtime_blocker_count,
            "legacy_packet_archive_completed": archive_completed,
            "ready_to_archive_or_delete_now": False,
            "ready_to_disable_cron_jobs_to_25_27_now": False,
            "ready_for_trade_grade_autonomous_execution": False,
            "ready_for_trade_grade_os_upgrade_readiness_claim": tier_ab_band_validation.get("status") != "error",
            "trade_grade_os_readiness_blockers": tier_ab_band_validation.get("errors") or [],
            "why": (
                "Routing is healthy for proof continuation: SQL/WF85 front door is SQL-first, legacy 42 checks are advisory-only, "
                "and ticker answer packets are assembler-generated compatibility snapshots. Full Legacy 42 script/archive prep also requires the "
                "no-runtime-import guard to be clean. Lifecycle apply still needs a separate diff, rollback proof, post-apply validation, "
                "and explicit Randall approval."
            ),
        },
        "validation": {
            "status": "ok" if status in {"planning_ready_apply_blocked", "planning_ready_runtime_cutover_required"} else "error",
            "errors": [],
            "warnings": [],
        },
        "stop_lines": [
            "Do not archive, move, delete, or apply from this packet.",
            "Do not retire source feeders, Python fallback, ticker_answer_packet.py, or source-open fallback from this packet.",
            "Do not promote SQL-first front-door behavior without a separate exact approval packet.",
            "Do not change cron schedules or disable jobs from this packet.",
            "Do not create customer/public output, portfolio/canon/cash/sizing/risk mutation, capital deployment, paper/live execution, brokerage/account action, or money movement.",
        ],
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    if packet.get("status") not in {"planning_ready_apply_blocked", "planning_ready_runtime_cutover_required"}:
        errors.append(f"packet_status_not_ready:{packet.get('status')}")

    docs = as_dict(packet.get("routing_alignment"))
    for key, row in docs.items():
        if as_dict(row).get("exists") is not True:
            errors.append(f"routing_alignment_doc_missing:{key}")

    route = as_dict(packet.get("current_route_health"))
    sql_route = as_dict(route.get("sql_canon_front_door"))
    if sql_route.get("route_good_for_next_packet") is not True:
        errors.append("sql_canon_front_door_not_green")
    if sql_route.get("legacy_42_retired_from_blocking") is not True:
        errors.append("legacy_42_not_retired_from_blocking")
    if sql_route.get("legacy_42_count_advisory_only") is not True:
        errors.append("legacy_42_count_not_advisory_only")

    lifecycle = as_dict(packet.get("legacy_42_lifecycle_scope"))
    if lifecycle.get("archive_planning_ready") is not True:
        errors.append("legacy_42_archive_planning_not_ready")
    if lifecycle.get("apply_allowed_now") is not False:
        errors.append("legacy_42_apply_allowed")
    if lifecycle.get("delete_ready_now") is not False:
        errors.append("legacy_42_delete_ready")
    legacy_packet_count = int(lifecycle.get("legacy_packet_count") or 0)
    if legacy_packet_count <= 0:
        errors.append("legacy_packet_count_zero")
    if int(lifecycle.get("active_reference_count") or 0) != 0:
        errors.append("active_legacy_packet_references_not_zero")
    if lifecycle.get("archive_completed") is not True and len(as_list(lifecycle.get("exact_archive_candidates"))) != legacy_packet_count:
        errors.append("exact_archive_candidate_count_mismatch")

    gates = {as_dict(row).get("gate"): as_dict(row) for row in as_list(packet.get("lifecycle_gates"))}
    for gate in (
        "legacy_42_no_runtime_imports_guard",
        "exact_consumer_inventory",
        "patch_diff_packet",
        "rollback_proof",
        "post_apply_validation",
        "explicit_owner_approval",
    ):
        if gate not in gates:
            errors.append(f"missing_lifecycle_gate:{gate}")
    if as_dict(gates.get("patch_diff_packet")).get("status") != "not_started_hard_stop":
        errors.append("patch_diff_gate_not_hard_stop")
    if as_dict(gates.get("rollback_proof")).get("status") != "not_started_hard_stop":
        errors.append("rollback_gate_not_hard_stop")
    if as_dict(gates.get("explicit_owner_approval")).get("status") != "required_not_granted":
        errors.append("explicit_owner_approval_gate_not_required")

    decision = as_dict(packet.get("readiness_decision"))
    if decision.get("ready_to_archive_or_delete_now") is not False:
        errors.append("readiness_decision_allows_archive_delete_now")
    if decision.get("ready_to_disable_cron_jobs_to_25_27_now") is not False:
        errors.append("readiness_decision_allows_cron_disable_now")
    if decision.get("ready_for_trade_grade_autonomous_execution") is not False:
        errors.append("readiness_decision_allows_autonomous_execution")

    retail = as_dict(route.get("retail_truth_routing"))
    if retail.get("customer_output_allowed") is not False:
        errors.append("retail_customer_output_allowed")
    wf87 = as_dict(route.get("trade_grade_autonomous_os"))
    if wf87.get("autonomous_execution_allowed_now") is not False:
        errors.append("wf87_autonomous_execution_allowed")
    if wf87.get("live_execution_allowed_now") is not False:
        errors.append("wf87_live_execution_allowed")
    trade_grade = as_dict(route.get("wf84_wf85_trade_grade"))
    if trade_grade.get("tier_a_b_band_guard_validation") == "error":
        blockers = as_list(as_dict(packet.get("readiness_decision")).get("trade_grade_os_readiness_blockers"))
        if "tier_a_b_complete_band_context_stale" not in blockers:
            errors.append("trade_grade_band_guard_blocker_not_exposed")
    cron = as_dict(route.get("cron_reduction"))
    if cron.get("ready_for_live_disable_to_25_27_now") is not False:
        errors.append("cron_live_disable_allowed")

    return sorted(set(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet()
    errors = validate_packet(packet) if args.validate else []
    packet["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": [],
    }
    if errors and packet["status"] == "planning_ready_apply_blocked":
        packet["status"] = "blocked_validation_error"
    if args.write:
        atomic_write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out) if args.write else None,
                "recommendation": packet["recommendation"],
                "readiness_decision": packet["readiness_decision"],
                "legacy_42_lifecycle_scope": {
                    "legacy_packet_count": packet["legacy_42_lifecycle_scope"]["legacy_packet_count"],
                    "archive_planning_ready": packet["legacy_42_lifecycle_scope"]["archive_planning_ready"],
                    "ready_to_archive_or_delete_now": packet["readiness_decision"]["ready_to_archive_or_delete_now"],
                    "exact_archive_candidate_count": len(packet["legacy_42_lifecycle_scope"]["exact_archive_candidates"]),
                },
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
