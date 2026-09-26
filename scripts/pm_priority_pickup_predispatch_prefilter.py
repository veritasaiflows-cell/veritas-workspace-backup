#!/usr/bin/env python3
"""Changed-input gate for the PM main-session priority pickup.

The pickup job previously woke Main every 30 minutes to run two deterministic
scripts and read their output.  Measured attribution showed ~28.7k tokens per
dispatch for ~5 output tokens, because nearly every wake concluded that nothing
was actionable.

This gate runs the same two deterministic scripts model-free, reads the proof
they already produce, and wakes Main only when the handoff says a human-review
priority actually exists or a control failed.  The wake carries the same
review-only authority the systemEvent carried; it does not add any.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf89_dispatch_record  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"

OUT = TMP / "pm-priority-pickup-predispatch-prefilter.json"
HISTORY = STATE_HISTORY / "pm-priority-pickup-predispatch-prefilter.jsonl"
HANDOFF = TMP / "main-session-priority-handoff.json"
EXECUTOR_OUT = TMP / "main-session-action-executor.json"

SCHEMA = "veritas.pm_priority_pickup_predispatch_prefilter.v1"
PICKUP_JOB_ID = "c295580b-fd61-4995-9a0e-f876873a5ea4"

# Receipts that mean the handoff changed in a way a human must look at.
WAKE_RECEIPTS = {"NEW_PRIORITY", "ESCALATED_PRIORITY", "BLOCKED"}
QUIET_STATUSES = {"no_priority"}

# Repeat-wake suppression, in hours, keyed by the selected priority level.
# These mirror re_escalation_interval_checks in the handoff itself.
DEFAULT_REESCALATION_HOURS = {"P0": 4, "P1": 8}
FALLBACK_REESCALATION_HOURS = 4

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "may_execute_repair": False,
    "may_spawn_helper": False,
    "may_lease_lane": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

STOP_LINES = [
    "This gate decides whether to wake Main. It never decides a priority disposition.",
    "A suppressed wake is not a closed priority; the handoff still shows it as pending.",
    "The gate may not widen Main's authority; the woken turn is review-only routing.",
]


def utc_now(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def ensure_workspace_path(path: Path) -> Path:
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"path escapes workspace: {path}")
    return resolved


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    resolved = ensure_workspace_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved.with_suffix(resolved.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(resolved)


def append_history(path: Path, record: dict[str, Any]) -> None:
    resolved = ensure_workspace_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def run_step(command: list[str], timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    started_at = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": command[1:],
            "started_at_utc": started_at,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": None,
            "ok": False,
            "error_code": "step_timeout",
            "stderr_tail": "",
        }
    except OSError as exc:
        return {
            "command": command[1:],
            "started_at_utc": started_at,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": None,
            "ok": False,
            "error_code": "step_launch_failed",
            "stderr_tail": str(exc)[-400:],
        }
    return {
        "command": command[1:],
        "started_at_utc": started_at,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "error_code": None if completed.returncode == 0 else "step_nonzero_exit",
        "stderr_tail": (completed.stderr or "")[-400:],
    }


def run_deterministic_steps(timeout_seconds: int) -> list[dict[str, Any]]:
    return [
        run_step(
            [
                sys.executable,
                str(ROOT / "scripts" / "main_session_escalation_consumer.py"),
                "--context",
                "cron",
                "--priority-observation-source",
                "main_session",
                "--write",
                "--validate",
            ],
            timeout_seconds,
        ),
        run_step(
            [
                sys.executable,
                str(ROOT / "scripts" / "main_session_action_executor.py"),
                "--context",
                "cron",
                "--write",
                "--validate",
            ],
            timeout_seconds,
        ),
    ]


def wake_signature(handoff: dict[str, Any]) -> str:
    summary = as_dict(handoff.get("summary"))
    signature = as_dict(handoff.get("input_signature"))
    return "|".join(
        [
            str(handoff.get("status") or ""),
            str(summary.get("selected_priority_id") or ""),
            str(summary.get("selected_priority") or ""),
            str(signature.get("sha256") or ""),
        ]
    )


def reescalation_hours(handoff: dict[str, Any]) -> float:
    summary = as_dict(handoff.get("summary"))
    level = str(summary.get("selected_priority") or "").upper()
    configured = as_dict(summary.get("re_escalation_interval_checks"))
    value = configured.get(level, DEFAULT_REESCALATION_HOURS.get(level))
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return float(FALLBACK_REESCALATION_HOURS)


def decide_wake(
    handoff: dict[str, Any],
    executor: dict[str, Any],
    steps: list[dict[str, Any]],
    previous: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Fail open on broken proof, but notify Main only once per stable signal."""
    reasons: list[str] = []

    for step in steps:
        if not step.get("ok"):
            reasons.append(f"deterministic_step_failed:{step.get('error_code')}")

    if not handoff:
        reasons.append("handoff_missing_or_unreadable")
    else:
        if as_dict(handoff.get("validation")).get("status") != "ok":
            reasons.append("handoff_validation_not_ok")
        status = str(handoff.get("status") or "").lower()
        if not status:
            reasons.append("handoff_status:unknown")
        elif status == "blocked":
            reasons.append("handoff_status:blocked")
        receipt = str(handoff.get("receipt") or "")
        if receipt in WAKE_RECEIPTS:
            reasons.append(f"handoff_receipt:{receipt}")

    if not executor:
        reasons.append("action_executor_output_missing")
    else:
        if as_dict(executor.get("validation")).get("status") not in {"ok", None}:
            reasons.append("action_executor_validation_not_ok")
        if str(executor.get("status") or "").lower() == "blocked":
            reasons.append("action_executor_blocked")

    reasons = sorted(set(reasons))
    signature = wake_signature(handoff)

    decision = {
        "wake_required": bool(reasons),
        "wake_reasons": reasons,
        "wake_signature": signature,
        "suppressed": False,
        "suppression_reason": None,
        "reescalation_hours": reescalation_hours(handoff),
    }

    if not decision["wake_required"]:
        return decision

    previous_decision = as_dict(previous.get("decision"))
    previous_wake = as_dict(previous.get("wake"))
    same_signal = previous_decision.get("wake_signature") == signature
    previously_dispatched = parse_timestamp(previous_wake.get("dispatched_at_utc")) is not None

    # Receipt values are transition labels. NEW_PRIORITY normally becomes
    # NO_DELTA on the next deterministic run even though the underlying signal
    # is unchanged, so receipt is deliberately excluded from wake_signature.
    # Once a stable signal has been delivered, time alone must never wake Main.
    if same_signal and previously_dispatched:
        decision["suppressed"] = True
        decision["suppression_reason"] = "unchanged_signal_already_dispatched"

    return decision


