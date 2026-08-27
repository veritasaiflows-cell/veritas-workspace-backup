#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "startup_brief_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("startup_brief_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_build_payload_from_existing_packets() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        module.ROOT = root
        module.TMP = tmp
        module.FUTURE_PACKET = tmp / "future-session-enhancement-packet.json"
        module.PM_PACKET = tmp / "pm-control-packet.json"
        module.CRON_PACKET = tmp / "cron-control-packet.json"
        module.IMPROVEMENT_PACKET = tmp / "improvement-ledger-current.json"
        module.TOKEN_USAGE_PACKET = tmp / "token-usage-ledger-current.json"
        module.TOKEN_BUDGET_PACKET = tmp / "token-budget-status.json"
        module.OWNER_GATED_PACKET = tmp / "owner-gated-action-review-queue.json"
        module.ESCALATION_CONSUMER_PACKET = tmp / "main-session-escalation-consumer.json"
        module.ACTION_EXECUTOR_PACKET = tmp / "main-session-action-executor.json"
        module.PM_AUTONOMY_DISPATCHER_PACKET = tmp / "pm-autonomy-dispatcher.json"
        module.PM_JOB_WORKER_PACKET = tmp / "pm-job-worker-runner.json"
        module.PM_AUTONOMY_VERIFIER_PACKET = tmp / "pm-autonomy-verifier.json"
        module.PM_MAIN_ACTION_INBOX_PACKET = tmp / "pm-main-session-action-inbox.json"
        module.WF74_DECISION_DOCKET_PACKET = tmp / "wf74-decision-docket.json"
        module.OTEL_LEARNING_PACKET = tmp / "otel-learning-loop.json"
        module.CRON_MIGRATION_REPAIR_PLAN_PACKET = tmp / "cron-migration-repair-plan.json"
        module.WF88_WIKI_SYNTHESIS_PACKET = tmp / "wf88-wiki-synthesis-packet.json"
        module.WIKI_BOOTSTRAP_PROOF_PACKET = tmp / "wiki-bootstrap-proof.json"
        module.ACTIONABLE_QUEUE_PACKET = tmp / "actionable-improvement-queue.json"
        module.NO_ORPHAN_VALIDATOR_PACKET = tmp / "no-orphan-validator.json"

        write_json(module.FUTURE_PACKET, {
            "workflow_capsules": [
                {"workflow_id": "WF85", "effective_status": "ready"},
                {"workflow_id": "WF84", "effective_status": "ready"},
            ],
            "execution_efficiency_policy": module.implementation_router.execution_efficiency_policy(),
            "coding_outcome_efficiency": {
                "present": True,
                "route_conformant_count": 4,
                "route_mismatch_count": 0,
                "comparable_cohort_count": 1,
                "eligible_cohort_count": 0,
                "automatic_ranking_or_promotion_active": False,
            },
        })
        write_json(module.PM_PACKET, {
            "status": "ok",
            "summary": {
                "implementation_queue": {"ready_job_count": 10, "blocked_job_count": 0},
                "pm_readiness": {"readiness_band": "yellow"},
                "finance_domain_repair_digest": {
                    "implementation_blocker_count": 0,
                    "control_plane_blocker_count": 0,
                    "finance_domain_repair_item_count": 200,
                    "tier_a_b_missing_decision_grade_band_count": 15,
                    "tier_a_b_missing_decision_grade_band_tickers": ["ACN"],
                },
            },
        })
        write_json(module.CRON_PACKET, {
            "status": "ok",
            "summary": {"escalation_signal_count": 0, "blocked_count": 0},
        })
        write_json(module.IMPROVEMENT_PACKET, {"status": "ok", "summary": {}})
        write_json(module.TOKEN_USAGE_PACKET, {"status": "ok", "summary": {}})
        write_json(module.TOKEN_BUDGET_PACKET, {
            "status": "ok",
            "fleet_usage": {
                "present": True,
                "status": "partial",
                "generated_at_utc": "2026-08-09T18:00:00Z",
                "summary": {
                    "configured_agent_count": 6,
                    "utilized_agent_count": 4,
                    "pricing_grade_attribution_coverage_percent": 75.0,
                    "main_accepted_count": 2,
                    "qa_review_completed_count": 2,
                    "qa_pass_count": 2,
                    "rework_count": 0,
                    "attribution_gap_count": 0,
                },
                "oauth_capacity_advisory": {
                    "status": "current",
                    "tier": "normal",
                    "remaining_percent": 58.0,
                    "automatic_action_allowed": False,
                },
            },
        })
        write_json(module.OWNER_GATED_PACKET, {"status": "ok", "summary": {}})
        write_json(module.ESCALATION_CONSUMER_PACKET, {"status": "ok", "summary": {}})
        write_json(module.ACTION_EXECUTOR_PACKET, {
            "status": "ok",
            "summary": {
                "action_type": "execute_pm_proof",
                "classification": "auto_execute",
                "selected_pm_job": {"job_id": "pm-01"},
                "executed": False,
            },
        })
        write_json(module.PM_AUTONOMY_DISPATCHER_PACKET, {"status": "ok", "summary": {}})
        write_json(module.PM_JOB_WORKER_PACKET, {"status": "ok", "summary": {}})
        write_json(module.PM_AUTONOMY_VERIFIER_PACKET, {"status": "ok", "summary": {}})
        write_json(module.PM_MAIN_ACTION_INBOX_PACKET, {"status": "ok"})
        write_json(module.WF74_DECISION_DOCKET_PACKET, {
            "status": "ok",
            "summary": {
                "row_count": 0,
                "active_action_count": 0,
                "fix_now_count": 0,
                "owner_decision_count": 0,
                "market_session_accrual_count": 0,
                "monitor_only_count": 0,
                "hard_stop_count": 0,
                "next_safe_action": "No active implementation action.",
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })
        write_json(module.OTEL_LEARNING_PACKET, {
            "status": "ok",
            "learning_summaries": {
                "otel_health": {"collector_health": "ok", "drift_status": "stable"},
                "token_cost": {"token_coverage_ratio": 0.82, "cost_coverage_ratio": 0.64},
            },
            "recommendations": [{"id": "carry-forward", "decision": "route"}],
            "carry_forward_contract": {"status": "ready", "next_safe_action": "Keep OTEL carry-forward visible."},
            "auto_implementation_router": {"status": "gated_auto_route_no_auto_apply"},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })
        write_json(module.WF88_WIKI_SYNTHESIS_PACKET, {
            "status": "wiki_synthesis_ready_no_apply_authority",
            "summary": {
                "wiki_page_count": 8,
                "self_prompt_count": 6,
                "followup_required_open_count": 0,
                "recommendation_later_outcome_graded_rows": 1,
            },
            "recommendation_leak_guard": {
                "pass": True,
                "open_unrouted_recommendation_count": 0,
                "auto_apply_count": 0,
            },
            "action_items": [],
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })
        write_json(module.WIKI_BOOTSTRAP_PROOF_PACKET, {
            "schema": "veritas.wiki_bootstrap_proof.v2",
            "status": "bootstrap_ready_no_apply_authority",
            "summary": {
                "bootstrap_gate": "material_bootstrap_ready",
                "required_file_count": 5,
                "validated_file_count": 5,
                "missing_file_count": 0,
                "missing_marker_count": 0,
                "missing_semantic_marker_count": 0,
                "semantic_render_hash_match": True,
                "recommendation_leak_guard_pass": True,
                "auto_apply_count": 0,
                "no_orphan_validation": "ok",
                "actionable_orphan_count": 0,
                "actionable_missing_contract_count": 0,
                "next_safe_action": "Open the WF88 wiki entry points before material work.",
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })
        write_json(module.ACTIONABLE_QUEUE_PACKET, {
            "status": "actionable_queue_ready_no_apply_authority",
            "summary": {
                "action_item_count": 0,
                "orphan_count": 0,
                "missing_contract_count": 0,
                "owner_decision_count": 0,
                "monitor_only_count": 0,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })
        write_json(module.NO_ORPHAN_VALIDATOR_PACKET, {
            "status": "no_orphan_validation_ready",
            "summary": {"validation_passed": True},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        })

        payload = module.build_payload(max_age_minutes=90)
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "ok"
        assert payload["authority_boundary"]["regenerates_control_packets"] is False
        assert payload["status_route_contract"]["default_command"] == r"python scripts\status_card_packet.py --read-only --frontdoor --render --validate"
        assert payload["status_route_contract"]["fallback_command"] == r"python scripts\startup_brief_packet.py --write --validate"
        assert payload["status_route_contract"]["preferred_cached_artifact"] == "tmp/veritas-status-card-frontdoor.json"
        assert payload["status_route_contract"]["drilldown_artifact"] == "tmp/veritas-status-card.json"
        assert payload["status_route_contract"]["max_tool_calls"] == 1
        assert payload["status_route_contract"]["stop_after_packet"] is True
        assert payload["status_route_contract"]["status_card_read_only_default"] is True
        assert payload["status_route_contract"]["startup_brief_is_fallback_only"] is True
        assert payload["status_route_contract"]["regenerates_pm_or_cron_packets"] is False
        assert payload["summary"]["wf85_status"] == "ready"
        assert payload["summary"]["pm_ready_job_count"] == 10
        assert payload["summary"]["main_session_action_executor_action"] == "execute_pm_proof"
        assert payload["summary"]["otel_learning_loop_status"] == "ok"
        assert payload["summary"]["otel_carry_forward_status"] == "ready"
        assert payload["summary"]["actionable_queue_orphan_count"] == 0
        assert payload["summary"]["no_orphan_validation_passed"] is True
        assert payload["summary"]["wiki_bootstrap_status"] == "bootstrap_ready_no_apply_authority"
        assert payload["summary"]["wiki_bootstrap_validation"] == "ok"
        assert payload["summary"]["wiki_bootstrap_validated_file_count"] == 5
        assert payload["summary"]["execution_efficiency_policy_schema"] == "veritas.execution_efficiency_policy.v1"
        assert payload["summary"]["execution_efficiency_material_dispatch_ready"] is True
        assert payload["execution_efficiency_policy"] == module.implementation_router.execution_efficiency_policy()
        assert payload["execution_efficiency_policy_source"] == "scripts/project_implementation_router.py"
        assert payload["future_efficiency_policy_matches_owner"] is True
        assert payload["summary"]["execution_efficiency_route_conformant_count"] == 4
        assert payload["summary"]["tier_a_b_missing_decision_grade_band_tickers"] == ["ACN"]
        assert payload["fleet_posture"]["status"] == "partial"
        assert payload["fleet_posture"]["operating_model"]["configured_total_agent_count"] == 7
        assert payload["fleet_posture"]["operating_model"]["main_authority"]["sole_acceptance_owner"] is True
        assert payload["fleet_posture"]["oauth_capacity_advisory"]["automatic_action_allowed"] is False
        assert payload["fleet_posture"]["privacy_contract"]["raw_prompt_stored"] is False
        text = module.render_text(payload)
        assert "otel=status:ok" in text
        assert "wiki_bootstrap=status:bootstrap_ready_no_apply_authority" in text
        assert "route=shallow_status" in text
        assert "max_tool_calls=1" in text
        assert "fleet=status:partial" in text

        tampered_future = json.loads(module.FUTURE_PACKET.read_text(encoding="utf-8"))
        tampered_future["execution_efficiency_policy"]["route_order"] = []
        write_json(module.FUTURE_PACKET, tampered_future)
        repaired_projection = module.build_payload(max_age_minutes=90)
        assert repaired_projection["execution_efficiency_policy"] == module.implementation_router.execution_efficiency_policy()
        assert repaired_projection["future_efficiency_policy_matches_owner"] is False
        assert "future_session_packet.execution_efficiency_policy_owner_mismatch" in repaired_projection["input_validation_warnings"]


def main() -> int:
    test_build_payload_from_existing_packets()
    print("startup brief packet tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
