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

import project_implementation_router as implementation_router
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
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


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


def completed_lane_states(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for lane in as_list(register.get("lanes")):
        lane_dict = as_dict(lane)
        if lane_dict.get("status") != "complete":
            continue
        workflow_id = str(lane_dict.get("workflow_id") or "").upper()
        workstream_id = str(lane_dict.get("workstream_id") or "")
        if workflow_id and workstream_id:
            completed[f"{workflow_id}::{workstream_id}"] = lane_dict
    return completed


def path_mtime(path: str) -> float | None:
    resolved = ROOT / normalize_path(path)
    try:
        return resolved.stat().st_mtime
    except OSError:
        return None


def completion_freshness(candidate: dict[str, Any], lane: dict[str, Any] | None) -> dict[str, Any]:
    if not lane:
        return {"state": "not_completed", "stale_inputs": [], "missing_proofs": []}
    proofs = [normalize_path(str(path)) for path in as_list(lane.get("proof_artifacts")) if str(path).strip()]
    missing_proofs = [path for path in proofs if not (ROOT / path).exists()]
    proof_mtimes = [mtime for mtime in (path_mtime(path) for path in proofs) if mtime is not None]
    if not proofs or missing_proofs or not proof_mtimes:
        return {"state": "stale_missing_proof", "stale_inputs": [], "missing_proofs": missing_proofs or proofs}
    oldest_proof_mtime = min(proof_mtimes)
    stale_inputs = []
    for source in as_list(candidate.get("read_first")):
        source_path = normalize_path(str(source))
        source_mtime = path_mtime(source_path)
        if source_mtime is not None and source_mtime > oldest_proof_mtime:
            stale_inputs.append(source_path)
    if stale_inputs:
        return {"state": "stale_inputs", "stale_inputs": stale_inputs, "missing_proofs": []}
    return {"state": "fresh", "stale_inputs": [], "missing_proofs": []}


def forbidden_write(path: str) -> str | None:
    normalized = normalize_path(path)
    parts = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(char in normalized for char in "*?[]")
        or ".." in parts
        or "." in parts
        or normalized.endswith("/")
    ):
        return "workspace_relative_exact_path_required"
    try:
        (ROOT / normalized).resolve().relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return "workspace_path_escape"
    for pattern in FORBIDDEN_WRITE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return pattern
    return None


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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
                "06. Playbooks/Project Continuity/Workflow 72 - Guarded Finance SQL Canon.md",
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
            "workstream_id": "ticker-card-freshness-owner-qa",
            "title": "WF78 ticker-card freshness owner QA lane",
            "reason": "Safe parallel proof lane after owner-runner integration: independently verify that daily ticker-card freshness is self-healing and fail-closed only on true production blockers.",
            "read_first": [
                "tmp/ticker-card-freshness-owner-runner.json",
                "tmp/finance-ticker-card-refresh-gate.json",
                "tmp/finance-data-coverage-current.json",
                "tmp/position-sizing-readiness-current.json",
            ],
            "allowed_writes": ["tmp/parallel-lanes/wf78-ticker-card-freshness-owner-qa.json"],
            "acceptance_commands": [
                "python scripts\\ticker_card_freshness_owner_runner.py --skip-provider-refresh --validate",
                "python scripts\\pm_control_packet.py --write --validate",
                "python scripts\\concurrent_lane_manager.py --validate",
            ],
            "deliverable": "A compact JSON QA packet confirming the owner runner status, true production blocker count, production repair debt classification, and unchanged finance authority boundary.",
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


def pm_job_workflow_id(job: dict[str, Any]) -> str:
    lane_id = str(job.get("lane_id") or "")
    implementation_class = str(job.get("implementation_class") or "")
    if lane_id in {"trade_grade_decision_os"} or implementation_class == "trade_grade_decision_os":
        return "WF85"
    if lane_id in {"finance_os_data_model", "finance_engine"} or implementation_class == "canonical_finance_data_plane":
        return "WF84"
    if lane_id.startswith("wf78") or implementation_class.startswith("wf78") or lane_id in {"ticker_card_refresh", "tier_promotion_review"}:
        return "WF78"
    if lane_id.startswith("wf75") or lane_id in {"smb_workflow_clarity", "retail_truth_routing"}:
        return "WF75"
    if lane_id == "parallel_lane_orchestration":
        return "WF73"
    return "PM"


