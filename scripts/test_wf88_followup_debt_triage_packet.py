from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_followup_debt_triage_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_followup_debt_triage_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.OUT = module.TMP / "wf88-followup-debt-triage-packet.json"
    module.MD_OUT = module.TMP / "wf88-followup-debt-triage-packet.md"
    module.IMPROVEMENT_LEDGER = module.TMP / "improvement-ledger-current.json"
    module.WF74_ROUTER = module.TMP / "wf74-autonomy-work-router.json"
    module.WF74_DOCKET = module.TMP / "wf74-decision-docket.json"
    module.CRON_CONTROL = module.TMP / "cron-control-packet.json"
    module.OTEL_OPS = module.TMP / "otel-ops-control.json"
    module.WF74_RUNNER = module.TMP / "wf74-model-quality-collection-cron-runner.json"
    module.FINANCE_RESPONSE_QUALITY_SLICE = module.TMP / "finance-response-quality-slice.json"
    module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP = module.TMP / "finance-response-quality-repair-loop.json"
    module.WF85_SOURCE_OPEN_RECONCILIATION = module.TMP / "wf85-source-open-reconciliation-contract.json"
    module.WORKFLOW_FOLLOWUPS = module.TMP / "workflow-blocker-followups.json"
    module.WF87_ROLLUP = module.TMP / "wf87-v2-readiness-rollup.json"
    module.AUTONOMY_SPINE = module.TMP / "autonomy-spine-readiness-rollup.json"
    module.VALIDATOR_TIMING = module.TMP / "validator-timing-ledger.json"
    module.WF88_OS2_CONTROL = module.TMP / "wf88-os2-control-packet.json"
    module.IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE = module.TMP / "implementation-token-attribution-bridge.json"
    generated = module.utc_now()

    followups = [
        {"source_type": "wf74_improvement_opportunity", "source_key": "cron_migration-a", "title": "Route blocked cron signals into a migration-ready repair plan", "category": "cron_migration", "priority": 92, "decision": "follow_up_required_before_closure"},
        {"source_type": "wf74_improvement_opportunity", "source_key": "collector_config-a", "title": "Review OTEL event-rate drift against the weekly baseline", "category": "collector_config", "priority": 88, "decision": "follow_up_required_before_closure"},
        {"source_type": "wf74_improvement_opportunity", "source_key": "outcome_measurement-a", "title": "Track WF87 shadow outcomes until regular-session follow-up thresholds are met", "category": "outcome_measurement", "priority": 84, "decision": "follow_up_required_before_closure"},
        {"source_type": "wf74_improvement_opportunity", "source_key": "planning_quality-a", "title": "Measure and close planning follow-through gaps", "category": "planning_quality", "priority": 80, "decision": "follow_up_required_before_closure"},
        {"source_type": "wf74_improvement_opportunity", "source_key": "code_mutation-a", "title": "Reduce validator drag for normal implementation passes", "category": "code_mutation", "priority": 72, "decision": "follow_up_required_before_closure"},
        {"source_type": "wf74_improvement_opportunity", "source_key": "finance_mutation-a", "title": "Clear finance response quality source-open blockers so WF74 scorecard can pass", "category": "finance_mutation", "priority": 96, "decision": "follow_up_required_before_closure"},
        {"source_type": "otel_learning_loop_recommendation", "source_key": "wf74_queue_followup", "title": "wf74_queue_followup", "category": "otel_learning_loop", "priority": 55, "decision": "follow_up_required_before_closure"},
    ]
    write_json(module.IMPROVEMENT_LEDGER, {"status": "warning", "generated_at_utc": generated, "followup_required_improvements": followups, "validation": {"status": "warning"}})
    write_json(module.WF74_ROUTER, {"status": "ok", "generated_at_utc": generated, "summary": {"open_unrouted_recommendation_count": 0, "recommendation_to_route_conversion_rate": 1.0, "pm_job_candidate_count": 3, "planning_followthrough_gap_count": 0, "planning_followthrough_clean_rate": 1.0}, "validation": {"status": "ok"}})
    write_json(module.WF74_DOCKET, {"status": "ok", "generated_at_utc": generated, "validation": {"status": "ok"}})
    write_json(module.CRON_CONTROL, {"status": "ok", "generated_at_utc": generated, "summary": {"blocked_count": 1, "escalation_signal_count": 1, "should_wake_main_session": True}, "validation": {"status": "ok"}})
    write_json(module.OTEL_OPS, {"status": "blocked", "generated_at_utc": generated, "summary": {"event_count": 0}, "drift": {"daily_warning_or_error_count": 0, "daily_vs_weekly_event_rate_ratio": 0.0}, "validation": {"status": "blocked"}})
    write_json(module.WF74_RUNNER, {"status": "ok", "generated_at_utc": generated, "summary": {"coding_runtime_validator_elapsed_seconds": 3.2, "planning_quality_followthrough_gap_count": 0, "steps_blocked": 0, "finance_response_quality_status": "ok", "finance_response_quality_source_open_blocked_count": 0, "finance_response_quality_source_freshness_blocked_count": 0, "finance_response_quality_remediation_tracks_needing_repair": 0}, "validation": {"status": "warning"}})
    write_json(module.FINANCE_RESPONSE_QUALITY_SLICE, {"schema": "veritas.finance_response_quality_slice.v1", "status": "ok", "generated_at_utc": generated, "summary": {"blocked_archetype_count": 0, "source_open_blocked_count": 0, "source_freshness_blocked_count": 0, "remediation_tracks_needing_repair": 0}, "validation": {"status": "ok", "errors": [], "warnings": []}})
    write_json(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP, {"schema": "veritas.finance_response_quality_repair_loop.v1", "status": "noop_ok", "generated_at_utc": generated, "summary": {"proposal_count": 0, "high_priority_count": 0, "source_open_blocked_count": 0, "source_freshness_blocked_count": 0, "remediation_tracks_needing_repair": 0}, "validation": {"status": "warning", "errors": [], "warnings": ["no_repair_proposals_generated"]}})
    write_json(module.WF85_SOURCE_OPEN_RECONCILIATION, {"schema": "veritas.wf85_source_open_reconciliation_contract.v1", "status": "ok", "generated_at_utc": generated, "summary": {"fresh_verified_source_count": 300, "unnecessary_source_open_blocker_count": 0, "wrong_source_open_blocker_reason_count": 0, "mismatch_error_count": 0, "producer_order_error_count": 0}, "validation": {"status": "ok", "errors": [], "warnings": []}})
    write_json(module.WORKFLOW_FOLLOWUPS, {"status": "ok", "generated_at_utc": generated, "followups": [{"route": "cron_migration", "followup_id": "cron-cron-migration"}], "validation": {"status": "ok"}})
    write_json(module.WF87_ROLLUP, {"status": "phase_a_hardening_implemented_runtime_blocked", "generated_at_utc": generated, "shadow_threshold": {"threshold_met": True}, "shadow_outcome_calibration": {"pending_regular_session_followup_count": 0, "decision_quality_claim_allowed_now": False, "model_performance_claim_allowed_now": False}, "validation": {"status": "ok"}})
    write_json(module.AUTONOMY_SPINE, {"status": "ok", "generated_at_utc": generated, "summary": {"final_state": "continue_accrual"}, "validation": {"status": "warning"}})
    write_json(module.VALIDATOR_TIMING, {"status": "ok", "generated_at_utc": generated, "validation": {"status": "ok"}})
    write_json(module.IMPLEMENTATION_TOKEN_ATTRIBUTION_BRIDGE, {"schema": "veritas.implementation_token_attribution_bridge.v1", "status": "warning", "generated_at_utc": generated, "summary": {"action_required_supported_runtime_gap_count": 0, "post_cutoff_supported_unresolved_gap_count": 0, "unknown_completion_supported_unresolved_gap_count": 0, "gap_resolution_status": "terminal_unavailable_only"}, "validation": {"status": "warning", "errors": [], "warnings": ["terminal_only"]}})
    write_json(module.WF88_OS2_CONTROL, {
        "status": "control_packet_warning_no_apply_authority",
        "generated_at_utc": generated,
        "canonical_action_state": [
            {"id": "wf88-learning-loop-measurement", "owner_workflow": "WF88", "state": "measure_not_claim"},
            {"id": "improvement-ledger-open-followups", "owner_workflow": "WF88", "state": "followup_required"},
            {"id": "wf85-source-open-repair-queue", "owner_workflow": "WF85", "state": "repair_queue"},
        ],
        "validation": {"status": "warning"},
    })


