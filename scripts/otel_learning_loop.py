#!/usr/bin/env python3
"""Build the OTEL metadata learning loop packet.

This turns local-only OTEL and proof-artifact metadata into bounded
recommendations. It deliberately avoids raw prompts, responses, system prompts,
tool inputs/outputs, headers, secrets, and raw command output bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "otel-learning-loop.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.otel_learning_loop.v1"

OTEL_CONTROL = TMP / "otel-ops-control.json"
OTEL_WINDOWS = TMP / "otel-ops-window-summary.json"
OTEL_TOOL_WORKFLOW = TMP / "otel-tool-workflow-metadata.json"
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
VALIDATOR_TIMING = TMP / "validator-timing-ledger.json"
CODING_RUNTIME = TMP / "coding-runtime-kpi-probe.json"
CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
CRON_SIGNAL_SCORECARD = TMP / "cron-signal-scorecard.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
WF87_SHADOW_OUTCOME = TMP / "wf87-shadow-outcome-scorecard.json"
WF87_READINESS_ROLLUP = TMP / "wf87-v2-readiness-rollup.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "content_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_KEY_MARKERS = (
    "prompt",
    "message_content",
    "completion",
    "response_text",
    "tool_input",
    "tool_output",
    "tool_payload",
    "system_prompt",
    "authorization",
    "bearer",
    "api_key",
    "oauth",
    "access_token",
    "refresh_token",
    "secret",
    "credential",
    "password",
    "cookie",
    "header",
)

FORBIDDEN_VALUE_MARKERS = (
    "sk-",
    "Bearer ",
    "Authorization:",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "api_key",
    "oauth_token",
    "access_token",
    "refresh_token",
    "system_prompt",
)


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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_duration_ms(value: Any) -> float | None:
    """Parse a measured duration without treating absence as zero latency."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def model_row_scoring_eligible(row: dict[str, Any]) -> bool:
    """Return whether a model row may influence performance economics.

    Lane-register rows must carry the explicit post-cutover eligibility flag.
    Non-lane cron/runtime producers retain their independently sourced
    operational semantics, including legacy artifacts written before the flag
    existed.
    """
    attribution = as_dict(row.get("attribution"))
    if attribution.get("model_applicable") is not True:
        return False
    if row.get("producer") == "concurrent_lane_manager":
        return attribution.get("telemetry_eligible") is True
    return attribution.get("telemetry_eligible") is not False


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def redact_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if any(marker.lower() in value.lower() for marker in FORBIDDEN_VALUE_MARKERS):
        return "[REDACTED]"
    return value


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(marker in lowered for marker in FORBIDDEN_KEY_MARKERS):
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key_text}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker.lower() in lowered for marker in FORBIDDEN_VALUE_MARKERS):
            findings.append(f"forbidden_value:{path}")
    return findings


