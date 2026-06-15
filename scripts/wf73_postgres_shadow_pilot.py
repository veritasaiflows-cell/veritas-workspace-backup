#!/usr/bin/env python3
"""Build the WF73 Postgres shadow-pilot projection.

This is a zero-service shadow program. It does not connect to Postgres, open a
port, create credentials, or change runtime state. It projects the JSON lane
register into the proposed Postgres table shape so WF73 can measure parity,
row coverage, proof coverage, and future pilot readiness while JSON remains
primary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTER = TMP / "concurrent-lane-register.json"
DEFAULT_OUT = TMP / "wf73-postgres-shadow-pilot.json"
DEFAULT_METRICS = TMP / "wf73-postgres-shadow-pilot-metrics.json"

SCHEMA = "veritas.wf73.postgres_shadow_pilot.v1"
ACTIVE_STATUSES = {"planned", "leased", "running"}
TERMINAL_STATUSES = {"complete", "blocked", "cancelled"}

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "shadow_projection_only": True,
    "json_lane_register_primary": True,
    "postgres_connection_required": False,
    "postgres_service_install_allowed": False,
    "docker_install_or_runtime_change_allowed": False,
    "native_service_change_allowed": False,
    "network_or_port_exposure_allowed": False,
    "credential_or_secret_change_allowed": False,
    "config_or_startup_mutation_allowed": False,
    "sql_execution_allowed": False,
    "sql_first_control_authority_allowed": False,
    "lane_claim_authority_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_out_for_register(register_path: Path) -> Path:
    resolved = register_path.resolve()
    if resolved == DEFAULT_REGISTER.resolve():
        return DEFAULT_OUT
    return register_path.parent / "wf73-postgres-shadow-pilot.json"


def default_metrics_for_out(out_path: Path) -> Path:
    if out_path.resolve() == DEFAULT_OUT.resolve():
        return DEFAULT_METRICS
    return out_path.with_name(out_path.stem + "-metrics.json")


def load_register(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def runtime_session_id(lane: dict[str, Any]) -> str | None:
    runtime = as_dict(lane.get("runtime"))
    value = runtime.get("session_key") or runtime.get("session_id")
    return str(value) if value else None


def build_sessions(lanes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for lane in lanes:
        runtime = as_dict(lane.get("runtime"))
        sid = runtime_session_id(lane)
        if not sid:
            continue
        existing = sessions.get(sid)
        started = lane.get("started_at_utc") or lane.get("created_at_utc") or utc_now()
        updated = lane.get("updated_at_utc") or started
        ended = lane.get("ended_at_utc")
        status = "complete" if lane.get("status") in TERMINAL_STATUSES else "active"
        if existing:
            existing["last_seen_at_utc"] = max(str(existing["last_seen_at_utc"]), str(updated))
            if ended:
                existing["ended_at_utc"] = ended
            if status == "active":
                existing["status"] = "active"
            continue
        sessions[sid] = {
            "session_id": sid,
            "channel": str(runtime.get("session_key") or "").split(":", 1)[0] or "unknown",
            "chat_id": runtime.get("session_key"),
            "message_id": runtime.get("session_id"),
            "session_label": runtime.get("session_label"),
            "task_name": runtime.get("task_name"),
            "agent_name": "veritas-main",
            "model_path": runtime.get("model_path"),
            "model_provider": runtime.get("model_provider"),
            "started_at_utc": started,
            "last_seen_at_utc": updated,
            "ended_at_utc": ended,
            "status": status,
            "metadata_json": {
                "run_id": runtime.get("run_id"),
                "thinking": runtime.get("thinking"),
                "retry_count": runtime.get("retry_count"),
            },
        }
    return sorted(sessions.values(), key=lambda row: row["session_id"])


def build_projection(register: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    sessions = build_sessions(lanes)
    workflow_lanes: list[dict[str, Any]] = []
    file_leases: list[dict[str, Any]] = []
    write_intents: list[dict[str, Any]] = []
    validation_runs: list[dict[str, Any]] = []
    proof_artifacts: list[dict[str, Any]] = []
    closeout_events: list[dict[str, Any]] = []
    lease_heartbeats: list[dict[str, Any]] = []

    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "")
        status = str(lane.get("status") or "")
        active = status in ACTIVE_STATUSES
        session_id = runtime_session_id(lane)
        workflow_lanes.append(
            {
                "lane_id": lane_id,
                "workflow_id": lane.get("workflow_id"),
                "workstream_id": lane.get("workstream_id"),
                "session_id": session_id,
                "owner": lane.get("owner"),
                "status": status,
                "lease_expires_at_utc": lane.get("lease_expires_at_utc"),
                "created_at_utc": lane.get("created_at_utc"),
                "started_at_utc": lane.get("started_at_utc"),
                "updated_at_utc": lane.get("updated_at_utc"),
                "completed_at_utc": lane.get("completed_at_utc"),
                "ended_at_utc": lane.get("ended_at_utc"),
                "summary": "; ".join(str(item) for item in as_list(lane.get("notes"))[-3:]),
                "authority_boundary": lane.get("authority_boundary"),
                "metadata_json": {"mode": lane.get("mode"), "merge_required_by_main": lane.get("merge_required_by_main")},
            }
        )
        if active and session_id:
            lease_heartbeats.append(
                {
                    "heartbeat_id": stable_id("heartbeat", lane_id, lane.get("updated_at_utc")),
                    "lane_id": lane_id,
                    "session_id": session_id,
                    "heartbeat_at_utc": lane.get("updated_at_utc") or utc_now(),
                    "status_note": status,
                }
            )
        for path in [normalize_path(item) for item in as_list(lane.get("allowed_writes")) if str(item).strip()]:
            lease_status = "active" if active else "released"
            lease_id = stable_id("file_lease", lane_id, path)
            file_leases.append(
                {
                    "file_lease_id": lease_id,
                    "lane_id": lane_id,
                    "path": path,
                    "access_mode": "write",
                    "lease_status": lease_status,
                    "lease_expires_at_utc": lane.get("lease_expires_at_utc"),
                    "created_at_utc": lane.get("created_at_utc"),
                    "released_at_utc": lane.get("ended_at_utc") if not active else None,
                    "metadata_json": {},
                }
            )
            write_intents.append(
                {
                    "write_intent_id": stable_id("write_intent", lane_id, path),
                    "lane_id": lane_id,
                    "file_lease_id": lease_id,
                    "path": path,
                    "intent_type": "write",
                    "reason": "lane_allowed_write",
                    "status": "claimed" if active else "applied",
                    "declared_at_utc": lane.get("created_at_utc"),
                    "applied_at_utc": lane.get("ended_at_utc") if not active else None,
                    "metadata_json": {},
                }
            )
        for index, command in enumerate(as_list(lane.get("acceptance_commands"))):
            validation_runs.append(
                {
                    "validation_run_id": stable_id("validation", lane_id, index, command),
                    "lane_id": lane_id,
                    "command": str(command),
                    "status": "skipped",
                    "exit_code": None,
                    "started_at_utc": lane.get("created_at_utc"),
                    "ended_at_utc": None,
                    "summary_json": {"shadow_projection": "declared_command_only"},
                }
            )
        for proof in [normalize_path(item) for item in as_list(lane.get("proof_artifacts")) if str(item).strip()]:
            proof_path = ROOT / proof
            proof_artifacts.append(
                {
                    "proof_artifact_id": stable_id("proof", lane_id, proof),
                    "lane_id": lane_id,
                    "path": proof,
                    "artifact_schema": None,
                    "hash_algorithm": "sha256",
                    "hash_value": sha256_file(proof_path),
                    "proof_role": "lane_closeout",
                    "created_at_utc": lane.get("ended_at_utc") or lane.get("updated_at_utc"),
                    "exists": proof_path.exists(),
                }
            )
        if status in TERMINAL_STATUSES:
            closeout_events.append(
                {
                    "closeout_event_id": stable_id("closeout", lane_id, lane.get("ended_at_utc")),
                    "lane_id": lane_id,
                    "event_type": "complete" if status == "complete" else status,
                    "event_at_utc": lane.get("ended_at_utc") or lane.get("completed_at_utc") or lane.get("updated_at_utc"),
                    "summary": "; ".join(str(item) for item in as_list(lane.get("notes"))[-3:]) or status,
                    "proof_artifact_id": None,
                }
            )

    postgres_health_checks = [
        {
            "health_check_id": stable_id("health", "json_shadow_projection", register.get("generated_at_utc")),
            "checked_at_utc": utc_now(),
            "endpoint": "not_configured",
            "loopback_only": True,
            "db_available": False,
            "json_fallback_available": True,
            "last_pg_dump_at_utc": None,
            "last_restore_test_at_utc": None,
            "status": "ok",
            "summary_json": {
                "mode": "json_shadow_projection",
                "postgres_runtime_dependency": False,
                "postgres_connection_attempted": False,
            },
        }
    ]

    return {
        "sessions": sessions,
        "workflow_lanes": workflow_lanes,
        "file_leases": file_leases,
        "write_intents": write_intents,
        "validation_runs": validation_runs,
        "proof_artifacts": proof_artifacts,
        "closeout_events": closeout_events,
        "lease_heartbeats": lease_heartbeats,
        "postgres_health_checks": postgres_health_checks,
    }


def validate_payload(payload: dict[str, Any], register: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")

    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    projection = as_dict(payload.get("shadow_projection"))
    workflow_rows = as_list(projection.get("workflow_lanes"))
    file_rows = as_list(projection.get("file_leases"))
    proof_rows = as_list(projection.get("proof_artifacts"))
    active_lanes = [lane for lane in lanes if lane.get("status") in ACTIVE_STATUSES]
    active_file_rows = [row for row in file_rows if as_dict(row).get("lease_status") == "active"]
    expected_active_writes = sum(len(as_list(lane.get("allowed_writes"))) for lane in active_lanes)
    missing_proofs = [as_dict(row).get("path") for row in proof_rows if as_dict(row).get("exists") is False]

    if len(workflow_rows) != len(lanes):
        errors.append("workflow_lane_row_count_mismatch")
    if len(active_file_rows) != expected_active_writes:
        errors.append("active_file_lease_count_mismatch")
    if missing_proofs:
        warnings.append(f"missing_proof_artifacts:{len(missing_proofs)}")

    register_validation = as_dict(register.get("validation"))
    if register_validation.get("status") != "ok":
        warnings.append("json_register_validation_not_ok")

    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }


def build_payload(register_path: Path = DEFAULT_REGISTER) -> dict[str, Any]:
    started = time.perf_counter()
    register = load_register(register_path)
    projection = build_projection(register)
    lanes = [lane for lane in as_list(register.get("lanes")) if isinstance(lane, dict)]
    active_lanes = [lane for lane in lanes if lane.get("status") in ACTIVE_STATUSES]
    row_counts = {name: len(rows) for name, rows in projection.items()}
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": "json_shadow_projection",
        "sources": {
            "json_lane_register": rel(register_path),
            "ddl_contract_review": "tmp/wf73-postgres-ddl-contract-review.json",
            "parity_spec_review": "tmp/wf73-postgres-parity-validator-spec-review.json",
            "failure_drills_review": "tmp/wf73-postgres-failure-drills-review.json",
            "go_no_go_review": "tmp/wf73-postgres-go-no-go-review.json",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "shadow_projection": projection,
        "metrics": {
            "json_primary": True,
            "postgres_runtime_dependency": False,
            "postgres_connection_attempted": False,
            "postgres_available": False,
            "shadow_projection_available": True,
            "lane_count": len(lanes),
            "active_lane_count": len(active_lanes),
            "row_counts": row_counts,
            "total_shadow_rows": sum(row_counts.values()),
            "active_write_lease_rows": len([row for row in projection["file_leases"] if row.get("lease_status") == "active"]),
            "proof_rows_with_existing_files": len([row for row in projection["proof_artifacts"] if row.get("exists") is True]),
            "proof_rows_missing_files": len([row for row in projection["proof_artifacts"] if row.get("exists") is False]),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        },
        "operator_recommendation": (
            "Use this as passive WF73 coordination telemetry only. JSON remains primary; "
            "do not promote Postgres or require DB availability without separate owner approval."
        ),
    }
    payload["validation"] = validate_payload(payload, register)
    payload["status"] = "ok" if as_dict(payload.get("validation")).get("status") == "ok" else "warning"
    return payload


def metrics_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf73.postgres_shadow_pilot_metrics.v1",
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "metrics": payload.get("metrics"),
        "validation": payload.get("validation"),
        "authority_boundary": payload.get("authority_boundary"),
    }


def refresh_shadow_pilot(register_path: Path = DEFAULT_REGISTER, out_path: Path | None = None) -> dict[str, Any]:
    out = out_path or default_out_for_register(register_path)
    metrics_out = default_metrics_for_out(out)
    payload = build_payload(register_path)
    atomic_write_json(out, payload)
    atomic_write_json(metrics_out, metrics_payload(payload))
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", default=str(DEFAULT_REGISTER))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--metrics-out", default=str(DEFAULT_METRICS))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    register_path = workspace_path(args.register)
    payload = build_payload(register_path)
    if args.write:
        out = workspace_path(args.out)
        metrics_out = workspace_path(args.metrics_out)
        atomic_write_json(out, payload)
        atomic_write_json(metrics_out, metrics_payload(payload))
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "mode": payload.get("mode"),
                "metrics": payload.get("metrics"),
                "validation": payload.get("validation"),
                "out": rel(workspace_path(args.out)),
                "metrics_out": rel(workspace_path(args.metrics_out)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