def test_followup_debt_triage_closes_only_proven_rows() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "warning"
        assert packet["summary"]["followup_input_count"] == 7
        assert packet["summary"]["closure_allowed_count"] == 5
        assert packet["summary"]["kept_open_count"] == 2
        assert packet["authority_boundary"]["cron_schedule_mutation_allowed"] is False
        assert packet["authority_boundary"]["finance_canon_or_portfolio_mutation_allowed"] is False

        closures = {row["source_key"]: row for row in packet["closure_items"]}
        assert closures["outcome_measurement-a"]["closure_status"] == "verified_fix"
        assert closures["planning_quality-a"]["closure_status"] == "verified_fix"
        assert closures["code_mutation-a"]["closure_status"] == "monitor_only_drift_currently_absent"
        assert closures["finance_mutation-a"]["closure_status"] == "verified_fix"
        assert closures["finance_mutation-a"]["action_state"] == "close_with_finance_response_quality_clean_proof"
        assert closures["finance_mutation-a"]["successor_id"] == "wf85-source-open-repair-queue"
        assert closures["finance_mutation-a"]["successor_artifact"] == "tmp/wf88-os2-control-packet.json"
        assert closures["wf74_queue_followup"]["closure_status"] == "verified_fix"
        assert closures["wf74_queue_followup"]["successor_artifact"] == "tmp/wf88-os2-control-packet.json"

        kept = {row["source_key"]: row for row in packet["active_followup_items"]}
        assert kept["cron_migration-a"]["action_state"] == "active_successor_followup"
        assert kept["collector_config-a"]["action_state"] == "active_operational_drift_review"


