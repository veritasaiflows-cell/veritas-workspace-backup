#!/usr/bin/env python3
"""Recommend a safe parallel helper lane and spawn packet.

This script is coordination proof only. It does not spawn sessions, mutate cron,
write canon/portfolio state, infer approval, or grant execution authority. It
chooses a narrow read-only/helper lane, checks write-surface collisions against
the concurrent lane register, and emits the lease command plus OpenClaw
sessions_spawn arguments for the main session to use.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.pm_control_reader import pm_implementation_job_queue
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "parallel-lane-recommendation.json"
WORKFLOW_INDEX = TMP / "workflow-routing-index.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
WF78_EVENT_QUEUE = TMP / "wf78-event-triggered-rerouting.json"
AUTOMATION_HARDENING = TMP / "automation-stack-hardening-pass.json"

SCHEMA = "veritas.parallel_lane_recommender.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "recommendation_only": True,
    "spawns_helpers": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "capital_deployment_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "recommendation_only"}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}

FORBIDDEN_WRITE_PATTERNS = [
    r"^\.openclaw[\\/]",
    r"^~?[\\/]?\.openclaw[\\/]",
    r"(^|[\\/])openclaw\.json$",
    r"(^|[\\/])\.env($|[\\/])",
    r"(^|[\\/])credentials?($|[\\/])",
    r"(^|[\\/])secrets?($|[\\/])",
    r"(^|[\\/])09\. Archive[\\/]",
    r"(^|[\\/])backups[\\/]",
    r"^03\. Portfolio[\\/]",
    r"^04\. Research[\\/]Coverage and Watchlist\.md$",
    r"^data[\\/]finance[\\/]universe-v1\.json$",
    r"^state[\\/]finance[\\/]",
    r"^TOOLS\.md$",
    r"^MEMORY\.md$",
    r"^SOUL\.md$",
    r"^AGENTS\.md$",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def workflow_route(routes: list[dict[str, Any]], workflow_id: str) -> dict[str, Any]:
    wanted = workflow_id.upper()
    for route in routes:
        if str(route.get("workflow_id") or "").upper() == wanted:
            return route
    return {}


def active_lane_writes(register: dict[str, Any]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for lane in as_list(register.get("lanes")):
        lane_dict = as_dict(lane)
        if lane_dict.get("status") not in {"planned", "leased", "running"}:
            continue
        lane_id = str(lane_dict.get("lane_id") or "")
        for path in as_list(lane_dict.get("allowed_writes")):
            normalized = normalize_path(str(path))
            if normalized:
                owners.setdefault(normalized, []).append(lane_id)
    return owners


def completed_lane_ids(register: dict[str, Any]) -> set[str]:
    completed: set[str] = set()
    for lane in as_list(register.get("lanes")):
        lane_dict = as_dict(lane)
        if lane_dict.get("status") != "complete":
            continue
        workflow_id = str(lane_dict.get("workflow_id") or "").upper()
        workstream_id = str(lane_dict.get("workstream_id") or "")
        if workflow_id and workstream_id:
            completed.add(f"{workflow_id}::{workstream_id}")
    return completed


def forbidden_write(path: str) -> str | None:
    normalized = normalize_path(path)
    for pattern in FORBIDDEN_WRITE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return pattern
    return None


def base_templates() -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": "WF78",
            "workstream_id": "event-rerouting-qa",
            "title": "WF78 event-rerouting QA lane",
            "reason": "Highest-leverage parallel lane while WF78 implementation continues: verify top AI work-selection actions without touching scripts or canonical surfaces.",
            "read_first": [
                "06. Playbooks/Project Continuity/Workflow 78 - 500 Ticker Finance Intelligence Scaleout.md",
                "tmp/wf78-event-triggered-rerouting.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/wf78-capital-review-queue.json",
                "tmp/market-execution-readiness-cron-hardening.json",
            ],
            "allowed_writes": ["tmp/parallel-lanes/wf78-event-rerouting-qa.json"],
            "acceptance_commands": [
                "python scripts\\wf78_event_triggered_rerouting.py --validate",
                "python scripts\\market_execution_readiness_cron_hardening.py --validate",
                "python scripts\\concurrent_lane_manager.py --validate",
            ],
            "deliverable": "A compact JSON QA packet confirming whether the top WF78 event-rerouting actions are source-backed, non-capital, non-executing, and ready for main-session integration.",
        },
        {
            "workflow_id": "WF72",
            "workstream_id": "a2-readonly-qa",
            "title": "WF72 A2 support-readiness QA lane",
            "reason": "Safe parallel lane while WF72 implementation continues: independently verify A2 read-only support/fallback posture without editing SQL, cache, or canon surfaces.",
            "read_first": [
                "06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md",
                "tmp/automation-stack-hardening-pass.json",
                "tmp/go-sql-consumer-authority-guard.json",
                "tmp/wf72-a2-consumer-authority-fallback-manifest.json",
                "tmp/wf72-a2-consumer-authority-fallback-values.json",
            ],
            "allowed_writes": ["tmp/parallel-lanes/wf72-a2-readonly-qa.json"],
            "acceptance_commands": [
                "python scripts\\automation_stack_hardening_pass.py --validate",
                "python scripts\\artifact_index.py validate",
                "python scripts\\concurrent_lane_manager.py --validate",
            ],
            "deliverable": "A compact JSON QA packet confirming whether WF72 A2 remains read-only/support-only and naming any blocker before consumer promotion or Python retirement.",
        },
        {
            "workflow_id": "WF78",
            "workstream_id": "tier1-quote-readiness-qa",
            "title": "WF78 Tier 1 quote-readiness QA lane",
            "reason": "Fast independent quote-readiness check: verify Tier A/capital-review symbols are covered by daily market-data proof without preparing orders.",
            "read_first": [
                "tmp/market-execution-readiness-cron-hardening.json",
                "tmp/intraday-alerts/quote-snapshot-proof.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/wf78-capital-review-queue.json",
            ],
            "allowed_writes": ["tmp/parallel-lanes/wf78-tier1-quote-readiness-qa.json"],
            "acceptance_commands": [
                "python scripts\\market_execution_readiness_cron_hardening.py --validate",
                "python scripts\\concurrent_lane_manager.py --validate",
            ],
            "deliverable": "A compact JSON QA packet listing required Tier 1 symbols, observed quote symbols, missing/stale rows, and boundary status.",
        },
    ]


def pm_context_jobs(pm_queue: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = []
    for job in as_list(pm_queue.get("jobs")):
        job_dict = as_dict(job)
        if job_dict.get("status") not in {"ready_for_main_or_helper", "ready"}:
            continue
        jobs.append(
            {
                "job_id": job_dict.get("job_id"),
                "rank": job_dict.get("rank"),
                "title": job_dict.get("title"),
                "collision_group": job_dict.get("collision_group"),
                "target_file_count": len(as_list(job_dict.get("target_files"))),
                "proof_command_count": len(as_list(job_dict.get("proof_commands"))),
            }
        )
    return sorted(jobs, key=lambda row: int(row.get("rank") or 999))


def score_template(
    template: dict[str, Any],
    routes: list[dict[str, Any]],
    write_owners: dict[str, list[str]],
    completed_lanes: set[str],
) -> dict[str, Any]:
    workflow_id = str(template.get("workflow_id") or "").upper()
    workstream_id = str(template.get("workstream_id") or "")
    lane_id = f"{workflow_id}::{workstream_id}"
    route = workflow_route(routes, workflow_id)
    allowed_writes = [normalize_path(str(path)) for path in as_list(template.get("allowed_writes"))]
    collisions = {path: write_owners[path] for path in allowed_writes if path in write_owners}
    forbidden = [{"path": path, "pattern": forbidden_write(path)} for path in allowed_writes if forbidden_write(path)]
    missing_read_first = [path for path in as_list(template.get("read_first")) if not (ROOT / normalize_path(str(path))).exists()]
    route_safe = route.get("safe_for_helper_lane") is True
    route_owner_gated = route.get("owner_action_required") is True
    already_completed = lane_id in completed_lanes
    score = 100
    if not route_safe:
        score -= 100
    if route_owner_gated:
        score -= 5
    if already_completed:
        score -= 100
    score -= 50 * len(collisions)
    score -= 50 * len(forbidden)
    score -= 3 * len(missing_read_first)
    score -= max(0, len(allowed_writes) - 1) * 5
    return {
        **template,
        "score": score,
        "route_found": bool(route),
        "route_safe_for_helper_lane": route_safe,
        "route_owner_action_required": route_owner_gated,
        "route_current_state": route.get("current_state"),
        "route_next_action": route.get("next_action"),
        "collisions": collisions,
        "forbidden_writes": forbidden,
        "missing_read_first": missing_read_first,
        "already_completed": already_completed,
        "eligible": score > 0 and not collisions and not forbidden and route_safe and not already_completed,
    }


def make_task(candidate: dict[str, Any]) -> str:
    read_first = "\n".join(f"- {path}" for path in as_list(candidate.get("read_first")))
    allowed = "\n".join(f"- {path}" for path in as_list(candidate.get("allowed_writes")))
    commands = "\n".join(f"- {cmd}" for cmd in as_list(candidate.get("acceptance_commands")))
    return (
        "[Subagent Task]\n"
        f"Lane: {candidate.get('title')}\n"
        "Work in C:\\Users\\Veritas\\.openclaw\\workspace.\n\n"
        f"Objective: {candidate.get('deliverable')}\n\n"
        "Read first:\n"
        f"{read_first}\n\n"
        "Allowed writes only:\n"
        f"{allowed}\n\n"
        "Acceptance commands:\n"
        f"{commands}\n\n"
        "Stop lines: no canon/portfolio/ticker-card/SQL-canon mutation, no customer/public output, no cron/config/auth/runtime mutation, no capital deployment, no trade/order execution, no paper/live/brokerage/account action, no money movement, no owner approval inference. Return a concise summary and the proof artifact path."
    )


def build_report(prefer_workflow: str | None = None) -> dict[str, Any]:
    workflow_index = as_dict(load(WORKFLOW_INDEX))
    register = as_dict(load(LANE_REGISTER))
    pm_queue = pm_implementation_job_queue()
    wf78_event_queue = as_dict(load(WF78_EVENT_QUEUE))
    hardening = as_dict(load(AUTOMATION_HARDENING))

    routes = [as_dict(route) for route in as_list(workflow_index.get("routes"))]
    write_owners = active_lane_writes(register)
    completed_lanes = completed_lane_ids(register)
    templates = base_templates()
    if prefer_workflow:
        wanted = prefer_workflow.upper()
        templates = [template for template in templates if str(template.get("workflow_id") or "").upper() == wanted] or templates
    scored = [score_template(template, routes, write_owners, completed_lanes) for template in templates]
    scored.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("workflow_id")), str(row.get("workstream_id"))))
    eligible = [row for row in scored if row.get("eligible")]
    top = eligible[0] if eligible else (scored[0] if scored else {})
    owner = f"helper-{str(top.get('workflow_id') or 'wf').lower()}-{str(top.get('workstream_id') or 'lane').replace('_', '-').replace(' ', '-')}"
    lease_command = ""
    spawn_args: dict[str, Any] = {}
    if top and top.get("eligible"):
        allowed_flags = " ".join(f"--allowed-write {path}" for path in as_list(top.get("allowed_writes")))
        lease_command = (
            f"python scripts\\concurrent_lane_manager.py --lease {top.get('workflow_id')} "
            f"--workstream {top.get('workstream_id')} --owner {owner} {allowed_flags} --write --validate"
        )
        spawn_args = {
            "runtime": "subagent",
            "mode": "run",
            "context": "isolated",
            "lightContext": True,
            "cwd": str(ROOT),
            "taskName": f"{str(top.get('workflow_id')).lower()}-{str(top.get('workstream_id')).lower()}",
            "label": str(top.get("title") or "parallel helper lane"),
            "task": make_task(top),
        }
    next_safe_action = (
        "Run lease_command, then call sessions_spawn with spawn_args. Main session must verify output and complete the lease."
        if top.get("eligible")
        else "No eligible new helper lane is available; do not re-lease a completed or ineligible lane. Main session should continue ready PM work inline or refresh candidates after state changes."
    )

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})

    check("workflow_index_present", bool(routes), rel(WORKFLOW_INDEX))
    check("lane_register_validation_ok", as_dict(register.get("validation")).get("status") == "ok", as_dict(register.get("validation")))
    check("top_candidate_eligible", bool(top.get("eligible")), top, "critical" if top.get("forbidden_writes") or top.get("collisions") else "warning")
    check("top_candidate_one_output", len(as_list(top.get("allowed_writes"))) == 1, top.get("allowed_writes"))
    check("top_candidate_no_collisions", not as_dict(top.get("collisions")), top.get("collisions"))
    check("top_candidate_no_forbidden_writes", not as_list(top.get("forbidden_writes")), top.get("forbidden_writes"))
    for flag in REQUIRED_TRUE_FLAGS:
        check(f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        check(f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    critical = [item for item in checks if item["severity"] == "critical" and item["ok"] is not True]
    warnings = [item for item in checks if item["severity"] == "warning" and item["ok"] is not True]
    complete_command_template = (
        f"python scripts\\concurrent_lane_manager.py --complete {top.get('workflow_id')} "
        f"--workstream {top.get('workstream_id')} --proof {as_list(top.get('allowed_writes'))[0] if as_list(top.get('allowed_writes')) else '<proof>'} --write --validate"
        if top else ""
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if critical else "warning" if warnings else "ok",
        "purpose": "Pick the fastest safe helper lane for isolated parallel session work without write collisions or authority drift.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "workflow_routing_index": rel(WORKFLOW_INDEX),
            "concurrent_lane_register": rel(LANE_REGISTER),
            "pm_control_packet": "tmp/pm-control-packet.json",
            "wf78_event_triggered_rerouting": rel(WF78_EVENT_QUEUE),
            "automation_stack_hardening_pass": rel(AUTOMATION_HARDENING),
        },
        "summary": {
            "candidate_count": len(scored),
            "eligible_candidate_count": len(eligible),
            "active_lane_count": as_dict(register.get("summary")).get("active_lane_count", 0),
            "completed_lane_count": len(completed_lanes),
            "pm_ready_job_count": len(pm_context_jobs(pm_queue)),
            "wf78_event_action_count": as_dict(wf78_event_queue.get("summary")).get("action_count"),
            "automation_hardening_status": hardening.get("status"),
            "top_workflow": top.get("workflow_id"),
            "top_workstream": top.get("workstream_id"),
            "top_title": top.get("title"),
            "top_score": top.get("score"),
            "next_safe_action": next_safe_action,
        },
        "lease_command": lease_command,
        "spawn_args": spawn_args,
        "complete_command_template": complete_command_template,
        "recommendation": {
            "top_candidate": top,
            "lease_command": lease_command,
            "spawn_args": spawn_args,
            "complete_command_template": complete_command_template,
        },
        "ranked_candidates": scored,
        "pm_ready_jobs_context": pm_context_jobs(pm_queue)[:5],
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [item["name"] for item in critical],
            "warnings": [item["name"] for item in warnings],
            "checks": checks,
        },
        "stop_lines": [
            "This script does not spawn sessions; main session must call sessions_spawn.",
            "Lease before spawn; complete or cancel the lease after integration.",
            "Parallel lanes should write one distinct tmp proof artifact by default.",
            "No capital, execution, account, cron/config/auth/runtime, canon/portfolio, customer/public, SQL-canon, or owner-approval authority.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend a safe parallel helper lane.")
    parser.add_argument("--workflow", help="Prefer candidates for this workflow, e.g. WF78 or WF72.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_report(args.workflow)
    out = Path(args.out)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "summary": payload.get("summary"),
        "lease_command": as_dict(payload.get("recommendation")).get("lease_command"),
        "validation": {k: v for k, v in as_dict(payload.get("validation")).items() if k != "checks"},
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
