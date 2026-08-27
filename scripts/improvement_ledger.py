#!/usr/bin/env python3
"""Build the durable improvement ledger and current carry-forward packet.

The live WF74 opportunity queue is regenerated under tmp/. This script promotes
its recommendations into append-only state history so new sessions can load the
improvement backlog without relying on chat history or one runtime packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"
DEFAULT_LEDGER = STATE_HISTORY / "improvement-ledger.jsonl"
DEFAULT_JSON = TMP / "improvement-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.improvement_ledger_current.v1"
EVENT_SCHEMA = "veritas.improvement_ledger_event.v1"

WF74_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
OTEL_LEARNING_LOOP = TMP / "otel-learning-loop.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
SKILL_WORKSHOP_MANIFEST = ROOT.parent / "skill-workshop" / "proposals.json"
WF88_FOLLOWUP_TRIAGE = TMP / "wf88-followup-debt-triage-packet.json"
WF88_OS2_CONTROL = TMP / "wf88-os2-control-packet.json"
FINANCE_RESPONSE_QUALITY_SLICE = TMP / "finance-response-quality-slice.json"
FINANCE_RESPONSE_QUALITY_REPAIR_LOOP = TMP / "finance-response-quality-repair-loop.json"
WF85_SOURCE_OPEN_RECONCILIATION = TMP / "wf85-source-open-reconciliation-contract.json"
WF74_SELF_PROMPT_REVIEW_PACKET = TMP / "wf74-self-prompt-review-packet.json"
WF74_PROMPT_VARIANT_LEDGER = TMP / "wf74-prompt-variant-ledger.json"

TRIAGE_CLOSURE_STATUSES = {
    "verified_fix",
    "pending_skill_proposal",
    "applied_skill_proposal",
    "superseded_by_open_improvement",
    "owner_packet_ready_not_applied",
    "monitor_only_drift_currently_absent",
}

FOLLOW_UP_CLASS_BY_STATUS = {
    "verified_fix": "live_code_or_validator",
    "applied_skill_proposal": "live_code_or_validator",
    "pending_skill_proposal": "pending_skill_proposal",
    "superseded_by_open_improvement": "successor_item",
    "owner_packet_ready_not_applied": "owner_gated_packet",
    "monitor_only_drift_currently_absent": "monitor_only_rationale",
    "standing_policy": "standing_policy",
    "monitor_only_standing": "monitor_only_rationale",
    "owner_decision_pending": "owner_gated_packet",
}

STANDING_STATES = {
    "standing_policy",
    "monitor_only_standing",
    "owner_decision_pending",
}

CANONICAL_SOURCE_KEYS = {
    (
        "wf74_improvement_opportunity",
        "cron_migration",
        "Route blocked cron signals into a migration-ready repair plan",
    ): "cron_migration-route-blocked-cron-signals",
    (
        "wf74_improvement_opportunity",
        "cron_migration",
        "Repair regressed cron signals after completed migration plan",
    ): "cron_migration-regressed-cron-signals",
    (
        "wf74_improvement_opportunity",
        "collector_config",
        "Review OTEL event-rate drift against the weekly baseline",
    ): "collector_config-otel-event-rate-drift",
    (
        "wf74_improvement_opportunity",
        "collector_config",
        "Owner-gated OTEL field-depth decision packet is ready",
    ): "collector_config-otel-field-depth-owner-decision",
    (
        "wf74_improvement_opportunity",
        "execution",
        "Maintain execution as proposal-only and exact-owner-gated",
    ): "execution-proposal-only-guardrail",
    (
        "wf74_improvement_opportunity",
        "workflow_maturity",
        "Keep WF87 runtime blockers visible as maturity blockers",
    ): "workflow_maturity-wf87-runtime-blockers-visible",
    (
        "wf74_improvement_opportunity",
        "workflow_maturity",
        "Close remaining workflow-maturity follow-ups",
    ): "workflow_maturity-residual-followups",
    (
        "wf74_improvement_opportunity",
        "code_mutation",
        "Reduce validator drag for normal implementation passes",
    ): "code_mutation-validator-drag-reduction",
    (
        "wf74_improvement_opportunity",
        "finance_mutation",
        "Route finance response-quality gaps into repair proposals",
    ): "finance_mutation-response-quality-repair-routing",
    (
        "wf74_improvement_opportunity",
        "workflow_maturity",
        "Convert workflow advancement blockers into implementation follow-ups",
    ): "workflow_maturity-advancement-blockers-followups",
}

OTEL_STANDING_RECOMMENDATIONS = {
    "content_capture_boundary": "standing_policy",
    "token_cost_metadata_depth": "owner_decision_pending",
    "cron_signal_learning_input": "monitor_only_standing",
    "workflow_advancement_learning_input": "monitor_only_standing",
    "workflow_maturity-wf87-runtime-blockers-visible": "monitor_only_standing",
    "wf87_outcome_measurement_backlog": "monitor_only_standing",
    "wf74_queue_followup": "monitor_only_standing",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "append_only": True,
    "local_only": True,
    "recommendation_tracking_only": True,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TEXT = (
    "sk-",
    "Bearer ",
    "Authorization:",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "system_prompt",
    "access_token",
    "refresh_token",
    "oauth_token",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def follow_up_class(status: Any) -> str | None:
    return FOLLOW_UP_CLASS_BY_STATUS.get(str(status or ""))


def with_follow_up_class(payload: dict[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    classification = follow_up_class(row.get("status"))
    if classification:
        row["follow_up_class"] = classification
    return row


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def event_fingerprint(row: dict[str, Any]) -> str:
    stable_fields = {
        key: row.get(key)
        for key in (
            "source_type",
            "source_key",
            "status",
            "carry_forward",
            "category",
            "title",
            "priority",
            "severity",
            "signal",
            "decision",
            "recommended_action",
            "next_action",
            "validation_command",
            "requires_before_apply",
            "allowed_autonomous_output",
            "review_cadence",
            "resolution_reason",
        )
        if key in row
    }
    return stable_id(json.dumps(stable_fields, sort_keys=True, separators=(",", ":"), default=str))


def finalize_event_ids(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        fingerprint = event_fingerprint(row)
        row["event_fingerprint"] = fingerprint
        if row.get("carry_forward") is False or row.get("status") in {"complete", "cancelled", "rejected"}:
            row["event_id"] = stable_id(
                row.get("source_type"),
                row.get("source_key"),
                fingerprint,
                row.get("source_generated_at_utc"),
            )
        else:
            row["event_id"] = stable_id(row.get("source_type"), row.get("source_key"), fingerprint)
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            rows.append({"schema": "invalid", "raw_line_sha": stable_id(line), "status": "invalid_json"})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def allowed_prompt_trace_key(key: str, child: Any) -> bool:
    if key not in {"self_prompt_id", "prompt_variant_id"}:
        return False
    if child in {None, ""}:
        return True
    if not isinstance(child, str):
        return False
    return len(child) <= 160 and "\n" not in child and "\r" not in child


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("prompt", "response", "tool_input", "tool_output", "system_prompt", "authorization", "secret", "token", "credential", "header")):
                if allowed_prompt_trace_key(lowered, child):
                    continue
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(marker.lower() in value.lower() for marker in FORBIDDEN_TEXT):
            findings.append(f"forbidden_value:{path}")
    return findings


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def source_path_for_type(source_type: str) -> Path:
    if source_type == "otel_learning_loop_recommendation":
        return OTEL_LEARNING_LOOP
    return WF74_QUEUE


def current_source_generated_at(source_type: str, queue: dict[str, Any], otel: dict[str, Any]) -> str | None:
    if source_type == "otel_learning_loop_recommendation":
        return otel.get("generated_at_utc")
    return queue.get("generated_at_utc")


def current_prompt_trace() -> dict[str, str]:
    packet = as_dict(load_json_artifact(WF74_SELF_PROMPT_REVIEW_PACKET))
    prompt = as_dict(packet.get("self_prompt"))
    variant_ledger = as_dict(load_json_artifact(WF74_PROMPT_VARIANT_LEDGER))
    summary = as_dict(variant_ledger.get("summary"))
    self_prompt_id = prompt.get("prompt_id") or summary.get("current_prompt_id")
    prompt_variant_id = prompt.get("variant_id") or summary.get("current_variant_id")
    trace: dict[str, str] = {}
    if self_prompt_id:
        trace["self_prompt_id"] = str(self_prompt_id)[:160]
    if prompt_variant_id:
        trace["prompt_variant_id"] = str(prompt_variant_id)[:160]
    return trace


def event_base(source_type: str, source_path: Path, source_generated_at: str | None, source_key: str) -> dict[str, Any]:
    row = {
        "schema": EVENT_SCHEMA,
        "event_id": stable_id(source_type, rel(source_path), source_generated_at, source_key),
        "recorded_at_utc": utc_now(),
        "source_type": source_type,
        "source_artifact": rel(source_path),
        "source_generated_at_utc": source_generated_at,
        "source_key": source_key,
        "status": "open",
        "carry_forward": True,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    row.update(current_prompt_trace())
    return row


def canonical_source_key(source_type: str, category: Any, title: Any, fallback: str) -> str:
    key = (source_type, str(category or ""), str(title or ""))
    return CANONICAL_SOURCE_KEYS.get(key, fallback)


def standing_state_for_row(row: dict[str, Any]) -> str | None:
    category = str(row.get("category") or "")
    title = str(row.get("title") or "")
    source_key = str(row.get("source_key") or "")
    decision = str(row.get("decision") or "")
    if category == "execution" and (
        decision == "standing_guardrail_no_execution"
        or title == "Maintain execution as proposal-only and exact-owner-gated"
    ):
        return "standing_policy"
    if source_key in OTEL_STANDING_RECOMMENDATIONS:
        return OTEL_STANDING_RECOMMENDATIONS[source_key]
    if category == "collector_config" and "field-depth" in title.casefold():
        return "owner_decision_pending"
    return None


def apply_standing_state(row: dict[str, Any]) -> dict[str, Any]:
    state = standing_state_for_row(row)
    if not state:
        return row
    row["standing_state"] = state
    row["sla_exempt"] = True
    if state == "standing_policy":
        row.update({
            "status": "complete",
            "carry_forward": False,
            "severity": "standing_policy",
            "resolution_reason": "standing_policy_not_actionable_improvement",
            "next_action": row.get("next_action") or row.get("recommended_action"),
            "follow_up": with_follow_up_class({
                "status": "standing_policy",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Permanent guardrail/policy visibility, not an actionable improvement row.",
                "proof": [row.get("source_artifact")],
            }),
        })
    elif state == "owner_decision_pending":
        row.update({
            "severity": "owner_decision_pending",
            "decision": row.get("decision") or "owner_decision_pending",
            "follow_up": with_follow_up_class({
                "status": "owner_decision_pending",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Owner-gated decision packet; keep one capped row visible and do not mutate collector/config without explicit approval.",
                "proof": [row.get("source_artifact")],
            }),
        })
    elif state == "monitor_only_standing":
        row.update({
            "severity": "monitor_only",
            "follow_up": with_follow_up_class({
                "status": "monitor_only_standing",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Standing monitor-only learning signal; keep one capped row visible without treating it as overdue implementation debt.",
                "proof": [row.get("source_artifact")],
            }),
        })
    return row


def queue_events(queue: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = queue.get("generated_at_utc")
    rows: list[dict[str, Any]] = []
    for opportunity in as_list(queue.get("opportunities")):
        if not isinstance(opportunity, dict):
            continue
        source_key = str(opportunity.get("opportunity_id") or stable_id(opportunity.get("title"), opportunity.get("signal")))
        source_key = canonical_source_key(
            "wf74_improvement_opportunity",
            opportunity.get("category"),
            opportunity.get("title"),
            source_key,
        )
        row = event_base("wf74_improvement_opportunity", WF74_QUEUE, generated_at, source_key)
        row.update({
            "category": opportunity.get("category"),
            "title": opportunity.get("title"),
            "priority": opportunity.get("priority"),
            "severity": "high" if int(opportunity.get("priority") or 0) >= 80 else "normal",
            "signal": opportunity.get("signal"),
            "decision": opportunity.get("proposal_gate"),
            "recommended_action": opportunity.get("recommended_action"),
            "next_action": opportunity.get("recommended_action"),
            "validation_command": opportunity.get("validation_command"),
            "proof_artifacts": [rel(WF74_QUEUE)],
            "evidence_keys": sorted(as_dict(opportunity.get("evidence")).keys()),
            "requires_before_apply": opportunity.get("requires_before_apply"),
            "allowed_autonomous_output": opportunity.get("allowed_autonomous_output"),
            "review_cadence": opportunity.get("review_cadence"),
        })
        apply_standing_state(row)
        rows.append(row)
    return rows


def otel_events(otel: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = otel.get("generated_at_utc")
    rows: list[dict[str, Any]] = []
    for rec in as_list(otel.get("recommendations")):
        if not isinstance(rec, dict):
            continue
        source_key = str(rec.get("id") or stable_id(rec.get("decision"), rec.get("rationale")))
        row = event_base("otel_learning_loop_recommendation", OTEL_LEARNING_LOOP, generated_at, source_key)
        row.update({
            "category": "otel_learning_loop",
            "title": rec.get("id"),
            "priority": 75 if rec.get("severity") == "warning" else 55,
            "severity": rec.get("severity") or "info",
            "decision": rec.get("decision"),
            "recommended_action": rec.get("next_action"),
            "next_action": rec.get("next_action"),
            "proof_artifacts": [rel(OTEL_LEARNING_LOOP)],
            "rationale": rec.get("rationale"),
            "blocked_capture": rec.get("blocked_capture"),
        })
        apply_standing_state(row)
        rows.append(row)
    return rows


def resolution_events(runner: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(runner.get("summary"))
    if runner.get("status") != "ok" or int(summary.get("steps_blocked") or 0) != 0:
        return []
    generated_at = runner.get("generated_at_utc") or utc_now()
    row = event_base("wf74_improvement_opportunity", WF74_RUNNER, generated_at, "code_mutation-eaa17861f4c9")
    row.update({
        "category": "code_mutation",
        "title": "Repair blocked WF74 collection step",
        "priority": 96,
        "severity": "resolved",
        "signal": "wf74_collection_step_clean",
        "decision": "resolved_by_latest_runner",
        "recommended_action": "No carry-forward action while latest WF74 collection has zero blocked steps.",
        "next_action": "Monitor future WF74 collection runs; reopen only if a later runner reports blocked steps.",
        "validation_command": "python scripts\\wf74_model_quality_collection_cron_runner.py --write --write-md --validate",
        "proof_artifacts": [rel(WF74_RUNNER)],
        "status": "complete",
        "carry_forward": False,
        "resolution_reason": "latest_wf74_runner_steps_blocked_zero",
        "follow_up": with_follow_up_class({
            "status": "verified_fix",
            "required": False,
            "implemented_durable_change": True,
            "proof": [rel(WF74_RUNNER)],
        }),
    })
    return [row]


def int_field(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def finance_response_quality_proof_clean(
    runner: dict[str, Any],
    finance_slice: dict[str, Any],
    repair_loop: dict[str, Any],
    wf85_reconciliation: dict[str, Any],
) -> bool:
    runner_summary = as_dict(runner.get("summary"))
    slice_summary = as_dict(finance_slice.get("summary"))
    repair_summary = as_dict(repair_loop.get("summary"))
    wf85_summary = as_dict(wf85_reconciliation.get("summary"))
    return all((
        runner.get("status") == "ok",
        int_field(runner_summary, "steps_blocked") == 0,
        runner_summary.get("finance_response_quality_status") == "ok",
        int_field(runner_summary, "finance_response_quality_source_open_blocked_count") == 0,
        int_field(runner_summary, "finance_response_quality_source_freshness_blocked_count") == 0,
        int_field(runner_summary, "finance_response_quality_remediation_tracks_needing_repair") == 0,
        finance_slice.get("status") == "ok",
        int_field(slice_summary, "blocked_archetype_count") == 0,
        int_field(slice_summary, "source_open_blocked_count") == 0,
        int_field(slice_summary, "source_freshness_blocked_count") == 0,
        int_field(slice_summary, "remediation_tracks_needing_repair") == 0,
        repair_loop.get("status") in {"ok", "noop_ok"},
        int_field(repair_summary, "proposal_count") == 0,
        int_field(repair_summary, "high_priority_count") == 0,
        int_field(repair_summary, "source_open_blocked_count") == 0,
        int_field(repair_summary, "source_freshness_blocked_count") == 0,
        int_field(repair_summary, "remediation_tracks_needing_repair") == 0,
        wf85_reconciliation.get("status") == "ok",
        int_field(wf85_summary, "fresh_verified_source_count") > 0,
        int_field(wf85_summary, "unnecessary_source_open_blocker_count") == 0,
        int_field(wf85_summary, "wrong_source_open_blocker_reason_count") == 0,
        int_field(wf85_summary, "mismatch_error_count") == 0,
        int_field(wf85_summary, "producer_order_error_count") == 0,
    ))


def cron_control_green() -> bool:
    payload = as_dict(load_json_artifact(TMP / "cron-control-packet.json"))
    summary = as_dict(payload.get("summary"))
    return all((
        payload.get("status") == "ok",
        int_field(summary, "blocked_count") == 0,
        int_field(summary, "urgent_count") == 0,
        int_field(summary, "escalation_signal_count") == 0,
    ))


def otel_ops_green() -> bool:
    payload = as_dict(load_json_artifact(TMP / "otel-ops-control.json"))
    validation = as_dict(payload.get("validation"))
    drift = as_dict(payload.get("drift"))
    summary = as_dict(payload.get("summary"))
    return all((
        payload.get("status") == "ok",
        validation.get("status") in {"ok", None},
        int_field(summary, "event_count") > 0,
        drift.get("status") in {"ok", "within_baseline", None},
    ))


def is_finance_response_quality_stale_row(row: dict[str, Any]) -> bool:
    if row.get("category") != "finance_mutation":
        return False
    text = " ".join(
        str(row.get(key) or "")
        for key in ("source_key", "title", "signal", "decision", "recommended_action", "next_action")
    ).casefold()
    markers = (
        "finance response quality",
        "finance response-quality",
        "source-open blocker",
        "source_open_blocked",
        "blocked_by_finance_source_open",
    )
    return any(marker in text for marker in markers)


def proof_clean_for_monitor_row(row: dict[str, Any]) -> tuple[bool, str, list[str]]:
    category = str(row.get("category") or "")
    title = str(row.get("title") or "")
    text = " ".join(str(row.get(key) or "") for key in ("source_key", "title", "signal", "decision", "next_action")).casefold()
    if category == "cron_migration" or "cron signal" in text or "cron signals" in title.casefold():
        if cron_control_green():
            return True, "resolved_by_cron_control_green_proof", ["tmp/cron-control-packet.json"]
        return False, "", []
    if category == "collector_config" or "otel" in text or "otel" in title.casefold():
        if otel_ops_green():
            return True, "resolved_by_otel_ops_green_proof", ["tmp/otel-ops-control.json"]
        return False, "", []
    return False, "", []


def finance_response_quality_resolution_events(
    existing: list[dict[str, Any]],
    current_open_events: list[dict[str, Any]],
    runner: dict[str, Any],
    finance_slice: dict[str, Any],
    repair_loop: dict[str, Any],
    wf85_reconciliation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Close stale finance-response/source-open carry-forward rows after clean proof.

    The source-open policy remains strict. This only clears obsolete improvement
    rows when the current WF74/WF85 producer chain proves zero source-open
    blockers and zero repair proposals.
    """
    if not finance_response_quality_proof_clean(runner, finance_slice, repair_loop, wf85_reconciliation):
        return []
    current_keys = {
        (str(row.get("source_type")), str(row.get("source_key")))
        for row in current_open_events
        if row.get("status") == "open" and row.get("carry_forward") is not False
    }
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    proof_artifacts = [
        rel(WF74_RUNNER),
        rel(FINANCE_RESPONSE_QUALITY_SLICE),
        rel(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP),
        rel(WF85_SOURCE_OPEN_RECONCILIATION),
        rel(WF88_OS2_CONTROL),
    ]
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        source_type = str(old.get("source_type") or "")
        source_key = str(old.get("source_key") or "")
        if (source_type, source_key) in current_keys:
            continue
        if source_type != "wf74_improvement_opportunity" or not is_finance_response_quality_stale_row(old):
            continue
        row = event_base(source_type, WF85_SOURCE_OPEN_RECONCILIATION, wf85_reconciliation.get("generated_at_utc") or utc_now(), source_key)
        row.update({
            "category": old.get("category"),
            "title": old.get("title"),
            "priority": old.get("priority"),
            "severity": "resolved",
            "signal": "finance_response_quality_current_proof_clean",
            "decision": "resolved_by_finance_response_quality_clean_proof",
            "recommended_action": "No carry-forward action while current WF74/WF85 proof shows zero finance response-quality source-open blockers and zero repair proposals.",
            "next_action": "Monitor current WF74/WF85 proof; reopen only if source-open blockers, repair proposals, or reconciliation mismatches reappear.",
            "validation_command": "python scripts\\wf85_source_open_reconciliation_contract.py --write --validate",
            "proof_artifacts": proof_artifacts,
            "status": "complete",
            "carry_forward": False,
            "resolution_reason": "finance_response_quality_current_proof_clean",
            "successor_id": "wf85-source-open-repair-queue",
            "successor_artifact": rel(WF88_OS2_CONTROL),
            "successor_artifact_kind": "wf88_canonical_action_state",
            "follow_up": with_follow_up_class({
                "status": "verified_fix",
                "required": False,
                "implemented_durable_change": True,
                "detail": "Current WF74 finance response-quality slice, repair loop, and WF85 reconciliation contract are clean.",
                "proof": proof_artifacts,
                "successor_id": "wf85-source-open-repair-queue",
                "successor_artifact": rel(WF88_OS2_CONTROL),
                "successor_artifact_kind": "wf88_canonical_action_state",
            }),
        })
        rows.append(row)
    return rows


