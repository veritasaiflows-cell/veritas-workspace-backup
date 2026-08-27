#!/usr/bin/env python3
"""Build a review-only Phase 2A cron reduction patch packet.

The packet proposes exact live cron add/disable commands for the two
non-market Phase 2A reductions after fresh local proof passes. It does not
apply cron changes. Live mutation still requires Randall's exact approval of
the generated packet.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.cron_reduction_phase2a_patch_packet.v1"
DEFAULT_OUT = TMP / "cron-reduction-phase2a-patch-packet.json"
DEFAULT_MD_OUT = TMP / "cron-reduction-phase2a-patch-packet.md"
DEFAULT_INVENTORY = TMP / "cron-reduction-inventory.json"
DEFAULT_PHASE2 = TMP / "cron-phase2-shadow-parity.json"
DEFAULT_POSTCLOSE = TMP / "postclose-paper-reconciliation-runner.json"
DEFAULT_WF68 = TMP / "wf68-alert-digest-consolidated-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_patch_packet_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "job_add_disable_delete_allowed": False,
    "runtime_config_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}

PHASE2A_CONTRACT_IDS = [
    "phase2_postclose_paper_reconciliation",
    "phase2_wf68_alert_digest",
]

COMPONENT_NAMES = {
    "phase2_postclose_paper_reconciliation": "postclose_paper_reconciliation",
    "phase2_wf68_alert_digest": "wf68_alert_digest",
}

RUNNER_PATHS = {
    "phase2_postclose_paper_reconciliation": DEFAULT_POSTCLOSE,
    "phase2_wf68_alert_digest": DEFAULT_WF68,
}

REPLACEMENT_SCHEDULES = {
    "phase2_postclose_paper_reconciliation": {
        "cron": "40 14 * * 1-5",
        "tz": "America/Phoenix",
        "timing_note": "Runs after the old 13:50 paper-position refresh and 14:36 WF86 reconciliation windows.",
    },
    "phase2_wf68_alert_digest": {
        "cron": "5 8,13 * * 1-5",
        "tz": "America/Phoenix",
        "timing_note": "Keeps a morning producer pass and an afternoon grouped-digest pass in one enabled job.",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def contract_by_id(inventory: dict[str, Any], contract_id: str) -> dict[str, Any]:
    for contract in as_list(inventory.get("contracts")):
        row = as_dict(contract)
        if row.get("id") == contract_id:
            return row
    return {}


def component_by_name(phase2: dict[str, Any], name: str) -> dict[str, Any]:
    for component in as_list(phase2.get("components")):
        row = as_dict(component)
        if row.get("name") == name:
            return row
    return {}


def quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def command_argv(runner_command: str) -> list[str]:
    parts = runner_command.split()
    if not parts:
        return []
    if parts[0].lower() == "python":
        return ["python", *parts[1:]]
    return parts


def add_command(job: dict[str, Any]) -> str:
    argv = json.dumps(job["command_argv"])
    return " ".join([
        "openclaw", "cron", "add",
        "--name", quote(job["name"]),
        "--description", quote(job["description"]),
        "--cron", quote(job["schedule"]["cron"]),
        "--tz", job["schedule"]["tz"],
        "--command-argv", quote(argv),
        "--command-cwd", quote(str(ROOT)),
        "--timeout-seconds", str(job["timeout_seconds"]),
        "--no-deliver",
        "--json",
    ])


def disable_command(job_id: str) -> str:
    return f"openclaw cron disable {job_id} --timeout 30000"


def enable_command(job_id: str) -> str:
    return f"openclaw cron enable {job_id} --timeout 30000"


def source_jobs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = []
    for job in as_list(contract.get("source_jobs_found")):
        row = as_dict(job)
        if row:
            jobs.append(row)
    return jobs


def replacement_live_state(inventory: dict[str, Any], name: str) -> dict[str, Any]:
    matches = []
    for group_name in ("enabled_jobs", "disabled_jobs"):
        for job in as_list(inventory.get(group_name)):
            row = as_dict(job)
            if row.get("name") == name:
                matches.append({
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "enabled": row.get("enabled"),
                    "source": group_name,
                })
    return {"exists": bool(matches), "matches": matches}


def replacement_job(contract_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    schedule = REPLACEMENT_SCHEDULES[contract_id]
    timeout = int(contract.get("hard_timeout_seconds") or contract.get("target_seconds") or 900)
    name = str(contract.get("replacement_job_name") or "")
    runner_command = str(contract.get("runner_command") or "")
    return {
        "contract_id": contract_id,
        "name": name,
        "description": (
            f"Phase 2A cron reduction replacement for {', '.join(contract.get('source_jobs') or [])}. "
            "Review-only command job; no capital/execution/account/config/canon authority."
        ),
        "schedule": schedule,
        "command_argv": command_argv(runner_command),
        "command_cwd": str(ROOT),
        "timeout_seconds": timeout,
        "expected_output": RUNNER_PATHS[contract_id].as_posix(),
    }


def build_batch(contract_id: str, inventory: dict[str, Any], phase2: dict[str, Any]) -> dict[str, Any]:
    contract = contract_by_id(inventory, contract_id)
    component = component_by_name(phase2, COMPONENT_NAMES[contract_id])
    runner = load_json(RUNNER_PATHS[contract_id])
    replacement = replacement_job(contract_id, contract)
    live_replacement = replacement_live_state(inventory, replacement["name"])
    jobs = source_jobs(contract)
    disable_jobs = [
        {
            "id": str(job.get("id") or ""),
            "name": str(job.get("name") or ""),
            "enabled": bool(job.get("enabled")),
            "schedule": job.get("schedule"),
            "disable_command": disable_command(str(job.get("id") or "")),
            "rollback_enable_command": enable_command(str(job.get("id") or "")),
        }
        for job in jobs
    ]
    return {
        "contract_id": contract_id,
        "component": component,
        "runner_status": {
            "path": rel(RUNNER_PATHS[contract_id]),
            "status": runner.get("status"),
            "validation_status": as_dict(runner.get("validation")).get("status"),
            "operator_action": runner.get("operator_action"),
            "generated_at_utc": runner.get("generated_at_utc"),
            "elapsed_seconds": runner.get("elapsed_seconds"),
            "authority_boundary": runner.get("authority_boundary"),
        },
        "replacement_job": {
            **replacement,
            "add_command": add_command(replacement),
            "live_state": live_replacement,
            "rollback_disable_command_template": f"openclaw cron disable {{{{{contract_id}_replacement_job_id}}}} --timeout 30000",
        },
        "source_jobs_to_disable": disable_jobs,
        "expected_enabled_savings": max(0, len(disable_jobs) - 1),
        "disable_gate": contract.get("disable_gate"),
    }


def validate_batch(batch: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    contract_id = str(batch.get("contract_id") or "unknown")
    component = as_dict(batch.get("component"))
    runner = as_dict(batch.get("runner_status"))
    replacement = as_dict(batch.get("replacement_job"))
    live_state = as_dict(replacement.get("live_state"))
    source_jobs = as_list(batch.get("source_jobs_to_disable"))
    if component.get("status") != "ok":
        errors.append(f"{contract_id}:component_status_not_ok:{component.get('status')}")
    if component.get("validation_status") != "ok":
        errors.append(f"{contract_id}:component_validation_not_ok:{component.get('validation_status')}")
    if component.get("safe_to_disable_source_jobs") is not True:
        errors.append(f"{contract_id}:safe_to_disable_source_jobs_not_true")
    if runner.get("status") != "ok":
        errors.append(f"{contract_id}:runner_status_not_ok:{runner.get('status')}")
    if runner.get("validation_status") != "ok":
        errors.append(f"{contract_id}:runner_validation_not_ok:{runner.get('validation_status')}")
    if runner.get("operator_action") != "NO_REPLY":
        errors.append(f"{contract_id}:runner_operator_action_not_no_reply:{runner.get('operator_action')}")
    if live_state.get("exists"):
        errors.append(f"{contract_id}:replacement_job_already_exists")
    if len(source_jobs) < 2:
        errors.append(f"{contract_id}:expected_two_source_jobs_found:{len(source_jobs)}")
    for job in source_jobs:
        if not as_dict(job).get("id"):
            errors.append(f"{contract_id}:source_job_missing_id")
        if as_dict(job).get("enabled") is not True:
            errors.append(f"{contract_id}:source_job_not_enabled:{as_dict(job).get('name')}")
    return errors


def build_payload(inventory: dict[str, Any], phase2: dict[str, Any]) -> dict[str, Any]:
    batches = [build_batch(contract_id, inventory, phase2) for contract_id in PHASE2A_CONTRACT_IDS]
    current_enabled = int(as_dict(inventory.get("summary")).get("enabled_jobs") or 0)
    replacement_count = len(batches)
    disable_count = sum(len(as_list(batch.get("source_jobs_to_disable"))) for batch in batches)
    net_savings = sum(int(batch.get("expected_enabled_savings") or 0) for batch in batches)
    validation_errors = [
        error
        for batch in batches
        for error in validate_batch(batch)
    ]
    if as_dict(phase2.get("validation")).get("status") == "ok":
        validation_warnings: list[str] = []
    else:
        validation_warnings = [
            "phase2_overall_still_blocked_by_market_window_components",
        ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "error" if validation_errors else "ok",
        "purpose": "Owner-review packet for Phase 2A non-market cron reduction. It proposes commands but does not apply them.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "current_state": {
            "enabled_jobs": current_enabled,
            "disabled_jobs": as_dict(inventory.get("summary")).get("disabled_jobs"),
            "total_jobs": as_dict(inventory.get("summary")).get("total_jobs"),
            "target_enabled_range": "25-27",
        },
        "phase2a_patch_summary": {
            "replacement_jobs_to_create": replacement_count,
            "source_jobs_to_disable": disable_count,
            "expected_net_enabled_savings": net_savings,
            "projected_enabled_jobs_after_patch": current_enabled - net_savings if current_enabled else None,
            "requires_owner_approval_before_apply": True,
        },
        "batches": batches,
        "apply_sequence": [
            "Confirm this exact packet with Randall.",
            "Create replacement cron jobs first and record their returned IDs.",
            "Run both replacement cron jobs manually or wait for first scheduled proof if required by owner gate.",
            "Disable listed source jobs only after replacement proof remains clean.",
            "Run post-apply validation commands.",
        ],
        "post_apply_validation_commands": [
            "python scripts\\cron_reduction_inventory.py --write --validate",
            "python scripts\\cron_contract_validator.py --require-contracts --fail-on-drift --fail-on-prompt-bloat --write --validate",
            "python scripts\\cron_control_packet.py --write --validate",
            "python scripts\\cron_reduction_next_patch_plan.py --write --validate",
            "python scripts\\automation_stack_hardening_pass.py --write --validate",
            "python scripts\\control_closeout_bundle.py --validation-budget shared --write --validate",
        ],
        "rollback_template": [
            "Disable any newly created replacement job IDs from this packet.",
            "Re-enable each source job listed under source_jobs_to_disable.",
            "Rerun the post-apply validation commands.",
        ],
        "stop_lines": [
            "This packet does not apply live cron changes.",
            "Do not disable source jobs until the exact replacement job IDs and post-create proof are recorded.",
            "Do not use this packet for Phase 2 market-window WF85/WF87/Tier-A reductions.",
            "No finance canon, portfolio, paper/live/account, cash/sizing, external/customer, config/auth/runtime, money movement, or owner-approval inference.",
        ],
        "validation": {
            "status": "error" if validation_errors else "warning" if validation_warnings else "ok",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }
    return payload


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = as_dict(payload.get("phase2a_patch_summary"))
    lines = [
        "# Cron Reduction Phase 2A Patch Packet",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Replacement jobs to create: `{summary.get('replacement_jobs_to_create')}`",
        f"- Source jobs to disable: `{summary.get('source_jobs_to_disable')}`",
        f"- Expected net savings: `{summary.get('expected_net_enabled_savings')}` enabled jobs",
        f"- Projected enabled count: `{summary.get('projected_enabled_jobs_after_patch')}`",
        f"- Owner approval required before apply: `{str(summary.get('requires_owner_approval_before_apply')).lower()}`",
        "",
        "## Proposed Commands",
    ]
    for batch in as_list(payload.get("batches")):
        replacement = as_dict(as_dict(batch).get("replacement_job"))
        lines.extend([
            "",
            f"### {replacement.get('name')}",
            f"- Schedule: `{as_dict(replacement.get('schedule')).get('cron')}` `{as_dict(replacement.get('schedule')).get('tz')}`",
            f"- Timing note: {as_dict(replacement.get('schedule')).get('timing_note')}",
            "",
            "Create replacement:",
            "```powershell",
            str(replacement.get("add_command") or ""),
            "```",
            "",
            "Disable sources after replacement proof:",
        ])
        for job in as_list(as_dict(batch).get("source_jobs_to_disable")):
            row = as_dict(job)
            lines.extend([
                f"- `{row.get('name')}`",
                "```powershell",
                str(row.get("disable_command") or ""),
                "```",
            ])
    lines.extend([
        "",
        "## Validation",
        f"- Status: `{as_dict(payload.get('validation')).get('status')}`",
        f"- Errors: `{len(as_list(as_dict(payload.get('validation')).get('errors')))}`",
        f"- Warnings: `{len(as_list(as_dict(payload.get('validation')).get('warnings')))}`",
        "",
        "## Boundary",
        "- Review-only packet. No live cron changes were applied by this artifact.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Phase 2A cron reduction patch packet.")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--phase2", default=str(DEFAULT_PHASE2))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    md_out = workspace_path(args.md_out)
    payload = build_payload(
        inventory=load_json(workspace_path(args.inventory)),
        phase2=load_json(workspace_path(args.phase2)),
    )
    if args.write:
        atomic_write_json(out, payload, indent=2)
    if args.write_md:
        write_markdown(md_out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "md_out": rel(md_out),
        "summary": payload.get("phase2a_patch_summary"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