def build_wake_message(handoff: dict[str, Any], decision: dict[str, Any]) -> str:
    summary = as_dict(handoff.get("summary"))
    lines = [
        "Priority pickup wake. The changed-input gate fired; a main-session review is required.",
        f"Reasons: {', '.join(decision['wake_reasons'])}",
        "",
        f"Read {rel(HANDOFF)} and {rel(EXECUTOR_OUT)}. Both were just refreshed model-free by the gate; do not re-run them.",
        f"Handoff status={handoff.get('status')} receipt={handoff.get('receipt')} "
        f"selected={summary.get('selected_priority')} id={summary.get('selected_priority_id')}",
        "",
        "If either validation is not ok, report only its path, failed control, and named owner.",
        "If the selected priority is P0/P1 with a pending disposition, claim it:",
        "  $p = (Get-Content -LiteralPath 'tmp\\main-session-priority-handoff.json' -Raw | ConvertFrom-Json).selected_item",
        "  python scripts\\main_session_escalation_consumer.py --context main_session --priority-observation-source main_session --write --validate --priority-id $p.priority_id --priority-disposition accepted",
        "Verify the accepted entry in state\\main-session-priority-disposition-ledger.jsonl, then route its named bounded owner.",
        "For defer/block, replace accepted and add a factual --priority-note. P2 is monitor-only.",
        "",
        "Boundaries: review and routing only. No repair execution, generic PM proof, --execute-safe, --execute-one,",
        "finance-agent packet, helper spawn, lane lease, ticker/SQL import, canon/portfolio/cash/sizing/risk mutation,",
        "capital deployment, paper/live/brokerage/account action, money movement, config/auth/runtime mutation,",
        "external delivery, archive/delete, or owner approval inference.",
        "Reply NO_REPLY only when no P0/P1 main-session action is required.",
    ]
    return "\n".join(lines)


