#!/usr/bin/env python3
"""Build a WF74 V2 review/routing decision docket.

The docket turns learning-loop opportunities, workflow followups, patch plans,
and durable improvement rows into one review surface with explicit action
states. It is a classifier and proof router only; it does not apply patches,
mutate cron schedules, change skills, alter finance state, or infer approval.
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
DATA = ROOT / "data"

DEFAULT_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
DEFAULT_ROUTER = TMP / "wf74-autonomy-work-router.json"
DEFAULT_AUTO_PATCH = TMP / "wf74-auto-patch-proposer.json"
DEFAULT_IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
DEFAULT_CRON_CONTROL = TMP / "cron-control-packet.json"
DEFAULT_OTEL_CONTROL = TMP / "otel-ops-control.json"
DEFAULT_WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
DEFAULT_WF87_READINESS = TMP / "wf87-v2-readiness-rollup.json"
DEFAULT_AUTONOMY_SPINE = TMP / "autonomy-spine-readiness-rollup.json"
DEFAULT_OUT = TMP / "wf74-decision-docket.json"
DEFAULT_MD = TMP / "wf74-decision-docket.md"

SCHEMA = "veritas.wf74_decision_docket.v1"

ACTION_STATES = {
    "fix_now",
    "owner_decision",
    "proof_refresh",
    "market_session_accrual",
    "skill_proposal",
    "monitor_only",
    "hard_stop",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "decision_docket_only": True,
    "auto_apply_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

GLOBAL_STOP_LINES = [
    "No auto-apply from the WF74 docket.",
    "No cron add/edit/disable/delete without exact owner approval, rollback proof, and post-change freshness proof.",
    "No skill apply/install/quarantine without explicit Skill Workshop approval.",
    "No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, or account mutation.",
    "No external/customer delivery, credential/config/runtime mutation, or owner approval inference.",
]

DEFAULT_PROOF_BY_STATE = {
    "fix_now": [
        "python scripts\\changed_file_validator_router.py --write --validate",
        "python scripts\\validator_bundle_router.py --write --validate",
        "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
    ],
    "proof_refresh": [
        "python scripts\\workflow_advancement_scorecard.py --write --validate",
        "python scripts\\wf74_autonomy_work_router.py --write --validate",
    ],
    "market_session_accrual": [
        "python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
        "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
        "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
    ],
    "monitor_only": [
        "python scripts\\wf74_decision_docket.py --write --validate",
    ],
    "owner_decision": [],
    "skill_proposal": [
        "openclaw skills check",
    ],
    "hard_stop": [],
}

STATE_ORDER = {
    "hard_stop": 0,
    "fix_now": 1,
    "owner_decision": 2,
    "proof_refresh": 3,
    "market_session_accrual": 4,
    "skill_proposal": 5,
    "monitor_only": 6,
}

FORBIDDEN_TERMS = {
    "raw_prompt",
    "raw prompt",
    "tool payload",
    "credentials",
    "secret",
    "live trading",
    "live order",
    "live account",
    "brokerage",
    "money movement",
    "customer delivery",
    "external delivery",
    "collector config",
    "runtime config",
}

RESPONSE_RECOMMENDATION_GAP_TERMS = {
    "facts without recommendations",
    "facts and repairs",
    "missing recommendations",
    "missing next steps",
    "recommendation-free",
    "no top recommendations",
    "response quality",
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


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    stem = "-".join(ch.lower() if ch.isalnum() else "-" for ch in str(parts[0] or "item"))[:44]
    while "--" in stem:
        stem = stem.replace("--", "-")
    return f"{stem.strip('-') or 'item'}-{digest}"


def text_blob(item: dict[str, Any]) -> str:
    values = [
        item.get("source_kind"),
        item.get("category"),
        item.get("title"),
        item.get("recommendation"),
        item.get("next_action"),
        item.get("proposal_gate"),
        item.get("route"),
        item.get("risk_class"),
        item.get("implementation_class"),
        item.get("status"),
    ]
    for key in ("blockers", "details"):
        value = item.get(key)
        if isinstance(value, (list, dict)):
            values.append(json.dumps(value, sort_keys=True, ensure_ascii=False))
        else:
            values.append(value)
    return " ".join(str(value or "") for value in values).casefold()


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def priority_value(item: dict[str, Any]) -> int:
    priority = item.get("priority")
    if isinstance(priority, str) and priority.upper().startswith("P"):
        return {"P0": 95, "P1": 85, "P2": 70, "P3": 55}.get(priority.upper(), 50)
    return int_value(priority) or 50


def cron_context(cron_control: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(cron_control.get("summary"))
    return {
        "status": cron_control.get("status"),
        "blocked_count": int_value(summary.get("blocked_count")),
        "escalation_signal_count": int_value(summary.get("escalation_signal_count")),
        "requires_attention_count": int_value(summary.get("requires_attention_count")),
        "stale_count": int_value(summary.get("stale_count")),
        "should_wake_main_session": bool(summary.get("should_wake_main_session")),
    }


def otel_context(otel_control: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(otel_control.get("validation"))
    collector_health = as_dict(otel_control.get("collector_health"))
    drift = as_dict(otel_control.get("drift"))
    volume = as_dict(otel_control.get("volume_normalization_recommendation"))
    return {
        "status": otel_control.get("status"),
        "validation_status": validation.get("status"),
        "collector_health_status": collector_health.get("status"),
        "collector_listening": bool(collector_health.get("listening")),
        "drift_status": drift.get("status"),
        "volume_recommendation_status": volume.get("status"),
    }


def otel_ops_current_clean(context: dict[str, Any]) -> bool:
    otel = as_dict(context.get("otel"))
    return (
        otel.get("status") == "ok"
        and otel.get("validation_status") == "ok"
        and otel.get("collector_health_status") == "ok"
        and bool(otel.get("collector_listening"))
        and otel.get("drift_status") == "ok"
    )


def is_otel_monitor_only_drift_review(item: dict[str, Any], text: str, context: dict[str, Any]) -> bool:
    category = str(item.get("category") or "").casefold()
    title = str(item.get("title") or "").casefold()
    if category != "collector_config":
        return False
    if "otel" not in text or "event-rate drift" not in title:
        return False
    monitor_terms = (
        "operational monitor-only",
        "local operations only",
        "non-blocked current otel packet",
        "do not mutate collector/runtime config",
        "current otel packet",
    )
    return any(term in text for term in monitor_terms) and otel_ops_current_clean(context)


def classify_item(item: dict[str, Any], context: dict[str, Any]) -> tuple[str, str]:
    text = text_blob(item)
    category = str(item.get("category") or "").casefold()
    source_kind = str(item.get("source_kind") or "").casefold()
    gate = str(item.get("proposal_gate") or "").casefold()
    route = str(item.get("route") or "").casefold()
    title = str(item.get("title") or "").casefold()

    if is_otel_monitor_only_drift_review(item, text, context):
        return "monitor_only", "otel_ops_current_monitor_only"

    if any(term in text for term in FORBIDDEN_TERMS):
        return "hard_stop", "forbidden_authority_or_capture_surface"

    if category in {"response_quality", "finance_response_quality", "closeout_quality"} or any(
        term in text for term in RESPONSE_RECOMMENDATION_GAP_TERMS
    ):
        return "fix_now", "response_quality_recommendation_contract_gap"

    if "skill" in category or "skill" in source_kind or "skill_workshop" in text:
        return "skill_proposal", "skill_workshop_proposal_only"

    if "maintain execution as proposal-only" in title or "standing_guardrail" in gate:
        return "monitor_only", "permanent_execution_guardrail_visibility"

    if "owner" in gate or "owner_decision" in text or "exact-owner-gated" in text:
        return "owner_decision", "owner_gate_required_before_action"

    if "outcome_measurement" in category or "shadow" in text or "wf87" in text:
        return "market_session_accrual", "regular_session_evidence_required"

    if "autonomy-spine" in text or "autonomy_spine" in text or "dependency_rollup" in route:
        return "market_session_accrual", "child_workflow_maturity_proof_required"

    if "cron" in category or "cron" in route or "cron" in title:
        cron = as_dict(context.get("cron"))
        if int_value(cron.get("blocked_count")) or int_value(cron.get("escalation_signal_count")):
            return "fix_now", "cron_governance_blocker_present"
        if int_value(cron.get("stale_count")):
            return "monitor_only", "cron_stale_monitor_only_after_green_control"
        return "monitor_only", "cron_control_green"

    if "patch_plan" in source_kind or "patch_plan" in text or "main_review_patch_required" in text:
        return "fix_now", "bounded_patch_plan_ready_for_implementation"

    if "pm_job_candidate" in text or "proof" in text or "workflow_maturity" in category:
        return "proof_refresh", "routed_followup_or_maturity_proof_refresh"

    return "monitor_only", "no_active_implementation_order"


def source_status(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def normalize_source_row(source_kind: str, row: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    extra = extra or {}
    source_id = (
        row.get("opportunity_id")
        or row.get("recommendation_id")
        or row.get("followup_id")
        or row.get("plan_id")
        or row.get("improvement_id")
        or row.get("job_id")
        or stable_id(source_kind, row.get("title"), row.get("category"))
    )
    title = row.get("title") or row.get("top_job_title") or row.get("description") or source_id
    return {
        "source_kind": source_kind,
        "source_id": str(source_id),
        "title": str(title),
        "category": row.get("category") or row.get("source_category") or row.get("route") or extra.get("category"),
        "priority": row.get("priority") or extra.get("priority"),
        "recommendation": row.get("recommended_action") or row.get("recommendation") or row.get("objective") or row.get("next_action"),
        "next_action": row.get("next_action") or row.get("objective") or row.get("recommended_action"),
        "proposal_gate": row.get("proposal_gate") or row.get("allowed_execution_mode") or extra.get("proposal_gate"),
        "route": row.get("route") or row.get("route_status") or extra.get("route"),
        "risk_class": row.get("risk_class") or extra.get("risk_class"),
        "implementation_class": row.get("implementation_class") or extra.get("implementation_class"),
        "status": row.get("status") or row.get("route_status") or extra.get("status"),
        "proof_commands": as_list(row.get("proof_commands")) or as_list(row.get("acceptance_validators")),
        "stop_lines": as_list(row.get("stop_lines")) or list(GLOBAL_STOP_LINES),
        "blockers": as_list(row.get("blockers")) or as_list(as_dict(row.get("evidence")).get("blockers")),
        "raw": row,
    }


def owner_review_proposal_gate(row: dict[str, Any]) -> str:
    route = str(row.get("route") or "").casefold()
    category = str(row.get("category") or "").casefold()
    title = str(row.get("title") or "").casefold()
    if route == "finance_repair_review" or category == "finance_mutation":
        return "finance_repair_proposal_only"
    if route == "execution_guardrail_review" or "maintain execution as proposal-only" in title:
        return "standing_guardrail_no_execution"
    return "owner_decision"


def collect_rows(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in as_list(sources["opportunity_queue"].get("opportunities")):
        rows.append(normalize_source_row("opportunity", as_dict(row)))

    router = sources["router"]
    for row in as_list(router.get("workflow_implementation_followups")):
        rows.append(normalize_source_row("workflow_followup", as_dict(row)))
    for row in as_list(router.get("pm_job_candidates")):
        # PM candidates duplicate many source opportunities. They remain useful
        # only when a candidate has no direct source row in the docket.
        normalized = normalize_source_row("pm_job_candidate", as_dict(row))
        normalized["dedupe_to_source"] = row.get("source_key")
        rows.append(normalized)

    auto_patch = sources["auto_patch"]
    for row in as_list(auto_patch.get("patch_plans")):
        rows.append(normalize_source_row("patch_plan", as_dict(row)))
    for row in as_list(auto_patch.get("skill_workshop_requests")):
        rows.append(normalize_source_row("skill_workshop_request", as_dict(row), {"category": "skill_application"}))
    for row in as_list(auto_patch.get("owner_gated_reviews")):
        source = as_dict(row)
        rows.append(normalize_source_row("owner_gated_review", source, {"proposal_gate": owner_review_proposal_gate(source)}))

    for row in as_list(sources["improvement_ledger"].get("latest_open_improvements")):
        rows.append(normalize_source_row("durable_improvement", as_dict(row)))

    return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    direct_ids = {row.get("source_id") for row in rows if row.get("source_kind") != "pm_job_candidate"}
    kept: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("source_kind") == "pm_job_candidate" and row.get("dedupe_to_source") in direct_ids:
            continue
        key = "|".join([
            str(row.get("source_kind")),
            str(row.get("source_id")),
            str(row.get("title")),
        ])
        current = kept.get(key)
        if not current or priority_value(row) > priority_value(current):
            kept[key] = row
    return list(kept.values())


def docket_row(item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    action_state, reason = classify_item(item, context)
    proof_commands = as_list(item.get("proof_commands")) or list(DEFAULT_PROOF_BY_STATE.get(action_state, []))
    stop_lines = as_list(item.get("stop_lines")) or list(GLOBAL_STOP_LINES)
    priority = priority_value(item)
    return {
        "schema": "veritas.wf74_decision_docket.row.v1",
        "docket_id": stable_id(item.get("source_kind"), item.get("source_id"), item.get("title")),
        "source_kind": item.get("source_kind"),
        "source_id": item.get("source_id"),
        "title": item.get("title"),
        "category": item.get("category"),
        "priority": priority,
        "action_state": action_state,
        "classification_reason": reason,
        "recommendation": item.get("recommendation"),
        "next_action": next_action_for_state(action_state, item, reason),
        "proof_commands": proof_commands,
        "stop_lines": stop_lines,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_status": item.get("status"),
        "route": item.get("route"),
        "proposal_gate": item.get("proposal_gate"),
    }


def next_action_for_state(action_state: str, item: dict[str, Any], reason: str) -> str:
    supplied = str(item.get("next_action") or item.get("recommendation") or "").strip()
    if action_state == "fix_now":
        return supplied or "Open a narrow implementation lane, patch the deterministic local blocker, then rerun release proof."
    if action_state == "owner_decision":
        return supplied or "Prepare an owner decision card; do not execute or mutate until Randall approves exact scope."
    if action_state == "proof_refresh":
        return supplied or "Run the listed proof refresh commands and update the docket from fresh artifacts."
    if action_state == "market_session_accrual":
        return supplied or "Keep collecting regular-session evidence; rerun WF87/AUTONOMY-SPINE rollups after market-session proof lands."
    if action_state == "skill_proposal":
        return supplied or "Draft a Skill Workshop proposal; apply only after explicit approval."
    if action_state == "hard_stop":
        return "Stop and ask Randall for exact authority before touching the forbidden surface."
    return supplied or f"Monitor only; no implementation action is open because {reason}."


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "opportunity_queue": workspace_path(args.opportunity_queue, DEFAULT_OPPORTUNITY_QUEUE),
        "router": workspace_path(args.router, DEFAULT_ROUTER),
        "auto_patch": workspace_path(args.auto_patch, DEFAULT_AUTO_PATCH),
        "improvement_ledger": workspace_path(args.improvement_ledger, DEFAULT_IMPROVEMENT_LEDGER),
        "cron_control": workspace_path(args.cron_control, DEFAULT_CRON_CONTROL),
        "otel_control": workspace_path(args.otel_control, DEFAULT_OTEL_CONTROL),
        "workflow_advancement": workspace_path(args.workflow_advancement, DEFAULT_WORKFLOW_ADVANCEMENT),
        "wf87_readiness": workspace_path(args.wf87_readiness, DEFAULT_WF87_READINESS),
        "autonomy_spine": workspace_path(args.autonomy_spine, DEFAULT_AUTONOMY_SPINE),
    }
    sources = {name: load_json(path) for name, path in paths.items()}
    context = {
        "cron": cron_context(sources["cron_control"]),
        "otel": otel_context(sources["otel_control"]),
        "workflow_advancement": as_dict(sources["workflow_advancement"].get("summary")),
        "wf87_readiness_status": sources["wf87_readiness"].get("status"),
        "autonomy_spine_state": as_dict(sources["autonomy_spine"].get("summary")).get("final_state"),
    }
    rows = [docket_row(row, context) for row in dedupe_rows(collect_rows(sources))]
    rows.sort(key=lambda row: (STATE_ORDER.get(str(row.get("action_state")), 99), -int_value(row.get("priority")), str(row.get("title"))))
    counts: dict[str, int] = {state: 0 for state in ACTION_STATES}
    for row in rows:
        counts[str(row.get("action_state"))] = counts.get(str(row.get("action_state")), 0) + 1
    active_states = {"fix_now", "owner_decision", "proof_refresh", "skill_proposal"}
    next_row = next((row for row in rows if row.get("action_state") in active_states), None)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Classify WF74 learning-loop, workflow, patch, skill, and durable-memory opportunities into explicit review/action states.",
        "sources": {name: rel(path) for name, path in paths.items()},
        "source_status": {name: source_status(path) for name, path in paths.items()},
        "context": context,
        "summary": {
            "row_count": len(rows),
            "action_state_counts": counts,
            "active_action_count": sum(counts.get(state, 0) for state in active_states),
            "fix_now_count": counts.get("fix_now", 0),
            "owner_decision_count": counts.get("owner_decision", 0),
            "market_session_accrual_count": counts.get("market_session_accrual", 0),
            "monitor_only_count": counts.get("monitor_only", 0),
            "hard_stop_count": counts.get("hard_stop", 0),
            "highest_priority_state": rows[0]["action_state"] if rows else "monitor_only",
            "next_safe_action": next_row["next_action"] if next_row else "No active implementation action; continue scheduled proof and monitor-only followups.",
        },
        "rows": rows,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": GLOBAL_STOP_LINES,
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = payload["validation"]["status"]
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = as_list(payload.get("rows"))
    for row in rows:
        state = row.get("action_state")
        if state not in ACTION_STATES:
            errors.append(f"invalid_action_state:{row.get('docket_id')}:{state}")
        for key in ("docket_id", "source_kind", "source_id", "title", "next_action"):
            if not row.get(key):
                errors.append(f"row_missing_{key}:{row.get('docket_id')}")
        if not as_list(row.get("stop_lines")):
            errors.append(f"row_missing_stop_lines:{row.get('docket_id')}")
        if state in {"fix_now", "proof_refresh", "market_session_accrual", "monitor_only", "skill_proposal"} and not as_list(row.get("proof_commands")):
            warnings.append(f"row_missing_proof_commands:{row.get('docket_id')}")
    counts = as_dict(as_dict(payload.get("summary")).get("action_state_counts"))
    if sum(int_value(value) for value in counts.values()) != len(rows):
        errors.append("action_state_count_mismatch")
    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Decision Docket",
        "",
        f"- Generated UTC: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Fix now: {summary.get('fix_now_count')}",
        f"- Owner decisions: {summary.get('owner_decision_count')}",
        f"- Market-session accrual: {summary.get('market_session_accrual_count')}",
        f"- Monitor-only: {summary.get('monitor_only_count')}",
        f"- Next safe action: {summary.get('next_safe_action')}",
        "",
        "## Rows",
        "",
    ]
    for row in as_list(payload.get("rows")):
        lines.extend([
            f"### {row.get('title')}",
            f"- State: {row.get('action_state')}",
            f"- Priority: {row.get('priority')}",
            f"- Source: {row.get('source_kind')} / {row.get('source_id')}",
            f"- Reason: {row.get('classification_reason')}",
            f"- Next: {row.get('next_action')}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    out = workspace_path(args.out, DEFAULT_OUT)
    md = workspace_path(args.write_md, DEFAULT_MD)
    atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md, render_markdown(payload))
    result = {"out": rel(out)}
    if args.write_md:
        result["md"] = rel(md)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF74 V2 decision docket.")
    parser.add_argument("--opportunity-queue", default=str(DEFAULT_OPPORTUNITY_QUEUE))
    parser.add_argument("--router", default=str(DEFAULT_ROUTER))
    parser.add_argument("--auto-patch", default=str(DEFAULT_AUTO_PATCH))
    parser.add_argument("--improvement-ledger", default=str(DEFAULT_IMPROVEMENT_LEDGER))
    parser.add_argument("--cron-control", default=str(DEFAULT_CRON_CONTROL))
    parser.add_argument("--otel-control", default=str(DEFAULT_OTEL_CONTROL))
    parser.add_argument("--workflow-advancement", default=str(DEFAULT_WORKFLOW_ADVANCEMENT))
    parser.add_argument("--wf87-readiness", default=str(DEFAULT_WF87_READINESS))
    parser.add_argument("--autonomy-spine", default=str(DEFAULT_AUTONOMY_SPINE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write-md", nargs="?", const=str(DEFAULT_MD), default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    write_result = write_outputs(payload, args) if args.write else None
    print(json.dumps({
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
        "write_result": write_result,
    }, indent=2, sort_keys=True))
    if args.validate and payload.get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
