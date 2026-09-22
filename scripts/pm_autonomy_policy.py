#!/usr/bin/env python3
"""Policy contract for scheduled PM autonomy.

This is intentionally conservative. It allows unattended proof refreshes and
planning handoffs, not code patches, helper spawning, cron mutation, config
changes, finance/canon mutation, external delivery, or execution authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
DEFAULT_POLICY_PATH = STATE / "pm-autonomy-policy.json"

SCHEMA = "veritas.pm_autonomy_policy.v1"

DEFAULT_POLICY: dict[str, Any] = {
    "schema": SCHEMA,
    "enabled": True,
    "cadence": {
        "target_runs_per_day": 3,
        "timezone": "America/Phoenix",
        "recommended_cron": "52 7,14,20 * * *",
    },
    "default_model": {
        "model": "ollama-cloud/glm-5.3:cloud",
        "thinking": "medium",
        "role": "isolated scheduled PM implementation proof worker",
    },
    "allowed_action_classes": {
        "proof_refresh": True,
        "main_proof_refresh": True,
        "implementation_plan": True,
        "low_risk_code_change": False,
        "main_verification": True,
    },
    "automation_boundary": {
        "proof_only_without_prompt": True,
        "planning_without_prompt": True,
        "code_patch_without_prompt": False,
        "helper_spawn_without_main": False,
        "cron_schedule_mutation_allowed": False,
        "config_auth_runtime_mutation_allowed": False,
        "cleanup_move_delete_archive_allowed": False,
        "customer_or_external_delivery_allowed": False,
        "sql_or_ticker_import_allowed": False,
        "canon_or_portfolio_mutation_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "capital_deployment_allowed": False,
        "money_movement_allowed": False,
        "owner_approval_inferred": False,
    },
    "selection": {
        "max_jobs_per_run": 1,
        "minimum_ready_statuses": ["ready_for_main_or_helper", "ready_for_review"],
        "blocked_statuses": ["blocked", "owner_decision_required", "completed_by_ledger"],
        "prefer_cron_proof_eligible": True,
        "cron_proof_refresh_requires_explicit_graduation": True,
        "sort_order": [
            "automation_action_rank",
            "priority_band_rank",
            "source_priority_score_desc",
            "readiness_score_desc",
            "rank",
        ],
    },
    "required_frontdoor_refresh_commands": [
        "python scripts\\pm_control_packet.py --write --write-db --validate",
        "python scripts\\pm_implementation_job_queue.py --write --write-db --validate",
    ],
    "post_run_verification_commands": [
        "python scripts\\pm_control_packet.py --write --write-db --validate",
        "python scripts\\startup_brief_packet.py --write --validate",
        "python scripts\\status_card_packet.py --write --validate",
    ],
    "stop_lines": [
        "No unattended code patches in phase 1.",
        "No helper spawning from cron/heartbeat.",
        "No cron schedule/config/runtime mutation from the worker.",
        "No canon/portfolio/SQL import/customer/external/paper/live/account/capital action.",
    ],
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    loaded = as_dict(load_json_artifact(path))
    if not loaded:
        return dict(DEFAULT_POLICY)
    merged = dict(DEFAULT_POLICY)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            inner = dict(merged[key])
            inner.update(value)
            merged[key] = inner
        else:
            merged[key] = value
    return merged


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    boundary = as_dict(policy.get("automation_boundary"))
    if policy.get("schema") != SCHEMA:
        errors.append("schema")
    for key in (
        "code_patch_without_prompt",
        "helper_spawn_without_main",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "cleanup_move_delete_archive_allowed",
        "customer_or_external_delivery_allowed",
        "sql_or_ticker_import_allowed",
        "canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "capital_deployment_allowed",
        "money_movement_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(key) is not False:
            errors.append(f"automation_boundary.{key}")
    classes = as_dict(policy.get("allowed_action_classes"))
    if classes.get("low_risk_code_change") is not False:
        errors.append("allowed_action_classes.low_risk_code_change")
    if classes.get("proof_refresh") is not True:
        errors.append("allowed_action_classes.proof_refresh")
    if classes.get("main_proof_refresh") is not True:
        errors.append("allowed_action_classes.main_proof_refresh")
    if classes.get("implementation_plan") is not True:
        errors.append("allowed_action_classes.implementation_plan")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="Write/validate the PM autonomy policy.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_POLICY_PATH)
    args = parser.parse_args()

    policy = load_policy(args.out)
    validation = validate_policy(policy)
    policy["validation"] = validation
    if args.write:
        atomic_write_json(args.out, policy)
        print(f"wrote {rel(args.out)} status={validation['status']}")
    else:
        print(json.dumps({"status": validation["status"], "policy": policy}, indent=2, sort_keys=True))
    if args.validate and validation["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
