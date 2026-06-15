#!/usr/bin/env python3
"""Validate WF68 Phase 7 runtime handoff design artifacts.

This validator is intentionally read-only. It checks that the Phase 7 artifact is
proposal-only, preserves no-mutation boundaries, names the runtime handoff
contract, and does not imply cron/systemEvent/config/channel/trade/account/canon
or Call Log authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "intraday-alerts" / "runtime-handoff-design.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "intraday-alerts" / "runtime-handoff-design-validation.json"

REQUIRED_BOUNDARY_FALSE_FLAGS = [
    "cron_mutation_allowed",
    "system_event_injection_allowed_by_this_artifact",
    "channel_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "brokerage_account_mutation_allowed",
    "paper_trade_allowed",
    "live_trade_or_account_action_allowed",
    "portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "call_log_mutation_allowed",
    "owner_approval_inferred",
]

REQUIRED_PHRASES = {
    "quiet NO_REPLY behavior": ["NO_REPLY", "exactly NO_REPLY"],
    "changed-alert ALERT_READY behavior": ["ALERT_READY", "changed alert"],
    "stale/no-fire downgrade": ["current_but_not_intraday_fresh", "no-fire"],
    "main-session fallback/watchdog": ["main-session", "watchdog"],
    "failure/action-needed visibility": ["failure", "action-needed"],
    "approval gates before runtime mutation": ["approval", "runtime mutation"],
}


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

    if data.get("schema_version") != "wf68.runtime_handoff_design.v1":
        errors.append("schema_version must be wf68.runtime_handoff_design.v1")
    if data.get("workflow") != "WF68":
        errors.append("workflow must be WF68")
    if data.get("phase") != "phase_7_runtime_handoff_design":
        errors.append("phase must be phase_7_runtime_handoff_design")
    if data.get("actual_runtime_mutation_applied") is not False:
        errors.append("actual_runtime_mutation_applied must be false")
    if data.get("runtime_mutation_remains_blocked") is not True:
        errors.append("runtime_mutation_remains_blocked must be true")

    boundary = data.get("no_mutation_boundary")
    if not isinstance(boundary, dict):
        errors.append("no_mutation_boundary must be an object")
        boundary = {}
    for flag in REQUIRED_BOUNDARY_FALSE_FLAGS:
        if boundary.get(flag) is not False:
            errors.append(f"no_mutation_boundary.{flag} must be false")

    jobs = data.get("proposed_jobs")
    if not isinstance(jobs, list) or len(jobs) < 2:
        errors.append("proposed_jobs must include at least producer and main-session handoff proposals")
    else:
        job_text = json.dumps(jobs, sort_keys=True)
        if "isolated" not in job_text:
            errors.append("proposed_jobs must include isolated producer semantics")
        if "systemEvent" not in job_text:
            errors.append("proposed_jobs must include main-session systemEvent handoff semantics")
        if "delivery_mode" not in job_text:
            warnings.append("proposed_jobs should name delivery mode")

    contract = data.get("input_output_contract")
    if not isinstance(contract, dict):
        errors.append("input_output_contract must be an object")
    else:
        statuses = contract.get("handoff_status_values")
        if not isinstance(statuses, dict):
            errors.append("input_output_contract.handoff_status_values must be an object")
        else:
            for status in ["NO_REPLY", "ALERT_READY", "BLOCKED_VALIDATION_ERROR", "STALE_OR_NO_FIRE_DOWNGRADE"]:
                if status not in statuses:
                    errors.append(f"handoff_status_values missing {status}")

    gates = data.get("approval_gates_before_runtime_mutation")
    if not isinstance(gates, list) or len(gates) < 5:
        errors.append("approval_gates_before_runtime_mutation must include multiple explicit gates")

    checklist = data.get("testable_acceptance_checklist")
    if not isinstance(checklist, list) or len(checklist) < 6:
        errors.append("testable_acceptance_checklist must include testable acceptance items")

    for label, phrases in REQUIRED_PHRASES.items():
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            errors.append(f"required contract missing {label}: {', '.join(missing)}")

    forbidden_true_fragments = [
        '"cron_mutation_allowed": true',
        '"system_event_injection_allowed_by_this_artifact": true',
        '"channel_mutation_allowed": true',
        '"paper_trade_allowed": true',
        '"live_trade_or_account_action_allowed": true',
        '"portfolio_mutation_allowed": true',
        '"canonical_note_mutation_allowed": true',
        '"call_log_mutation_allowed": true',
        '"owner_approval_inferred": true',
    ]
    for fragment in forbidden_true_fragments:
        if fragment in text:
            errors.append(f"forbidden authority true fragment present: {fragment}")

    return {
        "schema_version": "wf68.runtime_handoff_design_validation.v1",
        "workflow": "WF68",
        "phase": "phase_7_runtime_handoff_design",
        "input": rel(path),
        "status": "ok" if not errors else "error",
        "critical_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "runtime_mutation_remains_blocked": data.get("runtime_mutation_remains_blocked") is True,
        "actual_runtime_mutation_applied": data.get("actual_runtime_mutation_applied") is True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WF68 Phase 7 runtime handoff design.")
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--write", action="store_true", help="write validation artifact")
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