def pm_job_templates(pm_queue: dict[str, Any]) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for job in as_list(pm_queue.get("jobs")):
        job_dict = as_dict(job)
        capabilities = as_dict(job_dict.get("automation_capabilities"))
        if job_dict.get("status") != "ready_for_main_or_helper":
            continue
        department = str(job_dict.get("department") or "")
        if capabilities.get("owner_gate_required") is True:
            continue
        if capabilities.get("helper_lane_allowed") is not True:
            continue
        job_id = str(job_dict.get("job_id") or "")
        if not job_id:
            continue
        target_files = [normalize_path(str(path)) for path in as_list(job_dict.get("target_files")) if str(path).strip()]
        proof_artifact = f"tmp/parallel-lanes/{job_id}.json"
        allowed_writes = [proof_artifact, *target_files]
        read_first = target_files[:8] or [normalize_path(str(path)) for path in as_list(job_dict.get("owner_surface"))]
        workflow_id = pm_job_workflow_id(job_dict)
        templates.append({
            "workflow_id": workflow_id,
            "workstream_id": job_id,
            "title": str(job_dict.get("title") or job_id),
            "reason": "PM implementation queue job is ready for main/helper pickup and has explicit capability flags, target files, proof commands, and stop lines.",
            "read_first": read_first,
            "allowed_writes": allowed_writes,
            "acceptance_commands": [str(command) for command in as_list(job_dict.get("proof_commands"))],
            "deliverable": str(job_dict.get("objective") or job_dict.get("title") or "Complete bounded PM implementation job."),
            "from_pm_job": True,
            "pm_job_id": job_id,
            "department": department,
            "department_owner": job_dict.get("department_owner"),
            "owner_workflow": job_dict.get("owner_workflow"),
            "accountable_integrator": job_dict.get("accountable_integrator"),
            "allowed_execution_mode": job_dict.get("allowed_execution_mode"),
            "implementation_class": job_dict.get("implementation_class"),
            "collision_group": job_dict.get("collision_group"),
            "validation_budget": job_dict.get("validation_budget"),
            "closeout_mode": job_dict.get("closeout_mode"),
            "helper_packet": job_dict.get("helper_packet"),
            "stop_lines": job_dict.get("stop_lines"),
            "automation_capabilities": capabilities,
            "reopen_on_stale_inputs": True,
        })
    return templates


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
                "department": job_dict.get("department"),
                "department_owner": job_dict.get("department_owner"),
                "accountable_integrator": job_dict.get("accountable_integrator"),
                "allowed_execution_mode": job_dict.get("allowed_execution_mode"),
                "target_file_count": len(as_list(job_dict.get("target_files"))),
                "proof_command_count": len(as_list(job_dict.get("proof_commands"))),
            }
        )
    return sorted(jobs, key=lambda row: int(row.get("rank") or 999))


