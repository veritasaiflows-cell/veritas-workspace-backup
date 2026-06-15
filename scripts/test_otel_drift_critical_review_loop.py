#!/usr/bin/env python3
"""Focused synthetic tests for WF74 OTEL drift persistence classification."""
from __future__ import annotations

import copy

import otel_drift_critical_review_loop as drift_loop


def window(window_id: str, hours: float, events: int, warnings: int = 0, errors: int = 0) -> dict[str, object]:
    return {
        "window_id": window_id,
        "window_hours": hours,
        "summary": {
            "window_hours": hours,
            "event_count": events,
            "by_severity": {"info": events, "warning": warnings, "error": errors},
        },
        "rates_per_hour": {"events": round(events / hours, 4)},
    }


def summary(daily_events: int, weekly_events: int, *, warnings: int = 0, errors: int = 0) -> dict[str, object]:
    return {
        "schema": "veritas.otel_ops_window_summary.v1",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "windows": [
            window("daily_24h", 24.0, daily_events, warnings, errors),
            window("weekly_7d", 168.0, weekly_events),
        ],
        "weekly_daily_buckets_utc": [
            {"date_utc": "2026-06-10", "event_count": 100, "warning_count": 0, "error_count": 0},
            {"date_utc": "2026-06-11", "event_count": 100, "warning_count": 0, "error_count": 0},
        ],
    }


def queue(has_drift: bool) -> dict[str, object]:
    opportunities = []
    if has_drift:
        opportunities.append({
            "opportunity_id": "collector_config-test",
            "signal": "otel_operational_drift_review",
            "title": "Review OTEL event-rate drift against the weekly baseline",
            "priority": 88,
            "recommended_action": "Track whether the drift persists.",
        })
    return {"opportunities": opportunities}


def build(window_summary: dict[str, object], queue_payload: dict[str, object] | None = None) -> dict[str, object]:
    return drift_loop.build_payload(window_summary, {"drift": {}}, queue_payload or queue(False))


def test_normal_variance() -> None:
    payload = build(summary(240, 1680))
    assert payload["state"] == "normal_variance"
    assert payload["severity"] == "info"
    assert payload["validation"]["status"] == "ok"


def test_resolved_when_queue_signal_clears() -> None:
    payload = build(summary(240, 1680), queue(True))
    assert payload["state"] == "resolved"
    assert payload["classification"]["reasons"] == ["prior_queue_drift_signal_no_longer_present"]


def test_watch_for_single_non_persistent_ratio() -> None:
    payload = build(summary(550, 1680))
    assert payload["state"] == "watch"
    assert payload["severity"] == "warning"


def test_persistent_drift_uses_queue_and_bucket_evidence() -> None:
    packet = summary(700, 1680)
    packet["weekly_daily_buckets_utc"] = [
        {"date_utc": "2026-06-10", "event_count": 700, "warning_count": 0, "error_count": 0},
        {"date_utc": "2026-06-11", "event_count": 720, "warning_count": 0, "error_count": 0},
    ]
    payload = build(packet, queue(True))
    assert payload["state"] == "persistent_drift"
    assert payload["severity"] == "warning"
    assert payload["drift_evidence"]["persistent_bucket_count"] == 2
    assert payload["authority_boundary"]["collector_config_mutation_allowed"] is False


def test_critical_drift_for_errors() -> None:
    payload = build(summary(240, 1680, errors=1))
    assert payload["state"] == "critical_drift"
    assert payload["severity"] == "critical"
    assert payload["validation"]["status"] == "ok"
    assert "daily_error_count_ge_1" in payload["classification"]["reasons"]


def test_missing_evidence_blocks() -> None:
    payload = build({"schema": "bad", "validation": {"status": "blocked"}})
    assert payload["state"] == "blocked_missing_evidence"
    assert payload["status"] == "blocked"
    assert payload["validation"]["status"] == "blocked"


def test_authority_validation_blocks_widened_flags() -> None:
    payload = build(summary(240, 1680))
    widened = copy.deepcopy(payload)
    widened["authority_boundary"]["runtime_config_mutation_allowed"] = True
    validation = drift_loop.validate_payload(widened)
    assert validation["status"] == "blocked"
    assert any("runtime_config_mutation_allowed" in error for error in validation["errors"])


def test_markdown_contains_thresholds_and_guardrails() -> None:
    payload = build(summary(1200, 1680), queue(True))
    md = drift_loop.render_markdown(payload)
    assert "OTEL Drift Critical Review Loop" in md
    assert "Persistent drift band" in md
    assert "no collector config mutation" in md
    assert "no owner approval inference" in md


def main() -> int:
    test_normal_variance()
    test_resolved_when_queue_signal_clears()
    test_watch_for_single_non_persistent_ratio()
    test_persistent_drift_uses_queue_and_bucket_evidence()
    test_critical_drift_for_errors()
    test_missing_evidence_blocks()
    test_authority_validation_blocks_widened_flags()
    test_markdown_contains_thresholds_and_guardrails()
    print("otel_drift_critical_review_loop targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
