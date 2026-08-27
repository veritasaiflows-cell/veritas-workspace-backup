#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf74_self_audit_cadence_packet as packet


def write_json(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def source_paths(root: Path, auto_apply_count: int = 0) -> dict[str, Path]:
    return {
        "wf74_opportunity_queue": write_json(root, "queue.json", {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "opportunity_count": 2,
                "top_opportunity_id": "workflow_maturity-6fe5f34dc7fc",
            },
        }),
        "wf74_auto_patch_proposer": write_json(root, "auto-patch.json", {
            "status": "ok",
            "validation": {"status": "ok"},
            "summary": {
                "auto_apply_count": auto_apply_count,
                "auto_apply_candidate_count": 0,
                "owner_gated_plan_count": 2,
                "skill_workshop_request_count": 0,
            },
        }),
        "improvement_ledger": write_json(root, "improvement-ledger.json", {
            "status": "warning",
            "validation": {"status": "warning"},
            "summary": {
                "followup_required_open_count": 1,
                "top_improvement_sla_status": "overdue",
            },
        }),
        "model_quality_scorecard": write_json(root, "scorecard.json", {
            "status": "scaffold_active",
            "validation": {"status": "ok"},
            "active_tracks": ["implementation_quality", "performance", "learning_capture", "decision_quality"],
            "tracks": {
                "implementation_quality": {"metrics": {"validator_pass_rate": 1.0}},
                "performance": {"summary": "source present but metric map not wired"},
                "learning_capture": {"metrics": {"row_count": 10}},
                "decision_quality": {"metrics": {"scorecard_active_now": True}},
            },
        }),
        "otel_learning_loop": write_json(root, "otel-learning.json", {
            "status": "ok",
            "validation": {"status": "ok"},
        }),
        "otel_runtime_metadata_probe": write_json(root, "otel-probe.json", {
            "status": "warning",
            "validation": {"status": "ok"},
            "summary": {
                "runtime_metadata_observed": False,
                "metadata_depth_approved_enabled": True,
                "enabled_vs_observed_reconciliation": "approved_enabled_not_observed",
                "emission_path_diagnosis": "collector_debug_log_stale_no_current_runtime_metadata_source",
                "collector_log_age_hours": 169.56,
            },
        }),
        "implementation_token_bridge": write_json(root, "token-bridge.json", {
            "status": "warning",
            "validation": {"status": "warning"},
            "summary": {
                "implementation_token_gap_count": 347,
                "unclassified_supported_runtime_gap_count": 97,
                "gap_resolution_status": "stamp_required",
            },
        }),
        "finance_recommendation_ledger": write_json(root, "finance-recs.json", {
            "status": "warning",
            "validation": {"status": "warning"},
            "summary": {
                "metric_scope": "current_capital_recommendation_process_correctness",
                "capital_recommendation_later_outcome_graded_rows": 0,
                "durable_recommendation_later_outcome_graded_rows": 43,
            },
        }),
        "wf88_control_packet": write_json(root, "wf88.json", {
            "status": "control_packet_warning_no_apply_authority",
            "validation": {"status": "ok"},
            "summary": {
                "recommendation_later_outcome_metric_scope": "durable_recommendation_outcome_ledger_max_of_preview_durable_and_grade_history",
                "recommendation_current_preview_later_outcome_graded_rows": 0,
                "recommendation_durable_later_outcome_graded_rows": 43,
            },
        }),
        "wf88_wiki_synthesis": write_json(root, "wiki.json", {
            "status": "wiki_synthesis_warning_no_apply_authority",
            "validation": {"status": "warning"},
        }),
    }


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_packet_routes_current_measurement_gaps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = packet.build_packet(source_paths(Path(tmp)))
    summary = payload["summary"]
    warnings = set(payload["validation"]["warnings"])
    actions = {item["id"]: item for item in payload["action_items"]}
    expect(payload["validation"]["status"] == "warning", "expected warning-grade packet")
    expect(summary["cadence_codified"] is True, "cadence should be codified")
    expect(summary["auto_apply_count"] == 0, "auto-apply should remain zero")
    expect(summary["performance_metric_count"] == 0, "performance metric gap should be visible")
    expect(summary["unclassified_supported_runtime_gap_count"] == 97, "token gap should be visible")
    expect(summary["followup_required_open_count"] == 1, "ledger follow-up should be visible")
    expect(summary["otel_enabled_vs_observed_reconciliation"] == "approved_enabled_not_observed", "OTEL reconciliation missing")
    expect(summary["otel_emission_path_diagnosis"] == "collector_debug_log_stale_no_current_runtime_metadata_source", "OTEL emission diagnosis missing")
    expect(summary["otel_collector_log_age_hours"] == 169.56, "OTEL collector log age missing")
    expect(actions["close-implementation-token-attribution-gap"]["state"] == "fix_now", "token gap should be fix_now")
    expect(actions["route-overdue-improvement-followup"]["state"] == "fix_now", "overdue follow-up should be fix_now")
    expect("collector_debug_log_stale_no_current_runtime_metadata_source" in actions["reconcile-otel-approved-vs-observed"]["signal"], "OTEL action signal should carry emission diagnosis")
    expect("unclassified_supported_runtime_gap_count:97" in warnings, "token warning missing")
    expect("followup_required_open_count:1" in warnings, "follow-up warning missing")
    expect("otel_depth_enabled_but_runtime_metadata_not_observed" in warnings, "OTEL warning missing")
    expect("otel_runtime_metadata_source_stale" in warnings, "OTEL stale source warning missing")
    expect("performance_scorecard_metric_count_zero" in warnings, "performance warning missing")


def test_packet_blocks_nonzero_auto_apply() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = packet.build_packet(source_paths(Path(tmp), auto_apply_count=1))
    expect(payload["validation"]["status"] == "error", "nonzero auto-apply must error")
    expect("auto_apply_count_nonzero" in payload["validation"]["errors"], "auto-apply error missing")
    actions = {item["id"]: item for item in payload["action_items"]}
    expect(actions["preserve-zero-auto-apply"]["state"] == "hard_stop", "nonzero auto-apply must be hard_stop")


def main() -> None:
    test_packet_routes_current_measurement_gaps()
    test_packet_blocks_nonzero_auto_apply()
    print("wf74 self-audit cadence packet tests passed")


if __name__ == "__main__":
    main()