def score_template(
    template: dict[str, Any],
    routes: list[dict[str, Any]],
    write_owners: dict[str, list[str]],
    completed_lanes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    workflow_id = str(template.get("workflow_id") or "").upper()
    workstream_id = str(template.get("workstream_id") or "")
    lane_id = f"{workflow_id}::{workstream_id}"
    route = workflow_route(routes, workflow_id)
    allowed_writes = [normalize_path(str(path)) for path in as_list(template.get("allowed_writes"))]
    collisions = {path: write_owners[path] for path in allowed_writes if path in write_owners}
    forbidden = [{"path": path, "pattern": forbidden_write(path)} for path in allowed_writes if forbidden_write(path)]
    missing_read_first = [path for path in as_list(template.get("read_first")) if not (ROOT / normalize_path(str(path))).exists()]
    from_pm_job = template.get("from_pm_job") is True
    department = str(template.get("department") or "")
    route_safe = route.get("safe_for_helper_lane") is True or (
        from_pm_job and as_dict(template.get("automation_capabilities")).get("helper_lane_allowed") is True
    )
    route_owner_gated = route.get("owner_action_required") is True
    completion = completion_freshness(template, completed_lanes.get(lane_id))
    completion_state = str(completion.get("state") or "")
    reopen_on_stale_inputs = template.get("reopen_on_stale_inputs") is True
    already_completed = completion_state in {"fresh", "stale_inputs"} and not reopen_on_stale_inputs
    completion_reopen_reason = (
        "proof_missing_or_invalid"
        if completion_state == "stale_missing_proof"
        else "template_allows_stale_input_reopen"
        if completion_state == "stale_inputs" and reopen_on_stale_inputs
        else "completed_lane_context_changed_monitor_only"
        if completion_state == "stale_inputs"
        else completion_state
    )
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
    if from_pm_job:
        score += 15
    if from_pm_job and not department:
        score -= 100
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
        "department_missing": from_pm_job and not department,
        "already_completed": already_completed,
        "completion_state": completion_state,
        "completion_reopen_reason": completion_reopen_reason,
        "stale_completion_inputs": completion.get("stale_inputs", []),
        "missing_completion_proofs": completion.get("missing_proofs", []),
        # A lane whose read-first inputs are absent has nothing to review; never dispatch it.
        "eligible": score > 0 and not collisions and not forbidden and route_safe and not already_completed and not (from_pm_job and not department) and not missing_read_first,
    }


def lane_contracts(eligible: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_departments: set[str] = set()
    used_collisions: set[str] = set()
    for row in eligible:
        department = str(row.get("department") or "main_session_veritas")
        collision_group = str(row.get("collision_group") or row.get("workstream_id") or "")
        if department in used_departments or collision_group in used_collisions:
            continue
        used_departments.add(department)
        if collision_group:
            used_collisions.add(collision_group)
        selected.append({
            "workflow_id": row.get("workflow_id"),
            "workstream_id": row.get("workstream_id"),
            "title": row.get("title"),
            "pm_job_id": row.get("pm_job_id"),
            "department": department,
            "department_owner": row.get("department_owner"),
            "owner_workflow": row.get("owner_workflow"),
            "accountable_integrator": row.get("accountable_integrator") or "main_session_veritas",
            "allowed_execution_mode": row.get("allowed_execution_mode"),
            "collision_group": collision_group,
            "allowed_writes": row.get("allowed_writes"),
            "acceptance_commands": row.get("acceptance_commands"),
            "score": row.get("score"),
        })
    return selected


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
        "Stop lines: no canon/portfolio/ticker-card/SQL-canon mutation unless the PM job explicitly allows a bounded local artifact patch, no customer/public output, no cron/config/auth/runtime mutation, no capital deployment, no trade/order execution, no paper/live/brokerage/account action, no money movement, no owner approval inference. Return a concise summary and the proof artifact path."
    )


