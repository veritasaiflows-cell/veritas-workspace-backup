#!/usr/bin/env python3
"""Build a local, queryable OTEL operations control packet.

This is the first-hop OTEL route for WF74/operations learning. It parses the
local collector's current logs into JSONL and SQLite, then emits a compact
digest and action router. It is local-only and review-only; it does not change
collector config, cron schedules, runtime settings, or telemetry capture depth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OTEL_DIR = TMP / "otel-collector"
DEFAULT_LOG = OTEL_DIR / "collector.err.log"
DEFAULT_RECEIPTS = OTEL_DIR / "receipts.jsonl"
DEFAULT_COLLECTOR_CONFIG = ROOT / "tools" / "otelcol" / "openclaw-local-otel.yaml"
DEFAULT_EVENTS = TMP / "otel-ops-events.jsonl"
DEFAULT_DB = TMP / "otel-ops.sqlite"
DEFAULT_OUT = TMP / "otel-ops-control.json"
DEFAULT_WINDOW_SUMMARY = TMP / "otel-ops-window-summary.json"
DEFAULT_LEGACY_CONTROL_LOOP = TMP / "otel" / "control-loop.json"
DEFAULT_FIELD_DEPTH_PACKET = TMP / "otel-field-depth-limited-owner-packet.json"
DEFAULT_TOOL_WORKFLOW_METADATA = TMP / "otel-tool-workflow-metadata.json"

SCHEMA = "veritas.otel_ops_control.v1"
WINDOW_SUMMARY_SCHEMA = "veritas.otel_ops_window_summary.v1"

WINDOW_SPECS = [
    {
        "window_id": "intraday_1h",
        "label": "1 hour intraday",
        "window_hours": 1.0,
        "role": "post-change or suspected-incident check",
        "recommended_use": "Use after an implementation, repair, or suspected break to confirm telemetry is still flowing.",
        "productization": "ad_hoc_not_scheduled",
    },
    {
        "window_id": "intraday_6h",
        "label": "6 hour intraday",
        "window_hours": 6.0,
        "role": "same-session operating window",
        "recommended_use": "Use to review recent cron/workflow activity without waiting for the daily packet.",
        "productization": "ad_hoc_not_scheduled",
    },
    {
        "window_id": "daily_24h",
        "label": "24 hour daily control",
        "window_hours": 24.0,
        "role": "default daily operational health",
        "recommended_use": "Use as the normal cron/collector/trace-volume health packet.",
        "productization": "default_control_packet",
    },
    {
        "window_id": "weekly_7d",
        "label": "7 day trend",
        "window_hours": 168.0,
        "role": "recurring failure and friction trend review",
        "recommended_use": "Use to see whether warning/error noise, telemetry volume, or fix impact is changing across the week.",
        "productization": "trend_review",
    },
    {
        "window_id": "monthly_30d",
        "label": "30 day baseline",
        "window_hours": 720.0,
        "role": "monthly capacity and noise baseline",
        "recommended_use": "Use for baseline drift only; it is too broad for day-to-day debugging.",
        "productization": "baseline_review",
    },
]

CONTROL_LOOP_COMPAT_SCHEMA = "veritas.otel_control_loop_compat.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "external_export_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "logs_or_content_capture_enabled_by_this_script": False,
    "prompt_response_tool_content_capture_allowed": False,
    "secrets_or_headers_collection_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

METRIC_RE = re.compile(r'"metrics":\s*(?P<metrics>\d+),\s*"data points":\s*(?P<data_points>\d+)')
TRACE_RE = re.compile(r'"spans":\s*(?P<spans>\d+)')
JSON_RE = re.compile(r"(\{.*\})")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_collector_timestamp(value: str) -> str | None:
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def safe_json_from_line(line: str) -> dict[str, Any]:
    match = JSON_RE.search(line)
    if not match:
        return {}
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def row_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8", errors="ignore")).hexdigest()


def collector_health(host: str = "127.0.0.1", port: int = 4318, timeout: float = 0.25) -> dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"status": "ok", "host": host, "port": port, "listening": True}
    except OSError as exc:
        return {"status": "blocked", "host": host, "port": port, "listening": False, "error": str(exc)}


def parse_collector_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events, {"present": False, "path": rel(path)}
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line_no, line in enumerate(lines, start=1):
        if "\tMetrics\t" in line:
            match = METRIC_RE.search(line)
            if not match:
                continue
            timestamp = parse_collector_timestamp(line.split("\t", 1)[0])
            events.append({
                "event_id": row_hash(line),
                "timestamp_utc": timestamp,
                "source": rel(path),
                "line_number": line_no,
                "event_type": "collector_metric_batch",
                "signal": "metrics",
                "metrics": int(match.group("metrics")),
                "data_points": int(match.group("data_points")),
                "spans": None,
                "severity": "info",
                "summary": f"metrics={match.group('metrics')} data_points={match.group('data_points')}",
            })
        elif "\tTraces\t" in line:
            match = TRACE_RE.search(line)
            if not match:
                continue
            timestamp = parse_collector_timestamp(line.split("\t", 1)[0])
            events.append({
                "event_id": row_hash(line),
                "timestamp_utc": timestamp,
                "source": rel(path),
                "line_number": line_no,
                "event_type": "collector_trace_batch",
                "signal": "traces",
                "metrics": None,
                "data_points": None,
                "spans": int(match.group("spans")),
                "severity": "info",
                "summary": f"spans={match.group('spans')}",
            })
        elif "\terror\t" in line.lower() or "\twarn\t" in line.lower() or "Exporting failed" in line:
            timestamp = parse_collector_timestamp(line.split("\t", 1)[0])
            severity = "error" if "\terror\t" in line.lower() or "Exporting failed" in line else "warning"
            events.append({
                "event_id": row_hash(line),
                "timestamp_utc": timestamp,
                "source": rel(path),
                "line_number": line_no,
                "event_type": "collector_log_issue",
                "signal": "collector",
                "metrics": None,
                "data_points": None,
                "spans": None,
                "severity": severity,
                "summary": line[-500:],
            })
    return events, {"present": True, "path": rel(path), "line_count": len(lines), "bytes": path.stat().st_size}


def parse_receipts(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events, {"present": False, "path": rel(path)}
    line_count = 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line_count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        signal = str(row.get("signal") or "unknown")
        events.append({
            "event_id": row.get("sha256") or row_hash(line),
            "timestamp_utc": row.get("received_at_utc"),
            "source": rel(path),
            "line_number": line_no,
            "event_type": "local_receipt",
            "signal": signal,
            "metrics": None,
            "data_points": None,
            "spans": None,
            "content_length": row.get("content_length"),
            "severity": "info",
            "summary": f"receipt signal={signal} bytes={row.get('content_length')}",
        })
    return events, {"present": True, "path": rel(path), "line_count": line_count, "bytes": path.stat().st_size}


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events)
    path.write_text(text, encoding="utf-8")


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS otel_events (
            event_id TEXT PRIMARY KEY,
            timestamp_utc TEXT,
            source TEXT,
            line_number INTEGER,
            event_type TEXT,
            signal TEXT,
            metrics INTEGER,
            data_points INTEGER,
            spans INTEGER,
            content_length INTEGER,
            severity TEXT,
            summary TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS otel_action_candidates (
            id TEXT PRIMARY KEY,
            severity TEXT,
            action_type TEXT,
            owner TEXT,
            rationale TEXT,
            recommended_command TEXT,
            status TEXT
        )
        """
    )
    con.execute(
        """
        CREATE VIEW IF NOT EXISTS latest_otel_summary AS
        SELECT
            COUNT(*) AS event_count,
            SUM(CASE WHEN signal='metrics' THEN 1 ELSE 0 END) AS metric_batches,
            SUM(COALESCE(data_points, 0)) AS data_points,
            SUM(CASE WHEN signal='traces' THEN 1 ELSE 0 END) AS trace_batches,
            SUM(COALESCE(spans, 0)) AS spans,
            SUM(CASE WHEN severity='error' THEN 1 ELSE 0 END) AS errors,
            SUM(CASE WHEN severity='warning' THEN 1 ELSE 0 END) AS warnings,
            MAX(timestamp_utc) AS latest_timestamp_utc
        FROM otel_events
        """
    )
    return con