def model_cost_summary(model_run: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in as_list(model_run.get("rows")) if isinstance(row, dict)]
    model_rows = [row for row in rows if model_row_scoring_eligible(row)]
    uncredited_lane_rows = [
        row for row in rows
        if row.get("producer") == "concurrent_lane_manager"
        and bool(row.get("model_path") or as_dict(row.get("attribution")).get("model_present"))
        and not model_row_scoring_eligible(row)
    ]
    token_rows = [row for row in model_rows if row.get("tokens") is not None]
    cost_rows = [row for row in model_rows if row.get("cost") is not None]
    durations = [duration for row in model_rows if (duration := as_duration_ms(row.get("duration_ms"))) is not None]
    by_model: dict[str, dict[str, Any]] = {}
    for row in model_rows:
        model = str(row.get("model_path") or row.get("model_provider") or "unknown")
        bucket = by_model.setdefault(model, {
            "count": 0,
            "duration_covered_rows": 0,
            "duration_ms_total": 0.0,
            "tokens_rows": 0,
            "cost_rows": 0,
            "failure_rows": 0,
        })
        bucket["count"] += 1
        duration = as_duration_ms(row.get("duration_ms"))
        if duration is not None:
            bucket["duration_covered_rows"] += 1
            bucket["duration_ms_total"] += duration
        if row.get("tokens") is not None:
            bucket["tokens_rows"] += 1
        if row.get("cost") is not None:
            bucket["cost_rows"] += 1
        if str(row.get("status") or "").lower() not in {"ok", "complete", "success", ""}:
            bucket["failure_rows"] += 1
    for bucket in by_model.values():
        covered = int(bucket["duration_covered_rows"])
        bucket["avg_duration_ms"] = round(bucket["duration_ms_total"] / covered, 3) if covered else None
        del bucket["duration_ms_total"]
    return {
        "model_applicable_rows": len(model_rows),
        "model_performance_eligible_rows": len(model_rows),
        "uncredited_lane_audit_rows": len(uncredited_lane_rows),
        "token_coverage_rows": len(token_rows),
        "token_coverage_ratio": round(len(token_rows) / len(model_rows), 4) if model_rows else None,
        "cost_coverage_rows": len(cost_rows),
        "cost_coverage_ratio": round(len(cost_rows) / len(model_rows), 4) if model_rows else None,
        "avg_duration_ms": round(sum(durations) / len(durations), 3) if durations else None,
        "by_model": dict(sorted(by_model.items())),
    }


def tool_latency_summary(tool_workflow: dict[str, Any], validator_timing: dict[str, Any], coding_runtime: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in as_list(tool_workflow.get("rows")) if isinstance(row, dict)]
    durations = [row for row in rows if as_duration_ms(row.get("duration_ms")) is not None]
    failures = [row for row in rows if str(row.get("failure_category") or "none") != "none"]
    by_tool: dict[str, dict[str, Any]] = {}
    for row in durations:
        tool = str(row.get("tool_name") or "unknown")
        bucket = by_tool.setdefault(tool, {"count": 0, "duration_ms_total": 0.0, "failure_rows": 0})
        bucket["count"] += 1
        duration = as_duration_ms(row.get("duration_ms"))
        if duration is None:
            continue
        bucket["duration_ms_total"] += duration
        if str(row.get("failure_category") or "none") != "none":
            bucket["failure_rows"] += 1
    for bucket in by_tool.values():
        count = max(int(bucket["count"]), 1)
        bucket["avg_duration_ms"] = round(bucket["duration_ms_total"] / count, 3)
        del bucket["duration_ms_total"]
    slow_tools = sorted(by_tool.items(), key=lambda item: item[1].get("avg_duration_ms") or 0, reverse=True)[:10]
    timing_summary = as_dict(validator_timing.get("summary"))
    coding_kpis = as_dict(coding_runtime.get("kpis"))
    return {
        "tool_rows": len(rows),
        "duration_covered_rows": len(durations),
        "failure_rows": len(failures),
        "failure_categories": dict(Counter(str(row.get("failure_category") or "none") for row in rows)),
        "slowest_tools": [{"tool_name": name, **bucket} for name, bucket in slow_tools],
        "validator_elapsed_seconds": timing_summary.get("elapsed_seconds"),
        "validator_target_seconds": timing_summary.get("target_seconds"),
        "validator_slow": timing_summary.get("slow"),
        "coding_first_pass_clean": coding_kpis.get("first_pass_clean"),
        "coding_rework_required": coding_kpis.get("rework_required"),
    }


def otel_health_summary(otel: dict[str, Any], windows: dict[str, Any]) -> dict[str, Any]:
    drift = as_dict(otel.get("drift"))
    summary = as_dict(otel.get("summary"))
    trend = as_dict(windows.get("trend_indicators"))
    return {
        "collector_health": as_dict(otel.get("collector_health")).get("status"),
        "collector_loopback": as_dict(otel.get("collector_config")).get("binds_loopback_4318"),
        "status": otel.get("status"),
        "daily_event_count": summary.get("event_count"),
        "daily_warning_or_error_count": drift.get("daily_warning_or_error_count"),
        "daily_events_per_hour": drift.get("daily_events_per_hour"),
        "weekly_events_per_hour": drift.get("weekly_events_per_hour"),
        "daily_vs_weekly_event_rate_ratio": drift.get("daily_vs_weekly_event_rate_ratio"),
        "drift_status": drift.get("status"),
        "drift_reasons": drift.get("drift_reasons"),
        "weekly_warning_or_error_count": trend.get("weekly_warning_or_error_count"),
    }