def test_cron_followup_becomes_monitor_only_when_cron_control_is_green() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        write_json(module.CRON_CONTROL, {
            "status": "ok",
            "generated_at_utc": module.utc_now(),
            "summary": {
                "blocked_count": 0,
                "escalation_signal_count": 0,
                "should_wake_main_session": False,
            },
            "validation": {"status": "ok"},
        })
        packet = module.build_packet()

        kept = {row["source_key"]: row for row in packet["active_followup_items"]}
        cron = kept["cron_migration-a"]
        assert cron["action_state"] == "monitor_only"
        assert "Monitor only; cron control is green" in cron["recommended_next_action"]
        assert cron["context"]["cron_blocked_count"] == 0
        assert cron["context"]["cron_escalation_signal_count"] == 0


def test_collector_followup_becomes_monitor_only_when_otel_ops_is_clean() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        write_json(module.OTEL_OPS, {
            "status": "ok",
            "generated_at_utc": module.utc_now(),
            "summary": {"event_count": 144},
            "drift": {
                "status": "ok",
                "daily_warning_or_error_count": 0,
                "daily_vs_weekly_event_rate_ratio": 1.0,
            },
            "validation": {"status": "ok"},
        })
        packet = module.build_packet()

        kept = {row["source_key"]: row for row in packet["active_followup_items"]}
        collector = kept["collector_config-a"]
        assert collector["action_state"] == "monitor_only"
        assert "Monitor only; OTEL ops is current" in collector["recommended_next_action"]
        assert collector["context"]["otel_status"] == "ok"
        assert collector["context"]["daily_warning_or_error_count"] == 0
        assert collector["context"]["event_count_24h"] == 144


