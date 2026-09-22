#!/usr/bin/env python3
"""Build the OTEL metadata learning loop packet.

This turns local-only OTEL and proof-artifact metadata into bounded
recommendations. It deliberately avoids raw prompts, responses, system prompts,
tool inputs/outputs, headers, secrets, and raw command output bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "otel-learning-loop.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.otel_learning_loop.v1"

LEARNING_WORKFLOW_ALLOWLIST = {"CRON", "WF73", "WF74", "WF88", "OTEL"}

OTEL_CONTROL = TMP / "otel-ops-control.json"
OTEL_WINDOWS = TMP / "otel-ops-window-summary.json"
OTEL_TOOL_WORKFLOW = TMP / "otel-tool-workflow-metadata.json"
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
VALIDATOR_TIMING = TMP / "validator-timing-ledger.json"
CODING_RUNTIME = TMP / "coding-runtime-kpi-probe.json"
CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
CRON_SIGNAL_SCORECARD = TMP / "cron-signal-scorecard.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
OWNER_DECISIONS = ROOT / "state" / "owner-decisions" / "otel-recommendations.json"
ATTRIBUTION_BRIDGE = TMP / "implementation-token-attribution-bridge.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "content_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_KEY_MARKERS = (
    "prompt",
    "message_content",
    "completion",
    "response_text",
    "tool_input",
    "tool_output",
    "tool_payload",
    "system_prompt",
    "authorization",
    "bearer",
    "api_key",
    "oauth",
    "access_token",
    "refresh_token",
    "secret",
    "credential",
    "password",
    "cookie",
    "header",
)

FORBIDDEN_VALUE_MARKERS = (
    "sk-",
    "Bearer ",
    "Authorization:",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "api_key",
    "oauth_token",
    "access_token",
    "refresh_token",
    "system_prompt",
)


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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_duration_ms(value: Any) -> float | None:
    """Parse a measured duration without treating absence as zero latency."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def model_row_scoring_eligible(row: dict[str, Any]) -> bool:
    """Return whether a model row may influence performance economics.

    Lane-register rows must carry the explicit post-cutover eligibility flag.
    Non-lane cron/runtime producers retain their independently sourced
    operational semantics, including legacy artifacts written before the flag
    existed.
    """
    attribution = as_dict(row.get("attribution"))
    if attribution.get("model_applicable") is not True:
        return False
    if row.get("producer") == "concurrent_lane_manager":
        return attribution.get("telemetry_eligible") is True
    return attribution.get("telemetry_eligible") is not False


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def redact_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if any(marker.lower() in value.lower() for marker in FORBIDDEN_VALUE_MARKERS):
        return "[REDACTED]"
    return value


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(marker in lowered for marker in FORBIDDEN_KEY_MARKERS):
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key_text}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker.lower() in lowered for marker in FORBIDDEN_VALUE_MARKERS):
            findings.append(f"forbidden_value:{path}")
    return findings


def model_cost_summary(model_run: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in as_list(model_run.get("rows")) if isinstance(row, dict)]
    model_rows = [row for row in rows if model_row_scoring_eligible(row)]
    uncredited_lane_rows = [
        row for row in rows
        if row.get("producer") == "concurrent_lane_manager"
        and bool(row.get("model_path") or as_dict(row.get("attribution")).get("model_present"))
        and not model_row_scoring_eligible(row)
    ]
    token_rows = [row for row in model_rows if row.get("tokens") is not None]
    cost_rows = [row for row in model_rows if row.get("cost") is not None]
    durations = [duration for row in model_rows if (duration := as_duration_ms(row.get("duration_ms"))) is not None]
    by_model: dict[str, dict[str, Any]] = {}
    for row in model_rows:
        model = str(row.get("model_path") or row.get("model_provider") or "unknown")
        bucket = by_model.setdefault(model, {
            "count": 0,
            "duration_covered_rows": 0,
            "duration_ms_total": 0.0,
            "tokens_rows": 0,
            "cost_rows": 0,
            "failure_rows": 0,
        })
        bucket["count"] += 1
        duration = as_duration_ms(row.get("duration_ms"))
        if duration is not None:
            bucket["duration_covered_rows"] += 1
            bucket["duration_ms_total"] += duration
        if row.get("tokens") is not None:
            bucket["tokens_rows"] += 1
        if row.get("cost") is not None:
            bucket["cost_rows"] += 1
        if str(row.get("status") or "").lower() not in {"ok", "complete", "success", ""}:
            bucket["failure_rows"] += 1
    for bucket in by_model.values():
        covered = int(bucket["duration_covered_rows"])
        bucket["avg_duration_ms"] = round(bucket["duration_ms_total"] / covered, 3) if covered else None
        del bucket["duration_ms_total"]
    return {
        "model_applicable_rows": len(model_rows),
        "model_performance_eligible_rows": len(model_rows),
        "uncredited_lane_audit_rows": len(uncredited_lane_rows),
        "token_coverage_rows": len(token_rows),
        "token_coverage_ratio": round(len(token_rows) / len(model_rows), 4) if model_rows else None,
        "cost_coverage_rows": len(cost_rows),
        "cost_coverage_ratio": round(len(cost_rows) / len(model_rows), 4) if model_rows else None,
        "avg_duration_ms": round(sum(durations) / len(durations), 3) if durations else None,
        "by_model": dict(sorted(by_model.items())),
    }


