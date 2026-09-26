#!/usr/bin/env python3
"""Run the daily WF88 actionability refresh sequence.

This wrapper keeps the cron payload small while preserving an exact,
review-only command sequence. It stops on the first failing command and writes
a proof packet for the cron gate/front-door refresh path.

Producer-before-consumer coverage: the retrieval, decision-compiler, and RSI
outcome scorecards are refreshed here before the wiki synthesis/OS2 consumers,
so the nightly packet reflects regenerated evidence rather than stale
downstream scores. Fresh-packet reuse is invalidated when the producing script
changed since the artifact was generated, and consumer steps declare required
fresh dependencies that block with typed proof instead of greening on stale
inputs. Timeouts are recorded as typed failed proof so the packet is never
lost to an uncaught exception.

Dependency fail-closed contract (allowlist): a dependency artifact counts as
fresh evidence only when it is present and readable, carries a non-blank
string status with no failure markers, and carries validation status exactly
ok or warning. Missing/blank/critical/failed/fail-open/fail-closed/blocked/
error statuses never green a consumer. Review-only warnings (RSI maturity,
decision-compiler review-only state) remain warnings, never failures.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf88-daily-actionability-refresh.json"
SCHEMA = "veritas.wf88_daily_actionability_refresh.v1"

WF74_REUSE_WINDOW_MINUTES = 120

RETRIEVAL_QUALITY_MAX_AGE_MINUTES = 168 * 60
DECISION_COMPILER_MAX_AGE_MINUTES = 24 * 60
RSI_OUTCOME_MAX_AGE_MINUTES = 24 * 60
PRODUCER_CODE_SKEW_GRACE_SECONDS = 1.0

# Transient-collision retry (production default): overlapping scheduled jobs
# can briefly rewrite shared artifacts while this chain reads them, making an
# otherwise-green producer fail once. One bounded retry absorbs that class.
# Timeouts and launch errors are never retried; a persistent failure still
# stops the chain with first-attempt evidence preserved on the row.
STEP_RETRY_LIMIT = 1
STEP_RETRY_WAIT_SECONDS = 15.0

DEPENDENCY_MAX_AGE_MINUTES = {
    "tmp/retrieval-quality-scorecard.json": RETRIEVAL_QUALITY_MAX_AGE_MINUTES,
    "tmp/wf88-decision-compiler.json": DECISION_COMPILER_MAX_AGE_MINUTES,
    "tmp/rsi-outcome-scorecard.json": RSI_OUTCOME_MAX_AGE_MINUTES,
}

DEPENDENCY_PRODUCER_SCRIPTS = {
    "tmp/retrieval-quality-scorecard.json": "scripts/retrieval_quality_scorecard.py",
    "tmp/wf88-decision-compiler.json": "scripts/wf88_decision_compiler.py",
    "tmp/rsi-outcome-scorecard.json": "scripts/rsi_outcome_scorecard.py",
}

# recommendation_outcome_grading was retired 2026-09-25 (Randall approval): its
# quote and recommendation feeders stopped on 2026-08-29 with the alerts-OS pivot,
# so it graded nothing while reporting ok. The grades history stays as frozen
# evidence; the successor is a scorer on the alert-event ledger.
COMMANDS: list[dict[str, Any]] = [
    {"id": "wf55_outcome_ledger_current", "command": [sys.executable, "scripts\\wf55_outcome_ledger_v2.py", "preview"]},
    {"id": "finance_decision_performance", "command": [sys.executable, "scripts\\finance_decision_performance_digest.py", "--write", "--write-md", "--validate"]},
    {"id": "cron_contract_validator", "command": [sys.executable, "scripts\\cron_contract_validator.py", "--write", "--validate"]},
    {"id": "cron_freshness_spine", "command": [sys.executable, "scripts\\cron_freshness_spine.py", "--write", "--validate"]},
    {"id": "cron_control_packet", "command": [sys.executable, "scripts\\cron_control_packet.py", "--write", "--validate"]},
    {"id": "coding_outcome_ledger", "command": [sys.executable, "scripts\\coding_outcome_ledger.py", "--write", "--validate"]},
    {"id": "token_usage_ledger", "command": [sys.executable, "scripts\\token_usage_ledger.py", "--write", "--write-md", "--validate"]},
    {"id": "implementation_token_attribution_bridge", "command": [sys.executable, "scripts\\implementation_token_attribution_bridge.py", "--write", "--write-md", "--validate"]},
    {
        "id": "wf74_improvement_queue",
        "command": [sys.executable, "scripts\\wf74_improvement_opportunity_queue.py", "--write", "--write-md", "--validate"],
    },
    {"id": "finance_response_quality_repair_loop", "command": [sys.executable, "scripts\\finance_response_quality_repair_loop.py", "--write", "--write-md", "--validate"]},
    {
        "id": "wf74_reflection_proposals",
        "command": [sys.executable, "scripts\\wf74_reflection_to_proposal_autopilot.py", "--write", "--write-md", "--validate"],
    },
    {
        "id": "wf74_auto_patch_proposer",
        "command": [sys.executable, "scripts\\wf74_auto_patch_proposer.py", "--write", "--write-md", "--validate"],
    },
    {
        "id": "pm_control_packet",
        "command": [sys.executable, "scripts\\pm_control_packet.py", "--write", "--validate"],
    },
    {
        "id": "wf74_autonomy_router",
        "command": [sys.executable, "scripts\\wf74_autonomy_work_router.py", "--write", "--validate"],
    },
    {"id": "wf88_followup_triage", "command": [sys.executable, "scripts\\wf88_followup_debt_triage_packet.py", "--write", "--write-md", "--validate"]},
    # Closure-chain: durable append via existing guarded producer (build_payload append=True when --write without --check); --check never appends.
    {"id": "improvement_ledger", "command": [sys.executable, "scripts\\improvement_ledger.py", "--write", "--write-md", "--validate"]},
    {"id": "wf74_decision_docket", "command": [sys.executable, "scripts\\wf74_decision_docket.py", "--write", "--validate"]},
    {
        "id": "owner_gated_queue",
        "command": [sys.executable, "scripts\\owner_gated_action_review_queue.py", "--write", "--write-md", "--validate"],
    },
    {
        "id": "pm_implementation_jobs",
        "command": [sys.executable, "scripts\\pm_implementation_job_queue.py", "--write", "--write-db", "--validate"],
    },
    {"id": "workflow_routing_index", "command": [sys.executable, "scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"]},
    {"id": "wf88_retired_surface_cleanup_plan", "command": [sys.executable, "scripts\\wf88_retired_surface_cleanup_plan.py", "--write", "--write-md", "--validate"]},
    {"id": "wf88_route_contraction_packet", "command": [sys.executable, "scripts\\wf88_route_contraction_packet.py", "--write", "--write-md", "--validate"]},
    {"id": "wf88_delete_readiness_packet", "command": [sys.executable, "scripts\\wf88_delete_readiness_packet.py", "--write", "--write-md", "--validate"]},
    {"id": "wf74_wf88_loop_trace", "command": [sys.executable, "scripts\\wf74_wf88_loop_trace_packet.py", "--write", "--write-md", "--validate"]},
    {"id": "long_work_job_status", "command": [sys.executable, "scripts\\long_work_job_status_packet.py", "--write", "--write-md", "--validate"]},
    {"id": "skill_workshop_body_guard", "command": [sys.executable, "scripts\\skill_workshop_body_guard.py", "--write", "--validate"]},
    {"id": "otel_ops_control", "command": [sys.executable, "scripts\\otel_ops_control.py", "--write", "--write-db", "--multi-window", "--validate"]},
    {"id": "wf88_os2_before_wiki", "command": [sys.executable, "scripts\\wf88_os2_control_packet.py", "--write", "--write-md"]},
    {"id": "actionable_improvement_queue", "command": [sys.executable, "scripts\\actionable_improvement_queue.py", "--write", "--write-md", "--validate"]},
    {"id": "retrieval_live_eval", "command": [sys.executable, "scripts\\retrieval_live_eval.py", "--write", "--write-md", "--validate"]},
    {"id": "retrieval_quality_scorecard", "command": [sys.executable, "scripts\\retrieval_quality_scorecard.py", "--write", "--write-md", "--validate"]},
    {"id": "wf88_decision_compiler", "command": [sys.executable, "scripts\\wf88_decision_compiler.py", "--write", "--write-md", "--validate"]},
    {"id": "rsi_outcome_scorecard", "command": [sys.executable, "scripts\\rsi_outcome_scorecard.py", "--write", "--write-md", "--validate"]},
    {"id": "no_orphan_validator", "command": [sys.executable, "scripts\\no_orphan_validator.py", "--write", "--validate"]},
    {
        "id": "wf88_wiki_synthesis",
        "command": [sys.executable, "scripts\\wf88_wiki_synthesis_packet.py", "--write", "--write-md", "--write-wiki"],
        "requires_fresh_artifacts": [
            "tmp\\retrieval-quality-scorecard.json",
            "tmp\\wf88-decision-compiler.json",
            "tmp\\rsi-outcome-scorecard.json",
        ],
    },
    {"id": "wiki_bootstrap_validator", "command": [sys.executable, "scripts\\wiki_bootstrap_validator.py", "--write", "--validate"]},
    {"id": "wf88_os2_after_wiki", "command": [sys.executable, "scripts\\wf88_os2_control_packet.py", "--write", "--write-md"]},
    {"id": "wf88_wiki_cron_gate", "command": [sys.executable, "scripts\\wf88_wiki_refresh_cron_gate.py", "--write", "--validate"]},
    {"id": "workflow_routing_index_final", "command": [sys.executable, "scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"]},
    {"id": "wf74_workflow_router_capsules", "command": [sys.executable, "scripts\\workflow_router.py", "WF74", "--answer", "all", "--write-capsules", "--validate"]},
    {"id": "wf88_workflow_router_capsules", "command": [sys.executable, "scripts\\workflow_router.py", "WF88", "--answer", "all", "--write-capsules", "--validate"]},
    {"id": "future_session_packet", "command": [sys.executable, "scripts\\future_session_enhancement_packet.py", "--write", "--write-md"]},
    {"id": "startup_brief", "command": [sys.executable, "scripts\\startup_brief_packet.py", "--write"]},
    {"id": "status_card", "command": [sys.executable, "scripts\\status_card_packet.py", "--write"]},
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runs_local_refresh_commands": True,
    "auto_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def tail(value: str, limit: int = 1200) -> str:
    text = value.strip()
    return text[-limit:] if len(text) > limit else text


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_rel(path_value: str) -> str:
    return str(path_value).replace("\\", "/").strip()


def resolve_under_root(path_value: str) -> Path:
    path = Path(str(path_value))
    return path if path.is_absolute() else ROOT / path


def producer_script_for_command(spec: dict[str, Any]) -> Path | None:
    command = spec.get("command") or []
    if len(command) >= 2 and str(command[1]).endswith(".py"):
        return resolve_under_root(str(command[1]))
    return None


def script_changed_since(script: Path, generated: datetime | None) -> bool:
    if generated is None:
        return True
    try:
        mtime = datetime.fromtimestamp(script.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return True
    return mtime.timestamp() > generated.timestamp() + PRODUCER_CODE_SKEW_GRACE_SECONDS


def blocked_component_status(value: Any) -> bool:
    text = str(value or "").lower()
    return (
        ("blocked" in text)
        or ("fail_closed" in text)
        or ("fail_open" in text)
        or ("failed" in text)
        or ("critical" in text)
        or ("error" in text)
    )


EVIDENCE_STATUS_ALLOWLIST = frozenset({"ok", "warning", "decision_objects_warning_review_only", "wiki_synthesis_warning_no_apply_authority"})


def valid_evidence_status(value: Any) -> bool:
    """Explicit allowlist for dependency statuses.

    Legitimate producer states enumerated from existing tests
    (test_dependency_accepts_known_review_only_statuses) and exact current
    producer descriptors (ok / warning / decision_objects_warning_review_only):
    ok, warning, decision_objects_warning_review_only,
    wiki_synthesis_warning_no_apply_authority (review-only, from wiki-gate tests).
    Unknown/banana/hyphenated fail-open/fail-closed and non-string types reject.
    """
    return isinstance(value, str) and value.strip() in EVIDENCE_STATUS_ALLOWLIST


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def fresh_artifact_status(path_value: str, *, max_age_minutes: int) -> dict[str, Any]:
    path = Path(path_value)
    full = path if path.is_absolute() else ROOT / path
    data = load_json(full)
    generated_at = parse_generated_at(data.get("generated_at_utc"))
    validation_status = as_dict(data.get("validation")).get("status")
    now = datetime.now(timezone.utc)
    age_minutes = None if generated_at is None else round((now - generated_at).total_seconds() / 60, 2)
    fresh = (
        full.exists()
        and bool(data)
        and data.get("status") == "ok"
        and validation_status == "ok"
        and age_minutes is not None
        and 0 <= age_minutes <= max_age_minutes
    )
    return {
        "path": str(path_value),
        "exists": full.exists(),
        "status": data.get("status"),
        "validation_status": validation_status,
        "generated_at_utc": data.get("generated_at_utc"),
        "age_minutes": age_minutes,
        "fresh": fresh,
        "stale_reason": None if fresh else "not_fresh_validated_or_outside_reuse_window",
    }


def fresh_artifacts_ready(spec: dict[str, Any], *, max_age_minutes: int) -> tuple[bool, list[dict[str, Any]]]:
    artifact_paths = [str(path) for path in spec.get("reuse_fresh_artifacts") or []]
    if not artifact_paths:
        return False, []
    statuses = [fresh_artifact_status(path, max_age_minutes=max_age_minutes) for path in artifact_paths]
    if not all(row.get("fresh") for row in statuses):
        return False, statuses
    # A fresh packet timestamp is not fresh evidence: rerun the producer when
    # its own script changed after the artifact was generated, otherwise a
    # code fix would keep greening on pre-fix output.
    script = producer_script_for_command(spec)
    if script is not None:
        changed = [
            script_changed_since(script, parse_generated_at(row.get("generated_at_utc")))
            for row in statuses
        ]
        if any(changed):
            for row, was_changed in zip(statuses, changed):
                row["fresh"] = False
                row["stale_reason"] = (
                    "producer_script_changed_since_artifact"
                    if was_changed
                    else "sibling_artifact_producer_script_changed"
                )
            return False, statuses
    return True, statuses


def dependency_status(path_value: str, *, max_age_minutes: int) -> dict[str, Any]:
    """Honest producer-evidence check for consumer guards.

    Fail-closed allowlist: presence, non-blank marker-free string status,
    validation exactly ok-or-warning (review-only warnings such as RSI
    maturity or decision-compiler review-only state remain warnings, never
    failures), age within the producer contract, and producer script
    unchanged since the artifact was generated.
    """
    full = resolve_under_root(path_value)
    data = load_json(full)
    generated_at = parse_generated_at(data.get("generated_at_utc"))
    status_value = data.get("status")
    validation_status = as_dict(data.get("validation")).get("status")
    now = datetime.now(timezone.utc)
    age_minutes = None if generated_at is None else round((now - generated_at).total_seconds() / 60, 2)
    producer_rel = DEPENDENCY_PRODUCER_SCRIPTS.get(normalize_rel(path_value))
    code_changed = (
        script_changed_since(ROOT / producer_rel, generated_at)
        if producer_rel is not None
        else False
    )
    if not full.exists():
        reason: str | None = "missing_dependency_artifact"
    elif not data:
        reason = "unreadable_dependency_artifact"
    elif not valid_evidence_status(status_value):
        reason = "dependency_status_missing_or_blank" if not (isinstance(status_value, str) and status_value.strip()) else "dependency_status_blocked"
    elif validation_status not in {"ok", "warning"}:
        reason = "dependency_validation_not_ok"
    elif generated_at is None or age_minutes is None or age_minutes < 0 or age_minutes > max_age_minutes:
        reason = "stale_dependency_artifact"
    elif code_changed:
        reason = "dependency_producer_code_changed"
    else:
        reason = None
    return {
        "path": str(path_value),
        "exists": full.exists(),
        "status": status_value,
        "validation_status": validation_status,
        "generated_at_utc": data.get("generated_at_utc"),
        "age_minutes": age_minutes,
        "producer_script": producer_rel,
        "producer_code_changed": code_changed,
        "fresh": reason is None,
        "reason": reason,
    }


def dependencies_ready(spec: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    required = [str(path) for path in spec.get("requires_fresh_artifacts") or []]
    if not required:
        return True, []
    statuses = [
        dependency_status(
            path,
            max_age_minutes=DEPENDENCY_MAX_AGE_MINUTES.get(normalize_rel(path), WF74_REUSE_WINDOW_MINUTES),
        )
        for path in required
    ]
    return all(row.get("fresh") for row in statuses), statuses


# Targeted recovery before the single retry (2026-09-24). The retrieval
# scorecard checks the wiki packet's embedded OS2 descriptor (max 24h), but the
# wiki synthesis that refreshes it runs after the scorecard. One aborted night
# therefore blocked every later night. When the scorecard fails ONLY on the
# wiki-packet freshness fixtures, rebuild pages and packet together (a
# packet-only write desyncs page hashes and breaks the status card), then retry.
# Any other failure retries unchanged. Normal nights never run this.
WIKI_FRESHNESS_FIXTURE_IDS = frozenset({"rq_freshness_current_descriptor_accepted"})
RETRIEVAL_SCORECARD_REL = "tmp/retrieval-quality-scorecard.json"
WIKI_SYNTHESIS_RECOVERY = {
    "id": "wf88_wiki_synthesis_recovery",
    "command": [sys.executable, "scripts\\wf88_wiki_synthesis_packet.py", "--write", "--write-md", "--write-wiki"],
}


def recovery_for_failure(spec: dict[str, Any]) -> dict[str, Any] | None:
    if spec.get("id") != "retrieval_quality_scorecard":
        return None
    fixtures = load_json(resolve_under_root(RETRIEVAL_SCORECARD_REL)).get("fixtures")
    if not isinstance(fixtures, list):
        return None
    failed = {
        str(item.get("fixture_id"))
        for item in fixtures
        if isinstance(item, dict) and item.get("status") != "pass"
    }
    if failed and failed <= WIKI_FRESHNESS_FIXTURE_IDS:
        return WIKI_SYNTHESIS_RECOVERY
    return None


def run_recovery(spec: dict[str, Any], *, timeout_seconds: int) -> dict[str, Any]:
    command = [str(part) for part in spec["command"]]
    record: dict[str, Any] = {"id": spec["id"], "command": command, "returncode": None}
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=timeout_seconds, check=False
        )
        record["returncode"] = completed.returncode
        record["stdout_tail"] = tail(completed.stdout, 400)
        record["stderr_tail"] = tail(completed.stderr, 400)
    except subprocess.TimeoutExpired:
        record["returncode"] = "timeout"
    except OSError as exc:
        record["returncode"] = "launch_error"
        record["stderr_tail"] = tail(str(exc), 400)
    record["duration_seconds"] = round(time.monotonic() - start, 2)
    return record


def run_sequence(
    commands: list[dict[str, Any]],
    *,
    execute: bool,
    timeout_seconds: int,
    reuse_fresh_wf74: bool = True,
    fresh_max_age_minutes: int = WF74_REUSE_WINDOW_MINUTES,
    retry_limit: int = 0,
    retry_wait_seconds: float = STEP_RETRY_WAIT_SECONDS,
) -> tuple[list[dict[str, Any]], bool]:
    results: list[dict[str, Any]] = []
    ok = True
    for index, spec in enumerate(commands, 1):
        command = [str(part) for part in spec.get("command", [])]
        row = {
            "index": index,
            "id": spec.get("id"),
            "command": command,
            "executed": execute,
            "returncode": None,
            "duration_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
            "skipped": False,
            "skip_reason": None,
            "blocked": False,
            "block_reason": None,
            "timeout": False,
            "reuse_artifacts": [],
            "reuse_window_minutes": None,
            "dependencies": [],
        }
        if execute:
            deps_ok, dep_statuses = dependencies_ready(spec)
            row["dependencies"] = dep_statuses
            if not deps_ok:
                reasons = ";".join(
                    f"{entry.get('path')}:{entry.get('reason')}"
                    for entry in dep_statuses
                    if not entry.get("fresh")
                )
                row["executed"] = False
                row["blocked"] = True
                row["block_reason"] = f"stale_or_missing_producer_evidence:{reasons}"
                results.append(row)
                ok = False
                break
        if execute and reuse_fresh_wf74:
            reuse_window_minutes = spec.get("reuse_max_age_minutes")
            if reuse_window_minutes is None:
                reuse_window_minutes = fresh_max_age_minutes
            reusable, artifact_statuses = fresh_artifacts_ready(spec, max_age_minutes=reuse_window_minutes)
            row["reuse_window_minutes"] = reuse_window_minutes
            row["reuse_artifacts"] = artifact_statuses
            if reusable:
                row["executed"] = False
                row["returncode"] = 0
                row["skipped"] = True
                row["skip_reason"] = "fresh_validated_wf74_artifact_reused"
                results.append(row)
                continue
        if not execute:
            results.append(row)
            continue
        attempts = 0
        first_attempt: dict[str, Any] | None = None
        while True:
            start = time.monotonic()
            try:
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                row["duration_seconds"] = round(time.monotonic() - start, 2)
                row["timeout"] = True
                row["returncode"] = "timeout"
                parts = [f"command_timeout_after_{timeout_seconds}s: {' '.join(command)}"]
                if exc.stdout:
                    row["stdout_tail"] = tail(str(exc.stdout))
                if exc.stderr:
                    parts.append(str(exc.stderr))
                row["stderr_tail"] = tail("\n".join(parts))
                break
            except OSError as exc:
                row["duration_seconds"] = round(time.monotonic() - start, 2)
                row["returncode"] = "launch_error"
                row["stderr_tail"] = tail(f"command_launch_error: {' '.join(command)}: {exc}")
                break
            row["duration_seconds"] = round(time.monotonic() - start, 2)
            row["returncode"] = completed.returncode
            row["stdout_tail"] = tail(completed.stdout)
            row["stderr_tail"] = tail(completed.stderr)
            if completed.returncode != 0 and attempts < retry_limit:
                if first_attempt is None:
                    first_attempt = {
                        "returncode": completed.returncode,
                        "stdout_tail": row["stdout_tail"],
                        "stderr_tail": row["stderr_tail"],
                    }
                recovery = recovery_for_failure(spec)
                if recovery is not None:
                    row["recovery"] = run_recovery(recovery, timeout_seconds=timeout_seconds)
                attempts += 1
                time.sleep(retry_wait_seconds)
                continue
            break
        if first_attempt is not None:
            row["retry_attempted"] = True
            row["retry_attempts"] = attempts
            row["retry_wait_seconds"] = retry_wait_seconds
            row["first_attempt_returncode"] = first_attempt["returncode"]
            row["first_attempt_stdout_tail"] = first_attempt["stdout_tail"]
            row["first_attempt_stderr_tail"] = first_attempt["stderr_tail"]
        results.append(row)
        if row.get("returncode") != 0:
            ok = False
            break
    return results, ok


def build_packet(
    *,
    execute: bool,
    timeout_seconds: int,
    reuse_fresh_wf74: bool = True,
    fresh_max_age_minutes: int = WF74_REUSE_WINDOW_MINUTES,
) -> dict[str, Any]:
    results, ok = run_sequence(
        COMMANDS,
        execute=execute,
        timeout_seconds=timeout_seconds,
        reuse_fresh_wf74=reuse_fresh_wf74,
        fresh_max_age_minutes=fresh_max_age_minutes,
        retry_limit=STEP_RETRY_LIMIT,
        retry_wait_seconds=STEP_RETRY_WAIT_SECONDS,
    )
    skipped = [row for row in results if row.get("skipped")]
    retried = [row for row in results if row.get("retry_attempted")]
    recovered = [row for row in retried if row.get("returncode") == 0]
    failed = next((row for row in results if row.get("returncode") not in {0, None}), None)
    blocked = next((row for row in results if row.get("blocked")), None)
    errors: list[str] = []
    if failed is not None:
        errors.append("command_failed")
        if failed.get("timeout"):
            errors.append("command_timeout")
        if failed.get("returncode") == "launch_error":
            errors.append("command_launch_error")
    if blocked is not None:
        errors.append("stale_dependency_blocked")
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if ok else "blocked",
        "purpose": "Daily WF88 actionability/front-door refresh runner for cron.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "execute": execute,
        "command_count": len(COMMANDS),
        "skipped_count": len(skipped),
        "skipped_command_ids": [row.get("id") for row in skipped],
        "retried_count": len(retried),
        "recovered_after_retry_count": len(recovered),
        "reuse_fresh_wf74": reuse_fresh_wf74,
        "fresh_max_age_minutes": fresh_max_age_minutes,
        "completed_count": sum(
            1
            for row in results
            if row.get("returncode") == 0 or (not row.get("executed") and not row.get("blocked"))
        ),
        "failed_command": failed,
        "blocked_command": blocked,
        "results": results,
        "validation": {"status": "ok" if ok else "blocked", "errors": errors, "warnings": []},
    }
    return packet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-reuse-fresh-wf74", action="store_true", help="Rerun WF74 producer steps even when fresh validated artifacts already exist.")
    parser.add_argument("--fresh-max-age-minutes", type=int, default=WF74_REUSE_WINDOW_MINUTES)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet(
        execute=not args.dry_run,
        timeout_seconds=args.timeout_seconds,
        reuse_fresh_wf74=not args.no_reuse_fresh_wf74,
        fresh_max_age_minutes=args.fresh_max_age_minutes,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, packet)
    print(
        f"status={packet.get('status')} completed={packet.get('completed_count')}/{packet.get('command_count')} "
        f"skipped={packet.get('skipped_count')} out={out}"
    )
    failed = packet.get("failed_command")
    if failed:
        print(f"failed={failed.get('id')} returncode={failed.get('returncode')}")
        if failed.get("stderr_tail"):
            print(failed.get("stderr_tail"))
    blocked = packet.get("blocked_command")
    if blocked:
        print(f"blocked={blocked.get('id')} reason={blocked.get('block_reason')}")
    if args.validate and packet.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

