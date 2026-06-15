#!/usr/bin/env python3
"""Focused regressions for local OTEL ops control artifacts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from otel_ops_control import build_control_loop_compat, build_field_depth_packet, build_window_summary, drift_summary


def event(event_id: str, age_minutes: int, signal: str, value: int) -> dict[str, object]:
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).replace(microsecond=0)
    row: dict[str, object] = {
        "event_id": event_id,
        "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "source": "test",
        "line_number": 1,
        "event_type": "collector_metric_batch" if signal == "metrics" else "collector_trace_batch",
        "signal": signal,
        "severity": "info",
        "summary": "test",
    }
    if signal == "metrics":
        row["metrics"] = 1
        row["data_points"] = value
        row["spans"] = None
    else:
        row["metrics"] = None
        row["data_points"] = None
        row["spans"] = value
    return row


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    events = [
        event("m-recent", 10, "metrics", 10),
        event("t-recent", 10, "traces", 2),
        event("m-2h", 120, "metrics", 20),
        event("t-2h", 120, "traces", 3),
        event("m-8d", 8 * 24 * 60, "metrics", 30),
    ]
    health = {"status": "ok", "listening": True}
    config = {"binds_loopback_4318": True, "debug_verbosity_basic": True}
    window_payload = build_window_summary(events, health, config)
    windows = {row["window_id"]: row for row in window_payload["windows"]}
    drift = drift_summary(events)

    expect(window_payload["validation"]["status"] == "ok", "window summary should validate", errors)
    expect(set(windows) == {"intraday_1h", "intraday_6h", "daily_24h", "weekly_7d", "monthly_30d"}, "window IDs drifted", errors)
    expect(windows["intraday_1h"]["summary"]["event_count"] == 2, "1h window should include only recent metric/trace events", errors)
    expect(windows["intraday_6h"]["summary"]["event_count"] == 4, "6h window should include recent plus 2h events", errors)
    expect(windows["weekly_7d"]["summary"]["event_count"] == 4, "7d window should exclude 8-day event", errors)
    expect(windows["monthly_30d"]["summary"]["event_count"] == 5, "30d window should include all synthetic events", errors)
    expect(window_payload["drift"]["status"] in {"ok", "review"}, "window summary should expose drift status", errors)
    expect("daily_warning_or_error_count" in drift, "drift summary should expose warning/error count", errors)

    compat = build_control_loop_compat(
        {
            "status": "ok",
            "summary": {"window_hours": 24.0, "event_count": 4, "metric_batches": 2, "trace_batches": 2, "reported_spans": 5},
            "authority_boundary": {},
        },
        window_payload,
    )
    expect(compat["status"] == "ok", "legacy control-loop bridge should be ok when canonical artifacts are ok", errors)
    expect(compat["canonical_owner"] == "tmp/otel-ops-control.json", "compat bridge must point to canonical owner", errors)
    expect(compat["compatibility_role"] == "legacy_audit_bridge_not_owner", "compat bridge must not become canonical owner", errors)
    packet = build_field_depth_packet(config, windows["daily_24h"]["summary"], drift)
    expect(packet["status"] == "owner_decision_required", "field-depth packet must require owner decision", errors)
    expect(packet["authority_boundary"]["collector_config_mutation_allowed"] is False, "field-depth packet must not allow config mutation", errors)
    expect("no collector config mutation" in packet["blocked_now"], "field-depth packet must preserve config stop line", errors)

    if errors:
        print("otel_ops_control_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("otel_ops_control_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