def write_db(path: Path, events: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
    with init_db(path) as con:
        con.executemany(
            """
            INSERT OR REPLACE INTO otel_events (
                event_id, timestamp_utc, source, line_number, event_type, signal, metrics,
                data_points, spans, content_length, severity, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.get("event_id"),
                    event.get("timestamp_utc"),
                    event.get("source"),
                    event.get("line_number"),
                    event.get("event_type"),
                    event.get("signal"),
                    event.get("metrics"),
                    event.get("data_points"),
                    event.get("spans"),
                    event.get("content_length"),
                    event.get("severity"),
                    event.get("summary"),
                )
                for event in events
            ],
        )
        con.execute("DELETE FROM otel_action_candidates")
        con.executemany(
            """
            INSERT OR REPLACE INTO otel_action_candidates (
                id, severity, action_type, owner, rationale, recommended_command, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    action.get("id"),
                    action.get("severity"),
                    action.get("action_type"),
                    action.get("owner"),
                    action.get("rationale"),
                    action.get("recommended_command"),
                    action.get("status"),
                )
                for action in actions
            ],
        )
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        summary = con.execute("SELECT * FROM latest_otel_summary").fetchone()
        columns = [desc[0] for desc in con.execute("SELECT * FROM latest_otel_summary").description]
    return {"path": rel(path), "integrity": integrity, "latest_summary": dict(zip(columns, summary or []))}


