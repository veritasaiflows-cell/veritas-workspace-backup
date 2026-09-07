#!/usr/bin/env python3
"""Build a compact startup brief from existing route packets.

This is a fast read-only pickup surface for simple greetings and status checks.
It avoids regenerating PM/cron/control packets unless the operator explicitly
asks elsewhere; generated packets remain routing proof, not canon or approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import project_implementation_router as implementation_router
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "startup-brief-packet.json"
SCHEMA = "veritas.startup_brief_packet.v1"

FUTURE_PACKET = TMP / "future-session-enhancement-packet.json"
PM_PACKET = TMP / "pm-control-packet.json"
CRON_PACKET = TMP / "cron-control-packet.json"
IMPROVEMENT_PACKET = TMP / "improvement-ledger-current.json"
WF74_OPPORTUNITY_PACKET = TMP / "wf74-improvement-opportunity-queue.json"
WF74_AUTO_PATCH_PACKET = TMP / "wf74-auto-patch-proposer.json"
WF74_DECISION_DOCKET_PACKET = TMP / "wf74-decision-docket.json"
OTEL_LEARNING_PACKET = TMP / "otel-learning-loop.json"
WORKFLOW_BLOCKER_FOLLOWUPS_PACKET = TMP / "workflow-blocker-followups.json"
TOKEN_USAGE_PACKET = TMP / "token-usage-ledger-current.json"
TOKEN_BUDGET_PACKET = TMP / "token-budget-status.json"
OWNER_GATED_PACKET = TMP / "owner-gated-action-review-queue.json"
ESCALATION_CONSUMER_PACKET = TMP / "main-session-escalation-consumer.json"
ACTION_EXECUTOR_PACKET = TMP / "main-session-action-executor.json"
PM_AUTONOMY_DISPATCHER_PACKET = TMP / "pm-autonomy-dispatcher.json"
PM_JOB_WORKER_PACKET = TMP / "pm-job-worker-runner.json"
PM_AUTONOMY_VERIFIER_PACKET = TMP / "pm-autonomy-verifier.json"
PM_MAIN_ACTION_INBOX_PACKET = TMP / "pm-main-session-action-inbox.json"
CRON_MIGRATION_REPAIR_PLAN_PACKET = TMP / "cron-migration-repair-plan.json"
WF88_WIKI_SYNTHESIS_PACKET = TMP / "wf88-wiki-synthesis-packet.json"
WIKI_BOOTSTRAP_PROOF_PACKET = TMP / "wiki-bootstrap-proof.json"
ACTIONABLE_QUEUE_PACKET = TMP / "actionable-improvement-queue.json"
NO_ORPHAN_VALIDATOR_PACKET = TMP / "no-orphan-validator.json"
FINANCE_SQL_GUARD_PACKET = TMP / "finance-sql-canon-access-validation.json"
ALERT_QUOTE_PACKET = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
ALERT_FRESHNESS_PACKET = TMP / "alert-level-freshness-controller.json"
ALERT_RECOMMENDATIONS_PACKET = TMP / "finance-alert-os-digest.json"
ALERTS_OS_PIVOT_PACKET = TMP / "alerts-os-pivot-validator.json"
CRON_MIGRATION_REPAIR_TITLE = "Route blocked cron signals into a migration-ready repair plan"
WORKFLOW_BLOCKER_FOLLOWUP_TITLE = "Convert workflow advancement blockers into implementation follow-ups"

RETIRED_FINANCE_ROUTE_MARKERS = (
    "wf67",
    "wf68",
    "wf78",
    "wf86",
    "wf87",
    "trade-grade",
    "trade_grade",
    "deployment-readiness",
    "deployment_readiness",
    "capital-deployment",
    "capital_deployment",
    "position-sizing",
    "position_sizing",
    "approval-card",
    "approval_card",
    "repair-conveyor",
    "repair_conveyor",
    "paper-position",
    "paper_position",
    "paper-state",
    "paper_state",
    "paper-autotrader",
    "paper_autotrader",
    "portfolio-config",
    "portfolio_config",
)

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routes_existing_packets_only": True,
    "regenerates_control_packets": False,
    "finance_state_mutation_allowed": False,
    "capital_or_execution_action_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

STATUS_ROUTE_CONTRACT = {
    "route_name": "shallow_status",
    "default_command": r"python scripts\status_card_packet.py --read-only --frontdoor --render --validate",
    "fallback_command": r"python scripts\startup_brief_packet.py --write --validate",
    "preferred_cached_artifact": "tmp/veritas-status-card-frontdoor.json",
    "drilldown_artifact": "tmp/veritas-status-card.json",
    "max_tool_calls": 1,
    "stop_after_packet": True,
    "reads_existing_packets_only": True,
    "status_card_read_only_default": True,
    "startup_brief_is_fallback_only": True,
    "regenerates_pm_or_cron_packets": False,
    "stale_inputs_are_summary_only": True,
    "current_pm_action_wins_over_stale_lane_digest": True,
    "surfaces_nested_validation_warnings": True,
    "drilldown_allowed_only_when": [
        "user asks for material workflow detail",
        "user asks to act on the next queue item",
        "startup packet validation is critical",
        "missing/stale input blocks a specific decision the user requested",
    ],
    "forbidden_for_shallow_status": [
        "pm_control_packet regeneration",
        "cron_control_packet regeneration",
        "workflow capsule drilldown",
        "daily memory or Active Workflows reads",
        "lane-register inspection",
        "runtime gateway/status commands",
    ],
}

FLEET_POSTURE_SCHEMA = "veritas.fleet_posture.v1"
CONFIGURED_ISOLATED_AGENT_IDS = [
    "research-scout",
    "qa-redteam",
    "finance-source-scout",
    "finance-redteam",
    "implementation-builder",
    "docs-continuity-editor",
]
FLEET_OPERATING_MODEL = {
    "main_agent_id": "main",
    "configured_total_agent_count": 7,
    "configured_isolated_agent_ids": CONFIGURED_ISOLATED_AGENT_IDS,
    "main_authority": {
        "routing_owner": True,
        "final_qc_owner": True,
        "sole_acceptance_owner": True,
        "final_judgment_owner": True,
        "isolated_agents_can_accept": False,
    },
    "general_route": "model-free first -> eligible explicit Codex-native -> explicit Main exception -> otherwise persistent Terra with fresh transport proof -> risk-budgeted QA -> Main acceptance",
    "finance_route": "Main -> Finance Source when needed -> Main analysis -> Finance Red-Team -> Main judgment",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def strip_retired_finance_routes(value: Any) -> Any:
    """Project startup state without carrying obsolete finance routes forward."""
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in RETIRED_FINANCE_ROUTE_MARKERS):
                continue
            projected = strip_retired_finance_routes(item)
            if projected is not None:
                cleaned[key] = projected
        return cleaned
    if isinstance(value, list):
        return [
            projected
            for item in value
            if (projected := strip_retired_finance_routes(item)) is not None
        ]
    if isinstance(value, str) and any(marker in value.lower() for marker in RETIRED_FINANCE_ROUTE_MARKERS):
        return None
    return value


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def wf74_opportunity_packet() -> Path:
    return TMP / "wf74-improvement-opportunity-queue.json"


def wf74_auto_patch_packet() -> Path:
    return TMP / "wf74-auto-patch-proposer.json"


def wf74_decision_docket_packet() -> Path:
    return TMP / "wf74-decision-docket.json"


def otel_learning_packet() -> Path:
    return TMP / "otel-learning-loop.json"


def workflow_blocker_followups_packet() -> Path:
    return TMP / "workflow-blocker-followups.json"


def cron_migration_repair_plan_packet() -> Path:
    return TMP / "cron-migration-repair-plan.json"


def artifact_age_seconds(path: Path, now: datetime) -> float | None:
    if not path.exists():
        return None
    return max(0.0, now.timestamp() - path.stat().st_mtime)


def path_state(path: Path, now: datetime) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.exists(),
        "age_seconds": artifact_age_seconds(path, now),
    }


def fleet_posture(token_budget: dict[str, Any], source_state: dict[str, Any]) -> dict[str, Any]:
    """Normalize an existing metadata-only fleet view for a fast startup brief."""
    fleet = as_dict(token_budget.get("fleet_usage"))
    summary = as_dict(fleet.get("summary"))
    capacity = as_dict(fleet.get("oauth_capacity_advisory"))
    sandbox = as_dict(fleet.get("sandbox_posture"))
    present = fleet.get("present") is True
    return {
        "schema": FLEET_POSTURE_SCHEMA,
        "status": fleet.get("status") if present else "unavailable",
        "generated_at_utc": fleet.get("generated_at_utc"),
        "source_state": source_state,
        "operating_model": FLEET_OPERATING_MODEL,
        "reporting": {
            key: summary.get(key)
            for key in (
                "configured_agent_count", "utilized_agent_count",
                "pricing_grade_attribution_coverage_percent",
                "parent_job_completed_count", "main_accepted_count",
                "main_acceptance_pending_count", "qa_review_completed_count",
                "qa_pass_count", "qa_yield_percent", "rework_count",
                "attribution_gap_count",
            )
        },
        "oauth_capacity_advisory": {
            key: capacity.get(key)
            for key in ("status", "tier", "remaining_percent", "reset_at_utc", "automatic_action_allowed")
        },
        "containment": {
            "status": sandbox.get("status") if sandbox else "not_reported",
            "source": "fleet_usage.sandbox_posture" if sandbox else "not_collected_by_startup_brief",
            "workspace_isolation_is_not_hard_sandbox": True,
            "hard_sandbox_proven": sandbox.get("hard_sandbox_proven") is True,
            "automatic_runtime_change_allowed": False,
        },
        "privacy_contract": {
            "metadata_only": True,
            "raw_prompt_stored": False,
            "raw_response_stored": False,
            "tool_payload_stored": False,
        },
        "billing_semantics": {
            "label": "API-equivalent benchmark",
            "api_equivalent_is_not_invoice": as_dict(fleet.get("billing_semantics")).get("api_equivalent_is_not_invoice") is True,
            "actual_billed_cost_usd": None,
        },
    }


def packet_validation_status(payload: dict[str, Any]) -> str | None:
    validation = as_dict(payload.get("validation"))
    status = validation.get("status")
    if isinstance(status, str):
        return status
    if validation.get("critical"):
        return "critical"
    if validation.get("warnings"):
        return "warning"
    return None


def packet_warning_reasons(name: str, payload: dict[str, Any]) -> list[str]:
    status = packet_validation_status(payload)
    if status not in {"warning", "critical", "blocked", "error"}:
        return []
    return [f"{name}.validation_{status}"]


def first_workflow(future_packet: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    for row in future_packet.get("workflow_capsules") or []:
        if isinstance(row, dict) and row.get("workflow_id") == workflow_id:
            return row
    return {}


def first_matching_opportunity(opportunities: list[dict[str, Any]], *, title: str | None = None, category: str | None = None) -> dict[str, Any]:
    for row in opportunities:
        if title and row.get("title") == title:
            return row
        if category and row.get("category") == category:
            return row
    return {}


def wf74_pickup_summary(queue: dict[str, Any], auto_patch: dict[str, Any], docket: dict[str, Any], followups: dict[str, Any], repair_plan: dict[str, Any]) -> dict[str, Any]:
    queue_summary = as_dict(queue.get("summary"))
    auto_patch_summary = as_dict(auto_patch.get("summary"))
    docket_summary = as_dict(docket.get("summary"))
    followup_summary = as_dict(followups.get("summary"))
    opportunities = [as_dict(row) for row in as_list(queue.get("opportunities"))]
    cron_opportunity = first_matching_opportunity(
        opportunities,
        title=CRON_MIGRATION_REPAIR_TITLE,
        category="cron_migration",
    )
    workflow_opportunity = first_matching_opportunity(opportunities, title=WORKFLOW_BLOCKER_FOLLOWUP_TITLE)
    followup_rows = [as_dict(row) for row in as_list(followups.get("followups"))]
    repair_plan_visible = bool(repair_plan) and repair_plan.get("status") in {"ok", "ready_for_main_session", "warning"}
    top_title = queue_summary.get("top_opportunity_title")
    top_display_title = top_title
    if top_title == WORKFLOW_BLOCKER_FOLLOWUP_TITLE and int(followup_summary.get("followup_count") or 0):
        top_display_title = "Close remaining workflow-maturity follow-ups"
    return {
        "opportunity_count": queue_summary.get("opportunity_count"),
        "high_priority_count": queue_summary.get("high_priority_count"),
        "top_opportunity_title": queue_summary.get("top_opportunity_title"),
        "top_opportunity_display_title": top_display_title,
        "cron_migration_repair_visible": bool(cron_opportunity),
        "cron_migration_repair_priority": cron_opportunity.get("priority"),
        "cron_migration_repair_followup_count": len([row for row in followup_rows if row.get("route") == "cron_migration"]),
        "cron_migration_repair_plan_visible": repair_plan_visible,
        "cron_migration_repair_plan_status": repair_plan.get("status"),
        "workflow_blocker_followup_visible": bool(workflow_opportunity),
        "workflow_blocker_followup_priority": workflow_opportunity.get("priority"),
        "workflow_blocker_followup_count": followup_summary.get("followup_count"),
        "workflow_blocker_followup_route_counts": followup_summary.get("route_counts"),
        "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count"),
        "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
        "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
        "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
        "decision_docket_status": docket.get("status"),
        "decision_docket_validation": packet_validation_status(docket),
        "decision_docket_row_count": docket_summary.get("row_count"),
        "decision_docket_active_action_count": docket_summary.get("active_action_count"),
        "decision_docket_fix_now_count": docket_summary.get("fix_now_count"),
        "decision_docket_owner_decision_count": docket_summary.get("owner_decision_count"),
        "decision_docket_market_session_accrual_count": docket_summary.get("market_session_accrual_count"),
        "decision_docket_monitor_only_count": docket_summary.get("monitor_only_count"),
        "decision_docket_hard_stop_count": docket_summary.get("hard_stop_count"),
        "decision_docket_next_safe_action": docket_summary.get("next_safe_action"),
    }


def otel_learning_pickup_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summaries = as_dict(packet.get("learning_summaries"))
    health = as_dict(summaries.get("otel_health"))
    cost = as_dict(summaries.get("token_cost"))
    carry_forward = as_dict(packet.get("carry_forward_contract"))
    auto_router = as_dict(packet.get("auto_implementation_router"))
    return {
        "status": packet.get("status"),
        "validation": packet_validation_status(packet),
        "collector_health": health.get("collector_health"),
        "drift_status": health.get("drift_status"),
        "token_coverage_ratio": cost.get("token_coverage_ratio"),
        "cost_coverage_ratio": cost.get("cost_coverage_ratio"),
        "recommendation_count": len([row for row in as_list(packet.get("recommendations")) if isinstance(row, dict)]),
        "carry_forward_status": carry_forward.get("status"),
        "auto_implementation_status": auto_router.get("status"),
        "next_safe_action": packet.get("next_safe_action") or carry_forward.get("next_safe_action"),
    }


def wf88_wiki_synthesis_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    leak = as_dict(packet.get("recommendation_leak_guard"))
    return {
        "status": packet.get("status"),
        "validation": validation.get("status"),
        "wiki_page_count": summary.get("wiki_page_count"),
        "self_prompt_count": summary.get("self_prompt_count"),
        "action_item_count": len(as_list(packet.get("action_items"))),
        "recommendation_leak_guard_pass": leak.get("pass"),
        "open_unrouted_recommendation_count": leak.get("open_unrouted_recommendation_count"),
        "auto_apply_count": leak.get("auto_apply_count"),
        "rsi_status": summary.get("rsi_status"),
        "followup_required_open_count": summary.get("followup_required_open_count"),
        "recommendation_later_outcome_graded_rows": summary.get("recommendation_later_outcome_graded_rows"),
        "next_safe_action": "Refresh WF88 wiki synthesis after material learning-loop changes; route warnings through WF74/PM instead of chat residue.",
    }


def wiki_bootstrap_proof_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    return {
        "present": bool(packet),
        "schema": packet.get("schema"),
        "status": packet.get("status"),
        "validation": validation.get("status"),
        "bootstrap_gate": summary.get("bootstrap_gate"),
        "required_file_count": summary.get("required_file_count"),
        "validated_file_count": summary.get("validated_file_count"),
        "missing_file_count": summary.get("missing_file_count"),
        "missing_marker_count": summary.get("missing_marker_count"),
        "missing_semantic_marker_count": summary.get("missing_semantic_marker_count"),
        "semantic_render_hash_match": summary.get("semantic_render_hash_match"),
        "recommendation_leak_guard_pass": summary.get("recommendation_leak_guard_pass"),
        "auto_apply_count": summary.get("auto_apply_count"),
        "no_orphan_validation": summary.get("no_orphan_validation"),
        "actionable_orphan_count": summary.get("actionable_orphan_count"),
        "actionable_missing_contract_count": summary.get("actionable_missing_contract_count"),
        "next_safe_action": summary.get("next_safe_action")
        or "Run wiki_bootstrap_validator before material WF74/WF88/OTEL work.",
    }


def alerts_os_summary() -> dict[str, Any]:
    sources = {
        "sql_guard": FINANCE_SQL_GUARD_PACKET,
        "quote_snapshot": ALERT_QUOTE_PACKET,
        "freshness_controller": ALERT_FRESHNESS_PACKET,
        "recommendations_digest": ALERT_RECOMMENDATIONS_PACKET,
        "pivot_validator": ALERTS_OS_PIVOT_PACKET,
    }
    proofs: dict[str, dict[str, Any]] = {}
    blocked: list[str] = []
    ticker_count = None
    alert_state_counts = None
    for name, path in sources.items():
        packet = load(path)
        validation_status = as_dict(packet.get("validation")).get("status")
        proof_ok = bool(packet) and packet.get("status") == "ok" and validation_status in {None, "ok"}
        if not proof_ok:
            blocked.append(name)
        summary = as_dict(packet.get("summary"))
        ticker_count = summary.get("ticker_count") or ticker_count
        alert_state_counts = summary.get("alert_state_counts") or alert_state_counts
        proofs[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "present": bool(packet),
            "status": packet.get("status"),
            "validation_status": validation_status,
            "generated_at_utc": packet.get("generated_at_utc"),
        }
    return {
        "status": "ok" if not blocked else "blocked",
        "blocked_proofs": blocked,
        "ticker_count": ticker_count,
        "alert_state_counts": alert_state_counts,
        "proofs": proofs,
    }


def build_payload(max_age_minutes: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    future = load(FUTURE_PACKET)
    pm = load(PM_PACKET)
    cron = load(CRON_PACKET)
    improvement = load(IMPROVEMENT_PACKET)
    wf74_queue = load(wf74_opportunity_packet())
    wf74_auto_patch = load(wf74_auto_patch_packet())
    wf74_docket = load(wf74_decision_docket_packet())
    otel_learning = load(otel_learning_packet())
    wf88_wiki_synthesis = load(WF88_WIKI_SYNTHESIS_PACKET)
    wiki_bootstrap_proof = load(WIKI_BOOTSTRAP_PROOF_PACKET)
    actionable_queue = load(ACTIONABLE_QUEUE_PACKET)
    no_orphan_validator = load(NO_ORPHAN_VALIDATOR_PACKET)
    workflow_followups = load(workflow_blocker_followups_packet())
    cron_migration_repair_plan = load(cron_migration_repair_plan_packet())
    token_usage = load(TOKEN_USAGE_PACKET)
    token_budget = load(TOKEN_BUDGET_PACKET)
    owner_gated = load(OWNER_GATED_PACKET)
    escalation_consumer = load(ESCALATION_CONSUMER_PACKET)
    action_executor = load(ACTION_EXECUTOR_PACKET)
    pm_autonomy_dispatcher = load(PM_AUTONOMY_DISPATCHER_PACKET)
    pm_job_worker = load(PM_JOB_WORKER_PACKET)
    pm_autonomy_verifier = load(PM_AUTONOMY_VERIFIER_PACKET)
    pm_action_inbox = load(PM_MAIN_ACTION_INBOX_PACKET)
    pm_summary = as_dict(pm.get("summary"))
    cron_summary = as_dict(cron.get("summary"))
    improvement_summary = as_dict(improvement.get("summary"))
    token_summary = as_dict(token_usage.get("summary"))
    owner_gated_summary = as_dict(owner_gated.get("summary"))
    actionable_summary = as_dict(actionable_queue.get("summary"))
    no_orphan_summary = as_dict(no_orphan_validator.get("summary"))
    escalation_consumer_summary = as_dict(escalation_consumer.get("summary"))
    finance_alerts = alerts_os_summary()
    implementation_queue = as_dict(pm_summary.get("implementation_queue"))
    pm_readiness = as_dict(pm_summary.get("pm_readiness"))
    wf74_pickup = wf74_pickup_summary(wf74_queue, wf74_auto_patch, wf74_docket, workflow_followups, cron_migration_repair_plan)
    otel_pickup = otel_learning_pickup_summary(otel_learning)
    wf88_wiki = wf88_wiki_synthesis_summary(wf88_wiki_synthesis)
    wiki_bootstrap = wiki_bootstrap_proof_summary(wiki_bootstrap_proof)
    future_execution_efficiency_policy = as_dict(future.get("execution_efficiency_policy"))
    execution_efficiency_policy = implementation_router.execution_efficiency_policy()
    future_efficiency_policy_matches_owner = future_execution_efficiency_policy == execution_efficiency_policy
    coding_outcome_efficiency = as_dict(future.get("coding_outcome_efficiency"))
    wf85 = first_workflow(future, "WF85")
    artifacts = {
        "future_session_packet": path_state(FUTURE_PACKET, now),
        "pm_control_packet": path_state(PM_PACKET, now),
        "cron_control_packet": path_state(CRON_PACKET, now),
        "improvement_ledger_packet": path_state(IMPROVEMENT_PACKET, now),
        "wf74_opportunity_packet": path_state(wf74_opportunity_packet(), now),
        "wf74_auto_patch_packet": path_state(wf74_auto_patch_packet(), now),
        "wf74_decision_docket_packet": path_state(wf74_decision_docket_packet(), now),
        "otel_learning_loop_packet": path_state(otel_learning_packet(), now),
        "wf88_wiki_synthesis_packet": path_state(WF88_WIKI_SYNTHESIS_PACKET, now),
        "wiki_bootstrap_proof_packet": path_state(WIKI_BOOTSTRAP_PROOF_PACKET, now),
        "actionable_improvement_queue": path_state(ACTIONABLE_QUEUE_PACKET, now),
        "no_orphan_validator": path_state(NO_ORPHAN_VALIDATOR_PACKET, now),
        "workflow_blocker_followups_packet": path_state(workflow_blocker_followups_packet(), now),
        "cron_migration_repair_plan_packet": path_state(cron_migration_repair_plan_packet(), now),
        "token_usage_ledger_packet": path_state(TOKEN_USAGE_PACKET, now),
        "token_budget_status_packet": path_state(TOKEN_BUDGET_PACKET, now),
        "owner_gated_action_review_queue": path_state(OWNER_GATED_PACKET, now),
        "main_session_escalation_consumer": path_state(ESCALATION_CONSUMER_PACKET, now),
        "main_session_action_executor": path_state(ACTION_EXECUTOR_PACKET, now),
        "pm_autonomy_dispatcher": path_state(PM_AUTONOMY_DISPATCHER_PACKET, now),
        "pm_job_worker_runner": path_state(PM_JOB_WORKER_PACKET, now),
        "pm_autonomy_verifier": path_state(PM_AUTONOMY_VERIFIER_PACKET, now),
        "pm_main_session_action_inbox": path_state(PM_MAIN_ACTION_INBOX_PACKET, now),
        "finance_sql_guard": path_state(FINANCE_SQL_GUARD_PACKET, now),
        "alert_quote_snapshot": path_state(ALERT_QUOTE_PACKET, now),
        "alert_freshness_controller": path_state(ALERT_FRESHNESS_PACKET, now),
        "alert_recommendations_digest": path_state(ALERT_RECOMMENDATIONS_PACKET, now),
        "alerts_os_pivot_validator": path_state(ALERTS_OS_PIVOT_PACKET, now),
    }
    optional_inputs = {
        "wf74_opportunity_packet",
        "wf74_auto_patch_packet",
        "wf74_decision_docket_packet",
        "workflow_blocker_followups_packet",
        "cron_migration_repair_plan_packet",
        "token_budget_status_packet",
    }
    cron_blocked_or_escalated = int(cron_summary.get("blocked_count") or 0) + int(cron_summary.get("escalation_signal_count") or 0)
    stale = [
        key
        for key, state in artifacts.items()
        if (
            key not in optional_inputs
            or cron_blocked_or_escalated
        )
        and (state.get("age_seconds") is None or state.get("age_seconds", 0) > max_age_minutes * 60)
    ]
    validation_warnings = []
    for name, packet in [
        ("future_session_packet", future),
        ("pm_control_packet", pm),
        ("cron_control_packet", cron),
        ("improvement_ledger_packet", improvement),
        ("otel_learning_loop_packet", otel_learning),
        ("wf88_wiki_synthesis_packet", wf88_wiki_synthesis),
        ("wiki_bootstrap_proof_packet", wiki_bootstrap_proof),
        ("actionable_improvement_queue", actionable_queue),
        ("no_orphan_validator", no_orphan_validator),
        ("wf74_decision_docket_packet", wf74_docket),
        ("main_session_escalation_consumer", escalation_consumer),
        ("main_session_action_executor", action_executor),
        ("pm_autonomy_dispatcher", pm_autonomy_dispatcher),
        ("pm_job_worker_runner", pm_job_worker),
        ("pm_autonomy_verifier", pm_autonomy_verifier),
    ]:
        validation_warnings.extend(packet_warning_reasons(name, packet))
    if not future_efficiency_policy_matches_owner:
        validation_warnings.append("future_session_packet.execution_efficiency_policy_owner_mismatch")
    fleet = fleet_posture(token_budget, artifacts["token_budget_status_packet"])
    payload_status = "stale_input_warning" if stale else "warning" if validation_warnings else "ok"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": payload_status,
        "purpose": "Fast startup/status brief from existing route packets.",
        "max_age_minutes": max_age_minutes,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "status_route_contract": STATUS_ROUTE_CONTRACT.copy(),
        "inputs": artifacts,
        "fleet_posture": fleet,
        "execution_efficiency_policy": execution_efficiency_policy,
        "execution_efficiency_policy_source": "scripts/project_implementation_router.py",
        "future_efficiency_policy_matches_owner": future_efficiency_policy_matches_owner,
        "coding_outcome_efficiency": coding_outcome_efficiency,
        "summary": {
            "identity": "Veritas, Randall's finance-first market-intelligence chief of staff and workflow/decision-support operator.",
            "primary_goal": "Alerts and Recommendations OS",
            "wf85_status": wf85.get("effective_status"),
            "pm_status": pm.get("status"),
            "pm_readiness_band": pm_readiness.get("readiness_band"),
            "pm_ready_job_count": implementation_queue.get("ready_job_count"),
            "pm_blocked_job_count": implementation_queue.get("blocked_job_count"),
            "cron_status": cron.get("status"),
            "cron_escalation_signal_count": cron_summary.get("escalation_signal_count"),
            "cron_blocked_count": cron_summary.get("blocked_count"),
            "improvement_ledger_status": improvement.get("status"),
            "improvement_open_count": improvement_summary.get("latest_open_count"),
            "improvement_high_priority_open_count": improvement_summary.get("high_priority_open_count"),
            "improvement_overdue_open_count": improvement_summary.get("overdue_open_count"),
            "improvement_due_soon_open_count": improvement_summary.get("due_soon_open_count"),
            "improvement_high_priority_overdue_open_count": improvement_summary.get("high_priority_overdue_open_count"),
            "improvement_escalation_level": improvement_summary.get("escalation_level"),
            "improvement_top_title": improvement_summary.get("top_improvement_title"),
            "improvement_top_next_action": improvement_summary.get("top_improvement_next_action"),
            "improvement_top_age_hours": improvement_summary.get("top_improvement_age_hours"),
            "improvement_top_sla_status": improvement_summary.get("top_improvement_sla_status"),
            "wf74_opportunity_count": wf74_pickup.get("opportunity_count"),
            "wf74_high_priority_opportunity_count": wf74_pickup.get("high_priority_count"),
            "wf74_top_opportunity_title": wf74_pickup.get("top_opportunity_title"),
            "wf74_top_opportunity_display_title": wf74_pickup.get("top_opportunity_display_title"),
            "wf74_cron_migration_repair_visible": wf74_pickup.get("cron_migration_repair_visible"),
            "wf74_cron_migration_repair_priority": wf74_pickup.get("cron_migration_repair_priority"),
            "wf74_cron_migration_repair_followup_count": wf74_pickup.get("cron_migration_repair_followup_count"),
            "wf74_cron_migration_repair_plan_visible": wf74_pickup.get("cron_migration_repair_plan_visible"),
            "wf74_cron_migration_repair_plan_status": wf74_pickup.get("cron_migration_repair_plan_status"),
            "wf74_workflow_blocker_followup_visible": wf74_pickup.get("workflow_blocker_followup_visible"),
            "wf74_workflow_blocker_followup_priority": wf74_pickup.get("workflow_blocker_followup_priority"),
            "wf74_workflow_blocker_followup_count": wf74_pickup.get("workflow_blocker_followup_count"),
            "wf74_workflow_blocker_followup_route_counts": wf74_pickup.get("workflow_blocker_followup_route_counts"),
            "wf74_auto_patch_patch_plan_count": wf74_pickup.get("auto_patch_patch_plan_count"),
            "wf74_auto_patch_skill_workshop_request_count": wf74_pickup.get("auto_patch_skill_workshop_request_count"),
            "wf74_auto_patch_owner_gated_plan_count": wf74_pickup.get("auto_patch_owner_gated_plan_count"),
            "wf74_auto_patch_auto_apply_count": wf74_pickup.get("auto_patch_auto_apply_count"),
            "wf74_decision_docket_row_count": wf74_pickup.get("decision_docket_row_count"),
            "wf74_decision_docket_active_action_count": wf74_pickup.get("decision_docket_active_action_count"),
            "wf74_decision_docket_fix_now_count": wf74_pickup.get("decision_docket_fix_now_count"),
            "wf74_decision_docket_owner_decision_count": wf74_pickup.get("decision_docket_owner_decision_count"),
            "wf74_decision_docket_market_session_accrual_count": wf74_pickup.get("decision_docket_market_session_accrual_count"),
            "wf74_decision_docket_monitor_only_count": wf74_pickup.get("decision_docket_monitor_only_count"),
            "wf74_decision_docket_hard_stop_count": wf74_pickup.get("decision_docket_hard_stop_count"),
            "wf74_decision_docket_next_safe_action": wf74_pickup.get("decision_docket_next_safe_action"),
            "otel_learning_loop_status": otel_pickup.get("status"),
            "otel_learning_loop_validation": otel_pickup.get("validation"),
            "otel_collector_health": otel_pickup.get("collector_health"),
            "otel_drift_status": otel_pickup.get("drift_status"),
            "otel_token_coverage_ratio": otel_pickup.get("token_coverage_ratio"),
            "otel_cost_coverage_ratio": otel_pickup.get("cost_coverage_ratio"),
            "otel_recommendation_count": otel_pickup.get("recommendation_count"),
            "otel_carry_forward_status": otel_pickup.get("carry_forward_status"),
            "otel_auto_implementation_status": otel_pickup.get("auto_implementation_status"),
            "otel_next_safe_action": otel_pickup.get("next_safe_action"),
            "wf88_wiki_synthesis_status": wf88_wiki.get("status"),
            "wf88_wiki_synthesis_validation": wf88_wiki.get("validation"),
            "wf88_wiki_page_count": wf88_wiki.get("wiki_page_count"),
            "wf88_wiki_self_prompt_count": wf88_wiki.get("self_prompt_count"),
            "wf88_wiki_action_item_count": wf88_wiki.get("action_item_count"),
            "wf88_wiki_recommendation_leak_guard_pass": wf88_wiki.get("recommendation_leak_guard_pass"),
            "wf88_wiki_open_unrouted_recommendation_count": wf88_wiki.get("open_unrouted_recommendation_count"),
            "wf88_wiki_auto_apply_count": wf88_wiki.get("auto_apply_count"),
            "wf88_wiki_rsi_status": wf88_wiki.get("rsi_status"),
            "wf88_wiki_followup_required_open_count": wf88_wiki.get("followup_required_open_count"),
            "wf88_wiki_recommendation_later_outcome_graded_rows": wf88_wiki.get("recommendation_later_outcome_graded_rows"),
            "wf88_wiki_next_safe_action": wf88_wiki.get("next_safe_action"),
            "wiki_bootstrap_present": wiki_bootstrap.get("present"),
            "wiki_bootstrap_schema": wiki_bootstrap.get("schema"),
            "wiki_bootstrap_status": wiki_bootstrap.get("status"),
            "wiki_bootstrap_validation": wiki_bootstrap.get("validation"),
            "wiki_bootstrap_gate": wiki_bootstrap.get("bootstrap_gate"),
            "wiki_bootstrap_required_file_count": wiki_bootstrap.get("required_file_count"),
            "wiki_bootstrap_validated_file_count": wiki_bootstrap.get("validated_file_count"),
            "wiki_bootstrap_missing_file_count": wiki_bootstrap.get("missing_file_count"),
            "wiki_bootstrap_missing_marker_count": wiki_bootstrap.get("missing_marker_count"),
            "wiki_bootstrap_missing_semantic_marker_count": wiki_bootstrap.get("missing_semantic_marker_count"),
            "wiki_bootstrap_semantic_render_hash_match": wiki_bootstrap.get("semantic_render_hash_match"),
            "wiki_bootstrap_recommendation_leak_guard_pass": wiki_bootstrap.get("recommendation_leak_guard_pass"),
            "wiki_bootstrap_auto_apply_count": wiki_bootstrap.get("auto_apply_count"),
            "wiki_bootstrap_no_orphan_validation": wiki_bootstrap.get("no_orphan_validation"),
            "wiki_bootstrap_actionable_orphan_count": wiki_bootstrap.get("actionable_orphan_count"),
            "wiki_bootstrap_actionable_missing_contract_count": wiki_bootstrap.get("actionable_missing_contract_count"),
            "wiki_bootstrap_next_safe_action": wiki_bootstrap.get("next_safe_action"),
            "execution_efficiency_policy_schema": execution_efficiency_policy.get("schema"),
            "execution_efficiency_material_dispatch_ready": execution_efficiency_policy == implementation_router.execution_efficiency_policy(),
            "future_efficiency_policy_matches_owner": future_efficiency_policy_matches_owner,
            "execution_efficiency_route_conformant_count": coding_outcome_efficiency.get("route_conformant_count"),
            "execution_efficiency_route_mismatch_count": coding_outcome_efficiency.get("route_mismatch_count"),
            "execution_efficiency_comparable_cohort_count": coding_outcome_efficiency.get("comparable_cohort_count"),
            "execution_efficiency_eligible_cohort_count": coding_outcome_efficiency.get("eligible_cohort_count"),
            "actionable_queue_status": actionable_queue.get("status"),
            "actionable_queue_validation": as_dict(actionable_queue.get("validation")).get("status"),
            "actionable_queue_item_count": actionable_summary.get("action_item_count"),
            "actionable_queue_orphan_count": actionable_summary.get("orphan_count"),
            "actionable_queue_missing_contract_count": actionable_summary.get("missing_contract_count"),
            "actionable_queue_owner_decision_count": actionable_summary.get("owner_decision_count"),
            "actionable_queue_monitor_only_count": actionable_summary.get("monitor_only_count"),
            "actionable_queue_top_action_title": actionable_summary.get("top_action_title"),
            "actionable_queue_top_action_destination": actionable_summary.get("top_action_destination"),
            "actionable_queue_top_next_action": actionable_summary.get("top_next_action"),
            "no_orphan_validator_status": no_orphan_validator.get("status"),
            "no_orphan_validator_validation": as_dict(no_orphan_validator.get("validation")).get("status"),
            "no_orphan_validation_passed": no_orphan_summary.get("validation_passed"),
            "token_usage_status": token_usage.get("status"),
            "token_usage_event_count": token_summary.get("token_event_count"),
            "token_usage_total_tokens": token_summary.get("total_tokens"),
            "token_usage_cron_event_count": token_summary.get("cron_token_event_count"),
            "token_usage_implementation_event_count": token_summary.get("implementation_token_event_count"),
            "token_usage_implementation_gap_count": token_summary.get("implementation_token_gap_count"),
            "token_usage_pricing_status": token_summary.get("pricing_status"),
            "fleet_status": fleet.get("status"),
            "fleet_configured_agent_count": as_dict(fleet.get("reporting")).get("configured_agent_count"),
            "fleet_utilized_agent_count": as_dict(fleet.get("reporting")).get("utilized_agent_count"),
            "fleet_pricing_grade_attribution_coverage_percent": as_dict(fleet.get("reporting")).get("pricing_grade_attribution_coverage_percent"),
            "fleet_main_accepted_count": as_dict(fleet.get("reporting")).get("main_accepted_count"),
            "fleet_qa_pass_count": as_dict(fleet.get("reporting")).get("qa_pass_count"),
            "fleet_qa_review_completed_count": as_dict(fleet.get("reporting")).get("qa_review_completed_count"),
            "fleet_rework_count": as_dict(fleet.get("reporting")).get("rework_count"),
            "fleet_attribution_gap_count": as_dict(fleet.get("reporting")).get("attribution_gap_count"),
            "fleet_oauth_capacity_status": as_dict(fleet.get("oauth_capacity_advisory")).get("status"),
            "fleet_oauth_remaining_percent": as_dict(fleet.get("oauth_capacity_advisory")).get("remaining_percent"),
            "fleet_sandbox_status": as_dict(fleet.get("containment")).get("status"),
            "owner_gated_review_status": owner_gated.get("status"),
            "owner_gated_item_count": owner_gated_summary.get("item_count"),
            "owner_gated_decision_required_count": owner_gated_summary.get("owner_decision_required_count"),
            "owner_gated_top_gate": owner_gated_summary.get("top_gate"),
            "owner_gated_top_title": owner_gated_summary.get("top_title"),
            "owner_gated_next_safe_action": owner_gated_summary.get("next_safe_action"),
            "main_session_escalation_consumer_status": escalation_consumer.get("status"),
            "main_session_escalation_consumer_executed_safe_action_count": escalation_consumer_summary.get("executed_safe_action_count"),
            "main_session_escalation_consumer_unresolved_count": escalation_consumer_summary.get("unresolved_count"),
            "main_session_escalation_consumer_owner_decision_count": escalation_consumer_summary.get("owner_decision_count"),
            "main_session_escalation_consumer_repeated_blocker_count": escalation_consumer_summary.get("repeated_blocker_count"),
            "main_session_escalation_consumer_next_safe_action": escalation_consumer_summary.get("next_safe_action"),
            "main_session_action_executor_status": action_executor.get("status"),
            "pm_autonomy_dispatcher_status": pm_autonomy_dispatcher.get("status"),
            "pm_job_worker_status": pm_job_worker.get("status"),
            "pm_autonomy_verifier_status": pm_autonomy_verifier.get("status"),
            "pm_main_action_inbox_status": pm_action_inbox.get("status"),
            "finance_alerts_os_status": finance_alerts.get("status"),
            "finance_alerts_os_blocked_proofs": finance_alerts.get("blocked_proofs"),
            "finance_alerts_os_ticker_count": finance_alerts.get("ticker_count"),
            "finance_alerts_os_state_counts": finance_alerts.get("alert_state_counts"),
        },
        "finance_alerts_os": finance_alerts,
        "recommended_next_action": (
            "For simple greetings or shallow status checks, answer from this packet and stop. "
            "Refresh PM/cron/future-session packets only when the user asks for material workflow action/detail, "
            "validation is critical, or stale inputs block a specific requested decision."
        ),
        "stale_inputs": stale,
        "input_validation_warnings": validation_warnings,
        "validation": {"status": "pending", "errors": []},
    }
    for key in ("summary", "coding_outcome_efficiency", "fleet_posture", "input_validation_warnings"):
        payload[key] = strip_retired_finance_routes(payload.get(key))
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "critical"
    return payload


def validate(boundary: dict[str, Any]) -> dict[str, Any]:
    errors = [
        key for key, expected in AUTHORITY_BOUNDARY.items()
        if boundary.get(key) is not expected
    ]
    if STATUS_ROUTE_CONTRACT.get("max_tool_calls") != 1:
        errors.append("status_route_contract.max_tool_calls")
    if STATUS_ROUTE_CONTRACT.get("stop_after_packet") is not True:
        errors.append("status_route_contract.stop_after_packet")
    if STATUS_ROUTE_CONTRACT.get("status_card_read_only_default") is not True:
        errors.append("status_route_contract.status_card_read_only_default")
    if STATUS_ROUTE_CONTRACT.get("startup_brief_is_fallback_only") is not True:
        errors.append("status_route_contract.startup_brief_is_fallback_only")
    if STATUS_ROUTE_CONTRACT.get("regenerates_pm_or_cron_packets") is not False:
        errors.append("status_route_contract.regenerates_pm_or_cron_packets")
    if STATUS_ROUTE_CONTRACT.get("current_pm_action_wins_over_stale_lane_digest") is not True:
        errors.append("status_route_contract.current_pm_action_wins_over_stale_lane_digest")
    if STATUS_ROUTE_CONTRACT.get("surfaces_nested_validation_warnings") is not True:
        errors.append("status_route_contract.surfaces_nested_validation_warnings")
    return {"status": "critical" if errors else "ok", "errors": errors}


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors = list(validate(as_dict(payload.get("authority_boundary")))["errors"])
    summary = as_dict(payload.get("summary"))
    efficiency_policy = as_dict(payload.get("execution_efficiency_policy"))
    if efficiency_policy != implementation_router.execution_efficiency_policy():
        errors.append("execution_efficiency_policy.owner_mismatch")
    quality_efficiency = as_dict(efficiency_policy.get("quality_weighted_efficiency"))
    if (
        quality_efficiency.get("evaluation_mode")
        != "owner_directed_on_demand_evidence_review"
        or quality_efficiency.get("cohort_pilot_required") is not False
        or quality_efficiency.get("minimum_jobs_for_on_demand_review") != 0
    ):
        errors.append("execution_efficiency_policy.on_demand_review_contract_invalid")
    if quality_efficiency.get("automatic_route_promotion_allowed") is not False:
        errors.append("execution_efficiency_policy.auto_promotion_not_disabled")
    fleet = as_dict(payload.get("fleet_posture"))
    if fleet.get("schema") != FLEET_POSTURE_SCHEMA:
        errors.append("fleet_posture.schema_invalid")
    fleet_model = as_dict(fleet.get("operating_model"))
    fleet_authority = as_dict(fleet_model.get("main_authority"))
    if fleet_model.get("main_agent_id") != "main" or fleet_model.get("configured_total_agent_count") != 7:
        errors.append("fleet_posture.operating_model_invalid")
    for key, expected in FLEET_OPERATING_MODEL["main_authority"].items():
        if fleet_authority.get(key) is not expected:
            errors.append(f"fleet_posture.main_authority.{key}")
    containment = as_dict(fleet.get("containment"))
    if containment.get("workspace_isolation_is_not_hard_sandbox") is not True:
        errors.append("fleet_posture.workspace_isolation_limit_missing")
    if containment.get("automatic_runtime_change_allowed") is not False:
        errors.append("fleet_posture.automatic_runtime_change_allowed")
    privacy = as_dict(fleet.get("privacy_contract"))
    for key in ("metadata_only",):
        if privacy.get(key) is not True:
            errors.append(f"fleet_posture.{key}_not_true")
    for key in ("raw_prompt_stored", "raw_response_stored", "tool_payload_stored"):
        if privacy.get(key) is not False:
            errors.append(f"fleet_posture.{key}_not_false")
    cron_blocked_or_escalated = int(summary.get("cron_blocked_count") or 0) + int(summary.get("cron_escalation_signal_count") or 0)
    if cron_blocked_or_escalated and not summary.get("wf74_cron_migration_repair_visible"):
        errors.append("wf74_pickup.missing_cron_migration_repair")
    if (
        summary.get("wf74_cron_migration_repair_visible")
        and int(summary.get("wf74_cron_migration_repair_followup_count") or 0) == 0
        and not summary.get("wf74_cron_migration_repair_plan_visible")
    ):
        errors.append("wf74_pickup.missing_cron_migration_followup")
    if summary.get("wf74_workflow_blocker_followup_visible") and int(summary.get("wf74_workflow_blocker_followup_count") or 0) == 0:
        errors.append("wf74_pickup.missing_workflow_blocker_followups")
    if int(summary.get("wf74_auto_patch_auto_apply_count") or 0):
        errors.append("wf74_pickup.auto_apply_nonzero")
    if summary.get("wf88_wiki_synthesis_validation") == "blocked":
        errors.append("wf88_wiki_synthesis.validation_blocked")
    if summary.get("wf88_wiki_recommendation_leak_guard_pass") is False:
        errors.append("wf88_wiki_synthesis.recommendation_leak_guard_failed")
    if int(summary.get("wf88_wiki_auto_apply_count") or 0):
        errors.append("wf88_wiki_synthesis.auto_apply_nonzero")
    if summary.get("wiki_bootstrap_present") is not True:
        errors.append("wiki_bootstrap_proof.missing")
    if summary.get("wiki_bootstrap_schema") != "veritas.wiki_bootstrap_proof.v2":
        errors.append("wiki_bootstrap_proof.semantic_contract_schema_missing")
    if summary.get("wiki_bootstrap_validation") == "blocked":
        errors.append("wiki_bootstrap_proof.validation_blocked")
    if int(summary.get("wiki_bootstrap_missing_file_count") or 0):
        errors.append("wiki_bootstrap_proof.missing_file_count_nonzero")
    if int(summary.get("wiki_bootstrap_missing_marker_count") or 0):
        errors.append("wiki_bootstrap_proof.missing_marker_count_nonzero")
    if int(summary.get("wiki_bootstrap_missing_semantic_marker_count") or 0):
        errors.append("wiki_bootstrap_proof.missing_semantic_marker_count_nonzero")
    if summary.get("wiki_bootstrap_semantic_render_hash_match") is not True:
        errors.append("wiki_bootstrap_proof.semantic_render_hash_mismatch")
    if summary.get("wiki_bootstrap_recommendation_leak_guard_pass") is False:
        errors.append("wiki_bootstrap_proof.recommendation_leak_guard_failed")
    if int(summary.get("wiki_bootstrap_auto_apply_count") or 0):
        errors.append("wiki_bootstrap_proof.auto_apply_nonzero")
    if summary.get("wiki_bootstrap_no_orphan_validation") == "blocked":
        errors.append("wiki_bootstrap_proof.no_orphan_validation_blocked")
    if int(summary.get("wiki_bootstrap_actionable_orphan_count") or 0):
        errors.append("wiki_bootstrap_proof.actionable_orphan_count_nonzero")
    if int(summary.get("wiki_bootstrap_actionable_missing_contract_count") or 0):
        errors.append("wiki_bootstrap_proof.actionable_missing_contract_count_nonzero")
    if int(summary.get("actionable_queue_orphan_count") or 0):
        errors.append("actionable_queue.orphan_count_nonzero")
    if int(summary.get("actionable_queue_missing_contract_count") or 0):
        errors.append("actionable_queue.missing_contract_count_nonzero")
    if summary.get("no_orphan_validator_validation") == "blocked":
        errors.append("no_orphan_validator.validation_blocked")
    if summary.get("finance_alerts_os_status") != "ok":
        errors.append("finance_alerts_os.proof_blocked")
    return {"status": "critical" if errors else "ok", "errors": errors}


def render_text(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    route = as_dict(payload.get("status_route_contract"))
    return "\n".join([
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')}",
        f"route={route.get('route_name')} command=\"{route.get('default_command')}\" max_tool_calls={route.get('max_tool_calls')} stop_after_packet={route.get('stop_after_packet')}",
        f"primary={summary.get('primary_goal')} wf85={summary.get('wf85_status')}",
        f"pm={summary.get('pm_status')} readiness={summary.get('pm_readiness_band')} ready_jobs={summary.get('pm_ready_job_count')} blocked_jobs={summary.get('pm_blocked_job_count')}",
        f"cron={summary.get('cron_status')} escalation={summary.get('cron_escalation_signal_count')} blocked={summary.get('cron_blocked_count')}",
        f"improvements={summary.get('improvement_ledger_status')} open={summary.get('improvement_open_count')} high={summary.get('improvement_high_priority_open_count')} overdue={summary.get('improvement_overdue_open_count')} escalation={summary.get('improvement_escalation_level')} top={summary.get('improvement_top_title')}",
        f"wf74_pickup=top:{summary.get('wf74_top_opportunity_display_title') or summary.get('wf74_top_opportunity_title')} high={summary.get('wf74_high_priority_opportunity_count')} cron_visible={summary.get('wf74_cron_migration_repair_visible')} cron_followups={summary.get('wf74_cron_migration_repair_followup_count')} workflow_visible={summary.get('wf74_workflow_blocker_followup_visible')} workflow_followups={summary.get('wf74_workflow_blocker_followup_count')} auto_apply={summary.get('wf74_auto_patch_auto_apply_count')}",
        f"otel=status:{summary.get('otel_learning_loop_status')} drift={summary.get('otel_drift_status')} recs={summary.get('otel_recommendation_count')} carry={summary.get('otel_carry_forward_status')} auto_route={summary.get('otel_auto_implementation_status')}",
        f"wf88_wiki=status:{summary.get('wf88_wiki_synthesis_status')} validation={summary.get('wf88_wiki_synthesis_validation')} pages={summary.get('wf88_wiki_page_count')} prompts={summary.get('wf88_wiki_self_prompt_count')} leak_guard={summary.get('wf88_wiki_recommendation_leak_guard_pass')} auto_apply={summary.get('wf88_wiki_auto_apply_count')} rsi={summary.get('wf88_wiki_rsi_status')} followup_required={summary.get('wf88_wiki_followup_required_open_count')}",
        f"wiki_bootstrap=status:{summary.get('wiki_bootstrap_status')} validation={summary.get('wiki_bootstrap_validation')} gate={summary.get('wiki_bootstrap_gate')} files={summary.get('wiki_bootstrap_validated_file_count')}/{summary.get('wiki_bootstrap_required_file_count')} missing_markers={summary.get('wiki_bootstrap_missing_marker_count')} missing_semantics={summary.get('wiki_bootstrap_missing_semantic_marker_count')} semantic_hash_match={summary.get('wiki_bootstrap_semantic_render_hash_match')} leak_guard={summary.get('wiki_bootstrap_recommendation_leak_guard_pass')} auto_apply={summary.get('wiki_bootstrap_auto_apply_count')} no_orphan={summary.get('wiki_bootstrap_no_orphan_validation')}",
        f"implementation_efficiency=policy:{summary.get('execution_efficiency_policy_schema')} material_dispatch_ready={summary.get('execution_efficiency_material_dispatch_ready')} conformant={summary.get('execution_efficiency_route_conformant_count')} mismatches={summary.get('execution_efficiency_route_mismatch_count')} cohorts={summary.get('execution_efficiency_comparable_cohort_count')} eligible={summary.get('execution_efficiency_eligible_cohort_count')}",
        f"actionable_queue=status:{summary.get('actionable_queue_status')} validation={summary.get('actionable_queue_validation')} items={summary.get('actionable_queue_item_count')} orphans={summary.get('actionable_queue_orphan_count')} monitor={summary.get('actionable_queue_monitor_only_count')} no_orphan={summary.get('no_orphan_validator_validation')}",
        f"tokens={summary.get('token_usage_status')} events={summary.get('token_usage_event_count')} total={summary.get('token_usage_total_tokens')} implementation_gaps={summary.get('token_usage_implementation_gap_count')}",
        f"fleet=status:{summary.get('fleet_status')} utilized={summary.get('fleet_utilized_agent_count')}/{summary.get('fleet_configured_agent_count')} pricing_grade={summary.get('fleet_pricing_grade_attribution_coverage_percent')}% Main_accepted={summary.get('fleet_main_accepted_count')} QA={summary.get('fleet_qa_pass_count')}/{summary.get('fleet_qa_review_completed_count')} rework={summary.get('fleet_rework_count')} gaps={summary.get('fleet_attribution_gap_count')} oauth={summary.get('fleet_oauth_capacity_status')}:{summary.get('fleet_oauth_remaining_percent')}% sandbox={summary.get('fleet_sandbox_status')}",
        f"owner_gated={summary.get('owner_gated_review_status')} decisions={summary.get('owner_gated_decision_required_count')} top={summary.get('owner_gated_top_gate')}:{summary.get('owner_gated_top_title')}",
        f"escalation_consumer={summary.get('main_session_escalation_consumer_status')} safe_actions={summary.get('main_session_escalation_consumer_executed_safe_action_count')} unresolved={summary.get('main_session_escalation_consumer_unresolved_count')} owner_decisions={summary.get('main_session_escalation_consumer_owner_decision_count')} repeated={summary.get('main_session_escalation_consumer_repeated_blocker_count')}",
        f"orchestration=executor:{summary.get('main_session_action_executor_status')} dispatcher:{summary.get('pm_autonomy_dispatcher_status')} worker:{summary.get('pm_job_worker_status')} verifier:{summary.get('pm_autonomy_verifier_status')} inbox:{summary.get('pm_main_action_inbox_status')}",
        f"finance_alerts_os={summary.get('finance_alerts_os_status')} tickers={summary.get('finance_alerts_os_ticker_count')} states={summary.get('finance_alerts_os_state_counts')} blocked_proofs={summary.get('finance_alerts_os_blocked_proofs')}",
        f"stale_inputs={','.join(payload.get('stale_inputs') or [])}",
        f"input_validation_warnings={','.join(payload.get('input_validation_warnings') or [])}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact read-only startup brief packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--max-age-minutes", type=int, default=90)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload(args.max_age_minutes)
    if args.write:
        atomic_write_json(args.out, payload)
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.validate and payload.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