def recommendation_dispatch_contract(
    candidate: dict[str, Any],
    *,
    persistent_transport_proof: str | None = None,
    persistent_lane_mode: str = "patch_draft",
) -> dict[str, Any]:
    """Select and format one exact persistent route without spawning it."""
    description = " ".join(
        str(candidate.get(field) or "").strip()
        for field in ("title", "reason", "deliverable", "workflow_id")
        if str(candidate.get(field) or "").strip()
    )
    allowed_writes = [str(path) for path in as_list(candidate.get("allowed_writes")) if str(path).strip()]
    invalid_writes = [path for path in allowed_writes if forbidden_write(path)]
    if invalid_writes:
        return {
            "schema": "veritas.sessions_spawn_dispatch_contract.v1",
            "status": "blocked",
            "dispatch_executes_agent": False,
            "implicit_model_fallback_allowed": False,
            "same_inference_model_switching": False,
            "agent_dispatch": {},
            "model_route": {},
            "blockers": [f"invalid_or_forbidden_write_path:{path}" for path in invalid_writes],
            "spawn_args": {},
        }
    if allowed_writes and persistent_lane_mode != "scoped_worktree_implementation":
        return {
            "schema": "veritas.sessions_spawn_dispatch_contract.v1",
            "status": "blocked",
            "dispatch_executes_agent": False,
            "implicit_model_fallback_allowed": False,
            "same_inference_model_switching": False,
            "agent_dispatch": {},
            "model_route": {},
            "blockers": ["scoped_writeback_transport_proof_required"],
            "spawn_args": {},
        }
    dispatch = implementation_router.select_isolated_agent_dispatch(
        description,
        leased_paths=allowed_writes,
        write_mode="distinct_output" if allowed_writes else "read_only",
    )
    agent_id = str(dispatch.get("primary_agent_id") or "")
    if dispatch.get("decision") != "route" or not agent_id:
        return {
            "schema": "veritas.sessions_spawn_dispatch_contract.v1",
            "status": "blocked",
            "dispatch_executes_agent": False,
            "implicit_model_fallback_allowed": False,
            "same_inference_model_switching": False,
            "agent_dispatch": dispatch,
            "model_route": {},
            "blockers": [str(dispatch.get("fallback_reason") or "no_specialist_route")],
            "spawn_args": {},
        }

    normalized = implementation_router.normalize_dispatch_text(description)
    task_shape = (
        "qa" if "qa" in normalized or "verify" in normalized
        else "continuity" if "continuity" in normalized or "documentation" in normalized
        else "implementation" if any(term in normalized for term in ("implement", "patch", "code"))
        else "audit"
    )
    write_mode = "distinct_output" if allowed_writes else "read_only"
    write_scope = implementation_router.infer_write_scope(allowed_writes, write_mode)
    authority_class = implementation_router.infer_authority_class(description)
    execution_route = implementation_router.select_execution_route(
        description,
        task_shape=task_shape,
        authority_class=authority_class,
        write_scope=write_scope,
        write_mode=write_mode,
        helper_fit="one_bounded_helper",
        leased_paths=allowed_writes,
        agent_dispatch=dispatch,
        model_free_commands=[],
        model_free_proofs=[],
        allow_codex_native=False,
        native_dispatch_proof=None,
        main_only_reason=None,
        main_sol_use_case=None,
        main_sol_reason=None,
        persistent_transport_ready=bool(persistent_transport_proof),
        persistent_transport_proof=persistent_transport_proof,
        persistent_lane_mode=persistent_lane_mode,
        validation_budget="narrow",
        measurement_cohort_binding=None,
    )
    model_route = implementation_router.default_model_route(execution_route)
    contract = implementation_router.sessions_spawn_dispatch_contract(
        model_route,
        agent_id=agent_id,
        task_name=f"{str(candidate.get('workflow_id') or 'wf').lower()}-{str(candidate.get('workstream_id') or 'lane').lower()}",
        label=str(candidate.get("title") or "parallel helper lane"),
        task=make_task(candidate),
        cwd=ROOT,
    )
    contract["agent_dispatch"] = dispatch
    contract["model_route"] = model_route
    return contract


