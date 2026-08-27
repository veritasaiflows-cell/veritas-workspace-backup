#!/usr/bin/env python3
"""Build a review-only WF74 autonomous improvement opportunity queue.

This is the ranking layer for the learning loop. It reads existing WF74, OTEL,
coding, PM, and finance-quality proof surfaces and turns them into bounded
opportunities. It may collect, rank, and propose; it never mutates code, skills,
collector config, finance canon/portfolio state, or execution surfaces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"
OUT_JSON = TMP / "wf74-improvement-opportunity-queue.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA = "veritas.wf74_improvement_opportunity_queue.v1"

WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
CODING_OUTCOME = TMP / "coding-outcome-ledger-current.json"
CODING_RUNTIME = TMP / "coding-runtime-kpi-probe.json"
OTEL_OPS = TMP / "otel-ops-control.json"
MODEL_RUN = TMP / "model-run-ledger-current.json"
MODEL_LEARNING = TMP / "model-learning-metadata-ledger.json"
FINANCE_RESPONSE = TMP / "finance-response-quality-slice.json"
PM_CONTROL = TMP / "pm-control-packet.json"
FIELD_DEPTH_PACKET = TMP / "otel-field-depth-limited-owner-packet.json"
CRON_SIGNAL_SCORECARD = TMP / "cron-signal-scorecard.json"
CRON_CONTROL_PACKET = TMP / "cron-control-packet.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
WF87_SHADOW_OUTCOME = TMP / "wf87-shadow-outcome-scorecard.json"
WF87_READINESS_ROLLUP = TMP / "wf87-v2-readiness-rollup.json"
REPAIR_CONVEYOR = TMP / "trade-grade-repair-conveyor.json"
PM_IMPLEMENTATION_QUEUE = TMP / "pm-implementation-job-queue.json"
IMPLEMENTATION_COMPLETION_LEDGER = STATE / "implementation-completion-ledger.jsonl"

SOURCE_OPEN_REPAIR_TITLE = "Clear finance response quality source-open blockers so WF74 scorecard can pass"

OPPORTUNITY_COMPLETION_RULES = {
    SOURCE_OPEN_REPAIR_TITLE: {
        "pm-wf74-finance-source-open-quality-repair",
    },
    "Repair blocked WF74 collection step": {
        "pm-wf74-code-mutation-repair-blocked-collection-step",
    },
    "Route blocked cron signals into a migration-ready repair plan": {
        "pm-wf74-cron-migration-repair-plan",
        "pm-wf74-followup-cron-cron-migration",
    },
    "Convert workflow advancement blockers into implementation follow-ups": {
        "pm-wf74-workflow-blocker-followup-routing",
        "pm-wf74-followup-wf55-measurement-only",
        "pm-wf74-followup-wf87-maturity-accrual",
        "pm-wf74-followup-autonomy-spine-dependency-rollup",
    },
    "Measure and close planning follow-through gaps": {
        "pm-wf74-planning-followthrough-gap-reduction",
    },
}

WORKFLOW_MATURITY_RESIDUE_IDS = {
    "AUTONOMY-SPINE",
    "CRON",
    "WF55",
    "WF87",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "proposal_generation_only": True,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "owner_approval_inferred": False,
}

REVIEW_CADENCE = {
    "code_mutation": {
        "cadence": "daily queue, weekly proposal review, per-lane when validator failure or retry/rework appears",
        "allowed_autonomous_output": "ranked opportunity plus proposed patch scope",
        "requires_before_apply": "main-session implementation lane, tests, closeout proof, and no forbidden authority expansion",
    },
    "skill_application": {
        "cadence": "weekly review or after the same procedure friction repeats at least twice",
        "allowed_autonomous_output": "Skill Workshop proposal draft only",
        "requires_before_apply": "explicit owner request to apply/approve a specific skill proposal",
    },
    "collector_config": {
        "cadence": "daily OTEL drift review, weekly field-depth review if drift persists",
        "allowed_autonomous_output": "owner field-depth decision packet only",
        "requires_before_apply": "explicit owner approval, config diff, rollback, privacy scan, and post-change OTEL validation",
    },
    "finance_mutation": {
        "cadence": "daily finance-quality review, weekly remediation proposal rollup",
        "allowed_autonomous_output": "repair/proposal packet only",
        "requires_before_apply": "standing/scoped gate, validator proof, rollback, and no capital/execution inference",
    },
    "execution": {
        "cadence": "per exact card/order request and daily guard review when paper/live surfaces are active",
        "allowed_autonomous_output": "approval-ready card or guard proof only",
        "requires_before_apply": "exact owner approval plus fresh WF63/WF67 guard proof; live execution remains blocked",
    },
    "cron_migration": {
        "cadence": "daily cron scorecard review, weekly migration planning, per-blocker when repeated blocked signals appear",
        "allowed_autonomous_output": "ranked migration proposal, dry-run contract plan, and validation checklist",
        "requires_before_apply": "explicit owner approval for live cron schedule/model changes, contract validator proof, rollback plan, and post-change freshness proof",
    },
    "workflow_maturity": {
        "cadence": "daily workflow advancement scorecard review and weekly owner-radar synthesis",
        "allowed_autonomous_output": "workflow blocker routing packet and implementation-lane proposal",
        "requires_before_apply": "main-session lane register lease, source-artifact proof, validators, and no authority expansion",
    },
    "outcome_measurement": {
        "cadence": "daily shadow-outcome and follow-up measurement review until thresholds are met",
        "allowed_autonomous_output": "measurement backlog, follow-up target list, and maturity-readiness recommendation",
        "requires_before_apply": "regular-session follow-up evidence, threshold proof, and explicit owner gate before any paper/live action",
    },
    "planning_quality": {
        "cadence": "daily lane follow-through review and weekly planning-quality trend review",
        "allowed_autonomous_output": "planning gap signal, follow-through metrics, and scoped implementation proposal",
        "requires_before_apply": "main-session lane register lease, acceptance proof, validators, and no authority expansion",
    },
}

BLOCKED_ACTIONS = [
    "do not mutate code from this queue",
    "do not apply/install/approve skills from this queue",
    "do not mutate collector/runtime config from this queue",
    "do not mutate finance canon/portfolio/cash/sizing/risk/execution state from this queue",
    "do not submit/cancel/replace paper or live orders from this queue",
    "do not infer model ranking, finance correctness, owner approval, or execution readiness from telemetry counts",
]


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


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def load_jsonl_artifact(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def load_inputs() -> dict[str, Any]:
    return {
        "wf74_runner": as_dict(load_json_artifact(WF74_RUNNER)),
        "coding_outcome": as_dict(load_json_artifact(CODING_OUTCOME)),
        "coding_runtime": as_dict(load_json_artifact(CODING_RUNTIME)),
        "otel_ops": as_dict(load_json_artifact(OTEL_OPS)),
        "model_run": as_dict(load_json_artifact(MODEL_RUN)),
        "model_learning": as_dict(load_json_artifact(MODEL_LEARNING)),
        "finance_response": as_dict(load_json_artifact(FINANCE_RESPONSE)),
        "pm_control": as_dict(load_json_artifact(PM_CONTROL)),
        "field_depth_packet": as_dict(load_json_artifact(FIELD_DEPTH_PACKET)),
        "cron_signal": as_dict(load_json_artifact(CRON_SIGNAL_SCORECARD)),
        "cron_control": as_dict(load_json_artifact(CRON_CONTROL_PACKET)),
        "workflow_advancement": as_dict(load_json_artifact(WORKFLOW_ADVANCEMENT)),
        "wf87_shadow_outcome": as_dict(load_json_artifact(WF87_SHADOW_OUTCOME)),
        "wf87_readiness_rollup": as_dict(load_json_artifact(WF87_READINESS_ROLLUP)),
        "repair_conveyor": as_dict(load_json_artifact(REPAIR_CONVEYOR)),
        "pm_implementation_queue": as_dict(load_json_artifact(PM_IMPLEMENTATION_QUEUE)),
        "implementation_completion_ledger": load_jsonl_artifact(IMPLEMENTATION_COMPLETION_LEDGER),
    }


def opportunity_identity(category: str, title: str, signal: str, priority: Any) -> tuple[str, list[str]]:
    # Priority is deliberately excluded: re-ranking must not mint a new id and orphan ledger linkage.
    stable = f"{category}-{stable_id(title, signal)}"
    legacy = f"{category}-{stable_id(title, signal, priority)}"
    return stable, ([legacy] if legacy != stable else [])


def reidentify(updated: dict[str, Any], category: str) -> dict[str, Any]:
    aliases = [str(item) for item in as_list(updated.get("legacy_opportunity_ids")) if item]
    prior_id = str(updated.get("opportunity_id") or "")
    if prior_id:
        aliases.append(prior_id)
    new_id, legacy = opportunity_identity(
        category,
        str(updated.get("title") or ""),
        str(updated.get("signal") or ""),
        updated.get("priority"),
    )
    aliases.extend(legacy)
    updated["opportunity_id"] = new_id
    updated["legacy_opportunity_ids"] = sorted({item for item in aliases if item and item != new_id})
    return updated


def identity_tokens(row: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("opportunity_id", "origin_opportunity_id"):
        value = str(row.get(key) or "")
        if value:
            tokens.add(value)
    for item in as_list(row.get("legacy_opportunity_ids")):
        value = str(item or "")
        if value:
            tokens.add(value)
    suffixes = {token.rsplit("-", 1)[-1] for token in tokens}
    return tokens | {suffix for suffix in suffixes if len(suffix) >= 8}


def opportunity(
    *,
    category: str,
    title: str,
    priority: int,
    signal: str,
    evidence: dict[str, Any],
    recommended_action: str,
    proposal_gate: str,
    validation_command: str,
) -> dict[str, Any]:
    cadence = REVIEW_CADENCE[category]
    opportunity_id, legacy_ids = opportunity_identity(category, title, signal, priority)
    return {
        "schema": "veritas.wf74_improvement_opportunity.v1",
        "opportunity_id": opportunity_id,
        "origin_opportunity_id": opportunity_id,
        "legacy_opportunity_ids": legacy_ids,
        "lifecycle_id": f"lifecycle-{stable_id('wf74', opportunity_id)}",
        "category": category,
        "title": title,
        "priority": priority,
        "signal": signal,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "proposal_gate": proposal_gate,
        "review_cadence": cadence["cadence"],
        "allowed_autonomous_output": cadence["allowed_autonomous_output"],
        "requires_before_apply": cadence["requires_before_apply"],
        "validation_command": validation_command,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def ensure_lifecycle_identity(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    opportunity_id = str(updated.get("opportunity_id") or "")
    origin = str(updated.get("origin_opportunity_id") or opportunity_id)
    if origin:
        updated["origin_opportunity_id"] = origin
    lifecycle = str(updated.get("lifecycle_id") or "")
    if not lifecycle and origin:
        updated["lifecycle_id"] = f"lifecycle-{stable_id('wf74', origin)}"
    updated["legacy_opportunity_ids"] = sorted({
        str(item) for item in as_list(updated.get("legacy_opportunity_ids")) if item
    })
    return updated


def completed_job_index(inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for entry in as_list(inputs.get("implementation_completion_ledger")):
        if not isinstance(entry, dict):
            continue
        job = as_dict(entry.get("job"))
        job_id = str(job.get("job_id") or "")
        if not job_id:
            continue
        completed[job_id] = {
            "job_id": job_id,
            "title": job.get("title"),
            "implementation_class": job.get("implementation_class"),
            "collision_group": job.get("collision_group"),
            "completed_at_utc": entry.get("completed_at_utc") or entry.get("recorded_at_utc"),
            "source": "implementation_completion_ledger",
        }
    for job in as_list(as_dict(inputs.get("pm_implementation_queue")).get("jobs")):
        if not isinstance(job, dict) or job.get("status") != "completed_by_ledger":
            continue
        job_id = str(job.get("job_id") or "")
        if not job_id:
            continue
        completed.setdefault(job_id, {
            "job_id": job_id,
            "title": job.get("title"),
            "implementation_class": job.get("implementation_class"),
            "collision_group": job.get("collision_group"),
            "completed_at_utc": job.get("completed_at_utc"),
            "source": "pm_implementation_job_queue",
        })
    return completed


def identity_matched_job_ids(row: dict[str, Any], completed: dict[str, dict[str, Any]]) -> set[str]:
    tokens = identity_tokens(row)
    if not tokens:
        return set()
    matched: set[str] = set()
    for job_id, item in completed.items():
        haystacks = [job_id, str(item.get("collision_group") or "")]
        if any(token in haystack for token in tokens for haystack in haystacks if haystack):
            matched.add(job_id)
    return matched


def matched_completion(row: dict[str, Any], completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    title = str(row.get("title") or "")
    candidate_ids = set(OPPORTUNITY_COMPLETION_RULES.get(title, set()))
    matched_by_title = sorted(job_id for job_id in candidate_ids if job_id in completed)
    matched_by_identity = sorted(identity_matched_job_ids(row, completed))
    ordered = matched_by_title + [job_id for job_id in matched_by_identity if job_id not in set(matched_by_title)]
    if not ordered:
        return {}
    matches = [completed[job_id] for job_id in ordered]
    return {
        "matched_job_ids": [item.get("job_id") for item in matches],
        "matched_by_title_rule": matched_by_title,
        "matched_by_identity": matched_by_identity,
        "latest_completed_at_utc": max(str(item.get("completed_at_utc") or "") for item in matches),
        "matches": matches,
    }


def workflow_maturity_residue_only(row: dict[str, Any]) -> bool:
    evidence = as_dict(row.get("evidence"))
    blocked_workflows = as_list(evidence.get("blocked_workflows"))
    workflow_ids = {
        str(as_dict(item).get("workflow_id") or "").upper()
        for item in blocked_workflows
        if isinstance(item, dict)
    }
    if not workflow_ids:
        return False
    return workflow_ids <= WORKFLOW_MATURITY_RESIDUE_IDS and int(as_num(evidence.get("owner_needed_count"))) == 0


def workflow_blocker_requires_implementation(row: dict[str, Any]) -> bool:
    workflow_id = str(row.get("workflow_id") or "").upper()
    status = str(row.get("status") or "").lower()
    blockers = [str(item).lower() for item in as_list(row.get("blockers"))]
    if workflow_id in {"WF87", "AUTONOMY-SPINE"}:
        return False
    if workflow_id == "CRON":
        hard_markers = (
            "cron_status=blocked",
            "cron_status=critical",
            "cron_status=error",
            "blocked_count=",
            "urgent_attention_count=",
        )
        for blocker in blockers:
            if blocker in {"cron_status=blocked", "cron_status=critical", "cron_status=error"}:
                return True
            if blocker.startswith("blocked_count=") and blocker != "blocked_count=0":
                return True
            if blocker.startswith("urgent_attention_count=") and blocker != "urgent_attention_count=0":
                return True
        return status in {"blocked", "critical", "error"}
    return True


def residual_workflow_followup(row: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    updated = ensure_lifecycle_identity(row)
    updated["title"] = "Close remaining workflow-maturity follow-ups"
    updated["priority"] = min(int(as_num(row.get("priority")) or 0), 74)
    updated["signal"] = "workflow_maturity_residue_after_completed_routing"
    updated["recommended_action"] = (
        "Keep the residual CRON/WF55/WF87/AUTONOMY-SPINE maturity signals visible, but do not re-open "
        "the completed implementation-routing job unless a new non-maturity blocker appears."
    )
    updated["completion_status"] = "residual_followup_after_completion"
    updated["prior_completion"] = completion
    return reidentify(updated, "workflow_maturity")


def regressed_cron_followup(row: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    updated = ensure_lifecycle_identity(row)
    updated["title"] = "Repair regressed cron signals after completed migration plan"
    updated["signal"] = "cron_scorecard_regressed_after_completed_repair_plan"
    updated["recommended_action"] = (
        "Treat this as a current cron regression against the completed migration plan: inspect the blocked "
        "cron artifacts, repair the failing proof surface, then refresh cron control."
    )
    updated["completion_status"] = "current_regression_after_completion"
    updated["prior_completion"] = completion
    return reidentify(updated, "cron_migration")


def regressed_planning_followup(row: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    updated = ensure_lifecycle_identity(row)
    updated["title"] = "Continue planning follow-through gap reduction after completed pass"
    updated["signal"] = "planning_followthrough_gap_regressed_after_completed_pass"
    updated["recommended_action"] = (
        "Treat this as current planning-quality debt after the completed reduction pass: inspect lanes with missing "
        "proof, acceptance, or later rework and open a narrow follow-through repair if the gap persists."
    )
    updated["completion_status"] = "current_regression_after_completion"
    updated["prior_completion"] = completion
    return reidentify(updated, "planning_quality")


def annotate_open(row: dict[str, Any], completion: dict[str, Any] | None = None) -> dict[str, Any]:
    updated = ensure_lifecycle_identity(row)
    updated["completion_status"] = "open"
    if completion:
        updated["prior_completion"] = completion
    return updated


def current_cron_signal(inputs: dict[str, Any]) -> dict[str, Any]:
    cron_control = as_dict(inputs.get("cron_control"))
    control_scorecard = as_dict(cron_control.get("scorecard"))
    if control_scorecard and as_dict(control_scorecard.get("scorecard")):
        summary = as_dict(cron_control.get("summary"))
        scorecard = dict(as_dict(control_scorecard.get("scorecard")))
        for key in ("escalation_signal_count", "should_wake_main_session"):
            if key not in scorecard:
                scorecard[key] = summary.get(key)
        return {
            "source": "cron_control_packet",
            "source_path": rel(CRON_CONTROL_PACKET),
            "generated_at_utc": cron_control.get("generated_at_utc") or control_scorecard.get("generated_at_utc"),
            "packet_status": cron_control.get("status"),
            "packet_validation": as_dict(cron_control.get("validation")).get("status"),
            "scorecard": scorecard,
            "signals": as_list(control_scorecard.get("signals")),
        }
    legacy = as_dict(inputs.get("cron_signal"))
    return {
        "source": "legacy_cron_signal_scorecard",
        "source_path": rel(CRON_SIGNAL_SCORECARD),
        "generated_at_utc": legacy.get("generated_at_utc"),
        "packet_status": legacy.get("status"),
        "packet_validation": as_dict(legacy.get("validation")).get("status"),
        "scorecard": as_dict(legacy.get("scorecard")),
        "signals": as_list(legacy.get("signals")),
    }


def cron_signal_requires_repair(cron_signal: dict[str, Any]) -> bool:
    scorecard = as_dict(cron_signal.get("scorecard"))
    blocked = int(as_num(scorecard.get("blocked_count")))
    escalation = int(as_num(scorecard.get("escalation_signal_count")))
    should_wake = bool(scorecard.get("should_wake_main_session"))
    packet_failed = cron_signal.get("packet_status") in {"blocked", "critical", "error"}
    validation_failed = cron_signal.get("packet_validation") in {"blocked", "critical", "error"}
    return blocked > 0 or escalation > 0 or should_wake or packet_failed or validation_failed


def completed_cron_green_residue(row: dict[str, Any], completion: dict[str, Any], cron_signal: dict[str, Any]) -> dict[str, Any]:
    completed_row = dict(row)
    completed_row["completion_status"] = "completed_by_ledger_current_cron_green"
    completed_row["prior_completion"] = completion
    completed_row["current_cron_signal"] = {
        "source": cron_signal.get("source"),
        "generated_at_utc": cron_signal.get("generated_at_utc"),
        "packet_status": cron_signal.get("packet_status"),
        "packet_validation": cron_signal.get("packet_validation"),
        "scorecard": cron_signal.get("scorecard"),
    }
    return completed_row


def apply_completion_overlay(
    opportunities: list[dict[str, Any]],
    inputs: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    completed = completed_job_index(inputs)
    cron_signal = current_cron_signal(inputs)
    current: list[dict[str, Any]] = []
    completed_or_resolved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    for source_row in opportunities:
        row = ensure_lifecycle_identity(source_row)
        completion = matched_completion(row, completed)
        title = str(row.get("title") or "")
        if not completion:
            current.append(annotate_open(row))
            continue
        if title == "Route blocked cron signals into a migration-ready repair plan":
            if cron_signal_requires_repair(cron_signal):
                updated = regressed_cron_followup(row, completion)
                current.append(updated)
                regressed.append(updated)
            else:
                completed_or_resolved.append(completed_cron_green_residue(row, completion, cron_signal))
            continue
        if title == "Measure and close planning follow-through gaps":
            updated = regressed_planning_followup(row, completion)
            current.append(updated)
            regressed.append(updated)
            continue
        if title == "Convert workflow advancement blockers into implementation follow-ups" and workflow_maturity_residue_only(row):
            completed_row = dict(row)
            completed_row["completion_status"] = "completed_by_ledger_residual_visibility_only"
            completed_row["prior_completion"] = completion
            completed_or_resolved.append(completed_row)
            if not as_dict(row.get("evidence")).get("visibility_operationalized"):
                current.append(residual_workflow_followup(row, completion))
            continue
        current.append(annotate_open(row, completion))
    return current, completed_or_resolved, regressed


def otel_drift_priority_and_action(otel_drift: dict[str, Any]) -> tuple[int, str, str]:
    warning_or_error_count = int(as_num(otel_drift.get("daily_warning_or_error_count")))
    reasons = {str(reason) for reason in as_list(otel_drift.get("drift_reasons"))}
    event_rate_only = bool(reasons) and reasons <= {"daily_event_rate_deviates_from_weekly_baseline"}
    if warning_or_error_count == 0 and event_rate_only:
        return (
            64,
            "otel_operational_volume_review",
            (
                "Keep this as operational-volume review only; do not treat OTEL event-rate volume as model-learning "
                "quality evidence or collector-config authority while warning/error counts are zero."
            ),
        )
    return (
        88,
        "otel_operational_drift_review",
        "Track whether the drift persists for another collection window before proposing collector-depth changes.",
    )


def build_opportunities(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    runner_summary = as_dict(inputs["wf74_runner"].get("summary"))
    coding_runtime = as_dict(inputs["coding_runtime"].get("kpis"))
    coding_summary = as_dict(inputs["coding_outcome"].get("ledger_summary"))
    model_summary = as_dict(inputs["model_run"].get("summary"))
    otel_drift = as_dict(inputs["otel_ops"].get("drift"))
    field_depth = inputs["field_depth_packet"]
    finance_summary = as_dict(inputs["finance_response"].get("summary"))
    repair_conveyor_summary = as_dict(as_dict(inputs.get("repair_conveyor")).get("summary"))
    repair_conveyor_validation = as_dict(as_dict(inputs.get("repair_conveyor")).get("validation"))
    cron_signal = current_cron_signal(inputs)
    cron_scorecard = as_dict(cron_signal.get("scorecard"))
    workflow_advancement = as_dict(inputs.get("workflow_advancement"))
    wf87_shadow_outcome = as_dict(inputs.get("wf87_shadow_outcome"))
    wf87_readiness_rollup = as_dict(inputs.get("wf87_readiness_rollup"))
    workflow_summary = as_dict(workflow_advancement.get("summary"))
    workflow_validation_status = as_dict(workflow_advancement.get("validation")).get("status")
    wf87_shadow_summary = as_dict(wf87_shadow_outcome.get("summary"))
    wf87_shadow_validation_status = as_dict(wf87_shadow_outcome.get("validation")).get("status")
    wf87_phase = as_dict(wf87_readiness_rollup.get("phase_readiness"))
    wf87_blocker_taxonomy = as_dict(wf87_readiness_rollup.get("blocker_taxonomy"))
    wf87_readiness_validation_status = as_dict(wf87_readiness_rollup.get("validation")).get("status")
    opportunities: list[dict[str, Any]] = []

    coding_rows = int(as_num(coding_summary.get("ledger_row_count")))
    coding_model_attr = int(as_num(coding_summary.get("model_attributed_count")))
    planning_signal = as_dict(coding_summary.get("planning_quality_signal"))
    planning_gap_count = int(as_num(planning_signal.get("plan_followthrough_gap_count")))
    planning_clean_rate = planning_signal.get("plan_followthrough_clean_rate")
    if coding_rows and coding_model_attr == 0:
        opportunities.append(opportunity(
            category="code_mutation",
            title="Stamp model_path on implementation and helper producers",
            priority=94,
            signal="coding_outcome_model_attributed_count_zero",
            evidence={
                "coding_outcome_ledger_rows": coding_rows,
                "coding_outcome_model_attributed_count": coding_model_attr,
                "model_run_lane_register_rows": model_summary.get("lane_register_rows"),
            },
            recommended_action=(
                "Prepare a narrow implementation proposal to add model_path/model_provider stamping "
                "where producer runtime metadata already exists."
            ),
            proposal_gate="main_review_required",
            validation_command="python scripts\\model_run_ledger.py --write --write-md --validate",
        ))

    if planning_signal and (planning_gap_count or planning_clean_rate is None):
        opportunities.append(opportunity(
            category="planning_quality",
            title="Measure and close planning follow-through gaps",
            priority=80 if planning_gap_count else 62,
            signal="planning_quality_followthrough_gap",
            evidence={
                "tracked_lane_count": planning_signal.get("tracked_lane_count"),
                "plan_contract_present_count": planning_signal.get("plan_contract_present_count"),
                "plan_followthrough_clean_count": planning_signal.get("plan_followthrough_clean_count"),
                "plan_followthrough_gap_count": planning_gap_count,
                "plan_followthrough_clean_rate": planning_clean_rate,
                "gap_reasons": planning_signal.get("gap_reasons"),
            },
            recommended_action=(
                "Review lanes missing acceptance commands, proof, clean validation, or later ex-post cleanliness; "
                "convert repeated planning gaps into scoped implementation follow-ups."
            ),
            proposal_gate="main_review_required",
            validation_command="python scripts\\coding_outcome_ledger.py --write --validate",
        ))

    validator_elapsed = as_num(coding_runtime.get("validator_elapsed_seconds"))
    validator_target = as_num(coding_runtime.get("validator_target_seconds"))
    if validator_elapsed and validator_target and validator_elapsed > validator_target:
        opportunities.append(opportunity(
            category="code_mutation",
            title="Reduce validator drag for normal implementation passes",
            priority=72,
            signal="validator_elapsed_exceeds_target",
            evidence={
                "validator_elapsed_seconds": validator_elapsed,
                "validator_target_seconds": validator_target,
                "recommended_budget": coding_runtime.get("recommended_budget"),
                "recommended_validator_count": coding_runtime.get("recommended_validator_count"),
            },
            recommended_action=(
                "Review validator routing and repeated proof commands; propose a smaller default proof path "
                "only if quality boundaries remain intact."
            ),
            proposal_gate="main_review_required",
            validation_command="python scripts\\changed_file_validator_router.py --write --validate",
        ))

    if coding_runtime.get("rework_required") is True or as_dict(coding_runtime.get("failure_bucket_counts")):
        opportunities.append(opportunity(
            category="skill_application",
            title="Convert repeated coding friction into a Skill Workshop proposal",
            priority=82,
            signal="coding_rework_or_failure_bucket_present",
            evidence={
                "rework_required": coding_runtime.get("rework_required"),
                "failure_bucket_counts": coding_runtime.get("failure_bucket_counts"),
            },
            recommended_action=(
                "Draft a Skill Workshop proposal only if the same friction pattern repeats; do not apply it automatically."
            ),
            proposal_gate="skill_workshop_proposal_only",
            validation_command="openclaw skills check",
        ))

    if otel_drift.get("status") == "review":
        drift_priority, drift_signal, drift_action = otel_drift_priority_and_action(otel_drift)
        opportunities.append(opportunity(
            category="collector_config",
            title="Review OTEL event-rate drift against the weekly baseline",
            priority=drift_priority,
            signal=drift_signal,
            evidence={
                "daily_warning_or_error_count": otel_drift.get("daily_warning_or_error_count"),
                "daily_vs_weekly_event_rate_ratio": otel_drift.get("daily_vs_weekly_event_rate_ratio"),
                "drift_reasons": otel_drift.get("drift_reasons"),
                "operational_volume_only": drift_signal == "otel_operational_volume_review",
            },
            recommended_action=drift_action,
            proposal_gate="proposal_only_no_config_change",
            validation_command="python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
        ))

    if field_depth.get("status") == "owner_decision_required":
        opportunities.append(opportunity(
            category="collector_config",
            title="Owner-gated OTEL field-depth decision packet is ready",
            priority=70,
            signal="otel_field_depth_packet_owner_decision_required",
            evidence={
                "field_depth_packet": rel(FIELD_DEPTH_PACKET),
                "collector_posture": field_depth.get("current_collector_posture"),
            },
            recommended_action=(
                "Hold collector config unchanged; present the field-depth packet only if richer local metadata is worth approving."
            ),
            proposal_gate="owner_decision_required",
            validation_command="python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
        ))

    source_freshness_blocked = int(as_num(finance_summary.get("source_freshness_blocked_count")))
    source_open_blocked = int(as_num(finance_summary.get("source_open_blocked_count")))
    remediation_tracks = int(as_num(finance_summary.get("remediation_tracks_needing_repair")))
    runner_blocked = int(as_num(runner_summary.get("wf74_runner_steps_blocked") or runner_summary.get("steps_blocked")))
    runner_domain_blocked_nonfatal = bool(runner_summary.get("scheduler_exit_domain_blocked_nonfatal"))
    if runner_blocked and source_open_blocked:
        opportunities.append(opportunity(
            category="finance_mutation",
            title=SOURCE_OPEN_REPAIR_TITLE,
            priority=96,
            signal="wf74_scorecard_blocked_by_finance_source_open",
            evidence={
                "blocker_chain": [
                    "wf74_model_quality_collection_cron_runner",
                    "model_quality_scorecard",
                    "finance_response_quality_slice",
                    "source_open_blocked_count",
                ],
                "steps_blocked": runner_summary.get("steps_blocked"),
                "blocking_step_names": runner_summary.get("blocking_step_names"),
                "source_open_blocked_count": source_open_blocked,
                "source_freshness_blocked_count": source_freshness_blocked,
                "remediation_tracks_needing_repair": remediation_tracks,
                "average_quality_score": finance_summary.get("average_quality_score"),
                "recommended_department": "finance_wf78_wf84_wf85",
                "repair_conveyor": "WF78/WF85 source-open repair conveyor",
            },
            recommended_action=(
                "Run the WF78 source-open repair executor and work packet, then rerun the finance response quality "
                "slice and WF74 scorecard; do not patch WF74 around the fail-closed gate."
            ),
            proposal_gate="finance_repair_proposal_only",
            validation_command="python scripts\\finance_response_quality_slice.py --write --write-md --validate",
        ))

    if source_freshness_blocked or source_open_blocked or remediation_tracks:
        finance_repair_operationalized = (
            as_dict(inputs.get("repair_conveyor")).get("status") == "ready_for_repair_execution"
            and repair_conveyor_validation.get("status") in {"ok", "warning", None}
            and int(as_num(repair_conveyor_summary.get("implementation_blocker_count"))) == 0
            and int(as_num(repair_conveyor_summary.get("control_plane_blocker_count"))) == 0
            and repair_conveyor_summary.get("implementation_queue_posture") == "not_an_implementation_blocker"
        )
        opportunities.append(opportunity(
            category="finance_mutation",
            title="Route finance response-quality gaps into repair proposals",
            priority=66 if finance_repair_operationalized else 86,
            signal="finance_response_quality_domain_repair_operationalized" if finance_repair_operationalized else "finance_response_quality_repair_signal",
            evidence={
                "sector_timing_warning_available": finance_summary.get("sector_timing_warning_available"),
                "source_open_blocked_count": source_open_blocked,
                "source_freshness_blocked_count": source_freshness_blocked,
                "remediation_tracks_needing_repair": remediation_tracks,
                "average_quality_score": finance_summary.get("average_quality_score"),
                "repair_conveyor_status": as_dict(inputs.get("repair_conveyor")).get("status"),
                "repair_conveyor_validation": repair_conveyor_validation.get("status"),
                "repair_conveyor_implementation_blocker_count": repair_conveyor_summary.get("implementation_blocker_count"),
                "repair_conveyor_control_plane_blocker_count": repair_conveyor_summary.get("control_plane_blocker_count"),
                "repair_conveyor_posture": repair_conveyor_summary.get("implementation_queue_posture"),
                "finance_domain_repair_operationalized": finance_repair_operationalized,
            },
            recommended_action=(
                "Use the repair conveyor as finance-domain repair queue; create implementation work only if conveyor validation, implementation blockers, or control-plane blockers regress."
                if finance_repair_operationalized
                else "Create repair proposals for source-open/source-freshness/remediation gaps; do not mutate finance canon or portfolio state from WF74."
            ),
            proposal_gate="finance_repair_proposal_only",
            validation_command="python scripts\\finance_response_quality_slice.py --write --write-md --validate",
        ))

    if runner_blocked and not source_open_blocked and not runner_domain_blocked_nonfatal:
        opportunities.append(opportunity(
            category="code_mutation",
            title="Repair blocked WF74 collection step",
            priority=96,
            signal="wf74_collection_step_blocked",
            evidence={"steps_blocked": runner_summary.get("steps_blocked")},
            recommended_action="Open a narrow implementation lane for the blocked WF74 collection step.",
            proposal_gate="main_review_required",
            validation_command="python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate",
        ))

    cron_blocked = int(as_num(cron_scorecard.get("blocked_count")))
    cron_attention = int(as_num(cron_scorecard.get("requires_attention_count")))
    cron_escalation = int(as_num(cron_scorecard.get("escalation_signal_count")))
    cron_should_wake = bool(cron_scorecard.get("should_wake_main_session"))
    if cron_blocked or cron_escalation or cron_should_wake:
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
        opportunities.append(opportunity(
            category="cron_migration",
            title="Route blocked cron signals into a migration-ready repair plan",
            priority=92 if cron_blocked else 78,
            signal="cron_scorecard_attention_or_blocked",
            evidence={
                "blocked_count": cron_blocked,
                "requires_attention_count": cron_attention,
                "escalation_signal_count": cron_escalation,
                "should_wake_main_session": cron_should_wake,
                "enabled_job_count": cron_scorecard.get("enabled_job_count"),
                "cron_signal_source": cron_signal.get("source"),
                "cron_signal_generated_at_utc": cron_signal.get("generated_at_utc"),
                "cron_control_status": cron_signal.get("packet_status"),
                "cron_control_validation": cron_signal.get("packet_validation"),
                "attention_signals": attention_signals,
            },
            recommended_action=(
                "Build a dry-run cron migration/repair plan from the attention signals; do not mutate schedules "
                "until contract drift, rollback, and post-change freshness checks are ready."
            ),
            proposal_gate="cron_migration_plan_only",
            validation_command="python scripts\\cron_control_packet.py --write --validate",
        ))

    workflow_blocked = int(as_num(workflow_summary.get("blocked_count")))
    owner_needed = int(as_num(workflow_summary.get("owner_needed_count")))
    if workflow_blocked or owner_needed:
        blocked_workflows = [
            {
                "workflow_id": row.get("workflow_id"),
                "status": row.get("status"),
                "signal": row.get("signal"),
                "blockers": row.get("blockers"),
                "next_action": row.get("next_action"),
            }
            for row in as_list(inputs["workflow_advancement"].get("signals"))
            if isinstance(row, dict) and row.get("signal") == "blocked"
        ][:8]
        implementation_blockers = [
            row for row in blocked_workflows
            if workflow_blocker_requires_implementation(row)
        ]
        workflow_priority = 89 if owner_needed or implementation_blockers or workflow_validation_status not in {"ok", "warning"} else 74
        opportunities.append(opportunity(
            category="workflow_maturity",
            title="Convert workflow advancement blockers into implementation follow-ups",
            priority=workflow_priority,
            signal="workflow_advancement_blockers_present",
            evidence={
                "blocked_count": workflow_blocked,
                "owner_needed_count": owner_needed,
                "blocked_workflows": blocked_workflows,
                "implementation_blocker_count": len(implementation_blockers),
                "visibility_operationalized": workflow_priority < 80,
            },
            recommended_action=(
                "Route repeated workflow blockers into scoped implementation lanes or owner decisions, preserving "
                "review-only authority on generated scorecards."
            ),
            proposal_gate="main_review_required",
            validation_command="python scripts\\workflow_advancement_scorecard.py --write --validate",
        ))

    pending_followups = int(as_num(wf87_shadow_summary.get("pending_regular_session_followup_count")))
    stale_followups = int(as_num(wf87_shadow_summary.get("stale_pending_followup_count")))
    scoreable_decisions = int(as_num(wf87_shadow_summary.get("scoreable_decision_count")))
    if pending_followups or stale_followups or scoreable_decisions < 5:
        outcome_priority = 84 if stale_followups or pending_followups >= 5 or scoreable_decisions < 5 or wf87_shadow_validation_status != "ok" else 68
        opportunities.append(opportunity(
            category="outcome_measurement",
            title="Track WF87 shadow outcomes until regular-session follow-up thresholds are met",
            priority=outcome_priority,
            signal="wf87_shadow_outcome_measurement_backlog",
            evidence={
                "decision_count": wf87_shadow_summary.get("decision_count"),
                "scoreable_decision_count": scoreable_decisions,
                "pending_regular_session_followup_count": pending_followups,
                "stale_pending_followup_count": stale_followups,
                "decision_quality_claim_allowed_now": wf87_shadow_summary.get("decision_quality_claim_allowed_now"),
                "model_performance_claim_allowed_now": wf87_shadow_summary.get("model_performance_claim_allowed_now"),
                "visibility_operationalized": outcome_priority < 80,
            },
            recommended_action=(
                "Keep collecting regular-session follow-up observations; use the measurement backlog for calibration only, "
                "not decision-quality claims or execution authority."
            ),
            proposal_gate="measurement_only_no_execution",
            validation_command="python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
        ))

    binding_blockers = int(as_num(as_dict(wf87_blocker_taxonomy.get("counts")).get("binding_blocker_count")))
    if binding_blockers or wf87_phase.get("phase_a_runtime_gates_clean") is False:
        wf87_visibility_operationalized = wf87_readiness_validation_status == "ok" and binding_blockers > 0
        opportunities.append(opportunity(
            category="workflow_maturity",
            title="Keep WF87 runtime blockers visible as maturity blockers",
            priority=67 if wf87_visibility_operationalized else 83,
            signal="wf87_runtime_or_maturity_blockers_present",
            evidence={
                "phase_a_runtime_gates_clean": wf87_phase.get("phase_a_runtime_gates_clean"),
                "phase_b_assisted_round_trip_ready": wf87_phase.get("phase_b_assisted_round_trip_ready"),
                "phase_c_autonomous_paper_buy_ready": wf87_phase.get("phase_c_autonomous_paper_buy_ready"),
                "binding_blocker_count": binding_blockers,
                "binding_blockers": wf87_blocker_taxonomy.get("binding_blockers"),
                "visibility_operationalized": wf87_visibility_operationalized,
            },
            recommended_action=(
                "Treat WF87 blockers as learning friction and maturity debt; do not convert them into execution readiness."
            ),
            proposal_gate="main_review_required",
            validation_command="python scripts\\wf87_v2_readiness_rollup.py --write --validate",
        ))

    opportunities.append(opportunity(
        category="execution",
        title="Maintain execution as proposal-only and exact-owner-gated",
        priority=35,
        signal="standing_execution_cadence",
        evidence={
            "paper_or_live_execution_allowed": False,
            "exact_owner_approval_required": True,
        },
        recommended_action=(
            "Continue producing approval-ready cards and guard proof only; submit/cancel/replace remains separate exact approval."
        ),
        proposal_gate="standing_guardrail_no_execution",
        validation_command="python scripts\\alpaca_paper_execution_guard_validator.py --validate",
    ))
    return sorted(opportunities, key=lambda row: (-int(row["priority"]), str(row["opportunity_id"])))


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    missing_cadence = sorted(set(REVIEW_CADENCE) - set(as_dict(payload.get("review_cadence"))))
    if missing_cadence:
        errors.append("missing_review_cadence:" + ",".join(missing_cadence))
    if not as_list(payload.get("opportunities")):
        warnings.append("no_opportunities_ranked")
    if as_dict(payload.get("summary")).get("cron_signal_source") == "legacy_cron_signal_scorecard":
        warnings.append("cron_signal_source_legacy_scorecard")
    for row in as_list(payload.get("opportunities")):
        item = as_dict(row)
        if item.get("proposal_gate") in {"auto_apply", "auto_execute"}:
            errors.append(f"forbidden_auto_gate:{row.get('opportunity_id')}")
        opportunity_id = str(item.get("opportunity_id") or "")
        origin_opportunity_id = str(item.get("origin_opportunity_id") or "")
        lifecycle_id = str(item.get("lifecycle_id") or "")
        if not opportunity_id or not origin_opportunity_id or not lifecycle_id:
            errors.append(f"missing_lifecycle_identity:{opportunity_id or 'unknown'}")
        if lifecycle_id and not lifecycle_id.startswith("lifecycle-"):
            errors.append(f"noncanonical_lifecycle_id:{opportunity_id or 'unknown'}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    raw_opportunities = [ensure_lifecycle_identity(row) for row in build_opportunities(inputs)]
    opportunities, completed_or_resolved, regressed_after_completion = apply_completion_overlay(raw_opportunities, inputs)
    by_category: dict[str, int] = {}
    by_gate: dict[str, int] = {}
    for row in opportunities:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
        by_gate[row["proposal_gate"]] = by_gate.get(row["proposal_gate"], 0) + 1
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Rank safe improvement opportunities from WF74/OTEL/coding/finance metadata for proposal generation.",
        "source_artifacts": {
            "wf74_runner": rel(WF74_RUNNER),
            "coding_outcome": rel(CODING_OUTCOME),
            "coding_runtime": rel(CODING_RUNTIME),
            "otel_ops": rel(OTEL_OPS),
            "model_run": rel(MODEL_RUN),
            "model_learning": rel(MODEL_LEARNING),
            "finance_response": rel(FINANCE_RESPONSE),
            "pm_control": rel(PM_CONTROL),
            "field_depth_packet": rel(FIELD_DEPTH_PACKET),
            "cron_control_packet": rel(CRON_CONTROL_PACKET),
            "legacy_cron_signal_scorecard": rel(CRON_SIGNAL_SCORECARD),
            "workflow_advancement": rel(WORKFLOW_ADVANCEMENT),
            "wf87_shadow_outcome": rel(WF87_SHADOW_OUTCOME),
            "wf87_readiness_rollup": rel(WF87_READINESS_ROLLUP),
            "pm_implementation_queue": rel(PM_IMPLEMENTATION_QUEUE),
            "implementation_completion_ledger": rel(IMPLEMENTATION_COMPLETION_LEDGER),
        },
        "summary": {
            "opportunity_count": len(opportunities),
            "raw_signal_count": len(raw_opportunities),
            "completed_or_resolved_opportunity_count": len(completed_or_resolved),
            "regressed_after_completion_count": len(regressed_after_completion),
            "high_priority_count": sum(1 for row in opportunities if int(row["priority"]) >= 85),
            "outcome_measurement_followup_count": sum(1 for row in opportunities if row["category"] == "outcome_measurement"),
            "planning_quality_followup_count": sum(1 for row in opportunities if row["category"] == "planning_quality"),
            "by_category": dict(sorted(by_category.items())),
            "by_proposal_gate": dict(sorted(by_gate.items())),
            "top_opportunity_id": opportunities[0]["opportunity_id"] if opportunities else None,
            "top_opportunity_title": opportunities[0]["title"] if opportunities else None,
            "cron_signal_source": current_cron_signal(inputs).get("source"),
            "cron_signal_generated_at_utc": current_cron_signal(inputs).get("generated_at_utc"),
            "next_safe_action": "Run wf74_reflection_to_proposal_autopilot.py to produce bounded proposals; do not apply changes from the queue.",
        },
        "review_cadence": REVIEW_CADENCE,
        "allowed_autonomous_actions": [
            "refresh proof artifacts",
            "rank opportunities",
            "generate proposal packets",
            "surface PM/cron review signals",
        ],
        "blocked_actions": BLOCKED_ACTIONS,
        "opportunities": opportunities,
        "completed_or_resolved_opportunities": completed_or_resolved,
        "regressed_after_completion_opportunities": regressed_after_completion,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Improvement Opportunity Queue",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Opportunities: {summary.get('opportunity_count')}",
        f"- Raw signals: {summary.get('raw_signal_count')}",
        f"- Completed/resolved: {summary.get('completed_or_resolved_opportunity_count')}",
        f"- Regressed after completion: {summary.get('regressed_after_completion_count')}",
        f"- High priority: {summary.get('high_priority_count')}",
        f"- Top: {summary.get('top_opportunity_title')}",
        "",
        "## Top Opportunities",
    ]
    for row in as_list(payload.get("opportunities"))[:8]:
        lines.append(
            f"- {row.get('priority')} | {row.get('category')} | {row.get('title')} | "
            f"status={row.get('completion_status')} | gate={row.get('proposal_gate')}"
        )
    completed = as_list(payload.get("completed_or_resolved_opportunities"))
    if completed:
        lines.extend(["", "## Completed Or Resolved"])
        for row in completed[:8]:
            lines.append(f"- {row.get('priority')} | {row.get('category')} | {row.get('title')} | status={row.get('completion_status')}")
    lines.extend(["", "## Blocked Actions"])
    for item in BLOCKED_ACTIONS:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=OUT_JSON)
    args = parser.parse_args(argv)
    out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
    payload = build_payload(load_inputs())
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(payload))
    else:
        print(json.dumps(payload, indent=2))
    print(
        "status={status} validation={validation} opportunities={count} top={top}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            count=payload["summary"]["opportunity_count"],
            top=payload["summary"]["top_opportunity_title"],
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
