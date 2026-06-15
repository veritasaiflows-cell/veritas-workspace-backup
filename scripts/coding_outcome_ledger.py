#!/usr/bin/env python3
"""Build a durable coding outcome ledger from the lane register.

This is the coding analogue to the finance outcome ledger: it records
completed implementation lanes, their proof artifacts, validation proxy state,
and later-review placeholders. It is review-only and never grants execution,
config, finance, portfolio, account, or cleanup authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "tmp" / "concurrent-lane-register.json"
CHANGED_ROUTER = ROOT / "tmp" / "changed-file-validator-router.json"
LEDGER = ROOT / "data" / "state-history" / "coding-outcome-ledger.jsonl"
CURRENT = ROOT / "tmp" / "coding-outcome-ledger-current.json"

SCHEMA = "veritas.coding_outcome_ledger.v1"
CURRENT_SCHEMA = "veritas.coding_outcome_ledger_current.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "coding_outcome_tracking_only": True,
    "append_only": True,
    "spawns_helpers": False,
    "scheduler_allowed": False,
    "autonomous_execution_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": str(exc), "_line_number": line_number})
            continue
        rows.append(value if isinstance(value, dict) else {"_parse_error": "row is not an object", "_line_number": line_number})
    return rows


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_id_for_lane(lane: dict[str, Any]) -> str:
    lane_id = str(lane.get("lane_id") or "")
    completed = str(lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc") or "")
    digest = hashlib.sha256(f"{lane_id}|{completed}".encode("utf-8")).hexdigest()[:16]
    return f"coding_{digest}"


def duration_minutes(lane: dict[str, Any]) -> float | None:
    start = parse_utc(lane.get("started_at_utc") or lane.get("created_at_utc"))
    end = parse_utc(lane.get("ended_at_utc") or lane.get("completed_at_utc") or lane.get("updated_at_utc"))
    if not start or not end or end < start:
        return None
    return round((end - start).total_seconds() / 60.0, 2)


def lane_kind(lane: dict[str, Any]) -> str:
    writes = [str(item).replace("\\", "/") for item in as_list(lane.get("allowed_writes"))]
    if any(path.startswith("scripts/") for path in writes):
        return "script_or_validator_implementation"
    if any(path.startswith("state/workflows/") or "Project Continuity/" in path for path in writes):
        return "workflow_control_implementation"
    if any(path.startswith("tmp/") for path in writes):
        return "proof_artifact_lane"
    return "coordination_or_note_lane"


def validation_proxy(changed_router: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(changed_router.get("summary"))
    validation = as_dict(changed_router.get("validation"))
    return {
        "source": rel(CHANGED_ROUTER),
        "status": changed_router.get("status"),
        "validation_status": validation.get("status"),
        "recommended_budget": summary.get("recommended_budget"),
        "changed_path_count": summary.get("changed_path_count"),
        "recommendation_count": summary.get("recommendation_count"),
        "validator_passed": changed_router.get("status") == "ok" and validation.get("status") in {None, "ok"},
    }


def runtime_stamp(lane: dict[str, Any]) -> dict[str, Any]:
    runtime = as_dict(lane.get("runtime"))
    lane_id = str(lane.get("lane_id") or "")
    started = str(lane.get("started_at_utc") or lane.get("created_at_utc") or "")
    completed = str(lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc") or "")
    model_path = runtime.get("model_path") or lane.get("model_path")
    provider = None
    if isinstance(model_path, str) and "/" in model_path:
        provider = model_path.split("/", 1)[0]
    return {
        "run_id": runtime.get("run_id") or stable_run_id(lane_id, started, completed),
        "session_id": runtime.get("session_id") or lane.get("session_id"),
        "session_key": runtime.get("session_key") or lane.get("session_key"),
        "session_label": runtime.get("session_label") or lane.get("owner"),
        "task_name": runtime.get("task_name") or lane.get("workstream_id"),
        "model_path": model_path,
        "model_provider": runtime.get("model_provider") or provider,
        "model_attributed": bool(model_path),
        "session_attributed": bool(runtime.get("session_id") or runtime.get("session_key") or runtime.get("session_label")),
    }


def stable_run_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return f"run_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def edit_churn(writes: list[str]) -> dict[str, Any]:
    normalized = [item.replace("\\", "/") for item in writes]
    return {
        "allowed_write_count": len(normalized),
        "script_write_count": sum(1 for item in normalized if item.startswith("scripts/")),
        "test_write_count": sum(1 for item in normalized if item.startswith("scripts/test_")),
        "tmp_artifact_write_count": sum(1 for item in normalized if item.startswith("tmp/")),
        "memory_write_count": sum(1 for item in normalized if item.startswith("memory/")),
        "state_or_data_write_count": sum(1 for item in normalized if item.startswith("state/") or item.startswith("data/")),
    }


def retry_count(lane: dict[str, Any]) -> int:
    runtime = as_dict(lane.get("runtime"))
    explicit = runtime.get("retry_count") if runtime.get("retry_count") is not None else lane.get("retry_count")
    try:
        return max(0, int(explicit))
    except (TypeError, ValueError):
        return 0


def build_record(lane: dict[str, Any], changed_router: dict[str, Any]) -> dict[str, Any]:
    proofs = [str(item) for item in as_list(lane.get("proof_artifacts")) if str(item).strip()]
    acceptance = [str(item) for item in as_list(lane.get("acceptance_commands")) if str(item).strip()]
    writes = [str(item) for item in as_list(lane.get("allowed_writes")) if str(item).strip()]
    stamp = runtime_stamp(lane)
    proxy = validation_proxy(changed_router)
    return {
        "schema": SCHEMA,
        "event_id": event_id_for_lane(lane),
        "recorded_at_utc": utc_now(),
        "run_id": stamp["run_id"],
        "session_id": stamp["session_id"],
        "session_key": stamp["session_key"],
        "session_label": stamp["session_label"],
        "task_name": stamp["task_name"],
        "model_path": stamp["model_path"],
        "model_provider": stamp["model_provider"],
        "workflow_id": lane.get("workflow_id"),
        "lane_id": lane.get("lane_id"),
        "workstream_id": lane.get("workstream_id"),
        "owner": lane.get("owner"),
        "lane_status": lane.get("status"),
        "lane_kind": lane_kind(lane),
        "created_at_utc": lane.get("created_at_utc"),
        "started_at_utc": lane.get("started_at_utc"),
        "completed_at_utc": lane.get("completed_at_utc") or lane.get("ended_at_utc"),
        "duration_minutes": duration_minutes(lane),
        "allowed_write_count": len(writes),
        "allowed_writes": writes,
        "acceptance_command_count": len(acceptance),
        "acceptance_commands": acceptance,
        "proof_artifact_count": len(proofs),
        "proof_artifacts": proofs,
        "coding_outcome": {
            "implementation_completed": lane.get("status") == "complete",
            "proof_attached": bool(proofs),
            "acceptance_commands_declared": bool(acceptance),
            "validator_proxy_passed": proxy.get("validator_passed"),
            "retry_count": retry_count(lane),
            "edit_churn": edit_churn(writes),
            "rework_required": None,
            "regression_observed": None,
            "later_review_status": "pending_later_regression_review",
        },
        "attribution": {
            "run_id_present": bool(stamp["run_id"]),
            "session_present": bool(stamp["session_attributed"]),
            "model_present": bool(stamp["model_attributed"]),
            "producer_present": True,
        },
        "validation_proxy": proxy,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Coding ledger rows are tracking evidence only.",
            "No helper spawn, scheduler, config/runtime mutation, destructive cleanup, finance canon mutation, capital action, or trade authority.",
        ],
    }


def completed_lanes(register: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        lane for lane in as_list(register.get("lanes"))
        if isinstance(lane, dict) and lane.get("status") == "complete" and lane.get("lane_id")
    ]


def append_new_records(records: list[dict[str, Any]], ledger_path: Path) -> dict[str, Any]:
    existing = load_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    appended: list[str] = []
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        for record in records:
            event_id = str(record.get("event_id") or "")
            if not event_id or event_id in existing_ids:
                continue
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            appended.append(event_id)
            existing_ids.add(event_id)
    return {
        "status": "ok",
        "ledger": rel(ledger_path),
        "candidate_count": len(records),
        "appended_count": len(appended),
        "skipped_existing_count": len(records) - len(appended),
        "appended_event_ids": appended,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [row for row in rows if not row.get("_parse_error")]
    by_workflow: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for row in clean:
        workflow = str(row.get("workflow_id") or "UNKNOWN")
        kind = str(row.get("lane_kind") or "unknown")
        by_workflow[workflow] = by_workflow.get(workflow, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "ledger_row_count": len(clean),
        "parse_error_count": len(rows) - len(clean),
        "workflow_counts": dict(sorted(by_workflow.items())),
        "lane_kind_counts": dict(sorted(by_kind.items())),
        "run_attributed_count": sum(1 for row in clean if row.get("run_id")),
        "session_attributed_count": sum(1 for row in clean if as_dict(row.get("attribution")).get("session_present") is True),
        "model_attributed_count": sum(1 for row in clean if as_dict(row.get("attribution")).get("model_present") is True),
        "proof_attached_count": sum(1 for row in clean if as_dict(row.get("coding_outcome")).get("proof_attached") is True),
        "acceptance_declared_count": sum(1 for row in clean if as_dict(row.get("coding_outcome")).get("acceptance_commands_declared") is True),
        "validator_proxy_passed_count": sum(1 for row in clean if as_dict(row.get("coding_outcome")).get("validator_proxy_passed") is True),
        "total_retry_count": sum(int(as_dict(row.get("coding_outcome")).get("retry_count") or 0) for row in clean),
        "rework_required_count": sum(1 for row in clean if as_dict(row.get("coding_outcome")).get("rework_required") is True),
        "regression_observed_count": sum(1 for row in clean if as_dict(row.get("coding_outcome")).get("regression_observed") is True),
    }


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def validate_current(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if authority_true_paths(payload):
        errors.append("authority_drift_detected")
    register_validation = as_dict(as_dict(payload.get("source_statuses")).get("lane_register_validation"))
    if register_validation.get("errors"):
        warnings.append("source_lane_register_has_validation_errors")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_current(register_path: Path, changed_router_path: Path, ledger_path: Path, append_report: dict[str, Any] | None = None) -> dict[str, Any]:
    register = as_dict(load_json(register_path))
    changed_router = as_dict(load_json(changed_router_path))
    records = [build_record(lane, changed_router) for lane in completed_lanes(register)]
    ledger_rows = load_jsonl(ledger_path)
    payload = {
        "schema": CURRENT_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only coding outcome scoreboard from completed implementation lanes.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "lane_register": rel(register_path),
            "changed_file_validator_router": rel(changed_router_path),
            "durable_ledger": rel(ledger_path),
        },
        "source_statuses": {
            "lane_register_status": register.get("status"),
            "lane_register_validation": register.get("validation"),
            "changed_file_validator_router_status": changed_router.get("status"),
        },
        "current_register_summary": register.get("summary"),
        "candidate_completed_lane_count": len(records),
        "last_append_report": append_report,
        "ledger_summary": summarize_rows(ledger_rows),
        "recent_records": ledger_rows[-10:],
        "next_safe_action": "Use this ledger to review coding rework/regression over time; do not treat a clean validator as proof of long-term correctness.",
        "stop_lines": [
            "Review-only coding metrics.",
            "No config/runtime mutation, destructive cleanup, finance canon mutation, trading, account, or approval authority.",
        ],
    }
    payload["validation"] = validate_current(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=REGISTER)
    parser.add_argument("--changed-router", type=Path, default=CHANGED_ROUTER)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--current", type=Path, default=CURRENT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    register_path = abs_path(args.register)
    changed_router_path = abs_path(args.changed_router)
    ledger_path = abs_path(args.ledger)
    current_path = abs_path(args.current)

    register = as_dict(load_json(register_path))
    changed_router = as_dict(load_json(changed_router_path))
    records = [build_record(lane, changed_router) for lane in completed_lanes(register)]
    append_report = append_new_records(records, ledger_path) if args.write else None
    current = build_current(register_path, changed_router_path, ledger_path, append_report)
    if args.write:
        atomic_write_json(current_path, current)
    print(
        "status={status} validation={validation} ledger_rows={rows} appended={appended} out={out}".format(
            status=current["status"],
            validation=current["validation"]["status"],
            rows=current["ledger_summary"]["ledger_row_count"],
            appended=(append_report or {}).get("appended_count"),
            out=rel(current_path) if args.write else None,
        )
    )
    if args.validate and current["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
