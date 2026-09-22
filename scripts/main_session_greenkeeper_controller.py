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
from zoneinfo import ZoneInfo

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
CONTROL_CLOSEOUT = TMP / "control-closeout-bundle.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
WF74_PROPOSAL_AUTOPILOT = TMP / "wf74-reflection-to-proposal-autopilot.json"
WF74_AUTO_PATCH_PROPOSER = TMP / "wf74-auto-patch-proposer.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
WORKFLOW_BLOCKER_FOLLOWUPS = TMP / "workflow-blocker-followups.json"
FINANCE_SQL_GUARD = TMP / "finance-sql-canon-access-validation.json"
ALERT_QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
ALERT_FRESHNESS_CONTROLLER = TMP / "alert-level-freshness-controller.json"
ALERT_RECOMMENDATIONS_DIGEST = TMP / "finance-alert-os-digest.json"
ALERTS_OS_PIVOT_VALIDATOR = TMP / "alerts-os-pivot-validator.json"

AZ = ZoneInfo("America/Phoenix")

SCHEMA = "veritas.main_session_greenkeeper_controller.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "greenkeeper_decision_surface_only": True,
    "runs_allowlisted_review_only_commands": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "config_auth_channel_mutation_allowed": False,
    "finance_state_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_or_execution_action_allowed": False,
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
]