def monitor_only_resolution_events(existing: list[dict[str, Any]], queue: dict[str, Any], otel: dict[str, Any]) -> list[dict[str, Any]]:
    """Close monitor-only WF88/OTEL/cron rows when current proof is green.

    These are not implemented fixes. They are old operational visibility rows
    that should not stay as overdue debt once the live proof source is clean.
    """
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        follow_up = as_dict(old.get("follow_up"))
        action_state = str(old.get("triage_action_state") or follow_up.get("status") or "")
        if action_state not in {"monitor_only", "monitor_only_standing"}:
            continue
        clean, reason, proof = proof_clean_for_monitor_row(old)
        if not clean:
            continue
        source_type = str(old.get("source_type") or "wf74_improvement_opportunity")
        source_path = source_path_for_type(source_type)
        row = event_base(source_type, source_path, current_source_generated_at(source_type, queue, otel), str(old.get("source_key") or "unknown"))
        proof_artifacts = sorted({rel(source_path), *proof, *[str(item) for item in as_list(follow_up.get("proof")) if item]})
        row.update({
            "category": old.get("category"),
            "title": old.get("title"),
            "priority": old.get("priority"),
            "severity": "monitor_only_resolved",
            "signal": "monitor_only_current_proof_green",
            "decision": "resolved_by_current_monitor_proof",
            "recommended_action": "No carry-forward action while the current proof source is green.",
            "next_action": "Monitor only; reopen a repair lane only if the live proof source regresses.",
            "validation_command": old.get("validation_command"),
            "proof_artifacts": proof_artifacts,
            "status": "complete",
            "carry_forward": False,
            "resolution_reason": reason,
            "follow_up": with_follow_up_class({
                "status": "monitor_only_drift_currently_absent",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Current proof is green; prior monitor-only row is closed as non-actionable visibility.",
                "proof": proof_artifacts,
            }),
            "prior_event_id": old.get("event_id"),
            "prior_event_fingerprint": old.get("event_fingerprint"),
        })
        rows.append(row)
    return rows


