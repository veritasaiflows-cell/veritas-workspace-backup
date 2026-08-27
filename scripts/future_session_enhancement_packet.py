#!/usr/bin/env python3
"""Build a thin startup packet for future Veritas sessions.

This is a routing/proof surface. It summarizes the current boot route,
workflow/PM/cron/WF74 state, and hard authority boundaries so a new session can
orient quickly without treating generated artifacts as canon or approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import improvement_ledger as improvement_ledger_mod
import project_implementation_router as implementation_router
import session_resume_checkpoint as resume_checkpoint
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
MEMORY = ROOT / "memory"
OUT = TMP / "future-session-enhancement-packet.json"
SCHEMA = "veritas.future_session_enhancement_packet.v1"
LOCAL_TZ = ZoneInfo("America/Phoenix")
CRON_MIGRATION_REPAIR_TITLE = "Route blocked cron signals into a migration-ready repair plan"
WORKFLOW_BLOCKER_FOLLOWUP_TITLE = "Convert workflow advancement blockers into implementation follow-ups"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routes_truth_surfaces_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

CORE_SURFACES = [
    "SOUL.md",
    "AGENTS.md",
    "USER.md",
    "TOOLS.md",
    "06. Playbooks/Startup Truth Index.md",
    "06. Playbooks/Active Workflows.md",
    "MEMORY.md",
]

CORE_EFFICIENCY_MARKERS = {
    "AGENTS.md": ["project_implementation_router.py", "model_free_command", "codex_native_subagent"],
    "TOOLS.md": ["project_implementation_router.py", "persistent_isolated_agent", "Main/Sol"],
    "06. Playbooks/Startup Truth Index.md": [
        "veritas.execution_efficiency_policy.v1",
        "persistent_isolated_agent",
        "actual backend/model/thinking",
    ],
}

ARTIFACTS = {
    "pm_control_packet": "tmp/pm-control-packet.json",
    "cron_control_packet": "tmp/cron-control-packet.json",
    "wf74_collection": "tmp/wf74-model-quality-collection-cron-runner.json",
    "wf74_opportunity_queue": "tmp/wf74-improvement-opportunity-queue.json",
    "wf74_auto_patch_proposer": "tmp/wf74-auto-patch-proposer.json",
    "wf74_decision_docket": "tmp/wf74-decision-docket.json",
    "otel_learning_loop": "tmp/otel-learning-loop.json",
    "workflow_blocker_followups": "tmp/workflow-blocker-followups.json",
    "improvement_ledger": "tmp/improvement-ledger-current.json",
    "actionable_improvement_queue": "tmp/actionable-improvement-queue.json",
    "no_orphan_validator": "tmp/no-orphan-validator.json",
    "owner_gated_action_review_queue": "tmp/owner-gated-action-review-queue.json",
    "token_usage_ledger": "tmp/token-usage-ledger-current.json",
    "model_run_ledger": "tmp/model-run-ledger-current.json",
    "finance_correctness_ledger": "tmp/finance-recommendation-correctness-ledger-current.json",
    "model_quality_scorecard": "tmp/model-quality-scorecard.json",
    "wf74_cron_duplication_audit": "tmp/wf74-cron-duplication-audit.json",
    "training_dataset_candidates": "tmp/training-dataset-candidates.json",
    "changed_file_validator_router": "tmp/changed-file-validator-router.json",
    "current_resume": "tmp/current-resume.json",
    "current_active_lanes": "tmp/current-active-lanes.json",
    "main_session_escalation_consumer": "tmp/main-session-escalation-consumer.json",
    "main_session_action_executor": "tmp/main-session-action-executor.json",
    "finance_evidence_warning_router": "tmp/finance-evidence-warning-router.json",
    "wf88_wiki_synthesis": "tmp/wf88-wiki-synthesis-packet.json",
    "wiki_bootstrap_proof": "tmp/wiki-bootstrap-proof.json",
    "coding_outcome_ledger": "tmp/coding-outcome-ledger-current.json",
}

DERIVED_FILES = {
    "artifact_index_sqlite": "tmp/veritas-artifact-index.sqlite",
}

IMPROVEMENT_LEDGER_HISTORY = ROOT / "data" / "state-history" / "improvement-ledger.jsonl"

PACKET_MAX_STARTUP_AGE_HOURS = 12

VOLATILE_SIGNATURE_KEYS = {
    "age_hours",
    "age_seconds",
    "completed_at_utc",
    "duration_ms",
    "elapsed_seconds",
    "expires_at_utc",
    "freshness",
    "generated_at_utc",
    "modified_utc",
    "previous_freshness",
    "started_at_utc",
    "timestamp_utc",
    "updated_at_utc",
}

ARTIFACT_MAX_AGE_HOURS = {
    "pm_control_packet": 12,
    "cron_control_packet": 12,
    "wf74_collection": 24,
    "wf74_opportunity_queue": 24,
    "wf74_auto_patch_proposer": 24,
    "wf74_decision_docket": 24,
    "otel_learning_loop": 24,
    "workflow_blocker_followups": 24,
    "improvement_ledger": 24,
    "actionable_improvement_queue": 24,
    "no_orphan_validator": 24,
    "owner_gated_action_review_queue": 24,
    "token_usage_ledger": 24,
    "model_run_ledger": 24,
    "finance_correctness_ledger": 24,
    "model_quality_scorecard": 24,
    "wf74_cron_duplication_audit": 24,
    "training_dataset_candidates": 168,
    "changed_file_validator_router": 24,
    "current_resume": 12,
    "current_active_lanes": 12,
    "main_session_escalation_consumer": 12,
    "main_session_action_executor": 12,
    "finance_evidence_warning_router": 12,
    "wf88_wiki_synthesis": 24,
    "wiki_bootstrap_proof": 24,
    "coding_outcome_ledger": 24,
}

DERIVED_FILE_MAX_AGE_HOURS = {
    "artifact_index_sqlite": 24,
}

WORKFLOW_IDS = ["WF75", "WF78", "WF79-SMB", "WF72", "WF73", "WF74", "WF84", "WF85", "WF88"]

CHALLENGER_MODEL_POLICY = {
    "schema": "veritas.challenger_model_policy.v1",
    "scope": "serious finance workflow contracts, authority-sensitive decision layers, and trade-grade OS promotion gates",
    "required_challenger_model": "claude-cli/claude-opus-4-8",
    "use_for": [
        "false-ready detection",
        "authority-drift review",
        "source/freshness and state-precedence critique",
        "schema/contract stress test before implementation or promotion",
    ],
    "do_not_use_as": [
        "routine implementation default",
        "execution authority",
        "approval authority",
        "canon or portfolio mutation authority",
    ],
    "verification_rule": "After spawn, verify the actual subagent model path equals claude-cli/claude-opus-4-8; labels such as Opus are not sufficient.",
    "fallback_rule": "If the verified model path is unavailable or mismatched, classify the lane as standard challenger output and do not count it as Opus acceptance proof.",
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


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def file_state(path: str) -> dict[str, Any]:
    full = ROOT / path
    try:
        stat = full.stat()
    except FileNotFoundError:
        return {"path": path, "exists": False}
    state = {
        "path": path,
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    required_markers = CORE_EFFICIENCY_MARKERS.get(path, [])
    if required_markers:
        text = full.read_text(encoding="utf-8", errors="replace")
        state["efficiency_markers"] = {marker: marker in text for marker in required_markers}
        state["missing_efficiency_markers"] = [marker for marker in required_markers if marker not in text]
    return state


def source_file_state(label: str, path: str) -> dict[str, Any]:
    state = file_state(path)
    entry: dict[str, Any] = {
        "label": label,
        "path": path,
        "exists": state.get("exists"),
    }
    full = ROOT / path
    if full.suffix.lower() == ".json":
        payload = as_dict(load_json_artifact(full))
        entry.update({
            "schema": payload.get("schema"),
            "status": payload.get("status"),
            "validation_status": as_dict(payload.get("validation")).get("status"),
            "semantic_hash": semantic_json_hash(payload),
        })
    else:
        entry.update({
            "size_bytes": state.get("size_bytes"),
            "modified_utc": state.get("modified_utc"),
        })
    return entry


def strip_volatile_signature_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_volatile_signature_fields(child)
            for key, child in sorted(value.items())
            if key not in VOLATILE_SIGNATURE_KEYS and not key.endswith("_at_utc")
        }
    if isinstance(value, list):
        return [strip_volatile_signature_fields(child) for child in value]
    return value


def semantic_json_hash(payload: dict[str, Any]) -> str | None:
    if not payload:
        return None
    stable = strip_volatile_signature_fields(payload)
    body = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def input_signature_source_paths(now: datetime) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    rows.extend((f"core:{path}", path) for path in CORE_SURFACES)
    rows.extend((f"artifact:{label}", path) for label, path in ARTIFACTS.items())
    rows.extend((f"derived:{label}", path) for label, path in DERIVED_FILES.items())
    rows.extend(
        (f"workflow:{workflow_id}", f"state/workflows/{workflow_id}.json")
        for workflow_id in WORKFLOW_IDS
    )
    rows.extend((f"memory:{item['path']}", item["path"]) for item in daily_memory_surfaces(now))
    rows.append(("producer:future_session_enhancement_packet", rel(Path(__file__).resolve())))
    rows.append(("producer:session_resume_checkpoint", rel(Path(resume_checkpoint.__file__).resolve())))
    rows.append(("policy:project_implementation_router", rel(Path(implementation_router.__file__).resolve())))
    rows.append(("state:concurrent_lane_register", "tmp/concurrent-lane-register.json"))
    return sorted(rows, key=lambda item: item[0])


def build_input_signature(now: datetime) -> dict[str, Any]:
    sources = [
        source_file_state(label, path)
        for label, path in input_signature_source_paths(now)
    ]
    body = json.dumps(sources, sort_keys=True, separators=(",", ":"))
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "source_count": len(sources),
        "sources": sources,
    }


def live_resume_reuse_gate(
    now: datetime,
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Require fresh live lane/checkpoint truth before reusing a packet."""
    live = recovery if recovery is not None else extract_interruption_recovery_summary(now)
    lane = as_dict(live.get("lane_register"))
    resume = as_dict(live.get("resume_checkpoint"))
    active_count = int(lane.get("active_lane_count") or 0)
    reasons: list[str] = []
    if lane.get("projection_validation_status") != "ok":
        reasons.append("active_lane_projection_not_ok")
    if lane.get("resolution") in {
        "blocked_ambiguous",
        "blocked_missing_identity",
        "blocked_missing_register",
        "blocked_stale_lease",
    }:
        reasons.append(str(lane.get("resolution")))
    if active_count:
        if resume.get("validation_status") != "ok":
            reasons.append("resume_validation_not_ok")
        if resume.get("target_eligible") is not True:
            reasons.append("resume_target_not_eligible")
        if resume.get("execution_receipt_consumed") is True or resume.get("replay_blocked") is True:
            reasons.append("resume_command_consumed")
        expiry = parse_utc(resume.get("freshness_expiry"))
        if expiry is None or expiry <= now.astimezone(timezone.utc):
            reasons.append("resume_checkpoint_expired")
    elif lane.get("resolution") != "none":
        reasons.append("zero_lane_projection_not_resolved")
    return {
        "status": "blocked" if reasons else "ok",
        "reasons": sorted(set(reasons)),
        "active_lane_count": active_count,
        "checkpoint_id": resume.get("checkpoint_id"),
    }


