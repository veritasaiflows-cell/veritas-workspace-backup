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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.pm_control_reader import pm_implementation_job_queue, pm_next_actions
from lib.workflow_control import CAPSULE_DIR, find_override, load_registry, validation_errors
from market_data_utils import atomic_write_json, load_json_artifact

try:
    from lib.graphify_router import GraphifyRouter, GraphifyError
except Exception:
    GraphifyRouter = None  # type: ignore[misc,assignment]
    GraphifyError = Exception  # type: ignore[misc,assignment]

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ROUTE_INDEX = TMP / "workflow-routing-index.json"
ACTIVE_WORKFLOWS = ROOT / "06. Playbooks" / "Active Workflows.md"
CONTROL_OVERRIDES = ROOT / "state" / "workflow-control-overrides.json"

SCHEMA = "veritas.workflow_capsule.v1"

PM_ROUTE_ALIASES = {
    "WF79-SMB": "smb_workflow_clarity",
    "WF75": "wf75_service_state",
    "WF-RETAIL-ROUTING": "retail_truth_routing",
    "WF73": "parallel_lane_orchestration",
}


def read_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def selector_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize(value))


def route_selector_keys(route: dict[str, Any]) -> set[str]:
    workflow_id = str(route.get("workflow_id") or "")
    values: list[Any] = [workflow_id, route.get("display_name"), *(route.get("aliases") or [])]
    match = re.fullmatch(r"wf[-_ ]?(\d+)", workflow_id, flags=re.IGNORECASE)
    if match:
        number = match.group(1)
        values.extend([number, f"Workflow {number}"])
    return {selector_key(value) for value in values if selector_key(value)}


