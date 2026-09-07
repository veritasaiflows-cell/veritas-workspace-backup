#!/usr/bin/env python3
"""Review-only model-quality scorecard scaffold (WF74).

Joins existing proof surfaces into one normalized scorecard that measures
model output quality across three tracks:

  1. implementation_quality - live now. Built from behavior-eval discipline,
     validator pass rate, and surface-readiness pass rate.
  2. performance            - runtime latency live now; OTEL operational
     dimensions (cost, tokens, failover/errors, blocked tools, session
     friction) pending the OTEL backend, which is disabled in this lane.
  3. decision_quality       - active measurement-only. Append-only
     recommendation outcomes and the current alerts-OS evidence chain activate
     the scorecard; predictive/model-ranking claims remain blocked.

This is a scaffold, not a deployed model ranker. It can measure process quality
now, but it cannot claim "model A is better than model B" until per-model/session
attribution and mature semantic outcome history exist. It is review-only: no
canon/portfolio mutation, no owner approval, no OTEL backend enablement, no
base-model self-modification, and no investment-correctness claim from runtime
metrics alone.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import strategic_answer_route_context
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
HISTORY = ROOT / "data" / "state-history" / "model-quality-scorecard.jsonl"
DEFAULT_JSON = TMP / "model-quality-scorecard.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SQL_CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
SCHEMA = "wf74.model_quality_scorecard.v1"

HARNESS = TMP / "veritas-harness-scorecard.json"
OUTCOME_EVAL = TMP / "wf74-outcome-eval-suite-v2.json"
RUNTIME_PERF = TMP / "runtime-performance-scorecard.json"
OTEL_OPS = TMP / "otel-ops-control.json"
OTEL_WINDOW_SUMMARY = TMP / "otel-ops-window-summary.json"
OTEL_RUNTIME_PROBE = TMP / "otel-runtime-metadata-probe.json"
RECO_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
RECOMMENDATION_PERFORMANCE = TMP / "finance-decision-performance-digest.json"
FINANCE_SQL_VALIDATION = TMP / "finance-sql-canon-access-validation.json"
QUOTE_SNAPSHOT = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
ALERT_CONTROLLER = TMP / "alert-level-freshness-controller.json"
ALERT_DIGEST = TMP / "finance-alert-os-digest.json"
ALERTS_OS_PIVOT = TMP / "alerts-os-pivot-validator.json"
CRON_SPARK_CANARY = TMP / "cron-spark-canary-monitor.json"
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
TOKEN_USAGE_LEDGER = TMP / "token-usage-ledger-current.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
CODING_RUNTIME_PROBE = TMP / "coding-runtime-kpi-probe.json"
PM_CONTROL = TMP / "pm-control-packet.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
ROUTE_EFFICIENCY = TMP / "route-efficiency-scorecard.json"
WF73_AUDIT = TMP / "wf73-control-plane-audit.json"
CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"

# OTEL operational dimensions named in WF74 continuity (2026-06-06 handoff).
OTEL_DIMENSIONS = [
    "cost",
    "token_use",
    "latency",
    "failover_errors",
    "blocked_tools",
    "harness_failures",
    "session_friction",
]

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def load_inputs() -> dict[str, Any]:
    return {
        "harness": as_dict(load_json_artifact(HARNESS)),
        "outcome_eval": as_dict(load_json_artifact(OUTCOME_EVAL)),
        "runtime_perf": as_dict(load_json_artifact(RUNTIME_PERF)),
        "otel_ops": as_dict(load_json_artifact(OTEL_OPS)),
        "otel_window_summary": as_dict(load_json_artifact(OTEL_WINDOW_SUMMARY)),
        "otel_runtime_probe": as_dict(load_json_artifact(OTEL_RUNTIME_PROBE)),
        "reco_ledger": as_dict(load_json_artifact(RECO_LEDGER)),
        "recommendation_performance": as_dict(load_json_artifact(RECOMMENDATION_PERFORMANCE)),
        "finance_sql_validation": as_dict(load_json_artifact(FINANCE_SQL_VALIDATION)),
        "quote_snapshot": as_dict(load_json_artifact(QUOTE_SNAPSHOT)),
        "alert_controller": as_dict(load_json_artifact(ALERT_CONTROLLER)),
        "alert_digest": as_dict(load_json_artifact(ALERT_DIGEST)),
        "alerts_os_pivot": as_dict(load_json_artifact(ALERTS_OS_PIVOT)),
        "cron_spark_canary": as_dict(load_json_artifact(CRON_SPARK_CANARY)),
        "model_run_ledger": as_dict(load_json_artifact(MODEL_RUN_LEDGER)),
        "token_usage_ledger": as_dict(load_json_artifact(TOKEN_USAGE_LEDGER)),
        "model_learning_ledger": as_dict(load_json_artifact(MODEL_LEARNING_LEDGER)),
        "improvement_ledger": as_dict(load_json_artifact(IMPROVEMENT_LEDGER)),
        "coding_runtime_probe": as_dict(load_json_artifact(CODING_RUNTIME_PROBE)),
        "pm_control": as_dict(load_json_artifact(PM_CONTROL)),
        "cron_control": as_dict(load_json_artifact(CRON_CONTROL)),
        "route_efficiency": as_dict(load_json_artifact(ROUTE_EFFICIENCY)),
        "wf73_audit": as_dict(load_json_artifact(WF73_AUDIT)),
        "changed_file_router": as_dict(load_json_artifact(CHANGED_FILE_ROUTER)),
        "finance_sql_canon": finance_sql_canon_context(),
    }


def finance_sql_canon_context() -> dict[str, Any]:
    raw = strategic_answer_route_context(consumer="model_quality_scorecard", db_path=SQL_CANON_DB)
    return {
        "schema": "wf74.model_quality_scorecard.finance_sql_canon_context.v3",
        "status": raw.get("status"),
        "sql_canon_db": rel(SQL_CANON_DB),
        "typed_access_layer": raw.get("typed_access_layer"),
        "access_validation_status": raw.get("access_validation_status"),
        "production_answer_count": raw.get("production_answer_count"),
        "production_answer_tickers": raw.get("production_answer_tickers"),
        "answer_route_policy": as_dict(raw.get("answer_route_policy")),
        "validation": as_dict(raw.get("validation")),
    }


def implementation_quality_track(inputs: dict[str, Any]) -> dict[str, Any]:
    eval_summary = as_dict(inputs["outcome_eval"].get("summary"))
    perf_summary = as_dict(inputs["runtime_perf"].get("summary"))
    harness_summary = as_dict(inputs["harness"].get("summary"))

    categories = as_num(eval_summary.get("categories"))
    fixtures = as_num(eval_summary.get("fixtures"))
    classified = as_num(eval_summary.get("classified_correctly"))
    failed_classifications = as_num(eval_summary.get("failed_classifications"))

    perf_checks = as_num(perf_summary.get("checks_total"))
    perf_ok = as_num(perf_summary.get("ok_count"))

    harness_checks = as_num(harness_summary.get("checks_total"))
    harness_pass = as_num(harness_summary.get("pass_count"))
    harness_fail = as_num(harness_summary.get("failure_count"))

    metrics = {
        "behavior_eval_categories": int(categories),
        "behavior_eval_fixtures": int(fixtures),
        "behavior_eval_classified_correctly": int(classified),
        "behavior_eval_failed_classifications": int(failed_classifications),
        "behavior_eval_pass_rate": ratio(classified, fixtures),
        "validator_pass_rate": ratio(perf_ok, perf_checks),
        "validator_checks_total": int(perf_checks),
        "validator_blocked": int(perf_checks - perf_ok),
        "surface_readiness_pass_rate": ratio(harness_pass, harness_checks),
        "surface_readiness_failures": int(harness_fail),
    }
    inputs_present = bool(eval_summary) and bool(perf_summary) and bool(harness_summary)
    return {
        "readiness": "active" if inputs_present else "inputs_missing",
        "summary": (
            "Implementation-quality signals are observable now from behavior-eval "
            "discipline, validator pass rate, and surface-readiness checks. Not yet "
            "split by model/session until attribution lands."
        ),
        "metrics": metrics,
        "sources": [rel(OUTCOME_EVAL), rel(RUNTIME_PERF), rel(HARNESS)],
    }


def performance_track(inputs: dict[str, Any]) -> dict[str, Any]:
    perf_summary = as_dict(inputs["runtime_perf"].get("summary"))
    otel_ops = as_dict(inputs.get("otel_ops"))
    otel_summary = as_dict(otel_ops.get("summary"))
    otel_window_summary = as_dict(inputs.get("otel_window_summary"))
    otel_windows = [row for row in otel_window_summary.get("windows", []) if isinstance(row, dict)]
    field_inventory = as_dict(otel_ops.get("field_inventory"))
    otel_runtime_probe = as_dict(inputs.get("otel_runtime_probe"))
    otel_runtime_summary = as_dict(otel_runtime_probe.get("summary"))
    spark_canary = as_dict(inputs.get("cron_spark_canary"))
    spark_summary = as_dict(spark_canary.get("summary"))
    model_run_ledger = as_dict(inputs.get("model_run_ledger"))
    model_run_summary = as_dict(model_run_ledger.get("summary"))
    token_usage_ledger = as_dict(inputs.get("token_usage_ledger"))
    token_usage_summary = as_dict(token_usage_ledger.get("summary"))
    token_cost_coverage_percent = as_num(
        token_usage_summary.get("api_equivalent_cost_event_coverage_percent")
    )
    token_cost_rows = int(as_num(token_usage_summary.get("api_equivalent_cost_rows")))
    token_event_rows = int(as_num(token_usage_summary.get("token_event_count")))
    token_cost_available = bool(token_usage_summary) and token_cost_rows > 0
    spark_jobs = [job for job in spark_canary.get("jobs", []) if isinstance(job, dict)]
    spark_ok_jobs = [
        {
            "name": job.get("name"),
            "model": job.get("model"),
            "thinking": job.get("thinking"),
            "last_status": job.get("last_status"),
            "last_duration_ms": job.get("last_duration_ms"),
            "duration_ratio_vs_baseline": job.get("duration_ratio_vs_baseline"),
        }
        for job in spark_jobs
        if job.get("last_status") == "ok" and not job.get("pending_first_canary_run")
    ]
    runtime_live = {
        "total_duration_ms": as_num(perf_summary.get("total_duration_ms")),
        "max_command_duration_ms": as_num(perf_summary.get("max_command_duration_ms")),
        "blocked_count": int(as_num(perf_summary.get("blocked_count"))),
        "checks_total": int(as_num(perf_summary.get("checks_total"))),
        "source": rel(RUNTIME_PERF),
    }
    available_now = set(field_inventory.get("available_now") or [])
    otel_dimensions = {
        "latency": "partial_collector_batch_timing_available" if otel_summary else "pending_otel_backend",
        "failover_errors": "collector_warning_error_count_available" if otel_summary else "pending_otel_backend",
        "session_friction": "trace_span_count_available" if otel_summary else "pending_otel_backend",
        "cost": (
            "api_equivalent_from_token_usage_ledger_partial_coverage"
            if token_cost_available
            else "not_available_from_basic_debug_log"
        ),
        "token_use": (
            "from_token_usage_ledger" if token_event_rows > 0 else "not_available_from_basic_debug_log"
        ),
        "blocked_tools": "not_available_from_basic_debug_log",
        "harness_failures": "not_available_from_basic_debug_log",
    }
    metrics = {
        "runtime_total_duration_ms": runtime_live["total_duration_ms"],
        "runtime_max_command_duration_ms": runtime_live["max_command_duration_ms"],
        "runtime_blocked_count": runtime_live["blocked_count"],
        "runtime_checks_total": runtime_live["checks_total"],
        "otel_event_count": int(as_num(otel_summary.get("event_count"))),
        "otel_metric_batches": int(as_num(otel_summary.get("metric_batches"))),
        "otel_trace_batches": int(as_num(otel_summary.get("trace_batches"))),
        "otel_reported_data_points": int(as_num(otel_summary.get("reported_data_points"))),
        "otel_reported_spans": int(as_num(otel_summary.get("reported_spans"))),
        "otel_window_count": len(otel_windows),
        "otel_runtime_metadata_observed": bool(otel_runtime_summary.get("runtime_metadata_observed")),
        "otel_runtime_allowed_field_count": int(as_num(otel_runtime_summary.get("allowed_field_count"))),
        "spark_ok_run_count": int(as_num(spark_summary.get("ok_run_count"))),
        "spark_error_count": int(as_num(spark_summary.get("error_count"))),
        "model_run_row_count": int(as_num(model_run_summary.get("row_count"))),
        "model_run_ok_rows": int(as_num(model_run_summary.get("ok_rows"))),
        "model_run_blocked_or_error_rows": int(as_num(model_run_summary.get("blocked_or_error_rows"))),
        "model_attribution_coverage": model_run_summary.get("model_attribution_coverage"),
        "session_attribution_coverage": model_run_summary.get("session_attribution_coverage"),
        "cost_metric_available": token_cost_available,
        "token_metric_available": token_event_rows > 0,
        "cost_coverage_percent": round(token_cost_coverage_percent, 4),
        "cost_priced_rows": token_cost_rows,
        "token_event_rows": token_event_rows,
    }
    return {
        "readiness": "partial" if perf_summary or otel_summary else "inputs_missing",
        "summary": (
            "Runtime/build latency is live from the runtime performance scorecard. "
            "Local OTEL now provides queryable collector metrics/traces, but basic "
            "debug output still does not expose model/provider, tool, or session/"
            "workflow fields. Token/cost economics now read from the authoritative "
            "token_usage_ledger (Gateway usage-cost path) at partial API-equivalent "
            "coverage — non-zero and provenance-backed, but not an invoice and still "
            "too thin to unlock cross-model economic claims. Spark cron canary runs "
            "are tracked as bounded operational evidence only; they do not create a "
            "model-ranking claim."
        ),
        "metrics": metrics,
        "runtime_latency_live": runtime_live,
        "otel_local_ops": {
            "source": rel(OTEL_OPS),
            "window_summary_source": rel(OTEL_WINDOW_SUMMARY),
            "runtime_probe_source": rel(OTEL_RUNTIME_PROBE),
            "status": otel_ops.get("status"),
            "collector_health": as_dict(otel_ops.get("collector_health")).get("status"),
            "event_count": otel_summary.get("event_count"),
            "metric_batches": otel_summary.get("metric_batches"),
            "trace_batches": otel_summary.get("trace_batches"),
            "reported_data_points": otel_summary.get("reported_data_points"),
            "reported_spans": otel_summary.get("reported_spans"),
            "available_field_count": len(available_now),
            "window_summary_status": otel_window_summary.get("status"),
            "window_count": len(otel_windows),
            "window_ids": [row.get("window_id") for row in otel_windows],
            "trend_indicators": as_dict(otel_window_summary.get("trend_indicators")),
            "runtime_probe_status": otel_runtime_probe.get("status"),
            "runtime_metadata_observed": otel_runtime_summary.get("runtime_metadata_observed"),
            "runtime_allowed_field_count": otel_runtime_summary.get("allowed_field_count"),
            "runtime_raw_content_marker_count": otel_runtime_summary.get("raw_content_marker_count"),
            "runtime_secret_or_header_marker_count": otel_runtime_summary.get("secret_or_header_marker_count"),
            "runtime_observed_categories": as_dict(otel_runtime_probe.get("observed_categories")),
        },
        "otel_operational_dimensions": otel_dimensions,
        "spark_cron_canary": {
            "source": rel(CRON_SPARK_CANARY),
            "status": spark_canary.get("status"),
            "model_under_test": spark_canary.get("model_under_test"),
            "required_thinking": spark_canary.get("required_thinking"),
            "configured_count": spark_summary.get("configured_count"),
            "xhigh_thinking_count": spark_summary.get("xhigh_thinking_count"),
            "ok_run_count": spark_summary.get("ok_run_count"),
            "pending_first_canary_run_count": spark_summary.get("pending_first_canary_run_count"),
            "error_count": spark_summary.get("error_count"),
            "duration_regression_count": spark_summary.get("duration_regression_count"),
            "successful_natural_runs": spark_ok_jobs,
            "authority_note": (
                "Operational canary evidence only; no model-ranking, finance-correctness, "
                "portfolio/canon, paper/live/account, or owner-approval authority."
            ),
        },
        "model_run_ledger": {
            "source": rel(MODEL_RUN_LEDGER),
            "status": model_run_ledger.get("status"),
            "row_count": model_run_summary.get("row_count"),
            "ok_rows": model_run_summary.get("ok_rows"),
            "blocked_or_error_rows": model_run_summary.get("blocked_or_error_rows"),
            "attribution_applicable_rows": model_run_summary.get("attribution_applicable_rows"),
            "session_attribution_applicable_rows": model_run_summary.get("session_attribution_applicable_rows"),
            "model_attributed_rows": model_run_summary.get("model_attributed_rows"),
            "session_attributed_rows": model_run_summary.get("session_attributed_rows"),
            "model_attribution_coverage": model_run_summary.get("model_attribution_coverage"),
            "session_attribution_coverage": model_run_summary.get("session_attribution_coverage"),
            "model_attribution_applicable_coverage": model_run_summary.get("model_attribution_applicable_coverage"),
            "session_attribution_applicable_coverage": model_run_summary.get("session_attribution_applicable_coverage"),
            "authority_note": (
                "Normalized operational evidence only. Useful for measuring coverage "
                "and latency/status collection; insufficient for model ranking until "
                "sample size and session attribution improve."
            ),
        },
        "token_cost_economics": {
            "source": rel(TOKEN_USAGE_LEDGER),
            "status": token_usage_ledger.get("status"),
            "token_event_count": token_event_rows,
            "total_tokens": int(as_num(token_usage_summary.get("total_tokens"))),
            "api_equivalent_cost_rows": token_cost_rows,
            "api_equivalent_cost_event_coverage_percent": round(token_cost_coverage_percent, 4),
            "api_equivalent_cost_usd_total": token_usage_summary.get("api_equivalent_cost_usd_total"),
            "api_equivalent_estimate_status": token_usage_summary.get("api_equivalent_estimate_status"),
            "actual_billed_cost_known": bool(token_usage_summary.get("actual_billed_cost_known")),
            "actual_billed_cost_source": token_usage_summary.get("actual_billed_cost_source"),
            "authority_note": (
                "Authoritative economics path (Gateway usage-cost / token_usage_ledger) per the "
                "2026-08-13 telemetry role split. Cost is API-equivalent benchmark, NOT an invoice "
                "(actual_billed_cost_known=false). Coverage is still partial and too thin to unlock "
                "cross-model economic claims; the WF74 maturity gate stays partial until producer "
                "lanes emit joinable per-run token receipts over time."
            ),
        },
        "otel_backend_enabled": bool(otel_summary),
    }


def decision_quality_track(inputs: dict[str, Any]) -> dict[str, Any]:
    ledger = inputs["reco_ledger"]
    performance = as_dict(inputs.get("recommendation_performance"))
    finance_sql = as_dict(inputs.get("finance_sql_validation"))
    quote_snapshot = as_dict(inputs.get("quote_snapshot"))
    controller = as_dict(inputs.get("alert_controller"))
    digest = as_dict(inputs.get("alert_digest"))
    pivot = as_dict(inputs.get("alerts_os_pivot"))
    tracking = as_dict(ledger.get("recommendation_tracking_summary"))
    taxonomy = as_dict(ledger.get("outcome_grading_taxonomy"))
    durable = as_dict(ledger.get("durable_v2_ledger"))
    grade_history = as_dict(durable.get("grade_history"))
    outcome_summary = as_dict(performance.get("recommendation_outcomes"))
    controller_summary = as_dict(controller.get("summary"))
    digest_summary = as_dict(digest.get("summary"))
    durable_append_allowed = bool(tracking.get("durable_append_allowed") and durable.get("append_only") and durable.get("review_only"))
    recommendation_rows = int(as_num(durable.get("recommendation_tracking_rows") or outcome_summary.get("recommendation_tracking_rows")))
    graded_rows = int(as_num(grade_history.get("graded_ledger_event_count") or outcome_summary.get("outcome_grade_assigned_count")))
    assigned_grade_events = int(as_num(grade_history.get("assigned_grade_event_count")))
    source_green = {
        "guarded_sql": finance_sql.get("status") == "ok" and as_dict(finance_sql.get("validation")).get("status") == "ok",
        "quote_snapshot": quote_snapshot.get("status") == "ok",
        "alert_controller": controller.get("status") == "ok" and as_dict(controller.get("validation")).get("status") == "ok",
        "recommendation_digest": digest.get("status") == "ok" and as_dict(digest.get("validation")).get("status") == "ok",
        "pivot_validator": pivot.get("status") == "ok" and as_dict(pivot.get("validation")).get("status") == "ok",
    }
    scorecard_active_now = bool(durable_append_allowed and recommendation_rows and graded_rows)
    active_chain_green = all(source_green.values())
    readiness = (
        "active_measurement_only_semantic_claims_gated"
        if scorecard_active_now
        else "partial_recommendation_outcome_evidence"
        if recommendation_rows
        else "blocked_on_recommendation_outcomes"
    )
    return {
        "readiness": readiness,
        "summary": (
            "Review-only recommendation outcomes and the active alert evidence chain "
            "measure process quality, evidence freshness, and alert-state discipline. "
            "They do not authorize predictive, model-ranking, execution, or capital claims."
        ),
        "metrics": {
            "scorecard_active_now": scorecard_active_now,
            "scorecard_activation_basis": (
                "append_only_recommendation_outcomes"
                if scorecard_active_now
                else "insufficient_review_only_recommendation_outcomes"
            ),
            "tracking_row_count": recommendation_rows,
            "graded_rows": graded_rows,
            "semantic_outcome_grade_count": graded_rows,
            "assigned_grade_event_count": assigned_grade_events,
            "grade_taxonomy_count": len(as_dict(grade_history.get("grade_counts"))),
            "assignment_status": taxonomy.get("assignment_status"),
            "durable_append_allowed": durable_append_allowed,
            "recommendation_outcome_status": performance.get("status"),
            "recommendation_grade_counts": as_dict(grade_history.get("grade_counts")),
            "active_alert_chain_green": active_chain_green,
            "active_alert_chain_components": source_green,
            "alert_ticker_count": int(as_num(controller_summary.get("ticker_count"))),
            "alert_state_counts": as_dict(controller_summary.get("alert_state_counts")),
            "freshness_review_ticker_count": len(controller_summary.get("freshness_review_tickers") or []),
            "digest_ticker_count": int(as_num(digest_summary.get("ticker_count"))),
            "semantic_outcome_claim_allowed": False,
            "predictive_or_model_ranking_allowed": False,
            "consumer_posture": ledger.get("consumer_posture"),
        },
        "blockers": [
            *([] if recommendation_rows else ["review-only recommendation outcomes are missing"]),
            *([] if graded_rows else ["review-only recommendation grades are missing"]),
            *([] if durable_append_allowed else ["durable append gate not approved (durable_append_allowed=false)"]),
            *([] if active_chain_green else ["active alerts OS evidence chain is not fully green"]),
        ],
        "claim_blockers": [
            "predictive scoring, model ranking, win-rate, and expected-return claims remain blocked",
        ],
        "sources": [
            rel(RECO_LEDGER),
            rel(RECOMMENDATION_PERFORMANCE),
            rel(FINANCE_SQL_VALIDATION),
            rel(QUOTE_SNAPSHOT),
            rel(ALERT_CONTROLLER),
            rel(ALERT_DIGEST),
            rel(ALERTS_OS_PIVOT),
        ],
    }


def learning_capture_track(inputs: dict[str, Any]) -> dict[str, Any]:
    ledger = as_dict(inputs.get("model_learning_ledger"))
    improvement = as_dict(inputs.get("improvement_ledger"))
    summary = as_dict(ledger.get("summary"))
    improvement_summary = as_dict(improvement.get("summary"))
    improvement_kpis = as_dict(improvement.get("learning_loop_kpis"))
    improvement_open = improvement_summary.get("latest_open_count")
    improvement_closed = improvement_summary.get("latest_closed_count")
    if improvement_closed is None:
        improvement_closed = 0
    if improvement_kpis.get("anti_theater_status"):
        improvement_anti_theater_status = improvement_kpis.get("anti_theater_status")
    elif int(as_num(improvement_summary.get("high_priority_overdue_open_count"))) > 0:
        improvement_anti_theater_status = "blocked_by_overdue_backlog"
    elif int(as_num(improvement_closed)) <= 0:
        improvement_anti_theater_status = "proposal_loop_active_no_closure_proof"
    else:
        improvement_anti_theater_status = "proposal_loop_with_closure_proof"
    improvement_total = int(as_num(improvement_open)) + int(as_num(improvement_closed))
    improvement_closure_rate = improvement_kpis.get("closure_rate")
    if improvement_closure_rate is None and improvement_total:
        improvement_closure_rate = round(int(as_num(improvement_closed)) / improvement_total, 4)
    by_domain = as_dict(summary.get("by_domain"))
    privacy = as_dict(ledger.get("privacy_scan"))
    runtime_rows = int(as_num(summary.get("runtime_otel_rows")))
    coding_runtime_rows = int(as_num(summary.get("coding_runtime_rows")))
    runtime_probe_status = None
    runtime_fields = None
    coding_runtime_status = None
    coding_runtime_first_pass_clean = None
    coding_runtime_rework_required = None
    for row in ledger.get("rows", []):
        if isinstance(row, dict) and row.get("domain") == "runtime_otel" and row.get("source_id") == "runtime_metadata_probe_summary":
            metadata = as_dict(row.get("metadata"))
            runtime_probe_status = row.get("status")
            runtime_fields = metadata.get("allowed_field_count")
        if isinstance(row, dict) and row.get("domain") == "coding_runtime" and row.get("source_id") == "coding_runtime_kpi_summary":
            metadata = as_dict(row.get("metadata"))
            coding_runtime_status = row.get("status")
            coding_runtime_first_pass_clean = metadata.get("first_pass_validation_clean")
            coding_runtime_rework_required = metadata.get("rework_required")
    active = ledger.get("status") == "ok" and privacy.get("status") == "ok"
    return {
        "readiness": "active_metadata_only" if active else "missing_or_blocked",
        "summary": (
            "Metadata-only model/tool/failure/coding learning capture is active from "
            "local proof artifacts. It records names, statuses, durations, categories, "
            "and validator outcomes while raw prompts, responses, tool payloads, "
            "system prompts, secrets, and external export remain blocked."
        ),
        "metrics": {
            "row_count": summary.get("row_count"),
            "model_rows": summary.get("model_rows"),
            "tool_rows": summary.get("tool_rows"),
            "failure_rows": summary.get("failure_rows"),
            "coding_rows": summary.get("coding_rows"),
            "runtime_otel_rows": runtime_rows,
            "coding_runtime_rows": coding_runtime_rows,
            "runtime_probe_status": runtime_probe_status,
            "runtime_allowed_field_count": runtime_fields,
            "coding_runtime_status": coding_runtime_status,
            "coding_runtime_first_pass_clean": coding_runtime_first_pass_clean,
            "coding_runtime_rework_required": coding_runtime_rework_required,
            "improvement_open_count": improvement_open,
            "improvement_closed_count": improvement_closed,
            "improvement_recurring_open_count": improvement_summary.get("recurring_open_count"),
            "improvement_closure_rate": improvement_closure_rate,
            "improvement_anti_theater_status": improvement_anti_theater_status,
            "improvement_high_priority_overdue_count": improvement_kpis.get("high_priority_overdue_open_count"),
            "domain_counts": by_domain,
            "privacy_scan_status": privacy.get("status"),
            "forbidden_key_count": privacy.get("forbidden_key_count"),
        },
        "sources": [rel(MODEL_LEARNING_LEDGER), rel(IMPROVEMENT_LEDGER)],
        "blocked_claims": [
            "model ranking",
            "investment correctness from runtime metrics",
            "raw content review",
            "capture-depth expansion",
            "base-model self-modification",
        ],
    }


def model_attribution(inputs: dict[str, Any]) -> dict[str, Any]:
    model_run_ledger = as_dict(inputs.get("model_run_ledger"))
    summary = as_dict(model_run_ledger.get("summary"))
    coverage = as_num(summary.get("model_attribution_coverage"))
    session_coverage = as_num(summary.get("session_attribution_coverage"))
    applicable_coverage = as_num(summary.get("model_attribution_applicable_coverage"))
    session_applicable_coverage = as_num(summary.get("session_attribution_applicable_coverage"))
    recent_window = as_dict(summary.get("model_attribution_recent_window"))
    recent_coverage = as_num(summary.get("model_attribution_recent_coverage"))
    readiness = "partial" if coverage > 0 else "missing"
    instrumentation_working = recent_coverage >= 0.85
    return {
        "readiness": readiness,
        "attribution_coverage": coverage,
        "session_attribution_coverage": session_coverage,
        "attribution_applicable_coverage": applicable_coverage,
        "session_attribution_applicable_coverage": session_applicable_coverage,
        "recent_attribution_coverage": recent_coverage,
        "recent_attribution_window": recent_window,
        "instrumentation_working": instrumentation_working,
        "source": rel(MODEL_RUN_LEDGER),
        "row_count": int(as_num(summary.get("row_count"))),
        "attribution_applicable_rows": int(as_num(summary.get("attribution_applicable_rows"))),
        "session_attribution_applicable_rows": int(as_num(summary.get("session_attribution_applicable_rows"))),
        "model_attributed_rows": int(as_num(summary.get("model_attributed_rows"))),
        "session_attributed_rows": int(as_num(summary.get("session_attributed_rows"))),
        "schema_slots": ["model_path", "session_id", "workflow", "produced_at_utc"],
        "summary": (
            "Model attribution is now partially collected through the model-run "
            "ledger when producers stamp model_path. The applicable-row metric "
            "separates agent/model runs from local validator timings so coverage "
            "does not look worse than the actual instrumentable surface. Session "
            "coverage still needs broader producer stamping before model-vs-model "
            "comparison is allowed."
        ),
        "next_step": (
            (
                f"Instrumentation is working: recent-window coverage is {recent_coverage} "
                f"over {int(as_num(recent_window.get('applicable_rows')))} applicable rows. "
                "All-time coverage stays low only because pre-instrumentation rows cannot "
                "be backfilled, so do not spend effort re-stamping producers. The real "
                "remaining blockers are per-run outcome metrics (tokens/cost/duration are "
                "null on lane rows) and a skewed model mix with too few comparable samples."
            )
            if instrumentation_working
            else (
                "Stamp session_id/run_id/model_path on helper lanes, recommendation-review rows, "
                "PM jobs, and any new agent-run producers; keep runtime validator "
                "commands as non-applicable operational timings. Require repeated sample "
                "history before ranking."
            )
        ),
    }


def readiness_gates(tracks: dict[str, Any], attribution: dict[str, Any]) -> list[dict[str, Any]]:
    gates = []
    decision_metrics = as_dict(as_dict(tracks.get("decision_quality")).get("metrics"))
    graded_rows = int(as_num(decision_metrics.get("graded_rows")))
    scorecard_active_now = bool(decision_metrics.get("scorecard_active_now"))
    gates.append({
        "gate": "recommendation_outcome_history",
        "status": "review_measurement_active" if scorecard_active_now and graded_rows else "blocked",
        "blocks_track": "none" if scorecard_active_now else "decision_quality",
        "blocks_claim": "semantic_predictive_decision_quality",
        "track_status": "active_measurement_only" if scorecard_active_now else "not_active",
        "detail": (
            "Append-only recommendation outcomes are available for review-only process measurement; predictive and model-ranking claims remain blocked."
            if scorecard_active_now and graded_rows
            else "Collect append-only recommendation outcomes and deterministic review grades before activating this track."
        ),
    })
    gates.append({
        "gate": "otel_backend",
        "status": "metadata_layer_active",
        "blocks_track": "performance",
        "detail": "Basic OTEL is operational and metadata-only learning capture is active; direct runtime fields count only when otel_runtime_metadata_probe.py observes approved fields with no forbidden markers.",
    })
    gates.append({
        "gate": "model_attribution",
        "status": "partial" if attribution.get("readiness") == "partial" else "missing",
        "blocks_track": "all_cross_model_comparison",
        "detail": attribution["next_step"],
    })
    return gates


def _status_from_ok(ok: bool, warnings: bool = False) -> str:
    if not ok:
        return "needs_attention"
    return "active_with_warnings" if warnings else "active"


def _loop(
    *,
    loop_id: str,
    domain: str,
    owner_surface: str,
    status: str,
    meaning: str,
    observed_signals: dict[str, Any],
    next_safe_action: str,
    proof_sources: list[Path],
    feedback_sink: str,
    blocker_or_limit: str | None = None,
) -> dict[str, Any]:
    return {
        "loop_id": loop_id,
        "domain": domain,
        "owner_surface": owner_surface,
        "status": status,
        "meaning": meaning,
        "observed_signals": observed_signals,
        "next_safe_action": next_safe_action,
        "feedback_sink": feedback_sink,
        "blocker_or_limit": blocker_or_limit,
        "proof_sources": [rel(path) for path in proof_sources],
    }


def efficiency_loops(inputs: dict[str, Any], tracks: dict[str, Any], attribution: dict[str, Any]) -> dict[str, Any]:
    runtime_summary = as_dict(inputs["runtime_perf"].get("summary"))
    changed_router = as_dict(inputs.get("changed_file_router"))
    changed_summary = as_dict(changed_router.get("summary"))
    pm_control = as_dict(inputs.get("pm_control"))
    pm_summary = as_dict(pm_control.get("summary"))
    pm_readiness = as_dict(pm_summary.get("pm_readiness"))
    route_efficiency = as_dict(inputs.get("route_efficiency"))
    route_summary = as_dict(route_efficiency.get("summary"))
    wf73_audit = as_dict(inputs.get("wf73_audit"))
    wf73_summary = as_dict(wf73_audit.get("summary"))
    cron_control = as_dict(inputs.get("cron_control"))
    cron_summary = as_dict(cron_control.get("summary"))
    otel_ops = as_dict(inputs.get("otel_ops"))
    otel_summary = as_dict(otel_ops.get("summary"))
    otel_window_summary = as_dict(inputs.get("otel_window_summary"))
    otel_windows = [row for row in otel_window_summary.get("windows", []) if isinstance(row, dict)]
    decision_track = as_dict(tracks.get("decision_quality"))
    decision_metrics = as_dict(decision_track.get("metrics"))
    learning_track = as_dict(tracks.get("learning_capture"))
    learning_metrics = as_dict(learning_track.get("metrics"))
    coding_runtime = as_dict(inputs.get("coding_runtime_probe"))
    coding_kpis = as_dict(coding_runtime.get("kpis"))

    loops = [
        _loop(
            loop_id="coding_validation_efficiency",
            domain="coding",
            owner_surface="scripts/changed_file_validator_router.py / scripts/runtime_performance_scorecard.py",
            status=_status_from_ok(
                bool(runtime_summary)
                and runtime_summary.get("blocked_count") == 0
                and changed_router.get("status") == "ok"
                and coding_runtime.get("status") in {None, "ok"},
                changed_summary.get("recommended_budget") in {"shared", "major"} or bool(coding_kpis.get("rework_required")),
            ),
            meaning=(
                "Changed code is routed to a validation budget, and representative "
                "Python/Go/Node/SQL checks are timed so slow or blocked proof can be "
                "caught instead of rediscovered manually."
            ),
            observed_signals={
                "runtime_checks_total": runtime_summary.get("checks_total"),
                "runtime_blocked_count": runtime_summary.get("blocked_count"),
                "runtime_total_duration_ms": runtime_summary.get("total_duration_ms"),
                "changed_path_count": changed_summary.get("changed_path_count"),
                "recommended_budget": changed_summary.get("recommended_budget"),
                "recommended_command_count": changed_summary.get("recommendation_count"),
                "coding_runtime_status": coding_runtime.get("status"),
                "coding_first_pass_clean": coding_kpis.get("first_pass_validation_clean"),
                "coding_rework_required": coding_kpis.get("rework_required"),
                "coding_validator_elapsed_seconds": coding_kpis.get("validator_elapsed_seconds"),
                "coding_failure_buckets": coding_kpis.get("failure_bucket_counts"),
            },
            next_safe_action=(
                "Use scripts/changed_file_validator_router.py and scripts/coding_runtime_kpi_probe.py "
                "for the current diff, then run scripts/runtime_performance_scorecard.py when "
                "proof timing or validator coverage changes."
            ),
            feedback_sink="WF73 validation budget / WF74 runtime performance history",
            blocker_or_limit=(
                "Worktree has broad pre-existing change residue; diff-size signals "
                "are routing aids, not clean-state proof."
                if as_num(changed_summary.get("changed_path_count")) > 100
                else None
            ),
            proof_sources=[RUNTIME_PERF, CHANGED_FILE_ROUTER, CODING_RUNTIME_PROBE],
        ),
        _loop(
            loop_id="model_quality_efficiency",
            domain="models",
            owner_surface="model_quality_scorecard.py / model_run_ledger.py / wf74_model_quality_collection_cron_runner.py",
            status="active_with_known_gates",
            meaning=(
                "Model/run evidence, Spark cron canaries, alert/recommendation evidence "
                "discipline, and OTEL collector health are joined into one review-only "
                "scorecard. It is not a model ranker because mature semantic "
                "outcome claims and richer cost/tool OTEL fields are still gated."
            ),
            observed_signals={
                "model_run_rows": attribution.get("row_count"),
                "model_applicable_coverage": attribution.get("attribution_applicable_coverage"),
                "session_applicable_coverage": attribution.get("session_attribution_applicable_coverage"),
                "learning_metadata_rows": learning_metrics.get("row_count"),
                "learning_metadata_privacy_scan": learning_metrics.get("privacy_scan_status"),
                "learning_tool_rows": learning_metrics.get("tool_rows"),
                "learning_coding_rows": learning_metrics.get("coding_rows"),
                "learning_runtime_otel_rows": learning_metrics.get("runtime_otel_rows"),
                "learning_coding_runtime_rows": learning_metrics.get("coding_runtime_rows"),
                "coding_runtime_first_pass_clean": learning_metrics.get("coding_runtime_first_pass_clean"),
                "coding_runtime_rework_required": learning_metrics.get("coding_runtime_rework_required"),
                "runtime_probe_status": learning_metrics.get("runtime_probe_status"),
                "runtime_allowed_field_count": learning_metrics.get("runtime_allowed_field_count"),
                "recommendation_tracking_rows": decision_metrics.get("tracking_row_count"),
                "recommendation_graded_rows": decision_metrics.get("graded_rows"),
                "active_alert_chain_green": decision_metrics.get("active_alert_chain_green"),
                "alert_ticker_count": decision_metrics.get("alert_ticker_count"),
                "freshness_review_ticker_count": decision_metrics.get("freshness_review_ticker_count"),
                "otel_event_count": otel_summary.get("event_count"),
                "otel_trace_batches": otel_summary.get("trace_batches"),
                "otel_window_summary_status": otel_window_summary.get("status"),
                "otel_window_count": len(otel_windows),
            },
            next_safe_action=(
                "Keep the WF74 collection runner as the single scheduled owner; next "
                "enhancement is producer stamping plus mature recommendation-outcome "
                "review, not runtime-based model ranking."
            ),
            feedback_sink="WF74 model-quality scorecard and recommendation-outcome ledger",
            blocker_or_limit=(
                "Recommendation-outcome measurement is review-only; semantic/predictive "
                "claims remain gated. Direct runtime "
                "cost/tool field depth remains limited, but metadata-only learning capture is active."
            ),
            proof_sources=[MODEL_RUN_LEDGER, MODEL_LEARNING_LEDGER, CODING_RUNTIME_PROBE, RECO_LEDGER, RECOMMENDATION_PERFORMANCE, ALERT_CONTROLLER, ALERT_DIGEST, ALERTS_OS_PIVOT, CRON_SPARK_CANARY, OTEL_OPS, OTEL_WINDOW_SUMMARY, OTEL_RUNTIME_PROBE],
        ),
        _loop(
            loop_id="implementation_queue_efficiency",
            domain="implementation",
            owner_surface="pm_control_packet.py / Active Workflows",
            status=_status_from_ok(
                pm_control.get("status") == "ok"
                and as_num(pm_readiness.get("blocked_lanes")) == 0
                and as_num(pm_readiness.get("stale_lanes")) == 0,
                pm_readiness.get("readiness_band") != "green",
            ),
            meaning=(
                "Implementation work is flowing through PM readiness, validation budgets, "
                "closeout modes, and a top next action instead of disconnected chat tasks."
            ),
            observed_signals={
                "pm_readiness_band": pm_readiness.get("readiness_band"),
                "average_score": pm_readiness.get("average_score"),
                "stale_lanes": pm_readiness.get("stale_lanes"),
                "blocked_lanes": pm_readiness.get("blocked_lanes"),
            },
            next_safe_action="Refresh the PM control packet and use only non-finance or active alerts-OS implementation work.",
            feedback_sink="PM control packet / workflow capsules / daily memory closeout",
            proof_sources=[PM_CONTROL],
        ),
        _loop(
            loop_id="routing_efficiency",
            domain="routing",
            owner_surface="wf73_control_plane_audit.py / wf73_route_efficiency_scorecard.py / fast_path_qa.py",
            status=_status_from_ok(
                route_efficiency.get("status") == "ok" and as_num(route_summary.get("slow_count")) == 0,
                bool(wf73_summary.get("warning_surfaces")),
            ),
            meaning=(
                "Fast-route SQL/API probes and the ordered WF73 audit verify that "
                "routing surfaces are usable before broad scans or source-open drilldown."
            ),
            observed_signals={
                "route_probe_count": route_summary.get("probe_count"),
                "slow_count": route_summary.get("slow_count"),
                "failed_or_unavailable_count": route_summary.get("failed_or_unavailable_count"),
                "wf73_status": wf73_audit.get("status"),
                "wf73_warning_surfaces": wf73_summary.get("warning_surfaces"),
                "fast_path_status": wf73_summary.get("fast_path_status"),
            },
            next_safe_action=route_summary.get("next_safe_action")
            or "Use WF73 ordered audit and fast-path QA before broad workspace scans.",
            feedback_sink="WF73 route/index/boot optimization",
            blocker_or_limit=(
                "WF73 still reports warning surfaces; currently these are review queues or boot-size warnings, not route failures."
                if wf73_summary.get("warning_surfaces")
                else None
            ),
            proof_sources=[ROUTE_EFFICIENCY, WF73_AUDIT],
        ),
        _loop(
            loop_id="cron_otel_operations",
            domain="operations",
            owner_surface="cron_control_packet.py / otel_ops_control.py",
            status=_status_from_ok(
                cron_control.get("status") == "ok"
                and otel_ops.get("status") == "ok"
                and as_num(cron_summary.get("escalation_signal_count")) == 0,
                as_num(cron_summary.get("requires_attention_count")) > 0,
            ),
            meaning=(
                "Cron and OTEL now close the operational loop: scheduled jobs produce "
                "freshness/review signals, and local telemetry proves collector health "
                "without changing capture depth."
            ),
            observed_signals={
                "enabled_cron_jobs": cron_summary.get("enabled_job_count"),
                "fresh_cron_jobs": cron_summary.get("fresh_count"),
                "requires_attention_count": cron_summary.get("requires_attention_count"),
                "escalation_signal_count": cron_summary.get("escalation_signal_count"),
                "otel_collector_healthy": cron_summary.get("otel_collector_healthy"),
                "otel_metric_batches": otel_summary.get("metric_batches"),
                "otel_reported_spans": otel_summary.get("reported_spans"),
                "otel_window_count": len(otel_windows),
            },
            next_safe_action=cron_summary.get("next_safe_action")
            or "Refresh cron_control_packet.py and drill only when stale, blocked, or review buckets change.",
            feedback_sink="WF76 cron oversight / WF74 OTEL model-quality follow-up",
            blocker_or_limit="OTEL field depth is still collector-batch level; metadata-only learning capture covers model/tool/failure/coding scoring from local artifacts.",
            proof_sources=[CRON_CONTROL, OTEL_OPS, MODEL_LEARNING_LEDGER],
        ),
    ]

    status_counts = dict(Counter(str(loop.get("status")) for loop in loops))
    domains = sorted({str(loop.get("domain")) for loop in loops})
    enhancement_queue = [
        {
            "priority": 1,
            "owner": "WF74 / model-quality-scorecard",
            "action": "Keep WF74 collection behind wf74_model_quality_collection_cron_runner.py; do not schedule component ledgers separately.",
            "status": "active",
        },
        {
            "priority": 2,
            "owner": "alerts OS / WF74",
            "action": "Keep recommendation-outcome measurement review-only; apply predictive or semantic claims only under a separate evidence gate.",
            "status": "active_measurement_only_claims_gated",
        },
        {
            "priority": 3,
            "owner": "WF74 / OTEL",
            "action": "Use model_learning_metadata_ledger.py as the metadata-only capture layer; direct runtime/config capture remains separately gated.",
            "status": "active_metadata_only",
        },
        {
            "priority": 4,
            "owner": "WF73 / WF76 / main session",
            "action": "Keep cron review buckets visible and act only on real stale, blocked, owner-decision, or repeated review items.",
            "status": "monitor",
        },
    ]
    standing_rules = [
        {
            "rule_id": "input_changed_not_broken",
            "principle": "Changed inputs are not automatically broken outputs.",
            "meaning": (
                "Completed or validated lanes should move to monitor/review status when "
                "inputs drift, and should reopen only when proof is missing, invalid, "
                "blocked, or explicitly configured to reopen on stale inputs."
            ),
            "owner_surface": "changed_file_validator_router.py / parallel_lane_recommender.py / cron_freshness_spine.py",
            "next_safe_action": "Classify input drift as monitor-only unless a validator exposes a true blocker.",
        },
        {
            "rule_id": "producer_before_consumer",
            "principle": "Refresh producers before judging consumers.",
            "meaning": (
                "Assembler, ledger, PM, cron, and parity checks must run after their "
                "source producers so stale consumer artifacts do not create false "
                "regression or retirement blockers."
            ),
            "owner_surface": "wf74_model_quality_collection_cron_runner.py / run_alerts_recommendations_chain.py",
            "next_safe_action": "Keep collection runners ordered from source producers to downstream scorecards and parity checks.",
        },
        {
            "rule_id": "operational_telemetry_only",
            "principle": "OTEL proves operational telemetry, not coding skill or model rank.",
            "meaning": (
                "OTEL counts collector health, metric batches, trace batches, spans, "
                "and related run evidence. Coding-skill lessons belong in WF74/RSI "
                "observations, candidate builders, and skill proposals."
            ),
            "owner_surface": "otel_ops_control.py / model_quality_scorecard.py / WF74 RSI loop",
            "next_safe_action": "Use OTEL for ops health and WF74/RSI for implementation-learning proposals.",
        },
        {
            "rule_id": "freshness_precision",
            "principle": "Not intraday-fresh is not the same as stale.",
            "meaning": (
                "Post-close/current-to-window evidence should be warning or review "
                "context unless the active workflow specifically requires fresh "
                "intraday quotes or real-time proof."
            ),
            "owner_surface": "alert_level_freshness_controller.py / run_alerts_recommendations_chain.py",
            "next_safe_action": "Name the freshness window before promoting a warning into a blocker.",
        },
        {
            "rule_id": "self_contained_when_possible",
            "principle": "Prefer self-contained proof over fragile external dependencies.",
            "meaning": (
                "Use in-repo parsers and local derived artifacts when they reduce "
                "runtime dependency risk, and label stale source data instead of "
                "pretending it is current."
            ),
            "owner_surface": "macro_signal_spine.py / model_quality_scorecard.py",
            "next_safe_action": "Treat missing or stale external source fields as explicit evidence warnings, not hidden success.",
        },
    ]
    return {
        "schema": "wf74.efficiency_loops.v1",
        "status": "active_partial",
        "meaning": (
            "Coding, model, implementation, routing, and operations feedback loops "
            "are live enough for current work. The remaining gaps are explicit gates, "
            "not hidden missing work."
        ),
        "summary": {
            "loop_count": len(loops),
            "domains": domains,
            "status_counts": status_counts,
            "next_safe_action": (
                "Use the PM top action for execution, changed-file router for proof "
                "budget, WF74 scorecard for model loop state, and WF73/cron packets "
                "for routing and scheduled feedback."
            ),
        },
        "loops": loops,
        "enhancement_queue": enhancement_queue,
        "standing_rules": standing_rules,
    }


def build_scorecard(inputs: dict[str, Any]) -> dict[str, Any]:
    impl = implementation_quality_track(inputs)
    perf = performance_track(inputs)
    decision = decision_quality_track(inputs)
    learning = learning_capture_track(inputs)
    attribution = model_attribution(inputs)
    tracks = {
        "implementation_quality": impl,
        "performance": perf,
        "learning_capture": learning,
        "decision_quality": decision,
    }
    loops = efficiency_loops(inputs, tracks, attribution)
    active_tracks = [
        name for name, t in tracks.items()
        if str(t["readiness"]).startswith("active") or str(t["readiness"]).startswith("partial")
    ]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "scaffold_active",
        "posture": "review_only_scaffold_not_a_deployed_model_ranker",
        "active_tracks": active_tracks,
        "tracks": tracks,
        "efficiency_loops": loops,
        "model_attribution": attribution,
        "finance_sql_canon_context": inputs.get("finance_sql_canon"),
        "readiness_gates": readiness_gates(tracks, attribution),
        "next_actions": [
            loops["summary"]["next_safe_action"],
            "Stamp model/session attribution on producing surfaces, then join here.",
            "Keep recommendation outcomes append-only and review-only while preserving evidence lineage.",
            "Use deterministic recommendation grades as process-quality evidence; keep semantic/predictive claims gated.",
            "Use model_learning_metadata_ledger.py for metadata-only tool/failure/coding/runtime-OTEL learning capture; keep direct runtime capture gated by otel_runtime_metadata_probe.py.",
            "Keep otel_ops_control.py refreshed so WF74 can distinguish observed friction from anecdotes.",
        ],
        "authority_boundary": {
            "review_only": True,
            "model_ranking_claim": False,
            "investment_correctness_from_runtime_metrics": False,
            "base_model_self_modification": False,
            "otel_backend_enablement_in_this_lane": False,
            "durable_sql_canon_current_state_allowed": True,
            "sql_canon_mutation_allowed": False,
            "owner_approval_inference": False,
            "portfolio_or_canon_mutation": False,
            "paper_or_live_or_account_action": False,
        },
    }


def validate(scorecard: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    for key, path in [
        ("harness", HARNESS),
        ("outcome_eval", OUTCOME_EVAL),
        ("runtime_perf", RUNTIME_PERF),
        ("otel_window_summary", OTEL_WINDOW_SUMMARY),
        ("otel_runtime_probe", OTEL_RUNTIME_PROBE),
        ("reco_ledger", RECO_LEDGER),
        ("recommendation_performance", RECOMMENDATION_PERFORMANCE),
        ("finance_sql_validation", FINANCE_SQL_VALIDATION),
        ("quote_snapshot", QUOTE_SNAPSHOT),
        ("alert_controller", ALERT_CONTROLLER),
        ("alert_digest", ALERT_DIGEST),
        ("alerts_os_pivot", ALERTS_OS_PIVOT),
        ("cron_spark_canary", CRON_SPARK_CANARY),
        ("model_run_ledger", MODEL_RUN_LEDGER),
        ("model_learning_ledger", MODEL_LEARNING_LEDGER),
        ("improvement_ledger", IMPROVEMENT_LEDGER),
        ("coding_runtime_probe", CODING_RUNTIME_PROBE),
        ("pm_control", PM_CONTROL),
        ("cron_control", CRON_CONTROL),
        ("route_efficiency", ROUTE_EFFICIENCY),
        ("wf73_audit", WF73_AUDIT),
        ("changed_file_router", CHANGED_FILE_ROUTER),
    ]:
        if not inputs[key]:
            findings.append({"severity": "warning", "detail": f"input artifact missing or empty: {rel(path)}"})

    decision = scorecard["tracks"]["decision_quality"]
    if not decision["metrics"].get("durable_append_allowed") and decision["metrics"].get("graded_rows"):
        findings.append({"severity": "critical", "detail": "decision_quality cannot use recommendation grades without the review-only append contract."})
    if decision["metrics"].get("scorecard_active_now") is not True:
        findings.append({"severity": "warning", "detail": "decision_quality scorecard needs append-only recommendation rows and review grades."})
    if decision["metrics"].get("semantic_outcome_claim_allowed") is not False:
        findings.append({"severity": "critical", "detail": "semantic outcome claims must remain blocked until mature evidence exists."})
    if decision["metrics"].get("predictive_or_model_ranking_allowed") is not False:
        findings.append({"severity": "critical", "detail": "predictive/model-ranking claims must remain blocked."})
    outcome_gate = next(
        (gate for gate in scorecard.get("readiness_gates", []) if as_dict(gate).get("gate") == "recommendation_outcome_history"),
        {},
    )
    if decision["metrics"].get("scorecard_active_now") and as_dict(outcome_gate).get("blocks_track") != "none":
        findings.append({"severity": "critical", "detail": "recommendation outcome gate must not block an active review-only measurement track."})
    if decision["metrics"].get("scorecard_active_now") and as_dict(outcome_gate).get("blocks_claim") != "semantic_predictive_decision_quality":
        findings.append({"severity": "critical", "detail": "recommendation outcome gate must keep semantic/predictive claims blocked."})
    if not decision["metrics"].get("active_alert_chain_green"):
        findings.append({"severity": "warning", "detail": "active alerts OS evidence chain is not fully green."})

    boundary = scorecard["authority_boundary"]
    for flag in (
        "model_ranking_claim",
        "investment_correctness_from_runtime_metrics",
        "base_model_self_modification",
        "owner_approval_inference",
        "portfolio_or_canon_mutation",
        "paper_or_live_or_account_action",
        "otel_backend_enablement_in_this_lane",
        "sql_canon_mutation_allowed",
    ):
        if boundary.get(flag) is not False:
            findings.append({"severity": "critical", "detail": f"authority boundary violated: {flag} must be False"})
    if boundary.get("durable_sql_canon_current_state_allowed") is not True:
        findings.append({"severity": "critical", "detail": "authority boundary violated: durable_sql_canon_current_state_allowed must be True"})
    finance_sql = as_dict(scorecard.get("finance_sql_canon_context"))
    if finance_sql.get("status") != "ok":
        findings.append({"severity": "critical", "detail": "finance SQL-canon guard must be ok before scoring finance answer quality."})
    if not as_dict(finance_sql.get("answer_route_policy")).get("legacy_42_retired_from_blocking"):
        findings.append({"severity": "critical", "detail": "finance SQL-canon route must retire legacy 42 from blocking readiness checks."})

    if scorecard["model_attribution"]["attribution_coverage"] not in (0, 0.0) and scorecard["model_attribution"]["readiness"] == "missing":
        findings.append({"severity": "warning", "detail": "attribution coverage reported but readiness still 'missing'; reconcile."})

    spark_canary = as_dict(scorecard["tracks"]["performance"].get("spark_cron_canary"))
    if spark_canary.get("model_under_test") and spark_canary.get("authority_note") is None:
        findings.append({"severity": "critical", "detail": "spark cron canary evidence must include authority_note."})
    otel_local_ops = as_dict(scorecard["tracks"]["performance"].get("otel_local_ops"))
    if otel_local_ops.get("window_summary_status") and otel_local_ops.get("window_count") != 5:
        findings.append({"severity": "critical", "detail": "OTEL window summary must expose five windows when present."})

    learning = as_dict(scorecard["tracks"].get("learning_capture"))
    learning_metrics = as_dict(learning.get("metrics"))
    if learning_metrics.get("privacy_scan_status") != "ok":
        findings.append({"severity": "critical", "detail": "learning_capture privacy scan must be ok."})
    if int(as_num(learning_metrics.get("tool_rows"))) <= 0:
        findings.append({"severity": "warning", "detail": "learning_capture has no tool rows."})
    if learning_metrics.get("runtime_probe_status") == "blocked":
        findings.append({"severity": "critical", "detail": "runtime OTEL probe is blocked by forbidden markers."})
    if learning_metrics.get("improvement_anti_theater_status") == "proposal_loop_active_no_closure_proof":
        findings.append({"severity": "warning", "detail": "learning loop has no closure proof."})

    loops = as_dict(scorecard.get("efficiency_loops"))
    loop_rows = [row for row in loops.get("loops", []) if isinstance(row, dict)]
    required_domains = {"coding", "models", "implementation", "routing", "operations"}
    observed_domains = {str(row.get("domain")) for row in loop_rows}
    missing_domains = sorted(required_domains - observed_domains)
    if missing_domains:
        findings.append({"severity": "critical", "detail": f"efficiency loop domain missing: {', '.join(missing_domains)}"})
    for row in loop_rows:
        for field in ("loop_id", "owner_surface", "status", "next_safe_action", "feedback_sink", "proof_sources"):
            if not row.get(field):
                findings.append({"severity": "critical", "detail": f"efficiency loop {row.get('loop_id') or '<unknown>'} missing {field}"})
    if not loops.get("enhancement_queue"):
        findings.append({"severity": "critical", "detail": "efficiency loops must expose a next enhancement queue"})
    rule_rows = [row for row in loops.get("standing_rules", []) if isinstance(row, dict)]
    required_rules = {
        "input_changed_not_broken",
        "producer_before_consumer",
        "operational_telemetry_only",
        "freshness_precision",
        "self_contained_when_possible",
    }
    observed_rules = {str(row.get("rule_id")) for row in rule_rows}
    missing_rules = sorted(required_rules - observed_rules)
    if missing_rules:
        findings.append({"severity": "critical", "detail": f"efficiency standing rule missing: {', '.join(missing_rules)}"})
    for row in rule_rows:
        for field in ("rule_id", "principle", "meaning", "owner_surface", "next_safe_action"):
            if not row.get(field):
                findings.append({"severity": "critical", "detail": f"efficiency standing rule {row.get('rule_id') or '<unknown>'} missing {field}"})

    critical = sum(1 for f in findings if f["severity"] == "critical")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    status = "critical" if critical else ("warning" if warnings else "ok")
    return {"status": status, "critical": critical, "warnings": warnings, "findings": findings}


def render_md(scorecard: dict[str, Any]) -> str:
    lines = [
        "# Model Quality Scorecard (WF74 scaffold)",
        "",
        f"- Generated: {scorecard['generated_at_utc']}",
        f"- Status: {scorecard['status']} ({scorecard['posture']})",
        f"- Active tracks: {', '.join(scorecard['active_tracks']) or 'none'}",
        "",
        "## Tracks",
    ]
    for name, track in scorecard["tracks"].items():
        lines.append(f"### {name} - readiness: {track['readiness']}")
        lines.append(track["summary"])
        metrics = track.get("metrics") or track.get("runtime_latency_live")
        if isinstance(metrics, dict):
            for k, v in metrics.items():
                lines.append(f"- {k}: {v}")
        lines.append("")
    attribution = scorecard["model_attribution"]
    lines.append("## Model attribution")
    lines.append(f"- readiness: {attribution['readiness']} (coverage {attribution['attribution_coverage']})")
    lines.append(attribution["summary"])
    lines.append("")
    lines.append("## Efficiency loops")
    loops = scorecard["efficiency_loops"]
    summary = loops["summary"]
    lines.append(f"- status: {loops['status']}")
    lines.append(f"- loop_count: {summary['loop_count']}")
    lines.append(f"- domains: {', '.join(summary['domains'])}")
    lines.append(f"- next_safe_action: {summary['next_safe_action']}")
    for loop in loops["loops"]:
        lines.append(f"- {loop['loop_id']} [{loop['status']}]: {loop['meaning']}")
    lines.append("")
    lines.append("### Standing interpretation rules")
    for rule in loops.get("standing_rules", []):
        lines.append(f"- {rule['rule_id']}: {rule['principle']}")
    lines.append("")
    lines.append("## Readiness gates")
    for gate in scorecard["readiness_gates"]:
        blocked_surface = gate.get("blocks_claim") or gate.get("blocks_track")
        lines.append(f"- {gate['gate']} [{gate['status']}] blocks {blocked_surface}: {gate['detail']}")
    return "\n".join(lines) + "\n"


def append_history(scorecard: dict[str, Any], validation: dict[str, Any]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "generated_at_utc": scorecard["generated_at_utc"],
        "status": scorecard["status"],
        "validation_status": validation["status"],
        "active_tracks": scorecard["active_tracks"],
        "decision_quality_readiness": scorecard["tracks"]["decision_quality"]["readiness"],
        "attribution_coverage": scorecard["model_attribution"]["attribution_coverage"],
        "efficiency_loop_status": scorecard["efficiency_loops"]["status"],
        "efficiency_loop_count": scorecard["efficiency_loops"]["summary"]["loop_count"],
    }
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WF74 review-only model-quality scorecard scaffold")
    parser.add_argument("--write", action="store_true", help="write JSON artifact")
    parser.add_argument("--write-md", action="store_true", help="also write the Markdown summary")
    parser.add_argument("--validate", action="store_true", help="run validation and reflect status")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    inputs = load_inputs()
    scorecard = build_scorecard(inputs)
    validation = validate(scorecard, inputs)
    scorecard["validation"] = validation

    json_path = Path(args.json_out)
    if args.write:
        atomic_write_json(json_path, scorecard)
        append_history(scorecard, validation)
        if args.write_md:
            atomic_write_text(json_path.with_suffix(".md"), render_md(scorecard))

    if not args.quiet:
        print(
            f"status={scorecard['status']} validation={validation['status']} "
            f"active_tracks={','.join(scorecard['active_tracks']) or 'none'} "
            f"critical={validation['critical']} warnings={validation['warnings']}"
        )
        for finding in validation["findings"]:
            print(f"  [{finding['severity']}] {finding['detail']}")

    if args.validate and validation["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