def prefilter_decision(
    out: Path,
    now: datetime,
    current_signature: dict[str, Any],
    *,
    live_recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous = as_dict(load_json_artifact(out))
    previous_signature = as_dict(previous.get("input_signature"))
    previous_validation = as_dict(previous.get("validation"))
    previous_freshness = freshness_state(
        previous.get("generated_at_utc"),
        now,
        PACKET_MAX_STARTUP_AGE_HOURS,
    )
    source_unchanged = bool(
        previous_signature.get("hash")
        and previous_signature.get("hash") == current_signature.get("hash")
    )
    resume_gate = live_resume_reuse_gate(now, live_recovery)
    previous_usable = bool(
        previous
        and previous_validation.get("status") in {"ok", "warning"}
        and not previous_freshness.get("stale")
    )
    can_reuse = source_unchanged and previous_usable and resume_gate.get("status") == "ok"
    if not previous:
        reason = "missing_previous_packet"
    elif not previous_signature.get("hash"):
        reason = "missing_previous_input_signature"
    elif not source_unchanged:
        reason = "source_signature_changed"
    elif previous_freshness.get("stale"):
        reason = "packet_freshness_expired"
    elif previous_validation.get("status") == "critical":
        reason = "previous_packet_validation_critical"
    elif previous_validation.get("status") not in {"ok", "warning"}:
        reason = "previous_packet_validation_not_usable"
    elif resume_gate.get("status") != "ok":
        reason = "live_resume_revalidation_blocked"
    else:
        reason = "unchanged_inputs_and_fresh_packet"
    return {
        "status": "reuse_existing_packet" if can_reuse else "refresh_required",
        "can_reuse_existing_packet": can_reuse,
        "reason": reason,
        "source_unchanged": source_unchanged,
        "previous_packet_exists": bool(previous),
        "previous_generated_at_utc": previous.get("generated_at_utc"),
        "previous_validation_status": previous_validation.get("status"),
        "previous_freshness": previous_freshness,
        "live_resume_gate": resume_gate,
        "previous_input_hash": previous_signature.get("hash"),
        "current_input_hash": current_signature.get("hash"),
    }


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def age_hours(timestamp_utc: Any, now: datetime) -> float | None:
    stamp = parse_utc(timestamp_utc)
    if stamp is None:
        return None
    return round(max(0.0, (now.astimezone(timezone.utc) - stamp).total_seconds() / 3600), 2)


def freshness_state(timestamp_utc: Any, now: datetime, max_age_hours: float | None) -> dict[str, Any]:
    age = age_hours(timestamp_utc, now)
    stale = bool(max_age_hours is not None and age is not None and age > max_age_hours)
    return {
        "timestamp_utc": timestamp_utc,
        "age_hours": age,
        "max_age_hours": max_age_hours,
        "stale": stale,
    }


def artifact_state(label: str, path: str, now: datetime) -> dict[str, Any]:
    full = ROOT / path
    data = as_dict(load_json_artifact(full))
    validation = as_dict(data.get("validation"))
    summary = as_dict(data.get("summary"))
    generated_at = data.get("generated_at_utc")
    return {
        "label": label,
        "path": path,
        "exists": full.exists(),
        "schema": data.get("schema"),
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": generated_at,
        "freshness": freshness_state(generated_at, now, ARTIFACT_MAX_AGE_HOURS.get(label)),
        "summary_keys": sorted(summary.keys())[:20],
    }


def daily_memory_surfaces(now: datetime) -> list[dict[str, Any]]:
    today = now.date()
    yesterday = today - timedelta(days=1)
    candidates = [
        MEMORY / f"{today.isoformat()}.md",
        MEMORY / f"{yesterday.isoformat()}.md",
    ]
    states: list[dict[str, Any]] = []
    for path in candidates:
        states.append(file_state(rel(path)))
    return states


def workflow_capsules() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workflow_id in WORKFLOW_IDS:
        path = ROOT / "state" / "workflows" / f"{workflow_id}.json"
        data = as_dict(load_json_artifact(path))
        rows.append({
            "workflow_id": workflow_id,
            "path": rel(path),
            "exists": path.exists(),
            "effective_status": data.get("effective_status"),
            "helper_safe": data.get("helper_safe"),
            "next_action": data.get("next_action"),
            "authority_boundary": data.get("authority_boundary"),
            "blocker_count": len(as_list(data.get("blockers"))),
        })
    return rows


def extract_pm_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "pm-control-packet.json"))
    summary = as_dict(data.get("summary"))
    next_actions = as_list(data.get("next_actions"))
    jobs = as_list(as_dict(data.get("implementation_job_queue")).get("jobs"))
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "top_lane": (next_actions[0] or {}).get("lane_id") if next_actions and isinstance(next_actions[0], dict) else None,
        "top_action": (next_actions[0] or {}).get("description") if next_actions and isinstance(next_actions[0], dict) else None,
        "open_job_count": len(jobs),
        "summary": {key: summary.get(key) for key in sorted(summary.keys())[:12]},
    }


def extract_cron_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "cron-control-packet.json"))
    summary = as_dict(data.get("summary"))
    escalation = as_dict(data.get("escalation"))
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "escalation_count": summary.get("escalation_count"),
        "should_wake_main_session": escalation.get("should_wake_main_session"),
        "summary": {key: summary.get(key) for key in sorted(summary.keys())[:12]},
    }


def extract_otel_carry_forward(now: datetime) -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "otel-learning-loop.json"))
    summaries = as_dict(data.get("learning_summaries"))
    health = as_dict(summaries.get("otel_health"))
    cost = as_dict(summaries.get("token_cost"))
    carry_forward = as_dict(data.get("carry_forward_contract"))
    auto_router = as_dict(data.get("auto_implementation_router"))
    return {
        "present": bool(data),
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
        "freshness": freshness_state(data.get("generated_at_utc"), now, ARTIFACT_MAX_AGE_HOURS.get("otel_learning_loop")),
        "collector_health": health.get("collector_health"),
        "drift_status": health.get("drift_status"),
        "daily_event_count": health.get("daily_event_count"),
        "daily_warning_or_error_count": health.get("daily_warning_or_error_count"),
        "token_coverage_ratio": cost.get("token_coverage_ratio"),
        "cost_coverage_ratio": cost.get("cost_coverage_ratio"),
        "recommendation_count": len([row for row in as_list(data.get("recommendations")) if isinstance(row, dict)]),
        "carry_forward_status": carry_forward.get("status"),
        "auto_implementation_status": auto_router.get("status"),
        "auto_apply_allowed": False,
        "next_safe_action": data.get("next_safe_action") or carry_forward.get("next_safe_action"),
    }


def extract_action_executor_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "main-session-action-executor.json"))
    summary = as_dict(data.get("summary"))
    selected = as_dict(summary.get("selected_pm_job"))
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "mode": data.get("mode"),
        "context": data.get("context"),
        "action_type": summary.get("action_type"),
        "classification": summary.get("classification"),
        "selected_pm_job": selected.get("job_id"),
        "selected_pm_title": selected.get("title"),
        "parallel_helper_workstream": summary.get("parallel_helper_workstream"),
        "parallel_helper_title": summary.get("parallel_helper_title"),
        "parallel_helper_pm_job_id": summary.get("parallel_helper_pm_job_id"),
        "executed": summary.get("executed"),
        "execution_failed": summary.get("execution_failed"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def extract_escalation_consumer_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "main-session-escalation-consumer.json"))
    summary = as_dict(data.get("summary"))
    unresolved = int(summary.get("unresolved_count") or 0)
    owner = int(summary.get("owner_decision_count") or 0)
    manual = int(summary.get("blocked_manual_count") or 0)
    repeated = int(summary.get("repeated_blocker_count") or 0)
    auto_actionable = int(summary.get("auto_actionable_count") or 0)
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "mode": data.get("mode"),
        "context": data.get("context"),
        "cron_should_wake_main_session": summary.get("cron_should_wake_main_session"),
        "cron_escalation_signal_count": summary.get("cron_escalation_signal_count"),
        "executed_safe_action_count": summary.get("executed_safe_action_count"),
        "unresolved_count": unresolved,
        "owner_decision_count": owner,
        "blocked_manual_count": manual,
        "repeated_blocker_count": repeated,
        "auto_actionable_count": auto_actionable,
        "repeated_only_routed": repeated > 0 and unresolved == 0 and owner == 0 and manual == 0 and auto_actionable > 0,
        "next_safe_action": summary.get("next_safe_action"),
    }