def test_duplicate_operational_followups_close_as_superseded() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        ledger = json.loads(module.IMPROVEMENT_LEDGER.read_text(encoding="utf-8"))
        ledger["followup_required_improvements"].extend([
            {
                "source_type": "wf74_improvement_opportunity",
                "source_key": "cron_migration-b",
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "category": "cron_migration",
                "priority": 78,
                "decision": "follow_up_required_before_closure",
            },
            {
                "source_type": "wf74_improvement_opportunity",
                "source_key": "collector_config-b",
                "title": "Review OTEL event-rate drift against the weekly baseline",
                "category": "collector_config",
                "priority": 64,
                "decision": "follow_up_required_before_closure",
            },
        ])
        write_json(module.IMPROVEMENT_LEDGER, ledger)

        packet = module.build_packet()

        assert packet["validation"]["status"] == "warning"
        assert packet["summary"]["duplicate_followup_closed_count"] == 2
        assert packet["summary"]["closure_allowed_count"] == 7
        assert packet["summary"]["kept_open_count"] == 2
        closures = {row["source_key"]: row for row in packet["closure_items"]}
        assert closures["cron_migration-b"]["closure_status"] == "superseded_by_open_improvement"
        assert closures["collector_config-b"]["closure_status"] == "superseded_by_open_improvement"
        assert closures["cron_migration-b"]["successor_artifact"] == "tmp/improvement-ledger-current.json"
        assert closures["collector_config-b"]["successor_artifact"] == "tmp/improvement-ledger-current.json"
        kept = {row["source_key"]: row for row in packet["active_followup_items"]}
        assert kept["cron_migration-a"]["action_state"] == "active_successor_followup"
        assert kept["collector_config-a"]["action_state"] == "active_operational_drift_review"


def test_obsolete_wf85_blocked_packet_cannot_stop_or_decide_closure() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        wf85 = json.loads(module.WF85_SOURCE_OPEN_RECONCILIATION.read_text(encoding="utf-8"))
        wf85["status"] = "blocked"
        wf85["generated_at_utc"] = "2026-08-29T21:46:26Z"
        wf85["summary"]["unnecessary_source_open_blocker_count"] = 9
        wf85["summary"]["mismatch_error_count"] = 9
        wf85["summary"]["fresh_verified_source_count"] = 0
        wf85["validation"] = {"status": "blocked", "errors": ["source_gate_card_full_answer_counts_zero"], "warnings": []}
        write_json(module.WF85_SOURCE_OPEN_RECONCILIATION, wf85)

        packet = module.build_packet()

        assert "wf85_source_open_reconciliation" not in packet["source_status"]
        closures = {row["source_key"]: row for row in packet["closure_items"]}
        finance = closures["finance_mutation-a"]
        assert finance["closure_allowed"] is True
        assert finance["closure_status"] == "verified_fix"
        assert finance["action_state"] == "close_with_finance_response_quality_clean_proof"
        assert all("wf85" not in str(artifact).lower() for artifact in finance["proof_artifacts"])
        assert not any("wf85" in str(key).lower() for key in finance["context"])
        assert "wf85" not in finance["closure_reason"].lower()


def test_followup_debt_triage_blocks_invalid_closure_status() -> None:
    module = load_module()
    packet = {
        "authority_boundary": dict(module.AUTHORITY_BOUNDARY),
        "source_status": {"improvement_ledger": {"present": True}},
        "triage_items": [{
            "source_key": "bad",
            "category": "planning_quality",
            "closure_allowed": True,
            "closure_status": "not_allowed",
            "proof_artifacts": ["tmp/example.json"],
        }],
        "summary": {"kept_open_count": 0},
    }
    validation = module.validate(packet)
    assert validation["status"] == "blocked"
    assert any("invalid_closure_status" in error for error in validation["errors"])


def test_followup_debt_triage_blocks_closure_without_successor_artifact() -> None:
    module = load_module()
    packet = {
        "authority_boundary": dict(module.AUTHORITY_BOUNDARY),
        "source_status": {"improvement_ledger": {"present": True}},
        "triage_items": [{
            "source_key": "bad",
            "category": "planning_quality",
            "closure_allowed": True,
            "closure_status": "verified_fix",
            "proof_artifacts": ["tmp/example.json"],
        }],
        "summary": {"kept_open_count": 0},
    }
    validation = module.validate(packet)
    assert validation["status"] == "blocked"
    assert any("closure_without_successor_artifact" in error for error in validation["errors"])


