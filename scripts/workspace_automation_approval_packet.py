#!/usr/bin/env python3
"""Build the workspace automation approval-readiness packet.

This packet is a review-only planning and owner-decision surface. It does not
delete files, mutate cron schedules, change runtime/config/auth settings,
touch finance canon/portfolio state, submit paper/live orders, or infer owner
approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "workspace-automation-approval-packet.json"
OUT_MD = TMP / "workspace-automation-approval-packet.md"
SCHEMA = "veritas.workspace_automation_approval_packet.v1"

INPUTS = {
    "status_card": TMP / "veritas-status-card.json",
    "tmp_cleanup_report": TMP / "tmp-cleanup-report.json",
    "tmp_lifecycle_guard": TMP / "tmp-lifecycle-guard.json",
    "wf88_cleanup_plan": TMP / "wf88-retired-surface-cleanup-plan.json",
    "wf88_deletion_prep": TMP / "wf88-deletion-approval-prep-packet.json",
    "cron_control": TMP / "cron-control-packet.json",
    "token_efficiency": TMP / "token-efficiency-scorecard.json",
    "implementation_token_bridge": TMP / "implementation-token-attribution-bridge.json",
    "actionable_queue": TMP / "actionable-improvement-queue.json",
    "wf74_opportunities": TMP / "wf74-improvement-opportunity-queue.json",
    "security_warnings": TMP / "security-warning-ledger.json",
    "lane_register": TMP / "concurrent-lane-register.json",
    "pm_control": TMP / "pm-control-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "approval_packet_only": True,
    "delete_archive_move_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_or_source_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def blocked_or_missing_status(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return not normalized or normalized == "error" or "blocked" in normalized


def token_prefilter_telemetry_ready(token: dict[str, Any], bridge: dict[str, Any]) -> bool:
    """Return whether advisory prefilter candidates have a non-blocked evidence path.

    A token scorecard can legitimately be a warning while it identifies a
    review-only candidate.  It cannot, however, make a queue item ready when
    either its own or the implementation attribution bridge's source or
    validation state is blocked, errored, or absent.
    """
    return not any(
        (
            blocked_or_missing_status(token.get("status")),
            blocked_or_missing_status(as_dict(token.get("validation")).get("status")),
            blocked_or_missing_status(bridge.get("status")),
            blocked_or_missing_status(as_dict(bridge.get("validation")).get("status")),
        )
    )


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def input_record(path: Path, payload: dict[str, Any], required: bool = True) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def lane_summary(register: dict[str, Any]) -> dict[str, Any]:
    lanes = as_list(register.get("lanes"))
    active = [lane for lane in lanes if as_dict(lane).get("status") in {"planned", "leased", "running"}]
    return {
        "lane_count": len(lanes),
        "active_lane_count": len(active),
        "active_lane_ids": [as_dict(lane).get("lane_id") for lane in active[:12]],
    }


def current_area_state(artifacts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    status = artifacts["status_card"]
    tmp_guard = artifacts["tmp_lifecycle_guard"]
    cleanup_plan = artifacts["wf88_cleanup_plan"]
    deletion_prep = artifacts["wf88_deletion_prep"]
    cron = artifacts["cron_control"]
    token = artifacts["token_efficiency"]
    bridge = artifacts["implementation_token_bridge"]
    actionable = artifacts["actionable_queue"]
    wf74 = artifacts["wf74_opportunities"]
    lanes = artifacts["lane_register"]
    security = artifacts["security_warnings"]
    cleanup_report = artifacts["tmp_cleanup_report"]

    status_artifacts = as_dict(status.get("artifact_index_health"))
    finance = as_dict(status.get("finance_os"))
    wf78 = as_dict(status.get("wf78_visibility"))
    token_summary = as_dict(token.get("summary"))
    token_validation = as_dict(token.get("validation"))
    bridge_summary = as_dict(bridge.get("summary"))
    bridge_validation = as_dict(bridge.get("validation"))
    billing_semantics = as_dict(token.get("billing_semantics"))
    oauth_capacity_control = as_dict(token.get("oauth_capacity_control"))
    api_equivalent_cost = token_summary.get("api_equivalent_cost_usd")
    if api_equivalent_cost is None:
        api_equivalent_cost = token_summary.get("estimated_cost_total")

    return {
        "workspace_cleanup": {
            "tmp_total_mb": as_dict(tmp_guard.get("summary")).get("tmp_total_mb") or status_artifacts.get("tmp_total_mb"),
            "tmp_json_count": as_dict(tmp_guard.get("summary")).get("tmp_json_count") or status_artifacts.get("tmp_json_count"),
            "cleanup_preview_eligible_count": as_dict(tmp_guard.get("summary")).get("cleanup_preview_eligible_count")
            or status_artifacts.get("cleanup_preview_eligible_count"),
            "cleanup_plan_status": cleanup_plan.get("status"),
            "destructive_approval_ready_count": as_dict(deletion_prep.get("summary")).get("approval_packets_ready_count"),
            "tmp_cleanup_protected_violation_count": as_dict(cleanup_report.get("summary")).get("protected_violation_count"),
            "tmp_cleanup_candidate_digest": as_dict(cleanup_report.get("summary")).get("candidate_digest"),
        },
        "cron_efficiency": {
            "cron_status": cron.get("status"),
            "enabled_job_count": as_dict(cron.get("summary")).get("enabled_job_count"),
            "blocked_count": as_dict(cron.get("summary")).get("blocked_count"),
            "escalation_signal_count": as_dict(cron.get("summary")).get("escalation_signal_count"),
            "top_attention_jobs": as_list(as_dict(status.get("cron_fleet_health")).get("top_attention_jobs")),
        },
        "session_startup": {
            "status_card_status": status.get("status"),
            "startup_brief_status": as_dict(as_dict(status.get("input_artifacts")).get("startup_brief_packet")).get("status"),
            "stale_input_count": len(as_list(status.get("stale_inputs"))),
            "active_item_count": len(as_list(status.get("active_items"))),
        },
        "session_closeout": {
            "implementation_token_gap_count": bridge_summary.get("implementation_token_gap_count"),
            "closeout_enforcement_required": bridge_summary.get("closeout_enforcement_required"),
            "lane_register": lane_summary(lanes),
        },
        "helper_lanes": lane_summary(lanes),
        "repeated_friction": {
            "actionable_status": actionable.get("status"),
            "action_item_count": as_dict(actionable.get("summary")).get("action_item_count"),
            "monitor_only_count": as_dict(actionable.get("summary")).get("monitor_only_count"),
            "wf74_opportunity_count": as_dict(wf74.get("summary")).get("opportunity_count"),
            "wf74_high_priority_count": as_dict(wf74.get("summary")).get("high_priority_count"),
            "wf74_top_opportunity": as_dict(wf74.get("summary")).get("top_opportunity_title"),
        },
        "token_cost_control": {
            "token_status": token.get("status"),
            "token_validation_status": token_validation.get("status"),
            "implementation_token_bridge_status": bridge.get("status"),
            "implementation_token_bridge_validation_status": bridge_validation.get("status"),
            "prefilter_telemetry_ready": token_prefilter_telemetry_ready(token, bridge),
            "total_tokens": token_summary.get("total_tokens"),
            "api_equivalent_cost_usd": api_equivalent_cost,
            "api_equivalent_estimate_status": token_summary.get("api_equivalent_estimate_status"),
            "api_equivalent_cost_rows": token_summary.get("api_equivalent_cost_rows"),
            "api_equivalent_cost_event_coverage_percent": token_summary.get("api_equivalent_cost_event_coverage_percent"),
            "estimated_cost_total": api_equivalent_cost,
            "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
            "estimated_chatgpt_credits": token_summary.get("estimated_chatgpt_credits"),
            "chatgpt_credit_estimate_status": token_summary.get("chatgpt_credit_estimate_status"),
            "estimated_chatgpt_credit_rows": token_summary.get("estimated_chatgpt_credit_rows"),
            "chatgpt_credit_event_coverage_percent": token_summary.get("chatgpt_credit_event_coverage_percent"),
            "actual_billed_cost_usd": token_summary.get("actual_billed_cost_usd"),
            "billing_semantics": billing_semantics,
            "oauth_capacity_control": oauth_capacity_control,
            "oauth_quota_state": oauth_capacity_control.get("state") or oauth_capacity_control.get("status"),
            "oauth_remaining_percent": oauth_capacity_control.get("remaining_percent"),
            "unknown_or_invalid_input_token_semantics_event_count": token_summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            "rolling_5h_total_tokens": token_summary.get("rolling_5h_total_tokens"),
            "rolling_7d_observed_total_tokens": token_summary.get("rolling_7d_observed_total_tokens"),
            "usage_timestamp_coverage_percent": token_summary.get("usage_timestamp_coverage_percent"),
            "usage_pace": as_dict(token.get("usage_pace")),
            "api_call_reduction_candidate_count": token_summary.get("api_call_reduction_candidate_count"),
            "prompt_compression_candidate_count": token_summary.get("prompt_compression_candidate_count"),
            "top_candidate": token_summary.get("top_candidate"),
        },
        "finance_os": {
            "wf84_data_plane": finance.get("wf84_data_plane"),
            "wf85_decision_os": finance.get("wf85_decision_os"),
            "wf78_actionable_now_count": wf78.get("actionable_now_count"),
            "owner_review_ready_count": wf78.get("owner_review_ready_count"),
            "paper_execution_ready_count": as_dict(status.get("paper_top_blocker_summary")).get("execution_ready_count"),
        },
        "security_runtime": {
            "security_status": security.get("status") or as_dict(status.get("security_warnings")).get("status"),
            "open_warning_count": as_dict(security.get("summary")).get("open_warning_count")
            or as_dict(status.get("security_warnings")).get("open_warning_count"),
            "owner_decision_required_count": as_dict(security.get("summary")).get("owner_decision_required_count")
            or as_dict(status.get("security_warnings")).get("owner_decision_required_count"),
        },
    }


def area_plan(area_state: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    token_cost_control = area_state["token_cost_control"]
    token_candidate_count = as_int(token_cost_control.get("api_call_reduction_candidate_count"))
    if token_cost_control.get("prefilter_telemetry_ready") is not True:
        token_plan_status = "token_telemetry_repair_required"
    elif token_candidate_count:
        token_plan_status = "ready_for_prefilter_patch_queue"
    else:
        token_plan_status = "monitor_no_prefilter_candidates"
    return [
        {
            "area": "Workspace cleanup",
            "automate_next": "Two-pass reference-checked cleanup microbatches with rollback manifests.",
            "current_state": area_state["workspace_cleanup"],
            "implementation_steps": [
                "Generate nightly/weekly dry-run candidate inventory with protected-file assertions and a candidate digest.",
                "Run reference checks against artifact index, workflow routers, cron contracts, source-lineage registries, and live owner surfaces.",
                "Build one narrow microbatch packet at a time with hashes, rollback paths, validators, and exact approval language.",
                "Apply only after exact owner approval, then rerun reference checks and cleanup packets.",
            ],
            "owner_approval_required": "Required before any delete, archive, move, or apply.",
            "boundary": "No delete/archive/move/apply without exact owner approval and rollback proof.",
            "status": "proof_ready_destructive_apply_blocked",
        },
        {
            "area": "Cron efficiency",
            "automate_next": "Changed-input prefilters before model cron jobs.",
            "current_state": area_state["cron_efficiency"],
            "implementation_steps": [
                "Rank top token-heavy cron jobs from token-efficiency scorecard.",
                "For each candidate, define source-artifact hashes and skip conditions.",
                "Patch one command/model job at a time with no schedule/model/authority change.",
                "Validate skip/no-skip parity with cron contract, freshness spine, control packet, and token ledger.",
            ],
            "owner_approval_required": "Required before schedule/model/cadence mutation; not required for local proof-only prefilter patch when authority is unchanged.",
            "boundary": "No cron schedule or model-route change without validated diff and approval.",
            "status": "ready_for_scoped_prefilter_patches_after_current_cron_blockers_clear",
        },
        {
            "area": "Session startup",
            "automate_next": "Auto-build what changed, what matters, and next action from status, PM, cron, and WF88.",
            "current_state": area_state["session_startup"],
            "implementation_steps": [
                "Keep shallow status read-only and cached.",
                "Add a startup delta packet that compares latest status, PM, cron, WF88, and prior closeout stamps.",
                "Render a compact direct-session brief with active blocker, next action, and authority flags.",
                "Fail closed to cached status when source packets are stale or blocked.",
            ],
            "owner_approval_required": "Not required while read-only; required for new cron schedule or notification behavior.",
            "boundary": "Read-only; no PM/cron/workflow regeneration for shallow status unless explicitly requested.",
            "status": "ready_for_read_only_packet_slice",
        },
        {
            "area": "Session closeout",
            "automate_next": "Auto-update daily memory, lane register, proof ledger, and status card after material work.",
            "current_state": area_state["session_closeout"],
            "implementation_steps": [
                "Create a closeout stamp command that records changed files, validators, proof artifacts, and authority boundaries.",
                "Require lane closeout token metadata where provider/runtime exposes it, otherwise classify missing usage.",
                "Refresh startup/status packets after material closeout producers finish.",
                "Append daily memory only for meaningful coding, governance, finance workflow, or automation work.",
            ],
            "owner_approval_required": "Not required for local proof/memory/status updates inside workspace.",
            "boundary": "Local workspace only; no external delivery and no authority expansion.",
            "status": "ready_for_closeout_stamp_implementation",
        },
        {
            "area": "Helper lanes",
            "automate_next": "Auto-lease exact write surfaces, spawn bounded helper, run validators, close lane.",
            "current_state": area_state["helper_lanes"],
            "implementation_steps": [
                "Build a helper-lane launcher that refuses to spawn until read-first files, allowed writes, stop lines, and acceptance commands exist.",
                "Record model route, session metadata, and token attribution fields.",
                "Run only lane-local validators while shared validator outputs are owned by another active lane.",
                "Main session verifies output before shared continuity or owner surfaces are updated.",
            ],
            "owner_approval_required": "Not required for local bounded helpers; required for external/runtime/config/destructive/finance execution scopes.",
            "boundary": "Main verifies; helpers cannot mutate canon, schedules, config, cleanup apply, or execution authority.",
            "status": "ready_for_launcher_design_after_lane_collision_policy_patch",
        },
        {
            "area": "Repeated friction",
            "automate_next": "Auto-convert repeated failures into WF74 proposals or Skill Workshop drafts.",
            "current_state": area_state["repeated_friction"],
            "implementation_steps": [
                "Use WF74/actionable queues to detect repeated blocker recurrence and stale follow-through.",
                "Route deterministic code/validator friction into PM jobs or WF74 proposals.",
                "Route durable operator-behavior friction into Skill Workshop proposal drafts, not live skills.",
                "Close rows only after proof artifacts show the recommendation was routed, rejected, or monitor-only.",
            ],
            "owner_approval_required": "Required before applying, installing, rejecting, or quarantining Skill Workshop proposals.",
            "boundary": "Proposal only; no auto-apply or live skill mutation.",
            "status": "routing_layer_active_next_step_is_gap_close_for_high_priority_rows",
        },
        {
            "area": "Token/cost control",
            "automate_next": "Use OAuth capacity snapshots and explicit API-equivalent/credit semantics alongside deterministic predispatch reviews.",
            "current_state": token_cost_control,
            "implementation_steps": [
                "Record only sanitized remaining-capacity/reset metadata from a trusted status surface; never store account identity or raw status text.",
                "Keep API-equivalent USD, estimated ChatGPT credits, and owner-entered actual billed spend as separate fields.",
                "Start with top token-heavy jobs and add changed-input hash gates before model calls.",
                "Add prompt-compression harnesses only after fixture parity exists.",
                "Classify implementation token gaps as provider/runtime unavailable or stamp usage when exposed.",
                "Refresh the token scorecard after each patch; quota guidance remains advisory and cannot change cadence, model routes, or runtime automatically.",
            ],
            "owner_approval_required": "Required for raw prompt/tool capture or telemetry-depth expansion; not required for metadata-only local scorecards.",
            "boundary": "No raw prompt/tool payload capture without approval.",
            "status": token_plan_status,
        },
        {
            "area": "Finance OS",
            "automate_next": "More automatic non-capital ticker routing, stale evidence repair, and decision-card prep.",
            "current_state": area_state["finance_os"],
            "implementation_steps": [
                "Keep SQL/JSON canon guard as the internal review-only current-state source.",
                "Automate stale evidence repair and Tier C/B/A routing where validators are clean.",
                "Prepare owner-review cards and WF67 request artifacts when data is fresh and gates support them.",
                "Keep execution, cash/sizing/risk, portfolio/canon mutation, and paper/live/account action owner-gated.",
            ],
            "owner_approval_required": "Required for capital deployment, execution, account action, cash/sizing/risk mutation, and non-standing canon/portfolio mutation.",
            "boundary": "No capital/execution approval inferred.",
            "status": "non_capital_routing_active_but_wf84_wf85_currently_stale",
        },
        {
            "area": "Security/runtime",
            "automate_next": "Daily local-only config, scope, exposure, and secret-reference checks.",
            "current_state": area_state["security_runtime"],
            "implementation_steps": [
                "Run daily local-only bounded hardening and warning ledger refresh.",
                "Classify findings as accepted risk, local proof repair, owner decision, or blocked config/runtime mutation.",
                "Add secret-reference pattern checks for generated artifacts and logs without printing secret values.",
                "Prepare proposed diffs only; require approval before config/auth/runtime/service/channel mutation.",
            ],
            "owner_approval_required": "Required before config/auth/runtime/channel/service/startup/network exposure mutation.",
            "boundary": "No config/auth/runtime mutation without approval.",
            "status": "monitoring_active_owner_decisions_remain_open",
        },
    ]


def owner_approval_items(area_state: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    token_cost_control = area_state["token_cost_control"]
    token_candidate_count = as_int(token_cost_control.get("api_call_reduction_candidate_count"))
    token_prefilter_ready = (
        token_cost_control.get("prefilter_telemetry_ready") is True
        and token_candidate_count > 0
    )
    token_prefilter_why = (
        f"Token scorecard identifies {token_candidate_count} API-call reduction candidates with a non-blocked implementation attribution bridge."
        if token_prefilter_ready
        else "Token scorecard or implementation-token attribution bridge is blocked, errored, absent, or has no candidate; repair telemetry before queueing a prefilter patch."
    )
    return [
        {
            "decision": "Cleanup apply authority",
            "ready_now": False,
            "why": "Current WF88 deletion prep reports no destructive approval packet ready.",
            "exact_boundary": "Approve only exact listed microbatches with hashes, rollback, reference review, and validators.",
            "approval_phrase_template": "Approve the cleanup microbatch exactly as listed in tmp/<packet>.json.",
        },
        {
            "decision": "Cleanup Autopilot Phase 1 review-only cadence",
            "ready_now": True,
            "why": "Review-only packet generation and dry-run proof can run without deletion authority, but a new cron schedule would still be a schedule mutation.",
            "exact_boundary": "Review-only classification, reference checks, packet generation; no delete/archive/move/apply.",
            "approval_phrase_template": "Approve a review-only Cleanup Autopilot Phase 1 schedule that generates cleanup approval-readiness packets only and performs no delete/archive/move/apply.",
        },
        {
            "decision": "Cron prefilter patch queue",
            "ready_now": token_prefilter_ready,
            "why": token_prefilter_why,
            "exact_boundary": "Changed-input hash gates only; no schedule/model/authority mutation.",
            "approval_phrase_template": "Proceed with scoped cron changed-input prefilter patches that do not alter schedules, model routes, or authority boundaries.",
        },
        {
            "decision": "Authenticated OAuth collector or automatic throttling",
            "ready_now": False,
            "why": "The implemented path accepts explicit sanitized snapshots only; authenticated quota collection and automatic runtime action were not approved.",
            "exact_boundary": "Any future collector or throttle requires a separate auth/runtime/config review; raw content and secrets remain blocked.",
            "approval_phrase_template": "Approve a separately scoped read-only authenticated quota collector review; do not enable automatic schedule, model, runtime, or credit-purchase actions.",
        },
        {
            "decision": "Finance OS non-capital expansion",
            "ready_now": True,
            "why": "Non-capital routing and repair can expand through existing validators, but WF84/WF85 freshness must be restored before decision claims.",
            "exact_boundary": "Ticker routing, stale evidence repair, and card prep only; no capital, execution, account, cash, sizing, or approval authority.",
            "approval_phrase_template": "Proceed with validated non-capital finance routing and evidence-repair automation only; execution and capital decisions remain owner-gated.",
        },
    ]


def implementation_sequence() -> list[dict[str, Any]]:
    return [
        {
            "phase": "0. Control contract",
            "goal": "Keep every automation lane review-only unless a narrower standing approval exists.",
            "acceptance": "Approval packet authority flags are false for destructive cleanup, cron mutation, runtime/config mutation, finance execution, and owner approval inference.",
        },
        {
            "phase": "1. Owner approval readiness packet",
            "goal": "Consolidate all nine automation lanes into one packet and Markdown decision surface.",
            "acceptance": "workspace_automation_approval_packet.py writes JSON/MD and validates.",
        },
        {
            "phase": "2. Cleanup proof hardening",
            "goal": "Add explicit protected-file/no-delete assertions and candidate digest to cleanup dry-runs.",
            "acceptance": "tmp_cleanup.py dry-run writes protection_assertions with zero protected candidate violations.",
        },
        {
            "phase": "3. Cleanup autopilot",
            "goal": "Build two-pass reference checks and one-microbatch approval packets.",
            "acceptance": "No destructive approval packet is emitted unless references, rollback, hashes, and validators are clean.",
        },
        {
            "phase": "4. Cron/token efficiency",
            "goal": "Patch top model cron jobs with changed-input prefilters and parity tests.",
            "acceptance": "Cron contract/freshness/control proof remains clean and token scorecard shows reduced calls or classified no-op.",
        },
        {
            "phase": "5. Session lifecycle",
            "goal": "Add startup delta and closeout stamp producers.",
            "acceptance": "Material session closeout updates daily memory/status/proof ledgers without external delivery.",
        },
        {
            "phase": "6. Helper-lane launcher",
            "goal": "Refuse unsafe helper work until lease/read-first/write/validator/stop-line fields are complete.",
            "acceptance": "Launcher cannot spawn or close a lane with missing contract or colliding writes.",
        },
        {
            "phase": "7. Friction to proposals",
            "goal": "Route repeated blockers into WF74/PM/Skill Workshop proposals.",
            "acceptance": "Open recommendations are routed, proposal-only, and leak guard remains clean.",
        },
        {
            "phase": "8. Finance/security expansion",
            "goal": "Expand non-capital finance routing and local-only security/runtime checks.",
            "acceptance": "Finance execution and config/runtime mutation remain explicitly blocked until exact approval.",
        },
    ]


def build_packet() -> dict[str, Any]:
    artifacts = {name: load_optional(path) for name, path in INPUTS.items()}
    area_state = current_area_state(artifacts)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "owner_approval_readiness_packet_ready",
        "purpose": "Long implementation plan and owner-decision surface for the next workspace automations.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {name: input_record(path, artifacts[name], required=name not in {"tmp_cleanup_report"}) for name, path in INPUTS.items()},
        "area_state": area_state,
        "implementation_plan": area_plan(area_state),
        "implementation_sequence": implementation_sequence(),
        "owner_approval_items": owner_approval_items(area_state),
        "current_slice": {
            "implemented_by_this_packet": [
                "cleanup dry-run protected-file/no-delete assertions",
                "cleanup candidate digest in tmp-cleanup-report.json",
                "workspace automation approval-readiness JSON/Markdown packet",
                "OAuth-aware token/cost semantics and advisory capacity state propagation",
            ],
            "not_implemented_by_this_packet": [
                "destructive cleanup apply",
                "cron schedule/model mutation",
                "runtime/config/auth mutation",
                "finance canon/portfolio/capital/execution mutation",
                "external/customer delivery",
            ],
        },
        "next_safe_action": "Review owner_approval_items and pick one narrow approval class; default next implementation is cleanup autopilot reference-check microbatch prep with no apply authority.",
    }
    packet["validation"] = validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred"):
            if value is not False:
                errors.append(f"{key}_must_be_false")
    if boundary.get("review_only") is not True:
        errors.append("review_only_must_be_true")
    areas = as_list(packet.get("implementation_plan"))
    if len(areas) != 9:
        errors.append("implementation_plan_must_cover_9_areas")
    area_names = {as_dict(area).get("area") for area in areas}
    for expected in {
        "Workspace cleanup",
        "Cron efficiency",
        "Session startup",
        "Session closeout",
        "Helper lanes",
        "Repeated friction",
        "Token/cost control",
        "Finance OS",
        "Security/runtime",
    }:
        if expected not in area_names:
            errors.append(f"missing_area:{expected}")
    for item in as_list(packet.get("owner_approval_items")):
        if not as_dict(item).get("exact_boundary"):
            errors.append(f"approval_item_missing_boundary:{as_dict(item).get('decision')}")
    cleanup_state = as_dict(as_dict(packet.get("area_state")).get("workspace_cleanup"))
    if cleanup_state.get("tmp_cleanup_protected_violation_count") not in {0, None}:
        errors.append("tmp_cleanup_protected_violation_count_must_be_zero_or_unknown")
    if cleanup_state.get("tmp_cleanup_candidate_digest") is None:
        warnings.append("tmp_cleanup_digest_missing_run_tmp_cleanup_first")
    token_state = as_dict(as_dict(packet.get("area_state")).get("token_cost_control"))
    token_billing = as_dict(token_state.get("billing_semantics"))
    token_capacity = as_dict(token_state.get("oauth_capacity_control"))
    if token_billing and token_state.get("api_equivalent_cost_usd") is not None and token_billing.get("api_equivalent_is_not_invoice") is not True:
        errors.append("token_api_equivalent_cost_missing_not_invoice_guard")
    if token_capacity and token_capacity.get("automatic_action_allowed") is not False:
        errors.append("oauth_capacity_automatic_action_must_be_false")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_md(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Workspace Automation Approval Packet")
    lines.append("")
    lines.append(f"Generated: `{packet['generated_at_utc']}`")
    lines.append(f"Status: `{packet['status']}`")
    lines.append("")
    lines.append("## Bottom Line")
    lines.append("")
    lines.append(
        "The next automation layer should expand proof, routing, and owner-ready approval packets first. "
        "Destructive cleanup, cron schedule/model changes, runtime/config mutation, finance execution, "
        "and external delivery stay blocked until a narrow approval packet exists."
    )
    lines.append("")
    lines.append("## Implementation Plan")
    lines.append("")
    for row in packet["implementation_plan"]:
        lines.append(f"### {row['area']}")
        lines.append("")
        lines.append(f"- Automate next: {row['automate_next']}")
        lines.append(f"- Status: `{row['status']}`")
        lines.append(f"- Boundary: {row['boundary']}")
        lines.append(f"- Owner approval: {row['owner_approval_required']}")
        lines.append("- Steps:")
        for step in row["implementation_steps"]:
            lines.append(f"  - {step}")
        lines.append("- Current state:")
        for key, value in as_dict(row.get("current_state")).items():
            lines.append(f"  - `{key}`: `{value}`")
        lines.append("")
    lines.append("## Sequence")
    lines.append("")
    for phase in packet["implementation_sequence"]:
        lines.append(f"- **{phase['phase']}**: {phase['goal']} Acceptance: {phase['acceptance']}")
    lines.append("")
    lines.append("## Owner Approval Items")
    lines.append("")
    lines.append("| Decision | Ready now | Boundary | Approval language template |")
    lines.append("|---|---:|---|---|")
    for item in packet["owner_approval_items"]:
        lines.append(
            f"| {item['decision']} | {item['ready_now']} | {item['exact_boundary']} | {item['approval_phrase_template']} |"
        )
    lines.append("")
    lines.append("## Current Slice")
    lines.append("")
    lines.append("Implemented:")
    for item in packet["current_slice"]["implemented_by_this_packet"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Not implemented:")
    for item in packet["current_slice"]["not_implemented_by_this_packet"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    validation = as_dict(packet.get("validation"))
    lines.append(f"- Status: `{validation.get('status')}`")
    for error in as_list(validation.get("errors")):
        lines.append(f"- ERROR: {error}")
    for warning in as_list(validation.get("warnings")):
        lines.append(f"- WARNING: {warning}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet()
    if args.write:
        atomic_write_json(OUT_JSON, packet)
    if args.write_md:
        atomic_write_text(OUT_MD, render_md(packet))
    response = {
        "status": packet.get("status"),
        "validation": packet.get("validation"),
        "json": rel(OUT_JSON) if args.write else None,
        "md": rel(OUT_MD) if args.write_md else None,
        "next_safe_action": packet.get("next_safe_action"),
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
