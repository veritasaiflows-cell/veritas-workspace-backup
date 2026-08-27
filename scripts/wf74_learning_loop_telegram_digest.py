#!/usr/bin/env python3
"""WF74 learning-loop Telegram digest.

This is a review-only notification surface for WF74 opportunities and
proposals. It sends a quiet daily delta digest, with immediate owner-gate
delivery allowed only when a new owner-gated proposal appears.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
DEFAULT_PROPOSALS = TMP / "wf74-reflection-to-proposal-autopilot.json"
DEFAULT_AUTO_PATCH = TMP / "wf74-auto-patch-proposer.json"
DEFAULT_STATE = TMP / "wf74-learning-loop-telegram-state.json"
DEFAULT_OUTPUT = TMP / "wf74-learning-loop-telegram-digest.json"
DEFAULT_CRITICAL_REVIEW = TMP / "otel-critical-review-decision-packet.json"
DEFAULT_MODEL_QUALITY = TMP / "wf74-model-quality-collection-cron-runner.json"
DEFAULT_OTEL_LEARNING = TMP / "otel-learning-loop.json"
DEFAULT_IMPROVEMENTS = TMP / "improvement-ledger-current.json"
DEFAULT_AUTONOMY_ROUTER = TMP / "wf74-autonomy-work-router.json"
DEFAULT_DECISION_DOCKET = TMP / "wf74-decision-docket.json"
DEFAULT_OTEL_OPS = TMP / "otel-ops-control.json"
DEFAULT_TOOL_WORKFLOW = TMP / "otel-tool-workflow-metadata.json"
DEFAULT_TOKEN_BUDGET = TMP / "token-budget-status.json"
DEFAULT_TOKEN_EFFICIENCY = TMP / "token-efficiency-scorecard.json"
DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"
LOCAL_TZ = ZoneInfo("America/Phoenix")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "telegram_delivery_allowed": True,
    "learning_loop_notification_only": True,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "external_export_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}

BOUNDARY = (
    "Review/proposal only. This digest does not apply code, approve skills, "
    "change collector config, mutate finance/canon/portfolio state, or submit "
    "paper/live orders."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha12(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:12]


def authority_clean(value: Any) -> bool:
    dangerous = (
        "code_mutation",
        "skill_application",
        "collector_config",
        "runtime_config",
        "finance",
        "portfolio",
        "canon",
        "cash",
        "sizing",
        "sleeve",
        "risk_rule",
        "capital",
        "trade",
        "execution",
        "order",
        "submit",
        "cancel",
        "sell",
        "account",
        "brokerage",
        "money",
        "raw_prompt",
        "raw_response",
        "tool_payload",
        "owner_approval",
        "auto_apply",
    )
    allowed_true = {"review_only", "telegram_delivery_allowed", "learning_loop_notification_only"}
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, bool) and child is True:
                if any(token in lowered for token in dangerous) and lowered not in allowed_true:
                    return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def resolve_openclaw_command() -> str:
    found = shutil.which("openclaw") or shutil.which("openclaw.cmd") or shutil.which("openclaw.ps1")
    if found:
        return found
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "npm" / "openclaw.cmd"
        if candidate.exists():
            return str(candidate)
    return "openclaw"


def send_telegram(channel: str, target: str, message: str, timeout: int) -> dict[str, Any]:
    openclaw_command = resolve_openclaw_command()
    command = [openclaw_command, "message", "send", "--channel", channel, "--target", target, "--message", message]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": "openclaw message send --channel <channel> --target <target> --message <redacted>",
        "resolved_command": openclaw_command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "ok": completed.returncode == 0,
    }


def after_hours_gate(now_utc: datetime | None = None) -> dict[str, Any]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    minutes = now.hour * 60 + now.minute
    allowed = minutes >= 18 * 60
    return {
        "timezone": "America/Phoenix",
        "checked_at_local": now.replace(microsecond=0).isoformat(),
        "allowed_start_local": "18:00",
        "after_6pm_local": allowed,
        "reason": "after_6pm_arizona" if allowed else "before_6pm_arizona",
    }


def top_items(items: list[Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = [as_dict(item) for item in items if isinstance(item, dict)]
    return sorted(rows, key=lambda row: int(row.get("priority") or 0), reverse=True)[:limit]


def compact_mapping(value: Any, limit: int = 5) -> str:
    def count_value(item: tuple[str, Any]) -> int:
        try:
            return int(item[1] or 0)
        except (TypeError, ValueError):
            return 0

    items = sorted(as_dict(value).items(), key=lambda item: (-count_value(item), str(item[0])))
    return ", ".join(f"{key}:{count}" for key, count in items[:limit]) or "none"


def proposal_owner_gated(proposal: dict[str, Any]) -> bool:
    status = str(proposal.get("proposal_status") or "")
    return status in {"owner_decision_required", "exact_owner_approval_required"}


def otel_learning_summary(otel_learning: dict[str, Any]) -> dict[str, Any]:
    summaries = as_dict(otel_learning.get("learning_summaries"))
    health = as_dict(summaries.get("otel_health"))
    cost = as_dict(summaries.get("token_cost"))
    carry_forward = as_dict(otel_learning.get("carry_forward_contract"))
    auto_router = as_dict(otel_learning.get("auto_implementation_router"))
    recommendations = [as_dict(row) for row in as_list(otel_learning.get("recommendations")) if isinstance(row, dict)]
    top_recommendation = recommendations[0] if recommendations else {}
    return {
        "present": bool(otel_learning),
        "status": otel_learning.get("status"),
        "validation": as_dict(otel_learning.get("validation")).get("status"),
        "generated_at_utc": otel_learning.get("generated_at_utc"),
        "collector_health": health.get("collector_health"),
        "drift_status": health.get("drift_status"),
        "daily_event_count": health.get("daily_event_count"),
        "daily_warning_or_error_count": health.get("daily_warning_or_error_count"),
        "token_coverage_ratio": cost.get("token_coverage_ratio"),
        "cost_coverage_ratio": cost.get("cost_coverage_ratio"),
        "recommendation_count": len(recommendations),
        "top_recommendation_id": top_recommendation.get("id"),
        "top_recommendation_decision": top_recommendation.get("decision"),
        "carry_forward_status": carry_forward.get("status"),
        "auto_implementation_status": auto_router.get("status"),
        "auto_apply_allowed": False,
        "next_safe_action": otel_learning.get("next_safe_action") or carry_forward.get("next_safe_action"),
    }


def improvement_summary(improvements: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(improvements.get("summary"))
    kpis = as_dict(improvements.get("learning_loop_kpis"))
    skill_audit = as_dict(improvements.get("skill_proposal_audit"))
    latest_open = [as_dict(row) for row in as_list(improvements.get("latest_open_improvements")) if isinstance(row, dict)]
    followup_required = [
        as_dict(row)
        for row in as_list(improvements.get("followup_required_improvements"))
        if isinstance(row, dict)
    ]
    top = latest_open[0] if latest_open else {}
    return {
        "present": bool(improvements),
        "status": improvements.get("status"),
        "validation": as_dict(improvements.get("validation")).get("status"),
        "generated_at_utc": improvements.get("generated_at_utc"),
        "open_count": summary.get("latest_open_count"),
        "high_priority_count": summary.get("high_priority_open_count"),
        "overdue_count": summary.get("overdue_open_count"),
        "due_soon_count": summary.get("due_soon_open_count"),
        "high_priority_overdue_count": summary.get("high_priority_overdue_open_count"),
        "followup_required_count": summary.get("followup_required_open_count"),
        "escalation_level": summary.get("escalation_level"),
        "anti_theater_status": kpis.get("anti_theater_status"),
        "closure_rate": kpis.get("closure_rate"),
        "by_category": summary.get("by_category"),
        "top_title": top.get("title") or summary.get("top_improvement_title"),
        "top_priority": top.get("priority"),
        "top_age_hours": top.get("age_hours") or summary.get("top_improvement_age_hours"),
        "top_sla_status": top.get("sla_status") or summary.get("top_improvement_sla_status"),
        "top_next_action": top.get("next_action") or summary.get("top_improvement_next_action"),
        "top_open_improvements": latest_open[:3],
        "top_followup_required": followup_required[:3],
        "skill_proposal_count": skill_audit.get("proposal_count"),
        "pending_skill_proposal_count": skill_audit.get("pending_count")
        or summary.get("pending_skill_proposal_count"),
        "applied_skill_proposal_count": skill_audit.get("applied_count"),
        "relevant_pending_skill_proposal_count": skill_audit.get("relevant_pending_count")
        or summary.get("relevant_pending_skill_proposal_count"),
        "relevant_pending_skill_proposals": as_list(skill_audit.get("relevant_pending"))[:3],
        "skill_proposal_meaning": skill_audit.get("not_implemented_meaning"),
    }


def otel_ops_summary(otel_ops: dict[str, Any], tool_workflow: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(otel_ops.get("summary"))
    collector = as_dict(otel_ops.get("collector_health"))
    drift = as_dict(otel_ops.get("drift"))
    tool_meta = as_dict(otel_ops.get("tool_workflow_metadata")) or {
        "present": bool(tool_workflow),
        "status": tool_workflow.get("status"),
        "generated_at_utc": tool_workflow.get("generated_at_utc"),
        "row_count": as_dict(tool_workflow.get("summary")).get("row_count"),
        "unique_tool_count": as_dict(tool_workflow.get("summary")).get("unique_tool_count"),
        "failed_or_blocked_count": as_dict(tool_workflow.get("summary")).get("failed_or_blocked_count"),
        "privacy_scan_status": as_dict(tool_workflow.get("privacy_scan")).get("status"),
    }
    return {
        "present": bool(otel_ops) or bool(tool_workflow),
        "status": otel_ops.get("status"),
        "validation": as_dict(otel_ops.get("validation")).get("status"),
        "generated_at_utc": otel_ops.get("generated_at_utc"),
        "collector_status": collector.get("status"),
        "collector_host": collector.get("host"),
        "collector_port": collector.get("port"),
        "collector_listening": collector.get("listening"),
        "event_count": summary.get("event_count"),
        "warning_or_error_count": drift.get("daily_warning_or_error_count"),
        "daily_events_per_hour": drift.get("daily_events_per_hour"),
        "weekly_events_per_hour": drift.get("weekly_events_per_hour"),
        "daily_vs_weekly_ratio": drift.get("daily_vs_weekly_event_rate_ratio"),
        "drift_status": drift.get("status"),
        "drift_reasons": as_list(drift.get("drift_reasons")),
        "tool_metadata_present": tool_meta.get("present"),
        "tool_metadata_status": tool_meta.get("status"),
        "tool_metadata_row_count": tool_meta.get("row_count"),
        "tool_metadata_unique_tool_count": tool_meta.get("unique_tool_count"),
        "tool_metadata_failed_or_blocked_count": tool_meta.get("failed_or_blocked_count"),
        "tool_metadata_privacy_scan": tool_meta.get("privacy_scan_status"),
    }


def wf74_intelligence_summary(
    router: dict[str, Any],
    decision_docket: dict[str, Any],
    model_quality: dict[str, Any],
) -> dict[str, Any]:
    router_summary = as_dict(router.get("summary"))
    kpis = as_dict(router.get("kpis"))
    docket_summary = as_dict(decision_docket.get("summary"))
    docket_context = as_dict(decision_docket.get("context"))
    model_summary = as_dict(model_quality.get("summary"))
    return {
        "present": bool(router) or bool(decision_docket) or bool(model_quality),
        "router_status": router.get("status"),
        "router_validation": as_dict(router.get("validation")).get("status"),
        "docket_status": decision_docket.get("status"),
        "docket_validation": as_dict(decision_docket.get("validation")).get("status"),
        "model_quality_status": model_quality.get("status"),
        "model_quality_validation": as_dict(model_quality.get("validation")).get("status"),
        "opportunity_count": router_summary.get("opportunity_count"),
        "routed_opportunity_count": router_summary.get("routed_opportunity_count"),
        "pm_job_candidate_count": router_summary.get("pm_job_candidate_count"),
        "workflow_followup_count": router_summary.get("workflow_followup_count"),
        "cron_repair_plan_count": router_summary.get("cron_repair_plan_count"),
        "recommendation_to_route_conversion_rate": kpis.get("recommendation_to_route_conversion_rate")
        or router_summary.get("recommendation_to_route_conversion_rate"),
        "route_to_pm_job_conversion_rate": kpis.get("route_to_pm_job_conversion_rate")
        or router_summary.get("route_to_pm_job_conversion_rate"),
        "planning_followthrough_clean_rate": kpis.get("planning_followthrough_clean_rate")
        or router_summary.get("planning_followthrough_clean_rate"),
        "high_priority_overdue_count": kpis.get("high_priority_overdue_count")
        or router_summary.get("high_priority_overdue_count"),
        "top_improvement_age_hours": kpis.get("average_age_of_top_open_improvement_hours")
        or router_summary.get("top_improvement_age_hours"),
        "routed_categories": as_list(router_summary.get("routed_categories")),
        "department_counts": router_summary.get("department_counts"),
        "decision_row_count": docket_summary.get("row_count"),
        "fix_now_count": docket_summary.get("fix_now_count"),
        "owner_decision_count": docket_summary.get("owner_decision_count"),
        "hard_stop_count": docket_summary.get("hard_stop_count"),
        "highest_priority_state": docket_summary.get("highest_priority_state"),
        "next_safe_action": router.get("next_safe_action") or docket_summary.get("next_safe_action"),
        "cron_context": as_dict(docket_context.get("cron")),
        "wf87_readiness_status": docket_context.get("wf87_readiness_status"),
        "model_steps_total": model_summary.get("steps_total"),
        "model_steps_ok": model_summary.get("steps_ok"),
        "model_steps_blocked": model_summary.get("steps_blocked"),
        "finance_response_quality_status": model_summary.get("finance_response_quality_status"),
        "finance_source_open_blocked_count": model_summary.get("finance_response_quality_source_open_blocked_count"),
    }


def fleet_digest_view(token_budget: dict[str, Any], token_efficiency: dict[str, Any]) -> dict[str, Any]:
    """Return a metadata-only fleet view; never forward transcript or tool payload fields."""
    efficiency_fleet = as_dict(token_efficiency.get("fleet_efficiency"))
    budget_fleet = as_dict(token_budget.get("fleet_usage"))
    if efficiency_fleet.get("present") is True:
        source_name = "token_efficiency_scorecard"
        source = efficiency_fleet
    elif budget_fleet.get("present") is True:
        source_name = "token_budget_status"
        source = budget_fleet
    else:
        source_name = "unavailable"
        source = efficiency_fleet or budget_fleet

    summary = as_dict(source.get("summary"))
    windows = as_dict(source.get("usage_windows"))
    safe_windows = {
        name: {
            key: as_dict(windows.get(name)).get(key)
            for key in (
                "status", "coverage", "ready_agent_count", "configured_agent_count",
                "event_count", "total_tokens", "api_equivalent_cost_usd",
                "api_equivalent_is_not_invoice", "actual_billed_cost_usd", "date_labels",
            )
        }
        for name in ("rolling_5h_observed", "rolling_24h_gateway", "closed_7d_gateway")
    }
    agents: list[dict[str, Any]] = []
    for raw in as_list(source.get("agents")):
        if not isinstance(raw, dict):
            continue
        utilization = as_dict(raw.get("utilization"))
        outcomes = as_dict(raw.get("outcomes"))
        agents.append({
            "agent_id": raw.get("agent_id"),
            "agent_role": raw.get("agent_role"),
            "reporting_source": raw.get("reporting_source") or utilization.get("reporting_source"),
            "reporting_total_tokens": raw.get("reporting_total_tokens") if "reporting_total_tokens" in raw else utilization.get("reporting_total_tokens"),
            "utilization_share_percent": raw.get("utilization_share_percent") if "utilization_share_percent" in raw else utilization.get("utilization_share_percent"),
            "utilized": raw.get("utilized") if "utilized" in raw else utilization.get("utilized"),
            "session_event_count": raw.get("session_event_count") if "session_event_count" in raw else utilization.get("session_event_count"),
            "session_pricing_grade_event_count": raw.get("session_pricing_grade_event_count") if "session_pricing_grade_event_count" in raw else utilization.get("session_pricing_grade_event_count"),
            "outcomes": {
                key: outcomes.get(key)
                for key in (
                    "completed_lane_count", "parent_job_count", "parent_job_completed_count",
                    "outcome_tracking_start_utc", "outcome_eligible_completed_lane_count",
                    "historical_or_untracked_completed_lane_count", "main_accepted_count",
                    "main_acceptance_pending_count", "qa_review_completed_count", "qa_pass_count",
                    "qa_yield_percent", "rework_count", "attribution_gap_count",
                )
            },
        })
    agents.sort(key=lambda row: (-(int(row.get("reporting_total_tokens") or 0)), str(row.get("agent_id") or "")))

    billing = as_dict(source.get("billing_semantics"))
    capacity = as_dict(source.get("oauth_capacity_advisory"))
    present = source.get("present") is True
    semantics_ok = billing.get("api_equivalent_is_not_invoice") is True and billing.get("actual_billed_cost_usd") is None
    capacity_ok = capacity.get("automatic_action_allowed") is False
    return {
        "schema": "veritas.isolated_agent_fleet_telegram_view.v1",
        "present": present,
        "status": source.get("status") or "unavailable",
        "source": source_name,
        "generated_at_utc": source.get("generated_at_utc"),
        "summary": {
            key: summary.get(key)
            for key in (
                "configured_agent_count", "observed_agent_count", "utilized_agent_count",
                "session_event_count", "attribution_grade_coverage_percent",
                "pricing_grade_event_count", "pricing_grade_attribution_coverage_percent",
                "parent_job_count", "parent_job_completed_count", "parent_job_completion_percent",
                "completed_lane_count", "main_accepted_count", "main_acceptance_percent",
                "outcome_tracking_start_utc", "outcome_eligible_completed_lane_count",
                "historical_or_untracked_completed_lane_count", "main_acceptance_pending_count",
                "qa_review_completed_count", "qa_pass_count", "qa_yield_percent",
                "rework_count", "rework_percent", "attribution_gap_count",
            )
        },
        "usage_windows": safe_windows,
        "agents": agents,
        "billing_semantics": {
            "label": "API-equivalent benchmark",
            "api_equivalent_is_not_invoice": billing.get("api_equivalent_is_not_invoice") is True,
            "actual_billed_cost_usd": None,
        },
        "oauth_capacity_advisory": {
            "status": capacity.get("status"),
            "tier": capacity.get("tier"),
            "remaining_percent": capacity.get("remaining_percent"),
            "reset_at_utc": capacity.get("reset_at_utc"),
            "automatic_action_allowed": False,
        },
        "source_contract": {
            "api_equivalent_semantics_valid": semantics_ok if present else None,
            "oauth_capacity_advisory_only": capacity_ok if present else None,
        },
        "privacy_contract": {
            "metadata_only": True,
            "raw_prompt_stored": False,
            "raw_response_stored": False,
            "tool_payload_stored": False,
        },
    }


def fleet_signature(view: dict[str, Any]) -> dict[str, Any]:
    """Stable fleet delta fields; omit producer timestamps so unchanged data stays quiet."""
    return {
        "present": view.get("present"),
        "status": view.get("status"),
        "summary": as_dict(view.get("summary")),
        "usage_windows": as_dict(view.get("usage_windows")),
        "agents": as_list(view.get("agents")),
        "oauth_capacity_advisory": as_dict(view.get("oauth_capacity_advisory")),
    }


def signature(
    queue: dict[str, Any],
    proposals: dict[str, Any],
    auto_patch: dict[str, Any] | None = None,
    otel_learning: dict[str, Any] | None = None,
    improvements: dict[str, Any] | None = None,
    autonomy_router: dict[str, Any] | None = None,
    decision_docket: dict[str, Any] | None = None,
    model_quality: dict[str, Any] | None = None,
    otel_ops: dict[str, Any] | None = None,
    tool_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal_rows = as_list(proposals.get("proposals"))
    owner_ids = sorted(str(row.get("proposal_id")) for row in proposal_rows if isinstance(row, dict) and proposal_owner_gated(row))
    auto_patch_summary = as_dict(as_dict(auto_patch or {}).get("summary"))
    otel_summary = otel_learning_summary(as_dict(otel_learning or {}))
    improvement = improvement_summary(as_dict(improvements or {}))
    otel_ops_context = otel_ops_summary(as_dict(otel_ops or {}), as_dict(tool_workflow or {}))
    wf74_context = wf74_intelligence_summary(
        as_dict(autonomy_router or {}),
        as_dict(decision_docket or {}),
        as_dict(model_quality or {}),
    )
    return {
        "queue_generated_at_utc": queue.get("generated_at_utc"),
        "proposal_generated_at_utc": proposals.get("generated_at_utc"),
        "auto_patch_generated_at_utc": as_dict(auto_patch or {}).get("generated_at_utc"),
        "otel_learning_generated_at_utc": as_dict(otel_learning or {}).get("generated_at_utc"),
        "improvement_generated_at_utc": as_dict(improvements or {}).get("generated_at_utc"),
        "autonomy_router_generated_at_utc": as_dict(autonomy_router or {}).get("generated_at_utc"),
        "decision_docket_generated_at_utc": as_dict(decision_docket or {}).get("generated_at_utc"),
        "model_quality_generated_at_utc": as_dict(model_quality or {}).get("generated_at_utc"),
        "otel_ops_generated_at_utc": as_dict(otel_ops or {}).get("generated_at_utc"),
        "tool_workflow_generated_at_utc": as_dict(tool_workflow or {}).get("generated_at_utc"),
        "opportunity_ids": sorted(str(row.get("opportunity_id")) for row in as_list(queue.get("opportunities")) if isinstance(row, dict)),
        "proposal_ids": sorted(str(row.get("proposal_id")) for row in proposal_rows if isinstance(row, dict)),
        "owner_gated_proposal_ids": owner_ids,
        "summary": {
            "opportunity_count": as_dict(queue.get("summary")).get("opportunity_count"),
            "high_priority_count": as_dict(queue.get("summary")).get("high_priority_count"),
            "proposal_count": as_dict(proposals.get("summary")).get("proposal_count"),
            "owner_decision_required_count": as_dict(proposals.get("summary")).get("owner_decision_required_count"),
            "auto_apply_count": as_dict(proposals.get("summary")).get("auto_apply_count"),
            "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
            "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
            "otel_status": otel_summary.get("status"),
            "otel_drift_status": otel_summary.get("drift_status"),
            "otel_carry_forward_status": otel_summary.get("carry_forward_status"),
            "otel_recommendation_count": otel_summary.get("recommendation_count"),
            "improvement_open_count": improvement.get("open_count"),
            "improvement_high_priority_count": improvement.get("high_priority_count"),
            "improvement_overdue_count": improvement.get("overdue_count"),
            "improvement_escalation_level": improvement.get("escalation_level"),
            "pending_skill_proposal_count": improvement.get("pending_skill_proposal_count"),
            "relevant_pending_skill_proposal_count": improvement.get("relevant_pending_skill_proposal_count"),
            "otel_ops_event_count": otel_ops_context.get("event_count"),
            "otel_ops_drift_status": otel_ops_context.get("drift_status"),
            "tool_metadata_row_count": otel_ops_context.get("tool_metadata_row_count"),
            "wf74_routed_opportunity_count": wf74_context.get("routed_opportunity_count"),
            "wf74_fix_now_count": wf74_context.get("fix_now_count"),
            "wf74_model_steps_blocked": wf74_context.get("model_steps_blocked"),
        },
    }


def critical_review_signature(critical_review: dict[str, Any]) -> dict[str, Any]:
    if not critical_review:
        return {}
    decision = as_dict(critical_review.get("decision"))
    context = as_dict(critical_review.get("digest_context"))
    return {
        "generated_at_utc": critical_review.get("generated_at_utc"),
        "status": critical_review.get("status"),
        "severity": critical_review.get("severity") or context.get("severity"),
        "persistence": critical_review.get("persistence") or context.get("persistence"),
        "recommended_decision": decision.get("recommended_decision") or context.get("recommended_decision"),
        "owner_decision_today": decision.get("owner_decision_today") or context.get("owner_decision_today"),
    }


def model_quality_clean(model_quality: dict[str, Any], force_block: bool = False) -> tuple[bool, str]:
    if force_block:
        return False, "current_model_quality_step_failed"
    if not model_quality:
        return False, "model_quality_runner_missing"
    validation = as_dict(model_quality.get("validation"))
    summary = as_dict(model_quality.get("summary"))
    if summary.get("scheduler_exit_domain_blocked_nonfatal") is True:
        return True, str(summary.get("scheduler_exit_reason") or "model_quality_runner_domain_blocked_nonfatal")
    critical_findings = [
        str(as_dict(row).get("detail") or "")
        for row in as_list(validation.get("findings"))
        if as_dict(row).get("severity") == "critical"
    ]
    if model_quality.get("status") in {"blocked", "critical", "error"}:
        return False, f"model_quality_runner_status_{model_quality.get('status')}"
    if int(summary.get("steps_blocked") or 0) > 0:
        return False, "model_quality_runner_steps_blocked"
    if validation.get("status") in {"blocked", "error"}:
        return False, f"model_quality_runner_validation_{validation.get('status')}"
    if validation.get("status") == "critical":
        routed_diagnostic_criticals = {
            "improvement ledger validation is not ok",
            "WF74 proposal dispatcher validation is not ok or warning",
        }
        if critical_findings and set(critical_findings) <= routed_diagnostic_criticals:
            if int(summary.get("wf74_dispatch_auto_apply_count") or 0) > 0:
                return False, "model_quality_runner_dispatcher_auto_apply_critical"
            return True, "model_quality_runner_clean_with_routed_diagnostic_residue"
        return False, "model_quality_runner_validation_critical"
    if validation.get("status") == "warning":
        return True, "model_quality_runner_clean_with_warnings"
    return True, "model_quality_runner_clean"


def row_matches_context(row: dict[str, Any], context: dict[str, Any]) -> bool:
    titles = {str(item).strip().lower() for item in as_list(context.get("applies_to_titles")) if str(item).strip()}
    categories = {str(item).strip().lower() for item in as_list(context.get("applies_to_categories")) if str(item).strip()}
    title = str(row.get("title") or "").strip().lower()
    category = str(row.get("category") or "").strip().lower()
    return bool((title and title in titles) or (category and category in categories))


def row_context(row: dict[str, Any], critical_review: dict[str, Any]) -> dict[str, Any]:
    context = as_dict(critical_review.get("digest_context"))
    matched = context if row_matches_context(row, context) else {}
    decision = as_dict(critical_review.get("decision")) if matched else {}
    return {
        "severity": row.get("severity") or as_dict(row.get("evidence")).get("severity") or matched.get("severity"),
        "persistence": row.get("persistence") or row.get("persistence_status") or matched.get("persistence"),
        "next_safe_action": row.get("next_safe_action") or matched.get("next_safe_action"),
        "owner_decision_today": row.get("owner_decision_today") or decision.get("owner_decision_today") or matched.get("owner_decision_today"),
        "recommended_decision": row.get("recommended_decision") or decision.get("recommended_decision") or matched.get("recommended_decision"),
    }


def compact_context_suffix(row: dict[str, Any], critical_review: dict[str, Any]) -> str:
    context = row_context(row, critical_review)
    pieces: list[str] = []
    if context.get("severity"):
        pieces.append(f"severity {context['severity']}")
    if context.get("persistence"):
        pieces.append(f"persistence {context['persistence']}")
    if context.get("recommended_decision"):
        pieces.append(f"decision {context['recommended_decision']}")
    if context.get("owner_decision_today"):
        pieces.append(f"owner today {context['owner_decision_today']}")
    if context.get("next_safe_action"):
        pieces.append(f"next {context['next_safe_action']}")
    return "; ".join(str(piece).replace("\n", " ") for piece in pieces)


def digest_row(row: dict[str, Any], status_field: str, critical_review: dict[str, Any]) -> str:
    base = f"{row.get('title')} ({row.get(status_field)}, priority {row.get('priority')})"
    suffix = compact_context_suffix(row, critical_review)
    return f"{base} | {suffix}" if suffix else base


def load_state(path: Path) -> dict[str, Any]:
    state = load_dict(path)
    if not state:
        return {"schema": "veritas.wf74_learning_loop_telegram_state.v1", "sent": {}}
    if not isinstance(state.get("sent"), dict):
        state["sent"] = {}
    return state


def build_message(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    critical_review = as_dict(packet.get("critical_review"))
    otel = as_dict(packet.get("otel_learning_loop"))
    improvements = as_dict(packet.get("improvement_ledger"))
    skill_proposals = as_dict(packet.get("skill_proposals"))
    otel_ops = as_dict(packet.get("otel_ops"))
    wf74 = as_dict(packet.get("wf74_intelligence"))
    fleet = as_dict(packet.get("isolated_agent_fleet"))
    fleet_summary = as_dict(fleet.get("summary"))
    lines = [
        "WF74 Learning Loop Digest",
        "",
        "Bottom line",
        f"- Opportunities: {summary.get('opportunity_count')} total / {summary.get('high_priority_count')} high priority",
        f"- Proposals: {summary.get('proposal_count')} total / {summary.get('owner_decision_required_count')} owner-gated",
        f"- Auto-patch plans: {summary.get('auto_patch_plan_count')} total / {summary.get('auto_patch_skill_workshop_request_count')} skill requests",
        f"- Auto-apply: {summary.get('auto_apply_count')}",
        f"- Improvements: {improvements.get('status')} / open {improvements.get('open_count')} / high {improvements.get('high_priority_count')} / overdue {improvements.get('overdue_count')} / escalation {improvements.get('escalation_level')}",
        f"- Skill proposals: pending {skill_proposals.get('pending_count')} / relevant {skill_proposals.get('relevant_pending_count')} / applied {skill_proposals.get('applied_count')}",
        f"- WF74 route: routed {wf74.get('routed_opportunity_count')} / PM candidates {wf74.get('pm_job_candidate_count')} / fix-now {wf74.get('fix_now_count')} / hard stops {wf74.get('hard_stop_count')}",
        f"- OTEL: {otel.get('status')} / drift {otel.get('drift_status')} / carry-forward {otel.get('carry_forward_status')}",
        f"- OTEL ops: collector {otel_ops.get('collector_status')} / 24h events {otel_ops.get('event_count')} / warnings-errors {otel_ops.get('warning_or_error_count')}",
        f"- Agent fleet: {fleet.get('status')} / utilized {fleet_summary.get('utilized_agent_count')}/{fleet_summary.get('configured_agent_count')} / pricing-grade {fleet_summary.get('pricing_grade_attribution_coverage_percent')}%",
        f"- Trigger: {packet.get('trigger_reason')}",
    ]
    if fleet.get("present"):
        fleet_windows = as_dict(fleet.get("usage_windows"))
        five_hour = as_dict(fleet_windows.get("rolling_5h_observed"))
        day = as_dict(fleet_windows.get("rolling_24h_gateway"))
        week = as_dict(fleet_windows.get("closed_7d_gateway"))
        capacity = as_dict(fleet.get("oauth_capacity_advisory"))
        lines.extend([
            "",
            "Isolated Agent Fleet",
            f"- Windows: observed 5h {five_hour.get('total_tokens')} tokens ({five_hour.get('status')}); Gateway 24h {day.get('total_tokens')} ({day.get('status')}); closed 7d {week.get('total_tokens')} ({week.get('status')})",
            f"- Utilization: {fleet_summary.get('utilized_agent_count')}/{fleet_summary.get('configured_agent_count')} agents; pricing-grade attribution {fleet_summary.get('pricing_grade_attribution_coverage_percent')}%",
            f"- Outcomes: parent jobs completed {fleet_summary.get('parent_job_completed_count')}/{fleet_summary.get('parent_job_count')}; Main accepted {fleet_summary.get('main_accepted_count')}/{fleet_summary.get('outcome_eligible_completed_lane_count')} tracked; QA passed {fleet_summary.get('qa_pass_count')}/{fleet_summary.get('qa_review_completed_count')} ({fleet_summary.get('qa_yield_percent')}%); historical/untracked {fleet_summary.get('historical_or_untracked_completed_lane_count')}; rework {fleet_summary.get('rework_count')}; attribution gaps {fleet_summary.get('attribution_gap_count')}",
            f"- OAuth capacity: {capacity.get('status')} / tier {capacity.get('tier')} / remaining {capacity.get('remaining_percent')}%; advisory only, no automatic action",
            "- Cost semantics: API-equivalent benchmark; not an invoice. Actual billed cost is not inferred.",
        ])
        for raw in as_list(fleet.get("agents"))[:6]:
            agent = as_dict(raw)
            outcomes = as_dict(agent.get("outcomes"))
            lines.append(
                f"- {agent.get('agent_id')}: {agent.get('reporting_total_tokens')} tokens / {agent.get('utilization_share_percent')}% share; "
                f"completed {outcomes.get('parent_job_completed_count')}; accepted {outcomes.get('main_accepted_count')}; "
                f"rework {outcomes.get('rework_count')}; gaps {outcomes.get('attribution_gap_count')}"
            )
    if otel.get("present"):
        lines.extend([
            "",
            "OTEL Carry-Forward",
            f"- Collector: {otel.get('collector_health')}; events: {otel.get('daily_event_count')}; warnings/errors: {otel.get('daily_warning_or_error_count')}",
            f"- Token/cost coverage: {otel.get('token_coverage_ratio')} / {otel.get('cost_coverage_ratio')}",
            f"- Recommendations: {otel.get('recommendation_count')}; top: {otel.get('top_recommendation_id')} -> {otel.get('top_recommendation_decision')}",
            f"- Auto-implementation route: {otel.get('auto_implementation_status')}; auto-apply allowed: {otel.get('auto_apply_allowed')}",
            f"- Next: {otel.get('next_safe_action')}",
        ])
    if otel_ops.get("present"):
        lines.extend([
            "",
            "OTEL Operations",
            f"- Collector: {otel_ops.get('collector_status')} at {otel_ops.get('collector_host')}:{otel_ops.get('collector_port')}; listening: {otel_ops.get('collector_listening')}",
            f"- Rate: daily {otel_ops.get('daily_events_per_hour')} per hour / weekly {otel_ops.get('weekly_events_per_hour')} / ratio {otel_ops.get('daily_vs_weekly_ratio')}; drift {otel_ops.get('drift_status')}",
            f"- Tool metadata: rows {otel_ops.get('tool_metadata_row_count')}; tools {otel_ops.get('tool_metadata_unique_tool_count')}; failed-blocked {otel_ops.get('tool_metadata_failed_or_blocked_count')}; privacy {otel_ops.get('tool_metadata_privacy_scan')}",
        ])
    if improvements.get("present"):
        lines.extend([
            "",
            "Improvement Ledger",
            f"- SLA: open {improvements.get('open_count')}; high {improvements.get('high_priority_count')}; overdue {improvements.get('overdue_count')}; due soon {improvements.get('due_soon_count')}; follow-up required {improvements.get('followup_required_count')}",
            f"- Anti-theater: {improvements.get('anti_theater_status')}; closure rate {improvements.get('closure_rate')}; categories {compact_mapping(improvements.get('by_category'))}",
            f"- Top: p{improvements.get('top_priority')} {improvements.get('top_title')} ({improvements.get('top_sla_status')}, age {improvements.get('top_age_hours')}h)",
            f"- Next: {improvements.get('top_next_action')}",
        ])
    if skill_proposals.get("present"):
        lines.extend([
            "",
            "Skill Proposals",
            f"- Workshop: total {skill_proposals.get('proposal_count')}; pending {skill_proposals.get('pending_count')}; relevant pending {skill_proposals.get('relevant_pending_count')}; applied {skill_proposals.get('applied_count')}",
            f"- WF74-generated skill requests: {skill_proposals.get('wf74_skill_request_count')}",
            f"- Meaning: {skill_proposals.get('meaning')}",
        ])
        for item in as_list(skill_proposals.get("relevant_pending"))[:2]:
            row = as_dict(item)
            lines.append(f"- Pending: {row.get('skill')} ({row.get('proposal_id')})")
    if wf74.get("present"):
        cron_context = as_dict(wf74.get("cron_context"))
        lines.extend([
            "",
            "WF74 Intelligence",
            f"- Router: status {wf74.get('router_status')}; recommendation-route {wf74.get('recommendation_to_route_conversion_rate')}; route-PM {wf74.get('route_to_pm_job_conversion_rate')}; planning clean {wf74.get('planning_followthrough_clean_rate')}",
            f"- Docket: rows {wf74.get('decision_row_count')}; highest {wf74.get('highest_priority_state')}; owner decisions {wf74.get('owner_decision_count')}; hard stops {wf74.get('hard_stop_count')}",
            f"- Cron context: status {cron_context.get('status')}; blocked {cron_context.get('blocked_count')}; escalation {cron_context.get('escalation_signal_count')}; wake main {cron_context.get('should_wake_main_session')}",
            f"- Model-quality collection: steps {wf74.get('model_steps_ok')}/{wf74.get('model_steps_total')}; blocked {wf74.get('model_steps_blocked')}; finance source-open blocked {wf74.get('finance_source_open_blocked_count')}",
            f"- Next: {wf74.get('next_safe_action')}",
        ])
    if packet.get("new_owner_gated_proposals"):
        lines.extend(["", "Owner-Gated"])
        for item in as_list(packet.get("new_owner_gated_proposals"))[:3]:
            row = as_dict(item)
            lines.append(f"- {digest_row(row, 'proposal_status', critical_review)}")
    lines.extend(["", "Top Opportunities"])
    for row in as_list(packet.get("top_opportunities"))[:3]:
        item = as_dict(row)
        lines.append(f"- {digest_row(item, 'category', critical_review)}")
    lines.extend(["", "Top Proposals"])
    for row in as_list(packet.get("top_proposals"))[:3]:
        item = as_dict(row)
        lines.append(f"- {digest_row(item, 'proposal_status', critical_review)}")
    lines.extend(["", "Guardrail", f"- {BOUNDARY}"])
    return "\n".join(str(line) for line in lines)


def flatten_section(section: str) -> str:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    return " | ".join(lines)


def split_long_text(value: str, limit: int) -> list[str]:
    if len(value) <= limit:
        return [value]
    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        split_at = remaining.rfind(" | ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip(" |"))
        remaining = remaining[split_at:].strip(" |")
    if remaining:
        chunks.append(remaining)
    return chunks


def telegram_cli_safe_messages(message: str, max_chars: int = 2800) -> list[str]:
    sections = [flatten_section(section) for section in message.strip().split("\n\n")]
    sections = [section for section in sections if section]
    raw_chunks: list[str] = []
    current = ""
    for section in sections:
        for candidate in split_long_text(section, max_chars):
            if not current:
                current = candidate
            elif len(current) + len(" || ") + len(candidate) <= max_chars:
                current = f"{current} || {candidate}"
            else:
                raw_chunks.append(current)
                current = candidate
    if current:
        raw_chunks.append(current)
    total = len(raw_chunks)
    return [f"WF74 Learning Loop Digest part {index}/{total}: {chunk}" for index, chunk in enumerate(raw_chunks, start=1)]


def determine_trigger(sig: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str, list[str]]:
    current_hash = sha12(sig)
    sent = as_dict(state.get("sent"))
    prior_hash = str(state.get("last_signature_hash") or "")
    prior_owner_ids = set(as_list(state.get("last_owner_gated_proposal_ids")))
    current_owner_ids = set(as_list(sig.get("owner_gated_proposal_ids")))
    new_owner_ids = sorted(current_owner_ids - prior_owner_ids)

    if current_hash in sent:
        return False, "duplicate_signature_already_sent", new_owner_ids
    if new_owner_ids:
        return True, "new_owner_gated_proposal", new_owner_ids
    if prior_hash and current_hash != prior_hash:
        return True, "daily_delta_changed", new_owner_ids
    if not prior_hash:
        return True, "initial_digest", new_owner_ids
    return False, "no_delta", new_owner_ids


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    queue = load_dict(args.queue)
    proposals = load_dict(args.proposals)
    auto_patch = load_dict(args.auto_patch)
    critical_review = load_dict(args.critical_review)
    model_quality = load_dict(args.model_quality_runner)
    otel_learning = load_dict(args.otel_learning)
    improvements = load_dict(args.improvements)
    autonomy_router = load_dict(args.autonomy_router)
    decision_docket = load_dict(args.decision_docket)
    otel_ops = load_dict(args.otel_ops)
    tool_workflow = load_dict(args.tool_workflow)
    token_budget = load_dict(args.token_budget)
    token_efficiency = load_dict(args.token_efficiency)
    state = load_state(args.state)
    blockers: list[str] = []
    warnings: list[str] = []

    if queue.get("status") != "ok":
        blockers.append("opportunity_queue_not_ok")
    if proposals.get("status") != "ok":
        blockers.append("proposal_autopilot_not_ok")
    if auto_patch and auto_patch.get("status") not in {"ok", "warning"}:
        blockers.append("auto_patch_proposer_not_ok")
    if not authority_clean(AUTHORITY_BOUNDARY):
        blockers.append("digest_authority_drift")
    if as_dict(proposals.get("summary")).get("auto_apply_count", 0) != 0:
        blockers.append("proposal_auto_apply_count_nonzero")
    if as_dict(auto_patch.get("summary")).get("auto_apply_count", 0) != 0:
        blockers.append("auto_patch_auto_apply_count_nonzero")
    otel_summary = otel_learning_summary(otel_learning)
    if otel_learning and otel_summary.get("validation") == "blocked":
        blockers.append("otel_learning_loop_validation_blocked")
    if not otel_learning:
        warnings.append("otel_learning_loop_missing")
    improvement_context = improvement_summary(improvements)
    if not improvements:
        warnings.append("improvement_ledger_missing")
    elif improvement_context.get("validation") == "blocked":
        blockers.append("improvement_ledger_validation_blocked")
    autonomy_context = wf74_intelligence_summary(autonomy_router, decision_docket, model_quality)
    otel_ops_context = otel_ops_summary(otel_ops, tool_workflow)
    if not otel_ops and not tool_workflow:
        warnings.append("otel_ops_context_missing")
    fleet_context = fleet_digest_view(token_budget, token_efficiency)
    if fleet_context.get("present") is not True:
        warnings.append("isolated_agent_fleet_reporting_unavailable")
    else:
        fleet_contract = as_dict(fleet_context.get("source_contract"))
        if fleet_contract.get("api_equivalent_semantics_valid") is not True:
            blockers.append("isolated_agent_fleet_api_equivalent_semantics_invalid")
        if fleet_contract.get("oauth_capacity_advisory_only") is not True:
            blockers.append("isolated_agent_fleet_capacity_not_advisory_only")
    model_quality_ok, model_quality_reason = model_quality_clean(model_quality, args.force_model_quality_block)
    if not model_quality_ok:
        blockers.append(model_quality_reason)

    sig = signature(
        queue,
        proposals,
        auto_patch,
        otel_learning,
        improvements,
        autonomy_router,
        decision_docket,
        model_quality,
        otel_ops,
        tool_workflow,
    )
    sig["critical_review"] = critical_review_signature(critical_review)
    sig["isolated_agent_fleet"] = fleet_signature(fleet_context)
    should_notify, trigger_reason, new_owner_ids = determine_trigger(sig, state)
    after_hours = after_hours_gate()
    if args.after_6pm_only and not after_hours["after_6pm_local"] and not args.force:
        should_notify = False
        trigger_reason = "held_until_after_6pm_arizona"

    proposal_rows = [as_dict(row) for row in as_list(proposals.get("proposals")) if isinstance(row, dict)]
    new_owner = [row for row in proposal_rows if str(row.get("proposal_id")) in set(new_owner_ids)]
    top_proposals = top_items(proposal_rows)
    top_opportunities = top_items(as_list(queue.get("opportunities")))
    auto_patch_summary = as_dict(auto_patch.get("summary"))
    fleet_summary = as_dict(fleet_context.get("summary"))
    fleet_windows = as_dict(fleet_context.get("usage_windows"))
    summary = {
        "opportunity_count": as_dict(queue.get("summary")).get("opportunity_count", 0),
        "high_priority_count": as_dict(queue.get("summary")).get("high_priority_count", 0),
        "proposal_count": as_dict(proposals.get("summary")).get("proposal_count", 0),
        "owner_decision_required_count": as_dict(proposals.get("summary")).get("owner_decision_required_count", 0),
        "auto_patch_plan_count": auto_patch_summary.get("plan_count", 0),
        "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count", 0),
        "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count", 0),
        "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count", 0),
        "auto_apply_count": int(as_dict(proposals.get("summary")).get("auto_apply_count", 0) or 0)
        + int(auto_patch_summary.get("auto_apply_count", 0) or 0),
        "new_owner_gated_proposal_count": len(new_owner),
        "otel_status": otel_summary.get("status"),
        "otel_validation": otel_summary.get("validation"),
        "otel_drift_status": otel_summary.get("drift_status"),
        "otel_recommendation_count": otel_summary.get("recommendation_count"),
        "otel_carry_forward_status": otel_summary.get("carry_forward_status"),
        "otel_auto_implementation_status": otel_summary.get("auto_implementation_status"),
        "improvement_open_count": improvement_context.get("open_count"),
        "improvement_high_priority_count": improvement_context.get("high_priority_count"),
        "improvement_overdue_count": improvement_context.get("overdue_count"),
        "improvement_due_soon_count": improvement_context.get("due_soon_count"),
        "improvement_high_priority_overdue_count": improvement_context.get("high_priority_overdue_count"),
        "improvement_followup_required_count": improvement_context.get("followup_required_count"),
        "improvement_escalation_level": improvement_context.get("escalation_level"),
        "skill_pending_proposal_count": improvement_context.get("pending_skill_proposal_count"),
        "skill_relevant_pending_proposal_count": improvement_context.get("relevant_pending_skill_proposal_count"),
        "otel_ops_event_count": otel_ops_context.get("event_count"),
        "otel_ops_warning_or_error_count": otel_ops_context.get("warning_or_error_count"),
        "otel_tool_metadata_row_count": otel_ops_context.get("tool_metadata_row_count"),
        "wf74_routed_opportunity_count": autonomy_context.get("routed_opportunity_count"),
        "wf74_pm_job_candidate_count": autonomy_context.get("pm_job_candidate_count"),
        "wf74_fix_now_count": autonomy_context.get("fix_now_count"),
        "wf74_hard_stop_count": autonomy_context.get("hard_stop_count"),
        "fleet_reporting_status": fleet_context.get("status"),
        "fleet_configured_agent_count": fleet_summary.get("configured_agent_count"),
        "fleet_utilized_agent_count": fleet_summary.get("utilized_agent_count"),
        "fleet_pricing_grade_attribution_coverage_percent": fleet_summary.get("pricing_grade_attribution_coverage_percent"),
        "fleet_parent_job_completed_count": fleet_summary.get("parent_job_completed_count"),
        "fleet_main_accepted_count": fleet_summary.get("main_accepted_count"),
        "fleet_qa_yield_percent": fleet_summary.get("qa_yield_percent"),
        "fleet_rework_count": fleet_summary.get("rework_count"),
        "fleet_attribution_gap_count": fleet_summary.get("attribution_gap_count"),
        "fleet_rolling_5h_total_tokens": as_dict(fleet_windows.get("rolling_5h_observed")).get("total_tokens"),
        "fleet_rolling_24h_total_tokens": as_dict(fleet_windows.get("rolling_24h_gateway")).get("total_tokens"),
        "fleet_closed_7d_total_tokens": as_dict(fleet_windows.get("closed_7d_gateway")).get("total_tokens"),
        "fleet_oauth_capacity_status": as_dict(fleet_context.get("oauth_capacity_advisory")).get("status"),
        "fleet_oauth_capacity_tier": as_dict(fleet_context.get("oauth_capacity_advisory")).get("tier"),
    }

    packet: dict[str, Any] = {
        "schema": "veritas.wf74_learning_loop_telegram_digest.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if blockers else "ok",
        "mode": "send" if args.send else "dry_run",
        "operator_action": "MAIN_SESSION_BLOCKER_PACKET" if blockers else ("TELEGRAM_NOTIFY" if should_notify else "NO_REPLY"),
        "trigger_reason": trigger_reason,
        "after_hours_gate": after_hours,
        "source_artifacts": {
            "opportunity_queue": rel(args.queue),
            "proposal_autopilot": rel(args.proposals),
            "auto_patch_proposer": rel(args.auto_patch),
            "state": rel(args.state),
            "critical_review": rel(args.critical_review),
            "model_quality_runner": rel(args.model_quality_runner),
            "otel_learning_loop": rel(args.otel_learning),
            "improvement_ledger": rel(args.improvements),
            "autonomy_router": rel(args.autonomy_router),
            "decision_docket": rel(args.decision_docket),
            "otel_ops": rel(args.otel_ops),
            "tool_workflow_metadata": rel(args.tool_workflow),
            "token_budget_status": rel(args.token_budget),
            "token_efficiency_scorecard": rel(args.token_efficiency),
        },
        "signature_hash": sha12(sig),
        "summary": summary,
        "top_opportunities": top_opportunities,
        "top_proposals": top_proposals,
        "new_owner_gated_proposals": new_owner,
        "critical_review": {
            "present": bool(critical_review),
            "status": critical_review.get("status") if critical_review else None,
            "severity": critical_review.get("severity") if critical_review else None,
            "persistence": critical_review.get("persistence") if critical_review else None,
            "decision": critical_review.get("decision") if critical_review else None,
            "digest_context": critical_review.get("digest_context") if critical_review else None,
        },
        "model_quality_runner": {
            "present": bool(model_quality),
            "status": model_quality.get("status") if model_quality else None,
            "validation": as_dict(model_quality.get("validation")).get("status") if model_quality else None,
            "clean": model_quality_ok,
            "reason": model_quality_reason,
            "generated_at_utc": model_quality.get("generated_at_utc") if model_quality else None,
        },
        "otel_learning_loop": otel_summary,
        "otel_ops": otel_ops_context,
        "improvement_ledger": improvement_context,
        "skill_proposals": {
            "present": bool(improvements),
            "proposal_count": improvement_context.get("skill_proposal_count"),
            "pending_count": improvement_context.get("pending_skill_proposal_count"),
            "applied_count": improvement_context.get("applied_skill_proposal_count"),
            "relevant_pending_count": improvement_context.get("relevant_pending_skill_proposal_count"),
            "relevant_pending": improvement_context.get("relevant_pending_skill_proposals"),
            "wf74_skill_request_count": auto_patch_summary.get("skill_workshop_request_count"),
            "meaning": improvement_context.get("skill_proposal_meaning"),
        },
        "wf74_intelligence": autonomy_context,
        "isolated_agent_fleet": fleet_context,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "blockers": blockers,
        "warnings": warnings,
        "validation": {"status": "ok" if not blockers else "blocked", "errors": blockers, "warnings": warnings},
    }
    message = build_message(packet)
    delivery_messages = telegram_cli_safe_messages(message)
    packet["message_preview"] = message
    packet["delivery_chunk_count"] = len(delivery_messages) if should_notify and not blockers else 0
    packet["delivery_messages_preview"] = delivery_messages if should_notify and not blockers else []
    packet["sent_count"] = 0
    packet["send_result"] = None

    if args.send and packet["operator_action"] == "TELEGRAM_NOTIFY":
        results = [send_telegram(args.channel, args.target, item, args.timeout_seconds) for item in delivery_messages]
        ok = all(item.get("ok") for item in results)
        packet["send_result"] = {"ok": ok, "results": results}
        if ok:
            packet["sent_count"] = len(results)
            sent = as_dict(state.get("sent"))
            sent[packet["signature_hash"]] = {
                "sent_at_utc": packet["generated_at_utc"],
                "trigger_reason": trigger_reason,
                "summary": summary,
            }
            state["sent"] = sent
            state["last_signature_hash"] = packet["signature_hash"]
            state["last_owner_gated_proposal_ids"] = sig["owner_gated_proposal_ids"]
            state["last_summary"] = summary
            if args.write:
                atomic_write_json(args.state if args.state.is_absolute() else ROOT / args.state, state)
        else:
            packet["status"] = "blocked"
            packet["validation"]["status"] = "blocked"
            packet["validation"]["errors"].append("telegram_send_failed")
    elif args.write and packet["operator_action"] == "TELEGRAM_NOTIFY" and args.record_dry_run_state:
        state["last_signature_hash"] = packet["signature_hash"]
        state["last_owner_gated_proposal_ids"] = sig["owner_gated_proposal_ids"]
        state["last_summary"] = summary
        atomic_write_json(args.state if args.state.is_absolute() else ROOT / args.state, state)

    return packet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/send WF74 learning-loop Telegram delta digest.")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--auto-patch", type=Path, default=DEFAULT_AUTO_PATCH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--critical-review", type=Path, default=DEFAULT_CRITICAL_REVIEW)
    parser.add_argument("--model-quality-runner", type=Path, default=DEFAULT_MODEL_QUALITY)
    parser.add_argument("--otel-learning", type=Path, default=DEFAULT_OTEL_LEARNING)
    parser.add_argument("--improvements", type=Path, default=DEFAULT_IMPROVEMENTS)
    parser.add_argument("--autonomy-router", type=Path, default=DEFAULT_AUTONOMY_ROUTER)
    parser.add_argument("--decision-docket", type=Path, default=DEFAULT_DECISION_DOCKET)
    parser.add_argument("--otel-ops", type=Path, default=DEFAULT_OTEL_OPS)
    parser.add_argument("--tool-workflow", type=Path, default=DEFAULT_TOOL_WORKFLOW)
    parser.add_argument("--token-budget", type=Path, default=DEFAULT_TOKEN_BUDGET)
    parser.add_argument("--token-efficiency", type=Path, default=DEFAULT_TOKEN_EFFICIENCY)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--after-6pm-only", action="store_true", default=False)
    parser.add_argument("--record-dry-run-state", action="store_true")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--force-model-quality-block", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for attr in (
        "queue",
        "proposals",
        "auto_patch",
        "state",
        "output",
        "critical_review",
        "model_quality_runner",
        "otel_learning",
        "improvements",
        "autonomy_router",
        "decision_docket",
        "otel_ops",
        "tool_workflow",
        "token_budget",
        "token_efficiency",
    ):
        path = getattr(args, attr)
        if not path.is_absolute():
            setattr(args, attr, ROOT / path)
    packet = build_packet(args)
    if args.write:
        atomic_write_json(args.output, packet)
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        print(json.dumps({"status": "blocked", "errors": packet["validation"]["errors"], "output": rel(args.output)}, indent=2))
        return 1
    print(json.dumps({
        "status": packet["status"],
        "operator_action": packet["operator_action"],
        "trigger_reason": packet["trigger_reason"],
        "sent_count": packet["sent_count"],
        "summary": packet["summary"],
        "output": rel(args.output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
