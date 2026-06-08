#!/usr/bin/env python3
"""Build the consolidated PM control packet.

This is the primary low-overhead PM operating surface. It builds PM state,
implementation queue, heartbeat candidates, and main-session handoff in memory,
then writes one combined packet for routine lookup. Legacy sidecars are
explicit compatibility/debug outputs only.

Review-only: no helper spawning, workflow execution, customer/external
delivery, SQL import, canon/portfolio mutation, paper/live/account action, or
owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import heartbeat_continuation_candidates as heartbeat
import pm_implementation_job_queue as job_queue
import pm_main_session_handoff as handoff
import pm_program_state
from pm_main_session_handoff import build_handoff_from_payloads
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "pm-control-packet.json"
DEFAULT_DB = TMP / "pm-control-packet.sqlite"
DEFAULT_LEDGER = TMP / "pm-dispatch-ledger.json"

SCHEMA = "veritas.pm_control_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "coordination_packet_only": True,
    "executes_work": False,
    "spawns_helpers": False,
    "heartbeat_executes_work": False,
    "heartbeat_spawns_helpers": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
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


def workspace_path(value: str, default: Path) -> Path:
    path = Path(value) if value else default
    return path if path.is_absolute() else ROOT / path


def queue_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        pm_state=str(pm_program_state.PROGRAM_STATE_JSON),
        pm_actions=str(pm_program_state.NEXT_ACTIONS_JSON),
        cron_candidates=args.cron_candidates,
        helper_packets=args.helper_packets,
        max_pm_jobs=args.max_pm_jobs,
        max_cron_jobs=args.max_cron_jobs,
        out=str(job_queue.DEFAULT_OUT),
        db=str(job_queue.DEFAULT_DB),
        write=False,
        write_db=False,
        validate=False,
    )


def write_pm_legacy(program: dict[str, Any], write_db: bool, db_path: Path) -> dict[str, Any] | None:
    scoreboard, next_actions, blocker_register = pm_program_state.derived_packets(program)
    atomic_write_json(pm_program_state.PROGRAM_STATE_JSON, program)
    atomic_write_json(pm_program_state.LANE_SCOREBOARD_JSON, scoreboard)
    atomic_write_json(pm_program_state.NEXT_ACTIONS_JSON, next_actions)
    atomic_write_json(pm_program_state.BLOCKER_REGISTER_JSON, blocker_register)
    if write_db:
        return pm_program_state.rebuild_sqlite(program, db_path)
    return None


def write_queue_legacy(payload: dict[str, Any], write_db: bool, db_path: Path) -> dict[str, Any] | None:
    atomic_write_json(job_queue.DEFAULT_OUT, payload)
    if write_db:
        return job_queue.rebuild_sqlite(payload, db_path)
    return None


def write_heartbeat_legacy(payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["out"] = rel(heartbeat.DEFAULT_OUT)
    heartbeat.write_json(heartbeat.DEFAULT_OUT, payload)


def write_handoff_legacy(payload: dict[str, Any], ledger_path: Path) -> dict[str, Any]:
    atomic_write_json(handoff.DEFAULT_OUT, payload)
    ledger = handoff.update_ledger(ledger_path, payload)
    atomic_write_json(ledger_path, ledger)
    return ledger


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = utc_now()
    pm_db_path = workspace_path(args.pm_db, pm_program_state.DEFAULT_DB)
    queue_db_path = workspace_path(args.queue_db, job_queue.DEFAULT_DB)
    ledger_path = workspace_path(args.dispatch_ledger, DEFAULT_LEDGER)
    out_path = workspace_path(args.out, DEFAULT_OUT)
    control_db_path = workspace_path(args.db, DEFAULT_DB)

    program = pm_program_state.build_program_state()
    pm_db_result = write_pm_legacy(program, args.write_legacy_db, pm_db_path) if args.write_compat else None

    actions_payload = {
        "schema": program.get("schema"),
        "status": program.get("status"),
        "generated_at_utc": program.get("generated_at_utc"),
        "next_actions": program.get("next_actions", []),
    }
    q_args = queue_args(args)
    q_args.pm_state_payload = program
    q_args.pm_actions_payload = actions_payload
    queue_payload = job_queue.build_payload(q_args)
    queue_db_result = write_queue_legacy(queue_payload, args.write_legacy_db, queue_db_path) if args.write_compat else None

    review_path = workspace_path(args.review, heartbeat.DEFAULT_REVIEW)
    index_path = workspace_path(args.index, heartbeat.DEFAULT_INDEX)
    heartbeat_payload = heartbeat.build_payload(review_path, index_path, pm_program_state.PROGRAM_STATE_JSON)
    heartbeat_payload["pm_program_state"] = {
        "available": bool(program),
        "status": program.get("status"),
        "generated_at_utc": program.get("generated_at_utc"),
        "readiness": program.get("readiness"),
        "top_next_action": as_list(program.get("next_actions"))[0] if as_list(program.get("next_actions")) else {},
        "heartbeat_boundary": (
            "PM state may inform or queue bounded main-session review only; "
            "heartbeat must not execute PM next actions inline."
        ),
    }
    if args.write_compat:
        write_heartbeat_legacy(heartbeat_payload)

    handoff_payload = build_handoff_from_payloads(
        actions_payload,
        program,
        heartbeat_payload,
        queue_payload,
        ledger_path,
        args.cooldown_hours,
    )
    ledger = write_handoff_legacy(handoff_payload, ledger_path) if args.write_compat else handoff.read_ledger(ledger_path)

    validations = {
        "pm_program_state": as_dict(program.get("validation")).get("status"),
        "pm_implementation_job_queue": as_dict(queue_payload.get("validation")).get("status"),
        "heartbeat_continuation_candidates": as_dict(heartbeat_payload.get("validation")).get("status"),
        "pm_main_session_handoff": as_dict(handoff_payload.get("validation")).get("status"),
        "pm_program_state_sqlite": as_dict(pm_db_result).get("status") if pm_db_result else None,
        "pm_implementation_job_queue_sqlite": as_dict(queue_db_result).get("status") if queue_db_result else None,
    }
    control_db_result = rebuild_sqlite_stub(
        control_db_path,
        program,
        queue_payload,
        heartbeat_payload,
        handoff_payload,
    ) if args.write_db else None
    if control_db_result:
        validations["pm_control_packet_sqlite"] = control_db_result.get("status")

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "draft",
        "purpose": "Single PM operating packet combining PM state, PM implementation queue, heartbeat candidates, and main-session handoff.",
        "primary_output": rel(out_path),
        "compatibility_sidecars": {
            "written": bool(args.write_compat),
            "write_rule": "Legacy sidecars are written only with --write-compat for old dashboards/debugging.",
            "paths": {
                "pm_program_state": rel(pm_program_state.PROGRAM_STATE_JSON),
                "pm_lane_scoreboard": rel(pm_program_state.LANE_SCOREBOARD_JSON),
                "pm_next_actions": rel(pm_program_state.NEXT_ACTIONS_JSON),
                "pm_blocker_register": rel(pm_program_state.BLOCKER_REGISTER_JSON),
                "pm_implementation_job_queue": rel(job_queue.DEFAULT_OUT),
                "heartbeat_continuation_candidates": rel(heartbeat.DEFAULT_OUT),
                "pm_main_session_handoff": rel(handoff.DEFAULT_OUT),
                "pm_dispatch_ledger": rel(ledger_path),
            },
        },
        "sqlite_outputs": {
            "pm_program_state": pm_db_result,
            "pm_implementation_job_queue": queue_db_result,
            "pm_control_packet": control_db_result,
        },
        "summary": {
            "pm_status": program.get("status"),
            "pm_readiness": program.get("readiness"),
            "next_action_count": len(as_list(program.get("next_actions"))),
            "top_next_action": as_list(program.get("next_actions"))[0] if as_list(program.get("next_actions")) else {},
            "implementation_queue": queue_payload.get("summary"),
            "heartbeat": {
                "status": heartbeat_payload.get("status"),
                "candidate_count": heartbeat_payload.get("candidate_count"),
                "handoff_ready_count": heartbeat_payload.get("handoff_ready_count"),
                "blocked_count": heartbeat_payload.get("blocked_count"),
                "skipped_owner_paused": heartbeat_payload.get("skipped_owner_paused", []),
            },
            "main_session_handoff": {
                "status": handoff_payload.get("status"),
                "selected_action": as_dict(handoff_payload.get("selected_action")).get("action_id"),
                "selected_lane": as_dict(handoff_payload.get("selected_action")).get("lane_id"),
                "signal_class": as_dict(handoff_payload.get("signal_classification")).get("class"),
            },
        },
        "sections": {
            "pm_program_state": program,
            "pm_implementation_job_queue": queue_payload,
            "heartbeat_continuation_candidates": heartbeat_payload,
            "pm_main_session_handoff": handoff_payload,
        },
        "dispatch_ledger_latest": as_dict(ledger).get("latest"),
        "recommended_use": {
            "first_read": rel(out_path),
            "regenerate": "python scripts\\pm_control_packet.py --write --write-db --validate",
            "legacy_rule": "Legacy PM/heartbeat JSONs are opt-in compatibility sidecars; routine PM lookup must start from this packet.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": validate_packet(validations, program, queue_payload, heartbeat_payload, handoff_payload),
    }
    packet["status"] = "ok" if packet["validation"]["status"] == "ok" else "blocked"
    return packet


def validate_packet(
    validations: dict[str, Any],
    program: dict[str, Any],
    queue_payload: dict[str, Any],
    heartbeat_payload: dict[str, Any],
    handoff_payload: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = {
        "pm_program_state": "ok",
        "pm_implementation_job_queue": "ok",
        "heartbeat_continuation_candidates": "ok",
        "pm_main_session_handoff": "ok",
    }
    for key, value in expected.items():
        if validations.get(key) != value:
            errors.append(f"{key}_validation_not_ok:{validations.get(key)}")
    for key in ("pm_program_state_sqlite", "pm_implementation_job_queue_sqlite", "pm_control_packet_sqlite"):
        if validations.get(key) not in {None, "ok"}:
            errors.append(f"{key}_not_ok:{validations.get(key)}")
    if as_dict(heartbeat_payload.get("heartbeat_authority")).get("may_directly_advance_workflow_queue") is not False:
        errors.append("heartbeat_queue_execution_widened")
    for item in as_list(heartbeat_payload.get("candidates")):
        if as_dict(item).get("may_spawn_helper_from_heartbeat") is not False:
            errors.append(f"heartbeat_helper_spawn_widened:{item.get('workflow_id')}")
    if as_dict(handoff_payload.get("signal_classification")).get("heartbeat_may_execute") is not False:
        errors.append("handoff_heartbeat_execution_widened")
    if as_dict(queue_payload.get("authority_boundary")).get("cron_or_heartbeat_may_execute") is not False:
        errors.append("queue_cron_or_heartbeat_execution_widened")
    if program.get("status") != "ok":
        warnings.append(f"pm_program_state_status:{program.get('status')}")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
        "component_validation": validations,
    }


def rebuild_sqlite_stub(
    db_path: Path,
    program: dict[str, Any],
    queue_payload: dict[str, Any],
    heartbeat_payload: dict[str, Any],
    handoff_payload: dict[str, Any],
) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript(
            """
            DROP TABLE IF EXISTS pm_control_summary;
            DROP TABLE IF EXISTS pm_control_actions;
            DROP TABLE IF EXISTS pm_control_jobs;
            DROP TABLE IF EXISTS pm_control_heartbeat;
            CREATE TABLE pm_control_summary (
              key TEXT PRIMARY KEY,
              value TEXT
            );
            CREATE TABLE pm_control_actions (
              rank INTEGER PRIMARY KEY,
              action_id TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              status TEXT NOT NULL,
              action_type TEXT NOT NULL,
              description TEXT NOT NULL
            );
            CREATE TABLE pm_control_jobs (
              rank INTEGER PRIMARY KEY,
              job_id TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              status TEXT NOT NULL,
              validation_budget TEXT,
              closeout_mode TEXT
            );
            CREATE TABLE pm_control_heartbeat (
              workflow_id TEXT PRIMARY KEY,
              workflow_name TEXT,
              status TEXT NOT NULL,
              heartbeat_action TEXT
            );
            """
        )
        summary = {
            "pm_status": program.get("status"),
            "readiness_band": as_dict(program.get("readiness")).get("readiness_band"),
            "job_count": as_dict(queue_payload.get("summary")).get("job_count"),
            "ready_job_count": as_dict(queue_payload.get("summary")).get("ready_job_count"),
            "heartbeat_candidate_count": heartbeat_payload.get("candidate_count"),
            "handoff_status": handoff_payload.get("status"),
            "selected_action": as_dict(handoff_payload.get("selected_action")).get("action_id"),
        }
        for key, value in summary.items():
            conn.execute("INSERT INTO pm_control_summary VALUES (?, ?)", (key, json.dumps(value)))
        for action in as_list(program.get("next_actions")):
            conn.execute(
                "INSERT INTO pm_control_actions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(action.get("rank") or 9999),
                    str(action.get("action_id")),
                    str(action.get("lane_id")),
                    str(action.get("lane_status")),
                    str(action.get("action_type")),
                    str(action.get("description")),
                ),
            )
        for job in as_list(queue_payload.get("jobs")):
            budget = as_dict(job.get("validation_budget")).get("budget")
            conn.execute(
                "INSERT INTO pm_control_jobs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(job.get("rank") or 9999),
                    str(job.get("job_id")),
                    str(job.get("lane_id")),
                    str(job.get("status")),
                    str(budget),
                    str(job.get("closeout_mode")),
                ),
            )
        for candidate in as_list(heartbeat_payload.get("candidates")):
            conn.execute(
                "INSERT INTO pm_control_heartbeat VALUES (?, ?, ?, ?)",
                (
                    str(candidate.get("workflow_id")),
                    str(candidate.get("workflow_name")),
                    str(candidate.get("status")),
                    str(candidate.get("heartbeat_action")),
                ),
            )
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            "pm_control_summary": conn.execute("SELECT COUNT(*) FROM pm_control_summary").fetchone()[0],
            "pm_control_actions": conn.execute("SELECT COUNT(*) FROM pm_control_actions").fetchone()[0],
            "pm_control_jobs": conn.execute("SELECT COUNT(*) FROM pm_control_jobs").fetchone()[0],
            "pm_control_heartbeat": conn.execute("SELECT COUNT(*) FROM pm_control_heartbeat").fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "db_path": rel(db_path),
        "status": "ok" if integrity == "ok" else "blocked",
        "integrity_check": integrity,
        "table_counts": counts,
        "authority_boundary": "Derived PM control lookup only; JSON remains review-only proof.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build consolidated review-only PM control packet.")
    parser.add_argument("--write", action="store_true", help="Write PM control packet.")
    parser.add_argument("--write-compat", action="store_true", help="Also write legacy PM/queue/heartbeat/handoff sidecars.")
    parser.add_argument("--write-db", action="store_true", help="Rebuild consolidated SQLite index.")
    parser.add_argument("--write-legacy-db", action="store_true", help="With --write-compat, also rebuild legacy PM and queue SQLite indexes.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero when validation fails.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--pm-db", default=str(pm_program_state.DEFAULT_DB))
    parser.add_argument("--queue-db", default=str(job_queue.DEFAULT_DB))
    parser.add_argument("--review", default=str(heartbeat.DEFAULT_REVIEW))
    parser.add_argument("--index", default=str(heartbeat.DEFAULT_INDEX))
    parser.add_argument("--cron-candidates", default=str(job_queue.DEFAULT_CRON_CANDIDATES))
    parser.add_argument("--helper-packets", default=str(job_queue.DEFAULT_HELPER_PACKETS))
    parser.add_argument("--dispatch-ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--max-pm-jobs", type=int, default=10)
    parser.add_argument("--max-cron-jobs", type=int, default=4)
    parser.add_argument("--cooldown-hours", type=float, default=handoff.DEFAULT_DISPATCH_COOLDOWN_HOURS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = workspace_path(args.out, DEFAULT_OUT)
    packet = build_packet(args)
    if args.write:
        atomic_write_json(out_path, packet)
    print(json.dumps({
        "status": packet.get("status"),
        "out": rel(out_path),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
