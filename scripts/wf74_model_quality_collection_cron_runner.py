#!/usr/bin/env python3
"""Cron runner for WF74 model-quality and finance-correctness collection.

This keeps the scheduled path to one stable command. It refreshes operational
telemetry, model/run attribution coverage, finance recommendation rule checks,
and the WF74 scorecard, then records cron-control proof.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "wf74-model-quality-collection-cron-runner.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "wf74.model_quality_collection_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_or_content_capture_allowed": False,
    "external_export_allowed": False,
    "model_ranking_claim": False,
    "investment_correctness_claim": False,
    "wf55_outcome_grade_assignment_allowed": False,
    "owner_approval_inferred": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
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


def tail(text: str, limit: int = 1200) -> str:
    return text[-limit:] if len(text) > limit else text


def command_plan(include_harness: bool) -> list[tuple[str, list[str], int]]:
    plan: list[tuple[str, list[str], int]] = [
        ("otel_tool_workflow_metadata", [sys.executable, "scripts\\otel_tool_workflow_metadata.py", "--write", "--write-md", "--validate"], 90),
        ("otel_ops_control", [sys.executable, "scripts\\otel_ops_control.py", "--write", "--write-db", "--multi-window", "--validate"], 180),
        ("otel_runtime_metadata_probe", [sys.executable, "scripts\\otel_runtime_metadata_probe.py", "--write", "--write-md", "--validate"], 90),
        ("changed_file_validator_router", [sys.executable, "scripts\\changed_file_validator_router.py", "--write", "--validate"], 90),
        ("coding_outcome_ledger", [sys.executable, "scripts\\coding_outcome_ledger.py", "--write", "--validate"], 90),
        ("validator_timing_ledger_normal", [sys.executable, "scripts\\validator_timing_ledger.py", "--profile", "normal", "--write", "--validate"], 240),
        ("coding_runtime_kpi_probe", [sys.executable, "scripts\\coding_runtime_kpi_probe.py", "--write", "--write-md", "--validate"], 90),
        ("cron_spark_canary_monitor", [sys.executable, "scripts\\cron_spark_canary_monitor.py", "--write", "--validate"], 120),
        ("model_run_ledger", [sys.executable, "scripts\\model_run_ledger.py", "--write", "--write-md", "--validate"], 120),
        ("token_usage_ledger", [sys.executable, "scripts\\token_usage_ledger.py", "--write", "--write-md", "--validate"], 90),
        (
            "finance_recommendation_correctness_ledger",
            [sys.executable, "scripts\\finance_recommendation_correctness_ledger.py", "--write", "--write-md", "--validate"],
            120,
        ),
        (
            "finance_response_quality_slice",
            [sys.executable, "scripts\\finance_response_quality_slice.py", "--write", "--write-md", "--validate"],
            120,
        ),
        ("model_learning_metadata_ledger", [sys.executable, "scripts\\model_learning_metadata_ledger.py", "--write", "--write-md", "--validate"], 120),
        ("otel_learning_loop", [sys.executable, "scripts\\otel_learning_loop.py", "--write", "--write-md", "--validate"], 90),
        ("model_quality_scorecard", [sys.executable, "scripts\\model_quality_scorecard.py", "--write", "--write-md", "--validate"], 120),
        (
            "wf74_improvement_opportunity_queue",
            [sys.executable, "scripts\\wf74_improvement_opportunity_queue.py", "--write", "--write-md", "--validate"],
            90,
        ),
        ("improvement_ledger", [sys.executable, "scripts\\improvement_ledger.py", "--write", "--write-md", "--validate"], 90),
        (
            "wf74_reflection_to_proposal_autopilot",
            [sys.executable, "scripts\\wf74_reflection_to_proposal_autopilot.py", "--write", "--write-md", "--validate"],
            90,
        ),
        (
            "wf74_auto_patch_proposer",
            [sys.executable, "scripts\\wf74_auto_patch_proposer.py", "--write", "--write-md", "--validate"],
            90,
        ),
        (
            "owner_gated_action_review_queue",
            [sys.executable, "scripts\\owner_gated_action_review_queue.py", "--write", "--write-md", "--validate"],
            90,
        ),
        ("artifact_index_incremental", [sys.executable, "scripts\\artifact_index.py", "incremental"], 180),
        ("artifact_index_validate", [sys.executable, "scripts\\artifact_index.py", "validate"], 180),
    ]
    if include_harness:
        plan.append(("veritas_harness_scorecard_fast", [sys.executable, "scripts\\veritas_harness_scorecard.py", "--fast", "--write", "--validate"], 240))
        plan.append(("model_quality_scorecard_after_harness", [sys.executable, "scripts\\model_quality_scorecard.py", "--write", "--write-md", "--validate"], 120))
    plan.extend([
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--validate"], 180),
        ("wf74_cron_duplication_audit", [sys.executable, "scripts\\wf74_cron_duplication_audit.py", "--write", "--validate"], 90),
        ("cron_control_packet", [sys.executable, "scripts\\cron_control_packet.py", "--write", "--validate"], 180),
    ])
    return plan


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "status": "blocked",
            "returncode": None,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout or ""),
            "stderr_tail": tail(exc.stderr or ""),
        }
    return {
        "name": name,
        "command": command,
        "status": "ok" if completed.returncode == 0 else "blocked",
        "returncode": completed.returncode,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(completed.stdout or ""),
        "stderr_tail": tail(completed.stderr or ""),
    }


def artifact_status(path: str) -> dict[str, Any]:
    full = ROOT / path
    data = as_dict(load_json_artifact(full))
    return {
        "path": path,
        "exists": full.exists(),
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def build_payload(steps: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = [step for step in steps if step.get("status") != "ok"]
    artifacts = [
        artifact_status("tmp/otel-ops-control.json"),
        artifact_status("tmp/otel-ops-window-summary.json"),
        artifact_status("tmp/otel-runtime-metadata-probe.json"),
        artifact_status("tmp/otel-tool-workflow-metadata.json"),
        artifact_status("tmp/otel-field-depth-limited-owner-packet.json"),
        artifact_status("tmp/changed-file-validator-router.json"),
        artifact_status("tmp/coding-outcome-ledger-current.json"),
        artifact_status("tmp/validator-timing-ledger.json"),
        artifact_status("tmp/coding-runtime-kpi-probe.json"),
        artifact_status("tmp/cron-spark-canary-monitor.json"),
        artifact_status("tmp/model-run-ledger-current.json"),
        artifact_status("tmp/token-usage-ledger-current.json"),
        artifact_status("tmp/model-learning-metadata-ledger.json"),
        artifact_status("tmp/otel-learning-loop.json"),
        artifact_status("tmp/finance-recommendation-correctness-ledger-current.json"),
        artifact_status("tmp/finance-response-quality-slice.json"),
        artifact_status("tmp/tier-ab-band-freshness-cron-guard.json"),
        artifact_status("tmp/model-quality-scorecard.json"),
        artifact_status("tmp/wf74-improvement-opportunity-queue.json"),
        artifact_status("tmp/improvement-ledger-current.json"),
        artifact_status("tmp/wf74-reflection-to-proposal-autopilot.json"),
        artifact_status("tmp/wf74-auto-patch-proposer.json"),
        artifact_status("tmp/owner-gated-action-review-queue.json"),
        artifact_status("tmp/wf74-cron-duplication-audit.json"),
        artifact_status("tmp/cron-control-packet.json"),
    ]
    model_run = as_dict(load_json_artifact(TMP / "model-run-ledger-current.json"))
    token_usage = as_dict(load_json_artifact(TMP / "token-usage-ledger-current.json"))
    learning_ledger = as_dict(load_json_artifact(TMP / "model-learning-metadata-ledger.json"))
    finance_correctness = as_dict(load_json_artifact(TMP / "finance-recommendation-correctness-ledger-current.json"))
    finance_response_quality = as_dict(load_json_artifact(TMP / "finance-response-quality-slice.json"))
    model_quality = as_dict(load_json_artifact(TMP / "model-quality-scorecard.json"))
    duplication_audit = as_dict(load_json_artifact(TMP / "wf74-cron-duplication-audit.json"))
    repair_conveyor = as_dict(load_json_artifact(TMP / "trade-grade-repair-conveyor.json"))
    tier_ab_guard = as_dict(load_json_artifact(TMP / "tier-ab-band-freshness-cron-guard.json"))
    model_summary = as_dict(model_run.get("summary"))
    token_usage_summary = as_dict(token_usage.get("summary"))
    finance_summary = as_dict(finance_correctness.get("summary"))
    finance_response_summary = as_dict(finance_response_quality.get("summary"))
    repair_summary = as_dict(repair_conveyor.get("summary"))
    tier_ab_summary = as_dict(tier_ab_guard.get("summary"))
    duplication_summary = as_dict(duplication_audit.get("summary"))
    otel_window_summary = as_dict(load_json_artifact(TMP / "otel-ops-window-summary.json"))
    otel_ops = as_dict(load_json_artifact(TMP / "otel-ops-control.json"))
    otel_field_depth = as_dict(load_json_artifact(TMP / "otel-field-depth-limited-owner-packet.json"))
    otel_runtime_probe = as_dict(load_json_artifact(TMP / "otel-runtime-metadata-probe.json"))
    otel_tool_workflow = as_dict(load_json_artifact(TMP / "otel-tool-workflow-metadata.json"))
    otel_learning_loop = as_dict(load_json_artifact(TMP / "otel-learning-loop.json"))
    coding_outcome = as_dict(load_json_artifact(TMP / "coding-outcome-ledger-current.json"))
    coding_runtime_probe = as_dict(load_json_artifact(TMP / "coding-runtime-kpi-probe.json"))
    opportunity_queue = as_dict(load_json_artifact(TMP / "wf74-improvement-opportunity-queue.json"))
    improvement_ledger = as_dict(load_json_artifact(TMP / "improvement-ledger-current.json"))
    proposal_autopilot = as_dict(load_json_artifact(TMP / "wf74-reflection-to-proposal-autopilot.json"))
    auto_patch_proposer = as_dict(load_json_artifact(TMP / "wf74-auto-patch-proposer.json"))
    owner_gated_queue = as_dict(load_json_artifact(TMP / "owner-gated-action-review-queue.json"))
    coding_runtime_kpis = as_dict(coding_runtime_probe.get("kpis"))
    coding_outcome_summary = as_dict(coding_outcome.get("ledger_summary"))
    opportunity_summary = as_dict(opportunity_queue.get("summary"))
    improvement_ledger_summary = as_dict(improvement_ledger.get("summary"))
    proposal_summary = as_dict(proposal_autopilot.get("summary"))
    auto_patch_summary = as_dict(auto_patch_proposer.get("summary"))
    owner_gated_summary = as_dict(owner_gated_queue.get("summary"))
    otel_windows = [row for row in otel_window_summary.get("windows", []) if isinstance(row, dict)]
    otel_drift = as_dict(otel_ops.get("drift"))
    otel_tool_workflow_summary = as_dict(otel_tool_workflow.get("summary"))
    otel_learning_summary = as_dict(otel_learning_loop.get("learning_summaries"))
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not blocked else "blocked",
        "posture": "scheduled_review_only_collection",
        "summary": {
            "steps_total": len(steps),
            "steps_ok": len(steps) - len(blocked),
            "steps_blocked": len(blocked),
            "model_run_rows": model_summary.get("row_count"),
            "model_attribution_coverage": model_summary.get("model_attribution_coverage"),
            "session_attribution_coverage": model_summary.get("session_attribution_coverage"),
            "token_usage_status": token_usage.get("status"),
            "token_usage_validation": as_dict(token_usage.get("validation")).get("status"),
            "token_usage_event_count": token_usage_summary.get("token_event_count"),
            "token_usage_total_tokens": token_usage_summary.get("total_tokens"),
            "token_usage_cron_event_count": token_usage_summary.get("cron_token_event_count"),
            "token_usage_implementation_event_count": token_usage_summary.get("implementation_token_event_count"),
            "token_usage_implementation_gap_count": token_usage_summary.get("implementation_token_gap_count"),
            "token_usage_pricing_status": token_usage_summary.get("pricing_status"),
            "learning_metadata_rows": as_dict(learning_ledger.get("summary")).get("row_count"),
            "learning_metadata_domains": as_dict(learning_ledger.get("summary")).get("by_domain"),
            "learning_metadata_privacy_scan": as_dict(learning_ledger.get("summary")).get("privacy_scan_status"),
            "learning_coding_outcome_rows": as_dict(learning_ledger.get("summary")).get("coding_outcome_rows"),
            "finance_correctness_rows": finance_summary.get("row_count"),
            "finance_correctness_blocked_rows": finance_summary.get("blocked_count"),
            "finance_response_quality_status": finance_response_quality.get("status"),
            "finance_response_quality_average_score": finance_response_summary.get("average_quality_score"),
            "finance_response_quality_blocked_archetypes": finance_response_summary.get("blocked_archetype_count"),
            "finance_response_quality_wf72_support_only": finance_response_summary.get("wf72_support_only_confirmed"),
            "finance_response_quality_sector_timing_warning": finance_response_summary.get("sector_timing_warning_available"),
            "finance_response_quality_section_coverage_status": finance_response_summary.get("section_coverage_status"),
            "finance_response_quality_technical_gap_count": finance_response_summary.get("technical_posture_missing_both_count"),
            "finance_response_quality_source_freshness_blocked_count": finance_response_summary.get("source_freshness_blocked_count"),
            "finance_response_quality_source_open_blocked_count": finance_response_summary.get("source_open_blocked_count"),
            "finance_response_quality_negative_canary_pass_count": finance_response_summary.get("negative_canary_pass_count"),
            "finance_response_quality_remediation_tracks_needing_repair": finance_response_summary.get("remediation_tracks_needing_repair"),
            "finance_repair_conveyor_status": repair_conveyor.get("status"),
            "finance_repair_conveyor_pm_blocker_scope": repair_summary.get("pm_blocker_scope"),
            "finance_repair_conveyor_total_row_count": repair_summary.get("total_repair_conveyor_row_count"),
            "finance_repair_conveyor_domain_repair_item_count": repair_summary.get("finance_domain_repair_item_count"),
            "finance_repair_conveyor_owner_gate_count": repair_summary.get("owner_finance_gate_count"),
            "finance_repair_conveyor_domain_blocker_count": repair_summary.get("finance_domain_blocker_count"),
            "finance_repair_conveyor_tier_a_b_missing_decision_grade_band_count": repair_summary.get("tier_a_b_missing_decision_grade_band_count"),
            "finance_repair_conveyor_tier_b_missing_decision_grade_band_count": repair_summary.get("tier_b_missing_decision_grade_band_count"),
            "tier_a_b_band_cron_guard_status": tier_ab_guard.get("status"),
            "tier_a_b_band_cron_guard_validation": as_dict(tier_ab_guard.get("validation")).get("status"),
            "tier_a_b_complete_and_current_band_count": tier_ab_summary.get("complete_and_current_count"),
            "tier_a_b_stale_complete_band_context_count": tier_ab_summary.get("stale_complete_band_context_count"),
            "tier_a_b_cron_contracts_ok": tier_ab_summary.get("cron_contracts_ok"),
            "finance_repair_conveyor_implementation_blocker_count": repair_summary.get("implementation_blocker_count"),
            "finance_repair_conveyor_control_plane_blocker_count": repair_summary.get("control_plane_blocker_count"),
            "wf74_active_tracks": model_quality.get("active_tracks"),
            "wf74_validation_status": as_dict(model_quality.get("validation")).get("status"),
            "otel_window_summary_status": otel_window_summary.get("status"),
            "otel_drift_status": otel_drift.get("status"),
            "otel_daily_warning_or_error_count": otel_drift.get("daily_warning_or_error_count"),
            "otel_daily_vs_weekly_event_rate_ratio": otel_drift.get("daily_vs_weekly_event_rate_ratio"),
            "otel_field_depth_packet_status": otel_field_depth.get("status"),
            "otel_runtime_probe_status": otel_runtime_probe.get("status"),
            "otel_runtime_metadata_observed": as_dict(otel_runtime_probe.get("summary")).get("runtime_metadata_observed"),
            "otel_runtime_allowed_field_count": as_dict(otel_runtime_probe.get("summary")).get("allowed_field_count"),
            "otel_tool_workflow_metadata_status": otel_tool_workflow.get("status"),
            "otel_tool_workflow_metadata_rows": otel_tool_workflow_summary.get("row_count"),
            "otel_tool_workflow_unique_tool_count": otel_tool_workflow_summary.get("unique_tool_count"),
            "otel_tool_workflow_failed_or_blocked_count": otel_tool_workflow_summary.get("failed_or_blocked_count"),
            "otel_tool_workflow_session_attributed_count": otel_tool_workflow_summary.get("session_attributed_count"),
            "otel_tool_workflow_privacy_scan": as_dict(otel_tool_workflow.get("privacy_scan")).get("status"),
            "otel_learning_loop_status": otel_learning_loop.get("status"),
            "otel_learning_loop_validation": as_dict(otel_learning_loop.get("validation")).get("status"),
            "otel_learning_loop_privacy_scan": as_dict(otel_learning_loop.get("privacy_scan")).get("status"),
            "otel_learning_loop_recommendation_count": len([row for row in (otel_learning_loop.get("recommendations") or []) if isinstance(row, dict)]),
            "otel_learning_loop_token_coverage_ratio": as_dict(otel_learning_summary.get("token_cost")).get("token_coverage_ratio"),
            "otel_learning_loop_cost_coverage_ratio": as_dict(otel_learning_summary.get("token_cost")).get("cost_coverage_ratio"),
            "coding_runtime_probe_status": coding_runtime_probe.get("status"),
            "coding_runtime_first_pass_clean": coding_runtime_kpis.get("first_pass_validation_clean"),
            "coding_runtime_rework_required": coding_runtime_kpis.get("rework_required"),
            "coding_runtime_validator_elapsed_seconds": coding_runtime_kpis.get("validator_elapsed_seconds"),
            "coding_runtime_failure_buckets": coding_runtime_kpis.get("failure_bucket_counts"),
            "coding_outcome_ledger_status": coding_outcome.get("status"),
            "coding_outcome_ledger_rows": coding_outcome_summary.get("ledger_row_count"),
            "coding_outcome_session_attributed_count": coding_outcome_summary.get("session_attributed_count"),
            "coding_outcome_model_attributed_count": coding_outcome_summary.get("model_attributed_count"),
            "coding_outcome_validator_proxy_passed_count": coding_outcome_summary.get("validator_proxy_passed_count"),
            "coding_outcome_total_retry_count": coding_outcome_summary.get("total_retry_count"),
            "improvement_opportunity_queue_status": opportunity_queue.get("status"),
            "improvement_opportunity_count": opportunity_summary.get("opportunity_count"),
            "improvement_high_priority_count": opportunity_summary.get("high_priority_count"),
            "improvement_top_opportunity_title": opportunity_summary.get("top_opportunity_title"),
            "improvement_ledger_status": improvement_ledger.get("status"),
            "improvement_ledger_validation": as_dict(improvement_ledger.get("validation")).get("status"),
            "improvement_ledger_rows": improvement_ledger_summary.get("ledger_row_count"),
            "improvement_ledger_appended_event_count": improvement_ledger_summary.get("appended_event_count"),
            "improvement_ledger_latest_open_count": improvement_ledger_summary.get("latest_open_count"),
            "improvement_ledger_high_priority_open_count": improvement_ledger_summary.get("high_priority_open_count"),
            "improvement_ledger_overdue_open_count": improvement_ledger_summary.get("overdue_open_count"),
            "improvement_ledger_due_soon_open_count": improvement_ledger_summary.get("due_soon_open_count"),
            "improvement_ledger_high_priority_overdue_open_count": improvement_ledger_summary.get("high_priority_overdue_open_count"),
            "improvement_ledger_escalation_level": improvement_ledger_summary.get("escalation_level"),
            "improvement_ledger_top_improvement_title": improvement_ledger_summary.get("top_improvement_title"),
            "improvement_ledger_top_improvement_age_hours": improvement_ledger_summary.get("top_improvement_age_hours"),
            "improvement_ledger_top_improvement_sla_status": improvement_ledger_summary.get("top_improvement_sla_status"),
            "reflection_proposal_autopilot_status": proposal_autopilot.get("status"),
            "reflection_proposal_count": proposal_summary.get("proposal_count"),
            "reflection_owner_decision_required_count": proposal_summary.get("owner_decision_required_count"),
            "reflection_auto_apply_count": proposal_summary.get("auto_apply_count"),
            "auto_patch_proposer_status": auto_patch_proposer.get("status"),
            "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
            "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count"),
            "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
            "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
            "auto_patch_auto_apply_candidate_count": auto_patch_summary.get("auto_apply_candidate_count"),
            "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
            "owner_gated_review_status": owner_gated_queue.get("status"),
            "owner_gated_review_validation": as_dict(owner_gated_queue.get("validation")).get("status"),
            "owner_gated_item_count": owner_gated_summary.get("item_count"),
            "owner_gated_decision_required_count": owner_gated_summary.get("owner_decision_required_count"),
            "owner_gated_top_gate": owner_gated_summary.get("top_gate"),
            "owner_gated_top_title": owner_gated_summary.get("top_title"),
            "otel_window_count": len(otel_windows),
            "otel_window_ids": [row.get("window_id") for row in otel_windows],
            "wf74_duplicate_cron_collectors": duplication_summary.get("recurring_component_collectors_outside_owner_count"),
            "wf74_one_shot_component_reminders": duplication_summary.get("one_shot_component_collectors_outside_owner_count"),
        },
        "steps": steps,
        "artifacts": artifacts,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "rsi_observation": {
            "schema": "wf74.rsi_observation.v1",
            "source": "wf74_model_quality_collection_cron_runner",
            "lesson_type": "automation_candidate",
            "owner_surface": "WF74 / cron-automation-manager / future session packet",
            "what_changed": "WF74 scheduled collection refreshed model/run, finance-correctness, scorecard, artifact-index, harness, cron, and duplication-audit proof.",
            "warnings_or_blockers": [
                *([] if model_summary.get("session_attribution_coverage") else ["session attribution coverage missing"]),
                *([] if model_summary.get("cost_rows") else ["cost fields unavailable"]),
                *([] if duplication_summary.get("expected_owner_ok") is not False else ["WF74 cron owner duplication risk"]),
                *([] if not duplication_summary.get("one_shot_component_collectors_outside_owner_count") else ["one-shot WF74 component reminder exists outside owner job"]),
            ],
            "future_session_lesson": "Use this runner as the single scheduled WF74 collection owner; do not schedule component ledgers separately.",
            "recommended_destination": "memory/2026-06-08.md if new residue appears; Skill Workshop only for repeated procedure drift.",
            "actionability": "monitor",
        },
        "next_safe_action": (
            "Stamp session_id/run_id/model_path at cron/helper/PM producers; keep WF55 outcome grading gated."
        ),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    if as_dict(payload.get("summary")).get("steps_blocked", 0):
        findings.append({"severity": "critical", "detail": "one or more collection steps blocked"})
    if as_dict(payload.get("summary")).get("finance_response_quality_status") not in {None, "ok"}:
        findings.append({"severity": "critical", "detail": "finance response quality slice is not ok"})
    if int(as_dict(payload.get("summary")).get("finance_repair_conveyor_implementation_blocker_count") or 0):
        findings.append({"severity": "critical", "detail": "finance repair conveyor reported implementation blockers"})
    if int(as_dict(payload.get("summary")).get("finance_repair_conveyor_control_plane_blocker_count") or 0):
        findings.append({"severity": "critical", "detail": "finance repair conveyor reported control-plane blockers"})
    if as_dict(payload.get("summary")).get("tier_a_b_band_cron_guard_validation") == "error":
        findings.append({"severity": "critical", "detail": "Tier A/B band freshness cron guard failed"})
    if as_dict(payload.get("summary")).get("token_usage_validation") == "critical":
        findings.append({"severity": "critical", "detail": "token usage ledger validation is critical"})
    if int(as_dict(payload.get("summary")).get("token_usage_event_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "token usage ledger has no token-bearing rows"})
    if int(as_dict(payload.get("summary")).get("tier_a_b_stale_complete_band_context_count") or 0):
        findings.append({"severity": "critical", "detail": "Tier A/B complete band context is stale"})
    for artifact in payload.get("artifacts", []):
        if not artifact.get("exists"):
            findings.append({"severity": "critical", "detail": f"missing artifact: {artifact.get('path')}"})
    if as_dict(payload.get("summary")).get("otel_window_count") != 5:
        findings.append({"severity": "critical", "detail": "OTEL multi-window summary must expose five windows"})
    if as_dict(payload.get("summary")).get("otel_field_depth_packet_status") != "owner_decision_required":
        findings.append({"severity": "critical", "detail": "OTEL field-depth packet must remain owner-gated"})
    if int(as_dict(payload.get("summary")).get("coding_outcome_ledger_rows") or 0) <= 0:
        findings.append({"severity": "critical", "detail": "coding outcome ledger must provide per-lane rows"})
    if as_dict(payload.get("summary")).get("improvement_opportunity_queue_status") not in {None, "ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 improvement opportunity queue is not ok"})
    if as_dict(payload.get("summary")).get("improvement_ledger_validation") != "ok":
        findings.append({"severity": "critical", "detail": "improvement ledger validation is not ok"})
    if int(as_dict(payload.get("summary")).get("improvement_ledger_latest_open_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "improvement ledger has no open carry-forward rows"})
    if int(as_dict(payload.get("summary")).get("improvement_ledger_high_priority_overdue_open_count") or 0):
        findings.append({"severity": "warning", "detail": "improvement ledger has overdue high-priority carry-forward rows"})
    if int(as_dict(payload.get("summary")).get("reflection_proposal_count") or 0) <= 0:
        findings.append({"severity": "critical", "detail": "WF74 proposal autopilot produced no proposals"})
    if int(as_dict(payload.get("summary")).get("reflection_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 proposal autopilot must not auto-apply"})
    if as_dict(payload.get("summary")).get("auto_patch_proposer_status") not in {None, "ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 auto-patch proposer is not ok"})
    if int(as_dict(payload.get("summary")).get("auto_patch_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 auto-patch proposer must not auto-apply"})
    if as_dict(payload.get("summary")).get("owner_gated_review_validation") != "ok":
        findings.append({"severity": "critical", "detail": "owner-gated action review queue validation is not ok"})
    if int(as_dict(payload.get("summary")).get("owner_gated_decision_required_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "owner-gated action review queue has no decision items"})
    if as_dict(payload.get("summary")).get("wf74_duplicate_cron_collectors") not in {0, None}:
        findings.append({"severity": "critical", "detail": "duplicate WF74 cron component collectors detected"})
    if as_dict(payload.get("summary")).get("wf74_one_shot_component_reminders") not in {0, None}:
        findings.append({"severity": "warning", "detail": "one-shot WF74 component reminder exists outside owner job"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Model Quality Collection Cron Runner",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Steps ok/blocked: {summary.get('steps_ok')} / {summary.get('steps_blocked')}",
        f"- Model attribution coverage: {summary.get('model_attribution_coverage')}",
        f"- Session attribution coverage: {summary.get('session_attribution_coverage')}",
        f"- Token usage: {summary.get('token_usage_total_tokens')} tokens / events {summary.get('token_usage_event_count')} / pricing {summary.get('token_usage_pricing_status')}",
        f"- Finance correctness rows: {summary.get('finance_correctness_rows')}",
        f"- Finance response quality: {summary.get('finance_response_quality_status')} ({summary.get('finance_response_quality_average_score')})",
        f"- OTEL learning loop: {summary.get('otel_learning_loop_status')} / privacy {summary.get('otel_learning_loop_privacy_scan')} / recs {summary.get('otel_learning_loop_recommendation_count')}",
        f"- Improvement ledger: {summary.get('improvement_ledger_status')} / rows {summary.get('improvement_ledger_rows')} / open {summary.get('improvement_ledger_latest_open_count')}",
        f"- Improvement SLA: overdue {summary.get('improvement_ledger_overdue_open_count')} / due soon {summary.get('improvement_ledger_due_soon_open_count')} / escalation {summary.get('improvement_ledger_escalation_level')}",
        f"- Owner-gated decisions: {summary.get('owner_gated_decision_required_count')} / top {summary.get('owner_gated_top_gate')}: {summary.get('owner_gated_top_title')}",
        f"- WF74 active tracks: {', '.join(summary.get('wf74_active_tracks') or [])}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run WF74 model-quality collection cron digest")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--include-harness", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    steps: list[dict[str, Any]] = []
    for name, command, timeout in command_plan(args.include_harness):
        step = run_step(name, command, timeout)
        steps.append(step)
        if step["status"] != "ok":
            break

    payload = build_payload(steps)
    validation = validate(payload)
    payload["validation"] = validation
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))

    if not args.quiet:
        summary = as_dict(payload.get("summary"))
        print(
            f"status={payload['status']} validation={validation['status']} "
            f"steps_ok={summary.get('steps_ok')} steps_blocked={summary.get('steps_blocked')} "
            f"model_attr={summary.get('model_attribution_coverage')} finance_rows={summary.get('finance_correctness_rows')}"
        )
        for finding in validation["findings"]:
            print(f"  [{finding['severity']}] {finding['detail']}")

    if args.validate and validation["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