def extract_finance_warning_router_summary() -> dict[str, Any]:
    data = as_dict(load_json_artifact(TMP / "finance-evidence-warning-router.json"))
    summary = as_dict(data.get("summary"))
    return {
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "blocking_section_count": summary.get("blocking_section_count"),
        "blocking_sections": summary.get("blocking_sections"),
        "caveat_section_count": summary.get("caveat_section_count"),
        "caveat_sections": summary.get("caveat_sections"),
        "fundamental_warning_count": summary.get("fundamental_warning_count"),
        "fundamental_unknown_warning_codes": summary.get("fundamental_unknown_warning_codes"),
        "macro_warning_count": summary.get("macro_warning_count"),
        "energy_warning_count": summary.get("energy_warning_count"),
        "escalation_routed_repeated_only": summary.get("escalation_routed_repeated_only"),
        "saas_review_only_answer_can_proceed_with_caveats": summary.get("saas_review_only_answer_can_proceed_with_caveats"),
        "customer_output_allowed": summary.get("customer_output_allowed"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def improvement_ledger_history_fallback(now: datetime) -> dict[str, Any]:
    rows = [
        row for row in improvement_ledger_mod.read_jsonl(IMPROVEMENT_LEDGER_HISTORY)
        if row.get("schema") == improvement_ledger_mod.EVENT_SCHEMA
    ]
    latest = improvement_ledger_mod.latest_by_source_key(rows)
    open_rows = [
        row for row in latest
        if row.get("carry_forward") is not False and row.get("status") not in {"complete", "cancelled", "rejected"}
    ]
    closed_rows = [
        row for row in latest
        if row.get("carry_forward") is False or row.get("status") in {"complete", "cancelled", "rejected"}
    ]
    kpis = improvement_ledger_mod.learning_loop_kpis(open_rows, closed_rows)
    return {
        "source": rel(IMPROVEMENT_LEDGER_HISTORY),
        "history_row_count": len(rows),
        "fallback_generated_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "latest_open_count": len(open_rows),
        "latest_closed_count": len(closed_rows),
        "high_priority_open_count": len([row for row in open_rows if int(row.get("priority") or 0) >= 80]),
        "high_priority_overdue_open_count": kpis.get("high_priority_overdue_open_count"),
        "overdue_open_count": len([row for row in open_rows if row.get("sla_status") == "overdue"]),
        "due_soon_open_count": len([row for row in open_rows if row.get("sla_status") == "due_soon"]),
        "anti_theater_status": kpis.get("anti_theater_status"),
        "top_improvement_title": open_rows[0].get("title") if open_rows else None,
        "top_improvement_next_action": open_rows[0].get("next_action") if open_rows else None,
        "top_improvement_age_hours": open_rows[0].get("age_hours") if open_rows else None,
        "top_improvement_sla_status": open_rows[0].get("sla_status") if open_rows else None,
    }


def first_matching_opportunity(opportunities: list[dict[str, Any]], *, title: str | None = None, category: str | None = None) -> dict[str, Any]:
    for row in opportunities:
        if title and row.get("title") == title:
            return row
        if category and row.get("category") == category:
            return row
    return {}


def extract_wf74_summary(now: datetime) -> dict[str, Any]:
    collection = as_dict(load_json_artifact(TMP / "wf74-model-quality-collection-cron-runner.json"))
    opportunity_queue = as_dict(load_json_artifact(TMP / "wf74-improvement-opportunity-queue.json"))
    auto_patch = as_dict(load_json_artifact(TMP / "wf74-auto-patch-proposer.json"))
    decision_docket = as_dict(load_json_artifact(TMP / "wf74-decision-docket.json"))
    workflow_followups = as_dict(load_json_artifact(TMP / "workflow-blocker-followups.json"))
    cron_repair_plan = as_dict(load_json_artifact(TMP / "cron-migration-repair-plan.json"))
    cron_control = as_dict(load_json_artifact(TMP / "cron-control-packet.json"))
    improvement_ledger = as_dict(load_json_artifact(TMP / "improvement-ledger-current.json"))
    owner_gated = as_dict(load_json_artifact(TMP / "owner-gated-action-review-queue.json"))
    token_usage = as_dict(load_json_artifact(TMP / "token-usage-ledger-current.json"))
    model_run = as_dict(load_json_artifact(TMP / "model-run-ledger-current.json"))
    finance = as_dict(load_json_artifact(TMP / "finance-recommendation-correctness-ledger-current.json"))
    scorecard = as_dict(load_json_artifact(TMP / "model-quality-scorecard.json"))
    duplication_audit = as_dict(load_json_artifact(TMP / "wf74-cron-duplication-audit.json"))
    collection_summary = as_dict(collection.get("summary"))
    opportunity_summary = as_dict(opportunity_queue.get("summary"))
    auto_patch_summary = as_dict(auto_patch.get("summary"))
    docket_summary = as_dict(decision_docket.get("summary"))
    followup_summary = as_dict(workflow_followups.get("summary"))
    cron_summary = as_dict(cron_control.get("summary"))
    opportunities = [as_dict(row) for row in as_list(opportunity_queue.get("opportunities"))]
    cron_migration_opportunity = first_matching_opportunity(
        opportunities,
        title=CRON_MIGRATION_REPAIR_TITLE,
        category="cron_migration",
    )
    workflow_blocker_opportunity = first_matching_opportunity(
        opportunities,
        title=WORKFLOW_BLOCKER_FOLLOWUP_TITLE,
    )
    followups = [as_dict(row) for row in as_list(workflow_followups.get("followups"))]
    cron_migration_followups = [row for row in followups if row.get("route") == "cron_migration"]
    workflow_blocker_followups = [
        row for row in followups
        if row.get("route") in {"cron_migration", "maturity_accrual", "measurement_only", "dependency_rollup", "implementation_followup"}
    ]
    blocked_or_escalated_cron_count = (
        int(cron_summary.get("blocked_count") or 0)
        + int(cron_summary.get("escalation_signal_count") or 0)
    )
    cron_repair_plan_active = cron_repair_plan.get("active_repair_required") is True
    cron_migration_routing_visible = (
        bool(cron_migration_opportunity)
        or bool(cron_migration_followups)
        or bool(cron_repair_plan_active)
    )
    cron_migration_active_visible = cron_migration_routing_visible and blocked_or_escalated_cron_count > 0
    cron_migration_residue_visible = (
        (bool(cron_migration_opportunity) or bool(cron_migration_followups) or bool(cron_repair_plan))
        and not cron_migration_active_visible
    )
    improvement_summary = as_dict(improvement_ledger.get("summary"))
    owner_gated_summary = as_dict(owner_gated.get("summary"))
    token_summary = as_dict(token_usage.get("summary"))
    model_summary = as_dict(model_run.get("summary"))
    finance_summary = as_dict(finance.get("summary"))
    duplication_summary = as_dict(duplication_audit.get("summary"))
    collection_validation_data = as_dict(collection.get("validation"))
    learning_environment = as_dict(collection_summary.get("learning_environment_status"))
    improvement_freshness = freshness_state(
        improvement_ledger.get("generated_at_utc"),
        now,
        ARTIFACT_MAX_AGE_HOURS.get("improvement_ledger"),
    )
    fallback_needed = not improvement_ledger or bool(improvement_freshness.get("stale"))
    fallback = improvement_ledger_history_fallback(now) if fallback_needed else {}
    effective_improvement = fallback if fallback_needed and fallback.get("history_row_count") else improvement_summary
    collection_validation = collection_validation_data.get("status")
    improvement_escalation_level = (
        "history_fallback_high_priority_overdue"
        if fallback_needed and int(effective_improvement.get("high_priority_overdue_open_count") or 0)
        else improvement_summary.get("escalation_level")
    )
    collection_warning_routed_by_improvement_ledger = (
        collection.get("status") == "ok"
        and collection_validation == "warning"
        and int(collection_validation_data.get("critical") or 0) == 0
        and int(collection_summary.get("steps_blocked") or 0) == 0
        and improvement_escalation_level == "high_priority_overdue"
    )
    collection_warning_routed_by_quality_gate = (
        collection.get("status") == "ok"
        and collection_validation == "warning"
        and int(collection_validation_data.get("critical") or 0) == 0
        and int(collection_summary.get("steps_blocked") or 0) == 0
        and learning_environment.get("quality_gate_status") == "blocked"
        and bool(as_list(learning_environment.get("blocked_quality_gates")))
    )
    collection_warning_routed_by_nonblocking_residue = (
        collection.get("status") == "ok"
        and collection_validation == "warning"
        and int(collection_validation_data.get("critical") or 0) == 0
        and int(collection_summary.get("steps_blocked") or 0) == 0
        and not collection_warning_routed_by_improvement_ledger
        and not collection_warning_routed_by_quality_gate
    )
    return {
        "collection_status": collection.get("status"),
        "collection_validation": collection_validation,
        "opportunity_queue_status": opportunity_queue.get("status"),
        "opportunity_queue_validation": as_dict(opportunity_queue.get("validation")).get("status"),
        "wf74_opportunity_count": opportunity_summary.get("opportunity_count"),
        "wf74_high_priority_opportunity_count": opportunity_summary.get("high_priority_count"),
        "wf74_top_opportunity_title": opportunity_summary.get("top_opportunity_title"),
        "wf74_top_opportunity_id": opportunity_summary.get("top_opportunity_id"),
        "auto_patch_status": auto_patch.get("status"),
        "auto_patch_validation": as_dict(auto_patch.get("validation")).get("status"),
        "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
        "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count"),
        "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
        "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
        "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
        "decision_docket_status": decision_docket.get("status"),
        "decision_docket_validation": as_dict(decision_docket.get("validation")).get("status"),
        "decision_docket_row_count": docket_summary.get("row_count"),
        "decision_docket_active_action_count": docket_summary.get("active_action_count"),
        "decision_docket_fix_now_count": docket_summary.get("fix_now_count"),
        "decision_docket_owner_decision_count": docket_summary.get("owner_decision_count"),
        "decision_docket_market_session_accrual_count": docket_summary.get("market_session_accrual_count"),
        "decision_docket_monitor_only_count": docket_summary.get("monitor_only_count"),
        "decision_docket_hard_stop_count": docket_summary.get("hard_stop_count"),
        "decision_docket_next_safe_action": docket_summary.get("next_safe_action"),
        "cron_blocked_or_escalated_count": blocked_or_escalated_cron_count,
        "cron_migration_repair_visible": cron_migration_active_visible,
        "cron_migration_residue_visible": cron_migration_residue_visible,
        "cron_migration_repair_plan_active": cron_repair_plan_active,
        "cron_migration_repair_plan_status": cron_repair_plan.get("status"),
        "cron_migration_repair_priority": cron_migration_opportunity.get("priority"),
        "cron_migration_repair_gate": cron_migration_opportunity.get("proposal_gate"),
        "cron_migration_repair_followup_count": len(cron_migration_followups),
        "workflow_blocker_followup_visible": bool(workflow_blocker_opportunity),
        "workflow_blocker_followup_priority": workflow_blocker_opportunity.get("priority"),
        "workflow_blocker_followup_gate": workflow_blocker_opportunity.get("proposal_gate"),
        "workflow_blocker_followup_count": followup_summary.get("followup_count"),
        "workflow_blocker_followup_route_counts": followup_summary.get("route_counts"),
        "startup_pickup_items": [
            {
                "title": "WF74 V2 decision docket",
                "priority": None,
                "visible": int(docket_summary.get("active_action_count") or 0) > 0,
                "followup_count": docket_summary.get("row_count"),
                "next_action": docket_summary.get("next_safe_action"),
                "command": "python scripts\\wf74_decision_docket.py --write --validate",
            },
            {
                "title": CRON_MIGRATION_REPAIR_TITLE,
                "priority": cron_migration_opportunity.get("priority"),
                "visible": cron_migration_active_visible,
                "residue_visible": cron_migration_residue_visible,
                "followup_count": len(cron_migration_followups),
                "next_action": "Run main_session_greenkeeper_controller; inspect cron migration followup before any cron schedule/state mutation.",
                "command": "python scripts\\main_session_greenkeeper_controller.py --refresh-frontdoors --execute-safe --write --validate --append-ledger",
            },
            {
                "title": WORKFLOW_BLOCKER_FOLLOWUP_TITLE,
                "priority": workflow_blocker_opportunity.get("priority"),
                "visible": bool(workflow_blocker_opportunity),
                "followup_count": len(workflow_blocker_followups),
                "next_action": "Use workflow-blocker followup rows to open scoped implementation or maturity lanes.",
                "command": "python scripts\\workflow_advancement_scorecard.py --write --validate",
            },
        ],
        "collection_warning_routed_by_improvement_ledger": collection_warning_routed_by_improvement_ledger,
        "collection_warning_routed_by_quality_gate": collection_warning_routed_by_quality_gate,
        "collection_warning_routed_by_nonblocking_residue": collection_warning_routed_by_nonblocking_residue,
        "collection_validation_routed_reason": (
            "collection warning is duplicate wrapper residue from the improvement ledger high-priority overdue row"
            if collection_warning_routed_by_improvement_ledger
            else (
                "collection passed all steps; warning is an explicit blocked durable quality gate"
                if collection_warning_routed_by_quality_gate
                else (
                    "collection passed all steps; remaining warning is nonblocking maturity/visibility residue"
                    if collection_warning_routed_by_nonblocking_residue else None
                )
            )
        ),
        "collection_quality_gate_status": learning_environment.get("quality_gate_status"),
        "collection_blocked_quality_gates": as_list(learning_environment.get("blocked_quality_gates")),
        "steps_ok": collection_summary.get("steps_ok"),
        "steps_blocked": collection_summary.get("steps_blocked"),
        "improvement_ledger_status": improvement_ledger.get("status"),
        "improvement_ledger_validation": as_dict(improvement_ledger.get("validation")).get("status"),
        "improvement_ledger_current_freshness": improvement_freshness,
        "improvement_ledger_fallback_used": fallback_needed and bool(fallback.get("history_row_count")),
        "improvement_ledger_fallback_source": fallback.get("source"),
        "improvement_ledger_fallback_history_rows": fallback.get("history_row_count"),
        "improvement_ledger_rows": improvement_summary.get("ledger_row_count"),
        "improvement_open_count": improvement_summary.get("latest_open_count"),
        "improvement_effective_open_count": effective_improvement.get("latest_open_count"),
        "improvement_effective_closed_count": effective_improvement.get("latest_closed_count"),
        "improvement_high_priority_open_count": improvement_summary.get("high_priority_open_count"),
        "improvement_overdue_open_count": improvement_summary.get("overdue_open_count"),
        "improvement_due_soon_open_count": improvement_summary.get("due_soon_open_count"),
        "improvement_high_priority_overdue_open_count": improvement_summary.get("high_priority_overdue_open_count"),
        "improvement_effective_high_priority_overdue_open_count": effective_improvement.get("high_priority_overdue_open_count"),
        "improvement_effective_anti_theater_status": effective_improvement.get("anti_theater_status"),
        "improvement_escalation_level": improvement_escalation_level,
        "improvement_top_title": effective_improvement.get("top_improvement_title"),
        "improvement_top_next_action": effective_improvement.get("top_improvement_next_action"),
        "improvement_top_age_hours": effective_improvement.get("top_improvement_age_hours"),
        "improvement_top_sla_status": effective_improvement.get("top_improvement_sla_status"),
        "owner_gated_review_status": owner_gated.get("status"),
        "owner_gated_review_validation": as_dict(owner_gated.get("validation")).get("status"),
        "owner_gated_item_count": owner_gated_summary.get("item_count"),
        "owner_gated_decision_required_count": owner_gated_summary.get("owner_decision_required_count"),
        "owner_gated_top_gate": owner_gated_summary.get("top_gate"),
        "owner_gated_top_title": owner_gated_summary.get("top_title"),
        "owner_gated_next_safe_action": owner_gated_summary.get("next_safe_action"),
        "token_usage_status": token_usage.get("status"),
        "token_usage_validation": as_dict(token_usage.get("validation")).get("status"),
        "token_usage_event_count": token_summary.get("token_event_count"),
        "token_usage_total_tokens": token_summary.get("total_tokens"),
        "token_usage_cron_event_count": token_summary.get("cron_token_event_count"),
        "token_usage_implementation_event_count": token_summary.get("implementation_token_event_count"),
        "token_usage_implementation_gap_count": token_summary.get("implementation_token_gap_count"),
        "token_usage_pricing_status": token_summary.get("pricing_status"),
        "model_run_rows": model_summary.get("row_count"),
        "model_attribution_coverage": model_summary.get("model_attribution_coverage"),
        "session_attribution_coverage": model_summary.get("session_attribution_coverage"),
        "finance_correctness_rows": finance_summary.get("row_count"),
        "finance_ok_rows": finance_summary.get("ok_count"),
        "finance_warning_rows": finance_summary.get("warning_count"),
        "finance_blocked_rows": finance_summary.get("blocked_count"),
        "scorecard_validation": as_dict(scorecard.get("validation")).get("status"),
        "cron_duplication_status": duplication_audit.get("status"),
        "cron_duplication_validation": as_dict(duplication_audit.get("validation")).get("status"),
        "cron_owner_job_matches": duplication_summary.get("owner_job_matches"),
        "cron_component_collectors_outside_owner": duplication_summary.get("recurring_component_collectors_outside_owner_count"),
        "cron_one_shot_component_reminders": duplication_summary.get("one_shot_component_collectors_outside_owner_count"),
        "active_tracks": scorecard.get("active_tracks"),
        "blocked_claims": [
            "model ranking until repeated attributed samples and WF55 graded outcome history exist",
            "investment correctness from OTEL/runtime/validator success",
            "WF55 later outcome grading outside the WF55 gated process",
        ],
    }


def recommended_routes() -> list[dict[str, Any]]:
    return [
        {
            "use_case": "WF88 wiki synthesis / second-brain route",
            "command": "python scripts\\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate",
        },
        {
            "use_case": "WF88 wiki bootstrap proof",
            "command": "python scripts\\wiki_bootstrap_validator.py --write --validate",
        },
        {
            "use_case": "new session or post-compaction startup",
            "command": "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
        },
        {
            "use_case": "named workflow pickup",
            "command": "python scripts\\workflow_router.py WF## --answer all",
        },
        {
            "use_case": "PM queue and next action",
            "command": "python scripts\\pm_control_packet.py --write --write-db --validate",
        },
        {
            "use_case": "main-session automatic PM/cron pickup",
            "command": "python scripts\\main_session_action_executor.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger",
        },
        {
            "use_case": "WF74 blocked cron and workflow blocker pickup",
            "command": "python scripts\\main_session_greenkeeper_controller.py --refresh-frontdoors --execute-safe --write --validate --append-ledger",
        },
        {
            "use_case": "direct cron escalation consumption",
            "command": "python scripts\\main_session_escalation_consumer.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger",
        },
        {
            "use_case": "cron/autonomy trust",
            "command": "python scripts\\cron_control_packet.py --write --validate",
        },
        {
            "use_case": "model/run/finance-quality evidence",
            "command": "python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness",
        },
        {
            "use_case": "actionable improvement queue",
            "command": "python scripts\\actionable_improvement_queue.py --write --write-md --validate",
        },
        {
            "use_case": "no orphaned open improvement rows",
            "command": "python scripts\\no_orphan_validator.py --write --validate",
        },
        {
            "use_case": "refresh current improvement packet without appending durable history",
            "command": "python scripts\\improvement_ledger.py --check --write --write-md --validate",
        },
        {
            "use_case": "owner-gated approval/recommendation queue",
            "command": "python scripts\\owner_gated_action_review_queue.py --write --write-md --validate",
        },
        {
            "use_case": "rank cron and implementation token usage",
            "command": "python scripts\\token_usage_ledger.py --write --write-md --validate",
        },
        {
            "use_case": "WF74 cron duplicate collector audit",
            "command": "python scripts\\wf74_cron_duplication_audit.py --write --validate",
        },
        {
            "use_case": "local eval/training candidate review",
            "command": "python scripts\\training_dataset_candidate_builder.py --write --write-md --validate",
        },
        {
            "use_case": "changed-file validator choice",
            "command": "python scripts\\changed_file_validator_router.py --write --validate",
        },
        {
            "use_case": "finance/SaaS warning caveat classification",
            "command": "python scripts\\finance_evidence_warning_router.py --write --validate",
        },
    ]


def extract_wf88_wiki_synthesis() -> dict[str, Any]:
    packet = as_dict(load_json_artifact(TMP / "wf88-wiki-synthesis-packet.json"))
    summary = as_dict(packet.get("summary"))
    leak = as_dict(packet.get("recommendation_leak_guard"))
    validation = as_dict(packet.get("validation"))
    return {
        "present": bool(packet),
        "status": packet.get("status"),
        "validation_status": validation.get("status"),
        "wiki_page_count": summary.get("wiki_page_count"),
        "self_prompt_count": summary.get("self_prompt_count"),
        "action_item_count": len(as_list(packet.get("action_items"))),
        "recommendation_leak_guard_pass": leak.get("pass"),
        "open_unrouted_recommendation_count": leak.get("open_unrouted_recommendation_count"),
        "auto_apply_count": leak.get("auto_apply_count"),
        "rsi_status": summary.get("rsi_status"),
        "followup_required_open_count": summary.get("followup_required_open_count"),
        "recommendation_later_outcome_graded_rows": summary.get("recommendation_later_outcome_graded_rows"),
        "next_safe_action": "Run WF88 wiki synthesis after material WF88/WF74/PM/OTEL changes; route its warnings through WF74/PM rather than leaving them in chat.",
    }


def extract_wiki_bootstrap_proof() -> dict[str, Any]:
    packet = as_dict(load_json_artifact(TMP / "wiki-bootstrap-proof.json"))
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    return {
        "present": bool(packet),
        "schema": packet.get("schema"),
        "semantic_contract_schema": as_dict(packet.get("semantic_contract")).get("schema"),
        "status": packet.get("status"),
        "validation_status": validation.get("status"),
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


def extract_coding_outcome_efficiency() -> dict[str, Any]:
    packet = as_dict(load_json_artifact(TMP / "coding-outcome-ledger-current.json"))
    summary = as_dict(packet.get("ledger_summary"))
    gate = as_dict(summary.get("comparable_cohort_sample_gate"))
    return {
        "present": bool(packet),
        "status": packet.get("status"),
        "validation_status": as_dict(packet.get("validation")).get("status"),
        "ledger_row_count": summary.get("ledger_row_count"),
        "route_conformant_count": summary.get("route_conformant_count"),
        "route_mismatch_count": summary.get("route_mismatch_count"),
        "incident_row_count": summary.get("incident_row_count"),
        "invalid_token_integrity_row_count": summary.get("invalid_token_integrity_row_count"),
        "main_accepted_count": summary.get("main_accepted_count"),
        "total_retry_count": summary.get("total_retry_count"),
        "comparable_cohort_count": len(as_dict(summary.get("comparable_cohorts"))),
        "minimum_comparable_main_accepted_jobs": gate.get("required_accepted_count"),
        "eligible_cohort_count": gate.get("eligible_cohort_count"),
        "automatic_ranking_or_promotion_active": gate.get("route_ranking_or_promotion_before_gate"),
        "truth_limit": "Prospective route evidence only; incidents, invalid telemetry, and unavailable actual-route fields receive no efficiency success credit.",
    }


def extract_actionability_summary() -> dict[str, Any]:
    queue = as_dict(load_json_artifact(TMP / "actionable-improvement-queue.json"))
    validator = as_dict(load_json_artifact(TMP / "no-orphan-validator.json"))
    queue_summary = as_dict(queue.get("summary"))
    validator_summary = as_dict(validator.get("summary"))
    return {
        "present": bool(queue),
        "queue_status": queue.get("status"),
        "queue_validation_status": as_dict(queue.get("validation")).get("status"),
        "action_item_count": queue_summary.get("action_item_count"),
        "orphan_count": queue_summary.get("orphan_count"),
        "missing_contract_count": queue_summary.get("missing_contract_count"),
        "owner_decision_count": queue_summary.get("owner_decision_count"),
        "hard_stop_count": queue_summary.get("hard_stop_count"),
        "monitor_only_count": queue_summary.get("monitor_only_count"),
        "top_action_title": queue_summary.get("top_action_title"),
        "top_action_destination": queue_summary.get("top_action_destination"),
        "top_next_action": queue_summary.get("top_next_action"),
        "no_orphan_status": validator.get("status"),
        "no_orphan_validation_status": as_dict(validator.get("validation")).get("status"),
        "no_orphan_validation_passed": validator_summary.get("validation_passed"),
        "next_safe_action": "Open tmp/actionable-improvement-queue.json before treating Improvement Ledger rows as handled.",
    }


def resume_validation_is_eligible(status: Any) -> bool:
    return status == "ok"


def extract_interruption_recovery_summary(now: datetime | None = None) -> dict[str, Any]:
    lane_register = as_dict(load_json_artifact(TMP / "concurrent-lane-register.json"))
    current_resume = as_dict(load_json_artifact(TMP / "current-resume.json"))
    compact_active_lanes = as_dict(load_json_artifact(TMP / "current-active-lanes.json"))
    release_contract = as_dict(load_json_artifact(TMP / "implementation-release-contract.json"))
    closeout_bundle = as_dict(load_json_artifact(TMP / "control-closeout-bundle.json"))
    validator_bundle = as_dict(load_json_artifact(TMP / "validator-bundle-router.json"))
    current_time = now or datetime.now(timezone.utc)
    lane_projection = resume_checkpoint.project_active_lanes(lane_register, current_time)
    projected_current_lane = as_dict(lane_projection.get("current_lane"))
    resume_lane_id = current_resume.get("lane_id")
    resume_bound_lane = next(
        (
            as_dict(item)
            for item in as_list(lane_projection.get("active_lanes"))
            if as_dict(item).get("lane_id") == resume_lane_id
        ),
        {},
    )
    projection_validation = as_dict(lane_projection.get("validation"))
    evaluated_resume: dict[str, Any] = {}
    if current_resume:
        evaluated_resume = resume_checkpoint.rebind_live_lease(
            current_resume,
            lane_projection,
            current_time,
            root=ROOT,
        )
    resume_validation = as_dict(evaluated_resume.get("validation"))
    resume_ack = as_dict(evaluated_resume.get("resume_acknowledgement"))
    resume_receipt = as_dict(evaluated_resume.get("execution_receipt"))
    resume_gate = as_dict(evaluated_resume.get("execution_gate"))
    active_lane_count = int(lane_projection.get("active_lane_count") or 0)
    projection_resolution = lane_projection.get("resolution")
    resume_source_kind = as_dict(evaluated_resume.get("source")).get("kind")
    resume_valid = bool(
        evaluated_resume
        and resume_validation_is_eligible(resume_validation.get("status"))
    )
    resume_bound_current = bool(
        resume_bound_lane
        and resume_bound_lane.get("lease_current") is True
    )
    source_can_select = bool(
        projection_resolution == "single"
        or (
            projection_resolution == "blocked_ambiguous"
            and resume_source_kind == "explicit_checkpoint"
        )
    )
    resume_status = evaluated_resume.get("resume_status")
    receipt_consumed = resume_gate.get("execution_receipt_consumed") is True
    replay_blocked = resume_gate.get("replay_blocked") is True
    eligible_resume_target = bool(
        active_lane_count > 0
        and resume_valid
        and resume_bound_current
        and source_can_select
        and resume_status in {"ready", "blocked"}
        and not receipt_consumed
        and not replay_blocked
    )
    historical_only = bool(current_resume and active_lane_count == 0)
    if projection_resolution == "single":
        current_lane = projected_current_lane
    elif projection_resolution == "blocked_ambiguous" and eligible_resume_target:
        current_lane = resume_bound_lane
    else:
        current_lane = {}
    resume_target = evaluated_resume if eligible_resume_target else {}
    release_summary = as_dict(release_contract.get("summary"))
    closeout_summary = as_dict(closeout_bundle.get("summary"))
    validator_summary = as_dict(validator_bundle.get("summary"))
    validator_proof = as_dict(validator_bundle.get("proof_interpretation"))
    return {
        "schema": "veritas.interruption_recovery_summary.v1",
        "purpose": "Resume interrupted implementation from durable lane/release/proof state instead of asking Randall to resend context.",
        "resume_checkpoint": {
            "present": bool(current_resume),
            "schema": current_resume.get("schema"),
            "source_kind": resume_source_kind,
            "target_eligible": eligible_resume_target,
            "historical_only": historical_only,
            "status": resume_target.get("resume_status") or (
                "historical_only" if historical_only else (
                    "consumed_awaiting_successor" if receipt_consumed or replay_blocked else (
                        "blocked" if current_resume else None
                    )
                )
            ),
            "validation_status": resume_validation.get("status"),
            "validation_findings": resume_validation.get("findings"),
            "checkpoint_id": evaluated_resume.get("checkpoint_id"),
            "checkpoint_sequence": evaluated_resume.get("checkpoint_sequence"),
            "historical_lane_id": evaluated_resume.get("lane_id") if not eligible_resume_target else None,
            "workflow_id": resume_target.get("workflow_id"),
            "lane_id": resume_target.get("lane_id"),
            "workstream": resume_target.get("workstream"),
            "last_completed_step": resume_target.get("last_completed_step"),
            "in_progress_step": resume_target.get("in_progress_step"),
            "exact_next_action": resume_target.get("exact_next_action"),
            "exact_next_command": resume_target.get("exact_next_command"),
            "already_completed_do_not_repeat": resume_target.get("already_completed_do_not_repeat"),
            "freshness_expiry": evaluated_resume.get("freshness_expiry"),
            "acknowledgement_status": resume_ack.get("status"),
            "execution_receipt_status": resume_receipt.get("status"),
            "execution_receipt_checkpoint_id": resume_receipt.get("checkpoint_id"),
            "execution_receipt_at_utc": resume_receipt.get("executed_at_utc"),
            "already_completed_denylist_match": resume_gate.get("already_completed_denylist_match"),
            "execution_receipt_consumed": resume_gate.get("execution_receipt_consumed"),
            "replay_blocked": resume_gate.get("replay_blocked"),
            "command_authorized": bool(
                eligible_resume_target and resume_gate.get("command_authorized") is True
            ),
            "safe_to_execute_automatically": bool(
                eligible_resume_target
                and resume_gate.get("safe_to_execute_automatically") is True
            ),
            "blocker": resume_target.get("blocker"),
        },
        "compact_active_lanes": {
            "present": bool(compact_active_lanes),
            "schema": compact_active_lanes.get("schema"),
            "status": compact_active_lanes.get("status"),
            "validation_status": as_dict(compact_active_lanes.get("validation")).get("status"),
            "active_lane_count": compact_active_lanes.get("active_lane_count"),
            "resolution": compact_active_lanes.get("resolution"),
        },
        "lane_register": {
            "present": bool(lane_register),
            "status": lane_register.get("status"),
            "validation_status": as_dict(lane_register.get("validation")).get("status"),
            "projection_validation_status": projection_validation.get("status"),
            "active_lane_count": lane_projection.get("active_lane_count"),
            "projected_lane_count": lane_projection.get("projected_lane_count"),
            "resolution": lane_projection.get("resolution"),
            "blocking_reasons": lane_projection.get("blocking_reasons"),
            "active_lane_ids": [
                as_dict(item).get("lane_id") for item in as_list(lane_projection.get("active_lanes"))
            ],
            "stale_lease_count": sum(
                1 for item in as_list(lane_projection.get("active_lanes"))
                if as_dict(item).get("lease_current") is not True
            ),
            "current_lane_id": current_lane.get("lane_id"),
            "current_lane_status": current_lane.get("status"),
            "current_lane_owner": current_lane.get("owner"),
            "current_workstream": current_lane.get("workstream"),
            "current_next_action": current_lane.get("next_action"),
            "current_exact_next_command": current_lane.get("exact_next_command"),
            "updated_at_utc": current_lane.get("updated_at_utc"),
        },
        "release_contract": {
            "present": bool(release_contract),
            "status": release_contract.get("status"),
            "validation_status": as_dict(release_contract.get("validation")).get("status"),
            "ready_to_close": release_summary.get("ready_to_close"),
            "missing_gate_count": release_summary.get("missing_gate_count"),
            "unknown_warning_count": release_summary.get("unknown_warning_count"),
            "blocking_warning_count": release_summary.get("blocking_warning_count"),
        },
        "control_closeout": {
            "present": bool(closeout_bundle),
            "status": closeout_bundle.get("status"),
            "validation_status": as_dict(closeout_bundle.get("validation")).get("status"),
            "failed_step_count": closeout_summary.get("failed_step_count"),
            "warning_count": closeout_summary.get("warning_count"),
        },
        "validator_bundle": {
            "present": bool(validator_bundle),
            "status": validator_bundle.get("status"),
            "mode": validator_bundle.get("mode"),
            "proof_mode": validator_proof.get("proof_mode"),
            "proof_claim": validator_proof.get("proof_claim"),
            "safe_summary": validator_proof.get("safe_summary"),
            "selected_command_count": validator_summary.get("selected_command_count"),
            "executed_command_count": validator_summary.get("executed_command_count"),
            "failed_command_count": validator_summary.get("failed_command_count"),
        },
        "pickup_order": [
            "tmp/current-resume.json",
            "tmp/current-active-lanes.json",
            "tmp/concurrent-lane-register.json",
            "tmp/implementation-release-contract.json",
            "tmp/control-closeout-bundle.json",
            "tmp/validator-bundle-router.json",
            "memory/YYYY-MM-DD.md",
        ],
        "next_safe_action": "Validate and acknowledge current-resume.json first. Execute only its exact command when command_authorized=true; otherwise stop on its blocker before consulting lower-precedence routes.",
    }


def build_payload(
    now: datetime,
    *,
    out: Path = OUT,
    input_signature: dict[str, Any] | None = None,
    prefilter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = utc_now()
    generated_dt = parse_utc(generated_at) or datetime.now(timezone.utc)
    expires_dt = generated_dt + timedelta(hours=PACKET_MAX_STARTUP_AGE_HOURS)
    signature = input_signature or build_input_signature(now)
    prefilter_state = prefilter or prefilter_decision(out, now, signature)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "ok",
        "posture": "future_session_startup_routing_packet",
        "packet_freshness": {
            "max_startup_age_hours": PACKET_MAX_STARTUP_AGE_HOURS,
            "expires_at_utc": expires_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "meaning": "Regenerate this packet before use after expires_at_utc or when material PM/cron/WF74 inputs changed.",
        },
        "input_signature": signature,
        "prefilter": {
            **prefilter_state,
            "meaning": "Changed-input prefilter for command/runtime wrappers. Reuse is allowed only when sources are unchanged and the existing packet is still inside the startup freshness window.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "core_surfaces": [file_state(path) for path in CORE_SURFACES],
        "daily_memory_surfaces": daily_memory_surfaces(now),
        "artifacts": [artifact_state(label, path, now) for label, path in ARTIFACTS.items()],
        "derived_files": [
            file_state(path) | {
                "label": label,
                "freshness": freshness_state(file_state(path).get("modified_utc"), now, DERIVED_FILE_MAX_AGE_HOURS.get(label)),
            }
            for label, path in DERIVED_FILES.items()
        ],
        "workflow_capsules": workflow_capsules(),
        "pm_summary": extract_pm_summary(),
        "cron_summary": extract_cron_summary(),
        "otel_carry_forward": extract_otel_carry_forward(now),
        "main_session_escalation_consumer_summary": extract_escalation_consumer_summary(),
        "main_session_action_executor_summary": extract_action_executor_summary(),
        "finance_evidence_warning_router_summary": extract_finance_warning_router_summary(),
        "wf88_wiki_synthesis": extract_wf88_wiki_synthesis(),
        "wiki_bootstrap_proof": extract_wiki_bootstrap_proof(),
        "execution_efficiency_policy": implementation_router.execution_efficiency_policy(),
        "coding_outcome_efficiency": extract_coding_outcome_efficiency(),
        "actionability_summary": extract_actionability_summary(),
        "interruption_recovery": extract_interruption_recovery_summary(now),
        "wf74_summary": extract_wf74_summary(now),
        "recommended_routes": recommended_routes(),
        "challenger_model_policy": CHALLENGER_MODEL_POLICY.copy(),
        "rsi_observation": {
            "schema": "wf74.rsi_observation.v1",
            "source": "future_session_enhancement_packet",
            "lesson_type": "daily_context",
            "owner_surface": "Startup Truth Index / TOOLS.md / WF74",
            "what_changed": "Future-session startup context was compressed into one packet with PM, cron, WF74, workflow, memory, route, and stop-line state.",
            "warnings_or_blockers": [],
            "future_session_lesson": "Open this packet first after compaction/new-session handoff, then drill into exact owner artifacts only for the active request.",
            "recommended_destination": "memory/YYYY-MM-DD.md for daily deltas; promote only repeated startup failures to skill or TOOLS.md.",
            "actionability": "use_as_startup_route",
        },
        "next_safe_action": "Open this packet first, then drill into exact owner artifacts only for the active request.",
        "stop_lines": [
            "Generated packets route proof; they are not canon or approval.",
            "Do not infer owner approval, portfolio/canon mutation, capital deployment, or paper/live/account authority.",
            "Model-quality evidence is review-only until sample depth, attribution, and WF55 graded outcomes support stronger claims.",
            "For serious finance workflow gates, Opus challenger acceptance requires verified model path claude-cli/claude-opus-4-8; label text alone is not proof.",
            "Do not dispatch material implementation when the versioned efficiency policy is missing or malformed; shallow status remains available.",
        ],
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload


def classify_findings(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    current_task_markers = (
        "resume ",
        "resume checkpoint",
        "current lane",
        "active lane",
    )
    stale_markers = (
        "stale artifact",
        "stale derived file",
        "missing artifact",
        "missing daily memory surface",
        " is stale",
    )
    classified: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for finding in findings:
        row = dict(finding)
        detail = str(row.get("detail") or "").lower()
        severity = row.get("severity")
        if any(marker in detail for marker in current_task_markers):
            category = "current_task_blocker" if severity == "critical" else "current_task_warning"
            priority = "P0" if severity == "critical" else "P1"
        elif severity == "warning" and any(marker in detail for marker in stale_markers):
            category = "stale_informational"
            priority = "P3"
        elif severity == "critical":
            category = "global_blocker"
            priority = "P0"
        else:
            category = "unrelated_global_warning"
            priority = "P2"
        row["category"] = row.get("category") or category
        row["priority"] = row.get("priority") or priority
        counts[row["category"]] = counts.get(row["category"], 0) + 1
        classified.append(row)
    return classified, counts


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    missing_core = [item["path"] for item in payload.get("core_surfaces", []) if not item.get("exists")]
    for path in missing_core:
        findings.append({"severity": "critical", "detail": f"missing core surface: {path}"})
    for item in payload.get("core_surfaces", []):
        for marker in as_list(as_dict(item).get("missing_efficiency_markers")):
            findings.append({"severity": "critical", "detail": f"missing efficiency marker: {item.get('path')}:{marker}"})
    efficiency_policy = as_dict(payload.get("execution_efficiency_policy"))
    canonical_efficiency_policy = implementation_router.execution_efficiency_policy()
    if efficiency_policy != canonical_efficiency_policy:
        findings.append({"severity": "critical", "detail": "execution efficiency policy does not exactly match its router owner"})
    route_order = [as_dict(row).get("execution_backend") for row in as_list(efficiency_policy.get("route_order"))]
    if route_order != ["model_free_command", "codex_native_subagent", "main", "persistent_isolated_agent"]:
        findings.append({"severity": "critical", "detail": "execution efficiency route order mismatch"})
    quality = as_dict(efficiency_policy.get("quality_weighted_efficiency"))
    if quality.get("minimum_comparable_main_accepted_jobs") != 10:
        findings.append({"severity": "critical", "detail": "execution efficiency cohort gate mismatch"})
    if quality.get("automatic_route_ranking_allowed") is not False or quality.get("automatic_route_promotion_allowed") is not False:
        findings.append({"severity": "critical", "detail": "automatic route ranking or promotion must remain disabled"})
    outcome_efficiency = as_dict(payload.get("coding_outcome_efficiency"))
    if not outcome_efficiency.get("present"):
        findings.append({"severity": "warning", "detail": "coding outcome efficiency packet is missing"})
    elif outcome_efficiency.get("automatic_ranking_or_promotion_active") is not False:
        findings.append({"severity": "critical", "detail": "coding outcome ledger reports premature route ranking or promotion"})
    missing_memory = [item["path"] for item in payload.get("daily_memory_surfaces", []) if not item.get("exists")]
    for path in missing_memory:
        findings.append({"severity": "warning", "detail": f"missing daily memory surface: {path}"})
    for artifact in payload.get("artifacts", []):
        if not artifact.get("exists"):
            findings.append({"severity": "warning", "detail": f"missing artifact: {artifact.get('path')}"})
        freshness = as_dict(artifact.get("freshness"))
        if freshness.get("stale"):
            is_current_resume_state = artifact.get("label") in {"current_resume", "current_active_lanes"}
            findings.append({
                "severity": "warning",
                "category": "current_task_warning" if is_current_resume_state else "stale_informational",
                "priority": "P1" if is_current_resume_state else "P3",
                "detail": (
                    f"stale artifact: {artifact.get('path')} age_hours={freshness.get('age_hours')} "
                    f"max_age_hours={freshness.get('max_age_hours')}"
                ),
            })
    for derived in payload.get("derived_files", []):
        freshness = as_dict(derived.get("freshness"))
        if freshness.get("stale"):
            findings.append({
                "severity": "warning",
                "detail": (
                    f"stale derived file: {derived.get('path')} age_hours={freshness.get('age_hours')} "
                    f"max_age_hours={freshness.get('max_age_hours')}"
                ),
            })
    wf74 = as_dict(payload.get("wf74_summary"))
    otel = as_dict(payload.get("otel_carry_forward"))
    if otel:
        if not otel.get("present"):
            findings.append({"severity": "warning", "detail": "OTEL learning loop carry-forward packet is missing"})
        if as_dict(otel.get("freshness")).get("stale"):
            findings.append({"severity": "warning", "detail": "OTEL learning loop carry-forward packet is stale"})
        if otel.get("validation_status") in {"blocked", "critical", "error"}:
            findings.append({"severity": "critical", "detail": "OTEL learning loop validation is blocked"})
        if otel.get("auto_apply_allowed") is not False:
            findings.append({"severity": "critical", "detail": "OTEL carry-forward must keep auto-apply disabled"})
    collection_warning_routed = (
        wf74.get("collection_warning_routed_by_improvement_ledger")
        or wf74.get("collection_warning_routed_by_quality_gate")
        or wf74.get("collection_warning_routed_by_nonblocking_residue")
    )
    if wf74.get("collection_validation") not in {None, "ok"} and not collection_warning_routed:
        findings.append({"severity": "warning", "detail": "WF74 collection validation is not ok"})
    if wf74.get("opportunity_queue_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 opportunity queue validation is not ok"})
    if wf74.get("auto_patch_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 auto-patch proposer validation is not ok"})
    if wf74.get("decision_docket_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 decision docket validation is not ok"})
    if int(wf74.get("decision_docket_hard_stop_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 decision docket contains hard-stop items"})
    if int(wf74.get("auto_patch_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 auto-patch proposer must not auto-apply"})
    if int(wf74.get("cron_blocked_or_escalated_count") or 0) and not wf74.get("cron_migration_repair_visible"):
        findings.append({
            "severity": "critical",
            "detail": "blocked or escalated cron signals are not routed to the WF74 cron migration repair plan",
        })
    if wf74.get("cron_migration_repair_visible") and int(wf74.get("cron_migration_repair_followup_count") or 0) == 0:
        findings.append({
            "severity": "warning",
            "detail": "WF74 cron migration repair plan is visible but has no workflow followup row yet",
        })
    if wf74.get("workflow_blocker_followup_visible") and int(wf74.get("workflow_blocker_followup_count") or 0) == 0:
        findings.append({
            "severity": "critical",
            "detail": "WF74 workflow blocker opportunity is visible but workflow-blocker followups are missing",
        })
    if wf74.get("collection_warning_routed_by_quality_gate"):
        blocked_gates = ", ".join(str(item) for item in as_list(wf74.get("collection_blocked_quality_gates"))) or "unknown"
        findings.append({
            "severity": "warning",
            "detail": f"WF74 collection passed; quality gate remains blocked: {blocked_gates}",
        })
    if wf74.get("improvement_ledger_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "improvement ledger validation is not ok"})
    if as_dict(wf74.get("improvement_ledger_current_freshness")).get("stale") and not wf74.get("improvement_ledger_fallback_used"):
        findings.append({"severity": "critical", "detail": "stale improvement ledger current packet without JSONL fallback"})
    if wf74.get("improvement_ledger_fallback_used"):
        findings.append({"severity": "warning", "detail": "improvement ledger current packet stale; JSONL fallback used"})
    if wf74.get("improvement_escalation_level") in {"high_priority_overdue", "history_fallback_high_priority_overdue"}:
        findings.append({"severity": "warning", "detail": "high-priority improvement is overdue"})
    if wf74.get("owner_gated_review_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "owner-gated action review queue validation is not ok"})
    if wf74.get("token_usage_validation") == "critical":
        findings.append({"severity": "warning", "detail": "token usage ledger validation is critical"})
    if wf74.get("cron_duplication_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 cron duplication audit validation is not ok"})
    if wf74.get("cron_component_collectors_outside_owner") not in {0, None}:
        findings.append({"severity": "critical", "detail": "WF74 cron component collectors found outside owner job"})
    escalation_consumer = as_dict(payload.get("main_session_escalation_consumer_summary"))
    if escalation_consumer.get("validation_status") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "main-session escalation consumer validation is not ok"})
    if int(escalation_consumer.get("unresolved_count") or 0):
        findings.append({"severity": "warning", "detail": "main-session escalation consumer has unresolved residue"})
    repeated_only_is_routed = (
        int(escalation_consumer.get("repeated_blocker_count") or 0) > 0
        and int(escalation_consumer.get("unresolved_count") or 0) == 0
        and int(escalation_consumer.get("owner_decision_count") or 0) == 0
        and int(escalation_consumer.get("blocked_manual_count") or 0) == 0
        and int(escalation_consumer.get("auto_actionable_count") or 0) > 0
    )
    if int(escalation_consumer.get("repeated_blocker_count") or 0) and not repeated_only_is_routed:
        findings.append({"severity": "warning", "detail": "main-session escalation consumer has repeated blocker residue"})
    finance_warning_router = as_dict(payload.get("finance_evidence_warning_router_summary"))
    wf88_wiki = as_dict(payload.get("wf88_wiki_synthesis"))
    wiki_bootstrap = as_dict(payload.get("wiki_bootstrap_proof"))
    actionability = as_dict(payload.get("actionability_summary"))
    recovery = as_dict(payload.get("interruption_recovery"))
    if "wf88_wiki_synthesis" in payload and not wf88_wiki.get("present"):
        findings.append({"severity": "warning", "detail": "WF88 wiki synthesis packet is missing"})
    if wf88_wiki.get("validation_status") == "blocked":
        findings.append({"severity": "critical", "detail": "WF88 wiki synthesis validation is blocked"})
    if wf88_wiki.get("validation_status") == "warning":
        findings.append({"severity": "warning", "detail": "WF88 wiki synthesis has visible follow-up warnings"})
    if wf88_wiki.get("recommendation_leak_guard_pass") is False:
        findings.append({"severity": "critical", "detail": "WF88 wiki recommendation leak guard failed"})
    if int(wf88_wiki.get("auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki synthesis must keep auto-apply at zero"})
    if "wiki_bootstrap_proof" not in payload:
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof summary is missing"})
    elif not wiki_bootstrap.get("present"):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof packet is missing"})
    if wiki_bootstrap.get("validation_status") == "blocked":
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof validation is blocked"})
    if wiki_bootstrap.get("validation_status") == "warning":
        findings.append({"severity": "warning", "detail": "WF88 wiki bootstrap proof has classified warnings"})
    if int(wiki_bootstrap.get("missing_file_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof has missing entry files"})
    if int(wiki_bootstrap.get("missing_marker_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof has missing required markers"})
    if wiki_bootstrap.get("schema") != "veritas.wiki_bootstrap_proof.v2":
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof lacks current semantic contract"})
    if int(wiki_bootstrap.get("missing_semantic_marker_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof has missing efficiency semantics"})
    if wiki_bootstrap.get("semantic_render_hash_match") is not True:
        findings.append({"severity": "critical", "detail": "WF88 wiki semantic render hash does not match"})
    if wiki_bootstrap.get("recommendation_leak_guard_pass") is False:
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof recommendation leak guard failed"})
    if int(wiki_bootstrap.get("auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof must keep auto-apply at zero"})
    if wiki_bootstrap.get("no_orphan_validation") == "blocked":
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof no-orphan validation is blocked"})
    if int(wiki_bootstrap.get("actionable_orphan_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof sees orphaned actionable rows"})
    if int(wiki_bootstrap.get("actionable_missing_contract_count") or 0):
        findings.append({"severity": "critical", "detail": "WF88 wiki bootstrap proof sees missing action contracts"})
    if actionability:
        if not actionability.get("present"):
            findings.append({"severity": "warning", "detail": "actionable improvement queue is missing"})
        if int(actionability.get("orphan_count") or 0):
            findings.append({"severity": "critical", "detail": "actionable improvement queue has orphaned open rows"})
        if int(actionability.get("missing_contract_count") or 0):
            findings.append({"severity": "critical", "detail": "actionable improvement queue has missing action contracts"})
        if actionability.get("no_orphan_validation_status") == "blocked":
            findings.append({"severity": "critical", "detail": "no-orphan validator is blocked"})
        if actionability.get("no_orphan_validation_status") == "warning":
            findings.append({"severity": "warning", "detail": "no-orphan validator has visible monitor or owner-gate warnings"})
    if recovery:
        lane_register = as_dict(recovery.get("lane_register"))
        resume_state = as_dict(recovery.get("resume_checkpoint"))
        release_contract = as_dict(recovery.get("release_contract"))
        validator_bundle = as_dict(recovery.get("validator_bundle"))
        active_lane_count = int(lane_register.get("active_lane_count") or 0)
        active_lane_ids = [str(item) for item in as_list(lane_register.get("active_lane_ids")) if str(item)]
        resume_selects_active_lane = resume_state.get("target_eligible") is True
        if lane_register.get("present") and lane_register.get("validation_status") not in {None, "ok"}:
            findings.append({
                "severity": "warning",
                "category": "unrelated_global_warning",
                "priority": "P2",
                "detail": "interruption recovery lane register validation is not ok",
            })
        if active_lane_count and not lane_register.get("current_lane_id"):
            findings.append({
                "severity": "critical",
                "category": "current_task_blocker",
                "priority": "P0",
                "detail": "active lane count is nonzero but interruption recovery has no current lane identity",
            })
        if lane_register.get("projection_validation_status") == "critical" and not resume_selects_active_lane:
            findings.append({
                "severity": "critical",
                "category": "current_task_blocker",
                "priority": "P0",
                "detail": "active lane projection validation is critical",
            })
        if lane_register.get("resolution") == "blocked_ambiguous" and not resume_selects_active_lane:
            findings.append({
                "severity": "critical",
                "category": "current_task_blocker",
                "priority": "P0",
                "detail": "multiple active lanes require a fresh, valid explicit resume checkpoint",
            })
        if lane_register.get("resolution") in {
            "blocked_missing_identity",
            "blocked_missing_register",
            "blocked_stale_lease",
        }:
            findings.append({
                "severity": "critical",
                "category": "current_task_blocker",
                "priority": "P0",
                "detail": f"active lane resume resolution is blocked: {lane_register.get('resolution')}",
            })
        if int(lane_register.get("stale_lease_count") or 0):
            findings.append({
                "severity": "critical",
                "category": "current_task_blocker",
                "priority": "P0",
                "detail": "active lane projection contains stale or missing leases",
            })
        if active_lane_count and not resume_state.get("present"):
            findings.append({
                "severity": "critical",
                "category": "current_task_blocker",
                "priority": "P0",
                "detail": "resume checkpoint is missing while an active lane exists",
            })
        if resume_state.get("present"):
            if resume_state.get("schema") != resume_checkpoint.SCHEMA:
                findings.append({
                    "severity": "critical",
                    "category": "current_task_blocker",
                    "priority": "P0",
                    "detail": "resume checkpoint schema is not current",
                })
            if active_lane_count and resume_state.get("validation_status") != "ok":
                findings.append({
                    "severity": "critical",
                    "category": "current_task_blocker",
                    "priority": "P0",
                    "detail": "resume checkpoint live revalidation is not explicitly ok",
                })
            if active_lane_count and (
                resume_state.get("execution_receipt_consumed") is True
                or resume_state.get("replay_blocked") is True
                or resume_state.get("status") == "consumed_awaiting_successor"
            ):
                findings.append({
                    "severity": "critical",
                    "category": "current_task_blocker",
                    "priority": "P0",
                    "detail": "resume checkpoint command was consumed or replay-blocked and requires a successor",
                })
            if active_lane_count and not resume_selects_active_lane:
                findings.append({
                    "severity": "critical",
                    "category": "current_task_blocker",
                    "priority": "P0",
                    "detail": "resume checkpoint is not an eligible target for the current active lane state",
                })
            if active_lane_count and resume_state.get("lane_id") not in active_lane_ids and resume_state.get("lane_id"):
                findings.append({
                    "severity": "critical",
                    "category": "current_task_blocker",
                    "priority": "P0",
                    "detail": "resume checkpoint is not bound to a current active lane",
                })
            if resume_state.get("status") == "ready" and resume_state.get("command_authorized") is not True:
                findings.append({
                    "severity": "warning",
                    "category": "current_task_warning",
                    "priority": "P1",
                    "detail": "resume checkpoint is ready but its exact command remains acknowledgement-gated",
                })
            if resume_state.get("status") == "blocked":
                findings.append({
                    "severity": "critical",
                    "category": "current_task_blocker",
                    "priority": "P0",
                    "detail": f"resume checkpoint is operationally blocked: {resume_state.get('blocker') or 'unspecified blocker'}",
                })
        if release_contract.get("present") and release_contract.get("validation_status") not in {None, "ok"}:
            findings.append({
                "severity": "warning",
                "category": "unrelated_global_warning",
                "priority": "P2",
                "detail": "interruption recovery release contract validation is not ok",
            })
        if int(validator_bundle.get("selected_command_count") or 0) and int(validator_bundle.get("executed_command_count") or 0) == 0:
            if validator_bundle.get("proof_mode") != "plan_only":
                findings.append({
                    "severity": "warning",
                    "category": "unrelated_global_warning",
                    "priority": "P2",
                    "detail": "validator bundle selected commands lack clear plan-only interpretation",
                })
    if finance_warning_router.get("validation_status") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "finance evidence warning router validation is not ok"})
    if int(finance_warning_router.get("blocking_section_count") or 0):
        findings.append({"severity": "warning", "detail": "finance evidence warning router has blocking sections"})
    if finance_warning_router.get("status") is not None and finance_warning_router.get("customer_output_allowed") is not False:
        findings.append({"severity": "critical", "detail": "finance warning router must keep customer output disabled"})
    challenger_policy = as_dict(payload.get("challenger_model_policy"))
    efficiency_policy = as_dict(payload.get("execution_efficiency_policy"))
    quality_efficiency = as_dict(efficiency_policy.get("quality_weighted_efficiency"))
    outcome_efficiency = as_dict(payload.get("coding_outcome_efficiency"))
    if challenger_policy.get("required_challenger_model") != "claude-cli/claude-opus-4-8":
        findings.append({"severity": "critical", "detail": "challenger model policy must require claude-cli/claude-opus-4-8"})
    findings, priority_summary = classify_findings(findings)
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {
        "status": "critical" if critical else ("warning" if warnings else "ok"),
        "critical": critical,
        "warnings": warnings,
        "priority_summary": priority_summary,
        "findings": findings,
    }