def dispatch_wake(
    message: str,
    *,
    job_id: str,
    timeout_seconds: int,
    dry_run: bool,
) -> dict[str, Any]:
    run_at_ms = int(time.time() * 1000)
    session_key = f"agent:main:cron:{job_id}:run:{run_at_ms}"
    message_path = TMP / "pm-priority-pickup-wake-message.txt"

    record: dict[str, Any] = {
        "dispatched": False,
        "dry_run": bool(dry_run),
        "session_key": session_key,
        "run_at_epoch_ms": run_at_ms,
        "message_path": rel(message_path),
        "message_chars": len(message),
        "error_code": None,
    }

    if dry_run:
        record["error_code"] = "dry_run_not_dispatched"
        return record

    binary = shutil.which("openclaw")
    if not binary:
        record["error_code"] = "openclaw_cli_not_found"
        return record

    try:
        ensure_workspace_path(message_path).parent.mkdir(parents=True, exist_ok=True)
        message_path.write_text(message, encoding="utf-8")
    except OSError as exc:
        record["error_code"] = "wake_message_write_failed"
        record["stderr_tail"] = str(exc)[-400:]
        return record

    # WF89: the launcher writes the dispatch record before starting the run, so
    # this Main wake is measured. No record, no launch.
    started = time.monotonic()
    try:
        dispatch, completed = wf89_dispatch_record.launch(
            "main",
            session_key,
            "cron wake: pm priority pickup",
            message_file=message_path,
            extra_args=["--timeout", str(timeout_seconds), "--json"],
            binary=binary,
            launched_by="pm_priority_pickup_predispatch_prefilter",
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 60,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        record["error_code"] = "wake_dispatch_failed"
        record["error_type"] = type(exc).__name__
        record["duration_ms"] = int((time.monotonic() - started) * 1000)
        return record

    record["duration_ms"] = int((time.monotonic() - started) * 1000)
    record["wf89_dispatch_id"] = dispatch["dispatch_id"]
    record["returncode"] = completed.returncode
    record["dispatched"] = completed.returncode == 0
    record["dispatched_at_utc"] = utc_now()
    if completed.returncode != 0:
        record["error_code"] = "wake_dispatch_nonzero_exit"
        record["stderr_tail"] = (completed.stderr or "")[-400:]
    return record


def build_report(
    steps: list[dict[str, Any]],
    handoff: dict[str, Any],
    executor: dict[str, Any],
    decision: dict[str, Any],
    wake: dict[str, Any],
    *,
    now: datetime,
    job_id: str,
) -> dict[str, Any]:
    summary = as_dict(handoff.get("summary"))
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(now),
        "pickup_job_id": job_id,
        "purpose": "Wake Main for priority pickup only when the deterministic handoff proves a review is required.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": STOP_LINES,
        "deterministic_steps": steps,
        "handoff_observed": {
            "path": rel(HANDOFF),
            "status": handoff.get("status"),
            "receipt": handoff.get("receipt"),
            "validation_status": as_dict(handoff.get("validation")).get("status"),
            "selected_priority": summary.get("selected_priority"),
            "selected_priority_id": summary.get("selected_priority_id"),
            "priority_counts": summary.get("priority_counts"),
            "input_signature_sha256": as_dict(handoff.get("input_signature")).get("sha256"),
        },
        "action_executor_observed": {
            "path": rel(EXECUTOR_OUT),
            "status": executor.get("status"),
            "validation_status": as_dict(executor.get("validation")).get("status"),
        },
        "decision": decision,
        "wake": wake,
        "validation": {"status": "pending", "errors": [], "warnings": []},
    }


