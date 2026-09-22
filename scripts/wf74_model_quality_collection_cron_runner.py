#!/usr/bin/env python3
"""Cron runner for WF74 model-quality and alerts-OS evidence collection.

This keeps the scheduled path to one stable command. It refreshes operational
telemetry, model/run attribution coverage, recommendation outcomes,
and the WF74 scorecard, then records cron-control proof.
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

from lib.pm_control_reader import pm_implementation_job_queue
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf74_improvement_opportunity_queue import select_actionable_planning_gap


def project_planning_quality(planning_signal: dict[str, Any]) -> dict[str, Any]:
    """Project raw planning history separately from operational actionable debt.

    Raw history is preserved verbatim; the operational actionable status is
    trusted only when the signal schema is exact, counts are strict non-bool
    ints, and reconciliation is exact, otherwise fail closed to raw with a
    warning and never a clean quality/performance claim.
    Single source of selector meaning: wf74_improvement_opportunity_queue.
    """
    # Schema-exact trust: only veritas.planning_quality_signal.v1 may project a verified partition.
    # Single source of meaning for the fail-closed selector: wf74_improvement_opportunity_queue.
    selection = select_actionable_planning_gap(planning_signal)
    if planning_signal.get("schema") != "veritas.planning_quality_signal.v1":
        raw_gap = int(selection["raw_gap_count"])
        warning = str(selection.get("warning") or "partition_fields_unavailable")
        selection = {
            "selected_gap_count": raw_gap,
            "raw_gap_count": raw_gap,
            "source": "raw_gap_fallback",
            "warning": "planning_signal_schema_not_exact; " + warning,
            "actionable_gap_count": planning_signal.get("plan_followthrough_actionable_gap_count"),
            "terminal_unavailable_count": planning_signal.get("plan_followthrough_terminal_unavailable_count"),
            "repaired_accepted_count": planning_signal.get("plan_followthrough_repaired_accepted_count"),
            "partitioned_gap_row_count": planning_signal.get("partitioned_gap_row_count"),
            "partition_reconciliation_ok": planning_signal.get("partition_reconciliation_ok"),
        }
    if selection["source"] == "actionable_partition_verified":
        operational_status: Any = planning_signal.get("actionable_status") or (
            "attention" if int(selection["selected_gap_count"]) else "ok"
        )
    else:
        operational_status = "unverified_fallback"
    return {
        "planning_quality_gap_count_raw": int(selection["raw_gap_count"]),
        "planning_quality_gap_count_selected": int(selection["selected_gap_count"]),
        "planning_quality_gap_source": selection["source"],
        "planning_quality_actionable_gap_count": selection.get("actionable_gap_count"),
        "planning_quality_terminal_unavailable_count": selection.get("terminal_unavailable_count"),
        "planning_quality_repaired_accepted_count": selection.get("repaired_accepted_count"),
        "planning_quality_partitioned_gap_row_count": selection.get("partitioned_gap_row_count"),
        "planning_quality_partition_reconciliation_ok": selection.get("partition_reconciliation_ok"),
        "planning_quality_actionable_status": operational_status,
        "planning_quality_signal_schema": planning_signal.get("schema"),
        "planning_gap_selection_warning": selection.get("warning"),
    }

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "wf74-model-quality-collection-cron-runner.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "wf74.model_quality_collection_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_or_content_capture_allowed": False,
    "external_export_allowed": False,
    "model_ranking_claim": False,
    "investment_correctness_claim": False,
    "recommendation_outcome_grade_assignment_allowed": False,
    "owner_approval_inferred": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
}

NON_BLOCKING_STEP_NAMES = {
    "cron_control_packet",
    "wf74_outcome_feedback_ingestor",
    "wf74_prompt_variant_ledger",
    "otel_ops_control",
    "veritas_harness_scorecard_fast",
    "wf74_self_prompt_generator",
    "wf74_telemetry_critique_engine",
    "wf74_proposal_dispatcher",
}

DOMAIN_ATTENTION_STEP_NAMES: set[str] = set()

DOMAIN_NONFATAL_CRITICAL_DETAILS: set[str] = set()

# Transient-collision retry: scheduled bursts can overlap artifact writers,
# making an otherwise-green validation step read a mid-rewrite artifact once.
# One bounded retry (with a short wait) absorbs that class; persistent
# failures still block. Timeouts are never retried so the cron budget holds.
BLOCKING_STEP_RETRY_WAIT_SECONDS = 15.0
BLOCKING_STEP_RETRY_LIMIT = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def tail(text: str, limit: int = 1200) -> str:
    return text[-limit:] if len(text) > limit else text


def is_non_blocking_step(name: str) -> bool:
    return name in NON_BLOCKING_STEP_NAMES


def step_attention_class(name: str) -> str:
    return "domain_quality" if name in DOMAIN_ATTENTION_STEP_NAMES else "diagnostic"


def classify_step_status(name: str, returncode: int | None) -> str:
    if returncode == 0:
        return "ok"
    return "attention" if is_non_blocking_step(name) else "blocked"


def is_blocking_step_failure(step: dict[str, Any]) -> bool:
    return step.get("status") != "ok" and step.get("blocking") is not False


def classified_domain_blocker_reason(payload: dict[str, Any]) -> str | None:
    return None


def is_classified_domain_blocker(payload: dict[str, Any]) -> bool:
    return classified_domain_blocker_reason(payload) is not None


def scheduler_exit_decision(
    payload: dict[str, Any],
    validation: dict[str, Any],
    *,
    allow_domain_blocked_exit_zero: bool,
) -> dict[str, Any]:
    critical_details = [
        str(finding.get("detail"))
        for finding in validation.get("findings", [])
        if as_dict(finding).get("severity") == "critical"
    ]
    if not critical_details:
        return {
            "status": "ok",
            "returncode": 0,
            "reason": "no_critical_validation_findings",
            "critical_details": [],
            "domain_blocked_nonfatal": False,
        }
    if (
        allow_domain_blocked_exit_zero
        and classified_domain_blocker_reason(payload)
        and set(critical_details).issubset(DOMAIN_NONFATAL_CRITICAL_DETAILS)
    ):
        reason = classified_domain_blocker_reason(payload)
        return {
            "status": "domain_blocked_nonfatal",
            "returncode": 0,
            "reason": reason,
            "critical_details": critical_details,
            "domain_blocked_nonfatal": True,
        }
    return {
        "status": "critical",
        "returncode": 1,
        "reason": "technical_or_unclassified_critical_validation_findings",
        "critical_details": critical_details,
        "domain_blocked_nonfatal": False,
    }


def command_plan(include_harness: bool) -> list[tuple[str, list[str], int]]:
    plan: list[tuple[str, list[str], int]] = [
        ("otel_tool_workflow_metadata", [sys.executable, "scripts\\otel_tool_workflow_metadata.py", "--write", "--write-md", "--validate"], 90),
        ("otel_ops_control", [sys.executable, "scripts\\otel_ops_control.py", "--write", "--write-db", "--multi-window", "--validate"], 180),
        ("otel_runtime_metadata_probe", [sys.executable, "scripts\\otel_runtime_metadata_probe.py", "--write", "--write-md", "--validate"], 90),
        ("changed_file_validator_router", [sys.executable, "scripts\\changed_file_validator_router.py", "--validate"], 90),
        ("coding_outcome_ledger", [sys.executable, "scripts\\coding_outcome_ledger.py", "--write", "--validate"], 90),
        ("validator_timing_ledger_normal", [sys.executable, "scripts\\validator_timing_ledger.py", "--profile", "normal", "--write", "--validate"], 240),
        ("coding_runtime_kpi_probe", [sys.executable, "scripts\\coding_runtime_kpi_probe.py", "--write", "--write-md", "--validate"], 90),
        ("cron_spark_canary_monitor", [sys.executable, "scripts\\cron_spark_canary_monitor.py", "--write", "--validate"], 120),
        (
            "model_run_ledger",
            [
                sys.executable,
                "scripts\\model_run_ledger.py",
                "--write",
                "--write-md",
                "--validate",
                "--cron-job-limit",
                "8",
                "--cron-run-limit",
                "2",
                "--cron-list-timeout",
                "15",
                "--cron-runs-timeout",
                "8",
            ],
            120,
        ),
        ("token_usage_ledger", [sys.executable, "scripts\\token_usage_ledger.py", "--write", "--write-md", "--validate", "--skip-isolated-agent-usage-cost"], 240),
        (
            "recommendation_performance_digest",
            [sys.executable, "scripts\\finance_decision_performance_digest.py", "--write", "--write-md", "--validate"],
            120,
        ),
        (
            "alerts_os_pivot_validator",
            [sys.executable, "scripts\\alerts_os_pivot_validator.py", "--write", "--validate"],
            120,
        ),
        ("model_learning_metadata_ledger", [sys.executable, "scripts\\model_learning_metadata_ledger.py", "--write", "--write-md", "--validate"], 120),
        ("otel_learning_loop", [sys.executable, "scripts\\otel_learning_loop.py", "--write", "--write-md", "--validate"], 90),
        ("model_quality_scorecard", [sys.executable, "scripts\\model_quality_scorecard.py", "--write", "--write-md", "--validate"], 120),
        ("workflow_advancement_scorecard", [sys.executable, "scripts\\workflow_advancement_scorecard.py", "--write", "--validate"], 120),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--validate"], 180),
        ("wf74_cron_duplication_audit", [sys.executable, "scripts\\wf74_cron_duplication_audit.py", "--write", "--validate"], 90),
        ("cron_control_packet", [sys.executable, "scripts\\cron_control_packet.py", "--write", "--validate"], 180),
        (
            "wf74_improvement_opportunity_queue",
            [sys.executable, "scripts\\wf74_improvement_opportunity_queue.py", "--write", "--write-md", "--validate"],
            90,
        ),
        ("improvement_ledger", [sys.executable, "scripts\\improvement_ledger.py", "--write", "--write-md", "--validate"], 90),
        (
            "wf74_reflection_to_proposal_autopilot",
            [sys.executable, "scripts\\wf74_reflection_to_proposal_autopilot.py", "--write", "--write-md", "--validate"],
            90,
        ),
        (
            "wf74_auto_patch_proposer",
            [sys.executable, "scripts\\wf74_auto_patch_proposer.py", "--write", "--write-md", "--validate"],
            90,
        ),
        (
            "wf74_telemetry_critique_engine",
            [sys.executable, "scripts\\wf74_telemetry_critique_engine.py", "--write", "--validate"],
            90,
        ),
        (
            "wf74_self_prompt_generator",
            [sys.executable, "scripts\\wf74_self_prompt_generator.py", "--write", "--validate"],
            90,
        ),
        (
            "wf74_prompt_variant_ledger",
            [sys.executable, "scripts\\wf74_prompt_variant_ledger.py", "--write", "--validate"],
            90,
        ),
        (
            "wf74_outcome_feedback_ingestor",
            [sys.executable, "scripts\\wf74_outcome_feedback_ingestor.py", "--write", "--validate"],
            90,
        ),
        (
            "otel_recommendation_closeout",
            [sys.executable, "scripts\\otel_recommendation_closeout.py", "--write", "--write-md", "--validate"],
            90,
        ),
        ("wf74_autonomy_work_router", [sys.executable, "scripts\\wf74_autonomy_work_router.py", "--write", "--validate"], 90),
        (
            "pm_implementation_job_queue",
            [sys.executable, "scripts\\pm_implementation_job_queue.py", "--write", "--write-db", "--validate"],
            90,
        ),
        (
            "owner_gated_action_review_queue",
            [sys.executable, "scripts\\owner_gated_action_review_queue.py", "--write", "--write-md", "--validate"],
            90,
        ),
        (
            "wf74_decision_docket",
            [sys.executable, "scripts\\wf74_decision_docket.py", "--write", "--write-md", "--validate"],
            90,
        ),
        (
            "wf74_proposal_dispatcher",
            [sys.executable, "scripts\\wf74_proposal_dispatcher.py", "--write", "--write-md", "--validate"],
            90,
        ),
        ("artifact_index_incremental", [sys.executable, "scripts\\artifact_index.py", "incremental"], 180),
        ("artifact_index_validate", [sys.executable, "scripts\\artifact_index.py", "validate"], 180),
    ]
    if include_harness:
        plan.append(("veritas_harness_scorecard_fast", [sys.executable, "scripts\\veritas_harness_scorecard.py", "--fast", "--write", "--validate"], 240))
        plan.append(("model_quality_scorecard_after_harness", [sys.executable, "scripts\\model_quality_scorecard.py", "--write", "--write-md", "--validate"], 120))
    plan.append(("pm_control_packet", [sys.executable, "scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"], 180))
    return plan


def run_step(name: str, command: list[str], timeout: int, step_index: int | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        status = classify_step_status(name, None)
        return {
            "step_index": step_index,
            "name": name,
            "command": command,
            "status": status,
            "blocking": not is_non_blocking_step(name),
            "returncode": None,
            "failure_kind": "timeout",
            "attention_class": step_attention_class(name) if status == "attention" else None,
            "timeout_seconds": timeout,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout or ""),
            "stderr_tail": tail(exc.stderr or ""),
        }
    status = classify_step_status(name, completed.returncode)
    return {
        "step_index": step_index,
        "name": name,
        "command": command,
        "status": status,
        "blocking": not is_non_blocking_step(name),
        "returncode": completed.returncode,
        "failure_kind": None if completed.returncode == 0 else "nonzero_returncode",
        "attention_class": step_attention_class(name) if status == "attention" else None,
        "timeout_seconds": timeout,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(completed.stdout or ""),
        "stderr_tail": tail(completed.stderr or ""),
    }


def artifact_status(path: str) -> dict[str, Any]:
    full = ROOT / path
    data = as_dict(load_json_artifact(full))
    return {
        "path": path,
        "exists": full.exists(),
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
    }


def execute_plan(include_harness: bool) -> list[dict[str, Any]]:
    """Run the command plan with one bounded retry per blocking step.

    A blocking step that fails with a nonzero returncode gets exactly
    BLOCKING_STEP_RETRY_LIMIT retries after BLOCKING_STEP_RETRY_WAIT_SECONDS.
    The first attempt's evidence is preserved on the retried step record.
    Timeout failures are not retried; they block immediately.
    """
    steps: list[dict[str, Any]] = []
    for index, (name, command, timeout) in enumerate(command_plan(include_harness), start=1):
        step = run_step(name, command, timeout, index)
        if (
            is_blocking_step_failure(step)
            and step.get("failure_kind") == "nonzero_returncode"
            and BLOCKING_STEP_RETRY_LIMIT > 0
        ):
            time.sleep(BLOCKING_STEP_RETRY_WAIT_SECONDS)
            retry = run_step(name, command, timeout, index)
            retry["retry_attempted"] = True
            retry["retry_wait_seconds"] = BLOCKING_STEP_RETRY_WAIT_SECONDS
            retry["first_attempt_returncode"] = step.get("returncode")
            retry["first_attempt_stdout_tail"] = step.get("stdout_tail")
            retry["first_attempt_stderr_tail"] = step.get("stderr_tail")
            step = retry
        steps.append(step)
        if is_blocking_step_failure(step):
            break
    return steps


def build_payload(steps: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = [step for step in steps if is_blocking_step_failure(step)]
    attention = [step for step in steps if step.get("status") != "ok" and step.get("blocking") is False]
    domain_attention = [step for step in attention if step.get("attention_class") == "domain_quality"]
    diagnostic_attention = [step for step in attention if step.get("attention_class") != "domain_quality"]
    retried_steps = [step for step in steps if step.get("retry_attempted")]
    recovered_steps = [step for step in retried_steps if step.get("status") == "ok"]
    timed_out = [step for step in steps if step.get("failure_kind") == "timeout"]
    completed_steps = [step for step in steps if step.get("status") == "ok"]
    last_completed_step = completed_steps[-1] if completed_steps else None
    artifacts = [
        artifact_status("tmp/otel-ops-control.json"),
        artifact_status("tmp/otel-ops-window-summary.json"),
        artifact_status("tmp/otel-runtime-metadata-probe.json"),
        artifact_status("tmp/otel-tool-workflow-metadata.json"),
        artifact_status("tmp/otel-field-depth-limited-owner-packet.json"),
        artifact_status("tmp/changed-file-validator-router.json"),
        artifact_status("tmp/coding-outcome-ledger-current.json"),
        artifact_status("tmp/validator-timing-ledger.json"),
        artifact_status("tmp/coding-runtime-kpi-probe.json"),
        artifact_status("tmp/cron-spark-canary-monitor.json"),
        artifact_status("tmp/model-run-ledger-current.json"),
        artifact_status("tmp/token-usage-ledger-current.json"),
        artifact_status("tmp/model-learning-metadata-ledger.json"),
        artifact_status("tmp/otel-learning-loop.json"),
        artifact_status("tmp/finance-decision-performance-digest.json"),
        artifact_status("tmp/finance-sql-canon-access-validation.json"),
        artifact_status("tmp/intraday-alerts/quote-snapshot-proof.json"),
        artifact_status("tmp/alert-level-freshness-controller.json"),
        artifact_status("tmp/finance-alert-os-digest.json"),
        artifact_status("tmp/alerts-os-pivot-validator.json"),
        artifact_status("tmp/model-quality-scorecard.json"),
        artifact_status("tmp/wf74-improvement-opportunity-queue.json"),
        artifact_status("tmp/improvement-ledger-current.json"),
        artifact_status("tmp/wf74-reflection-to-proposal-autopilot.json"),
        artifact_status("tmp/wf74-auto-patch-proposer.json"),
        artifact_status("tmp/wf74-telemetry-critique.json"),
        artifact_status("tmp/wf74-self-prompt-review-packet.json"),
        artifact_status("tmp/wf74-prompt-variant-ledger.json"),
        artifact_status("tmp/wf74-feedback-ingest.json"),
        artifact_status("tmp/workflow-advancement-scorecard.json"),
        artifact_status("tmp/workflow-blocker-followups.json"),
        artifact_status("tmp/otel-recommendation-closeout.json"),
        artifact_status("tmp/wf74-autonomy-work-router.json"),
        artifact_status("tmp/cron-migration-repair-plan.json"),
        artifact_status("tmp/workflow-implementation-followup-ledger.json"),
        artifact_status("tmp/owner-gated-action-review-queue.json"),
        artifact_status("tmp/wf74-decision-docket.json"),
        artifact_status("tmp/wf74-proposal-dispatcher.json"),
        artifact_status("tmp/wf74-cron-duplication-audit.json"),
        artifact_status("tmp/cron-control-packet.json"),
        artifact_status("tmp/pm-control-packet.json"),
    ]
    model_run = as_dict(load_json_artifact(TMP / "model-run-ledger-current.json"))
    token_usage = as_dict(load_json_artifact(TMP / "token-usage-ledger-current.json"))
    learning_ledger = as_dict(load_json_artifact(TMP / "model-learning-metadata-ledger.json"))
    recommendation_performance = as_dict(load_json_artifact(TMP / "finance-decision-performance-digest.json"))
    finance_sql_validation = as_dict(load_json_artifact(TMP / "finance-sql-canon-access-validation.json"))
    quote_snapshot = as_dict(load_json_artifact(TMP / "intraday-alerts" / "quote-snapshot-proof.json"))
    alert_controller = as_dict(load_json_artifact(TMP / "alert-level-freshness-controller.json"))
    alert_digest = as_dict(load_json_artifact(TMP / "finance-alert-os-digest.json"))
    alerts_os_pivot = as_dict(load_json_artifact(TMP / "alerts-os-pivot-validator.json"))
    model_quality = as_dict(load_json_artifact(TMP / "model-quality-scorecard.json"))
    duplication_audit = as_dict(load_json_artifact(TMP / "wf74-cron-duplication-audit.json"))
    model_summary = as_dict(model_run.get("summary"))
    token_usage_summary = as_dict(token_usage.get("summary"))
    recommendation_summary = as_dict(recommendation_performance.get("recommendation_outcomes"))
    alert_controller_summary = as_dict(alert_controller.get("summary"))
    alert_digest_summary = as_dict(alert_digest.get("summary"))
    duplication_summary = as_dict(duplication_audit.get("summary"))
    otel_window_summary = as_dict(load_json_artifact(TMP / "otel-ops-window-summary.json"))
    otel_ops = as_dict(load_json_artifact(TMP / "otel-ops-control.json"))
    otel_field_depth = as_dict(load_json_artifact(TMP / "otel-field-depth-limited-owner-packet.json"))
    otel_runtime_probe = as_dict(load_json_artifact(TMP / "otel-runtime-metadata-probe.json"))
    otel_tool_workflow = as_dict(load_json_artifact(TMP / "otel-tool-workflow-metadata.json"))
    otel_learning_loop = as_dict(load_json_artifact(TMP / "otel-learning-loop.json"))
    coding_outcome = as_dict(load_json_artifact(TMP / "coding-outcome-ledger-current.json"))
    coding_runtime_probe = as_dict(load_json_artifact(TMP / "coding-runtime-kpi-probe.json"))
    opportunity_queue = as_dict(load_json_artifact(TMP / "wf74-improvement-opportunity-queue.json"))
    improvement_ledger = as_dict(load_json_artifact(TMP / "improvement-ledger-current.json"))
    proposal_autopilot = as_dict(load_json_artifact(TMP / "wf74-reflection-to-proposal-autopilot.json"))
    auto_patch_proposer = as_dict(load_json_artifact(TMP / "wf74-auto-patch-proposer.json"))
    prompt_variant_ledger = as_dict(load_json_artifact(TMP / "wf74-prompt-variant-ledger.json"))
    outcome_feedback = as_dict(load_json_artifact(TMP / "wf74-feedback-ingest.json"))
    workflow_scorecard = as_dict(load_json_artifact(TMP / "workflow-advancement-scorecard.json"))
    workflow_followups = as_dict(load_json_artifact(TMP / "workflow-blocker-followups.json"))
    otel_recommendation_closeout = as_dict(load_json_artifact(TMP / "otel-recommendation-closeout.json"))
    autonomy_router = as_dict(load_json_artifact(TMP / "wf74-autonomy-work-router.json"))
    pm_control = as_dict(load_json_artifact(TMP / "pm-control-packet.json"))
    pm_job_queue = pm_implementation_job_queue()
    owner_gated_queue = as_dict(load_json_artifact(TMP / "owner-gated-action-review-queue.json"))
    decision_docket = as_dict(load_json_artifact(TMP / "wf74-decision-docket.json"))
    proposal_dispatcher = as_dict(load_json_artifact(TMP / "wf74-proposal-dispatcher.json"))
    coding_runtime_kpis = as_dict(coding_runtime_probe.get("kpis"))
    coding_outcome_summary = as_dict(coding_outcome.get("ledger_summary"))
    planning_signal = as_dict(coding_outcome_summary.get("planning_quality_signal"))
    planning_projection = project_planning_quality(planning_signal)
    opportunity_summary = as_dict(opportunity_queue.get("summary"))
    improvement_ledger_summary = as_dict(improvement_ledger.get("summary"))
    improvement_kpis = as_dict(improvement_ledger.get("learning_loop_kpis"))
    proposal_summary = as_dict(proposal_autopilot.get("summary"))
    auto_patch_summary = as_dict(auto_patch_proposer.get("summary"))
    prompt_variant_summary = as_dict(prompt_variant_ledger.get("summary"))
    outcome_feedback_summary = as_dict(outcome_feedback.get("summary"))
    workflow_scorecard_summary = as_dict(workflow_scorecard.get("summary"))
    workflow_followup_summary = as_dict(workflow_followups.get("summary"))
    closeout_summary = as_dict(otel_recommendation_closeout.get("summary"))
    autonomy_router_summary = as_dict(autonomy_router.get("summary"))
    autonomy_router_kpis = as_dict(autonomy_router.get("kpis"))
    pm_job_queue_summary = as_dict(pm_job_queue.get("summary"))
    pm_control_summary = as_dict(pm_control.get("summary"))
    owner_gated_summary = as_dict(owner_gated_queue.get("summary"))
    decision_docket_summary = as_dict(decision_docket.get("summary"))
    proposal_dispatcher_summary = as_dict(proposal_dispatcher.get("summary"))
    otel_windows = [row for row in otel_window_summary.get("windows", []) if isinstance(row, dict)]
    otel_drift = as_dict(otel_ops.get("drift"))
    otel_tool_workflow_summary = as_dict(otel_tool_workflow.get("summary"))
    otel_learning_summary = as_dict(otel_learning_loop.get("learning_summaries"))
    readiness_gates = [
        gate for gate in (model_quality.get("readiness_gates") or [])
        if isinstance(gate, dict)
    ]
    blocked_quality_gates = [
        gate.get("gate") for gate in readiness_gates
        if gate.get("status") == "blocked"
    ]
    claim_gated_quality_gates = [
        gate.get("gate") for gate in readiness_gates
        if gate.get("status") in {"claim_maturity_gated", "evidence_maturity_gated"}
    ]
    runner_status = "blocked" if blocked else ("attention" if attention else "ok")
    quality_gate_status = "blocked" if blocked_quality_gates else ("claim_gated" if claim_gated_quality_gates else "ok")
    backlog_status = str(improvement_ledger_summary.get("escalation_level") or "unknown")
    anti_theater_status = str(improvement_kpis.get("anti_theater_status") or "unknown")
    decision_quality_status = (
        "blocked"
        if "recommendation_outcome_history" in blocked_quality_gates
        else (
            "active_measurement_only"
            if "recommendation_outcome_history" in claim_gated_quality_gates
            else "active"
        )
    )
    learning_environment_status = {
        "schema": "wf74.learning_environment_status.v1",
        "runner_status": runner_status,
        "quality_gate_status": quality_gate_status,
        "blocked_quality_gates": blocked_quality_gates,
        "claim_gated_quality_gates": claim_gated_quality_gates,
        "backlog_status": backlog_status,
        "anti_theater_status": anti_theater_status,
        "closure_rate": improvement_kpis.get("closure_rate"),
        "applied_fix_closure_rate": improvement_kpis.get("applied_fix_closure_rate"),
        "signal_absence_closure_rate": improvement_kpis.get("signal_absence_closure_rate"),
        "latest_open_count": improvement_kpis.get("latest_open_count"),
        "latest_closed_count": improvement_kpis.get("latest_closed_count"),
        "recurring_open_count": improvement_kpis.get("recurring_open_count"),
        "high_priority_overdue_open_count": improvement_kpis.get("high_priority_overdue_open_count"),
        "model_attribution_status": "partial" if model_summary.get("model_attribution_coverage") else "missing",
        "coding_ex_post_status": "graded" if coding_outcome_summary.get("ex_post_graded_count") else "pending",
        "planning_quality_status": planning_signal.get("status") or "missing",
        "planning_actionable_status": planning_projection["planning_quality_actionable_status"],
        "planning_actionable_gap_count": planning_projection["planning_quality_actionable_gap_count"],
        "planning_gap_source": planning_projection["planning_quality_gap_source"],
        "planning_gap_selection_warning": planning_projection["planning_gap_selection_warning"],
        "decision_quality_status": decision_quality_status,
        "semantic_outcome_claim_status": (
            "maturity_gated"
            if "recommendation_outcome_history" in claim_gated_quality_gates
            else "ready" if decision_quality_status == "active" else "blocked"
        ),
        "meaning": (
            "Runner health, decision-quality gates, and improvement backlog are separate. "
            "WF74 is a real learning environment only when it keeps evidence flowing, "
            "preserves authority boundaries, and tracks proposal closure instead of only producing more proposals. "
            "Review-only recommendation outcomes activate the scorecard; semantic/predictive claims remain separately gated."
        ),
    }
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not blocked else "blocked",
        "posture": "scheduled_review_only_collection",
        "summary": {
            "steps_total": len(steps),
            "steps_ok": len([step for step in steps if step.get("status") == "ok"]),
            "steps_blocked": len(blocked),
            "steps_attention": len(attention),
            "steps_retried": len(retried_steps),
            "steps_recovered_after_retry": len(recovered_steps),
            "non_blocking_attention_steps": [step.get("name") for step in attention],
            "blocking_step_names": [step.get("name") for step in blocked],
            "technical_blocking_steps": [step.get("name") for step in blocked if step.get("attention_class") != "domain_quality"],
            "domain_attention_steps": [step.get("name") for step in domain_attention],
            "diagnostic_attention_steps": [step.get("name") for step in diagnostic_attention],
            "timed_out_steps": [step.get("name") for step in timed_out],
            "last_completed_step": last_completed_step.get("name") if last_completed_step else None,
            "last_step_name": steps[-1].get("name") if steps else None,
            "collection_runtime_budget_seconds": sum(int(step.get("timeout_seconds") or 0) for step in steps),
            "model_run_rows": model_summary.get("row_count"),
            "model_attribution_coverage": model_summary.get("model_attribution_coverage"),
            "session_attribution_coverage": model_summary.get("session_attribution_coverage"),
            "token_usage_status": token_usage.get("status"),
            "token_usage_validation": as_dict(token_usage.get("validation")).get("status"),
            "token_usage_event_count": token_usage_summary.get("token_event_count"),
            "token_usage_total_tokens": token_usage_summary.get("total_tokens"),
            "token_usage_cron_event_count": token_usage_summary.get("cron_token_event_count"),
            "token_usage_implementation_event_count": token_usage_summary.get("implementation_token_event_count"),
            "token_usage_implementation_gap_count": token_usage_summary.get("implementation_token_gap_count"),
            "token_usage_pricing_status": token_usage_summary.get("pricing_status"),
            "learning_metadata_rows": as_dict(learning_ledger.get("summary")).get("row_count"),
            "learning_metadata_domains": as_dict(learning_ledger.get("summary")).get("by_domain"),
            "learning_metadata_privacy_scan": as_dict(learning_ledger.get("summary")).get("privacy_scan_status"),
            "learning_coding_outcome_rows": as_dict(learning_ledger.get("summary")).get("coding_outcome_rows"),
            "recommendation_performance_status": recommendation_performance.get("status"),
            "recommendation_tracking_rows": recommendation_summary.get("recommendation_tracking_rows"),
            "recommendation_graded_rows": recommendation_summary.get("outcome_grade_assigned_count"),
            "guarded_sql_validation_status": finance_sql_validation.get("status"),
            "quote_snapshot_status": quote_snapshot.get("status"),
            "alert_controller_status": alert_controller.get("status"),
            "alert_controller_validation": as_dict(alert_controller.get("validation")).get("status"),
            "alert_ticker_count": alert_controller_summary.get("ticker_count"),
            "alert_state_counts": alert_controller_summary.get("alert_state_counts"),
            "recommendation_digest_status": alert_digest.get("status"),
            "recommendation_digest_validation": as_dict(alert_digest.get("validation")).get("status"),
            "recommendation_digest_ticker_count": alert_digest_summary.get("ticker_count"),
            "alerts_os_pivot_status": alerts_os_pivot.get("status"),
            "alerts_os_pivot_validation": as_dict(alerts_os_pivot.get("validation")).get("status"),
            "wf74_active_tracks": model_quality.get("active_tracks"),
            "wf74_validation_status": as_dict(model_quality.get("validation")).get("status"),
            "otel_window_summary_status": otel_window_summary.get("status"),
            "otel_drift_status": otel_drift.get("status"),
            "otel_daily_warning_or_error_count": otel_drift.get("daily_warning_or_error_count"),
            "otel_daily_vs_weekly_event_rate_ratio": otel_drift.get("daily_vs_weekly_event_rate_ratio"),
            "otel_field_depth_packet_status": otel_field_depth.get("status"),
            "otel_runtime_probe_status": otel_runtime_probe.get("status"),
            "otel_runtime_metadata_observed": as_dict(otel_runtime_probe.get("summary")).get("runtime_metadata_observed"),
            "otel_runtime_allowed_field_count": as_dict(otel_runtime_probe.get("summary")).get("allowed_field_count"),
            "otel_tool_workflow_metadata_status": otel_tool_workflow.get("status"),
            "otel_tool_workflow_metadata_rows": otel_tool_workflow_summary.get("row_count"),
            "otel_tool_workflow_unique_tool_count": otel_tool_workflow_summary.get("unique_tool_count"),
            "otel_tool_workflow_failed_or_blocked_count": otel_tool_workflow_summary.get("failed_or_blocked_count"),
            "otel_tool_workflow_session_attributed_count": otel_tool_workflow_summary.get("session_attributed_count"),
            "otel_tool_workflow_privacy_scan": as_dict(otel_tool_workflow.get("privacy_scan")).get("status"),
            "otel_learning_loop_status": otel_learning_loop.get("status"),
            "otel_learning_loop_validation": as_dict(otel_learning_loop.get("validation")).get("status"),
            "otel_learning_loop_privacy_scan": as_dict(otel_learning_loop.get("privacy_scan")).get("status"),
            "otel_learning_loop_recommendation_count": len([row for row in (otel_learning_loop.get("recommendations") or []) if isinstance(row, dict)]),
            "otel_learning_loop_token_coverage_ratio": as_dict(otel_learning_summary.get("token_cost")).get("token_coverage_ratio"),
            "otel_learning_loop_cost_coverage_ratio": as_dict(otel_learning_summary.get("token_cost")).get("cost_coverage_ratio"),
            "coding_runtime_probe_status": coding_runtime_probe.get("status"),
            "coding_runtime_first_pass_clean": coding_runtime_kpis.get("first_pass_validation_clean"),
            "coding_runtime_rework_required": coding_runtime_kpis.get("rework_required"),
            "coding_runtime_validator_elapsed_seconds": coding_runtime_kpis.get("validator_elapsed_seconds"),
            "coding_runtime_failure_buckets": coding_runtime_kpis.get("failure_bucket_counts"),
            "coding_outcome_ledger_status": coding_outcome.get("status"),
            "coding_outcome_ledger_rows": coding_outcome_summary.get("ledger_row_count"),
            "coding_outcome_session_attributed_count": coding_outcome_summary.get("session_attributed_count"),
            "coding_outcome_model_attributed_count": coding_outcome_summary.get("model_attributed_count"),
            "coding_outcome_validator_proxy_passed_count": coding_outcome_summary.get("validator_proxy_passed_count"),
            "coding_outcome_total_retry_count": coding_outcome_summary.get("total_retry_count"),
            "coding_outcome_reviewable_code_row_count": coding_outcome_summary.get("reviewable_code_row_count"),
            "coding_outcome_ex_post_graded_count": coding_outcome_summary.get("ex_post_graded_count"),
            "coding_outcome_later_review_pending_count": coding_outcome_summary.get("later_review_pending_count"),
            "coding_outcome_rework_required_count": coding_outcome_summary.get("rework_required_count"),
            "coding_outcome_regression_observed_count": coding_outcome_summary.get("regression_observed_count"),
            "coding_outcome_first_pass_clean_count": coding_outcome_summary.get("first_pass_clean_count"),
            "coding_outcome_first_pass_clean_rate": coding_outcome_summary.get("first_pass_clean_rate"),
            "planning_quality_signal_status": planning_signal.get("status"),
            "planning_quality_tracked_lane_count": planning_signal.get("tracked_lane_count"),
            "planning_quality_contract_present_count": planning_signal.get("plan_contract_present_count"),
            "planning_quality_followthrough_clean_count": planning_signal.get("plan_followthrough_clean_count"),
            "planning_quality_followthrough_gap_count": planning_signal.get("plan_followthrough_gap_count"),
            "planning_quality_followthrough_clean_rate": planning_signal.get("plan_followthrough_clean_rate"),
            "planning_quality_actionable_gap_count": planning_projection["planning_quality_actionable_gap_count"],
            "planning_quality_gap_count_selected": planning_projection["planning_quality_gap_count_selected"],
            "planning_quality_gap_source": planning_projection["planning_quality_gap_source"],
            "planning_quality_actionable_status": planning_projection["planning_quality_actionable_status"],
            "planning_quality_terminal_unavailable_count": planning_projection["planning_quality_terminal_unavailable_count"],
            "planning_quality_repaired_accepted_count": planning_projection["planning_quality_repaired_accepted_count"],
            "improvement_opportunity_queue_status": opportunity_queue.get("status"),
            "improvement_opportunity_count": opportunity_summary.get("opportunity_count"),
            "improvement_high_priority_count": opportunity_summary.get("high_priority_count"),
            "improvement_top_opportunity_title": opportunity_summary.get("top_opportunity_title"),
            "improvement_ledger_status": improvement_ledger.get("status"),
            "improvement_ledger_validation": as_dict(improvement_ledger.get("validation")).get("status"),
            "improvement_ledger_rows": improvement_ledger_summary.get("ledger_row_count"),
            "improvement_ledger_appended_event_count": improvement_ledger_summary.get("appended_event_count"),
            "improvement_ledger_latest_open_count": improvement_ledger_summary.get("latest_open_count"),
            "improvement_ledger_latest_closed_count": improvement_ledger_summary.get("latest_closed_count"),
            "improvement_ledger_recurring_open_count": improvement_ledger_summary.get("recurring_open_count"),
            "improvement_ledger_closure_rate": improvement_kpis.get("closure_rate"),
            "improvement_ledger_applied_fix_closed_count": improvement_kpis.get("applied_fix_closed_count"),
            "improvement_ledger_signal_absence_closed_count": improvement_kpis.get("signal_absence_closed_count"),
            "improvement_ledger_other_closed_count": improvement_kpis.get("other_closed_count"),
            "improvement_ledger_applied_fix_closure_rate": improvement_kpis.get("applied_fix_closure_rate"),
            "improvement_ledger_signal_absence_closure_rate": improvement_kpis.get("signal_absence_closure_rate"),
            "improvement_ledger_anti_theater_status": improvement_kpis.get("anti_theater_status"),
            "improvement_ledger_high_priority_open_count": improvement_ledger_summary.get("high_priority_open_count"),
            "improvement_ledger_overdue_open_count": improvement_ledger_summary.get("overdue_open_count"),
            "improvement_ledger_due_soon_open_count": improvement_ledger_summary.get("due_soon_open_count"),
            "improvement_ledger_high_priority_overdue_open_count": improvement_ledger_summary.get("high_priority_overdue_open_count"),
            "improvement_ledger_escalation_level": improvement_ledger_summary.get("escalation_level"),
            "improvement_ledger_top_improvement_title": improvement_ledger_summary.get("top_improvement_title"),
            "improvement_ledger_top_improvement_age_hours": improvement_ledger_summary.get("top_improvement_age_hours"),
            "improvement_ledger_top_improvement_sla_status": improvement_ledger_summary.get("top_improvement_sla_status"),
            "reflection_proposal_autopilot_status": proposal_autopilot.get("status"),
            "reflection_proposal_count": proposal_summary.get("proposal_count"),
            "reflection_owner_decision_required_count": proposal_summary.get("owner_decision_required_count"),
            "reflection_auto_apply_count": proposal_summary.get("auto_apply_count"),
            "auto_patch_proposer_status": auto_patch_proposer.get("status"),
            "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
            "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count"),
            "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
            "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
            "auto_patch_auto_apply_candidate_count": auto_patch_summary.get("auto_apply_candidate_count"),
            "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
            "prompt_variant_ledger_status": prompt_variant_ledger.get("status"),
            "prompt_variant_ledger_validation": as_dict(prompt_variant_ledger.get("validation")).get("status"),
            "prompt_variant_ledger_existing_event_count": prompt_variant_summary.get("existing_event_count"),
            "prompt_variant_ledger_appended_event_count": prompt_variant_summary.get("appended_event_count"),
            "prompt_variant_ledger_current_prompt_id": prompt_variant_summary.get("current_prompt_id"),
            "prompt_variant_ledger_current_variant_id": prompt_variant_summary.get("current_variant_id"),
            "prompt_variant_ledger_eval_failed_count": prompt_variant_summary.get("eval_failed_count"),
            "prompt_variant_ledger_auto_apply_count": prompt_variant_summary.get("auto_apply_count"),
            "outcome_feedback_ingest_status": outcome_feedback.get("status"),
            "outcome_feedback_ingest_validation": as_dict(outcome_feedback.get("validation")).get("status"),
            "outcome_feedback_candidate_case_count": outcome_feedback_summary.get("candidate_case_count"),
            "outcome_feedback_append_case_count": outcome_feedback_summary.get("append_case_count"),
            "outcome_feedback_merged_case_count": outcome_feedback_summary.get("merged_case_count"),
            "workflow_advancement_scorecard_status": workflow_scorecard.get("status"),
            "workflow_advancement_scorecard_validation": as_dict(workflow_scorecard.get("validation")).get("status"),
            "workflow_advancement_advanced_count": workflow_scorecard_summary.get("advanced_count"),
            "workflow_advancement_blocked_count": workflow_scorecard_summary.get("blocked_count"),
            "workflow_advancement_owner_needed_count": workflow_scorecard_summary.get("owner_needed_count"),
            "workflow_advancement_cron_update_recommended": workflow_scorecard_summary.get("cron_update_recommended"),
            "workflow_blocker_followups_status": workflow_followups.get("status"),
            "workflow_blocker_followups_validation": as_dict(workflow_followups.get("validation")).get("status"),
            "workflow_blocker_followup_count": workflow_followup_summary.get("followup_count"),
            "otel_recommendation_closeout_status": otel_recommendation_closeout.get("status"),
            "otel_recommendation_closeout_validation": as_dict(otel_recommendation_closeout.get("validation")).get("status"),
            "otel_recommendation_closeout_closed_count": closeout_summary.get("closed_count"),
            "otel_recommendation_closeout_open_count": closeout_summary.get("open_count"),
            "wf74_autonomy_router_status": autonomy_router.get("status"),
            "wf74_autonomy_router_validation": as_dict(autonomy_router.get("validation")).get("status"),
            "wf74_autonomy_router_pm_job_candidate_count": autonomy_router_summary.get("pm_job_candidate_count"),
            "wf74_autonomy_router_workflow_followup_count": autonomy_router_summary.get("workflow_followup_count"),
            "wf74_recommendation_to_route_conversion_rate": autonomy_router_kpis.get("recommendation_to_route_conversion_rate"),
            "wf74_route_to_pm_job_conversion_rate": autonomy_router_kpis.get("route_to_pm_job_conversion_rate"),
            "wf74_high_priority_overdue_count": autonomy_router_kpis.get("high_priority_overdue_count"),
            "wf74_average_age_of_top_open_improvement_hours": autonomy_router_kpis.get("average_age_of_top_open_improvement_hours"),
            "pm_implementation_job_queue_status": pm_job_queue.get("status"),
            "pm_implementation_job_queue_validation": as_dict(pm_job_queue.get("validation")).get("status"),
            "pm_implementation_job_count": pm_job_queue_summary.get("job_count"),
            "pm_implementation_wf74_router_job_count": pm_job_queue_summary.get("wf74_router_job_count"),
            "pm_implementation_auto_main_executable_job_count": pm_job_queue_summary.get("auto_main_executable_job_count"),
            "pm_implementation_auto_cron_executable_job_count": pm_job_queue_summary.get("auto_cron_executable_job_count"),
            "pm_control_packet_status": pm_control.get("status"),
            "pm_control_packet_readiness_band": as_dict(pm_control_summary.get("pm_readiness")).get("readiness_band"),
            "owner_gated_review_status": owner_gated_queue.get("status"),
            "owner_gated_review_validation": as_dict(owner_gated_queue.get("validation")).get("status"),
            "owner_gated_item_count": owner_gated_summary.get("item_count"),
            "owner_gated_decision_required_count": owner_gated_summary.get("owner_decision_required_count"),
            "owner_gated_top_gate": owner_gated_summary.get("top_gate"),
            "owner_gated_top_title": owner_gated_summary.get("top_title"),
            "wf74_decision_docket_status": decision_docket.get("status"),
            "wf74_decision_docket_validation": as_dict(decision_docket.get("validation")).get("status"),
            "wf74_decision_docket_row_count": decision_docket_summary.get("row_count"),
            "wf74_decision_docket_fix_now_count": decision_docket_summary.get("fix_now_count"),
            "wf74_decision_docket_hard_stop_count": decision_docket_summary.get("hard_stop_count"),
            "wf74_proposal_dispatcher_status": proposal_dispatcher.get("status"),
            "wf74_proposal_dispatcher_validation": as_dict(proposal_dispatcher.get("validation")).get("status"),
            "wf74_dispatch_row_count": proposal_dispatcher_summary.get("dispatch_row_count"),
            "wf74_dispatch_pm_job_count": proposal_dispatcher_summary.get("pm_job_dispatch_count"),
            "wf74_dispatch_skill_workshop_proposal_count": proposal_dispatcher_summary.get("skill_workshop_proposal_count"),
            "wf74_dispatch_owner_gated_packet_count": proposal_dispatcher_summary.get("owner_gated_packet_count"),
            "wf74_dispatch_validator_ticket_count": proposal_dispatcher_summary.get("validator_ticket_count"),
            "wf74_dispatch_monitor_only_count": proposal_dispatcher_summary.get("monitor_only_count"),
            "wf74_dispatch_blocked_no_dispatch_count": proposal_dispatcher_summary.get("blocked_no_dispatch_count"),
            "wf74_dispatch_pm_ledger_suppression_ticket_count": proposal_dispatcher_summary.get("pm_ledger_suppression_ticket_count"),
            "wf74_dispatch_auto_apply_count": proposal_dispatcher_summary.get("auto_apply_count"),
            "otel_window_count": len(otel_windows),
            "otel_window_ids": [row.get("window_id") for row in otel_windows],
            "wf74_duplicate_cron_collectors": duplication_summary.get("recurring_component_collectors_outside_owner_count"),
            "wf74_one_shot_component_reminders": duplication_summary.get("one_shot_component_collectors_outside_owner_count"),
            "learning_environment_status": learning_environment_status,
        },
        "steps": steps,
        "artifacts": artifacts,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "rsi_observation": {
            "schema": "wf74.rsi_observation.v1",
            "source": "wf74_model_quality_collection_cron_runner",
            "lesson_type": "automation_candidate",
            "owner_surface": "WF74 / cron-automation-manager / future session packet",
            "what_changed": "WF74 scheduled collection refreshed model/run, alerts-OS evidence, scorecard, artifact-index, harness, cron, and duplication-audit proof.",
            "warnings_or_blockers": [
                *(
                    ["cron control packet reports scheduler attention"]
                    if any(step.get("name") == "cron_control_packet" for step in attention)
                    else []
                ),
                *(["decision quality is waiting for review-only recommendation outcomes"] if learning_environment_status["decision_quality_status"] == "blocked" else []),
                *(
                    ["semantic decision-outcome claims remain evidence-gated"]
                    if learning_environment_status["semantic_outcome_claim_status"] == "maturity_gated"
                    else []
                ),
                *(["high-priority improvement backlog is overdue"] if learning_environment_status["high_priority_overdue_open_count"] else []),
                *([] if model_summary.get("session_attribution_coverage") else ["session attribution coverage missing"]),
                *([] if model_summary.get("cost_rows") else ["cost fields unavailable"]),
                *([] if duplication_summary.get("expected_owner_ok") is not False else ["WF74 cron owner duplication risk"]),
                *([] if not duplication_summary.get("one_shot_component_collectors_outside_owner_count") else ["one-shot WF74 component reminder exists outside owner job"]),
            ],
            "future_session_lesson": "Use this runner as the single scheduled WF74 collection owner; do not schedule component ledgers separately.",
            "recommended_destination": "memory/2026-06-08.md if new residue appears; Skill Workshop only for repeated procedure drift.",
            "actionability": "monitor",
        },
        "next_safe_action": (
            "Use the WF74 router recommendation/action ledger to route domain quality residue into PM jobs; "
            "keep cron technical health separate from alert evidence readiness and do not mutate schedules."
        ),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    if as_dict(payload.get("summary")).get("steps_blocked", 0):
        findings.append({"severity": "critical", "detail": "one or more collection steps blocked"})
    if as_dict(payload.get("summary")).get("steps_attention", 0):
        findings.append({"severity": "warning", "detail": "one or more non-blocking diagnostic steps need attention"})
    summary = as_dict(payload.get("summary"))
    if summary.get("recommendation_performance_status") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "recommendation outcome performance digest is not ok"})
    for field in ("guarded_sql_validation_status", "alert_controller_validation", "recommendation_digest_validation", "alerts_os_pivot_validation"):
        if summary.get(field) != "ok":
            findings.append({"severity": "critical", "detail": f"active alerts OS proof is not green: {field}"})
    if summary.get("quote_snapshot_status") != "ok":
        findings.append({"severity": "critical", "detail": "active alerts OS quote snapshot is not green"})
    if as_dict(payload.get("summary")).get("token_usage_validation") == "critical":
        findings.append({"severity": "critical", "detail": "token usage ledger validation is critical"})
    if int(as_dict(payload.get("summary")).get("token_usage_event_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "token usage ledger has no token-bearing rows"})
    for artifact in payload.get("artifacts", []):
        if not artifact.get("exists"):
            findings.append({"severity": "critical", "detail": f"missing artifact: {artifact.get('path')}"})
    if as_dict(payload.get("summary")).get("otel_window_count") != 5:
        findings.append({"severity": "critical", "detail": "OTEL multi-window summary must expose five windows"})
    if as_dict(payload.get("summary")).get("otel_field_depth_packet_status") not in {"owner_decision_required", "approved_enabled"}:
        findings.append({"severity": "critical", "detail": "OTEL field-depth packet status must be owner-gated or approved-enabled"})
    if int(as_dict(payload.get("summary")).get("coding_outcome_ledger_rows") or 0) <= 0:
        findings.append({"severity": "critical", "detail": "coding outcome ledger must provide per-lane rows"})
    if as_dict(payload.get("summary")).get("planning_quality_signal_status") in {None, "missing"}:
        findings.append({"severity": "warning", "detail": "planning quality signal is missing"})
    if as_dict(payload.get("summary")).get("improvement_opportunity_queue_status") not in {None, "ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 improvement opportunity queue is not ok"})
    if as_dict(payload.get("summary")).get("improvement_ledger_validation") != "ok":
        findings.append({"severity": "warning", "detail": "improvement ledger validation is not ok"})
    if int(as_dict(payload.get("summary")).get("improvement_ledger_latest_open_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "improvement ledger has no open carry-forward rows"})
    if int(as_dict(payload.get("summary")).get("improvement_ledger_high_priority_overdue_open_count") or 0):
        findings.append({"severity": "warning", "detail": "improvement ledger has overdue high-priority carry-forward rows"})
    learning_environment = as_dict(as_dict(payload.get("summary")).get("learning_environment_status"))
    if not learning_environment:
        findings.append({"severity": "critical", "detail": "learning environment status split is missing"})
    if learning_environment.get("runner_status") == "blocked":
        findings.append({"severity": "critical", "detail": "learning environment runner status is blocked"})
    if learning_environment.get("quality_gate_status") == "blocked":
        findings.append({"severity": "warning", "detail": "learning environment has blocked quality gates"})
    if learning_environment.get("anti_theater_status") == "proposal_loop_active_no_closure_proof":
        findings.append({"severity": "warning", "detail": "learning loop has no closure proof"})
    if int(as_dict(payload.get("summary")).get("reflection_proposal_count") or 0) <= 0:
        findings.append({"severity": "critical", "detail": "WF74 proposal autopilot produced no proposals"})
    if int(as_dict(payload.get("summary")).get("reflection_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 proposal autopilot must not auto-apply"})
    if as_dict(payload.get("summary")).get("auto_patch_proposer_status") not in {None, "ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 auto-patch proposer is not ok"})
    if int(as_dict(payload.get("summary")).get("auto_patch_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 auto-patch proposer must not auto-apply"})
    if as_dict(payload.get("summary")).get("prompt_variant_ledger_validation") not in {None, "ok"}:
        findings.append({"severity": "warning", "detail": "WF74 prompt variant ledger validation is not ok"})
    if int(as_dict(payload.get("summary")).get("prompt_variant_ledger_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 prompt variant ledger observed auto-apply activity"})
    if as_dict(payload.get("summary")).get("outcome_feedback_ingest_validation") not in {None, "ok", "warning"}:
        findings.append({"severity": "warning", "detail": "WF74 outcome feedback ingest validation is not ok or warning"})
    if as_dict(payload.get("summary")).get("workflow_advancement_scorecard_validation") not in {"ok", "warning"}:
        findings.append({"severity": "critical", "detail": "workflow advancement scorecard validation is not ok or warning"})
    elif as_dict(payload.get("summary")).get("workflow_advancement_scorecard_validation") == "warning":
        findings.append({"severity": "warning", "detail": "workflow advancement scorecard has warning-level source residue"})
    if as_dict(payload.get("summary")).get("workflow_blocker_followups_validation") != "ok":
        findings.append({"severity": "critical", "detail": "workflow blocker followup validation is not ok"})
    if as_dict(payload.get("summary")).get("otel_recommendation_closeout_validation") not in {"ok", "warning"}:
        findings.append({"severity": "critical", "detail": "OTEL recommendation closeout validation is not ok or warning"})
    elif as_dict(payload.get("summary")).get("otel_recommendation_closeout_validation") == "warning":
        findings.append({"severity": "warning", "detail": "OTEL recommendation closeout has owner-gated or hygiene residue"})
    router_validation = as_dict(payload.get("summary")).get("wf74_autonomy_router_validation")
    router_candidates = int(as_dict(payload.get("summary")).get("wf74_autonomy_router_pm_job_candidate_count") or 0)
    router_route_rate = as_dict(payload.get("summary")).get("wf74_recommendation_to_route_conversion_rate")
    if router_validation not in {"ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 autonomy work router validation is not ok or warning"})
    elif router_validation == "warning":
        if router_candidates > 0 and router_route_rate in {1.0, None}:
            findings.append({"severity": "warning", "detail": "WF74 autonomy router has warning-level routed source residue"})
        else:
            findings.append({"severity": "critical", "detail": "WF74 autonomy work router warning lacks routed PM proof"})
    if int(as_dict(payload.get("summary")).get("wf74_autonomy_router_pm_job_candidate_count") or 0) <= 0:
        findings.append({"severity": "critical", "detail": "WF74 autonomy work router produced no PM job candidates"})
    if as_dict(payload.get("summary")).get("wf74_recommendation_to_route_conversion_rate") not in {1.0, None}:
        findings.append({"severity": "critical", "detail": "WF74 routable recommendations were not fully routed"})
    if as_dict(payload.get("summary")).get("pm_implementation_job_queue_validation") != "ok":
        findings.append({"severity": "critical", "detail": "PM implementation job queue validation is not ok"})
    if int(as_dict(payload.get("summary")).get("pm_implementation_wf74_router_job_count") or 0) <= 0:
        findings.append({"severity": "critical", "detail": "PM implementation queue did not ingest WF74 router jobs"})
    if int(as_dict(payload.get("summary")).get("pm_implementation_auto_main_executable_job_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "PM implementation queue has no auto-main executable jobs"})
    if int(as_dict(payload.get("summary")).get("pm_implementation_auto_cron_executable_job_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "PM implementation queue has no auto-cron executable jobs"})
    if as_dict(payload.get("summary")).get("owner_gated_review_validation") != "ok":
        findings.append({"severity": "critical", "detail": "owner-gated action review queue validation is not ok"})
    if int(as_dict(payload.get("summary")).get("owner_gated_decision_required_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "owner-gated action review queue has no decision items"})
    if as_dict(payload.get("summary")).get("wf74_decision_docket_validation") not in {"ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 decision docket validation is not ok or warning"})
    if int(as_dict(payload.get("summary")).get("wf74_decision_docket_row_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "WF74 decision docket produced no rows"})
    if int(as_dict(payload.get("summary")).get("wf74_decision_docket_hard_stop_count") or 0):
        findings.append({"severity": "warning", "detail": "WF74 decision docket has hard-stop rows"})
    dispatcher_validation = as_dict(payload.get("summary")).get("wf74_proposal_dispatcher_validation")
    if dispatcher_validation not in {"ok", "warning"}:
        findings.append({"severity": "critical", "detail": "WF74 proposal dispatcher validation is not ok or warning"})
    if int(as_dict(payload.get("summary")).get("wf74_dispatch_row_count") or 0) <= 0:
        findings.append({"severity": "warning", "detail": "WF74 proposal dispatcher produced no rows"})
    if int(as_dict(payload.get("summary")).get("wf74_dispatch_auto_apply_count") or 0):
        findings.append({"severity": "critical", "detail": "WF74 proposal dispatcher observed auto-apply activity"})
    if int(as_dict(payload.get("summary")).get("wf74_dispatch_blocked_no_dispatch_count") or 0):
        findings.append({"severity": "warning", "detail": "WF74 proposal dispatcher has blocked/no-dispatch rows"})
    if int(as_dict(payload.get("summary")).get("wf74_dispatch_pm_ledger_suppression_ticket_count") or 0):
        findings.append({"severity": "warning", "detail": "WF74 proposal dispatcher surfaced PM completion-ledger suppression tickets"})
    if as_dict(payload.get("summary")).get("wf74_duplicate_cron_collectors") not in {0, None}:
        findings.append({"severity": "critical", "detail": "duplicate WF74 cron component collectors detected"})
    if as_dict(payload.get("summary")).get("wf74_one_shot_component_reminders") not in {0, None}:
        findings.append({"severity": "warning", "detail": "one-shot WF74 component reminder exists outside owner job"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Model Quality Collection Cron Runner",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Steps ok/blocked/attention: {summary.get('steps_ok')} / {summary.get('steps_blocked')} / {summary.get('steps_attention')}",
        f"- Step retries: {summary.get('steps_retried')} / recovered {summary.get('steps_recovered_after_retry')}",
        f"- Model attribution coverage: {summary.get('model_attribution_coverage')}",
        f"- Session attribution coverage: {summary.get('session_attribution_coverage')}",
        f"- Token usage: {summary.get('token_usage_total_tokens')} tokens / events {summary.get('token_usage_event_count')} / pricing {summary.get('token_usage_pricing_status')}",
        f"- Recommendation outcomes: {summary.get('recommendation_tracking_rows')} rows / {summary.get('recommendation_graded_rows')} graded",
        f"- Alerts OS: controller {summary.get('alert_controller_validation')} / digest {summary.get('recommendation_digest_validation')} / pivot {summary.get('alerts_os_pivot_validation')}",
        f"- OTEL learning loop: {summary.get('otel_learning_loop_status')} / privacy {summary.get('otel_learning_loop_privacy_scan')} / recs {summary.get('otel_learning_loop_recommendation_count')}",
        f"- Coding ex-post: graded {summary.get('coding_outcome_ex_post_graded_count')} / pending {summary.get('coding_outcome_later_review_pending_count')} / first-pass-clean {summary.get('coding_outcome_first_pass_clean_rate')}",
        f"- Planning quality: {summary.get('planning_quality_signal_status')} / clean-rate {summary.get('planning_quality_followthrough_clean_rate')} / gaps {summary.get('planning_quality_followthrough_gap_count')}",
        f"- Improvement ledger: {summary.get('improvement_ledger_status')} / rows {summary.get('improvement_ledger_rows')} / open {summary.get('improvement_ledger_latest_open_count')}",
        f"- Closure split: applied-fix {summary.get('improvement_ledger_applied_fix_closed_count')} / signal-absence {summary.get('improvement_ledger_signal_absence_closed_count')} / other {summary.get('improvement_ledger_other_closed_count')}",
        f"- Autonomy router: {summary.get('wf74_autonomy_router_status')} / PM candidates {summary.get('wf74_autonomy_router_pm_job_candidate_count')} / route-rate {summary.get('wf74_recommendation_to_route_conversion_rate')}",
        f"- PM bridge: jobs {summary.get('pm_implementation_job_count')} / WF74 jobs {summary.get('pm_implementation_wf74_router_job_count')} / auto-main {summary.get('pm_implementation_auto_main_executable_job_count')} / auto-cron {summary.get('pm_implementation_auto_cron_executable_job_count')}",
        f"- Learning environment: {as_dict(summary.get('learning_environment_status')).get('runner_status')} / quality {as_dict(summary.get('learning_environment_status')).get('quality_gate_status')} / anti-theater {as_dict(summary.get('learning_environment_status')).get('anti_theater_status')}",
        f"- Improvement SLA: overdue {summary.get('improvement_ledger_overdue_open_count')} / due soon {summary.get('improvement_ledger_due_soon_open_count')} / escalation {summary.get('improvement_ledger_escalation_level')}",
        f"- Owner-gated decisions: {summary.get('owner_gated_decision_required_count')} / top {summary.get('owner_gated_top_gate')}: {summary.get('owner_gated_top_title')}",
        f"- WF74 dispatcher: rows {summary.get('wf74_dispatch_row_count')} / PM {summary.get('wf74_dispatch_pm_job_count')} / validators {summary.get('wf74_dispatch_validator_ticket_count')} / owner {summary.get('wf74_dispatch_owner_gated_packet_count')} / monitor {summary.get('wf74_dispatch_monitor_only_count')} / blocked {summary.get('wf74_dispatch_blocked_no_dispatch_count')} / auto-apply {summary.get('wf74_dispatch_auto_apply_count')}",
        f"- WF74 active tracks: {', '.join(summary.get('wf74_active_tracks') or [])}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run WF74 model-quality collection cron digest")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--include-harness", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--cron-nonblocking-domain-exit",
        action="store_true",
        help=(
            "When --validate is set, return exit 0 for fully classified domain blockers "
            "while preserving the blocked artifact. Technical or unclassified criticals still fail."
        ),
    )
    args = parser.parse_args(argv)

    steps = execute_plan(args.include_harness)

    payload = build_payload(steps)
    validation = validate(payload)
    payload["validation"] = validation
    domain_reason = classified_domain_blocker_reason(payload)
    scheduler_exit = scheduler_exit_decision(
        payload,
        validation,
        allow_domain_blocked_exit_zero=bool(
            args.validate
            and (
                args.cron_nonblocking_domain_exit
            )
        ),
    )
    payload["scheduler_exit"] = scheduler_exit
    payload["summary"]["scheduler_exit_status"] = scheduler_exit["status"]
    payload["summary"]["scheduler_exit_reason"] = scheduler_exit["reason"]
    payload["summary"]["scheduler_exit_domain_blocked_nonfatal"] = scheduler_exit["domain_blocked_nonfatal"]
    if scheduler_exit["status"] == "domain_blocked_nonfatal":
        payload["status"] = "domain_attention"
        payload["summary"]["domain_attention_status"] = "nonfatal"
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))

    if not args.quiet:
        summary = as_dict(payload.get("summary"))
        print(
            f"status={payload['status']} validation={validation['status']} "
            f"steps_ok={summary.get('steps_ok')} steps_blocked={summary.get('steps_blocked')} "
            f"model_attr={summary.get('model_attribution_coverage')} recommendation_rows={summary.get('recommendation_tracking_rows')} "
            f"scheduler_exit={scheduler_exit['status']}"
        )
        for finding in validation["findings"]:
            print(f"  [{finding['severity']}] {finding['detail']}")

    if args.validate:
        return int(scheduler_exit["returncode"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
