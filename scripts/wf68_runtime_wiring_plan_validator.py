#!/usr/bin/env python3
"""Validate WF68 runtime wiring phase-plan preview artifacts.

This validator is intentionally read-only. It checks that the runtime wiring plan
contains exact cron update previews, preserves the no-mutation boundary, and
keeps apply/runtime changes blocked pending owner approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "intraday-alerts" / "runtime-wiring-phase-plan.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "intraday-alerts" / "runtime-wiring-phase-plan-validation.json"

FALSE_AUTHORITY_FIELDS = [
    "live_trade_or_account_action_allowed",
    "paper_trade_allowed",
    "paper_or_live_order_submission_allowed",
    "paper_or_live_order_cancellation_allowed",
    "brokerage_account_mutation_allowed",
    "money_movement_allowed",
    "portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "call_log_mutation_allowed",
    "state_history_append_allowed_by_this_artifact",
    "channel_config_auth_runtime_mutation_allowed_by_this_artifact",
    "owner_approval_inferred",
    "probability_claims_allowed",
]

REQUIRED_PHASES = [
    "0_preflight",
    "1_shadow_artifact_status",
    "2_exact_job_preview",
    "3_manual_pre_enable_proof",
    "4_apply_runtime_wiring",
    "5_post_enable_validation",
    "6_pilot_observation",
]

REQUIRED_STATUS_TEXT = ["NO_REPLY", "ALERT_READY", "current_but_not_intraday_fresh", "action_needed"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def validate(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    data = load_json(path)
    text = json.dumps(data, sort_keys=True)

    if data.get("schema_version") != "wf68.runtime_wiring_phase_plan.v1":
        errors.append("schema_version must be wf68.runtime_wiring_phase_plan.v1")
    if data.get("workflow") != "WF68":
        errors.append("workflow must be WF68")
    if data.get("status") != "DESIGN_COMPLETE_NOT_APPLIED":
        errors.append("status must be DESIGN_COMPLETE_NOT_APPLIED")
    if data.get("actual_cron_mutation_applied") is not False:
        errors.append("actual_cron_mutation_applied must be false")
    if data.get("system_event_injection_applied") is not False:
        errors.append("system_event_injection_applied must be false")
    if data.get("runtime_wiring_apply_allowed_by_this_artifact") is not False:
        errors.append("runtime_wiring_apply_allowed_by_this_artifact must be false")

    phases = data.get("phases")
    if not isinstance(phases, list):
        errors.append("phases must be a list")
        phases = []
    phase_names = [p.get("phase") for p in phases if isinstance(p, dict)]
    for required in REQUIRED_PHASES:
        if required not in phase_names:
            errors.append(f"missing phase {required}")
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        if not phase.get("goal"):
            errors.append(f"phase {phase.get('phase')} missing goal")
        if not isinstance(phase.get("acceptance"), list) or not phase.get("acceptance"):
            errors.append(f"phase {phase.get('phase')} missing acceptance list")

    patches = data.get("proposed_cron_update_patches")
    if not isinstance(patches, dict):
        errors.append("proposed_cron_update_patches must be an object")
        patches = {}
    for key, expected_target, expected_kind in [
        ("producer", "isolated", "agentTurn"),
        ("handoff", "main", "systemEvent"),
    ]:
        item = patches.get(key)
        if not isinstance(item, dict):
            errors.append(f"missing {key} patch")
            continue
        if not item.get("jobId"):
            errors.append(f"{key} patch missing jobId")
        patch = item.get("patch")
        if not isinstance(patch, dict):
            errors.append(f"{key}.patch must be object")
            continue
        schedule = patch.get("schedule") if isinstance(patch.get("schedule"), dict) else {}
        if schedule.get("kind") != "cron" or schedule.get("tz") != "America/Phoenix" or not schedule.get("expr"):
            errors.append(f"{key} schedule must be cron with America/Phoenix tz and expr")
        if patch.get("sessionTarget") != expected_target:
            errors.append(f"{key} sessionTarget must be {expected_target}")
        payload = patch.get("payload") if isinstance(patch.get("payload"), dict) else {}
        if payload.get("kind") != expected_kind:
            errors.append(f"{key} payload.kind must be {expected_kind}")
        if key == "producer":
            delivery = patch.get("delivery") if isinstance(patch.get("delivery"), dict) else {}
            if delivery.get("mode") != "none":
                errors.append("producer delivery.mode must be none")
            tools = payload.get("toolsAllow")
            if tools != ["read", "exec"]:
                errors.append("producer toolsAllow must be exactly ['read', 'exec']")
            if "cron" in (payload.get("toolsAllow") or []):
                errors.append("producer payload must not include cron tool/wake access")
        if key == "handoff":
            if "NO_REPLY" not in payload.get("text", "") or "ALERT_READY" not in payload.get("text", ""):
                errors.append("handoff systemEvent text must include NO_REPLY and ALERT_READY behavior")

    authority = data.get("authority_boundary") if isinstance(data.get("authority_boundary"), dict) else {}
    for field in FALSE_AUTHORITY_FIELDS:
        if authority.get(field) is not False:
            errors.append(f"authority_boundary.{field} must be false")

    if not isinstance(data.get("rollback_plan"), list) or len(data.get("rollback_plan", [])) < 2:
        errors.append("rollback_plan must include producer and handoff rollback steps")
    decision = str(data.get("operator_decision_required", ""))
    if "Approve" not in decision or "does not apply cron updates" not in decision:
        errors.append("operator_decision_required must preserve approval gate and no-apply statement")

    for phrase in REQUIRED_STATUS_TEXT:
        if phrase not in text:
            errors.append(f"missing required runtime behavior phrase: {phrase}")

    return {
        "schema_version": "wf68.runtime_wiring_phase_plan_validation.v1",
        "workflow": "WF68",
        "input": rel(path),
        "status": "ok" if not errors else "error",
        "critical_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "actual_cron_mutation_applied": data.get("actual_cron_mutation_applied") is True,
        "runtime_wiring_apply_allowed_by_this_artifact": data.get("runtime_wiring_apply_allowed_by_this_artifact") is True,
        "producer_job_preview_present": isinstance((patches.get("producer") if isinstance(patches, dict) else None), dict),
        "handoff_job_preview_present": isinstance((patches.get("handoff") if isinstance(patches, dict) else None), dict),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WF68 runtime wiring phase plan.")
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    result = validate(input_path)
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