def _finance_ctx_from_seed(module):
    return {
        "wf74_runner": json.loads(module.WF74_RUNNER.read_text(encoding="utf-8")),
        "finance_response_quality_slice": json.loads(module.FINANCE_RESPONSE_QUALITY_SLICE.read_text(encoding="utf-8")),
        "finance_response_quality_repair_loop": json.loads(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP.read_text(encoding="utf-8")),
    }


def test_finance_proof_closes_without_retired_runner_keys() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        runner = json.loads(module.WF74_RUNNER.read_text(encoding="utf-8"))
        for key in (
            "finance_response_quality_status",
            "finance_response_quality_source_open_blocked_count",
            "finance_response_quality_source_freshness_blocked_count",
            "finance_response_quality_remediation_tracks_needing_repair",
        ):
            runner["summary"].pop(key, None)
        write_json(module.WF74_RUNNER, runner)
        assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is True


def test_finance_proof_rejects_missing_schema() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        for attr in ("FINANCE_RESPONSE_QUALITY_SLICE", "FINANCE_RESPONSE_QUALITY_REPAIR_LOOP"):
            path = getattr(module, attr)
            payload = json.loads(path.read_text(encoding="utf-8"))
            del payload["schema"]
            write_json(path, payload)
            assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is False


def test_finance_proof_rejects_missing_decisive_counts() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.FINANCE_RESPONSE_QUALITY_SLICE.read_text(encoding="utf-8"))
        del payload["summary"]["source_open_blocked_count"]
        write_json(module.FINANCE_RESPONSE_QUALITY_SLICE, payload)
        assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is False
        seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP.read_text(encoding="utf-8"))
        payload["summary"]["proposal_count"] = None
        write_json(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP, payload)
        assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is False


def test_finance_proof_rejects_bad_validation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_validations = [
            None,
            {"status": "critical", "errors": ["boom"], "warnings": []},
            {"status": "ok", "errors": ["hidden"], "warnings": []},
            {"status": "", "errors": [], "warnings": []},
            {"status": "mystery", "errors": [], "warnings": []},
            {"status": "warning", "errors": [], "warnings": []},
            {"status": "ok", "errors": [], "warnings": "not-a-list"},
        ]
        for bad in bad_validations:
            seed_workspace(Path(tmpdir), module)
            payload = json.loads(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP.read_text(encoding="utf-8"))
            if bad is None:
                del payload["validation"]
            else:
                payload["validation"] = bad
            write_json(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP, payload)
            assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is False, bad


def test_finance_proof_rejects_future_timestamp() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        payload = json.loads(module.FINANCE_RESPONSE_QUALITY_SLICE.read_text(encoding="utf-8"))
        payload["generated_at_utc"] = "2099-01-01T00:00:00Z"
        write_json(module.FINANCE_RESPONSE_QUALITY_SLICE, payload)
        assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is False


def test_finance_proof_rejects_stale_evidence_with_open_proposals() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        repair = json.loads(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP.read_text(encoding="utf-8"))
        repair["generated_at_utc"] = "2026-08-30T03:18:21Z"
        repair["summary"]["proposal_count"] = 2
        repair["summary"]["high_priority_count"] = 2
        write_json(module.FINANCE_RESPONSE_QUALITY_REPAIR_LOOP, repair)
        assert module.finance_response_quality_proof_clean(_finance_ctx_from_seed(module)) is False



def _bridge_payload(status="warning", validation_status="warning", age_hours=1.0, action_required=0, post_cutoff=0, unknown=0, resolution="terminal_unavailable_only", schema="veritas.implementation_token_attribution_bridge.v1", errors=None, generated_override=None):
    from datetime import datetime, timedelta, timezone
    if generated_override is not None:
        generated = generated_override
    else:
        generated = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {"schema": schema, "status": status, "generated_at_utc": generated, "summary": {"action_required_supported_runtime_gap_count": action_required, "post_cutoff_supported_unresolved_gap_count": post_cutoff, "unknown_completion_supported_unresolved_gap_count": unknown, "gap_resolution_status": resolution}, "validation": {"status": validation_status, "errors": [] if errors is None else errors, "warnings": ["t"] if validation_status == "warning" else []}}


