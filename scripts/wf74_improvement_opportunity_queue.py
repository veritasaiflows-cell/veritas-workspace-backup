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
    }


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
    return {
        "schema": "veritas.wf74_improvement_opportunity.v1",
        "opportunity_id": f"{category}-{stable_id(title, signal, priority)}",
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


def build_opportunities(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    runner_summary = as_dict(inputs["wf74_runner"].get("summary"))
    coding_runtime = as_dict(inputs["coding_runtime"].get("kpis"))
    coding_summary = as_dict(inputs["coding_outcome"].get("ledger_summary"))
    model_summary = as_dict(inputs["model_run"].get("summary"))
    otel_drift = as_dict(inputs["otel_ops"].get("drift"))
    field_depth = inputs["field_depth_packet"]
    finance_summary = as_dict(inputs["finance_response"].get("summary"))
    opportunities: list[dict[str, Any]] = []

    coding_rows = int(as_num(coding_summary.get("ledger_row_count")))
    coding_model_attr = int(as_num(coding_summary.get("model_attributed_count")))
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
        opportunities.append(opportunity(
            category="collector_config",
            title="Review OTEL event-rate drift against the weekly baseline",
            priority=88,
            signal="otel_operational_drift_review",
            evidence={
                "daily_warning_or_error_count": otel_drift.get("daily_warning_or_error_count"),
                "daily_vs_weekly_event_rate_ratio": otel_drift.get("daily_vs_weekly_event_rate_ratio"),
                "drift_reasons": otel_drift.get("drift_reasons"),
            },
            recommended_action=(
                "Track whether the drift persists for another collection window before proposing collector-depth changes."
            ),
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
    remediation_tracks = int(as_num(finance_summary.get("remediation_tracks_needing_repair")))
    if source_freshness_blocked or remediation_tracks:
        opportunities.append(opportunity(
            category="finance_mutation",
            title="Route finance response-quality gaps into repair proposals",
            priority=86,
            signal="finance_response_quality_repair_signal",
            evidence={
                "sector_timing_warning_available": finance_summary.get("sector_timing_warning_available"),
                "source_freshness_blocked_count": source_freshness_blocked,
                "remediation_tracks_needing_repair": remediation_tracks,
                "average_quality_score": finance_summary.get("average_quality_score"),
            },
            recommended_action=(
                "Create repair proposals for source-freshness/remediation gaps; do not mutate finance canon or portfolio state from WF74."
            ),
            proposal_gate="finance_repair_proposal_only",
            validation_command="python scripts\\finance_response_quality_slice.py --write --write-md --validate",
        ))

    if int(as_num(runner_summary.get("wf74_runner_steps_blocked") or runner_summary.get("steps_blocked"))):
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
    for row in as_list(payload.get("opportunities")):
        if as_dict(row).get("proposal_gate") in {"auto_apply", "auto_execute"}:
            errors.append(f"forbidden_auto_gate:{row.get('opportunity_id')}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    opportunities = build_opportunities(inputs)
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
        },
        "summary": {
            "opportunity_count": len(opportunities),
            "high_priority_count": sum(1 for row in opportunities if int(row["priority"]) >= 85),
            "by_category": dict(sorted(by_category.items())),
            "by_proposal_gate": dict(sorted(by_gate.items())),
            "top_opportunity_id": opportunities[0]["opportunity_id"] if opportunities else None,
            "top_opportunity_title": opportunities[0]["title"] if opportunities else None,
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
        f"- High priority: {summary.get('high_priority_count')}",
        f"- Top: {summary.get('top_opportunity_title')}",
        "",
        "## Top Opportunities",
    ]
    for row in as_list(payload.get("opportunities"))[:8]:
        lines.append(f"- {row.get('priority')} | {row.get('category')} | {row.get('title')} | gate={row.get('proposal_gate')}")
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
