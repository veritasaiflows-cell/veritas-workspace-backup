#!/usr/bin/env python3
"""Build the PM main-session continuation handoff.

This is the missing bridge between heartbeat-visible PM state and main-session
execution. It writes an exact review-only work packet for Veritas/main to pick
up. It does not execute workflow phases, spawn helpers, mutate cron, touch
canon/portfolio state, move/delete/archive files, use customer data, deliver
externally, or take paper/live/account action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_PM_ACTIONS = TMP / "pm-next-actions.json"
DEFAULT_PM_STATE = TMP / "pm-program-state.json"
DEFAULT_HEARTBEAT = TMP / "heartbeat-continuation-candidates.json"
DEFAULT_IMPLEMENTATION_QUEUE = TMP / "pm-implementation-job-queue.json"
DEFAULT_OUT = TMP / "pm-main-session-handoff.json"
DEFAULT_LEDGER = TMP / "pm-dispatch-ledger.json"
DEFAULT_DISPATCH_COOLDOWN_HOURS = 6.0

SCHEMA = "veritas.pm_main_session_handoff.v1"
LEDGER_SCHEMA = "veritas.pm_dispatch_ledger.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "heartbeat_executes_action": False,
    "main_session_may_continue_bounded_action": True,
    "helper_lane_may_be_started_by_main_session": True,
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKED_ACTION_TYPES = {
    "mutate_canon",
    "mutate_portfolio",
    "archive",
    "delete",
    "move",
    "sql_import",
    "ticker_import",
    "external_delivery",
    "paper_execution",
    "live_execution",
    "account_action",
    "config_runtime_change",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def read_ledger(path: Path) -> dict[str, Any]:
    ledger = load_json(path)
    if ledger.get("schema") == LEDGER_SCHEMA and isinstance(ledger.get("entries"), list):
        return ledger
    return {
        "schema": LEDGER_SCHEMA,
        "status": "ok",
        "entries": [],
    }


def action_is_safe(action: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not action:
        errors.append("missing_selected_action")
        return False, errors
    if action.get("authority") != "review_only":
        errors.append("selected_action_authority_not_review_only")
    if action.get("inline_execution_allowed") is not False:
        errors.append("selected_action_inline_execution_allowed")
    if action.get("heartbeat_may_execute") is not False:
        errors.append("selected_action_heartbeat_execution_allowed")
    if action.get("helper_lane_allowed_from_main_session") is not True:
        errors.append("selected_action_main_helper_not_allowed")
    if action.get("action_type") in BLOCKED_ACTION_TYPES:
        errors.append(f"selected_action_type_blocked:{action.get('action_type')}")
    stop_text = " ".join(str(item).lower() for item in as_list(action.get("stop_lines")))
    for token in ("owner approval required", "customer data", "external delivery", "paper/live", "account action"):
        if token in stop_text and "no " not in stop_text:
            errors.append(f"ambiguous_stop_line:{token}")
    return not errors, errors


def select_action(actions_payload: dict[str, Any], implementation_queue: dict[str, Any] | None = None) -> dict[str, Any]:
    actions = [item for item in as_list(actions_payload.get("next_actions")) if isinstance(item, dict)]
    queue = implementation_queue if isinstance(implementation_queue, dict) else {}
    jobs = [job for job in as_list(queue.get("jobs")) if isinstance(job, dict)]
    if jobs:
        ready_source_ids = {
            str(job.get("source_action_id"))
            for job in jobs
            if job.get("status") in {"ready_for_main_or_helper", "ready_for_review"}
            and job.get("source_action_id")
        }
        for action in sorted(actions, key=lambda item: int(item.get("rank") or 9999)):
            if str(action.get("action_id") or "") not in ready_source_ids:
                continue
            safe, _ = action_is_safe(action)
            if safe:
                return action
        jobs_by_source: dict[str, list[dict[str, Any]]] = {}
        for job in jobs:
            source_action_id = str(job.get("source_action_id") or "")
            if source_action_id:
                jobs_by_source.setdefault(source_action_id, []).append(job)
        for action in sorted(actions, key=lambda item: int(item.get("rank") or 9999)):
            safe, _ = action_is_safe(action)
            if not safe:
                continue
            matching_jobs = jobs_by_source.get(str(action.get("action_id") or ""), [])
            if matching_jobs and all(job.get("status") == "completed_by_ledger" for job in matching_jobs):
                continue
            return action
        return {}
    for action in sorted(actions, key=lambda item: int(item.get("rank") or 9999)):
        safe, _ = action_is_safe(action)
        if safe:
            return action
    return actions[0] if actions else {}


def recent_ready_dispatch(
    ledger: dict[str, Any],
    action_id: str | None,
    now: datetime,
    cooldown_hours: float,
) -> dict[str, Any]:
    if not action_id or cooldown_hours <= 0:
        return {"recent": False}
    for entry in reversed(as_list(ledger.get("entries"))):
        if not isinstance(entry, dict):
            continue
        if entry.get("action_id") != action_id:
            continue
        if entry.get("status") != "ready_for_main_session":
            continue
        if as_dict(entry).get("validation_status") not in {"ok", None}:
            continue
        generated_at = parse_utc(entry.get("generated_at_utc"))
        if not generated_at:
            continue
        age_hours = round(max(0.0, (now - generated_at).total_seconds() / 3600), 2)
        if age_hours <= cooldown_hours:
            return {
                "recent": True,
                "action_id": action_id,
                "last_dispatched_at_utc": entry.get("generated_at_utc"),
                "age_hours": age_hours,
                "cooldown_hours": cooldown_hours,
            }
        return {
            "recent": False,
            "action_id": action_id,
            "last_dispatched_at_utc": entry.get("generated_at_utc"),
            "age_hours": age_hours,
            "cooldown_hours": cooldown_hours,
        }
    return {"recent": False, "action_id": action_id, "cooldown_hours": cooldown_hours}


def command_contract(action: dict[str, Any]) -> list[str]:
    lane = action.get("lane_id")
    if lane == "finance_engine":
        return [
            "Run only the existing review-only finance freshness/current-window validators needed to clear stale proof.",
            "Do not mutate canonical notes, portfolio state, sizing, cash, risk rules, or execution entitlement.",
            "Regenerate PM state after validation.",
        ]
    if lane == "pm_handoff_pdf":
        return [
            "Regenerate PM weekly update, artifact-only handoff, and readiness brief from current WF75 proof.",
            "Do not deliver externally or imply launch/customer readiness.",
            "Regenerate PM state after validation.",
        ]
    if lane == "qa_source_trust":
        return [
            "Run targeted validators and classify warning/failure state before further readiness claims.",
            "Do not widen authority from a clean validator result.",
            "Regenerate PM state after validation.",
        ]
    if lane == "wf75_service_state":
        return [
            "Run the next anonymous WF75 service lifecycle slice only if the main session confirms the slice.",
            "Do not use customer data, external delivery, public launch, account, brokerage, or execution surfaces.",
            "Run WF75 closeout refresh after the slice.",
        ]
    if lane == "trade_grade_decision_os":
        return [
            "Refresh WF84/WF78 inputs only through existing review-only validators and proof surfaces.",
            "Run WF85 decision cards and repair conveyor; use outputs to prioritize source/freshness and band/stop repair before any approval-card draft lane.",
            "Do not infer capital approval, paper/live execution, account action, or portfolio/canon mutation from any generated card, score, SQL row, or validation result.",
            "Regenerate PM state after validation.",
        ]
    if lane == "smb_workflow_clarity":
        return [
            "SMB Workflow Clarity / Marketing Ops Automation is resumed as a P1 monetization lane; verify `scripts/workflow_router.py WF79-SMB --answer all` before opening helper work.",
            "Advance only internal proof: offer/ICP, sanitized demo packets, automation blueprints, cockpit panels, training/sales practice, and validator lint.",
            "Refresh `generic_intelligence_saas_pivot.py`, then run WF75 closeout so PM state, heartbeat handoff, operator packets, and harness routes stay aligned.",
            "Do not use real customer data, outreach, posting, ads, ad-account/customer-system access, credentials, external delivery, spend, or guaranteed ROI/revenue claims without a separate explicit approval gate.",
        ]
    return [
        "Inspect the selected PM next action.",
        "Execute only a bounded review-only validator/report/proof refresh if no stop line is crossed.",
        "Regenerate PM state after validation.",
    ]


def selected_implementation_job(queue: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    jobs = [job for job in as_list(queue.get("jobs")) if isinstance(job, dict)]
    action_id = action.get("action_id")
    for job in jobs:
        if job.get("source_action_id") == action_id and job.get("status") != "completed_by_ledger":
            return job
    for job in jobs:
        if job.get("status") in {"ready_for_main_or_helper", "ready_for_review"}:
            return job
    return jobs[0] if jobs else {}


def signal_classification(status: str, action: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    if status == "ready_for_main_session":
        queue_class = "MAIN_SESSION_REQUIRED"
        reason = "selected_action_is_safe_review_only_and_ready"
    elif status == "recently_dispatched":
        queue_class = "NO_REPLY"
        reason = "selected_action_recently_dispatched"
    elif status == "blocked" or errors:
        queue_class = "BLOCKED"
        reason = "selected_action_failed_safety_or_validation"
    elif status == "no_action":
        queue_class = "NO_REPLY"
        reason = "no_safe_pm_next_action_available"
    else:
        queue_class = "STALE_OR_NOISE"
        reason = "handoff_state_not_actionable"
    return {
        "class": queue_class,
        "reason": reason,
        "heartbeat_may_execute": False,
        "inline_execution_allowed": False,
        "main_session_may_continue": queue_class == "MAIN_SESSION_REQUIRED",
        "owner_decision_required": action.get("action_type") in BLOCKED_ACTION_TYPES,
    }


def helper_lane_contract(action: dict[str, Any]) -> dict[str, Any]:
    lane = str(action.get("lane_id") or "general_review")
    base = {
        "primary_lane": lane,
        "helper_allowed_from_main_session": bool(action.get("helper_lane_allowed_from_main_session") is True),
        "helper_allowed_from_heartbeat": False,
        "main_session_final_integrator": True,
        "allowed_merge_mode": "review_only_artifact_or_patch_proposal",
        "required_fields": [
            "staff_lane_or_role",
            "objective",
            "files_to_read_first",
            "allowed_actions",
            "forbidden_actions_or_stop_lines",
            "output_contract",
            "acceptance_proof",
            "timeout_or_partial_output_expectation",
            "merge_expectation",
            "authority_boundary",
        ],
        "closeout_required": [
            "what_was_inspected",
            "what_changed_or_did_not_change",
            "proof_tests_validators",
            "blockers_or_trust_gaps",
            "exact_next_action",
            "safe_to_merge_or_review_only",
        ],
        "global_stop_lines": [
            "no owner approval inference",
            "no config/auth/channel/service/runtime mutation",
            "no archive/move/delete",
            "no customer data or external delivery",
            "no canon/portfolio mutation unless exact gated apply is separately approved",
            "no paper/live/account action",
        ],
    }
    lane_profiles: dict[str, dict[str, Any]] = {
        "smb_workflow_clarity": {
            "staff_lane": "OS Operator / Automation Desk",
            "files_to_read_first": [
                "tmp/generic-service-run-contract.json",
                "tmp/wf75-smb-customer-preview.json",
                "tmp/wf75-smb-customer-preview-validation.json",
                "tmp/wf75-smb-automation-blueprints-validation.json",
                "tmp/wf75-smb-pilot-decision-packet.json",
            ],
            "acceptance_proof": [
                "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
                "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate",
            ],
        },
        "wf75_service_state": {
            "staff_lane": "OS Operator / Automation Desk",
            "files_to_read_first": [
                "tmp/wf75-service-state-current.json",
                "tmp/wf75-service-state.sqlite",
                "tmp/wf75-operator-queue.json",
                "tmp/wf75-artifact-only-pm-handoff.json",
            ],
            "acceptance_proof": [
                "python scripts\\wf75_service_state.py --write --validate",
                "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate",
            ],
        },
        "qa_source_trust": {
            "staff_lane": "Independent QA Desk",
            "files_to_read_first": [
                "tmp/pm-program-state.json",
                "tmp/pm-blocker-register.json",
                "tmp/veritas-harness-scorecard.json",
            ],
            "acceptance_proof": [
                "python scripts\\veritas_harness_scorecard.py --run --write --validate",
            ],
        },
        "finance_engine": {
            "staff_lane": "Finance Evidence / QA Desk",
            "files_to_read_first": [
                "tmp/finance-data-coverage-current.json",
                "tmp/current-window-artifacts.json",
                "tmp/run-summary-morning.json",
                "tmp/run-summary-post-close.json",
            ],
            "acceptance_proof": [
                "python scripts\\artifact_index.py validate",
                "python scripts\\finance_intelligence_state.py paper-positions --pretty",
            ],
        },
        "trade_grade_decision_os": {
            "staff_lane": "Personal Trade-Grade Decision OS Desk",
            "files_to_read_first": [
                "tmp/trade-grade-decision-cards.json",
                "tmp/trade-grade-repair-conveyor.json",
                "tmp/trade-grade-approval-card-gate.json",
                "tmp/canonical-finance-data-plane.json",
                "tmp/canonical-finance-data-plane-phase6-10.json",
                "tmp/wf78-capital-review-queue.json",
            ],
            "acceptance_proof": [
                "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
                "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
                "python scripts\\trade_grade_decision_cards.py --write --validate",
                "python scripts\\trade_grade_repair_conveyor.py --write --validate",
                "python scripts\\pm_control_packet.py --write --write-db --validate",
            ],
        },
    }
    base.update(lane_profiles.get(lane, {
        "staff_lane": "OS Operator / Automation Desk",
        "files_to_read_first": [
            "tmp/pm-control-packet.json",
            "tmp/pm-program-state.json",
            "tmp/pm-next-actions.json",
            "tmp/heartbeat-continuation-candidates.json",
        ],
        "acceptance_proof": [
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ],
    }))
    return base


def build_handoff(
    pm_actions_path: Path = DEFAULT_PM_ACTIONS,
    pm_state_path: Path = DEFAULT_PM_STATE,
    heartbeat_path: Path = DEFAULT_HEARTBEAT,
    implementation_queue_path: Path = DEFAULT_IMPLEMENTATION_QUEUE,
    ledger_path: Path = DEFAULT_LEDGER,
    cooldown_hours: float = DEFAULT_DISPATCH_COOLDOWN_HOURS,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    actions_payload = load_json(pm_actions_path)
    pm_state = load_json(pm_state_path)
    heartbeat = load_json(heartbeat_path)
    implementation_queue = load_json(implementation_queue_path)
    ledger = read_ledger(ledger_path)
    selected = select_action(actions_payload, implementation_queue)
    selected_job = selected_implementation_job(implementation_queue, selected)
    safe, errors = action_is_safe(selected)
    recent_dispatch = recent_ready_dispatch(
        ledger,
        str(selected.get("action_id") or "") if selected else "",
        now,
        cooldown_hours,
    )

    status = "ready_for_main_session" if safe else "blocked"
    if not selected:
        status = "no_action"
        errors = []
    elif safe and recent_dispatch.get("recent"):
        status = "recently_dispatched"
    signal = signal_classification(status, selected, errors)

    if status == "ready_for_main_session":
        dispatch_text = (
            "PM continuation handoff is ready. Main-session Veritas should read "
            "`tmp/pm-main-session-handoff.json`, execute only the selected bounded review-only action, "
            "run its validation/closeout contract, refresh PM state, and stop at any authority gate."
        )
    elif status == "recently_dispatched":
        dispatch_text = (
            "PM continuation handoff is quiet because the selected review-only action was recently "
            "dispatched. Re-evaluate after the cooldown or when PM proof becomes stale/blocked."
        )
    else:
        dispatch_text = "PM continuation handoff is not ready; inspect validation errors before continuing."

    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": status,
        "purpose": "Main-session continuation packet generated from PM program state and heartbeat candidates.",
        "sources": {
            "pm_next_actions": rel(pm_actions_path),
            "pm_program_state": rel(pm_state_path),
            "heartbeat_continuation_candidates": rel(heartbeat_path),
            "pm_implementation_job_queue": rel(implementation_queue_path),
            "pm_dispatch_ledger": rel(ledger_path),
        },
        "selected_action": selected,
        "selected_implementation_job": selected_job,
        "dispatch_cooldown": recent_dispatch,
        "readiness": pm_state.get("readiness"),
        "implementation_queue_summary": implementation_queue.get("summary"),
        "implementation_collision_summary": implementation_queue.get("collision_summary"),
        "heartbeat_summary": {
            "status": heartbeat.get("status"),
            "candidate_count": heartbeat.get("candidate_count"),
            "handoff_ready_count": heartbeat.get("handoff_ready_count"),
            "blocked_count": heartbeat.get("blocked_count"),
        },
        "signal_classification": signal,
        "main_session_contract": {
            "dispatch_text": dispatch_text,
            "consume_with": "Main session reads this JSON before continuing autonomous PM work.",
            "execute_in_order": command_contract(selected),
            "after_execution": [
                "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate when WF75 artifacts changed materially",
                "python scripts\\pm_control_packet.py --write --write-db --validate",
                "python scripts\\workspace_boundary_check.py --write --validate",
            ],
            "response_contract": [
                "selected PM action",
                "work performed",
                "validation result",
                "updated PM readiness",
                "remaining blocker or next action",
                "authority boundary preserved",
            ],
        },
        "helper_lane_contract": helper_lane_contract(selected),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "ok" if safe or status in {"no_action", "recently_dispatched"} else "error",
            "errors": errors,
            "warnings": [] if selected else ["no_pm_next_action_available"],
        },
    }


def build_handoff_from_payloads(
    actions_payload: dict[str, Any],
    pm_state: dict[str, Any],
    heartbeat: dict[str, Any],
    implementation_queue: dict[str, Any],
    ledger_path: Path = DEFAULT_LEDGER,
    cooldown_hours: float = DEFAULT_DISPATCH_COOLDOWN_HOURS,
    source_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ledger = read_ledger(ledger_path)
    selected = select_action(actions_payload, implementation_queue)
    selected_job = selected_implementation_job(implementation_queue, selected)
    safe, errors = action_is_safe(selected)
    recent_dispatch = recent_ready_dispatch(
        ledger,
        str(selected.get("action_id") or "") if selected else "",
        now,
        cooldown_hours,
    )

    status = "ready_for_main_session" if safe else "blocked"
    if not selected:
        status = "no_action"
        errors = []
    elif safe and recent_dispatch.get("recent"):
        status = "recently_dispatched"
    signal = signal_classification(status, selected, errors)

    if status == "ready_for_main_session":
        dispatch_text = (
            "PM continuation handoff is ready. Main-session Veritas should read "
            "`tmp/pm-control-packet.json`, execute only the selected bounded review-only action, "
            "run its validation/closeout contract, refresh PM control, and stop at any authority gate."
        )
    elif status == "recently_dispatched":
        dispatch_text = (
            "PM continuation handoff is quiet because the selected review-only action was recently "
            "dispatched. Re-evaluate after the cooldown or when PM proof becomes stale/blocked."
        )
    else:
        dispatch_text = "PM continuation handoff is not ready; inspect validation errors before continuing."

    sources = source_labels or {
        "pm_next_actions": "tmp/pm-control-packet.json#sections.pm_program_state.next_actions",
        "pm_program_state": "tmp/pm-control-packet.json#sections.pm_program_state",
        "heartbeat_continuation_candidates": "tmp/pm-control-packet.json#sections.heartbeat_continuation_candidates",
        "pm_implementation_job_queue": "tmp/pm-control-packet.json#sections.pm_implementation_job_queue",
        "pm_dispatch_ledger": rel(ledger_path),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": status,
        "purpose": "Main-session continuation packet generated from consolidated PM control packet sections.",
        "sources": sources,
        "selected_action": selected,
        "selected_implementation_job": selected_job,
        "dispatch_cooldown": recent_dispatch,
        "readiness": pm_state.get("readiness"),
        "implementation_queue_summary": implementation_queue.get("summary"),
        "implementation_collision_summary": implementation_queue.get("collision_summary"),
        "heartbeat_summary": {
            "status": heartbeat.get("status"),
            "candidate_count": heartbeat.get("candidate_count"),
            "handoff_ready_count": heartbeat.get("handoff_ready_count"),
            "blocked_count": heartbeat.get("blocked_count"),
        },
        "signal_classification": signal,
        "main_session_contract": {
            "dispatch_text": dispatch_text,
            "consume_with": "Main session reads tmp/pm-control-packet.json before continuing autonomous PM work.",
            "execute_in_order": command_contract(selected),
            "after_execution": [
                "python scripts\\pm_control_packet.py --write --write-db --validate",
                "python scripts\\workspace_boundary_check.py --write --validate when boundary-sensitive artifacts changed",
                "python scripts\\wf75_closeout_refresh.py --validation-budget shared --write --validate when WF75 artifacts changed materially",
            ],
            "response_contract": [
                "selected PM action",
                "work performed",
                "validation result",
                "updated PM readiness",
                "remaining blocker or next action",
                "authority boundary preserved",
            ],
        },
        "helper_lane_contract": helper_lane_contract(selected),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "ok" if safe or status in {"no_action", "recently_dispatched"} else "error",
            "errors": errors,
            "warnings": [] if selected else ["no_pm_next_action_available"],
        },
    }


def update_ledger(path: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    ledger = read_ledger(path)
    entry = {
        "generated_at_utc": handoff.get("generated_at_utc"),
        "status": handoff.get("status"),
        "action_id": as_dict(handoff.get("selected_action")).get("action_id"),
        "lane_id": as_dict(handoff.get("selected_action")).get("lane_id"),
        "authority": as_dict(handoff.get("selected_action")).get("authority"),
        "validation_status": as_dict(handoff.get("validation")).get("status"),
    }
    entries = as_list(ledger.get("entries"))
    entries.append(entry)
    ledger["entries"] = entries[-100:]
    ledger["generated_at_utc"] = handoff.get("generated_at_utc")
    ledger["entry_count"] = len(ledger["entries"])
    ledger["latest"] = entry
    ledger["status"] = "ok"
    return ledger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PM main-session continuation handoff.")
    parser.add_argument("--write", action="store_true", help="Write JSON handoff and dispatch ledger.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero when handoff validation fails.")
    parser.add_argument("--pm-actions", default=str(DEFAULT_PM_ACTIONS))
    parser.add_argument("--pm-state", default=str(DEFAULT_PM_STATE))
    parser.add_argument("--heartbeat", default=str(DEFAULT_HEARTBEAT))
    parser.add_argument("--implementation-queue", default=str(DEFAULT_IMPLEMENTATION_QUEUE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--cooldown-hours", type=float, default=DEFAULT_DISPATCH_COOLDOWN_HOURS)
    return parser.parse_args()


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    ledger_path = workspace_path(args.ledger)
    handoff = build_handoff(
        workspace_path(args.pm_actions),
        workspace_path(args.pm_state),
        workspace_path(args.heartbeat),
        workspace_path(args.implementation_queue),
        ledger_path,
        args.cooldown_hours,
    )
    if args.write:
        atomic_write_json(out, handoff)
        ledger = update_ledger(ledger_path, handoff)
        atomic_write_json(ledger_path, ledger)
    print(json.dumps({
        "status": handoff.get("status"),
        "validation": handoff.get("validation"),
        "selected_action": as_dict(handoff.get("selected_action")).get("action_id"),
        "out": rel(out),
        "ledger": rel(ledger_path),
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(handoff.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