def _usage_row():
    return {"source_type": "otel_learning_loop", "source_key": "usage_source_reverification_required", "title": "usage_source_reverification_required", "category": "otel_learning_loop", "priority": 60, "decision": "follow_up_required_before_closure"}


def test_usage_source_reverification_closes_on_terminal_only_bridge() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        row = _usage_row()
        ctx = {"implementation_token_bridge": _bridge_payload()}
        item = module.classify_usage_source_reverification(row, ctx)
        assert item.get("closure_allowed") is True
        assert item.get("closure_status") == "historical_terminal_unavailable_claim_limit"
        assert item.get("action_state") == "monitor_only"
        assert item.get("closure_status") in module.ALLOWED_CLOSURE_STATUSES
        assert item.get("closure_status") != "verified_fix"
        assert "NOT a verified success" in item.get("closure_reason") or "NOT a verified success" in item.get("closure_reason", "")
        assert "tmp/implementation-token-attribution-bridge.json" in item.get("proof_artifacts")


def test_usage_source_reverification_closes_on_historical_only_bridge() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        row = _usage_row()
        ctx = {"implementation_token_bridge": _bridge_payload(resolution="historical_or_classified_unavailable_only", status="ok", validation_status="ok")}
        item = module.classify_usage_source_reverification(row, ctx)
        assert item.get("closure_allowed") is True
        assert item.get("closure_status") == "historical_terminal_unavailable_claim_limit"
        assert item.get("action_state") == "monitor_only"


def test_usage_source_reverification_fails_closed() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        row = _usage_row()
        bad_cases = [
            {},
            {"schema": "wrong", "status": "warning", "generated_at_utc": _bridge_payload()["generated_at_utc"], "summary": {"action_required_supported_runtime_gap_count": 0, "post_cutoff_supported_unresolved_gap_count": 0, "unknown_completion_supported_unresolved_gap_count": 0, "gap_resolution_status": "terminal_unavailable_only"}, "validation": {"status": "warning", "errors": [], "warnings": ["t"]}},
            _bridge_payload(age_hours=25.0),
            _bridge_payload(generated_override="2099-01-01T00:00:00Z"),
            _bridge_payload(action_required=1, resolution="stamp_required"),
            _bridge_payload(post_cutoff=2, resolution="stamp_required"),
            _bridge_payload(validation_status="blocked", errors=["x"]),
            _bridge_payload(status="blocked"),
        ]
        # bool masquerade must fail closed
        bool_case = _bridge_payload()
        bool_case["summary"]["action_required_supported_runtime_gap_count"] = True
        bad_cases.append(bool_case)
        for bad in bad_cases:
            item = module.classify_usage_source_reverification(row, {"implementation_token_bridge": bad})
            assert not item.get("closure_allowed"), bad
            assert item.get("action_state") == "usage_source_reverification_open"


def test_usage_source_reverification_end_to_end_packet() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        ledger = json.loads(module.IMPROVEMENT_LEDGER.read_text(encoding="utf-8"))
        ledger["followup_required_improvements"].append(_usage_row())
        ledger_path = module.IMPROVEMENT_LEDGER
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        packet = module.build_packet()
        by_key = {row.get("source_key"): row for row in packet["triage_items"]}
        assert "usage_source_reverification_required" in by_key
        closed = by_key["usage_source_reverification_required"]
        assert closed.get("closure_allowed") is True
        assert closed.get("closure_status") == "historical_terminal_unavailable_claim_limit"
        assert closed.get("action_state") == "monitor_only"
        assert packet["validation"]["status"] in {"warning", "ok"}


