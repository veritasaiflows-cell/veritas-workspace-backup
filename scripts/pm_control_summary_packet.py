#!/usr/bin/env python3
"""Build a stable PM-control summary packet.

The full PM control packet is useful but too volatile and large for default
semantic memory. This packet keeps only stable counts, top actions, freshness,
and authority boundaries for retrieval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PM_CONTROL = TMP / "pm-control-packet.json"
OUT = TMP / "pm-control-summary-packet.json"
MD_OUT = OUT.with_suffix(".md")
SCHEMA = "veritas.pm_control_summary_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "stable_summary_only": True,
    "source_packet_route_only": True,
    "executes_work": False,
    "spawns_helpers": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
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


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def slim_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": action.get("rank"),
        "lane_id": action.get("lane_id"),
        "action_id": action.get("action_id"),
        "action_type": action.get("action_type"),
        "lane_status": action.get("lane_status"),
        "readiness_score": action.get("readiness_score"),
        "authority": action.get("authority"),
        "helper_lane_allowed_from_main_session": action.get("helper_lane_allowed_from_main_session"),
        "inline_execution_allowed": action.get("inline_execution_allowed"),
        "heartbeat_may_execute": action.get("heartbeat_may_execute"),
        "description": action.get("description"),
        "stop_lines": as_list(action.get("stop_lines")),
    }


def slim_stale_lane(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane_id": row.get("lane_id"),
        "title": row.get("title"),
        "readiness_score": row.get("readiness_score"),
        "top_job_id": row.get("top_job_id"),
        "top_job_title": row.get("top_job_title"),
        "closeout_mode": row.get("closeout_mode"),
        "validation_budget": row.get("validation_budget"),
        "helper_lane_allowed_from_main_session": row.get("helper_lane_allowed_from_main_session"),
        "next_action": row.get("next_action"),
    }


def build_packet(pm_control_path: Path = PM_CONTROL) -> dict[str, Any]:
    packet = load(pm_control_path)
    summary = as_dict(packet.get("summary"))
    implementation_queue = as_dict(summary.get("implementation_queue"))
    heartbeat = as_dict(summary.get("heartbeat"))
    handoff = as_dict(summary.get("main_session_handoff"))
    greenkeeper = as_dict(summary.get("main_session_greenkeeper"))
    escalation = as_dict(summary.get("main_session_escalation_consumer"))
    signal_freshness = as_dict(summary.get("control_plane_signal_freshness"))
    stale_digest = as_dict(summary.get("stale_lane_digest"))
    stale_lanes = [slim_stale_lane(as_dict(row)) for row in as_list(stale_digest.get("lanes"))[:12]]
    top_action = slim_action(as_dict(summary.get("top_next_action")))

    warnings: list[str] = []
    if not pm_control_path.exists():
        warnings.append("pm_control_packet_missing")
    if packet.get("status") != "ok":
        warnings.append(f"pm_control_status:{packet.get('status')}")
    if greenkeeper.get("validation_warnings"):
        warnings.append("greenkeeper_warning_present")
    if handoff.get("status") == "ready_for_main_session":
        warnings.append("main_session_handoff_ready")

    validation_status = "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "summary_warning_no_apply_authority" if warnings else "ok",
        "purpose": "Stable PM control summary for vector-memory retrieval without indexing the raw PM control packet.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "pm_control_packet": {
                "path": rel(pm_control_path),
                "present": pm_control_path.exists(),
                "sha256": sha256_file(pm_control_path),
                "status": packet.get("status"),
                "validation_status": as_dict(packet.get("validation")).get("status"),
                "generated_at_utc": packet.get("generated_at_utc"),
            }
        },
        "summary": {
            "pm_status": summary.get("pm_status"),
            "pm_readiness": summary.get("pm_readiness"),
            "next_action_count": summary.get("next_action_count"),
            "implementation_job_count": implementation_queue.get("job_count"),
            "implementation_ready_job_count": implementation_queue.get("ready_job_count"),
            "implementation_active_job_count": implementation_queue.get("active_job_count"),
            "implementation_blocked_job_count": implementation_queue.get("blocked_job_count"),
            "helper_lane_allowed_job_count": implementation_queue.get("helper_lane_allowed_job_count"),
            "heartbeat_candidate_count": heartbeat.get("candidate_count"),
            "heartbeat_blocked_count": heartbeat.get("blocked_count"),
            "heartbeat_handoff_ready_count": heartbeat.get("handoff_ready_count"),
            "stale_lane_count": stale_digest.get("stale_lane_count"),
            "control_plane_stale_count": signal_freshness.get("stale_count"),
            "cron_escalation_signal_count": escalation.get("cron_escalation_signal_count"),
            "main_session_greenkeeper_status": greenkeeper.get("status"),
            "main_session_handoff_status": handoff.get("status"),
            "selected_action": handoff.get("selected_action"),
            "selected_lane": handoff.get("selected_lane"),
            "next_safe_action": "Use this summary for recall; inspect tmp/pm-control-packet.json before material PM action.",
        },
        "top_next_action": top_action,
        "stale_lane_digest": {
            "stale_lane_count": stale_digest.get("stale_lane_count"),
            "next_safe_action": stale_digest.get("next_safe_action"),
            "lanes": stale_lanes,
        },
        "blocked_actions": [
            "do_not_index_raw_pm_control_packet_by_default",
            "do_not_execute_pm_jobs_from_this_summary",
            "do_not_spawn_helpers_from_this_summary",
            "do_not_infer_owner_or_finance_authority",
        ],
        "validation": {
            "status": validation_status,
            "errors": [],
            "warnings": warnings,
        },
    }


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    top = as_dict(payload.get("top_next_action"))
    lines = [
        "# PM Control Summary Packet",
        "",
        f"- Status: {payload.get('status')}",
        f"- PM status: {summary.get('pm_status')}",
        f"- Ready implementation jobs: {summary.get('implementation_ready_job_count')}",
        f"- Active implementation jobs: {summary.get('implementation_active_job_count')}",
        f"- Blocked implementation jobs: {summary.get('implementation_blocked_job_count')}",
        f"- Stale lanes: {summary.get('stale_lane_count')}",
        f"- Main-session handoff: {summary.get('main_session_handoff_status')} / {summary.get('selected_lane')}",
        f"- Top next action: {top.get('lane_id')} - {top.get('description')}",
        "",
        "## Boundary",
        "- Stable summary only. Inspect tmp/pm-control-packet.json before material PM action.",
        "- No execution, helper spawn, cron, runtime, canon, portfolio, finance, paper/live, or approval authority.",
        "",
    ]
    return "\n".join(lines)


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pm-control", type=Path, default=PM_CONTROL)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_packet(workspace_path(args.pm_control))
    out = workspace_path(args.out)
    md_out = workspace_path(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "out": rel(out),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
        }, indent=2, sort_keys=True))
    return 0 if as_dict(payload.get("validation")).get("errors") == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())
