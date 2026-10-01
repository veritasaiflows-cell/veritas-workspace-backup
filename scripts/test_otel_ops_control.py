#!/usr/bin/env python3
"""Focused regressions for local OTEL ops control artifacts."""
from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import otel_ops_control as ops
from otel_ops_control import (
    DEFAULT_COLLECTOR_CONFIG,
    OWNER_DECISIONS,
    OWNER_DECISIONS_SCHEMA,
    RETIRE_DECISION,
    TOKEN_DEPTH_DECISION_ID,
    build_actions,
    build_control_loop_compat,
    build_field_depth_packet,
    build_window_summary,
    collector_config_posture,
    drift_summary,
    build_telemetry_context,
    load_telemetry_summary,
    load_token_depth_owner_decision,
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
        no_decisions = tmp_dir / "no-decisions.json"  # never created: keeps these calls on the pending-packet path
        ctx = build_telemetry_context(_w(good_probe), _w(good_depth), decisions_path=no_decisions)
        expect(ctx.get("status") == "ok", "ctx ok", errors)
        ctx2 = build_telemetry_context(tmp_dir / "nope.json", _w(good_depth), decisions_path=no_decisions)
        expect(ctx2.get("status") == "warning", "ctx warning when missing", errors)
        data, flag = _bounded_read_text(_w(good_probe), 262144)
        expect(flag is None and isinstance(data, bytes) and len(data) <= 262144, "bounded read within limit", errors)
        big = tmp_dir / "big.json"; big.write_bytes(b"y" * (262144 + 5))
        data2, flag2 = _bounded_read_text(big, 262144)
        expect(flag2 == "oversize" and data2 is None, "bounded read rejects oversize via limit+1", errors)
        expect(ctx["token_depth"].get("reason") == "fresh_valid_owner_gated" and "retired_by_owner_decision" not in ctx["token_depth"], "without a decision record the pending-packet path must be unchanged", errors)

        # ---- token-depth owner-decision retirement (hermetic: every fixture lives in this temp dir) ----
        expect(OWNER_DECISIONS.as_posix().endswith("state/owner-decisions/otel-recommendations.json"), "OWNER_DECISIONS default path drifted", errors)
        expect(OWNER_DECISIONS_SCHEMA == "veritas.owner_decisions.otel_recommendations.v1", "owner-decisions schema constant drifted", errors)
        expect(TOKEN_DEPTH_DECISION_ID == "token_cost_metadata_depth", "token-depth decision id constant drifted", errors)
        expect(RETIRE_DECISION == "decline_and_retire_the_recommendation", "retire decision constant drifted", errors)
        decisions_schema = "veritas.owner_decisions.otel_recommendations.v1"
        decision_row = {"id": "token_cost_metadata_depth", "decision": "decline_and_retire_the_recommendation", "decided_by": "randall", "decided_at_utc": "2026-09-12T15:17:06+00:00", "authority": "SENTINEL-authority", "evidence": "SENTINEL-evidence", "because": "SENTINEL-because", "effect": "SENTINEL-effect"}
        expected_decision = {"id": "token_cost_metadata_depth", "decision": "decline_and_retire_the_recommendation", "decided_by": "randall", "decided_at_utc": "2026-09-12T15:17:06+00:00"}
        def _doc(*rows, **fields):
            return dict({"schema": decisions_schema, "decisions": list(rows)}, **fields)
        def _dec(name, doc):
            p = tmp_dir / ("dec-" + name + ".json")
            p.write_bytes(doc if isinstance(doc, bytes) else json.dumps(doc).encode("utf-8"))
            return p
        probe_path = _w(good_probe)
        no_depth = tmp_dir / "no-depth-packet.json"  # never created
        dec_retired = _dec("retired", _doc(decision_row))

        # Retirement recognized; the depth packet is not consulted.
        expect(load_token_depth_owner_decision(dec_retired) == expected_decision, "valid record should load exactly id/decision/decided_by/decided_at_utc", errors)
        real_loader = ops.load_telemetry_summary
        loaded_schemas = []
        def spy_loader(path, expected_schema, *a, **k):
            loaded_schemas.append(expected_schema)
            return real_loader(path, expected_schema, *a, **k)
        ops.load_telemetry_summary = spy_loader
        try:
            build_telemetry_context(probe_path, _w(good_depth), decisions_path=dec_retired)
        finally:
            ops.load_telemetry_summary = real_loader
        expect(loaded_schemas == ["veritas.otel_runtime_metadata_probe.v1"], "retired path must not read the token-depth packet", errors)
        ctx_r = build_telemetry_context(probe_path, no_depth, decisions_path=dec_retired)
        expect(ctx_r["status"] == "ok" and ctx_r["warnings"] == [], "retired decision must give ctx ok with the depth packet missing", errors)
        row_r = ctx_r["token_depth"]
        expect(set(row_r) == {"present", "fresh", "valid", "reason", "status", "owner_gated", "retired_by_owner_decision", "generated_at_utc", "decision"}, "retired row key set drifted", errors)
        expect(row_r["present"] is True and row_r["fresh"] is True and row_r["valid"] is True, "retired row must be present/fresh/valid", errors)
        expect(row_r["reason"] == "owner_decision_retired" and row_r["status"] == "owner_declined_retired", "retired row reason/status drifted", errors)
        expect(row_r["owner_gated"] is False and row_r["retired_by_owner_decision"] is True, "retired row must not be owner-gated", errors)
        expect(row_r["decision"] == expected_decision, "retired row must embed the four-field decision", errors)
        try:
            stamp_age = (datetime.now(timezone.utc) - datetime.strptime(row_r["generated_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            stamp_age = None
        expect(stamp_age is not None and -5 <= stamp_age <= 300, "retired row generated_at_utc must be evaluation-time UTC, seconds precision, trailing Z", errors)

        # No free text: the record's because/effect/authority/evidence never reach the row or the context.
        leak_scan = json.dumps(ctx_r, sort_keys=True) + json.dumps(load_token_depth_owner_decision(dec_retired), sort_keys=True)
        for word in ("because", "effect", "authority", "evidence", "SENTINEL"):
            expect(word not in leak_scan, "retired row/ctx must not carry free-text '" + word + "'", errors)

        # Fail-closed: no valid record means no retirement, and the pending-packet requirement applies (token_depth_missing here).
        pad = 262144 - len(json.dumps(_doc(dict(decision_row, because=""))).encode("utf-8"))
        bad_records = {
            "malformed-json": b"{not json",
            "invalid-utf8": b"\xff\xfe{}",
            "not-an-object": [decision_row],
            "missing-schema": {"decisions": [decision_row]},
            "schema-mismatch": _doc(decision_row, schema="veritas.owner_decisions.other.v1"),
            "decisions-not-a-list": {"schema": decisions_schema, "decisions": decision_row},
            "no-rows": _doc(),
            "other-id-only": _doc(dict(decision_row, id="some_other_recommendation")),
            "other-decision": _doc(dict(decision_row, decision="keep_the_recommendation")),
            "future-dated": _doc(dict(decision_row, decided_at_utc="2999-01-01T00:00:00+00:00")),
            "unparseable-date": _doc(dict(decision_row, decided_at_utc="not-a-date")),
            "non-string-date": _doc(dict(decision_row, decided_at_utc=20260912)),
            "missing-date": _doc({k: v for k, v in decision_row.items() if k != "decided_at_utc"}),
            "empty-decided-by": _doc(dict(decision_row, decided_by="")),
            "blank-decided-by": _doc(dict(decision_row, decided_by="   ")),
            "non-string-decided-by": _doc(dict(decision_row, decided_by=7)),
            "duplicate-id": _doc(decision_row, dict(decision_row)),
            "duplicate-id-conflicting": _doc(decision_row, dict(decision_row, decision="keep_the_recommendation")),
            "oversize": _doc(dict(decision_row, because="x" * (pad + 1))),
        }
        for name, doc in bad_records.items():
            bad_path = _dec("bad-" + name, doc)
            expect(load_token_depth_owner_decision(bad_path) is None, name + " record must not retire the recommendation", errors)
            bad_ctx = build_telemetry_context(probe_path, no_depth, decisions_path=bad_path)
            expect(bad_ctx["status"] == "warning" and bad_ctx["warnings"] == ["token_depth_missing"], name + " record must fail closed with a token_depth_* warning", errors)
            expect(bad_ctx["token_depth"].get("retired_by_owner_decision") is not True, name + " record must not yield a retired depth row", errors)
        expect(load_token_depth_owner_decision(no_decisions) is None, "missing decisions record must not retire the recommendation", errors)
        ctx_missing = build_telemetry_context(probe_path, no_depth, decisions_path=no_decisions)
        expect(ctx_missing["status"] == "warning" and ctx_missing["warnings"] == ["token_depth_missing"], "missing decisions record plus missing packet must warn token_depth_missing", errors)
        expect(load_token_depth_owner_decision(tmp_dir) is None and load_token_depth_owner_decision(None) is None, "unreadable decision paths must return None, never raise", errors)
        for name, doc in {
            "z-suffix-timestamp": _doc(dict(decision_row, decided_at_utc="2026-09-12T15:17:06Z")),
            "sibling-rows-ignored": _doc(dict(decision_row, id="some_other_recommendation", decision="keep_the_recommendation"), decision_row),
            "exact-size-limit": _doc(dict(decision_row, because="x" * pad)),
        }.items():
            expect(load_token_depth_owner_decision(_dec("ok-" + name, doc)) is not None, name + " record should still retire the recommendation", errors)

        # Window-summary embedding carries the retirement fields; owner_gated is no longer hard-coded True.
        window_r = build_window_summary(events, health, config, ctx_r)
        emb_r = window_r["telemetry_context"]["token_depth"]
        expect(emb_r == {"present": True, "fresh": True, "valid": True, "reason": "owner_decision_retired", "status": "owner_declined_retired", "owner_gated": False, "retired_by_owner_decision": True, "generated_at_utc": row_r["generated_at_utc"], "decision": expected_decision}, "window embedding of a retired depth row drifted", errors)
        expect(window_r["telemetry_context"]["status"] == "ok" and window_r["telemetry_context"]["warnings"] == [], "window embedding of a retired ctx should be ok with no warnings", errors)
        expect(not any(word in json.dumps(window_r["telemetry_context"], sort_keys=True) for word in ("because", "effect", "authority", "evidence", "SENTINEL")), "window embedding must not carry free text", errors)
        ctx_pending = build_telemetry_context(probe_path, _w(good_depth), decisions_path=no_decisions)
        emb_p = build_window_summary(events, health, config, ctx_pending)["telemetry_context"]["token_depth"]
        expect(emb_p["owner_gated"] is True and emb_p["retired_by_owner_decision"] is False and emb_p["decision"] is None, "pending depth embedding should stay owner-gated and not retired", errors)
        expect(emb_p["status"] == "owner_decision_pending" and emb_p["generated_at_utc"] == now, "pending depth embedding must carry the packet status and generated_at_utc", errors)
        emb_m = build_window_summary(events, health, config, ctx_missing)["telemetry_context"]["token_depth"]
        expect(emb_m["owner_gated"] is False and emb_m["retired_by_owner_decision"] is False and emb_m["generated_at_utc"] is None and emb_m["decision"] is None, "missing depth embedding must not claim owner-gated or retired and must carry generated_at_utc None", errors)
        emb_s = build_window_summary(events, health, config, {"status": "ok", "warnings": [], "runtime_probe": {}, "token_depth": {"owner_gated": 1, "retired_by_owner_decision": 1, "decision": expected_decision}})["telemetry_context"]["token_depth"]
        expect(emb_s["owner_gated"] is False and emb_s["retired_by_owner_decision"] is False and emb_s["decision"] is None, "window embedding flags must be strict booleans, not truthiness", errors)

        # build_actions wiring: recommended command by warning prefix, and the fresh-action depth note.
        def _act(actions, action_id):
            return next((a for a in actions if a["id"] == action_id), None)
        act_args = ({"event_count": 1}, {"binds_loopback_4318": True}, {"status": "ok"}, {"status": "ok"})
        stale_id = "otel_telemetry_summary_stale_or_missing"
        probe_cmd = "python scripts\\otel_runtime_metadata_probe.py --write --write-md --validate"
        depth_cmd = "python scripts\\otel_token_cost_metadata_depth_packet.py --write --validate"
        depth_suffix = "; token-depth owner decision record state/owner-decisions/otel-recommendations.json absent or not a valid decline_and_retire record"
        stale_depth_only = _act(build_actions(*act_args, ctx_missing), stale_id)
        expect(stale_depth_only is not None and stale_depth_only["recommended_command"] == depth_cmd, "token_depth-only warning should recommend the depth-packet command", errors)
        expect(stale_depth_only is not None and "token_depth_missing" in stale_depth_only["rationale"] and stale_depth_only["rationale"].endswith(depth_suffix), "token_depth-only rationale should append the owner-decision-record note", errors)
        ctx_probe_missing = build_telemetry_context(tmp_dir / "nope.json", _w(good_depth), decisions_path=no_decisions)
        expect(ctx_probe_missing["warnings"] == ["runtime_probe_missing"], "probe-only fixture should warn runtime_probe_missing", errors)
        stale_probe_only = _act(build_actions(*act_args, ctx_probe_missing), stale_id)
        expect(stale_probe_only is not None and stale_probe_only["recommended_command"] == probe_cmd and depth_suffix not in stale_probe_only["rationale"], "runtime_probe warning should keep the probe command and rationale", errors)
        ctx_both_missing = build_telemetry_context(tmp_dir / "nope.json", no_depth, decisions_path=no_decisions)
        expect(ctx_both_missing["warnings"] == ["runtime_probe_missing", "token_depth_missing"], "both-missing fixture should warn on probe and depth", errors)
        stale_both = _act(build_actions(*act_args, ctx_both_missing), stale_id)
        expect(stale_both is not None and stale_both["recommended_command"] == probe_cmd and depth_suffix not in stale_both["rationale"], "runtime_probe plus token_depth warnings should keep the probe command", errors)
        stale_unevaluated = _act(build_actions(*act_args, None), stale_id)
        expect(stale_unevaluated is not None and stale_unevaluated["recommended_command"] == probe_cmd and depth_suffix not in stale_unevaluated["rationale"], "telemetry_not_evaluated should keep the probe command", errors)
        stale_mixed = _act(build_actions(*act_args, {"status": "warning", "warnings": ["token_depth_missing", "telemetry_not_evaluated"]}), stale_id)
        expect(stale_mixed is not None and stale_mixed["recommended_command"] == probe_cmd and depth_suffix not in stale_mixed["rationale"], "a non-token_depth warning alongside token_depth should keep the probe command", errors)
        fresh_r = _act(build_actions(*act_args, ctx_r), "otel_telemetry_summary_fresh")
        expect(fresh_r is not None and "depth=owner_declined_retired" in fresh_r["rationale"], "fresh action rationale should report depth=owner_declined_retired", errors)
        expect(_act(build_actions(*act_args, ctx_r), stale_id) is None, "a retired depth row must not raise the stale action", errors)
        fresh_p = _act(build_actions(*act_args, ctx_pending), "otel_telemetry_summary_fresh")
        expect(fresh_p is not None and "depth=owner_gated_depth_no_approval" in fresh_p["rationale"], "pending depth should keep the owner-gated note", errors)
        fresh_u = _act(build_actions(*act_args, {"status": "ok", "warnings": [], "runtime_probe": {}, "token_depth": {}}), "otel_telemetry_summary_fresh")
        expect(fresh_u is not None and "depth=depth_unexpected" in fresh_u["rationale"], "an unclassified depth row should report depth_unexpected", errors)
        fresh_s = _act(build_actions(*act_args, {"status": "ok", "warnings": [], "runtime_probe": {}, "token_depth": {"retired_by_owner_decision": "yes", "owner_gated": True}}), "otel_telemetry_summary_fresh")
        expect(fresh_s is not None and "depth=owner_gated_depth_no_approval" in fresh_s["rationale"], "retirement must require a strict True, not truthiness", errors)

        # CLI wiring: --owner-decisions must reach both build_telemetry_context call sites (build_payload and main).
        def _run_ops_main(name, decisions_path):
            out_dir = tmp_dir / ("e2e-" + name)
            out_dir.mkdir()
            argv = ["otel_ops_control.py", "--write", "--multi-window"]
            for flag_name, target in (("--collector-log", out_dir / "collector.err.log"), ("--collector-log-glob", out_dir / "none-*.err.log"), ("--receipts", out_dir / "receipts.jsonl"), ("--collector-config", alternate_config), ("--events", out_dir / "events.jsonl"), ("--db", out_dir / "ops.sqlite"), ("--out", out_dir / "control.json"), ("--window-summary-out", out_dir / "window.json"), ("--legacy-control-loop-out", out_dir / "legacy.json"), ("--field-depth-packet-out", out_dir / "field-depth.json"), ("--tool-workflow-metadata", out_dir / "tool-workflow.json"), ("--runtime-probe-summary", probe_path), ("--token-depth-summary", _w(good_depth)), ("--owner-decisions", decisions_path)):
                argv += [flag_name, str(target)]
            saved_argv, saved_health = sys.argv, ops.collector_health
            sys.argv = argv
            ops.collector_health = lambda *a, **k: {"status": "ok", "host": "127.0.0.1", "port": 4318, "listening": True}
            try:
                with redirect_stdout(StringIO()):
                    rc = ops.main()
            finally:
                sys.argv, ops.collector_health = saved_argv, saved_health
            return rc, json.loads((out_dir / "control.json").read_text(encoding="utf-8")), json.loads((out_dir / "window.json").read_text(encoding="utf-8"))
        rc_r, control_r, window_main_r = _run_ops_main("retired", dec_retired)
        fresh_main_r = _act(control_r["actions"], "otel_telemetry_summary_fresh")
        expect(rc_r == 0, "main() should exit 0 for the retired wiring run", errors)
        expect(fresh_main_r is not None and "depth=owner_declined_retired" in fresh_main_r["rationale"], "--owner-decisions must reach build_payload's telemetry context", errors)
        expect(window_main_r["telemetry_context"]["token_depth"]["retired_by_owner_decision"] is True, "--owner-decisions must reach the window-summary telemetry context", errors)
        rc_p, control_p, window_main_p = _run_ops_main("pending", no_decisions)
        fresh_main_p = _act(control_p["actions"], "otel_telemetry_summary_fresh")
        expect(rc_p == 0, "main() should exit 0 for the pending wiring run", errors)
        expect(fresh_main_p is not None and "depth=owner_gated_depth_no_approval" in fresh_main_p["rationale"], "a missing --owner-decisions record must keep build_payload on the pending path", errors)
        expect(window_main_p["telemetry_context"]["token_depth"]["retired_by_owner_decision"] is False and window_main_p["telemetry_context"]["token_depth"]["owner_gated"] is True, "a missing --owner-decisions record must keep the window summary on the pending path", errors)

    if errors:
        print("otel_ops_control_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("otel_ops_control_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
