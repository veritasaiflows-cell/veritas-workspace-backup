#!/usr/bin/env python3
"""Build a review-only cron cadence reduction plan from live scheduler metadata.

The plan is intentionally non-mutating. It identifies effort normalization,
no-token system jobs to preserve, and high-cost/error candidates for repair or
cadence thinning. Live edits still require an explicit operator pass.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import agent_fleet_policy as fleet_policy
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "cron-cadence-reduction-plan.json"
TOKEN_SUMMARY = TMP / "cron-runs-2026-06-15-cost-summary.json"
PRICING = ROOT / "state" / "model-token-pricing.json"
SCHEMA = "veritas.cron_cadence_reduction_plan.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def openclaw_cmd() -> str:
    found = shutil.which("openclaw.cmd") or shutil.which("openclaw") or shutil.which("openclaw.ps1")
    if found:
        return found
    known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
    return str(known) if known.exists() else "openclaw.cmd"


def load_live_jobs(live_file: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if live_file:
        payload = load_json_artifact(live_file)
        return [row for row in as_list(as_dict(payload).get("jobs")) if isinstance(row, dict)], {"source": str(live_file), "ok": True}
    completed = subprocess.run(
        [openclaw_cmd(), "cron", "list", "--all", "--json", "--timeout", "30000"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=45,
    )
    meta = {"source": "openclaw cron list --all --json", "ok": completed.returncode == 0, "returncode": completed.returncode, "stderr_tail": (completed.stderr or "")[-2000:]}
    if completed.returncode != 0:
        return [], meta
    payload = json.loads(completed.stdout)
    return [row for row in as_list(payload.get("jobs")) if isinstance(row, dict)], meta


def desired_thinking(model: str | None) -> tuple[str | None, str | None]:
    if model == fleet_policy.GLM_FLASH_MODEL:
        return "low", "GLM 5.3 Flash is reserved for proven deterministic cron/status/proof jobs at low reasoning."
    if model == fleet_policy.GLM_MODEL:
        return "medium", "GLM 5.3 is the default for reasoning or tool-heavy cron helpers."
    if model == fleet_policy.MAIN_PRIMARY:
        return "medium", "The Main model is reserved for main-session/final judgment, not routine cron."
    if model == fleet_policy.BUILDER_MODEL:
        return "medium", "Muse Spark 1.3 is reserved for code authoring, not routine cron."
    if model == fleet_policy.KIMI_MODEL:
        return "medium", "Kimi K3 is a Main fallback, not the normal active cron route."
    if fleet_policy.is_denied_persistent_model(model or ""):
        return "medium", "Retired route: repoint this job to GLM 5.3 before tuning effort."
    return None, None


def payload_model(job: dict[str, Any]) -> str | None:
    return as_dict(job.get("payload")).get("model")


def payload_thinking(job: dict[str, Any]) -> str | None:
    return as_dict(job.get("payload")).get("thinking")


def build_effort_patches(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patches = []
    for job in jobs:
        payload = as_dict(job.get("payload"))
        if payload.get("kind") != "agentTurn":
            continue
        desired, reason = desired_thinking(payload.get("model"))
        if desired and payload.get("thinking") != desired:
            patches.append({
                "job_id": job.get("id"),
                "name": job.get("name"),
                "enabled": job.get("enabled"),
                "model": payload.get("model"),
                "current_thinking": payload.get("thinking"),
                "recommended_thinking": desired,
                "reason": reason,
                "command": f"openclaw cron edit {job.get('id')} --thinking {desired}",
            })
    return patches


def cost_reduction_candidates(token_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in as_list(token_summary.get("jobs")):
        if not isinstance(item, dict):
            continue
        tokens = int(item.get("total_tokens") or 0)
        cost = item.get("estimated_known_cost_usd")
        errors = int(item.get("error") or 0)
        runs = int(item.get("runs") or 0)
        reasons = []
        if errors:
            reasons.append("repair_before_more_cadence")
        if cost is not None and float(cost) >= 0.05:
            reasons.append("high_cost_row")
        if runs >= 3 and tokens >= 100_000:
            reasons.append("multi_run_cadence_thinning_candidate")
        if not reasons:
            continue
        rows.append({
            "job": item.get("job"),
            "runs": runs,
            "errors": errors,
            "total_tokens": tokens,
            "estimated_known_cost_usd": cost,
            "reason": reasons,
            "recommended_reduction_action": (
                "fix_error_or_runner_contract_first" if errors else
                "consider_changed_only_mode_or_reduce_intraday_windows"
            ),
        })
    return sorted(rows, key=lambda row: (row.get("estimated_known_cost_usd") or 0, row.get("total_tokens") or 0), reverse=True)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    jobs, live_meta = load_live_jobs(args.live_file)
    pricing = as_dict(load_json_artifact(args.pricing_file))
    token_summary = as_dict(load_json_artifact(args.token_summary_file))
    enabled_jobs = [job for job in jobs if job.get("enabled") is True]
    agent_jobs = [job for job in jobs if as_dict(job.get("payload")).get("kind") == "agentTurn"]
    system_jobs = [job for job in jobs if as_dict(job.get("payload")).get("kind") != "agentTurn"]
    effort_patches = build_effort_patches(jobs)
    model_counts = Counter(str(payload_model(job) or "non-agent/system") for job in jobs)
    summary = {
        "live_job_count": len(jobs),
        "enabled_job_count": len(enabled_jobs),
        "agent_turn_job_count": len(agent_jobs),
        "non_agent_or_system_job_count": len(system_jobs),
        "model_counts": dict(sorted(model_counts.items())),
        "effort_patch_count": len(effort_patches),
        "enabled_effort_patch_count": sum(1 for row in effort_patches if row.get("enabled") is True),
        "pricing_table_status": pricing.get("status") if pricing else "missing",
        "token_summary_present": bool(token_summary),
    }
    non_agent_preserve = [{
        "job_id": job.get("id"),
        "name": job.get("name"),
        "enabled": job.get("enabled"),
        "recommendation": "keep_as_system_event_or_non_agent_job_unless_human_synthesis_is_required",
    } for job in system_jobs]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if live_meta.get("ok") else "warning",
        "purpose": "Review-only reduction plan for cron effort, cost, and cadence noise.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "live_source": live_meta,
        "policy": {
            fleet_policy.GLM_FLASH_MODEL: "low for proven deterministic agentTurn cron/status/proof jobs",
            fleet_policy.GLM_MODEL: "medium for reasoning or tool-heavy cron helpers",
            fleet_policy.MAIN_PRIMARY: "main-session/final judgment only",
            fleet_policy.BUILDER_MODEL: "code authoring only",
            fleet_policy.KIMI_MODEL: "Main fallback only",
            "non_agent_or_system": "keep no-token path; do not convert command jobs to an LLM",
        },
        "summary": summary,
        "effort_patches": effort_patches,
        "non_agent_jobs_to_preserve": non_agent_preserve,
        "cost_reduction_candidates": cost_reduction_candidates(token_summary),
        "implementation_sequence": [
            "Normalize effort settings first because this is low-risk and reduces reasoning/token pressure.",
            "Preserve no-token command/system jobs rather than converting them to an LLM.",
            "Repair erroring high-cost jobs before adding cadence or running extra confirmations.",
            "Thin repeated intraday jobs only after the finance brief/status spine proves changed-only coverage.",
            "Add any new cadence only with a contract, stale-input guard, token threshold, and rollback note.",
        ],
        "validation": {
            "status": "ok" if jobs and pricing else "warning",
            "warnings": [] if pricing else ["pricing_table_missing"],
            "errors": [] if jobs else ["live_cron_jobs_unavailable"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--live-file", type=Path)
    parser.add_argument("--pricing-file", type=Path, default=PRICING)
    parser.add_argument("--token-summary-file", type=Path, default=TOKEN_SUMMARY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    if args.write:
        atomic_write_json(args.json_out, payload)
    if args.validate and payload.get("validation", {}).get("errors"):
        print(f"status={payload.get('status')} validation=error out={args.json_out}")
        return 1
    print(
        f"status={payload.get('status')} effort_patches={payload.get('summary', {}).get('effort_patch_count')} "
        f"enabled_effort_patches={payload.get('summary', {}).get('enabled_effort_patch_count')} out={args.json_out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