def standing_policy_resolution_events(existing: list[dict[str, Any]], queue: dict[str, Any], otel: dict[str, Any]) -> list[dict[str, Any]]:
    """Close older pre-canonical standing-policy rows without rewriting history."""
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        synthetic = dict(old)
        state = standing_state_for_row(synthetic)
        if state != "standing_policy":
            continue
        source_type = str(old.get("source_type") or "wf74_improvement_opportunity")
        source_path = source_path_for_type(source_type)
        row = event_base(source_type, source_path, current_source_generated_at(source_type, queue, otel), str(old.get("source_key") or "unknown"))
        proof_artifacts = sorted({rel(source_path), *[str(item) for item in as_list(old.get("proof_artifacts")) if item]})
        row.update({
            "category": old.get("category"),
            "title": old.get("title"),
            "priority": old.get("priority"),
            "severity": "standing_policy",
            "signal": "standing_policy_not_actionable_improvement",
            "decision": "resolved_as_standing_policy",
            "recommended_action": old.get("recommended_action") or "Keep the policy visible, but do not treat it as an actionable improvement row.",
            "next_action": old.get("next_action") or old.get("recommended_action"),
            "validation_command": old.get("validation_command"),
            "proof_artifacts": proof_artifacts,
            "status": "complete",
            "carry_forward": False,
            "standing_state": "standing_policy",
            "sla_exempt": True,
            "resolution_reason": "standing_policy_not_actionable_improvement",
            "follow_up": with_follow_up_class({
                "status": "standing_policy",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Older recurring row reclassified as permanent guardrail/policy visibility, not actionable improvement debt.",
                "proof": proof_artifacts,
            }),
            "prior_event_id": old.get("event_id"),
            "prior_event_fingerprint": old.get("event_fingerprint"),
        })
        rows.append(row)
    return rows


