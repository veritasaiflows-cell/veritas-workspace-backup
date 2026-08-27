#!/usr/bin/env python3
"""Targeted tests for WF74 learning-loop Telegram digest."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf74_learning_loop_telegram_digest as digest


def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def queue_packet() -> dict:
    return {
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "opportunity_count": 2,
            "high_priority_count": 1,
            "top_opportunity_title": "Stamp model_path on implementation and helper producers",
        },
        "opportunities": [
            {
                "opportunity_id": "opp-1",
                "title": "Stamp model_path on implementation and helper producers",
                "category": "code_mutation",
                "priority": 94,
            },
            {
                "opportunity_id": "opp-2",
                "title": "Review OTEL drift",
                "category": "collector_config",
                "priority": 88,
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def proposal_packet() -> dict:
    return {
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "proposal_count": 2,
            "owner_decision_required_count": 1,
            "auto_apply_count": 0,
        },
        "proposals": [
            {
                "proposal_id": "proposal-owner-1",
                "title": "Owner-gated OTEL field-depth decision packet is ready",
                "category": "collector_config",
                "proposal_status": "owner_decision_required",
                "priority": 70,
            },
            {
                "proposal_id": "proposal-main-1",
                "title": "Stamp model_path on implementation and helper producers",
                "category": "code_mutation",
                "proposal_status": "main_review_required",
                "priority": 94,
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def auto_patch_packet() -> dict:
    return {
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "plan_count": 0,
            "patch_plan_count": 0,
            "skill_workshop_request_count": 0,
            "owner_gated_plan_count": 0,
            "auto_apply_count": 0,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def critical_review_packet() -> dict:
    return {
        "schema": "veritas.otel_critical_review_decision_packet.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "severity": "warning",
        "persistence": "current_window_only: ratio=2.8; reasons=daily_event_rate_deviates_from_weekly_baseline",
        "decision": {
            "recommended_decision": "review",
            "owner_decision_required": True,
            "owner_decision_today": "yes_review_only",
            "next_safe_action": "Review owner decision context; keep collector config unchanged.",
        },
        "digest_context": {
            "applies_to_categories": ["collector_config"],
            "applies_to_titles": [
                "Review OTEL drift",
                "Owner-gated OTEL field-depth decision packet is ready",
            ],
            "severity": "warning",
            "persistence": "current_window_only",
            "next_safe_action": "Review owner decision context; keep collector config unchanged.",
            "owner_decision_today": "yes_review_only",
            "recommended_decision": "review",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def model_quality_packet() -> dict:
    return {
        "schema": "wf74.model_quality_collection_cron_runner.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {"steps_blocked": 0},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def model_quality_critical_residue_packet() -> dict:
    packet = model_quality_packet()
    packet["validation"] = {
        "status": "critical",
        "critical": 1,
        "warnings": 1,
        "findings": [
            {"severity": "critical", "detail": "improvement ledger validation is not ok"},
            {"severity": "warning", "detail": "improvement ledger has overdue high-priority carry-forward rows"},
        ],
    }
    return packet


def model_quality_domain_nonfatal_packet() -> dict:
    packet = model_quality_packet()
    packet["status"] = "domain_attention"
    packet["summary"] = {
        "steps_blocked": 1,
        "scheduler_exit_domain_blocked_nonfatal": True,
        "scheduler_exit_reason": "classified_finance_response_decision_readiness_debt",
    }
    packet["validation"] = {
        "status": "critical",
        "critical": 2,
        "findings": [
            {"severity": "critical", "detail": "one or more collection steps blocked"},
            {"severity": "critical", "detail": "learning environment runner status is blocked"},
        ],
    }
    return packet


def otel_learning_packet() -> dict:
    return {
        "schema": "veritas.otel_learning_loop.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "learning_summaries": {
            "otel_health": {
                "collector_health": "ok",
                "drift_status": "stable",
                "daily_event_count": 44,
                "daily_warning_or_error_count": 0,
            },
            "token_cost": {
                "token_coverage_ratio": 0.82,
                "cost_coverage_ratio": 0.64,
            },
        },
        "recommendations": [{"id": "carry-forward", "decision": "route"}],
        "carry_forward_contract": {"status": "ready", "next_safe_action": "Keep OTEL carry-forward visible."},
        "auto_implementation_router": {"status": "gated_auto_route_no_auto_apply"},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def improvement_ledger_packet() -> dict:
    return {
        "schema": "veritas.improvement_ledger_current.v1",
        "status": "warning",
        "generated_at_utc": stamp(),
        "summary": {
            "latest_open_count": 22,
            "high_priority_open_count": 7,
            "overdue_open_count": 18,
            "due_soon_open_count": 2,
            "high_priority_overdue_open_count": 7,
            "followup_required_open_count": 13,
            "escalation_level": "high_priority_overdue",
            "by_category": {"cron_migration": 4, "otel_learning_loop": 7},
        },
        "learning_loop_kpis": {
            "anti_theater_status": "blocked_by_overdue_backlog",
            "closure_rate": 0.29,
        },
        "skill_proposal_audit": {
            "proposal_count": 167,
            "pending_count": 5,
            "applied_count": 125,
            "relevant_pending_count": 1,
            "relevant_pending": [
                {
                    "proposal_id": "implementation-friction-closeout-20260619-a5dd119bda",
                    "skill": "implementation-friction-closeout",
                    "status": "pending",
                }
            ],
            "not_implemented_meaning": "Pending Skill Workshop proposals are not live doctrine.",
        },
        "latest_open_improvements": [
            {
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "priority": 92,
                "age_hours": 247.6,
                "sla_status": "overdue",
                "next_action": "Classify durable follow-up before closure.",
            }
        ],
        "followup_required_improvements": [
            {
                "title": "Route blocked cron signals into a migration-ready repair plan",
                "priority": 92,
            }
        ],
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["open improvements require follow-up classification before closure"],
        },
    }


def autonomy_router_packet() -> dict:
    return {
        "schema": "veritas.wf74_autonomy_work_router.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "opportunity_count": 3,
            "routed_opportunity_count": 1,
            "pm_job_candidate_count": 3,
            "workflow_followup_count": 2,
            "cron_repair_plan_count": 0,
            "routed_categories": ["workflow_maturity"],
            "department_counts": {"runtime_ops": 2, "cron": 1},
        },
        "kpis": {
            "recommendation_to_route_conversion_rate": 1.0,
            "route_to_pm_job_conversion_rate": 1.0,
            "planning_followthrough_clean_rate": 1.0,
            "high_priority_overdue_count": 7,
            "average_age_of_top_open_improvement_hours": 247.6,
        },
        "next_safe_action": "Route review-only follow-ups; do not apply changes.",
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def decision_docket_packet() -> dict:
    return {
        "schema": "veritas.wf74_decision_docket.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "row_count": 30,
            "fix_now_count": 6,
            "owner_decision_count": 1,
            "hard_stop_count": 0,
            "highest_priority_state": "fix_now",
            "next_safe_action": "Inspect current cron regression before patching.",
        },
        "context": {
            "cron": {
                "status": "ok",
                "blocked_count": 4,
                "escalation_signal_count": 4,
                "should_wake_main_session": True,
            },
            "wf87_readiness_status": "phase_a_hardening_implemented_runtime_blocked",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def otel_ops_packet() -> dict:
    return {
        "schema": "veritas.otel_ops_control.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {"event_count": 1347},
        "collector_health": {"status": "ok", "host": "127.0.0.1", "port": 4318, "listening": True},
        "drift": {
            "status": "ok",
            "daily_warning_or_error_count": 0,
            "daily_events_per_hour": 56.125,
            "weekly_events_per_hour": 72.6274,
            "daily_vs_weekly_event_rate_ratio": 0.7728,
            "drift_reasons": [],
        },
        "tool_workflow_metadata": {
            "present": True,
            "status": "ok",
            "row_count": 6982,
            "unique_tool_count": 516,
            "failed_or_blocked_count": 438,
            "privacy_scan_status": "ok",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def tool_workflow_packet() -> dict:
    return {
        "schema": "veritas.otel_tool_workflow_metadata.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "row_count": 6982,
            "unique_tool_count": 516,
            "failed_or_blocked_count": 438,
        },
        "privacy_scan": {"status": "ok"},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def token_budget_packet() -> dict:
    return {
        "schema": "veritas.token_budget_status.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "fleet_usage": {
            "present": True,
            "status": "partial",
            "generated_at_utc": stamp(),
            "summary": {"configured_agent_count": 6, "utilized_agent_count": 4},
            "usage_windows": {},
            "agents": [],
            "billing_semantics": {
                "api_equivalent_is_not_invoice": True,
                "actual_billed_cost_usd": None,
            },
            "oauth_capacity_advisory": {
                "status": "current",
                "tier": "balanced",
                "remaining_percent": 62.0,
                "automatic_action_allowed": False,
            },
        },
    }


def token_efficiency_packet() -> dict:
    return {
        "schema": "veritas.token_efficiency_scorecard.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "fleet_efficiency": {
            "present": True,
            "status": "partial",
            "generated_at_utc": stamp(),
            "summary": {
                "configured_agent_count": 6,
                "observed_agent_count": 6,
                "utilized_agent_count": 5,
                "session_event_count": 12,
                "attribution_grade_coverage_percent": 91.67,
                "pricing_grade_event_count": 9,
                "pricing_grade_attribution_coverage_percent": 75.0,
                "parent_job_count": 5,
                "parent_job_completed_count": 4,
                "parent_job_completion_percent": 80.0,
                "completed_lane_count": 4,
                "main_accepted_count": 3,
                "main_acceptance_percent": 75.0,
                "main_acceptance_pending_count": 1,
                "qa_pass_count": 3,
                "qa_yield_percent": 75.0,
                "rework_count": 1,
                "rework_percent": 25.0,
                "attribution_gap_count": 1,
            },
            "usage_windows": {
                "rolling_5h_observed": {"status": "partial_observed", "total_tokens": 1250},
                "rolling_24h_gateway": {
                    "status": "partial",
                    "total_tokens": 5000,
                    "api_equivalent_cost_usd": 0.25,
                    "api_equivalent_is_not_invoice": True,
                    "actual_billed_cost_usd": None,
                },
                "closed_7d_gateway": {
                    "status": "partial",
                    "total_tokens": 28000,
                    "api_equivalent_cost_usd": 1.4,
                    "api_equivalent_is_not_invoice": True,
                    "actual_billed_cost_usd": None,
                },
            },
            "agents": [{
                "agent_id": "implementation-builder",
                "agent_role": "implementation_builder",
                "reporting_source": "gateway_usage_cost",
                "reporting_total_tokens": 18000,
                "utilization_share_percent": 64.29,
                "utilized": True,
                "session_event_count": 4,
                "session_pricing_grade_event_count": 3,
                "prompt": "must-not-leak",
                "outcomes": {
                    "completed_lane_count": 2,
                    "parent_job_count": 2,
                    "parent_job_completed_count": 2,
                    "main_accepted_count": 1,
                    "main_acceptance_pending_count": 1,
                    "qa_pass_count": 1,
                    "qa_yield_percent": 50.0,
                    "rework_count": 1,
                    "attribution_gap_count": 1,
                },
            }],
            "billing_semantics": {
                "label": "API-equivalent benchmark",
                "api_equivalent_is_not_invoice": True,
                "actual_billed_cost_usd": None,
            },
            "oauth_capacity_advisory": {
                "status": "current",
                "tier": "balanced",
                "remaining_percent": 62.0,
                "reset_at_utc": "2026-08-12T00:00:00Z",
                "automatic_action_allowed": False,
            },
        },
    }


def run_digest(td: Path, extra: list[str] | None = None, expected_rc: int = 0) -> dict:
    output = td / "out.json"
    args = [
        "--queue",
        str(td / "queue.json"),
        "--proposals",
        str(td / "proposals.json"),
        "--auto-patch",
        str(td / "auto-patch.json"),
        "--state",
        str(td / "state.json"),
        "--output",
        str(output),
        "--critical-review",
        str(td / "critical-review.json"),
        "--model-quality-runner",
        str(td / "model-quality.json"),
        "--otel-learning",
        str(td / "otel-learning.json"),
        "--improvements",
        str(td / "improvements.json"),
        "--autonomy-router",
        str(td / "autonomy-router.json"),
        "--decision-docket",
        str(td / "decision-docket.json"),
        "--otel-ops",
        str(td / "otel-ops.json"),
        "--tool-workflow",
        str(td / "tool-workflow.json"),
        "--token-budget",
        str(td / "token-budget.json"),
        "--token-efficiency",
        str(td / "token-efficiency.json"),
        "--write",
        "--validate",
        "--force",
    ]
    if extra:
        args.extend(extra)
    rc = digest.main(args)
    assert rc == expected_rc
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        write(td / "queue.json", queue_packet())
        write(td / "proposals.json", proposal_packet())
        write(td / "auto-patch.json", auto_patch_packet())
        write(td / "model-quality.json", model_quality_packet())
        write(td / "otel-learning.json", otel_learning_packet())
        write(td / "improvements.json", improvement_ledger_packet())
        write(td / "autonomy-router.json", autonomy_router_packet())
        write(td / "decision-docket.json", decision_docket_packet())
        write(td / "otel-ops.json", otel_ops_packet())
        write(td / "tool-workflow.json", tool_workflow_packet())
        write(td / "token-budget.json", token_budget_packet())
        write(td / "token-efficiency.json", token_efficiency_packet())

        first = run_digest(td)
        assert first["status"] == "ok", first
        assert first["operator_action"] == "TELEGRAM_NOTIFY", first
        assert first["summary"]["owner_decision_required_count"] == 1
        assert first["summary"]["auto_apply_count"] == 0
        assert first["summary"]["otel_carry_forward_status"] == "ready"
        assert first["summary"]["improvement_open_count"] == 22
        assert first["summary"]["skill_pending_proposal_count"] == 5
        assert first["summary"]["otel_ops_event_count"] == 1347
        assert first["summary"]["wf74_fix_now_count"] == 6
        assert first["summary"]["fleet_utilized_agent_count"] == 5
        assert first["summary"]["fleet_pricing_grade_attribution_coverage_percent"] == 75.0
        assert first["summary"]["fleet_parent_job_completed_count"] == 4
        assert first["summary"]["fleet_main_accepted_count"] == 3
        assert first["summary"]["fleet_qa_yield_percent"] == 75.0
        assert first["summary"]["fleet_rework_count"] == 1
        assert first["summary"]["fleet_attribution_gap_count"] == 1
        assert first["summary"]["fleet_rolling_5h_total_tokens"] == 1250
        assert first["summary"]["fleet_rolling_24h_total_tokens"] == 5000
        assert first["summary"]["fleet_closed_7d_total_tokens"] == 28000
        assert first["otel_learning_loop"]["auto_apply_allowed"] is False
        assert first["improvement_ledger"]["escalation_level"] == "high_priority_overdue"
        assert first["skill_proposals"]["relevant_pending_count"] == 1
        assert first["otel_ops"]["tool_metadata_failed_or_blocked_count"] == 438
        assert first["wf74_intelligence"]["cron_context"]["blocked_count"] == 4
        assert first["isolated_agent_fleet"]["source"] == "token_efficiency_scorecard"
        assert first["isolated_agent_fleet"]["billing_semantics"]["api_equivalent_is_not_invoice"] is True
        assert first["isolated_agent_fleet"]["billing_semantics"]["actual_billed_cost_usd"] is None
        assert first["isolated_agent_fleet"]["oauth_capacity_advisory"]["automatic_action_allowed"] is False
        assert first["new_owner_gated_proposals"]
        assert "OTEL Carry-Forward" in first["message_preview"]
        assert "OTEL Operations" in first["message_preview"]
        assert "Improvement Ledger" in first["message_preview"]
        assert "Skill Proposals" in first["message_preview"]
        assert "WF74 Intelligence" in first["message_preview"]
        assert "Isolated Agent Fleet" in first["message_preview"]
        assert "API-equivalent benchmark; not an invoice" in first["message_preview"]
        assert "must-not-leak" not in json.dumps(first["isolated_agent_fleet"], sort_keys=True)
        assert "must-not-leak" not in first["message_preview"]
        assert "high_priority_overdue" in first["message_preview"]
        assert "Review/proposal only" in first["message_preview"]
        assert first["delivery_messages_preview"]
        assert all("\n" not in item for item in first["delivery_messages_preview"])
        assert digest.authority_clean(first["authority_boundary"])

        (td / "token-budget.json").unlink()
        (td / "token-efficiency.json").unlink()
        missing_fleet = run_digest(td)
        assert missing_fleet["status"] == "ok", missing_fleet
        assert missing_fleet["isolated_agent_fleet"]["present"] is False
        assert missing_fleet["summary"]["fleet_rolling_24h_total_tokens"] is None
        assert "isolated_agent_fleet_reporting_unavailable" in missing_fleet["warnings"]
        write(td / "token-budget.json", token_budget_packet())
        write(td / "token-efficiency.json", token_efficiency_packet())

        write(td / "model-quality.json", model_quality_critical_residue_packet())
        residue = run_digest(td)
        assert residue["status"] == "ok", residue
        assert residue["model_quality_runner"]["clean"] is True, residue
        assert residue["model_quality_runner"]["reason"] == "model_quality_runner_clean_with_routed_diagnostic_residue"
        write(td / "model-quality.json", model_quality_packet())

        write(td / "model-quality.json", model_quality_domain_nonfatal_packet())
        domain_nonfatal = run_digest(td)
        assert domain_nonfatal["status"] == "ok", domain_nonfatal
        assert domain_nonfatal["model_quality_runner"]["clean"] is True, domain_nonfatal
        assert domain_nonfatal["model_quality_runner"]["reason"] == "classified_finance_response_decision_readiness_debt"
        write(td / "model-quality.json", model_quality_packet())

        write(td / "critical-review.json", critical_review_packet())
        enriched = run_digest(td)
        assert enriched["critical_review"]["present"] is True
        assert "severity warning" in enriched["message_preview"], enriched["message_preview"]
        assert "persistence current_window_only" in enriched["message_preview"], enriched["message_preview"]
        assert "owner today yes_review_only" in enriched["message_preview"], enriched["message_preview"]
        assert "next Review owner decision context; keep collector config unchanged." in enriched["message_preview"]
        assert enriched["delivery_messages_preview"]
        assert all("\n" not in item for item in enriched["delivery_messages_preview"])

        state = {
            "sent": {enriched["signature_hash"]: {"sent_at_utc": stamp()}},
            "last_signature_hash": enriched["signature_hash"],
            "last_owner_gated_proposal_ids": ["proposal-owner-1"],
        }
        write(td / "state.json", state)
        duplicate = run_digest(td)
        assert duplicate["operator_action"] == "NO_REPLY", duplicate
        assert duplicate["trigger_reason"] == "duplicate_signature_already_sent"

        bad = proposal_packet()
        bad["summary"]["auto_apply_count"] = 1
        write(td / "proposals.json", bad)
        blocked = run_digest(td, expected_rc=1)
        assert blocked["status"] == "blocked", blocked
        assert "proposal_auto_apply_count_nonzero" in blocked["validation"]["errors"]

        write(td / "proposals.json", proposal_packet())
        model_blocked = run_digest(td, ["--force-model-quality-block"], expected_rc=1)
        assert model_blocked["status"] == "blocked", model_blocked
        assert model_blocked["operator_action"] == "MAIN_SESSION_BLOCKER_PACKET", model_blocked
        assert model_blocked["sent_count"] == 0, model_blocked
        assert "current_model_quality_step_failed" in model_blocked["validation"]["errors"]

    morning = datetime(2026, 6, 12, 17, 0, tzinfo=timezone.utc)  # 10:00 MST
    evening = datetime(2026, 6, 13, 1, 30, tzinfo=timezone.utc)  # 18:30 MST
    assert digest.after_hours_gate(morning)["after_6pm_local"] is False
    assert digest.after_hours_gate(evening)["after_6pm_local"] is True

    print("wf74_learning_loop_telegram_digest targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
