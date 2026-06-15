#!/usr/bin/env python3
"""Fast workflow lookup and capsule writer.

This is the low-overhead route front door. It reads existing route/PM proof,
applies workflow-control overrides, and answers state/next/blocker/helper
questions without broad scans or full closeout.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from lib.pm_control_reader import pm_implementation_job_queue, pm_next_actions
from lib.workflow_control import CAPSULE_DIR, apply_route_override, find_override, load_registry, validation_errors
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ROUTE_INDEX = TMP / "workflow-routing-index.json"

SCHEMA = "veritas.workflow_capsule.v1"

PM_ROUTE_ALIASES = {
    "WF79-SMB": "smb_workflow_clarity",
    "WF75": "wf75_service_state",
    "WF-RETAIL-ROUTING": "retail_truth_routing",
    "WF73": "parallel_lane_orchestration",
    "WF78": "wf78_scaleout",
    "WF84": "finance_os_data_model",
    "WF85": "trade_grade_decision_os",
    "WF72": "sql_index",
}


def read_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def capsule_name(workflow_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", workflow_id.strip())
    return f"{slug}.json"


def routes() -> list[dict[str, Any]]:
    payload = read_json(ROUTE_INDEX)
    items = payload.get("routes", [])
    return items if isinstance(items, list) else []


def pm_actions() -> list[dict[str, Any]]:
    payload = pm_next_actions()
    items = payload.get("next_actions", [])
    return items if isinstance(items, list) else []


def pm_jobs() -> list[dict[str, Any]]:
    payload = pm_implementation_job_queue()
    items = payload.get("jobs", [])
    return items if isinstance(items, list) else []


def find_route(selector: str, all_routes: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = normalize(selector)
    for route in all_routes:
        if normalize(route.get("workflow_id")) == wanted:
            return route
    for route in all_routes:
        if wanted in normalize(route.get("workflow_id")) or wanted in normalize(route.get("display_name")):
            return route
    return None


def matching_pm_action(route: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    workflow_id = str(route.get("workflow_id") or "")
    lane_id = PM_ROUTE_ALIASES.get(workflow_id)
    candidates = {normalize(lane_id), normalize(workflow_id)}
    for action in actions:
        if normalize(action.get("lane_id")) in candidates:
            return action
    return None


def matching_pm_job(action: dict[str, Any] | None, jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not action:
        return None
    action_id = action.get("action_id")
    lane_id = action.get("lane_id")
    for job in jobs:
        if job.get("source_action_id") == action_id:
            return job
    for job in jobs:
        if job.get("lane_id") == lane_id:
            return job
    return None


def build_capsule(route: dict[str, Any], registry: dict[str, Any], actions: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    route = apply_route_override(route, registry)
    action = matching_pm_action(route, actions)
    override = find_override(route.get("workflow_id", ""), workflow_name=route.get("display_name"), registry=registry)
    job = matching_pm_job(action, jobs)
    effective_status = (
        "on_hold"
        if override and override.get("status") == "on_hold"
        else route.get("effective_status_override")
        or (action or {}).get("lane_status")
        or "route_only"
    )
    next_action = (override or {}).get("next_action") or route.get("next_action") or (action or {}).get("description")
    helper_safe = bool(route.get("safe_for_helper_lane")) and not (override and override.get("status") == "on_hold")
    return {
        "schema": SCHEMA,
        "workflow_id": route.get("workflow_id"),
        "display_name": route.get("display_name"),
        "tier": route.get("tier"),
        "effective_status": effective_status,
        "next_action": next_action,
        "helper_safe": helper_safe,
        "owner_action_required": route.get("owner_action_required"),
        "authority_boundary": route.get("authority_boundary"),
        "blockers": route.get("blockers", []),
        "stop_lines": route.get("stop_lines", []),
        "continuity_note": route.get("continuity_note"),
        "primary_route_artifact": route.get("primary_route_artifact"),
        "secondary_artifacts": route.get("secondary_artifacts", []),
        "validator_commands": route.get("validator_commands", []),
        "default_resume_command": route.get("default_resume_command"),
        "control_override": override,
        "pm_action": action,
        "pm_job": {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "validation_budget": job.get("validation_budget"),
            "closeout_mode": job.get("closeout_mode"),
            "collision_group": job.get("collision_group"),
        } if job else None,
        "sources": {
            "route_index": str(ROUTE_INDEX.relative_to(ROOT)),
            "pm_control_packet": "tmp/pm-control-packet.json",
        },
    }


def validate_capsule(capsule: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("workflow_id", "display_name", "tier", "effective_status", "next_action"):
        if not capsule.get(key):
            errors.append(f"missing_{key}")
    if capsule.get("control_override") and capsule.get("helper_safe") is not False:
        errors.append("held_capsule_helper_safe_not_false")
    boundary = str(capsule.get("authority_boundary") or "").lower()
    if "review" not in boundary and not capsule.get("stop_lines"):
        errors.append("missing_review_boundary_or_stop_lines")
    return errors


def write_capsules(selected: list[dict[str, Any]], registry: dict[str, Any], actions: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    CAPSULE_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for route in selected:
        capsule = build_capsule(route, registry, actions, jobs)
        path = CAPSULE_DIR / capsule_name(str(route.get("workflow_id")))
        atomic_write_json(path, capsule)
        written.append({"workflow_id": route.get("workflow_id"), "path": str(path.relative_to(ROOT)), "errors": validate_capsule(capsule)})
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast workflow router.")
    parser.add_argument("workflow", nargs="?", help="Workflow id/name, e.g. WF78 or WF79-SMB.")
    parser.add_argument("--answer", choices=["summary", "next", "blockers", "helper", "all"], default="summary")
    parser.add_argument("--write-capsules", action="store_true", help="Write capsules for selected workflow or all workflows.")
    parser.add_argument("--all", action="store_true", help="Select all workflows for capsule writing/listing.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--list", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = load_registry()
    all_routes = routes()
    actions = pm_actions()
    jobs = pm_jobs()

    if args.list:
        payload = [{"workflow_id": item.get("workflow_id"), "display_name": item.get("display_name"), "tier": item.get("tier")} for item in all_routes]
        print(json.dumps(payload, indent=2))
        return 0

    selected = all_routes if args.all else []
    if args.workflow and not args.all:
        route = find_route(args.workflow, all_routes)
        if route is None:
            print(json.dumps({"status": "error", "error": "workflow_not_found", "workflow": args.workflow}, indent=2))
            return 1
        selected = [route]
    elif not selected:
        print(json.dumps({"status": "error", "error": "missing_workflow_or_all"}, indent=2))
        return 1

    capsules = [build_capsule(route, registry, actions, jobs) for route in selected]
    written = write_capsules(selected, registry, actions, jobs) if args.write_capsules else []
    errors = validation_errors(registry)
    if args.validate:
        for capsule in capsules:
            errors.extend(f"{capsule.get('workflow_id')}:{err}" for err in validate_capsule(capsule))
        for item in written:
            errors.extend(f"{item['workflow_id']}:{err}" for err in item.get("errors", []))

    capsule = capsules[0] if len(capsules) == 1 else None
    if args.answer == "next" and capsule:
        answer: Any = {"workflow_id": capsule["workflow_id"], "effective_status": capsule["effective_status"], "next_action": capsule["next_action"]}
    elif args.answer == "blockers" and capsule:
        answer = {"workflow_id": capsule["workflow_id"], "blockers": capsule["blockers"], "control_override": capsule["control_override"]}
    elif args.answer == "helper" and capsule:
        answer = {"workflow_id": capsule["workflow_id"], "helper_safe": capsule["helper_safe"], "pm_job": capsule["pm_job"]}
    elif args.answer == "all":
        answer = capsules
    else:
        answer = [{
            "workflow_id": item["workflow_id"],
            "display_name": item["display_name"],
            "effective_status": item["effective_status"],
            "helper_safe": item["helper_safe"],
            "next_action": item["next_action"],
        } for item in capsules]
    print(json.dumps({
        "status": "ok" if not errors else "error",
        "answer": answer,
        "written": written,
        "validation": {"status": "ok" if not errors else "error", "errors": errors},
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
