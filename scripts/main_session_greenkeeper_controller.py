#!/usr/bin/env python3
"""Review-only greenkeeper over cron, PM, and handoff control surfaces.

The controller keeps the follow-up path visible and machine-checkable. It can
refresh the thin truth surfaces, classify cron/PM signals, detect stale sidecar
conflicts, and optionally run allowlisted review-only proof commands.

It does not edit cron schedules, mutate runtime/config/auth, change canon or
portfolio state, deliver externally, submit paper/live orders, touch accounts,
move money, or infer owner approval.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.command_guard import command_is_review_only_safe, parse_command
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
CRON_CONTRACTS = STATE / "cron-contracts"

OUT = TMP / "main-session-greenkeeper-controller.json"
LEDGER = STATE / "main-session-greenkeeper-action-ledger.jsonl"
CRON_CONTROL = TMP / "cron-control-packet.json"
CRON_SCORECARD = TMP / "cron-signal-scorecard.json"
ESCALATION = TMP / "escalation-trigger.json"
ESCALATION_CONSUMER = TMP / "main-session-escalation-consumer.json"
PM_CONTROL = TMP / "pm-control-packet.json"
PM_EXECUTION_LOOP = TMP / "pm-execution-loop.json"
PARALLEL_RECOMMENDATION = TMP / "parallel-lane-recommendation.json"
CONTROL_CLOSEOUT = TMP / "control-closeout-bundle.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
WF74_PROPOSAL_AUTOPILOT = TMP / "wf74-reflection-to-proposal-autopilot.json"
WF74_AUTO_PATCH_PROPOSER = TMP / "wf74-auto-patch-proposer.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
WORKFLOW_BLOCKER_FOLLOWUPS = TMP / "workflow-blocker-followups.json"
FINANCE_RESPONSE_QUALITY = TMP / "finance-response-quality-slice.json"
TRADE_GRADE_REPAIR_CONVEYOR = TMP / "trade-grade-repair-conveyor.json"
WF78_SOURCE_OPEN_WORK_PACKETS = TMP / "wf78-source-open-work-packets.json"

SCHEMA = "veritas.main_session_greenkeeper_controller.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "greenkeeper_decision_surface_only": True,
    "runs_allowlisted_review_only_commands": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "config_auth_channel_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FRONTDOOR_REFRESH_COMMANDS: list[tuple[str, list[str], int]] = [
    ("cron_freshness_spine", ["scripts\\cron_freshness_spine.py", "--write", "--validate"], 240),
    ("cron_signal_scorecard", ["scripts\\cron_signal_scorecard.py", "--write", "--validate"], 240),
    ("escalation_trigger", ["scripts\\escalation_trigger.py", "--write", "--validate"], 240),
    ("cron_control_packet", ["scripts\\cron_control_packet.py", "--write", "--validate"], 300),
    ("pm_control_packet", ["scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 300),
    ("parallel_lane_recommender", ["scripts\\parallel_lane_recommender.py", "--write", "--validate"], 240),
    ("pm_execution_loop_dry_run", ["scripts\\pm_execution_loop.py", "--write", "--validate"], 240),
]

SAFE_REPAIR_COMMANDS: dict[str, tuple[list[str], int]] = {
    "artifact_index_incremental": (["scripts\\artifact_index.py", "incremental"], 300),
    "artifact_index_validate": (["scripts\\artifact_index.py", "validate"], 300),
    "pm_cockpit_live_required_source_refresh": (
        ["scripts\\wf78_tier_capacity_policy_gate.py", "--write", "--write-db", "--validate"],
        240,
    ),
    "pm_control_packet": (["scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 300),
    "parallel_lane_recommender": (["scripts\\parallel_lane_recommender.py", "--write", "--validate"], 240),
    "workflow_advancement_scorecard": (
        ["scripts\\workflow_advancement_scorecard.py", "--write", "--validate"],
        240,
    ),
    "wf74_reflection_to_proposal_autopilot": (
        ["scripts\\wf74_reflection_to_proposal_autopilot.py", "--write", "--validate"],
        240,
    ),
    "wf74_auto_patch_proposer": (
        ["scripts\\wf74_auto_patch_proposer.py", "--write", "--validate"],
        240,
    ),
    "finance_response_quality_slice": (
        ["scripts\\finance_response_quality_slice.py", "--write", "--write-md", "--validate"],
        300,
    ),
    "trade_grade_decision_cards": (
        ["scripts\\trade_grade_decision_cards.py", "--write", "--validate"],
        300,
    ),
    "trade_grade_repair_conveyor": (
        ["scripts\\trade_grade_repair_conveyor.py", "--write", "--validate"],
        300,
    ),
    "finance_response_quality_repair_loop": (
        ["scripts\\finance_response_quality_repair_loop.py", "--write", "--write-md", "--validate"],
        300,
    ),
    "wf78_source_open_repair_executor": (
        ["scripts\\wf78_source_open_repair_executor.py", "--tier", "all", "--write", "--validate"],
        300,
    ),
    "wf78_source_open_work_packet": (
        ["scripts\\wf78_source_open_work_packet.py", "--write", "--validate"],
        300,
    ),
    "wf78_deployment_readiness_review": (
        ["scripts\\wf78_deployment_readiness_review.py", "--write", "--validate"],
        300,
    ),
    "wf78_tier_weighted_freshness_resolver": (
        ["scripts\\wf78_tier_weighted_freshness_resolver.py", "--write", "--validate"],
        300,
    ),
}

SOFT_FRONTDOOR_FAILURES = {"parallel_lane_recommender"}

STOP_LINE_TOKENS = (
    "--apply",
    "--import",
    "--submit",
    "--cancel",
    "--sell",
    "--buy",
    "--archive",
    "--delete",
    "--live",
    "alpaca",
    "openclaw.json",
    "db_lifecycle_archive_apply",
    "finance_sql_canon",
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


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(path: Path) -> float | None:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - mtime).total_seconds() / 3600), 2)


def command_is_greenkeeper_safe(parts: list[str], *, allow_execute: bool = False) -> bool:
    command = " ".join(parts)
    lowered = f" {command.lower()} "
    if any(token in lowered for token in STOP_LINE_TOKENS):
        return False
    if allow_execute and parts[:1] == ["scripts\\pm_execution_loop.py"] and "--execute" in parts:
        stripped = [part for part in parts if part != "--execute"]
        return command_is_review_only_safe(" ".join(stripped))
    return command_is_review_only_safe(command)


def run_command(name: str, parts: list[str], timeout: int, *, allow_execute: bool = False) -> dict[str, Any]:
    started = utc_now()
    command = [sys.executable, *parts] if parts and parts[0].startswith("scripts\\") else parts
    if not command_is_greenkeeper_safe(parts, allow_execute=allow_execute):
        return {
            "name": name,
            "command": parts,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "blocked_by_guard": True,
            "stdout_preview": "",
            "stderr_preview": "command is outside greenkeeper review-only allowlist",
        }
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        ok = proc.returncode == 0
        accepted_no_work = False
        if not ok and name == "wf78_source_open_work_packet":
            packet = load_json(WF78_SOURCE_OPEN_WORK_PACKETS)
            accepted_no_work = wf78_source_open_work_packet_no_work_ok(packet)
            ok = accepted_no_work
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": ok,
            "accepted_no_work_wait_state": accepted_no_work,
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def wf78_source_open_work_packet_no_work_ok(packet: dict[str, Any]) -> bool:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    boundary = as_dict(packet.get("authority_boundary"))
    return (
        str(packet.get("status")) == "blocked"
        and summary.get("work_item_count") == 0
        and summary.get("packet_count") == 0
        and summary.get("top_recommendation") == "No packet work available."
        and validation.get("errors") == ["no source-open work items found"]
        and boundary.get("review_only") is True
        and boundary.get("work_packet_generation_only") is True
        and boundary.get("capital_deployment_allowed") is False
        and boundary.get("trade_or_execution_allowed") is False
        and boundary.get("paper_or_live_execution_allowed") is False
        and boundary.get("brokerage_or_account_action_allowed") is False
        and boundary.get("owner_approval_inferred") is False
    )


def maybe_refresh_frontdoors(args: argparse.Namespace) -> list[dict[str, Any]]:
    if not (args.refresh_frontdoors or args.execute_safe):
        return []
    return [run_command(name, parts, timeout) for name, parts, timeout in FRONTDOOR_REFRESH_COMMANDS]


def artifact_view(path: Path) -> dict[str, Any]:
    data = load_json(path)
    validation = as_dict(data.get("validation"))
    return {
        "path": rel(path),
        "present": bool(data),
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
        "age_hours": age_hours(path) if path.exists() else None,
    }


def classify_cron(cron_control: dict[str, Any], escalation: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    summary = as_dict(cron_control.get("summary"))
    embedded_escalation = as_dict(cron_control.get("escalation"))
    standalone_wake = bool(escalation.get("should_wake_main_session"))
    embedded_wake = bool(summary.get("should_wake_main_session") or embedded_escalation.get("should_wake_main_session"))
    standalone_count = int(escalation.get("escalation_signal_count") or 0)
    embedded_count = int(summary.get("escalation_signal_count") or embedded_escalation.get("escalation_signal_count") or 0)

    if standalone_wake != embedded_wake or standalone_count != embedded_count:
        actions.append({
            "id": "cron_escalation_sidecar_conflict",
            "classification": "auto_refresh",
            "severity": "high",
            "reason": "standalone escalation artifact disagrees with cron-control embedded escalation",
            "commands": ["cron_signal_scorecard", "escalation_trigger", "cron_control_packet"],
            "owner_gate_required": False,
        })
    if int(summary.get("stale_count") or 0) > 0:
        actions.append({
            "id": "cron_stale_jobs_present",
            "classification": "auto_refresh",
            "severity": "medium",
            "reason": f"{summary.get('stale_count')} cron jobs are stale",
            "commands": ["cron_freshness_spine", "cron_signal_scorecard", "escalation_trigger", "cron_control_packet"],
            "owner_gate_required": False,
        })
    if int(summary.get("blocked_count") or 0) > 0 or embedded_count > 0:
        actions.append({
            "id": "cron_blocked_or_escalated_signal",
            "classification": "main_handoff",
            "severity": "high",
            "reason": "cron has blocked or urgent escalation signals after refresh",
            "commands": [],
            "owner_gate_required": True,
        })
    if not actions:
        actions.append({
            "id": "cron_green",
            "classification": "no_reply",
            "severity": "info",
            "reason": "cron control is green or warning-only with no wake signal",
            "commands": [],
            "owner_gate_required": False,
        })
    return actions


def classify_pm(pm_control: dict[str, Any], pm_loop: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    summary = as_dict(pm_control.get("summary"))
    readiness = as_dict(summary.get("pm_readiness"))
    cockpit = as_dict(summary.get("pm_cockpit_source_health"))
    handoff = as_dict(summary.get("main_session_handoff"))
    implementation_queue = as_dict(summary.get("implementation_queue"))
    top_next_action = as_dict(summary.get("top_next_action"))
    loop_summary = as_dict(pm_loop.get("summary"))

    if int(cockpit.get("missing_required_count") or 0) or int(cockpit.get("stale_required_count") or 0):
        actions.append({
            "id": "pm_cockpit_required_source_drift",
            "classification": "auto_repair",
            "severity": "medium",
            "reason": "PM cockpit required source health is not clean",
            "commands": ["pm_cockpit_live_required_source_refresh", "pm_control_packet"],
            "owner_gate_required": False,
        })
    if int(readiness.get("stale_lanes") or 0) > 0:
        actions.append({
            "id": "pm_stale_lanes_present",
            "classification": "auto_repair",
            "severity": "medium",
            "reason": f"{readiness.get('stale_lanes')} stale PM lanes are present",
            "commands": ["pm_control_packet"],
            "owner_gate_required": False,
        })
    if int(implementation_queue.get("blocked_job_count") or 0) > 0:
        actions.append({
            "id": "pm_blocked_jobs_present",
            "classification": "blocked",
            "severity": "high",
            "reason": "PM implementation queue has blocked jobs",
            "commands": [],
            "owner_gate_required": True,
        })
    if handoff.get("signal_class") == "MAIN_SESSION_REQUIRED":
        actions.append({
            "id": "pm_main_session_handoff_ready",
            "classification": "main_handoff",
            "severity": "medium",
            "reason": f"PM selected {handoff.get('selected_action')} for main-session review",
            "commands": [],
            "owner_gate_required": False,
            "selected_job": as_list(loop_summary.get("selected_jobs"))[:1],
        })
    elif handoff.get("status") == "recently_dispatched" and top_next_action:
        actions.append({
            "id": "pm_main_session_followup_throttled_but_visible",
            "classification": "main_handoff",
            "severity": "low",
            "reason": f"PM dispatch cooldown is suppressing repeat wake, but top next action remains {top_next_action.get('action_id')}",
            "commands": [],
            "owner_gate_required": False,
            "selected_job": as_list(loop_summary.get("selected_jobs"))[:1],
        })
    if not actions:
        actions.append({
            "id": "pm_green",
            "classification": "no_reply",
            "severity": "info",
            "reason": "PM is green or warning-only with no blocked jobs",
            "commands": [],
            "owner_gate_required": False,
        })
    return actions


def review_only_boundary_clean(boundary: dict[str, Any]) -> bool:
    required_false = (
        "code_mutation_allowed",
        "skill_application_allowed",
        "collector_config_mutation_allowed",
        "runtime_config_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "external_export_allowed",
        "owner_approval_inferred",
    )
    return boundary.get("review_only") is True and all(boundary.get(key) is False for key in required_false)


def wf74_source_health(
    queue: dict[str, Any],
    proposals: dict[str, Any],
    auto_patch: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if queue.get("status") not in {"ok", "warning"}:
        reasons.append(f"queue_status={queue.get('status')}")
    if as_dict(queue.get("validation")).get("status") not in {"ok", "warning"}:
        reasons.append(f"queue_validation={as_dict(queue.get('validation')).get('status')}")
    if proposals.get("status") not in {"ok", "warning"}:
        reasons.append(f"proposal_status={proposals.get('status')}")
    if as_dict(proposals.get("validation")).get("status") not in {"ok", "warning"}:
        reasons.append(f"proposal_validation={as_dict(proposals.get('validation')).get('status')}")
    if auto_patch.get("status") not in {"ok", "warning"}:
        reasons.append(f"auto_patch_status={auto_patch.get('status')}")
    if as_dict(auto_patch.get("validation")).get("status") not in {"ok", "warning"}:
        reasons.append(f"auto_patch_validation={as_dict(auto_patch.get('validation')).get('status')}")
    if int(as_dict(proposals.get("summary")).get("auto_apply_count") or 0):
        reasons.append("proposal_auto_apply_count_nonzero")
    if int(as_dict(auto_patch.get("summary")).get("auto_apply_count") or 0):
        reasons.append("auto_patch_auto_apply_count_nonzero")
    return not reasons, reasons


def matching_proposals(proposals: dict[str, Any], opportunity_id: str) -> list[dict[str, Any]]:
    return [
        as_dict(row)
        for row in as_list(proposals.get("proposals"))
        if as_dict(row).get("source_opportunity_id") == opportunity_id
    ]


def classify_wf74_auto_handling(
    queue: dict[str, Any],
    proposals: dict[str, Any],
    auto_patch: dict[str, Any],
    finance_response: dict[str, Any],
    workflow_advancement: dict[str, Any],
    repair_conveyor: dict[str, Any],
    cron_control: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    cron_control = as_dict(cron_control)
    source_clean, source_reasons = wf74_source_health(queue, proposals, auto_patch)
    if not source_clean:
        return [{
            "id": "wf74_opportunity_sources_not_clean",
            "classification": "blocked",
            "severity": "high",
            "reason": "WF74 opportunity/proposal sources are not clean enough for automatic main-session handling",
            "source_reasons": source_reasons,
            "commands": [],
            "owner_gate_required": True,
        }]

    opportunities = [as_dict(row) for row in as_list(queue.get("opportunities"))]
    for row in opportunities:
        priority = int(row.get("priority") or 0)
        category = row.get("category")
        proposal_gate = row.get("proposal_gate")
        boundary = as_dict(row.get("authority_boundary"))
        if category == "workflow_maturity" and priority >= 85 and proposal_gate == "main_review_required":
            proposals_for_row = matching_proposals(proposals, str(row.get("opportunity_id")))
            action_base = {
                "id": "wf74_workflow_maturity_auto_followup",
                "opportunity_id": row.get("opportunity_id"),
                "classification": "auto_repair",
                "severity": "high",
                "reason": row.get("recommended_action") or "Route workflow blockers into scoped implementation follow-ups.",
                "title": row.get("title"),
                "priority": priority,
                "category": category,
                "proposal_gate": proposal_gate,
                "source_artifacts": [
                    rel(WF74_OPPORTUNITY_QUEUE),
                    rel(WF74_PROPOSAL_AUTOPILOT),
                    rel(WF74_AUTO_PATCH_PROPOSER),
                    rel(WORKFLOW_ADVANCEMENT),
                    rel(WORKFLOW_BLOCKER_FOLLOWUPS),
                ],
                "proposal_ids": [proposal.get("proposal_id") for proposal in proposals_for_row],
                "evidence": {
                    **as_dict(row.get("evidence")),
                    "workflow_blocker_followup_summary": as_dict(
                        workflow_advancement.get("workflow_blocker_followup_summary")
                    ),
                    "workflow_blocker_followup_count": as_dict(
                        workflow_advancement.get("workflow_blocker_followup_summary")
                    ).get("followup_count"),
                    "workflow_blocker_followup_routes": as_dict(
                        workflow_advancement.get("workflow_blocker_followup_summary")
                    ).get("route_counts"),
                },
                "commands": [
                    "workflow_advancement_scorecard",
                    "wf74_reflection_to_proposal_autopilot",
                    "wf74_auto_patch_proposer",
                    "pm_control_packet",
                ],
                "owner_gate_required": False,
                "auto_handling_scope": "create_or_refresh_review_only_implementation_followup",
            }
            if review_only_boundary_clean(boundary):
                actions.append(action_base)
            else:
                blocked = dict(action_base)
                blocked.update({
                    "classification": "blocked",
                    "reason": "WF74 workflow opportunity authority boundary is not review-only clean",
                    "commands": [],
                    "owner_gate_required": True,
                })
                actions.append(blocked)
        elif category == "cron_migration" and priority >= 85 and proposal_gate == "cron_migration_plan_only":
            proposals_for_row = matching_proposals(proposals, str(row.get("opportunity_id")))
            action_base = {
                "id": "wf74_cron_migration_repair_plan",
                "opportunity_id": row.get("opportunity_id"),
                "classification": "main_handoff",
                "severity": "high",
                "reason": row.get("recommended_action") or "Route blocked cron signals into a migration-ready repair plan.",
                "title": row.get("title"),
                "priority": priority,
                "category": category,
                "proposal_gate": proposal_gate,
                "source_artifacts": [
                    rel(WF74_OPPORTUNITY_QUEUE),
                    rel(WF74_PROPOSAL_AUTOPILOT),
                    rel(WF74_AUTO_PATCH_PROPOSER),
                    rel(CRON_CONTROL),
                    rel(CRON_SCORECARD),
                    rel(WORKFLOW_ADVANCEMENT),
                    rel(WORKFLOW_BLOCKER_FOLLOWUPS),
                ],
                "proposal_ids": [proposal.get("proposal_id") for proposal in proposals_for_row],
                "evidence": {
                    **as_dict(row.get("evidence")),
                    "cron_blocked_count": as_dict(cron_control.get("summary")).get("blocked_count"),
                    "cron_escalation_signal_count": as_dict(cron_control.get("summary")).get("escalation_signal_count"),
                    "workflow_blocker_followup_summary": as_dict(
                        workflow_advancement.get("workflow_blocker_followup_summary")
                    ),
                },
                "commands": [
                    "cron_control_packet",
                    "workflow_advancement_scorecard",
                    "wf74_reflection_to_proposal_autopilot",
                    "wf74_auto_patch_proposer",
                ],
                "owner_gate_required": True,
                "auto_handling_scope": "review_only_migration_repair_plan_visibility",
                "blocked_if_next_step_requires": [
                    "cron_schedule_or_state_mutation",
                    "runtime_config_auth_channel_mutation",
                    "external_delivery",
                    "finance_canon_or_portfolio_mutation",
                    "paper_or_live_order_action",
                    "owner_approval_inference",
                ],
            }
            if review_only_boundary_clean(boundary):
                actions.append(action_base)
            else:
                blocked = dict(action_base)
                blocked.update({
                    "classification": "blocked",
                    "reason": "WF74 cron migration opportunity authority boundary is not review-only clean",
                    "commands": [],
                    "owner_gate_required": True,
                })
                actions.append(blocked)
        elif category == "finance_mutation" and priority >= 85 and proposal_gate == "finance_repair_proposal_only":
            finance_summary = as_dict(finance_response.get("summary"))
            repair_summary = as_dict(repair_conveyor.get("summary"))
            proposals_for_row = matching_proposals(proposals, str(row.get("opportunity_id")))
            action_base = {
                "id": "wf74_finance_quality_repair_routing",
                "opportunity_id": row.get("opportunity_id"),
                "classification": "auto_repair",
                "severity": "high",
                "reason": row.get("recommended_action") or "Route finance response-quality gaps into repair proposals.",
                "title": row.get("title"),
                "priority": priority,
                "category": category,
                "proposal_gate": proposal_gate,
                "source_artifacts": [
                    rel(WF74_OPPORTUNITY_QUEUE),
                    rel(WF74_PROPOSAL_AUTOPILOT),
                    rel(FINANCE_RESPONSE_QUALITY),
                    rel(TRADE_GRADE_REPAIR_CONVEYOR),
                ],
                "proposal_ids": [proposal.get("proposal_id") for proposal in proposals_for_row],
                "evidence": {
                    **as_dict(row.get("evidence")),
                    "finance_response_quality_status": finance_response.get("status"),
                    "finance_source_freshness_blocked_count": finance_summary.get("source_freshness_blocked_count"),
                    "finance_remediation_tracks_needing_repair": finance_summary.get("remediation_tracks_needing_repair"),
                    "repair_conveyor_status": repair_conveyor.get("status"),
                    "repair_conveyor_row_count": repair_summary.get("total_repair_conveyor_row_count"),
                },
                "commands": [
                    "trade_grade_decision_cards",
                    "trade_grade_repair_conveyor",
                    "wf78_source_open_repair_executor",
                    "wf78_source_open_work_packet",
                    "wf78_deployment_readiness_review",
                    "wf78_tier_weighted_freshness_resolver",
                    "finance_response_quality_repair_loop",
                    "pm_control_packet",
                ],
                "post_repair_verification_commands": [
                    "finance_response_quality_slice",
                    "wf74_model_quality_collection_cron_runner",
                ],
                "owner_gate_required": False,
                "auto_handling_scope": "refresh_review_only_finance_source_open_repair_inputs_before_fail_closed_quality_verification",
                "blocked_if_next_step_requires": [
                    "canon_or_portfolio_mutation",
                    "cash_sizing_risk_or_execution_mutation",
                    "paper_or_live_order_action",
                    "owner_approval_inference",
                ],
            }
            if review_only_boundary_clean(boundary):
                actions.append(action_base)
            else:
                blocked = dict(action_base)
                blocked.update({
                    "classification": "blocked",
                    "reason": "WF74 finance opportunity authority boundary is not review-only clean",
                    "commands": [],
                    "owner_gate_required": True,
                })
                actions.append(blocked)
    return actions


def executable_command_from_message(message: str) -> str:
    if not isinstance(message, str) or not message:
        return ""
    patterns = [
        r"Execute exactly this single command:\s*([^\n\r]+)",
        r"Run the deterministic [^:]+:\s*([^\n\r]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            command = match.group(1).strip()
            for marker in (" Response contract:", " Boundaries:", " Do not ", " Then inspect "):
                if marker in command:
                    command = command.split(marker, 1)[0].strip()
            if command.endswith("."):
                command = command[:-1].strip()
            return command
    for line in message.splitlines():
        stripped = line.strip()
        if stripped.startswith("python scripts\\"):
            return stripped
    return ""


def approved_internal_telegram_runner_delivery(data: dict[str, Any]) -> bool:
    """Allow owner-only Telegram delivery when the runner contract is explicit."""
    delivery = as_dict(data.get("delivery"))
    internal_delivery = as_dict(data.get("internal_delivery"))
    authority = as_dict(data.get("authority_boundary"))
    if delivery.get("mode") != "none":
        return False
    return all([
        internal_delivery.get("mode") == "telegram_via_runner",
        internal_delivery.get("delivery_only_review_notification") is True,
        internal_delivery.get("cron_delivery_mode_remains_none") is True,
        internal_delivery.get("customer_or_public_delivery_allowed") is False,
        internal_delivery.get("approval_or_execution_authority_allowed") is False,
        authority.get("review_only") is True,
        authority.get("owner_telegram_delivery_allowed") is True
        or authority.get("telegram_delivery_allowed") is True,
        authority.get("customer_or_public_delivery_allowed") is False,
        authority.get("capital_deployment_allowed") is False,
        authority.get("paper_or_live_execution_allowed") is False,
        authority.get("brokerage_or_account_action_allowed") is False,
        authority.get("owner_approval_inferred") is False,
    ])


def contract_lint() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(CRON_CONTRACTS.glob("*.json")):
        data = load_json(path)
        if not data:
            continue
        payload = as_dict(data.get("payload"))
        delivery = as_dict(data.get("delivery"))
        authority = as_dict(data.get("authority_boundary"))
        message = str(payload.get("message") or "")
        executable = executable_command_from_message(message)
        executable_parts = parse_command(executable) if executable else []
        executable_has_send = "--send" in executable_parts
        text_has_send = "--send" in message.lower()
        text_mentions_telegram = "telegram" in message.lower()
        enabled = data.get("enabled") is True

        if (
            enabled
            and executable_has_send
            and delivery.get("mode") == "none"
            and not approved_internal_telegram_runner_delivery(data)
        ):
            findings.append({
                "id": "enabled_contract_internal_send_with_delivery_none",
                "classification": "owner_decision",
                "severity": "medium",
                "contract": rel(path),
                "name": data.get("name"),
                "reason": "executable command includes --send while cron delivery.mode is none; verify this is an approved internal notifier path",
                "executable_command": executable,
                "telegram_delivery_allowed": authority.get("telegram_delivery_allowed"),
                "paper_or_live_execution_allowed": authority.get("paper_or_live_execution_allowed"),
                "owner_gate_required": True,
            })
        elif enabled and text_has_send and not executable_has_send and text_mentions_telegram:
            findings.append({
                "id": "contract_text_mentions_send_but_executable_is_silent",
                "classification": "auto_refresh",
                "severity": "low",
                "contract": rel(path),
                "name": data.get("name"),
                "reason": "payload text mentions send/Telegram but extracted executable command is silent; keep scanner command-aware to avoid false positives",
                "executable_command": executable,
                "owner_gate_required": False,
            })
    return findings


def classify_sidecars(pm_control: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    control_generated = parse_utc(pm_control.get("generated_at_utc"))
    paths = as_dict(as_dict(pm_control.get("compatibility_sidecars")).get("paths"))
    for key in ("pm_main_session_handoff", "heartbeat_continuation_candidates"):
        rel_path = str(paths.get(key) or "")
        if not rel_path:
            continue
        path = ROOT / rel_path
        sidecar = load_json(path)
        sidecar_generated = parse_utc(sidecar.get("generated_at_utc"))
        stale = bool(control_generated and sidecar_generated and sidecar_generated < control_generated)
        if stale:
            findings.append({
                "id": f"{key}_older_than_pm_control",
                "classification": "auto_refresh",
                "severity": "low",
                "artifact": rel(path),
                "reason": "compatibility sidecar is older than pm-control-packet; use PM control as canonical route. Do not auto-refresh compatibility sidecars because --write-compat updates the dispatch ledger.",
                "commands": [],
                "owner_gate_required": False,
            })
    return findings


def action_commands(action: dict[str, Any]) -> list[tuple[str, list[str], int]]:
    selected: list[tuple[str, list[str], int]] = []
    for command_id in as_list(action.get("commands")):
        if command_id in SAFE_REPAIR_COMMANDS:
            parts, timeout = SAFE_REPAIR_COMMANDS[command_id]
            selected.append((command_id, parts, timeout))
        else:
            for name, parts, timeout in FRONTDOOR_REFRESH_COMMANDS:
                if name == command_id:
                    selected.append((name, parts, timeout))
                    break
    return selected


def execute_safe_actions(actions: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.execute_safe:
        return []
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        if action.get("classification") not in {"auto_refresh", "auto_repair"}:
            continue
        for command_id, parts, timeout in action_commands(action):
            key = " ".join(parts)
            if key in seen:
                continue
            seen.add(key)
            results.append(run_command(command_id, parts, timeout))
    if args.execute_pm_proof:
        results.append(run_command(
            "pm_execution_loop_execute",
            ["scripts\\pm_execution_loop.py", "--execute", "--write", "--validate"],
            900,
            allow_execute=True,
        ))
    return results


def append_ledger(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema": "veritas.main_session_greenkeeper_action_ledger.entry.v1",
        "recorded_at_utc": utc_now(),
        "report_generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "mode": report.get("mode"),
        "summary": report.get("summary"),
        "actions": report.get("actions"),
        "validation": report.get("validation"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    refresh_results = maybe_refresh_frontdoors(args)
    cron_control = load_json(CRON_CONTROL)
    escalation = load_json(ESCALATION)
    escalation_consumer = load_json(ESCALATION_CONSUMER)
    pm_control = load_json(PM_CONTROL)
    pm_loop = load_json(PM_EXECUTION_LOOP)
    parallel = load_json(PARALLEL_RECOMMENDATION)
    wf74_queue = load_json(WF74_OPPORTUNITY_QUEUE)
    wf74_proposals = load_json(WF74_PROPOSAL_AUTOPILOT)
    wf74_auto_patch = load_json(WF74_AUTO_PATCH_PROPOSER)
    finance_response = load_json(FINANCE_RESPONSE_QUALITY)
    workflow_advancement = load_json(WORKFLOW_ADVANCEMENT)
    repair_conveyor = load_json(TRADE_GRADE_REPAIR_CONVEYOR)

    actions = (
        classify_cron(cron_control, escalation)
        + classify_pm(pm_control, pm_loop)
        + classify_wf74_auto_handling(
            wf74_queue,
            wf74_proposals,
            wf74_auto_patch,
            finance_response,
            workflow_advancement,
            repair_conveyor,
            cron_control=cron_control,
        )
        + classify_sidecars(pm_control)
        + contract_lint()
    )
    execution_results = execute_safe_actions(actions, args)
    pre_execution_actions = actions
    if execution_results and all(result.get("ok") for result in execution_results):
        cron_control = load_json(CRON_CONTROL)
        escalation = load_json(ESCALATION)
        pm_control = load_json(PM_CONTROL)
        pm_loop = load_json(PM_EXECUTION_LOOP)
        parallel = load_json(PARALLEL_RECOMMENDATION)
        wf74_queue = load_json(WF74_OPPORTUNITY_QUEUE)
        wf74_proposals = load_json(WF74_PROPOSAL_AUTOPILOT)
        wf74_auto_patch = load_json(WF74_AUTO_PATCH_PROPOSER)
        finance_response = load_json(FINANCE_RESPONSE_QUALITY)
        workflow_advancement = load_json(WORKFLOW_ADVANCEMENT)
        repair_conveyor = load_json(TRADE_GRADE_REPAIR_CONVEYOR)
        actions = (
            classify_cron(cron_control, escalation)
            + classify_pm(pm_control, pm_loop)
            + classify_wf74_auto_handling(
                wf74_queue,
                wf74_proposals,
                wf74_auto_patch,
                finance_response,
                workflow_advancement,
                repair_conveyor,
                cron_control=cron_control,
            )
            + classify_sidecars(pm_control)
            + contract_lint()
        )

    errors: list[str] = []
    warnings: list[str] = []
    for result in refresh_results:
        if result.get("ok"):
            continue
        name = str(result.get("name") or "")
        if name in SOFT_FRONTDOOR_FAILURES:
            warnings.append(f"frontdoor_reported_residue:{name}")
        else:
            errors.append("frontdoor_refresh_failed")
    if any(not result.get("ok") for result in execution_results):
        errors.append("safe_action_execution_failed")
    if any(action.get("classification") == "blocked" for action in actions):
        warnings.append("blocked_action_present")
    if any(action.get("classification") == "owner_decision" for action in actions):
        warnings.append("owner_decision_action_present")
    if any(action.get("classification") == "main_handoff" for action in actions):
        warnings.append("main_handoff_action_present")
    opportunities = [as_dict(row) for row in as_list(wf74_queue.get("opportunities"))]
    cron_migration_opportunity_present = any(
        row.get("category") == "cron_migration"
        and int(row.get("priority") or 0) >= 85
        for row in opportunities
    )
    workflow_maturity_opportunity_present = any(
        row.get("title") == "Convert workflow advancement blockers into implementation follow-ups"
        or (
            row.get("category") == "workflow_maturity"
            and int(row.get("priority") or 0) >= 85
            and row.get("proposal_gate") == "main_review_required"
        )
        for row in opportunities
    )
    if cron_migration_opportunity_present and not any(action.get("id") == "wf74_cron_migration_repair_plan" for action in actions):
        errors.append("wf74_cron_migration_repair_plan_not_routed")
    if workflow_maturity_opportunity_present and not any(action.get("id") == "wf74_workflow_maturity_auto_followup" for action in actions):
        errors.append("wf74_workflow_maturity_followup_not_routed")

    action_counts: dict[str, int] = {}
    for action in actions:
        cls = str(action.get("classification") or "unknown")
        action_counts[cls] = action_counts.get(cls, 0) + 1

    status = "ok" if not errors else "blocked"
    if status == "ok" and warnings:
        status = "warning"

    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "execute_safe" if args.execute_safe else "dry_run",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "cron_control": artifact_view(CRON_CONTROL),
            "cron_signal_scorecard": artifact_view(CRON_SCORECARD),
            "escalation_trigger": artifact_view(ESCALATION),
            "main_session_escalation_consumer": artifact_view(ESCALATION_CONSUMER),
            "pm_control": artifact_view(PM_CONTROL),
            "pm_execution_loop": artifact_view(PM_EXECUTION_LOOP),
            "parallel_lane_recommendation": artifact_view(PARALLEL_RECOMMENDATION),
            "control_closeout": artifact_view(CONTROL_CLOSEOUT),
            "wf74_opportunity_queue": artifact_view(WF74_OPPORTUNITY_QUEUE),
            "wf74_proposal_autopilot": artifact_view(WF74_PROPOSAL_AUTOPILOT),
            "wf74_auto_patch_proposer": artifact_view(WF74_AUTO_PATCH_PROPOSER),
            "workflow_advancement_scorecard": artifact_view(WORKFLOW_ADVANCEMENT),
            "workflow_blocker_followups": artifact_view(WORKFLOW_BLOCKER_FOLLOWUPS),
            "finance_response_quality_slice": artifact_view(FINANCE_RESPONSE_QUALITY),
            "trade_grade_repair_conveyor": artifact_view(TRADE_GRADE_REPAIR_CONVEYOR),
        },
        "summary": {
            "action_count": len(actions),
            "action_counts": action_counts,
            "wf74_auto_handled_action_count": sum(
                1 for action in actions
                if str(action.get("id", "")).startswith("wf74_")
                and action.get("classification") in {"auto_refresh", "auto_repair"}
            ),
            "wf74_auto_handled_opportunity_ids": [
                action.get("opportunity_id")
                for action in actions
                if str(action.get("id", "")).startswith("wf74_")
                and action.get("classification") in {"auto_refresh", "auto_repair"}
                and action.get("opportunity_id")
            ],
            "wf74_cron_migration_plan_action_count": sum(
                1 for action in actions if action.get("id") == "wf74_cron_migration_repair_plan"
            ),
            "wf74_workflow_followup_action_count": sum(
                1 for action in actions if action.get("id") == "wf74_workflow_maturity_auto_followup"
            ),
            "wf74_startup_pickup_action_ids": [
                action.get("id")
                for action in actions
                if action.get("id") in {
                    "wf74_cron_migration_repair_plan",
                    "wf74_workflow_maturity_auto_followup",
                }
            ],
            "frontdoor_refresh_ran": bool(refresh_results),
            "frontdoor_refresh_failed": [r.get("name") for r in refresh_results if not r.get("ok")],
            "executed_safe_action_count": len(execution_results),
            "executed_safe_action_failed": [r.get("name") for r in execution_results if not r.get("ok")],
            "cron_should_wake_main_session": as_dict(cron_control.get("summary")).get("should_wake_main_session"),
            "cron_escalation_signal_count": as_dict(cron_control.get("summary")).get("escalation_signal_count"),
            "escalation_consumer_status": escalation_consumer.get("status"),
            "escalation_consumer_unresolved_count": as_dict(escalation_consumer.get("summary")).get("unresolved_count"),
            "escalation_consumer_executed_safe_action_count": as_dict(escalation_consumer.get("summary")).get("executed_safe_action_count"),
            "pm_main_session_handoff": as_dict(as_dict(pm_control.get("summary")).get("main_session_handoff")),
            "parallel_eligible_candidate_count": as_dict(parallel.get("summary")).get("eligible_candidate_count"),
            "next_safe_action": (
                "Inspect blocked_action_present before running safe execution."
                if "blocked_action_present" in warnings
                else "Use main_handoff actions for main-session review; auto_refresh/auto_repair actions may run under --execute-safe."
            ),
        },
        "actions": actions,
        "pre_execution_actions": pre_execution_actions if execution_results else [],
        "frontdoor_refresh_results": refresh_results,
        "safe_execution_results": execution_results,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "Dry-run by default; --execute-safe runs only allowlisted review-only proof/freshness commands.",
            "--execute-pm-proof is separately explicit and still routes through pm_execution_loop command guards.",
            "No cron schedule/state edit, runtime/config/auth mutation, external delivery, canon/portfolio mutation, SQL/ticker import, capital deployment, paper/live/account action, money movement, or owner approval inference.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Review-only main-session greenkeeper controller.")
    parser.add_argument("--write", action="store_true", help="Write the controller artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero only on blocked validation.")
    parser.add_argument("--refresh-frontdoors", action="store_true", help="Run allowlisted front-door proof refresh before classifying.")
    parser.add_argument("--execute-safe", action="store_true", help="Run allowlisted auto_refresh/auto_repair proof commands.")
    parser.add_argument("--execute-pm-proof", action="store_true", help="When --execute-safe is set, also run guarded pm_execution_loop --execute.")
    parser.add_argument("--append-ledger", action="store_true", help="Append this report summary to the greenkeeper action ledger.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args()

    if args.execute_pm_proof and not args.execute_safe:
        print("--execute-pm-proof requires --execute-safe", file=sys.stderr)
        return 2

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        if args.append_ledger:
            append_ledger(args.ledger, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} mode={report['mode']} "
            f"actions={report['summary']['action_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))

    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