def tool_latency_summary(tool_workflow: dict[str, Any], validator_timing: dict[str, Any], coding_runtime: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in as_list(tool_workflow.get("rows")) if isinstance(row, dict)]
    durations = [row for row in rows if as_duration_ms(row.get("duration_ms")) is not None]
    failures = [row for row in rows if str(row.get("failure_category") or "none") != "none"]
    by_tool: dict[str, dict[str, Any]] = {}
    for row in durations:
        tool = str(row.get("tool_name") or "unknown")
        bucket = by_tool.setdefault(tool, {"count": 0, "duration_ms_total": 0.0, "failure_rows": 0})
        bucket["count"] += 1
        duration = as_duration_ms(row.get("duration_ms"))
        if duration is None:
            continue
        bucket["duration_ms_total"] += duration
        if str(row.get("failure_category") or "none") != "none":
            bucket["failure_rows"] += 1
    for bucket in by_tool.values():
        count = max(int(bucket["count"]), 1)
        bucket["avg_duration_ms"] = round(bucket["duration_ms_total"] / count, 3)
        del bucket["duration_ms_total"]
    slow_tools = sorted(by_tool.items(), key=lambda item: item[1].get("avg_duration_ms") or 0, reverse=True)[:10]
    timing_summary = as_dict(validator_timing.get("summary"))
    coding_kpis = as_dict(coding_runtime.get("kpis"))
    return {
        "tool_rows": len(rows),
        "duration_covered_rows": len(durations),
        "failure_rows": len(failures),
        "failure_categories": dict(Counter(str(row.get("failure_category") or "none") for row in rows)),
        "slowest_tools": [{"tool_name": name, **bucket} for name, bucket in slow_tools],
        "validator_elapsed_seconds": timing_summary.get("elapsed_seconds"),
        "validator_target_seconds": timing_summary.get("target_seconds"),
        "validator_slow": timing_summary.get("slow"),
        "coding_first_pass_clean": coding_kpis.get("first_pass_clean"),
        "coding_rework_required": coding_kpis.get("rework_required"),
    }


def _tel_strict_bool(value):
    return isinstance(value, bool)