def validate(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if report.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if report.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_mutated")

    decision = as_dict(report.get("decision"))
    wake = as_dict(report.get("wake"))
    if "wake_required" not in decision:
        errors.append("decision_missing_wake_required")
    if decision.get("wake_required") and not decision.get("wake_reasons"):
        errors.append("wake_required_without_reason")
    if not decision.get("wake_required") and wake.get("dispatched"):
        errors.append("wake_dispatched_without_decision")
    if decision.get("suppressed") and not decision.get("suppression_reason"):
        errors.append("suppressed_without_reason")

    for step in report.get("deterministic_steps") or []:
        if not as_dict(step).get("ok"):
            warnings.append(f"deterministic_step_failed:{as_dict(step).get('error_code')}")

    if decision.get("wake_required") and not decision.get("suppressed"):
        if not wake.get("dispatched") and not wake.get("dry_run") and not wake.get("routed_to_pm"):
            warnings.append(f"wake_not_dispatched:{wake.get('error_code')}")

    handoff = as_dict(report.get("handoff_observed"))
    if handoff.get("status") is None:
        warnings.append("handoff_status_unavailable")

    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": sorted(set(warnings)),
    }


def history_record(report: dict[str, Any]) -> dict[str, Any]:
    decision = as_dict(report.get("decision"))
    wake = as_dict(report.get("wake"))
    handoff = as_dict(report.get("handoff_observed"))
    return {
        "generated_at_utc": report.get("generated_at_utc"),
        "pickup_job_id": report.get("pickup_job_id"),
        "wake_required": decision.get("wake_required"),
        "suppressed": decision.get("suppressed"),
        "wake_reasons": decision.get("wake_reasons"),
        "wake_dispatched": wake.get("dispatched"),
        "wake_session_key": wake.get("session_key") if wake.get("dispatched") else None,
        "handoff_status": handoff.get("status"),
        "handoff_receipt": handoff.get("receipt"),
        "validation_status": as_dict(report.get("validation")).get("status"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run the deterministic steps.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--dry-run-wake", action="store_true", help="Decide but never wake Main.")
    parser.add_argument(
        "--dispatch-main",
        action="store_true",
        help="Allow a genuinely new/changed signal to wake Main; otherwise retain it for deterministic PM intake only.",
    )
    parser.add_argument("--job-id", default=PICKUP_JOB_ID)
    parser.add_argument("--step-timeout", type=int, default=180)
    parser.add_argument("--wake-timeout", type=int, default=600)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--history-out", type=Path, default=HISTORY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.now(timezone.utc)

    previous = load_json(args.out)
    steps = run_deterministic_steps(args.step_timeout) if args.execute else []
    handoff = load_json(HANDOFF)
    executor = load_json(EXECUTOR_OUT)

    decision = decide_wake(handoff, executor, steps, previous, now)

    if decision["wake_required"] and not decision["suppressed"] and args.dispatch_main:
        wake = dispatch_wake(
            build_wake_message(handoff, decision),
            job_id=args.job_id,
            timeout_seconds=args.wake_timeout,
            dry_run=args.dry_run_wake or not args.execute,
        )
    elif decision["wake_required"] and not decision["suppressed"]:
        wake = {
            "dispatched": False,
            "dry_run": False,
            "routed_to_pm": True,
            "error_code": "main_dispatch_disabled_pm_funnel",
        }
    else:
        wake = {
            "dispatched": False,
            "dry_run": False,
            "error_code": "wake_not_required" if not decision["wake_required"] else "wake_suppressed",
        }
        previous_wake = as_dict(previous.get("wake"))
        if decision["suppressed"] and previous_wake.get("dispatched_at_utc"):
            wake["dispatched_at_utc"] = previous_wake.get("dispatched_at_utc")
            wake["session_key"] = previous_wake.get("session_key")
        elif not decision["wake_required"] and previous_wake.get("dispatched_at_utc"):
            # Preserve notification memory across NEW_PRIORITY -> NO_DELTA so
            # the still-pending selection cannot wake Main again next cycle.
            wake["dispatched_at_utc"] = previous_wake.get("dispatched_at_utc")
            wake["session_key"] = previous_wake.get("session_key")

    report = build_report(steps, handoff, executor, decision, wake, now=now, job_id=args.job_id)
    report["validation"] = validate(report)

    if args.write:
        atomic_write_json(args.out, report)
        append_history(args.history_out, history_record(report))

    print(json.dumps(report, indent=2, sort_keys=True))

    if args.validate and report["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
