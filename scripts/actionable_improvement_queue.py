#!/usr/bin/env python3
"""Build the actionable improvement queue.

This is a review-only bridge between the Improvement Ledger and the places
where work can actually be handled: WF88 follow-up triage, WF74 decision
docket, PM jobs, owner-gated packets, or explicit monitor-only review.

It does not apply recommendations, mutate cron/runtime/config, change finance
canon or portfolio state, or infer owner approval.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "actionable-improvement-queue.json"
MD_OUT = TMP / "actionable-improvement-queue.md"
SCHEMA = "veritas.actionable_improvement_queue.v1"

IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
WF88_FOLLOWUP_TRIAGE = TMP / "wf88-followup-debt-triage-packet.json"
WF74_DECISION_DOCKET = TMP / "wf74-decision-docket.json"
OWNER_GATED_QUEUE = TMP / "owner-gated-action-review-queue.json"
PM_JOB_QUEUE = TMP / "pm-implementation-job-queue.json"
WORKFLOW_FOLLOWUP_LEDGER = TMP / "workflow-implementation-followup-ledger.json"
MAIN_ESCALATION_CONSUMER = TMP / "main-session-escalation-consumer.json"
CRON_CONTROL_PACKET = TMP / "cron-control-packet.json"

HIGH_PRIORITY_MIN = 75

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routes_existing_artifacts": True,
    "creates_canon": False,
    "approval_authority": False,
    "auto_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

CADENCE = {
    "refresh_command": "python scripts\\actionable_improvement_queue.py --write --write-md --validate",
    "validator_command": "python scripts\\no_orphan_validator.py --write --validate",
    "target_cron_contract": "state/cron-contracts/runtime-wf88-wiki-synthesis-refresh.json",
    "refresh_cadence": "daily with WF88 wiki synthesis refresh and after material improvement ledger changes",
    "monitor_only_review_rule": "Monitor-only rows remain visible in this queue and must be revalidated on each daily WF88 refresh; escalate if severity, SLA, or proof state worsens.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def route_key(row: dict[str, Any]) -> tuple[str, str]:
    return norm(row.get("title")), norm(row.get("category"))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def source_state(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    generated_at = payload.get("generated_at_utc")
    generated = parse_utc(generated_at)
    age_hours = None
    if generated is not None:
        age_hours = round((datetime.now(timezone.utc) - generated).total_seconds() / 3600.0, 2)
    return {
        "path": rel(path),
        "present": path.exists(),
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
    }


def first_by_source_key(rows: list[dict[str, Any]], source_key: str | None) -> dict[str, Any]:
    if not source_key:
        return {}
    for row in rows:
        if row.get("source_key") == source_key or row.get("source_id") == source_key:
            return row
    return {}


def best_title_match(rows: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    title, category = route_key(item)
    priority = item.get("priority")
    exact: list[dict[str, Any]] = []
    title_only: list[dict[str, Any]] = []
    for row in rows:
        row_title, row_category = route_key(row)
        if row_title == title and row_category == category:
            exact.append(row)
        elif row_title == title:
            title_only.append(row)
    candidates = exact or title_only
    if priority is not None:
        for row in candidates:
            if row.get("priority") == priority:
                return row
    return candidates[0] if candidates else {}


def proof_artifacts_from(*rows: dict[str, Any]) -> list[str]:
    artifacts: list[str] = []
    for row in rows:
        for key in ("proof_artifacts", "artifacts", "evidence_artifacts"):
            for item in as_list(row.get(key)):
                if isinstance(item, str) and item not in artifacts:
                    artifacts.append(item)
        for key in ("proof_commands", "validation_commands"):
            if as_list(row.get(key)) and "proof_commands" not in artifacts:
                artifacts.append("proof_commands")
    return artifacts


def proof_commands_from(*rows: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for row in rows:
        for key in ("proof_commands", "validation_commands", "acceptance_proof"):
            for command in as_list(row.get(key)):
                if isinstance(command, str) and command not in commands:
                    commands.append(command)
    return commands


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def default_proof_contract(
    *,
    item: dict[str, Any],
    route: dict[str, Any],
    action_class: str,
    destination: str,
    next_action: Any,
) -> dict[str, Any]:
    title = norm(item.get("title"))
    category = norm(item.get("category"))
    route_id = norm(
        route.get("successor_id")
        or route.get("docket_id")
        or route.get("item_id")
        or route.get("job_id")
        or route.get("source_id")
        or item.get("source_key")
    )
    action_text = norm(next_action)
    text = " ".join([title, category, route_id, action_text, destination, action_class])
    commands: list[str] = []
    artifacts: list[str] = []
    trigger = "Escalate if the row becomes orphaned, loses its action contract, worsens in severity/SLA, or its proof packet regresses."
    close_condition = "Close only when a durable closure event, superseding open improvement, or current proof explicitly resolves the source row."

    if destination.startswith("wf88_followup"):
        commands.append("python scripts\\wf88_followup_debt_triage_packet.py --write --write-md --validate")
        artifacts.append(rel(WF88_FOLLOWUP_TRIAGE))
    if destination.startswith("wf74_decision_docket") or action_class in {"wf74_fix_now", "owner_decision", "owner_authority_required", "monitor_only"}:
        commands.append("python scripts\\wf74_decision_docket.py --write --write-md --validate")
        artifacts.append(rel(WF74_DECISION_DOCKET))
    if "cron" in text:
        commands.extend([
            "python scripts\\cron_freshness_spine.py --write --validate",
            "python scripts\\cron_control_packet.py --write --validate",
        ])
        artifacts.append(rel(CRON_CONTROL_PACKET))
        trigger = "Escalate only if cron blocked count, escalation signal count, missing contract count, or live drift becomes nonzero."
        close_condition = "Close or downgrade only after cron control remains green in current WF88/actionability proof or the source row is superseded."
    if "otel" in text or "collector" in text:
        commands.append("python scripts\\otel_ops_control.py --write --write-db --multi-window --validate")
        artifacts.extend([rel(TMP / "otel-ops-control.json"), rel(CRON_CONTROL_PACKET)])
        trigger = "Escalate only if OTEL ops validation blocks, collector health regresses, warning/error count rises, or event-rate drift stops being ok."
        close_condition = "Close or downgrade only after current OTEL proof is clean or the source row is superseded."
    if "wf87" in text or action_class == "market_session_accrual":
        commands.extend([
            "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
            "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
        ])
        artifacts.extend([rel(TMP / "wf87-v2-readiness-rollup.json"), rel(TMP / "autonomy-spine-readiness-rollup.json")])
        trigger = "Escalate if maturity proof worsens, runtime blockers become binding, or performance/execution claims appear before thresholds clear."
        close_condition = "Close only when WF87/outcome proof verifies the maturity row or a successor improvement takes over."
    if "finance response quality" in text or "finance response-quality" in text:
        commands.append("python scripts\\finance_response_quality_repair_loop.py --write --validate")
        artifacts.append(rel(TMP / "finance-response-quality-repair-loop.json"))
        trigger = "Escalate if finance repair conveyor validation blocks or finance answer-quality gaps reappear as implementation blockers."
        close_condition = "Close when finance repair proof is clean or the gap is superseded by a concrete repair proposal."
    if "paper" in text or "execution" in text:
        commands.append("python scripts\\wf67_full_portfolio_scope_validator.py --write --validate")
        artifacts.append(rel(TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"))
        trigger = "Escalate if any output implies order authority, paper/live execution approval, account authority, or owner approval inference."
        close_condition = "Close only when the execution-boundary row is superseded or current proof shows proposal-only, exact-owner-gated posture."

    return {
        "proof_commands": unique_strings(commands),
        "proof_artifacts": unique_strings(artifacts),
        "monitor_escalation_trigger": trigger,
        "close_condition": close_condition,
    }


def action_class_from_route(route: dict[str, Any]) -> str:
    state = str(route.get("action_state") or route.get("status") or "").strip()
    if state in {"active_successor_followup", "active_operational_drift_review"}:
        return state
    if state == "fix_now":
        return "wf74_fix_now"
    if state == "hard_stop":
        return "owner_authority_required"
    if state == "owner_decision":
        return "owner_decision"
    if state == "market_session_accrual":
        return "market_session_accrual"
    if state == "monitor_only":
        return "monitor_only"
    if state in {"ready", "active", "blocked"}:
        return "pm_job"
    return "routed"


def route_destination(action_class: str, destination: str) -> str:
    if action_class == "owner_authority_required":
        return "wf74_decision_docket_owner_authority_gate"
    if action_class == "owner_decision":
        return "owner_gated_action_review_queue" if destination == "owner_gated" else "wf74_decision_docket_owner_decision"
    return destination


def select_route(
    item: dict[str, Any],
    *,
    followups: list[dict[str, Any]],
    docket_rows: list[dict[str, Any]],
    owner_items: list[dict[str, Any]],
    pm_jobs: list[dict[str, Any]],
    workflow_followups: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    source_key = item.get("source_key")
    secondary: list[dict[str, Any]] = []

    followup = first_by_source_key(followups, source_key)
    docket = first_by_source_key(docket_rows, source_key) or best_title_match(docket_rows, item)
    owner = best_title_match(owner_items, item)
    pm_job = best_title_match(pm_jobs, item)
    workflow_followup = first_by_source_key(workflow_followups, source_key) or best_title_match(workflow_followups, item)

    for route in (docket, owner, pm_job, workflow_followup):
        if route:
            secondary.append(route)

    if followup:
        return action_class_from_route(followup), "wf88_followup_debt_triage", followup, secondary
    if docket:
        action_class = action_class_from_route(docket)
        return action_class, route_destination(action_class, "wf74_decision_docket"), docket, [row for row in secondary if row is not docket]
    if owner:
        return "owner_decision", "owner_gated_action_review_queue", owner, [row for row in secondary if row is not owner]
    if pm_job:
        return "pm_job", "pm_implementation_job_queue", pm_job, [row for row in secondary if row is not pm_job]
    if workflow_followup:
        return "workflow_followup", "workflow_implementation_followup_ledger", workflow_followup, [row for row in secondary if row is not workflow_followup]
    if str(item.get("decision") or "").startswith("monitor"):
        return "monitor_only", "improvement_ledger_monitor_review", item, []
    return "orphan", "unrouted", {}, []


def build_action_item(
    item: dict[str, Any],
    *,
    followups: list[dict[str, Any]],
    docket_rows: list[dict[str, Any]],
    owner_items: list[dict[str, Any]],
    pm_jobs: list[dict[str, Any]],
    workflow_followups: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    action_class, destination, route, secondary = select_route(
        item,
        followups=followups,
        docket_rows=docket_rows,
        owner_items=owner_items,
        pm_jobs=pm_jobs,
        workflow_followups=workflow_followups,
    )
    proof_artifacts = proof_artifacts_from(item, route, *secondary)
    proof_commands = proof_commands_from(item, route, *secondary)
    next_action = (
        route.get("recommended_next_action")
        or route.get("next_action")
        or route.get("objective")
        or item.get("next_action")
    )
    defaults = default_proof_contract(
        item=item,
        route=route,
        action_class=action_class,
        destination=destination,
        next_action=next_action,
    )
    proof_artifacts = unique_strings(proof_artifacts + as_list(defaults.get("proof_artifacts")))
    proof_commands = unique_strings(proof_commands + as_list(defaults.get("proof_commands")))
    review_by = (
        parse_utc(generated_at) + timedelta(days=1)
        if action_class in {"monitor_only", "market_session_accrual", "active_operational_drift_review"}
        else None
    )
    route_id = (
        route.get("successor_id")
        or route.get("docket_id")
        or route.get("item_id")
        or route.get("job_id")
        or route.get("source_id")
        or item.get("source_key")
    )
    secondary_states = {str(row.get("action_state") or row.get("status") or "") for row in secondary if row}
    secondary_owner_gate = bool({"hard_stop", "owner_decision"} & secondary_states)
    missing: list[str] = []
    if action_class == "orphan":
        missing.append("destination")
    if not next_action:
        missing.append("next_action")
    if action_class not in {"owner_decision", "owner_authority_required", "monitor_only", "market_session_accrual", "active_operational_drift_review"}:
        if not proof_artifacts and not proof_commands:
            missing.append("proof")
    if action_class in {"monitor_only", "market_session_accrual", "active_operational_drift_review"}:
        if not review_by:
            missing.append("review_rule")
        if not proof_artifacts and not proof_commands:
            missing.append("monitor_proof")
        if not defaults.get("close_condition"):
            missing.append("close_condition")
        if not defaults.get("monitor_escalation_trigger"):
            missing.append("monitor_escalation_trigger")

    return {
        "schema": "veritas.actionable_improvement_queue.item.v1",
        "item_id": item.get("source_key") or item.get("id") or norm(item.get("title")),
        "source_key": item.get("source_key"),
        "source_type": item.get("source_type"),
        "title": item.get("title"),
        "category": item.get("category"),
        "priority": item.get("priority"),
        "sla_status": item.get("sla_status"),
        "age_hours": item.get("age_hours"),
        "opened_at_utc": item.get("opened_at_utc"),
        "ledger_decision": item.get("decision"),
        "action_class": action_class,
        "destination": destination,
        "destination_id": route_id,
        "destination_title": route.get("title") or route.get("source_recommendation_title"),
        "secondary_routes": [
            {
                "destination_id": row.get("docket_id") or row.get("item_id") or row.get("job_id") or row.get("source_id"),
                "title": row.get("title") or row.get("source_recommendation_title"),
                "action_state": row.get("action_state") or row.get("status"),
            }
            for row in secondary
            if row
        ],
        "next_action": next_action,
        "proof_artifacts": proof_artifacts,
        "proof_commands": proof_commands,
        "requires_owner_decision": action_class in {"owner_decision", "owner_authority_required"} or secondary_owner_gate or bool(route.get("gate")),
        "secondary_owner_gate": secondary_owner_gate,
        "monitor_only": action_class in {"monitor_only", "market_session_accrual", "active_operational_drift_review"},
        "monitor_review_by_utc": review_by.replace(microsecond=0).isoformat().replace("+00:00", "Z") if review_by else None,
        "monitor_review_rule": CADENCE["monitor_only_review_rule"] if action_class in {"monitor_only", "market_session_accrual", "active_operational_drift_review"} else None,
        "monitor_escalation_trigger": defaults.get("monitor_escalation_trigger") if action_class in {"monitor_only", "market_session_accrual", "active_operational_drift_review"} else None,
        "close_condition": defaults.get("close_condition"),
        "proof_artifact": proof_artifacts[0] if proof_artifacts else None,
        "proof_command": proof_commands[0] if proof_commands else None,
        "is_orphan": action_class == "orphan",
        "missing_contract_fields": missing,
        "stop_lines": as_list(route.get("stop_lines")) or [
            "No auto-apply from this queue.",
            "No owner approval inference.",
            "No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, account, runtime config, or external mutation.",
        ],
    }


def dedupe_key(row: dict[str, Any]) -> str:
    parts = [
        norm(row.get("title")),
        norm(row.get("category")),
        str(row.get("action_class") or ""),
        str(row.get("destination") or ""),
        norm(row.get("next_action")),
    ]
    return "|".join(parts)


def worse_sla(left: Any, right: Any) -> Any:
    ranks = {"overdue": 0, "due_soon": 1, "current": 2, None: 3, "": 3}
    return left if ranks.get(left, 3) <= ranks.get(right, 3) else right


def merge_action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = dedupe_key(row)
        current = deduped.get(key)
        source_record = {
            "item_id": row.get("item_id"),
            "source_key": row.get("source_key"),
            "source_type": row.get("source_type"),
            "destination_id": row.get("destination_id"),
            "title": row.get("title"),
        }
        if current is None:
            current = dict(row)
            current["dedupe_key"] = key
            current["source_keys"] = unique_strings([row.get("source_key")])
            current["destination_ids"] = unique_strings([row.get("destination_id")])
            current["duplicate_source_count"] = 0
            current["duplicate_sources"] = []
            deduped[key] = current
            continue
        current["duplicate_source_count"] = int(current.get("duplicate_source_count") or 0) + 1
        current["duplicate_sources"] = as_list(current.get("duplicate_sources")) + [source_record]
        current["source_keys"] = unique_strings(as_list(current.get("source_keys")) + [row.get("source_key")])
        current["destination_ids"] = unique_strings(as_list(current.get("destination_ids")) + [row.get("destination_id")])
        current["proof_artifacts"] = unique_strings(as_list(current.get("proof_artifacts")) + as_list(row.get("proof_artifacts")))
        current["proof_commands"] = unique_strings(as_list(current.get("proof_commands")) + as_list(row.get("proof_commands")))
        current["proof_artifact"] = as_list(current.get("proof_artifacts"))[0] if as_list(current.get("proof_artifacts")) else None
        current["proof_command"] = as_list(current.get("proof_commands"))[0] if as_list(current.get("proof_commands")) else None
        current["missing_contract_fields"] = unique_strings(as_list(current.get("missing_contract_fields")) + as_list(row.get("missing_contract_fields")))
        current["requires_owner_decision"] = bool(current.get("requires_owner_decision")) or bool(row.get("requires_owner_decision"))
        current["secondary_owner_gate"] = bool(current.get("secondary_owner_gate")) or bool(row.get("secondary_owner_gate"))
        current["is_orphan"] = bool(current.get("is_orphan")) or bool(row.get("is_orphan"))
        current["priority"] = max(int(current.get("priority") or 0), int(row.get("priority") or 0))
        current["sla_status"] = worse_sla(current.get("sla_status"), row.get("sla_status"))
        current["age_hours"] = max(float(current.get("age_hours") or 0.0), float(row.get("age_hours") or 0.0))
        current["secondary_routes"] = as_list(current.get("secondary_routes")) + [
            secondary for secondary in as_list(row.get("secondary_routes")) if secondary not in as_list(current.get("secondary_routes"))
        ]
    return sorted(deduped.values(), key=sort_key)


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, float]:
    class_rank = {
        "orphan": 0,
        "owner_authority_required": 1,
        "wf74_fix_now": 2,
        "owner_decision": 3,
        "active_successor_followup": 4,
        "active_operational_drift_review": 5,
        "pm_job": 6,
        "market_session_accrual": 7,
        "monitor_only": 8,
    }.get(str(row.get("action_class")), 9)
    sla_rank = 0 if row.get("sla_status") == "overdue" else 1 if row.get("sla_status") == "due_soon" else 2
    return (
        class_rank,
        sla_rank,
        -int(row.get("priority") or 0),
        -float(row.get("age_hours") or 0.0),
    )


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    items = [as_dict(row) for row in as_list(packet.get("action_items"))]
    for row in items:
        priority = int(row.get("priority") or 0)
        overdue = row.get("sla_status") == "overdue"
        missing = as_list(row.get("missing_contract_fields"))
        if row.get("is_orphan"):
            errors.append(f"orphan_item:{row.get('item_id')}:{row.get('title')}")
        if missing and (priority >= HIGH_PRIORITY_MIN or overdue):
            errors.append(f"missing_action_contract:{row.get('item_id')}:{','.join(str(item) for item in missing)}")
        elif missing:
            warnings.append(f"missing_noncritical_action_contract:{row.get('item_id')}:{','.join(str(item) for item in missing)}")
    summary = as_dict(packet.get("summary"))
    if int(summary.get("owner_decision_count") or 0):
        warnings.append(f"owner_decisions_visible:{summary.get('owner_decision_count')}")
    if int(summary.get("hard_stop_count") or 0):
        warnings.append(f"owner_authority_required_visible:{summary.get('hard_stop_count')}")
    monitor_contract_gaps = [
        row.get("item_id")
        for row in items
        if row.get("monitor_only")
        and (
            not row.get("monitor_review_rule")
            or not row.get("monitor_escalation_trigger")
            or not row.get("close_condition")
            or (not as_list(row.get("proof_artifacts")) and not as_list(row.get("proof_commands")))
        )
    ]
    if monitor_contract_gaps:
        errors.append(f"monitor_contract_gaps:{len(monitor_contract_gaps)}")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def build_packet() -> dict[str, Any]:
    generated_at = utc_now()
    improvement = load(IMPROVEMENT_LEDGER)
    triage = load(WF88_FOLLOWUP_TRIAGE)
    docket = load(WF74_DECISION_DOCKET)
    owner = load(OWNER_GATED_QUEUE)
    pm_jobs = load(PM_JOB_QUEUE)
    workflow_followup = load(WORKFLOW_FOLLOWUP_LEDGER)
    escalation = load(MAIN_ESCALATION_CONSUMER)
    cron = load(CRON_CONTROL_PACKET)

    open_rows = [as_dict(row) for row in as_list(improvement.get("latest_open_improvements"))]
    followup_rows = [as_dict(row) for row in as_list(triage.get("active_followup_items"))]
    docket_rows = [as_dict(row) for row in as_list(docket.get("rows"))]
    owner_rows = [as_dict(row) for row in as_list(owner.get("review_items"))]
    job_rows = [as_dict(row) for row in as_list(pm_jobs.get("jobs"))]
    workflow_rows = [as_dict(row) for row in as_list(workflow_followup.get("followups"))]

    raw_action_rows = [
        build_action_item(
            row,
            followups=followup_rows,
            docket_rows=docket_rows,
            owner_items=owner_rows,
            pm_jobs=job_rows,
            workflow_followups=workflow_rows,
            generated_at=generated_at,
        )
        for row in open_rows
    ]
    action_rows = merge_action_rows(raw_action_rows)
    action_rows.sort(key=sort_key)
    top = action_rows[0] if action_rows else {}
    hard_stop_count = sum(
        1
        for row in action_rows
        if row.get("action_class") == "owner_authority_required"
        or any(as_dict(secondary).get("action_state") == "hard_stop" for secondary in as_list(row.get("secondary_routes")))
    )
    summary = {
        "open_input_count": len(open_rows),
        "raw_action_item_count": len(raw_action_rows),
        "action_item_count": len(action_rows),
        "deduped_action_item_count": len(action_rows),
        "duplicate_source_row_count": len(raw_action_rows) - len(action_rows),
        "orphan_count": sum(1 for row in action_rows if row.get("is_orphan")),
        "high_priority_orphan_count": sum(1 for row in action_rows if row.get("is_orphan") and int(row.get("priority") or 0) >= HIGH_PRIORITY_MIN),
        "overdue_orphan_count": sum(1 for row in action_rows if row.get("is_orphan") and row.get("sla_status") == "overdue"),
        "missing_contract_count": sum(1 for row in action_rows if as_list(row.get("missing_contract_fields"))),
        "high_priority_missing_contract_count": sum(
            1
            for row in action_rows
            if as_list(row.get("missing_contract_fields")) and int(row.get("priority") or 0) >= HIGH_PRIORITY_MIN
        ),
        "owner_decision_count": sum(1 for row in action_rows if row.get("requires_owner_decision")),
        "hard_stop_count": hard_stop_count,
        "wf74_fix_now_count": sum(1 for row in action_rows if row.get("action_class") == "wf74_fix_now"),
        "active_followup_count": sum(1 for row in action_rows if str(row.get("destination")).startswith("wf88_followup")),
        "pm_job_count": sum(1 for row in action_rows if row.get("action_class") == "pm_job"),
        "monitor_only_count": sum(1 for row in action_rows if row.get("monitor_only")),
        "monitor_contract_gap_count": sum(
            1
            for row in action_rows
            if row.get("monitor_only")
            and (
                not row.get("monitor_review_rule")
                or not row.get("monitor_escalation_trigger")
                or not row.get("close_condition")
                or (not as_list(row.get("proof_artifacts")) and not as_list(row.get("proof_commands")))
            )
        ),
        "top_action_title": top.get("title"),
        "top_action_class": top.get("action_class"),
        "top_action_destination": top.get("destination"),
        "top_next_action": top.get("next_action"),
        "cron_blocked_count": as_dict(cron.get("summary")).get("blocked_count"),
        "cron_escalation_signal_count": as_dict(cron.get("summary")).get("escalation_signal_count"),
        "main_session_unresolved_escalation_count": as_dict(escalation.get("summary")).get("unresolved_count"),
    }
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "actionable_queue_ready_no_apply_authority",
        "purpose": "Ensure open Improvement Ledger rows surface as durable actionable items instead of getting lost in summary counts.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "cadence": CADENCE.copy(),
        "inputs": {
            "improvement_ledger": source_state(IMPROVEMENT_LEDGER, improvement),
            "wf88_followup_triage": source_state(WF88_FOLLOWUP_TRIAGE, triage),
            "wf74_decision_docket": source_state(WF74_DECISION_DOCKET, docket),
            "owner_gated_queue": source_state(OWNER_GATED_QUEUE, owner),
            "pm_job_queue": source_state(PM_JOB_QUEUE, pm_jobs),
            "workflow_followup_ledger": source_state(WORKFLOW_FOLLOWUP_LEDGER, workflow_followup),
            "main_escalation_consumer": source_state(MAIN_ESCALATION_CONSUMER, escalation),
            "cron_control_packet": source_state(CRON_CONTROL_PACKET, cron),
        },
        "summary": summary,
        "action_items": action_rows,
        "blocked_actions": [
            "No auto-apply from this queue.",
            "No cron schedule/config/runtime mutation from this queue.",
            "No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, or account mutation.",
            "No external output or owner approval inference.",
        ],
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] != "ok":
        packet["status"] = "actionable_queue_warning_no_apply_authority"
    packet["summary"]["status"] = packet["status"]
    packet["summary"]["validation_status"] = packet["validation"]["status"]
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Actionable Improvement Queue",
        "",
        "## Verdict",
        "",
        "Every open improvement must route to a concrete destination: WF88 follow-up, WF74 docket, PM job, owner packet, or monitor review. Orphans are validation blockers.",
        "",
        "## Summary",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Validation: `{as_dict(packet.get('validation')).get('status')}`",
        f"- Open input rows: `{summary.get('open_input_count')}`",
        f"- Raw / deduped action rows: `{summary.get('raw_action_item_count')}` / `{summary.get('deduped_action_item_count')}`",
        f"- Duplicate source rows merged: `{summary.get('duplicate_source_row_count')}`",
        f"- Action items: `{summary.get('action_item_count')}`",
        f"- Orphans: `{summary.get('orphan_count')}`",
        f"- Missing contracts: `{summary.get('missing_contract_count')}`",
        f"- Owner decisions / hard stops: `{summary.get('owner_decision_count')}` / `{summary.get('hard_stop_count')}`",
        f"- Monitor rows / contract gaps: `{summary.get('monitor_only_count')}` / `{summary.get('monitor_contract_gap_count')}`",
        f"- Top action: `{summary.get('top_action_title')}` -> `{summary.get('top_action_destination')}`",
        f"- Top next action: {summary.get('top_next_action')}",
        "",
        "## Top Items",
        "",
        "| Priority | SLA | Class | Destination | Title |",
        "|---:|---|---|---|---|",
    ]
    for row in as_list(packet.get("action_items"))[:15]:
        item = as_dict(row)
        title = str(item.get("title") or "").replace("|", "\\|")
        lines.append(
            f"| {item.get('priority')} | {item.get('sla_status')} | `{item.get('action_class')}` | `{item.get('destination')}` | {title} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Review-only routing surface.",
        "- No recommendation, owner packet, PM row, or monitor row creates apply/execution authority.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    if args.print_json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_markdown(packet))
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