def operational_friction_summary(
    cron_signal: dict[str, Any],
    workflow_advancement: dict[str, Any],
    wf87_shadow: dict[str, Any],
    wf87_rollup: dict[str, Any],
) -> dict[str, Any]:
    cron_scorecard = as_dict(cron_signal.get("scorecard"))
    workflow_summary = as_dict(workflow_advancement.get("summary"))
    shadow_summary = as_dict(wf87_shadow.get("summary"))
    phase = as_dict(wf87_rollup.get("phase_readiness"))
    blocker_taxonomy = as_dict(wf87_rollup.get("blocker_taxonomy"))
    attention_signals = [
        {
            "source": row.get("source"),
            "artifact": row.get("artifact"),
            "signal_class": row.get("signal_class"),
            "status": row.get("status"),
            "reason": row.get("reason"),
            "next_action": row.get("next_action"),
        }
        for row in as_list(cron_signal.get("signals"))
        if isinstance(row, dict) and row.get("attention") == "requires_main_attention"
    ][:8]
    blocked_workflows = [
        {
            "workflow_id": row.get("workflow_id"),
            "status": row.get("status"),
            "signal": row.get("signal"),
            "blockers": row.get("blockers"),
            "next_action": row.get("next_action"),
        }
        for row in as_list(workflow_advancement.get("signals"))
        if isinstance(row, dict) and row.get("signal") == "blocked"
    ][:8]
    return {
        "cron": {
            "blocked_count": cron_scorecard.get("blocked_count"),
            "requires_attention_count": cron_scorecard.get("requires_attention_count"),
            "enabled_job_count": cron_scorecard.get("enabled_job_count"),
            "attention_signals": attention_signals,
        },
        "workflow_advancement": {
            "blocked_count": workflow_summary.get("blocked_count"),
            "owner_needed_count": workflow_summary.get("owner_needed_count"),
            "cron_update_recommended": workflow_summary.get("cron_update_recommended"),
            "blocked_workflows": blocked_workflows,
        },
        "wf87_shadow_outcomes": {
            "decision_count": shadow_summary.get("decision_count"),
            "scoreable_decision_count": shadow_summary.get("scoreable_decision_count"),
            "pending_regular_session_followup_count": shadow_summary.get("pending_regular_session_followup_count"),
            "stale_pending_followup_count": shadow_summary.get("stale_pending_followup_count"),
            "decision_quality_claim_allowed_now": shadow_summary.get("decision_quality_claim_allowed_now"),
            "model_performance_claim_allowed_now": shadow_summary.get("model_performance_claim_allowed_now"),
        },
        "wf87_readiness": {
            "phase_a_runtime_gates_clean": phase.get("phase_a_runtime_gates_clean"),
            "phase_b_assisted_round_trip_ready": phase.get("phase_b_assisted_round_trip_ready"),
            "phase_c_autonomous_paper_buy_ready": phase.get("phase_c_autonomous_paper_buy_ready"),
            "blocker_counts": as_dict(blocker_taxonomy.get("counts")),
            "binding_blockers": blocker_taxonomy.get("binding_blockers"),
        },
    }


