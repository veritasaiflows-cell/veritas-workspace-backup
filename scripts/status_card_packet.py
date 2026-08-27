#!/usr/bin/env python3
"""Build and render a cached Veritas status card.

The chat path should read this cached card instead of regenerating PM, cron,
workflow, memory, or lane-register surfaces. The writer assembles a compact
card from existing packets; the read-only renderer refuses to write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import project_implementation_router as implementation_router
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
MEMORY = ROOT / "memory"
OUT = TMP / "veritas-status-card.json"
FRONTDOOR_OUT = TMP / "veritas-status-card-frontdoor.json"
STARTUP_PACKET = TMP / "startup-brief-packet.json"
PM_PACKET = TMP / "pm-control-packet.json"
CRON_PACKET = TMP / "cron-control-packet.json"
FUTURE_PACKET = TMP / "future-session-enhancement-packet.json"
TOKEN_USAGE_PACKET = TMP / "token-usage-ledger-current.json"
TOKEN_BUDGET_PACKET = TMP / "token-budget-status.json"
TMP_ARTIFACT_SPIRE_PACKET = TMP / "tmp-artifact-spire.json"
SECURITY_WARNING_LEDGER_PACKET = TMP / "security-warning-ledger.json"
CRON_FRESHNESS_SPINE_PACKET = TMP / "cron-freshness-spine.json"
WF78_PROMOTION_VISIBILITY_PACKET = TMP / "wf78-promotion-visibility-top10.json"
WF78_LEGACY_LABEL_GUARD_PACKET = TMP / "wf78-legacy-label-retirement-guard.json"
WF67_MANAGER_PACKET = TMP / "alpaca-paper-readiness" / "wf67-autonomous-paper-manager-current.json"
WF67_PAPER_GUARD_PACKET = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
SHADOW_ELIGIBILITY_PACKET = TMP / "paper-autotrader" / "shadow-eligibility.json"
ARTIFACT_INDEX_DB = TMP / "veritas-artifact-index.sqlite"
OWNER_GATED_PACKET = TMP / "owner-gated-action-review-queue.json"
IMPROVEMENT_PACKET = TMP / "improvement-ledger-current.json"
WF74_OPPORTUNITY_PACKET = TMP / "wf74-improvement-opportunity-queue.json"
WF74_AUTO_PATCH_PACKET = TMP / "wf74-auto-patch-proposer.json"
WF74_DECISION_DOCKET_PACKET = TMP / "wf74-decision-docket.json"
OTEL_LEARNING_PACKET = TMP / "otel-learning-loop.json"
WF88_WIKI_SYNTHESIS_PACKET = TMP / "wf88-wiki-synthesis-packet.json"
WIKI_BOOTSTRAP_PROOF_PACKET = TMP / "wiki-bootstrap-proof.json"
WORKFLOW_ROUTING_INDEX_PACKET = TMP / "workflow-routing-index.json"
WORKFLOW_ROUTING_PARITY_PACKET = TMP / "workflow-routing-parity-validation.json"
LANE_REGISTER_PACKET = TMP / "concurrent-lane-register.json"
VECTOR_MEMORY_INDEX_PACKET = TMP / "vector-memory-index.json"
VECTOR_MEMORY_QUERY_PACKET = TMP / "vector-memory-query.json"
ACTIONABLE_QUEUE_PACKET = TMP / "actionable-improvement-queue.json"
NO_ORPHAN_VALIDATOR_PACKET = TMP / "no-orphan-validator.json"
WORKFLOW_BLOCKER_FOLLOWUPS_PACKET = TMP / "workflow-blocker-followups.json"
ACTION_EXECUTOR_PACKET = TMP / "main-session-action-executor.json"
ESCALATION_CONSUMER_PACKET = TMP / "main-session-escalation-consumer.json"
PM_AUTONOMY_DISPATCHER_PACKET = TMP / "pm-autonomy-dispatcher.json"
PM_JOB_WORKER_PACKET = TMP / "pm-job-worker-runner.json"
PM_AUTONOMY_VERIFIER_PACKET = TMP / "pm-autonomy-verifier.json"
PM_MAIN_ACTION_INBOX_PACKET = TMP / "pm-main-session-action-inbox.json"
IMPLEMENTATION_COMPLETION_LEDGER = STATE / "implementation-completion-ledger.jsonl"
CRON_MIGRATION_REPAIR_PLAN_PACKET = TMP / "cron-migration-repair-plan.json"
TTS_SMOKE_FILE = TMP / "tts-hello-from-veritas.mp3"

SCHEMA = "veritas.status_card_packet.v1"
FRONTDOOR_SCHEMA = "veritas.status_frontdoor.v1"
LOCAL_TZ = ZoneInfo("America/Phoenix")
CRON_MIGRATION_REPAIR_TITLE = "Route blocked cron signals into a migration-ready repair plan"
WORKFLOW_BLOCKER_FOLLOWUP_TITLE = "Convert workflow advancement blockers into implementation follow-ups"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cached_status_only": True,
    "status_question_runs_control_producers": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

STATUS_ROUTE_CONTRACT = {
    "route_name": "cached_status_card",
    "default_command": r"python scripts\status_card_packet.py --read-only --frontdoor --render --validate",
    "refresh_command": r"python scripts\status_card_packet.py --write --validate",
    "fallback_command": r"python scripts\startup_brief_packet.py --write --validate",
    "artifact": "tmp/veritas-status-card-frontdoor.json",
    "drilldown_artifact": "tmp/veritas-status-card.json",
    "max_tool_calls_for_status_question": 1,
    "read_only_default": True,
    "renderer_writes_files": False,
    "writer_reads_existing_packets_only": True,
    "regenerates_pm_or_cron_packets": False,
    "stale_inputs_are_summary_only": True,
    "implementation_closeout_refresh_required": True,
    "stale_when_completion_ledger_newer_than_card": True,
    "stale_when_pm_autonomy_artifacts_newer_than_card": True,
    "current_pm_action_wins_over_stale_lane_digest": True,
    "surfaces_nested_validation_warnings": True,
    "post_completion_refresh_commands": [
        r"python scripts\startup_brief_packet.py --write --validate",
        r"python scripts\status_card_packet.py --write --validate",
    ],
    "drilldown_allowed_only_when": [
        "user asks for material workflow detail",
        "user asks to act on the next queue item",
        "cached status validation is critical",
        "missing/stale input blocks a specific decision the user requested",
    ],
    "forbidden_for_status_question": [
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


def value_or_fallback(value: Any, fallback: Any) -> Any:
    return fallback if value is None else value


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def wf74_opportunity_packet() -> Path:
    return TMP / "wf74-improvement-opportunity-queue.json"


def wf74_auto_patch_packet() -> Path:
    return TMP / "wf74-auto-patch-proposer.json"


def wf74_decision_docket_packet() -> Path:
    return TMP / "wf74-decision-docket.json"


def workflow_blocker_followups_packet() -> Path:
    return TMP / "workflow-blocker-followups.json"


def cron_migration_repair_plan_packet() -> Path:
    return TMP / "cron-migration-repair-plan.json"


def workflow_routing_index_packet() -> Path:
    return TMP / "workflow-routing-index.json"


def workflow_routing_parity_packet() -> Path:
    return TMP / "workflow-routing-parity-validation.json"


def lane_register_packet() -> Path:
    return TMP / "concurrent-lane-register.json"


def vector_memory_index_packet() -> Path:
    return TMP / "vector-memory-index.json"


def vector_memory_query_packet() -> Path:
    return TMP / "vector-memory-query.json"


def otel_learning_packet() -> Path:
    return OTEL_LEARNING_PACKET


def artifact_age_seconds(path: Path, now: datetime) -> float | None:
    if not path.exists():
        return None
    return max(0.0, now.timestamp() - path.stat().st_mtime)


def path_state(path: Path, now: datetime) -> dict[str, Any]:
    generated_at = None
    payload = load(path) if path.exists() else {}
    if payload:
        generated_at = payload.get("generated_at_utc")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.exists(),
        "age_seconds": artifact_age_seconds(path, now),
        "generated_at_utc": generated_at,
        "status": payload.get("status") if payload else None,
    }


def file_state(path: Path, now: datetime) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "exists": path.exists(),
        "age_seconds": artifact_age_seconds(path, now),
        "generated_at_utc": None,
        "status": None,
    }


def parse_utc_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def mtime_utc(path: Path) -> datetime | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def loaded_card_stale_reasons(payload: dict[str, Any]) -> list[str]:
    card_generated = parse_utc_timestamp(payload.get("generated_at_utc"))
    if card_generated is None:
        return ["status_card.generated_at_utc_unreadable"]
    reasons: list[str] = []
    watched = {
        "pm_control_packet": PM_PACKET,
        "pm_implementation_job_queue": TMP / "pm-implementation-job-queue.json",
        "main_session_action_executor": ACTION_EXECUTOR_PACKET,
        "pm_autonomy_dispatcher": PM_AUTONOMY_DISPATCHER_PACKET,
        "pm_job_worker_runner": PM_JOB_WORKER_PACKET,
        "pm_main_session_action_inbox": PM_MAIN_ACTION_INBOX_PACKET,
        "otel_learning_loop": OTEL_LEARNING_PACKET,
        "wf88_wiki_synthesis": WF88_WIKI_SYNTHESIS_PACKET,
        "wiki_bootstrap_proof": WIKI_BOOTSTRAP_PROOF_PACKET,
        "actionable_improvement_queue": ACTIONABLE_QUEUE_PACKET,
        "no_orphan_validator": NO_ORPHAN_VALIDATOR_PACKET,
        "implementation_completion_ledger": IMPLEMENTATION_COMPLETION_LEDGER,
    }
    for name, path in watched.items():
        updated = mtime_utc(path)
        if updated and updated > card_generated + timedelta(seconds=1):
            reasons.append(f"status_card_older_than.{name}")
    return reasons


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


def packet_status_reasons(name: str, payload: dict[str, Any]) -> list[str]:
    status = str(payload.get("status") or "").strip()
    if status in {"warning", "critical", "blocked", "error", "stale_input_warning"}:
        return [f"{name}.status_{status}"]
    return []


def status_fleet_view(token_budget: dict[str, Any]) -> dict[str, Any]:
    fleet = as_dict(token_budget.get("fleet_usage"))
    summary = as_dict(fleet.get("summary"))
    windows = as_dict(fleet.get("usage_windows"))
    agents: list[dict[str, Any]] = []
    for row in as_list(fleet.get("agents")):
        if not isinstance(row, dict):
            continue
        utilization = as_dict(row.get("utilization"))
        outcomes = as_dict(row.get("outcomes"))
        agents.append({
            "agent_id": row.get("agent_id"),
            "agent_role": row.get("agent_role"),
            "utilization": {
                key: utilization.get(key)
                for key in (
                    "reporting_source", "reporting_total_tokens", "utilization_share_percent",
                    "utilized", "session_event_count", "session_attribution_grade_event_count",
                    "session_pricing_grade_event_count",
                )
            },
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
    return {
        "present": fleet.get("present") is True,
        "status": fleet.get("status") or "unavailable",
        "generated_at_utc": fleet.get("generated_at_utc"),
        "summary": {
            key: summary.get(key)
            for key in (
                "configured_agent_count", "observed_agent_count", "utilized_agent_count",
                "attribution_grade_coverage_percent", "pricing_grade_attribution_coverage_percent",
                "parent_job_count", "parent_job_completed_count", "parent_job_completion_percent",
                "completed_lane_count", "main_accepted_count", "main_acceptance_percent",
                "outcome_tracking_start_utc", "outcome_eligible_completed_lane_count",
                "historical_or_untracked_completed_lane_count", "main_acceptance_pending_count",
                "qa_review_completed_count", "qa_pass_count", "qa_yield_percent",
                "rework_count", "rework_percent", "attribution_gap_count",
            )
        },
        "usage_windows": {
            name: {
                key: as_dict(windows.get(name)).get(key)
                for key in (
                    "status", "coverage", "ready_agent_count", "configured_agent_count",
                    "event_count", "total_tokens", "api_equivalent_cost_usd",
                    "api_equivalent_is_not_invoice", "actual_billed_cost_usd", "date_labels",
                )
            }
            for name in ("rolling_5h_observed", "rolling_24h_gateway", "closed_7d_gateway")
        },
        "agents": agents,
        "billing_semantics": {
            "label": "API-equivalent benchmark",
            "api_equivalent_is_not_invoice": as_dict(fleet.get("billing_semantics")).get("api_equivalent_is_not_invoice") is True,
            "actual_billed_cost_usd": None,
        },
        "oauth_capacity_advisory": {
            key: as_dict(fleet.get("oauth_capacity_advisory")).get(key)
            for key in ("status", "tier", "remaining_percent", "reset_at_utc", "automatic_action_allowed")
        },
        "privacy_contract": {
            "metadata_only": True,
            "raw_prompt_stored": False,
            "raw_response_stored": False,
            "tool_payload_stored": False,
        },
    }


def fleet_posture(token_budget: dict[str, Any]) -> dict[str, Any]:
    """Return the compact, privacy-safe operating view of the seven-agent fleet.

    The source packet is metadata-only.  A missing or partial fleet feed is an
    observability limitation, not permission to invent utilization, billing,
    or sandbox state.
    """
    fleet = status_fleet_view(token_budget)
    raw_fleet = as_dict(token_budget.get("fleet_usage"))
    raw_sandbox = as_dict(raw_fleet.get("sandbox_posture"))
    sandbox_present = bool(raw_sandbox)
    return {
        "schema": FLEET_POSTURE_SCHEMA,
        "status": fleet.get("status") if fleet.get("present") else "unavailable",
        "generated_at_utc": fleet.get("generated_at_utc"),
        "operating_model": FLEET_OPERATING_MODEL,
        "reporting": {
            "source": "sanitized_metadata_only_fleet_usage",
            "configured_agent_count": as_dict(fleet.get("summary")).get("configured_agent_count"),
            "utilized_agent_count": as_dict(fleet.get("summary")).get("utilized_agent_count"),
            "pricing_grade_attribution_coverage_percent": as_dict(fleet.get("summary")).get("pricing_grade_attribution_coverage_percent"),
            "parent_job_completed_count": as_dict(fleet.get("summary")).get("parent_job_completed_count"),
            "main_accepted_count": as_dict(fleet.get("summary")).get("main_accepted_count"),
            "main_acceptance_pending_count": as_dict(fleet.get("summary")).get("main_acceptance_pending_count"),
            "qa_review_completed_count": as_dict(fleet.get("summary")).get("qa_review_completed_count"),
            "qa_pass_count": as_dict(fleet.get("summary")).get("qa_pass_count"),
            "qa_yield_percent": as_dict(fleet.get("summary")).get("qa_yield_percent"),
            "rework_count": as_dict(fleet.get("summary")).get("rework_count"),
            "attribution_gap_count": as_dict(fleet.get("summary")).get("attribution_gap_count"),
            "usage_windows": fleet.get("usage_windows"),
        },
        "oauth_capacity_advisory": fleet.get("oauth_capacity_advisory"),
        "containment": {
            "status": raw_sandbox.get("status") if sandbox_present else "not_reported",
            "source": "fleet_usage.sandbox_posture" if sandbox_present else "not_collected_by_cached_status",
            "workspace_isolation_is_not_hard_sandbox": True,
            "hard_sandbox_proven": raw_sandbox.get("hard_sandbox_proven") is True,
            "automatic_runtime_change_allowed": False,
        },
        "privacy_contract": fleet.get("privacy_contract"),
        "billing_semantics": fleet.get("billing_semantics"),
    }


def build_runtime_posture(token_summary: dict[str, Any], token_budget: dict[str, Any], *, fallback: bool = False) -> dict[str, Any]:
    budget_summary = as_dict(token_budget.get("summary"))
    envelope = as_dict(token_budget.get("tokens_envelope"))
    workspace_total = (
        envelope.get("workspace_total_tokens")
        if envelope
        else token_summary.get("total_tokens")
    )
    session_tokens = (
        envelope.get("session_tokens")
        or budget_summary.get("session_tokens")
        or "unavailable_to_workspace_script"
    )
    fleet = status_fleet_view(token_budget)
    return {
        "model": "openai/gpt-5.6-terra",
        "expected_route": {
            "execution_backend": "main",
            "model_path": "openai/gpt-5.6-terra",
            "thinking": None,
        },
        "actual_route": {
            "execution_backend": None,
            "model_path": None,
            "thinking": None,
            "status": "unavailable_to_workspace_script",
        },
        "route_conformance": "unavailable",
        "context": "workspace_cached_status_card_fallback" if fallback else "workspace_cached_status_card",
        "session": "webchat-main cached status fallback" if fallback else "webchat-main cached status",
        "voice": "TTS tagged mode proof present" if TTS_SMOKE_FILE.exists() else "not_cached_for_this_packet",
        "gateway": "openclaw-webchat-local",
        "model_route_match": None,
        "tokens": {
            "workspace_total_tokens": workspace_total,
            "session_tokens": session_tokens,
            "pricing_status": envelope.get("pricing_status") or token_summary.get("pricing_status"),
            "envelope": envelope or {
                "workspace_total_tokens": workspace_total,
                "pricing_status": token_summary.get("pricing_status"),
                "session_tokens_status": "unavailable_to_workspace_script",
            },
            "last_24h_burn_status": envelope.get("last_24h_burn_status") or budget_summary.get("last_24h_burn_status"),
            "isolated_agent_fleet": fleet,
        },
    }


def artifact_index_health(spire: dict[str, Any], now: datetime) -> dict[str, Any]:
    spire_summary = as_dict(spire.get("summary"))
    index_state = file_state(ARTIFACT_INDEX_DB, now)
    return {
        "status": spire.get("status") or ("ok" if ARTIFACT_INDEX_DB.exists() else "missing"),
        "artifact_index_exists": ARTIFACT_INDEX_DB.exists(),
        "artifact_index_size_mb": round(ARTIFACT_INDEX_DB.stat().st_size / (1024 * 1024), 2) if ARTIFACT_INDEX_DB.exists() else None,
        "artifact_index_age_seconds": index_state.get("age_seconds"),
        "tmp_json_count": spire_summary.get("tmp_json_count"),
        "tmp_total_mb": spire_summary.get("tmp_total_mb"),
        "stale_json_count": spire_summary.get("stale_json_count"),
        "wf78_json_count": spire_summary.get("wf78_json_count"),
        "cleanup_preview_eligible_count": spire_summary.get("cleanup_preview_eligible_count"),
        "truth_pointers": {
            "cron": "tmp/cron-control-packet.json",
            "pm": "tmp/pm-control-packet.json",
            "finance": "state/finance/finance-canon.sqlite plus tmp/trade-grade-os-freshness-cron-runner.json",
            "paper": "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json",
        },
        "next_safe_action": spire.get("next_safe_action"),
    }


def cron_fleet_health(cron: dict[str, Any], spine: dict[str, Any]) -> dict[str, Any]:
    cron_summary = as_dict(cron.get("summary"))
    spine_summary = as_dict(spine.get("summary"))
    jobs = [as_dict(row) for row in as_list(spine.get("jobs"))]
    attention_jobs = []
    for row in jobs:
        bucket = str(row.get("attention_bucket") or row.get("bucket") or "")
        klass = str(row.get("attention_class") or "")
        if "attention" in bucket or klass in {"urgent", "new_or_changed"}:
            name = row.get("name") or row.get("job_name") or row.get("id")
            if name:
                attention_jobs.append(str(name))
    return {
        "status": spine.get("status") or cron.get("status"),
        "job_count": spine_summary.get("job_count"),
        "fresh_count": spine_summary.get("fresh_count"),
        "stale_count": spine_summary.get("stale_count"),
        "requires_attention_count": spine_summary.get("requires_attention_count"),
        "urgent_attention_count": spine_summary.get("urgent_attention_count"),
        "monitor_only_or_stale_count": spine_summary.get("monitor_only_or_stale_count"),
        "quiet_success_count": spine_summary.get("quiet_success_count"),
        "blocked_count": value_or_fallback(spine_summary.get("blocked_count"), cron_summary.get("blocked_count")),
        "escalation_signal_count": cron_summary.get("escalation_signal_count"),
        "top_attention_jobs": attention_jobs[:3],
    }


def wf78_visibility_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    lanes = as_dict(packet.get("lanes"))
    return {
        "status": packet.get("status"),
        "candidate_count": summary.get("candidate_count"),
        "owner_review_ready_count": summary.get("owner_review_ready_count"),
        "market_refresh_pending_count": summary.get("market_refresh_pending_count"),
        "actionable_now_count": summary.get("actionable_now_count"),
        "actionable_top10_count": summary.get("actionable_top10_count"),
        "production_visible_count": summary.get("production_visible_count") or as_dict(lanes.get("production_visible")).get("count"),
        "tier_c_attention_count": summary.get("tier_c_attention_count"),
        "c_to_b_actionable_count": summary.get("c_to_b_actionable_count") or as_dict(lanes.get("c_to_b_actionable")).get("actionable_count"),
        "evidence_repair_count": summary.get("evidence_repair_count"),
        "canonical_top_of_funnel": "owner_review_ready_count",
        "next_safe_action": summary.get("next_safe_action"),
    }


def wf78_legacy_label_guard_summary(guard: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(guard.get("summary"))
    return {
        "status": guard.get("status"),
        "current_tier_authority": summary.get("current_tier_authority"),
        "active_legacy_label_refs": summary.get("active_legacy_label_refs"),
        "legacy_seeded_tier_count": summary.get("legacy_seeded_tier_count"),
        "legacy_seeded_tickers": summary.get("legacy_seeded_tickers"),
        "router_ahead_of_owner_approved_label_count": summary.get("router_ahead_of_owner_approved_label_count"),
        "router_ahead_of_owner_approved_label_tickers": summary.get("router_ahead_of_owner_approved_label_tickers"),
        "owner_review_only": True,
    }


def paper_top_blocker_summary(manager: dict[str, Any], guard: dict[str, Any], shadow: dict[str, Any]) -> dict[str, Any]:
    manager_summary = as_dict(manager.get("summary"))
    guard_findings = [as_dict(row) for row in as_list(guard.get("findings"))]
    critical_findings = [row for row in guard_findings if str(row.get("severity")).lower() in {"critical", "blocked", "error"}]
    guard_status = "blocked" if critical_findings or guard.get("ready_for_paper_submit_cancel") is False else guard.get("status")
    top_finding = critical_findings[0] if critical_findings else (guard_findings[0] if guard_findings else {})
    shadow_summary = as_dict(shadow.get("summary"))
    wf67_snapshot = as_dict(shadow.get("wf67_snapshot"))
    return {
        "status": "blocked" if guard_status == "blocked" else "ok",
        "manager_status": manager.get("status"),
        "consumer_posture": manager.get("consumer_posture"),
        "guard_status": guard_status or wf67_snapshot.get("guard_status"),
        "top_blocker_code": top_finding.get("code") or ("guard_not_clean" if guard_status == "blocked" else None),
        "top_blocker_severity": top_finding.get("severity"),
        "top_blocker_value": top_finding.get("value"),
        "position_count": manager_summary.get("position_count"),
        "ready_tickers": manager_summary.get("ready_tickers") or [],
        "blocked_tickers": manager_summary.get("blocked_tickers") or [],
        "would_buy_shadow_tickers": shadow_summary.get("would_buy_shadow_tickers") or [],
        "execution_ready_count": shadow_summary.get("execution_ready_count"),
        "next_safe_action": shadow_summary.get("next_safe_action") or "Keep paper execution blocked until WF67 guard and exact owner approval are clean.",
    }


def security_warning_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    return {
        "status": packet.get("status"),
        "warning_count": summary.get("warning_count"),
        "open_warning_count": summary.get("open_warning_count"),
        "owner_decision_required_count": summary.get("owner_decision_required_count"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def add_active_item(items: list[dict[str, Any]], item: Any, state: Any, next_action: Any, *, source: str) -> None:
    if not item:
        return
    text = str(item)
    if any(str(existing.get("item")) == text for existing in items):
        return
    items.append({
        "item": text,
        "state": state,
        "next": next_action,
        "source": source,
    })


def first_workflow(future_packet: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    for row in as_list(future_packet.get("workflow_capsules")):
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


def wf74_pickup_summary(
    cron_summary: dict[str, Any],
    queue: dict[str, Any],
    auto_patch: dict[str, Any],
    docket: dict[str, Any],
    followups: dict[str, Any],
    repair_plan: dict[str, Any],
) -> dict[str, Any]:
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
    workflow_opportunity = first_matching_opportunity(
        opportunities,
        title=WORKFLOW_BLOCKER_FOLLOWUP_TITLE,
    )
    followup_rows = [as_dict(row) for row in as_list(followups.get("followups"))]
    cron_followup_count = len([row for row in followup_rows if row.get("route") == "cron_migration"])
    cron_blocked_or_escalated_count = int(cron_summary.get("blocked_count") or 0) + int(cron_summary.get("escalation_signal_count") or 0)
    cron_repair_active_visible = bool(cron_opportunity) and cron_blocked_or_escalated_count > 0
    cron_repair_residue_visible = bool(cron_opportunity) and not cron_repair_active_visible
    repair_plan_visible = bool(repair_plan) and repair_plan.get("status") in {"ready_for_main_session", "warning"}
    high_priority_count = int(queue_summary.get("high_priority_count") or 0)
    workflow_followup_active_visible = bool(workflow_opportunity)
    docket_active_count = int(docket_summary.get("active_action_count") or 0)
    actionable = bool(high_priority_count or cron_repair_active_visible or workflow_followup_active_visible or docket_active_count)
    next_safe_action = (
        docket_summary.get("next_safe_action") or "Run main_session_greenkeeper_controller for WF74 pickup; inspect followups before scoped implementation."
        if actionable
        else docket_summary.get("next_safe_action") or "Monitor WF74 residual maturity/planning signals; no cron or workflow repair pickup is currently active."
    )
    top_title = queue_summary.get("top_opportunity_title")
    top_display_title = top_title
    if top_title == WORKFLOW_BLOCKER_FOLLOWUP_TITLE and int(followup_summary.get("followup_count") or 0):
        top_display_title = "Close remaining workflow-maturity follow-ups"
    return {
        "opportunity_count": queue_summary.get("opportunity_count"),
        "high_priority_count": high_priority_count,
        "top_opportunity_title": queue_summary.get("top_opportunity_title"),
        "top_opportunity_display_title": top_display_title,
        "cron_blocked_or_escalated_count": cron_blocked_or_escalated_count,
        "cron_migration_repair_visible": cron_repair_active_visible,
        "cron_migration_residue_visible": cron_repair_residue_visible,
        "cron_migration_repair_priority": cron_opportunity.get("priority"),
        "cron_migration_repair_followup_count": cron_followup_count,
        "cron_migration_repair_plan_visible": repair_plan_visible,
        "cron_migration_repair_plan_status": repair_plan.get("status"),
        "workflow_blocker_followup_visible": workflow_followup_active_visible,
        "workflow_blocker_followup_priority": workflow_opportunity.get("priority"),
        "workflow_blocker_followup_count": followup_summary.get("followup_count"),
        "workflow_blocker_followup_route_counts": followup_summary.get("route_counts"),
        "patch_plan_count": auto_patch_summary.get("patch_plan_count"),
        "skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
        "owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
        "auto_apply_count": auto_patch_summary.get("auto_apply_count"),
        "decision_docket_status": docket.get("status"),
        "decision_docket_validation": packet_validation_status(docket),
        "decision_docket_row_count": docket_summary.get("row_count"),
        "decision_docket_active_action_count": docket_active_count,
        "decision_docket_fix_now_count": docket_summary.get("fix_now_count"),
        "decision_docket_owner_decision_count": docket_summary.get("owner_decision_count"),
        "decision_docket_market_session_accrual_count": docket_summary.get("market_session_accrual_count"),
        "decision_docket_monitor_only_count": docket_summary.get("monitor_only_count"),
        "decision_docket_hard_stop_count": docket_summary.get("hard_stop_count"),
        "decision_docket_next_safe_action": docket_summary.get("next_safe_action"),
        "actionable": actionable,
        "next_safe_action": next_safe_action,
    }


def otel_learning_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summaries = as_dict(packet.get("learning_summaries"))
    health = as_dict(summaries.get("otel_health"))
    cost = as_dict(summaries.get("token_cost"))
    carry_forward = as_dict(packet.get("carry_forward_contract"))
    auto_router = as_dict(packet.get("auto_implementation_router"))
    recommendations = [row for row in as_list(packet.get("recommendations")) if isinstance(row, dict)]
    return {
        "present": bool(packet),
        "status": packet.get("status"),
        "validation": packet_validation_status(packet),
        "generated_at_utc": packet.get("generated_at_utc"),
        "collector_health": health.get("collector_health"),
        "drift_status": health.get("drift_status"),
        "daily_event_count": health.get("daily_event_count"),
        "daily_warning_or_error_count": health.get("daily_warning_or_error_count"),
        "token_coverage_ratio": cost.get("token_coverage_ratio"),
        "cost_coverage_ratio": cost.get("cost_coverage_ratio"),
        "recommendation_count": len(recommendations),
        "carry_forward_status": carry_forward.get("status"),
        "auto_implementation_status": auto_router.get("status"),
        "auto_apply_allowed": False,
        "next_safe_action": packet.get("next_safe_action") or carry_forward.get("next_safe_action"),
    }


def wf88_wiki_synthesis_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    leak = as_dict(packet.get("recommendation_leak_guard"))
    return {
        "present": bool(packet),
        "status": packet.get("status"),
        "validation": validation.get("status"),
        "page_count": summary.get("wiki_page_count"),
        "self_prompt_count": summary.get("self_prompt_count"),
        "action_item_count": len(as_list(packet.get("action_items"))),
        "recommendation_leak_guard_pass": leak.get("pass"),
        "open_unrouted_recommendation_count": leak.get("open_unrouted_recommendation_count"),
        "auto_apply_count": leak.get("auto_apply_count"),
        "rsi_status": summary.get("rsi_status"),
        "followup_required_open_count": summary.get("followup_required_open_count"),
        "recommendation_later_outcome_graded_rows": summary.get("recommendation_later_outcome_graded_rows"),
        "next_safe_action": "Refresh WF88 wiki synthesis after material learning-loop changes; keep action rows visible until routed or resolved.",
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


def actionable_queue_summary(packet: dict[str, Any], validator: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    validator_summary = as_dict(validator.get("summary"))
    validator_validation = as_dict(validator.get("validation"))
    return {
        "present": bool(packet),
        "status": packet.get("status"),
        "validation": validation.get("status"),
        "action_item_count": summary.get("action_item_count"),
        "orphan_count": summary.get("orphan_count"),
        "missing_contract_count": summary.get("missing_contract_count"),
        "owner_decision_count": summary.get("owner_decision_count"),
        "hard_stop_count": summary.get("hard_stop_count"),
        "monitor_only_count": summary.get("monitor_only_count"),
        "top_action_title": summary.get("top_action_title"),
        "top_action_class": summary.get("top_action_class"),
        "top_action_destination": summary.get("top_action_destination"),
        "top_next_action": summary.get("top_next_action"),
        "no_orphan_status": validator.get("status"),
        "no_orphan_validation": validator_validation.get("status"),
        "no_orphan_validation_passed": validator_summary.get("validation_passed"),
    }


def collect_recent_work(limit: int = 3) -> list[str]:
    today = datetime.now(LOCAL_TZ).date()
    candidates = [
        MEMORY / f"{(today - timedelta(days=1)).isoformat()}.md",
        MEMORY / f"{today.isoformat()}.md",
    ]
    headings: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            if not line.startswith("## "):
                continue
            text = line.strip("# ").strip()
            trailing_date = re.match(r"(.+?) - \d{4}-\d{2}-\d{2}(?:\s|$)", text)
            leading_date = re.search(r" - (.+)$", text)
            if trailing_date:
                title = trailing_date.group(1).strip()
            elif leading_date:
                title = leading_date.group(1).strip()
            else:
                title = text
            if title and title not in seen:
                headings.append(title)
                seen.add(title)
    return headings[-limit:]


def input_states(now: datetime) -> dict[str, dict[str, Any]]:
    return {
        "status_card": path_state(OUT, now),
        "startup_brief_packet": path_state(STARTUP_PACKET, now),
        "pm_control_packet": path_state(PM_PACKET, now),
        "pm_implementation_job_queue": path_state(TMP / "pm-implementation-job-queue.json", now),
        "cron_control_packet": path_state(CRON_PACKET, now),
        "future_session_packet": path_state(FUTURE_PACKET, now),
        "token_usage_packet": path_state(TOKEN_USAGE_PACKET, now),
        "token_budget_packet": path_state(TOKEN_BUDGET_PACKET, now),
        "tmp_artifact_spire_packet": path_state(TMP_ARTIFACT_SPIRE_PACKET, now),
        "security_warning_ledger_packet": path_state(SECURITY_WARNING_LEDGER_PACKET, now),
        "cron_freshness_spine_packet": path_state(CRON_FRESHNESS_SPINE_PACKET, now),
        "wf78_promotion_visibility_packet": path_state(WF78_PROMOTION_VISIBILITY_PACKET, now),
        "wf67_manager_packet": path_state(WF67_MANAGER_PACKET, now),
        "wf67_paper_guard_packet": path_state(WF67_PAPER_GUARD_PACKET, now),
        "shadow_eligibility_packet": path_state(SHADOW_ELIGIBILITY_PACKET, now),
        "owner_gated_packet": path_state(OWNER_GATED_PACKET, now),
        "improvement_packet": path_state(IMPROVEMENT_PACKET, now),
        "wf74_opportunity_packet": path_state(wf74_opportunity_packet(), now),
        "wf74_auto_patch_packet": path_state(wf74_auto_patch_packet(), now),
        "wf74_decision_docket_packet": path_state(wf74_decision_docket_packet(), now),
        "otel_learning_loop_packet": path_state(otel_learning_packet(), now),
        "wf88_wiki_synthesis_packet": path_state(WF88_WIKI_SYNTHESIS_PACKET, now),
        "wiki_bootstrap_proof_packet": path_state(WIKI_BOOTSTRAP_PROOF_PACKET, now),
        "workflow_routing_index_packet": path_state(workflow_routing_index_packet(), now),
        "workflow_routing_parity_packet": path_state(workflow_routing_parity_packet(), now),
        "lane_register_packet": path_state(lane_register_packet(), now),
        "vector_memory_index_packet": path_state(vector_memory_index_packet(), now),
        "vector_memory_query_packet": path_state(vector_memory_query_packet(), now),
        "actionable_queue_packet": path_state(ACTIONABLE_QUEUE_PACKET, now),
        "no_orphan_validator_packet": path_state(NO_ORPHAN_VALIDATOR_PACKET, now),
        "workflow_blocker_followups_packet": path_state(workflow_blocker_followups_packet(), now),
        "cron_migration_repair_plan_packet": path_state(cron_migration_repair_plan_packet(), now),
        "action_executor_packet": path_state(ACTION_EXECUTOR_PACKET, now),
        "escalation_consumer_packet": path_state(ESCALATION_CONSUMER_PACKET, now),
        "pm_autonomy_dispatcher_packet": path_state(PM_AUTONOMY_DISPATCHER_PACKET, now),
        "pm_job_worker_packet": path_state(PM_JOB_WORKER_PACKET, now),
        "pm_autonomy_verifier_packet": path_state(PM_AUTONOMY_VERIFIER_PACKET, now),
        "pm_main_action_inbox_packet": path_state(PM_MAIN_ACTION_INBOX_PACKET, now),
        "implementation_completion_ledger": file_state(IMPLEMENTATION_COMPLETION_LEDGER, now),
    }


ROUTE_CONTRACT_FIELDS = (
    "workflow_id", "tier", "priority", "lifecycle", "readiness",
    "current_state", "next_action", "authoritative_next_action",
    "authority_class", "primary_owner_lane", "human_approval_owner",
    "proof_artifact",
)


def workflow_routing_summary(index: dict[str, Any], parity: dict[str, Any]) -> dict[str, Any]:
    routes = [as_dict(row) for row in as_list(index.get("routes"))]
    projections = [
        {key: route.get(key) for key in ROUTE_CONTRACT_FIELDS}
        | {"freshness": as_dict(route.get("freshness"))}
        for route in routes
    ]
    summary = as_dict(index.get("summary"))
    parity_summary = as_dict(parity.get("summary"))
    readiness_counts = as_dict(summary.get("readiness_counts"))
    lifecycle_counts = as_dict(summary.get("lifecycle_counts"))
    index_status = index.get("status") or as_dict(index.get("validation")).get("status")
    parity_status = parity.get("status")
    status = "ok" if index_status not in {"blocked", "error", "critical"} and parity_status in {"ok", None} else "attention"
    return {
        "status": status,
        "route_count": len(routes),
        "active_build_queue_count": summary.get("active_build_queue_count"),
        "paused_count": lifecycle_counts.get("paused", 0),
        "refresh_required_count": readiness_counts.get("refresh_required", 0),
        "paper_fail_closed_count": sum(
            1 for route in routes if route.get("authority_class") == "paper_guard_fail_closed"
        ),
        "parity": {
            "status": parity_status,
            "routes_checked": parity_summary.get("routes_checked"),
            "critical": parity_summary.get("critical"),
        },
        "authority_note": "Route rows are derived mirrors. Active Workflows plus workflow-control-overrides own control state.",
        "routes": projections,
    }


def lane_register_summary(register: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(register.get("summary"))
    open_lanes = [as_dict(row) for row in as_list(summary.get("open_lanes"))]
    return {
        "status": register.get("status") or as_dict(register.get("validation")).get("status"),
        "historical_lane_count": summary.get("lane_count"),
        "historical_terminal_lane_count": summary.get("historical_terminal_lane_count"),
        "open_lane_count": summary.get("open_lane_count", summary.get("active_lane_count", 0)),
        "open_blocked_lane_count": summary.get("open_blocked_lane_count", 0),
        "attention_open_lane_count": summary.get("attention_open_lane_count", 0),
        "open_lanes": open_lanes,
        "next_safe_action": summary.get("next_safe_action"),
    }


def continuity_retrieval_summary(vector_index: dict[str, Any], vector_query: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(vector_index.get("validation"))
    index_status = vector_index.get("status") or validation.get("status")
    fallback_available = index_status in {"ok", "warning"} and bool(vector_index)
    query_status = vector_query.get("status") or as_dict(vector_query.get("validation")).get("status")
    return {
        "status": "ok" if fallback_available else "attention",
        "semantic_provider_status": "not_probed_by_cached_status_card",
        "last_local_query_status": query_status,
        "local_fallback_available": fallback_available,
        "local_fallback_command": r"python scripts\vector_memory_index.py --query \"<query>\" --allow-stale",
        "primary_artifact_rule": "A fresh proof packet does not make stale continuity/owner context fresh; material active routes expose refresh_required separately.",
        "index_generated_at_utc": vector_index.get("generated_at_utc"),
        "query_generated_at_utc": vector_query.get("generated_at_utc"),
    }


def build_payload(max_age_minutes: int = 90) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    startup = load(STARTUP_PACKET)
    startup_summary = as_dict(startup.get("summary"))
    pm = load(PM_PACKET)
    pm_summary = as_dict(pm.get("summary"))
    cron = load(CRON_PACKET)
    cron_summary = as_dict(cron.get("summary"))
    future = load(FUTURE_PACKET)
    future_efficiency_policy = as_dict(future.get("execution_efficiency_policy"))
    startup_efficiency_policy = as_dict(startup.get("execution_efficiency_policy"))
    execution_efficiency_policy = implementation_router.execution_efficiency_policy()
    future_efficiency_policy_matches_owner = future_efficiency_policy == execution_efficiency_policy
    startup_efficiency_policy_matches_owner = startup_efficiency_policy == execution_efficiency_policy
    token = load(TOKEN_USAGE_PACKET)
    token_summary = as_dict(token.get("summary"))
    token_budget = load(TOKEN_BUDGET_PACKET)
    tmp_spire = load(TMP_ARTIFACT_SPIRE_PACKET)
    security_ledger = load(SECURITY_WARNING_LEDGER_PACKET)
    cron_freshness = load(CRON_FRESHNESS_SPINE_PACKET)
    wf78_visibility = load(WF78_PROMOTION_VISIBILITY_PACKET)
    wf78_legacy_label_guard = load(WF78_LEGACY_LABEL_GUARD_PACKET)
    wf67_manager = load(WF67_MANAGER_PACKET)
    wf67_guard = load(WF67_PAPER_GUARD_PACKET)
    shadow_eligibility = load(SHADOW_ELIGIBILITY_PACKET)
    owner = load(OWNER_GATED_PACKET)
    owner_summary = as_dict(owner.get("summary"))
    improvement = load(IMPROVEMENT_PACKET)
    improvement_summary = as_dict(improvement.get("summary"))
    wf74_queue = load(wf74_opportunity_packet())
    wf74_auto_patch = load(wf74_auto_patch_packet())
    wf74_docket = load(wf74_decision_docket_packet())
    otel_learning = load(otel_learning_packet())
    wf88_wiki_synthesis = load(WF88_WIKI_SYNTHESIS_PACKET)
    wiki_bootstrap_proof = load(WIKI_BOOTSTRAP_PROOF_PACKET)
    workflow_routing_index = load(workflow_routing_index_packet())
    workflow_routing_parity = load(workflow_routing_parity_packet())
    lane_register = load(lane_register_packet())
    vector_memory_index = load(vector_memory_index_packet())
    vector_memory_query = load(vector_memory_query_packet())
    actionable_queue_packet = load(ACTIONABLE_QUEUE_PACKET)
    no_orphan_validator_packet = load(NO_ORPHAN_VALIDATOR_PACKET)
    workflow_followups = load(workflow_blocker_followups_packet())
    cron_migration_repair_plan = load(cron_migration_repair_plan_packet())
    wf74_pickup = wf74_pickup_summary(cron_summary, wf74_queue, wf74_auto_patch, wf74_docket, workflow_followups, cron_migration_repair_plan)
    action_executor = load(ACTION_EXECUTOR_PACKET)
    action_summary = as_dict(action_executor.get("summary"))
    escalation_consumer = load(ESCALATION_CONSUMER_PACKET)
    escalation_summary = as_dict(escalation_consumer.get("summary"))
    autonomy_dispatcher = load(PM_AUTONOMY_DISPATCHER_PACKET)
    autonomy_dispatcher_summary = as_dict(autonomy_dispatcher.get("summary"))
    pm_worker = load(PM_JOB_WORKER_PACKET)
    pm_worker_summary = as_dict(pm_worker.get("summary"))
    autonomy_verifier = load(PM_AUTONOMY_VERIFIER_PACKET)
    autonomy_verifier_summary = as_dict(autonomy_verifier.get("summary"))
    action_inbox = load(PM_MAIN_ACTION_INBOX_PACKET)

    pm_readiness = as_dict(pm_summary.get("pm_readiness"))
    implementation_queue = as_dict(pm_summary.get("implementation_queue"))
    cockpit_health = as_dict(pm_summary.get("pm_cockpit_source_health"))
    finance_digest = as_dict(pm_summary.get("finance_domain_repair_digest"))
    sql_health = as_dict(pm_summary.get("sql_canon_health")) or as_dict(cron.get("sql_canon_health"))
    sql_counts = as_dict(sql_health.get("counts"))
    stale_lane_digest = as_dict(pm_summary.get("stale_lane_digest"))
    stale_lanes = as_list(stale_lane_digest.get("lanes"))
    top_stale_lane = as_dict(stale_lanes[0]) if stale_lanes else {}
    top_next_action = as_dict(pm_summary.get("top_next_action"))
    wf85 = first_workflow(future, "WF85")
    wf84 = first_workflow(future, "WF84")
    workflow_routing = workflow_routing_summary(workflow_routing_index, workflow_routing_parity)
    lane_register_view = lane_register_summary(lane_register)
    continuity_retrieval = continuity_retrieval_summary(vector_memory_index, vector_memory_query)

    inputs = input_states(now)
    stale_inputs = [
        key
        for key, state in inputs.items()
        if key != "status_card"
        and key != "implementation_completion_ledger"
        # These diagnostic mirrors are intentionally allowed to be absent in
        # lightweight/bootstrap fixtures. Their own status fields surface the
        # degradation without making every cached-card caller look stale.
        and key not in {
            "workflow_routing_index_packet", "workflow_routing_parity_packet",
            "lane_register_packet", "vector_memory_index_packet", "vector_memory_query_packet",
        }
        and (state.get("age_seconds") is None or state.get("age_seconds", 0) > max_age_minutes * 60)
    ]
    validation_warnings = []
    for name, packet in [
        ("startup_brief_packet", startup),
        ("future_session_packet", future),
        ("pm_control_packet", pm),
        ("cron_control_packet", cron),
        ("cron_freshness_spine_packet", cron_freshness),
        ("improvement_packet", improvement),
        ("wf74_decision_docket_packet", wf74_docket),
        ("otel_learning_loop_packet", otel_learning),
        ("wf88_wiki_synthesis_packet", wf88_wiki_synthesis),
        ("wiki_bootstrap_proof_packet", wiki_bootstrap_proof),
        ("actionable_queue_packet", actionable_queue_packet),
        ("no_orphan_validator_packet", no_orphan_validator_packet),
        ("action_executor_packet", action_executor),
        ("pm_autonomy_dispatcher_packet", autonomy_dispatcher),
        ("pm_job_worker_packet", pm_worker),
        ("pm_autonomy_verifier_packet", autonomy_verifier),
        ("token_budget_packet", token_budget),
        ("tmp_artifact_spire_packet", tmp_spire),
        ("security_warning_ledger_packet", security_ledger),
        ("wf78_promotion_visibility_packet", wf78_visibility),
        ("wf67_paper_guard_packet", wf67_guard),
        ("shadow_eligibility_packet", shadow_eligibility),
    ]:
        validation_warnings.extend(packet_warning_reasons(name, packet))
        validation_warnings.extend(packet_status_reasons(name, packet))
    if not future_efficiency_policy_matches_owner:
        validation_warnings.append("future_session_packet.execution_efficiency_policy_owner_mismatch")
    if not startup_efficiency_policy_matches_owner:
        validation_warnings.append("startup_brief_packet.execution_efficiency_policy_owner_mismatch")
    if workflow_routing.get("status") != "ok":
        validation_warnings.append("workflow_routing.contract_or_parity_attention")
    if lane_register_view.get("attention_open_lane_count"):
        validation_warnings.append("lane_register.open_lane_attention")
    if continuity_retrieval.get("local_fallback_available") is not True:
        validation_warnings.append("continuity_retrieval.local_fallback_unavailable")

    selected_job = as_dict(action_summary.get("selected_pm_job")).get("job_id")
    selected_item = selected_job or action_summary.get("parallel_helper_workstream")
    recent_work = collect_recent_work()
    inbox_job = action_inbox.get("top_pending_job_id")
    inbox_action = action_inbox.get("action_type")
    queue_top_job = implementation_queue.get("top_ready_job_id") or implementation_queue.get("top_job_id")
    queue_top_title = implementation_queue.get("top_ready_job_title") or implementation_queue.get("top_job_title")
    dispatcher_job = autonomy_dispatcher_summary.get("selected_job_id")
    dispatcher_action = autonomy_dispatcher_summary.get("selected_action_type")
    ready_job_count = int(implementation_queue.get("ready_job_count") or 0)
    active_job_count = int(implementation_queue.get("active_job_count") or 0)
    current_handoff_job = inbox_job or dispatcher_job
    current_handoff_valid = bool(
        current_handoff_job
        and ready_job_count
        and current_handoff_job in {
            implementation_queue.get("top_ready_job_id"),
            implementation_queue.get("top_job_id"),
        }
    )
    if current_handoff_job and not current_handoff_valid:
        validation_warnings.append("pm_autonomy_handoff.stale_or_not_ready")
    wf88_wiki = wf88_wiki_synthesis_summary(wf88_wiki_synthesis)
    wiki_bootstrap = wiki_bootstrap_proof_summary(wiki_bootstrap_proof)
    actionable_queue = actionable_queue_summary(actionable_queue_packet, no_orphan_validator_packet)
    top_stale_job = top_stale_lane.get("top_job_id")
    top_stale_title = top_stale_lane.get("top_job_title")
    stale_lane_conflicts_with_current_job = bool(
        top_stale_title
        and (queue_top_job or dispatcher_job or inbox_job)
        and top_stale_job not in {queue_top_job, dispatcher_job, inbox_job}
    )

    active_items: list[dict[str, Any]] = []
    if current_handoff_valid:
        add_active_item(
            active_items,
            queue_top_title if current_handoff_job == queue_top_job and queue_top_title else current_handoff_job,
            inbox_action or dispatcher_action,
            action_inbox.get("main_next_action") or autonomy_dispatcher_summary.get("next_action"),
            source="pm_current_action",
        )
    if workflow_routing.get("refresh_required_count") or workflow_routing.get("parity", {}).get("status") not in {"ok", None}:
        add_active_item(
            active_items,
            "Workflow routing truth contract",
            workflow_routing.get("status"),
            "Refresh the derived route index/capsules/status card and resolve any parity finding before advancing a route.",
            source="workflow_routing",
        )
    for open_lane in as_list(lane_register_view.get("open_lanes"))[:2]:
        lane = as_dict(open_lane)
        add_active_item(
            active_items,
            lane.get("lane_id"),
            lane.get("status"),
            lane.get("next_action"),
            source="open_lane_register",
        )
    if not current_handoff_valid or current_handoff_job != queue_top_job:
        add_active_item(
            active_items,
            queue_top_title or queue_top_job,
            "ready" if ready_job_count else "not_ready",
            implementation_queue.get("top_ready_next_action") or implementation_queue.get("top_next_action"),
            source="pm_queue",
        )
    if top_stale_title and not stale_lane_conflicts_with_current_job:
        add_active_item(
            active_items,
            top_stale_title,
            "ready" if implementation_queue.get("ready_job_count") else "not_ready",
            top_stale_lane.get("next_action"),
            source="pm_stale_lane_digest",
        )
    if ready_job_count or active_job_count or current_handoff_valid:
        add_active_item(
            active_items,
            top_next_action.get("lane_id"),
            top_next_action.get("lane_status"),
            top_next_action.get("description"),
            source="pm_lane",
        )
    add_active_item(
        active_items,
        owner_summary.get("top_title"),
        owner_summary.get("top_plain_status") or owner_summary.get("top_gate"),
        owner_summary.get("next_safe_action"),
        source="owner_gated",
    )
    add_active_item(
        active_items,
        (
            wf74_pickup.get("top_opportunity_display_title")
            if improvement_summary.get("top_improvement_title") == WORKFLOW_BLOCKER_FOLLOWUP_TITLE
            and wf74_pickup.get("workflow_blocker_followup_count")
            else improvement_summary.get("top_improvement_title")
        ),
        improvement_summary.get("top_improvement_sla_status"),
        improvement_summary.get("top_improvement_next_action"),
        source="improvement_ledger",
    )
    if wf74_pickup.get("actionable"):
        add_active_item(
            active_items,
            wf74_pickup.get("top_opportunity_display_title") or wf74_pickup.get("top_opportunity_title"),
            f"high={wf74_pickup.get('high_priority_count')} cron_visible={wf74_pickup.get('cron_migration_repair_visible')} workflow_visible={wf74_pickup.get('workflow_blocker_followup_visible')}",
            wf74_pickup.get("next_safe_action"),
            source="wf74_pickup",
        )
    if wf88_wiki.get("present") and (
        wf88_wiki.get("validation") in {"warning", "blocked", "critical"}
        or int(wf88_wiki.get("action_item_count") or 0)
        or int(wf88_wiki.get("followup_required_open_count") or 0)
    ):
        add_active_item(
            active_items,
            "WF88 wiki synthesis",
            f"validation={wf88_wiki.get('validation')} leak_guard={wf88_wiki.get('recommendation_leak_guard_pass')} rsi={wf88_wiki.get('rsi_status')}",
            wf88_wiki.get("next_safe_action"),
            source="wf88_wiki_synthesis",
        )
    if wiki_bootstrap.get("present") and wiki_bootstrap.get("validation") in {"warning", "blocked", "critical"}:
        add_active_item(
            active_items,
            "WF88 wiki bootstrap proof",
            f"validation={wiki_bootstrap.get('validation')} gate={wiki_bootstrap.get('bootstrap_gate')} files={wiki_bootstrap.get('validated_file_count')}/{wiki_bootstrap.get('required_file_count')}",
            wiki_bootstrap.get("next_safe_action"),
            source="wiki_bootstrap_proof",
        )
    if actionable_queue.get("present") and (
        int(actionable_queue.get("action_item_count") or 0)
        or int(actionable_queue.get("orphan_count") or 0)
        or actionable_queue.get("no_orphan_validation") in {"warning", "blocked", "critical"}
    ):
        add_active_item(
            active_items,
            actionable_queue.get("top_action_title") or "Actionable improvement queue",
            f"destination={actionable_queue.get('top_action_destination')} orphans={actionable_queue.get('orphan_count')} no_orphan={actionable_queue.get('no_orphan_validation')}",
            actionable_queue.get("top_next_action"),
            source="actionable_improvement_queue",
        )
    add_active_item(
        active_items,
        selected_item,
        action_summary.get("classification"),
        action_summary.get("next_safe_action"),
        source="main_action_executor",
    )

    validation_warnings = list(dict.fromkeys(validation_warnings))
    runtime_posture = build_runtime_posture(token_summary, token_budget)
    artifact_health = artifact_index_health(tmp_spire, now)
    cron_fleet = cron_fleet_health(cron, cron_freshness)
    wf78_summary = wf78_visibility_summary(wf78_visibility)
    wf78_legacy_label_guard_view = wf78_legacy_label_guard_summary(wf78_legacy_label_guard)
    paper_blocker = paper_top_blocker_summary(wf67_manager, wf67_guard, shadow_eligibility)
    security_summary = security_warning_summary(security_ledger)
    otel_summary = otel_learning_summary(otel_learning)

    payload_status = "stale_input_warning" if stale_inputs else "warning" if validation_warnings else "ok"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": payload_status,
        "purpose": "Cached, thin status card for shallow Status? replies.",
        "max_age_minutes": max_age_minutes,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "status_route_contract": STATUS_ROUTE_CONTRACT.copy(),
        "input_artifacts": inputs,
        "operating_posture": runtime_posture,
        "execution_efficiency_policy": execution_efficiency_policy,
        "execution_efficiency_projection_source": "scripts/project_implementation_router.py",
        "future_efficiency_policy_matches_owner": future_efficiency_policy_matches_owner,
        "startup_efficiency_policy_matches_owner": startup_efficiency_policy_matches_owner,
        "artifact_index_health": artifact_health,
        "token_budget": {
            "status": token_budget.get("status"),
            "summary": as_dict(token_budget.get("summary")),
            "top_token_heavy_cron_jobs": as_list(token_budget.get("top_token_heavy_cron_jobs"))[:5],
            "fleet_usage": status_fleet_view(token_budget),
        },
        "isolated_agent_fleet": status_fleet_view(token_budget),
        "fleet_posture": fleet_posture(token_budget),
        "cron_fleet_health": cron_fleet,
        "workflow_routing": workflow_routing,
        "lane_register": lane_register_view,
        "continuity_retrieval": continuity_retrieval,
        "wf78_visibility": wf78_summary,
        "wf78_legacy_label_guard": wf78_legacy_label_guard_view,
        "paper_top_blocker_summary": paper_blocker,
        "security_warnings": security_summary,
        "finance_os": {
            "wf84_data_plane": startup_summary.get("wf84_status") or wf84.get("effective_status"),
            "wf85_decision_os": startup_summary.get("wf85_status") or wf85.get("effective_status"),
            "sql_canon": {
                "status": sql_health.get("status"),
                "securities": sql_counts.get("securities"),
                "production_answers": sql_health.get("production_answer_count") or cron_summary.get("sql_canon_production_answer_count"),
                "authority_false_flags": as_dict(next((row for row in as_list(sql_health.get("checks")) if isinstance(row, dict) and row.get("name") == "authority_false_flags_clean"), {})).get("detail"),
            },
            "tier_a_b_bands": {
                "complete_current": finance_digest.get("tier_a_b_complete_and_current_band_count"),
                "missing_decision_grade": finance_digest.get("tier_a_b_missing_decision_grade_band_count"),
                "missing_tickers": finance_digest.get("tier_a_b_missing_decision_grade_band_tickers") or [],
            },
            "trade_grade_repair": {
                "rows": finance_digest.get("total_repair_conveyor_row_count") or finance_digest.get("finance_domain_repair_item_count"),
                "implementation_blockers": finance_digest.get("implementation_blocker_count"),
                "scope": finance_digest.get("pm_blocker_scope"),
            },
        },
        "pm_queue": {
            "pm_readiness_band": pm_readiness.get("readiness_band") or startup_summary.get("pm_readiness_band"),
            "pm_readiness_score": pm_readiness.get("average_score"),
            "ready_jobs": value_or_fallback(implementation_queue.get("ready_job_count"), startup_summary.get("pm_ready_job_count")),
            "blocked_jobs": value_or_fallback(implementation_queue.get("blocked_job_count"), startup_summary.get("pm_blocked_job_count")),
            "stale_cockpit_sources": cockpit_health.get("stale_required_count"),
            "cron_escalation_signals": value_or_fallback(cron_summary.get("escalation_signal_count"), startup_summary.get("cron_escalation_signal_count")),
            "cron_blocked": value_or_fallback(cron_summary.get("blocked_count"), startup_summary.get("cron_blocked_count")),
            "action_executor": {
                "status": action_executor.get("status"),
                "selected": selected_item,
                "executed": action_summary.get("executed"),
            },
            "autonomy": {
                "dispatcher_status": autonomy_dispatcher.get("status"),
                "dispatcher_action": autonomy_dispatcher_summary.get("selected_action_type"),
                "dispatcher_selected_job": autonomy_dispatcher_summary.get("selected_job_id"),
                "dispatcher_selected_priority_score": autonomy_dispatcher_summary.get("selected_priority_score"),
                "worker_status": pm_worker.get("status"),
                "worker_action": pm_worker_summary.get("action_type"),
                "worker_selected_job": pm_worker_summary.get("selected_job_id"),
                "worker_executed": pm_worker_summary.get("executed"),
                "verifier_status": autonomy_verifier.get("status"),
                "verifier_action": autonomy_verifier_summary.get("action_type"),
                "inbox_action": action_inbox.get("action_type"),
                "inbox_top_job": action_inbox.get("top_pending_job_id"),
                "inbox_next_action": action_inbox.get("main_next_action"),
                "current_handoff_valid": current_handoff_valid,
            },
        },
        "wf74_pickup": wf74_pickup,
        "otel_learning_loop": otel_summary,
        "wf88_wiki_synthesis": wf88_wiki,
        "wiki_bootstrap_proof": wiki_bootstrap,
        "actionable_improvement_queue": actionable_queue,
        "recent_work": recent_work,
        "active_items": active_items,
        "next_actions": [
            action_inbox.get("main_next_action") if current_handoff_valid else None,
            wf74_pickup.get("next_safe_action") if wf74_pickup.get("actionable") else None,
            top_stale_lane.get("next_action") if not stale_lane_conflicts_with_current_job else None,
            owner_summary.get("next_safe_action"),
            improvement_summary.get("top_improvement_next_action"),
            "For shallow Status?, render this cached card and stop; refresh only when explicitly requested or critical.",
        ],
        "stale_inputs": stale_inputs,
        "input_validation_warnings": validation_warnings,
        "read_only_status_question_rule": "Read tmp/veritas-status-card-frontdoor.json or run the compact read-only renderer. Use hashed drilldown only for material or critical detail.",
        "validation": {"status": "pending", "errors": []},
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "critical"
    return payload


def validate_contract(boundary: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary.{key}")
    required_false = [
        "renderer_writes_files",
        "regenerates_pm_or_cron_packets",
    ]
    for key in required_false:
        if route.get(key) is not False:
            errors.append(f"status_route_contract.{key}")
    if route.get("read_only_default") is not True:
        errors.append("status_route_contract.read_only_default")
    if route.get("implementation_closeout_refresh_required") is not True:
        errors.append("status_route_contract.implementation_closeout_refresh_required")
    if route.get("stale_when_completion_ledger_newer_than_card") is not True:
        errors.append("status_route_contract.stale_when_completion_ledger_newer_than_card")
    if route.get("stale_when_pm_autonomy_artifacts_newer_than_card") is not True:
        errors.append("status_route_contract.stale_when_pm_autonomy_artifacts_newer_than_card")
    if route.get("current_pm_action_wins_over_stale_lane_digest") is not True:
        errors.append("status_route_contract.current_pm_action_wins_over_stale_lane_digest")
    if route.get("surfaces_nested_validation_warnings") is not True:
        errors.append("status_route_contract.surfaces_nested_validation_warnings")
    refresh_commands = as_list(route.get("post_completion_refresh_commands"))
    for command in [
        r"python scripts\startup_brief_packet.py --write --validate",
        r"python scripts\status_card_packet.py --write --validate",
    ]:
        if command not in refresh_commands:
            errors.append(f"status_route_contract.missing_post_completion_refresh_command.{command}")
    if route.get("max_tool_calls_for_status_question") != 1:
        errors.append("status_route_contract.max_tool_calls_for_status_question")
    forbidden = set(as_list(route.get("forbidden_for_status_question")))
    for phrase in ["pm_control_packet regeneration", "cron_control_packet regeneration", "lane-register inspection"]:
        if phrase not in forbidden:
            errors.append(f"status_route_contract.missing_forbidden.{phrase}")
    return {"status": "critical" if errors else "ok", "errors": errors}


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors = list(validate_contract(
        as_dict(payload.get("authority_boundary")),
        as_dict(payload.get("status_route_contract")),
    )["errors"])
    pm = as_dict(payload.get("pm_queue"))
    wf74 = as_dict(payload.get("wf74_pickup"))
    otel = as_dict(payload.get("otel_learning_loop"))
    wf88_wiki = as_dict(payload.get("wf88_wiki_synthesis"))
    wiki_bootstrap = as_dict(payload.get("wiki_bootstrap_proof"))
    actionable_queue = as_dict(payload.get("actionable_improvement_queue"))
    workflow_routing = as_dict(payload.get("workflow_routing"))
    lane_register = as_dict(payload.get("lane_register"))
    continuity_retrieval = as_dict(payload.get("continuity_retrieval"))
    operating = as_dict(payload.get("operating_posture"))
    tokens = as_dict(operating.get("tokens"))
    fleet = as_dict(payload.get("isolated_agent_fleet"))
    posture = as_dict(payload.get("fleet_posture"))
    if "not cached by this card" in json.dumps(operating, sort_keys=True):
        errors.append("operating_posture.contains_not_cached_placeholder")
    if not operating.get("gateway"):
        errors.append("operating_posture.gateway_missing")
    expected_route = as_dict(operating.get("expected_route"))
    actual_route = as_dict(operating.get("actual_route"))
    if expected_route.get("execution_backend") != "main" or expected_route.get("model_path") != "openai/gpt-5.6-terra":
        errors.append("operating_posture.expected_route_invalid")
    if actual_route.get("status") == "unavailable_to_workspace_script":
        if operating.get("model_route_match") is not None or operating.get("route_conformance") != "unavailable":
            errors.append("operating_posture.fabricated_route_match")
    elif operating.get("model_route_match") is not True:
        errors.append("operating_posture.actual_route_mismatch")
    efficiency_policy = as_dict(payload.get("execution_efficiency_policy"))
    if efficiency_policy != implementation_router.execution_efficiency_policy():
        errors.append("execution_efficiency_policy.owner_mismatch")
    if as_dict(efficiency_policy.get("quality_weighted_efficiency")).get("automatic_route_promotion_allowed") is not False:
        errors.append("execution_efficiency_policy.auto_promotion_not_disabled")
    if not tokens.get("session_tokens"):
        errors.append("operating_posture.session_tokens_missing")
    if not as_dict(tokens.get("envelope")):
        errors.append("operating_posture.token_envelope_missing")
    if fleet.get("present") is True:
        fleet_billing = as_dict(fleet.get("billing_semantics"))
        fleet_capacity = as_dict(fleet.get("oauth_capacity_advisory"))
        privacy = as_dict(fleet.get("privacy_contract"))
        if fleet_billing.get("api_equivalent_is_not_invoice") is not True:
            errors.append("isolated_agent_fleet.api_equivalent_invoice_guard")
        if fleet_billing.get("actual_billed_cost_usd") is not None:
            errors.append("isolated_agent_fleet.actual_billed_cost_must_be_null")
        if fleet_capacity.get("automatic_action_allowed") is not False:
            errors.append("isolated_agent_fleet.capacity_action_must_be_advisory")
        if privacy.get("metadata_only") is not True:
            errors.append("isolated_agent_fleet.metadata_only_not_true")
        for key in ("raw_prompt_stored", "raw_response_stored", "tool_payload_stored"):
            if privacy.get(key) is not False:
                errors.append(f"isolated_agent_fleet.{key}_not_false")
    if posture.get("schema") != FLEET_POSTURE_SCHEMA:
        errors.append("fleet_posture.schema_invalid")
    model = as_dict(posture.get("operating_model"))
    main_authority = as_dict(model.get("main_authority"))
    if model.get("main_agent_id") != "main" or model.get("configured_total_agent_count") != 7:
        errors.append("fleet_posture.operating_model_invalid")
    for key, expected in FLEET_OPERATING_MODEL["main_authority"].items():
        if main_authority.get(key) is not expected:
            errors.append(f"fleet_posture.main_authority.{key}")
    containment = as_dict(posture.get("containment"))
    if containment.get("workspace_isolation_is_not_hard_sandbox") is not True:
        errors.append("fleet_posture.workspace_isolation_limit_missing")
    if containment.get("automatic_runtime_change_allowed") is not False:
        errors.append("fleet_posture.automatic_runtime_change_allowed")
    posture_privacy = as_dict(posture.get("privacy_contract"))
    for key in ("raw_prompt_stored", "raw_response_stored", "tool_payload_stored"):
        if posture_privacy and posture_privacy.get(key) is not False:
            errors.append(f"fleet_posture.{key}_not_false")
    cron_fleet = as_dict(payload.get("cron_fleet_health"))
    if (
        payload.get("status") != "fallback_startup_brief"
        and cron_fleet.get("job_count") is not None
        and cron_fleet.get("requires_attention_count") is None
    ):
        errors.append("cron_fleet_health.requires_attention_count_missing")
    wf78 = as_dict(payload.get("wf78_visibility"))
    if wf78 and wf78.get("canonical_top_of_funnel") != "owner_review_ready_count":
        errors.append("wf78_visibility.canonical_top_of_funnel_drift")
    paper = as_dict(payload.get("paper_top_blocker_summary"))
    if paper and int(paper.get("execution_ready_count") or 0) == 0 and paper.get("would_buy_shadow_tickers") and not paper.get("top_blocker_code"):
        errors.append("paper_top_blocker_summary.missing_top_blocker")
    cron_blocked_or_escalated = int(pm.get("cron_blocked") or 0) + int(pm.get("cron_escalation_signals") or 0)
    if cron_blocked_or_escalated and not wf74.get("cron_migration_repair_visible"):
        errors.append("wf74_pickup.missing_cron_migration_repair")
    if (
        wf74.get("cron_migration_repair_visible")
        and int(wf74.get("cron_migration_repair_followup_count") or 0) == 0
        and not wf74.get("cron_migration_repair_plan_visible")
    ):
        errors.append("wf74_pickup.missing_cron_migration_followup")
    if wf74.get("workflow_blocker_followup_visible") and int(wf74.get("workflow_blocker_followup_count") or 0) == 0:
        errors.append("wf74_pickup.missing_workflow_blocker_followups")
    if int(wf74.get("auto_apply_count") or 0):
        errors.append("wf74_pickup.auto_apply_nonzero")
    if otel and otel.get("auto_apply_allowed") is not False:
        errors.append("otel_learning_loop.auto_apply_allowed_not_false")
    if wf88_wiki.get("present") and wf88_wiki.get("validation") == "blocked":
        errors.append("wf88_wiki_synthesis.validation_blocked")
    if wf88_wiki.get("present") and wf88_wiki.get("recommendation_leak_guard_pass") is False:
        errors.append("wf88_wiki_synthesis.recommendation_leak_guard_failed")
    if int(wf88_wiki.get("auto_apply_count") or 0):
        errors.append("wf88_wiki_synthesis.auto_apply_nonzero")
    if wiki_bootstrap.get("present") is not True:
        errors.append("wiki_bootstrap_proof.missing")
    if wiki_bootstrap.get("validation") == "blocked":
        errors.append("wiki_bootstrap_proof.validation_blocked")
    if int(wiki_bootstrap.get("missing_file_count") or 0):
        errors.append("wiki_bootstrap_proof.missing_file_count_nonzero")
    if int(wiki_bootstrap.get("missing_marker_count") or 0):
        errors.append("wiki_bootstrap_proof.missing_marker_count_nonzero")
    if wiki_bootstrap.get("schema") != "veritas.wiki_bootstrap_proof.v2":
        errors.append("wiki_bootstrap_proof.semantic_contract_schema_missing")
    if int(wiki_bootstrap.get("missing_semantic_marker_count") or 0):
        errors.append("wiki_bootstrap_proof.missing_semantic_marker_count_nonzero")
    if wiki_bootstrap.get("semantic_render_hash_match") is not True:
        errors.append("wiki_bootstrap_proof.semantic_render_hash_mismatch")
    if wiki_bootstrap.get("recommendation_leak_guard_pass") is False:
        errors.append("wiki_bootstrap_proof.recommendation_leak_guard_failed")
    if int(wiki_bootstrap.get("auto_apply_count") or 0):
        errors.append("wiki_bootstrap_proof.auto_apply_nonzero")
    if wiki_bootstrap.get("no_orphan_validation") == "blocked":
        errors.append("wiki_bootstrap_proof.no_orphan_validation_blocked")
    if int(wiki_bootstrap.get("actionable_orphan_count") or 0):
        errors.append("wiki_bootstrap_proof.actionable_orphan_count_nonzero")
    if int(wiki_bootstrap.get("actionable_missing_contract_count") or 0):
        errors.append("wiki_bootstrap_proof.actionable_missing_contract_count_nonzero")
    if int(actionable_queue.get("orphan_count") or 0):
        errors.append("actionable_improvement_queue.orphan_count_nonzero")
    if int(actionable_queue.get("missing_contract_count") or 0):
        errors.append("actionable_improvement_queue.missing_contract_count_nonzero")
    if actionable_queue.get("no_orphan_validation") == "blocked":
        errors.append("no_orphan_validator.validation_blocked")
    route_rows = [as_dict(row) for row in as_list(workflow_routing.get("routes"))]
    if route_rows:
        if int(workflow_routing.get("route_count") or 0) != len(route_rows):
            errors.append("workflow_routing.route_count_mismatch")
        if as_dict(workflow_routing.get("parity")).get("status") != "ok":
            errors.append("workflow_routing.parity_not_ok")
        for route in route_rows:
            if any(not route.get(key) for key in ("priority", "lifecycle", "readiness", "authority_class", "primary_owner_lane", "authoritative_next_action")):
                errors.append(f"workflow_routing.route_contract_incomplete:{route.get('workflow_id')}")
                break
    if lane_register.get("historical_lane_count") is not None:
        open_lanes = [as_dict(row) for row in as_list(lane_register.get("open_lanes"))]
        if int(lane_register.get("open_lane_count") or 0) != len(open_lanes):
            errors.append("lane_register.open_lane_count_mismatch")
        for lane in open_lanes:
            if any(not lane.get(key) for key in ("owner", "sla_status", "next_action")):
                errors.append(f"lane_register.open_lane_contract_incomplete:{lane.get('lane_id')}")
                break
    if continuity_retrieval and continuity_retrieval.get("local_fallback_available") not in {True, False}:
        errors.append("continuity_retrieval.fallback_visibility_invalid")
    active_items = [as_dict(item) for item in as_list(payload.get("active_items")) if as_dict(item).get("item")]
    if active_items:
        autonomy = as_dict(pm.get("autonomy"))
        expected_current = autonomy.get("inbox_top_job") or autonomy.get("dispatcher_selected_job")
        if autonomy.get("current_handoff_valid") and expected_current and active_items[0].get("source") != "pm_current_action":
            errors.append("active_items.first_item_not_current_pm_action")
    return {"status": "critical" if errors else "ok", "errors": errors}


def validation_for_loaded_card(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema")
    errors.extend(as_list(as_dict(payload.get("validation")).get("errors")))
    check = validate_payload(payload)
    errors.extend(check["errors"])
    if payload.get("status") != "fallback_startup_brief":
        errors.extend(loaded_card_stale_reasons(payload))
    return {"status": "critical" if errors else "ok", "errors": errors}


def load_read_only_card() -> tuple[dict[str, Any], str]:
    if OUT.exists():
        payload = load(OUT)
        payload["validation"] = validation_for_loaded_card(payload)
        return payload, "status_card"
    if STARTUP_PACKET.exists():
        payload = build_payload_from_startup_fallback()
        payload["validation"] = validation_for_loaded_card(payload)
        return payload, "startup_brief_fallback"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "critical",
        "purpose": "Cached status card missing.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "status_route_contract": STATUS_ROUTE_CONTRACT.copy(),
        "validation": {"status": "critical", "errors": ["missing_status_card", "missing_startup_brief_fallback"]},
    }, "missing"


def build_payload_from_startup_fallback() -> dict[str, Any]:
    startup = load(STARTUP_PACKET)
    summary = as_dict(startup.get("summary"))
    fallback_fleet_posture = as_dict(startup.get("fleet_posture")) or fleet_posture({})
    fallback_token_summary = {
        "total_tokens": summary.get("token_usage_total_tokens"),
        "pricing_status": summary.get("token_usage_pricing_status"),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": startup.get("generated_at_utc") or utc_now(),
        "status": "fallback_startup_brief",
        "purpose": "Fallback status card rendered from existing startup brief packet.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "status_route_contract": STATUS_ROUTE_CONTRACT.copy(),
        "operating_posture": build_runtime_posture(fallback_token_summary, {}, fallback=True),
        "execution_efficiency_policy": implementation_router.execution_efficiency_policy(),
        "execution_efficiency_projection_source": "scripts/project_implementation_router.py",
        "startup_efficiency_policy_matches_owner": as_dict(startup.get("execution_efficiency_policy")) == implementation_router.execution_efficiency_policy(),
        "isolated_agent_fleet": {
            "present": False,
            "status": fallback_fleet_posture.get("status") or "unavailable",
        },
        "fleet_posture": fallback_fleet_posture,
        "finance_os": {
            "wf84_data_plane": summary.get("wf84_status"),
            "wf85_decision_os": summary.get("wf85_status"),
            "tier_a_b_bands": {
                "missing_decision_grade": summary.get("tier_a_b_missing_decision_grade_band_count"),
                "missing_tickers": summary.get("tier_a_b_missing_decision_grade_band_tickers") or [],
            },
            "trade_grade_repair": {
                "rows": summary.get("finance_domain_repair_item_count"),
                "implementation_blockers": summary.get("implementation_blocker_count"),
            },
        },
        "pm_queue": {
            "pm_readiness_band": summary.get("pm_readiness_band"),
            "ready_jobs": summary.get("pm_ready_job_count"),
            "blocked_jobs": summary.get("pm_blocked_job_count"),
            "cron_escalation_signals": summary.get("cron_escalation_signal_count"),
            "cron_blocked": summary.get("cron_blocked_count"),
            "action_executor": {
                "status": summary.get("main_session_action_executor_status"),
                "selected": summary.get("main_session_action_executor_selected_job") or summary.get("main_session_action_executor_parallel_workstream"),
                "executed": summary.get("main_session_action_executor_executed"),
            },
        },
        "wf74_pickup": {
            "opportunity_count": summary.get("wf74_opportunity_count"),
            "high_priority_count": summary.get("wf74_high_priority_opportunity_count"),
            "top_opportunity_title": summary.get("wf74_top_opportunity_title"),
            "top_opportunity_display_title": (
                "Close remaining workflow-maturity follow-ups"
                if summary.get("wf74_top_opportunity_title") == WORKFLOW_BLOCKER_FOLLOWUP_TITLE
                and int(summary.get("wf74_workflow_blocker_followup_count") or 0)
                else summary.get("wf74_top_opportunity_title")
            ),
            "cron_blocked_or_escalated_count": (
                int(summary.get("cron_blocked_count") or 0)
                + int(summary.get("cron_escalation_signal_count") or 0)
            ),
            "cron_migration_repair_visible": summary.get("wf74_cron_migration_repair_visible"),
            "cron_migration_repair_priority": summary.get("wf74_cron_migration_repair_priority"),
            "cron_migration_repair_followup_count": summary.get("wf74_cron_migration_repair_followup_count"),
            "cron_migration_repair_plan_visible": summary.get("wf74_cron_migration_repair_plan_visible"),
            "cron_migration_repair_plan_status": summary.get("wf74_cron_migration_repair_plan_status"),
            "workflow_blocker_followup_visible": summary.get("wf74_workflow_blocker_followup_visible"),
            "workflow_blocker_followup_priority": summary.get("wf74_workflow_blocker_followup_priority"),
            "workflow_blocker_followup_count": summary.get("wf74_workflow_blocker_followup_count"),
            "workflow_blocker_followup_route_counts": summary.get("wf74_workflow_blocker_followup_route_counts"),
            "patch_plan_count": summary.get("wf74_auto_patch_patch_plan_count"),
            "skill_workshop_request_count": summary.get("wf74_auto_patch_skill_workshop_request_count"),
            "owner_gated_plan_count": summary.get("wf74_auto_patch_owner_gated_plan_count"),
            "auto_apply_count": summary.get("wf74_auto_patch_auto_apply_count"),
            "decision_docket_row_count": summary.get("wf74_decision_docket_row_count"),
            "decision_docket_active_action_count": summary.get("wf74_decision_docket_active_action_count"),
            "decision_docket_fix_now_count": summary.get("wf74_decision_docket_fix_now_count"),
            "decision_docket_owner_decision_count": summary.get("wf74_decision_docket_owner_decision_count"),
            "decision_docket_market_session_accrual_count": summary.get("wf74_decision_docket_market_session_accrual_count"),
            "decision_docket_monitor_only_count": summary.get("wf74_decision_docket_monitor_only_count"),
            "decision_docket_hard_stop_count": summary.get("wf74_decision_docket_hard_stop_count"),
            "decision_docket_next_safe_action": summary.get("wf74_decision_docket_next_safe_action"),
            "next_safe_action": "Run main_session_greenkeeper_controller for WF74 pickup; inspect followups before scoped implementation.",
        },
        "otel_learning_loop": {
            "present": summary.get("otel_learning_loop_status") is not None,
            "status": summary.get("otel_learning_loop_status"),
            "validation": summary.get("otel_learning_loop_validation"),
            "collector_health": summary.get("otel_collector_health"),
            "drift_status": summary.get("otel_drift_status"),
            "token_coverage_ratio": summary.get("otel_token_coverage_ratio"),
            "cost_coverage_ratio": summary.get("otel_cost_coverage_ratio"),
            "recommendation_count": summary.get("otel_recommendation_count"),
            "carry_forward_status": summary.get("otel_carry_forward_status"),
            "auto_implementation_status": summary.get("otel_auto_implementation_status"),
            "auto_apply_allowed": False,
            "next_safe_action": summary.get("otel_next_safe_action"),
        },
        "wf88_wiki_synthesis": {
            "present": summary.get("wf88_wiki_synthesis_status") is not None,
            "status": summary.get("wf88_wiki_synthesis_status"),
            "validation": summary.get("wf88_wiki_synthesis_validation"),
            "page_count": summary.get("wf88_wiki_page_count"),
            "self_prompt_count": summary.get("wf88_wiki_self_prompt_count"),
            "action_item_count": summary.get("wf88_wiki_action_item_count"),
            "recommendation_leak_guard_pass": summary.get("wf88_wiki_recommendation_leak_guard_pass"),
            "open_unrouted_recommendation_count": summary.get("wf88_wiki_open_unrouted_recommendation_count"),
            "auto_apply_count": summary.get("wf88_wiki_auto_apply_count"),
            "rsi_status": summary.get("wf88_wiki_rsi_status"),
            "followup_required_open_count": summary.get("wf88_wiki_followup_required_open_count"),
            "recommendation_later_outcome_graded_rows": summary.get("wf88_wiki_recommendation_later_outcome_graded_rows"),
            "next_safe_action": summary.get("wf88_wiki_next_safe_action"),
        },
        "wiki_bootstrap_proof": {
            "present": summary.get("wiki_bootstrap_present") is True,
            "schema": summary.get("wiki_bootstrap_schema"),
            "status": summary.get("wiki_bootstrap_status"),
            "validation": summary.get("wiki_bootstrap_validation"),
            "bootstrap_gate": summary.get("wiki_bootstrap_gate"),
            "required_file_count": summary.get("wiki_bootstrap_required_file_count"),
            "validated_file_count": summary.get("wiki_bootstrap_validated_file_count"),
            "missing_file_count": summary.get("wiki_bootstrap_missing_file_count"),
            "missing_marker_count": summary.get("wiki_bootstrap_missing_marker_count"),
            "missing_semantic_marker_count": summary.get("wiki_bootstrap_missing_semantic_marker_count"),
            "semantic_render_hash_match": summary.get("wiki_bootstrap_semantic_render_hash_match"),
            "recommendation_leak_guard_pass": summary.get("wiki_bootstrap_recommendation_leak_guard_pass"),
            "auto_apply_count": summary.get("wiki_bootstrap_auto_apply_count"),
            "no_orphan_validation": summary.get("wiki_bootstrap_no_orphan_validation"),
            "actionable_orphan_count": summary.get("wiki_bootstrap_actionable_orphan_count"),
            "actionable_missing_contract_count": summary.get("wiki_bootstrap_actionable_missing_contract_count"),
            "next_safe_action": summary.get("wiki_bootstrap_next_safe_action"),
        },
        "actionable_improvement_queue": {
            "present": summary.get("actionable_queue_status") is not None,
            "status": summary.get("actionable_queue_status"),
            "validation": summary.get("actionable_queue_validation"),
            "action_item_count": summary.get("actionable_queue_item_count"),
            "orphan_count": summary.get("actionable_queue_orphan_count"),
            "missing_contract_count": summary.get("actionable_queue_missing_contract_count"),
            "owner_decision_count": summary.get("actionable_queue_owner_decision_count"),
            "monitor_only_count": summary.get("actionable_queue_monitor_only_count"),
            "top_action_title": summary.get("actionable_queue_top_action_title"),
            "top_action_destination": summary.get("actionable_queue_top_action_destination"),
            "top_next_action": summary.get("actionable_queue_top_next_action"),
            "no_orphan_status": summary.get("no_orphan_validator_status"),
            "no_orphan_validation": summary.get("no_orphan_validator_validation"),
            "no_orphan_validation_passed": summary.get("no_orphan_validation_passed"),
        },
        "recent_work": [],
        "active_items": [],
        "next_actions": [
            summary.get("main_session_action_executor_next_safe_action"),
            summary.get("owner_gated_next_safe_action"),
            summary.get("improvement_top_next_action"),
        ],
        "stale_inputs": startup.get("stale_inputs") or [],
        "input_validation_warnings": startup.get("input_validation_warnings") or [],
        "read_only_status_question_rule": "Fallback only: refresh the status card later, but do not rebuild PM/cron for shallow status.",
        "validation": {"status": "ok", "errors": []},
    }


def fmt(value: Any) -> str:
    if value is None:
        return "not cached"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def generated_label(payload: dict[str, Any]) -> str:
    raw = payload.get("generated_at_utc")
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except ValueError:
        return fmt(raw)
    return dt.strftime("%a %Y-%m-%d %H:%M MST")


def artifact_pointer(path: Path) -> dict[str, Any]:
    """Return a bounded integrity pointer without embedding artifact contents."""
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        relative = path.as_posix()
    pointer: dict[str, Any] = {"path": relative, "present": path.is_file()}
    if not pointer["present"]:
        return pointer
    try:
        raw = path.read_bytes()
    except OSError:
        pointer["present"] = False
        pointer["read_error"] = True
        return pointer
    pointer.update({"size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return pointer


def compact_item(item: Any) -> dict[str, Any]:
    row = as_dict(item)
    return {
        key: row.get(key)
        for key in ("item", "state", "source", "next_action", "owner_action_required")
        if row.get(key) is not None
    }


def compact_frontdoor_projection(payload: dict[str, Any], full_status_path: Path = OUT) -> dict[str, Any]:
    """Project shallow startup/status truth and defer full proof to hashed drilldowns."""
    operating = as_dict(payload.get("operating_posture"))
    finance = as_dict(payload.get("finance_os"))
    sql = as_dict(finance.get("sql_canon"))
    bands = as_dict(finance.get("tier_a_b_bands"))
    pm = as_dict(payload.get("pm_queue"))
    wf74 = as_dict(payload.get("wf74_pickup"))
    wiki = as_dict(payload.get("wiki_bootstrap_proof"))
    routing = as_dict(payload.get("workflow_routing"))
    lane_register = as_dict(payload.get("lane_register"))
    retrieval = as_dict(payload.get("continuity_retrieval"))
    fleet = as_dict(payload.get("isolated_agent_fleet"))
    fleet_summary = as_dict(fleet.get("summary"))
    wf78_tier = as_dict(payload.get("wf78_legacy_label_guard"))
    policy = as_dict(payload.get("execution_efficiency_policy"))
    quality = as_dict(policy.get("quality_weighted_efficiency"))
    validation = as_dict(payload.get("validation"))
    errors = as_list(validation.get("errors"))
    warnings = as_list(validation.get("warnings"))
    input_warnings = as_list(payload.get("input_validation_warnings"))
    stale_inputs = as_list(payload.get("stale_inputs"))

    projected = {
        "schema": FRONTDOOR_SCHEMA,
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "validation": {
            "status": validation.get("status"),
            "error_count": len(errors),
            "warning_count": len(warnings) + len(input_warnings),
            "errors": errors[:8],
            "warnings": (warnings + input_warnings)[:8],
        },
        "operating_posture": {
            "expected_route": as_dict(operating.get("expected_route")),
            "actual_route": as_dict(operating.get("actual_route")),
            "route_conformance": operating.get("route_conformance"),
            "context": operating.get("context"),
            "session": operating.get("session"),
            "gateway": operating.get("gateway"),
            "tokens": {
                "workspace_total_tokens": as_dict(operating.get("tokens")).get("workspace_total_tokens"),
                "status": as_dict(operating.get("tokens")).get("last_24h_burn_status")
                or as_dict(operating.get("tokens")).get("pricing_status"),
            },
        },
        "efficiency_guard": {
            "policy_schema": policy.get("schema"),
            "route_order": [
                {
                    "execution_backend": as_dict(row).get("execution_backend"),
                    "expected_model_path": as_dict(row).get("expected_model_path"),
                    "expected_thinking": as_dict(row).get("expected_thinking"),
                }
                for row in as_list(policy.get("route_order"))
            ],
            "minimum_comparable_main_accepted_jobs": quality.get("minimum_comparable_main_accepted_jobs"),
            "automatic_route_promotion_allowed": quality.get("automatic_route_promotion_allowed"),
        },
        "finance": {
            "wf84_data_plane": finance.get("wf84_data_plane"),
            "wf85_decision_os": finance.get("wf85_decision_os"),
            "sql_status": sql.get("status"),
            "securities": sql.get("securities"),
            "complete_current_bands": bands.get("complete_current"),
            "missing_decision_grade_bands": bands.get("missing_decision_grade"),
        },
        "pm_queue": {
            "readiness_band": pm.get("pm_readiness_band"),
            "ready_jobs": pm.get("ready_jobs"),
            "blocked_jobs": pm.get("blocked_jobs"),
            "cron_escalation_signals": pm.get("cron_escalation_signals"),
            "cron_blocked": pm.get("cron_blocked"),
        },
        "workflow_routing": {
            "status": routing.get("status"),
            "route_count": routing.get("route_count"),
            "active_build_queue_count": routing.get("active_build_queue_count"),
            "paused_count": routing.get("paused_count"),
            "refresh_required_count": routing.get("refresh_required_count"),
            "paper_fail_closed_count": routing.get("paper_fail_closed_count"),
            "parity": as_dict(routing.get("parity")),
        },
        "lane_register": {
            "open_lane_count": lane_register.get("open_lane_count"),
            "open_blocked_lane_count": lane_register.get("open_blocked_lane_count"),
            "attention_open_lane_count": lane_register.get("attention_open_lane_count"),
        },
        "continuity_retrieval": {
            "status": retrieval.get("status"),
            "local_fallback_available": retrieval.get("local_fallback_available"),
            "last_local_query_status": retrieval.get("last_local_query_status"),
        },
        "wf74": {
            "top_opportunity": wf74.get("top_opportunity_display_title") or wf74.get("top_opportunity_title"),
            "high_priority_count": wf74.get("high_priority_count"),
            "next_safe_action": wf74.get("next_safe_action"),
        },
        "wiki_bootstrap": {
            "status": wiki.get("status"),
            "validation": wiki.get("validation"),
            "gate": wiki.get("bootstrap_gate"),
            "semantic_render_hash_match": wiki.get("semantic_render_hash_match"),
            "next_safe_action": wiki.get("next_safe_action"),
        },
        "wf78_legacy_label_guard": {
            "status": wf78_tier.get("status"),
            "active_legacy_label_refs": wf78_tier.get("active_legacy_label_refs"),
            "legacy_seeded_tier_count": wf78_tier.get("legacy_seeded_tier_count"),
            "legacy_seeded_tickers": wf78_tier.get("legacy_seeded_tickers"),
            "router_ahead_of_owner_approved_label_count": wf78_tier.get("router_ahead_of_owner_approved_label_count"),
            "router_ahead_of_owner_approved_label_tickers": wf78_tier.get("router_ahead_of_owner_approved_label_tickers"),
        },
        "fleet": {
            "status": fleet.get("status"),
            "utilized_agent_count": fleet_summary.get("utilized_agent_count"),
            "configured_agent_count": fleet_summary.get("configured_agent_count"),
            "main_accepted_count": fleet_summary.get("main_accepted_count"),
            "qa_yield_percent": fleet_summary.get("qa_yield_percent"),
            "attribution_gap_count": fleet_summary.get("attribution_gap_count"),
        },
        "recent_work": [item for item in as_list(payload.get("recent_work")) if item][:3],
        "active_items": [compact_item(item) for item in as_list(payload.get("active_items")) if compact_item(item)][:5],
        "next_actions": [item for item in as_list(payload.get("next_actions")) if item][:4],
        "stale_inputs": stale_inputs[:12],
        "authority_boundary": as_dict(payload.get("authority_boundary")),
        "drilldown": {
            "rule": "Read nested proof only for a material request, a critical validation result, or a blocked decision.",
            "artifacts": {
                "full_status": artifact_pointer(full_status_path),
                "startup": artifact_pointer(STARTUP_PACKET),
                "future_session": artifact_pointer(FUTURE_PACKET),
            },
        },
    }
    projected["projection_sha256"] = hashlib.sha256(
        json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return projected


def validation_for_loaded_frontdoor(payload: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(payload.get("validation")).copy()
    errors = list(as_list(validation.get("errors")))
    warnings = list(as_list(validation.get("warnings")))
    if payload.get("schema") != FRONTDOOR_SCHEMA:
        errors.append("frontdoor_schema_invalid")
    pointer = as_dict(as_dict(payload.get("drilldown")).get("artifacts")).get("full_status")
    pointer = as_dict(pointer)
    observed = artifact_pointer(OUT)
    if pointer.get("present") is True and observed.get("present") is True:
        if pointer.get("sha256") != observed.get("sha256"):
            errors.append("frontdoor_full_status_hash_mismatch")
    elif pointer.get("present") != observed.get("present"):
        errors.append("frontdoor_full_status_presence_mismatch")
    validation.update({
        "status": "critical" if errors else validation.get("status", "ok"),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    })
    return validation


def load_read_only_frontdoor() -> tuple[dict[str, Any], str]:
    if FRONTDOOR_OUT.exists():
        payload = load(FRONTDOOR_OUT)
        payload["validation"] = validation_for_loaded_frontdoor(payload)
        if payload["validation"]["status"] == "critical":
            payload["status"] = "critical"
        return payload, "status_frontdoor"
    full, source = load_read_only_card()
    return compact_frontdoor_projection(full, OUT), f"{source}_compact_fallback"


def render_frontdoor_markdown(payload: dict[str, Any], source: str) -> str:
    operating = as_dict(payload.get("operating_posture"))
    expected = as_dict(operating.get("expected_route"))
    actual = as_dict(operating.get("actual_route"))
    pm = as_dict(payload.get("pm_queue"))
    finance = as_dict(payload.get("finance"))
    wiki = as_dict(payload.get("wiki_bootstrap"))
    wf78_tier = as_dict(payload.get("wf78_legacy_label_guard"))
    efficiency = as_dict(payload.get("efficiency_guard"))
    lines = [
        f"## Status - {generated_label(payload)}",
        "",
        f"Source: `{source}`; status: `{payload.get('status')}`; validation: `{as_dict(payload.get('validation')).get('status')}`.",
        "",
        "### Compact Operating Truth",
        "",
        *table([
            ("Expected route", f"{expected.get('execution_backend')} / {expected.get('model_path')} / effort={expected.get('thinking')}"),
            ("Actual route", f"{actual.get('status')} / conformance={operating.get('route_conformance')}"),
            ("Context", operating.get("context")),
            ("Tokens", as_dict(operating.get("tokens")).get("workspace_total_tokens")),
            ("WF84/WF85", f"{finance.get('wf84_data_plane')} / {finance.get('wf85_decision_os')}"),
            ("PM queue", f"{pm.get('ready_jobs')} ready / {pm.get('blocked_jobs')} blocked"),
            ("Wiki bootstrap", f"{wiki.get('status')} / validation={wiki.get('validation')}"),
            ("WF78 legacy-label guard", f"legacy-label refs={wf78_tier.get('active_legacy_label_refs')} (target 0) / legacy-seeded tiers={wf78_tier.get('legacy_seeded_tier_count')} (target 0, owner-gated) / router-ahead-of-label={wf78_tier.get('router_ahead_of_owner_approved_label_count')} {wf78_tier.get('router_ahead_of_owner_approved_label_tickers')}"),
            ("Route evidence gate", f"{efficiency.get('minimum_comparable_main_accepted_jobs')} comparable Main-accepted jobs; auto-promotion={fmt(efficiency.get('automatic_route_promotion_allowed'))}"),
        ]),
    ]
    recent = as_list(payload.get("recent_work"))
    active = [as_dict(item) for item in as_list(payload.get("active_items"))]
    actions = as_list(payload.get("next_actions"))
    if recent:
        lines.extend(["", "### Recent Work", "", *[f"- {item}" for item in recent]])
    if active:
        lines.extend(["", "### Active Items", "", *[f"- {item.get('item')}: {item.get('state')}" for item in active]])
    if actions:
        lines.extend(["", "### Next Actions", "", *[f"{index}. {item}" for index, item in enumerate(actions, 1)]])
    lines.extend(["", "Nested proof is deferred. Drill down through the hashed artifact pointers only when the request or validation state requires it."])
    return "\n".join(lines)


def table(rows: list[tuple[str, Any]]) -> list[str]:
    lines = ["| | |", "|---|---|"]
    for label, value in rows:
        lines.append(f"| **{label}** | {fmt(value)} |")
    return lines


def render_markdown(payload: dict[str, Any], source: str = "status_card") -> str:
    if payload.get("schema") == FRONTDOOR_SCHEMA:
        return render_frontdoor_markdown(payload, source)
    operating = as_dict(payload.get("operating_posture"))
    finance = as_dict(payload.get("finance_os"))
    sql = as_dict(finance.get("sql_canon"))
    bands = as_dict(finance.get("tier_a_b_bands"))
    repair = as_dict(finance.get("trade_grade_repair"))
    pm = as_dict(payload.get("pm_queue"))
    executor = as_dict(pm.get("action_executor"))
    autonomy = as_dict(pm.get("autonomy"))
    cron_fleet = as_dict(payload.get("cron_fleet_health"))
    artifacts = as_dict(payload.get("artifact_index_health"))
    wf78 = as_dict(payload.get("wf78_visibility"))
    wf78_tier = as_dict(payload.get("wf78_legacy_label_guard"))
    paper = as_dict(payload.get("paper_top_blocker_summary"))
    security = as_dict(payload.get("security_warnings"))
    wf74 = as_dict(payload.get("wf74_pickup"))
    otel = as_dict(payload.get("otel_learning_loop"))
    wf88_wiki = as_dict(payload.get("wf88_wiki_synthesis"))
    wiki_bootstrap = as_dict(payload.get("wiki_bootstrap_proof"))
    actionable_queue = as_dict(payload.get("actionable_improvement_queue"))
    fleet = as_dict(payload.get("isolated_agent_fleet"))
    fleet_posture = as_dict(payload.get("fleet_posture"))
    fleet_summary = as_dict(fleet.get("summary"))
    fleet_windows = as_dict(fleet.get("usage_windows"))
    fleet_reporting = as_dict(fleet_posture.get("reporting"))
    fleet_model = as_dict(fleet_posture.get("operating_model"))
    fleet_capacity = as_dict(fleet_posture.get("oauth_capacity_advisory"))
    fleet_containment = as_dict(fleet_posture.get("containment"))
    authority = as_dict(payload.get("authority_boundary"))
    recent = [item for item in as_list(payload.get("recent_work")) if item][:3]
    active = [as_dict(item) for item in as_list(payload.get("active_items")) if as_dict(item).get("item")][:5]
    next_actions = [item for item in as_list(payload.get("next_actions")) if item][:4]
    lines = [
        f"## Status - {generated_label(payload)}",
        "",
        f"Source: `{source}`; status: `{payload.get('status')}`; validation: `{as_dict(payload.get('validation')).get('status')}`.",
        "",
        "### Operating Posture",
        "",
        *table([
            ("Expected route", f"{as_dict(operating.get('expected_route')).get('execution_backend')} / {as_dict(operating.get('expected_route')).get('model_path')} / effort={as_dict(operating.get('expected_route')).get('thinking') or 'unspecified'}"),
            ("Actual route", f"{as_dict(operating.get('actual_route')).get('status')} / conformance={operating.get('route_conformance')}"),
            ("Implementation routing", "model-free first; explicit bounded native Terra; persistent Terra with fresh transport proof; Main/Sol explicit only"),
            ("Context", operating.get("context")),
            ("Session", operating.get("session")),
            ("Voice", operating.get("voice")),
            ("Gateway", operating.get("gateway")),
            ("Tokens", as_dict(operating.get("tokens")).get("workspace_total_tokens")),
            ("Token envelope", as_dict(operating.get("tokens")).get("last_24h_burn_status") or as_dict(operating.get("tokens")).get("pricing_status")),
            ("Agent fleet", f"{fleet.get('status')} / utilized {fleet_summary.get('utilized_agent_count')}/{fleet_summary.get('configured_agent_count')} / pricing-grade {fleet_summary.get('pricing_grade_attribution_coverage_percent')}%"),
            ("Fleet windows", f"5h={as_dict(fleet_windows.get('rolling_5h_observed')).get('total_tokens')} 24h={as_dict(fleet_windows.get('rolling_24h_gateway')).get('total_tokens')} closed7d={as_dict(fleet_windows.get('closed_7d_gateway')).get('total_tokens')} tokens"),
            ("Fleet outcomes", f"parent-complete={fleet_summary.get('parent_job_completed_count')} Main-accepted={fleet_summary.get('main_accepted_count')}/{fleet_summary.get('outcome_eligible_completed_lane_count')} tracked QA={fleet_summary.get('qa_pass_count')}/{fleet_summary.get('qa_review_completed_count')} ({fleet_summary.get('qa_yield_percent')}%) historical={fleet_summary.get('historical_or_untracked_completed_lane_count')} rework={fleet_summary.get('rework_count')} gaps={fleet_summary.get('attribution_gap_count')}"),
            ("OTEL carry-forward", f"{otel.get('status')} / drift={otel.get('drift_status')} / recs={otel.get('recommendation_count')} / auto-route={otel.get('auto_implementation_status')} / auto-apply={fmt(otel.get('auto_apply_allowed'))}"),
            ("WF88 wiki synthesis", f"{wf88_wiki.get('status')} / validation={wf88_wiki.get('validation')} / pages={wf88_wiki.get('page_count')} / prompts={wf88_wiki.get('self_prompt_count')} / leak_guard={fmt(wf88_wiki.get('recommendation_leak_guard_pass'))}"),
            ("Wiki bootstrap proof", f"{wiki_bootstrap.get('status')} / validation={wiki_bootstrap.get('validation')} / gate={wiki_bootstrap.get('bootstrap_gate')} / files={wiki_bootstrap.get('validated_file_count')}/{wiki_bootstrap.get('required_file_count')} / semantic-missing={wiki_bootstrap.get('missing_semantic_marker_count')} / semantic-hash={fmt(wiki_bootstrap.get('semantic_render_hash_match'))} / auto-apply={wiki_bootstrap.get('auto_apply_count')}"),
            ("Artifact index", f"{fmt(artifacts.get('artifact_index_exists'))}, {artifacts.get('tmp_json_count')} tmp json, {artifacts.get('wf78_json_count')} WF78 json"),
        ]),
        "",
        "### Fleet Posture",
        "",
        *table([
            ("Operating model", f"Main + {len(fleet_model.get('configured_isolated_agent_ids') or [])} configured isolated agents"),
            ("Main authority", "routing, final QC, sole acceptance, final judgment"),
            ("General route", fleet_model.get("general_route")),
            ("Finance route", fleet_model.get("finance_route")),
            ("Reporting", f"status={fleet_posture.get('status')} utilized={fleet_reporting.get('utilized_agent_count')}/{fleet_reporting.get('configured_agent_count')} pricing-grade={fleet_reporting.get('pricing_grade_attribution_coverage_percent')}%"),
            ("Outcome quality", f"accepted={fleet_reporting.get('main_accepted_count')} pending={fleet_reporting.get('main_acceptance_pending_count')} QA={fleet_reporting.get('qa_pass_count')}/{fleet_reporting.get('qa_review_completed_count')} rework={fleet_reporting.get('rework_count')} gaps={fleet_reporting.get('attribution_gap_count')}"),
            ("OAuth capacity", f"{fleet_capacity.get('status')} / tier={fleet_capacity.get('tier')} / remaining={fleet_capacity.get('remaining_percent')}% / automatic_action={fmt(fleet_capacity.get('automatic_action_allowed'))}"),
            ("Containment", f"{fleet_containment.get('status')} (hard sandbox proven={fmt(fleet_containment.get('hard_sandbox_proven'))}; workspace isolation is not a hard sandbox)"),
        ]),
        "",
        "### Finance OS",
        "",
        *table([
            ("WF84 data plane", finance.get("wf84_data_plane")),
            ("WF85 decision OS", finance.get("wf85_decision_os")),
            ("SQL canon", f"{sql.get('status')} - {sql.get('securities')} tickers, {sql.get('production_answers')} production answers"),
            ("Tier A/B bands", f"{bands.get('complete_current')} complete/current, {bands.get('missing_decision_grade')} missing decision-grade bands"),
            ("Trade-grade repair", f"{repair.get('rows')} rows, {repair.get('implementation_blockers')} implementation blockers"),
        ]),
        "",
        "### PM & Queue",
        "",
        *table([
            ("PM readiness", f"{pm.get('pm_readiness_band')} ({pm.get('pm_readiness_score')})"),
            ("Ready jobs", pm.get("ready_jobs")),
            ("Blocked jobs", pm.get("blocked_jobs")),
            ("Stale cockpit sources", pm.get("stale_cockpit_sources")),
            ("Cron", f"{pm.get('cron_escalation_signals')} escalation, {pm.get('cron_blocked')} blocked"),
            ("Cron fleet", f"{cron_fleet.get('fresh_count')} fresh, {cron_fleet.get('requires_attention_count')} attention, {cron_fleet.get('monitor_only_or_stale_count')} monitor/stale, {cron_fleet.get('quiet_success_count')} quiet"),
            ("Action executor", f"{executor.get('selected')} / executed={fmt(executor.get('executed'))}"),
            ("PM autonomy", f"dispatch={autonomy.get('dispatcher_action')}:{autonomy.get('dispatcher_selected_job')} worker={autonomy.get('worker_action')}:{autonomy.get('worker_selected_job')} executed={fmt(autonomy.get('worker_executed'))}"),
            ("Current PM action", f"{autonomy.get('inbox_action')}:{autonomy.get('inbox_top_job')}" if autonomy.get("current_handoff_valid") else "none - autonomy handoff stale/not ready"),
            ("WF78 lanes", f"owner={wf78.get('owner_review_ready_count')} market_pending={wf78.get('market_refresh_pending_count')} c_to_b={wf78.get('c_to_b_actionable_count')} tier_c_attention={wf78.get('tier_c_attention_count')}"),
            ("WF78 legacy-label guard", f"legacy-label refs={wf78_tier.get('active_legacy_label_refs')} (target 0) / legacy-seeded tiers={wf78_tier.get('legacy_seeded_tier_count')} (target 0, owner-gated) / router-ahead-of-label={wf78_tier.get('router_ahead_of_owner_approved_label_count')} {wf78_tier.get('router_ahead_of_owner_approved_label_tickers')}"),
            ("Paper blocker", f"{paper.get('guard_status')} / {paper.get('top_blocker_code')}"),
            ("Security warnings", f"{security.get('open_warning_count')} open"),
        ]),
        "",
        "### WF74 Pickup",
        "",
        *table([
            ("Top opportunity", wf74.get("top_opportunity_display_title") or wf74.get("top_opportunity_title")),
            ("High-priority opportunities", wf74.get("high_priority_count")),
            ("Cron migration repair", f"visible={fmt(wf74.get('cron_migration_repair_visible'))}, priority={wf74.get('cron_migration_repair_priority')}, followups={wf74.get('cron_migration_repair_followup_count')}, plan={fmt(wf74.get('cron_migration_repair_plan_visible'))}"),
            ("Workflow blocker followups", f"visible={fmt(wf74.get('workflow_blocker_followup_visible'))}, priority={wf74.get('workflow_blocker_followup_priority')}, followups={wf74.get('workflow_blocker_followup_count')}"),
            ("Patch/skill/owner plans", f"{wf74.get('patch_plan_count')} / {wf74.get('skill_workshop_request_count')} / {wf74.get('owner_gated_plan_count')}; auto-apply={wf74.get('auto_apply_count')}"),
            ("Decision docket", f"rows={wf74.get('decision_docket_row_count')}, active={wf74.get('decision_docket_active_action_count')}, fix-now={wf74.get('decision_docket_fix_now_count')}, market-accrual={wf74.get('decision_docket_market_session_accrual_count')}"),
            ("OTEL next action", otel.get("next_safe_action")),
            ("WF88 wiki next action", wf88_wiki.get("next_safe_action")),
            ("Wiki bootstrap next action", wiki_bootstrap.get("next_safe_action")),
            ("WF88 wiki debt", f"actions={wf88_wiki.get('action_item_count')}, followup-required={wf88_wiki.get('followup_required_open_count')}, later-graded={wf88_wiki.get('recommendation_later_outcome_graded_rows')}, RSI={wf88_wiki.get('rsi_status')}"),
            ("Actionable improvements", f"items={actionable_queue.get('action_item_count')}, orphans={actionable_queue.get('orphan_count')}, missing={actionable_queue.get('missing_contract_count')}, no-orphan={actionable_queue.get('no_orphan_validation')}"),
            ("Top actionable improvement", f"{actionable_queue.get('top_action_title')} -> {actionable_queue.get('top_action_destination')}"),
        ]),
    ]
    if recent:
        lines.extend(["", "### Recent Work", ""])
        for item in recent:
            lines.append(f"- {item}")
    if active:
        lines.extend(["", "### Active Items", "", "| # | Item | State |", "|---|---|---|"])
        for index, item in enumerate(active, 1):
            lines.append(f"| **{index}** | {fmt(item.get('item'))} | {fmt(item.get('state'))} |")
    lines.extend([
        "",
        "### Authority Boundaries",
        "",
        f"- Capital deployment approved: `{fmt(authority.get('capital_deployment_approved'))}`",
        f"- Trade/execution approved: `{fmt(authority.get('trade_or_execution_approved'))}`",
        f"- Paper/live execution allowed: `{fmt(authority.get('paper_or_live_execution_allowed'))}`",
        f"- Owner approval inferred: `{fmt(authority.get('owner_approval_inferred'))}`",
    ])
    if next_actions:
        lines.extend(["", "### Next Actions", ""])
        for index, action in enumerate(next_actions, 1):
            lines.append(f"{index}. {action}")
    if payload.get("stale_inputs"):
        lines.extend(["", f"Stale inputs: `{', '.join(payload.get('stale_inputs') or [])}`."])
    if payload.get("input_validation_warnings"):
        lines.extend(["", f"Input validation warnings: `{', '.join(payload.get('input_validation_warnings') or [])}`."])
    lines.extend(["", payload.get("read_only_status_question_rule", "")])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the cached status card.")
    parser.add_argument("--read-only", action="store_true", help="Render or validate without writing.")
    parser.add_argument("--frontdoor", action="store_true", help="Use the compact front-door projection and defer nested proof.")
    parser.add_argument("--render", action="store_true", help="Render a Markdown status card.")
    parser.add_argument("--json", action="store_true", dest="print_json", help="Print JSON payload.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--max-age-minutes", type=int, default=90)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--frontdoor-out", type=Path, default=FRONTDOOR_OUT)
    args = parser.parse_args()

    if args.read_only:
        if args.frontdoor:
            payload, source = load_read_only_frontdoor()
        else:
            payload, source = load_read_only_card()
    else:
        payload = build_payload(max_age_minutes=args.max_age_minutes)
        source = "built_from_existing_packets"
        if args.write:
            atomic_write_json(args.out, payload)
            atomic_write_json(args.frontdoor_out, compact_frontdoor_projection(payload, args.out))
        if args.frontdoor:
            payload = compact_frontdoor_projection(payload, args.out)
            source = "built_compact_from_existing_packets"

    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.render or args.read_only:
        print(render_markdown(payload, source=source))
    else:
        print(f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} source={source}")

    validation = as_dict(payload.get("validation"))
    if args.validate and validation.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
