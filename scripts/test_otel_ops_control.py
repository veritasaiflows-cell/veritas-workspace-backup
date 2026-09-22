#!/usr/bin/env python3
"""Focused regressions for local OTEL ops control artifacts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from otel_ops_control import (
    DEFAULT_COLLECTOR_CONFIG,
    build_control_loop_compat,
    build_field_depth_packet,
    build_window_summary,
    collector_config_posture,
    drift_summary,
    build_telemetry_context,
    load_telemetry_summary,
    _bounded_read_text,
    parse_collector_logs,
    volume_normalization_recommendation,
)


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


def collector_line(timestamp: str, signal: str, count: int) -> str:
    if signal == "metrics":
        return (
            f'{timestamp}\tinfo\tMetrics\t{{"otelcol.signal": "metrics", '
            f'"resource metrics": 1, "metrics": 3, "data points": {count}}}'
        )
    return (
        f'{timestamp}\tinfo\tTraces\t{{"otelcol.signal": "traces", '
        f'"resource spans": 1, "spans": {count}}}'
    )


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

    empty_drift = drift_summary([])
    empty_volume = volume_normalization_recommendation(
        {"event_count": 0, "metric_batches": 0, "trace_batches": 0, "by_severity": {}},
        empty_drift,
    )
    expect(empty_drift["status"] == "insufficient_data", "zero events must not report drift status ok", errors)
    expect(empty_drift["data_sufficiency"] == "no_telemetry_events", "zero-event drift must explain insufficient data", errors)
    expect(empty_volume["status"] == "insufficient_data", "zero events must not recommend hold_config", errors)
    expect(empty_volume["configuration_recommendation_allowed"] is False, "zero events must forbid a configuration recommendation", errors)
    expect(empty_volume["owner_gated_config_options"] == [], "zero events must not emit configuration options", errors)
    expect("matches" not in empty_volume["current_recommendation"].lower(), "zero-event recommendation must not claim baseline match", errors)

    observed_volume = volume_normalization_recommendation(windows["daily_24h"]["summary"], drift)
    expect(observed_volume["status"] in {"hold_config", "review_config_proposal"}, "nonzero telemetry behavior must remain actionable", errors)
    expect(observed_volume["configuration_recommendation_allowed"] is True, "nonzero telemetry should retain owner-gated review behavior", errors)

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
    expect(
        any("no collector config mutation" in str(item) for item in packet["blocked_now"]),
        "field-depth packet must preserve config stop line",
        errors,
    )
    approved_config = collector_config_posture(DEFAULT_COLLECTOR_CONFIG)
    approved_packet = build_field_depth_packet(approved_config, windows["daily_24h"]["summary"], drift)
    expect(approved_packet["status"] == "approved_enabled", "exact approved config identity should remain approved", errors)
    expect(
        approved_packet["authority_boundary"]["owner_approved_local_depth_expansion"] is True,
        "exact approved path/hash should prove owner approval",
        errors,
    )
    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        alternate_config = tmp_dir / "alternate-collector.yaml"
        alternate_config.write_bytes(DEFAULT_COLLECTOR_CONFIG.read_bytes())
        alternate_posture = collector_config_posture(alternate_config)
        alternate_packet = build_field_depth_packet(alternate_posture, windows["daily_24h"]["summary"], drift)
        expect(
            alternate_packet["status"] == "observed_enabled_owner_approval_unverified",
            "alternate config with identical keys/content must not inherit approval",
            errors,
        )
        expect(
            alternate_packet["authority_boundary"]["local_depth_expansion_observed_enabled"] is True,
            "alternate enabled config should remain observable",
            errors,
        )
        expect(
            alternate_packet["authority_boundary"]["owner_approved_local_depth_expansion"] is False,
            "alternate config must not infer owner approval",
            errors,
        )
        expect(
            alternate_packet["collector_config_approval_identity"]["path_matches_approved_config"] is False,
            "alternate path must fail exact config identity",
            errors,
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000%z")
        primary = tmp_dir / "collector.err.log"
        restart = tmp_dir / "local-restart.err.log"
        primary.write_text(collector_line(timestamp, "metrics", 10) + "\n", encoding="utf-8")
        restart.write_text(collector_line(timestamp, "traces", 2) + "\n", encoding="utf-8")
        parsed, source = parse_collector_logs(primary, str(tmp_dir / "*.err.log"))
        expect(source["file_count"] == 2, "collector log glob should include restart log", errors)
        expect(len(parsed) == 2, "collector log parser should merge primary and restart events", errors)
        expect({row["signal"] for row in parsed} == {"metrics", "traces"}, "collector log parser should preserve signal types", errors)
        import json as _json2
        from datetime import timezone as _tz3
        def _w(d):
            p = tmp_dir / ("t_" + str(abs(hash(_json2.dumps(d, sort_keys=True))) % 999999) + ".json")
            p.write_text(_json2.dumps(d), encoding="utf-8")
            return p
        now = datetime.now(_tz3.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        good_probe = {"schema": "veritas.otel_runtime_metadata_probe.v1", "generated_at_utc": now, "status": "ok", "validation": {"status": "ok"}, "forbidden_findings": [], "blocked_markers": {}, "summary": {"runtime_metadata_observed": True, "allowed_field_count": 27, "raw_content_marker_count": 0, "secret_or_header_marker_count": 0, "metadata_depth_approved_enabled": True, "file_exporter_observed": True, "debug_log_observed": False, "runtime_metadata_learning_ready": True}}
        good_depth = {"schema": "veritas.otel_token_cost_metadata_depth_owner_packet.v1", "generated_at_utc": now, "status": "owner_decision_pending", "validation": {"status": "warning"}, "patch_would_change_token_or_cost_coverage": False}
        r = load_telemetry_summary(_w(good_probe), "veritas.otel_runtime_metadata_probe.v1")
        expect(r.get("valid") is True and r["scalars"]["allowed_field_count"] == 27, "fresh probe consumed", errors)
        d = load_telemetry_summary(_w(good_depth), "veritas.otel_token_cost_metadata_depth_owner_packet.v1")
        expect(d.get("valid") is True and d.get("owner_gated") is True, "owner-gated depth evidence only", errors)
        expect(load_telemetry_summary(tmp_dir / "nope.json", "veritas.otel_runtime_metadata_probe.v1").get("reason") == "missing", "missing fail-closed", errors)
        bad = dict(good_probe); bad["summary"] = dict(good_probe["summary"]); bad["summary"]["allowed_field_count"] = "27"
        expect("whitelist_type_invalid" in str(load_telemetry_summary(_w(bad), "veritas.otel_runtime_metadata_probe.v1").get("reason")), "strict types", errors)
        hostile = dict(good_probe); hostile["summary"] = dict(good_probe["summary"]); hostile["summary"]["raw_content_marker_count"] = 1
        expect("raw_or_secret" in str(load_telemetry_summary(_w(hostile), "veritas.otel_runtime_metadata_probe.v1").get("reason")), "raw marker rejected", errors)
        ff = dict(good_probe); ff["forbidden_findings"] = ["x"]
        expect("forbidden" in str(load_telemetry_summary(_w(ff), "veritas.otel_runtime_metadata_probe.v1").get("reason")), "forbidden rejected", errors)
        stale = dict(good_probe); stale["generated_at_utc"] = "2020-01-01T00:00:00Z"
        expect("stale" in str(load_telemetry_summary(_w(stale), "veritas.otel_runtime_metadata_probe.v1").get("reason")), "stale rejected", errors)
        fut = dict(good_probe); fut["generated_at_utc"] = "2999-01-01T00:00:00Z"
        expect("stale" in str(load_telemetry_summary(_w(fut), "veritas.otel_runtime_metadata_probe.v1").get("reason")), "future rejected", errors)
        over = tmp_dir / "over.json"; over.write_bytes(b"x" * (262144 + 1))
        expect("oversize" in str(load_telemetry_summary(over, "veritas.otel_runtime_metadata_probe.v1").get("reason")), "oversize rejected", errors)
        mal = tmp_dir / "mal.json"; mal.write_bytes(b"\xff\xfe{not json")
        expect("malformed" in str(load_telemetry_summary(mal, "veritas.otel_runtime_metadata_probe.v1").get("reason")), "malformed rejected", errors)
        ctx = build_telemetry_context(_w(good_probe), _w(good_depth))
        expect(ctx.get("status") == "ok", "ctx ok", errors)
        ctx2 = build_telemetry_context(tmp_dir / "nope.json", _w(good_depth))
        expect(ctx2.get("status") == "warning", "ctx warning when missing", errors)
        data, flag = _bounded_read_text(_w(good_probe), 262144)
        expect(flag is None and isinstance(data, bytes) and len(data) <= 262144, "bounded read within limit", errors)
        big = tmp_dir / "big.json"; big.write_bytes(b"y" * (262144 + 5))
        data2, flag2 = _bounded_read_text(big, 262144)
        expect(flag2 == "oversize" and data2 is None, "bounded read rejects oversize via limit+1", errors)

    if errors:
        print("otel_ops_control_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("otel_ops_control_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
