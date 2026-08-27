#!/usr/bin/env python3
"""Emit proof-only packets for the SQL-canon parallel phase plan.

The executor builds five independent review packets:

Phase A: SQL-first front-door promotion decision packet.
Phase B: legacy-42 ticker-answer archive diff/rollback packet.
Phase C: Retail-Grade Truth Routing SQL-canon alignment packet.
Phase D: WF87 Trade-Grade Autonomous OS SQL-canon readiness bridge.
Phase E: cron Phase2 market-window shadow reduction packet.

It never archives, deletes, moves, applies patches, edits cron schedules,
promotes SQL-first behavior, emits customer output, or authorizes execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

AGGREGATE_OUT = TMP / "sql-canon-parallel-phase-execution-packet.json"
PHASE_A_OUT = TMP / "sql-first-front-door-promotion-decision-packet.json"
PHASE_B_OUT = TMP / "legacy-42-archive-diff-rollback-packet.json"
PHASE_C_OUT = TMP / "retail-sql-canon-truth-alignment-packet.json"
PHASE_D_OUT = TMP / "wf87-sql-canon-readiness-bridge.json"
PHASE_E_OUT = TMP / "cron-phase2-market-window-shadow-reduction-packet.json"

FRONT_DOOR = TMP / "sql-canon-front-door-readiness-packet.json"
OWNER_DECISION = TMP / "sql-canon-owner-decision-packet.json"
LEGACY_LIFECYCLE = TMP / "legacy-42-lifecycle-gate-packet.json"
TICKER_PACKET_RETIREMENT = TMP / "ticker-answer-packet-retirement-approval-plan-20260609.json"
TICKER_ARCHIVE_APPLY = TMP / "ticker-answer-packet-archive-apply-current.json"
TICKER_VERSIONED_ARCHIVE = TMP / "ticker-answer-packet-versioned-archive-approval.json"
SQL_CONSUMER_INVENTORY = TMP / "sql-canon-consumer-inventory.json"
RETAIL_CONTRACT = TMP / "retail-truth-routing-contract.json"
RETAIL_HARNESS = TMP / "retail-answer-harness.json"
RETAIL_CUSTOMER_DECISION = TMP / "retail-customer-output-decision-packet.json"
RETAIL_CONTROL = TMP / "retail-automation-control-plane.json"
WF87_COMMAND = TMP / "wf87-autonomy-command-center.json"
TRADE_GRADE_RUNNER = TMP / "trade-grade-os-freshness-cron-runner.json"
TIER_AB_BAND_GUARD = TMP / "tier-ab-band-freshness-cron-guard.json"
CRON_REDUCTION_INVENTORY = TMP / "cron-reduction-inventory.json"
CRON_PHASE2 = TMP / "cron-phase2-shadow-parity.json"
CRON_CONTROL = TMP / "cron-control-packet.json"

SCHEMA = "veritas.sql_canon_parallel_phase_executor.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proof_packet_only": True,
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
    "cron_job_disable_allowed": False,
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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def phase_boundary(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    boundary = dict(AUTHORITY_BOUNDARY)
    if extra:
        boundary.update(extra)
    return boundary


def front_door_route_aligned(front: dict[str, Any]) -> bool:
    proof = as_dict(front.get("proof_summary"))
    scope = as_dict(front.get("scope"))
    contract = as_dict(front.get("readiness_contract"))
    strategic_evaluated_count = int(proof.get("strategic_front_door_evaluated_count") or 0)
    strategic_wf85_count = int(proof.get("strategic_front_door_wf85_default_count") or 0)
    return (
        front.get("status")
        in {
            "readiness_green_promotion_still_owner_gated",
            "readiness_waiting_no_validated_production_scope",
            "readiness_waiting_source_open_guard_retained",
        }
        and as_dict(front.get("validation")).get("status") == "ok"
        and int(proof.get("front_door_hard_blocked_count") or 0) == 0
        and scope.get("legacy_42_retired_from_blocking") is True
        and contract.get("legacy_42_count_advisory_only") is True
        and (strategic_evaluated_count == 0 or strategic_wf85_count == strategic_evaluated_count)
    )


def build_phase_a(now: str) -> dict[str, Any]:
    front = read_json(FRONT_DOOR)
    proof = as_dict(front.get("proof_summary"))
    lifecycle = read_json(LEGACY_LIFECYCLE)
    owner = read_json(OWNER_DECISION)
    aligned = front_door_route_aligned(front)
    strategic_evaluated_count = int(proof.get("strategic_front_door_evaluated_count") or 0)
    return {
        "schema": "veritas.sql_first_front_door_promotion_decision_packet.v1",
        "generated_at_utc": now,
        "phase": "A",
        "status": (
            "owner_review_ready_apply_blocked"
            if aligned and strategic_evaluated_count > 0
            else "strategic_production_wait_apply_blocked"
            if aligned
            else "blocked_pending_front_door_proof"
        ),
        "purpose": "Exact decision packet scaffold for SQL-first finance front-door promotion.",
        "recommendation": "prepare owner approval review; do not apply promotion from this packet",
        "authority_boundary": phase_boundary(),
        "promotion_scope": {
            "candidate_behavior": "finance front door may default to WF85 full-answer output backed by SQL-canon reference levels and JSON proof",
            "front_door_scope": "strategic SQL production scope; legacy 42 is compatibility inventory only",
            "front_door_wf85_default": f"{proof.get('front_door_wf85_default_count')}/{proof.get('front_door_evaluated_count')}",
            "strategic_front_door_wf85_default": f"{proof.get('strategic_front_door_wf85_default_count')}/{proof.get('strategic_front_door_evaluated_count')}",
            "source_open_contract_retained": proof.get("source_open_contract_true_count") == proof.get("front_door_evaluated_count"),
            "fallback_chain_retained": proof.get("fallback_chain_present_count") == proof.get("front_door_evaluated_count"),
            "legacy_entry_stop_blocks": proof.get("legacy_entry_stop_front_door_blocker_count"),
            "legacy_42_retired_from_blocking": as_dict(front.get("scope")).get("legacy_42_retired_from_blocking"),
            "legacy_42_count_advisory_only": as_dict(front.get("readiness_contract")).get("legacy_42_count_advisory_only"),
        },
        "evidence": {
            "front_door_packet": rel(FRONT_DOOR),
            "front_door_status": front.get("status"),
            "front_door_validation": as_dict(front.get("validation")).get("status"),
            "front_door_proof_summary": proof,
            "owner_decision_packet": rel(OWNER_DECISION),
            "owner_decision_status": owner.get("status"),
            "hard_gate_actions_allowed": owner.get("hard_gate_actions_allowed"),
            "legacy_lifecycle_packet": rel(LEGACY_LIFECYCLE),
            "legacy_lifecycle_status": lifecycle.get("status"),
        },
        "required_before_apply": [
            "Randall exact approval for this SQL-first promotion packet",
            "patch diff naming every consumer behavior change",
            "rollback proof restoring prior front-door behavior",
            "post-apply validation proof",
            "fallback/source-open contract retained unless a separate retirement gate clears",
        ],
        "apply_plan": {
            "patch_diff_ready": False,
            "rollback_proof_ready": False,
            "post_apply_validation_ready": False,
            "approval_required": True,
            "apply_allowed_now": False,
        },
        "stop_lines": [
            "No SQL-first promotion is applied by this packet.",
            "No fallback, source feeder, archive/delete, cron, customer, portfolio, account, paper/live, or capital authority changes.",
        ],
    }


def candidate_rows(ticker_plan: dict[str, Any]) -> list[dict[str, Any]]:
    destination_root = str(ticker_plan.get("proposed_archive_destination") or "09. Archive/WF85 Legacy Ticker Answer Packets/preview")
    rows: list[dict[str, Any]] = []
    sources = [item for item in as_list(ticker_plan.get("exact_archive_candidates")) if isinstance(item, str)]
    if not sources:
        sources = [
            str(row.get("path"))
            for row in as_list(ticker_plan.get("packet_rows"))
            if isinstance(row, dict)
            and row.get("built_from_assembler") is True
            and row.get("required_legacy_fields_present") is True
            and isinstance(row.get("path"), str)
        ]
    for source in sources:
        if not isinstance(source, str):
            continue
        source_path = ROOT / source
        destination = Path(destination_root) / source_path.name
        rows.append(
            {
                "source": source,
                "destination": destination.as_posix(),
                "exists": source_path.exists(),
                "size_bytes": source_path.stat().st_size if source_path.exists() else None,
                "sha256": sha256_file(source_path),
                "rollback_action": f"restore {destination.as_posix()} to {source}",
                "archive_ready_for_owner_packet": source_path.exists(),
                "delete_ready": False,
                "apply_allowed_now": False,
            }
        )
    return rows


def versioned_candidate_rows(versioned_packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(versioned_packet.get("rows")):
        row_dict = as_dict(row)
        if not row_dict:
            continue
        rows.append(
            {
                "source": row_dict.get("source"),
                "destination": row_dict.get("proposed_versioned_destination"),
                "exists": row_dict.get("source_exists"),
                "size_bytes": row_dict.get("source_bytes"),
                "sha256": row_dict.get("source_sha256"),
                "conflicting_preview_destination": row_dict.get("conflicting_preview_destination"),
                "conflicting_preview_destination_sha256": row_dict.get("conflicting_preview_destination_sha256"),
                "rollback_action": row_dict.get("rollback_action"),
                "archive_ready_for_owner_packet": row_dict.get("source_exists")
                and not row_dict.get("proposed_versioned_destination_exists"),
                "delete_ready": False,
                "apply_allowed_now": False,
            }
        )
    return rows


def build_phase_b(now: str) -> dict[str, Any]:
    ticker_plan = read_json(TICKER_PACKET_RETIREMENT)
    ticker_summary = as_dict(ticker_plan.get("summary"))
    expected_count = int(ticker_summary.get("legacy_packet_count") or 0)
    archive_completed = (
        ticker_plan.get("status") == "archived"
        and ticker_summary.get("archive_completed") is True
        and expected_count > 0
        and int(ticker_summary.get("legacy_packets_archived_count") or 0) == expected_count
    )
    archive_apply = read_json(TICKER_ARCHIVE_APPLY)
    archive_apply_summary = as_dict(archive_apply.get("summary"))
    versioned_archive = read_json(TICKER_VERSIONED_ARCHIVE)
    versioned_summary = as_dict(versioned_archive.get("summary"))
    versioned_ready = (
        versioned_archive.get("status") == "versioned_archive_owner_review_ready_apply_blocked"
        and as_dict(versioned_archive.get("validation")).get("status") == "ok"
        and int(versioned_summary.get("candidate_count") or 0) == expected_count
        and int(versioned_summary.get("versioned_destination_clear_count") or 0) == expected_count
        and int(versioned_summary.get("versioned_destination_existing_count") or 0) == 0
        and expected_count > 0
    )
    versioned_completed = (
        versioned_archive.get("status") == "versioned_archive_completed"
        and as_dict(versioned_archive.get("validation")).get("status") == "ok"
        and int(versioned_summary.get("candidate_count") or 0) == expected_count
        and int(versioned_summary.get("versioned_destination_existing_count") or 0) == expected_count
        and expected_count > 0
    )
    lifecycle = read_json(LEGACY_LIFECYCLE)
    rows = versioned_candidate_rows(versioned_archive) if versioned_ready or versioned_completed else candidate_rows(ticker_plan)
    all_ready = len(rows) == expected_count and expected_count > 0 and (
        versioned_completed or all(row["archive_ready_for_owner_packet"] for row in rows)
    )
    destination_hash_conflict_count = int(archive_apply_summary.get("destination_hash_conflict_count") or 0)
    if archive_completed:
        status = "archive_completed_no_active_sources"
    elif versioned_completed:
        status = "versioned_archive_completed"
    elif versioned_ready:
        status = "versioned_archive_owner_review_ready_apply_blocked"
    elif destination_hash_conflict_count:
        status = "archive_reconcile_blocked_destination_conflict"
    elif all_ready:
        status = "archive_approval_packet_ready_apply_blocked"
    else:
        status = "blocked_pending_exact_archive_inventory"
    return {
        "schema": "veritas.legacy_42_archive_diff_rollback_packet.v1",
        "generated_at_utc": now,
        "phase": "B",
        "status": status,
        "purpose": "Exact archive diff and rollback proof scaffold for the legacy-42 ticker-answer packet surface.",
        "recommendation": (
            "archive is complete; keep legacy packets archived and do not regenerate active compatibility files"
            if archive_completed or versioned_completed
            else "review the versioned archive approval packet; do not apply without exact Randall approval"
            if versioned_ready
            else "prepare a versioned archive or archive-replace approval packet before any move"
            if destination_hash_conflict_count
            else "ask for owner archive approval only after review; do not archive/delete/apply from this packet"
        ),
        "authority_boundary": phase_boundary(),
        "candidate_surface": {
            "source_surface": "tmp/ticker-answer-packets",
            "replacement_owner": "scripts/trade_grade_full_answer_assembler.py",
            "replacement_artifact": "tmp/trade-grade-full-answer/<TICKER>.json",
            "proposed_archive_destination": ticker_plan.get("proposed_archive_destination"),
            "legacy_packet_count": ticker_summary.get("legacy_packet_count"),
            "legacy_packets_archived_count": ticker_summary.get("legacy_packets_archived_count"),
            "active_reference_count": ticker_summary.get("active_reference_count"),
            "compatibility_or_governance_reference_count": ticker_summary.get("compatibility_or_governance_reference_count"),
            "archive_ready_now_from_planner": ticker_summary.get("archive_ready_now"),
            "archive_apply_report": rel(TICKER_ARCHIVE_APPLY),
            "archive_apply_status": archive_apply.get("status"),
            "destination_hash_conflict_count": destination_hash_conflict_count,
            "active_duplicate_same_hash_count": archive_apply_summary.get("active_duplicate_same_hash_count"),
            "versioned_archive_packet": rel(TICKER_VERSIONED_ARCHIVE),
            "versioned_archive_status": versioned_archive.get("status"),
            "versioned_archive_root": versioned_archive.get("proposed_versioned_archive_root"),
            "versioned_destination_clear_count": versioned_summary.get("versioned_destination_clear_count"),
            "versioned_destination_existing_count": versioned_summary.get("versioned_destination_existing_count"),
            "versioned_archive_completed": versioned_completed,
            "archive_completed_no_active_sources": archive_completed,
        },
        "diff_preview": {
            "move_count": 0 if archive_completed or versioned_completed else len(rows),
            "delete_count": 0,
            "code_patch_count": 0,
            "archive_rows": rows,
        },
        "rollback_proof": {
            "ready_for_owner_review": all_ready,
            "restore_required_count": len(rows),
            "restore_actions": [row["rollback_action"] for row in rows],
            "rollback_validation_commands": [
                "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
                "python scripts\\sql_canon_front_door_readiness_packet.py --write --validate",
                "python scripts\\legacy_42_lifecycle_gate_packet.py --write --validate",
            ],
        },
        "post_apply_validation_commands": [
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\sql_canon_front_door_readiness_packet.py --write --validate",
            "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
            "python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate",
            "python scripts\\db_lifecycle_manifest.py --write --validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
        ],
        "future_apply_command_after_exact_approval": versioned_archive.get("future_apply_command_after_exact_approval"),
        "owner_approval_required_before_archive": not (archive_completed or versioned_completed),
        "apply_allowed_now": False,
        "delete_allowed_now": False,
        "source_artifacts": {
            "ticker_packet_retirement_plan": rel(TICKER_PACKET_RETIREMENT),
            "legacy_lifecycle_gate": rel(LEGACY_LIFECYCLE),
            "ticker_answer_packet_archive_apply": rel(TICKER_ARCHIVE_APPLY),
            "ticker_answer_packet_versioned_archive": rel(TICKER_VERSIONED_ARCHIVE),
        },
        "stop_lines": [
            "No archive/move/delete is performed by this packet.",
            "No overwrite of existing archive destinations.",
            "No scripts/ticker_answer_packet.py deletion or fallback retirement.",
        ],
    }


def build_phase_c(now: str) -> dict[str, Any]:
    contract = read_json(RETAIL_CONTRACT)
    harness = read_json(RETAIL_HARNESS)
    customer = read_json(RETAIL_CUSTOMER_DECISION)
    control = read_json(RETAIL_CONTROL)
    front = read_json(FRONT_DOOR)
    internal_ready = (
        contract.get("status") == "ok"
        and harness.get("status") == "ok"
        and as_dict(customer.get("validation")).get("status") == "ok"
        and customer.get("internal_answer_safety_ready") is True
        and customer.get("customer_output_allowed") is False
    )
    return {
        "schema": "veritas.retail_sql_canon_truth_alignment_packet.v1",
        "generated_at_utc": now,
        "phase": "C",
        "status": "internal_truth_alignment_ready_customer_blocked" if internal_ready else "blocked_pending_retail_truth_proof",
        "purpose": "Align Retail-Grade Truth Routing with SQL-canon/WF85 internal truth surfaces while preserving customer-output blocks.",
        "recommendation": "use internally as an answer-safety gate; do not enable customer/public output",
        "authority_boundary": phase_boundary(
            {
                "internal_answer_safety_allowed": True,
                "customer_output_allowed": False,
                "real_customer_data_allowed": False,
                "personalized_advice_allowed": False,
            }
        ),
        "route_alignment": {
            "sql_wf85_front_door_status": front.get("status"),
            "sql_wf85_front_door_default": f"{as_dict(front.get('proof_summary')).get('front_door_wf85_default_count')}/{as_dict(front.get('proof_summary')).get('front_door_evaluated_count')}",
            "source_open_contract_retained": as_dict(front.get("readiness_contract")).get("source_open_fallback_contract_retained"),
            "retail_truth_contract_status": contract.get("status"),
            "retail_answer_harness_status": harness.get("status"),
            "retail_control_plane_status": control.get("status"),
            "customer_output_decision": customer.get("decision"),
            "customer_output_blockers": customer.get("customer_output_blockers"),
        },
        "required_before_customer_output": customer.get("required_before_customer_output") or [],
        "source_artifacts": {
            "retail_truth_contract": rel(RETAIL_CONTRACT),
            "retail_answer_harness": rel(RETAIL_HARNESS),
            "retail_customer_output_decision": rel(RETAIL_CUSTOMER_DECISION),
            "retail_automation_control_plane": rel(RETAIL_CONTROL),
            "sql_front_door": rel(FRONT_DOOR),
        },
        "stop_lines": [
            "No customer/public/external output.",
            "No real customer data, suitability, tax, retirement, account, brokerage, or personalized advice flow.",
        ],
    }


def build_phase_d(now: str) -> dict[str, Any]:
    wf87 = read_json(WF87_COMMAND)
    wf87_summary = as_dict(wf87.get("summary"))
    front = read_json(FRONT_DOOR)
    trade = read_json(TRADE_GRADE_RUNNER)
    trade_summary = as_dict(trade.get("summary"))
    band_guard = read_json(TIER_AB_BAND_GUARD)
    band_summary = as_dict(band_guard.get("summary"))
    band_validation = as_dict(band_guard.get("validation"))
    blockers = list(as_list(wf87_summary.get("binding_blockers")))
    if not blockers:
        blockers.extend(str(item) for item in as_list(wf87_summary.get("maturity_blockers")))
        blockers.extend(str(item) for item in as_list(wf87_summary.get("runtime_blockers")))
    blockers.extend(str(item) for item in as_list(band_validation.get("errors")))
    stale_count = int(band_summary.get("stale_complete_band_context_count") or 0)
    data_ready = (
        trade_summary.get("trade_grade_data_ready_for_decisions") is True
        and band_guard.get("status") == "ok"
        and band_validation.get("status") == "ok"
        and stale_count == 0
    )
    status = "trade_grade_os_data_ready_runtime_blocked" if data_ready else "trade_grade_os_bridge_ready_runtime_blocked"
    recommendation = (
        "trade-grade data plane is ready; continue shadow accrual, reconciliation maturity, daylight probes, and runtime blocker repair before any autonomous OS activation"
        if data_ready
        else "continue proof accrual and repair Tier A/B band-context freshness before any Trade-Grade OS readiness claim"
    )
    return {
        "schema": "veritas.wf87_sql_canon_readiness_bridge.v1",
        "generated_at_utc": now,
        "phase": "D",
        "status": status,
        "purpose": "Bridge SQL-canon/WF85 route health into WF87 Trade-Grade Autonomous OS readiness without execution authority.",
        "recommendation": recommendation,
        "authority_boundary": phase_boundary(
            {
                "paper_only_design": True,
                "autonomous_paper_submit_allowed": False,
                "autonomous_paper_cancel_allowed": False,
                "autonomous_paper_sell_allowed": False,
                "paper_submit_allowed": False,
                "live_trade_allowed": False,
                "paper_to_live_promotion_allowed": False,
            }
        ),
        "sql_canon_route_health": {
            "front_door_status": front.get("status"),
            "front_door_wf85_default": f"{as_dict(front.get('proof_summary')).get('front_door_wf85_default_count')}/{as_dict(front.get('proof_summary')).get('front_door_evaluated_count')}",
            "wf85_full_answer_built_count": trade_summary.get("wf85_full_answer_assembler_built_count"),
            "wf85_review_ready_count": trade_summary.get("wf85_review_ready_count"),
            "wf85_approval_card_draft_count": trade_summary.get("wf85_approval_card_draft_count"),
            "wf85_decision_blocked_count": trade_summary.get("wf85_decision_blocked_count"),
            "authority_violation_count": trade_summary.get("wf85_authority_violation_count"),
        },
        "wf87_runtime_state": {
            "status": wf87.get("status"),
            "autonomy_state": wf87_summary.get("autonomy_state"),
            "shadow_decisions": wf87_summary.get("shadow_decisions"),
            "shadow_sessions": wf87_summary.get("shadow_sessions"),
            "phase_c_autonomous_paper_buy_ready": wf87_summary.get("phase_c_autonomous_paper_buy_ready"),
            "autonomous_execution_allowed_now": wf87_summary.get("autonomous_execution_allowed_now"),
            "live_execution_allowed_now": wf87_summary.get("live_execution_allowed_now"),
            "binding_blockers": blockers,
        },
        "trade_grade_readiness_blocker": {
            "trade_grade_data_ready_for_decisions": trade_summary.get("trade_grade_data_ready_for_decisions"),
            "trade_grade_data_readiness_status": trade_summary.get("trade_grade_data_readiness_status"),
            "tier_a_b_band_guard_status": band_guard.get("status"),
            "tier_a_b_band_guard_validation": band_validation.get("status"),
            "stale_complete_band_context_count": band_summary.get("stale_complete_band_context_count"),
            "stale_complete_band_context_tickers": band_summary.get("stale_complete_band_context_tickers"),
            "expected_market_date": band_summary.get("expected_market_date"),
        },
        "source_artifacts": {
            "wf87_command_center": rel(WF87_COMMAND),
            "trade_grade_runner": rel(TRADE_GRADE_RUNNER),
            "tier_ab_band_guard": rel(TIER_AB_BAND_GUARD),
            "sql_front_door": rel(FRONT_DOOR),
        },
        "stop_lines": [
            "No paper/live submit, cancel, sell, replace, account action, money movement, or owner approval inference.",
            "No autonomous execution or live readiness claim while WF87 runtime blockers remain.",
        ],
    }


def build_phase_e(now: str) -> dict[str, Any]:
    inventory = read_json(CRON_REDUCTION_INVENTORY)
    inv_summary = as_dict(inventory.get("summary"))
    phase2 = read_json(CRON_PHASE2)
    control = read_json(CRON_CONTROL)
    components = [as_dict(row) for row in as_list(phase2.get("components"))]
    blocked = [row for row in components if row.get("status") != "ok" or row.get("safe_to_disable_source_jobs") is not True]
    return {
        "schema": "veritas.cron_phase2_market_window_shadow_reduction_packet.v1",
        "generated_at_utc": now,
        "phase": "E",
        "status": "blocked_pending_market_window_shadow",
        "purpose": "Phase2 cron reduction packet for market/paper replacement contracts on the path toward 25-27 enabled jobs.",
        "recommendation": "rerun morning and midday market/paper wrappers during valid market windows before any live disable",
        "authority_boundary": phase_boundary(),
        "reduction_state": {
            "enabled_jobs": inv_summary.get("enabled_jobs"),
            "phase2_target_enabled_jobs": inv_summary.get("phase2_target_enabled_jobs"),
            "final_target_enabled_jobs": inv_summary.get("final_target_enabled_jobs"),
            "current_replacement_contracts": inv_summary.get("current_replacement_contracts"),
            "phase2_status": phase2.get("status"),
            "cron_control_status": control.get("status"),
            "cron_control_blocked_count": as_dict(control.get("summary")).get("blocked_count"),
            "ready_to_disable_jobs_now": False,
        },
        "phase2_components": components,
        "blocked_components": blocked,
        "required_before_disable": [
            "fresh valid-market-window morning_market_paper shadow run",
            "fresh valid-market-window midday_market_paper shadow run",
            "cron contract validator clean",
            "rollback IDs and source-job list in exact disable packet",
            "Randall exact approval for live job disable",
        ],
        "source_artifacts": {
            "cron_reduction_inventory": rel(CRON_REDUCTION_INVENTORY),
            "cron_phase2_shadow_parity": rel(CRON_PHASE2),
            "cron_control_packet": rel(CRON_CONTROL),
        },
        "stop_lines": [
            "No cron schedule mutation or job disable.",
            "No customer, paper/live, account, portfolio, or capital authority change.",
        ],
    }


def validate_boundary(name: str, packet: dict[str, Any], errors: list[str]) -> None:
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if key == "proof_packet_only" and name != "aggregate":
            continue
        if boundary.get(key) is not expected:
            errors.append(f"{name}:authority_boundary_drift:{key}")


def build_packets() -> dict[str, Any]:
    now = utc_now()
    phases = {
        "A": build_phase_a(now),
        "B": build_phase_b(now),
        "C": build_phase_c(now),
        "D": build_phase_d(now),
        "E": build_phase_e(now),
    }
    blocked = {
        key: packet.get("status")
        for key, packet in phases.items()
        if str(packet.get("status") or "").startswith("blocked")
        or "blocked" in str(packet.get("status") or "")
        or "runtime_blocked" in str(packet.get("status") or "")
    }
    owner_review_ready = [
        key
        for key, packet in phases.items()
        if packet.get("status") in {
            "owner_review_ready_apply_blocked",
            "archive_approval_packet_ready_apply_blocked",
            "versioned_archive_owner_review_ready_apply_blocked",
        }
    ]
    aggregate = {
        "schema": SCHEMA,
        "generated_at_utc": now,
        "status": "parallel_phase_packets_ready_with_blockers",
        "workflow": "SQL-CANON",
        "purpose": "Aggregate proof-only executor for the recommended parallel SQL-canon, legacy lifecycle, retail, WF87, and cron-reduction phases.",
        "recommendation": "continue Phase A/B owner-review packets and Phase C internal routing; repair Phase D/E blockers before readiness claims or live disables",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "phase_outputs": {
            "A": rel(PHASE_A_OUT),
            "B": rel(PHASE_B_OUT),
            "C": rel(PHASE_C_OUT),
            "D": rel(PHASE_D_OUT),
            "E": rel(PHASE_E_OUT),
        },
        "phase_statuses": {key: packet.get("status") for key, packet in phases.items()},
        "blocked_or_not_ready_phases": blocked,
        "summary": {
            "phase_count": len(phases),
            "owner_review_ready_phases": owner_review_ready,
            "internal_ready_customer_blocked_phases": ["C"],
            "blocked_phases": sorted(blocked),
            "ready_to_archive_or_delete_now": False,
            "ready_to_promote_sql_first_now": False,
            "ready_to_disable_cron_jobs_now": False,
            "ready_for_trade_grade_autonomous_execution": False,
        },
        "next_actions": [
            "Review Phase A SQL-first promotion packet only when strategic production scope is non-empty; do not apply without exact approval.",
            (
                "Phase B archive is complete; keep legacy packets archived and avoid regenerating active compatibility files."
                if phases["B"].get("status") == "versioned_archive_completed"
                else "Review Phase B versioned archive approval packet; do not archive/delete without exact approval."
                if phases["B"].get("status") == "versioned_archive_owner_review_ready_apply_blocked"
                else "Resolve Phase B archive destination hash conflicts with a versioned archive or archive-replace approval packet."
                if "B" in blocked
                else "Review Phase B legacy-42 archive diff/rollback packet; do not archive/delete without exact approval."
            ),
            "Keep Phase C Retail routing internal and customer-blocked.",
            "Repair DECK Tier A/B band-context freshness before claiming Trade-Grade OS upgrade readiness.",
            "Rerun cron Phase2 morning/midday market-paper shadow proof during a valid market window before disabling jobs.",
        ],
        "phases": phases,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [
                "Phase D and E blockers are expected readiness blockers, not authority to loosen gates.",
            ],
        },
        "stop_lines": [
            "No archive/delete/move/apply.",
            "No SQL-first promotion apply.",
            "No cron schedule mutation or job disable.",
            "No customer/public output.",
            "No portfolio/canon/cash/sizing/risk mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }
    return {"aggregate": aggregate, **phases}


def validate_packets(packets: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    aggregate = as_dict(packets.get("aggregate"))
    validate_boundary("aggregate", aggregate, errors)
    phases = as_dict(aggregate.get("phases"))
    if set(phases) != {"A", "B", "C", "D", "E"}:
        errors.append("aggregate_missing_phases")
    for phase_id in ("A", "B", "C", "D", "E"):
        packet = as_dict(packets.get(phase_id))
        validate_boundary(phase_id, packet, errors)
        if packet.get("phase") != phase_id:
            errors.append(f"phase_id_mismatch:{phase_id}")
        if as_dict(packet.get("authority_boundary")).get("apply_allowed_now") is not False:
            errors.append(f"{phase_id}:apply_allowed")

    phase_a = as_dict(packets.get("A"))
    if phase_a.get("status") not in {"owner_review_ready_apply_blocked", "strategic_production_wait_apply_blocked"}:
        errors.append("phase_a_not_owner_review_or_wait_ready")
    if as_dict(phase_a.get("apply_plan")).get("apply_allowed_now") is not False:
        errors.append("phase_a_apply_allowed")
    promotion_scope = as_dict(phase_a.get("promotion_scope"))
    if promotion_scope.get("legacy_42_retired_from_blocking") is not True:
        errors.append("phase_a_legacy_42_not_retired_from_blocking")
    if promotion_scope.get("legacy_42_count_advisory_only") is not True:
        errors.append("phase_a_legacy_42_count_not_advisory_only")

    phase_b = as_dict(packets.get("B"))
    expected_archive_count = int(as_dict(phase_b.get("candidate_surface")).get("legacy_packet_count") or 0)
    if phase_b.get("status") not in {
        "archive_approval_packet_ready_apply_blocked",
            "archive_reconcile_blocked_destination_conflict",
            "versioned_archive_owner_review_ready_apply_blocked",
            "versioned_archive_completed",
            "archive_completed_no_active_sources",
        }:
        errors.append("phase_b_not_archive_review_or_reconcile_ready")
    rows = as_list(as_dict(phase_b.get("diff_preview")).get("archive_rows"))
    if expected_archive_count <= 0:
        errors.append("phase_b_archive_expected_count_zero")
    if len(rows) != expected_archive_count:
        errors.append("phase_b_archive_candidate_count_mismatch")
    if any(as_dict(row).get("apply_allowed_now") is not False for row in rows):
        errors.append("phase_b_row_apply_allowed")
    if phase_b.get("delete_allowed_now") is not False:
        errors.append("phase_b_delete_allowed")
    conflict_count = int(as_dict(phase_b.get("candidate_surface")).get("destination_hash_conflict_count") or 0)
    if phase_b.get("status") == "archive_reconcile_blocked_destination_conflict" and conflict_count <= 0:
        errors.append("phase_b_conflict_status_without_conflicts")
    versioned_clear_count = int(as_dict(phase_b.get("candidate_surface")).get("versioned_destination_clear_count") or 0)
    versioned_existing_count = int(as_dict(phase_b.get("candidate_surface")).get("versioned_destination_existing_count") or 0)
    if phase_b.get("status") == "versioned_archive_owner_review_ready_apply_blocked":
        if versioned_clear_count != expected_archive_count:
            errors.append("phase_b_versioned_destination_clear_count_mismatch")
        if versioned_existing_count != 0:
            errors.append("phase_b_versioned_destination_existing_count_not_zero")
        if not phase_b.get("future_apply_command_after_exact_approval"):
            errors.append("phase_b_missing_future_apply_command")
    if phase_b.get("status") == "versioned_archive_completed" and versioned_existing_count != expected_archive_count:
        errors.append("phase_b_completed_without_expected_versioned_destinations")

    phase_c = as_dict(packets.get("C"))
    if phase_c.get("status") != "internal_truth_alignment_ready_customer_blocked":
        errors.append("phase_c_not_internal_ready")
    if as_dict(phase_c.get("authority_boundary")).get("customer_output_allowed") is not False:
        errors.append("phase_c_customer_output_allowed")

    phase_d = as_dict(packets.get("D"))
    wf87 = as_dict(phase_d.get("wf87_runtime_state"))
    if wf87.get("autonomous_execution_allowed_now") is not False:
        errors.append("phase_d_autonomous_execution_allowed")
    if wf87.get("live_execution_allowed_now") is not False:
        errors.append("phase_d_live_execution_allowed")
    band = as_dict(phase_d.get("trade_grade_readiness_blocker"))
    if band.get("tier_a_b_band_guard_validation") == "error":
        errors.append("phase_d_tier_ab_band_guard_validation_error")
    if int(band.get("stale_complete_band_context_count") or 0) > 0 and not as_list(band.get("stale_complete_band_context_tickers")):
        errors.append("phase_d_stale_band_count_without_tickers")
    if phase_d.get("status") == "trade_grade_os_data_ready_runtime_blocked" and band.get("trade_grade_data_ready_for_decisions") is not True:
        errors.append("phase_d_data_ready_status_without_data_ready")

    phase_e = as_dict(packets.get("E"))
    if phase_e.get("status") != "blocked_pending_market_window_shadow":
        errors.append("phase_e_not_market_window_blocked")
    if as_dict(phase_e.get("reduction_state")).get("ready_to_disable_jobs_now") is not False:
        errors.append("phase_e_disable_allowed")

    summary = as_dict(aggregate.get("summary"))
    for key in (
        "ready_to_archive_or_delete_now",
        "ready_to_promote_sql_first_now",
        "ready_to_disable_cron_jobs_now",
        "ready_for_trade_grade_autonomous_execution",
    ):
        if summary.get(key) is not False:
            errors.append(f"aggregate_summary_allows:{key}")

    return sorted(set(errors))


def write_packets(packets: dict[str, Any]) -> None:
    atomic_write_json(PHASE_A_OUT, packets["A"], indent=2)
    atomic_write_json(PHASE_B_OUT, packets["B"], indent=2)
    atomic_write_json(PHASE_C_OUT, packets["C"], indent=2)
    atomic_write_json(PHASE_D_OUT, packets["D"], indent=2)
    atomic_write_json(PHASE_E_OUT, packets["E"], indent=2)
    atomic_write_json(AGGREGATE_OUT, packets["aggregate"], indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packets = build_packets()
    errors = validate_packets(packets) if args.validate else []
    packets["aggregate"]["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": packets["aggregate"]["validation"]["warnings"],
    }
    if errors:
        packets["aggregate"]["status"] = "blocked_validation_error"
    if args.write:
        write_packets(packets)
    aggregate = packets["aggregate"]
    print(
        json.dumps(
            {
                "status": aggregate["status"],
                "phase_statuses": aggregate["phase_statuses"],
                "blocked_or_not_ready_phases": aggregate["blocked_or_not_ready_phases"],
                "summary": aggregate["summary"],
                "outputs": aggregate["phase_outputs"] | {"aggregate": rel(AGGREGATE_OUT)},
                "validation": aggregate["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