def window_events(events: list[dict[str, Any]], hours: float) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    selected = []
    for event in events:
        dt = parse_iso_utc(event.get("timestamp_utc"))
        if dt and dt >= cutoff:
            selected.append(event)
    return selected


def summarize_events(events: list[dict[str, Any]], window_hours: float) -> dict[str, Any]:
    recent = window_events(events, window_hours)
    metric_events = [event for event in recent if event.get("signal") == "metrics"]
    trace_events = [event for event in recent if event.get("signal") == "traces"]
    latest_metric = metric_events[-1] if metric_events else {}
    latest_trace = trace_events[-1] if trace_events else {}
    by_type = Counter(str(event.get("event_type")) for event in recent)
    by_signal = Counter(str(event.get("signal")) for event in recent)
    by_severity = Counter(str(event.get("severity")) for event in recent)
    all_metric_values = sorted({event.get("metrics") for event in metric_events if event.get("metrics") is not None})
    data_point_values = sorted({event.get("data_points") for event in metric_events if event.get("data_points") is not None})
    return {
        "window_hours": window_hours,
        "event_count": len(recent),
        "by_event_type": dict(by_type),
        "by_signal": dict(by_signal),
        "by_severity": dict(by_severity),
        "metric_batches": len(metric_events),
        "trace_batches": len(trace_events),
        "reported_data_points": sum(int(event.get("data_points") or 0) for event in metric_events),
        "reported_spans": sum(int(event.get("spans") or 0) for event in trace_events),
        "metric_count_values": all_metric_values,
        "data_point_values": data_point_values,
        "latest_metric": {
            "timestamp_utc": latest_metric.get("timestamp_utc"),
            "metrics": latest_metric.get("metrics"),
            "data_points": latest_metric.get("data_points"),
        },
        "latest_trace": {
            "timestamp_utc": latest_trace.get("timestamp_utc"),
            "spans": latest_trace.get("spans"),
        },
    }


