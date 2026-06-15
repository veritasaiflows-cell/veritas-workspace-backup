#!/usr/bin/env python3
"""Targeted tests for the WF74 OTEL critical-review decision packet."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import otel_critical_review_decision_packet as packet_script


def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def field_packet() -> dict:
    return {
        "schema": "veritas.otel_field_depth_limited_owner_packet.v1",
        "generated_at_utc": stamp(),
        "status": "owner_decision_required",
        "current_collector_posture": {
            "present": True,
            "path": "tools/otelcol/openclaw-local-otel.yaml",
            "has_debug_exporter": True,
            "debug_verbosity_basic": True,
            "has_file_exporter": False,
            "has_logs_pipeline": False,
            "binds_loopback_4318": True,
        },
        "current_24h_summary": {"event_count": 100, "by_severity": {"info": 100}},
        "current_drift_summary": {
            "status": "review",
            "daily_warning_or_error_count": 0,
            "daily_vs_weekly_event_rate_ratio": 2.8,
            "drift_reasons": ["daily_event_rate_deviates_from_weekly_baseline"],
        },
        "proposed_change_if_approved_later": {
            "collector_config": "tools/otelcol/openclaw-local-otel.yaml",
            "candidate_capability": "file exporter and logs pipeline or equivalent bounded local receiver",
            "required_scope": "local-only, metadata-only, no raw prompt/response/tool payload/system prompt/secrets/headers",
            "required_review": "owner approval plus config diff, rollback, privacy scan, and post-change OTEL validation",
        },
        "authority_boundary": {
            "review_only": True,
            "local_only": True,
            "collector_config_mutation_allowed": False,
            "runtime_config_mutation_allowed": False,
            "external_export_allowed": False,
            "prompt_response_tool_content_capture_allowed": False,
            "owner_approval_inferred": False,
        },
        "blocked_now": ["no collector config mutation"],
        "next_safe_action": "Use this as the owner-review packet if deeper OTEL field capture is worth approving later.",
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def otel_ops_packet() -> dict:
    return {
        "schema": "veritas.otel_ops_control.v1",
        "generated_at_utc": stamp(),
        "status": "ok",
        "collector_health": {"status": "ok", "host": "127.0.0.1", "port": 4318, "listening": True},
        "collector_config": {
            "present": True,
            "path": "tools/otelcol/openclaw-local-otel.yaml",
            "has_debug_exporter": True,
            "debug_verbosity_basic": True,
            "has_file_exporter": False,
            "has_logs_pipeline": False,
            "binds_loopback_4318": True,
        },
        "drift": {
            "status": "review",
            "daily_warning_or_error_count": 0,
            "daily_vs_weekly_event_rate_ratio": 2.8,
            "drift_reasons": ["daily_event_rate_deviates_from_weekly_baseline"],
        },
        "field_inventory": {
            "available_now": ["collector endpoint health"],
            "not_available_from_basic_debug_log": ["model/provider name", "token usage"],
        },
        "actions": [{"id": "otel_operational_drift_review", "severity": "warning", "status": "review"}],
        "authority_boundary": {
            "review_only": True,
            "local_only": True,
            "external_export_allowed": False,
            "collector_config_mutation_allowed": False,
            "runtime_config_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def run_packet(td: Path, extra: list[str] | None = None, expected_rc: int = 0) -> dict:
    out = td / "decision.json"
    md = td / "decision.md"
    args = [
        "--field-packet",
        str(td / "field.json"),
        "--otel-ops",
        str(td / "otel.json"),
        "--critical-loop",
        str(td / "missing-loop.json"),
        "--json-out",
        str(out),
        "--md-out",
        str(md),
        "--write",
        "--write-md",
        "--validate",
    ]
    if extra:
        args.extend(extra)
    rc = packet_script.main(args)
    assert rc == expected_rc
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        write(td / "field.json", field_packet())
        write(td / "otel.json", otel_ops_packet())

        packet = run_packet(td)
        assert packet["schema"] == packet_script.SCHEMA
        assert packet["status"] == "ok", packet
        assert packet["severity"] == "warning", packet
        assert packet["decision"]["recommended_decision"] == "review", packet
        assert packet["decision"]["owner_decision_required"] is True
        assert packet["decision"]["owner_decision_today"] == "yes_review_only"
        assert packet["privacy_risk"]["level"] == "elevated"
        assert packet["config_change_requirement"]["required_for_approval"] is True
        assert packet["config_change_requirement"]["approved_by_this_packet"] is False
        assert packet["rollback_requirement"]["required_for_approval"] is True
        assert "no telemetry capture-depth expansion" in packet["blocked_actions"]
        assert packet_script.authority_clean(packet["authority_boundary"])
        assert packet["digest_context"]["severity"] == "warning"
        assert packet["validation"]["status"] == "ok"
        assert (td / "decision.md").read_text(encoding="utf-8").startswith("# OTEL Critical Review Decision Packet")

        loop = {"severity": "critical", "recommended_decision": "monitor", "persistence": "repeated_for_two_windows"}
        write(td / "loop.json", loop)
        packet = run_packet(td, ["--critical-loop", str(td / "loop.json")])
        assert packet["severity"] == "critical", packet
        assert packet["persistence"] == "repeated_for_two_windows"
        assert packet["decision"]["recommended_decision"] == "monitor"

        bad_field = field_packet()
        bad_field["authority_boundary"]["collector_config_mutation_allowed"] = True
        write(td / "field.json", bad_field)
        blocked = run_packet(td, expected_rc=1)
        assert blocked["status"] == "blocked", blocked
        assert "field_depth_authority_boundary_regression" in blocked["validation"]["errors"]

    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        write(td / "otel.json", otel_ops_packet())
        missing = run_packet(td, expected_rc=1)
        assert missing["decision"]["recommended_decision"] == "wait", missing
        assert "missing_or_unparseable_field_depth_packet" in missing["validation"]["errors"]

    print("otel_critical_review_decision_packet targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