def build_recommendations(
    cost: dict[str, Any],
    latency: dict[str, Any],
    health: dict[str, Any],
    queue: dict[str, Any],
    friction: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    token_ratio = cost.get("token_coverage_ratio")
    cost_ratio = cost.get("cost_coverage_ratio")
    if token_ratio is None or token_ratio < 0.8 or cost_ratio is None or cost_ratio < 0.8:
        recommendations.append({
            "id": "token_cost_metadata_depth",
            "severity": "warning",
            "decision": "prepare_owner_gated_metadata_depth_patch",
            "rationale": "Token/cost coverage is too low for reliable model-routing economics.",
            "blocked_capture": ["raw prompts", "raw responses", "tool payloads", "system prompts", "secrets", "headers"],
            "next_action": "If approved later, add local-only token/cost metadata capture with redaction validation and rollback.",
        })
    if as_float(cost.get("uncredited_lane_audit_rows")) > 0:
        recommendations.append({
            "id": "usage_source_reverification_required",
            "severity": "warning",
            "decision": "block_model_economics_claims_for_uncredited_lanes",
            "rationale": "One or more completed model lanes are audit-visible but lack an independently reverified source-to-lane usage join.",
            "next_action": "Repair the protected dispatch/source correlation path; do not use these lanes for performance, cost, latency, reliability, or savings comparisons.",
        })
    if latency.get("validator_slow") or as_float(latency.get("validator_elapsed_seconds")) > as_float(latency.get("validator_target_seconds"), 999999):
        recommendations.append({
            "id": "validator_latency_optimization",
            "severity": "info",
            "decision": "optimize_slowest_validators_or_changed_only_modes",
            "rationale": "Validator timing is above target or marked slow.",
            "next_action": "Use slowest tool rows and validator timing ledger to propose changed-only/background routes.",
        })
    if health.get("drift_status") != "ok" or as_float(health.get("daily_warning_or_error_count")) > 0:
        recommendations.append({
            "id": "otel_drift_review",
            "severity": "warning",
            "decision": "review_operational_drift_before_expansion",
            "rationale": "OTEL drift or warning/error counts are not clean.",
            "next_action": "Keep collector settings unchanged and inspect recent workflow volume.",
        })
    if as_dict(queue.get("summary")).get("high_priority_count"):
        recommendations.append({
            "id": "wf74_queue_followup",
            "severity": "info",
            "decision": "route_existing_wf74_opportunities",
            "rationale": "WF74 opportunity queue has high-priority items that can use metadata evidence.",
            "next_action": "Use learning-loop packet as support evidence for repair proposals, not auto-apply authority.",
        })
    cron = as_dict(friction.get("cron"))
    if as_float(cron.get("blocked_count")) or as_float(cron.get("requires_attention_count")):
        recommendations.append({
            "id": "cron_signal_learning_input",
            "severity": "warning",
            "decision": "route_cron_blockers_into_migration_plan",
            "rationale": "Cron blocked/attention signals are now first-class learning-loop inputs instead of standalone freshness noise.",
            "next_action": "Produce a dry-run migration plan with contract validation, rollback, and post-change freshness proof before mutating live schedules.",
        })
    workflow = as_dict(friction.get("workflow_advancement"))
    if as_float(workflow.get("blocked_count")) or workflow.get("cron_update_recommended"):
        recommendations.append({
            "id": "workflow_advancement_learning_input",
            "severity": "warning",
            "decision": "route_workflow_blockers_into_followup_queue",
            "rationale": "Workflow advancement blockers should create implementation or owner-decision follow-ups, not disappear after a status packet.",
            "next_action": "Rank blocked workflows in the WF74 opportunity queue and open narrow lanes only when write surfaces are clear.",
        })
    shadow = as_dict(friction.get("wf87_shadow_outcomes"))
    if as_float(shadow.get("pending_regular_session_followup_count")) or shadow.get("decision_quality_claim_allowed_now") is False:
        recommendations.append({
            "id": "wf87_outcome_measurement_backlog",
            "severity": "info",
            "decision": "keep_shadow_outcomes_as_measurement_backlog",
            "rationale": "WF87 has shadow outcome data, but low scoreable follow-up means it can calibrate only, not claim decision quality.",
            "next_action": "Keep collecting regular-session follow-up observations and block performance/execution claims until thresholds are met.",
        })
    recommendations.append({
        "id": "content_capture_boundary",
        "severity": "policy",
        "decision": "keep_raw_content_capture_blocked",
        "rationale": "Learning-loop value is mostly available from metadata; raw content capture creates unnecessary privacy and authority risk.",
        "next_action": "Use targeted, owner-approved, redacted review packets if content review is ever needed.",
    })
    return recommendations


def build_carry_forward_contract(
    cost: dict[str, Any],
    health: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    warning_recommendations = [
        row for row in recommendations
        if as_dict(row).get("severity") in {"warning", "policy"}
    ]
    return {
        "status": "attention" if warning_recommendations else "ok",
        "purpose": "Make OTEL learning-loop state explicit in future-session, startup, status, and evening alert surfaces.",
        "stale_after_hours": 24,
        "required_source_packets": [
            rel(OTEL_CONTROL),
            rel(OTEL_WINDOWS),
            rel(OTEL_TOOL_WORKFLOW),
            rel(MODEL_RUN_LEDGER),
            rel(WF74_OPPORTUNITY_QUEUE),
        ],
        "session_boot_order": [
            "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            "python scripts\\otel_learning_loop.py --write --write-md --validate",
            "python scripts\\wf74_improvement_opportunity_queue.py --write --validate",
            "python scripts\\wf74_decision_docket.py --write --write-md --validate",
            "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
        ],
        "must_surface_in": [
            "tmp/future-session-enhancement-packet.json",
            "tmp/startup-brief-packet.json",
            "tmp/veritas-status-card.json",
            "tmp/wf74-learning-loop-telegram-digest.json",
        ],
        "carry_forward_fields": {
            "collector_health": health.get("collector_health"),
            "drift_status": health.get("drift_status"),
            "token_coverage_ratio": cost.get("token_coverage_ratio"),
            "cost_coverage_ratio": cost.get("cost_coverage_ratio"),
            "recommendation_count": len(recommendations),
            "warning_recommendation_count": len(warning_recommendations),
        },
        "next_safe_action": (
            "Surface this packet in startup/status/evening digest; route implementation through WF74/PM only."
        ),
    }


def build_auto_implementation_router(recommendations: list[dict[str, Any]], queue: dict[str, Any]) -> dict[str, Any]:
    queue_summary = as_dict(queue.get("summary"))
    blocked_actions = [
        "direct code mutation from OTEL signals alone",
        "Skill Workshop apply/install/approval",
        "collector/runtime/cron config mutation",
        "finance canon, portfolio, cash, sizing, risk, paper, live, account, or external action",
        "owner approval inference",
    ]
    return {
        "status": "gated_auto_route_no_auto_apply" if recommendations else "monitor_only_no_auto_apply",
        "auto_apply_allowed": False,
        "safe_chain": [
            "OTEL metadata",
            "WF74 opportunity queue",
            "WF74 decision docket",
            "WF74 auto-patch proposer",
            "PM implementation job/router",
            "lane register lease",
            "main-session verification",
            "closeout/front-door refresh",
        ],
        "automatic_actions_allowed_now": [
            "refresh proof artifacts",
            "rank and dedupe opportunities",
            "generate patch/skill/owner-decision plans",
            "route proof-safe PM work with explicit lane contracts",
            "send review-only evening alert context",
        ],
        "automatic_actions_blocked": blocked_actions,
        "blocked_actions": blocked_actions,
        "pm_queue_signal": {
            "opportunity_count": queue_summary.get("opportunity_count"),
            "high_priority_count": queue_summary.get("high_priority_count"),
            "top_opportunity_title": queue_summary.get("top_opportunity_title"),
        },
        "next_safe_action": (
            "Use WF74 auto-patch and decision docket as the implementation router; auto-apply remains zero."
        ),
    }


def build_parallel_execution_plan() -> list[dict[str, Any]]:
    return [
        {
            "stream": "A",
            "title": "Telemetry depth and redaction",
            "owner": "OTEL/WF74",
            "state": "metadata_ready_owner_gated_depth_for_runtime_capture",
            "target": "token/cost/latency coverage without raw content capture",
            "proof": "python scripts\\otel_learning_loop.py --write --write-md --validate",
        },
        {
            "stream": "B",
            "title": "Carry-forward and session pickup",
            "owner": "startup/status/future-session packets",
            "state": "implemented_by_packet_surface",
            "target": "OTEL state visible to new sessions and shallow status",
            "proof": "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
        },
        {
            "stream": "C",
            "title": "WF74 improvement routing",
            "owner": "WF74 docket and auto-patch proposer",
            "state": "gated_auto_route_no_auto_apply",
            "target": "improvement opportunities become explicit action states",
            "proof": "python scripts\\wf74_decision_docket.py --write --write-md --validate",
        },
        {
            "stream": "D",
            "title": "Cron and stage-SLA learning input",
            "owner": "cron control and WF74 migration routing",
            "state": "review_only_contract_proof",
            "target": "cron SLA friction becomes ranked follow-up, not chat residue",
            "proof": "python scripts\\cron_control_packet.py --write --validate",
        },
        {
            "stream": "E",
            "title": "Evening alert and learning review",
            "owner": "WF74 Telegram digest",
            "state": "review_notification_integrated",
            "target": "Randall gets OTEL carry-forward and improvement status in evening alert",
            "proof": "python scripts\\wf74_learning_loop_telegram_digest.py --write --validate --force",
        },
    ]


def build_payload() -> dict[str, Any]:
    otel = as_dict(load_json_artifact(OTEL_CONTROL))
    windows = as_dict(load_json_artifact(OTEL_WINDOWS))
    tool_workflow = as_dict(load_json_artifact(OTEL_TOOL_WORKFLOW))
    model_run = as_dict(load_json_artifact(MODEL_RUN_LEDGER))
    learning = as_dict(load_json_artifact(MODEL_LEARNING_LEDGER))
    validator_timing = as_dict(load_json_artifact(VALIDATOR_TIMING))
    coding_runtime = as_dict(load_json_artifact(CODING_RUNTIME))
    changed_router = as_dict(load_json_artifact(CHANGED_FILE_ROUTER))
    queue = as_dict(load_json_artifact(WF74_OPPORTUNITY_QUEUE))
    cron_signal = as_dict(load_json_artifact(CRON_SIGNAL_SCORECARD))
    workflow_advancement = as_dict(load_json_artifact(WORKFLOW_ADVANCEMENT))
    wf87_shadow = as_dict(load_json_artifact(WF87_SHADOW_OUTCOME))
    wf87_rollup = as_dict(load_json_artifact(WF87_READINESS_ROLLUP))

    cost = model_cost_summary(model_run)
    latency = tool_latency_summary(tool_workflow, validator_timing, coding_runtime)
    health = otel_health_summary(otel, windows)
    friction = operational_friction_summary(cron_signal, workflow_advancement, wf87_shadow, wf87_rollup)
    recommendations = build_recommendations(cost, latency, health, queue, friction)
    carry_forward = build_carry_forward_contract(cost, health, recommendations)
    auto_router = build_auto_implementation_router(recommendations, queue)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Metadata-only learning loop for OTEL, tool/coding runtime, cost coverage, latency, failure categories, and bounded improvement routing.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_status": [
            source_status(OTEL_CONTROL),
            source_status(OTEL_WINDOWS),
            source_status(OTEL_TOOL_WORKFLOW),
            source_status(MODEL_RUN_LEDGER),
            source_status(MODEL_LEARNING_LEDGER),
            source_status(VALIDATOR_TIMING),
            source_status(CODING_RUNTIME),
            source_status(CHANGED_FILE_ROUTER),
            source_status(WF74_OPPORTUNITY_QUEUE),
            source_status(CRON_SIGNAL_SCORECARD),
            source_status(WORKFLOW_ADVANCEMENT),
            source_status(WF87_SHADOW_OUTCOME),
            source_status(WF87_READINESS_ROLLUP),
        ],
        "redaction_policy": {
            "allowed": [
                "model/provider identifiers",
                "token counts when available",
                "cost numbers when available",
                "duration/latency numbers",
                "tool names",
                "workflow/session/lane IDs",
                "status/failure categories",
                "validator pass/fail metadata",
                "artifact proof paths",
            ],
            "blocked": [
                "raw prompts",
                "raw responses",
                "raw tool inputs",
                "raw tool outputs",
                "system prompts",
                "headers",
                "secrets",
                "credentials",
                "customer/account/brokerage data",
            ],
        },
        "learning_summaries": {
            "otel_health": health,
            "token_cost": cost,
            "tool_latency": latency,
            "learning_ledger": {
                "status": learning.get("status"),
                "summary": as_dict(learning.get("summary")),
            },
            "changed_file_router": {
                "status": changed_router.get("status"),
                "summary": as_dict(changed_router.get("summary")),
            },
            "operational_friction": friction,
        },
        "recommendations": recommendations,
        "carry_forward_contract": carry_forward,
        "auto_implementation_router": auto_router,
        "parallel_execution_plan": build_parallel_execution_plan(),
        "review_loop": {
            "daily_evening_alert": "python scripts\\wf74_learning_loop_telegram_cron_runner.py --write --validate --send",
            "new_session_pickup": "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
            "status_pickup": "python scripts\\status_card_packet.py --write --validate",
            "weekly_review": "Review recommendation changes, auto-apply count, and carry-forward warnings before widening automation.",
        },
        "next_safe_action": "Keep metadata collection in the WF74 runner; prepare a separate owner-gated config patch only for token/cost/latency metadata depth.",
        "blocked_actions": [
            "no raw content capture",
            "no system prompt capture",
            "no raw tool payload capture",
            "no secrets or headers capture",
            "no external export",
            "no collector/runtime config mutation from this script",
            "no model ranking claim from telemetry alone",
            "no finance/capital/execution authority",
        ],
    }
    findings = scan_forbidden(payload)
    payload["privacy_scan"] = {
        "status": "ok" if not findings else "blocked",
        "finding_count": len(findings),
        "findings": findings[:50],
    }
    payload["validation"] = {
        "status": "ok" if payload["privacy_scan"]["status"] == "ok" else "blocked",
        "errors": [] if not findings else ["privacy_scan_blocked"],
        "warnings": [],
    }
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summaries = as_dict(payload.get("learning_summaries"))
    health = as_dict(summaries.get("otel_health"))
    cost = as_dict(summaries.get("token_cost"))
    latency = as_dict(summaries.get("tool_latency"))
    lines = [
        "# OTEL Learning Loop",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Collector health: `{health.get('collector_health')}`",
        f"- Drift status: `{health.get('drift_status')}`",
        f"- Token coverage: `{cost.get('token_coverage_ratio')}`",
        f"- Cost coverage: `{cost.get('cost_coverage_ratio')}`",
        f"- Tool failure rows: `{latency.get('failure_rows')}`",
        f"- Privacy scan: `{as_dict(payload.get('privacy_scan')).get('status')}`",
        "",
        "## Recommendations",
    ]
    for item in as_list(payload.get("recommendations")):
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('id')}`: {item.get('decision')} - {item.get('rationale')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Metadata-only. No raw prompts, responses, tool payloads, system prompts, secrets, headers, external export, or finance/execution authority.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.write:
        atomic_write_json(args.json_out, payload)
        print(f"wrote {rel(args.json_out)} status={payload.get('status')}")
    if args.write_md:
        atomic_write_text(args.md_out, render_md(payload))
        print(f"wrote {rel(args.md_out)}")
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        print(json.dumps(payload.get("validation"), indent=2))
        return 1
    if not args.write:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