def build_report(
    prefer_workflow: str | None = None,
    *,
    persistent_transport_proof: str | None = None,
    persistent_lane_mode: str = "patch_draft",
) -> dict[str, Any]:
    workflow_index = as_dict(load(WORKFLOW_INDEX))
    register = as_dict(load(LANE_REGISTER))
    pm_queue = pm_implementation_job_queue()
    wf78_event_queue = as_dict(load(WF78_EVENT_QUEUE))
    hardening = as_dict(load(AUTOMATION_HARDENING))

    routes = [as_dict(route) for route in as_list(workflow_index.get("routes"))]
    write_owners = active_lane_writes(register)
    completed_lanes = completed_lane_states(register)
    templates = pm_job_templates(pm_queue) + base_templates()
    if prefer_workflow:
        wanted = prefer_workflow.upper()
        templates = [template for template in templates if str(template.get("workflow_id") or "").upper() == wanted] or templates
    scored = [score_template(template, routes, write_owners, completed_lanes) for template in templates]
    scored.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("workflow_id")), str(row.get("workstream_id"))))
    eligible = [row for row in scored if row.get("eligible")]
    contracts = lane_contracts(eligible)
    all_candidates_complete = bool(scored) and all(row.get("already_completed") for row in scored)
    top = eligible[0] if eligible else (scored[0] if scored else {})
    owner = f"helper-{str(top.get('workflow_id') or 'wf').lower()}-{str(top.get('workstream_id') or 'lane').replace('_', '-').replace(' ', '-')}"
    lease_command = ""
    proposed_lease_command = ""
    spawn_args: dict[str, Any] = {}
    dispatch_contract: dict[str, Any] = {
        "schema": "veritas.sessions_spawn_dispatch_contract.v1",
        "status": "not_applicable",
        "spawn_args": {},
        "blockers": [],
    }
    if top and top.get("eligible"):
        allowed_flags = " ".join(f"--allowed-write {ps_quote(str(path))}" for path in as_list(top.get("allowed_writes")))
        read_flags = " ".join(f"--read-first {ps_quote(str(path))}" for path in as_list(top.get("read_first")))
        acceptance_flags = " ".join(
            f"--acceptance-command {ps_quote(str(command))}" for command in as_list(top.get("acceptance_commands"))
        )
        reopen_flag = "--reopen-complete " if str(top.get("completion_state") or "") not in {"", "not_completed"} else ""
        proposed_lease_command = (
            f"python scripts\\concurrent_lane_manager.py --lease {top.get('workflow_id')} "
            f"--workstream {top.get('workstream_id')} --owner {owner} {allowed_flags} "
            f"{read_flags} {acceptance_flags} --replace-contract {reopen_flag}--write --validate"
        )
        dispatch_contract = recommendation_dispatch_contract(
            top,
            persistent_transport_proof=persistent_transport_proof,
            persistent_lane_mode=persistent_lane_mode,
        )
        if dispatch_contract.get("status") == "ready":
            lease_command = proposed_lease_command
            spawn_args = as_dict(dispatch_contract.get("spawn_args"))
    next_safe_action = (
        "Run lease_command, then call sessions_spawn with spawn_args. Main session must verify output and complete the lease."
        if top.get("eligible") and dispatch_contract.get("status") == "ready"
        else (
            "Dispatch is blocked. Supply a fresh agent-matched persistent transport proof; do not lease or spawn using runtime defaults."
            if top.get("eligible")
            else "No eligible new helper lane is available; do not re-lease a completed or ineligible lane. Main session should continue ready PM work inline or refresh candidates after state changes."
        )
    )

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})

    check("workflow_index_present", bool(routes), rel(WORKFLOW_INDEX))
    check("lane_register_validation_ok", as_dict(register.get("validation")).get("status") == "ok", as_dict(register.get("validation")))
    check(
        "top_candidate_eligible_or_all_complete",
        bool(top.get("eligible")) or all_candidates_complete,
        top,
        "critical" if top.get("forbidden_writes") or top.get("collisions") else "warning",
    )
    check(
        "top_candidate_one_output_or_pm_explicit_targets",
        len(as_list(top.get("allowed_writes"))) == 1 or top.get("from_pm_job") is True,
        top.get("allowed_writes"),
    )
    check("top_candidate_no_collisions", not as_dict(top.get("collisions")), top.get("collisions"))
    check("top_candidate_no_forbidden_writes", not as_list(top.get("forbidden_writes")), top.get("forbidden_writes"))
    if top.get("eligible"):
        check(
            "top_candidate_dispatch_ready",
            dispatch_contract.get("status") == "ready",
            dispatch_contract,
        )
        if dispatch_contract.get("status") == "ready":
            check(
                "spawn_args_pin_agent_model_and_thinking",
                all(key in spawn_args for key in ("agentId", "model", "thinking")),
                spawn_args,
            )
    contract_departments = [str(row.get("department") or "") for row in contracts]
    contract_collisions = [str(row.get("collision_group") or "") for row in contracts if row.get("collision_group")]
    check("lane_contracts_unique_departments", len(contract_departments) == len(set(contract_departments)), contracts)
    check("lane_contracts_unique_collision_groups", len(contract_collisions) == len(set(contract_collisions)), contracts)
    for contract in contracts:
        check(
            f"lane_contract_integrator:{contract.get('workstream_id')}",
            contract.get("accountable_integrator") == "main_session_veritas",
            contract,
        )
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
        "status": "blocked" if critical else "ok",
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
            "lane_contract_count": len(contracts),
            "eligible_department_count": len({str(row.get("department") or "unknown") for row in eligible}),
            "completed_candidate_count": len([row for row in scored if row.get("already_completed")]),
            "all_candidates_complete": all_candidates_complete,
            "active_lane_count": as_dict(register.get("summary")).get("active_lane_count", 0),
            "completed_lane_count": len(completed_lanes),
            "pm_ready_job_count": len(pm_context_jobs(pm_queue)),
            "pm_ready_department_counts": {
                department: len([row for row in pm_context_jobs(pm_queue) if row.get("department") == department])
                for department in sorted({str(row.get("department") or "unknown") for row in pm_context_jobs(pm_queue)})
            },
            "wf78_event_action_count": as_dict(wf78_event_queue.get("summary")).get("action_count"),
            "automation_hardening_status": hardening.get("status"),
            "top_workflow": top.get("workflow_id"),
            "top_workstream": top.get("workstream_id"),
            "top_title": top.get("title"),
            "top_score": top.get("score"),
            "next_safe_action": next_safe_action,
        },
        "lease_command": lease_command,
        "proposed_lease_command": proposed_lease_command,
        "spawn_args": spawn_args,
        "dispatch_contract": dispatch_contract,
        "complete_command_template": complete_command_template,
        "recommendation": {
            "top_candidate": top,
            "lease_command": lease_command,
            "proposed_lease_command": proposed_lease_command,
            "spawn_args": spawn_args,
            "dispatch_contract": dispatch_contract,
            "complete_command_template": complete_command_template,
        },
        "ranked_candidates": scored,
        "lane_contracts": contracts,
        "pm_ready_jobs_context": pm_context_jobs(pm_queue)[:5],
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [item["name"] for item in critical],
            "warnings": [item["name"] for item in warnings],
            "checks": checks,
        },
        "stop_lines": [
            "This script does not spawn sessions; main session must call sessions_spawn.",
            "No lease or spawn arguments are actionable until fresh transport proof makes dispatch_contract ready.",
            "Lease before spawn; complete or cancel the lease after integration.",
            "Parallel lanes should write one distinct tmp proof artifact by default.",
            "No capital, execution, account, cron/config/auth/runtime, canon/portfolio, customer/public, SQL-canon, or owner-approval authority.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend a safe parallel helper lane.")
    parser.add_argument("--workflow", help="Prefer candidates for this workflow, e.g. WF78 or WF72.")
    parser.add_argument(
        "--persistent-transport-proof",
        help="Fresh workspace-relative proof for the selected persistent agent; required before lease/spawn args become actionable.",
    )
    parser.add_argument(
        "--persistent-lane-mode",
        choices=sorted(implementation_router.PERSISTENT_LANE_MODES),
        default="patch_draft",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_report(
        args.workflow,
        persistent_transport_proof=args.persistent_transport_proof,
        persistent_lane_mode=args.persistent_lane_mode,
    )
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