def _tel_finite_nonneg(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 and value == value and value not in (float("inf"), float("-inf"))

def revalidate_telemetry_context(embedded):
    base = {"present": False, "fresh": False, "valid": False, "reason": "unknown"}
    if not isinstance(embedded, dict) or not embedded:
        return dict(base, reason="missing")
    probe = embedded.get("runtime_probe") if isinstance(embedded.get("runtime_probe"), dict) else None
    depth = embedded.get("token_depth") if isinstance(embedded.get("token_depth"), dict) else None
    if probe is None or depth is None:
        return dict(base, reason="malformed")
    for label, row in (("runtime_probe", probe), ("token_depth", depth)):
        ts = row.get("generated_at_utc")
        try:
            from datetime import datetime as _dt
            d = _dt.fromisoformat(str(ts).replace("Z", "+00:00"))
            if d.tzinfo is None:
                from datetime import timezone as _tz2
                d = d.replace(tzinfo=_tz2.utc)
            from datetime import datetime as _dt2, timezone as _tz
            age = (_dt2.now(_tz.utc) - d).total_seconds() / 3600.0
        except Exception:
            return dict(base, reason="learning_" + label + "_timestamp_malformed")
        if age < 0 or age > 24.0:
            return dict(base, reason="learning_" + label + "_stale")
    scalars = as_dict(probe.get("scalars")) if isinstance(probe.get("scalars"), dict) else {}
    for k in ("runtime_metadata_observed", "metadata_depth_approved_enabled", "file_exporter_observed", "debug_log_observed", "runtime_metadata_learning_ready"):
        if not _tel_strict_bool(scalars.get(k)):
            return dict(base, reason="learning_whitelist_type_invalid:" + k)
    v = scalars.get("allowed_field_count")
    if not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
        return dict(base, reason="learning_whitelist_type_invalid:allowed_field_count")
    for k in ("raw_content_marker_count", "secret_or_header_marker_count"):
        vv = scalars.get(k)
        if not _tel_finite_nonneg(vv) or vv != 0:
            return dict(base, reason="learning_raw_or_secret_marker_positive")
    if depth.get("status") != "owner_decision_pending" or depth.get("owner_gated") is not True:
        return dict(base, reason="learning_depth_not_owner_gated")
    return {"present": True, "fresh": True, "valid": True, "reason": "fresh_valid", "runtime_metadata_observed": scalars.get("runtime_metadata_observed"), "allowed_field_count": scalars.get("allowed_field_count"), "owner_gated_depth": True}

def otel_health_summary(otel: dict[str, Any], windows: dict[str, Any], telemetry_context: dict[str, Any] | None = None) -> dict[str, Any]:
    drift = as_dict(otel.get("drift"))
    summary = as_dict(otel.get("summary"))
    trend = as_dict(windows.get("trend_indicators"))
    embedded = telemetry_context if isinstance(telemetry_context, dict) else as_dict(otel.get("telemetry_context"))
    reval = revalidate_telemetry_context(embedded) if embedded else {"present": False, "fresh": False, "valid": False, "reason": "missing"}
    return {
        "collector_health": as_dict(otel.get("collector_health")).get("status"),
        "collector_loopback": as_dict(otel.get("collector_config")).get("binds_loopback_4318"),
        "status": otel.get("status"),
        "daily_event_count": summary.get("event_count"),
        "daily_warning_or_error_count": drift.get("daily_warning_or_error_count"),
        "daily_events_per_hour": drift.get("daily_events_per_hour"),
        "weekly_events_per_hour": drift.get("weekly_events_per_hour"),
        "daily_vs_weekly_event_rate_ratio": drift.get("daily_vs_weekly_event_rate_ratio"),
        "drift_status": drift.get("status"),
        "drift_reasons": drift.get("drift_reasons"),
        "weekly_warning_or_error_count": trend.get("weekly_warning_or_error_count"),
        "telemetry_status": reval.get("reason"),
        "telemetry_fresh_valid": bool(reval.get("valid")),
        "telemetry_runtime_observed": reval.get("runtime_metadata_observed"),
        "telemetry_allowed_fields": reval.get("allowed_field_count"),
        "telemetry_owner_gated_depth": reval.get("owner_gated_depth", False),
    }


def operational_friction_summary(
    cron_signal: dict[str, Any],
    workflow_advancement: dict[str, Any],
) -> dict[str, Any]:
    cron_scorecard = as_dict(cron_signal.get("scorecard"))
    workflow_summary = as_dict(workflow_advancement.get("summary"))
    attention_signals = [
        {
            "source": row.get("source"),
            "artifact": row.get("artifact"),
            "signal_class": row.get("signal_class"),
            "status": row.get("status"),
            "reason": row.get("reason"),
            "next_action": row.get("next_action"),
        }
        for row in as_list(cron_signal.get("signals"))
        if (
            isinstance(row, dict)
            and row.get("attention") == "requires_main_attention"
        )
    ][:8]
    blocked_workflows = [
        {
            "workflow_id": row.get("workflow_id"),
            "status": row.get("status"),
            "signal": row.get("signal"),
            "blockers": row.get("blockers"),
            "next_action": row.get("next_action"),
        }
        for row in as_list(workflow_advancement.get("signals"))
        if (
            isinstance(row, dict)
            and row.get("signal") == "blocked"
            and str(row.get("workflow_id") or "").upper() in LEARNING_WORKFLOW_ALLOWLIST
        )
    ][:8]
    return {
        "cron": {
            "blocked_count": cron_scorecard.get("blocked_count"),
            "requires_attention_count": cron_scorecard.get("requires_attention_count"),
            "enabled_job_count": cron_scorecard.get("enabled_job_count"),
            "attention_signals": attention_signals,
        },
        "workflow_advancement": {
            "blocked_count": len(blocked_workflows),
            "owner_needed_count": workflow_summary.get("owner_needed_count"),
            "cron_update_recommended": workflow_summary.get("cron_update_recommended"),
            "blocked_workflows": blocked_workflows,
        },
    }


def owner_decision_suppressions() -> dict[str, dict[str, Any]]:
    """Recommendation ids retired by an explicit owner decision record.

    Missing/unreadable record means no suppression (fail-open to the
    pre-decision behavior), never a blanket retirement.
    """
    try:
        record = as_dict(load_json_artifact(OWNER_DECISIONS))
    except Exception:
        return {}
    suppressed: dict[str, dict[str, Any]] = {}
    for row in as_list(record.get("decisions")):
        if not isinstance(row, dict):
            continue
        rec_id = row.get("id")
        if rec_id and row.get("decision") == "decline_and_retire_the_recommendation":
            suppressed[str(rec_id)] = {
                "id": rec_id,
                "decision": row.get("decision"),
                "decided_by": row.get("decided_by"),
                "decided_at_utc": row.get("decided_at_utc"),
                "evidence": row.get("evidence"),
            }
    return suppressed


ATTRIBUTION_BRIDGE_SCHEMA = "veritas.implementation_token_attribution_bridge.v1"
# Freshness SLA reuses this packet's own carry-forward contract
# (carry_forward_contract.stale_after_hours = 24): a bridge producer
# timestamp older than 24h is stale. Only the producer's generated_at_utc
# counts; filesystem mtime is never consulted.
ATTRIBUTION_BRIDGE_FRESHNESS_SLA_HOURS = 24
ATTRIBUTION_BRIDGE_OK_STATUSES = {"ok", "warning"}
ATTRIBUTION_BRIDGE_TERMINAL_RESOLUTIONS = {
    "complete",
    "terminal_unavailable_only",
    "historical_or_classified_unavailable_only",
}


def _strict_nonnegative_int(value: Any) -> int | None:
    """Accept only true ints >= 0. Bool, float, str, and None are malformed."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _parse_bridge_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def attribution_action_state(
    model_run: dict[str, Any],
    bridge: dict[str, Any],
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Partition live actionable attribution debt from historical terminal metadata.

    Uses only the attribution bridge owner's exact action-required signals
    (action_required_supported_runtime_gap_count, gap_resolution_status,
    closeout_enforcement_required) guarded by exact schema/status/validation
    shape and a fresh producer timestamp; never a time-only filter. Missing,
    blank, unknown, future, stale, error, or conflicting signals yield
    unknown, which callers must surface as a warning, never as monitor_only.
    """
    model_summary = as_dict(model_run.get("summary")) if isinstance(model_run, dict) else {}
    recent_coverage = as_dict(model_summary.get("model_attribution_recent_window")).get("coverage")
    source = bridge if isinstance(bridge, dict) else {}
    base = {
        "bridge_status": source.get("status"),
        "bridge_generated_at_utc": source.get("generated_at_utc"),
        "model_attribution_recent_coverage": recent_coverage,
    }

    def unknown(reason: str, required_count: Any = None, gap_resolution: Any = None, closeout_required: Any = None) -> dict[str, Any]:
        return {
            "state": "unknown",
            "reason": reason,
            "action_required_supported_runtime_gap_count": required_count,
            "gap_resolution_status": gap_resolution,
            "closeout_enforcement_required": closeout_required,
            **base,
        }

    def decided(state: str, reason: str, required_count: int, gap_resolution: str, closeout_required: bool) -> dict[str, Any]:
        return {
            "state": state,
            "reason": reason,
            "action_required_supported_runtime_gap_count": required_count,
            "gap_resolution_status": gap_resolution,
            "closeout_enforcement_required": closeout_required,
            **base,
        }

    if not isinstance(bridge, dict) or not bridge:
        return unknown("bridge_missing_or_blank")
    if bridge.get("schema") != ATTRIBUTION_BRIDGE_SCHEMA:
        return unknown("bridge_schema_mismatch")
    if bridge.get("status") not in ATTRIBUTION_BRIDGE_OK_STATUSES:
        return unknown("bridge_status_not_ok")
    validation = bridge.get("validation")
    if not isinstance(validation, dict):
        return unknown("bridge_validation_missing")
    if validation.get("status") not in ATTRIBUTION_BRIDGE_OK_STATUSES:
        return unknown("bridge_validation_not_ok")
    if validation.get("errors"):
        return unknown("bridge_validation_errors")
    now = now_utc if now_utc is not None else datetime.now(timezone.utc)
    generated = _parse_bridge_timestamp(bridge.get("generated_at_utc"))
    if generated is None:
        return unknown("bridge_timestamp_missing_or_malformed")
    if generated > now:
        return unknown("bridge_timestamp_in_future")
    if (now - generated).total_seconds() / 3600.0 > ATTRIBUTION_BRIDGE_FRESHNESS_SLA_HOURS:
        return unknown("bridge_stale")
    summary = bridge.get("summary")
    if not isinstance(summary, dict):
        return unknown("bridge_summary_missing")
    gap_resolution = summary.get("gap_resolution_status")
    closeout_required = summary.get("closeout_enforcement_required")
    required_count = _strict_nonnegative_int(summary.get("action_required_supported_runtime_gap_count"))
    if required_count is None:
        return unknown("bridge_required_count_malformed", gap_resolution=gap_resolution, closeout_required=closeout_required)
    if closeout_required is not True and closeout_required is not False:
        return unknown("bridge_closeout_absent_or_malformed", required_count=required_count, gap_resolution=gap_resolution)
    if not isinstance(gap_resolution, str) or not gap_resolution:
        return unknown("bridge_gap_resolution_unknown", required_count=required_count, closeout_required=closeout_required)
    actionable = required_count > 0 or closeout_required is True or gap_resolution == "stamp_required"
    if actionable:
        conflict = (
            (required_count > 0 and (closeout_required is False or gap_resolution in ATTRIBUTION_BRIDGE_TERMINAL_RESOLUTIONS))
            or (closeout_required is True and (required_count == 0 or gap_resolution in ATTRIBUTION_BRIDGE_TERMINAL_RESOLUTIONS))
            or (gap_resolution == "stamp_required" and (required_count == 0 or closeout_required is False))
        )
        if conflict:
            return unknown("bridge_signals_conflict", required_count=required_count, gap_resolution=gap_resolution, closeout_required=closeout_required)
        return decided("action_required", "explicit_bridge_action_signal", required_count, gap_resolution, closeout_required)
    if required_count == 0 and closeout_required is False and gap_resolution in ATTRIBUTION_BRIDGE_TERMINAL_RESOLUTIONS:
        return decided("monitor_only", "explicit_terminal_or_historical_only", required_count, gap_resolution, closeout_required)
    return unknown("bridge_gap_resolution_unknown", required_count=required_count, gap_resolution=gap_resolution, closeout_required=closeout_required)


def build_recommendations(
    cost: dict[str, Any],
    latency: dict[str, Any],
    health: dict[str, Any],
    queue: dict[str, Any],
    friction: dict[str, Any],
    model_run: dict[str, Any],
    bridge: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    token_ratio = cost.get("token_coverage_ratio")
    cost_ratio = cost.get("cost_coverage_ratio")
    if token_ratio is None or token_ratio < 0.8 or cost_ratio is None or cost_ratio < 0.8:
        recommendations.append({
            "id": "token_cost_metadata_depth",
            "severity": "warning",
            "decision": "prepare_owner_gated_metadata_depth_patch",
            "rationale": "Token/cost coverage is too low for reliable model-routing economics.",
            "blocked_capture": ["raw prompts", "raw responses", "tool payloads", "system prompts", "secrets", "headers"],
            "next_action": "If approved later, add local-only token/cost metadata capture with redaction validation and rollback.",
        })
    action_state = attribution_action_state(model_run, bridge).get("state")
    live_debt_visible = as_float(cost.get("uncredited_lane_audit_rows")) > 0
    if live_debt_visible or action_state == "action_required":
        if action_state == "monitor_only":
            recommendations.append({
                "id": "historical_attribution_claim_limits",
                "severity": "info",
                "decision": "limit_model_economics_claims_to_supported_reverified_windows",
                "rationale": "Uncredited lanes are audit-visible but the attribution bridge classifies the remaining supported-runtime gap as historical or terminal-unavailable; no live stamping action is required.",
                "next_action": "Keep historical economics and model-performance limits visible as claim boundaries; do not use these lanes for performance, cost, latency, reliability, or savings comparisons.",
            })
        elif action_state == "action_required":
            recommendations.append({
                "id": "usage_source_reverification_required",
                "severity": "warning",
                "decision": "block_model_economics_claims_for_uncredited_lanes",
                "rationale": "The attribution bridge reports live action-required supported-runtime gaps that lack an independently reverified source-to-lane usage join.",
                "next_action": "Repair the protected dispatch/source correlation path; do not use these lanes for performance, cost, latency, reliability, or savings comparisons.",
            })
        else:
            recommendations.append({
                "id": "usage_source_reverification_required",
                "severity": "warning",
                "decision": "block_model_economics_claims_for_uncredited_lanes",
                "rationale": "Uncredited lanes are audit-visible but the attribution bridge action-required signals are missing, stale, or malformed, so zero live debt cannot be assumed.",
                "next_action": "Restore a fresh, schema-valid attribution bridge packet, then repair the protected dispatch/source correlation path; do not use these lanes for performance, cost, latency, reliability, or savings comparisons.",
            })
    if latency.get("validator_slow") or as_float(latency.get("validator_elapsed_seconds")) > as_float(latency.get("validator_target_seconds"), 999999):
        recommendations.append({
            "id": "validator_latency_optimization",
            "severity": "info",
            "decision": "optimize_slowest_validators_or_changed_only_modes",
            "rationale": "Validator timing is above target or marked slow.",
            "next_action": "Use slowest tool rows and validator timing ledger to propose changed-only/background routes.",
        })
    if health.get("drift_status") != "ok" or as_float(health.get("daily_warning_or_error_count")) > 0:
        recommendations.append({
            "id": "otel_drift_review",
            "severity": "warning",
            "decision": "review_operational_drift_before_expansion",
            "rationale": "OTEL drift or warning/error counts are not clean.",
            "next_action": "Keep collector settings unchanged and inspect recent workflow volume.",
        })
    if as_dict(queue.get("summary")).get("high_priority_count"):
        recommendations.append({
            "id": "wf74_queue_followup",
            "severity": "info",
            "decision": "route_existing_wf74_opportunities",
            "rationale": "WF74 opportunity queue has high-priority items that can use metadata evidence.",
            "next_action": "Use learning-loop packet as support evidence for repair proposals, not auto-apply authority.",
        })
    cron = as_dict(friction.get("cron"))
    if as_float(cron.get("blocked_count")) or as_float(cron.get("requires_attention_count")):
        recommendations.append({
            "id": "cron_signal_learning_input",
            "severity": "warning",
            "decision": "route_cron_blockers_into_migration_plan",
            "rationale": "Cron blocked/attention signals are now first-class learning-loop inputs instead of standalone freshness noise.",
            "next_action": "Produce a dry-run migration plan with contract validation, rollback, and post-change freshness proof before mutating live schedules.",
        })
    workflow = as_dict(friction.get("workflow_advancement"))
    if as_float(workflow.get("blocked_count")) or workflow.get("cron_update_recommended"):
        recommendations.append({
            "id": "workflow_advancement_learning_input",
            "severity": "warning",
            "decision": "route_workflow_blockers_into_followup_queue",
            "rationale": "Workflow advancement blockers should create implementation or owner-decision follow-ups, not disappear after a status packet.",
            "next_action": "Rank blocked workflows in the WF74 opportunity queue and open narrow lanes only when write surfaces are clear.",
        })
    _tel_ok = bool(health.get("telemetry_fresh_valid"))
    if not _tel_ok:
        recommendations.append({"id": "otel_telemetry_stale_or_missing", "severity": "warning", "decision": "treat_telemetry_counts_fail_closed", "rationale": "Telemetry summary is not fresh/valid at consume time; use collector err-log health only.", "next_action": "Refresh runtime probe summary; do not infer model, finance, or execution readiness."})
    if health.get("telemetry_owner_gated_depth"):
        recommendations.append({"id": "otel_token_depth_owner_gated", "severity": "info", "decision": "keep_token_depth_owner_gated_no_approval", "rationale": "Token-depth packet is owner_decision_pending with validation warning; evidence only, not approval.", "next_action": "Await explicit owner decision; no capture, billing, allocation, or promotion claim."})
    recommendations.append({
        "id": "content_capture_boundary",
        "severity": "policy",
        "decision": "keep_raw_content_capture_blocked",
        "rationale": "Learning-loop value is mostly available from metadata; raw content capture creates unnecessary privacy and authority risk.",
        "next_action": "Use targeted, owner-approved, redacted review packets if content review is ever needed.",
    })
    return recommendations


def build_carry_forward_contract(
    cost: dict[str, Any],
    health: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    warning_recommendations = [
        row for row in recommendations
        if as_dict(row).get("severity") in {"warning", "policy"}
    ]
    return {
        "status": "attention" if warning_recommendations else "ok",
        "purpose": "Make OTEL learning-loop state explicit in future-session, startup, status, and evening alert surfaces.",
        "stale_after_hours": 24,
        "required_source_packets": [
            rel(OTEL_CONTROL),
            rel(OTEL_WINDOWS),
            rel(OTEL_TOOL_WORKFLOW),
            rel(MODEL_RUN_LEDGER),
            rel(WF74_OPPORTUNITY_QUEUE),
        ],
        "session_boot_order": [
            "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            "python scripts\\otel_learning_loop.py --write --write-md --validate",
            "python scripts\\wf74_improvement_opportunity_queue.py --write --validate",
            "python scripts\\wf74_decision_docket.py --write --write-md --validate",
            "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
        ],
        "must_surface_in": [
            "tmp/future-session-enhancement-packet.json",
            "tmp/startup-brief-packet.json",
            "tmp/veritas-status-card.json",
            "tmp/wf74-learning-loop-telegram-digest.json",
        ],
        "carry_forward_fields": {
            "collector_health": health.get("collector_health"),
            "drift_status": health.get("drift_status"),
            "token_coverage_ratio": cost.get("token_coverage_ratio"),
            "cost_coverage_ratio": cost.get("cost_coverage_ratio"),
            "recommendation_count": len(recommendations),
            "warning_recommendation_count": len(warning_recommendations),
        },
        "next_safe_action": (
            "Surface this packet in startup/status/evening digest; route implementation through WF74/PM only."
        ),
    }


def build_auto_implementation_router(recommendations: list[dict[str, Any]], queue: dict[str, Any]) -> dict[str, Any]:
    queue_summary = as_dict(queue.get("summary"))
    blocked_actions = [
        "direct code mutation from OTEL signals alone",
        "Skill Workshop apply/install/approval",
        "collector/runtime/cron config mutation",
        "finance canon, portfolio, cash, sizing, risk, paper, live, account, or external action",
        "owner approval inference",
    ]
    return {
        "status": "gated_auto_route_no_auto_apply" if recommendations else "monitor_only_no_auto_apply",
        "auto_apply_allowed": False,
        "safe_chain": [
            "OTEL metadata",
            "WF74 opportunity queue",
            "WF74 decision docket",
            "WF74 auto-patch proposer",
            "PM implementation job/router",
            "lane register lease",
            "main-session verification",
            "closeout/front-door refresh",
        ],
        "automatic_actions_allowed_now": [
            "refresh proof artifacts",
            "rank and dedupe opportunities",
            "generate patch/skill/owner-decision plans",
            "route proof-safe PM work with explicit lane contracts",
            "send review-only evening alert context",
        ],
        "automatic_actions_blocked": blocked_actions,
        "blocked_actions": blocked_actions,
        "pm_queue_signal": {
            "opportunity_count": queue_summary.get("opportunity_count"),
            "high_priority_count": queue_summary.get("high_priority_count"),
            "top_opportunity_title": queue_summary.get("top_opportunity_title"),
        },
        "next_safe_action": (
            "Use WF74 auto-patch and decision docket as the implementation router; auto-apply remains zero."
        ),
    }


def build_parallel_execution_plan() -> list[dict[str, Any]]:
    return [
        {
            "stream": "A",
            "title": "Telemetry depth and redaction",
            "owner": "OTEL/WF74",
            "state": "metadata_ready_owner_gated_depth_for_runtime_capture",
            "target": "token/cost/latency coverage without raw content capture",
            "proof": "python scripts\\otel_learning_loop.py --write --write-md --validate",
        },
        {
            "stream": "B",
            "title": "Carry-forward and session pickup",
            "owner": "startup/status/future-session packets",
            "state": "implemented_by_packet_surface",
            "target": "OTEL state visible to new sessions and shallow status",
            "proof": "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
        },
        {
            "stream": "C",
            "title": "WF74 improvement routing",
            "owner": "WF74 docket and auto-patch proposer",
            "state": "gated_auto_route_no_auto_apply",
            "target": "improvement opportunities become explicit action states",
            "proof": "python scripts\\wf74_decision_docket.py --write --write-md --validate",
        },
        {
            "stream": "D",
            "title": "Cron and stage-SLA learning input",
            "owner": "cron control and WF74 migration routing",
            "state": "review_only_contract_proof",
            "target": "cron SLA friction becomes ranked follow-up, not chat residue",
            "proof": "python scripts\\cron_control_packet.py --write --validate",
        },
        {
            "stream": "E",
            "title": "Evening alert and learning review",
            "owner": "WF74 Telegram digest",
            "state": "review_notification_integrated",
            "target": "Randall gets OTEL carry-forward and improvement status in evening alert",
            "proof": "python scripts\\wf74_learning_loop_telegram_digest.py --write --validate --force",
        },
    ]


def build_payload() -> dict[str, Any]:
    otel = as_dict(load_json_artifact(OTEL_CONTROL))
    windows = as_dict(load_json_artifact(OTEL_WINDOWS))
    tool_workflow = as_dict(load_json_artifact(OTEL_TOOL_WORKFLOW))
    model_run = as_dict(load_json_artifact(MODEL_RUN_LEDGER))
    learning = as_dict(load_json_artifact(MODEL_LEARNING_LEDGER))
    validator_timing = as_dict(load_json_artifact(VALIDATOR_TIMING))
    coding_runtime = as_dict(load_json_artifact(CODING_RUNTIME))
    changed_router = as_dict(load_json_artifact(CHANGED_FILE_ROUTER))
    queue = as_dict(load_json_artifact(WF74_OPPORTUNITY_QUEUE))
    cron_signal = as_dict(load_json_artifact(CRON_SIGNAL_SCORECARD))
    workflow_advancement = as_dict(load_json_artifact(WORKFLOW_ADVANCEMENT))
    bridge = as_dict(load_json_artifact(ATTRIBUTION_BRIDGE))

    cost = model_cost_summary(model_run)
    latency = tool_latency_summary(tool_workflow, validator_timing, coding_runtime)
    health = otel_health_summary(otel, windows, as_dict(otel.get("telemetry_context")))
    friction = operational_friction_summary(cron_signal, workflow_advancement)
    recommendations = build_recommendations(cost, latency, health, queue, friction, model_run, bridge)
    suppressions = owner_decision_suppressions()
    if suppressions:
        recommendations = [
            rec
            for rec in recommendations
            if not (isinstance(rec, dict) and rec.get("id") in suppressions)
        ]
    carry_forward = build_carry_forward_contract(cost, health, recommendations)
    auto_router = build_auto_implementation_router(recommendations, queue)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Metadata-only learning loop for OTEL, tool/coding runtime, cost coverage, latency, failure categories, and bounded improvement routing.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_status": [
            source_status(OTEL_CONTROL),
            source_status(OTEL_WINDOWS),
            source_status(OTEL_TOOL_WORKFLOW),
            source_status(MODEL_RUN_LEDGER),
            source_status(MODEL_LEARNING_LEDGER),
            source_status(VALIDATOR_TIMING),
            source_status(CODING_RUNTIME),
            source_status(CHANGED_FILE_ROUTER),
            source_status(WF74_OPPORTUNITY_QUEUE),
            source_status(CRON_SIGNAL_SCORECARD),
            source_status(WORKFLOW_ADVANCEMENT),
            source_status(ATTRIBUTION_BRIDGE),
        ],
        "redaction_policy": {
            "allowed": [
                "model/provider identifiers",
                "token counts when available",
                "cost numbers when available",
                "duration/latency numbers",
                "tool names",
                "workflow/session/lane IDs",
                "status/failure categories",
                "validator pass/fail metadata",
                "artifact proof paths",
            ],
            "blocked": [
                "raw prompts",
                "raw responses",
                "raw tool inputs",
                "raw tool outputs",
                "system prompts",
                "headers",
                "secrets",
                "credentials",
                "customer/account/brokerage data",
            ],
        },
        "owner_decision_suppressions": list(suppressions.values()),
        "learning_summaries": {
            "otel_health": health,
            "token_cost": cost,
            "tool_latency": latency,
            "attribution_action_state": attribution_action_state(model_run, bridge),
            "learning_ledger": {
                "status": learning.get("status"),
                "summary": as_dict(learning.get("summary")),
            },
            "changed_file_router": {
                "status": changed_router.get("status"),
                "summary": as_dict(changed_router.get("summary")),
            },
            "operational_friction": friction,
        },
        "recommendations": recommendations,
        "carry_forward_contract": carry_forward,
        "auto_implementation_router": auto_router,
        "parallel_execution_plan": build_parallel_execution_plan(),
        "review_loop": {
            "daily_evening_alert": "python scripts\\wf74_learning_loop_telegram_cron_runner.py --write --validate --send",
            "new_session_pickup": "python scripts\\future_session_enhancement_packet.py --write --write-md --validate",
            "status_pickup": "python scripts\\status_card_packet.py --write --validate",
            "weekly_review": "Review recommendation changes, auto-apply count, and carry-forward warnings before widening automation.",
        },
        "next_safe_action": "Keep metadata collection in the WF74 runner; prepare a separate owner-gated config patch only for token/cost/latency metadata depth.",
        "blocked_actions": [
            "no raw content capture",
            "no system prompt capture",
            "no raw tool payload capture",
            "no secrets or headers capture",
            "no external export",
            "no collector/runtime config mutation from this script",
            "no model ranking claim from telemetry alone",
            "no finance/capital/execution authority",
        ],
    }
    findings = scan_forbidden(payload)
    payload["privacy_scan"] = {
        "status": "ok" if not findings else "blocked",
        "finding_count": len(findings),
        "findings": findings[:50],
    }
    payload["validation"] = {
        "status": "ok" if payload["privacy_scan"]["status"] == "ok" else "blocked",
        "errors": [] if not findings else ["privacy_scan_blocked"],
        "warnings": [],
    }
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summaries = as_dict(payload.get("learning_summaries"))
    health = as_dict(summaries.get("otel_health"))
    cost = as_dict(summaries.get("token_cost"))
    latency = as_dict(summaries.get("tool_latency"))
    lines = [
        "# OTEL Learning Loop",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Collector health: `{health.get('collector_health')}`",
        f"- Drift status: `{health.get('drift_status')}`",
        f"- Token coverage: `{cost.get('token_coverage_ratio')}`",
        f"- Cost coverage: `{cost.get('cost_coverage_ratio')}`",
        f"- Tool failure rows: `{latency.get('failure_rows')}`",
        f"- Privacy scan: `{as_dict(payload.get('privacy_scan')).get('status')}`",
        "",
        "## Recommendations",
    ]
    for item in as_list(payload.get("recommendations")):
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('id')}`: {item.get('decision')} - {item.get('rationale')}")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Metadata-only. No raw prompts, responses, tool payloads, system prompts, secrets, headers, external export, or finance/execution authority.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.write:
        atomic_write_json(args.json_out, payload)
        print(f"wrote {rel(args.json_out)} status={payload.get('status')}")
    if args.write_md:
        atomic_write_text(args.md_out, render_md(payload))
        print(f"wrote {rel(args.md_out)}")
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        print(json.dumps(payload.get("validation"), indent=2))
        return 1
    if not args.write:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
