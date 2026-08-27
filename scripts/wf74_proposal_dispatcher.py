#!/usr/bin/env python3
"""Dispatch reviewed WF74 proposals into bounded, review-only next lanes.

This is Phase 3 of the WF74 learning loop. It consumes already-reviewed
WF74 routing/proposal packets and emits a dispatch packet. It does not create
PM jobs, create/apply Skill Workshop proposals, apply code, mutate cron,
change finance state, or infer owner approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_DOCKET = TMP / "wf74-decision-docket.json"
DEFAULT_AUTO_PATCH = TMP / "wf74-auto-patch-proposer.json"
DEFAULT_ROUTER = TMP / "wf74-autonomy-work-router.json"
DEFAULT_PM_QUEUE = TMP / "pm-implementation-job-queue.json"
DEFAULT_OWNER_QUEUE = TMP / "owner-gated-action-review-queue.json"
DEFAULT_CRON_CONTROL = TMP / "cron-control-packet.json"
DEFAULT_OUT = TMP / "wf74-proposal-dispatcher.json"
DEFAULT_MD = TMP / "wf74-proposal-dispatcher.md"

SCHEMA = "veritas.wf74_proposal_dispatcher.v1"

DISPATCH_DESTINATIONS = {
    "pm_job",
    "skill_workshop_proposal",
    "owner_gated_packet",
    "validator_ticket",
    "monitor_only",
    "blocked_no_dispatch",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "dispatch_packet_only": True,
    "routes_existing_review_artifacts": True,
    "auto_apply_allowed": False,
    "code_mutation_allowed": False,
    "pm_job_creation_allowed": False,
    "skill_workshop_create_allowed": False,
    "skill_application_allowed": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKED_ACTIONS = [
    "No auto-apply from the dispatcher.",
    "No PM job creation from the dispatcher; emit PM job candidates only.",
    "No Skill Workshop proposal creation or apply/install/quarantine from the dispatcher.",
    "No cron schedule/state/config/runtime mutation.",
    "No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, or account mutation.",
    "No external delivery, raw prompt/response/tool-payload capture, or owner approval inference.",
]

DESTINATION_ORDER = {
    "blocked_no_dispatch": 0,
    "validator_ticket": 1,
    "pm_job": 2,
    "owner_gated_packet": 3,
    "skill_workshop_proposal": 4,
    "monitor_only": 5,
}

SKILL_BY_TEXT = {
    "cron": "cron-automation-manager",
    "skill": "veritas-self-improvement",
    "implementation": "disciplined-implementation",
    "validator": "disciplined-implementation",
    "execution": "automation-hardening-manager",
    "paper": "wf67-paper-trading-operator",
    "finance": "veritas-response-contract",
    "otel": "otel-operations-analyst",
    "telemetry": "privacy-safe-telemetry-expansion",
}

FORBIDDEN_RAW_CAPTURE_TERMS = {
    "raw prompt",
    "raw_prompt",
    "raw response",
    "tool payload",
    "tool_payload",
    "secret",
    "credential",
    "authorization header",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def bool_value(value: Any) -> bool:
    return bool(value)


def source_state(path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(packet.get("validation"))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": packet.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": packet.get("generated_at_utc"),
    }


def choose_skill(*parts: Any) -> str:
    text = " ".join(str(part or "").lower() for part in parts)
    for key, skill in SKILL_BY_TEXT.items():
        if key in text:
            return skill
    return "veritas-self-improvement"


def cron_state(cron_control: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(cron_control.get("summary"))
    blocked = int_value(summary.get("blocked_count"))
    escalated = int_value(summary.get("escalation_signal_count"))
    wake = bool_value(summary.get("should_wake_main_session"))
    attention = int_value(summary.get("requires_attention_count"))
    classification = "active_repair_required" if blocked or escalated or wake else "green_monitor_only"
    return {
        "schema": "veritas.wf74_dispatcher_cron_state.v1",
        "classification": classification,
        "blocked_count": blocked,
        "escalation_signal_count": escalated,
        "requires_attention_count": attention,
        "should_wake_main_session": wake,
        "proof": rel(DEFAULT_CRON_CONTROL),
    }


def router_candidates(router: dict[str, Any]) -> list[dict[str, Any]]:
    return [as_dict(row) for row in as_list(router.get("pm_job_candidates"))]


def pm_jobs(pm_queue: dict[str, Any]) -> list[dict[str, Any]]:
    return [as_dict(row) for row in as_list(pm_queue.get("jobs"))]


def index_router_candidates(router: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in router_candidates(router):
        for key in (
            row.get("source_key"),
            row.get("job_id"),
            stable_id("title", row.get("title")),
        ):
            if key:
                result[str(key)] = row
    return result


def index_pm_jobs(pm_queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("job_id")): row for row in pm_jobs(pm_queue) if row.get("job_id")}


def find_router_candidate(source_id: Any, title: Any, candidates_by_key: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for key in (source_id, stable_id("title", title)):
        if key and str(key) in candidates_by_key:
            return candidates_by_key[str(key)]
    wanted = norm(title)
    for candidate in candidates_by_key.values():
        if wanted and norm(candidate.get("title")) == wanted:
            return candidate
    return {}


def dispatch_row(
    *,
    source_artifact: Path,
    source_type: str,
    source_id: Any,
    title: Any,
    destination: str,
    reason: str,
    proposed_action: str,
    priority: Any = None,
    category: Any = None,
    action_state: Any = None,
    source_kind: Any = None,
    pm_candidate: dict[str, Any] | None = None,
    pm_queue_job: dict[str, Any] | None = None,
    suggested_skill: str | None = None,
    proof_commands: list[Any] | None = None,
    owner_gate: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if destination not in DISPATCH_DESTINATIONS:
        destination = "blocked_no_dispatch"
        reason = f"unknown_dispatch_destination:{destination}"
    return {
        "schema": "veritas.wf74_dispatch_row.v1",
        "dispatch_id": f"wf74-dispatch-{stable_id(source_type, source_id, title, destination)}",
        "source_artifact": rel(source_artifact),
        "source_type": source_type,
        "source_id": source_id,
        "source_kind": source_kind,
        "title": str(title or source_id or "WF74 dispatch row"),
        "category": category,
        "priority": priority,
        "action_state": action_state,
        "dispatch_destination": destination,
        "dispatch_reason": reason,
        "proposed_action": proposed_action,
        "pm_job_id": as_dict(pm_candidate).get("job_id") or as_dict(pm_queue_job).get("job_id"),
        "pm_queue_status": as_dict(pm_queue_job).get("status"),
        "pm_queue_allowed_execution_mode": as_dict(pm_queue_job).get("allowed_execution_mode"),
        "suggested_skill": suggested_skill,
        "owner_gate": owner_gate,
        "proof_commands": [cmd for cmd in as_list(proof_commands) if cmd],
        "direct_apply_allowed": False,
        "direct_memory_write_allowed": False,
        "direct_skill_write_allowed": False,
        "blocked_actions": BLOCKED_ACTIONS,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "metadata": metadata or {},
    }


def dispatch_docket_row(
    row: dict[str, Any],
    *,
    cron: dict[str, Any],
    candidates_by_key: dict[str, dict[str, Any]],
    pm_jobs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_id = row.get("source_id") or row.get("docket_id")
    title = row.get("title") or source_id
    text = f"{title} {row.get('next_action')} {row.get('recommendation')} {row.get('details')}".lower()
    state = str(row.get("action_state") or "monitor_only")
    source_kind = row.get("source_kind")
    category = row.get("category")
    priority = row.get("priority")
    proof_commands = as_list(row.get("proof_commands"))
    pm_candidate = find_router_candidate(source_id, title, candidates_by_key)
    pm_queue_job = as_dict(pm_jobs_by_id.get(str(pm_candidate.get("job_id")))) if pm_candidate else {}

    if state == "hard_stop" or any(term in text for term in FORBIDDEN_RAW_CAPTURE_TERMS):
        return dispatch_row(
            source_artifact=DEFAULT_DOCKET,
            source_type="decision_docket_row",
            source_id=source_id,
            title=title,
            destination="blocked_no_dispatch",
            reason="hard_stop_or_forbidden_capture_boundary",
            proposed_action="Stop and remove or owner-route the unsafe request before any dispatch.",
            priority=priority,
            category=category,
            action_state=state,
            source_kind=source_kind,
            proof_commands=proof_commands,
            metadata={"classification_reason": row.get("classification_reason")},
        )

    if state == "skill_proposal" or source_kind == "skill_workshop_request":
        return dispatch_row(
            source_artifact=DEFAULT_DOCKET,
            source_type="decision_docket_row",
            source_id=source_id,
            title=title,
            destination="skill_workshop_proposal",
            reason="reviewed_skill_proposal_candidate",
            proposed_action="Draft a Skill Workshop proposal in a separate explicit action; do not apply it here.",
            priority=priority,
            category=category,
            action_state=state,
            source_kind=source_kind,
            suggested_skill=choose_skill(category, title),
            proof_commands=proof_commands or ["openclaw skills check"],
        )

    if state == "owner_decision":
        return dispatch_row(
            source_artifact=DEFAULT_DOCKET,
            source_type="decision_docket_row",
            source_id=source_id,
            title=title,
            destination="owner_gated_packet",
            reason="decision_docket_owner_decision",
            proposed_action="Prepare or refresh the owner-gated packet; wait for explicit owner decision.",
            priority=priority,
            category=category,
            action_state=state,
            source_kind=source_kind,
            owner_gate=row.get("proposal_gate") or "owner_decision",
            proof_commands=proof_commands,
        )

    if state == "proof_refresh":
        return dispatch_row(
            source_artifact=DEFAULT_DOCKET,
            source_type="decision_docket_row",
            source_id=source_id,
            title=title,
            destination="validator_ticket",
            reason="proof_refresh_or_eval_gap",
            proposed_action="Refresh the listed proof commands and close only when the source packet is current.",
            priority=priority,
            category=category,
            action_state=state,
            source_kind=source_kind,
            proof_commands=proof_commands,
        )

    if state == "fix_now":
        if category == "cron_migration" and cron.get("classification") == "green_monitor_only":
            return dispatch_row(
                source_artifact=DEFAULT_DOCKET,
                source_type="decision_docket_row",
                source_id=source_id,
                title=title,
                destination="monitor_only",
                reason="cron_fix_now_resolved_by_current_control_packet",
                proposed_action="Keep cron residue visible; do not dispatch repair work unless blocked/escalated/wake signals recur.",
                priority=priority,
                category=category,
                action_state=state,
                source_kind=source_kind,
                proof_commands=["python scripts\\cron_control_packet.py --write --validate"],
                metadata={"current_cron_state": cron},
            )
        if pm_candidate:
            if pm_queue_job.get("status") == "completed_by_ledger":
                return dispatch_row(
                    source_artifact=DEFAULT_DOCKET,
                    source_type="decision_docket_row",
                    source_id=source_id,
                    title=title,
                    destination="validator_ticket",
                    reason="fresh_router_candidate_suppressed_by_pm_completion_ledger",
                    proposed_action="Review PM completion-ledger suppression against current WF74 router proof before treating this as done.",
                    priority=priority,
                    category=category,
                    action_state=state,
                    source_kind=source_kind,
                    pm_candidate=pm_candidate,
                    pm_queue_job=pm_queue_job,
                    proof_commands=[
                        "python scripts\\wf74_autonomy_work_router.py --write --validate",
                        "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
                    ],
                    metadata={"router_status": pm_candidate.get("status")},
                )
            return dispatch_row(
                source_artifact=DEFAULT_DOCKET,
                source_type="decision_docket_row",
                source_id=source_id,
                title=title,
                destination="pm_job",
                reason="current_router_pm_candidate_available",
                proposed_action="Route to the PM job candidate; execution remains separate and bounded by the lane contract.",
                priority=priority,
                category=category,
                action_state=state,
                source_kind=source_kind,
                pm_candidate=pm_candidate,
                pm_queue_job=pm_queue_job,
                proof_commands=as_list(pm_candidate.get("proof_commands")) or proof_commands,
            )
        return dispatch_row(
            source_artifact=DEFAULT_DOCKET,
            source_type="decision_docket_row",
            source_id=source_id,
            title=title,
            destination="validator_ticket",
            reason="fix_now_without_current_pm_route",
            proposed_action="Repair or refresh WF74 routing before opening implementation work.",
            priority=priority,
            category=category,
            action_state=state,
            source_kind=source_kind,
            proof_commands=[
                "python scripts\\wf74_decision_docket.py --write --write-md --validate",
                "python scripts\\wf74_autonomy_work_router.py --write --validate",
            ],
        )

    return dispatch_row(
        source_artifact=DEFAULT_DOCKET,
        source_type="decision_docket_row",
        source_id=source_id,
        title=title,
        destination="monitor_only",
        reason=f"review_state_{state}_is_not_immediate_dispatch",
        proposed_action=str(row.get("next_action") or "Monitor and refresh only when the source condition changes."),
        priority=priority,
        category=category,
        action_state=state,
        source_kind=source_kind,
        proof_commands=proof_commands,
    )


def dispatch_router_candidate(row: dict[str, Any], pm_jobs_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pm_job = as_dict(pm_jobs_by_id.get(str(row.get("job_id"))))
    if pm_job.get("status") == "completed_by_ledger":
        return dispatch_row(
            source_artifact=DEFAULT_ROUTER,
            source_type="router_pm_job_candidate",
            source_id=row.get("job_id") or row.get("source_key"),
            title=row.get("title"),
            destination="validator_ticket",
            reason="router_candidate_suppressed_by_pm_completion_ledger",
            proposed_action="Review whether the completion ledger is stale against the fresh WF74 router candidate.",
            priority=row.get("priority"),
            category=row.get("source_category"),
            pm_candidate=row,
            pm_queue_job=pm_job,
            proof_commands=[
                "python scripts\\wf74_autonomy_work_router.py --write --validate",
                "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
            ],
        )
    return dispatch_row(
        source_artifact=DEFAULT_ROUTER,
        source_type="router_pm_job_candidate",
        source_id=row.get("job_id") or row.get("source_key"),
        title=row.get("title"),
        destination="pm_job",
        reason="router_candidate_ready_for_pm_lane_review",
        proposed_action="Keep as PM job candidate; run only through PM/lane authority proof.",
        priority=row.get("priority"),
        category=row.get("source_category"),
        pm_candidate=row,
        pm_queue_job=pm_job,
        proof_commands=as_list(row.get("proof_commands")),
    )


def dispatch_owner_item(row: dict[str, Any]) -> dict[str, Any]:
    decision_required = row.get("decision_required")
    if decision_required is None:
        decision_required = row.get("owner_decision_required")
    if decision_required is None:
        decision_state = str(row.get("decision_state") or "")
        required_decision = str(row.get("required_owner_decision") or "")
        decision_required = decision_state not in {"", "monitor_only"} and required_decision != "none_now"
    gate = row.get("gate") or row.get("category")
    destination = "owner_gated_packet" if decision_required is not False else "monitor_only"
    return dispatch_row(
        source_artifact=DEFAULT_OWNER_QUEUE,
        source_type="owner_gated_action_item",
        source_id=row.get("item_id") or row.get("id") or stable_id("owner", gate, row.get("title")),
        title=row.get("title") or row.get("plain_status") or gate,
        destination=destination,
        reason="owner_decision_required" if destination == "owner_gated_packet" else "owner_gate_monitor_only",
        proposed_action=str(row.get("required_owner_decision") or row.get("next_safe_action") or "Keep owner gate visible; do not apply."),
        priority=row.get("priority"),
        category=row.get("category"),
        owner_gate=gate,
        proof_commands=as_list(row.get("proof_commands")),
        metadata={"plain_status": row.get("plain_status")},
    )


def dispatch_auto_patch_sidecars(auto_patch: dict[str, Any], existing_keys: set[tuple[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_type, source_key, destination in (
        ("auto_patch_plan", "patch_plans", "pm_job"),
        ("auto_patch_skill_request", "skill_workshop_requests", "skill_workshop_proposal"),
        ("auto_patch_owner_review", "owner_gated_reviews", "owner_gated_packet"),
    ):
        for row in as_list(auto_patch.get(source_key)):
            item = as_dict(row)
            source_id = str(item.get("plan_id") or item.get("review_id") or stable_id(source_type, item.get("title")))
            dedupe_key = (source_type, source_id)
            if dedupe_key in existing_keys:
                continue
            pm_candidate: dict[str, Any] = {}
            if destination == "pm_job" and item.get("requires_owner_approval"):
                dest = "owner_gated_packet"
                reason = "auto_patch_plan_requires_owner_approval"
                proposed = "Prepare an owner-gated implementation packet before any code lane."
            elif destination == "pm_job" and not (item.get("pm_job_id") or item.get("job_id")):
                dest = "validator_ticket"
                reason = "auto_patch_plan_requires_pm_job_candidate"
                proposed = (
                    "Open a scoped PM implementation job through the queue/router before dispatch; "
                    "do not apply from the proposer artifact."
                )
            else:
                dest = destination
                reason = f"{source_type}_dispatch"
                proposed = str(item.get("next_safe_action") or item.get("required_owner_action") or "Review separately; do not apply from dispatcher.")
                if destination == "pm_job":
                    pm_candidate = {"job_id": item.get("pm_job_id") or item.get("job_id")}
            rows.append(dispatch_row(
                source_artifact=DEFAULT_AUTO_PATCH,
                source_type=source_type,
                source_id=source_id,
                title=item.get("title"),
                destination=dest,
                reason=reason,
                proposed_action=proposed,
                priority=item.get("priority"),
                category=item.get("category"),
                suggested_skill=choose_skill(item.get("category"), item.get("title")) if dest == "skill_workshop_proposal" else None,
                owner_gate=item.get("route") if dest == "owner_gated_packet" else None,
                pm_candidate=pm_candidate,
                proof_commands=as_list(item.get("validation_commands")),
                metadata={"route": item.get("route"), "risk_class": item.get("risk_class")},
            ))
    return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_id[str(row.get("dispatch_id"))] = row
    return sorted(
        by_id.values(),
        key=lambda row: (
            DESTINATION_ORDER.get(str(row.get("dispatch_destination")), 9),
            -int_value(row.get("priority")),
            str(row.get("title") or ""),
        ),
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    docket_path = workspace_path(getattr(args, "docket", None), DEFAULT_DOCKET)
    auto_patch_path = workspace_path(getattr(args, "auto_patch", None), DEFAULT_AUTO_PATCH)
    router_path = workspace_path(getattr(args, "router", None), DEFAULT_ROUTER)
    pm_queue_path = workspace_path(getattr(args, "pm_queue", None), DEFAULT_PM_QUEUE)
    owner_queue_path = workspace_path(getattr(args, "owner_queue", None), DEFAULT_OWNER_QUEUE)
    cron_control_path = workspace_path(getattr(args, "cron_control", None), DEFAULT_CRON_CONTROL)

    docket = load(docket_path)
    auto_patch = load(auto_patch_path)
    router = load(router_path)
    pm_queue = load(pm_queue_path)
    owner_queue = load(owner_queue_path)
    cron_control = load(cron_control_path)

    cron = cron_state(cron_control)
    candidates_by_key = index_router_candidates(router)
    pm_jobs_by_id = index_pm_jobs(pm_queue)

    rows: list[dict[str, Any]] = []
    for item in as_list(docket.get("rows")):
        if isinstance(item, dict):
            rows.append(dispatch_docket_row(
                as_dict(item),
                cron=cron,
                candidates_by_key=candidates_by_key,
                pm_jobs_by_id=pm_jobs_by_id,
            ))

    docket_source_ids = {
        (str(row.get("source_kind") or row.get("source_type")), str(row.get("source_id")))
        for row in rows
        if row.get("source_id")
    }
    rows.extend(dispatch_auto_patch_sidecars(auto_patch, docket_source_ids))

    docket_ids = {str(row.get("source_id")) for row in rows if row.get("source_id")}
    for candidate in router_candidates(router):
        key = str(candidate.get("job_id") or candidate.get("source_key") or "")
        source_key = str(candidate.get("source_key") or "")
        if key not in docket_ids and source_key not in docket_ids:
            rows.append(dispatch_router_candidate(candidate, pm_jobs_by_id))

    owner_items = as_list(owner_queue.get("items")) or as_list(owner_queue.get("review_items"))
    for item in owner_items:
        if isinstance(item, dict):
            rows.append(dispatch_owner_item(as_dict(item)))

    rows = dedupe_rows(rows)
    counts: dict[str, int] = {destination: 0 for destination in sorted(DISPATCH_DESTINATIONS)}
    for row in rows:
        destination = str(row.get("dispatch_destination") or "blocked_no_dispatch")
        counts[destination] = counts.get(destination, 0) + 1

    summary = {
        "dispatch_row_count": len(rows),
        "by_destination": counts,
        "pm_job_dispatch_count": counts.get("pm_job", 0),
        "skill_workshop_proposal_count": counts.get("skill_workshop_proposal", 0),
        "owner_gated_packet_count": counts.get("owner_gated_packet", 0),
        "validator_ticket_count": counts.get("validator_ticket", 0),
        "monitor_only_count": counts.get("monitor_only", 0),
        "blocked_no_dispatch_count": counts.get("blocked_no_dispatch", 0),
        "pm_ledger_suppression_ticket_count": sum(
            1 for row in rows if "suppressed_by_pm_completion_ledger" in str(row.get("dispatch_reason") or "")
        ),
        "auto_apply_count": int_value(as_dict(auto_patch.get("summary")).get("auto_apply_count")),
        "auto_patch_auto_apply_candidate_count": int_value(as_dict(auto_patch.get("summary")).get("auto_apply_candidate_count")),
        "cron_signal_classification": cron.get("classification"),
        "next_safe_action": "Review validator tickets first, then PM job candidates; apply nothing from this packet.",
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Route reviewed WF74 proposals into exactly one review-only next lane each.",
        "inputs": {
            "docket": source_state(docket_path, docket),
            "auto_patch": source_state(auto_patch_path, auto_patch),
            "router": source_state(router_path, router),
            "pm_queue": source_state(pm_queue_path, pm_queue),
            "owner_queue": source_state(owner_queue_path, owner_queue),
            "cron_control": source_state(cron_control_path, cron_control),
        },
        "current_cron_state": cron,
        "summary": summary,
        "dispatch_destinations": sorted(DISPATCH_DESTINATIONS),
        "dispatch_rows": rows,
        "blocked_actions": BLOCKED_ACTIONS,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "blocked":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    summary = as_dict(payload.get("summary"))
    if int_value(summary.get("auto_apply_count")):
        errors.append("auto_patch_auto_apply_count_must_be_zero")
    if int_value(summary.get("auto_patch_auto_apply_candidate_count")):
        errors.append("auto_patch_auto_apply_candidate_count_must_be_zero")
    for source_name, source in as_dict(payload.get("inputs")).items():
        validation_status = as_dict(source).get("validation_status")
        status = as_dict(source).get("status")
        if as_dict(source).get("exists") is False:
            errors.append(f"missing_input:{source_name}")
        if validation_status == "blocked" or status == "blocked":
            errors.append(f"blocked_input:{source_name}")
        elif validation_status == "warning" or status == "warning":
            warnings.append(f"warning_input:{source_name}")
    if not as_list(payload.get("dispatch_rows")):
        errors.append("missing_dispatch_rows")
    for row in as_list(payload.get("dispatch_rows")):
        item = as_dict(row)
        destination = str(item.get("dispatch_destination") or "")
        if destination not in DISPATCH_DESTINATIONS:
            errors.append(f"unknown_destination:{item.get('dispatch_id')}:{destination}")
        if item.get("direct_apply_allowed"):
            errors.append(f"direct_apply_allowed:{item.get('dispatch_id')}")
        if item.get("direct_memory_write_allowed"):
            errors.append(f"direct_memory_write_allowed:{item.get('dispatch_id')}")
        if item.get("direct_skill_write_allowed"):
            errors.append(f"direct_skill_write_allowed:{item.get('dispatch_id')}")
        if destination == "pm_job" and not item.get("pm_job_id"):
            errors.append(f"pm_dispatch_missing_job_id:{item.get('dispatch_id')}")
        if destination == "skill_workshop_proposal" and not item.get("suggested_skill"):
            errors.append(f"skill_dispatch_missing_skill:{item.get('dispatch_id')}")
        if destination == "owner_gated_packet" and not item.get("owner_gate"):
            warnings.append(f"owner_dispatch_missing_specific_gate:{item.get('dispatch_id')}")
    return {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Proposal Dispatcher",
        "",
        "Status: review only",
        "",
        "## Summary",
        "",
        f"- Validation: `{as_dict(payload.get('validation')).get('status')}`",
        f"- Rows: `{summary.get('dispatch_row_count')}`",
        f"- PM jobs: `{summary.get('pm_job_dispatch_count')}`",
        f"- Skill Workshop proposals: `{summary.get('skill_workshop_proposal_count')}`",
        f"- Owner-gated packets: `{summary.get('owner_gated_packet_count')}`",
        f"- Validator tickets: `{summary.get('validator_ticket_count')}`",
        f"- Monitor-only: `{summary.get('monitor_only_count')}`",
        f"- Blocked/no dispatch: `{summary.get('blocked_no_dispatch_count')}`",
        f"- PM ledger suppression tickets: `{summary.get('pm_ledger_suppression_ticket_count')}`",
        f"- Auto-apply count: `{summary.get('auto_apply_count')}`",
        "",
        "## Top Rows",
        "",
    ]
    for row in as_list(payload.get("dispatch_rows"))[:12]:
        item = as_dict(row)
        lines.append(
            f"- `{item.get('dispatch_destination')}` {item.get('title')} "
            f"({item.get('dispatch_reason')})"
        )
        lines.append(f"  - {item.get('proposed_action')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- This packet does not apply code, create PM jobs, create/apply Skill Workshop proposals, mutate cron/config/runtime, mutate finance canon/portfolio, or infer owner approval.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docket", default=str(DEFAULT_DOCKET))
    parser.add_argument("--auto-patch", dest="auto_patch", default=str(DEFAULT_AUTO_PATCH))
    parser.add_argument("--router", default=str(DEFAULT_ROUTER))
    parser.add_argument("--pm-queue", dest="pm_queue", default=str(DEFAULT_PM_QUEUE))
    parser.add_argument("--owner-queue", dest="owner_queue", default=str(DEFAULT_OWNER_QUEUE))
    parser.add_argument("--cron-control", dest="cron_control", default=str(DEFAULT_CRON_CONTROL))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--md-out", dest="md_out", default=str(DEFAULT_MD))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    out = workspace_path(args.out, DEFAULT_OUT)
    md_out = workspace_path(args.md_out, DEFAULT_MD)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = as_dict(payload.get("summary"))
        print(
            "status={status} validation={validation} rows={rows} pm={pm} skill={skill} owner={owner} validators={validators} monitor={monitor} blocked={blocked} auto_apply={auto_apply}".format(
                status=payload.get("status"),
                validation=as_dict(payload.get("validation")).get("status"),
                rows=summary.get("dispatch_row_count"),
                pm=summary.get("pm_job_dispatch_count"),
                skill=summary.get("skill_workshop_proposal_count"),
                owner=summary.get("owner_gated_packet_count"),
                validators=summary.get("validator_ticket_count"),
                monitor=summary.get("monitor_only_count"),
                blocked=summary.get("blocked_no_dispatch_count"),
                auto_apply=summary.get("auto_apply_count"),
            )
        )
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