if __name__ == "__main__":
    test_followup_debt_triage_closes_only_proven_rows()
    test_cron_followup_becomes_monitor_only_when_cron_control_is_green()
    test_collector_followup_becomes_monitor_only_when_otel_ops_is_clean()
    test_duplicate_operational_followups_close_as_superseded()
    test_obsolete_wf85_blocked_packet_cannot_stop_or_decide_closure()
    test_followup_debt_triage_blocks_invalid_closure_status()
    test_followup_debt_triage_blocks_closure_without_successor_artifact()
    test_finance_proof_closes_without_retired_runner_keys()
    test_finance_proof_rejects_missing_schema()
    test_finance_proof_rejects_missing_decisive_counts()
    test_finance_proof_rejects_bad_validation()
    test_finance_proof_rejects_future_timestamp()
    test_finance_proof_rejects_stale_evidence_with_open_proposals()
    test_usage_source_reverification_closes_on_terminal_only_bridge()
    test_usage_source_reverification_closes_on_historical_only_bridge()
    test_usage_source_reverification_fails_closed()
    test_usage_source_reverification_end_to_end_packet()
    print("wf88 follow-up debt triage packet tests passed")


def load_triage_under_test():
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location(
        'wf88_triage_under_test', str(here / 'wf88_followup_debt_triage_packet.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def planning_row_fixture():
    return {'source_type': 'wf74_improvement_opportunity', 'source_key': 'planning_quality-a',
            'title': 'Measure and close planning follow-through gaps', 'category': 'planning_quality',
            'priority': 80, 'decision': 'follow_up_required_before_closure'}


def planning_ctx_fixture(router_summary):
    return {'wf74_router': {'summary': router_summary}, 'wf74_runner': {'summary': {}}}


def trusted_router_summary(actionable, terminal, repaired, raw, status):
    return {'planning_followthrough_gap_count': raw, 'planning_followthrough_clean_rate': 0.185,
            'planning_followthrough_gap_count_selected': actionable,
            'planning_followthrough_gap_source': 'actionable_partition_verified',
            'planning_followthrough_actionable_gap_count': actionable,
            'planning_followthrough_terminal_unavailable_count': terminal,
            'planning_followthrough_repaired_accepted_count': repaired,
            'planning_partitioned_gap_row_count': raw,
            'planning_partition_reconciliation_ok': True,
            'planning_actionable_status': status,
            'planning_signal_schema': 'veritas.planning_quality_signal.v1',
            'planning_gap_selection_warning': None}


def test_classify_planning_keeps_live_like_current_open() -> None:
    module = load_triage_under_test()
    summary = trusted_router_summary(21, 128, 14, 163, 'attention')
    item = module.classify_planning(planning_row_fixture(), planning_ctx_fixture(summary))
    assert item['action_state'] == 'planning_followthrough_gap_open'
    assert not item.get('closure_allowed')
    assert item['context']['planning_followthrough_gap_count'] == 163
    assert item['context']['planning_followthrough_actionable_gap_count'] == 21


def test_classify_planning_closes_only_on_trusted_zero_actionable() -> None:
    module = load_triage_under_test()
    summary = trusted_router_summary(0, 149, 14, 163, 'ok')
    item = module.classify_planning(planning_row_fixture(), planning_ctx_fixture(summary))
    assert item.get('closure_allowed') is True
    assert item['closure_status'] == 'verified_fix'
    assert item['context']['planning_followthrough_gap_count'] == 163
    assert item['context']['planning_followthrough_terminal_unavailable_count'] == 149
    assert 'not rewritten as clean' in item['closure_reason']


def test_classify_planning_malformed_partition_never_closes() -> None:
    module = load_triage_under_test()
    summary = trusted_router_summary(21, 128, 14, 163, 'attention')
    summary['planning_followthrough_gap_source'] = 'raw_gap_fallback'
    summary['planning_partition_reconciliation_ok'] = False
    summary['planning_gap_selection_warning'] = 'partition_reconciliation_not_exactly_true'
    item = module.classify_planning(planning_row_fixture(), planning_ctx_fixture(summary))
    assert item['action_state'] == 'planning_followthrough_gap_open'
    assert not item.get('closure_allowed')


def test_classify_planning_legacy_fixture_still_closes() -> None:
    module = load_triage_under_test()
    summary = {'planning_followthrough_gap_count': 0, 'planning_followthrough_clean_rate': 1.0}
    item = module.classify_planning(planning_row_fixture(), planning_ctx_fixture(summary))
    assert item.get('closure_allowed') is True
    assert item['closure_status'] == 'verified_fix'
