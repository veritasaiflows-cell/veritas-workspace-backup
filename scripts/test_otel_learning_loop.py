from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import otel_learning_loop as loop

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "otel_learning_loop.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_uncredited_lane_and_missing_duration_do_not_pollute_model_metrics() -> None:
    summary = loop.model_cost_summary({
        "rows": [
            {
                "producer": "concurrent_lane_manager",
                "model_path": "openai/gpt-5.6-terra",
                "status": "complete",
                "duration_ms": 10,
                "tokens": 9999,
                "cost": 9.99,
                "attribution": {
                    "model_present": True,
                    "model_applicable": False,
                    "telemetry_eligible": False,
                },
            },
            {
                "producer": "openclaw_cron_runs",
                "model_path": "openai/gpt-5.6-terra",
                "status": "ok",
                "duration_ms": 1000,
                "tokens": 100,
                "cost": 0.01,
                "attribution": {
                    "model_present": True,
                    "model_applicable": True,
                    "telemetry_eligible": True,
                },
            },
            {
                "producer": "openclaw_cron_runs",
                "model_path": "openai/gpt-5.6-terra",
                "status": "ok",
                "duration_ms": None,
                "tokens": 100,
                "cost": 0.01,
                "attribution": {
                    "model_present": True,
                    "model_applicable": True,
                    "telemetry_eligible": True,
                },
            },
        ]
    })
    assert summary["model_performance_eligible_rows"] == 2
    assert summary["uncredited_lane_audit_rows"] == 1
    assert summary["avg_duration_ms"] == 1000.0
    bucket = summary["by_model"]["openai/gpt-5.6-terra"]
    assert bucket["count"] == 2
    assert bucket["duration_covered_rows"] == 1
    assert bucket["avg_duration_ms"] == 1000.0

    tool_summary = loop.tool_latency_summary(
        {"rows": [
            {"tool_name": "missing", "duration_ms": None, "failure_category": "none"},
            {"tool_name": "measured", "duration_ms": 125, "failure_category": "none"},
        ]},
        {},
        {},
    )
    assert tool_summary["duration_covered_rows"] == 1
    assert tool_summary["slowest_tools"] == [{"tool_name": "measured", "count": 1, "avg_duration_ms": 125.0, "failure_rows": 0}]


def test_owner_decision_record_suppresses_retired_recommendation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        record = Path(tmp) / "otel-recommendations.json"
        record.write_text(json.dumps({
            "schema": "veritas.owner_decisions.otel_recommendations.v1",
            "decisions": [{
                "id": "token_cost_metadata_depth",
                "decision": "decline_and_retire_the_recommendation",
                "decided_by": "randall",
                "decided_at_utc": "2026-09-12T16:00:00+00:00",
                "evidence": "tmp/otel-token-cost-metadata-depth-owner-packet.json",
            }],
        }), encoding="utf-8")
        original = loop.OWNER_DECISIONS
        try:
            loop.OWNER_DECISIONS = record
            suppressed = loop.owner_decision_suppressions()
            assert "token_cost_metadata_depth" in suppressed
            assert suppressed["token_cost_metadata_depth"]["decided_by"] == "randall"
            loop.OWNER_DECISIONS = Path(tmp) / "missing.json"
            assert loop.owner_decision_suppressions() == {}
        finally:
            loop.OWNER_DECISIONS = original


def _attribution_bridge_doc(summary, generated_at_utc, status="warning", validation=None):
    doc = {
        "schema": "veritas.implementation_token_attribution_bridge.v1",
        "status": status,
        "generated_at_utc": generated_at_utc,
        "validation": {"status": "warning", "errors": [], "warnings": ["implementation_token_gap_count:597"]},
        "summary": summary,
    }
    if validation is not None:
        doc["validation"] = validation
    return doc


def _attribution_timestamp(hours_from_now):
    point = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    return point.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _terminal_summary():
    return {"action_required_supported_runtime_gap_count": 0, "gap_resolution_status": "terminal_unavailable_only", "closeout_enforcement_required": False}