def event_time_span(events: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = [dt for event in events if (dt := parse_iso_utc(event.get("timestamp_utc")))]
    if not timestamps:
        return {
            "earliest_timestamp_utc": None,
            "latest_timestamp_utc": None,
            "observed_span_hours": 0.0,
        }
    earliest = min(timestamps)
    latest = max(timestamps)
    return {
        "earliest_timestamp_utc": earliest.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "latest_timestamp_utc": latest.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "observed_span_hours": round(max((latest - earliest).total_seconds() / 3600.0, 0.0), 3),
    }


def daily_buckets(events: list[dict[str, Any]], hours: float = 168.0) -> list[dict[str, Any]]:
    selected = window_events(events, hours)
    buckets: dict[str, dict[str, Any]] = {}
    for event in selected:
        dt = parse_iso_utc(event.get("timestamp_utc"))
        if not dt:
            continue
        key = dt.date().isoformat()
        bucket = buckets.setdefault(
            key,
            {
                "date_utc": key,
                "event_count": 0,
                "metric_batches": 0,
                "trace_batches": 0,
                "reported_data_points": 0,
                "reported_spans": 0,
                "warning_count": 0,
                "error_count": 0,
            },
        )
        bucket["event_count"] += 1
        if event.get("signal") == "metrics":
            bucket["metric_batches"] += 1
            bucket["reported_data_points"] += int(event.get("data_points") or 0)
        if event.get("signal") == "traces":
            bucket["trace_batches"] += 1
            bucket["reported_spans"] += int(event.get("spans") or 0)
        if event.get("severity") == "warning":
            bucket["warning_count"] += 1
        if event.get("severity") == "error":
            bucket["error_count"] += 1
    return [buckets[key] for key in sorted(buckets)]


def per_hour(value: Any, hours: float) -> float | None:
    try:
        hours = float(hours)
        numeric = float(value or 0)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    return round(numeric / hours, 4)


def window_status(summary: dict[str, Any], health: dict[str, Any]) -> str:
    if health.get("status") != "ok":
        return "blocked"
    if summary.get("event_count", 0) <= 0:
        return "warning"
    if summary.get("by_severity", {}).get("error", 0):
        return "warning"
    return "ok"


def warning_or_error_count(summary: dict[str, Any]) -> int:
    severity = summary.get("by_severity") if isinstance(summary.get("by_severity"), dict) else {}
    return int(severity.get("warning", 0) or 0) + int(severity.get("error", 0) or 0)


def drift_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    daily = summarize_events(events, 24.0)
    weekly = summarize_events(events, 168.0)
    daily_rate = per_hour(daily.get("event_count"), 24.0) or 0.0
    weekly_rate = per_hour(weekly.get("event_count"), 168.0) or 0.0
    ratio = round(daily_rate / weekly_rate, 4) if weekly_rate else None
    warning_count = warning_or_error_count(daily)
    drift_reasons: list[str] = []
    if warning_count > 0:
        drift_reasons.append("daily_warning_or_error_count_gt_0")
    if ratio is not None and (ratio >= 2.5 or ratio <= 0.25):
        drift_reasons.append("daily_event_rate_deviates_from_weekly_baseline")
    return {
        "status": "review" if drift_reasons else "ok",
        "daily_warning_or_error_count": warning_count,
        "daily_events_per_hour": daily_rate,
        "weekly_events_per_hour": weekly_rate,
        "daily_vs_weekly_event_rate_ratio": ratio,
        "drift_reasons": drift_reasons,
        "alert_rule": "review when daily_warning_or_error_count > 0 or daily/weekly event-rate ratio is outside 0.25x-2.5x",
        "meaning": "Operational drift only; not a model-quality, finance-correctness, or execution-readiness signal.",
    }


def build_window_summary(events: list[dict[str, Any]], health: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    for spec in WINDOW_SPECS:
        summary = summarize_events(events, float(spec["window_hours"]))
        windows.append({
            **spec,
            "status": window_status(summary, health),
            "summary": summary,
            "rates_per_hour": {
                "events": per_hour(summary.get("event_count"), float(spec["window_hours"])),
                "metric_batches": per_hour(summary.get("metric_batches"), float(spec["window_hours"])),
                "trace_batches": per_hour(summary.get("trace_batches"), float(spec["window_hours"])),
                "reported_data_points": per_hour(summary.get("reported_data_points"), float(spec["window_hours"])),
                "reported_spans": per_hour(summary.get("reported_spans"), float(spec["window_hours"])),
            },
            "meaning": (
                "Operational telemetry only: collector health, metric/trace volume, spans, and warning/error noise. "
                "This window does not measure coding skill, model quality, finance correctness, or approval readiness."
            ),
        })
    windows_by_id = {str(row["window_id"]): row for row in windows}
    daily = windows_by_id["daily_24h"]["summary"]
    weekly = windows_by_id["weekly_7d"]["summary"]
    monthly = windows_by_id["monthly_30d"]["summary"]
    drift = drift_summary(events)
    trend_indicators = {
        "daily_events_per_hour": per_hour(daily.get("event_count"), 24.0),
        "weekly_events_per_hour": per_hour(weekly.get("event_count"), 168.0),
        "monthly_events_per_hour": per_hour(monthly.get("event_count"), 720.0),
        "daily_trace_batches_per_hour": per_hour(daily.get("trace_batches"), 24.0),
        "weekly_trace_batches_per_hour": per_hour(weekly.get("trace_batches"), 168.0),
        "daily_warning_or_error_count": int(daily.get("by_severity", {}).get("warning", 0) or 0)
        + int(daily.get("by_severity", {}).get("error", 0) or 0),
        "weekly_warning_or_error_count": int(weekly.get("by_severity", {}).get("warning", 0) or 0)
        + int(weekly.get("by_severity", {}).get("error", 0) or 0),
        "data_span": event_time_span(events),
        "interpretation": (
            "Compare rates and warning/error counts as operational drift signals only. "
            "A longer OTEL window strengthens ops evidence; it does not create model ranking or coding-skill proof."
        ),
    }
    trend_indicators["drift_status"] = drift["status"]
    trend_indicators["drift_reasons"] = drift["drift_reasons"]
    payload = {
        "schema": WINDOW_SUMMARY_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if all(row["status"] in {"ok", "warning"} for row in windows) and health.get("status") == "ok" else "blocked",
        "purpose": "Multi-window local OTEL operations summary for intraday checks, daily health, weekly trend review, and monthly baseline review.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "collector_health": health,
        "collector_config": config,
        "windows": windows,
        "weekly_daily_buckets_utc": daily_buckets(events, 168.0),
        "trend_indicators": trend_indicators,
        "drift": drift,
        "next_safe_action": (
            "Keep 24h as the cron/PM control packet; use intraday windows manually after changes, "
            "use weekly trend for repeated friction, and use monthly baseline only for capacity/noise drift."
        ),
        "blocked_actions": [
            "no collector config mutation",
            "no runtime config mutation",
            "no telemetry capture-depth expansion",
            "no model ranking or coding-skill inference",
            "no finance canon/portfolio/capital/paper/live/account authority",
        ],
    }
    payload["validation"] = validate_window_summary(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def build_control_loop_compat(payload: dict[str, Any], window_payload: dict[str, Any] | None) -> dict[str, Any]:
    """Compatibility bridge for old audits that expected tmp/otel/control-loop.json.

    The canonical owner remains tmp/otel-ops-control.json. This artifact is a
    thin pointer plus health summary so old route checks do not report a missing
    main loop while the workspace uses the newer single-owner OTEL packet.
    """
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    window_validation = (
        window_payload.get("validation") if isinstance(window_payload, dict) and isinstance(window_payload.get("validation"), dict) else {}
    )
    compat = {
        "schema": CONTROL_LOOP_COMPAT_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if payload.get("status") == "ok" and (not window_payload or window_payload.get("status") == "ok") else "warning",
        "compatibility_role": "legacy_audit_bridge_not_owner",
        "canonical_owner": "tmp/otel-ops-control.json",
        "window_summary": "tmp/otel-ops-window-summary.json",
        "sqlite": "tmp/otel-ops.sqlite",
        "summary": {
            "canonical_status": payload.get("status"),
            "canonical_window_hours": summary.get("window_hours"),
            "event_count": summary.get("event_count"),
            "metric_batches": summary.get("metric_batches"),
            "trace_batches": summary.get("trace_batches"),
            "reported_spans": summary.get("reported_spans"),
            "window_summary_status": window_payload.get("status") if isinstance(window_payload, dict) else None,
            "window_count": len(window_payload.get("windows", [])) if isinstance(window_payload, dict) else 0,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "ok" if payload.get("status") == "ok" and (not window_validation or window_validation.get("status") == "ok") else "warning",
            "errors": [],
            "warnings": [
                "compatibility_bridge_only_not_canonical_owner",
                *([] if window_payload else ["window_summary_not_requested"]),
            ],
        },
        "next_safe_action": "Use tmp/otel-ops-control.json as the canonical OTEL owner; keep this bridge only for legacy audit compatibility.",
    }
    return compat


def validate_window_summary(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if payload.get("authority_boundary", {}).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    expected_windows = {str(spec["window_id"]) for spec in WINDOW_SPECS}
    observed_windows = {str(row.get("window_id")) for row in payload.get("windows", []) if isinstance(row, dict)}
    missing = sorted(expected_windows - observed_windows)
    if missing:
        errors.append(f"missing_windows:{','.join(missing)}")
    for row in payload.get("windows", []):
        if not isinstance(row, dict):
            continue
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        if summary.get("event_count", 0) <= 0:
            warnings.append(f"{row.get('window_id')}_has_no_events")
        for field in ("role", "recommended_use", "productization", "meaning"):
            if not row.get(field):
                errors.append(f"{row.get('window_id')}_missing_{field}")
    if payload.get("collector_health", {}).get("status") != "ok":
        errors.append("collector_not_listening")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def collector_config_posture(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"present": False, "path": rel(path)}
    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    return {
        "present": True,
        "path": rel(path),
        "has_debug_exporter": "debug:" in lower,
        "debug_verbosity_basic": "verbosity: basic" in lower,
        "has_file_exporter": "file:" in lower,
        "has_logs_pipeline": re.search(r"pipelines:\s*.*logs:", lower, re.S) is not None,
        "binds_loopback_4318": "127.0.0.1:4318" in lower,
    }


def build_actions(summary: dict[str, Any], config: dict[str, Any], health: dict[str, Any], drift: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if health.get("status") != "ok":
        actions.append({
            "id": "otel_collector_not_listening",
            "severity": "critical",
            "action_type": "runtime_review",
            "owner": "openclaw-operator",
            "rationale": "OTEL endpoint is not reachable, so telemetry is not currently collecting.",
            "recommended_command": "Test-NetConnection 127.0.0.1 -Port 4318",
            "status": "blocked",
        })
    if summary.get("metric_batches", 0) == 0 and summary.get("trace_batches", 0) == 0:
        actions.append({
            "id": "otel_no_recent_events",
            "severity": "warning",
            "action_type": "cron_or_runtime_review",
            "owner": "cron-automation-manager",
            "rationale": "No recent OTEL batches were observed in the selected window.",
            "recommended_command": "python scripts\\otel_ops_control.py --write --write-db --validate",
            "status": "review",
        })
    if config.get("debug_verbosity_basic") and not config.get("has_file_exporter"):
        actions.append({
            "id": "otel_field_depth_limited",
            "severity": "info",
            "action_type": "wf74_followup",
            "owner": "WF74 / model-quality-scorecard",
            "rationale": "Current collector logs prove metrics/traces are arriving but expose only batch counts, not model/tool/token/error fields.",
            "recommended_command": "Prepare a local-only detailed-field capture packet before changing collector config.",
            "status": "candidate",
        })
    if summary.get("by_severity", {}).get("error", 0) or summary.get("by_severity", {}).get("warning", 0):
        actions.append({
            "id": "otel_collector_warnings_or_errors",
            "severity": "warning",
            "action_type": "operator_review",
            "owner": "openclaw-operator",
            "rationale": "Collector warning/error lines appeared in the OTEL log.",
            "recommended_command": "Select-String -Path tmp\\otel-collector\\collector.err.log -Pattern 'warn|error|Exporting failed'",
            "status": "review",
        })
    if drift and drift.get("status") == "review":
        actions.append({
            "id": "otel_operational_drift_review",
            "severity": "warning",
            "action_type": "operator_review",
            "owner": "openclaw-operator / WF74",
            "rationale": (
                "OTEL operational drift rule tripped: "
                + ", ".join(str(item) for item in drift.get("drift_reasons", []))
            ),
            "recommended_command": "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            "status": "review",
        })
    actions.append({
        "id": "otel_daily_digest_ready",
        "severity": "info",
        "action_type": "cron_digest",
        "owner": "cron-automation-manager",
        "rationale": "OTEL ops control is cron-safe and can refresh one packet plus SQLite index without changing telemetry settings.",
        "recommended_command": "python scripts\\otel_ops_control.py --write --write-db --validate",
        "status": "ready",
    })
    return actions


def build_field_depth_packet(config: dict[str, Any], summary: dict[str, Any], drift: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema": "veritas.otel_field_depth_limited_owner_packet.v1",
        "generated_at_utc": utc_now(),
        "status": "owner_decision_required",
        "purpose": "Review packet for richer local-only OTEL field capture. This packet does not change collector config.",
        "current_collector_posture": config,
        "current_24h_summary": summary,
        "current_drift_summary": drift,
        "proposed_change_if_approved_later": {
            "collector_config": rel(DEFAULT_COLLECTOR_CONFIG),
            "candidate_capability": "file exporter and logs pipeline or equivalent bounded local receiver for model/tool/token/error fields",
            "required_scope": "local-only, metadata-only, no raw prompt/response/tool payload/system prompt/secrets/headers",
            "required_review": "owner approval plus config diff, rollback, privacy scan, and post-change OTEL validation",
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "collector_config_mutation_allowed": False,
            "owner_decision_packet_only": True,
        },
        "blocked_now": [
            "no collector config mutation",
            "no telemetry capture-depth expansion",
            "no file exporter/logs pipeline enablement",
            "no external export",
            "no raw prompt/response/tool payload/system-prompt/secret/header capture",
        ],
        "next_safe_action": "Use this as the owner-review packet if deeper OTEL field capture is worth approving later.",
    }
    payload["validation"] = {
        "status": "ok",
        "errors": [],
        "warnings": ["owner_approval_required_before_any_collector_config_change"],
    }
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if payload.get("authority_boundary", {}).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if payload.get("collector_health", {}).get("status") != "ok":
        errors.append("collector_not_listening")
    if payload.get("summary", {}).get("event_count", 0) <= 0:
        errors.append("no_otel_events_indexed")
    if payload.get("summary", {}).get("metric_batches", 0) <= 0:
        warnings.append("no_metric_batches_in_window")
    if payload.get("summary", {}).get("trace_batches", 0) <= 0:
        warnings.append("no_trace_batches_in_window")
    db = payload.get("sqlite", {})
    if db and db.get("integrity") != "ok":
        errors.append("sqlite_integrity_not_ok")
    config = payload.get("collector_config", {})
    if config.get("has_logs_pipeline"):
        errors.append("collector_logs_pipeline_enabled")
    if not config.get("binds_loopback_4318"):
        warnings.append("collector_config_loopback_binding_not_confirmed")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    log_events, log_source = parse_collector_log(args.collector_log)
    receipt_events, receipt_source = parse_receipts(args.receipts)
    events = sorted(log_events + receipt_events, key=lambda event: (event.get("timestamp_utc") or "", event.get("source") or "", event.get("line_number") or 0))
    summary = summarize_events(events, args.window_hours)
    health = collector_health()
    config = collector_config_posture(args.collector_config)
    drift = drift_summary(events)
    actions = build_actions(summary, config, health, drift)
    tool_workflow_metadata = as_dict(load_json_artifact(args.tool_workflow_metadata))
    tool_workflow_summary = as_dict(tool_workflow_metadata.get("summary"))
    sqlite_summary: dict[str, Any] = {}
    if args.write_db:
        sqlite_summary = write_db(args.db, events, actions)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Local OTEL operational visibility: collector health, event summaries, SQLite query surface, and review-only action routing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sources": {
            "collector_log": log_source,
            "local_receipts": receipt_source,
            "collector_config": rel(args.collector_config),
            "events_jsonl": rel(args.events),
            "sqlite": rel(args.db),
            "window_summary": rel(args.window_summary_out),
            "tool_workflow_metadata": rel(args.tool_workflow_metadata),
        },
        "collector_health": health,
        "collector_config": config,
        "summary": summary,
        "drift": drift,
        "tool_workflow_metadata": {
            "present": bool(tool_workflow_metadata),
            "status": tool_workflow_metadata.get("status"),
            "generated_at_utc": tool_workflow_metadata.get("generated_at_utc"),
            "row_count": tool_workflow_summary.get("row_count"),
            "unique_tool_count": tool_workflow_summary.get("unique_tool_count"),
            "workflow_attributed_count": tool_workflow_summary.get("workflow_attributed_count"),
            "session_attributed_count": tool_workflow_summary.get("session_attributed_count"),
            "failed_or_blocked_count": tool_workflow_summary.get("failed_or_blocked_count"),
            "failure_category_counts": tool_workflow_summary.get("failure_category_counts"),
            "top_tool_name_counts": dict(list(as_dict(tool_workflow_summary.get("tool_name_counts")).items())[:20]),
            "privacy_scan_status": as_dict(tool_workflow_metadata.get("privacy_scan")).get("status"),
            "meaning": "Metadata-only tool/workflow/session context for explaining OTEL volume and workflow failures.",
        },
        "field_inventory": {
            "available_now": [
                "collector endpoint health",
                "metric batch count",
                "metric data-point count",
                "trace batch count",
                "span count",
                "collector warning/error lines",
                "legacy local receipt content length and signal when receipts exist",
                "metadata-only tool names from local proof artifacts",
                "metadata-only tool status/failure categories from local proof artifacts",
                "metadata-only session/workflow/lane IDs from local proof artifacts",
            ],
            "not_available_from_basic_debug_log": [
                "model/provider name",
                "token usage",
                "cost",
                "raw tool payloads",
                "request latency fields beyond collector batch timing",
            ],
            "next_depth_gate": "Tool/workflow metadata is now collected from bounded proof artifacts; collector-depth expansion remains owner-gated for richer runtime fields.",
        },
        "actions": actions,
        "sqlite": sqlite_summary,
        "cron_contract": {
            "recommended_schedule": "daily or twice daily after normal operating windows",
            "command": "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            "reply_policy": "NO_REPLY when validation ok and only info candidates exist; summarize when warnings/errors or repeated action candidates appear.",
            "blocked_actions": [
                "no collector/runtime/config mutation",
                "no logs/content capture enablement",
                "no external telemetry export",
                "no skill/cron changes without separate action packet or explicit approval",
            ],
        },
        "stop_lines": [
            "This script is local-only and review-only. It indexes existing collector output; it does not change telemetry capture settings, collector config, cron schedules, OpenClaw runtime config, finance/canon/portfolio, customer surfaces, or execution/account authority.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local OTEL operations control packet.")
    parser.add_argument("--collector-log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--collector-config", type=Path, default=DEFAULT_COLLECTOR_CONFIG)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--window-summary-out", type=Path, default=DEFAULT_WINDOW_SUMMARY)
    parser.add_argument("--legacy-control-loop-out", type=Path, default=DEFAULT_LEGACY_CONTROL_LOOP)
    parser.add_argument("--field-depth-packet-out", type=Path, default=DEFAULT_FIELD_DEPTH_PACKET)
    parser.add_argument("--tool-workflow-metadata", type=Path, default=DEFAULT_TOOL_WORKFLOW_METADATA)
    parser.add_argument("--window-hours", type=float, default=24.0)
    parser.add_argument("--multi-window", action="store_true", help="also write the 1h/6h/24h/7d/30d operational window summary")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args)
    events, _ = parse_collector_log(args.collector_log)
    receipts, _ = parse_receipts(args.receipts)
    all_events = sorted(events + receipts, key=lambda event: (event.get("timestamp_utc") or "", event.get("source") or "", event.get("line_number") or 0))
    window_payload: dict[str, Any] | None = None
    if args.multi_window:
        window_payload = build_window_summary(
            all_events,
            payload.get("collector_health", {}),
            payload.get("collector_config", {}),
        )
    compat_payload = build_control_loop_compat(payload, window_payload)
    if args.write:
        write_jsonl(args.events, all_events)
        atomic_write_json(args.out, payload)
        atomic_write_json(args.legacy_control_loop_out, compat_payload)
        atomic_write_json(
            args.field_depth_packet_out,
            build_field_depth_packet(
                payload.get("collector_config", {}),
                payload.get("summary", {}),
                payload.get("drift", {}),
            ),
        )
        if window_payload is not None:
            atomic_write_json(args.window_summary_out, window_payload)
        print(
            f"wrote {rel(args.out)} status={payload['status']} "
            f"events={payload['summary']['event_count']} metrics={payload['summary']['metric_batches']} traces={payload['summary']['trace_batches']}"
        )
        if window_payload is not None:
            print(
                f"wrote {rel(args.window_summary_out)} status={window_payload['status']} "
                f"windows={len(window_payload.get('windows', []))}"
            )
        print(f"wrote {rel(args.legacy_control_loop_out)} status={compat_payload['status']} compat=legacy_audit_bridge")
    else:
        print(json.dumps(window_payload or payload["summary"], indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    if args.validate and window_payload is not None and window_payload["validation"]["status"] != "ok":
        return 1
    if args.validate and compat_payload["status"] not in {"ok", "warning"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
