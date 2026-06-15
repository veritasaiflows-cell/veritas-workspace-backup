#!/usr/bin/env python3
"""Classify WF74 OTEL drift persistence from existing local proof artifacts.

Review-only/local-only: this script reads existing OTEL multi-window summaries
and WF74 queue evidence. It does not mutate collector config, runtime config,
cron schedules, telemetry depth, logs pipelines, finance state, or execution
surfaces.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
WINDOW_SUMMARY = TMP / "otel-ops-window-summary.json"
OPS_CONTROL = TMP / "otel-ops-control.json"
QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
JSON_OUT = TMP / "otel-drift-critical-review-loop.json"
MD_OUT = TMP / "otel-drift-critical-review-loop.md"

SCHEMA = "veritas.otel_drift_critical_review_loop.v1"

ALLOWED_STATES = {
    "normal_variance",
    "watch",
    "persistent_drift",
    "critical_drift",
    "resolved",
    "blocked_missing_evidence",
}

THRESHOLDS = {
    "normal_ratio_low": 0.5,
    "normal_ratio_high": 2.0,
    "persistent_ratio_low": 0.25,
    "persistent_ratio_high": 2.5,
    "critical_ratio_low": 0.1,
    "critical_ratio_high": 4.0,
    "critical_daily_error_count": 1,
    "watch_daily_warning_count": 1,
    "critical_daily_warning_count": 5,
    "persistent_bucket_min_count": 2,
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "external_export_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "telemetry_capture_depth_mutation_allowed": False,
    "logs_pipeline_or_file_exporter_enablement_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "secrets_or_headers_collection_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

BLOCKED_ACTIONS = [
    "no collector config mutation",
    "no runtime config mutation",
    "no cron schedule mutation",
    "no telemetry capture-depth expansion",
    "no logs pipeline or file exporter enablement",
    "no raw prompt/response/tool payload capture",
    "no external telemetry export",
    "no finance canon/portfolio/capital/paper/live/account authority",
    "no owner approval inference",
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


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def window_by_id(window_summary: dict[str, Any], window_id: str) -> dict[str, Any]:
    for row in as_list(window_summary.get("windows")):
        row_dict = as_dict(row)
        if row_dict.get("window_id") == window_id:
            return row_dict
    return {}


def severity_counts(window: dict[str, Any]) -> dict[str, int]:
    summary = as_dict(window.get("summary"))
    by_severity = as_dict(summary.get("by_severity"))
    return {
        "warnings": as_int(by_severity.get("warning")),
        "errors": as_int(by_severity.get("error")),
        "warning_or_error_count": as_int(by_severity.get("warning")) + as_int(by_severity.get("error")),
    }


def rate_from_window(window: dict[str, Any], field: str = "events") -> float | None:
    rates = as_dict(window.get("rates_per_hour"))
    rate = as_float(rates.get(field))
    if rate is not None:
        return rate
    summary = as_dict(window.get("summary"))
    hours = as_float(summary.get("window_hours") or window.get("window_hours"))
    count = as_float(summary.get("event_count"))
    if hours and hours > 0 and count is not None:
        return round(count / hours, 4)
    return None


def ratio_value(daily_rate: float | None, weekly_rate: float | None) -> float | None:
    if daily_rate is None or weekly_rate is None or weekly_rate <= 0:
        return None
    return round(daily_rate / weekly_rate, 4)


def is_ratio_outside(value: float | None, low: float, high: float) -> bool:
    return value is not None and (value <= low or value >= high)


def direction(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= THRESHOLDS["persistent_ratio_high"]:
        return "high"
    if value <= THRESHOLDS["persistent_ratio_low"]:
        return "low"
    if value > THRESHOLDS["normal_ratio_high"]:
        return "elevated"
    if value < THRESHOLDS["normal_ratio_low"]:
        return "suppressed"
    return "normal"


def drift_opportunity(queue: dict[str, Any]) -> dict[str, Any]:
    for row in as_list(queue.get("opportunities")):
        row_dict = as_dict(row)
        title = str(row_dict.get("title") or "").lower()
        signal = str(row_dict.get("signal") or "")
        if signal == "otel_operational_drift_review" or "otel event-rate drift" in title:
            return row_dict
    return {}


def persistence_buckets(window_summary: dict[str, Any], weekly_rate: float | None) -> list[dict[str, Any]]:
    if weekly_rate is None or weekly_rate <= 0:
        return []
    buckets = []
    for row in as_list(window_summary.get("weekly_daily_buckets_utc")):
        row_dict = as_dict(row)
        event_count = as_float(row_dict.get("event_count"))
        if event_count is None:
            continue
        bucket_rate = round(event_count / 24.0, 4)
        bucket_ratio = ratio_value(bucket_rate, weekly_rate)
        if is_ratio_outside(bucket_ratio, THRESHOLDS["persistent_ratio_low"], THRESHOLDS["persistent_ratio_high"]):
            buckets.append({
                "date_utc": row_dict.get("date_utc"),
                "event_count": row_dict.get("event_count"),
                "events_per_hour": bucket_rate,
                "ratio_vs_weekly": bucket_ratio,
                "warning_count": as_int(row_dict.get("warning_count")),
                "error_count": as_int(row_dict.get("error_count")),
                "direction": direction(bucket_ratio),
            })
    return buckets


def classify_state(
    *,
    ratio: float | None,
    daily_warning_count: int,
    daily_error_count: int,
    persistent_bucket_count: int,
    queue_has_drift: bool,
    missing_evidence: list[str],
) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    if missing_evidence:
        return "blocked_missing_evidence", "blocked", [f"missing_or_invalid:{','.join(missing_evidence)}"]

    if daily_error_count >= THRESHOLDS["critical_daily_error_count"]:
        reasons.append("daily_error_count_ge_1")
    if daily_warning_count >= THRESHOLDS["critical_daily_warning_count"]:
        reasons.append("daily_warning_count_ge_5")
    if is_ratio_outside(ratio, THRESHOLDS["critical_ratio_low"], THRESHOLDS["critical_ratio_high"]):
        reasons.append("event_rate_ratio_outside_critical_threshold")
    if reasons:
        return "critical_drift", "critical", reasons

    persistent_ratio = is_ratio_outside(ratio, THRESHOLDS["persistent_ratio_low"], THRESHOLDS["persistent_ratio_high"])
    if persistent_ratio:
        reasons.append("event_rate_ratio_outside_persistent_threshold")
    if persistent_bucket_count >= THRESHOLDS["persistent_bucket_min_count"]:
        reasons.append("repeated_daily_buckets_outside_persistent_threshold")
    if queue_has_drift:
        reasons.append("wf74_queue_contains_otel_drift_opportunity")
    if persistent_ratio and (
        persistent_bucket_count >= THRESHOLDS["persistent_bucket_min_count"] or queue_has_drift
    ):
        return "persistent_drift", "warning", reasons

    if (
        daily_warning_count >= THRESHOLDS["watch_daily_warning_count"]
        or is_ratio_outside(ratio, THRESHOLDS["normal_ratio_low"], THRESHOLDS["normal_ratio_high"])
    ):
        if daily_warning_count:
            reasons.append("daily_warning_count_gt_0")
        if ratio is not None:
            reasons.append("event_rate_ratio_outside_normal_variance_band")
        return "watch", "warning", reasons

    if queue_has_drift:
        return "resolved", "info", ["prior_queue_drift_signal_no_longer_present"]

    return "normal_variance", "info", ["within_normal_variance_band"]


def recommended_action(state: str) -> str:
    return {
        "normal_variance": "Keep the normal OTEL daily review cadence; no collector or runtime action is warranted.",
        "watch": "Refresh the OTEL multi-window packet after the next collection window and compare recent workflow/cron volume before proposing changes.",
        "persistent_drift": (
            "Keep collector settings unchanged; inspect recent workflow volume and re-check the next window. "
            "Escalate only to an owner-gated field-depth decision packet if persistence continues."
        ),
        "critical_drift": (
            "Perform immediate local operator review of collector warning/error lines and recent runtime changes. "
            "Do not mutate config, capture depth, or schedules without separate explicit approval."
        ),
        "resolved": "Let the next WF74 digest mark the drift opportunity resolved; no collector action is warranted.",
        "blocked_missing_evidence": (
            "Refresh evidence with `python scripts\\otel_ops_control.py --write --write-db --multi-window --validate` "
            "and regenerate the WF74 improvement queue before classifying drift."
        ),
    }[state]


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if payload.get("state") not in ALLOWED_STATES:
        errors.append("unsupported_state")
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    for key in THRESHOLDS:
        if key not in as_dict(payload.get("thresholds")):
            errors.append(f"missing_threshold:{key}")
    if not as_list(payload.get("blocked_actions")):
        errors.append("missing_blocked_actions")
    if payload.get("state") == "blocked_missing_evidence":
        errors.append("missing_required_evidence")
    if payload.get("state") == "critical_drift":
        warnings.append("critical_drift_is_review_only_no_config_authority")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_payload(
    window_summary: dict[str, Any],
    ops_control: dict[str, Any],
    queue: dict[str, Any],
    *,
    source_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    source_paths = source_paths or {
        "window_summary": WINDOW_SUMMARY,
        "ops_control": OPS_CONTROL,
        "opportunity_queue": QUEUE,
    }
    missing: list[str] = []
    if window_summary.get("schema") != "veritas.otel_ops_window_summary.v1":
        missing.append("window_summary_schema")
    if as_dict(window_summary.get("validation")).get("status") != "ok":
        missing.append("window_summary_validation")
    daily = window_by_id(window_summary, "daily_24h")
    weekly = window_by_id(window_summary, "weekly_7d")
    if not daily:
        missing.append("daily_24h_window")
    if not weekly:
        missing.append("weekly_7d_window")

    daily_rate = rate_from_window(daily)
    weekly_rate = rate_from_window(weekly)
    ratio = ratio_value(daily_rate, weekly_rate)
    if daily_rate is None:
        missing.append("daily_events_per_hour")
    if weekly_rate is None:
        missing.append("weekly_events_per_hour")
    if ratio is None:
        missing.append("daily_vs_weekly_ratio")

    counts = severity_counts(daily)
    opportunity = drift_opportunity(queue)
    buckets = persistence_buckets(window_summary, weekly_rate)
    state, severity, reasons = classify_state(
        ratio=ratio,
        daily_warning_count=counts["warnings"],
        daily_error_count=counts["errors"],
        persistent_bucket_count=len(buckets),
        queue_has_drift=bool(opportunity),
        missing_evidence=missing,
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "state": state,
        "severity": severity,
        "purpose": "Classify OTEL event-rate drift persistence against the weekly baseline using existing WF74/OTEL proof artifacts.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_artifacts": {name: rel(path) for name, path in source_paths.items()},
        "thresholds": dict(THRESHOLDS),
        "classification": {
            "state": state,
            "severity": severity,
            "reasons": reasons,
            "direction": direction(ratio),
            "recommended_next_safe_action": recommended_action(state),
        },
        "drift_evidence": {
            "daily_events_per_hour": daily_rate,
            "weekly_events_per_hour": weekly_rate,
            "daily_vs_weekly_event_rate_ratio": ratio,
            "daily_warning_count": counts["warnings"],
            "daily_error_count": counts["errors"],
            "daily_warning_or_error_count": counts["warning_or_error_count"],
            "persistent_bucket_count": len(buckets),
            "persistent_buckets": buckets,
            "queue_opportunity_present": bool(opportunity),
            "queue_opportunity_id": opportunity.get("opportunity_id"),
            "queue_priority": opportunity.get("priority"),
            "queue_recommended_action": opportunity.get("recommended_action"),
            "ops_control_drift": as_dict(ops_control.get("drift")),
            "missing_evidence": missing,
        },
        "recommended_next_safe_action": recommended_action(state),
        "blocked_actions": list(BLOCKED_ACTIONS),
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    evidence = as_dict(payload.get("drift_evidence"))
    classification = as_dict(payload.get("classification"))
    lines = [
        "# OTEL Drift Critical Review Loop",
        "",
        f"Generated: {payload.get('generated_at_utc')}",
        f"State: {payload.get('state')}",
        f"Severity: {payload.get('severity')}",
        "",
        "## Evidence",
        "",
        f"- Daily events/hour: {evidence.get('daily_events_per_hour')}",
        f"- Weekly events/hour: {evidence.get('weekly_events_per_hour')}",
        f"- Daily vs weekly ratio: {evidence.get('daily_vs_weekly_event_rate_ratio')}",
        f"- Daily warnings/errors: {evidence.get('daily_warning_or_error_count')}",
        f"- Persistent daily buckets: {evidence.get('persistent_bucket_count')}",
        f"- WF74 queue drift opportunity: {evidence.get('queue_opportunity_present')}",
        "",
        "## Classification",
        "",
        f"- Direction: {classification.get('direction')}",
        f"- Reasons: {', '.join(str(item) for item in as_list(classification.get('reasons'))) or 'none'}",
        f"- Next safe action: {payload.get('recommended_next_safe_action')}",
        "",
        "## Thresholds",
        "",
        f"- Normal ratio band: {THRESHOLDS['normal_ratio_low']}x to {THRESHOLDS['normal_ratio_high']}x",
        f"- Persistent drift band: outside {THRESHOLDS['persistent_ratio_low']}x to {THRESHOLDS['persistent_ratio_high']}x",
        f"- Critical drift band: outside {THRESHOLDS['critical_ratio_low']}x to {THRESHOLDS['critical_ratio_high']}x",
        f"- Critical warning/error handling: errors >= {THRESHOLDS['critical_daily_error_count']} or warnings >= {THRESHOLDS['critical_daily_warning_count']}",
        "",
        "## Blocked Actions",
        "",
    ]
    for action in as_list(payload.get("blocked_actions")):
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify WF74 OTEL drift persistence.")
    parser.add_argument("--window-summary", type=Path, default=WINDOW_SUMMARY)
    parser.add_argument("--ops-control", type=Path, default=OPS_CONTROL)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--json-out", type=Path, default=JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        load_dict(args.window_summary),
        load_dict(args.ops_control),
        load_dict(args.queue),
        source_paths={
            "window_summary": args.window_summary,
            "ops_control": args.ops_control,
            "opportunity_queue": args.queue,
        },
    )
    if args.write:
        atomic_write_json(args.json_out, payload)
    if args.write_md:
        atomic_write_text(args.md_out, render_markdown(payload))
    if not args.quiet:
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "state": payload["state"],
                    "severity": payload["severity"],
                    "ratio": payload["drift_evidence"]["daily_vs_weekly_event_rate_ratio"],
                    "persistent_bucket_count": payload["drift_evidence"]["persistent_bucket_count"],
                    "validation": payload["validation"],
                },
                indent=2,
            )
        )
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