def test_attribution_action_state_is_fail_closed() -> None:
    fresh = _attribution_timestamp(0)
    clean = loop.attribution_action_state({}, _attribution_bridge_doc(_terminal_summary(), fresh))
    assert clean["state"] == "monitor_only"
    assert clean["reason"] == "explicit_terminal_or_historical_only"
    assert clean["closeout_enforcement_required"] is False
    assert clean["action_required_supported_runtime_gap_count"] == 0
    live_summary = {"action_required_supported_runtime_gap_count": 2, "gap_resolution_status": "stamp_required", "closeout_enforcement_required": True}
    live = loop.attribution_action_state({}, _attribution_bridge_doc(live_summary, fresh))
    assert live["state"] == "action_required"
    stale_doc = _attribution_bridge_doc(_terminal_summary(), _attribution_timestamp(-25))
    with tempfile.TemporaryDirectory() as tmp:
        touched = Path(tmp) / "bridge.json"
        touched.write_text(json.dumps(stale_doc), encoding="utf-8")
        os.utime(touched, None)
        reloaded = json.loads(touched.read_text(encoding="utf-8"))
    assert loop.attribution_action_state({}, reloaded)["state"] == "unknown"
    assert loop.attribution_action_state({}, _attribution_bridge_doc(_terminal_summary(), _attribution_timestamp(2)))["state"] == "unknown"
    for bad_count in (-1, 0.5, True, "3", None):
        summary = {"action_required_supported_runtime_gap_count": bad_count, "gap_resolution_status": "terminal_unavailable_only", "closeout_enforcement_required": False}
        assert loop.attribution_action_state({}, _attribution_bridge_doc(summary, fresh))["state"] == "unknown"
    missing_closeout = {"action_required_supported_runtime_gap_count": 0, "gap_resolution_status": "terminal_unavailable_only"}
    assert loop.attribution_action_state({}, _attribution_bridge_doc(missing_closeout, fresh))["state"] == "unknown"
    mystery = {"action_required_supported_runtime_gap_count": 0, "gap_resolution_status": "mystery_status", "closeout_enforcement_required": False}
    assert loop.attribution_action_state({}, _attribution_bridge_doc(mystery, fresh))["state"] == "unknown"
    assert loop.attribution_action_state({}, _attribution_bridge_doc(_terminal_summary(), fresh, status="blocked"))["state"] == "unknown"
    blocked_validation = {"status": "blocked", "errors": ["blocked"], "warnings": []}
    assert loop.attribution_action_state({}, _attribution_bridge_doc(_terminal_summary(), fresh, validation=blocked_validation))["state"] == "unknown"
    error_validation = {"status": "warning", "errors": ["boom"], "warnings": []}
    assert loop.attribution_action_state({}, _attribution_bridge_doc(_terminal_summary(), fresh, validation=error_validation))["state"] == "unknown"
    conflict_summary = {"action_required_supported_runtime_gap_count": 4, "gap_resolution_status": "terminal_unavailable_only", "closeout_enforcement_required": False}
    assert loop.attribution_action_state({}, _attribution_bridge_doc(conflict_summary, fresh))["state"] == "unknown"
    lone_stamp = {"action_required_supported_runtime_gap_count": 0, "gap_resolution_status": "stamp_required", "closeout_enforcement_required": False}
    assert loop.attribution_action_state({}, _attribution_bridge_doc(lone_stamp, fresh))["state"] == "unknown"
    wrong_schema = _attribution_bridge_doc(_terminal_summary(), fresh)
    wrong_schema["schema"] = "wrong.schema.v1"
    assert loop.attribution_action_state({}, wrong_schema)["state"] == "unknown"
    assert loop.attribution_action_state({}, {})["state"] == "unknown"