def render_md(payload: dict[str, Any]) -> str:
    wf74 = as_dict(payload.get("wf74_summary"))
    pm = as_dict(payload.get("pm_summary"))
    cron = as_dict(payload.get("cron_summary"))
    otel = as_dict(payload.get("otel_carry_forward"))
    escalation_consumer = as_dict(payload.get("main_session_escalation_consumer_summary"))
    action_executor = as_dict(payload.get("main_session_action_executor_summary"))
    finance_warning_router = as_dict(payload.get("finance_evidence_warning_router_summary"))
    actionability = as_dict(payload.get("actionability_summary"))
    wiki_bootstrap = as_dict(payload.get("wiki_bootstrap_proof"))
    recovery = as_dict(payload.get("interruption_recovery"))
    recovery_resume = as_dict(recovery.get("resume_checkpoint"))
    recovery_lane = as_dict(recovery.get("lane_register"))
    recovery_release = as_dict(recovery.get("release_contract"))
    recovery_validator = as_dict(recovery.get("validator_bundle"))
    validation = as_dict(payload.get("validation"))
    challenger_policy = as_dict(payload.get("challenger_model_policy"))
    efficiency_policy = as_dict(payload.get("execution_efficiency_policy"))
    quality_efficiency = as_dict(efficiency_policy.get("quality_weighted_efficiency"))
    outcome_efficiency = as_dict(payload.get("coding_outcome_efficiency"))
    lines = [
        "# Future Session Enhancement Packet",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Fresh until: {as_dict(payload.get('packet_freshness')).get('expires_at_utc')} "
        f"(max startup age {as_dict(payload.get('packet_freshness')).get('max_startup_age_hours')}h)",
        f"- Status: {payload.get('status')} / validation {validation.get('status')}",
        "",
        "## Resume First",
        f"- Checkpoint: `{recovery_resume.get('checkpoint_id')}` / status `{recovery_resume.get('status')}` / validation `{recovery_resume.get('validation_status')}` / eligible `{recovery_resume.get('target_eligible')}` / expires `{recovery_resume.get('freshness_expiry')}`",
        f"- Lane: `{recovery_resume.get('lane_id')}` / workflow `{recovery_resume.get('workflow_id')}` / workstream `{recovery_resume.get('workstream')}`",
        f"- Last completed: {recovery_resume.get('last_completed_step')}",
        f"- In progress: {recovery_resume.get('in_progress_step')}",
        f"- Exact next action: {recovery_resume.get('exact_next_action')}",
        f"- Exact next command: `{recovery_resume.get('exact_next_command')}`",
        f"- Already completed; do not repeat: {recovery_resume.get('already_completed_do_not_repeat')}",
        f"- Acknowledgement: `{recovery_resume.get('acknowledgement_status')}` / execution receipt `{recovery_resume.get('execution_receipt_status')}` / replay blocked `{recovery_resume.get('replay_blocked')}` / command authorized `{recovery_resume.get('command_authorized')}` / automatic-safe `{recovery_resume.get('safe_to_execute_automatically')}`",
        f"- Blocker: {recovery_resume.get('blocker')}",
        "",
        "## Global Context",
        f"- PM status: {pm.get('status')} / top lane {pm.get('top_lane')}",
        f"- Cron status: {cron.get('status')} / wake main {cron.get('should_wake_main_session')}",
        f"- OTEL carry-forward: {otel.get('status')} / drift {otel.get('drift_status')} / recs {otel.get('recommendation_count')} / auto-route {otel.get('auto_implementation_status')}",
        f"- Escalation consumer: {escalation_consumer.get('status')} / safe actions {escalation_consumer.get('executed_safe_action_count')} / unresolved {escalation_consumer.get('unresolved_count')} / repeated {escalation_consumer.get('repeated_blocker_count')}",
        f"- Main action executor: {action_executor.get('status')} / {action_executor.get('action_type')} / selected {action_executor.get('selected_pm_job') or action_executor.get('parallel_helper_workstream')} / executed {action_executor.get('executed')}",
        f"- Finance warning router: {finance_warning_router.get('status')} / blocking {finance_warning_router.get('blocking_section_count')} / caveats {finance_warning_router.get('caveat_sections')}",
        f"- Wiki bootstrap proof: {wiki_bootstrap.get('status')} / validation {wiki_bootstrap.get('validation_status')} / gate {wiki_bootstrap.get('bootstrap_gate')} / files {wiki_bootstrap.get('validated_file_count')}/{wiki_bootstrap.get('required_file_count')} / auto-apply {wiki_bootstrap.get('auto_apply_count')}",
        f"- Implementation efficiency contract: {efficiency_policy.get('schema')} / model-free first / bounded native Terra / persistent Terra with proof / Main-Sol explicit only",
        f"- Efficiency evidence: conformant {outcome_efficiency.get('route_conformant_count')} / mismatches {outcome_efficiency.get('route_mismatch_count')} / retries {outcome_efficiency.get('total_retry_count')} / comparable cohorts {outcome_efficiency.get('comparable_cohort_count')} / gate {quality_efficiency.get('minimum_comparable_main_accepted_jobs')} accepted jobs / auto-promotion {quality_efficiency.get('automatic_route_promotion_allowed')}",
        f"- Interruption recovery: active lanes {recovery_lane.get('active_lane_count')} / resolution {recovery_lane.get('resolution')} / current {recovery_lane.get('current_lane_id')} / release ready {recovery_release.get('ready_to_close')} / validator proof {recovery_validator.get('proof_mode')}",
        f"- WF74 collection: {wf74.get('collection_status')} / validation {wf74.get('collection_validation')}",
        f"- WF74 opportunities: {wf74.get('wf74_opportunity_count')} total / {wf74.get('wf74_high_priority_opportunity_count')} high / top {wf74.get('wf74_top_opportunity_title')}",
        f"- WF74 cron migration pickup: visible {wf74.get('cron_migration_repair_visible')} / priority {wf74.get('cron_migration_repair_priority')} / followups {wf74.get('cron_migration_repair_followup_count')}",
        f"- WF74 workflow blocker pickup: visible {wf74.get('workflow_blocker_followup_visible')} / priority {wf74.get('workflow_blocker_followup_priority')} / followups {wf74.get('workflow_blocker_followup_count')} / routes {wf74.get('workflow_blocker_followup_route_counts')}",
        f"- WF74 patch plans: {wf74.get('auto_patch_patch_plan_count')} patch / {wf74.get('auto_patch_skill_workshop_request_count')} skill / {wf74.get('auto_patch_owner_gated_plan_count')} owner-gated / auto-apply {wf74.get('auto_patch_auto_apply_count')}",
        f"- WF74 decision docket: rows {wf74.get('decision_docket_row_count')} / active {wf74.get('decision_docket_active_action_count')} / fix-now {wf74.get('decision_docket_fix_now_count')} / market-accrual {wf74.get('decision_docket_market_session_accrual_count')}",
        f"- WF74 collection routed warning: {wf74.get('collection_warning_routed_by_improvement_ledger')} / {wf74.get('collection_validation_routed_reason')}",
        f"- WF74 collection quality gate: {wf74.get('collection_quality_gate_status')} / blocked {wf74.get('collection_blocked_quality_gates')}",
        f"- WF74 model attribution: {wf74.get('model_attribution_coverage')}",
        f"- WF74 session attribution: {wf74.get('session_attribution_coverage')}",
        f"- WF74 improvement fallback used: {wf74.get('improvement_ledger_fallback_used')} / source {wf74.get('improvement_ledger_fallback_source')}",
        f"- Actionable improvements: items {actionability.get('action_item_count')} / orphans {actionability.get('orphan_count')} / missing {actionability.get('missing_contract_count')} / no-orphan {actionability.get('no_orphan_validation_status')}",
        f"- Top actionable improvement: {actionability.get('top_action_title')} -> {actionability.get('top_action_destination')}",
        f"- WF74 anti-theater status: {wf74.get('improvement_effective_anti_theater_status')}",
        f"- WF74 duplicate cron collectors outside owner: {wf74.get('cron_component_collectors_outside_owner')}",
        f"- Improvement ledger open/high: {wf74.get('improvement_open_count')} / {wf74.get('improvement_high_priority_open_count')}",
        f"- Improvement ledger effective open/closed: {wf74.get('improvement_effective_open_count')} / {wf74.get('improvement_effective_closed_count')}",
        f"- Improvement ledger SLA: overdue {wf74.get('improvement_overdue_open_count')} / due soon {wf74.get('improvement_due_soon_open_count')} / escalation {wf74.get('improvement_escalation_level')}",
        f"- Top improvement: {wf74.get('improvement_top_title')}",
        f"- Owner-gated decisions: {wf74.get('owner_gated_decision_required_count')} / top {wf74.get('owner_gated_top_gate')}: {wf74.get('owner_gated_top_title')}",
        f"- Token usage events/tokens: {wf74.get('token_usage_event_count')} / {wf74.get('token_usage_total_tokens')}",
        f"- Implementation token events/gaps: {wf74.get('token_usage_implementation_event_count')} / {wf74.get('token_usage_implementation_gap_count')}",
        f"- Finance correctness rows ok/warn/blocked: {wf74.get('finance_ok_rows')} / {wf74.get('finance_warning_rows')} / {wf74.get('finance_blocked_rows')}",
        f"- Serious-work challenger model: {challenger_policy.get('required_challenger_model')}",
        "",
        "## WF74 Startup Pickup",
    ]
    for item in as_list(wf74.get("startup_pickup_items")):
        pickup = as_dict(item)
        lines.append(
            f"- {pickup.get('title')}: visible `{pickup.get('visible')}`, "
            f"priority `{pickup.get('priority')}`, followups `{pickup.get('followup_count')}`; "
            f"`{pickup.get('command')}`"
        )
    lines.extend([
        "",
        "## Open First",
    ])
    for route in payload.get("recommended_routes", []):
        lines.append(f"- {route.get('use_case')}: `{route.get('command')}`")
    lines.extend([
        "",
        "## Stop Lines",
    ])
    for line in payload.get("stop_lines", []):
        lines.append(f"- {line}")
    lines.extend([
        "",
        "## Challenger Model Policy",
        f"- Scope: {challenger_policy.get('scope')}",
        f"- Required model: `{challenger_policy.get('required_challenger_model')}`",
        f"- Verification: {challenger_policy.get('verification_rule')}",
        f"- Fallback: {challenger_policy.get('fallback_rule')}",
    ])
    if validation.get("findings"):
        lines.extend(["", "## Validation Findings"])
        for finding in validation["findings"]:
            lines.append(
                f"- [{finding.get('severity')} / {finding.get('category')} / {finding.get('priority')}] "
                f"{finding.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def mark_input_snapshot_unstable(
    payload: dict[str, Any],
    before_signature: dict[str, Any],
    after_signature: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed when source state changes twice during one packet build."""
    result = dict(payload)
    validation = dict(as_dict(result.get("validation")))
    findings = [dict(as_dict(item)) for item in as_list(validation.get("findings"))]
    findings.append({
        "severity": "critical",
        "category": "current_task_blocker",
        "priority": "P0",
        "detail": "future-session packet input snapshot changed during generation; retry from one stable source generation",
    })
    priority_summary = dict(as_dict(validation.get("priority_summary")))
    priority_summary["current_task_blocker"] = int(priority_summary.get("current_task_blocker") or 0) + 1
    validation.update({
        "status": "critical",
        "critical": int(validation.get("critical") or 0) + 1,
        "priority_summary": priority_summary,
        "findings": findings,
    })
    result["validation"] = validation
    result["status"] = "warning"
    result["input_snapshot_stability"] = {
        "status": "critical",
        "before_hash": before_signature.get("hash"),
        "after_hash": after_signature.get("hash"),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a future-session startup enhancement packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--prefilter-only", action="store_true", help="Check whether the existing packet can be reused without rebuilding it.")
    parser.add_argument("--skip-if-unchanged", action="store_true", help="Do not rewrite the packet when source inputs are unchanged and the existing packet is still fresh.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    now = datetime.now(LOCAL_TZ)
    input_signature = build_input_signature(now)
    live_recovery = extract_interruption_recovery_summary(now)
    prefilter = prefilter_decision(
        args.out,
        now,
        input_signature,
        live_recovery=live_recovery,
    )
    if args.prefilter_only:
        print(
            f"status={prefilter['status']} can_reuse={prefilter['can_reuse_existing_packet']} "
            f"reason={prefilter['reason']} input_hash={prefilter['current_input_hash']}"
        )
        return 0
    if args.skip_if_unchanged and prefilter.get("can_reuse_existing_packet"):
        confirmed_signature = build_input_signature(now)
        confirmed_recovery = extract_interruption_recovery_summary(now)
        confirmed_prefilter = prefilter_decision(
            args.out,
            now,
            confirmed_signature,
            live_recovery=confirmed_recovery,
        )
        if (
            confirmed_signature.get("hash") == input_signature.get("hash")
            and confirmed_prefilter.get("can_reuse_existing_packet")
        ):
            print(
                f"status=unchanged_skip validation=ok reason={confirmed_prefilter['reason']} "
                f"input_hash={confirmed_prefilter['current_input_hash']}"
            )
            return 0
        input_signature = confirmed_signature
        prefilter = confirmed_prefilter

    payload = build_payload(now, out=args.out, input_signature=input_signature, prefilter=prefilter)
    post_build_signature = build_input_signature(now)
    if post_build_signature.get("hash") != input_signature.get("hash"):
        retry_recovery = extract_interruption_recovery_summary(now)
        retry_prefilter = prefilter_decision(
            args.out,
            now,
            post_build_signature,
            live_recovery=retry_recovery,
        )
        payload = build_payload(
            now,
            out=args.out,
            input_signature=post_build_signature,
            prefilter=retry_prefilter,
        )
        final_signature = build_input_signature(now)
        if final_signature.get("hash") != post_build_signature.get("hash"):
            payload = mark_input_snapshot_unstable(payload, post_build_signature, final_signature)
    if args.write:
        atomic_write_json(args.out, payload)
        if args.write_md:
            atomic_write_text(args.out.with_suffix(".md"), render_md(payload))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"wf74={payload['wf74_summary'].get('collection_status')} "
        f"pm={payload['pm_summary'].get('status')} cron={payload['cron_summary'].get('status')} "
        f"escalation_consumer={payload['main_session_escalation_consumer_summary'].get('status')}"
    )
    for finding in payload["validation"]["findings"]:
        print(f"  [{finding['severity']}] {finding['detail']}")
    if args.validate and payload["validation"]["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
