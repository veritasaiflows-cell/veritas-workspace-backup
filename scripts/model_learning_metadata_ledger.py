#!/usr/bin/env python3
"""Build the approved metadata-only learning ledger for WF74.

This is the implementation side of the model-learning capture approval packet.
It records model, tool/command, failure, and coding metadata from existing local
proof artifacts. It intentionally does not capture raw prompts, model responses,
tool inputs, tool outputs, system prompts, secrets, credentials, customer data,
or any external export payload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "model-learning-metadata-ledger.json"
OUT_MD = TMP / "model-learning-metadata-ledger.md"
SCHEMA = "veritas.model_learning_metadata_ledger.v1"

APPROVAL_PACKET = TMP / "model-learning-capture-approval-packet.json"
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"
REPEATABLE_CLOSEOUT = TMP / "repeatable-work-closeout.json"
MODEL_QUALITY = TMP / "model-quality-scorecard.json"
FINANCE_CORRECTNESS = TMP / "finance-recommendation-correctness-ledger-current.json"
FINANCE_RESPONSE_QUALITY = TMP / "finance-response-quality-slice.json"
OTEL_RUNTIME_PROBE = TMP / "otel-runtime-metadata-probe.json"
OTEL_TOOL_WORKFLOW_METADATA = TMP / "otel-tool-workflow-metadata.json"
CODING_RUNTIME_PROBE = TMP / "coding-runtime-kpi-probe.json"
CODING_OUTCOME_LEDGER = TMP / "coding-outcome-ledger-current.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "customer_account_or_brokerage_capture_allowed": False,
    "base_model_self_modification_allowed": False,
    "model_ranking_claim_allowed": False,
    "investment_correctness_from_runtime_metrics_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_KEYS = {
    "prompt",
    "raw_prompt",
    "response",
    "raw_response",
    "completion",
    "tool_input",
    "tool_inputs",
    "tool_output",
    "tool_outputs",
    "system_prompt",
    "authorization",
    "cookie",
    "api_key",
    "oauth_token",
    "bearer",
    "secret",
    "credential",
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


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def load_inputs() -> dict[str, Any]:
    return {
        "approval_packet": as_dict(load_json_artifact(APPROVAL_PACKET)),
        "model_run_ledger": as_dict(load_json_artifact(MODEL_RUN_LEDGER)),
        "wf74_runner": as_dict(load_json_artifact(WF74_RUNNER)),
        "changed_file_router": as_dict(load_json_artifact(CHANGED_FILE_ROUTER)),
        "repeatable_closeout": as_dict(load_json_artifact(REPEATABLE_CLOSEOUT)),
        "model_quality": as_dict(load_json_artifact(MODEL_QUALITY)),
        "finance_correctness": as_dict(load_json_artifact(FINANCE_CORRECTNESS)),
        "finance_response_quality": as_dict(load_json_artifact(FINANCE_RESPONSE_QUALITY)),
        "otel_runtime_probe": as_dict(load_json_artifact(OTEL_RUNTIME_PROBE)),
        "otel_tool_workflow_metadata": as_dict(load_json_artifact(OTEL_TOOL_WORKFLOW_METADATA)),
        "coding_runtime_probe": as_dict(load_json_artifact(CODING_RUNTIME_PROBE)),
        "coding_outcome_ledger": as_dict(load_json_artifact(CODING_OUTCOME_LEDGER)),
    }


def row_base(domain: str, source: Path, source_id: str, status: str | None) -> dict[str, Any]:
    return {
        "schema": "veritas.model_learning_metadata_ledger.row.v1",
        "row_id": stable_id(domain, rel(source), source_id, status),
        "domain": domain,
        "source_artifact": rel(source),
        "source_id": source_id,
        "status": status or "unknown",
        "metadata": {},
        "scoring_use": None,
        "payload_capture": False,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def model_rows(model_run_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_row in as_list(model_run_ledger.get("rows")):
        if not isinstance(source_row, dict):
            continue
        attribution = as_dict(source_row.get("attribution"))
        if not attribution.get("model_applicable"):
            continue
        row = row_base("model", MODEL_RUN_LEDGER, str(source_row.get("run_id")), source_row.get("status"))
        row["metadata"] = {
            "producer": source_row.get("producer"),
            "run_kind": source_row.get("run_kind"),
            "model_provider": source_row.get("model_provider"),
            "model_path": source_row.get("model_path"),
            "thinking": source_row.get("thinking"),
            "session_present": attribution.get("session_present"),
            "duration_ms": source_row.get("duration_ms"),
            "tokens_present": source_row.get("tokens") is not None,
            "cost_present": source_row.get("cost") is not None,
            "error_type": source_row.get("error_type"),
            "retry_count": source_row.get("retry_count"),
        }
        row["scoring_use"] = "model attribution, latency, token/cost coverage, and reliability scoring"
        rows.append(row)
    return rows


def tool_rows(wf74_runner: dict[str, Any], closeout: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in as_list(wf74_runner.get("steps")):
        if not isinstance(step, dict):
            continue
        row = row_base("tools", WF74_RUNNER, str(step.get("name")), step.get("status"))
        command = as_list(step.get("command"))
        row["metadata"] = {
            "tool_name": step.get("name"),
            "tool_namespace": "workspace_script",
            "operation_category": "wf74_collection_step",
            "duration_ms": step.get("duration_ms"),
            "returncode": step.get("returncode"),
            "command_stem": " ".join(str(part) for part in command[:2]),
            "failure_kind": "none" if step.get("status") == "ok" else "collection_step_blocked",
        }
        row["scoring_use"] = "tool/command reliability, latency, and failure scoring"
        rows.append(row)
    for step in as_list(closeout.get("steps")):
        if not isinstance(step, dict):
            continue
        row = row_base("tools", REPEATABLE_CLOSEOUT, str(step.get("name")), "ok" if step.get("ok") else "blocked")
        command = as_list(step.get("command"))
        row["metadata"] = {
            "tool_name": step.get("name"),
            "tool_namespace": "workspace_script",
            "operation_category": "repeatable_closeout_step",
            "returncode": step.get("returncode"),
            "command_stem": " ".join(str(part) for part in command[:2]),
            "failure_kind": "none" if step.get("ok") else "closeout_step_blocked",
        }
        row["scoring_use"] = "closeout reliability and repeated-failure scoring"
        rows.append(row)
    return rows


def failure_rows(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = [
        ("wf74_runner", WF74_RUNNER, inputs["wf74_runner"]),
        ("repeatable_closeout", REPEATABLE_CLOSEOUT, inputs["repeatable_closeout"]),
        ("model_quality", MODEL_QUALITY, inputs["model_quality"]),
        ("finance_correctness", FINANCE_CORRECTNESS, inputs["finance_correctness"]),
        ("finance_response_quality", FINANCE_RESPONSE_QUALITY, inputs["finance_response_quality"]),
    ]
    for label, path, payload in sources:
        validation = as_dict(payload.get("validation"))
        status = payload.get("status") or validation.get("status")
        if status in {None, "ok", "scaffold_active"} and not validation.get("errors"):
            continue
        row = row_base("failures", path, label, str(status or "unknown"))
        row["metadata"] = {
            "failure_kind": "validation_or_status_not_ok",
            "root_cause_bucket": "artifact_status",
            "surface": label,
            "recoverable": True,
            "repeated_pattern": False,
            "validation_error_count": len(as_list(validation.get("errors"))),
            "validation_warning_count": len(as_list(validation.get("warnings"))),
            "owner_action_required": False,
        }
        row["scoring_use"] = "failure taxonomy and repair prioritization"
        rows.append(row)
    return rows


def coding_rows(changed_file_router: dict[str, Any], closeout: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary = as_dict(changed_file_router.get("summary"))
    row = row_base("coding", CHANGED_FILE_ROUTER, "changed_file_router_summary", changed_file_router.get("status"))
    row["metadata"] = {
        "changed_file_count": summary.get("changed_path_count"),
        "recommended_budget": summary.get("recommended_budget"),
        "recommendation_count": summary.get("recommendation_count"),
        "validation_status": as_dict(changed_file_router.get("validation")).get("status"),
    }
    row["scoring_use"] = "validator-budget and changed-file routing scoring"
    rows.append(row)

    closeout_summary = as_dict(closeout.get("summary"))
    row = row_base("coding", REPEATABLE_CLOSEOUT, "repeatable_closeout_summary", closeout.get("status"))
    row["metadata"] = {
        "steps_run": closeout_summary.get("steps_run"),
        "failed_step_count": len(as_list(closeout_summary.get("failed_steps"))),
        "validation_status": as_dict(closeout.get("validation")).get("status"),
        "rework_required": bool(as_list(closeout_summary.get("failed_steps"))),
    }
    row["scoring_use"] = "implementation closeout and rework scoring"
    rows.append(row)
    return rows


def runtime_otel_rows(probe: dict[str, Any]) -> list[dict[str, Any]]:
    if not probe:
        return []
    rows: list[dict[str, Any]] = []
    summary = as_dict(probe.get("summary"))
    status = probe.get("status")
    row = row_base("runtime_otel", OTEL_RUNTIME_PROBE, "runtime_metadata_probe_summary", str(status or "unknown"))
    row["metadata"] = {
        "runtime_metadata_observed": summary.get("runtime_metadata_observed"),
        "allowed_field_count": summary.get("allowed_field_count"),
        "raw_content_marker_count": summary.get("raw_content_marker_count"),
        "secret_or_header_marker_count": summary.get("secret_or_header_marker_count"),
        "source_log": as_dict(probe.get("source")).get("collector_log"),
        "line_count": as_dict(probe.get("source")).get("line_count"),
        "observed_categories": as_dict(probe.get("observed_categories")),
        "status_meaning": summary.get("status_meaning"),
    }
    row["scoring_use"] = "direct runtime metadata coverage and privacy-gate scoring"
    rows.append(row)
    for field, count in as_dict(probe.get("observed_allowed_fields")).items():
        field_row = row_base("runtime_otel", OTEL_RUNTIME_PROBE, f"field:{field}", str(status or "unknown"))
        field_row["metadata"] = {
            "runtime_field": field,
            "observed_count": count,
            "category": (
                "tool"
                if str(field).startswith("openclaw.tool") or str(field).startswith("gen_ai.tool")
                else "model"
                if str(field).startswith("openclaw.model") or str(field).startswith("gen_ai.")
                else "operational"
            ),
        }
        field_row["scoring_use"] = "runtime field coverage tracking"
        rows.append(field_row)
    return rows


def tool_workflow_metadata_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload:
        return []
    rows: list[dict[str, Any]] = []
    summary = as_dict(payload.get("summary"))
    status = str(payload.get("status") or "unknown")
    summary_row = row_base("tool_workflow_metadata", OTEL_TOOL_WORKFLOW_METADATA, "tool_workflow_metadata_summary", status)
    summary_row["metadata"] = {
        "row_count": summary.get("row_count"),
        "unique_tool_count": summary.get("unique_tool_count"),
        "workflow_attributed_count": summary.get("workflow_attributed_count"),
        "session_attributed_count": summary.get("session_attributed_count"),
        "failed_or_blocked_count": summary.get("failed_or_blocked_count"),
        "failure_category_counts": as_dict(summary.get("failure_category_counts")),
        "privacy_scan_status": as_dict(payload.get("privacy_scan")).get("status"),
    }
    summary_row["scoring_use"] = "metadata-only tool/workflow/session diagnostics for OTEL drift explanation and workflow repair"
    rows.append(summary_row)
    for item in as_list(payload.get("rows"))[:250]:
        row_dict = as_dict(item)
        row = row_base(
            "tool_workflow_metadata",
            OTEL_TOOL_WORKFLOW_METADATA,
            str(row_dict.get("row_id")),
            str(row_dict.get("status") or "unknown"),
        )
        row["metadata"] = {
            "tool_name": row_dict.get("tool_name"),
            "tool_namespace": row_dict.get("tool_namespace"),
            "workflow_id": row_dict.get("workflow_id"),
            "session_present": bool(row_dict.get("session_id") or row_dict.get("session_key") or row_dict.get("session_label")),
            "lane_id": row_dict.get("lane_id"),
            "workstream_id": row_dict.get("workstream_id"),
            "source_kind": row_dict.get("source_kind"),
            "failure_category": row_dict.get("failure_category"),
            "returncode": row_dict.get("returncode"),
            "duration_ms": row_dict.get("duration_ms"),
        }
        row["scoring_use"] = "tool reliability, workflow attribution, and metadata-only failure routing"
        rows.append(row)
    return rows


def coding_runtime_rows(probe: dict[str, Any]) -> list[dict[str, Any]]:
    if not probe:
        return []
    rows: list[dict[str, Any]] = []
    kpis = as_dict(probe.get("kpis"))
    row = row_base("coding_runtime", CODING_RUNTIME_PROBE, "coding_runtime_kpi_summary", str(probe.get("status") or "unknown"))
    row["metadata"] = {
        "changed_path_count": kpis.get("changed_path_count"),
        "recommended_budget": kpis.get("recommended_budget"),
        "recommended_validator_count": kpis.get("recommended_validator_count"),
        "validator_elapsed_seconds": kpis.get("validator_elapsed_seconds"),
        "validator_failed_count": kpis.get("validator_failed_count"),
        "closeout_failed_count": kpis.get("closeout_failed_count"),
        "wf74_steps_blocked": kpis.get("wf74_steps_blocked"),
        "learning_coding_rows": kpis.get("learning_coding_rows"),
        "learning_runtime_otel_rows": kpis.get("learning_runtime_otel_rows"),
        "first_pass_validation_clean": kpis.get("first_pass_validation_clean"),
        "rework_required": kpis.get("rework_required"),
        "failure_bucket_counts": as_dict(kpis.get("failure_bucket_counts")),
    }
    row["scoring_use"] = "coding runtime KPI, validator selection, rework, and PM monitoring"
    rows.append(row)
    for bucket, count in as_dict(kpis.get("failure_bucket_counts")).items():
        bucket_row = row_base("coding_runtime", CODING_RUNTIME_PROBE, f"failure_bucket:{bucket}", str(probe.get("status") or "unknown"))
        bucket_row["metadata"] = {"failure_bucket": bucket, "count": count}
        bucket_row["scoring_use"] = "repeated coding failure pattern tracking"
        rows.append(bucket_row)
    return rows


def coding_outcome_rows(outcome: dict[str, Any]) -> list[dict[str, Any]]:
    if not outcome:
        return []
    rows: list[dict[str, Any]] = []
    summary = as_dict(outcome.get("ledger_summary"))
    summary_row = row_base("coding_outcome", CODING_OUTCOME_LEDGER, "coding_outcome_summary", str(outcome.get("status") or "unknown"))
    summary_row["metadata"] = {
        "ledger_row_count": summary.get("ledger_row_count"),
        "run_attributed_count": summary.get("run_attributed_count"),
        "session_attributed_count": summary.get("session_attributed_count"),
        "model_attributed_count": summary.get("model_attributed_count"),
        "proof_attached_count": summary.get("proof_attached_count"),
        "acceptance_declared_count": summary.get("acceptance_declared_count"),
        "validator_proxy_passed_count": summary.get("validator_proxy_passed_count"),
        "total_retry_count": summary.get("total_retry_count"),
        "rework_required_count": summary.get("rework_required_count"),
        "regression_observed_count": summary.get("regression_observed_count"),
    }
    summary_row["scoring_use"] = "coding outcome attribution, validator pass/fail proxy, retry, and edit-churn scoring"
    rows.append(summary_row)
    for record in as_list(outcome.get("recent_records")):
        if not isinstance(record, dict) or record.get("_parse_error"):
            continue
        coding = as_dict(record.get("coding_outcome"))
        churn = as_dict(coding.get("edit_churn"))
        row = row_base("coding_outcome", CODING_OUTCOME_LEDGER, str(record.get("event_id")), str(record.get("lane_status") or "unknown"))
        row["metadata"] = {
            "run_id": record.get("run_id"),
            "workflow_id": record.get("workflow_id"),
            "lane_id": record.get("lane_id"),
            "workstream_id": record.get("workstream_id"),
            "lane_kind": record.get("lane_kind"),
            "session_present": as_dict(record.get("attribution")).get("session_present"),
            "model_present": as_dict(record.get("attribution")).get("model_present"),
            "model_path": record.get("model_path"),
            "duration_minutes": record.get("duration_minutes"),
            "validator_proxy_passed": coding.get("validator_proxy_passed"),
            "retry_count": coding.get("retry_count"),
            "script_write_count": churn.get("script_write_count"),
            "test_write_count": churn.get("test_write_count"),
            "tmp_artifact_write_count": churn.get("tmp_artifact_write_count"),
            "state_or_data_write_count": churn.get("state_or_data_write_count"),
            "proof_attached": coding.get("proof_attached"),
            "acceptance_commands_declared": coding.get("acceptance_commands_declared"),
            "later_review_status": coding.get("later_review_status"),
        }
        row["scoring_use"] = "per-task coding outcome, attribution, validation proxy, retry, and edit-churn scoring"
        rows.append(row)
    return rows


def finance_response_quality_rows(slice_payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not slice_payload:
        return []
    rows: list[dict[str, Any]] = []
    summary = as_dict(slice_payload.get("summary"))
    row = row_base("finance_response_quality", FINANCE_RESPONSE_QUALITY, "finance_response_quality_summary", str(slice_payload.get("status") or "unknown"))
    row["metadata"] = {
        "archetype_count": summary.get("archetype_count"),
        "average_quality_score": summary.get("average_quality_score"),
        "blocked_archetype_count": summary.get("blocked_archetype_count"),
        "wf84_wf85_answer_path_ok": summary.get("wf84_wf85_answer_path_ok"),
        "wf72_support_only_confirmed": summary.get("wf72_support_only_confirmed"),
        "wf75_internal_service_slice_only": summary.get("wf75_internal_service_slice_only"),
        "sector_timing_warning_available": summary.get("sector_timing_warning_available"),
        "section_coverage_status": summary.get("section_coverage_status"),
        "technical_posture_missing_both_count": summary.get("technical_posture_missing_both_count"),
        "source_freshness_blocked_count": summary.get("source_freshness_blocked_count"),
        "source_open_blocked_count": summary.get("source_open_blocked_count"),
        "negative_canary_pass_count": summary.get("negative_canary_pass_count"),
        "remediation_tracks_needing_repair": summary.get("remediation_tracks_needing_repair"),
        "macro_signal_status": summary.get("macro_signal_status"),
        "macro_posture": summary.get("macro_posture"),
        "parity_critical_ticker_count": summary.get("parity_critical_ticker_count"),
    }
    row["scoring_use"] = "finance answer response-quality scoring and PM/WF74 feedback"
    rows.append(row)
    for archetype in as_list(slice_payload.get("archetypes")):
        if not isinstance(archetype, dict):
            continue
        archetype_row = row_base(
            "finance_response_quality",
            FINANCE_RESPONSE_QUALITY,
            str(archetype.get("archetype_id")),
            str(archetype.get("status") or "unknown"),
        )
        archetype_row["metadata"] = {
            "archetype_id": archetype.get("archetype_id"),
            "quality_score": archetype.get("quality_score"),
            "failed_required_check_count": len(as_list(archetype.get("failed_required_checks"))),
            "check_count": len(as_list(archetype.get("checks"))),
        }
        archetype_row["scoring_use"] = "answer archetype quality and missing-warning tracking"
        rows.append(archetype_row)
    return rows


def privacy_scan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if lowered in FORBIDDEN_KEYS:
                    findings.append({"path": f"{path}.{key}", "reason": "forbidden key"})
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
    walk(rows, "rows")
    return {
        "status": "blocked" if findings else "ok",
        "forbidden_key_count": len(findings),
        "findings": findings[:50],
    }


def build_ledger(inputs: dict[str, Any]) -> dict[str, Any]:
    rows = [
        *model_rows(inputs["model_run_ledger"]),
        *tool_rows(inputs["wf74_runner"], inputs["repeatable_closeout"]),
        *failure_rows(inputs),
        *coding_rows(inputs["changed_file_router"], inputs["repeatable_closeout"]),
        *runtime_otel_rows(inputs["otel_runtime_probe"]),
        *tool_workflow_metadata_rows(inputs["otel_tool_workflow_metadata"]),
        *coding_runtime_rows(inputs["coding_runtime_probe"]),
        *coding_outcome_rows(inputs["coding_outcome_ledger"]),
        *finance_response_quality_rows(inputs["finance_response_quality"]),
    ]
    by_domain: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for row in rows:
        by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + 1
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    scan = privacy_scan(rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if scan["status"] == "ok" else "blocked",
        "purpose": "Metadata-only model/tool/failure/coding learning ledger for WF74 scoring.",
        "approval_source": rel(APPROVAL_PACKET),
        "summary": {
            "row_count": len(rows),
            "by_domain": by_domain,
            "status_counts": status_counts,
            "model_rows": by_domain.get("model", 0),
            "tool_rows": by_domain.get("tools", 0),
            "failure_rows": by_domain.get("failures", 0),
            "coding_rows": by_domain.get("coding", 0),
            "runtime_otel_rows": by_domain.get("runtime_otel", 0),
            "tool_workflow_metadata_rows": by_domain.get("tool_workflow_metadata", 0),
            "coding_runtime_rows": by_domain.get("coding_runtime", 0),
            "coding_outcome_rows": by_domain.get("coding_outcome", 0),
            "finance_response_quality_rows": by_domain.get("finance_response_quality", 0),
            "privacy_scan_status": scan["status"],
        },
        "privacy_scan": scan,
        "rows": rows,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "limits": [
            "Ledger is derived from existing local proof artifacts plus the local-only runtime OTEL metadata probe when present.",
            "Tool rows capture command/tool names and metadata only, never tool inputs or outputs.",
            "Runtime OTEL rows are metadata coverage and privacy-gate evidence only; they never carry raw prompt, response, tool payload, or system-prompt text.",
            "Tool/workflow metadata rows capture tool names, status, failure category, workflow/session IDs, and timings only; they never carry raw command output or payloads.",
            "Coding-runtime rows are KPI metadata only; they never carry raw diffs or file contents.",
            "Model ranking remains blocked until sample size, attribution, and graded outcomes support it.",
            "Investment correctness cannot be inferred from this ledger.",
            "Finance-response-quality rows score answer contracts and warning coverage only; they do not grade investment outcomes.",
        ],
    }


def validate(ledger: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(ledger.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    if as_dict(ledger.get("privacy_scan")).get("status") != "ok":
        errors.append("privacy scan is not ok")
    summary = as_dict(ledger.get("summary"))
    for domain in ("model", "tools", "coding", "coding_outcome", "finance_response_quality"):
        if int(summary.get("by_domain", {}).get(domain, 0)) <= 0:
            warnings.append(f"no rows for expected domain: {domain}")
    for row in as_list(ledger.get("rows")):
        if row.get("payload_capture") is not False:
            errors.append(f"payload_capture must be false: {row.get('row_id')}")
    return {"status": "failed" if errors else "ok", "errors": errors, "warnings": warnings}


def render_md(ledger: dict[str, Any]) -> str:
    summary = as_dict(ledger.get("summary"))
    lines = [
        "# Model Learning Metadata Ledger",
        "",
        f"- Generated: {ledger.get('generated_at_utc')}",
        f"- Status: {ledger.get('status')}",
        f"- Rows: {summary.get('row_count')}",
        f"- By domain: `{json.dumps(summary.get('by_domain'), sort_keys=True)}`",
        f"- Privacy scan: {summary.get('privacy_scan_status')}",
        "",
        "## Limits",
    ]
    for item in as_list(ledger.get("limits")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(OUT_JSON))
    args = parser.parse_args(argv)

    ledger = build_ledger(load_inputs())
    validation = validate(ledger)
    ledger["validation"] = validation
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, ledger)
    if args.write_md:
        atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(ledger))
    if args.validate:
        print(json.dumps({"status": validation["status"], "json": rel(out), "errors": validation["errors"], "warnings": validation["warnings"]}, indent=2))
        return 1 if validation["errors"] else 0
    if not args.write and not args.write_md:
        print(json.dumps(ledger, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