def test_usage_source_recommendation_follows_bridge_state() -> None:
    cost = {"uncredited_lane_audit_rows": 5}
    fresh = _attribution_timestamp(0)
    live_bridge = _attribution_bridge_doc({"action_required_supported_runtime_gap_count": 2, "gap_resolution_status": "stamp_required", "closeout_enforcement_required": True}, fresh)
    historical_bridge = _attribution_bridge_doc(_terminal_summary(), fresh)
    live_recs = loop.build_recommendations(cost, {}, {}, {}, {}, {}, live_bridge)
    assert any(item.get("id") == "usage_source_reverification_required" and item.get("severity") == "warning" for item in live_recs)
    assert not any(item.get("id") == "historical_attribution_claim_limits" for item in live_recs)
    historical_recs = loop.build_recommendations(cost, {}, {}, {}, {}, {}, historical_bridge)
    assert not any(item.get("id") == "usage_source_reverification_required" for item in historical_recs)
    assert any(item.get("id") == "historical_attribution_claim_limits" and item.get("severity") == "info" for item in historical_recs)
    unknown_recs = loop.build_recommendations(cost, {}, {}, {}, {}, {}, {})
    assert any(item.get("id") == "usage_source_reverification_required" and item.get("severity") == "warning" for item in unknown_recs)
    assert not any(item.get("id") == "historical_attribution_claim_limits" for item in unknown_recs)
    clean_recs = loop.build_recommendations({"uncredited_lane_audit_rows": 0}, {}, {}, {}, {}, {}, historical_bridge)
    assert not any(item.get("id") in {"usage_source_reverification_required", "historical_attribution_claim_limits"} for item in clean_recs)
    zero_counter_live_recs = loop.build_recommendations({"uncredited_lane_audit_rows": 0}, {}, {}, {}, {}, {}, live_bridge)
    assert any(item.get("id") == "usage_source_reverification_required" for item in zero_counter_live_recs)


def main() -> int:
    errors: list[str] = []
    try:
        test_uncredited_lane_and_missing_duration_do_not_pollute_model_metrics()
    except AssertionError as exc:
        errors.append(f"telemetry eligibility regression failed: {exc}")
    try:
        test_owner_decision_record_suppresses_retired_recommendation()
    except AssertionError as exc:
        errors.append(f"owner-decision suppression regression failed: {exc}")
    try:
        test_attribution_action_state_is_fail_closed()
    except AssertionError as exc:
        errors.append(f"attribution fail-closed regression failed: {exc}")
    try:
        test_usage_source_recommendation_follows_bridge_state()
    except AssertionError as exc:
        errors.append(f"usage-source bridge-state regression failed: {exc}")
    out = ROOT / "tmp" / "test-otel-learning-loop.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json-out", str(out), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    expect(result.returncode == 0, f"script failed: {result.stdout} {result.stderr}", errors)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expect(payload.get("schema") == "veritas.otel_learning_loop.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") == "ok", "validation should be ok", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "system_prompt_capture_allowed",
        "secret_or_header_capture_allowed",
        "content_capture_allowed",
        "external_export_allowed",
        "collector_config_mutation_allowed",
        "runtime_config_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    blocked = payload.get("redaction_policy", {}).get("blocked", [])
    expect("raw prompts" in blocked, "raw prompts must be blocked", errors)
    expect("system prompts" in blocked, "system prompts must be blocked", errors)
    recommendations = payload.get("recommendations", [])
    expect(any(item.get("id") == "content_capture_boundary" for item in recommendations), "content boundary recommendation missing", errors)
    carry_forward = payload.get("carry_forward_contract", {})
    expect(carry_forward.get("status") in {"ok", "attention", "ready", "warning"}, "carry-forward contract missing readiness", errors)
    expect("tmp/future-session-enhancement-packet.json" in carry_forward.get("must_surface_in", []), "future session carry-forward surface missing", errors)
    auto_router = payload.get("auto_implementation_router", {})
    expect(auto_router.get("status") == "gated_auto_route_no_auto_apply", "auto implementation router must stay gated", errors)
    expect(auto_router.get("auto_apply_allowed") is False, "auto implementation router must not allow auto apply", errors)
    blocked_auto = auto_router.get("blocked_actions", [])
    expect(any("direct code mutation from OTEL signals" in str(item) for item in blocked_auto), "direct OTEL code mutation must be blocked", errors)
    parallel = payload.get("parallel_execution_plan", [])
    expect({row.get("stream") for row in parallel} >= {"A", "B", "C", "D", "E"}, "parallel execution streams missing", errors)
    review_loop = payload.get("review_loop", {})
    expect("daily_evening_alert" in review_loop, "daily evening alert review loop missing", errors)
    summaries = payload.get("learning_summaries", {})
    friction = summaries.get("operational_friction", {})
    expect("cron" in friction, "cron friction summary missing", errors)
    expect("workflow_advancement" in friction, "workflow advancement friction summary missing", errors)
    serialized = json.dumps(payload).lower()
    for retired_marker in ("wf67", "wf87", "paper-autotrader", "would_buy", "autonomous_paper_buy", "trade-grade"):
        expect(retired_marker not in serialized, f"retired finance residue present: {retired_marker}", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: otel learning loop is metadata-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
