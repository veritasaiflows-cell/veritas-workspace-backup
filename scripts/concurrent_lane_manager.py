#!/usr/bin/env python3
"""MVP concurrent lane lease manager.

This is a small anti-collision register for parallel workflow/helper lanes. It
does not spawn helpers, schedule work, mutate canon/portfolio state, infer owner
approval, or grant execution authority. It records planned/leased/running/
complete lanes and validates that active lanes do not write the same surfaces.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTER = TMP / "concurrent-lane-register.json"
WORKFLOW_INDEX = TMP / "workflow-routing-index.json"
SHADOW_PILOT_ERROR = TMP / "wf73-postgres-shadow-pilot-metrics.json"
SCHEMA = "veritas.concurrent_lane_register.v1"

ACTIVE_STATUSES = {"planned", "leased", "running"}
VALID_STATUSES = ACTIVE_STATUSES | {"complete", "blocked", "cancelled"}
TERMINAL_STATUSES = {"complete", "blocked", "cancelled"}
DEFAULT_LEASE_HOURS = 6

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "coordination_register_only": True,
    "spawns_helpers": False,
    "scheduler_allowed": False,
    "autonomous_execution_allowed": False,
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

REQUIRED_TRUE_FLAGS = {"review_only", "coordination_register_only"}
REQUIRED_FALSE_FLAGS = {flag for flag in AUTHORITY_BOUNDARY if flag not in REQUIRED_TRUE_FLAGS}

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
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def route_by_id(workflow_id: str) -> dict[str, Any]:
    index = load_dict(WORKFLOW_INDEX)
    wanted = workflow_id.upper()
    for route in as_list(index.get("routes")):
        if isinstance(route, dict) and str(route.get("workflow_id") or "").upper() == wanted:
            return route
    return {}


def empty_register() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_authority": "06. Playbooks/Active Workflows.md",
        "workflow_route_index": rel(WORKFLOW_INDEX),
        "lanes": [],
        "stop_lines": [
            "This register coordinates helper-lane leases only; it does not spawn helpers or schedule work.",
            "No two active lanes may write the same surface.",
            "Completion requires proof artifacts or acceptance commands.",
            "No canon/portfolio/config/auth/runtime/destructive/capital/trade/account/money authority.",
        ],
    }


def load_register(path: Path) -> dict[str, Any]:
    register = load_dict(path)
    if not register:
        return empty_register()
    register.setdefault("schema", SCHEMA)
    register.setdefault("authority_boundary", dict(AUTHORITY_BOUNDARY))
    register.setdefault("lanes", [])
    register.setdefault("stop_lines", empty_register()["stop_lines"])
    return register


def lane_id(workflow_id: str, workstream_id: str) -> str:
    return f"{workflow_id.upper()}::{workstream_id.strip().lower()}"


def find_lane(register: dict[str, Any], workflow_id: str, workstream_id: str) -> dict[str, Any] | None:
    target = lane_id(workflow_id, workstream_id)
    for lane in as_list(register.get("lanes")):
        if isinstance(lane, dict) and lane.get("lane_id") == target:
            return lane
    return None


def default_forbidden_writes(route: dict[str, Any]) -> list[str]:
    forbidden = [
        "SOUL.md",
        "AGENTS.md",
        "TOOLS.md",
        "MEMORY.md",
        "03. Portfolio/*",
        "state/finance/*",
        "data/finance/universe-v1.json",
        "09. Archive/*",
        "config/auth/runtime/channel/credential surfaces",
    ]
    if route.get("owner_action_required"):
        forbidden.append("owner-gated route surfaces without main-session approval")
    return forbidden


def build_lane_template(workflow_id: str, workstream_id: str, owner: str = "unassigned") -> dict[str, Any]:
    route = route_by_id(workflow_id)
    now = utc_now()
    read_first: list[str] = []
    if route.get("continuity_note"):
        read_first.append(route["continuity_note"])
    if route.get("primary_route_artifact") and not route.get("primary_pending"):
        read_first.append(route["primary_route_artifact"])
    read_first.extend(as_list(route.get("secondary_artifacts")))
    acceptance = as_list(route.get("validator_commands")) + ["python scripts\\concurrent_lane_manager.py --validate"]
    return {
        "lane_id": lane_id(workflow_id, workstream_id),
        "workflow_id": workflow_id.upper(),
        "workstream_id": workstream_id,
        "owner": owner,
        "status": "planned",
        "mode": "Spawn distinct-output" if route.get("safe_for_helper_lane", True) else "Main-session only",
        "created_at_utc": now,
        "updated_at_utc": now,
        "lease_expires_at_utc": None,
        "read_first": read_first[:6],
        "allowed_writes": [],
        "forbidden_writes": default_forbidden_writes(route),
        "acceptance_commands": acceptance,
        "proof_artifacts": [],
        "stop_lines": as_list(route.get("stop_lines")),
        "notes": [],
        "merge_required_by_main": True,
        "authority_boundary": route.get("authority_boundary") or "derived helper-lane coordination only; no approval/execution/mutation authority",
    }


def upsert_lane(register: dict[str, Any], lane: dict[str, Any]) -> None:
    lanes = as_list(register.get("lanes"))
    for index, existing in enumerate(lanes):
        if isinstance(existing, dict) and existing.get("lane_id") == lane.get("lane_id"):
            lanes[index] = lane
            register["lanes"] = lanes
            return
    lanes.append(lane)
    register["lanes"] = lanes


def apply_runtime_metadata(lane: dict[str, Any], args: argparse.Namespace) -> None:
    runtime = as_dict(lane.get("runtime"))
    for key in (
        "session_key",
        "session_id",
        "session_label",
        "task_name",
        "run_id",
        "model_path",
        "model_provider",
        "thinking",
        "retry_count",
    ):
        value = getattr(args, key, None)
        if value not in (None, ""):
            runtime[key] = value
    if runtime.get("model_path") and not runtime.get("model_provider"):
        model_path = str(runtime.get("model_path") or "")
        if "/" in model_path:
            runtime["model_provider"] = model_path.split("/", 1)[0]
    if runtime:
        lane["runtime"] = runtime


def stamp_status_times(lane: dict[str, Any], status: str) -> None:
    now = utc_now()
    lane["updated_at_utc"] = now
    if status == "running" and not lane.get("started_at_utc"):
        lane["started_at_utc"] = now
    if status in TERMINAL_STATUSES:
        lane["ended_at_utc"] = now
        lane["lease_expires_at_utc"] = None
        if status == "complete":
            lane["completed_at_utc"] = now
    elif status in ACTIVE_STATUSES:
        lane.pop("ended_at_utc", None)
        if status != "complete":
            lane.pop("completed_at_utc", None)


def apply_plan(register: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if find_lane(register, args.plan, args.workstream):
        raise SystemExit(f"lane already exists: {lane_id(args.plan, args.workstream)}")
    lane = build_lane_template(args.plan, args.workstream, args.owner)
    lane["notes"].append("planned_from_workflow_route_index")
    upsert_lane(register, lane)
    return lane


def apply_lease(register: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    lane = find_lane(register, args.lease, args.workstream) or build_lane_template(args.lease, args.workstream, args.owner)
    if lane.get("status") == "complete" and not args.reopen_complete:
        raise SystemExit("cannot lease a completed lane")
    if lane.get("status") == "complete" and args.reopen_complete:
        lane["proof_artifacts"] = []
        lane.pop("completed_at_utc", None)
        lane.pop("ended_at_utc", None)
    lane["status"] = args.lane_status
    lane["owner"] = args.owner
    stamp_status_times(lane, args.lane_status)
    if args.lane_status in ACTIVE_STATUSES:
        lane["lease_expires_at_utc"] = (
            datetime.now(timezone.utc) + timedelta(hours=float(args.lease_hours))
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    apply_runtime_metadata(lane, args)
    if args.allowed_write:
        lane["allowed_writes"] = sorted({normalize_path(item) for item in args.allowed_write})
    if args.read_first:
        base_read_first = [] if args.replace_contract else as_list(lane.get("read_first"))
        lane["read_first"] = sorted({normalize_path(item) for item in base_read_first + args.read_first})
    if args.acceptance_command:
        base_acceptance = [] if args.replace_contract else as_list(lane.get("acceptance_commands"))
        lane["acceptance_commands"] = base_acceptance + args.acceptance_command
    if args.note:
        lane["notes"] = as_list(lane.get("notes")) + args.note
    upsert_lane(register, lane)
    return lane


def apply_complete(register: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    lane = find_lane(register, args.complete, args.workstream)
    if lane is None:
        raise SystemExit(f"lane not found: {lane_id(args.complete, args.workstream)}")
    lane["status"] = "complete"
    stamp_status_times(lane, "complete")
    apply_runtime_metadata(lane, args)
    if args.proof:
        lane["proof_artifacts"] = sorted({normalize_path(item) for item in as_list(lane.get("proof_artifacts")) + args.proof})
    if args.note:
        lane["notes"] = as_list(lane.get("notes")) + args.note
    upsert_lane(register, lane)
    return lane


def apply_status(register: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    lane = find_lane(register, args.set_status, args.workstream)
    if lane is None:
        raise SystemExit(f"lane not found: {lane_id(args.set_status, args.workstream)}")
    lane["status"] = args.lane_status
    stamp_status_times(lane, args.lane_status)
    apply_runtime_metadata(lane, args)
    if args.note:
        lane["notes"] = as_list(lane.get("notes")) + args.note
    upsert_lane(register, lane)
    return lane


def path_forbidden(path: str) -> str | None:
    normalized = normalize_path(path)
    for pattern in FORBIDDEN_WRITE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return pattern
    return None


PROOF_PATH_EXTENSIONS = {
    ".csv",
    ".db",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".pdf",
    ".py",
    ".sqlite",
    ".txt",
    ".xlsx",
}


def proof_path_candidates(value: str) -> list[str]:
    """Return filesystem proof paths embedded in a proof entry.

    Older lane closeouts sometimes stored short narrative proof such as
    "command -> status ok" in proof_artifacts. Keep that visible, but only
    require existence checks for entries that are actually artifact paths.
    """
    candidates: list[str] = []
    for raw_part in str(value).split(";"):
        part = normalize_path(raw_part)
        if not part:
            continue
        if re.match(r"^(python|py|pytest|node|npm|go|openclaw|cd)\b", part, re.IGNORECASE):
            continue
        suffix = Path(part).suffix.lower()
        if suffix not in PROOF_PATH_EXTENSIONS:
            continue
        if re.search(r"\s(->|status=|status |=|ok\b|blocked\b|eligible=)", part, re.IGNORECASE):
            continue
        candidates.append(part)
    return candidates


def validate_register(register: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})

    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    active = [lane for lane in lanes if lane.get("status") in ACTIVE_STATUSES]
    now = datetime.now(timezone.utc)

    check("schema_current", register.get("schema") == SCHEMA, register.get("schema"))
    for flag in REQUIRED_TRUE_FLAGS:
        check(f"authority_{flag}_true", as_dict(register.get("authority_boundary")).get(flag) is True, as_dict(register.get("authority_boundary")).get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        check(f"authority_{flag}_false", as_dict(register.get("authority_boundary")).get(flag) is False, as_dict(register.get("authority_boundary")).get(flag))

    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    for lane in lanes:
        lid = str(lane.get("lane_id") or "")
        if lid in seen_ids:
            duplicate_ids.append(lid)
        seen_ids.add(lid)
    check("unique_lane_ids", not duplicate_ids, duplicate_ids)

    invalid_status = [lane.get("lane_id") for lane in lanes if lane.get("status") not in VALID_STATUSES]
    check("valid_status_values", not invalid_status, invalid_status)

    active_write_owners: dict[str, list[str]] = {}
    active_forbidden_hits: list[dict[str, str]] = []
    terminal_forbidden_hits: list[dict[str, str]] = []
    active_without_owner: list[str] = []
    stale_leases: list[str] = []
    active_without_writes: list[str] = []
    running_without_start: list[str] = []
    running_without_session: list[str] = []
    terminal_without_end: list[str] = []
    completed_without_proof: list[str] = []
    missing_proof: list[dict[str, str]] = []

    for lane in lanes:
        lid = str(lane.get("lane_id") or "")
        status = lane.get("status")
        writes = [normalize_path(str(item)) for item in as_list(lane.get("allowed_writes")) if str(item).strip()]
        if status in ACTIVE_STATUSES:
            if not lane.get("owner") or lane.get("owner") == "unassigned":
                active_without_owner.append(lid)
            if status in {"leased", "running"} and not writes:
                active_without_writes.append(lid)
            expires = parse_utc(lane.get("lease_expires_at_utc"))
            if status in {"leased", "running"} and expires and expires < now:
                stale_leases.append(lid)
            if status == "running" and not parse_utc(lane.get("started_at_utc")):
                running_without_start.append(lid)
            if status == "running" and not as_dict(lane.get("runtime")).get("session_key"):
                running_without_session.append(lid)
            for path in writes:
                active_write_owners.setdefault(path, []).append(lid)
        legacy_complete_end = status == "complete" and parse_utc(lane.get("completed_at_utc"))
        if status in TERMINAL_STATUSES and not parse_utc(lane.get("ended_at_utc")) and not legacy_complete_end:
            terminal_without_end.append(lid)
        for path in writes:
            pattern = path_forbidden(path)
            if pattern:
                hit = {"lane_id": lid, "path": path, "pattern": pattern}
                if status in ACTIVE_STATUSES:
                    active_forbidden_hits.append(hit)
                else:
                    terminal_forbidden_hits.append(hit)
        if status == "complete":
            proofs = [normalize_path(str(item)) for item in as_list(lane.get("proof_artifacts")) if str(item).strip()]
            commands = [str(item) for item in as_list(lane.get("acceptance_commands")) if str(item).strip()]
            if not proofs and not commands:
                completed_without_proof.append(lid)
            for proof in proofs:
                for proof_path in proof_path_candidates(proof):
                    if not (ROOT / proof_path).exists():
                        missing_proof.append({"lane_id": lid, "proof": proof_path})

    collisions = {path: owners for path, owners in active_write_owners.items() if len(owners) > 1}
    check("no_active_write_collisions", not collisions, collisions)
    check("no_active_forbidden_write_paths", not active_forbidden_hits, active_forbidden_hits)
    check("terminal_forbidden_write_paths", not terminal_forbidden_hits, terminal_forbidden_hits, "warning")
    check("active_lanes_have_owner", not active_without_owner, active_without_owner)
    check("leased_running_lanes_declare_writes", not active_without_writes, active_without_writes)
    check("no_stale_active_leases", not stale_leases, stale_leases, "warning")
    check("running_lanes_have_started_at", not running_without_start, running_without_start, "warning")
    check("running_lanes_have_session_metadata", not running_without_session, running_without_session, "warning")
    check("terminal_lanes_have_ended_at", not terminal_without_end, terminal_without_end, "warning")
    check("completed_lanes_have_proof_or_acceptance", not completed_without_proof, completed_without_proof)
    check("proof_artifacts_exist", not missing_proof, missing_proof)

    errors = [item for item in checks if item["severity"] == "critical" and not item["ok"]]
    warnings = [item for item in checks if item["severity"] == "warning" and not item["ok"]]
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def refresh_summary(register: dict[str, Any]) -> None:
    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    counts: dict[str, int] = {}
    workflow_counts: dict[str, int] = {}
    for lane in lanes:
        status = str(lane.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        wid = str(lane.get("workflow_id") or "unknown")
        workflow_counts[wid] = workflow_counts.get(wid, 0) + 1
    register["generated_at_utc"] = utc_now()
    register["summary"] = {
        "lane_count": len(lanes),
        "status_counts": dict(sorted(counts.items())),
        "workflow_counts": dict(sorted(workflow_counts.items())),
        "active_lane_count": sum(1 for lane in lanes if lane.get("status") in ACTIVE_STATUSES),
        "next_safe_action": "Lease narrow distinct-output lanes only after allowed_writes are explicit; main session must merge and update continuity.",
    }
    register["validation"] = validate_register(register)


def print_result(action: str, register: dict[str, Any], lane: dict[str, Any] | None = None) -> None:
    print(
        json.dumps(
            {
                "action": action,
                "status": as_dict(register.get("validation")).get("status"),
                "summary": register.get("summary"),
                "lane": lane,
                "validation": {
                    "errors": len(as_list(as_dict(register.get("validation")).get("errors"))),
                    "warnings": len(as_list(as_dict(register.get("validation")).get("warnings"))),
                },
            },
            indent=2,
        )
    )


def refresh_shadow_pilot_after_write(register_path: Path) -> None:
    """Refresh passive WF73 shadow telemetry without making it lane authority."""
    try:
        from wf73_postgres_shadow_pilot import refresh_shadow_pilot

        refresh_shadow_pilot(register_path)
    except Exception as exc:  # pragma: no cover - fail-open by design
        atomic_write_json(
            SHADOW_PILOT_ERROR,
            {
                "schema": "veritas.wf73.postgres_shadow_pilot_metrics.v1",
                "generated_at_utc": utc_now(),
                "status": "warning",
                "mode": "shadow_refresh_failed_json_primary_preserved",
                "metrics": {
                    "json_primary": True,
                    "postgres_runtime_dependency": False,
                    "shadow_projection_available": False,
                },
                "validation": {
                    "status": "warning",
                    "errors": [],
                    "warnings": [f"shadow_refresh_failed:{type(exc).__name__}"],
                },
                "authority_boundary": {
                    "review_only": True,
                    "shadow_projection_only": True,
                    "json_lane_register_primary": True,
                    "lane_claim_authority_allowed": False,
                    "owner_approval_inferred": False,
                },
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--plan", metavar="WORKFLOW")
    action.add_argument("--lease", metavar="WORKFLOW")
    action.add_argument("--complete", metavar="WORKFLOW")
    action.add_argument("--set-status", metavar="WORKFLOW")
    action.add_argument("--status", dest="show_status", action="store_true")
    parser.add_argument("--workstream", default="default", help="Workstream identifier within the workflow.")
    parser.add_argument("--owner", default="unassigned")
    parser.add_argument("--lease-hours", type=float, default=DEFAULT_LEASE_HOURS)
    parser.add_argument("--allowed-write", action="append", default=[])
    parser.add_argument("--read-first", action="append", default=[])
    parser.add_argument("--acceptance-command", action="append", default=[])
    parser.add_argument("--session-key", default="", help="OpenClaw session key for the helper lane, when known.")
    parser.add_argument("--session-id", default="", help="OpenClaw session id for the helper lane, when known.")
    parser.add_argument("--session-label", default="", help="Human-readable helper session label, when known.")
    parser.add_argument("--task-name", default="", help="Stable OpenClaw taskName/alias for the helper lane, when known.")
    parser.add_argument("--run-id", default="", help="Stable model/runtime run id, when known.")
    parser.add_argument("--model-path", default="", help="Model path for the lane, for example openai/gpt-5.5.")
    parser.add_argument("--model-provider", default="", help="Model provider, inferred from --model-path when omitted.")
    parser.add_argument("--thinking", default="", help="Model reasoning/posture level, when exposed.")
    parser.add_argument("--retry-count", default="", help="Retry count for the lane, when known.")
    parser.add_argument(
        "--replace-contract",
        action="store_true",
        help="Replace template read_first and acceptance commands with explicitly supplied lane contract values.",
    )
    parser.add_argument(
        "--reopen-complete",
        action="store_true",
        help="Allow a completed lane to be re-leased when its proof is stale against current input artifacts.",
    )
    parser.add_argument("--proof", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--status-value", dest="lane_status", default="leased", choices=sorted(VALID_STATUSES))
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    register_path = args.register if args.register.is_absolute() else ROOT / args.register
    register = load_register(register_path)
    lane: dict[str, Any] | None = None
    action_name = "status"

    if args.plan:
        action_name = "plan"
        lane = apply_plan(register, args)
    elif args.lease:
        action_name = "lease"
        lane = apply_lease(register, args)
    elif args.complete:
        action_name = "complete"
        lane = apply_complete(register, args)
    elif args.set_status:
        action_name = "set-status"
        lane = apply_status(register, args)

    refresh_summary(register)
    if args.write:
        atomic_write_json(register_path, register)
        refresh_shadow_pilot_after_write(register_path)
    print_result(action_name, register, lane)
    if args.validate and as_dict(register.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
