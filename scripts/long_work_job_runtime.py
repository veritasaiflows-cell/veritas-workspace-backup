#!/usr/bin/env python3
"""Shared runtime contract for resumable long local jobs.

This is the runtime companion to long_work_packet_linter.py. The linter checks
whether a long-work plan is shaped correctly; this module records the actual
job status, checkpoints, and resume commands so long local work can survive
tool timeouts, compaction, model changes, and new sessions.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "long-work-jobs"
TMP = ROOT / "tmp"
SCHEMA = "veritas.long_work_job_status.v1"
PACKET_SCHEMA = "veritas.long_work_job_status_packet.v1"

TERMINAL_STATUSES = {"complete", "warning", "blocked", "cancelled"}
ACTIVE_STATUSES = {"created", "running", "paused", "resumable"}
VALID_STATUSES = TERMINAL_STATUSES | ACTIVE_STATUSES

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runtime_status_only": True,
    "checkpoint_resume_only": True,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_or_source_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "delete_archive_or_move_allowed": False,
    "model_training_claim_allowed": False,
    "raw_prompt_or_tool_capture_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_job_id(job_id: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(job_id).strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    if not cleaned:
        raise ValueError("job_id cannot be empty")
    return cleaned


def job_dir(job_id: str) -> Path:
    return STATE / normalize_job_id(job_id)


def status_path(job_id: str) -> Path:
    return job_dir(job_id) / "status.json"


def event_log_path(job_id: str) -> Path:
    return job_dir(job_id) / "events.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_status(job_id: str) -> dict[str, Any]:
    return load_json(status_path(job_id))


def compact_status(status: dict[str, Any]) -> dict[str, Any]:
    progress = as_dict(status.get("progress"))
    validation = as_dict(status.get("validation"))
    return {
        "job_id": status.get("job_id"),
        "status": status.get("status"),
        "owner_workflow": status.get("owner_workflow"),
        "job_type": status.get("job_type"),
        "profile": status.get("profile"),
        "processed_units": progress.get("processed_units"),
        "total_units": progress.get("total_units"),
        "remaining_units": progress.get("remaining_units"),
        "percent_complete": progress.get("percent_complete"),
        "validation_status": validation.get("status"),
        "last_heartbeat_utc": status.get("last_heartbeat_utc"),
        "next_resume_command": status.get("next_resume_command"),
    }


def new_status(
    *,
    job_id: str,
    owner_workflow: str,
    job_type: str,
    profile: str,
    command_contract: dict[str, Any],
    paths: dict[str, Any],
    total_units: int = 0,
    input_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    status = {
        "schema": SCHEMA,
        "job_id": normalize_job_id(job_id),
        "owner_workflow": owner_workflow,
        "job_type": job_type,
        "profile": profile,
        "status": "created",
        "created_at_utc": now,
        "updated_at_utc": now,
        "started_at_utc": None,
        "completed_at_utc": None,
        "last_heartbeat_utc": now,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "command_contract": command_contract,
        "paths": paths,
        "input_snapshot": input_snapshot or {},
        "progress": progress_payload(processed=0, total=total_units),
        "validation": {"status": "not_run", "errors": [], "warnings": []},
        "warnings": [],
        "errors": [],
        "next_resume_command": None,
        "closeout_ready": False,
    }
    status["compact_status"] = compact_status(status)
    return status


def progress_payload(*, processed: int, total: int) -> dict[str, Any]:
    processed = max(0, int(processed))
    total = max(0, int(total))
    remaining = max(0, total - processed)
    percent = round((processed / total) * 100.0, 2) if total else 0.0
    return {
        "processed_units": processed,
        "total_units": total,
        "remaining_units": remaining,
        "percent_complete": percent,
    }


def write_status(status: dict[str, Any], *, event: str | None = None) -> dict[str, Any]:
    status = dict(status)
    job_id = normalize_job_id(str(status.get("job_id") or ""))
    status["job_id"] = job_id
    status["schema"] = SCHEMA
    status["updated_at_utc"] = utc_now()
    if status.get("status") in ACTIVE_STATUSES:
        status["last_heartbeat_utc"] = status["updated_at_utc"]
    if status.get("status") in TERMINAL_STATUSES and not status.get("completed_at_utc"):
        status["completed_at_utc"] = status["updated_at_utc"]
    status["compact_status"] = compact_status(status)
    atomic_write_json(status_path(job_id), status)
    if event:
        append_event(job_id, event, status=status)
    return status


def append_event(job_id: str, event: str, *, status: dict[str, Any] | None = None, detail: dict[str, Any] | None = None) -> None:
    path = event_log_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at_utc": utc_now(),
        "job_id": normalize_job_id(job_id),
        "event": event,
        "status": (status or {}).get("status"),
        "detail": detail or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def validate_status(status: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if status.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    for field in ("job_id", "owner_workflow", "job_type", "profile", "status", "created_at_utc", "updated_at_utc"):
        if not status.get(field):
            errors.append(f"missing_required_field:{field}")
    if status.get("status") not in VALID_STATUSES:
        errors.append(f"invalid_status:{status.get('status')}")
    progress = as_dict(status.get("progress"))
    processed = int(progress.get("processed_units") or 0)
    total = int(progress.get("total_units") or 0)
    if processed < 0 or total < 0 or processed > total:
        errors.append("invalid_progress_counts")
    boundary = as_dict(status.get("authority_boundary"))
    forbidden_true = [
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "sql_or_source_mutation_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_output_allowed",
        "delete_archive_or_move_allowed",
        "raw_prompt_or_tool_capture_allowed",
        "owner_approval_inferred",
    ]
    for key in forbidden_true:
        if boundary.get(key) is True:
            errors.append(f"authority_boundary_forbidden_true:{key}")
    if status.get("status") in {"paused", "resumable", "running", "blocked"} and not status.get("next_resume_command"):
        warnings.append("active_or_blocked_job_missing_next_resume_command")
    validation = as_dict(status.get("validation"))
    if validation.get("status") in {"blocked", "error"}:
        errors.append(f"job_validation_{validation.get('status')}")
    elif validation.get("status") == "warning":
        warnings.append("job_validation_warning")
    if status.get("status") == "complete" and validation.get("status") not in {"ok", "warning"}:
        errors.append("complete_job_missing_clean_validation")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def list_statuses() -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    if not STATE.exists():
        return statuses
    for path in sorted(STATE.glob("*/status.json")):
        data = load_json(path)
        if data:
            statuses.append(data)
    return statuses


def summarize_statuses(statuses: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    stale: list[str] = []
    resumable: list[str] = []
    blocked: list[str] = []
    now = datetime.now(timezone.utc)
    for status in statuses:
        state = str(status.get("status") or "unknown")
        counts[state] = counts.get(state, 0) + 1
        job_id = str(status.get("job_id") or "")
        if state in {"paused", "resumable", "blocked"} and status.get("next_resume_command"):
            resumable.append(job_id)
        if state == "blocked":
            blocked.append(job_id)
        heartbeat = parse_utc(status.get("last_heartbeat_utc"))
        if state in ACTIVE_STATUSES and heartbeat is not None:
            age_minutes = (now - heartbeat).total_seconds() / 60.0
            if age_minutes > 30:
                stale.append(job_id)
    active_count = sum(counts.get(state, 0) for state in ACTIVE_STATUSES)
    terminal_count = sum(counts.get(state, 0) for state in TERMINAL_STATUSES)
    return {
        "job_count": len(statuses),
        "active_job_count": active_count,
        "terminal_job_count": terminal_count,
        "resumable_job_count": len(resumable),
        "blocked_job_count": len(blocked),
        "stale_active_job_count": len(stale),
        "status_counts": dict(sorted(counts.items())),
        "resumable_job_ids": resumable,
        "blocked_job_ids": blocked,
        "stale_active_job_ids": stale,
        "next_safe_action": (
            "Resume bounded long jobs with their next_resume_command."
            if resumable
            else "No resumable long jobs are waiting."
        ),
    }


def build_status_packet() -> dict[str, Any]:
    statuses = list_statuses()
    rows = []
    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    for status in statuses:
        validation = validate_status(status)
        if validation["errors"]:
            validation_errors.extend(f"{status.get('job_id')}:{item}" for item in validation["errors"])
        if validation["warnings"]:
            validation_warnings.extend(f"{status.get('job_id')}:{item}" for item in validation["warnings"])
        rows.append({
            "status_path": rel(status_path(str(status.get("job_id")))),
            "compact_status": compact_status(status),
            "validation": validation,
        })
    summary = summarize_statuses(statuses)
    packet = {
        "schema": PACKET_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "long_work_jobs_ready",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "summary": summary,
        "jobs": rows,
        "validation": {
            "status": "blocked" if validation_errors else ("warning" if validation_warnings else "ok"),
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }
    if packet["validation"]["status"] != "ok":
        packet["status"] = "long_work_jobs_warning"
    return packet


def example_status() -> dict[str, Any]:
    return new_status(
        job_id="example-long-work-job",
        owner_workflow="RUNTIME",
        job_type="example",
        profile="example",
        command_contract={
            "start_command": "python scripts\\example.py start --write --validate",
            "resume_command": "python scripts\\example.py resume --max-seconds 240 --write --validate",
            "validate_command": "python scripts\\example.py validate --write --validate",
            "bounded_execution_required": True,
        },
        paths={
            "status": "state/long-work-jobs/example-long-work-job/status.json",
            "checkpoint": "state/long-work-jobs/example-long-work-job/checkpoint.json",
        },
        total_units=10,
        input_snapshot={"source_hash": "example"},
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["example", "list", "status", "validate"])
    parser.add_argument("--job-id")
    parser.add_argument("--out", type=Path, default=TMP / "long-work-job-status-packet.json")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.action == "example":
        payload = example_status()
        payload["validation"] = validate_status(payload)
        if args.write:
            write_status(payload, event="example_written")
    elif args.action == "status":
        if not args.job_id:
            raise SystemExit("--job-id is required for status")
        payload = load_status(args.job_id)
        if not payload:
            payload = {"status": "missing", "job_id": args.job_id, "validation": {"status": "blocked", "errors": ["missing_status"], "warnings": []}}
    elif args.action == "validate":
        if args.job_id:
            payload = load_status(args.job_id)
            payload["validation"] = validate_status(payload)
        else:
            payload = build_status_packet()
    else:
        payload = build_status_packet()

    if args.write and args.action in {"list", "validate"}:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(args.out, payload)
    print(json.dumps(payload if args.pretty else {"status": payload.get("status"), "summary": payload.get("summary"), "validation": payload.get("validation")}, indent=2, sort_keys=True))
    validation = as_dict(payload.get("validation"))
    return 1 if validation.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