def capsule_name(workflow_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", workflow_id.strip())
    return f"{slug}.json"


def routes() -> list[dict[str, Any]]:
    payload = read_json(ROUTE_INDEX)
    items = payload.get("routes", [])
    return items if isinstance(items, list) else []


# LOOP-REPAIR-20260912 (consumer slice): targeted WF74/WF88 live-dependency
# invalidation plus claim_limits projection.
#
# Producer mirror (scripts/workflow_routing_index.py is read-only on this
# slice): WF74_LIVE_PROOFS, WF74_OTEL_PROOFS, and WF88_LIVE_PROOFS name the
# exact live evidence the computed WF74/WF88 blockers and claim_limits derive
# from, and each route carries a claim_limits list beside blockers. The index
# stores per-dependency mtime tokens only for the primary artifact and the
# continuity note, so a changed secondary ledger/docket/OTEL/retrieval
# artifact -- or elapsed producer-clock SLA with an untouched filesystem --
# can leave cached computed blockers/limits stale while the existing
# primary+continuity mtime check still passes. This consumer closes that gap
# without executing producer code and without widening the global
# source_freshness_snapshot: for WF74/WF88 routes only, a lookup is refused
# as routing_index_stale when a mirrored live dependency changed after the
# index was written (live mtime newer than the index file mtime) or when its
# current producer evidence is missing, unreadable, future-dated,
# un-timestamped, older than SLA, or reporting failure against a cached green
# answer. WF88 additionally covers the WF74 live set because
# compute_wf88_blockers() folds WF74 upstream state into WF88 blockers.
# Non-WF74/WF88 semantics are untouched.
#
# Limitations (no unsupported hashes claimed): the index carries no
# per-dependency content hash or consumed-mtime token, so "changed after the
# index" is a coarse fail-closed mtime comparison -- touching a file without
# changing it trips refusal, and a change followed by an index rebuild that
# did not re-run the producer is not detectable here (producer-side defect,
# out of consumer scope). Live failure status is not re-derived: it is already
# encoded in the cached computed blockers at build time, and any post-build
# flip rewrites the file and trips the mtime gate; only a live failure that
# contradicts a cached green answer is refused. If the producer adds a live
# source without updating this mirror, that source is unchecked until the
# mirror follows.
_LOOP_LIVE_SLA_FALLBACK_HOURS = 72.0
_LOOP_LIVE_FUTURE_SKEW_SECONDS = 3600.0
_LOOP_LIVE_FAIL_TOKENS = ("blocked", "failed", "fail_closed", "error", "critical")
_WF74_LIVE_DEPENDENCIES = (
    "tmp/wf74-improvement-opportunity-queue.json",
    "tmp/wf74-decision-docket.json",
    "tmp/wf74-autonomy-work-router.json",
    "tmp/improvement-ledger-current.json",
    "tmp/otel-ops-control.json",
    "tmp/otel-ops-window-summary.json",
)
_WF88_LIVE_DEPENDENCIES = (
    "tmp/wf88-os2-control-packet.json",
    "tmp/improvement-ledger-current.json",
    "tmp/retrieval-live-eval.json",
)


def _loop_live_sla_hours(route: dict[str, Any]) -> float:
    """Producer-clock SLA for a route; falls back to the loop 72h default."""
    sla = route.get("freshness_sla")
    if isinstance(sla, dict):
        for key in ("primary_artifact_max_age_hours", "owner_context_max_age_hours"):
            value = sla.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return _LOOP_LIVE_SLA_FALLBACK_HOURS


def _loop_live_parse_generated_at(raw: Any) -> datetime | None:
    """Finite declared proof timestamp; filesystem mtime is never proof freshness."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        moment = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        stamp = moment.timestamp()
    except (OverflowError, OSError, ValueError):
        return None
    if stamp != stamp or stamp in (float("inf"), float("-inf")):
        return None
    return moment


def _loop_live_status_failed(status: Any) -> bool:
    return any(token in str(status or "").casefold() for token in _LOOP_LIVE_FAIL_TOKENS)


def _loop_live_default_mtime_ns(rel: str) -> int | None:
    try:
        return (ROOT / rel).stat().st_mtime_ns
    except OSError:
        return None


def _loop_live_default_payload(rel: str) -> dict[str, Any] | None:
    try:
        with (ROOT / rel).open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _wf_loop_live_dependency_reasons(
    route: dict[str, Any],
    *,
    index_mtime_ns: int | None,
    now: datetime | None = None,
    _stat: Any = None,
    _load: Any = None,
) -> list[dict[str, Any]]:
    """Fail-closed WF74/WF88 live-dependency check (lookup-time, no producer run).

    _stat maps a workspace-relative path to an mtime ns (or None when absent);
    _load maps it to a parsed JSON dict (or None when missing/unreadable).
    Defaults read the live workspace; tests inject fakes so no fixture files
    are written into the workspace.
    """
    workflow_id = str(route.get("workflow_id") or "")
    if workflow_id == "WF74":
        dependencies = _WF74_LIVE_DEPENDENCIES
    elif workflow_id == "WF88":
        dependencies = tuple(dict.fromkeys((*_WF88_LIVE_DEPENDENCIES, *_WF74_LIVE_DEPENDENCIES)))
    else:
        return []
    stat = _stat or _loop_live_default_mtime_ns
    load = _load or _loop_live_default_payload
    moment_now = now if now is not None else datetime.now(timezone.utc)
    sla_hours = _loop_live_sla_hours(route)
    cached_blockers = route.get("blockers") or []
    reasons: list[dict[str, Any]] = []
    if index_mtime_ns is None:
        reasons.append({
            "source": "live_dependency",
            "workflow_id": workflow_id,
            "reason": "route_index_mtime_unavailable",
            "detail": "cannot prove cached WF74/WF88 blockers/limits postdate live evidence; rebuild the index",
        })
        return reasons
    for rel in dependencies:
        current_mtime_ns = stat(rel)
        if current_mtime_ns is None:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_missing",
                "detail": "live evidence absent on disk; cached blockers/limits are unproven",
            })
            continue
        if current_mtime_ns > index_mtime_ns:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_changed_after_index",
                "stored_mtime_ns": index_mtime_ns,
                "current_mtime_ns": current_mtime_ns,
            })
            continue
        payload = load(rel)
        if payload is None:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_unreadable",
                "detail": "live evidence is not parseable JSON; fail closed until the producer is repaired",
            })
            continue
        generated = _loop_live_parse_generated_at(payload.get("generated_at_utc"))
        if generated is None:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_no_usable_generated_at_utc",
                "detail": "missing or unparsable producer clock; touching the file must never green it",
            })
            continue
        skew_seconds = (generated - moment_now).total_seconds()
        if skew_seconds > _LOOP_LIVE_FUTURE_SKEW_SECONDS:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_generated_at_in_future",
                "detail": "producer timestamp is ahead of now beyond skew tolerance; fail closed",
            })
            continue
        age_hours = round(-skew_seconds / 3600.0, 1)
        if age_hours > sla_hours:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_expired_by_producer_clock",
                "age_hours": age_hours,
                "sla_hours": sla_hours,
                "detail": "evidence expired by producer clock although the filesystem is untouched",
            })
            continue
        validation = payload.get("validation")
        live_failed = _loop_live_status_failed(payload.get("status")) or (
            isinstance(validation, dict)
            and (
                _loop_live_status_failed(validation.get("status"))
                or (isinstance(validation.get("errors"), list) and len(validation["errors"]) > 0)
            )
        )
        if live_failed and not cached_blockers:
            reasons.append({
                "source": "live_dependency",
                "workflow_id": workflow_id,
                "artifact": rel,
                "reason": "live_proof_reports_failure_against_cached_green",
                "detail": "live evidence reports failure while cached blockers claim green; rebuild before serving",
            })
    return reasons


def route_index_staleness_reasons(
    payload: dict[str, Any],
    selected_routes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Refuse a route answer when either canonical control source moved.

    The router is a derived reader.  It must not repair or reinterpret a
    change in Active Workflows or workflow-control overrides at answer time.
    """
    snapshot = payload.get("source_freshness")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    sources = {
        "active_workflows_mtime_ns": ACTIVE_WORKFLOWS,
        "control_overrides_mtime_ns": CONTROL_OVERRIDES,
    }
    reasons: list[dict[str, Any]] = []
    for key, path in sources.items():
        try:
            current = path.stat().st_mtime_ns
        except FileNotFoundError:
            current = None
        stored = snapshot.get(key)
        if stored != current:
            reasons.append({
                "source": key,
                "stored_mtime_ns": stored,
                "current_mtime_ns": current,
            })
    # A changed proof artifact or owner continuity note can change material
    # readiness even if the control page itself did not move.  Check only the
    # requested route(s) where possible; ``--all`` intentionally checks all.
    candidates = selected_routes or []
    for route in candidates:
        freshness = route.get("freshness") if isinstance(route.get("freshness"), dict) else {}
        checks = [
            ("continuity_note", route.get("continuity_note"), freshness.get("continuity_note_mtime_ns")),
            ("primary_route_artifact", route.get("primary_route_artifact"), freshness.get("primary_artifact_mtime_ns")),
        ]
        for field, relative, stored in checks:
            if not relative:
                continue
            if field == "primary_route_artifact" and freshness.get("primary_artifact_self_referential") is True:
                continue
            path = ROOT / str(relative)
            try:
                current = path.stat().st_mtime_ns
            except FileNotFoundError:
                current = None
            if stored != current:
                reasons.append({
                    "source": field,
                    "workflow_id": route.get("workflow_id"),
                    "stored_mtime_ns": stored,
                    "current_mtime_ns": current,
                })
    # LOOP-REPAIR-20260912 (consumer slice): targeted WF74/WF88 live
    # dependency invalidation. Secondary ledger/docket/OTEL/retrieval changes
    # and elapsed producer-clock SLA are invisible to the mtime checks above.
    try:
        index_mtime_ns: int | None = ROUTE_INDEX.stat().st_mtime_ns
    except OSError:
        index_mtime_ns = None
    for route in candidates:
        reasons.extend(_wf_loop_live_dependency_reasons(route, index_mtime_ns=index_mtime_ns))
    return reasons


def pm_actions() -> list[dict[str, Any]]:
    payload = pm_next_actions()
    items = payload.get("next_actions", [])
    return items if isinstance(items, list) else []


def pm_jobs() -> list[dict[str, Any]]:
    payload = pm_implementation_job_queue()
    items = payload.get("jobs", [])
    return items if isinstance(items, list) else []


def find_route(selector: str, all_routes: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = selector_key(selector)
    if not wanted:
        return None
    matches = [route for route in all_routes if wanted in route_selector_keys(route)]
    return matches[0] if len(matches) == 1 else None


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
    # The routing index has already reconciled the canonical control sources.
    # Do not apply a second override here: doing so can produce a fresh-looking
    # capsule from a stale derived index.
    route = dict(route)
    action = matching_pm_action(route, actions)
    override = find_override(route.get("workflow_id", ""), workflow_name=route.get("display_name"), registry=registry)
    job = matching_pm_job(action, jobs)
    effective_status = route.get("effective_status_override") or route.get("readiness") or "route_only"
    next_action = route.get("authoritative_next_action") or route.get("next_action")
    helper_safe = bool(route.get("safe_for_helper_lane")) and route.get("readiness") == "route_only"
    pm_action = dict(action) if action else None
    if pm_action and pm_action.get("lane_status") != effective_status:
        pm_action["source_lane_status"] = pm_action.get("lane_status")
        pm_action["lane_status"] = effective_status
        pm_action["superseded_by_route_contract"] = True
    return {
        "schema": SCHEMA,
        "workflow_id": route.get("workflow_id"),
        "display_name": route.get("display_name"),
        "tier": route.get("tier"),
        "priority": route.get("priority"),
        "lifecycle": route.get("lifecycle"),
        "readiness": route.get("readiness"),
        "effective_status": effective_status,
        "current_state": route.get("current_state"),
        "next_action": next_action,
        "authoritative_next_action": route.get("authoritative_next_action"),
        "helper_safe": helper_safe,
        "owner_action_required": route.get("owner_action_required"),
        "authority_boundary": route.get("authority_boundary"),
        "authority_class": route.get("authority_class"),
        "primary_owner_lane": route.get("primary_owner_lane"),
        "secondary_consumers": route.get("secondary_consumers") or [],
        "human_approval_owner": route.get("human_approval_owner"),
        "proof_artifact": route.get("proof_artifact"),
        "freshness_sla": route.get("freshness_sla"),
        "blockers": route.get("blockers", []),
        # LOOP-REPAIR-20260912: project producer-computed claim limits beside
        # blockers; claim limits constrain claims and never block operation.
        "claim_limits": list(route.get("claim_limits") or []),
        "stop_lines": route.get("stop_lines", []),
        "continuity_note": route.get("continuity_note"),
        "primary_route_artifact": route.get("primary_route_artifact"),
        "secondary_artifacts": route.get("secondary_artifacts", []),
        "validator_commands": route.get("validator_commands", []),
        "default_resume_command": route.get("default_resume_command"),
        "control_override": override,
        "pm_action": pm_action,
        "pm_job": {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "validation_budget": job.get("validation_budget"),
            "closeout_mode": job.get("closeout_mode"),
            "collision_group": job.get("collision_group"),
        } if job else None,
        "sources": {
            "route_index": str(ROUTE_INDEX.relative_to(ROOT)),
            "canonical_control": [
                str(ACTIVE_WORKFLOWS.relative_to(ROOT)),
                str(CONTROL_OVERRIDES.relative_to(ROOT)),
            ],
            "pm_control_packet": "tmp/pm-control-packet.json",
        },
    }


def validate_capsule(capsule: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "workflow_id", "display_name", "tier", "priority", "lifecycle", "readiness", "current_state",
        "effective_status", "next_action", "authoritative_next_action", "authority_class",
        "primary_owner_lane", "human_approval_owner",
    ):
        if not capsule.get(key):
            errors.append(f"missing_{key}")
    if capsule.get("control_override") and capsule.get("helper_safe") is not False:
        errors.append("held_capsule_helper_safe_not_false")
    if capsule.get("effective_status") == "ready":
        errors.append("route_only_must_not_serialize_as_ready")
    if capsule.get("lifecycle") == "paused" and (
        capsule.get("effective_status") != "on_hold" or capsule.get("helper_safe") is not False
    ):
        errors.append("paused_capsule_must_be_on_hold_and_helper_unsafe")
    if capsule.get("authority_class") == "paper_guard_fail_closed" and capsule.get("effective_status") != "blocked":
        errors.append("paper_guard_capsule_must_be_blocked")
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
    parser.add_argument("--answer", choices=["summary", "next", "blockers", "helper", "all", "code_structure"], default="summary")
    parser.add_argument("--code-node", help="Symbol/file node for --answer code_structure, e.g. workflow_router.py")
    parser.add_argument("--code-graph", choices=["scripts", "skills", "skills-md"], default="scripts", help="Graph namespace for --answer code_structure")
    parser.add_argument("--code-subcommand", choices=["affected", "explain", "path", "query"], default=None, help="Graphify subcommand; defaults to affected for scripts/skills and explain for skills-md")
    parser.add_argument("--code-target", help="Second node for --code-subcommand path")
    parser.add_argument("--write-capsules", action="store_true", help="Write capsules for selected workflow or all workflows.")
    parser.add_argument("--all", action="store_true", help="Select all workflows for capsule writing/listing.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--list", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = load_registry()
    index_payload = read_json(ROUTE_INDEX)
    items = index_payload.get("routes", [])
    all_routes = items if isinstance(items, list) else []
    actions = pm_actions()
    jobs = pm_jobs()

    if args.list:
        stale_reasons = route_index_staleness_reasons(index_payload)
        if stale_reasons:
            print(json.dumps({
                "status": "error",
                "error": "routing_index_stale",
                "reasons": stale_reasons,
                "refresh_command": "python scripts\\workflow_routing_index.py --write --write-db --validate",
            }, indent=2))
            return 1
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

    stale_reasons = route_index_staleness_reasons(index_payload, selected)
    if stale_reasons:
        print(json.dumps({
            "status": "error",
            "error": "routing_index_stale",
            "reasons": stale_reasons,
            "refresh_command": "python scripts\\workflow_routing_index.py --write --write-db --validate",
        }, indent=2))
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
    elif args.answer == "code_structure":
        if not GraphifyRouter:
            answer = {"status": "unavailable", "reason": "graphify_router not importable"}
        elif not args.code_node:
            answer = {"status": "error", "error": "--code-node required for --answer code_structure"}
        else:
            try:
                router = GraphifyRouter()
                subcommand = args.code_subcommand
                if subcommand is None:
                    subcommand = "explain" if args.code_graph == "skills-md" else "affected"
                if subcommand == "affected":
                    result = router.affected(args.code_node, graph_name=args.code_graph)
                elif subcommand == "explain":
                    result = router.explain(args.code_node, graph_name=args.code_graph)
                elif subcommand == "path":
                    target = args.code_target or args.code_node
                    result = router.path(args.code_node, target, graph_name=args.code_graph)
                elif subcommand == "query":
                    result = router.query(args.code_node, graph_name=args.code_graph)
                else:
                    result = {"status": "error", "error": "unknown subcommand"}
                answer = {
                    "status": "ok",
                    "code_node": args.code_node,
                    "code_graph": args.code_graph,
                    "code_subcommand": subcommand,
                    "graphify_available": router.available(),
                    "result": result,
                }
            except GraphifyError as exc:
                answer = {"status": "error", "error": str(exc)}
    else:
        answer = [{
            "workflow_id": item["workflow_id"],
            "display_name": item["display_name"],
            "priority": item["priority"],
            "lifecycle": item["lifecycle"],
            "readiness": item["readiness"],
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