SAFE_REPAIR_COMMANDS: dict[str, tuple[list[str], int]] = {
    "artifact_index_incremental": (["scripts\\artifact_index.py", "incremental"], 300),
    "artifact_index_validate": (["scripts\\artifact_index.py", "validate"], 300),
    "pm_control_packet": (["scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 300),
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
    # Canonical flags are mandatory. Without --dynamic-entitlement-scope the
    # chain falls back to the hard-coded 18-name ALERT_TICKERS instead of the
    # 32-member guarded-SQL scope, silently degrading the shared quote proof and
    # the alert-level controller. See the 2026-09-18 off-slot incident.
    "alerts_recommendations_midday_chain": (
        [
            "scripts\\run_alerts_recommendations_chain.py",
            "midday",
            "--timeout-seconds",
            "120",
            "--dynamic-entitlement-scope",
            "--recurring-reference-inputs",
            "--scope-origin",
            "phase3f_dynamic_entitlement",
            "--write",
            "--validate",
        ],
        600,
    ),
    "alerts_os_pivot_validator": (
        ["scripts\\alerts_os_pivot_validator.py", "--write", "--validate"],
        240,
    ),
}

# Commands whose output is semantically bound to a fixed local-time slot. The
# 2026-09-18 21:31 Phoenix incident ran the midday chain three hours off its
# 11:05 slot and overwrote shared quote and digest evidence with off-slot
# content. Off-slot runs are skipped rather than rewritten; the scheduled job
# owns the real slot.
SLOT_BOUND_COMMANDS: dict[str, tuple[int, int]] = {
    "alerts_recommendations_midday_chain": (11, 12),
}


def slot_bound_skip(command_id: str, now: datetime | None = None) -> str | None:
    """Return a skip reason when a slot-bound command sits outside its local slot."""
    window = SLOT_BOUND_COMMANDS.get(command_id)
    if window is None:
        return None
    local = (now or datetime.now(timezone.utc)).astimezone(AZ)
    if local.weekday() >= 5:
        return "outside_slot_non_trading_day"
    if not (window[0] <= local.hour < window[1]):
        return "outside_slot_window"
    return None


SOFT_FRONTDOOR_FAILURES: set[str] = set()

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


RETIRED_FINANCE_ROUTE_MARKERS = (
    "wf67", "wf68", "wf78", "wf86", "wf87",
    "trade-grade", "trade_grade",
    "deployment-readiness", "deployment_readiness",
    "capital-deployment", "capital_deployment",
    "position-sizing", "position_sizing",
    "approval-card", "approval_card",
    "repair-conveyor", "repair_conveyor",
    "paper-position", "paper_position",
    "paper-state", "paper_state",
    "paper-autotrader", "paper_autotrader",
    "portfolio-config", "portfolio_config",
)


def retired_finance_route_text(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in RETIRED_FINANCE_ROUTE_MARKERS)


def active_action_is_retired(action: dict[str, Any]) -> bool:
    identity = " ".join(str(action.get(key) or "") for key in (
        "id", "opportunity_id", "title", "category", "reason", "source", "path"
    ))
    commands = " ".join(str(item) for item in as_list(action.get("commands")))
    return retired_finance_route_text(f"{identity} {commands}")


def alerts_os_proof_health() -> dict[str, Any]:
    sources = {
        "sql_guard": FINANCE_SQL_GUARD,
        "quote_snapshot": ALERT_QUOTE_PROOF,
        "freshness_controller": ALERT_FRESHNESS_CONTROLLER,
        "recommendations_digest": ALERT_RECOMMENDATIONS_DIGEST,
        "pivot_validator": ALERTS_OS_PIVOT_VALIDATOR,
    }
    proofs: dict[str, dict[str, Any]] = {}
    blocked: list[str] = []
    for name, path in sources.items():
        payload = load_json(path)
        validation_status = as_dict(payload.get("validation")).get("status")
        ok = bool(payload) and payload.get("status") == "ok" and validation_status in {None, "ok"}
        if not ok:
            blocked.append(name)
        proofs[name] = {
            **artifact_view(path),
            "ticker_count": as_dict(payload.get("summary")).get("ticker_count"),
        }
    return {
        "status": "ok" if not blocked else "blocked",
        "blocked_proofs": blocked,
        "proofs": proofs,
    }


def classify_alerts_os(health: dict[str, Any]) -> list[dict[str, Any]]:
    blocked = [str(item) for item in as_list(health.get("blocked_proofs"))]
    if not blocked:
        return [{
            "id": "alerts_os_green",
            "classification": "no_reply",
            "severity": "info",
            "reason": "Guarded SQL, quote evidence, alert freshness, recommendations digest, and pivot boundary are clean.",
            "commands": [],
            "owner_gate_required": False,
        }]
    repairable = [item for item in blocked if item != "pivot_validator"]
    actions: list[dict[str, Any]] = []
    if repairable:
        actions.append({
            "id": "alerts_os_proof_refresh",
            "classification": "auto_refresh",
            "severity": "medium",
            "reason": f"Alerts OS proof refresh required: {', '.join(repairable)}",
            "commands": ["alerts_recommendations_midday_chain", "alerts_os_pivot_validator"],
            "owner_gate_required": False,
        })
    if "pivot_validator" in blocked:
        actions.append({
            "id": "alerts_os_boundary_blocked",
            "classification": "main_handoff",
            "severity": "high",
            "reason": "Alerts OS pivot boundary validator is not clean; inspect its exact active-surface findings.",
            "commands": [],
            "owner_gate_required": False,
        })
    return actions


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
    if allow_execute:
        return False
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
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": ok,
            "stdout_captured": bool(proc.stdout.strip()),
            "stderr_captured": bool(proc.stderr.strip()),
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
            "stdout_captured": bool(exc.stdout),
            "stderr_captured": bool(exc.stderr),
        }


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
            "classification": "main_handoff",
            "severity": "medium",
            "reason": "PM cockpit required source health is not clean; inspect the named current owner proof.",
            "commands": [],
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
    top_action_retired = active_action_is_retired(top_next_action) if top_next_action else False
    handoff_retired = retired_finance_route_text(json.dumps(handoff, sort_keys=True))
    if handoff.get("signal_class") == "MAIN_SESSION_REQUIRED" and not top_action_retired and not handoff_retired:
        actions.append({
            "id": "pm_main_session_handoff_ready",
            "classification": "main_handoff",
            "severity": "medium",
            "reason": f"PM selected {handoff.get('selected_action')} for main-session review",
            "commands": [],
            "owner_gate_required": False,
            "selected_job": as_list(loop_summary.get("selected_jobs"))[:1],
        })
    elif handoff.get("status") == "recently_dispatched" and top_next_action and not top_action_retired:
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
    workflow_advancement: dict[str, Any],
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
        if category == "finance_mutation" or active_action_is_retired(row):
            continue
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
            skip_reason = slot_bound_skip(command_id)
            if skip_reason is not None:
                results.append({
                    "name": command_id,
                    "command": parts,
                    "started_at_utc": utc_now(),
                    "completed_at_utc": utc_now(),
                    "returncode": None,
                    "ok": True,
                    "skipped": True,
                    "skip_reason": skip_reason,
                    "slot_window_phoenix_hours": list(SLOT_BOUND_COMMANDS[command_id]),
                })
                continue
            results.append(run_command(command_id, parts, timeout))
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
    wf74_queue = load_json(WF74_OPPORTUNITY_QUEUE)
    wf74_proposals = load_json(WF74_PROPOSAL_AUTOPILOT)
    wf74_auto_patch = load_json(WF74_AUTO_PATCH_PROPOSER)
    workflow_advancement = load_json(WORKFLOW_ADVANCEMENT)
    alerts_health = alerts_os_proof_health()

    actions = (
        classify_cron(cron_control, escalation)
        + classify_pm(pm_control, {})
        + classify_alerts_os(alerts_health)
        + classify_wf74_auto_handling(
            wf74_queue,
            wf74_proposals,
            wf74_auto_patch,
            workflow_advancement,
            cron_control=cron_control,
        )
        + classify_sidecars(pm_control)
        + contract_lint()
    )
    actions = [action for action in actions if not active_action_is_retired(action)]
    execution_results = execute_safe_actions(actions, args)
    pre_execution_actions = actions
    if execution_results and all(result.get("ok") for result in execution_results):
        cron_control = load_json(CRON_CONTROL)
        escalation = load_json(ESCALATION)
        pm_control = load_json(PM_CONTROL)
        wf74_queue = load_json(WF74_OPPORTUNITY_QUEUE)
        wf74_proposals = load_json(WF74_PROPOSAL_AUTOPILOT)
        wf74_auto_patch = load_json(WF74_AUTO_PATCH_PROPOSER)
        workflow_advancement = load_json(WORKFLOW_ADVANCEMENT)
        alerts_health = alerts_os_proof_health()
        actions = (
            classify_cron(cron_control, escalation)
            + classify_pm(pm_control, {})
            + classify_alerts_os(alerts_health)
            + classify_wf74_auto_handling(
                wf74_queue,
                wf74_proposals,
                wf74_auto_patch,
                workflow_advancement,
                cron_control=cron_control,
            )
            + classify_sidecars(pm_control)
            + contract_lint()
        )
        actions = [action for action in actions if not active_action_is_retired(action)]

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
    pm_handoff = as_dict(as_dict(pm_control.get("summary")).get("main_session_handoff"))
    if retired_finance_route_text(json.dumps(pm_handoff, sort_keys=True)):
        pm_handoff = {}

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
            "control_closeout": artifact_view(CONTROL_CLOSEOUT),
            "wf74_opportunity_queue": artifact_view(WF74_OPPORTUNITY_QUEUE),
            "wf74_proposal_autopilot": artifact_view(WF74_PROPOSAL_AUTOPILOT),
            "wf74_auto_patch_proposer": artifact_view(WF74_AUTO_PATCH_PROPOSER),
            "workflow_advancement_scorecard": artifact_view(WORKFLOW_ADVANCEMENT),
            "workflow_blocker_followups": artifact_view(WORKFLOW_BLOCKER_FOLLOWUPS),
            "finance_sql_guard": artifact_view(FINANCE_SQL_GUARD),
            "alert_quote_snapshot": artifact_view(ALERT_QUOTE_PROOF),
            "alert_freshness_controller": artifact_view(ALERT_FRESHNESS_CONTROLLER),
            "alert_recommendations_digest": artifact_view(ALERT_RECOMMENDATIONS_DIGEST),
            "alerts_os_pivot_validator": artifact_view(ALERTS_OS_PIVOT_VALIDATOR),
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
            "pm_main_session_handoff": pm_handoff,
            "finance_alerts_os": alerts_health,
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
            "The retired --execute-pm-proof compatibility flag always fails closed.",
            "No cron schedule/state edit, runtime/config/auth mutation, external delivery, finance-state mutation, SQL/ticker import, capital/execution/account action, money movement, or owner approval inference.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Review-only main-session greenkeeper controller.")
    parser.add_argument("--write", action="store_true", help="Write the controller artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero only on blocked validation.")
    parser.add_argument("--refresh-frontdoors", action="store_true", help="Run allowlisted front-door proof refresh before classifying.")
    parser.add_argument("--execute-safe", action="store_true", help="Run allowlisted auto_refresh/auto_repair proof commands.")
    parser.add_argument("--execute-pm-proof", action="store_true", help="Retired compatibility flag; always fails closed.")
    parser.add_argument("--append-ledger", action="store_true", help="Append this report summary to the greenkeeper action ledger.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args()

    if args.execute_pm_proof:
        print("--execute-pm-proof is retired; route explicit PM work through its active owner", file=sys.stderr)
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