def stale_source_resolution_events(
    existing: list[dict[str, Any]],
    current_open_events: list[dict[str, Any]],
    queue: dict[str, Any],
    otel: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Close old carry-forward rows when the latest source no longer emits them.

    The ledger is append-only, so the close is itself an event for the same
    source_type/source_key. This prevents stale resolved opportunities from
    remaining overdue forever.
    """
    current_keys = {
        (str(row.get("source_type")), str(row.get("source_key")))
        for row in current_open_events
        if row.get("status") == "open" and row.get("carry_forward") is not False
    }
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        source_type = str(old.get("source_type") or "")
        source_key = str(old.get("source_key") or "")
        if source_type not in {"wf74_improvement_opportunity", "otel_learning_loop_recommendation"}:
            continue
        if source_key == "code_mutation-eaa17861f4c9":
            continue
        if old.get("decision") == "follow_up_required_before_closure":
            continue
        if (source_type, source_key) in current_keys:
            continue
        follow_up = closure_follow_up(old, current_open_events, manifest)
        if follow_up.get("required"):
            rows.append(followup_required_event(old, queue, otel))
            continue
        source_path = source_path_for_type(source_type)
        row = event_base(source_type, source_path, current_source_generated_at(source_type, queue, otel), source_key)
        row.update({
            "category": old.get("category"),
            "title": old.get("title"),
            "priority": old.get("priority"),
            "severity": "resolved",
            "signal": "source_no_longer_emits_candidate",
            "decision": "resolved_by_latest_source_absence",
            "recommended_action": "No carry-forward action while the latest source no longer emits this candidate.",
            "next_action": "Monitor future source runs; reopen only if the candidate reappears.",
            "validation_command": old.get("validation_command"),
            "proof_artifacts": [rel(source_path)],
            "status": "complete",
            "carry_forward": False,
            "resolution_reason": "latest_source_no_longer_emits_candidate",
            "follow_up": follow_up,
        })
        rows.append(row)
    return rows


def skill_workshop_manifest() -> dict[str, Any]:
    return as_dict(load_json_artifact(SKILL_WORKSHOP_MANIFEST))


def implementation_friction_proposal_exists(manifest: dict[str, Any]) -> dict[str, Any] | None:
    for proposal in as_list(manifest.get("proposals")):
        if not isinstance(proposal, dict):
            continue
        if proposal.get("skillKey") != "implementation-friction-closeout":
            continue
        if proposal.get("status") not in {"pending", "applied"}:
            continue
        if proposal.get("scanState") not in {None, "clean"}:
            continue
        return proposal
    return None


def skill_proposal_audit(manifest: dict[str, Any]) -> dict[str, Any]:
    proposals = [as_dict(row) for row in as_list(manifest.get("proposals"))]
    pending = [row for row in proposals if row.get("status") == "pending"]
    applied = [row for row in proposals if row.get("status") == "applied"]
    relevant_pending = [
        row for row in pending
        if any(
            token in " ".join(str(row.get(key) or "") for key in ("id", "skillKey", "description", "title")).casefold()
            for token in (
                "wf74",
                "self-improvement",
                "implementation-friction",
                "cron-automation",
                "automation-hardening",
                "disciplined-implementation",
                "pm-department",
            )
        )
    ]
    return {
        "schema": "veritas.improvement_ledger_skill_proposal_audit.v1",
        "manifest_path": rel(SKILL_WORKSHOP_MANIFEST),
        "proposal_count": len(proposals),
        "pending_count": len(pending),
        "applied_count": len(applied),
        "relevant_pending_count": len(relevant_pending),
        "relevant_pending": [
            {
                "proposal_id": row.get("id"),
                "skill": row.get("skillKey") or row.get("skillName"),
                "description": row.get("description"),
                "status": row.get("status"),
                "scan_state": row.get("scanState"),
                "created_at": row.get("createdAt"),
            }
            for row in relevant_pending[:20]
        ],
        "not_implemented_meaning": (
            "Pending Skill Workshop proposals are scoped durable follow-up, not live skill doctrine. "
            "They remain unimplemented until Randall explicitly asks to apply the specific proposal."
        ),
    }


def matching_open_followup(old: dict[str, Any], current_open_events: list[dict[str, Any]]) -> dict[str, Any] | None:
    old_title = str(old.get("title") or "")
    old_category = str(old.get("category") or "")
    old_source_key = str(old.get("source_key") or "")
    for row in current_open_events:
        if row.get("status") != "open" or row.get("carry_forward") is False:
            continue
        if str(row.get("source_key") or "") == old_source_key:
            return row
        if old_title and str(row.get("title") or "") == old_title:
            return row
    if old_category in {"cron_migration", "workflow_maturity", "finance_mutation", "outcome_measurement", "code_mutation"}:
        category_matches = [
            row for row in current_open_events
            if str(row.get("category") or "") == old_category
            and row.get("status") == "open"
            and row.get("carry_forward") is not False
        ]
        if category_matches:
            return sorted(category_matches, key=lambda row: int(row.get("priority") or 0), reverse=True)[0]
    return None


def closure_follow_up(old: dict[str, Any], current_open_events: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    decision = str(old.get("decision") or "")
    reason = str(old.get("resolution_reason") or "")
    category = str(old.get("category") or "")
    title = str(old.get("title") or "")
    standing_state = standing_state_for_row(old)
    if standing_state == "standing_policy":
        return with_follow_up_class({
            "status": "standing_policy",
            "required": False,
            "implemented_durable_change": False,
            "detail": "Permanent guardrail/policy visibility, not an actionable improvement row.",
            "proof": [old.get("source_artifact"), rel(source_path_for_type(str(old.get("source_type") or "")))],
        })
    if standing_state == "owner_decision_pending":
        return with_follow_up_class({
            "status": "owner_decision_pending",
            "required": False,
            "implemented_durable_change": False,
            "detail": "Owner-gated decision packet; keep one capped row visible and do not mutate collector/config without explicit approval.",
            "proof": [old.get("source_artifact"), rel(source_path_for_type(str(old.get("source_type") or "")))],
        })
    if standing_state == "monitor_only_standing":
        return with_follow_up_class({
            "status": "monitor_only_standing",
            "required": False,
            "implemented_durable_change": False,
            "detail": "Standing monitor-only learning signal; keep one capped row visible without treating it as overdue implementation debt.",
            "proof": [old.get("source_artifact"), rel(source_path_for_type(str(old.get("source_type") or "")))],
        })
    if reason == "latest_wf74_runner_steps_blocked_zero" or decision == "resolved_by_latest_runner":
        return with_follow_up_class({
            "status": "verified_fix",
            "required": False,
            "implemented_durable_change": True,
            "detail": "Latest WF74 collection runner proves zero blocked collection steps.",
            "proof": [rel(WF74_RUNNER)],
        })
    if decision == "resolved_by_pending_skill_workshop_proposal" or reason == "implementation_friction_skill_workshop_proposal_created":
        proposal = implementation_friction_proposal_exists(manifest)
        return with_follow_up_class({
            "status": "pending_skill_proposal",
            "required": False,
            "implemented_durable_change": False,
            "proposal_id": proposal.get("id") if proposal else old.get("proposal_id"),
            "proposal_status": proposal.get("status") if proposal else old.get("proposal_status"),
            "detail": "A Skill Workshop proposal exists, but it is not live doctrine until explicitly applied.",
            "proof": [rel(SKILL_WORKSHOP_MANIFEST)],
        })
    match = matching_open_followup(old, current_open_events)
    if match:
        return with_follow_up_class({
            "status": "superseded_by_open_improvement",
            "required": False,
            "implemented_durable_change": False,
            "successor_source_key": match.get("source_key"),
            "successor_id": match.get("source_key"),
            "successor_artifact": rel(DEFAULT_JSON),
            "successor_artifact_kind": "canonical_open_improvement_row",
            "successor_title": match.get("title"),
            "detail": "The old closed signal is represented by a current open improvement.",
            "proof": [match.get("source_artifact")],
        })
    if category == "collector_config" and "field-depth" in title:
        return with_follow_up_class({
            "status": "owner_packet_ready_not_applied",
            "required": False,
            "implemented_durable_change": False,
            "detail": "The owner-gated packet is a follow-up artifact; collector/config mutation still requires explicit approval.",
            "proof": ["tmp/otel-field-depth-limited-owner-packet.json"],
        })
    if category == "otel_learning_loop" and title == "otel_drift_review":
        return with_follow_up_class({
            "status": "monitor_only_drift_currently_absent",
            "required": False,
            "implemented_durable_change": False,
            "detail": "Latest OTEL learning-loop source no longer emits the drift recommendation; keep monitoring through OTEL ops.",
            "proof": [rel(OTEL_LEARNING_LOOP), "tmp/otel-ops-control.json"],
        })
    return {
        "status": "missing_followup",
        "required": True,
        "implemented_durable_change": False,
        "follow_up_class": "unclassified_missing_followup",
        "detail": "Latest source absence alone is not enough to close a recurring or material improvement.",
        "proof": [],
    }


def needs_followup_before_closure(row: dict[str, Any]) -> bool:
    if row.get("decision") == "follow_up_required_before_closure":
        return False
    if row.get("status") not in {"open", "complete"} and row.get("carry_forward") is False:
        return False
    if row.get("status") == "complete" or row.get("carry_forward") is False:
        if has_durable_follow_up_classification(row):
            return False
        return closure_type(row) == "signal_absence"
    return int(row.get("priority") or 0) >= 64 or int(row.get("recurrence_count") or 0) > 1


def is_closed_event(row: dict[str, Any]) -> bool:
    return row.get("carry_forward") is False or row.get("status") in {"complete", "cancelled", "rejected"}


def has_durable_follow_up_classification(row: dict[str, Any]) -> bool:
    follow_up = as_dict(row.get("follow_up"))
    status = str(follow_up.get("status") or "")
    if not follow_up_class(status):
        return False
    return bool(follow_up.get("follow_up_class") or follow_up_class(status))


def followup_required_event(old: dict[str, Any], queue: dict[str, Any], otel: dict[str, Any]) -> dict[str, Any]:
    source_type = str(old.get("source_type") or "wf74_improvement_opportunity")
    source_path = source_path_for_type(source_type)
    source_generated_at = (
        current_source_generated_at(source_type, queue, otel)
        or old.get("source_generated_at_utc")
        or utc_now()
    )
    row = event_base(source_type, source_path, source_generated_at, str(old.get("source_key") or "unknown"))
    row.update({
        "category": old.get("category"),
        "title": old.get("title"),
        "priority": old.get("priority"),
        "severity": "follow_up_required",
        "signal": "source_absence_without_followup",
        "decision": "follow_up_required_before_closure",
        "recommended_action": "Classify this improvement's durable follow-up before closing it: live code/validator, pending skill proposal, owner-gated packet, successor open item, or explicit monitor-only rationale.",
        "next_action": "Create or identify the follow-up artifact, then rerun improvement_ledger.py so closure can carry durable follow-up status.",
        "validation_command": old.get("validation_command"),
        "proof_artifacts": [rel(source_path)],
        "status": "open",
        "carry_forward": True,
        "closure_blocked_reason": "latest_source_absence_without_followup",
        "prior_resolution_reason": old.get("resolution_reason"),
        "follow_up": {
            "status": "missing_followup",
            "required": True,
            "implemented_durable_change": False,
            "follow_up_class": "unclassified_missing_followup",
        },
    })
    return row


def closure_followup_classification_event(
    old: dict[str, Any],
    queue: dict[str, Any],
    otel: dict[str, Any],
    follow_up: dict[str, Any],
) -> dict[str, Any]:
    source_type = str(old.get("source_type") or "wf74_improvement_opportunity")
    source_path = source_path_for_type(source_type)
    proof_artifacts = sorted({
        *[str(item) for item in as_list(old.get("proof_artifacts")) if item],
        *[str(item) for item in as_list(follow_up.get("proof")) if item],
        rel(source_path),
    })
    source_generated_at = (
        current_source_generated_at(source_type, queue, otel)
        or old.get("source_generated_at_utc")
        or utc_now()
    )
    row = event_base(source_type, source_path, source_generated_at, str(old.get("source_key") or "unknown"))
    row.update({
        "category": old.get("category"),
        "title": old.get("title"),
        "priority": old.get("priority"),
        "severity": "resolved",
        "signal": "closure_followup_classified",
        "decision": old.get("decision") or "resolved_with_durable_followup_classification",
        "recommended_action": old.get("recommended_action") or "Closed with durable follow-up classification.",
        "next_action": old.get("next_action") or "Monitor source packets; reopen only if the underlying signal recurs.",
        "validation_command": old.get("validation_command"),
        "proof_artifacts": proof_artifacts,
        "status": "complete",
        "carry_forward": False,
        "resolution_reason": old.get("resolution_reason") or "durable_followup_classification_repair",
        "follow_up": follow_up,
        "successor_id": follow_up.get("successor_id"),
        "successor_artifact": follow_up.get("successor_artifact"),
        "successor_artifact_kind": follow_up.get("successor_artifact_kind"),
        "prior_event_id": old.get("event_id"),
        "prior_event_fingerprint": old.get("event_fingerprint"),
    })
    return row


def successor_fields_for_closed_row(row: dict[str, Any]) -> dict[str, str]:
    follow_up = as_dict(row.get("follow_up"))
    status = str(follow_up.get("status") or "")
    triage_state = str(row.get("triage_action_state") or "")
    if row.get("successor_artifact") or follow_up.get("successor_artifact"):
        return {}
    if status == "superseded_by_open_improvement":
        detail = str(follow_up.get("detail") or row.get("closure_reason") or "")
        parsed_successor_id = ""
        marker = "represented by open source_key "
        if marker in detail:
            parsed_successor_id = detail.split(marker, 1)[1].split(";", 1)[0].strip()
        successor_id = (
            follow_up.get("successor_id")
            or row.get("successor_id")
            or follow_up.get("successor_source_key")
            or row.get("successor_source_key")
            or parsed_successor_id
        )
        if not successor_id:
            return {}
        return {
            "successor_id": str(successor_id),
            "successor_artifact": rel(DEFAULT_JSON),
            "successor_artifact_kind": "canonical_open_improvement_row",
        }
    if is_finance_response_quality_stale_row(row):
        return {
            "successor_id": "wf85-source-open-repair-queue",
            "successor_artifact": rel(WF88_OS2_CONTROL),
            "successor_artifact_kind": "wf88_canonical_action_state",
        }
    if triage_state == "close_with_threshold_proof":
        return {
            "successor_id": "wf88-learning-loop-measurement",
            "successor_artifact": rel(WF88_OS2_CONTROL),
            "successor_artifact_kind": "wf88_canonical_action_state",
        }
    if triage_state in {
        "close_with_clean_followthrough_proof",
        "close_as_currently_absent_drag",
        "close_with_routing_proof",
    }:
        return {
            "successor_id": "improvement-ledger-open-followups",
            "successor_artifact": rel(WF88_OS2_CONTROL),
            "successor_artifact_kind": "wf88_canonical_action_state",
        }
    return {}


def closure_successor_artifact_repair_event(
    old: dict[str, Any],
    queue: dict[str, Any],
    otel: dict[str, Any],
    successor: dict[str, str],
) -> dict[str, Any]:
    source_type = str(old.get("source_type") or "wf74_improvement_opportunity")
    source_path = source_path_for_type(source_type)
    successor_artifact = successor.get("successor_artifact")
    proof_artifacts = sorted({
        *[str(item) for item in as_list(old.get("proof_artifacts")) if item],
        *[str(item) for item in as_list(as_dict(old.get("follow_up")).get("proof")) if item],
        *([successor_artifact] if successor_artifact else []),
        rel(source_path),
    })
    follow_up = dict(as_dict(old.get("follow_up")))
    follow_up.update(successor)
    row = event_base(source_type, source_path, current_source_generated_at(source_type, queue, otel), str(old.get("source_key") or "unknown"))
    row.update({
        "category": old.get("category"),
        "title": old.get("title"),
        "priority": old.get("priority"),
        "severity": "resolved",
        "signal": "closure_successor_artifact_classified",
        "decision": old.get("decision") or "resolved_with_successor_artifact",
        "recommended_action": old.get("recommended_action") or "Closed with durable successor artifact classification.",
        "next_action": old.get("next_action") or "Use successor_artifact to inspect the canonical action row before reopening.",
        "validation_command": old.get("validation_command"),
        "proof_artifacts": proof_artifacts,
        "status": "complete",
        "carry_forward": False,
        "resolution_reason": old.get("resolution_reason") or "successor_artifact_classification_repair",
        "follow_up": with_follow_up_class(follow_up),
        "triage_action_state": old.get("triage_action_state"),
        "successor_id": successor.get("successor_id"),
        "successor_artifact": successor_artifact,
        "successor_artifact_kind": successor.get("successor_artifact_kind"),
        "prior_event_id": old.get("event_id"),
        "prior_event_fingerprint": old.get("event_fingerprint"),
    })
    return row


def repair_missing_successor_artifact_events(
    existing: list[dict[str, Any]],
    queue: dict[str, Any],
    otel: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if not is_closed_event(old):
            continue
        if str(old.get("resolution_reason") or "") not in {
            "wf88_followup_debt_triage",
            "finance_response_quality_current_proof_clean",
            "latest_source_no_longer_emits_candidate",
        }:
            continue
        successor = successor_fields_for_closed_row(old)
        if not successor:
            continue
        rows.append(closure_successor_artifact_repair_event(old, queue, otel, successor))
    return rows


def repair_unclassified_closure_events(
    existing: list[dict[str, Any]],
    current_open_events: list[dict[str, Any]],
    queue: dict[str, Any],
    otel: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if not is_closed_event(old):
            continue
        if has_durable_follow_up_classification(old):
            continue
        follow_up = closure_follow_up(old, current_open_events, manifest)
        if follow_up.get("required"):
            rows.append(followup_required_event(old, queue, otel))
        else:
            rows.append(closure_followup_classification_event(old, queue, otel, follow_up))
    return rows


def standing_followup_required_resolution_events(
    existing: list[dict[str, Any]],
    queue: dict[str, Any],
    otel: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        follow_up = as_dict(old.get("follow_up"))
        if old.get("decision") != "follow_up_required_before_closure" and follow_up.get("required") is not True:
            continue
        state = standing_state_for_row(old)
        if state not in STANDING_STATES:
            continue
        if state == "standing_policy":
            resolved_follow_up = with_follow_up_class({
                "status": "standing_policy",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Permanent guardrail/policy visibility, not an actionable improvement row.",
                "proof": [old.get("source_artifact"), rel(source_path_for_type(str(old.get("source_type") or "")))],
            })
        elif state == "owner_decision_pending":
            resolved_follow_up = with_follow_up_class({
                "status": "owner_decision_pending",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Owner-gated decision packet; keep one capped row visible and do not mutate collector/config without explicit approval.",
                "proof": [old.get("source_artifact"), rel(source_path_for_type(str(old.get("source_type") or "")))],
            })
        else:
            resolved_follow_up = with_follow_up_class({
                "status": "monitor_only_standing",
                "required": False,
                "implemented_durable_change": False,
                "detail": "Standing monitor-only learning signal; keep one capped row visible without treating it as overdue implementation debt.",
                "proof": [old.get("source_artifact"), rel(source_path_for_type(str(old.get("source_type") or "")))],
            })
        row = closure_followup_classification_event(old, queue, otel, resolved_follow_up)
        row.update({
            "severity": "resolved",
            "signal": "standing_followup_required_classified",
            "decision": f"resolved_as_{state}",
            "recommended_action": old.get("recommended_action") or "Resolved as standing monitor-only or owner-gated visibility.",
            "next_action": old.get("next_action") or "Monitor source packets; reopen only if the underlying signal recurs as actionable debt.",
            "resolution_reason": "standing_followup_classification_repair",
            "standing_state": state,
            "sla_exempt": True,
        })
        rows.append(row)
    return rows


def skill_workshop_resolution_events(existing: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    proposal = implementation_friction_proposal_exists(manifest)
    if not proposal:
        return []
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        if old.get("category") != "skill_application":
            continue
        if old.get("title") != "Convert repeated coding friction into a Skill Workshop proposal":
            continue
        row = event_base(
            str(old.get("source_type") or "wf74_improvement_opportunity"),
            SKILL_WORKSHOP_MANIFEST,
            utc_now(),
            str(old.get("source_key")),
        )
        row.update({
            "category": old.get("category"),
            "title": old.get("title"),
            "priority": old.get("priority"),
            "severity": "resolved",
            "signal": "skill_workshop_proposal_created",
            "decision": "resolved_by_pending_skill_workshop_proposal",
            "recommended_action": "Keep the Skill Workshop proposal pending unless Randall explicitly approves applying it.",
            "next_action": "Inspect or apply the specific proposal only on explicit owner request.",
            "validation_command": "openclaw skills check",
            "proof_artifacts": [rel(SKILL_WORKSHOP_MANIFEST)],
            "proposal_id": proposal.get("id"),
            "proposal_status": proposal.get("status"),
            "status": "complete",
            "carry_forward": False,
            "resolution_reason": "implementation_friction_skill_workshop_proposal_created",
            "follow_up": with_follow_up_class({
                "status": "pending_skill_proposal",
                "required": False,
                "implemented_durable_change": False,
                "proposal_id": proposal.get("id"),
            }),
        })
        rows.append(row)
    return rows


def wf88_followup_triage_resolution_events(
    existing: list[dict[str, Any]],
    triage: dict[str, Any],
    queue: dict[str, Any],
    otel: dict[str, Any],
) -> list[dict[str, Any]]:
    validation_status = as_dict(triage.get("validation")).get("status")
    if not triage or validation_status == "blocked":
        return []
    closure_items = {
        (str(item.get("source_type")), str(item.get("source_key"))): item
        for item in (as_dict(row) for row in as_list(triage.get("closure_items")))
        if item.get("closure_allowed") is True
        and str(item.get("closure_status") or "") in TRIAGE_CLOSURE_STATUSES
        and as_list(item.get("proof_artifacts"))
    }
    if not closure_items:
        return []
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        follow_up = as_dict(old.get("follow_up"))
        if old.get("decision") != "follow_up_required_before_closure" and follow_up.get("required") is not True:
            continue
        source_type = str(old.get("source_type") or "")
        source_key = str(old.get("source_key") or "")
        triage_item = closure_items.get((source_type, source_key))
        if not triage_item:
            continue
        status = str(triage_item.get("closure_status") or "")
        source_path = source_path_for_type(source_type)
        row = event_base(source_type, source_path, current_source_generated_at(source_type, queue, otel), source_key)
        proof_artifacts = sorted({rel(WF88_FOLLOWUP_TRIAGE), *[str(item) for item in as_list(triage_item.get("proof_artifacts"))]})
        successor_id = triage_item.get("successor_id") or triage_item.get("successor_source_key")
        successor_artifact = triage_item.get("successor_artifact")
        successor_artifact_kind = triage_item.get("successor_artifact_kind")
        row.update({
            "category": old.get("category"),
            "title": old.get("title"),
            "priority": old.get("priority"),
            "severity": "resolved",
            "signal": "wf88_followup_debt_triage_closure",
            "decision": "resolved_by_wf88_followup_debt_triage",
            "recommended_action": triage_item.get("recommended_next_action") or "No carry-forward action after WF88 follow-up debt triage closure proof.",
            "next_action": triage_item.get("recommended_next_action") or "Monitor source packets; reopen only if the underlying signal recurs.",
            "validation_command": old.get("validation_command"),
            "proof_artifacts": proof_artifacts,
            "status": "complete",
            "carry_forward": False,
            "resolution_reason": "wf88_followup_debt_triage",
            "follow_up": with_follow_up_class({
                "status": status,
                "required": False,
                "implemented_durable_change": status in {"verified_fix", "applied_skill_proposal"},
                "detail": triage_item.get("closure_reason"),
                "proof": proof_artifacts,
                "source_packet": rel(WF88_FOLLOWUP_TRIAGE),
                "successor_id": successor_id,
                "successor_artifact": successor_artifact,
                "successor_artifact_kind": successor_artifact_kind,
            }),
            "triage_action_state": triage_item.get("action_state"),
            "successor_id": successor_id,
            "successor_artifact": successor_artifact,
            "successor_artifact_kind": successor_artifact_kind,
        })
        rows.append(row)
    return rows


def wf88_followup_triage_active_events(
    existing: list[dict[str, Any]],
    triage: dict[str, Any],
    queue: dict[str, Any],
    otel: dict[str, Any],
) -> list[dict[str, Any]]:
    validation_status = as_dict(triage.get("validation")).get("status")
    if not triage or validation_status == "blocked":
        return []
    active_items = {
        (str(item.get("source_type")), str(item.get("source_key"))): item
        for item in (as_dict(row) for row in as_list(triage.get("active_followup_items")))
        if item.get("closure_allowed") is not True
        and str(item.get("action_state") or "")
        and as_list(item.get("proof_artifacts"))
    }
    if not active_items:
        return []
    rows: list[dict[str, Any]] = []
    latest_existing = latest_by_source_key([row for row in existing if row.get("schema") == EVENT_SCHEMA])
    for old in latest_existing:
        if old.get("carry_forward") is False or old.get("status") in {"complete", "cancelled", "rejected"}:
            continue
        source_type = str(old.get("source_type") or "")
        source_key = str(old.get("source_key") or "")
        triage_item = active_items.get((source_type, source_key))
        if not triage_item:
            continue
        source_path = source_path_for_type(source_type)
        proof_artifacts = sorted({rel(WF88_FOLLOWUP_TRIAGE), *[str(item) for item in as_list(triage_item.get("proof_artifacts"))]})
        successor_id = triage_item.get("successor_id") or triage_item.get("successor_source_key")
        successor_artifact = triage_item.get("successor_artifact")
        successor_artifact_kind = triage_item.get("successor_artifact_kind")
        row = event_base(source_type, source_path, current_source_generated_at(source_type, queue, otel), source_key)
        row.update({
            "category": old.get("category") or triage_item.get("category"),
            "title": old.get("title") or triage_item.get("title"),
            "priority": old.get("priority") or triage_item.get("priority"),
            "severity": "follow_up_required",
            "signal": "wf88_followup_debt_triage_active",
            "decision": "follow_up_required_before_closure",
            "recommended_action": triage_item.get("recommended_next_action") or old.get("recommended_action"),
            "next_action": triage_item.get("recommended_next_action") or old.get("next_action"),
            "validation_command": old.get("validation_command"),
            "proof_artifacts": proof_artifacts,
            "status": "open",
            "carry_forward": True,
            "closure_blocked_reason": "wf88_followup_debt_triage_kept_open",
            "follow_up": {
                "status": triage_item.get("action_state"),
                "required": True,
                "implemented_durable_change": False,
                "detail": triage_item.get("closure_reason"),
                "proof": proof_artifacts,
                "source_packet": rel(WF88_FOLLOWUP_TRIAGE),
                "successor_id": successor_id,
                "successor_artifact": successor_artifact,
                "successor_artifact_kind": successor_artifact_kind,
            },
            "triage_action_state": triage_item.get("action_state"),
            "successor_id": successor_id,
            "successor_artifact": successor_artifact,
            "successor_artifact_kind": successor_artifact_kind,
        })
        rows.append(row)
    return rows


def latest_by_source_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    first_seen: dict[tuple[str, str], datetime] = {}
    last_seen: dict[tuple[str, str], datetime] = {}
    occurrence_counts: Counter[tuple[str, str]] = Counter()
    unique_fingerprints: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        key = (str(row.get("source_type")), str(row.get("source_key")))
        occurrence_counts[key] += 1
        unique_fingerprints.setdefault(key, set()).add(str(row.get("event_fingerprint") or row.get("event_id") or "unknown"))
        seen = parse_utc(row.get("recorded_at_utc")) or parse_utc(row.get("source_generated_at_utc"))
        if seen:
            if key not in first_seen or seen < first_seen[key]:
                first_seen[key] = seen
            if key not in last_seen or seen > last_seen[key]:
                last_seen[key] = seen
        existing = latest.get(key)
        if not existing or str(row.get("source_generated_at_utc") or row.get("recorded_at_utc") or "") >= str(existing.get("source_generated_at_utc") or existing.get("recorded_at_utc") or ""):
            latest[key] = row
    now = datetime.now(timezone.utc)
    for key, row in latest.items():
        opened = first_seen.get(key) or parse_utc(row.get("recorded_at_utc")) or now
        last = last_seen.get(key) or parse_utc(row.get("recorded_at_utc")) or opened
        age_hours = max(0.0, (now - opened).total_seconds() / 3600)
        priority = int(row.get("priority") or 0)
        sla_days = 1 if priority >= 90 else (3 if priority >= 80 else 7)
        standing_state = str(row.get("standing_state") or "")
        if row.get("sla_exempt") is True or standing_state in STANDING_STATES:
            ratio = 0.0
            sla_status = standing_state or "standing"
        else:
            ratio = age_hours / (sla_days * 24)
            if ratio >= 1:
                sla_status = "overdue"
            elif ratio >= 0.75:
                sla_status = "due_soon"
            else:
                sla_status = "within_sla"
        row["opened_at_utc"] = opened.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row["last_seen_at_utc"] = last.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row["age_hours"] = round(age_hours, 2)
        row["sla_days"] = sla_days
        row["sla_status"] = sla_status
        row["sla_ratio"] = round(ratio, 4)
        row["recurrence_count"] = occurrence_counts.get(key, 1)
        row["distinct_state_count"] = len(unique_fingerprints.get(key, set()))
    return sorted(latest.values(), key=lambda row: (int(row.get("priority") or 0), str(row.get("source_generated_at_utc") or "")), reverse=True)


def closure_type(row: dict[str, Any]) -> str:
    reason = str(row.get("resolution_reason") or "")
    decision = str(row.get("decision") or "")
    follow_up = as_dict(row.get("follow_up"))
    if reason == "wf88_followup_debt_triage" or decision == "resolved_by_wf88_followup_debt_triage":
        status = str(follow_up.get("status") or "")
        if status in {"verified_fix", "applied_skill_proposal"}:
            return "applied_fix"
        if status == "pending_skill_proposal":
            return "pending_skill_proposal"
        if status == "superseded_by_open_improvement":
            return "superseded"
        if status == "owner_packet_ready_not_applied":
            return "owner_gated_packet"
        if status == "monitor_only_drift_currently_absent":
            return "monitor_only"
        return "other"
    if reason == "latest_source_no_longer_emits_candidate" or decision == "resolved_by_latest_source_absence":
        if follow_up.get("status") == "superseded_by_open_improvement":
            return "superseded"
        if follow_up.get("status") == "owner_packet_ready_not_applied":
            return "owner_gated_packet"
        if follow_up.get("status") == "monitor_only_drift_currently_absent":
            return "monitor_only"
        return "signal_absence"
    if reason in {
        "latest_wf74_runner_steps_blocked_zero",
        "finance_response_quality_current_proof_clean",
    }:
        return "applied_fix"
    if reason in {
        "standing_policy_not_actionable_improvement",
        "resolved_by_cron_control_green_proof",
        "resolved_by_otel_ops_green_proof",
    }:
        return "monitor_only"
    if reason == "implementation_friction_skill_workshop_proposal_created" or decision == "resolved_by_pending_skill_workshop_proposal":
        return "pending_skill_proposal"
    if decision == "resolved_by_latest_runner":
        return "applied_fix"
    return "other"


def learning_loop_kpis(open_rows: list[dict[str, Any]], closed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_latest = len(open_rows) + len(closed_rows)
    high_priority_overdue = [
        row for row in open_rows
        if int(row.get("priority") or 0) >= 80 and row.get("sla_status") == "overdue"
    ]
    recurring_open = [row for row in open_rows if int(row.get("recurrence_count") or 0) > 1]
    closure_rate = round(len(closed_rows) / total_latest, 4) if total_latest else None
    closure_counts = Counter(closure_type(row) for row in closed_rows)
    applied_fix_closed = closure_counts.get("applied_fix", 0)
    signal_absence_closed = closure_counts.get("signal_absence", 0)
    pending_skill_proposal_closed = closure_counts.get("pending_skill_proposal", 0)
    superseded_closed = closure_counts.get("superseded", 0)
    owner_gated_packet_closed = closure_counts.get("owner_gated_packet", 0)
    monitor_only_closed = closure_counts.get("monitor_only", 0)
    other_closed = closure_counts.get("other", 0)
    if high_priority_overdue:
        anti_theater_status = "blocked_by_overdue_backlog"
    elif not closed_rows:
        anti_theater_status = "proposal_loop_active_no_closure_proof"
    else:
        anti_theater_status = "proposal_loop_with_closure_proof"
    return {
        "schema": "veritas.learning_loop_kpis.v1",
        "anti_theater_status": anti_theater_status,
        "latest_open_count": len(open_rows),
        "latest_closed_count": len(closed_rows),
        "closure_rate": closure_rate,
        "closure_type_counts": dict(sorted(closure_counts.items())),
        "applied_fix_closed_count": applied_fix_closed,
        "signal_absence_closed_count": signal_absence_closed,
        "pending_skill_proposal_closed_count": pending_skill_proposal_closed,
        "superseded_closed_count": superseded_closed,
        "owner_gated_packet_closed_count": owner_gated_packet_closed,
        "monitor_only_closed_count": monitor_only_closed,
        "other_closed_count": other_closed,
        "applied_fix_closure_rate": round(applied_fix_closed / total_latest, 4) if total_latest else None,
        "signal_absence_closure_rate": round(signal_absence_closed / total_latest, 4) if total_latest else None,
        "pending_skill_proposal_closure_rate": round(pending_skill_proposal_closed / total_latest, 4) if total_latest else None,
        "recurring_open_count": len(recurring_open),
        "high_priority_overdue_open_count": len(high_priority_overdue),
        "top_recurring_open_titles": [row.get("title") for row in recurring_open[:5]],
        "meaning": (
            "WF74 is only real learning when proposals either close, become validator/skill/code changes, "
            "or remain explicitly tracked as overdue debt. Open proposals alone are not proof of improvement."
        ),
    }


def build_payload(ledger_path: Path, append: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    queue = as_dict(load_json_artifact(WF74_QUEUE))
    otel = as_dict(load_json_artifact(OTEL_LEARNING_LOOP))
    runner = as_dict(load_json_artifact(WF74_RUNNER))
    finance_slice = as_dict(load_json_artifact(FINANCE_RESPONSE_QUALITY_SLICE))
    repair_loop = as_dict(load_json_artifact(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP))
    wf85_reconciliation = as_dict(load_json_artifact(WF85_SOURCE_OPEN_RECONCILIATION))
    skill_manifest = skill_workshop_manifest()
    followup_triage = as_dict(load_json_artifact(WF88_FOLLOWUP_TRIAGE))
    existing = read_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    existing_fingerprints = {str(row.get("event_fingerprint")) for row in existing if row.get("event_fingerprint")}
    current_open_events = queue_events(queue) + otel_events(otel)
    candidate_events = finalize_event_ids(
        current_open_events
        + resolution_events(runner)
        + finance_response_quality_resolution_events(
            existing,
            current_open_events,
            runner,
            finance_slice,
            repair_loop,
            wf85_reconciliation,
        )
        + stale_source_resolution_events(existing, current_open_events, queue, otel, skill_manifest)
        + repair_unclassified_closure_events(existing, current_open_events, queue, otel, skill_manifest)
        + standing_followup_required_resolution_events(existing + current_open_events, queue, otel)
        + repair_missing_successor_artifact_events(existing, queue, otel)
        + skill_workshop_resolution_events(existing + current_open_events, skill_manifest)
        + wf88_followup_triage_resolution_events(existing + current_open_events, followup_triage, queue, otel)
        + wf88_followup_triage_active_events(existing + current_open_events, followup_triage, queue, otel)
        + standing_policy_resolution_events(existing, queue, otel)
        + monitor_only_resolution_events(existing, queue, otel)
    )
    new_events = [
        row for row in candidate_events
        if row.get("event_id") not in existing_ids
        and row.get("event_fingerprint") not in existing_fingerprints
    ]
    if append:
        append_jsonl(ledger_path, new_events)
    all_rows = existing + candidate_events
    latest = latest_by_source_key([row for row in all_rows if row.get("schema") == EVENT_SCHEMA])
    open_rows = [row for row in latest if row.get("carry_forward") is not False and row.get("status") not in {"complete", "cancelled", "rejected"}]
    closed_rows = [row for row in latest if row.get("carry_forward") is False or row.get("status") in {"complete", "cancelled", "rejected"}]
    event_history_rows = [row for row in read_jsonl(ledger_path) if row.get("schema") == EVENT_SCHEMA] if append else [row for row in all_rows if row.get("schema") == EVENT_SCHEMA]
    historical_open_rows = [
        row for row in event_history_rows
        if row.get("carry_forward") is not False and row.get("status") not in {"complete", "cancelled", "rejected"}
    ]
    historical_closed_rows = [
        row for row in event_history_rows
        if row.get("carry_forward") is False or row.get("status") in {"complete", "cancelled", "rejected"}
    ]
    title_counts = Counter(str(row.get("title") or "untitled") for row in event_history_rows)
    duplicate_title_rows = sum(count - 1 for count in title_counts.values() if count > 1)
    standing_policy_rows = [row for row in latest if row.get("standing_state") == "standing_policy"]
    owner_decision_pending_rows = [row for row in latest if row.get("standing_state") == "owner_decision_pending"]
    monitor_only_standing_rows = [row for row in latest if row.get("standing_state") == "monitor_only_standing"]
    actionable_open_rows = [row for row in open_rows if row.get("standing_state") not in STANDING_STATES]
    high_priority = [row for row in open_rows if int(row.get("priority") or 0) >= 80]
    overdue = [row for row in open_rows if row.get("sla_status") == "overdue"]
    due_soon = [row for row in open_rows if row.get("sla_status") == "due_soon"]
    high_priority_overdue = [row for row in high_priority if row.get("sla_status") == "overdue"]
    if high_priority_overdue:
        escalation_level = "high_priority_overdue"
    elif overdue:
        escalation_level = "overdue"
    elif due_soon:
        escalation_level = "due_soon"
    elif high_priority:
        escalation_level = "high_priority_open"
    else:
        escalation_level = "normal"
    category_counts = Counter(str(row.get("category") or "unknown") for row in open_rows)
    source_counts = Counter(str(row.get("source_type") or "unknown") for row in open_rows)
    followup_required_open = [
        row for row in open_rows
        if row.get("decision") == "follow_up_required_before_closure"
        or as_dict(row.get("follow_up")).get("required") is True
    ]
    unclassified_closed_followup = [
        row for row in closed_rows
        if not has_durable_follow_up_classification(row)
    ]
    skill_audit = skill_proposal_audit(skill_manifest)
    kpis = learning_loop_kpis(open_rows, closed_rows)
    privacy_findings = scan_forbidden({"new_events": new_events, "latest_open_improvements": open_rows})
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Append-only improvement ledger plus current carry-forward queue for new-session pickup.",
        "mode": "append" if append else "check",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "ledger_path": rel(ledger_path),
        "source_status": [
            source_status(WF74_QUEUE),
            source_status(OTEL_LEARNING_LOOP),
            source_status(WF74_RUNNER),
            source_status(FINANCE_RESPONSE_QUALITY_SLICE),
            source_status(FINANCE_RESPONSE_QUALITY_REPAIR_LOOP),
            source_status(WF85_SOURCE_OPEN_RECONCILIATION),
            source_status(WF88_OS2_CONTROL),
            source_status(SKILL_WORKSHOP_MANIFEST),
            source_status(WF88_FOLLOWUP_TRIAGE),
        ],
        "summary": {
            "ledger_row_count": len([row for row in read_jsonl(ledger_path) if row.get("schema") == EVENT_SCHEMA]) if append else len([row for row in all_rows if row.get("schema") == EVENT_SCHEMA]),
            "historical_open_row_count": len(historical_open_rows),
            "historical_closed_row_count": len(historical_closed_rows),
            "historical_duplicate_title_extra_count": duplicate_title_rows,
            "history_metric_note": "Raw append-only rows are audit history; current debt is latest_open_count/actionable_open_count, not historical_open_row_count.",
            "candidate_event_count": len(candidate_events),
            "candidate_new_event_count": len(new_events),
            "would_append_event_count": 0 if append else len(new_events),
            "appended_event_count": len(new_events) if append else 0,
            "latest_open_count": len(open_rows),
            "latest_closed_count": len(closed_rows),
            "actionable_open_count": len(actionable_open_rows),
            "standing_policy_count": len(standing_policy_rows),
            "owner_decision_pending_count": len(owner_decision_pending_rows),
            "monitor_only_standing_count": len(monitor_only_standing_rows),
            "recurring_open_count": kpis["recurring_open_count"],
            "applied_fix_closed_count": kpis["applied_fix_closed_count"],
            "signal_absence_closed_count": kpis["signal_absence_closed_count"],
            "pending_skill_proposal_closed_count": kpis["pending_skill_proposal_closed_count"],
            "superseded_closed_count": kpis["superseded_closed_count"],
            "owner_gated_packet_closed_count": kpis["owner_gated_packet_closed_count"],
            "monitor_only_closed_count": kpis["monitor_only_closed_count"],
            "other_closed_count": kpis["other_closed_count"],
            "followup_required_open_count": len(followup_required_open),
            "unclassified_closed_followup_count": len(unclassified_closed_followup),
            "pending_skill_proposal_count": skill_audit["pending_count"],
            "relevant_pending_skill_proposal_count": skill_audit["relevant_pending_count"],
            "high_priority_open_count": len(high_priority),
            "overdue_open_count": len(overdue),
            "due_soon_open_count": len(due_soon),
            "high_priority_overdue_open_count": len(high_priority_overdue),
            "escalation_level": escalation_level,
            "by_category": dict(sorted(category_counts.items())),
            "by_source_type": dict(sorted(source_counts.items())),
            "top_improvement_title": open_rows[0].get("title") if open_rows else None,
            "top_improvement_next_action": open_rows[0].get("next_action") if open_rows else None,
            "top_improvement_age_hours": open_rows[0].get("age_hours") if open_rows else None,
            "top_improvement_sla_status": open_rows[0].get("sla_status") if open_rows else None,
            "privacy_scan_status": "ok" if not privacy_findings else "blocked",
        },
        "learning_loop_kpis": kpis,
        "skill_proposal_audit": skill_audit,
        "latest_open_improvements": open_rows[:20],
        "latest_closed_improvements": closed_rows[:20],
        "followup_required_improvements": followup_required_open[:20],
        "unclassified_closed_followup_improvements": unclassified_closed_followup[:20],
        "recommendations": [
            {
                "id": "load_improvement_ledger_on_startup",
                "decision": "hard_route_new_sessions_to_improvement_ledger",
                "next_action": "New sessions should inspect tmp/improvement-ledger-current.json after future-session startup before recommending OS/WF74 improvements.",
                "proof": rel(DEFAULT_JSON),
            },
            {
                "id": "use_ledger_not_chat_memory",
                "decision": "treat_chat_context_as_secondary",
                "next_action": "Use data/state-history/improvement-ledger.jsonl and current packet for improvement carry-forward; chat history is not durable authority.",
                "proof": rel(ledger_path),
            },
            {
                "id": "fallback_to_jsonl_tail_when_current_packet_stale",
                "decision": "avoid_silent_stale_carry_forward",
                "next_action": "If tmp/improvement-ledger-current.json is stale or missing, rebuild/fallback from the append-only JSONL tail before giving new-session improvement advice.",
                "proof": rel(ledger_path),
            },
        ],
        "next_safe_action": "Load this packet in new sessions, review top open improvements, and route implementation through lane register plus validators before applying changes.",
        "blocked_actions": [
            "no auto-apply from ledger",
            "no skill approval/application from ledger",
            "no collector/runtime/config mutation from ledger",
            "no finance canon/portfolio/cash/sizing mutation from ledger",
            "no paper/live/account action from ledger",
            "no owner approval inference from ledger",
        ],
        "privacy_scan": {
            "status": "ok" if not privacy_findings else "blocked",
            "finding_count": len(privacy_findings),
            "findings": privacy_findings,
        },
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload, new_events


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    summary = as_dict(payload.get("summary"))
    if summary.get("privacy_scan_status") != "ok":
        errors.append("privacy scan not ok")
    if int(summary.get("latest_open_count") or 0) <= 0:
        warnings.append("no open improvements found")
    kpis = as_dict(payload.get("learning_loop_kpis"))
    if kpis.get("anti_theater_status") == "proposal_loop_active_no_closure_proof":
        warnings.append("learning loop has no closure proof yet")
    if int(summary.get("followup_required_open_count") or 0) > 0:
        warnings.append("open improvements require follow-up classification before closure")
    if int(summary.get("unclassified_closed_followup_count") or 0) > 0:
        errors.append("closed improvements lack durable follow-up classification")
    for row in payload.get("latest_closed_improvements", []):
        follow_up = as_dict(as_dict(row).get("follow_up"))
        if follow_up.get("required") is True:
            errors.append(f"closed improvement still requires follow-up: {as_dict(row).get('source_key')}")
        if not has_durable_follow_up_classification(as_dict(row)):
            errors.append(f"closed improvement missing durable follow-up class: {as_dict(row).get('source_key')}")
    for source in payload.get("source_status", []):
        if not source.get("exists"):
            warnings.append(f"missing source: {source.get('path')}")
    return {"status": "critical" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Improvement Ledger Current",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Ledger rows: {summary.get('ledger_row_count')}",
        f"- Appended this run: {summary.get('appended_event_count')}",
        f"- Would append in check mode: {summary.get('would_append_event_count')}",
        f"- Open improvements: {summary.get('latest_open_count')} / high priority {summary.get('high_priority_open_count')}",
        f"- Closed latest improvements: {summary.get('latest_closed_count')} / closure rate {as_dict(payload.get('learning_loop_kpis')).get('closure_rate')}",
        f"- Closure split: applied_fix {summary.get('applied_fix_closed_count')} / signal_absence {summary.get('signal_absence_closed_count')} / pending_skill_proposal {summary.get('pending_skill_proposal_closed_count')} / superseded {summary.get('superseded_closed_count')} / other {summary.get('other_closed_count')}",
        f"- Follow-up-required open items: {summary.get('followup_required_open_count')}",
        f"- Unclassified closed follow-up items: {summary.get('unclassified_closed_followup_count')}",
        f"- Pending skill proposals: {summary.get('pending_skill_proposal_count')} / relevant {summary.get('relevant_pending_skill_proposal_count')}",
        f"- Recurring open improvements: {summary.get('recurring_open_count')}",
        f"- Anti-theater status: {as_dict(payload.get('learning_loop_kpis')).get('anti_theater_status')}",
        f"- SLA pressure: overdue {summary.get('overdue_open_count')} / due soon {summary.get('due_soon_open_count')} / escalation {summary.get('escalation_level')}",
        f"- Top improvement: {summary.get('top_improvement_title')}",
        f"- Next action: {summary.get('top_improvement_next_action')}",
        "",
        "## Open Improvements",
    ]
    for row in payload.get("latest_open_improvements", [])[:10]:
        lines.append(f"- {row.get('title')} [{row.get('category')}] priority={row.get('priority')} sla={row.get('sla_status')} age_hours={row.get('age_hours')} gate={row.get('decision')}")
    lines.extend(["", "## Blocked Actions"])
    for action in payload.get("blocked_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build append-only improvement ledger and current packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate and render from current inputs without appending to the durable ledger.")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--ledger-out", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()

    append = bool(args.write and not args.check)
    payload, new_events = build_payload(args.ledger_out, append=append)
    if args.write:
        atomic_write_json(args.json_out, payload)
        if args.write_md:
            atomic_write_text(args.md_out, render_md(payload))
    print(
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
        f"mode={payload.get('mode')} open={as_dict(payload.get('summary')).get('latest_open_count')} "
        f"appended={as_dict(payload.get('summary')).get('appended_event_count')} "
        f"would_append={as_dict(payload.get('summary')).get('would_append_event_count')} "
        f"escalation={as_dict(payload.get('summary')).get('escalation_level')} "
        f"ledger={rel(args.ledger_out)}"
    )
    for error in as_dict(payload.get("validation")).get("errors", []):
        print(f"  [critical] {error}")
    for warning in as_dict(payload.get("validation")).get("warnings", []):
        print(f"  [warning] {warning}")
    if args.validate and as_dict(payload.get("validation")).get("status") == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
