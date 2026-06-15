#!/usr/bin/env python3
"""Summarize PM parallel-operator health from local proof artifacts.

This is a reporting-only surface over the JSON lane register, WF73 shadow
metrics, and the PM control packet. It does not lease lanes, spawn helpers,
mutate PM state, touch the PM cockpit, schedule work, or grant approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_LANE_REGISTER = TMP / "concurrent-lane-register.json"
DEFAULT_SHADOW_METRICS = TMP / "wf73-postgres-shadow-pilot-metrics.json"
DEFAULT_PM_PACKET = TMP / "pm-control-packet.json"
DEFAULT_OUT = TMP / "pm-parallel-operator-visibility.json"

SCHEMA = "veritas.parallel_operator_visibility.v1"
ACTIVE_STATUSES = {"planned", "leased", "running"}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "local_reporting_only": True,
    "lane_register_json_primary": True,
    "wf73_shadow_passive_telemetry_only": True,
    "pm_packet_review_only": True,
    "executes_work": False,
    "spawns_helpers": False,
    "leases_or_completes_lanes": False,
    "touches_pm_cockpit_app": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {
    "review_only",
    "local_reporting_only",
    "lane_register_json_primary",
    "wf73_shadow_passive_telemetry_only",
    "pm_packet_review_only",
}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(value: str | None, default: Path) -> Path:
    path = Path(value) if value else default
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def source_state(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def lane_runtime_label(lane: dict[str, Any]) -> str | None:
    runtime = as_dict(lane.get("runtime"))
    return runtime.get("session_label") or runtime.get("session_key") or runtime.get("session_id")


def active_lane_summary(register: dict[str, Any]) -> dict[str, Any]:
    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    active = [lane for lane in lanes if lane.get("status") in ACTIVE_STATUSES]
    active_rows: list[dict[str, Any]] = []
    active_write_rows: list[dict[str, Any]] = []
    collisions: dict[str, list[str]] = {}

    for lane in active:
        lane_id = str(lane.get("lane_id") or "")
        writes = [normalize_path(path) for path in as_list(lane.get("allowed_writes")) if normalize_path(path)]
        active_rows.append(
            {
                "lane_id": lane_id,
                "workflow_id": lane.get("workflow_id"),
                "workstream_id": lane.get("workstream_id"),
                "owner": lane.get("owner"),
                "status": lane.get("status"),
                "started_at_utc": lane.get("started_at_utc"),
                "updated_at_utc": lane.get("updated_at_utc"),
                "lease_expires_at_utc": lane.get("lease_expires_at_utc"),
                "runtime_label": lane_runtime_label(lane),
                "active_write_count": len(writes),
            }
        )
        for path in writes:
            active_write_rows.append({"path": path, "lane_id": lane_id, "status": lane.get("status")})
            collisions.setdefault(path, []).append(lane_id)

    collision_rows = [
        {"path": path, "lane_ids": sorted(lane_ids), "lane_count": len(lane_ids)}
        for path, lane_ids in sorted(collisions.items())
        if len(set(lane_ids)) > 1
    ]
    return {
        "lane_count": len(lanes),
        "active_lane_count": len(active_rows),
        "active_lanes": sorted(active_rows, key=lambda row: str(row.get("lane_id") or "")),
        "active_write_lease_count_from_register": len(active_write_rows),
        "active_write_leases": sorted(active_write_rows, key=lambda row: (row["path"], row["lane_id"])),
        "write_collision_count": len(collision_rows),
        "write_collisions": collision_rows,
    }


def shadow_summary(metrics_packet: dict[str, Any]) -> dict[str, Any]:
    metrics = as_dict(metrics_packet.get("metrics"))
    validation = as_dict(metrics_packet.get("validation"))
    return {
        "status": metrics_packet.get("status"),
        "generated_at_utc": metrics_packet.get("generated_at_utc"),
        "json_primary": metrics.get("json_primary"),
        "postgres_runtime_dependency": metrics.get("postgres_runtime_dependency"),
        "postgres_connection_attempted": metrics.get("postgres_connection_attempted"),
        "active_lane_count": metrics.get("active_lane_count"),
        "active_write_lease_rows": metrics.get("active_write_lease_rows"),
        "total_shadow_rows": metrics.get("total_shadow_rows"),
        "elapsed_ms": metrics.get("elapsed_ms"),
        "validation_status": validation.get("status"),
        "validation_error_count": len(as_list(validation.get("errors"))),
        "validation_warning_count": len(as_list(validation.get("warnings"))),
    }


def pm_summary(pm_packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(pm_packet.get("summary"))
    queue = as_dict(summary.get("implementation_queue"))
    readiness = as_dict(summary.get("pm_readiness"))
    top_action = as_dict(summary.get("top_next_action"))
    stale_digest = as_dict(summary.get("stale_lane_digest"))
    return {
        "status": pm_packet.get("status"),
        "generated_at_utc": pm_packet.get("generated_at_utc"),
        "readiness_band": readiness.get("readiness_band"),
        "readiness_average_score": readiness.get("average_score"),
        "ready_or_complete_lanes": readiness.get("ready_or_complete_lanes"),
        "blocked_lanes": readiness.get("blocked_lanes"),
        "stale_lanes": readiness.get("stale_lanes"),
        "needs_validation_lanes": readiness.get("needs_validation_lanes"),
        "job_count": queue.get("job_count"),
        "ready_job_count": queue.get("ready_job_count"),
        "blocked_job_count": queue.get("blocked_job_count"),
        "owner_decision_job_count": queue.get("owner_decision_job_count"),
        "top_job_id": queue.get("top_job_id"),
        "top_job_title": queue.get("top_job_title"),
        "top_next_action_id": top_action.get("action_id"),
        "top_next_action_description": top_action.get("description"),
        "top_next_action_lane": top_action.get("lane_id"),
        "top_next_action_lane_status": top_action.get("lane_status"),
        "stale_lane_count": stale_digest.get("stale_lane_count"),
    }


def validate_payload(payload: dict[str, Any], source_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    boundary = as_dict(payload.get("authority_boundary"))
    for flag in sorted(REQUIRED_TRUE_FLAGS):
        if boundary.get(flag) is not True:
            errors.append(f"authority_boundary_{flag}_not_true")
    for flag in sorted(REQUIRED_FALSE_FLAGS):
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary_{flag}_not_false")

    for name, source_payload in source_payloads.items():
        if not source_payload:
            errors.append(f"{name}_missing_or_unparseable")

    lane = as_dict(payload.get("lane_register"))
    if lane.get("write_collision_count"):
        errors.append("active_write_collision_detected")
    if lane.get("active_lane_count") != payload.get("shadow_metrics", {}).get("active_lane_count"):
        warnings.append("lane_register_active_count_differs_from_shadow_metrics")
    if lane.get("active_write_lease_count_from_register") != payload.get("shadow_metrics", {}).get("active_write_lease_rows"):
        warnings.append("lane_register_write_lease_count_differs_from_shadow_metrics")

    shadow = as_dict(payload.get("shadow_metrics"))
    if shadow.get("json_primary") is not True:
        errors.append("shadow_metrics_json_primary_not_true")
    if shadow.get("postgres_runtime_dependency") not in {False, None}:
        errors.append("shadow_metrics_postgres_runtime_dependency_not_false")
    if shadow.get("postgres_connection_attempted") not in {False, None}:
        errors.append("shadow_metrics_postgres_connection_attempted_not_false")
    if shadow.get("validation_status") not in {None, "ok"}:
        warnings.append("shadow_metrics_validation_not_ok")

    pm = as_dict(payload.get("pm_packet"))
    if pm.get("status") not in {None, "ok", "warning"}:
        warnings.append("pm_packet_status_not_ok")

    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def next_safe_action(lane: dict[str, Any], pm: dict[str, Any], validation: dict[str, Any]) -> str:
    if validation.get("errors"):
        return "Stop and repair visibility source/authority validation before using this report."
    if lane.get("write_collision_count"):
        return "Stop: active write lease collision detected in the JSON lane register."
    active_lane_count = int(lane.get("active_lane_count") or 0)
    active_write_count = int(lane.get("active_write_lease_count_from_register") or 0)
    if active_lane_count:
        return (
            f"Keep {active_lane_count} active lane(s) on their leased outputs; "
            f"avoid {active_write_count} active write lease(s) and merge only after proof."
        )
    if int(pm.get("blocked_job_count") or 0):
        top = pm.get("top_next_action_description") or pm.get("top_job_title") or "the top PM blocker"
        return f"Inspect the PM blocker first: {top}"
    if int(pm.get("ready_job_count") or 0):
        top = pm.get("top_job_title") or pm.get("top_next_action_description") or "the top ready PM job"
        return f"Next review-only PM action: {top}"
    return "No active lanes or ready PM jobs; refresh PM packet before opening new work."


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    lane_path = workspace_path(args.lane_register, DEFAULT_LANE_REGISTER)
    shadow_path = workspace_path(args.shadow_metrics, DEFAULT_SHADOW_METRICS)
    pm_path = workspace_path(args.pm_packet, DEFAULT_PM_PACKET)

    lane_payload = load_dict(lane_path)
    shadow_payload = load_dict(shadow_path)
    pm_payload = load_dict(pm_path)

    lane = active_lane_summary(lane_payload)
    shadow = shadow_summary(shadow_payload)
    pm = pm_summary(pm_payload)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Local PM parallel-operator visibility over lane register, WF73 shadow metrics, and PM packet.",
        "sources": {
            "lane_register": source_state(lane_path, lane_payload),
            "wf73_shadow_metrics": source_state(shadow_path, shadow_payload),
            "pm_control_packet": source_state(pm_path, pm_payload),
        },
        "lane_register": lane,
        "shadow_metrics": shadow,
        "pm_packet": pm,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    validation = validate_payload(
        payload,
        {
            "lane_register": lane_payload,
            "wf73_shadow_metrics": shadow_payload,
            "pm_control_packet": pm_payload,
        },
    )
    payload["validation"] = validation
    payload["status"] = validation["status"]
    payload["next_safe_action"] = next_safe_action(lane, pm, validation)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane-register", default=str(DEFAULT_LANE_REGISTER))
    parser.add_argument("--shadow-metrics", default=str(DEFAULT_SHADOW_METRICS))
    parser.add_argument("--pm-packet", default=str(DEFAULT_PM_PACKET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--closeout-out", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    out_path = workspace_path(args.out, DEFAULT_OUT)
    if args.write:
        atomic_write_json(out_path, payload)
        if args.closeout_out:
            atomic_write_json(workspace_path(args.closeout_out, Path(args.closeout_out)), payload)
    print(
        f"parallel_operator_visibility status={payload['status']} "
        f"active_lanes={payload['lane_register']['active_lane_count']} "
        f"active_write_leases={payload['lane_register']['active_write_lease_count_from_register']} "
        f"pm_ready={payload['pm_packet'].get('ready_job_count')} "
        f"pm_blocked={payload['pm_packet'].get('blocked_job_count')}"
    )
    if args.validate and payload["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
