#!/usr/bin/env python3
"""Changed-input gate for the deterministic status-card freshness runner.

The gate is intentionally local and review-only.  It hashes a small, explicit
input manifest before refreshing the compact status card.  A skip
is allowed only when the input hash is unchanged, the previous runner output
was successful, and that output is still inside the bounded reuse window.

The wrapper's execute mode may refresh the status-card packet directly. When
cron or PM control is newer than the WF74 opportunity queue, it refreshes that
queue producer first so the card cannot go critical on a stale producer. It does
not edit cron. The owner-approved status-card cron
payload was activated as this command entrypoint on 2026-08-27, so scheduled
invocations do not create a model or agent turn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import wf88_daily_actionability_refresh as nightly_sequence

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "status-card-freshness-predispatch-prefilter.json"
RUNNER_OUT = TMP / "status-card-freshness-runner.json"
SCHEMA = "veritas.status_card_freshness_predispatch_prefilter.v1"
RUNNER_SCHEMA = "veritas.status_card_freshness_alerts_os_runner.v2"
LOCAL_TZ = ZoneInfo("America/Phoenix")
MAX_REUSE_MINUTES = 45

# These are inputs to the five-step chain, not its output proof files.  The
# explicit list makes the skip boundary reviewable and prevents a broad scan.
STATIC_INPUT_SOURCES = [
    # Direct code and route/control owners.
    "scripts/future_session_enhancement_packet.py",
    "scripts/startup_brief_packet.py",
    "scripts/status_card_packet.py",
    "scripts/session_resume_checkpoint.py",
    "scripts/improvement_ledger.py",
    "scripts/project_implementation_router.py",
    "scripts/market_data_utils.py",
    "scripts/lib/pm_control_reader.py",
    "scripts/lib/workflow_control.py",
    "SOUL.md",
    "AGENTS.md",
    "USER.md",
    "06. Playbooks/Startup Truth Index.md",
    "06. Playbooks/Active Workflows.md",
    "state/workflow-control-overrides.json",
    # Inputs consumed by status_card_packet.py or produced upstream in the
    # same chain.  Generated timestamps are normalized out of JSON below;
    # semantic status changes remain part of the signature.
    "tmp/pm-control-packet.json",
    "tmp/cron-control-packet.json",
    "tmp/future-session-enhancement-packet.json",
    "tmp/future-session-enhancement-packet.md",
    "tmp/startup-brief-packet.json",
    "tmp/token-usage-ledger-current.json",
    "tmp/token-budget-status.json",
    "tmp/tmp-artifact-spire.json",
    "tmp/security-warning-ledger.json",
    "tmp/cron-freshness-spine.json",
    "tmp/finance-sql-canon-access-validation.json",
    "tmp/intraday-alerts/quote-snapshot-proof.json",
    "tmp/alert-level-freshness-controller.json",
    "tmp/finance-alert-os-digest.json",
    "tmp/alerts-os-pivot-validator.json",
    "tmp/veritas-artifact-index.sqlite",
    "tmp/owner-gated-action-review-queue.json",
    "tmp/improvement-ledger-current.json",
    "tmp/wf74-improvement-opportunity-queue.json",
    "tmp/wf74-auto-patch-proposer.json",
    "tmp/wf74-decision-docket.json",
    "tmp/otel-learning-loop.json",
    "tmp/wf88-wiki-synthesis-packet.json",
    "tmp/wiki-bootstrap-proof.json",
    "tmp/concurrent-lane-register.json",
    "tmp/vector-memory-index.json",
    "tmp/vector-memory-query.json",
    "tmp/actionable-improvement-queue.json",
    "tmp/no-orphan-validator.json",
    "tmp/workflow-blocker-followups.json",
    "tmp/main-session-action-executor.json",
    "tmp/main-session-escalation-consumer.json",
    "tmp/pm-autonomy-dispatcher.json",
    "tmp/pm-job-worker-runner.json",
    "tmp/pm-autonomy-verifier.json",
    "tmp/pm-main-session-action-inbox.json",
    "state/implementation-completion-ledger.jsonl",
    "tmp/cron-migration-repair-plan.json",
]

REQUIRED_INPUT_SOURCES = frozenset(
    {
        # Code and doctrine/control inputs must fail closed if absent or
        # malformed.  The remaining packet inputs are optional status-card
        # surfaces and may be reused with their warning state after a
        # successful run.
        "scripts/future_session_enhancement_packet.py",
        "scripts/startup_brief_packet.py",
        "scripts/status_card_packet.py",
        "scripts/session_resume_checkpoint.py",
        "scripts/improvement_ledger.py",
        "scripts/project_implementation_router.py",
        "scripts/market_data_utils.py",
        "scripts/lib/pm_control_reader.py",
        "scripts/lib/workflow_control.py",
        "SOUL.md",
        "AGENTS.md",
        "USER.md",
        "06. Playbooks/Startup Truth Index.md",
        "06. Playbooks/Active Workflows.md",
        "state/workflow-control-overrides.json",
        "tmp/future-session-enhancement-packet.json",
        "tmp/future-session-enhancement-packet.md",
        "tmp/startup-brief-packet.json",
    }
)

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "prefilter_is_review_proof_surface": True,
    "prefilter_proof_write_allowed": True,
    "may_run_alerts_os_status_card_refresh": True,
    "status_card_review_artifact_writes_allowed": True,
    "control_or_authority_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "cron_payload_mutation_allowed": False,
    "model_route_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

STOP_LINES = [
    "Do not edit or promote a cron payload from this wrapper.",
    "Do not mutate schedule, model route, config, runtime, finance/canon/portfolio, or execution surfaces.",
    "Execute mode may write only the status-card review outputs and its local runner proof.",
    "Do not treat skipped_unchanged as a freshness or approval decision beyond this bounded runner reuse.",
    "Any future live payload change remains a separate owner-gated cron operation with rollback proof.",
]

VOLATILE_KEYS = {
    "age_hours",
    "age_minutes",
    "age_seconds",
    "completed_at",
    "completed_at_utc",
    "created_at",
    "created_at_utc",
    "duration_ms",
    "elapsed_seconds",
    "generated_at",
    "generated_at_utc",
    "modified_at",
    "modified_at_utc",
    "previous_freshness",
    "started_at",
    "started_at_utc",
    "timestamp",
    "timestamp_utc",
    "updated_at",
    "updated_at_utc",
}


def utc_now(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(path: str | Path, root: Path = ROOT) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def ensure_workspace_path(path: str | Path, root: Path = ROOT) -> Path:
    resolved = resolve_path(path, root).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path must remain inside the workspace: {path}") from exc
    return resolved


def stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized_key = str(key)
            if normalized_key in VOLATILE_KEYS or normalized_key.endswith("_at_utc") or normalized_key.endswith("_mtime_ns"):
                continue
            result[normalized_key] = stable_value(child)
        return result
    if isinstance(value, list):
        return [stable_value(child) for child in value]
    return value


def json_or_bytes_material(path: Path) -> tuple[bytes, str, str | None]:
    raw = path.read_bytes()
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            stable = json.dumps(stable_value(parsed), sort_keys=True, separators=(",", ":")).encode("utf-8")
            return stable, "stable_json_without_volatile_fields", None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return raw, "raw_bytes_json_parse_failed", type(exc).__name__
    if path.suffix.lower() == ".jsonl":
        lines: list[Any] = []
        try:
            for raw_line in raw.decode("utf-8-sig").splitlines():
                if raw_line.strip():
                    lines.append(stable_value(json.loads(raw_line)))
            stable = json.dumps(lines, sort_keys=True, separators=(",", ":")).encode("utf-8")
            return stable, "stable_jsonl_without_volatile_fields", None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return raw, "raw_bytes_jsonl_parse_failed", type(exc).__name__
    return raw, "raw_bytes", None


def source_key(path: str | Path, root: Path = ROOT) -> str:
    return rel(ensure_workspace_path(path, root), root)


def source_record(path: str | Path, root: Path = ROOT, *, required: bool = False) -> dict[str, Any]:
    resolved = ensure_workspace_path(path, root)
    display = rel(resolved, root)
    if not resolved.exists():
        return {
            "path": display,
            "required": required,
            "exists": False,
            "kind": "missing",
            "sha256": None,
            "size_bytes": None,
            "normalization": None,
            "parse_error": None,
        }
    if not resolved.is_file():
        return {
            "path": display,
            "required": required,
            "exists": True,
            "kind": "unsupported",
            "sha256": None,
            "size_bytes": None,
            "normalization": None,
            "parse_error": "not_a_file",
        }
    material, normalization, parse_error = json_or_bytes_material(resolved)
    return {
        "path": display,
        "required": required,
        "exists": True,
        "kind": "file",
        "sha256": hashlib.sha256(material).hexdigest(),
        "size_bytes": resolved.stat().st_size,
        "normalization": normalization,
        "parse_error": parse_error,
    }


def input_source_paths(now: datetime, source_paths: Iterable[str | Path] | None = None) -> list[str | Path]:
    paths: list[str | Path] = list(STATIC_INPUT_SOURCES if source_paths is None else source_paths)
    phoenix_date = now.astimezone(LOCAL_TZ).date()
    paths.extend(
        [
            f"memory/{phoenix_date.isoformat()}.md",
            f"memory/{(phoenix_date - timedelta(days=1)).isoformat()}.md",
        ]
    )
    # Preserve order while avoiding duplicate records in the proof.
    seen: set[str] = set()
    unique: list[str | Path] = []
    for path in paths:
        key = str(path).replace("\\", "/")
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def build_input_signature(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    source_paths: Iterable[str | Path] | None = None,
    required_source_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    explicit_required_paths = list(required_source_paths) if required_source_paths is not None else None
    paths = input_source_paths(current, source_paths)
    if explicit_required_paths is not None:
        seen = {source_key(path, root) for path in paths}
        for path in explicit_required_paths:
            key = source_key(path, root)
            if key not in seen:
                paths.append(path)
                seen.add(key)
    required_keys = {
        source_key(path, root)
        for path in (REQUIRED_INPUT_SOURCES if explicit_required_paths is None else explicit_required_paths)
    }
    records = [
        source_record(path, root, required=source_key(path, root) in required_keys)
        for path in paths
    ]
    digest_material = [
        {key: record.get(key) for key in ("path", "required", "exists", "kind", "sha256", "size_bytes", "normalization", "parse_error")}
        for record in records
    ]
    digest = hashlib.sha256(json.dumps(digest_material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "hash": digest,
        "generated_at_utc": utc_now(current),
        "phoenix_date": current.astimezone(LOCAL_TZ).date().isoformat(),
        "source_count": len(records),
        "missing_source_count": sum(1 for record in records if not record["exists"]),
        "unsupported_source_count": sum(1 for record in records if record["kind"] == "unsupported"),
        "parse_warning_count": sum(1 for record in records if record["parse_error"]),
        "required_source_problem_count": sum(
            1
            for record in records
            if record["required"] and (not record["exists"] or record["kind"] == "unsupported" or record["parse_error"])
        ),
        "optional_source_problem_count": sum(
            1
            for record in records
            if not record["required"] and (not record["exists"] or record["kind"] == "unsupported" or record["parse_error"])
        ),
        "sources": records,
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def atomic_write_json(path: Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    resolved = ensure_workspace_path(path, root)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved.with_suffix(resolved.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(resolved)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def runner_success(payload: dict[str, Any]) -> bool:
    counters = {
        key: payload.get(key)
        for key in ("step_count", "steps_executed", "steps_passed", "steps_failed")
    }
    if not all(type(value) is int for value in counters.values()):
        return False
    return bool(
        payload.get("schema") == RUNNER_SCHEMA
        and payload.get("status") == "ok"
        and counters["step_count"] == counters["steps_executed"] == counters["steps_passed"] == 1
        and counters["steps_failed"] == 0
    )


def runner_output_summary(payload: dict[str, Any], now: datetime, max_reuse_minutes: int) -> dict[str, Any]:
    completed = parse_timestamp(payload.get("completed_at_utc") or payload.get("generated_at_utc"))
    age_seconds = (now.astimezone(timezone.utc) - completed).total_seconds() if completed else None
    fresh_enough = bool(completed and 0 <= age_seconds <= max_reuse_minutes * 60)
    return {
        "present": bool(payload),
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "steps_passed": payload.get("steps_passed"),
        "step_count": payload.get("step_count"),
        "steps_failed": payload.get("steps_failed"),
        "completed_at_utc": payload.get("completed_at_utc") or payload.get("generated_at_utc"),
        "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "success": runner_success(payload),
        "fresh_enough_for_reuse": fresh_enough,
        "reuse_window_minutes": max_reuse_minutes,
    }


def previous_success_signature(previous: dict[str, Any]) -> str | None:
    if previous.get("status") not in {"runner_executed", "skipped_unchanged"}:
        return None
    value = previous.get("last_success_signature")
    if value:
        return str(value)
    signature = previous.get("input_signature")
    if not isinstance(signature, dict):
        return None
    value = signature.get("hash")
    return str(value) if value else None


def source_problem(record: dict[str, Any]) -> bool:
    return bool(not record.get("exists") or record.get("kind") == "unsupported" or record.get("parse_error"))


def build_prefilter_report(
    *,
    root: Path = ROOT,
    now: datetime | None = None,
    proof_path: Path = OUT,
    runner_path: Path = RUNNER_OUT,
    max_reuse_minutes: int = MAX_REUSE_MINUTES,
    source_paths: Iterable[str | Path] | None = None,
    required_source_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    proof_path = ensure_workspace_path(proof_path, root)
    runner_path = ensure_workspace_path(runner_path, root)
    input_signature = build_input_signature(
        root=root,
        now=current,
        source_paths=source_paths,
        required_source_paths=required_source_paths,
    )
    previous = load_json(proof_path)
    runner = load_json(runner_path)
    runner_summary = runner_output_summary(runner, current, max_reuse_minutes)
    last_success = previous_success_signature(previous)
    source_warnings: list[str] = []
    force_run_warnings: list[str] = []
    problem_records = [record for record in input_signature["sources"] if source_problem(record)]
    required_issues = {
        "missing" if not record["exists"] else "unsupported" if record["kind"] == "unsupported" else "unparseable"
        for record in problem_records
        if record["required"]
    }
    optional_issues = {
        "missing" if not record["exists"] else "unsupported" if record["kind"] == "unsupported" else "unparseable"
        for record in problem_records
        if not record["required"]
    }
    force_run_warnings.extend(f"required_source_{issue}_force_run_required" for issue in sorted(required_issues))
    source_warnings.extend(force_run_warnings)
    source_warnings.extend(f"optional_source_{issue}_warning_reuse_allowed" for issue in sorted(optional_issues))
    source_unchanged = bool(last_success and last_success == input_signature["hash"])
    # Some status-card inputs are optional packets.  Their absence must be
    # visible in the proof and must force the first run, but it should not
    # cause an already-successful, unchanged warning state to execute every
    # cycle.  A newly appearing or changing packet still changes the hash.
    can_skip = bool(
        source_unchanged
        and runner_summary["success"]
        and runner_summary["fresh_enough_for_reuse"]
        and not force_run_warnings
    )
    if can_skip:
        status = "skipped_unchanged"
        action = "skip_runner"
        reason = "unchanged_inputs_successful_runner_output_fresh"
    else:
        status = "run_required"
        action = "run_existing_runner_when_promoted"
        if not last_success:
            reason = "missing_previous_success_signature"
        elif not source_unchanged:
            reason = "source_signature_changed"
        elif not runner_summary["success"]:
            reason = "previous_runner_output_not_successful"
        elif not runner_summary["fresh_enough_for_reuse"]:
            reason = "previous_runner_output_outside_reuse_window"
        elif force_run_warnings:
            reason = force_run_warnings[0]
        else:
            reason = source_warnings[0] if source_warnings else "reuse_conditions_not_met"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(current),
        "status": status,
        "action": action,
        "job_name": "Runtime - Status Card Freshness Refresh",
        "purpose": "Skip duplicate deterministic status-card work only when the alerts-OS input manifest is unchanged and a successful refresh proof remains fresh.",
        "input_signature": input_signature,
        "last_success_signature": last_success,
        "previous_prefilter_status": previous.get("status"),
        "source_unchanged": source_unchanged,
        "would_run_existing_runner": not can_skip,
        "would_spawn_model_or_agent_turn": False,
        "prefilter": {
            "reason": reason,
            "source_unchanged": source_unchanged,
            "source_warnings": source_warnings,
            "force_run_warnings": force_run_warnings,
            "meaning": "Reuse is bounded to a prior successful runner output inside the configured freshness window; it is not a route, approval, or finance decision.",
        },
        "runner_output": runner_summary,
        "source_artifacts": {
            "prefilter_proof": rel(resolve_path(proof_path, root), root),
            "runner_output": rel(resolve_path(runner_path, root), root),
            "status_card_refresh": "scripts/status_card_packet.py",
        },
        "promotion_effect": {
            "alerts_os_status_card_path": True,
            "current_live_payload_kind": "command",
            "eliminates_scheduled_agent_turn": True,
            "requires_separate_cron_payload_promotion": False,
            "reason": "The owner-approved live cron payload invokes this deterministic command directly, so unchanged and changed paths require no model or agent turn.",
        },
        "execution_semantics": {
            "prefilter_writes_its_own_review_proof": True,
            "execute_mode_writes_existing_review_packets": True,
            "control_or_authority_state_mutation": False,
            "scheduled_agent_turn_occurs_if_embedded_in_current_agent_turn": False,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": STOP_LINES,
        "validation": {
            "status": "warning" if source_warnings else "ok",
            "errors": [],
            "warnings": source_warnings,
        },
    }


def run_existing_runner(
    timeout_seconds: int = 180,
    root: Path = ROOT,
    runner_out: Path = RUNNER_OUT,
) -> dict[str, Any]:
    try:
        resolved_runner_out = ensure_workspace_path(runner_out, root)
    except ValueError:
        return {
            "command": None,
            "started_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "duration_ms": 0,
            "returncode": None,
            "ok": False,
            "error_code": "runner_output_path_outside_workspace",
            "stdout_tail": "",
            "stderr_tail": "runner output must remain inside the workspace",
        }
    try:
        resolved_runner_out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "command": None,
            "started_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "duration_ms": 0,
            "returncode": None,
            "ok": False,
            "error_code": "runner_output_path_prepare_failed",
            "error_type": type(exc).__name__,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }
    staleness = nightly_sequence.status_card_queue_staleness(root)
    producer_steps: list[dict[str, Any]] = []

    def finish(payload: dict[str, Any]) -> dict[str, Any]:
        payload["producer_steps"] = producer_steps
        payload["producer_order"] = staleness
        return payload

    if staleness.get("stale"):
        producer_command = nightly_sequence.command_for_step(nightly_sequence.STATUS_CARD_QUEUE_STEP)
        if not producer_command:
            return finish({
                "command": None,
                "started_at_utc": utc_now(),
                "completed_at_utc": utc_now(),
                "duration_ms": 0,
                "returncode": None,
                "ok": False,
                "error_code": "producer_order_blocked",
                "producer_failure": "producer_command_missing",
                "stdout_tail": "",
                "stderr_tail": "status card queue producer is not declared",
            })
        producer_timeout = min(nightly_sequence.STATUS_CARD_PRODUCER_TIMEOUT_SECONDS, timeout_seconds)
        producer_started = time.monotonic()
        producer_started_at = utc_now()
        try:
            produced = subprocess.run(
                producer_command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=producer_timeout,
                check=False,
            )
            producer_result = {
                "id": nightly_sequence.STATUS_CARD_QUEUE_STEP,
                "command": producer_command,
                "started_at_utc": producer_started_at,
                "completed_at_utc": utc_now(),
                "duration_ms": int((time.monotonic() - producer_started) * 1000),
                "returncode": produced.returncode,
                "ok": produced.returncode == 0,
                "stdout_tail": (produced.stdout or "")[-2000:],
                "stderr_tail": (produced.stderr or "")[-2000:],
            }
        except subprocess.TimeoutExpired as exc:
            producer_result = {
                "id": nightly_sequence.STATUS_CARD_QUEUE_STEP,
                "command": producer_command,
                "started_at_utc": producer_started_at,
                "completed_at_utc": utc_now(),
                "duration_ms": int((time.monotonic() - producer_started) * 1000),
                "returncode": None,
                "ok": False,
                "timeout_seconds": producer_timeout,
                "error_code": "step_timeout",
                "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            }
        except (OSError, ValueError) as exc:
            producer_result = {
                "id": nightly_sequence.STATUS_CARD_QUEUE_STEP,
                "command": producer_command,
                "started_at_utc": producer_started_at,
                "completed_at_utc": utc_now(),
                "duration_ms": int((time.monotonic() - producer_started) * 1000),
                "returncode": None,
                "ok": False,
                "error_code": "runner_launch_failed",
                "error_type": type(exc).__name__,
                "stdout_tail": "",
                "stderr_tail": str(exc),
            }
        producer_steps.append(producer_result)
        if not producer_result.get("ok"):
            # Do not run the card against the stale queue. A failed producer is
            # a typed block, not a false critical from the card.
            return finish({
                "command": producer_command,
                "started_at_utc": producer_result.get("started_at_utc"),
                "completed_at_utc": producer_result.get("completed_at_utc"),
                "duration_ms": producer_result.get("duration_ms"),
                "returncode": producer_result.get("returncode"),
                "ok": False,
                "error_code": "producer_order_blocked",
                "producer_failure": producer_result.get("error_code") or "producer_nonzero_exit",
                "timeout_seconds": producer_result.get("timeout_seconds"),
                "stdout_tail": producer_result.get("stdout_tail", ""),
                "stderr_tail": producer_result.get("stderr_tail", ""),
            })

    command = [
        sys.executable,
        str(resolve_path("scripts/status_card_packet.py", root)),
        "--write",
        "--validate",
    ]
    started = time.monotonic()
    started_at = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        completed_at = utc_now()
        runner_proof = {
            "schema": RUNNER_SCHEMA,
            "generated_at_utc": completed_at,
            "completed_at_utc": completed_at,
            "status": "ok" if completed.returncode == 0 else "error",
            "step_count": 1,
            "steps_executed": 1,
            "steps_passed": 1 if completed.returncode == 0 else 0,
            "steps_failed": 0 if completed.returncode == 0 else 1,
            "step": "status_card_packet",
            "authority": "review_only_alerts_os_status_refresh",
        }
        atomic_write_json(resolved_runner_out, runner_proof, root=root)
        return finish({
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": completed_at,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": (completed.stdout or "")[-2000:],
            "stderr_tail": (completed.stderr or "")[-2000:],
        })
    except subprocess.TimeoutExpired as exc:
        return finish({
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        })
    except (OSError, ValueError) as exc:
        return finish({
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "returncode": None,
            "ok": False,
            "error_code": "runner_launch_failed",
            "error_type": type(exc).__name__,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        })


def finalize_runner_execution(
    report: dict[str, Any],
    execution: dict[str, Any],
    *,
    root: Path = ROOT,
    runner_path: Path = RUNNER_OUT,
    max_reuse_minutes: int = MAX_REUSE_MINUTES,
    now: datetime | None = None,
    source_paths: Iterable[str | Path] | None = None,
    required_source_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    report["runner_execution"] = execution
    if execution.get("ok"):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        resolved_runner_path = ensure_workspace_path(runner_path, root)
        post_run_signature = build_input_signature(
            root=root,
            now=current,
            source_paths=source_paths,
            required_source_paths=required_source_paths,
        )
        report["post_run_input_signature"] = post_run_signature
        report["runner_output"] = runner_output_summary(
            load_json(resolved_runner_path),
            current,
            max_reuse_minutes,
        )
        if report["runner_output"]["success"] and report["runner_output"]["fresh_enough_for_reuse"]:
            report["status"] = "runner_executed"
            report["action"] = "runner_executed"
            report["last_success_signature"] = post_run_signature["hash"]
            report["prefilter"]["reason"] = "changed_or_unproven_inputs_runner_succeeded"
            report["validation"] = {
                "status": "ok",
                "errors": [],
                "warnings": report["validation"].get("warnings", []),
            }
        elif report["runner_output"]["success"]:
            report["status"] = "blocked"
            report["action"] = "runner_output_not_reusable"
            report["validation"] = {
                "status": "error",
                "errors": ["status_card_alerts_os_refresh_output_not_reusable"],
                "warnings": report["validation"].get("warnings", []),
            }
        else:
            report["status"] = "blocked"
            report["action"] = "runner_output_invalid"
            report["validation"] = {
                "status": "error",
                "errors": ["status_card_alerts_os_refresh_output_invalid"],
                "warnings": report["validation"].get("warnings", []),
            }
    else:
        report["status"] = "blocked"
        report["action"] = "runner_failed"
        report["validation"] = {
            "status": "error",
            "errors": ["status_card_alerts_os_refresh_failed"],
            "warnings": report["validation"].get("warnings", []),
        }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run the existing runner when the prefilter says run_required.")
    parser.add_argument("--prefilter-only", action="store_true", help="Write only the prefilter decision; never run the existing runner.")
    parser.add_argument("--write", action="store_true", help="Write the prefilter proof artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero only when runner execution fails.")
    parser.add_argument("--json", action="store_true", dest="print_json", help="Print the complete JSON report.")
    parser.add_argument("--out", type=Path, default=OUT, help="Prefilter proof output path.")
    parser.add_argument("--runner-out", type=Path, default=RUNNER_OUT, help="Existing runner output path used for reuse checks.")
    parser.add_argument("--max-reuse-minutes", type=int, default=MAX_REUSE_MINUTES)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute and args.prefilter_only:
        raise SystemExit("--execute and --prefilter-only are mutually exclusive")
    if args.max_reuse_minutes <= 0 or args.timeout_seconds <= 0:
        raise SystemExit("reuse and timeout values must be positive")
    try:
        args.out = ensure_workspace_path(args.out, ROOT)
        args.runner_out = ensure_workspace_path(args.runner_out, ROOT)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    report = build_prefilter_report(
        proof_path=args.out,
        runner_path=args.runner_out,
        max_reuse_minutes=args.max_reuse_minutes,
    )
    if report["status"] == "run_required" and args.execute and not args.prefilter_only:
        execution = run_existing_runner(args.timeout_seconds, root=ROOT, runner_out=args.runner_out)
        report = finalize_runner_execution(
            report,
            execution,
            root=ROOT,
            runner_path=args.runner_out,
            max_reuse_minutes=args.max_reuse_minutes,
        )
    if args.write:
        atomic_write_json(args.out, report)
    if args.print_json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"status={report['status']} action={report['action']} "
            f"source_unchanged={report['source_unchanged']} "
            f"runner_success={report['runner_output']['success']}"
        )
    return 1 if args.validate and report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
